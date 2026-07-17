#!/usr/bin/env python3
"""Class-5 BAND+AGE replay (Codex "Test A", 8086 mid-band-delay hypothesis).

Decisive analysis (NO RTL change). For EVERY aligned CODE->CODE prefetch-resume
opportunity (the full population, incl. timing-clean GO cells - NOT error-only),
over discovery + held-out corpora and uniform + random waits, test whether a
(byte-count definition, timer-semantics) combination makes the chip's GO-vs-PAUSE
decision COLLISION-FREE under the 8086 band+age rule:

    count 0-2            -> GO   (next free cycle)
    count 3-4, age <  2  -> PAUSE
    count 3-4, age >= 2  -> GO
    count 5-6            -> blocked

"Collision" = a cell sharing the same (count, band-age-bucket, bus-avail,
EU-ownership) that contains BOTH chip-GO and chip-PAUSE. If a combo becomes
collision-free (esp. on held-out) the "irreducible" 50/50 boundary was timer-state
aliasing and class-5 is recoverable. If identical (count, age, bus, EU) still
yields both outcomes, the 8086 mapping is insufficient.

Chip = ground truth (board). Model internals label the aligned prefix (model==chip
up to the first bus divergence, so state at/before the resume decision is
chip-accurate). Raw per-opportunity rows are dumped to JSONL for a follow-up RTL
predictor.

Usage: python3 sw/class5_bandage.py [--host H] [--discovery ...] [--heldout ...]
"""
import sys, argparse, json, time, traceback
import random as _r
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, CODE)

LOG = SW / "class5_bandage.log"
DUMP = SW / "class5_bandage.jsonl"

# ---- candidate byte-count definitions (evaluated at the decision edge row) ----
COUNTS = ["q_cnt", "q_avl", "q_cnt-pop", "cnt_next", "q_avl-pop+aged", "occupied"]


def cc(defn, r):
    """Candidate byte-count value for model row r under definition `defn`."""
    if defn == "q_cnt":
        return r["q_cnt"]
    if defn == "q_avl":
        return r["q_avl"]
    if defn == "q_cnt-pop":
        return r["q_cnt"] - r["pop_now"]
    if defn == "cnt_next":
        return r["cnt_next"]
    if defn == "q_avl-pop+aged":
        return r["q_avl"] - r["pop_now"] + r["q_aged"]
    if defn == "occupied":
        return r["occupied"]
    raise KeyError(defn)


def band(v):
    if v <= 2:
        return "low"
    if v <= 4:
        return "mid"
    return "full"


# ---- timer semantics: (start-event, clock-domain) -> age at decision edge ----
# start events:  entry (band entry), freefirst (first free-bus clock in band),
#                fetchdone (last CODE fetch completion while in band)
# clock domains: cpu (every CPU clock), free (only free-bus/idle clocks)
AGES = ["entry_cpu", "entry_free", "freefirst_cpu", "freefirst_free",
        "fetchdone_cpu", "fetchdone_free"]


def bus_free(r):
    """Row where the bus is idle/available for a prefetch (ST_TI == t==0)."""
    return r["t"] == 0


def ages_at(defn, kr, de, comp_rows):
    """Return {age_name: age} for candidate `defn` at decision-edge row `de`.

    Backward scan over the model trace: find the contiguous in-band (3-4) run
    ending at de, then measure each timer variant's elapsed clocks BEFORE de
    (so a cell that just entered the band has age 0 -> pauses)."""
    res = {a: 0 for a in AGES}
    v = cc(defn, kr[de])
    if band(v) != "mid":
        return res            # rule uses age only inside the 3-4 band
    # contiguous in-band run: earliest row s with cc in {3,4} for all [s,de]
    s = de
    while s - 1 >= 0 and band(cc(defn, kr[s - 1])) == "mid":
        s -= 1
    # entry-start ages (clocks already spent in band before the decision)
    res["entry_cpu"] = de - s
    res["entry_free"] = sum(1 for r in range(s, de) if bus_free(kr[r]))
    # freefirst: first free-bus clock within the run
    f = next((r for r in range(s, de + 1) if bus_free(kr[r])), None)
    if f is not None:
        res["freefirst_cpu"] = max(0, de - f)
        res["freefirst_free"] = sum(1 for r in range(f, de) if bus_free(kr[r]))
    # fetchdone: last CODE fetch completion (T4 row) within the run
    d = next((r for r in range(de, s - 1, -1) if r in comp_rows), None)
    if d is not None:
        res["fetchdone_cpu"] = max(0, de - d)
        res["fetchdone_free"] = sum(1 for r in range(d, de) if bus_free(kr[r]))
    return res


def opportunities(seed, host, image, wv, wname, tag, out):
    """Record every aligned CODE->CODE resume opportunity with all candidate
    counts, all timer ages, chip idle/label, and context fields."""
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    kt4 = {}; kt1 = {}; bi = -1
    comp_rows = set()   # model rows that are a CODE-fetch T4 completion
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1; kt1[bi] = ri
        if x["t"] == 5:
            kt4[bi] = ri
    for a in ka:
        if a["bs"] == CODE and a["t4"] is not None:
            comp_rows.add(a["t4"])
    cb, kb = bs_stream(ca), bs_stream(ka)
    n = min(len(cb), len(kb))
    D = next((j for j in range(n)
              if cb[j] != kb[j] or ca[j]["addr"] != ka[j]["addr"]), n)
    nopp = 0
    for i in range(1, D):
        if cb[i] != CODE or cb[i - 1] != CODE:
            continue
        if ca[i - 1]["t4"] is None or (i - 1) not in kt4:
            continue
        de = kt4[i - 1] + 1 if (kt4[i - 1] + 1) < len(kr) else kt4[i - 1]
        e = kr[de]
        # chip resume idle (Ti between pred T4 and succ T1) - ground truth
        cidle = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                    if crel[r]["t"] == 0)
        # GO = resumes ~immediately (idle<=1); PAUSE = idle>=3; 2 = ambiguous
        label = "go" if cidle <= 1 else ("pause" if cidle >= 3 else "amb")
        rec = dict(seed=seed, w=wname, tag=tag, i=i, cidle=cidle, label=label,
                   eu_req=e["eu_req"], eu_consuming=e["eu_consuming"],
                   t=e["t"], busfree=int(bus_free(e)))
        for defn in COUNTS:
            v = cc(defn, e)
            rec["cnt_" + defn] = v
            ag = ages_at(defn, kr, de, comp_rows)
            for a, av in ag.items():
                rec[f"age_{defn}_{a}"] = av
        out.append(rec)
        nopp += 1
    return nopp


def gather(seeds, host, tag, out, logf):
    wdefs = [("w1", [1] * 4096), ("w2", [2] * 4096), ("w3", [3] * 4096)]
    for (ws, wm) in [(4, 3), (7, 7)]:
        rr = _r.Random((ws << 8) | wm)
        wdefs.append((f"r{ws}.{wm}", [rr.randint(0, wm) for _ in range(4096)]))
    for seed in seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for wname, wv in wdefs:
            t0 = time.time()
            try:
                k = opportunities(seed, host, image, wv, wname, tag, out)
                msg = (f"[{time.strftime('%H:%M:%S')}] {tag} fz{seed} {wname}: "
                       f"{k} opps ({time.time()-t0:.0f}s) total={len(out)}")
            except Exception as ex:
                msg = (f"[{time.strftime('%H:%M:%S')}] {tag} fz{seed} {wname}: "
                       f"ERR {ex} ({time.time()-t0:.0f}s)")
                traceback.print_exc()
            print(msg); logf.write(msg + "\n"); logf.flush()
            # incremental dump so a crash doesn't lose the board time
            with DUMP.open("w") as df:
                for r in out:
                    df.write(json.dumps(r) + "\n")


def collision(rows, defn, agename, key_eu):
    """Collision (minority-mass) for a (count, age-def) combo over `rows`.
    FULL population incl. the full band (>=5 -> blocked -> a pure-PAUSE cell).
    Cell key = (count, age>=2, busfree[, eu_consuming]).
    Returns (n_used, n_in_mixed_cell, n_cells, n_mixed_cells, minmass)."""
    cells = defaultdict(lambda: {"go": 0, "pause": 0})
    used = 0
    for r in rows:
        if r["label"] == "amb":
            continue          # idle==2 is ambiguous; excluded from purity
        v = r["cnt_" + defn]
        age = r[f"age_{defn}_{agename}"]
        key = [v, int(age >= 2), r["busfree"]]
        if key_eu:
            key += [r["eu_consuming"]]
        cells[tuple(key)][r["label"]] += 1
        used += 1
    mixed = {k: c for k, c in cells.items() if c["go"] and c["pause"]}
    inmixed = sum(c["go"] + c["pause"] for c in mixed.values())
    # minority mass = irreducible residual (opps on wrong side of cell majority)
    minmass = sum(min(c["go"], c["pause"]) for c in cells.values())
    return used, inmixed, len(cells), len(mixed), minmass


def report(out, logf):
    def emit(s):
        print(s); logf.write(s + "\n")
    disc = [r for r in out if r["tag"] == "disc"]
    held = [r for r in out if r["tag"] == "held"]
    emit(f"\n=== population: {len(out)} aligned CODE->CODE opps "
         f"(disc={len(disc)} held={len(held)}) ===")
    for tag, sub in (("disc", disc), ("held", held)):
        g = sum(1 for r in sub if r["label"] == "go")
        p = sum(1 for r in sub if r["label"] == "pause")
        a = sum(1 for r in sub if r["label"] == "amb")
        emit(f"  {tag}: GO={g} PAUSE={p} AMB(idle2)={a}")

    emit("\nMetric = MINORITY MASS: sum over cells of min(GO,PAUSE) / used. This is"
         " the irreducible\nresidual - opportunities on the wrong side of their"
         " cell's majority vote. 0.0% = collision-FREE\n(the key fully determines"
         " chip GO/PAUSE => class-5 recoverable). Also shown: %opps in any mixed"
         " cell.")
    # baseline: count-only (no age) collision, for reference
    emit("\n--- baseline count-ONLY (no age term), key=(count,busfree) ---")
    emit("   defn                 disc minmass (mixed%)      held minmass (mixed%)")
    for defn in COUNTS:
        du, di, _, _, dmm = collision_countonly(disc, defn)
        hu, hi, _, _, hmm = collision_countonly(held, defn)
        emit(f"   {defn:18s}  {dmm:4d}/{du:<5d}={pct(dmm,du):>5} ({pct(di,du):>5})   "
             f"{hmm:4d}/{hu:<5d}={pct(hmm,hu):>5} ({pct(hi,hu):>5})")

    best_overall = None
    for key_eu, klbl in ((False, "key=(count,age>=2,busfree)"),
                         (True, "key=(count,age>=2,busfree,eu_consuming)")):
        emit(f"\n--- band+AGE  [{klbl}]  ranked by held minmass ---")
        emit("   defn              age-semantics       "
             "disc minmass (mixed%)      held minmass (mixed%)")
        results = []
        for defn in COUNTS:
            for agename in AGES:
                du, di, dc, dm, dmm = collision(disc, defn, agename, key_eu)
                hu, hi, hc, hm, hmm = collision(held, defn, agename, key_eu)
                results.append((hmm / max(1, hu), dmm / max(1, du),
                                defn, agename, du, di, dmm, hu, hi, hmm))
        results.sort()
        for _, _, defn, agename, du, di, dmm, hu, hi, hmm in results:
            emit(f"   {defn:16s}  {agename:16s}  "
                 f"{dmm:4d}/{du:<5d}={pct(dmm,du):>5} ({pct(di,du):>5})   "
                 f"{hmm:4d}/{hu:<5d}={pct(hmm,hu):>5} ({pct(hi,hu):>5})")
        b = results[0]
        emit(f"   >> BEST held-out minmass: {b[2]} / {b[3]}  "
             f"held={pct(b[9],b[7])}  disc={pct(b[6],b[4])}")
        if best_overall is None or b[0] < best_overall[0]:
            best_overall = (b[0], b[2], b[3], key_eu)

    # ---- DECISIVE mid-band (count in 3,4) age-separation table ----
    emit("\n--- MID-BAND (count 3-4) age separation: does age split GO/PAUSE? ---")
    emit("   (8086 rule predicts age<2->PAUSE, age>=2->GO; report actual polarity)")
    for defn in COUNTS:
        emit(f"   {defn}:")
        for v in (3, 4):
            for lab, lo, hi in (("age<2 ", 0, 2), ("age>=2", 2, 99)):
                g = sum(1 for r in out if r["label"] == "go"
                        and r["cnt_" + defn] == v
                        and lo <= r[f"age_{defn}_entry_cpu"] < hi)
                p = sum(1 for r in out if r["label"] == "pause"
                        and r["cnt_" + defn] == v
                        and lo <= r[f"age_{defn}_entry_cpu"] < hi)
                emit(f"      count={v} {lab}: GO={g:5d} PAUSE={p:4d}")

    # ---- residual mixed cells under the best (count,age[,eu]) key ----
    _, bdefn, bage, bkeu = best_overall
    emit(f"\n--- RESIDUAL mixed cells under BEST key ({bdefn},{bage}"
         f"{',eu_consuming' if bkeu else ''}) on HELD-OUT ---")
    cells = defaultdict(lambda: {"go": 0, "pause": 0})
    for r in held:
        if r["label"] == "amb":
            continue
        v = r["cnt_" + bdefn]
        key = (v, int(r[f"age_{bdefn}_{bage}"] >= 2), r["busfree"]) + \
            ((r["eu_consuming"],) if bkeu else ())
        cells[key][r["label"]] += 1
    for k, c in sorted(cells.items()):
        if c["go"] and c["pause"]:
            lbl = f"(cnt={k[0]},age>=2={k[1]},busfree={k[2]}"
            lbl += f",euCons={k[3]})" if bkeu else ")"
            emit(f"   {lbl}: GO={c['go']} PAUSE={c['pause']}")


def collision_countonly(rows, defn):
    cells = defaultdict(lambda: {"go": 0, "pause": 0})
    used = 0
    for r in rows:
        if r["label"] == "amb":
            continue
        v = r["cnt_" + defn]
        cells[(v, r["busfree"])][r["label"]] += 1
        used += 1
    mixed = {k: c for k, c in cells.items() if c["go"] and c["pause"]}
    inmixed = sum(c["go"] + c["pause"] for c in mixed.values())
    minmass = sum(min(c["go"], c["pause"]) for c in cells.values())
    return used, inmixed, len(cells), len(mixed), minmass


def pct(a, b):
    return f"{100*a/max(1,b):.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--discovery", type=int, nargs="+",
                    default=list(range(90000, 90008)))
    ap.add_argument("--heldout", type=int, nargs="+",
                    default=list(range(91000, 91006)))
    a = ap.parse_args()
    DUMP.unlink(missing_ok=True)
    with LOG.open("w") as logf:
        logf.write(f"start {time.ctime()}\n"); logf.flush()
        out = []
        gather(a.discovery, a.host, "disc", out, logf)
        gather(a.heldout, a.host, "held", out, logf)
        report(out, logf)
        logf.write(f"done {time.ctime()}\n")


if __name__ == "__main__":
    main()
