#!/usr/bin/env python3
"""Decode a V30 harness capture dump into a readable per-cycle trace.

Usage: decode_capture.py capture.hex [-n LIMIT]

Input: one 16-hex-digit (64-bit) record per line, as produced by
sw/dump_capture.tcl. Record layout is defined in hdl/rtl/nec_bus.sv /
hdl/README.md.

NOTE on JTAG dump ordering: dump_capture.tcl may return words MSB-first per
line depending on quartus_stp version; if decoded T-states look nonsensical,
try --byte-reverse.
"""
import argparse
import sys

T_STATES = {0: "TI", 1: "T1", 2: "T2", 3: "T3", 4: "TW", 5: "T4", 6: "?6", 7: "?7"}

BUS_STATUS = {
    0b000: "INTA", 0b001: "IOR ", 0b010: "IOW ", 0b011: "HALT",
    0b100: "CODE", 0b101: "MEMR", 0b110: "MEMW", 0b111: "PASV",
}

# 8086-compatible queue status (QS1,QS0). Pin mapping per datasheet:
# QS0 = ASTB pin, QS1 = INTAK pin in max mode. Verify at bring-up.
QUEUE_OPS = {0b00: "-", 0b01: "F", 0b10: "E", 0b11: "S"}


def decode(rec: int) -> dict:
    return {
        "ad_addr":  rec & 0xFFFFF,
        "ad_data":  (rec >> 20) & 0xFFFF,
        "ps":       (rec >> 36) & 0xF,
        "bs_early": (rec >> 40) & 0x7,
        "bs_late":  (rec >> 43) & 0x7,
        "qs":       (rec >> 46) & 0x3,
        "rd_n":     (rec >> 48) & 1,
        "ube_n":    (rec >> 49) & 1,
        "buslock_n": (rec >> 50) & 1,
        "ready":    (rec >> 51) & 1,
        "int":      (rec >> 52) & 1,
        "nmi":      (rec >> 53) & 1,
        "poll_n":   (rec >> 54) & 1,
        "reset":    (rec >> 55) & 1,
        "t_state":  (rec >> 56) & 0x7,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("-n", type=int, default=0, help="limit records shown")
    ap.add_argument("--start", type=int, default=0, help="first record to show")
    ap.add_argument("--small", action="store_true",
                    help="interpret pins as small-scale mode functions")
    ap.add_argument("--byte-reverse", action="store_true",
                    help="byte-swap each 64-bit record before decoding")
    args = ap.parse_args()

    records = []
    with open(args.dump) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            v = int(line, 16)
            if args.byte_reverse:
                v = int.from_bytes(v.to_bytes(8, "big"), "little")
            records.append(v)

    print(f"{len(records)} records")
    if args.small:
        # small-scale mode: qs={INTAK,ASTB}, bs={IO/M,BUFR/W,BUFEN}, lk=WR
        print(f"{'idx':>5} AS IK {'IO/M':<4} {'addr':<5} {'data':<4} "
              f"RD WR UBE RDY RST  cycle")
    else:
        print(f"{'idx':>5} {'T':<2} {'BSe':<4} {'BSl':<4} Q "
              f"{'addr':<5} {'data':<4} PS RD UBE LK RDY INT NMI PLL RST")

    shown = 0
    for i, rec in enumerate(records):
        if i < args.start:
            continue
        d = decode(rec)
        if args.small:
            astb = d["qs"] & 1
            intak_n = (d["qs"] >> 1) & 1
            io_m = (d["bs_late"] >> 2) & 1        # 1 = memory, 0 = I/O
            wr_n = d["buslock_n"]
            cycle = ""
            if not intak_n:
                cycle = "INTA"
            elif not d["rd_n"]:
                cycle = "MEMR" if io_m else "IOR"
            elif not wr_n:
                cycle = "MEMW" if io_m else "IOW"
            elif astb:
                cycle = "T1"
            print(f"{i:>5}  {astb}  {intak_n} {'mem' if io_m else 'io ':<4} "
                  f"{d['ad_addr']:05x} {d['ad_data']:04x} "
                  f" {d['rd_n']}  {wr_n}  {d['ube_n']}   {d['ready']}   {d['reset']}   {cycle}")
        else:
            print(f"{i:>5} {T_STATES[d['t_state']]:<2} "
                  f"{BUS_STATUS[d['bs_early']]:<4} {BUS_STATUS[d['bs_late']]:<4} "
                  f"{QUEUE_OPS[d['qs']]} "
                  f"{d['ad_addr']:05x} {d['ad_data']:04x} {d['ps']:x}  "
                  f"{d['rd_n']}  {d['ube_n']}   {d['buslock_n']}  "
                  f"{d['ready']}   {d['int']}   {d['nmi']}   {d['poll_n']}   {d['reset']}")
        shown += 1
        if args.n and shown >= args.n:
            print(f"... ({len(records) - i - 1} more)")
            break


if __name__ == "__main__":
    main()
