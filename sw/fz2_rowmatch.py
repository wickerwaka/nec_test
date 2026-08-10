#!/usr/bin/env python3
"""fz2_rowmatch -- AMENDMENT A-14's SIXTH disposition, `ROW_MATCHED`, and its
FALSIFIERS.

THE RULING THIS IMPLEMENTS (user, 2026-08-09, prereg sec.36.1, verbatim):

    "If these seeds are matching between real CPU and core, then it doesn't
     matter if they aren't producing the final state dump."

THE CLASS, IN ONE LINE.  The socket leg and the fabric-core leg were compared
by the campaign's OWN comparator over its FULL window and did not differ on one
row.  That is the project's #1 correctness statement -- physical-vs-core match
-- measured directly.  The architectural dump is ENRICHMENT on top of it: where
a capture reaches the terminator the dump gives a second, independent column,
and where it does not, the row comparison still stands on its own.

  ⚠ WHAT IT IS NOT.  It is not a statement that the seed dumped, and it does
  NOT enter any rate.  E-1's two rate clauses measure TERMINATOR-REACHED and
  are untouched by this file -- see sec.36.3.  It is not a claim about the
  part's architectural state either: no dump means no arch column, and this
  class says nothing about one.  It says the two legs did the same thing,
  cycle for cycle, for the whole window the comparator ran.

THE PREDICATE, AND WHY EVERY CLAUSE IS THERE.  `evidence()` below is the
definition.  It reads the campaign's own comparator output -- the leaves
`fuzz_classify.classify` writes on the result line -- and adds NO second
comparator of its own:

  (1) `win >= SCORER_WINDOW`.  THE NON-DEGENERACY CLAUSE, and it is the one
      that keeps the class honest.  `diff_rows` sets the compare length to
      `min(len(real), len(sim), 4000)` on a seed with no done marker, so
      `win == 4000` is an ARITHMETIC PROOF that BOTH legs carried at least
      4,000 rows and that nothing shortened the comparison.  A match over a
      short window is not evidence and must not count as one.  The constant is
      `fuzz_campaign.SCORER_WINDOW`, registered at A-6 and re-used here -- this
      file introduces no threshold of its own.
  (2) `verdict == SUCCESS`.  The comparator's own verdict.  A `KNOWN_ACCEPTED`
      seed's legs DIVERGE and are accepted under a named rule; that is a
      different disposition and this class must not absorb it.
  (3) `bad_rows == 0` AND `flick == 0`.  Stated explicitly rather than left
      implied by (2), so the predicate is readable without tracing
      `classify`'s assembly order.  `flick == 0` is STRICTER than the
      comparator's own verdict -- a `qs` flicker row is benign there and
      disqualifying here -- and the direction matters: every clause in this
      predicate can only make the class SMALLER.
  (4) `func_mismatch` false and `truncated` false and no `alarms`.  Same
      direction, same reason.

THE FALSIFIERS, and they are why this file has a `falsify` command rather than
a paragraph.  The failure mode for a class like this is VACUITY -- a predicate
that says "matched" about everything is measuring nothing.  Three bars, all
registered at sec.36.5 before the rescore:

  F1  DIVERGENCE.  ZERO lines with `bad_rows > 0` may take the class.
  F2  WINDOW.  ZERO lines with `win < SCORER_WINDOW` may take the class.
  F3  NOT UNIVERSAL.  The predicate must be FALSE on a positive number of the
      corpus's lines, and the count is printed with its denominator.

F1 and F2 are the two ways the class could be a tautology; F3 is the check
that it is a question at all.  `falsify` prints each with its denominator and
returns non-zero on any failure.
"""
import argparse
import collections
import os
import sys

SW = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SW)

import fuzz_campaign as fzc                                  # noqa: E402

# The comparator's OWN limit, registered at A-6 as
# "`fuzz_classify.diff_rows`' own `limit`, in POSITIONS".  Not a new constant
# and not a threshold chosen here.
SCORER_WINDOW = fzc.SCORER_WINDOW

# Every leaf the predicate reads.  A line missing any of them cannot be asked
# and returns None -- never False, which would read as a measured absence
# (`fz2_stall`'s "not evaluable" convention, applied here).
NEEDED = ("verdict", "bad_rows", "flick", "win", "func_mismatch", "truncated")


def evidence(line):
    """A-14's SIXTH disposition, measured on the campaign's OWN comparator
    output.  Returns None when the line cannot be asked; otherwise a dict whose
    `row_matched` is the class and whose other keys are the clause-by-clause
    answer, so a reader can see WHICH clause did the work.

    `why` names the FIRST failing clause, for the census, and is None on a
    member."""
    if not isinstance(line, dict):
        return None
    for f in NEEDED:
        if line.get(f) is None:
            return None
    win = int(line["win"])
    full = win >= SCORER_WINDOW
    clean = (line["verdict"] == "SUCCESS"
             and int(line["bad_rows"]) == 0
             and int(line["flick"]) == 0
             and not line["func_mismatch"]
             and not line["truncated"]
             and not (line.get("alarms") or []))
    why = None
    if not full:
        why = "degenerate_window"
    elif line["verdict"] != "SUCCESS":
        why = f"verdict:{line['verdict']}"
    elif int(line["bad_rows"]) > 0:
        why = "legs_diverge"
    elif int(line["flick"]) > 0:
        why = "qs_flicker"
    elif line["func_mismatch"]:
        why = "func_mismatch"
    elif line["truncated"]:
        why = "txn_truncated"
    elif line.get("alarms"):
        why = "alarms"
    return {"row_matched": bool(full and clean),
            "win": win, "full_window": full,
            "bad_rows": int(line["bad_rows"]), "flick": int(line["flick"]),
            "verdict": line["verdict"],
            # THE ARITHMETIC PROOF, carried with the answer: `diff_rows` sets
            # `n = min(len(real), len(sim), 4000)` when there is no done
            # marker, so a `win` of 4,000 is a proof that both legs carried at
            # least that many rows.  Banked with the class so the window this
            # seed was compared over is never a thing a reader has to take on
            # trust.
            "legs_at_least": win,
            "why": why}


def resolve(line):
    """(row_matched, evidence, source).

    `line`   the comparator's leaves are present -- every capture this
             campaign has ever taken carries them, because `classify` writes
             them on every result line.
    `none`   a leaf is absent.  Returns None and the seed stays
             UNDISPOSITIONED; it is never extrapolated."""
    ev = evidence(line)
    if ev is None:
        return None, None, "none"
    return ev["row_matched"], ev, "line"


# --------------------------------------------------------------------------- #
# the falsifiers
# --------------------------------------------------------------------------- #
def _lines():
    import fz2_w1 as W
    return [(pop, r) for pop in W.POPS for r in W._lines(W.CID[pop])]


def cmd_falsify(a):
    rows = _lines()
    ev = [(pop, r, evidence(r)) for pop, r in rows]
    askable = [(p, r, e) for p, r, e in ev if e is not None]
    print(f"== A-14 ROW_MATCHED falsifiers over {len(rows)} corpus lines "
          f"({len(askable)} askable, {len(rows) - len(askable)} not)")

    rc = 0
    # F1 -- DIVERGENCE.  The class must not absorb a seed whose legs differ.
    div = [(p, r, e) for p, r, e in askable if e["bad_rows"] > 0]
    f1 = [x for x in div if x[2]["row_matched"]]
    print(f"   F1 DIVERGENCE : {len(f1)} / {len(div)} lines with bad_rows > 0 "
          f"take the class  [{'PASS' if not f1 else 'FAIL'}]")
    if f1:
        rc = 1
        for p, r, e in f1[:10]:
            print(f"     ** {r['seed']} bad={e['bad_rows']}")

    # F2 -- WINDOW.  A match over a short window is not evidence.
    short = [(p, r, e) for p, r, e in askable if e["win"] < SCORER_WINDOW]
    f2 = [x for x in short if x[2]["row_matched"]]
    print(f"   F2 WINDOW     : {len(f2)} / {len(short)} lines with win < "
          f"{SCORER_WINDOW} take the class  "
          f"[{'PASS' if not f2 else 'FAIL'}]")
    if f2:
        rc = 1
        for p, r, e in f2[:10]:
            print(f"     ** {r['seed']} win={e['win']}")

    # F3 -- NOT UNIVERSAL.  A predicate true of everything measures nothing.
    yes = [x for x in askable if x[2]["row_matched"]]
    no = [x for x in askable if not x[2]["row_matched"]]
    print(f"   F3 NOT UNIVERSAL: FALSE on {len(no)} / {len(askable)} askable "
          f"lines  [{'PASS' if no else 'FAIL'}]")
    if not no:
        rc = 1

    # The same three questions asked of the NON-DUMPING lines alone -- the only
    # population `bars` ever asks this predicate of.  Reported separately
    # because the corpus-wide figures are dominated by seeds that DID dump and
    # whose window is therefore done-shrunk for a reason that has nothing to do
    # with this class.
    nd = [(p, r, e) for p, r, e in askable if not r.get("arch_ok")]
    nd_div = [x for x in nd if x[2]["bad_rows"] > 0]
    nd_short = [x for x in nd if x[2]["win"] < SCORER_WINDOW]
    nd_yes = [x for x in nd if x[2]["row_matched"]]
    print(f"\n   ON THE NON-DUMPING LINES ALONE ({len(nd)}):")
    print(f"     legs DIVERGE          : {len(nd_div)}, of which "
          f"{sum(1 for x in nd_div if x[2]['row_matched'])} take the class")
    print(f"     window < {SCORER_WINDOW}        : {len(nd_short)}, of which "
          f"{sum(1 for x in nd_short if x[2]['row_matched'])} take the class")
    print(f"     ROW_MATCHED           : {len(nd_yes)} / {len(nd)}")
    for p, r, e in nd_div[:20]:
        print(f"       diverging: {r['seed']:>13} {r['verdict']:>14} "
              f"bad={e['bad_rows']:<5} win={e['win']} mech={r.get('mech')}")
    for p, r, e in nd_short[:20]:
        print(f"       short win: {r['seed']:>13} {r['verdict']:>14} "
              f"win={e['win']} mech={r.get('mech')}")

    print(f"\nA-14 FALSIFIERS: {'PASS' if rc == 0 else 'FAIL'}")
    return rc


def cmd_census(a):
    """What the class contains, with the window each member was compared over
    printed beside it -- the coordinator's own condition (sec.36.5)."""
    rows = _lines()
    yes, no, na = [], collections.Counter(), 0
    for pop, r in rows:
        e = evidence(r)
        if e is None:
            na += 1
            continue
        if e["row_matched"]:
            yes.append((pop, r, e))
        else:
            no[e["why"]] += 1
    print(f"== ROW_MATCHED over {len(rows)} lines: {len(yes)} take it, "
          f"{sum(no.values())} do not, {na} not askable")
    print("   reasons it is NOT taken:", dict(no))
    w = collections.Counter(e["win"] for _, _, e in yes)
    print("   window of the members:", dict(w))
    nd = [(p, r, e) for p, r, e in yes if not r.get("arch_ok")]
    print(f"   of the members, NON-DUMPING: {len(nd)}")
    if a.non_dumping:
        for p, r, e in sorted(nd, key=lambda x: x[1]["seed"]):
            print(f"     {r['seed']:>13} {r['tier']:>4} {str(r.get('mech')):>10} "
                  f"win={e['win']} legs>={e['legs_at_least']} "
                  f"bad={e['bad_rows']} flick={e['flick']} {r['verdict']}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("falsify", help="F1 / F2 / F3, with denominators")
    f.set_defaults(fn=cmd_falsify)
    c = sub.add_parser("census", help="what the class contains")
    c.add_argument("--non-dumping", action="store_true",
                   help="list the non-dumping members with their windows")
    c.set_defaults(fn=cmd_census)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
