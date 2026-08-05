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
import random
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

import check_seq                                        # noqa: E402
import simbin                                           # noqa: E402

simbin.ensure("sm3 s24 TF-floor cell")
import sm3_ackgeom as ag                                # noqa: E402
from gen_seq import (Prog, PC0, SP0, DATA_LO, DATA_HI,   # noqa: E402
                     far_int_support, HANDLER_AT)

OUT = ROOT / "sw" / "testdata" / "sm3-s24tfcell"
ROM = ROOT / "docs" / "V20BITS.TXT"
MEMW = 6

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
    rng = random.Random(f"sm3-s24/{variant}")
    ins, _ = sled(variant)
    p = Prog(rng)
    for _ in range(NPERIOD):
        for b in ins:
            p.emit(list(b))
    instr = p.assemble()

    ivt, handler = far_int_support()
    ivt = dict(ivt)
    # vector 1 is the SINGLE-STEP vector and `far_int_support` does not route
    # it -- nothing in the tree ever needed it before §83.
    ivt[1] = (0, HANDLER_AT if variant == "storm" else TF_HANDLER_AT)

    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += handler
    if variant != "storm":
        ram += [(TF_HANDLER_AT + i, b) for i, b in enumerate(TF_HANDLER)]

    _starts, period = starts_of(variant)
    tf = not (variant.startswith("notf") or variant == "iretnotf")
    psw = PSW_TF if tf else PSW_NOTF
    if variant in ("iret", "iretnotf"):
        ram = [x for x in ram if not (SP0 <= x[0] < SP0 + 6 * (NPERIOD + 4))]
        for k in range(NPERIOD + 4):
            ip = PC0 + period * k + 1        # the byte AFTER this period's CF
            for j, w in enumerate((ip, 0x0000, psw)):
                ram.append((SP0 + 6 * k + 2 * j, w & 0xFF))
                ram.append((SP0 + 6 * k + 2 * j + 1, w >> 8))
    else:
        ram = [x for x in ram if not (SP0 <= x[0] < SP0 + 2 * (NPERIOD + 4))]
        for k in range(NPERIOD + 4):
            ram.append((SP0 + 2 * k, psw & 0xFF))
            ram.append((SP0 + 2 * k + 1, psw >> 8))

    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": PSW_NOTF,       # TF and IE both CLEAR
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    image, meta = check_seq.compose(dict(seed=0, instr=instr, regs=regs,
                                         ram=ram, ivt=ivt))
    return image, meta


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
                rows, _ = run_sim(image, w, f)
                ph = phases(rows, v)
                cell["floor"][str(f)] = {"n": len(ph),
                                         "phases": ph[:12],
                                         "hist": _hist(ph)}
            tab["rows"][v][f"w{w}"] = cell
            print(f"{v:10s} w{w} walk={dist} "
                  + "  ".join(f"F{f}:{_hist(cell['floor'][str(f)]['phases'])}"
                              for f in floors), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "predictions.json").write_text(json.dumps(tab, indent=1))
    print(f"\nwrote {OUT/'predictions.json'}")


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
    from s13_board import board_idle
    print(board_idle())


# --------------------------------------------------------------------------- #
def cmd_score(args):
    import fuzz_classify as fc
    pred = json.loads((OUT / "predictions.json").read_text())
    man = json.loads((OUT / "manifest.json").read_text())
    floors = pred["floors"]
    chip = defaultdict(list)
    for key, rec in man["cells"].items():
        v, w, _r = key.split(":")
        chip[(v, w)].append(rec["hist"])

    print("=== A. THE CLOCK RULER -- chip vs engine PER CLOCK on the "
          "TF-CLEAR controls (no law in them) ===")
    ruler = {}
    for v in NOTF_VARIANTS + ("iretnotf",):
        image, _m = image_of(v)
        for w in [int(x) for x in str(man["waits"]).strip("[]").split(",")]:
            f = OUT / f"{v}_w{w}_r0.rows.json.gz"
            if not f.exists():
                continue
            with gzip.open(f, "rt") as fh:
                rows = json.load(fh)
            srows, _ = run_sim(image, w, 3, clocks=len(rows))
            d = fc.diff_rows(rows, srows, limit=len(rows), window=len(rows))
            ruler[f"{v}:w{w}"] = {"n": min(len(rows), len(srows)),
                                  "ndiff": len(d.rows)}
            print(f"{v:10s} w{w}: rows={min(len(rows), len(srows))} "
                  f"row-diffs={len(d.rows)}")

    print("\n=== B. THE CHIP, per cell ===")
    survivors = set(floors)
    detail = {}
    for (v, w), hists in sorted(chip.items()):
        same = all(h == hists[0] for h in hists)
        walk = pred["rows"][v][w]["walk"]
        row = {"chip": hists[0], "reps_identical": same, "walk": walk,
               "floor_hits": []}
        for f in floors:
            if pred["rows"][v][w]["floor"][str(f)]["hist"] == hists[0]:
                row["floor_hits"].append(f)
        detail[f"{v}:{w}"] = row
        print(f"{v:10s} {w} walk={walk} chip={hists[0]} "
              f"reps_identical={same} floors_matching={row['floor_hits']}")
        if v != "storm":
            survivors &= set(row["floor_hits"])
    print(f"\n=== SURVIVING FLOORS across every scored cell: "
          f"{sorted(survivors)} ===")

    print("\n=== C. PER-CLOCK, chip vs engine, at each surviving floor ===")
    perclk = {}
    for f in (sorted(survivors) or floors):
        tot = nd = 0
        for (v, w) in sorted(chip):
            image, _m = image_of(v)
            fp = OUT / f"{v}_{w}_r0.rows.json.gz"
            if not fp.exists():
                continue
            with gzip.open(fp, "rt") as fh:
                rows = json.load(fh)
            srows, _ = run_sim(image, int(w[1:]), f, clocks=len(rows))
            d = fc.diff_rows(rows, srows, limit=len(rows), window=len(rows))
            tot += min(len(rows), len(srows))
            nd += len(d.rows)
        perclk[f] = {"rows": tot, "ndiff": nd}
        print(f"floor {f}: {tot} rows, {nd} row-diffs")

    (OUT / "score.json").write_text(json.dumps(
        {"ruler": ruler, "detail": detail, "survivors": sorted(survivors),
         "perclock": perclk}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--floors", default="1,2,3,4,5,6,7")
    p.add_argument("--waits", default="0,3")
    p.set_defaults(fn=cmd_predict)
    p = sub.add_parser("run")
    p.add_argument("--waits", default="0,3")
    p.add_argument("--variants", default="")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--prereg", default="")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("score")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("idle")
    p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
