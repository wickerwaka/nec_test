#!/usr/bin/env python3
"""dumpdiv - dump chip-vs-TB rows around the first divergence for a seed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, run_tb, BS_NAME, T_NAME, QS_NAME, diff
from gen_seq import generate
from measure import chip_ref
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("seed", type=int)
ap.add_argument("--waits", type=int, default=1)
ap.add_argument("--host", default="root@mister-nec")
ap.add_argument("--ctx", type=int, default=14)
a = ap.parse_args()

real = chip_ref(a.seed, a.waits, a.host)
real = [dict(r, t_state=r["t"]) for r in real]
g = generate(a.seed, exts=())
image, meta = compose(g)
sim = run_tb(image, 4200, waits=a.waits)
bad, first, n, flick = diff(real, sim, maxprint=0)
print(f"seed{a.seed} w{a.waits}: bad={bad} first@{first} n={n}")
lo = max(0, first - a.ctx)
hi = min(len(real), len(sim), first + a.ctx)
print(f"{'idx':>4}  {'CHIP: t bs addr data qs':<30}  {'TB: t bs addr data qs'}")
for i in range(lo, hi):
    r, s = real[i], sim[i]
    def fmt(x):
        return (f"{T_NAME.get(x['t_state'],x.get('t')):<2} {BS_NAME[x['bs_early']]:<4} "
                f"{x['ad_addr']:05x} {x['ad_data']:04x} {QS_NAME[x['qs']]}")
    mark = " <<<" if i == first else ""
    diffm = "  *" if (r['bs_early'] != s['bs_early'] or r['t_state'] != s['t']
                      or r['ad_addr'] != s['ad_addr']) else ""
    print(f"{i:>4}  {fmt(r):<30}  {fmt(dict(s,t_state=s['t'])):<30}{diffm}{mark}")
