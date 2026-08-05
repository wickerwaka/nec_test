#!/usr/bin/env python3
"""x1_retention -- §56.3a's `core_ad` retention INTERVENTION, Verilated leg.

WHAT IS REGISTERED (ucore_provenance.md §56.3a, verbatim in substance; this
file scores against it and does not restate it).

  the reading      at an INTA's T1 the chip's AD pads float and RETAIN the
                   previous data phase.  Inside the FPGA `core_ad` is an
                   internal net with no keeper, so the row reads whatever the
                   resolution gives instead.  116 of 116 fabric-only HLT-sweep
                   failures are INTA rows -- and the attribution is a READING,
                   NOT ESTABLISHED (C11), because F42 had evidence of exactly
                   this shape and was refuted anyway.
  the intervention give system_large's `core_ad` an explicit retention model.
                   NOTHING in either core changes; `v30u_biu.sv` in particular
                   is NOT touched.
  the population   the four HLT delay sweeps, all 283 cells, same driver, same
                   goldens.
  THE BAR, BOTH HALVES REQUIRED
                   (i)  ALL 116 close -- the total reaches 259/283 EXACTLY, not
                        merely toward it.  A partial close means the class was
                        not one mechanism and the residue is the CORE's.
                   (ii) NOTHING ELSE MOVES -- `HLT.RES` cell-identical at
                        47/49, 48/49, 24/25, 24/25; every `HLT.INT` cell
                        matching its OFFLINE result CELL FOR CELL; no non-INTA
                        row acquiring a new first divergence.
  WHAT REFUTES IT  any of the 116 still failing, or any fabric-only NON-INTA
                   divergence.  A survivor is reclassified as CORE-OWNED and
                   reported as a REFUTATION, not re-explained.

WHAT THIS FILE IS, AND IS NOT.  It is the OFFLINE half: `system_large` under
Verilator (`hdl/tb/tb_sys.sv`), which is the same integration the bitstream is
built from, driven by the same `emit_suite` driver that emitted the goldens.
It is NOT the fabric leg -- no board is touched here -- so it cannot by itself
close a bar that was registered on fabric numbers.  What it CAN do, and what it
is for, is stated before the run in the ledger: establish whether the Verilated
integration REPRODUCES the fabric baseline (143/283), and if it does, whether
the intervention moves it to 259/283 under the registered bar.  If the baseline
does not reproduce, that is the result, and the intervention is not scored.

  offline   the per-cell PASS/FAIL of `tb_v30_core` (which MODELS pad
            retention, §R.2) -- the 259/283 column, and bar (ii)'s reference.
  capture   --leg base : tb_sys built WITHOUT X1_AD_RETENTION
            --leg ret  : tb_sys built WITH it.  The two builds differ by that
                         define and by nothing else.
  score     the bar.
"""
import argparse
import gzip
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                  # noqa: E402
import check_core as cc                                  # noqa: E402
from analyze_capture import decode_words                 # noqa: E402

OUT = ROOT / "sw" / "testdata" / "x1-retention"
TB_DIR = ROOT / "hdl" / "tb"
# SM3 sitting 12 -- THE VACUOUS-GATE PATTERN, SEVENTH INCARNATION, AND IT IS
# THIS FILE'S OWN.  These two names were `tb_sys`, which is what sitting 6's
# ad-hoc hand-rebuild happened to call its output (`ucore_provenance.md`
# §67.7).  `build()` below -- added at sitting 8 to close §67.6's SIXTH
# incarnation -- runs plain `verilator --binary --top-module tb_sys`, and that
# writes **`Vtb_sys`**.  So `build()` compiled the current RTL into a file
# `capture` never opened, printed `REBUILT`, and `capture` then ran the
# 2026-08-04 14:53 binary from sitting 6.  §69.2's "the 283 `ret` records are
# BYTE-IDENTICAL to HEAD's" was a binary compared with ITSELF.
#
# MEASURED, not inferred: `hdl/tb/obj_dir_sys/{tb_sys,Vtb_sys}` differ, the
# `tb_sys` files' mtime is sitting 6's and never moved across two `build()`
# runs, and `Vtb_sys.mk` says `default: Vtb_sys`.
#
# The stale files are ARCHIVED BY RENAME (`tb_sys.stale-s6`), not deleted.
BIN = {"base": TB_DIR / "obj_dir_sys" / "Vtb_sys",
       "ret": TB_DIR / "obj_dir_sys_ret" / "Vtb_sys"}

# u4_f42_fabric.py's population, unchanged, because "same driver, same goldens"
# is half of what the registration asks for.
SWEEPS = [("s10-hltsweep-w0", 0, list(range(0, 49))),
          ("s10-hltsweep-w1", 1, list(range(0, 49))),
          ("s13-hltsweep-w2", 2, list(range(0, 25))),
          ("s13-hltsweep-w3", 3, list(range(0, 25)))]
FORMS = ["HLT.INT", "HLT.RES"]

_LEG = {"bin": None}

# --------------------------------------------------------------------------- #
# THE BUILD, which this file did not have (ucore_provenance.md §67.6/§67.7's
# routed rig debt, TAKEN at task #37 because this sitting must rebuild both
# legs anyway).  §67.6 measured what its absence costs: `capture` checked only
# that the binary EXISTED, so a stale `tb_sys` scored PRE-F43 RTL against a
# POST-F43 reference column and reported "6 SURVIVORS, BAR (i) NOT MET" -- a
# result that was entirely the instrument.  The dependency set is the same one
# `check_core.build()` uses for `tb_v30_core`, plus the harness RTL tb_sys
# integrates; the flag set is `check_core.build()`'s plus the two waivers
# tb_sys.sv's AXI task-driven handshake needs.
# --------------------------------------------------------------------------- #
HARNESS_RTL = ["capture_buf.sv", "hps_axi_slave.sv", "iords_buf.sv",
               "nec_bus.sv", "system_large.sv", "test_mem.sv", "wvec_buf.sv"]
UCORE_DIR = ROOT / "hdl" / "rtl" / "ucore"


def build_deps():
    """Everything the binary is a function of.  A file missing from this list
    is a vacuous gate waiting to happen -- see the note above."""
    return ([ROOT / "hdl" / "rtl" / f for f in HARNESS_RTL]
            + [TB_DIR / "tb_sys.sv"]
            + cc.core_paths("ucore")[:1] + cc.core_paths("ucore")[2:]
            + sorted(UCORE_DIR.glob("*.svh")))


def build(leg, force=False):
    obj = BIN[leg].parent
    deps = build_deps()
    if BIN[leg].exists() and not force:
        newest = max(p.stat().st_mtime for p in deps)
        if BIN[leg].stat().st_mtime > newest:
            return False
    rtl = ([UCORE_DIR / "v30u_ss_pkg.sv"]
           + [ROOT / "hdl" / "rtl" / f for f in HARNESS_RTL]
           + [UCORE_DIR / f for f in ("v30_core.sv", "v30u_biu.sv",
                                      "v30u_ucrom.sv", "v30u_eu.sv")]
           + [TB_DIR / "tb_sys.sv"])
    cmd = ["verilator", "--binary", "--timing",
           "-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN",
           "-Wno-TIMESCALEMOD", "-Wno-WIDTHEXPAND", "-Wno-BLKSEQ",
           "-Wno-DECLFILENAME", "-Wno-UNUSEDPARAM",
           "-Wno-MULTIDRIVEN", "-Wno-PINCONNECTEMPTY",
           "--top-module", "tb_sys"]
    if leg == "ret":
        cmd.append("-DX1_AD_RETENTION")
    cmd += ["-I" + str(UCORE_DIR), "-Mdir", str(obj)] + [str(p) for p in rtl]
    print("building:", " ".join(cmd), flush=True)
    t0 = time.time()
    subprocess.run(cmd, check=True, cwd=ROOT)
    # THE FALSIFIER FOR THE SEVENTH INCARNATION (see BIN above).  A `build()`
    # whose compiler writes somewhere other than the file `capture` opens is
    # indistinguishable from a working one unless this is checked: the binary
    # must EXIST and must be NEWER THAN THE COMPILE that just ran.
    if not BIN[leg].exists():
        sys.exit(f"x1_retention.build({leg}): verilator succeeded but "
                 f"{BIN[leg]} does not exist -- BIN and the compiler disagree "
                 f"about the output name")
    if BIN[leg].stat().st_mtime < t0:
        sys.exit(f"x1_retention.build({leg}): {BIN[leg]} was NOT written by "
                 f"the compile that just ran (mtime precedes it) -- the "
                 f"binary `capture` will run is not the one `build` made")
    return True


def cmd_build(a):
    for leg in (("base", "ret") if a.leg == "all" else (a.leg,)):
        did = build(leg, force=a.force)
        print(f"  {leg}: {'REBUILT' if did else 'up to date'}  {BIN[leg]}")
    return 0


def golden(suite, form):
    fn = ROOT / "tests" / "v30" / suite / f"{form}.json.gz"
    return json.loads(gzip.decompress(fn.read_bytes()))


# --------------------------------------------------------------------------- #
# the DUT, in `run_image`'s clothes.
#
# emit_suite composes the image, arms the event and parses the capture; the
# ONLY thing swapped is where the records come from.  That is the same
# substitution u4_f42_fabric makes for the FPGA, and it is why the resulting
# number is on `check_core`'s scale by construction rather than by intention.
# --------------------------------------------------------------------------- #
def vsys_run(image, host, tag="test", waits=0, evt=None, iord=None,
             pins=None, want_fired=False, cap=None, use_core=None,
             wrand=None, wvec=None, iords=None, div=None):
    if wrand is not None or wvec is not None or iords is not None:
        raise RuntimeError("tb_sys carries no wrand/wvec/iords leg")
    with tempfile.TemporaryDirectory(dir=Path.home() / ".cache") as td:
        img = Path(td) / "img.hex"
        capf = Path(td) / "cap.hex"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(_LEG["bin"]), f"+img={img}", f"+cap={capf}",
                f"+ncap={cap or 2048}", f"+waits={waits}",
                f"+div={div or es.EMIT_DIV}"]
        if pins:
            argv.append(f"+pins={pins:x}")
        if evt is not None:
            a, d, ho, p = evt
            argv += [f"+evaddr={a:05x}", f"+evdelay={d}", f"+evhold={ho}",
                     f"+evpin={p}"]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
        m = re.search(r"SYS DONE (\d+) records fired=(\d)", r.stdout)
        if not m:
            raise RuntimeError(f"tb_sys failed: {r.stdout[-300:]} "
                               f"{r.stderr[-200:]}")
        words = [int(x, 16) for x in capf.read_text().split() if x]
    recs = decode_words(words)
    fired = bool(int(m.group(2)))
    return (recs, fired) if want_fired else recs


# --------------------------------------------------------------------------- #
def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    _LEG["bin"] = BIN[a.leg]
    # §67.6's lesson: never score against a binary nothing in the tree owns.
    build(a.leg)
    if not _LEG["bin"].exists():
        sys.exit(f"missing {_LEG['bin']} -- `x1_retention.py build --leg {a.leg}`")
    # THE DUT PIN, exactly as u4_f42_fabric flips it: nothing here writes to
    # tests/v30/, and this is a DUT leg, not an emission.
    es.EMIT_USE_CORE = True
    es.run_image = vsys_run
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
                # both board probes seed from the SAME string (s13_board reuses
                # s10's), so the sweep axis is the delay and nothing else.
                rng = random.Random(f"v30-s10-hlt/{form}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError:
                    continue
                case["delay"] = delay
                try:
                    t = es.emit_evt_case(spec, case, None, tag="x1",
                                         preload_n=0, waits=waits)
                except Exception as e:                     # noqa: BLE001
                    err += 1
                    print(f"  ERR {suite}/{form}/{di}: {str(e)[:120]}",
                          flush=True)
                    continue
                t["idx"] = di
                out[di] = t
                n += 1
            fn = OUT / f"{suite}.{form}.{a.leg}.json.gz"
            fn.write_bytes(gzip.compress(json.dumps(
                {str(k): v for k, v in out.items()}).encode()))
            print(f"  {suite}/{form}: {len(out)} cells "
                  f"({time.time()-t0:.0f}s)", flush=True)
    print(f"CAPTURE {a.leg}: {n} cells, {err} errors, {time.time()-t0:.0f}s")
    return 0


# --------------------------------------------------------------------------- #
def cmd_offline(a):
    """The tb_v30_core column, per CELL.  `check_core` prints a
    `HLT.INT idx N` header for every failing cell, which is the whole reason
    this can be read out of it rather than re-implemented -- but ONLY for the
    first `--details` of them (default 3), so the count is passed high enough
    to cover the sweep and the parse is CHECKED against the printed
    `pass/n` totals below.  A silently truncated fail list would make bar (ii)
    read green by having nothing to compare against."""
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for suite, waits, _d in SWEEPS:
        for form in FORMS:
            r = subprocess.run(
                [sys.executable, str(SW / "check_core.py"),
                 "--suite-dir", f"tests/v30/{suite}", "--opcodes", form,
                 "--waits", str(waits), "--cases", "0", "--details", "999"],
                capture_output=True, text=True, cwd=ROOT, timeout=7200)
            bad = sorted({int(m) for m in
                          re.findall(rf"^  {re.escape(form)} idx (\d+) ",
                                     r.stdout, re.M)})
            tot = re.search(rf"^{re.escape(form)}: (\d+)/(\d+) full",
                            r.stdout, re.M)
            np_, nn = (int(tot.group(1)), int(tot.group(2))) if tot else (0, 0)
            if len(bad) != nn - np_:
                sys.exit(f"{suite}/{form}: parsed {len(bad)} failing idx but "
                         f"check_core reports {nn - np_} -- the fail list is "
                         f"truncated and bar (ii) would be vacuous")
            res[f"{suite}/{form}"] = {"fail": bad, "pass": np_, "n": nn}
            print(f"  {suite}/{form}: {res[f'{suite}/{form}']['pass']}/"
                  f"{res[f'{suite}/{form}']['n']}  fail={bad}", flush=True)
    (OUT / "offline.json").write_text(json.dumps(res, indent=1))
    tp = sum(v["pass"] for v in res.values())
    tn = sum(v["n"] for v in res.values())
    print(f"OFFLINE (tb_v30_core, the retention-modelling TB): {tp}/{tn}")
    return 0


def _score_leg(leg):
    """(per-cell pass map, total, scored) for one DUT leg."""
    cells, tot, ok = {}, 0, 0
    for suite, _w, _d in SWEEPS:
        for form in FORMS:
            fn = OUT / f"{suite}.{form}.{leg}.json.gz"
            if not fn.exists():
                continue
            dut = json.loads(gzip.decompress(fn.read_bytes()))
            g = {t["idx"]: t for t in golden(suite, form)}
            for k, t in sorted(dut.items(), key=lambda x: int(x[0])):
                idx = int(k)
                if idx not in g:
                    continue
                tot += 1
                mm, _m = cc.diff_rows(g[idx]["cycles"], t["cycles"])
                good = not mm
                ok += good
                first = None
                if mm:
                    r, c = mm[0][0], mm[0][1]
                    # the golden's cycle rows are SST lists; [7] is the bus
                    # status, which is the column X1's whole claim is about.
                    first = (r, cc.COL_NAME.get(c, str(c)),
                             g[idx]["cycles"][r][7]
                             if r < len(g[idx]["cycles"]) else None)
                cells[f"{suite}/{form}/{idx}"] = {"pass": good, "first": first}
    return cells, ok, tot


def cmd_score(a):
    off = json.loads((OUT / "offline.json").read_bytes())
    offpass = {}
    for k, v in off.items():
        for i in v["fail"]:
            offpass[f"{k}/{i}"] = False
    base, bok, btot = _score_leg("base")
    ret, rok, rtot = _score_leg("ret")
    offtot = sum(v["pass"] for v in off.values())
    offn = sum(v["n"] for v in off.values())

    print("=== X1 / §56.3a, VERILATED LEG "
          "(system_large under Verilator; NO board) ===")
    print(f"  offline  tb_v30_core (models pad retention)  {offtot}/{offn}")
    print(f"  base     tb_sys, X1_AD_RETENTION OFF          {bok}/{btot}")
    print(f"  ret      tb_sys, X1_AD_RETENTION ON           {rok}/{rtot}")
    print(f"  fabric   (§56.1, cited not re-measured)       143/283")

    def cellpass(m, k):
        return m[k]["pass"] if k in m else None

    keys = sorted(set(base) | set(ret))
    inta = [k for k in keys if base.get(k, {}).get("first")
            and base[k]["first"][2] == "INTA"]
    basefail = [k for k in keys if cellpass(base, k) is False]
    retfail = [k for k in keys if cellpass(ret, k) is False]
    offfail = [k for k in keys if offpass.get(k) is False]
    print(f"\n  cells failing: base {len(basefail)}  ret {len(retfail)}  "
          f"offline {len(offfail)}")
    print(f"  base-only failures (base fails, offline passes): "
          f"{len([k for k in basefail if k not in offfail])}")
    print(f"    ...of which the golden's first-divergence row is an INTA row: "
          f"{len([k for k in inta if k not in offfail])}")

    # BAR (i)
    closed = [k for k in basefail if k not in offfail and cellpass(ret, k)]
    survived = [k for k in basefail if k not in offfail
                and cellpass(ret, k) is False]
    print(f"\n  BAR (i)  all base-only cells close, total == offline exactly")
    print(f"    closed {len(closed)}   SURVIVED {len(survived)}   "
          f"ret total {rok} vs offline {offtot}: "
          f"{'MET' if (not survived and rok == offtot) else 'NOT MET'}")
    if survived:
        print("    survivors (REFUTES the attribution; these are "
              "reclassified CORE-OWNED unless separately registered):")
        for k in survived[:40]:
            print(f"      {k}  first={ret[k]['first']}")

    # BAR (ii)
    moved = [k for k in keys
             if cellpass(ret, k) is not None
             and cellpass(ret, k) != (offpass.get(k, True))]
    print(f"\n  BAR (ii) nothing else moves -- every cell matching its OFFLINE "
          f"result cell for cell")
    print(f"    cells differing from offline after the intervention: "
          f"{len(moved)}: {'MET' if not moved else 'NOT MET'}")
    for k in moved[:40]:
        print(f"      {k}  ret={'pass' if cellpass(ret,k) else 'FAIL'} "
              f"offline={'pass' if offpass.get(k, True) else 'FAIL'}")
    print(f"\n  VERDICT (this leg): "
          f"{'MET' if (not survived and rok == offtot and not moved) else 'NOT MET'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    s = ap.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("build")
    b.add_argument("--leg", choices=("base", "ret", "all"), default="all")
    b.add_argument("--force", action="store_true")
    b.set_defaults(fn=cmd_build)
    c = s.add_parser("capture")
    c.add_argument("--leg", choices=("base", "ret"), required=True)
    c.set_defaults(fn=cmd_capture)
    o = s.add_parser("offline")
    o.set_defaults(fn=cmd_offline)
    v = s.add_parser("score")
    v.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
