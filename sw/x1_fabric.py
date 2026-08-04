#!/usr/bin/env python3
"""x1_fabric -- §56.3a's `core_ad` retention intervention, THE FABRIC LEG.

`u4_f42_fabric.py` is this leg's ancestor and its captures under
`sw/testdata/u4-f42/` ARE the §56.1 / §56.3 numbers (143/283 on FLASH #3).
This file exists so that a re-capture on a NEW bitstream is written BESIDE
them and never over them -- the same discipline the X3 `_f4` legs use.

    baseline  the 283 sweep cells through the FPGA core (`use_core=1`) on the
              bitstream currently on the board.  §59.5 prediction 1 says this
              must reproduce 143/283 on BS-A; a different total is a
              BITSTREAM-VINTAGE FINDING and it invalidates the comparability
              of any before/after taken across it, which is why it is taken
              FIRST.
    socket    §55.2 item 3 / §52.9's rig-integrity control: the SAME driver and
              the SAME 49 cells (`s10-hltsweep-w0` / `HLT.RES`) through the
              SOCKET (`EMIT_USE_CORE=False`, `use_core=0`) must reproduce the
              golden 49/49.  It is not a result: if it moves, nothing else is
              readable.
    score     `check_core.diff_rows`, cell by cell -- the SAME comparator the
              TB's 259/283 is on, so the numbers are on one scale.

THE GOLDENS ARE NOT TOUCHED.  `emit_suite.EMIT_USE_CORE` is the pin that says
goldens come from the socket and from nothing else; the `baseline` leg flips it
for its own DUT capture only and writes into `sw/testdata/x1-retention/`.
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

import emit_suite as es                                    # noqa: E402
import check_core as cc                                    # noqa: E402

HOST = "root@mister-nec"
OUT = ROOT / "sw" / "testdata" / "x1-retention"
SWEEPS = [("s10-hltsweep-w0", 0, list(range(0, 49))),
          ("s10-hltsweep-w1", 1, list(range(0, 49))),
          ("s13-hltsweep-w2", 2, list(range(0, 25))),
          ("s13-hltsweep-w3", 3, list(range(0, 25)))]
FORMS = ["HLT.INT", "HLT.RES"]
# §52.9's socket control: the same driver, the same 49 cells.
SOCKET_CONTROL = [("s10-hltsweep-w0", 0, ["HLT.RES"], list(range(0, 49)))]


def golden(suite, form):
    fn = ROOT / "tests" / "v30" / suite / f"{form}.json.gz"
    return json.loads(gzip.decompress(fn.read_bytes()))


def _sweep_capture(a, sweeps, tag, use_core):
    es.EMIT_USE_CORE = use_core
    print(f"leg {a.leg}: emit_suite.EMIT_USE_CORE = {use_core} "
          f"({'the FPGA core' if use_core else 'the SOCKET -- rig control'}), "
          f"NOT a golden emission", flush=True)
    t0 = time.time()
    n = err = 0
    for suite, waits, forms, delays in sweeps:
        for form in forms:
            g = {t["idx"]: t for t in golden(suite, form)}
            out = {}
            for di, delay in enumerate(delays):
                if di not in g:
                    continue
                spec = es.EVT_FORMS[form]
                # both board probes seed the program from the SAME string
                # (s13_board.py:149 reuses s10's), so the axis is the delay.
                rng = random.Random(f"v30-s10-hlt/{form}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError:
                    continue
                case["delay"] = delay
                try:
                    t = es.emit_evt_case(spec, case, a.host, tag=tag,
                                         preload_n=0, waits=waits)
                except Exception as e:                     # noqa: BLE001
                    err += 1
                    print(f"  ERR {suite}/{form}/{di}: {str(e)[:100]}",
                          flush=True)
                    continue
                t["idx"] = di
                out[di] = t
                n += 1
            fn = OUT / f"{suite}.{form}.{a.leg}.json.gz"
            fn.write_bytes(gzip.compress(json.dumps(
                {str(k): v for k, v in out.items()}).encode()))
            print(f"  {suite}/{form}: {len(out)} cells", flush=True)
    print(f"CAPTURE {a.leg}: {n} cells, {err} errors, {time.time()-t0:.0f}s")
    return 0 if err == 0 else 1


def cmd_baseline(a):
    OUT.mkdir(parents=True, exist_ok=True)
    sweeps = [(s, w, FORMS, d) for s, w, d in SWEEPS]
    return _sweep_capture(a, sweeps, "x1fab", True)


def cmd_socket(a):
    OUT.mkdir(parents=True, exist_ok=True)
    return _sweep_capture(a, SOCKET_CONTROL, "x1soc", False)


def cmd_score(a):
    tot = ok = 0
    per = {}
    cells = {}
    for suite, waits, delays in SWEEPS:
        for form in FORMS:
            fn = OUT / f"{suite}.{form}.{a.leg}.json.gz"
            if not fn.exists():
                continue
            dut = json.loads(gzip.decompress(fn.read_bytes()))
            g = {t["idx"]: t for t in golden(suite, form)}
            sok = stot = 0
            for k, t in sorted(dut.items(), key=lambda x: int(x[0])):
                idx = int(k)
                if idx not in g:
                    continue
                tot += 1
                stot += 1
                mm, _masked = cc.diff_rows(g[idx]["cycles"], t["cycles"])
                if not mm:
                    ok += 1
                    sok += 1
                    cells[f"{suite}/{form}/{idx}"] = None
                else:
                    r, c = mm[0][0], mm[0][1]
                    col = cc.COL_NAME.get(c, str(c))
                    # the bus-status of the golden's first-divergence row: the
                    # INTA class is read off THIS, not off a name.
                    grow = g[idx]["cycles"][r] if r < len(g[idx]["cycles"]) else None
                    cells[f"{suite}/{form}/{idx}"] = {
                        "row": r, "col": col,
                        "golden_row": grow,
                    }
                    per.setdefault((suite, form), []).append(
                        (idx, f"row{r}:{col}"))
            if stot:
                print(f"  {suite}/{form}: {sok}/{stot}")
    print(f"=== X1 {a.leg} IN FABRIC: {ok}/{tot} cells identical to the golden")
    (OUT / f"score_{a.leg}.json").write_text(json.dumps(
        {"leg": a.leg, "exact": ok, "total": tot, "cells": cells},
        indent=1) + "\n")
    if a.verbose:
        for k, v in sorted(per.items()):
            print(f"  {k[0]}/{k[1]}: " +
                  " ".join(f"idx{i}:{c}" for i, c in v))
    return 0


def cmd_score_socket(a):
    tot = ok = 0
    bad = []
    for suite, waits, forms, delays in SOCKET_CONTROL:
        for form in forms:
            fn = OUT / f"{suite}.{form}.{a.leg}.json.gz"
            if not fn.exists():
                print(f"  MISSING {fn.name}")
                return 2
            dut = json.loads(gzip.decompress(fn.read_bytes()))
            g = {t["idx"]: t for t in golden(suite, form)}
            for k, t in sorted(dut.items(), key=lambda x: int(x[0])):
                idx = int(k)
                if idx not in g:
                    continue
                tot += 1
                mm, _m = cc.diff_rows(g[idx]["cycles"], t["cycles"])
                if not mm:
                    ok += 1
                else:
                    bad.append((idx, mm[0][0],
                                cc.COL_NAME.get(mm[0][1], str(mm[0][1]))))
    print(f"=== SOCKET CONTROL ({a.leg}): {ok}/{tot} vs the golden")
    if bad:
        print("  *** the rig-integrity control MOVED -- nothing else in this "
              "section is readable ***")
        for b in bad[:20]:
            print(f"    idx{b[0]} row{b[1]}:{b[2]}")
    (OUT / f"score_{a.leg}.json").write_text(json.dumps(
        {"leg": a.leg, "exact": ok, "total": tot, "bad": bad}, indent=1) + "\n")
    return 0 if ok == tot else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("baseline", cmd_baseline), ("socket", cmd_socket)):
        c = s.add_parser(name)
        c.add_argument("--host", default=HOST)
        c.add_argument("--leg", required=True,
                       help="the capture tag, e.g. fab_f4 / fab_f5 / soc_f4")
        c.set_defaults(fn=fn)
    for name, fn in (("score", cmd_score), ("score-socket", cmd_score_socket)):
        c = s.add_parser(name)
        c.add_argument("--leg", required=True)
        c.add_argument("-v", "--verbose", action="store_true")
        c.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
