#!/usr/bin/env python3
"""sweep_regea - Campaign 5 fit: register-indirect / based-indexed EA
reader & store commit-phase matrix.

Same method as sweep_dispphase but for the mod0 register-indirect and
based-indexed EA forms newly exercised by the Campaign 5 addressing-mode
expansion. Measures the reader MEMR T1 / store MEMW T1 cycle index on
chip vs core across prefetch phases.

Usage: sweep_regea.py [--tb] [--phases 0-11] [--forms ...]
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
import sweep_popa as sp                             # reuse run_board/run_tb

TGT = 0x2482
BX0 = 0x2400
SI0 = 0x0082          # BX+SI = 0x2482
DI0 = 0x0082

FORMS = {
    # readers (MEMR T1 anchor)
    "rd_bx":    bytes([0x8B, 0x07]),             # MOV AX,[BX]        mod0 rm7
    "rd_bxsi":  bytes([0x8B, 0x00]),             # MOV AX,[BX+SI]     mod0 rm0
    "rd_si":    bytes([0x8B, 0x04]),             # MOV AX,[SI]        mod0 rm4
    "rd_di":    bytes([0x8B, 0x05]),             # MOV AX,[DI]        mod0 rm5
    "alurd_bx": bytes([0x03, 0x07]),             # ADD AX,[BX]        load-op
    # stores (MEMW T1 anchor)
    "st_bx":    bytes([0x89, 0x07]),             # MOV [BX],AX        mod0 rm7
    "st_bxsi":  bytes([0x89, 0x00]),             # MOV [BX+SI],AX
    "st_si":    bytes([0x89, 0x04]),             # MOV [SI],AX
    "st8_bx":   bytes([0x88, 0x07]),             # MOV [BX],AL  byte store
}
# rm7=[BX]: BX=TGT.  rm0=[BX+SI]: BX0+SI0=TGT.  rm4=[SI]: SI=TGT. rm5=[DI].


def build_image(form, phase):
    body = FORMS[form]
    # pick base regs so EA == TGT
    if form.endswith("bx") or form in ("st8_bx", "alurd_bx"):
        bw, si, di = TGT, SI0, DI0
    elif "bxsi" in form:
        bw, si, di = BX0, SI0, DI0
    elif form.endswith("si"):
        bw, si, di = BX0, TGT, DI0
    elif form.endswith("di"):
        bw, si, di = BX0, SI0, TGT
    else:
        bw, si, di = TGT, SI0, DI0
    instr = b"\x90" * phase + body + b"\x90" * 4
    regs = {"BW": bw, "IX": si, "IY": di, "AW": 0x1234,
            "SS": 0, "SP": 0x3F00, "DS0": 0, "DS1": 0, "PSW": 0xF202}
    ram = [(a, (a * 7 + 3) & 0xFF) for a in range(0x2400, 0x2500)]
    return testimage.compose(regs=regs, instr=instr, ram=ram)


def anchor_t1(recs, is_store):
    want = (2, 3) if is_store else (5, 6)   # MEMW vs MEMR bus status
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] in want and \
                (r["ad_addr"] & 0xFFFFF) == TGT:
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-11")
    ap.add_argument("--forms", default=",".join(FORMS))
    ap.add_argument("--tb", action="store_true")
    ap.add_argument("--out", default="/tmp/regea.tsv")
    a = ap.parse_args()
    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    forms = a.forms.split(",")

    rows = []
    print(f"{'form':9} {'ph':2} {'chipT1':6} {'coreT1':6} {'d':>3} "
          f"{'diff':>4} {'first':>5}")
    for form in forms:
        is_store = form.startswith("st")
        for ph in phases:
            image, _ = build_image(form, ph)
            chip = sp.run_board(image, a.host, False, 0)
            core = sp.run_tb(image, 0) if a.tb else \
                sp.run_board(image, a.host, True, 0)
            ct1 = anchor_t1(chip, is_store)
            kt1 = anchor_t1(core, is_store)
            bad, first, n, flick = sp.policy_diff(chip, core)
            d = (kt1 - ct1) if (ct1 is not None and kt1 is not None) else None
            print(f"{form:9} {ph:2} {str(ct1):6} {str(kt1):6} {str(d):>3} "
                  f"{bad:>4} {str(first):>5}"
                  + (f" [+{flick}fl]" if flick else ""))
            rows.append((form, ph, ct1, kt1, d, bad, first))
    ndiv = sum(1 for r in rows if r[5])
    print(f"\n{len(rows)} cells, {ndiv} divergent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
