#!/usr/bin/env python3
"""Class-5 FLUSH ATTRIBUTION + queue-TRAJECTORY regeneration (board-free).

WHY: the two bandage corpora carry the CHIP ground truth (cidle per aligned
CODE->CODE prefetch-resume opportunity) but NO flush field, so nobody knows
whether the chip's cidle-3 pauses are post-flush refetches or genuine
non-flush pause quanta. They also carry no per-cycle queue trajectory, so the
"latched refill verdict" hypothesis (H-LV v2) has never been testable offline.

WHAT: this script does NOT re-measure the chip. The chip labels already exist,
keyed by (seed, w, i), and are immutable. It re-derives the MODEL-side fields
at PINNED RTL (HEAD 1f6004c, DUT untouched) with the Verilator TB only, and
JOINS them onto the existing chip labels. That makes it board-free AND fixes
the fresh corpus's "uncertain provenance" model fields, which were generated
from a modified working tree - here every model field for BOTH corpora comes
from the same pinned DUT.

The opportunity SET is taken from the corpora themselves (each corpus row is
an opportunity that lay inside the chip-vs-model aligned prefix). The aligned
prefix cannot be recomputed board-free - there is no chip trace here - so the
corpus row set defines it. This is a pure join, never a re-selection.

NEW FIELDS PER OPPORTUNITY:
    flush_win / flush_clk  q_flush anywhere in the window [T4_pred, T1_next]
    pred_tw                the predecessor fetch's own Tw (wait states)
    t4_clk / t1_clk        absolute CPU clocks of T4_pred and T1_next
    traj                   per-cycle trajectory over [T4_pred - 8, T1_next],
                           TRAJ_FIELDS order, encoded as tuples (compact)

Model fields are recomputed with class5_bandage.py's own definitions (same
cc()/ages_at()/band() semantics) so occ / occ34_age mean exactly what they
mean in the fitted predicates. A cross-check against each corpus's stored
model fields is reported (agreement = provenance proof).

Usage:
    python3 sw/class5_flushtraj.py                    # both corpora
    python3 sw/class5_flushtraj.py --corpus gz        # just the committed one
Output: sw/class5_flushtraj.jsonl.gz (+ .log)
"""
import sys, os, json, gzip, time, argparse, traceback
import random as _r
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import generate, compose, run_tb_internal, accesses, bs_stream, CODE
from class5_bandage import COUNTS, cc, band, ages_at, bus_free, AGES

GZ = SW / "class5_bandage.jsonl.gz"
FRESH = SW / "class5_bandage.jsonl"
OUT = SW / "class5_flushtraj2.jsonl.gz"
LOG = SW / "class5_flushtraj2.log"

PRE = 16         # trajectory lead-in clocks before T4_pred (EU
                 # demand-onset search needs more lead-in than the
                 # BIU-only sweep did)

# per-cycle trajectory fields (order is the wire format; keep in sync w/ readers)
TRAJ_FIELDS = ["clk", "t", "q_cnt", "q_avl", "cnt_next", "occupied", "pop_now",
               "push_now", "q_aged", "eu_req", "eu_ready", "eu_hold", "busfree",
               "q_flush", "eval_ext", "prefetch_ok", "grid_phase", "pf_lim",
               "eu_consuming",
               # EU-SIDE SCHEDULE. pop_want is the EU's byte DEMAND, derived
               # from EU microcode state alone; q_pop = pop_want && q_avail, so
               # the bus only ever shows demand AND availability. Measured on
               # fz90000/w1: 635 demand cycles, 299 visible pops, 336 STARVED
               # (demand with an empty queue) - i.e. >half the EU demand
               # schedule is structurally invisible to the BIU. This is the
               # candidate hidden variable behind the tw1-3 residual.
               "eu_state", "pop_want", "q_avail", "eu_dly", "eu_rsv_lead"]


def wait_vectors():
    """MUST reproduce class5_bandage.py:gather() exactly or the (seed,w) keys
    do not name the same opportunities."""
    wd = {"w1": [1] * 4096, "w2": [2] * 4096, "w3": [3] * 4096}
    for (ws, wm) in [(4, 3), (7, 7)]:
        rr = _r.Random((ws << 8) | wm)
        wd[f"r{ws}.{wm}"] = [rr.randint(0, wm) for _ in range(4096)]
    return wd


def model_index(rows):
    kt1, kt4, bi = {}, {}, -1
    for ri, x in enumerate(rows):
        if x["t"] == 1:
            bi += 1
            kt1[bi] = ri
        if x["t"] == 5:
            kt4[bi] = ri
    return kt1, kt4


def model_accesses(rows):
    return accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                          ad_addr=x["addr"], ad_data=0) for x in rows])


def traj_row(r):
    return [r["clk"], r["t"], r["q_cnt"], r["q_avl"], r["cnt_next"],
            r["occupied"], r["pop_now"], r["push_now"], r["q_aged"],
            r["eu_req"], r["eu_ready"], r["eu_hold"], int(r["t"] == 0),
            r["q_flush"], r["eval_ext"], r["prefetch_ok"], r["grid_phase"],
            r["pf_lim"], r["eu_consuming"],
            r["state"], r["pop_want"], r["q_avail"], r["eu_dly"],
            r["eu_rsv_lead"]]


def regen_pair(seed, wname, wv, corpus_rows, out, log):
    """One TB run at pinned RTL covering every corpus opportunity of (seed,w)."""
    g = generate(f"fz{seed}", exts=())
    image, meta = compose(g)
    rows = run_tb_internal(image, 4200, wv)
    kt1, kt4 = model_index(rows)
    ka = model_accesses(rows)
    kb = bs_stream(ka)
    comp_rows = {a["t4"] for a in ka if a["bs"] == CODE and a["t4"] is not None}
    nmatch = nmiss = 0
    agree = defaultdict(lambda: [0, 0])     # field -> [agree, total]
    for a in corpus_rows:
        i = a["i"]
        if (i - 1) not in kt4 or i not in kt1 or i >= len(ka):
            nmiss += 1
            continue
        t4p, t1n = kt4[i - 1], kt1[i]
        de = t4p + 1 if (t4p + 1) < len(rows) else t4p
        e = rows[de]
        # window [T4_pred, T1_next] inclusive
        win = range(t4p, min(t1n + 1, len(rows)))
        fl = [r for r in win if rows[r]["q_flush"]]
        rec = dict(seed=seed, w=wname, tag=a["tag"], i=i,
                   cidle=a["cidle"], label=a["label"], src=a["src"],
                   flush_win=int(bool(fl)),
                   flush_clk=(rows[fl[0]]["clk"] if fl else None),
                   pred_tw=ka[i - 1]["tw"], succ_tw=ka[i]["tw"],
                   t4_clk=rows[t4p]["clk"], t1_clk=rows[t1n]["clk"],
                   t4_row=t4p, t1_row=t1n,
                   model_cidle=sum(1 for r in range(t4p + 1, t1n)
                                   if rows[r]["t"] == 0),
                   eu_req=e["eu_req"], eu_consuming=e["eu_consuming"],
                   t=e["t"], busfree=int(bus_free(e)))
        # model counts + ages, recomputed with class5_bandage.py's own semantics
        for defn in COUNTS:
            v = cc(defn, e)
            rec["cnt_" + defn] = v
            for an, av in ages_at(defn, rows, de, comp_rows).items():
                rec[f"age_{defn}_{an}"] = av
        # provenance cross-check vs the corpus's stored model fields
        for k in ("cnt_occupied", "cnt_q_cnt", "age_occupied_entry_cpu",
                  "busfree", "eu_req"):
            if k in a:
                agree[k][1] += 1
                agree[k][0] += int(a[k] == rec[k])
        # trajectory over [T4_pred - PRE, T1_next]
        lo = max(0, t4p - PRE)
        rec["traj0"] = lo - t4p          # trajectory start, relative to T4_pred
        rec["traj"] = [traj_row(rows[r]) for r in range(lo, min(t1n + 1, len(rows)))]
        out.append(rec)
        nmatch += 1
    ag = " ".join(f"{k}={v[0]}/{v[1]}" for k, v in sorted(agree.items()))
    log(f"  fz{seed} {wname}: {nmatch} joined, {nmiss} unjoinable | agree {ag}")
    return nmatch, nmiss, agree


def load_corpus(path, src):
    op = gzip.open if path.suffix == ".gz" else open
    rows = []
    with op(path, "rt") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            r["src"] = src
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["gz", "fresh", "both"], default="both")
    a = ap.parse_args()

    logf = LOG.open("w")

    def log(s):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    log(f"start {time.ctime()}  pinned RTL: HEAD 1f6004c (DUT untouched; TB "
        f"d[49]=eu_hold d[50]=cpu_clk appended, observability only)")
    corp = []
    if a.corpus in ("gz", "both"):
        corp += load_corpus(GZ, "gz")
    if a.corpus in ("fresh", "both"):
        corp += load_corpus(FRESH, "fresh")
    log(f"corpus rows: {len(corp)}")

    by = defaultdict(list)
    for r in corp:
        by[(r["src"], r["seed"], r["w"])].append(r)
    log(f"(src,seed,w) pairs -> TB runs: {len(by)}")

    wvs = wait_vectors()
    out = []
    tot_m = tot_x = 0
    ag_all = defaultdict(lambda: [0, 0])
    for n, ((src, seed, wname), rws) in enumerate(sorted(by.items())):
        t0 = time.time()
        try:
            m, x, ag = regen_pair(seed, wname, wvs[wname], rws, out, log)
            tot_m += m
            tot_x += x
            for k, v in ag.items():
                ag_all[k][0] += v[0]
                ag_all[k][1] += v[1]
        except Exception as ex:
            log(f"  fz{seed} {wname}: ERR {ex}")
            traceback.print_exc()
        if (n + 1) % 10 == 0:
            log(f"  [{n+1}/{len(by)}] {time.time()-t0:.1f}s/pair "
                f"rows={len(out)}")

    log(f"\njoined {tot_m}, unjoinable {tot_x}")
    log("PROVENANCE cross-check (regenerated model field == corpus's stored one):")
    for k, v in sorted(ag_all.items()):
        log(f"  {k:28s} {v[0]}/{v[1]} = {100*v[0]/max(1,v[1]):.2f}%")
    # split by corpus so the fresh corpus's provenance is judged on its own
    for src in ("gz", "fresh"):
        sub = [r for r in corp if r["src"] == src]
        if not sub:
            continue
        log(f"  ({src}: {len(sub)} corpus rows)")

    with gzip.open(OUT, "wt") as f:
        f.write(json.dumps(dict(_meta=True, traj_fields=TRAJ_FIELDS, pre=PRE,
                                rtl="HEAD 1f6004c")) + "\n")
        for r in out:
            f.write(json.dumps(r) + "\n")
    log(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")
    log(f"done {time.ctime()}")
    logf.close()


if __name__ == "__main__":
    main()
