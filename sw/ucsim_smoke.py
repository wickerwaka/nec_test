#!/usr/bin/env python3
"""ucsim_smoke - thin driver for sim/v30sim.

Gunzips a v0.x suite file, pipes it to the simulator, tallies pass/fail per
form and prints the first N failures with their diffs.

This is the S1a bring-up driver: it compares RAW final state (registers incl.
raw PSW + RAM).  The full checker with the flags-mask / dont-care policy of
sw/check_core.py::check_case is S2 work.

Usage:
  ucsim_smoke.py [--suite tests/v30/v0.2] [--forms 88,89,00,...] [--all]
                 [--s1b] [--details N] [--trace FORM:IDX]
"""

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"

# The S1a bring-up families (campaign plan, gate P1).
BRINGUP = [
    # MOV
    "88", "89", "8A", "8B", "B0", "B8", "C6.0", "C7.0",
    "A0", "A1", "A2", "A3",
    # ALU rm,r + acc,imm
    "00", "01", "02", "03", "04", "05",
    "30", "31", "38", "39", "3C",
    # INC/DEC
    "40", "48", "FE.0",
    # PUSH/POP
    "50", "58", "8F.0", "06", "0E", "1E", "07", "17", "1F",
]

# The S1b families (campaign plan, gate P1 second half): flow, the internal
# routine page, and the arithmetic groups.
S1B = (
    # S1a handoff: OP8/OP8b, group OPC select, NOT/NEG, CWD, SAHF
    [f"83.{i}" for i in range(8)]
    + [f"80.{i}" for i in range(1, 8)]
    + [f"81.{i}" for i in range(1, 8)]
    + ["F6.2", "F6.3", "F7.2", "F7.3", "99", "9E"]
    # shifts / rotates + the internal SHIFT routine
    + [f"{op}.{i}" for op in ("C0", "C1", "D0", "D1", "D2", "D3")
       for i in range(8)]
    # multiply / divide + MULADJ MULX IMUL IMULI IDIV IDIV2
    + [f"F6.{i}" for i in range(4, 8)]
    + [f"F7.{i}" for i in range(4, 8)]
    + ["69", "6B"]
    # BCD
    + ["27", "2F", "37", "3F", "D4", "D5"]
    # flow / stack / internal routines
    + ["9A", "CA", "CB", "CC", "CD", "CE", "CF", "C8", "C9",
       "60", "61", "62", "6A", "E0", "E1", "E2", "E3", "D7",
       "E4", "E5", "EC", "ED"]
)


# The S1c families (campaign plan, gate P1 close-out): the whole 0F page.
S1C = (
    [f"0F1{d}" for d in "0123456789ABCDEF"]      # TEST1/CLR1/SET1/NOT1
    + ["0F20", "0F22", "0F26"]                   # ADD4S/SUB4S/CMP4S
    + ["0F28", "0F2A"]                           # ROL4/ROR4
    + ["0F31", "0F33", "0F39", "0F3B"]           # INS/EXT
)


def run_form(suite: Path, form: str, details: int, report: int,
             alu_hw: bool = False):
    path = suite / f"{form}.json.gz"
    if not path.exists():
        return None
    raw = gzip.open(path, "rb").read()
    argv = [str(SIM), "run", str(ROM), f"--report={report}"]
    if alu_hw:
        argv.append("--alu-hw-report")
    proc = subprocess.run(argv, input=raw, stdout=subprocess.PIPE)
    fails, summary, hw = [], None, None
    for line in proc.stdout.decode().splitlines():
        rec = json.loads(line)
        if rec.get("summary"):
            summary = rec
        elif rec.get("alu_hw_report"):
            hw = rec
        else:
            fails.append(rec)
    return summary, fails[:details], hw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="tests/v30/v0.2")
    ap.add_argument("--forms", default=None,
                    help="comma-separated form list (default: bring-up set)")
    ap.add_argument("--s1b", action="store_true",
                    help="the S1b family set (flow + internal page + arith)")
    ap.add_argument("--s1c", action="store_true",
                    help="the S1c family set (the whole 0F page)")
    ap.add_argument("--all", action="store_true",
                    help="every form file in the suite directory")
    ap.add_argument("--details", type=int, default=3)
    ap.add_argument("--report", type=int, default=8)
    ap.add_argument("--trace", default=None, metavar="FORM:IDX")
    ap.add_argument("--alu-hw", action="store_true",
                    help="ALU-hardware flag attribution audit (P1 sufficiency)")
    args = ap.parse_args()

    suite = (ROOT / args.suite) if not Path(args.suite).is_absolute() \
        else Path(args.suite)

    if args.trace:
        form, _, idx = args.trace.partition(":")
        raw = gzip.open(suite / f"{form}.json.gz", "rb").read()
        subprocess.run([str(SIM), "trace", str(ROM), idx or "0"], input=raw)
        return 0

    if args.all:
        forms = sorted(p.name[:-len(".json.gz")]
                       for p in suite.glob("*.json.gz"))
    elif args.s1b:
        forms = S1B
    elif args.s1c:
        forms = S1C
    elif args.forms:
        forms = args.forms.split(",")
    else:
        forms = BRINGUP

    tot_p = tot_f = 0
    bad = []
    hw_tot = {}
    for form in forms:
        out = run_form(suite, form, args.details, args.report, args.alu_hw)
        if out is None:
            print(f"{form:8s} MISSING")
            continue
        summary, fails, hw = out
        if hw:
            for k, v in hw.items():
                if k != "alu_hw_report":
                    hw_tot[k] = hw_tot.get(k, 0) + v
        p, f = summary["pass"], summary["fail"]
        tot_p += p
        tot_f += f
        flag = "ok " if f == 0 else "FAIL"
        print(f"{form:8s} {flag} {p}/{p + f}")
        if f:
            bad.append(form)
            for rec in fails:
                print(f"    idx {rec['idx']:4d} {rec['name']}"
                      f"\n        {rec['diff']}")
    print(f"\nTOTAL pass={tot_p} fail={tot_f}"
          + (f"  failing forms: {','.join(bad)}" if bad else ""))
    if hw_tot:
        n = hw_tot["cases"]
        print("\nALU-hardware flag attribution (non-emergent behaviours):")
        print(f"  cases                         {n}")
        print(f"  cases whose FINAL PSW keeps   {hw_tot['cases_any']} "
              f"({100.0 * hw_tot['cases_any'] / n:.2f}%)")
        print("  at least one such bit")
        for key, name in (("shift_v", "per-step shift/rotate V law"),
                          ("logic_ac", "logic-op AC = 0"),
                          ("bcd", "BCD correction")):
            print(f"  {name:30s} commits={hw_tot[key + '_commits']:8d} "
                  f"cases={hw_tot[key + '_cases']:7d} "
                  f"final-PSW bits={hw_tot[key + '_bits']:8d}")
    return 1 if tot_f else 0


if __name__ == "__main__":
    sys.exit(main())
