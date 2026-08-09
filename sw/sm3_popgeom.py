#!/usr/bin/env python3
"""sm3_popgeom -- the CHIP-SIDE control for H1: after a queue FLUSH, how long
after the refilling fetch's T1 does the first opcode POP (`qs = F`) happen?

A MEASUREMENT tool, never a gate.  Reads banked `chip_rows` only -- no engine
is run, so this is silicon's own answer.

A flush shows on the pins as `qs = E`.  The first `qs = F` after it is the
first opcode byte popped out of the refilled queue, and the CODE cycle that
supplied it is the last CODE T1 at or before that pop.  Reported as
(fetch length, pop - fetch_T1), which is the would-pop clock B that M14's
`entry = B + 2` is anchored on.

Usage: sm3_popgeom.py [--bank ...] [--jobs N] [--evt-only] [--report out.json]
"""
import argparse
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                              # noqa: E402
import ucsim_fuzz as uf                                 # noqa: E402
import sm3_ackgeom as ag                                # noqa: E402

BANK = ROOT / "tests" / "v30" / "fuzz_bank"
# ⚠ THE v1 CORPUS, AND ALL OF IT IS `status: SUPERSEDED` SINCE 2026-08-09
# (SUP-1, docs/notes/invalidation_ledger.md; the predicate is
# `sw/bank_status.py`).  MEASUREMENT TOOL, NOT A GATE: it names these
# banks explicitly and reads them deliberately -- they are its subject.
# Nothing was moved or deleted, so every path below still resolves.
BANKS = ["mc1", "mc2", "t30-raw", "t30-brkem"]
CODE, INTA = 4, 0


def one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    cy = ag.cycles(recs, win)
    # cycle lookup by row
    t1_of = {c[1]: c for c in cy}
    out = []
    for i in range(win):
        if recs[i]["qs"] != 2:               # E -- the flush strobe
            continue
        # the first pop after it
        j = i + 1
        while j < win and recs[j]["qs"] != 1:
            if recs[j]["qs"] == 3:           # S -- a subsequent byte first
                j = -1
                break
            j += 1
        if j < 0 or j >= win:
            continue
        # the REFILL: the first CODE cycle whose T1 opens after the flush.  The
        # byte that pop `j` takes is the one THAT cycle brings in -- a later
        # fetch cannot have supplied it, and there is no earlier one because the
        # flush emptied the queue.
        sup = None
        for c in cy:
            if c[0] == CODE and c[1] > i:
                sup = c
                break
        if sup is None or sup[1] > j:
            continue
        out.append({"flush": i, "pop": j, "fetch_t1": sup[1],
                    "fetch_end": sup[2], "len": sup[2] - sup[1] + 1,
                    "d": j - sup[1], "de": sup[1] - i})
    w = entry.get("waits") or {}
    wc = f"wrand{w.get('wmax')}" if w.get("wrand") else f"fix{w.get('fixed') or 0}"
    return {"path": str(path), "wc": wc, "evt": bool(entry.get("evt")),
            "pops": out}


def seeds_of(banks):
    out = []
    for b in banks:
        d = BANK / b / "seeds"
        if d.is_dir():
            out += sorted(str(p) for p in d.glob("*.json.gz"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(BANKS))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    paths = seeds_of([b for b in a.bank.split(",") if b])
    if a.limit:
        paths = paths[:a.limit]
    with Pool(a.jobs) as pool:
        res = pool.map(one, paths, chunksize=8)
    n = sum(len(r["pops"]) for r in res)
    print(f"== sm3_popgeom -- {len(res)} seeds, {n} flush->pop events")
    by = defaultdict(Counter)
    for r in res:
        for p in r["pops"]:
            by[p["len"]][p["d"]] += 1
    for L in sorted(by):
        tot = sum(by[L].values())
        print(f"  fetch len {L:>2}  n={tot:<6} pop-fetchT1: "
              + "  ".join(f"{d}:{c}" for d, c in sorted(by[L].items())))
    if a.report:
        Path(a.report).write_text(json.dumps(res))
        print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
