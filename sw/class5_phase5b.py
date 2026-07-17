#!/usr/bin/env python3
"""PHASE 5b: functional-form-free probe + the duration law it exposed.

WHY: Phase 5's EU-forecast fit came back at MARGIN 0 over the always-4
baseline, which would ordinarily read as "no signal in tw1-3". Fit C said the
same. Both were fits of a RIGID FORM: max(floor, D0 + S - T4 - 1). Before
reporting a second negative, this file asks the form-free question - does ANY
field carry information about cidle 3-vs-4 - using a majority-vote LOOKUP
fitted on FIT and applied to HOLD. A lookup is not a shippable rule; it is an
UPPER BOUND on what any functional form over that field could achieve, which is
exactly what is needed to tell "no signal" apart from "wrong form".

IT WAS THE WRONG FORM. Result (HOLD, tw1-3, always-4 baseline 44/79 = 56%):
    occupied@T4+1   67/79 = 85%   margin +23   <- BIU field
    q_cnt@T4+1      65/79 = 82%   margin +21   <- BIU field
    eu_state@T4+1   51/79 = 65%   margin  +7
    pop_want, starve, eu_rsv_lead, eu_dly, eu_consuming: margin +0

So (a) the EU-side hypothesis is NOT confirmed - the EU demand fields carry no
duration signal; and (b) the premise it rested on ("tw1-3 is unfittable from
BIU fields") is FALSE. The signal was in occupied all along.

AND occupied@T4+1 IS the corpus's own cnt_occupied (verified identical on
16058/16058 rows) - the field every predicate has been keyed on since Phase 1.
No new dump was ever needed for the duration law. Fit C missed it because
max(floor, D0+S-T4-1) cannot express "cidle = 3 if occ<=2, 4 if occ==4".

THE LAW (tw1-3, non-flush low+mid pause):
    occupied@T4+1 <= 2  -> cidle 3     (FIT 9/9,   HOLD 23/23)
    occupied@T4+1 == 4  -> cidle 4     (FIT 35/36, HOLD 29/29)
    occupied@T4+1 == 3  -> COIN FLIP   (FIT 16:23, HOLD 12:15)
The residual is now CONFINED to one cell. It is not crackable by any tested
field, BIU or EU: best 2nd field is eu_state@T4+1 at HOLD 17/27 (margin +2,
and FIT 77% -> HOLD 63% = overfit). pred_tw inside the cell is noise
(tw1 7:14, tw2 12:11, tw3 9:13).

Usage: python3 sw/class5_phase5b.py
"""
import sys
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from class5_phase5 import load, OCC

LOG = SW / "class5_phase5b.log"


def main():
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    meta, fi, allrows = load()

    def at(tj, c, f):
        t = tj.row.get(c)
        return t[fi[f]] if t else None

    same = sum(1 for rec, tj in allrows
               if at(tj, tj.t4 + 1, "occupied") == rec[OCC])
    log("=== PHASE 5b: form-free probe ===")
    log(f"occupied@T4+1 == corpus cnt_occupied on {same}/{len(allrows)} rows")

    nf = [x for x in allrows if x[0]["flush_win"] == 0
          and x[0]["label"] in ("go", "pause")]
    P = [x for x in nf if x[0][OCC] <= 4 and x[0]["label"] == "pause"]
    FIT = [x for x in P if x[0]["src"] == "fresh"]
    HOLD = [x for x in P if x[0]["src"] != "fresh"]

    def t13(r):
        return [x for x in r if 1 <= x[0]["pred_tw"] <= 3]

    log("\n--- form-free lookup (fit FIT -> apply HOLD), tw1-3 ---")
    b4h = sum(1 for x in t13(HOLD) if x[0]["cidle"] == 4)
    nh = len(t13(HOLD))
    log(f"    HOLD always-4 baseline: {b4h}/{nh} ({100*b4h/nh:.0f}%)")
    rows = []
    for f in ("occupied", "q_cnt", "q_avl", "cnt_next", "eu_state", "eu_dly",
              "pop_want", "q_avail", "eu_rsv_lead", "eu_consuming"):
        for off in (0, 1):
            tab = defaultdict(lambda: defaultdict(int))
            for rec, tj in t13(FIT):
                tab[at(tj, tj.t4 + off, f)][rec["cidle"]] += 1
            vote = {k: max(v, key=v.get) for k, v in tab.items()}
            fo = sum(max(v.values()) for v in tab.values())
            fn = sum(sum(v.values()) for v in tab.values())
            ho = sum(1 for rec, tj in t13(HOLD)
                     if vote.get(at(tj, tj.t4 + off, f)) == rec["cidle"])
            rows.append((ho - b4h, f, off, fo, fn, ho))
    rows.sort(reverse=True)
    for m, f, off, fo, fn, ho in rows:
        log(f"      {f:13s}@T4+{off}: FIT {fo}/{fn} -> HOLD {ho}/{nh} "
            f"({100*ho/nh:.0f}%)  margin {m:+d}")

    log("\n--- THE LAW: cidle vs occupied@T4+1 (tw1-3) ---")
    for nm, sub in (("FIT(fresh)", t13(FIT)), ("HOLD(gz)", t13(HOLD))):
        t = defaultdict(lambda: defaultdict(int))
        for rec, tj in sub:
            t[at(tj, tj.t4 + 1, "occupied")][rec["cidle"]] += 1
        log(f"    {nm}:")
        for k in sorted(t):
            log(f"      occupied@T4+1={k}: cidle {dict(sorted(t[k].items()))}")

    log("\n--- COMPOSITE LAW, scored per split ---")
    log("    tw==0 or tw>=4 -> 3 (floor);  tw1-3: occ<=2 -> 3, occ>=3 -> 4")

    def law(rec):
        if rec["pred_tw"] == 0 or rec["pred_tw"] >= 4:
            return 3
        return 3 if rec[OCC] <= 2 else 4

    for nm, sub in (("FIT(fresh)", FIT), ("HOLD(gz)", HOLD)):
        ok = sum(1 for rec, tj in sub if law(rec) == rec["cidle"])
        b4 = sum(1 for rec, tj in sub if rec["cidle"] == 4)
        t = t13(sub)
        ok3 = sum(1 for rec, tj in t if law(rec) == rec["cidle"])
        tb = max(sum(1 for x in t if x[0]["cidle"] == 4),
                 sum(1 for x in t if x[0]["cidle"] == 3))
        log(f"    {nm}: all-tw {ok}/{len(sub)} ({100*ok/len(sub):.0f}%) "
            f"[best trivial {max(b4, len(sub)-b4)}/{len(sub)}]   "
            f"tw1-3 {ok3}/{len(t)} ({100*ok3/len(t):.0f}%) "
            f"[trivial {tb}/{len(t)}]  margin {ok3-tb:+d}")
    log("\n    NOT an RTL proposal - reported as a measurement. The occ==3 cell")
    log("    remains a coin flip and is now the sharp factorial target.")
    logf.close()


if __name__ == "__main__":
    main()
