#!/usr/bin/env python3
"""sm3_h3_cell -- THE DIRECTED BOARD CELL for H3 CLASS B, exactly as
`ucore_provenance.md` §63.6 specifies it.

Spec and PRE-REGISTERED predictions:
`docs/notes/sm3_h7_h3_prereg_2026-08-04.md` §3.  Read it before running this;
the predictions were committed BEFORE the first board contact of the sitting.

WHAT IT ASKS.  §63.5 split `PF_LOST` in two and showed the bigger half is the
8080 landing pad, not arbitration.  What is left -- CLASS B, 221 seeds in the
model and 37 in the ucore -- has `delta = 0` on **184 of 221**: the two sides
open a cycle on the SAME CLOCK and disagree about WHOSE it is.  That is a
GRANT-ORDER SWAP, not a timing slip.  §63.6 tested the one candidate the work
order named -- chip-side queue occupancy at the contested slot -- and reported
it as a NEGATIVE result: the contested slots are skewed to a fuller queue
(186 of 221 at occ 3-5) but occ 0 through 5 all occur, so there is no single
threshold and M4's `occ + inflight <= 4` is not off by one.

§63.6's cells, verbatim: *"(a) a fixed instruction whose EU access is issued at
a known clock, with the queue pre-loaded to occ 0...6 in six otherwise
identical captures, at waits 0-3 -- this reads the grant priority as a function
of occupancy alone; (b) the same with the EU request arriving one clock EARLIER
and one clock LATER than the prefetcher's eligibility instant, which separates
'the chip's tie-break is prefetch-first' from 'the chip's EU request is one
clock later than modelled'.  Class A's own `delta = +2` says the second reading
has to be on the table."*

HOW THE QUEUE IS PRE-LOADED, and why this is a REAL sweep and not a fitted one.
There is no queue-preload port on the socket, so occupancy is set the way the
part itself sets it: every loop body opens with `EB 00` (a near JMP to the next
instruction), which FLUSHES the queue and starts a cold refill at a known
instant.  `PAD` filler bytes then separate that flush from the EU access, so
the prefetcher has run ahead by a different, MONOTONE amount when the EU asks
for the bus.  The achieved occupancy is not assumed -- it is MEASURED off the
capture's own `QS` port for every contested slot, by the same counting rule
§63.6 used (bytes delivered by CODE cycles that completed since the last
`QS = E`, minus the pops seen since).

THE THREE STIMULI -- cell (a) is the PAD sweep, cell (b) is the pair of
variants that move the EU's request instant either side of `mw`:

  mw     `EB 00` ; PAD x NOP ; `C6 06 disp16 ib`   MOV byte [disp16], imm8
         the baseline.  A MEMW, which is 106 of the model's 221 class-B cells.
  mwseg  the same with a `26` (ES:) segment-override prefix on the MOV.
         The override is decoded before the EA is formed, so the EU's bus
         request arrives LATER by the prefix's own cost, with the prefetcher's
         eligibility instant unchanged.
  mr     `EB 00` ; PAD x NOP ; `A0 disp16`         MOV AL, [disp16]
         a MEMR whose EA is an immediate displacement with no ModRM byte to
         decode, so the EU's request arrives EARLIER.

THE OBSERVABLE, read off the pins with no engine in the loop.  For each EU
access in the capture: the queue occupancy at its T1, whether the bus cycle
IMMEDIATELY BEFORE it was a CODE fetch, and the gap from that cycle's T1.  A
tie-break of "prefetch first" shows as a CODE fetch occupying the slot the EU
access could have had; the PAD sweep says whether that depends on occupancy.

NO PIN EVENT.  This cell is pure bus arbitration; `evt` is None and the only
axes are the stimulus, the pad and the wait class.

BOARD DISCIPLINE (CLAUDE.md).  Single-writer checked by the caller; SOCKET ONLY
(`use_core=False`); the divider PINNED and `div_guard`'s readback RECORDED; the
FULL per-clock rows retained beside the raw 64-bit words and their sha256;
`board_idle()` at the end; 5 consecutive transport errors STOP the cell.
NO FLASHING -- the board carries FLASH #4 and this cell does not use the core.

Usage:
    python3 sw/sm3_h3_cell.py run [--waits 0,1,2,3] [--pads 0,1,2,3,4,5,6,7]
    python3 sw/sm3_h3_cell.py report
    python3 sw/sm3_h3_cell.py idle
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

import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import sm3_ackgeom as ag                                # noqa: E402
import sm3_h1_cell as h1                                # noqa: E402
from gen_seq import (Prog, PC0, SP0, DATA_LO,           # noqa: E402
                     far_int_support)
from s10_board import capture, DIV_OF_RECORD            # noqa: E402
from s13_board import div_guard                         # noqa: E402
from t2b_board import HOST                              # noqa: E402
import emit_suite as es                                 # noqa: E402

assert es.EMIT_USE_CORE is False, "H3 cell refuses to run: truth is the socket"

OUT = ROOT / "sw" / "testdata" / "sm3-h3cell"
INTA, HALT, CODE, MEMR, MEMW, PASV = 0, 3, 4, 5, 6, 7
EU_KINDS = ("MEMR", "MEMW", "IOR", "IOW")
VARIANTS = ("mw", "mwseg", "mr")
# One fixed data address for every access, so the address never varies with the
# stimulus and cannot be confounded with it.
TGT = DATA_LO + 0x40


def program(variant, pad, n=24):
    """`instr` bytes: n copies of  EB 00 ; PAD x NOP ; <the EU access>."""
    p = Prog(random.Random(f"sm3-h3/{variant}/{pad}"))
    lo, hi = TGT & 0xFF, (TGT >> 8) & 0xFF
    if variant == "mw":
        acc = [0xC6, 0x06, lo, hi, 0x5A]
    elif variant == "mwseg":
        acc = [0x26, 0xC6, 0x06, lo, hi, 0x5A]
    elif variant == "mr":
        acc = [0xA0, lo, hi]
    else:
        raise SystemExit(f"unknown variant {variant}")
    for _ in range(n):
        p.emit([0xEB, 0x00])
        for _ in range(pad):
            p.emit([0x90])
        p.emit(acc)
    return p.assemble()


def image_of(variant, pad):
    rng = random.Random(f"sm3-h3img/{variant}/{pad}")
    instr = program(variant, pad)
    ivt, handler = far_int_support()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_LO + 0x200)]
    ram += handler
    image, meta = check_seq.compose(dict(seed=0, instr=instr, regs=regs,
                                         ram=ram, ivt=ivt))
    return image, meta


def occ_at(rows, cy, i):
    """Queue occupancy on row `i`, counted off the capture's own QS port by
    §63.6's rule: bytes delivered by CODE cycles that COMPLETED since the last
    `QS = E`, minus the pops (`QS` in {F, S}) seen since."""
    last_e = -1
    for j in range(i - 1, -1, -1):
        if rows[j]["qs"] == 2:
            last_e = j
            break
    base = max(0, last_e)
    delivered = sum(2 for c in cy if c[0] == CODE and c[2] < i and c[1] > base)
    pops = sum(1 for j in range(base + 1, i) if rows[j]["qs"] in (1, 3))
    return delivered - pops


def measure(rows):
    """Every EU access in the capture with its arbitration context."""
    n = len(rows)
    cy = ag.cycles(rows, n)
    out = []
    for k, c in enumerate(cy):
        kind = fc.BS_NAME[c[0]]
        if kind not in EU_KINDS:
            continue
        prev = cy[k - 1] if k > 0 else None
        if prev is None:
            continue
        pk = fc.BS_NAME[prev[0]]
        out.append({
            "i": k, "kind": kind, "t1": c[1], "disp": c[3],
            "addr": rows[c[1]]["ad_addr"] & 0xFFFFF,
            "prev_kind": pk, "prev_t1": prev[1],
            "prev_len": prev[2] - prev[1] + 1,
            "gap": c[1] - prev[1],
            "idle": c[3] - prev[2] - 1,
            "occ": occ_at(rows, cy, c[1]),
            # the tie-break question in one bit: did a CODE fetch take the
            # slot immediately ahead of this EU access?
            "prefetch_first": pk == "CODE",
        })
    return out


def cmd_run(args):
    OUT.mkdir(parents=True, exist_ok=True)
    waits = [int(x) for x in args.waits.split(",") if x != ""]
    pads = [int(x) for x in args.pads.split(",") if x != ""]
    variants = [v for v in args.variants.split(",") if v]
    man = {"cell": "SM3 H3 class B -- the grant-order swap, vs occupancy",
           "spec": "docs/notes/sm3_h7_h3_prereg_2026-08-04.md §3",
           "prereg_commit": args.prereg, "use_core": False, "host": HOST,
           "div": DIV_OF_RECORD, "waits": waits, "pads": pads,
           "variants": variants, "evt": None, "cells": {}}
    man["div_guard"] = div_guard("sm3-h3cell")
    recs = []
    t0 = time.time()
    consec_err = 0
    stop = False
    for variant in variants:
        if stop:
            break
        for pad in pads:
            if stop:
                break
            image, meta = image_of(variant, pad)
            for w in waits:
                key = f"{variant}:p{pad}:w{w}"
                try:
                    rows, raw, sha, fired = capture(
                        image, waits=w, div=DIV_OF_RECORD, evt=None,
                        tag="sm3h3")
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
                acc = measure(rows)
                rec = {"key": key, "variant": variant, "pad": pad, "waits": w,
                       "sha": sha, "fired": bool(fired), "nrows": len(rows),
                       "acc": acc}
                recs.append(rec)
                man["cells"][key] = {"sha": sha, "rows": len(rows),
                                     "naccess": len(acc)}
                stem = key.replace(":", "_")
                with gzip.open(OUT / f"{stem}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(OUT / f"{stem}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                occs = Counter(a["occ"] for a in acc)
                pf = sum(1 for a in acc if a["prefetch_first"])
                print(f"  {key}: {len(acc)} EU accesses, prefetch-first "
                      f"{pf}/{len(acc)}, occ {dict(sorted(occs.items()))} "
                      f"({time.time()-t0:.0f}s)", flush=True)
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
    print("\n  --- SM3 H3 class B directed cell: the grant order vs occupancy ---")
    print("  (PRE-REGISTERED, sm3_h7_h3_prereg_2026-08-04.md §3:"
          "  R1 the pad sweep MOVES the achieved occupancy;"
          "  R2 prefetch-first is a FUNCTION of occupancy alone;"
          "  R3 the two request-instant variants shift the same curve.)")
    print(f"\n  captures {len(recs)}, EU accesses "
          f"{sum(len(r['acc']) for r in recs)}")

    print("\n  R1 -- the pad sweep against the ACHIEVED occupancy "
          "(the sweep is real only if this moves):")
    print(f"  {'variant':<8}{'pad':>4}{'w':>3}   occupancy histogram at the EU T1")
    for r in sorted(recs, key=lambda x: (x["variant"], x["pad"], x["waits"])):
        occ = Counter(a["occ"] for a in r["acc"])
        print(f"  {r['variant']:<8}{r['pad']:>4}{r['waits']:>3}   "
              + " ".join(f"{k}:{v}" for k, v in sorted(occ.items())))

    print("\n  R2 -- prefetch-first, as a function of occupancy alone "
          "(pooled over pad, per variant and wait):")
    for variant in sorted({r["variant"] for r in recs}):
        for w in sorted({r["waits"] for r in recs}):
            tab = defaultdict(lambda: [0, 0])
            for r in recs:
                if r["variant"] != variant or r["waits"] != w:
                    continue
                for a in r["acc"]:
                    tab[a["occ"]][0] += 1
                    tab[a["occ"]][1] += 1 if a["prefetch_first"] else 0
            if not tab:
                continue
            print(f"    {variant:<8} w{w}  " + "  ".join(
                f"occ{k} {v[1]}/{v[0]}" for k, v in sorted(tab.items())))

    print("\n  R3 -- the EU request instant moved: the gap from the previous "
          "cycle's T1, per variant (a pure tie-break shows the SAME curve "
          "shifted, a late request shows a different one):")
    for variant in sorted({r["variant"] for r in recs}):
        for w in sorted({r["waits"] for r in recs}):
            grp = [a for r in recs if r["variant"] == variant
                   and r["waits"] == w for a in r["acc"]]
            if not grp:
                continue
            print(f"    {variant:<8} w{w}  prev kind "
                  + str(dict(Counter(a["prev_kind"] for a in grp)))
                  + "  gap " + str(dict(sorted(Counter(a["gap"] for a in grp)
                                               .items())[:8])))
    return 0


def cmd_score(args):
    """THE GRANT ORDER, chip vs engine, on the SAME captures.

    §63.6's family is defined by the two sides opening a cycle on the same
    clock and disagreeing about whose it is, so the tie-break is only readable
    by pairing.  The EU accesses are paired BY ORDINAL, which survives the row
    drift that starts at the first divergence."""
    import tempfile
    import timed_fuzz as tf
    recs = json.loads((OUT / "cells.json").read_text())
    tab = defaultdict(lambda: [0, 0])
    swaps = []
    for r in recs:
        image, meta = image_of(r["variant"], r["pad"])
        rows = json.load(gzip.open(
            OUT / f"{r['key'].replace(':', '_')}.rows.json.gz", "rt"))
        entry = {"waits": {"wrand": False, "fixed": r["waits"]}}
        with tempfile.TemporaryDirectory() as td:
            if args.core == "sim":
                erows, err = tf.run_sim(image, entry, len(rows), td, None)
            else:
                erows, err = tf.run_tb(image, entry, len(rows), td,
                                       args.core, None)
        eacc = measure(erows) if erows else []
        for k, ca in enumerate(r["acc"]):
            if k >= len(eacc):
                break
            ea = eacc[k]
            same = (ca["t1"] == ea["t1"] and ca["prev_kind"] == ea["prev_kind"])
            key = (r["variant"], r["waits"], ca["occ"])
            tab[key][0] += 1
            tab[key][1] += 1 if same else 0
            if not same and ca["t1"] == ea["t1"]:
                swaps.append((r["key"], k, ca["prev_kind"], ea["prev_kind"],
                              ca["occ"]))
    print(f"\n  --- engine `{args.core}` vs the H3 class-B captures, "
          f"grant order by ordinal ---")
    for v in sorted({k[0] for k in tab}):
        for w in sorted({k[1] for k in tab if k[0] == v}):
            cells = sorted((k[2], tab[k]) for k in tab
                           if k[0] == v and k[1] == w)
            print(f"    {v:<7} w{w}  " + "  ".join(
                f"occ{o} {c[1]}/{c[0]}" for o, c in cells))
    print(f"\n  SAME-CLOCK, DIFFERENT OWNER (the class-B signature): "
          f"{len(swaps)}")
    for s in swaps[:20]:
        print(f"    {s[0]} access#{s[1]}  chip prev={s[2]} eng prev={s[3]} "
              f"occ={s[4]}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--waits", default="0,1,2,3")
    r.add_argument("--pads", default="0,1,2,3,4,5,6,7")
    r.add_argument("--variants", default=",".join(VARIANTS))
    r.add_argument("--prereg", default="")
    sub.add_parser("report")
    s = sub.add_parser("score")
    s.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"))
    sub.add_parser("idle")
    a = ap.parse_args()
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "report":
        return report()
    if a.cmd == "score":
        return cmd_score(a)
    return h1.cmd_idle(a)


if __name__ == "__main__":
    sys.exit(main())
