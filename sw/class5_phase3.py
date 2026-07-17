#!/usr/bin/env python3
"""PHASE 2 / FIT B: rescoped shadow-FSM sweep (coordinator rescope, post-165aae9).

FIT A (sw/class5_phase2.py) is FROZEN and reported as-is; it is NOT retro-edited.
This is a SEPARATE, LABELLED fit under the rescope:

  1. reset-anchored grids DROPPED (t4_clk%2 splits nothing; grid_phase@T4 == 1
     by construction). Anchors are fetch/bus/flush-relative only.
     NOTE: with period=1 every clock is an eval slot, so the phase anchor is
     VACUOUS - such variants are not "reset-anchored" in any meaningful sense
     and are retained under anchor=lastT4 (the canonical anchor-free form).
  2. pred_tw is a MANDATORY COVARIATE / CROSS-CHECK, never a term in the rule.
     The winner must reproduce the E2 tw tables EMERGENTLY. Any rule keying on
     tw directly is a curve-fit and is rejected by construction: no demand
     condition in this sweep can see tw.
  3. plain threshold-onset is already known to fail -> the sweep is extended
     with GRID-QUANTIZED evaluation (period 2, fetch/flush-anchored) AND
     COMPOSITE demand conditions (eu_consuming, in-flight, pop cadence, aged).
     A kill is only reported after these are exhausted.
  4. FIT = low+mid non-flush (occ<=4). Blocked band (occ>=5) is a FROZEN
     VALIDATION set, never fitted (heavy-tailed residuals would dominate).
  5. flush rows are TABULATED, never fitted (the arm is already chip-exact).

DISCIPLINE: select on gz-disc ONLY -> FREEZE -> score gz-held and fresh once.
Selection metric is fixed BEFORE scoring held/fresh, and follows the
coordinator's stated PRIZE (the queue-demand event => exact cidle on non-flush
low+mid pause rows), with GO/PAUSE errors as the tie-break.

Usage: python3 sw/class5_phase3.py
"""
import sys, json, gzip, itertools, time
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase2 import load, split, Traj, OCC, AGE

LOG = SW / "class5_phase3.log"
OUT = SW / "class5_phase3.json"

T_T1, T_T3 = 1, 3


# ---- demand conditions. NONE of these can see pred_tw (item 2). ----
def _mk():
    D = {}

    def add(n, f):
        D[n] = f
    add("q_cnt<=1", lambda t, f: t[f["q_cnt"]] <= 1)
    add("q_cnt<=2", lambda t, f: t[f["q_cnt"]] <= 2)
    add("q_avl<=1", lambda t, f: t[f["q_avl"]] <= 1)
    add("q_avl<=2", lambda t, f: t[f["q_avl"]] <= 2)
    add("cnt_next<=1", lambda t, f: t[f["cnt_next"]] <= 1)
    add("cnt_next<=2", lambda t, f: t[f["cnt_next"]] <= 2)
    add("occupied<=2", lambda t, f: t[f["occupied"]] <= 2)
    add("occupied<=3", lambda t, f: t[f["occupied"]] <= 3)
    add("occupied<=4", lambda t, f: t[f["occupied"]] <= 4)
    # ---- composites (item 3) ----
    add("cnt_next<=2&!euCons",
        lambda t, f: t[f["cnt_next"]] <= 2 and not t[f["eu_consuming"]])
    add("cnt_next<=2&euCons",
        lambda t, f: t[f["cnt_next"]] <= 2 and t[f["eu_consuming"]])
    add("cnt_next<=2&!euReq",
        lambda t, f: t[f["cnt_next"]] <= 2 and not t[f["eu_req"]])
    add("cnt_next<=2&!euHold",
        lambda t, f: t[f["cnt_next"]] <= 2 and not t[f["eu_hold"]])
    add("cnt_next<=2&!(euReq|euHold)",
        lambda t, f: t[f["cnt_next"]] <= 2 and not (t[f["eu_req"]] or t[f["eu_hold"]]))
    add("cnt_next<=2|pop",
        lambda t, f: t[f["cnt_next"]] <= 2 or t[f["pop_now"]] > 0)
    add("cnt_next<=2&pop",
        lambda t, f: t[f["cnt_next"]] <= 2 and t[f["pop_now"]] > 0)
    add("cnt_next<=2&aged0",
        lambda t, f: t[f["cnt_next"]] <= 2 and t[f["q_aged"]] == 0)
    add("cnt_next<=2&infl0",
        lambda t, f: t[f["cnt_next"]] <= 2 and (t[f["occupied"]] - t[f["q_cnt"]]) <= 0)
    add("occupied<=3&!(euReq|euHold)",
        lambda t, f: t[f["occupied"]] <= 3 and not (t[f["eu_req"]] or t[f["eu_hold"]]))
    add("occupied<=4&!(euReq|euHold)",
        lambda t, f: t[f["occupied"]] <= 4 and not (t[f["eu_req"]] or t[f["eu_hold"]]))
    add("occupied<=3&infl0",
        lambda t, f: t[f["occupied"]] <= 3 and (t[f["occupied"]] - t[f["q_cnt"]]) <= 0)
    add("occupied<=4&aged0",
        lambda t, f: t[f["occupied"]] <= 4 and t[f["q_aged"]] == 0)
    add("q_cnt<=2&!(euReq|euHold)",
        lambda t, f: t[f["q_cnt"]] <= 2 and not (t[f["eu_req"]] or t[f["eu_hold"]]))
    add("pop", lambda t, f: t[f["pop_now"]] > 0)
    add("occupied<=4&pop",
        lambda t, f: t[f["occupied"]] <= 4 and t[f["pop_now"]] > 0)
    add("infl>=1", lambda t, f: (t[f["occupied"]] - t[f["q_cnt"]]) >= 1)
    return D


DEM = _mk()
PERIODS = [1, 2]
ANCHORS = ["lastT1", "lastT4", "lastflush"]      # reset DROPPED (item 1)
OFFSETS = [0, 1]
CLEARS = ["noD", "issue", "both"]
READS = ["T4", "T4+1", "T3rdy"]
LAGS = [2, 3]


def anchor_clk(tj, fi, anch):
    if anch == "lastT4":
        return tj.t4
    if anch == "lastT1":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["t"]] == T_T1]
        return c[-1] if c else None
    if anch == "lastflush":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["q_flush"]]]
        return c[-1] if c else None
    raise KeyError(anch)


def read_clk(tj, fi, rd):
    if rd == "T4":
        return tj.t4
    if rd == "T4+1":
        return tj.t4 + 1
    if rd == "T3rdy":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["t"]] == T_T3]
        return c[-1] if c else None
    raise KeyError(rd)


def simulate(tj, fi, v):
    dn, per, anch, off, clr, rd, lag = v
    d = DEM[dn]
    a = anchor_clk(tj, fi, anch)
    rp = read_clk(tj, fi, rd)
    if a is None or rp is None or rp < tj.lo:
        return None, None, False

    def is_eval(k):
        return (k - a) % per == (off % per)

    pend = 0
    for k in range(tj.lo, rp + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        if is_eval(k):
            if d(t, fi):
                pend = 1
            elif clr in ("noD", "both"):
                pend = 0
        if clr in ("issue", "both") and t[fi["t"]] == T_T1 and k != rp:
            pend = 0
    if pend:
        return "go", (0 if tj.pred_tw == 0 else 1), True
    ds = None
    for k in range(rp, tj.hi + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        if is_eval(k) and d(t, fi):
            ds = k
            break
    if ds is None:
        return "pause", None, True
    L = None
    for k in range(max(ds + lag, tj.t4 + 1), tj.hi + 1):
        if is_eval(k):
            L = k
            break
    if L is None:
        return "pause", None, True
    return "pause", L - tj.t4 - 1, True


def score(rows, fi, v):
    r = dict(n=0, uneval=0, gg=0, gp=0, pg=0, pp=0, ex=0, ex_n=0, nocid=0,
             err_cells=defaultdict(int))
    for rec, tj in rows:
        r["n"] += 1
        pl, pc, ok = simulate(tj, fi, v)
        if not ok:
            r["uneval"] += 1
            continue
        cl = rec["label"]
        if cl == "go":
            if pl == "go":
                r["gg"] += 1
            else:
                r["gp"] += 1
                r["err_cells"][(rec[OCC], rec[AGE])] += 1
        else:
            if pl == "go":
                r["pg"] += 1
                r["err_cells"][(rec[OCC], rec[AGE])] += 1
            else:
                r["pp"] += 1
            if pc is None:
                r["nocid"] += 1
            else:
                r["ex_n"] += 1
                r["ex"] += int(pc == rec["cidle"])
    r["errs"] = r["gp"] + r["pg"]
    r["exrate"] = r["ex"] / max(1, r["ex_n"])
    # TOTAL MISPREDICTIONS - the single honest scalar, fixed as THE selection
    # metric. Rate-style metrics are degenerate here: a variant that predicts
    # PAUSE for everything scores 9/9=100% exact on the 9 pause rows it can
    # still resolve while committing 4198 GO/PAUSE errors, and a variant whose
    # anchor is usually undefined scores a tiny trivially-GO subset. Counting
    # every row the FSM gets wrong - wrong branch, wrong cidle, or a pause whose
    # resume never lands inside the trajectory - cannot be gamed that way.
    r["tot"] = r["gp"] + r["pg"] + (r["ex_n"] - r["ex"]) + r["nocid"]
    return r


def vname(v):
    return (f"D={v[0]} period={v[1]} anchor={v[2]} offset={v[3]} "
            f"clear={v[4]} read={v[5]} lag={v[6]}")


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
    fl = [x for x in allrows if x[0]["flush_win"] == 1]

    log("=== PHASE 2 / FIT B (RESCOPED) - separate labelled fit; Fit A frozen "
        "and reported as-is ===")
    # band split (item 4)
    band = [x for x in nf if x[0][OCC] <= 4]
    blocked = [x for x in nf if x[0][OCC] >= 5]
    log(f"non-flush rows {len(nf)}: low+mid(occ<=4) FIT={len(band)}  "
        f"blocked(occ>=5) VALIDATION-ONLY={len(blocked)}")
    disc, held, fresh = split(band)
    log(f"fit=gz-disc {len(disc)} | frozen tests: gz-held {len(held)}, "
        f"fresh {len(fresh)}")

    variants = list(itertools.product(sorted(DEM), PERIODS, ANCHORS, OFFSETS,
                                      CLEARS, READS, LAGS))
    # period=1 -> offset vacuous AND anchor vacuous: keep one canonical form
    variants = [v for v in variants
                if not (v[1] == 1 and (v[3] == 1 or v[2] != "lastT4"))]
    log(f"\nsweeping {len(variants)} variants on gz-disc ONLY")
    log("SELECTION METRIC (fixed, before any held/fresh scoring): TOTAL\n"
        "  MISPREDICTIONS on non-flush low+mid = GO/PAUSE errors + wrong-cidle\n"
        "  on pause rows + pauses whose resume never lands in the trajectory.\n"
        "  This encodes the coordinator's PRIZE (the queue-demand event => exact\n"
        "  cidle) while being immune to the degenerate-subset gaming that rate\n"
        "  metrics permit (predict-PAUSE-always scores 9/9=100% exact with 4198\n"
        "  GO/PAUSE errors; a rarely-defined anchor scores a trivially-GO subset).")

    t0 = time.time()
    elig = []
    for v in variants:
        s = score(disc, fi, v)
        if s["uneval"] == 0:
            elig.append((v, s))
    log(f"  ({time.time()-t0:.0f}s) eligible (evaluable on every fit row): "
        f"{len(elig)}/{len(variants)}")
    elig.sort(key=lambda x: (x[1]["tot"], x[1]["errs"]))

    log("\n--- TOP 10 on gz-disc (ranked by TOTAL mispredictions) ---")
    log(f"    {'total':>6} {'errs':>5} {'exact':>11} {'noTraj':>6}  variant")
    for v, s in elig[:10]:
        log(f"    {s['tot']:>6} {s['errs']:>5} "
            f"{str(s['ex'])+'/'+str(s['ex_n']):>11} {s['nocid']:>6}  {vname(v)}")

    best_v, best_s = elig[0]
    run_v, run_s = elig[1]
    log(f"\n>> FROZEN (Fit B), selected on gz-disc alone:\n   {vname(best_v)}")
    log(f"   disc: TOTAL mispredictions={best_s['tot']} of {best_s['n']} | "
        f"GO/PAUSE errs={best_s['errs']} (GO->PAUSE={best_s['gp']} "
        f"PAUSE->GO={best_s['pg']}) | exact-cidle={best_s['ex']}/{best_s['ex_n']}"
        f" | beyond-traj={best_s['nocid']}")
    log(f"   RUNNER-UP:\n   {vname(run_v)}")
    log(f"   disc: TOTAL={run_s['tot']} errs={run_s['errs']} "
        f"exact-cidle={run_s['ex']}/{run_s['ex_n']} beyond-traj={run_s['nocid']}")

    # ---------------- FREEZE ----------------
    log("\n=== FROZEN. gz-held and fresh scored once, no further tuning. ===")
    final = {}
    for nm, s in (("disc", disc), ("held", held), ("fresh", fresh)):
        sc = score(s, fi, best_v)
        final[nm] = sc
        log(f"\n--- {nm} (non-flush low+mid, n={sc['n']}) ---")
        log("    confusion:            pred GO   pred PAUSE")
        log(f"      chip GO     {sc['gg']:>12} {sc['gp']:>12}")
        log(f"      chip PAUSE  {sc['pg']:>12} {sc['pp']:>12}")
        log(f"    TOTAL mispredictions: {sc['tot']} of {sc['n']}")
        log(f"    GO/PAUSE errors: {sc['errs']}    exact-cidle on pause rows: "
            f"{sc['ex']}/{sc['ex_n']} ({100*sc['exrate']:.1f}%)"
            f"   beyond-traj: {sc['nocid']}")
        if sc["err_cells"]:
            log(f"    error cells (occ,age): {dict(sorted(sc['err_cells'].items()))}")

    # ---------------- E2: emergent tw tables (item 2) ----------------
    log("\n=== E2 CROSS-CHECK: does the winner reproduce the pred_tw gradient "
        "EMERGENTLY? ===")
    log("    (the rule contains NO tw term - tw is a covariate, never an input)")
    log("\n    non-flush low-band pause rows, cidle 3-vs-4 by predecessor Tw:")
    log(f"    {'tw':>3}  {'chip 3:4':>10}  {'pred 3:4':>10}  {'exact':>9}")
    lb = [x for x in nf if x[0][OCC] <= 4 and x[0]["label"] == "pause"]
    for tw in sorted({x[0]["pred_tw"] for x in lb}):
        sub = [x for x in lb if x[0]["pred_tw"] == tw]
        c3 = sum(1 for x in sub if x[0]["cidle"] == 3)
        c4 = sum(1 for x in sub if x[0]["cidle"] == 4)
        p3 = p4 = ex = exn = 0
        for rec, tj in sub:
            pl, pc, ok = simulate(tj, fi, best_v)
            if not ok:
                continue
            if pc == 3:
                p3 += 1
            elif pc == 4:
                p4 += 1
            if pc is not None:
                exn += 1
                ex += int(pc == rec["cidle"])
        log(f"    {tw:>3}  {str(c3)+':'+str(c4):>10}  {str(p3)+':'+str(p4):>10}"
            f"  {str(ex)+'/'+str(exn):>9}")
    log("\n    GO/PAUSE extinction with tw (non-flush low+mid, waited preds):")
    log(f"    {'tw':>3}  {'chip GO:PAUSE':>14}  {'pred GO:PAUSE':>14}")
    lm = [x for x in nf if x[0][OCC] <= 4 and x[0]["pred_tw"] >= 1]
    for tw in sorted({x[0]["pred_tw"] for x in lm}):
        sub = [x for x in lm if x[0]["pred_tw"] == tw]
        cg = sum(1 for x in sub if x[0]["label"] == "go")
        cp = len(sub) - cg
        pg = pp = 0
        for rec, tj in sub:
            pl, pc, ok = simulate(tj, fi, best_v)
            if ok and pl == "go":
                pg += 1
            elif ok:
                pp += 1
        log(f"    {tw:>3}  {str(cg)+':'+str(cp):>14}  {str(pg)+':'+str(pp):>14}")

    # ---------------- blocked band: frozen validation (item 4) ----------------
    log("\n=== BLOCKED BAND (occ>=5): FROZEN VALIDATION, never fitted ===")
    sc = score(blocked, fi, best_v)
    log(f"  n={sc['n']} errs={sc['errs']} exact-cidle={sc['ex']}/{sc['ex_n']} "
        f"({100*sc['exrate']:.1f}%)  beyond-traj={sc['nocid']} "
        f"uneval={sc['uneval']}")
    log("  (a fitted low+mid demand definition ALSO predicting blocked-band")
    log("   resumes would be the strongest evidence one rule spans all bands)")

    # ---------------- flush: tabulate only (item 5) ----------------
    log("\n=== FLUSH ARM: TABULATED, never fitted (item 5) ===")
    tab = defaultdict(lambda: defaultdict(int))
    dm = defaultdict(int)
    for rec, tj in fl:
        off = (rec["flush_clk"] - rec["t4_clk"]) if rec["flush_clk"] is not None else None
        tab[off][rec["cidle"]] += 1
        dm[rec["model_cidle"] - rec["cidle"]] += 1
    log("  chip cidle by flush offset (flush_clk - t4_clk):")
    for off in sorted(tab, key=lambda x: (x is None, x)):
        log(f"    offset {str(off):>4}: {dict(sorted(tab[off].items()))}")
    log(f"  model_cidle - chip_cidle over ALL {len(fl)} flush rows: "
        f"{dict(sorted(dm.items()))}")
    log("  => the flush arm is already chip-exact at HEAD; nothing to build.")

    json.dump(dict(fit="B (rescoped)", variant=vname(best_v),
                   runner_up=vname(run_v),
                   final={k: {kk: ({str(a): b for a, b in vv.items()}
                                   if kk == "err_cells" else vv)
                              for kk, vv in v.items()}
                          for k, v in final.items()}),
              OUT.open("w"), indent=1, default=str)
    log(f"\nwrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
