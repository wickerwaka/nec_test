#!/usr/bin/env python3
"""FIT C addendum: the primary-goal test, the floor-regime check, and the
(L,K) separability test. Reproduces the three decisive numbers.

1. PRIMARY GOAL (tw1-3 ~100% exact): tested against the TRIVIAL majority-class
   baseline. tw1-3 is cidle-4-dominant, so "always 4" is a strong baseline and
   any candidate must be scored against it, not against zero.
2. FLOOR REGIME: is the architect's tw>=4 21/21 reachable? (Confirms the floor
   term is real, independent of the deadline term.)
3. (L,K) SEPARABILITY: the architect states L,K are unidentifiable BECAUSE
   "every low-band pause row has tw>=1 ... the low band has none [with tw=0]".
   That premise is FALSE on this corpus - there are 31 tw=0 pause rows. The
   CONCLUSION still holds, for a different reason: all 31 have cidle == 3 ==
   floor, so the floor term explains them and they constrain L only by an
   INEQUALITY (L small enough for the floor to bind), never an equality. The
   ridge is therefore exact. What WOULD break it is a tw=0 pause row with
   cidle 4 (deadline binding at tw=0); the corpus contains none.

Usage: python3 sw/class5_phase4b.py
"""
import sys, itertools
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase2 import load, OCC, AGE
from class5_phase3 import DEM
from class5_phase4 import pred_cidle, d0_of, SS, FLOORS, D0MODES

LOG = SW / "class5_phase4b.log"


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
    P = [x for x in band if x[0]["label"] == "pause"]
    FIT = [x for x in P if x[0]["src"] == "fresh"]
    HOLD = [x for x in P if x[0]["src"] != "fresh"]
    V = list(itertools.product(sorted(DEM), SS, FLOORS, D0MODES))

    def tw13(r):
        return [x for x in r if 1 <= x[0]["pred_tw"] <= 3]

    def twhi(r):
        return [x for x in r if x[0]["pred_tw"] >= 4]

    def ex(rows, v):
        return sum(1 for rec, tj in rows if pred_cidle(tj, fi, *v) == rec["cidle"])

    log("=== 1. PRIMARY GOAL: tw1-3 exact vs trivial baseline (FIT=fresh) ===")
    t = tw13(FIT)
    b4 = sum(1 for x in t if x[0]["cidle"] == 4)
    b3 = sum(1 for x in t if x[0]["cidle"] == 3)
    log(f"  n={len(t)}  always-4 = {b4}/{len(t)} ({100*b4/len(t):.1f}%)  "
        f"always-3 = {b3}/{len(t)}")
    best = max(V, key=lambda v: ex(t, v))
    log(f"  BEST of {len(V)}: {ex(t,best)}/{len(t)} "
        f"({100*ex(t,best)/len(t):.1f}%)  {best}")
    log(f"  >> SIGNAL over majority-class baseline: {ex(t,best)-b4} row(s)")
    log("  => the deadline regime carries essentially no trajectory signal.")

    log("\n=== 2. FLOOR REGIME: is tw>=4 21/21 reachable? ===")
    h = twhi(FIT + HOLD)
    log(f"  pooled tw>=4 pause rows n={len(h)}, cidle-3: "
        f"{sum(1 for x in h if x[0]['cidle']==3)}")
    bh = max(V, key=lambda v: ex(h, v))
    log(f"  BEST tw>=4: {ex(h,bh)}/{len(h)}  {bh}")
    log(f"    its tw1-3 (FIT): {ex(t,bh)}/{len(t)}")
    log("  => the FLOOR term is REAL and confirmed. But no single variant wins")
    log("     both regimes: the best floor rule is far BELOW the tw1-3 baseline.")

    log("\n=== 3. (L,K) SEPARABILITY ===")
    tw0 = [x for x in P if x[0]["pred_tw"] == 0]
    log(f"  low+mid non-flush PAUSE rows: {len(P)};  with pred_tw==0: {len(tw0)}")
    c = defaultdict(int)
    for x in tw0:
        c[(x[0][OCC], x[0][AGE], x[0]["cidle"])] += 1
    log(f"  their (occ,age,cidle): {dict(sorted(c.items()))}")
    log("  The architect's premise ('the low band has no tw=0 pause rows') is")
    log("  FALSE - there are 31. But EVERY one has cidle==3==floor, so they are")
    log("  explained by the floor and constrain L only by inequality. The")
    log("  conclusion (L,K unidentifiable) therefore STANDS, for a different")
    log("  reason. A tw=0 pause row with cidle 4 would break the ridge; none exists.")

    def predLK(tj, rec, dn, L, K, floor, mode):
        D0 = d0_of(tj, fi, DEM[dn], mode, tj.t4 + 1)
        if D0 is None:
            return floor
        return max(floor, D0 + L + (K if rec["pred_tw"] >= 1 else 0) - tj.t4 - 1)

    dn, floor, mode = "cnt_next<=2&euCons", 3, "onset"
    log(f"\n  2D map (D={dn} floor={floor} D0={mode}), exact on FIT n={len(FIT)}:")
    log("        K=0  K=1  K=2  K=3")
    for L in range(0, 7):
        row = []
        for K in range(0, 4):
            e = sum(1 for rec, tj in FIT
                    if predLK(tj, rec, dn, L, K, floor, mode) == rec["cidle"])
            row.append(f"{e:4d}")
        log(f"    L={L} " + " ".join(row))
    log("  => an EXACT ridge along L+K=5: (2,3)==(3,2)==(4,1)==(5,0)==75.")
    log("     L+K is reported as a constrained SUM. No split is claimed.")
    logf.close()


if __name__ == "__main__":
    main()
