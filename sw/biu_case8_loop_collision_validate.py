#!/usr/bin/env python3
"""Validate current RTL against the frozen E2/E3 loop-collision oracle."""

import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

from biu_case8_loop_collision_hw import (  # noqa: E402
    PATCH, WAITS, derive, vector,
)
from check_seq import compose, run_tb  # noqa: E402
from gen_seq import generate  # noqa: E402

OPS = (0xE2, 0xE3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--oracle",
        default=str(SW / "testdata/biu_blackbox/"
                    "case8-loop-collision-oracle-v1.json"))
    args = ap.parse_args()
    oracle = json.loads(Path(args.oracle).read_text())
    if oracle.get("status") != "FROZEN_BEFORE_RTL":
        raise RuntimeError("oracle was not frozen before RTL")

    base, _ = compose(generate("fz62", exts=()))
    failures = []
    keys = tuple(oracle["table"]["w0"])
    for opcode in OPS:
        image = bytearray(base)
        image[PATCH] = opcode
        for wait in WAITS:
            expected = oracle["table"][f"w{wait}"]
            for history in ("A", "B"):
                outcome = derive(run_tb(
                    bytes(image), 4200, waits=0,
                    wvec=vector(wait, history)))
                observed = {k: outcome[k] for k in keys}
                if observed != expected:
                    failures.append({
                        "opcode": opcode, "wait": wait, "history": history,
                        "expected": expected, "observed": observed,
                    })
    print(f"CASE8_LOOP_COLLISION_RTL_GATE "
          f"{'PASS' if not failures else 'FAIL'} "
          f"records={len(OPS) * len(WAITS) * 2} "
          f"mismatches={len(failures)}")
    for failure in failures:
        print(json.dumps(failure, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
