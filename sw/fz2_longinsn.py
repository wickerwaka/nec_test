#!/usr/bin/env python3
"""fz2_longinsn -- AMENDMENT A-7's FIFTH declared discard class, its HARD
FALSIFIER, and the resolver that says HOW each seed was asked.

THE CLASS, AND WHAT IT IS NOT.  `fuzz_campaign.long_insn_evidence` is the
detector and its docstring is the definition; nothing here restates it.  In
one line: on the SOCKET leg's own rows, the part is still driving the bus at
and after the terminating NMI and has not fetched one byte of code there, so
it is inside a single instruction that outlives the 4,096-record capture.

  ⚠ IT IS A CAPTURE-WINDOW LIMIT, NOT A PART DEFECT, AND THE TWO ARE
  CATEGORICALLY DIFFERENT.  A-4's `stalled` part has STOPPED: no window, no
  budget and no directive can make it dump.  A `long_insn` seed is RUNNING and
  WOULD dump given a longer window -- the NMI is latched at the pin and served
  at the instruction boundary that arrives after the last record.  `vec_used`
  is TRUE on this class for exactly that reason.  Nothing in this file may be
  read as a statement that the part failed to take an interrupt.

THE FALSIFIER, and it is the reason this file has a `falsify` command rather
than a comment.  Neither clause of the detector mentions a dump, so it is a
real question whether it fires on captures that DID reach the terminator -- a
detector that does is measuring "no dump" by another name and would make the
class circular.  The registered bar is ZERO firings on terminator-reached
captures, run over every banked capture in every bank, and `falsify` prints
that number with its denominator.

THE RESOLVER, and the one thing about it that needs saying out loud.  A-7
banks `long_insn` at capture time, so a capture taken under it is
self-classifying.  The 2026-08-09 A-6 capture predates that column, and its
rows exist for a minority of seeds -- but it banks A-6's `mech`, and since A-7
`term_mechanism` reaches its `LONG_INSN` branch by CALLING this same detector.
So `mech == "LONG_INSN"` is a banked, capture-time record of the detector
having fired, not an inference about it.  The implication runs ONE WAY: that
branch is reached only after REACHED / WINDOW / FORGED_DONE / BUDGET, so the
label can UNDER-report the detector and never over-report it, and a `mech`
that is present and is something else is INCONCLUSIVE rather than False.  Such
a seed stays UNDISPOSITIONED.  The direction matters: every uncertainty in
this resolver leaves the residue LARGER, which is the direction that cannot
buy a bar.
"""
import argparse
import collections
import gzip
import json
import os
import sys

SW = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SW)

import fuzz_campaign as fzc                                  # noqa: E402
import fz2_stall as fs                                       # noqa: E402

BANKS = fs.BANKS
BS_NAME = fs.BS_NAME
capture_index = fs.capture_index


def evidence_of_capture(path):
    """(line, evidence) for one banked capture, evidence via the ONE detector
    in `fuzz_campaign` -- this file owns no second copy of it."""
    d = json.load(gzip.open(path, "rt"))
    line, real, sim = d["line"], d.get("real"), d.get("sim")
    holds = ((line.get("term") or {}).get("hold_rows")) or None
    return line, fzc.long_insn_evidence(real, sim, holds)


def resolve(line, capidx):
    """(long_insn, evidence, source) for one result line.

    `line`  A-7's own capture-time column -- a self-classifying capture.
    `rows`  recomputed from a banked capture.
    `mech`  A-6's census column reads `LONG_INSN`, which since A-7 IS this
            detector's answer recorded at capture time (see the module
            docstring).  TRUE, definitively.
    `mech_inconclusive`  `mech` is present and is some other label.  The label
            is applied in a fixed order and an earlier one wins, so this does
            NOT say the detector is False.  Returns None; the seed stays
            UNDISPOSITIONED.
    `none`  neither column nor rows.  Returns None."""
    if line.get("long_insn") is not None:
        return bool(line["long_insn"]), line.get("long_insn_at"), "line"
    p = capidx.get(line["k"])
    if p is not None:
        _, ev = evidence_of_capture(p)
        if ev is not None:
            return ev["long_insn"], ev, "rows"
    if "mech" in line and line["mech"] is not None:
        if line["mech"] == "LONG_INSN":
            return True, None, "mech"
        return None, None, "mech_inconclusive"
    return None, None, "none"


def _load(bank):
    out = []
    for cid in BANKS[bank]:
        for p in sorted(capture_index(cid).values()):
            line, ev = evidence_of_capture(p)
            out.append((cid, line, ev))
    return out


def cmd_falsify(a):
    """THE HARD BAR: the detector must fire on ZERO captures that reached the
    terminator.  Reported per bank, and per campaign inside it."""
    rc = 0
    banks = (["current", "prior", "archive"] if a.bank == "all" else [a.bank])
    g_ok = g_fire = 0
    for bank in banks:
        rows = _load(bank)
        print(f"== bank {bank!r} ({', '.join(BANKS[bank])}): "
              f"{len(rows)} banked captures")
        noev = sum(1 for _, _, e in rows if e is None)
        ok = [(c, l, e) for c, l, e in rows
              if e is not None and l.get("arch_ok")]
        bad = [(c, l, e) for c, l, e in rows
               if e is not None and not l.get("arch_ok")]
        fo = [(c, l, e) for c, l, e in ok if e["long_insn"]]
        fb = [(c, l, e) for c, l, e in bad if e["long_insn"]]
        g_ok += len(ok)
        g_fire += len(fo)
        print(f"   not evaluable (no unique terminating-NMI run): {noev}")
        for cid in BANKS[bank]:
            n_ok = sum(1 for c, _, _ in ok if c == cid)
            n_f = sum(1 for c, _, _ in fo if c == cid)
            print(f"   {cid:22s} terminator-REACHED {n_ok:4d}   "
                  f"detector fires on {n_f}")
        print(f"   FALSIFIER over the bank: fires on {len(fo)} / {len(ok)} "
              f"terminator-REACHED captures  "
              f"[{'PASS' if not fo else 'FAIL'}]")
        print(f"   for contrast, on NOT-reached captures: {len(fb)} / "
              f"{len(bad)}")
        if fo:
            rc = 1
            for c, l, e in fo[:20]:
                print(f"     ** {l['seed']} after={e['after']} "
                      f"code={e['code_after']} qs_nz={e['qs_nz']}")
        # The two clauses separately, so the reader can see which one does the
        # work rather than take the conjunction on trust.
        live = [e for _, _, e in ok if e["after"]]
        nocode = [e for _, _, e in ok if not e["code_after"]]
        print(f"   clause (1) alone [bus still running after the NMI]: "
              f"{len(live)} / {len(ok)} reached")
        print(f"   clause (2) alone [not one CODE fetch after the NMI]: "
              f"{len(nocode)} / {len(ok)} reached")
        # A-4 DISJOINTNESS, checked and not asserted: clause (1) is A-4 clause
        # (3)'s exact negation, so no capture may carry both labels.
        both = 0
        for c, l, e in rows:
            if e is None or not e["long_insn"]:
                continue
            st = fs.resolve(l, capture_index(c))[0]
            both += bool(st)
        print(f"   carries BOTH A-4 `stalled` and A-7 `long_insn`: {both} "
              f"[{'PASS' if not both else 'FAIL'} -- disjoint by construction]")
        if both:
            rc = 1
    print(f"\nA-7 FALSIFIER, ALL BANKS: fires on {g_fire} / {g_ok} "
          f"terminator-REACHED captures  [{'PASS' if not g_fire else 'FAIL'}]")
    return rc


def cmd_census(a):
    """What the class contains, and the corroborating measurement that makes it
    a mechanism rather than a label: `QS` never changes for the whole post-NMI
    span, the bus is MEMR/MEMW only, and `LOCK` is never asserted."""
    for bank in (["current", "prior", "archive"] if a.bank == "all"
                 else [a.bank]):
        rows = [(c, l, e) for c, l, e in _load(bank) if e is not None]
        cls = [(c, l, e) for c, l, e in rows if e["long_insn"]]
        print(f"== bank {bank!r}: {len(cls)} captures in the class")
        if not cls:
            continue
        print("   tier:", dict(collections.Counter(l["tier"]
                                                   for _, l, _ in cls)))
        print("   campaign:", dict(collections.Counter(c for c, _, _ in cls)))
        print("   term.vec_used:",
              dict(collections.Counter((l.get("term") or {}).get("vec_used")
                                       for _, l, _ in cls)))
        npost = sum(e["post_rows"] for _, _, e in cls)
        nqs = sum(e["qs_nz"] for _, _, e in cls)
        nlock = sum(e["lock_rows"] for _, _, e in cls)
        print(f"   post-NMI rows {npost}; rows with ANY queue activity "
              f"(`qs` != 0): {nqs}; rows with LOCK asserted: {nlock}")
        act = sorted(e["after"] for _, _, e in cls)
        print(f"   non-PASV post-NMI rows per capture: min={act[0]} "
              f"p50={act[len(act)//2]} max={act[-1]}")
        # the bus-cycle kinds, off the rows themselves
        kinds = collections.Counter()
        for c, l, e in cls:
            p = capture_index(c)[l["k"]]
            d = json.load(gzip.open(p, "rt"))
            for r in d["real"]:
                if r["idx"] >= e["f"] and r["bs_early"] != 7 and r.get("t") == 1:
                    kinds[BS_NAME[r["bs_early"]]] += 1
        print("   post-NMI bus cycles by kind:", dict(kinds))
        both = [e for _, _, e in cls if e["core_after"] is not None]
        cm = [e for e in both if e["core_match"]]
        print(f"   POSITIVE HALF -- both legs have rows on {len(both)} of "
              f"{len(cls)}: the FABRIC CORE is in the same state "
              f"(bus running, no CODE fetch) on {len(cm)} / {len(both)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("falsify", "census"):
        p = sub.add_parser(name)
        p.add_argument("--bank", choices=sorted(BANKS), default="all")
    a = ap.parse_args()
    return {"falsify": cmd_falsify, "census": cmd_census}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
