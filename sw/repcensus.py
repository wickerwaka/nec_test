#!/usr/bin/env python3
"""repcensus -- the REP RE-ENTRY census, chip and model through ONE reconstruction.

The `cx >= 2` REP residual (provenance 10.7, 12.4) is the campaign's last w0
physics question: the loop body is exact, `cx = 0` and `cx = 1` are exact, and
only the WINDOW-CLOSING pop drifts, in BOTH directions.  This instrument reads,
per case and from the row streams alone:

  * every bus cycle in the window as (T1 row, T4 row, status, address)
  * the STORE (and, for MOVS/CMPS, the LOAD) sequence and its per-iteration
    period
  * the window-closing F pop, and its offset from the LAST store's T4 and T1
  * `cx`, and the ENTRY PHASE (the row the opcode itself popped on)

The q1census lesson is the whole point of the file: the chip rows and the model
rows go through the SAME reconstruction.  Golden rows are `case["cycles"]`,
which sw/emit_suite.build_rows produced; sim rows come from
check_core.build_rows_sim over the record stream.  Neither is re-derived here.

Sources, all optional and all additive:
  * the v0.1 goldens (default): the five REP forms, 500 cases each
  * `--p4`: sw/testdata/t2b/p4-f3aa -- the SILICON discriminating pair at
    w0/w1/w3, same schema, read through the same extractor
  * `--fuzz`: REP segments in the fuzz bank (see `--fuzzdir`)

Usage:
  repcensus.py                       # w0 goldens, the prediction scorecard
  repcensus.py --waits 1             # the same over the w1 suite
  repcensus.py --p4                  # + the silicon pair
  repcensus.py --dump F3AA --cxmin 2 # per-case rows for one form
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core                      # noqa: E402
import timed_gate                      # noqa: E402

FORMS = ["F3A4", "F3A5", "F3AA", "F3AB", "F2AA"]

# The ROM loop each form runs, and the bus accesses one iteration makes.
# (docs/V20UC.TXT: MOVS 008C-0093, CMPS 00A0-00AF, STOS 00B8-00C1,
#  LODS 00C4-00CF, SCAS.)
LOOP_KIND = {"F3A4": "movs", "F3A5": "movs", "F3AA": "stos",
             "F3AB": "stos", "F2AA": "stos"}


# --- row-stream extraction --------------------------------------------------

def cycles_of(rows):
    """Bus cycles in a reconstructed row stream.

    A cycle occupies the rows [T1 .. T4] inclusive; the STATUS shown on a T4
    row belongs to the NEXT cycle (M2: the status register is driven one clock
    early), so a cycle's own kind is read off its T1 row.  -> list of dicts.
    """
    out = []
    i = 0
    n = len(rows)
    while i < n:
        if rows[i][8] != "T1":
            i += 1
            continue
        j = i + 1
        while j < n and rows[j][8] in ("T2", "T3", "Tw"):
            j += 1
        if j >= n or rows[j][8] != "T4":
            # the window ends inside this cycle -- record what is there
            out.append({"t1": i, "t4": None, "bs": rows[i][7],
                        "addr": rows[i][1], "waits": 0})
            break
        out.append({"t1": i, "t4": j, "bs": rows[i][7], "addr": rows[i][1],
                    "waits": (j - i) - 3})
        i = j + 1
    return out


def fpops(rows):
    return [i for i, r in enumerate(rows) if r[9] == "F"]


def measure(rows, cx):
    """The census record for ONE row stream (chip or model)."""
    cyc = cycles_of(rows)
    st = [c for c in cyc if c["bs"] == "MEMW"]
    ld = [c for c in cyc if c["bs"] == "MEMR"]
    fp = fpops(rows)
    close = len(rows) - 1          # the window's last row IS the closing pop
    m = {
        "n_rows": len(rows),
        "n_store": len(st),
        "n_load": len(ld),
        "close": close,
        "entry": fp[1] if len(fp) > 1 else None,   # the opcode's own pop
        "store_t1": [c["t1"] for c in st],
        "store_t4": [c["t4"] for c in st],
        "load_t1": [c["t1"] for c in ld],
        "load_t4": [c["t4"] for c in ld],
        "cx": cx,
    }
    if st and st[-1]["t4"] is not None:
        m["off_t4"] = close - st[-1]["t4"]
        m["off_t1"] = close - st[-1]["t1"]
    else:
        m["off_t4"] = None
        m["off_t1"] = None
    # per-iteration period: successive store T1 deltas (STOS) or successive
    # load T1 deltas (MOVS/CMPS -- one load per element on both).
    key = m["store_t1"] if len(m["store_t1"]) >= 2 else m["load_t1"]
    m["period"] = [b - a for a, b in zip(key, key[1:])]
    return m


# --- case sources -----------------------------------------------------------

def golden_cases(suite, forms, ncases):
    for name in forms:
        p = suite / f"{name}.json.gz"
        if not p.exists():
            continue
        cases = json.load(gzip.open(p))
        if ncases:
            cases = cases[:ncases]
        yield name, cases


def sim_rows_for(cases, waits):
    """-> {case index: rows or None}, through check_core, no local fork."""
    sims = timed_gate.run_form(cases, waits, False)
    out = {}
    for i, c in enumerate(cases):
        s = sims.get(i)
        if s is None:
            out[i] = None
            continue
        rows, _e, _i0, _i1 = check_core.build_rows_sim(
            s["recs"], c["initial"]["queue"],
            n_close=check_core.n_fpops(c) - 1)
        out[i] = rows
    return out


# --- the scorecard ----------------------------------------------------------

def scorecard(recs, title):
    """recs: list of (form, idx, cx, gold_measure, sim_measure)."""
    print(f"\n===== {title} =====")
    print(f"cases: {len(recs)}")

    # --- P1  the chip's closing pop rides a FIXED offset at cx >= 2 ---------
    print("\n[P1] closing pop offset from the LAST store's T4 "
          "(chip | model), by form and cx band")
    hdr = "%-6s %-6s %5s  %-22s  %-22s  %s"
    print(hdr % ("form", "cxband", "n", "chip off_t4", "model off_t4",
                 "exact"))
    bands = defaultdict(list)
    for form, idx, cx, g, s in recs:
        band = "cx=0" if cx == 0 else ("cx=1" if cx == 1 else "cx>=2")
        bands[(form, band)].append((g, s))
    for (form, band) in sorted(bands):
        lst = bands[(form, band)]
        gc = Counter(g["off_t4"] for g, s in lst)
        sc = Counter(s["off_t4"] if s else "none" for g, s in lst)
        ex = sum(1 for g, s in lst if s and g["close"] == s["close"]
                 and g["n_rows"] == s["n_rows"])
        print(hdr % (form, band, len(lst), dict(sorted(gc.items(), key=str)),
                     dict(sorted(sc.items(), key=str)),
                     f"{ex}/{len(lst)}"))

    # --- P1b the ENTRY PHASE is absorbed ------------------------------------
    print("\n[P1b] does the chip's closing pop move with the ENTRY phase?")
    print("      (cx>=2 only; groups of cases with an identical STORE grid,")
    print("       i.e. identical (n_store, store_t1 tuple), split by entry)")
    grp = defaultdict(list)
    for form, idx, cx, g, s in recs:
        if cx < 2 or not s:
            continue
        grp[(form, tuple(g["store_t1"]), tuple(g["store_t4"]))].append(
            (idx, g, s))
    absorb_g = absorb_s = tot = 0
    for k, lst in grp.items():
        if len({g["entry"] for _i, g, _s in lst}) < 2:
            continue
        tot += 1
        if len({g["close"] for _i, g, _s in lst}) == 1:
            absorb_g += 1
        if len({s["close"] for _i, _g, s in lst}) == 1:
            absorb_s += 1
    print(f"      groups with >=2 distinct entry phases on one store grid: "
          f"{tot}")
    print(f"      chip  closing pop CONSTANT across the group: {absorb_g}/{tot}")
    print(f"      model closing pop CONSTANT across the group: {absorb_s}/{tot}")

    # --- P2  the cx = 1 variable exit, per ROM path -------------------------
    print("\n[P2] cx<=1 (the negative control): chip offsets and model match")
    for band, sel in (("cx=0", lambda c: c == 0), ("cx=1", lambda c: c == 1)):
        lst = [(form, g, s) for form, idx, cx, g, s in recs if sel(cx)]
        gc = Counter(g["off_t4"] for _f, g, _s in lst)
        ex = sum(1 for _f, g, s in lst if s and g["close"] == s["close"]
                 and g["n_rows"] == s["n_rows"])
        print(f"      {band}: n={len(lst)}  chip off_t4={dict(sorted(gc.items(), key=str))}"
              f"  rows-exact={ex}/{len(lst)}")

    # --- P3  the ITERATION PERIOD -------------------------------------------
    print("\n[P3] iteration period (store->store T1 delta), chip vs model")
    per = defaultdict(lambda: [Counter(), Counter()])
    for form, idx, cx, g, s in recs:
        for d in g["period"]:
            per[form][0][d] += 1
        if s:
            for d in s["period"]:
                per[form][1][d] += 1
    for form in sorted(per):
        gc, sc = per[form]
        print(f"      {form}: chip {dict(sorted(gc.items()))}   "
              f"model {dict(sorted(sc.items()))}")

    # --- P4  where the model lands relative to the chip ---------------------
    print("\n[P4] model closing pop MINUS chip closing pop, cx>=2")
    d = Counter()
    for form, idx, cx, g, s in recs:
        if cx >= 2 and s:
            d[(form, s["close"] - g["close"])] += 1
    for form in FORMS:
        row = {k[1]: v for k, v in d.items() if k[0] == form}
        if row:
            print(f"      {form}: {dict(sorted(row.items()))}")

    # --- the RELEASE INDEX candidates ---------------------------------------
    print("\n[R] release-index probe: chip closing pop expressed against the")
    print("    LAST store's T1 and T4, and the FIRST store's T1")
    for band, lo in (("cx>=2", 2), ("cx=1", 1)):
        lst = [(g, s) for _f, _i, cx, g, s in recs
               if (cx >= 2 if lo == 2 else cx == 1) and g["store_t1"]]
        if not lst:
            continue
        c1 = Counter(g["close"] - g["store_t1"][-1] for g, _s in lst)
        c4 = Counter(g["off_t4"] for g, _s in lst)
        print(f"    {band}: close-lastT1={dict(sorted(c1.items(), key=str))}  "
              f"close-lastT4={dict(sorted(c4.items(), key=str))}")


def dump(recs, form, cxmin, limit):
    print(f"\n--- per-case dump: {form} cx>={cxmin} ---")
    n = 0
    for f, idx, cx, g, s in recs:
        if f != form or cx < cxmin:
            continue
        n += 1
        if n > limit:
            break
        print(f"  [{idx:3d}] cx={cx:<5d} entry={g['entry']} "
              f"storeT1={g['store_t1']} storeT4={g['store_t4']} "
              f"loadT1={g['load_t1']} "
              f"close chip={g['close']} model={s['close'] if s else None} "
              f"off_t4 chip={g['off_t4']} model={s['off_t4'] if s else None}")


# --- p4 silicon capture -----------------------------------------------------

def p4_records():
    p = ROOT / "sw" / "testdata" / "t2b" / "p4-f3aa" / "f3aa_pair.json"
    if not p.exists():
        return []
    d = json.load(open(p))
    out = []
    for key, c in d["cases"].items():
        w = int(key.rsplit(":", 1)[1][1:])
        cx = c["initial"]["regs"]["cx"]
        g = measure(c["cycles"], cx)
        srows = sim_rows_for([c], w)[0]
        s = measure(srows, cx) if srows else None
        out.append((key, w, cx, g, s))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(ROOT / "tests" / "v30" / "v0.1"))
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--forms", default=",".join(FORMS))
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--p4", action="store_true")
    ap.add_argument("--dump", default="")
    ap.add_argument("--cxmin", type=int, default=2)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    suite = Path(args.suite)
    forms = [f.strip() for f in args.forms.split(",") if f.strip()]

    recs = []
    for name, cases in golden_cases(suite, forms, args.cases):
        sims = sim_rows_for(cases, args.waits)
        for i, c in enumerate(cases):
            cx = c["initial"]["regs"]["cx"]
            g = measure(c["cycles"], cx)
            s = measure(sims[i], cx) if sims[i] else None
            recs.append((name, i, cx, g, s))

    scorecard(recs, f"v0.1 REP census  suite={suite.name} waits={args.waits}")

    if args.dump:
        dump(recs, args.dump, args.cxmin, args.limit)

    if args.p4:
        print("\n===== T2b P4 -- the SILICON discriminating pair =====")
        for key, w, cx, g, s in p4_records():
            print(f"  {key:14s} cx={cx} entry={g['entry']} "
                  f"storeT1={g['store_t1']} storeT4={g['store_t4']} "
                  f"close chip={g['close']} model={s['close'] if s else None} "
                  f"off_t4 chip={g['off_t4']} model={s['off_t4'] if s else None}")

    if args.report:
        json.dump([{"form": f, "idx": i, "cx": cx, "chip": g, "sim": s}
                   for f, i, cx, g, s in recs],
                  open(args.report, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
