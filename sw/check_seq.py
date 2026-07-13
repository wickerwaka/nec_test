#!/usr/bin/env python3
"""check_seq - Mission S: chip-vs-core sequence fuzzing.

For each seed: generate a program (gen_seq), compose the standard test
image around it, run it on the real chip (serve path, full capture from
RESET release), replay the SAME image in the Verilator TB (+bootimg -
no backdoor, the loader runs in the core), and diff every cycle row
from RESET release to the store's done marker.

Column policy follows check_boot (mission G): qs from release, bs from
release+8, t/ube/addr/data/ps from release+9; addr on T1 rows, data on
T2/T3 rows and T4/Ti status rows of active cycles, ps on T2 rows.

Usage:
  check_seq.py SEED [SEED...]     one-off checks
  check_seq.py --fuzz N [--start K] [--stop-after M]   campaign
  check_seq.py --sim-only SEED    TB-vs-TB plumbing self-test
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                       # noqa: E402
from gen_seq import generate                           # noqa: E402
from v30run import run_image                           # noqa: E402

ROOT = SW.parent
BIN = ROOT / "hdl" / "tb" / "obj_dir" / "Vtb_v30_core"
T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def compose(g):
    return testimage.compose(regs=g["regs"], instr=g["instr"],
                             ram=g["ram"])


def run_tb(image, n):
    td = tempfile.mkdtemp(prefix="seq_")
    img = Path(td) / "img.hex"
    out = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in image) + "\n")
    r = subprocess.run([str(BIN), f"+bootimg={img}", f"+bootn={n}",
                        f"+out={out}"], capture_output=True, text=True,
                       cwd=ROOT, timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError(f"TB failed: {r.stdout[-300:]} {r.stderr[-200:]}")
    sim = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            sim.append({"t": int(p[1]), "bs_early": int(p[2]),
                        "qs": int(p[3]), "ube_n": int(p[4]),
                        "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                        "ps": int(p[7], 16)})
    return sim


def run_chip(image, host):
    recs = run_image(bytes(image), host, tag="seq")
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    return recs[rel:]


def done_idx(recs, key_addr, key_kind):
    """Index of the done-marker IOW T1 (+ a small tail)."""
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and \
                r["bs_early"] == 2 and \
                (r["ad_addr"] & 0xFFFF) == testimage.OUT_PORT_DONE:
            return i
    return None


def diff(real, sim, limit=4000, maxprint=10):
    """-> (n_mismatch_rows, first_divergence_index)"""
    dend = done_idx(real, None, None)
    n = min(len(real), len(sim), limit,
            (dend + 8) if dend is not None else limit)
    bad, first = 0, None
    for i in range(n):
        r, s = real[i], sim[i]
        rt = r.get("t_state", r.get("t"))
        mm = []
        if r["qs"] != s["qs"]:
            mm.append(f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}")
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            mm.append(f"bs {BS_NAME[r['bs_early']]}!="
                      f"{BS_NAME[s['bs_early']]}")
        if i >= 9:
            if rt != s["t"]:
                mm.append(f"t {T_NAME.get(rt)}!={T_NAME.get(s['t'])}")
            if r["ube_n"] != s["ube_n"]:
                mm.append(f"ube {r['ube_n']}!={s['ube_n']}")
            active = r["bs_early"] != 7
            if rt == 1 and r["ad_addr"] != s["ad_addr"]:
                mm.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if rt in (2, 3) and r["ad_data"] != s["ad_data"]:
                mm.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                mm.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt == 2 and active and r["ps"] != s["ps"]:
                mm.append(f"ps {r['ps']:x}!={s['ps']:x}")
        if mm:
            bad += 1
            if first is None:
                first = i
            if bad <= maxprint:
                print(f"    row {i}: " + ", ".join(mm))
    return bad, first, n


def check_seed(seed, host, sim_only=False):
    g = generate(seed)
    image, meta = compose(g)
    if sim_only:
        real = run_tb(image, 4200)
        real = [dict(r, t_state=r["t"]) for r in real]
    else:
        real = run_chip(image, host)
    sim = run_tb(image, 4200)
    bad, first, n = diff(real, sim)
    status = "MATCH" if bad == 0 else f"DIVERGE@{first}"
    print(f"seed {seed}: {g['n_ins']} ins, {n} rows compared -> {status}"
          f"{f' ({bad} rows)' if bad else ''}")
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="*")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--fuzz", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--stop-after", type=int, default=0,
                    help="stop after M divergent seeds (0 = never)")
    ap.add_argument("--sim-only", action="store_true")
    a = ap.parse_args()
    fails = []
    if a.fuzz:
        for k in range(a.start, a.start + a.fuzz):
            ok = check_seed(f"fz{k}", a.host, a.sim_only)
            if not ok:
                fails.append(f"fz{k}")
                if a.stop_after and len(fails) >= a.stop_after:
                    break
        print(f"\nfuzz: {a.fuzz - len(fails)}/{a.fuzz} clean; "
              f"divergent seeds: {fails}")
        return 1 if fails else 0
    ok = True
    for s in a.seeds:
        ok &= check_seed(s, a.host, a.sim_only)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
