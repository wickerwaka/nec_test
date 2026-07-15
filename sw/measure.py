#!/usr/bin/env python3
"""measure - chip-vs-TB drift metric for the BIU rebuild (Stages 2/3).

Ground truth = the socketed chip (reflash-free). Chip captures are CACHED to
disk keyed by (seed, waits, exts) so an RTL edit only re-runs the Verilator TB,
not the board. Reports the drift trajectory: per-seed bad-rows, aggregate
mean/median, fully-clean count, and the first-divergence distribution - the
numbers the resume-predicate payoff moves.

Usage:
  measure.py cache  --seeds N [--start K] [--waits 0,1,3]   # fill chip cache
  measure.py drift  --seeds N [--start K] [--waits 0,1,3]   # TB vs cached chip
  measure.py adjud  SEED --waits W                          # single-seed dump
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from check_seq import compose, run_chip, run_tb, diff       # noqa: E402
from gen_seq import generate                                # noqa: E402

CACHE = SW / "testdata" / "chipcache"
CACHE.mkdir(exist_ok=True)


def chip_ref(seed, waits, host, exts=()):
    key = CACHE / f"s{seed}_w{waits}_{'_'.join(exts) or 'base'}.json"
    if key.exists():
        return json.loads(key.read_text())
    g = generate(seed, exts=exts)
    image, meta = compose(g)
    real = run_chip(image, host, use_core=False, waits=waits)
    # store only the columns diff() needs, as plain lists
    slim = [{"t": r.get("t_state", r.get("t")), "bs_early": r["bs_early"],
             "qs": r["qs"], "ube_n": r["ube_n"], "ad_addr": r["ad_addr"],
             "ad_data": r["ad_data"], "ps": r["ps"]} for r in real]
    key.write_text(json.dumps(slim))
    return slim


def one(seed, waits, host, exts=()):
    real = chip_ref(seed, waits, host, exts)
    real = [dict(r, t_state=r["t"]) for r in real]
    g = generate(seed, exts=exts)
    image, meta = compose(g)
    sim = run_tb(image, 4200, waits=waits)
    bad, first, n, flick = diff(real, sim, maxprint=0)
    return bad, first, n


def cmd_cache(a):
    for w in [int(x) for x in a.waits.split(",")]:
        for s in range(a.start, a.start + a.seeds):
            chip_ref(s, w, a.host)
            print(f"cached seed{s} w{w}", flush=True)
    return 0


def cmd_drift(a):
    for w in [int(x) for x in a.waits.split(",")]:
        rows = []
        clean = 0
        firsts = []
        for s in range(a.start, a.start + a.seeds):
            bad, first, n = one(s, w, a.host)
            rows.append(bad)
            if bad == 0:
                clean += 1
            else:
                firsts.append(first)
            print(f"  w{w} seed{s}: bad={bad} first@{first} ({n} rows)",
                  flush=True)
        print(f"=== waits={w}: N={len(rows)} bad-rows mean={statistics.mean(rows):.1f} "
              f"median={statistics.median(rows):.1f} CLEAN={clean}/{len(rows)} "
              f"first-div median={statistics.median(firsts) if firsts else '-'}",
              flush=True)
    return 0


def cmd_adjud(a):
    """Single-seed chip-vs-TB row dump for adjudicating a w0 delta."""
    from check_seq import BS_NAME, T_NAME, QS_NAME
    real = chip_ref(a.seed, a.waits, a.host)
    real = [dict(r, t_state=r["t"]) for r in real]
    g = generate(a.seed, exts=())
    image, meta = compose(g)
    sim = run_tb(image, 4200, waits=a.waits)
    bad, first, n, flick = diff(real, sim, maxprint=40)
    print(f"seed {a.seed} w{a.waits}: bad={bad} first@{first} n={n}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cache", "drift"):
        p = sub.add_parser(name)
        p.add_argument("--host", default="root@mister-nec")
        p.add_argument("--seeds", type=int, default=40)
        p.add_argument("--start", type=int, default=90000)
        p.add_argument("--waits", default="0,1,3")
        p.set_defaults(fn=cmd_cache if name == "cache" else cmd_drift)
    p = sub.add_parser("adjud")
    p.add_argument("seed", type=int)
    p.add_argument("--waits", type=int, default=0)
    p.add_argument("--host", default="root@mister-nec")
    p.set_defaults(fn=cmd_adjud)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
