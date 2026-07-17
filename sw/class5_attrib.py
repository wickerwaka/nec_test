#!/usr/bin/env python3
"""2a/2b: ATTRIBUTE the >=+2 block and the negative tail, per row, to a cause.

The >=+2 block (~126 proxy units, {2:6, 3:26, 4:4, 5:4}) is +3-DOMINATED, it
PREDATES the class-5 law, and it SURVIVED every build we tried. Nobody has ever
attributed it.

PRE-REGISTERED HYPOTHESIS (coordinator): lowband-veto FALSE PAUSES. The model
pauses to cidle 4 where the chip GOes at cidle 1 -> gap_error = 4-1 = +3
EXACTLY. lowband was fitted BEFORE flush attribution existed, and its occ4/age-3
term is already known to be 11/11 flush-driven.
KILL: no single cause accounts for >=40%.

2b: the negative tail (85u). KILL: dominated by occ3/d2 -> that cell is a floor
candidate, which is itself a finding.
"""
import sys, json, gzip
import random as _r
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import generate, compose, run_tb_internal, accesses, CODE

def wv():
    wd = {"w1": [1]*4096, "w2": [2]*4096, "w3": [3]*4096}
    for ws, wm in [(4, 3), (7, 7)]:
        rr = _r.Random((ws << 8) | wm)
        wd[f"r{ws}.{wm}"] = [rr.randint(0, wm) for _ in range(4096)]
    return wd

def midx(rows):
    kt1, kt4, bi = {}, {}, -1
    for ri, x in enumerate(rows):
        if x["t"] == 1: bi += 1; kt1[bi] = ri
        if x["t"] == 5: kt4[bi] = ri
    return kt1, kt4

def main():
    logf = (SW/"class5_attrib.log").open("w")
    def log(s=""):
        print(s, flush=True); logf.write(s+"\n"); logf.flush()

    corp = defaultdict(dict)
    for l in gzip.open(SW/"class5_bandage.jsonl.gz", "rt"):
        r = json.loads(l); corp[(r["seed"], r["w"])][r["i"]] = r
    for l in open(SW/"class5_bandage.jsonl"):
        r = json.loads(l); corp[(r["seed"], r["w"])][r["i"]] = r
    # flush attribution from the flushtraj dump
    fl = {}
    for l in gzip.open(SW/"class5_flushtraj2.jsonl.gz", "rt"):
        r = json.loads(l)
        if r.get("_meta"): continue
        fl[(r["seed"], r["w"], r["i"])] = r["flush_win"]
    W = wv()
    rows_out = []
    for (seed, wn), ops in sorted(corp.items()):
        g = generate(f"fz{seed}", exts=()); image, meta = compose(g)
        tr = run_tb_internal(image, 4200, W[wn])
        kt1, kt4 = midx(tr)
        for i, c in ops.items():
            if (i-1) not in kt4 or i not in kt1: continue
            t4 = kt4[i-1]
            mc = sum(1 for r in range(t4+1, kt1[i]) if tr[r]["t"] == 0)
            ge = mc - c["cidle"]
            if ge == 0: continue
            win = range(t4, min(kt1[i]+1, len(tr)))
            lb = any(tr[r]["lowband_pause"] for r in win)
            lawb = any(tr[r]["law_block"] for r in win)
            rows_out.append(dict(seed=seed, w=wn, i=i, ge=ge, chip=c["cidle"],
                                 model=mc, lowband=lb, law=lawb,
                                 flush=fl.get((seed, wn, i)),
                                 occ=c["cnt_occupied"], age=c["age_occupied_entry_cpu"],
                                 qcnt=c["cnt_q_cnt"], label=c["label"]))

    log("=== 2a: ATTRIBUTION OF THE >=+2 BLOCK ===")
    p2 = [r for r in rows_out if r["ge"] >= 2]
    units = sum(r["ge"] for r in p2)
    log(f"  n={len(p2)} rows, {units} units")
    log(f"  ge dist: {dict(sorted(defaultdict(int, {k: sum(1 for r in p2 if r['ge']==k) for k in set(r['ge'] for r in p2)}).items()))}")
    log("\n  PRE-REGISTERED HYPOTHESIS: lowband FALSE PAUSE -> model 4, chip 1 -> +3")
    h = [r for r in p2 if r["model"] == 4 and r["chip"] == 1]
    log(f"  rows with model==4 AND chip==1 (the exact signature): {len(h)}/{len(p2)}"
        f"  ({100*len(h)/max(1,len(p2)):.0f}%)")
    log(f"    of those, lowband-armed: {sum(1 for r in h if r['lowband'])}")
    log(f"    of those, law-armed    : {sum(1 for r in h if r['law'])}")
    log(f"    of those, flush-window : {sum(1 for r in h if r['flush']==1)}")

    log("\n  --- (model,chip) pairs across the whole >=+2 block ---")
    mc = defaultdict(int)
    for r in p2: mc[(r["model"], r["chip"])] += 1
    for k, v in sorted(mc.items(), key=lambda x: -x[1]):
        log(f"    model={k[0]:<3} chip={k[1]:<3}: {v:3d}  (ge={k[0]-k[1]:+d})")

    log("\n  --- cause census over the >=+2 block ---")
    cause = defaultdict(int)
    for r in p2:
        if r["flush"] == 1: cause["flush-window row"] += 1
        elif r["lowband"] and not r["law"]: cause["lowband-armed ONLY"] += 1
        elif r["law"] and not r["lowband"]: cause["law-armed ONLY"] += 1
        elif r["law"] and r["lowband"]: cause["BOTH armed"] += 1
        else: cause["NEITHER armed (legacy path)"] += 1
    for k, v in sorted(cause.items(), key=lambda x: -x[1]):
        log(f"    {k:32s}: {v:3d}  ({100*v/len(p2):.0f}%)")
    top = max(cause.values())/len(p2)
    log(f"\n  >> dominant cause share: {100*top:.0f}%   "
        f"{'PASS (>=40%)' if top>=0.4 else 'KILL (<40%, no single cause)'}")

    log("\n  --- >=+2 by (occ, age) ---")
    ca = defaultdict(int)
    for r in p2: ca[(r["occ"], r["age"])] += 1
    log(f"    {dict(sorted(ca.items()))}")

    log("\n=== 2b: ATTRIBUTION OF THE NEGATIVE TAIL ===")
    n2 = [r for r in rows_out if r["ge"] < 0]
    nu = sum(-r["ge"] for r in n2)
    log(f"  n={len(n2)} rows, {nu} units")
    mcn = defaultdict(int)
    for r in n2: mcn[(r["model"], r["chip"])] += 1
    log("  --- (model,chip) pairs ---")
    for k, v in sorted(mcn.items(), key=lambda x: -x[1])[:8]:
        log(f"    model={k[0]:<3} chip={k[1]:<3}: {v:3d}  (ge={k[0]-k[1]:+d})")
    can = defaultdict(int)
    for r in n2: can[(r["occ"], r["qcnt"])] += 1
    log(f"\n  by (occ@T4+1, q_cnt): {dict(sorted(can.items()))}")
    o32 = sum(1 for r in n2 if r["occ"] == 3 and r["qcnt"] == 2)
    log(f"  occ3/qcnt2 share: {o32}/{len(n2)} = {100*o32/max(1,len(n2)):.0f}%"
        f"  {'-> FLOOR CANDIDATE (a finding)' if o32/max(1,len(n2))>=0.4 else ''}")
    json.dump(rows_out, (SW/"class5_attrib.json").open("w"), indent=1)
    log(f"\nwrote {SW/'class5_attrib.json'}")
    logf.close()

if __name__ == "__main__":
    main()
