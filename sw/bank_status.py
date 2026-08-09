#!/usr/bin/env python3
"""bank_status - RETIREMENT BY STATUS for `tests/v30/fuzz_bank/<cid>/`.

A banked campaign is retired BY STATUS, NOT BY LOCATION.  Nothing is moved,
renamed or deleted: the retirement is a `status` key in the campaign's own
`manifest.json`, and every consumer computes its population from that key.
This is the INV-1 precedent -- *"a list can drift away from what it describes
and a rename can be undone silently; a predicate computed from the artifact
cannot"*.  A superseded bank stays byte-identical where it always was, stays
readable, and comes back with one explicit flag; it simply stops being replayed
on every gate run.

**STATUS IS NOT INVALIDATION.**  `timed_fuzz.f46_invalidated` says a capture was
taken under a directive the rig could not apply -- a rig DEFECT, and the capture
is scored against something it never saw.  `SUPERSEDED` alleges nothing of the
kind: the captures are true silicon and stay true.  It says only that a better
instrument exists and the project no longer develops against this population.
The two predicates are independent, computed separately, and neither implies the
other.  See `docs/notes/invalidation_ledger.md` § SUPERSEDED POPULATIONS.

Manifest keys (all optional; absence means ACTIVE, so no existing bank and no
future promotion has to be edited to keep meaning what it meant):

    "status":         "SUPERSEDED"
    "superseded_by":  ["fz2c", "fz2e"]        what replaces it
    "as_of_commit":   "<sha>"                 the tree the status was set on
    "superseded_ledger": "docs/notes/invalidation_ledger.md#SUP-1"

This module is a LEAF: stdlib only.  Consumers in a multiprocessing pool import
it without pulling in the classifier or the accept engine.
"""
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
BANK = SW.parent / "tests" / "v30" / "fuzz_bank"

ACTIVE = "ACTIVE"
SUPERSEDED = "SUPERSEDED"


def manifest_of(cid):
    p = BANK / cid / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def bank_status(cid):
    """The campaign's status, READ FROM ITS OWN MANIFEST.  A bank with no
    `status` key is ACTIVE."""
    return manifest_of(cid).get("status") or ACTIVE


def is_superseded(cid):
    return bank_status(cid) == SUPERSEDED


def bank_cids(include_superseded=False):
    """Every campaign id present under the bank, sorted, status-filtered unless
    the caller explicitly asks for the retired ones."""
    if not BANK.is_dir():
        return []
    cids = sorted(d.name for d in BANK.iterdir()
                  if d.is_dir() and (d / "seeds").is_dir())
    if include_superseded:
        return cids
    return [c for c in cids if not is_superseded(c)]


def seed_paths(include_superseded=False, cids=None):
    """THE REPLAYED POPULATION -- the one predicate every consumer of
    `tests/v30/fuzz_bank/*/seeds/*.json.gz` should call.

    `cids` restricts to named campaigns (still status-filtered unless
    `include_superseded`), so a tool carrying its own `--bank` list gets the
    same answer as the gate's glob.

    Returns `(paths, dropped)` -- `dropped` maps each excluded cid to the number
    of seeds it holds, so no consumer has to be silent about what it left out.
    """
    want = bank_cids(include_superseded=True)
    if cids is not None:
        keep = set(cids)
        want = [c for c in want if c in keep]
    paths, dropped = [], {}
    for cid in want:
        seeds = sorted((BANK / cid / "seeds").glob("*.json.gz"))
        if not include_superseded and is_superseded(cid):
            dropped[cid] = len(seeds)
            continue
        paths += seeds
    return paths, dropped


def dropped_note(dropped, flag="--include-superseded"):
    """One loud line naming what was excluded and how to get it back.  A
    consumer that drops seeds silently defeats the whole mechanism."""
    if not dropped:
        return None
    n = sum(dropped.values())
    detail = " ".join(f"{c}:{k}" for c, k in sorted(dropped.items()))
    return (f"SUPERSEDED banks EXCLUDED: {n} seeds in {len(dropped)} campaign(s)"
            f" ({detail}) -- pass {flag} to include them "
            "(docs/notes/invalidation_ledger.md § SUP-1)")


def report(include_superseded=False):
    """`python3 sw/bank_status.py [--include-superseded]` -- the population, as
    arithmetic over the manifests.  A gate's denominator, checkable in a second
    without replaying anything."""
    rows = []
    for cid in bank_cids(include_superseded=True):
        n = len(list((BANK / cid / "seeds").glob("*.json.gz")))
        man = manifest_of(cid)
        rows.append((cid, bank_status(cid), n,
                     ",".join(man.get("superseded_by") or []) or "-"))
    paths, dropped = seed_paths(include_superseded=include_superseded)
    print(f"{'cid':<12} {'status':<12} {'seeds':>6}  superseded_by")
    for cid, st, n, by in rows:
        print(f"{cid:<12} {st:<12} {n:>6}  {by}")
    print(f"\nall banks           {sum(r[2] for r in rows):>6}")
    print(f"replayed population {len(paths):>6}"
          f"{'  (--include-superseded)' if include_superseded else ''}")
    note = dropped_note(dropped)
    if note:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(report("--include-superseded" in sys.argv[1:]))
