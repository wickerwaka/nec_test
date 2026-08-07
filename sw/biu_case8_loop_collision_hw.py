#!/usr/bin/env python3
"""Chip-only loop/JCXZ collision matrix around the fz62 wait-1 boundary."""

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
SELECTED = 58
WAITS = tuple(range(8)) + (15,)
OPS = (0xE0, 0xE1, 0xE2, 0xE3)
PATCH = 0x52D
TARGET = 0x536


def sha_words(words):
    h = hashlib.sha256()
    for word in words:
        h.update(int(word).to_bytes(8, "little"))
    return h.hexdigest()


def vector(wait, history):
    v = [1] * CAP
    if history == "B":
        v[:40] = [0, 2] * 20
    v[SELECTED] = wait
    return v


def derive(recs):
    acc = accesses(recs)
    redirect = next((x for x in acc
                     if x["bs"] == 4 and x["addr"] == TARGET and
                     340 < x["t1"] < 480), None)
    if redirect is None:
        return {"taken": False}
    es = [i for i, r in enumerate(recs)
          if r["qs"] == 2 and redirect["t1"] - 30 < i < redirect["t1"]]
    if not es:
        return {"taken": False}
    e = es[-1]
    local = [x for x in acc
             if x["bs"] == 4 and 0x52A <= x["addr"] <= 0x53A]
    doomed = [x for x in local
              if x["addr"] == 0x532 and redirect["t1"] - 30 < x["t1"] < e]
    prev = max((x for x in acc if x["t4"] is not None and x["t4"] < e),
               key=lambda x: x["t4"])
    return {
        "taken": True,
        "selected_tw": acc[SELECTED]["tw"],
        "doomed_532_before_e": len(doomed),
        "flush_e_clock": e,
        "redirect_t1_from_e": redirect["t1"] - e,
        "preflush_status": prev["bs"],
        "preflush_address": prev["addr"],
        "preflush_t4_to_e": e - prev["t4"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--divs", default="8,4")
    ap.add_argument("--ops", default="e0,e1,e2,e3")
    args = ap.parse_args()
    if not args.live:
        ap.error("--live is required")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    divs = tuple(int(x, 0) for x in args.divs.split(","))
    ops = tuple(int(x, 16) for x in args.ops.split(","))

    base, _ = compose(generate("fz62", exts=()))
    if base[PATCH] != 0xE3:
        raise RuntimeError(f"fz62 opcode anchor changed: {base[PATCH]:02x}")
    records = []
    for opcode in ops:
        image = bytearray(base)
        image[PATCH] = opcode
        for wait in WAITS:
            for history in ("A", "B"):
                for div in divs:
                    sigs = []
                    for rep in range(args.reps):
                        tag = (f"case8_loop{opcode:02x}_w{wait}_{history}_"
                               f"d{div}_r{rep}")
                        recs, words = run_image(
                            bytes(image), args.host, tag=tag, waits=0,
                            use_core=False, wvec=vector(wait, history),
                            div=div, cap=CAP, want_raw=True)
                        outcome = derive(recs)
                        record = {
                            "opcode": opcode, "wait": wait,
                            "history": history, "clock_mhz": 32 // div,
                            "rep": rep, "raw_sha256": sha_words(words),
                            "outcome": outcome,
                        }
                        path = (root / "captures" / f"op{opcode:02x}" /
                                f"w{wait}" / history / f"div{div}" / f"r{rep}")
                        path.mkdir(parents=True, exist_ok=True)
                        store_raw(path / "raw.hex", words)
                        (path / "derived.json").write_text(
                            json.dumps(record, indent=2, sort_keys=True) + "\n")
                        records.append(record)
                        sigs.append(json.dumps(
                            {k: v for k, v in outcome.items()
                             if k != "flush_e_clock"}, sort_keys=True))
                    if len(set(sigs)) != 1:
                        raise RuntimeError(
                            f"non-repeatable op{opcode:02x}/w{wait}/"
                            f"{history}/d{div}")
            print(f"op{opcode:02x} w{wait} retained="
                  f"{2 * len(divs) * args.reps}", flush=True)

    summary = {
        "schema": "v30-biu-case8-loop-collision-chip-v1",
        "gate": "PASS", "records": len(records), "selected_access": SELECTED,
        "waits": list(WAITS), "histories": ["A", "B"],
        "clock_mhz": [32 // d for d in divs],
        "repetitions": args.reps, "records_derived": records,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"CASE8_LOOP_COLLISION_CHIP_GATE PASS records={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
