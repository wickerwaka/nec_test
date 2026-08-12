#!/usr/bin/env python3
"""ghost_pred_cell -- THE DIRECTED BOARD CELL on the `8F` mod=3 GHOST-READ
ADDRESS **PREDICATE**: when does silicon decorate the rail with an AND, and
when does it take it bare?

WHY IT EXISTS.  Four waves have stopped at the same wall and every one of them
named the same blocker.

  * **wave-4** (`fz2_w4_ghostaddr_results_2026-08-10.md`) measured THREE seats
    -- `fz2c/410008`, `fz2e/519016`, `fz2e/520040` -- where the CHIP performs
    the AND and the core did not, and landed `ghost_bus_off = ghost_off & SP`
    unconditionally.  Its own closing sentence: *"THE AND IS NOT UNIVERSAL AND
    THIS LANDING DOES NOT CLAIM IT IS ... The two free choices left standing
    are WHICH RAIL and WHETHER THE AND HAPPENS."*
  * **wave-6** refuted the single-rail hypothesis (`IND` at dist 0, `M_EA` at
    dist 1, intersection EMPTY).
  * **wave-7** refuted the retained-flop reformulation (0 closures, 2 LOST).
  * **wave-8** could not evaluate its derivation AT ALL: **n = 1**, and on that
    one seat `IND == SP == ec50`, so the candidate rails were degenerate.
  * **M10-SYS** (wave-9) fixed the INSTRUMENT (13/13 solved where the old leg
    solved 7/13) and got the population to **two** speaking seats -- both
    **UNDECORATED**, `SS:<register>` bit-exact -- *"and in exactly wave-8's way:
    on both speaking seats the undecorated value is held simultaneously by
    `SP`, `TMPB` and `IND`."*

**THE BANKED CORPUS CANNOT DISCRIMINATE.**  Its seeds are random programs; on
every seat that speaks, the candidate rails happen to hold the same number.
Two seats with the same three-way degeneracy discriminate no better than one.

**THE FIX IS CONSTRUCTION, NOT MORE FUZZ.**  This cell builds programs in which
every candidate rail holds a DISTINCT, RECOGNISABLE value at the `8F`, and reads
the ghost read's address straight off the pins.

THE OBSERVABLE IS ENGINE-FREE AND IT IS ONE 20-BIT NUMBER.  `8F /r` with
`mod == 3` issues exactly ONE memory read.  On the socketed chip that read goes
to a STALE address; the ucore sends it to `SS:(ghost_off & SP)`.  The cell reads
the `T1` address of that cycle and decodes it into (segment, offset), and the
offset into a NAMED sentinel by table lookup.  Nothing here decodes an opcode,
runs an engine or consults a golden.

THE SENTINEL ALPHABET IS THE WHOLE TRICK.  `SP` is given the mask value
`0xF0F0`; every other sentinel carries exactly ONE bit inside that mask and ONE
bit outside it, and no two share either bit.  Therefore

    bare X_i          two bits, one of them OUTSIDE SP's mask   -> NOT an AND
    X_i & SP          exactly one bit, INSIDE the mask          -> AN AND
    X_i & X_j         zero                                      -> a rail-pair AND
    X_i | X_j         four bits                                 -> a wired OR
    SP itself         0xF0F0 (bit 4 belongs to no sentinel)     -> the plain pop

are ALL DISTINCT VALUES and every one of them names itself.  That is the
property the banked corpus does not have and cannot be given.

THE PROGRAM.  `R` identical blocks of `BLOCK` bytes:

    <pre>        the rail-loading preamble + the PREDECESSOR class
    8F C3        the probe -- POP BW, mod = 3
    90 90 ...    pad to BLOCK

Every block re-arms `SP` with `MOV SP, imm16`, so the R blocks are R
INDEPENDENT REPEATS of one measurement rather than a drifting sequence.

THE THREE DISCRIMINATOR BANDS, DECLARED BEFORE THE RUN and grounded in the
MEASURED rails (`rails`, offline, committed with the pre-registration):

    D3  ALU/MUL (`alu88` `alu44` `alu08` `mul` `imul`).  The ALU result is what
        lands in `TMPA` -- measured, not assumed -- so the addends are chosen to
        PUT A NAMED SENTINEL THERE: 0x8800, 0x4400, 0x0088, 0x1100, 0x1100.
        H-A predicts `SS:(X & SP)`; H-B and H-C predict `SS:X`.  This band is
        the AND's own discriminator and it is five legs wide.
    D2  ModR/M-mem (`mem3`/`mem3r` carry a rail with bits outside SP's mask).
        H-A and H-B predict the ANDed value; H-C predicts the bare one.
    D1  POP-class (`pop1`/`pop2`).  The last BUS address is 0x8800 while SP is
        0xF0F0 and NO core register holds 0x8800 at the probe -- so this band
        alone can see H-E, wave-6's stale-MAR reading, and it is the only place
        the chip can show a rail the ucore has already forgotten.

D3 separates H-A from {H-B,H-C}; D2 separates {H-A,H-B} from H-C; D1 separates
H-E from all of them.  Together they name exactly one -- or none of them, which
is a finding and is reported as one.

BOARD DISCIPLINE (CLAUDE.md), in code: single-writer asked of the board before
the first capture; SOCKET ONLY (`use_core=False`, passed explicitly, because the
board's CFG is sticky); NO FLASHING anywhere and the flash pin is recorded; the
divider PINNED and `div_guard`'s readback RECORDED at every stratum boundary;
the FULL per-clock capture words retained with a sha256 per cell; `board_idle()`
at the end; three consecutive transport errors STOP the cell.  THIS CELL DRIVES
NO PIN -- there is no `evt`, no hold, no `fired`, and none of INV-1's
directive-truncation exposure.

Usage:
    python3 sw/ghost_pred_cell.py show                # offline, the programs
    python3 sw/ghost_pred_cell.py predict             # offline, the hypotheses
    python3 sw/ghost_pred_cell.py calib               # offline (tb_sys)
    python3 sw/ghost_pred_cell.py rails [--legs ...]  # offline (tb_sys + M10-SYS)
    python3 sw/ghost_pred_cell.py core  [--legs ...]  # offline (tb_sys ret)
    python3 sw/ghost_pred_cell.py run   [--legs ...]  # BOARD, socket only
    python3 sw/ghost_pred_cell.py score
    python3 sw/ghost_pred_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage as ti                                    # noqa: E402

OUT = ROOT / "sw" / "testdata" / "ghost-pred"
CALIB = OUT / "calib.json"
PRED = OUT / "predictions.json"

# --------------------------------------------------------------------------- #
# THE SEGMENTS.  Bases 0x08000 / 0x20000 / 0x40000 / 0x60000 -- chosen so the
# four 64 KB windows [base, base+0xFFFF] are PAIRWISE DISJOINT, which makes the
# (segment, offset) decode of a 20-bit pin address UNIQUE.  The board's memory
# is the 64 KB image mirrored through the 1 MB space, so every one of them
# addresses the same bytes and no placement changes meaning.
# --------------------------------------------------------------------------- #
SEG = {"CS": 0x0800, "SS": 0x2000, "DS": 0x4000, "ES": 0x6000}
SEG_BASE = {k: v << 4 for k, v in SEG.items()}


def SSp(off):
    return (SEG_BASE["SS"] + off) & 0xFFFFF


def DSp(off):
    return (SEG_BASE["DS"] + off) & 0xFFFFF


def ESp(off):
    return (SEG_BASE["ES"] + off) & 0xFFFFF


# --------------------------------------------------------------------------- #
# THE SENTINEL ALPHABET.  `A_SP` is the mask; every other value is
# (one bit inside the mask) | (one bit outside it), all bits unique.
# --------------------------------------------------------------------------- #
A_SP = 0xF0F0            # mask bits 15 14 13 12  7 6 5 4   (bit 4 is SP's own)
A_POP = 0x8800           # 15 | 11
E1 = 0x4400              # 14 | 10
E2 = 0x2200              # 13 |  9
E3 = 0x1100              # 12 |  8
V1 = 0x0088              #  7 |  3
V2 = 0x0044              #  6 |  2
E_SEG = 0x0022           #  5 |  1

SENT = {"SP": A_SP, "A_POP": A_POP, "E1": E1, "E2": E2, "E3": E3,
        "V1": V1, "V2": V2, "E_SEG": E_SEG}

# every value the reader can NAME, and what it means.  Built mechanically from
# the alphabet -- there is no hand-written constant in this table.
def _label_table():
    t = {}
    for n, v in SENT.items():
        t.setdefault(v, f"{n}")
        t.setdefault((v + 2) & 0xFFFF, f"{n}+2")
    for n, v in SENT.items():
        if n == "SP":
            continue
        t.setdefault(v & A_SP, f"{n}&SP")
        t.setdefault(v | A_SP, f"{n}|SP")
    names = [n for n in SENT if n != "SP"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            t.setdefault(SENT[a] | SENT[b], f"{a}|{b}")
    t.setdefault(0x0000, "ZERO")
    # the odd second half of a split word
    for v, n in list(t.items()):
        t.setdefault((v + 1) & 0xFFFF, f"{n}+1")
    return t


LABEL = _label_table()

# recognisable data words, one per candidate address, so the POPPED VALUE is a
# second, independent channel naming the address that was actually read.
def _ram():
    r = []
    tag = 0x10

    def put(off, w):
        r.append((off & 0xFFFF, w & 0xFF))
        r.append(((off + 1) & 0xFFFF, (w >> 8) & 0xFF))

    for n, v in SENT.items():
        if n == "E_SEG":
            continue
        put(v, 0xDA00 | tag)
        put(v + 2, 0xDA01 | tag)
        if n != "SP":
            put(v & A_SP, 0xDB00 | tag)
        tag += 0x10
    # the `8E` leg reloads DS from memory; the word there is DS's OWN value, so
    # the segment map is a fixed point and every block is identical.
    put(E_SEG, SEG["DS"])
    return r


RAM = _ram()

REGS = {"PS": SEG["CS"], "PC": ti.ANCHOR0 - (SEG["CS"] << 4),
        "SS": SEG["SS"], "DS0": SEG["DS"], "DS1": SEG["ES"],
        "SP": A_SP, "AW": 0, "BW": 0, "CW": 0, "DW": 0,
        "BP": 0, "IX": 0, "IY": 0}

# --------------------------------------------------------------------------- #
# encodings -- raw bytes, no assembler, so the image is a pure function of this
# file.  R_* are the ModR/M / opcode register numbers.
# --------------------------------------------------------------------------- #
R_AW, R_CW, R_DW, R_BW, R_SP, R_BP, R_IX, R_IY = range(8)


def movi(r, v):                       # MOV r16, imm16
    return bytes([0xB8 + r, v & 0xFF, (v >> 8) & 0xFF])


def movm(r, a):                       # MOV r16, [disp16]
    return bytes([0x8B, 0x06 | (r << 3), a & 0xFF, (a >> 8) & 0xFF])


def movms(r, a):                      # MOV [disp16], r16
    return bytes([0x89, 0x06 | (r << 3), a & 0xFF, (a >> 8) & 0xFF])


def popr(r):                          # POP r16 (documented)
    return bytes([0x58 + r])


PROBE = bytes([0x8F, 0xC0 | R_BW])            # 8F C3 -- POP BW, mod = 3
SEG_ES = bytes([0x26])                        # ES: override

BLOCK = 32
R = 5
WAITS = (0, 1, 2, 3)
ALIGNS = (0, 1, 2, 3)

BS_INTA, BS_IOR, BS_IOW, BS_HALT, BS_CODE, BS_MEMR, BS_MEMW, BS_PASV = range(8)
IVT3_OFF = 0x0000C                    # vector 3's low half: the test phase ends

# --------------------------------------------------------------------------- #
# THE LEGS.
#
# Each is (pre, probe, [expected preamble MEMR addresses], class, note).
# `class` is the DECLARED role: "D1" and "D2" are the two discriminators, "X" is
# exploratory (declared non-discriminating IN ADVANCE), "N" is a NULL control.
# --------------------------------------------------------------------------- #
LEGS = {
    # ---- register-only predecessors: no memory op in the block at all.
    #      The ALU RESULT is what lands in `TMPA` (measured, `rails`), so the
    #      three ADD legs PUT A CHOSEN SENTINEL IN THE RAIL: the addends are
    #      picked so the sum is `A_POP`, `E1` and `V1`, whose `&SP` images are
    #      distinct named values.  That is what makes them the AND's own
    #      discriminators.
    "alu88": (movi(R_AW, 0x8000) + movi(R_BW, 0x0800) + bytes([0x01, 0xD8]),
              PROBE, [], "D3",
              "ADD AW,BW = 0x8800 (A_POP) -- bare 8800 vs ANDed 8000"),
    "alu44": (movi(R_AW, 0x4000) + movi(R_BW, 0x0400) + bytes([0x01, 0xD8]),
              PROBE, [], "D3",
              "ADD AW,BW = 0x4400 (E1) -- bare 4400 vs ANDed 4000"),
    "alu08": (movi(R_AW, 0x0080) + movi(R_BW, 0x0008) + bytes([0x01, 0xD8]),
              PROBE, [], "D3",
              "ADD AW,BW = 0x0088 (V1) -- the same question at the bottom of "
              "the word: bare 0088 vs ANDed 0080"),
    "mul": (movi(R_AW, 0x0110) + movi(R_BW, 0x0010) + bytes([0xF7, 0xE3]),
            PROBE, [], "D3",
            "MUL BW -- the F7 /4 register form, product 0x1100 (E3)"),
    "imul": (movi(R_AW, 0x0110) + bytes([0x69, 0xD8, 0x10, 0x00]),
             PROBE, [], "D3",
             "IMUL BW,AW,0x0010 = 0x1100 -- the 14'h0104 native-PLA class the "
             "RTL's `ghost_uses_mul_hi` arm names and wave-4 measured INERT on "
             "654 seeds because no seed reached it"),
    # ---- POP-class: the bus address and SP are FAR APART -- D1 --------------
    "pop0": (popr(R_BW), PROBE, [SSp(A_SP)], "X",
             "POP BW with the stack AT the SP sentinel: bus 0xF0F0, SP 0xF0F2 "
             "-- the DEGENERATE control that reproduces the banked corpus"),
    "pop1": (movi(R_SP, A_POP) + popr(R_BW) + movi(R_SP, A_SP),
             PROBE, [SSp(A_POP)], "D1",
             "POP BW at 0x8800, then SP re-armed to 0xF0F0 -- bus address and "
             "SP are 0x8800 apart and every AND of them is named"),
    "pop2": (movi(R_SP, A_POP) + popr(R_BW) + popr(R_CW) + movi(R_SP, A_SP),
             PROBE, [SSp(A_POP), SSp(A_POP + 2)], "D1",
             "two pops: the last bus address is 0x8802, one word past the "
             "first -- says WHICH pop, not just which register"),
    # ---- ModR/M-memory predecessors -- D2 -----------------------------------
    "mem1": (movm(R_AW, E3), PROBE, [DSp(E3)], "D2",
             "MOV AW,[0x1100] -- one ModR/M EA, SP untouched"),
    "mem3": (movm(R_AW, E1) + movm(R_BW, E2) + movm(R_CW, E3),
             PROBE, [DSp(E1), DSp(E2), DSp(E3)], "D2",
             "a THREE-DEEP EA staircase 0x4400 -> 0x2200 -> 0x1100: which "
             "rung answers names the depth of the latch"),
    "mem3r": (movm(R_AW, E3) + movm(R_BW, E2) + movm(R_CW, E1),
              PROBE, [DSp(E3), DSp(E2), DSp(E1)], "D2",
              "the staircase REVERSED -- the control that separates `the last "
              "EA` from `a fixed slot in the block`"),
    "memw": (movi(R_AW, 0xDA40) + movms(R_AW, E2), PROBE, [], "D2",
             "a memory WRITE predecessor (the WB_EA rail).  It writes the word "
             "that is already there, so the image is a fixed point"),
    "popmem": (movi(R_SP, A_POP) + popr(R_BW) + movi(R_SP, A_SP)
               + movm(R_AW, E3),
               PROBE, [SSp(A_POP), DSp(E3)], "D2",
               "POP then EA: both rails are hot and the EA is the LATER one"),
    "mempop": (movi(R_SP, A_POP) + movm(R_AW, E3) + popr(R_BW)
               + movi(R_SP, A_SP),
               PROBE, [DSp(E3), SSp(A_POP)], "D1",
               "EA then POP: both rails are hot and the POP is the LATER one "
               "-- the mirror of `popmem`"),
    "mov8e": (bytes([0x8E, 0x1E, E_SEG & 0xFF, E_SEG >> 8]),
              PROBE, [DSp(E_SEG)], "D2",
              "MOV DS,[0x0022] -- the `pe_opc_reg == 8'h8e` case the RTL "
              "carries and wave-4 measured INERT.  The word read is DS's own "
              "value, so the segment map does not move"),
    "pfxmem": (SEG_ES + movm(R_AW, E3), PROBE, [ESp(E3)], "D2",
               "ES: MOV AW,[0x1100] -- a segment override on the PREDECESSOR"),
    "pfxpro": (movm(R_AW, E3), SEG_ES + PROBE, [DSp(E3)], "X",
               "ES: 8F C3 -- a segment override on the PROBE.  Answers "
               "`fz2e/526054`'s segment fork directly"),
    # ---- NULL controls: mod != 3, no ghost ----------------------------------
    "n_pop": (movi(R_SP, A_POP) + popr(R_BW) + movi(R_SP, A_SP),
              popr(R_AW), [SSp(A_POP)], "N",
              "THE NULL: the identical preamble and a DOCUMENTED `POP AW`.  "
              "Its read MUST be at SS:SP exactly -- this is the positive "
              "control for the reader itself"),
    "n_mod0": (movi(R_SP, A_POP) + popr(R_BW) + movi(R_SP, A_SP),
               bytes([0x8F, 0x06, E2 & 0xFF, E2 >> 8]), [SSp(A_POP)], "N",
               "THE mod != 3 NULL: `8F /0` with a real ModR/M memory operand. "
               "Reproduces FLASH #13's 130/130 control on a directed program"),
}

# --------------------------------------------------------------------------- #
# THE SLED FAMILY -- A DECLARED **POST-HOC** SUB-SWEEP, ADDED AFTER THE
# REGISTERED GRID WAS SCORED AND LABELLED AS SUCH.
#
# The registered grid found the AND switching on the (`waits`, `align`) axes
# with the RAIL and the PREDECESSOR held fixed, which no registered hypothesis
# predicts.  These legs separate the two readings of that: `align` moves the
# WHOLE body's byte phase, while `sl<N>` inserts N NOPs BETWEEN the predecessor
# and the probe -- moving the probe's own byte phase and the queue's state
# without moving anything else.  Nothing here is scored against a registered
# bar; it is characterisation and it is reported as characterisation.
# --------------------------------------------------------------------------- #
for _n in range(8):
    LEGS[f"sl{_n}"] = (movi(R_AW, 0x8000) + movi(R_BW, 0x0800)
                       + bytes([0x01, 0xD8]) + bytes([0x90]) * _n,
                       PROBE, [], "S",
                       f"alu88 with {_n} NOPs between the ADD and the probe "
                       f"-- POST-HOC, the queue-phase axis")

# --------------------------------------------------------------------------- #
# THE VALIDATION FAMILY -- SIX LEGS THAT DID NOT SELECT THE KEY.
#
# The standing rule (CLAUDE.md): *"A refuted key's REPLACEMENT must be validated
# on data that was not used to select it."*  The `dQS` key was selected on the
# NINE discriminating legs of the registered grid; every leg here is a DIFFERENT
# opcode, of a different length, reaching the same rail value by a different
# route, and none of its blocks existed when the key was chosen.  The frozen map
# is `docs/notes/ghost_pred_cell_key_2026-08-11.md`, committed before these were
# captured.
# --------------------------------------------------------------------------- #
_V = {
    "v_sub":  (movi(R_AW, 0x8808) + movi(R_BW, 0x0008) + bytes([0x29, 0xD8]),
               "SUB AW,BW = 0x8800 -- a different ALU opcode, same rail"),
    "v_or":   (movi(R_AW, 0x8000) + movi(R_BW, 0x0800) + bytes([0x09, 0xD8]),
               "OR AW,BW = 0x8800"),
    "v_inc":  (movi(R_AW, 0x87FF) + bytes([0x40]),
               "INC AW = 0x8800 -- a ONE-BYTE predecessor, block 2 bytes shorter"),
    "v_shl":  (movi(R_AW, 0x4400) + bytes([0xD1, 0xE0]),
               "SHL AW,1 = 0x8800 -- a shift, not an adder"),
    "v_neg":  (movi(R_AW, 0x7800) + bytes([0xF7, 0xD8]),
               "NEG AW = 0x8800 -- the F7 group, register form"),
    "v_lea":  (bytes([0x8D, 0x06, 0x00, 0x88]),
               "LEA AW,[0x8800] -- a ModR/M form with NO memory access"),
}
for _k, (_pre, _n) in _V.items():
    LEGS[_k] = (_pre, PROBE, [], "V", _n)

LEG_ORDER = list(LEGS)
D1 = [k for k, v in LEGS.items() if v[3] == "D1"]
D2 = [k for k, v in LEGS.items() if v[3] == "D2"]
D3 = [k for k, v in LEGS.items() if v[3] == "D3"]
NULLS = [k for k, v in LEGS.items() if v[3] == "N"]
SLED = [k for k, v in LEGS.items() if v[3] == "S"]
VALID = [k for k, v in LEGS.items() if v[3] == "V"]

# THE LAST BUS ADDRESS BEFORE THE PROBE, known by construction from the block.
# `None` means the block contains no bus data cycle of its own, so the last one
# is the PREVIOUS block's own ghost -- disclosed, not guessed.
LAST_BUS = {k: (v[2][-1] if v[2] else None) for k, v in LEGS.items()}
LAST_BUS["memw"] = DSp(E2)          # a WRITE, and the only one in the family
LAST_BUS["n_pop"] = SSp(A_POP)
LAST_BUS["n_mod0"] = SSp(A_POP)
# the EA path wrote the address latch last (H-B's predicate)
EA_LAST = {k: (LEGS[k][3] == "D2") for k in LEGS}

# --------------------------------------------------------------------------- #
# THE HYPOTHESES.  `rail` is the value the wave-6/7 reading calls "the last
# latched memory address" at the probe; `and_when` is the predicate each
# hypothesis puts on the AND.  A leg with `rail = None` is DECLARED
# NON-DISCRIMINATING before the run and is reported, never scored.
#
#   H-A  predecessor-type selection with an UNCONDITIONAL AND  (wave-4's law)
#   H-B  the AND happens iff the EA path was the last writer of the latch
#   H-C  the AND never happens -- M10-SYS's two undecorated seats, generalised
#   H-D  the null: the ghost is the plain stack address SS:SP
# --------------------------------------------------------------------------- #
SP_AT_PROBE = {k: (A_SP + 2 if k in ("pop0",) else A_SP) for k in LEGS}


def _rails():
    """The MEASURED core rails at each leg's ghost row (`rails` subcommand).

    They characterise the STIMULUS -- what this program puts in which named
    register -- and they are taken OFFLINE, on `tb_sys ret`, and committed with
    the pre-registration BEFORE the board is touched.  They are not silicon and
    nothing about silicon is derived from them; they are what turns
    "hypothesis H-A" into "H-A predicts THIS 20-bit number on THIS leg"."""
    p = OUT / "rails" / "rails.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return {r["leg"]: r for r in d["rows"] if r.get("ok")}


def ghost_off_of(terms, leg):
    """`v30u_eu.sv:1481-1493`, evaluated on frozen registers -- the RTL's own
    expression, transcribed, with no free parameter."""
    ea = int(terms["EA_RESIDUE"], 16)
    ta = int(terms["TMPA"], 16)
    if ea != ta:                                   # ghost_uses_ea
        return ea if leg == "mov8e" else (ea & 0xFFFE)
    return ta


def predictions(leg, rails=None):
    """{hypothesis: predicted 20-bit ADDRESS or None} for one leg.

      H-A  wave-4's landed law: the rail, ANDed with SP, UNCONDITIONALLY
      H-B  the AND happens iff the EA path was the last writer of the latch
      H-C  M10-SYS's two undecorated seats generalised: the AND never happens
      H-D  the null: the plain stack address SS:SP
      H-E  wave-6's stale-MAR reading: the LAST BUS ADDRESS, segment and all --
           a value NO core register holds on the POP legs, which is why it is
           registered separately and why `pop1` can see it at all
    """
    rails = _rails() if rails is None else rails
    sp = SP_AT_PROBE[leg]
    ss = SEG_BASE["SS"]
    out = {"H-D": (ss + sp) & 0xFFFFF, "H-E": LAST_BUS[leg]}
    r = rails.get(leg)
    if leg in NULLS or r is None:
        out.update({"H-A": None, "H-B": None, "H-C": None})
        if leg in NULLS:
            out.update({"H-A": out["H-D"], "H-B": out["H-D"],
                        "H-C": out["H-D"], "H-E": out["H-D"]})
        return out
    go = ghost_off_of(r["terms"], leg)
    spm = int(r["terms"]["SP"], 16)
    out["H-A"] = (ss + (go & spm)) & 0xFFFFF
    out["H-C"] = (ss + go) & 0xFFFFF
    out["H-B"] = out["H-A"] if EA_LAST[leg] else out["H-C"]
    out["ghost_off"] = go
    return out


# --------------------------------------------------------------------------- #
# the program
# --------------------------------------------------------------------------- #
def block_of(leg):
    pre, probe, _rd, _cl, _n = LEGS[leg]
    blk = movi(R_SP, A_SP) if leg not in ("pop1", "pop2", "mempop", "popmem",
                                          "n_pop", "n_mod0") else b""
    blk = blk + pre + probe
    if len(blk) > BLOCK - 2:
        raise ValueError(f"leg {leg}: block is {len(blk)} bytes, "
                         f"BLOCK is {BLOCK}")
    return blk + bytes([0x90]) * (BLOCK - len(blk))


def body_of(leg, align):
    """`align` NOPs, R identical blocks, then SP re-armed to a SAFE stack
    before the fall-through into the 0xCC (INT3) fill."""
    tail = movi(R_SP, 0x3F00) + bytes([0x90]) * 4
    return bytes([0x90]) * align + block_of(leg) * R + tail


def image_of(leg, align):
    img, meta = ti.compose(regs=REGS, instr=body_of(leg, align), ram=RAM)
    return bytes(img), meta


def image_sha(leg, align):
    return hashlib.sha256(image_of(leg, align)[0]).hexdigest()


def n_pre(leg):
    return len(LEGS[leg][2])


def stratum_key(leg, waits):
    return f"{leg}_w{waits}"


def cell_key(leg, waits, align):
    return f"{leg}_w{waits}_a{align}"


# --------------------------------------------------------------------------- #
# the decode -- pins only, no engine
# --------------------------------------------------------------------------- #
def decode_addr(a):
    """(segment, offset, label) for a 20-bit pin address, or (None, None, hex)
    when it lies in no segment's own 64 KB window."""
    for s, b in SEG_BASE.items():
        if b <= a <= b + 0xFFFF:
            off = a - b
            return s, off, LABEL.get(off, f"?{off:04x}")
    return None, None, f"??{a:05x}"


def _rows_from_words(words):
    """Decode + trim reset, exactly `s10_board.capture`'s row semantics."""
    from analyze_capture import decode_words
    recs = decode_words(words)
    rel = next((i for i, r in enumerate(recs) if not r["rst"]), 0)
    rows = recs[rel:]
    for r in rows:
        if r["t"] in (0, 5):
            r["bs_early"] = r["bs_late"]
    return rows


def _txns(rows):
    out = []
    for i, r in enumerate(rows):
        if r["t"] == 1:
            out.append([i, r["bs_early"], r["ad_addr"], None])
        elif r["t"] in (3, 4) and out:
            out[-1][3] = r["ad_data"]
    return out


def features(rows, leg, align, meta):
    """Every measured quantity this cell reports, off the pins.

    `ok` is False when the cell is STRUCTURALLY INVALID -- the anchor T1 is not
    in the window, the test phase does not close, or the number of MEMR cycles
    is not `R * (n_pre + 1)`.  Those cells are RETAINED and REPORTED, never
    silently dropped, and the full ordered MEMR list is kept either way so the
    scorer can be revised without re-capturing."""
    anchor = meta["anchor_linear"]
    f = {"ok": False, "why": None, "n_rows": len(rows)}
    tx = _txns(rows)
    a = next((k for k, (_i, b, ad, _d) in enumerate(tx)
              if b == BS_CODE and ad == anchor), None)
    f["anchor_txn"] = a
    if a is None:
        f["why"] = "anchor T1 not in the capture window"
        return f

    end = None
    for k in range(a, len(tx)):
        _i, b, ad, _d = tx[k]
        if (b == BS_MEMR and ad == IVT3_OFF) or b == BS_IOW:
            end = k
            break
    f["test_end_txn"] = end
    if end is None:
        f["why"] = "the test phase never closed (no vector-3 read, no IOW)"
        return f

    reads = [[i, ad, d] for i, b, ad, d in tx[a:end] if b == BS_MEMR]
    writes = [[i, ad, d] for i, b, ad, d in tx[a:end] if b == BS_MEMW]
    f["memr"] = [[i, f"{ad:05x}", (None if d is None else f"{d:04x}")]
                 for i, ad, d in reads]
    f["n_memr"] = len(reads)
    f["n_memw"] = len(writes)
    f["n_code"] = sum(1 for _i, b, _a, _d in tx[a:end] if b == BS_CODE)

    npre = n_pre(leg)
    want = R * (npre + 1)
    f["n_memr_expected"] = want
    if len(reads) != want:
        f["why"] = (f"{len(reads)} MEMR cycles, expected {want} "
                    f"({R} blocks x ({npre} preamble + 1 probe))")
        if len(reads) == R * (npre + 2):
            f["why"] += "  [= R*(n_pre+2): every probe read may have SPLIT]"
        return f

    exp = LEGS[leg][2]
    ghosts, pre_ok = [], True
    for k in range(R):
        blk = reads[k * (npre + 1):(k + 1) * (npre + 1)]
        for j, want_a in enumerate(exp):
            if blk[j][1] != want_a:
                pre_ok = False
        i, ad, d = blk[npre]
        s, off, lab = decode_addr(ad)
        ghosts.append({"block": k, "row": i, "addr": ad, "seg": s,
                       "off": off, "label": lab,
                       "data": d, "txn_addr": f"{ad:05x}"})
    f["pre_ok"] = pre_ok
    f["ghost"] = ghosts
    f["ghost_addr"] = [g["addr"] for g in ghosts]
    f["ghost_label"] = [g["label"] for g in ghosts]
    f["ghost_seg"] = sorted({g["seg"] for g in ghosts}, key=str)
    f["ghost_off"] = [g["off"] for g in ghosts]
    f["uniform"] = len(set(f["ghost_addr"])) == 1
    f["mode_addr"] = Counter(f["ghost_addr"]).most_common(1)[0][0]
    s, off, lab = decode_addr(f["mode_addr"])
    f["mode_seg"], f["mode_off"], f["mode_label"] = s, off, lab
    f["ok"] = True
    if not pre_ok:
        f["why"] = "preamble MEMR addresses are not the composed ones"
    return f


# --------------------------------------------------------------------------- #
# the grid
# --------------------------------------------------------------------------- #
def grid(legs=None):
    return [(p, w, al) for p in (legs or LEG_ORDER)
            for w in WAITS for al in ALIGNS]


def ncap_for(waits, cal=None):
    if cal:
        v = cal.get("ncap", {}).get(str(waits))
        if v:
            return v
    return min(4090, 1400 + 700 * waits)


def _select(arg):
    if not arg:
        return LEG_ORDER
    want = [x for x in arg.split(",") if x]
    bad = [x for x in want if x not in LEGS]
    if bad:
        raise SystemExit(f"unknown leg(s): {bad}")
    return want


def _sha_dir(dd):
    lines = []
    for p in sorted(dd.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  "
                         f"{p.relative_to(dd)}")
    (dd / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


def _sweep(cal, cells, capture_fn, outdir, reps_every=0, reps=3, progress=20):
    """capture_fn(image, waits, ncap) -> (words, extra)."""
    outdir.mkdir(parents=True, exist_ok=True)
    table, unstable = [], []
    t0 = time.time()
    n = 0
    shards = defaultdict(dict)
    for leg, w, al in cells:
        img, meta = image_of(leg, al)
        ncap = ncap_for(w, cal)
        words, extra = capture_fn(img, w, ncap)
        f = features(_rows_from_words(words), leg, al, meta)
        sha = hashlib.sha256(
            ("\n".join(f"{x:016x}" for x in words) + "\n").encode()).hexdigest()
        ck = cell_key(leg, w, al)
        row = {"cell": ck, "leg": leg, "waits": w, "align": al, "ncap": ncap,
               "sha256": sha, "n_words": len(words),
               "image_sha256": image_sha(leg, al),
               "klass": LEGS[leg][3], "block": block_of(leg).hex()}
        row.update(f)
        row.update(extra)
        if reps_every and n % reps_every == 0:
            shas, offs = [sha], [tuple(f.get("ghost_addr") or ())]
            for _ in range(reps - 1):
                w2, _e = capture_fn(img, w, ncap)
                shas.append(hashlib.sha256(
                    ("\n".join(f"{x:016x}" for x in w2) + "\n").encode()
                ).hexdigest())
                offs.append(tuple(features(_rows_from_words(w2), leg, al, meta)
                                  .get("ghost_addr") or ()))
            row["rep_shas"] = shas
            row["rep_ghost"] = [list(o) for o in offs]
            row["stable"] = len(set(shas)) == 1
            row["take_stable"] = len(set(offs)) == 1
            if not row["take_stable"]:
                unstable.append(ck)
        table.append(row)
        shards[stratum_key(leg, w)][ck] = [f"{x:016x}" for x in words]
        n += 1
        if progress and n % progress == 0:
            print(f"    {n}/{len(cells)} cells  ({time.time() - t0:.0f}s)  "
                  f"{ck}  ghost={f.get('mode_label')}", flush=True)
    for k, sh in shards.items():
        with gzip.open(outdir / f"{k}.raw.json.gz", "wt") as fh:
            json.dump(sh, fh, separators=(",", ":"))
    return table, unstable, time.time() - t0


def _merge(outdir, table):
    p = outdir / "table.json"
    old = json.loads(p.read_text()) if p.exists() else []
    by = {r["cell"]: r for r in old}
    kept = len(by)
    for r in table:
        by[r["cell"]] = r
    merged = sorted(by.values(), key=lambda r: (LEG_ORDER.index(r["leg"]),
                                                r["waits"], r["align"]))
    if kept:
        print(f"  merged with {kept} previously measured cells -> {len(merged)}")
    return merged


# --------------------------------------------------------------------------- #
# offline commands
# --------------------------------------------------------------------------- #
def cmd_show(a):
    print(f"segments: " + "  ".join(f"{k}={v:04x}(base {v << 4:05x})"
                                    for k, v in SEG.items()))
    print("sentinels: " + "  ".join(f"{k}={v:04x}" for k, v in SENT.items()))
    print(f"\n  {'value':>6}  meaning")
    for v in sorted(LABEL):
        print(f"  {v:6x}  {LABEL[v]}")
    print(f"\nBLOCK={BLOCK}  R={R}  waits={WAITS}  aligns={ALIGNS}")
    print(f"\n  {'leg':<8}{'cls':<5}{'bytes':<38}{'n_pre':<7}note")
    for k in LEG_ORDER:
        b = block_of(k)
        used = len(b.rstrip(b"\x90"))
        print(f"  {k:<8}{LEGS[k][3]:<5}{b[:used].hex():<38}{n_pre(k):<7}"
              f"{LEGS[k][4][:60]}")
    print(f"\n  image sha256 (align 0):")
    for k in LEG_ORDER:
        print(f"    {k:<8}{image_sha(k, 0)}")
    return 0


def cmd_predict(a):
    """The per-leg predictions of the four (five) hypotheses, as ADDRESSES.

    Requires `rails` to have been taken first: H-A/H-B/H-C are the RTL's own
    `ghost_off` expression evaluated on the leg's own frozen registers, so they
    are NUMBERS, not adjectives, and a leg on which two of them coincide is
    declared NON-DISCRIMINATING here -- before the board -- and stays that way
    whatever the board says."""
    OUT.mkdir(parents=True, exist_ok=True)
    rails = _rails()
    if not rails:
        raise SystemExit("ghost_pred_cell: run `rails` first (offline) -- the "
                         "predictions are evaluated on the measured rails")
    rows = []
    hyp = ("H-A", "H-B", "H-C", "H-D", "H-E")

    def s_(v):
        if v is None:
            return "--"
        sg, off, lab = decode_addr(v)
        return f"{sg}:{lab}" if sg else f"{v:05x}"

    print(f"  {'leg':<8}{'cls':<5}{'ghost_off':<11}" +
          "".join(f"{h:<16}" for h in hyp) + "discriminates")
    for k in LEG_ORDER:
        p_ = predictions(k, rails)
        go = p_.get("ghost_off")
        vals = {h: p_[h] for h in hyp}
        # which hypothesis pairs this leg can actually tell apart
        sep = sorted({f"{a}/{b}" for i2, a in enumerate(hyp)
                      for b in hyp[i2 + 1:]
                      if vals[a] is not None and vals[b] is not None
                      and vals[a] != vals[b]})
        print(f"  {k:<8}{LEGS[k][3]:<5}"
              f"{('--' if go is None else f'{go:04x}'):<11}" +
              "".join(f"{s_(vals[h]):<16}" for h in hyp) +
              ("  ".join(sep[:4]) if sep else "NONE"))
        rows.append({"leg": k, "klass": LEGS[k][3], "ghost_off": go,
                     "sp": SP_AT_PROBE[k], "last_bus": LAST_BUS[k],
                     "pred": vals,
                     "pred_label": {h: s_(v) for h, v in vals.items()},
                     "separates": sep,
                     "rails": rails.get(k, {}).get("terms")})
    d = {"tool": "ghost_pred_cell predict", "segments": SEG,
         "sentinels": {k: f"{v:04x}" for k, v in SENT.items()},
         "block": BLOCK, "R": R, "waits": list(WAITS), "aligns": list(ALIGNS),
         "D1": D1, "D2": D2, "D3": D3, "nulls": NULLS,
         "git": _git_head(),
         "images": {f"{k}_a{al}": image_sha(k, al)
                    for k in LEG_ORDER for al in ALIGNS},
         "legs": rows,
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    PRED.write_text(json.dumps(d, indent=1) + "\n")
    print(f"\n  D1 POP-class   (SP vs the last bus address): {D1}")
    print(f"  D2 ModR/M-mem  (the EA path as last writer):  {D2}")
    print(f"  D3 ALU/MUL     (a CHOSEN sentinel in the rail): {D3}")
    print(f"  NULL controls  (must read SS:SP exactly):      {NULLS}")
    print(f"  -> {PRED}")
    return 0


def _tbsys():
    import fz2_tbsys
    return fz2_tbsys


def cmd_calib(a):
    """Capture depth per wait level, measured on the LONGEST leg.

    AN INSTRUMENT SETTING, NOT A RESULT: every scored quantity is recomputed
    from the capture's own transactions, so a generous calibration costs time
    and biases nothing.  Taken on an engine because taking it on the board
    would be board contact before the pre-registration."""
    tbs = _tbsys()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_calib.hex"
    worst = max(LEG_ORDER, key=lambda k: len(block_of(k).rstrip(b"\x90")))
    print(f"  worst-case leg: {worst}")
    cal = {"tool": "ghost_pred_cell calib", "leg": "tb_sys ret", "worst": worst,
           "block": BLOCK, "R": R, "ncap": {}, "measured": {},
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    img, meta = image_of(worst, max(ALIGNS))
    for w in WAITS:
        tmp.unlink(missing_ok=True)
        r = tbs.run_tb("ret", img, tmp, ncap=4090, waits=w, quiet=True)
        rows = _rows_from_words(r["words"])
        f = features(rows, worst, max(ALIGNS), meta)
        last = f["ghost"][-1]["row"] if f.get("ghost") else None
        cal["measured"][str(w)] = {"ok": f["ok"], "why": f["why"],
                                   "n_memr": f.get("n_memr"),
                                   "last_ghost_row": last}
        cal["ncap"][str(w)] = min(4090, max((last or 0) + 250,
                                            1400 + 700 * w))
        print(f"  w{w}: ok={f['ok']} n_memr={f.get('n_memr')} "
              f"last_ghost_row={last} -> ncap {cal['ncap'][str(w)]}")
    tmp.unlink(missing_ok=True)
    CALIB.write_text(json.dumps(cal, indent=1) + "\n")
    print(f"  -> {CALIB}")
    return 0


def _cal():
    return json.loads(CALIB.read_text()) if CALIB.exists() else {}


def cmd_rails(a):
    """THE CONSTRUCTION'S OWN FALSIFIER, and it runs BEFORE the board.

    The whole claim of this cell is that its programs break the degeneracy the
    banked corpus cannot break -- M10-SYS §4.5(b): *"on both speaking seats the
    undecorated value is held simultaneously by `SP`, `TMPB` and `IND`"*.  That
    claim is CHECKABLE offline, on the instrument wave-9 built: freeze the core
    at the ghost read's own row through `M10-SYS` (`+ss_at`, read-only), read
    the 21 named terms out of the save-state map, and count how many of them
    are equal.

    It measures the CORE's rails, which is the only engine whose registers are
    readable at all; it is evidence about the STIMULUS (does this program put
    distinct values in distinct rails?), not about silicon.  If the core's rails
    are degenerate here the cell is not worth taking to the board."""
    import fz2_m10 as m10
    import re as _re
    tbs = _tbsys()
    cal = _cal()
    d = OUT / "rails"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "_run.hex"
    A = m10.ss_addrs()
    rows_out = []
    print(f"  {'leg':<8}{'blk':<5}{'row':<6}" +
          "".join(f"{t:<7}" for t in m10.TERMS[:20]))
    for leg in _select(a.legs):
        img, meta = image_of(leg, a.align)
        ncap = ncap_for(a.waits, cal)
        tmp.unlink(missing_ok=True)
        r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=a.waits, quiet=True)
        f = features(_rows_from_words(r["words"]), leg, a.align, meta)
        if not f.get("ok"):
            print(f"  {leg:<8}INVALID: {f['why']}")
            rows_out.append({"leg": leg, "ok": False, "why": f["why"]})
            continue
        for g in f["ghost"][a.block:a.block + 1]:
            # M10's OWN CALIBRATION, not an assumed offset: sweep the freeze
            # across the fork and take the clock at which the BIU's current
            # address IS the ghost address.  A register read at the wrong clock
            # is a fitted number (`fz2_m10.solve`'s rule, verbatim).
            walk = []
            best = None
            for dd in range(a.dlo, a.dhi + 1):
                row = g["row"] + dd
                if row < 0:
                    continue
                rr = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=a.waits,
                                quiet=True, ss_at=row)
                ss = {}
                for m in _re.finditer(m10.SS6_RE, rr["stdout"]):
                    ss[int(m.group(1), 16)] = int(m.group(2), 16)
                biu = ((ss.get(A["SSA_B_CUR_ADDR_LO"], 0) |
                        (ss.get(A["SSA_B_CUR_ADDR_HI"], 0) << 16)) & 0xFFFFF)
                tt = m10.terms_of(ss, A)
                walk.append({"d": dd, "row": row, "biu": f"{biu:05x}",
                             "terms": {k: f"{v:04x}" for k, v in tt.items()}})
                if biu == g["addr"] and best is None:
                    best = (dd, row, ss)
            if best is None:
                print(f"  {leg:<8}NO FREEZE lands on the ghost address "
                      f"{g['addr']:05x} in d in [{a.dlo},{a.dhi}]")
                rows_out.append({"leg": leg, "ok": False, "walk": walk,
                                 "why": "no freeze on the ghost address",
                                 "ghost": g["addr"], "ghost_label": g["label"]})
                continue
            dd, row, ss = best
            t = m10.terms_of(ss, A)
            sg = {m10.SEG_NAME[i]: (ss.get(A[m10.SEG_ORDER[i]], 0) & 0xFFFF)
                  for i in range(4)}
            vals = {k: v for k, v in t.items() if k != "ZERO"}
            dup = Counter(vals.values())
            rows_out.append({"leg": leg, "ok": True, "block": g["block"],
                             "row": row, "d": dd, "walk": walk,
                             "ghost": g["addr"],
                             "ghost_label": g["label"],
                             "terms": {k: f"{v:04x}" for k, v in t.items()},
                             "segs": {k: f"{v:04x}" for k, v in sg.items()},
                             "n_distinct": len(set(vals.values())),
                             "n_terms": len(vals),
                             "collisions": {f"{v:04x}": [k for k in vals
                                                         if vals[k] == v]
                                            for v, n in dup.items() if n > 1}})
            print(f"  {leg:<8}{g['block']:<5}{row:<6}(d={dd:+d}) " +
                  "".join(f"{t[k]:04x}   " for k in m10.TERMS[:20]))
    tmp.unlink(missing_ok=True)
    out = {"tool": "ghost_pred_cell rails", "leg": "tb_sys ret",
           "receipt": _tbsys_receipt(), "waits": a.waits, "align": a.align,
           "block": a.block, "dlo": a.dlo, "dhi": a.dhi, "git": _git_head(),
           "terms": m10.TERMS, "rows": rows_out,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (d / "rails.json").write_text(json.dumps(out, indent=1) + "\n")
    print("\n  distinctness of the 20 named terms at the ghost row:")
    for r in rows_out:
        if r.get("ok"):
            print(f"    {r['leg']:<8}{r['n_distinct']:>3}/{r['n_terms']} "
                  f"distinct   ghost={r['ghost_label']}   "
                  f"collisions={ {k: v for k, v in r['collisions'].items()} }")
    print(f"  -> {d / 'rails.json'}")
    return 0


def _tbsys_receipt():
    try:
        import artifact
        import x1_retention as x1
        return {k: (artifact.receipt_id(v) if hasattr(artifact, "receipt_id")
                    else hashlib.sha256(v.read_bytes()).hexdigest())
                for k, v in x1.BIN.items() if v.exists()}
    except Exception as e:                                   # noqa: BLE001
        return {"error": str(e)}


def cmd_core(a):
    """The SAME grid on `tb_sys ret` -- the ucore's own ghost-address map.

    NOT the reference: the correctness target is silicon (CLAUDE.md,
    2026-08-04).  It exists so the measured silicon predicate can be put beside
    the engine's, cell for cell, on the identical stimulus."""
    tbs = _tbsys()
    cal = _cal()
    d = OUT / "core"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "_run.hex"

    def cap(img, w, ncap):
        tmp.unlink(missing_ok=True)     # tb_sys does not truncate its cap file
        r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w, quiet=True)
        return r["words"], {}

    cells = grid(_select(a.legs))
    table, unstable, secs = _sweep(cal, cells, cap, d)
    tmp.unlink(missing_ok=True)
    table = _merge(d, table)
    man = {"tool": "ghost_pred_cell core", "leg": "tb_sys ret",
           "receipt": _tbsys_receipt(), "cells": len(table),
           "seconds": round(secs, 1), "block": BLOCK, "R": R,
           "git": _git_head(),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (d / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    (d / "table.json").write_text(json.dumps(table, indent=1) + "\n")
    print(f"  core: {len(table)} cells in {secs:.0f}s -> {d}")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


# --------------------------------------------------------------------------- #
# the BOARD leg
# --------------------------------------------------------------------------- #
def _git_head():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def _board():
    import v30run
    from t2b_board import HOST
    from s13_board import div_guard
    from s10_board import pin_div, DIV_OF_RECORD
    import emit_suite as es
    assert es.EMIT_USE_CORE is False, \
        "ghost_pred_cell refuses to run: truth source is not the socket"
    return v30run, HOST, div_guard, pin_div, DIV_OF_RECORD


def _ssh(host, cmd, timeout=25):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=10", host, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def single_writer(host):
    """Asked of the board, not assumed (CLAUDE.md).  Returns the record."""
    rec = {}
    rc, up, err = _ssh(host, "uptime")
    rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
    print(f"  uptime: {rec['uptime']}")
    if rc != 0:
        rec["single_writer"] = "UNKNOWN (unreachable)"
        return rec
    rc, ps, _ = _ssh(host, "ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    others = [l for l in ps.splitlines() if l.strip()]
    rec["board_procs"] = others
    rec["single_writer"] = "VIOLATED" if others else "OK"
    for l in others:
        print(f"    *** {l}")
    lp = subprocess.run(["bash", "-lc", "pgrep -af '[v]30ctl.py serve' || true"],
                        capture_output=True, text=True).stdout.strip()
    rec["local_serve_procs"] = [l for l in lp.splitlines() if l.strip()]
    if rec["local_serve_procs"]:
        rec["single_writer"] = "VIOLATED"
        print(f"  *** local serve client(s): {rec['local_serve_procs']}")
    if rec["single_writer"] == "OK":
        print("  no v30/serve process on the board -> SINGLE WRITER")
    return rec


def _flash_pin():
    p = ROOT / "sw" / "testdata" / "flash_log.jsonl"
    ls = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return {"entries": len(ls), "tail": ls[-1]}


def cmd_run(a):
    v30run, HOST, div_guard, pin_div, DIV = _board()
    cal = _cal()
    d = OUT / "board"
    d.mkdir(parents=True, exist_ok=True)
    man = {"tool": "ghost_pred_cell run", "host": HOST, "use_core": False,
           "div": DIV, "git": _git_head(),
           "spec": "docs/notes/ghost_pred_cell_prereg_2026-08-11.md",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "flash": _flash_pin(), "block": BLOCK, "R": R,
           "images": {f"{k}_a{al}": image_sha(k, al)
                      for k in LEG_ORDER for al in ALIGNS},
           "div_guards": []}
    print("== single-writer / reachability")
    man["preflight"] = single_writer(HOST)
    if man["preflight"]["single_writer"] != "OK" and not a.force:
        (d / "manifest_aborted.json").write_text(json.dumps(man, indent=1))
        raise SystemExit("single-writer check did not pass -- STOP (CLAUDE.md)")
    print(f"== flash pin: {man['flash']['entries']} entries, "
          f"sof {man['flash']['tail'].get('sha256', '?')[:16]}...")
    pin_div()
    man["div_guards"].append(("preflight", div_guard("preflight")))

    errs = {"n": 0, "run": 0}

    def cap(img, w, ncap):
        for _attempt in (1, 2, 3):
            try:
                _recs, _fired, words = v30run.run_image(
                    img, HOST, tag="ghostpred", waits=w, use_core=False,
                    div=DIV, want_raw=True, cap=ncap)
                errs["run"] = 0
                return words, {}
            except v30run.RigMismatch as e:
                raise SystemExit(
                    f"RIG MISMATCH -- the rig is not holding the directive it "
                    f"was handed (INV-1's own failure mode): {e}.  STOP; a "
                    f"rig-integrity finding outranks the cell.")
            except Exception as e:                            # noqa: BLE001
                errs["n"] += 1
                errs["run"] += 1
                print(f"    transport error ({errs['run']}): {e}", flush=True)
                if errs["run"] >= 3:
                    raise SystemExit(
                        "three consecutive transport errors -- STOP.  A rig "
                        "finding outranks the cell (CLAUDE.md).")
                time.sleep(2)
        raise SystemExit("unreachable")

    table, unstable, secs = [], [], 0.0
    for leg in _select(a.legs):
        man["div_guards"].append((leg, div_guard(leg)))
        t, u, sec = _sweep(cal, grid([leg]), cap, d,
                           reps_every=a.reps_every, reps=a.reps)
        table += t
        unstable += u
        secs += sec
        out = _merge(d, table)
        man.update(cells=len(out), seconds=round(secs, 1),
                   transport_errors=errs["n"], unstable=unstable)
        (d / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
        (d / "table.json").write_text(json.dumps(out, indent=1) + "\n")
        lab = Counter(r.get("mode_label") for r in t)
        print(f"  {leg}: {len(t)} cells  ghost={dict(lab)}  "
              f"({secs:.0f}s cumulative)", flush=True)
    man["div_guards"].append(("final", div_guard("final")))
    out = _merge(d, table)
    man["cells"] = len(out)
    man["div_guards_unpinned"] = [t for t, g in man["div_guards"]
                                  if g["state"] != "PINNED"]
    (d / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    (d / "table.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\n  board: {len(table)} cells in {secs:.0f}s, "
          f"{errs['n']} transport errors, {len(unstable)} GHOST-unstable")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    if man["div_guards_unpinned"]:
        print(f"*** UNPINNED div readback(s): {man['div_guards_unpinned']} "
              f"-- RIG-INTEGRITY FINDING ***")
        return 3
    return 0


# --------------------------------------------------------------------------- #
# THE KEY -- FROZEN ON THE REGISTERED GRID, APPLIED UNCHANGED TO THE VALIDATION
# FAMILY.  `docs/notes/ghost_pred_cell_key_2026-08-11.md` is the registration
# and it was committed BEFORE the validation legs were captured.
#
# `dQS` is the number of clocks from the last `QS == 1` (opcode pop) row to the
# ghost read's own T1 row.  `QS = 1` is the SAME boundary `ucore_provenance.md`
# 86 registers for the BRK/TF arm; it is not a quantity invented here.
# --------------------------------------------------------------------------- #
KEY = {1: "AND", 2: "BARE", 3: "BARE", 5: "SP", 6: "AND", 7: "BARE", 8: "BARE"}
KEY_DEFAULT = "BARE"          # dQS >= 7; dQS == 4 was NOT OBSERVED -> no rule


def key_of(dqs):
    if dqs is None:
        return None
    if dqs == 4:
        return None                       # never observed; the key is silent
    return KEY.get(dqs, KEY_DEFAULT if dqs >= 7 else None)


def dqs_of(rows, ghost_row, back=40):
    """clocks from the last `QS == 1` opcode pop to the ghost T1."""
    pops = [i for i in range(max(0, ghost_row - back), ghost_row)
            if rows[i]["qs"] == 1]
    return (ghost_row - pops[-1]) if pops else None


def cmd_idle(a):
    v30run, HOST, div_guard, pin_div, DIV = _board()
    import check_seq
    img, _ = ti.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img, HOST, use_core=False)
    print("  board_idle: OK (socket, use_core=False)")
    return 0


# --------------------------------------------------------------------------- #
# the score
# --------------------------------------------------------------------------- #
def _load(which):
    p = OUT / which / "table.json"
    if not p.exists():
        raise SystemExit(f"ghost_pred_cell: no {which} table ({p})")
    return json.loads(p.read_text())


def _verdict(chip):
    """The measured predicate, from D1 and D2, on the chip's own rows."""
    by = defaultdict(list)
    for r in chip:
        if r.get("ok") and r.get("pre_ok"):
            by[r["leg"]].append(r)
    out = {}
    for leg, rows in by.items():
        p = predictions(leg)
        offs = Counter()
        for r in rows:
            offs.update(o for o in r["ghost_off"] if o is not None)
        hyp = {h: sum(n for o, n in offs.items() if v is not None and o == v)
               for h, v in p.items()}
        tot = sum(offs.values())
        out[leg] = {"klass": LEGS[leg][3], "cells": len(rows),
                    "blocks": tot,
                    "offs": {f"{o:04x} {LABEL.get(o, '?')}": n
                             for o, n in offs.most_common()},
                    "pred": {h: (None if v is None else
                                 f"{v:04x} {LABEL.get(v, '?')}")
                             for h, v in p.items()},
                    "hits": hyp,
                    "rate": {h: (round(n / tot, 4) if tot else None)
                             for h, n in hyp.items()}}
    return out


def cmd_score(a):
    chip = _load("board")
    try:
        core = _load("core")
    except SystemExit:
        core = []
    ch = {r["cell"]: r for r in chip}
    co = {r["cell"]: r for r in core}
    print("=== STRUCTURE")
    for nm, tb in (("chip", chip), ("core", core)):
        if not tb:
            continue
        ok = sum(1 for r in tb if r.get("ok"))
        pre = sum(1 for r in tb if r.get("pre_ok"))
        print(f"  {nm}: {len(tb)} cells, {ok} structurally valid, "
              f"{pre} with the composed preamble")
        for r in tb:
            if not r.get("ok"):
                print(f"    INVALID {r['cell']}: {r['why']}")

    print("\n=== THE NULL CONTROLS (must read SS:SP exactly)")
    for leg in NULLS:
        rows = [r for r in chip if r["leg"] == leg and r.get("ok")]
        n = sum(len(r["ghost_off"]) for r in rows)
        good = sum(1 for r in rows for o, s in zip(r["ghost_off"],
                                                   r["ghost_seg"] * len(r["ghost_off"]))
                   if o == SP_AT_PROBE[leg])
        good = sum(1 for r in rows for g in r["ghost"]
                   if g["off"] == SP_AT_PROBE[leg] and g["seg"] == "SS")
        print(f"  {leg}: {good}/{n} blocks at SS:{SP_AT_PROBE[leg]:04x}")

    print("\n=== THE CHIP'S MEASURED GHOST ADDRESS, PER LEG")
    v = _verdict(chip)
    for leg in LEG_ORDER:
        if leg not in v:
            continue
        r = v[leg]
        print(f"  {leg:<8}[{r['klass']}] {r['blocks']:>3} blocks   "
              f"{'  '.join(f'{k}x{n}' for k, n in r['offs'].items())}")
        print(f"           predictions "
              f"{'  '.join(f'{h}={x}' for h, x in r['pred'].items() if x)}"
              f"   hits {r['hits']}")

    print("\n=== CHIP vs CORE, cell for cell")
    same = diff = 0
    diffs = []
    for k in sorted(set(ch) & set(co)):
        A, B = ch[k], co[k]
        if not (A.get("ok") and B.get("ok")):
            continue
        if A["ghost_addr"] == B["ghost_addr"]:
            same += 1
        else:
            diff += 1
            diffs.append((k, A.get("mode_label"), B.get("mode_label")))
    print(f"  identical ghost addresses: {same}   different: {diff}")
    seen = set()
    for k, x, y in diffs:
        sig = (k.split("_w")[0], x, y)
        if sig in seen:
            continue
        seen.add(sig)
        print(f"    {k:<20} chip={x:<14} core={y}")

    d = {"tool": "ghost_pred_cell score", "verdict": v,
         "chip_cells": len(chip), "core_cells": len(core),
         "chip_vs_core": {"same": same, "diff": diff},
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT / "score.json").write_text(json.dumps(d, indent=1) + "\n")
    print(f"\n  -> {OUT / 'score.json'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    for nm, fn in (("show", cmd_show), ("predict", cmd_predict),
                   ("calib", cmd_calib), ("score", cmd_score),
                   ("idle", cmd_idle)):
        c = s.add_parser(nm)
        c.set_defaults(fn=fn)
    c = s.add_parser("core")
    c.add_argument("--legs", default=None)
    c.set_defaults(fn=cmd_core)
    c = s.add_parser("rails")
    c.add_argument("--legs", default=None)
    c.add_argument("--waits", type=int, default=0)
    c.add_argument("--align", type=int, default=0)
    c.add_argument("--block", type=int, default=2,
                   help="which repeat's ghost row to freeze at (0..R-1); 2 is "
                        "a STEADY-STATE block, not the cold first one")
    c.add_argument("--dlo", type=int, default=-12,
                   help="freeze-sweep low bound, relative to the ghost T1")
    c.add_argument("--dhi", type=int, default=1)
    c.set_defaults(fn=cmd_rails)
    c = s.add_parser("run")
    c.add_argument("--legs", default=None)
    c.add_argument("--reps-every", type=int, default=8,
                   help="every Nth cell is captured `--reps` times (stability)")
    c.add_argument("--reps", type=int, default=3)
    c.add_argument("--force", action="store_true",
                   help="proceed past a failed single-writer check (recorded)")
    c.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
