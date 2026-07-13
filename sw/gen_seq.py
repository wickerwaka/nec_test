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
        imm = rng.getrandbits(16 if w else 8)
        p.emit(bytes([op * 8 + 4 + w]) +
               imm.to_bytes(2 if w else 1, "little"))
        return "alu_acc_imm"
    elif kind == 1:          # 80/81/83 reg
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g, 0xC0 | (op << 3) | rng.choice(NOSP)]) +
               rng.getrandbits(8 * n).to_bytes(n, "little"))
        return "alu_grp_imm_r"
    else:                    # 80/81/83 mem
        g = rng.choice([0x80, 0x81, 0x83])
        n = 2 if g == 0x81 else 1
        p.emit(bytes([g]) + _modrm_direct(op, rng) +
               rng.getrandbits(8 * n).to_bytes(n, "little"))
        return "alu_grp_imm_m"


def _gen_mov(p, rng):
    kind = rng.randrange(4)
    if kind == 0:            # B8+r imm16
        p.emit(bytes([0xB8 + rng.choice(NOSP)]) +
               rng.getrandbits(16).to_bytes(2, "little"))
        return "mov_imm16"
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
    opc = rng.choice([0xEB] + [0x70 + c for c in range(16)])
    p.branch(opc)
    return "jcc" if opc != 0xEB else "jmp_short"


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


MENU = [(_gen_alu_rr, 14), (_gen_alu_mem, 12), (_gen_alu_imm, 10),
        (_gen_mov, 16), (_gen_incdec, 6), (_gen_xchg, 4),
        (_gen_shift, 5), (_gen_mul, 3), (_gen_div_safe, 2),
        (_gen_test, 4), (_gen_branch, 8), (_gen_string, 5),
        (_gen_nops, 6)]
MENU_STACK_W = 6

EXT_MENU = {
    "callret": (_gen_callret, 5, "callret_near"),
    "sregw":   (_gen_sregw, 4, "sreg_rw"),
    "popf":    (_gen_pushf_popf, 4, "pushf_popf"),
}


def form_universe(exts=None):
    """All form tags the generator can emit (base menu + given exts, or
    ALL exts when exts is None). Lets the coverage report show families
    that have never been exercised."""
    base = ["alu_rr", "alu_mem", "alu_acc_imm", "alu_grp_imm_r",
            "alu_grp_imm_m", "mov_imm16", "mov_rr", "mov_rm", "mov_moffs",
            "lea", "incdec_r16", "push_r16", "pop_r16", "xchg_rr",
            "shift_by1", "mulu8_r", "divu16_safe", "test_rr", "jcc",
            "jmp_short", "string_single", "rep_string", "nops"]
    keys = EXT_MENU.keys() if exts is None else exts
    return base + [EXT_MENU[e][2] for e in keys]


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
    return dict(seed=seed, instr=instr, regs=regs, ram=ram,
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
