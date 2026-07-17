#!/usr/bin/env python3
"""Class-5 signed inter-T1 GAP-ERROR census (Codex class-5 pivot instrument).

Class 5 = "same bus decisions, WRONG CLOCK": the chip and model agree on the
(BUS TYPE, ADDRESS) stream but the model places some T1 edges at the wrong cycle.
First-divergence taxonomy (class5tax) hides later independent impulses and
mis-attributes cumulative drift. Instead, for every aligned bus ordinal i compute
the SIGNED per-interval cadence derivative:

    chip_gap[i]  = chip_T1[i]  - chip_T1[i-1]     (clocks between consecutive T1s)
    model_gap[i] = model_T1[i] - model_T1[i-1]
    gap_error[i] = chip_gap[i] - model_gap[i]

Because the SAME explicit wait vector is applied and the type/address streams
match on the aligned prefix, gap_error[i] localizes EXACTLY where each new timing
impulse is injected (a constant accumulated offset -> 0; sign shows advance/delay;
canceling +/- errors are both visible). w0 vectors (wmax=0) are included as
zero-error controls: the rule must predict gap_error==0 there naturally.

Each nonzero impulse is decomposed by grid geometry so we can test whether a
small set of future-slot features separates nonzero impulses from clean controls.

Chip = ground truth (use_core=0); model = TB internals (== fabric on the aligned
prefix). Usage: python3 sw/class5_gaperr.py [--seeds ...] [--nws N] [--wmaxes ...]
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import Counter, defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from class5_align import align
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _sname, BSN, MEMR, MEMW, CODE)


def wv_of(ws, wmax):
    # BUG FIX: the old form `[_r.Random(seed).randint(0,wmax) for _ in range(4096)]`
    # constructed a NEW Random(seed) per element, so every element was the SAME
    # first draw -> a CONSTANT vector (uniform wait), never per-cycle random. The
    # entire gaperr census history (422/308/188/...) was therefore a DEGENERATE
    # uniform-wait census, heavily w0-weighted - NOT the random-wait target
    # (memory #1 priority). Fixed: one Random, drawn 4096 times.
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def analyze_vec(seed, ws, wmax, host, image):
    wv = wv_of(ws, wmax)
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in crel]) \
        if False else accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    cb, kb = bs_stream(ca), bs_stream(ka)
    # RESYNC-TOLERANT ALIGNMENT (was: hard first-divergence cutoff D, which
    # truncated the entire remaining stream on a 2-access arbitration swap and
    # so FLOORED the census mass exactly as it floored the corpus). kmap maps
    # chip access index -> model access index over the recovered alignment.
    pairs, _events, _stop = align(ca, ka)
    kmap = {ci: ki for ci, ki in pairs}
    out = []
    for i in sorted(kmap):
        if i == 0 or (i - 1) not in kmap:
            continue
        ki, kip = kmap[i], kmap[i - 1]
        cg = ca[i]["t1"] - ca[i - 1]["t1"]
        mg = ka[ki]["t1"] - ka[kip]["t1"]
        ge = cg - mg
        # model live-state row just before cur T1 (uncontaminated decision edge)
        d = kr[max(0, ka[ki]["t1"] - 1)]
        # Ti (idle) counts in the interval, chip vs model
        cti = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                  if crel[r]["t"] == 0) if ca[i - 1]["t4"] else -1
        mti = sum(1 for r in range(ka[kip]["t4"] + 1, ka[ki]["t1"])
                  if kr[r]["t"] == 0) if ka[kip]["t4"] else -1
        out.append(dict(
            ge=ge, cg=cg, mg=mg,
            prev_bs=BSN.get(cb[i - 1], cb[i - 1]),
            cur_bs=BSN.get(cb[i], cb[i]),
            prev_tw=ca[i - 1]["tw"], cur_tw=ca[i]["tw"],
            cur_par=ca[i]["addr"] & 1,
            cti=cti, mti=mti,
            m_state=_sname(d["state"]), m_occ=d["occupied"], m_qcnt=d["q_cnt"],
            m_qaged=d["q_aged"], m_evx=d["eval_ext"], m_flush=d["q_flush"],
            seed=seed, ws=ws, wmax=wmax, i=i))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=list(range(90000, 90020)))
    ap.add_argument("--nws", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[0, 1, 3, 7])
    a = ap.parse_args()
    allrows = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                try:
                    allrows += analyze_vec(seed, ws, wmax, a.host, image)
                except Exception as e:
                    print(f"  fz{seed} ws{ws} wmax{wmax}: ERR {e}")
    nz = [r for r in allrows if r["ge"] != 0]
    print(f"\n=== class-5 gap-error census: {len(allrows)} aligned intervals, "
          f"{len(nz)} nonzero ({100*len(nz)/max(1,len(allrows)):.1f}%) ===")

    # --- DENOMINATOR tables (Codex): the nonzero-only tables below can mislead
    # (e.g. "always +ve at tw=7" may just mean few tw=7 opportunities). Report,
    # per cell, TOTAL opportunities and zero/pos/neg split so the ERROR RATE and
    # sign balance are visible, not just the impulses. ---
    def denom(keyfn, title, order=None):
        tot = defaultdict(lambda: [0, 0, 0])  # [zero, pos, neg]
        for r in allrows:
            k = keyfn(r)
            if r["ge"] == 0:
                tot[k][0] += 1
            elif r["ge"] > 0:
                tot[k][1] += 1
            else:
                tot[k][2] += 1
        print(f"\n{title}  [n=total  err%=nonzero/total  +/-=pos/neg]:")
        keys = order if order else sorted(tot, key=lambda k: -(tot[k][1] + tot[k][2]))
        for k in keys:
            z, p, m = tot[k]
            n = z + p + m
            if p + m == 0 and n < 50:
                continue
            print(f"   {str(k):<22} n={n:6d}  err={100*(p+m)/max(1,n):5.2f}%  "
                  f"+{p:<4d} -{m:<4d}")

    denom(lambda r: f"{r['prev_bs']}->{r['cur_bs']}", "By transition (denominator)")
    denom(lambda r: (r["prev_bs"], r["prev_tw"]),
          "By (prev_bs, prev_tw) (denominator - is prev_tw governing?)")
    denom(lambda r: (r["cur_bs"], r["prev_tw"]),
          "By (cur_bs, prev_tw) (denominator)")
    # CODE->CODE only, by prev_tw: the core prefetch-resume response curve
    cc = [r for r in allrows if r["prev_bs"] == "CODE" and r["cur_bs"] == "CODE"]
    print(f"\nCODE->CODE resume response curve (n={len(cc)}): "
          "prev_tw -> err% (+/-):")
    ct = defaultdict(lambda: [0, 0, 0])
    for r in cc:
        ct[r["prev_tw"]][0 if r["ge"] == 0 else (1 if r["ge"] > 0 else 2)] += 1
    for tw in sorted(ct):
        z, p, m = ct[tw]
        n = z + p + m
        print(f"   prev_tw={tw}: n={n:6d}  err={100*(p+m)/max(1,n):5.2f}%  +{p} -{m}")
    print("\nsigned gap_error histogram (clocks):")
    for k, c in sorted(Counter(r["ge"] for r in allrows).items()):
        bar = "#" * min(60, c // 2) if k != 0 else ""
        print(f"   {k:+3d}: {c:5d} {bar}")
    # net + absolute impulse mass
    net = sum(r["ge"] for r in allrows)
    absm = sum(abs(r["ge"]) for r in allrows)
    print(f"\nnet gap_error sum = {net:+d}   |impulse| mass = {absm}   "
          f"(net<<mass => canceling +/- impulses)")
    # w0 control sanity: wmax==0 intervals MUST all be zero
    w0 = [r for r in allrows if r["wmax"] == 0]
    w0nz = [r for r in w0 if r["ge"] != 0]
    print(f"\nw0 control (wmax=0): {len(w0)} intervals, {len(w0nz)} nonzero "
          f"(MUST be 0 - instrument + w0-neutrality sanity)")
    if w0nz:
        for r in w0nz[:8]:
            print(f"   !! fz{r['seed']} ws{r['ws']} i={r['i']} ge={r['ge']:+d} "
                  f"{r['prev_bs']}->{r['cur_bs']}")
    # decomposition of nonzero impulses
    print("\nnonzero impulses by (prev->cur bus, prev_tw):")
    by = defaultdict(Counter)
    for r in nz:
        by[(f"{r['prev_bs']}->{r['cur_bs']}", r["prev_tw"])][r["ge"]] += 1
    for key in sorted(by, key=lambda k: -sum(by[k].values()))[:20]:
        dist = "  ".join(f"{g:+d}:{c}" for g, c in sorted(by[key].items()))
        print(f"   {key[0]:<14} prev_tw={key[1]}: {dist}")
    print("\nnonzero impulses by model state at cur-T1-1:")
    for k, c in Counter(r["m_state"] for r in nz).most_common(12):
        print(f"   {k:<12}: {c}")
    print("\nnonzero impulses by (cur_bs, cur_parity):")
    for k, c in sorted(Counter((r["cur_bs"], r["cur_par"]) for r in nz).items()):
        print(f"   {k}: {c}")
    print("\nnonzero impulses by chip-vs-model Ti delta (cti-mti):")
    for k, c in sorted(Counter((r["cti"] - r["mti"]) for r in nz
                               if r["cti"] >= 0 and r["mti"] >= 0).items()):
        print(f"   Ti_delta {k:+d}: {c}")


if __name__ == "__main__":
    main()
