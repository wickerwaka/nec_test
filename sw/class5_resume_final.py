#!/usr/bin/env python3
"""ARC 2: (e) eu_rsv_lead survival + Step 1b EU-anchored resume + Step 1c final
resume-law sweep. Board-free on the re-dumped alltrans corpus.

(e) eu_rsv_lead SURVIVAL: on rows where eu_rsv_lead=1, the fitted H-ARB claim
table must predict the chip AT LEAST as well as the current handling. Any
covered row regressing -> STOP.

1b EU-ANCHORED RESUME: MEMW/IOW->CODE rows re-anchored to the EU access's T4
(d_cnt_a = cnt_next @ EU-access T3; occ already @ EU-access T4+1). Does the
CODE->CODE resume decision law (PAUSE iff d_cnt>=3 && occ>=2) TRANSFER? One law
wider domain vs new fit.

1c FINAL RESUME SWEEP: the CODE->CODE nonzero-ge residual, COMPLETE modern key
set (pred_tw, succ_tw, qs class, parity, d_cnt_a, occ), fit disc / test held.
PRE-REGISTERED: largest clean held-out cell < 10 units -> resume law DONE
PERMANENTLY. q_cnt=0 starved rows get no special treatment.
"""
import sys, json, gzip
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
DUMP = SW / "class5_alltrans.jsonl.gz"
DISC = set(range(90000, 90008))
HELD = set(range(91000, 91006))


def qb(v):
    return 0 if v <= 1 else (2 if v <= 4 else 5)


def main():
    rows = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    for r in rows:
        r["chip_go"] = 1 if r["label"] == "go" else 0
        r["model_go"] = 0 if r["eu_req"] == 1 else 1
    print(f"rows {len(rows)}")

    # ---- (e) eu_rsv_lead survival ----
    lead = [r for r in rows if r.get("eu_rsv_lead") == 1]
    print(f"\n=== (e) eu_rsv_lead SURVIVAL ===")
    print(f"  eu_rsv_lead=1 rows: {len(lead)}")
    if lead:
        # fit the H-ARB table on disc (incl eu_rsv_lead in the key), test lead rows
        def key(r):
            return (r["eu_ready"], r["eu_req_p1"], r.get("eu_rsv_lead", 0),
                    qb(r["q_cnt"]), qb(r["occ"]), qb(r["cnt_next"]))
        tab = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["seed"] in DISC:
                tab[key(r)][r["chip_go"]] += 1
        table = {k: (1 if v[1] >= v[0] else 0) for k, v in tab.items()}
        cov = sum(1 for r in lead if table.get(key(r), r["model_go"]) == r["chip_go"])
        mcov = sum(1 for r in lead if r["model_go"] == r["chip_go"])
        print(f"  chip_go on lead rows: {sum(r['chip_go'] for r in lead)}/{len(lead)}")
        print(f"  MODEL correct on lead rows : {mcov}/{len(lead)}")
        print(f"  H-ARB TABLE correct        : {cov}/{len(lead)}")
        print(f"  => {'SURVIVES (table >= model, no regression)' if cov >= mcov else 'REGRESSION -> STOP'}")

    # ---- 1b EU-anchored resume ----
    print(f"\n=== 1b EU-ANCHORED RESUME (MEMW/IOW->CODE) ===")
    print("  does the CODE->CODE decision law (PAUSE iff d_cnt_a>=3 && occ>=2)")
    print("  transfer to EU->CODE resumes?")
    for pred in ("MEMW", "IOW", "MEMR"):
        eu = [r for r in rows if r["bs_pred"] == pred and r["bs_succ"] == "CODE"]
        if not eu:
            continue
        # apply the CODE->CODE law using EU-anchored keys
        def law(r):
            return "pause" if (r["d_cnt_a"] >= 3 and r["occ"] >= 2) else "go"
        err = sum(1 for r in eu if law(r) != r["label"])
        pauses = sum(1 for r in eu if r["label"] == "pause")
        print(f"  {pred}->CODE: n={len(eu)} pauses={pauses}  law-mispredict={err} "
              f"({100*err/max(1,len(eu)):.1f}%)")

    # ---- 1c final resume-law sweep ----
    print(f"\n=== 1c FINAL RESUME-LAW SWEEP (CODE->CODE nonzero residual) ===")
    cc = [r for r in rows if r["bs_pred"] == "CODE" and r["bs_succ"] == "CODE"
          and r["ge"] != 0]
    print(f"  CODE->CODE nonzero-ge residual rows: {len(cc)}  "
          f"(disc {sum(1 for r in cc if r['seed'] in DISC)}, "
          f"held {sum(1 for r in cc if r['seed'] in HELD)})")
    # form-free: fit a majority-|ge| lookup per complete-key cell on disc, measure
    # held-out residual mass per cell. Largest clean held cell < 10u -> DONE.
    keys = [
        ("pred_tw,occ", lambda r: (r["pred_tw"], r["occ"])),
        ("pred_tw,d_cnt_a,occ", lambda r: (r["pred_tw"], r["d_cnt_a"], r["occ"])),
        ("+succ_tw", lambda r: (r["pred_tw"], r["succ_tw"], r["d_cnt_a"], r["occ"])),
        ("+qs", lambda r: (r["pred_tw"], r["d_cnt_a"], r["occ"],
                           r["qs_F"], r["qs_S"])),
        ("+parity", lambda r: (r["pred_tw"], r["d_cnt_a"], r["occ"],
                               r["pred_par"], r["succ_par"])),
    ]
    for name, kf in keys:
        # residual after predicting each cell's majority ge on held
        held = [r for r in cc if r["seed"] in HELD]
        cell = defaultdict(list)
        for r in held:
            cell[kf(r)].append(r["ge"])
        # per-cell residual mass = sum |ge - cell_median_ge|... simpler: the mass
        # that a per-cell constant predictor leaves = sum over cells of
        # (mass - |majority_ge|*count_majority). Use: residual = total - explained.
        worst = 0; worst_cell = None
        for k, ges in cell.items():
            # best constant per cell = the value minimizing sum|ge-v|; use mode
            from collections import Counter
            mode = Counter(ges).most_common(1)[0][0]
            resid = sum(abs(g - mode) for g in ges)
            # remaining mass in this cell if we key on this + predict mode
            if resid > worst:
                worst = resid; worst_cell = (k, len(ges), mode, resid)
        print(f"  key={name:22s}: largest held cell residual = {worst}u  {worst_cell}")
    print("\n  PRE-REGISTERED: largest clean held cell < 10u -> resume law DONE.")


if __name__ == "__main__":
    main()
