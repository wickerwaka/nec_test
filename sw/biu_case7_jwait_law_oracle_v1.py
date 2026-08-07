#!/usr/bin/env python3
"""Freeze the final-JWAIT versus class-5 CODE-resume decision table."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("output")
    args = ap.parse_args()
    source_path = Path(args.source)
    source = json.loads(source_path.read_text())
    if source.get("gate") != "PASS":
        raise RuntimeError("source gate is not PASS")

    table = defaultdict(set)
    for record in source["records_derived"]:
        outcome = record["outcome"]
        table[record["wait"]].add((
            outcome["target_fetches_before_continue"],
            outcome["redirect_address"],
            outcome["redirect_t1_from_e"],
        ))
    conflicts = {k: sorted(v) for k, v in table.items() if len(v) != 1}
    if conflicts:
        raise RuntimeError(f"condition-family conflict: {conflicts}")

    obj = {
        "schema": "v30-biu-case7-jwait-law-oracle-v1",
        "status": "FROZEN_BEFORE_RTL",
        "scope": (
            "taken Jcc final hard reservation colliding with a scheduled "
            "class-5 CODE resume"),
        "source": str(source_path),
        "source_sha256": sha256(source_path),
        "state_rule": (
            "a scheduled CODE resume yields when Jcc is in its final "
            "not-ready reservation clock; earlier JWAIT clocks do not block"),
        "forbidden_variables": [
            "condition opcode", "branch displacement", "program seed",
            "absolute ordinal", "preparation-history fingerprint",
        ],
        "controls": {
            "condition_opcodes": [0x70, 0x75, 0x79, 0x7B],
            "histories": ["A", "B"], "clock_mhz": [4, 8],
            "repetitions": 5, "waits": source["waits"],
        },
        "table": {
            f"w{wait}": {
                "target_fetches_before_continue": next(iter(values))[0],
                "redirect_address": next(iter(values))[1],
                "redirect_t1_from_e": next(iter(values))[2],
            }
            for wait, values in sorted(table.items())
        },
    }
    output = Path(args.output)
    output.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    print(f"CASE7_JWAIT_LAW_ORACLE_FROZEN sha256={sha256(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
