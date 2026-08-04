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
                     far_int_support)
from s10_board import capture, DIV_OF_RECORD            # noqa: E402
from s13_board import div_guard                         # noqa: E402
from t2b_board import HOST                              # noqa: E402
import emit_suite as es                                 # noqa: E402

assert es.EMIT_USE_CORE is False, "H1 cell refuses to run: truth is the socket"

OUT = ROOT / "sw" / "testdata" / "sm3-h1cell"
INTA, CODE, HALT = 0, 4, 3

# --------------------------------------------------------------------------- #
# the four stimuli
# --------------------------------------------------------------------------- #
VARIANTS = ("nop", "ebnext", "farnext", "callret")


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
    elif variant == "callret":
        for _ in range(n):
            p.emit([0xE8, 0x00, 0x00])     # CALL next  (pushes, redirects)
            p.emit([0xC3])                 # RET        (pops,   redirects)
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
    image, meta = check_seq.compose(dict(seed=0, instr=instr, regs=regs,
                                         ram=ram, ivt=ivt))
    return image, meta


# --------------------------------------------------------------------------- #
# the observable -- read off the pins, no engine
# --------------------------------------------------------------------------- #
def measure(rows):
    """The FIRST acknowledge's lead-in geometry, chip side.  -> dict or None."""
    cy, ak = ag.acks(rows)
    if not ak:
        return None
    ci, nlen = ak[0]
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
            "ncode_before": sum(1 for c in cy[:ci] if c[0] == CODE),
            "nhalt": sum(1 for c in cy if c[0] == HALT)}


# --------------------------------------------------------------------------- #
def cmd_run(args):
    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in args.waits.split(",") if x != ""]
    variants = [v for v in args.variants.split(",") if v]
    delays = list(range(args.d0, args.d0 + args.delays))
    if args.pilot:
        delays = delays[:6]
        waits = waits[:2]
    man = {"cell": "SM3 H1 -- the recognition boundary after a REDIRECT",
           "spec": "docs/notes/sm3_h1_prereg_2026-08-04.md sec.5",
           "prereg_commit": args.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "variants": variants,
           "delays": [delays[0], delays[-1]], "hold": args.hold, "cells": {}}
    man["div_guard"] = div_guard("sm3-h1cell")
    rows_out = []
    t0 = time.time()
    consec_err = 0
    for variant in variants:
        image, meta = image_of(variant)
        anchor = meta["anchor_linear"] if "anchor_linear" in meta else \
            (0 * 16 + PC0)
        for w in waits:
            for d in delays:
                key = f"{variant}:w{w}:d{d}"
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD,
                        evt=(anchor & 0xFFFFF, d, args.hold, 0),
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
                rec = {"key": key, "variant": variant, "waits": w, "delay": d,
                       "sha": sha, "fired": bool(fired), "nrows": len(rows),
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


def cmd_idle(args):
    import v30run
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)
    print("  board_idle: a single-NOP image captured on the socket -- OK")
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
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.set_defaults(fn=lambda a: (report(), 0)[1])
    p = sub.add_parser("idle")
    p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
