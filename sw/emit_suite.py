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


def _mirror_collision(test):
    """True if the case's memory footprint holds two DISTINCT 20-bit addresses
    that alias to the same 16-bit cell. The board captures on a 64K-mirrored
    test RAM, so a colliding golden is only valid there - a flat-1MB consumer
    (any real emulator; task #17 upstream contribution) reads a different byte
    and diverges. Footprint = every memory bus touch in the window (CODE fetch /
    MEMR / MEMW) plus loaded and written ram. Reroll on collision: it is
    seed-deterministic and, unlike capture-length rerolls, does not bias against
    long traces. (testimage.compose's ram-vs-ram + footprint checks are
    necessary but NOT sufficient - they miss ram-vs-instruction, stack, and
    prefetch touches; this trace-based check is complete.)"""
    a = set()
    for row in test["cycles"]:
        if row[7] in ("CODE", "MEMR", "MEMW"):
            a.add(row[1] & 0xFFFFF)
    for x, _ in test["initial"]["ram"]:
        a.add(x & 0xFFFFF)
    for x, _ in test["final"]["ram"]:
        a.add(x & 0xFFFFF)
    return len({x & 0xFFFF for x in a}) < len(a)

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
# serve-v2 capture prefix: normal 0-wait cases finish (incl. store +
# done marker) well under 1024 records; 1536 leaves headroom. Raise for
# wait-state emissions. A too-small value fails loudly ("no done
# marker") and the case retries.
EMIT_CAP = 4096  # was 1536 (32db59a partial-capture); done marker sits past 1536 -> truncated -> spurious 'no done marker'. 4096 = capture-buffer size.
# Golden emission MUST run on the SOCKETED REAL CHIP (use_core=False), not the
# internal v30_core (use_core=True). The internal EU does not implement the 0x63
# undocumented no-op used as the prefetch preamble (PRELOAD_BYTES) -> preloaded
# cases run away. use_core was added AFTER v0.1 emission (2035cce, post-8b5a7d7),
# so v0.1 always used the socket; emission was never pinned. Pin it here.
EMIT_USE_CORE = False


#----------------------------------------------------------------------------
# opcode specs
#----------------------------------------------------------------------------
# modrm: None, "rm8r8", "rm16r16", "r8rm8", "r16rm16", "grp8", "grp16"
# imm: byte count appended after modrm/opcode
def SPEC(key, mnem, base, modrm=None, w=0, imm=0, group=None,
         stack=False, divtrap=False, string4s=False, imm_mask=None,
         branch=None, moffs=None, sreg=None, lea=False, xlat=False,
         string1=None, rep=False, segpfx=None, io_port=False,
         io_dx=False, clcount=False, shiftimm=False, bcdbase=False,
         swint=None, membytes=None, memonly=False, popmem=False,
         chkind=False, prep=False, dispose=False, regonly=False,
         insext=None, popf=False, pushr=False, popr=False):
    return dict(key=key, mnem=mnem, base=base, modrm=modrm, w=w, imm=imm,
                group=group, stack=stack, divtrap=divtrap,
                string4s=string4s, imm_mask=imm_mask, branch=branch,
                moffs=moffs, sreg=sreg, lea=lea, xlat=xlat,
                string1=string1, rep=rep, segpfx=segpfx, io_port=io_port,
                io_dx=io_dx, clcount=clcount, shiftimm=shiftimm,
                bcdbase=bcdbase, swint=swint, membytes=membytes,
                memonly=memonly, popmem=popmem, chkind=chkind, prep=prep,
                dispose=dispose, regonly=regonly, insext=insext,
                popf=popf, pushr=pushr, popr=popr)


ALU = ["add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"]
OPCODES = {}
for i, m in enumerate(ALU):
    OPCODES[f"{i * 8:02X}"] = SPEC(f"{i * 8:02X}", m, [i * 8],
                                   modrm="mr8", w=0)
    # golden-coverage audit (2026-07-13): the word (X1: rm16,r16) and both
    # direction-reversed forms (X2: r8,rm8 / X3: r16,rm16) were implemented
    # in the core by Mission S (op_alu = (opc & C4)==0) but never emitted -
    # the suite only had the rm8,r8 representative. Add all 24 so they enter
    # the permanent regression.
    OPCODES[f"{i * 8 + 1:02X}"] = SPEC(f"{i * 8 + 1:02X}", m, [i * 8 + 1],
                                       modrm="mr16", w=1)
    OPCODES[f"{i * 8 + 2:02X}"] = SPEC(f"{i * 8 + 2:02X}", m, [i * 8 + 2],
                                       modrm="rm8", w=0)
    OPCODES[f"{i * 8 + 3:02X}"] = SPEC(f"{i * 8 + 3:02X}", m, [i * 8 + 3],
                                       modrm="rm16", w=1)
OPCODES["B8"] = SPEC("B8", "mov ax,", [0xB8], imm=2)
# MOV reg8, imm8 (B0-B7): the reg8 half of the "1011 W reg" encoding. Only
# the reg16 half (B8-BF, key B8) was emitted; B0-B7 had NO core dispatch
# and DEADLOCKED (breadth-fuzz find). B0 (mov al) is the representative
# (the core decodes B0-B7 uniformly via opc[7:3]==5'b10110, like B8-BF).
OPCODES["B0"] = SPEC("B0", "mov al,", [0xB0], imm=1)
# MOV r/m, imm (C6 rm8,imm8 / C7 rm16,imm16), group /0. reg AND mem forms
# had NO core dispatch and DEADLOCKED (breadth-fuzz find). Write-only store
# (no operand read) with the imm popped after the modrm/displacement.
OPCODES["C6.0"] = SPEC("C6.0", "mov b,imm8", [0xC6], modrm="grp8",
                       group=0, imm=1)
OPCODES["C7.0"] = SPEC("C7.0", "mov w,imm16", [0xC7], modrm="grp16",
                       group=0, w=1, imm=2)
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
OPCODES["F7.7"] = SPEC("F7.7", "div", [0xF7], modrm="grp16", group=7, w=1,
                       divtrap=True, stack=True)
OPCODES["F6.7"] = SPEC("F6.7", "div", [0xF6], modrm="grp8", group=7,
                       divtrap=True, stack=True)
OPCODES["0F18"] = SPEC("0F18", "test1", [0x0F, 0x18], modrm="grp8",
                       group=0, imm=1, imm_mask=0x07)
OPCODES["0F28"] = SPEC("0F28", "rol4", [0x0F, 0x28], modrm="grp8", group=0)
OPCODES["0F20"] = SPEC("0F20", "add4s", [0x0F, 0x20], string4s=True)
# Mission E control flow: the emitter predicts the continuation from the
# initial state and parks the store stub there.
OPCODES["EB"] = SPEC("EB", "br short", [0xEB], branch="jmp8")
OPCODES["E9"] = SPEC("E9", "br near", [0xE9], branch="jmp16")
OPCODES["74"] = SPEC("74", "be", [0x74], branch="jcc")
OPCODES["75"] = SPEC("75", "bne", [0x75], branch="jcc")
OPCODES["7C"] = SPEC("7C", "blt", [0x7C], branch="jcc")
OPCODES["E2"] = SPEC("E2", "dbnz", [0xE2], branch="loop")
OPCODES["E8"] = SPEC("E8", "call near", [0xE8], branch="call", stack=True)
OPCODES["C3"] = SPEC("C3", "ret", [0xC3], branch="ret", stack=True)
OPCODES["C2"] = SPEC("C2", "ret pop", [0xC2], branch="ret", stack=True)

# Mission J coverage growth
OPCODES["A0"] = SPEC("A0", "mov al,", [0xA0], moffs="r8")
OPCODES["A1"] = SPEC("A1", "mov ax,", [0xA1], moffs="r16")
OPCODES["A2"] = SPEC("A2", "mov moffs,al", [0xA2], moffs="w8")
OPCODES["A3"] = SPEC("A3", "mov moffs,ax", [0xA3], moffs="w16")
OPCODES["8C"] = SPEC("8C", "mov", [0x8C], modrm="mr16", w=1, sreg="st")
OPCODES["8E"] = SPEC("8E", "mov", [0x8E], modrm="rm16", w=1, sreg="ld")
OPCODES["8D"] = SPEC("8D", "lea", [0x8D], modrm="rm16", w=1, lea=True)
OPCODES["D7"] = SPEC("D7", "xlat", [0xD7], xlat=True)
OPCODES["98"] = SPEC("98", "cbw", [0x98])
OPCODES["99"] = SPEC("99", "cwd", [0x99])
OPCODES["A4"] = SPEC("A4", "movsb", [0xA4], string1="movs", w=0)
OPCODES["A5"] = SPEC("A5", "movsw", [0xA5], string1="movs", w=1)
OPCODES["AA"] = SPEC("AA", "stosb", [0xAA], string1="stos", w=0)
OPCODES["AB"] = SPEC("AB", "stosw", [0xAB], string1="stos", w=1)
OPCODES["AC"] = SPEC("AC", "lodsb", [0xAC], string1="lods", w=0)
OPCODES["AD"] = SPEC("AD", "lodsw", [0xAD], string1="lods", w=1)
# CMPBK (A6/A7) and CMPM (AE/AF) singles + all four repeat prefixes
# (F3 REPE / F2 REPNE / 65 REPC / 64 REPNC - V-series adds the carry
# variants, CMPBK/CMPM only)
for _b, _nm, _st, _w in ((0xA6, "cmpsb", "cmps", 0), (0xA7, "cmpsw", "cmps", 1),
                         (0xAE, "scasb", "scas", 0), (0xAF, "scasw", "scas", 1)):
    OPCODES[f"{_b:02X}"] = SPEC(f"{_b:02X}", _nm, [_b], string1=_st, w=_w)
    for _p, _pn in ((0xF3, "repe"), (0xF2, "repne"),
                    (0x65, "repc"), (0x64, "repnc")):
        _k = f"{_p:02X}{_b:02X}"
        OPCODES[_k] = SPEC(_k, f"{_pn} {_nm}", [_p, _b], string1=_st,
                           w=_w, rep=True)
# remaining REP variants of the non-compare strings (word forms + LODS)
OPCODES["F3A5"] = SPEC("F3A5", "rep movsw", [0xF3, 0xA5],
                       string1="movs", w=1, rep=True)
OPCODES["F3AB"] = SPEC("F3AB", "rep stosw", [0xF3, 0xAB],
                       string1="stos", w=1, rep=True)
OPCODES["F3AC"] = SPEC("F3AC", "rep lodsb", [0xF3, 0xAC],
                       string1="lods", w=0, rep=True)
OPCODES["F3AD"] = SPEC("F3AD", "rep lodsw", [0xF3, 0xAD],
                       string1="lods", w=1, rep=True)
OPCODES["F2AA"] = SPEC("F2AA", "repne stosb", [0xF2, 0xAA],
                       string1="stos", w=0, rep=True)
OPCODES["F3AA"] = SPEC("F3AA", "rep stosb", [0xF3, 0xAA],
                       string1="stos", w=0, rep=True)
OPCODES["F3A4"] = SPEC("F3A4", "rep movsb", [0xF3, 0xA4],
                       string1="movs", w=0, rep=True)
OPCODES["26.8B"] = SPEC("26.8B", "mov", [0x26, 0x8B], modrm="rm16", w=1,
                        segpfx="es")
OPCODES["2E.8B"] = SPEC("2E.8B", "mov", [0x2E, 0x8B], modrm="rm16", w=1,
                        segpfx="cs")
OPCODES["36.8B"] = SPEC("36.8B", "mov", [0x36, 0x8B], modrm="rm16", w=1,
                        segpfx="ss")
OPCODES["3E.8B"] = SPEC("3E.8B", "mov", [0x3E, 0x8B], modrm="rm16", w=1,
                        segpfx="ds")

# 0F bit ops: TEST1/CLR1/SET1/NOT1 x (rm8/rm16) x (CL/imm) (0F 10-1F;
# 0F18 already present with its fitted spec)
for _i, _bm in enumerate(("test1", "clr1", "set1", "not1")):
    for _w in (0, 1):
        _cl = 0x10 + 2 * _i + _w
        _im = 0x18 + 2 * _i + _w
        k1 = f"0F{_cl:02X}"
        OPCODES[k1] = SPEC(k1, f"{_bm} cl", [0x0F, _cl],
                           modrm="grp16" if _w else "grp8", group=0,
                           w=_w, clcount=True)
        k2 = f"0F{_im:02X}"
        if k2 not in OPCODES:
            OPCODES[k2] = SPEC(k2, f"{_bm} imm", [0x0F, _im],
                               modrm="grp16" if _w else "grp8", group=0,
                               w=_w, imm=1, imm_mask=0x0F if _w else 0x07)
# full Jcc set (70-7F; 74/75/7C keep their original entries)
JCC_NAMES = ["bv", "bnv", "bc", "bnc", "be", "bne", "bnh", "bh",
             "bn", "bp", "bpe", "bpo", "blt", "bge", "ble", "bgt"]
for _cc in range(16):
    _k = f"{0x70 + _cc:02X}"
    if _k not in OPCODES:
        OPCODES[_k] = SPEC(_k, JCC_NAMES[_cc], [0x70 + _cc], branch="jcc")
# LOOPE/LOOPNE/JCXZ (DBNZE/DBNZNE/BCWZ)
OPCODES["E1"] = SPEC("E1", "dbnze", [0xE1], branch="loopz")
OPCODES["E0"] = SPEC("E0", "dbnzne", [0xE0], branch="loopnz")
OPCODES["E3"] = SPEC("E3", "bcwz", [0xE3], branch="jcxz")
# ALU acc,imm (04..3C / 05..3D)
for _i, _m in enumerate(ALU):
    _b8, _b16 = _i * 8 + 4, _i * 8 + 5
    OPCODES[f"{_b8:02X}"] = SPEC(f"{_b8:02X}", f"{_m} al,imm8", [_b8],
                                 imm=1)
    OPCODES[f"{_b16:02X}"] = SPEC(f"{_b16:02X}", f"{_m} aw,imm16",
                                  [_b16], imm=2)
# TEST family
OPCODES["84"] = SPEC("84", "test", [0x84], modrm="mr8", w=0)
OPCODES["85"] = SPEC("85", "test", [0x85], modrm="mr16", w=1)
OPCODES["A8"] = SPEC("A8", "test al,imm8", [0xA8], imm=1)
OPCODES["A9"] = SPEC("A9", "test aw,imm16", [0xA9], imm=2)
# F6/F7 remaining groups: TEST imm / NOT / NEG / MULU16 / MUL(signed)
OPCODES["F6.0"] = SPEC("F6.0", "test b,imm8", [0xF6], modrm="grp8",
                       group=0, imm=1)
OPCODES["F7.0"] = SPEC("F7.0", "test w,imm16", [0xF7], modrm="grp16",
                       group=0, w=1, imm=2)
for _g, _m in ((2, "not"), (3, "neg"), (5, "mul")):
    OPCODES[f"F6.{_g}"] = SPEC(f"F6.{_g}", f"{_m} b", [0xF6],
                               modrm="grp8", group=_g)
    OPCODES[f"F7.{_g}"] = SPEC(f"F7.{_g}", f"{_m} w", [0xF7],
                               modrm="grp16", group=_g, w=1)
OPCODES["F7.4"] = SPEC("F7.4", "mulu w", [0xF7], modrm="grp16", group=4,
                       w=1)
OPCODES["F6.6"] = SPEC("F6.6", "divu b", [0xF6], modrm="grp8", group=6,
                       divtrap=True, stack=True)
# IMUL reg,rm,imm
OPCODES["69"] = SPEC("69", "mul r,rm,imm16", [0x69], modrm="rm16", w=1,
                     imm=2)
OPCODES["6B"] = SPEC("6B", "mul r,rm,simm8", [0x6B], modrm="rm16", w=1,
                     imm=1)
# XCHG AW,reg + NOP
OPCODES["90"] = SPEC("90", "nop", [0x90])
for _r in range(1, 8):
    _k = f"{0x90 + _r:02X}"
    OPCODES[_k] = SPEC(_k, f"xch aw,{REG16[_r]}", [0x90 + _r])
# PUSH/POP sreg, PUSHF/POPF, LAHF/SAHF, PUSH imm, PUSH R/POP R
for _s, _nm in ((0, "ds1"), (2, "ss"), (3, "ds0")):
    OPCODES[f"{6 + _s * 8:02X}"] = SPEC(f"{6 + _s * 8:02X}",
                                        f"push {_nm}", [6 + _s * 8],
                                        stack=True)
    OPCODES[f"{7 + _s * 8:02X}"] = SPEC(f"{7 + _s * 8:02X}",
                                        f"pop {_nm}", [7 + _s * 8],
                                        stack=True, popmem=True)
OPCODES["0E"] = SPEC("0E", "push ps", [0x0E], stack=True)
OPCODES["9C"] = SPEC("9C", "push psw", [0x9C], stack=True)
OPCODES["9D"] = SPEC("9D", "pop psw", [0x9D], stack=True, popf=True)
OPCODES["9E"] = SPEC("9E", "mov psw,ah", [0x9E])
OPCODES["9F"] = SPEC("9F", "mov ah,psw", [0x9F])
OPCODES["68"] = SPEC("68", "push imm16", [0x68], imm=2, stack=True)
OPCODES["6A"] = SPEC("6A", "push simm8", [0x6A], imm=1, stack=True)
OPCODES["60"] = SPEC("60", "push r", [0x60], pushr=True)
OPCODES["61"] = SPEC("61", "pop r", [0x61], popr=True)
# CY/direction/IE flag ops
for _b, _nm in ((0xF5, "not1 cy"), (0xF8, "clr1 cy"), (0xF9, "set1 cy"),
                (0xFC, "clr1 dir"), (0xFD, "set1 dir"),
                (0xFA, "di"), (0xFB, "ei")):
    OPCODES[f"{_b:02X}"] = SPEC(f"{_b:02X}", _nm, [_b])
# FPO2 (66/67)
OPCODES["66"] = SPEC("66", "fpo2.0", [0x66], modrm="rm16", w=1)
OPCODES["67"] = SPEC("67", "fpo2.1", [0x67], modrm="rm16", w=1)
# INS/EXT bit-field forms (register + imm4 length)
OPCODES["0F31"] = SPEC("0F31", "ins", [0x0F, 0x31], modrm="rm8",
                       regonly=True, insext="ins")
OPCODES["0F33"] = SPEC("0F33", "ext", [0x0F, 0x33], modrm="rm8",
                       regonly=True, insext="ext")
OPCODES["0F39"] = SPEC("0F39", "ins imm4", [0x0F, 0x39], modrm="grp8",
                       group=0, regonly=True, imm=1, imm_mask=0x0F,
                       insext="ins")
OPCODES["0F3B"] = SPEC("0F3B", "ext imm4", [0x0F, 0x3B], modrm="grp8",
                       group=0, regonly=True, imm=1, imm_mask=0x0F,
                       insext="ext")
# 0F BCD strings + ROR4
OPCODES["0F22"] = SPEC("0F22", "sub4s", [0x0F, 0x22], string4s=True)
OPCODES["0F26"] = SPEC("0F26", "cmp4s", [0x0F, 0x26], string4s=True)
OPCODES["0F2A"] = SPEC("0F2A", "ror4", [0x0F, 0x2A], modrm="grp8",
                       group=0)
# FPO1 (ESC): bus shape only; mem forms place a word operand
for _b in range(0xD8, 0xE0):
    OPCODES[f"{_b:02X}"] = SPEC(f"{_b:02X}", f"fpo1.{_b & 7}", [_b],
                                modrm="rm16", w=1)
# segment-prefix x string/stack memory ops (src-side override)
OPCODES["26.A4"] = SPEC("26.A4", "es: movsb", [0x26, 0xA4],
                        string1="movs", w=0, segpfx="es")
OPCODES["2E.A5"] = SPEC("2E.A5", "cs: movsw", [0x2E, 0xA5],
                        string1="movs", w=1, segpfx="cs")
OPCODES["36.A6"] = SPEC("36.A6", "ss: cmpsb", [0x36, 0xA6],
                        string1="cmps", w=0, segpfx="ss")
OPCODES["3E.AC"] = SPEC("3E.AC", "ds: lodsb", [0x3E, 0xAC],
                        string1="lods", w=0, segpfx="ds")
# ALU r/m,imm groups: 80 (rm8,imm8), 81 (rm16,imm16), 83 (rm16,simm8)
for _g, _m in enumerate(ALU):
    OPCODES[f"80.{_g}"] = SPEC(f"80.{_g}", f"{_m} b,imm8", [0x80],
                               modrm="grp8", group=_g, imm=1)
    OPCODES[f"81.{_g}"] = SPEC(f"81.{_g}", f"{_m} w,imm16", [0x81],
                               modrm="grp16", group=_g, w=1, imm=2)
    OPCODES[f"83.{_g}"] = SPEC(f"83.{_g}", f"{_m} w,simm8", [0x83],
                               modrm="grp16", group=_g, w=1, imm=1)
# shift/rotate groups (all 8 sub-ops incl. the undocumented alias 6):
# D0/D1 by 1, D2/D3 by CL, C0/C1 by imm8
SHOPS = ["rol", "ror", "rcl", "rcr", "shl", "shr", "shl6", "sar"]
for _g, _m in enumerate(SHOPS):
    if f"D0.{_g}" not in OPCODES:
        OPCODES[f"D0.{_g}"] = SPEC(f"D0.{_g}", f"{_m} b,1", [0xD0],
                                   modrm="grp8", group=_g)
    OPCODES[f"D1.{_g}"] = SPEC(f"D1.{_g}", f"{_m} w,1", [0xD1],
                               modrm="grp16", group=_g, w=1)
    OPCODES[f"D2.{_g}"] = SPEC(f"D2.{_g}", f"{_m} b,cl", [0xD2],
                               modrm="grp8", group=_g, clcount=True)
    OPCODES[f"D3.{_g}"] = SPEC(f"D3.{_g}", f"{_m} w,cl", [0xD3],
                               modrm="grp16", group=_g, w=1, clcount=True)
    OPCODES[f"C0.{_g}"] = SPEC(f"C0.{_g}", f"{_m} b,imm8", [0xC0],
                               modrm="grp8", group=_g, imm=1,
                               shiftimm=True)
    OPCODES[f"C1.{_g}"] = SPEC(f"C1.{_g}", f"{_m} w,imm8", [0xC1],
                               modrm="grp16", group=_g, w=1, imm=1,
                               shiftimm=True)
# BCD adjusts: ADJ4A/ADJ4S/ADJBA/ADJBS + CVTBD/CVTDB (imm base; biased
# to 0x0A, base 0 excluded on the first pass - div0 trap path is the
# divtrap family's)
OPCODES["27"] = SPEC("27", "adj4a", [0x27])
OPCODES["2F"] = SPEC("2F", "adj4s", [0x2F])
OPCODES["37"] = SPEC("37", "adjba", [0x37])
OPCODES["3F"] = SPEC("3F", "adjbs", [0x3F])
OPCODES["D4"] = SPEC("D4", "cvtbd", [0xD4], imm=1, bcdbase=True)
OPCODES["D5"] = SPEC("D5", "cvtdb", [0xD5], imm=1, bcdbase=True)
# LDS/LES (4-byte pointer loads, mem-only), POP mem, FE/FF remainder
OPCODES["C4"] = SPEC("C4", "mov ds1+reg", [0xC4], modrm="rm16", w=1,
                     membytes=4, memonly=True)
OPCODES["C5"] = SPEC("C5", "mov ds0+reg", [0xC5], modrm="rm16", w=1,
                     membytes=4, memonly=True)
# 8F /0 = POP r/m16. The mem forms (mod 0/1/2) pop to memory; mod3
# (0xC0-0xC7) is the undocumented register-destination alias which writes
# NO register (only SP += 2) and issues one stack read whose word is
# discarded. That read's committed ADDRESS and data are stale internal
# EA/address-latch state (pre-window injection-stub history) - recorded
# faithfully here but flagged a golden-schema don't-care for the replay
# comparison; see metadata.json 8F.0 dont_care + check_core.dontcare_cells.
OPCODES["8F.0"] = SPEC("8F.0", "pop mem", [0x8F], modrm="grp16", group=0,
                       w=1, stack=True, popmem=True)
OPCODES["FE.1"] = SPEC("FE.1", "dec b", [0xFE], modrm="grp8", group=1)
OPCODES["FF.0"] = SPEC("FF.0", "inc w", [0xFF], modrm="grp16", group=0,
                       w=1)
OPCODES["FF.1"] = SPEC("FF.1", "dec w", [0xFF], modrm="grp16", group=1,
                       w=1)
OPCODES["FF.2"] = SPEC("FF.2", "call rm", [0xFF], modrm="grp16", group=2,
                       w=1, stack=True)
OPCODES["FF.3"] = SPEC("FF.3", "call far mem", [0xFF], modrm="grp16",
                       group=3, w=1, membytes=4, memonly=True, stack=True)
OPCODES["FF.4"] = SPEC("FF.4", "br rm", [0xFF], modrm="grp16", group=4,
                       w=1)
OPCODES["FF.5"] = SPEC("FF.5", "br far mem", [0xFF], modrm="grp16",
                       group=5, w=1, membytes=4, memonly=True)
OPCODES["FF.6"] = SPEC("FF.6", "push mem", [0xFF], modrm="grp16", group=6,
                       w=1, stack=True)
# far transfers + software interrupts
OPCODES["CB"] = SPEC("CB", "retf", [0xCB], branch="retf", stack=True)
OPCODES["CA"] = SPEC("CA", "retf pop", [0xCA], branch="retfp", stack=True)
OPCODES["9A"] = SPEC("9A", "call far", [0x9A], branch="callf", stack=True)
OPCODES["EA"] = SPEC("EA", "br far", [0xEA], branch="jmpf")
OPCODES["CF"] = SPEC("CF", "reti", [0xCF], branch="iret", stack=True)
OPCODES["CD"] = SPEC("CD", "brk imm8", [0xCD], imm=1, swint="cd",
                     stack=True)
OPCODES["CC"] = SPEC("CC", "brk3", [0xCC], swint="brk3", stack=True)
OPCODES["CE"] = SPEC("CE", "brkv", [0xCE], swint="brkv", stack=True)
OPCODES["C8"] = SPEC("C8", "prepare", [0xC8], prep=True)
OPCODES["C9"] = SPEC("C9", "dispose", [0xC9], dispose=True)
OPCODES["62"] = SPEC("62", "chkind", [0x62], modrm="rm16", w=1,
                     membytes=4, memonly=True, chkind=True, stack=True)
OPCODES["E4"] = SPEC("E4", "in al,", [0xE4], imm=1)
OPCODES["E5"] = SPEC("E5", "in ax,", [0xE5], imm=1)
# OUT: the port must stay clear of the harness store-routine ports
# (IOW 0xFE = register dump, 0xFC = done marker; a word OUT to 0xFB/0xFD
# splits onto them) - io_port/io_dx keep test ports out of 0x00F8-0x00FF
OPCODES["E6"] = SPEC("E6", "out imm8,al", [0xE6], imm=1, io_port=True)
OPCODES["E7"] = SPEC("E7", "out imm8,ax", [0xE7], imm=1, w=1, io_port=True)
OPCODES["EE"] = SPEC("EE", "out dx,al", [0xEE], io_dx=True)
OPCODES["EF"] = SPEC("EF", "out dx,ax", [0xEF], w=1, io_dx=True)
OPCODES["EC"] = SPEC("EC", "in al, dx", [0xEC])
OPCODES["ED"] = SPEC("ED", "in ax, dx", [0xED])
IO_IN_OPS = {"E4", "E5", "EC", "ED"}

BRANCH_OPS = ["EB", "E9", "74", "75", "7C", "E2", "E8", "C3", "C2"]

#----------------------------------------------------------------------------
# pin-event (interrupt/NMI/POLL/HALT) forms - Campaign 3 block 4
#----------------------------------------------------------------------------
# JSON extensions per test:
#   "evt":  {"pin": 0|1|2, "hold": H, "trigger": "fetch"|"fpop",
#            "addr": linear (fetch mode), "delay": D}
#     fetch: pin asserted during cycle idx(CODE T1 at addr) + 2 + D
#            (the harness scheduler law; cold variants)
#     fpop:  pin asserted during cycle idx(window-opening F pop) + D,
#            D >= 0 (prefetched variants: the preload instructions do
#            not exist in TB replay, so no fetch anchor is available)
#   "pins": static pin levels before the event {"poll_n": 1}
#   "iord": 16-bit data the system returns for I/O reads (IN forms)
# Vectored forms point the IVT entry directly at the store stub; the
# row window closes at the first F pop FROM that address (the handler
# entry) instead of a fixed pop count.
def EVT(key, mnem, pin, hold, dmin, dmax, ie=None, vec=0xFF,
        close="handler", pins=0, builder=None):
    return dict(key=key, mnem=mnem, pin=pin, hold=hold, dmin=dmin,
                dmax=dmax, ie=ie, vec=vec, close=close, pins=pins,
                builder=builder, evtform=True)


def _b_nop(rng, regs):
    return bytes([0x90]), [], "nop"


def _b_b8(rng, regs):
    v = rng.getrandbits(16)
    return bytes([0xB8]) + v.to_bytes(2, "little"), [], f"mov ax, {v:04x}h"


def _b_movss(rng, regs):
    return bytes([0x8E, 0xD0]), [], "mov ss, ax"


def _b_movds(rng, regs):
    return bytes([0x8E, 0xD8]), [], "mov ds, ax"


def _b_ei(rng, regs):
    return bytes([0xFB]), [], "ei"


def _b_poppsw(rng, regs):
    # popped image: normalized, IE forced 1 (never TF/MD games)
    v = (rng.getrandbits(16) & 0x0ED5) | 0xF202
    lin = ((regs["ss"] << 4) + regs["sp"]) & 0xFFFFF
    ram = [(lin, v & 0xFF), ((lin + 1) & 0xFFFFF, v >> 8)]
    return bytes([0x9D]), ram, f"pop psw ({v:04x})"


def _b_repstm(rng, regs):
    regs["cx"] = rng.randrange(1, 5)
    return bytes([0xF3, 0xAA]), [], f"rep stosb (cx={regs['cx']})"


def _b_halt(rng, regs):
    return bytes([0xF4]), [], "halt"


def _b_poll(rng, regs):
    return bytes([0x9B]), [], "poll"


EVT_FORMS = {
    "INT.90":   EVT("INT.90", "int", 0, 0, 1, 7, ie=1, builder=_b_nop),
    "INT.B8":   EVT("INT.B8", "int", 0, 0, 1, 8, ie=1, builder=_b_b8),
    "INT.8ED0": EVT("INT.8ED0", "int", 0, 0, 1, 8, ie=1,
                    builder=_b_movss),
    "INT.8ED8": EVT("INT.8ED8", "int", 0, 0, 1, 8, ie=1,
                    builder=_b_movds),
    "INT.FB":   EVT("INT.FB", "int", 0, 0, 1, 6, ie=0, builder=_b_ei),
    "INT.9D":   EVT("INT.9D", "int", 0, 0, 1, 10, ie=None,
                    builder=_b_poppsw),
    "INT.F3AA": EVT("INT.F3AA", "int", 0, 0, 1, 28, ie=1,
                    builder=_b_repstm),
    "NMI.90":   EVT("NMI.90", "nmi", 1, 2, 1, 7, ie=None, vec=2,
                    builder=_b_nop),
    "NMI.B8":   EVT("NMI.B8", "nmi", 1, 2, 1, 8, ie=None, vec=2,
                    builder=_b_b8),
    "HLT.INT":  EVT("HLT.INT", "halt/int", 0, 0, 14, 40, ie=1,
                    builder=_b_halt),
    "HLT.NMI":  EVT("HLT.NMI", "halt/nmi", 1, 2, 14, 40, ie=None, vec=2,
                    builder=_b_halt),
    "HLT.RES":  EVT("HLT.RES", "halt/resume", 0, 0, 14, 40, ie=0,
                    close="next", builder=_b_halt),
    "IE0.90":   EVT("IE0.90", "masked int", 0, 0, 1, 7, ie=0,
                    close="next", builder=_b_nop),
    "POLL.LO":  EVT("POLL.LO", "poll (low)", None, 0, 0, 0, ie=None,
                    close="next", builder=_b_poll),
    "POLL.REL": EVT("POLL.REL", "poll release", 2, 6, 4, 30, ie=None,
                    close="next", pins=4, builder=_b_poll),
}

SREG_STR = ["es", "cs", "ss", "ds"]


def n_prefix(spec):
    """Prefix bytes ahead of the opcode (each pops as an extra F)."""
    n = 1 if spec["rep"] or spec["segpfx"] else 0
    return n

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
            mod = 3 if spec["regonly"] else \
                rng.randrange(3) if (spec["lea"] or spec["memonly"]) \
                else rng.randrange(4)
            rm = rng.randrange(8)
            if spec["sreg"] == "st":
                reg = rng.randrange(4)
            elif spec["sreg"] == "ld":
                reg = rng.choice([0, 2, 3])      # never load CS
            else:
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
            rn = SREG_STR[reg] if spec["sreg"] else \
                (REG16 if wide else REG8)[reg]
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
            if spec["io_port"]:
                while imm_v >= 0xF8:        # harness store ports
                    imm_v = rng.getrandbits(8)
            if spec["shiftimm"] and rng.random() < 0.5:
                imm_v &= 0x0F               # bias toward short counts
            if spec["bcdbase"]:
                imm_v = 0x0A if rng.random() < 0.5 else \
                    rng.randrange(1, 256)   # base 0 = div0 trap, excluded
            instr += imm_v.to_bytes(spec["imm"], "little")
            name += f" {imm_v:0{2 * spec['imm']}x}h"
        if spec["io_dx"] and 0x00F8 <= regs["dx"] <= 0x00FF:
            continue                        # harness store ports
        if spec["clcount"]:
            if rng.random() < 0.5:
                regs["cx"] = (regs["cx"] & 0xFF00) | rng.randrange(0, 9)
            name += f" (cl={regs['cx'] & 0xFF:02x}h)"
        if spec["string4s"]:
            regs["cx"] = (regs["cx"] & 0xFF00) | rng.randrange(1, 7)
            name = f"{spec['mnem']} (cl={regs['cx'] & 0xFF})"

        anchor = ((regs["cs"] << 4) + regs["ip"]) & 0xFFFFF
        a_phys = anchor & 0xFFFF

        def lin(seg, off):
            return ((regs[seg] << 4) + (off & 0xFFFF)) & 0xFFFFF

        # control flow: append displacement bytes, evaluate the branch
        # from the initial state, predict the continuation offset
        next_ip = None
        next_cs = None
        if spec["branch"] in ("retf", "retfp", "iret"):
            toff, tseg = rng.getrandbits(16), rng.getrandbits(16)
            words = [toff, tseg]
            if spec["branch"] == "iret":
                # popped PSW: normalized, BRK=0 (single-step path is
                # out of scope for this tranche)
                words.append((rng.getrandbits(16) & 0x0ED5) | 0xF002)
            if spec["branch"] == "retfp":
                instr += rng.getrandbits(16).to_bytes(2, "little")
            for k, wv in enumerate(words):
                ram.append((lin("ss", regs["sp"] + 2 * k), wv & 0xFF))
                ram.append((lin("ss", regs["sp"] + 2 * k + 1), wv >> 8))
            next_ip, next_cs = toff, tseg
            name += f" -> {tseg:04x}h:{toff:04x}h"
            if spec["branch"] == "retfp":
                name += f" +{int.from_bytes(instr[1:3], 'little'):04x}h"
        elif spec["branch"] in ("callf", "jmpf"):
            toff, tseg = rng.getrandbits(16), rng.getrandbits(16)
            instr += toff.to_bytes(2, "little") + tseg.to_bytes(2, "little")
            next_ip, next_cs = toff, tseg
            name += f" {tseg:04x}h:{toff:04x}h"
        elif spec["branch"]:
            br = spec["branch"]
            taken = True
            sd = 0
            if br in ("jmp8", "jcc", "loop", "loopz", "loopnz", "jcxz"):
                d8 = rng.getrandbits(8)
                instr += bytes([d8])
                sd = d8 - 0x100 if d8 & 0x80 else d8
            elif br in ("jmp16", "call"):
                d16 = rng.getrandbits(16)
                instr += d16.to_bytes(2, "little")
                sd = d16
            elif spec["key"] == "C2":
                instr += rng.getrandbits(16).to_bytes(2, "little")
            fall = (regs["ip"] + len(instr)) & 0xFFFF
            if br == "jcc":
                f = regs["flags"]
                cf, pf = f & 1, (f >> 2) & 1
                zf, sf, of = (f >> 6) & 1, (f >> 7) & 1, (f >> 11) & 1
                cc = spec["base"][0] & 0x0F
                base_t = [of == 1, of == 0, cf == 1, cf == 0,
                          zf == 1, zf == 0, cf | zf == 1, cf | zf == 0,
                          sf == 1, sf == 0, pf == 1, pf == 0,
                          (sf ^ of) == 1, (sf ^ of) == 0,
                          ((sf ^ of) | zf) == 1,
                          ((sf ^ of) | zf) == 0][cc]
                taken = bool(base_t)
            elif br == "jcxz":
                if rng.random() < 0.4:
                    regs["cx"] = 0
                taken = (regs["cx"] & 0xFFFF) == 0
            elif br in ("loopz", "loopnz"):
                if rng.random() < 0.3:
                    regs["cx"] = 1                     # cx side not taken
                elif (regs["cx"] & 0xFFFF) < 2:
                    regs["cx"] = rng.randrange(2, 0x10000)
                zf = (regs["flags"] >> 6) & 1
                taken = ((regs["cx"] - 1) & 0xFFFF) != 0 and \
                    (zf == 1 if br == "loopz" else zf == 0)
            elif br == "loop":
                if rng.random() < 0.3:
                    regs["cx"] = 1                     # not taken
                elif (regs["cx"] & 0xFFFF) < 2:
                    regs["cx"] = rng.randrange(2, 0x10000)
                taken = ((regs["cx"] - 1) & 0xFFFF) != 0
            if br == "ret":
                next_ip = rng.getrandbits(16)
                ram.append((lin("ss", regs["sp"]), next_ip & 0xFF))
                ram.append((lin("ss", regs["sp"] + 1), next_ip >> 8))
            else:
                next_ip = (fall + sd) & 0xFFFF if taken else fall
            if br in ("jmp8", "jmp16", "call"):
                name += f" {next_ip:04x}h"
            elif br in ("jcc", "loop", "loopz", "loopnz", "jcxz"):
                name += f" {(fall + sd) & 0xFFFF:04x}h" + \
                        ("" if taken else " (not taken)")
            elif spec["key"] == "C2":
                name += f" {int.from_bytes(instr[1:3], 'little'):04x}h"

        if next_cs is not None:
            # far transfer: stub at the target cs:ip
            tgt16 = ((next_cs << 4) + next_ip) & 0xFFFF
            spans = [range(a_phys, a_phys + len(instr) + 8),
                     range(tgt16, tgt16 + 24)]
            if spec["branch"] == "iret":
                # spec["stack"] reserves sp-8..sp+3; the popped PSW
                # word at sp+4 needs its own reservation
                lo = lin("ss", regs["sp"] + 4) & 0xFFFF
                spans.append(range(lo, lo + 2))
        elif next_ip is not None and \
                next_ip != (regs["ip"] + len(instr)) & 0xFFFF:
            # instr + fall-through prefetch overrun; stub at the target
            spans = [range(a_phys, a_phys + len(instr) + 8),
                     range(lin("cs", next_ip) & 0xFFFF,
                           (lin("cs", next_ip) & 0xFFFF) + 24)]
        else:
            spans = [range(a_phys, a_phys + len(instr) + 24)]  # instr+stub

        # memory operand placement (LEA computes but never accesses)
        opbytes = []
        if spec["modrm"] and (instr[len(spec["base"])] >> 6) != 3 \
                and not spec["lea"]:
            mb = instr[len(spec["base"])]
            mod, rm = mb >> 6, mb & 7
            nd = {0: 2 if rm == 6 else 0, 1: 1, 2: 2, 3: 0}[mod]
            d = int.from_bytes(
                instr[len(spec["base"]) + 1:len(spec["base"]) + 1 + nd],
                "little")
            ea, seg = ea_of(rm, mod, d, regs)
            if spec["segpfx"]:
                seg = spec["segpfx"]           # override absorbs default
            nbytes = spec["membytes"] or (2 if spec["w"] else 1)
            for k in range(nbytes):
                opbytes.append(rng.getrandbits(8))
                ram.append((lin(seg, ea + k), opbytes[-1]))
            spans.append(range(lin(seg, ea) & 0xFFFF,
                               (lin(seg, ea) & 0xFFFF) + nbytes))
            # FF-group indirect transfers: target from the operand
            if spec["key"] in ("FF.2", "FF.4"):
                next_ip = opbytes[0] | (opbytes[1] << 8)
            elif spec["key"] in ("FF.3", "FF.5"):
                next_ip = opbytes[0] | (opbytes[1] << 8)
                next_cs = opbytes[2] | (opbytes[3] << 8)
        elif spec["key"] in ("FF.2", "FF.4"):      # reg-indirect target
            next_ip = regs[REG16[instr[len(spec["base"])] & 7]]
        if spec["key"] in ("FF.2", "FF.3", "FF.4", "FF.5"):
            # rebuild the spans: fall-through stub replaced by the
            # transfer target's stub
            tcs = next_cs if next_cs is not None else regs["cs"]
            tgt16 = ((tcs << 4) + next_ip) & 0xFFFF
            spans[0] = range(a_phys, a_phys + len(instr) + 8)
            spans.append(range(tgt16, tgt16 + 24))
            name += f" -> {tcs:04x}h:{next_ip:04x}h"
        # direct-address (moffs) forms A0-A3
        if spec["moffs"]:
            a16 = rng.getrandbits(16)
            instr += a16.to_bytes(2, "little")
            nb = 2 if spec["moffs"] in ("r16", "w16") else 1
            if spec["moffs"][0] == "r":
                for k in range(nb):
                    ram.append((lin("ds", a16 + k), rng.getrandbits(8)))
                name += f" [{a16:04x}h]"
            else:
                name = f"{spec['mnem']} [{a16:04x}h]"
            spans.append(range(lin("ds", a16) & 0xFFFF,
                               (lin("ds", a16) & 0xFFFF) + nb))
        # XLAT reads ds:[bx+al]
        if spec["xlat"]:
            xea = (regs["bx"] + (regs["ax"] & 0xFF)) & 0xFFFF
            ram.append((lin("ds", xea), rng.getrandbits(8)))
            spans.append(range(lin("ds", xea) & 0xFFFF,
                               (lin("ds", xea) & 0xFFFF) + 1))
        # single/REP string ops (MOVBK/STM/LDM); DF from the random flags
        if spec["string1"]:
            nb = 2 if spec["w"] else 1
            if spec["rep"]:
                regs["cx"] = rng.randrange(0, 4)
            cnt = (regs["cx"] & 0xFFFF) if spec["rep"] else 1
            df = (regs["flags"] >> 10) & 1
            st = spec["string1"]
            sseg = spec["segpfx"] or "ds"     # override hits the src side
            for i in range(cnt):
                step = -i * nb if df else i * nb
                sbytes = []
                if st in ("movs", "lods", "cmps"):
                    so = (regs["si"] + step) & 0xFFFF
                    for k in range(nb):
                        sbytes.append(rng.getrandbits(8))
                        ram.append((lin(sseg, so + k), sbytes[-1]))
                    spans.append(range(lin(sseg, so) & 0xFFFF,
                                       (lin(sseg, so) & 0xFFFF) + nb))
                if st in ("cmps", "scas"):
                    # read side at es:di; bias toward equality so REPE/
                    # REPNE/REPC/REPNC terminations vary
                    do = (regs["di"] + step) & 0xFFFF
                    eq = rng.random() < (0.6 if spec["rep"] else 0.35)
                    for k in range(nb):
                        if eq:
                            v = sbytes[k] if st == "cmps" else \
                                (regs["ax"] >> (8 * k)) & 0xFF
                        else:
                            v = rng.getrandbits(8)
                        ram.append((lin("es", do + k), v))
                    spans.append(range(lin("es", do) & 0xFFFF,
                                       (lin("es", do) & 0xFFFF) + nb))
                if st in ("movs", "stos"):
                    do = (regs["di"] + step) & 0xFFFF
                    spans.append(range(lin("es", do) & 0xFFFF,
                                       (lin("es", do) & 0xFFFF) + nb))
            name += f" (df={df}" + \
                    (f", cx={cnt})" if spec["rep"] else ")")
        if spec["string4s"]:
            n = ((regs["cx"] & 0xFF) + 1) // 2
            for k in range(n):
                ram.append((lin("ds", regs["si"] + k), rng.getrandbits(8)))
                ram.append((lin("es", regs["di"] + k), rng.getrandbits(8)))
            spans.append(range(lin("ds", regs["si"]) & 0xFFFF,
                               (lin("ds", regs["si"]) & 0xFFFF) + n))
            spans.append(range(lin("es", regs["di"]) & 0xFFFF,
                               (lin("es", regs["di"]) & 0xFFFF) + n))
        if spec["insext"]:
            # INS: bit field to DS1:IY; EXT: bit field from DS0:IX.
            # Offset (rm-field reg8) and register-form length (reg-field
            # reg8) constrained to 0-15 for this tranche (silicon uses
            # the low 4 bits; wider values deferred)
            mb = instr[2]

            def s8(i, v):
                r16 = REG16[i & 3]
                if i & 4:
                    regs[r16] = (regs[r16] & 0x00FF) | (v << 8)
                else:
                    regs[r16] = (regs[r16] & 0xFF00) | v
            s8(mb & 7, rng.randrange(16))
            if spec["imm"] == 0:
                s8((mb >> 3) & 7, rng.randrange(16))
            iseg, ibase = ("es", "di") if spec["insext"] == "ins" \
                else ("ds", "si")
            for k in range(6):
                ram.append((lin(iseg, regs[ibase] + k),
                            rng.getrandbits(8)))
            ilo = lin(iseg, regs[ibase]) & 0xFFFF
            spans.append(range(ilo, ilo + 6))
        if spec["prep"]:
            # PREPARE size16, level8: push BP (+ level-1 frame temps
            # read at BP-2k + the new frame ptr); SP -= size after
            size = rng.getrandbits(16)
            level = rng.randrange(0, 4) if rng.random() < 0.7 \
                else rng.randrange(0, 8)
            instr += size.to_bytes(2, "little") + bytes([level])
            npush = (level + 1) if level > 0 else 1
            plo = lin("ss", regs["sp"] - 2 * npush) & 0xFFFF
            spans.append(range(plo, plo + 2 * npush))
            for k in range(1, level):
                ram.append((lin("ss", regs["bp"] - 2 * k),
                            rng.getrandbits(8)))
                ram.append((lin("ss", regs["bp"] - 2 * k + 1),
                            rng.getrandbits(8)))
            if level > 1:
                blo = lin("ss", regs["bp"] - 2 * (level - 1)) & 0xFFFF
                spans.append(range(blo, blo + 2 * (level - 1)))
            name += f" size={size:04x}h level={level}"
        if spec["dispose"]:
            # DISPOSE: SP=BP; BP = word popped at ss:BP
            ram.append((lin("ss", regs["bp"]), rng.getrandbits(8)))
            ram.append((lin("ss", regs["bp"] + 1), rng.getrandbits(8)))
            blo = lin("ss", regs["bp"]) & 0xFFFF
            spans.append(range(blo, blo + 2))
        if spec["key"] == "58" or spec["popmem"]:   # POP reads [ss:sp]
            ram.append((lin("ss", regs["sp"]), rng.getrandbits(8)))
            ram.append((lin("ss", regs["sp"] + 1), rng.getrandbits(8)))
        if spec["popf"]:      # POP PSW: normalized image, BRK=0
            pfv = (rng.getrandbits(16) & 0x0ED5) | 0xF002
            ram.append((lin("ss", regs["sp"]), pfv & 0xFF))
            ram.append((lin("ss", regs["sp"] + 1), pfv >> 8))
            name += f" ({pfv:04x})"
        if spec["pushr"]:     # PUSH R: 8 words at sp-16..sp-1
            plo = lin("ss", regs["sp"] - 16) & 0xFFFF
            spans.append(range(plo, plo + 18))
        if spec["popr"]:      # POP R: 8 words read at sp..sp+15
            for k in range(16):
                ram.append((lin("ss", regs["sp"] + k), rng.getrandbits(8)))
            plo = lin("ss", regs["sp"]) & 0xFFFF
            spans.append(range(plo, plo + 16))
        if spec["stack"]:
            lo = (lin("ss", regs["sp"] - 8)) & 0xFFFF
            spans.append(range(lo, lo + 12))
        ivt = None
        if spec["divtrap"]:
            ivt = {0: (0x0000, HANDLER_OFF)}
            # handler: BR far to the stub (patched in emit_case)
            spans.append(range(0, 4))
            spans.append(range(HANDLER_OFF, HANDLER_OFF + 5))
        if spec["swint"]:
            vec = instr[1] if spec["swint"] == "cd" else \
                (3 if spec["swint"] == "brk3" else 4)
            fires = spec["swint"] != "brkv" or bool(regs["flags"] & 0x0800)
            if fires:
                ivt = {vec: (0x0000, HANDLER_OFF)}
                spans.append(range(4 * vec, 4 * vec + 4))
                spans.append(range(HANDLER_OFF, HANDLER_OFF + 5))
            elif spec["swint"] == "brkv":
                name += " (no trap)"
        if spec["chkind"]:
            # signed bounds pair from the placed operand; vector 5 on
            # out-of-range (docs: 0xFFFF upper = -1 traps)
            blo = opbytes[0] | (opbytes[1] << 8)
            bhi = opbytes[2] | (opbytes[3] << 8)
            idx = regs[REG16[(instr[len(spec["base"])] >> 3) & 7]]
            sv = [v - 0x10000 if v & 0x8000 else v for v in
                  (blo, bhi, idx)]
            if sv[2] < sv[0] or sv[2] > sv[1]:
                ivt = {5: (0x0000, HANDLER_OFF)}
                spans.append(range(20, 24))
                spans.append(range(HANDLER_OFF, HANDLER_OFF + 5))
                name += " (trap)"

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
        c = dict(regs=regs, instr=instr, ram=ram, name=name, ivt=ivt,
                 next_ip=next_ip, next_cs=next_cs)
        if spec["key"] in IO_IN_OPS:
            c["iord"] = rng.getrandbits(16)
            c["name"] += f" (iord={c['iord']:04x})"
        return c
    raise ComposeError("could not place case after 64 rerolls")


def gen_evt_case(spec, rng):
    """Random initial state + fixed-ish instruction for a pin-event form.
    Vectored forms park the store stub at a random location and point
    the IVT entry straight at it; execution between the test
    instruction and recognition runs image-fill NOPs."""
    for _ in range(64):
        regs = {r: rnd16(rng) for r in REG16}
        regs["cs"] = rng.getrandbits(16)
        regs["ip"] = rng.getrandbits(16)
        for sr in ("ds", "es", "ss"):
            regs[sr] = rng.getrandbits(16)
        f = (rng.getrandbits(16) & 0x0ED5) | 0xF002
        if spec["ie"] is not None:
            f = (f & ~0x0200) | (0x0200 if spec["ie"] else 0)
        regs["flags"] = f

        instr, ram, opname = spec["builder"](rng, regs)
        anchor = ((regs["cs"] << 4) + regs["ip"]) & 0xFFFFF
        a_phys = anchor & 0xFFFF

        def lin(seg, off):
            return ((regs[seg] << 4) + (off & 0xFFFF)) & 0xFFFFF

        delay = rng.randrange(spec["dmin"], spec["dmax"] + 1) \
            if spec["pin"] is not None else 0

        # execution margin: test instr + fill NOPs run until recognition
        spans = [range(a_phys, a_phys + len(instr) + 24)]
        ivt = None
        stub_linear = None
        if spec["close"] == "handler":
            stub_linear = rng.randrange(0x0800, 0xEF00) & 0xFFFE
            ivt = {spec["vec"]: (0x0000, stub_linear)}
            spans.append(range(4 * spec["vec"], 4 * spec["vec"] + 4))
            spans.append(range(stub_linear, stub_linear + 24))
            # interrupt pushes: 3 words below SS:SP; MOV SS,AW moves the
            # stack to AW:SP before the pushes
            pss = "ss"
            pv = regs["ss"]
            if spec["key"] == "INT.8ED0":
                pv = regs["ax"]
            plo = ((pv << 4) + ((regs["sp"] - 6) & 0xFFFF)) & 0xFFFFF
            spans.append(range(plo & 0xFFFF, (plo & 0xFFFF) + 8))
            _ = pss
        # (close="next" forms: the stub sits inside the margin span)
        if spec["key"] == "INT.9D":
            # POP PSW read at ss:sp; pushes at sp-4..sp+1 (post-pop SP):
            # the handler-push span above covers sp-6..sp+1 already
            pass
        if spec["key"] == "INT.F3AA":   # STM writes cx bytes from es:di
            df = (regs["flags"] >> 10) & 1
            for i in range(regs["cx"]):
                step = -i if df else i
                do = (regs["di"] + step) & 0xFFFF
                spans.append(range(lin("es", do) & 0xFFFF,
                                   (lin("es", do) & 0xFFFF) + 1))

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
        for a, _v in ram:
            if (a & 0xFFFF) in testimage.RESERVED:
                bad = True
        if bad:
            continue
        name = f"{opname} <{spec['mnem']} d={delay}>"
        return dict(regs=regs, instr=instr, ram=ram, name=name, ivt=ivt,
                    stub_linear=stub_linear, delay=delay)
    raise ComposeError("could not place evt case after 64 rerolls")


# empirical execution time of one 63 C0 preload (cycles): shifts the
# pf-variant event delay so the assert still lands around the test
# instruction (measured: 63 C0 retires in 50 cycles)
PRELOAD_CYCLES = 50


def emit_evt_case(spec, case, host, tag, preload_n=0, waits=0):
    """Run one pin-event case on hardware, return the suite test object."""
    nec_regs = {INTEL2NEC[k]: v for k, v in case["regs"].items()}
    instr = case["instr"]
    ivt = case["ivt"]
    anchor = ((case["regs"]["cs"] << 4) + case["regs"]["ip"]) & 0xFFFFF

    if preload_n:
        nec_regs["PC"] = (nec_regs["PC"] - 2 * preload_n) & 0xFFFF
        run_instr = PRELOAD_BYTES * preload_n + instr
    else:
        run_instr = instr

    if spec["close"] == "handler":
        stub_linear = case["stub_linear"]
    else:
        stub_linear = (anchor + len(instr)) & 0xFFFF

    trig = ((case["regs"]["cs"] << 4) + nec_regs["PC"]) & 0xFFFFF
    delay_hw = case["delay"] + (PRELOAD_CYCLES * preload_n)
    evt = None
    if spec["pin"] is not None:
        evt = (trig, delay_hw, spec["hold"], spec["pin"])
    pins = spec["pins"]

    image, meta = testimage.compose(regs=nec_regs, instr=run_instr,
                                    ram=case["ram"], ivt=ivt,
                                    stub_linear=stub_linear)
    recs, fired = run_image(image, host, tag, waits=waits, evt=evt,
                            iord=None, pins=pins or None, want_fired=True,
                            cap=EMIT_CAP, use_core=EMIT_USE_CORE)
    if evt and not fired:
        raise RunError("event did not fire")
    res = parse_result(recs, meta)

    close_addr = stub_linear if spec["close"] == "handler" else None
    rows, events, i0, i1, q0, qf, fetched, memrd = \
        build_rows(recs, meta["anchor_linear"], n_skip_f=preload_n,
                   n_close=1, close_addr=close_addr)

    # event timing for replay: cold cases use the harness fetch-trigger
    # law; prefetched cases anchor on the window-opening F pop (the
    # preloads do not exist in TB replay)
    evt_json = None
    if evt:
        if preload_n == 0:
            evt_json = {"pin": spec["pin"], "hold": spec["hold"],
                        "trigger": "fetch", "addr": trig,
                        "delay": case["delay"]}
        else:
            t1 = next(r["idx"] for r in recs
                      if r["t"] == 1 and r["bs_early"] == 4
                      and r["ad_addr"] == trig)
            assert_cyc = t1 + 2 + delay_hw
            fpop0 = events[i0][0]["idx"]
            d = assert_cyc - fpop0
            if d < 1:
                # d=0 (assert exactly at the window-opening pop) is not
                # schedulable in TB replay; reroll
                raise RunError(f"pf assert before window ({d})")
            evt_json = {"pin": spec["pin"], "hold": spec["hold"],
                        "trigger": "fpop", "delay": d}

    # sanity: vectored forms must push a PC at/after the test instruction
    if spec["close"] == "handler":
        writes = window_writes(events, i0, i1)
        wb = []
        for t in writes:
            wb += write_bytes(t)
        if len(wb) < 6:
            raise RunError("fewer than 3 pushed words in window")
        last2 = dict(wb[-2:])
        lo_a = min(last2)
        if lo_a + 1 not in last2:
            raise RunError("PC push bytes not contiguous")
        pushed_pc = last2[lo_a] | (last2[lo_a + 1] << 8)
        min_pc = case["regs"]["ip"] if spec["key"] == "INT.F3AA" else \
            (case["regs"]["ip"] + len(instr)) & 0xFFFF
        if pushed_pc < min_pc or pushed_pc > min_pc + 12:
            raise RunError(f"recognition off-window: pushed {pushed_pc:04x}"
                           f" vs min {min_pc:04x}")

    # initial ram: instr + placed operands + IVT + fill actually read
    init_ram = []
    placed = {}
    for k, b in enumerate(instr):
        placed[(anchor + k) & 0xFFFFF] = b
        init_ram.append([(anchor + k) & 0xFFFFF, b])
    for a, v in case["ram"]:
        placed[a & 0xFFFFF] = v
        init_ram.append([a & 0xFFFFF, v])
    if ivt:
        for n, (seg, off) in ivt.items():
            for k, b in enumerate(off.to_bytes(2, "little") +
                                  seg.to_bytes(2, "little")):
                placed[4 * n + k] = b
                init_ram.append([4 * n + k, b])
    for a in sorted(fetched | memrd):
        a20 = a & 0xFFFFF
        if a20 not in placed:
            v = image[a20 & 0xFFFF]
            placed[a20] = v
            init_ram.append([a20, v])

    writes = window_writes(events, i0, i1)
    mem = dict(placed)
    fin_ram = []
    for t in writes:
        for a, b in write_bytes(t):
            a20 = a & 0xFFFFF
            if mem.get(a20) != b:
                mem[a20] = b
                fin_ram.append([a20, b])

    got = res["regs"]
    if got.get("PSW") is None or (got["PSW"] & 0xF002) != 0xF002 or \
            (got["PSW"] & 0x0028) != 0:
        # PSW extraction corrupted (stack mirror collided with the
        # scratch page) - reroll. Reserved bits: 15-12 and 1 read as 1,
        # 5 and 3 as 0 (closure block: f017/ffee/9e4d-style corruptions)
        raise RunError(f"implausible final PSW {got.get('PSW')}")
    fin_regs = {}
    for ik, nk in INTEL2NEC.items():
        if ik == "ip":
            fin_ip = stub_linear if spec["close"] == "handler" else \
                (case["regs"]["ip"] + len(instr)) & 0xFFFF
            if fin_ip != case["regs"]["ip"]:
                fin_regs["ip"] = fin_ip
        elif ik == "cs":
            fin_cs = 0x0000 if spec["close"] == "handler" else \
                case["regs"]["cs"]
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
    if evt_json:
        test["evt"] = evt_json
    if pins:
        test["pins"] = pins
    if spec["close"] == "handler":
        test["close_addr"] = stub_linear
    if _mirror_collision(test):
        raise ComposeError("64K-mirror footprint collision "
                            "(aliased 20-bit addresses; invalid on flat memory)")
    test["hash"] = hashlib.sha1(
        json.dumps([test["name"], test["bytes"], test["initial"],
                    test["final"], test["cycles"]],
                   separators=(",", ":")).encode()).hexdigest()
    return test


#----------------------------------------------------------------------------
# capture -> suite record
#----------------------------------------------------------------------------

def fetch_width(rec):
    return 2 if (rec["ad_addr"] & 1) == 0 and not rec["ube_n"] else 1


def build_rows(recs, anchor_linear, n_skip_f=0, n_close=1,
               close_addr=None):
    """Walk recs from the test anchor, reconstructing the shadow queue.
    Returns (rows, i0, i1, q_at_start, q_final, fetched, memr_bytes):
    rows = cycle rows for the window [F pop #n_skip_f .. F pop
    #n_skip_f+n_close]; prefixed instructions pop one F per prefix
    byte, so their windows close n_close = 1+nprefix pops later.
    close_addr (linear): close instead at the first F pop AFTER i0
    whose byte was fetched from close_addr (interrupt-handler entry).
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
    if close_addr is not None:
        i1 = next((i for i in fpop_is
                   if i > i0 and events[i][1] is not None
                   and events[i][1][0] is not None
                   and (events[i][1][0] & 0xFFFFF) == close_addr), None)
        if i1 is None:
            raise RunError(f"no F pop from close addr {close_addr:05x}")
    else:
        if len(fpop_is) < n_skip_f + n_close + 1:
            raise RunError(f"only {len(fpop_is)} F pops after anchor")
        i1 = fpop_is[n_skip_f + n_close]

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


def emit_case(spec, case, host, tag, preload_n=0, waits=0):
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

    next_ip = case.get("next_ip")
    if next_ip is None:
        next_ip = (case["regs"]["ip"] + len(instr)) & 0xFFFF
    next_cs = case.get("next_cs")
    cont_cs = next_cs if next_cs is not None else case["regs"]["cs"]
    stub_linear = ((cont_cs << 4) + next_ip) & 0xFFFF
    if ivt:
        # handler at HANDLER_OFF: BR far 0000:stub
        h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
        ram += [(HANDLER_OFF + k, b) for k, b in enumerate(h)]

    image, meta = testimage.compose(regs=nec_regs, instr=run_instr,
                                    ram=ram, ivt=ivt,
                                    stub_linear=stub_linear)
    recs = run_image(image, host, tag, waits=waits,
                     iord=case.get("iord"), cap=EMIT_CAP,
                     use_core=EMIT_USE_CORE)
    res = parse_result(recs, meta)

    rows, events, i0, i1, q0, qf, fetched, memrd = \
        build_rows(recs, meta["anchor_linear"], n_skip_f=preload_n,
                   n_close=1 + n_prefix(spec))

    # continuation check: the window-closing F pop must come from the
    # predicted next_ip (guards branch/ret prediction and stub placement)
    pop1 = events[i1][1]
    tgt_lin = (((cont_cs << 4) + next_ip) & 0xFFFFF)
    if case["ivt"] is None:
        if pop1 is None or pop1[0] is None or \
                (pop1[0] & 0xFFFFF) != tgt_lin:
            got_a = None if (pop1 is None or pop1[0] is None) else pop1[0]
            raise RunError(f"continuation mismatch: predicted "
                           f"{tgt_lin:05x}, window closed at "
                           f"{got_a if got_a is None else hex(got_a)}")

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
        vec = next(iter(ivt))
        seg, off = ivt[vec]
        for k, b in enumerate(off.to_bytes(2, "little") +
                              seg.to_bytes(2, "little")):
            placed[4 * vec + k] = b
            init_ram.append([4 * vec + k, b])
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
    trap_addrs = ()
    if ivt is not None:
        _vec = next(iter(ivt))
        trap_addrs = (4 * _vec, 4 * _vec + 2)
    trapped = ivt is not None and any(
        r["t"] == 1 and r["bs_early"] == 5 and r["ad_addr"] in trap_addrs
        for r, _, _ in events[i0:i1 + 1])

    got = res["regs"]
    if got.get("PSW") is not None and \
            ((got["PSW"] & 0xF002) != 0xF002 or (got["PSW"] & 0x0028) != 0):
        # PSW extraction corruption (see the evt-path check) - reroll
        raise RunError(f"implausible final PSW {got['PSW']:04x}")
    fin_regs = {}
    for ik, nk in INTEL2NEC.items():
        if ik == "ip":
            fin_ip = HANDLER_OFF if trapped else next_ip
            if fin_ip != case["regs"]["ip"]:
                fin_regs["ip"] = fin_ip
        elif ik == "cs":
            fin_cs = 0x0000 if trapped else cont_cs
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
    if case.get("iord") is not None:
        test["iord"] = case["iord"]
    if _mirror_collision(test):
        raise ComposeError("64K-mirror footprint collision "
                            "(aliased 20-bit addresses; invalid on flat memory)")
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
    recs = run_image(image, host, tag="pc0", use_core=EMIT_USE_CORE)
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
        recs = run_image(image, host, tag=f"pc{n}", use_core=EMIT_USE_CORE)
        try:
            rows, events, i0, i1, q0, qf, _, _ = \
                build_rows(recs, meta["anchor_linear"], n_skip_f=n)
            print(f"N={n}: queue at test F pop = {len(q0)} bytes "
                  f"{[f'{b:02x}' for b in q0]}")
        except RunError as e:
            print(f"N={n}: {e}")
    return 0


def _emit_one_index(spec, is_evt, op, idx, host, seed_base, preload_n, waits):
    """Emit a single OUTPUT index deterministically and confined to that index:
    attempt 0 uses the ORIGINAL per-case seed f"{base}/{op}/{idx}" (so a
    non-colliding index re-emits byte-identically); collisions/failures reroll
    WITHIN the index via f".../{idx}/{r}" (r>=1) - never skip-to-next-seed, so
    other indices are untouched. Returns the test object (idx set)."""
    pn = preload_n if preload_n >= 0 else (2 if idx % 2 == 1 else 0)
    for r in range(64):
        sd = f"{seed_base}/{op}/{idx}" if r == 0 \
            else f"{seed_base}/{op}/{idx}/{r}"
        rng = random.Random(sd)
        try:
            if is_evt:
                case = gen_evt_case(spec, rng)
                t = emit_evt_case(spec, case, host, tag=f"re{op}",
                                  preload_n=pn, waits=waits)
            else:
                case = gen_case(spec, rng)
                t = emit_case(spec, case, host, tag=f"re{op}",
                              preload_n=pn, waits=waits)
        except (ComposeError, RunError):
            continue
        t["idx"] = idx
        return t
    raise RunError(f"{op} idx {idx}: no collision-free case in 64 rerolls")


def cmd_reemit(host, index_map, out_dir, seed_base, preload_n=-1, waits=0):
    """Re-emit specific OUTPUT indices per form (from index_map = {op:[idx..]}),
    replacing them in-place in the existing files. Confined per index (see
    _emit_one_index) so non-targeted cases stay byte-identical. Use for the
    collision re-emission and for 10k resumability. NOTE: only valid for forms
    whose current file has idx==seed (no skip-to-next rerolls in emit_log); a
    form with a logged reroll must be FULLY re-emitted instead."""
    if EMIT_USE_CORE is not False:
        raise RunError("re-emit truth source is not the socket")
    out_dir = Path(out_dir)
    for op, idxs in index_map.items():
        is_evt = op in EVT_FORMS
        spec = EVT_FORMS[op] if is_evt else OPCODES[op]
        fn = out_dir / f"{op}.json.gz"
        tests = json.load(gzip.open(fn))
        by = {t["idx"]: t for t in tests}
        for idx in idxs:
            by[idx] = _emit_one_index(spec, is_evt, op, idx, host,
                                      seed_base, preload_n, waits)
        merged = [by[k] for k in sorted(by)]
        with gzip.open(fn, "wt") as f:
            json.dump(merged, f, separators=(",", ":"))
        print(f"{op}: re-emitted {len(idxs)} indices -> {fn}", flush=True)
    return 0


def cmd_emit(host, opcodes, n_cases, out_dir, seed_base, preload_n,
             waits=0):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "emit_log.txt"
    # TRUTH-SOURCE GUARD: goldens may ONLY be captured from the socketed real
    # chip (use_core=False). The internal v30_core is the DUT, never the
    # reference. A pin at the emit call sites (EMIT_USE_CORE) PLUS this per-run
    # assertion + log line, so a future use_core-style A/B flag added to the
    # harness cannot silently redirect truth back to the core (see bringup_log
    # "wrong core selected for emission").
    if EMIT_USE_CORE is not False:
        raise RunError(
            "REFUSING to emit goldens: truth source is not the socket "
            f"(EMIT_USE_CORE={EMIT_USE_CORE!r}); goldens require use_core=False")
    truth = "SOCKET (real chip, use_core=False)"
    stamp = (f"# TRUTH SOURCE: {truth}  seed_base={seed_base}  "
             f"cases={n_cases}  waits={waits}  forms={len(opcodes)}")
    with log.open("a") as f:
        f.write(stamp + "\n")
    print(stamp, flush=True)
    for op in opcodes:
        is_evt = op in EVT_FORMS
        spec = EVT_FORMS[op] if is_evt else OPCODES[op]
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
                if is_evt:
                    case = gen_evt_case(spec, rng)
                    t = emit_evt_case(spec, case, host, tag=f"em{op}",
                                      preload_n=pn, waits=waits)
                else:
                    case = gen_case(spec, rng)
                    t = emit_case(spec, case, host, tag=f"em{op}",
                                  preload_n=pn, waits=waits)
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


def cmd_spotcheck(host, out_dir, per_op=3):
    """Mission 16 validation: replay emitted cases' initial states
    (non-prefetched) and compare architectural finals with the records.
    Prefetched records thereby also get an architectural cross-check."""
    out_dir = Path(out_dir)
    total = bad = 0
    for gz in sorted(out_dir.glob("*.json.gz")):
        op = gz.name[:-len(".json.gz")]
        if op not in OPCODES:
            continue
        spec = OPCODES[op]
        tests = json.load(gzip.open(gz))
        rng = random.Random(f"spot/{op}")
        for t in rng.sample(tests, min(per_op, len(tests))):
            regs = dict(t["initial"]["regs"])
            instr = bytes(t["bytes"])
            anchor = ((regs["cs"] << 4) + regs["ip"]) & 0xFFFFF
            ibytes = set(range(anchor, anchor + len(instr)))
            hbytes = set(range(HANDLER_OFF, HANDLER_OFF + 5)) | \
                set(range(0, 4)) if spec["divtrap"] else set()
            ram = [(a, v) for a, v in t["initial"]["ram"]
                   if a not in ibytes and a not in hbytes]
            ivt = {0: (0x0000, HANDLER_OFF)} if spec["divtrap"] else None
            case = dict(regs=regs, instr=instr, ram=ram,
                        name=t["name"], ivt=ivt)
            total += 1
            try:
                t2 = emit_case(spec, case, host, tag=f"sp{op}")
            except (ComposeError, RunError) as e:
                print(f"{op} idx {t['idx']}: replay failed {str(e)[:80]}")
                bad += 1
                continue
            r_ok = t2["final"]["regs"] == t["final"]["regs"]
            m1 = {a: v for a, v in t["final"]["ram"]}
            m2 = {a: v for a, v in t2["final"]["ram"]}
            m_ok = m1 == m2
            if not (r_ok and m_ok):
                bad += 1
                print(f"{op} idx {t['idx']} {t['name']!r}: MISMATCH "
                      f"regs {t['final']['regs']} vs {t2['final']['regs']}"
                      f" ram {m1} vs {m2}")
        print(f"{op}: checked", flush=True)
    print(f"\nspotcheck: {total - bad}/{total} replays match")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd",
                    choices=["validate", "preload-cal", "emit", "spotcheck",
                             "reemit"])
    ap.add_argument("--indices-file", default="",
                    help="reemit: JSON {op: [output-idx, ...]} to re-emit in "
                         "place (confined per index; non-targeted cases untouched)")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--opcodes", default=",".join(TRANCHE))
    ap.add_argument("--cases", type=int, default=500)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", default="v30-v0.1")
    ap.add_argument("--preload", type=int, default=-1,
                    help="-1 = alternate non-prefetched / prefetched(N=2) "
                         "per V20 convention (default); 0 = none; N>0 = "
                         "always N 63C0 preload repetitions")
    ap.add_argument("--waits", type=int, default=0,
                    help="harness wait states per bus cycle (CFG waits)")
    args = ap.parse_args()
    global EMIT_CAP
    if args.waits:
        EMIT_CAP = min(4096, EMIT_CAP * (1 + args.waits))
    if args.cmd == "validate":
        return cmd_validate(args.host)
    if args.cmd == "spotcheck":
        return cmd_spotcheck(args.host, args.out)
    if args.cmd == "preload-cal":
        return cmd_preload_cal(args.host)
    if args.cmd == "reemit":
        index_map = json.load(open(args.indices_file))
        return cmd_reemit(args.host, index_map, args.out, args.seed,
                          args.preload, args.waits)
    return cmd_emit(args.host, args.opcodes.split(","), args.cases,
                    args.out, args.seed, args.preload, args.waits)


if __name__ == "__main__":
    sys.exit(main())
