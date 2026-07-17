#!/usr/bin/env python3
"""ARC 2 ARBITER-SURFACE PROBE (board-free).

The re-key strawman was corrected: the prefetch_ok claim never arbitrates the 5/5
swap sites, because at those sites the model COMMITTED the EU access - only possible
via want_eu (eu_req && eu_ready). The 288u paired-swap mass is decided at the SLOT
PRIORITY (want_half2 > want_eu > prefetch), a FIXED ordering the chip evidently makes
CONDITIONAL: with a starved queue + demand-deadline expired, the scheduled refill
outranks even a READY EU access for that slot.

This probe (board-free: the chip ground truth is already in class5_census544.jsonl.gz;
we only re-derive the MODEL arbiter commit-slot fields via the Verilator TB) attaches
the arbiter state at each census transition's successor-access decision edge, and
tests whether ONE discriminator covers the paired/EU-timing mass.

METHODOLOGY COROLLARY (now standing): counterfactuals score against the REAL
implemented arbiter (want_half2>want_eu>prefetch), full conjunct, with the baseline's
own accuracy printed alongside. No proxy.

Commit-slot fields (TB d[62..65], DUT bit-identical): want_eu, slot_fire, slot_id,
eu_kind. Derived from the per-cycle trace: d_cnt (frame-A cnt_next @ pred T3),
ready_lead_age (consecutive eu_ready==1 cycles ending at the decision edge).
"""
import sys, json, gzip, random as _r
from pathlib import Path
from collections import defaultdict, Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import (generate, compose, run_tb_internal, accesses,
                          bs_stream, _sname, BSN)

CENSUS = SW / "class5_census544.jsonl.gz"
SLOTNAME = {0: "NONE", 1: "T3_EVAL", 2: "TI_PLAIN", 3: "T4_FLUSH_STAGED",
            4: "EVAL_EXT", 5: "FF_TI", 6: "DEFER_IDLE", 7: "FLUSH_HOLD",
            8: "DEFER_T4", 9: "FF_T4", 10: "LAW_RESUME"}


def wv_of(ws, wmax):
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


_img_cache = {}
def image_for(seed):
    if seed not in _img_cache:
        g = generate(f"fz{seed}", exts=())
        _img_cache[seed] = compose(g)[0]
    return _img_cache[seed]


import os, pickle
CACHE = Path(os.environ.get("ARB_CACHE",
             "/tmp/claude-1000/-home-wickerwaka-src-nec-test/"
             "d28f988f-be24-491f-b4b1-5a987e9cc8bb/scratchpad/arb_tb_cache"))
CACHE.mkdir(parents=True, exist_ok=True)


def model_accesses(seed, ws, wmax):
    cf = CACHE / f"{seed}_{ws}_{wmax}.pkl"
    if cf.exists():
        return pickle.loads(cf.read_bytes())
    recs = _model_accesses(seed, ws, wmax)
    cf.write_bytes(pickle.dumps(recs))
    return recs


def _model_accesses(seed, ws, wmax):
    """Run the TB (board-free) and return per-model-access records with the
    arbiter commit-slot fields at the access's decision edge (T1-1)."""
    kr = run_tb_internal(image_for(seed), 4200, wv_of(ws, wmax))
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    recs = []
    for j, a in enumerate(ka):
        t1 = a["t1"]
        dr = kr[max(0, t1 - 1)]                 # decision edge (same as gaperr)
        # frame-A d_cnt: cnt_next at predecessor access's T3 cycle
        d_cnt = -1
        if j > 0 and ka[j - 1]["t4"] is not None:
            t3 = ka[j - 1]["t4"]
            while t3 > 0 and kr[t3]["t"] != 3:
                t3 -= 1
            if kr[t3]["t"] == 3:
                d_cnt = kr[t3]["cnt_next"]
        # ready-lead-age: consecutive eu_ready==1 rows ending at dr
        age = 0
        r = max(0, t1 - 1)
        while r >= 0 and kr[r]["eu_ready"] == 1:
            age += 1; r -= 1
        # the actual FIRED slot that produced this access (staged commits fire
        # 1-2 cycles before delivery, so slot_id at t1-1 is often NONE)
        fired = 0
        for rr in range(max(0, t1 - 3), t1 + 1):
            if kr[rr]["slot_fire"] == 1:
                fired = kr[rr]["slot_id"]
        # model Ti count in the interval (matches census mti)
        mti = -1
        if j > 0 and ka[j - 1]["t4"] is not None:
            mti = sum(1 for rr in range(ka[j - 1]["t4"] + 1, t1)
                      if kr[rr]["t"] == 0)
        recs.append(dict(
            j=j, bs=a["bs"], tw=a["tw"], addr=a["addr"],
            prev_bs=ka[j - 1]["bs"] if j > 0 else -1,
            prev_tw=ka[j - 1]["tw"] if j > 0 else -1,
            # --- arbiter commit-slot fields at the decision edge ---
            want_eu=dr["want_eu"], slot_id=dr["slot_id"], fired_slot=fired,
            slot_fire=dr["slot_fire"], eu_kind=dr["eu_kind"],
            eu_ready=dr["eu_ready"], eu_req=dr["eu_req"],
            eu_req_p1=dr["eu_req_p1"], q_cnt=dr["q_cnt"], occ=dr["occupied"],
            cnt_next=dr["cnt_next"], d_cnt=d_cnt, ready_lead_age=age,
            q_aged=dr["q_aged"], eval_ext=dr["eval_ext"], q_flush=dr["q_flush"],
            prefetch_ok=dr["prefetch_ok"], prefetch_ext=dr["prefetch_ext"],
            pf_starved=dr["pf_starved"], pf_late_rsv=dr["pf_late_rsv"],
            owns_slot=dr["owns_slot"], eu_rsv_lead=dr["eu_rsv_lead"],
            # census-match signature
            m_state=_sname(dr["state"]), m_occ=dr["occupied"],
            m_qcnt=dr["q_cnt"], m_qaged=dr["q_aged"], mti=mti))
    return recs


def sig(r, census=False):
    """Join signature = SUCCESSOR-ACCESS-ONLY functions (independent of the
    alignment/predecessor, which diverges from model-adjacency exactly at the swap
    sites we care about). The census's m_state/m_occ/m_qcnt/m_qaged are read at the
    successor's decision row kr[t1-1] - the same row this probe reads - so they match
    the model access regardless of ordering. cur_bs/cur_par/cur_tw are the aligned
    successor's own type/parity/waits (shared chip==model at an aligned pair)."""
    if census:
        return (BSN_inv(r["cur_bs"]), r["cur_par"], r["cur_tw"],
                r["m_state"], r["m_occ"], r["m_qcnt"], r["m_qaged"])
    return (r["bs"], r["addr"] & 1, r["tw"],
            r["m_state"], r["m_occ"], r["m_qcnt"], r["m_qaged"])


BSN2 = {"INTA": 0, "IOR": 1, "IOW": 2, "HALT": 3, "CODE": 4, "MEMR": 5,
        "MEMW": 6, "PASV": 7}
def BSN_inv(name):
    return BSN2.get(name, name)


def paired(r):
    """Ordering-artifact partition (documented reconstruction of PROBE 1): a
    nonzero-ge row whose immediately-adjacent (di==1) neighbor carries the equal-
    magnitude opposite-sign impulse. NOTE: PROBE 1's published 288u used an ad-hoc
    (uncommitted) matcher; this strict reconstruction yields a smaller number, so we
    report BOTH the strict-paired mass and the total EU-timing mass and characterize
    the mechanism rather than relying on the exact figure."""
    g = r["ge"]
    if g == 0:
        return False
    if r.get("di_next") == 1 and r.get("ge_next") == -g:
        return True
    if r.get("di_prev") == 1 and r.get("ge_prev") == -g:
        return True
    return False


def bucket(v):
    return "<=1" if v <= 1 else ("2-4" if v <= 4 else ">4")


def main():
    census = [json.loads(l) for l in gzip.open(CENSUS, "rt")]
    combos = sorted(set((r["seed"], r["ws"], r["wmax"]) for r in census))
    print(f"census nonzero rows {len(census)}, |ge| mass "
          f"{sum(abs(r['ge']) for r in census)}, combos {len(combos)}")

    # --- board-free TB regen + join (ordinal-proximity tiebreak for collisions) ---
    matched, unmatched, collided, keydisagree = 0, 0, 0, 0
    all_recs = {}                        # combo -> list of model access recs
    in_census = defaultdict(set)         # combo -> set of model access j joined
    for (seed, ws, wmax) in combos:
        recs = model_accesses(seed, ws, wmax)
        all_recs[(seed, ws, wmax)] = recs
        by_sig = defaultdict(list)
        for r in recs:
            by_sig[sig(r)].append(r)
        for c in census:
            if (c["seed"], c["ws"], c["wmax"]) != (seed, ws, wmax):
                continue
            cand = by_sig.get(sig(c, census=True), [])
            if not cand:
                c["arb"] = None; unmatched += 1; continue
            if len(cand) > 1:
                # collisions share the successor decision-row state; break the tie
                # by model-ordinal proximity to the chip ordinal i (alignment is
                # near-identity), and record whether candidates AGREE on the arbiter
                # key (want_eu, q_cnt bucket, eu_kind) - if they do, attribution is
                # collision-robust.
                keys = set((r["want_eu"], bucket(r["q_cnt"]), r["eu_kind"])
                           for r in cand)
                if len(keys) > 1:
                    keydisagree += 1
                cand = sorted(cand, key=lambda r: abs(r["j"] - c["i"]))
                collided += 1
            else:
                matched += 1
            c["arb"] = cand[0]
            in_census[(seed, ws, wmax)].add(cand[0]["j"])
    print(f"\nJOIN (board-free): matched-unique {matched}, collided(tiebroken) "
          f"{collided}, unmatched {unmatched} of {len(census)}; "
          f"collision key-disagreements {keydisagree} "
          f"(low => attribution collision-robust)")

    ok = [c for c in census if c.get("arb")]
    # ---- (1) arbiter decision at the successor commit ----
    we = [c for c in ok if c["arb"]["want_eu"] == 1]
    pf = [c for c in ok if c["arb"]["want_eu"] == 0]
    print(f"\n=== successor commit by arbiter branch ===")
    print(f"  want_eu (ready-EU committed): {len(we)} rows, "
          f"|ge| {sum(abs(c['ge']) for c in we)}")
    print(f"  prefetch/other             : {len(pf)} rows, "
          f"|ge| {sum(abs(c['ge']) for c in pf)}")
    print(f"  fired_slot dist (all matched): "
          f"{Counter(SLOTNAME.get(c['arb']['fired_slot']) for c in ok)}")
    print(f"  want_eu fired_slot dist: "
          f"{Counter(SLOTNAME.get(c['arb']['fired_slot']) for c in we)}")

    # ---- (2) paired/ordering partition: is it the want_eu arbitration family? ----
    P = [c for c in census if paired(c)]
    p_mass = sum(abs(c["ge"]) for c in P)
    p_code = sum(abs(c["ge"]) for c in P if c["cur_bs"] == "CODE")
    p_we = sum(abs(c["ge"]) for c in P
               if c.get("arb") and c["arb"]["want_eu"] == 1)
    print(f"\n=== paired (strict reconstruction) - IS IT THE want_eu SWAP FAMILY? ===")
    print(f"  strict-paired mass {p_mass} rows {len(P)}  "
          f"(PROBE 1 ad-hoc figure was 288u; see paired() docstring)")
    print(f"  paired CODE-successor (PREFETCH commit, want_eu=0) mass: {p_code} "
          f"({100*p_code/max(1,p_mass):.0f}%)")
    print(f"  paired want_eu-committed (the hypothesised arbitration swap) mass: "
          f"{p_we} ({100*p_we/max(1,p_mass):.0f}%)  <-- the arbiter surgery's actual "
          f"reachable target")
    ptrans = Counter(c["prev_bs"] + "->" + c["cur_bs"] for c in P)
    print(f"  paired by transition: {ptrans.most_common(6)}")

    # ---- (3) mechanism: where does the census mass sit, by arbiter branch? ----
    print(f"\n=== census mass by (want_eu, q_cnt-bucket, eu_kind) ===")
    tab = defaultdict(lambda: [0, 0])
    for c in ok:
        a = c["arb"]
        k = (a["want_eu"], bucket(a["q_cnt"]), a["eu_kind"])
        tab[k][0] += 1; tab[k][1] += abs(c["ge"])
    print("  (want_eu, q_cnt, eu_kind) -> rows, |ge|mass:")
    for k in sorted(tab, key=lambda k: -tab[k][1]):
        print(f"    we={k[0]} qcnt{k[1]:<4} kind{k[2]}: rows {tab[k][0]:3d}  "
              f"mass {tab[k][1]}")

    # ---- (4) GO GATE: form-free want_eu-demotion discriminator ----
    # TARGET = the want_eu-committed census mass (the mass a want_eu demotion could
    # move). AGREEING DENOMINATOR (board-free) = every model want_eu commit whose
    # ordering the chip AGREED with, i.e. NOT joined to a nonzero census row (ge==0).
    # A demotion predicate firing THERE is a false-flip (it would break a correct
    # ordering). COROLLARY: scored against the real arbiter (want_eu is the real
    # branch); baseline printed alongside.
    print(f"\n=== (GO GATE) form-free want_eu-demotion discriminator ===")
    we_cens = [c for c in ok if c["arb"]["want_eu"] == 1]
    tgt_mass = sum(abs(c["ge"]) for c in we_cens)
    # agreeing (ge==0) want_eu commits, board-free
    agree = []
    for combo, recs in all_recs.items():
        for r in recs:
            if r["want_eu"] == 1 and r["j"] not in in_census[combo]:
                agree.append(r)
    print(f"  TARGET want_eu census mass {tgt_mass} ({len(we_cens)} rows);  "
          f"AGREEING (ge==0) want_eu commits {len(agree)} (false-flip denominator)")
    print(f"  BASELINE (real arbiter, no demotion): coverage 0%, false-flip 0% "
          f"[the fixed want_half2>want_eu>prefetch priority]")

    # form-free single-predicate grid over the arbiter keys
    preds = []
    for qc in ("<=0", "<=1", "<=2"):
        qf = {"<=0": lambda a: a["q_cnt"] == 0, "<=1": lambda a: a["q_cnt"] <= 1,
              "<=2": lambda a: a["q_cnt"] <= 2}[qc]
        preds.append((f"q_cnt{qc}", qf))
        for kd, kn in ((0, "MEM"), (1, "IO")):
            preds.append((f"q_cnt{qc} & kind={kn}",
                          (lambda a, qf=qf, kd=kd: qf(a) and a["eu_kind"] == kd)))
        preds.append((f"q_cnt{qc} & d_cnt<=1",
                      (lambda a, qf=qf: qf(a) and 0 <= a["d_cnt"] <= 1)))
        preds.append((f"q_cnt{qc} & age>=2",
                      (lambda a, qf=qf: qf(a) and a["ready_lead_age"] >= 2)))
    preds += [("eval_ext", lambda a: a["eval_ext"] == 1),
              ("pf_starved", lambda a: a["pf_starved"] == 1),
              ("kind=IO", lambda a: a["eu_kind"] == 1),
              ("d_cnt<=1", lambda a: 0 <= a["d_cnt"] <= 1),
              ("occ<=2", lambda a: a["occ"] <= 2)]
    print(f"  {'predicate':28s} {'cover%':>7} {'covmass':>8} {'falseflip%':>11} "
          f"{'ff_rows':>8}")
    best = None
    for name, pred in preds:
        cov = sum(abs(c["ge"]) for c in we_cens if pred(c["arb"]))
        ff = sum(1 for r in agree if pred(r))
        ffp = 100 * ff / max(1, len(agree))
        covp = 100 * cov / max(1, tgt_mass)
        flag = "  <-- GATE" if (covp >= 60 and ffp < 2) else (
               "  KILL(<40%)" if covp < 40 else "")
        print(f"  {name:28s} {covp:6.0f}% {cov:8d} {ffp:10.2f}% {ff:8d}{flag}")
        if covp >= 60 and ffp < 2 and (best is None or cov > best[1]):
            best = (name, cov)
    print(f"  GATE RESULT: {'PASS -> '+best[0] if best else 'NO predicate reaches >=60% cover with <2% false-flip'}")
    print(f"  NOTE: total census mass 544; want_eu-decided target is only {tgt_mass} "
          f"({100*tgt_mass/544:.0f}%) - the rest is prefetch/other commits a want_eu "
          f"demotion cannot touch.")

    # ---- (5) EU-anchored resume MEMW/IOW->CODE (independent, form-free) ----
    print(f"\n=== EU-anchored resume: *->CODE with EU predecessor ===")
    euc = [c for c in ok if c["cur_bs"] == "CODE" and c["prev_bs"] != "CODE"]
    print(f"  rows {len(euc)}  |ge| {sum(abs(c['ge']) for c in euc)}")
    bt = defaultdict(lambda: [0, 0])
    for c in euc:
        bt[c["prev_bs"]][0] += 1; bt[c["prev_bs"]][1] += abs(c["ge"])
    for k in sorted(bt, key=lambda k: -bt[k][1]):
        print(f"    {k}->CODE: rows {bt[k][0]}  mass {bt[k][1]}")

    # ---- (6) carve-out re-scores vs REAL baseline ----
    print(f"\n=== carve-out firing at census sites (real-baseline context) ===")
    for f in ("pf_starved", "pf_late_rsv", "owns_slot", "eu_rsv_lead"):
        fires = [c for c in ok if c["arb"][f] == 1]
        print(f"  {f:12s}: fires at {len(fires)} census sites, "
              f"|ge| {sum(abs(c['ge']) for c in fires)}")


if __name__ == "__main__":
    main()
