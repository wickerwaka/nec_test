#!/usr/bin/env python3
"""Offline completion audit for the prospective BIU ledger-cell-2 campaign."""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_capture import decode_words  # noqa: E402
from biu_blackbox_probe import (capture_hash, load_raw,  # noqa: E402
                                observable_hash)
from biu_case2_campaign import (DIVS, HISTORIES, REPS, WAITS,  # noqa: E402
                                certificate_gate, target_key,
                                validate_target)
from biu_case2_micro_oracle import guard_v1  # noqa: E402

EXPECTED_ORACLE_SHA256 = \
    "6055084cf83da1cdec619611b1ad85640fb42067897eb53253e3fead3fb3d201"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle")
    ap.add_argument("campaign")
    args = ap.parse_args()
    root = Path(args.campaign)
    manifest = json.loads((root / "manifest.json").read_text())
    oracle = json.loads(Path(args.oracle).read_text())
    errors = []
    if manifest["gate"] != "PASS":
        errors.append("campaign manifest gate is not PASS")
    if sha256(args.oracle) != EXPECTED_ORACLE_SHA256:
        errors.append("prospectively frozen micro-oracle hash changed")
    before = guard_v1()

    inventory = []
    records = []
    coverage = defaultdict(int)
    stable = defaultdict(set)
    for raw_path in sorted(root.glob("**/raw.hex")):
        words = load_raw(raw_path)
        recs = decode_words(words)
        rel = str(raw_path.relative_to(root))
        item = {
            "path": rel, "words": len(words),
            "raw_sha256": capture_hash(words),
            "observable_sha256": observable_hash(words),
            "final_t": recs[-1]["t"],
            "final_bus_status": recs[-1]["bs_early"],
        }
        inventory.append(item)
        if len(words) != 4096 or recs[-1]["t"] != 0 \
                or recs[-1]["bs_early"] != 7:
            errors.append(f"capture overflow/incomplete: {rel}")
        derived_path = raw_path.with_name("derived.json")
        if "/matrix/" not in f"/{rel}":
            continue
        if not derived_path.is_file():
            errors.append(f"missing derived record: {rel}")
            continue
        record = json.loads(derived_path.read_text())
        records.append(record)
        if record["observable_sha256"] != item["observable_sha256"]:
            errors.append(f"observable hash mismatch: {rel}")
        if record["selected_tw"] != record["wait"]:
            errors.append(f"selected requested/observed Tw mismatch: {rel}")
        cell = (
            record["population"], record["role"], record["pad"],
            record["wait"], record["history"], record["clock_mhz"],
            record["rep"])
        coverage[cell] += 1
        repeat_cell = cell[:-1]
        stable[repeat_cell].add(item["observable_sha256"])

    expected_cells = set()
    for setup in manifest["setups"]:
        for wait in WAITS:
            for history in HISTORIES:
                for div in DIVS:
                    for rep in range(REPS):
                        expected_cells.add((
                            setup["population"], setup["role"], setup["pad"],
                            wait, history, 32 // div, rep))
    if set(coverage) != expected_cells or any(v != 1 for v in coverage.values()):
        errors.append("matrix factorial coverage is not exact")
    unstable = [list(k) for k, values in stable.items() if len(values) != 1]
    if unstable:
        errors.append(f"non-identical repetitions: {unstable[:4]}")
    history_pairs = defaultdict(dict)
    for cell, values in stable.items():
        population, role, pad, wait, history, clock_mhz = cell
        history_pairs[
            (population, role, pad, wait, clock_mhz)][history] = next(
                iter(values))
    same_histories = [
        list(group) for group, values in history_pairs.items()
        if set(values) != set(HISTORIES)
        or values[HISTORIES[0]] == values[HISTORIES[1]]]
    if same_histories:
        errors.append(
            f"preparation histories not observably distinct: "
            f"{same_histories[:4]}")

    populations = {"discovery": [], "validation": []}
    for record in records:
        if target_key(record):
            populations[record["population"]].append(record)
    gates = {}
    for population in populations:
        outcome, details = validate_target(
            populations[population], oracle, population)
        cert = certificate_gate(populations[population])
        gates[population] = {
            "outcome": outcome, "certificate": cert,
            "mismatch_details": details}
        if outcome["gate"] != "PASS" or cert["gate"] != "PASS":
            errors.append(f"{population} prospective gate failed")

    inventory_digest = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":"))
        .encode()).hexdigest()
    result = {
        "schema": "v30-biu-case2-completion-audit-v1",
        "gate": "PASS" if not errors else "FAIL",
        "errors": errors,
        "campaign_manifest_sha256": sha256(root / "manifest.json"),
        "micro_oracle_sha256": sha256(args.oracle),
        "frozen_v1_sha256": before,
        "matrix_records": len(records),
        "raw_captures": len(inventory),
        "raw_inventory_sha256": inventory_digest,
        "raw_inventory": inventory,
        "factorial": {
            "waits": list(WAITS), "histories": list(HISTORIES),
            "clock_mhz": sorted(32 // d for d in DIVS),
            "repetitions": REPS, "expected_cells": len(expected_cells),
            "observed_cells": len(coverage),
            "requested_observed_tw_gate": "PASS",
            "unstable_repetition_cells": unstable,
            "history_pairs": len(history_pairs),
            "non_distinct_history_pairs": same_histories,
        },
        "prospective_gates": gates,
        "exact_command": (
            f"python3 sw/biu_case2_audit.py {args.oracle} {args.campaign}"),
    }
    (root / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"CASE2_COMPLETION_AUDIT {result['gate']} "
        f"raw={len(inventory)} matrix={len(records)} "
        f"cells={len(coverage)} target="
        f"{sum(len(v) for v in populations.values())}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
