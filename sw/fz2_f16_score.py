#!/usr/bin/env python3
"""fz2_f16_score -- SCORE THE FLASH #16 CAPTURE AGAINST THE REGISTERED
PREDICTIONS, SEAT BY SEAT.

Registered in `docs/notes/fz2_f16_prereg_2026-08-10.md` §4-§5.

**THE SEAT LISTS BELOW ARE TRANSCRIBED FROM THE PRE-REGISTRATION, WHICH WAS
COMMITTED BEFORE THE FLASH, AND THIS FILE WAS WRITTEN WHILE THE RETENTION BUILD
WAS STILL RUNNING AND BEFORE THE F16 LEDGER EXISTED.**  They are not re-derived
from the result.  The verdicts are computed by a rule fixed in advance, so
nothing can be scored by choosing a boundary after seeing where the seeds
landed.

The reference ledger is FLASH #15's, because that is the era the predictions
were made against.

Usage:
    python3 sw/fz2_f16_score.py --new <derived f16 ledger json>
                               [--ref <f15 ledger json>]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F15 = os.path.join(ROOT, "sw/testdata/fz2/fz2_failure_ledger_f15_2026-08-10.json")


def S(s):
    return s.split()


# ---- P-1: the two seats that CLOSE (§4.1) --------------------------------- #
CLOSERS = S("fz2c/406023 fz2e/527051")
CLEAN_CLOSER = "fz2c/406023"     # arch OK
CHIP_MOVER = "fz2e/527051"       # the sitting's principal uncertainty (§4.1a)

# ---- P-2: the four D3 stall (a) seats -- stay failing, rows may move ------- #
#   seed -> faithful-replay predicted diverging_rows (informational)
A_SEATS = {
    "fz2e/520062": 2965,
    "fz2e/528008": 3196,
    "fz2e/532012": 4,
    "fz2e/533028": 12,
}

# ---- P-3: the frozen counter-populations (§4.3) --------------------------- #
OTHER_D3 = S("fz2c/407036 fz2e/520013 fz2e/521016 fz2e/527008")
S641 = S("fz2c/406063 fz2c/410047 fz2e/518053 fz2e/535027")
C2A = S("fz2c/405002 fz2c/405013 fz2c/405072 fz2e/512056")
M9 = S("fz2c/404049 fz2c/405025 fz2c/407000 fz2c/407067 fz2c/408068 "
       "fz2c/409077 fz2e/501069 fz2e/510043 fz2e/510048 fz2e/511014 "
       "fz2e/512062 fz2e/513026 fz2e/515047 fz2e/516026 fz2e/516066 "
       "fz2e/520005 fz2e/520013 fz2e/527008 fz2e/527017 fz2e/527065 "
       "fz2e/530017 fz2e/530020 fz2e/531030 fz2e/532000 fz2e/532021 "
       "fz2e/532066 fz2e/534062 fz2e/535004 fz2e/535027")
# the D3-stall (a) seats are DISTURBED by construction and are excluded from the
# frozen set; everything else in the ledger except the two closers is frozen.
FROZEN = sorted(set(OTHER_D3) | set(S641) | set(C2A) | set(M9))

# ---- P-4: the falsifier (§4.4) -------------------------------------------- #
MUST_NOT_APPEAR = S("fz2c/404040")

# ---- §5: the registered headline ------------------------------------------ #
PRIMARY, FLOOR, DENOM = 3724, 3723, 3838
REF_MATCHED, REF_FAILURES = 3722, 116


def verdict(ok):
    return "MET   " if ok else "MISSED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=F15)
    a = ap.parse_args()
    new = json.load(open(a.new))
    ref = json.load(open(a.ref))
    R = {f["seed"]: f for f in ref["failures"]}
    N = {f["seed"]: f for f in new["failures"]}
    left, came = set(R) - set(N), set(N) - set(R)
    misses = []

    def head(t):
        print(f"\n=== {t} ===")

    def miss(tag):
        misses.append(tag)

    head("HEADLINE, against the registered figures")
    c = new["corpus"]
    print(f"  denominator            {c['denominator']:,}   registered {DENOM:,}"
          f"   {verdict(c['denominator'] == DENOM)}")
    if c["denominator"] != DENOM:
        print("     ^ G-6 discard re-roll -- A-12/A-13's process: itemize, "
              "report BOTH bases, not a ratchet violation")
    print(f"  SEED MATCH             {c['matched']:,} / {c['denominator']:,} "
          f"= {c['seed_match_pct']} %   (F15 {REF_MATCHED:,} / {DENOM:,})")
    d = c["matched"] - PRIMARY
    print(f"    registered PRIMARY   {PRIMARY:,}   "
          + ("HIT EXACTLY" if d == 0 else f"{d:+d} vs primary"))
    print(f"    registered FLOOR     {FLOOR:,}   {verdict(c['matched'] >= FLOOR)}")
    if c["matched"] < FLOOR:
        miss("headline below the registered FLOOR")
    print(f"  failures               {c['failures']}   registered 114")
    print(f"  ROW MATCH              "
          f"{c['rows_compared'] - c['rows_diverging']:,} / {c['rows_compared']:,}"
          f" = {c['row_match_pct']} %   (F15 98.9216 %)")
    print(f"  LEFT the ledger {len(left)}   ENTERED {len(came)}")

    head("P-1  THE TWO SEATS CLOSE, seed for seed (§4.1)")
    for s in CLOSERS:
        closed = s not in N
        tag = "(arch OK, clean closer)" if s == CLEAN_CLOSER else \
              "(chip mover under test -- §4.1a)"
        if closed:
            print(f"    {s}  CLOSED  {tag}   {verdict(True)}")
        else:
            f = N[s]
            print(f"    {s}  DID NOT CLOSE  {tag}  first "
                  f"{R[s]['first_bad_row']}->{f['first_bad_row']}  rows "
                  f"{R[s]['diverging_rows']}->{f['diverging_rows']}  arch {f['arch']}")
    both = all(s not in N for s in CLOSERS)
    clean = CLEAN_CLOSER not in N
    chip = CHIP_MOVER not in N
    print(f"  closed {sum(s not in N for s in CLOSERS)}/2   "
          f"{verdict(both)}")
    if not clean:
        miss("P-1 the arch=OK clean closer fz2c/406023 did NOT close")
    if not chip:
        print("    NOTE: fz2e/527051 did not close -- FIDELITY FINDING per "
              "§4.1a/§5.2, NOT a miss of the sitting; the faithful replay "
              "disagreed with silicon on the seat that carries the wave")

    head("P-2  THE FOUR D3 STALL (a) SEATS STAY FAILING; rows may move (§4.2)")
    for s, rep in A_SEATS.items():
        if s not in N:
            print(f"    {s}  EXITED THE LEDGER -- a finding (§4.2)")
            miss(f"P-2 (a) seat {s} exited")
            continue
        f = N[s]
        moved = f["diverging_rows"] != R[s]["diverging_rows"]
        print(f"    {s}  STILL FAILING  first "
              f"{R[s]['first_bad_row']}->{f['first_bad_row']}  rows "
              f"{R[s]['diverging_rows']}->{f['diverging_rows']}"
              f" (faithful-replay ~{rep})   {'ROWS MOVED' if moved else 'unmoved'}")

    head("P-3  THE FROZEN COUNTER-POPULATIONS: zero exits, first_bad UNCHANGED")
    exits = fbmoved = rowmoved = 0
    for s in FROZEN:
        tag = ("D3o" if s in OTHER_D3 else "") + ("/64.1" if s in S641 else "") \
              + ("/C2a" if s in C2A else "") + ("/M9" if s in M9 else "")
        if s not in R:
            print(f"    {s:14s} {tag:14s} NOT IN F15 LEDGER -- skipped")
            continue
        if s not in N:
            print(f"    {s:14s} {tag:14s} EXITED THE LEDGER -- a finding")
            exits += 1
            continue
        dfb = N[s]["first_bad_row"] != R[s]["first_bad_row"]
        dr = N[s]["diverging_rows"] != R[s]["diverging_rows"]
        if dfb:
            print(f"    {s:14s} {tag:14s} first_bad MOVED "
                  f"{R[s]['first_bad_row']}->{N[s]['first_bad_row']} -- a finding")
            fbmoved += 1
        elif dr:
            print(f"    {s:14s} {tag:14s} rows {R[s]['diverging_rows']}->"
                  f"{N[s]['diverging_rows']} (downstream noise, reported)")
            rowmoved += 1
    print(f"    exits {exits}   first_bad moved {fbmoved}   rows moved (noise) "
          f"{rowmoved}   of {len(FROZEN)}   {verdict(exits == 0 and fbmoved == 0)}")
    if exits:
        miss("P-3 frozen counter-population exit")
    if fbmoved:
        miss("P-3 frozen counter-population first_bad moved")

    head("P-4  THE FALSIFIER: fz2c/404040 MUST NOT APPEAR (§4.4)")
    for s in MUST_NOT_APPEAR:
        gone = s not in N
        print(f"    {s}  {'ABSENT -- ' + verdict(True) if gone else 'PRESENT -- FALSIFIER FIRED'}")
        if not gone:
            miss("P-4 falsifier fired")

    head("P-5  ZERO LOSSES: no matched seed may become a failure (§4.5)")
    print(f"    entered the ledger: {len(came)}   {verdict(not came)}")
    for s in sorted(came):
        f = N[s]
        print(f"      NEW FAILURE  {s}  first_bad {f['first_bad_row']}  "
              f"rows {f['diverging_rows']}  arch {f['arch']}  fam {f['family']}"
              f"  tier {f.get('tier')}")
    if came:
        miss("P-5 new failures")

    head("P-6  NO UNREGISTERED CLOSURE -- exits are EXACTLY the two (§4.6)")
    unreg = sorted(left - set(CLOSERS))
    print(f"    exits {len(left)}   registered 2   unregistered {len(unreg)}   "
          f"{verdict(not unreg)}")
    for s in unreg:
        f = R[s]
        print(f"      UNREGISTERED CLOSURE  {s}  fam {f['family']}  "
              f"was first {f['first_bad_row']} rows {f['diverging_rows']}")
    if unreg:
        miss("P-6 unregistered closure (a faithful-replay instrument finding)")

    head("P-7  NO UNREGISTERED FIRST-DIVERGENCE DECREASE (§4.7)")
    bad = []
    for s in sorted(set(R) & set(N)):
        dd = N[s]["first_bad_row"] - R[s]["first_bad_row"]
        if dd < 0:
            bad.append((s, R[s]["first_bad_row"], N[s]["first_bad_row"],
                        N[s]["family"]))
    print(f"    first-divergence DECREASES on still-failing seeds: {len(bad)}   "
          f"{verdict(not bad)}")
    for s, o, n, fam in bad:
        print(f"      {s}  {o} -> {n}   fam {fam}")
    if bad:
        miss("P-7 unregistered first-divergence decrease")

    head("P-8  THE FAMILY TABLE: only D3 moves, 10 -> 8 (§4.8)")
    fams = sorted(set([f["family"] for f in ref["failures"]]
                      + [f["family"] for f in new["failures"]]))
    for fam in fams:
        was = sum(1 for f in ref["failures"] if f["family"] == fam)
        got = sum(1 for f in new["failures"] if f["family"] == fam)
        flag = ""
        if fam.startswith("D3"):
            flag = f"   <-- predicted 8   {verdict(got == 8)}"
            if got != 8:
                miss("P-8 D3 != 8")
        elif was != got:
            flag = "   <-- UNEXPECTED MOVE"
            miss(f"P-8 unexpected family move: {fam}")
        print(f"    {fam:46s} {was:3d} -> {got:3d}{flag}")
    print(f"    {'TOTAL':46s} {len(R):3d} -> {len(N):3d}   predicted 114")

    head("SUMMARY")
    if misses:
        print(f"  {len(misses)} registered clause(s) MISSED, reported as registered:")
        for m in misses:
            print(f"    - {m}")
    else:
        print("  every registered clause MET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
