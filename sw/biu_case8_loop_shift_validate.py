#!/usr/bin/env python3
"""Validate current RTL against the pre-RTL E0-E3 shifted pilot table."""

import json
import sys
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

from biu_case8_loop_collision_hw import PATCH, WAITS, derive, vector  # noqa: E402
from check_seq import compose, run_tb  # noqa: E402
from gen_seq import generate  # noqa: E402

PILOT = (SW / "testdata/biu_blackbox/"
         "case8-loop-collision-pilot-v2/summary.json")


def normalized(outcome):
    return {k: v for k, v in outcome.items() if k != "flush_e_clock"}


def main():
    source = json.loads(PILOT.read_text())
    expected = defaultdict(set)
    for record in source["records_derived"]:
        expected[(record["opcode"], record["wait"])].add(
            json.dumps(normalized(record["outcome"]), sort_keys=True))
    conflicts = {k: v for k, v in expected.items() if len(v) != 1}
    if conflicts:
        raise RuntimeError(f"pilot conflicts: {conflicts}")

    base, _ = compose(generate("fz62", exts=()))
    failures = []
    for opcode in (0xE0, 0xE1, 0xE2, 0xE3):
        image = bytearray(base)
        image[PATCH] = opcode
        for wait in WAITS:
            exp = next(iter(expected[(opcode, wait)]))
            for history in ("A", "B"):
                observed = normalized(derive(run_tb(
                    bytes(image), 4200, waits=0,
                    wvec=vector(wait, history))))
                if json.dumps(observed, sort_keys=True) != exp:
                    failures.append({
                        "opcode": opcode, "wait": wait, "history": history,
                        "expected": json.loads(exp), "observed": observed,
                    })
    print(f"CASE8_LOOP_SHIFTED_RTL_GATE "
          f"{'PASS' if not failures else 'FAIL'} records=72 "
          f"mismatches={len(failures)}")
    for failure in failures:
        print(json.dumps(failure, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
