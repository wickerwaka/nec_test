#!/usr/bin/env python3
"""Class-5 starvation-AGE experiment (Codex's decisive q0-collision resolver).

The q0 collision (q_cnt(pred_T4)=0 gives both L=2 and L=4) implies a second
demand-state: how long ago the queue emptied. Hold q_cnt(pred_T4)=0 and the local
geometry fixed, vary only empty_age = pred_T4 - clock(queue 1->0), and measure the
chip's resume L. If L follows empty_age (newly empty -> scheduled later L=4;
long-empty -> demand overdue -> immediate L=2), the deadline event is the
queue-empty transition and the RTL needs a demand-age latch.

Search over upstream WVEC perturbations (TB, fast) keeping q_cnt(pred_T4)==0;
group survivors by reconstructed empty_age; confirm chip L. Chip = ground truth.
Usage: python3 sw/class5_agesweep.py --seeds 90002 90003 90005 ...
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, BSN, CODE)
from class5_factorW import find_anchor
from class5_factorQ import tb_acc, locate, chip_L


def qcnt_row(kr, ka, i):
    t4 = ka[i - 1]["t4"]
    return (kr[t4]["q_cnt"], kr[t4].get("q_avl", -1), t4) if t4 is not None else (None, None, None)


def empty_age(kr, ka, i):
    """clocks from the last q_cnt 1->0 transition to pred_T4."""
    t4 = ka[i - 1]["t4"]
    if t4 is None:
        return None
    for r in range(t4, 0, -1):
        if kr[r]["q_cnt"] == 0 and kr[r - 1]["q_cnt"] >= 1:
            return t4 - r
    # queue was 0 for the whole visible window
    return 99


def set_pred_N(image, wv, pred_addr, succ_addr, N):
    kr, ka = tb_acc(image, wv)
    i = locate(ka, pred_addr, succ_addr)
    if i is None:
        return None, None, None, None
    wv2 = list(wv); wv2[i - 1] = N
    kr2, ka2 = tb_acc(image, wv2)
    i2 = locate(ka2, pred_addr, succ_addr)
    if i2 is None:
        return None, None, None, None
    return wv2, i2, kr2, ka2


def try_anchor(seed, host, image, nsat, span, out):
    anc = find_anchor(seed, host, image, 6, [3, 7])
    if anc is None:
        return
    pa, sa = anc["pred_addr"], anc["succ_addr"]
    wv0, i0, kr0, ka0 = set_pred_N(image, list(anc["wv"]), pa, sa, nsat)
    if wv0 is None:
        return
    q0, av0, _ = qcnt_row(kr0, ka0, i0)
    if q0 != 0:
        return  # only q_cnt=0 anchors for the starvation-age sweep
    print(f"  fz{seed} q0 anchor {pa:05x}->{sa:05x} (base age="
          f"{empty_age(kr0, ka0, i0)})")
    variants = {}   # empty_age -> wv (dedup)
    variants[empty_age(kr0, ka0, i0)] = wv0
    base = list(anc["wv"])
    for j in range(max(0, i0 - 1 - span), i0 - 1):
        for w in range(0, 8):
            wv = list(base); wv[j] = w
            wv2, i2, kr2, ka2 = set_pred_N(image, wv, pa, sa, nsat)
            if wv2 is None or wv2[i2 - 1] != nsat:
                continue
            q, av, _ = qcnt_row(kr2, ka2, i2)
            if q != 0:
                continue          # hold q_cnt(T4)=0
            age = empty_age(kr2, ka2, i2)
            if age not in variants:
                variants[age] = wv2
    for age in sorted(variants):
        L, idle = chip_L(image, host, variants[age], pa, sa)
        if L is None:
            continue
        out.append((seed, age, L))
        print(f"    empty_age={age}: chip L={L} (idle {idle})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[90002, 90003, 90005, 90007, 90013, 90015])
    ap.add_argument("--nsat", type=int, default=6)
    ap.add_argument("--span", type=int, default=12)
    a = ap.parse_args()
    out = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        try:
            try_anchor(seed, a.host, image, a.nsat, a.span, out)
        except Exception as e:
            print(f"  fz{seed}: ERR {e}")
    print("\n=== L vs empty_age (all q_cnt(T4)=0) ===")
    by = defaultdict(list)
    for seed, age, L in out:
        by[age].append(L)
    for age in sorted(by):
        Ls = by[age]
        print(f"   empty_age={age}: L in {sorted(set(Ls))} (n={len(Ls)})")


if __name__ == "__main__":
    main()
