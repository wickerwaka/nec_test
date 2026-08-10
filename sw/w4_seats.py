#!/usr/bin/env python3
"""wave-4 seat/non-mover extractor -- reads an `fz2_replay --out` report and
prints the per-seed `bad_rows` / `first_bad_row` for a named seat list, plus the
whole-population LOST/GAINED/EARLIER deltas between two reports.

This is a MEASUREMENT tool, not a gate.  It asserts nothing; every number it
prints is read out of the two reports it is handed.
"""
import argparse
import json
import sys
from pathlib import Path

SEATS = {
    "p5": ["fz2e/520062", "fz2e/528008", "fz2e/532012", "fz2e/533028"],
    "p4": ["fz2c/410028", "fz2e/520066", "fz2e/527055", "fz2e/528030"],
    "p3": ["fz2c/406073", "fz2e/518044"],
    "p3c2": ["fz2c/404071", "fz2e/514044", "fz2e/516001"],
    "s641": ["fz2c/406063", "fz2c/410047", "fz2e/518053", "fz2e/535027"],
    "c2a": ["fz2c/405002", "fz2c/405013", "fz2c/405072", "fz2e/512056"],
    "d3other": ["fz2c/407036", "fz2e/520013", "fz2e/521016", "fz2e/527008"],
    "sharp": ["fz2c/404040"],
}


def load(path):
    d = json.loads(Path(path).read_text())
    rows = d["rows"] if isinstance(d, dict) and "rows" in d else d
    return {r["seed"]: r for r in rows}


def bad(r):
    return r["sys"].get("bad")


def first(r):
    return r["sys"].get("first")


def cell(r):
    if r is None:
        return "ABSENT"
    return "bad=%-5s first=%-5s  (fabric bad=%-5s first=%-5s)" % (
        bad(r), first(r), r.get("fabric_bad"), r.get("fabric_first"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--after")
    ap.add_argument("--groups", default="p5,p4,p3,p3c2,s641,c2a,d3other,sharp")
    a = ap.parse_args()

    b = load(a.base)
    f = load(a.after) if a.after else None

    for g in a.groups.split(","):
        print("== %s ==" % g)
        for s in SEATS[g]:
            if f is None:
                print("   %-14s %s" % (s, cell(b.get(s))))
            else:
                print("   %-14s BEFORE %s   AFTER %s"
                      % (s, cell(b.get(s)), cell(f.get(s))))

    if f is None:
        print("\npopulation: %d seeds in base" % len(b))
        return 0

    common = sorted(set(b) & set(f))
    lost = [s for s in common if bad(b[s]) == 0 and (bad(f[s]) or 0) != 0]
    gained = [s for s in common if (bad(b[s]) or 0) != 0 and bad(f[s]) == 0]
    earlier = []
    for s in common:
        bb, ff = first(b[s]), first(f[s])
        if bb is not None and ff is not None and ff < bb:
            earlier.append((s, bb, ff))
    moved = [s for s in common
             if bad(b[s]) != bad(f[s]) or first(b[s]) != first(f[s])]

    print("\npopulation   base %d / after %d / common %d" % (len(b), len(f), len(common)))
    print("GAINED  %d  %s" % (len(gained), gained))
    print("LOST    %d  %s" % (len(lost), lost))
    print("EARLIER %d  %s" % (len(earlier), earlier))
    print("MOVED AT ALL %d  %s" % (len(moved), moved))
    only_b = sorted(set(b) - set(f))
    only_f = sorted(set(f) - set(b))
    if only_b or only_f:
        print("ASYMMETRIC POPULATION  base-only %s  after-only %s" % (only_b, only_f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
