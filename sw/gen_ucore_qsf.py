#!/usr/bin/env python3
"""gen_ucore_qsf -- derive hdl/nec_test_ucore.qsf from hdl/nec_test.qsf.

The two cores are drop-in alternatives selected by the RTL FILE LIST, so the
ucore bitstream is a Quartus REVISION of the same project rather than a second
project: `quartus_sh --flow compile nec_test -c nec_test_ucore`.

The .qsf cannot choose its own file list -- Quartus reads it with a restricted
settings parser that has no `if` (measured: Error 125048 on every line of a Tcl
conditional).  So the revision file is GENERATED from the FSM one by changing
exactly two things:

    source files.qip            ->  source files_ucore.qip
    PROJECT_OUTPUT_DIRECTORY    ->  output_files_ucore

...and nothing else, so a settings change made for the FSM build cannot be
silently missing from the ucore build.  `--check` re-derives and compares,
which is the gate: a stale revision file is a build comparing two things that
differ by more than the core.

NOTE, measured: **Quartus REWRITES the revision .qsf it compiles**, appending
the assignments it picked up from `source sys/sys.tcl` (the ~180 pin locations
and the PRE_FLOW_SCRIPT).  So this file must be regenerated before a build and
`--check` must be run BEFORE compiling, not after -- a post-build `--check`
failure is Quartus's materialisation, not drift.  Regenerating is always safe:
everything Quartus appends is re-derived from the sourced .tcl anyway.

    sw/gen_ucore_qsf.py [--check]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "hdl" / "nec_test.qsf"
DST = ROOT / "hdl" / "nec_test_ucore.qsf"

HEADER = """# ---------------------------------------------------------------------------
#  GENERATED FILE -- do not edit.  Regenerate with `sw/gen_ucore_qsf.py`.
#
#  The `nec_test_ucore` REVISION: hdl/nec_test.qsf with the core's file list
#  swapped for the ucore's and its own output directory.  Everything else --
#  device, pins, timing settings, optimisation settings, VERILOG_MACROs -- is
#  copied verbatim, so the two-bitstream A/B differs by the CORE and by nothing
#  else.  `sw/gen_ucore_qsf.py --check` is the gate on that claim.
#
#      quartus_sh --flow compile nec_test -c nec_test_ucore
# ---------------------------------------------------------------------------
"""


def derive(text):
    out, seen_src, seen_out = [], 0, 0
    for ln in text.splitlines():
        s = ln.strip()
        if s == "source files.qip":
            out.append("source files_ucore.qip")
            seen_src += 1
        elif s.startswith("set_global_assignment -name PROJECT_OUTPUT_DIRECTORY"):
            out.append("set_global_assignment -name PROJECT_OUTPUT_DIRECTORY "
                       "output_files_ucore")
            seen_out += 1
        else:
            out.append(ln)
    if seen_src != 1:
        sys.exit(f"gen_ucore_qsf: expected exactly one 'source files.qip' in "
                 f"{SRC}, found {seen_src}")
    if seen_out != 1:
        sys.exit(f"gen_ucore_qsf: expected exactly one PROJECT_OUTPUT_DIRECTORY "
                 f"in {SRC}, found {seen_out}")
    return HEADER + "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the generated file is out of date")
    a = ap.parse_args()
    want = derive(SRC.read_text())
    if a.check:
        have = DST.read_text() if DST.exists() else ""
        if have != want:
            sys.exit(f"gen_ucore_qsf: {DST} is STALE -- regenerate it "
                     f"(the two bitstreams would differ by more than the core)")
        print(f"gen_ucore_qsf: {DST.name} is up to date")
        return
    DST.write_text(want)
    print(f"gen_ucore_qsf: wrote {DST}")


if __name__ == "__main__":
    main()
