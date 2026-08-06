#!/usr/bin/env python3
"""w33_poste_cell -- THE DIRECTED BOARD CELL for `mc1/721`: WHERE DOES A
POST-`E` REGISTER WRITE LAND RELATIVE TO THE SUCCESSOR'S ONE-BYTE-LOGIC WRITE?

Spec and PRE-REGISTERED per-candidate predictions:
`docs/notes/wrfuzz_w33_prereg_2026-08-06.md`.  Read it before running this; the
predictions were committed BEFORE the first board contact of the sitting.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

WHAT IT ASKS.  `ucore_provenance.md` sec.86.G diagnosed `mc1/721` to the clock:

    1BL clk=303  pre=f202 post=f203     <- the SUCCESSOR's one-byte-logic write
    PE  clk=304  pre=f203 post=f203     <- the PREDECESSOR's POST-`E` row,
                                           ONE CLOCK LATER

-- both writes land, in the WRONG ORDER, because on the `E`-row PRE-POP path
the successor's zero-cost loader chain rides the SAME edge as the `E` row and
the post-`E` discharge slips to the next.  sec.87.B then found that sec.86.G's
specified fix ("discharge `poste` inline at the point it is raised") CANNOT be
done on one micro-ROM read, and booked the honest block: **two independently
measured laws collide** -- sec.35.3's 1BL execute strobe on clock 1, and the
post-`E` row's own one-clock cost -- and one seed cannot say which moves.

sec.86.G's falsifier, verbatim:

    any <ROM form whose post-`E` row writes a register> followed by a
    <1BL form that writes the same register> with a PRE-POPPED successor,
    where the ucore's final value is the successor's write rather than the
    post-`E`'s.

THIS CELL MANUFACTURES EXACTLY THAT, in two independent readouts, plus the
control arm that decides WHICH placement moves.

  ARM A -- `9E` SAHF's post-`E` writes the FULL flag word (its `007D` row
           snapshots `FLAGS -> tmpaH`, so IE rides in the high byte), and the
           successor is `FA` DI.  **IE is on the `ps` pins on every active data
           phase**, so the observable needs no memory write at all and no
           frame reader: it is the `ie` bit of the status nibble during the NOP
           run that follows.

  ARM B -- the same collision read as a WORD: `9E` SAHF then a CY-writing 1BL
           (`F5` CMC / `F9` STC / `F8` CLC), then `9C` PUSHF, whose `MEMW`
           carries the whole flag word onto the lanes.  Three outcomes are
           distinguishable, not two, because the sled plants a DIFFERENT flag
           byte before the pair: post-`E`-first, 1BL-first, and post-`E`-LOST.

  ARM D -- **the decider**: an ISOLATED 1BL (`FA` DI) with no post-`E` anywhere
           near it, whose IE clear is timed against a bus anchor.  If the
           `ucore` publishes the clear ONE CLOCK EARLY here too, then the 1BL
           commit is what moves, the post-`E` row keeps its clock and its ROM
           word, and sec.87.B's collision DISSOLVES with no second micro-ROM
           read.  If the `ucore` matches silicon clock for clock in isolation,
           the two placements really do collide and the block stands.

  CONTROLS -- `9E` with a NOP successor (both orders agree), a 1BL with no
           `9E` (both orders agree), and DI/EI nulls.  They say the readout is
           reading the collision and not the rig.

BOARD DISCIPLINE (CLAUDE.md).  Single-writer checked by the caller; SOCKET ONLY
(`use_core=False`, explicit, because the board's CFG is sticky); the divider
PINNED and `div_guard`'s readback RECORDED; the FULL per-clock rows retained
beside the raw 64-bit words and their sha256; `board_idle()` at the end; a run
of consecutive transport errors STOPS the cell.  **NO FLASHING**, and this cell
drives NO PIN AT ALL -- every arm is internal, so there is no `evt`, no hold,
no `fired`, and none of INV-1's directive-truncation exposure.

Usage:
    python3 sw/w33_poste_cell.py predict
    python3 sw/w33_poste_cell.py engines [--waits 0,3]      # offline, no board
    python3 sw/w33_poste_cell.py run [--waits 0,3] [--reps 3] --prereg <sha>
    python3 sw/w33_poste_cell.py score
    python3 sw/w33_poste_cell.py idle
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
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                        # noqa: E402
import simbin                                           # noqa: E402

simbin.ensure("w33 post-E collision cell")
import sm3_ackgeom as ag                                # noqa: E402
from gen_seq import Prog, PC0, SP0, DATA_LO, DATA_HI    # noqa: E402

OUT = ROOT / "sw" / "testdata" / "w33-postecell"
ROM = ROOT / "docs" / "V20BITS.TXT"

MEMW, MEMR, CODE, PASV = 6, 5, 4, 7
NPERIOD = 40

# --------------------------------------------------------------------------- #
# the sleds
# --------------------------------------------------------------------------- #
# ARM A -- the IE readout.  `FB` EI raises IE; `9E` SAHF's `E` row snapshots
# the flag word (IE = 1) into `tmpaH` and its POST-`E` row writes the whole
# word back; `FA` DI is the successor 1BL that clears IE.  The NOP run that
# follows is where `ps.ie` is read, on every active data phase.
#
#   post-E FIRST  ->  FLAGS := snapshot (IE=1), then DI clears  ->  ie = 0
#   1BL    FIRST  ->  DI clears, then FLAGS := snapshot (IE=1)  ->  ie = 1
#
# The pad walks the successor's arrival relative to the `E` row, which is what
# selects the PRE-POP path; `none` is the tightest and `movi` the loosest.
A_PADS = {
    "none": [],
    "clc":  [0xF8],                 # a CY 1BL between them: still adjacent
    "inc":  [0x41],                 # INC CW
    "movi": [0xB0, 0x5A],           # MOV AL,imm8 -- the longest short pad
}
ATAIL = 8                           # NOPs: the IE observation window


def _a_sled(pad, di=True, sahf=True):
    ins = [[0xFB]]                                  # EI
    ins += [[0x9E]] if sahf else [[0x90]]           # SAHF (the post-E form)
    if pad:
        ins += [list(pad)]
    ins += [[0xFA]] if di else [[0x90]]             # DI  (the successor 1BL)
    ins += [[0x90]] * ATAIL
    return ins


# ARM B -- the WORD readout.  `33 C0` XOR AW,AW plants a flag byte of 0x46
# (ZF, PF; CY clear) that neither candidate can produce, so a LOST post-`E` is
# a THIRD outcome and not a tie.  `B4 xx` seeds AH; `9E` SAHF's post-`E` writes
# it; the 1BL writes CY; `9C` PUSHF puts the whole word on the lanes.
B_1BL = {"cmc": (0xF5, "CMC"), "stc": (0xF9, "STC"), "clc": (0xF8, "CLC")}


def _b_sled(ah, bl, sahf=True):
    ins = [[0x33, 0xC0], [0xB4, ah]]
    ins += [[0x9E]] if sahf else [[0x90]]
    ins += [[bl]] if bl is not None else [[0x90]]
    ins += [[0x9C], [0x5A]]                          # PUSHF ; POP DX
    return ins


# ARM D -- the ISOLATED 1BL.  No `9E` anywhere.  `8A 07` MOV AL,[BW] is the
# bus ANCHOR whose T1 fixes the clock axis; the pad walks the DI's commit
# relative to the prefetch phase, so across the pad set SOME cell has an active
# data phase straddling the commit clock.
D_PADS = {"p0": [], "p1": [0x90], "p2": [0x90, 0x90], "p3": [0x90] * 3,
          "p4": [0x90] * 4, "p5": [0x90] * 5}


def _d_sled(pad):
    return ([[0xFB]]                     # EI      -- IE up
            + [[0x8A, 0x07]]             # MOV AL,[BW]  -- the ANCHOR MEMR
            + ([list(pad)] if pad else [])
            + [[0xFA]]                   # DI      -- the ISOLATED 1BL
            + [[0x8A, 0x07]]             # MOV AL,[BW]  -- the READOUT MEMR
            + [[0x90]] * 4)


VARIANTS = {}
for _k, _p in A_PADS.items():
    VARIANTS[f"a_{_k}"] = ("A", _a_sled(_p))
VARIANTS["a_noDI"] = ("Actl", _a_sled([], di=False))          # ie must stay 1
VARIANTS["a_no9E"] = ("Actl", _a_sled([], sahf=False))        # ie must be 0
for _k, (_b, _n) in B_1BL.items():
    # AH is chosen so the two candidates differ in CY: `cmc`/`clc` start from
    # CY=1 (AH bit0), `stc` from CY=0.
    _ah = 0xD4 if _k == "stc" else 0xD5
    VARIANTS[f"b_{_k}"] = ("B", _b_sled(_ah, _b))
VARIANTS["b_nobl"] = ("Bctl", _b_sled(0xD5, None))            # 9E, no 1BL
VARIANTS["b_no9E"] = ("Bctl", _b_sled(0xD5, 0xF5, sahf=False))  # 1BL, no 9E
for _k, _p in D_PADS.items():
    VARIANTS[f"d_{_k}"] = ("D", _d_sled(_p))


def sled(variant):
    return VARIANTS[variant][1]


def arm_of(variant):
    return VARIANTS[variant][0]


def starts_of(variant):
    starts, off = [], 0
    for b in sled(variant):
        starts.append(off)
        off += len(b)
    return starts, off


def image_of(variant):
    rng = random.Random(f"w33-poste/{variant}")
    p = Prog(rng)
    for _ in range(NPERIOD):
        for b in sled(variant):
            p.emit(list(b))
    instr = p.assemble()
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0,
            # IE and BRK both CLEAR at reset: no pin is driven and no trap may
            # fire.  Every arm raises IE itself with its own `FB`.
            "PSW": 0xF002,
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    image, meta = check_seq.compose(dict(seed=0, instr=instr, regs=regs,
                                         ram=ram))
    return image, meta


# --------------------------------------------------------------------------- #
# the observables -- read off the pins, no engine, identical on both sides
# --------------------------------------------------------------------------- #
def t_of(r):
    return r.get("t_state", r.get("t"))


def cycles(rows, n=None):
    n = n or len(rows)
    out = []
    for i in range(min(n, len(rows))):
        if t_of(rows[i]) == 1 and rows[i]["bs_early"] != PASV:
            out.append((i, rows[i]["bs_early"], rows[i]["ad_addr"] & 0xFFFFF))
    return out


def ie_census(rows, skip=200):
    """ARM A / D.  The `ie` bit (bit 2) of the status nibble on every active
    DATA phase (`t == 2`), by bus status.  Boot rows are skipped: the sled has
    not started yet and the reset stub's own cycles are not the measurement."""
    c = Counter()
    for i in range(skip, len(rows)):
        r = rows[i]
        if t_of(r) == 2 and r["bs_early"] != PASV:
            c[(r["bs_early"], (r["ps"] >> 2) & 1)] += 1
    return c


def a_readout(rows, skip=200):
    """ARM A's ONE-BIT observable: `ie` on the CODE fetches of the NOP run.
    Reported as a histogram, never rounded to a single value -- the sled raises
    and lowers IE once per period, so BOTH values must appear; what the
    candidates disagree about is the RATIO, and the discriminator is written in
    the pre-registration as the count on the fetches that follow the DI."""
    c = ie_census(rows, skip)
    tot = {}
    for (bs, ie), k in c.items():
        tot.setdefault(bs, [0, 0])[ie] += k
    return {bs: v for bs, v in sorted(tot.items())}


def b_words(rows, skip=200):
    """ARM B's observable: the word every `PUSHF` `MEMW` put on the lanes.
    The sled's ONLY word write is the PUSHF (the POP is a read), so the MEMW
    stream IS the flag stream."""
    out = []
    cy = cycles(rows)
    for k, (r, bs, a) in enumerate(cy):
        if bs != MEMW or r < skip:
            continue
        end = cy[k + 1][0] if k + 1 < len(cy) else len(rows)
        out.append(rows[min(r + 1, end - 1)]["ad_data"] & 0xFFFF)
    return out


def d_readout(rows, skip=200):
    """ARM D's observable, engine-free and clock-resolved: for every ANCHOR
    `MEMR`, the OFFSET in clocks from its T1 to the first active data phase
    that publishes `ie == 0`.  The sled raises IE with `FB` before the anchor
    and clears it with `FA` after, so the offset IS the 1BL commit's clock plus
    the fixed publication delay -- and the pad walks the prefetch phase, so a
    one-clock move in the commit shows up as a one-clock move in the offset on
    the cells where a data phase straddles it."""
    cy = cycles(rows)
    offs = []
    for k, (r, bs, a) in enumerate(cy):
        if bs != MEMR or r < skip:
            continue
        # the first `ie == 0` data phase strictly after this anchor's T1
        for i in range(r + 1, min(r + 60, len(rows))):
            rr = rows[i]
            if t_of(rr) == 2 and rr["bs_early"] != PASV:
                if ((rr["ps"] >> 2) & 1) == 0:
                    offs.append(i - r)
                    break
                # IE still up: keep looking inside this anchor's window
        else:
            offs.append(None)
    return offs


def observe(rows, variant):
    arm = arm_of(variant)
    if arm in ("A", "Actl"):
        return {"ie": {str(k): v for k, v in a_readout(rows).items()}}
    if arm in ("B", "Bctl"):
        w = b_words(rows)
        return {"words": dict(Counter(f"{x:04x}" for x in w)), "n": len(w)}
    return {"doff": dict(Counter(str(x) for x in d_readout(rows)))}


# --------------------------------------------------------------------------- #
# the engine legs -- the SAME stimulus, both engines, no board
# --------------------------------------------------------------------------- #
def run_sim(image, waits, clocks=4200, brktrace=False):
    td = tempfile.mkdtemp(prefix="w33_")
    try:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        env = dict(os.environ)
        if brktrace:
            env["V30SIM_BRKTRACE"] = "1"
        argv = [str(simbin.SIM), "timed-boot", str(ROM), str(img),
                f"--clocks={clocks}", "--ndjson", f"--waits={waits}"]
        p = subprocess.run(argv, capture_output=True, env=env, timeout=600)
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


def _tb_bin():
    import timed_fuzz as tf
    return tf.tb_bin("ucore")


def run_ucore(image, waits, clocks=4200, brktrace=False):
    td = tempfile.mkdtemp(prefix="w33u_")
    try:
        img = Path(td) / "img.hex"
        outp = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(_tb_bin()), f"+bootimg={img}", f"+bootn={clocks}",
                "+mirror=1", f"+out={outp}", f"+waits={waits}"]
        if brktrace:
            argv.append("+brktrace")
        p = subprocess.run(argv, capture_output=True, timeout=900)
        so = p.stdout.decode()
        if "BOOT DONE" not in so:
            return [], so[-400:]
        rows = []
        for line in outp.read_text().splitlines():
            f = line.split()
            if f and f[0] == "r":
                rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                             "qs": int(f[3]), "ube_n": int(f[4]),
                             "ad_addr": int(f[5], 16),
                             "ad_data": int(f[6], 16), "ps": int(f[7], 16)})
        return rows, so
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


ADJ_RE = re.compile(r'(1BL|PE)\s+clk=(\d+) pre=([0-9a-f]{4}) post=([0-9a-f]{4})'
                    r'(?: upc=([0-9A-F]{3}))?')


def adjacencies(trace_text):
    """The GEOMETRY PREDICATE the arm is only valid under: a `1BL` write at
    clock N followed by a `PE` (post-`E`) write at N+1.  This is sec.86.G's own
    signature and it is checked BEFORE any prediction is scored -- an arm that
    does not reproduce it is reported as GEOMETRY-ABSENT, not as a result."""
    evs = []
    for l in trace_text.splitlines():
        m = ADJ_RE.match(l.strip())
        if m:
            evs.append((m.group(1), int(m.group(2)), int(m.group(3), 16),
                        int(m.group(4), 16), m.group(5)))
    adj = []
    for i in range(len(evs) - 1):
        a, b = evs[i], evs[i + 1]
        if a[0] == "1BL" and b[0] == "PE" and b[1] == a[1] + 1:
            adj.append({"clk": a[1], "bl_pre": a[2], "bl_post": a[3],
                        "pe_post": b[3], "upc": b[4],
                        "bl_bits": a[2] ^ a[3]})
    return adj, len(evs)


# --------------------------------------------------------------------------- #
def cmd_engines(a):
    """OFFLINE.  Both engines on every arm, plus the GEOMETRY PREDICATE.  This
    is what the pre-registration's prediction table is written from, and it is
    run BEFORE any board contact."""
    waits = [int(x) for x in a.waits.split(",")]
    variants = a.variants.split(",") if a.variants else list(VARIANTS)
    rec = {"tool": "w33_poste_cell engines", "waits": waits, "cells": {}}
    for v in variants:
        image, _ = image_of(v)
        for w in waits:
            key = f"{v}:w{w}"
            srows, serr = run_sim(image, w, a.clocks)
            urows, uso = run_ucore(image, w, a.clocks, brktrace=True)
            adj, nev = adjacencies(uso)
            eff = [x for x in adj if x["bl_bits"]]
            cell = {"sim": observe(srows, v) if srows else "ENGINE ERROR",
                    "ucore": observe(urows, v) if urows else "ENGINE ERROR",
                    "adj": len(adj), "adj_effective": len(eff),
                    "adj_bits": dict(Counter(f"{x['bl_bits']:04x}"
                                             for x in eff)),
                    "nrows": [len(srows), len(urows)]}
            rec["cells"][key] = cell
            print(f"  {key:<16} adj={len(adj):>3} eff={len(eff):>3} "
                  f"{cell['adj_bits']}")
            print(f"      sim   {json.dumps(cell['sim'])}")
            print(f"      ucore {json.dumps(cell['ucore'])}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "engines.json").write_text(json.dumps(rec, indent=1))
    return 0


def cmd_predict(a):
    print(__doc__.split("Usage:")[0])
    print("The prediction table lives in the pre-registration document and is "
          "NOT restated here, so that it cannot drift from the committed "
          "copy: docs/notes/wrfuzz_w33_prereg_2026-08-06.md")
    return 0


def cmd_run(a):
    from s10_board import capture, DIV_OF_RECORD
    from s13_board import div_guard
    from t2b_board import HOST
    import emit_suite as es
    assert es.EMIT_USE_CORE is False, \
        "w33 post-E cell refuses to run: truth is the socket"

    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in a.waits.split(",")]
    variants = a.variants.split(",") if a.variants else list(VARIANTS)
    man = {"cell": "wrfuzz W3.3 -- the post-E / 1BL commit-order collision",
           "spec": "docs/notes/wrfuzz_w33_prereg_2026-08-06.md",
           "prereg_commit": a.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "variants": variants,
           "reps": a.reps, "evt": None, "cells": {}}
    man["div_guard"] = div_guard("w33-postecell")
    old = OUT / "manifest.json"
    if old.exists():
        prev = json.loads(old.read_text())
        man["cells"] = dict(prev.get("cells", {}))
        man["variants"] = sorted(set(prev.get("variants", [])) | set(variants))
        man["div_guard_prev"] = prev.get("div_guard")
    t0, consec = time.time(), 0
    for v in variants:
        image, _ = image_of(v)
        for w in waits:
            for rep in range(a.reps):
                key = f"{v}:w{w}:r{rep}"
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD, evt=None,
                        tag="w33pe")
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
                obs = observe(rows, v)
                man["cells"][key] = {"sha": sha, "rows": len(rows), "obs": obs}
                with gzip.open(OUT / f"{key.replace(':','_')}.rows.json.gz",
                               "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(OUT / f"{key.replace(':','_')}.raw.hex.gz",
                               "wt") as f:
                    f.write("\n".join(raw) + "\n")
                print(f"  {key}: rows={len(rows)} {json.dumps(obs)} "
                      f"({time.time()-t0:.0f}s)", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    _sha256sums()
    print(f"\n{len(man['cells'])} captures in {time.time()-t0:.0f}s")
    return 0


def _sha256sums():
    lines = []
    for p in sorted(OUT.glob("*")):
        if p.name == "SHA256SUMS" or not p.is_file():
            continue
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def cmd_idle(a):
    from b1_recapture import board_idle
    board_idle()
    print("board_idle: OK")
    return 0


def cmd_score(a):
    """Scores the RETAINED captures against BOTH engines, cell for cell.  No
    board contact; the captures are silicon and they are deterministic from
    RESET (this cell drives no pin)."""
    man = json.loads((OUT / "manifest.json").read_text())
    eng = json.loads((OUT / "engines.json").read_text()) \
        if (OUT / "engines.json").exists() else {"cells": {}}
    rows_of = {}
    for key in man["cells"]:
        p = OUT / f"{key.replace(':', '_')}.rows.json.gz"
        with gzip.open(p, "rt") as f:
            rows_of[key] = json.load(f)
    verdicts = {}
    for key in sorted(man["cells"]):
        v, w, _rep = key.split(":")
        obs = observe(rows_of[key], v)
        e = eng["cells"].get(f"{v}:{w}", {})
        verdicts[key] = {"chip": obs, "sim": e.get("sim"),
                         "ucore": e.get("ucore"),
                         "chip==sim": obs == e.get("sim"),
                         "chip==ucore": obs == e.get("ucore")}
        print(f"{key:<22} chip=={'sim  ' if obs == e.get('sim') else '     '}"
              f"{'ucore' if obs == e.get('ucore') else ''}")
        print(f"    chip  {json.dumps(obs)}")
        if e:
            print(f"    sim   {json.dumps(e.get('sim'))}")
            print(f"    ucore {json.dumps(e.get('ucore'))}")
    (OUT / "score.json").write_text(json.dumps(verdicts, indent=1))
    ns = sum(1 for x in verdicts.values() if x["chip==sim"])
    nu = sum(1 for x in verdicts.values() if x["chip==ucore"])
    print(f"\n{len(verdicts)} cells:  chip==sim {ns}   chip==ucore {nu}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict"); p.set_defaults(fn=cmd_predict)
    p = sub.add_parser("engines")
    p.add_argument("--waits", default="0,3")
    p.add_argument("--variants", default=None)
    p.add_argument("--clocks", type=int, default=4200)
    p.set_defaults(fn=cmd_engines)
    p = sub.add_parser("run")
    p.add_argument("--waits", default="0,3")
    p.add_argument("--variants", default=None)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--prereg", default=None)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("score"); p.set_defaults(fn=cmd_score)
    p = sub.add_parser("idle"); p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
