#!/usr/bin/env python3
"""evtdbg -- S9b diagnostic: one EVT seed, chip rows vs timed-sim rows, with the
replay directive and the acknowledge position printed.  NOT a gate."""
import gzip
import json
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

BS = fc.BS_NAME
T = fc.T_NAME
QS = fc.QS_NAME


def find(cid, k):
    for p in sorted((ROOT / "tests/v30/fuzz_bank" / cid / "seeds").glob("*.json.gz")):
        if p.name.split("_")[1] == str(k):
            return p
    raise SystemExit(f"no seed {cid}/{k}")


def row(r):
    return (f"t={T.get(r.get('t_state', r.get('t')))!s:<3} "
            f"bs={BS[r['bs_early']]:<5} qs={QS[r['qs']]:<3} "
            f"a={r['ad_addr']:05x} d={r['ad_data']:04x} u={r['ube_n']} "
            f"ps={r['ps']:x}")


def main():
    cid, k = sys.argv[1], int(sys.argv[2])
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    entry = json.loads(gzip.decompress(find(cid, k).read_bytes()))
    image, meta, g, sha = uf.regen(entry)
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    evt = tf.evt_directive(entry, meta, recs, win)
    print(f"seed {cid}/{k}  waits={entry.get('waits')} evt_axis={entry.get('evt')}")
    print(f"  directive {json.dumps(evt)}")
    cstream = uf.chip_stream(recs, win)
    print(f"  chip stream {len(cstream)} events, window {win}/{len(recs)}")
    # where the acknowledge stands in ROWS
    txns = [t for t in fc.extract_txns(recs)]
    for i, t in enumerate(txns):
        if fc.KIND[t["kind"]] in ("INTA", "HALT"):
            print(f"  chip {fc.KIND[t['kind']]} txn#{i} at row {t['start']}")
    with tempfile.TemporaryDirectory() as td:
        rows, err = tf.run_sim(image, entry, len(recs), td, evt)
    if err:
        print("  stderr:", err.strip())
    dr = fc.diff_rows(recs, rows)
    print(f"  n={dr.n} ndiff={len(dr.rows)} first_bad="
          f"{dr.rows[0].i if dr.rows else '-'}")
    if not dr.rows:
        return
    i0 = dr.rows[0].i
    bad = {d.i for d in dr.rows}
    for i in range(max(0, i0 - ctx), min(dr.n, i0 + ctx)):
        mark = "*" if i in bad else " "
        s = rows[i] if i < len(rows) else None
        print(f"{mark}{i:5d}  CHIP {row(recs[i])}   SIM "
              f"{row(s) if s else '-'}")


main()
