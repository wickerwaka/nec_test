#!/usr/bin/env python3
"""wrfuzz W4 -- THE PREDICTION, derived from the CURRENT offline columns.

OFFLINE, board-free.  It does NOT compute the bar: the bar is `B = 86.6681 %`,
frozen at W2 (`wrfuzz_provenance.md` §3.1) and re-derivable from nothing.  This
tool computes what THIS SITTING EXPECTS the fresh tranche to score, per
stratum, so that the sitting's understanding is tested beside its bar.

THE CONSTRUCTION, stated before the number is read:

  1. The W2 table is REPRODUCED from `sw/testdata/campaigns/wr1/results.jsonl`
     with `wrfuzz_w2.open_bus` -- the registered exclusion -- and its `S` must
     come out at 91.6681 %.  A tool that cannot reproduce the frozen number is
     not allowed to predict with it.
  2. For every stratum, the seeds that were SCORED and NOT exact in fabric at
     W2 are looked up in the CURRENT `ucore` Verilator column over the same
     banked captures.  A seed the current core replays EXACTLY is predicted to
     CLOSE; a seed it still misses is predicted to stay missed.
  3. predicted_rate_i = (exact_i + closed_i) / scored_i, and the predicted
     tranche statistic is the unweighted mean of the 28 -- the SAME
     construction as `S`, because the bar is written in that construction.

THE THREE PLACES THIS CAN BE WRONG, named in advance:

  * The proxy is the TB, not the fabric.  W2 measured them agreeing on
    182 / 184 (§3.2), so the substitution costs about a point at most, and it
    is a SUBSTITUTION and not an identity.
  * Only 184 of the 380 retained captures are offline-scorable (the rest are
    the registered OPEN_BUS exclusion), so a scored miss with no offline row
    is predicted to STAY MISSED -- the conservative direction, and it is
    counted and reported rather than dropped.
  * Nothing here predicts a seed the survey scored EXACT going the other way.
    Y-3/Y-6's "ZERO LOST" bars were met on every population at W3.1-W3.5, so
    the prediction takes them at their measured word; a loss would be a
    finding against those bars and not against this arithmetic.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import wrfuzz_w1 as w1                                      # noqa: E402
import wrfuzz_w2 as w2                                      # noqa: E402

S_FROZEN = 91.6681
B_FROZEN = 86.6681


def main():
    tb_report = sys.argv[1]
    rows = w2.results()
    cur = {r["k"]: r for r in json.load(open(tb_report))}

    per = defaultdict(lambda: {"n": 0, "ob": 0, "scored": 0, "exact": 0,
                               "miss": 0, "closed": 0, "still": 0,
                               "no_offline": 0})
    for r in rows:
        st = w2.stratum_of(r["k"])
        t = per[st["i"]]
        t["n"] += 1
        if w2.open_bus(r):
            t["ob"] += 1
            continue
        t["scored"] += 1
        if r["verdict"] == "SUCCESS":
            t["exact"] += 1
            continue
        t["miss"] += 1
        c = cur.get(r["k"])
        if c is None or c.get("exact") is None or c.get("reason"):
            t["no_offline"] += 1
            t["still"] += 1
        elif c["exact"]:
            t["closed"] += 1
        else:
            t["still"] += 1

    print(f"{'i':>3} {'stratum':<16} {'scored':>7} {'exact':>6} {'W2%':>7} "
          f"{'miss':>5} {'closed':>7} {'noOFF':>6} {'pred%':>7} {'d':>6}")
    S = P = 0.0
    tot = defaultdict(int)
    for st in w1.STRATA:
        t = per[st["i"]]
        w2r = 100.0 * t["exact"] / t["scored"]
        pr = 100.0 * (t["exact"] + t["closed"]) / t["scored"]
        S += w2r
        P += pr
        for k in t:
            tot[k] += t[k]
        print(f"{st['i']:>3} {w1.label(st):<16} {t['scored']:>7} "
              f"{t['exact']:>6} {w2r:>7.2f} {t['miss']:>5} {t['closed']:>7} "
              f"{t['no_offline']:>6} {pr:>7.2f} {pr-w2r:>+6.2f}")
    S /= len(w1.STRATA)
    P /= len(w1.STRATA)
    print(f"\n  pooled W2   {tot['exact']}/{tot['scored']} = "
          f"{100.0*tot['exact']/tot['scored']:.2f} %")
    print(f"  pooled pred {tot['exact']+tot['closed']}/{tot['scored']} = "
          f"{100.0*(tot['exact']+tot['closed'])/tot['scored']:.2f} %")
    print(f"  scored misses {tot['miss']}, predicted CLOSED {tot['closed']}, "
          f"still missed {tot['still']} (of which {tot['no_offline']} have no "
          f"offline row and are held missed by the conservative rule)")
    print(f"\n  S  (reproduced) = {S:.4f} %   [frozen {S_FROZEN}]  "
          f"{'REPRODUCED' if abs(S - S_FROZEN) < 5e-4 else '*** DOES NOT REPRODUCE ***'}")
    print(f"  B  (frozen)     = {B_FROZEN} %   -- NOT re-derived here")
    print(f"  S' (predicted)  = {P:.4f} %   delta {P-S:+.4f} points")
    return 0 if abs(S - S_FROZEN) < 5e-4 else 1


if __name__ == "__main__":
    sys.exit(main())
