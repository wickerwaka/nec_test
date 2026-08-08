#!/usr/bin/env python3
"""gen_soup - Tier A "instruction soup" generator for the massive fuzz
expansion (task #29).

Unlike gen_seq (a curated menu of hand-proven safe gadgets), gen_soup draws
over the FULL legal opcode space via sw/optable.py, dispatched per Op.policy.
Containment is structural rather than per-form:

  * full_ivt() points every vector except the terminator's at the v2 image's
    interrupt modification-handler table, so every trap (divide, BOUND/INT5,
    INT n, INTO, single-step, NMI, ...) runs a register-only body and IRETs
    -> arithmetic / traps need no operand pre-conditioning.
  * memory WRITES in contained mode are windowed (mod0/rm6 direct into the
    0x2000-0x2F00 data window); the 25% non-windowed EA draws degrade to the
    safe mod3 register form. Only WILD seeds emit truly wild memory modrm
    (20-bit aliases -> self-modification -> the accepted no-done subset).
  * forward-only branches in contained mode; CALL/RET/far/indirect/LOOP as
    the proven contained gadgets; SP is never written outside wild mode.
  * REP + string forces a MOV CW,0..12 count clamp; PORT stays in the even
    0x08..0xEE harness-safe band (never 0xFC done / 0xFE regs).

FUZZ v2 (plan D1) -- SEGMENT RANDOMIZATION BY DERIVED OFFSET.  Every segment
register is uniformly random over 16 bits and EVERY literal address the
generator emits is derived through `Bias.off()`, so the designed PHYSICAL
address is unchanged while the `ps` / A19-16 column -- dead zero in every seed
the old system ever produced -- becomes live.  See the `Bias` docstring for
the one rule; there is no table and no per-form case.

The generator does NOT modify gen_seq (its fz-seed RNG streams are frozen);
it imports only the byte-layout primitives (Prog + assemble, _imm_biased,
_mem_ea, the window constants, NOSP) and subclasses `Prog` for the two
absolute fixups that carry an address (`BiasProg`).

Returns a g-dict matching the gen_seq contract
(seed/instr/regs/ram/ivt/handlers/n_ins/forms/ins) plus provenance extras
(has_brkem, brkem_pos, has_halt, has_tf, wild, phys) so check_seq.compose(g)
and the fuzz classifier consume it unchanged.
"""
import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from gen_seq import (Prog, _imm_biased, _mem_ea, NOSP,  # noqa: E402
                     DATA_LO, DATA_HI, SP0)
import optable  # noqa: E402
import testimage as ti  # noqa: E402  (THE image map: anchor, code region, IHT)

# --------------------------------------------------------------------------- #
# THE ANCHOR (fuzz-v2 task T2 requirement 3).
#
# It is `testimage.ANCHOR0` and NOT a generator constant of its own, because a
# second copy of the map is exactly the thing that drifts.  The map places it at
# CODE_LO + 0x100, and that is the value this generator wants for its own
# reasons too:
#   * 256 bytes of 0xCC (INT3) apron BELOW it, so a backward runaway traps
#     within one page instead of walking out of the code region;
#   * 0xBE00 - 0x8100 = 15,616 bytes of headroom above it, ~15x the longest
#     body this generator can emit (raw payload <= 1024 B, soup <= ~600 B), so
#     a body can never reach the handler table or the terminator;
#   * it is inside [CODE_LO, CODE_HI), which is what `testimage.compose`
#     REQUIRES -- the v1 anchor 0x0500 is why every v2 compose raised.
ANCHOR = ti.ANCHOR0

# far-return stub, INSIDE the code region (v2).  It was at 0x0480, which is
# outside [CODE_LO,CODE_HI) and would therefore be counted an ESCAPE by
# `fuzz_classify.escaped_code_region`; it sits in the 0xCC apron below the
# anchor, where nothing else is ever placed.
STUB_AT = ti.CODE_LO + 0x40
IRET_AT = STUB_AT               # bare IRET
RETF_AT = STUB_AT + 1           # far-CALL return target
HANDLER_BYTES = [(IRET_AT, 0xCF), (RETF_AT, 0xCB)]

# windowed target band for wild-mode SP resync + string pointers
STR_SI_LO, STR_SI_HI = 0x2400, 0x2800
STR_DI_LO, STR_DI_HI = 0x2900, 0x2D00

# XLAT reads DS0:[BW+AL] with AL fully random, so BW must leave a whole page of
# headroom inside the data window (see emit_xlat).
XLAT_LO, XLAT_HI = DATA_LO, DATA_HI - 0x100

SEG_NAMES = ("PS", "SS", "DS0", "DS1")


class Bias:
    """Plan D1 -- segment randomization by DERIVED OFFSET.  ONE RULE:

        base_seg in [0, 0x1000);   per-register k in [0, 16)
        seg(name) = base_seg + k[name] * 0x1000
        off(phys) = (phys - base_seg * 16) & 0xFFFF

    Consequences, all of them exact and none of them a special case:

      * every segment register is UNIFORMLY RANDOM over 16 bits (0x1000
        base values x 16 k values = 0x10000, each once);
      * all four share their low 12 bits, so seg*16 agrees mod 2^16 and the
        PHYSICAL OFFSET of `off(p)` under ANY of them is exactly `p` -- which
        is the only domain that decodes on this rig (`test_mem.sv` wires
        addr[15:1] and leaves addr[19:16] unconnected);
      * a segment-override prefix therefore becomes a physical no-op while
        genuinely changing A19-16 -- the coverage the `ps` column wants;
      * IP and EA wrap are closed under it: `off` is taken mod 2^16 and the
        hardware adds mod 2^16 too, so no wrap needs handling anywhere.

    `any_seg(rng)` draws a FRESH k from the same family: a different A19-16
    with the same physical base.  It is the only thing that ever produces a
    segment VALUE other than the four register ones, and it is why
    `p_sreg_rand` can be 1.0 -- a random segment load is now contained."""

    def __init__(self, seed):
        rng = random.Random(f"bias/{seed}")
        self.base_seg = rng.randrange(0x1000)
        self.k = {nm: rng.randrange(16) for nm in SEG_NAMES}

    def seg(self, name):
        return self.base_seg + self.k[name] * 0x1000

    def any_seg(self, rng):
        return self.base_seg + rng.randrange(16) * 0x1000

    def off(self, phys):
        return (phys - self.base_seg * 16) & 0xFFFF

    def linear(self, phys):
        """The 20-bit PS-relative linear address of a physical byte (the
        domain `fuzz_accept`'s code-fetch rows are compared in)."""
        return ((self.seg("PS") << 4) + self.off(phys)) & 0xFFFFF


class BiasProg(Prog):
    """`Prog` with the two absolute fixups moved onto the bias helper.

    `gen_seq.Prog.assemble` patches a far JMP's off16 and a near-indirect
    MOV's imm16 from the module constant `PC0` and writes segment 0.  Both are
    v1 addresses.  This subclass re-patches them after the frozen parent pass,
    which keeps the forward-branch displacement logic in ONE place -- and it
    leaves `gen_seq` untouched, so no fz-seed stream moves."""

    def __init__(self, rng, bias):
        super().__init__(rng)
        self.b = bias
        self.abs_seg = {}          # ins_index -> segment word for a far JMP

    def emit_farjmp_next(self):
        self.abs_seg[len(self.ins)] = self.b.any_seg(self.rng)
        super().emit_farjmp_next()

    def assemble(self):
        raw = bytearray(Prog.assemble(self))
        sizes = [len(b) for b in self.ins]
        start = [0]
        for s in sizes:
            start.append(start[-1] + s)
        base = self.b.off(ANCHOR)
        for idx in self.abs_fixups:
            off = (base + start[idx + 1]) & 0xFFFF      # the NEXT instruction
            seg = self.abs_seg[idx]
            i = start[idx]
            raw[i + 1], raw[i + 2] = off & 0xFF, off >> 8
            raw[i + 3], raw[i + 4] = seg & 0xFF, seg >> 8
        for mov_idx, upto in self.reg_ip_fixups:
            off = (base + start[upto]) & 0xFFFF
            i = start[mov_idx]
            raw[i + 1], raw[i + 2] = off & 0xFF, off >> 8
        return bytes(raw)


def full_ivt(bias, rng):
    """Every vector EXCEPT the terminator's -> a handler-table slot.

    Vector `testimage.TERM_VECTOR` is composed by `testimage.compose` (it is
    the INT3 the 0xCC fill executes) and `compose` RAISES if a caller sets it,
    so it is absent here by construction rather than by filtering downstream.

    Each entry gets its own `k`, so the IVT itself carries the whole A19-16
    family: 255 far pointers whose segments differ and whose physical targets
    are all inside the handler table."""
    slots = [ti.IHT_AT + i * ti.IHT_STRIDE for i in range(ti.IHT_N)]
    return {n: (bias.any_seg(rng), bias.off(rng.choice(slots)))
            for n in range(256) if n != ti.TERM_VECTOR}


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
    p_illegal_mod3: float = 0.0   # emit the illegal LEA/BOUND mod=11 forms (0 =
                                  # never; small in survey campaigns for the
                                  # task-#30 accepted-class regression coverage)
    p_sreg_rand: float = 1.00     # DS0/DS1 load = a FRESH member of the segment
                                  # family (else the register's own value, an
                                  # inert reload).  Under plan D1 a "random"
                                  # segment is a different A19-16 with the same
                                  # physical base, so it no longer escapes the
                                  # window and no longer has to be rationed:
                                  # 0.40 -> 1.00.  `strict` still sets it to 0
                                  # to hold A19-16 constant across a run.
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
# memory-operand-REQUIRED ops in EA_MODRM_OPS: a mod=11 (register) encoding is
# illegal (LES/LDS are already _EA_SPECIAL/windowed). LEA-mod3 executes on the
# chip (loads the stale EA latch); BOUND-mod3 halts on both chip and core.
MEM_ONLY_EA = {0x8D, 0x62}
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


# --------------------------------------------------------------------------- #
# THE INTERRUPT MODIFICATION-HANDLER POOL (plan D8).
#
# ONE RULE: nothing in a handler may TRAP, BRANCH or TOUCH THE STACK.  A
# handler that traps re-enters a handler and recurses without bound -- and
# every entry pushes three words, so the recursion eats the stack as well as
# the clock.  It is the single most dangerous failure mode in the design and
# it is closed by construction, not by a runtime check.
#
# Mechanically the rule is "the register domain only", which is:
#   * FREE minus the SP writers (already out of FREE_OPS) minus the two
#     accumulator ops that DIVIDE -- D4 AAM traps on a zero base, and D5 AAD
#     rides with it as the same encoding pair;
#   * EA at mod=11, i.e. no memory operand at all, minus the two forms that
#     REQUIRE memory (8D LEA, 62 BOUND: mod=11 is illegal for both), minus the
#     group extensions that divide or push.
# CFLOW_FWD, CFLOW_GADGET, STACK, PORT, SREG, EVT_ONLY, BRKEM and UNDOC are
# whole policy classes that never enter either pool, so they need no naming
# here -- which is why this is one rule and not a per-opcode table.
HANDLER_TRAP_FREE = frozenset({0xD4, 0xD5})            # AAM / AAD
HANDLER_BANNED_EXT = frozenset({(0xF6, 6), (0xF6, 7),  # DIV / IDIV rm8
                                (0xF7, 6), (0xF7, 7),  # DIV / IDIV rm16
                                (0xFF, 6)})            # PUSH rm16


# ---------------------------------------------------------------------------
class Soup:
    def __init__(self, seed, knobs, evt_pin, wild, handler=False):
        self.rng = random.Random(f"soup/{seed}")
        self.k = knobs
        self.evt_pin = evt_pin        # None | 0=INT | 1=NMI | 2=POLL
        self.wild = wild
        self.handler = handler        # restricted pools: see the block above
        self.b = Bias(seed)
        self.p = BiasProg(self.rng, self.b)
        self.forms = []
        self.stackn = 0
        self.brkem_ins = []           # p.ins indices carrying a BRKEM
        self.has_halt = False
        self.has_tf = False
        self.lea_mod3 = []            # (ins_idx, dest_reg) for illegal LEA-mod3
        self.since_sp = 0             # instrs since last wild SP resync
        # the two draw pools.  A handler restricts them; nothing else does.
        self.free_ops = ([o for o in FREE_OPS if o.code not in HANDLER_TRAP_FREE]
                         if handler else FREE_OPS)
        self.ea_ops = ([o for o in EA_MODRM_OPS if o.code not in MEM_ONLY_EA]
                       if handler else EA_MODRM_OPS)

    def _exts(self, op):
        e = _safe_exts(op)
        if self.handler:
            e = [x for x in e if (op.code, x) not in HANDLER_BANNED_EXT]
        return e

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
            ea = self.b.off(_mem_ea(rng))           # even/odd data-window addr
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
        op = self.rng.choice(self.free_ops)
        imm = (_imm_biased(self.rng, 8 * op.imm).to_bytes(op.imm, "little")
               if op.imm else b"")
        self.p.emit(self._prefix() + bytes([op.code]) + imm)
        return "free"

    def emit_ea(self):
        op = self.rng.choice(self.ea_ops)
        rng = self.rng
        # LEA (8D) / BOUND (62) REQUIRE a memory operand; a mod=11 (register)
        # encoding is illegal. Default-exclude it (force a windowed mem form) so
        # the campaign never emits it; the p_illegal_mod3 knob (survey campaigns)
        # deliberately emits it for regression coverage of the fix + accept rule.
        mem_only = op.code in MEM_ONLY_EA
        illegal = mem_only and rng.random() < self.k.p_illegal_mod3
        if op.group:
            ext = rng.choice(self._exts(op))
            reg_field = ext
            write = op.code in (0xFE, 0xFF, 0xC6, 0xC7) or \
                (op.code in (0x80, 0x81, 0x82, 0x83, 0xC0, 0xC1,
                             0xD0, 0xD1, 0xD2, 0xD3) and ext != 7)
        else:
            reg_field = rng.choice(NOSP)
            write = op.code in (0x88, 0x89, 0x86, 0x87)  # store / xchg RMW
        if illegal:
            ea = bytes([0xC0 | (reg_field << 3) | rng.choice(NOSP)])  # mod=11
            if op.code == 0x8D:                     # LEA-mod3 provenance for the rule
                self.lea_mod3.append((len(self.p.ins), reg_field))
        elif mem_only:
            ea = self._ea(reg_field, write, force_windowed=True)  # never mod3
        else:
            ea = self._ea(reg_field, write)
        imm = b""
        if op.imm_extdep:                        # F6/F7: /0,/1 carry immediate
            if op.group and reg_field in (0, 1):
                nb = 2 if op.code == 0xF7 else 1
                imm = _imm_biased(rng, 8 * nb).to_bytes(nb, "little")
        elif op.imm:
            imm = _imm_biased(rng, 8 * op.imm).to_bytes(op.imm, "little")
        self.p.emit(self._prefix() + bytes([op.code]) + ea + imm)
        return "ea_illegal_mod3" if illegal else "ea"

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
        rng = self.rng
        op = rng.choice([0xC4, 0xC5])
        ea = rng.randrange(DATA_LO, DATA_HI - 4) & 0xFFFE
        off = rng.getrandbits(16)
        # the injected far pointer's SEGMENT word was hardcoded 0, which under
        # plan D1 is the ONE segment value that is not in the family -- loading
        # it would take DS0/DS1 off the shared physical base and every later
        # windowed EA with it.  It is a fresh family member instead: a real
        # A19-16 change, a physical no-op.
        seg = self.b.any_seg(rng)
        self.p.ram_set(ea, [off & 0xFF, off >> 8, seg & 0xFF, seg >> 8])
        eo = self.b.off(ea)
        self.p.emit(bytes([op, (rng.choice(NOSP) << 3) | 6,
                           eo & 0xFF, eo >> 8]))
        return "les_lds"

    def emit_moffs(self):
        op = self.rng.choice([0xA0, 0xA1, 0xA2, 0xA3])
        ea = self.b.off(_mem_ea(self.rng))
        self.p.emit(self._prefix() + bytes([op, ea & 0xFF, ea >> 8]))
        return "moffs"

    def emit_xlat(self):
        # XLAT reads DS0:[BW+AL] with AL whatever the stream left in it, so a
        # bare D7 is an EXISTING CONTAINMENT VIOLATION: BW is fully random and
        # the read lands at an arbitrary offset.  Windowed the same way
        # emit_string windows SI/DI -- an atomic MOV BW,<windowed>; D7 pair,
        # with a whole page of headroom above the target so BW+AL cannot leave
        # the data window for any AL.
        bw = self.b.off(self.rng.randrange(XLAT_LO, XLAT_HI))
        self.p.emit_atomic([bytes([0xBB, bw & 0xFF, bw >> 8]),   # MOV BW
                            self._prefix() + bytes([0xD7])])     # XLAT (read)
        return "xlat"

    def emit_string(self):
        rng = self.rng
        si = self.b.off(rng.randrange(STR_SI_LO, STR_SI_HI))
        di = self.b.off(rng.randrange(STR_DI_LO, STR_DI_HI))
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
        si = self.b.off(rng.randrange(STR_SI_LO, STR_SI_HI))
        iy = self.b.off(rng.randrange(STR_DI_LO, STR_DI_HI))
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
        bp = self.b.off(0x3FE0)
        sp = self.b.off(SP0)
        seq = [bytes([0xBD, bp & 0xFF, bp >> 8]),              # MOV BP,^0x3FE0
               bytes([0xC8, size & 0xFF, size >> 8, level])]
        if rng.random() < 0.5:
            seq.append(bytes([0xC9]))                          # DISPOSE
        seq.append(bytes([0xBC, sp & 0xFF, sp >> 8]))          # MOV SP,^0x3F00
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
            off = self.b.off(RETF_AT)
            seg = self.b.any_seg(rng)
            self.p.emit(bytes([0x9A, off & 0xFF, off >> 8,
                               seg & 0xFF, seg >> 8]))
            return "far_call"
        if r < 0.62:                                           # software INT
            # ONE rule: a DELIBERATE software interrupt targets a modification
            # handler, never the terminator.  Under v2 vector TERM_VECTOR is
            # the terminator (the 0xCC fill's INT3), so `CC` / `CD 03` would
            # end the seed at a uniformly random point in its own body -- a
            # valid dump, but roughly half the corpus truncated for nothing.
            # The INT3 OPCODE is exercised by the fill on every escape.
            if rng.random() < 0.5:
                n = rng.randrange(255)
                self.p.emit([0xCD, n + (n >= ti.TERM_VECTOR)])
            else:
                self.p.emit([0xCE])                            # INTO (vector 4)
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
        # a FRESH family member (new A19-16, same physical base) or the
        # register's own value (an inert reload).  Both are contained, which is
        # why p_sreg_rand is 1.0 by default now.
        val = (self.b.any_seg(rng) if rng.random() < self.k.p_sreg_rand
               else self.b.seg("DS1" if sreg == 0x00 else "DS0"))
        ea = rng.randrange(DATA_LO, DATA_HI - 2) & 0xFFFE
        self.p.ram_set(ea, [val & 0xFF, val >> 8])
        eo = self.b.off(ea)
        self.p.emit(bytes([0x8E, (sreg << 3) | 6, eo & 0xFF, eo >> 8]))
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
        sp = self.b.off(SP0)
        self.p.emit_atomic([bytes([0xBC]) + self.rng.getrandbits(16).to_bytes(2, "little"),
                            bytes([0xBC, sp & 0xFF, sp >> 8])])  # rand; ^0x3F00
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

    # --- the handler-body driver (plan D8) --------------------------------
    def build_handler(self, limit):
        """One handler body of at most `limit` bytes, drawn from the two
        RESTRICTED pools only.  compose appends the IRET, so a body cannot
        fall out of its slot and needs no terminator of its own.

        ONE extra rule, and it is about THE 0F SCRUB, not about opcodes: a
        handler body may not CONTAIN the byte 0x0F anywhere.  `scrub_0f`
        rewrites a `0F` and THE BYTE AFTER IT to `90 90`, and the byte after a
        0x0F immediate is the NEXT INSTRUCTION'S OPCODE -- so one boundary-
        crossing pair turns that instruction into a NOP and re-decodes its
        tail as fresh instructions, which is how a `C3` (RET) or a `CD`
        appears in a body that never emitted one.  On the last body byte the
        partner is the appended IRET itself.  The fuzz body may contain 0x0F
        freely; a handler may not, because a handler's safety is a claim about
        its DECODING and the scrub can move its boundaries.  (No handler
        opcode is 0x0F -- the pools carry none -- so this only ever rejects an
        immediate, and it costs one redraw.)"""
        assert self.handler, "build_handler on an unrestricted Soup"
        self.p = BiasProg(self.rng, self.b)
        rejects = 0
        while rejects < 64:
            mark = len(self.p.ins)
            (self.emit_free if self.rng.random() < 0.5 else self.emit_ea)()
            if 0x0F in b"".join(bytes(x) for x in self.p.ins[mark:]):
                del self.p.ins[mark:]
                rejects += 1
                continue
            if sum(len(x) for x in self.p.ins) > limit:
                del self.p.ins[mark:]
                break
        return b"".join(bytes(x) for x in self.p.ins)


def handler_bodies(seed, n=ti.IHT_N, limit=ti.IHT_STRIDE - 1):
    """The per-seed pool of `n` interrupt modification-handler bodies.

    A SECOND `Soup` instance with restricted knobs -- `handler=True` narrows
    the two pools per the rule stated above, and `p_window_ea=0` forces every
    EA to mod=11.  No new emitter and no new opcode list, which is the point:
    the bodies are drawn from the same generator the fuzz body is."""
    s = Soup(f"hand/{seed}",
             SoupKnobs(p_window_ea=0.0, p_brkem=0.0, p_undoc=0.0, p_tf=0.0,
                       p_halt=0.0, p_illegal_mod3=0.0),
             evt_pin=None, wild=False, handler=True)
    return [s.build_handler(limit) for _ in range(n)]


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
    b = s.b

    # brkem / LEA-mod3 provenance: the 20-bit PS-RELATIVE LINEAR address of the
    # instruction, which is the domain `fuzz_accept`'s code-fetch rows carry
    # (`ad_addr & 0xFFFFF`).  Under plan D1 that is no longer the same number
    # as the physical offset.
    sizes = [len(x) for x in s.p.ins]
    def _lin(idx):
        return ((b.seg("PS") << 4) + b.off(ANCHOR) + sum(sizes[:idx])) & 0xFFFFF
    brkem_pos = [(idx, _lin(idx)) for idx in s.brkem_ins]
    _rname = ["AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY"]
    lea_mod3_pos = [(_lin(idx), _rname[reg]) for idx, reg in s.lea_mod3]

    ix_phys = rng0.randrange(STR_SI_LO, STR_SI_HI)
    iy_phys = rng0.randrange(STR_DI_LO, STR_DI_HI)
    regs = {"PS": b.seg("PS"), "PC": b.off(ANCHOR),
            "SS": b.seg("SS"), "SP": b.off(SP0),
            "DS0": b.seg("DS0"), "DS1": b.seg("DS1"),
            "PSW": 0xF202,
            "AW": rng0.getrandbits(16), "BW": rng0.getrandbits(16),
            "CW": rng0.getrandbits(16), "DW": rng0.getrandbits(16),
            "BP": rng0.getrandbits(16),
            "IX": b.off(ix_phys), "IY": b.off(iy_phys)}
    ram = [(a, rng0.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += [(a, rng0.getrandbits(8)) for a in range(0x3E00, 0x4000)]
    for addr, data in s.p.ram_over:
        ram += [(addr + i, x) for i, x in enumerate(data)]
    ram += HANDLER_BYTES

    return dict(seed=seed, instr=instr, regs=regs, ram=ram,
                ivt=full_ivt(b, rng0), handlers=handler_bodies(seed),
                n_ins=len(s.p.ins), forms=s.forms,
                ins=[bytes(x) for x in s.p.ins],
                has_brkem=bool(brkem_pos), brkem_pos=brkem_pos,
                lea_mod3_pos=lea_mod3_pos,
                # the DESIGNED physical address behind each (seg, off) pair --
                # what the bias lint checks the derivation against
                phys={"PC": ANCHOR, "SP": SP0, "IX": ix_phys, "IY": iy_phys},
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
