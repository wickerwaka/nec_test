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


def _modrm_direct(reg, rng):
    ea = _mem_ea(rng)
    return bytes([(reg << 3) | 6, ea & 0xFF, ea >> 8])


class Prog:
    def __init__(self, rng):
        self.rng = rng
        self.ins = []          # list of bytes objects (one per instruction)
        self.fixups = []       # (ins_index, target_ins_index) for disp8
        self.noland = set()    # indices illegal as branch targets: landing
                               # here would skip a safe-gadget's setup

    def emit(self, b):
        self.ins.append(bytes(b))

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
            assert disp < 0x80
            out[idx][1] = disp
        return b"".join(bytes(b) for b in out)


NOSP = [0, 1, 2, 3, 5, 6, 7]     # never write SP (stack must stay windowed)


def _gen_alu_rr(p, rng):
    op = rng.randrange(8)
    w = rng.getrandbits(1)
    d = rng.getrandbits(1)
    reg, rm = rng.choice(NOSP), rng.choice(NOSP)
    p.emit([op * 8 + (2 * d) + w, 0xC0 | (reg << 3) | rm])


def _gen_alu_mem(p, rng):
    op = rng.randrange(8)
    w = rng.getrandbits(1)
    d = rng.getrandbits(1)
    reg = rng.randrange(8)
    pre = b""
    if rng.random() < 0.25:
        pre = bytes([rng.choice([0x26, 0x2E, 0x36, 0x3E])])
    p.emit(pre + bytes([op * 8 + (2 * d) + w]) + _modrm_direct(reg, rng))


def _gen_alu_imm(p, rng):
    op = rng.randrange(8)
    kind = rng.randrange(3)
    if kind == 0:            # acc,imm
        w = rng.getrandbits(1)
        imm = rng.getrandbits(16 if w else 8)
        p.emit(bytes([op * 8 + 4 + w]) +
               imm.to_bytes(2 if w else 1, "little"))
    elif kind == 1:          # 80/81/83 reg
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g, 0xC0 | (op << 3) | rng.choice(NOSP)]) +
               rng.getrandbits(8 * n).to_bytes(n, "little"))
    else:                    # 80/81/83 mem
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g]) + _modrm_direct(op, rng) +
               rng.getrandbits(8 * n).to_bytes(n, "little"))


def _gen_mov(p, rng):
    kind = rng.randrange(4)
    if kind == 0:            # B8+r imm16
        p.emit(bytes([0xB8 + rng.choice(NOSP)]) +
               rng.getrandbits(16).to_bytes(2, "little"))
    elif kind == 1:          # mov r,r / r,m / m,r
        w = rng.getrandbits(1)
        d = rng.getrandbits(1)
        if rng.random() < 0.5:
            p.emit([0x88 + 2 * d + w,
                    0xC0 | (rng.choice(NOSP) << 3) | rng.choice(NOSP)])
        else:
            p.emit(bytes([0x88 + 2 * d + w]) +
                   _modrm_direct(rng.randrange(8), rng))
    elif kind == 2:          # moffs
        w = rng.getrandbits(1)
        d = rng.getrandbits(1)
        ea = _mem_ea(rng)
        p.emit(bytes([0xA0 + 2 * d + w, ea & 0xFF, ea >> 8]))
    else:                    # lea
        p.emit(bytes([0x8D]) + _modrm_direct(rng.choice(NOSP), rng))


def _gen_incdec(p, rng):
    p.emit([rng.choice([0x40, 0x48]) + rng.randrange(8)])


def _gen_pushpop(p, rng, state):
    if state["stackops"] >= 20:
        return _gen_incdec(p, rng)
    state["stackops"] += 1
    if rng.random() < 0.5:
        p.emit([0x50 + rng.randrange(8)])
        state["depth"] += 1
    else:
        r = rng.randrange(8)
        if r == 4:            # POP SP: allowed (load wins law) but
            r = 0             # keep SP inside the window - swap to AX
        p.emit([0x58 + r])
        state["depth"] -= 1


def _gen_xchg(p, rng):
    w = rng.getrandbits(1)
    p.emit([0x86 + w, 0xC0 | (rng.choice(NOSP) << 3) | rng.choice(NOSP)])


def _gen_shift(p, rng):
    w = rng.getrandbits(1)
    p.emit([0xD0 + w, 0xC0 | (4 << 3) | rng.choice(NOSP)])


def _gen_mul(p, rng):
    p.emit([0xF6, 0xC0 | (4 << 3) | rng.randrange(4)])   # MULU8 reg


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


def _gen_test(p, rng):
    w = rng.getrandbits(1)
    p.emit([0x84 + w, 0xC0 | (rng.randrange(8) << 3) | rng.randrange(8)])


def _gen_branch(p, rng):
    opc = rng.choice([0xEB] + [0x70 + c for c in range(16)])
    p.branch(opc)


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
    else:
        seq.append([op])
    p.emit_atomic(seq)


def _gen_nops(p, rng):
    for _ in range(rng.randrange(1, 4)):
        p.emit([0x90])


MENU = [(_gen_alu_rr, 14), (_gen_alu_mem, 12), (_gen_alu_imm, 10),
        (_gen_mov, 16), (_gen_incdec, 6), (_gen_xchg, 4),
        (_gen_shift, 5), (_gen_mul, 3), (_gen_div_safe, 2),
        (_gen_test, 4), (_gen_branch, 8), (_gen_string, 5),
        (_gen_nops, 6)]
MENU_STACK_W = 6


def generate(seed, nmin=20, nmax=100):
    """-> dict(seed, instr, regs, ram)"""
    rng = random.Random(f"seq/{seed}")
    p = Prog(rng)
    state = {"stackops": 0, "depth": 0}
    n = rng.randrange(nmin, nmax + 1)
    funcs, weights = zip(*MENU)
    funcs = list(funcs) + [lambda pp, rr: _gen_pushpop(pp, rr, state)]
    weights = list(weights) + [MENU_STACK_W]
    while len(p.ins) < n:
        rng.choices(funcs, weights=weights)[0](p, rng)
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
    return dict(seed=seed, instr=instr, regs=regs, ram=ram,
                n_ins=len(p.ins))


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
