#!/usr/bin/env python3
"""Flash-acceptance for the eu_req=0 store-stage fix (session 019f663c).

Directly compares the socketed CHIP (use_core=0, ground truth), the flashed
FABRIC (use_core=1, the synthesized patched RTL), and the Verilator TB (the RTL
source) on the eu_req=0 store vector and controls. Reports the first
(BUS TYPE, ADDRESS) divergence for chip-vs-fabric AND fabric-vs-TB.

Codex 6-point acceptance (store):
  1. the doomed CODE at the store's post-EA cycle disappears in FABRIC (== chip)
  2. FABRIC issues MEMW at the exact chip bus index (same idle count, same order)
  3. FABRIC == patched TB (no synthesis surprise)
  4/5/6. controls + held-out: no NEW chip-CODE / fabric-IDLE divergence
"""
import sys, random as _r
from pathlib import Path
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _trunc, BSN, MEMR, MEMW, CODE)

# (seed, ws, wmax) triples: the store case + a few controls / held-out
CASES = [
    (90015, 10, 7),   # the eu_req=0 store doomed-prefetch case (was class-1)
    (90003,  1, 3),   # control (fitting)
    (90042, 10, 7),   # control (fitting, class-5 seed - must be UNCHANGED)
    (91000,  1, 1),   # held-out
    (91003,  3, 3),   # held-out
]


def wv_of(ws, wmax):
    return [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]


def first_div(a, b):
    n = min(len(a), len(b))
    ba, bb = bs_stream(a), bs_stream(b)
    for i in range(n):
        if ba[i] != bb[i] or a[i]["addr"] != b[i]["addr"]:
            return i
    return None


def main():
    host = "root@mister-nec"
    for seed, ws, wmax in CASES:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        wv = wv_of(ws, wmax)
        cr = run_chip(image, host, use_core=False, wvec=wv)
        fr = run_chip(image, host, use_core=True, wvec=wv)
        kr = run_tb_internal(image, 4200, wv)
        crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
        frel = fr[next(i for i, r in enumerate(fr) if not r["rst"]):]
        ca = _trunc(accesses(crel))
        fa = _trunc(accesses(frel))
        ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                   ad_addr=x["addr"], ad_data=0) for x in kr]))
        cf = first_div(ca, fa)   # chip vs fabric
        ft = first_div(fa, ka)   # fabric vs TB
        tag = f"fz{seed} ws{ws} wmax{wmax}"
        print(f"\n### {tag}")
        print(f"  chip-vs-FABRIC first div: "
              + ("NONE (match)" if cf is None else
                 f"bus {cf}: chip={BSN.get(ca[cf]['bs'])}@{ca[cf]['addr']:05x} "
                 f"fab={BSN.get(fa[cf]['bs'])}@{fa[cf]['addr']:05x}"))
        print(f"  FABRIC-vs-TB   first div: "
              + ("NONE (match)" if ft is None else
                 f"bus {ft}: fab={BSN.get(fa[ft]['bs'])}@{fa[ft]['addr']:05x} "
                 f"tb={BSN.get(ka[ft]['bs'])}@{ka[ft]['addr']:05x}"))
        # for the store case, show the window around bus 37 on all three
        if seed == 90015:
            print("  window [bus: chip / fabric / tb]:")
            for B in range(34, 42):
                def cell(s):
                    return (f"{BSN.get(s[B]['bs']):<4}@{s[B]['addr']:05x}"
                            if B < len(s) else "----")
                mark = " <== was doomed CODE" if B == 37 else ""
                print(f"    {B:3d}: {cell(ca)} / {cell(fa)} / {cell(ka)}{mark}")


if __name__ == "__main__":
    main()
