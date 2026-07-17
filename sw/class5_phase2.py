#!/usr/bin/env python3
"""PHASE 2: SHADOW-FSM SWEEP over queue trajectories (offline; no RTL change).

HYPOTHESIS "H-LV v2": the chip runs a periodic loader evaluation that LATCHES a
refill verdict PEND; it chains iff PEND was set at the last evaluation before
T4. The model's sole defect is computing the verdict INSTANTANEOUSLY at
eval_ext instead of reading the latched PEND.

TEST: is chip GO/PAUSE (+cidle) a deterministic function of the queue
trajectory plus a small latched-verdict/grid state? If yes, H-LV v2 is real and
buildable. If no variant works, the missing state is not a queue-trajectory
projection under any tested grid anchor, and only a chip factorial can proceed.

SCOPE (coordinator amendment, post-Phase-1): NON-FLUSH rows only. Phase 1
proved flush is a distinct mechanism with its own cidle alphabet ({3:40, 4:7})
vs non-flush ({3:118, 4:132, 5:16, ..., 22:4}); mixing them corrupts the fit.
Flush rows are reported separately, never fitted. The cidle-2 'amb' sub-check is
dropped: all 62 amb rows are flush-window rows, so flush already answers it.

SHARPENED TARGET: occ3/age1 (non-flush, cidle {3:11, 4:8}) and occ3/age2
(non-flush, cidle {3:14, 4:7}) are duration-MIXED inside one cell with zero
flush rows to blame, and lie entirely inside the no-truncation safe set. No
static field separates 3 from 4 there (verified). They are the cleanest test bed.

DISCIPLINE: fit on gz-disc (90000-07) ONLY -> FREEZE -> then gz-held (91000-05)
and fresh (90008-17 / 91006-11) are scored once, with no re-selection.

Usage: python3 sw/class5_phase2.py [--w0-check]
"""
import sys, json, gzip, argparse, itertools, time
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
DUMP = SW / "class5_flushtraj.jsonl.gz"
LOG = SW / "class5_phase2.log"
OUT = SW / "class5_phase2.json"

OCC, AGE = "cnt_occupied", "age_occupied_entry_cpu"

# ---- variant axes (exactly the sweep the task specifies) ----
DEMANDS = ["q_cnt<=1", "q_cnt<=2", "q_avl<=2", "cnt_next<=2",
           "occupied<=3", "occupied<=4"]
PERIODS = [1, 2]
ANCHORS = ["reset", "lastT1", "lastT4", "lastflush"]
OFFSETS = [0, 1]
CLEARS = ["noD", "issue", "both"]
READS = ["T4", "T4+1", "T3rdy"]
LAGS = [2, 3]

T_TI, T_T1, T_T3, T_T4 = 0, 1, 3, 5


class Traj:
    """Decoded trajectory for one opportunity, indexed by absolute clock."""
    __slots__ = ("clk", "row", "lo", "hi", "t4", "t1n", "pred_tw")

    def __init__(self, rec, fi):
        tr = rec["traj"]
        ci = fi["clk"]
        self.lo = tr[0][ci]
        self.hi = tr[-1][ci]
        self.row = {t[ci]: t for t in tr}
        self.t4 = rec["t4_clk"]
        self.t1n = rec["t1_clk"]
        self.pred_tw = rec["pred_tw"]


def demand(t, fi, d):
    if d == "q_cnt<=1":
        return t[fi["q_cnt"]] <= 1
    if d == "q_cnt<=2":
        return t[fi["q_cnt"]] <= 2
    if d == "q_avl<=2":
        return t[fi["q_avl"]] <= 2
    if d == "cnt_next<=2":
        return t[fi["cnt_next"]] <= 2
    if d == "occupied<=3":
        return t[fi["occupied"]] <= 3
    if d == "occupied<=4":
        return t[fi["occupied"]] <= 4
    raise KeyError(d)


def anchor_clk(tj, fi, anch):
    """Absolute clock the eval grid is phase-locked to (None = unavailable)."""
    if anch == "reset":
        return 0
    if anch == "lastT4":
        return tj.t4
    if anch == "lastT1":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["t"]] == T_T1]
        return c[-1] if c else None
    if anch == "lastflush":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["q_flush"]]]
        return c[-1] if c else None
    raise KeyError(anch)


def read_clk(tj, fi, rd):
    if rd == "T4":
        return tj.t4
    if rd == "T4+1":
        return tj.t4 + 1
    if rd == "T3rdy":
        c = [k for k in range(tj.lo, tj.t4 + 1)
             if k in tj.row and tj.row[k][fi["t"]] == T_T3]
        return c[-1] if c else None
    raise KeyError(rd)


def simulate(tj, fi, v):
    """Run the shadow FSM. Returns (pred_label, pred_cidle or None, ok).

    ok=False => this variant cannot be evaluated on this row (anchor/read point
    or the required forward slot lies outside the recorded trajectory). Such
    rows are reported as unevaluable, never silently scored."""
    d, per, anch, off, clr, rd, lag = v
    a = anchor_clk(tj, fi, anch)
    rp = read_clk(tj, fi, rd)
    if a is None or rp is None or rp < tj.lo:
        return None, None, False

    def is_eval(k):
        return (k - a) % per == (off % per)

    pend = 0
    for k in range(tj.lo, rp + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        if is_eval(k):
            if demand(t, fi, d):
                pend = 1
            elif clr in ("noD", "both"):
                pend = 0
        if clr in ("issue", "both") and t[fi["t"]] == T_T1 and k != rp:
            pend = 0

    if pend:
        return "go", (0 if tj.pred_tw == 0 else 1), True

    # PAUSE: demand_slot = first eval slot >= read point where D holds
    ds = None
    for k in range(rp, tj.hi + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        if is_eval(k) and demand(t, fi, d):
            ds = k
            break
    if ds is None:
        return "pause", None, True          # pauses, duration beyond traj
    # The resume cannot start before T4+1: the bus is still running the
    # predecessor fetch until T4. Without this clamp a read point at T3 lets
    # demand_slot precede T4 and yields nonsense cidle (-1/0). Clamping is
    # physically required and can only HELP the hypothesis - the kill below is
    # therefore not an artifact of an unclamped predictor.
    L = None
    for k in range(max(ds + lag, tj.t4 + 1), tj.hi + 1):
        if is_eval(k):
            L = k
            break
    if L is None:
        return "pause", None, True
    return "pause", L - tj.t4 - 1, True


def score(rows, fi, v, band_only=True):
    """Confusion + exact-cidle over `rows` for variant v."""
    r = dict(n=0, uneval=0, gg=0, gp=0, pg=0, pp=0,
             ex=0, ex_n=0, nocid=0, err_cells=defaultdict(int))
    for rec, tj in rows:
        if band_only and rec[OCC] > 4:
            continue
        r["n"] += 1
        pl, pc, ok = simulate(tj, fi, v)
        if not ok:
            r["uneval"] += 1
            continue
        cl = rec["label"]
        if cl == "go" and pl == "go":
            r["gg"] += 1
        elif cl == "go" and pl == "pause":
            r["gp"] += 1
            r["err_cells"][(rec[OCC], rec[AGE])] += 1
        elif cl == "pause" and pl == "go":
            r["pg"] += 1
            r["err_cells"][(rec[OCC], rec[AGE])] += 1
        elif cl == "pause" and pl == "pause":
            r["pp"] += 1
        if cl == "pause":
            if pc is None:
                r["nocid"] += 1
            else:
                r["ex_n"] += 1
                r["ex"] += int(pc == rec["cidle"])
    r["errs"] = r["gp"] + r["pg"]
    return r


def load(fi_out):
    L = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    meta, recs = L[0], L[1:]
    fi = {n: i for i, n in enumerate(meta["traj_fields"])}
    fi_out.update(fi)
    out = []
    for rec in recs:
        out.append((rec, Traj(rec, fi)))
    return meta, out


def split(rows):
    """gz-disc = fit set; gz-held and fresh are scored once, after the freeze."""
    disc = [x for x in rows if x[0]["src"] == "gz" and x[0]["tag"] == "disc"]
    held = [x for x in rows if x[0]["src"] == "gz" and x[0]["tag"] == "held"]
    fresh = [x for x in rows if x[0]["src"] == "fresh"]
    return disc, held, fresh


def vname(v):
    d, per, anch, off, clr, rd, lag = v
    return (f"D={d} period={per} anchor={anch} offset={off} "
            f"clear={clr} read={rd} lag={lag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-only", action="store_true",
                    help="score only occ3/age1-4 (diagnostic)")
    a = ap.parse_args()
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    fi = {}
    meta, allrows = load(fi)
    # ---- SCOPE: non-flush only (coordinator amendment) ----
    nf = [x for x in allrows if x[0]["flush_win"] == 0]
    flush = [x for x in allrows if x[0]["flush_win"] == 1]
    log("=== PHASE 2: SHADOW-FSM SWEEP (H-LV v2) ===")
    log(f"rtl={meta.get('rtl')}")
    log(f"rows: {len(allrows)} total -> NON-FLUSH {len(nf)} fitted, "
        f"{len(flush)} flush rows EXCLUDED (separate mechanism, reported only)")
    # amb rows are all flush, so non-flush is pure go/pause; assert it
    ambnf = [x for x in nf if x[0]["label"] == "amb"]
    log(f"amb rows among non-flush: {len(ambnf)} (expect 0 - all amb are flush)")
    nf = [x for x in nf if x[0]["label"] in ("go", "pause")]

    disc, held, fresh = split(nf)
    log(f"fit set gz-disc={len(disc)}  |  frozen tests: gz-held={len(held)} "
        f"fresh={len(fresh)}")
    for nm, s in (("disc", disc), ("held", held), ("fresh", fresh)):
        b = [x for x in s if x[0][OCC] <= 4]
        g = sum(1 for x in b if x[0]["label"] == "go")
        p = sum(1 for x in b if x[0]["label"] == "pause")
        log(f"  {nm}: low+mid(occ<=4) n={len(b)} GO={g} PAUSE={p}")

    variants = list(itertools.product(DEMANDS, PERIODS, ANCHORS, OFFSETS,
                                      CLEARS, READS, LAGS))
    # period 1 makes offset meaningless -> dedupe
    variants = [v for v in variants if not (v[1] == 1 and v[3] == 1)]
    log(f"\nsweeping {len(variants)} variants on gz-disc ONLY...")

    res = []
    t0 = time.time()
    allres = []
    for v in variants:
        s = score(disc, fi, v)
        allres.append((v, s))
        # ELIGIBILITY: a variant must be evaluable on EVERY fitted row. Without
        # this, a variant whose anchor/read point is usually unavailable scores
        # a tiny, trivially-GO subset and fakes "0 errors". (The lastflush
        # anchor does exactly this: non-flush rows have no flush in the window
        # by construction, so the anchor is structurally undefined for them.)
        if s["uneval"]:
            continue
        res.append((s["errs"], -(s["ex"] / max(1, s["ex_n"])), v, s))
    res.sort(key=lambda x: (x[0], x[1]))
    log(f"  ({time.time()-t0:.0f}s)")
    log(f"  eligible (evaluable on all {len(disc)} fitted rows): "
        f"{len(res)}/{len(variants)}")
    una = defaultdict(int)
    for v, s in allres:
        if s["uneval"]:
            una[(v[2], v[5])] += 1
    log(f"  ineligible variants by (anchor, read): {dict(sorted(una.items()))}")
    if not res:
        log("\nNO ELIGIBLE VARIANT: every variant is unevaluable on some row. "
            "The sweep cannot be scored. KILL.")
        return

    log("\n--- TOP 10 on gz-disc (low+mid, non-flush) ranked by GO/PAUSE errors,"
        " then exact-cidle ---")
    log(f"    {'errs':>5} {'exact':>7} {'uneval':>7}  variant")
    for e, nex, v, s in res[:10]:
        log(f"    {e:>5} {-nex*100:>6.1f}% {s['uneval']:>7}  {vname(v)}")

    best_e, _, best_v, best_s = res[0]
    log(f"\n>> FROZEN VARIANT (selected on gz-disc alone): {vname(best_v)}")
    log(f"   disc: errs={best_s['errs']} (GO->PAUSE={best_s['gp']} "
        f"PAUSE->GO={best_s['pg']}) exact-cidle="
        f"{best_s['ex']}/{best_s['ex_n']} uneval={best_s['uneval']}")
    run_v, _, runv, run_s = res[1] if len(res) > 1 else (None, None, None, None)
    if runv:
        log(f"   RUNNER-UP: {vname(runv)}  disc errs={run_s['errs']} "
            f"exact={run_s['ex']}/{run_s['ex_n']}")

    # ---------- FREEZE. Everything below is scored once, no re-selection. ----------
    log("\n=== FROZEN. Scoring gz-held and fresh with NO further tuning. ===")
    final = {}
    for nm, s in (("disc", disc), ("held", held), ("fresh", fresh)):
        sc = score(s, fi, best_v)
        final[nm] = sc
        tot = sc["gg"] + sc["gp"] + sc["pg"] + sc["pp"]
        log(f"\n--- {nm} (low+mid non-flush, n={sc['n']}, scored={tot}, "
            f"uneval={sc['uneval']}) ---")
        log(f"    confusion:            pred GO   pred PAUSE")
        log(f"      chip GO     {sc['gg']:>12} {sc['gp']:>12}")
        log(f"      chip PAUSE  {sc['pg']:>12} {sc['pp']:>12}")
        log(f"    GO/PAUSE errors: {sc['errs']}"
            f"   exact-cidle on pause rows: {sc['ex']}/{sc['ex_n']}"
            f" ({100*sc['ex']/max(1,sc['ex_n']):.1f}%)"
            f"   pause-cidle beyond traj: {sc['nocid']}")
        if sc["err_cells"]:
            log(f"    error cells (occ,age): "
                f"{dict(sorted(sc['err_cells'].items()))}")

    # ---------- the sharpened target ----------
    log("\n=== SHARPENED TARGET: occ3/age1-4, non-flush, per corpus ===")
    for nm, s in (("disc", disc), ("held", held), ("fresh", fresh)):
        tgt = [x for x in s if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 4]
        if not tgt:
            log(f"  {nm}: (no rows)")
            continue
        sc = score(tgt, fi, best_v)
        log(f"  {nm}: n={sc['n']} errs={sc['errs']} "
            f"exact-cidle={sc['ex']}/{sc['ex_n']} uneval={sc['uneval']}")
    log("\n  per-cell detail (ALL corpora pooled), chip vs predicted:")
    for occ, age in ((3, 1), (3, 2), (3, 3), (3, 4)):
        sub = [x for x in nf if x[0][OCC] == occ and x[0][AGE] == age]
        cm = defaultdict(int)
        for rec, tj in sub:
            pl, pc, ok = simulate(tj, fi, best_v)
            cm[(rec["cidle"], pc if ok else "UNEVAL")] += 1
        log(f"    occ{occ}/age{age}: (chip_cidle -> pred_cidle): "
            f"{dict(sorted(cm.items(), key=lambda kv: str(kv[0])))}")

    # ---------- w1/w2/w3 gradient absorption ----------
    log("\n=== w1/w2/w3 GRADIENT (occ3, age1-4, non-flush): chip vs predicted ===")
    for w in ("w1", "w2", "w3"):
        sub = [x for x in nf if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 4
               and x[0]["w"] == w]
        cg = sum(1 for x in sub if x[0]["label"] == "go")
        cp = sum(1 for x in sub if x[0]["label"] == "pause")
        pg = pp = 0
        for rec, tj in sub:
            pl, pc, ok = simulate(tj, fi, best_v)
            if ok and pl == "go":
                pg += 1
            elif ok:
                pp += 1
        log(f"  {w}: chip GO={cg} PAUSE={cp}   pred GO={pg} PAUSE={pp}")

    # ---------- flush rows, reported separately, never fitted ----------
    log("\n=== FLUSH rows (EXCLUDED from the fit; reported as a separate "
        "population) ===")
    sc = score(flush, fi, best_v)
    log(f"  n={sc['n']} errs={sc['errs']} (GO->PAUSE={sc['gp']} "
        f"PAUSE->GO={sc['pg']}) exact-cidle={sc['ex']}/{sc['ex_n']}")
    log("  (a frozen non-flush FSM is not expected to explain these; shown for "
        "completeness only)")

    # ---------- DECISIVE: can ANY eligible variant split 3-vs-4 at all? ----------
    # The frozen variant failing is one thing; the KILL requires that NO variant
    # in the sweep reconstructs the duration split. Scored on the FIT set (disc)
    # only, so this establishes the kill without touching held/fresh.
    log("\n=== KILL CHECK: best exact-cidle ANY eligible variant achieves on the "
        "target cells (occ3/age1-2, non-flush, gz-disc ONLY) ===")
    tgt = [x for x in disc if x[0][OCC] == 3 and 1 <= x[0][AGE] <= 2]
    log(f"  target rows on disc: {len(tgt)} "
        f"(chip cidle {sorted(x[0]['cidle'] for x in tgt)})")
    bx = []
    for e, nex, v, s in res:
        sc = score(tgt, fi, v)
        bx.append((sc["ex"], sc["ex_n"], v))
    bx.sort(key=lambda x: -x[0])
    log(f"  best exact-cidle over all {len(res)} eligible variants:")
    for ex, exn, v in bx[:5]:
        log(f"    {ex}/{exn}  {vname(v)}")
    # and: does ANY variant assign DIFFERENT cidle to chip-3 vs chip-4 rows?
    log("\n  does ANY eligible variant predict a DIFFERENT cidle for chip-3 vs "
        "chip-4 rows in occ3/age1-2 (i.e. split the duration at all)?")
    nsplit = 0
    ex_split = None
    for e, nex, v, s in res:
        p3 = {simulate(tj, fi, v)[1] for rec, tj in tgt if rec["cidle"] == 3}
        p4 = {simulate(tj, fi, v)[1] for rec, tj in tgt if rec["cidle"] == 4}
        if p3 and p4 and not (p3 & p4):
            nsplit += 1
            if ex_split is None:
                ex_split = (v, p3, p4)
    log(f"    variants achieving a clean split: {nsplit}/{len(res)}")
    if ex_split:
        log(f"    e.g. {vname(ex_split[0])}: chip3->{ex_split[1]} "
            f"chip4->{ex_split[2]}")
    else:
        log("    NONE. Every eligible variant maps chip-cidle-3 and chip-cidle-4"
            " rows in occ3/age1-2 onto an OVERLAPPING predicted-cidle set:")
        for ex, exn, v in bx[:3]:
            p3 = sorted(str(simulate(tj, fi, v)[1]) for rec, tj in tgt
                        if rec["cidle"] == 3)
            p4 = sorted(str(simulate(tj, fi, v)[1]) for rec, tj in tgt
                        if rec["cidle"] == 4)
            log(f"      {vname(v)}")
            log(f"        chip3 -> pred {p3}")
            log(f"        chip4 -> pred {p4}")

    json.dump(dict(variant=vname(best_v),
                   variant_raw=list(best_v),
                   runner_up=vname(runv) if runv else None,
                   kill_check=dict(n_eligible=len(res), n_split=nsplit,
                                   best_exact_target=[bx[0][0], bx[0][1]]),
                   final={k: {kk: ({str(a): b for a, b in vv.items()}
                                   if kk == "err_cells" else vv)
                              for kk, vv in v.items()}
                          for k, v in final.items()}),
              OUT.open("w"), indent=1, default=str)
    log(f"\nwrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
