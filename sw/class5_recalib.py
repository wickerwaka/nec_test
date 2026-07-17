#!/usr/bin/env python3
"""FRESH-SEED RECALIBRATION, in one board pass.

Captures each fresh (seed, wait-vector) ONCE and derives, from the same
captures, on the same pf_drain-deleted build:
  (A) census-style mass, OLD hard-cutoff aligner  (the floored number)
  (B) census-style mass, RESYNC aligner            (un-floored)
  (C) alltrans-proxy mass (idle-cidle delta), RESYNC aligner
So the census floor (A vs B) AND the real proxy/census ratio (C vs B) come out
of a single pass, over identical seeds. No number carried forward; every
threshold re-derived from THIS composition.

Fresh seeds (never fitted): disc 90008-90017, held 91006-91011.
Chip = ground truth (use_core=False, read-only). No flash.
"""
import sys, json, gzip, time, argparse
import random as _r
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream)
from class5_align import align


def wv_of(ws, wmax):
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def masses(ca, ka):
    """Return (old_cut_mass, resync_mass, proxy_mass)."""
    cb, kb = bs_stream(ca), bs_stream(ka)
    n = min(len(cb), len(kb))
    # OLD hard cutoff
    D = next((i for i in range(n)
              if cb[i] != kb[i] or ca[i]["addr"] != ka[i]["addr"]), n)
    old = 0
    for i in range(1, D):
        old += abs((ca[i]["t1"] - ca[i-1]["t1"]) - (ka[i]["t1"] - ka[i-1]["t1"]))
    # RESYNC
    pairs, _e, _s = align(ca, ka)
    kmap = {ci: ki for ci, ki in pairs}
    rmass = pmass = 0
    for i in sorted(kmap):
        if i == 0 or (i - 1) not in kmap:
            continue
        ki, kip = kmap[i], kmap[i - 1]
        rmass += abs((ca[i]["t1"] - ca[i-1]["t1"]) - (ka[ki]["t1"] - ka[kip]["t1"]))
        if ca[i-1]["t4"] is not None:
            cti = sum(1 for r in range(ca[i-1]["t4"]+1, ca[i]["t1"]))  # placeholder
    # proxy mass: idle-cidle delta, resync-aligned
    for i in sorted(kmap):
        if i == 0 or (i - 1) not in kmap:
            continue
        ki, kip = kmap[i], kmap[i-1]
        if ca[i-1]["t4"] is None:
            continue
        cti = ca[i]["t1"] - ca[i-1]["t4"] - 1
        mti = ka[ki]["t1"] - ka[kip]["t4"] - 1
        pmass += abs(cti - mti)
    return old, rmass, pmass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=list(range(90008, 90018)) + list(range(91006, 91012)))
    ap.add_argument("--nws", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[0, 1, 3, 7])
    a = ap.parse_args()
    logf = (SW / "class5_recalib.log").open("w")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    log(f"start {time.ctime()}  FRESH-SEED RECALIBRATION (resync vs old-cutoff)")
    log(f"seeds={a.seeds}")
    tot = defaultdict(int)
    per_w0 = 0
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                wv = wv_of(ws, wmax)
                t0 = time.time()
                try:
                    cr = run_chip(image, a.host, use_core=False, wvec=wv)
                    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
                    kr = run_tb_internal(image, 4200, wv)
                    ca = accesses(crel)
                    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                        ad_addr=x["addr"], ad_data=0) for x in kr])
                    o, r_, p = masses(ca, ka)
                    tot["old"] += o; tot["resync"] += r_; tot["proxy"] += p
                    if wmax == 0:
                        per_w0 += r_
                except Exception as e:
                    log(f"  fz{seed} ws{ws} wmax{wmax}: ERR {e}")
        log(f"  fz{seed}: cumulative old={tot['old']} resync={tot['resync']} "
            f"proxy={tot['proxy']}")
    log(f"\n=== RESULT (fresh seeds, same captures, same build) ===")
    log(f"  census mass, OLD hard-cutoff aligner : {tot['old']}   (FLOORED)")
    log(f"  census mass, RESYNC aligner          : {tot['resync']}   (un-floored)")
    log(f"  => census floor = {tot['resync']-tot['old']} units the cutoff hid "
        f"({100*(tot['resync']-tot['old'])/max(1,tot['resync']):.0f}% of true)")
    log(f"  alltrans-proxy mass (idle-cidle delta): {tot['proxy']}")
    log(f"  w0 control (must be 0): {per_w0}")
    if tot["proxy"]:
        log(f"\n  REAL RATIO census(resync) / proxy = "
            f"{tot['resync']/tot['proxy']:.2f}")
    json.dump(dict(tot), (SW / "class5_recalib.json").open("w"), indent=1)
    log(f"done {time.ctime()}")
    logf.close()


if __name__ == "__main__":
    main()
