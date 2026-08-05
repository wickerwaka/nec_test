#!/usr/bin/env python3
"""sm3_h1_cell -- THE DIRECTED BOARD CELL for H1 (I3's sec.26.6.4 cell, the
whole-program half).

Spec and PRE-REGISTERED per-candidate predictions:
`docs/notes/sm3_h1_prereg_2026-08-04.md` sec.5.  Read it before running this;
the predictions were committed BEFORE the first board contact of the sitting.

WHAT IT ASKS.  The banked EVT population says a re-entry acknowledge opens at
`max(F1 + 6, F1 + L + 1)` with F1 the refilling CODE fetch's T1.  Every one of
those boundaries follows an IRET, and no golden form has a queue-flushing
anchor instruction at all, so two readings survive offline:

  C1   the floor belongs to any REDIRECT, and sits at the RESTARTED
       PREFETCH's index 2;
  C1'  ...at the REDIRECT's OWN commit + 4  (identical whenever the restart is
       granted at the redirect's e+2, which is every case in the bank);
  C3   the floor belongs to IRET specifically.

This cell drives boundaries that follow a NEAR JMP, a FAR JMP and a near
CALL/RET pair -- none of them an IRET -- and sweeps the assert delay so the
recognition lands at every phase of the loop, at four wait levels.  A NOP sled
is the control: it has no redirect, and must reproduce the golden law.

BOARD DISCIPLINE (CLAUDE.md).  Single-writer checked by the caller; SOCKET ONLY
(`use_core=False`, explicit, because the board's CFG is sticky); the divider
PINNED and `div_guard`'s readback RECORDED on every probe; the FULL per-clock
rows retained beside the raw 64-bit words and their sha256; `board_idle()` at
the end; a run of consecutive transport errors STOPS the cell rather than
grinding on.  NO FLASHING -- the board carries FLASH #4 and this cell does not
use the core.

Usage:
    python3 sw/sm3_h1_cell.py run   [--pilot] [--waits 0,1,2,3] [--delays N]
    python3 sw/sm3_h1_cell.py report
    python3 sw/sm3_h1_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage                                        # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import sm3_ackgeom as ag                                # noqa: E402
from gen_seq import (Prog, PC0, SP0, DATA_LO, DATA_HI,  # noqa: E402
                     far_int_support, SWINT_VEC)
from s10_board import capture, DIV_OF_RECORD            # noqa: E402
from s13_board import div_guard                         # noqa: E402
from t2b_board import HOST                              # noqa: E402
import emit_suite as es                                 # noqa: E402

assert es.EMIT_USE_CORE is False, "H1 cell refuses to run: truth is the socket"

OUT = ROOT / "sw" / "testdata" / "sm3-h1cell"
INTA, CODE, HALT = 0, 4, 3


def set_out(name):
    """Point the cell at a DIFFERENT retention directory.  Sitting 7's H1a cell
    is a new question on the same instrument, and overwriting sitting 5's
    `manifest.json` would destroy a retained record to save a directory."""
    global OUT
    OUT = ROOT / "sw" / "testdata" / name
    return OUT


# --------------------------------------------------------------------------- #
# the stimuli
# --------------------------------------------------------------------------- #
VARIANTS = ("nop", "ebnext", "farnext", "callret", "iretnext", "clipopf",
            "swintnext")

# --------------------------------------------------------------------------- #
# SITTING 11 -- the IE-RESTORE cell.  `clipopf` (k = 0 padding) produced NO
# ACKNOWLEDGE in 24/24 captures and §61.3 booked that as an open question.  It
# is not a defect in the stimulus: with `CLI ; POPF` back to back the ONLY
# boundary at which IE is set is the POPF's own, so any law that cannot
# recognise at the boundary where IE ROSE can never recognise at all.  The fix
# is PADDING -- put N NOPs between the POPF and the next CLI, so a boundary
# EXISTS after the rise with IE still up, and read off the pins WHICH boundary
# the part chose.  The pushed frame's IP is on the bus; no engine is needed.
#
# The period is (2 + PAD) bytes and every instruction is 1 byte, so
#
#     phase = (pushed_IP - PC0) mod (2 + PAD)
#
# names the boundary exactly:
#     0  the boundary BEFORE the CLI (end of the previous iteration)
#     1  after the CLI            -- IE is CLEAR here
#     2  after the POPF/STI       -- THE BOUNDARY AT WHICH IE ROSE
#     3.. after NOP #1, #2, ...   -- IE up, and the rise is behind us
S11_PAD = 2
S11_VARIANTS = ("iepop", "iesti", "iehot")

# --------------------------------------------------------------------------- #
# SITTING 13 -- THE PADDING-LENGTH CELL (Codex phase-review concern 4b).
#
# §72.7's law is written "two clocks after PSW.IE's rising edge".  On the
# sitting-11 geometry that reading and a BOUNDARY-QUANTISATION one -- a sampler
# that simply rejects the first boundary after the rise, whatever its distance
# in clocks -- are OBSERVATIONALLY IDENTICAL, because the pad instruction is a
# NOP and the first boundary after the rise sits ~2 clocks away.  The two
# readings coincide only at that spacing.
#
# THEY SEPARATE IF THE FIRST BOUNDARY AFTER THE RISE IS MOVED FAR AWAY IN
# CLOCKS.  Put a LONG instruction immediately after the POPF and ask whether
# the boundary it ends is available:
#
#     a 2-clock TIMER          ->  it is >= 2 clocks after the rise: AVAILABLE
#     BOUNDARY QUANTISATION    ->  it is the first boundary after the rise:
#                                  REJECTED, and the entry appears one further on
#
# So the axis is the PAD INSTRUCTION'S CLOCK LENGTH, measured off the pins on a
# no-rise control of the SAME geometry, and the observable is unchanged: which
# boundary the pushed IP names.  Every sled is five instructions long and the
# `hot` twin has the same byte period, so the two are read on one scale.
S13_PADS = {
    "nop":  ([0x90],       "NOP -- the sitting-11 spacing, the anchor"),
    "cld":  ([0xFC],       "CLD -- 1 byte, flag only"),
    "xchg": ([0x93],       "XCHG AW,BW -- 1 byte, registers only"),
    "rol":  ([0xD2, 0xC0], "ROL AL,CL with CL = 3 -- AL/flags only, variable"),
    "mul":  ([0xF6, 0xE3], "MUL BL -- AW/flags only, the LONG pad"),
}
S13_VARIANTS = tuple([f"pad{k}" for k in S13_PADS]
                     + [f"hot{k}" for k in S13_PADS])


def s13_sled(variant):
    """(instruction byte-lists of ONE period, label of the boundary AFTER each).

      pad*  CLI ; POPF ; PAD ; NOP ; NOP     -- IE RISES at the POPF
      hot*  POPF ; PAD ; NOP ; NOP ; NOP     -- IE already up, popped word up:
                                                the SAME geometry with NO RISE

    `OWN` is the boundary the IE-writing instruction itself ends; `B1` is the
    FIRST boundary after it -- the one this cell moves in clocks -- and `DEAD`
    is the boundary at which IE is clear.
    """
    kind, pad = variant[:3], variant[3:]
    body = list(S13_PADS[pad][0])
    if kind == "pad":
        return ([[0xFA], [0x9D], body, [0x90], [0x90]],
                ["DEAD", "OWN", "B1", "B2", "B3"])
    return ([[0x9D], body, [0x90], [0x90], [0x90]],
            ["OWN", "B1", "B2", "B3", "B4"])


def s13_boundary(ip, variant):
    """Which boundary of the sled the pushed IP names.  -> label or None.

    The pushed IP is the address of the instruction that WOULD have run next,
    i.e. the START of instruction j -- so the entry was taken at the boundary
    AFTER instruction j-1.  Anything that is not an instruction start is
    reported as None rather than rounded to one."""
    instrs, labels = s13_sled(variant)
    starts, off = [], 0
    for b in instrs:
        starts.append(off)
        off += len(b)
    period = off
    o = (ip - PC0) % period
    if o not in starts:
        return None
    j = starts.index(o)
    return labels[(j - 1) % len(labels)]

# H7 sitting 7, the OPCODE axis (§65.1's lead).  Each is a straight-line sled of
# ONE instruction, chosen so the stream has a dense, uniform boundary set and no
# cumulative side effect over ~200 iterations.  The two GOLDEN NMI forms' own
# opcodes are first; the rest are drawn from `sm3_h7_opcode`'s census of the
# banked seeds that sit at the chip floor.
OPCODE_SLEDS = {
    "op90nop":   ([0x90], "NOP -- golden NMI.90's opcode"),
    "opB8mov":   ([0xB8, 0x34, 0x12], "MOV AW,imm16 -- golden NMI.B8's opcode"),
    "opFCcld":   ([0xFC], "CLD -- 1 byte, flag only"),
    "op41inc":   ([0x41], "INC CW -- 1 byte, register only"),
    "op84test":  ([0x84, 0xC0], "TEST AL,AL -- 2 bytes, flags only"),
    "op03add":   ([0x03, 0xC0], "ADD AW,AW -- 2 bytes, register only"),
    "op2Fdas":   ([0x2F], "DAS -- 1 byte, AL/flags only"),
    "opB0mov8":  ([0xB0, 0x5A], "MOV AL,imm8 -- 2 bytes"),
    "op70jo":    ([0x70, 0x00], "JO +0 -- NOT taken (OF clear): no redirect"),
    "op71jno":   ([0x71, 0x00], "JNO +0 -- TAKEN: a redirect every instruction"),
}
H7_VARIANTS = tuple(OPCODE_SLEDS)


def program(variant, n=40):
    """`instr` bytes for one variant.  Every variant is a straight-line stream
    of the same shape; only whether each step REDIRECTS differs.

      nop      NOP  -- no redirect at all (the CONTROL)
      ebnext   EB 00 -- near JMP to the next instruction: a redirect that makes
                        NO bus cycle of its own
      farnext  EA .. -- far JMP to the next instruction: a redirect that also
                        reloads PS
      callret  E8 00 00 / C3 -- near CALL to the next instruction then near
                        RET: a redirect that commits immediately after a bus
                        cycle, which is the IRET's own shape
    """
    rng = random.Random(f"sm3-h1/{variant}")
    p = Prog(rng)
    if variant == "nop":
        for _ in range(n * 3):
            p.emit([0x90])
    elif variant == "ebnext":
        for _ in range(n):
            p.emit([0xEB, 0x00])
    elif variant == "farnext":
        for _ in range(n):
            p.emit_farjmp_next()
    elif variant == "iretnext":
        # `CF` IRET, N of them back to back.  Each pops a PRE-PLANTED frame
        # (ip = the next IRET, cs = 0, psw = IE set) off the stack and jumps to
        # it, so the part executes an IRET at a boundary that is NOT a return
        # from an acknowledge.  This is the ONE cell that separates "the
        # instruction is IRET" from "the boundary follows an interrupt entry".
        for _ in range(n * 3):
            p.emit([0xCF])
    elif variant == "clipopf":
        # `FA 9D` CLI ; POPF, N of them.  Each POPF restores a PLANTED flags
        # word with IE SET, so IE RISES at that boundary -- and the part is
        # not returning from an acknowledge.  This separates "IE rose here"
        # from "the previous entry left something behind".
        for _ in range(n * 2):
            p.emit([0xFA])
            p.emit([0x9D])
    elif variant == "swintnext":
        # `CD 20` INT SWINT_VEC, N of them back to back.  The vector points at
        # `far_int_support`'s bare `CF` handler, so each one is a REAL
        # interrupt ENTRY -- the same microcoded entry sequence, the same
        # pushed frame, IE cleared -- announced by a VECTOR READ and carrying
        # NO INTA CYCLE, returning immediately by IRET.  This is `mc1/2672`'s
        # shape (§64.2) built on purpose.
        #
        # It is also self-selecting: IE is CLEAR from the entry until the IRET
        # restores it, so the ONLY boundary in the whole stream at which a
        # maskable INT can be recognised is the one immediately after each
        # IRET's restarted prefetch -- exactly the boundary H1a is about.
        for _ in range(n * 2):
            p.emit([0xCD, SWINT_VEC])
    elif variant == "iepop":
        # `FA 9D 90 90` CLI ; POPF ; NOP x PAD.  `clipopf` with room after the
        # rise.  Each POPF restores a PLANTED flags word with IE SET, so IE
        # RISES at that boundary, and the PAD NOPs keep IE up for PAD further
        # boundaries before the next CLI takes it down again.
        for _ in range(n * 2):
            p.emit([0xFA])
            p.emit([0x9D])
            for _ in range(S11_PAD):
                p.emit([0x90])
    elif variant == "iesti":
        # `FA FB 90 90` CLI ; STI ; NOP x PAD.  The SAME geometry with the rise
        # produced by STI instead of a stack pop -- x86's documented
        # one-instruction STI shadow is the rival reading, and this leg is what
        # separates "the EI instruction sets an inhibit" from "IE rose".
        for _ in range(n * 2):
            p.emit([0xFA])
            p.emit([0xFB])
            for _ in range(S11_PAD):
                p.emit([0x90])
    elif variant == "iehot":
        # `9D 90 90 90` POPF ; NOP x (PAD+1), with IE ALREADY SET and the
        # planted word popping IE SET: the SAME instruction, the SAME bus
        # geometry, and NO RISE.  The CONTROL that says the instrument can see
        # the POPF's own boundary at all.
        for _ in range(n * 2):
            p.emit([0x9D])
            for _ in range(S11_PAD + 1):
                p.emit([0x90])
    elif variant == "callret":
        for _ in range(n):
            p.emit([0xE8, 0x00, 0x00])     # CALL next  (pushes, redirects)
            p.emit([0xC3])                 # RET        (pops,   redirects)
    elif variant in S13_VARIANTS:
        # SITTING 13: `CLI ; POPF ; PAD ; NOP ; NOP` (or the no-rise `hot`
        # twin).  The pad's CLOCK length is the axis; see `s13_sled`.
        instrs, _labels = s13_sled(variant)
        for _ in range(n * 2):
            for b in instrs:
                p.emit(list(b))
    elif variant in OPCODE_SLEDS:
        body = OPCODE_SLEDS[variant][0]
        for _ in range(max(1, (n * 3 * 2) // len(body))):
            p.emit(list(body))
    else:
        raise SystemExit(f"unknown variant {variant}")
    return p.assemble()


def image_of(variant):
    rng = random.Random(f"sm3-h1img/{variant}")
    instr = program(variant)
    ivt, handler = far_int_support()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,        # IE set
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += handler
    if variant in ("clipopf", "iepop", "iesti", "iehot") \
            or variant in S13_VARIANTS:
        ram = [x for x in ram if not (SP0 <= x[0] < SP0 + 2 * 200)]
        for k in range(200):
            ram.append((SP0 + 2 * k, 0x02))
            ram.append((SP0 + 2 * k + 1, 0xF2))
    if variant == "iretnext":
        # the planted IRET frames: (ip, cs, psw) triples walking up from SP0
        ram = [x for x in ram if not (SP0 <= x[0] < SP0 + 6 * 130)]
        for k in range(130):
            ip = PC0 + 1 + k
            for j, w in enumerate((ip, 0x0000, 0xF202)):
                ram.append((SP0 + 6 * k + 2 * j, w & 0xFF))
                ram.append((SP0 + 6 * k + 2 * j + 1, w >> 8))
    image, meta = check_seq.compose(dict(seed=0, instr=instr, regs=regs,
                                         ram=ram, ivt=ivt))
    return image, meta


# --------------------------------------------------------------------------- #
# the observable -- read off the pins, no engine
# --------------------------------------------------------------------------- #
def measure(rows, which=0):
    """One acknowledge's lead-in geometry, chip side.  -> dict or None."""
    cy, ak = ag.acks(rows)
    if len(ak) <= which:
        return None
    ci, nlen = ak[which]
    kind, t1, end, disp = cy[ci]
    if ci == 0:
        return None
    prev = cy[ci - 1]
    L = prev[2] - prev[1] + 1
    # the flush that emptied the queue ahead of the refill, and the refill's
    # own start: both read off the pins
    qsE = None
    for i in range(t1 - 1, max(-1, t1 - 60), -1):
        if rows[i]["qs"] == 2:
            qsE = i
            break
    # the CODE cycle that first opened after that flush
    refill = None
    if qsE is not None:
        for c in cy:
            if c[0] == CODE and c[1] > qsE:
                refill = c
                break
    prevprev = cy[ci - 2] if ci >= 2 else None
    return {"ack_t1": t1, "ack_disp": disp, "n_inta": nlen,
            "prev_kind": fc.BS_NAME[prev[0]], "prev_t1": prev[1],
            "prev_len": L, "gap": t1 - prev[1],
            "qsE": qsE, "flush_to_F1": (None if (qsE is None or refill is None)
                                        else refill[1] - qsE),
            "refill_t1": None if refill is None else refill[1],
            "refill_len": None if refill is None else refill[2] - refill[1] + 1,
            "refill_gap": None if refill is None else t1 - refill[1],
            "prevprev_kind": None if prevprev is None else fc.BS_NAME[prevprev[0]],
            "prevprev_end": None if prevprev is None else prevprev[2],
            "ord": which + 1, "nack": len(ak),
            "ncode_before": sum(1 for c in cy[:ci] if c[0] == CODE),
            "nhalt": sum(1 for c in cy if c[0] == HALT)}


# --------------------------------------------------------------------------- #
# SITTING 11 -- the observable, read off the pins with NO ENGINE.
#
# An interrupt ENTRY of any kind -- INT pin, NMI pin or a software `INT n` --
# pushes exactly three words, SP descending: PSW, then CS, then IP.  None of
# the sitting-11 sleds contains any other memory WRITE, so a run of three MEMW
# cycles whose addresses step DOWN by two IS an entry, and its third word is
# the RETURN ADDRESS -- i.e. the BOUNDARY the part chose.  That is the whole
# measurement, and it works identically for a maskable acknowledge (which has
# INTA cycles) and for an NMI (which has none).
# --------------------------------------------------------------------------- #
MEMW = 6


def _cycle_data(rows, c):
    """The 16-bit value a bus cycle carried.  AD is the ADDRESS at T1 and the
    DATA from T2 on -- and by the cycle's last retained row the pads may
    already be driving the NEXT cycle's address, so the sample is T2."""
    return rows[min(c[1] + 1, c[2])]["ad_data"] & 0xFFFF


def entry_frames(rows):
    """Every interrupt entry's pushed frame, chip side.  -> list of dicts."""
    cy = ag.cycles(rows, len(rows))
    out = []
    i = 0
    while i + 2 < len(cy):
        a, b, c = cy[i], cy[i + 1], cy[i + 2]
        if (a[0] == MEMW and b[0] == MEMW and c[0] == MEMW
                and (rows[a[1]]["ad_addr"] & 0xFFFFF) - 2
                == (rows[b[1]]["ad_addr"] & 0xFFFFF)
                and (rows[b[1]]["ad_addr"] & 0xFFFFF) - 2
                == (rows[c[1]]["ad_addr"] & 0xFFFFF)):
            # walk BACK over the entry's announcement: an INTA pair (pin INT)
            # or the two IVT vector reads below 0x400 (NMI / software INT).
            j = i
            while j > 0 and (cy[j - 1][0] == INTA
                             or (cy[j - 1][0] == 5
                                 and (rows[cy[j - 1][1]]["ad_addr"] & 0xFFFFF)
                                 < 0x00400)):
                j -= 1
            # ...and the last STACK read before that: the POPF's own pop, i.e.
            # the clock at which IE was committed.  Read off the pins.
            pop = None
            for x in range(j - 1, max(-1, j - 8), -1):
                if cy[x][0] == 5 and (rows[cy[x][1]]["ad_addr"] & 0xFFFFF) \
                        >= SP0:
                    pop = cy[x][1]
                    break
            out.append({"push_t1": a[1], "ann_t1": cy[j][1], "pop_t1": pop,
                        "psw": _cycle_data(rows, a),
                        "cs": _cycle_data(rows, b),
                        "ip": _cycle_data(rows, c),
                        "inta_before": any(x[0] == INTA for x in
                                           cy[max(0, i - 6):i])})
            i += 3
            continue
        i += 1
    return out


def s11_phase(ip, period):
    """Which boundary of the sled the pushed IP names.  See S11_VARIANTS."""
    return ((ip - PC0) % period + period) % period


S11_PERIOD = {"iepop": 2 + S11_PAD, "iesti": 2 + S11_PAD,
              "iehot": 2 + S11_PAD, "clipopf": 2}
# the phase of the IE-writing instruction's OWN boundary.  In `iepop`/`iesti`/
# `clipopf` IE ROSE there and the IE-restore reading FORBIDS a maskable
# recognition at it; in `iehot` the same instruction runs with no rise and the
# same boundary must be AVAILABLE -- that is what makes `iehot` the control.
S11_OWN_PHASE = {"iepop": 2, "iesti": 2, "iehot": 1, "clipopf": 0}
# the phase at which IE is CLEAR (the CLI just ran) -- forbidden to a maskable
# recognition under EVERY reading that tests IE at the boundary
S11_DEAD_PHASE = {"iepop": 1, "iesti": 1, "iehot": None, "clipopf": 1}


# --------------------------------------------------------------------------- #
def cmd_run(args):
    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in args.waits.split(",") if x != ""]
    variants = [v for v in args.variants.split(",") if v]
    pins = [int(x) for x in getattr(args, "pins", "0").split(",") if x != ""]
    delays = list(range(args.d0, args.d0 + args.delays))
    if args.pilot:
        delays = delays[:6]
        waits = waits[:2]
    man = {"cell": "SM3 H1 -- the recognition boundary after a REDIRECT",
           "spec": "docs/notes/sm3_h1_prereg_2026-08-04.md sec.5",
           "prereg_commit": args.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "variants": variants,
           "pins": pins, "pad": S11_PAD,
           "delays": [delays[0], delays[-1]], "hold": args.hold, "cells": {}}
    man["div_guard"] = div_guard("sm3-h1cell")
    rows_out = []
    t0 = time.time()
    consec_err = 0
    for variant in variants:
        image, meta = image_of(variant)
        anchor = meta["anchor_linear"] if "anchor_linear" in meta else \
            (0 * 16 + PC0)
        for pin in pins:
          for w in waits:
            for d in delays:
                key = (f"{variant}:w{w}:d{d}" if len(pins) == 1 and pin == 0
                       else f"{variant}:p{pin}:w{w}:d{d}")
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD,
                        evt=(anchor & 0xFFFFF, d, args.hold, pin),
                        tag="sm3h1")
                    consec_err = 0
                except Exception as e:                    # noqa: BLE001
                    consec_err += 1
                    print(f"  {key}: TRANSPORT ERROR {e}", flush=True)
                    if consec_err >= 5:
                        print("  *** 5 consecutive transport errors -- STOP "
                              "(the board is not nursed along) ***", flush=True)
                        man["stopped"] = key
                        break
                    continue
                g = measure(rows)
                gs = [measure(rows, i) for i in range(6)]
                rec = {"key": key, "acks": [x for x in gs if x], "variant": variant, "waits": w, "delay": d,
                       "pin": pin,
                       "sha": sha, "fired": bool(fired), "nrows": len(rows),
                       "frames": entry_frames(rows),
                       "geom": g}
                rows_out.append(rec)
                man["cells"][key] = {"sha": sha, "rows": len(rows),
                                     "fired": bool(fired)}
                with gzip.open(OUT / f"{key.replace(':','_')}.rows.json.gz",
                               "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(OUT / f"{key.replace(':','_')}.raw.hex.gz",
                               "wt") as f:
                    f.write("\n".join(raw) + "\n")
                if g:
                    print(f"  {key}: prev={g['prev_kind']}/L{g['prev_len']} "
                          f"gap={g['gap']} refill_gap={g['refill_gap']} "
                          f"flush->F1={g['flush_to_F1']} "
                          f"({time.time()-t0:.0f}s)", flush=True)
                else:
                    print(f"  {key}: NO ACKNOWLEDGE (fired={fired})",
                          flush=True)
            else:
                continue
            break
    man["seconds"] = round(time.time() - t0, 1)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    (OUT / "cells.json").write_text(json.dumps(rows_out, indent=1))
    _sha_dir(OUT)
    report(rows_out)
    return 0


def _sha_dir(d):
    lines = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  "
                         f"{p.relative_to(d)}")
    (d / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


def report(recs=None):
    if recs is None:
        recs = json.loads((OUT / "cells.json").read_text())
    print("\n  --- SM3 H1 directed cell: the acknowledge's lead-in ---")
    print("  (PRE-REGISTERED, sm3_h1_prereg_2026-08-04.md sec.5:"
          "  P1 = every REDIRECT variant shows gap max(6, L+1);"
          "  P3 = they show gap L (=4 at w0) -> C1 REFUTED, revert.)")
    by = defaultdict(Counter)
    for r in recs:
        g = r["geom"]
        if not g or g["prev_kind"] != "CODE":
            continue
        by[(r["variant"], r["waits"])][(g["prev_len"], g["gap"])] += 1
    for k in sorted(by):
        tot = sum(by[k].values())
        print(f"  {k[0]:<8} w{k[1]}  n={tot:<4} " +
              "  ".join(f"L{L}->gap{gp}:{n}"
                        for (L, gp), n in sorted(by[k].items())))
    # C1 vs C1': does the acknowledge move with a DELAYED refill?
    print("\n  --- C1 vs C1': gap from the REFILL fetch's T1, by flush->F1 ---")
    d2 = defaultdict(Counter)
    for r in recs:
        g = r["geom"]
        if not g or g["refill_gap"] is None:
            continue
        d2[(r["variant"], r["waits"])][(g["flush_to_F1"], g["refill_len"],
                                        g["refill_gap"])] += 1
    for k in sorted(d2):
        print(f"  {k[0]:<8} w{k[1]}  " +
              "  ".join(f"(fl->F1={a},L={b})->gap{c}:{n}"
                        for (a, b, c), n in sorted(d2[k].items(),
                                                   key=lambda x: -x[1])[:8]))


# --------------------------------------------------------------------------- #
# SITTING 7 -- H1a's verdict, read off the retained rows with no engine
# --------------------------------------------------------------------------- #
HANDLER_AT = 0x0480


def entry_shape(rows, ack_t1):
    """Is `mc1/2672`'s shape immediately behind this acknowledge?

    Scanning BACK from the acknowledge's T1, in order:
      1. a contiguous triple of stack reads (the IRET's three pops),
      2. before them a CODE fetch of the handler at HANDLER_AT,
      3. before that a MEMR below 0x00400 -- an IVT VECTOR READ, i.e. an
         interrupt ENTRY that was announced by a vector read and NOT by an
         INTA cycle.
    Returns one of 'swint-entry', 'iret-only', 'inta-behind', 'other'."""
    cy = ag.cycles(rows, len(rows))
    ci = next((k for k, c in enumerate(cy) if c[1] == ack_t1), None)
    if ci is None or ci < 4:
        return "other"
    back = cy[max(0, ci - 14):ci][::-1]
    if any(c[0] == INTA for c in back):
        return "inta-behind"
    pops = [c for c in back if c[0] == 5]        # MEMR
    trip = [c for c in pops if 0x03000 <= (rows[c[1]]["ad_addr"] & 0xFFFFF)
            < 0x04000]
    if len(trip) < 3:
        return "other"
    handler = any(c[0] == CODE and
                  (rows[c[1]]["ad_addr"] & 0xFFFFF) >> 1 == HANDLER_AT >> 1
                  for c in back)
    vec = any(c[0] == 5 and (rows[c[1]]["ad_addr"] & 0xFFFFF) < 0x00400
              for c in back)
    if handler and vec:
        return "swint-entry"
    return "iret-only"


def h1a_report(recs=None):
    """H1a: does a software-INT entry -- a REAL interrupt entry with NO INTA
    cycle -- arm the re-entry recognition floor for the NEXT acknowledge?

    The observable is `refill_gap`: the clocks from the RESTARTED PREFETCH's T1
    to the acknowledge's T1.  H1's floor is `max(F1 + 6, F1 + L + 1)`, so with
    the restart's L = 4 a FLOORED acknowledge sits at 6 and an UNFLOORED one at
    4.  Two clocks, read off the pins."""
    if recs is None:
        recs = json.loads((OUT / "cells.json").read_text())
    print("\n  --- SM3 H1a: is the arm the interrupt ENTRY or the INTA CYCLE? ---")
    print("  (PRE-REGISTERED, sm3_s7_prereg_2026-08-04.md §3:"
          "  A1 entry-generic -> swintnext FLOORED (refill_gap 6) and iretnext"
          " UNFLOORED (4);  A2 INTA-only -> BOTH unfloored.)")
    tab = defaultdict(Counter)
    shapes = defaultdict(Counter)
    for r in recs:
        g = r["geom"]
        if not g or g.get("refill_gap") is None:
            continue
        stem = r["key"].replace(":", "_")
        p = OUT / f"{stem}.rows.json.gz"
        sh = "?"
        if p.exists():
            rows = json.load(gzip.open(p, "rt"))
            sh = entry_shape(rows, g["ack_t1"])
        shapes[(r["variant"], r["waits"])][sh] += 1
        if sh in ("swint-entry", "iret-only"):
            tab[(r["variant"], r["waits"], sh)][
                (g["refill_len"], g["refill_gap"])] += 1
    print(f"\n  {'variant':<11}{'w':>3}  lead-in shape behind the FIRST acknowledge")
    for k in sorted(shapes):
        print(f"  {k[0]:<11}{k[1]:>3}  {dict(shapes[k])}")
    print(f"\n  {'variant':<11}{'w':>3} {'shape':<12} (refill L -> gap): n")
    floored = unfloored = 0
    for k in sorted(tab):
        cells = sorted(tab[k].items(), key=lambda x: -x[1])
        print(f"  {k[0]:<11}{k[1]:>3} {k[2]:<12} " +
              "  ".join(f"L{a}->gap{b}:{n}" for (a, b), n in cells))
        for (L, gp), n in cells:
            if L is None or gp is None:
                continue
            if gp >= max(6, L + 1):
                floored += n
            elif gp == L:
                unfloored += n
    print(f"\n  TOTALS over scored first acknowledges: "
          f"FLOORED {floored}   UNFLOORED {unfloored}")
    return 0


def s11_report(recs=None):
    """SITTING 11 -- WHICH BOUNDARY does the part choose when IE RISES?

    Chip side, no engine.  For every capture, the FIRST entry's pushed IP is
    reduced to a sled PHASE (see S11_VARIANTS), and the statistic is a
    MINIMUM-style one: a phase either OCCURS over the delay sweep or it does
    not.  §71.6's IE-restore reading forbids the raising instruction's OWN
    boundary to a MASKABLE recognition and forbids nothing to an NMI."""
    if recs is None:
        recs = json.loads((OUT / "cells.json").read_text())
    print("\n  --- SM3 sitting 11: the boundary an IE RISE is recognised at ---")
    print("  (PRE-REGISTERED, sm3_s11_prereg_2026-08-04.md §4)")
    tab = defaultdict(Counter)
    noack = Counter()
    tot = Counter()
    for r in recs:
        v = r["variant"]
        if v not in S11_PERIOD:
            continue
        grp = (v, r.get("pin", 0), r["waits"])
        tot[grp] += 1
        fr = r.get("frames") or []
        if not fr:
            noack[grp] += 1
            continue
        tab[grp][s11_phase(fr[0]["ip"], S11_PERIOD[v])] += 1
    print(f"\n  {'variant':<9}{'pin':>4}{'w':>3}  {'n':>4} {'noENTRY':>8}   "
          f"first-entry PHASE histogram   [own={'OWN'} dead=IE-clear]")
    for k in sorted(tab | noack, key=lambda x: (x[0], x[1], x[2])):
        own = S11_OWN_PHASE[k[0]]
        dead = S11_DEAD_PHASE[k[0]]
        h = tab[k]
        mark = "  ".join(
            f"p{p}{'*OWN' if p == own else ('*DEAD' if p == dead else '')}:{n}"
            for p, n in sorted(h.items()))
        print(f"  {k[0]:<9}{k[1]:>4}{k[2]:>3}  {tot[k]:>4} {noack[k]:>8}   "
              f"{mark}")
    print("\n  VERDICT COORDINATES (w0 only -- the discriminating regime):")
    for v in sorted(S11_PERIOD):
        for pin in (0, 1):
            k = (v, pin, 0)
            if k not in tot:
                continue
            own = S11_OWN_PHASE[v]
            dead = S11_DEAD_PHASE[v]
            print(f"    {v:<9} pin{pin} w0: n={tot[k]:<4} "
                  f"noENTRY={noack[k]:<4} OWN(p{own})={tab[k][own]:<4} "
                  f"DEAD(p{dead})={0 if dead is None else tab[k][dead]}")
    return 0


def s13_rows(recs):
    """(variant, pin, w) -> {label: [pop->ann clocks]}, plus the no-entry count.

    Chip side, no engine.  `pop_t1` is the POPF's own stack read -- the clock at
    which IE was committed, read off the pins -- and `ann_t1` is the entry's
    announcement, so `ann - pop` is an ABSOLUTE clock coordinate that needs no
    model.  It is the same coordinate §72.3 used to measure the +2."""
    tab = defaultdict(lambda: defaultdict(list))
    noent = Counter()
    tot = Counter()
    unmapped = Counter()
    for r in recs:
        v = r["variant"]
        if v not in S13_VARIANTS:
            continue
        grp = (v, r.get("pin", 0), r["waits"])
        tot[grp] += 1
        fr = r.get("frames") or []
        if not fr:
            noent[grp] += 1
            continue
        f = fr[0]
        lab = s13_boundary(f["ip"], v)
        if lab is None:
            unmapped[grp] += 1
            continue
        d = None if f.get("pop_t1") is None else f["ann_t1"] - f["pop_t1"]
        tab[grp][lab].append(d)
    return tab, noent, tot, unmapped


def s13_report(recs=None, wait=0):
    """SITTING 13 -- IS THE FLOOR TWO CLOCKS, OR ONE BOUNDARY?

    Pre-registration: `docs/notes/sm3_s13_prereg_2026-08-05.md` §4."""
    if recs is None:
        recs = json.loads((OUT / "cells.json").read_text())
    tab, noent, tot, unmapped = s13_rows(recs)
    print("\n  --- SM3 sitting 13: the boundary chosen, by PAD CLOCK LENGTH ---")
    print("  (PRE-REGISTERED, sm3_s13_prereg_2026-08-05.md §4."
          "  `pad*` = IE RISES at the POPF;  `hot*` = the SAME geometry, NO"
          " rise.)")
    print(f"\n  {'variant':<9}{'pin':>4}{'w':>3} {'n':>4} {'noENT':>6} {'?':>3}"
          f"   boundary histogram of the FIRST entry"
          f"   [min(ann-pop) in clocks]")
    for k in sorted(set(tab) | set(noent), key=lambda x: (x[0], x[1], x[2])):
        h = tab[k]
        cells = "  ".join(
            f"{lab}:{len(v)}"
            + ("" if not [x for x in v if x is not None]
               else f"[{min(x for x in v if x is not None)}]")
            for lab, v in sorted(h.items()))
        print(f"  {k[0]:<9}{k[1]:>4}{k[2]:>3} {tot[k]:>4} {noent[k]:>6} "
              f"{unmapped[k]:>3}   {cells}")

    # the PAD's clock length, measured on the NO-RISE control at this wait
    print(f"\n  --- the pad instruction's CLOCK length, measured on the "
          f"NO-RISE control (`hot*`, pin 0, w{wait}) ---")
    print("      L_pad := min(ann-pop | B1) - min(ann-pop | OWN), both on the"
          " control")
    lpad = {}
    for pad in S13_PADS:
        k = (f"hot{pad}", 0, wait)
        h = tab.get(k, {})

        def mn(lab):
            v = [x for x in h.get(lab, []) if x is not None]
            return min(v) if v else None
        own, b1 = mn("OWN"), mn("B1")
        lpad[pad] = None if (own is None or b1 is None) else b1 - own
        print(f"      {pad:<5} {S13_PADS[pad][1]:<44} OWN={own} B1={b1}  "
              f"L_pad={lpad[pad]}")

    print(f"\n  --- THE VERDICT COORDINATES (pin 0, w{wait}) ---")
    print("      P2  a floor exists            : OWN = 0 and DEAD = 0 on every"
          " `pad*`")
    print("      P3  THE DISCRIMINATOR         : is B1 TAKEN when L_pad >> 2?")
    print("            B1 >= 1  -> a CLOCK test (the landed rendering)")
    print("            B1  = 0  -> BOUNDARY QUANTISATION")
    for pad in S13_PADS:
        k = (f"pad{pad}", 0, wait)
        h = tab.get(k, {})
        n = {lab: len(h.get(lab, [])) for lab in
             ("DEAD", "OWN", "B1", "B2", "B3")}
        print(f"      pad{pad:<5} L_pad={str(lpad[pad]):<5} "
              f"DEAD={n['DEAD']:<3} OWN={n['OWN']:<3} B1={n['B1']:<3} "
              f"B2={n['B2']:<3} B3={n['B3']:<3} noENTRY={noent[k]}")
    print(f"\n      P4  the NMI control (pin 1): OWN must be AVAILABLE")
    for pad in S13_PADS:
        k = (f"pad{pad}", 1, wait)
        h = tab.get(k, {})
        print(f"      pad{pad:<5} " + "  ".join(
            f"{lab}:{len(h.get(lab, []))}" for lab in
            ("DEAD", "OWN", "B1", "B2", "B3")) + f"  noENTRY={noent[k]}")
    return 0


def s13_engine(args):
    """P5 -- the SAME question put to an engine, scored cell for cell.

    A divergence here is a REGISTERED FAILURE to report, not to patch: the
    landed rendering is `int_p[2] && ie_p[2] && psw[FIE]`, and whether that
    reproduces silicon on a geometry it was never fitted to is exactly what
    concern 4 asks."""
    recs = json.loads((OUT / "cells.json").read_text())
    imgs = {v: image_of(v) for v in sorted({r["variant"] for r in recs})}
    eng = []
    for r in recs:
        if r["variant"] not in S13_VARIANTS or r["waits"] != args.wait:
            continue
        image, meta = imgs[r["variant"]]
        evt = (meta["anchor_linear"] & 0xFFFFF, r["delay"], args.hold,
               r.get("pin", 0))
        rows = engine_rows(image, meta, [None] * r["nrows"], r["waits"], evt,
                           args.core)
        fr = entry_frames(rows) if rows else []
        eng.append({"variant": r["variant"], "pin": r.get("pin", 0),
                    "waits": r["waits"], "delay": r["delay"],
                    "frames": fr[:1], "nrows": len(rows or [])})
    print(f"\n  === engine `{args.core}` on the SAME images, w{args.wait} ===")
    s13_report(eng, wait=args.wait)
    # cell for cell against the chip
    chip = {(r["variant"], r.get("pin", 0), r["waits"], r["delay"]): r
            for r in recs}
    same = diff = 0
    bad = []
    for e in eng:
        c = chip[(e["variant"], e["pin"], e["waits"], e["delay"])]
        cl = (s13_boundary(c["frames"][0]["ip"], e["variant"])
              if c.get("frames") else "NOENTRY")
        el = (s13_boundary(e["frames"][0]["ip"], e["variant"])
              if e.get("frames") else "NOENTRY")
        if cl == el:
            same += 1
        else:
            diff += 1
            bad.append((e["variant"], e["pin"], e["delay"], cl, el))
    print(f"\n  CELL FOR CELL vs the chip, w{args.wait}: "
          f"AGREE {same}   DIFFER {diff}")
    for b in bad[:40]:
        print(f"    {b[0]} p{b[1]} d{b[2]}: chip {b[3]}  engine {b[4]}")
    (OUT / f"s13_engine_{args.core}_w{args.wait}.json").write_text(
        json.dumps({"core": args.core, "wait": args.wait, "agree": same,
                    "differ": diff, "bad": bad}, indent=1) + "\n")
    return 0


def cmd_idle(args):
    import v30run
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)
    print("  board_idle: a single-NOP image captured on the socket -- OK")
    return 0


# --------------------------------------------------------------------------- #
# the ENGINE legs on the SAME captures -- `timed_fuzz`'s own replay policy,
# imported rather than forked (regeneration is not needed: the image is built
# here deterministically and the sha is recorded in the manifest).
# --------------------------------------------------------------------------- #
def engine_rows(image, meta, chip_rows, waits, evt, core):
    import tempfile
    import timed_fuzz as tf
    import ucsim_fuzz as uf
    entry = {"waits": {"wrand": False, "fixed": waits},
             "evt": {"pin": evt[3], "delay": evt[1], "hold": evt[2],
                     "hold_bits": 12, "hold_applied": evt[2]}}
    win = len(chip_rows)
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            cstream = uf.chip_stream(chip_rows, win)
            fires = uf.entry_points(cstream, evt[3])
            frames = [uf.frame_of(cstream, i) for i in fires]
            keep = 0
            while keep < len(fires) and frames[keep][0] >= 0:
                keep += 1
            d = {"pin": evt[3], "addr": evt[0], "delay": evt[1],
                 "hold": evt[2], "pins": 0, "at": fires[:keep],
                 "cs": [f[0] for f in frames[:keep]],
                 "ip": [f[1] for f in frames[:keep]]}
            rows, err = tf.run_sim(image, entry, len(chip_rows), td, d)
        else:
            rows, err = tf.run_tb(image, entry, len(chip_rows), td, core, evt)
    return rows


def cmd_score(args):
    recs = json.loads((OUT / "cells.json").read_text())
    imgs = {}
    for r in recs:
        imgs.setdefault(r["variant"], None)
    imgs = {v: image_of(v) for v in imgs}
    agree = Counter()
    tab = defaultdict(Counter)
    for r in recs:
        if not r["geom"]:
            continue
        rows = json.load(gzip.open(
            OUT / f"{r['key'].replace(':', '_')}.rows.json.gz", "rt"))
        image, meta = imgs[r["variant"]]
        evt = (meta["anchor_linear"] & 0xFFFFF, r["delay"], args.hold, 0)
        erows = engine_rows(image, meta, rows, r["waits"], evt, args.core)
        for k, cg in enumerate(r.get("acks") or [r["geom"]]):
            g = measure(erows, k) if erows else None
            same = bool(g and g["ack_t1"] == cg["ack_t1"] and
                        g["gap"] == cg["gap"])
            grp = (r["variant"], r["waits"], "ord1" if k == 0 else "ord2+")
            agree[(grp, same)] += 1
            tab[grp][(cg["prev_len"], cg["gap"], None if not g else g["prev_len"],
                      None if not g else g["gap"])] += 1
    print(f"\n  --- engine `{args.core}` vs the directed captures ---")
    tot_ok = tot_n = 0
    for k in sorted(tab, key=lambda x: (x[2], x[0], x[1])):
        ok = agree[(k, True)]
        n = ok + agree[(k, False)]
        tot_ok += ok
        tot_n += n
        print(f"  {k[2]:<5} {k[0]:<8} w{k[1]}  agree {ok}/{n}   " +
              "  ".join(f"chip L{a}/gap{b} | eng L{c}/gap{d}: {m}"
                        for (a, b, c, d), m in sorted(tab[k].items(),
                                                      key=lambda x: -x[1])))
    print(f"  TOTAL ack-clock agreement: {tot_ok}/{tot_n}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--waits", default="0,1,2,3")
    p.add_argument("--variants", default=",".join(VARIANTS))
    p.add_argument("--delays", type=int, default=24)
    p.add_argument("--d0", type=int, default=12)
    p.add_argument("--hold", type=int, default=6)
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--prereg", default="72fdaca572")
    p.add_argument("--pins", default="0")
    p.add_argument("--out", default="")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out", default="")
    p.set_defaults(fn=lambda a: (report(), 0)[1])
    p = sub.add_parser("score")
    p.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"))
    p.add_argument("--hold", type=int, default=16)
    p.add_argument("--out", default="")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("h1a")
    p.add_argument("--out", default="sm3-h1acell")
    p.set_defaults(fn=lambda a: h1a_report())
    p = sub.add_parser("s11")
    p.add_argument("--out", default="sm3-s11cell")
    p.set_defaults(fn=lambda a: s11_report())
    p = sub.add_parser("s13")
    p.add_argument("--out", default="sm3-s13cell")
    p.add_argument("--wait", type=int, default=0)
    p.set_defaults(fn=lambda a: s13_report(wait=a.wait))
    p = sub.add_parser("s13-engine")
    p.add_argument("--out", default="sm3-s13cell")
    p.add_argument("--core", default="ucore", choices=("sim", "ucore", "fsm"))
    p.add_argument("--wait", type=int, default=0)
    p.add_argument("--hold", type=int, default=300)
    p.set_defaults(fn=s13_engine)
    p = sub.add_parser("idle")
    p.add_argument("--out", default="")
    p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    if getattr(a, "out", ""):
        set_out(a.out)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
