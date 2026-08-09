#!/usr/bin/env python3
"""fz2_stall -- AMENDMENT A-4's fourth declared discard class, its FALSIFIER,
and the backfill that lets a capture taken before A-4 be classified at all.

THE CLASS.  `fuzz_campaign.stall_evidence` is the detector and its docstring is
the definition; nothing here restates it.  In one line: on the SOCKET leg's own
rows, the bus was already quiet for >= `STALL_IDLE` clocks when the terminating
NMI asserted, the cycle it went quiet on was NOT a HALT announcement, and it
issues not one bus cycle at or after the NMI.  The part stopped BEFORE the
terminator and the terminator does not restart it, so no `TERM_CLOCKS` value
reaches it and no capture-side repair can.

THE FALSIFIER, and it is the reason this file has a `falsify` command rather
than a comment.  A seed that reached the terminator DUMPED, and a dump is bus
activity; a detector that fires on one is broken.  The registered bar is
**ZERO firings on terminator-reached captures**, run over every banked capture
in both campaigns, and `falsify` prints that number beside the class's own.

THE BACKFILL, and its limit.  A-4 computes the detector at CAPTURE time and
banks `stalled` on the result line, so a future capture is self-classifying.
The 2026-08-09 re-capture predates that: its lines carry no such column, so
this tool recomputes the detector from BANKED ROWS where they exist -- and
they exist for a minority of the undispositioned seeds, because
`fuzz_campaign` banks rows only for divergent / keep-rows / ballast captures.
A seed with neither the column nor the rows is UNCLASSIFIABLE and stays
UNDISPOSITIONED.  `annotate` reports all three populations separately and
never extrapolates the third into the class.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import sys

SW = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SW)
ROOT = os.path.dirname(SW)

import fuzz_campaign as fzc                                  # noqa: E402

CAMPAIGNS = os.path.join(ROOT, "sw", "testdata", "campaigns")
# The live corpus and INV-2's archived one.  They are NEVER pooled into a
# rate; the falsifier reports each separately, which is also what makes the
# archive a second, disjoint population for it.
BANKS = {"current": ("fz2c", "fz2e"),
         # the A-5-scored capture, archived BY RENAME at amendment A-6 (prereg
         # sec.17.8).  NOT an invalidation -- no constant moved -- and kept
         # reachable so the A-4 falsifier can still be run on the bank it was
         # first run on.
         "prior": ("fz2c-A5-archive", "fz2e-A5-archive"),
         "archive": ("fz2c-INV2-archive", "fz2e-INV2-archive")}
BANKS["all"] = BANKS["current"] + BANKS["prior"] + BANKS["archive"]
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
           6: "MEMW", 7: "PASV"}


def capture_index(cid):
    """{k: path} for every banked capture of one campaign id."""
    out = {}
    for p in glob.glob(os.path.join(CAMPAIGNS, cid, "captures", "*.json.gz")):
        try:
            out[int(os.path.basename(p).split("_")[1])] = p
        except (IndexError, ValueError):                     # noqa: PERF203
            continue
    return out


def evidence_of_capture(path):
    """(line, evidence) for one banked capture, evidence via the ONE detector
    in `fuzz_campaign` -- this file owns no second copy of it."""
    d = json.load(gzip.open(path, "rt"))
    line, real, sim = d["line"], d.get("real"), d.get("sim")
    holds = ((line.get("term") or {}).get("hold_rows")) or None
    return line, fzc.stall_evidence(real, sim, holds)


def resolve(line, capidx):
    """(stalled, evidence, source) for one result line.

    source is `line` when A-4's own column is present (a self-classifying
    capture), `rows` when it had to be recomputed from banked rows, and
    `none` when the seed can be classified by neither -- in which case
    `stalled` is None and the seed stays UNDISPOSITIONED."""
    if line.get("stalled") is not None:
        return bool(line["stalled"]), line.get("stalled_at"), "line"
    p = capidx.get(line["k"])
    if p is None:
        return None, None, "none"
    _, ev = evidence_of_capture(p)
    if ev is None:
        return None, None, "none"
    return ev["stalled"], ev, "rows"


def _load(bank):
    """[(cid, line, evidence)] over every BANKED CAPTURE of a bank."""
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
    for bank in (["current", "prior", "archive"] if a.bank == "all"
                 else [a.bank]):
        rows = _load(bank)
        print(f"== bank {bank!r} ({', '.join(BANKS[bank])}): "
              f"{len(rows)} banked captures")
        noev = sum(1 for _, _, e in rows if e is None)
        ok = [(c, l, e) for c, l, e in rows if e is not None and l.get("arch_ok")]
        bad = [(c, l, e) for c, l, e in rows
               if e is not None and not l.get("arch_ok")]
        fo = [(c, l, e) for c, l, e in ok if e["stalled"]]
        fb = [(c, l, e) for c, l, e in bad if e["stalled"]]
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
                print(f"     ** {l['seed']} idle={e['idle']} "
                      f"last={BS_NAME[e['last_bs']]} after={e['after']}")
        # The two halves of the predicate, separately, so the reader can see
        # which clause is doing the work rather than take the conjunction on
        # trust.  The PRE-NMI half alone is clauses (1)+(2), which reference
        # nothing the terminator did.
        pre_ok = [e for _, _, e in ok if e["last_bs"] != fzc.BS_HALT
                  and e["idle"] >= fzc.STALL_IDLE]
        pre_bad = [e for _, _, e in bad if e["last_bs"] != fzc.BS_HALT
                   and e["idle"] >= fzc.STALL_IDLE]
        post_ok = [e for _, _, e in ok if e["after"] == 0]
        print(f"   clause (1)+(2) alone [pre-NMI only]: reached {len(pre_ok)}"
              f" / {len(ok)}, not-reached {len(pre_bad)} / {len(bad)}")
        print(f"   clause (3) alone [dead bus after the NMI]: reached "
              f"{len(post_ok)} / {len(ok)}")
        idl_ok = [e["idle"] for _, _, e in ok
                  if e["last_bs"] != fzc.BS_HALT]
        idl_f = [e["idle"] for _, _, e in fb]
        if idl_ok and idl_f:
            print(f"   longest non-HALT pre-NMI idle on a REACHED capture: "
                  f"{max(idl_ok)};  shortest in the class: {min(idl_f)} "
                  f"(STALL_IDLE = {fzc.STALL_IDLE})")
    return rc


def cmd_census(a):
    """What the class contains, and THE POSITIVE HALF -- the chip-vs-core
    agreement on the park clock, which is the evidence a discard must not
    throw away."""
    for bank in (["current", "prior", "archive"] if a.bank == "all"
                 else [a.bank]):
        rows = [(c, l, e) for c, l, e in _load(bank) if e is not None]
        cls = [(c, l, e) for c, l, e in rows if e["stalled"]]
        print(f"== bank {bank!r}: {len(cls)} captures in the class")
        if not cls:
            continue
        print("   tier:", dict(collections.Counter(l["tier"] for _, l, _ in cls)))
        print("   campaign:", dict(collections.Counter(c for c, _, _ in cls)))
        print("   verdict:", dict(collections.Counter(l["verdict"]
                                                      for _, l, _ in cls)))
        print("   last pre-NMI bus cycle:",
              dict(collections.Counter(BS_NAME[e["last_bs"]] for _, _, e in cls)))
        print("   term.vec_used:",
              dict(collections.Counter((l.get("term") or {}).get("vec_used")
                                       for _, l, _ in cls)))
        idl = sorted(e["idle"] for _, _, e in cls)
        print(f"   idle clocks before the NMI: min={idl[0]} "
              f"p50={idl[len(idl)//2]} max={idl[-1]}")
        both = [e for _, _, e in cls if e["core_last"] is not None]
        cs = [e for e in both if e["core_stalled"]]
        cm = [e for e in both if e["core_match"]]
        print(f"   POSITIVE HALF -- both legs have rows on {len(both)} of "
              f"{len(cls)}:")
        print(f"     the fabric core ALSO stops (same detector, core rows): "
              f"{len(cs)} / {len(both)}")
        print(f"     and parks on the SAME CLOCK as the chip: {len(cm)} / "
              f"{len(both)}")
        d = collections.Counter(e["core_last"] - e["last"] for e in both)
        print("     core-minus-chip park clock:",
              dict(sorted(d.items())[:12]))
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
