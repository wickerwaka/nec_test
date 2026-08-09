#!/usr/bin/env python3
"""T8 offline gate -- `sw/v30ctl.py`'s fuzz-v2 host side against the RTL's own
decode.  No board, no /dev/mem, no bitstream.

    python3 sw/t8_v30ctl_gate.py        # rc 0 = pass

`RtlDecode` below is transcribed from `hdl/rtl/hps_axi_slave.sv` AS T5 LEFT IT
-- the write case at :322-379, the read case at :464-496 and the EVTn decode
table at :225-238 -- and from nothing else.  It is the RTL, not the design
brief and not v30ctl, so a v30ctl bug cannot hide inside a shared assumption.
Every register bit is checked twice: once by v30ctl's packer on the way in,
once by the RTL's readback pack on the way out.

`ModelHarness` redirects `Harness.read32`/`write32` at that model and stubs
NOTHING else: `set_event`, `read_event`, `set_term_vector`, `set_vecsub_en`,
`rig_readback_check`, `status` and `serve()` are the shipped code.
"""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v30ctl as V



# ---------------------------------------------------------------------------
# hps_axi_slave.sv, transcribed
# ---------------------------------------------------------------------------
class RtlDecode:
    """The register file and the decode, as the RTL writes them.

    ev_sel / ev_is_addr / ev_is_cfg  -- hps_axi_slave.sv:225-238
      8'h1C -> sel 0 addr   8'h20 -> sel 0 cfg
      8'h30 -> sel 1 addr   8'h34 -> sel 1 cfg
      8'h38 -> sel 2 addr   8'h3C -> sel 2 cfg
    """
    EV = {0x1C: (0, "a"), 0x20: (0, "c"),
          0x30: (1, "a"), 0x34: (1, "c"),
          0x38: (2, "a"), 0x3C: (2, "c")}
    N = 3

    def __init__(self):
        # the RTL's reset values, hps_axi_slave.sv:280-286
        self.evt_addr = [0] * self.N     # [19:0] each
        self.evt_delay = [0] * self.N    # [15:0]
        self.evt_hold = [0] * self.N     # [11:0]
        self.evt_pin = [0] * self.N      # [2:0]
        self.evt_arm = [0] * self.N      # [0]
        self.evt_vecsub_en = 0           # [2:0]
        self.cfg_tvec = 0                # [31:0]
        # STATUS inputs, driven by nec_bus
        self.evt_fired = 0
        self.vec_used = 0
        self.other = {}                  # registers this model does not model

    def write(self, off8, wdata):
        wdata &= 0xFFFFFFFF
        if off8 == 0x40:                                   # :365
            self.cfg_tvec = wdata
        elif off8 == 0x44:                                 # :366
            self.evt_vecsub_en = wdata & ((1 << self.N) - 1)
        elif off8 in self.EV:                              # :368-378, default
            sel, kind = self.EV[off8]
            if kind == "a":
                self.evt_addr[sel] = wdata & 0xFFFFF       # wdata[19:0]
            else:
                self.evt_delay[sel] = wdata & 0xFFFF       # wdata[15:0]
                # {wdata[30:27], wdata[23:16]}
                self.evt_hold[sel] = (((wdata >> 27) & 0xF) << 8) \
                    | ((wdata >> 16) & 0xFF)
                self.evt_pin[sel] = (wdata >> 24) & 0x7    # wdata[26:24]
                self.evt_arm[sel] = (wdata >> 31) & 0x1    # wdata[31]
        else:
            self.other[off8] = wdata

    def read(self, off8):
        if off8 == 0x00:
            return 0x56333031
        if off8 == 0x10:                                   # :471-472
            # {25'd0, vec_used, evt_fired, cap_full, cpu_running, pwr_good}
            return ((self.vec_used & 1) << 6) \
                | ((self.evt_fired & 0x7) << 3) \
                | (self.other.get("status_low", 0) & 0x7)
        if off8 == 0x40:                                   # :478
            return self.cfg_tvec
        if off8 == 0x44:                                   # :479
            return self.evt_vecsub_en & ((1 << self.N) - 1)
        if off8 in self.EV:                                # :484-495
            sel, kind = self.EV[off8]
            if kind == "a":
                return self.evt_addr[sel] & 0xFFFFF        # {12'd0, evt_addr}
            # {arm, hold[11:8], pin, hold[7:0], delay}
            return ((self.evt_arm[sel] & 1) << 31) \
                | (((self.evt_hold[sel] >> 8) & 0xF) << 27) \
                | ((self.evt_pin[sel] & 0x7) << 24) \
                | ((self.evt_hold[sel] & 0xFF) << 16) \
                | (self.evt_delay[sel] & 0xFFFF)
        return self.other.get(off8, 0)


class ModelHarness(V.Harness):
    """v30ctl.Harness with its two primitives redirected at RtlDecode.

    Nothing else is stubbed: set_event / read_event / set_term_vector /
    set_vecsub_en / rig_readback_check / status are the shipped code."""

    def __init__(self):
        self.rtl = RtlDecode()

    def read32(self, off):
        assert off >= V.REG_OFF, f"non-register read {off:#x}"
        return self.rtl.read(off - V.REG_OFF)

    def write32(self, off, val):
        assert off >= V.REG_OFF, f"non-register write {off:#x}"
        self.rtl.write(off - V.REG_OFF, val)







FAIL = []


def check(name, got, want):
    ok = got == want
    if not ok:
        FAIL.append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r} want {want!r}")


def raises(name, fn, want_type=ValueError):
    try:
        fn()
    except want_type as e:
        print(f"  PASS  {name}: raised {type(e).__name__}: "
              f"{str(e).splitlines()[0][:110]}")
        return
    except Exception as e:                                   # noqa: BLE001
        FAIL.append(name)
        print(f"  FAIL  {name}: raised {type(e).__name__} not {want_type.__name__}: {e}")
        return
    FAIL.append(name)
    print(f"  FAIL  {name}: DID NOT RAISE")


# ---------------------------------------------------------------------------
print("=" * 78)
print("G1  offsets: v30ctl vs the RTL's decode table")
print("=" * 78)
for name, off, want8 in [
        ("R_EVT_ADDR", V.R_EVT_ADDR, 0x1C), ("R_EVT_CFG", V.R_EVT_CFG, 0x20),
        ("R_EVT2_ADDR", V.R_EVT2_ADDR, 0x30), ("R_EVT2_CFG", V.R_EVT2_CFG, 0x34),
        ("R_EVT3_ADDR", V.R_EVT3_ADDR, 0x38), ("R_EVT3_CFG", V.R_EVT3_CFG, 0x3C),
        ("R_TVEC", V.R_TVEC, 0x40), ("R_VECCTL", V.R_VECCTL, 0x44)]:
    check(f"{name} = REG_OFF+{want8:#04x}", off - V.REG_OFF, want8)
check("EVT_N", V.EVT_N, RtlDecode.N)
check("EVT_REGS table", V.EVT_REGS,
      ((V.R_EVT_ADDR, V.R_EVT_CFG), (V.R_EVT2_ADDR, V.R_EVT2_CFG),
       (V.R_EVT3_ADDR, V.R_EVT3_CFG)))

print()
print("=" * 78)
print("G2  round trip: host packer -> RTL write unpack -> RTL readback pack")
print("=" * 78)
# exhaustive over the field EXTREMES plus a walking-1 sweep of every bit of
# every field, on every scheduler.  Every bit of EVT_CFG is spoken for, so a
# walking 1 over delay/hold plus all legal pins plus both arm values covers it.
DIRECTIVES = []
for pin in (0, 1, 2):
    for arm in (True, False):
        DIRECTIVES.append(dict(addr=0, delay=0, hold=0, pin=pin, arm=arm))
        DIRECTIVES.append(dict(addr=(1 << 20) - 1, delay=0xFFFF,
                               hold=(1 << 12) - 1, pin=pin, arm=arm))
for b in range(20):
    DIRECTIVES.append(dict(addr=1 << b, delay=0, hold=0, pin=1, arm=True))
for b in range(16):
    DIRECTIVES.append(dict(addr=0, delay=1 << b, hold=0, pin=2, arm=True))
for b in range(12):
    DIRECTIVES.append(dict(addr=0, delay=0, hold=1 << b, pin=0, arm=True))
# the F46 signature specifically: a hold whose high nibble is non-zero
DIRECTIVES.append(dict(addr=0x00400, delay=44, hold=300, pin=1, arm=True))
DIRECTIVES.append(dict(addr=0x0BEEF, delay=0xCAFE, hold=0xFFF, pin=0, arm=True))

h = ModelHarness()
bad = 0
for which in range(V.EVT_N):
    for d in DIRECTIVES:
        h.set_event(which=which, allow_pin_conflict=True, verify=True, **d)
        got = h.read_event(which)
        if got != {**d, "arm": bool(d["arm"])}:
            bad += 1
            print(f"  FAIL  sched {which} {d} -> {got}")
check(f"EVT round trip, {len(DIRECTIVES)} directives x {V.EVT_N} schedulers "
      f"({len(DIRECTIVES) * V.EVT_N} cases), verify=True on every one",
      bad, 0)

# and prove the RTL's readback WORD is bit-identical to what the host packed
badw = 0
for which in range(V.EVT_N):
    r_addr, r_cfg = V.EVT_REGS[which]
    for d in DIRECTIVES:
        h.set_event(which=which, allow_pin_conflict=True, **d)
        want = V.pack_evt_cfg(delay=d["delay"], hold=d["hold"], pin=d["pin"],
                              arm=d["arm"])
        if h.read32(r_cfg) != want or h.read32(r_addr) != d["addr"]:
            badw += 1
check("EVT_CFG/EVT_ADDR readback words bit-identical to the host's pack",
      badw, 0)

print()
print("  bit table, one directive, derived from the RTL model:")
h.set_event(which=1, addr=0xFEDCB, delay=0xCAFE, hold=0xABC, pin=2, arm=True,
            allow_pin_conflict=True)
w = h.read32(V.R_EVT2_CFG)
print(f"    host pack_evt_cfg(delay=0xCAFE, hold=0xABC, pin=2, arm=1) = "
      f"{V.pack_evt_cfg(delay=0xCAFE, hold=0xABC, pin=2, arm=True):#010x}")
print(f"    RTL EVT2_CFG readback                                     = {w:#010x}")
print(f"      [15:0]  delay      = {w & 0xFFFF:#06x}   (want 0xcafe)")
print(f"      [23:16] hold[7:0]  = {(w >> 16) & 0xFF:#04x}     (want 0xbc)")
print(f"      [26:24] pin        = {(w >> 24) & 7}        (want 2 = POLL_N)")
print(f"      [30:27] hold[11:8] = {(w >> 27) & 0xF:#x}      (want 0xa)")
print(f"      [31]    arm        = {(w >> 31) & 1}        (want 1)")
print(f"    RTL EVT2_ADDR readback = {h.read32(V.R_EVT2_ADDR):#010x} "
      f"(want 0x000fedcb, upper 12 bits read 0)")

print()
print("=" * 78)
print("G3  TVEC and VECCTL round trip")
print("=" * 78)
bad = 0
for cs in (0x0000, 0x0001, 0x8000, 0xFFFF, 0xBEEF):
    for ip in (0x0000, 0x0001, 0x8000, 0xFFFF, 0x1234):
        h.set_term_vector(cs, ip, verify=True)
        if h.read_term_vector() != (cs, ip):
            bad += 1
check("TVEC round trip over 25 (cs, ip) pairs, verify=True", bad, 0)
h.set_term_vector(0xBEEF, 0x1234)
check("TVEC word = {CS, IP}", f"{h.read32(V.R_TVEC):#010x}", "0xbeef1234")
bad = 0
for m in range(1 << V.EVT_N):
    h.set_vecsub_en(m, verify=True)
    if h.read_vecsub_en() != m:
        bad += 1
check("VECCTL round trip over all 8 masks, verify=True", bad, 0)

print()
print("=" * 78)
print("G4  STATUS decode vs {25'd0, vec_used, evt_fired, cap_full, "
      "cpu_running, pwr_good}")
print("=" * 78)
bad = 0
for fired in range(8):
    for vu in (0, 1):
        h.rtl.evt_fired, h.rtl.vec_used = fired, vu
        h.rtl.other["status_low"] = 0b111
        st = h.status()
        want = dict(pwr_good=True, cpu_running=True, cap_full=True,
                    evt_fired=fired, vec_used=bool(vu))
        if {k: st[k] for k in want} != want:
            bad += 1
            print(f"  FAIL  fired={fired} vec_used={vu} -> {st}")
        if h.events_fired() != fired or h.vec_used() != bool(vu):
            bad += 1
        for n in range(V.EVT_N):
            if h.event_fired(n) != bool(fired & (1 << n)):
                bad += 1
check("STATUS decode over all 16 (evt_fired, vec_used) combinations", bad, 0)
h.rtl.other["status_low"] = 0

print()
print("=" * 78)
print("G5  NEGATIVE CONTROLS -- each must raise")
print("=" * 78)
g = ModelHarness()
raises("pin=3", lambda: g.set_event(addr=0, pin=3))
raises("pin=7", lambda: g.set_event(addr=0, pin=7))
raises("pin=-1", lambda: g.set_event(addr=0, pin=-1))
raises("pack_evt_cfg(pin=3) direct", lambda: V.pack_evt_cfg(pin=3))
raises("hold=4096 (beyond 12 bits)", lambda: g.set_event(addr=0, hold=4096))
raises("hold=-1", lambda: g.set_event(addr=0, hold=-1))
raises("delay=65536 (beyond 16 bits)", lambda: g.set_event(addr=0, delay=65536))
raises("delay=-1", lambda: g.set_event(addr=0, delay=-1))
raises("addr=0x100000 (beyond 20 bits)", lambda: g.set_event(addr=0x100000))
raises("which=3 (EVT_N=3)", lambda: g.set_event(addr=0, which=3))
raises("which=-1", lambda: g.set_event(addr=0, which=-1))
raises("vecsub mask=8 (beyond EVT_N bits)", lambda: g.set_vecsub_en(8))
raises("tvec cs=0x10000", lambda: g.set_term_vector(0x10000, 0))
raises("tvec ip=0x10000", lambda: g.set_term_vector(0, 0x10000))

print("  -- same-pin overlap --")
g = ModelHarness()
g.set_event(which=0, addr=0x00400, delay=10, hold=50, pin=V.EVT_PIN_NMI)
raises("scheduler 1 armed on NMI while 0 is armed on NMI",
       lambda: g.set_event(which=1, addr=0x00500, delay=20, hold=50,
                           pin=V.EVT_PIN_NMI))
raises("scheduler 2 armed on NMI while 0 is armed on NMI",
       lambda: g.set_event(which=2, addr=0x00600, delay=20, hold=50,
                           pin=V.EVT_PIN_NMI))
g.set_event(which=1, addr=0x00500, delay=20, hold=50, pin=V.EVT_PIN_INT)
raises("scheduler 2 armed on INT while 1 is armed on INT",
       lambda: g.set_event(which=2, addr=0x00600, delay=20, hold=50,
                           pin=V.EVT_PIN_INT))

print("  -- and the POSITIVE controls, without which the refusal proves nothing --")
g = ModelHarness()
g.set_event(which=0, addr=0x00400, delay=10, hold=50, pin=V.EVT_PIN_NMI)
g.set_event(which=1, addr=0x00500, delay=20, hold=60, pin=V.EVT_PIN_INT)
g.set_event(which=2, addr=0x00600, delay=30, hold=70, pin=V.EVT_PIN_POLL)
check("three schedulers on three DIFFERENT pins are accepted",
      [g.read_event(n)["pin"] for n in range(3)], [1, 0, 2])
g2 = ModelHarness()
g2.set_event(which=0, addr=0x00400, delay=10, hold=50, pin=V.EVT_PIN_NMI)
g2.set_event(which=1, addr=0x00500, delay=20, hold=50, pin=V.EVT_PIN_NMI,
             allow_pin_conflict=True)
check("allow_pin_conflict=True accepts the same pin",
      [g2.read_event(n)["arm"] for n in (0, 1)], [True, True])
g3 = ModelHarness()
g3.set_event(which=0, addr=0x00400, delay=10, hold=50, pin=V.EVT_PIN_NMI)
g3.set_event(which=0, arm=False)
g3.set_event(which=1, addr=0x00500, delay=20, hold=50, pin=V.EVT_PIN_NMI)
check("disarming 0 frees NMI for 1", g3.read_event(1)["arm"], True)
g4 = ModelHarness()
g4.set_event(which=0, addr=0x00400, delay=10, hold=50, pin=V.EVT_PIN_NMI)
g4.set_event(which=0, addr=0x00700, delay=11, hold=51, pin=V.EVT_PIN_NMI)
check("re-arming the SAME scheduler on its own pin is not a conflict",
      g4.read_event(0)["addr"], 0x700)

print()
print("=" * 78)
print("G6  rig_readback_check + verify=True falsifier (non-vacuity)")
print("=" * 78)
g = ModelHarness()
g.set_event(which=0, addr=0x123, delay=7, hold=9, pin=V.EVT_PIN_NMI)
g.set_term_vector(0x1111, 0x2222)
g.set_vecsub_en(0b101)
before = [g.read32(o) for pair in V.EVT_REGS for o in pair] \
    + [g.read32(V.R_TVEC), g.read32(V.R_VECCTL)]
out = g.rig_readback_check()
after = [g.read32(o) for pair in V.EVT_REGS for o in pair] \
    + [g.read32(V.R_TVEC), g.read32(V.R_VECCTL)]
check("rig_readback_check passes on a faithful rig", len(out) > 0, True)
check("rig_readback_check restores every register it touched", after, before)


class TruncatingHarness(ModelHarness):
    """A rig with F46 back in it: EVT_CFG's hold high nibble is dropped."""
    def write32(self, off, val):
        if off in (V.R_EVT_CFG, V.R_EVT2_CFG, V.R_EVT3_CFG):
            val &= ~(0xF << 27)
        super().write32(off, val)


t = TruncatingHarness()
raises("verify=True catches an F46-style silent truncation",
       lambda: t.set_event(addr=0x400, delay=44, hold=300,
                           pin=V.EVT_PIN_NMI, verify=True),
       V.RigReadbackError)
t = TruncatingHarness()
raises("rig_readback_check catches it too",
       lambda: t.rig_readback_check(), V.RigReadbackError)
t = TruncatingHarness()
check("...and verify=False does NOT (so the check is doing the work)",
      (t.set_event(addr=0x400, delay=44, hold=300, pin=V.EVT_PIN_NMI),
       t.read_event(0)["hold"]), (None, 44))


class DeadTvecHarness(ModelHarness):
    def write32(self, off, val):
        if off in (V.R_TVEC, V.R_VECCTL):
            return
        super().write32(off, val)


raises("rig_readback_check catches a dead TVEC/VECCTL",
       lambda: DeadTvecHarness().rig_readback_check(), V.RigReadbackError)

print()
print("=" * 78)
print("G7  scheduler 0's historical calling convention is bit-for-bit unchanged")
print("=" * 78)
a, b = ModelHarness(), ModelHarness()
for d in [dict(addr=0x00400, delay=44, hold=300, pin=1, arm=True),
          dict(addr=0x00500, delay=0, hold=0, pin=0, arm=True),
          dict(arm=False)]:
    a.set_event(**d)                       # no `which` -> scheduler 0
    b.set_event(which=0, **d)
check("set_event(...) == set_event(which=0, ...) on every register",
      (a.read32(V.R_EVT_ADDR), a.read32(V.R_EVT_CFG)),
      (b.read32(V.R_EVT_ADDR), b.read32(V.R_EVT_CFG)))
# and against the pre-T8 packing expression, transcribed from git HEAD
for delay, hold, pin, arm in [(44, 300, 1, True), (0, 0, 0, False),
                              (0xFFFF, 0xFFF, 2, True), (1, 255, 0, True)]:
    old = ((delay & 0xFFFF) | ((hold & 0xFF) << 16) | ((pin & 7) << 24)
           | (((hold >> 8) & 0xF) << 27)) | ((1 << 31) if arm else 0)
    check(f"pack_evt_cfg == pre-T8 expression (d={delay} h={hold} p={pin} "
          f"a={int(arm)})",
          V.pack_evt_cfg(delay=delay, hold=hold, pin=pin, arm=arm), old)

print()


class ServeHarness(ModelHarness):
    """ModelHarness plus the run-loop stubs serve() calls. Registers are the
    real thing; memory/capture/start/stop are inert."""
    def __init__(self):
        super().__init__()
        self.trace = []
        self.snapshots = []

    def stop(self):
        self.trace.append("stop")

    def start(self, power_wait=False):
        # snapshot the register file at the instant the CPU is released --
        # this is the only moment the directive actually matters
        self.snapshots.append({
            "evt": [self.read_event(n) for n in range(V.EVT_N)],
            "tvec": self.read_term_vector(),
            "vecsub": self.read_vecsub_en(),
            "pins": self.read32(V.R_PINS),
            "iord": self.read32(V.R_IORD),
        })
        # pretend schedulers 0 and 2 fired and the overlay served
        self.rtl.evt_fired = 0b101
        self.rtl.vec_used = 1

    def status(self):
        s = super().status()
        s["cap_full"] = True
        s["cap_count"] = 7
        return s

    def load_mem(self, data, addr=0):
        self.trace.append(f"load {len(data)}")

    def load_iords(self, seq):
        pass

    def set_iord(self, val):
        self.write32(V.R_IORD, val & 0xFFFF)

    def dump_capture(self, count=V.CAP_RECORDS):
        return [0] * count


def run_serve(lines):
    h = ServeHarness()
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO("".join(l + "\n" for l in lines))
    sys.stdout = io.StringIO()
    try:
        V.serve(h)
        return h, sys.stdout.getvalue().splitlines()
    finally:
        sys.stdin, sys.stdout = old_in, old_out


img = base64.b64encode(b"\xf4" * 8).decode()


def run_hdr(out):
    """The RUN/DELTA reply's OK line -- never the banner.  T11 bumped the
    banner to `OK SERVE v3`, and a filter written as `!= "OK SERVE v2"` would
    silently start returning the banner instead of the reply."""
    return [l for l in out
            if l.startswith("OK ") and not l.startswith("OK SERVE")][0]


print("=" * 78)
print("S1  three schedulers + tvec + vecsub through one RUN line")
print("=" * 78)
h, out = run_serve([
    "RUN 0.01 evt=00400:10:50:0 evt2=00500:20:60:1 evt3=00600:30:70:2 "
    "tvec=beef:1234 vecsub=4 cap=2",
    img, "EXIT"])
print("  reply lines:", [l[:60] for l in out if not l.startswith("AAAA")][:4])
snap = h.snapshots[0]
check("scheduler 0", snap["evt"][0],
      dict(addr=0x400, delay=10, hold=50, pin=0, arm=True))
check("scheduler 1", snap["evt"][1],
      dict(addr=0x500, delay=20, hold=60, pin=1, arm=True))
check("scheduler 2", snap["evt"][2],
      dict(addr=0x600, delay=30, hold=70, pin=2, arm=True))
check("TVEC", snap["tvec"], (0xBEEF, 0x1234))
check("VECCTL", snap["vecsub"], 0b100)
hdr = run_hdr(out)
check("reply header shape (4 fields, field 4 = STATUS[5:3] = 0b101)",
      " ".join(hdr.split()[:4]), "OK 7 1 5")
check("all schedulers disarmed and VECCTL cleared after the run",
      ([h.read_event(n)["arm"] for n in range(V.EVT_N)], h.read_vecsub_en()),
      ([False, False, False], 0))

print()
print("=" * 78)
print("S2  the v1 line is bit-for-bit what it always was")
print("=" * 78)
h, out = run_serve(["RUN 0.01 evt=00400:44:300:1 cap=2", img, "EXIT"])
snap = h.snapshots[0]
check("scheduler 0 (hold=300, the F46 value)", snap["evt"][0],
      dict(addr=0x400, delay=44, hold=300, pin=1, arm=True))
check("schedulers 1,2 left disarmed", [snap["evt"][n]["arm"] for n in (1, 2)],
      [False, False])
check("TVEC/VECCTL default to inert", (snap["tvec"], snap["vecsub"]),
      ((0, 0), 0))
hdr = run_hdr(out)
check("reply header", " ".join(hdr.split()[:4]), "OK 7 1 5")

print()
print("=" * 78)
print("S3  the guards reach the wire: a bad RUN line is ERR, not a bad capture")
print("=" * 78)
for line, want in [
        ("RUN 0.01 evt=00400:0:0:3", "pin"),
        ("RUN 0.01 evt=00400:0:4096:0", "hold"),
        ("RUN 0.01 evt=00400:65536:0:0", "delay"),
        ("RUN 0.01 evt=100000:0:0:0", "addr"),
        ("RUN 0.01 evt=00400:0:50:1 evt2=00500:0:50:1", "already armed"),
        ("RUN 0.01 vecsub=9", "vecsub_en mask"),
        ("RUN 0.01 tvec=10000:0", "tvec cs")]:
    _, out = run_serve([line, img, "EXIT"])
    err = [l for l in out if l.startswith("ERR")]
    ok = bool(err) and want in err[0]
    if not ok:
        FAIL.append(line)
    print(f"  {'PASS' if ok else 'FAIL'}  {line}\n         -> "
          f"{(err[0] if err else out)!s:.130}")

print()
print("=" * 78)
print("S4  serve v3 -- the verified readback the capture path scores on (T11)")
print("=" * 78)
h, out = run_serve([
    "RUN 0.01 evt=00400:10:50:0 evt3=00600:900:20:1 tvec=0000:bf00 "
    "vecsub=4 pinok=1 cap=2", img, "EXIT"])
check("the banner announces v3", out[0], "OK SERVE v3")
hdr = run_hdr(out)
tok = dict(f.split("=", 1) for f in hdr.split() if "=" in f)
check("the reply carries vec= (STATUS[6])", tok.get("vec"), "1")
rb = tok.get("rb", "").split(",")
check("the reply carries rb= with EVT_N pairs + TVEC + VECCTL",
      len(rb), V.EVT_N + 2)
check("rb's scheduler 0 pair is EXACTLY what v30ctl's packers make of the "
      "directive that was sent",
      rb[0], f"{V.pack_evt_addr(0x400):08x}:"
             f"{V.pack_evt_cfg(delay=10, hold=50, pin=0, arm=True):08x}")
check("rb's scheduler 2 pair likewise", rb[2],
      f"{V.pack_evt_addr(0x600):08x}:"
      f"{V.pack_evt_cfg(delay=900, hold=20, pin=1, arm=True):08x}")
check("rb's TVEC is the whole 32-bit word", rb[-2],
      f"{V.pack_tvec(0x0000, 0xBF00):08x}")
check("rb's VECCTL names only scheduler 2", rb[-1], f"{0b100:08x}")
check("scheduler 1, not asked for, reads back DISARMED",
      bool(int(rb[1].split(':')[1], 16) & (1 << 31)), False)
check("pinok=1 permitted two schedulers on the NMI pin",
      [h.snapshots[0]["evt"][n]["pin"] for n in (0, 2)], [0, 1])

h2, out2 = run_serve(["RUN 0.01 evt=00400:0:50:1 evt3=00500:0:50:1 pinok=1",
                      img, "EXIT"])
check("...and it is the FLAG that permits it: the same line WITH pinok is OK",
      any(l.startswith("ERR") for l in out2), False)

print()
print("=" * 78)
print("RESULT: " + ("ALL PASS" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
print("=" * 78)
sys.exit(1 if FAIL else 0)
