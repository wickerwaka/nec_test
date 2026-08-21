#!/usr/bin/env python3
"""Directed REP-termination-vs-INT race regression.

The cell sweeps one-clock INT placements across both zero-flag repeat
polarities:

  * REPNE SCASB: bytes 0..4 differ, byte 5 matches, bytes 6..11 differ.
  * REPE  SCASB: bytes 0..4 match, byte 5 differs, bytes 6..11 match.

Both arms must stop after byte 5 (IY = DATA+6, CW = 6).  The interrupt
handler increments BP and IRETs.  If C_REP withdraws the completed iteration
before consulting its ZF result, the pushed PC is the prefix and the resumed
scan consumes bytes 6..11 (IY = DATA+12, CW = 0).

The default ``rtl`` command drives the repository's existing bare-v30_core
batch testbench.  It runs 300 delays per arm in one Verilator process and
records the final architectural state, pushed resume IP, INTA-cycle count,
and ISR count.  ``board`` uses the same instruction/data/ISR geometry in a
fuzz-v2 image and explicitly selects the socketed V30; it is intentionally an
opt-in hardware operation.

Examples:
  python3 sw/rep_int_term_race.py rtl --out /tmp/rep-int-pre.json
  python3 sw/rep_int_term_race.py board --delays 41-50,78-87 \
      --out sw/testdata/rep-int-term-race/board.json
"""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import artifact                                      # noqa: E402
import check_core as C                               # noqa: E402
import testimage as ti                               # noqa: E402


PHASES = 300
ANCHOR = 0x0500
HANDLER = 0x0700
DATA = 0x2400
COUNT = 12
TERM_N = 6
STACK = 0x3400
INT_VECTOR = 0xFF
# Long enough to remain pending across the contested C_REP sample, short
# enough to fall before the ISR's IRET.  At the baseline checkout this yields
# the bug report's exact 10-delay window per polarity.
INT_HOLD = 22
MAX_CYCLES = 900
N_FPOPS = 8

ARMS = {
    "repne": {
        "prefix": 0xF2,
        "target": 0x41,
        "data": [0x42] * 5 + [0x41] + [0x42] * 6,
        "terminator": "match",
    },
    "repe": {
        "prefix": 0xF3,
        "target": 0x41,
        "data": [0x41] * 5 + [0x42] + [0x41] * 6,
        "terminator": "mismatch",
    },
}


def _regs(arm, *, names="x86"):
    a = ARMS[arm]
    if names == "x86":
        return {
            "ax": a["target"], "cx": COUNT, "dx": 0, "bx": 0,
            "sp": STACK, "bp": 0, "si": 0, "di": DATA,
            "es": 0, "cs": 0, "ss": 0, "ds": 0,
            "ip": ANCHOR, "flags": ti.normalize_psw(0x0202),
        }
    return {
        "AW": a["target"], "CW": COUNT, "DW": 0, "BW": 0,
        "SP": STACK, "BP": 0, "IX": 0, "IY": DATA,
        "DS1": 0, "PS": ti.CODE_LO >> 4, "SS": 0, "DS0": 0,
        "PC": ti.ANCHOR0 - ti.CODE_LO, "PSW": ti.normalize_psw(0x0202),
    }


def _instruction(arm):
    return bytes([ARMS[arm]["prefix"], 0xAE])  # REP{E,NE} SCASB


def _flat_ram(arm):
    """RAM placements for the backdoor-injected bare-core batch cell."""
    ram = [(ANCHOR + i, b) for i, b in enumerate(_instruction(arm))]
    ram += [(DATA + i, b) for i, b in enumerate(ARMS[arm]["data"])]
    # External vector -> INC BP; IRET.  BP is the independent ISR counter.
    ram += [(4 * INT_VECTOR + 0, HANDLER & 0xFF),
            (4 * INT_VECTOR + 1, HANDLER >> 8),
            (4 * INT_VECTOR + 2, 0),
            (4 * INT_VECTOR + 3, 0),
            (HANDLER + 0, 0x45),
            (HANDLER + 1, 0xCF)]
    return ram


def _write_batch(path, phases, hold):
    cases = [(arm, delay) for arm in ARMS for delay in phases]
    with path.open("w") as f:
        f.write(f"{len(cases):x}\n")
        for idx, (arm, delay) in enumerate(cases):
            r = _regs(arm)
            ram = _flat_ram(arm)
            f.write(f"{idx:x}\n")
            f.write(" ".join(f"{r[k]:04x}" for k in C.REGS) + "\n")
            # Empty injected queue; fetch starts at the prefix.
            f.write(f"0 0 0 0 0 0 0 {r['ip']:04x}\n")
            f.write(f"{len(ram):x}\n")
            for addr, byte in ram:
                f.write(f"{addr & 0xFFFFF:05x} {byte & 0xFF:02x}\n")
            f.write(f"{MAX_CYCLES:x} {N_FPOPS:x}\n")
            # fetch-trigger INT: mode pin addr delay hold pins iord iords_n
            f.write(f"1 0 {ANCHOR:05x} {delay:x} {hold:x} 0 ffff 0\n")
    return cases


def _transactions(recs):
    out = []
    cur = None
    for i, r in enumerate(recs):
        if r["t"] == 1:
            cur = {"row": i, "kind": C.BUS_STR[r["bs_early"]],
                   "addr": r["ad_addr"], "data": None}
        elif r["t"] in (3, 4) and cur is not None:
            cur["data"] = r["ad_data"]
        elif r["t"] == 5 and cur is not None:
            out.append(cur)
            cur = None
    return out


def _score(arm, delay, final, recs):
    tx = _transactions(recs)
    inta = [t for t in tx if t["kind"] == "INTA"]
    memw = [t for t in tx if t["kind"] == "MEMW"]
    isr_count = final["bp"]
    pushed_ip = memw[2]["data"] if isr_count and len(memw) >= 3 else None
    got = {"di": final["di"], "cx": final["cx"]}
    want = {"di": DATA + TERM_N, "cx": COUNT - TERM_N}
    overrun = isr_count == 1 and got != want
    return {
        "arm": arm, "delay": delay, "terminator": ARMS[arm]["terminator"],
        "di": final["di"], "cx": final["cx"], "bp": final["bp"],
        "pushed_ip": pushed_ip, "inta_cycles": len(inta),
        "interrupt_serviced": isr_count == 1,
        "overrun": overrun,
        "pass": not overrun and (not isr_count or got == want),
    }


def _parse_delays(text):
    if not text:
        return list(range(PHASES))
    out = set()
    for part in text.split(","):
        p = part.strip()
        if not p:
            continue
        if "-" in p:
            lo, hi = (int(x, 0) for x in p.split("-", 1))
            out.update(range(lo, hi + 1))
        else:
            out.add(int(p, 0))
    bad = [x for x in out if not 0 <= x < PHASES]
    if bad:
        raise SystemExit(f"delays outside 0..{PHASES - 1}: {bad}")
    return sorted(out)


def _summary(rows):
    by_arm = {}
    for arm in ARMS:
        rr = [r for r in rows if r["arm"] == arm]
        fail = [r for r in rr if r["overrun"]]
        by_arm[arm] = {
            "cases": len(rr),
            "interrupt_serviced": sum(r["interrupt_serviced"] for r in rr),
            "overruns": len(fail),
            "failing_delays": [r["delay"] for r in fail],
            "pushed_ips_on_fail": sorted({r["pushed_ip"] for r in fail}),
            "inta_counts_on_fail": sorted({r["inta_cycles"] for r in fail}),
            "isr_counts_on_fail": sorted({r["bp"] for r in fail}),
        }
    return {
        "cases": len(rows),
        "overruns": sum(r["overrun"] for r in rows),
        "by_arm": by_arm,
    }


def _write_result(path, payload):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"  artifact: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def cmd_rtl(args):
    phases = _parse_delays(args.delays)
    C.build(core="ucore")
    binary = C.core_bin("ucore")
    with tempfile.TemporaryDirectory(prefix="rep_int_term_") as td:
        batch = Path(td) / "batch.txt"
        out = Path(td) / "out.txt"
        cases = _write_batch(batch, phases, args.hold)
        run = subprocess.run(
            [str(binary), f"+batch={batch}", f"+out={out}",
             f"+ce_div={args.ce_div}"],
            cwd=ROOT, capture_output=True, text=True, timeout=300)
        if run.returncode != 0 or f"DONE {len(cases)} cases" not in run.stdout:
            raise SystemExit(f"bare-core run failed\n{run.stdout[-1000:]}\n"
                             f"{run.stderr[-1000:]}")
        parsed = C.parse_out(out)
    rows = []
    for idx, (arm, delay) in enumerate(cases):
        got = parsed.get(idx)
        if got is None or got["final"] is None:
            raise SystemExit(f"case {arm}/{delay}: no final state")
        rows.append(_score(arm, delay, got["final"], got["recs"]))
    summary = _summary(rows)
    payload = {
        "tool": "rep_int_term_race rtl", "engine": "bare v30_core/ucore",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                        cwd=ROOT, text=True).strip(),
        "binary": str(binary.relative_to(ROOT)),
        "receipt": artifact.receipt_id(binary),
        "ce_div": args.ce_div, "hold": args.hold,
        "phases_per_arm": len(phases),
        "phase_values": phases, "summary": summary, "rows": rows,
    }
    print(json.dumps(summary, indent=1))
    _write_result(args.out, payload)
    return 1 if summary["overruns"] else 0


def _board_image(arm):
    regs = _regs(arm, names="nec")
    ram = [(DATA + i, b) for i, b in enumerate(ARMS[arm]["data"])]
    # Slot 0 is INC BP + the IRET testimage appends.
    image, meta = ti.compose(
        regs=regs, instr=_instruction(arm), ram=ram,
        ivt={INT_VECTOR: (0, ti.IHT_AT)}, handlers=[bytes([0x45])])
    return bytes(image), meta


def _raw_sha(words):
    return hashlib.sha256(("\n".join(f"{w:016x}" for w in words)
                           + "\n").encode()).hexdigest()


def _board_score(arm, delay, recs, fired, meta):
    import v30run
    parsed = v30run.parse_result(recs, meta)
    tx = v30run.extract_txns_large(recs)
    inta = [t for t in tx if v30run.KIND[t["kind"]] == "INTA"]
    # External INT is the only INTA source.  Its three following stack writes
    # are PSW, CS, PC; INT3 termination later has no INTA cycles.
    memw_after = []
    if inta:
        memw_after = [t for t in tx if v30run.KIND[t["kind"]] == "MEMW"
                      and t["start"] > inta[0]["start"]]
    pushed_ip = memw_after[2]["data"] if len(memw_after) >= 3 else None
    fin = parsed["regs"]
    isr_count = fin["BP"]
    got = {"di": fin["IY"], "cx": fin["CW"]}
    want = {"di": DATA + TERM_N, "cx": COUNT - TERM_N}
    overrun = isr_count == 1 and got != want
    return {
        "arm": arm, "delay": delay, "terminator": ARMS[arm]["terminator"],
        "di": fin["IY"], "cx": fin["CW"], "bp": isr_count,
        "pushed_ip": pushed_ip, "inta_cycles": len(inta),
        "event_fired": bool(fired), "interrupt_serviced": isr_count == 1,
        "overrun": overrun,
        "pass": not overrun and (not isr_count or got == want),
    }


def cmd_board(args):
    import emit_suite as es
    import v30run
    import b1_recapture
    from ie_pinfall_cell import _board, _flash_pin, _sha_dir, single_writer

    phases = _parse_delays(args.delays)
    _vr, host_default, div_guard, pin_div, div_default = _board()
    host = args.host or host_default
    div = args.div if args.div is not None else div_default
    if es.EMIT_USE_CORE is not False:
        raise SystemExit("refusing board run: emit_suite truth source is not socket")
    args.out = args.out.resolve()
    outdir = args.out.parent
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tool": "rep_int_term_race board", "host": host,
        "use_core": False, "div": div,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                        cwd=ROOT, text=True).strip(),
        "flash": _flash_pin(), "phase_values": phases,
        "images": {}, "div_guards": [],
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for arm in ARMS:
        image, _meta = _board_image(arm)
        manifest["images"][arm] = hashlib.sha256(image).hexdigest()
    print("== single-writer / reachability")
    manifest["preflight"] = single_writer(host)
    if manifest["preflight"]["single_writer"] != "OK":
        _write_result(args.out, manifest)
        raise SystemExit("single-writer check did not pass -- STOP")

    rows = []
    raw = {}
    t0 = time.time()
    try:
        pin_div()
        manifest["div_guards"].append(["preflight", div_guard("rep-int-pre")])
        for arm in ARMS:
            image, meta = _board_image(arm)
            anchor = meta["anchor_linear"]
            for n, delay in enumerate(phases, 1):
                recs, fired, words = v30run.run_image(
                    image, host, tag="repit", waits=0, use_core=False,
                    div=div, evt=(anchor, delay, args.hold, 0),
                    want_raw=True, cap=args.cap)
                row = _board_score(arm, delay, recs, fired, meta)
                sha = _raw_sha(words)
                row.update(raw_sha256=sha, raw_words=len(words))
                rows.append(row)
                raw[f"{arm}:{delay}"] = [f"{w:016x}" for w in words]
                if n % 20 == 0 or n == len(phases):
                    print(f"  {arm}: {n}/{len(phases)}  "
                          f"({time.time() - t0:.0f}s)", flush=True)
            manifest["div_guards"].append([arm, div_guard(f"rep-int-{arm}")])
    finally:
        # A failed capture still closes the serve process and checks the idle
        # state; the board must never be handed back in an unknown condition.
        runner = v30run._runners.get(host)
        if runner is not None:
            runner.close()
        try:
            b1_recapture.board_idle()
            manifest["board_idle"] = "completed; socket selected"
        finally:
            runner = v30run._runners.get(host)
            if runner is not None:
                runner.close()
        manifest["serve_session"] = "closed"

    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["seconds"] = round(time.time() - t0, 1)
    manifest["summary"] = _summary(rows)
    manifest["rows"] = rows
    raw_path = outdir / "board.raw.json.gz"
    with gzip.open(raw_path, "wt") as f:
        json.dump(raw, f, separators=(",", ":"))
    _write_result(args.out, manifest)
    _sha_dir(outdir)
    print(json.dumps(manifest["summary"], indent=1))
    print(f"  raw: {raw_path.relative_to(ROOT)}")
    return 1 if manifest["summary"]["overruns"] else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("rtl", help="600-phase bare-v30_core regression")
    rp.add_argument("--delays", help="comma/range subset; default 0-299")
    rp.add_argument("--ce-div", type=int, default=C.CE_DIV_DEFAULT)
    rp.add_argument("--hold", type=int, default=INT_HOLD)
    rp.add_argument("--out", type=Path)
    rp.set_defaults(func=cmd_rtl)

    bp = sub.add_parser("board", help="socketed-V30 hardware comparison")
    bp.add_argument("--delays", required=True,
                    help="comma/range delays selected by the preregistration")
    bp.add_argument("--host")
    bp.add_argument("--div", type=int)
    bp.add_argument("--cap", type=int, default=1400)
    bp.add_argument("--hold", type=int, default=INT_HOLD)
    bp.add_argument("--out", type=Path, required=True)
    bp.set_defaults(func=cmd_board)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
