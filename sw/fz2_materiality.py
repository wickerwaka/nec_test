#!/usr/bin/env python3
"""fz2_materiality -- A MATERIALITY CENSUS OF THE FLASH #17 FAILURE LEDGER.

THE QUESTION THIS ANSWERS (user, 2026-08-11, verbatim):

    "How many of these divergences have impacts on functionality or timing.
     An address value being presented on the bus that is never used does not
     impact functionality or timing, for instance.  A pin changing state
     slightly earlier or later is not significant if it doesn't change the
     overall timing."

The failure ledger counts SEEDS THAT DIFFER.  It does not say what the
difference COSTS.  This tool partitions the 113 F17 failures into MEASURED
consequence classes.  It is a LENS on banked data: it re-scores nothing,
captures nothing, touches no board and moves no verdict.  Every number it
prints is derived from `sw/testdata/campaigns/*/captures/*.json.gz` -- the
FABRIC rows of BOTH legs -- and from the F17 ledger that names them.

WHAT THE ROWS ARE, AND WHY THAT MATTERS
---------------------------------------
`fuzz_campaign.capture_board` writes BOTH legs from the BOARD:
`real` = `run_chip(use_core=False)`, the SOCKET leg (the real uPD70116);
`sim`  = `run_chip(use_core=True)`, the FABRIC ucore.  Both are silicon-era
captures of the same image under the same directive, 4,063 rows each.

  ⚠ THIS TOOL DOES NOT USE THE OFFLINE REPLAY.  `fz2_flash17_results` §5.3
  measured a ONE-SIDED +1..+5 row under-count in offline replay against
  fabric on 24 of 43 predicted seeds.  Reading the banked FABRIC rows makes
  that residue irrelevant to every figure below: there is no replay in the
  loop, so there is no replay bias to bound.  The cost is that this census
  can only be taken where the capture was BANKED -- which for the 113
  failures is 113 of 113, each verified by sha256 against the ledger.

THE TWO CONTROLS, RUN ON EVERY INVOCATION
-----------------------------------------
Neither is decoration.  A lens that reads the rows differently from the
scorer is measuring its own parser, so both are checked before anything is
classified and a failure of either makes the census unquotable (exit 2):

  C-ROW   `fuzz_classify.diff_rows(real, sim, window=line["win"])` must
          reproduce the ledger's `first_bad_row`, `diverging_rows` and
          `compare_window` for every seed.
  C-ARCH  `fuzz_classify.arch_dump(rows, len(rows), sentinel_only=True)` --
          `fuzz_campaign.eval_case`'s OWN parameters -- must reproduce the
          banked `arch_words` and `arch_sim_words` for every seed.

THE CLASSES.  Ordered, most material first; a seed takes the MOST material
class for which it qualifies.

  1 FUNCTIONAL   The architectural result differs.  Either both legs dumped
                 and the 15-word dumps differ in any word, or exactly one leg
                 produced a dump at all.  Real behavioural divergences; each
                 one is NAMED in the report with its differing words.
  2 TIMING       Dumps identical, but the SCHEDULE differs.  Measured in the
                 CLOCK domain, not the cycle-index domain: a bus cycle STARTS
                 on a clock in one leg where the other leg starts none, or
                 the two legs reach the done marker on different clocks.  A
                 schedule that shifts changes overall timing, so it is
                 material by the user's criterion.
  3 TRANSIENT    Dumps identical, EVERY bus cycle in the window starts on the
                 same clock in both legs, and at least one diff lands on a
                 CYCLE-DEFINING column (`t`, `bs_early`) -- a phase or status
                 pin early/late, or two cycles swapped between two slots that
                 both legs occupy.  Not significant by the user's criterion.
  4 COSMETIC     Dumps identical, every bus cycle starts on the same clock,
                 and every diff is a VALUE on `ad_addr` / `ad_data` / `ps` /
                 `qs` / `ube_n` at a matched position.  The ghost read is the
                 type case: both legs perform the read on the same clock at
                 different addresses, and the dump identity is the direct
                 measurement that the value did not propagate.  Not
                 significant by the user's criterion.
  5 UNSCOREABLE  NEITHER leg produced a dump.  The non-propagation proof used
                 by classes 3 and 4 is a DUMP-IDENTITY proof, and it is
                 unavailable here -- so these seeds are reported separately
                 and never forced into a class.  Their row evidence IS
                 printed, including the class they WOULD take, but that is a
                 counterfactual and is labelled as one.

  ⚠ THE HONESTY CLAUSE THAT MATTERS MOST.  Classes 3 and 4 mean "no
  architectural consequence WAS OBSERVED", measured on the 15 words the
  terminator dumps: AW BW CW DW BP IX IY SP PC PS PSW DS0 DS1 SS MAGIC.  A
  divergence that changed only memory the program never re-read, or a
  register the terminator overwrites before dumping, would be invisible to
  it.  The census prints the dump-proof audit as its own section and the
  count of class-3/4 seeds classified WITHOUT a two-sided dump is zero by
  construction.

WHAT IS *NOT* MEASURED HERE, STATED SO IT IS NOT ASSUMED
--------------------------------------------------------
  * The capture is a FIXED 4,063-row window on both legs, so "total row
    counts differ" -- the brief's first TIMING probe -- is never true on this
    population and carries no information.  Its usable equivalent is the
    DONE-MARKER CLOCK (`fuzz_classify._done_idx`): the row at which the
    program reached the terminator.  That IS scored, and it is the closest
    thing this rig has to "how long the program took".
  * Everything is measured INSIDE the ledger's own compare window `win`.  A
    schedule change beyond it is not seen; a schedule change near its end
    shows up as a cycle-count difference, and the tool does not try to tell
    that apart from an insertion.  Both are TIMING.
  * `family` is CARRIED FORWARD from the ledger and never re-derived --
    `fz2_ledger`'s rule for `fz2_ledger`'s reason (§38.9: the partition is a
    record of how the bus structure classified each seed, not a re-reading).
  * NOTHING here says whose fault a divergence is.  63 of the 113 are
    ESCAPED seeds; the census reports that overlap per class and does not
    adjust for it.  ⚠ CORRECTED 2026-08-11: this used to read "ESCAPED
    open-bus seeds, which F14 §4 established have no reproducible bus".
    There is no open bus on this rig -- `hdl/rtl/test_mem.sv` mirrors the
    64K image across the whole 1 MB space, so an escaped program's
    instruction stream IS defined on both legs.  The escaped class's
    capture-to-capture flicker is a MEASURED CORRELATION whose MECHANISM IS
    UNPROVEN.  The classification below is unaffected: it rests on dump
    identity and row alignment, never on the escape.

USAGE
    python3 sw/fz2_materiality.py                      # the whole census
    python3 sw/fz2_materiality.py --seed fz2c/404041   # one seed, verbose
    python3 sw/fz2_materiality.py --json out.json
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import sys

SW = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SW)
sys.path.insert(0, SW)

import fuzz_classify as fc                                   # noqa: E402
import fz2_ledger                                            # noqa: E402

FUNCTIONAL = "FUNCTIONAL"
TIMING = "TIMING"
TRANSIENT = "TRANSIENT"
COSMETIC = "COSMETIC"
UNSCOREABLE = "UNSCOREABLE"
CLASSES = (FUNCTIONAL, TIMING, TRANSIENT, COSMETIC, UNSCOREABLE)

# The columns `fuzz_classify.diff_rows` can report, split by whether they
# DEFINE the cycle (which cycle it is, and which phase it is in) or merely
# carry a VALUE inside a cycle whose identity and clock position both legs
# agree on.  This split is the brief's, restated as code: it is the ONLY
# place the TRANSIENT/COSMETIC boundary lives.
CYCLE_DEFINING = ("bs", "t")
VALUE_ONLY = ("addr", "data", "nxta", "ps", "ube", "qs")

# How many trailing identical rows count as "the legs re-aligned before the
# window ended".  REPORTED ONLY -- it dispositions nothing, because a seed
# with no dump on either leg is UNSCOREABLE either way.
TAIL_CLEAN = 64

# `fz2_flash17_results` §4.3's six NEW-at-F17 failures, verbatim.  The ledger
# has its OWN `new_failure` flag, derived against the F13-era committed
# ledger, and the two sets are DIFFERENT -- both are printed, because quoting
# one under the other's name is how an anchor stops anchoring.
F17_NEW_SIX = ("fz2e/521006", "fz2e/521024", "fz2e/522002",
               "fz2e/527051", "fz2e/529058", "fz2e/534003")


# --------------------------------------------------------------------------- #
# per-seed measurement
# --------------------------------------------------------------------------- #
def _cycles(rows, win):
    """The bus cycles that START inside the compare window, in order.

    `fuzz_classify.extract_txns` is the campaign's own extractor (T1 opens,
    T3/Tw carries data, T4 closes); this adds no second parser and only
    bounds it to `win`, the same bound `diff_rows` used."""
    return [t for t in fc.extract_txns(rows) if t["start"] < win]


def _col(other):
    """The column name out of a `RowDiff.other` string ('addr 0f2ea!=...')."""
    return other.split(" ", 1)[0]


def measure(entry, verify_sha=True):
    """Everything this census knows about one ledger failure.  -> dict."""
    path = os.path.join(ROOT, entry["capture"])
    blob = open(path, "rb").read()
    sha = hashlib.sha256(blob).hexdigest()
    if verify_sha and sha != entry["capture_sha256"]:
        raise SystemExit(f"CAPTURE SHA MISMATCH {entry['seed']}\n"
                         f"  ledger {entry['capture_sha256']}\n"
                         f"  file   {sha}")
    cap = json.loads(gzip.decompress(blob))
    line, real, sim = cap["line"], cap["real"], cap["sim"]
    win = line["win"]

    # ---- C-ROW: reproduce the ledger's own row diff ----------------------- #
    dr = fc.diff_rows(real, sim, window=win)
    bad = [x for x in dr.rows if not x.flicker]
    flick = [x for x in dr.rows if x.flicker]
    first_bad = dr.rows[0].i if dr.rows else None
    c_row = (dr.n == entry["compare_window"]
             and len(bad) + len(flick) == entry["diverging_rows"]
             and first_bad == entry["first_bad_row"])

    # ---- C-ARCH: reproduce the ledger's own dumps ------------------------- #
    dump_r = fc.arch_dump(real, len(real), sentinel_only=True)
    dump_s = fc.arch_dump(sim, len(sim), sentinel_only=True)
    c_arch = (dump_r == line["arch_words"] and dump_s == line["arch_sim_words"])

    # ---- the schedule, IN THE CLOCK DOMAIN --------------------------------#
    # A cycle-INDEX comparison cannot tell an inserted cycle apart from a
    # shifted one: one insertion offsets every later index.  Comparing the
    # SET OF START CLOCKS asks the question the user actually asked -- does a
    # bus cycle happen at a clock where the other leg has none? -- and it is
    # insertion-proof by construction.
    cr, cs = _cycles(real, win), _cycles(sim, win)
    start_r = {t["start"] for t in cr}
    start_s = {t["start"] for t in cs}
    only_chip = sorted(start_r - start_s)
    only_core = sorted(start_s - start_r)
    m = min(len(cr), len(cs))
    kind_diff = [j for j in range(m) if cr[j]["kind"] != cs[j]["kind"]]
    done_r, done_s = fc._done_idx(real), fc._done_idx(sim)
    done_delta = (None if (done_r is None or done_s is None)
                  else done_r - done_s)

    why = []
    if only_chip or only_core:
        why.append(f"cycle_starts chip-only {len(only_chip)} / "
                   f"core-only {len(only_core)}")
    if done_delta:
        why.append(f"done_clock {done_delta:+d}")
    schedule_changed = bool(why)

    # ---- columns ----------------------------------------------------------#
    cols = collections.Counter()
    for x in bad:
        for o in x.other:
            cols[_col(o)] += 1
        if x.qs_mm:
            cols["qs"] += 1
    for _ in flick:
        cols["qs(flicker)"] += 1
    defining = sum(v for k, v in cols.items() if k in CYCLE_DEFINING)

    last_diff = dr.rows[-1].i if dr.rows else None
    tail_clean = None if last_diff is None else (dr.n - 1 - last_diff)
    realigned = (tail_clean or 0) >= TAIL_CLEAN

    # ---- the class --------------------------------------------------------#
    def _immaterial():
        """TRANSIENT vs COSMETIC, given dumps equal and schedule unchanged."""
        if defining:
            return (TRANSIENT,
                    ("cycle REORDER: %d cycles differ in status at a slot "
                     "both legs occupy" % len(kind_diff)) if kind_diff
                    else "cycle-defining pin early/late on %d row(s)"
                         % defining)
        return COSMETIC, "value-only on %d row(s)" % len(bad)

    arch_words = None
    would_be = None
    if dump_r is not None and dump_s is not None:
        arch_words = sorted(k for k in dump_r if dump_r[k] != dump_s.get(k))
        if arch_words:
            klass, sub = FUNCTIONAL, "arch:" + ",".join(arch_words)
        elif schedule_changed:
            klass, sub = TIMING, "; ".join(why)
        else:
            klass, sub = _immaterial()
    elif dump_r is None and dump_s is None:
        klass = UNSCOREABLE
        sub = ("no dump on either leg; "
               + ("legs re-align (%d clean trailing rows)" % tail_clean
                  if realigned else "rows diverge to the window end"))
        would_be = (TIMING if schedule_changed else _immaterial()[0])
    else:
        klass = FUNCTIONAL
        who = "CHIP" if dump_r is not None else "CORE"
        both_done = done_r is not None and done_s is not None
        sub = (f"dump produced by {who} only; both legs wrote a done marker "
               f"({done_r} / {done_s}) but the other leg's 15-word "
               f"MAGIC-anchored dump did not form"
               if both_done else
               f"terminator dump reached by {who} only "
               f"(done chip {done_r} / core {done_s})")

    return {
        "seed": entry["seed"], "tier": entry["tier"],
        "family": entry["family"], "new_failure": entry.get("new_failure"),
        "banked_verdict": entry.get("banked_verdict"),
        "banked_sub": entry.get("banked_sub"),
        "klass": klass, "sub": sub, "would_be": would_be,
        "c_row": c_row, "c_arch": c_arch,
        "win": dr.n, "first_bad": first_bad, "last_diff": last_diff,
        "tail_clean": tail_clean, "realigned": realigned,
        "bad_rows": len(bad), "flicker_rows": len(flick),
        "cols": dict(cols),
        "cycles_chip": len(cr), "cycles_core": len(cs),
        "cycle_starts_only_chip": len(only_chip),
        "cycle_starts_only_core": len(only_core),
        "cycle_kind_diffs": len(kind_diff),
        "done_chip": done_r, "done_core": done_s, "done_delta": done_delta,
        "schedule_changed": schedule_changed, "schedule_why": why,
        "dump_chip": dump_r, "dump_core": dump_s,
        "dump_proof": dump_r is not None and dump_s is not None,
        "arch_diff_words": arch_words,
        "escaped_n": line.get("escaped_n"),
        "ob_frac": ((line.get("ob_escape") or {}).get("frac")),
        "mech": line.get("mech"),
    }


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def _pct(n, d):
    return f"{100.0 * n / d:.2f} %" if d else "n/a"


def report(res, led, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                        # noqa: E731
    denom = led["corpus"]["denominator"]
    n = len(res)
    byc = collections.Counter(r["klass"] for r in res)

    p("")
    p("=" * 78)
    p("  fz2 MATERIALITY CENSUS -- FLASH #17 FAILURE LEDGER")
    p("=" * 78)
    p(f"  seeds classified   {n}")
    p(f"  corpus denominator {denom}")
    p(f"  era sof            {led['era']['sof_sha256'][:16]}…")
    p(f"  rows               BANKED FABRIC captures, BOTH legs "
      f"(socket chip + fabric core)")
    p(f"  offline replay     NOT IN THE LOOP (see the module docstring)")

    crow = sum(1 for r in res if r["c_row"])
    carch = sum(1 for r in res if r["c_arch"])
    p("")
    p(f"  C-ROW   diff_rows reproduces the ledger   {crow} / {n}"
      f"   {'PASS' if crow == n else 'FAIL'}")
    p(f"  C-ARCH  arch_dump reproduces the ledger   {carch} / {n}"
      f"   {'PASS' if carch == n else 'FAIL'}")

    # ---- (a) by class ---------------------------------------------------- #
    p("")
    p("-" * 78)
    p("  (a) BY CONSEQUENCE CLASS")
    p("-" * 78)
    p(f"  {'class':<13} {'seeds':>5}  {'% of ' + str(n):>10}  "
      f"{'% of ' + str(denom):>12}")
    for k in CLASSES:
        p(f"  {k:<13} {byc[k]:>5}  {_pct(byc[k], n):>10}  "
          f"{_pct(byc[k], denom):>12}")
    mat = byc[FUNCTIONAL] + byc[TIMING]
    imm = byc[TRANSIENT] + byc[COSMETIC]
    p("  " + "-" * 44)
    p(f"  {'MATERIAL':<13} {mat:>5}  {_pct(mat, n):>10}  "
      f"{_pct(mat, denom):>12}   functional + timing")
    p(f"  {'IMMATERIAL':<13} {imm:>5}  {_pct(imm, n):>10}  "
      f"{_pct(imm, denom):>12}   transient + cosmetic")
    p(f"  {'UNPROVEN':<13} {byc[UNSCOREABLE]:>5}  "
      f"{_pct(byc[UNSCOREABLE], n):>10}  {_pct(byc[UNSCOREABLE], denom):>12}"
      f"   no dump on either leg")

    # ---- TIMING and UNSCOREABLE detail ----------------------------------- #
    tim = [r for r in res if r["klass"] == TIMING]
    ins = [r for r in tim if r["cycle_starts_only_chip"]
           or r["cycle_starts_only_core"]]
    donly = [r for r in tim if r not in ins]
    p("")
    p(f"  TIMING breakdown ({len(tim)}):")
    p(f"      a bus cycle starts on a clock the other leg has none : "
      f"{len(ins)}")
    p(f"      done-marker clock differs, cycle starts all match    : "
      f"{len(donly)}")
    ext = sorted(max(r["cycle_starts_only_chip"], r["cycle_starts_only_core"])
                 for r in tim)
    if ext:
        p(f"      unmatched cycle STARTS per seed: min {ext[0]}"
          f"  median {ext[len(ext) // 2]}  max {ext[-1]}")
    p("")
    p("  ⚠ TIMING SPLIT BY WHETHER THE PROGRAM'S TOTAL LENGTH MOVED.  The"
      " user's criterion is")
    p("  OVERALL timing, so the local-schedule seeds are separated from the"
      " ones that also")
    p("  changed when the program finished.  BOTH stay TIMING -- a bus cycle"
      " that exists in")
    p("  one leg and not the other is a schedule difference whatever the"
      " total comes to.")
    same = [r for r in tim if r["done_delta"] == 0]
    moved = [r for r in tim if r["done_delta"] not in (0, None)]
    nodone = [r for r in tim if r["done_delta"] is None]
    p(f"      done-marker clock IDENTICAL (local re-schedule only) : "
      f"{len(same)}")
    p(f"      done-marker clock MOVED (total run length changed)   : "
      f"{len(moved)}")
    p(f"      no done marker on one or both legs                   : "
      f"{len(nodone)}")
    dd = sorted(abs(r["done_delta"]) for r in moved)
    if dd:
        p(f"      |done-clock delta| over the {len(dd)} that moved:"
          f" min {dd[0]}  median {dd[len(dd) // 2]}  max {dd[-1]} clocks")

    uns = [r for r in res if r["klass"] == UNSCOREABLE]
    wb = collections.Counter(r["would_be"] for r in uns)
    p("")
    p(f"  UNSCOREABLE counterfactual ({len(uns)}) -- the class each WOULD take"
      f" if a dump existed.")
    p(f"  ⚠ NOT a verdict.  Printed so the residue's SHAPE is visible; no"
      f" seed is promoted by it.")
    for k in (TIMING, TRANSIENT, COSMETIC):
        p(f"      would be {k:<10} {wb[k]:>3}")

    # ---- (b) class x family ---------------------------------------------- #
    p("")
    p("-" * 78)
    p("  (b) CONSEQUENCE CLASS x MECHANISM FAMILY   (family carried forward)")
    p("-" * 78)
    fams = sorted({r["family"] for r in res})
    w = max(len(f) for f in fams)
    p(f"  {'family':<{w}} {'FUNC':>5} {'TIME':>5} {'TRAN':>5} {'COSM':>5} "
      f"{'UNSC':>5} {'tot':>5}")
    grid = collections.Counter((r["family"], r["klass"]) for r in res)
    for f in fams:
        row = [grid[(f, k)] for k in CLASSES]
        p(f"  {f:<{w}} {row[0]:>5} {row[1]:>5} {row[2]:>5} {row[3]:>5} "
          f"{row[4]:>5} {sum(row):>5}")
    tot = [byc[k] for k in CLASSES]
    p(f"  {'TOTAL':<{w}} {tot[0]:>5} {tot[1]:>5} {tot[2]:>5} {tot[3]:>5} "
      f"{tot[4]:>5} {n:>5}")

    # ---- (c) the functional seeds, named --------------------------------- #
    func = [r for r in res if r["klass"] == FUNCTIONAL]
    p("")
    p("-" * 78)
    p(f"  (c) EVERY FUNCTIONAL SEED, NAMED  ({len(func)})")
    p("-" * 78)
    for r in sorted(func, key=lambda x: x["seed"]):
        esc = f"escaped {r['escaped_n']}" if r["escaped_n"] else "not escaped"
        p(f"  {r['seed']:<13} {r['tier']:<5} {esc:<12} {r['family']}")
        if r["arch_diff_words"]:
            p("      " + "  ".join(
                f"{k} {r['dump_chip'][k]:#06x}/{r['dump_core'][k]:#06x}"
                for k in r["arch_diff_words"]))
        else:
            p(f"      {r['sub']}")

    # ---- (d) escaped overlap --------------------------------------------- #
    p("")
    p("-" * 78)
    p("  (d) THE ESCAPED OVERLAP   (the noise-prone class)")
    p("-" * 78)
    esc = [r for r in res if (r["escaped_n"] or 0) > 0]
    p(f"  escaped seeds among the {n}: {len(esc)}   "
      f"(`escaped_n > 0`)")
    p(f"  The escaped class flickers capture to capture (F14 §4 / F17 §4.3a),")
    p(f"  so a divergence on one is weaker evidence about the core.  ERRATUM")
    p(f"  2026-08-11: the reason given there -- 'an escaped program has no")
    p(f"  reproducible bus' -- rested on an open-bus story that is FALSE on")
    p(f"  this rig (test_mem.sv mirrors the image across the 1 MB space, so an")
    p(f"  escaped program's instruction stream IS defined).  The flicker is a")
    p(f"  MEASURED CORRELATION; its MECHANISM IS UNPROVEN.  The overlap is")
    p(f"  REPORTED; nothing below is adjusted for it, and no class below rests")
    p(f"  on it -- the classification is dump identity + row alignment.")
    ec = collections.Counter(r["klass"] for r in esc)
    nc = collections.Counter(r["klass"] for r in res
                             if (r["escaped_n"] or 0) == 0)
    p("")
    p(f"  {'class':<13} {'escaped':>8} {'not escaped':>12}")
    for k in CLASSES:
        p(f"  {k:<13} {ec[k]:>8} {nc[k]:>12}")
    tc = collections.Counter((r["tier"], r["klass"]) for r in res)
    p("")
    p(f"  {'class':<13} {'soup':>8} {'raw':>8}")
    for k in CLASSES:
        p(f"  {k:<13} {tc[('soup', k)]:>8} {tc[('raw', k)]:>8}")

    # ---- (e) anchors ------------------------------------------------------ #
    p("")
    p("-" * 78)
    p("  (e) SANITY ANCHORS")
    p("-" * 78)
    by_seed = {r["seed"]: r for r in res}
    p(f"  F17 §4.3's SIX new-at-F17 failures (its own list, verbatim):")
    for s in F17_NEW_SIX:
        r = by_seed.get(s)
        p(f"      {s:<13} {(r['klass'] if r else 'NOT IN LEDGER'):<12}"
          f" esc {r['escaped_n'] if r else '-':<5} {r['sub'][:44] if r else ''}")
    newf = [r for r in res if r["new_failure"]]
    p(f"  the LEDGER's own `new_failure` flag ({len(newf)}) -- a DIFFERENT set,"
      f" derived against F13:")
    for r in sorted(newf, key=lambda x: x["seed"]):
        p(f"      {r['seed']:<13} {r['klass']:<12} esc {r['escaped_n']:<5}"
          f" {r['sub'][:44]}")
    r = by_seed.get("fz2e/527051")
    if r:
        p(f"  fz2e/527051, the known flicker seed: {r['klass']}"
          f" -- {r['sub']}")
        p(f"      F17 §4.3a: its CORE dump is bit-identical ACROSS ERAS and its"
          f" CHIP dump MOVED.")
        p(f"      That is an era-to-era statement.  THIS census compares CHIP"
          f" vs CORE within F17,")
        p(f"      and the ledger's own `arch` column agrees with the answer"
          f" above.")

    # ---- (f) dump-proof audit -------------------------------------------- #
    p("")
    p("-" * 78)
    p("  (f) THE DUMP-PROOF AUDIT   (the honesty clause)")
    p("-" * 78)
    noproof = [r for r in res if not r["dump_proof"]]
    one = [r for r in noproof if r["dump_chip"] or r["dump_core"]]
    both = [r for r in noproof if not (r["dump_chip"] or r["dump_core"])]
    p(f"  seeds with a TWO-SIDED dump (the proof is available): "
      f"{n - len(noproof)} / {n}")
    p(f"  seeds WITHOUT one                                   : "
      f"{len(noproof)} / {n}")
    p(f"      exactly one leg dumped : {len(one):>3}"
      f"   -> FUNCTIONAL (the asymmetry IS the divergence)")
    p(f"      neither leg dumped     : {len(both):>3}"
      f"   -> UNSCOREABLE (no proof either way)")
    al = sum(1 for r in both if r["realigned"])
    p(f"          legs re-align before the window ends : {al}")
    p(f"          rows diverge to the window end       : {len(both) - al}")
    bad = [r for r in res
           if r["klass"] in (TRANSIENT, COSMETIC) and not r["dump_proof"]]
    p(f"  class-3/4 seeds classified WITHOUT a dump proof: {len(bad)}"
      f"   (0 by construction)")
    p("")
    p(f"  {'seed':<13} {'tier':<5} {'bad':>5} {'first':>6} {'tail':>6}"
      f"  would be     mech")
    for r in sorted(both, key=lambda x: x["seed"]):
        p(f"  {r['seed']:<13} {r['tier']:<5} {r['bad_rows']:>5}"
          f" {r['first_bad']:>6} {r['tail_clean']:>6}"
          f"  {r['would_be']:<12} {r['mech']}")

    # ---- (h) census class vs the campaign's own verdict ------------------ #
    p("")
    p("-" * 78)
    p("  (h) THIS CENSUS'S CLASS  x  THE CAMPAIGN'S OWN BANKED VERDICT")
    p("-" * 78)
    p("  ⚠ THE TWO WORDS 'FUNCTIONAL' MEAN DIFFERENT THINGS AND THE TABLE"
      " EXISTS TO SAY SO.")
    p("  `fuzz_classify` calls a seed FUNCTIONAL when the BUS TRANSACTION"
      " STREAM diverges --")
    p("  a write, a read address, or an INTA position that the other leg did"
      " not produce.")
    p("  THIS census calls a seed FUNCTIONAL when the ARCHITECTURAL RESULT"
      " diverges -- the")
    p("  15-word register dump.  A read at a different address whose value"
      " never reaches a")
    p("  register is the first and not the second, and that gap is the whole"
      " point of the")
    p("  user's question.  Neither column is wrong; they answer different"
      " questions.")
    p("")
    verds = sorted({r["banked_verdict"] for r in res})
    vg = collections.Counter((r["banked_verdict"], r["klass"]) for r in res)
    w2 = max(len(v) for v in verds)
    p(f"  {'banked verdict':<{w2}} {'FUNC':>5} {'TIME':>5} {'TRAN':>5} "
      f"{'COSM':>5} {'UNSC':>5} {'tot':>5}")
    for v in verds:
        row = [vg[(v, k)] for k in CLASSES]
        p(f"  {v:<{w2}} {row[0]:>5} {row[1]:>5} {row[2]:>5} {row[3]:>5} "
          f"{row[4]:>5} {sum(row):>5}")

    # ---- (g) the immaterial detail --------------------------------------- #
    p("")
    p("-" * 78)
    p("  (g) WHAT THE IMMATERIAL SEEDS ACTUALLY DIFFER ON")
    p("-" * 78)
    for k in (TRANSIENT, COSMETIC):
        sel = [r for r in res if r["klass"] == k]
        cc = collections.Counter()
        for r in sel:
            for c, v in r["cols"].items():
                cc[c] += v
        p(f"  {k} ({len(sel)} seeds), diff-row column totals: "
          + (", ".join(f"{c}={v}" for c, v in cc.most_common()) or "-"))
        for r in sorted(sel, key=lambda x: x["seed"]):
            p(f"      {r['seed']:<13} {r['bad_rows']:>3} rows  "
              f"{', '.join(f'{c}={v}' for c, v in sorted(r['cols'].items())):<44}"
              f" {r['family'][:32]}")
    p("")


def report_seed(r, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                        # noqa: E731
    p("")
    p(f"  seed            {r['seed']}   tier {r['tier']}")
    p(f"  family          {r['family']}")
    p(f"  banked verdict  {r['banked_verdict']} / {r['banked_sub']}")
    p(f"  CLASS           {r['klass']}   ({r['sub']})")
    if r["would_be"]:
        p(f"  would-be class  {r['would_be']}   (COUNTERFACTUAL, not a verdict)")
    p("")
    p(f"  controls        C-ROW {r['c_row']}   C-ARCH {r['c_arch']}")
    p(f"  compare window  {r['win']}   first_bad {r['first_bad']}"
      f"   last_diff {r['last_diff']}   trailing-clean {r['tail_clean']}")
    p(f"  diverging rows  {r['bad_rows']} + {r['flicker_rows']} flicker")
    p("  diff columns    " + (", ".join(f"{c}={v}" for c, v in
                                        sorted(r["cols"].items())) or "-"))
    p(f"  bus cycles      chip {r['cycles_chip']}   core {r['cycles_core']}")
    p(f"  cycle starts    chip-only {r['cycle_starts_only_chip']}"
      f"   core-only {r['cycle_starts_only_core']}"
      f"   status diffs {r['cycle_kind_diffs']}")
    p(f"  done marker     chip {r['done_chip']}   core {r['done_core']}"
      f"   delta {r['done_delta']}")
    p("  schedule        " + ("CHANGED: " + "; ".join(r["schedule_why"])
                              if r["schedule_changed"] else "UNCHANGED"))
    p(f"  dump proof      {r['dump_proof']}")
    if r["dump_chip"] and r["dump_core"]:
        d = r["arch_diff_words"]
        if not d:
            p("  arch dump       IDENTICAL, 15 / 15 words")
        for k in (d or []):
            p(f"      {k:<6} chip {r['dump_chip'][k]:#06x}"
              f"   core {r['dump_core'][k]:#06x}")
    p(f"  escaped_n       {r['escaped_n']}   ob_frac {r['ob_frac']}"
      f"   mech {r['mech']}")
    p("")


def measure_all(ledger=None, seed=None, verify_sha=True,
                why="materiality census"):
    """THE CENSUS'S CLASSIFICATION, AS A LIBRARY ENTRY POINT.  -> (led, [dict]).

    `main()` calls this and so does `sw/fz2_immaterial.py`, the IMMATERIAL
    disposition layer, and that is the whole reason it exists as a function:
    the disposition must read THIS classification and must never re-implement
    it.  A second copy of `measure()`'s reasoning living in the disposition
    tool is how a disposition and its census start disagreeing about the same
    seed, and neither one would be wrong on its own terms.

    It moves no logic: `main()` used to inline exactly these four statements,
    and the census's printed output is byte-identical across the extraction."""
    led = fz2_ledger.load(ledger, why=why)
    entries = led["failures"]
    if seed:
        entries = [e for e in entries if e["seed"] == seed]
        if not entries:
            raise SystemExit(f"no such failure in the ledger: {seed}")
    return led, [measure(e, verify_sha=verify_sha) for e in entries]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", default=None,
                    help="failure ledger (default: fz2_ledger.CURRENT)")
    ap.add_argument("--seed", default=None, help="one seed, verbose")
    ap.add_argument("--json", default=None, help="write per-seed rows here")
    ap.add_argument("--no-sha", action="store_true",
                    help="skip the capture sha256 verification (do not)")
    a = ap.parse_args(argv)

    led, res = measure_all(a.ledger, a.seed, verify_sha=not a.no_sha)

    if a.seed:
        report_seed(res[0])
    else:
        report(res, led)

    if a.json:
        with open(a.json, "w") as f:
            json.dump({"tool": "sw/fz2_materiality.py",
                       "ledger": os.path.relpath(
                           os.path.abspath(a.ledger or fz2_ledger.CURRENT),
                           ROOT),
                       "era": led["era"],
                       "denominator": led["corpus"]["denominator"],
                       "seeds": res}, f, indent=1)
        print(f"  wrote {a.json}")

    bad = [r for r in res if not (r["c_row"] and r["c_arch"])]
    if bad:
        print(f"  CONTROL FAILED on {len(bad)} seeds -- census NOT QUOTABLE")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
