#!/usr/bin/env python3
"""evtsurvey -- S9b survey: where do the EVT population's first divergences sit
RELATIVE TO THE ACKNOWLEDGE, and what is the first-divergence family?

Input is a `timed_fuzz.py --report` json.  NOT a gate: a taxonomy tool.
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc          # noqa: E402
import ucsim_fuzz as uf             # noqa: E402


def marks(recs, win):
    """Row indices of the interesting markers in the CHIP capture."""
    inta, halt = [], []
    prev = None
    for t in fc.extract_txns(recs):
        if t["start"] >= win:
            break
        k = fc.KIND[t["kind"]]
        if k == "INTA" and prev != "INTA":
            inta.append(t["start"])
        if k == "HALT":
            halt.append(t["start"])
        prev = k
    return inta, halt


def main():
    res = json.load(open(sys.argv[1]))
    fam = Counter()
    gaps = []
    rows = []
    for r in res:
        if r["cat"] != "DIVERGE":
            continue
        entry = json.loads(gzip.decompress(Path(r["path"]).read_bytes()))
        recs = entry["chip_rows"]
        win = uf.window_of(recs)
        inta, halt = marks(recs, win)
        fb = r["first_bad"]
        di = min((abs(fb - x) for x in inta), default=None)
        dh = min((abs(fb - x) for x in halt), default=None)
        # nearest marker BEFORE-or-at the divergence, which is what "the
        # divergence belongs to this event" means
        near = "-"
        if dh is not None and (di is None or dh <= di):
            near = f"HALT{fb - min(halt, key=lambda x: abs(fb - x)):+d}"
        elif di is not None:
            near = f"INTA{fb - min(inta, key=lambda x: abs(fb - x)):+d}"
        fam[(r["kind"], near.split("+")[0].split("-")[0])] += 1
        gaps.append((di if di is not None else 10 ** 9, r))
        rows.append((r["cid"], r["k"], fb, r["n"], r["ndiff"], r["kind"],
                     near, r.get("detail", "")[:48]))
    print(f"diverging seeds: {len(rows)}")
    print("family x nearest marker: " +
          "  ".join(f"{a}/{b}={c}" for (a, b), c in fam.most_common()))
    near_ack = sum(1 for g, _ in gaps if g <= 4)
    print(f"within 4 rows of an acknowledge: {near_ack}/{len(rows)}")
    for t in sorted(rows, key=lambda x: x[2]):
        print("  {:<9} {:<6} fb={:<6} n={:<5} nd={:<5} {:<10} {:<12} {}"
              .format(*t))


main()
