#!/usr/bin/env python3
"""s11_census -- the ACKNOWLEDGE-GAP census (ucsim_t_provenance 22).

OFFLINE.  No board, NO MODEL IN THE LOOP: every number below is read off the
CHIP's own rows (the banked goldens, or the S10 raw 64-bit capture words).
NOT a gate -- a measurement tool.

  gap    for every acknowledge PAIR: INTA1's T1 / its Tw count / its completion
         eval (11.1's instant), what occupies the clocks between INTA1's T4 and
         INTA2's T1, and INTA2's T1 against M18's `eval + 5`.
  flush  the DISCRIMINATOR: where the queue-clear (QS=E) sits relative to
         INTA1's T1, against whether a prefetch took the gap.
  lock   BUSLOCK_N across the pair, straight off the S10 raw words -- the
         "LOCK holds the prefetcher off between acknowledges" rival.
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

C_PINS, C_BUS, C_SEG, C_MEMCMD, C_IOCMD, C_UBE, C_DATA, C_STAT, C_T, C_QOP, C_QB = range(11)


def load(suite, form):
    p = ROOT / suite / f"{form}.json.gz"
    return json.load(gzip.open(p)) if p.exists() else None


def forms_of(suite):
    d = ROOT / suite
    return sorted(p.name[:-8] for p in d.glob("*.json.gz")) if d.is_dir() else []


def cycles_of(rows):
    """-> list of {t1, stat, tw, last} bus cycles, in order (T1-anchored)."""
    out = []
    cur = None
    for i, r in enumerate(rows):
        if r[C_T] == "T1":
            cur = {"t1": i, "stat": r[C_STAT], "tw": 0, "last": i}
            out.append(cur)
        elif cur is not None and r[C_T] in ("T2", "T3", "Tw", "T4"):
            if r[C_T] == "Tw":
                cur["tw"] += 1
            cur["last"] = i
    return out


def ack_pairs(rows):
    """Every INTA1/INTA2 pair with what sits between them."""
    cyc = cycles_of(rows)
    pairs = []
    for k in range(len(cyc) - 1):
        if cyc[k]["stat"] != "INTA":
            continue
        # the next INTA after it
        nxt = None
        between = []
        for j in range(k + 1, len(cyc)):
            if cyc[j]["stat"] == "INTA":
                nxt = cyc[j]
                break
            between.append(cyc[j])
        if nxt is None:
            continue
        if any(c["stat"] == "INTA" for c in between):
            continue
        a, b = cyc[k], nxt
        n = a["tw"]
        # 11.1 / M2r: the completion eval sits at T1+2 at w0 and T1+3+N waited
        ev = a["t1"] + 2 if n == 0 else a["t1"] + 3 + n
        pairs.append({
            "t1a": a["t1"], "twa": n, "eval": ev, "t1b": b["t1"],
            "gap": b["t1"] - a["t1"], "m18": b["t1"] - (ev + 5),
            "between": [(c["stat"], c["t1"], c["tw"]) for c in between],
            "free": b["t1"] - (a["t1"] + 4 + n),
        })
        # only the FIRST pair of a run matters; skip the partner
    return pairs


def cmd_gap(args):
    tot = Counter()
    bystat = Counter()
    m18 = Counter()
    freeh = defaultdict(Counter)
    percase = []
    for suite, w in args.suites:
        for form in (args.forms or forms_of(suite)):
            ts = load(suite, form)
            if not ts:
                continue
            for idx, t in enumerate(ts):
                ps = ack_pairs(t["cycles"])
                for p in ps:
                    tot[(w, bool(p["between"]))] += 1
                    m18[(w, p["m18"])] += 1
                    freeh[w][p["free"]] += 1
                    for st, _, _ in p["between"]:
                        bystat[(w, st)] += 1
                    percase.append((suite, form, idx, w, p))
    print("=== acknowledge-gap census ===")
    print("  waits | clean pairs | pairs with something between")
    for w in sorted({k[0] for k in tot}):
        print(f"  {w:5d} | {tot[(w, False)]:11d} | {tot[(w, True)]}")
    print("\n  what sits between (status of the intervening cycles):")
    for (w, st), n in sorted(bystat.items()):
        print(f"    w{w} {st}: {n}")
    print("\n  M18 residual (INTA2 T1 - (eval + 5)); 0 = the law holds:")
    for (w, d), n in sorted(m18.items()):
        print(f"    w{w} delta={d:+d}: {n}")
    print("\n  FREE clocks between INTA1's last clock and INTA2's T1:")
    for w in sorted(freeh):
        print(f"    w{w}: {dict(sorted(freeh[w].items()))}")
    if args.dump:
        json.dump([{"suite": s, "form": f, "idx": i, "w": w, **p}
                   for s, f, i, w, p in percase], open(args.dump, "w"))
    return 0


def cmd_flush(args):
    """The DISCRIMINATOR: where the queue-clear (QS=E) sits relative to the
    first acknowledge's T1, against whether a prefetch takes the gap.  Chip
    rows only; the E is the chip's own QS port."""
    print("=== the flush's position vs the gap prefetch ===")
    for suite, w in args.suites:
        tab = defaultdict(Counter)
        for form in (args.forms or forms_of(suite)):
            ts = load(suite, form)
            if not ts:
                continue
            for t in ts:
                rows = t["cycles"]
                ps = ack_pairs(rows)
                if not ps:
                    continue
                p = ps[0]
                e = [i - p["t1a"] for i, r in enumerate(rows)
                     if r[C_QOP] == "E" and i < p["t1a"]]
                tab[bool(p["between"])][e[-1] if e else None] += 1
        print(f"  w{w}:")
        for gap in (False, True):
            lab = "prefetch in the gap" if gap else "clean pair        "
            print(f"    {lab}  last E before INTA1 T1, at offset -> "
                  f"{dict(sorted(tab[gap].items(), key=lambda kv: (kv[0] is None, kv[0])))}")
    return 0


# raw 64-bit capture word (hdl/rtl/nec_bus.sv, "Capture record")
_TS = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
_BS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
       4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}


def cmd_lock(args):
    """BUSLOCK_N across the acknowledge pair, straight off the S10 raw words
    (bit 50 in large mode).  The rival reading for the gap -- "the chip holds
    the prefetcher off between acknowledges via a LOCK-adjacent hold" -- lives
    or dies here."""
    print("=== BUSLOCK_N across the acknowledge pair (S10 raw words) ===")
    for f in sorted(Path(args.dir).glob(args.glob)):
        ws = [int(l, 16) for l in gzip.open(f, "rt") if l.strip()]
        rows = [(_TS[(w >> 56) & 7], _BS[(w >> 40) & 7], (w >> 50) & 1)
                for w in ws]
        t1 = [i for i, r in enumerate(rows) if r[0] == "T1" and r[1] == "INTA"]
        if len(t1) < 2:
            print(f"  {f.name}: fewer than two acknowledges")
            continue
        a, b = t1[0], t1[1]
        inner = rows[a:b + 1]
        low = sum(1 for r in inner if r[2] == 0)
        code = [i for i in range(a, b) if rows[i][0] == "T1"
                and rows[i][1] == "CODE"]
        print(f"  {f.name}: INTA1 T1={a} INTA2 T1={b}  "
              f"LOCK_N low on {low}/{len(inner)} clocks of the interval  "
              f"CODE T1s inside it: {code}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("flush")
    p.add_argument("--suites", nargs="+", required=True, help="SUITE:WAITS")
    p.add_argument("--forms", nargs="*")
    p.set_defaults(fn=cmd_flush)
    p = sub.add_parser("lock")
    p.add_argument("--dir", default="sw/testdata/s10/s1-tranche")
    p.add_argument("--glob", default="INT.F3AA_w*.raw.hex.gz")
    p.set_defaults(fn=cmd_lock)
    p = sub.add_parser("gap")
    p.add_argument("--suites", nargs="+", required=True,
                   help="SUITE:WAITS")
    p.add_argument("--forms", nargs="*")
    p.add_argument("--dump", default="")
    p.set_defaults(fn=cmd_gap)
    a = ap.parse_args()
    if getattr(a, "suites", None):
        a.suites = [(s.rsplit(":", 1)[0], int(s.rsplit(":", 1)[1]))
                    for s in a.suites]
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
