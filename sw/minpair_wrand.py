#!/usr/bin/env python3
"""minpair_wrand - Phase 1 minimal-pair tractability probe (chip, in silicon).

Question (Phase 2's key tool): can the random-wait rig produce clean MINIMAL
PAIRS for the prefetch-resume law -- two runs whose wait patterns are identical
around a resume decision EXCEPT for one inserted wait, with the chip's resume
gap shifting as a function of that one wait?

Method (no RTL, reflash-free): fix ONE program (fuzz seed => fixed architectural
access stream). Run it on the CHIP (use_core=0) under many WAIT-seeds at wmax=1
(binary waits). Architectural EU data accesses (MEMR/MEMW) are a stable anchor
across wait-seeds (writes proven byte-identical), so the k-th data access is the
same access in every run. For each data-access ordinal we measure:
  - resume gap = idle clocks from that access's T4 to the next CODE-fetch T1
    (the prefetch the BIU issues after the EU released the bus)
  - the LOCAL wait context = Tw of the data access and its neighbors
Then we tabulate gap vs local context. If the gap is a clean function of a
BOUNDED local window, minimal pairs are tractable (find two runs with the same
window except one bit -> gap delta = the single wait's effect). If the gap
scatters for a fixed local window, the resume law has long memory (matching the
"needs accumulated history" refutations) and corpus-search minimal pairs are
hard.

Usage: minpair_wrand.py --seed 90003 --nwseed 48 --wmax 1 [--ord K]
"""
import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from check_seq import compose, run_chip                  # noqa: E402
from gen_seq import generate                             # noqa: E402

MEMR, MEMW, CODE = 5, 6, 4


def accesses(rows):
    """Per bus cycle: dict(bs, t1, t4, tw). t1/t4 = row indices, tw = wait count."""
    out, cur = [], None
    for i, r in enumerate(rows):
        if r["t"] == 1:
            if cur is not None:
                out.append(cur)
            cur = dict(bs=r["bs_early"], t1=i, t4=None, tw=0)
        elif cur is not None:
            if r["t"] == 4:
                cur["tw"] += 1
            if r["t"] == 5:
                cur["t4"] = i
    if cur is not None:
        out.append(cur)
    return out


def resume_gaps(acc):
    """For each EU data access (MEMR/MEMW), the gap to the next CODE fetch.
    Returns list of (data_ordinal, bus_index, tw_self, gap) where gap = idle
    clocks between the data access T4 and the next CODE-fetch T1."""
    out = []
    d = 0
    for i, a in enumerate(acc):
        if a["bs"] in (MEMR, MEMW):
            gap = None
            for j in range(i + 1, len(acc)):
                if acc[j]["bs"] == CODE:
                    if a["t4"] is not None:
                        gap = acc[j]["t1"] - a["t4"]
                    break
            out.append((d, i, a["tw"], gap))
            d += 1
    return out


def local_ctx(acc, bus_i, back=2, fwd=0):
    """Tw pattern of the bus cycles around bus index bus_i (the window that a
    bounded resume rule could depend on)."""
    lo, hi = max(0, bus_i - back), min(len(acc), bus_i + fwd + 1)
    return tuple(acc[j]["tw"] for j in range(lo, hi))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seed", type=int, default=90003)
    ap.add_argument("--nwseed", type=int, default=48)
    ap.add_argument("--wmax", type=int, default=1)
    ap.add_argument("--wbase", type=lambda x: int(x, 0), default=0x4000)
    ap.add_argument("--ord", type=int, default=-1,
                    help="focus on this data-access ordinal (default: auto-pick "
                         "the one most sensitive to its own wait)")
    ap.add_argument("--compare-core", action="store_true",
                    help="also run each wait-seed on the fabric core and report "
                         "ordinals where the model's resume gap != the chip's "
                         "(direct bug localization for Phase 2)")
    a = ap.parse_args()

    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)

    # run the SAME program under many wait-seeds on the chip
    runs = []       # list of (wseed, acc, gaps)
    coreruns = []
    for k in range(a.nwseed):
        ws = (a.wbase + k) & 0xFFFF
        rows = run_chip(image, a.host, use_core=False, waits=0, wrand=(a.wmax, ws))
        runs.append((ws, accesses(rows), resume_gaps(accesses(rows))))
        if a.compare_core:
            crows = run_chip(image, a.host, use_core=True, waits=0,
                             wrand=(a.wmax, ws))
            coreruns.append((ws, accesses(crows), resume_gaps(accesses(crows))))
    ndata = min(len(r[2]) for r in runs)
    print(f"program fz{a.seed}: {len(runs[0][1])} bus cycles, {ndata} EU data "
          f"accesses (stable anchor), {a.nwseed} wait-seeds @ wmax={a.wmax}",
          flush=True)

    # for each data ordinal, how much does the resume gap vary, and does it
    # track the access's own wait?
    print("\nper-ordinal gap sensitivity (gap = idle clocks data.T4 -> next CODE.T1):")
    best = None
    for d in range(ndata):
        by_self = defaultdict(list)   # tw_self -> [gap]
        for ws, acc, gaps in runs:
            _, bi, tw, gap = gaps[d]
            if gap is not None:
                by_self[tw].append(gap)
        if 0 in by_self and 1 in by_self:
            g0 = statistics.mean(by_self[0])
            g1 = statistics.mean(by_self[1])
            spread = statistics.pstdev([x for v in by_self.values() for x in v])
            delta = g1 - g0
            tag = ""
            if abs(delta) >= 1 and spread < 2.0:
                tag = "  <== clean single-wait response"
                if best is None or abs(delta) > abs(best[1]):
                    best = (d, delta, spread)
            print(f"  ord {d:3}: gap|w=0 mean={g0:.1f} (n={len(by_self[0])}) | "
                  f"gap|w=1 mean={g1:.1f} (n={len(by_self[1])}) | "
                  f"delta={delta:+.1f} spread={spread:.2f}{tag}", flush=True)

    # chip-vs-model resume-gap localization: for each (wait-seed, ordinal),
    # compare the chip's resume gap with the fabric core's. Ordinals with any
    # mismatch are where the model's prefetch-resume rule is wrong.
    if a.compare_core:
        print("\n=== chip-vs-MODEL resume-gap divergence (per ordinal) ===")
        nd = min(ndata, min(len(r[2]) for r in coreruns))
        bad_ord = {}
        for d in range(nd):
            mism = 0
            examples = []
            for (ws, _, cg), (_, _, kg) in zip(runs, coreruns):
                gc, gk = cg[d][3], kg[d][3]
                if gc is not None and gk is not None and gc != gk:
                    mism += 1
                    if len(examples) < 3:
                        examples.append((ws, gc, gk))
            if mism:
                bad_ord[d] = (mism, examples)
        if not bad_ord:
            print("  model matches chip on every resume gap (no divergence in "
                  "this program)")
        for d, (mism, ex) in sorted(bad_ord.items()):
            exs = "; ".join(f"ws{w:#06x}:chip{gc}/model{gk}" for w, gc, gk in ex)
            print(f"  ord {d:3}: {mism}/{a.nwseed} wait-seeds diverge "
                  f"(chip resume gap != model) | {exs}", flush=True)

    focus = a.ord if a.ord >= 0 else (best[0] if best else 0)
    print(f"\n=== MINIMAL-PAIR search at data ordinal {focus} ===", flush=True)
    # group runs by local wait context around the resume access; find two runs
    # whose context differs in exactly ONE position, with different gaps
    bi0 = runs[0][2][focus][1]
    ctx_map = defaultdict(list)   # local_ctx -> [(ws, gap)]
    for ws, acc, gaps in runs:
        _, bi, tw, gap = gaps[focus]
        if gap is None:
            continue
        ctx = local_ctx(acc, bi, back=3, fwd=1)
        ctx_map[ctx].append((ws, gap, tw))
    # consistency within identical context
    print("local Tw context (3 back .. 1 fwd of the resume access) -> gaps:")
    for ctx in sorted(ctx_map):
        gaps = [x[1] for x in ctx_map[ctx]]
        print(f"  ctx {ctx}: n={len(gaps)} gaps={sorted(set(gaps))} "
              f"{'CONSISTENT' if len(set(gaps))==1 else 'SCATTER'}", flush=True)
    # find a Hamming-1 pair of contexts with different gaps
    ctxs = list(ctx_map)
    found = False
    for i in range(len(ctxs)):
        for j in range(i + 1, len(ctxs)):
            ca, cb = ctxs[i], ctxs[j]
            if len(ca) != len(cb):
                continue
            diff = [p for p in range(len(ca)) if ca[p] != cb[p]]
            if len(diff) == 1:
                ga = statistics.mean([x[1] for x in ctx_map[ca]])
                gb = statistics.mean([x[1] for x in ctx_map[cb]])
                wa = ctx_map[ca][0]
                wb = ctx_map[cb][0]
                print(f"\n  MINIMAL PAIR: contexts differ only at window pos "
                      f"{diff[0]} ({ca[diff[0]]} vs {cb[diff[0]]}):")
                print(f"    A ctx={ca} wseed={wa[0]:#06x} gap~{ga:.1f}")
                print(f"    B ctx={cb} wseed={wb[0]:#06x} gap~{gb:.1f}")
                print(f"    => single-wait resume-gap shift = {gb-ga:+.1f} clocks")
                found = True
    if not found:
        print("  no Hamming-1 context pair found (need more wait-seeds or the "
              "resume window is wider than probed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
