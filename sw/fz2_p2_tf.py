#!/usr/bin/env python3
"""fz2_p2_tf -- the `PSW.TF` SUB-POPULATION of the fuzz-v2 corpus, and how it
scores on a `fz2_c1_rescore` leg.

`results.jsonl` carries `has_tf` per seed, so the population is DERIVED, never
listed.  The board's own tally (FLASH #14: 101 seeds, 7 failing) is a BOARD
figure and cannot be moved offline; what this prints is the OFFLINE tally over
the subset that has a retained capture, which is the quantity an offline
landing can move.

    python3 sw/fz2_p2_tf.py LEG.json [LEG2.json]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tf_seeds():
    out, tot = set(), 0
    for cid in ("fz2c", "fz2e"):
        for l in open(ROOT / "sw/testdata/campaigns" / cid / "results.jsonl"):
            r = json.loads(l)
            tot += 1
            if r.get("has_tf"):
                out.add(r["seed"])
    return out, tot


def leg(p):
    return {r["seed"]: r for r in json.load(open(p))}


if __name__ == "__main__":
    tf, tot = tf_seeds()
    print(f"corpus {tot} seeds, PSW.TF set in {len(tf)}")
    legs = [(p, leg(p)) for p in sys.argv[1:]]
    for p, L in legs:
        have = sorted(s for s in tf if s in L)
        clean = [s for s in have if L[s].get("bad") == 0]
        print(f"{Path(p).name:24s}  TF seeds with a capture {len(have):3d}   "
              f"row-clean {len(clean):3d}   failing {len(have) - len(clean):3d}")
    if len(legs) == 2:
        (_, B), (_, A) = legs
        have = sorted(s for s in tf if s in A and s in B)
        g = [s for s in have if B[s].get("bad") and A[s].get("bad") == 0]
        l = [s for s in have if B[s].get("bad") == 0 and A[s].get("bad")]
        print(f"TF population: GAINED {len(g)}  LOST {len(l)}")
        for s in g:
            print("   GAINED", s)
        for s in l:
            print("   LOST  ", s)
