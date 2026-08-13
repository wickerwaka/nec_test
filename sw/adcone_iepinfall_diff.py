#!/usr/bin/env python3
"""adcone_iepinfall_diff -- compare two `ie_pinfall_cell core` tables cell for
cell.  The table is a LIST of cell records, so a plain `==` on the file says
only that something moved; this says WHICH FIELD of WHICH CELL.

Fields that MUST move across a re-run (timestamps, receipts, wall clock) are
named and excluded; everything else is a measurement and must not.

    python3 sw/adcone_iepinfall_diff.py <before.json> <after.json>
"""
import json
import sys

# fields that are provenance, not measurement
VOLATILE = {"ts", "seconds", "secs", "receipt", "elapsed", "wall"}


def key_of(rec, i):
    for k in ("cell", "id", "name", "key"):
        if isinstance(rec, dict) and k in rec:
            return str(rec[k])
    return f"#{i}"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a = json.load(open(sys.argv[1]))
    b = json.load(open(sys.argv[2]))
    if type(a) is not type(b):
        print("NOT COMPARABLE: different top-level types")
        return 2
    if isinstance(a, dict):
        a = [dict(v, **{"_k": k}) for k, v in sorted(a.items())]
        b = [dict(v, **{"_k": k}) for k, v in sorted(b.items())]
    print(f"cells: {len(a)} vs {len(b)}")
    if len(a) != len(b):
        print("NOT COMPARABLE: cell counts differ")
        return 2
    ka = [key_of(r, i) for i, r in enumerate(a)]
    kb = [key_of(r, i) for i, r in enumerate(b)]
    if ka != kb:
        print("NOT COMPARABLE: cell keys differ")
        return 2
    diffs = []
    volatile_hits = set()
    for i, (ra, rb) in enumerate(zip(a, b)):
        if ra == rb:
            continue
        if not (isinstance(ra, dict) and isinstance(rb, dict)):
            diffs.append((ka[i], "<whole record>", ra, rb))
            continue
        for f in sorted(set(ra) | set(rb)):
            if ra.get(f) != rb.get(f):
                if f in VOLATILE:
                    volatile_hits.add(f)
                    continue
                diffs.append((ka[i], f, ra.get(f), rb.get(f)))
    if volatile_hits:
        print(f"ignored volatile field(s): {sorted(volatile_hits)}")
    if diffs:
        print(f"DIFFERING: {len(diffs)} field(s) over "
              f"{len({d[0] for d in diffs})} cell(s)")
        for k, f, x, y in diffs[:20]:
            print(f"  {k}.{f}: {x!r} -> {y!r}")
        return 1
    print(f"IDENTICAL: {len(a)} cells, every measured field unmoved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
