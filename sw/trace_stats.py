#!/usr/bin/env python3
"""trace_stats - summarize golden-trace event schedules per opcode form.

For each test case, reduce the cycle rows to an event schedule relative to
the window's first F pop: queue pops (F/S/E), bus-cycle T1s by type, and
the closing F. Group identical schedules per form signature so the EU
microsequencer can be written against the real per-form timing.

Usage: trace_stats.py OPCODE [OPCODE...] [--variant even|odd|all] [--max N]
"""
import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "tests" / "v30" / "v0.1"


def signature(case, op):
    b = case["bytes"]
    regs = case["initial"]["regs"]
    sig = []
    sig.append("pf" if case["idx"] % 2 else "cold")
    sig.append("ip-odd" if regs["ip"] & 1 else "ip-even")
    two_byte = b[0] == 0x0F
    mrm_i = (2 if two_byte else 1)
    if op in ("B8", "40", "48"):
        pass
    elif op in ("50", "58"):
        sig.append("sp-odd" if regs["sp"] & 1 else "sp-even")
    elif len(b) > mrm_i and op not in ("0F20",):
        m = b[mrm_i]
        mod, rm = m >> 6, m & 7
        if mod == 3:
            sig.append("mod3")
        else:
            nd = {0: 2 if rm == 6 else 0, 1: 1, 2: 2}[mod]
            sig.append(f"mem-d{nd}")
    return " ".join(sig)


def schedule(case):
    ev = []
    for i, r in enumerate(case["cycles"]):
        (ale, bus, seg, mem, io, ube, data, bs, t, q, qb) = r
        if t == "T1":
            ev.append(f"{bs}{'b' if ube else 'w'}@{i}")
        if q in ("F", "S", "E"):
            ev.append(f"{q}@{i}")
    ev.append(f"len={len(case['cycles'])}")
    return " ".join(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("opcodes", nargs="+")
    ap.add_argument("--variant", default="all")
    ap.add_argument("--max", type=int, default=6)
    args = ap.parse_args()
    for op in args.opcodes:
        cases = json.load(gzip.open(DIR / f"{op}.json.gz"))
        groups = defaultdict(Counter)
        for c in cases:
            if args.variant == "even" and c["idx"] % 2:
                continue
            if args.variant == "odd" and not c["idx"] % 2:
                continue
            groups[signature(c, op)][schedule(c)] += 1
        print(f"==== {op} ====")
        for sig in sorted(groups):
            print(f"  [{sig}]  ({sum(groups[sig].values())} cases)")
            for sched, n in groups[sig].most_common(args.max):
                print(f"    {n:4d}x  {sched}")


if __name__ == "__main__":
    main()
