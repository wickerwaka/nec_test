#!/usr/bin/env python3
"""Class-5 Factor-W experiment: the prefetch-RESUME response curve vs predecessor
wait count N (Codex's decisive first class-5 measurement).

At a reproducible CODE->CODE impulse anchor, sweep ONLY the predecessor fetch's
own wait count N=0..7 (via the explicit WVEC), holding the instruction stream
fixed, and measure the CHIP's vs MODEL's resume-idle count (Ti cycles between the
predecessor's T4 and the successor's T1). Two contexts:

  ISOLATED : WVEC all zero except the predecessor fetch = N  (clean grid; the
             pure resume_idle_chip(N) law with no accumulated drift).
  INCONTEXT: the original impulse WVEC, but the predecessor's slot overridden to
             N (the real drained-queue context the impulse occurred in).

If chip resume_idle changes with N while occupancy/pop placement are held ->
stretched-grid DURATION/PHASE is causal. If model tracks chip -> no defect at
this anchor; where they diverge is the class-5 law the model is missing.

Chip = ground truth (use_core=0); model = TB (== fabric). Anchors are discovered
from the gap-error census logic. Usage:
  python3 sw/class5_factorW.py --seed 90007 [--ws-scan 6] [--wmaxes 1 3 7]
"""
import sys, argparse, random as _r
from pathlib import Path
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, BSN, CODE)


def lfsr_wv(ws, wmax):
    return [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]


def resume_idle(rows, acc, i):
    """Ti (idle) cycles between acc[i-1].t4 and acc[i].t1."""
    a, b = acc[i - 1], acc[i]
    if a["t4"] is None:
        return None
    return sum(1 for r in range(a["t4"] + 1, b["t1"]) if rows[r]["t"] == 0)


def find_anchor(seed, host, image, ws_scan, wmaxes):
    """Scan for the largest-magnitude CODE->CODE gap-error impulse; return
    (wv, i, predP_busidx, pred_addr, succ_addr, ge, ws, wmax, prev_tw)."""
    best = None
    for ws in range(1, ws_scan + 1):
        for wmax in wmaxes:
            wv = lfsr_wv(ws, wmax)
            cr = run_chip(image, host, use_core=False, wvec=wv)
            crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
            kr = run_tb_internal(image, 4200, wv)
            ca = accesses(crel)
            ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                ad_addr=x["addr"], ad_data=0) for x in kr])
            cb, kb = bs_stream(ca), bs_stream(ka)
            n = min(len(cb), len(kb))
            D = next((j for j in range(n)
                      if cb[j] != kb[j] or ca[j]["addr"] != ka[j]["addr"]), n)
            for i in range(1, D):
                if cb[i] != CODE or cb[i - 1] != CODE:
                    continue
                cg = ca[i]["t1"] - ca[i - 1]["t1"]
                mg = ka[i]["t1"] - ka[i - 1]["t1"]
                ge = cg - mg
                if ge == 0:
                    continue
                cand = (abs(ge), dict(wv=wv, i=i, ge=ge, ws=ws, wmax=wmax,
                                      pred_addr=ca[i - 1]["addr"],
                                      succ_addr=ca[i]["addr"],
                                      pred_bus=i - 1, prev_tw=ca[i - 1]["tw"]))
                if best is None or cand[0] > best[0]:
                    best = cand
    return best[1] if best else None


def sweep(seed, host, image, base_wv, pred_bus, i, label):
    print(f"\n  --- {label} sweep (predecessor bus#{pred_bus}, "
          f"successor #{i}) ---")
    print(f"    N | chip_idle model_idle  gap(chip-model) | chip_gap model_gap")
    for N in range(0, 8):
        wv = list(base_wv)
        wv[pred_bus] = N
        cr = run_chip(image, host, use_core=False, wvec=wv)
        crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
        kr = run_tb_internal(image, 4200, wv)
        ca = accesses(crel)
        ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                            ad_addr=x["addr"], ad_data=0) for x in kr])
        # verify the anchor still aligns (same pred/succ addr at i-1,i)
        ok = (i < len(ca) and i < len(ka)
              and ca[i - 1]["bs"] == CODE and ca[i]["bs"] == CODE)
        ci = resume_idle(crel, ca, i) if ok else None
        mi = resume_idle(kr, ka, i) if ok else None
        if ci is None or mi is None:
            print(f"    {N} | anchor moved (realignment needed)")
            continue
        cg = ca[i]["t1"] - ca[i - 1]["t1"]
        mg = ka[i]["t1"] - ka[i - 1]["t1"]
        flag = "  <== DIVERGE" if ci != mi else ""
        print(f"    {N} |   {ci:3d}      {mi:3d}       {ci-mi:+3d}          |"
              f"  {cg:3d}     {mg:3d}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--ws-scan", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    a = ap.parse_args()
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    anc = find_anchor(a.seed, a.host, image, a.ws_scan, a.wmaxes)
    if anc is None:
        print(f"fz{a.seed}: no CODE->CODE impulse anchor found"); return 1
    print(f"\n### fz{a.seed} anchor: pred CODE@{anc['pred_addr']:05x} -> "
          f"succ CODE@{anc['succ_addr']:05x}  (impulse ge={anc['ge']:+d} at "
          f"ws{anc['ws']} wmax{anc['wmax']} prev_tw={anc['prev_tw']}, "
          f"bus#{anc['pred_bus']}->#{anc['i']})")
    # ISOLATED: single waited predecessor in an otherwise-w0 stream
    zero_wv = [0] * 4096
    sweep(a.seed, a.host, image, zero_wv, anc["pred_bus"], anc["i"], "ISOLATED")
    # INCONTEXT: the real impulse WVEC, predecessor slot overridden
    sweep(a.seed, a.host, image, anc["wv"], anc["pred_bus"], anc["i"], "INCONTEXT")


if __name__ == "__main__":
    main()
