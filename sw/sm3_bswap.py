#!/usr/bin/env python3
"""sm3_bswap -- the T8 byte-swap probe (SM3 item 2.1).

§49.7 records four banked seeds on which the ucore and the C++ model AGREE with
each other and DISAGREE with the socket, three of them an exact byte swap on a
write.  §T.8 attributes them to M5b's A0 rotator (`BiuTimed::mem_write`'s
`swap8` on `a & 1`).  M5b was itself MEASURED, on four quadrants -- so before
anything is changed the two populations have to be put side by side.

This tool prints, for a named seed, the chip rows and the engine rows around the
divergent write, with the write's own bus cycle decomposed: base address, A0,
UBE, split-or-not, and the datapath value the model handed the swapper.

OFFLINE, board-free.  A measurement, not a gate.

  sm3_bswap.py --seed tests/v30/fuzz_bank/mc1/seeds/raw_2340_*.json.gz --core ucore
"""
import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
import timed_fuzz as tf                                 # noqa: E402
import ucsim_fuzz as uf                                 # noqa: E402

BS = fc.BS_NAME
T = {1: "T1", 2: "T2", 3: "T3", 4: "T4", 5: "Ti", 6: "Tw"}


def rowstr(r):
    return (f"{T.get(r.get('t_state', r.get('t')), '?'):>2} "
            f"{BS[r['bs_early']]:<5} a={r['ad_addr']:05x} d={r['ad_data']:04x} "
            f"ube={r['ube_n']} qs={r['qs']} ps={r.get('ps', 0):x}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", required=True)
    ap.add_argument("--core", default="ucore", choices=["sim", "ucore", "fsm"])
    ap.add_argument("--ctx", type=int, default=10)
    a = ap.parse_args()

    p = Path(a.seed)
    entry = json.loads(gzip.decompress(p.read_bytes()))
    image, meta, _g, _sha = uf.regen(entry)
    chip = entry["chip_rows"]
    win = uf.window_of(chip)
    with tempfile.TemporaryDirectory() as td:
        if a.core == "sim":
            evt = (tf.evt_directive(entry, meta, chip, win)
                   if entry.get("evt") else None)
            rows, err = tf.run_sim(image, entry, len(chip), td, evt)
        else:
            evt = tf.evt_tuple(entry, meta, "banked") if entry.get("evt") else None
            rows, err = tf.run_tb(image, entry, len(chip), td, a.core, evt)
    dr = fc.diff_rows(chip, rows)
    print(f"{p.name}  core={a.core}  err={err}  n={dr.n}  ndiff={len(dr.rows)}")
    if not dr.rows:
        print("  NOW EXACT")
        return 0
    fb = dr.rows[0].i
    print(f"  first divergence row {fb}")
    lo, hi = max(0, fb - a.ctx), min(dr.n, fb + a.ctx + 1)
    print(f"\n  {'row':>5}  {'CHIP':<52}  {'ENGINE':<52}")
    for i in range(lo, hi):
        c = rowstr(chip[i]) if i < len(chip) else "-"
        s = rowstr(rows[i]) if i < len(rows) else "-"
        mark = " <<<" if i == fb else ("  * " if c != s else "    ")
        print(f"  {i:>5}{mark}{c:<52}  {s:<52}")

    # the enclosing bus cycle of the divergence, chip side
    for j in range(fb, -1, -1):
        if chip[j].get("t_state", chip[j].get("t")) == 1:
            print(f"\n  enclosing chip cycle: T1 at row {j}  "
                  f"{BS[chip[j]['bs_early']]}  addr={chip[j]['ad_addr']:05x}  "
                  f"A0={chip[j]['ad_addr'] & 1}  ube_n={chip[j]['ube_n']}")
            break
    # ...and the preceding T1s, so a SPLIT is visible as two cycles
    t1s = [i for i in range(max(0, fb - 40), min(dr.n, fb + 8))
           if i < len(chip) and chip[i].get("t_state", chip[i].get("t")) == 1]
    print("  chip T1s nearby: " + "  ".join(
        f"{i}:{BS[chip[i]['bs_early']]}@{chip[i]['ad_addr']:05x}"
        f"/u{chip[i]['ube_n']}" for i in t1s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
