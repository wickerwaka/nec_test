#!/usr/bin/env python3
"""fz2_p2_seats -- the P2/P3 SEAT LISTS, DERIVED FROM THE LEDGER, and the
BEFORE/AFTER comparison of two `fz2_c1_rescore` outputs over them.

A BOOKKEEPING TOOL, NOT A GATE.  The seat lists are derived from the failure
ledger's own `family` field so they cannot be hand-curated after a result:

    M2  = family `C1 vector-1 trap MISSED by core` + `B2 HALT entry (one leg
          only)`                                                   -- 20 seats
    M3  = the two NEW/UNCLASSIFIED over-fires named in the commissioning brief
    M4  = families `C2 INTA-vectored delivery`, `C3 NMI(vec2) entry`,
          `C4 other-vector delivery`                               -- 12 rows,
          of which the brief's 11 are C2 + one; both are printed

    python3 sw/fz2_p2_seats.py list
    python3 sw/fz2_p2_seats.py cmp BEFORE.json AFTER.json
"""
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

M3_SEEDS = ("fz2e/517043", "fz2e/531009")
GATE64_1 = ("fz2c/406063", "fz2c/410047", "fz2e/518053", "fz2e/535027")
C2A_KEEP = ("fz2c/404040",)


def ledger_path():
    d = ROOT / "sw/testdata/fz2"
    return os.environ.get("FZ2_LEDGER") or str(
        d / sorted(f for f in os.listdir(d)
                   if f.startswith("fz2_failure_ledger") and f.endswith(".json"))[-1])


def led():
    return {f["seed"]: f for f in json.load(open(ledger_path()))["failures"]}


def seats():
    L = led()
    fam = collections.defaultdict(list)
    for s, f in L.items():
        fam[f["family"]].append(s)
    m2 = sorted(fam["C1 vector-1 trap MISSED by core"]
                + fam["B2 HALT entry (one leg only)"])
    m4 = sorted(fam["C2 INTA-vectored delivery"] + fam["C3 NMI(vec2) entry"]
                + fam["C4 other-vector delivery"])
    return {"M2": m2, "M3": list(M3_SEEDS), "M4": m4}, L


def cmd_list():
    S, L = seats()
    print("LEDGER", ledger_path())
    for k in ("M2", "M3", "M4"):
        print(f"== {k}  {len(S[k])}")
        for s in S[k]:
            e = L.get(s)
            print(f"   {s:14s} {e['family'] if e else '(not in ledger)':34s} "
                  f"fb={e['first_bad_row'] if e else '-'} tier={e['tier'] if e else '-'}")


def cmd_cmp(b, a):
    B = {r["seed"]: r for r in json.load(open(b))}
    A = {r["seed"]: r for r in json.load(open(a))}
    S, L = seats()
    both = sorted(set(B) & set(A))
    gained = [s for s in both if B[s].get("bad") and A[s].get("bad") == 0]
    lost = [s for s in both if B[s].get("bad") == 0 and A[s].get("bad")]
    earlier = [s for s in both
               if B[s].get("first") is not None and A[s].get("first") is not None
               and A[s]["first"] < B[s]["first"]]
    err = [s for s in both if A[s].get("err") or B[s].get("err")]
    print(f"compared {len(both)}   BEFORE clean "
          f"{sum(1 for s in both if B[s].get('bad') == 0)}"
          f"   AFTER clean {sum(1 for s in both if A[s].get('bad') == 0)}")
    print(f"GAINED {len(gained)}   LOST {len(lost)}   EARLIER {len(earlier)}"
          f"   ERR {len(err)}")
    for nm, lst in (("GAINED", gained), ("LOST", lost), ("EARLIER", earlier),
                    ("ERR", err)):
        for s in lst:
            fam = L[s]["family"][:28] if s in L else "-"
            print(f"  {nm:8s} {s:14s} {fam:28s} "
                  f"{B[s].get('first')}->{A[s].get('first')} "
                  f"bad {B[s].get('bad')}->{A[s].get('bad')}")
    for k in ("M2", "M3", "M4"):
        cl = [s for s in S[k] if s in A and A[s].get("bad") == 0]
        print(f"{k}: {len(cl)} of {len(S[k])} row-clean AFTER "
              f"(BEFORE {sum(1 for s in S[k] if s in B and B[s].get('bad') == 0)})")
    print("§64.1 counter-population (must not move):")
    for s in GATE64_1 + C2A_KEEP:
        if s in B and s in A:
            print(f"   {s:14s} first {B[s].get('first')} -> {A[s].get('first')}"
                  f"   bad {B[s].get('bad')} -> {A[s].get('bad')}"
                  f"   {'OK' if (B[s].get('first'), B[s].get('bad')) == (A[s].get('first'), A[s].get('bad')) else 'MOVED'}")
        else:
            print(f"   {s:14s} not in both legs")


if __name__ == "__main__":
    if sys.argv[1] == "list":
        cmd_list()
    elif sys.argv[1] == "cmp":
        cmd_cmp(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
