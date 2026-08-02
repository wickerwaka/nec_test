#!/usr/bin/env python3
"""q2dump -- side-by-side per-clock rows around a fuzz seed's first divergence,
chip and model, with the flush/redirect landmarks marked.  Diagnostic only."""

import gzip
import json
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc             # noqa: E402
import ucsim_fuzz as uf                # noqa: E402
import timed_fuzz as tf                # noqa: E402

T_STR = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
Q_STR = {0: "-", 1: "F", 2: "E", 3: "S"}


def fmt(r):
    if r is None:
        return " " * 30
    return (f"{T_STR[r['t']]:<3}{BUS_STR[r['bs_early']]:<5}"
            f"{Q_STR[r['qs']]:<2}{r['ad_addr']:05x} {r['ad_data']:04x}")


def main():
    path = sys.argv[1]
    span = int(sys.argv[2]) if len(sys.argv) > 2 else 18
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    image, meta, g, sha = uf.regen(entry)
    recs = entry["chip_rows"]
    with tempfile.TemporaryDirectory() as td:
        rows, err = tf.run_sim(image, entry, len(recs), td)
    dr = fc.diff_rows(recs, rows)
    i0 = dr.rows[0].i if dr.rows else 0
    print(f"# {path}")
    print(f"# waits={entry.get('waits')}  first_bad={i0}  n={dr.n}")
    lo, hi = max(0, i0 - span), min(len(recs), i0 + span // 2)
    print("  idx   CHIP                            MODEL")
    for i in range(lo, hi):
        c = recs[i] if i < len(recs) else None
        s = rows[i] if i < len(rows) else None
        mark = "<<<" if i == i0 else ("   " if (c and s and
                                                fmt(c) == fmt(s)) else " * ")
        print(f"  {i:>5} {fmt(c):<32}{fmt(s):<32}{mark}")


if __name__ == "__main__":
    main()
