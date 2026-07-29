#!/usr/bin/env python3
"""B3 — wvec-directed law fitting (grid-term, held-out validated).

Re-captures the waited family retaining every signed gap-error impulse with its
grid-observable context, then FITS + HELD-OUT-VALIDATES two laws the census
flags:
  (1) prev_tw SIGN-FLIP law (CODE->CODE): the resume gap-error sign is a function
      of prev_tw (the Tw-stretch of the completing bus cycle = the two-rhythm beat
      phase in grid terms). t33-v2 R1 found prev_tw=0 -> negative, prev_tw>=1 ->
      positive. Fit signed-mean per prev_tw on even-k seeds, predict sign on
      odd-k; report the flip + mass explained by prev_tw ALONE.
  (2) EU-ACCESS block (CODE->EU / EU->CODE / EU->EU): richer grid key
      (prev_tw, cur_tw, prev_bs) held-out sign prediction -> mass explained.

Grid framing: prev_tw/cur_tw are the per-cycle Tw stretches (the stretched-grid
phase the rebuild makes first-class); the laws are expressed over them, not over
model-internal occ/eval_ext (those are the Stage-D shadow frame).

Board for capture; fitting board-free. Impulses saved to mc1_refix/impulses.jsonl.
Usage: nohup setsid python3 -u sw/b3_fit.py > sw/b3_fit.log 2>&1 &
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


def imp_of(real, sim, k):
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
        out.append(dict(k=k, cell="%s->%s" % (kindof(ca[i - 1]["bs"]),
                                               kindof(ca[i]["bs"])),
                        prev_bs=ca[i - 1]["bs"], cur_bs=ca[i]["bs"],
                        prev_tw=ca[i - 1]["tw"], cur_tw=ca[i]["tw"], ge=ge))
    return out


def board_idle():
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)


def capture_all():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    fam = [r for r in rows if waited(r) and
           (r.get("verdict") == "TIMING" or r.get("sub") == "done_mismatch")]
    board_idle()
    allimp = []
    consec = err = done = 0
    t0 = time.time()
    for r in fam:
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
            consec = 0
        except Exception as e:
            err += 1
            consec += 1
            if consec >= STORM:
                print(f"=== B3_WEDGE_STOP consec={consec} k={k} ===", flush=True)
                board_idle()
                sys.exit(2)
            continue
        allimp.extend(imp_of(chip, core, k))
        done += 1
        if done % 400 == 0:
            print(f"  ... {done}/{len(fam)} ({time.time()-t0:.0f}s, {err} err)", flush=True)
    board_idle()
    print(f"captured {done} seeds, {len(allimp)} impulses, {err} runerr", flush=True)
    return allimp


def heldout(imps, keyfn):
    """train signed-mean per key on even-k, predict sign on odd-k. -> (acc,
    majority, mass_fittable, n_test)."""
    model = defaultdict(lambda: [0, 0])
    tr = [x for x in imps if x["k"] % 2 == 0]
    te = [x for x in imps if x["k"] % 2 == 1]
    for x in tr:
        model[keyfn(x)][0] += x["ge"]
        model[keyfn(x)][1] += 1
    prior = 1 if sum(1 for x in tr if x["ge"] > 0) >= len(tr) / 2 else -1
    correct = maj = mass_tot = mass_hit = 0
    for x in te:
        m = model.get(keyfn(x))
        pred = (1 if m[0] > 0 else -1) if (m and m[1] >= 3 and m[0] != 0) else prior
        if (x["ge"] > 0) == (pred > 0):
            correct += 1
            mass_hit += abs(x["ge"])
        if (x["ge"] > 0) == (prior > 0):
            maj += 1
        mass_tot += abs(x["ge"])
    n = len(te)
    return (round(100*correct/max(1, n), 1), round(100*maj/max(1, n), 1),
            round(100*mass_hit/max(1, mass_tot), 1), n)


def main():
    print(f"=== B3 LAW FITTING {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===", flush=True)
    imps = capture_all()
    with open(OUT / "impulses.jsonl", "w") as fh:
        for x in imps:
            fh.write(json.dumps(x) + "\n")

    cc = [x for x in imps if x["cell"] == "CODE->CODE"]
    print("\n=== LAW 1: prev_tw SIGN-FLIP (CODE->CODE, grid beat phase) ===", flush=True)
    bucket = defaultdict(lambda: [0, 0])
    for x in cc:
        b = min(x["prev_tw"], 3)
        bucket[b][0] += x["ge"]
        bucket[b][1] += 1
    for b in sorted(bucket):
        s, n = bucket[b]
        print(f"  prev_tw={b}{'+' if b == 3 else ' '}: n={n:5d} signed-mean ge="
              f"{s/max(1,n):+.2f}  (sign {'+' if s > 0 else '-'})")
    acc, maj, mf, n = heldout(cc, lambda x: min(x["prev_tw"], 3))
    print(f"  HELD-OUT (prev_tw ALONE): sign acc={acc}% (majority {maj}%), "
          f"mass-fittable={mf}%  n={n}")

    print("\n=== LAW 2: EU-ACCESS block (grid key prev_tw,cur_tw,prev_bs) ===", flush=True)
    res = {}
    for cell in ("CODE->EU", "EU->CODE", "EU->EU"):
        ci = [x for x in imps if x["cell"] == cell]
        acc, maj, mf, n = heldout(ci, lambda x: (min(x["prev_tw"], 3),
                                                 min(x["cur_tw"], 3), x["prev_bs"]))
        res[cell] = dict(acc=acc, majority=maj, mass_fittable=mf, n=n)
        print(f"  {cell:<10} held-out sign acc={acc}% (majority {maj}%), "
              f"mass-fittable={mf}%  n={n}")

    (OUT / "b3_laws.json").write_text(json.dumps(
        dict(prev_tw_flip={str(b): dict(n=bucket[b][1],
                                        mean=round(bucket[b][0]/max(1, bucket[b][1]), 2))
                           for b in sorted(bucket)},
             eu_access=res), indent=1) + "\n")
    print("\n=== B3_FIT_DONE ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
