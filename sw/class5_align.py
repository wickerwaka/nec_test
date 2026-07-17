#!/usr/bin/env python3
"""RESYNC-TOLERANT ALIGNMENT.

THE BUG IT FIXES: the corpus aligner used
    D = first index where bus TYPE or ADDRESS differs
and TRUNCATED THE ENTIRE REMAINING PREFIX there. Measured:
    fz91000 w3   : D=116, mismatch run 2, post-D agreement 92/94 = 98%  -> 91 rows binned
    fz90002 r7.7 : D=192, mismatch run 2, post-D agreement 47/49 = 96%  -> 46 rows binned
A single two-access EU-vs-prefetch ARBITRATION SWAP (chip takes the prefetch
first, model takes the EU first; same two accesses, opposite order) threw away a
stream that then matched the chip exactly. We were never losing rows of
CORRECTNESS - we were losing rows of MEASUREMENT.

AND THE PATHOLOGY IS PERVERSE: it bites hardest when the model is GOOD ENOUGH TO
RE-ALIGN, so as the model improves the corpus SHRINKS. Every corpus we ever built
under-sampled the late-program region, and every historical corpus-size number is
a FLOOR, not a count.

WHY GAP-LENGTH ALONE CANNOT WORK (calibration, from real data):
    fz91000 w3   run=2, 98% after  -> TRANSIENT
    fz90002 r7.7 run=2, 96% after  -> TRANSIENT
    fz91000 r7.7 run=2, 15% after  -> GENUINELY DIVERGED
All three have run==2. A run-length window classifies them identically and is
therefore WRONG BY CONSTRUCTION. "Sustained" must be defined by POST-RESYNC
AGREEMENT, not by gap length.

DEFINITION OF SUSTAINED (defended):
  On a mismatch at j, we search for a re-sync: a shift s in [-SHIFT, +SHIFT] and
  a skip k in [1, WINDOW] such that the next CONFIRM accesses all match exactly
  under that shift. If such a re-sync exists, the mismatch was TRANSIENT: we
  record the divergence event with its contents and continue. If no re-sync
  exists within the window, the divergence is SUSTAINED and alignment stops.
  CONFIRM=8 consecutive exact matches is the evidence bar - it is what separates
  a 2-access swap (which resumes exact agreement immediately and indefinitely)
  from fz91000 r7.7 (which never regains a stable run).
EVERY RESYNC IS RECORDED AND COUNTED. A resync IS a model-vs-chip divergence - it
is data, not noise, and it is emitted as its own row class with the swap contents.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

WINDOW = 8      # how far ahead to look for a re-sync
SHIFT = 2       # tolerated insert/delete of accesses
CONFIRM = 8     # consecutive exact matches required to call it a re-sync


def _match(ca, ka, i, j):
    return (ca[i]["bs"] == ka[j]["bs"] and ca[i]["addr"] == ka[j]["addr"])


def _run_ok(ca, ka, i, j, n):
    """CONFIRM consecutive exact matches starting at (i,j)."""
    for d in range(CONFIRM):
        if i + d >= len(ca) or j + d >= len(ka):
            return False
        if not _match(ca, ka, i + d, j + d):
            return False
    return True


def align(ca, ka):
    """Resync-tolerant alignment.

    Returns (pairs, events, stop_reason) where
      pairs  = [(ci, ki)] aligned access index pairs (exact matches only)
      events = [dict(ci, ki, span_chip, span_model, shift)] each recorded
               divergence that was RE-SYNCED (never silent)
      stop   = ('end'|'sustained', ci, ki)
    """
    pairs, events = [], []
    i = j = 0
    while i < len(ca) and j < len(ka):
        if _match(ca, ka, i, j):
            pairs.append((i, j)); i += 1; j += 1; continue
        # mismatch: hunt for a re-sync
        found = None
        for k in range(1, WINDOW + 1):
            for s in range(-SHIFT, SHIFT + 1):
                ci, ki = i + k, j + k + s
                if ci < 0 or ki < 0:
                    continue
                if _run_ok(ca, ka, ci, ki, 0):
                    found = (ci, ki, k, s); break
            if found:
                break
        if not found:
            return pairs, events, ("sustained", i, j)
        ci, ki, k, s = found
        events.append(dict(ci=i, ki=j, k=k, shift=s,
                           chip=[(ca[x]["bs"], ca[x]["addr"]) for x in range(i, ci)],
                           model=[(ka[x]["bs"], ka[x]["addr"]) for x in range(j, ki)]))
        i, j = ci, ki
    return pairs, events, ("end", i, j)
