#!/usr/bin/env python3
"""f20_cell -- THE FLASH #20 DIRECTED-CELL SCORER.

WHY IT EXISTS.  The `8F` ghost LAUNCH relocation (`ef19010e63`) and the F-B'
split law (`292f30bcf8`) have never been in a bitstream.  Their primary
evidence is `ghost_pred_cell`'s 528-cell directed grid, and every figure of it
that exists today -- `identical 398 / different 122` -- was taken on `tb_sys
ret`, a Verilated model, with `--no-fabric-era-guard` in force on everything
else in the wave.  **SILICON MATCH is the only correctness bar** (CLAUDE.md,
2026-08-04), and an offline column is not silicon.

THIS SCORER PUTS THREE COLUMNS OF THE SAME 528 CELLS BESIDE EACH OTHER:

    chip      the SOCKETED PART, `use_core=False`               -- SILICON
    fabric    the ucore INSIDE THE FPGA, `use_core=True`        -- the landing
    core      the ucore on `tb_sys ret`, Verilator, offline     -- the model

and reports three comparisons, of which only the first two say anything about
the landing:

    CHIP vs FABRIC   the relocation's claim, ON SILICON.  Registered 398/122.
    FABRIC vs CORE   does the synthesised core do what the model said it does?
                     Registered 528/528 identical -- this is the sharpest form
                     of "is the relocation true in fabric", because it is an
                     ENGINE-vs-ENGINE identity with no golden in it.
    CHIP vs CORE     the offline column, re-derived here so the three numbers
                     are printed by one tool from one set of tables.

AND ONE IDENTITY CHECK THAT IS NOT A COMPARISON: `--chip-ref DIR` asserts the
freshly captured socket column is BYTE-IDENTICAL, per cell `sha256`, to a
banked one.  Silicon does not change when an FPGA is reflashed; if that row
moves, the finding is about the rig, not about the landing.

NON-VACUITY.  `--null N` perturbs N fabric cells' ghost addresses in memory
before scoring.  It must move CHIP-vs-FABRIC and FABRIC-vs-CORE by exactly N.
Run it before the board is touched; a scorer that cannot fail is not a scorer.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sw" / "testdata" / "ghost-pred"


def load(d):
    p = Path(d)
    if p.is_dir():
        p = p / "table.json"
    if not p.exists():
        raise SystemExit(f"f20_cell: no table at {p}")
    return json.loads(p.read_text())


def by_cell(tab):
    return {r["cell"]: r for r in tab}


def compare(a, b):
    """(same, diff, [(cell, a_label, b_label)]) over cells both legs scored."""
    A, B = by_cell(a), by_cell(b)
    same, diffs = 0, []
    for k in sorted(set(A) & set(B)):
        x, y = A[k], B[k]
        if not (x.get("ok") and y.get("ok")):
            continue
        if x["ghost_addr"] == y["ghost_addr"]:
            same += 1
        else:
            diffs.append((k, x.get("mode_label"), y.get("mode_label")))
    return same, len(diffs), diffs


def per_leg(a, b):
    A, B = by_cell(a), by_cell(b)
    tot, hit = Counter(), Counter()
    for k in sorted(set(A) & set(B)):
        x, y = A[k], B[k]
        if not (x.get("ok") and y.get("ok")):
            continue
        tot[x["leg"]] += 1
        if x["ghost_addr"] == y["ghost_addr"]:
            hit[x["leg"]] += 1
    return tot, hit


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chip", default=str(OUT / "board"))
    ap.add_argument("--fabric", default=str(OUT / "fabric"))
    ap.add_argument("--core", default=str(OUT / "core"))
    ap.add_argument("--chip-ref", default=None,
                    help="a banked socket column the fresh one must be "
                         "BYTE-IDENTICAL to, per-cell sha256")
    ap.add_argument("--null", type=int, default=0,
                    help="perturb N fabric cells in memory (non-vacuity)")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    chip = load(a.chip)
    core = load(a.core)
    fab = load(a.fabric) if Path(a.fabric).exists() or \
        (Path(a.fabric) / "table.json").exists() else []

    if a.null and fab:
        n = 0
        for r in fab:
            if r.get("ok") and r.get("ghost_addr") and n < a.null:
                r["ghost_addr"] = [(v ^ 1) for v in r["ghost_addr"]]
                r["mode_label"] = "NULLED"
                n += 1
        print(f"  *** --null {a.null}: perturbed {n} fabric cells "
              f"IN MEMORY (nothing on disk is touched) ***\n")

    out = {"tool": "sw/f20_cell.py",
           "cells": {"chip": len(chip), "core": len(core), "fabric": len(fab)}}

    print("=== STRUCTURE")
    for nm, tb in (("chip  (socket, silicon)", chip),
                   ("fabric(ucore in FPGA)", fab),
                   ("core  (tb_sys ret)", core)):
        if not tb:
            print(f"  {nm:<26} ABSENT")
            continue
        print(f"  {nm:<26} {len(tb):>4} cells, "
              f"{sum(1 for r in tb if r.get('ok')):>4} structurally valid")

    if a.chip_ref:
        ref = by_cell(load(a.chip_ref))
        cur = by_cell(chip)
        both = sorted(set(ref) & set(cur))
        moved = [k for k in both if ref[k]["sha256"] != cur[k]["sha256"]]
        print(f"\n=== THE SOCKET COLUMN vs THE BANKED ONE (byte identity)")
        print(f"  {len(both) - len(moved)} / {len(both)} cells "
              f"BYTE-IDENTICAL, {len(moved)} moved")
        for k in moved[:20]:
            print(f"    MOVED {k}  {ref[k]['sha256'][:16]} -> "
                  f"{cur[k]['sha256'][:16]}")
        out["chip_vs_banked"] = {"identical": len(both) - len(moved),
                                 "moved": len(moved), "moved_cells": moved}

    pairs = [("CHIP vs FABRIC   (the landing, ON SILICON)", chip, fab),
             ("FABRIC vs CORE   (synthesised vs modelled)", fab, core),
             ("CHIP vs CORE     (the offline column)", chip, core)]
    res = {}
    for name, A, B in pairs:
        if not (A and B):
            continue
        same, diff, diffs = compare(A, B)
        key = name.split("(")[0].strip().replace(" ", "_").lower()
        res[key] = {"same": same, "diff": diff}
        print(f"\n=== {name}")
        print(f"  identical ghost addresses: {same}   different: {diff}")
        seen = set()
        for k, x, y in diffs:
            sig = (k.split("_w")[0], x, y)
            if sig in seen:
                continue
            seen.add(sig)
            print(f"    {k:<20} A={x:<14} B={y}")
        if len(diffs) and len(seen) < len(diffs):
            print(f"    ... {len(diffs)} differing cells in "
                  f"{len(seen)} distinct (leg, label) signatures")
    out["compare"] = res

    if chip and fab:
        tot, hit = per_leg(chip, fab)
        print("\n=== CHIP vs FABRIC, PER LEG")
        for leg in sorted(tot, key=lambda x: -tot[x] if False else x):
            print(f"  {leg:<9} {hit[leg]:>3} / {tot[leg]:<3}")
        out["per_leg_chip_vs_fabric"] = {k: [hit[k], tot[k]] for k in tot}

    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
