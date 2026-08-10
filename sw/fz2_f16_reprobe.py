#!/usr/bin/env python3
"""fz2_f16_reprobe -- F15 s5.1-style reproducibility probe for the TWO seeds
that ENTERED the ledger at FLASH #16 (P-5 miss).  Safe and isolated: it does
NOT touch the banked corpus; it re-derives each seed's stratum config, captures
it N times on the resident FLASH #16 bitstream through the capture driver's own
path, and reports whether the SOCKET (chip) leg reproduces across the repeats
and which banked trajectory (F15 vs F16) each fresh capture matches.

The banked figure is the figure (F15 s5.2).  This is a DIAGNOSIS of the miss,
not a replacement for it.  div_guard on both sides.
"""
import argparse
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fz2_w1 as w1
import fuzz_campaign as fzc
import fuzz_classify as fc

SEEDS = ["fz2e/513017", "fz2e/534041"]
HOST = "root@mister-nec"


def stratum_for(cid, k):
    for st in w1.STRATA:
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return st
    raise SystemExit(f"no stratum for {cid} {k}")


def banked_chip(cid, k, suffix):
    """The banked SOCKET rows for one seed out of a campaign's captures."""
    d = os.path.join(fzc.CAMPAIGNS, cid + suffix, "results.jsonl")
    row = None
    for ln in open(d):
        ln = ln.strip()
        if ln:
            r = json.loads(ln)
            if r["seed"] == f"{cid}/{k}":
                row = r
                break
    if not row:
        return None, None
    cap = os.path.join(fzc.CAMPAIGNS, cid + suffix, "captures",
                       os.path.basename(row["cid"] if False else ""), )
    return row, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    a = ap.parse_args()
    dg = []
    w1.div_guard("reprobe-start", dg)
    for sid in SEEDS:
        cid, ks = sid.split("/")
        k = int(ks)
        st = stratum_for(cid, k)
        ov = w1.ov_of(st)
        cfg = fzc.derive_case(cid, k, ov)
        g = fzc.build(cfg)
        image, meta = fzc.compose_case(g, cfg)
        print(f"\n==== {sid}  stratum {w1.label(st)}  ov={ov} ====")
        reps = []
        for i in range(a.reps):
            real, sim, e = fzc.capture_board(image, meta, cfg, HOST)
            if e:
                print(f"  rep {i}: ERROR {e}")
                continue
            reps.append((real, sim))
        if len(reps) < 2:
            print("  too few good reps to compare")
            continue
        # reproducibility across the fresh repeats (chip leg)
        base = reps[0][0]
        agree = 0
        for j in range(1, len(reps)):
            d = fc.diff_rows(base, reps[j][0])
            print(f"  rep0 vs rep{j} (chip): bad={d.bad} flick={d.flick} "
                  f"first={d.first}  n={d.n}")
            agree += (d.bad == 0)
        print(f"  chip reproducibility: {agree}/{len(reps)-1} repeats identical "
              f"to rep0 on scored rows")
        # arch dump of each fresh rep (chip)
        dumps = [fc.arch_dump(r[0], min(len(r[0]), 4000)) for r in reps]
        arch_stable = all(dj == dumps[0] for dj in dumps)
        print(f"  arch dump stable across reps: {arch_stable}")
        if not arch_stable:
            for i, dmp in enumerate(dumps):
                print(f"    rep{i} arch: AW={dmp.get('AW')} PC={dmp.get('PC')} "
                      f"PS={dmp.get('PS')}")
        else:
            print(f"    arch AW={dumps[0].get('AW')} PC={dumps[0].get('PC')} "
                  f"PS={dumps[0].get('PS')}")
        # which banked trajectory does rep0 match?  compare against F15 and F16
        for suf, name in (("-F15-archive", "F15 banked (good)"),
                          ("", "F16 banked (anomalous)")):
            row, _ = banked_chip(cid, k, suf)
            if row:
                print(f"    banked {name}: verdict={row.get('verdict')} "
                      f"bad_rows={row.get('bad_rows')} "
                      f"chip AW={row.get('arch_words',{}).get('AW')} "
                      f"term_fired={row.get('term',{}).get('fired')}")
    w1.div_guard("reprobe-end", dg)
    unp = [x for x in dg if x.get("state") != "PINNED"]
    print(f"\n  div_guards {len(dg)}, unpinned {len(unp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
