#!/usr/bin/env python3
"""sm3_h7_cell -- THE DIRECTED BOARD CELL for H7, exactly as
`ucore_provenance.md` §63.3 specifies it.

Spec and PRE-REGISTERED predictions:
`docs/notes/sm3_h7_h3_prereg_2026-08-04.md` §2.  Read it before running this;
the predictions were committed BEFORE the first board contact of the sitting.

WHAT IT ASKS.  §63.2 measured, over the 208 banked NMI seeds, that the chip's
NMI vector read never opens earlier than **A + 12** (A = the rig's assert
clock) while both engines floor at **A + 13**, and that the 14 seeds sitting on
the chip's floor are exactly the seeds the engines miss.  §63.3 then BUILT the
obvious one-register fix -- the NMI pin pipeline 4 -> 3 -- and it is REFUTED:
17 golden NMI cases break, and they are precisely the 17 the EVTTRACE census
identifies as A-LIMITED.  Two silicon populations disagree by one clock in the
same regime, and the in-bank split (14 fire at A+3, 7 at A+4) is cut across by
the wait class, the rig delay, the bus owner at A and the queue occupancy at A.

§63.3's cell, verbatim: *"One fixed instruction stream, the assert delay swept
one clock at a time so that A walks through B-6 ... B-2 with everything else
held, at waits 0/1/2/3, and the whole sweep run twice: once with the queue
PRIMED at the boundary and once with it DRY (the one axis that separates the
golden A-limited cases, which are all cold fetch-trigger cases, from the banked
seeds).  The cell reads out where A+12 appears and where A+13 does.  If the
answer moves with the queue state the extra clock is on the ENTRY (bus) side
and the latch is right; if it does not, the latch depth is conditional on
something neither engine reads and the cell says on what."*

THE TWO SWEEPS, and they are the H1 cell's own stimuli so nothing new is being
introduced beside the question:

  nop      a NOP sled.  The prefetcher runs far ahead of the EU, so every
           recognition boundary is reached with the queue PRIMED.
  ebnext   a chain of `EB 00` near JMPs.  Every instruction flushes the queue,
           so every boundary is reached DRY and the successor byte is a COLD
           FETCH -- the golden A-limited cases' own shape.

THE OBSERVABLE, read off the pins with no engine in the loop:

  A     arm + delay + 2, the rig's own assert clock (`sm3_nmigeom` §63.1, and
        established there four independent ways)
  V     the T1 of the chip's NMI vector read, MEMR at 0x00008
  gap   V - A.  Sweeping `delay` one clock at a time walks A past a FIXED
        boundary, so `gap` falls by 1 per step while the recognition is
        B-limited and then STOPS FALLING: the value it stops at IS the floor,
        and that knee is the whole measurement.

BOARD DISCIPLINE (CLAUDE.md).  Single-writer checked by the caller; SOCKET ONLY
(`use_core=False`); the divider PINNED and `div_guard`'s readback RECORDED; the
FULL per-clock rows retained beside the raw 64-bit words and their sha256;
`board_idle()` at the end; 5 consecutive transport errors STOP the cell.
NO FLASHING -- the board carries FLASH #4 and this cell does not use the core.

Usage:
    python3 sw/sm3_h7_cell.py run [--waits 0,1,2,3] [--delays N] [--d0 N]
    python3 sw/sm3_h7_cell.py report
    python3 sw/sm3_h7_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                              # noqa: E402
import sm3_ackgeom as ag                                # noqa: E402
import sm3_h1_cell as h1                                # noqa: E402
import sm3_nmigeom as ng                                # noqa: E402
from s10_board import capture, DIV_OF_RECORD            # noqa: E402
from s13_board import div_guard                         # noqa: E402
from t2b_board import HOST                              # noqa: E402
import emit_suite as es                                 # noqa: E402

assert es.EMIT_USE_CORE is False, "H7 cell refuses to run: truth is the socket"

OUT = ROOT / "sw" / "testdata" / "sm3-h7cell"
NMI_VEC_LIN = 0x00008
CODE, MEMR = 4, 5
# Every banked NMI seed carries hold = 2 (§63.2), so the part is offered the
# same two-clock pulse here and the only free coordinate is where it lands.
HOLD = 2
VARIANTS = ("nop", "ebnext")


def measure(rows, anchor, delay):
    """A, V and the geometry around both -- chip side, no engine."""
    n = len(rows)
    arm = ng.first_t1(rows, CODE, anchor & 0xFFFFF, n)
    if arm < 0:
        return {"arm": -1}
    A = arm + delay + 2
    V = ng.first_t1(rows, MEMR, NMI_VEC_LIN, n)
    cy = ag.cycles(rows, n)
    # the queue occupancy the recognition was reached with, counted from the
    # capture exactly as §63.6 counts it: bytes delivered by CODE cycles that
    # COMPLETED since the last QS = E, minus the pops seen since
    occ = None
    if V > 0:
        last_e = -1
        for i in range(V - 1, -1, -1):
            if rows[i]["qs"] == 2:
                last_e = i
                break
        base = max(0, last_e)
        delivered = sum(2 for c in cy if c[0] == CODE and c[2] < V and c[1] > base)
        pops = sum(1 for i in range(base + 1, V) if rows[i]["qs"] in (1, 3))
        occ = delivered - pops
    return {"arm": arm, "A": A, "V": V, "gap": (V - A) if V > 0 else None,
            "bus_A": ng.bus_at(rows, A, n), "bus_A1": ng.bus_at(rows, A + 1, n),
            "occ_at_V": occ,
            "nvec": sum(1 for c in cy if c[0] == MEMR and
                        (rows[c[1]]["ad_addr"] & 0xFFFFF) == NMI_VEC_LIN)}


def cmd_run(args):
    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in args.waits.split(",") if x != ""]
    variants = [v for v in args.variants.split(",") if v]
    delays = list(range(args.d0, args.d0 + args.delays))
    man = {"cell": "SM3 H7 -- the NMI recognition floor, primed vs dry",
           "spec": "docs/notes/sm3_h7_h3_prereg_2026-08-04.md §2",
           "prereg_commit": args.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "variants": variants,
           "delays": [delays[0], delays[-1]], "hold": HOLD, "pin": 1,
           "cells": {}}
    man["div_guard"] = div_guard("sm3-h7cell")
    recs = []
    t0 = time.time()
    consec_err = 0
    stop = False
    for variant in variants:
        if stop:
            break
        image, meta = h1.image_of(variant)
        anchor = int(meta["anchor_linear"]) & 0xFFFFF
        for w in waits:
            if stop:
                break
            for d in delays:
                key = f"{variant}:w{w}:d{d}"
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD,
                        evt=(anchor, d, HOLD, 1), tag="sm3h7")
                    consec_err = 0
                except Exception as e:                    # noqa: BLE001
                    consec_err += 1
                    print(f"  {key}: TRANSPORT ERROR {e}", flush=True)
                    if consec_err >= 5:
                        print("  *** 5 consecutive transport errors -- STOP "
                              "(the board is not nursed along) ***", flush=True)
                        man["stopped"] = key
                        stop = True
                        break
                    continue
                g = measure(rows, anchor, d)
                rec = {"key": key, "variant": variant, "waits": w, "delay": d,
                       "sha": sha, "fired": bool(fired), "nrows": len(rows),
                       "geom": g}
                recs.append(rec)
                man["cells"][key] = {"sha": sha, "rows": len(rows),
                                     "fired": bool(fired)}
                stem = key.replace(":", "_")
                with gzip.open(OUT / f"{stem}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(OUT / f"{stem}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                print(f"  {key}: A={g.get('A')} V={g.get('V')} "
                      f"gap={g.get('gap')} occ={g.get('occ_at_V')} "
                      f"busA={g.get('bus_A')} ({time.time()-t0:.0f}s)",
                      flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    (OUT / "cells.json").write_text(json.dumps(recs, indent=1))
    n = _sha_dir(OUT)
    print(f"  retained {n} files with SHA256SUMS in {OUT}")
    report(recs)
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
    print("\n  --- SM3 H7 directed cell: where A+12 appears and where A+13 does ---")
    print("  (PRE-REGISTERED, sm3_h7_h3_prereg_2026-08-04.md §2:"
          "  Q1 no cell below A+12;  Q2 the floor MOVES with the queue state"
          " -> entry side;  Q3 it does not -> the latch is conditional on"
          " something else and the cell must say on what.)")
    got = [r for r in recs if r["geom"].get("gap") is not None]
    print(f"\n  captures {len(recs)}, with a vector read {len(got)}, "
          f"fired {sum(1 for r in recs if r['fired'])}")
    if not got:
        return
    print(f"\n  {'variant':<9}{'w':>3}   floor min(V-A)   n at floor   gap histogram")
    floors = {}
    for variant in sorted({r["variant"] for r in got}):
        for w in sorted({r["waits"] for r in got}):
            grp = [r for r in got if r["variant"] == variant and r["waits"] == w]
            if not grp:
                continue
            gaps = Counter(r["geom"]["gap"] for r in grp)
            f = min(gaps)
            floors[(variant, w)] = f
            print(f"  {variant:<9}{w:>3}   {f:>12}   {gaps[f]:>10}   " +
                  " ".join(f"{k}:{v}" for k, v in sorted(gaps.items())[:10]))
    print("\n  THE DISCRIMINATOR -- the floor, primed vs dry, per wait level:")
    for w in sorted({r["waits"] for r in got}):
        a = floors.get(("nop", w))
        b = floors.get(("ebnext", w))
        verdict = ("(no pair)" if a is None or b is None else
                   "SAME -> Q3: the queue state does not select"
                   if a == b else
                   f"DIFFER by {b - a} -> Q2: the extra clock is ENTRY-side")
        print(f"    w{w}:  primed(nop) {a}   dry(ebnext) {b}    {verdict}")
    below = [r for r in got if r["geom"]["gap"] < 12]
    print(f"\n  Q1 falsifier -- cells with V-A < 12: {len(below)}"
          + (" *** THE FLOOR IS FALSIFIED ***" if below else " (floor holds)"))
    for r in below[:10]:
        print(f"    {r['key']} gap={r['geom']['gap']}")
    # the axes §63.2 already tabulated and found cutting across the split
    print("\n  at the floor, the axes that cut across the in-bank split:")
    for variant in sorted({r["variant"] for r in got}):
        grp = [r for r in got if r["variant"] == variant
               and r["geom"]["gap"] == floors.get((variant, r["waits"]))]
        print(f"    {variant:<9} bus owner at A: "
              + str(dict(Counter(tuple(r['geom']['bus_A'][:2]) for r in grp)))
              + "  occ at V: "
              + str(dict(sorted(Counter(r['geom']['occ_at_V'] for r in grp).items(),
                                key=lambda x: (x[0] is None, x[0])))))


def cmd_score(args):
    """The SAME sweep through an engine, so the chip's knee and the engine's
    knee are read off the same stimulus with the same instrument."""
    recs = json.loads((OUT / "cells.json").read_text())
    imgs = {}
    out = []
    for r in recs:
        if r["variant"] not in imgs:
            imgs[r["variant"]] = h1.image_of(r["variant"])
        image, meta = imgs[r["variant"]]
        anchor = int(meta["anchor_linear"]) & 0xFFFFF
        rows = json.load(gzip.open(
            OUT / f"{r['key'].replace(':', '_')}.rows.json.gz", "rt"))
        erows = h1.engine_rows(image, meta, rows, r["waits"],
                               (anchor, r["delay"], HOLD, 1), args.core)
        g = measure(erows, anchor, r["delay"]) if erows else {}
        out.append((r, g))
    print(f"\n  --- engine `{args.core}` on the SAME H7 sweep ---")
    print(f"  {'variant':<9}{'w':>3}   chip floor   engine floor   delta")
    for v in sorted({r["variant"] for r, _ in out}):
        for w in sorted({r["waits"] for r, _ in out}):
            grp = [(r, g) for r, g in out if r["variant"] == v
                   and r["waits"] == w]
            cg = [r["geom"]["gap"] for r, _ in grp
                  if r["geom"].get("gap") is not None]
            eg = [g["gap"] for _, g in grp if g.get("gap") is not None]
            if not cg or not eg:
                continue
            print(f"  {v:<9}{w:>3}   {min(cg):>10}   {min(eg):>12}   "
                  f"{min(eg)-min(cg):>+5}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--waits", default="0,1,2,3")
    r.add_argument("--variants", default=",".join(VARIANTS))
    r.add_argument("--delays", type=int, default=16)
    r.add_argument("--d0", type=int, default=6)
    r.add_argument("--prereg", default="")
    sub.add_parser("report")
    s = sub.add_parser("score")
    s.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"))
    sub.add_parser("idle")
    a = ap.parse_args()
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "report":
        report()
        return 0
    if a.cmd == "score":
        return cmd_score(a)
    return h1.cmd_idle(a)


if __name__ == "__main__":
    sys.exit(main())
