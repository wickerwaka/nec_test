#!/usr/bin/env python3
"""gen_seq - Mission S: random multi-instruction program generator for
chip-vs-core sequence fuzzing.

Programs are safety-constrained, not outcome-predicted: check_seq diffs
the full per-cycle trace of chip and core running the SAME image, so
the generator only guarantees that a program cannot leave its windows,
trap through an uninitialized IVT, self-modify, touch harness pages, or
run unbounded. Silicon supplies the truth for everything else.

v1 form set = the fully fitted families (ALU rm/r + acc-imm + rm-imm,
MOV, XCHG, INC/DEC/PUSH/POP r16, shifts by 1, MULU8, safe DIV, TEST,
Jcc/JMP forward, strings incl. REP with small CW, segment prefixes on
mem ops, NOP runs). Extend FORM_MENU as families turn green.

Excluded by design (v1): IN/OUT (TB iord parity unverified in bootimg
mode), sreg writes, POPF/POP PSW (random BRK), CALL/RET (stack pairing),
0F forms, HALT, self-modifying code.

Layout (all in the 64KB physical image, CS=DS=ES=SS=0):
  0x0000-0x03FF  IVT (untouched)
  0x0500-0x07FF  program + store stub (compose places the stub after)
  0x2000-0x2FFF  data window (prefilled with seeded random bytes)
  0x3E00-0x3FFE  stack window (SP starts mid-window)
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_LO, DATA_HI = 0x2000, 0x2F00
SP0 = 0x3F00
PC0 = 0x0500

REG16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]


def _mem_ea(rng):
    """mod=0 rm=6 direct address inside the data window."""
    return rng.randrange(DATA_LO, DATA_HI) & 0xFFFE | (rng.random() < 0.3)


def _data_word_ea(rng):
    """even direct address with >=4 bytes of headroom in the data window
    (for controlled word/dword setups: pointers, BOUND bounds)."""
    return rng.randrange(DATA_LO, DATA_HI - 4) & 0xFFFE


def _modrm_direct(reg, rng, ea=None):
    if ea is None:
        ea = _mem_ea(rng)
    return bytes([(reg << 3) | 6, ea & 0xFF, ea >> 8])


def _modrm_reg(reg, rm):
    return bytes([0xC0 | (reg << 3) | rm])


def _imm_biased(rng, bits):
    """Immediate value biased toward the interesting boundaries (0, 1, -1,
    sign bit, signed/unsigned max, byte carry edges) so ALU/shift/mul
    operands land on carry/overflow/sign transitions instead of only in the
    uniform-random interior. ~55% boundary, ~45% uniform."""
    if rng.random() < 0.55:
        if bits == 16:
            return rng.choice([0x0000, 0x0001, 0xFFFF, 0x8000, 0x7FFF,
                               0x8001, 0x7FFE, 0x00FF, 0x0100, 0x0080,
                               0x007F, 0xFF00, 0xFFFE, 0x0002, 0xFF80])
        return rng.choice([0x00, 0x01, 0xFF, 0x80, 0x7F, 0x81, 0x7E, 0x02,
                           0xFE, 0x0F, 0xF0])
    return rng.getrandbits(bits)


class Prog:
    def __init__(self, rng):
        self.rng = rng
        self.ins = []          # list of bytes objects (one per instruction)
        self.fixups = []       # (ins_index, target_ins_index) for disp8
        self.abs_fixups = []   # ins_index of a far JMP whose off word must
                               # be patched to the NEXT instruction's IP
        self.reg_ip_fixups = []  # (mov_index, upto_index): patch a B8+r MOV
                               # imm16 to the absolute IP of the boundary
                               # AFTER instruction upto_index-1 (near
                               # indirect CALL/JMP self-continuation target)
        self.noland = set()    # indices illegal as branch targets: landing
                               # here would skip a safe-gadget's setup
        self.ram_over = []     # (addr, bytes) controlled data-window bytes a
                               # gadget needs (e.g. a seg-0 far pointer, BOUND
                               # bounds) - applied over the random fill so we
                               # never need a MOV rm,imm (C6/C7) to set them

    def ram_set(self, addr, data):
        self.ram_over.append((addr, bytes(data)))

    def emit(self, b):
        self.ins.append(bytes(b))

    def emit_farjmp_next(self):
        """Far JMP to (0, next-instruction): a contained CS reload that
        continues the stream. Patched to an absolute IP in assemble()."""
        self.abs_fixups.append(len(self.ins))
        self.ins.append(bytes([0xEA, 0, 0, 0, 0]))

    def emit_atomic(self, instrs):
        """Emit a multi-instruction safe gadget (e.g. DIV or a string op).
        Only the first instruction is a legal branch target; landing after
        it would skip the setup that keeps the gadget trap-safe and
        windowed (skipping MOV CX,div -> divide error; skipping MOV SI/DI/
        CLD/MOV CX,cw -> REP with garbage count / pointer walks out of the
        data window). Both escape via the untouched IVT."""
        start = len(self.ins)
        for b in instrs:
            self.ins.append(bytes(b))
        for i in range(start + 1, len(self.ins)):
            self.noland.add(i)

    def branch(self, opc):
        """Forward branch to 1..4 instructions ahead (patched later)."""
        idx = len(self.ins)
        self.ins.append(bytes([opc, 0]))
        skip = self.rng.randrange(1, 5)
        self.fixups.append((idx, skip))

    def assemble(self):
        # patch forward displacements (target = boundary after skipping
        # `skip` following instructions; cap at program end). Snap the
        # target forward out of any safe-gadget interior so a branch can
        # never skip a gadget's setup instructions.
        sizes = [len(b) for b in self.ins]
        out = [bytearray(b) for b in self.ins]
        n = len(self.ins)
        for idx, skip in self.fixups:
            tgt = min(idx + 1 + skip, n)
            while tgt < n and tgt in self.noland:
                tgt += 1
            disp = sum(sizes[k] for k in range(idx + 1, tgt))
            if len(out[idx]) >= 3 and out[idx][0] == 0xE9:   # BR near rel16
                out[idx][1] = disp & 0xFF
                out[idx][2] = (disp >> 8) & 0xFF
            else:
                assert disp < 0x80
                out[idx][1] = disp
        # far JMP: absolute IP of the following instruction (CS=0, program
        # based at PC0). Falls to the store stub when it is the last instr.
        for idx in self.abs_fixups:
            off = (PC0 + sum(sizes[k] for k in range(0, idx + 1))) & 0xFFFF
            out[idx][1] = off & 0xFF
            out[idx][2] = off >> 8
            out[idx][3] = 0x00
            out[idx][4] = 0x00
        # near-indirect target: a B8+r MOV whose imm16 must equal the
        # absolute IP of the boundary after instruction (upto-1).
        for mov_idx, upto in self.reg_ip_fixups:
            off = (PC0 + sum(sizes[k] for k in range(0, upto))) & 0xFFFF
            out[mov_idx][1] = off & 0xFF
            out[mov_idx][2] = off >> 8
        return b"".join(bytes(b) for b in out)


NOSP = [0, 1, 2, 3, 5, 6, 7]     # never write SP (stack must stay windowed)


def _gen_alu_rr(p, rng):
    op = rng.randrange(8)
    w = rng.getrandbits(1)
    d = rng.getrandbits(1)
    reg, rm = rng.choice(NOSP), rng.choice(NOSP)
    p.emit([op * 8 + (2 * d) + w, 0xC0 | (reg << 3) | rm])
    return "alu_rr"


def _gen_alu_mem(p, rng):
    op = rng.randrange(8)
    w = rng.getrandbits(1)
    d = rng.getrandbits(1)
    reg = rng.randrange(8)
    pre = b""
    if rng.random() < 0.25:
        pre = bytes([rng.choice([0x26, 0x2E, 0x36, 0x3E])])
    p.emit(pre + bytes([op * 8 + (2 * d) + w]) + _modrm_direct(reg, rng))
    return "alu_mem"


def _gen_alu_imm(p, rng):
    op = rng.randrange(8)
    kind = rng.randrange(3)
    if kind == 0:            # acc,imm
        w = rng.getrandbits(1)
        imm = _imm_biased(rng, 16 if w else 8)
        p.emit(bytes([op * 8 + 4 + w]) +
               imm.to_bytes(2 if w else 1, "little"))
        return "alu_acc_imm"
    elif kind == 1:          # 80/81/83 reg
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g, 0xC0 | (op << 3) | rng.choice(NOSP)]) +
               _imm_biased(rng, 8 * n).to_bytes(n, "little"))
        return "alu_grp_imm_r"
    else:                    # 80/81/83 mem
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g]) + _modrm_direct(op, rng) +
               _imm_biased(rng, 8 * n).to_bytes(n, "little"))
        return "alu_grp_imm_m"


def _gen_mov(p, rng):
    kind = rng.randrange(6)
    if kind == 0:            # B8+r imm16
        p.emit(bytes([0xB8 + rng.choice(NOSP)]) +
               _imm_biased(rng, 16).to_bytes(2, "little"))
        return "mov_imm16"
    elif kind == 4:          # B0+r imm8 (MOV reg8, imm8) - re-enabled
        p.emit(bytes([0xB0 + rng.randrange(8)]) +
               bytes([_imm_biased(rng, 8)]))
        return "mov_imm8"
    elif kind == 5:          # C6/C7 /0 (MOV r/m, imm) - re-enabled
        w = rng.getrandbits(1)
        n = 2 if w else 1
        imm = _imm_biased(rng, 8 * n).to_bytes(n, "little")
        if rng.random() < 0.5:      # register destination (never SP)
            p.emit(bytes([0xC6 + w, 0xC0 | rng.choice(NOSP)]) + imm)
            return "mov_ri_r"
        p.emit(bytes([0xC6 + w]) + _modrm_direct(0, rng) + imm)
        return "mov_ri_m"
    elif kind == 1:          # mov r,r / r,m / m,r
        w = rng.getrandbits(1)
        d = rng.getrandbits(1)
        if rng.random() < 0.5:
            p.emit([0x88 + 2 * d + w,
                    0xC0 | (rng.choice(NOSP) << 3) | rng.choice(NOSP)])
            return "mov_rr"
        p.emit(bytes([0x88 + 2 * d + w]) +
               _modrm_direct(rng.randrange(8), rng))
        return "mov_rm"
    elif kind == 2:          # moffs
        w = rng.getrandbits(1)
        d = rng.getrandbits(1)
        ea = _mem_ea(rng)
        p.emit(bytes([0xA0 + 2 * d + w, ea & 0xFF, ea >> 8]))
        return "mov_moffs"
    else:                    # lea
        p.emit(bytes([0x8D]) + _modrm_direct(rng.choice(NOSP), rng))
        return "lea"


def _gen_incdec(p, rng):
    p.emit([rng.choice([0x40, 0x48]) + rng.randrange(8)])
    return "incdec_r16"


def _gen_pushpop(p, rng, state):
    if state["stackops"] >= 20:
        return _gen_incdec(p, rng)
    state["stackops"] += 1
    if rng.random() < 0.5:
        p.emit([0x50 + rng.randrange(8)])
        state["depth"] += 1
        return "push_r16"
    r = rng.randrange(8)
    if r == 4:                # POP SP: allowed (load wins law) but
        r = 0                 # keep SP inside the window - swap to AX
    p.emit([0x58 + r])
    state["depth"] -= 1
    return "pop_r16"


def _gen_xchg(p, rng):
    w = rng.getrandbits(1)
    p.emit([0x86 + w, 0xC0 | (rng.choice(NOSP) << 3) | rng.choice(NOSP)])
    return "xchg_rr"


def _gen_shift(p, rng):
    w = rng.getrandbits(1)
    p.emit([0xD0 + w, 0xC0 | (4 << 3) | rng.choice(NOSP)])
    return "shift_by1"


def _gen_mul(p, rng):
    p.emit([0xF6, 0xC0 | (4 << 3) | rng.randrange(4)])   # MULU8 reg
    return "mulu8_r"


def _gen_div_safe(p, rng):
    """Canned trap-safe DIVU16: DX=0, AX small, divisor nonzero. Atomic so
    a branch cannot land on the DIV while skipping its operand setup."""
    d = rng.randrange(0x100, 0xFFFF)
    p.emit_atomic([
        bytes([0xBA, 0x00, 0x00]),                          # MOV DX,0
        bytes([0xB8]) + rng.getrandbits(12).to_bytes(2, "little"),  # MOV AX
        bytes([0xB9]) + d.to_bytes(2, "little"),            # MOV CX,div
        [0xF7, 0xF1],                                       # DIV CX
    ])
    return "divu16_safe"


def _gen_test(p, rng):
    w = rng.getrandbits(1)
    p.emit([0x84 + w, 0xC0 | (rng.randrange(8) << 3) | rng.randrange(8)])
    return "test_rr"


def _gen_branch(p, rng):
    opc = rng.choice([0xEB, 0xE3] + [0x70 + c for c in range(16)])
    p.branch(opc)
    if opc == 0xEB:
        return "jmp_short"
    return "jcxz" if opc == 0xE3 else "jcc"


def _gen_string(p, rng):
    # window the pointers, bound the count, fix the direction. Atomic: a
    # branch must not land past the SI/DI/CLD (or MOV CX,cw) setup, which
    # would run the op / REP with garbage pointers or count and walk out of
    # the data window (STOSW into the program or IVT -> escape).
    si = rng.randrange(0x2400, 0x2800)
    di = rng.randrange(0x2900, 0x2D00)
    seq = [
        bytes([0xBE, si & 0xFF, si >> 8]),                # MOV SI
        bytes([0xBF, di & 0xFF, di >> 8]),                # MOV DI
        [0xFC] if rng.random() < 0.8 else [0xFD],         # CLD/STD
    ]
    op = rng.choice([0xA4, 0xA5, 0xAA, 0xAB, 0xAC, 0xAD])
    if rng.random() < 0.5:
        cw = rng.randrange(0, 4)
        seq.append(bytes([0xB9, cw, 0x00]))               # MOV CX,cw
        seq.append([0xF3, op])                            # REP op
        tag = "rep_string"
    else:
        seq.append([op])
        tag = "string_single"
    p.emit_atomic(seq)
    return tag


def _gen_nops(p, rng):
    for _ in range(rng.randrange(1, 4)):
        p.emit([0x90])
    return "nops"


#----------------------------------------------------------------------------
# staged extensions (Campaign 4 Mission E): enabled per-family via
# generate(exts=...) so each expansion can be re-gated independently.
#----------------------------------------------------------------------------

def _gen_callret(p, rng):
    """CALL near + RET near, fully contained:
        CALL sub  (rel16, +2 over the JMP)
        JMP after (executed on return; skips body+RET)
        sub: <body> RET
        after:
    Stack balanced +2/-2; all control flow forward; atomic (landing
    inside would call/ret with unbalanced stack)."""
    body = []
    for _ in range(rng.randrange(1, 3)):
        r = rng.randrange(8)
        body.append(bytes([rng.choice([0x40, 0x48]) + (0 if r == 4 else r)]))
    body_len = sum(len(b) for b in body)
    seq = [
        bytes([0xE8, 0x02, 0x00]),           # CALL +2 (to sub)
        bytes([0xEB, body_len + 1]),         # JMP after (over body+RET)
        *body,
        bytes([0xC3]),                       # RET
    ]
    p.emit_atomic(seq)
    return "callret_near"


def _gen_sregw(p, rng):
    """Segment-register write: read sreg into AX, write it back (value
    unchanged -> addressing preserved; SS write also exercises the
    interrupt-shadow path harmlessly). Atomic: landing on the write with
    arbitrary AX would wreck addressing."""
    sreg = rng.choice([0, 2, 3])   # ES, SS, DS (skip CS)
    p.emit_atomic([
        bytes([0x8C, 0xC0 | (sreg << 3)]),   # MOV AX,sreg
        bytes([0x8E, 0xC0 | (sreg << 3)]),   # MOV sreg,AX
    ])
    return "sreg_rw"


def _gen_pushf_popf(p, rng):
    """PUSH PSW / POP PSW pair (flags unchanged -> TF stays clear, DIR
    preserved; exercises the POP-PSW commit path). Atomic: a lone POP PSW
    from random stack data could set TF/DIR."""
    p.emit_atomic([bytes([0x9C]), bytes([0x9D])])
    return "pushf_popf"


#----------------------------------------------------------------------------
# Campaign 4 breadth expansion (priority 2): the remaining SAFE documented
# families. Each gadget is either intrinsically windowed or forces its own
# operand/pointer state so behaviour is contained regardless of the random
# register/RAM context. Forbidden encodings (0F 2nd byte >= 0x40 / BRKEM,
# 0F 34, 0F FF, HALT, 8080-mode, undocumented FE/7, INS/EXT mem-mod) are
# NEVER emitted. Grouped to match the roadmap (a)-(f).
#----------------------------------------------------------------------------

# --- group (a): the 0F extension set ---------------------------------------

def _gen_bitops(p, rng):
    """TEST1/CLR1/SET1/NOT1 (0F 10-1F), reg or direct-mem operand, bit
    index from CL (0F 10-17) or imm (0F 18-1F). The index is taken modulo
    the operand size, so writes never leave the operand -> contained."""
    i = rng.randrange(4)                 # test1/clr1/set1/not1
    w = rng.getrandbits(1)
    use_imm = rng.getrandbits(1)
    op = (0x18 if use_imm else 0x10) + 2 * i + w
    if rng.random() < 0.5:
        ins = bytes([0x0F, op]) + _modrm_reg(0, rng.choice(NOSP))
    else:
        ins = bytes([0x0F, op]) + _modrm_direct(0, rng)
    if use_imm:
        ins += bytes([rng.getrandbits(4 if w else 3)])
    p.emit(ins)
    return "bitop"


def _gen_rol4(p, rng):
    """ROL4/ROR4 (0F 28 / 0F 2A, grp8 /0): rotate a BCD nibble through AL;
    byte operand reg or direct-mem. Contained (single byte touched)."""
    op = rng.choice([0x28, 0x2A])
    if rng.random() < 0.5:
        ins = bytes([0x0F, op]) + _modrm_reg(0, rng.randrange(8))
    else:
        ins = bytes([0x0F, op]) + _modrm_direct(0, rng)
    p.emit(ins)
    return "rol4"


def _gen_bcd4s(p, rng):
    """ADD4S/SUB4S/CMP4S (0F 20/22/26). BCD string add/sub/cmp over CL/2
    bytes at DS0:IX and DS1:IY. Force IX/IY into the data window and CL to
    1..6 (CL=0 underflows into a ~256-digit runaway). Atomic."""
    op = rng.choice([0x20, 0x22, 0x26])
    ix = rng.randrange(0x2400, 0x2800)
    iy = rng.randrange(0x2900, 0x2D00)
    p.emit_atomic([
        bytes([0xBE, ix & 0xFF, ix >> 8]),          # MOV IX(SI), window
        bytes([0xBF, iy & 0xFF, iy >> 8]),          # MOV IY(DI), window
        bytes([0xB9, rng.randrange(1, 7), 0x00]),   # MOV CW, 1..6 (CL=count)
        bytes([0x0F, op]),                          # 4S op
    ])
    return "bcd4s"


def _gen_insext(p, rng):
    """INS/EXT bit-field (0F 31/33 reg-form, 0F 39/3B imm4-form). ONLY the
    reg forms (mem-mod is parked in the core). Offset src = AL, length src =
    CL (never AH - AH-offset with len<16 burns 256*len cycles); set the low
    bytes via the 16-bit MOV imm (B8/B9), offset 0..7 and length 1..8,
    target pointer windowed. Atomic."""
    ins_op = rng.random() < 0.5           # INS vs EXT
    use_imm = rng.random() < 0.5
    setup = [bytes([0xB8, rng.randrange(0, 8), 0x00])]  # MOV AW (AL=offset)
    if use_imm:
        modrm = 0xC0 | 0                  # grp8 /0, rm=AL
        core = bytes([0x0F, 0x39 if ins_op else 0x3B, modrm,
                      rng.randrange(1, 9)])
    else:
        setup.append(bytes([0xB9, rng.randrange(1, 9), 0x00]))  # MOV CW(CL=len)
        modrm = 0xC0 | (1 << 3) | 0       # reg=CL(len), rm=AL(offset)
        core = bytes([0x0F, 0x31 if ins_op else 0x33, modrm])
    if ins_op:                            # INS writes field at DS1:IY
        iy = rng.randrange(0x2900, 0x2D00)
        setup.append(bytes([0xBF, iy & 0xFF, iy >> 8]))
    else:                                 # EXT reads field at DS0:IX
        ix = rng.randrange(0x2400, 0x2800)
        setup.append(bytes([0xBE, ix & 0xFF, ix >> 8]))
    p.emit_atomic(setup + [core])
    return "insext"


# --- group (b): BCD/adjust + CVT -------------------------------------------

def _gen_adjust(p, rng):
    """DAA/DAS/AAA/AAS (27/2F/37/3F), AAM/AAD (D4/D5 imm base, nonzero -
    base 0 is a divide trap), CBW/CWD (98/99). All accumulator-only."""
    op = rng.choice([0x27, 0x2F, 0x37, 0x3F, 0x98, 0x99, 0xD4, 0xD5])
    if op in (0xD4, 0xD5):
        p.emit(bytes([op, rng.randrange(1, 256)]))
    else:
        p.emit(bytes([op]))
    return "adjust"


# --- group (c): LDS/LES/XLAT, multiply, shift/rotate -----------------------

def _gen_ldsxlat(p, rng):
    """XLAT (D7, read-only) or LDS/LES (C5/C4). The far-pointer load reads
    a controlled {offset, seg=0} word pair from the data window so the
    loaded segment stays 0 and addressing is preserved. Atomic."""
    if rng.random() < 0.4:
        p.emit(bytes([0xD7]))             # XLAT AL,[BW+AL] - read only
        return "xlat"
    op = rng.choice([0xC4, 0xC5])         # LES / LDS
    ea = _data_word_ea(rng)
    off = rng.getrandbits(16)
    # inject the {offset, seg=0} far pointer via the data window (no C6/C7);
    # loading seg=0 keeps DS/ES at 0 so addressing is preserved.
    p.ram_set(ea, [off & 0xFF, off >> 8, 0x00, 0x00])
    p.emit(bytes([op]) + _modrm_direct(rng.choice(NOSP), rng, ea))  # LDS/LES
    return "ldsles"


def _gen_muls(p, rng):
    """Full multiply family: MULU/MUL r/m8 & r/m16 (F6/F7 /4,/5), and the
    3-operand IMUL reg16,rm16,imm8/imm16 (6B/69). Reg or direct-mem."""
    kind = rng.randrange(4)
    if kind == 0:                         # F6/F7 /4 MULU or /5 MUL, reg
        w = rng.getrandbits(1)
        p.emit(bytes([0xF6 + w]) + _modrm_reg(rng.choice([4, 5]),
                                              rng.choice(NOSP)))
    elif kind == 1:                       # F6/F7 /4-5 mem
        w = rng.getrandbits(1)
        p.emit(bytes([0xF6 + w]) + _modrm_direct(rng.choice([4, 5]), rng))
    elif kind == 2:                       # 6B IMUL reg16,rm16,imm8
        reg = rng.choice(NOSP)
        if rng.random() < 0.5:
            p.emit(bytes([0x6B]) + _modrm_reg(reg, rng.choice(NOSP)) +
                   bytes([rng.getrandbits(8)]))
        else:
            p.emit(bytes([0x6B]) + _modrm_direct(reg, rng) +
                   bytes([rng.getrandbits(8)]))
    else:                                 # 69 IMUL reg16,rm16,imm16
        reg = rng.choice(NOSP)
        imm = rng.getrandbits(16).to_bytes(2, "little")
        if rng.random() < 0.5:
            p.emit(bytes([0x69]) + _modrm_reg(reg, rng.choice(NOSP)) + imm)
        else:
            p.emit(bytes([0x69]) + _modrm_direct(reg, rng) + imm)
    return "mul"


def _gen_shifts(p, rng):
    """Full shift/rotate (all 8 sub-ops ROL..SAR): by 1 (D0/D1), by CL
    (D2/D3, CL forced to 0..31), by imm8 (C0/C1, 0..31). Reg or mem."""
    sub = rng.randrange(8)
    w = rng.getrandbits(1)
    mode = rng.randrange(3)
    if mode == 0:                         # by 1
        opc = 0xD0 + w
        if rng.random() < 0.5:
            p.emit(bytes([opc]) + _modrm_reg(sub, rng.choice(NOSP)))
        else:
            p.emit(bytes([opc]) + _modrm_direct(sub, rng))
        return "shift_by1_full"
    if mode == 1:                         # by CL (bounded)
        opc = 0xD2 + w
        tgt = (bytes([opc]) + _modrm_reg(sub, rng.choice(NOSP))
               if rng.random() < 0.5
               else bytes([opc]) + _modrm_direct(sub, rng))
        # MOV CW imm16 sets CL to the (bounded) count (avoids MOV reg8,imm8)
        p.emit_atomic([bytes([0xB9, rng.randrange(0, 32), 0x00]), tgt])
        return "shift_cl"
    opc = 0xC0 + w                        # by imm8 (small)
    imm = rng.randrange(0, 32)
    if rng.random() < 0.5:
        p.emit(bytes([opc]) + _modrm_reg(sub, rng.choice(NOSP)) + bytes([imm]))
    else:
        p.emit(bytes([opc]) + _modrm_direct(sub, rng) + bytes([imm]))
    return "shift_imm"


# --- group (d): PUSH/POP mem + sreg, PREPARE/DISPOSE, CHKIND ----------------

def _gen_pushpopm(p, rng, state):
    """PUSH mem (FF/6), POP mem (8F/0 mod0 direct - NOT the mod3 register
    alias), or a balanced PUSH sreg / POP sreg pair (value preserved so
    addressing is unchanged; POP SS exercises the interrupt shadow)."""
    if state["stackops"] >= 20:
        return _gen_nops(p, rng)
    k = rng.randrange(3)
    if k == 0:
        state["stackops"] += 1
        p.emit(bytes([0xFF]) + _modrm_direct(6, rng))    # PUSH word[ea]
        state["depth"] += 1
        return "push_mem"
    if k == 1:
        state["stackops"] += 1
        p.emit(bytes([0x8F]) + _modrm_direct(0, rng))    # POP word[ea]
        state["depth"] -= 1
        return "pop_mem"
    sreg = rng.choice([0, 2, 3])                          # ES, SS, DS
    p.emit_atomic([bytes([0x06 | (sreg << 3)]),          # PUSH sreg
                   bytes([0x07 | (sreg << 3)])])         # POP sreg
    return "pushpop_sreg"


def _gen_prepare(p, rng):
    """PREPARE (C8 iw,ib, ENTER) + optional DISPOSE (C9, LEAVE), bounded
    frame size and level, BP forced into the stack window. SP is
    re-windowed afterwards so any residual (level>0 ENTER without a
    matching LEAVE) can never walk the stack out. Atomic."""
    size = rng.randrange(0, 0x20) & 0xFFFE
    level = rng.randrange(0, 4)
    seq = [bytes([0xBD, 0xE0, 0x3F]),                    # MOV BP, 0x3FE0
           bytes([0xC8, size & 0xFF, size >> 8, level])]  # PREPARE size,lvl
    if rng.random() < 0.5:
        seq.append(bytes([0xC9]))                        # DISPOSE
    seq.append(bytes([0xBC, 0x00, 0x3F]))                # MOV SP, 0x3F00
    p.emit_atomic(seq)
    return "prepare"


def _gen_bound(p, rng):
    """CHKIND/BOUND (62 /r): check reg16 against [ea]..[ea+2]. Bounds are
    forced to the full signed range (0x8000..0x7FFF) so the index is always
    in range and never traps to INT 5. Atomic."""
    ea = _data_word_ea(rng)
    reg = rng.choice(NOSP)
    # inject full signed-range bounds via the data window (no C6/C7) so the
    # index is always in range and BOUND never traps to INT 5.
    p.ram_set(ea, [0x00, 0x80, 0xFF, 0x7F])            # lo=0x8000 hi=0x7FFF
    p.emit(bytes([0x62, (reg << 3) | 0x06, ea & 0xFF, ea >> 8]))  # BOUND
    return "bound"


# --- group (e): far transfers + software interrupts + IRET -----------------
# These need a composed IVT + handler so delivery returns cleanly. The
# handler is a bare IRET (software INT return) followed by a RETF (far CALL
# return); every used vector points at it. generate() injects both when a
# far/int family is enabled. Priority 3 (interrupt injection) reuses this.

HANDLER_AT = 0x0480                  # below the program (PC0=0x0500)
SWINT_VEC = 0x20                     # software INTn vector
FAR_INT_EXTS = ("farcall", "swint", "farjmp")


HW_INT_VEC = 0xFF                   # CFG default INT-pin vector
NMI_VEC = 2                         # NMI IVT slot


def far_int_support():
    """(ivt dict, handler ram bytes). All exercised vectors -> the bare
    IRET handler (software INT3/INTO/INTn AND the injected hardware INT
    (0xFF) / NMI (2) pins). RETF stub follows for far CALL."""
    handler = [(HANDLER_AT, 0xCF),          # IRET
               (HANDLER_AT + 1, 0xCB)]      # RETF
    ivt = {n: (0, HANDLER_AT)
           for n in (3, 4, SWINT_VEC, NMI_VEC, HW_INT_VEC)}
    return ivt, handler


def _gen_farcall(p, rng):
    """far CALL (9A) to the RETF stub -> returns after the call, stack
    balanced (+4/-4)."""
    off = HANDLER_AT + 1
    p.emit(bytes([0x9A, off & 0xFF, off >> 8, 0x00, 0x00]))
    return "far_call"


def _gen_swint(p, rng):
    """software interrupt: INT3 (CC -> vec 3), INTn (CD ib -> SWINT_VEC),
    or INTO (CE -> vec 4 iff OF, else a no-op). Handler IRETs, so each
    returns to the following instruction; stack net-zero."""
    k = rng.randrange(3)
    if k == 0:
        p.emit(bytes([0xCC]))
        return "int3"
    if k == 1:
        p.emit(bytes([0xCD, SWINT_VEC]))
        return "intn"
    p.emit(bytes([0xCE]))
    return "into"


def _gen_farjmp(p, rng):
    """far JMP (EA) to (0, next-instruction): a contained CS reload that
    continues the stream (target patched in assemble)."""
    p.emit_farjmp_next()
    return "far_jmp"


# --- group (f): loop family ------------------------------------------------

def _gen_loop(p, rng):
    """JCXZ (E3, forward like a Jcc) or a bounded backward LOOP/LOOPE/
    LOOPNE (E2/E1/E0): CX forced to 1..4, a tiny INC/DEC body, backward
    disp computed within the gadget. Atomic (interior is no-land)."""
    if rng.random() < 0.3:
        p.branch(0xE3)                       # JCXZ forward
        return "jcxz"
    op = rng.choice([0xE0, 0xE1, 0xE2])
    body = []
    for _ in range(rng.randrange(1, 3)):
        r = rng.randrange(8)
        body.append(bytes([rng.choice([0x40, 0x48]) + (0 if r == 4 else r)]))
    body_len = sum(len(b) for b in body)
    disp = (-(body_len + 2)) & 0xFF          # back to body start
    p.emit_atomic([bytes([0xB9, rng.randrange(1, 5), 0x00])] + body +
                  [bytes([op, disp])])
    return "loop"


# ---------------------------------------------------------------------------
# Campaign 5 breadth: addressing-mode coverage + the remaining safe forms.
# The generator previously emitted ONLY mod0/rm6 (direct) and mod3 (register)
# EAs; the whole register-indirect / based / indexed / disp8 / disp16 /
# BP-relative (SS-default) addressing space was unexercised. _windowed_ea
# builds any (mod,rm,disp) form and forces the computed effective address to
# a chosen in-window target by pre-loading the base/index registers, so
# writes stay contained regardless of the random register context. Reads may
# also be aimed at offset 0xFFFF to exercise the segment-wrap split access.
# ---------------------------------------------------------------------------

EA_LO, EA_HI = 0x2100, 0x2E00      # write-safe EA target band (word headroom)

# (base_reg, index_reg) in REG16 numbering for mod!=0; rm6 special-cased
_RM_BASEIDX = {0: (3, 6), 1: (3, 7), 2: (5, 6), 3: (5, 7),
               4: (None, 6), 5: (None, 7), 6: (5, None), 7: (3, None)}


def _pick_target(rng, write, straddle_ok):
    """EA target: normally in the data window (~40% odd, for odd-alignment
    timing); for reads, occasionally 0xFFFF so a word access wraps to offset
    0 of the segment (the fz494 split-access path - never for a write, which
    would corrupt the IVT at 0x0000)."""
    if straddle_ok and not write and rng.random() < 0.12:
        return 0xFFFF
    t = rng.randrange(EA_LO, EA_HI)
    return (t | 1) if rng.random() < 0.4 else (t & 0xFFFE)


def _windowed_ea(rng, reg_field, write, straddle_ok=True):
    """(setup_instrs, ea_bytes) for a random (mod,rm,disp) EA forced to a
    contained target. setup_instrs = MOV imm16 loading the base/index regs;
    ea_bytes = modrm + disp. EA = (base+index+disp) mod 2^16 == target."""
    mod = rng.randrange(3)
    rm = rng.randrange(8)
    t = _pick_target(rng, write, straddle_ok)
    if mod == 0 and rm == 6:           # direct disp16 (no base/index regs)
        return [], bytes([(reg_field << 3) | 6, t & 0xFF, t >> 8])
    if rm == 6:                        # mod1/2 rm6 => [BP+disp], SS default
        base, index = 5, None
    else:
        base, index = _RM_BASEIDX[rm]
    if mod == 0:
        disp, dispb = 0, b""
    elif mod == 1:
        disp = rng.randrange(-0x20, 0x20)
        dispb = bytes([disp & 0xFF])
    else:
        disp = rng.randrange(0, 0x10000)
        dispb = bytes([disp & 0xFF, (disp >> 8) & 0xFF])
    regs = [r for r in (base, index) if r is not None]
    setup, acc = [], 0
    for r in regs[:-1]:
        v = rng.randrange(0, 0x40)
        setup.append(bytes([0xB8 + r]) + v.to_bytes(2, "little"))
        acc += v
    val = (t - disp - acc) & 0xFFFF
    setup.append(bytes([0xB8 + regs[-1]]) + val.to_bytes(2, "little"))
    return setup, bytes([(mod << 6) | (reg_field << 3) | rm]) + dispb


def _gen_ea_rich(p, rng):
    """A memory-operand instruction using the full mod/rm/disp addressing
    space (register-indirect, based, indexed, BP-relative SS-default,
    disp8/disp16, odd alignment, segment-wrap reads), optionally under a
    stack of 0-3 segment-override prefixes. Atomic: base/index setup first."""
    npfx = rng.choices([0, 1, 2, 3], weights=[58, 30, 8, 4])[0]
    seg = b"".join(bytes([rng.choice([0x26, 0x2E, 0x36, 0x3E])])
                   for _ in range(npfx))
    kind = rng.randrange(8)
    if kind in (0, 1):                 # ALU rm,r (d=0 RMW) or r,rm (d=1 read)
        op, w, d = rng.randrange(8), rng.getrandbits(1), kind
        setup, ea = _windowed_ea(rng, rng.choice(NOSP),
                                 write=(d == 0 and op != 7))
        core = bytes([op * 8 + 2 * d + w]) + ea
    elif kind == 2:                    # MOV mem,reg / reg,mem
        w, d = rng.getrandbits(1), rng.getrandbits(1)
        setup, ea = _windowed_ea(rng, rng.choice(NOSP), write=(d == 0))
        core = bytes([0x88 + 2 * d + w]) + ea
    elif kind == 3:                    # LEA (address calc, no memory access)
        setup, ea = _windowed_ea(rng, rng.choice(NOSP), False)
        core = bytes([0x8D]) + ea
    elif kind == 4:                    # TEST mem,reg (read only)
        w = rng.getrandbits(1)
        setup, ea = _windowed_ea(rng, rng.randrange(8), False)
        core = bytes([0x84 + w]) + ea
    elif kind == 5:                    # XCHG reg,mem (RMW write)
        w = rng.getrandbits(1)
        setup, ea = _windowed_ea(rng, rng.choice(NOSP), True)
        core = bytes([0x86 + w]) + ea
    elif kind == 6:                    # shift/rotate mem by 1 (D0/D1)
        w, sub = rng.getrandbits(1), rng.randrange(8)
        setup, ea = _windowed_ea(rng, sub, True)
        core = bytes([0xD0 + w]) + ea
    else:                              # ALU grp imm -> mem (80/81/83)
        op = rng.randrange(8)
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        setup, ea = _windowed_ea(rng, op, write=(op != 7))
        core = bytes([g]) + ea + _imm_biased(rng, 8 * n).to_bytes(n, "little")
    p.emit_atomic(setup + [seg + core])
    return "ea_rich"


def _gen_unary(p, rng):
    """NOT / NEG (F6/F7 /2,/3), reg or windowed mem (RMW write)."""
    w, ext = rng.getrandbits(1), rng.choice([2, 3])
    if rng.random() < 0.5:
        p.emit(bytes([0xF6 + w]) + _modrm_reg(ext, rng.choice(NOSP)))
    else:
        setup, ea = _windowed_ea(rng, ext, True)
        p.emit_atomic(setup + [bytes([0xF6 + w]) + ea])
    return "unary"


def _gen_incdec_ext(p, rng):
    """INC/DEC reg8 (FE /0,/1) or INC/DEC r/m in memory (FE/FF /0,/1)."""
    ext = rng.getrandbits(1)
    if rng.random() < 0.5:
        p.emit(bytes([0xFE, 0xC0 | (ext << 3) | rng.randrange(8)]))
    else:
        w = rng.getrandbits(1)
        setup, ea = _windowed_ea(rng, ext, True)
        p.emit_atomic(setup + [bytes([0xFE + w]) + ea])
    return "incdec_ext"


def _gen_test_imm(p, rng):
    """TEST acc,imm (A8/A9) or TEST r/m,imm (F6/F7 /0), reg or mem. Read
    only - never writes (mem EA still windowed for coverage fidelity)."""
    k, w = rng.randrange(3), rng.getrandbits(1)
    n = 2 if w else 1
    imm = _imm_biased(rng, 8 * n).to_bytes(n, "little")
    if k == 0:
        p.emit(bytes([0xA8 + w]) + imm)
    elif k == 1:
        p.emit(bytes([0xF6 + w]) + _modrm_reg(0, rng.randrange(8)) + imm)
    else:
        setup, ea = _windowed_ea(rng, 0, False)
        p.emit_atomic(setup + [bytes([0xF6 + w]) + ea + imm])
    return "test_imm"


def _gen_xchg_acc(p, rng):
    """XCHG AW,reg16 (single-byte 90+r; 91-97, never SP=94)."""
    p.emit([0x90 + rng.choice([1, 2, 3, 5, 6, 7])])
    return "xchg_acc"


def _gen_pushimm(p, rng, state):
    """PUSH imm8 (6A, sign-extended) / PUSH imm16 (68). Grows the stack;
    tracked against the shared stackops cap so SP stays windowed."""
    if state["stackops"] >= 20:
        return _gen_nops(p, rng)
    state["stackops"] += 1
    state["depth"] += 1
    if rng.random() < 0.5:
        p.emit(bytes([0x6A, _imm_biased(rng, 8)]))
    else:
        p.emit(bytes([0x68]) + _imm_biased(rng, 16).to_bytes(2, "little"))
    return "push_imm"


def _gen_pushapopa(p, rng):
    """PUSH R (60) then POP R (61): all-register save/restore, net stack
    zero, registers preserved. Atomic (SP is -16 only between the pair)."""
    p.emit_atomic([bytes([0x60]), bytes([0x61])])
    return "pushapopa"


def _gen_flagops(p, rng):
    """Single-byte flag ops: CMC (F5), CLC (F8), STC (F9), DI (FA), EI (FB),
    SAHF=MOV PSW,AH (9E), LAHF=MOV AH,PSW (9F). IE toggling is inert with no
    interrupt injection; SAHF cannot set TF (not in the loadable byte)."""
    p.emit([rng.choice([0xF5, 0xF8, 0xF9, 0xFA, 0xFB, 0x9E, 0x9F])])
    return "flagops"


def _gen_brnear(p, rng):
    """BR near (E9 rel16), forward 1..4 instructions - the 16-bit-disp
    sibling of the short jump. Patched via the forward-branch fixup."""
    idx = len(p.ins)
    p.ins.append(bytes([0xE9, 0, 0]))
    p.fixups.append((idx, rng.randrange(1, 5)))
    return "br_near"


def _gen_inout(p, rng):
    """IN/OUT family. imm8-port (E4/E5 IN, E6/E7 OUT) or DX-port (EC IN AL,
    EE/EF OUT). Ports kept in a harness-safe even band (never 0xFC done /
    0xFE regs); 0xED (=IN AX,DX, the 8080 CALLN/RETEM lead byte) is never
    emitted, so no accidental 8080-mode escape can form."""
    port = rng.randrange(0x08, 0xF0) & 0xFE
    k = rng.randrange(4)
    if k == 0:                         # IN acc,imm8
        p.emit(bytes([0xE4 + rng.getrandbits(1), port]))
    elif k == 1:                       # OUT imm8,acc
        p.emit(bytes([0xE6 + rng.getrandbits(1), port]))
    elif k == 2:                       # IN AL,DX (byte; skip ED)
        p.emit_atomic([bytes([0xBA]) + port.to_bytes(2, "little"),
                       bytes([0xEC])])
    else:                              # OUT DX,acc
        p.emit_atomic([bytes([0xBA]) + port.to_bytes(2, "little"),
                       bytes([0xEE + rng.getrandbits(1)])])
    return "inout"


def _gen_sregmem(p, rng):
    """MOV mem16,sreg (8C, store a segment reg to windowed memory) or MOV
    sreg,mem16 (8E) reading a segment from an injected ZERO word (loaded
    segment stays 0 so addressing is preserved). Atomic."""
    sreg = rng.choice([0, 2, 3])       # ES, SS, DS (skip CS)
    if rng.random() < 0.5:
        setup, ea = _windowed_ea(rng, sreg, True)
        p.emit_atomic(setup + [bytes([0x8C]) + ea])
    else:
        ea = _data_word_ea(rng)
        p.ram_set(ea, [0x00, 0x00])
        p.emit(bytes([0x8E]) + _modrm_direct(sreg, rng, ea))
    return "sregmem"


def _gen_divbound(p, rng):
    """Division at the quotient boundary WITHOUT tripping the divide trap:
    unsigned max quotient 0xFF (byte) / 0xFFFF (word) or a small signed
    divide. Operands forced so DX:AX / divisor stays representable. Atomic."""
    w = rng.getrandbits(1)
    signed = rng.random() < 0.4
    ext = 7 if signed else 6
    d = rng.randrange(2, 0x80)
    if not signed:
        if w == 0:
            q = rng.choice([0xFF, 0xFE, rng.randrange(0, 0x100)])
            val = (q * d + rng.randrange(0, d)) & 0xFFFF
        else:
            q = rng.choice([0xFFFF, 0xFFFE, rng.randrange(0, 0x10000)])
            val = q * d + rng.randrange(0, d)
    else:
        q = rng.randrange(-0x40, 0x40)
        r = rng.randrange(0, d)
        val = (q * d + (r if q >= 0 else -r)) & 0xFFFFFFFF
    setup = [bytes([0xB8]) + (val & 0xFFFF).to_bytes(2, "little")]
    if w:
        setup.append(bytes([0xBA]) + ((val >> 16) & 0xFFFF).to_bytes(2, "little"))
    setup.append(bytes([0xB9]) + d.to_bytes(2, "little"))    # MOV CX,divisor
    setup.append(bytes([0xF6 + w, 0xC0 | (ext << 3) | 1]))   # F6/F7 /ext, CX
    p.emit_atomic(setup)
    return "divbound"


def _gen_indirect(p, rng):
    """Near indirect CALL (FF /2) / JMP (FF /4) through a register preloaded
    with the continuation IP (patched at assemble). Contained: JMP
    self-continues to the next instruction; CALL enters a RET stub and
    returns (stack balanced +2/-2). Atomic."""
    reg = rng.choice([0, 1, 2, 3])     # AW/CW/DW/BW hold the target pointer
    start = len(p.ins)
    if rng.random() < 0.5:             # JMP reg -> next instruction
        p.ins.append(bytes([0xB8 + reg, 0, 0]))              # MOV reg,next
        p.ins.append(bytes([0xFF, 0xC0 | (4 << 3) | reg]))   # JMP reg (near)
        p.noland.add(start + 1)
        p.reg_ip_fixups.append((start, start + 2))
        return "indirect"
    body = [bytes([rng.choice([0x40, 0x48]) + rng.choice(NOSP)])
            for _ in range(rng.randrange(1, 3))]
    body_len = sum(len(b) for b in body)
    p.ins.append(bytes([0xB8 + reg, 0, 0]))                  # MOV reg,sub
    p.ins.append(bytes([0xFF, 0xC0 | (2 << 3) | reg]))       # CALL reg (near)
    p.ins.append(bytes([0xEB, body_len + 1]))                # JMP after
    sub_i = len(p.ins)
    for b in body:
        p.ins.append(b)
    p.ins.append(bytes([0xC3]))                              # RET
    for i in range(start + 1, len(p.ins)):
        p.noland.add(i)
    p.reg_ip_fixups.append((start, sub_i))
    return "indirect"


MENU = [(_gen_alu_rr, 14), (_gen_alu_mem, 12), (_gen_alu_imm, 10),
        (_gen_mov, 16), (_gen_incdec, 6), (_gen_xchg, 4),
        (_gen_shift, 5), (_gen_mul, 3), (_gen_div_safe, 2),
        (_gen_test, 4), (_gen_branch, 8), (_gen_string, 5),
        (_gen_nops, 6)]
MENU_STACK_W = 6

EXT_MENU = {
    "callret":  (_gen_callret, 5, ["callret_near"]),
    "sregw":    (_gen_sregw, 4, ["sreg_rw"]),
    "popf":     (_gen_pushf_popf, 4, ["pushf_popf"]),
    # group (a): 0F extension set
    "bitops":   (_gen_bitops, 6, ["bitop"]),
    "rol4":     (_gen_rol4, 3, ["rol4"]),
    "bcd4s":    (_gen_bcd4s, 3, ["bcd4s"]),
    "insext":   (_gen_insext, 3, ["insext"]),
    # group (b): BCD/adjust + CVT
    "adjust":   (_gen_adjust, 5, ["adjust"]),
    # group (c): LDS/LES/XLAT, multiply, shift/rotate
    "ldsxlat":  (_gen_ldsxlat, 4, ["xlat", "ldsles"]),
    "muls":     (_gen_muls, 4, ["mul"]),
    "shifts":   (_gen_shifts, 6, ["shift_by1_full", "shift_cl",
                                  "shift_imm"]),
    # group (d): PUSH/POP mem + sreg, PREPARE/DISPOSE, CHKIND
    "pushpopm": (_gen_pushpopm, 5, ["push_mem", "pop_mem",
                                    "pushpop_sreg"]),
    "prepare":  (_gen_prepare, 3, ["prepare"]),
    "bound":    (_gen_bound, 3, ["bound"]),
    # group (e): far transfers + software INT + IRET (need IVT + handler)
    "farcall":  (_gen_farcall, 4, ["far_call"]),
    "swint":    (_gen_swint, 4, ["int3", "intn", "into"]),
    "farjmp":   (_gen_farjmp, 3, ["far_jmp"]),
    # group (f): loop family
    "loop":     (_gen_loop, 5, ["jcxz", "loop"]),
    # Campaign 5 breadth: addressing modes + the remaining safe forms
    "earich":   (_gen_ea_rich, 16, ["ea_rich"]),
    "unary":    (_gen_unary, 5, ["unary"]),
    "incdec8":  (_gen_incdec_ext, 5, ["incdec_ext"]),
    "testimm":  (_gen_test_imm, 4, ["test_imm"]),
    "xchgacc":  (_gen_xchg_acc, 3, ["xchg_acc"]),
    "pushimm":  (_gen_pushimm, 4, ["push_imm"]),
    "pushapopa": (_gen_pushapopa, 3, ["pushapopa"]),
    "flagops":  (_gen_flagops, 4, ["flagops"]),
    "brnear":   (_gen_brnear, 4, ["br_near"]),
    "inout":    (_gen_inout, 5, ["inout"]),
    "sregmem":  (_gen_sregmem, 4, ["sregmem"]),
    "divbound": (_gen_divbound, 3, ["divbound"]),
    "indirect": (_gen_indirect, 4, ["indirect"]),
}
STATE_EXTS = ("pushpopm", "pushimm")   # exts whose gen takes shared state


def form_universe(exts=None):
    """All form tags the generator can emit (base menu + given exts, or
    ALL exts when exts is None). Lets the coverage report show families
    that have never been exercised."""
    base = ["alu_rr", "alu_mem", "alu_acc_imm", "alu_grp_imm_r",
            "alu_grp_imm_m", "mov_imm16", "mov_rr", "mov_rm", "mov_moffs",
            "lea", "incdec_r16", "push_r16", "pop_r16", "xchg_rr",
            "shift_by1", "mulu8_r", "divu16_safe", "test_rr", "jcc",
            "jcxz", "jmp_short", "string_single", "rep_string", "nops"]
    keys = EXT_MENU.keys() if exts is None else exts
    out = list(base)
    for e in keys:
        out += EXT_MENU[e][2]
    return out


def generate(seed, nmin=20, nmax=100, exts=()):
    """-> dict(seed, instr, regs, ram, forms, ins). exts = iterable of
    EXT_MENU keys (staged expansions; each changes the program stream for
    the same seed, so gate runs must pin their exts set).

    forms = per-gadget form tags (coverage); ins = per-instruction byte
    strings (objective opsig/prefix coverage)."""
    rng = random.Random(f"seq/{seed}")
    p = Prog(rng)
    state = {"stackops": 0, "depth": 0}
    n = rng.randrange(nmin, nmax + 1)
    funcs, weights = zip(*MENU)
    funcs = list(funcs) + [lambda pp, rr: _gen_pushpop(pp, rr, state)]
    weights = list(weights) + [MENU_STACK_W]
    for e in exts:
        f, w = EXT_MENU[e][:2]
        if e in STATE_EXTS:
            funcs.append(lambda pp, rr, ff=f: ff(pp, rr, state))
        else:
            funcs.append(f)
        weights.append(w)
    forms = []
    while len(p.ins) < n:
        tag = rng.choices(funcs, weights=weights)[0](p, rng)
        if tag:
            forms.append(tag)
    instr = p.assemble()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,
            "AW": rng.getrandbits(16), "BW": rng.getrandbits(16),
            "CW": rng.getrandbits(16), "DW": rng.getrandbits(16),
            "BP": rng.getrandbits(16),
            "IX": rng.randrange(0x2400, 0x2800),
            "IY": rng.randrange(0x2900, 0x2D00)}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += [(a, rng.getrandbits(8)) for a in range(0x3E00, 0x4000)]
    # gadget-controlled bytes win over the random fill (appended last; compose
    # takes the last write per physical address for same-address duplicates)
    for addr, data in p.ram_over:
        ram += [(addr + i, b) for i, b in enumerate(data)]
    ivt = None
    if any(e in FAR_INT_EXTS for e in exts):
        ivt, handler = far_int_support()
        ram += handler                    # IRET + RETF handler stub bytes
    return dict(seed=seed, instr=instr, regs=regs, ram=ram, ivt=ivt,
                n_ins=len(p.ins), forms=forms,
                ins=[bytes(b) for b in p.ins])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--dump", action="store_true")
    a = ap.parse_args()
    g = generate(a.seed)
    print(f"seed {g['seed']}: {g['n_ins']} instructions, "
          f"{len(g['instr'])} bytes")
    if a.dump:
        print(g["instr"].hex())


if __name__ == "__main__":
    main()
