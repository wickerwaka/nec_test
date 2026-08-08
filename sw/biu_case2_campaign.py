#!/usr/bin/env python3
"""Fresh factorial capture and validation for BIU ledger cell 2.

Selection is certificate-only: pilot outcomes are never used to choose cells.
Every retained validation record must match the already-frozen micro-oracle.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biu_blackbox_oracle import key, normalized_outcome  # noqa: E402
from biu_blackbox_probe import observable_hash, store_raw, transactions  # noqa: E402
from biu_case2_micro_oracle import (COMMON_KEY, PREDICTIONS,  # noqa: E402
                                    V1_HASHES, guard_v1)
from biu_collision_probe import derive  # noqa: E402
from biu_decoder_probe import fixture, pop_events, run  # noqa: E402
from v30run import parse_result  # noqa: E402

# --- fuzz-v2 T12: RETIRED, not broken.  See sw/retired_v1.py. -----------
import retired_v1  # noqa: E402
retired_v1.retire(
    'biu_case2_campaign.py',
    'BIU rebuild campaign (task #34, RETIRED 2026-08-01)',
    'built on biu_decoder_probe.fixture, which is retired',
    None)
# ------------------------------------------------------------------------


WAITS = tuple(range(8)) + (15,)
DIVS = (8, 4)
HISTORIES = ("A", "B")
REPS = 5
PAD_PAIRS = ((3, 2), (9, 8))

DISCOVERY = {
    "modrm": ("read_mov_aw", bytes.fromhex("8b07")),
    "disp8": ("read_mov_aw_disp8", bytes.fromhex("8b4700")),
}
VALIDATION = {
    "modrm": ("read_mov_dw", bytes.fromhex("8b17")),
    "disp8": ("read_mov_dw_disp8", bytes.fromhex("8b5700")),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.loads(json.dumps(value))


def target_key(record):
    return list(key(record)) == COMMON_KEY


def save(path, words, record):
    path.mkdir(parents=True, exist_ok=True)
    store_raw(path / "raw.hex", words)
    (path / "derived.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")


def select_setup(host, root, population, role, name, code, pad, control):
    """Characterize one pre-registered setup, using state but not outcome."""
    image, meta, target = fixture(code, pad, odd=True)
    zeros = [0] * 4096
    base_tag = f"bb_case2_{population}_{role}_p{pad}_base"
    recs, words = run(host, image, base_tag, 8, zeros)
    parse_result(recs, meta)
    txns = transactions(recs)
    final_addr = target + len(code) - 1
    pops = [p for p in pop_events(recs) if p["addr"] == final_addr]
    if len(pops) != 1:
        raise RuntimeError(
            f"{population}/{role}/p{pad}: final-byte pop count {len(pops)}")
    pop_clock = pops[0]["clock"]
    candidates = [
        i for i, txn in enumerate(txns)
        if txn["kind"] == "CODE"
        and txn["addr"] >= target + len(code)
        and -7 <= txn["t4"] - pop_clock <= 0]
    if not candidates:
        raise RuntimeError(
            f"{population}/{role}/p{pad}: no collision fetch candidate")
    selected = candidates[-1]
    prep_idx = next(
        i for i, txn in enumerate(txns)
        if txn["kind"] == "CODE"
        and not (meta["anchor_linear"] <= txn["addr"]
                 < meta["stub_linear"]))
    (root / "selection" / population / role /
     f"p{pad}" / "baseline").mkdir(parents=True, exist_ok=True)
    store_raw(root / "selection" / population / role /
              f"p{pad}" / "baseline" / "raw.hex", words)
    matches = []
    for wait in WAITS:
        zeros = [0] * 4096
        zeros[selected] = wait
        tag = f"bb_case2_sel_{population}_{role}_p{pad}_w{wait}"
        recs, words = run(host, image, tag, 8, zeros)
        parse_result(recs, meta)
        record = derive(
            image, recs, words, zeros, selected, final_addr, tag,
            request_class="read")
        record.update({
            "population": population, "role": role, "form": name,
            "pad": pad, "padding_control": control, "wait": wait,
            "history": "A", "clock_mhz": 4, "request_class": "read",
            "selection_outcome_quarantined": True})
        save(root / "selection" / population / role /
             f"p{pad}" / f"w{wait}", words, record)
        if target_key(record):
            matches.append(wait)
    if not matches:
        raise RuntimeError(
            f"{population}/{role}/p{pad}: no common-key wait")
    return {
        "population": population, "role": role, "form": name,
        "code": code, "pad": pad, "padding_control": control,
        "image": image, "meta": meta, "target": target,
        "final_addr": final_addr, "selected": selected,
        "prep_idx": prep_idx, "matching_waits": matches}


def full_matrix(host, root, setup):
    """Capture waits 0..7+15 under both histories/frequencies/repetitions."""
    target_records = []
    all_records = []
    for wait in WAITS:
        for history in HISTORIES:
            for div in DIVS:
                repetitions = []
                for rep in range(REPS):
                    wvec = [0] * 4096
                    wvec[setup["selected"]] = wait
                    if history == "B":
                        wvec[setup["prep_idx"]] = 1
                    tag = (
                        f"bb_case2_{setup['population']}_{setup['role']}_"
                        f"p{setup['pad']}_w{wait}_{history}_d{div}_r{rep}")
                    recs, words = run(
                        host, setup["image"], tag, div, wvec)
                    parse_result(recs, setup["meta"])
                    record = derive(
                        setup["image"], recs, words, wvec,
                        setup["selected"], setup["final_addr"], tag,
                        request_class="read")
                    record.update({
                        "population": setup["population"],
                        "role": setup["role"], "form": setup["form"],
                        "pad": setup["pad"],
                        "padding_control": setup["padding_control"],
                        "target_final_address": setup["final_addr"],
                        "wait": wait,
                        "request_class": "read",
                        "history": history, "clock_mhz": 32 // div,
                        "rep": rep})
                    save(root / "matrix" / setup["population"] /
                         setup["role"] / f"p{setup['pad']}" / f"w{wait}" /
                         history / f"div{div}" / f"rep{rep}", words, record)
                    repetitions.append(record)
                    all_records.append(record)
                    if target_key(record):
                        target_records.append(record)
                if len({observable_hash_from_record(r)
                        for r in repetitions}) != 1:
                    raise RuntimeError(
                        f"unstable observable trace: {tag}")
    return all_records, target_records


def observable_hash_from_record(record):
    return record["observable_sha256"]


def certificate_projection(record, normalize_padding=False):
    """The complete registered pin-derived state, excluding absolute time."""
    cert = canonical(record["certificate"])
    cert.pop("qs_through_boundary")
    if normalize_padding:
        origin = record["target_final_address"]
        for item in cert["queue"]:
            item["addr"] -= origin
        if cert["next_fetch_address"] is not None:
            cert["next_fetch_address"] -= origin
        if cert["bus"] is not None:
            cert["bus"]["address"] -= origin
        cert["instruction_bytes_consumed"] %= 6
    return {
        "certificate": cert,
        "selected_t4_from_pop": record["selected_t4_from_pop"],
        "predecessor": record.get("predecessor", "CODE"),
    }


def certificate_gate(records):
    """Prove role matching exactly and padding/history invariance modulo shift."""
    exact_groups = {}
    normalized = {}
    for record in records:
        group = (
            record["population"], record["padding_control"],
            record["history"], record["clock_mhz"], record["rep"])
        exact_groups.setdefault(group, {})[record["role"]] = \
            certificate_projection(record)
        nuisance = (
            record["population"], record["role"],
            record["history"], record["clock_mhz"], record["rep"])
        normalized.setdefault(nuisance, set()).add(json.dumps(
            certificate_projection(record, normalize_padding=True),
            sort_keys=True))
    bad_exact = [
        {"group": list(group), "roles": roles}
        for group, roles in exact_groups.items()
        if set(roles) != {"modrm", "disp8"}
        or roles["modrm"] != roles["disp8"]]
    bad_padding = [
        {"group": list(group), "certificates": sorted(values)}
        for group, values in normalized.items() if len(values) != 1]
    return {
        "gate": "PASS" if not bad_exact and not bad_padding else "FAIL",
        "exact_role_groups": len(exact_groups),
        "bad_exact_role_groups": bad_exact,
        "bad_padding_groups": bad_padding,
    }


def validate_target(records, oracle, population):
    counts = {
        "records": 0, "unseen_keys": 0, "action_mismatches": 0,
        "t1_mismatches": 0, "address_width_mismatches": 0,
        "qs_mismatches": 0}
    details = []
    for record in records:
        counts["records"] += 1
        role = record["role"]
        if not target_key(record) or role not in oracle["predictions"]:
            counts["unseen_keys"] += 1
            continue
        got = canonical(list(normalized_outcome(record)))
        want = oracle["predictions"][role]
        mismatch = []
        if got[0] != want[0]:
            counts["action_mismatches"] += 1
            mismatch.append("action")
        if got[1] != want[1]:
            counts["t1_mismatches"] += 1
            mismatch.append("t1")
        if got[2:4] != want[2:4]:
            counts["address_width_mismatches"] += 1
            mismatch.append("address_width")
        if got[4] != want[4]:
            counts["qs_mismatches"] += 1
            mismatch.append("qs")
        if mismatch:
            details.append({
                "population": population, "role": role,
                "form": record["form"], "pad": record["pad"],
                "wait": record["wait"], "history": record["history"],
                "clock_mhz": record["clock_mhz"], "rep": record["rep"],
                "mismatch": mismatch, "want": want, "got": got})
    counts["gate"] = "PASS" if all(
        counts[name] == 0 for name in (
            "unseen_keys", "action_mismatches", "t1_mismatches",
            "address_width_mismatches", "qs_mismatches")) \
        and counts["records"] > 0 else "FAIL"
    return counts, details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle")
    ap.add_argument("output")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not args.live:
        ap.error("--live is required")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    before = guard_v1()
    oracle = json.loads(Path(args.oracle).read_text())
    if oracle.get("status") != "FROZEN_BEFORE_FRESH_FACTORIAL_CAPTURE":
        raise RuntimeError("micro-oracle was not frozen prospectively")
    if oracle["common_key"] != COMMON_KEY \
            or oracle["predictions"] != PREDICTIONS:
        raise RuntimeError("micro-oracle contents differ from registered rule")
    oracle_hash = sha256(args.oracle)

    setups = []
    for population, forms in (
            ("discovery", DISCOVERY), ("validation", VALIDATION)):
        for control, (modrm_pad, disp8_pad) in enumerate(PAD_PAIRS):
            for role, pad in (("modrm", modrm_pad), ("disp8", disp8_pad)):
                name, code = forms[role]
                setups.append(select_setup(
                    args.host, root, population, role, name, code,
                    pad, control))

    manifests = []
    populations = {"discovery": [], "validation": []}
    for setup in setups:
        all_records, target_records = full_matrix(args.host, root, setup)
        populations[setup["population"]].extend(target_records)
        manifests.append({
            "population": setup["population"], "role": setup["role"],
            "form": setup["form"], "pad": setup["pad"],
            "padding_control": setup["padding_control"],
            "selected_bus_index": setup["selected"],
            "target_address": setup["target"],
            "target_final_address": setup["final_addr"],
            "matching_waits": setup["matching_waits"],
            "matrix_records": len(all_records),
            "target_records": len(target_records)})

    discovery_counts, discovery_details = validate_target(
        populations["discovery"], oracle, "discovery")
    validation_counts, validation_details = validate_target(
        populations["validation"], oracle, "validation")
    discovery_certificate = certificate_gate(populations["discovery"])
    validation_certificate = certificate_gate(populations["validation"])
    after = guard_v1()
    result = {
        "schema": "v30-biu-case2-prospective-validation-v1",
        "micro_oracle": args.oracle,
        "micro_oracle_sha256": oracle_hash,
        "frozen_v1_sha256_before": before,
        "frozen_v1_sha256_after": after,
        "waits": list(WAITS), "histories": list(HISTORIES),
        "clock_mhz": [4, 8], "repetitions": REPS,
        "setups": manifests,
        "discovery": discovery_counts,
        "validation": validation_counts,
        "discovery_certificate": discovery_certificate,
        "validation_certificate": validation_certificate,
        "mismatches": discovery_details + validation_details,
        "exact_commands": [
            f"python3 sw/biu_case2_micro_oracle.py {args.oracle}",
            f"python3 sw/biu_case2_campaign.py {args.oracle} "
            f"{args.output} --host {args.host} --live"],
        "gate": "PASS" if discovery_counts["gate"] == "PASS"
        and validation_counts["gate"] == "PASS"
        and discovery_certificate["gate"] == "PASS"
        and validation_certificate["gate"] == "PASS" else "FAIL"}
    (root / "manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("CASE2_PROSPECTIVE_GATE "
          f"{result['gate']} discovery={discovery_counts} "
          f"validation={validation_counts}")
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
