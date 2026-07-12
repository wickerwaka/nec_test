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
from exp_biu import fspacing_case, queue_timeline     # noqa: E402
from v30run import run_test                           # noqa: E402

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
    """W bit guess from the destination (first) operand: reg8/byte -> 0.
    Fallback only — prefer the assembler's last_w (the emitted W bit)."""
    parts = asm.split(None, 1)
    if len(parts) < 2:
        return 0 if parts[0].upper().endswith("B") else 1
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
    w = a.last_w if getattr(a, "last_w", None) is not None else derive_width(asm)
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


#----------------------------------------------------------------------------
# mission 4: control flow (taken branches: next F IS the target first byte,
# so the F-gap includes the flush+refill = the real effective time)
#----------------------------------------------------------------------------

STRING_REGS = {"DS0": 0, "IX": 0x0800, "DS1": 0, "IY": 0x0900}


def fgap_run(a, host, src, regs=None, tag="fl", ram=None, stub_linear=None):
    """Assemble a full sled at 0x0500, run, return (gaps, fpops)."""
    code = a.assemble(src, org=0x0500)
    regs_full = dict({"PS": 0, "PC": 0x0500}, **(regs or {}))
    res = run_test(regs=regs_full, instr=code, host=host, tag=tag, ram=ram,
                   stub_linear=stub_linear)
    ev = queue_timeline(res["recs"], res["meta"])
    fpops = [e["idx"] for e in ev if e["q"] == "F"]
    gaps = [b - x for x, b in zip(fpops, fpops[1:])]
    return gaps, fpops


def measure_flow(a, host, name, form_rec, src, regs, doc_expect, tag,
                 note=None, ram=None, stub_linear=None, x_bytes=None):
    """One control-flow case: X at F-pop index 16, gap 16 = its time.
    doc_expect: the single documented value applicable to this case."""
    gaps, fpops = fgap_run(a, host, src, regs, tag=tag, ram=ram,
                           stub_linear=stub_linear)
    gap = gaps[16] if len(gaps) > 16 else None
    nop_t = sorted(gaps[8:15])[3] if len(gaps) > 15 else None
    print(f"{name:<28} F-gap {gap!s:>4}  (NOP baseline {nop_t}, "
          f"{len(fpops)} F ops)")
    out = {
        "nec_form": form_rec["nec_form"],
        "asm": name,
        "bytes": x_bytes or "",
        "operands": {k: f"0x{v:04X}" for k, v in (regs or {}).items()},
        "measured_cycles": gap,
        "nop_baseline": nop_t,
        "documented_clocks": [(c["when"] + ": " if c["when"] else "")
                              + c["value"] for c in form_rec["clocks"]],
        "documented_values": [doc_expect],
        "match": gap == doc_expect if gap is not None else None,
        "deviation": (gap - doc_expect) if gap is not None else None,
    }
    if note:
        out["note"] = note
    if gap is not None and gap != doc_expect:
        print(f"    ^ DEVIATION {gap - doc_expect:+d} vs documented "
              f"[{doc_expect}]")
    return out


def form_lookup(a, mnem, pattern):
    """instructions.json record for a (mnemonic, operand-pattern) pair."""
    for p, rec in a.forms[mnem.upper()]:
        if p == pattern:
            return rec
    raise KeyError((mnem, pattern))


def cmd_flow(host):
    a = Assembler()
    results = []
    nop16 = "    NOP\n" * 16

    # conditional branches: X is 2 bytes at 0x510, fall-through 0x512,
    # taken target 0x514 (even). doc: taken 14 / not-taken 4 (DBNZ* 13/5).
    cond_src = nop16 + "    {insn} t\n" + "    NOP\n" * 2 + "t:\n" + \
        "    NOP\n" * 8
    cond = [
        ("BZ",    {"PSW": 0x0040}, True, 14), ("BZ",   {"PSW": 0}, False, 4),
        ("BNZ",   {"PSW": 0},  True, 14), ("BNZ", {"PSW": 0x0040}, False, 4),
        ("BC",    {"PSW": 0x0001}, True, 14), ("BC",  {"PSW": 0}, False, 4),
        ("BNC",   {"PSW": 0},  True, 14), ("BNC", {"PSW": 0x0001}, False, 4),
        ("BCWZ",  {"CW": 0},   True, 13), ("BCWZ", {"CW": 5}, False, 5),
        ("DBNZ",  {"CW": 3},   True, 13), ("DBNZ", {"CW": 1}, False, 5),
        ("DBNZE", {"CW": 3, "PSW": 0x0040}, True, 14),
        ("DBNZE", {"CW": 3, "PSW": 0}, False, 5),
        ("DBNZNE", {"CW": 3, "PSW": 0}, True, 14),
        ("DBNZNE", {"CW": 3, "PSW": 0x0040}, False, 5),
    ]
    for i, (mnem, regs, taken, doc) in enumerate(cond):
        rec = form_lookup(a, mnem, "short-label")
        results.append(measure_flow(
            a, host, f"{mnem} t ({'taken' if taken else 'not-taken'})",
            rec, cond_src.format(insn=mnem), regs, doc, tag=f"fc{i}",
            note=f"target 0x0514 even, {'taken' if taken else 'fall-through'}"))

    # unconditional transfers; register/memory targets point at 0x0514
    # (mid-sled) or 0x0600 (stub relocated there for CALL/RET cases)
    stk = dict(STACK_REGS)
    uncond = [
        # (name, mnem, pattern, src-X-line, regs, ram, stub, doc, note)
        ("BR t (short)", "BR", "short-label",
         "    BR t\n" + "    NOP\n" * 2 + "t:\n", None, None, None, 12,
         "2-byte EB, target 0x0514 even"),
        ("BR t (near, disp16)", "BR", "near-label",
         "    DB 0xE9, 0x02, 0x00\n", None, None, None, 12,
         "hand-encoded E9 (assembler prefers short); target 0x0515... "
         "3-byte insn at 0x510, target 0x513+2=0x0515 ODD"),
        ("BR DW", "BR", "regptr16",
         "    BR DW\n" + "    NOP\n" * 2, {"DW": 0x0514}, None, None, 11,
         "target 0x0514 even"),
        ("BR [BW]", "BR", "memptr16",
         "    BR [BW]\n" + "    NOP\n" * 2, dict(MEM_REGS),
         word_ram(0x0800, 0x0514), None, 20, "target word at even 0x0800"),
        ("BR far 0:0x0514", "BR", "far-label",
         "    BR 0x0000:0x0514\n", None, None, None, 15,
         "5-byte EA, even target"),
        ("CALL 0x0600", "CALL", "near-proc",
         "    CALL 0x0600\n" + "    NOP\n" * 2, stk, None, 0x0600, 16,
         "stub at target; SP even 0x0F00"),
        ("CALL DW", "CALL", "regptr16",
         "    CALL DW\n" + "    NOP\n" * 2, dict(stk, DW=0x0600), None,
         0x0600, 14, "stub at target"),
        ("CALL [BW]", "CALL", "memptr16",
         "    CALL word [BW]\n" + "    NOP\n" * 2,
         dict(stk, **MEM_REGS), word_ram(0x0800, 0x0600), 0x0600, 23,
         "pointer at even 0x0800, stub at target"),
        ("CALL far 0:0x0600", "CALL", "far-proc",
         "    CALL 0x0000:0x0600\n" + "    NOP\n" * 2, stk, None, 0x0600,
         21, "5-byte 9A, stub at target"),
        ("RET", "RET", "",
         "    RET\n" + "    NOP\n" * 8, stk, word_ram(0x0F00, 0x0511),
         None, 15, "returns to 0x0511 (next byte); jump still flushes"),
        ("RET 4", "RET", "pop-value",
         "    RET 4\n" + "    NOP\n" * 8, stk, word_ram(0x0F00, 0x0513),
         None, 20, "returns to 0x0513; SP += 4 extra"),
    ]
    for i, (name, mnem, pat, xline, regs, ram, stub, doc, note) in \
            enumerate(uncond):
        rec = form_lookup(a, mnem, pat)
        src = nop16 + xline + "    NOP\n" * 8
        results.append(measure_flow(a, host, name, rec, src, regs, doc,
                                    tag=f"fu{i}", ram=ram, stub_linear=stub,
                                    note=note))
    save(results, [])
    return 0


#----------------------------------------------------------------------------
# mission 4: string primitives (single ops via fspacing; REP observed raw)
#----------------------------------------------------------------------------

def cmd_string(host):
    a = Assembler()
    results, skipped = run_cases(host, [
        ("MOVBKB", dict(STRING_REGS), {"note": "DS0:IX=0800 -> DS1:IY=0900, DIR=0"}),
        ("MOVBKW", dict(STRING_REGS), {"note": "even src/dst, DIR=0"}),
        ("CMPBKB", dict(STRING_REGS), {"note": "fill==fill, Z=1 result"}),
        ("CMPBKW", dict(STRING_REGS), {"note": "even src/dst"}),
        ("LDMB", dict(STRING_REGS), {"note": "load 0x0800"}),
        ("LDMW", dict(STRING_REGS), {"note": "even"}),
        ("STMB", dict(STRING_REGS, AW=0x90), {"note": "store 0x90 at 0x0900"}),
        ("STMW", dict(STRING_REGS, AW=0x9090), {"note": "even dst"}),
    ])
    save(results, skipped)

    # REP forms: F-op attribution unknown a priori — print the raw gap
    # structure around the sled position and record totals.
    print("\nREP cases (gaps 14..22; X starts at F-pop 16):")
    for i, (prefix, insn, cw, extra) in enumerate([
            ("REP", "STMW", 3, {"AW": 0x9090}),
            ("REP", "STMB", 3, {"AW": 0x90}),
            ("REP", "MOVBKW", 3, {}),
            ("REPE", "CMPBKW", 3, {}),
            ("REP", "STMW", 0, {"AW": 0x9090}),
    ]):
        regs = dict(STRING_REGS, CW=cw, **extra)
        src = "    NOP\n" * 16 + f"    {prefix}\n    {insn}\n" + \
            "    NOP\n" * 8
        gaps, fpops = fgap_run(a, host, src, regs, tag=f"rp{i}")
        print(f"{prefix} {insn} CW={cw}: nF={len(fpops)} "
              f"gaps[14:22]={gaps[14:22]}")
    return 0


#----------------------------------------------------------------------------
# mission 4: BCD, TRANS, IN/OUT, mem-CL shifts
#----------------------------------------------------------------------------

def cmd_misc(host):
    cases = [
        ("ADJBA", {"AW": 0x000B}, {}),
        ("ADJBA", {"AW": 0x0004}, {"note": "no adjust path"}),
        ("ADJ4A", {"AW": 0x009A}, {}),
        ("ADJ4A", {"AW": 0x0033}, {"note": "no adjust path"}),
        ("ADJBS", {"AW": 0x000B}, {}),
        ("ADJ4S", {"AW": 0x009A}, {}),
        ("CVTBD", {"AW": 0x0053}, {}),
        ("CVTBD", {"AW": 0x00FF}, {"note": "max dividend"}),
        ("CVTDB", {"AW": 0x0503}, {}),
        ("CVTBW", {"AW": 0x0080}, {}),
        ("CVTWL", {"AW": 0x8000}, {"note": "negative -> DW=FFFF"}),
        ("CVTWL", {"AW": 0x0001}, {"note": "positive -> DW=0"}),
        ("TRANS", dict(MEM_REGS, AW=0x0005), {"note": "table 0x0800, AL=5"}),
        ("IN AL, 0x40", None, {}),
        ("IN AW, 0x40", None, {"note": "even port"}),
        ("IN AL, DW", {"DW": 0x0040}, {}),
        ("IN AW, DW", {"DW": 0x0040}, {"note": "even port"}),
        ("OUT 0x40, AL", {"AW": 0x55}, {}),
        ("OUT 0x40, AW", {"AW": 0x5555}, {"note": "even port"}),
        ("OUT DW, AL", {"DW": 0x0040, "AW": 0x55}, {}),
        ("OUT DW, AW", {"DW": 0x0040, "AW": 0x5555}, {"note": "even port"}),
        ("SHL word [BW], CL", dict(MEM_REGS, CW=1), {"n": 1, "note": "CL=1"}),
        ("SHL word [BW], CL", dict(MEM_REGS, CW=4), {"n": 4, "note": "CL=4"}),
        ("SHL byte [BW], CL", dict(MEM_REGS, CW=4), {"n": 4, "note": "CL=4"}),
        ("ROR word [BW], CL", dict(MEM_REGS, CW=4), {"n": 4, "note": "CL=4"}),
    ]
    results, skipped = run_cases(host, cases)
    save(results, skipped)
    dev = [r for r in results if r["match"] is False]
    for r in dev:
        print(f"  {r['nec_form']:<24} {r['asm']:<24} measured "
              f"{r['measured_cycles']} vs {r['documented_values']} "
              f"({r['deviation']:+d})")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mul", "sweep", "flow", "string", "misc"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    sys.exit({"mul": cmd_mul, "sweep": cmd_sweep, "flow": cmd_flow,
              "string": cmd_string, "misc": cmd_misc}[args.cmd](args.host))


if __name__ == "__main__":
    main()
