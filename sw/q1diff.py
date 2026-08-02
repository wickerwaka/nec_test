#!/usr/bin/env python3
"""q1diff -- the Q1 discriminator: the CHIP's pop stream against the SIM's,
pop by pop, over the fuzz banks.

`sw/timed_fuzz.py` says WHERE the row streams first part; this says WHICH POP
moved, by how much, and what the two machines each saw at that moment.  Both
sides go through `sw/q1census.py`, so the reconstruction (deliverer, ready,
role, Tw) is byte-identical on the two streams and any asymmetry is the
model's.

Usage:
  q1diff.py [--bank ...] [--limit N] [--jobs N] [--waitclass fix0] [--report f]
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

import q1census as qc                                # noqa: E402
import timed_fuzz as tf                              # noqa: E402
import ucsim_fuzz as uf                              # noqa: E402
import fuzz_classify as fc                           # noqa: E402


def wait_class(entry):
    w = entry.get("waits") or {}
    return f"wrand{w.get('wmax')}" if w.get("wrand") else \
           f"fix{w.get('fixed') or 0}"


def stream(rows):
    return qc.annotate(qc.pops(rows, qc.fetches(rows)))


def one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    out = {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
           "wc": wait_class(entry)}
    if entry.get("evt"):
        out["cat"] = "EVT"
        return out
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception as e:                                   # noqa: BLE001
        out["cat"] = "REGEN_ERROR"
        return out
    if sha != entry["image_sha256"]:
        out["cat"] = "GEN_DRIFT"
        return out
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    if fc._open_bus_escaped_before(recs, win, win):
        out["cat"] = "OPEN_BUS"
        return out
    with tempfile.TemporaryDirectory() as td:
        srows, err = tf.run_sim(image, entry, len(recs), td)
    if not srows:
        out["cat"] = "SIM_ERROR"
        return out
    cp = stream(recs[:win])
    sp = stream(srows[:win])
    out["cat"] = "OK"
    out["npops"] = min(len(cp), len(sp))

    # align by index and find the FIRST pop that moved.  The role/qs sequence
    # is the instruction stream itself, so a role or qs mismatch means control
    # flow already parted and the pop indices no longer name the same byte:
    # that is reported separately and never counted as a shift.
    for i in range(min(len(cp), len(sp))):
        c, s = cp[i], sp[i]
        if c["qs"] != s["qs"]:
            out["first"] = {"i": i, "why": "qskind",
                            "chip_qs": c["qs"], "sim_qs": s["qs"],
                            "chip_row": c["row"], "sim_row": s["row"]}
            break
        if c["qs"] == "E":
            if c["row"] != s["row"]:
                out["first"] = {"i": i, "why": "flush",
                                "d": c["row"] - s["row"],
                                "chip_row": c["row"], "sim_row": s["row"]}
                break
            continue
        if c["row"] != s["row"]:
            out["first"] = {
                "i": i, "why": "shift", "d": c["row"] - s["row"],
                "role": c["role"], "prev_role": cp[i-1].get("role") if i else "-",
                "chip_row": c["row"], "sim_row": s["row"],
                "chip_ready": c.get("ready"), "sim_ready": s.get("ready"),
                "chip_tw": c.get("tw"), "sim_tw": s.get("tw"),
                "chip_bs": c.get("bs"), "sim_bs": s.get("bs"),
                "chip_t": c.get("tstate"), "sim_t": s.get("tstate"),
                "chip_prev": cp[i-1]["row"] if i else None,
                "sim_prev": sp[i-1]["row"] if i else None,
                "chip_addr": c.get("addr"), "sim_addr": s.get("addr"),
                "byte": c.get("byte"),
            }
            break
        if c.get("addr") != s.get("addr"):
            out["first"] = {"i": i, "why": "addr", "chip_row": c["row"]}
            break
    else:
        out["first"] = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(tf.BANKS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pilot", type=int, default=0)
    ap.add_argument("--waitclass", default="")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--report", default="")
    ap.add_argument("--details", type=int, default=0)
    args = ap.parse_args()

    paths = tf.seeds_of([b for b in args.bank.split(",") if b])
    if args.pilot:
        paths = tf.stratify(paths, args.pilot)
    elif args.limit:
        paths = paths[:args.limit]
    with Pool(args.jobs) as pool:
        res = pool.map(one, paths, chunksize=4)
    if args.waitclass:
        res = [r for r in res if r["wc"] == args.waitclass]

    ok = [r for r in res if r["cat"] == "OK"]
    clean = [r for r in ok if r["first"] is None]
    print(f"== q1diff  {len(res)} seeds, {len(ok)} scored, "
          f"{len(clean)} with an IDENTICAL pop stream")
    why = Counter(r["first"]["why"] for r in ok if r["first"])
    print("  first-parting reason: " + "  ".join(f"{k}={v}" for k, v in
                                                 why.most_common()))
    sh = [r["first"] for r in ok if r["first"] and r["first"]["why"] == "shift"]
    print(f"  SHIFTS n={len(sh)}   delta: " + "  ".join(
        f"{d:+d}={n}" for d, n in sorted(Counter(x["d"] for x in sh).items())))
    print("  by role: " + "  ".join(
        f"{k}={v}" for k, v in Counter(x["role"] for x in sh).most_common(12)))
    print("  by (prev_role->role): " + "  ".join(
        f"{a}>{b}={v}" for (a, b), v in
        Counter((x["prev_role"], x["role"]) for x in sh).most_common(12)))
    print("  chip landing (bs,t): " + "  ".join(
        f"{fc.BS_NAME[x[0]]}/{fc.T_NAME[x[1]]}={v}" for x, v in
        Counter((x["chip_bs"], x["chip_t"]) for x in sh).most_common(8)))
    # the decisive projection: what each side's own march would have given
    g = Counter()
    for x in sh:
        if x["chip_ready"] is None or x["sim_ready"] is None or \
                x["chip_prev"] is None:
            continue
        g[(x["chip_ready"] - x["chip_prev"], x["chip_row"] - x["chip_prev"],
           x["sim_ready"] - x["sim_prev"], x["sim_row"] - x["sim_prev"])] += 1
    print("  (chip rdy,pop | sim rdy,pop) relative to each side's PREV pop:")
    for (cr, cp_, sr, sp_), n in g.most_common(16):
        print(f"      chip rdy{cr:+d}->pop{cp_:+d}   "
              f"sim rdy{sr:+d}->pop{sp_:+d}   x{n}")
    if args.details:
        for r in ok[:args.details]:
            if r["first"]:
                print("   ", r["cid"], r["k"], r["wc"], r["first"])
    if args.report:
        Path(args.report).write_text(json.dumps(res))
        print("  report ->", args.report)


if __name__ == "__main__":
    sys.exit(main() or 0)
