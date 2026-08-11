#!/usr/bin/env python3
"""fz2_immaterial -- THE `IMMATERIAL` DISPOSITION, AND ITS FALSIFIERS.

THE RULING THIS IMPLEMENTS (user, 2026-08-11, verbatim):

    "An address value being presented on the bus that is never used does not
     impact functionality or timing.  A pin changing state slightly earlier or
     later is not significant if it doesn't change the overall timing."

and, on the disposition itself: *"Do everything except the merge."*

THE CLASS, IN ONE LINE.  A ledger failure whose two legs produced the SAME
architectural result on the SAME schedule, and differ only in what was on the
bus in between.  It leaves the WORKING residue and STAYS IN THE LEDGER.

THE PRECEDENT IS A-14 (`sw/fz2_rowmatch.py`, prereg sec.36-sec.37), and it is
followed clause for clause: a disposition with its OWN falsifier, DERIVED from
the record per seed and never a seed list, DISPOSITIONED-NOT-EXPLAINED, and
moving NO rate, bar or verdict.  `sw/fz2_w1.py bars` is untouched by this file
and must stay 11/11 byte-identical across it; if wiring this into a scorer
would move a bar, the answer is to report it and not to wire it.

  ⚠ WHAT IT IS NOT.  It is NOT a claim that nothing happened -- it is a claim
  that nothing MEASURABLE happened, on the two columns this rig can measure:
  the 15-word terminator dump and the clock at which every bus cycle starts.
  It is NOT an exclusion: the seed stays in the ledger, in the denominator, and
  in every rate it was already in.  And it is NOT A-14's `ROW_MATCHED`, which
  is the class for legs that do NOT differ at all; every member of THIS class
  diverges on at least one row, and clause (6) says so out loud.

THE PREDICATE.  `evidence()` below is the definition.  It reads the leaves
`fz2_materiality.measure()` writes -- the census's OWN measurement, imported as
a library, never re-implemented here -- and adds NO second comparator.  Every
clause can only make the class SMALLER, which is the direction that matters:

  (1) C-CONTROL.  The census's own two controls PASS on this seed, re-derived
      from the banked rows on THIS invocation: `diff_rows` reproduces the
      ledger's `first_bad_row` / `diverging_rows` / `compare_window` (C-ROW),
      and `arch_dump` reproduces its banked `arch_words` / `arch_sim_words`
      (C-ARCH).  A lens that reads the rows differently from the scorer is
      measuring its own parser, and a disposition resting on one would be
      dispositioning the parser.
  (2) D-PROOF.  THE NON-DEGENERACY CLAUSE, and the one that keeps the class
      honest.  BOTH legs produced a 15-word `MAGIC`-anchored terminator dump.
      The whole class rests on a DUMP-IDENTITY proof of non-propagation; with
      no dump there is no proof, and a seed with no proof must not be
      dispositioned by silence.  This clause alone holds all 11 UNSCOREABLE
      seeds out, and they STAY OPEN.
  (3) D-IDENT.  The two dumps are bit-identical, word for word, over
      `AW BW CW DW BP IX IY SP PC PS PSW DS0 DS1 SS MAGIC`.
  (4) S-STARTS.  Every bus cycle that starts inside the compare window starts
      on the SAME CLOCK in both legs -- no cycle exists on a clock where the
      other leg has none.  Measured in the CLOCK domain, not the cycle-index
      domain, because one insertion offsets every later index.
  (5) S-DONE.  Both legs reach the done marker on the same clock
      (`done_delta == 0`).  `None` fails this clause; it is never read as zero.
  (6) DIVERGENT.  The seed differs on at least one row.  Stated explicitly so
      the class can never absorb a MATCHING seed -- that is A-14's
      `ROW_MATCHED` and a different disposition -- and so that a reader can see
      the class is a statement about a REAL difference costing nothing, not
      about the absence of a difference.

  THE SUB-CLASS is the census's own TRANSIENT / COSMETIC split and is carried,
  not re-derived: `CYCLE_DEFINING = ("bs", "t")` versus everything else lives
  in `fz2_materiality` and in exactly one place.  Both sub-classes are
  IMMATERIAL; the split is reported because it says WHICH of the user's two
  sentences a seed answers to.

  ⚠ THE HONESTY CLAUSE, INHERITED VERBATIM FROM THE CENSUS.  IMMATERIAL means
  "no architectural consequence WAS OBSERVED on 15 registers at the end of the
  run", not "provably none exists".  A divergence that changed only memory the
  program never re-read, or a register the terminator's prologue overwrites
  before the store, would be invisible to it.

WHAT IS *NOT* DISPOSITIONED, STATED SO IT IS NOT ASSUMED
--------------------------------------------------------
  * THE 11 UNSCOREABLE SEEDS STAY OPEN.  Neither leg dumped, so there is no
    proof either way.  Dispositioning them would be ACCEPTANCE BY IGNORANCE.
    The census prints the class each WOULD take; that is a counterfactual and
    no seed is promoted by it.
  * THE 7 `TIMING_RECONVERGED` SEEDS STAY OPEN.  They finish on exactly the
    same clock but their schedule DID shift mid-run, so clause (4) fails and
    they do not take the disposition under the strict criterion.  They are
    named as a sub-class with the question written out, and the question is
    the USER's to answer -- see `cmd_reconverged` and the disposition
    document sec.5.

THE FALSIFIERS -- `falsify`, and this file has a command rather than a
paragraph for A-14's reason.  The failure mode for a class like this is
VACUITY: a predicate that says "harmless" about everything is measuring
nothing.  Eight bars, each printed with its denominator, non-zero exit on any
failure:

  G1  DUMP PROOF     ZERO seeds without a two-sided dump may take the class.
  G2  DUMP IDENTITY  ZERO seeds whose dumps differ in any word may take it.
  G3  SCHEDULE       ZERO seeds with an unmatched cycle start or a moved
                     done marker may take it.
  G4  NOT UNIVERSAL  The predicate must be FALSE on a positive number of the
                     ledger's entries, printed with its denominator.
  G5  CONTROLS       C-ROW and C-ARCH must PASS on EVERY ledger entry, re-
                     derived from the banked rows on this invocation.
  G6  THE CENSUS     The partition derived here must equal the one REGISTERED
                     in `docs/notes/fz2_materiality_census_2026-08-11.md`,
                     PARSED from that document.  This is the clause that fires
                     loudly if any seed's classification changes.
  G7  THE DOCUMENT   The 21 seeds NAMED in the disposition document must be
                     EXACTLY the ones derived here, set for set.  The document
                     names them for the reader; the class is COMPUTED, and G7
                     is the check that the two never drift apart.
  G8  NO FORK        The clause-by-clause predicate above must agree with
                     `fz2_materiality`'s own class on every entry WHOSE
                     CONTROLS PASS, with the skipped count printed.  It is
                     written independently of `measure()`'s `if` ladder on
                     purpose, so that agreement is evidence and not tautology.

G1-G3 are the three ways the class could be a tautology, G4 is the check that
it is a question at all, G5-G7 are the three ways it could silently drift, and
G8 is the check that this file did not fork the census.

  THE EXIT CODE IS MONOTONE.  G5 exits 2 -- the census is UNQUOTABLE, which is
  a stronger statement than "a bar failed" -- and no later bar may downgrade it
  to a 1.  `bar()` uses `max(rc, 1)` for exactly that reason.

  THE FALSIFIERS WERE DEMONSTRATED TO FAIL, NOT ONLY TO PASS: five
  perturbations, each caught by a NAMED bar, are tabulated in the disposition
  document sec.6.1 with the tool's verbatim output.  The harness is
  deliberately not committed -- a tool that ships the ability to rewrite a
  banked capture is a hazard -- and `--ledger` is the seam it used.

USAGE
    python3 sw/fz2_immaterial.py falsify        # the eight bars; 0 / 1 / 2
    python3 sw/fz2_immaterial.py census         # the 21, with their evidence
    python3 sw/fz2_immaterial.py reconverged    # the 7, and the open question
    python3 sw/fz2_immaterial.py --ledger X falsify      # a perturbed input
"""
import argparse
import collections
import json
import os
import re
import sys

SW = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SW)
sys.path.insert(0, SW)

import fz2_materiality as M                                  # noqa: E402

IMMATERIAL = "IMMATERIAL"

# The two documents this disposition is answerable to.  G6 reads the CENSUS
# (which registered the partition, and which this file did not write); G7 reads
# the DISPOSITION document (which this file's members are named in).  Both are
# PARSED, so a doc edit that disagrees with the code is a FAILURE and not a
# comment -- `sw/fz2_w1.py lint`'s idiom, applied to this layer.
CENSUS_DOC = os.path.join(ROOT, "docs", "notes",
                          "fz2_materiality_census_2026-08-11.md")
DISPO_DOC = os.path.join(ROOT, "docs", "notes",
                         "fz2_immaterial_disposition_2026-08-11.md")

# The census's own class names, imported rather than re-spelled.
FUNCTIONAL, TIMING = M.FUNCTIONAL, M.TIMING
TRANSIENT, COSMETIC, UNSCOREABLE = M.TRANSIENT, M.COSMETIC, M.UNSCOREABLE

# The NAMED sub-class of TIMING that this disposition deliberately does NOT
# take: schedule shifted mid-run, total run length unchanged.  Named so it is
# a question with an address rather than a footnote.
TIMING_RECONVERGED = "TIMING_RECONVERGED"


# --------------------------------------------------------------------------- #
# the predicate
# --------------------------------------------------------------------------- #
def evidence(m):
    """THE `IMMATERIAL` DISPOSITION, clause by clause.  -> dict.

    `m` is one `fz2_materiality.measure()` result.  Returns a dict whose
    `immaterial` is the class and whose other keys are the clause-by-clause
    answer, so a reader can see WHICH clause did the work.  `why` names the
    FIRST failing clause and is None on a member."""
    c_control = bool(m["c_row"] and m["c_arch"])
    d_proof = bool(m["dump_proof"])
    d_ident = d_proof and not m["arch_diff_words"]
    s_starts = (m["cycle_starts_only_chip"] == 0
                and m["cycle_starts_only_core"] == 0)
    s_done = m["done_delta"] == 0                 # None is NOT zero
    divergent = (m["bad_rows"] + m["flicker_rows"]) > 0

    why = None
    if not c_control:
        why = "control_failed"
    elif not d_proof:
        why = "no_dump_proof"
    elif not d_ident:
        why = "arch:" + ",".join(m["arch_diff_words"])
    elif not s_starts:
        why = ("cycle_starts chip-only %d / core-only %d"
               % (m["cycle_starts_only_chip"], m["cycle_starts_only_core"]))
    elif not s_done:
        why = ("done_clock %s" % ("none" if m["done_delta"] is None
                                  else "%+d" % m["done_delta"]))
    elif not divergent:
        why = "legs_do_not_differ"                # A-14's class, not this one

    ok = (c_control and d_proof and d_ident and s_starts and s_done
          and divergent)
    # The SUB-class is the census's, carried and never re-derived.
    sub = m["klass"] if ok else None
    return {"immaterial": ok, "sub": sub, "why": why,
            "c_control": c_control, "d_proof": d_proof, "d_ident": d_ident,
            "s_starts": s_starts, "s_done": s_done, "divergent": divergent,
            # the numbers a reader would otherwise have to take on trust
            "bad_rows": m["bad_rows"], "flicker_rows": m["flicker_rows"],
            "done_chip": m["done_chip"], "done_core": m["done_core"],
            "cycles_chip": m["cycles_chip"], "cycles_core": m["cycles_core"],
            "win": m["win"], "cols": m["cols"]}


def reconverged(m):
    """THE NAMED SUB-CLASS THIS DISPOSITION DOES NOT TAKE.  -> bool.

    A TIMING seed whose schedule shifted mid-run and whose program still
    finished on exactly the same clock.  Booked, undispositioned, and the
    question is stated in the disposition document sec.5."""
    return m["klass"] == TIMING and m["done_delta"] == 0


def partition(res):
    """-> (members, non_members, evidence-by-seed).  The whole layer, derived
    from the record on every call.  There is no list anywhere in this file."""
    ev = {m["seed"]: evidence(m) for m in res}
    yes = [m for m in res if ev[m["seed"]]["immaterial"]]
    no = [m for m in res if not ev[m["seed"]]["immaterial"]]
    return yes, no, ev


# --------------------------------------------------------------------------- #
# the two documents, PARSED
# --------------------------------------------------------------------------- #
_CENSUS_ROW = re.compile(
    r"^\|\s*\*\*(FUNCTIONAL|TIMING|TRANSIENT|COSMETIC|UNSCOREABLE)\*\*"
    r"[^|]*\|\s*\*\*(\d+)\*\*\s*\|")
_CENSUS_IMM = re.compile(
    r"^\s*IMMATERIAL\s*\(transient \+ cosmetic\)\s*(\d+)\s*/\s*(\d+)\b", re.M)
_CENSUS_RECONV = re.compile(
    r"^\s*done-marker clock IDENTICAL \(local re-schedule only\)\s*:\s*(\d+)",
    re.M)


def census_doc():
    """The partition as the CENSUS document registers it.  -> dict or None."""
    if not os.path.exists(CENSUS_DOC):
        return None
    text = open(CENSUS_DOC).read()
    d = {"classes": {}}
    for line in text.splitlines():
        mm = _CENSUS_ROW.match(line.strip())
        if mm:
            d["classes"][mm.group(1)] = int(mm.group(2))
    mm = _CENSUS_IMM.search(text)
    if mm:
        d["immaterial"], d["total"] = int(mm.group(1)), int(mm.group(2))
    mm = _CENSUS_RECONV.search(text)
    if mm:
        d["reconverged"] = int(mm.group(1))
    return d


# The disposition document names its members in a table whose first cell is the
# seed in backticks.  Only rows inside the MEMBER table are read, which is what
# the anchors are for -- a seed named in prose elsewhere in the document is not
# a claim of membership and must not be parsed as one.
_DISPO_BEGIN = "<!-- IMMATERIAL-MEMBERS-BEGIN -->"
_DISPO_END = "<!-- IMMATERIAL-MEMBERS-END -->"
_DISPO_SEED = re.compile(r"^\|\s*`(fz2[ce]/\d+)`\s*\|")
_DISPO_HEADLINE = re.compile(r"WORKING-RESIDUE\s*=\s*(\d+)\s*=\s*(\d+)\s*"
                             r"[-−]\s*(\d+)\s*$", re.M)


def dispo_doc():
    """The members as the DISPOSITION document names them.  -> dict or None."""
    if not os.path.exists(DISPO_DOC):
        return None
    text = open(DISPO_DOC).read()
    if _DISPO_BEGIN not in text or _DISPO_END not in text:
        return {"seeds": None, "headline": None, "anchors": False}
    body = text.split(_DISPO_BEGIN, 1)[1].split(_DISPO_END, 1)[0]
    seeds = set()
    for line in body.splitlines():
        mm = _DISPO_SEED.match(line.strip())
        if mm:
            seeds.add(mm.group(1))
    mm = _DISPO_HEADLINE.search(text)
    return {"seeds": seeds, "anchors": True,
            "headline": (int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))
            if mm else None}


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def _load(a):
    return M.measure_all(a.ledger, why="IMMATERIAL disposition")


def cmd_falsify(a):
    led, res = _load(a)
    yes, no, ev = partition(res)
    n = len(res)
    byc = collections.Counter(m["klass"] for m in res)
    print(f"\n== IMMATERIAL falsifiers over {n} ledger failures "
          f"(denominator {led['corpus']['denominator']}, "
          f"era sof {led['era']['sof_sha256'][:16]}…)")
    print(f"   members {len(yes)}   non-members {len(no)}")
    rc = 0

    def bar(tag, name, bad, denom, note=""):
        # `rc` is MONOTONE: a later failing bar must never downgrade G5's
        # exit 2 to a 1.  "Unquotable" is a stronger statement than "failing"
        # and the exit code has to keep saying so.
        nonlocal rc
        ok = not bad
        print(f"   {tag} {name:<15}: {len(bad)} / {denom} "
              f"{note}  [{'PASS' if ok else 'FAIL'}]")
        if bad:
            rc = max(rc, 1)
            for x in bad[:10]:
                print(f"     ** {x}")

    # G1 -- DUMP PROOF.  No proof, no disposition.
    pool = [m for m in res if not m["dump_proof"]]
    bar("G1", "DUMP PROOF",
        [f"{m['seed']} {m['klass']}" for m in pool
         if ev[m["seed"]]["immaterial"]],
        len(pool), "seeds without a two-sided dump take the class")

    # G2 -- DUMP IDENTITY.  A differing register is a material difference.
    pool = [m for m in res if m["dump_proof"] and m["arch_diff_words"]]
    bar("G2", "DUMP IDENTITY",
        [f"{m['seed']} arch:{','.join(m['arch_diff_words'])}" for m in pool
         if ev[m["seed"]]["immaterial"]],
        len(pool), "seeds whose 15 words differ take the class")

    # G3 -- SCHEDULE.  A moved cycle or a moved finish is a timing cost.
    pool = [m for m in res
            if m["cycle_starts_only_chip"] or m["cycle_starts_only_core"]
            or m["done_delta"] != 0]
    bar("G3", "SCHEDULE",
        [f"{m['seed']} {ev[m['seed']]['why']}" for m in pool
         if ev[m["seed"]]["immaterial"]],
        len(pool), "seeds whose schedule moved take the class")

    # G4 -- NOT UNIVERSAL.  A predicate true of everything measures nothing.
    print(f"   G4 {'NOT UNIVERSAL':<15}: FALSE on {len(no)} / {n} entries  "
          f"[{'PASS' if no else 'FAIL'}]")
    if not no:
        rc = 1
    whys = collections.Counter(
        (ev[m["seed"]]["why"] or "?").split(":")[0].split(" ")[0] for m in no)
    print(f"      why not, by first failing clause: {dict(whys)}")

    # G5 -- CONTROLS.  The census's own two, re-derived on this invocation.
    crow = [m["seed"] for m in res if not m["c_row"]]
    carch = [m["seed"] for m in res if not m["c_arch"]]
    ok5 = not crow and not carch
    print(f"   G5 {'CONTROLS':<15}: C-ROW {n - len(crow)} / {n} · "
          f"C-ARCH {n - len(carch)} / {n}  [{'PASS' if ok5 else 'FAIL'}]")
    if not ok5:
        rc = max(rc, 2)              # UNQUOTABLE, not merely failing
        for s in sorted(set(crow) | set(carch))[:10]:
            which = ("C-ROW" if s in crow else "") + \
                    ("+C-ARCH" if s in carch else "")
            print(f"     ** control failed: {s} ({which.strip('+')})")

    # G6 -- THE CENSUS DOCUMENT.  The registered partition, parsed.
    cd = census_doc()
    if cd is None:
        print(f"   G6 {'THE CENSUS':<15}: {CENSUS_DOC} MISSING  [FAIL]")
        rc = 1
    else:
        diffs = []
        for k in (FUNCTIONAL, TIMING, TRANSIENT, COSMETIC, UNSCOREABLE):
            if cd["classes"].get(k) != byc[k]:
                diffs.append(f"{k}: doc {cd['classes'].get(k)} != derived "
                             f"{byc[k]}")
        if cd.get("immaterial") != len(yes):
            diffs.append(f"IMMATERIAL: doc {cd.get('immaterial')} != derived "
                         f"{len(yes)}")
        if cd.get("total") != n:
            diffs.append(f"total: doc {cd.get('total')} != derived {n}")
        rc_n = sum(1 for m in res if reconverged(m))
        if cd.get("reconverged") != rc_n:
            diffs.append(f"TIMING_RECONVERGED: doc {cd.get('reconverged')} "
                         f"!= derived {rc_n}")
        bar("G6", "THE CENSUS", diffs, len(cd["classes"]) + 3,
            "registered cells disagree with the derivation")

    # G7 -- THE DISPOSITION DOCUMENT.  The named 21 must BE the derived 21.
    dd = dispo_doc()
    got = {m["seed"] for m in yes}
    if dd is None:
        print(f"   G7 {'THE DOCUMENT':<15}: {DISPO_DOC} MISSING  [FAIL]")
        rc = 1
    elif not dd["anchors"] or dd["seeds"] is None:
        print(f"   G7 {'THE DOCUMENT':<15}: member-table anchors absent  "
              f"[FAIL]")
        rc = 1
    else:
        diffs = ([f"named but NOT derived: {s}"
                  for s in sorted(dd["seeds"] - got)]
                 + [f"derived but NOT named: {s}"
                    for s in sorted(got - dd["seeds"])])
        if dd["headline"] != (len(no), n, len(yes)):
            diffs.append(f"WORKING-RESIDUE headline {dd['headline']} != "
                         f"derived ({len(no)}, {n}, {len(yes)})")
        bar("G7", "THE DOCUMENT", diffs,
            len(dd["seeds"] | got) + 1, "disagreements doc vs derivation")

    # G8 -- NO FORK.  The clauses must reproduce the census's own partition.
    # ASKED ONLY WHERE THE CONTROLS PASS, and the excluded count is printed:
    # clause (1) makes a control-failed seed a non-member while `measure()`
    # still reports the class it computed, and that disagreement is G5's
    # finding, not a fork.  Folding it in here would report one defect twice
    # under two names.
    askable = [m for m in res if m["c_row"] and m["c_arch"]]
    fork = [f"{m['seed']} census {m['klass']} / clauses "
            f"{IMMATERIAL if ev[m['seed']]['immaterial'] else 'not'}"
            for m in askable
            if ev[m["seed"]]["immaterial"] != (m["klass"] in (TRANSIENT,
                                                              COSMETIC))]
    bar("G8", "NO FORK", fork, len(askable),
        f"entries where the clauses and the census disagree "
        f"({n - len(askable)} not askable, controls failed)")

    print(f"\n   the working residue: {len(no)} = {n} - {len(yes)}   "
          f"({byc[FUNCTIONAL]} FUNCTIONAL + {byc[TIMING]} TIMING + "
          f"{byc[UNSCOREABLE]} UNSCOREABLE)")
    print(f"   NOT dispositioned, and printed every time: "
          f"UNSCOREABLE {byc[UNSCOREABLE]} · "
          f"{TIMING_RECONVERGED} {sum(1 for m in res if reconverged(m))}")
    print(f"\nIMMATERIAL FALSIFIERS: {'PASS' if rc == 0 else 'FAIL'}")
    return rc


def cmd_census(a):
    led, res = _load(a)
    yes, no, ev = partition(res)
    n = len(res)
    byc = collections.Counter(m["klass"] for m in res)
    print(f"\n== {IMMATERIAL}: {len(yes)} of {n} ledger failures, "
          f"{len(no)} remain in the WORKING residue")
    print(f"   quote it as: {len(no)} material+unproven of {n} diverging "
          f"of {led['corpus']['denominator']}")
    sub = collections.Counter(ev[m["seed"]]["sub"] for m in yes)
    print(f"   sub-classes: " + " · ".join(f"{k} {v}"
                                           for k, v in sorted(sub.items())))
    print("")
    w = max((len(m["family"]) for m in yes), default=10)
    print(f"  {'seed':<13} {'sub':<10} {'tier':<5} {'esc':>5} {'bad':>4} "
          f"{'done':>6} {'cyc':>5}  {'family':<{w}} columns")
    for m in sorted(yes, key=lambda x: (x["family"], x["seed"])):
        e = ev[m["seed"]]
        print(f"  {m['seed']:<13} {e['sub']:<10} {m['tier']:<5} "
              f"{m['escaped_n'] or 0:>5} {e['bad_rows']:>4} "
              f"{m['done_chip']:>6} {m['cycles_chip']:>5}  "
              f"{m['family']:<{w}} "
              + ", ".join(f"{c}={v}" for c, v in sorted(m["cols"].items())))
    print("")
    print(f"  every member: dumps bit-identical 15/15 · all bus cycles start "
          f"on the same clock · done marker identical")
    print(f"  STILL OPEN, and not dispositioned by this class: "
          f"UNSCOREABLE {byc[UNSCOREABLE]} (no dump either leg) · "
          f"{TIMING_RECONVERGED} {sum(1 for m in res if reconverged(m))}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"tool": "sw/fz2_immaterial.py",
                       "era": led["era"],
                       "denominator": led["corpus"]["denominator"],
                       "n_failures": n,
                       "immaterial": sorted(m["seed"] for m in yes),
                       "working_residue": len(no),
                       "reconverged": sorted(m["seed"] for m in res
                                             if reconverged(m)),
                       "evidence": ev}, f, indent=1)
        print(f"  wrote {a.json}")
    return 0


def cmd_reconverged(a):
    """The NAMED sub-class this disposition does NOT take, and the question."""
    led, res = _load(a)
    rec = [m for m in res if reconverged(m)]
    tim = [m for m in res if m["klass"] == TIMING]
    print(f"\n== {TIMING_RECONVERGED}: {len(rec)} of {len(tim)} TIMING seeds "
          f"-- BOOKED, UNDISPOSITIONED")
    print("   Their schedule shifted mid-run and the program still finished")
    print("   on EXACTLY the same clock.  Clause (4) S-STARTS fails, so they")
    print("   do NOT take IMMATERIAL under the strict reading of the ruling.")
    print("")
    w = max((len(m["family"]) for m in rec), default=10)
    print(f"  {'seed':<13} {'tier':<5} {'esc':>5} {'bad':>5} "
          f"{'chip-only':>9} {'core-only':>9} {'done':>6}  family")
    for m in sorted(rec, key=lambda x: x["seed"]):
        print(f"  {m['seed']:<13} {m['tier']:<5} {m['escaped_n'] or 0:>5} "
              f"{m['bad_rows']:>5} {m['cycle_starts_only_chip']:>9} "
              f"{m['cycle_starts_only_core']:>9} {m['done_chip']:>6}  "
              f"{m['family']:<{w}}")
    print("")
    print("  THE QUESTION FOR THE USER (disposition doc sec.5): the ruling")
    print("  says a pin moving early or late is not significant *if it")
    print("  doesn't change the overall timing*.  On these seeds the OVERALL")
    print("  timing is unchanged -- same finish clock -- but the bus is on")
    print("  clocks the other leg leaves free, which is visible to any device")
    print("  sharing it.  Is 'overall timing' the FINISH CLOCK, or the whole")
    print("  bus schedule?  Until that is answered they stay MATERIAL.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ledger", default=None,
                   help="failure ledger (default: fz2_ledger.CURRENT)")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("falsify", help="G1-G8, with denominators")
    f.set_defaults(fn=cmd_falsify)
    c = sub.add_parser("census", help="the members, with their evidence")
    c.add_argument("--json", default=None, help="write the derivation here")
    c.set_defaults(fn=cmd_census)
    r = sub.add_parser("reconverged", help="the named sub-class NOT taken")
    r.set_defaults(fn=cmd_reconverged)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
