#!/usr/bin/env python3
"""classify_split - re-classify the three-way w1/w3 drift split on current RTL.

For each seed, find the first-divergence row and classify its context by the
chip-vs-TB bus pattern in a window around it:
  FLUSH  - a QS=E (flush) event within +/-6 rows on either side (branch redirect)
  ARB    - chip CODE (prefetch) where TB has MEMR/MEMW (or vice versa): EU-access
           vs prefetch ordering
  RESUME - same bus-kind but T-state/idle timing offset (prefetch pacing)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, run_tb, BS_NAME  # noqa: E402
from gen_seq import generate                     # noqa: E402
from measure import chip_ref                      # noqa: E402
import argparse


def classify(real, sim, first):
    lo = max(0, first - 6)
    hi = min(len(real), len(sim), first + 6)
    # flush: any QS=E on chip or TB in window
    flush = any(real[i]["qs"] == 2 or sim[i]["qs"] == 2 for i in range(lo, hi))
    r, s = real[first], sim[first]
    rb, sb = r["bs_early"], s["bs_early"]
    # arbitration: one side CODE(4), other MEM(5/6) at the divergence
    code_vs_mem = ({rb, sb} & {4}) and ({rb, sb} & {5, 6}) and rb != sb
    # also check window for the CODE-first-vs-MEMW arbitration signature
    arb_win = any((({real[i]["bs_early"], sim[i]["bs_early"]} & {4}) and
                   ({real[i]["bs_early"], sim[i]["bs_early"]} & {5, 6}) and
                   real[i]["bs_early"] != sim[i]["bs_early"])
                  for i in range(lo, hi))
    if flush:
        return "FLUSH"
    if code_vs_mem or arb_win:
        return "ARB"
    return "RESUME"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--start", type=int, default=90000)
    ap.add_argument("--waits", type=int, default=1)
    a = ap.parse_args()
    counts = {"FLUSH": 0, "ARB": 0, "RESUME": 0, "CLEAN": 0}
    detail = []
    for s in range(a.start, a.start + a.seeds):
        real = chip_ref(s, a.waits, a.host)
        real = [dict(r, t_state=r["t"]) for r in real]
        g = generate(s, exts=())
        image, meta = compose(g)
        sim = run_tb(image, 4200, waits=a.waits)
        from check_seq import diff
        bad, first, n, flick = diff(real, sim, maxprint=0)
        if bad == 0:
            counts["CLEAN"] += 1
            continue
        cls = classify(real, sim, first)
        counts[cls] += 1
        detail.append((s, first, cls, BS_NAME[real[first]["bs_early"]],
                       BS_NAME[sim[first]["bs_early"]]))
    print(f"=== w{a.waits} split over {a.seeds} seeds ===")
    for k, v in counts.items():
        print(f"  {k:8} {v}")
    print("--- first-div detail (seed first cls chipBS tbBS) ---")
    for d in sorted(detail, key=lambda x: x[1]):
        print(f"  {d[0]} @{d[1]:5} {d[2]:8} chip={d[3]:5} tb={d[4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
