#!/usr/bin/env python3
"""fz2_f15_score -- SCORE THE FLASH #15 CAPTURE AGAINST THE REGISTERED
PREDICTIONS, SEAT BY SEAT.

Registered in `docs/notes/fz2_f15_prereg_2026-08-10.md` (`a89951a00c`) §4-§5 and
addendum A-1 (`77838ef777`).

**THE SEAT LISTS BELOW ARE TRANSCRIBED FROM THE PRE-REGISTRATION, WHICH WAS
COMMITTED BEFORE THE FLASH, AND THIS FILE WAS WRITTEN WHILE THE CAPTURE WAS
STILL RUNNING AND BEFORE ITS LEDGER EXISTED.**  They are not re-derived from
the result.  The verdicts are computed by a rule fixed in advance, so nothing
can be scored by choosing a boundary after seeing where the seeds landed.

The reference ledger is FLASH #14's, because that is the era the predictions
were made against.

Usage:
    python3 sw/fz2_f15_score.py --new <derived f15 ledger json>
                               [--ref <f14 ledger json>]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F14 = os.path.join(ROOT, "sw/testdata/fz2/fz2_failure_ledger_f14_2026-08-10.json")


def S(s):
    return s.split()


# ---- P-1: the 29 seats, verbatim from the pre-registration §4.1 ------------ #
P1_SEATS = S("fz2c/408000 fz2c/409066 fz2c/410073 fz2e/518024 fz2e/518065 "
             "fz2e/518068 fz2e/519027 fz2e/523046 fz2e/526025 fz2e/528076")
P2_SEATS_C1 = S("fz2c/407024 fz2c/409062 fz2c/410062 fz2e/507064 fz2e/518046 "
                "fz2e/518072 fz2e/519032 fz2e/530030 fz2e/531000")
P2_SEATS_B2 = S("fz2c/407057 fz2c/410000 fz2c/410053 fz2e/521036 fz2e/522071 "
                "fz2e/529036 fz2e/529055 fz2e/535042")
P2_SEATS_NEW = S("fz2e/517043 fz2e/531009")
P2_SEATS = P2_SEATS_C1 + P2_SEATS_B2 + P2_SEATS_NEW
ALL_SEATS = P1_SEATS + P2_SEATS                                          # 29

# the 12 whose ledger `arch` is OK -- §0.3 / §5.2's FLOOR is built on these
ARCH_OK_SEATS = S("fz2c/408000 fz2c/409066 fz2c/410073 fz2e/518024 "
                  "fz2e/518065 fz2e/518068 fz2e/519027 fz2e/523046 "
                  "fz2e/526025 fz2e/528076 fz2e/529055 fz2e/531000")

# ---- P-2: the five registered movers that must NOT close (§4.2) ------------ #
#   seed -> (predicted first_bad_row, predicted diverging_rows, tolerance)
P2_MOVERS = {
    "fz2c/406073": (1574, 5),
    "fz2e/518044": (2608, 5),
    "fz2c/407064": (1947, 998),
    "fz2c/407065": (3053, 422),
    "fz2e/523045": (3040, 396),
}
# the ONLY seeds permitted a first-divergence DECREASE (§0.4)
EARLIER_ALLOWED = S("fz2c/406073 fz2e/518044 fz2c/407064")
# P-2b: one seed gains a row, first_bad unmoved
P2B_GAINER = "fz2e/518067"

# ---- P-3: the predicted family table (§4.3) ------------------------------- #
PRED_FAMILY = {
    "A1 qs-pop one clock late": 5,
    "A2 qs-pop other offset": 4,
    "A3 cycle-time slip (non-qs)": 15,
    "B1 HALT-cycle address": 1,
    "B2 HALT entry (one leg only)": 2,
    "C1 vector-1 trap MISSED by core": 1,
    "C2 INTA-vectored delivery": 10,
    "C3 NMI(vec2) entry": 1,
    "C4 other-vector delivery": 1,
    "D1 chip fetched, core did not": 10,
    "D2 core fetched, chip did not": 10,
    "D3 both fetched, different address": 10,
    "E1 same-status data cycle, different address": 41,
    "E2 different-status data cycle": 4,
    "NEW/UNCLASSIFIED": 1,
}
PRED_SURVIVORS = {          # the named survivors, so the table can be checked
    "C1 vector-1 trap MISSED by core": S("fz2e/518039"),
    "B2 HALT entry (one leg only)": S("fz2c/406073 fz2e/518044"),
    "A1 qs-pop one clock late": S("fz2c/407065 fz2e/509036 fz2e/513055 "
                                  "fz2e/518009 fz2e/523045"),
    "NEW/UNCLASSIFIED": S("fz2e/532032"),
}

# ---- P-4: the §38.9 missed-trap overlay falls 21 -> 4 (§4.4) --------------- #
PRED_OVERLAY = S("fz2c/406073 fz2c/407064 fz2e/518039 fz2e/518044")

# ---- P-5: the falsifier (§4.5) -------------------------------------------- #
MUST_NOT_APPEAR = S("fz2c/404040")

# ---- P-6: the counter-populations, 36 seeds, zero movement (§4.6) ---------- #
M9 = S("fz2c/404049 fz2c/405025 fz2c/407000 fz2c/407067 fz2c/408068 "
       "fz2c/409077 fz2e/501069 fz2e/510043 fz2e/510048 fz2e/511014 "
       "fz2e/512062 fz2e/513026 fz2e/515047 fz2e/516026 fz2e/516066 "
       "fz2e/520005 fz2e/520013 fz2e/527008 fz2e/527017 fz2e/527065 "
       "fz2e/530017 fz2e/530020 fz2e/531030 fz2e/532000 fz2e/532021 "
       "fz2e/532066 fz2e/534062 fz2e/535004 fz2e/535027")
S641 = S("fz2c/406063 fz2c/410047 fz2e/518053 fz2e/535027")
C2A = S("fz2c/405002 fz2c/405013 fz2c/405072 fz2e/512056")
FROZEN = sorted(set(M9) | set(S641) | set(C2A))                          # 36

# ---- §5: the registered headline ------------------------------------------ #
PRIMARY, FLOOR, DENOM = 3723, 3706, 3839
REF_MATCHED, REF_FAILURES = 3694, 145


def verdict(ok):
    return "MET   " if ok else "MISSED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=F14)
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
          f"= {c['seed_match_pct']} %   (F14 {REF_MATCHED:,} / {DENOM:,})")
    d = c["matched"] - PRIMARY
    print(f"    registered PRIMARY   {PRIMARY:,}   "
          + ("HIT EXACTLY" if d == 0 else f"{d:+d} vs primary"))
    print(f"    registered FLOOR     {FLOOR:,}   {verdict(c['matched'] >= FLOOR)}")
    if c["matched"] < FLOOR:
        miss("headline below the registered FLOOR")
    print(f"  failures               {c['failures']}   registered 116")
    print(f"  ROW MATCH              "
          f"{c['rows_compared'] - c['rows_diverging']:,} / {c['rows_compared']:,}"
          f" = {c['row_match_pct']} %   (F14 98.6673 %, point estimate ~98.92 %)")
    print(f"  LEFT the ledger {len(left)}   ENTERED {len(came)}")

    head("P-1  THE 29 SEATS -- P1's 10 and P2's 19, seed for seed")
    for name, seats, reg in (("P1  19d2fc2b82", P1_SEATS, 10),
                             ("P2  a275b9553c (C1 family)", P2_SEATS_C1, 9),
                             ("P2  a275b9553c (B2 family)", P2_SEATS_B2, 8),
                             ("P2  a275b9553c (NEW/UNCL)", P2_SEATS_NEW, 2)):
        closed = [s for s in seats if s not in N]
        open_ = [s for s in seats if s in N]
        print(f"  {name:28s} closed {len(closed)}/{reg}   "
              f"{verdict(len(closed) == reg)}")
        for s in open_:
            f = N[s]
            print(f"      DID NOT CLOSE  {s}  fam={f['family'][:22]:22s} "
                  f"first {R[s]['first_bad_row']}->{f['first_bad_row']}  "
                  f"rows {R[s]['diverging_rows']}->{f['diverging_rows']}  "
                  f"arch {f['arch']}")
        if len(closed) != reg:
            miss(f"P-1 {name}")
    tot = [s for s in ALL_SEATS if s not in N]
    print(f"  TOTAL closed {len(tot)}/29   {verdict(len(tot) == 29)}")

    head("P-1 FLOOR SPLIT -- the 12 arch=OK seats vs the 17 arch-carrying ones")
    ok_closed = [s for s in ARCH_OK_SEATS if s not in N]
    car = [s for s in ALL_SEATS if s not in ARCH_OK_SEATS]
    car_closed = [s for s in car if s not in N]
    print(f"  arch=OK        closed {len(ok_closed)}/12   "
          f"{verdict(len(ok_closed) == 12)}   (a rows-close IS a ledger exit)")
    print(f"  arch-carrying  closed {len(car_closed)}/17   "
          f"(§0.3: the rows-only instrument cannot predict these)")
    if len(ok_closed) != 12:
        miss("the 12 arch=OK seats")

    head("P-1a  the two seeds that ENTERED at F14 (M3's supposed over-fires)")
    for s in P2_SEATS_NEW:
        print(f"    {s}  {'CLOSED -- M3-as-a-separate-mechanism stays SUPERSEDED' if s not in N else 'STILL FAILING -- P2 5A.2 is REFUTED and M3 re-opens'}")

    head("P-2  THE FIVE REGISTERED MOVERS MUST NOT CLOSE (§4.2)")
    for s, (pf, pr) in P2_MOVERS.items():
        if s not in N:
            print(f"    {s}  CLOSED -- UNREGISTERED, §4.2 said it stays")
            miss(f"P-2 {s} closed")
            continue
        f, r = N[s], R[s]
        df = f["first_bad_row"] - r["first_bad_row"]
        print(f"    {s}  first {r['first_bad_row']} -> {f['first_bad_row']} "
              f"({df:+d}, predicted {pf})   rows {r['diverging_rows']} -> "
              f"{f['diverging_rows']} (predicted ~{pr})   "
              f"{'first_bad EXACT' if f['first_bad_row'] == pf else 'first_bad OFF'}")

    head("P-2b  fz2e/518067 gains one row, first_bad UNMOVED")
    s = P2B_GAINER
    if s in N and s in R:
        print(f"    {s}  first {R[s]['first_bad_row']} -> {N[s]['first_bad_row']}"
              f"  rows {R[s]['diverging_rows']} -> {N[s]['diverging_rows']}")
    else:
        print(f"    {s}  {'CLOSED' if s not in N else 'absent from ref'}")

    head("§0.4  FIRST-DIVERGENCE DECREASES -- allowed on exactly three seeds")
    bad = []
    for s in sorted(set(R) & set(N)):
        d = N[s]["first_bad_row"] - R[s]["first_bad_row"]
        if d < 0 and s not in EARLIER_ALLOWED:
            bad.append((s, R[s]["first_bad_row"], N[s]["first_bad_row"],
                        N[s]["family"]))
    print(f"    unregistered EARLIER moves: {len(bad)}   {verdict(not bad)}")
    for s, o, n, fam in bad:
        print(f"      {s}  {o} -> {n}   fam {fam}")
    if bad:
        miss("unregistered first-divergence decrease")

    head("P-3  THE PREDICTED FAMILY TABLE")
    fams = sorted(set(list(PRED_FAMILY) + [f["family"] for f in new["failures"]]))
    tf = tp = 0
    for fam in fams:
        got = sum(1 for f in new["failures"] if f["family"] == fam)
        pred = PRED_FAMILY.get(fam)
        was = sum(1 for f in ref["failures"] if f["family"] == fam)
        tf += got
        tp += pred or 0
        flag = "" if pred == got else f"   <-- predicted {pred}"
        print(f"    {fam:46s} {was:3d} -> {got:3d}{flag}")
    print(f"    {'TOTAL':46s} {len(R):3d} -> {tf:3d}   predicted {tp}")
    for fam, seats in PRED_SURVIVORS.items():
        got = sorted(f["seed"] for f in new["failures"] if f["family"] == fam)
        print(f"    survivors {fam[:34]:34s} predicted {seats}")
        print(f"    {'':44s} measured  {got}")

    head("P-4  the §38.9 missed-trap overlay: 21 -> predicted 4")
    ov = sorted(set(new.get("overlay_38_9", [])))
    print(f"    measured {len(ov)}   predicted {len(PRED_OVERLAY)}   "
          f"{verdict(sorted(ov) == sorted(PRED_OVERLAY))}")
    print(f"    predicted {sorted(PRED_OVERLAY)}")
    print(f"    measured  {ov}")

    head("P-5  THE FALSIFIER: fz2c/404040 MUST NOT APPEAR")
    for s in MUST_NOT_APPEAR:
        gone = s not in N
        print(f"    {s}  {'ABSENT -- ' + verdict(True) if gone else 'PRESENT -- FALSIFIER FIRED'}")
        if not gone:
            miss("P-5 falsifier fired")

    head("P-6  THE COUNTER-POPULATIONS: 36 seeds, zero movement")
    moved = exits = 0
    for s in FROZEN:
        tag = ("M9" if s in M9 else "") + ("/64.1" if s in S641 else "") + \
              ("/C2a" if s in C2A else "")
        if s not in N:
            print(f"    {s:14s} {tag:12s} EXITED THE LEDGER -- a finding")
            exits += 1
            continue
        same = (N[s]["first_bad_row"] == R[s]["first_bad_row"]
                and N[s]["diverging_rows"] == R[s]["diverging_rows"])
        if not same:
            print(f"    {s:14s} {tag:12s} MOVED  first "
                  f"{R[s]['first_bad_row']}->{N[s]['first_bad_row']}  rows "
                  f"{R[s]['diverging_rows']}->{N[s]['diverging_rows']}")
            moved += 1
    print(f"    exits {exits}   moved {moved}   of {len(FROZEN)}   "
          f"{verdict(exits == 0 and moved == 0)}")
    if exits:
        miss("P-6 counter-population exit")
    if moved:
        miss("P-6 counter-population movement")

    head("P-7  ZERO LOSSES: no matched seed may become a failure")
    print(f"    entered the ledger: {len(came)}   {verdict(not came)}")
    for s in sorted(came):
        f = N[s]
        print(f"      NEW FAILURE  {s}  first_bad {f['first_bad_row']}  "
              f"rows {f['diverging_rows']}  arch {f['arch']}  fam {f['family']}"
              f"  tier {f.get('tier')}")
    if came:
        miss("P-7 new failures")

    head("P-8  NO UNREGISTERED CLOSURE -- exits are EXACTLY the 29")
    unreg = sorted(left - set(ALL_SEATS))
    print(f"    exits {len(left)}   registered 29   unregistered {len(unreg)}   "
          f"{verdict(not unreg)}")
    for s in unreg:
        f = R[s]
        print(f"      UNREGISTERED CLOSURE  {s}  fam {f['family']}  "
              f"was first {f['first_bad_row']} rows {f['diverging_rows']}")
    if unreg:
        miss("P-8 unregistered closure (an fz2_replay instrument finding)")

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
