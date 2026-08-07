#!/usr/bin/env python3
"""Replay retained case250 wait planes against the current RTL."""

import argparse
from collections import Counter
import glob
import json
from pathlib import Path

from check_seq import compose, run_tb
from gen_seq import generate
from biu_case165_ins_split_write_factorial import wait_vector
from biu_case249_new_ins_factorial import CASES, resolve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path,
                    default=Path("sw/case253_rtl_ins_deadline.json"))
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("--seeds", default="")
    ap.add_argument("--roles", default="")
    args = ap.parse_args()
    paths = args.inputs or sorted(glob.glob("sw/case250_fz*_factorial.json"))
    by_seed = {}
    selected_seeds = {int(x) for x in args.seeds.split(",") if x}
    selected_roles = {x for x in args.roles.split(",") if x}
    for path in paths:
        for record in json.load(open(path))["records"]:
            if selected_seeds and record["seed"] not in selected_seeds:
                continue
            if selected_roles and record["role"] not in selected_roles:
                continue
            by_seed.setdefault(record["seed"], []).append(record)
    exts = tuple(x for x in Path("sw/case31_all_exts.txt").read_text()
                 .strip().split(",") if x)
    details = []
    for seed, records in sorted(by_seed.items()):
        image, _ = compose(generate(f"fz{seed}", exts=exts))
        for record in records:
            vector = wait_vector(CASES[seed]["lfsr"])
            if record["history"] == "B":
                vector[5], vector[6] = vector[6], vector[5]
            vector[record["selected"]] = record["wait"]
            _, writes, resolved = resolve(
                run_tb(image, 4200, wvec=vector), CASES[seed])
            expected = [x["t1"] for x in record["chip_writes"]]
            observed = [x["t1"] for x in writes]
            deltas = [o - e for o, e in zip(observed, expected)]
            details.append({"seed": seed, "history": record["history"],
                            "role": record["role"], "wait": record["wait"],
                            "expected": expected, "observed": observed,
                            "deltas": deltas, "resolved": resolved,
                            "match": expected == observed})
    bad = [x for x in details if not x["match"]]
    result = {"schema": "v30-case253-rtl-ins-deadline-v1",
              "source_files": paths, "records": len(details),
              "write_checks": sum(len(x["expected"]) for x in details),
              "matches": len(details) - len(bad), "mismatches": len(bad),
              "delta_counts": dict(sorted(Counter(
                  d for x in details for d in x["deltas"]).items())),
              "gate": "PASS" if not bad else "FAIL", "bad": bad}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"CASE253_RTL_INS_DEADLINE {result['gate']} "
          f"{result['matches']}/{result['records']} "
          f"writes={result['write_checks']} deltas={result['delta_counts']}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
