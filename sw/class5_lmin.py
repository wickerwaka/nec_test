#!/usr/bin/env python3
"""Class-5 Lmin geometry census: extract the saturated resume floor Lmin =
(successor_T1 - predecessor_T4) at high N, across many CODE->CODE resume anchors,
and correlate it with fetch/queue/EU features at the predecessor T4. Fetch PARITY
is NOT the discriminator (linear prefetch runs are all even->even); this finds the
real determinant of Lmin=4 vs 5.

For each discovered anchor, sweep N=0..7 (predecessor wait via WVEC, INCONTEXT),
measure chip resume_idle(N); Lmin_idle = min over N (the floor), Lmin = Lmin_idle+1.
Record features at the predecessor T4 (chip fetch parities; model internals on the
aligned prefix). Chip = ground truth. Usage: python3 sw/class5_lmin.py [--seeds ..]
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import defaultdict, Counter
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _sname, BSN, CODE)


def lfsr_wv(ws, wmax):
    return [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]


def find_anchors(seed, host, image, ws_scan, wmaxes, cap):
    """All distinct CODE->CODE nonzero-gap-error anchors from a scan."""
    seen = {}
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
                if cg - mg == 0:
                    continue
                key = (ca[i - 1]["addr"], ca[i]["addr"])
                if key not in seen:
                    seen[key] = dict(wv=wv, i=i, pred_bus=i - 1, ws=ws, wmax=wmax,
                                     pred_addr=key[0], succ_addr=key[1])
                if len(seen) >= cap:
                    return list(seen.values())
    return list(seen.values())


def sweep_anchor(host, image, anc):
    base_wv, pred_bus, i = anc["wv"], anc["pred_bus"], anc["i"]
    idles = {}
    feat = None
    for N in range(0, 8):
        wv = list(base_wv); wv[pred_bus] = N
        cr = run_chip(image, host, use_core=False, wvec=wv)
        crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
        kr = run_tb_internal(image, 4200, wv)
        ca = accesses(crel)
        ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                            ad_addr=x["addr"], ad_data=0) for x in kr])
        if i >= len(ca) or ca[i]["bs"] != CODE or ca[i - 1]["bs"] != CODE \
                or ca[i - 1]["t4"] is None:
            continue
        ci = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                 if crel[r]["t"] == 0)
        idles[N] = ci
        if N == 7 and i < len(ka) and ka[i - 1]["t4"] is not None:
            kt4 = ka[i - 1]["t4"]
            x = kr[kt4]
            feat = dict(pred_par=ca[i - 1]["addr"] & 1,
                        succ_par=ca[i]["addr"] & 1,
                        pred_state=_sname(x["state"]),
                        qcnt_t4=x["q_cnt"], occ_t4=x["occupied"],
                        gph_t4=x.get("grid_phase", -1),
                        pushpend_t4=x.get("push_pend", -1),
                        qaged_t4=x["q_aged"], infl_t4=x["infl"])
    if not idles:
        return None
    lmin_idle = min(idles.values())
    return dict(idles=idles, lmin_idle=lmin_idle, lmin=lmin_idle + 1, feat=feat,
                **{k: anc[k] for k in ("pred_addr", "succ_addr", "ws", "wmax")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[90002, 90007, 90011, 90003, 90005, 90009, 90013])
    ap.add_argument("--ws-scan", type=int, default=5)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[3, 7])
    ap.add_argument("--cap", type=int, default=4, help="anchors per seed")
    a = ap.parse_args()
    results = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        ancs = find_anchors(seed, a.host, image, a.ws_scan, a.wmaxes, a.cap)
        for anc in ancs:
            r = sweep_anchor(a.host, image, anc)
            if r is None:
                continue
            r["seed"] = seed
            results.append(r)
            f = r["feat"] or {}
            curve = " ".join(f"{r['idles'].get(N,'-')}" for N in range(8))
            print(f"fz{seed} {r['pred_addr']:05x}->{r['succ_addr']:05x}: "
                  f"idle[N=0..7]={curve}  Lmin={r['lmin']} "
                  f"| par {f.get('pred_par','?')}->{f.get('succ_par','?')} "
                  f"pred_state={f.get('pred_state','?')} "
                  f"qc={f.get('qcnt_t4','?')} occ={f.get('occ_t4','?')} "
                  f"gph={f.get('gph_t4','?')} pushpend={f.get('pushpend_t4','?')} "
                  f"qaged={f.get('qaged_t4','?')}")
    print(f"\n=== {len(results)} anchors ===")
    print("\nLmin distribution:")
    for k, c in sorted(Counter(r["lmin"] for r in results).items()):
        print(f"   Lmin={k}: {c}")
    # correlate Lmin with each feature
    for fk in ["pred_par", "succ_par", "pred_state", "qcnt_t4", "occ_t4",
               "gph_t4", "pushpend_t4", "qaged_t4"]:
        print(f"\nLmin by {fk}:")
        by = defaultdict(Counter)
        for r in results:
            if r["feat"]:
                by[r["feat"][fk]][r["lmin"]] += 1
        for v in sorted(by, key=lambda x: str(x)):
            dist = " ".join(f"Lmin{lm}:{c}" for lm, c in sorted(by[v].items()))
            print(f"   {fk}={v}: {dist}")


if __name__ == "__main__":
    main()
