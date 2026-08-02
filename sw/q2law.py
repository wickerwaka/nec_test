#!/usr/bin/env python3
"""q2law -- what predicts the CHIP's flush `E` clock?

The flush INSTANT is an EU quantity: the micro-row that calls `flush()`.  It is
not in question here (the model reproduces the whole control-flow tranche at
w0), so it can be read out of the model with `V30SIM_FLUSHTRACE` and used as
the independent variable.  Everything else in this census is read from the
CHIP's own rows:

    x         the flush clock (model, FLUSHTRACE `FX`)
    e         the clock the CHIP displays QS=E on
    disp      the CHIP's first bus-cycle STATUS DISPLAY at or after x
              (a cycle whose T1 is at x+1 or later displays at T1-1)
    prev T4   the last completed cycle at or before x, and its wait count

and the model's own answers for the same three, so the two can be scored event
by event.  Sources: the v0.1 flush-form goldens at w0, the w1/w3 suites, and
the fuzz bank (pre-divergence events only, unless --all-events).
"""

import argparse
import gzip
import json
import os
import sys
import subprocess
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
import q2census as qc                  # noqa: E402

FLUSH_FORMS = ["EB", "E9", "E8", "C2", "C3", "CA", "CB", "CC", "CD", "CE",
               "CF", "EA", "9A", "C8", "E0", "E1", "E2", "E3",
               "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
               "7A", "7B", "7C", "7D", "7E", "7F", "FF.2", "FF.3", "FF.4"]


# --- the per-event record ---------------------------------------------------

def cyc_of(rows):
    return qc.cycles_of(rows)


def event_at(rows, x):
    """Read the row stream's answers around the flush clock x."""
    cyc = cyc_of(rows)
    n = len(rows)
    e = next((i for i in range(max(0, x), n) if rows[i][2] == 2), None)
    disp = next((c["t1"] - 1 for c in cyc if c["t1"] >= x + 1), None)
    # the cycle RUNNING at x (T1 <= x <= T4), and the last one COMPLETED
    run = next((c for c in cyc if c["t1"] <= x and
                (c["t4"] is None or c["t4"] >= x)), None)
    prev = None
    for c in cyc:
        if c["t4"] is not None and c["t4"] <= x:
            prev = c
    return {"e": e, "disp": disp,
            "run_bs": run["bs"] if run else None,
            "run_ci": (x - run["t1"]) if run else None,
            "run_t4": run["t4"] if run else None,
            "run_tw": run["tw"] if run else None,
            "prev_t4": prev["t4"] if prev else None,
            "prev_tw": prev["tw"] if prev else None,
            "prev_bs": prev["bs"] if prev else None}


def parse_trace(err):
    """-> list per case of {'fx': [clk...], 'fc': {clk: disp}}"""
    cases = []
    cur = None
    for l in err.splitlines():
        p = l.split()
        if not p:
            continue
        if p[0] == "FB":
            cur = {"fx": [], "fc": {}, "fe": []}
            cases.append(cur)
        elif cur is None:
            continue
        elif p[0] == "FX":
            cur["fx"].append(int(p[1]))
        elif p[0] == "FC":
            cur["fc"][int(p[1])] = int(p[2].split("=")[1])
        elif p[0] == "FE":
            cur["fe"].append(int(p[1]))
    return cases


# --- sources ----------------------------------------------------------------

def golden_events(form, waits, suite, ncases):
    p = suite / f"{form}.json.gz"
    if not p.exists():
        return []
    cases = json.load(gzip.open(p))
    if ncases:
        cases = cases[:ncases]
    env = dict(os.environ, V30SIM_FLUSHTRACE="1")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "rows.txt"
        argv = [str(timed_gate.SIM), "timed-run", str(timed_gate.ROM),
                f"--waits={waits}"]
        with open(out, "wb") as fo:
            r = subprocess.run(argv, input=json.dumps(cases).encode(),
                               stdout=fo, stderr=subprocess.PIPE, env=env)
        sims = check_core.parse_out(out)
    tr = parse_trace(r.stderr.decode())
    ev = []
    for i, c in enumerate(cases):
        s = sims.get(i)
        if s is None or i >= len(tr):
            continue
        srows, _e, i0, _i1 = check_core.build_rows_sim(
            s["recs"], c["initial"]["queue"],
            n_close=check_core.n_fpops(c) - 1)
        if srows is None:
            continue
        grows = qc.rows_from_golden(c["cycles"])
        mrows = qc.rows_from_golden(srows)
        for xclk in tr[i]["fx"]:
            x = xclk - i0
            if x < 0 or x >= len(grows):
                continue
            g = event_at(grows, x)
            m = event_at(mrows, x)
            ev.append({"src": f"{form}:w{waits}", "case": i, "x": x,
                       "pre": True, "g": g, "m": m})
    return ev


def fuzz_events(path):
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
    tr = parse_trace(err)
    if not tr:
        return []
    grows = qc.rows_from_recs(recs)
    mrows = qc.rows_from_recs(rows)
    ev = []
    for x in tr[-1]["fx"]:
        if x >= len(grows):
            continue
        g = event_at(grows, x)
        m = event_at(mrows, x)
        ev.append({"src": f"fuzz:{entry.get('cid')}/{entry.get('k')}",
                   "case": entry.get("k"), "x": x,
                   # UNCONTAMINATED: everything up to the flush clock is
                   # identical on both sides, so this event's inputs are the
                   # chip's own even if its OUTPUT is the first divergence.
                   "pre": x <= first,
                   "g": g, "m": m})
    return ev


# --- scoring ----------------------------------------------------------------

def score(ev, title, args):
    print(f"\n===== {title} =====")
    ev = [e for e in ev if e["g"]["e"] is not None]
    if not args.all_events:
        ev = [e for e in ev if e["pre"]]
    print(f"flush events with a chip E: {len(ev)}")
    if not ev:
        return
    print("\n[R0] chip E - flush clock:      " + "  ".join(
        f"{k}={v}" for k, v in Counter(e["g"]["e"] - e["x"]
                                       for e in ev).most_common(10)))
    print("[R0] model E - flush clock:     " + "  ".join(
        f"{k}={v}" for k, v in Counter(e["m"]["e"] - e["x"] for e in ev
                                       if e["m"]["e"] is not None
                                       ).most_common(10)))
    dd = [e for e in ev if e["g"]["disp"] is not None]
    print(f"\n[R1] chip E - chip next STATUS DISPLAY at/after the flush "
          f"({len(dd)} events)")
    print("     " + "  ".join(f"{k}={v}" for k, v in Counter(
        e["g"]["e"] - e["g"]["disp"] for e in dd).most_common(10)))
    print("[R1] by whether the bus was RUNNING a cycle at the flush clock:")
    tab = defaultdict(Counter)
    for e in dd:
        key = ("running" if e["g"]["run_bs"] is not None else "idle")
        tab[key][e["g"]["e"] - e["g"]["disp"]] += 1
    for k in sorted(tab):
        print(f"     {k:<9} " + "  ".join(f"{a}={b}" for a, b in
                                          tab[k].most_common(8)))
    print("\n[R2] chip E - flush clock, by (bus running?, its index, its "
          "wait count):")
    tab = Counter((e["g"]["run_bs"] is not None, e["g"]["run_ci"],
                   e["g"]["run_tw"], e["g"]["e"] - e["x"]) for e in ev)
    for k, v in sorted(tab.items(), key=str)[:60]:
        print(f"     run={k[0]} ci={k[1]} tw={k[2]}  E-x={k[3]:+d}   {v}")
    print("\n[R3] chip vs model E clock: " + "  ".join(
        f"{k}={v}" for k, v in Counter(
            (e["g"]["e"] - e["m"]["e"]) if e["m"]["e"] is not None else "none"
            for e in ev).most_common(8)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", action="store_true")
    ap.add_argument("--forms", default=",".join(FLUSH_FORMS))
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--suite", default="tests/v30/v0.1")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--fuzz", default="")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--all-events", action="store_true")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    ev = []
    if args.goldens:
        for f in args.forms.split(","):
            ev += golden_events(f.strip(), args.waits,
                                ROOT / args.suite, args.cases)
        score(ev, f"goldens {args.suite} w{args.waits}", args)
    if args.fuzz:
        paths = [l.split()[0] for l in open(args.fuzz)] \
            if Path(args.fuzz).is_file() else tf.seeds_of(tf.BANKS)
        with Pool(args.jobs) as pool:
            fev = [e for r in pool.map(fuzz_events, paths, chunksize=2)
                   for e in r]
        score(fev, f"fuzz ({len(paths)} seeds)", args)
        ev += fev
    if args.report:
        Path(args.report).write_text(json.dumps(ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
