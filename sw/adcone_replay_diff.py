#!/usr/bin/env python3
"""adcone_replay_diff -- byte-compare two `fz2_replay --out` reports.

THE PIN-IDENTITY LEG OF THE `ucrom -> ad_o` WAVE.  L1 is claimed pin-identical
BY CONSTRUCTION (docs/notes/adcone_l1_prereg_2026-08-13.md §1); this is the
measurement that would refute it.  Each seed's `sys` block is the replayed
run's own per-row result -- `nrows` (how many rows the core produced), `bad`
(non-flicker differing rows against the banked SOCKET capture), `flick`,
`first` (the first differing row index), `fired`, `vecused`.  A pin that moved
on ANY clock of ANY seed moves at least one of those.

    python3 sw/adcone_replay_diff.py <before.json> <after.json>

exit 0 = identical, 1 = a row moved, 2 = the populations are not comparable.
"""
import json
import sys

FIELDS = ("n", "nrows", "bad", "flick", "first", "fired", "vecused")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a = json.load(open(sys.argv[1]))
    b = json.load(open(sys.argv[2]))
    ra = {r["seed"]: r for r in a["rows"]}
    rb = {r["seed"]: r for r in b["rows"]}
    print(f"before {sys.argv[1]}  tb_sys receipt {a['tb_sys_receipt'][:16]}…")
    print(f"after  {sys.argv[2]}  tb_sys receipt {b['tb_sys_receipt'][:16]}…")
    print(f"seeds: {len(ra)} vs {len(rb)}")
    if set(ra) != set(rb):
        print("NOT COMPARABLE: the seed sets differ")
        print("  only-before:", sorted(set(ra) - set(rb))[:10])
        print("  only-after :", sorted(set(rb) - set(ra))[:10])
        return 2

    rows = sum(r["sys"]["nrows"] for r in a["rows"])
    diffs = []
    for s in sorted(ra):
        sa, sb = ra[s]["sys"], rb[s]["sys"]
        moved = [f for f in FIELDS if sa.get(f) != sb.get(f)]
        # the banked columns must not move either -- they are the reference
        for f in ("fabric_bad", "fabric_first", "win", "family"):
            if ra[s].get(f) != rb[s].get(f):
                moved.append(f)
        if moved:
            diffs.append((s, moved, sa, sb))

    print(f"replayed rows compared: {rows:,}")
    print(f"tables block identical: {a['tables'] == b['tables']}")
    if diffs:
        print(f"DIFFERING SEEDS: {len(diffs)}")
        for s, m, sa, sb in diffs[:20]:
            print(f"  {s}  moved={m}")
            print(f"      before {sa}")
            print(f"      after  {sb}")
        return 1
    print(f"IDENTICAL: {len(ra)} seeds, {rows:,} replayed rows, "
          f"every `sys` field and every banked reference field unmoved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
