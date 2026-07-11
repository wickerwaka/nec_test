#!/usr/bin/env python3
"""Analyze a V30 harness capture: bus transactions, fetch stream, timing.

Consumes the per-cycle record dumps produced by v30ctl.py dump-cap or
sw/dump_capture.tcl and reconstructs bus-level activity. Small-scale mode
only for now (record layout per hdl/README.md; ASTB/RD/WR bits are sticky
per cycle).

Usage:
  analyze_capture.py CAPTURE.hex [--txn] [--loops] [-v]

Reports:
  - reset release point and reset-to-first-bus-cycle latency
  - the transaction stream (--txn): index, type, address, data, cycle count
  - fetch/data classification via a linear-fetch-pointer heuristic
  - loop detection (--loops): repeating transaction sequences with per-loop
    cycle counts — instruction-timing measurements fall out of this
"""

import argparse
import sys
from dataclasses import dataclass, field


@dataclass
class Cycle:
    idx: int
    ad_addr: int
    ad_data: int
    ps: int
    astb: bool
    intak_n: bool
    io_m: bool     # 1 = memory
    rd_n: bool
    wr_n: bool
    ube_n: bool
    ready: bool
    rst: bool


@dataclass
class Txn:
    start: int          # cycle index of T1
    end: int            # last cycle index with the strobe active
    kind: str           # MEMR/MEMW/IOR/IOW/INTA
    addr: int
    data: int
    word: bool          # both byte lanes active
    cls: str = "?"      # fetch/data classification


def parse(path):
    cycles = []
    with open(path) as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            r = int(line, 16)
            cycles.append(Cycle(
                idx=i,
                ad_addr=r & 0xFFFFF,
                ad_data=(r >> 20) & 0xFFFF,
                ps=(r >> 36) & 0xF,
                astb=bool((r >> 46) & 1),
                intak_n=bool((r >> 47) & 1),
                io_m=bool((r >> 45) & 1),   # bs_late[2]
                rd_n=bool((r >> 48) & 1),
                wr_n=bool((r >> 50) & 1),
                ube_n=bool((r >> 49) & 1),
                ready=bool((r >> 51) & 1),
                rst=bool((r >> 55) & 1),
            ))
    return cycles


def find_reset_release(cycles):
    for i in range(1, len(cycles)):
        if cycles[i - 1].rst and not cycles[i].rst:
            return i
    return 0


def extract_txns(cycles, start):
    """Group cycles into bus transactions.

    A transaction begins at a run of ASTB=1 cycles (T1; the address-phase
    sample of the LAST cycle in the run holds the latched address) and its
    strobe (RD/WR/INTAK low) spans the following cycles. Data is the
    data-phase sample of the last strobe-active cycle.
    """
    txns = []
    i = start
    n = len(cycles)
    while i < n:
        if not cycles[i].astb:
            i += 1
            continue
        # T1: consume the full ASTB run; the address-phase sample of the
        # LAST cycle holds the latched address (an ASTB pulse can straddle
        # a record boundary, and the first cycle after reset carries float
        # garbage). Bus cycles are >=4 CPU clocks, so two distinct T1s can
        # never be adjacent records.
        j = i
        while j + 1 < n and cycles[j + 1].astb:
            j += 1
        t1 = cycles[j]
        addr = t1.ad_addr
        ube_n = t1.ube_n
        # follow the strobe
        k = j
        kind, data, last = None, None, j
        while k < n:
            c = cycles[k]
            if not c.intak_n:
                kind, data, last = "INTA", c.ad_data, k
            elif not c.rd_n:
                kind, data, last = ("MEMR" if c.io_m else "IOR"), c.ad_data, k
            elif not c.wr_n:
                kind, data, last = ("MEMW" if c.io_m else "IOW"), c.ad_data, k
            elif kind is not None:
                break     # strobe finished
            k += 1
            if k > j + 40:
                break     # runaway (waits beyond expectation): bail out
        if kind is None:
            i = j + 1
            continue
        txns.append(Txn(start=i, end=last, kind=kind, addr=addr, data=data,
                        word=(addr & 1) == 0 and not ube_n))
        i = last + 1
    return txns


def strobe_active(c):
    return not (c.rd_n and c.wr_n and c.intak_n)


def classify(txns):
    """Fetch vs data heuristic: track a linear fetch pointer.

    The 16-bit BIU fetches WORDS at even addresses; the only byte fetch is
    the first one after a jump to an odd address. So:
      - continuation: MEMR at the fetch pointer, word if the pointer is
        even, byte if odd (which re-aligns the pointer)
      - stream break (jump/queue flush): a MEMR whose successor MEMR is a
        valid continuation of it — requiring word-ness rules out the two
        halves of an odd-address split data read
      - anything else is a data read
    """
    def cont_ok(t, ptr):
        if t.kind != "MEMR" or t.addr != ptr:
            return False
        return t.word if ptr % 2 == 0 else not t.word

    fetch_ptr = None
    for i, t in enumerate(txns):
        if t.kind != "MEMR":
            t.cls = "data"
            fetch_ptr = None if t.kind in ("INTA",) else fetch_ptr
            continue
        if fetch_ptr is not None and cont_ok(t, fetch_ptr):
            t.cls = "fetch"
            fetch_ptr = (t.addr + 2) & ~1 if t.word else t.addr + 1
            continue
        # candidate stream break: treat as a jump target only if the next
        # MEMR is a valid continuation of it
        step = 2 if t.word else 1
        new_ptr = (t.addr + step) & ~1 if t.word or t.addr % 2 == 1 else t.addr + step
        nxt = next((u for u in txns[i + 1:i + 4] if u.kind == "MEMR"), None)
        if nxt is not None and cont_ok(nxt, new_ptr) and (t.word or t.addr % 2 == 1):
            t.cls = "fetch*"          # fetch after a stream break (jump/flush)
            fetch_ptr = new_ptr
        else:
            t.cls = "data"
    return txns


def find_loop(txns):
    """Detect the shortest repeating transaction-sequence period by
    comparing (kind, addr) tuples."""
    key = [(t.kind, t.addr) for t in txns]
    n = len(key)
    for period in range(4, n // 3):
        # require at least 3 consecutive repetitions somewhere in the tail
        base = n - 3 * period
        if base < 0:
            break
        if key[base:base + period] == key[base + period:base + 2 * period] \
           == key[base + 2 * period:base + 3 * period]:
            return period, base
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--txn", action="store_true", help="print transactions")
    ap.add_argument("--loops", action="store_true", help="loop analysis")
    ap.add_argument("-n", type=int, default=60, help="limit txn print")
    args = ap.parse_args()

    cycles = parse(args.dump)
    print(f"{len(cycles)} cycles")

    rel = find_reset_release(cycles)
    print(f"reset released at cycle {rel}")

    txns = classify(extract_txns(cycles, rel))
    if not txns:
        print("no bus transactions found")
        return
    first = txns[0]
    print(f"first bus cycle: {first.kind} @{first.addr:05x} "
          f"= cycle {first.start} ({first.start - rel} clks after reset release)")
    print(f"{len(txns)} transactions "
          f"({sum(1 for t in txns if t.cls.startswith('fetch'))} fetch, "
          f"{sum(1 for t in txns if t.cls == 'data')} data)")

    if args.txn:
        print(f"\n{'#':>4} {'cyc':>5} {'len':>3} {'type':<5} {'addr':<6} "
              f"{'data':<4} {'w':<2} cls")
        for i, t in enumerate(txns[:args.n]):
            print(f"{i:>4} {t.start:>5} {t.end - t.start + 1:>3} {t.kind:<5} "
                  f"{t.addr:05x}  {t.data:04x} {'w' if t.word else 'b':<2} {t.cls}")
        if len(txns) > args.n:
            print(f"... ({len(txns) - args.n} more)")

    if args.loops:
        period, base = find_loop(txns)
        if period is None:
            print("\nno repeating loop detected")
        else:
            loop = txns[base:base + period]
            cyc = txns[base + period].start - txns[base].start
            print(f"\nloop: {period} transactions, {cyc} CPU clocks per iteration")
            print(f"{'type':<5} {'addr':<6} {'data':<4} cls")
            for t in loop:
                print(f"{t.kind:<5} {t.addr:05x}  {t.data:04x} {t.cls}")


if __name__ == "__main__":
    main()
