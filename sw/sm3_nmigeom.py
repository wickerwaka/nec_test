#!/usr/bin/env python3
"""sm3_nmigeom -- the geometry of the NMI EDGE against the recognition it
produces, chip side and engine side, over the banked EVT population.

A MEASUREMENT tool (session SM3 sitting 4, hypothesis H7); it is never a gate.

Every banked NMI seed is driven by the SAME rig directive shape: a CODE-T1
address match arms a counter, `delay` clocks later the NMI pin is driven, and
it is held for `hold` clocks (`hdl/rtl/nec_bus.sv`, the `ev_st` FSM).  Every
banked NMI seed in the tree has `hold == 2`, so the part is offered a
TWO-CLOCK PULSE and the only free coordinate is WHERE the pulse lands.

Per seed it reports, in the capture's own row coordinate:

  arm      the row of the CODE T1 whose address is `meta["anchor_linear"]`
  A        the row the pin goes HIGH on = arm + delay + 2.  This is the rig's
           OWN documented offset (`docs/facts/interrupt_model.md`: "the
           scheduler asserts the pin during capture cycle
           `idx(trigger CODE T1) + 2 + delay`"), it is what `hdl/tb/
           tb_v30_core.sv`'s copy of the scheduler says beside the code, and
           it was CHECKED against the model's own `biu.assert_clk()` through
           `V30SIM_EVTTRACE` on `mc1/570` (anchor 145, delay 10, A = 157).
  V        the row the chip's RECOGNITION opens its T1 on -- the NMI vector
           read (MEMR at 0x00008) for pin 1, INTA1 for pin 0
  Ve       the same for the engine, when `--core` is given
  bus      what owned the bus on row A: the cycle's status, its T-state index,
           and the index of A inside that cycle
  gap      V - A

`--core` runs the engine leg through `timed_fuzz`'s own regeneration path,
wait vectors and event directive, so the engine sees exactly what the standing
gate gives it.

`--pin 0` runs the same measurement over the INT population, where the
recognition is INTA1 rather than the vector read.  That leg is the CONTROL that
makes the A coordinate usable: over the 929 banked INT seeds it reproduces
`interrupt_model.md`'s own chip-side law -- minimum assert-to-INTA1-T1 of 7
running, 8 from HALT -- measured three weeks later on a different population.

Usage:
  sm3_nmigeom.py [--pin 0|1|2] [--core sim|ucore|fsm] [--jobs N]
                 [--report out.json]
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

BANK = ROOT / "tests" / "v30" / "fuzz_bank"
# ⚠ THE v1 CORPUS, AND ALL OF IT IS `status: SUPERSEDED` SINCE 2026-08-09
# (SUP-1, docs/notes/invalidation_ledger.md; the predicate is
# `sw/bank_status.py`).  MEASUREMENT TOOL, NOT A GATE: it names these
# banks explicitly and reads them deliberately -- they are its subject.
# Nothing was moved or deleted, so every path below still resolves.
BANKS = ["mc1", "mc2", "t30-raw", "t30-brkem"]

CODE, MEMR, PASV, INTA = 4, 5, 7, 0
NMI_VEC = 0x00008


def _t(r):
    return r.get("t_state", r.get("t"))


def first_t1(rows, kind, addr, n, start=0):
    """Row index of the first T1 of a `kind` cycle at `addr`, or -1.
    `addr = None` matches any address (the INTA control, whose T1 drives no
    address at all -- interrupt_model.md)."""
    for i in range(start, min(n, len(rows))):
        r = rows[i]
        if _t(r) == 1 and r["bs_early"] == kind and \
                (addr is None or (r["ad_addr"] & 0xFFFFF) == addr):
            return i
    return -1


def bus_at(rows, i, n):
    """(status, index-inside-cycle, T-state) on row `i`: walk back to that
    cycle's T1.  A PASV row that belongs to no cycle reports index -1."""
    if i < 0 or i >= min(n, len(rows)):
        return ("OOB", -1, -1)
    t = _t(rows[i])
    j = i
    while j >= 0 and _t(rows[j]) != 1:
        j -= 1
    if j < 0:
        return (fc.BS_NAME[rows[i]["bs_early"]], -1, t)
    # is row i still inside cycle j?  a cycle ends at its T4 (t == 5 marks Ti)
    return (fc.BS_NAME[rows[j]["bs_early"]], i - j, t)


def one(args):
    path, core = args
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    e = entry.get("evt") or {}
    out = {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
           "pin": int(e.get("pin", -1)), "hold": int(e.get("hold", 0)),
           "delay": int(e.get("delay", 0))}
    w = entry.get("waits") or {}
    out["wc"] = f"wrand{w.get('wmax')}" if w.get("wrand") \
        else f"fix{w.get('fixed') or 0}"
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception as ex:                                   # noqa: BLE001
        out["err"] = str(ex)[:120]
        return out
    if sha != entry["image_sha256"]:
        out["err"] = "GEN_DRIFT"
        return out
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    out["win"] = win
    anchor = int(meta["anchor_linear"]) & 0xFFFFF
    arm = first_t1(recs, CODE, anchor, win)
    out["arm"] = arm
    A = arm + int(e.get("delay", 0)) + 2 if arm >= 0 else -1
    out["A"] = A
    out["Aend"] = A + int(e.get("hold", 0)) - 1 if A >= 0 else -1
    kind, vaddr = ((MEMR, NMI_VEC) if out["pin"] == 1 else (INTA, None))
    V = first_t1(recs, kind, vaddr, win)
    out["V"] = V
    out["gap"] = (V - A) if (V >= 0 and A >= 0) else None
    out["bus_A"] = bus_at(recs, A, win)
    out["bus_A1"] = bus_at(recs, A + 1, win)
    # how many NMI entries the chip made inside the window
    nv = 0
    i = 0
    while True:
        j = first_t1(recs, kind, vaddr, win, i)
        if j < 0:
            break
        nv += 1
        i = j + 1
    out["nvec"] = nv

    if core:
        with tempfile.TemporaryDirectory() as td:
            if core == "sim":
                ev = tf.evt_directive(entry, meta, recs, win, "banked")
                rows, err = tf.run_sim(image, entry, len(recs), td, ev)
                out["fires"] = len(ev["at"]) if ev else 0
            else:
                ev = tf.evt_tuple(entry, meta, "banked")
                rows, err = tf.run_tb(image, entry, len(recs), td, core, ev)
        out["nrows"] = len(rows)
        Ve = first_t1(rows, kind, vaddr, win) if rows else -1
        out["Ve"] = Ve
        out["gape"] = (Ve - A) if (Ve >= 0 and A >= 0) else None
        nv = 0
        i = 0
        while rows:
            j = first_t1(rows, kind, vaddr, win, i)
            if j < 0:
                break
            nv += 1
            i = j + 1
        out["nvec_e"] = nv
        dr = fc.diff_rows(recs, rows) if rows else None
        out["exact"] = bool(dr is not None and not dr.rows)
        out["first_bad"] = dr.rows[0].i if (dr and dr.rows) else None
        out["detail"] = ((dr.rows[0].qs_txt or "") + " " +
                         " ".join(dr.rows[0].other)).strip() \
            if (dr and dr.rows) else ""
    return out


def seeds_of(banks):
    out = []
    for b in banks:
        d = BANK / b / "seeds"
        if d.is_dir():
            out += sorted(str(p) for p in d.glob("*.json.gz"))
    return out


def axis(path):
    e = json.loads(gzip.decompress(Path(path).read_bytes()))
    ev = e.get("evt") or {}
    return int(ev.get("pin", -1)) if ev else -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(BANKS))
    ap.add_argument("--pin", type=int, default=1)
    ap.add_argument("--core", default="", choices=("", "sim", "ucore", "fsm"))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    paths = seeds_of([b for b in a.bank.split(",") if b])
    with Pool(a.jobs) as pool:
        ax = pool.map(axis, paths, chunksize=16)
    paths = [p for p, x in zip(paths, ax) if x == a.pin]
    if a.limit:
        paths = paths[:a.limit]
    with Pool(a.jobs) as pool:
        res = pool.map(one, [(p, a.core) for p in paths], chunksize=4)

    print(f"== sm3_nmigeom -- {len(res)} seeds, pin={a.pin}, "
          f"core={a.core or 'none'}")
    bad = [r for r in res if r.get("err")]
    if bad:
        print(f"  ERRORS {len(bad)}")
    ok = [r for r in res if not r.get("err")]
    print("  hold:", dict(Counter(r["hold"] for r in ok)))
    print("  arm found:", sum(1 for r in ok if r["arm"] >= 0), "/", len(ok))
    print("  chip vector reads per seed:",
          dict(sorted(Counter(r["nvec"] for r in ok).items())))
    print("  chip gap V-A:", dict(sorted(Counter(r["gap"] for r in ok).items(), key=lambda x: (x[0] is None, x[0]))))
    print("  bus owner on A:", dict(Counter(r["bus_A"][0] for r in ok)))
    print("  (status, idx) on A:",
          dict(sorted(Counter((r["bus_A"][0], r["bus_A"][1])
                              for r in ok).items(), key=lambda x: -x[1])[:12]))
    if a.core:
        ex = [r for r in ok if r.get("exact")]
        print(f"  engine exact {len(ex)}/{len(ok)}")
        ne = [r for r in ok if not r.get("exact")]
        print("  engine vector reads per seed:",
              dict(sorted(Counter(r.get("nvec_e") for r in ok).items())))
        print("  engine gap Ve-A:",
              dict(sorted(Counter(r.get("gape") for r in ok).items(),
                          key=lambda x: (x[0] is None, x[0]))))
        print("  gap delta (Ve-V):",
              dict(sorted(Counter((r["Ve"] - r["V"])
                                  if (r.get("Ve", -1) >= 0 and r["V"] >= 0)
                                  else None for r in ok).items(),
                          key=lambda x: (x[0] is None, x[0]))))
        print("  non-exact first signature:",
              dict(Counter(" ".join((r.get("detail") or "").split()[:2])
                           for r in ne).most_common(10)))
        # the split that matters: chip gap x engine gap
        cnt = defaultdict(Counter)
        for r in ok:
            cnt[r["gap"]][r.get("gape")] += 1
        for k in sorted(cnt, key=lambda x: (x is None, x)):
            print(f"    chip gap {k}: engine " +
                  " ".join(f"{g}:{n}" for g, n in
                           sorted(cnt[k].items(),
                                  key=lambda x: (x[0] is None, x[0]))))
    if a.report:
        Path(a.report).write_text(json.dumps(res))
        print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
