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

**AND THE SAME MECHANISM ONE LEVEL DOWN: PER-SEED EXCLUSION** (EXC-1,
`fz2_corpus_prereg_2026-08-08.md` §31 / AMENDMENT A-12).  An individual banked
seed can be EXCLUDED for the same kind of reason and by the same kind of key --
a list in the bank's own `manifest.json`, naming the file, the seed and the
reason.  An excluded seed is a TRUE capture of something this project is not
scoring (a deferred feature); it is neither invalid nor superseded, it stays
byte-identical where it is, and `--include-excluded` replays it in full.

Manifest keys (all optional; absence means ACTIVE, so no existing bank and no
future promotion has to be edited to keep meaning what it meant):

    "status":         "SUPERSEDED"
    "superseded_by":  ["fz2c", "fz2e"]        what replaces it
    "as_of_commit":   "<sha>"                 the tree the status was set on
    "superseded_ledger": "docs/notes/invalidation_ledger.md#SUP-1"

    "excluded_seeds": [                       per-seed, EXC-n
        {"file": "soup_509069_e6e5f2c9b2ec.json.gz",
         "seed": "fz2e/509069",
         "reason": "<why, in words>",
         "ledger": "docs/notes/invalidation_ledger.md#EXC-1",
         "as_of_commit": "<sha>"}
    ]

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
EXCL_KEY = "#excluded"          # the `dropped` key suffix for a per-seed EXC-n


def manifest_of(cid):
    p = BANK / cid / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def bank_status(cid):
    """The campaign's status, READ FROM ITS OWN MANIFEST.  A bank with no
    `status` key is ACTIVE."""
    return manifest_of(cid).get("status") or ACTIVE


def is_superseded(cid):
    return bank_status(cid) == SUPERSEDED


def excluded_of(cid):
    """The campaign's EXCLUDED seeds, READ FROM ITS OWN MANIFEST: a dict
    `{filename: record}`.  A bank with no `excluded_seeds` key excludes
    nothing, so nothing already in the tree changes meaning.

    EXC-1 / prereg §31.  This is the per-seed form of the retirement above and
    it obeys the same rule: the seed FILE is never moved, renamed or deleted --
    the exclusion is a key, and every consumer computes its population from
    the key."""
    out = {}
    for rec in manifest_of(cid).get("excluded_seeds") or []:
        f = rec.get("file")
        if f:
            out[f] = rec
    return out


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


def seed_paths(include_superseded=False, cids=None, include_excluded=False):
    """THE REPLAYED POPULATION -- the one predicate every consumer of
    `tests/v30/fuzz_bank/*/seeds/*.json.gz` should call.

    `cids` restricts to named campaigns (still status-filtered unless
    `include_superseded`), so a tool carrying its own `--bank` list gets the
    same answer as the gate's glob.

    Returns `(paths, dropped)` -- `dropped` maps a REASON KEY to the number of
    seeds that key removed, so no consumer has to be silent about what it left
    out.  There are two kinds of key and `dropped_note` tells them apart:

        "<cid>"              a whole bank retired SUPERSEDED  (SUP-n)
        "<cid>#excluded"     individually EXCLUDED seeds inside an ACTIVE bank
                             (EXC-n) -- the campaign is NOT retired

    A superseded bank's own excluded seeds are not double-counted: the bank
    leaves whole, under its own key.
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
        if not include_excluded:
            excl = excluded_of(cid)
            if excl:
                keep_p = [p for p in seeds if p.name not in excl]
                if len(keep_p) != len(seeds):
                    dropped[cid + EXCL_KEY] = len(seeds) - len(keep_p)
                seeds = keep_p
        paths += seeds
    return paths, dropped


def dropped_note(dropped, flag="--include-superseded",
                 excl_flag="--include-excluded"):
    """One loud line naming what was excluded and how to get it back.  A
    consumer that drops seeds silently defeats the whole mechanism.

    The two classes are NAMED SEPARATELY.  Printing a per-seed EXC exclusion
    under the word SUPERSEDED would allege that a campaign was retired when it
    was not, and would name the wrong flag for getting the seeds back -- which
    is the same class of untruth the ledger's three-way table exists to
    prevent."""
    if not dropped:
        return None
    sup = {k: v for k, v in dropped.items() if not k.endswith(EXCL_KEY)}
    exc = {k[:-len(EXCL_KEY)]: v for k, v in dropped.items()
           if k.endswith(EXCL_KEY)}
    parts = []
    if sup:
        detail = " ".join(f"{c}:{k}" for c, k in sorted(sup.items()))
        parts.append(f"SUPERSEDED banks EXCLUDED: {sum(sup.values())} seeds in "
                     f"{len(sup)} campaign(s) ({detail}) -- pass {flag} to "
                     "include them "
                     "(docs/notes/invalidation_ledger.md § SUP-1)")
    if exc:
        detail = " ".join(f"{c}:{k}" for c, k in sorted(exc.items()))
        parts.append(f"EXCLUDED seeds: {sum(exc.values())} seed(s) in "
                     f"{len(exc)} ACTIVE campaign(s) ({detail}) -- pass "
                     f"{excl_flag} to include them "
                     "(docs/notes/invalidation_ledger.md § EXC-1)")
    return "  |  ".join(parts)


def report(include_superseded=False, include_excluded=False):
    """`python3 sw/bank_status.py [--include-superseded] [--include-excluded]`
    -- the population, as arithmetic over the manifests.  A gate's denominator,
    checkable in a second without replaying anything."""
    rows = []
    for cid in bank_cids(include_superseded=True):
        n = len(list((BANK / cid / "seeds").glob("*.json.gz")))
        man = manifest_of(cid)
        rows.append((cid, bank_status(cid), n, len(excluded_of(cid)),
                     ",".join(man.get("superseded_by") or []) or "-"))
    paths, dropped = seed_paths(include_superseded=include_superseded,
                                include_excluded=include_excluded)
    print(f"{'cid':<12} {'status':<12} {'seeds':>6} {'excl':>5}  superseded_by")
    for cid, st, n, nx, by in rows:
        print(f"{cid:<12} {st:<12} {n:>6} {nx:>5}  {by}")
    print(f"\nall banks           {sum(r[2] for r in rows):>6}")
    print(f"replayed population {len(paths):>6}"
          f"{'  (--include-superseded)' if include_superseded else ''}"
          f"{'  (--include-excluded)' if include_excluded else ''}")
    note = dropped_note(dropped)
    if note:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(report("--include-superseded" in sys.argv[1:],
                    "--include-excluded" in sys.argv[1:]))
