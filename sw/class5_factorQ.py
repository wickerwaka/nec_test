#!/usr/bin/env python3
"""Class-5 Factor-Q: controlled q_cnt(pred_T4) boundary intervention (Codex's
decisive class-5 experiment). Tests whether the resume floor/delay follows the
queue-fill boundary (queue-demand-deadline) or is confounded with consumption.

At a fixed CODE->CODE resume anchor, hold the predecessor wait N and the
predecessor/successor addresses FIXED, and perturb UPSTREAM waits (via WVEC) to
move the reconstructed q_cnt at the predecessor's T4 across 2<->3. Measure the
chip's L = successor_T1 - predecessor_T4 for each achievable q_cnt. If L follows
q_cnt (q3->5, q2->4) the boundary is causal; if the same q_cnt yields both L, it
is history-latched.

Search is TB-only (fast); survivors are confirmed on the chip. The predecessor is
located by ADDRESS each run (upstream waits can shift its bus-order index). Chip
= ground truth. Usage: python3 sw/class5_factorQ.py --seed 90011 [--nsat 6]
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _sname, BSN, CODE)
from class5_factorW import find_anchor


def tb_acc(image, wv):
    kr = run_tb_internal(image, 4200, wv)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    return kr, ka


def locate(ka, pred_addr, succ_addr):
    """index i of the successor s.t. ka[i-1] is CODE@pred_addr and ka[i] is
    CODE@succ_addr (first such consecutive pair)."""
    for i in range(1, len(ka)):
        if (ka[i - 1]["bs"] == CODE and ka[i - 1]["addr"] == pred_addr
                and ka[i]["bs"] == CODE and ka[i]["addr"] == succ_addr):
            return i
    return None


def qcnt_at_predT4(kr, ka, i):
    t4 = ka[i - 1]["t4"]
    return kr[t4]["q_cnt"] if t4 is not None else None


def set_pred_N(image, wv, pred_addr, succ_addr, N):
    """Two-pass: locate predecessor by addr, set its WVEC slot to N, return the
    adjusted wv and the located index (or None)."""
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


def chip_L(image, host, wv, pred_addr, succ_addr):
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    ca = accesses(crel)
    i = locate(ca, pred_addr, succ_addr)
    if i is None or ca[i - 1]["t4"] is None:
        return None, None
    L = ca[i]["t1"] - ca[i - 1]["t4"]
    idle = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
               if crel[r]["t"] == 0)
    return L, idle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--nsat", type=int, default=6, help="saturated predecessor N")
    ap.add_argument("--ws-scan", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[3, 7])
    ap.add_argument("--span", type=int, default=12, help="upstream accesses to probe")
    ap.add_argument("--max-confirm", type=int, default=3, help="chip runs per q_cnt")
    a = ap.parse_args()
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    anc = find_anchor(a.seed, a.host, image, a.ws_scan, a.wmaxes)
    if anc is None:
        print(f"fz{a.seed}: no anchor"); return 1
    pred_addr, succ_addr = anc["pred_addr"], anc["succ_addr"]
    print(f"### fz{a.seed} anchor CODE@{pred_addr:05x} -> CODE@{succ_addr:05x} "
          f"(base ws{anc['ws']} wmax{anc['wmax']}); Nsat={a.nsat}")
    base = list(anc["wv"])
    wv0, i0, kr0, ka0 = set_pred_N(image, base, pred_addr, succ_addr, a.nsat)
    if wv0 is None:
        print("  base anchor not locatable at Nsat"); return 1
    q0 = qcnt_at_predT4(kr0, ka0, i0)
    print(f"  base q_cnt(pred_T4) = {q0} (pred bus#{i0-1})")

    # TB SEARCH: perturb one upstream access wait, collect variants by q_cnt
    variants = defaultdict(list)   # q_cnt -> list of wv (pred N reset to Nsat)
    variants[q0].append(wv0)
    for j in range(max(0, i0 - 1 - a.span), i0 - 1):
        for w in range(0, 8):
            wv = list(base); wv[j] = w
            wv2, i2, kr2, ka2 = set_pred_N(image, wv, pred_addr, succ_addr, a.nsat)
            if wv2 is None:
                continue
            q = qcnt_at_predT4(kr2, ka2, i2)
            if q is None:
                continue
            # keep predecessor N fixed at Nsat (verify) and anchor intact
            if wv2[i2 - 1] != a.nsat:
                continue
            if all(wv2 != v for v in variants[q]):
                variants[q].append((wv2, j, w))
    print("  TB search: q_cnt -> #variants: "
          + ", ".join(f"q{q}={len(v)}" for q, v in sorted(variants.items())))

    # CONFIRM on chip: for q_cnt in {2,3} (and neighbors present), measure L
    print("\n  CHIP confirmation (L = successor_T1 - pred_T4; idle = L-1):")
    print("   q_cnt | chip L (idle)   [perturbation]")
    for q in sorted(variants):
        shown = 0
        for item in variants[q]:
            if shown >= a.max_confirm:
                break
            wv = item if isinstance(item, list) else item[0]
            tag = "base" if isinstance(item, list) else f"acc#{item[1]}=w{item[2]}"
            L, idle = chip_L(image, a.host, wv, pred_addr, succ_addr)
            if L is None:
                continue
            print(f"     {q}   |   {L} ({idle})        [{tag}]")
            shown += 1


if __name__ == "__main__":
    main()
