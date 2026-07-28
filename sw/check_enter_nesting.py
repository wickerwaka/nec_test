#!/usr/bin/env python3
"""check_enter_nesting - standing gate for the task #31 ENTER nesting-mask fix.

Replays the board-frozen ENTER-nesting tranche (tests/v30/enter_nesting, nesting
0..255 x 2 BP/stack contexts) against the current-RTL Verilator core and asserts
the ENTER stack-frame WALK matches the chip golden exactly:

  * push/copy COUNT - the number of MEMW pushes and MEMR frame-pointer copies in
    the stack region (0x2000..0x3fff) equals the chip's (= the full 8-bit walk;
    a mod-32 mask would drop pushes for nesting>=32).
  * push/copy STREAM - the ordered (kind, addr, data) of every stack-region
    transaction matches the chip byte-for-byte.

PASS proves the core walks the full 8-bit nesting level like the chip across the
whole 0..255 range (the mask bug is gone) and the frame values are exact.
"""
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                        # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402

TRANCHE = SW.parent / "tests" / "v30" / "enter_nesting"
STK_LO, STK_HI = 0x2000, 0x3FFF


def stack_walk(rows):
    """Ordered stack-region (ENTER walk) MEMW/MEMR transactions."""
    out = []
    for tx in fc.extract_txns(rows):
        k = fc.KIND[tx["kind"]]
        if k in ("MEMW", "MEMR") and STK_LO <= (tx["addr"] & 0xFFFF) <= STK_HI:
            out.append([k, tx["addr"] & 0xFFFF, tx.get("data")])
    return out


def golden_walk(txns):
    return [[k, a, d] for k, a, d in txns if STK_LO <= a <= STK_HI]


def main():
    goldens = json.load(gzip.open(TRANCHE / "goldens.json.gz", "rt"))
    fails = []
    checked = 0
    max_push = 0
    for g in goldens:
        instr = (bytes([0xBD]) + int(g["bp"]).to_bytes(2, "little")
                 + bytes([0xC8]) + int(g["fsize"]).to_bytes(2, "little")
                 + bytes([g["nest"]]))
        image, meta = testimage.compose(regs={"BP": g["bp"], "SP": g["sp"]},
                                        instr=instr)
        rows = check_seq.run_tb(image, 4200, waits=0)
        tb = stack_walk(rows)
        chip = golden_walk(g["digest"]["txns"])
        checked += 1
        pushes = sum(1 for t in chip if t[0] == "MEMW")
        max_push = max(max_push, pushes)
        if tb != chip:
            tb_p = sum(1 for t in tb if t[0] == "MEMW")
            fails.append((g["ctx"], g["nest"], pushes, tb_p, len(chip), len(tb)))

    print(f"check_enter_nesting: {'PASS' if not fails else 'FAIL'} | "
          f"{checked} goldens (nesting 0..255 x2 ctx) | max stack pushes "
          f"{max_push} (nest=255 => 256) | walk-mismatches {len(fails)}")
    for ctx, nest, cp, tp, cn, tn in fails[:12]:
        print(f"  ctx{ctx} nest={nest}: chip pushes={cp} tb={tp} "
              f"(chip walk {cn} txns, tb {tn})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
