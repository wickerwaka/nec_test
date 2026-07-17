#!/usr/bin/env python3
"""PHASE 2 addendum: the frontier, the underpowered-fit-set finding, the w0
sanity check, and ONE clearly-labelled exploratory generalization test.

Three things the frozen-protocol run (class5_phase2.py) cannot say by itself:

1. FRONTIER. The frozen variant failing criteria (a)/(b) is only a kill if NO
   eligible variant meets them. Computed on gz-disc (the fit set) only, so this
   establishes the kill without consulting held/fresh.

2. UNDERPOWER. gz-disc holds only ~7 rows in occ3/age1-2 - the very cells the
   coordinator sharpened the target to. The duration question is therefore
   nearly unfittable on the designated fit set. This is a protocol limitation,
   reported as such - NOT an excuse to refit.

3. EXPLORATORY (explicitly NOT a pass claim, and NOT the frozen variant): the
   sweep contains variants scoring 7/7 exact-cidle on those 7 disc target rows.
   With 5 chip-3 / 2 chip-4 rows a clean split is cheap by chance, so the only
   question worth asking is whether such a variant GENERALIZES to the 53 target
   rows in held+fresh. If it does, H-LV v2 deserves a rematch on a fit set built
   for it. If it does not, the kill is confirmed twice over. Reported as
   evidence for the coordinator's chip-factorial decision, not as a fit.

Usage: python3 sw/class5_phase2b.py
"""
import sys, json, gzip, time
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase2 import (load, split, score, simulate, vname, Traj,
                           DEMANDS, PERIODS, ANCHORS, OFFSETS, CLEARS,
                           READS, LAGS, OCC, AGE)
import itertools

LOG = SW / "class5_phase2b.log"


def main():
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    fi = {}
    meta, allrows = load(fi)
    nf = [x for x in allrows if x[0]["flush_win"] == 0
          and x[0]["label"] in ("go", "pause")]
    disc, held, fresh = split(nf)

    variants = list(itertools.product(DEMANDS, PERIODS, ANCHORS, OFFSETS,
                                      CLEARS, READS, LAGS))
    variants = [v for v in variants if not (v[1] == 1 and v[3] == 1)]

    log("=== PHASE 2 ADDENDUM ===")

    # ---------------- 1. FRONTIER on the fit set ----------------
    log("\n--- 1. FRONTIER: best ANY eligible variant achieves on gz-disc ---")
    log("    (criteria: (a) 0 GO/PAUSE errs on non-flush low+mid; "
        "(b) >=95% exact cidle)")
    elig = []
    for v in variants:
        s = score(disc, fi, v)
        if s["uneval"] == 0:
            elig.append((v, s))
    best_err = min(s["errs"] for _, s in elig)
    best_ex = max(s["ex"] / max(1, s["ex_n"]) for _, s in elig)
    log(f"    eligible variants: {len(elig)}")
    log(f"    BEST GO/PAUSE errors achievable: {best_err}   "
        f"(criterion (a) needs 0)")
    log(f"    BEST exact-cidle rate achievable: {100*best_ex:.1f}%   "
        f"(criterion (b) needs >=95%)")
    n0 = sum(1 for _, s in elig if s["errs"] == 0)
    n95 = sum(1 for _, s in elig if s["ex"] / max(1, s["ex_n"]) >= 0.95)
    log(f"    variants meeting (a): {n0}/{len(elig)}")
    log(f"    variants meeting (b): {n95}/{len(elig)}")
    log(f"    variants meeting BOTH: "
        f"{sum(1 for _, s in elig if s['errs']==0 and s['ex']/max(1,s['ex_n'])>=0.95)}"
        f"/{len(elig)}")

    # ---------------- 2. UNDERPOWER of the fit set ----------------
    log("\n--- 2. FIT-SET POWER on the sharpened target cells ---")
    for nm, s in (("gz-disc (FIT)", disc), ("gz-held", held), ("fresh", fresh)):
        t12 = [x for x in s if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2]
        t14 = [x for x in s if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 4]
        d = defaultdict(int)
        for x in t12:
            d[x[0]["cidle"]] += 1
        log(f"    {nm:14s}: occ3/age1-2 n={len(t12):3d} cidle {dict(sorted(d.items()))}"
            f"   | occ3/age1-4 n={len(t14):3d}")
    log("    => the designated fit set (gz-disc) carries only a handful of rows")
    log("       in the cells the whole question turns on. The duration split is")
    log("       structurally underpowered on gz-disc. Reported, not worked around.")

    # ---------------- 3. EXPLORATORY generalization ----------------
    log("\n--- 3. EXPLORATORY (NOT the frozen variant, NOT a pass claim) ---")
    log("    Do variants that ace the 7 disc target rows generalize to the 53")
    log("    target rows in held+fresh? Chance-level split on 5-vs-2 is cheap;")
    log("    generalization is not.")
    tgt_d = [x for x in disc if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2]
    tgt_h = [x for x in held if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2]
    tgt_f = [x for x in fresh if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2]
    perf = []
    for v, s in elig:
        sd = score(tgt_d, fi, v)
        if sd["ex_n"] and sd["ex"] == sd["ex_n"]:
            perf.append(v)
    log(f"    variants scoring 7/7 (perfect) on the disc target rows: {len(perf)}")
    log(f"    held target rows: {len(tgt_h)}   fresh target rows: {len(tgt_f)}")
    best = None
    for v in perf:
        sh = score(tgt_h, fi, v)
        sf = score(tgt_f, fi, v)
        rate = (sh["ex"] + sf["ex"]) / max(1, sh["ex_n"] + sf["ex_n"])
        if best is None or rate > best[0]:
            best = (rate, v, sh, sf)
    if best:
        log(f"\n    BEST generalization among those {len(perf)}:")
        log(f"      {vname(best[1])}")
        log(f"      held  target exact-cidle: {best[2]['ex']}/{best[2]['ex_n']}")
        log(f"      fresh target exact-cidle: {best[3]['ex']}/{best[3]['ex_n']}")
        log(f"      pooled held+fresh: {100*best[0]:.1f}%")
        log("\n    distribution of held+fresh target generalization over all "
            f"{len(perf)} disc-perfect variants:")
        rates = []
        for v in perf:
            sh = score(tgt_h, fi, v)
            sf = score(tgt_f, fi, v)
            rates.append((sh["ex"] + sf["ex"]) / max(1, sh["ex_n"] + sf["ex_n"]))
        rates.sort(reverse=True)
        log(f"      max={100*max(rates):.1f}%  median={100*rates[len(rates)//2]:.1f}%"
            f"  min={100*min(rates):.1f}%")
        log("      (if the max is near chance, the 7/7 was overfitting 7 rows)")

    json.dump(dict(best_err=best_err, best_exact=best_ex,
                   n_eligible=len(elig), n_meet_a=n0, n_meet_b=n95,
                   n_disc_perfect=len(perf),
                   generalization=(dict(variant=vname(best[1]),
                                        held=[best[2]["ex"], best[2]["ex_n"]],
                                        fresh=[best[3]["ex"], best[3]["ex_n"]],
                                        pooled=best[0]) if best else None)),
              (SW / "class5_phase2b.json").open("w"), indent=1, default=str)
    logf.close()


if __name__ == "__main__":
    main()
