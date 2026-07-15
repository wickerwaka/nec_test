#!/usr/bin/env python3
"""baseline_wrand - Phase 1 random-wait baseline characterization.

Measures the current (master, flashed) model's divergence under SEEDED RANDOM
per-access wait states, in TRUE write-anchored clock-cycle terms (the same
metric as timing_magnitude.py: the clock delta between the chip's and the
comparand's k-th memory write, normalized to the first common write).

Three positions, all on the same image with the SAME wrand seed:
  chip   = socketed part      (use_core=0)   -- ground truth
  fabric = in-FPGA v30_core   (use_core=1)
  tb     = Verilator v30_core (+wrand plusargs)

Reports, per wait-config:
  - chip-vs-fabric and chip-vs-TB |final offset| median/mean/WORST, peak
    excursion, fully-cycle-clean fraction
  - functional identity (memory writes byte-identical)
  - rig proof: per-access Tw-count sequence identical chip vs fabric

Usage:
  baseline_wrand.py rigproof [--seed S] [--wmax K]
  baseline_wrand.py sweep --start 90000 --seeds 200 --wmax 3,7 [--wbase 0x1234]
  baseline_wrand.py sweep --uniform 1,3 ...      # uniform reference on same set
"""
import argparse
import statistics
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from check_seq import compose, run_chip, run_tb          # noqa: E402
from gen_seq import generate                             # noqa: E402
from timing_magnitude import writes, fetches, faddr_resync  # noqa: E402


def per_access_waits(rows):
    """Per bus cycle: (bs_early, Tw-count). Tw = rows with t==4 between T1s."""
    out, cur, tw = [], None, 0
    for r in rows:
        if r["t"] == 1:
            if cur is not None:
                out.append((cur, tw))
            cur, tw = r["bs_early"], 0
        elif r["t"] == 4 and cur is not None:
            tw += 1
    if cur is not None:
        out.append((cur, tw))
    return out


def woff(chip, core):
    """Write-anchored clock offset chip vs core (normalized to first write)."""
    cw, kw = writes(chip), writes(core)
    nw = min(len(cw), len(kw))
    ok = (len(cw) == len(kw)) and all(cw[k][1:] == kw[k][1:] for k in range(nw))
    d = [cw[k][0] - kw[k][0] for k in range(nw)]
    if d:
        d0 = d[0]
        d = [x - d0 for x in d]
    final = d[-1] if d else 0
    absmax = max((abs(x) for x in d), default=0)
    return dict(final=final, absmax=absmax, writes_ok=ok,
                nwc=len(cw), nwk=len(kw))


def capture(seed, host, exts, w, wr):
    """Run one image on all three positions. Returns (chip, fab, tb)."""
    g = generate(seed, exts=exts)
    image, meta = compose(g)
    chip = run_chip(image, host, use_core=False, waits=w, wrand=wr)
    fab = run_chip(image, host, use_core=True, waits=w, wrand=wr)
    tb = run_tb(image, 4200, waits=w, wrand=wr)
    return chip, fab, tb


def rigproof(a):
    """Step 1: prove the SAME seed gives the SAME wait pattern chip vs fabric."""
    wr = (a.wmax, a.wseed & 0xFFFF)
    print(f"rig proof: seed fz{a.seed} wmax={a.wmax} wseed={a.wseed:#06x}")
    chip, fab, tb = capture(f"fz{a.seed}", a.host, (), 0, wr)
    pc, pf, pt = (per_access_waits(chip), per_access_waits(fab),
                  per_access_waits(tb))
    n = min(len(pc), len(pf))
    # compare Tw-count sequence position-by-position (bs_early + tw)
    mism = [k for k in range(n) if pc[k] != pf[k]]
    twhist = {}
    for _, tw in pc[:n]:
        twhist[tw] = twhist.get(tw, 0) + 1
    print(f"  accesses: chip={len(pc)} fabric={len(pf)} tb={len(pt)}")
    print(f"  chip Tw-count histogram (0..wmax): "
          f"{dict(sorted(twhist.items()))}")
    print(f"  chip-vs-fabric per-access (bs,Tw) identical over first {n}: "
          f"{'YES' if not mism else f'NO ({len(mism)} mism @ {mism[:8]})'}")
    ntb = min(len(pc), len(pt))
    mism_tb = [k for k in range(ntb) if pc[k] != pt[k]]
    print(f"  chip-vs-TB     per-access (bs,Tw) identical over first {ntb}: "
          f"{'YES' if not mism_tb else f'NO ({len(mism_tb)} mism @ {mism_tb[:8]})'}")
    wf = woff(chip, fab)
    wt = woff(chip, tb)
    print(f"  write-anchored offset: chip-vs-fabric final={wf['final']:+d} "
          f"absmax={wf['absmax']} writes_ok={wf['writes_ok']} | "
          f"chip-vs-TB final={wt['final']:+d} absmax={wt['absmax']} "
          f"writes_ok={wt['writes_ok']}")
    return 0


def summarize(label, rows, key):
    vals = [abs(r[key]["final"]) for r in rows]
    amax = [r[key]["absmax"] for r in rows]
    clean = sum(1 for r in rows if r[key]["final"] == 0 and r[key]["absmax"] == 0)
    wok = sum(1 for r in rows if r[key]["writes_ok"])
    print(f"  [{label}] N={len(rows)} |final| med={statistics.median(vals):.0f} "
          f"mean={statistics.mean(vals):.2f} WORST={max(vals)} clk | "
          f"peak-excursion med={statistics.median(amax):.0f} worst={max(amax)} | "
          f"fully-clean={clean}/{len(rows)} | writes-identical={wok}/{len(rows)}",
          flush=True)


def sweep(a):
    configs = []
    if a.wmax:
        for k in [int(x) for x in a.wmax.split(",")]:
            configs.append((f"rand-wmax{k}", 0, k))
    if a.uniform:
        for w in [int(x) for x in a.uniform.split(",")]:
            configs.append((f"uniform-w{w}", w, None))
    for label, w, k in configs:
        rows = []
        print(f"=== config {label} ===", flush=True)
        for s in range(a.start, a.start + a.seeds):
            wr = (k, (a.wbase ^ s) & 0xFFFF) if k is not None else None
            try:
                chip, fab, tb = capture(f"fz{s}", a.host, (), w, wr)
            except Exception as e:                       # noqa: BLE001
                print(f"  fz{s}: SKIP ({type(e).__name__}: {e})", flush=True)
                continue
            r = dict(seed=s, cf=woff(chip, fab), ct=woff(chip, tb))
            rows.append(r)
            print(f"  fz{s}: chip-fab final={r['cf']['final']:+d} "
                  f"absmax={r['cf']['absmax']:3} wok={int(r['cf']['writes_ok'])} | "
                  f"chip-tb final={r['ct']['final']:+d} "
                  f"absmax={r['ct']['absmax']:3} wok={int(r['ct']['writes_ok'])}",
                  flush=True)
        if rows:
            summarize(f"{label} chip-vs-FABRIC", rows, "cf")
            summarize(f"{label} chip-vs-TB    ", rows, "ct")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rigproof")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90000)
    p.add_argument("--wmax", type=int, default=3)
    p.add_argument("--wseed", type=lambda x: int(x, 0), default=0x1234)
    p.set_defaults(fn=rigproof)
    p = sub.add_parser("sweep")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--start", type=int, default=90000)
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--wmax", default="3,7", help="random wmax list (comma)")
    p.add_argument("--uniform", default="", help="uniform waits list (comma)")
    p.add_argument("--wbase", type=lambda x: int(x, 0), default=0x1234)
    p.set_defaults(fn=sweep)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
