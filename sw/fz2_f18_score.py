#!/usr/bin/env python3
"""fz2_f18_score -- SCORE THE FLASH #18 CAPTURE AGAINST THE REGISTERED
PREDICTIONS, SEAT BY SEAT.

Registered in `docs/notes/fz2_flash18_prereg_2026-08-11.md`, committed at
`7c4a639ca4` **BEFORE any Quartus build and BEFORE any board contact**.

**THIS FILE WAS WRITTEN WHILE THE CONTROL BUILD WAS STILL RUNNING, BEFORE THE
BOARD WAS FLASHED AND BEFORE THE F18 LEDGER EXISTED.**  Every list below is
transcribed from that document; nothing is re-derived from the result, and the
verdict rules are fixed here in advance so no boundary can be chosen after
seeing where the seeds landed.

The reference ledger is FLASH #17's, because that is the era the predictions
were made against.

⚠ THREE THINGS THIS SCORER DOES THAT THE F17 ONE DID NOT, AND WHY:

  1. **P-2 SCORES A NON-ZERO TARGET.**  phantom-T1's three seats are registered
     to COLLAPSE to `bad_rows == 1`, not to close: the ucore has ONE status
     value per CPU clock where silicon has TWO, so the withdrawal clock stays a
     single `bs CODE != PASV` cell.  **A 0 on any of the three is scored as a
     FINDING, not as a success** -- it would refute the landing's own booking.
     A scorer that treats "fewer failures" as "better" cannot see that, so this
     one does not.

  2. **IT SCORES `bad_rows` AND `diverging_rows` SEPARATELY, AND SAYS WHICH.**
     `fz2_ledger` writes each entry's `diverging_rows = bad_rows + flick` and
     accumulates the corpus total as `bad_rows` alone.  Conflating them is what
     produced FLASH #17 §5.3's "unexplained one-sided +1..+5 residue"; the
     prereg §1.1 files that as an erratum and this file keeps the two units
     apart by name.

  3. **THE HEADLINE BAND IS 3.3x THE EFFECT**, worse than F17's 1.25x.  It is
     printed with the sentence that says it is a containment check and not
     evidence, so the two cannot be quoted apart.

Usage:
    python3 sw/fz2_f18_score.py --new <derived f18 ledger json>
                               [--ref <f17 ledger json>]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F17 = os.path.join(ROOT,
                   "sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json")


def S(s):
    return s.split()


# --------------------------------------------------------------------------- #
# P-1 -- KM's THREE SEATS, registered to LEAVE the ledger (prereg §4.1).
# seed -> (F17 bad_rows, F17 first_bad_row, signal strength)
# --------------------------------------------------------------------------- #
CLOSERS = {
    "fz2c/404041": (2437, 933, "high"),
    "fz2e/501066": (572, 515, "mid"),
    "fz2e/513019": (2843, 656, "high"),
}

# --------------------------------------------------------------------------- #
# P-2 -- phantom-T1's THREE SEATS, registered to COLLAPSE and STAY (§4.2).
# seed -> (F17 bad_rows, F17 first_bad_row, predicted first_bad_row)
# PRIMARY POINT is bad_rows == 1 with flick == 0; the BAND is 1..6 inclusive.
# ZERO IS A FINDING.
# --------------------------------------------------------------------------- #
COLLAPSERS = {
    "fz2c/404071": (905, 244, 243),
    "fz2e/514044": (1261, 235, 234),
    "fz2e/516001": (1154, 584, 583),
}
COLLAPSE_POINT = 1
COLLAPSE_LO, COLLAPSE_HI = 1, 6

# --------------------------------------------------------------------------- #
# P-9 -- the ONLY seeds exempt from the no-first-divergence-decrease bar.
# Three, not nineteen: the merged-tree replay names no others over 651 seeds.
# --------------------------------------------------------------------------- #
EARLIER_OK = set(COLLAPSERS)

# --------------------------------------------------------------------------- #
# P-7 -- the named non-movers (§4.7).  seed -> (bad_rows, first_bad_row) as the
# merged-tree replay re-measured them.
#
# ⚠ THE BAR IS "UNMOVED FROM THE REFERENCE LEDGER", AND IT IS SCORED THAT WAY.
# The tuple below is the prereg §4.7 table transcribed, and it is printed as a
# TRANSCRIPTION CHECK only.  The prereg's table quotes the REPLAY's `bad_rows`
# while the ledger entry carries `diverging_rows = bad_rows + flick` (§1.1), so
# two of these differ from the reference ledger by their `flick` and comparing
# against the literal would score a units mismatch as a moved seed.  Scoring
# `N[s] == R[s]` is unit-consistent by construction and is what "unmoved"
# means.  This was caught by running the scorer against the F17 NULL before the
# board was flashed; prereg AMENDMENT A-1.
# --------------------------------------------------------------------------- #
NONMOVERS = {
    # the §64.1 four (the KM/N1 list)
    "fz2c/405002": (840, 527),   "fz2c/405013": (921, 1331),
    "fz2c/405072": (891, 636),   "fz2e/512056": (984, 1475),
    # the W7-4 older §64.1 four
    "fz2c/406063": (3149, 245),  "fz2c/410047": (3589, 227),
    "fz2e/518053": (3413, 567),  "fz2e/535027": (3226, 296),
    # the M10 LEA-mod3 six
    "fz2c/406054": (3141, 470),  "fz2c/408019": (1086, 1617),
    "fz2e/518038": (194, 429),   "fz2e/522019": (3075, 396),
    "fz2e/524034": (3479, 457),  "fz2e/530001": (20, 442),
}
NONMOVER_GROUP = {
    "fz2c/405002": "§64.1 four", "fz2c/405013": "§64.1 four",
    "fz2c/405072": "§64.1 four", "fz2e/512056": "§64.1 four",
    "fz2c/406063": "W7-4 four",  "fz2c/410047": "W7-4 four",
    "fz2e/518053": "W7-4 four",  "fz2e/535027": "W7-4 four",
    "fz2c/406054": "LEA-mod3 6", "fz2c/408019": "LEA-mod3 6",
    "fz2e/518038": "LEA-mod3 6", "fz2e/522019": "LEA-mod3 6",
    "fz2e/524034": "LEA-mod3 6", "fz2e/530001": "LEA-mod3 6",
}

# ---- P-6: the falsifier (prereg §4.6) ------------------------------------- #
MUST_NOT_APPEAR = S("fz2c/404040")

# ---- §4.3: the registered headline ---------------------------------------- #
PRIMARY_FAILURES = 110
BAND_LO, BAND_HI = 100, 120         # 110 +/- the measured floor of 10/3,840
DENOM = 3837
NOISE_BUDGET = 10                   # total unregistered membership flips
PRED_BAD_SUM = 110023               # corpus rows_diverging = Sigma bad_rows
PRED_DIV_SUM = 110084               # Sigma diverging_rows = Sigma bad + flick
REF_MATCHED, REF_FAILURES = 3724, 113
REF_BAD_SUM, REF_DIV_SUM = 119192, 119258

# ---- §4.8: the registered family table ------------------------------------ #
FAMILY_PRED = {
    "C2 INTA-vectored delivery": (10, 9),
    "D2 core fetched, chip did not": (10, 8),
}

# ---- §4.4: the attribution dichotomy, stated so it cannot be softened ------ #
ATTRIB = ("A new/unregistered flip is attributed to THIS SITTING'S LANDINGS -- "
          "a landing-level finding -- if it carries `PSW.TF` set at a "
          "`0F`-escaped instruction within six F pops of its fork row (KM), or "
          "a HALT wake whose withdrawn announcement is followed by an "
          "acknowledge within 12 rows of its fork (phantom-T1).  Calling it "
          "NOISE requires POSITIVE evidence: the CORE leg bit-identical and/or "
          "the terminator's `fired` count moved.  \"Not obviously ours\" is NOT "
          "an attribution and will not be written.")


def verdict(ok):
    return "MET   " if ok else "MISSED"


def raw_rows(seeds, suffix=""):
    """{seed: (bad_rows, flick, first_bad)} straight out of the live campaign
    results.jsonl -- the ONLY place `bad_rows` and `flick` survive separately.
    The ledger entry has already added them together (§1.1)."""
    out = {}
    want = set(seeds)
    for cid in ("fz2c", "fz2e"):
        p = os.path.join(ROOT, f"sw/testdata/campaigns/{cid}{suffix}/"
                               f"results.jsonl")
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("seed") in want:
                    out[r["seed"]] = (r.get("bad_rows"), r.get("flick"),
                                      r.get("first_bad"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=F17)
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

    print("fz2_f18_score -- prereg docs/notes/fz2_flash18_prereg_2026-08-11.md "
          "(committed 7c4a639ca4, before build and before board contact)")
    print(f"  reference ledger  {os.path.relpath(a.ref, ROOT)}")
    print(f"  scored ledger     {os.path.relpath(a.new, ROOT)}")
    print(f"  ref era .sof      {ref['era']['sof_sha256'][:16]}...")
    print(f"  new era .sof      {new['era']['sof_sha256'][:16]}...")

    # ---------------------------------------------------------------- P-1 --- #
    head("P-1  KM's THREE SEATS CLOSE, SEED BY SEAT (§4.1) "
         "-- HALF THE SITTING'S CLAIM")
    closed = 0
    for s, (was, wasfb, sig) in CLOSERS.items():
        if s not in N:
            print(f"    {s:14s} bad {was:5d} -> 0   CLOSED   "
                  f"(first was {wasfb})   [{sig} signal]   {verdict(True)}")
            closed += 1
        else:
            f = N[s]
            print(f"    {s:14s} bad {was:5d} -> {f['diverging_rows']:5d}"
                  f"   DID NOT CLOSE   first {wasfb}->{f['first_bad_row']}"
                  f"  fam {f['family']}   {verdict(False)}")
            miss(f"P-1 seat {s} (KM) did not close")
    print(f"  closed {closed}/3   {verdict(closed == 3)}")
    print("  §4.1a: none of the three is below the measured noise MAGNITUDE "
          "(movers ran 1,189-3,312 rows);\n"
          "         572 is the smallest and it is mid-signal, not low.")

    # ---------------------------------------------------------------- P-2 --- #
    head("P-2  phantom-T1's THREE SEATS COLLAPSE TO ONE ROW AND STAY (§4.2) "
         "-- THE OTHER HALF")
    print(f"  PRIMARY POINT bad_rows == {COLLAPSE_POINT} and flick == 0; "
          f"BAND {COLLAPSE_LO} <= bad_rows <= {COLLAPSE_HI}; "
          f"bad_rows == 0 is a FINDING, not a success.")
    col_met = 0
    for s, (was, wasfb, predfb) in COLLAPSERS.items():
        if s not in N:
            print(f"    {s:14s} bad {was:5d} -> 0   *** CLOSED ***   "
                  f"FINDING -- this refutes the landing's own booking that the "
                  f"residual is the\n"
                  f"                   harness's one-status-per-clock limit "
                  f"(ackwake_results §2.5).  NOT scored as a success.")
            miss(f"P-2 seat {s} closed to 0 -- outside the registered band")
            finding(f"{s} closed to 0: the integration rendered a half-clock "
                    f"the offline harness cannot -- investigate")
            continue
        f = N[s]
        bad = f["diverging_rows"]          # ledger unit; see the flick note
        fb = f["first_bad_row"]
        ok_band = COLLAPSE_LO <= bad <= COLLAPSE_HI
        ok_fb = (fb == predfb)
        ok_point = (bad == COLLAPSE_POINT)
        print(f"    {s:14s} bad {was:5d} -> {bad:3d}"
              f"   (point {COLLAPSE_POINT}, band [{COLLAPSE_LO},{COLLAPSE_HI}])"
              f"   first {wasfb} -> {fb} (pred {predfb})"
              f"   band {verdict(ok_band)}  first {verdict(ok_fb)}"
              f"  {'point EXACT' if ok_point else 'point off'}")
        if ok_band and ok_fb:
            col_met += 1
        if not ok_band:
            miss(f"P-2 seat {s} bad_rows {bad} outside [{COLLAPSE_LO},"
                 f"{COLLAPSE_HI}]")
        if not ok_fb:
            miss(f"P-2 seat {s} first_bad_row {fb} != predicted {predfb}")
    print(f"  collapsed as registered {col_met}/3   {verdict(col_met == 3)}")
    print("  ⚠ the ledger's `diverging_rows` is `bad_rows + flick`; the "
          "prediction was made on `bad_rows`\n"
          "    with flick predicted 0, so a value of 2-6 here is a flick, not a "
          "second divergence.\n"
          "    the band above is applied to `diverging_rows`, which is the "
          "CONSERVATIVE direction (it is >= bad_rows).")
    raw = raw_rows(list(CLOSERS) + list(COLLAPSERS))
    if raw:
        print("  THE TWO UNITS, SEPARATED, STRAIGHT OUT OF THE LIVE "
              "results.jsonl (all six seats):")
        for s in list(CLOSERS) + list(COLLAPSERS):
            if s in raw:
                b, fl, fb = raw[s]
                tgt = 0 if s in CLOSERS else COLLAPSE_POINT
                print(f"    {s:14s} bad_rows {str(b):>5s}  flick {str(fl):>3s}"
                      f"  first_bad {str(fb):>5s}   "
                      f"registered bad_rows {tgt}")
            else:
                print(f"    {s:14s} not in the live results.jsonl -- reported")

    # ---------------------------------------------------------------- P-3 --- #
    head("P-3  THE HEADLINE, AGAINST THE BAND REGISTERED BEFORE CAPTURE (§4.3)")
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
        miss("P-3 headline outside the registered band")
        finding("headline outside the band -- investigate")
    print("  ⚠ §4.3: THE BAND IS 3.3x THE EFFECT.  A RESULT INSIDE IT SAYS "
          "NOTHING ABOUT EITHER LANDING AND IS\n"
          "    NOT QUOTED AS CONFIRMING ONE.  The evidence is P-1 and P-2, seat "
          "by seat, and nothing else.")
    print(f"  SEED MATCH             {c['matched']:,} / {c['denominator']:,} "
          f"= {c['seed_match_pct']} %   (F17 {REF_MATCHED:,} / {DENOM:,} "
          f"= 97.0550 %)")
    print(f"  ROW MATCH              "
          f"{c['rows_compared'] - c['rows_diverging']:,} / {c['rows_compared']:,}"
          f" = {c['row_match_pct']} %   (F17 98.9475 %)")
    print(f"  LEFT the ledger {len(left)}   ENTERED {len(came)}")

    head("P-3a  THE ROW METRIC, IN BOTH UNITS, NAMED (§1.1, §4.3)")
    s_div = sum(N[s]["diverging_rows"] for s in N)
    print(f"  corpus rows_diverging (Sigma bad_rows)      "
          f"{REF_BAD_SUM:,} -> {c['rows_diverging']:,} "
          f"({c['rows_diverging'] - REF_BAD_SUM:+,})   predicted "
          f"{PRED_BAD_SUM:,}   delta-vs-prediction "
          f"{c['rows_diverging'] - PRED_BAD_SUM:+,}")
    print(f"  Sigma diverging_rows  (Sigma bad + flick)   "
          f"{REF_DIV_SUM:,} -> {s_div:,} ({s_div - REF_DIV_SUM:+,})"
          f"   predicted {PRED_DIV_SUM:,}   delta-vs-prediction "
          f"{s_div - PRED_DIV_SUM:+,}")
    print("  No registered ROW COST this sitting: neither mechanism was "
          "measured to make ANY seed worse,\n"
          "  offline, on any of 651 seeds.  A cost here would be a finding.")

    # ---------------------------------------------------------------- P-4 --- #
    head("P-4  ZERO LOSSES, ON A BUDGET (§4.4)")
    print(f"    entered the ledger: {len(came)}   noise budget (shared with "
          f"P-5): {NOISE_BUDGET}")
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
        print("      ⚠ A `PSW.TF` seed among the entrants is the case to look "
              "at hardest -- it is KM's population.")

    # ---------------------------------------------------------------- P-5 --- #
    head("P-5  NO UNREGISTERED CLOSURE -- exits are EXACTLY KM's three (§4.5)")
    unreg = sorted(left - set(CLOSERS))
    print(f"    exits {len(left)}   registered 3   unregistered {len(unreg)}   "
          f"{verdict(not unreg)}")
    for s in unreg:
        f = R[s]
        print(f"      UNREGISTERED CLOSURE  {s}  fam {f['family']}  "
              f"was first {f['first_bad_row']} rows {f['diverging_rows']}  "
              f"tier {f.get('tier')}")
    if unreg:
        miss("P-5 unregistered closure")
    flips = len(unreg) + len(came)
    print(f"    TOTAL UNREGISTERED MEMBERSHIP FLIPS (entries + unregistered "
          f"exits) = {flips}   budget {NOISE_BUDGET}   "
          f"{verdict(flips <= NOISE_BUDGET)}")
    if flips > NOISE_BUDGET:
        miss("P-4/P-5 unregistered membership flips exceed the noise budget")
        finding(f"{flips} unregistered flips vs a floor of {NOISE_BUDGET}")

    # ---------------------------------------------------------------- P-6 --- #
    head("P-6  THE FALSIFIER: fz2c/404040 MUST NOT APPEAR (§4.6)")
    for s in MUST_NOT_APPEAR:
        gone = s not in N
        print(f"    {s}  " + ("ABSENT -- " + verdict(True) if gone
                              else "PRESENT -- FALSIFIER FIRED, "
                                   "LANDING-LEVEL FINDING"))
        if not gone:
            miss("P-6 falsifier fired")
            finding("fz2c/404040 present -- a landing broke a mechanism "
                    "nobody claimed")

    # ---------------------------------------------------------------- P-7 --- #
    head("P-7  THE NAMED NON-MOVERS, SEAT-LEVEL (§4.7)")
    print("    the bar is UNMOVED FROM THE REFERENCE LEDGER, scored N[s] vs "
          "R[s] (unit-consistent).\n"
          "    the prereg §4.7 literals are printed beside it as a "
          "TRANSCRIPTION CHECK only (A-1).")
    nm_ok = nm_bad = 0
    for s in sorted(NONMOVERS):
        pbad, pfb = NONMOVERS[s]
        grp = NONMOVER_GROUP[s]
        if s not in N or s not in R:
            print(f"    {s:14s} [{grp:11s}] NOT IN BOTH LEDGERS -- MISSED")
            miss(f"P-7 non-mover {s} ({grp}) left the ledger")
            nm_bad += 1
            continue
        f, r = N[s], R[s]
        ok = (f["diverging_rows"] == r["diverging_rows"]
              and f["first_bad_row"] == r["first_bad_row"])
        tx = "" if (r["diverging_rows"] == pbad
                    and r["first_bad_row"] == pfb) else \
             f"   [transcription: prereg says {pbad}/{pfb}, ref ledger holds " \
             f"{r['diverging_rows']}/{r['first_bad_row']} -- the flick, §1.1]"
        print(f"    {s:14s} [{grp:11s}] rows {r['diverging_rows']:5d} -> "
              f"{f['diverging_rows']:5d}   first {r['first_bad_row']} -> "
              f"{f['first_bad_row']}   {verdict(ok)}{tx}")
        if ok:
            nm_ok += 1
        else:
            nm_bad += 1
            miss(f"P-7 non-mover {s} ({grp}) moved")
    print(f"    UNMOVED {nm_ok} / {len(NONMOVERS)}   {verdict(nm_bad == 0)}")

    # ---------------------------------------------------------------- P-8 --- #
    head("P-8  THE FAMILY TABLE (§4.8)")
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
                miss(f"P-8 family {fam.split()[0]} = {got}, predicted {pred}")
        elif was != got:
            flag = "   <-- UNEXPECTED MOVE (see P-4/P-5 attribution)"
            miss(f"P-8 unexpected family move: {fam.split()[0]}")
        print(f"    {fam:46s} {was:3d} -> {got:3d}{flag}")
    print(f"    {'TOTAL':46s} {len(R):3d} -> {len(N):3d}   "
          f"predicted {PRIMARY_FAILURES}")
    print("    ⚠ §4.8: a family RE-CLASSIFICATION of the three collapsed seats "
          "is NOT a miss -- at bad_rows == 1\n"
          "      the classifier sees one cell.  The three seats' families are "
          "printed below for the record:")
    for s in COLLAPSERS:
        if s in N:
            print(f"      {s:14s} {R[s]['family']}  ->  {N[s]['family']}"
                  + ("   (RE-CLASSIFIED)" if R[s]["family"] != N[s]["family"]
                     else ""))

    # ---------------------------------------------------------------- P-9 --- #
    head("P-9  FIRST-DIVERGENCE: only phantom-T1's three may decrease (§4.9)")
    common = set(R) & set(N)
    exp_hit, unexp = [], []
    for s in sorted(common):
        o, nn = R[s]["first_bad_row"], N[s]["first_bad_row"]
        if o is None or nn is None or nn >= o:
            continue
        (exp_hit if s in EARLIER_OK else unexp).append((s, o, nn,
                                                        N[s]["family"]))
    print(f"    registered earlier-movers that moved earlier: "
          f"{len(exp_hit)} of {len(EARLIER_OK)} named")
    for s, o, nn, fam in exp_hit:
        pred = COLLAPSERS[s][2]
        print(f"      {s:14s} {o:5d} -> {nn:5d}   (predicted {pred})   {fam}")
    print(f"    UNREGISTERED first-divergence decreases: {len(unexp)}   "
          f"{verdict(not unexp)}")
    for s, o, nn, fam in unexp:
        print(f"      {s:14s} {o:5d} -> {nn:5d}   fam {fam}   -- itemised")
    if unexp:
        miss("P-9 unregistered first-divergence decrease")
    incr = [(s, R[s]["first_bad_row"], N[s]["first_bad_row"])
            for s in sorted(common)
            if R[s]["first_bad_row"] is not None
            and N[s]["first_bad_row"] is not None
            and N[s]["first_bad_row"] > R[s]["first_bad_row"]]
    print(f"    first-divergence INCREASES (reported, not barred): {len(incr)}")
    for s, o, nn in incr:
        print(f"      {s:14s} {o:5d} -> {nn:5d}")

    # ---------------------------------------------------------------------- #
    head("SUMMARY")
    print(f"  P-1  KM seats closed         {closed}/3")
    print(f"  P-2  phantom-T1 collapsed    {col_met}/3   "
          f"(point {COLLAPSE_POINT}, band [{COLLAPSE_LO},{COLLAPSE_HI}], "
          f"0 = FINDING)")
    print(f"  P-3  failures                {c['failures']}"
          f"   band [{BAND_LO},{BAND_HI}]   primary {PRIMARY_FAILURES}")
    print(f"  P-4/5 unregistered flips     {flips}   budget {NOISE_BUDGET}")
    print(f"  P-7  named non-movers        {nm_ok}/{len(NONMOVERS)} unmoved")
    print(f"  P-9  unregistered earlier    {len(unexp)}")
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
