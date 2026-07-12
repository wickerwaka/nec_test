#!/usr/bin/env python3
"""sweep_timing - Campaign 2: per-opcode timing measurements at scale.

Method: saturated-queue F-spacing (exp_biu.py exp 3, validated against
documented reg/imm timings in docs/facts/biu_model.md — no fixed offset).
Each case embeds one instruction in a NOP sled; its F-to-next-F gap is its
retirement-to-retirement time. Documented clocks come from the matched
instructions.json record (the assembler reports which form it encoded),
selecting the uPD70116 even-address figures (all operands here are
even-aligned).

Results accumulate in docs/facts/timing_measured.json keyed by
(nec_form, asm, operands); re-running a case overwrites its record.

Usage:
  sweep_timing.py mul   [--host ...]   # MUL/MULU deep characterization
  sweep_timing.py sweep [--host ...]   # curated starter set (~100 forms)
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                          # noqa: E402
from exp_biu import fspacing_case                     # noqa: E402

FACTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "facts"
OUT_PATH = FACTS_DIR / "timing_measured.json"

PROVENANCE = {
    "method": "fspacing",
    "description": "saturated-queue F-to-F spacing: 16-NOP runway + target "
                   "instruction + 8-NOP tail; gap between the target's "
                   "first-byte queue pop (QS=F) and the next instruction's "
                   "= retirement-to-retirement time. Validated exactly "
                   "against documented reg/imm timings (biu_model.md exp 3).",
    "conditions": {
        "chip": "uPD70116C-8 (V30), socketed harness",
        "mode": "max (large), S/LG# low",
        "clk_mhz": 4, "waits": 0,
        "anchor": "0000:0500 (even, code even-aligned)",
        "mem_operand": "DS0=0, BW=0x0800 (even); memory fill 0x90 unless "
                       "ram noted",
        "stack": "SS=0, SP=0x0F00 (even) for stack cases",
    },
    "script": "sw/sweep_timing.py",
    "documented_source": "docs/facts/instructions.json (User's Manual); "
                         "uPD70116 even-address values used",
}

MEM_REGS = {"BW": 0x0800, "IX": 0x0010, "DS0": 0}
STACK_REGS = {"SS": 0, "SP": 0x0F00}

REG8_NAMES = {"AL", "AH", "BL", "BH", "CL", "CH", "DL", "DH"}


#----------------------------------------------------------------------------
# documented-clock selection and parsing
#----------------------------------------------------------------------------

def parse_clock_value(s, n=None):
    """'21 or 22' -> {21,22}; '33 to 39 (...)' -> range; '7+n' -> {7+n}.
    Returns a set of ints, or None if unparseable."""
    s = re.sub(r"\(according to.*?\)", "", s)
    s = re.sub(r",?\s*where\s+n\s*=.*$", "", s)
    s = s.replace(" ", "")
    m = re.fullmatch(r"(\d+)", s)
    if m:
        return {int(m.group(1))}
    m = re.fullmatch(r"(\d+)or(\d+)", s)
    if m:
        return {int(m.group(1)), int(m.group(2))}
    m = re.fullmatch(r"(\d+)to(\d+)", s)
    if m:
        return set(range(int(m.group(1)), int(m.group(2)) + 1))
    m = re.fullmatch(r"(\d+)\+n", s)
    if m and n is not None:
        return {int(m.group(1)) + n}
    return None


def doc_values(rec, w, n=None):
    """Applicable documented clock values for our conditions (uPD70116,
    even-aligned operands, operand width w). Returns (set, verbatim list)."""
    vals, verbatim = set(), []
    for c in rec["clocks"]:
        wl = c["when"].lower()
        if "70108" in wl:
            continue
        if "70116" in wl and "odd" in wl:
            continue
        if re.search(r"w\s*=\s*0", wl) and w != 0:
            continue
        if re.search(r"w\s*=\s*1", wl) and w != 1:
            continue
        verbatim.append((c["when"] + ": " if c["when"] else "") + c["value"])
        v = parse_clock_value(c["value"], n)
        if v:
            vals |= v
    return vals, verbatim


def derive_width(asm):
    """W bit guess from the destination (first) operand: reg8/byte -> 0."""
    parts = asm.split(None, 1)
    if len(parts) < 2:
        return 1
    first = parts[1].split(",")[0].strip()
    if first.upper() in REG8_NAMES or first.lower().startswith("byte"):
        return 0
    return 1


#----------------------------------------------------------------------------
# one measurement
#----------------------------------------------------------------------------

def measure(a, host, asm, regs=None, n=None, ram=None, tag="sw", note=None):
    """Assemble one instruction, measure its F-gap, compare to docs.
    Returns the result record (also printed by fspacing_case)."""
    code = a.assemble(asm)
    rec = a.last_rec
    w = derive_width(asm)
    vals, verbatim = doc_values(rec, w, n)
    label = f"{asm}"
    gap, nop_t = fspacing_case(a, host, label, f"    {asm}\n",
                               regs_extra=regs, tag=tag, ram=ram)
    out = {
        "nec_form": rec["nec_form"],
        "asm": asm,
        "bytes": code.hex(" "),
        "operands": {k: f"0x{v:04X}" for k, v in (regs or {}).items()},
        "measured_cycles": gap,
        "nop_baseline": nop_t,
        "documented_clocks": verbatim,
        "documented_values": sorted(vals),
        "match": gap in vals if vals else None,
        "deviation": (0 if gap in vals else
                      min((gap - v for v in vals), key=abs)) if vals and
                     gap is not None else None,
    }
    if n is not None:
        out["n"] = n
    if ram:
        out["ram"] = [[f"0x{ad:04X}", f"0x{v:02X}"] for ad, v in ram]
    if note:
        out["note"] = note
    if nop_t != 3:
        out["warn"] = f"NOP baseline {nop_t} != 3 (queue not saturated?)"
    return out


def save(results, skipped):
    """Merge into timing_measured.json (replace records with same key)."""
    data = {"_provenance": dict(PROVENANCE, date=str(date.today())),
            "results": [], "skipped": []}
    if OUT_PATH.exists():
        old = json.loads(OUT_PATH.read_text())
        data["results"] = old.get("results", [])
        data["skipped"] = old.get("skipped", [])

    def key(r):
        return (r["nec_form"], r["asm"], json.dumps(r.get("operands", {}),
                                                    sort_keys=True))
    merged = {key(r): r for r in data["results"]}
    for r in results:
        merged[key(r)] = r
    data["results"] = sorted(merged.values(),
                             key=lambda r: (r["nec_form"], r["asm"],
                                            json.dumps(r.get("operands"))))
    skip_merged = {s["asm"]: s for s in data["skipped"]}
    for s in skipped:
        skip_merged[s["asm"]] = s
    data["skipped"] = sorted(skip_merged.values(), key=lambda s: s["asm"])
    OUT_PATH.write_text(json.dumps(data, indent=1) + "\n")
    print(f"\nwrote {len(data['results'])} results, "
          f"{len(data['skipped'])} skipped -> {OUT_PATH}")


def run_cases(host, cases):
    """cases: list of (asm, regs, kwargs). Returns (results, skipped)."""
    a = Assembler()
    results, skipped = [], []
    for i, (asm, regs, kw) in enumerate(cases):
        tag = f"sw{i}"
        try:
            r = measure(a, host, asm, regs=regs, tag=tag, **kw)
            results.append(r)
            if r["match"] is False:
                print(f"    ^ DEVIATION {r['deviation']:+d} vs documented "
                      f"{r['documented_values']}")
        except Exception as e:                        # noqa: BLE001
            print(f"{asm:<28} SKIPPED: {e}")
            skipped.append({"asm": asm, "reason": str(e)})
    return results, skipped


#----------------------------------------------------------------------------
# mission 1: MUL/MULU characterization
#----------------------------------------------------------------------------

def word_ram(addr, val):
    return [(addr, val & 0xFF), (addr + 1, (val >> 8) & 0xFF)]


def cmd_mul(host):
    cases = []
    # MULU reg8: AL x CL (documented 21 or 22)
    for al, cl in ((0x00, 0x00), (0x01, 0x01), (0xFF, 0xFF), (0x07, 0x05),
                   (0x80, 0x80), (0xAA, 0x0F)):
        cases.append(("MULU CL", {"AW": al, "CW": cl},
                      {"note": f"AL={al:#04x} CL={cl:#04x}"}))
    # MULU reg16: AW x CW (documented 29 or 30)
    for aw, cw in ((0x0000, 0x0000), (0x0001, 0x0001), (0xFFFF, 0xFFFF),
                   (0x0007, 0x0005), (0x1234, 0x5678), (0x8000, 0x0002)):
        cases.append(("MULU CW", {"AW": aw, "CW": cw},
                      {"note": f"AW={aw:#06x} CW={cw:#06x}"}))
    # MUL reg8 signed (documented 33-39, "according to data")
    for al, cl in ((0x00, 0x00), (0x01, 0x01), (0xFF, 0xFF), (0x7F, 0x7F),
                   (0x80, 0x7F), (0xFF, 0x01)):
        cases.append(("MUL CL", {"AW": al, "CW": cl},
                      {"note": f"AL={al:#04x} CL={cl:#04x}"}))
    # MUL reg16 signed (documented 41-47)
    for aw, cw in ((0x0000, 0x0000), (0x0001, 0x0001), (0xFFFF, 0xFFFF),
                   (0x7FFF, 0x7FFF), (0x8000, 0x7FFF), (0xFFFF, 0x0001)):
        cases.append(("MUL CW", {"AW": aw, "CW": cw},
                      {"note": f"AW={aw:#06x} CW={cw:#06x}"}))
    # memory forms, even-aligned at DS0:0800
    for al, m in ((0x07, 0x05), (0xFF, 0xFF), (0x00, 0x00)):
        cases.append(("MULU byte [BW]", dict(MEM_REGS, AW=al),
                      {"ram": [(0x0800, m)],
                       "note": f"AL={al:#04x} mem8={m:#04x}"}))
    for aw, m in ((0x0007, 0x0005), (0xFFFF, 0xFFFF), (0x0000, 0x0000)):
        cases.append(("MULU word [BW]", dict(MEM_REGS, AW=aw),
                      {"ram": word_ram(0x0800, m),
                       "note": f"AW={aw:#06x} mem16={m:#06x}"}))
    for al, m in ((0x7F, 0x7F), (0xFF, 0xFF)):
        cases.append(("MUL byte [BW]", dict(MEM_REGS, AW=al),
                      {"ram": [(0x0800, m)],
                       "note": f"AL={al:#04x} mem8={m:#04x}"}))
    for aw, m in ((0x7FFF, 0x7FFF), (0xFFFF, 0xFFFF)):
        cases.append(("MUL word [BW]", dict(MEM_REGS, AW=aw),
                      {"ram": word_ram(0x0800, m),
                       "note": f"AW={aw:#06x} mem16={m:#06x}"}))
    # 3-operand immediate forms (documented 28-34 / 36-42)
    for cw, imm in ((0x0000, 0x10), (0x7FFF, 0x7F), (0xFFFF, 0x10)):
        cases.append((f"MUL BW, CW, 0x{imm:02X}", {"CW": cw},
                      {"note": f"CW={cw:#06x} imm8={imm:#04x}"}))
    for cw, imm in ((0x0000, 0x1234), (0x7FFF, 0x7FFF)):
        cases.append((f"MUL BW, CW, 0x{imm:04X}", {"CW": cw},
                      {"note": f"CW={cw:#06x} imm16={imm:#06x}"}))
    results, skipped = run_cases(host, cases)
    save(results, skipped)
    return 0


#----------------------------------------------------------------------------
# mission 2: curated starter sweep
#----------------------------------------------------------------------------

def sweep_cases():
    c = []
    alu = ["ADD", "ADDC", "SUB", "SUBC", "CMP", "AND", "OR", "XOR", "TEST"]
    # reg16,reg16 and reg8,reg8
    for op in alu:
        c.append((f"{op} BW, DW", None, {}))
    c.append(("ADD BL, DL", None, {}))
    c.append(("XOR BL, DL", None, {}))
    # acc,imm
    for op in alu:
        c.append((f"{op} AW, 0x1111", None, {}))
    c.append(("ADD AL, 0x11", None, {}))
    # reg,imm (non-acc; 0x11 -> sign-extended 83 form, 0x0111 -> full imm16)
    c.append(("ADD BW, 0x11", None, {"note": "S=1 sign-extended imm8"}))
    c.append(("ADD BW, 0x0111", None, {"note": "full imm16"}))
    c.append(("CMP BW, 0x11", None, {"note": "S=1 sign-extended imm8"}))
    c.append(("XOR BW, 0x0111", None, {"note": "full imm16"}))
    # reg,mem
    for op in ("ADD", "SUB", "AND", "CMP"):
        c.append((f"{op} DW, [BW]", MEM_REGS, {}))
    c.append(("ADD DL, byte [BW]", MEM_REGS, {}))
    # mem,reg (RMW; CMP/TEST read-only)
    for op in ("ADD", "XOR", "CMP", "TEST"):
        c.append((f"{op} [BW], DW", MEM_REGS, {}))
    # mem,imm
    c.append(("ADD word [BW], 0x11", MEM_REGS, {"note": "S=1 imm8"}))
    c.append(("CMP word [BW], 0x11", MEM_REGS, {"note": "S=1 imm8"}))
    # MOV family
    c += [
        ("MOV BW, DW", None, {}),
        ("MOV BL, DL", None, {}),
        ("MOV BW, 0x1234", None, {}),
        ("MOV BL, 0x12", None, {}),
        ("MOV DW, [BW]", MEM_REGS, {}),
        ("MOV DL, byte [BW]", MEM_REGS, {}),
        ("MOV [BW], DW", MEM_REGS, {}),
        ("MOV [BW], DL", MEM_REGS, {}),
        ("MOV AW, [0x0802]", MEM_REGS, {}),
        ("MOV AL, [0x0802]", MEM_REGS, {}),
        ("MOV [0x0802], AW", MEM_REGS, {}),
        ("MOV word [BW], 0x1234", MEM_REGS, {}),
        ("MOV DW, DS0", None, {}),
        ("MOV DS1, DW", None, {"note": "DS1=0 loaded, benign"}),
        ("MOV [BW], DS0", MEM_REGS, {}),
        ("MOV DS1, [BW]", MEM_REGS, {"note": "DS1=0x9090 loaded, unused"}),
    ]
    # INC/DEC
    c += [
        ("INC AW", None, {}), ("INC DL", None, {}),
        ("DEC AW", None, {}), ("DEC DL", None, {}),
        ("INC word [BW]", MEM_REGS, {}), ("DEC word [BW]", MEM_REGS, {}),
    ]
    # PUSH/POP (SS=0, SP=0x0F00 even; pops read fill 0x9090 unless ram)
    c += [
        ("PUSH BW", STACK_REGS, {}),
        ("PUSH DS0", STACK_REGS, {}),
        ("PUSH PSW", STACK_REGS, {}),
        ("PUSH 0x1234", STACK_REGS, {}),
        ("PUSH 0x12", STACK_REGS, {}),
        ("POP BW", STACK_REGS, {"note": "pops fill 0x9090"}),
        ("POP DS1", STACK_REGS, {"note": "pops fill; DS1 unused after"}),
        ("POP PSW", STACK_REGS,
         {"ram": word_ram(0x0F00, 0xF002), "note": "pops PSW=0xF002"}),
        ("PUSH R", STACK_REGS, {"note": "8 words pushed"}),
        ("POP R", STACK_REGS, {"note": "8 words popped (fill); regs junk "
                               "after, stub does not care"}),
    ]
    # XCH
    c += [
        ("XCH AW, BW", None, {}),
        ("XCH BW, DW", None, {}),
        ("XCH [BW], DW", MEM_REGS, {}),
    ]
    # shifts/rotates by 1 (reg)
    for op in ("SHL", "SHR", "SHRA", "ROL", "ROR", "ROLC", "RORC"):
        c.append((f"{op} AW, 1", None, {}))
    c.append(("SHL AL, 1", None, {}))
    # mem,1
    c.append(("SHL word [BW], 1", MEM_REGS, {}))
    c.append(("ROR word [BW], 1", MEM_REGS, {}))
    # by CL (documented 7+n)
    c.append(("SHL AW, CL", {"CW": 0x0000}, {"n": 0, "note": "CL=0"}))
    c.append(("SHL AW, CL", {"CW": 0x0001}, {"n": 1, "note": "CL=1"}))
    c.append(("SHL AW, CL", {"CW": 0x0004}, {"n": 4, "note": "CL=4"}))
    for op in ("SHR", "SHRA", "ROL", "RORC"):
        c.append((f"{op} AW, CL", {"CW": 0x0004}, {"n": 4, "note": "CL=4"}))
    c.append(("SHL AL, CL", {"CW": 0x0004}, {"n": 4, "note": "CL=4"}))
    # by imm8 (V30-specific encoding)
    c.append(("SHL AW, 4", None, {"n": 4}))
    c.append(("ROR AW, 4", None, {"n": 4}))
    # flag ops
    for op in ("CLR1 CY", "SET1 CY", "NOT1 CY", "CLR1 DIR", "SET1 DIR"):
        c.append((op, None, {}))
    # bit ops on registers (CL=3)
    for op in ("CLR1", "SET1", "NOT1"):
        c.append((f"{op} AL, CL", {"CW": 0x0003}, {"note": "CL=3"}))
        c.append((f"{op} AW, CL", {"CW": 0x0003}, {"note": "CL=3"}))
        c.append((f"{op} AL, 3", None, {}))
    c.append(("SET1 AW, 7", None, {}))
    # F6/F7 group companions
    c += [
        ("NOT AW", None, {}), ("NOT DL", None, {}),
        ("NEG AW", None, {}), ("NEG word [BW]", MEM_REGS, {}),
    ]
    # anchors from campaign 1 (regression cross-check)
    c += [
        ("NOP", None, {}),
        ("MOV AW, 0x1234", None, {}),
        ("DIVU CW", {"AW": 9, "DW": 0, "CW": 3}, {}),
    ]
    return c


def cmd_sweep(host):
    results, skipped = run_cases(host, sweep_cases())
    save(results, skipped)
    dev = [r for r in results if r["match"] is False]
    print(f"\n{len(results)} measured, {len(dev)} deviations, "
          f"{len(skipped)} skipped")
    for r in dev:
        print(f"  {r['nec_form']:<24} {r['asm']:<24} measured "
              f"{r['measured_cycles']} vs {r['documented_values']} "
              f"({r['deviation']:+d})")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mul", "sweep"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    sys.exit({"mul": cmd_mul, "sweep": cmd_sweep}[args.cmd](args.host))


if __name__ == "__main__":
    main()
