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


def doc_values(rec, w, n=None, odd=False):
    """Applicable documented clock values for our conditions (uPD70116,
    even-aligned operands unless odd=True, operand width w).
    Returns (set, verbatim list)."""
    vals, verbatim = set(), []
    for c in rec["clocks"]:
        wl = c["when"].lower()
        if odd:
            # odd-operand case: take the uPD70116 odd-address rows
            if "70116" in wl and "even" in wl:
                continue
            if "70108" in wl and "70116" not in wl:
                continue
        else:
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

def measure(a, host, asm, regs=None, n=None, ram=None, tag="sw", note=None,
            odd=False, org=0x0500):
    """Assemble one instruction, measure its F-gap, compare to docs.
    Returns the result record (also printed by fspacing_case)."""
    code = a.assemble(asm)
    rec = a.last_rec
    w = a.last_w if getattr(a, "last_w", None) is not None else derive_width(asm)
    vals, verbatim = doc_values(rec, w, n, odd=odd)
    label = f"{asm}"
    gap, nop_t = fspacing_case(a, host, label, f"    {asm}\n",
                               regs_extra=regs, tag=tag, ram=ram, org=org)
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
    if odd:
        out["odd_operand"] = True
    if org != 0x0500:
        out["anchor"] = f"0x{org:04X}"
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
        return (r["nec_form"], r["asm"],
                json.dumps(r.get("operands", {}), sort_keys=True),
                r.get("odd_operand"), r.get("anchor"))
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


def fgap_run(a, host, src, regs=None, tag="fl", ram=None, stub_linear=None,
             ivt=None):
    """Assemble a full sled at 0x0500, run, return (gaps, fpops)."""
    code = a.assemble(src, org=0x0500)
    regs_full = dict({"PS": 0, "PC": 0x0500}, **(regs or {}))
    res = run_test(regs=regs_full, instr=code, host=host, tag=tag, ram=ram,
                   stub_linear=stub_linear, ivt=ivt)
    ev = queue_timeline(res["recs"], res["meta"])
    fpops = [e["idx"] for e in ev if e["q"] == "F"]
    gaps = [b - x for x, b in zip(fpops, fpops[1:])]
    return gaps, fpops


def measure_flow(a, host, name, form_rec, src, regs, doc_expect, tag,
                 note=None, ram=None, stub_linear=None, x_bytes=None,
                 ivt=None):
    """One control-flow case: X at F-pop index 16, gap 16 = its time.
    doc_expect: the single documented value applicable to this case."""
    gaps, fpops = fgap_run(a, host, src, regs, tag=tag, ram=ram,
                           stub_linear=stub_linear, ivt=ivt)
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


#----------------------------------------------------------------------------
# mission 5: alignment penalties (odd word operands; odd code anchor)
#----------------------------------------------------------------------------

ODD_MEM = {"BW": 0x0801, "IX": 0x0010, "DS0": 0}


def cmd_odd(host):
    # A) odd-aligned word memory operands (code stays even-anchored)
    cases = [
        ("MOV DW, [BW]", ODD_MEM, {"odd": True, "note": "odd word load"}),
        ("MOV [BW], DW", ODD_MEM, {"odd": True, "note": "odd word store"}),
        ("ADD DW, [BW]", ODD_MEM, {"odd": True}),
        ("ADD [BW], DW", ODD_MEM, {"odd": True, "note": "odd RMW"}),
        ("INC word [BW]", ODD_MEM, {"odd": True, "note": "odd RMW"}),
        ("XCH [BW], DW", ODD_MEM, {"odd": True, "note": "odd RMW"}),
        ("MOV AW, [0x0801]", {"DS0": 0}, {"odd": True, "note": "odd direct load"}),
        ("MOV [0x0801], AW", {"DS0": 0}, {"odd": True, "note": "odd direct store"}),
        ("MOV DL, byte [BW]", ODD_MEM,
         {"note": "byte at odd addr - no split expected"}),
        ("MULU word [BW]", dict(ODD_MEM, AW=7),
         {"odd": True, "ram": [(0x0801, 5), (0x0802, 0)]}),
        ("SHL word [BW], 1", ODD_MEM, {"odd": True, "note": "odd RMW"}),
        ("PUSH BW", {"SS": 0, "SP": 0x0F01}, {"odd": True, "note": "SP odd"}),
        ("POP BW", {"SS": 0, "SP": 0x0F01}, {"odd": True, "note": "SP odd"}),
        ("STMW", dict(STRING_REGS, IY=0x0901, AW=0x9090),
         {"odd": True, "note": "odd string dst"}),
        ("LDMW", dict(STRING_REGS, IX=0x0801), {"odd": True, "note": "odd src"}),
    ]
    results, skipped = run_cases(host, cases)

    # B) odd code anchor (PC=0x0501): representative forms, even operands
    print("\nodd anchor (PC=0x0501):")
    a = Assembler()
    for i, (asm, regs, kw) in enumerate([
            ("NOP", None, {}),
            ("MOV AW, 0x1234", None, {}),
            ("ADD BW, DW", None, {}),
            ("INC AW", None, {}),
            ("ADD DW, [BW]", MEM_REGS, {}),
            ("MOV [BW], DW", MEM_REGS, {}),
            ("DIVU CW", {"AW": 9, "DW": 0, "CW": 3}, {}),
            ("SHL AW, 1", None, {}),
            ("PUSH BW", STACK_REGS, {}),
            ("MULU CW", {"AW": 7, "CW": 5}, {}),
    ]):
        try:
            r = measure(a, host, asm, regs=regs, tag=f"oa{i}", org=0x0501,
                        note="odd anchor", **kw)
            results.append(r)
            if r["match"] is False:
                print(f"    ^ DEVIATION {r['deviation']:+d} vs "
                      f"{r['documented_values']}")
        except Exception as e:                        # noqa: BLE001
            print(f"{asm:<28} SKIPPED: {e}")
            skipped.append({"asm": asm, "reason": f"odd anchor: {e}"})
    save(results, skipped)
    return 0


#----------------------------------------------------------------------------
# mission 10: remaining coverage — 0F extension set, prefixes, stack/misc,
# trap paths, HALT
#----------------------------------------------------------------------------

def measure_raw(a, host, name, mnem, pattern, x_src, regs, doc_vals, tag,
                ram=None, note=None):
    """fspacing for a DB-encoded form the assembler can't emit; documented
    values supplied by the caller (from the form's instructions.json row)."""
    rec = form_lookup(a, mnem, pattern)
    gap, nop_t = fspacing_case(a, host, name, x_src, regs_extra=regs,
                               tag=tag, ram=ram)
    vals = set(doc_vals or [])
    out = {
        "nec_form": rec["nec_form"],
        "asm": name,
        "bytes": a.assemble(x_src, org=0x0510).hex(" "),
        "operands": {k: f"0x{v:04X}" for k, v in (regs or {}).items()},
        "measured_cycles": gap,
        "nop_baseline": nop_t,
        "documented_clocks": [(c["when"] + ": " if c["when"] else "")
                              + c["value"] for c in rec["clocks"]],
        "documented_values": sorted(vals),
        "match": gap in vals if vals and gap is not None else None,
        "deviation": (0 if gap in vals else
                      min((gap - v for v in vals), key=abs))
                     if vals and gap is not None else None,
    }
    if note:
        out["note"] = note
    if nop_t != 3:
        out["warn"] = f"NOP baseline {nop_t} != 3 (queue not saturated?)"
    if out["match"] is False:
        print(f"    ^ DEVIATION {out['deviation']:+d} vs "
              f"{out['documented_values']}")
    return out


def measure_prefixed(a, host, name, x_src, n_prefix, regs, tag, note=None):
    """Prefixed instruction: each prefix retires with its own F pop (REP
    finding, measurements.md). Record per-F gaps and the total."""
    gaps, fpops = fgap_run(a, host,
                           "    NOP\n" * 16 + x_src + "    NOP\n" * 8,
                           regs, tag=tag)
    parts = gaps[16:16 + n_prefix + 1]
    total = sum(parts) if len(parts) == n_prefix + 1 else None
    print(f"{name:<28} parts={parts} total={total}")
    return {
        "nec_form": "prefix measurement",
        "asm": name,
        "bytes": a.assemble(x_src, org=0x0510).hex(" "),
        "operands": {k: f"0x{v:04X}" for k, v in (regs or {}).items()},
        "measured_cycles": total,
        "per_f_gaps": parts,
        "nop_baseline": sorted(gaps[8:15])[3] if len(gaps) > 15 else None,
        "documented_clocks": [],
        "documented_values": [],
        "match": None,
        "deviation": None,
        "note": note or "prefix pops its own F; total = prefix(es) + insn",
    }


def cmd_more(host):
    a = Assembler()
    results, skipped = [], []
    bit_regs = dict(MEM_REGS, CW=3)      # CL=3 for reg,CL / mem,CL forms

    # --- (a) documented 0F extension set: assembler-supported forms ---
    cases = [
        # TEST1 (never timed)
        ("TEST1 AL, CL", dict(CW=3), {"note": "CL=3"}),
        ("TEST1 AW, CL", dict(CW=3), {"note": "CL=3"}),
        ("TEST1 AL, 3", None, {}),
        ("TEST1 AW, 5", None, {}),
        ("TEST1 byte [BW], CL", bit_regs, {"note": "CL=3"}),
        ("TEST1 word [BW], CL", bit_regs, {"note": "CL=3, even mem"}),
        ("TEST1 byte [BW], 3", dict(MEM_REGS), {}),
        ("TEST1 word [BW], 5", dict(MEM_REGS), {"note": "even mem"}),
        # NOT1/CLR1/SET1 mem forms (reg forms measured in mission 3)
        ("NOT1 byte [BW], CL", bit_regs, {"note": "CL=3"}),
        ("NOT1 word [BW], CL", bit_regs, {"note": "CL=3, even mem"}),
        ("NOT1 byte [BW], 3", dict(MEM_REGS), {}),
        ("NOT1 word [BW], 5", dict(MEM_REGS), {"note": "even mem"}),
        ("CLR1 byte [BW], CL", bit_regs, {"note": "CL=3"}),
        ("CLR1 word [BW], CL", bit_regs, {"note": "CL=3, even mem"}),
        ("CLR1 byte [BW], 3", dict(MEM_REGS), {}),
        ("CLR1 word [BW], 5", dict(MEM_REGS), {"note": "even mem"}),
        ("SET1 byte [BW], CL", bit_regs, {"note": "CL=3"}),
        ("SET1 word [BW], CL", bit_regs, {"note": "CL=3, even mem"}),
        ("SET1 byte [BW], 3", dict(MEM_REGS), {}),
        ("SET1 word [BW], 5", dict(MEM_REGS), {"note": "even mem"}),
        # ROL4/ROR4
        ("ROL4 AL", {"AW": 0x0005}, {}),
        ("ROL4 byte [BW]", dict(MEM_REGS, AW=0x0005), {}),
        ("ROR4 AL", {"AW": 0x0005}, {}),
        ("ROR4 byte [BW]", dict(MEM_REGS, AW=0x0005), {}),
        # EXT reg,imm4 (assembler-supported INS/EXT form)
        ("EXT DL, 4", {"DS0": 0, "IX": 0x0800, "DW": 0},
         {"ram": [(0x0800, 0xA5), (0x0801, 0x3C)],
          "note": "bit offset DL=0, len 4; src 0x0800"}),
        # --- (c) stack/misc forms ---
        ("PUSH word [BW]", dict(MEM_REGS, **STACK_REGS), {}),
        ("POP word [BW]", dict(MEM_REGS, **STACK_REGS),
         {"note": "pops fill into [BW]"}),
        ("PUSH PS", STACK_REGS, {}),
        ("POP DS0", STACK_REGS,
         {"note": "DS0=0x9090 after; unused by sled (code via PS)"}),
        ("LDEA BW, [BW+IX]", MEM_REGS, {}),
        ("LDEA BW, [0x0800]", MEM_REGS, {}),
        ("CHKIND DW, [BW]", dict(MEM_REGS, DW=5),
         {"ram": word_ram(0x0800, 0x0000) + word_ram(0x0802, 0xFFFF),
          "note": "in bounds [0,FFFF] - no trap"}),
        ("DISPOSE", {"SS": 0, "SP": 0x0F00, "BP": 0x0F10},
         {"note": "SP=BP; pops fill into BP"}),
        ("BRKV", {"PSW": 0x0000}, {"note": "V=0, no trap (doc row garbled; "
                                   "V=1 path measured separately)"}),
    ]
    r, s = run_cases(host, cases)
    results += r
    skipped += s

    # --- (a) INS/EXT and 4S forms the assembler can't emit: DB-encoded ---
    ins_regs = {"DS1": 0, "IY": 0x0900, "AW": 0x5555, "DW": 0, "CW": 3}
    ext_regs = {"DS0": 0, "IX": 0x0800, "DW": 0, "CW": 7}
    s4_regs = {"DS0": 0, "IX": 0x0800, "DS1": 0, "IY": 0x0900}
    s4_ram = [(0x0800, 0x34), (0x0801, 0x12), (0x0802, 0x78),
              (0x0803, 0x56), (0x0900, 0x11), (0x0901, 0x11),
              (0x0902, 0x11), (0x0903, 0x11)]
    raw_cases = [
        ("INS DL, CL", "INS", "reg1, reg2", "    DB 0x0F, 0x31, 0xCA\n",
         ins_regs, range(31, 118), None,
         "offset DL=0, len CL=3, dst DS1:IY=0x0900"),
        ("INS DL, 4", "INS", "reg8,imm4",
         "    DB 0x0F, 0x39, 0xC2, 0x04\n",
         ins_regs, range(67, 88), None, "offset DL=0, len 4"),
        ("EXT DL, CL", "EXT", "reg1, reg2", "    DB 0x0F, 0x33, 0xCA\n",
         ext_regs, range(26, 56), [(0x0800, 0xA5), (0x0801, 0x3C)],
         "offset DL=0, len CL=7, src DS0:IX=0x0800"),
        ("ADD4S (CL=2)", "ADD4S", "[DS1-spec:]dst-string,[seg-spec:]src-string",
         "    DB 0x0F, 0x20\n", dict(s4_regs, CW=2), [7 + 19 * 1], s4_ram,
         "n=1 byte pair; doc 7+19n"),
        ("ADD4S (CL=4)", "ADD4S", "[DS1-spec:]dst-string,[seg-spec:]src-string",
         "    DB 0x0F, 0x20\n", dict(s4_regs, CW=4), [7 + 19 * 2], s4_ram,
         "n=2; doc 7+19n"),
        ("ADD4S (CL=6)", "ADD4S", "[DS1-spec:]dst-string,[seg-spec:]src-string",
         "    DB 0x0F, 0x20\n", dict(s4_regs, CW=6), [7 + 19 * 3], s4_ram,
         "n=3; doc 7+19n"),
        ("SUB4S (CL=4)", "SUB4S", "[DS1-spec:]dst-string,[seg-spec:]src-string",
         "    DB 0x0F, 0x22\n", dict(s4_regs, CW=4), [7 + 19 * 2], s4_ram,
         "n=2; doc 7+19n"),
        ("CMP4S (CL=4)", "CMP4S", "[DS1-spec:]dst-string,[seg-spec:]src-string",
         "    DB 0x0F, 0x26\n", dict(s4_regs, CW=4), [7 + 19 * 2], s4_ram,
         "n=2; doc 7+19n"),
        # PREPARE via DB (assembler mis-encodes imm16 operand order)
        ("PREPARE 8, 0", "PREPARE", "imm16,imm8",
         "    DB 0xC8, 0x08, 0x00, 0x00\n",
         {"SS": 0, "SP": 0x0F00, "BP": 0x0F20}, [12],
         None, "imm8=0: doc 12; DB-encoded (assembler imm16 bug)"),
        ("PREPARE 8, 1", "PREPARE", "imm16,imm8",
         "    DB 0xC8, 0x08, 0x00, 0x01\n",
         {"SS": 0, "SP": 0x0F00, "BP": 0x0F20}, None,
         None, "imm8=1: no doc row (manual gap)"),
        ("PREPARE 8, 2", "PREPARE", "imm16,imm8",
         "    DB 0xC8, 0x08, 0x00, 0x02\n",
         {"SS": 0, "SP": 0x0F00, "BP": 0x0F20}, [19 + 8 * 1],
         None, "imm8=2: doc 19+8(imm8-1)"),
    ]
    for i, (name, mnem, pat, src, regs, doc, ram, note) in \
            enumerate(raw_cases):
        try:
            results.append(measure_raw(a, host, name, mnem, pat, src, regs,
                                       doc, tag=f"mr{i}", ram=ram,
                                       note=note))
        except Exception as e:                        # noqa: BLE001
            print(f"{name:<28} SKIPPED: {e}")
            skipped.append({"asm": name, "reason": str(e)})

    # --- (b) segment-override prefix cost (prefix = own F pop) ---
    pfx_cases = [
        ("DS0: MOV AW,[BW] (redundant)", "    DB 0x3E\n    MOV AW, [BW]\n",
         1, dict(MEM_REGS), "baseline MOV AW,[BW] = 13"),
        ("DS1: MOV AW,[BW]", "    DB 0x26\n    MOV AW, [BW]\n",
         1, dict(MEM_REGS, DS1=0), "override to DS1=0 (same phys)"),
        ("SS: MOV AW,[BW]", "    DB 0x36\n    MOV AW, [BW]\n",
         1, dict(MEM_REGS, SS=0), "override to SS=0"),
        ("DS1: DS0: MOV AW,[BW] (stacked)",
         "    DB 0x26\n    DB 0x3E\n    MOV AW, [BW]\n",
         2, dict(MEM_REGS, DS1=0), "two prefixes, last wins"),
        ("DS0: ADD BW,DW (no mem ref)", "    DB 0x3E\n    ADD BW, DW\n",
         1, None, "prefix on pure register op (baseline 3)"),
        ("BUSLOCK NOP", "    BUSLOCK\n    NOP\n",
         1, None, "LOCK prefix (doc 2) + NOP (3)"),
    ]
    for i, (name, src, npfx, regs, note) in enumerate(pfx_cases):
        try:
            results.append(measure_prefixed(a, host, name, src, npfx, regs,
                                            tag=f"px{i}", note=note))
        except Exception as e:                        # noqa: BLE001
            print(f"{name:<28} SKIPPED: {e}")
            skipped.append({"asm": name, "reason": str(e)})

    # --- (c) trap/return paths via flow measurement (IVT hooked) ---
    stk = dict(STACK_REGS)
    flow_cases = [
        # RETI: frame PC=0x0511 (next byte), PS=0, PSW=0xF002 at SP
        ("RETI", "RETI", "", "    RETI\n" + "    NOP\n" * 8, stk,
         word_ram(0x0F00, 0x0511) + word_ram(0x0F02, 0x0000) +
         word_ram(0x0F04, 0xF002), None, 27,
         "frame pops to 0x0511; includes flush like RET"),
        ("BRK 3 (trap)", "BRK", "3", "    BRK 3\n" + "    NOP\n" * 8, stk,
         None, {3: (0x0000, 0x0511)}, 38,
         "vector 3 hooked to next byte 0x0511"),
        ("BRKV (V=1, trap)", "BRKV", "", "    BRKV\n" + "    NOP\n" * 8,
         dict(stk, PSW=0x0800), None, {4: (0x0000, 0x0511)}, 52,
         "V=1; vector 4 hooked to 0x0511; doc row garbled (52 is the "
         "70108 V=1 row)"),
        ("CHKIND DW,[BW] (trap)", "CHKIND", "reg16,mem32",
         "    CHKIND DW, [BW]\n" + "    NOP\n" * 8,
         dict(stk, **MEM_REGS, DW=0x0005),
         word_ram(0x0800, 0x0000) + word_ram(0x0802, 0x0004),
         {5: (0x0000, 0x0512)}, 55,
         "DW=5 > upper bound 4; vector 5 hooked past the 2-byte insn; "
         "doc 53-56"),
    ]
    nop16 = "    NOP\n" * 16
    for i, (name, mnem, pat, xline, regs, ram, ivt, doc, note) in \
            enumerate(flow_cases):
        try:
            rec = form_lookup(a, mnem, pat) if pat != "3" else \
                form_lookup(a, "BRK", "3")
            results.append(measure_flow(a, host, name, rec,
                                        nop16 + xline, regs, doc,
                                        tag=f"tf{i}", ram=ram, ivt=ivt,
                                        note=note))
        except Exception as e:                        # noqa: BLE001
            print(f"{name:<28} SKIPPED: {e}")
            skipped.append({"asm": name, "reason": str(e)})

    # --- (d) HALT: no done marker ever; measure from the raw capture ---
    try:
        import testimage
        from v30run import run_image, extract_txns_large, KIND
        src = "    NOP\n" * 16 + "    HALT\n" + "    NOP\n" * 8
        code = a.assemble(src, org=0x0500)
        image, meta = testimage.compose(regs={"PS": 0, "PC": 0x0500},
                                        instr=code)
        recs = run_image(image, host, tag="halt")
        ev = queue_timeline(recs, meta)
        fpops = [e["idx"] for e in ev if e["q"] == "F"]
        txns = extract_txns_large(recs)
        halts = [t for t in txns if KIND[t["kind"]] == "HALT"]
        f16 = fpops[16] if len(fpops) > 16 else None
        h0 = halts[0]["start"] if halts else None
        gap = (h0 - f16) if (f16 is not None and h0 is not None) else None
        last_bus = max((t["end"] for t in txns), default=None)
        print(f"HALT: F-pop@{f16} first HALT bus cycle T1@{h0} "
              f"delta={gap}; {len(halts)} HALT txns; last bus activity "
              f"rec {last_bus} of {recs[-1]['idx']}")
        results.append({
            "nec_form": "HALT (no operand)", "asm": "HALT",
            "bytes": "f4", "operands": {},
            "measured_cycles": gap, "nop_baseline": None,
            "documented_clocks": ["2"], "documented_values": [2],
            "match": gap == 2 if gap is not None else None,
            "deviation": (gap - 2) if gap is not None else None,
            "note": "metric = F-pop to HALT bus-cycle T1 (no next F "
                    "exists); bus idles after, done marker never arrives "
                    "(quarantined by design)",
        })
    except Exception as e:                            # noqa: BLE001
        print(f"HALT SKIPPED: {e}")
        skipped.append({"asm": "HALT", "reason": str(e)})

    save(results, skipped)
    dev = [r for r in results if r["match"] is False]
    print(f"\n{len(results)} measured, {len(dev)} deviations, "
          f"{len(skipped)} skipped")
    for r in dev:
        print(f"  {r['nec_form']:<24} {r['asm']:<28} measured "
              f"{r['measured_cycles']} vs {r['documented_values']} "
              f"({r['deviation']:+d})")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mul", "sweep", "flow", "string", "misc",
                                    "odd", "more"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    sys.exit({"mul": cmd_mul, "sweep": cmd_sweep, "flow": cmd_flow,
              "string": cmd_string, "misc": cmd_misc,
              "odd": cmd_odd, "more": cmd_more}[args.cmd](args.host))


if __name__ == "__main__":
    main()
