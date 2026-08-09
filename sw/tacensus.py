#!/usr/bin/env python3
"""tacensus -- the POST-WRITE TURNAROUND census (ucsim_t_provenance.md 17.4).

17.4 named a residual and a shape: 93 flush events whose `E` the model misses,
77 of them with the chip's `E` at `x+2`, the model's at `x+0`, and the last
completed cycle a ZERO-WAIT MEMW ending at `x-1`.  It read that as a post-write
bus turnaround.

This instrument exists to score that reading against its own CONTROL: how many
events carry the same signature and are ALREADY exact.  It extends `q2law`'s
per-event record with (a) the full `V30SIM_FLUSHTRACE` FX state at the flush
clock -- outstanding EU request, committed-but-not-started cycle, queue
occupancy, the pre-flush `no_eval_` and absorb window -- and (b) the NEXT bus
cycle on each side (chip and model), so the `E` and the commit can be scored
separately.

Chip and model go through the SAME extractor (`q2census.cycles_of`), exactly
as repcensus / q2census / q2law do; nothing is re-derived locally.

It also carries the census that SETTLED it, and that one reads the CHIP ALONE
(`--chains`): every trap push chain in the bank -- three back-to-back MEMW
cycles whose addresses step down by 2, followed by a CODE fetch -- with the
store-2-to-store-3 T1 gap and the emulation-mode status bit PS3 (M9) on each
store's data phase.  No model, no micro-row trace, so it is valid on every seed
including the ones whose model run diverges earlier.

Usage:
  tacensus.py [--jobs N] [--report out.json]
  tacensus.py --chains [--jobs N]
"""

import argparse
import gzip
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc             # noqa: E402
import ucsim_fuzz as uf                # noqa: E402
import timed_fuzz as tf                # noqa: E402
import q2census as qc                  # noqa: E402

BUS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
       6: "MEMW", 7: "PASV"}


def parse_fx(err):
    """FLUSHTRACE -> the LAST case's FX records, keyed by clock."""
    out = {}
    for l in err.splitlines():
        p = l.split()
        if not p or p[0] != "FX":
            continue
        d = {"x": int(p[1])}
        for kv in p[2:]:
            k, _, v = kv.partition("=")
            d[k] = v
        out[d["x"]] = d
    return out


def side(rows, x):
    """The row stream's answers around the flush clock x."""
    cyc = qc.cycles_of(rows)
    n = len(rows)
    e = next((i for i in range(max(0, x), n) if rows[i][2] == 2), None)
    nxt = next((c for c in cyc if c["t1"] >= x + 1), None)
    run = next((c for c in cyc if c["t1"] <= x and
                (c["t4"] is None or c["t4"] >= x)), None)
    prev = None
    for c in cyc:
        if c["t4"] is not None and c["t4"] <= x:
            prev = c
    # the first CODE cycle at or after the flush -- the redirect
    red = next((c for c in cyc if c["bs"] == 4 and c["t1"] >= x + 1), None)
    return {"e": e,
            "nxt_t1": nxt["t1"] if nxt else None,
            "nxt_bs": nxt["bs"] if nxt else None,
            "nxt_tw": nxt["tw"] if nxt else None,
            "red_t1": red["t1"] if red else None,
            "run_bs": run["bs"] if run else None,
            "run_ci": (x - run["t1"]) if run else None,
            "run_tw": run["tw"] if run else None,
            "prev_t1": prev["t1"] if prev else None,
            "prev_t4": prev["t4"] if prev else None,
            "prev_tw": prev["tw"] if prev else None,
            "prev_bs": prev["bs"] if prev else None}


def one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception:                                        # noqa: BLE001
        return []
    if sha != entry["image_sha256"]:
        return []
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    if tf.excuse(entry, recs, win):
        return []
    os.environ["V30SIM_FLUSHTRACE"] = "1"
    with tempfile.TemporaryDirectory() as td:
        rows, err = tf.run_sim(image, entry, len(recs), td)
    if not rows:
        return []
    dr = fc.diff_rows(recs, rows)
    first = dr.rows[0].i if dr.rows else len(recs)
    fx = parse_fx(err)
    if not fx:
        return []
    grows = qc.rows_from_recs(recs)
    mrows = qc.rows_from_recs(rows)
    ev = []
    for x in sorted(fx):
        if x >= len(grows) or x >= len(mrows):
            continue
        ev.append({"src": f"{entry.get('cid')}/{entry.get('k')}",
                   "path": str(path), "x": x, "pre": x <= first,
                   "first": first,
                   "g": side(grows, x), "m": side(mrows, x),
                   "fx": fx[x]})
    return ev


def chains(path):
    """CHIP-ONLY: the trap push chains of one seed."""
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    if tf.excuse(entry, recs, win):
        return []
    cyc = qc.cycles_of(qc.rows_from_recs(recs))
    for c in cyc:                       # cycles_of keeps no address
        c["ad"] = recs[c["t1"]].get("ad_addr")
    out = []
    for k in range(len(cyc) - 3):
        a, b, c, d = cyc[k:k + 4]
        if not (a["bs"] == 6 and b["bs"] == 6 and c["bs"] == 6 and d["bs"] == 4):
            continue
        if None in (a["ad"], b["ad"], c["ad"]):
            continue
        if not (a["ad"] - b["ad"] == 2 and b["ad"] - c["ad"] == 2):
            continue
        # M9: PS3 is the emulation-mode bit, read on each store's DATA phase.
        md = [((recs[x["t1"] + 1].get("ps") or 0) >> 3) & 1 for x in (a, b, c)]
        out.append({"src": f"{entry.get('cid')}/{entry.get('k')}",
                    "tw": [a["tw"], b["tw"], c["tw"]],
                    "g2": c["t1"] - b["t1"], "md": md})
    return out


def score_chains(rows):
    print(f"trap push chains (chip rows only): {len(rows)}")
    tab = defaultdict(Counter)
    for r in rows:
        tab[(tuple(r["md"]), r["tw"][1])][r["g2"]] += 1
    print("  (MD at push 1/2/3, store-2 wait count) -> store-2 -> store-3 T1 gap")
    for k in sorted(tab, key=str):
        print(f"    MD={k[0]} tw={k[1]:<2} " +
              "  ".join(f"{g}:{n}" for g, n in sorted(tab[k].items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--report", default="")
    ap.add_argument("--seeds", default="")
    ap.add_argument("--chains", action="store_true")
    args = ap.parse_args()
    paths = ([l.split()[0] for l in open(args.seeds)]
             # MEASUREMENT TOOL, NOT A GATE, AND ITS SUBJECT IS THE v1 CORPUS:
             # `include_superseded=True` is passed DELIBERATELY so SUP-1's
             # retirement (docs/notes/invalidation_ledger.md) does not make this
             # instrument silently vacuous.  It replays nothing on any gate run.
             if args.seeds else tf.seeds_of(tf.BANKS,
                                            include_superseded=True))
    if args.chains:
        with Pool(args.jobs) as pool:
            rows = [r for rr in pool.map(chains, paths, chunksize=2)
                    for r in rr]
        score_chains(rows)
        return 0
    with Pool(args.jobs) as pool:
        ev = [e for r in pool.map(one, paths, chunksize=2) for e in r]
    ev = [e for e in ev if e["pre"] and e["g"]["e"] is not None]
    print(f"flush events (pre-divergence, chip E present): {len(ev)}")
    miss = [e for e in ev if e["m"]["e"] != e["g"]["e"]]
    print(f"model E wrong: {len(miss)}")
    print("  chip E - x / model E - x: " + "  ".join(
        f"{k}={v}" for k, v in Counter(
            (e["g"]["e"] - e["x"],
             None if e["m"]["e"] is None else e["m"]["e"] - e["x"])
            for e in miss).most_common(12)))
    if args.report:
        Path(args.report).write_text(json.dumps(ev))
        print(f"  report -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
