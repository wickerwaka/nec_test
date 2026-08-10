#!/usr/bin/env python3
"""fz2_leafdiff -- LEAF-BY-LEAF DIFF OF TWO JSON RECORDS.

The FLASH #14 brief asks for `fz2_w1 bars` to be **leaf-diffed** rather than
eyeballed, so that a bar which moved cannot hide inside a bar record that is
printed truncated to 130 characters.  Every scalar leaf is addressed by its
full path and compared; a path present on one side only is reported as such.

Paths that carry a timestamp or a run identity are excluded by default (they
move by construction and say nothing), and **the exclusion list is printed with
the diff** so it can never quietly grow.

    python3 sw/fz2_leafdiff.py A.json B.json [--all] [--prefix bars]
"""
import argparse
import json
import sys

# Leaves that move by construction on any re-run.  PRINTED with every diff.
NOISE = ("ts", "started", "finished", "seconds", "board_seconds",
         "gen_git", "tree_dirty", "git", "git_describe", "sof_path",
         "flash_ts", "flash_git", "receipt_id", "capture_sha256", "sha256",
         "rows_sha256", "host")


def leaves(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{path}[{i}]")
    else:
        yield path, o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--all", action="store_true",
                    help="do not suppress the noise leaves")
    ap.add_argument("--prefix", default="",
                    help="only paths starting with /<prefix>")
    x = ap.parse_args()
    A = dict(leaves(json.load(open(x.a))))
    B = dict(leaves(json.load(open(x.b))))

    def keep(p):
        if x.prefix and not p.startswith("/" + x.prefix):
            return False
        if x.all:
            return True
        return p.rsplit("/", 1)[-1].split("[")[0] not in NOISE

    ka = {p for p in A if keep(p)}
    kb = {p for p in B if keep(p)}
    only_a, only_b = sorted(ka - kb), sorted(kb - ka)
    moved = sorted(p for p in ka & kb if A[p] != B[p])

    print(f"  A {x.a}\n  B {x.b}")
    if not x.all:
        print(f"  suppressed leaf names (move by construction): {', '.join(NOISE)}")
    print(f"  leaves compared {len(ka & kb)}   "
          f"A-only {len(only_a)}   B-only {len(only_b)}   MOVED {len(moved)}")
    for p in only_a:
        print(f"    A-ONLY  {p} = {A[p]!r}")
    for p in only_b:
        print(f"    B-ONLY  {p} = {B[p]!r}")
    for p in moved:
        print(f"    MOVED   {p}\n              A={A[p]!r}\n              B={B[p]!r}")
    print(f"  {'IDENTICAL' if not (only_a or only_b or moved) else 'DIFFERS'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
