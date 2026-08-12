#!/usr/bin/env python3
"""iret_tf_cell -- THE DIRECTED BOARD CELL that resolves WHERE the second TF
boundary unit sits, and what an `IRET` setter does that a `popf` setter cannot.

WHY IT EXISTS.  `docs/notes/tf0f_cell_results_2026-08-11.md` §5.2, verbatim:

    `pushed_off` measures the COUNT of units a probe contributes (1 vs 2), not
    WHERE the second one sits -- at a count of 2 the third unit is the first pad
    byte whatever the second unit's position.  *"The second boundary is at the
    opcode byte"* is an INTERPRETATION of the count, not a measurement.
    Resolving it needs the trap to land one boundary earlier -- an `IRET`
    setter ... and that cell is **not built here**.

`KM` therefore matched silicon's COUNT on 30 legs and the landing (`e57c3b4d12`)
matched the ucore to that count.  This cell measures the POSITION.

THE MECHANISM, AS THE RTL IMPLEMENTS IT (`v30u_eu.sv`), because the predictions
are derived from it and not from the "unit" surface language:

  * a SAMPLE rides a boundary POP -- `brk_smp_n = q_pop && q_ripe && q_bnd_pop`,
    with `q_bnd_pop = q_first || (st == S_EXT_POP)` since `KM`;
  * the arm is a LEVEL, `if (brk_smp) brk_arm_n = brk_seen`;
  * the TAKE is `bnd_fire = at_bnd && bnd_take`, and `bnd_opc` is gated by
    `bnd_armed`, **which is set only at a RETIRE and never at a prefix
    hand-over**.

So the ucore's pushed PC is ALWAYS an instruction start.  Silicon's need not be:
if the part can take at the prefix/escape hand-over the pushed PC lands INSIDE
the probe, and *that* is where the second boundary sits.  `tf0f` could not see
it because with its geometry the arming pop was already the probe's LAST
decoration pop, so no hand-over remained between the arm and the retire.

THE THREE THINGS THIS CELL SEPARATES, AND HOW.

  (1) WHICH POP ARMS.  `tf0f` measured, on the `popf` setter, that the FIRST
      boundary pop after the setter is too early (§86.B's 4-clock floor) and the
      SECOND arms: `nop` reads 6, not 5.  With an `IRET` setter the flag load
      sits at the very end of a long, queue-flushing instruction, so the first
      pop after it may already be clear of the floor.  `S = 1` and `S = 2` are
      both registered.

  (2) WHERE THE TAKE CAN LAND.  A FILLER of `f` one-byte NOPs between the setter
      and the probe moves the arming pop.  At `f = 1` the arm lands on the
      probe's FIRST pop, so every hand-over inside the probe is still ahead of
      it -- and the pushed PC separates "retire only" from "at the opcode" from
      "at the escape" from "at the first decoration byte".  At `f = 0` (the
      `tf0f` geometry) they collapse.  This is the cell.

  (3) SETTER ADJACENCY.  The same probe, same filler, both setters.  Any
      difference is an adjacency effect neither §86 nor `KM` can express.

THE PROGRAM.  `R` identical blocks of `BLOCK` bytes, one trap each:

    popf geometry     68 00 01 9D   push 0x100 ; popf     <- TF <- 1
                      90 * f        the FILLER
                      <P>           the probe
                      90 ...        pad to BLOCK
    iret geometry     CD 04         BRK 4 -- vector 4's handler writes TF into
                      90 * f        the frame it returns through, so the
                      <P>           instruction that raises TF is that handler's
                      90 ...        IRET, with nothing between it and the probe

Vector 1's handler CLEARS TF in the frame it is about to return through, so a
block produces EXACTLY ONE trap and a capture is `R` independent repeats.

THE OBSERVABLE IS ENGINE-FREE.  A vector-1 entry is announced by a `MEMR` at
linear 0x00004; the three descending `MEMW`s that follow are PSW, PS, **PC**,
and `pushed_off = pushed_PC - block_base` names the boundary in bytes.  Nothing
in this reader decodes an opcode, runs an engine or consults a golden.

BOARD DISCIPLINE (CLAUDE.md), in code: single-writer asked of the board before
the first capture; SOCKET ONLY (`use_core=False`, explicit); NO FLASHING and the
flash pin recorded; the divider PINNED and `div_guard` recorded at every leg
boundary; FULL per-clock words retained with a sha256 per cell; `board_idle()`
at the end; three consecutive transport errors STOP the cell.  This cell drives
no pin: the trap is internal, so there is no `evt`, no hold and none of INV-1's
directive-truncation exposure.

Usage:
    python3 sw/iret_tf_cell.py calib                 # offline (tb_sys)
    python3 sw/iret_tf_cell.py predict               # offline
    python3 sw/iret_tf_cell.py core  [--legs ...]    # offline (tb_sys)
    python3 sw/iret_tf_cell.py run   [--legs ...]    # BOARD, socket only
    python3 sw/iret_tf_cell.py score [--stage der]
    python3 sw/iret_tf_cell.py qs
    python3 sw/iret_tf_cell.py idle
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
import tf0f_cell as tf                                    # noqa: E402

OUT = ROOT / "sw" / "testdata" / "iret-tf"
CALIB = OUT / "calib.json"
PRED = OUT / "predictions.json"

# --------------------------------------------------------------------------- #
# the program
# --------------------------------------------------------------------------- #
BLOCK = 16               # bytes per block -- word-aligned, so `align` alone
R = 6                    # blocks per image = independent repeats per capture

S_POPF = bytes([0x68, 0x00, 0x01, 0x9D])   # push 0x100 ; popf   (TF <- 1)
S_POPF_N = bytes([0x68, 0x00, 0x00, 0x9D])  # the NULL setter (tf0f's CLEARER)
S_IRET = bytes([0xCD, 0x04])               # BRK 4 -> vector 4 -> its IRET sets TF

# Vector 1's handler: at entry SP points at the pushed PC, so [BP+4] is the
# pushed PSW.  0xF002 is the composed PSW with TF CLEAR.  compose appends IRET.
H_VEC1 = bytes([0x89, 0xE5,                        # MOV BP,SP
                0xC7, 0x46, 0x04, 0x02, 0xF0])    # MOV word [BP+4],0xF002
# Vector 4's handler, the IRET SETTER: identical shape, 0xF102 = TF SET.  The
# instruction that raises TF is therefore the IRET compose appends here, and
# there is nothing at all between that IRET and the probe.
H_VEC4_SET = bytes([0x89, 0xE5,
                    0xC7, 0x46, 0x04, 0x02, 0xF1])  # MOV word [BP+4],0xF102
H_VEC4_CLR = H_VEC1                                 # the iret NULL

IVT = {1: (0x0000, ti.IHT_AT), 4: (0x0000, ti.IHT_AT + ti.IHT_STRIDE)}

# tf0f's own REGS, unchanged, so the `repro` legs compose BYTE-IDENTICAL images
REGS = dict(tf.REGS)

PREFIX_BYTES = tf.PREFIX_BYTES

# --------------------------------------------------------------------------- #
# THE PROBE FAMILY.  Every probe is `mod = 3` -- register-only, no memory
# operand anywhere -- because a take that lands INSIDE a probe resumes there and
# re-executes the tail as a different instruction.  With `mod = 3` that tail can
# have no memory side effect at all, so the geometry cannot perturb itself.  No
# probe is a BRKEM alias (`0F` + any byte >= 0x40) and none is the parked
# `0F 31`-with-memory form.
# --------------------------------------------------------------------------- #
PROBES = {
    # --- UNDECORATED: the opcode IS the first byte.  The control band.
    "nop":   (bytes([0x90]),                          "NOP"),
    "addrr": (bytes([0x01, 0xD8]),                    "ADD AW,BW -- opcode+ModR/M"),
    "movi":  (bytes([0xB8, 0x34, 0x12]),              "MOV AW,0x1234"),
    # --- PREFIX ONLY.  d = 1 is non-discriminating; d >= 2 separates.
    "pfx1":  (bytes([0x2E, 0x01, 0xD8]),              "CS: ADD AW,BW"),
    "pfx2":  (bytes([0x2E, 0x3E, 0x01, 0xD8]),        "CS: DS: ADD AW,BW"),
    "pfx3":  (bytes([0x2E, 0x3E, 0x26, 0x01, 0xD8]),  "3 prefixes + ADD AW,BW"),
    "pfx4":  (bytes([0x2E, 0x3E, 0x26, 0x36, 0x01, 0xD8]),
                                                      "4 prefixes + ADD AW,BW"),
    # --- BARE `0F` ESCAPE.  d = 1: the escape and the opcode are adjacent, so
    #     every position rule collapses.  Carried as the KM control band.
    "x1b":   (bytes([0x0F, 0x1B, 0xE8, 0x4F]),        "0F 1B -- mod=3"),
    "x13":   (bytes([0x0F, 0x13, 0xC0]),              "0F 13 -- mod=3"),
    # --- PREFIX **AND** ESCAPE.  d >= 2 AND two KINDS of decoration: these are
    #     the only probes on which "at the escape" and "at the opcode" differ.
    "z1b":   (bytes([0x2E, 0x0F, 0x1B, 0xE8, 0x4F]),  "CS: 0F 1B -- mod=3"),
    "p2x":   (bytes([0x2E, 0x3E, 0x0F, 0x1B, 0xE8, 0x4F]),
                                                      "2 prefixes + 0F 1B"),
    "p4x":   (bytes([0x2E, 0x3E, 0x26, 0x36, 0x0F, 0x1B, 0xE8, 0x4F]),
                                                      "4 prefixes + 0F 1B"),
    # --- THE DISJOINT VALIDATION FAMILY.  Every byte sequence here appears
    #     nowhere above.  Registered before capture; scored only after the
    #     derivation verdict is committed.
    "v_pfxa": (bytes([0x36, 0x26, 0x01, 0xD8]),       "SS: ES: ADD AW,BW"),
    "v_pfxb": (bytes([0xF3, 0x2E, 0x3E, 0x01, 0xD8]), "REP CS: DS: ADD AW,BW"),
    "v_z13":  (bytes([0x3E, 0x0F, 0x13, 0xC0]),       "DS: 0F 13 -- mod=3"),
    "v_p3x":  (bytes([0x26, 0x36, 0x3E, 0x0F, 0x13, 0xC0]),
                                                      "3 prefixes + 0F 13"),
    "v_x2a":  (bytes([0x0F, 0x2A, 0xC0]),             "0F 2A -- ROR4, mod=3"),
    "v_lock": (bytes([0xF0, 0x01, 0xD8]),             "LOCK ADD AW,BW"),
    "v_xchg": (bytes([0x93]),                         "XCHG AW,BW"),
}

VAL_PROBES = [k for k in PROBES if k.startswith("v_")]
DER_PROBES = [k for k in PROBES if not k.startswith("v_")]

# --------------------------------------------------------------------------- #
# THE LEGS.  A leg is (setter, filler, probe, tf).  `repro` legs are `tf0f`'s
# own images, byte for byte, re-run here as the instrument control.
# --------------------------------------------------------------------------- #
GEOM = {                       # name: (setter, filler)
    "P0": ("popf", 0),         # tf0f's geometry, on this cell's images
    "P1": ("popf", 1),         # THE MONEY LEG -- the arm lands on the probe's
                               # first pop, so every hand-over is still ahead
    "P2": ("popf", 2),         # the arm lands before the probe entirely
    "I0": ("iret", 0),         # money leg #2 if the IRET arms on its first pop
    "I1": ("iret", 1),
}

P0_LEGS = ["nop", "addrr", "pfx2", "pfx4", "x1b", "z1b"]
P2_LEGS = ["nop", "pfx4", "z1b", "p4x"]
REPRO = ["nop", "x1b", "z1b"]          # tf0f probe names; published chip column


def _mk_legs():
    L = {}
    for p in DER_PROBES:
        L[f"P1_{p}"] = dict(geom="P1", probe=p, tf=True, stage="der")
        L[f"I0_{p}"] = dict(geom="I0", probe=p, tf=True, stage="der")
        L[f"I1_{p}"] = dict(geom="I1", probe=p, tf=True, stage="der")
    for p in P0_LEGS:
        L[f"P0_{p}"] = dict(geom="P0", probe=p, tf=True, stage="der")
    for p in P2_LEGS:
        L[f"P2_{p}"] = dict(geom="P2", probe=p, tf=True, stage="der")
    for p in REPRO:
        L[f"RP_{p}"] = dict(geom="RP", probe=p, tf=True, stage="der")
    # the NULLs -- identical geometry, TF never raised
    L["N_p1_z1b"] = dict(geom="P1", probe="z1b", tf=False, stage="der")
    L["N_i0_z1b"] = dict(geom="I0", probe="z1b", tf=False, stage="der")
    L["N_i0_p4x"] = dict(geom="I0", probe="p4x", tf=False, stage="der")
    # the disjoint VALIDATION population, on the two discriminating geometries
    for p in VAL_PROBES:
        L[f"P1_{p}"] = dict(geom="P1", probe=p, tf=True, stage="val")
        L[f"I0_{p}"] = dict(geom="I0", probe=p, tf=True, stage="val")
    L["N_p1_v_p3x"] = dict(geom="P1", probe="v_p3x", tf=False, stage="val")
    return L


LEGS = _mk_legs()
DERIVATION = [k for k, v in LEGS.items() if v["stage"] == "der"]
VALIDATION = [k for k, v in LEGS.items() if v["stage"] == "val"]
LEG_ORDER = DERIVATION + VALIDATION
CONTROL_LEGS = [k for k, v in LEGS.items() if not v["tf"]]

WAITS = (0, 1, 2, 3)
ALIGNS = (0, 1, 2, 3)

IVT1_OFF = 0x00004
BS_INTA, BS_IOR, BS_IOW, BS_HALT, BS_CODE, BS_MEMR, BS_MEMW, BS_PASV = range(8)


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def _shape(probe):
    """(n_prefix_bytes, escaped, length)."""
    p = PROBES[probe][0]
    n = 0
    while n < len(p) and p[n] in PREFIX_BYTES:
        n += 1
    return n, (n < len(p) and p[n] == 0x0F), len(p)


def setter_bytes(leg):
    g = LEGS[leg]
    if g["geom"] == "RP":
        return tf.SETTER
    s, _f = GEOM[g["geom"]]
    if s == "popf":
        return S_POPF if g["tf"] else S_POPF_N
    return S_IRET                       # the iret NULL differs in the HANDLER


def filler_of(leg):
    g = LEGS[leg]
    return 0 if g["geom"] == "RP" else GEOM[g["geom"]][1]


def probe_off(leg):
    return len(setter_bytes(leg)) + filler_of(leg)


def body_of(leg, align):
    g = LEGS[leg]
    blk = setter_bytes(leg) + bytes([0x90]) * filler_of(leg) \
        + PROBES[g["probe"]][0]
    if len(blk) > BLOCK - 2:
        raise ValueError(f"leg {leg} leaves < 2 pad bytes in the block")
    blk = blk + bytes([0x90]) * (BLOCK - len(blk))
    return bytes([0x90]) * align + blk * R


def image_of(leg, align):
    """The composed 64 KB image.  Deterministic -- no rng anywhere in this
    cell, which is what makes it DIRECTED and not a fuzz."""
    g = LEGS[leg]
    if g["geom"] == "RP":
        return tf.image_of(g["probe"], align)          # byte-identical to tf0f
    h4 = H_VEC4_SET if (g["tf"] and GEOM[g["geom"]][0] == "iret") else H_VEC4_CLR
    img, meta = ti.compose(regs=REGS, instr=body_of(leg, align), ivt=IVT,
                           handlers=[H_VEC1, h4])
    return bytes(img), meta


def image_sha(leg, align):
    return hashlib.sha256(image_of(leg, align)[0]).hexdigest()


def block_base(meta, align, k):
    return (meta["regs_in"]["PC"] + align + k * BLOCK) & 0xFFFF


def stratum_key(leg, waits):
    return f"{leg}_w{waits}"


def cell_key(leg, waits, align):
    return f"{leg}_w{waits}_a{align}"


# --------------------------------------------------------------------------- #
# row reading -- pins only, no engine
# --------------------------------------------------------------------------- #
_rows_from_words = tf._rows_from_words
_txns = tf._txns


def features(rows, leg, align, meta):
    """Every measured quantity this cell reports, off the pins.

    `ok` is False when the cell is STRUCTURALLY INVALID -- the anchor T1 is not
    in the window, the number of vector-1 entries is not `R` (or not 0 for a
    null), or an entry's three pushes are not in the window.  Those cells are
    RETAINED and REPORTED, never silently dropped."""
    anchor = meta["anchor_linear"]
    pc0 = meta["regs_in"]["PC"]
    f = {"ok": False, "why": None, "n_rows": len(rows)}
    tx = _txns(rows)
    a = next((k for k, (i, b, ad, _d) in enumerate(tx)
              if b == BS_CODE and ad == anchor), None)
    f["anchor_txn"] = a
    if a is None:
        f["why"] = "anchor T1 not in the capture window"
        return f

    n_code = 0
    entries = []
    code_seen = []
    for k in range(a, len(tx)):
        i, b, ad, d = tx[k]
        if b == BS_CODE:
            n_code += 1
            code_seen.append((k, ad))
        if b == BS_MEMR and ad == IVT1_OFF:
            ws = [t for t in tx[k:k + 10] if t[1] == BS_MEMW][:3]
            entries.append({"txn": k, "row": i, "code_before": n_code,
                            "last_code": (code_seen[-1][1] if code_seen
                                          else None),
                            "pushed_psw": ws[0][3] if len(ws) > 0 else None,
                            "pushed_ps": ws[1][3] if len(ws) > 1 else None,
                            "pushed_pc": ws[2][3] if len(ws) > 2 else None})
    f["n_entries"] = len(entries)
    f["n_code_total"] = n_code
    f["term_done"] = any(b == BS_IOW and (ad & 0xFF) == 0xFC
                         for _i, b, ad, _d in tx[a:])

    want = 0 if leg in CONTROL_LEGS else R
    if len(entries) != want:
        f["why"] = f"{len(entries)} vector-1 entries, expected {want}"
        f["entries"] = entries
        return f
    if want == 0:
        f["ok"] = True
        f["pushed_off"] = []
        f["entries"] = []
        return f

    offs, lastc, gaps, prev = [], [], [], None
    for k, e in enumerate(entries):
        if e["pushed_pc"] is None:
            f["why"] = f"entry {k}: fewer than three pushes in the window"
            f["entries"] = entries
            return f
        base = block_base(meta, align, k)
        offs.append((e["pushed_pc"] - base) & 0xFFFF)
        lin_base = (anchor - pc0 + base) & 0xFFFFF
        lastc.append((e["last_code"] - lin_base) if e["last_code"] is not None
                     else None)
        gaps.append(e["code_before"] - prev if prev is not None else None)
        prev = e["code_before"]
    f["entries"] = entries
    f["pushed_off"] = offs
    f["lastcode_off"] = lastc
    f["code_gap"] = gaps
    f["pushed_off_set"] = sorted(set(offs))
    f["lastcode_off_set"] = sorted({x for x in lastc if x is not None})
    f["uniform"] = len(set(offs)) == 1
    f["pushed_off_mode"] = Counter(offs).most_common(1)[0][0]
    f["ok"] = True
    return f


# --------------------------------------------------------------------------- #
# THE PRE-REGISTERED HYPOTHESIS SPACE
#
# It is a PRODUCT of three degrees of freedom, not a hand-picked list, so no
# rule can be added after the fact without changing the product and there is no
# per-opcode special case anywhere in it.
#
#   S   WHICH POP ARMS, after the setter raises TF.  `tf0f` MEASURED S = 2 for
#       the `popf` setter (`nop` reads 6, not 5) and this cell re-measures it on
#       its own images (`P0`/`RP`).  For the `IRET` setter both are open:
#         S1  the FIRST boundary pop after the setter arms -- the flag load sits
#             at the end of a long, queue-flushing instruction, so §86.B's
#             4-clock floor may already be cleared.  This is what makes a
#             conventional single-step advance one instruction per trap.
#         S2  the SECOND arms, exactly as `popf`.
#
#   P   WHICH POPS ARE SAMPLES inside a decorated instruction:
#         PA    the instruction-start pop and the OPCODE pop -- two, whatever
#               the depth (`KM` read as a sample rule)
#         Pall  every decoration byte's pop AND the opcode's -- which is what
#               the `QS = 1` pins announce and what `pop_is_first` does in the
#               ucore (`pfx4` = five pops)
#
#   B   WHERE A TAKE MAY LAND inside a decorated instruction, over and above its
#       own retire (which always takes):
#         B0    nowhere -- RETIRE ONLY.  This is the ucore as landed
#               (`bnd_armed` is set only at a retire), i.e. prediction (a).
#         B1    at the FIRST decoration byte's hand-over (resume `a+1`)
#         Bnp   at the PREFIX STACK's hand-over -- resume `a+np`, the `0F` byte
#               on an escaped probe, the opcode on a prefix-only one
#         Bd    at the OPCODE's hand-over (resume `a+d`) -- this is `KM`'s own
#               INTERPRETATION, *"the second boundary is at the opcode byte"*
#         Ball  at every decoration byte's hand-over
#
# The trap is then simulated exactly: walk the block's events in program order
# from the first pop after the setter, arm on the S-th POP, take at the first
# BOUNDARY after it, and report its resume PC.  `pushed_off` is that PC.
# --------------------------------------------------------------------------- #
S_KINDS = {"S1": "the FIRST boundary pop after the setter arms",
           "S2": "the SECOND boundary pop after the setter arms (measured for "
                 "`popf` by tf0f)"}
P_KINDS = {"PA": "samples at the instruction-start pop and the OPCODE pop only",
           "Pall": "samples at EVERY decoration byte's pop and the opcode's "
                   "(what the QS pins announce; what `pop_is_first` does)"}
B_KINDS = {"B0": "takes at RETIRES ONLY -- the ucore as landed",
           "B1": "a take may also land at the FIRST decoration byte's hand-over",
           "Bnp": "a take may also land at the PREFIX STACK's hand-over (the "
                  "`0F` byte on an escaped probe)",
           "Bd": "a take may also land at the OPCODE's hand-over -- KM's own "
                 "interpretation",
           "Ball": "a take may land at EVERY decoration byte's hand-over"}


def _instrs(leg):
    """[(addr, n_prefix, escaped, len)] for the instructions AFTER the setter in
    one block, to the block end.  The setter's own pops precede the TF rise and
    are not in the walk."""
    o = len(setter_bytes(leg))
    out = []
    for _ in range(filler_of(leg)):
        out.append((o, 0, False, 1))
        o += 1
    npx, esc, ln = _shape(LEGS[leg]["probe"])
    out.append((o, npx, esc, ln))
    o += ln
    while o < BLOCK:
        out.append((o, 0, False, 1))
        o += 1
    return out


def _events(leg, P, B):
    """[("pop", addr) | ("bnd", resume_pc)] in program order."""
    ev = []
    for (a, npx, esc, ln) in _instrs(leg):
        d = npx + (1 if esc else 0)
        if d == 0:
            ev.append(("pop", a))
        else:
            pops = {a, a + d} if P == "PA" else set(range(a, a + d + 1))
            bnd = {"B0": set(), "B1": {a + 1}, "Bnp": {a + npx},
                   "Bd": {a + d}, "Ball": set(range(a + 1, a + d + 1))}[B]
            bnd = {x for x in bnd if x > a}       # a+np == a when np == 0
            for x in range(a, a + d + 1):
                if x in pops:
                    ev.append(("pop", x))
                if (x + 1) in bnd:
                    ev.append(("bnd", x + 1))
        ev.append(("bnd", a + ln))                # the RETIRE
    return ev


def arm_index(leg, S):
    """Which pop arms, for this leg's setter."""
    g = LEGS[leg]
    if g["geom"] == "RP" or GEOM[g["geom"]][0] == "popf":
        return 2                                  # MEASURED by tf0f
    return 1 if S == "S1" else 2


def predict_off(leg, S, P, B):
    n, armed = 0, False
    want = arm_index(leg, S)
    for kind, val in _events(leg, P, B):
        if kind == "pop":
            n += 1
            if n >= want:
                armed = True
        elif armed:
            return val
    return None


def rules():
    return [(s, p, b) for s in S_KINDS for p in P_KINDS for b in B_KINDS]


def rule_name(s, p, b):
    return f"{s}.{p}.{b}"


def cmd_predict(a):
    OUT.mkdir(parents=True, exist_ok=True)
    p = {"tool": "iret_tf_cell predict",
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "block": BLOCK, "R": R, "waits": list(WAITS), "aligns": list(ALIGNS),
         "setters": {"popf": S_POPF.hex(), "popf_null": S_POPF_N.hex(),
                     "iret": S_IRET.hex()},
         "handlers": {"vec1": H_VEC1.hex(), "vec4_set": H_VEC4_SET.hex(),
                      "vec4_clr": H_VEC4_CLR.hex()},
         "ivt": {str(k): list(v) for k, v in IVT.items()}, "regs": REGS,
         "geometries": {k: {"setter": v[0], "filler": v[1]}
                        for k, v in GEOM.items()},
         "S_kinds": S_KINDS, "P_kinds": P_KINDS, "B_kinds": B_KINDS,
         "derivation_legs": DERIVATION, "validation_legs": VALIDATION,
         "control_legs": CONTROL_LEGS,
         "legs": {}, "images": {}, "cells": len(DERIVATION + VALIDATION) * 16}
    for k in LEG_ORDER:
        g = LEGS[k]
        npx, esc, ln = _shape(g["probe"])
        pr = {rule_name(s, pp, b): predict_off(k, s, pp, b)
              for (s, pp, b) in rules()}
        vals = sorted({v for v in pr.values() if v is not None})
        p["legs"][k] = {
            "geom": g["geom"], "probe": g["probe"], "tf": g["tf"],
            "stage": g["stage"], "bytes": PROBES[g["probe"]][0].hex(),
            "what": PROBES[g["probe"]][1], "len": ln, "n_prefix": npx,
            "escaped": esc, "decoration": npx + (1 if esc else 0),
            "setter": setter_bytes(k).hex(), "filler": filler_of(k),
            "probe_off": probe_off(k),
            "pushed_off": (None if not g["tf"] else pr),
            "distinct": vals, "separates": (len(vals) > 1),
        }
    for k in LEG_ORDER:
        for al in ALIGNS:
            p["images"][f"{k}_a{al}"] = image_sha(k, al)
    p["non_discriminating"] = [k for k, v in p["legs"].items()
                               if v["tf"] and not v["separates"]]
    # the published tf0f chip column, for the REPRO legs -- an instrument bar
    p["repro_expect_chip"] = {"RP_nop": 6, "RP_x1b": 8, "RP_z1b": 9}
    p["repro_image_identical_to_tf0f"] = {
        f"RP_{q}_a{al}": (image_sha(f"RP_{q}", al) == tf.image_sha(q, al))
        for q in REPRO for al in ALIGNS}
    PRED.write_text(json.dumps(p, indent=1))
    print(json.dumps({k: v for k, v in p.items() if k != "images"}, indent=1))
    print(f"  -> {PRED}  ({p['cells']} cells)")
    return 0


# --------------------------------------------------------------------------- #
# the sweep driver, shared by the board leg and the tb_sys leg
# --------------------------------------------------------------------------- #
def ncap_for(waits, cal=None):
    if cal:
        v = cal.get("ncap", {}).get(str(waits))
        if v:
            return v
    return min(4090, 2000 + 700 * waits)


def _sweep(cal, cells, capture_fn, outdir, reps_every=0, reps=3, progress=32):
    outdir.mkdir(parents=True, exist_ok=True)
    table, unstable = [], []
    t0 = time.time()
    n = 0
    shards = defaultdict(dict)
    for leg, w, al in cells:
        img, meta = image_of(leg, al)
        ncap = ncap_for(w, cal)
        words, extra = capture_fn(img, w, ncap)
        rows = _rows_from_words(words)
        f = features(rows, leg, al, meta)
        sha = hashlib.sha256(
            ("\n".join(f"{x:016x}" for x in words) + "\n").encode()).hexdigest()
        ck = cell_key(leg, w, al)
        row = {"cell": ck, "leg": leg, "geom": LEGS[leg]["geom"],
               "probe": LEGS[leg]["probe"], "tf": LEGS[leg]["tf"],
               "stage": LEGS[leg]["stage"], "waits": w, "align": al,
               "ncap": ncap, "sha256": sha, "n_words": len(words),
               "image_sha256": image_sha(leg, al),
               "probe_bytes": PROBES[LEGS[leg]["probe"]][0].hex(),
               "probe_off": probe_off(leg)}
        row.update(f)
        row.update(extra)
        if reps_every and n % reps_every == 0:
            shas = [sha]
            offs = [tuple(f.get("pushed_off") or ())]
            for _ in range(reps - 1):
                w2, _e = capture_fn(img, w, ncap)
                shas.append(hashlib.sha256(
                    ("\n".join(f"{x:016x}" for x in w2) + "\n").encode()
                ).hexdigest())
                offs.append(tuple(features(_rows_from_words(w2), leg, al,
                                           meta).get("pushed_off") or ()))
            row["rep_shas"] = shas
            row["rep_offs"] = [list(o) for o in offs]
            row["stable"] = len(set(shas)) == 1
            row["take_stable"] = len(set(offs)) == 1
            if not row["take_stable"]:
                unstable.append(ck)
        table.append(row)
        shards[stratum_key(leg, w)][ck] = [f"{x:016x}" for x in words]
        n += 1
        if progress and n % progress == 0:
            print(f"    {n}/{len(cells)} cells  ({time.time() - t0:.0f}s)  "
                  f"{ck}  off={f.get('pushed_off_set')}", flush=True)
    for k, sh in shards.items():
        with gzip.open(outdir / f"{k}.raw.json.gz", "wt") as fh:
            json.dump(sh, fh, separators=(",", ":"))
    return table, unstable, time.time() - t0


def _merge(outdir, table):
    """A resumed invocation must not silently DELETE what a previous one
    measured.  Merge by cell key, newest wins, and say how many were carried."""
    p = outdir / "table.json"
    old = json.loads(p.read_text()) if p.exists() else []
    by = {r["cell"]: r for r in old}
    kept = len(by)
    for r in table:
        by[r["cell"]] = r
    merged = sorted(by.values(),
                    key=lambda r: (LEG_ORDER.index(r["leg"]), r["waits"],
                                   r["align"]))
    if kept:
        print(f"  merged with {kept} previously measured cells -> {len(merged)}")
    return merged


def _select(arg, default=None):
    if not arg:
        return default if default is not None else DERIVATION
    if arg == "der":
        return DERIVATION
    if arg == "val":
        return VALIDATION
    if arg == "all":
        return LEG_ORDER
    want = [x for x in arg.split(",") if x]
    bad = [x for x in want if x not in LEGS]
    if bad:
        raise SystemExit(f"unknown leg(s): {bad}")
    return want


def grid(legs):
    return [(lg, w, al) for lg in legs for w in WAITS for al in ALIGNS]


def _sha_dir(dd):
    lines = []
    for p in sorted(dd.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  "
                         f"{p.relative_to(dd)}")
    (dd / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


# --------------------------------------------------------------------------- #
# calibration -- offline, on tb_sys; an INSTRUMENT setting, never a result
# --------------------------------------------------------------------------- #
def _tbsys():
    import fz2_tbsys
    return fz2_tbsys


def _cal():
    return json.loads(CALIB.read_text()) if CALIB.exists() else {}


CALIB_LEGS = ["I0_p4x", "I1_p4x", "P2_p4x", "P1_p4x"]


def cmd_calib(a):
    """Measure the capture depth each wait level needs, on the legs with the
    most bus traffic per block.

    THIS IS AN INSTRUMENT SETTING, NOT A RESULT.  Every reported quantity is
    recomputed from the capture's OWN transactions, so a generous calibration
    costs time and biases nothing."""
    tbs = _tbsys()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_calib.hex"
    cal = {"tool": "iret_tf_cell calib", "leg": "tb_sys ret",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "instrument setting only; every scored quantity is measured "
                   "from the capture's own transactions",
           "block": BLOCK, "R": R, "ncap": {}, "worst": {}}
    for w in WAITS:
        need, det = 0, {}
        for lg in CALIB_LEGS:
            img, meta = image_of(lg, max(ALIGNS))
            tmp.unlink(missing_ok=True)   # tb_sys does NOT truncate its cap file
            r = tbs.run_tb("ret", img, tmp, ncap=4090, waits=w, quiet=True)
            f = features(_rows_from_words(r["words"]), lg, max(ALIGNS), meta)
            last = f["entries"][-1]["row"] if f.get("entries") else None
            det[lg] = {"entries": f.get("n_entries"), "last_entry_row": last,
                       "ok": f["ok"], "why": f["why"]}
            if last:
                need = max(need, int(last + 200))
        cal["worst"][str(w)] = det
        cal["ncap"][str(w)] = min(4090, max(need, 2000 + 700 * w))
        print(f"  w{w}: {det}  -> ncap {cal['ncap'][str(w)]}")
    tmp.unlink(missing_ok=True)
    CALIB.write_text(json.dumps(cal, indent=1))
    print(f"  -> {CALIB}")
    return 0


# --------------------------------------------------------------------------- #
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
    """The SAME grid on `tb_sys ret` -- the ucore's own boundary map.

    This is the core leg and it is NOT the reference: the correctness target is
    silicon (CLAUDE.md, 2026-08-04).  It is also prediction (a): the ucore as
    landed implements `B0` (`bnd_armed` is set only at a retire), so its column
    IS the `*.*.B0` row of the hypothesis table, measured rather than asserted."""
    tbs = _tbsys()
    cal = _cal()
    d = OUT / "core"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "_run.hex"

    def cap(img, w, ncap):
        tmp.unlink(missing_ok=True)
        r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w, quiet=True)
        return r["words"], {}

    cells = grid(_select(a.legs))
    table, _u, secs = _sweep(cal, cells, cap, d)
    tmp.unlink(missing_ok=True)
    table = _merge(d, table)
    man = {"tool": "iret_tf_cell core", "leg": "tb_sys ret",
           "receipt": _tbsys_receipt(), "cells": len(table),
           "seconds": round(secs, 1), "block": BLOCK, "R": R,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "table.json").write_text(json.dumps(table, indent=1))
    print(f"  core: {len(table)} cells in {secs:.0f}s -> {d}")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


# --------------------------------------------------------------------------- #
# the BOARD leg
# --------------------------------------------------------------------------- #
def _board():
    import v30run
    from t2b_board import HOST
    from s13_board import div_guard
    from s10_board import pin_div, DIV_OF_RECORD
    import emit_suite as es
    assert es.EMIT_USE_CORE is False, \
        "iret_tf_cell refuses to run: truth source is not the socket"
    return v30run, HOST, div_guard, pin_div, DIV_OF_RECORD


def _flash_pin():
    p = ROOT / "sw" / "testdata" / "flash_log.jsonl"
    ls = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return {"entries": len(ls), "tail": ls[-1]}


def cmd_run(a):
    v30run, HOST, div_guard, pin_div, DIV = _board()
    cal = _cal()
    d = OUT / "board"
    d.mkdir(parents=True, exist_ok=True)
    legs = _select(a.legs)
    man = {"tool": "iret_tf_cell run", "host": HOST, "use_core": False,
           "div": DIV, "spec": "docs/notes/iret_tf_cell_prereg_2026-08-11.md",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "flash": _flash_pin(), "block": BLOCK, "R": R, "legs": legs,
           "images": {f"{lg}_a{al}": image_sha(lg, al)
                      for lg in legs for al in ALIGNS},
           "div_guards": []}
    print("== single-writer / reachability")
    man["preflight"] = tf.single_writer(HOST)
    if man["preflight"]["single_writer"] != "OK" and not a.force:
        (d / "manifest_aborted.json").write_text(json.dumps(man, indent=1))
        raise SystemExit("single-writer check did not pass -- STOP (CLAUDE.md)")
    print(f"== flash pin: {man['flash']['entries']} entries, "
          f"sof {man['flash']['tail']['sha256'][:16]}...")
    pin_div()
    man["div_guards"].append(("preflight", div_guard("preflight")))

    errs = {"n": 0, "run": 0}

    def cap(img, w, ncap):
        for _attempt in (1, 2, 3):
            try:
                _recs, _fired, words = v30run.run_image(
                    img, HOST, tag="irettf", waits=w, use_core=False, div=DIV,
                    want_raw=True, cap=ncap)
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
    for lg in legs:
        man["div_guards"].append((lg, div_guard(lg)))
        t, u, sec = _sweep(cal, grid([lg]), cap, d,
                           reps_every=a.reps_every, reps=a.reps, progress=0)
        table += t
        unstable += u
        secs += sec
        out = _merge(d, table)
        man.update(cells=len(out), seconds=round(secs, 1),
                   transport_errors=errs["n"], unstable=unstable)
        (d / "manifest.json").write_text(json.dumps(man, indent=1))
        (d / "table.json").write_text(json.dumps(out, indent=1))
        offs = sorted({x for r in t for x in (r.get("pushed_off") or [])})
        print(f"  {lg:12s} {len(t)} cells  off={offs}  ({secs:.0f}s)",
              flush=True)
    man["div_guards"].append(("final", div_guard("final")))
    out = _merge(d, table)
    man["cells"] = len(out)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "table.json").write_text(json.dumps(out, indent=1))
    print(f"\n  board: {len(table)} cells in {secs:.0f}s, "
          f"{errs['n']} transport errors, {len(unstable)} TAKE-unstable")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def _load(which):
    p = OUT / which / "table.json"
    if not p.exists():
        raise SystemExit(f"no {p}")
    return json.loads(p.read_text())


COLS = ["n_entries", "pushed_off", "pushed_off_set", "lastcode_off_set",
        "uniform", "term_done"]


def cmd_score(a):
    board = _load("board")
    try:
        core = _load("core")
    except SystemExit:
        core = []
    stage = a.stage
    ck = {r["cell"]: r for r in core}
    pred = json.loads(PRED.read_text()) if PRED.exists() else {"legs": {}}
    legs = [k for k in LEG_ORDER
            if stage in ("all", LEGS[k]["stage"])]
    out = {"stage": stage, "controls": {}, "boundary": {}, "rules": {},
           "diff": [], "columns": {}, "confirm": {}, "repro": {}}

    print("== 0. THE NULL -- nothing below is quotable without it\n")
    for lg in [k for k in legs if k in CONTROL_LEGS]:
        sel = [r for r in board if r["leg"] == lg]
        ent = sorted({r.get("n_entries") for r in sel})
        bad = [r["cell"] for r in sel if r.get("n_entries")]
        out["controls"][lg] = {"cells": len(sel), "entry_counts": ent,
                               "nonzero": bad}
        print(f"  {lg:12s} {len(sel)} cells, vector-1 entries {ent} "
              f"-- {'PASS' if not bad else 'FAIL ' + str(bad)}")

    print("\n== 0b. THE INSTRUMENT CONTROL -- the `repro` legs are tf0f's own "
          "images,\n       byte for byte, and must reproduce its published chip "
          "column\n")
    for lg, want in (pred.get("repro_expect_chip") or {}).items():
        sel = [r for r in board if r["leg"] == lg and r.get("ok")]
        got = sorted({x for r in sel for x in r["pushed_off"]})
        ident = all(v for k, v in
                    (pred.get("repro_image_identical_to_tf0f") or {}).items()
                    if k.startswith(lg + "_"))
        out["repro"][lg] = {"want": want, "got": got, "cells": len(sel),
                            "images_identical": ident,
                            "pass": (got == [want] and ident)}
        if sel:
            print(f"  {lg:12s} tf0f published {want}, measured {got}, "
                  f"images byte-identical {ident} -- "
                  f"{'PASS' if out['repro'][lg]['pass'] else 'FAIL'}")

    print("\n== 1. THE MEASURED BOUNDARY, per leg: pushed_off\n")
    hdr = f"  {'stg':4s} {'leg':13s} {'bytes':18s} {'f':1s} | " \
          f"{'chip':9s} | {'core':9s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for lg in legs:
        if lg in CONTROL_LEGS:
            continue
        sel = [r for r in board if r["leg"] == lg and r.get("ok")]
        if not sel:
            continue
        vals, cvals = Counter(), Counter()
        for r in sel:
            vals.update(r["pushed_off"])
        for r in core:
            if r["leg"] == lg and r.get("ok"):
                cvals.update(r["pushed_off"])
        pr = pred["legs"].get(lg, {}).get("pushed_off") or {}
        out["boundary"][lg] = {
            "chip": dict(vals), "core": dict(cvals), "pred": pr,
            "chip_unique": (len(vals) == 1),
            "chip_off": (next(iter(vals)) if len(vals) == 1 else None),
            "core_unique": (len(cvals) == 1),
            "core_off": (next(iter(cvals)) if len(cvals) == 1 else None),
            "n_cells": len(sel), "n_traps": sum(vals.values()),
            "stage": LEGS[lg]["stage"], "geom": LEGS[lg]["geom"],
            "probe": LEGS[lg]["probe"],
            "separates": pred["legs"].get(lg, {}).get("separates")}
        print(f"  {LEGS[lg]['stage']:4s} {lg:13s} "
              f"{PROBES[LEGS[lg]['probe']][0].hex():18s} {filler_of(lg)} | "
              f"{str(dict(vals)):9s} | {str(dict(cvals)):9s}"
              + ("" if out["boundary"][lg]["separates"] else "   (no sep)"))

    print("\n== 2. WHICH COMPOSITE RULE SURVIVES -- chip, then core\n")
    scored = [lg for lg in legs if lg in out["boundary"]]
    for col in ("chip", "core"):
        print(f"  -- vs {col.upper()} ({len(scored)} legs) --")
        best = []
        for (s, p, b) in rules():
            nm = rule_name(s, p, b)
            ag, tot, miss = 0, 0, []
            for lg in scored:
                pv = out["boundary"][lg]["pred"].get(nm)
                if pv is None:
                    continue
                tot += 1
                mv = out["boundary"][lg][f"{col}_off"]
                if out["boundary"][lg][f"{col}_unique"] and mv == pv:
                    ag += 1
                else:
                    miss.append(lg)
            out["rules"].setdefault(nm, {})[col] = {
                "agree": ag, "of": tot, "misses": miss}
            best.append((ag, tot, nm, miss))
        best.sort(key=lambda x: -x[0])
        for ag, tot, nm, miss in best:
            flag = "   <== ALL" if ag == tot else ""
            ms = "" if ag == tot else \
                "   misses: " + ",".join(miss[:6]) + \
                ("..." if len(miss) > 6 else "")
            print(f"    {nm:14s} {ag:3d}/{tot:3d}{flag}{ms}")
        print()

    print("== 3. chip vs core, cell for cell")
    diff, tot = Counter(), Counter()
    for r in board:
        if r["leg"] not in legs:
            continue
        c = ck.get(r["cell"])
        if not c:
            continue
        for k in COLS:
            tot[k] += 1
            if r.get(k) != c.get(k):
                diff[k] += 1
                if k == "pushed_off":
                    out["diff"].append(
                        {"cell": r["cell"], "chip": r.get("pushed_off"),
                         "core": c.get("pushed_off")})
    for k in COLS:
        out["columns"][k] = {"diff": diff[k], "compared": tot[k]}
        print(f"  {k:18s} {diff[k]:4d} / {tot[k]:4d}"
              f"{'   <== DIFFERS' if diff[k] else ''}")

    print("\n== 4. structural validity and stability")
    inval = [r["cell"] for r in board if r["leg"] in legs and not r.get("ok")]
    rep = [r for r in board if r["leg"] in legs and "rep_shas" in r]
    tu = [r["cell"] for r in rep if not r.get("take_stable")]
    sd = [r["cell"] for r in rep if not r.get("stable")]
    n_board = len([r for r in board if r["leg"] in legs])
    out["confirm"] = {"invalid": inval, "repeated": len(rep), "of": n_board,
                      "take_unstable": tu, "stream_distinct": sd}
    print(f"  structurally invalid cells: {len(inval)} of {n_board}"
          f"{'  ' + str(inval[:8]) if inval else ''}")
    print(f"  {len(rep)}/{n_board} cells captured x3: "
          f"TAKE-unstable {len(tu)}, stream-distinct {len(sd)}")
    (OUT / f"score_{stage}.json").write_text(json.dumps(out, indent=1))
    print(f"\n  -> {OUT / f'score_{stage}.json'}")
    return 0


# --------------------------------------------------------------------------- #
# the QS-pin control -- does the divergence, if any, live in the front end?
# --------------------------------------------------------------------------- #
def _qs_stream(which, leg, waits, align):
    p = OUT / which / f"{stratum_key(leg, waits)}.raw.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt") as fh:
        sh = json.load(fh)
    key = cell_key(leg, waits, align)
    if key not in sh:
        return None
    rows = _rows_from_words([int(x, 16) for x in sh[key]])
    _img, meta = image_of(leg, align)
    a = next((i for i, r in enumerate(rows)
              if r["t"] == 1 and r["bs_early"] == BS_CODE
              and r["ad_addr"] == meta["anchor_linear"]), None)
    if a is None:
        return None
    ops = []
    for i in range(a, len(rows)):
        r = rows[i]
        if r["qs"]:
            ops.append(r["qs"])
        if r["t"] == 1 and r["bs_early"] == BS_MEMR and r["ad_addr"] == IVT1_OFF:
            break
    return ops


def cmd_qs(a):
    """Do the chip and the core emit the SAME QS stream up to the first
    vector-1 entry?  If they do, any trap-boundary divergence is NOT a queue or
    decode-front-end divergence and is localised to what CONSUMES the stream.
    Pins only -- no engine is in this comparison."""
    board = {r["cell"] for r in _load("board")}
    out = {"stream_diff": [], "compared": 0, "per_leg": {}}
    print("== the QS PIN stream, chip vs core, to the first vector-1 entry\n")
    for lg in LEG_ORDER:
        diff, n = 0, 0
        for w in WAITS:
            for al in ALIGNS:
                if cell_key(lg, w, al) not in board:
                    continue
                qb = _qs_stream("board", lg, w, al)
                qc = _qs_stream("core", lg, w, al)
                if qb is None or qc is None:
                    continue
                k = min(len(qb), len(qc))
                n += 1
                out["compared"] += 1
                if qb[:k] != qc[:k]:
                    diff += 1
                    out["stream_diff"].append(cell_key(lg, w, al))
        if n:
            out["per_leg"][lg] = {"diff": diff, "of": n}
            print(f"  {lg:13s} {diff} of {n} cells differ"
                  f"{'   <== DIFFERS' if diff else ''}")
    (OUT / "qs.json").write_text(json.dumps(out, indent=1))
    print(f"\n  compared {out['compared']} cells, "
          f"{len(out['stream_diff'])} differ  -> {OUT / 'qs.json'}")
    return 0


# --------------------------------------------------------------------------- #
def cmd_idle(a):
    import b1_recapture
    r = b1_recapture.board_idle()
    print(f"board_idle -> {r}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("calib").set_defaults(fn=cmd_calib)
    sub.add_parser("predict").set_defaults(fn=cmd_predict)

    p = sub.add_parser("core")
    p.add_argument("--legs", default="")
    p.set_defaults(fn=cmd_core)

    p = sub.add_parser("run")
    p.add_argument("--legs", default="")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--reps-every", type=int, default=8)
    p.add_argument("--force", action="store_true",
                   help="proceed past a failed single-writer check (recorded)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("score")
    p.add_argument("--stage", default="der", choices=("der", "val", "all"))
    p.set_defaults(fn=cmd_score)

    sub.add_parser("qs").set_defaults(fn=cmd_qs)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
