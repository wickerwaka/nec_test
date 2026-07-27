#!/usr/bin/env python3
"""optable - static opcode metadata for the massive fuzz expansion (task #29).

The fuzz generators (gen_soup Tier A, gen_raw Tier B) draw over the FULL legal
opcode space rather than a curated menu.  This module is the single authority
on what each byte IS and how it may be emitted:

  * a per-opcode emission POLICY class (see POLICY) that gen_soup dispatches on,
  * the group /reg extensions that are HARD-BANNED even when the opcode is legal
    (FE /2-7, 8E /1 = MOV CS, FF /7),
  * a full 0F WHITELIST (only the documented extension forms; everything else in
    the 0F space is BANNED - 0F 34 locks the chip, 0F 35-3F are unprobed, 0F
    E0/F0 are V33 BRKXA/RETXA, and the >=0x40 aliases fall into BRKEM),
  * ilen(buf, i): a static instruction-length decoder over the legal 1-byte +
    whitelisted-0F space (prefix stacks, modrm+disp, W/ext-dependent immediates).

Authorities cross-checked by selfcheck():
  * docs/facts/undocumented_0f.md   - the 0F-space behaviour survey (0F authority)
  * docs/facts/instructions.json    - documented encoding bit-strings
  * sw/fuzz_cov.py                  - GROUP_OPS / MODRM_OPS / F0_MODRM sets

Run `python3 sw/optable.py --selfcheck` for the standing generation-side gate.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import fuzz_cov  # noqa: E402  (GROUP_OPS / MODRM_OPS / F0_MODRM cross-check sets)

FACTS = ROOT / "docs" / "facts" / "instructions.json"

# --- emission policy classes -----------------------------------------------
# gen_soup dispatches per Op.policy; gen_raw only consults BANNED (scrub pass).
FREE = "FREE"                 # ALU / MOV imm / flags / adjust: fully random operands
EA = "EA"                     # memory-operand form: windowed direct EA or wild modrm
PORT = "PORT"                 # IN/OUT + string I/O: even harness-safe port band
STACK = "STACK"               # PUSH/POP/ENTER/LEAVE: depth-capped, SP re-windowed
CFLOW_FWD = "CFLOW_FWD"       # forward-only branch (Jcc / JMP short|near / JCXZ)
CFLOW_GADGET = "CFLOW_GADGET" # CALL/RET/far/indirect/LOOP/INTn: contained gadgets
SREG = "SREG"                 # segment-register load/store (MOV CS is ext-banned)
EVT_ONLY = "EVT_ONLY"         # HALT / POLL: only with an armed wake event
BRKEM = "BRKEM"               # 0F FF ib: the accepted 8080-gap entry
UNDOC = "UNDOC"               # undocumented-but-characterised-safe (low emit rate)
BANNED = "BANNED"             # never emitted; lint-asserted absent

# the nine prefix bytes (all exercised incl. the previously-untested
# repnz/lock/repnc/repc): 4 seg overrides, 2 repc/repnc, lock, repnz, rep.
SEG_PREFIXES = (0x26, 0x2E, 0x36, 0x3E)
PREFIXES = frozenset(SEG_PREFIXES) | {0x64, 0x65, 0xF0, 0xF2, 0xF3}


@dataclass(frozen=True)
class Op:
    code: int                 # opcode byte (or 0F second byte for the 0F set)
    mnem: str
    policy: str
    modrm: bool = False       # consumes a modrm byte (+ disp per mod/rm)
    group: bool = False       # /reg field of the modrm selects the operation
    imm: int = 0              # fixed immediate bytes AFTER modrm+disp
    rel: int = 0              # relative-branch displacement bytes (imm-like)
    farptr: bool = False      # trailing off16:seg16 (EA/9A far pointer)
    imm_extdep: bool = False  # F6/F7: /0,/1 carry an immediate, /2-7 do not
    banned_ext: frozenset = field(default_factory=frozenset)
    note: str = ""


# ---------------------------------------------------------------------------
# One-byte opcode table (0x00-0xFF). Built programmatically for the regular
# ALU / reg-encoded ranges, then patched for the irregular remainder.
# ---------------------------------------------------------------------------
TABLE = {}


def _put(code, mnem, policy, **kw):
    TABLE[code] = Op(code, mnem, policy, **kw)


# ALU family: 8 ops x {rm,r | r,rm | acc,imm8 | acc,imm16} at base 0x00,08,...,38
_ALU = ["ADD", "OR", "ADC", "SBB", "AND", "SUB", "XOR", "CMP"]
for _i, _nm in enumerate(_ALU):
    _b = _i * 8
    _put(_b + 0, f"{_nm} rm,r8", EA, modrm=True)
    _put(_b + 1, f"{_nm} rm,r16", EA, modrm=True)
    _put(_b + 2, f"{_nm} r8,rm", EA, modrm=True)
    _put(_b + 3, f"{_nm} r16,rm", EA, modrm=True)
    _put(_b + 4, f"{_nm} AL,imm8", FREE, imm=1)
    _put(_b + 5, f"{_nm} AW,imm16", FREE, imm=2)

# segment PUSH/POP interleaved in the ALU rows (06/07/0E/16/17/1E/1F) + 0F prefix
_put(0x06, "PUSH ES", STACK)
_put(0x07, "POP ES", SREG)
_put(0x0E, "PUSH CS", STACK)
# 0x0F handled as the two-byte prefix below (not in TABLE as an Op)
_put(0x16, "PUSH SS", STACK)
_put(0x17, "POP SS", SREG)
_put(0x1E, "PUSH DS", STACK)
_put(0x1F, "POP DS", SREG)

# BCD/segment-override rows: 26/2E/36/3E are prefixes; 27/2F/37/3F accumulator
_put(0x27, "DAA", FREE)
_put(0x2F, "DAS", FREE)
_put(0x37, "AAA", FREE)
_put(0x3F, "AAS", FREE)
for _p in SEG_PREFIXES:
    _put(_p, "SEG:", FREE, note="prefix")   # policy unused; PREFIXES gates emission

# INC/DEC r16 (0x40-0x4F), PUSH/POP r16 (0x50-0x5F)
for _r in range(8):
    _put(0x40 + _r, "INC r16", FREE)
    _put(0x48 + _r, "DEC r16", FREE)
    _put(0x50 + _r, "PUSH r16", STACK)
    _put(0x58 + _r, "POP r16", STACK)

# 0x60-0x6F: PUSHA/POPA, BOUND, undoc, prefixes, IMUL-imm, string I/O
_put(0x60, "PUSH R", STACK)
_put(0x61, "POP R", STACK)
_put(0x62, "BOUND", EA, modrm=True)
_put(0x63, "undoc63", UNDOC, note="undocumented (BRKS/RETRBI territory)")
_put(0x64, "REPNC", FREE, note="prefix")
_put(0x65, "REPC", FREE, note="prefix")
_put(0x66, "FPO2 fp-op", EA, modrm=True, note="coprocessor op-2 escape")
_put(0x67, "FPO2 fp-op,mem", EA, modrm=True, note="coprocessor op-2 escape")
_put(0x68, "PUSH imm16", STACK, imm=2)
_put(0x69, "IMUL r16,rm,imm16", EA, modrm=True, imm=2)
_put(0x6A, "PUSH imm8", STACK, imm=1)
_put(0x6B, "IMUL r16,rm,imm8", EA, modrm=True, imm=1)
_put(0x6C, "INMB", PORT)
_put(0x6D, "INMW", PORT)
_put(0x6E, "OUTMB", PORT)
_put(0x6F, "OUTMW", PORT)

# Jcc rel8 (0x70-0x7F)
_JCC = ["JO", "JNO", "JC", "JNC", "JZ", "JNZ", "JBE", "JA",
        "JS", "JNS", "JPE", "JPO", "JL", "JGE", "JLE", "JG"]
for _c, _nm in enumerate(_JCC):
    _put(0x70 + _c, f"{_nm} rel8", CFLOW_FWD, rel=1)

# group1 ALU imm (80/81/82/83)
_put(0x80, "GRP1 rm,imm8", EA, modrm=True, group=True, imm=1)
_put(0x81, "GRP1 rm,imm16", EA, modrm=True, group=True, imm=2)
_put(0x82, "GRP1 rm,imm8 (alias)", EA, modrm=True, group=True, imm=1)
_put(0x83, "GRP1 rm,imm8sx", EA, modrm=True, group=True, imm=1)

_put(0x84, "TEST rm,r8", EA, modrm=True)
_put(0x85, "TEST rm,r16", EA, modrm=True)
_put(0x86, "XCHG rm,r8", EA, modrm=True)
_put(0x87, "XCHG rm,r16", EA, modrm=True)
_put(0x88, "MOV rm,r8", EA, modrm=True)
_put(0x89, "MOV rm,r16", EA, modrm=True)
_put(0x8A, "MOV r8,rm", EA, modrm=True)
_put(0x8B, "MOV r16,rm", EA, modrm=True)
_put(0x8C, "MOV rm,sreg", SREG, modrm=True)
_put(0x8D, "LEA r16,m", EA, modrm=True)
# 8E MOV sreg,rm: /1 = MOV CS is HARD-BANNED (would reload PS to garbage)
_put(0x8E, "MOV sreg,rm", SREG, modrm=True, group=True, banned_ext=frozenset({1}))
_put(0x8F, "POP rm", STACK, modrm=True, group=True)

# 0x90-0x9F: NOP/XCHG acc, CBW/CWD, far CALL, POLL, PUSHF/POPF, SAHF/LAHF
_put(0x90, "NOP", FREE)
for _r in range(1, 8):
    _put(0x90 + _r, "XCHG AW,r16", FREE)
_put(0x98, "CVTBW", FREE)
_put(0x99, "CVTWL", FREE)
_put(0x9A, "CALL far", CFLOW_GADGET, farptr=True)
_put(0x9B, "POLL", EVT_ONLY)
_put(0x9C, "PUSHF", STACK)
_put(0x9D, "POPF", STACK)
_put(0x9E, "SAHF", FREE)
_put(0x9F, "LAHF", FREE)

# 0xA0-0xAF: MOV acc,moffs; string ops; TEST acc,imm
_put(0xA0, "MOV AL,moffs", EA, imm=2)
_put(0xA1, "MOV AW,moffs", EA, imm=2)
_put(0xA2, "MOV moffs,AL", EA, imm=2)
_put(0xA3, "MOV moffs,AW", EA, imm=2)
_put(0xA4, "MOVSB", EA)
_put(0xA5, "MOVSW", EA)
_put(0xA6, "CMPSB", EA)
_put(0xA7, "CMPSW", EA)
_put(0xA8, "TEST AL,imm8", FREE, imm=1)
_put(0xA9, "TEST AW,imm16", FREE, imm=2)
_put(0xAA, "STOSB", EA)
_put(0xAB, "STOSW", EA)
_put(0xAC, "LODSB", EA)
_put(0xAD, "LODSW", EA)
_put(0xAE, "SCASB", EA)
_put(0xAF, "SCASW", EA)

# MOV r8,imm8 (B0-B7), MOV r16,imm16 (B8-BF)
for _r in range(8):
    _put(0xB0 + _r, "MOV r8,imm8", FREE, imm=1)
    _put(0xB8 + _r, "MOV r16,imm16", FREE, imm=2)

# 0xC0-0xCF: shift-imm group, RET, LES/LDS, MOV rm,imm, ENTER/LEAVE, INT/IRET
_put(0xC0, "GRP2 rm8,imm8", EA, modrm=True, group=True, imm=1)
_put(0xC1, "GRP2 rm16,imm8", EA, modrm=True, group=True, imm=1)
_put(0xC2, "RET imm16", CFLOW_GADGET, imm=2)
_put(0xC3, "RET", CFLOW_GADGET)
_put(0xC4, "LES r16,m", EA, modrm=True)
_put(0xC5, "LDS r16,m", EA, modrm=True)
_put(0xC6, "MOV rm8,imm8", EA, modrm=True, group=True, imm=1)
_put(0xC7, "MOV rm16,imm16", EA, modrm=True, group=True, imm=2)
_put(0xC8, "PREPARE imm16,imm8", STACK, imm=3)
_put(0xC9, "DISPOSE", STACK)
_put(0xCA, "RETF imm16", CFLOW_GADGET, imm=2)
_put(0xCB, "RETF", CFLOW_GADGET)
_put(0xCC, "INT3", CFLOW_GADGET)
_put(0xCD, "INT imm8", CFLOW_GADGET, imm=1)
_put(0xCE, "INTO", CFLOW_GADGET)
_put(0xCF, "IRET", CFLOW_GADGET)

# 0xD0-0xDF: shift group, AAM/AAD, SALC, XLAT, ESC(FPU)
_put(0xD0, "GRP2 rm8,1", EA, modrm=True, group=True)
_put(0xD1, "GRP2 rm16,1", EA, modrm=True, group=True)
_put(0xD2, "GRP2 rm8,CL", EA, modrm=True, group=True)
_put(0xD3, "GRP2 rm16,CL", EA, modrm=True, group=True)
_put(0xD4, "AAM imm8", FREE, imm=1)
_put(0xD5, "AAD imm8", FREE, imm=1)
_put(0xD6, "SALC", UNDOC, note="undocumented set-AL-from-carry")
_put(0xD7, "XLAT", EA)
for _e in range(8):
    _put(0xD8 + _e, "FPO2 (ESC)", EA, modrm=True, note="coprocessor escape (dummy EA read)")

# 0xE0-0xEF: LOOP family, IN/OUT imm8, CALL/JMP rel, far JMP, IN/OUT DX
_put(0xE0, "LOOPNE rel8", CFLOW_GADGET, rel=1)
_put(0xE1, "LOOPE rel8", CFLOW_GADGET, rel=1)
_put(0xE2, "LOOP rel8", CFLOW_GADGET, rel=1)
_put(0xE3, "JCXZ rel8", CFLOW_FWD, rel=1)
_put(0xE4, "IN AL,imm8", PORT, imm=1)
_put(0xE5, "IN AW,imm8", PORT, imm=1)
_put(0xE6, "OUT imm8,AL", PORT, imm=1)
_put(0xE7, "OUT imm8,AW", PORT, imm=1)
_put(0xE8, "CALL rel16", CFLOW_GADGET, rel=2)
_put(0xE9, "JMP rel16", CFLOW_FWD, rel=2)
_put(0xEA, "JMP far", CFLOW_GADGET, farptr=True)
_put(0xEB, "JMP rel8", CFLOW_FWD, rel=1)
_put(0xEC, "IN AL,DW", PORT)
_put(0xED, "IN AW,DW", PORT, note="native IN AW,DX (NOT the 8080 lead byte here)")
_put(0xEE, "OUT DW,AL", PORT)
_put(0xEF, "OUT DW,AW", PORT)

# 0xF0-0xFF: LOCK, undoc, REP, HALT, CMC, unary/mul/div group, flags, INC/DEC group
_put(0xF0, "BUSLOCK", FREE, note="prefix")
_put(0xF1, "undocF1", UNDOC, note="undocumented")
_put(0xF2, "REPNE", FREE, note="prefix")
_put(0xF3, "REP", FREE, note="prefix")
_put(0xF4, "HALT", EVT_ONLY)
_put(0xF5, "CMC", FREE)
# F6/F7 group: /0,/1 TEST carry an immediate; /2-7 (NOT/NEG/MUL/IMUL/DIV/IDIV) do not
_put(0xF6, "GRP3 rm8", EA, modrm=True, group=True, imm_extdep=True)
_put(0xF7, "GRP3 rm16", EA, modrm=True, group=True, imm_extdep=True)
_put(0xF8, "CLC", FREE)
_put(0xF9, "STC", FREE)
_put(0xFA, "DI", FREE)
_put(0xFB, "EI", FREE)
_put(0xFC, "CLD", FREE)
_put(0xFD, "STD", FREE)
# FE group: only /0 INC /1 DEC are legal (byte); /2-7 are HARD-BANNED
_put(0xFE, "GRP4 rm8", EA, modrm=True, group=True,
     banned_ext=frozenset({2, 3, 4, 5, 6, 7}))
# FF group: /0 INC /1 DEC /2 CALL /3 CALLF /4 JMP /5 JMPF /6 PUSH legal; /7 BANNED
_put(0xFF, "GRP5 rm16", EA, modrm=True, group=True, banned_ext=frozenset({7}))


# ---------------------------------------------------------------------------
# 0F extension WHITELIST (docs/facts/undocumented_0f.md + instructions.json).
# Only the documented forms; every other second byte is BANNED (see is_banned_0f).
# ---------------------------------------------------------------------------
F0_WHITELIST = {}


def _put0f(b2, mnem, policy, **kw):
    F0_WHITELIST[b2] = Op(b2, mnem, policy, **kw)


# TEST1/CLR1/NOT1/SET1 by CL (0F 10-17) then by imm3/imm4 (0F 18-1F)
for _o in range(0x10, 0x18):
    _put0f(_o, "bitop rm,CL", EA, modrm=True, group=True)
for _o in range(0x18, 0x20):
    _put0f(_o, "bitop rm,imm", EA, modrm=True, group=True, imm=1)
# ADD4S/SUB4S/CMP4S (0F 20/22/26): fixed CL-counted, NO modrm
_put0f(0x20, "ADD4S", EA)
_put0f(0x22, "SUB4S", EA)
_put0f(0x26, "CMP4S", EA)
# ROL4/ROR4 (0F 28/2A grp8 /0)
_put0f(0x28, "ROL4", EA, modrm=True, group=True)
_put0f(0x2A, "ROR4", EA, modrm=True, group=True)
# INS/EXT bit-field: reg-reg (0F 31/33), reg-imm4 (0F 39/3B)
_put0f(0x31, "INS reg,reg", EA, modrm=True)
_put0f(0x33, "EXT reg,reg", EA, modrm=True)
_put0f(0x39, "INS reg,imm4", EA, modrm=True, imm=1)
_put0f(0x3B, "EXT reg,imm4", EA, modrm=True, imm=1)
# BRKEM (0F FF ib): the accepted 8080-gap entry
_put0f(0xFF, "BRKEM imm8", BRKEM, imm=1)


def is_banned_0f(b2):
    """True iff the 0F second byte is BANNED (anything not whitelisted)."""
    return b2 not in F0_WHITELIST


# byte pairs that must NEVER appear (0F prefix + these) - the scrub authority.
# 0F 34 locks the chip; 0F 35-3F are unprobed; 0F E0/F0 are V33 BRKXA/RETXA.
HARD_BANNED_0F = frozenset({0x34}) | frozenset(range(0x35, 0x40)) | {0xE0, 0xF0}


# ---------------------------------------------------------------------------
# Static instruction-length decoder.
# ---------------------------------------------------------------------------
def _modrm_extra(buf, i):
    """disp bytes consumed by a modrm at buf[i] (the modrm byte itself not
    counted here). mod00/rm110 = disp16; mod01 = disp8; mod10 = disp16."""
    if i >= len(buf):
        return 0
    m = buf[i]
    mod, rm = m >> 6, m & 7
    if mod == 0:
        return 2 if rm == 6 else 0
    if mod == 1:
        return 1
    if mod == 2:
        return 2
    return 0


def ilen(buf, i):
    """Static length (in bytes) of the instruction at buf[i] over the legal
    1-byte + whitelisted-0F space, prefix stack included. Returns the total
    consumed length; a run off the end of buf is clamped to len(buf)-i.

    Not a validity checker - it length-decodes what a legal generator emits
    (banned forms never reach a live stream). Unknown/short input returns the
    consumed-so-far length so a caller can still advance."""
    n = len(buf)
    j = i
    # prefix stack
    while j < n and buf[j] in PREFIXES:
        j += 1
    if j >= n:
        return n - i
    op = buf[j]
    j += 1
    if op == 0x0F:                       # two-byte extension
        if j >= n:
            return n - i
        b2 = buf[j]
        j += 1
        info = F0_WHITELIST.get(b2)
        if info is None:                 # banned/unknown: 0F + byte (best effort)
            return min(j, n) - i
        if info.modrm:
            if j < n:
                j += 1 + _modrm_extra(buf, j)
        j += info.imm
        return min(j, n) - i
    info = TABLE.get(op)
    if info is None:
        return j - i
    if info.modrm:
        ext = None
        if j < n:
            ext = (buf[j] >> 3) & 7
            j += 1 + _modrm_extra(buf, j)
        # F6/F7 immediate is present only for /0 (TEST) and /1
        if info.imm_extdep:
            if ext in (0, 1):
                j += 2 if op == 0xF7 else 1
        else:
            j += info.imm
    else:
        j += info.imm
    j += info.rel
    if info.farptr:
        j += 4
    return min(j, n) - i


# ---------------------------------------------------------------------------
# Reachable-code safety scan (lint authority for the soup instruction stream).
# ---------------------------------------------------------------------------
_PORT_IMM_OPS = frozenset({0xE4, 0xE5, 0xE6, 0xE7})
_PORT_DX_OPS = frozenset({0xEC, 0xED, 0xEE, 0xEF, 0x6C, 0x6D, 0x6E, 0x6F})
FORBIDDEN_PORTS = frozenset({0xFC, 0xFE})   # done-marker / register-store forgery


def scan_code(buf, start=0, end=None):
    """Walk buf[start:end] as an instruction stream and return a list of
    (offset, reason) for BANNED content reachable as code: non-whitelisted 0F
    second bytes, banned group /reg extensions (FE /2-7, 8E /1, FF /7), and
    I/O to the forbidden 0xFC/0xFE ports (imm8 ports + a MOV DW,imm feeding a
    DX/string-I/O op). Used by fuzz_campaign lint on the soup code stream."""
    end = len(buf) if end is None else end
    hits = []
    i = start
    last_movdw = None
    while i < end:
        step = max(1, ilen(buf, i))
        j = i
        while j < end and buf[j] in PREFIXES:
            j += 1
        if j >= end:
            break
        op = buf[j]
        j += 1
        movdw_here = None
        if op == 0x0F:
            if j < end and is_banned_0f(buf[j]):
                hits.append((i, f"banned 0F {buf[j]:02x}"))
        else:
            info = TABLE.get(op)
            if info and info.group and info.modrm and j < end:
                ext = (buf[j] >> 3) & 7
                if ext in info.banned_ext:
                    hits.append((i, f"{op:02x} /{ext} banned ext"))
            if op in _PORT_IMM_OPS and j < end and buf[j] in FORBIDDEN_PORTS:
                hits.append((i, f"IN/OUT imm port {buf[j]:02x}"))
            if op in _PORT_DX_OPS and last_movdw in FORBIDDEN_PORTS:
                hits.append((i, f"DX/string I/O to port {last_movdw:02x}"))
            if op == 0xBA and j + 1 < end and buf[j + 1] == 0x00:  # MOV DW,imm16
                movdw_here = buf[j]
        last_movdw = movdw_here
        i += step
    return hits


def scan_raw_bytes(buf):
    """Post-scrub safety scan of a raw (data+code) buffer: return (offset,
    reason) for any residual chip-wedging byte - a banned 0F pair (0F 34 /
    0F 35-3F / 0F E0 / 0F F0) or a stray HALT(F4)/POLL(9B). ED and the BRKEM
    aliases (0F >= 0x40) are intentionally left in and never reported."""
    hits = []
    n = len(buf)
    pos = 0
    while True:
        i = buf.find(0x0F, pos) if isinstance(buf, (bytes, bytearray)) \
            else _find(buf, 0x0F, pos)
        if i < 0 or i >= n - 1:
            break
        if buf[i + 1] in HARD_BANNED_0F:
            hits.append((i, f"residual 0F {buf[i + 1]:02x}"))
        pos = i + 1
    for b, why in ((0xF4, "stray HALT F4"), (0x9B, "stray POLL 9B")):
        pos = 0
        while True:
            i = buf.find(b, pos) if isinstance(buf, (bytes, bytearray)) \
                else _find(buf, b, pos)
            if i < 0:
                break
            hits.append((i, why))
            pos = i + 1
    return hits


def _find(seq, val, start):
    for i in range(start, len(seq)):
        if seq[i] == val:
            return i
    return -1


# ---------------------------------------------------------------------------
# Selfcheck: cross-validate the table against the three authorities.
# ---------------------------------------------------------------------------
def _expand_first_byte(tok):
    """Concrete first-byte value(s) for an instructions.json encoding[0]
    token. Single-byte opcode fields only carry W / s (1 bit) or reg (3) /
    sreg (2) placeholders; returns [] when the token is not a determinate
    single byte."""
    t = tok.replace(" ", "")
    t = t.replace("sreg", "SS").replace("reg", "RRR")
    if len(t) != 8 or any(c in t for c in ("mod", "mem")):
        return []
    var = [k for k, c in enumerate(t) if c not in "01"]
    out = []
    for combo in range(1 << len(var)):
        bits = list(t)
        for bi, pos in enumerate(var):
            bits[pos] = str((combo >> bi) & 1)
        out.append(int("".join(bits), 2))
    return out


def selfcheck(verbose=False):
    """Return a list of error strings (empty = clean)."""
    errs = []

    # 1. full 1-byte coverage: every opcode has an Op, except the 0F prefix
    for c in range(256):
        if c == 0x0F:
            if c in TABLE:
                errs.append("0x0F must be the two-byte prefix, not a TABLE Op")
            continue
        if c not in TABLE:
            errs.append(f"opcode {c:02x} missing from TABLE")

    # 2. prefixes agree with fuzz_cov.PREFIX_BYTES (plus repnc/repc extension)
    if not (fuzz_cov.PREFIX_BYTES <= PREFIXES):
        errs.append(f"fuzz_cov.PREFIX_BYTES not subset of PREFIXES: "
                    f"{fuzz_cov.PREFIX_BYTES - PREFIXES}")
    if PREFIXES - fuzz_cov.PREFIX_BYTES != {0x64, 0x65}:
        errs.append(f"PREFIXES extension unexpected: "
                    f"{PREFIXES - fuzz_cov.PREFIX_BYTES}")

    # 3. fuzz_cov.GROUP_OPS -> group=True
    for c in fuzz_cov.GROUP_OPS:
        op = TABLE.get(c)
        if op is None or not op.group:
            errs.append(f"GROUP_OPS {c:02x} not marked group in TABLE")

    # 4. fuzz_cov.MODRM_OPS -> modrm=True
    for c in fuzz_cov.MODRM_OPS:
        op = TABLE.get(c)
        if op is None or not op.modrm:
            errs.append(f"MODRM_OPS {c:02x} not marked modrm in TABLE")

    # 5. fuzz_cov.F0_MODRM -> whitelisted & modrm=True
    for b2 in fuzz_cov.F0_MODRM:
        op = F0_WHITELIST.get(b2)
        if op is None or not op.modrm:
            errs.append(f"F0_MODRM {b2:02x} not whitelisted-with-modrm")

    # 6. required hard bans present. is_banned_0f is the SOUP whitelist gate;
    #    HARD_BANNED_0F is the RAW-scrub band (blankets 0x35-0x3F, incl. the
    #    two whitelisted INS/EXT-imm4 forms - raw simply never emits those).
    if 0x34 not in HARD_BANNED_0F or not is_banned_0f(0x34):
        errs.append("0F 34 not banned")
    for b2 in range(0x35, 0x40):
        if b2 not in HARD_BANNED_0F:
            errs.append(f"0F {b2:02x} not in the raw-scrub band")
        if b2 not in F0_WHITELIST and not is_banned_0f(b2):
            errs.append(f"0F {b2:02x} (unprobed) not soup-banned")
    for b2 in (0xE0, 0xF0):
        if b2 not in HARD_BANNED_0F or not is_banned_0f(b2):
            errs.append(f"0F {b2:02x} (BRKXA/RETXA) not banned")
    # every non-whitelisted 0F byte must be soup-banned (definitional guard)
    for b2 in range(256):
        if b2 not in F0_WHITELIST and not is_banned_0f(b2):
            errs.append(f"0F {b2:02x} not soup-banned despite non-whitelist")
    if TABLE[0xFE].banned_ext != frozenset({2, 3, 4, 5, 6, 7}):
        errs.append("FE /2-7 not banned")
    if TABLE[0x8E].banned_ext != frozenset({1}):
        errs.append("8E /1 (MOV CS) not banned")

    # 7. instructions.json: documented first bytes must exist & not be BANNED;
    #    documented modrm forms must be marked modrm.
    if FACTS.exists():
        recs = json.loads(FACTS.read_text())["instructions"]
        for r in recs:
            enc = r["encoding"]
            b0s = _expand_first_byte(enc[0])
            for b0 in b0s:
                if b0 == 0x0F:
                    continue
                op = TABLE.get(b0)
                if op is None:
                    errs.append(f"documented {enc[0]!r} ({r['nec_form']}) "
                                f"byte {b0:02x} absent from TABLE")
                    continue
                if op.policy == BANNED:
                    errs.append(f"documented {r['nec_form']} byte {b0:02x} "
                                f"marked BANNED")
                if len(enc) > 1 and "mod" in enc[1] and not op.modrm:
                    errs.append(f"documented modrm form {r['nec_form']} "
                                f"byte {b0:02x} not marked modrm")
    elif verbose:
        print(f"  (instructions.json absent at {FACTS} - skipped authority 7)")

    # 8. ilen sanity on hand-picked encodings (prefixes, modrm+disp, imm, 0F)
    for buf, want in _ILEN_CASES:
        got = ilen(bytes(buf), 0)
        if got != want:
            errs.append(f"ilen({bytes(buf).hex()}) = {got}, want {want}")

    if verbose:
        print(f"  TABLE: {len(TABLE)} one-byte ops; "
              f"F0_WHITELIST: {len(F0_WHITELIST)} forms; "
              f"{sum(1 for o in TABLE.values() if o.policy == BANNED)} "
              f"one-byte BANNED")
    return errs


# (bytes, expected length) - exercises every ilen branch
_ILEN_CASES = [
    ([0x90], 1),                                   # NOP
    ([0xB8, 0x34, 0x12], 3),                       # MOV AW,imm16
    ([0xB0, 0x7F], 2),                             # MOV AL,imm8
    ([0x05, 0x00, 0x10], 3),                       # ADD AW,imm16
    ([0x04, 0xFF], 2),                             # ADD AL,imm8
    ([0x00, 0xC1], 2),                             # ADD CL,AL (mod3)
    ([0x00, 0x06, 0x00, 0x20], 4),                 # ADD [disp16],AL
    ([0x01, 0x40, 0x10], 3),                       # ADD [BW+IX+disp8],AW
    ([0x8B, 0x80, 0x00, 0x20], 4),                 # MOV AW,[BW+IX+disp16]
    ([0x81, 0x06, 0x00, 0x20, 0x34, 0x12], 6),     # ADD [disp16],imm16
    ([0x83, 0xC0, 0x01], 3),                       # ADD AW,imm8sx
    ([0xF6, 0xC0, 0xFF], 3),                        # TEST AL,imm8 (F6/0)
    ([0xF7, 0xC0, 0x34, 0x12], 4),                 # TEST AW,imm16 (F7/0)
    ([0xF6, 0xD0], 2),                             # NOT AL (F6/2, no imm)
    ([0xF7, 0xF1], 2),                             # DIV CW (F7/6, no imm)
    ([0x26, 0x8B, 0x06, 0x00, 0x20], 5),           # ES: MOV AW,[disp16]
    ([0xF3, 0xA4], 2),                             # REP MOVSB
    ([0xF0, 0x00, 0xC1], 3),                        # LOCK ADD CL,AL
    ([0xEA, 0x00, 0x05, 0x00, 0x00], 5),           # JMP far
    ([0x9A, 0x81, 0x04, 0x00, 0x00], 5),           # CALL far
    ([0xCD, 0x20], 2),                             # INT 0x20
    ([0xC8, 0x10, 0x00, 0x02], 4),                 # PREPARE 16,2
    ([0xE8, 0x02, 0x00], 3),                       # CALL rel16
    ([0xEB, 0x10], 2),                             # JMP rel8
    ([0xA1, 0x00, 0x20], 3),                       # MOV AW,[moffs]
    ([0x0F, 0x10, 0xC0], 3),                       # TEST1 AL,CL
    ([0x0F, 0x18, 0xC0, 0x03], 4),                 # TEST1 AL,imm3
    ([0x0F, 0x20], 2),                             # ADD4S
    ([0x0F, 0x28, 0xC0], 3),                       # ROL4 AL
    ([0x0F, 0x31, 0xC8], 3),                       # INS
    ([0x0F, 0x39, 0xC0, 0x04], 4),                 # INS reg,imm4
    ([0x0F, 0xFF, 0x40], 3),                       # BRKEM 0x40
    ([0xC6, 0x06, 0x00, 0x20, 0x55], 5),           # MOV [disp16],imm8
    ([0xD1, 0xE0], 2),                             # SHL AW,1
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true",
                    help="cross-validate against the three authorities")
    ap.add_argument("--dump", action="store_true",
                    help="print the full policy table")
    a = ap.parse_args()
    if a.dump:
        for c in range(256):
            op = TABLE.get(c)
            if op:
                print(f"  {c:02x} {op.policy:<13} {op.mnem}")
        for b2 in sorted(F0_WHITELIST):
            op = F0_WHITELIST[b2]
            print(f"  0F{b2:02x} {op.policy:<13} {op.mnem}")
        return 0
    if a.selfcheck or True:
        errs = selfcheck(verbose=True)
        if errs:
            print(f"optable selfcheck: {len(errs)} ERROR(S)")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("optable selfcheck: 0 errors")
        return 0


if __name__ == "__main__":
    sys.exit(main())
