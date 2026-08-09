#!/usr/bin/env python3
"""sm3_ackgeom -- the CHIP-SIDE geometry of every interrupt acknowledge in the
banked EVT population.  A MEASUREMENT tool; it is never a gate.

It needs no engine: everything it reports is read off the socket capture the
bank already stores (`chip_rows`), so it says what SILICON does and nothing
about what any model does.

Per acknowledge (a maximal run of back-to-back INTA bus cycles) it records the
lead-in geometry H1 is about:

  disp        the row the acknowledge is ANNOUNCED on (bs_early == INTA on a
              row that is not that cycle's own T1..T4 body)
  t1          the row INTA1's T1 opens on
  prev        the bus cycle that owned the bus immediately before, its kind,
              its T1 row and its last row
  gap         t1 - prev.t1
  idle        disp - prev.end - 1, the clocks granted to NOTHING
  ord         which acknowledge of the record this is (1-based)
  qsE / qsF   the last queue-EMPTY and queue-FIRST-BYTE strobes before t1
  waits       the wait count the preceding cycle actually took

Usage:
  sm3_ackgeom.py [--bank ...] [--jobs N] [--report out.json] [--limit N]
"""
import argparse
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                              # noqa: E402
import ucsim_fuzz as uf                                 # noqa: E402

BANK = ROOT / "tests" / "v30" / "fuzz_bank"
# ⚠ THE v1 CORPUS, AND ALL OF IT IS `status: SUPERSEDED` SINCE 2026-08-09
# (SUP-1, docs/notes/invalidation_ledger.md; the predicate is
# `sw/bank_status.py`).  MEASUREMENT TOOL, NOT A GATE: it names these
# banks explicitly and reads them deliberately -- they are its subject.
# Nothing was moved or deleted, so every path below still resolves.
BANKS = ["mc1", "mc2", "t30-raw", "t30-brkem"]

INTA, HALT, CODE, PASV = 0, 3, 4, 7


def _t(r):
    return r.get("t_state", r.get("t"))


def cycles(recs, n=None):
    """Every bus cycle as (kind, t1, end, disp) with `disp` the first row of the
    ANNOUNCEMENT run that leads into its T1.  `end` is the T4 row (or the last
    row before the next cycle's T1 if the record is cut)."""
    n = len(recs) if n is None else min(n, len(recs))
    out = []
    cur = None
    for i in range(n):
        r = recs[i]
        t = _t(r)
        if t == 1:
            # walk the announcement run backwards: rows carrying this cycle's
            # status on bs_early before its own T1
            j = i - 1
            while j >= 0 and recs[j]["bs_early"] == r["bs_early"] and \
                    _t(recs[j]) not in (1, 2, 3, 4):
                j -= 1
            if cur is not None:
                cur[2] = i - 1
                out.append(tuple(cur))
            cur = [r["bs_early"], i, None, j + 1]
        elif t == 5 and cur is not None:
            cur[2] = i
            out.append(tuple(cur))
            cur = None
    if cur is not None:
        cur[2] = n - 1
        out.append(tuple(cur))
    return out


def acks(recs, n=None):
    """Acknowledges: maximal runs of consecutive INTA cycles.  -> list of the
    cycle-index of each run's FIRST INTA cycle, plus the run length."""
    cy = cycles(recs, n)
    out = []
    k = 0
    while k < len(cy):
        if cy[k][0] == INTA:
            j = k
            while j + 1 < len(cy) and cy[j + 1][0] == INTA:
                j += 1
            out.append((k, j - k + 1))
            k = j + 1
        else:
            k += 1
    return cy, out


def geom(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    e = entry.get("evt") or {}
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    cy, ak = acks(recs, win)
    w = entry.get("waits") or {}
    wc = f"wrand{w.get('wmax')}" if w.get("wrand") else f"fix{w.get('fixed') or 0}"
    rows = []
    for ordn, (ci, nlen) in enumerate(ak, 1):
        kind, t1, end, disp = cy[ci]
        prev = cy[ci - 1] if ci > 0 else None
        # the last queue strobes before this acknowledge's T1
        qsE = qsF = qsS = -1
        for i in range(t1 - 1, max(-1, t1 - 40), -1):
            q = recs[i]["qs"]
            if q == 2 and qsE < 0:
                qsE = i
            if q == 1 and qsF < 0:
                qsF = i
            if q == 3 and qsS < 0:
                qsS = i
        rows.append({
            "ord": ordn, "n_inta": nlen, "t1": t1, "disp": disp,
            "prev_kind": None if prev is None else fc.BS_NAME[prev[0]],
            "prev_t1": None if prev is None else prev[1],
            "prev_end": None if prev is None else prev[2],
            "prev_disp": None if prev is None else prev[3],
            "prev_len": None if prev is None else prev[2] - prev[1] + 1,
            "gap": None if prev is None else t1 - prev[1],
            "idle": None if prev is None else disp - prev[2] - 1,
            "d2t1": t1 - disp,
            "qsE": qsE, "qsF": qsF, "qsS": qsS,
            "dE": (t1 - qsE) if qsE >= 0 else None,
            "dF": (t1 - qsF) if qsF >= 0 else None,
        })
    return {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
            "pin": int(e.get("pin", -1)), "hold": int(e.get("hold", 0)),
            "delay": int(e.get("delay", 0)), "wc": wc, "win": win,
            "nack": len(ak), "acks": rows,
            "nhalt": sum(1 for c in cy if c[0] == HALT)}


def seeds_of(banks):
    out = []
    for b in banks:
        d = BANK / b / "seeds"
        if d.is_dir():
            out += sorted(str(p) for p in d.glob("*.json.gz"))
    return out


def is_evt(path):
    e = json.loads(gzip.decompress(Path(path).read_bytes()))
    return bool(e.get("evt"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(BANKS))
    ap.add_argument("--seeddir", default="")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    paths = sorted(str(x) for x in Path(a.seeddir).glob("*.json.gz")) \
        if a.seeddir else seeds_of([b for b in a.bank.split(",") if b])
    with Pool(a.jobs) as pool:
        ev = pool.map(is_evt, paths, chunksize=16)
    paths = [p for p, x in zip(paths, ev) if x]
    if a.limit:
        paths = paths[:a.limit]
    with Pool(a.jobs) as pool:
        res = pool.map(geom, paths, chunksize=8)

    print(f"== sm3_ackgeom -- {len(res)} EVT seeds, "
          f"{sum(r['nack'] for r in res)} acknowledges")
    by_pin = Counter(r["pin"] for r in res)
    print("  by pin:", dict(by_pin))
    print("  acks per seed:", dict(sorted(Counter(r["nack"] for r in res).items())))

    firsts, later = [], []
    for r in res:
        for k in r["acks"]:
            (firsts if k["ord"] == 1 else later).append((r, k))

    for lbl, grp in (("FIRST acknowledge", firsts), ("LATER acknowledges", later)):
        if not grp:
            continue
        print(f"\n  -- {lbl}: {len(grp)}")
        print("     prev kind :", dict(Counter(k["prev_kind"] for _, k in grp)))
        print("     gap       :", dict(sorted(Counter(k["gap"] for _, k in grp).items(),
                                              key=lambda x: -x[1])[:8]))
        print("     idle      :", dict(sorted(Counter(k["idle"] for _, k in grp).items(),
                                              key=lambda x: -x[1])[:8]))
        print("     disp->T1  :", dict(Counter(k["d2t1"] for _, k in grp)))
        print("     prev len  :", dict(sorted(Counter(k["prev_len"] for _, k in grp).items())))
        # gap conditioned on the previous cycle's kind and length
        cnt = defaultdict(Counter)
        for _, k in grp:
            cnt[(k["prev_kind"], k["prev_len"])][k["gap"]] += 1
        for key in sorted(cnt, key=lambda x: (str(x[0]), x[1] or 0)):
            print(f"       prev={key[0]:<5} len={key[1]}  gap "
                  + " ".join(f"{g}:{n}" for g, n in sorted(cnt[key].items())))
    if a.report:
        Path(a.report).write_text(json.dumps(res))
        print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
