#!/usr/bin/env python3
"""Measure V30 instruction-byte consumption with the CODE producer clamped."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage  # noqa: E402
from analyze_capture import QOPS  # noqa: E402
from biu_blackbox_probe import (ProbeSpec, certify, observable_hash,  # noqa: E402
                                store_raw, transactions)
from v30asm import Assembler  # noqa: E402
from v30run import parse_result, run_image  # noqa: E402

# --- fuzz-v2 T12: RETIRED, not broken.  See sw/retired_v1.py. -----------
import retired_v1  # noqa: E402
retired_v1.retire(
    'biu_decoder_probe.py',
    'BIU rebuild campaign (task #34, RETIRED 2026-08-01)',
    "the shared fixture() composes at 0x0500/0x0501 and then reads meta['stub_linear']; the campaign it served is closed",
    None)
# ------------------------------------------------------------------------


CAP = 4096
REPS = 5

# Raw bytes make displacement width a controlled variable.
FORMS = {
    "nop": bytes.fromhex("90"),
    "lea_nodisp": bytes.fromhex("8d07"),
    "lea_disp8z": bytes.fromhex("8d4700"),
    "lea_disp16z": bytes.fromhex("8d870000"),
    "movr_nodisp": bytes.fromhex("8b07"),
    "movr_disp8z": bytes.fromhex("8b4700"),
    "movr_disp16z": bytes.fromhex("8b870000"),
    "movw_nodisp": bytes.fromhex("8907"),
    "movw_disp8z": bytes.fromhex("894700"),
    "movw_disp16z": bytes.fromhex("89870000"),
    "rmw_inc": bytes.fromhex("ff07"),
}


def cert_key(cert):
    fields = ("queue", "queue_depth", "next_fetch_address",
              "next_fetch_parity", "bus", "instruction_bytes_consumed",
              "current_qs", "controlled_eu_request")
    return json.dumps({k: cert[k] for k in fields}, sort_keys=True)


def fixture(code, runway_n=0, odd=False, regs=None, ram=None, prefix=b""):
    origin = 0x0501 if odd else 0x0500
    runway = b"\x90" * runway_n
    saturate = b"\x90" * 16 + bytes.fromhex("f7f1")  # DIVU CW
    body = saturate + runway + prefix + code + b"\x90" * 24
    fixture_regs = {"PS": 0, "PC": origin, "BW": 0x2000,
                    "AW": 9, "DW": 0, "CW": 3}
    if regs:
        fixture_regs.update(regs)
    fixture_ram = [(0x2000, 0x34), (0x2001, 0x12)]
    if ram:
        fixture_ram.extend(ram)
    image, meta = testimage.compose(
        regs=fixture_regs, instr=body, ram=fixture_ram)
    return image, meta, origin + len(saturate) + len(runway) + len(prefix)


def run(host, image, tag, div, wvec):
    return run_image(image, host, tag=tag, waits=0, use_core=False,
                     wvec=wvec, div=div, cap=CAP, want_raw=True)


def pop_events(recs):
    """Map each externally reported F/S pop to its queued address/byte tag."""
    txns = transactions(recs)
    timeline = []
    for t in txns:
        if t["kind"] != "CODE":
            continue
        n = 2 if t["word"] else 1
        for off in range(n):
            addr = t["addr"] + off
            lane = 1 if addr & 1 else 0
            byte = None if t["data"] is None else \
                (t["data"] >> (8 * lane)) & 0xff
            timeline.append((t["t4"], 0, "push",
                             {"addr": addr, "byte": byte}))
    for r in recs:
        q = QOPS[r["qs"]]
        if q in ("F", "S"):
            timeline.append((r["idx"], 1, q, None))
        elif q == "E":
            timeline.append((r["idx"], 2, "E", None))
    queue, out = [], []
    for clock, _, op, tag in sorted(timeline, key=lambda x: x[:2]):
        if op == "push":
            queue.append(tag)
        elif op == "E":
            queue.clear()
        else:
            if not queue:
                raise RuntimeError("QS pop from externally empty queue")
            got = queue.pop(0)
            out.append({"clock": clock, "event": op, **got})
    return out


def probe_record(image, recs, words, wvec, selected, target, code, tag):
    txns = transactions(recs)
    t = txns[selected]
    first_tw = t["t4"] - t["tw"]
    spec = ProbeSpec(
        probe_id=tag, image="unused", preparation=tag,
        challenge="decoder consumption", wait_vector=tuple(wvec),
        boundary_clock=first_tw, clock_div=8, repeat_count=5,
        controlled_eu_request="none", capture_records=len(words))
    cert, _ = certify(spec, image, recs)
    pops = [p for p in pop_events(recs)
            if target <= p["addr"] < target + len(code)]
    if [p["addr"] for p in pops] != list(range(target, target + len(code))):
        raise RuntimeError(f"{tag}: target pop tagging failed")
    if t["addr"] < target + len(code):
        raise RuntimeError(f"{tag}: waited fetch overlaps target bytes")
    if not (first_tw <= pops[-1]["clock"] < t["t4"]):
        raise RuntimeError(f"{tag}: producer not clamped at final pop")
    final_pop = pops[-1]["clock"]
    request = next((x for x in txns
                    if x["t1"] > final_pop and x["kind"] != "CODE"), None)
    return {
        "certificate": cert, "selected_bus_index": selected,
        "selected_address": t["addr"], "selected_tw": t["tw"],
        "pops": [{**p, "from_first_pop": p["clock"] - pops[0]["clock"]}
                 for p in pops],
        "first_noncode_request": None if request is None else {
            "kind": request["kind"], "address": request["addr"],
            "t1_clock": request["t1"],
            "from_final_pop": request["t1"] - final_pop},
        "observable_sha256": observable_hash(words),
    }


def save(path, words, record):
    path.mkdir(parents=True, exist_ok=True)
    store_raw(path / "raw.hex", words)
    (path / "derived.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")


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
    summary = {"schema": "v30-biu-decoder-timing-v1", "forms": []}
    for name, code in FORMS.items():
        chosen = None
        zeros = [0] * 4096
        for runway_n in range(0, 25):
            image, meta, target = fixture(code, runway_n)
            base_recs, _ = run(
                args.host, image, f"bb_dec_{name}_base_p{runway_n}",
                8, zeros)
            base_txns = transactions(base_recs)
            # Candidate fetch already contains bytes beyond the target;
            # stretching it must cover every target-byte pop.
            candidates = [i for i, t in enumerate(base_txns)
                          if t["kind"] == "CODE"
                          and target <= t["addr"] < meta["stub_linear"]]
            for selected in candidates:
                wvec = [0] * 4096
                wvec[selected] = 15
                recs, words = run(
                    args.host, image,
                    f"bb_dec_{name}_p{runway_n}_select{selected}", 8, wvec)
                try:
                    probe_record(image, recs, words, wvec, selected,
                                 target, code, name)
                except RuntimeError:
                    continue
                chosen = selected
                break
            if chosen is not None:
                break
        if chosen is None:
            raise RuntimeError(f"{name}: no producer-clamp candidate")

        prep_idx = next(i for i, t in enumerate(base_txns)
                        if t["kind"] == "CODE"
                        and not (meta["anchor_linear"] <= t["addr"]
                                 < meta["stub_linear"]))
        form = {"name": name, "bytes": code.hex(),
                "runway_bytes": runway_n, "runs": []}
        history_keys = {}
        for history in ("A", "B"):
            for div in (8, 4):
                records = []
                for rep in range(REPS):
                    wvec = [0] * 4096
                    wvec[chosen] = 15
                    if history == "B":
                        wvec[prep_idx] = 1
                    tag = f"bb_dec_{name}_{history}_d{div}_r{rep}"
                    recs, words = run(args.host, image, tag, div, wvec)
                    parse_result(recs, meta)
                    record = probe_record(image, recs, words, wvec, chosen,
                                          target, code, tag)
                    save(root / name / history / f"div{div}" / f"rep{rep}",
                         words, record)
                    records.append(record)
                if len({r["observable_sha256"] for r in records}) != 1:
                    raise RuntimeError(f"{name}/{history}/div{div}: unstable")
                keys = {cert_key(r["certificate"]) for r in records}
                timings = {json.dumps(
                    {"pops": r["pops"],
                     "request": r["first_noncode_request"]},
                    sort_keys=True) for r in records}
                if len(keys) != 1 or len(timings) != 1:
                    raise RuntimeError(f"{name}/{history}/div{div}: mismatch")
                history_keys.setdefault(history, set()).update(keys)
                form["runs"].append({
                    "history": history, "clock_mhz": 32 // div,
                    "repetitions": REPS, "certificate": records[0]["certificate"],
                    "pops": records[0]["pops"],
                    "first_noncode_request":
                        records[0]["first_noncode_request"]})
        if history_keys["A"] != history_keys["B"]:
            raise RuntimeError(f"{name}: preparation histories differ")
        # Compare relative timing, not absolute clocks shifted by history B.
        def relative(run_record):
            pops = tuple(p["from_first_pop"] for p in run_record["pops"])
            req = run_record["first_noncode_request"]
            return pops, None if req is None else \
                (req["kind"], req["from_final_pop"])
        if len({relative(r) for r in form["runs"]}) != 1:
            raise RuntimeError(f"{name}: frequency/history timing mismatch")
        summary["forms"].append(form)
        print(f"{name}: pops={[p['from_first_pop'] for p in form['runs'][0]['pops']]}")
    summary["gate"] = "PASS"
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print("DECODER_TIMING_GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
