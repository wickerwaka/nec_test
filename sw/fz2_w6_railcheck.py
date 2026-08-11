#!/usr/bin/env python3
"""fz2 WAVE-6 -- THE 8F GHOST-READ RAIL CLASSIFIER.

Reads the two `fz2_m10.py solve` outputs banked for wave-6 and, for every
SOLVED address-fork seat, reports which named single rail (plain or `& SP`)
reproduces the CHIP address at the fork clock (`d = 0`, where the BIU's own
current-address register stands on the forking cycle's core address).

It exists so the wave-6 BOOKING is re-runnable from an artifact, not retyped:
the derivation's whole content -- "no single rail fits every DERIVE seat, and
the fitting rail tracks the retired-8F pipeline distance" -- falls straight out
of this table.  Nothing here is fitted; the rail set is the physical address
registers the ghost path could read, and the freeze is the one M10 calibrated
(`SSA_B_CUR_ADDR_LO/HI == core_addr`).

    python3 sw/fz2_w6_railcheck.py            # both banked columns
    python3 sw/fz2_w6_railcheck.py --solve X  # any solve JSON
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FZ2 = ROOT / "sw" / "testdata" / "fz2"

# the address registers the ghost read could physically reuse.  IND is the
# BIU's live index; M_EA/R_EA/WB_EA the retained ModR/M addresses; EA_RESIDUE
# and TMPA the ALU-residue rail the CURRENT fitted selector reads.
RAILS = ["IND", "M_EA", "WB_EA", "R_EA", "EA_RESIDUE", "TMPA",
         "TMPB", "PEND_OFF", "OPR"]


def fork_fit(rec):
    """rails (plain / `&SP`) reproducing chip at the fork clock d==0, or None
    if the seat did not reproduce (NOREPRO)."""
    if rec.get("status") != "SOLVED":
        return None
    chip = rec["chip_addr"]
    fz = next((f for f in rec["freezes"] if f["delta"] == 0), None)
    if fz is None:
        return []
    t, sg = fz["terms"], fz["segs"]
    hits = []
    for R in RAILS:
        rv = t.get(R)
        if rv is None:
            continue
        for sv in sg.values():
            for andsp in (False, True):
                v = (rv & t["SP"]) if andsp else rv
                a = ((sv << 4) + v) & 0xFFFFF
                a1 = ((sv << 4) + v + 1) & 0xFFFFF
                if a == chip or a1 == chip:
                    hits.append(R + ("&SP" if andsp else ""))
    return sorted(set(hits))


def klass(hits):
    if hits is None:
        return "NOREPRO"
    rails = {h.replace("&SP", "") for h in hits}
    if not hits:
        return "EMPTY"
    if "IND" in rails and not (rails & {"M_EA", "WB_EA", "R_EA"}):
        return "IND"
    if (rails & {"M_EA", "WB_EA", "R_EA"}) and "IND" not in rails:
        return "M_EA"
    if rails & {"EA_RESIDUE", "TMPA"}:
        return "EA_RESIDUE"
    return "MIXED:" + ",".join(sorted(rails))


def run(path):
    d = json.load(open(path))
    print(f"== {Path(path).name}: {d['n']} seats ==")
    counts = {}
    for r in d["rows"]:
        hits = fork_fit(r)
        k = klass(hits)
        counts[k] = counts.get(k, 0) + 1
        ca = "%05x" % r["chip_addr"] if r.get("chip_addr") is not None else "-----"
        co = "%05x" % r["core_addr"] if r.get("core_addr") is not None else "-----"
        extra = "" if hits is None else "  {%s}" % " ".join(hits)
        print(f"  {r['seed']:<14} chip={ca} core={co}  {k}{extra}")
    print("  --- classes:", ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solve", action="append",
                    help="solve JSON (default: the two banked wave-6 columns)")
    a = ap.parse_args()
    paths = a.solve or [FZ2 / "fz2_w6_solve_derive.json",
                        FZ2 / "fz2_w6_solve_holdout.json"]
    for p in paths:
        run(p)


if __name__ == "__main__":
    main()
