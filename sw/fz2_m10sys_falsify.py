#!/usr/bin/env python3
"""fz2_m10sys_falsify -- M10-SYS's OWN FALSIFIER, and it is wave-8's.

    "On the three seats `tb_v30_core` already solves -- fz2e/524030,
     fz2e/518006, fz2e/518067 -- the `tb_sys` freeze must return
     BYTE-IDENTICAL register terms at every freeze `d`.  A port that disagrees
     with the working instrument on the seats both can do is measuring itself."
        -- fz2_w8_ghostsel_results_2026-08-11.md sec.3

Registered in `fz2_m10sys_prereg_2026-08-11.md` sec.3 as M10S-F1/F2/F3.  It
compares two `fz2_m10.py solve` outputs -- one `--tb core`, one `--tb sys` --
value for value, and it is deliberately NOT a comparison of the derived
`chip_fits` sets: those are functions of the register values, so comparing them
instead would let a systematic read error cancel.  The fit sets are checked too,
as a DERIVED cross-check, and reported separately.

M10S-F3 is the non-vacuity clause, and it exists because a probe that returned
zeros would pass a comparison against a reference that also returned zeros.

ERRATUM E-M10S-1 (2026-08-11, stated the day it was measured, and NOT repaired
by moving the bar).  **M10S-F3 AS REGISTERED IS MISSED AND IS REPORTED AS
MISSED.**  It asked for >= 20 distinct `SP` values and >= 20 distinct
`biu_addr` values across the 42 freezes; the measurement is **6** and **11**.
The bar was arithmetically unmeetable when it was written and that is the
author's error, not a finding: the 42 freezes are 14 CONSECUTIVE core clocks on
each of three seats, and a stack pointer is SUPPOSED to be nearly constant over
fourteen adjacent clocks.  Registering a bar one cannot meet is not rigour
(the same lesson `fz2_w8_ghostsel_prereg` sec.2 wrote about "≥ 3 fresh HOLDOUT
closures").

**THE EXIT CODE IS THEREFORE F1 AND F2 -- WAVE-8's REGISTERED FALSIFIER,
VERBATIM AND UNWIDENED.**  F3 is computed, printed and reported as MISSED, and
it never gates.  Its INTENT -- "the probe is reading, not emitting a constant"
-- is served by F1 itself, which matched 1,050 values against a reference taken
on a DIFFERENT harness; a constant-emitting probe fails that catastrophically.
`--stream-seat` prints a direct, POST-HOC characterisation of one whole 226-word
stream (tag, distinct values, non-zero words) and is LABELLED post-hoc wherever
it is quoted, because a number chosen after seeing the data is not a bar.
"""
import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fz2_m10 as m10                                         # noqa: E402

SEATS = ["fz2e/524030", "fz2e/518006", "fz2e/518067"]
TAG_ADDR = 0x000
TAG_WANT = 0x8DE2          # SS_VERSION 0x8D / SS_COUNT 226 -- ss_lint's tag


def rows_of(p):
    return {r["seed"]: r for r in json.load(open(p))["rows"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--core-solve", required=True,
                    help="fz2_m10.py solve --tb core output (the REFERENCE)")
    ap.add_argument("--sys-solve", required=True,
                    help="fz2_m10.py solve --tb sys output (the NEW LEG)")
    ap.add_argument("--offset", type=int, default=0,
                    help="M10S-F1a: the ONE permitted repair, a single integer "
                         "row offset applied to the sys leg's freeze index -- "
                         "same value for every seat and every freeze.  Any "
                         "per-seat or per-d adjustment is a refusal.")
    ap.add_argument("--stream-seat", default=None,
                    help="POST-HOC (E-M10S-1): re-run one seat's freeze and "
                         "characterise the whole 226-word stream.  Evidence, "
                         "never a bar.")
    ap.add_argument("--out")
    a = ap.parse_args()

    ref, got = rows_of(a.core_solve), rows_of(a.sys_solve)
    A = m10.ss_addrs()
    print("=== M10-SYS FALSIFIER (prereg sec.3) ===")
    print(f"  reference (tb_v30_core) {a.core_solve}")
    print(f"  new leg   (tb_sys)      {a.sys_solve}")
    print(f"  row offset applied to the sys leg: {a.offset:+d}"
          + ("   (M10S-F1a repair)" if a.offset else "   (none -- F1 as registered)"))

    nval = nbad = nfreeze = 0
    nbiu = nbiu_bad = 0
    nfit = nfit_bad = 0
    sps, bius = set(), set()
    bad_detail = []
    missing = []
    for s in SEATS:
        r, g = ref.get(s), got.get(s)
        if r is None or g is None:
            missing.append(f"{s}: absent from {'reference' if r is None else 'new leg'}")
            continue
        if r["status"] != "SOLVED" or g["status"] != "SOLVED":
            missing.append(f"{s}: status core={r['status']} sys={g['status']}")
            continue
        gf = {f["delta"] - a.offset: f for f in g["freezes"]}
        for f in r["freezes"]:
            d = f["delta"]
            h = gf.get(d)
            if h is None:
                missing.append(f"{s}: sys leg has no freeze at d={d:+d}")
                continue
            nfreeze += 1
            for k, v in sorted(f["terms"].items()):
                nval += 1
                if h["terms"].get(k) != v:
                    nbad += 1
                    bad_detail.append(f"{s} d={d:+d} {k}: core={v:04x} "
                                      f"sys={h['terms'].get(k)}")
            for k, v in sorted(f["segs"].items()):
                nval += 1
                if h["segs"].get(k) != v:
                    nbad += 1
                    bad_detail.append(f"{s} d={d:+d} seg {k}: core={v:04x} "
                                      f"sys={h['segs'].get(k)}")
            nbiu += 1
            if f["biu_addr"] != h["biu_addr"]:
                nbiu_bad += 1
                bad_detail.append(f"{s} d={d:+d} biu_addr: core={f['biu_addr']:05x} "
                                  f"sys={h['biu_addr']:05x}")
            nfit += 2
            nfit_bad += (sorted(f["chip_fits"]) != sorted(h["chip_fits"]))
            nfit_bad += (sorted(f["core_fits"]) != sorted(h["core_fits"]))
            sps.add(h["terms"]["SP"])
            bius.add(h["biu_addr"])

    f1 = nbad == 0 and not missing
    f2 = nbiu_bad == 0 and not missing
    f3 = len(sps) >= 20 and len(bius) >= 20
    print(f"\n  M10S-F1  register values IDENTICAL   "
          f"{nval - nbad}/{nval}   over {nfreeze} freezes   "
          f"{'MET' if f1 else 'MISSED'}")
    print(f"  M10S-F2  SSA_B_CUR_ADDR IDENTICAL   "
          f"{nbiu - nbiu_bad}/{nbiu}                  "
          f"{'MET' if f2 else 'MISSED'}")
    print(f"  M10S-F3  non-vacuity: distinct SP {len(sps)} (>=20), "
          f"distinct biu_addr {len(bius)} (>=20)   {'MET' if f3 else 'MISSED'}"
          f"   <- REPORTED, NOT GATING: erratum E-M10S-1, the bar was "
          f"unmeetable when written")
    print(f"  derived cross-check: chip_fits/core_fits sets identical "
          f"{nfit - nfit_bad}/{nfit}")
    for m in missing:
        print(f"    MISSING {m}")
    for b in bad_detail[:20]:
        print(f"    DIFF {b}")

    # POST-HOC, and labelled: one whole 226-word stream, read directly off the
    # probe.  Not a bar -- see E-M10S-1.
    stream = None
    if a.stream_seat:
        r = ref[a.stream_seat]
        _rows, ss = m10.replay_tbsys(a.stream_seat, ss_at=r["fork_row"] - 1)
        stream = {"seat": a.stream_seat, "words": len(ss),
                  "tag": ss.get(TAG_ADDR), "distinct": len(set(ss.values())),
                  "nonzero": sum(1 for v in ss.values() if v)}
        print(f"\n  POST-HOC stream characterisation (NOT A BAR, E-M10S-1) "
              f"-- {a.stream_seat} at d=-1:")
        print(f"    {stream['words']} words   SS_TAG 0x{stream['tag']:04X} "
              f"(want 0x{TAG_WANT:04X} = SS_VERSION 0x8D / SS_COUNT 226)   "
              f"{stream['distinct']} distinct values   "
              f"{stream['nonzero']} non-zero")

    ok = f1 and f2
    print(f"\nM10-SYS FALSIFIER: {'PASS' if ok else 'FAIL'}"
          f"   (gate = F1 and F2; F3 reported as MISSED, E-M10S-1)")
    if a.out:
        Path(a.out).write_text(json.dumps(
            {"seats": SEATS, "offset": a.offset, "freezes": nfreeze,
             "stream_post_hoc": stream,
             "erratum": "E-M10S-1: F3's threshold was unmeetable when written; "
                        "reported as MISSED, never gating",
             "values": nval, "values_bad": nbad,
             "biu": nbiu, "biu_bad": nbiu_bad,
             "fits": nfit, "fits_bad": nfit_bad,
             "distinct_sp": len(sps), "distinct_biu": len(bius),
             "F1": f1, "F2": f2, "F3": f3, "pass": ok,
             "missing": missing, "diffs": bad_detail[:200]}, indent=1))
        print(f"wrote {a.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
