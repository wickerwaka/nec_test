#!/usr/bin/env python3
"""w32_launch -- THE TRAP ENTRY'S *LAUNCH*: does the take suspend the
prefetcher?  (task #41, wrfuzz W3.2, the second half of W3.1's sec.4.7.)

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

W3.1 partitioned the survey's 75-seed trap family by ENTRY GEOMETRY and landed
the DIFF_BOUNDARY half (the recognition shadow).  The SAME_BOUNDARY half -- 32
seeds where both sides trap at the SAME instruction boundary and the engine's
vector read is 2..6 clocks LATE -- was booked with a candidate:

    an INT / NMI recognition SUSPENDS the prefetcher on its decision clock
    (`eu_bnd_post = irq_take && ...` in the RTL, `live = maskable() && ...` in
    the model), and the TRAP's take never raises that suspend, so the engine's
    prefetcher steals a slot the chip's does not and the vector read is late by
    exactly as long as the stolen slot takes.

This tool measures that, per seed, from the banked capture plus one engine run:
the entry partition (`partition`), and for the SAME_BOUNDARY seeds the PREFETCH
GEOMETRY around the contested vector read on both sides (`geom`) -- what each
side launched between the last common row and its own vector read, how long the
extra launch took, and whether the extra launch's length ACCOUNTS for the delta.

NOTHING HERE FITS A PARAMETER.  The predicted delta is read off the ENGINE'S
OWN extra bus cycle (its T1 -> next T1 length in clocks, waits included); the
chip supplies the target.  A seed either has `delta == extra_len` or it does
not, and both counts are printed.
"""
import argparse
import gzip
import json
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                                  # noqa: E402
import timed_fuzz as tf                                     # noqa: E402
import ucsim_fuzz as uf                                     # noqa: E402
import w31_shadow as w31                                    # noqa: E402


def t_of(r):
    return r.get("t_state", r.get("t"))


def engine_rows(entry, core):
    """The engine's rows for this seed, under the seed's OWN wait directive --
    `timed_fuzz`'s own two runners, not a copy of them."""
    image, meta, g, sha = uf.regen(entry)
    if sha != entry["image_sha256"]:
        raise ValueError("GEN_DRIFT")
    n = len(entry["chip_rows"])
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            rows, err = tf.run_sim(image, entry, n, td)
        else:
            rows, err = tf.run_tb(image, entry, n, td, core)
    return rows, err


def cycles(rows, n):
    """Every bus cycle: T1 row, status, address, the row of the NEXT T1
    (`end`), and the cycle's OWN active length (`alen`, T1 through T5
    inclusive -- the rig's `t` port numbers the phases and 5 is the last
    active one, so `end - row - alen` is the IDLE clocks that follow)."""
    lc = w31.launches(rows, n)
    out = []
    for i, (r, bs, a) in enumerate(lc):
        end = lc[i + 1][0] if i + 1 < len(lc) else n
        alen = end - r
        for q in range(r, end):
            if t_of(rows[q]) == 5:
                alen = q - r + 1
                break
        out.append({"row": r, "bs": bs, "addr": a, "end": end, "alen": alen})
    return out


def pair_entries(ce, ee):
    """-> (class, j, detail).  `j` is the index of the first entry that
    differs.  The comparison key is the pre-registered one: (vector, pushed IP,
    T1 row).

    An ODD-SP (byte-split) frame publishes no readable IP, so a pair in which
    either side is one is UNREADABLE **only if it actually differs** -- a pair
    that agrees on vector and row is not evidence of anything and must not take
    the whole capture out of the partition."""
    m = min(len(ce), len(ee))
    for j in range(m):
        a, b = ce[j], ee[j]
        blind = a["odd_frame"] or b["odd_frame"] or \
            a["ip"] is None or b["ip"] is None
        if blind:
            if a["vec"] == b["vec"] and a["row"] == b["row"]:
                continue
            if a["vec"] != b["vec"]:
                return "DIFF_BOUNDARY", j, {"cvec": a["vec"], "evec": b["vec"],
                                            "cip": a["ip"], "eip": b["ip"],
                                            "delta": b["row"] - a["row"]}
            return "UNREADABLE", j, {"delta": b["row"] - a["row"]}
        if a["vec"] != b["vec"] or a["ip"] != b["ip"]:
            return "DIFF_BOUNDARY", j, {"cvec": a["vec"], "evec": b["vec"],
                                        "cip": a["ip"], "eip": b["ip"],
                                        "delta": b["row"] - a["row"]}
        if a["row"] != b["row"]:
            return "SAME_BOUNDARY", j, {"vec": a["vec"], "ip": a["ip"],
                                        "crow": a["row"], "erow": b["row"],
                                        "delta": b["row"] - a["row"]}
    if len(ce) != len(ee):
        return "COUNT_DIFF", m, {"nc": len(ce), "ne": len(ee)}
    return "NO_ENTRY_DIFF", -1, {}


def geometry(crows, erows, n, ce, ee, j):
    """The prefetch geometry around the contested vector read, read off the two
    BUS-CYCLE STREAMS aligned from row 0 rather than from a window.

    Two sides that ran the same cycles in the same order are aligned index by
    index; the first index at which they part is either a cycle ONE SIDE RAN
    AND THE OTHER DID NOT (an INSERT / DELETE -- the prefetch-steal shape) or
    the same cycle at a different row (a SHIFT -- a bubble).  The distinction
    is the whole question and it must not be an artifact of where a window was
    opened."""
    cc, ec = cycles(crows, n), cycles(erows, n)
    cv, ev = ce[j]["row"], ee[j]["row"]
    ci = next(i for i, c in enumerate(cc) if c["row"] == cv)
    ei = next(i for i, c in enumerate(ec) if c["row"] == ev)
    g = {"crow": cv, "erow": ev, "delta": ev - cv, "ip": ce[j]["ip"],
         "ci": ci, "ei": ei, "n_ins": ei - ci}
    # the first index at which the aligned streams part, and HOW
    d = None
    for i in range(min(len(cc), len(ec))):
        a, b = cc[i], ec[i]
        if (a["bs"], a["addr"]) != (b["bs"], b["addr"]):
            d = (i, "CYCLE")
            break
        if a["row"] != b["row"]:
            d = (i, "SHIFT")
            break
    g["d_i"], g["d_kind"] = d if d else (None, "-")
    if d:
        i = d[0]
        g["d_crow"], g["d_erow"] = cc[i]["row"], ec[i]["row"]
        g["d_shift"] = ec[i]["row"] - cc[i]["row"]
        g["d_c"] = [cc[i]["bs"], cc[i]["addr"]]
        g["d_e"] = [ec[i]["bs"], ec[i]["addr"]]
        # the ENGINE cycle that the chip does not run at this index, and the
        # chip's own idle gap where that cycle would have gone
        g["prev_end"] = cc[i - 1]["end"] if i else 0
        g["e_len"] = ec[i]["end"] - ec[i]["row"]
    # the window, both sides, from three cycles before the contested entry
    lo = max(0, ci - 3)
    g["c_cyc"] = [(c["bs"], c["addr"], c["row"], c["end"] - c["row"])
                  for c in cc[lo:ci + 1]]
    g["e_cyc"] = [(c["bs"], c["addr"], c["row"], c["end"] - c["row"])
                  for c in ec[max(0, ei - 3 - (ei - ci)):ei + 1]]
    # IDLE clocks immediately before the contested vector read, each side
    g["c_idle"] = cv - (cc[ci - 1]["row"] + cc[ci - 1]["alen"]) if ci else 0
    g["e_idle"] = ev - (ec[ei - 1]["row"] + ec[ei - 1]["alen"]) if ei else 0
    g["c_prev"] = [cc[ci - 1]["bs"], cc[ci - 1]["addr"]] if ci else None
    g["e_prev"] = [ec[ei - 1]["bs"], ec[ei - 1]["addr"]] if ei else None
    return g


def one(args):
    path, core = args
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    out = {"seed": f"{entry['cid']}/{entry['k']}", "k": entry["k"],
           "stratum": entry.get("stratum_label"), "has_tf": entry.get("has_tf"),
           "waits": entry.get("waits"), "n": win}
    ex = tf.excuse(entry, recs, win)
    if ex:
        out["cls"] = ex
        return out
    try:
        erows, err = engine_rows(entry, core)
    except Exception as e:                                    # noqa: BLE001
        out["cls"] = "ENGINE_ERROR"
        out["detail"] = str(e)[:200]
        return out
    if not erows:
        out["cls"] = "ENGINE_ABORT"
        out["detail"] = err[:200]
        return out
    dr = fc.diff_rows(recs, erows)
    out["exact"] = not dr.rows
    out["first_bad"] = dr.rows[0].i if dr.rows else dr.n
    ce = w31.entries(recs, win)
    ee = w31.entries(erows, min(win, len(erows)))
    out["n_ce"], out["n_ee"] = len(ce), len(ee)
    cls, j, det = pair_entries(ce, ee)
    out["cls"] = cls
    out["j"] = j
    out.update(det)
    if cls == "SAME_BOUNDARY":
        out["geom"] = geometry(recs, erows, min(win, len(erows)), ce, ee, j)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeddir",
                    default=str(Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2/seeds"))
    ap.add_argument("--core", default="ucore", choices=("sim", "ucore", "fsm"))
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="", help="comma-separated k values")
    a = ap.parse_args()
    paths = sorted(str(p) for p in Path(a.seeddir).glob("*.json.gz"))
    if a.only:
        want = {int(x) for x in a.only.split(",")}
        paths = [p for p in paths
                 if any(f"_{k}_" in Path(p).name for k in want)]
    with Pool(a.jobs) as pool:
        res = pool.map(one, [(p, a.core) for p in paths], chunksize=2)
    print(f"== w32_launch --core {a.core} -- {len(res)} captures")
    print("  entry partition  " + "  ".join(
        f"{k}={v}" for k, v in sorted(Counter(r['cls'] for r in res).items())))
    sb = [r for r in res if r["cls"] == "SAME_BOUNDARY"]
    print(f"\n  SAME_BOUNDARY {len(sb)}  "
          f"(exact {sum(1 for r in sb if r.get('exact'))})")
    print("    delta       " + "  ".join(
        f"{d:+d}x{n}" for d, n in sorted(Counter(r["geom"]["delta"]
                                                 for r in sb).items())))
    print("    inserted cycles (engine index - chip index at the entry)  " +
          "  ".join(f"{d:+d}x{n}" for d, n in
                    sorted(Counter(r["geom"]["n_ins"] for r in sb).items())))
    print("    first parting of the two bus-cycle streams: " + "  ".join(
        f"{k}x{v}" for k, v in
        sorted(Counter(r["geom"]["d_kind"] for r in sb).items())))
    print("\n    seed        stratum         wait   delta ins  first-part  "
          "idle c/e   prev cycle (chip)   the engine's extra")
    for r in sorted(sb, key=lambda r: (r["geom"]["n_ins"],
                                       r["geom"]["delta"])):
        g = r["geom"]
        w = r["waits"] or {}
        wl = ("wrand%d" % w["wmax"]) if w.get("wrand") else \
             ("wvec" if r["stratum"] and "wvec" in r["stratum"]
              else "fix%d" % (w.get("fixed") or 0))
        ex = (f"{g['d_e'][0]} {g['d_e'][1]:05x}/{g.get('e_len', 0)}"
              if g["d_kind"] == "CYCLE" else
              f"shift {g.get('d_shift', 0):+d}")
        pv = f"{g['c_prev'][0]} {g['c_prev'][1]:05x}" if g["c_prev"] else "-"
        print(f"    {r['seed']:<11} {str(r['stratum']):<15} {wl:<6} "
              f"{g['delta']:+4d} {g['n_ins']:+3d}  {g['d_kind']:<6} "
              f"{g['c_idle']:3d}/{g['e_idle']:<3d}  {pv:<18}  {ex}")
    if a.out:
        json.dump(res, open(a.out, "w"))
        print(f"\n  dump -> {a.out}")


if __name__ == "__main__":
    main()
