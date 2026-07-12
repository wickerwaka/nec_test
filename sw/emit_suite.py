#!/usr/bin/env python3
"""emit_suite - Campaign 2 missions 14/16: emit a SingleStepTests-format
V30 (uPD70116) test suite from the real chip.

Format: the V20 suite schema (docs/notes/singlesteptests_v20.md) extended
for the 16-bit bus per the 8086-suite precedent. Each test:
  name, bytes, initial{regs,ram,queue}, final{regs,ram,queue}, cycles,
  hash, idx
Cycle rows (11 columns, 8086-suite shaped):
  [pins, bus20, seg, memstat, iostat, ube_n, data16, busstat, tstate,
   qop, qbyte]
Windows run from the QS first-byte (F) pop of the test instruction to the
F pop of the next instruction (queue status gives suite-grade boundaries).
The shadow queue is reconstructed from CODE fetch data (pushed at T4, low
byte first on even word fetches) and F/S pops, and provides the qbyte
column, the final queue contents, and (for prefetched variants) the
initial queue.

Known v0.1 limitations (see tests/v30/v0.1/README.md): no IN/port-read
opcodes (harness IOR data not configurable), no segment-override prefix
randomization, memory/IO command columns synthesized from BS + T-state
(no i8288 on the harness).

Usage:
  emit_suite.py validate [--host ...]        # 5 V20 cases of opcode 00
  emit_suite.py preload-cal [--host ...]     # mission 15 calibration
  emit_suite.py emit [--opcodes 00,B8,...] [--cases N] [--out DIR]
                     [--seed S] [--preload]
"""

import argparse
import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage                                      # noqa: E402
from testimage import ComposeError                    # noqa: E402
from v30run import run_image, parse_result, RunError  # noqa: E402

SW = Path(__file__).resolve().parent
DEFAULT_OUT = SW.parent / "tests" / "v30" / "v0.1"
V20_DATA = SW.parent / "tests" / "v30" / "v20suite"

INTEL2NEC = {"ax": "AW", "bx": "BW", "cx": "CW", "dx": "DW",
             "sp": "SP", "bp": "BP", "si": "IX", "di": "IY",
             "cs": "PS", "ds": "DS0", "es": "DS1", "ss": "SS",
             "ip": "PC", "flags": "PSW"}
NEC2INTEL = {v: k for k, v in INTEL2NEC.items()}

SEG_STR = {0: "ES", 1: "SS", 2: "CS", 3: "DS"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
T_STR = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
Q_STR = {0: "-", 1: "F", 2: "E", 3: "S"}

REG8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
REG16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]
EA_STR = ["bx+si", "bx+di", "bp+si", "bp+di", "si", "di", "bp", "bx"]

PRELOAD_BYTES = b"\x63\xc0"       # NEC undocumented multi-cycle no-op
HANDLER_OFF = 0x0400              # IVT-0 handler (V20 convention)


#----------------------------------------------------------------------------
# opcode specs
#----------------------------------------------------------------------------
# modrm: None, "rm8r8", "rm16r16", "r8rm8", "r16rm16", "grp8", "grp16"
# imm: byte count appended after modrm/opcode
def SPEC(key, mnem, base, modrm=None, w=0, imm=0, group=None,
         stack=False, divtrap=False, string4s=False, imm_mask=None):
    return dict(key=key, mnem=mnem, base=base, modrm=modrm, w=w, imm=imm,
                group=group, stack=stack, divtrap=divtrap,
                string4s=string4s, imm_mask=imm_mask)


ALU = ["add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"]
OPCODES = {}
for i, m in enumerate(ALU):
    OPCODES[f"{i * 8:02X}"] = SPEC(f"{i * 8:02X}", m, [i * 8],
                                   modrm="mr8", w=0)
OPCODES["B8"] = SPEC("B8", "mov ax,", [0xB8], imm=2)
OPCODES["40"] = SPEC("40", "inc ax", [0x40])
OPCODES["48"] = SPEC("48", "dec ax", [0x48])
OPCODES["50"] = SPEC("50", "push ax", [0x50], stack=True)
OPCODES["58"] = SPEC("58", "pop ax", [0x58], stack=True)
OPCODES["86"] = SPEC("86", "xchg", [0x86], modrm="mr8", w=0)
OPCODES["87"] = SPEC("87", "xchg", [0x87], modrm="mr16", w=1)
OPCODES["88"] = SPEC("88", "mov", [0x88], modrm="mr8", w=0)
OPCODES["89"] = SPEC("89", "mov", [0x89], modrm="mr16", w=1)
OPCODES["8A"] = SPEC("8A", "mov", [0x8A], modrm="rm8", w=0)
OPCODES["8B"] = SPEC("8B", "mov", [0x8B], modrm="rm16", w=1)
OPCODES["D0.4"] = SPEC("D0.4", "shl", [0xD0], modrm="grp8", group=4)
OPCODES["F6.4"] = SPEC("F6.4", "mul", [0xF6], modrm="grp8", group=4)
OPCODES["F7.6"] = SPEC("F7.6", "div", [0xF7], modrm="grp16", group=6, w=1,
                       divtrap=True, stack=True)
OPCODES["FE.0"] = SPEC("FE.0", "inc", [0xFE], modrm="grp8", group=0)
OPCODES["0F18"] = SPEC("0F18", "test1", [0x0F, 0x18], modrm="grp8",
                       group=0, imm=1, imm_mask=0x07)
OPCODES["0F28"] = SPEC("0F28", "rol4", [0x0F, 0x28], modrm="grp8", group=0)
OPCODES["0F20"] = SPEC("0F20", "add4s", [0x0F, 0x20], string4s=True)

TRANCHE = ["00", "08", "10", "18", "20", "28", "30", "38", "B8", "40",
           "48", "50", "58", "86", "87", "88", "89", "8A", "8B", "D0.4",
           "F6.4", "F7.6", "FE.0", "0F18", "0F28", "0F20"]


#----------------------------------------------------------------------------
# case generation
#----------------------------------------------------------------------------

def rnd16(rng):
    return 0 if rng.random() < 0.02 else rng.getrandbits(16)


def ea_of(rm, mod, disp, regs):
    base = {0: regs["bx"] + regs["si"], 1: regs["bx"] + regs["di"],
            2: regs["bp"] + regs["si"], 3: regs["bp"] + regs["di"],
            4: regs["si"], 5: regs["di"], 6: regs["bp"], 7: regs["bx"]}[rm]
    if mod == 0 and rm == 6:
        return disp & 0xFFFF, "ds"
    seg = "ss" if rm in (2, 3, 6) else "ds"
    if mod == 1:
        disp = disp - 0x100 if disp & 0x80 else disp
    return (base + (disp if mod else 0)) & 0xFFFF, seg


def dispstr(mod, rm, disp):
    if mod == 0 and rm == 6:
        return f"[{disp:04x}h]"
    s = EA_STR[rm]
    if mod == 1:
        d = disp - 0x100 if disp & 0x80 else disp
        s += f"{d:+03x}h".replace("0x", "")
    elif mod == 2:
        s += f"+{disp:04x}h"
    return f"[{s}]"


def gen_case(spec, rng):
    """Random initial state + instruction bytes per V20 conventions.
    Returns dict with intel regs, instr bytes, ram placements, name,
    divtrap flag. Re-rolls internally on footprint conflicts."""
    for _ in range(64):
        regs = {r: rnd16(rng) for r in REG16}
        regs["cs"] = rng.getrandbits(16)
        regs["ip"] = rng.getrandbits(16)
        for sr in ("ds", "es", "ss"):
            regs[sr] = rng.getrandbits(16)
        regs["flags"] = (rng.getrandbits(16) & 0x0ED5) | 0xF002

        instr = bytes(spec["base"])
        name = spec["mnem"]
        ram = []
        if spec["modrm"]:
            mod = rng.randrange(4)
            rm = rng.randrange(8)
            reg = spec["group"] if spec["group"] is not None \
                else rng.randrange(8)
            disp = 0
            ndisp = 0
            if mod == 1:
                ndisp, disp = 1, rng.getrandbits(8)
            elif mod == 2 or (mod == 0 and rm == 6):
                ndisp, disp = 2, rng.getrandbits(16)
            instr += bytes([(mod << 6) | (reg << 3) | rm])
            instr += disp.to_bytes(ndisp, "little") if ndisp else b""
            wide = spec["modrm"] in ("mr16", "rm16", "grp16")
            rn = (REG16 if wide else REG8)[reg]
            if mod == 3:
                on = (REG16 if wide else REG8)[rm]
            else:
                on = ("word " if wide else "byte ") + dispstr(mod, rm, disp)
            if spec["modrm"] in ("rm8", "rm16"):    # reg, rm order
                name = f"{spec['mnem']} {rn}, {on}"
            elif spec["group"] is not None:
                name = f"{spec['mnem']} {on}" + \
                    (", 1" if spec["key"] == "D0.4" else "")
            else:
                name = f"{spec['mnem']} {on}, {rn}"
        imm_v = None
        if spec["imm"]:
            imm_v = rng.getrandbits(8 * spec["imm"])
            if spec["imm_mask"] is not None:
                imm_v &= spec["imm_mask"]
            instr += imm_v.to_bytes(spec["imm"], "little")
            name += f" {imm_v:0{2 * spec['imm']}x}h"
        if spec["string4s"]:
            regs["cx"] = (regs["cx"] & 0xFF00) | rng.randrange(1, 7)
            name = f"{spec['mnem']} (cl={regs['cx'] & 0xFF})"

        anchor = ((regs["cs"] << 4) + regs["ip"]) & 0xFFFFF
        a_phys = anchor & 0xFFFF
        spans = [range(a_phys, a_phys + len(instr) + 24)]   # instr+stub

        def lin(seg, off):
            return ((regs[seg] << 4) + (off & 0xFFFF)) & 0xFFFFF

        # memory operand placement
        if spec["modrm"] and (instr[len(spec["base"])] >> 6) != 3:
            mb = instr[len(spec["base"])]
            mod, rm = mb >> 6, mb & 7
            nd = {0: 2 if rm == 6 else 0, 1: 1, 2: 2, 3: 0}[mod]
            d = int.from_bytes(
                instr[len(spec["base"]) + 1:len(spec["base"]) + 1 + nd],
                "little")
            ea, seg = ea_of(rm, mod, d, regs)
            nbytes = 2 if spec["w"] else 1
            for k in range(nbytes):
                ram.append((lin(seg, ea + k), rng.getrandbits(8)))
            spans.append(range(lin(seg, ea) & 0xFFFF,
                               (lin(seg, ea) & 0xFFFF) + nbytes))
        if spec["string4s"]:
            n = ((regs["cx"] & 0xFF) + 1) // 2
            for k in range(n):
                ram.append((lin("ds", regs["si"] + k), rng.getrandbits(8)))
                ram.append((lin("es", regs["di"] + k), rng.getrandbits(8)))
            spans.append(range(lin("ds", regs["si"]) & 0xFFFF,
                               (lin("ds", regs["si"]) & 0xFFFF) + n))
            spans.append(range(lin("es", regs["di"]) & 0xFFFF,
                               (lin("es", regs["di"]) & 0xFFFF) + n))
        if spec["key"] == "58":                  # POP AX reads [ss:sp]
            ram.append((lin("ss", regs["sp"]), rng.getrandbits(8)))
            ram.append((lin("ss", regs["sp"] + 1), rng.getrandbits(8)))
        if spec["stack"]:
            lo = (lin("ss", regs["sp"] - 8)) & 0xFFFF
            spans.append(range(lo, lo + 12))
        ivt = None
        if spec["divtrap"]:
            ivt = {0: (0x0000, HANDLER_OFF)}
            # handler: BR far to the stub (patched in emit_case)
            spans.append(range(0, 4))
            spans.append(range(HANDLER_OFF, HANDLER_OFF + 5))

        # conflict rejection (incl. reserved page)
        bad = False
        seen = set()
        for sp in spans:
            for a in sp:
                if a in testimage.RESERVED or a in seen:
                    bad = True
                    break
                seen.add(a)
            if bad:
                break
        for a, _ in ram:
            if (a & 0xFFFF) in testimage.RESERVED:
                bad = True
        if bad:
            continue
        return dict(regs=regs, instr=instr, ram=ram, name=name, ivt=ivt)
    raise ComposeError("could not place case after 64 rerolls")


#----------------------------------------------------------------------------
# capture -> suite record
#----------------------------------------------------------------------------

def fetch_width(rec):
    return 2 if (rec["ad_addr"] & 1) == 0 and not rec["ube_n"] else 1


def build_rows(recs, anchor_linear, n_skip_f=0):
    """Walk recs from the test anchor, reconstructing the shadow queue.
    Returns (rows, i0, i1, q_at_start, q_final, fetched, memr_bytes):
    rows = cycle rows for the window [F pop #n_skip_f .. next F];
    fetched/memr = byte addresses read during the window."""
    started = False
    queue = []
    pend = None       # (width,) fetch in flight
    pend_data = None
    events = []       # (rec, popped_byte or None, queue_snapshot_after)
    for r in recs:
        if not started:
            if r["t"] == 1 and r["ad_addr"] == anchor_linear \
                    and r["bs_early"] == 4:
                started = True
            else:
                continue
        popped = None
        if r["t"] == 1 and r["bs_early"] == 4:
            pend = (fetch_width(r), r["ad_addr"])
            pend_data = None
        if r["t"] in (3, 4) and pend:
            pend_data = r["ad_data"]
        if r["t"] == 5 and pend:
            w, addr = pend
            if pend_data is not None:
                if w == 2:
                    queue.append((addr, pend_data & 0xFF))
                    queue.append((addr + 1, pend_data >> 8))
                else:
                    queue.append((addr, pend_data >> 8 if addr & 1
                                  else pend_data & 0xFF))
            pend = None
        if r["qs"] in (1, 3) and queue:
            popped = queue.pop(0)
        elif r["qs"] == 2:
            queue = []
        events.append((r, popped, list(queue)))

    fpop_is = [i for i, (r, _, _) in enumerate(events) if r["qs"] == 1]
    if len(fpop_is) < n_skip_f + 2:
        raise RunError(f"only {len(fpop_is)} F pops after anchor")
    i0 = fpop_is[n_skip_f]
    i1 = fpop_is[n_skip_f + 1]

    q_at_start = [b for _, b in events[i0 - 1][2]] if i0 else []
    # queue contents just BEFORE the window's first pop, i.e. including
    # the popped byte: reconstruct from the pop + snapshot
    ev0 = events[i0]
    if ev0[1] is not None:
        q_at_start = [ev0[1][1]] + [b for _, b in ev0[2]]

    rows = []
    fetched, memrd = set(), set()
    for r, popped, _ in events[i0:i1 + 1]:
        t = r["t"]
        bs = BUS_STR[r["bs_early"]]
        ale = 1 if t == 1 else 0
        bus = r["ad_addr"] if t == 1 else \
            ((r["ps"] << 16) | r["ad_data"]) & 0xFFFFF
        seg = SEG_STR[r["ps"] & 3] if t in (2, 3, 4) and \
            r["bs_early"] != 7 else "--"
        mem = "---"
        io = "---"
        if bs in ("CODE", "MEMR") and t in (2, 3, 4):
            mem = "R--"
        elif bs == "MEMW":
            mem = "-A-" if t == 2 else ("-AW" if t in (3, 4) else "---")
        elif bs == "IOR" and t in (2, 3, 4):
            io = "R--"
        elif bs == "IOW":
            io = "-A-" if t == 2 else ("-AW" if t in (3, 4) else "---")
        rows.append([ale, bus, seg, mem, io, r["ube_n"], r["ad_data"],
                     bs, T_STR[t], Q_STR[r["qs"]],
                     popped[1] if popped else 0])
    for r, _, _ in events[:i1 + 1]:
        if r["t"] == 1 and r["bs_early"] == 4:
            for k in range(fetch_width(r)):
                fetched.add(r["ad_addr"] + k)
        if r["t"] == 1 and r["bs_early"] == 5:
            w = 2 if (r["ad_addr"] & 1) == 0 and not r["ube_n"] else 1
            for k in range(w):
                memrd.add(r["ad_addr"] + k)

    q_final = [b for _, b in events[i1][2]]
    return rows, events, i0, i1, q_at_start, q_final, fetched, memrd


def window_writes(events, i0, i1):
    """MEMW transactions whose T1 falls inside the window, as
    (addr, data, ube_n) in access order."""
    out = []
    cur = None
    for r, _, _ in events[i0:i1 + 1]:
        if r["t"] == 1 and r["bs_early"] == 6:
            cur = {"addr": r["ad_addr"], "ube_n": r["ube_n"], "data": None}
        elif r["t"] in (3, 4) and cur:
            cur["data"] = r["ad_data"]
        elif r["t"] == 5 and cur:
            out.append(cur)
            cur = None
    return out


def write_bytes(txn):
    """(addr, byte) pairs for a captured MEMW honoring byte lanes."""
    a, d = txn["addr"], txn["data"]
    if a & 1:
        return [(a, d >> 8)] if not txn["ube_n"] else []
    out = [(a, d & 0xFF)]
    if not txn["ube_n"]:
        out.append((a + 1, d >> 8))
    return out


def emit_case(spec, case, host, tag, preload_n=0):
    """Run one generated case on hardware, return the suite test object."""
    nec_regs = {INTEL2NEC[k]: v for k, v in case["regs"].items()}
    instr = case["instr"]
    ram = list(case["ram"])
    ivt = case["ivt"]
    anchor = ((case["regs"]["cs"] << 4) + case["regs"]["ip"]) & 0xFFFFF

    if preload_n:
        nec_regs["PC"] = (nec_regs["PC"] - 2 * preload_n) & 0xFFFF
        run_instr = PRELOAD_BYTES * preload_n + instr
    else:
        run_instr = instr

    stub_linear = ((anchor & 0xFFFF) + len(instr)) & 0xFFFF
    if ivt:
        # handler at HANDLER_OFF: BR far 0000:stub
        h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
        ram += [(HANDLER_OFF + k, b) for k, b in enumerate(h)]

    image, meta = testimage.compose(regs=nec_regs, instr=run_instr,
                                    ram=ram, ivt=ivt,
                                    stub_linear=stub_linear)
    recs = run_image(image, host, tag)
    res = parse_result(recs, meta)

    rows, events, i0, i1, q0, qf, fetched, memrd = \
        build_rows(recs, meta["anchor_linear"], n_skip_f=preload_n)

    # initial ram: instr bytes + placed operands + fill actually read
    init_ram = []
    placed = {}
    for k, b in enumerate(instr):
        placed[(anchor + k) & 0xFFFFF] = b
        init_ram.append([(anchor + k) & 0xFFFFF, b])
    for a, v in case["ram"]:
        placed[a & 0xFFFFF] = v
        init_ram.append([a & 0xFFFFF, v])
    if ivt:
        seg, off = ivt[0]
        for k, b in enumerate(off.to_bytes(2, "little") +
                              seg.to_bytes(2, "little")):
            placed[k] = b
            init_ram.append([k, b])
        h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0, 0])
        for k, b in enumerate(h):
            placed[(HANDLER_OFF + k) & 0xFFFFF] = b
            init_ram.append([(HANDLER_OFF + k) & 0xFFFFF, b])
    for a in sorted(fetched | memrd):
        a20 = a & 0xFFFFF
        if a20 not in placed:
            v = image[a20 & 0xFFFF]
            placed[a20] = v
            init_ram.append([a20, v])

    # final ram = window writes applied over initial
    writes = window_writes(events, i0, i1)
    mem = dict(placed)
    fin_ram = []
    for t in writes:
        for a, b in write_bytes(t):
            a20 = a & 0xFFFFF
            if mem.get(a20) != b:
                mem[a20] = b
                fin_ram.append([a20, b])

    # trap detection: IVT vector 0 read inside the window
    trapped = ivt is not None and any(
        r["t"] == 1 and r["bs_early"] == 5 and r["ad_addr"] in (0, 2)
        for r, _, _ in events[i0:i1 + 1])

    got = res["regs"]
    fin_regs = {}
    for ik, nk in INTEL2NEC.items():
        if ik == "ip":
            fin_ip = HANDLER_OFF if trapped else \
                (case["regs"]["ip"] + len(instr)) & 0xFFFF
            if fin_ip != case["regs"]["ip"]:
                fin_regs["ip"] = fin_ip
        elif ik == "cs":
            fin_cs = 0x0000 if trapped else case["regs"]["cs"]
            if fin_cs != case["regs"]["cs"]:
                fin_regs["cs"] = fin_cs
        else:
            g = got.get(nk)
            if g is not None and g != case["regs"][ik]:
                fin_regs[ik] = g

    test = {
        "name": case["name"],
        "bytes": list(instr),
        "initial": {
            "regs": dict(case["regs"]),
            "ram": init_ram,
            "queue": q0 if preload_n else [],
        },
        "final": {
            "regs": fin_regs,
            "ram": fin_ram,
            "queue": qf,
        },
        "cycles": rows,
    }
    test["hash"] = hashlib.sha1(
        json.dumps([test["name"], test["bytes"], test["initial"],
                    test["final"], test["cycles"]],
                   separators=(",", ":")).encode()).hexdigest()
    return test


#----------------------------------------------------------------------------
# commands
#----------------------------------------------------------------------------

def cmd_validate(host):
    """Mission 14: 5 non-prefetched V20 cases of opcode 00 through the
    emitter; compare architectural fields to the V20 baseline."""
    cases = json.load(gzip.open(V20_DATA / "00.json.gz"))
    done = 0
    fails = 0
    for c in cases:
        if done >= 5:
            break
        if c["initial"]["queue"] or (c["initial"]["regs"]["flags"] & 0x100):
            continue
        if c["bytes"][0] in (0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3):
            continue          # prefixed: extra F pops shift the window
        spec = OPCODES["00"]
        case = dict(regs=dict(c["initial"]["regs"]), instr=bytes(c["bytes"]),
                    ram=[], name=c["name"], ivt=None)
        # place the V20 case's ram (minus its own instr bytes: we compose
        # instr ourselves; minus fill duplicates - placed wins)
        anchor = ((case["regs"]["cs"] << 4) + case["regs"]["ip"]) & 0xFFFFF
        ibytes = set(range(anchor, anchor + len(case["instr"])))
        case["ram"] = [(a, v) for a, v in c["initial"]["ram"]
                       if a not in ibytes]
        try:
            t = emit_case(spec, case, host, tag=f"val{done}")
        except (ComposeError, RunError) as e:
            print(f"idx {c['idx']}: SKIP {str(e)[:80]}")
            continue
        done += 1
        # compare architectural fields
        exp_regs = dict(c["initial"]["regs"])
        exp_regs.update(c["final"]["regs"])
        got_regs = dict(case["regs"])
        got_regs.update(t["final"]["regs"])
        bad = [k for k in exp_regs if exp_regs[k] != got_regs.get(k)]
        exp_ram = {a: v for a, v in c["final"]["ram"]}
        got_ram = {a: v for a, v in t["final"]["ram"]}
        ram_bad = {a for a in exp_ram
                   if exp_ram[a] != got_ram.get(a, exp_ram[a] if False
                                                 else None)}
        # a final.ram entry may be unchanged vs initial in one set
        init_ram = {a: v for a, v in c["initial"]["ram"]}
        ram_bad = {a for a in set(exp_ram) | set(got_ram)
                   if (got_ram.get(a, init_ram.get(a)) !=
                       exp_ram.get(a, init_ram.get(a)))}
        status = "OK" if not bad and not ram_bad else "MISMATCH"
        if status != "OK":
            fails += 1
        print(f"idx {c['idx']} {c['name']!r}: {status} "
              f"(reg diffs: {bad}, ram diffs: {sorted(ram_bad)}); "
              f"V20 {len(c['cycles'])} cycle rows (8-bit bus) vs V30 "
              f"{len(t['cycles'])}")
        if status != "OK":
            for k in bad:
                print(f"    {k}: v20 {exp_regs[k]:04x} vs v30 "
                      f"{got_regs.get(k):04x}")
    print(f"\n{done} validated, {fails} mismatched")
    return 1 if fails else 0


def cmd_preload_cal(host):
    """Mission 15: verify 63 C0 side-effect-free, calibrate N vs queue
    depth at the test instruction's F pop."""
    # 1. side effects: distinctive regs through 8x 63 C0
    inject = {"AW": 0x1111, "BW": 0x2222, "CW": 0x3333, "DW": 0x4444,
              "SP": 0x5555, "BP": 0x6666, "IX": 0x7777, "IY": 0x8888,
              "DS0": 0x9999, "DS1": 0xAAAA, "SS": 0xBBBB,
              "PS": 0x0000, "PC": 0x0500, "PSW": 0x08D5}
    image, meta = testimage.compose(regs=inject, instr=PRELOAD_BYTES * 8)
    recs = run_image(image, host, tag="pc0")
    res = parse_result(recs, meta)
    diffs = {k: (v, res["regs"].get(k)) for k, v in
             testimage.compose(regs=inject, instr=b"")[1]["regs_in"].items()
             if k not in ("PC",) and res["regs"].get(k) not in (None, v)}
    print(f"63 C0 x8: reg/PSW diffs vs injected: {diffs or 'NONE'}")

    # 2. depth at the F pop of a marker instruction after N preloads
    for n in range(0, 8):
        instr = PRELOAD_BYTES * n + b"\x90"
        image, meta = testimage.compose(
            regs={"PS": 0, "PC": 0x0500}, instr=instr)
        recs = run_image(image, host, tag=f"pc{n}")
        try:
            rows, events, i0, i1, q0, qf, _, _ = \
                build_rows(recs, meta["anchor_linear"], n_skip_f=n)
            print(f"N={n}: queue at test F pop = {len(q0)} bytes "
                  f"{[f'{b:02x}' for b in q0]}")
        except RunError as e:
            print(f"N={n}: {e}")
    return 0


def cmd_emit(host, opcodes, n_cases, out_dir, seed_base, preload_n):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "emit_log.txt"
    for op in opcodes:
        spec = OPCODES[op]
        rng_master = random.Random(f"{seed_base}/{op}")
        tests = []
        rerolls = 0
        t0 = time.time()
        i = 0
        while len(tests) < n_cases and rerolls < n_cases * 3:
            rng = random.Random(f"{seed_base}/{op}/{i}")
            i += 1
            # V20 convention: every other case runs from a full queue
            pn = preload_n if preload_n >= 0 else \
                (2 if len(tests) % 2 == 1 else 0)
            try:
                case = gen_case(spec, rng)
                t = emit_case(spec, case, host, tag=f"em{op}",
                              preload_n=pn)
            except (ComposeError, RunError) as e:
                rerolls += 1
                with log.open("a") as f:
                    f.write(f"{op} case-seed {i - 1} reroll: "
                            f"{str(e)[:120]}\n")
                continue
            t["idx"] = len(tests)
            tests.append(t)
            if len(tests) % 50 == 0:
                print(f"  {op}: {len(tests)}/{n_cases} "
                      f"({(time.time() - t0) / len(tests):.2f}s/case)",
                      flush=True)
        fn = out_dir / f"{op}.json.gz"
        with gzip.open(fn, "wt") as f:
            json.dump(tests, f, separators=(",", ":"))
        print(f"{op}: wrote {len(tests)} tests ({rerolls} rerolls) -> {fn} "
              f"in {time.time() - t0:.0f}s", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "preload-cal", "emit"])
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--opcodes", default=",".join(TRANCHE))
    ap.add_argument("--cases", type=int, default=500)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", default="v30-v0.1")
    ap.add_argument("--preload", type=int, default=-1,
                    help="-1 = alternate non-prefetched / prefetched(N=2) "
                         "per V20 convention (default); 0 = none; N>0 = "
                         "always N 63C0 preload repetitions")
    args = ap.parse_args()
    if args.cmd == "validate":
        return cmd_validate(args.host)
    if args.cmd == "preload-cal":
        return cmd_preload_cal(args.host)
    return cmd_emit(args.host, args.opcodes.split(","), args.cases,
                    args.out, args.seed, args.preload)


if __name__ == "__main__":
    sys.exit(main())
