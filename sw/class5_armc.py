#!/usr/bin/env python3
"""POWERED ARM C: CODE-only selective waits, the sixth-attempt tiebreaker.

Arm C waits CODE fetches by N, all DATA at 0. THE DIAGNOSTIC: our HEAD build
saturates at cidle 4 (the staged path structurally CANNOT emit 3 - q_aged
blackout at T4+2). max()/pre-wait-frame predicts the CHIP pins at cidle 3 for
tw>=4 and STAYS 3 through N=20. So at N=8/12/20:
  chip pins at 3, model pins at 4  -> DIRECT SILICON EVIDENCE the ~85u
    direct-path ceiling is real chip behaviour -> justifies a sixth attempt.
  chip does NOT pin at 3           -> the sixth attempt's premise weakens ->
    ship the plateau.

FIXED POINT ON THE CHIP STREAM (not the model): the wait vector is bus-cycle-
ordinal indexed and CODE-only waits change the stream, so ordinal->type drifts.
Iterate: type from a capture -> build vector -> re-capture -> until the CAPTURE
satisfies the rule (every CODE access tw==N, every non-CODE tw==0). Converged
cells only; non-converging (program, N) are DISCARDED AND COUNTED.

TWO OBSERVABLES:
  (1) EXTINCTION RATE: pause fraction vs N. max() predicts pauses go extinct as
      N grows (deadline slides past, floor binds, GO). Cheap - needs few rows.
  (2) CIDLE PIN: at matched keys (occ@T4+1, pred-fetch waited), the chip cidle
      distribution. Pin-at-3 is the decisive signal where n>=15 post-strat.

use_core=False (real chip), read-only. No flash. Per-cell timeout + incremental.
"""
import sys, json, gzip, time, argparse
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import (generate, compose, run_chip, accesses, bs_stream, CODE)

MAXV = 4096
OUT = SW / "class5_armc.jsonl.gz"
LOG = SW / "class5_armc.log"


def chip_acc(image, host, wv):
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
    return crel, accesses(crel)


def build_vec(acc, N):
    v = [0] * MAXV
    for i, a in enumerate(acc):
        if i >= MAXV:
            break
        v[i] = N if a["bs"] == CODE else 0
    return v


def converged(acc, N):
    return all((a["tw"] == (N if a["bs"] == CODE else 0)) for a in acc)


def fixed_point_chip(image, host, N, iters=8):
    """Converge the CODE-only wait vector on the CHIP's own access stream."""
    crel, acc = chip_acc(image, host, [0] * MAXV)
    for it in range(iters):
        v = build_vec(acc, N)
        crel, acc = chip_acc(image, host, v)
        if converged(acc, N):
            return True, it + 1, crel, acc
    return False, iters, crel, acc


def pauses(crel, acc):
    """CODE->CODE resume events: (occ-proxy, pred_tw, chip cidle)."""
    out = []
    for i in range(1, len(acc)):
        if acc[i]["bs"] != CODE or acc[i - 1]["bs"] != CODE:
            continue
        if acc[i - 1]["t4"] is None:
            continue
        cidle = sum(1 for r in range(acc[i - 1]["t4"] + 1, acc[i]["t1"])
                    if crel[r]["t"] == 0)
        out.append(dict(cidle=cidle, pred_tw=acc[i - 1]["tw"],
                        pred_par=acc[i - 1]["addr"] & 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--Ns", type=int, nargs="+", default=[1, 2, 3, 4, 6, 8, 12, 20])
    ap.add_argument("--nprog", type=int, default=20,
                    help="programs per N (scale until n>=15 post-strat)")
    ap.add_argument("--base", type=int, default=90000)
    a = ap.parse_args()
    logf = LOG.open("w")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    log(f"start {time.ctime()}  POWERED ARM C  Ns={a.Ns} nprog={a.nprog}")
    allrows = []
    disc = defaultdict(lambda: dict(conv=0, noconv=0, events=0, pause=0,
                                    cidle=defaultdict(int)))
    for N in a.Ns:
        for k in range(a.nprog):
            seed = a.base + k
            g = generate(f"fz{seed}", exts=())
            image, meta = compose(g)
            t0 = time.time()
            try:
                ok, its, crel, acc = fixed_point_chip(image, a.host, N)
            except Exception as e:
                log(f"  N={N} fz{seed}: ERR {e}")
                continue
            d = disc[N]
            if not ok:
                d["noconv"] += 1
                continue
            d["conv"] += 1
            ev = pauses(crel, acc)
            d["events"] += len(ev)
            for e in ev:
                if e["cidle"] >= 3:
                    d["pause"] += 1
                    d["cidle"][e["cidle"]] += 1
                allrows.append(dict(N=N, seed=seed, **e))
        d = disc[N]
        log(f"  N={N:>2}: conv={d['conv']} noconv={d['noconv']} events={d['events']} "
            f"pauses={d['pause']} ({100*d['pause']/max(1,d['events']):.1f}%)  "
            f"cidle={dict(sorted(d['cidle'].items()))}")
        with gzip.open(OUT, "wt") as f:
            for r in allrows:
                f.write(json.dumps(r) + "\n")

    log("\n=== EXTINCTION RATE (max() predicts pauses -> extinct as N grows) ===")
    log(f"  {'N':>3} {'events':>7} {'pauses':>7} {'pause%':>7}  cidle-dist")
    for N in a.Ns:
        d = disc[N]
        log(f"  {N:>3} {d['events']:>7} {d['pause']:>7} "
            f"{100*d['pause']/max(1,d['events']):>6.1f}%  "
            f"{dict(sorted(d['cidle'].items()))}")
    log("\n=== CIDLE PIN TEST (the decisive signal) ===")
    log("  max(): chip pins at 3 for high N. model (HEAD): pins at 4.")
    for N in [n for n in a.Ns if n >= 8]:
        d = disc[N]
        c3 = d["cidle"].get(3, 0); c4 = d["cidle"].get(4, 0)
        tot = sum(d["cidle"].values())
        verdict = ("PINS AT 3" if c3 > c4 else ("PINS AT 4" if c4 > c3 else "split"))
        log(f"  N={N:>2}: cidle3={c3} cidle4={c4} (n={tot})  -> chip {verdict}"
            f"{'  [n<15, underpowered]' if tot < 15 else ''}")
    log(f"\ndone {time.ctime()}")
    logf.close()


if __name__ == "__main__":
    main()
