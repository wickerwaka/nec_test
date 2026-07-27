#!/usr/bin/env python3
"""gen_soup - Tier A "instruction soup" generator for the massive fuzz
expansion (task #29).

Unlike gen_seq (a curated menu of hand-proven safe gadgets), gen_soup draws
over the FULL legal opcode space via sw/optable.py, dispatched per Op.policy.
Containment is structural rather than per-form:

  * full_ivt() points ALL 256 vectors at a bare IRET handler at 0x0480, so
    every trap (divide, BOUND/INT5, INT n, INTO, single-step, NMI, ...)
    returns cleanly -> arithmetic / traps need no operand pre-conditioning.
  * memory WRITES in contained mode are windowed (mod0/rm6 direct into the
    0x2000-0x2F00 data window); the 25% non-windowed EA draws degrade to the
    safe mod3 register form. Only WILD seeds emit truly wild memory modrm
    (20-bit aliases -> self-modification -> the accepted no-done subset).
  * forward-only branches in contained mode; CALL/RET/far/indirect/LOOP as
    the proven contained gadgets; SP is never written outside wild mode.
  * REP + string forces a MOV CW,0..12 count clamp; PORT stays in the even
    0x08..0xEE harness-safe band (never 0xFC done / 0xFE regs).

The generator does NOT modify gen_seq (its fz-seed RNG streams are frozen);
it imports only the byte-layout primitives (Prog + assemble, _imm_biased,
_mem_ea, the window constants, HANDLER_AT, NOSP).

Returns a g-dict matching the gen_seq contract
(seed/instr/regs/ram/ivt/n_ins/forms/ins) plus provenance extras
(has_brkem, brkem_pos, has_halt, has_tf, wild) so check_seq.compose(g) and the
fuzz classifier consume it unchanged.
"""
import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from gen_seq import (Prog, _imm_biased, _mem_ea, NOSP,  # noqa: E402
                     DATA_LO, DATA_HI, SP0, PC0, HANDLER_AT)
import optable  # noqa: E402

# handler + far-return stub (IRET at 0x0480, RETF at 0x0481). Every IVT slot
# targets the IRET; far CALL gadgets target the RETF byte.
IRET_AT = HANDLER_AT            # 0x0480
RETF_AT = HANDLER_AT + 1        # 0x0481
HANDLER_BYTES = [(IRET_AT, 0xCF), (RETF_AT, 0xCB)]

# windowed target band for wild-mode SP resync + string pointers
STR_SI_LO, STR_SI_HI = 0x2400, 0x2800
STR_DI_LO, STR_DI_HI = 0x2900, 0x2D00


def full_ivt():
    """All 256 vectors -> the bare IRET handler at 0x0480 (1 KB IVT, no
    collision with the handler at 0x0480 or the program at 0x0500)."""
    return {n: (0, IRET_AT) for n in range(256)}


@dataclass
class SoupKnobs:
    p_prefix: float = 0.30        # fraction of prefixable ops carrying a stack
    max_prefix: int = 4           # 0..4 prefixes per stack
    p_window_ea: float = 0.75     # windowed-direct vs mod3/wild EA
    p_wild_seed: float = 0.15     # fraction of seeds in wild sub-mode
    p_brkem: float = 0.001        # per-instruction BRKEM (0F FF ib) rate. Lowered
                                  # 0.005->0.001 (task #29 Phase-5 decision): at
                                  # ~50 ins/seed 0.005 put ~17% of board captures
                                  # in dead 8080-entry; 0.001 ~= 3.4%/seed.
    p_undoc: float = 0.02         # per-instruction undoc-opcode rate
    p_halt: float = 0.30          # HALT/POLL rate (only when evt pin permits)
    p_tf: float = 0.002           # deliberate TF-set (single-step) rate
    p_backward_raw: float = 0.02  # raw backward Jcc (wild seeds only)
    p_sreg_rand: float = 0.40     # DS0/DS1 load = random (else 0x0000). A random
                                  # DS then a windowed write escapes the window
                                  # (accepted no-done breadth) - set 0 for a
                                  # strict contained fall-through generation.
    stack_cap: int = 24           # max outstanding PUSH-family ops


# --- opcode pools drawn from optable, grouped by policy (prefixes excluded) --
def _pool(policy, pred=None):
    out = []
    for code, op in optable.TABLE.items():
        if code in optable.PREFIXES:
            continue
        if op.policy != policy:
            continue
        if pred and not pred(op):
            continue
        out.append(op)
    return out


# SP-writing single-byte forms excluded from contained draws
_SP_WRITERS = {0x44, 0x4C, 0x94}   # INC SP, DEC SP, XCHG AW,SP

FREE_OPS = [o for o in _pool(optable.FREE) if o.code not in _SP_WRITERS]
# generic modrm-EA ops: exclude the special-cased no-modrm / far-pointer forms
_EA_SPECIAL = {0xA0, 0xA1, 0xA2, 0xA3,               # moffs
               0xA4, 0xA5, 0xA6, 0xA7, 0xAA, 0xAB,   # string
               0xAC, 0xAD, 0xAE, 0xAF,
               0xC4, 0xC5,                           # LES/LDS (inject zero ptr)
               0xD7}                                 # XLAT (no modrm, read)
EA_MODRM_OPS = [o for o in _pool(optable.EA)
                if o.modrm and o.code not in _EA_SPECIAL]
PORT_IMM_OPS = [o for o in _pool(optable.PORT) if o.code in (0xE4, 0xE5, 0xE6, 0xE7)]
PORT_DX_OPS = [o for o in _pool(optable.PORT) if o.code in (0xEC, 0xED, 0xEE, 0xEF)]
PORT_STR_OPS = [o for o in _pool(optable.PORT) if o.code in (0x6C, 0x6D, 0x6E, 0x6F)]
UNDOC_OPS = _pool(optable.UNDOC)
STRING_CODES = [0xA4, 0xA5, 0xA6, 0xA7, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF]
# whitelisted 0F EA forms usable as generic register/windowed ops
F0_EA = [b for b, o in optable.F0_WHITELIST.items()
         if o.policy == optable.EA and o.modrm
         and b not in (0x31, 0x33, 0x39, 0x3B)]   # INS/EXT emitted specially


def _safe_exts(op):
    """Legal group /reg ext values for the EA family (banned + cflow removed)."""
    exts = [e for e in range(8) if e not in op.banned_ext]
    if op.code == 0xFF:                       # only INC/DEC/PUSH mem (no call/jmp)
        exts = [e for e in exts if e in (0, 1, 6)]
    return exts


def _port(rng):
    """Even harness-safe port in 0x08..0xEE (never 0xFC done / 0xFE regs)."""
    return rng.randrange(0x08, 0xEF) & 0xFE


# ---------------------------------------------------------------------------
class Soup:
    def __init__(self, seed, knobs, evt_pin, wild):
        self.rng = random.Random(f"soup/{seed}")
        self.k = knobs
        self.evt_pin = evt_pin        # None | 0=INT | 1=NMI | 2=POLL
        self.wild = wild
        self.p = Prog(self.rng)
        self.forms = []
        self.stackn = 0
        self.brkem_ins = []           # p.ins indices carrying a BRKEM
        self.has_halt = False
        self.has_tf = False
        self.since_sp = 0             # instrs since last wild SP resync

    # --- prefix stack -----------------------------------------------------
    def _prefix(self, allow_rep=True):
        rng = self.rng
        if rng.random() >= self.k.p_prefix:
            return b""
        pool = list(optable.PREFIXES)
        if not allow_rep:
            pool = [b for b in pool if b not in (0x64, 0x65, 0xF2, 0xF3)]
        n = rng.randint(1, self.k.max_prefix)
        return bytes(rng.choice(pool) for _ in range(n))

    # --- EA operand build -------------------------------------------------
    def _ea(self, reg_field, write, force_windowed=False):
        """(bytes) modrm + disp for reg_field. Contained: windowed direct
        (mod0/rm6) at p_window_ea else the safe mod3 register form; wild
        seeds emit a truly wild memory modrm for the non-windowed fraction."""
        rng = self.rng
        if force_windowed or rng.random() < self.k.p_window_ea:
            ea = _mem_ea(rng)                       # even/odd data-window addr
            return bytes([(reg_field << 3) | 6, ea & 0xFF, ea >> 8])
        if self.wild:
            mod = rng.randrange(3)                  # wild memory (may self-modify)
            rm = rng.randrange(8)
            b = bytes([(mod << 6) | (reg_field << 3) | rm])
            if mod == 0 and rm == 6:
                a = rng.getrandbits(16)
                return b + bytes([a & 0xFF, a >> 8])
            if mod == 1:
                return b + bytes([rng.getrandbits(8)])
            if mod == 2:
                a = rng.getrandbits(16)
                return b + bytes([a & 0xFF, a >> 8])
            return b
        rm = rng.choice(NOSP)                        # contained: mod3 register form
        return bytes([0xC0 | (reg_field << 3) | rm])

    # --- family emitters --------------------------------------------------
    def emit_free(self):
        op = self.rng.choice(FREE_OPS)
        imm = (_imm_biased(self.rng, 8 * op.imm).to_bytes(op.imm, "little")
               if op.imm else b"")
        self.p.emit(self._prefix() + bytes([op.code]) + imm)
        return "free"

    def emit_ea(self):
        op = self.rng.choice(EA_MODRM_OPS)
        rng = self.rng
        if op.group:
            ext = rng.choice(_safe_exts(op))
            reg_field = ext
            write = op.code in (0xFE, 0xFF, 0xC6, 0xC7) or \
                (op.code in (0x80, 0x81, 0x82, 0x83, 0xC0, 0xC1,
                             0xD0, 0xD1, 0xD2, 0xD3) and ext != 7)
        else:
            reg_field = rng.choice(NOSP)
            write = op.code in (0x88, 0x89, 0x86, 0x87)  # store / xchg RMW
        ea = self._ea(reg_field, write)
        imm = b""
        if op.imm_extdep:                        # F6/F7: /0,/1 carry immediate
            if op.group and reg_field in (0, 1):
                nb = 2 if op.code == 0xF7 else 1
                imm = _imm_biased(rng, 8 * nb).to_bytes(nb, "little")
        elif op.imm:
            imm = _imm_biased(rng, 8 * op.imm).to_bytes(op.imm, "little")
        self.p.emit(self._prefix() + bytes([op.code]) + ea + imm)
        return "ea"

    def emit_ea_0f(self):
        b2 = self.rng.choice(F0_EA)
        op = optable.F0_WHITELIST[b2]
        reg_field = self.rng.randrange(8)
        if op.group:                             # bitop/rol4: /0 (rol4) or op-select
            reg_field = 0 if b2 in (0x28, 0x2A) else self.rng.randrange(8)
        ea = self._ea(reg_field, write=True)
        imm = bytes([self.rng.getrandbits(8)]) if op.imm else b""
        self.p.emit(self._prefix() + bytes([0x0F, b2]) + ea + imm)
        return "ea_0f"

    def emit_insext(self):
        rng = self.rng
        ins = rng.random() < 0.5
        if rng.random() < 0.5:                   # reg,imm4 (0F 39/3B)
            b2 = 0x39 if ins else 0x3B
            self.p.emit_atomic([
                bytes([0xB8, rng.randrange(0, 8), 0x00]),         # AL=offset 0..7
                bytes([0x0F, b2, 0xC0, rng.randrange(1, 9)])])    # len imm 1..8
        else:                                    # reg,reg (0F 31/33)
            b2 = 0x31 if ins else 0x33
            self.p.emit_atomic([
                bytes([0xB8, rng.randrange(0, 8), 0x00]),         # AL=offset
                bytes([0xB9, rng.randrange(1, 9), 0x00]),         # CL=length 1..8
                bytes([0x0F, b2, 0xC8])])                         # reg2=CL,reg1=AL
        return "insext"

    def emit_bcd4s(self):
        b2 = self.rng.choice([0x20, 0x22, 0x26])
        self.p.emit_atomic([bytes([0xB9, self.rng.randrange(1, 7), 0x00]),  # CL 1..6
                            bytes([0x0F, b2])])
        return "bcd4s"

    def emit_les_lds(self):
        op = self.rng.choice([0xC4, 0xC5])
        ea = self.rng.randrange(DATA_LO, DATA_HI - 4) & 0xFFFE
        off = self.rng.getrandbits(16)
        self.p.ram_set(ea, [off & 0xFF, off >> 8, 0x00, 0x00])   # seg -> 0
        self.p.emit(bytes([op, (self.rng.choice(NOSP) << 3) | 6,
                           ea & 0xFF, ea >> 8]))
        return "les_lds"

    def emit_moffs(self):
        op = self.rng.choice([0xA0, 0xA1, 0xA2, 0xA3])
        ea = _mem_ea(self.rng)
        self.p.emit(self._prefix() + bytes([op, ea & 0xFF, ea >> 8]))
        return "moffs"

    def emit_xlat(self):
        self.p.emit(self._prefix() + bytes([0xD7]))              # read-only
        return "xlat"

    def emit_string(self):
        rng = self.rng
        si = rng.randrange(STR_SI_LO, STR_SI_HI)
        di = rng.randrange(STR_DI_LO, STR_DI_HI)
        op = rng.choice(STRING_CODES)
        seq = [bytes([0xBE, si & 0xFF, si >> 8]),               # MOV SI
               bytes([0xBF, di & 0xFF, di >> 8]),               # MOV DI
               [0xFC] if rng.random() < 0.85 else [0xFD]]        # CLD/STD
        rep = rng.random() < 0.5
        seg = ([rng.choice(list(optable.SEG_PREFIXES))]
               if rng.random() < 0.25 else [])
        if rep:
            cw = rng.randrange(0, 13)                           # REP+string clamp
            reppfx = rng.choice([0xF3, 0xF2, 0x64, 0x65])       # rep/repnz/repc/repnc
            seq.append(bytes([0xB9, cw, 0x00]))                 # MOV CW,0..12
            seq.append(seg + [reppfx, op])
            tag = "rep_string"
        else:
            seq.append(seg + [op])
            tag = "string"
        self.p.emit_atomic(seq)
        return tag

    def emit_port(self):
        rng = self.rng
        r = rng.random()
        if r < 0.4:                                             # imm8-port
            op = rng.choice(PORT_IMM_OPS)
            self.p.emit(self._prefix() + bytes([op.code, _port(rng)]))
            return "port_imm"
        if r < 0.7:                                             # DX-port
            op = rng.choice(PORT_DX_OPS)
            self.p.emit_atomic([bytes([0xBA]) + _port(rng).to_bytes(2, "little"),
                                bytes([op.code])])
            return "port_dx"
        # INM/OUTM string I/O (bounded count, windowed pointers)
        op = rng.choice(PORT_STR_OPS)
        si = rng.randrange(STR_SI_LO, STR_SI_HI)
        iy = rng.randrange(STR_DI_LO, STR_DI_HI)
        seq = [bytes([0xBE, si & 0xFF, si >> 8]),               # SI (OUTM src)
               bytes([0xBF, iy & 0xFF, iy >> 8]),               # IY (INM dst)
               bytes([0xBA]) + _port(rng).to_bytes(2, "little"),  # DW=port
               [0xFC]]
        if rng.random() < 0.5:
            seq.append(bytes([0xB9, rng.randrange(1, 4), 0x00]))  # CW 1..3
            seq.append([0xF3, op.code])
        else:
            seq.append([op.code])
        self.p.emit_atomic(seq)
        return "port_str"

    def emit_stack(self):
        rng = self.rng
        if self.stackn >= self.k.stack_cap:
            return self.emit_free()
        r = rng.random()
        if r < 0.30:                                           # PUSH r16
            self.p.emit([0x50 + rng.randrange(8)])
            self.stackn += 1
            return "push_r16"
        if r < 0.50:                                           # POP r16 (never SP)
            reg = rng.randrange(8)
            self.p.emit([0x58 + (0 if reg == 4 else reg)])
            return "pop_r16"
        if r < 0.62:                                           # PUSH imm
            if rng.random() < 0.5:
                self.p.emit(bytes([0x6A, _imm_biased(rng, 8)]))
            else:
                self.p.emit(bytes([0x68]) + _imm_biased(rng, 16).to_bytes(2, "little"))
            self.stackn += 1
            return "push_imm"
        if r < 0.72:                                           # PUSHF/POPF pair
            self.p.emit_atomic([bytes([0x9C]), bytes([0x9D])])
            return "pushf_popf"
        if r < 0.82:                                           # PUSHA/POPA pair
            self.p.emit_atomic([bytes([0x60]), bytes([0x61])])
            return "pusha_popa"
        if r < 0.90:                                           # PUSH/POP sreg pair
            sreg = rng.choice([0, 2, 3])                       # ES, SS, DS (skip CS)
            self.p.emit_atomic([bytes([0x06 | (sreg << 3)]),
                                bytes([0x07 | (sreg << 3)])])
            return "pushpop_sreg"
        if r < 0.96:                                           # POP mem (windowed)
            self.p.emit(bytes([0x8F]) + self._ea(0, write=True,
                                                 force_windowed=True))
            return "pop_mem"
        # PREPARE/DISPOSE (ENTER/LEAVE) with BP windowed + SP resync
        size = rng.randrange(0, 0x20) & 0xFFFE
        level = rng.randrange(0, 4)
        seq = [bytes([0xBD, 0xE0, 0x3F]),                      # MOV BP,0x3FE0
               bytes([0xC8, size & 0xFF, size >> 8, level])]
        if rng.random() < 0.5:
            seq.append(bytes([0xC9]))                          # DISPOSE
        seq.append(bytes([0xBC, 0x00, 0x3F]))                  # MOV SP,0x3F00
        self.p.emit_atomic(seq)
        return "prepare"

    def emit_cflow_fwd(self):
        # near JMP rel16 (E9) is 3 bytes: emit the wide form directly (Prog.branch
        # only lays the 2-byte short/Jcc form; passing E9 there malforms it).
        if self.rng.random() < 0.15:
            idx = len(self.p.ins)
            self.p.ins.append(bytes([0xE9, 0, 0]))
            self.p.fixups.append((idx, self.rng.randrange(1, 5)))
            return "cflow_fwd"
        opc = self.rng.choice([0xEB, 0xE3] + [0x70 + c for c in range(16)])
        self.p.branch(opc)
        return "cflow_fwd"

    def emit_cflow_gadget(self):
        rng = self.rng
        r = rng.random()
        if r < 0.22:                                           # far JMP -> next
            self.p.emit_farjmp_next()
            return "far_jmp"
        if r < 0.40:                                           # far CALL -> RETF stub
            self.p.emit(bytes([0x9A, RETF_AT & 0xFF, RETF_AT >> 8, 0, 0]))
            return "far_call"
        if r < 0.62:                                           # software INT
            k = rng.randrange(3)
            if k == 0:
                self.p.emit([0xCC])
            elif k == 1:
                self.p.emit([0xCD, rng.randrange(256)])        # any vector (full IVT)
            else:
                self.p.emit([0xCE])
            return "swint"
        if r < 0.80:                                           # CALL near + RET
            body = [bytes([rng.choice([0x40, 0x48]) + (0 if x == 4 else x)])
                    for x in (rng.randrange(8),)]
            body_len = sum(len(b) for b in body)
            self.p.emit_atomic([bytes([0xE8, 0x02, 0x00]),
                                bytes([0xEB, body_len + 1]), *body,
                                bytes([0xC3])])
            return "callret"
        # near indirect CALL/JMP through a preloaded register (self-continue)
        reg = rng.choice([0, 1, 2, 3])
        start = len(self.p.ins)
        if rng.random() < 0.5:
            self.p.ins.append(bytes([0xB8 + reg, 0, 0]))
            self.p.ins.append(bytes([0xFF, 0xC0 | (4 << 3) | reg]))   # JMP reg
            self.p.noland.add(start + 1)
            self.p.reg_ip_fixups.append((start, start + 2))
        else:
            self.p.ins.append(bytes([0xB8 + reg, 0, 0]))
            self.p.ins.append(bytes([0xFF, 0xC0 | (2 << 3) | reg]))   # CALL reg
            self.p.ins.append(bytes([0xEB, 1]))                       # JMP after
            sub_i = len(self.p.ins)
            self.p.ins.append(bytes([0xC3]))                         # RET
            for i in range(start + 1, len(self.p.ins)):
                self.p.noland.add(i)
            self.p.reg_ip_fixups.append((start, sub_i))
        return "indirect"

    def emit_loop(self):
        rng = self.rng
        op = rng.choice([0xE0, 0xE1, 0xE2])
        body = [bytes([rng.choice([0x40, 0x48]) + rng.choice([0, 2, 3, 5, 6, 7])])
                for _ in range(rng.randrange(1, 3))]
        body_len = sum(len(b) for b in body)
        disp = (-(body_len + 2)) & 0xFF
        self.p.emit_atomic([bytes([0xB9, rng.randrange(1, 5), 0x00])] + body +
                           [bytes([op, disp])])
        return "loop"

    def emit_sreg(self):
        rng = self.rng
        sreg = rng.choice([0x00, 0x03])          # DS1 (reg=00), DS0 (reg=11)
        val = rng.getrandbits(16) if rng.random() < self.k.p_sreg_rand else 0x0000
        ea = rng.randrange(DATA_LO, DATA_HI - 2) & 0xFFFE
        self.p.ram_set(ea, [val & 0xFF, val >> 8])
        self.p.emit(bytes([0x8E, (sreg << 3) | 6, ea & 0xFF, ea >> 8]))
        return "sreg"

    def emit_undoc(self):
        op = self.rng.choice(UNDOC_OPS)
        self.p.emit(bytes([op.code]))
        return "undoc"

    def emit_brkem(self):
        self.brkem_ins.append(len(self.p.ins))
        self.p.emit(bytes([0x0F, 0xFF, self.rng.randrange(256)]))
        return "brkem"

    def emit_halt(self):
        # HALT only with an armed level-INT wake; POLL with an armed POLL pin.
        self.has_halt = True
        if self.evt_pin == 2:
            self.p.emit_atomic([bytes([0x9B])])                # POLL
            return "poll"
        self.p.emit_atomic([bytes([0xFB]), bytes([0xF4])])     # EI; HALT
        return "halt"

    def emit_tf(self):
        # deliberate TF set (single-step). With the bare-IRET IVT the step
        # storm never returns to the stub -> this seed is a flagged no-done.
        self.has_tf = True
        self.p.emit_atomic([bytes([0x68, 0x00, 0x01]),         # PUSH 0x0100 (TF)
                            bytes([0x9D])])                     # POPF
        return "tf"

    def emit_wild_sp(self):
        # wild SP write then forced resync (keeps the stack recoverable)
        self.p.emit_atomic([bytes([0xBC]) + self.rng.getrandbits(16).to_bytes(2, "little"),
                            bytes([0xBC, 0x00, 0x3F])])         # MOV SP,rand; MOV SP,0x3F00
        self.since_sp = 0
        return "wild_sp"

    def emit_wild_back(self):
        # raw backward Jcc (wild only): may loop; Jcc is conditional so it
        # usually falls through - part of the accepted no-done subset.
        opc = self.rng.choice([0x70 + c for c in range(16)])
        self.p.emit(bytes([opc, 0xFC]))                        # disp -4
        return "wild_back"

    # --- driver -----------------------------------------------------------
    def build(self, nmin, nmax):
        rng = self.rng
        n = rng.randrange(nmin, nmax + 1)
        halt_used = False
        base = [(self.emit_free, 20), (self.emit_ea, 20), (self.emit_ea_0f, 4),
                (self.emit_string, 5), (self.emit_port, 5), (self.emit_stack, 10),
                (self.emit_cflow_fwd, 8), (self.emit_cflow_gadget, 6),
                (self.emit_loop, 3), (self.emit_sreg, 3), (self.emit_moffs, 2),
                (self.emit_xlat, 1), (self.emit_les_lds, 2), (self.emit_bcd4s, 2),
                (self.emit_insext, 2)]
        funcs, weights = zip(*base)
        while len(self.p.ins) < n:
            # rare gated specials first
            if rng.random() < self.k.p_brkem:
                self.forms.append(self.emit_brkem())
                continue
            if rng.random() < self.k.p_undoc:
                self.forms.append(self.emit_undoc())
                continue
            if rng.random() < self.k.p_tf:
                self.forms.append(self.emit_tf())
                continue
            if (not halt_used and self.evt_pin in (0, 2)
                    and rng.random() < self.k.p_halt):
                self.forms.append(self.emit_halt())
                halt_used = True
                continue
            if self.wild:
                self.since_sp += 1
                if self.since_sp >= rng.randint(8, 16):
                    self.forms.append(self.emit_wild_sp())
                    continue
                if rng.random() < self.k.p_backward_raw:
                    self.forms.append(self.emit_wild_back())
                    continue
            self.forms.append(rng.choices(funcs, weights=weights)[0]())
        instr = self.p.assemble()
        return instr


def gen_soup(seed, nmin=24, nmax=80, knobs=None, evt_pin=None, wild=None):
    """-> g-dict (compose-ready) + soup provenance extras.

    evt_pin: None | 0=INT | 1=NMI | 2=POLL - governs HALT/POLL emission.
    wild: force wild sub-mode (default = seeded p_wild_seed draw)."""
    knobs = knobs or SoupKnobs()
    rng0 = random.Random(f"soup-mode/{seed}")
    if wild is None:
        wild = rng0.random() < knobs.p_wild_seed
    s = Soup(seed, knobs, evt_pin, wild)
    instr = s.build(nmin, nmax)

    # brkem provenance: linear = anchor 0x0500 + byte offset of the BRKEM instr
    sizes = [len(b) for b in s.p.ins]
    brkem_pos = [(idx, (PC0 + sum(sizes[:idx])) & 0xFFFFF) for idx in s.brkem_ins]

    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0, "DS0": 0, "DS1": 0,
            "PSW": 0xF202,
            "AW": rng0.getrandbits(16), "BW": rng0.getrandbits(16),
            "CW": rng0.getrandbits(16), "DW": rng0.getrandbits(16),
            "BP": rng0.getrandbits(16),
            "IX": rng0.randrange(STR_SI_LO, STR_SI_HI),
            "IY": rng0.randrange(STR_DI_LO, STR_DI_HI)}
    ram = [(a, rng0.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += [(a, rng0.getrandbits(8)) for a in range(0x3E00, 0x4000)]
    for addr, data in s.p.ram_over:
        ram += [(addr + i, b) for i, b in enumerate(data)]
    ram += HANDLER_BYTES

    return dict(seed=seed, instr=instr, regs=regs, ram=ram, ivt=full_ivt(),
                n_ins=len(s.p.ins), forms=s.forms,
                ins=[bytes(b) for b in s.p.ins],
                has_brkem=bool(brkem_pos), brkem_pos=brkem_pos,
                has_halt=s.has_halt, has_tf=s.has_tf, wild=wild)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("seed")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--pin", type=int, default=None, help="evt pin 0=INT 1=NMI 2=POLL")
    a = ap.parse_args()
    g = gen_soup(a.seed, evt_pin=a.pin)
    print(f"seed {g['seed']}: {g['n_ins']} ins, {len(g['instr'])} bytes, "
          f"wild={g['wild']} brkem={g['brkem_pos']} halt={g['has_halt']} "
          f"tf={g['has_tf']}")
    if a.dump:
        print(g["instr"].hex())


if __name__ == "__main__":
    main()
