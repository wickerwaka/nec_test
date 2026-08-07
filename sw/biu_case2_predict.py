#!/usr/bin/env python3
"""Apply the frozen ledger-cell-2 micro-oracle to one derived probe record."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biu_blackbox_oracle import key  # noqa: E402


def predict(oracle, record):
    got_key = list(key(record))
    role = record.get("role")
    if got_key != oracle["common_key"] or role not in oracle["predictions"]:
        return {"status": "UNSEEN", "key": got_key, "role": role}
    return {
        "status": "PREDICTED",
        "key": got_key,
        "controlled_event": {"consumer_byte_role": role},
        "prediction": oracle["predictions"][role],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle")
    ap.add_argument("record")
    args = ap.parse_args()
    oracle = json.loads(Path(args.oracle).read_text())
    record = json.loads(Path(args.record).read_text())
    result = predict(oracle, record)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PREDICTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
