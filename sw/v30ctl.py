#!/usr/bin/env python3
"""v30ctl - control the V30 test harness over the lightweight HPS bridge.

Runs on the DE10's ARM (MiSTer Linux) as root. Stop MiSTer Main first
(`killall MiSTer`) so nothing else drives the FPGA-side interfaces.

Address map (hdl/rtl/hps_axi_slave.sv -- THE AUTHORITY; this is a restatement),
window at physical 0xFF200000:
  +0x000000  64 KB test memory (byte-packed)
  +0x100000  32 KB capture buffer (4096 x 64-bit records)
  +0x140000   4 KB wait-vector replay RAM (host write-only)
  +0x180000  registers (MAGIC/CTRL/CFG/PINS/STATUS/CAPCOUNT/...):
       0x1C/0x20  EVT_ADDR  / EVT_CFG   pin-event scheduler 0
       0x30/0x34  EVT2_ADDR / EVT2_CFG  pin-event scheduler 1
       0x38/0x3C  EVT3_ADDR / EVT3_CFG  pin-event scheduler 2
                  -- the three pairs are byte-identical in layout and share ONE
                     packer here and ONE unpacker in the RTL
       0x40       TVEC     [15:0] IP  [31:16] CS, served by the NMI vector-read
                           overlay at linear 0x00008 / 0x0000A while armed
       0x44       VECCTL   [2:0] vecsub_en, bit n = scheduler n's FIRE arms it
       0x10       STATUS   [0] pwr_good [1] cpu_running [2] cap_full
                           [5:3] evt_fired (one bit per scheduler)
                           [6] vec_used (the overlay served a CS half)

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
  v30ctl.py cfg [--div N] [--waits N] [--vector V] [--small 0|1] [--use-core 0|1]
                [--wrand 0|1] [--wmax K] [--wseed S]
  v30ctl.py serve                    # persistent stdin/stdout batch mode:
                                     #   PING                     -> OK PONG
                                     #   CFG <div> <waits> <vector> <small> [use_core]
                                     #     ('-' keeps a field)    -> OK CFG
                                     #   WRAND <randen> <wmax> <seed> <replay>
                                     #     ('-' keeps a field)    -> OK WRAND
                                     #     random/replay per-access waits;
                                     #     identical pattern across A/B
                                     #   WVEC\\n<base64 Tw bytes> -> OK WVEC <n>
                                     #     load the replay wait-vector RAM
                                     #   RUN <timeout_s> [k=v ...]\\n<base64>
                                     #     -> OK <cap_count> <full> <evt>
                                     #        \\n<base64 of 4096 LE uint64>
                                     #     options (reset to defaults on every
                                     #     RUN when not given):
                                     #       evt=A:D:H:P  pin-event scheduler 0:
                                     #                    CODE T1 at linear A
                                     #                    (hex), +D clocks,
                                     #                    drive pin P (0=INT
                                     #                    1=NMI 2=POLL) for H
                                     #                    clocks (0=til reset)
                                     #       evt2=A:D:H:P scheduler 1, same
                                     #       evt3=A:D:H:P scheduler 2, same
                                     #       tvec=CS:IP   NMI vector-read
                                     #                    overlay data (hex)
                                     #       vecsub=M     VECCTL mask (hex):
                                     #                    bit n = scheduler n's
                                     #                    FIRE arms the overlay
                                     #       pinok=1      let schedulers share
                                     #                    a pin (stimulus NMI +
                                     #                    terminating NMI); the
                                     #                    default REFUSES
                                     #       iord=XXXX    I/O read data (hex,
                                     #                    default FFFF)
                                     #       pins=X       static PINS reg (hex:
                                     #                    b0 INT b1 NMI
                                     #                    b2 POLL_N; default 0)
                                     #     <evt> in the reply = STATUS[5:3],
                                     #     bit n = scheduler n fired, sampled
                                     #     before host_reset (it was 0/1 when
                                     #     there was one scheduler, and bit 0
                                     #     is still scheduler 0)
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
WVEC_OFF  = 0x140000   # wait-vector replay RAM (Phase 2a), host write-only
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
R_WRAND    = REG_OFF + 0x24   # seeded random per-access waits (Phase 1 rig)

# THE RIG's pin-event HOLD WIDTH, and the single place it is written down.
# `hdl/rtl/hps_axi_slave.sv`'s `evt_hold` is the authority; this must track it.
# 8 until 2026-08-04 (F46: silent truncation of a banked hold=300 to 44),
# 12 since -- `pack_evt_cfg` below packs [23:16] + [30:27] to reach it.
RIG_EVT_HOLD_BITS  = 12
RIG_EVT_DELAY_BITS = 16
RIG_EVT_ADDR_BITS  = 20
R_IORDS_CTL  = REG_OFF + 0x28 # iords FIFO: [0] reset (pulse) [1] enable
R_IORDS_PUSH = REG_OFF + 0x2C # iords FIFO: [15:0] append one value

# Pin-event schedulers 1 and 2 (fuzz v2).  Scheduler 0 keeps its historical
# offsets so a host that knows nothing about the extra schedulers is bit-for-bit
# unchanged; the layout of every pair is IDENTICAL and there is exactly ONE
# packer for it below -- `hps_axi_slave.sv` has exactly one unpacker to match.
#
# ON A PRE-T5 BITSTREAM (which is what the board carries until the fuzz-v2
# flash) these offsets do not exist: the old write decode ends `default: ;` so
# writes are no-ops, and the old read decode ends `default: rdata <= DEADBEEF`.
# That degrades safely -- schedulers 1/2 stay silent, TVEC/VECCTL are inert, the
# old STATUS is `{28'd0, evt_fired, ...}` so the mask reads 0 or 1 exactly as it
# used to, and DEADBEEF unpacks to pin 6, which is not a pin, so the same-pin
# refusal cannot fire spuriously.  `rig_readback_check()` DOES fail there, and
# that is the correct answer: the registers genuinely are not in that fabric.
R_EVT2_ADDR = REG_OFF + 0x30
R_EVT2_CFG  = REG_OFF + 0x34
R_EVT3_ADDR = REG_OFF + 0x38
R_EVT3_CFG  = REG_OFF + 0x3C
R_TVEC      = REG_OFF + 0x40  # [15:0] IP  [31:16] CS  (NMI vector overlay data)
R_VECCTL    = REG_OFF + 0x44  # [2:0] vecsub_en, bit n = scheduler n arms it

# Number of pin-event schedulers.  `hdl/rtl/system_large.sv`'s EVT_N localparam
# is the authority; hps_axi_slave $fatal's if its offset table disagrees.
EVT_N = 3

# (EVT_ADDR, EVT_CFG) per scheduler, indexed by `which`.  A TABLE, not a fork:
# every accessor below indexes this and shares one packer.
EVT_REGS = ((R_EVT_ADDR,  R_EVT_CFG),
            (R_EVT2_ADDR, R_EVT2_CFG),
            (R_EVT3_ADDR, R_EVT3_CFG))

# evt_pin encoding.  `nec_bus.sv` decodes 0/1/2 and NOTHING ELSE: values 3-7
# make the scheduler fire and drive no pin at all.  There is deliberately no RTL
# trap and no RTL remap -- a remap is the silent-substitution pattern that
# caused INV-1 -- so the host is the only place this class of directive can be
# created, and `pack_evt_cfg` is where it dies.
EVT_PIN_INT, EVT_PIN_NMI, EVT_PIN_POLL = 0, 1, 2
EVT_PIN_NAMES = {EVT_PIN_INT: "INT", EVT_PIN_NMI: "NMI", EVT_PIN_POLL: "POLL_N"}

# STATUS (0x10) bit positions -- `hps_axi_slave.sv`
#   rdata <= {25'd0, vec_used, evt_fired, cap_full, cpu_running, pwr_good}
ST_PWR_GOOD    = 1 << 0
ST_CPU_RUNNING = 1 << 1
ST_CAP_FULL    = 1 << 2
ST_EVT_FIRED_S = 3            # [5:3], one bit per scheduler
ST_VEC_USED    = 1 << 6

MAGIC = 0x56333031


class RigReadbackError(RuntimeError):
    """The rig did not read back the directive it was handed.

    INV-1 in one sentence: 760 banked seeds were scored against a capture taken
    under a directive no engine was ever given, because the rig silently applied
    something else. Every register added for fuzz v2 has an RTL readback path;
    this is what makes that checkable, and it is not cosmetic."""


def pack_evt_cfg(delay=0, hold=0, pin=EVT_PIN_INT, arm=True):
    """THE EVT_CFG packer -- one, shared by all EVT_N schedulers.

    EVT_CFG layout (0x20 / 0x34 / 0x3C, byte-identical), and the hold is SPLIT
    because it grew into the only free space the word had:

        [15:0]  delay      [23:16] hold[7:0]    [26:24] pin
        [30:27] hold[11:8] [31]    arm

    Out-of-range RAISES; nothing here truncates. The hold register was EIGHT
    bits until 2026-08-04 and truncated SILENTLY (F46: 760 banked EVT seeds
    asked for 300 and the socket got 300 & 0xFF = 44). A rig that quietly
    applies a different directive than the one it was handed poisons every
    capture it takes -- and a SECOND packer would reintroduce that by drift
    alone, which is why `set_event` calls this one and there is no other."""
    if pin not in EVT_PIN_NAMES:
        raise ValueError(
            f"evt pin {pin} is not a pin: nec_bus.sv decodes "
            f"{sorted(EVT_PIN_NAMES)} only "
            f"({', '.join(f'{k}={v}' for k, v in sorted(EVT_PIN_NAMES.items()))})"
            "; 3-7 fire the scheduler and drive nothing. The RTL deliberately "
            "neither traps nor remaps them -- a remap is the silent-"
            "substitution pattern that caused INV-1 -- so this is where it dies")
    if not 0 <= hold < (1 << RIG_EVT_HOLD_BITS):
        raise ValueError(
            f"evt hold {hold} does not fit the rig's "
            f"{RIG_EVT_HOLD_BITS}-bit register (max "
            f"{(1 << RIG_EVT_HOLD_BITS) - 1}); truncating it silently is "
            f"F46 and it is not done here")
    if not 0 <= delay < (1 << RIG_EVT_DELAY_BITS):
        raise ValueError(
            f"evt delay {delay} does not fit {RIG_EVT_DELAY_BITS} bits")
    v = ((delay & 0xFFFF) | ((hold & 0xFF) << 16) | ((pin & 7) << 24)
         | (((hold >> 8) & 0xF) << 27))
    if arm:
        v |= 1 << 31
    return v


def unpack_evt_cfg(word):
    """Inverse of `pack_evt_cfg`, for reading a scheduler back off the rig."""
    word &= 0xFFFFFFFF
    return {
        "delay": word & 0xFFFF,
        "hold":  ((word >> 16) & 0xFF) | (((word >> 27) & 0xF) << 8),
        "pin":   (word >> 24) & 7,
        "arm":   bool((word >> 31) & 1),
    }


def pack_evt_addr(addr):
    """EVT_ADDR (0x1C / 0x30 / 0x38): [19:0] linear CODE T1 trigger address.

    RAISES rather than masking. A truncated trigger address fires the scheduler
    on a different instruction -- the same defect as F46 wearing a different
    hat, and the readback (`{12'd0, evt_addr}`) cannot tell you it happened."""
    if not 0 <= addr < (1 << RIG_EVT_ADDR_BITS):
        raise ValueError(
            f"evt addr {addr:#x} does not fit the rig's "
            f"{RIG_EVT_ADDR_BITS}-bit trigger register "
            f"(max {(1 << RIG_EVT_ADDR_BITS) - 1:#x})")
    return addr


def pack_tvec(cs, ip):
    """TVEC (0x40): [15:0] IP, [31:16] CS -- the two words the NMI vector-read
    overlay serves at linear 0x00008 / 0x0000A while it is armed."""
    for name, v in (("cs", cs), ("ip", ip)):
        if not 0 <= v < (1 << 16):
            raise ValueError(f"tvec {name} {v:#x} does not fit 16 bits")
    return ((cs & 0xFFFF) << 16) | (ip & 0xFFFF)

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
            "pwr_good":    bool(s & ST_PWR_GOOD),
            "cpu_running": bool(s & ST_CPU_RUNNING),
            "cap_full":    bool(s & ST_CAP_FULL),
            # [5:3]: one bit per pin-event scheduler, sticky until it disarms
            "evt_fired":   (s >> ST_EVT_FIRED_S) & ((1 << EVT_N) - 1),
            # [6]: the NMI vector-read overlay actually served a CS half
            "vec_used":    bool(s & ST_VEC_USED),
            "cap_count":   self.read32(R_CAPCOUNT),
            "ctrl":        self.read32(R_CTRL),
            "cfg":         self.read32(R_CFG),
            "use_core":    bool(self.read32(R_CFG) & (1 << 25)),
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

    def load_iords(self, seq):
        """Load the per-IOR iords FIFO (INS / REP INS): reset, push each 16-bit
        value in order, enable. seq=None/empty resets+disables (scalar cfg_iord
        serves every IOR, byte-identical to the pre-FIFO path). Byte forms carry
        the value in both lanes; the caller pre-duplicates (see extract_iords)."""
        self.write32(R_IORDS_CTL, 0x1)                 # reset (clear ptr+count)
        if not seq:
            return
        for v in seq:
            self.write32(R_IORDS_PUSH, v & 0xFFFF)
        self.write32(R_IORDS_CTL, 0x2)                 # enable serving

    # ---- pin-event schedulers -----------------------------------------
    #
    # EVT_N independent schedulers, ONE register layout, ONE packer
    # (`pack_evt_cfg`).  `which` selects the scheduler and defaults to 0, so
    # every historical call site keeps meaning exactly what it meant.
    def set_event(self, addr=None, delay=0, hold=0, pin=EVT_PIN_INT, arm=True,
                  which=0, allow_pin_conflict=False, verify=False):
        """Arm pin-event scheduler `which`: on a CODE T1 at linear `addr`,
        wait `delay` CPU clocks, drive pin (0=INT 1=NMI 2=POLL_N) for `hold`
        clocks (0 = until disarmed). arm=False disarms.

        Packing, and every range guard, is `pack_evt_cfg` / `pack_evt_addr` --
        read those. Out-of-range RAISES; nothing here truncates.

        `allow_pin_conflict=False` (the default) REFUSES to arm this scheduler
        on a pin another scheduler is already armed on. The pins are OR-ed in
        `nec_bus.sv` and NMI recognition in the CPU is an EDGE latch
        (`hdl/rtl/ucore/v30u_eu.sv:297`), so two overlapping asserts produce ONE
        recognition -- silently, with nothing in the capture to say why. The
        hardware deliberately does not second-guess this; the host does.

        `verify=True` reads the pair back and raises `RigReadbackError` unless
        the rig holds exactly what it was handed."""
        r_addr, r_cfg = self._evt_regs(which)
        word = pack_evt_cfg(delay=delay, hold=hold, pin=pin, arm=arm)
        aw = None if addr is None else pack_evt_addr(addr)
        if arm and not allow_pin_conflict:
            self._refuse_pin_conflict(which, pin)
        if aw is not None:
            self.write32(r_addr, aw)
        self.write32(r_cfg, word)
        if verify:
            self._verify32(r_cfg, word, f"EVT_CFG[{which}]")
            if aw is not None:
                self._verify32(r_addr, aw, f"EVT_ADDR[{which}]")

    @staticmethod
    def _evt_regs(which):
        if which not in range(EVT_N):
            raise ValueError(
                f"scheduler index {which} out of range: the rig has "
                f"EVT_N={EVT_N} pin-event schedulers (0..{EVT_N - 1})")
        return EVT_REGS[which]

    def read_event(self, which=0):
        """Read scheduler `which` back off the rig: {addr, delay, hold, pin,
        arm}. EVT_ADDR reads back as {12'd0, addr[19:0]}, EVT_CFG bit for bit."""
        r_addr, r_cfg = self._evt_regs(which)
        d = unpack_evt_cfg(self.read32(r_cfg))
        d["addr"] = self.read32(r_addr) & ((1 << RIG_EVT_ADDR_BITS) - 1)
        return d

    def _refuse_pin_conflict(self, which, pin):
        for other in range(EVT_N):
            if other == which:
                continue
            d = self.read_event(other)
            if d["arm"] and d["pin"] == pin:
                raise ValueError(
                    f"scheduler {other} is already armed on pin {pin} "
                    f"({EVT_PIN_NAMES.get(pin, '?')}); arming scheduler "
                    f"{which} on it too OR-es the two drives onto one wire. "
                    f"NMI recognition is an EDGE latch, so overlapping asserts "
                    f"produce ONE recognition and the capture will not show "
                    f"why. Disarm {other} first, or pass "
                    f"allow_pin_conflict=True to say you meant it")

    def _verify32(self, off, want, name):
        got = self.read32(off)
        if got != want:
            raise RigReadbackError(
                f"{name} readback {got:#010x} != written {want:#010x} -- the "
                f"rig is not holding the directive it was handed (INV-1)")
        return got

    def event_fired(self, which=0):
        """True iff scheduler `which` fired (STATUS[3+which], sticky)."""
        self._evt_regs(which)               # bounds check, same table
        return bool(self.read32(R_STATUS) & (1 << (ST_EVT_FIRED_S + which)))

    def events_fired(self):
        """STATUS[5:3] as a mask, bit n = scheduler n fired."""
        return (self.read32(R_STATUS) >> ST_EVT_FIRED_S) & ((1 << EVT_N) - 1)

    def vec_used(self):
        """STATUS[6]: the NMI vector-read overlay actually served a CS half."""
        return bool(self.read32(R_STATUS) & ST_VEC_USED)

    # ---- termination-vector overlay -----------------------------------
    def set_term_vector(self, cs, ip, verify=False):
        """TVEC (0x40): the CS:IP the NMI vector-read overlay serves at linear
        0x00008 / 0x0000A while armed. Substituting the DATA (rather than
        redirecting to another slot or pre-writing the image) is what keeps the
        terminator working for a seed that scribbles the IVT."""
        word = pack_tvec(cs, ip)
        self.write32(R_TVEC, word)
        if verify:
            self._verify32(R_TVEC, word, "TVEC")
        return word

    def read_term_vector(self):
        """-> (cs, ip)."""
        v = self.read32(R_TVEC)
        return ((v >> 16) & 0xFFFF, v & 0xFFFF)

    def set_vecsub_en(self, mask, verify=False):
        """VECCTL (0x44): bit n = scheduler n's FIRE arms the NMI vector-read
        overlay. It is keyed on WHICH DIRECTIVE FIRED, not on which pin went
        high -- with EVT_N schedulers the NMI pin is an OR, and that is the only
        formulation under which a stimulus NMI and a terminating NMI coexist."""
        if not 0 <= mask < (1 << EVT_N):
            raise ValueError(
                f"vecsub_en mask {mask:#x} does not fit EVT_N={EVT_N} bits")
        self.write32(R_VECCTL, mask)
        if verify:
            self._verify32(R_VECCTL, mask, "VECCTL")
        return mask

    def read_vecsub_en(self):
        return self.read32(R_VECCTL) & ((1 << EVT_N) - 1)

    # ---- readback self-check ------------------------------------------
    def rig_readback_check(self, patterns=None):
        """Write a directive to every fuzz-v2 register, read it back, and RAISE
        on the first disagreement. Restores what it found. Run it once at the
        top of a session, while the harness is stopped: it is the cheap proof
        that the rig is applying the directives it is handed, which is the one
        thing INV-1 says nobody checked.

        Returns {register-name: written-word} on success."""
        if patterns is None:
            # two distinct values per field, so a stuck bit or a dropped
            # high-nibble (F46's exact signature) cannot pass both
            patterns = [
                dict(addr=0x00000, delay=0x0000, hold=0x001,
                     pin=EVT_PIN_INT, arm=True),
                dict(addr=0xFEDCB, delay=0xBEEF, hold=0xABC,
                     pin=EVT_PIN_POLL, arm=True),
            ]
        # save/restore as RAW WORDS: a decode-and-repack round trip through the
        # guards would refuse to put back anything the guards reject, and this
        # must leave the rig exactly as it found it
        saved = [(off, self.read32(off))
                 for pair in EVT_REGS for off in pair]
        saved += [(R_TVEC, self.read32(R_TVEC)),
                  (R_VECCTL, self.read32(R_VECCTL))]
        out = {}
        try:
            for n in range(EVT_N):
                r_addr, r_cfg = EVT_REGS[n]
                for p in patterns:
                    # allow_pin_conflict: this is a register test, no run
                    self.set_event(which=n, allow_pin_conflict=True,
                                   verify=True, **p)
                    out[f"EVT_ADDR[{n}]"] = pack_evt_addr(p["addr"])
                    out[f"EVT_CFG[{n}]"] = pack_evt_cfg(
                        delay=p["delay"], hold=p["hold"], pin=p["pin"],
                        arm=p["arm"])
                    got = self.read_event(n)
                    for k, want in p.items():
                        if got[k] != want:
                            raise RigReadbackError(
                                f"EVT[{n}] field {k}: rig holds {got[k]!r}, "
                                f"handed {want!r} (readback word "
                                f"{self.read32(r_cfg):#010x} / addr "
                                f"{self.read32(r_addr):#010x})")
            for cs, ip in ((0x0000, 0xFFFF), (0xBEEF, 0x1234)):
                out["TVEC"] = self.set_term_vector(cs, ip, verify=True)
                if self.read_term_vector() != (cs, ip):
                    raise RigReadbackError(
                        f"TVEC: rig holds {self.read_term_vector()}, handed "
                        f"{(cs, ip)}")
            for m in range(1 << EVT_N):
                out["VECCTL"] = self.set_vecsub_en(m, verify=True)
                if self.read_vecsub_en() != m:
                    raise RigReadbackError(
                        f"VECCTL: rig holds {self.read_vecsub_en():#x}, "
                        f"handed {m:#x}")
        finally:
            for off, word in saved:
                self.write32(off, word)
        return out

    def set_cfg(self, div=None, waits=None, vector=None, small=None,
                use_core=None):
        v = self.read32(R_CFG)
        if div is not None:    v = (v & ~0x3F) | (div & 0x3F)
        if waits is not None:  v = (v & ~0xF00) | ((waits & 0xF) << 8)
        if vector is not None: v = (v & ~0xFF0000) | ((vector & 0xFF) << 16)
        if small is not None:  v = (v & ~(1 << 24)) | ((1 if small else 0) << 24)
        # Campaign 4 A/B selector: bit 25 = use_core (1 = internal v30_core)
        if use_core is not None:
            v = (v & ~(1 << 25)) | ((1 if use_core else 0) << 25)
        self.write32(R_CFG, v)

    def set_wrand(self, enable=None, wmax=None, seed=None, replay=None):
        """Per-access wait insertion (WRAND, 0x24), large mode, overriding
        CFG.wait_states. enable=1 draws each bus cycle's Tw from a seeded LFSR
        over 0..wmax; replay=1 applies the host wait-vector RAM instead
        (replay > rand > uniform). The same seed/vector drives READY for both
        A/B positions, so a run applies the identical wait pattern to chip and
        fabric core. Set only while stopped."""
        v = self.read32(R_WRAND)
        if enable is not None: v = (v & ~0x1) | (1 if enable else 0)
        if replay is not None: v = (v & ~0x2) | (2 if replay else 0)
        if wmax   is not None: v = (v & ~0xF0) | ((wmax & 0xF) << 4)
        if seed   is not None: v = (v & ~0xFFFF0000) | ((seed & 0xFFFF) << 16)
        self.write32(R_WRAND, v)

    def load_wvec(self, tw_list):
        """Load an exact per-bus-cycle Tw sequence into the replay RAM
        (0x140000). Entry k = wait count for bus cycle k (0..255). Packed 4
        per 32-bit word, little end first (byte lane = bus_idx[1:0]). Applied
        when WRAND.replay is set. Write only while the harness is stopped."""
        tw = list(tw_list)
        tw += [0] * ((-len(tw)) % 4)
        words = [tw[i] | (tw[i + 1] << 8) | (tw[i + 2] << 16) | (tw[i + 3] << 24)
                 for i in range(0, len(tw), 4)]
        data = struct.pack(f"<{len(words)}I", *words)
        ch = 1024
        for i in range(0, len(data), ch):
            end = min(i + ch, len(data))
            self.win[WVEC_OFF + i: WVEC_OFF + end] = data[i:end]


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

    v3 additions (banner `OK SERVE v3`; the client negotiates on the version
    number, so a v2 board still serves a v2 client and vice versa):
      * every EVT/TVEC/VECCTL write on the RUN path is made with
        `verify=True` -- read back off the rig and RAISE on a disagreement;
      * the reply's OK line carries two trailing `k=v` tokens,
        `vec=<STATUS[6]>` and `rb=<raw register readback>`, sampled after the
        directive is programmed and BEFORE the CPU is released.  The client
        repacks what it SENT with this module's packers and compares.  This is
        INV-1's actual lesson: the failure was not a register width, it was
        that nothing on the capture path ever asked the rig what it held.
      * `pinok=1` opts a RUN into schedulers sharing a pin.
      * `RBCHECK` runs `rig_readback_check()` on the board and reports.
    """
    import base64
    import zlib
    out = sys.stdout
    base_img = None          # cached baseline (bytearray)

    def reply(s):
        out.write(s + "\n")
        out.flush()

    def do_run(img, timeout, evts, iord, pins, cap, crc, iords=None,
               tvec=None, vecsub=0, pinok=False):
        h.stop()
        h.load_mem(img, 0)
        h.set_iord(iord)
        h.load_iords(iords)        # per-IOR sequence (INS); None -> scalar iord
        h.write32(R_PINS, pins)
        # DISARM EVERY scheduler first, then arm the ones this run asked for:
        # the same-pin refusal reads the rig, so it must see this run's state
        # and not the previous run's leftovers
        for n in range(EVT_N):
            h.set_event(arm=False, which=n)
        for n, e in enumerate(evts):
            if e:
                # `verify=True`: read the pair back off the rig BEFORE the CPU
                # is released and RAISE on a disagreement.  INV-1's root cause
                # was not a register width -- it was that the rig silently
                # applied a directive other than the one it was handed, and
                # 760 banked seeds were scored against it.  Verification on
                # the RUN path is the only place that cannot be skipped.
                h.set_event(addr=e[0], delay=e[1], hold=e[2], pin=e[3],
                            which=n, verify=True,
                            allow_pin_conflict=pinok)
        h.set_term_vector(*(tvec or (0, 0)), verify=True)
        h.set_vecsub_en(vecsub, verify=True)
        # THE READBACK THE HOST SCORES ON.  Sampled here -- after the whole
        # directive is programmed and before `start()` -- because the run's
        # epilogue disarms everything, so a readback taken afterwards would
        # prove nothing.  Raw 32-bit words: the client repacks what it SENT
        # with this module's own packers and compares.  It is deliberately not
        # a decoded summary; a decode on both sides could agree while the
        # register disagreed.
        rb = ",".join(f"{h.read32(a):08x}:{h.read32(c):08x}"
                      for a, c in EVT_REGS)
        rb += f",{h.read32(R_TVEC):08x},{h.read32(R_VECCTL):08x}"
        h.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if h.status()["cap_full"]:
                break
            time.sleep(0.002)
        st = h.status()
        # STATUS[5:3], bit n = scheduler n fired.  Sampled before host_reset:
        # it clears on reset.  With one scheduler this was 0/1 and it still is,
        # so `bool(int(field))` -- "did anything fire" -- is unchanged.
        fired = st["evt_fired"]
        # STATUS[6]: the NMI vector-read overlay actually SERVED a CS half.
        # Sampled at the same instant as `fired`, for the same reason.
        vec_used = int(bool(st["vec_used"]))
        h.stop()
        for n in range(EVT_N):
            h.set_event(arm=False, which=n)
        h.set_vecsub_en(0)
        h.write32(R_PINS, 0)
        recs = h.dump_capture(cap)
        blob = struct.pack(f"<{len(recs)}Q", *recs)
        tail = f" {crc:08x}" if crc is not None else ""
        # v3 TOKENS, appended after the positional fields (and after the DELTA
        # crc): `vec=` is STATUS[6] and `rb=` is the pre-start register
        # readback.  A pre-v3 client splits on whitespace and indexes fields
        # 3/4, so trailing `k=v` tokens are inert to it; a v3 client REQUIRES
        # `rb=` and refuses a run that does not carry one.
        reply(f"OK {st['cap_count']} {int(st['cap_full'])} {fired}{tail}"
              f" vec={vec_used} rb={rb}")
        reply(base64.b64encode(blob).decode())

    # evt / evt2 / evt3 -> scheduler 0 / 1 / 2.  ONE parse, one table: the
    # option names differ, the grammar does not.
    EVT_OPT = {f"evt{n + 1}" if n else "evt": n for n in range(EVT_N)}

    def parse_opts(parts):
        timeout = float(parts[1]) if len(parts) > 1 else 3.0
        iord, pins, cap, iords = 0xFFFF, 0, CAP_RECORDS, None
        evts = [None] * EVT_N
        tvec, vecsub, pinok = None, 0, False
        for kv in parts[2:]:
            k, _, v = kv.partition("=")
            if k in EVT_OPT:
                a, d, ho, p = v.split(":")
                evts[EVT_OPT[k]] = (int(a, 16), int(d), int(ho), int(p))
            elif k == "tvec":
                cs, ip = v.split(":")
                tvec = (int(cs, 16), int(ip, 16))
            elif k == "vecsub":
                vecsub = int(v, 16)
            elif k == "pinok":
                # THE CALLER SAYS IT MEANT IT.  `set_event`'s default REFUSES
                # to arm two schedulers on one pin, because the pins are OR-ed
                # and NMI recognition is an edge latch, so an ACCIDENTAL
                # overlap produces one recognition with nothing in the capture
                # to say why.  A stimulus NMI plus a TERMINATING NMI is the one
                # configuration where the overlap is the design (the overlay is
                # keyed on WHICH DIRECTIVE FIRED, not on which pin went high --
                # `set_vecsub_en`), so it is opted into explicitly, per RUN, and
                # never inferred from the presence of a `vecsub` mask.
                pinok = bool(int(v, 0))
            elif k == "iord":
                iord = int(v, 16)
            elif k == "iords":
                # per-IOR ordered sequence (INS / REP INS), comma-separated hex
                iords = [int(x, 16) for x in v.split(",")] if v else []
            elif k == "pins":
                pins = int(v, 16)
            elif k == "cap":
                cap = max(1, min(int(v), CAP_RECORDS))
            else:
                raise ValueError(f"unknown option {k!r}")
        return timeout, evts, iord, pins, cap, iords, tvec, vecsub, pinok

    reply("OK SERVE v3")
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
                # CFG <div> <waits> <vector> <small> [use_core]  ('-' keeps)
                vals = [None if p == "-" else int(p, 0) for p in parts[1:6]]
                h.stop()
                h.set_cfg(*vals)
                reply("OK CFG")
            elif parts[0] == "WRAND":
                # WRAND <randen> <wmax> <seed> <replay>  ('-' keeps a field).
                # Seeded random / replay per-access waits; identical across A/B.
                raw = parts[1:5]
                vals = [None if p == "-" else int(p, 0) for p in raw]
                while len(vals) < 4:
                    vals.append(None)
                h.stop()
                h.set_wrand(vals[0], vals[1], vals[2], vals[3])
                reply("OK WRAND")
            elif parts[0] == "WVEC":
                # WVEC\n<base64 raw Tw bytes>  load the replay wait-vector RAM
                blob = base64.b64decode(sys.stdin.readline().strip())
                h.stop()
                h.load_wvec(list(blob))
                reply(f"OK WVEC {len(blob)}")
            elif parts[0] == "RBCHECK":
                # v3: run `rig_readback_check()` ON THE BOARD and report.  The
                # per-RUN `verify=True` above proves the rig held THIS run's
                # directive; this proves the registers round-trip two distinct
                # values per field, which is the stuck-bit / dropped-nibble
                # case a single directive can pass by luck.  Restores what it
                # found; run while stopped, at the top of a session.
                h.stop()
                # NOT named `out`: `reply` closes over serve's `out`, which is
                # stdout, and rebinding it here kills the transport
                rbc = h.rig_readback_check()
                reply(f"OK RBCHECK {len(rbc)} " + ",".join(sorted(rbc)))
            elif parts[0] == "BASE":
                base_img = bytearray(
                    base64.b64decode(sys.stdin.readline().strip()))
                reply(f"OK BASE {zlib.crc32(base_img) & 0xFFFFFFFF:08x}")
            elif parts[0] == "DELTA":
                (timeout, evts, iord, pins, cap, iords,
                 tvec, vecsub, pinok) = parse_opts(parts)
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
                do_run(bytes(img), timeout, evts, iord, pins, cap, crc, iords,
                       tvec, vecsub, pinok)
            elif parts[0] == "RUN":
                (timeout, evts, iord, pins, cap, iords,
                 tvec, vecsub, pinok) = parse_opts(parts)
                img = base64.b64decode(sys.stdin.readline().strip())
                do_run(img, timeout, evts, iord, pins, cap, None, iords,
                       tvec, vecsub, pinok)
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
    p.add_argument("--use-core", type=int, choices=(0, 1),
                   help="A/B: 1 = internal v30_core, 0 = socketed chip")
    p.add_argument("--wrand", type=int, choices=(0, 1),
                   help="seeded random per-access waits (large mode)")
    p.add_argument("--wmax", type=lambda x: int(x, 0),
                   help="max Tw per access in random mode (0..15)")
    p.add_argument("--wseed", type=lambda x: int(x, 0),
                   help="random-wait PRNG seed (16-bit; 0 -> 0xACE1)")
    p.add_argument("--replay", type=int, choices=(0, 1),
                   help="apply the host wait-vector replay RAM (Phase 2a)")
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
        h.set_cfg(args.div, args.waits, args.vector, args.small, args.use_core)
        if args.wrand is not None or args.wmax is not None \
                or args.wseed is not None or args.replay is not None:
            h.set_wrand(args.wrand, args.wmax, args.wseed, args.replay)
        print(f"cfg = {h.read32(R_CFG):08x} wrand = {h.read32(R_WRAND):08x} "
              f"(harness stopped; 'start' to run)")
    elif args.cmd == "serve":
        serve(h)


if __name__ == "__main__":
    main()
