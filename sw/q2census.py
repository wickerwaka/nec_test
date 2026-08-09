#!/usr/bin/env python3
"""q2census -- the REDIRECT-COMMIT census: where the flush `E` and the
redirect fetch's status sit, chip and model, through ONE reconstruction.

The open question (provenance 14.2, 16.6): in the Q2 fuzz family and in the
`EB` w1 goldens the CHIP shows the flush `E` on the SAME clock as the redirect
fetch's status display, while the model splits them.  Two prior attempts to
land the measured QS-port half alone were reverted for masking regressions.
This instrument extracts, per FLUSH EVENT and from the row streams alone:

  * the clock the `E` is displayed on
  * the redirect fetch's STATUS (display) clock and its T1
  * the PRIOR bus cycle: kind, T1, T4, its wait count, and its eval instant
  * the same five quantities for the model, aligned event by event

Sources (all optional, all additive):
  * `--goldens`: the flush-form v0.1 goldens at w0, and the w1/w3 suites
  * `--fuzz`:    the fuzz bank, restricted to seeds whose first divergence is
                 the Q2 signature (`qs E!=- bs CODE!=PASV`), or `--fuzz-all`

Chip and model go through the SAME extractor.  Golden rows are
`case["cycles"]` (built by sw/emit_suite.build_rows), model rows come from
check_core.build_rows_sim; fuzz rows are the bank's own `chip_rows` records
and the sim's ndjson records, i.e. exactly what sw/timed_fuzz.py compares.
"""

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core                      # noqa: E402
import timed_gate                      # noqa: E402
import fuzz_classify as fc             # noqa: E402
import ucsim_fuzz as uf                # noqa: E402
import timed_fuzz as tf                # noqa: E402

T_STR = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
Q_STR = {0: "-", 1: "F", 2: "E", 3: "S"}
T_NUM = {v: k for k, v in T_STR.items()}
BUS_NUM = {v: k for k, v in BUS_STR.items()}
Q_NUM = {v: k for k, v in Q_STR.items()}

FLUSH_FORMS = ["EB", "E9", "E8", "C2", "C3", "CA", "CB", "CC", "CD",
               "E0", "E1", "E2", "E3", "74", "75", "7C", "FF.4", "FF.2",
               "EA", "CF", "9A", "FF.3", "C8"]


# --- ONE row representation -------------------------------------------------

def rows_from_golden(cycles):
    """11-column rows -> (t, bs, qs) triples."""
    return [(T_NUM[r[8]], BUS_NUM[r[7]], Q_NUM[r[9]]) for r in cycles]


def rows_from_recs(recs):
    """raw per-clock records (bank chip_rows / sim ndjson) -> triples."""
    return [(r["t"], r["bs_early"], r["qs"]) for r in recs]


# --- the extractor ----------------------------------------------------------

def cycles_of(rows):
    """Bus cycles as dicts: t1 index, t4 index, kind (read off the T1 row),
    wait count.  A cycle occupies [T1..T4]; the status on a T4/Ti row belongs
    to the NEXT cycle (M2)."""
    out = []
    i, n = 0, len(rows)
    while i < n:
        if rows[i][0] != 1:
            i += 1
            continue
        j = i + 1
        while j < n and rows[j][0] in (2, 3, 4):
            j += 1
        if j >= n or rows[j][0] != 5:
            out.append({"t1": i, "t4": None, "bs": rows[i][1], "tw": None})
            break
        out.append({"t1": i, "t4": j, "bs": rows[i][1], "tw": (j - i) - 3})
        i = j + 1
    return out


def flush_events(rows):
    """Every QS=E row, with the redirect fetch that follows it and the bus
    cycle that precedes it."""
    cyc = cycles_of(rows)
    ev = []
    for i, r in enumerate(rows):
        if r[2] != 2:                       # QS != E
            continue
        # the redirect: the first CODE cycle whose T1 is at or after the E.
        red = next((c for c in cyc
                    if c["bs"] == 4 and c["t1"] >= i), None)
        # ...but a doomed fetch may still be RUNNING at the E, and its T1 is
        # BEFORE the E; the redirect is the first CODE T1 strictly after any
        # cycle already in flight at i.
        run = next((c for c in cyc
                    if c["t1"] <= i and (c["t4"] is None or c["t4"] >= i)),
                   None)
        if run is not None and red is not None and red["t1"] == run["t1"]:
            red = next((c for c in cyc
                        if c["bs"] == 4 and c["t1"] > i), None)
        # the prior cycle: the last one whose T4 is at or before the E, i.e.
        # the completed access the E's clock is measured from.
        prev = None
        for c in cyc:
            if c["t4"] is not None and c["t4"] <= i:
                prev = c
        ev.append({
            "e": i,
            "red_t1": red["t1"] if red else None,
            "red_disp": (red["t1"] - 1) if red else None,
            "red_tw": red["tw"] if red else None,
            "prev_t1": prev["t1"] if prev else None,
            "prev_t4": prev["t4"] if prev else None,
            "prev_tw": prev["tw"] if prev else None,
            "prev_bs": prev["bs"] if prev else None,
            "run_t1": run["t1"] if run else None,
            "run_t4": run["t4"] if run else None,
            "run_bs": run["bs"] if run else None,
            "run_tw": run["tw"] if run else None,
        })
    return ev


def pair_events(g, s):
    """Align chip and model flush events in order (there is one per flush)."""
    return list(zip(g, s))


def erec(tag, ev, rows):
    d = dict(ev)
    d["tag"] = tag
    d["n"] = len(rows)
    return d


# --- sources ----------------------------------------------------------------

def golden_source(forms, waits, ncases, suite):
    for name in forms:
        p = suite / f"{name}.json.gz"
        if not p.exists():
            continue
        cases = json.load(gzip.open(p))
        if ncases:
            cases = cases[:ncases]
        sims = timed_gate.run_form(cases, waits, False)
        for i, c in enumerate(cases):
            s = sims.get(i)
            if s is None:
                continue
            srows, _e, _i0, _i1 = check_core.build_rows_sim(
                s["recs"], c["initial"]["queue"],
                n_close=check_core.n_fpops(c) - 1)
            if srows is None:
                continue
            yield (f"{name}", i, waits,
                   rows_from_golden(c["cycles"]), rows_from_golden(srows))


def fuzz_one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception:                                        # noqa: BLE001
        return None
    if sha != entry["image_sha256"]:
        return None
    recs = entry["chip_rows"]
    with tempfile.TemporaryDirectory() as td:
        rows, err = tf.run_sim(image, entry, len(recs), td)
    if not rows:
        return None
    dr = fc.diff_rows(recs, rows)
    first = dr.rows[0].i if dr.rows else None
    w = entry.get("waits") or {}
    wtag = f"wrand{w.get('wmax')}" if w.get("wrand") else \
        f"fix{w.get('fixed') or 0}"
    return (f"{entry.get('cid')}/{entry.get('k')}", wtag, first,
            rows_from_recs(recs), rows_from_recs(rows))


# --- reporting --------------------------------------------------------------

def summarise(recs, title, args):
    """recs: list of (tag, key, waits/first, chip_rows, sim_rows)."""
    print(f"\n===== {title} =====")
    n_ev = 0
    coin_chip = Counter()
    coin_sim = Counter()
    off_chip = Counter()
    off_sim = Counter()
    rows_out = []
    for tag, key, extra, grows, srows in recs:
        gev = flush_events(grows)
        sev = flush_events(srows)
        for k, (ge, se) in enumerate(pair_events(gev, sev)):
            n_ev += 1
            # coincidence: is the E on the redirect's STATUS clock?
            def coin(e):
                if e["red_disp"] is None:
                    return "no-redirect"
                d = e["e"] - e["red_disp"]
                return f"{d:+d}"
            coin_chip[coin(ge)] += 1
            coin_sim[coin(se)] += 1
            # the E's offset from the PRIOR cycle's T4
            def off(e):
                if e["prev_t4"] is None:
                    return None
                return e["e"] - e["prev_t4"]
            og, os_ = off(ge), off(se)
            off_chip[(ge["prev_tw"], og)] += 1
            off_sim[(se["prev_tw"], os_)] += 1
            rows_out.append((tag, key, extra, k, ge, se))
    print(f"flush events: {n_ev}")
    print("  chip  E - redirect status clock: " +
          "  ".join(f"{k}={v}" for k, v in coin_chip.most_common()))
    print("  model E - redirect status clock: " +
          "  ".join(f"{k}={v}" for k, v in coin_sim.most_common()))
    if args.by_tw:
        print("  chip  (prev tw, E - prev T4): " +
              "  ".join(f"{k}={v}" for k, v in sorted(off_chip.items(),
                                                      key=str)))
        print("  model (prev tw, E - prev T4): " +
              "  ".join(f"{k}={v}" for k, v in sorted(off_sim.items(),
                                                      key=str)))
    return rows_out


def dump(rows_out, n):
    print("\n  tag                 key        ev  "
          "chip: E red_disp red_t1 prevT4 tw bs | model: E red_disp red_t1")
    for tag, key, extra, k, ge, se in rows_out[:n]:
        print(f"  {tag:<20}{str(key):<10} {k:>3}  "
              f"{ge['e']:>5} {str(ge['red_disp']):>8} {str(ge['red_t1']):>6} "
              f"{str(ge['prev_t4']):>6} {str(ge['prev_tw']):>2} "
              f"{BUS_STR.get(ge['prev_bs'], '?'):<4} | "
              f"{se['e']:>5} {str(se['red_disp']):>8} {str(se['red_t1']):>6}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", action="store_true")
    ap.add_argument("--forms", default=",".join(FLUSH_FORMS))
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--suite", default="tests/v30/v0.1")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--fuzz", action="store_true")
    ap.add_argument("--fuzz-all", action="store_true")
    ap.add_argument("--report", default="")
    ap.add_argument("--fuzzreport", default="",
                    help="a timed_fuzz --report json, to pick the Q2 family")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--dump", type=int, default=0)
    ap.add_argument("--by-tw", action="store_true")
    args = ap.parse_args()

    out = []
    if args.goldens:
        recs = list(golden_source([f for f in args.forms.split(",") if f],
                                  args.waits, args.cases, ROOT / args.suite))
        recs = [(t, i, w, g, s) for t, i, w, g, s in recs]
        out += summarise(recs, f"goldens {args.suite} w{args.waits}", args)
    if args.fuzz or args.fuzz_all:
        paths = []
        if args.fuzzreport:
            rep = json.load(open(args.fuzzreport))
            for r in rep:
                if r["cat"] not in ("EXACT", "DIVERGE"):
                    continue
                if args.fuzz_all or (not r["exact"] and
                                     r.get("detail", "").startswith(
                                         "qs E!=- bs CODE!=PASV")):
                    paths.append(r["path"])
        else:
            # MEASUREMENT TOOL, NOT A GATE, AND ITS SUBJECT IS THE v1 CORPUS:
            # `include_superseded=True` is passed DELIBERATELY so SUP-1's
            # retirement (docs/notes/invalidation_ledger.md) does not make this
            # instrument silently vacuous.  It replays nothing on any gate run.
            paths = tf.seeds_of(tf.BANKS, include_superseded=True)
        with Pool(args.jobs) as pool:
            res = [r for r in pool.map(fuzz_one, paths, chunksize=2) if r]
        recs = [(t, w, f, g, s) for t, w, f, g, s in res]
        out += summarise(recs, f"fuzz ({len(recs)} seeds)", args)
    if args.dump:
        dump(out, args.dump)
    if args.report:
        Path(args.report).write_text(json.dumps(
            [{"tag": t, "key": k, "extra": e, "ev": i, "chip": g, "sim": s}
             for t, k, e, i, g, s in out]))
        print(f"  report -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
