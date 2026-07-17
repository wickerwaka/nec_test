#!/usr/bin/env python3
"""Class-5 anchor cycle-trace: visualize the QS-pop geometry around a CODE->CODE
resume anchor, chip vs model, at a matching-N and a diverging-N. Prerequisite for
designing the matched-pop (Factor-P) experiment: shows WHERE the queue byte-pops
land relative to the predecessor T4 / eval_ext and the successor T1, i.e. what a
"one-clock pop shift" would move.

Usage: python3 sw/class5_anchortrace.py --seed 90007 --N 1 4 [--ws-scan 6]
"""
import sys, argparse, random as _r
from pathlib import Path
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _sname, BSN, CODE)
from class5_factorW import find_anchor

TN = {1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4", 0: "Ti"}
QN = {0: " ", 1: "F", 2: "E", 3: "S"}


def dump(seed, host, image, base_wv, pred_bus, i, N, pred_addr, succ_addr):
    wv = list(base_wv)
    wv[pred_bus] = N
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    if i >= len(ca) or i >= len(ka):
        print(f"    N={N}: anchor beyond stream"); return
    # window rows: from predecessor T1-2 to successor T1+2 (in each stream)
    cp1, ct4, cs1 = ca[i - 1]["t1"], ca[i - 1]["t4"], ca[i]["t1"]
    kp1, kt4, ks1 = ka[i - 1]["t1"], ka[i - 1]["t4"], ka[i]["t1"]
    print(f"\n  === N={N}  chip resume_idle="
          f"{sum(1 for r in range(ct4+1, cs1) if crel[r]['t']==0)}  "
          f"model resume_idle="
          f"{sum(1 for r in range(kt4+1, ks1) if kr[r]['t']==0)} ===")
    print("   CHIP  [row tstate bs      addr   QS]        "
          "MODEL [row tstate bs     addr  QS state       qc occ evx qag]")
    clo, chi = max(0, cp1 - 2), min(len(crel), cs1 + 3)
    klo, khi = max(0, kp1 - 2), min(len(kr), ks1 + 3)
    span = max(chi - clo, khi - klo)
    for off in range(span):
        cs = ""
        cr_i = clo + off
        if cr_i < chi:
            r = crel[cr_i]
            mk = "<T4" if cr_i == ct4 else ("<T1s" if cr_i == cs1 else "")
            cs = (f"{cr_i:4d} {TN.get(r['t'],r['t']):>2} "
                  f"{BSN.get(r['bs_early'],r['bs_early']):<4} {r['ad_addr']:05x} "
                  f"{QN.get(r['qs'],'?')} {mk:<4}")
        ms = ""
        kr_i = klo + off
        if kr_i < khi:
            x = kr[kr_i]
            mk = "<T4" if kr_i == kt4 else ("<T1s" if kr_i == ks1 else "")
            ms = (f"{kr_i:4d} {TN.get(x['t'],x['t']):>2} "
                  f"{BSN.get(x['bs'],x['bs']):<4} {x['addr']:05x} "
                  f"{QN.get(x['qs'],'?')} {_sname(x['state']):<9} "
                  f"qc{x['q_cnt']} av{x.get('q_avl',-1)} oc{x['occupied']:2d} cn{x.get('cnt_next',-1)} "
                  f"pp{x.get('push_pend',-1)} pn{x.get('push_now',-1)} "
                  f"ag{x['q_aged']} lim{x.get('pf_lim',-1)} "
                  f"ok{x.get('prefetch_ok',-1)} ex{x['eval_ext']} {mk}")
        print(f"   {cs:<40}  {ms}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--N", type=int, nargs="+", default=[1, 4])
    ap.add_argument("--ws-scan", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    a = ap.parse_args()
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    anc = find_anchor(a.seed, a.host, image, a.ws_scan, a.wmaxes)
    if anc is None:
        print(f"fz{a.seed}: no anchor"); return 1
    print(f"### fz{a.seed} anchor pred CODE@{anc['pred_addr']:05x} -> "
          f"succ CODE@{anc['succ_addr']:05x}  ws{anc['ws']} wmax{anc['wmax']} "
          f"prev_tw={anc['prev_tw']} bus#{anc['pred_bus']}->#{anc['i']} "
          f"(impulse ge={anc['ge']:+d})")
    for N in a.N:
        dump(a.seed, a.host, image, anc["wv"], anc["pred_bus"], anc["i"], N,
             anc["pred_addr"], anc["succ_addr"])


if __name__ == "__main__":
    main()
