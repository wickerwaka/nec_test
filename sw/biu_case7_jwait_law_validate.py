#!/usr/bin/env python3
"""Prospectively validate current RTL against the frozen case-7 chip oracle."""

import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

from biu_case7_jwait_law_hw import (  # noqa: E402
    DISCOVERY_OPS, HELDOUT_OPS, WAITS, derive, vector,
)
from check_seq import compose, run_tb  # noqa: E402
from gen_seq import generate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--oracle",
        default=str(SW / "testdata/biu_blackbox/"
                    "case7-jwait-law-oracle-v1.json"))
    args = ap.parse_args()
    oracle = json.loads(Path(args.oracle).read_text())
    if oracle.get("status") != "FROZEN_BEFORE_RTL":
        raise RuntimeError("oracle was not frozen before RTL")

    base, _ = compose(generate("fz85", exts=()))
    failures = []
    records = []
    for role, ops in (("discovery", DISCOVERY_OPS),
                      ("heldout", HELDOUT_OPS)):
        for opcode in ops:
            image = bytearray(base)
            image[0x569] = opcode
            for wait in WAITS:
                expected = oracle["table"][f"w{wait}"]
                for history in ("A", "B"):
                    outcome = derive(run_tb(
                        bytes(image), 4200, waits=0,
                        wvec=vector(wait, history)))
                    observed = {
                        "target_fetches_before_continue":
                            outcome["target_fetches_before_continue"],
                        "redirect_address": outcome["redirect_address"],
                        "redirect_t1_from_e": outcome["redirect_t1_from_e"],
                    }
                    record = {
                        "role": role, "opcode": opcode, "wait": wait,
                        "history": history, "expected": expected,
                        "observed": observed,
                    }
                    records.append(record)
                    if observed != expected:
                        failures.append(record)
        print(f"{role}: {len(ops) * len(WAITS) * 2} RTL probes",
              flush=True)

    print(f"CASE7_JWAIT_LAW_RTL_GATE "
          f"{'PASS' if not failures else 'FAIL'} "
          f"records={len(records)} mismatches={len(failures)}")
    for failure in failures[:20]:
        print(json.dumps(failure, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
