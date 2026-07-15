#!/usr/bin/env python3
"""hwdrift - in-silicon A/B drift vs sim, per seed.

Per seed/waits, reports three bad-row counts:
  fab-vs-chip : fabric core (use_core=1) vs socketed chip (use_core=0) - SILICON
  chip-vs-TB  : cached chip vs Verilator TB - SIM (measure.py ground truth)
  fab-vs-TB   : fabric core vs TB - the synth FLOAT FLOOR (should be ~0)
The fronts are REAL in fabric iff fab-vs-chip == chip-vs-TB per seed and the
float floor is ~0.
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, run_tb, run_chip, diff
from gen_seq import generate
from measure import chip_ref

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="root@mister-nec")
ap.add_argument("--seeds", type=int, default=15)
ap.add_argument("--start", type=int, default=90000)
ap.add_argument("--waits", default="1,3")
a = ap.parse_args()

for w in [int(x) for x in a.waits.split(",")]:
    print(f"=== waits={w} ===", flush=True)
    agree = 0; floor_clean = 0; n = 0
    for s in range(a.start, a.start + a.seeds):
        g = generate(s, exts=())
        image, meta = compose(g)
        chip = chip_ref(s, w, a.host)                    # cached, use_core=0
        chip = [dict(r, t_state=r["t"]) for r in chip]
        fab = run_chip(image, a.host, use_core=True, waits=w)   # fabric
        tb = run_tb(image, 4200, waits=w)
        fc, _, nfc, _ = diff(chip, fab, maxprint=0)      # silicon A/B
        ct, _, nct, _ = diff(chip, tb, maxprint=0)       # sim (measure)
        ft, _, nft, _ = diff(fab, tb, maxprint=0)        # float floor
        n += 1
        if fc == ct:
            agree += 1
        if ft == 0:
            floor_clean += 1
        flag = "" if (fc == ct and ft == 0) else "  <-- CHECK"
        print(f"  seed{s} w{w}: fab-vs-chip={fc} chip-vs-TB={ct} "
              f"fab-vs-TB(floor)={ft}{flag}", flush=True)
    print(f"  --- w{w}: silicon==sim {agree}/{n}, float-floor-clean "
          f"{floor_clean}/{n}", flush=True)
