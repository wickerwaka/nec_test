#!/usr/bin/env python3
"""Scan an emitted suite for 64K-mirror footprint collisions and emit the
re-emission worklist: an index-map JSON {op: [output-idx, ...]} for the
index-targeted forms (feed to `emit_suite.py reemit --indices-file`), and a
separate list of forms that must be FULLY re-emitted (idx != seed because the
running emission logged a skip-to-next reroll for them).

  python3 sw/collision_scan.py [--dir tests/v30/v0.2] [--out reemit_map.json]

The collision criterion matches emit_suite._mirror_collision / check_core.mirror_
collision exactly: two DISTINCT 20-bit footprint addresses that alias mod-64K.
Footprint = window CODE/MEMR/MEMW bus addresses + loaded + written ram.
"""
import sys, gzip, json, glob, os, argparse, re


def collides(t):
    a = set()
    for row in t["cycles"]:
        if row[7] in ("CODE", "MEMR", "MEMW"):
            a.add(row[1] & 0xFFFFF)
    for x, _ in t["initial"]["ram"]:
        a.add(x & 0xFFFFF)
    for x, _ in t["final"]["ram"]:
        a.add(x & 0xFFFFF)
    return len({x & 0xFFFF for x in a}) < len(a)


def rerolled_forms(suite_dir):
    """Forms with a logged skip-to-next reroll -> idx != seed -> full re-emit."""
    log = os.path.join(suite_dir, "emit_log.txt")
    forms = set()
    if os.path.exists(log):
        for line in open(log):
            m = re.match(r"^(\S+) case-seed \d+ reroll:", line)
            if m:
                forms.add(m.group(1))
    return forms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="tests/v30/v0.2")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    full = rerolled_forms(a.dir)
    index_map = {}
    tot = coll = 0
    for f in sorted(glob.glob(os.path.join(a.dir, "*.json.gz"))):
        op = os.path.basename(f)[:-len(".json.gz")]
        cases = json.load(gzip.open(f))
        tot += len(cases)
        bad = [t["idx"] for t in cases if collides(t)]
        coll += len(bad)
        if bad and op not in full:
            index_map[op] = bad
    forms_scanned = len(glob.glob(os.path.join(a.dir, "*.json.gz")))
    print(f"scanned {forms_scanned} forms, {tot} cases; {coll} colliding "
          f"({100*coll/max(tot,1):.2f}%)")
    print(f"index-targeted forms: {len(index_map)} "
          f"({sum(len(v) for v in index_map.values())} indices)")
    print(f"FULL re-emit forms (logged reroll -> idx!=seed): {sorted(full)}")
    if a.out:
        json.dump({"index_targeted": index_map, "full_reemit": sorted(full)},
                  open(a.out, "w"), indent=0)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
