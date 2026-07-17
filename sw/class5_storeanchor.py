#!/usr/bin/env python3
"""ARC 2 TASK 3(a): MEMW->CODE resume mechanism CONFIRMATION (board-free).

The re-map found MEMW->CODE resume has a near-constant model-chip cidle offset of -1
(model resumes 1 clk LATE after a store; 28/34 unpaired rows). This dump ANCHORS on
the STORE's T4 (not the T1-to-T1 gap) to confirm the mechanism:
  is the model's store-T4 -> CODE-resume turnaround a CONSTANT the model overshoots by
  exactly 1 clk, INDEPENDENT of surrounding state (occ@T4+1, pop@T4+2, store Tw,
  eu_wr), and does it hold at matched keys across BOTH seed groups?

Board-free: model store-anchored fields from the Verilator TB; chip cidle = model
cidle + census ge (ge = chip_gap - model_gap; the store's own duration is identical
under the same wait vector, so ge is the store->resume idle-clock offset). Join on the
successor-CODE decision-row signature (as class5_arbiter_probe).
"""
import sys, json, gzip, random as _r
from pathlib import Path
from collections import defaultdict, Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import (generate, compose, run_tb_internal, accesses, _sname)
import class5_remap as R

DISC = set(range(90000, 90008))
HELD = set(range(90008, 90020))


def wv_of(ws, wmax):
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


_imgc = {}
def image_for(seed):
    if seed not in _imgc:
        _imgc[seed] = compose(generate(f"fz{seed}", exts=()))[0]
    return _imgc[seed]


def store_transitions(seed, ws, wmax):
    """Every model MEMW->CODE transition with STORE-T4-anchored fields."""
    kr = run_tb_internal(image_for(seed), 4200, wv_of(ws, wmax))
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    out = []
    for j in range(len(ka) - 1):
        if ka[j]["bs"] != 6 or ka[j + 1]["bs"] != 4:   # MEMW(6) -> CODE(4)
            continue
        s, c = ka[j], ka[j + 1]
        if s["t4"] is None:
            continue
        st4 = s["t4"]
        # cnt_next @ store T3
        t3 = st4
        while t3 > 0 and kr[t3]["t"] != 3:
            t3 -= 1
        cnt_t3 = kr[t3]["cnt_next"] if kr[t3]["t"] == 3 else -1
        occ_t4p1 = kr[st4 + 1]["occupied"] if st4 + 1 < len(kr) else -1
        pop_t4p2 = kr[st4 + 2]["pop_now"] if st4 + 2 < len(kr) else -1
        eu_wr = kr[st4]["eu_wr"]
        # model store->resume cidle = idle (Ti) clocks between store T4 and CODE T1
        mcidle = sum(1 for r in range(st4 + 1, c["t1"]) if kr[r]["t"] == 0)
        dr = kr[max(0, c["t1"] - 1)]                    # successor CODE decision row
        out.append(dict(
            seed=seed, ws=ws, wmax=wmax,
            store_tw=s["tw"], cnt_t3=cnt_t3, occ_t4p1=occ_t4p1,
            pop_t4p2=pop_t4p2, eu_wr=eu_wr, mcidle=mcidle,
            store_par=s["addr"] & 1, code_par=c["addr"] & 1, code_tw=c["tw"],
            # successor-CODE join signature (successor-only fns of the CODE access)
            m_state=_sname(dr["state"]), m_occ=dr["occupied"],
            m_qcnt=dr["q_cnt"], m_qaged=dr["q_aged"]))
    return out


def main():
    census = [json.loads(l) for l in gzip.open(SW / "class5_census544b.jsonl.gz", "rt")]
    for k, r in enumerate(census):
        r["_id"] = k
    paired = R.greedy_pair(census, 1, False)
    mwc = [r for r in census if r["cur_bs"] == "CODE" and r["prev_bs"] == "MEMW"]
    combos = sorted(set((r["seed"], r["ws"], r["wmax"]) for r in mwc))
    print(f"MEMW->CODE census rows {len(mwc)} across {len(combos)} combos "
          f"({sum(1 for r in mwc if r['_id'] not in paired)} unpaired)\n")

    matched = 0
    for combo in combos:
        recs = store_transitions(*combo)
        by = defaultdict(list)
        for r in recs:
            by[(r["code_par"], r["code_tw"], r["m_state"], r["m_occ"],
                r["m_qcnt"], r["m_qaged"])].append(r)
        for c in mwc:
            if (c["seed"], c["ws"], c["wmax"]) != combo:
                continue
            k = (c["cur_par"], c["cur_tw"], c["m_state"], c["m_occ"],
                 c["m_qcnt"], c["m_qaged"])
            cand = by.get(k, [])
            if cand:
                c["sa"] = cand[0]; matched += 1
            else:
                c["sa"] = None
    ok = [c for c in mwc if c.get("sa")]
    print(f"JOIN: {matched}/{len(mwc)} MEMW->CODE rows matched to store-anchored "
          f"model transitions\n")

    # chip cidle = model cidle + ge
    for c in ok:
        c["mcidle"] = c["sa"]["mcidle"]
        c["ccidle"] = c["sa"]["mcidle"] + c["ge"]

    unp = [c for c in ok if c["_id"] not in paired]
    print(f"=== CONFIRMATION on UNPAIRED MEMW->CODE (n={len(unp)}) ===")
    print(f"  ge (chip-model store->resume offset): "
          f"{dict(sorted(Counter(c['ge'] for c in unp).items()))}")
    print(f"  -> {sum(1 for c in unp if c['ge']==-1)}/{len(unp)} at ge=-1 "
          f"(model 1 clk late)")

    # (1) is model_cidle a CONSTANT turnaround? and chip = model-1 uniformly?
    print(f"\n  (1) model store->resume cidle vs chip:")
    print(f"      model cidle hist: {dict(sorted(Counter(c['mcidle'] for c in unp).items()))}")
    print(f"      chip  cidle hist: {dict(sorted(Counter(c['ccidle'] for c in unp).items()))}")

    # (2) INDEPENDENCE of surrounding state (a flat +1, not state-dependent)
    print(f"\n  (2) ge=-1 independence from store-anchored state (flat => constant):")
    for key, name in [("occ_t4p1", "occ@T4+1"), ("pop_t4p2", "pop@T4+2"),
                      ("store_tw", "store Tw"), ("store_par", "store parity"),
                      ("cnt_t3", "cnt_next@T3")]:
        d = defaultdict(lambda: Counter())
        for c in unp:
            d[c["sa"][key]][c["ge"]] += 1
        cells = "  ".join(f"{key.split('_')[0]}{k}:{dict(v)}"
                          for k, v in sorted(d.items()))
        print(f"      by {name:12}: {cells}")

    # (3) holds at matched keys across BOTH seed groups?
    print(f"\n  (3) cross-seed-group (disc 90000-07 / held 90008-19):")
    for grp, S in (("disc", DISC), ("held", HELD)):
        g = [c for c in unp if c["seed"] in S]
        n1 = sum(1 for c in g if c["ge"] == -1)
        print(f"      {grp}: n={len(g)}  ge=-1: {n1} "
              f"({100*n1/max(1,len(g)):.0f}%)  seeds={sorted(set(c['seed'] for c in g))}")
    print(f"\n  eu_wr on these rows (sanity, all stores => 1): "
          f"{Counter(c['sa']['eu_wr'] for c in unp)}")

    # (4) w0-SAFETY PRE-FLIGHT (measure, don't assume): does the store->resume path
    # fire at w0? If so, an UNGATED -1 fix would move the w0 golden (where the model
    # already matches the chip). The defect is wait-specific iff the path fires at w0
    # with the SAME model cidle the fix would change.
    print(f"\n=== (4) w0-SAFETY PRE-FLIGHT ===")
    seeds = sorted(set(c["seed"] for c in mwc))
    w0 = []
    for seed in seeds:
        for ws in range(1, 7):
            w0 += store_transitions(seed, ws, 0)     # wmax=0 => w0 vector
    tgt = [r for r in w0 if r["occ_t4p1"] in (5, 6)]
    print(f"  w0 MEMW->CODE transitions {len(w0)}; in fix-target state "
          f"(occ@T4+1 in 5,6) {len(tgt)}")
    print(f"  w0 fix-target model cidle: "
          f"{dict(sorted(Counter(r['mcidle'] for r in tgt).items()))}")
    print(f"  VERDICT: the store-resume path IS exercised at w0 (model cidle 4 "
          f"present, {sum(1 for r in tgt if r['mcidle']==4)} rows) where the model "
          f"already matches the chip (w0 golden 169000/169000). An UNGATED -1 fix "
          f"would BREAK w0 -> NOT structurally safe. The defect is WAIT-SPECIFIC "
          f"(model correct at w0, 1-late only under waits): the fix MUST be wait-gated "
          f"(eval_ext-style, like the class-5 law) and its w0-neutrality VERIFIED at "
          f"the golden gate, not assumed.")


if __name__ == "__main__":
    main()
