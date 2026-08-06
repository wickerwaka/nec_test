#!/usr/bin/env python3
"""w34_grant -- THE P1 GRANT LAW: what separates the 121 directed entries on
which the chip GRANTS a `CODE` fetch inside the trap entry's window from the 23
`wr1` seeds on which it DECLINES one it could legally make.

Spec, populations, candidate predicates and bars:
`docs/notes/wrfuzz_w34_prereg_2026-08-06.md`, committed at `b84277a414`
BEFORE this file existed.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

WHAT IT ASKS.  `wrfuzz_provenance.md` sec.6.6 closed W3.3 with

    P1 is a GRANT question at the contested slot, not a recognition question.

so the discriminating variable between "prefetch granted inside the
take -> vector window" (directed, 121/563) and "declined" (P1, 23/23) is the
law.  This tool computes, per entry, on the SAME footing for both populations:

  * the take clock, the vector-read T1, and `vec - take`;
  * the previous bus cycle -- status, address, T1, T4 row, active length;
  * the chip's queue OCCUPANCY and IN-FLIGHT bytes as a TRAJECTORY across
    `[take-4, vec]`, reconstructed from the capture's own QS port;
  * `room`: the idle clocks a fetch would have to fit into, which is what
    splits "declined" from "no opportunity";
  * whether a `CODE` T1 falls in `(take, vec)` and at what offset from the
    previous `CODE`.

NOTHING IS FITTED.  Every number is read off a capture or off an engine's own
`brktrace`; the candidates are scored by counting exceptions.

Usage:
    python3 sw/w34_grant.py directed [--core ucore|sim] [--variants ...]
    python3 sw/w34_grant.py p1       [--core ucore|sim]
    python3 sw/w34_grant.py report
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                            # noqa: E402
simbin.ensure("w34 grant law")
import fuzz_classify as fc                               # noqa: E402
import sm3_tf_floor_cell as fcell                        # noqa: E402

CAP = ROOT / "sw" / "testdata" / "sm3-s24tfcell"
OUT = ROOT / "sw" / "testdata" / "w34-grant"
ROM = ROOT / "docs" / "V20BITS.TXT"
W2 = Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2"

TI, T1, T2, T3, TW, T4 = 0, 1, 2, 3, 4, 5
INTA, HALT, CODE, MEMR, MEMW, PASV = 0, 3, 4, 5, 6, 7
QS_NONE, QS_F, QS_E, QS_S = 0, 1, 2, 3


def t_of(r):
    return r.get("t_state", r.get("t"))


# --------------------------------------------------------------------------- #
# the bus, and the queue
# --------------------------------------------------------------------------- #
def cycles(rows):
    """Every bus cycle as a dict: T1 row, status, address, the T4 row (the
    clock the read data is committed), the active length T1..T4 inclusive, and
    the row of the next T1 (`end`)."""
    n = len(rows)
    out = []
    for i in range(n):
        if t_of(rows[i]) != T1 or rows[i]["bs_early"] == PASV:
            continue
        t4 = None
        for j in range(i + 1, n):
            if t_of(rows[j]) == T4:
                t4 = j
                break
            if t_of(rows[j]) == T1:
                break
        out.append({"row": i, "bs": rows[i]["bs_early"],
                    "addr": rows[i]["ad_addr"] & 0xFFFFF,
                    "t4": t4, "alen": (t4 - i + 1) if t4 is not None else None})
    for k in range(len(out)):
        out[k]["end"] = out[k + 1]["row"] if k + 1 < len(out) else n
    return out


def queue_trace(rows, cy):
    """`occ[i]` = queue bytes held on row `i`; `inf[i]` = bytes of `CODE`
    cycles ISSUED but not yet delivered on row `i`.

    The rule is sec.63.6's, sharpened by `q1census.fetches`: a `CODE` cycle at
    an EVEN address delivers TWO bytes, at an ODD address ONE (the upper half
    of the word); the bytes join the queue at the cycle's T4.  A pop is a
    `QS` of F or S; a `QS = E` FLUSHES both the queue and everything in
    flight."""
    n = len(rows)
    occ = [0] * (n + 1)
    inf = [0] * (n + 1)
    fetch = [(c["row"], c["t4"], 1 if (c["addr"] & 1) else 2)
             for c in cy if c["bs"] == CODE and c["t4"] is not None]
    join = defaultdict(list)
    for idx, (t1, t4, _b) in enumerate(fetch):
        join[t4].append(idx)
    dead, q = set(), 0
    for i in range(n):
        if rows[i]["qs"] == QS_E:
            q = 0
            for idx, (t1, _t4, _b) in enumerate(fetch):
                if t1 <= i:
                    dead.add(idx)
        else:
            for idx in join.get(i, ()):
                if idx not in dead:
                    q += fetch[idx][2]
            if rows[i]["qs"] in (QS_F, QS_S):
                q = max(0, q - 1)
        occ[i] = q
        inf[i] = sum(fetch[idx][2] for idx in range(len(fetch))
                     if idx not in dead
                     and fetch[idx][0] <= i < fetch[idx][1])
    return occ, inf


def vector_reads(rows, cy):
    """The T1 row of the FIRST read of every IVT vector pair, plus the vector
    number.  (`w33_take_cell.vector_reads`, unchanged in substance.)"""
    out = []
    for k, c in enumerate(cy):
        if c["bs"] != MEMR or c["addr"] >= 0x400:
            continue
        p = cy[k - 1] if k else None
        if p and p["bs"] == MEMR and p["addr"] < 0x400 and p["addr"] + 2 == c["addr"]:
            continue
        out.append((c["row"], c["addr"] >> 2, k))
    return out


# --------------------------------------------------------------------------- #
# the engines' own take clock
# --------------------------------------------------------------------------- #
BRKT_RE = re.compile(r'BRKT clk=(\d+)')
SIMBRK_RE = re.compile(r'BRKR clk=(\d+) .* take=1')


def _tb(core):
    import timed_fuzz as tf
    return tf.tb_bin(core)


def ucore_run(image, clocks, wargs):
    """The RTL leg with `+brktrace`.  `wargs` is `timed_fuzz.tb_wait_args`'s
    own output -- the seed's OWN wait directive, in the rig's own priority
    order, never a copy of it."""
    td = tempfile.mkdtemp(prefix="w34u_")
    try:
        img = Path(td) / "img.hex"
        outp = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(_tb("ucore")), f"+bootimg={img}", f"+bootn={clocks}",
                "+mirror=1", f"+out={outp}", "+brktrace"] + list(wargs)
        p = subprocess.run(argv, capture_output=True, timeout=900)
        takes = [int(m.group(1)) for m in BRKT_RE.finditer(p.stdout.decode())]
        rows = []
        if outp.exists():
            for line in outp.read_text().splitlines():
                f = line.split()
                if f and f[0] == "r":
                    rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                                 "qs": int(f[3]), "ube_n": int(f[4]),
                                 "ad_addr": int(f[5], 16),
                                 "ad_data": int(f[6], 16), "ps": int(f[7], 16)})
        return takes, rows
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def sim_run(image, clocks, wargs):
    td = tempfile.mkdtemp(prefix="w34s_")
    try:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        env = dict(os.environ)
        env["V30SIM_BRKTRACE"] = "1"
        argv = [str(simbin.SIM), "timed-boot", str(ROM), str(img),
                f"--clocks={clocks}", "--ndjson"] + list(wargs)
        p = subprocess.run(argv, capture_output=True, env=env, timeout=600)
        takes = [int(m.group(1)) for m in SIMBRK_RE.finditer(p.stderr.decode())]
        rows = []
        for l in p.stdout.decode().splitlines():
            if l.startswith("{"):
                o = json.loads(l)
                if "t" in o:
                    rows.append(o)
        return takes, rows
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# --------------------------------------------------------------------------- #
# the per-entry measurement, identical for both populations
# --------------------------------------------------------------------------- #
def measure_entry(rows, cy, occ, inf, vrow, vk, take):
    """Every quantity sec.3 of the pre-registration lists, for ONE entry."""
    p = cy[vk - 1] if vk else None
    m = {"vec": vrow, "take": take, "vt": (vrow - take) if take is not None
         else None}
    if p:
        m["prev_bs"] = fc.BS_NAME[p["bs"]]
        m["prev_addr"] = p["addr"]
        m["prev_t1"] = p["row"]
        m["prev_t4"] = p["t4"]
        m["prev_alen"] = p["alen"]
        m["prev_free"] = (p["t4"] + 1) if p["t4"] is not None else None
        m["room"] = vrow - m["prev_free"] if m["prev_free"] is not None else None
        if take is not None and p["t4"] is not None:
            m["t4_minus_take"] = p["t4"] - take
            m["take_minus_prevt1"] = take - p["row"]
    # the previous CODE fetch, whatever came between
    pc = None
    for c in reversed(cy[:vk]):
        if c["bs"] == CODE:
            pc = c
            break
    if pc:
        m["prevcode_addr"] = pc["addr"]
        m["prevcode_t1"] = pc["row"]
        m["prevcode_t4"] = pc["t4"]
    # the grant, if any
    g = [c for c in cy[:vk] if c["bs"] == CODE and take is not None
         and take < c["row"] < vrow]
    m["n_code"] = len(g)
    if g:
        m["grant_t1"] = g[0]["row"]
        m["grant_addr"] = g[0]["addr"]
        m["grant_minus_take"] = g[0]["row"] - take
    # `L` -- the bus cycle IN PROGRESS OR LAST COMPLETED at the take.  This is
    # the apples-to-apples anchor: for a GRANTED entry `cy[vk-1]` is the grant
    # itself, so anything measured against it is measuring the answer.
    if take is not None:
        L = None
        for c in cy:
            if c["row"] < take:
                L = c
            else:
                break
        if L is not None and L["t4"] is not None:
            m["L_bs"] = fc.BS_NAME[L["bs"]]
            m["L_t1"] = L["row"]
            m["L_t4"] = L["t4"]
            m["L_alen"] = L["alen"]
            m["L_t4_minus_take"] = L["t4"] - take
            m["L_take_minus_t1"] = take - L["row"]
            free = min(L["t4"] + 1, len(occ) - 1)
            m["L_free"] = free
            m["oi_at_Lfree"] = occ[free] + inf[free]
            m["occ_at_Lfree"] = occ[free]
            m["inf_at_Lfree"] = inf[free]
            m["L_room"] = vrow - free
    if take is not None:
        lo, hi = max(0, take - 4), min(len(occ) - 1, vrow)
        m["occ_traj"] = [occ[i] for i in range(lo, hi + 1)]
        m["inf_traj"] = [inf[i] for i in range(lo, hi + 1)]
        m["traj_lo"] = lo
        m["occ_at_take"] = occ[take]
        m["inf_at_take"] = inf[take]
        m["oi_at_take"] = occ[take] + inf[take]
        if p and p["t4"] is not None:
            f = min(p["t4"] + 1, len(occ) - 1)
            m["occ_at_free"] = occ[f]
            m["inf_at_free"] = inf[f]
            m["oi_at_free"] = occ[f] + inf[f]
    return m


# --------------------------------------------------------------------------- #
# population G / N -- the directed cells
# --------------------------------------------------------------------------- #
def _directed_one(args):
    v, w, core = args
    cpath = CAP / f"{v}_w{w}_r0.rows.json.gz"
    if not cpath.exists():
        return None
    with gzip.open(cpath, "rt") as f:
        chip = json.load(f)
    image, _ = fcell.image_of(v)
    n = len(chip)
    wargs = ([f"+waits={w}"] if core == "ucore" else [f"--waits={w}"])
    takes, erows = (ucore_run(image, n, wargs) if core == "ucore"
                    else sim_run(image, n, wargs))
    if not erows:
        return {"cell": f"{v}:w{w}", "error": "ENGINE"}
    m = min(len(chip), len(erows))
    d = fc.diff_rows(chip[:m], erows[:m], window=m)
    cy = cycles(chip)
    occ, inf = queue_trace(chip, cy)
    ent = []
    for (vrow, vec, vk) in vector_reads(chip, cy):
        if vec != 1:
            continue
        tk = [t for t in takes if t < vrow]
        if not tk:
            continue
        ent.append(measure_entry(chip, cy, occ, inf, vrow, vk, tk[-1]))
    return {"cell": f"{v}:w{w}", "variant": v, "waits": w,
            "exact": d.bad == 0, "row_diffs": d.bad, "n_rows": m,
            "entries": ent}


def cmd_directed(a):
    variants = a.variants.split(",") if a.variants else \
        [v for v in fcell.VARIANTS if v.startswith("popf")]
    waits = [int(x) for x in a.waits.split(",")]
    jobs = [(v, w, a.core) for v in variants for w in waits]
    with Pool(a.jobs) as pool:
        res = [r for r in pool.map(_directed_one, jobs) if r]
    OUT.mkdir(parents=True, exist_ok=True)
    tag = a.tag or "popf"
    (OUT / f"directed_{a.core}_{tag}.json").write_text(json.dumps(res, indent=1))
    n_g = n_n = 0
    for c in res:
        if c.get("error") or not c["exact"]:
            print(f"  {c['cell']:<16} EXCLUDED  "
                  f"{c.get('error') or 'row_diffs %d' % c['row_diffs']}")
            continue
        g = sum(1 for e in c["entries"] if e["n_code"])
        n_g += g
        n_n += len(c["entries"]) - g
        print(f"  {c['cell']:<16} exact  entries={len(c['entries']):3d}  "
              f"granted={g:3d}  vt={dict(Counter(e['vt'] for e in c['entries']))}")
    print(f"\n  TOTAL granted={n_g}  no-grant={n_n}")
    return 0


# --------------------------------------------------------------------------- #
# population P -- the 23 P1 seeds
# --------------------------------------------------------------------------- #
def p1_seeds(core):
    part = json.load(open(W2 / f"w32_part_{core}.json"))
    return [r for r in part if r["cls"] == "SAME_BOUNDARY"
            and r["geom"]["n_ins"] == 1]


def _p1_one(args):
    rec, core = args
    import ucsim_fuzz as uf
    import timed_fuzz as tf
    seeds = sorted(Path(W2 / "seeds").glob(f"*_{rec['k']}_*.json.gz"))
    entry = json.loads(gzip.decompress(seeds[0].read_bytes()))
    chip = entry["chip_rows"]
    image, meta, g, sha = uf.regen(entry)
    if sha != entry["image_sha256"]:
        return {"seed": rec["seed"], "k": rec["k"], "error": "GEN_DRIFT"}
    n = len(chip)
    wobj = entry.get("waits") or {}
    # the seed's OWN wait directive, from `timed_fuzz`'s own builders
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            erows, err = tf.run_sim(image, entry, n, td)
            wargs = tf.wait_args(entry, td)
            takes, _r2 = sim_run(image, n, wargs)
        else:
            erows, err = tf.run_tb(image, entry, n, td, core)
            wargs = tf.tb_wait_args(entry, td)
            takes, _r2 = ucore_run(image, n, wargs)
    ccy = cycles(chip)
    cocc, cinf = queue_trace(chip, ccy)
    ecy = cycles(erows) if erows else []
    eocc, einf = queue_trace(erows, ecy) if erows else ([], [])
    crow = rec["geom"]["crow"]
    erow = rec["geom"]["erow"]
    ck = next((k for k, c in enumerate(ccy) if c["row"] == crow), None)
    ek = next((k for k, c in enumerate(ecy) if c["row"] == erow), None)
    out = {"seed": rec["seed"], "k": rec["k"], "stratum": rec["stratum"],
           "waits": wobj, "delta": rec["geom"]["delta"],
           "n_takes": len(takes)}
    if ck is None:
        out["error"] = "NO_CHIP_ENTRY"
        return out
    take_v9 = crow - 9
    tk = [t for t in takes if t < erow]
    take_eng = tk[-1] if tk else None
    out["chip"] = measure_entry(chip, ccy, cocc, cinf, crow, ck, take_v9)
    out["chip_at_engtake"] = (measure_entry(chip, ccy, cocc, cinf, crow, ck,
                                            take_eng)
                              if take_eng is not None else None)
    if ek is not None and erows:
        out["eng"] = measure_entry(erows, ecy, eocc, einf, erow, ek, take_eng)
    out["take_eng"] = take_eng
    out["take_vec9"] = take_v9
    out["take_gap"] = (take_eng - take_v9) if take_eng is not None else None
    return out


def cmd_p1(a):
    recs = p1_seeds(a.core)
    with Pool(a.jobs) as pool:
        res = pool.map(_p1_one, [(r, a.core) for r in recs])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"p1_{a.core}.json").write_text(json.dumps(res, indent=1))
    print(f"== w34_grant p1 --core {a.core} -- {len(res)} seeds")
    print(f"{'seed':<12}{'strat':<14}{'d':>3} {'take_e':>7}{'take_9':>7}"
          f"{'gap':>4}  chip: {'oi@take':>8}{'oi@free':>8}{'room':>5}"
          f"{'t4-tk':>6}  eng: {'oi@take':>8}{'grant':>6}")
    for r in res:
        if r.get("error"):
            print(f"{r['seed']:<12} {r['error']}")
            continue
        c, e = r["chip"], r.get("eng") or {}
        print(f"{r['seed']:<12}{str(r['stratum']):<14}{r['delta']:>3} "
              f"{str(r['take_eng']):>7}{r['take_vec9']:>7}{str(r['take_gap']):>4}  "
              f"      {str(c.get('oi_at_take')):>8}{str(c.get('oi_at_free')):>8}"
              f"{str(c.get('room')):>5}{str(c.get('t4_minus_take')):>6}"
              f"        {str(e.get('oi_at_take')):>8}"
              f"{str(e.get('grant_minus_take')):>6}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("directed")
    p.add_argument("--core", default="ucore", choices=("ucore", "sim"))
    p.add_argument("--variants", default=None)
    p.add_argument("--waits", default="0,3")
    p.add_argument("--jobs", type=int, default=10)
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_directed)
    p = sub.add_parser("p1")
    p.add_argument("--core", default="ucore", choices=("ucore", "sim"))
    p.add_argument("--jobs", type=int, default=8)
    p.set_defaults(fn=cmd_p1)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
