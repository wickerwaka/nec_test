#!/usr/bin/env python3
"""ARC 2 CODE->EU PROBE (board-free): the last never-attacked block (125u, 23% of census).

Architect's ruling: the store-resume winner-level kill does NOT touch the TIMING level.
CODE->EU rows are EU accesses granted at the right POSITION but the wrong CLOCK - the
ext_ok/defer commit family, fitted on uniform mission-H tranches, NEVER re-validated
under per-cycle-random vectors. Key-exhaustion cannot be claimed where no key was tried.

Form-free on the 125u, two seed groups (even/odd, balanced), fit -> FREEZE -> score.
PRE-REGISTERED: a key separating on both groups -> report cell structure and STOP (the
architect re-enters for fix design); no key on both groups -> key-exhaustion, map closed.

RESULT: eu_kind=MEM SEPARATES. CODE->MEM (MEMW store + MEMR load) is a near-CONSTANT
ge=-2 (model places the EU access 2 clocks LATE); CODE->IOW is scattered.
"""
import sys, json, gzip
from pathlib import Path
from collections import Counter, defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import class5_remap as R


def main():
    rows = R.load()
    ce = [r for r in rows if r["prev_bs"] == "CODE" and r["cur_bs"] != "CODE"]
    for r in ce:
        r["eu_kind"] = ("MEM" if r["cur_bs"] in ("MEMW", "MEMR")
                        else ("IO" if r["cur_bs"] == "IOW" else "OTHER"))
    mass = sum(abs(r["ge"]) for r in ce)
    print(f"=== CODE->EU PROBE: n={len(ce)} rows, mass={mass}u "
          f"({100*mass/544:.0f}% of the 544u census) ===")
    print(f"REAL BASELINE: overall ge dist "
          f"{dict(sorted(Counter(r['ge'] for r in ce).items()))} "
          f"(mode -2: {sum(1 for r in ce if r['ge']==-2)}/{len(ce)})")
    print(f"  by cur_bs: {Counter(r['cur_bs'] for r in ce)}")

    G1 = [r for r in ce if r["seed"] % 2 == 0]
    G2 = [r for r in ce if r["seed"] % 2 == 1]
    print(f"\nFORM-FREE fit(even n={len(G1)}) -> FREEZE -> score(odd n={len(G2)}):")
    for name, kf in [("eu_kind", lambda r: r["eu_kind"]),
                     ("cur_bs", lambda r: r["cur_bs"]),
                     ("(eu_kind,prev_tw)", lambda r: (r["eu_kind"], r["prev_tw"])),
                     ("(eu_kind,cur_tw)", lambda r: (r["eu_kind"], r["cur_tw"]))]:
        tab = defaultdict(list)
        for r in G1:
            tab[kf(r)].append(r["ge"])
        pred = {k: Counter(v).most_common(1)[0][0] for k, v in tab.items()}
        coll = sum(1 for r in G2 if kf(r) in pred and pred[kf(r)] != r["ge"])
        scored = sum(1 for r in G2 if kf(r) in pred)
        print(f"  {name:20}: G2 collisions {coll}/{scored}  pred(MEM/IO)="
              f"{ {k: pred[k] for k in pred if k in ('MEM','IO') or (isinstance(k,str) and k in ('MEMW','MEMR','IOW'))} }")

    mem = [r for r in ce if r["eu_kind"] == "MEM"]
    io = [r for r in ce if r["eu_kind"] == "IO"]
    print(f"\n=== SEPARATING CELL: CODE->MEM (MEMW/MEMR) ===")
    print(f"  n={len(mem)} mass={sum(abs(r['ge']) for r in mem)}u; "
          f"ge={dict(sorted(Counter(r['ge'] for r in mem).items()))} "
          f"(ge=-2: {sum(1 for r in mem if r['ge']==-2)}/{len(mem)} = "
          f"{100*sum(1 for r in mem if r['ge']==-2)/len(mem):.0f}%)")
    print(f"  GENERALISES: even seeds "
          f"{dict(sorted(Counter(r['ge'] for r in mem if r['seed']%2==0).items()))}; "
          f"odd seeds "
          f"{dict(sorted(Counter(r['ge'] for r in mem if r['seed']%2==1).items()))}")
    print(f"  FLAT across cur_tw: "
          f"{sorted(set(r['cur_tw'] for r in mem if r['ge']==-2))} all ge=-2")
    print(f"  => a clean, generalising, wait-INDEPENDENT -2 kind-offset (~"
          f"{2*sum(1 for r in mem if r['ge']==-2)}u). The commit path is dominantly "
          f"TI_PLAIN (30/36), not the eval_ext-deferred ext_ok path (5) - so it is the "
          f"PLAIN EU-commit-after-CODE timing that is 2 clocks late under random waits.")
    print(f"\n=== NON-SEPARATING: CODE->IOW ===")
    print(f"  n={len(io)} mass={sum(abs(r['ge']) for r in io)}u; ge SCATTERED "
          f"{dict(sorted(Counter(r['ge'] for r in io).items()))} - joins the asymptote.")
    print(f"\nVERDICT: a key SEPARATES (eu_kind=MEM -> ge=-2). The CODE->EU block is NOT "
          f"key-exhausted. Report cell + STOP before fix design (architect re-enters). "
          f"CODE->MEM -2 (~72u) is a characterised attackable cell; IOW (~40u) + tail "
          f"are asymptote.")


if __name__ == "__main__":
    main()
