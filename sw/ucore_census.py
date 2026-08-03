#!/usr/bin/env python3
"""Summarise a check_core.py --core ucore run log into a census.

Reads the per-form summary lines of a check_core run (stdout captured to a
file) and prints a table grouped by first-divergence signature.  Measurement
tool, NOT a gate.
"""
import re
import sys
from collections import Counter, defaultdict

LINE = re.compile(
    r"^(\S+): (\d+)/(\d+) full\s+\(cycles (\d+), arch (\d+)\)(?:\s+first-div: (.*))?$")


def parse(path):
    forms = {}
    with open(path) as f:
        for line in f:
            m = LINE.match(line.rstrip())
            if not m:
                continue
            form, full, tot, cyc, arch, fd = m.groups()
            if form == "TOTAL":
                continue
            forms[form] = {"full": int(full), "tot": int(tot),
                           "cyc": int(cyc), "arch": int(arch),
                           "fd": fd or ""}
    return forms


def sig(rec):
    """Coarse family signature from the first-divergence string."""
    fd = rec["fd"]
    if rec["full"] == rec["tot"]:
        return "GREEN"
    if "fewer than 2 F pops" in fd or "no sim output" in fd:
        return "HANG"
    if "SIM FAILED" in fd:
        return "SIMFAIL"
    if rec["cyc"] == rec["tot"]:
        return "ARCH-ONLY"
    # leading column name of the most common first divergence
    cols = re.findall(r"'(\w+)'", fd)
    return ("DIV:" + cols[0]) if cols else ("DIV:" + fd[:24])


def main():
    a = parse(sys.argv[1])
    b = parse(sys.argv[2]) if len(sys.argv) > 2 else None
    groups = defaultdict(list)
    for form, rec in a.items():
        groups[sig(rec)].append(form)
    tot_full = sum(r["full"] for r in a.values())
    tot_all = sum(r["tot"] for r in a.values())
    print(f"forms {len(a)}  cases {tot_full}/{tot_all} full  "
          f"cycle-exact forms "
          f"{sum(1 for r in a.values() if r['cyc'] == r['tot'])}  "
          f"green forms {sum(1 for r in a.values() if r['full'] == r['tot'])}")
    for k in sorted(groups, key=lambda k: -len(groups[k])):
        fs = sorted(groups[k])
        print(f"\n== {k}  ({len(fs)} forms)")
        for i in range(0, len(fs), 12):
            print("   " + " ".join(f"{x:<8}" for x in fs[i:i + 12]))
    if b:
        print("\n== DELTA vs", sys.argv[2])
        reg, imp = [], []
        for form in sorted(set(a) | set(b)):
            fa = a.get(form, {}).get("full", -1)
            fb = b.get(form, {}).get("full", -1)
            if fa < fb:
                reg.append(f"{form} {fb}->{fa}")
            elif fa > fb:
                imp.append(f"{form} {fb}->{fa}")
        print("REGRESSED:", ", ".join(reg) if reg else "none")
        print("IMPROVED :", ", ".join(imp) if imp else "none")
        print(f"TOTAL: {sum(r['full'] for r in b.values())} -> {tot_full}")


if __name__ == "__main__":
    main()
