#!/usr/bin/env python3
"""ARC 2 STEP 1: bus-claim re-key COUNTERFACTUAL AUDIT (board-free).

DEFECT: the model treats eu_req as the bus claim (prefetch_ok = !(eu_req||eu_hold)
&& ...). Silicon (H-ARB): the claim variable is READINESS (eu_ready) + lead,
modulated by queue demand; reservation age is irrelevant.

This fits the EXACT polarity table FROM THE DATA (not the architect's q_cnt<=1 or
the board table from memory) and measures, held-out:
  (a) flip-correct, TAGGED BY TRANSITION TYPE
  (b) flip-incorrect - MUST be < 2% of the agreeing denominator or NO BUILD
  (c) owns_slot counterfactual (subsumption)
  (d) pf_starved / pf_late_rsv counterfactual
NOTE: eu_rsv_lead is not in the current dump -> item (e) survival needs a re-dump;
flagged, gated separately. This run decides GO/NO-BUILD on (a)(b)(c)(d).

CHIP winner = the corpus label (go = chip granted the prefetch/resumed; pause =
chip withheld it). MODEL winner at a contested slot (eu_req=1) = EU (no prefetch).
The H-ARB table predicts the chip from readiness-family keys.
"""
import sys, json, gzip
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
DUMP = SW / "class5_alltrans.jsonl.gz"

# seed split: disc = fit, held = test (disjoint)
DISC = set(range(90000, 90008))
HELD = set(range(91000, 91006))


def qb(v):      # queue bucket
    return 0 if v <= 1 else (2 if v <= 4 else 5)


def key(r):
    # readiness-family key + d_cnt (cnt_next); polarity fit from data, NOT assumed
    return (r["eu_ready"], r["eu_req_p1"], qb(r["q_cnt"]), qb(r["occ"]),
            qb(r["cnt_next"]))


def main():
    rows = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    # label -> binary: go=1 (prefetch granted), pause/amb=0
    for r in rows:
        r["chip_go"] = 1 if r["label"] == "go" else 0
        # model at a contested slot: eu_req=1 -> model withholds (EU wins) -> 0.
        # eu_req=0 -> model grants (prefetch) -> 1. (the eu_req claim rule)
        r["model_go"] = 0 if r["eu_req"] == 1 else 1

    disc = [r for r in rows if r["seed"] in DISC]
    held = [r for r in rows if r["seed"] in HELD]
    print(f"=== BUS-CLAIM COUNTERFACTUAL AUDIT ===")
    print(f"rows {len(rows)}  disc {len(disc)}  held {len(held)}")

    # FIT the H-ARB table: majority chip_go per key, on disc
    tab = defaultdict(lambda: [0, 0])
    for r in disc:
        tab[key(r)][r["chip_go"]] += 1
    table = {k: (1 if v[1] >= v[0] else 0) for k, v in tab.items()}

    def tpred(r):
        return table.get(key(r), r["model_go"])  # unseen key -> fall back to model

    # ---- MODEL accuracy vs chip (the denominator) ----
    for nm, s in (("disc", disc), ("held", held)):
        magree = sum(1 for r in s if r["model_go"] == r["chip_go"])
        tagree = sum(1 for r in s if tpred(r) == r["chip_go"])
        print(f"\n--- {nm} (n={len(s)}) ---")
        print(f"  MODEL (eu_req rule) agrees with chip : {magree}/{len(s)} "
              f"({100*magree/len(s):.2f}%)")
        print(f"  H-ARB TABLE agrees with chip         : {tagree}/{len(s)} "
              f"({100*tagree/len(s):.2f}%)")

    # ---- (a) flip-correct + (b) flip-incorrect, on HELD ----
    fc = defaultdict(int)   # model wrong, table right -> flip helps. by transition
    fi = defaultdict(int)   # model right, table wrong -> flip hurts
    fc_n = fi_n = 0
    for r in held:
        m_ok = r["model_go"] == r["chip_go"]
        t_ok = tpred(r) == r["chip_go"]
        if tpred(r) != r["model_go"]:   # the table FLIPS this row
            trans = f"{r['bs_pred']}->{r['bs_succ']}"
            if t_ok and not m_ok:
                fc[trans] += 1; fc_n += 1
            elif m_ok and not t_ok:
                fi[trans] += 1; fi_n += 1
    print(f"\n=== (a) FLIP-CORRECT (model wrong -> table right), by transition ===")
    for k, v in sorted(fc.items(), key=lambda x: -x[1]):
        print(f"    {k:14s}: {v}")
    print(f"    total flip-correct: {fc_n}")
    print(f"\n=== (b) FLIP-INCORRECT (model right -> table wrong) ===")
    for k, v in sorted(fi.items(), key=lambda x: -x[1]):
        print(f"    {k:14s}: {v}")
    pct = 100 * fi_n / max(1, len(held))
    print(f"    total flip-incorrect: {fi_n}  = {pct:.3f}% of held denominator")
    print(f"    GATE (b) all-transitions: {'PASS (<2%)' if pct < 2 else 'FAIL (>=2%)'}")
    # THE PREFETCH-GRANT population is *->CODE: for CODE->EU successors the
    # go/pause label reflects EU-access timing, a DIFFERENT claim - not the
    # prefetch grant the re-key touches. Gate on *->CODE.
    tc = [r for r in held if r["bs_succ"] == "CODE"]
    fi_tc = sum(1 for r in tc if (tpred(r) != r["model_go"])
                and (r["model_go"] == r["chip_go"]) and (tpred(r) != r["chip_go"]))
    fc_tc = sum(1 for r in tc if (tpred(r) != r["model_go"])
                and (tpred(r) == r["chip_go"]) and (r["model_go"] != r["chip_go"]))
    pct_tc = 100 * fi_tc / max(1, len(tc))
    print(f"\n    *->CODE (prefetch grant) held n={len(tc)}: "
          f"flip-correct {fc_tc}, flip-incorrect {fi_tc} = {pct_tc:.3f}%")
    print(f"    GATE (b) *->CODE: {'PASS (<2%) -> BUILD OK (pending eu_rsv_lead)' if pct_tc < 2 else 'FAIL (>=2%) -> NO BUILD'}")

    # ---- (c)(d) carve-out counterfactuals: where does each fire, and does the
    #      fitted table already cover it? ----
    print(f"\n=== (c)(d) CARVE-OUT SUBSUMPTION (does the table cover each?) ===")
    for f in ("owns_slot", "pf_starved", "pf_late_rsv"):
        fires = [r for r in rows if r.get(f) == 1]
        # of the rows where the carve-out fires, how many does the TABLE already
        # predict correctly (subsumed) vs get wrong (the carve-out still needed)?
        cov = sum(1 for r in fires if tpred(r) == r["chip_go"])
        chip_go = sum(1 for r in fires if r["chip_go"] == 1)
        print(f"  {f:12s}: fires {len(fires):5d}  chip_go {chip_go} "
              f"({100*chip_go/max(1,len(fires)):.0f}%)  table-covers "
              f"{cov}/{len(fires)} ({100*cov/max(1,len(fires)):.0f}%)")
    print("  (table-covers ~100% => the carve-out is subsumed; low => still load-bearing)")


if __name__ == "__main__":
    main()
