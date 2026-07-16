#!/usr/bin/env python3
"""Class-5 Phase-S opportunity AUDIT (Codex's go/no-go gate for the pause veto).

The veto only matters where the MODEL would GO at the eval_ext (legacy grant
fires) at the q_cnt=2 boundary. Among those opportunities:
  chip PAUSE = a +gap-error the veto would FIX.
  chip GO    = correct today; a veto here is a FALSE PAUSE -> injects a -impulse.

Grid-search pause predicates (cad>=T1 AND dage>=T2, optional popc==2) for a
ZERO-FALSE-PAUSE predicate (zero captured chip-GO) with meaningful coverage of the
chip-PAUSE population, on DISCOVERY / HELD-OUT / FRESH corpora and uniform+random
waits. GO S3 only if a zero-FP predicate covers >=10% of the fixable population on
held-out AND fresh. Chip = ground truth; model internals label the aligned prefix.

Usage: python3 sw/class5_pauseaudit.py
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, CODE)


def opportunities(seed, host, image, wv, out, tag):
    """Record q_cnt=2 boundary CODE->CODE eval_ext opportunities where the MODEL
    goes (prefetches at ~T4+1); label with chip go/pause + model history vars."""
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    kt4 = {}; kt1 = {}; bi = -1
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1; kt1[bi] = ri
        if x["t"] == 5:
            kt4[bi] = ri
    cb, kb = bs_stream(ca), bs_stream(ka)
    n = min(len(cb), len(kb))
    D = next((j for j in range(n)
              if cb[j] != kb[j] or ca[j]["addr"] != ka[j]["addr"]), n)

    def dage(t4):
        for r in range(t4, 0, -1):
            if kr[r]["q_cnt"] <= 1:
                return t4 - r
        return 99
    for i in range(1, D):
        if cb[i] != CODE or cb[i - 1] != CODE:
            continue
        if ca[i - 1]["t4"] is None or (i - 1) not in kt4 or (i - 2) not in kt1:
            continue
        x = kr[kt4[i - 1]]
        if x["q_cnt"] != 2:
            continue
        midle = sum(1 for r in range(ka[i - 1]["t4"] + 1, ka[i]["t1"])
                    if kr[r]["t"] == 0)
        # model GOES at the boundary = resumes ~immediately (idle<=1)
        if midle > 1:
            continue
        cidle = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                    if crel[r]["t"] == 0)
        out.append(dict(tag=tag, cad=kt1[i - 1] - kt1[i - 2],
                        dage=dage(kt4[i - 1]), popc=x.get("pop_cnt", -1),
                        chip_pause=(cidle >= 3)))


def gather(seeds, host, tag, out):
    for seed in seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        wvs = [[w] * 4096 for w in (1, 2, 3)]
        wvs += [[_r.Random((ws << 8) | wm).randint(0, wm) for _ in range(4096)]
                for ws in (4, 7) for wm in (3, 7)]
        for wv in wvs:
            try:
                opportunities(seed, host, image, wv, out, tag)
            except Exception as e:
                print(f"  fz{seed}: ERR {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--discovery", type=int, nargs="+",
                    default=list(range(90000, 90008)))
    ap.add_argument("--heldout", type=int, nargs="+",
                    default=list(range(91000, 91006)))
    ap.add_argument("--fresh", type=int, nargs="+",
                    default=list(range(92000, 92006)))
    a = ap.parse_args()
    out = []
    gather(a.discovery, a.host, "disc", out)
    gather(a.heldout, a.host, "held", out)
    gather(a.fresh, a.host, "fresh", out)
    for tag in ("disc", "held", "fresh"):
        sub = [r for r in out if r["tag"] == tag]
        npause = sum(1 for r in sub if r["chip_pause"])
        print(f"{tag}: {len(sub)} model-GO q_cnt=2 boundary opps, "
              f"{npause} chip-PAUSE (fixable +errors), {len(sub)-npause} chip-GO")

    print("\n=== zero-false-pause predicate grid search ===")
    print("pred (cad>=C & dage>=D [& popc==2]) : "
          "disc(fix/false) held(fix/false) fresh(fix/false) | coverage")
    best = None
    for C_ in range(10, 26, 2):
        for Dd in range(16, 44, 4):
            for pc2 in (False, True):
                def hit(r):
                    return (r["cad"] >= C_ and r["dage"] >= Dd
                            and (not pc2 or r["popc"] == 2))
                res = {}
                for tag in ("disc", "held", "fresh"):
                    sub = [r for r in out if r["tag"] == tag]
                    fix = sum(1 for r in sub if r["chip_pause"] and hit(r))
                    fp = sum(1 for r in sub if (not r["chip_pause"]) and hit(r))
                    res[tag] = (fix, fp)
                # zero-FP on held + fresh, and coverage of held+fresh pause pop
                hf_pause = sum(1 for r in out if r["tag"] in ("held", "fresh")
                               and r["chip_pause"])
                hf_fix = res["held"][0] + res["fresh"][0]
                zerofp = res["held"][1] == 0 and res["fresh"][1] == 0
                cov = hf_fix / max(1, hf_pause)
                tagp = "  ZERO-FP" if zerofp else ""
                if zerofp and hf_fix > 0:
                    line = (f"cad>={C_} dage>={Dd}{' popc2' if pc2 else '':7}: "
                            f"{res['disc']} {res['held']} {res['fresh']} | "
                            f"cov={cov:.0%}{tagp}")
                    print(line)
                    if best is None or cov > best[0]:
                        best = (cov, C_, Dd, pc2, res)
    print("\nBEST zero-FP predicate (held+fresh):",
          f"cad>={best[1]} dage>={best[2]}{' popc==2' if best[3] else ''} "
          f"coverage={best[0]:.0%}" if best else "NONE FOUND -> NO-GO")


if __name__ == "__main__":
    main()
