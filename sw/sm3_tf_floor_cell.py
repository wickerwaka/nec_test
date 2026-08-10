#!/usr/bin/env python3
"""sm3_tf_floor_cell -- THE DIRECTED BOARD CELL that MEASURES the BRK/TF arm's
floor, and the DISJOINT VALIDATION the §85 erratum owes §84's landed law.

Spec and PRE-REGISTERED per-candidate predictions:
`docs/notes/sm3_s24_prereg_2026-08-05.md`.  Read it before running this; the
predictions were committed BEFORE the first board contact of the sitting.

WHAT IT ASKS.  §84.3 landed

    THE ARM DOES NOT SEE A `TF` THAT ROSE TOO RECENTLY.  Sampled at the
    instruction's retire, a rise fewer than N clocks earlier is not there yet.

with N = 3 -- and it says in as many words that the selecting population bounds
N only to **[3, 6]**, because the only two opcodes that raise TF there are `9D`
(rise 1-2 clocks before its own retire) and `CF` (6-26), with NOTHING IN
BETWEEN.  §84.3's own falsifier is *"any instruction whose TF rise is 3, 4 or 5
clocks before the retire that must sample it"*.

THIS CELL MANUFACTURES EXACTLY THOSE CASES.  The rise is pinned by the setter
(`9D`, whose flag write is its `E` row) and the FIRST BOUNDARY AFTER IT is
walked in ACTUAL CLOCKS by changing ONE instruction -- the pad `I1` -- and by
the wait level, which stretches the same pad.  The engine's own retire trace
(`V30SIM_BRKTRACE`) reports the walk, and it covers **2, 3, 4, 5 clocks at w0
and 3, 4, 5, 6 at w3**: the whole undetermined interval, from both sides.

THE OBSERVABLE IS READ OFF THE PINS WITH NO ENGINE.  A vector-1 entry pushes
exactly three words with SP descending -- PSW, CS, **IP** -- announced by the
two IVT reads below `0x400`; no sled contains any other three-in-a-row
descending word write.  The third push is the RETURN ADDRESS, i.e. **the
boundary the part chose**, and every sled is periodic with every instruction
start known, so

    phase = (pushed_IP - PC0) mod period

names that boundary exactly.  This is `sm3_h1_cell`'s §72 reader, one vector
over.

THE ARITHMETIC, once, so the prediction table is checkable by hand.  Write `Bj`
for the retire boundary of the sled's instruction `Ij` (`I0` is the setter).
The law TAKES at a boundary when the arm stands and SAMPLES TF into the arm
afterwards, so if `Bj` is the FIRST boundary whose sample sees the rise then the
trap is taken at `B(j+1)` and the pushed IP is the start of `I(j+2)`.  `B0` is
1-2 clocks after the rise and never sees it under any floor >= 3, so the whole
question is `B1`:

    dist(rise -> B1) >= floor   ->  trap at B2, pushed IP = start of I3
    dist(rise -> B1) <  floor   ->  trap at B3, pushed IP = start of I4

and that is a ONE-BIT observable per (sled, wait) cell.

THE CONTROLS.  `*_notf` plants a PSW with TF CLEAR in the same geometry and must
produce **zero** vector-1 entries -- the null that says the entries are the trap
and not the rig.  `iret` is the OTHER branch of the same law with no floor
question at all (its rise is 6+ clocks before its own retire, so `B0` itself
samples and the trap lands ONE boundary earlier than `popf`'s); the two sleds
differ by the setter alone and are read on the same scale, which is the
asymmetry §84.1 wrote as an opcode rule and §84.3 re-read as one floor.
`storm` swaps the handler for a bare `IRET` that RESTORES TF, and measures the
cadence (§84's V-2 grace) on a directed population.

BOARD DISCIPLINE (CLAUDE.md).  Single-writer checked by the caller; SOCKET ONLY
(`use_core=False`, explicit, because the board's CFG is sticky); the divider
PINNED and `div_guard`'s readback RECORDED; the FULL per-clock rows retained
beside the raw 64-bit words and their sha256; `board_idle()` at the end; a run
of consecutive transport errors STOPS the cell.  **NO FLASHING**, and this cell
drives NO PIN AT ALL -- the trap is internal, so there is no `evt`, no hold, no
`fired`, and none of INV-1's directive-truncation exposure.

THE STIMULUS IS FROZEN, NOT GENERATED (fuzz-v2, 2026-08-10).  This cell used to
compose its 15 images at the v1 code anchor; fuzz-v2 moved the code region and
the compose now refuses.  Re-anchoring was NOT taken -- the 90 captures here are
SOCKET captures and a re-anchored image is a program the part never ran -- so
the images are stored beside the rows and checked on load against the `sha256`
in `predictions.json`, which was committed before the first board contact.
`image_of.__doc__` has the reasoning and the re-derivation recipe.  Nothing in
`gen_seq` / `testimage` / `check_seq` is touched by this cell any more.

Usage:
    python3 sw/sm3_tf_floor_cell.py predict [--floors 1,2,3,4,5,6,7]
    python3 sw/sm3_tf_floor_cell.py run [--waits 0,3] [--reps 3]
    python3 sw/sm3_tf_floor_cell.py score
    python3 sw/sm3_tf_floor_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                           # noqa: E402

simbin.ensure("sm3 s24 TF-floor cell")
import sm3_ackgeom as ag                                # noqa: E402

OUT = ROOT / "sw" / "testdata" / "sm3-s24tfcell"
IMAGES = OUT / "images"
ROM = ROOT / "docs" / "V20BITS.TXT"
MEMW = 6

# THE FROZEN v1 ANCHOR.  This cell's stimulus is a FROZEN ARTIFACT (see
# `image_of`), so its geometry constant is frozen WITH it and is deliberately
# NOT imported from `gen_seq` -- a later move of `gen_seq.PC0` must not silently
# re-interpret 90 captures that were taken at 0x0500.
PC0 = 0x0500

# --------------------------------------------------------------------------- #
# the images
# --------------------------------------------------------------------------- #
# The PSW words planted on the stack.  IE is CLEAR in both: no pin is driven and
# nothing may be recognised except the trap itself.
PSW_TF = 0xF102          # BRK/TF SET
PSW_NOTF = 0xF002        # ...and the control that says the geometry is innocent

# The TF handler.  It CLEARS TF in the frame it is about to return through, so
# each setter produces exactly ONE trap and the sled free-runs to the next
# setter -- which turns one capture into ~40 INDEPENDENT repeats of the same
# measurement instead of a storm that only measures its own first trap.
# At entry SP points at IP, so [BP+4] is the pushed PSW.
TF_HANDLER_AT = 0x0460
TF_HANDLER = [0x89, 0xE5,                     # MOV BP,SP
              0xC7, 0x46, 0x04, 0x02, 0xF0,   # MOV word ptr [BP+4],0xF002
              0xCF]                           # IRET

# pad = I1, the instruction whose CLOCK LENGTH walks dist(rise -> B1).
PADS = {
    "none": ([],             "no pad: I1 is the first NOP"),
    "clc":  ([0xF8],         "CLC -- the SHORTEST pad"),
    "inc":  ([0x41],         "INC CW"),
    "test": ([0x84, 0xC0],   "TEST AL,AL -- 2 bytes, same length as INC"),
    "xchg": ([0x93],         "XCHG AW,BW"),
    "add":  ([0x03, 0xC0],   "ADD AW,AW -- 2 bytes, same length as XCHG"),
    "movi": ([0xB0, 0x5A],   "MOV AL,imm8 -- the LONGEST short pad"),
    "pfx":  ([0x26],         "ES: PREFIX -- I1 is a PREFIX BOUNDARY"),
    "memr": ([0x8A, 0x07],   "MOV AL,[BW] -- a bus cycle, so the wait axis "
                             "stretches it hard"),
    "mul":  ([0xF6, 0xE3],   "MUL BL -- far above any floor: the SATURATED "
                             "control"),
}
POPF_VARIANTS = tuple(f"popf{k}" for k in PADS)
NOTF_VARIANTS = ("notfnone", "notfclc")
OTHER_VARIANTS = ("iret", "storm", "iretnotf")
VARIANTS = POPF_VARIANTS + NOTF_VARIANTS + OTHER_VARIANTS

TAIL = 5                 # NOPs after the pad: room for B1..B5 inside a period
NPERIOD = 70


def sled(variant):
    """(instruction byte-lists of ONE period, labels of the boundary AFTER
    each).  Every sled is periodic and every instruction start is known, which
    is what makes `phase` name a boundary."""
    if variant.startswith("popf") or variant.startswith("notf"):
        pad = PADS[variant[4:]][0]
        ins = [[0x9D]] + ([list(pad)] if pad else []) + [[0x90]] * TAIL
    elif variant in ("iret", "iretnotf"):
        # `CF` popping a PLANTED frame that points at the very next byte: the
        # SAME redirect shape as `sm3_h1_cell`'s `iretnext`, with a NOP run
        # behind it so the boundaries after it are one byte apart.
        ins = [[0xCF]] + [[0x90]] * TAIL
    elif variant == "storm":
        ins = [[0x9D]] + [[0x90]] * TAIL
    else:
        raise SystemExit(f"unknown variant {variant}")
    return ins, [f"B{i}" for i in range(len(ins))]


def starts_of(variant):
    ins, _ = sled(variant)
    starts, off = [], 0
    for b in ins:
        starts.append(off)
        off += len(b)
    return starts, off


def image_of(variant):
    """THE FROZEN STIMULUS -- the exact bytes the part was handed, loaded from
    disk and CHECKED against the pre-registered record.  -> (bytearray, meta).

    WHY THIS IS A LOAD AND NOT A COMPOSE (fuzz-v2 / the v1-anchor debt).  This
    cell used to BUILD its images: `Prog` at `gen_seq.PC0` (0x0500) through the
    v1 `testimage.compose`.  fuzz-v2 T1/T2 moved the code region to
    [0x8000,0xC000) and rewrote `compose` (the `stub_linear` store stub and the
    0x90 fill are gone; a 0xCC apron, an interrupt-handler table and a
    terminator are in), so on this branch the old call dies with

        ComposeError: body [0500,06a4) is not inside the code region [8000,c000)

    measured on this branch, after `W-0a` and `W-1` have already passed (they
    read the retained rows and need no image).

    `sw/retired_v1.py` and `gen_seq._v1_anchor_stop` record the DECISION not to
    paper that over by moving `PC0`, and the reason is exactly this cell's
    reason: **the 90 captures in this directory are SOCKET captures** -- taken
    on the part at `use_core=False` -- and a v2-anchored re-compose would score
    the engine on a program silicon has never run.  That would be a fabricated
    green.

    BUT RE-CAPTURE IS NOT THE ONLY HONEST ROUTE, AND IT IS NOT THE ONE TAKEN.
    The stimulus is not a thing this cell needs to *derive*; it is a thing it
    needs to *reproduce*.  These 15 images are frozen artifacts exactly as the
    rows beside them are, so they are stored beside them, and the tie back to
    silicon is a hash that was committed BEFORE the part ever ran them:
    `predictions.json` records a `sha256` per variant and was committed at
    `0fd3955f3a`, before the sitting's first board contact.  Every load is
    checked against it.  Nothing is re-anchored, `gen_seq` is not touched, and
    no board is needed.

    HOW THE FILES WERE PRODUCED, so a reviewer can re-derive them:

        git archive --format=tar -o /tmp/v1.tar 7e949925b7 sw docs
        # extract, then run the ORIGINAL image_of (unchanged at that commit --
        # `git diff 7e949925b7 6ae4966b83 -- sw/sm3_tf_floor_cell.py` is empty)
        # and gzip each `image_of(v)[0]` to images/<v>.bin.gz.

    All 15 reproduce the `predictions.json` sha256 byte for byte; `index.json`
    carries them again beside the geometry, and the two are cross-checked here.
    """
    p = IMAGES / f"{variant}.bin.gz"
    if not p.exists():
        raise SystemExit(
            f"sm3_tf_floor_cell: no frozen image for {variant} ({p}).\n"
            "  This cell's stimulus is FROZEN (see image_of.__doc__): it is not\n"
            "  regenerated on this branch, because fuzz-v2 moved the code\n"
            "  region and a re-anchored image is not the program the socket\n"
            "  captures were taken on.")
    with gzip.open(p, "rb") as f:
        image = bytearray(f.read())

    got = hashlib.sha256(bytes(image)).hexdigest()
    want = _frozen_sha(variant)
    if got != want:
        raise SystemExit(
            f"sm3_tf_floor_cell: FROZEN IMAGE MISMATCH for {variant}.\n"
            f"  on disk    : {got}\n"
            f"  registered : {want}\n"
            "  The registered value is `predictions.json`, committed BEFORE the\n"
            "  first board contact of the sitting.  The 90 captures beside it\n"
            "  were taken on the registered bytes, so a mismatch means the\n"
            "  stimulus has drifted away from the silicon and NOTHING here is\n"
            "  scoreable until it is put back.")

    # The geometry `phases()` reads must be the geometry the frozen bytes were
    # built with, or `phase` names the wrong boundary.
    starts, period = starts_of(variant)
    idx = _frozen_index()[variant]
    if [starts, period] != [idx["starts"], idx["period"]]:
        raise SystemExit(
            f"sm3_tf_floor_cell: sled geometry for {variant} has drifted from "
            f"the frozen image.\n  sled()      : starts={starts} period={period}"
            f"\n  frozen image: starts={idx['starts']} period={idx['period']}")
    return image, {"frozen": True, "sha256": got, "path": str(p),
                   "period": period, "starts": starts}


_FROZEN_INDEX = None


def _frozen_index():
    global _FROZEN_INDEX
    if _FROZEN_INDEX is None:
        _FROZEN_INDEX = json.loads((IMAGES / "index.json").read_text())
    return _FROZEN_INDEX


def _frozen_sha(variant):
    """The PRE-REGISTERED sha256 -- `predictions.json` is the authority because
    it was committed before the part ran; `index.json` must agree with it."""
    pred = json.loads((OUT / "predictions.json").read_text())
    a = pred["rows"][variant]["sha256"]
    b = _frozen_index()[variant]["sha256"]
    if a != b:
        raise SystemExit(
            f"sm3_tf_floor_cell: images/index.json disagrees with the "
            f"PRE-REGISTERED predictions.json for {variant}\n"
            f"  predictions.json : {a}\n  index.json       : {b}")
    return a


# --------------------------------------------------------------------------- #
# the observable -- read off the pins, no engine, identical on both sides
# --------------------------------------------------------------------------- #
def entry_frames(rows):
    """Every vector-1 entry's pushed frame.  -> list of dicts.

    An entry pushes three words, SP descending: PSW, CS, IP.  No sled emits any
    other three-in-a-row descending word write (the handler's single
    `MOV [BP+4]` is one write, not three), so the pattern IS an entry.  The
    announcement is walked back over: the two IVT reads below `0x400`.
    """
    cy = ag.cycles(rows, len(rows))
    out, i = [], 0
    while i + 2 < len(cy):
        a, b, c = cy[i], cy[i + 1], cy[i + 2]
        if (a[0] == MEMW and b[0] == MEMW and c[0] == MEMW
                and (rows[a[1]]["ad_addr"] & 0xFFFFF) - 2
                == (rows[b[1]]["ad_addr"] & 0xFFFFF)
                and (rows[b[1]]["ad_addr"] & 0xFFFFF) - 2
                == (rows[c[1]]["ad_addr"] & 0xFFFFF)):
            j = i
            while j > 0 and cy[j - 1][0] == 5 \
                    and (rows[cy[j - 1][1]]["ad_addr"] & 0xFFFFF) < 0x400:
                j -= 1
            vec = None
            if j < i:
                vec = (rows[cy[j][1]]["ad_addr"] & 0xFFFFF) >> 2
            out.append({"push_t1": a[1], "ann_t1": cy[j][1], "vec": vec,
                        "psw": _d(rows, a), "cs": _d(rows, b),
                        "ip": _d(rows, c), "sp_top": rows[a[1]]["ad_addr"]
                        & 0xFFFFF})
            i += 3
            continue
        i += 1
    return out


def _d(rows, c):
    """The 16-bit value a bus cycle carried.  AD is the ADDRESS at T1 and DATA
    from T2 on; by the last retained row the pads may already be driving the
    next cycle's address, so the sample is T2."""
    return rows[min(c[1] + 1, c[2])]["ad_data"] & 0xFFFF


def phases(rows, variant):
    """The phase of every entry's pushed IP.  `None` where the pushed IP is not
    an instruction start -- reported, never rounded to one."""
    starts, period = starts_of(variant)
    out = []
    for f in entry_frames(rows):
        o = (f["ip"] - PC0) % period
        out.append(o if o in starts else None)
    return out


# --------------------------------------------------------------------------- #
# the engine leg -- the SAME stimulus at every candidate floor
# --------------------------------------------------------------------------- #
def run_sim(image, waits, floor, clocks=4200):
    td = tempfile.mkdtemp(prefix="s24_")
    try:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        env = dict(os.environ)
        env["V30SIM_BRKFLOOR"] = str(floor)
        argv = [str(simbin.SIM), "timed-boot", str(ROM), str(img),
                f"--clocks={clocks}", "--ndjson", f"--waits={waits}"]
        p = subprocess.run(argv, capture_output=True, env=env, timeout=300)
        rows = []
        for l in p.stdout.decode().splitlines():
            if l.startswith("{"):
                o = json.loads(l)
                if "t" in o:
                    rows.append(o)
        return rows, p.stderr.decode()
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# SM3 SITTING 25 -- THE SECOND ENGINE.  §85.3 asked for this cell re-scored
# with the `ucore` as the engine, "which is now the sharpest gate the trap
# has".  The RTL leg is the SAME stimulus through the Verilated TB's `+bootimg`
# replay -- the image's own loader stub runs in the core from RESET, which is
# the frame the retained chip rows are stored in -- and the floor is the RTL's
# own compile-time knob `V30_BRK_FLOOR`, the exact counterpart of the model's
# `V30SIM_BRKFLOOR`.  The scan binaries live outside the receipt layer on
# purpose: they are INSTRUMENTS built to be wrong, and the only binary any gate
# quotes is the receipted default (`sw/check_core.py --core ucore`), which is
# what `--core ucore` uses at the LANDED floor.
UCORE_SCAN = Path(os.path.expanduser("~/.cache/ucsimt-tmp/s25scan"))
UCORE_LANDED_FLOOR = 4   # §86: the model's 3, one coordinate over


def _ucore_bin(floor):
    if floor == UCORE_LANDED_FLOOR:
        b = ROOT / "hdl" / "tb" / "obj_dir_ucore" / "Vtb_v30_core"
        if b.exists():
            return b
    b = UCORE_SCAN / f"f{floor}" / "Vtb_v30_core"
    if not b.exists():
        raise SystemExit(f"sm3_tf_floor_cell: no ucore binary for floor {floor} "
                         f"({b}) -- build the scan set first")
    return b


def run_ucore(image, waits, floor, clocks=4200):
    td = tempfile.mkdtemp(prefix="s24u_")
    try:
        img = Path(td) / "img.hex"
        outp = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(_ucore_bin(floor)), f"+bootimg={img}", f"+bootn={clocks}",
                "+mirror=1", f"+out={outp}", f"+waits={waits}"]
        p = subprocess.run(argv, capture_output=True, timeout=900)
        so = p.stdout.decode()
        if "BOOT DONE" not in so:
            return [], (so[-200:] + " " + p.stderr.decode()[-200:]).strip()
        rows = []
        for line in outp.read_text().splitlines():
            f = line.split()
            if f and f[0] == "r":
                rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                             "qs": int(f[3]), "ube_n": int(f[4]),
                             "ad_addr": int(f[5], 16), "ad_data": int(f[6], 16),
                             "ps": int(f[7], 16)})
        return rows, ""
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def run_engine(core, image, waits, floor, clocks=4200):
    return (run_sim if core == "sim" else run_ucore)(image, waits, floor, clocks)


def brk_walk(image, waits):
    """dist(rise -> Bj) for the FIRST armed setter, off the engine's own retire
    trace.  This is the CLOCK RULER of the whole cell, and it is the engine's;
    it is credible exactly as far as the engine's bus timing on the same sled
    matches the chip's per clock, which `score` checks and reports."""
    td = tempfile.mkdtemp(prefix="s24w_")
    try:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        env = dict(os.environ)
        env["V30SIM_BRKTRACE"] = "1"
        env["V30SIM_BRKFLOOR"] = "99"      # never take: the UNPERTURBED walk
        argv = [str(simbin.SIM), "timed-boot", str(ROM), str(img),
                "--clocks=1200", "--ndjson", f"--waits={waits}"]
        p = subprocess.run(argv, capture_output=True, env=env, timeout=300)
        tr = []
        for l in p.stderr.decode().splitlines():
            m = re.match(r"BRKR clk=(-?\d+) tf=(\d) rise=(-?\d+) seen=(\d) "
                         r"take=(\d) arm=(\d) op=(\w\w)", l)
            if m:
                g = m.groups()
                tr.append((int(g[0]), int(g[1]), int(g[2]), int(g[6], 16)))
        for i, t in enumerate(tr):
            if t[1] == 1 and t[2] >= 0:
                rise = t[2]
                return [x[0] - rise for x in tr[i:i + 5]], \
                       [f"{x[3]:02X}" for x in tr[i:i + 5]]
        return None, None
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# --------------------------------------------------------------------------- #
def cmd_predict(args):
    floors = [int(x) for x in args.floors.split(",")]
    waits = [int(x) for x in args.waits.split(",")]
    tab = {"cell": "SM3 s24 -- the BRK/TF arm FLOOR, measured",
           "floors": floors, "waits": waits, "sim": simbin.SIM.name,
           "rows": {}}
    for v in VARIANTS:
        image, _meta = image_of(v)
        starts, period = starts_of(v)
        tab["rows"][v] = {"period": period, "starts": starts,
                          "sha256": hashlib.sha256(bytes(image)).hexdigest(),
                          "cells": {}}
        for w in waits:
            dist, ops = brk_walk(image, w)
            cell = {"walk": dist, "walk_ops": ops, "floor": {}}
            for f in floors:
                rows, _ = run_engine(args.core, image, w, f)
                ph = phases(rows, v)
                cell["floor"][str(f)] = {"n": len(ph),
                                         "phases": ph[:12],
                                         "hist": _hist(ph)}
            tab["rows"][v][f"w{w}"] = cell
            print(f"{v:10s} w{w} walk={dist} "
                  + "  ".join(f"F{f}:{_hist(cell['floor'][str(f)]['phases'])}"
                              for f in floors), flush=True)
    tab["core"] = args.core
    OUT.mkdir(parents=True, exist_ok=True)
    # THE PRE-REGISTERED TABLE IS THE MODEL'S AND IT IS NEVER OVERWRITTEN: it
    # was committed before the first board contact and it is what W-2 is scored
    # against as registered.  A second engine writes a second file.
    name = ("predictions.json" if args.core == "sim"
            else f"predictions-{args.core}.json")
    (OUT / name).write_text(json.dumps(tab, indent=1))
    print(f"\nwrote {OUT/name}")


def _hist(ph):
    c = Counter("None" if x is None else str(x) for x in ph)
    return dict(sorted(c.items()))


# --------------------------------------------------------------------------- #
def cmd_run(args):
    from s10_board import capture, DIV_OF_RECORD
    from s13_board import div_guard
    from t2b_board import HOST
    import emit_suite as es
    assert es.EMIT_USE_CORE is False, \
        "s24 TF-floor cell refuses to run: truth is the socket"

    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in args.waits.split(",")]
    variants = [v for v in args.variants.split(",") if v] if args.variants \
        else list(VARIANTS)
    man = {"cell": "SM3 s24 -- the BRK/TF arm FLOOR, measured",
           "spec": "docs/notes/sm3_s24_prereg_2026-08-05.md",
           "prereg_commit": args.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "variants": variants,
           "reps": args.reps, "evt": None, "cells": {}}
    man["div_guard"] = div_guard("sm3-s24tfcell")
    # MERGE, never clobber: a cell run in two passes (controls first, then the
    # TF sleds) must not lose the first pass's record to the second's write.
    old = OUT / "manifest.json"
    if old.exists():
        prev = json.loads(old.read_text())
        man["cells"] = dict(prev.get("cells", {}))
        man["variants"] = sorted(set(prev.get("variants", [])) | set(variants))
        man["div_guard_prev"] = prev.get("div_guard")
    t0, consec = time.time(), 0
    for v in variants:
        image, _meta = image_of(v)
        for w in waits:
            for rep in range(args.reps):
                key = f"{v}:w{w}:r{rep}"
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD, evt=None,
                        tag="s24tf")
                    consec = 0
                except Exception as e:                    # noqa: BLE001
                    consec += 1
                    print(f"  {key}: TRANSPORT ERROR {e}", flush=True)
                    if consec >= 5:
                        print("  *** 5 consecutive transport errors -- STOP "
                              "***", flush=True)
                        man["stopped"] = key
                        (OUT / "manifest.json").write_text(
                            json.dumps(man, indent=1))
                        raise SystemExit(3)
                    continue
                ph = phases(rows, v)
                man["cells"][key] = {"sha": sha, "rows": len(rows),
                                     "nentry": len(ph), "hist": _hist(ph)}
                with gzip.open(OUT / f"{key.replace(':','_')}.rows.json.gz",
                               "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(OUT / f"{key.replace(':','_')}.raw.hex.gz",
                               "wt") as f:
                    f.write("\n".join(raw) + "\n")
                print(f"  {key}: rows={len(rows)} entries={len(ph)} "
                      f"hist={_hist(ph)} ({time.time()-t0:.0f}s)", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    _sha256sums()
    print(f"\n{len(man['cells'])} captures in {time.time()-t0:.0f}s")


def _sha256sums():
    lines = []
    for p in sorted(OUT.glob("*")):
        if p.name == "SHA256SUMS" or not p.is_file():
            continue
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def cmd_idle(args):
    from b1_recapture import board_idle
    board_idle()
    print("board_idle: OK")


# --------------------------------------------------------------------------- #
def cmd_score(args):
    """Score every registered bar of `sm3_s24_prereg_2026-08-05.md` §6.

    `--table` selects WHICH prediction table the floor is scored against:
    `predictions.json` is the PRE-REGISTERED one, committed before contact;
    `predictions_corrected.json` is the same table regenerated after §85.2's
    instrument fix.  Both are scored and both are reported -- the registered
    outcome is never replaced by the corrected one.
    """
    import fuzz_classify as fc
    man = json.loads((OUT / "manifest.json").read_text())
    waits = man["waits"]
    ph_of = {}
    for key in man["cells"]:
        v, w, r = key.split(":")
        with gzip.open(OUT / f"{v}_{w}_{r}.rows.json.gz", "rt") as fh:
            ph_of[(v, w, r)] = phases(json.load(fh), v)
    rep = {"bars": {}}

    # --- W-0a  the null -----------------------------------------------------
    nulls = [(k, len(p)) for k, p in ph_of.items()
             if k[0] in NOTF_VARIANTS + ("iretnotf",)]
    w0a = sum(n for _, n in nulls)
    rep["bars"]["W-0a"] = {"captures": len(nulls), "entries": w0a,
                           "bar": 0, "met": w0a == 0}
    print(f"W-0a  TF-clear null: {len(nulls)} captures, {w0a} vector-1 "
          f"entries (bar 0)  -> {'MET' if w0a == 0 else 'NOT MET'}")

    # --- W-1  determinism ---------------------------------------------------
    bad = []
    for v in sorted({k[0] for k in ph_of}):
        for w in waits:
            got = [ph_of[(v, f"w{w}", f"r{r}")] for r in range(man["reps"])
                   if (v, f"w{w}", f"r{r}") in ph_of]
            if got and any(g != got[0] for g in got):
                bad.append(f"{v}:w{w}")
    rep["bars"]["W-1"] = {"disagreeing_cells": bad, "met": not bad}
    print(f"W-1   determinism across {man['reps']} repeats: "
          f"{'MET -- every cell identical' if not bad else 'NOT MET ' + str(bad)}")

    # --- W-0b  the clock ruler ---------------------------------------------
    tot = nd = 0
    for v in NOTF_VARIANTS + ("iretnotf",):
        for w in waits:
            with gzip.open(OUT / f"{v}_w{w}_r0.rows.json.gz", "rt") as fh:
                rows = json.load(fh)
            image, _m = image_of(v)
            srows, _ = run_engine(args.core, image, w,
                                  UCORE_LANDED_FLOOR, clocks=len(rows))
            d = fc.diff_rows(rows, srows, limit=len(rows), window=len(rows))
            tot += min(len(rows), len(srows))
            nd += len(d.rows)
    rep["bars"]["W-0b"] = {"rows": tot, "ndiff": nd, "bar": 0, "met": nd == 0}
    print(f"W-0b  clock ruler, chip vs engine per clock on the LAW-FREE "
          f"controls: {tot} rows, {nd} row-diffs (bar 0)  -> "
          f"{'MET' if nd == 0 else 'NOT MET'}")

    # --- W-2  the floor, on BOTH tables ------------------------------------
    scored = [v for v in POPF_VARIANTS + ("iret",)]
    tables = (("predictions.json", "predictions_corrected.json")
              if args.core == "sim" else (f"predictions-{args.core}.json",))
    for tab in tables:
        fp = OUT / tab
        if not fp.exists():
            continue
        pred = json.loads(fp.read_text())
        surv, per = set(pred["floors"]), {}
        for v in scored:
            for w in waits:
                cp = ph_of[(v, f"w{w}", "r0")]
                hits = [f for f in pred["floors"]
                        if pred["rows"][v][f"w{w}"]["floor"][str(f)]["phases"]
                        == cp[:len(pred["rows"][v][f"w{w}"]["floor"]
                                   [str(f)]["phases"])]]
                per[f"{v}:w{w}"] = hits
                surv &= set(hits)
        n3 = sum(1 for h in per.values() if 3 in h)
        rep["bars"].setdefault("W-2", {})[tab] = {
            "per_cell": per, "survivors": sorted(surv),
            "cells": len(per), "cells_matching_3": n3,
            "misses_at_3": [k for k, h in per.items() if 3 not in h]}
        print(f"W-2   [{tab}] surviving floors over {len(per)} cells: "
              f"{sorted(surv)}   (floor 3 matches {n3}/{len(per)}; "
              f"misses {[k for k, h in per.items() if 3 not in h] or 'none'})")

    # --- W-3  the asymmetry -------------------------------------------------
    w3ok = all(ph_of[("iret", f"w{w}", "r0")][0] == 2
               and ph_of[("popfnone", f"w{w}", "r0")][0] == 3 for w in waits)
    rep["bars"]["W-3"] = {"met": w3ok,
                          "iret": {f"w{w}": ph_of[("iret", f"w{w}", "r0")][0]
                                   for w in waits},
                          "popfnone": {f"w{w}":
                                       ph_of[("popfnone", f"w{w}", "r0")][0]
                                       for w in waits}}
    print(f"W-3   iret vs popfnone, same period, setter the only difference: "
          f"iret={[ph_of[('iret', f'w{w}', 'r0')][0] for w in waits]} "
          f"popfnone={[ph_of[('popfnone', f'w{w}', 'r0')][0] for w in waits]}"
          f"  -> {'MET' if w3ok else 'NOT MET'}")

    # --- W-4  no trap TAKEN at a prefix boundary ---------------------------
    at_pfx = sum(1 for w in waits for r in range(man["reps"])
                 for x in ph_of.get(("popfpfx", f"w{w}", f"r{r}"), []) if x == 2)
    nonstart = sum(1 for w in waits for r in range(man["reps"])
                   for x in ph_of.get(("popfpfx", f"w{w}", f"r{r}"), [])
                   if x is None)
    rep["bars"]["W-4"] = {"phase2": at_pfx, "not_a_start": nonstart,
                          "met": at_pfx == 0 and nonstart == 0}
    print(f"W-4   traps taken AT the prefix boundary (popfpfx phase 2): "
          f"{at_pfx}; pushed IPs that are not an instruction start: "
          f"{nonstart}  -> {'MET' if at_pfx == 0 and nonstart == 0 else 'NOT MET'}")

    # --- W-5  the storm cadence --------------------------------------------
    starts, period = starts_of("storm")
    bad5 = []
    for w in waits:
        seq = ph_of[("storm", f"w{w}", "r0")]
        for a, b in zip(seq, seq[1:]):
            if a is None or b is None or \
                    (starts.index(b) - starts.index(a)) % len(starts) != 1:
                bad5.append((w, a, b))
    rep["bars"]["W-5"] = {"pairs": sum(len(ph_of[("storm", f"w{w}", "r0")]) - 1
                                       for w in waits),
                          "bad": bad5[:10], "met": not bad5}
    print(f"W-5   storm cadence, grace 0 on every consecutive pair: "
          f"{sum(len(ph_of[('storm', f'w{w}', 'r0')]) - 1 for w in waits)} "
          f"pairs, {len(bad5)} bad  -> {'MET' if not bad5 else 'NOT MET'}")

    # --- W-6  per clock, at every floor ------------------------------------
    print("W-6   per clock, chip vs engine, EVERY capture:")
    pc = {}
    for f in [int(x) for x in args.floors.split(",")]:
        tot = nd = 0
        worst = []
        for v in sorted({k[0] for k in ph_of}):
            for w in waits:
                with gzip.open(OUT / f"{v}_w{w}_r0.rows.json.gz", "rt") as fh:
                    rows = json.load(fh)
                image, _m = image_of(v)
                srows, _ = run_engine(args.core, image, w, f,
                                      clocks=len(rows))
                d = fc.diff_rows(rows, srows, limit=len(rows), window=len(rows))
                tot += min(len(rows), len(srows))
                nd += len(d.rows)
                if d.rows:
                    worst.append(f"{v}:w{w}={len(d.rows)}")
        pc[f] = {"rows": tot, "ndiff": nd, "cells_with_diffs": worst}
        print(f"        floor {f}: {tot} rows, {nd} row-diffs"
              + (f"   [{', '.join(worst)}]" if worst else "   EXACT"))
    rep["bars"]["W-6"] = pc
    rep["core"] = args.core
    name = "score.json" if args.core == "sim" else f"score-{args.core}.json"
    (OUT / name).write_text(json.dumps(rep, indent=1))
    print(f"\nwrote {OUT/name}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--floors", default="1,2,3,4,5,6,7")
    p.add_argument("--waits", default="0,3")
    p.add_argument("--core", default="sim", choices=("sim", "ucore"))
    p.set_defaults(fn=cmd_predict)
    p = sub.add_parser("run")
    p.add_argument("--waits", default="0,3")
    p.add_argument("--variants", default="")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--prereg", default="")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("score")
    p.add_argument("--floors", default="1,2,3,4,5,6,7")
    p.add_argument("--core", default="sim", choices=("sim", "ucore"),
                   help="the ENGINE scored against the retained chip rows: "
                        "the C++ timed model (sim) or the ucore RTL in the "
                        "Verilator TB")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("idle")
    p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
