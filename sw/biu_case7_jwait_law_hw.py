#!/usr/bin/env python3
"""Chip-only collision matrix: class-5 resume versus final Jcc reservation."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

from biu_blackbox_probe import store_raw  # noqa: E402
from causal_wrand import accesses  # noqa: E402
from check_seq import compose  # noqa: E402
from gen_seq import generate  # noqa: E402
from v30run import run_image  # noqa: E402

CAP = 4096
REPS = 5
SELECTED = 97
WAITS = tuple(range(8)) + (15,)
DISCOVERY_OPS = (0x70, 0x75, 0x79, 0x7B)
HELDOUT_OPS = (0x72, 0x76, 0x7C, 0x7E)


def sha_words(words):
    h = hashlib.sha256()
    for word in words:
        h.update(int(word).to_bytes(8, "little"))
    return h.hexdigest()


def vector(wait, history):
    v = [3] * CAP
    if history == "B":
        v[:40] = [2, 4] * 20
    v[SELECTED] = wait
    return v


def derive(recs):
    acc = accesses(recs)
    local = [x for x in acc
             if x["bs"] == 4 and 0x56A <= x["addr"] <= 0x572]
    seq = [x["addr"] for x in local]
    # Redirect target is 0x56e for every selected taken condition.  Count
    # target fetches before the first 0x570 continuation.
    stop = next((i for i, addr in enumerate(seq) if addr == 0x570), len(seq))
    target_fetches = sum(addr == 0x56E for addr in seq[:stop])
    es = [i for i, r in enumerate(recs) if r["qs"] == 2 and i > 700]
    if not es:
        raise RuntimeError("branch flush E not found")
    e = es[0]
    redirect = next(x for x in local if x["t1"] > e)
    return {
        "selected_tw": next(
            x["tw"] for i, x in enumerate(acc) if i == SELECTED),
        "code_sequence": seq[:8],
        "target_fetches_before_continue": target_fetches,
        "flush_e_clock": e,
        "redirect_address": redirect["addr"],
        "redirect_t1_from_e": redirect["t1"] - e,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--heldout", action="store_true")
    args = ap.parse_args()
    if not args.live:
        ap.error("--live is required")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)

    base, _ = compose(generate("fz85", exts=()))
    ops = HELDOUT_OPS if args.heldout else DISCOVERY_OPS
    records = []
    for opcode in ops:
        image = bytearray(base)
        image[0x569] = opcode
        for wait in WAITS:
            for history in ("A", "B"):
                wvec = vector(wait, history)
                for div in (8, 4):
                    outcomes = []
                    for rep in range(REPS):
                        tag = (f"case7_j{opcode:02x}_w{wait}_{history}_"
                               f"d{div}_r{rep}")
                        recs, words = run_image(
                            bytes(image), args.host, tag=tag, waits=0,
                            use_core=False, wvec=wvec, div=div, cap=CAP,
                            want_raw=True)
                        outcome = derive(recs)
                        record = {
                            "condition_opcode": opcode, "wait": wait,
                            "history": history, "clock_mhz": 32 // div,
                            "rep": rep, "raw_sha256": sha_words(words),
                            "outcome": outcome,
                        }
                        path = (root / "captures" / f"j{opcode:02x}" /
                                f"w{wait}" / history / f"div{div}" / f"r{rep}")
                        path.mkdir(parents=True, exist_ok=True)
                        store_raw(path / "raw.hex", words)
                        (path / "derived.json").write_text(
                            json.dumps(record, indent=2, sort_keys=True) + "\n")
                        records.append(record)
                        normalized = {
                            k: v for k, v in outcome.items()
                            if k != "flush_e_clock"
                        }
                        outcomes.append(json.dumps(normalized, sort_keys=True))
                    if len(set(outcomes)) != 1:
                        raise RuntimeError(
                            f"non-repeatable j{opcode:02x}/w{wait}/"
                            f"{history}/d{div}")
                print(f"j{opcode:02x} w{wait} {history} retained=10",
                      flush=True)

    failures = []
    for opcode in ops:
        for wait in WAITS:
            rs = [r for r in records if r["condition_opcode"] == opcode and
                  r["wait"] == wait and r["rep"] == 0]
            sigs = {
                json.dumps({
                    k: v for k, v in r["outcome"].items()
                    if k != "flush_e_clock"
                }, sort_keys=True)
                for r in rs
            }
            if len(sigs) != 1:
                failures.append({"opcode": opcode, "wait": wait})
    summary = {
        "schema": "v30-biu-case7-jwait-law-chip-v1",
        "gate": "PASS" if not failures else "FAIL",
        "role": "heldout" if args.heldout else "discovery",
        "records": len(records), "repetitions": REPS,
        "waits": list(WAITS), "histories": ["A", "B"],
        "clock_mhz": [4, 8], "control_failures": failures,
        "records_derived": records,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"CASE7_JWAIT_LAW_CHIP_GATE {summary['gate']} "
          f"records={len(records)}")
    return 0 if summary["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
