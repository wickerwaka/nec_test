#!/usr/bin/env python3
"""OFFLINE alignment probe -- NO BOARD.  Selects a seed base on ALIGNMENT
COVERAGE ONLY (RC-2), by the rule fixed before it was run:

  candidates in order rep-cl0-rc1, rep-cl0-rc2, ...;  take the FIRST whose
  12 F3A5 images contain at least one doubly-odd (SI odd AND DI odd) image.

Nothing else is consulted.  gen_case is deterministic, so this is a pure
re-derivation of what the emitter would build.
"""
import random
import sys
sys.path.insert(0, "/home/wickerwaka/src/nec_test/sw")
import emit_suite as es

FORCE_CX = [255, 256, 257]
FORCE_DF = [0, 1]
NCASES = 12


def images(seed_base, op):
    spec = es.OPCODES[op]
    out = []
    for idx in range(NCASES):
        # mirrors cmd_emit's no-reroll path: attempt i == output index
        rng = random.Random(f"{seed_base}/{op}/{idx}")
        fcx, fdf = es._forced_cell(idx, FORCE_CX, FORCE_DF)
        try:
            c = es.gen_case(spec, rng, force_cx=fcx, force_df=fdf)
        except Exception as e:                       # noqa: BLE001
            out.append((idx, fcx, fdf, None, None, None, None,
                        f"{type(e).__name__}: {e}"))
            continue
        r = c["regs"]
        si, di = r["si"], r["di"]
        sl = ((r["ds"] << 4) + si) & 0xFFFFF
        dl = ((r["es"] << 4) + di) & 0xFFFFF
        out.append((idx, fcx, fdf, si, di, sl, dl, ""))
    return out


for n in range(1, 40):
    base = f"rep-cl0-rc{n}"
    rows = images(base, "F3A5")
    dodd = [r[0] for r in rows if r[3] is not None and (r[3] & 1) and (r[4] & 1)]
    err = [r for r in rows if r[7]]
    print(f"{base}: doubly-odd idx={dodd}  gen_errors={len(err)}")
    if dodd:
        print(f"\nSELECTED (first with >=1 doubly-odd): {base}\n")
        for op in ("F3A4", "F3A5"):
            print(f"--- {op} ---")
            print(" idx  cx   df   SI     DI     SIlin   DIlin   align")
            for (idx, fcx, fdf, si, di, sl, dl, e) in images(base, op):
                if e:
                    print(f" {idx:3d}  ERROR {e}")
                    continue
                a = ("odd" if sl & 1 else "even") + "/" + \
                    ("odd" if dl & 1 else "even")
                print(f" {idx:3d}  {fcx:3d}  {fdf}   {si:04x}   {di:04x}   "
                      f"{sl:05x}   {dl:05x}   {a}")
        break
