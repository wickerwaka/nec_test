#!/usr/bin/env python3
"""Reset/prepare/challenge/observe probes for V30 BIU identification.

This is deliberately a socket-only measurement tool.  It derives state only
from CODE completions, QS pins, bus status, READY-derived Tw counts, and
addresses.  It neither imports nor names CPU RTL state.

No command is executed by default.  ``analyze`` works on retained raw captures;
``run`` requires --live and performs one complete reset-per-repetition run
through v30run's explicit wait-vector replay path.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_capture import BUS_STATUS, QOPS, decode_words  # noqa: E402
from v30run import RunError, run_image  # noqa: E402

SCHEMA = "v30-biu-blackbox-v1"
SAFE_DIVS = {4: "8MHz", 8: "4MHz"}
ACTION = {"PASV": "IDLE", "HALT": "IDLE"}


class ProbeError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class ProbeSpec:
    probe_id: str
    image: str
    preparation: str
    challenge: str
    wait_vector: tuple[int, ...]
    boundary_clock: int
    clock_div: int
    repeat_count: int
    controlled_eu_request: str
    capture_records: int = 4096
    setup: dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ProbeSpec":
        obj = json.loads(path.read_text())
        unknown = set(obj) - {f.name for f in dataclasses.fields(cls)}
        if unknown:
            raise ProbeError(f"unknown ProbeSpec field(s): {sorted(unknown)}")
        obj["wait_vector"] = tuple(obj["wait_vector"])
        spec = cls(**obj)
        spec.validate(path.parent)
        return spec

    def validate(self, base: Path) -> None:
        if self.clock_div not in SAFE_DIVS:
            raise ProbeError("clock_div must be 4 (8 MHz) or 8 (4 MHz)")
        if self.repeat_count < 5:
            raise ProbeError("repeat_count must be >=5")
        if not 0 <= self.boundary_clock < self.capture_records:
            raise ProbeError("boundary_clock outside capture")
        if not self.wait_vector or len(self.wait_vector) > 4096:
            raise ProbeError("wait_vector must contain 1..4096 entries")
        if any(type(x) is not int or not 0 <= x <= 255
               for x in self.wait_vector):
            raise ProbeError("wait_vector entries must be byte Tw counts")
        image = (base / self.image).resolve()
        if not image.is_file() or image.stat().st_size != 65536:
            raise ProbeError("image must name a 65536-byte harness image")


def raw_bytes(words: tuple[int, ...] | list[int]) -> bytes:
    return struct.pack(f"<{len(words)}Q", *words)


def capture_hash(words: tuple[int, ...] | list[int]) -> str:
    return hashlib.sha256(raw_bytes(words)).hexdigest()


def observable_hash(words: tuple[int, ...] | list[int]) -> str:
    """Hash only electrically meaningful capture fields.

    Control/status [63:40] is always retained.  AD address is retained at T1;
    AD data/PS is retained at T3/Tw.  Floating AD samples at TI/T2/T4 are kept
    in the raw artifact but cannot be a repeatability gate.
    """
    norm = []
    for word in words:
        t = (word >> 56) & 7
        masked = word & (((1 << 24) - 1) << 40)
        if t == 1:
            masked |= word & ((1 << 20) - 1)
        elif t in (3, 4):
            masked |= word & (((1 << 20) - 1) << 20)
        norm.append(masked)
    return hashlib.sha256(raw_bytes(norm)).hexdigest()


def load_raw(path: Path) -> tuple[int, ...]:
    vals = tuple(int(line.strip(), 16) for line in path.read_text().splitlines()
                 if line.strip())
    if not vals:
        raise ProbeError(f"empty capture: {path}")
    return vals


def store_raw(path: Path, words: tuple[int, ...] | list[int]) -> None:
    path.write_text("".join(f"{word:016x}\n" for word in words))


def transactions(recs: list[dict[str, int]]) -> list[dict[str, Any]]:
    out, cur = [], None
    for r in recs:
        if r["t"] == 1:
            cur = {"t1": r["idx"], "kind": BUS_STATUS[r["bs_early"]],
                   "addr": r["ad_addr"], "word": not r["ube_n"]
                   and not (r["ad_addr"] & 1), "ube_n": r["ube_n"],
                   "data": None, "tw": 0}
        elif cur is not None and r["t"] in (3, 4):
            cur["data"] = r["ad_data"]
            if r["t"] == 4:
                cur["tw"] += 1
        elif cur is not None and r["t"] == 5:
            cur["t4"] = r["idx"]
            out.append(cur)
            cur = None
    return out


def certify(spec: ProbeSpec, image: bytes,
            recs: list[dict[str, int]]) -> tuple[dict[str, Any], dict[str, Any]]:
    txns = transactions(recs)
    before = [t for t in txns if t["t4"] <= spec.boundary_clock]
    observed = [t["tw"] for t in txns]
    requested = list(spec.wait_vector[:len(observed)])
    if observed != requested:
        at = next((i for i, (a, b) in enumerate(zip(observed, requested))
                   if a != b), min(len(observed), len(requested)))
        raise ProbeError(f"Tw replay mismatch at bus access {at}: "
                         f"requested={requested[at:at+1]} "
                         f"observed={observed[at:at+1]}")

    queue: list[dict[str, int]] = []
    consumed = 0
    timeline: list[tuple[int, int, str, dict[str, int] | None]] = []
    for t in before:
        if t["kind"] == "CODE":
            n = 2 if t["word"] else 1
            for off in range(n):
                addr = (t["addr"] + off) & 0xfffff
                lane = 1 if (addr & 1) else 0
                sampled = None if t["data"] is None else \
                    (t["data"] >> (8 * lane)) & 0xff
                tag = {"addr": addr, "byte": sampled,
                       "image_byte": image[addr & 0xffff]}
                timeline.append((t["t4"], 0, "push", tag))
    for r in recs[:spec.boundary_clock + 1]:
        q = QOPS[r["qs"]]
        if q in ("F", "S"):
            timeline.append((r["idx"], 1, "pop", None))
        elif q == "E":
            timeline.append((r["idx"], 2, "flush", None))
    for _, _, op, tag in sorted(timeline, key=lambda event: event[:2]):
        if op == "push":
            queue.append(tag)  # externally tagged CODE completion
        elif op == "flush":
            queue.clear()
        else:
            if not queue:
                raise ProbeError("QS consumed an externally empty queue; "
                                 "calibration/trace boundary is invalid")
            queue.pop(0)
            consumed += 1

    active = next((t for t in txns
                   if t["t1"] <= spec.boundary_clock <= t["t4"]), None)
    last_code = next((t for t in reversed(before) if t["kind"] == "CODE"),
                     None)
    next_fetch = None
    if active is not None and active["kind"] == "CODE" \
            and spec.boundary_clock < active["t4"]:
        # A waited producer has not completed, so the next fetch is the
        # externally visible active CODE transaction itself.
        next_fetch = active["addr"]
    elif last_code:
        next_fetch = (last_code["addr"] + (2 if last_code["word"] else 1)) \
                     & 0xfffff
    qs = [{"clock": r["idx"], "event": QOPS[r["qs"]]}
          for r in recs[:spec.boundary_clock + 1] if QOPS[r["qs"]]]
    cert = {
        "queue": queue, "queue_depth": len(queue),
        "next_fetch_address": next_fetch,
        "next_fetch_parity": None if next_fetch is None else next_fetch & 1,
        "bus": None if active is None else {
            "kind": active["kind"], "t_state": recs[spec.boundary_clock]["t"],
            "address": active["addr"]},
        "instruction_bytes_consumed": consumed,
        "last_code_completion_age": (
            None if last_code is None
            else spec.boundary_clock - last_code["t4"]),
        "current_qs": QOPS[recs[spec.boundary_clock]["qs"]],
        "controlled_eu_request": spec.controlled_eu_request,
        "qs_through_boundary": qs,
    }

    post = next((t for t in txns if t["t1"] > spec.boundary_clock), None)
    if post is None:
        raise ProbeError("no post-boundary bus decision in capture")
    intervening = [{"clock": r["idx"], "event": QOPS[r["qs"]]}
                   for r in recs[spec.boundary_clock + 1:post["t1"] + 1]
                   if QOPS[r["qs"]]]
    outcome = {
        "action": ACTION.get(post["kind"], post["kind"]),
        "clocks_to_t1": post["t1"] - spec.boundary_clock,
        "t1_clock": post["t1"], "address": post["addr"],
        "width": 16 if post["word"] else 8,
        "intervening_qs": intervening,
    }
    return cert, outcome


def derive(spec: ProbeSpec, spec_dir: Path, words: tuple[int, ...]) -> dict[str, Any]:
    if len(words) != spec.capture_records:
        raise ProbeError(f"capture length {len(words)} != "
                         f"capture_records {spec.capture_records}")
    recs = decode_words(words)
    # A transaction reaching the final record means truncation is possible.
    if recs[-1]["t"] not in (0, 5) or recs[-1]["bs_early"] != 7:
        raise ProbeError("capture overflow/truncation guard: final record busy")
    image = ((spec_dir / spec.image).resolve()).read_bytes()
    cert, outcome = certify(spec, image, recs)
    return {"schema": SCHEMA, "probe_id": spec.probe_id,
            "clock": SAFE_DIVS[spec.clock_div],
            "raw_sha256": capture_hash(words),
            "observable_sha256": observable_hash(words),
            "state_certificate": cert, "outcome": outcome}


def stable_gate(records: list[dict[str, Any]]) -> None:
    if len(records) < 5:
        raise ProbeError("fewer than five repetitions")
    hashes = {r["observable_sha256"] for r in records}
    if len(hashes) != 1:
        raise ProbeError("observable traces are not bit-identical: "
                         f"{sorted(hashes)}")


def cmd_analyze(args: argparse.Namespace) -> int:
    sp = Path(args.spec).resolve()
    spec = ProbeSpec.load(sp)
    records = [derive(spec, sp.parent, load_raw(Path(p))) for p in args.capture]
    stable_gate(records)
    print(json.dumps({"schema": SCHEMA, "gate": "PASS",
                      "repetitions": len(records), "record": records[0]},
                     indent=2, sort_keys=True))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not args.live:
        raise ProbeError("live execution is locked; pass --live explicitly")
    sp = Path(args.spec).resolve()
    spec = ProbeSpec.load(sp)
    image = (sp.parent / spec.image).resolve().read_bytes()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    (out / "spec.json").write_text(sp.read_text())
    records = []
    for rep in range(spec.repeat_count):
        recs, words = run_image(
            image, args.host, tag=f"bb_{spec.probe_id}_{rep}",
            waits=0, use_core=False, wvec=spec.wait_vector,
            div=spec.clock_div, cap=spec.capture_records, want_raw=True)
        del recs
        raw = out / f"raw-{rep:02d}.hex"
        store_raw(raw, words)
        record = derive(spec, sp.parent, words)
        (out / f"derived-{rep:02d}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n")
        records.append(record)
    stable_gate(records)
    (out / "gate.json").write_text(json.dumps(
        {"schema": SCHEMA, "gate": "PASS", "repetitions": len(records),
         "raw_sha256": records[0]["raw_sha256"]}, indent=2) + "\n")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="derive and gate retained captures")
    a.add_argument("spec")
    a.add_argument("capture", nargs="+")
    a.set_defaults(func=cmd_analyze)
    r = sub.add_parser("run", help="perform socket-only reset-per-probe runs")
    r.add_argument("spec")
    r.add_argument("output")
    r.add_argument("--host", default="root@mister-nec")
    r.add_argument("--live", action="store_true")
    r.set_defaults(func=cmd_run)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (ProbeError, RunError, OSError, ValueError) as exc:
        print(f"PROBE FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
