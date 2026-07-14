#!/usr/bin/env python3
"""sweep_loop - flush-modeling fit: LOOP-taken doomed-prefetch matrix.

A backward LOOP (E0/E1/E2) taken flushes the queue and redirects the
fetch pointer to the branch target. The chip issues ONE doomed
speculative fall-through prefetch during the flush that the core may not
model; the flush/redirect + QS=E display timing is prefetch-phase
dependent. This tool runs a self-contained single-taken backward loop
across NOP prefetch phases on chip vs TB (or fabric), reporting the
target-fetch T1 index, QS=E display index, and the per-cycle diff.

Micro-sequence at the anchor (PS=0, PC=0x0100):
  N*NOP (phase) | MOV CX,2 | tgt: <body NOPs> | LOOP disp | 4*NOP | stub
CX=2 => LOOP taken exactly once (CX 2->1 taken, 1->0 fall-through).

Usage:
  sweep_loop.py [--tb] [--phases 0-15] [--op e2|e1|e0] [--body 1]
  sweep_loop.py fz-style single-phase dump with --dump PH
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
import sweep_popa as sp                             # reuse run_board/run_tb

OPS = {"e0": 0xE0, "e1": 0xE1, "e2": 0xE2}


def build_image(phase, op=0xE2, body=1):
    # body must not touch CW (the loop counter); use NOPs so timing is clean
    bodyb = b"\x90" * body
    disp = (-(body + 2)) & 0xFF                     # back to tgt (LOOP is 2B)
    instr = (b"\x90" * phase +
             b"\xB9\x02\x00" +                       # MOV CX,2
             bodyb +
             bytes([op, disp]) +
             b"\x90" * 4)
    regs = {"AW": 0x1111, "BW": 0x2222, "SS": 0, "SP": 0x3F00,
            "DS0": 0, "DS1": 0, "PSW": 0xF202}
    ram = [(a, (a * 3 + 7) & 0xFF) for a in range(0x3E00, 0x3F80)]
    img, meta = testimage.compose(regs=regs, instr=instr, ram=ram)
    # linear address of the loop target (body start)
    tgt = (meta["anchor_linear"] + phase + 3) & 0xFFFFF
    loop_at = (tgt + body) & 0xFFFFF
    return img, tgt, loop_at


def first_code_t1_at(recs, addr):
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] == 4 and \
                (r["ad_addr"] & 0xFFFFF) == (addr & 0xFFFFF):
            return i
    return None


def qs_e_idx(recs, after=0):
    for i, r in enumerate(recs):
        if i >= after and r.get("qs") == 2:      # QS=E
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-15")
    ap.add_argument("--op", default="e2")
    ap.add_argument("--body", type=int, default=1)
    ap.add_argument("--tb", action="store_true")
    a = ap.parse_args()
    op = OPS[a.op]
    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)

    ndiv = 0
    print(f"op={a.op} body={a.body}")
    print(f"{'ph':2} {'tgtT1c':6} {'tgtT1k':6} {'d':>3} "
          f"{'qsEc':5} {'qsEk':5} {'diff':>4} {'first':>5}")
    for ph in phases:
        img, tgt, loop_at = build_image(ph, op, a.body)
        chip = sp.run_board(img, a.host, False, 0)
        core = sp.run_tb(img, 0) if a.tb else sp.run_board(img, a.host, True, 0)
        # the branch resolves near the LOOP fetch; target T1 is the redirect
        ct1 = first_code_t1_at(chip, tgt)
        kt1 = first_code_t1_at(core, tgt)
        # QS=E after the loop-instruction region
        qc = qs_e_idx(chip)
        qk = qs_e_idx(core)
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
