#!/usr/bin/env python3
"""Freeze the E2/E3 loop collision table from chip-only captures."""

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

    keys = ("taken", "selected_tw", "doomed_532_before_e",
            "redirect_t1_from_e", "preflush_status",
            "preflush_address", "preflush_t4_to_e")
    table = defaultdict(set)
    for record in source["records_derived"]:
        outcome = record["outcome"]
        table[record["wait"]].add(tuple(outcome[k] for k in keys))
    conflicts = {k: sorted(v) for k, v in table.items() if len(v) != 1}
    if conflicts:
        raise RuntimeError(f"E2/E3/history/frequency conflict: {conflicts}")

    obj = {
        "schema": "v30-biu-case8-loop-collision-oracle-v1",
        "status": "FROZEN_BEFORE_RTL",
        "scope": "taken E2/E3 resolution versus one selected CODE wait",
        "source": str(source_path),
        "source_sha256": sha256(source_path),
        "state_rule": (
            "taken E2 and E3 share one externally visible resolution schedule; "
            "the selected wait moves a single doomed CODE opportunity across "
            "the final three-clock hard-reservation boundary"),
        "forbidden_variables": [
            "program seed", "absolute ordinal", "preparation-history fingerprint",
        ],
        "controls": {
            "opcodes": [0xE2, 0xE3], "histories": ["A", "B"],
            "clock_mhz": [4, 8], "repetitions": 5,
            "waits": source["waits"],
        },
        "table": {
            f"w{wait}": dict(zip(keys, next(iter(values))))
            for wait, values in sorted(table.items())
        },
    }
    output = Path(args.output)
    output.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    print(f"CASE8_LOOP_COLLISION_ORACLE_FROZEN sha256={sha256(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
