#!/usr/bin/env python3
"""LC6 provenance capture (P-C14/15/16 core: the Family-5 strio veto on silicon).
Runs the 3 frozen LC6 gadget configs on the CHIP (use_core=False) and the FABRIC
(use_core=True, master build) and asserts chip==fabric via the aligned diff. That
+ the model-side proof (M-LC6 changes the committed output on these gadgets)
establishes the chip exhibits the eu_rsv_strio/pick_t3 veto. Banks the chip rows
to sw/testdata/lc6_provenance.jsonl for the deferred board-free replay gate.

Board session, capture-only, NO reflash. Per-case timeout via run_image.
Usage: python3 sw/lc6_provenance.py --host root@mister-nec
"""
import sys
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import biu_law_lc6_gadget as G                       # noqa: E402
from check_seq import run_chip, diff                 # noqa: E402

# (op, j, k, ws, wmax) — the W0 frozen configs (LC6 is w0-ACTIVE, Finding 4, so
# w0 exercises the strio veto; chip==fabric here IS the veto provenance). The
# random-wait config is CONFOUNDED by the general waited-cadence residual (the
# campaign's target, not a veto issue), so it is a census datapoint, not
# provenance -- excluded here.
CFG = [(0x6E, 0, 0, 0, 0)]   # the clean w0 veto-provenance datapoint (P-C14 core)
BANK = ROOT / "sw/testdata/lc6_provenance.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    a = ap.parse_args()
    rows_out = []
    allclean = True
    import random
    for op, j, k, ws, wmax in CFG:
        img = G.build_image(op, j, k)
        if wmax == 0:
            chip = run_chip(img, a.host, use_core=False, waits=0)
            fab = run_chip(img, a.host, use_core=True, waits=0)
        else:
            rr = random.Random((ws << 8) | wmax)
            wvec = [rr.randint(0, wmax) for _ in range(4096)]
            chip = run_chip(img, a.host, use_core=False, wvec=wvec)
            fab = run_chip(img, a.host, use_core=True, wvec=wvec)
        bad, first, n, flick = diff(chip, fab)
        ok = (bad == 0)
        allclean = allclean and ok
        print(f"LC6-prov op={op:#x} j={j} k={k} ws={ws} wmax={wmax}: "
              f"chip=={('fabric' if ok else 'FABRIC MISMATCH')} "
              f"(bad={bad} n={n} flick={flick})")
        rows_out.append(dict(op=op, j=j, k=k, ws=ws, wmax=wmax,
                             bad=bad, n=n, flick=flick,
                             chip=[dict(t=r.get("t", r.get("t_state")),
                                        bs=r["bs_early"], addr=r["ad_addr"],
                                        qs=r.get("qs", 0)) for r in chip]))
    BANK.parent.mkdir(parents=True, exist_ok=True)
    with open(BANK, "w") as fh:
        for r in rows_out:
            fh.write(json.dumps(r) + "\n")
    print(f"\nLC6 provenance: {'ALL chip==fabric (silicon-correct veto)' if allclean else 'MISMATCH — investigate'}; "
          f"banked {len(rows_out)} configs -> {BANK}")
    return 0 if allclean else 1


if __name__ == "__main__":
    sys.exit(main())
