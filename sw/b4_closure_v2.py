#!/usr/bin/env python3
"""B4 closure re-analysis — NON-CIRCULAR, pre-registered (P1 review blocker 1).

The prior cmd_sweep excused WANDER by "occupancy varied across k", which the
review judged circular (occ-variation excusal can absorb a hidden variable
correlated with occupancy). This re-analysis instead MATCHES observations on the
full bus-observable causal state and fails on ANY within-matched-cell non-phase
variation.

============================ PRE-REGISTERED (before running) ===================
MATCH KEY (causal state): (seed, eu_ord, occ, fill_rising_sat, w). Only events
  sharing this exact key are compared. eu_ord=-1 (non-EU-preceded resume) is
  EXCLUDED and reported separately, not counted as a pass.
PHASE: k-parity (k & 1) -- the leading bus-grid phase the sweep varies.
TESTABLE CELL: a (match-key, parity) with >=2 distinct k values (so phase-fixed
  variation is observable). Cells with <2 k at a parity are UNTESTABLE and
  reported separately, not counted as pass.
FALSIFIER (the closure over (grid_phase, occ, fill) is REFUTED if):
  >=1 TESTABLE cell has >1 distinct resume gap value at fixed (match-key, parity).
  Such a cell = same seed, structural ordinal, occupancy, fill, wait, and phase
  parity, yet different resume gap => a hidden variable beyond (phase, occ, fill).
SECONDARY (cross-wait) diagnostic: for a match on (occ, fill_rising_sat, parity)
  ACROSS w in {1,3}, if the gap sets are disjoint the wait regime carries info
  beyond (phase,occ,fill) -- reported, informative (grid_phase is meant to encode
  the stretch, so a clean cross-wait match strengthens the closure).
VERDICT: GO iff 0 testable-cell violations. Any violation => NO-GO (routes to the
  user per the plan). CONSTANT/CLEAN-PARITY counting is NOT used as the verdict.
================================================================================
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "sw/b4_resume_events.json"


def main():
    ev = json.loads(EV.read_text())
    # match cells: (seed, eu_ord, occ, fill_rising_sat, w) -> {parity: {k: gap}}
    cells = defaultdict(lambda: defaultdict(dict))
    excluded_nonEU = 0
    for e in ev:
        if e["eu_ord"] < 0:
            excluded_nonEU += 1
            continue
        key = (e["seed"], e["eu_ord"], e["occ"],
               e["fill"]["rising_sat"], e["w"])
        cells[key][e["k"] & 1][e["k"]] = e["gap"]

    testable = 0
    untestable = 0
    clean = 0
    violations = []
    for key, byp in cells.items():
        for parity, kg in byp.items():
            if len(kg) < 2:
                untestable += 1
                continue
            testable += 1
            gaps = set(kg.values())
            if len(gaps) > 1:
                violations.append((key, parity, sorted(gaps), dict(kg)))
            else:
                clean += 1

    print("=== B4 NON-CIRCULAR CLOSURE (pre-registered) ===")
    print(f"events={len(ev)}  excluded(non-EU eu_ord=-1)={excluded_nonEU}")
    print(f"match-cells={len(cells)}  testable(>=2 k at a parity)={testable}  "
          f"untestable(<2 k)={untestable}")
    print(f"CLEAN (gap constant at fixed match-key,parity)={clean}  "
          f"VIOLATIONS={len(violations)}")
    if violations:
        print("\nFALSIFIED -- hidden variable beyond (phase,occ,fill):")
        for key, parity, gaps, kg in violations[:25]:
            s, eo, occ, frs, w = key
            print(f"  seed{s} eu_ord{eo} occ{occ} fill_rs{frs} w{w} par{parity}: "
                  f"gaps={gaps}  k->gap={kg}")

    # secondary cross-wait diagnostic (occ, fill_rs, parity) across w1/w3
    cw = defaultdict(lambda: defaultdict(set))
    for e in ev:
        if e["eu_ord"] < 0 or e["w"] not in (1, 3):
            continue
        cw[(e["occ"], e["fill"]["rising_sat"], e["k"] & 1)][e["w"]].add(e["gap"])
    cross_disjoint = 0
    cross_tot = 0
    for key, byw in cw.items():
        if 1 in byw and 3 in byw:
            cross_tot += 1
            if byw[1].isdisjoint(byw[3]):
                cross_disjoint += 1
    print(f"\nCROSS-WAIT diagnostic (occ,fill,parity across w1/w3): "
          f"{cross_tot} matched, {cross_disjoint} fully disjoint "
          f"(disjoint => wait carries info beyond phase/occ/fill).")

    verdict = "GO" if not violations else "NO-GO"
    print(f"\n=== B4_V2_VERDICT: {verdict}  (violations={len(violations)}) ===")
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
