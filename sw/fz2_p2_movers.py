#!/usr/bin/env python3
"""ad-hoc: the still-failing seeds whose replay first_bad moved."""
import json
import sys

B = {r["seed"]: r for r in json.loads(open(sys.argv[1]).read())["rows"]}
A = {r["seed"]: r for r in json.loads(open(sys.argv[2]).read())["rows"]}
for s in sorted(B):
    b, a = (B[s].get("sys") or {}), (A[s].get("sys") or {})
    if a.get("bad") == 0:
        continue
    if b.get("first") != a.get("first"):
        print(f"{s:14s} {B[s]['family'][:32]:32s} first {b.get('first')} -> "
              f"{a.get('first')}   bad {b.get('bad')} -> {a.get('bad')}   "
              f"fabric_first {B[s]['fabric_first']}")
