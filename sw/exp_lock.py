#!/usr/bin/env python3
"""exp_lock - BUSLOCK (F0 LOCK prefix) chip characterization.

Phase-1 rebuild measurement (reflash-free, socketed chip = ground truth).
Emits LOCK-prefixed RMW memory ops (F0 <op>) plus a non-locked baseline and
dumps the per-cycle bus grid with the max-mode LOCK output pin (capture bit
50, active low). Answers, from first principles:
  - when LOCK asserts / deasserts relative to the locked op's bus cycles
  - whether prefetch (CODE fetches) is suppressed while LOCK is asserted
  - the prefix's own bus footprint (does F0 pop as its own cycle?)

Usage: exp_lock.py [--host root@mister-nec]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler          # noqa: E402
from v30run import run_test           # noqa: E402

T = {0: "TI", 1: "T1", 2: "T2", 3: "T3", 4: "TW", 5: "T4"}
BS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
      4: "CODE", 5: "MEMR", 6: "MEMW", 7: "----"}
Q = {0: "-", 1: "F", 2: "E", 3: "S"}


def dump(res, title, anchor):
    recs = res["recs"]
    # find the anchor CODE T1 (the locked op / baseline op fetch region start)
    start = None
    for i, r in enumerate(recs):
        if r["t"] == 1 and r["bs_early"] == 4 and r["ad_addr"] == anchor:
            start = i
            break
    if start is None:
        print(f"{title}: anchor {anchor:05x} not found")
        return
    print(f"\n=== {title}  (anchor {anchor:05x}) ===")
    print(" idx  T  BS   addr  data  Q ube rd LOCK")
    lock_spans = []
    in_lock = False
    span0 = None
    for r in recs[start - 2:start + 34]:
        lk = r["lock_n"]
        active = (lk == 0)
        if active and not in_lock:
            in_lock = True
            span0 = r["idx"]
        elif not active and in_lock:
            in_lock = False
            lock_spans.append((span0, r["idx"] - 1))
        mark = " <LOCK" if active else ""
        print(f"{r['idx']:>5} {T.get(r['t'],'?'):<2} "
              f"{BS[r['bs_early']]:<4} {r['ad_addr']:05x} {r['ad_data']:04x} "
              f"{Q[r['qs']]}  {r['ube_n']}   {r['rd_n']}  {lk}{mark}")
    if in_lock:
        lock_spans.append((span0, recs[start + 33]["idx"]))
    print(f"  LOCK-low spans (idx): {lock_spans}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    a = Assembler()
    mem = {"BW": 0x0800, "DS0": 0, "AW": 0xBEEF, "PS": 0, "PC": 0x0500}

    # Each case: a 16-NOP runway (saturate/settle the queue), then the op,
    # then 8 NOPs. Anchor = the op's first fetch address (0x0500 + 16).
    runway = b"\x90" * 16
    tail = b"\x90" * 8
    anchor = 0x0500 + 16
    cases = [
        ("ADD [BW],AW  (no lock)",        a.assemble("ADD [BW], AW")),
        ("F0 ADD [BW],AW  (LOCK)",  b"\xf0" + a.assemble("ADD [BW], AW")),
        ("F0 XCH [BW],AW  (LOCK)",  b"\xf0" + a.assemble("XCH [BW], AW")),
        ("XCH [BW],AW  (no prefix)",       a.assemble("XCH [BW], AW")),
        ("F0 INC byte [BW] (LOCK)", b"\xf0" + a.assemble("INC byte [BW]")),
    ]
    for title, op in cases:
        instr = runway + op + tail
        res = run_test(regs=dict(mem), instr=instr, host=args.host,
                       tag="lock")
        dump(res, title, anchor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
