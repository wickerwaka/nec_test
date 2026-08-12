#!/usr/bin/env python3
"""f19_b2 -- FLASH #19's bar B-2: the fabric x1 column against the offline one.

WHY THIS FILE EXISTS
--------------------
`timing_recovery_results_2026-08-11.md` §5 registered E-1's fabric bar as
*"`x1_fabric baseline` reproducing its offline column with 0 PASS/FAIL
disagreements and 0 differing coordinates"*.  On `fuzz-v2-on-relanding` the
golden-relative form of that comparison is NEARLY VACUOUS, because BOTH legs
regenerate their stimulus from `random.Random("v30-s10-hlt/<form>")` and the
fuzz-v2 image anchor moved: the regenerated case differs from the frozen golden
in exactly one field, `ip`, so every cell fails against the golden on both legs.
(`fz2_flash19_prereg_2026-08-12.md` §3.1 isolates it; `check_core --suite-dir`
is unaffected at 97/97 because it reads the case OUT of the golden file.)

So this file scores the bar in the two forms the pre-registration registers,
and it is committed BEFORE the build and BEFORE any board contact.

    B-2a  cell-level PASS/FAIL + first-divergence-coordinate agreement, both
          legs scored against the same goldens by check_core.diff_rows.
          REPORTED, and DECLARED near-vacuous.  It is the bar's literal form.

    B-2b  ROW FOR ROW.  For each cell, diff_rows(offline_cycles, fabric_cycles)
          must be EMPTY.  Both legs ran the SAME regenerated stimulus, so this
          compares what the board's `nec_bus` registers sampled against what an
          untimed Verilated model says they should have sampled -- which is
          exactly what a false multicycle exception would break.
          THIS IS THE LOAD-BEARING FORM.

NON-VACUITY
-----------
`--null N` perturbs N cells of the offline column in memory before comparing.
A run with `--null` that still reports 0 differing cells is a broken scorer and
the flag exists so that claim can be checked in one command.
"""
import argparse
import copy
import gzip
import json
import random
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core as cc                                       # noqa: E402
import x1_retention as xr                                     # noqa: E402

OUT = ROOT / "sw" / "testdata" / "x1-retention"
META = xr.META


def load(leg):
    """-> {cellkey: cycles}.  Both legs write the same file shape."""
    cells = {}
    for suite, _w, _d in xr.SWEEPS:
        for form in xr.FORMS:
            fn = OUT / f"{suite}.{form}.{leg}.json.gz"
            if not fn.exists():
                continue
            d = json.loads(gzip.decompress(fn.read_bytes()))
            d.pop(META, None)
            for k, t in d.items():
                cells[f"{suite}/{form}/{int(k)}"] = t["cycles"]
    return cells


def golden_map():
    g = {}
    for suite, _w, _d in xr.SWEEPS:
        for form in xr.FORMS:
            for t in xr.golden(suite, form):
                g[f"{suite}/{form}/{t['idx']}"] = t["cycles"]
    return g


def coord(cycles, gold):
    mm, _ = cc.diff_rows(gold, cycles)
    if not mm:
        return True, None
    r, c = mm[0][0], mm[0][1]
    return False, (r, cc.COL_NAME.get(c, str(c)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fab", default="fab_f19", help="the FABRIC leg tag")
    ap.add_argument("--off", default="ret", help="the OFFLINE tb_sys leg tag")
    ap.add_argument("--null", type=int, default=0,
                    help="perturb N offline cells first (non-vacuity check)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    fab, off, gold = load(a.fab), load(a.off), golden_map()
    if not fab:
        sys.exit(f"no fabric column {a.fab} under {OUT}")
    if not off:
        sys.exit(f"no offline column {a.off} under {OUT}")

    nulled = []
    if a.null:
        off = copy.deepcopy(off)
        rng = random.Random(20260812)
        for k in rng.sample(sorted(off), min(a.null, len(off))):
            if off[k]:
                off[k][0] = list(off[k][0])
                off[k][0][1] = (off[k][0][1] ^ 0x1) & 0xFFFFF
                nulled.append(k)

    keys = sorted(set(fab) | set(off))
    only_fab = sorted(set(fab) - set(off))
    only_off = sorted(set(off) - set(fab))

    # ---- B-2a ------------------------------------------------------------ #
    a_agree = a_dis = a_nogold = 0
    a_bad = []
    for k in keys:
        if k not in fab or k not in off or k not in gold:
            a_nogold += 1
            continue
        fp, fc = coord(fab[k], gold[k])
        op, oc = coord(off[k], gold[k])
        if fp == op and fc == oc:
            a_agree += 1
        else:
            a_dis += 1
            a_bad.append((k, (fp, fc), (op, oc)))

    # ---- B-2b ------------------------------------------------------------ #
    b_same = 0
    b_bad = []
    for k in keys:
        if k not in fab or k not in off:
            continue
        mm, _ = cc.diff_rows(off[k], fab[k])
        if not mm:
            b_same += 1
        else:
            r, c = mm[0][0], mm[0][1]
            b_bad.append({"cell": k, "row": r,
                          "col": cc.COL_NAME.get(c, str(c)),
                          "off": mm[0][2], "fab": mm[0][3],
                          "n_diff_rows": len({m[0] for m in mm}),
                          "rows_off": len(off[k]), "rows_fab": len(fab[k])})

    n = len([k for k in keys if k in fab and k in off])
    print(f"=== FLASH #19  B-2   fabric `{a.fab}`  vs  offline `{a.off}`")
    print(f"  cells   fabric {len(fab)} · offline {len(off)} · compared {n}"
          + (f"   ONLY-FAB {len(only_fab)} ONLY-OFF {len(only_off)}"
             if only_fab or only_off else ""))
    if nulled:
        print(f"  NULL    {len(nulled)} offline cells perturbed: "
              + " ".join(nulled[:6]) + (" …" if len(nulled) > 6 else ""))
    print(f"  B-2a    cell PASS/FAIL + coordinate AGREEMENT   "
          f"{a_agree} / {n}   disagreements {a_dis}"
          f"{'   (unscoreable ' + str(a_nogold) + ')' if a_nogold else ''}")
    print("          ^ DECLARED NEAR-VACUOUS under GEN-DRIFT "
          "(prereg §3.1) -- reported, not quoted as the result")
    for k, f, o in a_bad[:20]:
        print(f"            {k}   fab {f}   off {o}")
    print(f"  B-2b    ROW-FOR-ROW identical cells             "
          f"{b_same} / {n}   differing {len(b_bad)}     <-- THE BAR")
    for e in b_bad[:40]:
        print(f"            {e['cell']}  row {e['row']}:{e['col']}  "
              f"off={e['off']} fab={e['fab']}  "
              f"({e['n_diff_rows']} rows; len {e['rows_off']}/{e['rows_fab']})")
    if len(b_bad) > 40:
        print(f"            … {len(b_bad) - 40} more")

    # the INTA class the pre-registration pre-declares
    if b_bad:
        inta = [e for e in b_bad
                if e["row"] < len(gold.get(e["cell"], []))
                and gold[e["cell"]][e["row"]][7] == "INTA"]
        print(f"  of the differing cells, first-divergence row is INTA-status "
              f"in {len(inta)} / {len(b_bad)}  (prereg §3.1's pre-declared "
              f"non-E-1 class)")

    res = {"fab_leg": a.fab, "off_leg": a.off, "compared": n,
           "null_cells": nulled,
           "b2a_agree": a_agree, "b2a_disagree": a_dis,
           "b2a_disagreements": [{"cell": k, "fab": f, "off": o}
                                 for k, f, o in a_bad],
           "b2b_identical": b_same, "b2b_differing": len(b_bad),
           "b2b_detail": b_bad,
           "only_fab": only_fab, "only_off": only_off}
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
        print(f"  -> {a.out}")
    verdict = (a_dis == 0 and not b_bad and not only_fab and not only_off)
    print(f"\nB-2: {'MET' if verdict else 'MISSED'}")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
