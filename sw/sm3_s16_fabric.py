#!/usr/bin/env python3
"""sm3_s16_fabric -- THE S16 DISPLAY WALK THROUGH THE INTEGRATION (SM3 s19).

`sm3_s16_cell.py` captures the S16 population from the SOCKET and refuses to do
anything else (`assert es.EMIT_USE_CORE is False`).  That is right: the goldens
come from the chip and from nothing else.  This file is its DUT counterpart --
the same 1,371 cells, the same frozen programs, the same delays, replayed
through the ucore instead of through the socket -- and it is `x1_fabric.py`'s
shape applied to a population 4.8x larger than the four HLT sweeps.

THREE DUTs, one comparator:

    fabric   the FPGA core on the board (`use_core=1`), the strongest
             instrument -- the pads really float and really retain.
    vsys     `system_large` under Verilator (`hdl/tb/tb_sys.sv`, through
             `x1_retention.vsys_run`), the SAME integration the bitstream is
             built from, `--ret` selecting the `X1_AD_RETENTION` build.
    socket   `use_core=0`, the rig-integrity control: the same driver over a
             subset must reproduce the golden exactly.  It is not a result.

**THE COMPARATOR IS ROWS ONLY** (`check_core.diff_rows`), because a capture is
all a DUT leg has -- there is no architectural readback on this path.  So the
number here is NOT `sm3_s16_score.py`'s 1,294/1,371, which is
`not mm and arch_ok`.  `offline` computes the ROWS-ONLY column from
`tb_v30_core` on the identical cells, and THAT is what a fabric total may be
compared with.  Quoting a rows-only total against an arch-inclusive one is the
comparator error this docstring exists to prevent.

Usage:
    python3 sw/sm3_s16_fabric.py offline                  # tb_v30_core, rows only
    python3 sw/sm3_s16_fabric.py vsys   --leg vsys_ret --ret
    python3 sw/sm3_s16_fabric.py fabric --leg fab_f9
    python3 sw/sm3_s16_fabric.py socket --leg soc_f9
    python3 sw/sm3_s16_fabric.py score  --leg fab_f9 [--ref offline]
"""
import argparse
import gzip
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                      # noqa: E402
import check_core as cc                                      # noqa: E402
import v30run                                                # noqa: E402

OUT = ROOT / "sw" / "testdata" / "sm3-s16fab"

# `sm3_s16_cell` asserts SOCKET-ONLY at import, so the population constants are
# taken from it BEFORE anything flips the pin, and the pin is flipped only
# inside a leg that owns a DUT.
import sm3_s16_cell as s16                                   # noqa: E402
from sm3_s16_cell import FORMS, PROGRAMS, WAITS, suite_dir   # noqa: E402
from t2b_board import HOST                                   # noqa: E402

# the socket control: one wait level, one program, both non-NMI forms.  Small
# enough to be cheap and large enough that a rig move cannot hide in it.
SOCKET_CONTROL = [(0, 0, "HLT.INT"), (0, 0, "HLT.RES")]


def golden(w, p, form):
    fn = suite_dir(w, p) / f"{form}.json.gz"
    if not fn.exists():
        return None
    return json.loads(gzip.decompress(fn.read_bytes()))


def _cells(subset=None):
    """(w, p, form, cases) over the emitted goldens -- the population is the
    GOLDEN's, so the 141 non-composable cells are absent by construction."""
    for w in WAITS:
        for p in PROGRAMS:
            for form in FORMS:
                if subset is not None and (w, p, form) not in subset:
                    continue
                cs = golden(w, p, form)
                if cs:
                    yield w, p, form, cs


def div_guard(tag):
    """`s13_board.div_guard` in substance -- PIN, then ask the transport what it
    commanded and RECORD the answer.  UNPINNED is a FINDING, not a retry."""
    from s10_board import pin_div
    pin_div()
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if "UNPINNED" not in str(rb) and "UNKNOWN" not in str(rb) \
        else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "***", flush=True)
    return {"readback": str(rb), "state": state}


# --------------------------------------------------------------------------- #
# Set by `cmd_vsys` before `_capture` runs; see the note there.  Empty for
# every other leg, which is what keeps the stamp out of the fabric manifests.
_ERA = {}


def _capture(a, use_core, subset=None, board=True):
    OUT.mkdir(parents=True, exist_ok=True)
    es.EMIT_USE_CORE = use_core
    print(f"leg {a.leg}: emit_suite.EMIT_USE_CORE = {use_core} "
          f"({'the FPGA core' if use_core else 'the SOCKET -- rig control'}), "
          f"NOT a golden emission", flush=True)
    man = {"leg": a.leg, "use_core": use_core, "board": board,
           "host": HOST if board else None, "div_guard": {}}
    man.update(_ERA)
    if board:
        man["div_guard"]["open"] = div_guard(f"{a.leg} open")
    t0 = time.time()
    n = err = 0
    for w, p, form, cases in _cells(subset):
        spec = es.EVT_FORMS[form]
        out = {}
        for c in cases:
            try:
                _s, case = s16.gen_case(form, p)
            except es.ComposeError:
                continue
            case["delay"] = c["idx"]                    # THE SWEEP AXIS
            try:
                t = es.emit_evt_case(spec, case, HOST if board else None,
                                     tag="s16f", preload_n=0, waits=w)
            except Exception as e:                          # noqa: BLE001
                err += 1
                print(f"  ERR w{w}/p{p}/{form}/{c['idx']}: {str(e)[:110]}",
                      flush=True)
                continue
            t["idx"] = c["idx"]
            out[c["idx"]] = t
            n += 1
        fn = OUT / f"s16-w{w}-p{p}.{form}.{a.leg}.json.gz"
        fn.write_bytes(gzip.compress(json.dumps(
            {str(k): v for k, v in out.items()}).encode()))
        print(f"  w{w} p{p} {form}: {len(out)} cells "
              f"({time.time()-t0:.0f}s)", flush=True)
    if board:
        man["div_guard"]["close"] = div_guard(f"{a.leg} close")
    man["cells"] = n
    man["errors"] = err
    man["seconds"] = round(time.time() - t0, 1)
    (OUT / f"manifest_{a.leg}.json").write_text(json.dumps(man, indent=1))
    print(f"CAPTURE {a.leg}: {n} cells, {err} errors, {man['seconds']}s")
    return 0 if err == 0 else 1


def cmd_fabric(a):
    return _capture(a, True)


def cmd_socket(a):
    sub = {(w, p, f) for w, p, f in SOCKET_CONTROL}
    return _capture(a, False, subset=sub)


def cmd_vsys(a):
    """The Verilated `system_large`, through x1_retention's own driver."""
    import x1_retention as x1
    leg = "ret" if a.ret else "base"
    x1.build(leg)
    x1._LEG["bin"] = x1.BIN[leg]
    print(f"  DUT {x1.BIN[leg]}  receipt "
          f"{str(__import__('artifact').receipt_id(x1.BIN[leg]))[:16]}…",
          flush=True)
    es.run_image = x1.vsys_run
    # THE ERA STAMP (SM3 sitting 22).  A `vsys` leg is a SOFTWARE leg: it is a
    # function of the tree and of nothing else, so a capture that does not
    # record WHICH tree can be compared with a reference column from another
    # one and nothing will say so.  That is not hypothetical -- the banked
    # `vsys_ret` column was captured before F56 and F57 landed in the ucore and
    # was still being quoted at 1,321 against a post-F57 offline reference
    # (`ucore_provenance.md` §83.0b).  A FABRIC leg is deliberately NOT stamped
    # this way: its DUT is a bitstream, and its provenance is the flash log.
    _ERA["tree"] = x1.tree_key()
    _ERA["receipt"] = __import__("artifact").receipt_id(x1.BIN[leg])
    return _capture(a, True, board=False)


# --------------------------------------------------------------------------- #
def cmd_offline(a):
    """The `tb_v30_core` ROWS-ONLY column, cell by cell -- the reference a
    fabric total may be compared with."""
    OUT.mkdir(parents=True, exist_ok=True)
    cc.require_bin("ucore", "sm3_s16_fabric offline")
    binp = cc.core_bin("ucore")
    cells = {}
    ok = tot = 0
    for w, p, form, cases in _cells():
        with tempfile.TemporaryDirectory() as td:
            b, o = Path(td) / "b.txt", Path(td) / "o.txt"
            cc.compose_batch(cases, b)
            r = subprocess.run(
                [str(binp), f"+batch={b}", f"+out={o}", f"+waits={w}",
                 "+ce_div=1"], cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0 or not o.exists():
                print(f"  SIM FAIL w{w}/p{p}/{form}")
                continue
            sims = cc.parse_out(o)
        for c in cases:
            sim = sims.get(c["idx"])
            tot += 1
            key = f"w{w}/p{p}/{form}/{c['idx']}"
            if sim is None:
                cells[key] = {"row": -1, "col": "NO_SIM"}
                continue
            rows, _e, _a, _b = cc.build_rows_sim(
                sim["recs"], c["initial"]["queue"], n_close=cc.n_fpops(c) - 1)
            if rows is None:
                cells[key] = {"row": -1, "col": "NO_ROWS"}
                continue
            mm, _ = cc.diff_rows(c["cycles"], rows)
            if not mm:
                ok += 1
                cells[key] = None
            else:
                cells[key] = {"row": mm[0][0],
                              "col": cc.COL_NAME.get(mm[0][1], str(mm[0][1]))}
    (OUT / "score_offline.json").write_text(json.dumps(
        {"leg": "offline", "exact": ok, "total": tot, "cells": cells},
        indent=1) + "\n")
    print(f"=== S16 OFFLINE (tb_v30_core, ROWS ONLY): {ok}/{tot}")
    return 0


# --------------------------------------------------------------------------- #
def cmd_score(a):
    # THE ERA GUARD, for the SOFTWARE legs only (SM3 sitting 22).  A `vsys`
    # column is a function of the tree; if its manifest says it was taken on a
    # different one, the number is about the instrument, not the core.
    man = OUT / f"manifest_{a.leg}.json"
    if man.is_file():
        m = json.loads(man.read_text())
        if not m.get("board", True) and str(a.leg).startswith("vsys"):
            import x1_retention as x1
            want, got = x1.tree_key(), m.get("tree")
            if got != want:
                sys.exit(
                    f"\nERA MISMATCH -- REFUSING TO SCORE.\n"
                    f"  leg           {a.leg} (a SOFTWARE leg: tb_sys under "
                    f"Verilator, no board)\n"
                    f"  its tree      "
                    f"{got or 'ABSENT (captured before the era stamp existed)'}\n"
                    f"  current tree  {want}\n"
                    f"  Re-capture it "
                    f"(sm3_s16_fabric.py vsys --leg {a.leg} [--ret]).\n")
    cells = {}
    ok = tot = 0
    per = {}
    for w, p, form, cases in _cells():
        fn = OUT / f"s16-w{w}-p{p}.{form}.{a.leg}.json.gz"
        if not fn.exists():
            continue
        dut = json.loads(gzip.decompress(fn.read_bytes()))
        g = {c["idx"]: c for c in cases}
        sok = stot = 0
        for k, t in sorted(dut.items(), key=lambda x: int(x[0])):
            idx = int(k)
            if idx not in g:
                continue
            tot += 1
            stot += 1
            mm, _m = cc.diff_rows(g[idx]["cycles"], t["cycles"])
            key = f"w{w}/p{p}/{form}/{idx}"
            if not mm:
                ok += 1
                sok += 1
                cells[key] = None
            else:
                cells[key] = {"row": mm[0][0],
                              "col": cc.COL_NAME.get(mm[0][1], str(mm[0][1]))}
                per.setdefault(f"w{w}/{form}", []).append(
                    f"p{p}/{idx}:row{mm[0][0]}:{cells[key]['col']}")
        if stot and a.verbose:
            print(f"  w{w}/p{p}/{form}: {sok}/{stot}")
    print(f"=== S16 {a.leg} (ROWS ONLY): {ok}/{tot}")
    (OUT / f"score_{a.leg}.json").write_text(json.dumps(
        {"leg": a.leg, "exact": ok, "total": tot, "cells": cells},
        indent=1) + "\n")

    ref = OUT / f"score_{a.ref}.json"
    if ref.exists() and a.ref != a.leg:
        rc = json.loads(ref.read_text())["cells"]
        common = [k for k in cells if k in rc]
        dis = [k for k in common if (cells[k] is None) != (rc[k] is None)]
        coord = [k for k in common
                 if cells[k] and rc[k] and
                 (cells[k]["row"], cells[k]["col"]) != (rc[k]["row"], rc[k]["col"])]
        print(f"  vs {a.ref} over {len(common)} common cells: "
              f"{len(dis)} PASS/FAIL disagreements, "
              f"{len(coord)} differing first-divergence coordinates")
        for k in sorted(dis)[:60]:
            print(f"    DISAGREE {k}: {a.leg}="
                  f"{'pass' if cells[k] is None else 'FAIL ' + str(cells[k])}"
                  f"  {a.ref}="
                  f"{'pass' if rc[k] is None else 'FAIL ' + str(rc[k])}")
        for k in sorted(coord)[:20]:
            print(f"    COORD {k}: {a.leg}={cells[k]}  {a.ref}={rc[k]}")
    if a.verbose:
        for k, v in sorted(per.items()):
            print(f"  {k}: " + " ".join(v))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("fabric", cmd_fabric), ("socket", cmd_socket)):
        c = s.add_parser(name)
        c.add_argument("--leg", required=True)
        c.set_defaults(fn=fn)
    c = s.add_parser("vsys")
    c.add_argument("--leg", required=True)
    c.add_argument("--ret", action="store_true",
                   help="the X1_AD_RETENTION build (else the base build)")
    c.set_defaults(fn=cmd_vsys)
    s.add_parser("offline").set_defaults(fn=cmd_offline)
    c = s.add_parser("score")
    c.add_argument("--leg", required=True)
    c.add_argument("--ref", default="offline")
    c.add_argument("-v", "--verbose", action="store_true")
    c.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
