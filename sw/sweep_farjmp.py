#!/usr/bin/env python3
"""sweep_farjmp - flush-modeling fit: far JMP (EA) queue-flush/refetch matrix.

Far JMP (EA off16 seg16) reloads PS:PC and flushes the prefetch queue; the
fall-through prefetch in flight is doomed and the redirect commits (EA uses
the mid-cycle flush_fast path). This runs a contained far JMP to (0,
fall-through) across NOP prefetch phases on chip vs TB, reporting the
redirect target-fetch T1 index and the per-cycle diff.

Micro-sequence at the anchor (PS=0, PC=0x0100):
  N*NOP (phase) | EA <off=anchor+N+5> <seg=0> | 6*NOP | stub
The target is the byte right after EA (a contained CS reload continuing the
stream, like gen_seq _gen_farjmp) so the program reaches the store stub.
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
import sweep_popa as sp                             # reuse run_board/run_tb


def build_image(phase, seg=0):
    anchor = 0x0100
    ea_at = anchor + phase
    tgt_off = ea_at + 5                              # fall-through past EA
    tgt_lin = (seg << 4) + tgt_off
    instr = (b"\x90" * phase +
             bytes([0xEA, tgt_off & 0xFF, tgt_off >> 8, seg & 0xFF, seg >> 8]) +
             b"\x90" * 6)
    regs = {"AW": 0x1111, "SS": 0, "SP": 0x3F00, "DS0": 0, "DS1": 0,
            "PSW": 0xF202}
    ram = [(a, (a * 3 + 7) & 0xFF) for a in range(0x3E00, 0x3F80)]
    img, meta = testimage.compose(regs=regs, instr=instr, ram=ram)
    return img, tgt_lin & 0xFFFFF


def first_code_t1_at(recs, addr):
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] == 4 and \
                (r["ad_addr"] & 0xFFFFF) == (addr & 0xFFFFF):
            return i
    return None


def qs_e_idx(recs):
    for i, r in enumerate(recs):
        if r.get("qs") == 2:
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-15")
    ap.add_argument("--seg", default="0")
    ap.add_argument("--tb", action="store_true")
    a = ap.parse_args()
    seg = int(a.seg, 0)
    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    ndiv = 0
    print(f"seg={seg:#x}")
    print(f"{'ph':2} {'tgtT1c':6} {'tgtT1k':6} {'d':>3} "
          f"{'qsEc':5} {'qsEk':5} {'diff':>4} {'first':>5}")
    for ph in phases:
        img, tgt = build_image(ph, seg)
        chip = sp.run_board(img, a.host, False, 0)
        core = sp.run_tb(img, 0) if a.tb else sp.run_board(img, a.host, True, 0)
        ct1 = first_code_t1_at(chip, tgt)
        kt1 = first_code_t1_at(core, tgt)
        qc, qk = qs_e_idx(chip), qs_e_idx(core)
        bad, first, n, flick = sp.policy_diff(chip, core)
        d = (kt1 - ct1) if (ct1 is not None and kt1 is not None) else None
        if bad:
            ndiv += 1
        print(f"{ph:2} {str(ct1):6} {str(kt1):6} {str(d):>3} "
              f"{str(qc):5} {str(qk):5} {bad:>4} {str(first):>5}"
              + (f" [+{flick}fl]" if flick else ""))
    print(f"\n{len(list(phases))} phases, {ndiv} divergent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
