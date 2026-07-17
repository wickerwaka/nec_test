#!/usr/bin/env python3
"""PHASE 1: FLUSH ATTRIBUTION of the chip's pause quanta.

QUESTION: are the occ3/age2 chip-cidle-3 cases (the LATE anchors) flush-driven,
as occ4/age3 -> chip cidle 3 was found to be (5/5 post-flush refetch)?

STAKE: if EVERY non-flush chip pause is cidle 4, the chip's non-flush pause is a
SINGLE QUANTUM everywhere, the model's existing veto machinery already produces
exactly that, and the remaining problem reduces to (i) the decision function and
(ii) flush-window interaction - with no duration machinery at all.

INPUT: sw/class5_flushtraj.jsonl.gz (chip labels joined to pinned-RTL model
state + q_flush over the window [T4_pred, T1_next]).

Usage: python3 sw/class5_phase1.py
"""
import sys, json, gzip
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
DUMP = SW / "class5_flushtraj.jsonl.gz"
LOG = SW / "class5_phase1.log"

OCC = "cnt_occupied"
AGE = "age_occupied_entry_cpu"


def load():
    rows = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    return rows[0], rows[1:]


def main():
    meta, rows = load()
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")

    log("=== PHASE 1: FLUSH ATTRIBUTION ===")
    log(f"rtl={meta.get('rtl')}  rows={len(rows)}")
    log("window = [T4_pred, T1_next] inclusive; flush = any q_flush in window")
    log("chip cidle is corpus ground truth; flush is pinned-RTL model state\n")

    # ---- headline: cidle distribution split by flush, over PAUSE rows ----
    log("--- ALL rows: chip cidle distribution by flush-in-window ---")
    for src in ("gz", "fresh", "ALL"):
        sub = rows if src == "ALL" else [r for r in rows if r["src"] == src]
        for fl in (0, 1):
            d = defaultdict(int)
            for r in sub:
                if r["flush_win"] == fl:
                    d[r["cidle"]] += 1
            tot = sum(d.values())
            log(f"  {src:5s} flush={fl}: n={tot:5d}  cidle "
                f"{dict(sorted(d.items()))}")
    log()

    # ---- THE decisive question ----
    log("--- DECISIVE: chip PAUSE rows (cidle>=3), split by flush ---")
    for src in ("gz", "fresh", "ALL"):
        sub = rows if src == "ALL" else [r for r in rows if r["src"] == src]
        ps = [r for r in sub if r["label"] == "pause"]
        for fl in (0, 1):
            d = defaultdict(int)
            for r in ps:
                if r["flush_win"] == fl:
                    d[r["cidle"]] += 1
            log(f"  {src:5s} flush={fl}: n={sum(d.values()):4d}  cidle "
                f"{dict(sorted(d.items()))}")
    nf3 = [r for r in rows if r["label"] == "pause"
           and r["flush_win"] == 0 and r["cidle"] == 3]
    log(f"\n  >> NON-FLUSH chip pauses with cidle==3: {len(nf3)}")
    if nf3:
        c = defaultdict(int)
        for r in nf3:
            c[(r[OCC], r[AGE])] += 1
        log("     by (occ, occ34_age) cell:")
        for k, v in sorted(c.items()):
            log(f"       occ={k[0]} age={k[1]}: {v}")
        log("     rows:")
        for r in sorted(nf3, key=lambda x: (x["src"], x["seed"], x["w"], x["i"]))[:40]:
            log(f"       {r['src']:5s} fz{r['seed']} {r['w']:5s} i={r['i']:<4} "
                f"occ={r[OCC]} age={r[AGE]} q_cnt={r['cnt_q_cnt']} "
                f"cidle={r['cidle']} pred_tw={r['pred_tw']} "
                f"busfree={r['busfree']} eu_req={r['eu_req']}")
    log()

    # ---- full per-cell cross-tab, low+mid band ----
    log("--- PER-CELL: (occ, occ34_age) x flush -> chip cidle distribution ---")
    log("    (low+mid band = occupied <= 4; 'GO' = cidle<=1, pause = cidle>=3)")
    cells = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for r in rows:
        if r[OCC] > 4:
            continue
        cells[(r[OCC], r[AGE])][r["flush_win"]][r["cidle"]] += 1
    log(f"    {'occ':>3} {'age':>3} {'fl':>2}  {'n':>5}  cidle-distribution")
    for k in sorted(cells):
        for fl in (0, 1):
            d = cells[k][fl]
            if not d:
                continue
            log(f"    {k[0]:>3} {k[1]:>3} {fl:>2}  {sum(d.values()):>5}  "
                f"{dict(sorted(d.items()))}")
    log()

    # ---- the specific anchors of interest ----
    log("--- ANCHOR CELLS of interest ---")
    for occ, age in ((3, 2), (4, 3), (3, 1), (3, 3), (3, 4)):
        sub = [r for r in rows if r[OCC] == occ and r[AGE] == age]
        for fl in (0, 1):
            d = defaultdict(int)
            for r in sub:
                if r["flush_win"] == fl:
                    d[r["cidle"]] += 1
            if d:
                log(f"  occ{occ}/age{age} flush={fl}: n={sum(d.values()):4d} "
                    f"cidle {dict(sorted(d.items()))}")
    log()

    # ---- pause rows: is cidle 4 the single non-flush quantum? ----
    log("--- NON-FLUSH pause quantum check ---")
    nf = [r for r in rows if r["label"] == "pause" and r["flush_win"] == 0]
    d = defaultdict(int)
    for r in nf:
        d[r["cidle"]] += 1
    log(f"  non-flush pause cidle histogram: {dict(sorted(d.items()))}  n={len(nf)}")
    fw = [r for r in rows if r["label"] == "pause" and r["flush_win"] == 1]
    d2 = defaultdict(int)
    for r in fw:
        d2[r["cidle"]] += 1
    log(f"  FLUSH     pause cidle histogram: {dict(sorted(d2.items()))}  n={len(fw)}")

    # ---- amb (cidle 2) rows ----
    log("\n--- AMB (cidle==2) rows: cell + flush ---")
    amb = [r for r in rows if r["label"] == "amb"]
    c = defaultdict(int)
    for r in amb:
        c[(r[OCC], r[AGE], r["flush_win"])] += 1
    log(f"  n={len(amb)}  by (occ, age, flush):")
    for k, v in sorted(c.items()):
        log(f"    occ={k[0]} age={k[1]} flush={k[2]}: {v}")

    logf.close()


if __name__ == "__main__":
    main()
