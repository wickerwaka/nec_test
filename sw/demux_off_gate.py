#!/usr/bin/env python3
"""demux_off_gate -- THE DE-MUXED CONFIGURATION, BUILT AND PROVEN.

Every standing gate in this tree builds `v30_core` WITH `-DV30_MUXED_AD`,
because the rig integration (`system_large` + `nec_bus`) is a multiplexed-pin
instrument by construction.  So without this gate the OTHER configuration --
the one the whole 2026-08-14 wave exists to create -- would never be
elaborated, and "the ports are removed" would be a claim about text.

THREE LEGS, and the second is the one that makes the first mean something.

  RUN   build `hdl/tb/tb_demux_min.sv` against the ucore with the define OFF
        and run it.  Bars, all four, from the harness's own census:
          FPOPS > 0          instructions actually STARTED
          BS_KINDS >= 4      at least four max-mode cycle types exercised
          WRITES > 0         at least one store committed from `DATA_O`
          ADDR_MOVES > 0     `ADDR_O` actually changed between bus cycles
        A run that elaborates and does nothing proves nothing.

  GONE  build the SAME testbench with a `.AD(...)` connection spliced into the
        core instantiation.  It must FAIL to elaborate, and the failure must
        NAME the pin.  A build that merely warns is not evidence that a port
        was removed.  Repeated for `AD_OE` and `CE_HALF`.

  ON    build the same testbench WITH the define.  It must ALSO fail, because
        `tb_demux_min` connects `DATA_I`, which does not exist there.  This is
        the control that the first leg's success is the define's doing and not
        an accident of a port list that accepts anything.

  python3 sw/demux_off_gate.py [--clocks N] [--seed S] [--keep]

Exit 0 = PASS, 1 = a bar missed, 2 = an operational failure.
`docs/notes/demux_bus_prereg_2026-08-14.md` §5 (P-OFF-1, P-OFF-2, P-OFF-3).
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TB = ROOT / "hdl" / "tb" / "tb_demux_min.sv"
UCORE = ROOT / "hdl" / "rtl" / "ucore"
RTL = ["v30u_ss_pkg.sv", "v30_core.sv", "v30u_biu.sv",
       "v30u_ucrom.sv", "v30u_eu.sv"]

WAIVERS = ["-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN", "-Wno-TIMESCALEMOD",
           "-Wno-WIDTHEXPAND", "-Wno-BLKSEQ", "-Wno-DECLFILENAME",
           "-Wno-UNUSEDPARAM", "-Wno-MULTIDRIVEN", "-Wno-UNOPTFLAT",
           "-Wno-CASEINCOMPLETE"]


def verilate(tb, objdir, defines):
    cmd = (["verilator", "--binary", "--timing"] + list(defines) + WAIVERS +
           ["--top-module", "tb_demux_min",
            "-I" + str(UCORE), "-Mdir", str(objdir), str(tb)] +
           [str(UCORE / f) for f in RTL])
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=1800)
    return r


def leg_run(work, clocks, seed):
    """RUN: the de-muxed core elaborates, runs, and does something."""
    obj = work / "obj_run"
    r = verilate(TB, obj, [])
    if r.returncode != 0:
        print(r.stdout[-4000:])
        print(r.stderr[-4000:])
        return None, "verilator FAILED to build the de-muxed core"
    # a clean build is part of the claim: the ports are gone, not merely unused
    warn = [ln for ln in r.stderr.splitlines()
            if ln.startswith("%Warning")]
    if warn:
        print("  build warnings:")
        for ln in warn[:20]:
            print("   ", ln)
    sim = subprocess.run([str(obj / "Vtb_demux_min"),
                          f"+nclocks={clocks}", f"+seed={seed}"],
                         cwd=ROOT, capture_output=True, text=True, timeout=3600)
    out = sim.stdout
    print(out.strip())
    if sim.returncode != 0:
        print(sim.stderr[-4000:])
        return None, f"the de-muxed run exited {sim.returncode}"
    got = {}
    for key in ("BS_KINDS", "QPOPS", "FPOPS", "WRITES", "ADDR_MOVES"):
        m = re.search(rf"\b{key}\s+(\d+)", out)
        if m:
            got[key] = int(m.group(1))
    if "RESULT OK" not in out:
        return got, "the harness's own RESULT line is not OK"
    return got, None


# the three pins the define is registered to REMOVE, and the text that splices
# each one back into the instantiation
GONE_PINS = {
    "AD":      "    .AD        (20'h0),\n",
    "AD_OE":   "    .AD_OE     (),\n",
    "CE_HALF": "    .CE_HALF   (1'b0),\n",
}


def leg_gone(work):
    """GONE: connecting a removed pin must FAIL, naming the pin."""
    src = TB.read_text()
    anchor = "    .DATA_I    (DATA_I),\n"
    if anchor not in src:
        return {}, "tb_demux_min.sv lost its .DATA_I anchor"
    results = {}
    for pin, splice in GONE_PINS.items():
        probe = work / f"tb_probe_{pin}.sv"
        probe.write_text(src.replace(anchor, anchor + splice, 1))
        r = verilate(probe, work / f"obj_gone_{pin}", [])
        blob = (r.stdout or "") + (r.stderr or "")
        named = pin in blob and ("PINNOTFOUND" in blob or
                                 "Pin not found" in blob.replace("_", " ") or
                                 "not found" in blob)
        results[pin] = (r.returncode != 0, named)
        verdict = ("REFUSED, pin named" if r.returncode != 0 and named
                   else "REFUSED but pin NOT named" if r.returncode != 0
                   else "ACCEPTED -- THE PORT IS STILL THERE")
        print(f"  .{pin:<8s} spliced in -> exit {r.returncode}: {verdict}")
    bad = [p for p, (failed, named) in results.items() if not (failed and named)]
    return results, (None if not bad else
                     f"a removed port was still accepted or unnamed: {bad}")


def leg_on(work):
    """ON: the same TB WITH the define must fail -- DATA_I does not exist."""
    r = verilate(TB, work / "obj_on", ["-DV30_MUXED_AD"])
    blob = (r.stdout or "") + (r.stderr or "")
    named = "DATA_I" in blob
    print(f"  tb_demux_min built WITH -DV30_MUXED_AD -> exit {r.returncode}"
          f"{', DATA_I named' if named else ''}")
    if r.returncode == 0:
        return "the muxed build ACCEPTED .DATA_I -- the define is not selecting"
    if not named:
        return "the muxed build failed but did not name DATA_I"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clocks", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--keep", action="store_true",
                    help="keep the scratch build tree")
    a = ap.parse_args()

    if not TB.exists():
        sys.exit(f"demux_off_gate: {TB} is missing")

    work = Path(tempfile.mkdtemp(prefix="demux_off_",
                                 dir=str(Path.home() / ".cache")))
    fails = []
    try:
        print("=== LEG 1/3  RUN -- the de-muxed core, define OFF")
        got, err = leg_run(work, a.clocks, a.seed)
        if err:
            fails.append(f"RUN: {err}")
        if got:
            bars = [("FPOPS", got.get("FPOPS", 0), 1),
                    ("BS_KINDS", got.get("BS_KINDS", 0), 4),
                    ("WRITES", got.get("WRITES", 0), 1),
                    ("ADDR_MOVES", got.get("ADDR_MOVES", 0), 1)]
            for name, val, bar in bars:
                ok = val >= bar
                print(f"  {name:<11s} {val:>8d}  >= {bar:<4d} "
                      f"{'MET' if ok else 'MISSED'}")
                if not ok:
                    fails.append(f"RUN bar {name}: {val} < {bar}")

        print("\n=== LEG 2/3  GONE -- AD / AD_OE / CE_HALF are not ports")
        _, err = leg_gone(work)
        if err:
            fails.append(f"GONE: {err}")

        print("\n=== LEG 3/3  ON -- the control: the define really selects")
        err = leg_on(work)
        if err:
            fails.append(f"ON: {err}")
    finally:
        if a.keep:
            print(f"\n(scratch kept at {work})")
        else:
            shutil.rmtree(work, ignore_errors=True)

    print()
    if fails:
        for f in fails:
            print(f"demux_off_gate: FAIL -- {f}")
        return 1
    print("=== demux_off_gate: PASS -- the de-muxed core builds and runs, the "
          "three muxed ports are GONE, and the define is what removes them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
