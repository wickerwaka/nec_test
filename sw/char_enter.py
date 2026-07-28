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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
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
