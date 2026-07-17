#!/usr/bin/env python3
"""PHASE 6 / TASK B: FORM-FREE LOOKUP ON THE **DECISION** FUNCTION.

WHY: every veto predicate, and the Phase-S NO-GO (75016e3, "the ~3% fixable
cases are INSEPARABLE in predicate space"), was a PREDICATE-GRID SEARCH. None
was ever form-free bounded. The same conclusion has now been wrong TWICE by
exactly that mechanism:
    single-term kill      -> the max() family fixed it
    max-family "no signal"-> a form-free lookup fixed it (occupied@T4+1, +23)
    lookup "coin flip"    -> a one-clock-later key fixed it (pop@T4+2, 64/66)
So "inseparable in predicate space" is re-tested here as "separable by a
form-free lookup over TRAJECTORY keys", which upper-bounds any predicate.

METRIC: GO/PAUSE is ~98.5% GO, so ACCURACY IS MEANINGLESS - "always GO" scores
98.5% while getting every pause wrong. Scored as ERRORS = false-pause +
missed-pause, against the always-GO baseline (= the pause count). The permanent
baseline guard stays on.

CAUSALITY CAVEAT (stated, not hidden): the trajectory is the MODEL's. On the
model-early rows - the ones that matter - the model GOes, so its own T1 lands at
T4+2 and any occ@T4+k for k>=2 is contaminated by the model's own launch.
pop@T4+k is EU-driven and unaffected by the BIU launch, so it stays clean;
occ@T4+0/+1 are clean by construction (earliest possible T1 is T4+2). Keys are
tagged CLEAN / CONTAMINATED and reported separately. A crack that only appears
on contaminated keys is NOT a crack.

PROTOCOL: fit=fresh, hold=gz (the pre-registered one-time re-split, unchanged).
fit -> FREEZE -> score HOLD once.

Usage: python3 sw/class5_phase6.py
"""
import sys, json, itertools
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase5 import load, OCC

LOG = SW / "class5_phase6.log"
OUT = SW / "class5_phase6.json"

# key -> (extractor, clean?)
CLEAN_K = {}
for k in range(0, 5):
    CLEAN_K[f"pop@T4+{k}"] = (("pop_now", k), True)      # EU-driven: clean
for k in (0, 1):
    CLEAN_K[f"occ@T4+{k}"] = (("occupied", k), True)     # pre-launch: clean
    CLEAN_K[f"qcnt@T4+{k}"] = (("q_cnt", k), True)
for k in (2, 3, 4):
    CLEAN_K[f"occ@T4+{k}"] = (("occupied", k), False)    # post-launch: dirty
    CLEAN_K[f"qcnt@T4+{k}"] = (("q_cnt", k), False)


def getk(tj, fi, spec):
    f, k = spec
    t = tj.row.get(tj.t4 + k)
    return t[fi[f]] if t else None


def main():
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    meta, fi, allrows = load()
    nf = [x for x in allrows if x[0]["flush_win"] == 0
          and x[0]["label"] in ("go", "pause")]
    band = [x for x in nf if x[0][OCC] <= 4]
    FIT = [x for x in band if x[0]["src"] == "fresh"]
    HOLD = [x for x in band if x[0]["src"] != "fresh"]

    log("=== PHASE 6 / TASK B: form-free lookup on the DECISION function ===")
    for nm, s in (("FIT(fresh)", FIT), ("HOLD(gz)", HOLD)):
        g = sum(1 for x in s if x[0]["label"] == "go")
        p = len(s) - g
        log(f"  {nm}: n={len(s)} GO={g} PAUSE={p}  "
            f"=> always-GO baseline errors = {p}")
    log("  metric = ERRORS (false-pause + missed-pause). Accuracy is useless")
    log("  here: always-GO is 98.5% 'accurate' and 100% wrong on every pause.")
    log("  Fits so far (predicate grids): 15 errors FIT / 19 HOLD.\n")

    def wf(rec):
        return rec["pred_tw"]

    def evaluate(keyfn, rows_fit, rows_hold):
        tab = defaultdict(lambda: defaultdict(int))
        for rec, tj in rows_fit:
            tab[keyfn(rec, tj)][rec["label"]] += 1
        vote = {k: max(v, key=v.get) for k, v in tab.items()}
        # unseen key -> predict GO (the majority class)
        fe = sum(sum(v.values()) - max(v.values()) for v in tab.values())
        he = 0
        for rec, tj in rows_hold:
            p = vote.get(keyfn(rec, tj), "go")
            if p != rec["label"]:
                he += 1
        return fe, he, len(tab)

    # ---- single keys ----
    log("--- 1. SINGLE trajectory keys ---")
    log(f"    {'errs FIT':>9} {'errs HOLD':>10} {'cells':>6} {'clean':>6}  key")
    res = []
    for name, (spec, clean) in sorted(CLEAN_K.items()):
        fe, he, nc = evaluate(lambda r, t, s=spec: getk(t, fi, s), FIT, HOLD)
        res.append((he, fe, name, nc, clean))
    fe, he, nc = evaluate(lambda r, t: wf(r), FIT, HOLD)
    res.append((he, fe, "pred_tw (wait-frame)", nc, True))
    res.sort()
    for he, fe, name, nc, clean in res:
        log(f"    {fe:>9} {he:>10} {nc:>6} {'yes' if clean else 'DIRTY':>6}  {name}")

    # ---- combinations ----
    log("\n--- 2. COMBINATION keys ---")
    combos = [
        ("occ@T4+1 x pop@T4+2", lambda r, t: (getk(t, fi, ("occupied", 1)),
                                              getk(t, fi, ("pop_now", 2))), True),
        ("occ@T4+1 x tw", lambda r, t: (getk(t, fi, ("occupied", 1)), wf(r)), True),
        ("occ@T4+1 x pop@T4+2 x tw",
         lambda r, t: (getk(t, fi, ("occupied", 1)), getk(t, fi, ("pop_now", 2)),
                       wf(r)), True),
        ("occ@T4+1 x pop@T4+1", lambda r, t: (getk(t, fi, ("occupied", 1)),
                                              getk(t, fi, ("pop_now", 1))), True),
        ("occ@T4+0 x occ@T4+1", lambda r, t: (getk(t, fi, ("occupied", 0)),
                                              getk(t, fi, ("occupied", 1))), True),
        ("pop@T4+0..2", lambda r, t: tuple(getk(t, fi, ("pop_now", k))
                                           for k in range(3)), True),
        ("occ@T4+1 x pop@T4+0..2",
         lambda r, t: (getk(t, fi, ("occupied", 1)),) +
                      tuple(getk(t, fi, ("pop_now", k)) for k in range(3)), True),
        ("occ@T4+1 x qcnt@T4+1 x pop@T4+2",
         lambda r, t: (getk(t, fi, ("occupied", 1)), getk(t, fi, ("q_cnt", 1)),
                       getk(t, fi, ("pop_now", 2))), True),
        ("occ@T4+1 x occ@T4+2 (DIRTY)",
         lambda r, t: (getk(t, fi, ("occupied", 1)),
                       getk(t, fi, ("occupied", 2))), False),
    ]
    log(f"    {'errs FIT':>9} {'errs HOLD':>10} {'cells':>6} {'clean':>6}  key")
    cres = []
    for name, fn, clean in combos:
        fe, he, nc = evaluate(fn, FIT, HOLD)
        cres.append((he, fe, name, nc, clean))
    cres.sort()
    for he, fe, name, nc, clean in cres:
        log(f"    {fe:>9} {he:>10} {nc:>6} {'yes' if clean else 'DIRTY':>6}  {name}")

    bh, bf, bname, bnc, bclean = cres[0]
    log(f"\n>> BEST combination: {bname}  FIT {bf} errs, HOLD {bh} errs "
        f"({bnc} cells, {'clean' if bclean else 'CONTAMINATED'})")
    log(f"   always-GO baseline HOLD errors: "
        f"{sum(1 for x in HOLD if x[0]['label']=='pause')}")
    log(f"   predicate-grid fits to date: 19 HOLD errors")

    # ---- the model-early rows: where the mass is ----
    log("\n--- 3. THE MODEL-EARLY ROWS (chip pauses, model GOes) ---")
    log("    This is the dominant remaining mass (~2-3 clocks each).")
    me = [x for x in band if x[0]["label"] == "pause"
          and x[0]["model_cidle"] is not None and x[0]["model_cidle"] <= 1]
    log(f"    model-early rows in low+mid non-flush: {len(me)}")
    if me:
        c = defaultdict(int)
        for rec, tj in me:
            c[(rec[OCC], rec["pred_tw"])] += 1
        log(f"    by (occ@T4+1, tw): {dict(sorted(c.items()))}")
        mf = [x for x in me if x[0]["src"] == "fresh"]
        mh = [x for x in me if x[0]["src"] != "fresh"]
        log(f"    FIT {len(mf)} / HOLD {len(mh)}")
        for name, fn, clean in combos:
            if not clean:
                continue
            tab = defaultdict(lambda: defaultdict(int))
            for rec, tj in FIT:
                tab[fn(rec, tj)][rec["label"]] += 1
            vote = {k: max(v, key=v.get) for k, v in tab.items()}
            got = sum(1 for rec, tj in mh
                      if vote.get(fn(rec, tj), "go") == "pause")
            log(f"      {name:34s}: recovers {got}/{len(mh)} HOLD model-early rows")

    # ---- q0/q1 starved cell re-audit ----
    log("\n--- 4. RE-AUDIT: the q0/q1 STARVED cell (long called unminable) ---")
    log("    Previously key-cell analysis over SNAPSHOT keys only; trajectory")
    log("    keys (pop@T4+k, occ@T4+k) did not exist then.")
    q01 = [x for x in nf if x[0]["cnt_q_cnt"] <= 1]
    g = sum(1 for x in q01 if x[0]["label"] == "go")
    p = len(q01) - g
    log(f"    cell: {g} GO / {p} PAUSE (n={len(q01)})")
    qf = [x for x in q01 if x[0]["src"] == "fresh"]
    qh = [x for x in q01 if x[0]["src"] != "fresh"]
    ph = sum(1 for x in qh if x[0]["label"] == "pause")
    log(f"    FIT {len(qf)} (pause {sum(1 for x in qf if x[0]['label']=='pause')})"
        f" / HOLD {len(qh)} (pause {ph})")
    log(f"    always-GO baseline HOLD errors: {ph}")
    qres = []
    for name, fn, clean in combos:
        if not clean:
            continue
        fe, he, nc = evaluate(fn, qf, qh)
        qres.append((he, fe, name, nc))
    for name, (spec, clean) in sorted(CLEAN_K.items()):
        if not clean:
            continue
        fe, he, nc = evaluate(lambda r, t, s=spec: getk(t, fi, s), qf, qh)
        qres.append((he, fe, name, nc))
    qres.sort()
    log(f"    {'errs FIT':>9} {'errs HOLD':>10} {'cells':>6}  key")
    for he, fe, name, nc in qres[:6]:
        log(f"    {fe:>9} {he:>10} {nc:>6}  {name}")

    json.dump(dict(best_combo=bname, best_fit_errs=bf, best_hold_errs=bh,
                   baseline_hold=sum(1 for x in HOLD if x[0]["label"] == "pause")),
              OUT.open("w"), indent=1, default=str)
    log(f"\nwrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
