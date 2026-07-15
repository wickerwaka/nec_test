#!/usr/bin/env python3
"""predict_resume - two-rhythm software predictor of chip prefetch-resume.

Stage-3 go/no-go for the co-sim scheduler rewrite (reflash-free, no RTL). Tests
whether the chip's prefetch-resume slot is a clean FUNCTION of the two-rhythm
relative-phase state:
  Rhythm A (bus grid): phase within the bus cycle, re-synced at each T1, mod 4+N.
  Rhythm B (EU consumption): the queue-occupancy trajectory; a refill-threshold
    CROSSING = the first idle cycle after a bus cycle where occ <= refill-thresh.
  Relative beat phase = rhythm A phase AT the rhythm-B crossing.
Predictor key = (completed-cycle-kind, beat-phase-at-crossing, occ-at-crossing)
-> most-common resume gap. Match rate against the chip's ACTUAL prefetch T1s,
broken down overall / big-gap / by wait level. If big-gap match -> ~100% the
two-rhythm law closes (scheduler buildable); if it plateaus, residual variable.

Usage: predict_resume.py [--waits 0,1,3] [--seeds N] [--start K]
Reads cached chip captures from sw/testdata/chipcache/ (fill via measure.py).
"""
import argparse
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

CACHE = Path(__file__).resolve().parent / "testdata" / "chipcache"


def occ_trace(rows):
    """Physical queue bytes present per cycle (fetch +2/+1 at CODE T4, -1 per
    F/S pop, 0 at E flush)."""
    d = 0; cf = False; cw = False; o = []
    for r in rows:
        t = r["t"]; bs = r["bs_early"]
        if t == 1:
            cf = (bs == 4); cw = (r["ad_addr"] & 1) == 0 and not r["ube_n"]
        if t == 5 and cf:
            d += 2 if cw else 1; cf = False
        q = r["qs"]
        if q in (1, 3): d = max(d - 1, 0)
        elif q == 2: d = 0
        o.append(d)
    return o


def collect(rows, P, refill=4):
    """Yield a resume event per prefetch T1 with two-rhythm features."""
    oc = occ_trace(rows)
    last_t1 = prev_end = curk = prevk = None
    out = []
    for i, r in enumerate(rows):
        t = r["t"]
        if t == 1:
            if r["bs_early"] == 4 and prev_end is not None and \
                    i - prev_end < 40 and last_t1 is not None:
                cross = next((j for j in range(prev_end + 1, i + 1)
                             if oc[j] <= refill), None)
                if cross is not None:
                    out.append(dict(
                        kind="EU" if prevk != 4 else "PF",
                        beat=(cross - last_t1) % P,
                        occ=oc[cross],
                        gap=i - cross,
                        biggap=(i - prev_end - 1) > 2))
            last_t1 = i; curk = r["bs_early"]
        if t == 5:
            prev_end = i; prevk = curk
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--waits", default="0,1,3")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--start", type=int, default=90000)
    a = ap.parse_args()
    for w in [int(x) for x in a.waits.split(",")]:
        P = 4 + w
        evs = []
        for s in range(a.start, a.start + a.seeds):
            p = CACHE / f"s{s}_w{w}_base.json"
            if p.exists():
                evs += collect(json.loads(p.read_text()), P)
        if not evs:
            print(f"w{w}: no cached captures"); continue
        # two-rhythm predictor
        tab = defaultdict(Counter)
        for e in evs:
            tab[(e["kind"], e["beat"], e["occ"])][e["gap"]] += 1
        pr = lambda e: tab[(e["kind"], e["beat"], e["occ"])].most_common(1)[0][0]
        # baseline: no beat phase
        tab0 = defaultdict(Counter)
        for e in evs:
            tab0[(e["kind"], e["occ"])][e["gap"]] += 1
        pr0 = lambda e: tab0[(e["kind"], e["occ"])].most_common(1)[0][0]
        big = [e for e in evs if e["biggap"]]
        ov = 100 * sum(pr(e) == e["gap"] for e in evs) / len(evs)
        bg = 100 * sum(pr(e) == e["gap"] for e in big) / len(big) if big else 0
        bg0 = 100 * sum(pr0(e) == e["gap"] for e in big) / len(big) if big else 0
        print(f"w{w}: N={len(evs)} big={len(big)} | two-rhythm overall={ov:.1f}% "
              f"big-gap={bg:.1f}%  (vs no-phase big-gap={bg0:.1f}%)")


if __name__ == "__main__":
    main()
