#!/usr/bin/env python3
"""Class-5 STREAM-cadence measurement: the fill-vs-pause boundary IN CONTEXT.

The isolated saturated-N surface census gave the PAUSED-state floor L(q_cnt). But
a floor-only RTL shattered w1/w3 because in a FILLING stream the chip prefetches
back-to-back even at q_cnt>=2. This measures the chip's CODE->CODE resume idle as
a function of the model's queue state (q_cnt, occupied) at the predecessor T4, in
UNIFORM-wait streams (the filling regime) - to find when the chip pauses vs
continues, and where the model (occ<=pf_lim) diverges from the chip.

Chip = ground truth; model internals label the queue state on the aligned prefix.
Usage: python3 sw/class5_streamcadence.py [--seeds ...] [--waits 1 2 3]
"""
import sys, argparse
from pathlib import Path
from collections import defaultdict, Counter
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _sname, BSN, CODE)


def analyze(seed, host, image, w, out):
    wv = [w] * 4096
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    # model bus index -> kr T4 row
    kt4 = {}; bi = -1
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1
        if x["t"] == 5:
            kt4[bi] = ri
    cb, kb = bs_stream(ca), bs_stream(ka)
    n = min(len(cb), len(kb))
    D = next((j for j in range(n)
              if cb[j] != kb[j] or ca[j]["addr"] != ka[j]["addr"]), n)
    for i in range(1, D):
        if cb[i] != CODE or cb[i - 1] != CODE:
            continue
        if ca[i - 1]["t4"] is None or (i - 1) not in kt4:
            continue
        # chip resume idle (Ti between pred T4 and succ T1)
        cidle = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                    if crel[r]["t"] == 0)
        midle = sum(1 for r in range(ka[i - 1]["t4"] + 1, ka[i]["t1"])
                    if kr[r]["t"] == 0)
        x = kr[kt4[i - 1]]   # model row at predecessor T4
        # decision edge = the deferred-completion eval (eval_ext), pred_T4 + 1
        e = kr[kt4[i - 1] + 1] if kt4[i - 1] + 1 < len(kr) else x
        out.append(dict(w=w, qcnt=x["q_cnt"], occ=x["occupied"],
                        av=x.get("q_avl", -1), infl=x.get("infl", -1),
                        drain=x.get("pf_drain", -1),
                        cons=x.get("eu_consuming", -1),
                        popc=x.get("pop_cnt", -1),
                        eocc=e["occupied"], epop=e.get("pop_now", -1),
                        epush=e.get("push_now", -1), eav=e.get("q_avl", -1),
                        eqc=e["q_cnt"], elim=e.get("pf_lim", -1),
                        cidle=cidle, midle=midle, err=cidle - midle))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[90002, 90003, 90005, 90007, 90011])
    ap.add_argument("--waits", type=int, nargs="+", default=[1, 2, 3])
    a = ap.parse_args()
    out = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for w in a.waits:
            try:
                analyze(seed, a.host, image, w, out)
            except Exception as e:
                print(f"  fz{seed} w{w}: ERR {e}")
    print(f"\n=== {len(out)} CODE->CODE resumes in uniform-wait streams ===")
    print("\nCHIP resume idle by q_cnt(pred_T4)  [the fill-vs-pause boundary]:")
    byq = defaultdict(Counter)
    for r in out:
        byq[r["qcnt"]][r["cidle"]] += 1
    for q in sorted(byq):
        dist = " ".join(f"idle{k}:{c}" for k, c in sorted(byq[q].items()))
        print(f"   q_cnt={q}: {dist}")
    print("\nCHIP resume idle by occupied(pred_T4):")
    byo = defaultdict(Counter)
    for r in out:
        byo[r["occ"]][r["cidle"]] += 1
    for o in sorted(byo):
        dist = " ".join(f"idle{k}:{c}" for k, c in sorted(byo[o].items()))
        print(f"   occ={o}: {dist}")
    print("\nchip-vs-model idle DISAGREEMENT (err=cidle-midle) by q_cnt:")
    bye = defaultdict(Counter)
    for r in out:
        bye[r["qcnt"]][r["err"]] += 1
    for q in sorted(bye):
        dist = " ".join(f"{k:+d}:{c}" for k, c in sorted(bye[q].items()) if k != 0)
        nz = sum(c for k, c in bye[q].items() if k != 0)
        tot = sum(bye[q].values())
        print(f"   q_cnt={q}: err {dist or '(none)'}  ({nz}/{tot} disagree)")
    # BOUNDARY discriminator: at q_cnt=2 (occ~4), what separates chip pause
    # (idle>=3) from chip back-to-back (idle<=1)?
    print("\nBOUNDARY q_cnt=2: chip pause(idle>=3) vs go(idle<=1) by DECISION-EDGE state:")
    for fld in ["occ", "cons", "popc", "eocc", "epop", "epush", "eav", "eqc", "elim"]:
        pause = Counter(); go = Counter()
        for r in out:
            if r["qcnt"] != 2:
                continue
            (pause if r["cidle"] >= 3 else go)[r[fld]] += 1
        vals = sorted(set(pause) | set(go))
        cells = "  ".join(f"{fld}={v}:{go[v]}/{pause[v]}" for v in vals)
        print(f"   [go/pause] {cells}")
    # cross: does (eocc) cleanly separate go from pause?
    print("\n  q_cnt=2 chip idle by decision-edge eocc:")
    byeo = defaultdict(Counter)
    for r in out:
        if r["qcnt"] == 2:
            byeo[r["eocc"]][r["cidle"]] += 1
    for o in sorted(byeo):
        dist = " ".join(f"idle{k}:{c}" for k, c in sorted(byeo[o].items()))
        print(f"     eocc={o}: {dist}")


if __name__ == "__main__":
    main()
