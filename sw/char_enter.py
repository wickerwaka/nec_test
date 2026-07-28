#!/usr/bin/env python3
"""char_enter - directed board characterization of ENTER/PREPARE (0xC8) nesting
levels 0..255 x BP/stack contexts (task #31). The V30 does NOT mask the nesting
level (full 8-bit stack-frame walk); the fabric core masked it mod 32 (fixed in
v30_eu.sv). Captures the CHIP (use_core=False) golden ENTER bus-transaction
digest per case and freezes tests/v30/enter_nesting/{goldens.json.gz,
metadata.json}. Standing gate: sw/check_enter_nesting.py.

    python3 sw/char_enter.py --freeze          # capture + freeze (board)
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                        # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402

OUT = SW.parent / "tests" / "v30" / "enter_nesting"
# BP/SP contexts: BP relative to the stack window so the frame-pointer walk reads
# valid in-image memory; framesize varied too.
CONTEXTS = [
    {"BP": 0x3FE0, "SP": 0x3F00, "fsize": 0x0010},
    {"BP": 0x3FA0, "SP": 0x3E80, "fsize": 0x0000},
]

# --- waited tranche (task #31 second ENTER bug: PUSH-BP drop under waits) -------
# The mask tranche (goldens.json.gz) is w0-only and blind to the wait-triggered
# BP-push drop. The waited tranche captures the chip ENTER at several uniform
# waits + a wrand slice, over a nesting set covering the value-bug (nest 0), the
# walk shapes (1..5), and the mask boundary (31/32/63). High nesting is dropped
# from the waited set so even the w7 traces fit the 4200-row window.
NST_WAITED = [0, 1, 2, 3, 4, 5, 8, 16, 31, 32, 63]
WAITS_FIXED = [0, 1, 2, 3, 7]
WRAND_SLICE = [(3, 0x1234), (7, 0x5678)]     # (wmax, wseed)
STK_LO, STK_HI = 0x2000, 0x3FFF
TB_WINDOW = 4200


def full_txns(rows, anchor16):
    """Ordered bus transactions from the TEST-INSTRUCTION anchor (the first CODE
    fetch at anchor16, i.e. after the reg-load preamble far-jumps to PS:PC and
    flushes the queue) to the end, each as [kind, addr16, data, duration].
    Captures the whole bus schedule (identity + length + order) - the cycle-
    exactness signal, robust to the reset/preamble region address artifact and to
    the t=0/t=1 fetch phase (extract_txns is T1-keyed). Anchoring on the flushed
    test entry, not linear 0, drops the preamble (which is chip/TB-identical here
    anyway but carries the reset-region addressing artifact)."""
    out, started = [], False
    for tx in fc.extract_txns(rows):
        k = fc.KIND[tx["kind"]]
        a = tx["addr"] & 0xFFFF
        if not started:
            if k == "CODE" and a == (anchor16 & 0xFFFF):
                started = True
            else:
                continue
        out.append([k, a, tx.get("data"), tx.get("end", tx["start"]) - tx["start"]])
    return out


def walk_of(txns):
    """Stack-region MEMW/MEMR subset of a full-txn list (the ENTER walk). This is
    the value-bug invariant: a dropped BP push removes a MEMW; it holds at EVERY
    wait (the w2 nest>=1 prefetch interleave only moves a CODE fetch, not the
    walk)."""
    return [[k, a, d] for k, a, d, _dur in txns
            if k in ("MEMW", "MEMR") and STK_LO <= a <= STK_HI]


def active_count(rows):
    """Number of active bus cycles (T1 rows with a real bus status). Pins the
    total bus-busy schedule alongside full_txns."""
    return sum(1 for r in rows
               if fc._tstate(r) == 1 and r["bs_early"] != 7)


def enter_case_instr(bp, fsize, nest):
    return (bytes([0xBD]) + int(bp).to_bytes(2, "little")
            + bytes([0xC8]) + int(fsize).to_bytes(2, "little")
            + bytes([nest]))


def capture_waited(host):
    """Waited + wrand ENTER goldens: full bus digest per (ctx, nest, wait)."""
    goldens = []
    t0 = time.time()
    plan = ([("fixed", w) for w in WAITS_FIXED]
            + [("wrand", wr) for wr in WRAND_SLICE])
    total = len(CONTEXTS) * len(NST_WAITED) * len(plan)
    for ci, ctx in enumerate(CONTEXTS):
        for nest in NST_WAITED:
            instr = enter_case_instr(ctx["BP"], ctx["fsize"], nest)
            regs = {"BP": ctx["BP"], "SP": ctx["SP"]}
            image, meta = testimage.compose(regs=regs, instr=instr)
            anchor16 = meta["anchor_linear"] & 0xFFFF
            for kind, wp in plan:
                if kind == "fixed":
                    rows = check_seq.run_chip(image, host, use_core=False, waits=wp)
                    wf = {"waits": wp}
                else:
                    wmax, wseed = wp
                    rows = check_seq.run_chip(image, host, use_core=False,
                                              wrand=(wmax, wseed))
                    wf = {"wrand": [wmax, wseed]}
                ft = full_txns(rows, anchor16)
                g = {"ctx": ci, "nest": nest, "fsize": ctx["fsize"],
                     "bp": ctx["BP"], "sp": ctx["SP"], "anchor16": anchor16,
                     "full": ft, "active": active_count(rows)}
                g.update(wf)
                goldens.append(g)
                if len(goldens) % 32 == 0:
                    OUT.mkdir(parents=True, exist_ok=True)
                    (OUT / "heartbeat_waited.json").write_text(json.dumps(
                        {"done": len(goldens), "total": total,
                         "rate": round(len(goldens) / (time.time() - t0), 2)}))
    return goldens


def digest(rows):
    """The ENTER's observable bus stream: ordered (kind, addr16, data) for every
    MEMW/MEMR transaction, plus the active-cycle span. Push count = #MEMW."""
    txns = []
    for tx in fc.extract_txns(rows):
        k = fc.KIND[tx["kind"]]
        if k in ("MEMW", "MEMR"):
            txns.append([k, tx["addr"] & 0xFFFF, tx.get("data")])
    memw = sum(1 for t in txns if t[0] == "MEMW")
    memr = sum(1 for t in txns if t[0] == "MEMR")
    last_active = max((i for i, r in enumerate(rows)
                       if fc._tstate(r) == 1 and r["bs_early"] != 7), default=0)
    return {"txns": txns, "memw": memw, "memr": memr, "span": last_active}


def capture(host, window=4200):
    goldens = []
    t0 = time.time()
    for ci, ctx in enumerate(CONTEXTS):
        for nest in range(256):
            instr = (bytes([0xBD]) + ctx["BP"].to_bytes(2, "little")   # MOV BP,imm
                     + bytes([0xC8]) + ctx["fsize"].to_bytes(2, "little")
                     + bytes([nest]))                                  # ENTER
            regs = {"BP": ctx["BP"], "SP": ctx["SP"]}
            image, meta = testimage.compose(regs=regs, instr=instr)
            rows = check_seq.run_chip(image, host, use_core=False)
            goldens.append({"ctx": ci, "nest": nest, "fsize": ctx["fsize"],
                            "bp": ctx["BP"], "sp": ctx["SP"],
                            "digest": digest(rows)})
            if (len(goldens)) % 64 == 0:
                (OUT).mkdir(parents=True, exist_ok=True)
                (OUT / "heartbeat.json").write_text(json.dumps(
                    {"done": len(goldens), "total": 256 * len(CONTEXTS),
                     "rate": round(len(goldens) / (time.time() - t0), 2)}))
    return goldens


def main_waited(host, freeze):
    goldens = capture_waited(host)
    # sanity: chip pushes nest+1 regardless of waits (the bug fix's invariant)
    bad = []
    for g in goldens:
        pushes = sum(1 for k, a, d in walk_of(g["full"]) if k == "MEMW")
        if pushes != g["nest"] + 1:
            bad.append(g)
    print(f"captured {len(goldens)} WAITED ENTER goldens; "
          f"chip push==nest+1 mismatches: {len(bad)}")
    for g in bad[:8]:
        wf = g.get("waits", g.get("wrand"))
        print(f"  ctx{g['ctx']} nest={g['nest']} w={wf} "
              f"memw={sum(1 for k,a,d in walk_of(g['full']) if k=='MEMW')}")
    if freeze:
        OUT.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT / "goldens_waited.json.gz", "wt") as f:
            json.dump(goldens, f)
        (OUT / "metadata_waited.json").write_text(json.dumps({
            "experiment": "ENTER/PREPARE (0xC8) under WAIT states - the task #31 "
                          "PUSH-BP-drop fix. Nesting set x fixed waits {0,1,2,3,7} "
                          "+ a wrand slice x 2 BP/stack contexts.",
            "rig": "sw/char_enter.py --waited", "truth_source": "SOCKET "
                   "(use_core=False)",
            "finding": "The fabric ENTER dropped its initial PUSH BP under >=2 "
                       "waits (S_PREP_L consumed the level byte / started the walk "
                       "before the BP push was accepted). Fixed by gating pop_want "
                       "on (prep_acc||eu_started) in v30_eu.sv. The chip pushes "
                       "nest+1 at every wait.",
            "nesting_set": NST_WAITED, "waits_fixed": WAITS_FIXED,
            "wrand_slice": WRAND_SLICE, "contexts": CONTEXTS,
            "checks": {
                "walk_stream_strict": "stack-region MEMW/MEMR (kind,addr,data,"
                    "order) == chip at ALL waits (the value-bug invariant)",
                "cycle_exact": "full txn stream (kind,addr,data,dur)+active count "
                    "== chip; STRICT at ALL waits and all nesting in this "
                    "compose-harness tranche (measured: 0 divergences)"},
            "known_divergences": [],
            "note_33": "A wait-count-dependent ENTER-walk-vs-prefetch INTERLEAVE "
                       "exists but is LAYOUT-SPECIFIC and does NOT appear in this "
                       "compose-harness tranche (verified cycle-exact everywhere "
                       "here). It reproduces in a DIRECTED harness (MOV SP,0x3f00; "
                       "MOV BP,0x3fe0; ENTER; NOP-sled at PS:PC=0:0x500): at w2 the "
                       "chip holds the bus through the whole ENTER walk before the "
                       "next-opcode prefetch, while the fixed core lets ONE CODE "
                       "prefetch in between the BP push and the walk (w1 chip "
                       "prefetches mid-walk, w3+ does not - only w2 differs). Walk/ "
                       "value identical; a clean prefetch-arbitration cadence "
                       "datapoint booked to #33 (see docs/notes/t31_rootcause.md).",
            "date": "2026-07-28"}, indent=1))
        print(f"froze {len(goldens)} waited goldens -> {OUT}")
    _leave_idle(host)
    return 1 if bad else 0


def _leave_idle(host):
    try:
        img, _ = testimage.compose(regs={}, instr=bytes([0x90]))
        check_seq.run_chip(img, host, use_core=False)
        print("board left use_core=0")
    except Exception:                                       # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--waited", action="store_true",
                    help="capture the waited+wrand tranche (goldens_waited.json.gz)")
    a = ap.parse_args()
    if a.waited:
        return main_waited(a.host, a.freeze)
    goldens = capture(a.host)
    # sanity: chip must NOT mask - push count == nest+1 across the board
    bad = [g for g in goldens if g["digest"]["memw"] != g["nest"] + 1]
    print(f"captured {len(goldens)} ENTER goldens; "
          f"chip push==nest+1 mismatches: {len(bad)}")
    for g in bad[:8]:
        print(f"  ctx{g['ctx']} nest={g['nest']} memw={g['digest']['memw']}")
    if a.freeze:
        OUT.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT / "goldens.json.gz", "wt") as f:
            json.dump(goldens, f)
        (OUT / "metadata.json").write_text(json.dumps({
            "experiment": "ENTER/PREPARE (0xC8) nesting 0..255 x 2 BP/stack "
                          "contexts - the full 8-bit stack-frame walk",
            "rig": "sw/char_enter.py", "truth_source": "SOCKET (use_core=False)",
            "finding": "The V30 does NOT mask the ENTER nesting level: pushes = "
                       "nesting+1 for all 0..255 (BP + level-1 frame-pointer "
                       "copies + FrameTemp). The fabric core masked it mod 32 "
                       "(pushes=(nest&0x1f)+1) - fixed in v30_eu.sv (a4_k full "
                       "8-bit, no [4:0] mask). a4_k/a4_cnt were already 8-bit "
                       "SS-mapped flops, so no savestate widening.",
            "n_goldens": len(goldens), "contexts": CONTEXTS,
            "worst_case": "nest=255 -> 256 MEMW pushes; fits the 4200-row w0 "
                          "window (verified ~4199 rows).",
            "date": "2026-07-27"}, indent=1))
        print(f"froze {len(goldens)} goldens -> {OUT}")
    # leave board on the chip
    try:
        img, _ = testimage.compose(regs={}, instr=bytes([0x90]))
        check_seq.run_chip(img, a.host, use_core=False)
        print("board left use_core=0")
    except Exception:                                       # noqa: BLE001
        pass
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
