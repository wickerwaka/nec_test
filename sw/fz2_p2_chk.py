#!/usr/bin/env python3
"""ad-hoc: seat-by-seat BEFORE-leg status against the ledger."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fz2_p2_seats as S                                  # noqa: E402

B = {r["seed"]: r for r in json.load(open(sys.argv[1]))}
seats, L = S.seats()
for k in ("M2", "M3", "M4"):
    print(f"== {k}")
    for s in seats[k]:
        r = B.get(s)
        want = L[s]["first_bad_row"] if s in L else None
        if r is None:
            print(f"   {s:14s} NO CAPTURE IN THE 677")
            continue
        print(f"   {s:14s} ledger_fb={want:5} tb_fb={str(r.get('first')):5} "
              f"bad={r.get('bad')} sig={str(r.get('sig'))[:44]} "
              f"{'SCOREABLE' if r.get('first') == want else 'OUT'}")
