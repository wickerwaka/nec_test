#!/usr/bin/env python3
"""check_ab_sim - Campaign 4 Mission A/C, simulation half.

Runs the v30_core INSIDE the real integration (system_large) behind the
actual nec_bus capture path, via hdl/tb/tb_ab.sv under Verilator with the
A/B mux set to the core position (CFG.use_core=1). It drains the harness
capture buffer and diffs the core's boot trace against the real chip's
first boot measurement (sw/testdata/largemode_boot_real.hex) — the same
golden and the same column policy sw/check_boot.py uses for the standalone
core replay.

A match here proves the in-FPGA A/B harness observes the core exactly as it
observes the socketed chip: the capture path, memory model and pin sampling
serve both identically. The on-silicon confirmation is sw/check_seq.py with
CFG.use_core toggled on the board (Mission C/E).

Usage: check_ab_sim.py [nrows] [--core {fsm,ucore}] [--build] [--keep]

ucore U4: `--core ucore` swaps the RTL list for the ROM-driven twin, exactly as
`sw/check_core.py --core` does -- the module is `v30_core` and the package is
`v30_ss_pkg` in both, so system_large.sv / nec_bus.sv / tb_ab.sv are untouched.
This is the SIMULATION half of the in-fabric A/B: it puts the ucore inside the
real integration, behind the real capture path, before any bitstream is flashed.

  U4 FINDING: this gate had been UNBUILDABLE since the save-state package
  landed.  `v30_ss_pkg.sv` was never added to the list below, and both
  v30_core.sv and v30_eu.sv `import v30_ss_pkg::*`, so verilator exited with
  "Importing from missing package 'v30_ss_pkg'".  The binary in obj_dir_ab
  dated from 2026-07-13, the day this file was written, and nothing had rebuilt
  it since -- a gate that cannot build is a gate nobody was running.  Fixed
  here as part of standing it up for the ucore.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import artifact as art            # noqa: E402
from decode_capture import decode  # noqa: E402

ROOT = SW.parent
TB_DIR = ROOT / "hdl" / "tb"
CAPTURE = SW / "testdata" / "largemode_boot_real.hex"

# the integration, shared by both cores and deliberately identical
_PLATFORM = [
    TB_DIR / "tb_ab.sv",
    ROOT / "hdl" / "rtl" / "system_large.sv",
    ROOT / "hdl" / "rtl" / "nec_bus.sv",
    ROOT / "hdl" / "rtl" / "test_mem.sv",
    ROOT / "hdl" / "rtl" / "capture_buf.sv",
    ROOT / "hdl" / "rtl" / "wvec_buf.sv",
    ROOT / "hdl" / "rtl" / "iords_buf.sv",
    ROOT / "hdl" / "rtl" / "hps_axi_slave.sv",
]
# ...and this list must stay a subset of hdl/files.qip's.  Three files had
# drifted out of it (v30_ss_pkg.sv, wvec_buf.sv, iords_buf.sv) and the gate had
# not built since 2026-07-13 as a result.
_CORE_DIR = {"fsm": ROOT / "hdl" / "rtl" / "core",
             "ucore": ROOT / "hdl" / "rtl" / "ucore"}
# the package FIRST -- v30_core.sv and v30_eu.sv both import it.
_CORE_RTL = {
    "fsm": ["v30_ss_pkg.sv", "v30_core.sv", "v30_biu.sv", "v30_eu.sv"],
    "ucore": ["v30u_ss_pkg.sv", "v30_core.sv", "v30u_biu.sv",
              "v30u_ucrom.sv", "v30u_eu.sv"],
}


def core_rtl(core):
    """The package FIRST, then the platform, then the rest of the core.

    ⚠ THE PACKAGE MUST PRECEDE `_PLATFORM`, NOT MERELY THE REST OF THE CORE,
    AND IT DID NOT UNTIL 2026-08-13.  `_CORE_RTL` already listed the package
    first *within the core list*, but that list was appended AFTER `_PLATFORM`
    -- and `system_large.sv` acquired a `v30_ss_pkg::SS_COUNT` reference of its
    own when the M10-SYS save-state freeze probe landed (`system_large.sv:476`,
    inside the `ifndef SYNTHESIS` arm).  Verilator requires a package to be
    predeclared, so from that landing onwards BOTH legs failed elaboration with

        %Error-PKGNODECL: rtl/system_large.sv:476:29: Package/class
        'v30_ss_pkg' not found, and needs to be predeclared

    and the gate registered at "both legs MATCH over 187 rows" could not build
    at all.  MEASURED: moving the package file to the head of the list and
    changing NOTHING else makes it elaborate and link.

    This is the SECOND time this gate has died of its own file list (the first
    is the 2026-07-13 drift recorded above), and both times nothing saw it,
    because a gate that cannot build reports no failures.  The falsifier is the
    gate itself: run it."""
    d = _CORE_DIR[core]
    pkg, rest = _CORE_RTL[core][0], _CORE_RTL[core][1:]
    return [d / pkg] + _PLATFORM + [d / f for f in rest]


def core_obj(core):
    return TB_DIR / ("obj_dir_ab" if core == "fsm" else f"obj_dir_ab_{core}")

T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def recipe(core):
    """WHAT `tb_ab` IS A FUNCTION OF.  `hdl/rtl/ucore/*.hex` is in the list
    because `v30u_ucrom.sv` `$readmemh`s the microcode AT RUN TIME -- the
    binary's behaviour is a function of two files the compiler never opened."""
    rtl, d = core_rtl(core), _CORE_DIR[core]
    inputs = (list(rtl) + sorted(d.glob("*.svh"))
              + [p for p in sorted(d.glob("*.hex")) if p.is_file()])
    # `-DV30_MUXED_AD` is the RIG's bus shape (hdl/rtl/ucore/v30_core.sv, THE
    # BUS SHAPE): `system_large` wires AD/AD_OE/CE_HALF and `nec_bus` is a
    # multiplexed-pin instrument by construction.
    cmd = ["verilator", "--binary", "--timing", "-Wno-fatal",
           "-DV30_MUXED_AD",
           "--top-module", "tb_ab", "-Mdir", art.TOK_OUT, "-o", "tb_ab",
           "-I" + art.TOK_ROOT + "/" + str(d.relative_to(ROOT)),
           *[art.TOK_ROOT + "/" + str(f.relative_to(ROOT)) for f in rtl]]
    return art.Recipe(kind="verilator_binary", artifact=core_obj(core) / "tb_ab",
                      inputs=inputs, command=cmd, tool="verilator",
                      workdir=core_obj(core), label=f"tb_ab/{core}")


def build(core, force=False):
    """Build if the CONTENT KEY moved, then assert the scorer postcondition.

    This gate had NOT BUILT SINCE 2026-07-13 (three files had drifted out of
    its RTL list) and nobody noticed, because a gate that cannot build is a
    gate nobody was running.  The receipt makes the same class visible from the
    other side: an input that drifts out of the declared list changes
    `inputs.sha256`, and one that is missing from the tree hashes as
    `MISSING`."""
    return art.ensure(recipe(core), force=force, quiet=False,
                      why=f"check_ab_sim --core {core}")


def run_core(BIN, nrows, keep=False):
    td = tempfile.mkdtemp(prefix="ab_")
    cap = Path(td) / "core_cap.hex"
    r = subprocess.run([str(BIN), f"+cap={cap}", f"+ncap={nrows + 20}"],
                       capture_output=True, text=True)
    if "AB TESTS PASSED" not in r.stdout:
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit("tb_ab run failed / A-B self-checks failed")
    recs = [decode(int(l, 16)) for l in cap.read_text().split() if l]
    if keep:
        print(f"kept core capture: {cap}", file=sys.stderr)
    # align at RESET release, like check_boot
    rel = next(i for i, d in enumerate(recs) if not d["reset"])
    return recs[rel:]


def load_real():
    recs = [decode(int(l, 16)) for l in CAPTURE.read_text().split() if l]
    rel = next(i for i, r in enumerate(recs) if not r["reset"])
    return recs[rel:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nrows", nargs="?", type=int, default=200)
    ap.add_argument("--core", choices=("fsm", "ucore"), default="ucore",
                    help="RTL engine inside system_large (default: ucore "
                         "since 2026-08-04; 'fsm' is the ARCHIVED core, still "
                         "invokable - docs/notes/fsm_core_archive_2026-08-04.md)")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    n, force, keep = a.nrows, a.build, a.keep

    binp = build(a.core, force)
    real = load_real()
    sim = run_core(binp, n, keep)
    print(f"== check_ab_sim: {a.core} core inside system_large, "
          f"vs the chip's own boot capture ==")
    # P-1: a number with no artifact id is not quotable.
    print(f"   artifact {art.relpath(binp)}  receipt "
          f"{str(art.receipt_id(binp))[:16]}…")

    bad = 0
    for i in range(min(n, len(real), len(sim))):
        r, s = real[i], sim[i]
        mm = []
        if QS_NAME[r["qs"]] != QS_NAME[s["qs"]]:
            mm.append(f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}")
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            mm.append(f"bs {BS_NAME[r['bs_early']]}!={BS_NAME[s['bs_early']]}")
        if i >= 9:
            if r["t_state"] != s["t_state"]:
                mm.append(f"t {T_NAME.get(r['t_state'])}!={T_NAME.get(s['t_state'])}")
            if r["ube_n"] != s["ube_n"]:
                mm.append(f"ube {r['ube_n']}!={s['ube_n']}")
            t = r["t_state"]
            active = r["bs_early"] != 7
            if t == 1 and r["ad_addr"] != s["ad_addr"]:
                mm.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if t in (2, 3) and r["ad_data"] != s["ad_data"]:
                mm.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if t in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                mm.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if t == 2 and active and r["ps"] != s["ps"]:
                mm.append(f"ps {r['ps']:x}!={s['ps']:x}")
        if mm:
            bad += 1
            if bad <= 12:
                print(f"row {i:3d} (release+{i}): " + ", ".join(mm) +
                      f"   [real {T_NAME.get(r['t_state'])} "
                      f"{BS_NAME[r['bs_early']]} {QS_NAME[r['qs']]} "
                      f"{r['ad_addr']:05x}/{r['ad_data']:04x} | core "
                      f"{T_NAME.get(s['t_state'])} {BS_NAME[s['bs_early']]} "
                      f"{QS_NAME[s['qs']]} {s['ad_addr']:05x}/{s['ad_data']:04x}]")

    # loop-period sanity: CODE T1 at 00100 recurrence
    t1s = [i for i, r in enumerate(real[:n])
           if r["t_state"] == 1 and r["bs_early"] == 4
           and r["ad_addr"] == 0x00100]
    t1c = [i for i, r in enumerate(sim[:n])
           if r["t_state"] == 1 and r["bs_early"] == 4
           and r["ad_addr"] == 0x00100]
    print(f"\nloop CODE T1 @00100: real {t1s} core {t1c}")
    print(f"\n{'AB SIM MATCHES CHIP BOOT' if bad == 0 else f'{bad} rows differ'}"
          f" over {min(n, len(real), len(sim))} rows from RESET release")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
