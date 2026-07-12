#!/usr/bin/env python3
"""probe_uncertain - Campaign 2 mission 6: architectural probes that retire
instructions.json _uncertain entries with hardware evidence.

Each probe runs a tiny program via v30run.run_test and inspects final
architectural state (registers, PSW, memory via readback MOVs). Results
are printed; the conclusions get appended to the _uncertain entries
("resolved" field) and summarized in docs/facts/measurements.md.

Usage: probe_uncertain.py all [--host ...]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                          # noqa: E402
from v30run import run_test                           # noqa: E402

PSW_CY, PSW_P, PSW_AC, PSW_Z, PSW_S, PSW_V = 0x01, 0x04, 0x10, 0x40, 0x80, 0x800
STACK = {"SS": 0, "SP": 0x0F00}


def run(a, host, src, regs=None, tag="pu", ivt=None, ram=None,
        stub_linear=None):
    code = a.assemble(src, org=0x0500)
    regs_full = dict({"PS": 0, "PC": 0x0500}, **(regs or {}))
    res = run_test(regs=regs_full, instr=code, host=host, tag=tag,
                   ivt=ivt, ram=ram, stub_linear=stub_linear)
    return res["regs"]


def flags(psw):
    return "".join(n for n, b in
                   [("V", PSW_V), ("S", PSW_S), ("Z", PSW_Z),
                    ("AC", PSW_AC), ("P", PSW_P), ("CY", PSW_CY)]
                   if psw & b)


def probe_shr_cy(a, host):
    """[31] SHR formulas print 'CY <- MSB' but prose says LSB."""
    print("\n[31] SHR: CY gets MSB or LSB?")
    for i, (al, src, expect_lsb, expect_msb) in enumerate([
            (0x80, "SHR AL, 1", 0, 1),      # LSB=0, MSB=1: discriminates
            (0x01, "SHR AL, 1", 1, 0),      # LSB=1, MSB=0: discriminates
            (0x04, "SHR AL, CL", 1, None),  # CL=3: last bit out = 1
    ]):
        regs = run(a, host, f"    {src}\n", {"AW": al, "CW": 3},
                   tag=f"shr{i}")
        cy = regs["PSW"] & PSW_CY
        print(f"  AL={al:#04x} {src}: AL'={regs['AW'] & 0xFF:#04x} CY={cy} "
              f"-> {'LSB rule' if cy == expect_lsb else 'MSB rule'}")


def probe_brk_bytes(a, host):
    """[46] BRK imm8 'Bytes: 1' misprint? Handler RETIs; if the return
    address were opcode+1, the imm byte 0x41 (INC CW) would execute."""
    print("\n[46] BRK imm8 length via RETI return address:")
    regs = run(a, host, "    BRK 0x41\n    INC AW\n    INC DW\n",
               dict(STACK, AW=0, CW=0, DW=0),
               ivt={0x41: (0, 0x0700)}, ram=[(0x0700, 0xCF)],  # RETI
               tag="brk")
    print(f"  AW={regs['AW']} CW={regs['CW']} DW={regs['DW']} "
          f"SP={regs['SP']:#06x}")
    verdict = "2 bytes (return past imm8)" if regs["CW"] == 0 else \
        "1 byte?! imm executed as INC CW"
    print(f"  -> BRK imm8 is {verdict}")


def probe_rorc_v(a, host):
    """[38] RORC mem,imm8 V=U vs reg,imm8 V=X: do both forms treat V the
    same on identical data?"""
    print("\n[38] RORC V flag: reg,imm8 vs mem,imm8 (same data):")
    for i, (val, cnt, v0, cy0) in enumerate([
            (0x80, 2, 1, 0), (0x80, 2, 0, 0), (0x01, 1, 1, 1),
            (0x42, 3, 0, 1)]):
        psw = (PSW_V if v0 else 0) | (PSW_CY if cy0 else 0)
        r1 = run(a, host, f"    RORC AL, {cnt}\n",
                 {"AW": val, "PSW": psw}, tag=f"rvr{i}")
        r2 = run(a, host, f"    RORC byte [BW], {cnt}\n    MOV DL, byte [BW]\n",
                 {"BW": 0x0800, "DS0": 0, "PSW": psw},
                 ram=[(0x0800, val)], tag=f"rvm{i}")
        v1, v2 = (r1["PSW"] & PSW_V) >> 11, (r2["PSW"] & PSW_V) >> 11
        res1, res2 = r1["AW"] & 0xFF, r2["DW"] & 0xFF
        print(f"  val={val:#04x} cnt={cnt} V0={v0} CY0={cy0}: "
              f"reg: res={res1:#04x} V={v1} | mem: res={res2:#04x} V={v2} "
              f"{'SAME' if (v1, res1) == (v2, res2) else 'DIFFER'}")


def probe_adj4a(a, host):
    """[23] ADJ4A condition printed '< 9', standard DAA is '> 9'."""
    print("\n[23] ADJ4A low-nibble condition:")
    for i, al in enumerate([0x0A, 0x33, 0x09]):
        regs = run(a, host, "    ADJ4A\n", {"AW": al}, tag=f"daa{i}")
        print(f"  AL={al:#04x} -> AL'={regs['AW'] & 0xFF:#04x} "
              f"flags={flags(regs['PSW'])}")


def probe_div_conditions(a, host):
    """[19][21][22] DIVU/DIV overflow condition misprints + pushed PC.
    Benign cases: plain run (any trap would hang/corrupt -> visible).
    Overflow cases: IVT 0 -> pop handler at 0x0700 (POP BW=PC, CW=PS,
    DW=PSW), store stub right after it."""
    handler = [(0x0700, 0x5B), (0x0701, 0x59), (0x0702, 0x5A)]

    print("\n[19] DIVU boundary (quotient == FFH must not trap):")
    regs = run(a, host, "    DIVU CL\n", {"AW": 0x01FE, "CW": 2}, tag="dvu0")
    print(f"  AW=0x01FE/CL=2 (q=0xFF boundary): AW={regs['AW']:#06x} "
          f"(AL=q, AH=rem) -> {'no trap' if regs['AW'] == 0x00FF else '??'}")
    regs = run(a, host, "    DIVU CL\n", dict(STACK, AW=0x0200, CW=2),
               ivt={0: (0, 0x0700)}, ram=handler, stub_linear=0x0703,
               tag="dvu1")
    print(f"  AW=0x0200/CL=2 (q=0x100): SP={regs['SP']:#06x} "
          f"AW={regs['AW']:#06x} pushedPC={regs['BW']:#06x} "
          f"pushedPS={regs['CW']:#06x} "
          f"-> {'TRAP, regs preserved' if regs['AW'] == 0x0200 else '??'}")

    print("[22] DIV reg16 condition ('< 7FFFH' as printed would trap "
          "benign divides):")
    regs = run(a, host, "    DIV CW\n", {"AW": 0x1000, "DW": 0, "CW": 2},
               tag="dvs0")
    print(f"  0000:1000/2 (q=0x0800 benign): AW={regs['AW']:#06x} "
          f"DW={regs['DW']:#06x} -> "
          f"{'no trap, q correct' if regs['AW'] == 0x0800 else '??'}")
    regs = run(a, host, "    DIV CW\n", dict(STACK, AW=0, DW=0x1000, CW=2),
               ivt={0: (0, 0x0700)}, ram=handler, stub_linear=0x0703,
               tag="dvs1")
    print(f"  1000:0000/2 (q>0x7FFF): SP={regs['SP']:#06x} "
          f"AW={regs['AW']:#06x} DW-in was 0x1000, "
          f"pushedPC={regs['BW']:#06x} pushedPS={regs['CW']:#06x} "
          f"pushedPSW={regs['DW']:#06x}")


def probe_mul_flags(a, host):
    """[15][17] MUL 'sign extension of AH' typos: verify actual CY/V rule."""
    print("\n[15][17] MUL CY/V semantics (0 when high half == sign ext):")
    for i, (al, cl, desc) in enumerate([
            (0xFF, 0x01, "-1*1 = -1, AH=sign ext -> CY/V=0"),
            (0x40, 0x04, "0x40*4 = 0x100, AH!=ext -> CY/V=1"),
            (0x02, 0x03, "6, fits -> 0")]):
        regs = run(a, host, "    MUL CL\n", {"AW": al, "CW": cl},
                   tag=f"mf{i}")
        cy, v = regs["PSW"] & PSW_CY, (regs["PSW"] & PSW_V) >> 11
        print(f"  AL={al:#04x} CL={cl:#04x}: AW={regs['AW']:#06x} "
              f"CY={cy} V={v}  ({desc})")


def probe_bitop_encodings(a, host):
    """[26][27][28][29] scan-illegible byte-boxes: execute the assumed
    encodings and verify the architectural result via readback."""
    print("\n[26-29] bit-op mem encodings (assumed boxes) execute correctly:")
    mem = {"BW": 0x0800, "DS0": 0, "CW": 1}
    cases = [
        ("TEST1 word [BW], 10", "    MOV DW, [BW]\n", [(0x0800, 0x00),
                                                       (0x0801, 0x04)],
         lambda r: (r["PSW"] & PSW_Z) == 0, "bit10 set -> Z=0"),
        ("TEST1 word [BW], 10", "    MOV DW, [BW]\n", [(0x0800, 0x00),
                                                       (0x0801, 0x00)],
         lambda r: (r["PSW"] & PSW_Z) != 0, "bit10 clear -> Z=1"),
        ("NOT1 word [BW], 4", "    MOV DW, [BW]\n", None,
         lambda r: r["DW"] == 0x9080, "0x9090 ^ 0x0010 = 0x9080"),
        ("CLR1 word [BW], 4", "    MOV DW, [BW]\n", None,
         lambda r: r["DW"] == 0x9080, "0x9090 & ~0x0010 = 0x9080"),
        ("SET1 byte [BW+4], CL", "    MOV DL, byte [BW+4]\n", None,
         lambda r: (r["DW"] & 0xFF) == 0x92, "CL=1: 0x90|0x02 = 0x92 "
         "(disp8 form)"),
    ]
    for i, (insn, readback, ram, check, desc) in enumerate(cases):
        code = a.assemble(insn)
        regs = run(a, host, f"    {insn}\n" + readback, dict(mem),
                   ram=ram, tag=f"bo{i}")
        ok = check(regs)
        print(f"  {insn:<24} [{code.hex(' ')}] {desc}: "
              f"{'OK' if ok else 'FAIL'} (DW={regs['DW']:#06x} "
              f"flags={flags(regs['PSW'])})")


def probe_rolc_cl(a, host):
    """[35] ROLC reg,CL clocks printed '7 = n' -> timing check of 7+n."""
    from exp_biu import fspacing_case
    print("\n[35] ROLC reg,CL timing (expect 14 = 7+4 +3 class delta):")
    gap, nop = fspacing_case(a, host, "ROLC AW, CL (CL=4)",
                             "    ROLC AW, CL\n", {"CW": 4}, tag="rolc")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    a = Assembler()
    for fn in (probe_shr_cy, probe_brk_bytes, probe_rorc_v, probe_adj4a,
               probe_div_conditions, probe_mul_flags, probe_bitop_encodings,
               probe_rolc_cl):
        fn(a, args.host)
    return 0


if __name__ == "__main__":
    sys.exit(main())
