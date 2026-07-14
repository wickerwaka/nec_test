#!/usr/bin/env python3
"""sweep_swint - flush-modeling fit: software-INT (CC/CD/CE) vectoring matrix.

A software interrupt (INT3 CC / INTn CD ib / INTO CE) pushes PSW:PS:PC,
reads the IVT vector, flushes the queue and refetches at the handler. The
fall-through prefetch in flight is doomed by the vectoring flush; the
handler-fetch redirect + QS=E timing is prefetch-phase dependent. This
runs each form across NOP prefetch phases on chip vs TB, reporting the
handler-entry fetch T1 index and the per-cycle diff.

Handler at 0x0480 = IRET (CF), so each INT returns to the following
instruction and the stream continues to the store stub. IVT vectors
3 (INT3), the CD immediate, and 4 (INTO) all point at the handler.
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
import sweep_popa as sp                             # reuse run_board/run_tb

HANDLER = 0x0480
VEC = 0x20                       # CD immediate vector

FORMS = {
    "int3": bytes([0xCC]),               # -> vector 3
    "intn": bytes([0xCD, VEC]),          # -> vector 0x20
    "into": bytes([0xCE]),               # -> vector 4 (OF set below)
}


def build_image(form, phase):
    instr = b"\x90" * phase + FORMS[form] + b"\x90" * 4
    # OF set (PSW bit 11) so INTO vectors; IE cleared is fine (software INT)
    psw = 0xF202 | (0x0800 if form == "into" else 0)
    regs = {"AW": 0x1111, "SS": 0, "SP": 0x3F00, "DS0": 0, "DS1": 0,
            "PSW": psw}
    ram = [(HANDLER, 0xCF)]                          # IRET
    ram += [(a, (a * 3 + 7) & 0xFF) for a in range(0x3E00, 0x3F80)]
    ivt = {3: (0, HANDLER), VEC: (0, HANDLER), 4: (0, HANDLER)}
    img, meta = testimage.compose(regs=regs, instr=instr, ram=ram, ivt=ivt)
    return img


def handler_t1(recs):
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] == 4 and \
                (r["ad_addr"] & 0xFFFFF) == HANDLER:
            return i
    return None


def qs_e_idx(recs):
    return next((i for i, r in enumerate(recs) if r.get("qs") == 2), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-15")
    ap.add_argument("--forms", default=",".join(FORMS))
    ap.add_argument("--tb", action="store_true")
    a = ap.parse_args()
    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    total_div = 0
    for form in a.forms.split(","):
        ndiv = 0
        print(f"== {form} ==")
        print(f"{'ph':2} {'hT1c':5} {'hT1k':5} {'d':>3} "
              f"{'qEc':4} {'qEk':4} {'diff':>4} {'first':>5}")
        for ph in phases:
            img = build_image(form, ph)
            chip = sp.run_board(img, a.host, False, 0)
            core = sp.run_tb(img, 0) if a.tb else \
                sp.run_board(img, a.host, True, 0)
            ct1, kt1 = handler_t1(chip), handler_t1(core)
            qc, qk = qs_e_idx(chip), qs_e_idx(core)
            bad, first, n, flick = sp.policy_diff(chip, core)
            d = (kt1 - ct1) if (ct1 is not None and kt1 is not None) else None
            if bad:
                ndiv += 1
            print(f"{ph:2} {str(ct1):5} {str(kt1):5} {str(d):>3} "
                  f"{str(qc):4} {str(qk):4} {bad:>4} {str(first):>5}"
                  + (f" [+{flick}fl]" if flick else ""))
        total_div += ndiv
        print(f"  {form}: {ndiv} divergent\n")
    print(f"total divergent cells: {total_div}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
