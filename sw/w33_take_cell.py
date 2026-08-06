#!/usr/bin/env python3
"""w33_take_cell -- P1's TAKE CLOCK, measured on a population where the
coordinate is NOT circular.

Spec and PRE-REGISTERED per-candidate predictions:
`docs/notes/wrfuzz_w33_prereg_2026-08-06.md`.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

WHAT IT ASKS.  `wrfuzz_provenance.md` sec.5.4a closed W3.2 with a sharpened
question rather than a law:

    The open quantity is the TAKE CLOCK at the contested entry, and it cannot
    be measured from this corpus: the only instrument for it is an engine's own
    boundary clock, and every contested entry lies AFTER that engine's first
    divergence.  The measurement is circular on banked data.

sec.5.7 then re-specified the cell around it and named the instrument:
`sm3_tf_floor_cell`'s sled, because it is PERIODIC, every instruction start is
known, and the pushed IP names the boundary the part chose.

**AND THE 30 RETAINED FLOOR-CELL CAPTURES ALREADY BREAK THE CIRCULARITY.**
Both engines are EXACT on all 30 -- 121,890 rows / 121,860 rows, ZERO
row-diffs (`standing_gates.md`, the BRK/TF floor cell).  On a capture where
every bus event agrees clock for clock, an engine's take clock IS a coordinate
both sides share, which is precisely what the banked `wr1` corpus cannot
supply.  So the first leg of this cell is OFFLINE and needs no board at all:
it reads the take clock out of the engine's own trace (`+brktrace`'s `BRKT`
line in the RTL, `V30SIM_BRKTRACE`'s `BRKR ... take=1` in the model) and
measures, per (sled, wait) cell and per entry:

  * `vec - take`  -- the clocks from the take to the entry's VECTOR-READ T1;
  * every `CODE` T1 in `[take - 4, vec]`, i.e. what the prefetcher did in the
    window the suspend candidate is about;
  * the idle gaps either side.

If `vec - take` is INVARIANT across the pad walk and both wait levels, the
engines' boundary clock is silicon's take clock up to that constant, and P1's
cause is NOT the take clock.  If it MOVES with the pad or the wait, it is.

The `run` leg captures the same sleds fresh only if the offline leg's
precondition fails (a cell where the engine is not exact).  It is the board
arm and it is not taken unless the offline leg says it is needed.

Usage:
    python3 sw/w33_take_cell.py geom [--core ucore|sim] [--variants ...]
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                           # noqa: E402
simbin.ensure("w33 take cell")
import sm3_tf_floor_cell as fcell                       # noqa: E402
import fuzz_classify as fc                              # noqa: E402

CAP = ROOT / "sw" / "testdata" / "sm3-s24tfcell"
OUT = ROOT / "sw" / "testdata" / "w33-takecell"
ROM = ROOT / "docs" / "V20BITS.TXT"

PASV, CODE, MEMR, MEMW = 7, 4, 5, 6


def t_of(r):
    return r.get("t_state", r.get("t"))


def cycles(rows):
    out = []
    for i in range(len(rows)):
        if t_of(rows[i]) == 1 and rows[i]["bs_early"] != PASV:
            out.append((i, rows[i]["bs_early"], rows[i]["ad_addr"] & 0xFFFFF))
    return out


def vector_reads(rows):
    """The T1 row of every IVT read (`MEMR` below 0x400).  A vector-1 entry
    reads TWO of them; the FIRST is the entry's launch, which is the quantity
    P1's invariant is written on."""
    out, cy = [], cycles(rows)
    for k, (r, bs, a) in enumerate(cy):
        if bs == MEMR and a < 0x400:
            prev = cy[k - 1] if k else None
            if not (prev and prev[1] == MEMR and prev[2] < 0x400
                    and prev[2] + 2 == a):
                out.append((r, a >> 2))
    return out


BRKT_RE = re.compile(r'BRKT clk=(\d+)')
SIMBRK_RE = re.compile(r'BRKR clk=(\d+) .* take=1')


def ucore_takes(image, waits, clocks):
    td = tempfile.mkdtemp(prefix="w33t_")
    try:
        img = Path(td) / "img.hex"
        outp = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(_tb()), f"+bootimg={img}", f"+bootn={clocks}",
                "+mirror=1", f"+out={outp}", f"+waits={waits}", "+brktrace"]
        p = subprocess.run(argv, capture_output=True, timeout=900)
        so = p.stdout.decode()
        takes = [int(m.group(1)) for m in BRKT_RE.finditer(so)]
        rows = []
        if outp.exists():
            for line in outp.read_text().splitlines():
                f = line.split()
                if f and f[0] == "r":
                    rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                                 "qs": int(f[3]), "ube_n": int(f[4]),
                                 "ad_addr": int(f[5], 16),
                                 "ad_data": int(f[6], 16), "ps": int(f[7], 16)})
        return takes, rows
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def _tb():
    import timed_fuzz as tf
    return tf.tb_bin("ucore")


def sim_takes(image, waits, clocks):
    td = tempfile.mkdtemp(prefix="w33s_")
    try:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        env = dict(os.environ)
        env["V30SIM_BRKTRACE"] = "1"
        argv = [str(simbin.SIM), "timed-boot", str(ROM), str(img),
                f"--clocks={clocks}", "--ndjson", f"--waits={waits}"]
        p = subprocess.run(argv, capture_output=True, env=env, timeout=600)
        takes = [int(m.group(1)) for m in SIMBRK_RE.finditer(p.stderr.decode())]
        rows = []
        for l in p.stdout.decode().splitlines():
            if l.startswith("{"):
                o = json.loads(l)
                if "t" in o:
                    rows.append(o)
        return takes, rows
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def cmd_geom(a):
    variants = a.variants.split(",") if a.variants else \
        [v for v in fcell.VARIANTS if v.startswith("popf")]
    waits = [int(x) for x in a.waits.split(",")]
    rec = {"tool": "w33_take_cell geom", "core": a.core, "cells": {}}
    all_off, all_code = Counter(), Counter()
    for v in variants:
        image, _ = fcell.image_of(v)
        for w in waits:
            key = f"{v}:w{w}"
            cpath = CAP / f"{v}_w{w}_r0.rows.json.gz"
            if not cpath.exists():
                print(f"  {key}: NO RETAINED CAPTURE -- skipped")
                continue
            with gzip.open(cpath, "rt") as f:
                chip = json.load(f)
            n = len(chip)
            takes, erows = (ucore_takes(image, w, n) if a.core == "ucore"
                            else sim_takes(image, w, n))
            if not erows:
                print(f"  {key}: ENGINE ERROR")
                continue
            m = min(len(chip), len(erows))
            d = fc.diff_rows(chip[:m], erows[:m], window=m)
            exact = (d.bad == 0)
            cvec = vector_reads(chip)
            evec = vector_reads(erows)
            # PRECONDITION: the coordinate is shared only where the engine is
            # exact on this capture.  Reported, never assumed.
            offs, codes = [], []
            ccy = cycles(chip)
            for (vr, vec) in cvec:
                tk = [t for t in takes if t < vr]
                if not tk:
                    continue
                t0 = tk[-1]
                offs.append(vr - t0)
                nc = sum(1 for (r, bs, ad) in ccy
                         if bs == CODE and t0 < r < vr)
                codes.append(nc)
            cell = {"exact": exact, "row_diffs": d.bad, "n_rows": m,
                    "n_chip_entries": len(cvec), "n_eng_entries": len(evec),
                    "n_takes": len(takes),
                    "vec_minus_take": dict(Counter(str(x) for x in offs)),
                    "code_in_window": dict(Counter(str(x) for x in codes))}
            rec["cells"][key] = cell
            all_off.update(offs)
            all_code.update(codes)
            print(f"  {key:<18} exact={'YES' if exact else 'NO (%d)' % d.bad} "
                  f"entries={len(cvec)}/{len(evec)} takes={len(takes)} "
                  f"vec-take={dict(Counter(offs))} "
                  f"code_in_window={dict(Counter(codes))}")
    rec["total_vec_minus_take"] = {str(k): v for k, v in sorted(all_off.items())}
    rec["total_code_in_window"] = {str(k): v for k, v in sorted(all_code.items())}
    print(f"\nALL CELLS  vec-take={dict(sorted(all_off.items()))}  "
          f"code_in_window={dict(sorted(all_code.items()))}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"geom_{a.core}.json").write_text(json.dumps(rec, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("geom")
    p.add_argument("--core", default="ucore", choices=("ucore", "sim"))
    p.add_argument("--variants", default=None)
    p.add_argument("--waits", default="0,3")
    p.set_defaults(fn=cmd_geom)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
