#!/usr/bin/env python3
"""ucsim_smoke - thin driver for sim/v30sim.

Gunzips a v0.x suite file, pipes it to the simulator, tallies pass/fail per
form and prints the first N failures with their diffs.

This is the S1a bring-up driver: it compares RAW final state (registers incl.
raw PSW + RAM).  The full checker with the flags-mask / dont-care policy of
sw/check_core.py::check_case is S2 work.

Usage:
  ucsim_smoke.py [--suite tests/v30/v0.2] [--forms 88,89,00,...] [--all]
                 [--details N] [--trace FORM:IDX]
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


def run_form(suite: Path, form: str, details: int, report: int):
    path = suite / f"{form}.json.gz"
    if not path.exists():
        return None
    raw = gzip.open(path, "rb").read()
    proc = subprocess.run([str(SIM), "run", str(ROM), f"--report={report}"],
                          input=raw, stdout=subprocess.PIPE)
    fails, summary = [], None
    for line in proc.stdout.decode().splitlines():
        rec = json.loads(line)
        if rec.get("summary"):
            summary = rec
        else:
            fails.append(rec)
    return summary, fails[:details]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="tests/v30/v0.2")
    ap.add_argument("--forms", default=None,
                    help="comma-separated form list (default: bring-up set)")
    ap.add_argument("--all", action="store_true",
                    help="every form file in the suite directory")
    ap.add_argument("--details", type=int, default=3)
    ap.add_argument("--report", type=int, default=8)
    ap.add_argument("--trace", default=None, metavar="FORM:IDX")
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
    elif args.forms:
        forms = args.forms.split(",")
    else:
        forms = BRINGUP

    tot_p = tot_f = 0
    bad = []
    for form in forms:
        out = run_form(suite, form, args.details, args.report)
        if out is None:
            print(f"{form:8s} MISSING")
            continue
        summary, fails = out
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
    return 1 if tot_f else 0


if __name__ == "__main__":
    sys.exit(main())
