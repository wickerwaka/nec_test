#!/usr/bin/env python3
"""tf0f_cell -- THE DIRECTED BOARD CELL on the TF trap boundary of a TWO-BYTE
(`0F`-escaped) and of a PREFIXED opcode.

WHY IT EXISTS.  Two bookings ask for exactly this population and neither has it:

  1. `docs/notes/fz2_a3d1d2_diagnosis_2026-08-11.md` §6.6.  The A3/D1/D2 block's
     ONLY lead is the TF trap boundary after an `0F`-extended instruction: on
     `fz2c/404041`, `fz2e/501066` and `fz2e/513019` the core issues one or two
     further CODE prefetches before entering vector 1 and the chip does not, so
     the two legs push DIFFERENT return addresses.  Verdict, verbatim: *"The
     derivable population is THREE seats ... A clean book beats a fitted land.
     Booked."*  Re-open condition, verbatim: *"A directed TF x `0F` capture ...
     a directed population that crosses TF with the whitelisted `0F` band ... at
     both `mod = 3` and `mod != 3` would give a two-digit denominator and a real
     split."*
  2. `ucore_provenance.md` §86 registers the arm's sampling boundary as ONE
     predicate -- **the `QS = 1` opcode pop** -- on the reasoning that *"a prefix
     retires with its own F pop, and so does the `0F` escape's first byte"*.
     That sentence has never been measured against silicon on a two-byte opcode
     or on a prefix stack: §86.C's cell walks a ONE-BYTE pad.  This is `C1`'s
     registered directed-cell debt.

WHAT IT MEASURES, IN ONE SENTENCE.  With `PSW.TF` raised by the program itself
(`push 0x100 ; popf`, the seats' own setter) and ONE probe instruction `P`
placed immediately after it, it reads off the pins WHICH INSTRUCTION BOUNDARY
the part chose -- as the RETURN ADDRESS the vector-1 entry pushes -- for a probe
family that separates every candidate reading of "the boundary".

THE OBSERVABLE IS ENGINE-FREE AND IT IS ONE SMALL INTEGER.  A vector-1 entry is
announced by a `MEMR` at linear `0x00004` (and `0x00006`); the three descending
`MEMW`s that follow are PSW, PS, **PC**, in hardware push order, and the third
is the boundary the part chose.  The body is PERIODIC with period `BLOCK`, every
instruction start inside a block is known by construction, and so

    pushed_off = pushed_PC - block_base

names that boundary exactly, in bytes, identically in every block.  Nothing in
this reader decodes an opcode, runs an engine or consults a golden.

THE PROGRAM.  `R` identical blocks of `BLOCK` bytes:

    68 00 01     push 0x100      <- 0x100 IS PSW.TF; `testimage.normalize_psw`
    9D           popf               forces TF CLEAR into every composed image,
    <P>          the probe           so the only way to a set TF is this pair
    90 90 ...    pad to BLOCK

Vector 1 points at a handler that CLEARS TF in the frame it is about to return
through, so each block produces EXACTLY ONE trap and one capture is `R`
independent repeats of the same measurement rather than a storm that only ever
measures its own first trap (`sm3_tf_floor_cell`'s trick, one vector over).

THE PROBE FAMILY IS THE DISCRIMINATOR.  Every probe is `mod = 3` or a
data-region EA, no probe is a BRKEM alias (`0F` + any byte >= 0x40 is the 8080
door -- `docs/facts/undocumented_0f.md`), and no probe is the parked
`0F 31`-with-memory-ModR/M form (`fz2_a3d1d2_diagnosis` §5):

    single-byte     nop clc incaw        the CONTROL band -- §86 walks these
    multi-byte      movi addrr           length without a second opcode byte
    prefixed        pfx1 pfx2 pfx3 pfx4  "a prefix retires with its own F pop"
    0F, mod=3       x13 x1b x18 x28 x33  the LEAD's own shape (`x1b` is
                                         `fz2e/501066`'s literal bytes)
    0F, mod!=3      y1e                  `fz2c/404041`'s shape, EA in the data
                                         carve-out
    prefix + 0F     z1b                  the two mechanisms crossed
    TF CLEAR        notf                 THE NULL: zero vector-1 entries

AXES.  `waits` 0-3 (which is also the queue-fullness axis: at w3 the prefetcher
never gets ahead) and `align` 0-3 (which moves every block's byte phase against
the word-aligned fetch, so the probe arrives with the queue in a different
state).  Both are declared before the run and neither is chosen after seeing a
result.

BOARD DISCIPLINE (CLAUDE.md), in code: single-writer asked of the board before
the first capture; SOCKET ONLY (`use_core=False`, passed explicitly, because the
board's CFG is sticky); NO FLASHING anywhere and the flash pin is recorded; the
divider PINNED and `div_guard`'s readback RECORDED at every stratum boundary;
the FULL per-clock capture words retained with a sha256 per cell; `board_idle()`
at the end; a run of consecutive transport errors STOPS the cell and is reported
as a rig finding, which outranks the measurement.  THIS CELL DRIVES NO PIN --
the trap is internal, so there is no `evt`, no hold, no `fired`, and none of
INV-1's directive-truncation exposure.

Usage:
    python3 sw/tf0f_cell.py calib                 # offline (tb_sys)
    python3 sw/tf0f_cell.py predict               # offline
    python3 sw/tf0f_cell.py core  [--strata ...]  # offline (tb_sys)
    python3 sw/tf0f_cell.py run   [--strata ...]  # BOARD, socket only
    python3 sw/tf0f_cell.py score
    python3 sw/tf0f_cell.py seats
    python3 sw/tf0f_cell.py idle
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

OUT = ROOT / "sw" / "testdata" / "tf0f"
CALIB = OUT / "calib.json"
PRED = OUT / "predictions.json"

# --------------------------------------------------------------------------- #
# the program
# --------------------------------------------------------------------------- #
BLOCK = 16               # bytes per block; word-aligned so every block has the
                         # SAME byte phase and `align` alone moves it
R = 6                    # blocks per image = independent repeats per capture
SETTER = bytes([0x68, 0x00, 0x01, 0x9D])      # push 0x100 ; popf   (TF <- 1)
CLEARER = bytes([0x68, 0x00, 0x00, 0x9D])     # push 0x000 ; popf   (the null)

# The vector-1 handler.  At entry SP points at the pushed PC, so [BP+4] is the
# pushed PSW; 0xF002 is the composed PSW with TF CLEAR.  `compose` appends IRET.
HANDLER = bytes([0x89, 0xE5,                       # MOV BP,SP
                 0xC7, 0x46, 0x04, 0x02, 0xF0])   # MOV word [BP+4],0xF002

# The probes' implicit-memory operands (INS/EXT/bit-string) are pointed INTO the
# data carve-out, which `testimage` fills with 0x90 and which no probe's result
# can move out of.  Applied to EVERY leg, control and probe alike, so the
# geometry is identical across the family.
REGS = {"IX": 0x0000, "IY": 0x0000, "DS0": 0x0200, "DS1": 0x0200}

PROBES = {
    # ---- CONTROL band: one-byte opcodes.  §86 says the registered predicate
    #      is right here, and the cell must say so on its own evidence.
    "nop":   (bytes([0x90]),                        "NOP -- 1 byte"),
    "clc":   (bytes([0xF8]),                        "CLC -- 1 byte, flag write"),
    "incaw": (bytes([0x40]),                        "INC AW -- 1 byte"),
    # ---- length without a second OPCODE byte
    "movi":  (bytes([0xB8, 0x34, 0x12]),            "MOV AW,0x1234 -- 3 bytes, "
                                                    "one opcode byte"),
    "addrr": (bytes([0x01, 0xD8]),                  "ADD AW,BW -- opcode+ModR/M "
                                                    "mod=3"),
    # ---- the prefix ladder: 1, 2, 3, 4 prefixes on the SAME 2-byte op
    "pfx1":  (bytes([0x2E, 0x01, 0xD8]),            "CS: ADD AW,BW"),
    "pfx2":  (bytes([0x2E, 0x3E, 0x01, 0xD8]),      "CS: DS: ADD AW,BW"),
    "pfx3":  (bytes([0x2E, 0x3E, 0x26, 0x01, 0xD8]), "3 prefixes + ADD AW,BW"),
    "pfx4":  (bytes([0x2E, 0x3E, 0x26, 0x36, 0x01, 0xD8]),
                                                    "4 prefixes + ADD AW,BW"),
    # ---- the LEAD: 0F-escaped, mod = 3
    "x13":   (bytes([0x0F, 0x13, 0xC0]),            "0F 13 -- bitop rm,CL, "
                                                    "mod=3, 3 bytes"),
    "x1b":   (bytes([0x0F, 0x1B, 0xE8, 0x4F]),      "0F 1B E8 4F -- fz2e/501066's "
                                                    "LITERAL probe bytes"),
    "x18":   (bytes([0x0F, 0x18, 0xC0, 0x05]),      "0F 18 -- bitop rm,imm, mod=3"),
    "x28":   (bytes([0x0F, 0x28, 0xC0]),            "0F 28 -- ROL4, mod=3, 3 bytes"),
    "x33":   (bytes([0x0F, 0x33, 0xC3]),            "0F 33 -- EXT reg,reg, mod=3"),
    # ---- the LEAD, mod != 3: fz2c/404041's shape.  ModR/M 0x06 is the
    #      direct-disp16 form; DS0 = 0 puts the EA at linear 0x2000, inside the
    #      data carve-out.
    "y1e":   (bytes([0x0F, 0x1E, 0x06, 0x00, 0x20, 0x05]),
                                                    "0F 1E -- bitop [0x2000],imm, "
                                                    "mod=0 direct"),
    # ---- the two mechanisms crossed
    "z1b":   (bytes([0x2E, 0x0F, 0x1B, 0xE8, 0x4F]), "CS: 0F 1B E8 4F"),
    # ---- THE NULL: identical geometry, TF never set
    "notf":  (bytes([0x0F, 0x1B, 0xE8, 0x4F]),      "the NULL: `push 0x000` in "
                                                    "place of `push 0x100`, "
                                                    "same probe, same geometry"),
}

# --------------------------------------------------------------------------- #
# THE DISJOINT VALIDATION POPULATION.
#
# The standing rule: *"A refuted key's REPLACEMENT must be validated on data
# that was not used to select it."*  The measured law `KM` (below) was selected
# on the 16 legs above; every leg here is a byte sequence that appears NOWHERE
# in that set, and its per-leg prediction is registered in
# `docs/notes/tf0f_cell_erratum_2026-08-11.md` BEFORE it is captured.
# --------------------------------------------------------------------------- #
VPROBES = {
    # prefix stack AND `0F` escape, at depths the derivation set never reached
    "v_p2x":  (bytes([0x2E, 0x3E, 0x0F, 0x1B, 0xE8, 0x4F]),
               "2 prefixes + 0F 1B, mod=3"),
    "v_p4x":  (bytes([0x2E, 0x3E, 0x26, 0x36, 0x0F, 0x1B, 0xE8, 0x4F]),
               "4 prefixes + 0F 1B, mod=3 -- the deepest decoration"),
    # a prefix on a NON-escaped multi-byte op
    "v_pfxi": (bytes([0x2E, 0xB8, 0x34, 0x12]),     "CS: MOV AW,0x1234"),
    # prefixes that are NOT segment overrides
    "v_rep":  (bytes([0xF3, 0x01, 0xD8]),           "REP prefix + ADD AW,BW"),
    "v_lock": (bytes([0xF0, 0x01, 0xD8]),           "LOCK prefix + ADD AW,BW"),
    # `0F` forms the derivation set never used
    "v_x39":  (bytes([0x0F, 0x39, 0xC0, 0x04]),     "0F 39 -- INS reg,imm4, mod=3"),
    "v_x1f":  (bytes([0x0F, 0x1F, 0xC0, 0x03]),     "0F 1F -- bitop rm,imm, mod=3"),
    "v_x10":  (bytes([0x0F, 0x10, 0xC0]),           "0F 10 -- bitop rm,CL, mod=3"),
    "v_x2a":  (bytes([0x0F, 0x2A, 0xC0]),           "0F 2A -- ROR4, mod=3"),
    "v_y13":  (bytes([0x0F, 0x13, 0x06, 0x00, 0x00]),
               "0F 13 -- bitop [DS0:0], CL, mod=0 direct (EA = linear 0x2000)"),
    # UNDECORATED legs of new lengths -- the other side of the predicate
    "v_add":  (bytes([0x81, 0xC0, 0x34, 0x12]),     "ADD AW,0x1234 -- 4 bytes, "
                                                    "opcode IS the first byte"),
    "v_movm": (bytes([0xA1, 0x00, 0x00]),           "MOV AW,[DS0:0] -- 3 bytes"),
    "v_push": (bytes([0x50]),                       "PUSH AW -- 1 byte"),
    "v_xchg": (bytes([0x93]),                       "XCHG AW,BW -- 1 byte"),
    # and the NULL again, on a validation-set probe
    "v_notf": (bytes([0x2E, 0x0F, 0x1B, 0xE8, 0x4F]),
               "the NULL, validation set: `push 0x000`, decorated probe"),
}
PROBES.update(VPROBES)

CONTROL_LEGS = ("notf", "v_notf")
DERIVATION = [k for k in PROBES if k not in VPROBES]
VALIDATION = list(VPROBES)
PROBE_ORDER = DERIVATION + VALIDATION

WAITS = (0, 1, 2, 3)
ALIGNS = (0, 1, 2, 3)

IVT1_OFF = 0x00004       # vector 1, offset half
IVT1_SEG = 0x00006
BS_INTA, BS_IOR, BS_IOW, BS_HALT, BS_CODE, BS_MEMR, BS_MEMW, BS_PASV = range(8)


def body_of(probe, align):
    """The composed body: `align` NOPs, then R identical blocks."""
    p, _ = PROBES[probe]
    setter = CLEARER if probe in CONTROL_LEGS else SETTER
    blk = setter + p
    if len(blk) > BLOCK - 2:
        raise ValueError(f"probe {probe} leaves < 2 pad bytes in the block")
    blk = blk + bytes([0x90]) * (BLOCK - len(blk))
    return bytes([0x90]) * align + blk * R


def image_of(probe, align):
    """The composed 64 KB image.  Deterministic -- no rng anywhere in this
    cell, which is what makes it DIRECTED and not a fuzz."""
    img, meta = ti.compose(regs=REGS, instr=body_of(probe, align),
                           ivt={1: (0x0000, ti.IHT_AT)}, handlers=[HANDLER])
    return bytes(img), meta


def image_sha(probe, align):
    return hashlib.sha256(image_of(probe, align)[0]).hexdigest()


def block_base(meta, align, k):
    """PC of block k, in the code segment's own offset units."""
    return (meta["regs_in"]["PC"] + align + k * BLOCK) & 0xFFFF


def probe_off():
    """Offset of the probe's first byte inside its block."""
    return len(SETTER)


def stratum_key(probe, waits):
    return f"{probe}_w{waits}"


def cell_key(probe, waits, align):
    return f"{probe}_w{waits}_a{align}"


# --------------------------------------------------------------------------- #
# row reading -- pins only, no engine
# --------------------------------------------------------------------------- #
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
    """[(row, bs, addr, data)] -- one entry per bus cycle, data taken from the
    T3/TW sample exactly as `analyze_capture.analyze_large` does."""
    out = []
    for i, r in enumerate(rows):
        if r["t"] == 1:
            out.append([i, r["bs_early"], r["ad_addr"], None])
        elif r["t"] in (3, 4) and out:
            out[-1][3] = r["ad_data"]
    return out


def features(rows, probe, align, meta):
    """Every measured quantity this cell reports, off the pins.

    `ok` is False when the cell is STRUCTURALLY INVALID -- the anchor T1 is not
    in the window, or the number of vector-1 entries is not `R` (for a TF leg)
    or not 0 (for the null), or an entry's three pushes are not in the window.
    Those cells are RETAINED and REPORTED, never silently dropped."""
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
            e = {"txn": k, "row": i, "code_before": n_code,
                 "last_code": (code_seen[-1][1] if code_seen else None),
                 "pushed_psw": ws[0][3] if len(ws) > 0 else None,
                 "pushed_ps": ws[1][3] if len(ws) > 1 else None,
                 "pushed_pc": ws[2][3] if len(ws) > 2 else None}
            entries.append(e)
    f["n_entries"] = len(entries)
    f["n_code_total"] = n_code
    f["term_done"] = any(b == BS_IOW and (ad & 0xFF) == 0xFC
                         for _i, b, ad, _d in tx[a:])

    want = 0 if probe in CONTROL_LEGS else R
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
        # the prefetch high-water mark, relative to the same block base.  The
        # capture's CODE addresses are LINEAR; the base is a PC, so the code
        # segment's own linear origin has to come off.
        lin_base = (meta["anchor_linear"] - pc0 + base) & 0xFFFFF
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
# the grid
# --------------------------------------------------------------------------- #
def grid(strata=None):
    """[(probe, waits, align)] -- the whole declared grid, in run order."""
    sel = strata or DERIVATION
    cells = []
    for p in sel:
        for w in WAITS:
            for al in ALIGNS:
                cells.append((p, w, al))
    return cells


def ncap_for(waits, cal=None):
    if cal:
        v = cal.get("ncap", {}).get(str(waits))
        if v:
            return v
    return 1500 + 500 * waits


# --------------------------------------------------------------------------- #
# calibration -- offline, on tb_sys, and it sets INSTRUMENT settings ONLY
# --------------------------------------------------------------------------- #
def _tbsys():
    import fz2_tbsys
    return fz2_tbsys


def cmd_calib(a):
    """Measure the capture depth each wait level needs, on the worst-case
    (longest) probe.

    THIS IS AN INSTRUMENT SETTING, NOT A RESULT.  It decides how deep the
    capture goes, never what it is scored against: every reported quantity in
    `core`/`run`/`score` is recomputed from the capture's OWN transactions, so a
    calibration that is generous costs time and biases nothing.  It is taken on
    an engine because capture depth is program geometry and because taking it on
    the board would be board contact before the pre-registration."""
    tbs = _tbsys()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_calib.hex"
    cal = {"tool": "tf0f_cell calib", "leg": "tb_sys ret",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "instrument setting only; every scored quantity is measured "
                   "from the capture's own transactions",
           "block": BLOCK, "R": R, "ncap": {}, "worst": {}}
    worst = max(PROBES, key=lambda p: len(PROBES[p][0]))
    print(f"  worst-case probe: {worst} ({len(PROBES[worst][0])} bytes)")
    img, meta = image_of(worst, max(ALIGNS))
    for w in WAITS:
        tmp.unlink(missing_ok=True)     # tb_sys does NOT truncate its cap file
        r = tbs.run_tb("ret", img, tmp, ncap=4090, waits=w, quiet=True)
        rows = _rows_from_words(r["words"])
        f = features(rows, worst, max(ALIGNS), meta)
        last = f["entries"][-1]["row"] if f.get("entries") else None
        need = int(last + 200) if last else None
        cal["worst"][str(w)] = {"entries": f.get("n_entries"),
                                "last_entry_row": last, "ok": f["ok"],
                                "why": f["why"]}
        cal["ncap"][str(w)] = min(4090, max(need or 0, 1500 + 500 * w))
        print(f"  w{w}: entries={f.get('n_entries')} last_entry_row={last} "
              f"-> ncap {cal['ncap'][str(w)]}")
    tmp.unlink(missing_ok=True)
    CALIB.write_text(json.dumps(cal, indent=1))
    print(f"  -> {CALIB}")
    return 0


def _cal():
    return json.loads(CALIB.read_text()) if CALIB.exists() else {}


# --------------------------------------------------------------------------- #
# the sweep driver, shared by the board leg and the tb_sys leg
# --------------------------------------------------------------------------- #
def _sweep(cal, cells, capture_fn, outdir, reps_every=0, reps=3, progress=25):
    """capture_fn(image, waits, ncap) -> (words, extra)."""
    outdir.mkdir(parents=True, exist_ok=True)
    table, unstable = [], []
    t0 = time.time()
    n = 0
    shards = defaultdict(dict)
    for probe, w, al in cells:
        img, meta = image_of(probe, al)
        ncap = ncap_for(w, cal)
        words, extra = capture_fn(img, w, ncap)
        rows = _rows_from_words(words)
        f = features(rows, probe, al, meta)
        sha = hashlib.sha256(
            ("\n".join(f"{x:016x}" for x in words) + "\n").encode()).hexdigest()
        ck = cell_key(probe, w, al)
        row = {"cell": ck, "probe": probe, "waits": w, "align": al,
               "ncap": ncap, "sha256": sha, "n_words": len(words),
               "image_sha256": image_sha(probe, al),
               "probe_bytes": PROBES[probe][0].hex(),
               "probe_len": len(PROBES[probe][0])}
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
                offs.append(tuple(features(_rows_from_words(w2), probe, al,
                                           meta).get("pushed_off") or ()))
            row["rep_shas"] = shas
            row["rep_offs"] = [list(o) for o in offs]
            row["stable"] = len(set(shas)) == 1
            row["take_stable"] = len(set(offs)) == 1
            if not row["take_stable"]:
                unstable.append(ck)
        table.append(row)
        shards[stratum_key(probe, w)][ck] = [f"{x:016x}" for x in words]
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
                    key=lambda r: (PROBE_ORDER.index(r["probe"]),
                                   r["waits"], r["align"]))
    if kept:
        print(f"  merged with {kept} previously measured cells -> {len(merged)}")
    return merged


def _select(arg):
    if not arg:
        return DERIVATION
    want = [x for x in arg.split(",") if x]
    bad = [x for x in want if x not in PROBES]
    if bad:
        raise SystemExit(f"unknown probe(s): {bad}")
    return want


def _sha_dir(dd):
    lines = []
    for p in sorted(dd.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  "
                         f"{p.relative_to(dd)}")
    (dd / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


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

    This is the core leg of the comparison and it is NOT the reference: the
    correctness target is silicon (CLAUDE.md, 2026-08-04).  It exists so the
    measured silicon boundary can be put beside the engine's, cell for cell, on
    the identical stimulus."""
    tbs = _tbsys()
    cal = _cal()
    d = OUT / "core"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "_run.hex"

    def cap(img, w, ncap):
        tmp.unlink(missing_ok=True)      # tb_sys does not truncate its cap file
        r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w, quiet=True)
        return r["words"], {}

    cells = grid(_select(a.strata))
    table, unstable, secs = _sweep(cal, cells, cap, d)
    tmp.unlink(missing_ok=True)
    table = _merge(d, table)
    man = {"tool": "tf0f_cell core", "leg": "tb_sys ret",
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
        "tf0f_cell refuses to run: truth source is not the socket"
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
    man = {"tool": "tf0f_cell run", "host": HOST, "use_core": False, "div": DIV,
           "spec": "docs/notes/tf0f_cell_prereg_2026-08-11.md",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "flash": _flash_pin(), "block": BLOCK, "R": R,
           "images": {f"{p}_a{al}": image_sha(p, al)
                      for p in PROBE_ORDER for al in ALIGNS},
           "div_guards": []}
    print("== single-writer / reachability")
    man["preflight"] = single_writer(HOST)
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
                    img, HOST, tag="tf0f", waits=w, use_core=False, div=DIV,
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
    for probe in _select(a.strata):
        man["div_guards"].append((probe, div_guard(probe)))
        t, u, sec = _sweep(cal, grid([probe]), cap, d,
                           reps_every=a.reps_every, reps=a.reps)
        table += t
        unstable += u
        secs += sec
        out = _merge(d, table)
        man.update(cells=len(out), seconds=round(secs, 1),
                   transport_errors=errs["n"], unstable=unstable)
        (d / "manifest.json").write_text(json.dumps(man, indent=1))
        (d / "table.json").write_text(json.dumps(out, indent=1))
        print(f"  {probe}: {len(t)} cells  ({secs:.0f}s cumulative)", flush=True)
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
# the PRE-REGISTERED hypothesis table
# --------------------------------------------------------------------------- #
# THE ARITHMETIC, once, so every prediction below is checkable by hand.
#
# Write `Ij` for the j-th instruction after the setter's `popf` (`I0` = popf,
# `I1` = the probe's first boundary-bearing unit) and `Bj` for its retire
# boundary.  `ucore_provenance.md` §84.3 / §86 land:
#
#     the arm SAMPLES `TF` at a boundary and TAKES at the NEXT one,
#
# and §86.B measures the floor as 4 clocks from the rise, which `B0` (1-2 clocks
# after `popf`'s flag write) never clears.  So `B1` is the first sampling
# boundary, the trap is taken at `B2`, and
#
#     pushed_PC = start of I3.
#
# The WHOLE question this cell asks is WHAT COUNTS AS A BOUNDARY UNIT, and the
# probe family is chosen so that the candidate answers give DIFFERENT
# `pushed_off`.  The candidates are NOT a hand-picked list: they are the FULL
# 3 x 2 product of the only two degrees of freedom the question has --
#
#     P (what a PREFIX STACK contributes)   none | stack (one, any depth) | byte
#     E (what the `0F` ESCAPE byte does)    no unit | its own unit
#
# -- so no rule can be added after the fact without changing the product, and
# there is no per-opcode special case anywhere in the table.  Named:
#
#     K1 = (none,  no)   ONE unit per ARCHITECTURAL instruction
#     K7 = (none,  yes)
#     K3 = (stack, no)
#     K5 = (stack, yes)
#     K4 = (byte,  no)
#     K2 = (byte,  yes)  = §86's PROSE read literally ("a prefix retires with
#                          its own F pop, and so does the `0F` escape's first
#                          byte")
#
# `pushed_off` is measured from the block base; the setter is 4 bytes, so `I1`
# starts at offset 4 and every pad NOP is its own one-byte unit.
PREFIX_BYTES = (0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3)

#
# Two further rules are carried BESIDE the lattice and are labelled as what
# they are -- rules DERIVED FROM A MEASURED COLUMN, not registered before it:
#
#   KM  the MEASURED SILICON LAW.  An instruction contributes ONE boundary
#       unit, plus ONE MORE iff its OPCODE BYTE IS NOT ITS FIRST BYTE -- i.e.
#       iff it carries a prefix stack and/or an `0F` escape.  The extra unit is
#       ONE however deep the decoration is and however many KINDS of decoration
#       are present, which is what separates it from every additive member of
#       the lattice.  DERIVED on the 16 `DERIVATION` legs; VALIDATED on the 15
#       disjoint `VALIDATION` legs, whose per-leg predictions are registered in
#       `tf0f_cell_erratum_2026-08-11.md` before capture.
#   KC  the same predicate with the `0F` escape REMOVED -- i.e. the ucore's own
#       measured behaviour, carried so the two engines can be scored on one
#       scale.
#
# ⚠ `pushed_off` measures the COUNT of units a probe contributes (1 vs 2), not
# WHERE the second one sits: at a count of 2 the third unit is the first pad
# byte whatever the second unit's position.  "The second boundary is AT the
# opcode byte" is therefore an INTERPRETATION of `KM`, not a measurement, and
# it is flagged as such wherever it is written.
KINDS = {
    "K1": ("none", "no"),
    "K7": ("none", "yes"),
    "K3": ("stack", "no"),
    "K5": ("stack", "yes"),
    "K4": ("byte", "no"),
    "K2": ("byte", "yes"),
}
DERIVED_KINDS = ("KM", "KC")
KIND_SAYS = {
    "K1": "ONE unit per architectural instruction: a prefix stack and its "
          "opcode are one unit, `0F xx` is one unit",
    "K7": "the prefix stack is not a unit, but the `0F` escape byte is",
    "K3": "the prefix STACK is one extra unit whatever its depth; the `0F` "
          "escape byte is NOT a unit",
    "K5": "the prefix STACK is one extra unit whatever its depth; the `0F` "
          "escape byte IS a unit -- the shape the A3/D1/D2 diagnosis predicts "
          "for silicon",
    "K4": "every prefix BYTE is its own unit; the `0F` escape byte is NOT",
    "K2": "§86's PROSE READ LITERALLY: every prefix byte is its own unit AND "
          "the `0F` escape byte is its own",
    "KM": "THE MEASURED SILICON LAW (derived, not pre-registered): one unit, "
          "plus ONE MORE iff the opcode byte is not the first byte -- once, "
          "however deep and however many kinds of decoration",
    "KC": "the ucore's own measured behaviour: KM with the `0F` escape not "
          "counting as decoration",
}


def _shape(probe):
    """(n_prefix_bytes, escaped) for a probe."""
    p, _ = PROBES[probe]
    n = 0
    while n < len(p) and p[n] in PREFIX_BYTES:
        n += 1
    return n, (n < len(p) and p[n] == 0x0F)


def _starts(probe, kind):
    """Unit-start offsets inside a block under boundary rule `kind`."""
    p, _ = PROBES[probe]
    o = len(SETTER)
    n_pfx, esc = _shape(probe)
    if kind in DERIVED_KINDS:
        dec = (n_pfx > 0) or (esc and kind == "KM")
        # the second unit is placed at the OPCODE byte; `st[2]` is insensitive
        # to that choice (see the note above), so the placement is a label, not
        # a claim
        st = [o] + ([o + n_pfx + (1 if esc else 0)] if dec else [])
        return sorted(set(st + list(range(o + len(p), BLOCK))))
    pmode, emode = KINDS[kind]
    if pmode == "none":
        st = [o]
    elif pmode == "stack":
        st = ([o] if n_pfx else []) + [o + n_pfx]
    else:                                   # "byte"
        st = [o + i for i in range(n_pfx)] + [o + n_pfx]
    if esc and emode == "yes":
        st.append(o + n_pfx + 1)
    # then the pad NOPs, one byte each, to the end of the block
    st += list(range(o + len(p), BLOCK))
    return sorted(set(st))


def predict_off(probe, kind):
    """`pushed_off` under boundary rule `kind`.

    §84.3 / §86: the arm SAMPLES `TF` at a boundary and TAKES at the NEXT one,
    and §86.B's floor of 4 clocks is never cleared by `B0` (`popf`'s own retire,
    1-2 clocks after its flag write).  So `B1` -- the retire of the FIRST unit
    after the setter -- is the first sampling boundary, the trap is taken at
    `B2`, and the pushed return address is the START OF THE THIRD UNIT.
    `_starts()[0]` is that first unit, so the answer is `_starts()[2]`."""
    st = _starts(probe, kind)
    return st[2] if len(st) > 2 else None


def cmd_predict(a):
    OUT.mkdir(parents=True, exist_ok=True)
    p = {"tool": "tf0f_cell predict",
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "block": BLOCK, "R": R, "waits": list(WAITS), "aligns": list(ALIGNS),
         "setter": SETTER.hex(), "clearer": CLEARER.hex(),
         "handler": HANDLER.hex(), "regs": REGS,
         "kinds": {k: {"lattice": (k in KINDS),
                       "prefix": KINDS[k][0] if k in KINDS else None,
                       "escape": KINDS[k][1] if k in KINDS else None,
                       "says": v} for k, v in KIND_SAYS.items()},
         "derivation_legs": DERIVATION, "validation_legs": VALIDATION,
         "probes": {}, "images": {}, "cells": len(grid())}
    for k in PROBE_ORDER:
        b, what = PROBES[k]
        n_pfx, esc = _shape(k)
        p["probes"][k] = {
            "bytes": b.hex(), "len": len(b), "what": what,
            "n_prefix": n_pfx, "escaped": esc,
            "control": k in CONTROL_LEGS,
            "stage": ("validation" if k in VALIDATION else "derivation"),
            "pushed_off": {kd: predict_off(k, kd) for kd in KIND_SAYS},
        }
    for k in PROBE_ORDER:
        for al in ALIGNS:
            p["images"][f"{k}_a{al}"] = image_sha(k, al)
    # WHERE THE CELL DISCRIMINATES AND WHERE IT DOES NOT -- stated in the
    # artifact, so a probe that separates nothing cannot be quoted as if it did.
    disc = {}
    for k in PROBE_ORDER:
        vals = {kd: predict_off(k, kd) for kd in KINDS}
        disc[k] = {"distinct": sorted({v for v in vals.values()
                                       if v is not None}),
                   "separates": len({v for v in vals.values()}) > 1}
    p["discrimination"] = disc
    p["non_discriminating"] = [k for k, v in disc.items() if not v["separates"]]
    PRED.write_text(json.dumps(p, indent=1))
    print(json.dumps({k: v for k, v in p.items()
                      if k not in ("images",)}, indent=1))
    print(f"  -> {PRED}  ({p['cells']} cells)")
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
    ck = {r["cell"]: r for r in core}
    pred = json.loads(PRED.read_text()) if PRED.exists() else {"probes": {}}
    out = {"controls": {}, "boundary": {}, "kinds": {}, "diff": [],
           "columns": {}, "confirm": {}}

    print("== 0. THE NULL -- nothing below is quotable without it\n")
    for probe in CONTROL_LEGS:
        sel = [r for r in board if r["probe"] == probe]
        ent = sorted({r.get("n_entries") for r in sel})
        bad = [r["cell"] for r in sel if r.get("n_entries")]
        out["controls"][probe] = {"cells": len(sel), "entry_counts": ent,
                                  "nonzero": bad}
        print(f"  {probe}: {len(sel)} cells, vector-1 entries {ent} "
              f"-- {'PASS' if not bad else 'FAIL ' + str(bad)}")

    print("\n== 1. THE MEASURED BOUNDARY, per probe: pushed_off\n")
    print(f"  {'stg':4s} {'probe':7s} {'bytes':16s} | {'chip':7s} | "
          f"{'core':7s} | " + " ".join(f"{k:>3s}" for k in KIND_SAYS))
    for probe in PROBE_ORDER:
        if probe in CONTROL_LEGS:
            continue
        sel = [r for r in board if r["probe"] == probe and r.get("ok")]
        if not sel:
            continue
        vals = Counter()
        for r in sel:
            vals.update(r["pushed_off"])
        cvals = Counter()
        for r in core:
            if r["probe"] == probe and r.get("ok"):
                cvals.update(r["pushed_off"])
        pr = pred["probes"].get(probe, {}).get("pushed_off", {})
        hit = [kd for kd in KIND_SAYS
               if pr.get(kd) is not None and len(vals) == 1
               and pr[kd] == next(iter(vals))]
        out["boundary"][probe] = {
            "chip": dict(vals), "core": dict(cvals), "pred": pr,
            "chip_unique": (len(vals) == 1),
            "chip_off": (next(iter(vals)) if len(vals) == 1 else None),
            "core_off": (next(iter(cvals)) if len(cvals) == 1 else None),
            "kinds_matched": hit, "n_cells": len(sel),
            "n_traps": sum(vals.values())}
        out["boundary"][probe]["stage"] = ("val" if probe in VALIDATION
                                           else "der")
        print(f"  {out['boundary'][probe]['stage']:4s} {probe:7s} "
              f"{PROBES[probe][0].hex():16s} | "
              f"{str(dict(vals)):7s} | {str(dict(cvals)):7s} | "
              + " ".join(f"{str(pr.get(kd)):>3s}" for kd in KIND_SAYS)
              + (f"   -> {','.join(hit)}" if hit else "   -> NONE"))

    print("\n== 2. WHICH BOUNDARY RULE SURVIVES -- the two populations SEPARATELY")
    for stage, legs in (("DERIVATION", DERIVATION), ("VALIDATION", VALIDATION)):
        pop = [p for p in legs if p in out["boundary"]]
        if not pop:
            continue
        print(f"\n  -- {stage} ({len(pop)} legs) --")
        for kd, txt in KIND_SAYS.items():
            agree, tot, miss = 0, 0, []
            for probe in pop:
                b = out["boundary"][probe]
                pv = b["pred"].get(kd)
                if pv is None:
                    continue
                tot += 1
                if b["chip_unique"] and b["chip_off"] == pv:
                    agree += 1
                else:
                    miss.append(probe)
            out["kinds"].setdefault(kd, {})[stage] = {
                "agree": agree, "of": tot, "misses": miss, "says": txt}
            print(f"    {kd}: {agree}/{tot} legs"
                  f"{'   misses: ' + ','.join(miss) if miss else '   <== ALL'}")
        # and the same for the CORE column, so the two engines are on one scale
        for kd in ("KM", "KC"):
            agree, tot, miss = 0, 0, []
            for probe in pop:
                b = out["boundary"][probe]
                pv = b["pred"].get(kd)
                if pv is None:
                    continue
                tot += 1
                if b["core_off"] is not None and b["core_off"] == pv:
                    agree += 1
                else:
                    miss.append(probe)
            out["kinds"].setdefault(kd, {})[stage + "_core"] = {
                "agree": agree, "of": tot, "misses": miss}
            print(f"    {kd} vs CORE: {agree}/{tot} legs"
                  f"{'   misses: ' + ','.join(miss) if miss else '   <== ALL'}")

    print("\n== 3. chip vs core, cell for cell")
    diff, tot = Counter(), Counter()
    for r in board:
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
                         "core": c.get("pushed_off"),
                         "chip_lastcode": r.get("lastcode_off_set"),
                         "core_lastcode": c.get("lastcode_off_set")})
    for k in COLS:
        out["columns"][k] = {"diff": diff[k], "compared": tot[k]}
        print(f"  {k:18s} {diff[k]:4d} / {tot[k]:4d}"
              f"{'   <== DIFFERS' if diff[k] else ''}")

    print("\n== 4. the prefetch high-water mark (lastcode_off), chip vs core")
    for probe in PROBE_ORDER:
        if probe in CONTROL_LEGS:
            continue
        bs, cs = Counter(), Counter()
        for r in board:
            if r["probe"] == probe and r.get("ok"):
                bs.update(x for x in r["lastcode_off"] if x is not None)
        for r in core:
            if r["probe"] == probe and r.get("ok"):
                cs.update(x for x in r["lastcode_off"] if x is not None)
        if bs or cs:
            print(f"  {probe:7s} chip {dict(bs)}   core {dict(cs)}")

    print("\n== 5. stability")
    rep = [r for r in board if "rep_shas" in r]
    tu = [r["cell"] for r in rep if not r.get("take_stable")]
    sd = [r["cell"] for r in rep if not r.get("stable")]
    out["confirm"] = {"repeated": len(rep), "of": len(board),
                      "take_unstable": tu, "stream_distinct": sd}
    print(f"  {len(rep)}/{len(board)} cells captured x3: "
          f"TAKE-unstable {len(tu)}, stream-distinct {len(sd)}")
    (OUT / "score.json").write_text(json.dumps(out, indent=1))
    print(f"\n  -> {OUT / 'score.json'}")
    return 0


# --------------------------------------------------------------------------- #
# the three booked seats, read against the measured law
# --------------------------------------------------------------------------- #
SEATS = {
    "fz2c/404041": "D2 -- push 0x100/popf then `0F 1E 57 a0 a2` (mod=1); "
                   "CODE-before-first-entry chip 85 / core 87 (CORE +2)",
    "fz2e/501066": "D2 -- push 0x100/popf then `0F 1B e8 4f` (mod=3); "
                   "CODE-before-first-entry chip 61 / core 62 (CORE +1)",
    "fz2e/513019": "C2 -- the third clean mover; chip 82 / core 84 (CORE +2)",
}


def cmd_seats(a):
    """Read the banked FABRIC captures for the three booked seats and report,
    per leg, the vector-1 entries and the CODE-fetch counts before them.

    ENGINE-FREE on the chip side: the banked capture carries BOTH legs as
    already-decoded rows (`real` = the CHIP, `sim` = the core) and this command
    READS the core column, it does not produce it.  It does NOT re-fit
    anything -- the boundary rule comes from `score`, on the directed cell."""
    led = ROOT / "sw" / "testdata" / "fz2" / \
        "fz2_failure_ledger_f17_2026-08-11.json"
    by = {}
    if led.exists():
        by = {f["seed"]: f for f in json.loads(led.read_text())["failures"]}
    outrows = []
    print("== the three booked seats, on their own banked FABRIC rows\n")
    for seed, why in SEATS.items():
        cap = _seat_capture(seed, by.get(seed))
        if cap is None:
            print(f"  {seed:14s} NO CAPTURE FOUND")
            outrows.append({"seed": seed, "why": why, "capture": None})
            continue
        r = _seat_features(cap)
        r.update(seed=seed, why=why, family=(by.get(seed) or {}).get("family"))
        outrows.append(r)
        print(f"  {seed:14s} entries chip {r['chip_n_entries']} / core "
              f"{r['core_n_entries']}   CODE-before-first chip "
              f"{r['chip_code_before']} / core {r['core_code_before']}  "
              f"(core {r['code_delta']:+d})")
        print(f"                 pushed PC chip {r['chip_pushed']} / core "
              f"{r['core_pushed']}")
        print(f"                 {why}")
    (OUT / "seats.json").write_text(json.dumps({"seats": outrows}, indent=1))
    print(f"\n  -> {OUT / 'seats.json'}")
    return 0


def _seat_capture(seed, rec):
    if rec and rec.get("capture"):
        p = ROOT / rec["capture"]
        if p.exists():
            return p
    cid, k = seed.split("/")
    for p in sorted((ROOT / "sw" / "testdata" / "campaigns" / cid /
                     "captures").glob(f"*_{k}_*.json.gz")):
        return p
    return None


def _seat_features(path):
    with gzip.open(path, "rt") as fh:
        cap = json.load(fh)
    out = {"capture": str(path.relative_to(ROOT))}
    for tag, key in (("chip", "real"), ("core", "sim")):
        rows = cap.get(key) or []
        tx = _txns(rows)
        n_code, ent, pushed = 0, [], []
        for k, (i, b, ad, _d) in enumerate(tx):
            if b == BS_CODE:
                n_code += 1
            if b == BS_MEMR and ad == IVT1_OFF:
                ws = [t for t in tx[k:k + 10] if t[1] == BS_MEMW][:3]
                ent.append(n_code)
                pushed.append(ws[2][3] if len(ws) > 2 else None)
        out[f"{tag}_n_entries"] = len(ent)
        out[f"{tag}_code_before"] = ent[0] if ent else None
        out[f"{tag}_entries_code"] = ent[:8]
        out[f"{tag}_pushed"] = [hex(x) if x is not None else None
                                for x in pushed[:8]]
    a, b = out["core_code_before"], out["chip_code_before"]
    out["code_delta"] = (a - b) if (a is not None and b is not None) else None
    return out


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
    p.add_argument("--strata", default="")
    p.set_defaults(fn=cmd_core)

    p = sub.add_parser("run")
    p.add_argument("--strata", default="")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--reps-every", type=int, default=8)
    p.add_argument("--force", action="store_true",
                   help="proceed past a failed single-writer check (recorded)")
    p.set_defaults(fn=cmd_run)

    sub.add_parser("score").set_defaults(fn=cmd_score)
    sub.add_parser("seats").set_defaults(fn=cmd_seats)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
