#!/usr/bin/env python3
"""B2 — per-cell held-out PREDICTABILITY targets (the P1-frozen TARGET numbers).

Re-captures the waited family on the current fabric (like B1) but retains every
signed inter-T1 gap-error IMPULSE with its bus-observable context tuple, then
runs the t33_scattertest held-out test PER KIND CELL: train the conditional
signed mean on half the seeds, predict the impulse sign on the held-out half, and
report per-cell (a) held-out sign accuracy vs the majority baseline and (b) the
fraction of |ge| mass whose sign is correctly predicted (= the fittable share).
These per-cell numbers are the rebuild's per-cell TARGETs (frozen at P1); the
rebuild must meet or beat them.

Context tuple (bus-observable only, per the t33-v2 R1 method): (prev_bs, cur_bs,
prev_tw, cur_tw, prev_prev_bs). Board for the capture; analysis board-free.

Usage: nohup setsid python3 -u sw/b2_predict.py > sw/b2_predict.log 2>&1 &
"""
import sys
import json
import time
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import fuzz_campaign as fzc                          # noqa: E402
import check_seq                                     # noqa: E402
import testimage                                     # noqa: E402
from causal_wrand import accesses, CODE              # noqa: E402
from class5_align import align                       # noqa: E402

HOST = "root@mister-nec"
RESULTS = ROOT / "sw/testdata/campaigns/mc1/results.jsonl"
OUT = ROOT / "sw/testdata/campaigns/mc1_refix"
STORM = 25


def waited(r):
    w = r.get("waits") or {}
    return bool(w.get("wrand")) or (w.get("fixed") or 0) > 0


def kindof(bs):
    return "CODE" if bs == CODE else "EU"


def impulses(real, sim):
    """-> list of (cell, ctx_tuple, signed_ge) for one seed."""
    rel = next((i for i, x in enumerate(real) if not x.get("rst")), 0)
    ca = accesses(real[rel:])
    ka = accesses(sim)
    if len(ca) < 4 or len(ka) < 4:
        return []
    try:
        pairs, _e, _s = align(ca, ka)
    except Exception:
        return []
    kmap = {ci: ki for ci, ki in pairs}
    out = []
    for i in sorted(kmap):
        if i < 2 or (i - 1) not in kmap:
            continue
        ki, kip = kmap[i], kmap[i - 1]
        ge = (ca[i]["t1"] - ca[i - 1]["t1"]) - (ka[ki]["t1"] - ka[kip]["t1"])
        if not ge:
            continue
        cell = "%s->%s" % (kindof(ca[i - 1]["bs"]), kindof(ca[i]["bs"]))
        ctx = (ca[i - 1]["bs"], ca[i]["bs"], ca[i - 1]["tw"], ca[i]["tw"],
               ca[i - 2]["bs"])
        out.append((cell, ctx, ge))
    return out


def board_idle():
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)


def main():
    t0 = time.time()
    print(f"=== B2 PREDICTABILITY capture {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===", flush=True)
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    fam = [r for r in rows if waited(r) and
           (r.get("verdict") == "TIMING" or r.get("sub") == "done_mismatch")]
    board_idle()
    # per-cell: train/test impulse lists (split by seed parity)
    imp = {"train": defaultdict(list), "test": defaultdict(list)}
    consec_err = runerr = done = 0
    for idx, r in enumerate(fam):
        k = r["k"]
        w = r["waits"]
        wr = (w["wmax"], w["wseed"]) if w.get("wrand") else None
        try:
            g = fzc.build(fzc.derive_case(r.get("cid", "mc1"), k,
                                          {"force_contained": True, "strict": True}))
            image, _ = check_seq.compose(g)
        except Exception:
            continue
        try:
            if wr:
                chip = check_seq.run_chip(image, HOST, use_core=False, wrand=wr)
                core = check_seq.run_chip(image, HOST, use_core=True, wrand=wr)
            else:
                chip = check_seq.run_chip(image, HOST, use_core=False, waits=w["fixed"])
                core = check_seq.run_chip(image, HOST, use_core=True, waits=w["fixed"])
            consec_err = 0
        except Exception as e:
            runerr += 1
            consec_err += 1
            if consec_err >= STORM:
                print(f"=== B2_WEDGE_STOP consec={consec_err} seed={k} ===", flush=True)
                board_idle()
                return 2
            continue
        split = "train" if (k % 2 == 0) else "test"
        for cell, ctx, ge in impulses(chip, core):
            imp[split][cell].append((ctx, ge))
        done += 1
        if done % 300 == 0:
            print(f"  ... {done}/{len(fam)} ({time.time()-t0:.0f}s, {runerr} err)", flush=True)
    board_idle()
    print("board idle (session end)", flush=True)

    # train conditional signed mean per (cell, ctx); predict on held-out
    print("\n=== B2 PER-CELL HELD-OUT PREDICTABILITY (P1 TARGETs) ===", flush=True)
    result = {}
    for cell in ("CODE->CODE", "EU->CODE", "CODE->EU", "EU->EU"):
        model = defaultdict(lambda: [0, 0])   # ctx -> [sum_ge, n]
        for ctx, ge in imp["train"][cell]:
            model[ctx][0] += ge
            model[ctx][1] += 1
        # global sign prior (majority) from train
        allge = [ge for _, ge in imp["train"][cell]]
        prior = 1 if sum(1 for g in allge if g > 0) >= len(allge) / 2 else -1
        # predict on test
        correct = 0
        mass_tot = mass_hit = 0
        maj = 0
        for ctx, ge in imp["test"][cell]:
            m = model.get(ctx)
            pred = (1 if m[0] > 0 else -1 if m[0] < 0 else prior) if m and m[1] >= 3 else prior
            if (ge > 0) == (pred > 0):
                correct += 1
                mass_hit += abs(ge)
            mass_tot += abs(ge)
            if (ge > 0) == (prior > 0):
                maj += 1
        n = len(imp["test"][cell])
        acc = 100 * correct / max(1, n)
        majb = 100 * maj / max(1, n)
        fittable = 100 * mass_hit / max(1, mass_tot)
        result[cell] = dict(n_test=n, acc=round(acc, 1), majority=round(majb, 1),
                            mass_fittable=round(fittable, 1), mass_test=mass_tot)
        print(f"  {cell:<11} n={n:6d}  held-out sign acc={acc:4.1f}% "
              f"(majority {majb:4.1f}%)  mass-fittable={fittable:4.1f}% "
              f"(of {mass_tot} test |ge|)")
    (OUT / "b2_targets.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"\n=== B2_PREDICT_DONE  ({time.time()-t0:.0f}s, runerr={runerr}) ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
