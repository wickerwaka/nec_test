#!/usr/bin/env python3
"""s14_census -- the WOKEN-PREFETCH census (ucsim_t_provenance 25).

OFFLINE.  No board, no new capture.  Reads the four committed HLT delay
sweeps (`tests/v30/s10-hltsweep-w{0,1}`, `tests/v30/s13-hltsweep-w{2,3}`) and,
for the CHIP golden and the MODEL alike, extracts the clocks the woken
prefetch's fate is decided by:

    H       the HALT status display clock
    D       the first CODE status display after H
    T1      the CODE cycle's T1, or NONE if the announcement was DROPPED
    W       the passive clock the announcement was dropped on
    iD/iT1  the first acknowledge's display / T1

and prints them side by side with `A` (the clock the part first samples the
asserted pin) and `F` (the clock the HALT pseudo-cycle frees the bus).
A MEASUREMENT TOOL, not a gate.

    s14_census.py            the whole sweep, all four wait levels
    s14_census.py --band     only |A - H| <= 2, which is where the residue is
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

from timed_gate import run_form, row_check                 # noqa: E402

SUITES = [("tests/v30/s10-hltsweep-w0", 0),
          ("tests/v30/s10-hltsweep-w1", 1),
          ("tests/v30/s13-hltsweep-w2", 2),
          ("tests/v30/s13-hltsweep-w3", 3)]

# 24.8's MEASURED anchor-to-HALT-display series, which 25.5 decomposes into
# two fetch pitches.  Used here only to label each cell with its `A - H`.
HANCHOR = {0: 8, 1: 12, 2: 14, 3: 16}

TS, BS = 8, 7          # tstate / busstat column indices


def feat(rows):
    """-> the clocks above, off one side's row stream."""
    n = len(rows)
    H = next((i for i in range(n) if rows[i][BS] == "HALT"), None)
    if H is None:
        return None
    hT1 = next((i for i in range(H, n) if rows[i][TS] == "T1"), None)
    hT4 = next((i for i in range(hT1, n) if rows[i][TS] == "T4"), None) \
        if hT1 is not None else None
    D = next((i for i in range(H + 1, n) if rows[i][BS] == "CODE"), None)
    codeT1 = None
    if D is not None:
        for i in range(D, min(n, D + 12)):
            if rows[i][TS] == "T1" and rows[i][BS] == "CODE":
                codeT1 = i
                break
            if rows[i][BS] != "CODE" and i > D:
                break
    W = None
    if D is not None and codeT1 is None:
        W = next((i for i in range(D, n) if rows[i][BS] != "CODE"), None)
    iD = next((i for i in range(H + 1, n) if rows[i][BS] == "INTA"), None)
    iT1 = None
    if iD is not None:
        iT1 = next((i for i in range(iD, n)
                    if rows[i][TS] == "T1" and rows[i][BS] == "INTA"), None)
    return dict(H=H, hT1=hT1, hT4=hT4, D=D, codeT1=codeT1, W=W, iD=iD, iT1=iT1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", action="store_true",
                    help="only the cells with |A - H| <= 2")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    print("%-9s %-2s %-3s %-4s %-3s %-3s %-4s | %-23s | %-23s | ndiff"
          % ("form", "N", "d", "A-H", "A", "F", "F-D",
             "CHIP  D  T1   W  iD iT1", "MODEL D  T1   W  iD iT1"))
    out = []
    for sdir, w in SUITES:
        suite = ROOT / sdir
        for form in ("HLT.INT", "HLT.RES"):
            p = suite / f"{form}.json.gz"
            if not p.exists():
                continue
            cases = json.load(gzip.open(p))
            sims = run_form(cases, w, False)
            for i, c in enumerate(cases):
                ok, nmm, _h, mrows, _e, _i0, _i1 = row_check(c, sims.get(i))
                g = feat(c["cycles"])
                if g is None:
                    continue
                m = feat(mrows) if ok else None
                d = c["evt"]["delay"]
                AH = d - (HANCHOR[w] - 2)
                if args.band and abs(AH) > 2:
                    continue
                A = g["H"] + AH
                F = (g["hT4"] + 1) if g["hT4"] is not None else None

                def f(x):
                    return "  -" if x is None else "%3d" % x

                def side(s):
                    return " " * 23 if not s else "%s %s %s %s %s" % (
                        f(s["D"]), f(s["codeT1"]), f(s["W"]), f(s["iD"]),
                        f(s["iT1"]))
                print("%-9s %-2d %-3d %-4d %-3d %-3s %-4s | %-23s | %-23s | %d"
                      % (form, w, d, AH, A, f(F),
                         "-" if (F is None or g["D"] is None)
                         else str(F - g["D"]),
                         side(g), side(m), nmm or 0))
                out.append(dict(form=form, w=w, d=d, AH=AH, A=A, F=F,
                                ndiff=nmm, chip=g, model=m))
    if args.report:
        json.dump(out, open(args.report, "w"), indent=1)


main()
