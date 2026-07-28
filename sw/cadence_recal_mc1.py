#!/usr/bin/env python3
"""cadence_recal_mc1 - wrand cadence-floor threshold verdict over a campaign's
wrand population (task #29 P7). Board-free: recomputes cadence_metrics from the
gzipped captures of every wrand divergent seed and reports the accept-rate at
the frozen threshold (max_step=9) vs the proposed widening (max_step=15), the
maxstep distribution, and - critically - whether widening would swallow any
code_mism / func divergence (the floor's #1 risk).

    python3 sw/cadence_recal_mc1.py mc1
"""
import argparse
import glob
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_accept as fa                                    # noqa: E402
import fuzz_classify as fc                                  # noqa: E402
CAMPAIGNS = SW / "testdata" / "campaigns"


def pct(a, p):
    return a[min(len(a) - 1, int(p * len(a)))] if a else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cid")
    ap.add_argument("--proposed", type=int, default=15)
    a = ap.parse_args()
    cdir = CAMPAIGNS / a.cid
    rows = [json.loads(l) for l in (cdir / "results.jsonl").read_text().splitlines()
            if l.strip()]
    eng = fa.AcceptEngine.load()
    thr = next(r.thr for r in eng.rules if isinstance(r, fa.CadenceFloorRule))
    frozen = thr["max_step"]

    wrand = [r for r in rows if r["waits"].get("wrand")
             and r["verdict"] in ("TIMING", "KNOWN_ACCEPTED")]
    maxsteps, reasons = [], Counter()
    # per-seed recomputed metric + what widening would do
    would_accept_at = {frozen: 0, a.proposed: 0}
    newly_by_reason = Counter()
    danger = []            # divergences a wider step would swallow but must not
    n_cap = 0
    for r in wrand:
        fs = glob.glob(str(cdir / "captures" /
                           f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"))
        if not fs:
            continue
        d = json.load(gzip.open(fs[0], "rt"))
        dr = fc.diff_rows(d["real"], d["sim"], window=r["win"])
        m = fa.cadence_metrics(d["real"], d["sim"], dr, thr)
        n_cap += 1
        maxsteps.append(m["maxstep"])
        reasons[m["reason"] or "accept"] += 1
        # accept iff reason is None under a given max_step (holding other bounds)
        for ms in (frozen, a.proposed):
            ok = m["reason"] is None or (
                m["reason"] and m["reason"].startswith("step_break")
                and m["maxstep"] <= ms)
            would_accept_at[ms] += int(ok)
        # newly accepted by widening: was rejected at frozen, accepted at proposed
        rej_frozen = not (m["reason"] is None or (
            m["reason"] and m["reason"].startswith("step_break")
            and m["maxstep"] <= frozen))
        acc_prop = m["reason"] is None or (
            m["reason"] and m["reason"].startswith("step_break")
            and m["maxstep"] <= a.proposed)
        if rej_frozen and acc_prop:
            newly_by_reason[m["reason"] or "accept"] += 1
        # a non-step reject (code_mism/pre_tw/skip_frac/rate_break) is never
        # step-gated, so a max_step widening cannot accept it. Confirm: was it
        # rejected at frozen AND (wrongly) accepted at proposed?
        if rej_frozen and acc_prop and m["reason"] \
                and not m["reason"].startswith("step_break"):
            danger.append((r["k"], m["reason"], m["maxstep"]))

    maxsteps.sort()
    # histogram bands to expose the distribution shape (is there a cliff at 15?)
    bands = [(0, 9), (10, 15), (16, 30), (31, 63), (64, 127), (128, 1 << 30)]
    hist = Counter()
    for ms in maxsteps:
        for lo, hi in bands:
            if lo <= ms <= hi:
                hist[(lo, hi)] += 1
                break
    print("maxstep histogram (bands): " + "  ".join(
        f"[{lo}-{'inf' if hi > 1000 else hi}]={hist[(lo,hi)]}" for lo, hi in bands))
    print(f"# cadence recal over {a.cid}: {len(wrand)} wrand divergent seeds, "
          f"{n_cap} with captures\n")
    print(f"maxstep distribution: p50={pct(maxsteps,.5)} p90={pct(maxsteps,.9)} "
          f"p95={pct(maxsteps,.95)} p99={pct(maxsteps,.99)} max={maxsteps[-1] if maxsteps else 0}")
    print(f"reject reasons: {dict(reasons)}")
    print(f"\naccept-rate @ frozen(max_step={frozen}): "
          f"{would_accept_at[frozen]}/{n_cap} = {100*would_accept_at[frozen]/max(1,n_cap):.1f}%")
    print(f"accept-rate @ proposed(max_step={a.proposed}): "
          f"{would_accept_at[a.proposed]}/{n_cap} = {100*would_accept_at[a.proposed]/max(1,n_cap):.1f}%")
    print(f"newly accepted by widening {frozen}->{a.proposed}: "
          f"{would_accept_at[a.proposed]-would_accept_at[frozen]} "
          f"(by reason: {dict(newly_by_reason)})")
    print(f"\nSAFETY: non-step reject reasons a step widening would swallow: "
          f"{len(danger)} (MUST be 0) {danger[:5]}")


if __name__ == "__main__":
    main()
