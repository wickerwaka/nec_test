#!/usr/bin/env python3
"""sm3_ackcmp -- the acknowledge LEAD-IN geometry, chip vs an engine, per
acknowledge.  A MEASUREMENT tool, never a gate.

`sm3_ackgeom` reads the geometry off the socket capture alone.  This one runs
an engine over the same seed (through `timed_fuzz`'s own regeneration path,
window and directive, imported rather than forked) and pairs the two streams
BY ACKNOWLEDGE ORDINAL, so the comparison survives the row drift that starts at
the first divergence.

Reported per acknowledge, for both sides:

  gap        INTA1's T1 minus the T1 of the bus cycle immediately before it
  prev       that cycle's kind and length
  ncode      CODE cycles between the previous acknowledge and this one

Usage:
  sm3_ackcmp.py --core {sim,ucore,fsm} [--jobs N] [--limit N] [--report f]
"""
import argparse
import gzip
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                              # noqa: E402
import ucsim_fuzz as uf                                 # noqa: E402
import timed_fuzz as tf                                 # noqa: E402
import sm3_ackgeom as ag                                # noqa: E402

INTA, CODE = 0, 4


def side(recs, win):
    cy, ak = ag.acks(recs, win)
    out = []
    for ordn, (ci, nlen) in enumerate(ak, 1):
        kind, t1, end, disp = cy[ci]
        prev = cy[ci - 1] if ci > 0 else None
        ncode = 0
        j = ci - 1
        while j >= 0 and cy[j][0] != INTA:
            if cy[j][0] == CODE:
                ncode += 1
            j -= 1
        out.append({"ord": ordn, "t1": t1, "disp": disp, "n_inta": nlen,
                    "prev_kind": None if prev is None else fc.BS_NAME[prev[0]],
                    "prev_len": None if prev is None else prev[2] - prev[1] + 1,
                    "prev_t1": None if prev is None else prev[1],
                    "gap": None if prev is None else t1 - prev[1],
                    "ncode": ncode})
    return out


def one(args):
    path, core = args
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    e = entry.get("evt") or {}
    if not e:
        return None
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    if tf.excuse(entry, recs, win, True):
        return None
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception:                                     # noqa: BLE001
        return None
    if sha != entry["image_sha256"]:
        return None
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            evt = tf.evt_directive(entry, meta, recs, win)
            rows, err = tf.run_sim(image, entry, len(recs), td, evt)
        else:
            ev = tf.evt_tuple(entry, meta)
            rows, err = tf.run_tb(image, entry, len(recs), td, core, ev)
    if not rows:
        return None
    w = entry.get("waits") or {}
    wc = f"wrand{w.get('wmax')}" if w.get("wrand") else f"fix{w.get('fixed') or 0}"
    return {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
            "wc": wc, "pin": int(e.get("pin", -1)),
            "chip": side(recs, win), "eng": side(rows, win)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    paths = ag.seeds_of(ag.BANKS)
    with Pool(a.jobs) as pool:
        ev = pool.map(ag.is_evt, paths, chunksize=16)
    paths = [p for p, x in zip(paths, ev) if x]
    if a.limit:
        paths = paths[:a.limit]
    with Pool(a.jobs) as pool:
        res = [r for r in pool.map(one, [(p, a.core) for p in paths],
                                   chunksize=4) if r]

    print(f"== sm3_ackcmp --core {a.core} -- {len(res)} EVT seeds scored")
    pairs = []
    for r in res:
        eng = {k["ord"]: k for k in r["eng"]}
        for c in r["chip"]:
            pairs.append((r, c, eng.get(c["ord"])))
    print(f"   {len(pairs)} chip acknowledges, "
          f"{sum(1 for _, _, e in pairs if e)} paired")
    for lbl, sel in (("FIRST (wake)", lambda c: c["ord"] == 1),
                     ("LATER (re-entry)", lambda c: c["ord"] > 1)):
        grp = [(r, c, e) for r, c, e in pairs if sel(c) and e]
        if not grp:
            continue
        print(f"\n  -- {lbl}: {len(grp)} paired acknowledges")
        cnt = defaultdict(Counter)
        for r, c, e in grp:
            cnt[(c["prev_kind"], c["prev_len"])][(c["gap"], e["prev_kind"],
                                                  e["prev_len"], e["gap"])] += 1
        for key in sorted(cnt, key=lambda x: (str(x[0]), x[1] or 0)):
            tot = sum(cnt[key].values())
            print(f"     chip prev={key[0]} len={key[1]}  n={tot}")
            for (cg, ek, el, eg), n in sorted(cnt[key].items(),
                                              key=lambda x: -x[1])[:6]:
                print(f"        chip gap {cg:<3} | eng prev={ek} len={el} "
                      f"gap {eg:<3}  n={n}")
    if a.report:
        Path(a.report).write_text(json.dumps(res))
        print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
