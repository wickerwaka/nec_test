#!/usr/bin/env python3
"""sm3_h1probe -- a MEASUREMENT tool (never a gate) for H1, the re-entry
acknowledge's lead-in.

Replays one banked seed through the chip capture, the C++ timed model and an
RTL core, and prints the three columns side by side around a chosen row, with
the model's own `V30SIM_EVTTRACE` lines (anchor / A / B / entry) interleaved.

  sm3_h1probe.py <seed.json.gz> [--at N] [--span 24] [--core ucore]
"""
import argparse
import gzip
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc          # noqa: E402
import ucsim_fuzz as uf             # noqa: E402
import timed_fuzz as tf             # noqa: E402
import sm3_ackgeom as ag            # noqa: E402


def row_txt(r):
    if r is None:
        return " " * 42
    return (f"{fc.T_NAME[r.get('t_state', r.get('t'))]:2s} "
            f"{fc.BS_NAME[r['bs_early']]:5s} {fc.QS_NAME[r['qs']]} "
            f"a={r['ad_addr']:05x} d={r['ad_data']:04x} ps={r['ps']:x} "
            f"u={r['ube_n']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--at", type=int, default=-1)
    ap.add_argument("--span", type=int, default=24)
    ap.add_argument("--core", default="ucore")
    ap.add_argument("--ack", type=int, default=0,
                    help="centre on the Nth acknowledge (1-based) instead")
    ap.add_argument("--no-tb", action="store_true")
    a = ap.parse_args()

    entry = json.loads(gzip.decompress(Path(a.seed).read_bytes()))
    image, meta, g, sha = uf.regen(entry)
    assert sha == entry["image_sha256"], "GEN DRIFT"
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    print(f"seed {a.seed}\n  evt={entry.get('evt')} waits={entry.get('waits')} "
          f"rows={len(recs)} window={win}")

    with tempfile.TemporaryDirectory() as td:
        evt = tf.evt_directive(entry, meta, recs, win)
        os.environ["V30SIM_EVTTRACE"] = "1"
        srows, serr = tf.run_sim(image, entry, len(recs), td, evt)
        print("  evt directive at=", evt["at"], "cs=", evt["cs"], "ip=", evt["ip"])
        for ln in serr.splitlines():
            print("  SIM: " + ln)
        trows = []
        if not a.no_tb:
            ev = tf.evt_tuple(entry, meta)
            trows, terr = tf.run_tb(image, entry, len(recs), td, a.core, ev)
            if terr:
                print("  TB: " + terr[:300])

    centre = a.at
    if a.ack:
        cy, ak = ag.acks(recs, win)
        if a.ack <= len(ak):
            centre = cy[ak[a.ack - 1][0]][1]
    if centre < 0:
        centre = win // 2
    lo = max(0, centre - a.span)
    hi = min(len(recs), centre + a.span)
    print(f"{'i':>5}  {'CHIP':<42} {'SIM':<42} {a.core.upper()}")
    for i in range(lo, hi):
        c = recs[i] if i < len(recs) else None
        s = srows[i] if i < len(srows) else None
        t = trows[i] if i < len(trows) else None
        print(f"{i:5d}  {row_txt(c)} | {row_txt(s)} | {row_txt(t)}")


if __name__ == "__main__":
    main()
