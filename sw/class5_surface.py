#!/usr/bin/env python3
"""Class-5 resume-law SURFACE census: map L as a function of (q_cnt(pred_T4),
empty_age) across many anchors + upstream WVEC perturbations at saturated N.
Completes the deadline arithmetic for the waited-resume RTL scheduler.

For each anchor, sweep upstream perturbations (holding predecessor N + addrs),
and for every resulting variant record the triple (pre-push q_cnt at pred T4,
empty_age = pred_T4 - clock(queue 1->0), chip L = successor_T1 - pred_T4).
Aggregate into a (q_cnt, age-bucket) -> {L} table. Chip = ground truth.
Usage: python3 sw/class5_surface.py --seeds ...
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import generate, compose, run_chip, accesses, CODE
from class5_factorW import find_anchor
from class5_factorQ import tb_acc, locate, chip_L
from class5_agesweep import set_pred_N, qcnt_row, empty_age


def collect(seed, host, image, nsat, span, out):
    anc = find_anchor(seed, host, image, 6, [3, 7])
    if anc is None:
        return
    pa, sa = anc["pred_addr"], anc["succ_addr"]
    base = list(anc["wv"])
    seen = set()
    # base + upstream single-access perturbations
    cands = [base]
    for j in range(max(0, anc["pred_bus"] - span), anc["pred_bus"]):
        for w in range(0, 8):
            wv = list(base); wv[j] = w
            cands.append(wv)
    n_conf = 0
    for wv in cands:
        wv2, i2, kr2, ka2 = set_pred_N(image, wv, pa, sa, nsat)
        if wv2 is None or wv2[i2 - 1] != nsat:
            continue
        q, av, _ = qcnt_row(kr2, ka2, i2)
        age = empty_age(kr2, ka2, i2)
        if q is None:
            continue
        key = (q, age, tuple(wv2[max(0, i2 - 14):i2]))
        if key in seen:
            continue
        seen.add(key)
        L, idle = chip_L(image, host, wv2, pa, sa)
        if L is None:
            continue
        out.append((seed, q, age, L))
        n_conf += 1
        if n_conf >= 40:   # cap chip runs per anchor
            break
    print(f"  fz{seed} {pa:05x}->{sa:05x}: {n_conf} points")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[90002, 90003, 90005, 90007, 90009, 90011, 90013])
    ap.add_argument("--nsat", type=int, default=6)
    ap.add_argument("--span", type=int, default=10)
    a = ap.parse_args()
    out = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        try:
            collect(seed, a.host, image, a.nsat, a.span, out)
        except Exception as e:
            print(f"  fz{seed}: ERR {e}")

    def agebucket(age):
        return "0-3" if age <= 3 else ("4+" if age < 99 else "never")

    print(f"\n=== {len(out)} (q_cnt, empty_age, L) points ===")
    print("\nL by (q_cnt, age-bucket):")
    tbl = defaultdict(list)
    for seed, q, age, L in out:
        tbl[(q, agebucket(age))].append(L)
    for key in sorted(tbl):
        Ls = tbl[key]
        from collections import Counter
        dist = " ".join(f"L{L}:{c}" for L, c in sorted(Counter(Ls).items()))
        print(f"   q_cnt={key[0]} age={key[1]:>5}: {dist}  (n={len(Ls)})")
    print("\nL by q_cnt (all ages):")
    byq = defaultdict(list)
    for seed, q, age, L in out:
        byq[q].append(L)
    for q in sorted(byq):
        from collections import Counter
        dist = " ".join(f"L{L}:{c}" for L, c in sorted(Counter(byq[q]).items()))
        print(f"   q_cnt={q}: {dist}  (n={len(byq[q])})")


if __name__ == "__main__":
    main()
