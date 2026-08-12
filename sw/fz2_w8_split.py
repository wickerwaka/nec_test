#!/usr/bin/env python3
"""fz2 WAVE-8 -- freeze the DERIVE/HOLDOUT split for the 8F ghost
PREDECESSOR-TYPE SELECTION law.

The split is a salted hash of the SEED ID and nothing else: it has no
dependence on any address, any register value, any solve result, or on
anything measured in this wave.  Wave-6's and wave-7's splits are burned
(their seats were inspected), so the salt is fresh: "w8".

POPULATION.  The F17 ledger's family `E1 same-status data cycle, different
address` (39 seeds) MINUS the 11 of them that `sw/fz2_immaterial.py census`
disposes as IMMATERIAL.  KM's three closures (`fz2c/404041`, `fz2e/501066`,
`fz2e/513019`) are D2/C2 and are not in E1, so nothing is subtracted for them.
Both subtractions are DERIVED here from the artifacts, not from a list.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sw"))

LEDGER = os.path.join(ROOT, "sw", "testdata", "fz2",
                      "fz2_failure_ledger_f17_2026-08-11.json")
OUT = os.path.join(ROOT, "docs", "notes", "fz2_w8_split.json")
SALT = "w8"

# The IMMATERIAL members, DERIVED through the census's OWN code path --
# `fz2_materiality.measure_all` + `fz2_immaterial.partition` -- never a list.
def immaterial_seeds():
    import fz2_materiality as M
    import fz2_immaterial as fi
    _led, res = M.measure_all(LEDGER, why="fz2 wave-8 split")
    yes, _no, _ev = fi.partition(res)
    return {m["seed"] for m in yes}


def main():
    led = json.load(open(LEDGER))
    e1 = [f for f in led["failures"] if f["family"].startswith("E1")]
    imm = immaterial_seeds()
    pop = [f for f in e1 if f["seed"] not in imm]
    der, hol = [], []
    for f in sorted(pop, key=lambda x: x["seed"]):
        h = hashlib.sha256((f["seed"] + SALT).encode()).hexdigest()
        (der if h[0] < "8" else hol).append(f["seed"])
    rec = {
        "salt": SALT,
        "rule": "sha256(seed_id + 'w8').hexdigest()[0] < '8'  ->  DERIVE",
        "ledger": os.path.relpath(LEDGER, ROOT),
        "population": ("F17 family E1 (39) minus its IMMATERIAL members; "
                       "KM's 3 closures are not in E1"),
        "e1_total": len(e1),
        "immaterial_in_e1": sorted(x["seed"] for x in e1
                                   if x["seed"] in imm),
        "n": len(pop), "derive": der, "holdout": hol,
    }
    print(json.dumps(rec, indent=1))
    if "--write" in sys.argv:
        with open(OUT, "w") as fh:
            json.dump(rec, fh, indent=1)
            fh.write("\n")
        print(f"  wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
