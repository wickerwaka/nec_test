#!/usr/bin/env python3
"""fz2_f14_score -- SCORE THE FLASH #14 CAPTURE AGAINST THE REGISTERED
PREDICTIONS, SEAT BY SEAT.

Registered in `docs/notes/fz2_f14_prereg_2026-08-10.md` §5-§6, amended by
erratum E-1 (`b89f9aa2ea`, the arch column does not gate) and addendum A-1
(`12650eb073`, C-CHIP).

**THE SEAT LISTS BELOW ARE TRANSCRIBED FROM THE PRE-REGISTRATION, WHICH WAS
COMMITTED BEFORE THE FLASH.**  They are not re-derived from the result.  The
whole point of this file is that the verdicts are computed by a rule fixed in
advance, so nothing can be scored by choosing a boundary after seeing where the
seeds landed.

Usage:
    python3 sw/fz2_f14_score.py --new  <derived ledger json>
                               [--ref  <committed ledger json>]
"""
import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED = os.path.join(ROOT, "sw/testdata/fz2/fz2_failure_ledger_2026-08-09.json")


def S(s):
    return s.split()


# ---- the registered seats, verbatim from the pre-registration -------------- #
P1_CLOSE = S("fz2c/407027 fz2c/410078 fz2c/411050 "
             "fz2e/520052 fz2e/521030 fz2e/523057")            # A1 landing, 6
P1B_STAY_LATER = S("fz2c/407065 fz2c/408000 fz2c/409066 fz2c/410073 "
                   "fz2e/518024 fz2e/518065 fz2e/518068 fz2e/519027 "
                   "fz2e/523045 fz2e/523046 fz2e/526025 fz2e/528076")  # +1 each
P1B_STAY = S("fz2e/521075 fz2e/518009 fz2c/407036")
P1B_UNMOVED = S("fz2e/518009")            # must not move at all
P2_CLOSE = S("fz2c/406031 fz2c/408031 fz2c/409016 fz2c/409030 fz2c/410048 "
             "fz2c/410067 fz2c/410076 fz2e/518011 fz2e/518047 fz2e/519058 "
             "fz2e/526032 fz2e/526052 fz2e/526071 fz2e/527040 fz2e/528070 "
             "fz2e/529023 fz2e/531041 fz2e/531057 fz2e/532028 fz2e/532046 "
             "fz2e/534074 fz2e/535054 fz2e/535072")            # F58, 23
P2_STAY = S("fz2c/407064")
P3_CLOSE = S("fz2c/400007 fz2c/400019 fz2c/400022 fz2c/402075 fz2c/408079 "
             "fz2e/521012 fz2e/521054 fz2e/521062 fz2e/522047 fz2e/522051 "
             "fz2e/522075 fz2e/529017")                        # C1, 12
P3B_STAY = S("fz2c/406073 fz2c/407057 fz2c/410053 fz2e/518044 fz2e/521036 "
             "fz2e/522071 fz2e/535042 fz2e/529036 fz2e/518039")
P3C_FROZEN = S("fz2c/406063 fz2c/410047 fz2e/518053 fz2e/535027")
P4_CLOSE = S("fz2e/511030 fz2e/516038")                        # C2, 2
P4B_STAY_LATER = S("fz2e/513019")
P4C_STAY = S("fz2c/405002 fz2c/405013 fz2c/405072 fz2e/512056")
P4D_MUST_NOT_APPEAR = S("fz2c/404040")
P5_CLOSE = S("fz2e/519011 fz2e/519044 fz2e/513052")            # D1, 3
P5B_STAY = S("fz2e/532066 fz2e/531032 fz2e/528069")
P8_ARCH = P3_CLOSE + P4_CLOSE                                  # non-gating, 14

MUST_NOT_EXIT_FAMILIES = (
    "A3 cycle-time slip (non-qs)",
    "B2 HALT entry (one leg only)",
    "C3 NMI(vec2) entry",
    "C4 other-vector delivery",
    "D1 chip fetched, core did not",
    "D2 core fetched, chip did not",
    "D3 both fetched, different address",
    "E1 same-status data cycle, different address",
    "E2 different-status data cycle")

ALL_CLOSERS = P1_CLOSE + P2_CLOSE + P3_CLOSE + P4_CLOSE + P5_CLOSE   # 46

PRIMARY, FLOOR, DENOM = 3685, 3671, 3837
PRED_FAMILY = {                       # §6.1
    "A1 qs-pop one clock late": 17, "A2 qs-pop other offset": 5,
    "A3 cycle-time slip (non-qs)": 15, "B1 HALT-cycle address": 1,
    "B2 HALT entry (one leg only)": 10, "C1 vector-1 trap MISSED by core": 17,
    "C2 INTA-vectored delivery": 10, "C3 NMI(vec2) entry": 1,
    "C4 other-vector delivery": 1, "D1 chip fetched, core did not": 10,
    "D2 core fetched, chip did not": 10,
    "D3 both fetched, different address": 10,
    "E1 same-status data cycle, different address": 41,
    "E2 different-status data cycle": 4}


def verdict(ok):
    return "MET   " if ok else "MISSED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=COMMITTED)
    a = ap.parse_args()
    new = json.load(open(a.new))
    ref = json.load(open(a.ref))
    R = {f["seed"]: f for f in ref["failures"]}
    N = {f["seed"]: f for f in new["failures"]}
    left, came = set(R) - set(N), set(N) - set(R)
    nl = 0

    def head(t):
        print(f"\n=== {t} ===")

    head("HEADLINE, against the registered figures")
    c = new["corpus"]
    print(f"  denominator            {c['denominator']:,}   registered {DENOM:,}"
          f"   {verdict(c['denominator'] == DENOM)}")
    print(f"  SEED MATCH             {c['matched']:,} / {c['denominator']:,} "
          f"= {c['seed_match_pct']} %")
    delta = c["matched"] - PRIMARY
    print(f"    registered PRIMARY   {PRIMARY:,}   "
          + ("HIT" if delta == 0 else f"{delta:+d} vs primary"))
    print(f"    registered FLOOR     {FLOOR:,}   "
          f"{verdict(c['matched'] >= FLOOR)}  (at least 32 of the 46)")
    print(f"  failures               {c['failures']}   registered 152")
    print(f"  ROW MATCH (disc. excl) "
          f"{c['rows_compared'] - c['rows_diverging']:,} / {c['rows_compared']:,}"
          f" = {c['row_match_pct']} %   (was 11,159,527 / 11,322,230 = 98.5630 %)")
    print(f"  LEFT the ledger {len(left)}   ENTERED {len(came)}")

    head("PER-LANDING SEAT CLOSURE, as registered")
    for name, seats, reg in (
            ("P-1  A1  483c1f1270", P1_CLOSE, 6),
            ("P-2  F58 b245334d7c", P2_CLOSE, 23),
            ("P-3  C1  97ca50861c", P3_CLOSE, 12),
            ("P-4  C2  93af2a75cd", P4_CLOSE, 2),
            ("P-5  D1  c64f99e6a9", P5_CLOSE, 3)):
        closed = [s for s in seats if s not in N]
        open_ = [s for s in seats if s in N]
        print(f"  {name}   closed {len(closed)}/{reg}   {verdict(len(closed) == reg)}")
        for s in open_:
            f = N[s]
            print(f"      DID NOT CLOSE  {s}  fam={f['family'][:22]:22s} "
                  f"first {R[s]['first_bad_row']}->{f['first_bad_row']}  "
                  f"rows {R[s]['diverging_rows']}->{f['diverging_rows']}")
        nl += (len(closed) != reg)

    head("SEATS REGISTERED TO STAY (a closure here is an UNREGISTERED gain)")
    for name, seats in (("P-1b A1 downstream +1", P1B_STAY_LATER),
                        ("P-1b A1 other", P1B_STAY),
                        ("P-2  F58 407064", P2_STAY),
                        ("P-3b C1 non-carriers", P3B_STAY),
                        ("P-4b C2 improver", P4B_STAY_LATER),
                        ("P-4c C2a open", P4C_STAY),
                        ("P-5b D1 movers", P5B_STAY)):
        gone = [s for s in seats if s not in N]
        print(f"  {name:24s} stayed {len(seats) - len(gone)}/{len(seats)}   "
              f"{verdict(not gone)}" + (f"   UNREGISTERED EXIT: {gone}" if gone else ""))
        nl += bool(gone)

    head("P-1b DIRECTION: the 12 must move LATER, none EARLIER")
    okd = bad = 0
    for s in P1B_STAY_LATER:
        if s not in N:
            continue
        d = N[s]["first_bad_row"] - R[s]["first_bad_row"]
        if d > 0:
            okd += 1
        if d < 0:
            bad += 1
        print(f"    {s}  {R[s]['first_bad_row']} -> {N[s]['first_bad_row']}  "
              f"({d:+d}){'   <-- EARLIER' if d < 0 else ''}")
    print(f"  moved later {okd}/12, EARLIER {bad}   {verdict(bad == 0)}")
    nl += bool(bad)

    head("P-1b  fz2e/518009 must not move at all")
    for s in P1B_UNMOVED:
        if s in N and s in R:
            same = (N[s]["first_bad_row"] == R[s]["first_bad_row"]
                    and N[s]["diverging_rows"] == R[s]["diverging_rows"])
            print(f"    {s}  first {R[s]['first_bad_row']}->{N[s]['first_bad_row']}"
                  f"  rows {R[s]['diverging_rows']}->{N[s]['diverging_rows']}   "
                  f"{verdict(same)}")
            nl += (not same)
        else:
            print(f"    {s}  CLOSED -- unregistered")
            nl += 1

    head("P-3c  the §64.1 counter-population must not move by one row")
    for s in P3C_FROZEN:
        if s in N and s in R:
            same = (N[s]["first_bad_row"] == R[s]["first_bad_row"]
                    and N[s]["diverging_rows"] == R[s]["diverging_rows"])
            print(f"    {s}  first {R[s]['first_bad_row']}->{N[s]['first_bad_row']}"
                  f"  rows {R[s]['diverging_rows']}->{N[s]['diverging_rows']}   "
                  f"{verdict(same)}")
            nl += (not same)
        else:
            print(f"    {s}  CLOSED -- unregistered")
            nl += 1

    head("P-4d  THE FALSIFIER: fz2c/404040 MUST NOT APPEAR")
    for s in P4D_MUST_NOT_APPEAR:
        print(f"    {s}  {'ABSENT -- ' + verdict(True) if s not in N else 'PRESENT -- FALSIFIER FIRED, the C2 landing form is wrong'}")
        nl += (s in N)

    head("P-6  the 92 seeds in nine untouched families: ZERO exits")
    for fam in MUST_NOT_EXIT_FAMILIES:
        was = [s for s in R if R[s]["family"] == fam]
        gone = [s for s in was if s not in N]
        print(f"    {fam:46s} {len(was) - len(gone):3d}/{len(was):3d}   "
              f"{verdict(not gone)}" + (f"  EXITS {gone}" if gone else ""))
        nl += bool(gone)

    head("P-7  ZERO LOSSES: no matched seed may become a failure")
    print(f"    entered the ledger: {len(came)}   {verdict(not came)}")
    for s in sorted(came):
        f = N[s]
        print(f"      NEW FAILURE  {s}  first_bad {f['first_bad_row']}  "
              f"rows {f['diverging_rows']}  arch {f['arch']}  fam {f['family']}")
    nl += bool(came)

    head("P-8  NON-GATING: arch_match on C1's 12 + C2's 2 (baseline 0/14)")
    conv = [s for s in P8_ARCH if s not in N]   # closed => scored below
    print(f"    of the 14, {len(conv)} left the ledger entirely")
    still = [s for s in P8_ARCH if s in N]
    for s in still:
        print(f"      still failing: {s}  arch {N[s]['arch']}  "
              f"arch_match {N[s].get('arch_match')}")

    head("§6.1  the predicted family table")
    got = new["family_counts"]
    for fam, pred in sorted(PRED_FAMILY.items()):
        g = got.get(fam, 0)
        print(f"    {fam:46s} pred {pred:3d}  got {g:3d}   {verdict(g == pred)}")
        nl += (g != pred)
    extra = {k: v for k, v in got.items() if k not in PRED_FAMILY}
    if extra:
        print(f"    *** UNREGISTERED FAMILIES: {extra} ***")
        nl += 1

    head("§6.5  the §38.9 missed-trap overlay: 40 -> 28 predicted")
    n38 = len(new["overlay_38_9"])
    print(f"    {n38}   {verdict(n38 == 28)}")
    nl += (n38 != 28)

    head("WHICH SEEDS LEFT, BY FAMILY (gain accounting)")
    byfam = collections.Counter(R[s]["family"] for s in left)
    for k, v in sorted(byfam.items()):
        print(f"    {k:46s} {v:3d}")
    unreg = sorted(left - set(ALL_CLOSERS))
    print(f"  registered closers that closed: {len(left & set(ALL_CLOSERS))}/46")
    if unreg:
        print(f"  *** {len(unreg)} UNREGISTERED CLOSURES -- itemized, not folded "
              f"into the headline ***")
        for s in unreg:
            print(f"      {s}  fam {R[s]['family']}  was first "
                  f"{R[s]['first_bad_row']} rows {R[s]['diverging_rows']}")

    print(f"\n=== {nl} registered clause(s) NOT MET ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
