#!/usr/bin/env python3
"""s10_analyze -- OFFLINE readings of the S10 captures (ucsim_t_provenance 21).

NOT a gate: a measurement tool.  Every number it prints is read off the CHIP's
own golden rows with no model in the loop, except where a sub-command says
otherwise in its own name (`--vs-sim`).

  inta     the acknowledge geometry: run length, INTA1->INTA2 gap, Tw on the
           acknowledge.  This is S1's registered discriminator (21.0 S1 pred 3:
           bus-keyed 7+N_ack vs cadence-keyed 7).
  addr     M15 under waits: does the acknowledge cycle drive an address?
  chain    S4: the chained-withdrawal magnitude, chain length read off the
           golden's own bus trace.
"""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

# golden row columns (check_core.COL_NAME)
C_PINS, C_BUS, C_SEG, C_MEMCMD, C_IOCMD, C_UBE, C_DATA, C_STAT, C_T, C_QOP, C_QB = range(11)


def load(suite, form):
    p = ROOT / suite / f"{form}.json.gz"
    if not p.exists():
        return None
    return json.load(gzip.open(p))


def forms_of(suite):
    d = ROOT / suite
    return sorted(p.name[:-8] for p in d.glob("*.json.gz")) if d.is_dir() else []


def runs_of(rows):
    """INTA runs in a golden row window.  Each run is a list of per-cycle dicts
    {t1, tw, addr_t1, ube_t1, seg}: pins only, no model."""
    runs, cur, cyc = [], [], None
    for i, r in enumerate(rows):
        if r[C_T] == "T1":
            cyc = {"stat": r[C_STAT], "t1": i, "tw": 0,
                   "addr_t1": r[C_BUS], "ube_t1": r[C_UBE]}
            if r[C_STAT] == "INTA":
                cur.append(cyc)
            elif cur:
                runs.append(cur)
                cur = []
        elif cyc is not None and r[C_T] == "Tw":
            cyc["tw"] += 1
    if cur:
        runs.append(cur)
    return runs


def cmd_inta(args):
    print(f"=== INTA geometry :: {args.suite} ===")
    gaps = defaultdict(Counter)
    lens = Counter()
    twc = Counter()
    per_form = {}
    for form in (args.forms or forms_of(args.suite)):
        ts = load(args.suite, form)
        if not ts:
            continue
        g = Counter()
        n_ack = 0
        for t in ts:
            for run in runs_of(t["cycles"]):
                lens[len(run)] += 1
                n_ack += 1
                twc[run[0]["tw"]] += 1
                if len(run) >= 2:
                    gap = run[1]["t1"] - run[0]["t1"]
                    g[(run[0]["tw"], gap)] += 1
                    gaps[run[0]["tw"]][gap] += 1
        per_form[form] = (n_ack, g)
        if n_ack:
            print(f"  {form:9s} acknowledges={n_ack:4d}  "
                  f"(Tw_ack,gap) -> {dict(sorted(g.items()))}")
    print(f"\n  INTA run-length histogram : {dict(sorted(lens.items()))}")
    print(f"  Tw on the FIRST acknowledge: {dict(sorted(twc.items()))}")
    print("\n  --- the registered discriminator (21.0 S1 prediction 3) ---")
    print("   Tw_ack | gap histogram          | reading A (7+N) | reading B (7)")
    for tw in sorted(gaps):
        hist = dict(sorted(gaps[tw].items()))
        a, b = 7 + tw, 7
        tot = sum(hist.values())
        na, nb = hist.get(a, 0), hist.get(b, 0)
        print(f"   {tw:6d} | {str(hist):22s} | {na:5d}/{tot:<5d}   | {nb:5d}/{tot}")
    if gaps:
        allA = all(set(h) == {7 + tw} for tw, h in gaps.items())
        allB = all(set(h) == {7} for h in gaps.values())
        verdict = ("READING A -- BUS-KEYED (gap = 7 + N_ack)" if allA else
                   "READING B -- CADENCE-KEYED (gap = 7, wait-invariant)" if allB
                   else "NEITHER -- a new term; reported as a FINDING")
        print(f"\n  VERDICT: {verdict}")


def cmd_addr(args):
    """M15 under waits: AD15-0 float through the commit display and T1 and
    AD19-16 are driven to 0, so the acknowledge's T1 'address' must be the
    STALE value the previous data phase left, never a fresh address, and the
    upper nibble must be 0."""
    print(f"=== M15 (the acknowledge drives no address) :: {args.suite} ===")
    upper = Counter()
    stale_ok = stale_bad = 0
    for form in (args.forms or forms_of(args.suite)):
        ts = load(args.suite, form)
        if not ts:
            continue
        for t in ts:
            rows = t["cycles"]
            for run in runs_of(rows):
                for c in run:
                    upper[(c["addr_t1"] >> 16) & 0xF] += 1
                    prev = None
                    for j in range(c["t1"] - 1, -1, -1):
                        if rows[j][C_T] in ("T3", "Tw", "T4"):
                            prev = rows[j][C_DATA]
                            break
                    if prev is not None and (c["addr_t1"] & 0xFFFF) == (prev & 0xFFFF):
                        stale_ok += 1
                    else:
                        stale_bad += 1
    print(f"  AD19-16 on the acknowledge T1: {dict(sorted(upper.items()))}"
          f"   (M15 predicts {{0: all}})")
    print(f"  AD15-0 == the last data phase (floating/stale): "
          f"{stale_ok} yes / {stale_bad} no")
    print("  VERDICT: " + ("M15 HOLDS under waits" if set(upper) == {0} and stale_bad == 0
                           else "M15 does NOT hold as stated -- a FINDING"))


def cmd_chain(args):
    """S4: chain length = the number of completed string stores before the
    acknowledge, read off the golden's own bus trace -- the SAME policy the
    functional replay uses (sim/pin_replay.h), not re-invented here."""
    print("=== S4 chained-withdrawal census ===")
    tab = defaultdict(Counter)
    for suite, waits in args.suites:
        ts = load(suite, "INT.F3AA")
        if not ts:
            print(f"  {suite}: no INT.F3AA")
            continue
        for t in ts:
            rows = t["cycles"]
            runs = runs_of(rows)
            if not runs:
                continue
            ack = runs[0][0]["t1"]
            n_st = 0
            last_t4 = None
            for i, r in enumerate(rows):
                if i >= ack:
                    break
                if r[C_T] == "T1" and r[C_STAT] == "MEMW":
                    n_st += 1
                if r[C_T] == "T4" and i < ack:
                    last_t4 = i
            gap = None if last_t4 is None else ack - last_t4
            tab[(waits, n_st)][gap] += 1
    print("  waits | chain | (last store T4 -> INTA1 T1) gap histogram")
    for (w, n) in sorted(tab):
        if n == 0:
            continue
        print(f"  {w:5d} | {n:5d} | {dict(sorted((k, v) for k, v in tab[(w, n)].items() if k is not None))}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("inta", cmd_inta), ("addr", cmd_addr)):
        p = sub.add_parser(name)
        p.add_argument("--suite", default="tests/v30/v0.1-w1evt")
        p.add_argument("--forms", nargs="*")
        p.set_defaults(fn=fn)
    p = sub.add_parser("chain")
    p.add_argument("--suites", nargs="+", default=[])
    p.set_defaults(fn=cmd_chain)
    a = ap.parse_args()
    if a.cmd == "chain":
        a.suites = [(s.split(":")[0], int(s.split(":")[1])) for s in a.suites]
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
