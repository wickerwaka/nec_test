#!/usr/bin/env python3
"""Prospective V30 BIU one-clock collision sweeps.

Phase 1 maps only the no-EU-request case (NOP).  A post-target CODE fetch whose
zero-wait completion lies within seven clocks before the target pop is moved
across that pop one Tw at a time.  Only pin-derived state and outcomes enter
the table.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biu_blackbox_probe import (ProbeSpec, certify, observable_hash,  # noqa: E402
                                store_raw, transactions)
from biu_decoder_probe import fixture, pop_events, run  # noqa: E402
from v30run import parse_result  # noqa: E402

# --- fuzz-v2 T12: RETIRED, not broken.  See sw/retired_v1.py. -----------
import retired_v1  # noqa: E402
retired_v1.retire(
    'biu_collision_probe.py',
    'BIU rebuild campaign (task #34, RETIRED 2026-08-01)',
    'built on biu_decoder_probe.fixture, which is retired',
    None)
# ------------------------------------------------------------------------


WAITS = tuple(range(8)) + (15,)
CAP = 4096
REPS = 5


def cert_key(cert):
    fields = ("queue", "queue_depth", "next_fetch_address",
              "next_fetch_parity", "bus", "instruction_bytes_consumed",
              "current_qs", "controlled_eu_request")
    return json.dumps({k: cert[k] for k in fields}, sort_keys=True)


def outcome_after(recs, boundary):
    txns = transactions(recs)
    nxt = next((t for t in txns if t["t1"] > boundary), None)
    if nxt is None:
        raise RuntimeError("no post-boundary T1")
    qs = [{"clock_delta": r["idx"] - boundary,
           "event": {1: "F", 2: "E", 3: "S"}[r["qs"]]}
          for r in recs[boundary + 1:nxt["t1"] + 1] if r["qs"]]
    return {"action": "IDLE" if nxt["kind"] in ("PASV", "HALT")
            else nxt["kind"],
            "clocks_to_t1": nxt["t1"] - boundary,
            "address": nxt["addr"], "width": 16 if nxt["word"] else 8,
            "intervening_qs": qs}


def derive(image, recs, words, wvec, selected, target, tag,
           request_class="none"):
    txns = transactions(recs)
    pops = [p for p in pop_events(recs) if p["addr"] == target]
    if len(pops) != 1:
        raise RuntimeError(f"{tag}: target pop count {len(pops)}")
    boundary = pops[0]["clock"]
    if selected >= len(txns) or txns[selected]["kind"] != "CODE":
        raise RuntimeError(f"{tag}: selected bus ordinal changed")
    spec = ProbeSpec(
        probe_id=tag, image="unused", preparation=tag,
        challenge="no-request collision", wait_vector=tuple(wvec),
        boundary_clock=boundary, clock_div=8, repeat_count=5,
        controlled_eu_request=request_class, capture_records=len(words))
    cert, _ = certify(spec, image, recs)
    return {
        "certificate": cert, "outcome": outcome_after(recs, boundary),
        "target_pop_clock": boundary,
        "selected_bus_index": selected,
        "selected_address": txns[selected]["addr"],
        "selected_t4_from_pop": txns[selected]["t4"] - boundary,
        "selected_tw": txns[selected]["tw"],
        "observable_sha256": observable_hash(words)}


def save(path, words, record):
    path.mkdir(parents=True, exist_ok=True)
    store_raw(path / "raw.hex", words)
    (path / "derived.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")


def signature(record):
    out = record["outcome"]
    return (out["action"], out["clocks_to_t1"], out["address"],
            out["width"], json.dumps(out["intervening_qs"], sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not args.live:
        ap.error("--live is required")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    discovery = []
    setups = {}

    for odd in (False, True):
        parity = "odd" if odd else "even"
        for pad in range(25):
            image, meta, target = fixture(b"\x90", pad, odd=odd)
            zeros = [0] * 4096
            recs, _ = run(args.host, image,
                          f"bb_col_{parity}_p{pad}_base", 8, zeros)
            parse_result(recs, meta)
            txns = transactions(recs)
            pops = [p for p in pop_events(recs) if p["addr"] == target]
            if len(pops) != 1:
                raise RuntimeError(f"{parity}/p{pad}: target pop tagging")
            pop_clock = pops[0]["clock"]
            candidates = [
                i for i, t in enumerate(txns)
                if t["kind"] == "CODE"
                and t["addr"] >= target + 1
                and -7 <= t["t4"] - pop_clock <= 0
            ]
            if not candidates:
                continue
            selected = candidates[-1]
            prep_idx = next(
                i for i, t in enumerate(txns)
                if t["kind"] == "CODE"
                and not (meta["anchor_linear"] <= t["addr"]
                         < meta["stub_linear"]))
            setups[(parity, pad)] = {
                "image": image, "meta": meta, "target": target,
                "selected": selected, "prep_idx": prep_idx}
            for wait in WAITS:
                wvec = [0] * 4096
                wvec[selected] = wait
                tag = f"bb_col_{parity}_p{pad}_w{wait}"
                recs, words = run(args.host, image, tag, 8, wvec)
                parse_result(recs, meta)
                record = derive(image, recs, words, wvec,
                                selected, target, tag)
                record.update({"parity": parity, "pad": pad,
                               "wait": wait, "history": "A"})
                save(root / "discovery" / parity / f"p{pad}" / f"w{wait}",
                     words, record)
                discovery.append(record)

    # A transition is an adjacent w0..w7 pair whose actual decision changes.
    by_setup = defaultdict(dict)
    for record in discovery:
        by_setup[(record["parity"], record["pad"])][record["wait"]] = record
    transitions = []
    for setup, byw in by_setup.items():
        for wait in range(7):
            if wait in byw and wait + 1 in byw \
                    and signature(byw[wait]) != signature(byw[wait + 1]):
                transitions.append((setup, wait, wait + 1))
        # wait 15 is a mandatory far-side validation for every setup that has
        # at least one boundary.

    if not transitions:
        raise RuntimeError("no no-request transition boundaries found")
    confirm_cells = set()
    for setup, lo, hi in transitions:
        confirm_cells.update(((*setup, lo), (*setup, hi), (*setup, 15)))

    confirmations = []
    for parity, pad, wait in sorted(confirm_cells):
        setup = setups[(parity, pad)]
        for history in ("A", "B"):
            for div in (8, 4):
                records = []
                for rep in range(REPS):
                    wvec = [0] * 4096
                    wvec[setup["selected"]] = wait
                    if history == "B":
                        wvec[setup["prep_idx"]] = 1
                    tag = (f"bb_col_cf_{parity}_p{pad}_w{wait}_"
                           f"{history}_d{div}_r{rep}")
                    recs, words = run(
                        args.host, setup["image"], tag, div, wvec)
                    parse_result(recs, setup["meta"])
                    record = derive(
                        setup["image"], recs, words, wvec,
                        setup["selected"], setup["target"], tag)
                    save(root / "confirm" / parity / f"p{pad}" / f"w{wait}" /
                         history / f"div{div}" / f"rep{rep}", words, record)
                    records.append(record)
                if len({r["observable_sha256"] for r in records}) != 1 \
                        or len({cert_key(r["certificate"])
                                for r in records}) != 1 \
                        or len({signature(r) for r in records}) != 1:
                    raise RuntimeError(
                        f"confirmation instability {parity}/p{pad}/w{wait}/"
                        f"{history}/div{div}")
                confirmations.append({
                    "parity": parity, "pad": pad, "wait": wait,
                    "history": history, "clock_mhz": 32 // div,
                    "repetitions": REPS,
                    "certificate": records[0]["certificate"],
                    "selected_t4_from_pop":
                        records[0]["selected_t4_from_pop"],
                    "outcome": records[0]["outcome"]})

    # Each exact preparation must be frequency invariant.  Histories need not
    # have equal absolute clocks, but their state/outcome fields must agree.
    grouped = defaultdict(list)
    for c in confirmations:
        grouped[(c["parity"], c["pad"], c["wait"], c["history"])].append(c)
    for key, vals in grouped.items():
        if len({cert_key(v["certificate"]) for v in vals}) != 1 \
                or len({json.dumps(v["outcome"], sort_keys=True)
                        for v in vals}) != 1:
            raise RuntimeError(f"frequency mismatch {key}")
    by_hist = defaultdict(dict)
    for c in confirmations:
        by_hist[(c["parity"], c["pad"], c["wait"],
                 c["clock_mhz"])][c["history"]] = c
    for key, vals in by_hist.items():
        if set(vals) != {"A", "B"} \
                or cert_key(vals["A"]["certificate"]) != \
                cert_key(vals["B"]["certificate"]) \
                or vals["A"]["outcome"] != vals["B"]["outcome"]:
            raise RuntimeError(f"history mismatch {key}")

    depths = sorted({r["certificate"]["queue_depth"] for r in discovery})
    summary = {
        "schema": "v30-biu-no-request-collision-v1",
        "gate": "PASS", "reachable_depths": depths,
        "inapplicable_saturated_depths": [5, 6],
        "transition_count": len(transitions),
        "transitions": [{"parity": p, "pad": d, "wait_lo": lo,
                         "wait_hi": hi}
                        for ((p, d), lo, hi) in transitions],
        "discovery": discovery, "confirmations": confirmations}
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"NO_REQUEST_COLLISION_GATE PASS transitions={len(transitions)} "
          f"depths={depths}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
