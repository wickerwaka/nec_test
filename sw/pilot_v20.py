#!/usr/bin/env python3
"""pilot_v20 - run V20 SingleStepTests cases on the real V30 and compare.

Architectural cross-validation: the V30's register/flag/memory results
should match the V20 suite exactly (same execution core; only bus behavior
differs). Uses non-prefetched cases only (initial queue empty) since our
load routine's far jump starts the test with a flushed queue.

Usage:
  pilot_v20.py B8 00 37 [--cases 20] [--host root@mister-nec]
  (expects XX.json.gz + metadata.json in --data DIR)
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage                                     # noqa: E402
from testimage import ComposeError                   # noqa: E402
from v30run import run_image, parse_result, RunError  # noqa: E402

INTEL2NEC = {
    "ax": "AW", "bx": "BW", "cx": "CW", "dx": "DW",
    "sp": "SP", "bp": "BP", "si": "IX", "di": "IY",
    "cs": "PS", "ds": "DS0", "es": "DS1", "ss": "SS",
    "ip": "PC", "flags": "PSW",
}
DOCUMENTED_FLAGS = 0x0FD5   # V DIR IE S Z AC P CY (TF excluded: never injected)


def expected_final(case):
    regs = dict(case["initial"]["regs"])
    regs.update(case["final"]["regs"])
    return regs


def apply_write(mem, txn):
    """Apply a captured MEMW honoring A0/UBE byte lanes."""
    addr = txn["addr"]
    data = txn["data"]
    a0 = addr & 1
    if a0 == 0:
        mem[addr & 0xFFFFF] = data & 0xFF            # even lane
        if not txn["ube_n"]:
            mem[(addr + 1) & 0xFFFFF] = data >> 8    # odd lane
    else:
        if not txn["ube_n"]:
            mem[addr & 0xFFFFF] = data >> 8          # odd byte on upper lane


def run_case(case, mask, host, tag, raw_flags=False):
    init = case["initial"]
    regs = {INTEL2NEC[k]: v for k, v in init["regs"].items()}
    exp = expected_final(case)

    stub_linear = ((exp["cs"] << 4) + exp["ip"]) & 0xFFFF
    image, meta = testimage.compose(
        regs=regs,
        instr=bytes(case["bytes"]),
        stub_linear=stub_linear,
        ram=[(a, v) for a, v in init["ram"]],
    )
    recs = run_image(image, host, tag)
    res = parse_result(recs, meta)
    got = res["regs"]

    fails = []
    for intel, nec in INTEL2NEC.items():
        want = exp[intel]
        g = got.get(nec)
        if nec == "PSW":
            m = 0xFFFF if raw_flags else (mask & DOCUMENTED_FLAGS)
            if g is None or (g ^ want) & m:
                fails.append((nec, want, g, m))
        elif nec == "PC":
            if g != (want + 6) & 0xFFFF:    # stub pad offset
                fails.append((nec, (want + 6) & 0xFFFF, g, 0xFFFF))
        else:
            if g != want:
                fails.append((nec, want, g, 0xFFFF))

    # final memory: composed bytes + captured test-phase writes
    mem = {}
    for a, v in init["ram"]:
        mem[a & 0xFFFFF] = v
    for t in res["test_txns"]:
        if t["kind"] == "MEMW":
            apply_write(mem, t)
    stub_range = range(meta["stub_linear"], meta["stub_linear"] + 32)
    for a, v in case["final"]["ram"]:
        if (a & 0xFFFF) in stub_range or (a & 0xFFFF) in testimage.RESERVED:
            continue
        g = mem.get(a & 0xFFFFF)
        if g != v:
            fails.append((f"ram[{a:05x}]", v, g, 0xFF))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("opcodes", nargs="+")
    ap.add_argument("--cases", type=int, default=20)
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--raw-flags", action="store_true",
                    help="compare the FULL 16-bit flags word, ignoring the "
                         "suite's undefined-flag mask (V20==V30 exactness "
                         "check, mission 12)")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent
                    .parent / "tests" / "v30" / "v20suite"))
    args = ap.parse_args()

    meta_db = json.load(open(Path(args.data) / "metadata.json"))
    op_meta = meta_db.get("opcodes", meta_db)

    grand_pass = grand_fail = 0
    for op in args.opcodes:
        cases = json.load(gzip.open(Path(args.data) / f"{op}.json.gz"))
        mask = op_meta.get(op, {}).get("flags-mask", 0xFFFF)
        ran = passed = skipped = 0
        for case in cases:
            if ran >= args.cases:
                break
            if case["initial"]["queue"]:
                continue                        # prefetched variant
            if case["initial"]["regs"]["flags"] & 0x0100:
                continue                        # TF set: not injectable
            try:
                fails = run_case(case, mask, args.host, f"pilot{op}",
                                 raw_flags=args.raw_flags)
            except ComposeError:
                skipped += 1
                continue
            except RunError as e:
                fails = [("RUN", str(e), None, 0)]
            ran += 1
            if fails:
                grand_fail += 1
                print(f"  FAIL {op} idx={case['idx']} {case['name']!r}:")
                for name, want, g, m in fails:
                    gs = f"{g:04x}" if isinstance(g, int) else str(g)
                    ws = f"{want:04x}" if isinstance(want, int) else str(want)
                    print(f"       {name}: want {ws} got {gs} (mask {m:04x})")
            else:
                passed += 1
                grand_pass += 1
        print(f"{op}: {passed}/{ran} passed ({skipped} skipped for "
              f"compose collisions)")
    print(f"\nTOTAL: {grand_pass} passed, {grand_fail} failed")
    sys.exit(1 if grand_fail else 0)


if __name__ == "__main__":
    main()
