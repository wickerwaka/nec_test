#!/usr/bin/env python3
"""ad-hoc: the exact diverging rows of one seed on the live ucore TB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fuzz_classify as fc                                # noqa: E402
import fz2_p2_probe as P                                  # noqa: E402

S = P.load(sys.argv[1])
rows = P.tb_rows(S)
dr = fc.diff_rows(S["cap"]["real"], rows, window=int(S["line"]["win"]))
bad = [r for r in dr.rows if not r.flicker]
print(f"{sys.argv[1]}  win {dr.n}  bad {len(bad)}")
for r in bad:
    print(f"  row {r.i}: qs={r.qs_txt} other={r.other}")
