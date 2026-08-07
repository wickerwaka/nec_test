#!/usr/bin/env python3
"""Targeted prospective micro-oracle for BIU mismatch-ledger cell 2.

The rule is intentionally tiny: for one externally reconstructed common state,
consumer byte role predicts the next decision.  It contains no form, padding,
seed, ordinal, or preparation-history fields.
"""

import argparse
import hashlib
import json
from pathlib import Path

V1_ORACLE = Path("sw/testdata/biu_blackbox/chip-oracle-v1.json")
V1_VALIDATION = Path(
    "sw/testdata/biu_blackbox/chip-oracle-v1.validation.json")
V1_HASHES = {
    str(V1_ORACLE):
        "23c0313ddf67510b12b0de1b513ef6e9f6a3fec9482b61b90110a98c0f3fc9be",
    str(V1_VALIDATION):
        "cdc551359d4aa4ad0222be754aa7bd883e9420409d86c66b2dde92a9ad70449d",
}

COMMON_KEY = [
    2, 0, "IDLE", 0, "read", "CODE", -3, "S", 0, 3,
]

PREDICTIONS = {
    "modrm": [
        "CODE", 2, ["selected_delta", 2], 16, [],
    ],
    "disp8": [
        "MEMR", 3, ["absolute", 8192], 16, [],
    ],
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard_v1():
    got = {path: sha256(Path(path)) for path in V1_HASHES}
    if got != V1_HASHES:
        raise RuntimeError(
            f"frozen v1 artifact changed: got={got} want={V1_HASHES}")
    return got


def freeze(output):
    hashes = guard_v1()
    obj = {
        "schema": "v30-biu-case2-micro-oracle-v1",
        "status": "FROZEN_BEFORE_FRESH_FACTORIAL_CAPTURE",
        "target": "oracle mismatch ledger cell 2",
        "common_key": COMMON_KEY,
        "causal_variable": "consumer_byte_role",
        "allowed_roles": sorted(PREDICTIONS),
        "predictions": PREDICTIONS,
        "forbidden_variables": [
            "form", "padding", "seed", "structural_ordinal",
            "preparation_history", "exact_history_fingerprint"],
        "frozen_v1_sha256": hashes,
        "acceptance": {
            "unseen_keys": 0, "action_mismatches": 0,
            "t1_mismatches": 0, "address_width_mismatches": 0,
            "qs_mismatches": 0},
    }
    Path(output).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    print(f"CASE2_MICRO_ORACLE_FROZEN {output}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    args = ap.parse_args()
    freeze(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
