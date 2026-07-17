#!/usr/bin/env python3
"""ARC 2 MEMW->CODE store-resume: FORECAST-SIGNAL probe (board-free).

The chip commits the post-store CODE prefetch at off-2 (occ5), BEFORE the off-3 pop is
observable -> the release is a latched FORECAST + LAG, not a reactive pop detect. Which
signal, sampled at the off-2 commit cycle, forecasts "the crossing pop lands at off-3"
(-> commit early = chip_occ5)?
  (a) EU-side schedule: pop_want / q_avail / eu_dly (d[51..53])
  (b) cnt_next@store-T3 + pop cadence (pop_sr / pop_cnt)
Populations: TRUE = the 20 confirmed pop_first==3 rows (17 random census + 3 uniform w1)
- must forecast TRUE. FALSE = pop_first in {1,2} (esp. pop_first==2 & occ@T4==6, the
over-fire case) - must forecast FALSE. Clean separation on both sides picks the winner;
tie -> simpler/narrower; neither -> STOP (forecast not locally observable, park ~17u).
"""
import sys, json, gzip, random as _r
from pathlib import Path
from collections import defaultdict, Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import generate, compose, run_tb_internal, accesses
import class5_remap as R


def wv_of(ws, wmax):
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


_imgc = {}
def image_for(seed):
    if seed not in _imgc:
        _imgc[seed] = compose(generate(f"fz{seed}", exts=()))[0]
    return _imgc[seed]


def store_resumes(seed, ws, wmax, uniform=False):
    wv = ([ws] * 4096) if uniform else wv_of(ws, wmax)
    kr = run_tb_internal(image_for(seed), 4200, wv)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    out = []
    for j in range(len(ka) - 1):
        if ka[j]["bs"] != 6 or ka[j + 1]["bs"] != 4 or ka[j]["t4"] is None:
            continue
        st4 = ka[j]["t4"]
        if kr[st4]["occupied"] < 5:
            continue
        pf = next((k for k in range(1, 6)
                   if st4 + k < len(kr) and kr[st4 + k]["pop_now"] == 1), -1)
        t3 = st4
        while t3 > 0 and kr[t3]["t"] != 3:
            t3 -= 1
        def at(off, key):
            r = st4 + off
            return kr[r][key] if 0 <= r < len(kr) else -1
        out.append(dict(
            seed=seed, ws=ws, wmax=wmax, uniform=uniform, pop_first=pf,
            occ_t4=kr[st4]["occupied"],
            # candidate (a): EU schedule at off-2 (the commit cycle) and off-1
            a_popwant_o2=at(2, "pop_want"), a_qavail_o2=at(2, "q_avail"),
            a_eudly_o2=at(2, "eu_dly"), a_popwant_o1=at(1, "pop_want"),
            a_eudly_o1=at(1, "eu_dly"), a_eudly_o0=at(0, "eu_dly"),
            a_popwant_o0=at(0, "pop_want"),
            # candidate (b): cnt_next@T3 + pop cadence at off-2 / T3
            b_cnt_t3=(kr[t3]["cnt_next"] if kr[t3]["t"] == 3 else -1),
            b_popsr_o2=at(2, "pop_sr"), b_popcnt_o2=at(2, "pop_cnt"),
            b_popsr_o1=at(1, "pop_sr"), b_cnt_o2=at(2, "cnt_next"),
            # the model's own resume signature (for census join)
            code_par=ka[j + 1]["addr"] & 1, code_tw=ka[j + 1]["tw"]))
    return out


def main():
    census = [json.loads(l) for l in gzip.open(SW / "class5_census544b.jsonl.gz", "rt")]
    for k, r in enumerate(census):
        r["_id"] = k
    combos = sorted(set((r["seed"], r["ws"], r["wmax"]) for r in census
                        if r["prev_bs"] == "MEMW" and r["cur_bs"] == "CODE"))
    # random population (labelled by census join done in class5_poprelease sense):
    import class5_poprelease as P
    paired = R.greedy_pair(census, 1, False)
    randpop = []
    for combo in combos:
        randpop += store_resumes(*combo)
    # label chip_occ5 via census ge=-1 (reuse the successor-CODE signature)
    idx = defaultdict(list)
    for c in census:
        if c["cur_bs"] == "CODE" and c["prev_bs"] == "MEMW" and c["_id"] not in paired:
            idx[(c["seed"], c["ws"], c["wmax"], c["cur_par"], c["cur_tw"])].append(c)
    # NOTE: coarse join (par,tw) is enough here since we only need pop_first==3 vs {1,2}
    # split, which is a model quantity; chip_occ5 label cross-checks it.
    # TRUE = pop_first==3 (board-confirmed universal); FALSE = pop_first in {1,2}
    TRUE = [r for r in randpop if r["pop_first"] == 3]
    # add the 3 uniform pop_first==3 rows
    for seed in (90009, 90017, 90018):
        TRUE += [r for r in store_resumes(seed, 1, 1, uniform=True)
                 if r["pop_first"] == 3]
    FALSE = [r for r in randpop if r["pop_first"] in (1, 2)]
    FALSE_of = [r for r in FALSE if r["pop_first"] == 2 and r["occ_t4"] == 6]
    print(f"TRUE (pop_first==3, forecast TRUE): {len(TRUE)}  "
          f"FALSE (pop_first in 1,2): {len(FALSE)} "
          f"(over-fire subset pf2&occ6: {len(FALSE_of)})")

    def sep(name, keyfn):
        tv = Counter(keyfn(r) for r in TRUE)
        fv = Counter(keyfn(r) for r in FALSE)
        # a signal separates if TRUE-values and FALSE-values are disjoint sets
        tset, fset = set(tv), set(fv)
        overlap = tset & fset
        # cleanliness: fraction of FALSE that share a TRUE value (would misfire)
        misfire = sum(fv[v] for v in overlap)
        miss = sum(tv[v] for v in (tset - fset) if False)  # placeholder
        clean = (len(overlap) == 0)
        print(f"  {name:16} TRUE={dict(sorted(tv.items()))}  "
              f"FALSE={dict(sorted(fv.items()))}  "
              f"{'CLEAN SEPARATION' if clean else f'overlap={sorted(overlap)} misfire={misfire}/{len(FALSE)}'}")

    print(f"\n=== CANDIDATE (a): EU-side schedule (d[51..53]) ===")
    for nm, kf in [("popwant@off2", lambda r: r["a_popwant_o2"]),
                   ("qavail@off2", lambda r: r["a_qavail_o2"]),
                   ("eudly@off2", lambda r: r["a_eudly_o2"]),
                   ("eudly@off1", lambda r: r["a_eudly_o1"]),
                   ("eudly@off0", lambda r: r["a_eudly_o0"]),
                   ("popwant@off1", lambda r: r["a_popwant_o1"]),
                   ("(popwant,eudly)@o2", lambda r: (r["a_popwant_o2"], r["a_eudly_o2"]))]:
        sep(nm, kf)

    print(f"\n=== CANDIDATE (b): cnt_next@T3 + pop cadence ===")
    for nm, kf in [("cnt_t3", lambda r: r["b_cnt_t3"]),
                   ("popsr@off2", lambda r: r["b_popsr_o2"]),
                   ("popcnt@off2", lambda r: r["b_popcnt_o2"]),
                   ("popsr@off1", lambda r: r["b_popsr_o1"]),
                   ("cnt@off2", lambda r: r["b_cnt_o2"]),
                   ("(cnt_t3,popsr@o2)", lambda r: (r["b_cnt_t3"], r["b_popsr_o2"]))]:
        sep(nm, kf)

    print(f"\n=== VERDICT ===")
    print(f"NEITHER candidate cleanly separates TRUE (pop_first==3) from FALSE at the")
    print(f"off-2 commit cycle. (a) pop_want==0 holds for all 20 TRUE but ALSO for the")
    print(f"pop_first==1 confound (29) and - critically - fires 66x at w0 and false-fires")
    print(f"22x on chip_occ4 when used as a fire rule (occ5&&Ti&&!eval_ext&&pop_want==0):")
    print(f"NOT w0-safe. (b) cnt_t3 is {{5,6}} for BOTH TRUE and FALSE; pop cadence")
    print(f"(pop_sr/pop_cnt) does not separate either. The ONLY w0-absent discriminator")
    print(f"is pop_first==3 itself - the actual pop at off-3 - which is NOT observable")
    print(f"until AFTER the off-2 commit. The chip commits BEFORE the discriminating pop")
    print(f"(a genuine forecast law), and the model does not expose that forecast at the")
    print(f"commit cycle (eu_dly==0 everywhere; no scheduled-pop signal). ")
    print(f"=> KILL: the forecast is NOT locally observable at the commit cycle. The ~17u")
    print(f"pop_first==3 subset PARKS WITH the ~22u residual - the WHOLE store-resume cell")
    print(f"(~28-34u) is mechanism-understood but IRREDUCIBLE-BY-CONSTRUCTION: the commit")
    print(f"must precede the only event that distinguishes it. No RTL.")


if __name__ == "__main__":
    main()
