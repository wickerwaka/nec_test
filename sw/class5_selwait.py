#!/usr/bin/env python3
"""SELECTIVE PER-ACCESS-TYPE WAITS - TB SHAKEOUT (board-free).

Arm C: CODE fetches waited N, all DATA at 0.
Arm D: EU DATA accesses waited M, all CODE at 0.

WHY: every schedule ever run waits ALL accesses, so a fetch's own Tw and the
EU's consumption timing move TOGETHER. That covariance is why the corpus cannot
settle the mechanism. Selective waits break it on existing programs.

THE WRINKLE: the wait vector is BUS-CYCLE-ORDINAL indexed, and selective waits
CHANGE the stream, so ordinal->type drifts. Hence FIXED-POINT ITERATION:
  v0 from a w0 reference typing -> run -> re-type from the ACTUAL capture ->
  rebuild -> repeat. CONVERGED iff the capture itself satisfies the rule:
  every CODE access has tw==N and every non-CODE access has tw==0, checked
  directly from accesses() per-access tw. Non-converging cells are DISCARDED
  AND COUNTED - never fudged.

This is the board-free half: prove the fixed point converges and measure the
MODEL response curves, so board time is spent only on ranked cells.
"""
import sys, json
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import generate, compose, run_tb_internal, accesses, CODE

MAXV = 4096


def model_accesses(rows):
    return accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                          ad_addr=x["addr"], ad_data=0) for x in rows])


def build_vec(acc, N, M):
    """Tw per bus-cycle ordinal from a typing: CODE->N, everything else->M."""
    v = [0] * MAXV
    for i, a in enumerate(acc):
        if i >= MAXV:
            break
        v[i] = N if a["bs"] == CODE else M
    return v


def check_converged(acc, N, M):
    """The capture must SATISFY the rule: every CODE tw==N, every non-CODE tw==M."""
    bad = 0
    for a in acc:
        want = N if a["bs"] == CODE else M
        if a["tw"] != want:
            bad += 1
    return bad


def fixed_point(image, N, M, iters=12):
    """Iterate v -> capture -> re-type -> v until the capture satisfies the rule."""
    rows = run_tb_internal(image, 4200, [0] * MAXV)
    acc = model_accesses(rows)
    hist = []
    for it in range(iters):
        v = build_vec(acc, N, M)
        rows = run_tb_internal(image, 4200, v)
        acc2 = model_accesses(rows)
        bad = check_converged(acc2, N, M)
        hist.append(bad)
        if bad == 0:
            return True, it + 1, rows, acc2, hist
        # re-type from the ACTUAL capture and rebuild
        acc = acc2
    return False, iters, rows, acc, hist


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[90003, 90007, 90016, 91006, 91008])
    ap.add_argument("--armC", type=int, nargs="+", default=[1, 2, 3, 4, 6, 8, 12, 20])
    ap.add_argument("--armD", type=int, nargs="+", default=[1, 2, 3, 4, 8])
    a = ap.parse_args()
    logf = (SW / "class5_selwait.log").open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n"); logf.flush()

    log("=== SELECTIVE-WAIT TB SHAKEOUT (board-free) ===")
    log("convergence = the CAPTURE satisfies the rule (every CODE tw==N, every")
    log("non-CODE tw==M), checked from accesses() per-access tw. Not a proxy.\n")

    results = {}
    log(f"    {'arm':4} {'seed':>6} {'N':>3} {'M':>3} {'conv':>5} {'iters':>6}  bad-per-iter")
    for arm, vals in (("C", [(n, 0) for n in a.armC]), ("D", [(0, m) for m in a.armD])):
        for (N, M) in vals:
            for seed in a.seeds:
                g = generate(f"fz{seed}", exts=())
                image, meta = compose(g)
                try:
                    ok, its, rows, acc, hist = fixed_point(image, N, M)
                except Exception as e:
                    log(f"    {arm:4} {seed:>6} {N:>3} {M:>3} {'ERR':>5}  {e}")
                    continue
                results[(arm, seed, N, M)] = dict(conv=ok, iters=its, hist=hist)
                log(f"    {arm:4} {seed:>6} {N:>3} {M:>3} {str(ok):>5} {its:>6}  {hist[:6]}")
    nconv = sum(1 for v in results.values() if v["conv"])
    log(f"\n  CONVERGED: {nconv}/{len(results)}   NON-CONVERGING (discarded+counted): "
        f"{len(results)-nconv}")
    json.dump({f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v for k, v in results.items()},
              (SW / "class5_selwait.json").open("w"), indent=1)
    log(f"\nwrote {SW/'class5_selwait.json'}")
    logf.close()


if __name__ == "__main__":
    main()
