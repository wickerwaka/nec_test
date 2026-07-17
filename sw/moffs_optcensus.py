#!/usr/bin/env python3
"""MOFFS eu_req=0 OPPORTUNITY census (Codex-required, before the S_MLO lead-veto).

Enumerate EVERY aligned decision cell where the model is at S_MLO with a MOFFS
access, eval_ext (waited window), and the low-addr byte popping (q_pop). At each,
classify the CHIP action vs the MODEL action at the immediately-following bus
opportunity:
    both CODE   = both prefetch (timing-clean prefetch) -> a lead veto here would
                  WRONGLY suppress a legal chip prefetch. MUST be zero for loads.
    both EU     = both reserve (timing-clean reserve) -> already correct.
    over        = model prefetched CODE, chip reserved (MEMR/MEMW) -> the target
                  cells the veto should fix.
    under       = model reserved, chip prefetched -> would refute the veto.

Broken down by opcode (A0/A1 loads vs A2/A3 stores = negative control) and by the
MOFFS access address parity. Chip = ground truth (use_core=0); model = TB
internals (== fabric), valid on the aligned prefix.

Usage: python3 sw/moffs_optcensus.py [--seeds ...] [--nws N] [--wmaxes ...]
"""
import sys, argparse, random as _r
from pathlib import Path
from collections import Counter, defaultdict
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _trunc, _sname, BSN,
                          MEMR, MEMW, CODE)

OPN = {0xA0: "A0.ld.b", 0xA1: "A1.ld.w", 0xA2: "A2.st.b", 0xA3: "A3.st.w"}


def wv_of(ws, wmax):
    return [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]


def census_one(seed, ws, wmax, host, image):
    wv = wv_of(ws, wmax)
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = _trunc(accesses(crel))
    ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                               ad_addr=x["addr"], ad_data=0) for x in kr]))
    cb, kb = bs_stream(ca), bs_stream(ka)
    # model bus index -> kr T1 row
    mt1 = {}; bi = -1
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1; mt1[bi] = ri
    t1rows = sorted(mt1.items())   # (busidx, row)
    hits = []
    for ri, x in enumerate(kr):
        if _sname(x["state"]) != "S_MLO" or x["eval_ext"] != 1 or x["q_pop"] != 1:
            continue
        opc = x["opc"]
        if opc not in OPN:
            continue
        # the following bus opportunity: first model bus index whose T1 row > ri
        B = next((bidx for bidx, row in t1rows if row > ri), None)
        if B is None or B >= min(len(cb), len(kb)):
            continue
        # require alignment strictly BEFORE B (the decision is uncontaminated)
        if any(cb[i] != kb[i] or ca[i]["addr"] != ka[i]["addr"]
               for i in range(1, B)):
            continue
        agree = (cb[B] == kb[B] and ca[B]["addr"] == ka[B]["addr"])
        # parity of the MOFFS EU access: the first model MEMR/MEMW at/after B
        euB = next((i for i in range(B, min(len(ka), B + 6))
                    if kb[i] in (MEMR, MEMW)), None)
        par = (ka[euB]["addr"] & 1) if euB is not None else -1
        if agree:
            kind = "both_CODE" if cb[B] == CODE else \
                   ("both_EU" if cb[B] in (MEMR, MEMW) else "both_other")
        else:
            if cb[B] in (MEMR, MEMW) and kb[B] == CODE:
                kind = "over"          # model over-prefetch (target)
            elif cb[B] == CODE and kb[B] in (MEMR, MEMW):
                kind = "under"         # model over-reserve (refutes veto)
            else:
                kind = "other_div"
        hits.append(dict(opc=opc, kind=kind, par=par, B=B,
                         chip=BSN.get(cb[B], cb[B]), model=BSN.get(kb[B], kb[B]),
                         addr=ca[B]["addr"] if B < len(ca) else 0))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=list(range(90000, 90040)))
    ap.add_argument("--nws", type=int, default=6)
    ap.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    a = ap.parse_args()
    allhits = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                try:
                    allhits += census_one(seed, ws, wmax, a.host, image)
                except Exception as e:
                    print(f"  fz{seed} ws{ws} wmax{wmax}: ERR {e}")
    print(f"\n=== MOFFS opportunity census: {len(allhits)} aligned "
          f"eval_ext+S_MLO+q_pop cells ===")
    by_opc = defaultdict(Counter)
    for h in allhits:
        by_opc[h["opc"]][h["kind"]] += 1
    print("\nBy opcode x outcome:")
    for opc in sorted(by_opc):
        c = by_opc[opc]
        total = sum(c.values())
        print(f"  {OPN[opc]:>9} (n={total:3d}): " +
              "  ".join(f"{k}={c[k]}" for k in
                        ["both_CODE", "both_EU", "over", "under", "other_div"]
                        if c[k]))
    print("\nBy opcode x parity x outcome:")
    byp = defaultdict(Counter)
    for h in allhits:
        byp[(h["opc"], h["par"])][h["kind"]] += 1
    for (opc, par) in sorted(byp):
        c = byp[(opc, par)]
        print(f"  {OPN[opc]:>9} par{par}: " +
              "  ".join(f"{k}={c[k]}" for k in
                        ["both_CODE", "both_EU", "over", "under", "other_div"]
                        if c[k]))
    # the decisive safety check
    load_bothcode = sum(1 for h in allhits
                        if h["opc"] in (0xA0, 0xA1) and h["kind"] == "both_CODE")
    load_under = sum(1 for h in allhits
                     if h["opc"] in (0xA0, 0xA1) and h["kind"] == "under")
    print(f"\nSAFETY (loads A0/A1): timing-clean both_CODE cells = {load_bothcode} "
          f"(MUST be 0 for a safe S_MLO lead veto); under cells = {load_under} "
          f"(MUST be 0)")


if __name__ == "__main__":
    main()
