#!/usr/bin/env python3
"""sweep_push - Campaign 5: stack-PUSH commit-phase matrix.
PUSH forms write to SS:SP-2. SP preset 0x3F00 -> first write at 0x3EFE.
"""
import argparse
import sys
from pathlib import Path
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
import sweep_popa as sp                             # noqa: E402

TGT = 0x3EFE

FORMS = {
    "push_ax":  bytes([0x50]),                    # PUSH AX      (r16)
    "push_bx":  bytes([0x53]),                    # PUSH BX
    "push_imm": bytes([0x68, 0x34, 0x12]),        # PUSH imm16
    "push_i8":  bytes([0x6A, 0x7F]),              # PUSH imm8
    "push_m":   bytes([0xFF, 0x36, 0x82, 0x24]),  # PUSH [0x2482] (mem)
}


def build_image(form, phase):
    instr = b"\x90" * phase + FORMS[form] + b"\x90" * 4
    regs = {"AW": 0x1111, "BW": 0x2222, "SS": 0, "SP": 0x3F00,
            "DS0": 0, "DS1": 0, "PSW": 0xF202}
    ram = [(a, (a * 5 + 1) & 0xFF) for a in range(0x2400, 0x2500)]
    ram += [(a, (a * 3 + 7) & 0xFF) for a in range(0x3E00, 0x3F80)]
    return testimage.compose(regs=regs, instr=instr, ram=ram)


def st_t1(recs):
    for i, r in enumerate(recs):
        if r.get("t") == 1 and r["bs_early"] in (5, 6) and \
                (r["ad_addr"] & 0xFFFFF) == TGT:
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-11")
    ap.add_argument("--forms", default=",".join(FORMS))
    ap.add_argument("--tb", action="store_true")
    a = ap.parse_args()
    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    bad = 0
    for form in a.forms.split(","):
        res = []
        for ph in phases:
            img, _ = build_image(form, ph)
            chip = sp.run_board(img, a.host, False, 0)
            core = sp.run_tb(img, 0) if a.tb else sp.run_board(img, a.host, True, 0)
            ct1 = st_t1(chip)
            kt1 = st_t1(core)
            b, f, n, fl = sp.policy_diff(chip, core)
            d = (kt1 - ct1) if (ct1 and kt1) else None
            if b:
                bad += 1
                res.append(f"ph{ph}(d={d},diff={b})")
        print(f"{form:9}: {'CLEAN' if not res else ' '.join(res)}")
    print("divergent cells:", bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
