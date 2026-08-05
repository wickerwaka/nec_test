#!/usr/bin/env python3
"""sm3_haltsupp -- THE HALT-ANNOUNCEMENT SUPPRESSION CENSUS (SM3 sitting 17).

A MEASUREMENT tool; it is never a gate.

WHAT IT MEASURES.  A `HLT` whose pin event arrives early enough never puts a
HALT status on the bus at all: the part executes the HALT (the pushed frame
says so) and the ANNOUNCEMENT is cancelled.  The S16 directed display walk
(`sm3_s16_cell.py`, sitting 16) walks the pin-event delay one clock at a time
across the HALT for three forms x six programs x four wait levels, so it
contains the whole boundary, and this reads it out in ONE coordinate:

    arm   the capture row of the CODE T1 at the case's anchor -- the row the
          rig's `ev_st` FSM arms on (`nec_bus.sv`, and `sm3_nmigeom.py`'s
          header derives the +2)
    A     the row the pin goes HIGH on = arm + delay + 2
    H     the row the HALT status appears on, read off a capture of the SAME
          (form, program, wait) at a delay that does announce.  `H` is a
          property of the program and the wait level, not of the delay.

and reports, per (form, wait), the largest `A - arm` that still suppresses.

THE SILICON LEG reads the retained per-clock rows of `sw/testdata/sm3-s16cell/`
-- no model, no core.  THE ENGINE LEG re-derives the same predicate from the
engine's own row stream over the emitted goldens
(`tests/v30/s16-dispwalk-w<w>-p<p>/`), so the two legs are the same question
asked of two engines.

Usage:
    python3 sw/sm3_haltsupp.py chip                 # silicon, from the raw rows
    python3 sw/sm3_haltsupp.py engine [--core ucore|fsm|sim]
"""
import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import sm3_s16_cell as s16                                   # noqa: E402

RAW = ROOT / "sw" / "testdata" / "sm3-s16cell"
CODE, MEMR, HALT = 4, 5, 3
BS_C, T_C, BUS_C = 7, 8, 1
NMI_VEC = 0x00008


# --------------------------------------------------------------------------- #
# the SILICON leg -- retained raw rows only
# --------------------------------------------------------------------------- #
def chip_cell(form, p, w, d):
    f = RAW / f"{form}_p{p}_w{w}_d{d}.rows.json.gz"
    if not f.exists():
        return None
    rows = json.load(gzip.open(f))
    _s, case = s16.gen_case(form, p)
    r = case["regs"]
    anchor = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
    arm = next((i for i, x in enumerate(rows)
                if x["t"] == 1 and x["bs_early"] == CODE
                and (x["ad_addr"] & 0xFFFFF) == anchor), -1)
    if arm < 0:
        return {"form": form, "p": p, "w": w, "d": d, "err": "no arm"}
    A = arm + d + 2
    V = next((i for i in range(arm, len(rows))
              if rows[i]["t"] == 1 and rows[i]["bs_early"] == MEMR
              and (rows[i]["ad_addr"] & 0xFFFFF) == NMI_VEC), -1)
    lim = V if V > 0 else min(len(rows), arm + 120)
    hs = [i for i in range(arm, lim) if rows[i]["bs_early"] == HALT]
    return {"form": form, "p": p, "w": w, "d": d, "arm": arm,
            "Arel": A - arm, "V": V, "gap": (V - A) if V >= 0 else None,
            "Hrel": (hs[0] - arm) if hs else None}


def cmd_chip(a):
    res = [c for form in s16.FORMS for w in s16.WAITS for p in s16.PROGRAMS
           for d in s16.DELAYS
           if (c := chip_cell(form, p, w, d)) is not None]
    print(f"== SILICON, {len(res)} retained captures "
          f"({RAW.relative_to(ROOT)})")
    bad = [c for c in res if c.get("err")]
    if bad:
        print(f"   ERRORS {len(bad)}")
    print("  form      w   H(rel)  max A-rel that SUPPRESSES   H - that   n")
    out = {}
    for form in s16.FORMS:
        for w in s16.WAITS:
            cs = [c for c in res if c["form"] == form and c["w"] == w
                  and not c.get("err")]
            Hs = sorted({c["Hrel"] for c in cs if c["Hrel"] is not None})
            sup = [c["Arel"] for c in cs if c["Hrel"] is None]
            mx = max(sup) if sup else None
            k = (Hs[0] - mx) if (Hs and mx is not None) else None
            out[f"{form}/w{w}"] = {"H": Hs, "maxA": mx, "K": k,
                                   "n_suppressed": len(sup), "n": len(cs)}
            print(f"  {form:9s} {w}   {str(Hs):8s} {str(mx):>6s}"
                  f"                {str(k):>6s}   {len(cs)}")
    print("\n  K = H - (largest suppressing A), in CLOCKS.  A one-valued K per "
          "form, invariant\n  over the wait level, IS the law: the "
          "announcement at H is cancelled iff A <= H - K.")
    for form in s16.FORMS:
        ks = {out[f'{form}/w{w}']["K"] for w in s16.WAITS}
        print(f"    {form:9s} K = {ks}")
    # the vector-read floor on the same population, for the H7 coordinate
    nmi = [c for c in res if c["form"] == "HLT.NMI" and c.get("gap") is not None]
    halted = [c for c in nmi if c["Hrel"] is not None]
    running = [c for c in nmi if c["Hrel"] is None]
    print(f"\n  the NMI vector read on the same cells: from HALT "
          f"{sorted({c['gap'] for c in halted})} ({len(halted)} cells), "
          f"suppressed/running {sorted({c['gap'] for c in running})} "
          f"({len(running)} cells)")
    return 0


# --------------------------------------------------------------------------- #
# the ENGINE leg -- the emitted goldens, the engine's own rows
# --------------------------------------------------------------------------- #
def engine_rows(core, cases, w):
    import check_core as cc
    if core == "sim":
        # RIG DEFECT FIXED, SM3 sitting 18.  `v30sim timed-run` keys its record
        # stream by the case's ARRAY POSITION (`timed_runner.cpp` 658-662); the
        # RTL batch is keyed by the golden's own `idx` (`compose_batch`).  On
        # the S16 suites `idx` is the DELAY, starts at 1..4 and has gaps, so the
        # `sims.get(c["idx"])` below read the WRONG CASE on the model leg -- the
        # model column of `ucore_provenance.md` §78.I was measured through it.
        # Re-key to `idx` here so everything downstream is engine-neutral.
        import timed_gate as tg
        s = tg.run_form(cases, w, False)
        sims = {c["idx"]: s.get(i) for i, c in enumerate(cases)}
    else:
        binp = cc.core_bin(core)
        with tempfile.TemporaryDirectory() as td:
            b, o = Path(td) / "b.txt", Path(td) / "o.txt"
            cc.compose_batch(cases, b)
            rr = subprocess.run([str(binp), f"+batch={b}", f"+out={o}",
                                 f"+waits={w}", "+ce_div=1"],
                                cwd=ROOT, capture_output=True, text=True)
            if rr.returncode != 0 or not o.exists():
                return None
            sims = cc.parse_out(o)
    out = {}
    for c in cases:
        sim = sims.get(c["idx"])
        if sim is None:
            continue
        rows, _e, _i, _j = cc.build_rows_sim(
            sim["recs"], c["initial"]["queue"], n_close=cc.n_fpops(c) - 1)
        out[c["idx"]] = rows
    return out


def cmd_engine(a):
    import check_core as cc
    print(f"== ENGINE ({a.core}) vs GOLDEN, over the S16 suites")
    tot = {}
    band = []
    for form in s16.FORMS:
        for w in s16.WAITS:
            g_sup, e_sup, mismatch = set(), set(), []
            for p in s16.PROGRAMS:
                fn = s16.suite_dir(w, p) / f"{form}.json.gz"
                if not fn.exists():
                    continue
                cases = json.load(gzip.open(fn))
                rows = engine_rows(a.core, cases, w)
                if rows is None:
                    print(f"   ENGINE FAIL {form} w{w} p{p}")
                    continue
                for c in cases:
                    r = rows.get(c["idx"])
                    gh = any(x[BS_C] == "HALT" for x in c["cycles"])
                    if not gh:
                        g_sup.add(c["idx"])
                    if r is not None and not any(x[BS_C] == "HALT" for x in r):
                        e_sup.add(c["idx"])
                    if r is not None and gh != any(x[BS_C] == "HALT"
                                                   for x in r):
                        mm, _ = cc.diff_rows(c["cycles"], r)
                        mismatch.append((w, p, c["idx"], gh,
                                         mm[0] if mm else None))
            tot[f"{form}/w{w}"] = (sorted(g_sup), sorted(e_sup),
                                   len(mismatch))
            band += mismatch
            print(f"  {form:9s} w{w}: golden suppresses d={sorted(g_sup)}   "
                  f"engine suppresses d={sorted(e_sup)}   "
                  f"DISAGREE {len(mismatch)}")
    print(f"\n  cells where the two disagree about the announcement: "
          f"{len(band)}")
    for m in band[:8]:
        print(f"    w{m[0]} p{m[1]} d{m[2]} golden_HALT={m[3]} first={m[4]}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("chip").set_defaults(fn=cmd_chip)
    e = sub.add_parser("engine")
    e.add_argument("--core", default="ucore",
                   choices=("ucore", "fsm", "sim"))
    e.set_defaults(fn=cmd_engine)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
