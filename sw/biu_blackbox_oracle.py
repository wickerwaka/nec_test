#!/usr/bin/env python3
"""Freeze and validate the chip-derived BIU next-decision table.

The oracle key is intentionally small and history-free.  It contains only
externally reconstructed queue/bus state, controlled event class, and the
prospectively nominated six-entry queue-head position.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

TRAINING = (
    "sw/testdata/biu_blackbox/no-request-collision-20260728/summary.json",
    "sw/testdata/biu_blackbox/reservation-collision-20260728/summary.json",
    "sw/testdata/biu_blackbox/string-collision-20260728/summary.json",
    "sw/testdata/biu_blackbox/predecessor-collision-20260728/summary.json",
)


def runf_sat3(record):
    n = 0
    for event in reversed(record["certificate"]["qs_through_boundary"]):
        if event["event"] != "F":
            break
        n += 1
    return min(n, 3)


def current_qs(record):
    c = record["certificate"]
    if "current_qs" in c:
        return c["current_qs"]
    hist = c["qs_through_boundary"]
    return hist[-1]["event"] if hist \
        and hist[-1]["clock"] == record["target_pop_clock"] else None


def key(record):
    c = record["certificate"]
    bus = c["bus"] or {}
    return (
        c["queue_depth"], c["next_fetch_parity"],
        bus.get("kind", "IDLE"), bus.get("t_state", 0),
        record.get("request_class", "none"),
        record.get("predecessor", "CODE"),
        record["selected_t4_from_pop"], current_qs(record),
        runf_sat3(record), c["instruction_bytes_consumed"] % 6,
    )


def normalized_outcome(record):
    out = record["outcome"]
    if out["action"] == "CODE":
        address = ("selected_delta",
                   out["address"] - record["selected_address"])
    else:
        address = ("absolute", out["address"])
    return (
        out["action"], out["clocks_to_t1"], address, out["width"],
        tuple((x["clock_delta"], x["event"])
              for x in out["intervening_qs"]),
    )


def encode_key(value):
    return json.dumps(value, separators=(",", ":"))


def freeze(output):
    table = defaultdict(set)
    counts = defaultdict(int)
    for source in TRAINING:
        data = json.loads(Path(source).read_text())
        if data.get("gate") != "PASS":
            raise RuntimeError(f"training source not passed: {source}")
        for record in data["discovery"]:
            k = key(record)
            table[k].add(normalized_outcome(record))
            counts[k] += 1
    conflicts = {k: v for k, v in table.items() if len(v) != 1}
    if conflicts:
        first = next(iter(conflicts.items()))
        raise RuntimeError(f"oracle key conflict: {first}")
    obj = {
        "schema": "v30-biu-chip-oracle-v1",
        "status": "FROZEN_BEFORE_HELDOUT",
        "training_sources": list(TRAINING),
        "state_variables": [
            "queue_depth", "next_fetch_parity", "bus_kind", "bus_t_state",
            "controlled_request_class", "predecessor_class",
            "selected_fetch_t4_from_boundary", "current_qs",
            "consecutive_F_sat3", "queue_head_mod6"],
        "training_records": sum(counts.values()),
        "table_keys": len(table),
        "repeated_training_records": sum(counts.values()) - len(table),
        "table": {
            encode_key(k): list(next(iter(v))) for k, v in table.items()},
    }
    Path(output).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    print(f"ORACLE_FROZEN keys={len(table)} "
          f"repeats={obj['repeated_training_records']}")


def validate(oracle_path, summaries):
    oracle = json.loads(Path(oracle_path).read_text())
    table = oracle["table"]
    total = unseen = mismatches = 0
    examples = []
    for source in summaries:
        data = json.loads(Path(source).read_text())
        if data.get("gate") != "PASS":
            raise RuntimeError(f"held-out source not passed: {source}")
        for record in data["discovery"]:
            total += 1
            k = encode_key(key(record))
            if k not in table:
                unseen += 1
                if len(examples) < 10:
                    examples.append({"kind": "unseen", "key": json.loads(k)})
                continue
            got = list(normalized_outcome(record))
            # JSON canonicalization turns nested tuples into lists.
            got = json.loads(json.dumps(got))
            if got != table[k]:
                mismatches += 1
                if len(examples) < 10:
                    examples.append(
                        {"kind": "mismatch", "key": json.loads(k),
                         "want": table[k], "got": got})
    result = {
        "schema": "v30-biu-chip-oracle-validation-v1",
        "oracle": str(oracle_path), "heldout_sources": summaries,
        "records": total, "unseen_keys": unseen,
        "mismatches": mismatches, "examples": examples,
        "gate": "PASS" if unseen == 0 and mismatches == 0 else "FAIL"}
    result_path = Path(oracle_path).with_suffix(".validation.json")
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"ORACLE_VALIDATION {result['gate']} records={total} "
          f"unseen={unseen} mismatches={mismatches}")
    return 0 if result["gate"] == "PASS" else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("output")
    v = sub.add_parser("validate")
    v.add_argument("oracle")
    v.add_argument("summaries", nargs="+")
    args = ap.parse_args()
    if args.command == "freeze":
        freeze(args.output)
        return 0
    return validate(args.oracle, args.summaries)


if __name__ == "__main__":
    raise SystemExit(main())
