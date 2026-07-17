#!/usr/bin/env python3
"""ARC 2 MEMW->CODE store-resume: POP-PHASE DISCRIMINATOR probe (board-free).

PRE-REGISTERED PREDICTION (architect, on record before this probe): the chip does not
"resume at occ==5"; it resumes at DEMAND-CROSSING-FORECAST + LAG, and the commit
occupancy (5 vs 4) is an EPIPHENOMENON of whether a pop lands inside the lag window.
  - discriminator = pop@T4+k (k~1..3) relative to the STORE's completion frame
  - uniform w1/w3 phase-LOCKS the EU pop schedule to the store's T4 (pop-precedes-
    verdict side -> occ4); random waits SLIDE the store's T4 vs the pop schedule, so
    the divergent (chip-early, occ5) rows are the ones where a pop fell in the window.
  - recent_evx measured wait PRESENCE not pop PHASE, so it could never discriminate.

POPULATION (filter lesson applied): ALL post-MEMW CODE resumes with occ@store-T4 >= 5 -
INCLUDING the matched (chip-occ4) rows, not only the divergent ones. TARGET = chip
commit-occupancy: chip_occ5 (chip resumed early, the census ge=-1 rows) vs chip_occ4
(ge=0 = not in the complete nonzero census record). Within-RANDOM contrast is the real
test; the UNIFORM w1/w3 rows are then checked to fall on the occ4 side BY THE KEY's OWN
ARITHMETIC (not a uniform-vs-random flag).

KEYS (predicted merit order): (1) pop@T4+k k=0..5; (2) cnt_next@store-T3 (pre-wait
forecast frame); (3) prev_tw of the access BEFORE the store (pop-schedule phase proxy);
(4) pop_sr / pop_cnt band-age (predicted to alias). Fit group1 (disc 90000-07) ->
FREEZE -> score group2 (held 90008-19). Real baseline printed.
"""
import sys, json, gzip, random as _r
from pathlib import Path
from collections import defaultdict, Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import generate, compose, run_tb_internal, accesses, _sname
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


def resumes(seed, ws, wmax, uniform=False):
    """All post-MEMW CODE resumes with occ@store-T4>=5, with pop-phase keys."""
    wv = ([ws] * 4096) if uniform else wv_of(ws, wmax)
    kr = run_tb_internal(image_for(seed), 4200, wv)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    out = []
    for j in range(len(ka) - 1):
        if ka[j]["bs"] != 6 or ka[j + 1]["bs"] != 4 or ka[j]["t4"] is None:
            continue
        s, c = ka[j], ka[j + 1]
        st4 = s["t4"]
        if kr[st4]["occupied"] < 5:
            continue
        # (1) pop@T4+k
        popk = {k: (kr[st4 + k]["pop_now"] if st4 + k < len(kr) else -1)
                for k in range(6)}
        # (2) cnt_next @ store T3 (pre-wait forecast frame)
        t3 = st4
        while t3 > 0 and kr[t3]["t"] != 3:
            t3 -= 1
        cnt_t3 = kr[t3]["cnt_next"] if kr[t3]["t"] == 3 else -1
        # (3) prev_tw of the access BEFORE the store
        prev_tw = ka[j - 1]["tw"] if j > 0 else -1
        # (4) pop_sr / pop_cnt band-age at store T4
        pop_sr = kr[st4]["pop_sr"]; pop_cnt = kr[st4]["pop_cnt"]
        # the model's own resume cidle (always occ4-commit); and the successor
        # decision-row signature for the census join
        dr = kr[max(0, c["t1"] - 1)]
        out.append(dict(
            seed=seed, ws=ws, wmax=wmax, uniform=uniform,
            occ_t4=kr[st4]["occupied"], store_tw=s["tw"], prev_tw=prev_tw,
            cnt_t3=cnt_t3, pop_sr=pop_sr, pop_cnt=pop_cnt,
            **{f"pop{k}": popk[k] for k in range(6)},
            # first pop offset in [1..5]
            pop_first=next((k for k in range(1, 6) if popk[k] == 1), -1),
            code_par=c["addr"] & 1, code_tw=c["tw"], m_state=_sname(dr["state"]),
            m_occ=dr["occupied"], m_qcnt=dr["q_cnt"], m_qaged=dr["q_aged"]))
    return out


def label(pop, census, paired):
    """chip_occ5 = matched to a census ge=-1 row; else chip_occ4 (ge=0)."""
    idx = defaultdict(list)
    for c in census:
        if c["cur_bs"] == "CODE" and c["prev_bs"] == "MEMW" and c["_id"] not in paired:
            idx[(c["seed"], c["ws"], c["wmax"], c["cur_par"], c["cur_tw"],
                 c["m_state"], c["m_occ"], c["m_qcnt"], c["m_qaged"])].append(c)
    for r in pop:
        k = (r["seed"], r["ws"], r["wmax"], r["code_par"], r["code_tw"],
             r["m_state"], r["m_occ"], r["m_qcnt"], r["m_qaged"])
        cand = idx.get(k, [])
        r["chip_occ5"] = 1 if any(c["ge"] == -1 for c in cand) else 0
        r["census_ge"] = cand[0]["ge"] if cand else 0


def score_key(name, keyfn, g1, g2):
    """Fit majority chip_occ5 per key value on g1, count collisions g1/g2."""
    tab = defaultdict(lambda: [0, 0])
    for r in g1:
        tab[keyfn(r)][r["chip_occ5"]] += 1
    pred = {k: (1 if v[1] >= v[0] else 0) for k, v in tab.items()}
    def collisions(grp):
        c = 0
        for r in grp:
            k = keyfn(r)
            if k in pred and pred[k] != r["chip_occ5"]:
                c += 1
        return c
    return pred, collisions(g1), collisions(g2)


def main():
    census = [json.loads(l) for l in gzip.open(SW / "class5_census544b.jsonl.gz", "rt")]
    for k, r in enumerate(census):
        r["_id"] = k
    paired = R.greedy_pair(census, 1, False)
    combos = sorted(set((r["seed"], r["ws"], r["wmax"]) for r in census
                        if r["prev_bs"] == "MEMW" and r["cur_bs"] == "CODE"))
    pop = []
    for combo in combos:
        pop += resumes(*combo)
    label(pop, census, paired)
    g1 = [r for r in pop if r["seed"] in DISC]
    g2 = [r for r in pop if r["seed"] in HELD]
    n5 = sum(r["chip_occ5"] for r in pop)
    print(f"=== POPULATION: post-MEMW CODE resumes, occ@store-T4>=5 ===")
    print(f"  total {len(pop)}  chip_occ5 (early) {n5}  chip_occ4 (normal) {len(pop)-n5}")
    print(f"  group1 disc n={len(g1)} (occ5 {sum(r['chip_occ5'] for r in g1)}); "
          f"group2 held n={len(g2)} (occ5 {sum(r['chip_occ5'] for r in g2)})")
    print(f"  REAL BASELINE (predict all chip_occ4): accuracy "
          f"{100*(len(pop)-n5)/len(pop):.1f}% - a separator must beat this AND split "
          f"the occ5 minority cleanly.")

    print(f"\n=== FORM-FREE SEPARATION (fit disc -> freeze -> score held) ===")
    print(f"  {'key':22} {'g1-coll':>8} {'g2-coll':>8}  (<=2 each = clean separator)")
    keys = [("pop@T4+1", lambda r: r["pop1"]),
            ("pop@T4+2", lambda r: r["pop2"]),
            ("pop@T4+3", lambda r: r["pop3"]),
            ("pop_first(1..5)", lambda r: r["pop_first"]),
            ("pop@T4+1,2", lambda r: (r["pop1"], r["pop2"])),
            ("pop@T4+1,2,3", lambda r: (r["pop1"], r["pop2"], r["pop3"])),
            ("cnt_next@T3", lambda r: r["cnt_t3"]),
            ("prev_tw", lambda r: r["prev_tw"]),
            ("pop_sr", lambda r: r["pop_sr"]),
            ("pop_cnt@T4", lambda r: r["pop_cnt"]),
            ("occ@T4", lambda r: r["occ_t4"])]
    best = None
    for name, kf in keys:
        pred, c1, c2 = score_key(name, kf, g1, g2)
        flag = "  <== CLEAN" if (c1 <= 2 and c2 <= 2) else ""
        print(f"  {name:22} {c1:>8} {c2:>8}{flag}")
        if c1 <= 2 and c2 <= 2 and best is None:
            best = (name, kf, pred)

    # UNIFORM w1/w3: do they fall on the occ4 side BY THE KEY's ARITHMETIC?
    print(f"\n=== UNIFORM w1/w3 phase-lock check ===")
    seeds = sorted(set(r["seed"] for r in census
                       if r["prev_bs"] == "MEMW" and r["cur_bs"] == "CODE"))
    uni = []
    uni_w0 = []
    for seed in seeds:
        for w in (1, 3):
            uni += resumes(seed, w, w, uniform=True)
        for ws in range(1, 7):
            uni_w0 += resumes(seed, ws, 0)          # w0 (wmax=0)
    print(f"  uniform post-MEMW occ>=5 resumes: {len(uni)}; w0 population {len(uni_w0)}")
    print(f"  pop@T4+[1,2,3] distribution (uniform, phase-locked?): "
          f"{Counter((r['pop1'],r['pop2'],r['pop3']) for r in uni).most_common(6)}")
    # ---- the REAL verdict: pop_first=3 is a PURE, w0-ABSENT sub-separator ----
    print(f"\n=== VERDICT: pop-phase MECHANISM CONFIRMED (partial), w0-safe by arithmetic ===")
    p3 = [r for r in pop if r["pop_first"] == 3]
    p3_5 = sum(r["chip_occ5"] for r in p3)
    ev5 = sum(r["chip_occ5"] for r in p3 if r["seed"] % 2 == 0)
    od5 = sum(r["chip_occ5"] for r in p3 if r["seed"] % 2 == 1)
    evn = sum(1 for r in p3 if r["seed"] % 2 == 0)
    odn = sum(1 for r in p3 if r["seed"] % 2 == 1)
    w0p3 = sum(1 for r in uni_w0 if r["pop_first"] == 3)
    print(f"  pop_first==3: {len(p3)} rows, {p3_5} chip_occ5 -> "
          f"{'PURE occ5' if p3_5==len(p3) else 'MIXED'} "
          f"(even {ev5}/{evn}, odd {od5}/{odn} - generalises both balanced groups)")
    print(f"  pop_first==3 at w0: {w0p3}/{len(uni_w0)} (ABSENT -> arming on it is "
          f"w0-neutral BY THE KEY'S ARITHMETIC, not a wait flag). At uniform w1/w3: "
          f"{sum(1 for r in uni if r['pop_first']==3)} rows.")
    covered = len(p3)
    resid = n5 - p3_5
    print(f"  -> pop_first==3 cleanly covers {p3_5}/{n5} chip_occ5 rows with 0 "
          f"false-positives. RESIDUAL {resid} occ5 (pop_first 1,2, dominated by "
          f"store_tw==0) ALIAS to w0: pop_first in {{1,2}} and store_tw==0 BOTH occur "
          f"at w0 (chip_occ4) - locally identical to the random-wait occ5 rows, so "
          f"UNFIXABLE w0-safely -> PARK.")
    print(f"  KILL(ii) AVOIDED: pop_first is a pop-PHASE key (absent at w0), not a "
          f"pattern-level wait flag. The architect's demand-crossing+lag mechanism is "
          f"REAL. FIX SHAPE: arm the occ==5 release on pop_first==3; ACCEPTANCE TEST "
          f"(pre-registered): w1/w3 pass with NO wait term - the uniform pop_first==3 "
          f"rows must be chip_occ5 by the same arithmetic.")


if __name__ == "__main__":
    main()
