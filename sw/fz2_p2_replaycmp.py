#!/usr/bin/env python3
"""fz2_p2_replaycmp -- BEFORE/AFTER over two `fz2_replay --out` runs.

`fz2_replay` is a FIDELITY instrument: it asks "does the offline replay agree
with the fabric verdict".  Used as a BEFORE/AFTER pair on the SAME banked
socket rows it is also a BENEFIT instrument, and a seed that goes
`replay FAIL -> replay PASS` is a seed the landing closed against silicon.

    python3 sw/fz2_p2_replaycmp.py BEFORE.json AFTER.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import fz2_ledger as fzl                                  # noqa: E402


def rows(p):
    d = json.loads(Path(p).read_text())
    return d, {r["seed"]: r for r in d["rows"]}


def first(r):
    return (r.get("sys") or {}).get("first")


def bad(r):
    """the replay's own bad-row count, or None if the row carries an error"""
    t = r.get("sys") or {}
    return t.get("bad")


if __name__ == "__main__":
    (dB, B), (dA, A) = rows(sys.argv[1]), rows(sys.argv[2])
    led = {f["seed"]: f for f in fzl.load(quiet=True)["failures"]}
    print(f"BEFORE  {dB.get('ts')}  tb_sys {str(dB.get('tb_sys_receipt'))[:16]}…"
          f"  git {(dB.get('git') or {}).get('describe')}")
    print(f"AFTER   {dA.get('ts')}  tb_sys {str(dA.get('tb_sys_receipt'))[:16]}…"
          f"  git {(dA.get('git') or {}).get('describe')}")
    both = sorted(set(B) & set(A))
    gained = [s for s in both if bad(B[s]) and bad(A[s]) == 0]
    lost = [s for s in both if bad(B[s]) == 0 and bad(A[s])]
    worse = [s for s in both
             if bad(B[s]) and bad(A[s]) and bad(A[s]) > bad(B[s])]
    print(f"compared {len(both)}   BEFORE clean {sum(1 for s in both if bad(B[s]) == 0)}"
          f"   AFTER clean {sum(1 for s in both if bad(A[s]) == 0)}")
    print(f"GAINED {len(gained)}   LOST {len(lost)}   MORE-BAD-ROWS {len(worse)}")
    for nm, lst in (("GAINED", gained), ("LOST", lost), ("WORSE", worse)):
        for s in lst:
            f = led.get(s, {})
            print(f"  {nm:7s} {s:14s} {f.get('family', '-')[:32]:32s} "
                  f"bad {bad(B[s])} -> {bad(A[s])}")
