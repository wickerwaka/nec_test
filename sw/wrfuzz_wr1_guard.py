#!/usr/bin/env python3
"""wrfuzz_wr1_guard -- the REGISTERED REGRESSION GUARD over the `wr1` OFFLINE
columns (wrfuzz W6, 2026-08-06).

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

⚠ **WHAT THIS IS.**  An IMPLEMENTATION guard.  It re-runs `w32_launch` over the
380 retained `wr1` captures and asserts that the three landings of wrfuzz W3.1 /
W3.4 / W3.5 are still in the tree and still worth what they were measured to be
worth, seed by seed, against a baseline banked at registration.

⚠ **WHAT THIS IS NOT, AND THE DISTINCTION IS THE POINT.**

* It is **not a silicon-match rate**.  The 184 is the retained-and-scored subset
  of the 380 captures and that subset is **DIVERGENT BY CONSTRUCTION**.  84 and
  91 are ATTRIBUTION figures.  They may never be quoted as a match rate.
* It is **not a ranking of the two engines**.  No delta between the two legs is
  computed here or anywhere.
* It is **not a new sample**, and it does not re-claim W4's fabric measurement.
  **`T` = 90.0170 % is a FIRST REGISTRATION on a population that is now spent**
  (`standing_gates.md`, wrfuzz section): the victory tranche was frozen, drawn
  and scored once, a second run of the same seeds is not a second sample, and
  **nothing is ratcheted to 90.0170 %**.  This guard runs offline, touches no
  board, and says nothing whatever about that number.

**The three registered clauses** (all four must hold for a leg to be GREEN):

  1. `exact >= floor` -- model **84 / 184**, `ucore` **91 / 184**;
  2. **zero previously-exact seeds lost** -- no seed that was `exact` in the
     baseline may be non-exact now;
  3. **zero first divergences moved earlier** -- no scored seed's `first_bad`
     may decrease;
  4. the scored denominator is still **184** (an exclusion that moved would make
     clauses 1-3 unreadable).

Baseline: `sw/testdata/wrfuzz/w6_wr1_guard_baseline.json`, banked at
registration from the very runs this file's clauses quote.  The 380 capture
records are a DERIVATION of the committed `sw/testdata/campaigns/wr1/` and are
rebuilt on demand by `sw/wrfuzz_w2.py seeds` -- they are not committed, for the
same reason the loose captures are not (ledger §3.10).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
BASELINE = SW / "testdata/wrfuzz/w6_wr1_guard_baseline.json"
DEFAULT_SEEDDIR = Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2/seeds"


def run_leg(core, seeddir, jobs, dump):
    cmd = [sys.executable, str(SW / "w32_launch.py"), "--core", core,
           "--seeddir", str(seeddir), "--jobs", str(jobs), "--out", str(dump)]
    print(f"  $ {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout[-4000:])
        print(p.stderr[-4000:], file=sys.stderr)
        raise SystemExit(f"w32_launch --core {core} exited {p.returncode}")
    return {r["seed"]: r for r in json.load(open(dump)) if "exact" in r}


def score(core, base, now):
    b, floors = base["legs"][core], base["floors"]
    bs = b["seeds"]
    ex = sum(1 for r in now.values() if r["exact"])
    lost = sorted(s for s, v in bs.items()
                  if v["exact"] and not (now.get(s) or {}).get("exact"))
    earlier = sorted(s for s, v in bs.items()
                     if s in now and now[s]["first_bad"] < v["first_bad"])
    missing = sorted(s for s in bs if s not in now)
    clauses = [
        (f"exact {ex} >= floor {floors[core]}", ex >= floors[core]),
        (f"zero previously-exact lost (got {len(lost)})", not lost),
        (f"zero first divergences moved earlier (got {len(earlier)})",
         not earlier),
        (f"scored denominator {len(now)} == {base['denominator']}",
         len(now) == base["denominator"] and not missing),
    ]
    print(f"\n  == {core}: {ex} / {len(now)} exact "
          f"(baseline {b['exact']} / {b['scored']})")
    for text, ok in clauses:
        print(f"     [{'PASS' if ok else 'FAIL'}] {text}")
    for label, items in (("LOST", lost), ("MOVED EARLIER", earlier),
                         ("MISSING", missing)):
        if items:
            print(f"     {label}: {' '.join(items[:20])}"
                  + (" ..." if len(items) > 20 else ""))
    return all(ok for _, ok in clauses)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeddir", default=str(DEFAULT_SEEDDIR))
    ap.add_argument("--core", default="both",
                    choices=("both", "sim", "ucore"))
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--dumpdir", default="",
                    help="keep the per-leg w32_launch dumps here")
    a = ap.parse_args()
    base = json.loads(BASELINE.read_text())
    seeddir = Path(a.seeddir)
    if not seeddir.is_dir():
        raise SystemExit(f"seeddir {seeddir} absent -- rebuild it with "
                         f"`python3 sw/wrfuzz_w2.py seeds`")
    cores = ("sim", "ucore") if a.core == "both" else (a.core,)
    print("== wrfuzz wr1 OFFLINE GUARD (IMPLEMENTATION guard -- attribution "
          "figures on a divergent-by-construction subset;")
    print("   NOT a silicon-match rate, NOT a new sample, NOT a ranking, and "
          "NOT a re-claim of W4's 90.0170 %)")
    print(f"   baseline {BASELINE.relative_to(ROOT)}  "
          f"floors sim {base['floors']['sim']} / ucore "
          f"{base['floors']['ucore']} of {base['denominator']}\n")
    ok = True
    with tempfile.TemporaryDirectory() as td:
        dd = Path(a.dumpdir) if a.dumpdir else Path(td)
        dd.mkdir(parents=True, exist_ok=True)
        for core in cores:
            now = run_leg(core, seeddir, a.jobs, dd / f"guard_{core}.json")
            ok &= score(core, base, now)
    print(f"\n== {'GREEN' if ok else 'RED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
