#!/usr/bin/env python3
"""u4_f42_fabric - score §48.3's registered prediction IN FABRIC.

§48.3, registered before a bitstream existed: *if the 17 uncountable HLT cells
really are the TESTBENCH's composed-AD drive mask and not the core, then in
fabric -- where the analyser samples real pins and no drive mask exists --
those cells must PASS.*  *If any of the 17 fails in fabric, F42 is REFUTED.*

This runs the FOUR HLT delay sweeps through the ucore INSIDE the FPGA
(`use_core=1`) using the SAME driver that emitted the goldens
(`emit_suite.emit_evt_case`), and scores each cell against the stored golden
with the SAME comparator `check_core` uses.  Two legs, and the difference
between them IS the prediction:

    capture   run the sweeps through the FPGA core and keep the suite records
    score     `check_core.diff_rows` against the stored goldens, cell by cell,
              on the same scale as the TB's 249/283

THE GOLDENS ARE NOT TOUCHED.  `emit_suite.EMIT_USE_CORE` is the pin that says
goldens come from the SOCKET and from nothing else; this script flips it for
its own DUT capture only, writes into sw/testdata/u4-f42/ and never into
tests/v30/.  It is a DUT leg, not an emission.
"""
import argparse
import gzip
import json
import random
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                  # noqa: E402
import check_core as cc                                  # noqa: E402

HOST = "root@mister-nec"
OUT = ROOT / "sw" / "testdata" / "u4-f42"
SWEEPS = [("s10-hltsweep-w0", 0, list(range(0, 49))),
          ("s10-hltsweep-w1", 1, list(range(0, 49))),
          ("s13-hltsweep-w2", 2, list(range(0, 25))),
          ("s13-hltsweep-w3", 3, list(range(0, 25)))]
FORMS = ["HLT.INT", "HLT.RES"]


def golden(suite, form):
    fn = ROOT / "tests" / "v30" / suite / f"{form}.json.gz"
    return json.loads(gzip.decompress(fn.read_bytes()))


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    # THE DUT PIN.  Flipped here and nowhere else; nothing in this file writes
    # to tests/v30/.
    es.EMIT_USE_CORE = True
    print("DUT leg: emit_suite.EMIT_USE_CORE = True "
          "(the FPGA core, NOT a golden emission)", flush=True)
    t0 = time.time()
    n = err = 0
    for suite, waits, delays in SWEEPS:
        for form in FORMS:
            g = {t["idx"]: t for t in golden(suite, form)}
            out = {}
            for di, delay in enumerate(delays):
                if di not in g:
                    continue
                spec = es.EVT_FORMS[form]
                # BOTH board probes seed the program from the SAME string --
                # s13_board.py:149 reuses s10's -- so the sweep axis really is
                # the delay and nothing else.
                rng = random.Random(f"v30-s10-hlt/{form}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError:
                    continue
                case["delay"] = delay
                try:
                    t = es.emit_evt_case(spec, case, a.host, tag="f42",
                                         preload_n=0, waits=waits)
                except Exception as e:                     # noqa: BLE001
                    err += 1
                    print(f"  ERR {suite}/{form}/{di}: {str(e)[:100]}",
                          flush=True)
                    continue
                t["idx"] = di
                out[di] = t
                n += 1
            fn = OUT / f"{suite}.{form}.core.json.gz"
            fn.write_bytes(gzip.compress(json.dumps(
                {str(k): v for k, v in out.items()}).encode()))
            print(f"  {suite}/{form}: {len(out)} cells", flush=True)
    print(f"CAPTURE: {n} cells, {err} errors, {time.time()-t0:.0f}s")
    return 0


def cmd_score(a):
    tot = ok = 0
    per = {}
    for suite, waits, delays in SWEEPS:
        for form in FORMS:
            fn = OUT / f"{suite}.{form}.core.json.gz"
            if not fn.exists():
                continue
            dut = json.loads(gzip.decompress(fn.read_bytes()))
            g = {t["idx"]: t for t in golden(suite, form)}
            for k, t in sorted(dut.items(), key=lambda x: int(x[0])):
                idx = int(k)
                if idx not in g:
                    continue
                gd = g[idx]
                tot += 1
                # check_core's OWN comparator and column policy, so this
                # number is on the same scale as the TB's 249/283.
                mm, _masked = cc.diff_rows(gd["cycles"], t["cycles"])
                if not mm:
                    ok += 1
                else:
                    r, c = mm[0][0], mm[0][1]
                    col = cc.COL_NAME.get(c, str(c))
                    per.setdefault((suite, form), []).append(
                        (idx, f"row{r}:{col}"))
    print(f"=== F42 IN FABRIC: {ok}/{tot} cells identical to the golden")
    for k, v in sorted(per.items()):
        print(f"  {k[0]}/{k[1]}: " +
              " ".join(f"idx{ i }:{c}" for i, c in v))
    return 0


def main():
    ap = argparse.ArgumentParser()
    s = ap.add_subparsers(dest="cmd", required=True)
    c = s.add_parser("capture")
    c.add_argument("--host", default=HOST)
    c.set_defaults(fn=cmd_capture)
    v = s.add_parser("score")
    v.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
