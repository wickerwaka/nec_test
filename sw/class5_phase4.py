#!/usr/bin/env python3
"""PHASE 2 / FIT C: the max() TWO-TERM family (coordinator rescope #2).

WHY THIS EXISTS: Fits A and B swept the SINGLE-TERM family
    T1 = quantize(demand_slot + lag)
and killed it. That kill STANDS, but only for the single-term family. The
architect's v3 hypothesis was actually TWO-TERM:
    T1 = max( pred_T4 + 1 + floor , D0 + L + K*[tw>=1] )
and the §5 sweep spec did not express the max(). The reported fingerprint of the
single-term winner - it NEVER predicts cidle 4 at any tw - is exactly what a
missing floor/deadline max() looks like. So the broader claim "the queue-demand
event is not a trajectory projection" was NOT established and is not claimed.

THE THREE tw REGIMES, from ONE max() - not a mode switch, no regime term:
  tw0    deadline already passed        -> GO
  tw1-3  DEADLINE regime: cidle = D0 + S - T4 - 1   <- the residual lives here
  tw>=4  FLOOR regime: the long wait drains the queue early, so D0 << T4, the
         deadline term goes small and the floor clamps -> cidle = 3
The Phase-2 partial (cnt_next<=2, read T4+1, lag 2: 29/29 on occ3/age1-2) is now
explained: those cells lie entirely in the deadline regime, so a pure-deadline
rule is exact ON them and must collapse off them. Used below as a known-good
anchor.

STRUCTURE (a fact about the arithmetic, stated rather than assumed): max(floor,
.) with floor>=2 can never emit cidle 1, so GO cannot come from the max(). The
GO/PAUSE branch is therefore a SEPARATE condition, exactly as the architect's own
"false-pause on 13744 waited GOs: 130 (0.9%)" implies. Branch-errors and
pause-cidle are independent, so they are swept separately (81 + 810) rather than
as a 45927-way joint. This is an efficiency factorisation, not a scope cut.

TRAJECTORY COVERAGE - why this family is measurable where the last one was not:
D0 is constrained to <= T4+1, which lies entirely inside the recorded lead-in
([T4-8, T1_next]). The single-term sweep had to look FORWARD past the model's own
resume and lost 32-380 rows to truncation. This family loses none.

KNOWN DEGENERACY - NOT fitted around: every low-band pause row has tw>=1, so
only S = L+K is constrained; (L=4,K=0) == (L=3,K=1) == (L=2,K=2) are the same
model. S is reported as a constrained SUM. No split is claimed. Only tw=0 pause
cells could break the ridge and the low band has none. That is a factorial job.

PRE-REGISTERED ONE-TIME RE-SPLIT (declared before fitting, authorized):
  FIT   = fresh (90008-17 / 91006-11)   [26 rows in occ3/age1-2 vs gz-disc's 7]
  HOLD  = gz (90000-07 disc + 91000-05 held)
Seeds stay disjoint. One-time; roles are not iterated. The original split is also
reported for comparison. Nothing here is shipped on a re-split alone - the chip
factorial is the true validator.

Usage: python3 sw/class5_phase4.py
"""
import sys, json, itertools, time
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase2 import load, Traj, OCC, AGE
from class5_phase3 import DEM, anchor_clk, read_clk, T_T1, T_T3

LOG = SW / "class5_phase4.log"
OUT = SW / "class5_phase4.json"

SS = [2, 3, 4, 5, 6]          # S = L + K (constrained sum; NOT split)
FLOORS = [2, 3, 4]
D0MODES = ["onset", "level"]
READS = ["T4", "T4+1", "T3rdy"]


def d0_of(tj, fi, d, mode, cap):
    """Demand onset D0, read at <= cap (= T4+1). Returns None if the demand
    never onsets inside the recorded lead-in (=> deadline term does not bind).

    mode 'onset' = last RISING EDGE of D at k <= cap (a demand EVENT).
    mode 'level' = last clock <= cap at which D merely HOLDS.
    Both are searched only in [traj_lo, cap], which is fully recorded."""
    hi = min(cap, tj.hi)
    last = None
    for k in range(tj.lo, hi + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        cur = d(t, fi)
        if mode == "level":
            if cur:
                last = k
        else:
            p = tj.row.get(k - 1)
            prev = d(p, fi) if p is not None else False
            if cur and not prev:
                last = k
    return last


def pred_cidle(tj, fi, dn, S, floor, mode):
    """cidle for a PAUSE row under the max() two-term rule:
         T1 = max(T4 + 1 + floor, D0 + S)
         cidle = T1 - T4 - 1 = max(floor, D0 + S - T4 - 1)
    D0 is capped at T4+1 per the hypothesis."""
    D0 = d0_of(tj, fi, DEM[dn], mode, tj.t4 + 1)
    if D0 is None:
        return floor                      # deadline never binds -> floor
    return max(floor, D0 + S - tj.t4 - 1)


def branch_go(tj, fi, dn, rd):
    """Separate GO/PAUSE branch: GO iff demand holds at the read point.
    (period=1 / clear=noD form: PEND at read == D at read.)"""
    rp = read_clk(tj, fi, rd)
    if rp is None or rp < tj.lo:
        return None
    t = tj.row.get(rp)
    if t is None:
        return None
    return bool(DEM[dn](t, fi))


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
    band = [x for x in nf if x[0][OCC] <= 4]

    def is_fresh(x):
        return x[0]["src"] == "fresh"

    FIT = [x for x in band if is_fresh(x)]
    HOLD = [x for x in band if not is_fresh(x)]
    log("=== PHASE 2 / FIT C: max() TWO-TERM family ===")
    log("PRE-REGISTERED RE-SPLIT (declared before fitting, one-time):")
    log(f"  FIT  = fresh  n={len(FIT)}")
    log(f"  HOLD = gz     n={len(HOLD)}")
    log("  (original split also reported below for comparison)")
    log("S = L+K is a CONSTRAINED SUM. L and K are unidentifiable from this")
    log("corpus (every low-band pause row has tw>=1). No split is claimed.\n")

    fitp = [x for x in FIT if x[0]["label"] == "pause"]
    holdp = [x for x in HOLD if x[0]["label"] == "pause"]
    log(f"pause rows: FIT={len(fitp)} HOLD={len(holdp)}")

    def tw13(rows):
        return [x for x in rows if 1 <= x[0]["pred_tw"] <= 3]
    log(f"  of which tw1-3 (the DEADLINE regime, the target): "
        f"FIT={len(tw13(fitp))} HOLD={len(tw13(holdp))}")

    # ---------------- 1. cidle formula sweep (on chip-PAUSE rows) ----------
    tgt0 = tw13(fitp)
    log("\n--- 1. DEADLINE/FLOOR sweep: exact cidle on chip-PAUSE rows ---")
    log("    METRIC (fixed): exact-cidle over ALL tw on FRESH pause rows -")
    log("    the architect's own headline (104/174), tie-broken by tw1-3.")
    log("    NOT metricised on tw1-3 alone: tw1-3 is cidle-4-dominant, so a")
    log("    'predict 4 always' rule scores ~69% there while getting the tw>=4")
    log("    FLOOR regime exactly backwards (1/22). Trivial baselines are")
    log("    printed below precisely so that gaming is visible, not inferred.")
    b3 = sum(1 for rec, tj in fitp if rec["cidle"] == 3)
    b4 = sum(1 for rec, tj in fitp if rec["cidle"] == 4)
    b3t = sum(1 for rec, tj in tgt0 if rec["cidle"] == 3)
    b4t = sum(1 for rec, tj in tgt0 if rec["cidle"] == 4)
    log(f"    TRIVIAL BASELINES on FIT: always-3 = {b3}/{len(fitp)} all-tw "
        f"({b3t}/{len(tgt0)} tw1-3);  always-4 = {b4}/{len(fitp)} all-tw "
        f"({b4t}/{len(tgt0)} tw1-3)")
    log("    A candidate must beat BOTH to be meaningful.")
    variants = list(itertools.product(sorted(DEM), SS, FLOORS, D0MODES))
    t0 = time.time()
    res = []
    tgt = tw13(fitp)
    for (dn, S, floor, mode) in variants:
        ex13 = sum(1 for rec, tj in tgt
                   if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
        exall = sum(1 for rec, tj in fitp
                    if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
        res.append((ex13, exall, (dn, S, floor, mode)))
    # rank by ALL-tw exact (primary), then tw1-3 (tie-break)
    res.sort(key=lambda x: (-x[1], -x[0]))
    log(f"    ({time.time()-t0:.0f}s) {len(variants)} variants")
    log(f"\n    {'all tw':>9} {'tw1-3':>9}  variant   [ranked by all-tw]")
    for ex13, exall, v in res[:10]:
        log(f"    {str(exall)+'/'+str(len(fitp)):>9} "
            f"{str(ex13)+'/'+str(len(tgt)):>9}  "
            f"D={v[0]} S=L+K={v[1]} floor={v[2]} D0={v[3]}")
    best = res[0][2]
    runner = res[1][2] if len(res) > 1 else None
    log(f"\n>> FROZEN cidle rule (fit on FRESH alone): D={best[0]} "
        f"S=L+K={best[1]} floor={best[2]} D0={best[3]}")
    log(f"   FIT: all-tw {res[0][1]}/{len(fitp)}  tw1-3 {res[0][0]}/{len(tgt)}")
    if runner:
        log(f"   RUNNER-UP: D={runner[0]} S=L+K={runner[1]} floor={runner[2]} "
            f"D0={runner[3]}  (all-tw {res[1][1]}/{len(fitp)}, "
            f"tw1-3 {res[1][0]}/{len(tgt)})")

    # ---------------- 2. branch sweep (GO/PAUSE) ----------
    log("\n--- 2. GO/PAUSE branch sweep (independent of the cidle rule) ---")
    bres = []
    for dn in sorted(DEM):
        for rd in READS:
            err = un = 0
            for rec, tj in FIT:
                g = branch_go(tj, fi, dn, rd)
                if g is None:
                    un += 1
                    continue
                if (rec["label"] == "go") != g:
                    err += 1
            bres.append((un, err, dn, rd))
    bres.sort(key=lambda x: (x[0], x[1]))
    log(f"    {'errs':>6} {'uneval':>7}  branch")
    for un, err, dn, rd in bres[:6]:
        log(f"    {err:>6} {un:>7}  GO iff {dn} @ {rd}")
    bun, berr, bdn, brd = bres[0]
    log(f"\n>> FROZEN branch: GO iff {bdn} @ {brd}  (FIT errs={berr})")

    # ---------------- FREEZE ----------------
    log("\n=== FROZEN. HOLD (gz) scored once. No threshold touched. ===")
    dn, S, floor, mode = best

    def full(rows, nm):
        gg = gp = pg = pp = 0
        ex = exn = 0
        for rec, tj in rows:
            g = branch_go(tj, fi, bdn, brd)
            pl = "go" if g else "pause"
            cl = rec["label"]
            if cl == "go":
                if pl == "go":
                    gg += 1
                else:
                    gp += 1
            else:
                if pl == "go":
                    pg += 1
                else:
                    pp += 1
                exn += 1
                ex += int(pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
        log(f"\n--- {nm} (non-flush low+mid, n={len(rows)}) ---")
        log("    confusion:            pred GO   pred PAUSE")
        log(f"      chip GO     {gg:>12} {gp:>12}")
        log(f"      chip PAUSE  {pg:>12} {pp:>12}")
        log(f"    GO/PAUSE errors: {gp+pg}   (false-pause on waited GOs: {gp})")
        log(f"    exact cidle on chip-PAUSE rows: {ex}/{exn} "
            f"({100*ex/max(1,exn):.1f}%)")
        return dict(gg=gg, gp=gp, pg=pg, pp=pp, ex=ex, exn=exn)

    fin = {"FIT(fresh)": full(FIT, "FIT (fresh)"),
           "HOLD(gz)": full(HOLD, "HOLD (gz) - scored ONCE")}

    # ---------------- per-tw, the decisive table ----------------
    log("\n=== PER-tw exact cidle (chip-PAUSE rows) - the regime structure ===")
    log("    (ONE max() rule; no regime term, no tw term in the demand def)")
    for nm, rows in (("FIT(fresh)", fitp), ("HOLD(gz)", holdp),
                     ("POOLED", fitp + holdp)):
        log(f"\n    {nm}:")
        log(f"      {'tw':>3} {'n':>4} {'exact':>9}  {'chip 3:4':>9}  {'pred 3:4':>9}")
        for tw in sorted({x[0]["pred_tw"] for x in rows}):
            sub = [x for x in rows if x[0]["pred_tw"] == tw]
            ex = sum(1 for rec, tj in sub
                     if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
            c3 = sum(1 for x in sub if x[0]["cidle"] == 3)
            c4 = sum(1 for x in sub if x[0]["cidle"] == 4)
            p3 = sum(1 for rec, tj in sub
                     if pred_cidle(tj, fi, dn, S, floor, mode) == 3)
            p4 = sum(1 for rec, tj in sub
                     if pred_cidle(tj, fi, dn, S, floor, mode) == 4)
            log(f"      {tw:>3} {len(sub):>4} {str(ex)+'/'+str(len(sub)):>9}  "
                f"{str(c3)+':'+str(c4):>9}  {str(p3)+':'+str(p4):>9}")

    # ---------------- L+K ridge ----------------
    log("\n=== L+K RIDGE (the degeneracy, reported not fitted around) ===")
    log("    exact-cidle on tw1-3 FIT rows as S=L+K varies, best D/floor/D0 held:")
    for s in SS:
        ex = sum(1 for rec, tj in tgt
                 if pred_cidle(tj, fi, dn, s, floor, mode) == rec["cidle"])
        log(f"      S=L+K={s}: {ex}/{len(tgt)}")
    log("    Every (L,K) with L+K=S is the SAME model on this corpus: all")
    log("    low-band pause rows have tw>=1, so K*[tw>=1] is a constant. Only")
    log("    tw=0 pause cells could separate L from K and the low band has none.")

    # ---------------- original split, for comparison ----------------
    log("\n=== ORIGINAL SPLIT (gz-disc fit / gz-held+fresh), for comparison ===")
    od = [x for x in band if x[0]["src"] == "gz" and x[0]["tag"] == "disc"]
    oh = [x for x in band if not (x[0]["src"] == "gz" and x[0]["tag"] == "disc")]
    for nm, rows in (("gz-disc", od), ("held+fresh", oh)):
        p = [x for x in rows if x[0]["label"] == "pause"]
        ex = sum(1 for rec, tj in p
                 if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
        t3 = tw13(p)
        ex3 = sum(1 for rec, tj in t3
                  if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
        log(f"    {nm:12s}: exact cidle {ex}/{len(p)} "
            f"({100*ex/max(1,len(p)):.1f}%)   tw1-3: {ex3}/{len(t3)}")
    log("    (the FROZEN rule above, evaluated on the original split - NOT refit)")

    # ---------------- known-good anchor ----------------
    log("\n=== ANCHOR: occ3/age1-2 (the Phase-2 partial's cells) ===")
    a = [x for x in nf if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2
         and x[0]["label"] == "pause"]
    ex = sum(1 for rec, tj in a
             if pred_cidle(tj, fi, dn, S, floor, mode) == rec["cidle"])
    log(f"    exact cidle {ex}/{len(a)}  (pure-deadline rule got 29/29 here;")
    log("     these cells are entirely in the deadline regime)")

    json.dump(dict(fit="C (max two-term)", cidle_rule=dict(
        D=dn, S_sum_L_plus_K=S, floor=floor, D0=mode),
        branch=dict(D=bdn, read=brd), final=fin,
        note="L and K unidentifiable; S=L+K reported as a sum"),
        OUT.open("w"), indent=1, default=str)
    log(f"\nwrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
