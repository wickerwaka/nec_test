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


#----------------------------------------------------------------------------
# mission 11 batch 2: remaining _uncertain entries
#----------------------------------------------------------------------------

def run_full(a, host, src, regs=None, tag="pu", ivt=None, ram=None):
    code = a.assemble(src, org=0x0500)
    regs_full = dict({"PS": 0, "PC": 0x0500}, **(regs or {}))
    return run_test(regs=regs_full, instr=code, host=host, tag=tag,
                    ivt=ivt, ram=ram)


def probe_cmpbk_odd_slope(a, host):
    """[3] CMPBK odd-address repeat clocks printed 7+22/rep on a garbled
    line. Measure REPE CMPBKW at odd src/dst, CW=1..3: slope should be 22
    if the layout reading is right (even slope measured 14; odd = +8 for
    two split word reads per iteration)."""
    from sweep_timing import fgap_run
    print("\n[3] REPE CMPBKW odd-address slope (expect 22/rep):")
    totals = []
    for cw in (1, 2, 3):
        regs = {"DS0": 0, "IX": 0x0801, "DS1": 0, "IY": 0x0901, "CW": cw}
        src = "    NOP\n" * 16 + "    REPE\n    CMPBKW\n" + "    NOP\n" * 8
        gaps, _ = fgap_run(a, host, src, regs, tag=f"cbo{cw}")
        tot = gaps[16] + gaps[17]
        totals.append(tot)
        print(f"  CW={cw}: REP F {gaps[16]} + insn {gaps[17]} = {tot}")
    slopes = [b - x for x, b in zip(totals, totals[1:])]
    print(f"  totals={totals} slopes={slopes} -> "
          f"{'7+22/rep layout reading CONFIRMED' if all(s == 22 for s in slopes) else 'slope != 22'}")


def probe_ins_max(a, host):
    """[6] INS reg,reg even max printed 117 (> odd max 113). Time the
    worst case (16-bit field, offset 15 -> byte-boundary work)."""
    from exp_biu import fspacing_case
    print("\n[6] INS reg,reg worst-ish cases vs printed max 117:")
    for dl, cl in ((0, 15), (15, 15), (7, 15)):
        regs = {"DS1": 0, "IY": 0x0900, "AW": 0xFFFF, "DW": dl, "CW": cl}
        gap, _ = fspacing_case(a, host, f"INS DL,CL off={dl} len={cl+1}",
                               "    DB 0x0F, 0x31, 0xCA\n", regs,
                               tag=f"insx{dl}")


def probe_inm_iy(a, host):
    """[9] INM prose says IX auto-incremented; operation says IY."""
    print("\n[9] INM (6C): which index register moves?")
    regs = run(a, host, "    DB 0x6C\n",
               {"DS1": 0, "IY": 0x0900, "IX": 0x0010, "DW": 0x0040},
               tag="inm")
    print(f"  IY 0x0900 -> {regs['IY']:#06x}, IX 0x0010 -> "
          f"{regs['IX']:#06x} -> "
          f"{'IY updated (prose typo confirmed)' if regs['IY'] == 0x0901 and regs['IX'] == 0x0010 else '??'}")


def probe_add_acc_imm(a, host):
    """[11] ADD acc,imm operation printed without '+'."""
    print("\n[11] ADD AW,imm arithmetic:")
    regs = run(a, host, "    ADD AW, 0x1111\n", {"AW": 0x1111}, tag="aai")
    print(f"  0x1111 + 0x1111 = {regs['AW']:#06x} -> "
          f"{'addition confirmed' if regs['AW'] == 0x2222 else '??'}")


def probe_sub_mem_disp(a, host):
    """[12] SUB mem,reg printed without disp byte-boxes; verify the
    displacement form executes (encoding 29 50 40 = [BW+IX+0x40])."""
    print("\n[12] SUB [BW+IX+0x40], DW with displacement:")
    regs = run(a, host,
               "    SUB [BW+IX+0x40], DW\n    MOV CW, [BW+IX+0x40]\n",
               {"BW": 0x0800, "IX": 0x0010, "DS0": 0, "DW": 0x0034},
               ram=[(0x0850, 0x34), (0x0851, 0x12)], tag="smd")
    print(f"  [0x0850]=0x1234 - DW=0x0034 -> readback {regs['CW']:#06x} "
          f"-> {'disp form works (boxes are a print omission)' if regs['CW'] == 0x1200 else '??'}")


def probe_subc_direction(a, host):
    """[14] SUBC reg,reg field layout: which reg is destination?"""
    print("\n[14] SUBC BW, DW (BW=10, DW=3, CY=1):")
    regs = run(a, host, "    SUBC BW, DW\n",
               {"BW": 10, "DW": 3, "PSW": PSW_CY}, tag="sbc")
    print(f"  BW={regs['BW']} DW={regs['DW']} -> "
          f"{'dest=first operand (BW=6), layout as transcribed' if regs['BW'] == 6 and regs['DW'] == 3 else '??'}")


def probe_mul_mem8_transfers(a, host):
    """[16] MUL mem8 'Transfers: None' — count data transfers on the bus."""
    print("\n[16] MULU byte [BW] bus transfers:")
    res = run_full(a, host, "    MULU byte [BW]\n",
                   {"AW": 7, "BW": 0x0800, "DS0": 0},
                   ram=[(0x0800, 5)], tag="mmt")
    data = [t for t in res["test_txns"] if t["kind"] in ("MEMR", "MEMW")]
    print(f"  AW=7 * [0x0800]=5 -> AW={res['regs']['AW']:#06x}; "
          f"data transfers: {[(t['kind'], hex(t['addr'])) for t in data]} "
          f"-> {'1 read (Transfers: None is a misprint)' if len(data) == 1 else '??'}")


def probe_divu_mem16(a, host):
    """[20] DIVU mem16 'AL <- temp / (mem16)' — quotient register width."""
    print("\n[20] DIVU word [BW]: where does the quotient go?")
    regs = run(a, host, "    DIVU word [BW]\n",
               {"AW": 0x0009, "DW": 0, "BW": 0x0800, "DS0": 0},
               ram=[(0x0800, 3), (0x0801, 0)], tag="dvm")
    print(f"  DW:AW=9 / [0x0800]=3 -> AW={regs['AW']:#06x} "
          f"DW={regs['DW']:#06x} -> "
          f"{'AW=quotient, DW=remainder (AL is a misprint for AW)' if regs['AW'] == 3 and regs['DW'] == 0 else '??'}")


def probe_xor_mem_imm_order(a, host):
    """[25] XOR mem,imm byte-box order printed imm-above-disp; the wire
    order the assembler emits (disp first: 81 77 40 34 12) must execute."""
    print("\n[25] XOR word [BW+0x40], 0x1234 (disp8 then imm16 on wire):")
    regs = run(a, host,
               "    XOR word [BW+0x40], 0x1234\n    MOV CW, [BW+0x40]\n",
               {"BW": 0x0800, "DS0": 0},
               ram=[(0x0840, 0xFF), (0x0841, 0xFF)], tag="xmi")
    print(f"  0xFFFF ^ 0x1234 -> readback {regs['CW']:#06x} -> "
          f"{'disp-before-imm confirmed (box layout is a print artifact)' if regs['CW'] == 0xEDCB else '??'}")


def probe_shra_mem(a, host):
    """[32] SHRA mem,imm8 prose says 'register MSB'; verify memory MSB."""
    print("\n[32] SHRA byte [BW], 2 on 0x84:")
    regs = run(a, host, "    SHRA byte [BW], 2\n    MOV DL, byte [BW]\n",
               {"BW": 0x0800, "DS0": 0}, ram=[(0x0800, 0x84)], tag="shm")
    dl = regs["DW"] & 0xFF
    print(f"  0x84 >>a 2 -> {dl:#04x} -> "
          f"{'sign-extends the MEMORY operand (prose typo)' if dl == 0xE1 else '??'}")


def probe_ror_cl_preserved(a, host):
    """[33] ROR reg,CL 'while CL != 0': does CL survive?"""
    print("\n[33] ROR AL, CL with CL=3: is CL consumed?")
    regs = run(a, host, "    ROR AL, CL\n", {"AW": 0x11, "CW": 3},
               tag="rcl")
    print(f"  AL' = {regs['AW'] & 0xFF:#04x} CW = {regs['CW']} -> "
          f"{'CL preserved (microcode uses temp; wording only)' if regs['CW'] == 3 else 'CL CONSUMED?!'}")


def probe_ror_mem_msb(a, host):
    """[34] ROR mem,imm8 formula lacks the MSB<-CY step."""
    print("\n[34] ROR byte [BW], 1 on 0x01 (LSB must reach MSB):")
    regs = run(a, host, "    ROR byte [BW], 1\n    MOV DL, byte [BW]\n",
               {"BW": 0x0800, "DS0": 0}, ram=[(0x0800, 0x01)], tag="rmm")
    dl = regs["DW"] & 0xFF
    print(f"  0x01 ror 1 -> {dl:#04x} -> "
          f"{'MSB set (formula omission is a print artifact)' if dl == 0x80 else '??'}")


def probe_rorc_mem_cl(a, host):
    """[37] RORC mem,CL formula prints 'reg <- reg / 2'; verify the memory
    operand rotates exactly like the reg form (mission 8: 0x80,CY=0,CL=3
    -> 0x10)."""
    print("\n[37] RORC byte [BW], CL (CL=3, CY=0) on 0x80:")
    regs = run(a, host, "    RORC byte [BW], CL\n    MOV DL, byte [BW]\n",
               {"BW": 0x0800, "DS0": 0, "CW": 3, "PSW": 0},
               ram=[(0x0800, 0x80)], tag="rmc")
    dl = regs["DW"] & 0xFF
    print(f"  -> {dl:#04x} -> "
          f"{'matches reg-form 0x10 (formula typo, operand is mem)' if dl == 0x10 else '??'}")


def probe_reti_flags(a, host):
    """[49] RETI flag table scan smudge ('R*' in CY cell): CY restored?"""
    print("\n[49] RETI restores CY from the stack frame:")
    for i, (frame_psw, want_cy) in enumerate([(0xF003, 1), (0xF002, 0)]):
        ram = [(0x0F00, 0x01), (0x0F01, 0x05),       # return PC 0x0501
               (0x0F02, 0x00), (0x0F03, 0x00),       # PS 0
               (0x0F04, frame_psw & 0xFF), (0x0F05, frame_psw >> 8)]
        regs = run(a, host, "    RETI\n    INC AW\n",
                   {"SS": 0, "SP": 0x0F00, "AW": 0}, ram=ram, tag=f"rti{i}")
        cy = regs["PSW"] & PSW_CY
        print(f"  frame PSW={frame_psw:#06x}: PSW out={regs['PSW']:#06x} "
              f"CY={cy} AW={regs['AW']} -> "
              f"{'restored' if cy == want_cy and regs['AW'] == 1 else '??'}")


def probe_ei(a, host):
    """[50] EI operation printed 'EI <- 1' (misprint for IE)."""
    print("\n[50] EI sets PSW.IE (bit 9):")
    regs = run(a, host, "    EI\n", {"PSW": 0}, tag="ei")
    ie = (regs["PSW"] >> 9) & 1
    print(f"  PSW out={regs['PSW']:#06x} IE={ie} -> "
          f"{'IE set (formula misprint confirmed)' if ie == 1 else '??'}")


BATCH2 = (probe_cmpbk_odd_slope, probe_ins_max, probe_inm_iy,
          probe_add_acc_imm, probe_sub_mem_disp, probe_subc_direction,
          probe_mul_mem8_transfers, probe_divu_mem16,
          probe_xor_mem_imm_order, probe_shra_mem, probe_ror_cl_preserved,
          probe_ror_mem_msb, probe_rorc_mem_cl, probe_reti_flags, probe_ei)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all", "batch2"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    a = Assembler()
    fns = BATCH2 if args.cmd == "batch2" else (
        probe_shr_cy, probe_brk_bytes, probe_rorc_v, probe_adj4a,
        probe_div_conditions, probe_mul_flags, probe_bitop_encodings,
        probe_rolc_cl)
    for fn in fns:
        try:
            fn(a, args.host)
        except Exception as e:                        # noqa: BLE001
            print(f"  PROBE FAILED ({fn.__name__}): {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
