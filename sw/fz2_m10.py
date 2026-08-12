#!/usr/bin/env python3
"""fz2_m10 -- THE M10 (family `E1`) EA-FORK DIAGNOSTIC.

M10 is the fz2 failure ledger's family `E1`, "same-status data cycle, different
address": at one clock both legs run a data cycle of the SAME bus status and
drive DIFFERENT addresses.  It is the largest un-diagnosed block in the F15
ledger and nothing in the ledger names a mechanism for it.

THIS FILE IS A DIAGNOSTIC, NOT A GATE.  It answers three questions and it
answers each of them off an artifact:

  `survey`   -- what the family IS on the F15 ledger: the forking cycle's
                status and address on both legs, the instruction the chip had
                in dispatch (`fz2_failview`'s shadow-queue reconstruction,
                validated 116/116 there), the opcode/ModRM the fork dispatched,
                and the cross-cut against the two CONCURRENT packages, P4'
                (the `8F` mod==3 ghost) and P5' (`8E`/1, the CS retarget).
                A seat whose fork dispatches either belongs to that package and
                not to M10.

  `solve`    -- the register-file solve the F14 survey proposed.  For a seat,
                replay the seed offline on the receipted `--core ucore`
                `tb_v30_core` binary, freeze the core AT THE FORK CLOCK through
                the save-state map (`+ss_at=<clk> +ss_mode=6`, the addressed
                read that already exists -- no RTL change, §49.8's deciding
                measurement in its READ form), and ask which
                (segment, register, displacement) triple forms the CHIP's
                address.  The core's own architectural registers are the
                solve's basis: on the cheap subset (`arch_match` and few
                diverging rows) the two engines agree on architectural state,
                so the fork is a difference in HOW the EA was formed, not in
                WHAT it was formed from.

  `report`    -- both, as the markdown tables the diagnosis document carries.

WHAT THE SOLVE MAY AND MAY NOT CONCLUDE.  The replay must reproduce the fork:
same row, same core address, same chip address.  A seat whose offline replay
does not put the fork where the board put it is reported `NOREPRO` and is NOT
scored -- an address solved at the wrong clock is a fitted number.  The
`tb_v30_core` replay is faithful only up to the substituted-NMI vector read
(`fz2_a1_rescore.cut`, erratum E-1), and every fork used here is before it.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                              # noqa: E402
import fuzz_campaign as fzc                                   # noqa: E402
import fuzz_classify as fc                                    # noqa: E402
import fz2_failview as fv                                     # noqa: E402
import fz2_replay as fzr                                      # noqa: E402
import fz2_tbsys as tbs                                       # noqa: E402

LEDGER = ROOT / "sw" / "testdata" / "fz2" / \
    "fz2_failure_ledger_f15_2026-08-10.json"
FAMILY = "E1 same-status data cycle, different address"

BS_NAME = fv.BS_NAME

# --------------------------------------------------------------------------- #
# the save-state addresses this file reads.  Values are LIFTED from
# hdl/rtl/ucore/v30u_ss_pkg.sv by `ss_addrs()` -- never transcribed, because a
# transcribed address is a number with no artifact id.
# --------------------------------------------------------------------------- #
# the eight GPR save-state names, in the ModRM r/m ORDER the part uses
GPR_ORDER = ["SSA_E_AX", "SSA_E_CX", "SSA_E_DX", "SSA_E_BX",
             "SSA_E_SP", "SSA_E_BP", "SSA_E_IX", "SSA_E_IY"]
GPR_NAME = ["AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY"]
SEG_ORDER = ["SSA_E_ES", "SSA_E_CS", "SSA_E_SS", "SSA_E_DS"]
SEG_NAME = ["ES", "CS", "SS", "DS"]


def ss_addrs():
    """{symbol: address} lifted from the RTL package.  ARTIFACT, not recall."""
    src = (ROOT / "hdl" / "rtl" / "ucore" / "v30u_ss_pkg.sv").read_text()
    out = {}
    for m in re.finditer(r"localparam\s+logic\s+\[8:0\]\s+(SSA_\w+)\s*=\s*"
                         r"9'h([0-9A-Fa-f]+)\s*;", src):
        out[m.group(1)] = int(m.group(2), 16)
    return out


# --------------------------------------------------------------------------- #
# corpus
# --------------------------------------------------------------------------- #
_LINES = {}


def lines():
    if _LINES:
        return _LINES
    for cid in ("fz2c", "fz2e"):
        p = ROOT / "sw" / "testdata" / "campaigns" / cid / "results.jsonl"
        for ln in open(p):
            r = json.loads(ln)
            _LINES[r["seed"]] = r
    return _LINES


def seats(ledger=LEDGER, family=FAMILY):
    led = json.load(open(ledger))
    return led, [e for e in led["failures"] if e["family"] == family]


def capture(e):
    raw = Path(e["capture"]).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != e["capture_sha256"]:
        raise ValueError(f"{e['seed']}: capture sha256 {got[:16]}… != ledger")
    return json.loads(gzip.decompress(raw))


# --------------------------------------------------------------------------- #
# the forking cycle
# --------------------------------------------------------------------------- #
def cycle_at(rows, i):
    """(t1_row, addr, bs) for the bus cycle the fork row `i` belongs to or
    previews.

    At a `Ti`/`T4` row the AD lines carry the NEXT cycle's address preview
    (`nxta`, low 16 bits) and the full 20-bit address only appears at that
    cycle's own `T1`.  So the cycle a fork row NAMES is the first `T1` at or
    after it, and that is the row whose address is comparable across legs."""
    for j in range(i, min(len(rows), i + 12)):
        if rows[j]["t"] == 1:
            return j, rows[j]["ad_addr"] & 0xFFFFF, rows[j]["bs_early"]
    return None, None, None


def dispatched(cap, fb):
    """(group, groups_before_and_including_it, bmap).

    `group` is what `fz2_failview` calls "in dispatch at the fork" -- the last
    `QS = F` pop at or before the fork row, its own cut, its own shadow queue,
    its own group rule.  The LIST is the retired run up to and including it,
    because a bus cycle is NOT necessarily the dispatched instruction's: the
    BIU runs behind the EU, so an instruction that retired two `F` pops ago can
    still own the cycle standing on the wire.  Every claim this file makes
    about a preceding instruction says HOW MANY `F` pops back it is."""
    pops, bmap = fv.shadow(cap["real"])
    gs = fv.groups_of(pops)
    pre = [g for g in gs if g["f_row"] <= fb]
    if not pre:
        return None, [], bmap
    return pre[-1], pre, bmap


def modrm_of(bs):
    """(opcode, modrm) for a retired byte group, honouring 0x0F two-byte and
    the segment/REP prefixes the part retires as their OWN groups (so a group
    here is one instruction OR one prefix -- there is no prefix to skip)."""
    if not bs:
        return None, None
    op = bs[0]
    if op == 0x0F and len(bs) > 1:
        return 0x0F00 | bs[1], (bs[2] if len(bs) > 2 else None)
    return op, (bs[1] if len(bs) > 1 else None)


# opcodes whose FORK belongs to a concurrent package rather than to M10
def package_of(op, mrm):
    """'P4' for the 8F mod==3 ghost, 'P5' for 8E/1 (the CS retarget), else
    None.  Both are "different address, same status" by construction and both
    are being fixed CONCURRENTLY -- a seat whose fork is theirs is that
    package's seat, not M10's."""
    if op == 0x8F and mrm is not None and (mrm >> 6) == 3:
        return "P4"
    if op == 0x8E and mrm is not None and ((mrm >> 3) & 7) == 1:
        return "P5"
    return None


def nearest_package(groups):
    """(package, F-pops back, bytes) for the nearest preceding instruction that
    belongs to a concurrent package, scanning BACKWARDS from the fork.

    THIS IS THE CORRECTION THE ARTIFACT FORCED.  Attributing a fork to the
    instruction whose `F` pop is nearest it MISSES the `8F` ghost entirely: the
    ghost read is a bus cycle the 8F mod==3 form issues AFTER it retires, so by
    the time the cycle reaches the pins the queue has already popped the NEXT
    instruction's `F` and `fz2_failview` names THAT one.  Five of the ten seats
    the first cut called "cheap M10" have an `8F` mod==3 one or two pops back
    and the fork is its stack read.  `dist` is reported for every seat so a
    reader can apply their own cut."""
    for back, g in enumerate(reversed(groups)):
        p = package_of(*modrm_of(g["bytes"]))
        if p:
            return p, back, " ".join(f"{b:02x}" for b in g["bytes"])
    return None, None, None


def survey_one(e):
    cap = capture(e)
    real, sim, line = cap["real"], cap["sim"], cap["line"]
    win = e["compare_window"]
    dr = fc.diff_rows(real, sim, window=win)
    fb = e["first_bad_row"]
    repro = (dr.first == fb)

    marks, _flick = fv.marks_of(dr)
    first_cols = sorted(marks.get(fb, set())) if repro else []
    r_t1, r_addr, r_bs = cycle_at(real, fb)
    s_t1, s_addr, s_bs = cycle_at(sim, fb)
    g, pre, bmap = dispatched(cap, fb) if repro else (None, [], None)
    bs_bytes = g["bytes"] if g else []
    op, mrm = modrm_of(bs_bytes)
    npk, ndist, nbytes = nearest_package(pre[-6:]) if pre else (None, None, None)

    d = {
        "seed": e["seed"], "tier": e["tier"],
        "first_bad_row": fb, "repro": repro,
        "diverging_rows": e["diverging_rows"],
        "arch_match": bool(line.get("arch_match")),
        "mech": e["mech"], "win": win,
        "waits": ("wrand" if line["waits"]["wrand"] else
                  ("wvec" if line.get("wvec") else
                   f"fixed w{line['waits']['fixed']}")),
        "chip_t1_row": r_t1, "core_t1_row": s_t1,
        "chip_addr": r_addr, "core_addr": s_addr,
        "chip_bs": BS_NAME.get(r_bs), "core_bs": BS_NAME.get(s_bs),
        "first_cols": first_cols,
        "t1_addr_differs": (r_addr is not None and s_addr is not None
                            and r_addr != s_addr),
        "f_row": (g["f_row"] if g else None),
        "dispatch_addr": (g["addr"] if g else None),
        "bytes": " ".join(f"{b:02x}" for b in bs_bytes),
        "op": op, "modrm": mrm,
        "mod": (mrm >> 6) if mrm is not None else None,
        "reg": ((mrm >> 3) & 7) if mrm is not None else None,
        "rm": (mrm & 7) if mrm is not None else None,
        "package": package_of(op, mrm),
        "near_package": npk, "near_dist": ndist, "near_bytes": nbytes,
        "prev_bytes": [" ".join(f"{b:02x}" for b in x["bytes"])
                       for x in pre[-6:]],
    }
    if d["chip_addr"] is not None and d["core_addr"] is not None:
        d["delta"] = (d["chip_addr"] - d["core_addr"]) & 0xFFFFF
        d["para_aligned"] = (d["chip_addr"] % 16) == (d["core_addr"] % 16)
        d["chip_mod16"] = d["chip_addr"] % 16
    return d


# --------------------------------------------------------------------------- #
# the offline replay + the save-state freeze
# --------------------------------------------------------------------------- #
def replay(seed, ss_at=None, n=4200):
    """(rows, ss_words).  The seed's own image through the campaign's own
    generator (image sha256 ASSERTED), the campaign's own wait source, the
    campaign's own terminating NMI on the TB's single scheduler -- i.e.
    `fz2_a1_rescore.one`'s call, with `+ss_at/+ss_mode=6` added and stdout
    kept.  `ss_words` is {address: value} at CE clock `ss_at`, or {}."""
    cid, k = seed.split("/")
    k = int(k)
    cfg = fzc.derive_case(cid, k, fv.ov_for(cid, k))
    image, meta = fzc.compose_case(fzc.build(cfg), cfg)
    if hashlib.sha256(bytes(image)).hexdigest() != lines()[seed]["image_sha256"]:
        raise ValueError(f"{seed}: GEN_DRIFT")
    evts, _, _ = fzc.term_directive(cfg, meta)
    w = cfg["waits"]
    evt = evts[fzc.TERM_SCHED]
    wvec = fzc.wvec_of(cfg)
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None

    td = tempfile.mkdtemp(prefix="m10_", dir=os.environ.get(
        "UCSIMT_TMP", str(Path.home() / ".cache" / "ucsimt-tmp")))
    try:
        img = Path(td) / "img.hex"
        out = Path(td) / "out.txt"
        im = bytes(image) * 16 if len(image) == (1 << 16) else bytes(image)
        img.write_text("\n".join(f"{b:02x}" for b in im) + "\n")
        args = [str(check_seq.tb_bin("ucore")), f"+bootimg={img}",
                f"+bootn={n}", f"+out={out}",
                f"+waits={0 if w['wrand'] else w['fixed']}"]
        if wvec is not None:
            wv = Path(td) / "wvec.hex"
            wv.write_text("\n".join(f"{min(255, max(0, int(x))):02x}"
                                    for x in wvec) + "\n")
            args += [f"+wvec={wv}"]
        elif wrand is not None:
            args += ["+wrand=1", f"+wmax={wrand[0]}", f"+wseed={wrand[1]:04x}"]
        if evt is not None:
            a, dl, ho, p = evt
            args += [f"+evaddr={a:05x}", f"+evdelay={dl}",
                     f"+evhold={ho}", f"+evpin={p}"]
        if ss_at is not None:
            args += [f"+ss_at={ss_at}", "+ss_mode=6", "+ss_scramble_seed=0"]
        r = subprocess.run(args, capture_output=True, text=True,
                           cwd=ROOT, timeout=900)
        if "BOOT DONE" not in r.stdout:
            raise RuntimeError(f"TB failed: {r.stdout[-300:]}{r.stderr[-200:]}")
        rows = []
        for ln in out.read_text().splitlines():
            p = ln.split()
            if p and p[0] == "r":
                rows.append({"t": int(p[1]), "bs_early": int(p[2]),
                             "qs": int(p[3]), "ube_n": int(p[4]),
                             "ad_addr": int(p[5], 16),
                             "ad_data": int(p[6], 16), "ps": int(p[7], 16)})
        ss = {}
        for m in re.finditer(r"SS6 idx=(\d+) word=\d+ addr=([0-9a-f]+) "
                             r"val=([0-9a-f]+)", r.stdout):
            ss[int(m.group(2), 16)] = int(m.group(3), 16)
        return rows, ss
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


SS6_RE = re.compile(r"SS6 idx=-?\d+ word=\d+ addr=([0-9a-f]+) val=([0-9a-f]+)")


def replay_tbsys(seed, ss_at=None, leg="ret"):
    """(rows, ss_words) -- THE SAME QUESTION, ON `tb_sys` (`M10-SYS`).

    Wave-8 §2 is the reason this exists: `tb_v30_core` has ONE pin-event
    scheduler and SIX of thirteen DERIVE seats are `NOREPRO` on it for harness
    reasons, while `fz2_replay --leg ret` on THIS harness reproduces the fabric
    verdict AND the fabric first-bad row on 28 of 28 of the same seeds.

    The case is derived through `fz2_replay.regen_case` -- `fuzz_campaign`'s own
    three calls in its own order, KEEPING the cfg `build()` mutated, because
    `ucsim_fuzz.regen` drops that mutation and 679 of the corpus's event seeds
    would silently run at a 2-clock hold where the capture was taken at 300
    (fz2_replay's module docstring).  The directive, the overlay and the wait
    source are `fz2_replay.replay_sys`'s, unchanged: BOTH schedulers, `TVEC`,
    `VECCTL`, and the seed's own `wvec`/`wrand`/fixed level."""
    cid, k = seed.split("/")
    k = int(k)
    cfg, image, meta, sha = fzr.regen_case(cid, k)
    if sha != lines()[seed]["image_sha256"]:
        raise ValueError(f"{seed}: GEN_DRIFT")
    evts, tvec, vecsub = fzc.term_directive(cfg, meta)
    w = cfg["waits"]
    cs, ip = tvec
    td = tempfile.mkdtemp(prefix="m10sys_", dir=os.environ.get(
        "UCSIMT_TMP", str(Path.home() / ".cache" / "ucsimt-tmp")))
    try:
        r = tbs.run_tb(leg, image, Path(td) / "cap.hex", ncap=fzr.NCAP,
                       waits=0 if w["wrand"] else w["fixed"], div=fzr.DIV,
                       evts={i: t for i, t in enumerate(evts) if t},
                       tvec=(cs << 16) | ip, vecctl=vecsub,
                       wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
                       wvec=fzc.wvec_of(cfg), quiet=True, ss_at=ss_at)
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)
    rows = [] if ss_at is not None else fzr._drop_reset(tbs.decode(r["words"]))
    ss = {int(m.group(1), 16): int(m.group(2), 16)
          for m in SS6_RE.finditer(r["stdout"])}
    return rows, ss


def replay_for(tb):
    return replay if tb == "core" else replay_tbsys


# --------------------------------------------------------------------------- #
# the address solve
# --------------------------------------------------------------------------- #
TERMS = ["AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY",
         "PC", "TMPA", "TMPB", "TMPC", "OPR", "IND",
         "M_EA", "R_EA", "WB_EA", "PEND_OFF", "EA_RESIDUE", "EA_PAIR_RHS",
         "ZERO"]


def terms_of(ss, A):
    """The named 16-bit values the part can put on its internal address bus,
    read out of the save-state map at ONE freeze.  Nothing here is derived,
    fitted or offset: each is one register the map already carries."""
    def g(n):
        return ss.get(A[n], 0) & 0xFFFF
    t = {GPR_NAME[i]: g(GPR_ORDER[i]) for i in range(8)}
    t.update({"PC": g("SSA_E_PC"), "TMPA": g("SSA_E_TMPA"),
              "TMPB": g("SSA_E_TMPB"), "TMPC": g("SSA_E_TMPC"),
              "OPR": g("SSA_E_OPR"), "IND": g("SSA_E_IND"),
              "M_EA": g("SSA_E_M_EA"), "R_EA": g("SSA_E_R_EA"),
              "WB_EA": g("SSA_E_WB_EA"), "PEND_OFF": g("SSA_E_PEND_OFF"),
              "EA_RESIDUE": g("SSA_E_EA_RESIDUE"),
              "EA_PAIR_RHS": g("SSA_E_EA_PAIR_RHS"), "ZERO": 0})
    return t


def exprs_of(t):
    """{name: value} over the term set and the TWO bit-wise combinations a
    shared internal bus can produce when two drivers are live at once: the
    wired-AND and the wired-OR.  There is no addition, no mask, no constant
    and no per-opcode case in this space -- if the answer needed one it would
    be a fitted table and the SIMPLICITY principle says that is a signal of
    misunderstanding, not a deliverable."""
    e = dict(t)
    ks = [k for k in TERMS if k != "ZERO"]
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            e[f"{a}&{b}"] = t[a] & t[b]
            e[f"{a}|{b}"] = t[a] | t[b]
    return e


def fits_at(target, ss, A):
    """Every (segment, expression) that reproduces `target` EXACTLY, with no
    displacement term at all.  A displacement is a free parameter and one free
    parameter fits anything; the constraint that has teeth is the exact one."""
    t = terms_of(ss, A)
    sg = {SEG_NAME[i]: (ss.get(A[SEG_ORDER[i]], 0) & 0xFFFF) for i in range(4)}
    ex = exprs_of(t)
    out = []
    for sn, sv in sg.items():
        base = (sv << 4) & 0xFFFFF
        for en, ev in ex.items():
            if (base + ev) & 0xFFFFF == target:
                out.append(f"{sn}:{en}")
            elif (base + ev + 1) & 0xFFFFF == target:
                # the SECOND half of a split (odd-address) word.  `acc_phys2`
                # is `acc_phys_base + 1` in the RTL, so `+1` is the part's own
                # arithmetic and not a free parameter fitted here.
                out.append(f"{sn}:{en}+1")
    return out, t, sg


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_survey(a):
    led, ss = seats(a.ledger)
    rows = [survey_one(e) for e in ss]
    json.dump({"ledger": str(a.ledger), "family": FAMILY,
               "n": len(rows), "rows": rows},
              open(a.out, "w"), indent=1)
    n = len(rows)
    print(f"M10 / family `{FAMILY}` on {Path(a.ledger).name}: {n} seats")
    print(f"  reconstruction reproduces the fork row: "
          f"{sum(1 for r in rows if r['repro'])}/{n}")
    print(f"  the forking cycle's T1 address differs: "
          f"{sum(1 for r in rows if r['t1_addr_differs'])}/{n}")
    print(f"  paragraph-aligned delta (chip%16 == core%16): "
          f"{sum(1 for r in rows if r.get('para_aligned'))}/{n}")
    import collections
    print(f"  chip address mod 16 == 0: "
          f"{sum(1 for r in rows if r.get('chip_mod16') == 0)}/{n}")
    print(f"  first diverging COLUMN at the fork: "
          f"{collections.Counter('+'.join(r['first_cols']) for r in rows).most_common()}")
    print(f"  distinct dispatched opcodes: "
          f"{len({r['op'] for r in rows if r['op'] is not None})}")
    pk = collections.Counter(r["package"] for r in rows)
    print(f"  RECLASSIFY, cut at the fork's OWN dispatch:"
          f"  P4' (8F mod==3): {pk.get('P4', 0)}"
          f"   P5' (8E/1): {pk.get('P5', 0)}"
          f"   stays M10: {pk.get(None, 0)}")
    nk = collections.Counter(r["near_package"] for r in rows)
    print(f"  RECLASSIFY, nearest within 6 F pops:"
          f"  P4': {nk.get('P4', 0)}   P5': {nk.get('P5', 0)}"
          f"   stays M10: {nk.get(None, 0)}")
    dd = collections.Counter(r["near_dist"] for r in rows
                             if r["near_package"] == "P4")
    print(f"    P4' distance histogram (F pops back): "
          f"{sorted(dd.items())}")
    for r in rows:
        print(f"    {r['seed']:<14} fork {r['first_bad_row']:>5} "
              f"div {r['diverging_rows']:>4} arch "
              f"{'OK ' if r['arch_match'] else 'DIF'} "
              f"{r['chip_bs']:<5} chip "
              f"{('%05x' % r['chip_addr']) if r['chip_addr'] is not None else '-----'}"
              f" core "
              f"{('%05x' % r['core_addr']) if r['core_addr'] is not None else '-----'}"
              f"  pkg {str(r['near_package']):<4}@{str(r['near_dist']):<4}"
              f" [{r['bytes']}]")
    cheap = [r for r in rows if r["arch_match"] and r["diverging_rows"] <= 8
             and r["near_package"] is None]
    print(f"  CHEAP SUBSET (arch_match & <=8 diverging & not reclassified): "
          f"{len(cheap)}")
    for r in cheap:
        print(f"    {r['seed']:<14} fork {r['first_bad_row']:>5} "
              f"div {r['diverging_rows']:>2} "
              f"{r['chip_bs']:<5} chip {r['chip_addr']:05x} "
              f"core {r['core_addr']:05x} "
              f"op {r['op']:02x} mrm "
              f"{('%02x' % r['modrm']) if r['modrm'] is not None else '--'}"
              f"  [{r['bytes']}]")
    print(f"\nwrote {a.out}")


def _one_solve(job):
    """One seat: validate the offline replay against the board, sweep the
    save-state freeze across the fork, and report every named term that
    reproduces the CHIP's address and every one that reproduces the CORE's."""
    seed, fb, chip, core, win, ledger, span, tb = job
    A = ss_addrs()
    rp = replay_for(tb)
    rec = {"seed": seed, "fork_row": fb, "chip_addr": chip,
           "core_addr": core, "tb": tb}
    try:
        rows, _ = rp(seed)
    except Exception as ex:                                   # noqa: BLE001
        rec["status"] = f"REPLAY_ERR {str(ex)[:100]}"
        return rec
    cap = capture(next(e for e in seats(ledger)[1] if e["seed"] == seed))
    dr = fc.diff_rows(cap["real"], rows, window=win)
    bad = [x for x in dr.rows if not x.flicker]
    off_fork = bad[0].i if bad else None
    _t1, off_addr, _bs = cycle_at(rows, fb)
    rec["offline_fork_row"] = off_fork
    rec["offline_core_addr"] = off_addr
    if off_fork != fb or off_addr != core:
        rec["status"] = "NOREPRO"
        return rec
    # THE ROW -> CE-CLOCK OFFSET IS MEASURED, NOT ASSUMED.  `cpu_cyc` counts CE
    # posedges from reset release and the recorded row index counts rows the TB
    # emitted while `recording`; the BIU's own current-address register
    # (`SSA_B_CUR_ADDR_LO/HI`) is printed at every freeze, so a reader can see
    # for themselves which freeze is standing on the forking cycle.  A seat
    # whose sweep never shows that address is visible here and is not quoted.
    rec["status"] = "SOLVED"
    rec["freezes"] = []
    for d in range(-span, 2):
        try:
            _r, ss = rp(seed, ss_at=fb + d)
        except Exception:                                     # noqa: BLE001
            continue
        if not ss:
            continue
        cf, t, sg = fits_at(chip, ss, A)
        kf, _, _ = fits_at(core, ss, A)
        biu = ((ss.get(A["SSA_B_CUR_ADDR_LO"], 0) |
                (ss.get(A["SSA_B_CUR_ADDR_HI"], 0) << 16)) & 0xFFFFF)
        rec["freezes"].append({"delta": d, "biu_addr": biu,
                               "chip_fits": cf, "core_fits": kf,
                               "terms": t, "segs": sg})
    return rec


def cmd_control(a):
    """THE BASE RATE.  "31 of 41 seats have an `8F` mod==3 within 6 `F` pops of
    the fork" is not evidence until the same statistic is measured where the
    fork ISN'T.  This is the corpus's OWN control and it holds the seed fixed:
    for every M10 seat, `--samples` rows drawn uniformly from that seed's own
    scored window, scored by the identical rule on the identical reconstruction.

    A second control runs the identical rule at the fork rows of every OTHER
    family in the ledger, which asks whether the proximity is a property of
    forks in general or of THIS family's forks."""
    import random
    led, ss = seats(a.ledger)
    rng = random.Random(a.seed)
    hit = tot = 0
    per = []
    for e in ss:
        cap = capture(e)
        pops, _bm = fv.shadow(cap["real"])
        gs = fv.groups_of(pops)
        win = e["compare_window"]
        h = 0
        for _ in range(a.samples):
            row = rng.randrange(64, max(65, min(win, len(cap["real"]))))
            pre = [g for g in gs if g["f_row"] <= row]
            p, _d, _b = nearest_package(pre[-6:]) if pre else (None, None, None)
            if p == "P4":
                h += 1
        per.append((e["seed"], h))
        hit += h
        tot += a.samples
    print(f"CONTROL A -- random rows inside the SAME {len(ss)} seeds' own "
          f"windows, same rule, same reconstruction")
    print(f"  8F mod==3 within 6 F pops: {hit}/{tot} = {100.0*hit/tot:.2f} %")
    other = [e for e in led["failures"] if e["family"] != FAMILY]
    oh = 0
    for e in other:
        try:
            cap = capture(e)
        except Exception:                                     # noqa: BLE001
            continue
        pops, _bm = fv.shadow(cap["real"])
        gs = fv.groups_of(pops)
        pre = [g for g in gs if g["f_row"] <= e["first_bad_row"]]
        p, _d, _b = nearest_package(pre[-6:]) if pre else (None, None, None)
        if p == "P4":
            oh += 1
    print(f"CONTROL B -- the OTHER {len(other)} ledger failures at THEIR own "
          f"fork rows, same rule")
    print(f"  8F mod==3 within 6 F pops: {oh}/{len(other)} = "
          f"{100.0*oh/len(other):.2f} %")
    json.dump({"control_a": {"hits": hit, "n": tot, "per_seed": per,
                             "samples": a.samples, "rng_seed": a.seed},
               "control_b": {"hits": oh, "n": len(other)}},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


def cmd_solve(a):
    sv = json.load(open(a.survey))["rows"]
    pick = [s.strip() for s in a.seeds.split(",")] if a.seeds else None
    if pick:
        todo = [r for r in sv if r["seed"] in set(pick)]
    else:
        todo = [r for r in sv
                if r["repro"] and r["arch_match"]
                and r["diverging_rows"] <= a.maxdiv
                and r["chip_addr"] is not None
                and r["chip_addr"] != r["core_addr"]]
    jobs = [(r["seed"], r["first_bad_row"], r["chip_addr"], r["core_addr"],
             r["win"], a.ledger, a.span, a.tb) for r in todo]
    print(f"  freeze instrument: tb={a.tb} "
          f"({'tb_v30_core, one scheduler' if a.tb == 'core' else 'tb_sys / M10-SYS, three schedulers + overlay'})")
    from concurrent.futures import ProcessPoolExecutor
    out = []
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for rec in ex.map(_one_solve, jobs):
            out.append(rec)
            print(f"{rec['seed']:<14} {rec['status']}", flush=True)
            for f in rec.get("freezes", []):
                if f["chip_fits"] or f["core_fits"]:
                    print(f"   d={f['delta']:+d} biu={f['biu_addr']:05x}"
                          f"  CHIP {f['chip_fits']}  CORE {f['core_fits']}")
    json.dump({"n": len(out), "rows": out}, open(a.out, "w"), indent=1)

    # THE CROSS-SEAT INTERSECTION.  One seat's fit is a coincidence; the
    # quantity with teeth is the term that fits EVERY seat at the SAME freeze
    # offset, because the space is ~500 named expressions and 12 simultaneous
    # exact constraints over it either names a term or empties the space.
    ok = [r for r in out if r["status"] == "SOLVED"]
    print(f"\nSOLVED {len(ok)} / {len(out)}")
    for d in range(-a.span, 2):
        sets = []
        for r in ok:
            f = next((x for x in r["freezes"] if x["delta"] == d), None)
            sets.append(set(f["chip_fits"]) if f else set())
        inter = set.intersection(*sets) if sets else set()
        cov = sum(1 for s in sets if s)
        print(f"  freeze d={d:+d}: seats with ANY chip fit {cov}/{len(ok)}"
              f"   intersection {sorted(inter) if inter else 'EMPTY'}")
    # and the per-expression coverage, best-over-freeze, which is what a fix
    # brief needs when no single freeze offset covers every seat
    import collections
    cnt = collections.Counter()
    for r in ok:
        seen = set()
        for f in r["freezes"]:
            seen |= set(f["chip_fits"])
        for e in seen:
            cnt[e] += 1
    print("  best-over-freeze coverage (chip):")
    for e, c in cnt.most_common(15):
        print(f"    {c:>3}/{len(ok)}  {e}")
    print(f"\nwrote {a.out}")


def cmd_report(a):
    """The diagnosis document's tables, GENERATED.  Every number below is read
    out of the three JSON artifacts; nothing here is typed by hand."""
    import artifact as art                                    # noqa: PLC0415
    sv = json.load(open(a.survey))
    rows = sv["rows"]
    out = []
    W = out.append
    led = json.load(open(a.ledger))
    W(f"ledger `{Path(a.ledger).name}`  era sof "
      f"`{led['era']['sof_sha256'][:12]}…`  flash_git `{led['era']['flash_git']}`")
    W(f"TB `{check_seq.tb_bin('ucore')}` receipt "
      f"`{art.receipt_id(check_seq.tb_bin('ucore'))[:16]}…`")
    W("")
    W("| seed | fork | col | div | arch | chip addr | core addr | Δ | "
      "in dispatch | 8F mod3 back | package |")
    W("|---|---:|---|---:|---|---:|---:|---:|---|---:|---|")
    for r in sorted(rows, key=lambda x: (x["near_package"] or "zz", x["seed"])):
        ca = f"`{r['chip_addr']:05x}`" if r["chip_addr"] is not None else ""
        co = f"`{r['core_addr']:05x}`" if r["core_addr"] is not None else ""
        dl = f"`{r['delta']:+d}`" if r.get("delta") is not None else ""
        W(f"| `{r['seed']}` | {r['first_bad_row']} | "
          f"{'+'.join(r['first_cols'])} | {r['diverging_rows']} | "
          f"{'OK' if r['arch_match'] else 'DIFF'} | {ca} | {co} | {dl} | "
          f"`{r['bytes']}` | "
          f"{r['near_dist'] if r['near_dist'] is not None else '—'} | "
          f"{r['near_package'] or '**M10**'} |")
    W("")
    for tag, path in (("P4' cheap subset", a.solve),
                      ("residual M10", a.residual)):
        if not path or not Path(path).exists():
            continue
        d = json.load(open(path))
        W(f"**{tag}** — {sum(1 for x in d['rows'] if x['status'] == 'SOLVED')}"
          f" of {d['n']} scored ("
          f"{sum(1 for x in d['rows'] if x['status'] != 'SOLVED')} NOREPRO)")
        W("")
        W("| seed | chip | core | freeze | chip fits | core fits |")
        W("|---|---:|---:|---:|---|---|")
        for r in d["rows"]:
            if r["status"] != "SOLVED":
                W(f"| `{r['seed']}` | `{r['chip_addr']:05x}` | "
                  f"`{r['core_addr']:05x}` | — | *{r['status']}* | |")
                continue
            best = None
            for f in r["freezes"]:
                if f["chip_fits"]:
                    best = f
                    break
            f = best or (r["freezes"][-1] if r["freezes"] else None)
            cf = ", ".join(f"`{x}`" for x in f["chip_fits"][:4]) if f else ""
            kf = ", ".join(f"`{x}`" for x in f["core_fits"][:4]) if f else ""
            W(f"| `{r['seed']}` | `{r['chip_addr']:05x}` | "
              f"`{r['core_addr']:05x}` | {f['delta'] if f else ''} | "
              f"{cf or '**EMPTY**'} | {kf or '**EMPTY**'} |")
        W("")
    txt = "\n".join(out)
    if a.out:
        Path(a.out).write_text(txt + "\n")
        print(f"wrote {a.out}")
    else:
        print(txt)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey")
    s.add_argument("--ledger", default=str(LEDGER))
    s.add_argument("--out", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                       "fz2_m10_survey.json"))
    s.set_defaults(fn=cmd_survey)
    s = sub.add_parser("solve")
    s.add_argument("--ledger", default=str(LEDGER))
    s.add_argument("--survey", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                           "fz2_m10_survey.json"))
    s.add_argument("--seeds", default=None)
    s.add_argument("--maxdiv", type=int, default=8)
    s.add_argument("--span", type=int, default=12)
    s.add_argument("--tb", choices=("core", "sys"), default="core",
                   help="which harness the freeze runs on.  `core` is "
                        "tb_v30_core (the historical leg, ONE pin-event "
                        "scheduler); `sys` is M10-SYS on tb_sys -- three "
                        "schedulers, the NMI vector overlay and the board's "
                        "own wait sources.  Default `core` so every historical "
                        "invocation still means what it meant.")
    s.add_argument("--jobs", type=int, default=6)
    s.add_argument("--out", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                        "fz2_m10_solve.json"))
    s.set_defaults(fn=cmd_solve)
    s = sub.add_parser("control")
    s.add_argument("--ledger", default=str(LEDGER))
    s.add_argument("--samples", type=int, default=200)
    s.add_argument("--seed", type=int, default=20260810)
    s.add_argument("--out", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                        "fz2_m10_control.json"))
    s.set_defaults(fn=cmd_control)
    s = sub.add_parser("report")
    s.add_argument("--ledger", default=str(LEDGER))
    s.add_argument("--survey", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                           "fz2_m10_survey.json"))
    s.add_argument("--solve", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                          "fz2_m10_solve.json"))
    s.add_argument("--residual", default=str(ROOT / "sw" / "testdata" / "fz2" /
                                             "fz2_m10_solve_residual.json"))
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
