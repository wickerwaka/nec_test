#!/usr/bin/env python3
"""fz2_f17_score -- SCORE THE FLASH #17 CAPTURE AGAINST THE REGISTERED
PREDICTIONS, SEAT BY SEAT.

Registered in `docs/notes/fz2_flash17_prereg_2026-08-11.md` §4, committed at
`b1630239cc` **BEFORE any Quartus build and BEFORE any board contact**.

**THIS FILE WAS WRITTEN WHILE THE CONTROL BUILD WAS STILL RUNNING, BEFORE THE
BOARD WAS FLASHED AND BEFORE THE F17 LEDGER EXISTED.**  Every list below is
transcribed from that document; nothing is re-derived from the result, and the
verdict rules are fixed here in advance so no boundary can be chosen after
seeing where the seeds landed.

The reference ledger is FLASH #16's, because that is the era the predictions
were made against.

⚠ TWO THINGS THIS SCORER DOES THAT THE F16 ONE DID NOT, AND WHY:

  1. **The headline is a BAND, not a floor.**  The socket-capture noise floor
     is 10/3,840 and wave 4's whole predicted effect is 8 seats, so the band is
     1.25x the effect.  §4.2 registers it as a CONTAINMENT CHECK and registers
     that a result INSIDE it is NOT evidence for wave 4.  This file prints that
     sentence with the number so the two cannot be quoted apart.

  2. **It does NOT register "no first-divergence decrease".**  The
     ghost-address landing's W-4 bar asked exactly that and was REFUTED at 19
     seeds.  Those 19 are NAMED here (from the pre-registration's Appendix A)
     and the bar is on everything else.  Re-registering a bar already known to
     fail would be dishonest.

Usage:
    python3 sw/fz2_f17_score.py --new <derived f17 ledger json>
                               [--ref <f16 ledger json>]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F16 = os.path.join(ROOT, "sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json")


def S(s):
    return s.split()


# --------------------------------------------------------------------------- #
# P-1 -- THE EIGHT SEATS THAT CLOSE (prereg §4.1).  seed -> (mechanism, F16
# diverging_rows, signal strength).  "low" is §4.1b: a 4-row seat's closure is
# weaker evidence than a 2,966-row seat's, and the report says so.
# --------------------------------------------------------------------------- #
CLOSERS = {
    "fz2e/519016": ("ghost ADDRESS", 2, "low"),
    "fz2e/520040": ("ghost ADDRESS", 4, "low"),
    "fz2e/520062": ("P5'-stall", 2966, "high"),
    "fz2e/528008": ("P5'-stall", 3197, "high"),
    "fz2e/532012": ("P5'-stall", 4, "low"),
    "fz2e/533028": ("P5'-stall", 12, "low"),
    "fz2e/527055": ("P4'-space", 4, "low"),
    "fz2e/528030": ("P4'-space", 9, "low"),
}

# --------------------------------------------------------------------------- #
# P-8 -- the three seats the wave itself booked as NOT closing (prereg §4.8).
# seed -> (landing, predicted diverging_rows, predicted first_bad_row)
# --------------------------------------------------------------------------- #
BOOKED_NOT_CLOSING = {
    "fz2e/520066": ("B P4'-space  LATCHED r_cmt_bs", 8, 1249),
    "fz2c/410028": ("B P4'-space  re-forks on a qs cell", 426, 3004),
    "fz2c/410008": ("ghost ADDRESS  ghost row fixed, seed not", 4, 1198),
}

# --------------------------------------------------------------------------- #
# P-6 -- the 19 still-failing seeds registered IN ADVANCE to move EARLIER
# (prereg Appendix A, bold rows).  These are the ONLY seeds exempt from the
# no-first-divergence-decrease bar.
# --------------------------------------------------------------------------- #
EARLIER_OK = S("fz2c/406063 fz2c/408068 fz2c/409065 fz2e/518039 fz2e/518053 "
               "fz2e/520000 fz2e/520005 fz2e/521016 fz2e/521049 fz2e/525017 "
               "fz2e/526054 fz2e/527008 fz2e/530017 fz2e/530020 fz2e/530046 "
               "fz2e/530070 fz2e/532000 fz2e/534062 fz2e/535004")

# --------------------------------------------------------------------------- #
# Appendix A -- the 43 predicted movers.  seed -> (predicted rows, predicted
# first_bad_row).  Rows are REPORTED, NOT BARRED.
# --------------------------------------------------------------------------- #
MOVERS = {
    "fz2c/404049": (1636, 221),   "fz2c/404071": (905, 244),
    "fz2c/405025": (1090, 215),   "fz2c/406063": (3149, 245),
    "fz2c/407064": (998, 1947),   "fz2c/407065": (422, 3053),
    "fz2c/408019": (1086, 1617),  "fz2c/408068": (405, 426),
    "fz2c/409065": (16, 1534),    "fz2c/410008": (4, 1198),
    "fz2c/410028": (426, 3004),   "fz2e/501069": (1959, 1547),
    "fz2e/509036": (783, 562),    "fz2e/510043": (2238, 971),
    "fz2e/514044": (1261, 235),   "fz2e/514072": (936, 326),
    "fz2e/515047": (952, 410),    "fz2e/516001": (1154, 584),
    "fz2e/516066": (387, 1811),   "fz2e/518039": (1587, 2363),
    "fz2e/518050": (2560, 748),   "fz2e/518053": (3413, 567),
    "fz2e/520000": (836, 502),    "fz2e/520005": (2870, 484),
    "fz2e/521016": (16, 352),     "fz2e/521049": (14, 2150),
    "fz2e/522003": (403, 3164),   "fz2e/522029": (32, 785),
    "fz2e/523045": (396, 3040),   "fz2e/524030": (2610, 352),
    "fz2e/525017": (12, 1141),    "fz2e/526054": (320, 265),
    "fz2e/527008": (2183, 929),   "fz2e/530017": (1670, 1440),
    "fz2e/530020": (671, 296),    "fz2e/530046": (2084, 1345),
    "fz2e/530070": (1753, 2225),  "fz2e/531030": (342, 3218),
    "fz2e/532000": (3001, 426),   "fz2e/533025": (1041, 1678),
    "fz2e/534062": (1271, 1271),  "fz2e/535004": (807, 1131),
    "fz2e/535036": (4, 1716),
}

# the two registered ROW COSTS, named in advance so they are not hidden in a net
REGISTERED_ROW_COSTS = S("fz2e/518039 fz2e/526054")

# ---- P-5: the falsifier (prereg §4.5) ------------------------------------- #
MUST_NOT_APPEAR = S("fz2c/404040")

# ---- §4.2: the registered headline ---------------------------------------- #
PRIMARY_FAILURES = 108
BAND_LO, BAND_HI = 98, 118          # 108 +/- the measured floor of 10/3,840
DENOM = 3838
NOISE_BUDGET = 10                   # total unregistered membership flips
PRED_ROW_SUM = 118662               # sum of diverging_rows over the F16 116
REF_MATCHED, REF_FAILURES, REF_ROW_SUM = 3722, 116, 123084

# ---- §4.7: the registered family table ------------------------------------ #
FAMILY_PRED = {
    "D3 both fetched, different address": (8, 4),
    "E1 same-status data cycle, different address": (41, 39),
    "E2 different-status data cycle": (4, 2),
}

# ---- §4.3: the attribution dichotomy, stated so it cannot be softened ------ #
ATTRIB = ("A new/unregistered flip is attributed to WAVE 4 -- a landing-level "
          "finding -- if it carries a `MOV CS,rm` (8E /1) at a retarget "
          "boundary, an `8F` with mod==3 within six F pops of its fork row, or "
          "a fork on an I/O-vs-memory status cell.  Calling it NOISE requires "
          "POSITIVE evidence: the CORE leg unchanged and/or the terminator's "
          "`fired` count moved.  \"Not obviously wave 4\" is NOT an attribution.")


def verdict(ok):
    return "MET   " if ok else "MISSED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=F16)
    a = ap.parse_args()
    new = json.load(open(a.new))
    ref = json.load(open(a.ref))
    R = {f["seed"]: f for f in ref["failures"]}
    N = {f["seed"]: f for f in new["failures"]}
    left, came = set(R) - set(N), set(N) - set(R)
    misses, findings = [], []

    def head(t):
        print(f"\n=== {t} ===")

    def miss(tag):
        misses.append(tag)

    def finding(tag):
        findings.append(tag)

    print("fz2_f17_score -- prereg docs/notes/fz2_flash17_prereg_2026-08-11.md "
          "(committed b1630239cc, before build and before board contact)")
    print(f"  reference ledger  {os.path.relpath(a.ref, ROOT)}")
    print(f"  scored ledger     {os.path.relpath(a.new, ROOT)}")
    print(f"  ref era .sof      {ref['era']['sof_sha256'][:16]}...")
    print(f"  new era .sof      {new['era']['sof_sha256'][:16]}...")

    # ---------------------------------------------------------------- P-1 --- #
    head("P-1  THE EIGHT SEATS CLOSE, SEED BY SEAT (§4.1) "
         "-- THIS IS THE SITTING'S CLAIM")
    closed_hi = closed_lo = 0
    for s, (mech, was, sig) in CLOSERS.items():
        if s not in N:
            print(f"    {s:14s} {mech:16s} rows {was:5d} -> 0   CLOSED   "
                  f"[{sig} signal]   {verdict(True)}")
            if sig == "high":
                closed_hi += 1
            else:
                closed_lo += 1
        else:
            f = N[s]
            print(f"    {s:14s} {mech:16s} rows {was:5d} -> {f['diverging_rows']:5d}"
                  f"   DID NOT CLOSE   first {R[s]['first_bad_row']}->"
                  f"{f['first_bad_row']}  fam {f['family']}   {verdict(False)}")
            miss(f"P-1 seat {s} ({mech}) did not close")
    n = closed_hi + closed_lo
    print(f"  closed {n}/8   (high-signal {closed_hi}/2, low-signal {closed_lo}/6)"
          f"   {verdict(n == 8)}")
    print("  §4.1b: the two HIGH-signal seats (fz2e/520062 2,966 rows and "
          "fz2e/528008 3,197 rows) carry more\n"
          "         evidence than the six that close from 2-12 rows, and this "
          "report does not count all eight equally.")

    # ---------------------------------------------------------------- P-2 --- #
    head("P-2  THE HEADLINE, AGAINST THE BAND REGISTERED BEFORE CAPTURE (§4.2)")
    c = new["corpus"]
    print(f"  denominator            {c['denominator']:,}   registered {DENOM:,}"
          f"   {verdict(c['denominator'] == DENOM)}")
    if c["denominator"] != DENOM:
        print("     ^ G-6 discard re-roll -- A-12/A-13: itemise seed by seed, "
              "report BOTH bases, NOT a ratchet violation")
    print(f"  failures               {c['failures']}   "
          f"registered PRIMARY {PRIMARY_FAILURES}   "
          f"({c['failures'] - PRIMARY_FAILURES:+d})")
    inband = BAND_LO <= c["failures"] <= BAND_HI
    print(f"  registered BAND        {BAND_LO} <= failures <= {BAND_HI}"
          f"   ({PRIMARY_FAILURES} +/- 10, the measured socket-capture floor)"
          f"   {verdict(inband)}")
    if not inband:
        miss("P-2 headline outside the registered band")
        finding("headline outside the band -- investigate")
    print("  ⚠ §4.2: THE BAND IS 1.25x THE EFFECT.  A RESULT INSIDE IT SAYS "
          "NOTHING ABOUT WAVE 4 AND IS\n"
          "    NOT QUOTED AS CONFIRMING IT.  The evidence is P-1, seat by seat, "
          "and nothing else.")
    print(f"  SEED MATCH             {c['matched']:,} / {c['denominator']:,} "
          f"= {c['seed_match_pct']} %   (F16 {REF_MATCHED:,} / {DENOM:,} "
          f"= 96.9776 %)")
    print(f"  ROW MATCH              "
          f"{c['rows_compared'] - c['rows_diverging']:,} / {c['rows_compared']:,}"
          f" = {c['row_match_pct']} %   (F16 98.9139 %)")
    print(f"  LEFT the ledger {len(left)}   ENTERED {len(came)}")

    head("P-2a  THE ROW METRIC, AND ITS TWO REGISTERED COSTS (§4.2a)")
    common = set(R) & set(N)
    s_ref = sum(R[s]["diverging_rows"] for s in R)
    s_new = sum(N[s]["diverging_rows"] for s in N)
    print(f"  Sum diverging_rows over each era's own ledger: {s_ref:,} -> "
          f"{s_new:,} ({s_new - s_ref:+,})   predicted point {PRED_ROW_SUM:,}")
    for s in REGISTERED_ROW_COSTS:
        if s in N and s in R:
            print(f"    registered COST  {s:14s} {R[s]['diverging_rows']:5d} -> "
                  f"{N[s]['diverging_rows']:5d}   (predicted "
                  f"{MOVERS[s][0]})  -- W-2 named this seat IN ADVANCE as one "
                  f"the AND does not govern")
        else:
            print(f"    registered COST  {s:14s} NOT IN BOTH LEDGERS -- reported")

    # ---------------------------------------------------------------- P-3 --- #
    head("P-3  ZERO LOSSES, ON A BUDGET (§4.3)")
    print(f"    entered the ledger: {len(came)}   noise budget (shared with "
          f"P-4): {NOISE_BUDGET}")
    for s in sorted(came):
        f = N[s]
        print(f"      NEW FAILURE  {s}  first_bad {f['first_bad_row']}  "
              f"rows {f['diverging_rows']}  arch {f['arch']}  "
              f"fam {f['family']}  tier {f.get('tier')}  "
              f"verdict {f.get('banked_verdict')}/{f.get('banked_sub')}")
    if came:
        print("    ATTRIBUTION IS OWED ON EVERY ONE OF THESE, AND IT IS A "
              "DICHOTOMY:")
        for ln in ATTRIB.split(".  "):
            print(f"      {ln.strip()}.")

    # ---------------------------------------------------------------- P-4 --- #
    head("P-4  NO UNREGISTERED CLOSURE -- exits are EXACTLY the eight (§4.4)")
    unreg = sorted(left - set(CLOSERS))
    print(f"    exits {len(left)}   registered 8   unregistered {len(unreg)}   "
          f"{verdict(not unreg)}")
    for s in unreg:
        f = R[s]
        print(f"      UNREGISTERED CLOSURE  {s}  fam {f['family']}  "
              f"was first {f['first_bad_row']} rows {f['diverging_rows']}")
    flips = len(unreg) + len(came)
    print(f"    TOTAL UNREGISTERED MEMBERSHIP FLIPS (entries + unregistered "
          f"exits) = {flips}   budget {NOISE_BUDGET}   {verdict(flips <= NOISE_BUDGET)}")
    if flips > NOISE_BUDGET:
        miss("P-3/P-4 unregistered membership flips exceed the noise budget")
        finding(f"{flips} unregistered flips vs a floor of {NOISE_BUDGET}")

    # ---------------------------------------------------------------- P-5 --- #
    head("P-5  THE FALSIFIER: fz2c/404040 MUST NOT APPEAR (§4.5)")
    for s in MUST_NOT_APPEAR:
        gone = s not in N
        print(f"    {s}  " + ("ABSENT -- " + verdict(True) if gone
                              else "PRESENT -- FALSIFIER FIRED, "
                                   "LANDING-LEVEL FINDING"))
        if not gone:
            miss("P-5 falsifier fired")
            finding("fz2c/404040 present -- wave 4 broke a mechanism nobody claimed")

    # ---------------------------------------------------------------- P-6 --- #
    head("P-6  FIRST-DIVERGENCE: the 19 registered earlier-movers are EXEMPT; "
         "no OTHER seed may decrease (§4.6)")
    exp_hit, unexp = [], []
    for s in sorted(common):
        o, nn = R[s]["first_bad_row"], N[s]["first_bad_row"]
        if o is None or nn is None or nn >= o:
            continue
        (exp_hit if s in EARLIER_OK else unexp).append((s, o, nn, N[s]["family"]))
    print(f"    registered earlier-movers that moved earlier: "
          f"{len(exp_hit)} of {len(EARLIER_OK)} named")
    for s, o, nn, fam in exp_hit:
        pred = MOVERS.get(s, (None, None))[1]
        print(f"      {s:14s} {o:5d} -> {nn:5d}   (predicted {pred})   {fam}")
    silent = [s for s in EARLIER_OK if s in common
              and not any(x[0] == s for x in exp_hit)]
    for s in silent:
        print(f"      {s:14s} did NOT move earlier -- reported, not a miss "
              f"(the prediction was permissive)")
    print(f"    UNREGISTERED first-divergence decreases: {len(unexp)}   "
          f"{verdict(not unexp)}")
    for s, o, nn, fam in unexp:
        print(f"      {s:14s} {o:5d} -> {nn:5d}   fam {fam}   -- itemised")
    if unexp:
        miss("P-6 unregistered first-divergence decrease")

    # ---------------------------------------------------------------- P-7 --- #
    head("P-7  THE FAMILY TABLE (§4.7)")
    fams = sorted(set([f["family"] for f in ref["failures"]]
                      + [f["family"] for f in new["failures"]]))
    for fam in fams:
        was = sum(1 for f in ref["failures"] if f["family"] == fam)
        got = sum(1 for f in new["failures"] if f["family"] == fam)
        flag = ""
        if fam in FAMILY_PRED:
            _, pred = FAMILY_PRED[fam]
            flag = f"   <-- predicted {pred}   {verdict(got == pred)}"
            if got != pred:
                miss(f"P-7 family {fam.split()[0]} != {pred}")
        elif was != got:
            flag = "   <-- UNEXPECTED MOVE (see P-3/P-4 attribution)"
            miss(f"P-7 unexpected family move: {fam.split()[0]}")
        print(f"    {fam:46s} {was:3d} -> {got:3d}{flag}")
    print(f"    {'TOTAL':46s} {len(R):3d} -> {len(N):3d}   "
          f"predicted {PRIMARY_FAILURES}")

    # ---------------------------------------------------------------- P-8 --- #
    head("P-8  THE THREE SEATS THE WAVE BOOKED AS NOT CLOSING (§4.8)")
    for s, (why, prow, pfirst) in BOOKED_NOT_CLOSING.items():
        if s not in N:
            print(f"    {s:14s} CLOSED -- an INSTRUMENT FINDING about the "
                  f"faithful replay ({why})")
            finding(f"P-8 {s} closed though its landing booked it as not closing")
            continue
        f = N[s]
        print(f"    {s:14s} STILL FAILING   rows {R[s]['diverging_rows']}->"
              f"{f['diverging_rows']} (pred {prow})   first "
              f"{R[s]['first_bad_row']}->{f['first_bad_row']} (pred {pfirst})"
              f"   {verdict(True)}")
        print(f"                   {why}")

    # ------------------------------------------------------ Appendix A ------ #
    head("APPENDIX A  THE 43 PREDICTED MOVERS -- rows REPORTED, NOT BARRED")
    exact = near = off = gone = 0
    for s in sorted(MOVERS):
        prow, pfirst = MOVERS[s]
        if s not in N:
            print(f"    {s:14s} EXITED (see P-4)")
            gone += 1
            continue
        f = N[s]
        drow = f["diverging_rows"] - prow
        dfb = (f["first_bad_row"] - pfirst
               if f["first_bad_row"] is not None and pfirst is not None else None)
        if drow == 0 and dfb == 0:
            exact += 1
            tag = "EXACT"
        elif abs(drow) <= 8 and (dfb is None or abs(dfb) <= 8):
            near += 1
            tag = "near"
        else:
            off += 1
            tag = "OFF"
        fb = ("first %5s (pred %s, %+d)" % (f["first_bad_row"], pfirst, dfb)
              if dfb is not None else "first %s (pred %s)"
              % (f["first_bad_row"], pfirst))
        print(f"    {s:14s} rows {f['diverging_rows']:5d} (pred {prow:5d}, "
              f"{drow:+5d})   {fb}   {tag}")
    print(f"    EXACT {exact}   near(<=8) {near}   OFF {off}   exited {gone}"
          f"   of {len(MOVERS)}")
    print("    This is a FIDELITY measurement of the offline instrument against "
          "silicon, not a bar.")

    # ---------------------------------------------------------------------- #
    head("SUMMARY")
    print(f"  P-1  seats closed            {n}/8"
          f"   (high {closed_hi}/2, low {closed_lo}/6)")
    print(f"  P-2  failures                {c['failures']}"
          f"   band [{BAND_LO},{BAND_HI}]   primary {PRIMARY_FAILURES}")
    print(f"  P-3/4 unregistered flips     {flips}   budget {NOISE_BUDGET}")
    print(f"  P-6  unregistered earlier    {len(unexp)}")
    if misses:
        print(f"\n  {len(misses)} registered clause(s) MISSED, reported as "
              f"registered, never restated:")
        for m in misses:
            print(f"    - {m}")
    else:
        print("\n  every registered clause MET")
    if findings:
        print(f"\n  {len(findings)} FINDING(S):")
        for m in findings:
            print(f"    - {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
