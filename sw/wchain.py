#!/usr/bin/env python3
"""wchain -- the WRITE-CHAIN census, read straight out of the GOLDEN rows.

Finds every pair of consecutive bus cycles in a golden window and reports the
spacing from the first cycle's T4 to the second cycle's T1, keyed by the two
cycles' statuses.  A cycle granted at the first one's T3 eval opens its T1 on
the first one's T4 + 1 (M1: eval -> display -> T1); anything later means the
second request was not visible at that eval.

The split halves of one unaligned access are folded together: they are one
access to the EU, and (M5b) one load of the write-data-pairing latch.  A pair
is tagged `split` when the second cycle's address is the first's + 1 and both
drive the same data.
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import timed_gate                      # noqa: E402


def cycles(rows):
    """-> [(t1_row, t4_row, busstat, addr, data)] for the window's bus cycles."""
    out = []
    for i, r in enumerate(rows):
        if r[8] == "T1":
            t4 = i + 3
            if t4 >= len(rows):
                continue
            out.append((i, t4, r[7], r[1] & 0xFFFFF,
                        rows[i + 1][6] if i + 1 < len(rows) else None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(timed_gate.V01))
    ap.add_argument("--forms", default="all")
    ap.add_argument("--pair", default="MEMW>MEMW")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    want = tuple(args.pair.split(">"))
    per = defaultdict(Counter)
    for name, path in timed_gate.form_files(Path(args.suite), args.forms):
        for c in json.load(gzip.open(path)):
            cy = cycles(c["cycles"])
            for a, b in zip(cy, cy[1:]):
                if (a[2], b[2]) != want:
                    continue
                split = (b[3] == a[3] + 1 and b[4] == a[4])
                per[name][("split" if split else "chain", b[0] - a[1])] += 1
    for name in sorted(per):
        tot = sum(per[name].values())
        print("%-8s n=%-6d %s" % (name, tot, ", ".join(
            "%s T4%+d" % (k, d) for (k, d), n in per[name].most_common(args.top)
        ) if tot else ""))
        print("%-8s          %s" % ("", ", ".join(
            "%s T4%+d x%d" % (k, d, n)
            for (k, d), n in per[name].most_common(args.top))))


if __name__ == "__main__":
    sys.exit(main())
