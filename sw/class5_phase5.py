#!/usr/bin/env python3
"""PHASE 5: the MODEL-EU FORECAST test (board-free).

HYPOTHESIS (promoted from the Fit-C caveat): the tw1-3 residual is not absence
of mechanism - it is information the BIU-side dump cannot carry. If the resume
deadline is set by EU microcode timing, no projection of BIU/queue fields can
reconstruct it, and every BIU-only fit must sit at the majority-class baseline.
That is exactly what Fit C found (tw1-3 best 59/85 vs always-4 58/85 = ONE row).

WHY THIS IS TESTABLE WITHOUT THE BOARD OR THE MICROCODE DOCS: our own EU model
is a validated cycle-exact proxy for EU timing (w0 goldens 169000/169000). So
the EU's demand schedule can be read directly out of the model.

THE STRUCTURAL POINT (measured, fz90000/w1): q_pop = pop_want && q_avail, and
pop_want is a function of EU microcode state ALONE. 635 EU demand cycles ->
299 visible pops, 336 STARVED (demand against an empty queue). More than HALF
the EU demand schedule is structurally invisible to the BIU. The bus can never
show demand-without-availability; the EU model can.

THE DECISIVE TEST (this file):
  1. UNFITTED: is T1_next - (EU demand event) TIGHT on the tw1-3 rows? A sharp
     mode is the signature; it is measured before any fitting.
  2. FITTED: re-run Fit C with EU-side demand definitions added, and score
     against the ALWAYS-4 BASELINE (58/85 = 68.2%). The permanent guard: a
     result only counts if it beats the trivial baseline BY A REAL MARGIN.
     Fit C's BIU-only best beat it by one row.

PROTOCOL: unchanged. The pre-registered one-time re-split stands (fit=fresh,
hold=gz); no re-splitting. fit -> FREEZE -> score held ONCE.

Usage: python3 sw/class5_phase5.py
"""
import sys, json, gzip, itertools, time
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

DUMP = SW / "class5_flushtraj2.jsonl.gz"
LOG = SW / "class5_phase5.log"
OUT = SW / "class5_phase5.json"
OCC, AGE = "cnt_occupied", "age_occupied_entry_cpu"


class Traj:
    __slots__ = ("row", "lo", "hi", "t4", "t1n", "pred_tw")

    def __init__(self, rec, fi):
        tr = rec["traj"]
        ci = fi["clk"]
        self.lo = tr[0][ci]
        self.hi = tr[-1][ci]
        self.row = {t[ci]: t for t in tr}
        self.t4 = rec["t4_clk"]
        self.t1n = rec["t1_clk"]
        self.pred_tw = rec["pred_tw"]


def load():
    L = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    meta, recs = L[0], L[1:]
    fi = {n: i for i, n in enumerate(meta["traj_fields"])}
    return meta, fi, [(r, Traj(r, fi)) for r in recs]


def onsets(tj, fi, field, lo=None, hi=None):
    """Rising edges of a 0/1 trajectory field (an EVENT, not a level)."""
    lo = tj.lo if lo is None else lo
    hi = tj.hi if hi is None else hi
    out = []
    for k in range(lo, hi + 1):
        t = tj.row.get(k)
        if t is None:
            continue
        p = tj.row.get(k - 1)
        cur = t[fi[field]] > 0
        prev = (p[fi[field]] > 0) if p is not None else False
        if cur and not prev:
            out.append(k)
    return out


def starve_onsets(tj, fi, lo=None, hi=None):
    """Rising edges of (pop_want && !q_avail) = EU STARVATION - the EU wants a
    byte and the queue cannot supply it. Invisible to the bus by construction."""
    lo = tj.lo if lo is None else lo
    hi = tj.hi if hi is None else hi
    pw, qa = fi["pop_want"], fi["q_avail"]

    def st(k):
        t = tj.row.get(k)
        return t is not None and t[pw] > 0 and t[qa] == 0
    return [k for k in range(lo, hi + 1) if st(k) and not st(k - 1)]


def main():
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    meta, fi, allrows = load()
    nf = [x for x in allrows if x[0]["flush_win"] == 0
          and x[0]["label"] in ("go", "pause")]
    band = [x for x in nf if x[0][OCC] <= 4]
    P = [x for x in band if x[0]["label"] == "pause"]
    FIT = [x for x in P if x[0]["src"] == "fresh"]
    HOLD = [x for x in P if x[0]["src"] != "fresh"]

    def tw13(r):
        return [x for x in r if 1 <= x[0]["pred_tw"] <= 3]

    def twhi(r):
        return [x for x in r if x[0]["pred_tw"] >= 4]

    log("=== PHASE 5: MODEL-EU FORECAST TEST ===")
    log(f"rtl={meta.get('rtl')}  non-flush low+mid pause rows: {len(P)} "
        f"(FIT/fresh {len(FIT)}, HOLD/gz {len(HOLD)})")
    log(f"tw1-3 (the residual): FIT {len(tw13(FIT))} HOLD {len(tw13(HOLD))}")

    # ---- 0. the invisibility measurement, over the whole corpus ----
    log("\n--- 0. HOW MUCH EU DEMAND IS INVISIBLE TO THE BIU? ---")
    dw = dp = ds = 0
    for rec, tj in band:
        for k in range(tj.lo, tj.hi + 1):
            t = tj.row.get(k)
            if t is None:
                continue
            if t[fi["pop_want"]] > 0:
                dw += 1
                if t[fi["q_avail"]] > 0:
                    dp += 1
                else:
                    ds += 1
    log(f"    over all recorded trajectory clocks: EU demand cycles={dw}, "
        f"visible pops={dp}, STARVED (invisible)={ds}")
    log(f"    => {100*ds/max(1,dw):.1f}% of EU demand is not observable from "
        f"the bus.")

    # ---- 1. UNFITTED: is T1 - EU demand event tight? ----
    log("\n--- 1. UNFITTED: T1_next - (EU demand event), tw1-3 pause rows ---")
    log("    No fitting. If an EU-clock variable sets the deadline, the offset")
    log("    should show a SHARP MODE. Compared against the same statistic")
    log("    measured from BIU-visible pops (the pop shadow).")
    for nm, rows in (("FIT(fresh)", tw13(FIT)), ("HOLD(gz)", tw13(HOLD)),
                     ("POOLED", tw13(FIT) + tw13(HOLD))):
        for label, fn in (("last pop_want onset <= T4+1",
                           lambda tj: [k for k in onsets(tj, fi, "pop_want")
                                       if k <= tj.t4 + 1]),
                          ("last STARVE onset <= T4+1",
                           lambda tj: [k for k in starve_onsets(tj, fi)
                                       if k <= tj.t4 + 1]),
                          ("last VISIBLE pop <= T4+1 (bus shadow)",
                           lambda tj: [k for k in range(tj.lo, tj.t4 + 2)
                                       if (tj.row.get(k) or [0]*30)[fi["pop_now"]] > 0])):
            d = defaultdict(int)
            miss = 0
            for rec, tj in rows:
                c = fn(tj)
                if not c:
                    miss += 1
                    continue
                d[rec["t1_clk"] - c[-1]] += 1
            tot = sum(d.values())
            if not tot:
                continue
            top = sorted(d.items(), key=lambda kv: -kv[1])[:1][0]
            log(f"    {nm:11s} {label:38s}: n={tot:3d} miss={miss:2d}  "
                f"mode={top[0]} ({top[1]}/{tot}={100*top[1]/tot:.0f}%)  "
                f"dist={dict(sorted(d.items()))}")

    # ---- 2. FITTED: EU-side demand definitions ----
    log("\n--- 2. FITTED: Fit C re-run with EU-SIDE demand definitions ---")
    b4 = sum(1 for x in tw13(FIT) if x[0]["cidle"] == 4)
    b3 = sum(1 for x in tw13(FIT) if x[0]["cidle"] == 3)
    n13 = len(tw13(FIT))
    log(f"    PERMANENT GUARD - trivial baselines on FIT tw1-3 (n={n13}): "
        f"always-4 = {b4}/{n13} ({100*b4/n13:.1f}%), always-3 = {b3}/{n13}")
    log("    A result counts only if it beats always-4 BY A REAL MARGIN.")
    log("    (Fit C's BIU-only best: 59/85 = one row over baseline.)")

    EUD = {
        "pop_want": ("pop_want", None),
        "starve": ("STARVE", None),
        "eu_rsv_lead": ("eu_rsv_lead", None),
    }

    def d0_eu(tj, kind, cap):
        if kind == "pop_want":
            c = [k for k in onsets(tj, fi, "pop_want") if k <= cap]
        elif kind == "STARVE":
            c = [k for k in starve_onsets(tj, fi) if k <= cap]
        elif kind == "eu_rsv_lead":
            c = [k for k in onsets(tj, fi, "eu_rsv_lead") if k <= cap]
        elif kind == "pop_now":
            c = [k for k in onsets(tj, fi, "pop_now") if k <= cap]
        else:
            raise KeyError(kind)
        return c[-1] if c else None

    KINDS = ["pop_want", "STARVE", "eu_rsv_lead", "pop_now"]
    CAPS = [0, 1, 2]          # cap = T4 + cap
    SS = list(range(0, 8))
    FLOORS = [2, 3, 4]

    def predict(tj, kind, cap, S, floor):
        D0 = d0_eu(tj, kind, tj.t4 + cap)
        if D0 is None:
            return floor
        return max(floor, D0 + S - tj.t4 - 1)

    def ex(rows, v):
        return sum(1 for rec, tj in rows
                   if predict(tj, *v) == rec["cidle"])

    variants = list(itertools.product(KINDS, CAPS, SS, FLOORS))
    t13 = tw13(FIT)
    res = sorted(variants, key=lambda v: (-ex(t13, v), -ex(FIT, v)))
    log(f"\n    {len(variants)} EU-side variants. TOP 8 by FIT tw1-3 exact:")
    log(f"      {'tw1-3':>8} {'all tw':>8}  variant")
    for v in res[:8]:
        log(f"      {str(ex(t13,v))+'/'+str(len(t13)):>8} "
            f"{str(ex(FIT,v))+'/'+str(len(FIT)):>8}  "
            f"D0={v[0]} cap=T4+{v[1]} S=L+K={v[2]} floor={v[3]}")
    best = res[0]
    log(f"\n>> FROZEN (fit on FRESH alone): D0={best[0]} cap=T4+{best[1]} "
        f"S=L+K={best[2]} floor={best[3]}")
    log(f"   FIT tw1-3 {ex(t13,best)}/{len(t13)} "
        f"({100*ex(t13,best)/len(t13):.1f}%)  vs baseline {b4}/{n13} "
        f"({100*b4/n13:.1f}%)  MARGIN = {ex(t13,best)-b4} rows")
    run = res[1]
    log(f"   RUNNER-UP: D0={run[0]} cap=T4+{run[1]} S=L+K={run[2]} "
        f"floor={run[3]}  (tw1-3 {ex(t13,run)}/{len(t13)})")

    # ---- FREEZE ----
    log("\n=== FROZEN. HOLD (gz) scored ONCE. ===")
    fin = {}
    for nm, rows in (("FIT(fresh)", FIT), ("HOLD(gz)", HOLD)):
        t = tw13(rows)
        hb4 = sum(1 for x in t if x[0]["cidle"] == 4)
        log(f"\n  {nm}: pause n={len(rows)}")
        log(f"    all-tw exact: {ex(rows,best)}/{len(rows)} "
            f"({100*ex(rows,best)/max(1,len(rows)):.1f}%)")
        log(f"    tw1-3 exact : {ex(t,best)}/{len(t)} "
            f"({100*ex(t,best)/max(1,len(t)):.1f}%)   "
            f"always-4 baseline {hb4}/{len(t)} ({100*hb4/max(1,len(t)):.1f}%)   "
            f"MARGIN {ex(t,best)-hb4}")
        h = twhi(rows)
        log(f"    tw>=4 exact : {ex(h,best)}/{len(h)}")
        fin[nm] = dict(all=[ex(rows, best), len(rows)],
                       tw13=[ex(t, best), len(t)], base4=hb4,
                       twhi=[ex(h, best), len(h)])

    # ---- per-tw ----
    log("\n=== PER-tw (chip-PAUSE rows), frozen EU rule ===")
    for nm, rows in (("FIT(fresh)", FIT), ("HOLD(gz)", HOLD)):
        log(f"\n    {nm}:")
        log(f"      {'tw':>3} {'n':>4} {'exact':>8}  {'chip 3:4':>9}  {'pred 3:4':>9}")
        for tw in sorted({x[0]["pred_tw"] for x in rows}):
            sub = [x for x in rows if x[0]["pred_tw"] == tw]
            c3 = sum(1 for x in sub if x[0]["cidle"] == 3)
            c4 = sum(1 for x in sub if x[0]["cidle"] == 4)
            p3 = sum(1 for rec, tj in sub if predict(tj, *best) == 3)
            p4 = sum(1 for rec, tj in sub if predict(tj, *best) == 4)
            log(f"      {tw:>3} {len(sub):>4} "
                f"{str(ex(sub,best))+'/'+str(len(sub)):>8}  "
                f"{str(c3)+':'+str(c4):>9}  {str(p3)+':'+str(p4):>9}")

    # ---- L+K ridge under EU fields ----
    log("\n=== L+K RIDGE under EU-side fields ===")
    kind, cap, S, floor = best
    for s in SS:
        log(f"    S=L+K={s}: FIT tw1-3 {ex(t13,(kind,cap,s,floor))}/{len(t13)}")
    log("    (corpus still has no tw=0/cidle-4 row, so L,K remain a factorial")
    log("     job - not fitted around here.)")

    json.dump(dict(frozen=dict(D0=best[0], cap=best[1], S=best[2],
                               floor=best[3]),
                   baseline_tw13_always4=b4, n_tw13=n13, final=fin),
              OUT.open("w"), indent=1, default=str)
    log(f"\nwrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
