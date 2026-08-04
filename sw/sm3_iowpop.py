#!/usr/bin/env python3
"""sm3_iowpop -- the `IOW` population of `ucore_provenance.md` §66.3, DERIVED
from the artifact rather than cited from a list.

§66.3's finding: `hdl/tb/tb_v30_core.sv` committed `IOW` cycles into `mem[]`,
so an I/O write to port P corrupted memory at address P for the RTL legs only.
The seeds it can reach are exactly those whose CHIP ROWS contain an `IOW`
cycle whose port number is later READ as memory (a `MEMR` or a `CODE` fetch at
that address).  §66.3 measured **37** such seeds over the 2,710 SCORED seeds.

This tool re-derives the population over the WHOLE banked corpus, CHIP-SIDE,
with no engine and no testbench in the loop -- which is the point: the defect
was in a replay instrument, so a population defined by the instrument would be
circular.  It is a MEASUREMENT, and it is also the CONTROL that
`sm3_sig_admit.py --cause iow` refuses to write without.

`sm3_sigctl.py`'s own control is INV-1's (a `recapture` block with
`evt.hold == 300` and `evt.hold_bits == 12`) and is the right control for the
admission it was written for.  A different cause needs a different control;
this is that control, and it is a separate file so neither can be quietly
substituted for the other.

Usage:
  sm3_iowpop.py [--jobs N] [--out iowpop.json]
"""
import argparse
import gzip
import json
import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import ucsim_fuzz as uf                                   # noqa: E402

BANK = ROOT / "tests" / "v30" / "fuzz_bank"
BANKS = ("mc1", "mc2", "t30-raw", "t30-brkem")
IOW, MEMR, CODE = 2, 5, 4


def key_of(rel):
    """`mc1/seeds/raw_1937_8d55….json.gz` -> `mc1/1937`, the ledger's own
    spelling for a seed."""
    m = re.match(r"([\w\-]+)/seeds/(?:raw|soup)_(\d+)_", str(rel))
    return f"{m.group(1)}/{m.group(2)}" if m else str(rel)


def one(p):
    p = Path(p)
    rel = p.relative_to(BANK)
    entry = json.loads(gzip.decompress(p.read_bytes()))
    recs = entry.get("chip_rows") or []
    if not recs:
        return (str(rel), False)
    win = uf.window_of(recs)
    ports = []
    hit = False
    for i in range(min(win, len(recs))):
        r = recs[i]
        if r.get("t_state", r.get("t")) != 1:
            continue
        a = r["ad_addr"] & 0xFFFFF
        if r["bs_early"] == IOW:
            ports.append((i, a & 0xFFFF))
        elif r["bs_early"] in (MEMR, CODE):
            if any(a == pa for pi, pa in ports if pi < i):
                hit = True
    return (str(rel), hit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    paths = [str(x) for b in BANKS
             for x in sorted((BANK / b / "seeds").glob("*.json.gz"))]
    with Pool(a.jobs) as pool:
        res = pool.map(one, paths, chunksize=8)
    pop = sorted(r for r, v in res if v)
    keys = sorted({key_of(r) for r in pop})
    print(f"== sm3_iowpop -- {len(res)} banked seeds, "
          f"IOW population {len(pop)}")
    print("  " + " ".join(keys))
    if a.out:
        Path(a.out).write_text(json.dumps(
            {"n_bank": len(res), "paths": pop, "keys": keys}, indent=1))
        print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
