#!/usr/bin/env python3
"""v30ctl - control the V30 test harness over the lightweight HPS bridge.

Runs on the DE10's ARM (MiSTer Linux) as root. Stop MiSTer Main first
(`killall MiSTer`) so nothing else drives the FPGA-side interfaces.

Address map (hdl/rtl/hps_axi_slave.sv), window at physical 0xFF200000:
  +0x000000  64 KB test memory (byte-packed)
  +0x100000  32 KB capture buffer (4096 x 64-bit records)
  +0x180000  registers (MAGIC/CTRL/CFG/PINS/STATUS/CAPCOUNT)

IMPORTANT flow around FPGA reconfiguration: run `v30ctl.py prep` BEFORE
JTAG-programming a new bitstream (it puts the HPS-FPGA bridges into reset so
the reconfiguration cannot wedge the interconnect), then any other command
afterwards re-enables them. An access to an unconfigured/unresponsive bridge
hard-locks the ARM — power cycle if that happens.

Usage:
  v30ctl.py prep                     # put bridges in reset (before reconfig)
  v30ctl.py status
  v30ctl.py stop                     # host_reset: CPU stopped, memory/capture accessible
  v30ctl.py start [--power-wait]     # release reset (default: fast re-run)
  v30ctl.py load FILE [--at ADDR]    # write binary image into test memory (while stopped)
  v30ctl.py peek ADDR [COUNT]        # hex dump of test memory (while stopped)
  v30ctl.py dump-cap FILE            # write capture records, decode with decode_capture.py
  v30ctl.py run FILE [--timeout S]   # stop -> load -> start -> wait full -> dump to stdout name
  v30ctl.py cfg [--div N] [--waits N] [--vector V] [--small 0|1]
  v30ctl.py serve                    # persistent stdin/stdout batch mode:
                                     #   PING                     -> OK PONG
                                     #   CFG <div> <waits> <vector> <small>
                                     #     ('-' keeps a field)    -> OK CFG
                                     #   RUN <timeout_s> [k=v ...]\\n<base64>
                                     #     -> OK <cap_count> <full> <evt>
                                     #        \\n<base64 of 4096 LE uint64>
                                     #     options (reset to defaults on every
                                     #     RUN when not given):
                                     #       evt=A:D:H:P  pin-event scheduler:
                                     #                    CODE T1 at linear A
                                     #                    (hex), +D clocks,
                                     #                    drive pin P (0=INT
                                     #                    1=NMI 2=POLL) for H
                                     #                    clocks (0=til reset)
                                     #       iord=XXXX    I/O read data (hex,
                                     #                    default FFFF)
                                     #       pins=X       static PINS reg (hex:
                                     #                    b0 INT b1 NMI
                                     #                    b2 POLL_N; default 0)
                                     #     <evt> in the reply = evt_fired,
                                     #     sampled before host_reset
                                     #   EXIT                     -> OK BYE
                                     # errors: ERR <message>; one command per
                                     # line, all responses flushed
"""

import argparse
import mmap
import os
import struct
import sys
import time

LW_BASE   = 0xFF200000
LW_SPAN   = 0x200000
RSTMGR    = 0xFFD05000
L3_GPV    = 0xFF800000

MEM_OFF   = 0x000000
CAP_OFF   = 0x100000
REG_OFF   = 0x180000

R_MAGIC    = REG_OFF + 0x00
R_CTRL     = REG_OFF + 0x04
R_CFG      = REG_OFF + 0x08
R_PINS     = REG_OFF + 0x0C
R_STATUS   = REG_OFF + 0x10
R_CAPCOUNT = REG_OFF + 0x14
R_IORD     = REG_OFF + 0x18
R_EVT_ADDR = REG_OFF + 0x1C
R_EVT_CFG  = REG_OFF + 0x20

MAGIC = 0x56333031

CTRL_HOST_RESET = 1 << 0
CTRL_POWER_OFF  = 1 << 1
CTRL_SKIP_PWRUP = 1 << 2

CAP_RECORDS = 4096


class Harness:
    def __init__(self, connect=True):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        if not connect:
            return
        self._enable_bridges()
        self.win = mmap.mmap(self.fd, LW_SPAN, offset=LW_BASE)
        magic = self.read32(R_MAGIC)
        if magic != MAGIC:
            raise RuntimeError(
                f"bridge magic mismatch: got {magic:08x}, want {MAGIC:08x} "
                "(is the harness bitstream loaded?)")

    def _brgmodrst(self, set_bits, clr_bits):
        rst = mmap.mmap(self.fd, 0x1000, offset=RSTMGR)
        v = struct.unpack("<I", rst[0x1C:0x20])[0]
        rst[0x1C:0x20] = struct.pack("<I", (v | set_bits) & ~clr_bits)
        rst.close()

    def disable_bridges(self):
        # put hps2fpga/lwhps2fpga/fpga2hps into reset: safe state for FPGA
        # reconfiguration
        self._brgmodrst(set_bits=0x7, clr_bits=0)

    def _enable_bridges(self):
        # deassert bridge resets and open the L3 remap window — the same
        # pokes MiSTer Main performs on core load
        self._brgmodrst(set_bits=0, clr_bits=0x7)
        gpv = mmap.mmap(self.fd, 0x1000, offset=L3_GPV)
        gpv[0:4] = struct.pack("<I", 0x19)
        gpv.close()

    def read32(self, off):
        return struct.unpack("<I", self.win[off:off + 4])[0]

    def write32(self, off, val):
        self.win[off:off + 4] = struct.pack("<I", val & 0xFFFFFFFF)

    # ---- harness operations -------------------------------------------
    def stop(self):
        self.write32(R_CTRL, CTRL_HOST_RESET | CTRL_SKIP_PWRUP)

    def start(self, power_wait=False):
        self.write32(R_CTRL, 0 if power_wait else CTRL_SKIP_PWRUP)

    def status(self):
        s = self.read32(R_STATUS)
        return {
            "pwr_good":    bool(s & 1),
            "cpu_running": bool(s & 2),
            "cap_full":    bool(s & 4),
            "cap_count":   self.read32(R_CAPCOUNT),
            "ctrl":        self.read32(R_CTRL),
            "cfg":         self.read32(R_CFG),
        }

    def load_mem(self, data: bytes, addr=0):
        assert addr % 4 == 0, "load address must be 32-bit aligned"
        # pad to a whole number of words
        pad = (-len(data)) % 4
        data = data + b"\x00" * pad
        # bounded slice writes: one memcpy per chunk is fast, but keep
        # chunks <= 1KB and 32-bit aligned - a single giant copy across
        # the 32-bit lightweight bridge can emit 64-bit ARM accesses
        # that bus-error
        ch = 1024
        for i in range(0, len(data), ch):
            end = min(i + ch, len(data))
            self.win[MEM_OFF + addr + i: MEM_OFF + addr + end] = data[i:end]

    def peek_mem(self, addr, count):
        out = bytearray()
        a0 = addr & ~3
        a1 = (addr + count + 3) & ~3
        for a in range(a0, a1, 4):
            out += self.win[MEM_OFF + a: MEM_OFF + a + 4]
        return bytes(out[addr - a0: addr - a0 + count])

    def dump_capture(self, count=CAP_RECORDS):
        # bounded slice reads (see load_mem note on chunk size)
        count = min(count, CAP_RECORDS)
        raw = bytearray()
        total = count * 8
        ch = 1024
        for i in range(0, total, ch):
            end = min(i + ch, total)
            raw += self.win[CAP_OFF + i: CAP_OFF + end]
        return list(struct.unpack(f"<{count}Q", bytes(raw)))

    def set_iord(self, val):
        self.write32(R_IORD, val & 0xFFFF)

    def set_event(self, addr=None, delay=0, hold=0, pin=0, arm=True):
        """Arm the pin-event scheduler: on a CODE T1 at linear `addr`,
        wait `delay` CPU clocks, drive pin (0=INT 1=NMI 2=POLL) for `hold`
        clocks (0 = until disarmed). arm=False disarms."""
        if addr is not None:
            self.write32(R_EVT_ADDR, addr & 0xFFFFF)
        v = (delay & 0xFFFF) | ((hold & 0xFF) << 16) | ((pin & 7) << 24)
        if arm:
            v |= 1 << 31
        self.write32(R_EVT_CFG, v)

    def event_fired(self):
        return bool(self.read32(R_STATUS) & 8)

    def set_cfg(self, div=None, waits=None, vector=None, small=None):
        v = self.read32(R_CFG)
        if div is not None:    v = (v & ~0x3F) | (div & 0x3F)
        if waits is not None:  v = (v & ~0xF00) | ((waits & 0xF) << 8)
        if vector is not None: v = (v & ~0xFF0000) | ((vector & 0xFF) << 16)
        if small is not None:  v = (v & ~(1 << 24)) | ((1 if small else 0) << 24)
        self.write32(R_CFG, v)


def write_cap_file(recs, path):
    with open(path, "w") as fh:
        for r in recs:
            fh.write(f"{r:016x}\n")


def serve(h):
    """Persistent batch mode over stdin/stdout (one ssh connection serves
    many runs; each RUN still does the full stop/load/start/reset cycle).

    v2 additions (client falls back to v1 semantics on an old banner):
      BASE\\n<base64 image>       cache + CRC a baseline image
                                  -> OK BASE <crc32-hex>
      DELTA <timeout> [k=v ...]\\n<base64 patch>
                                  patch = repeat{u32 off, u16 len, bytes}
                                  applied to the cached baseline, then a
                                  normal run; reply carries the effective
                                  image's crc32 as a 4th field
      cap=N (RUN/DELTA option)    return only the first N capture records
    """
    import base64
    import zlib
    out = sys.stdout
    base_img = None          # cached baseline (bytearray)

    def reply(s):
        out.write(s + "\n")
        out.flush()

    def do_run(img, timeout, evt, iord, pins, cap, crc):
        h.stop()
        h.load_mem(img, 0)
        h.set_iord(iord)
        h.write32(R_PINS, pins)
        if evt:
            h.set_event(addr=evt[0], delay=evt[1], hold=evt[2], pin=evt[3])
        else:
            h.set_event(arm=False)
        h.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if h.status()["cap_full"]:
                break
            time.sleep(0.002)
        st = h.status()
        fired = int(h.event_fired())   # before stop: clears on reset
        h.stop()
        h.set_event(arm=False)
        h.write32(R_PINS, 0)
        recs = h.dump_capture(cap)
        blob = struct.pack(f"<{len(recs)}Q", *recs)
        tail = f" {crc:08x}" if crc is not None else ""
        reply(f"OK {st['cap_count']} {int(st['cap_full'])} {fired}{tail}")
        reply(base64.b64encode(blob).decode())

    def parse_opts(parts):
        timeout = float(parts[1]) if len(parts) > 1 else 3.0
        evt, iord, pins, cap = None, 0xFFFF, 0, CAP_RECORDS
        for kv in parts[2:]:
            k, _, v = kv.partition("=")
            if k == "evt":
                a, d, ho, p = v.split(":")
                evt = (int(a, 16), int(d), int(ho), int(p))
            elif k == "iord":
                iord = int(v, 16)
            elif k == "pins":
                pins = int(v, 16)
            elif k == "cap":
                cap = max(1, min(int(v), CAP_RECORDS))
            else:
                raise ValueError(f"unknown option {k!r}")
        return timeout, evt, iord, pins, cap

    reply("OK SERVE v2")
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        try:
            if parts[0] == "PING":
                reply("OK PONG")
            elif parts[0] == "EXIT":
                reply("OK BYE")
                break
            elif parts[0] == "CFG":
                vals = [None if p == "-" else int(p, 0) for p in parts[1:5]]
                h.stop()
                h.set_cfg(*vals)
                reply("OK CFG")
            elif parts[0] == "BASE":
                base_img = bytearray(
                    base64.b64decode(sys.stdin.readline().strip()))
                reply(f"OK BASE {zlib.crc32(base_img) & 0xFFFFFFFF:08x}")
            elif parts[0] == "DELTA":
                timeout, evt, iord, pins, cap = parse_opts(parts)
                patch = base64.b64decode(sys.stdin.readline().strip())
                if base_img is None:
                    raise ValueError("DELTA without BASE")
                img = bytearray(base_img)
                i = 0
                while i < len(patch):
                    off, ln = struct.unpack_from("<IH", patch, i)
                    i += 6
                    img[off:off + ln] = patch[i:i + ln]
                    i += ln
                crc = zlib.crc32(img) & 0xFFFFFFFF
                do_run(bytes(img), timeout, evt, iord, pins, cap, crc)
            elif parts[0] == "RUN":
                timeout, evt, iord, pins, cap = parse_opts(parts)
                img = base64.b64decode(sys.stdin.readline().strip())
                do_run(img, timeout, evt, iord, pins, cap, None)
            else:
                reply(f"ERR unknown command {parts[0]!r}")
        except Exception as e:                        # noqa: BLE001
            reply(f"ERR {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prep")
    sub.add_parser("serve")
    sub.add_parser("status")
    sub.add_parser("stop")
    p = sub.add_parser("start")
    p.add_argument("--power-wait", action="store_true",
                   help="full ~131 ms rail-settle wait instead of fast re-run")
    p = sub.add_parser("load")
    p.add_argument("file")
    p.add_argument("--at", type=lambda x: int(x, 0), default=0)
    p = sub.add_parser("peek")
    p.add_argument("addr", type=lambda x: int(x, 0))
    p.add_argument("count", type=lambda x: int(x, 0), nargs="?", default=64)
    p = sub.add_parser("dump-cap")
    p.add_argument("file")
    p = sub.add_parser("run")
    p.add_argument("file", help="binary memory image, loaded at 0")
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--cap", default="capture.hex")
    p = sub.add_parser("cfg")
    p.add_argument("--div", type=lambda x: int(x, 0))
    p.add_argument("--waits", type=lambda x: int(x, 0))
    p.add_argument("--vector", type=lambda x: int(x, 0))
    p.add_argument("--small", type=int, choices=(0, 1))
    args = ap.parse_args()

    if args.cmd == "prep":
        h = Harness(connect=False)
        h.disable_bridges()
        print("bridges in reset: safe to reconfigure the FPGA")
        return

    h = Harness()

    if args.cmd == "status":
        for k, v in h.status().items():
            print(f"{k}: {v:#x}" if isinstance(v, int) and not isinstance(v, bool) else f"{k}: {v}")
    elif args.cmd == "stop":
        h.stop()
        print("stopped (host owns memory/capture)")
    elif args.cmd == "start":
        h.start(power_wait=args.power_wait)
        print("running")
    elif args.cmd == "load":
        data = open(args.file, "rb").read()
        h.stop()
        h.load_mem(data, args.at)
        print(f"loaded {len(data)} bytes at {args.at:#x} (harness stopped)")
    elif args.cmd == "peek":
        data = h.peek_mem(args.addr, args.count)
        for i in range(0, len(data), 16):
            row = data[i:i + 16]
            print(f"{args.addr + i:05x}: " + " ".join(f"{b:02x}" for b in row))
    elif args.cmd == "dump-cap":
        h.stop()
        write_cap_file(h.dump_capture(), args.file)
        print(f"wrote {CAP_RECORDS} records to {args.file}")
    elif args.cmd == "run":
        data = open(args.file, "rb").read()
        h.stop()
        h.load_mem(data, 0)
        h.start()
        t0 = time.time()
        while time.time() - t0 < args.timeout:
            if h.status()["cap_full"]:
                break
            time.sleep(0.01)
        st = h.status()
        h.stop()
        write_cap_file(h.dump_capture(), args.cap)
        print(f"cap_count={st['cap_count']} full={st['cap_full']} -> {args.cap}")
    elif args.cmd == "cfg":
        h.stop()
        h.set_cfg(args.div, args.waits, args.vector, args.small)
        print(f"cfg = {h.read32(R_CFG):08x} (harness stopped; 'start' to run)")
    elif args.cmd == "serve":
        serve(h)


if __name__ == "__main__":
    main()
