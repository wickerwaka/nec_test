#!/usr/bin/env python3
"""fz2_termcost -- WHAT THE TERMINATING NMI'S TAIL ACTUALLY COSTS, measured on
the board's own rows, in the capture's own absolute row numbers.

THE INSTRUMENT FOR AMENDMENT A-3.  Finding O-2a said the terminator fires and
is intercepted but the dump does not complete inside the 4,096-row capture, and
guessed that the raw tier "is not sitting at the anchor when the NMI lands".
This tool measures the guess.  It is REFUTED: the anchor row is IDENTICAL in
both tiers to the clock, and so is the dump.  What was wrong is the budget's
own arithmetic (see `fuzz_campaign.term_clocks`).

Everything here is read off BANKED CAPTURES -- no board, no TB, no engine.
Every number A-3 quotes is printed by `python3 sw/fz2_termcost.py measure`.

WHAT IS MEASURED, per capture, on the SOCKET leg's rows:

    f        the row the terminating NMI asserts.  Identified as the pin_nmi
             run of length `TERM_HOLD`; a stimulus NMI holds 2 or 300 and is
             therefore a different run, never this one.
    anchor   f - term_clocks.  The rig counts the delay from the anchor's own
             CODE T1, so this recovers the anchor's ABSOLUTE row.  It comes out
             a single exact value per wait level over hundreds of captures,
             which is the evidence that the scheduler's delay is exact.
    entry    f -> the first `OUT OUT_PORT_REGS` at or after f.  The NMI
             acceptance latency plus the two vector reads, three pushes and the
             handler's first fetch.  THE TERM THE BUDGET NEVER HAD.
    dump     that `OUT` -> the `OUT OUT_PORT_DONE` done marker.  The dump
             proper.
    left     4095 - f.  The tail room the budget actually left.

CENSORING IS THE POINT.  `entry` and `dump` are observable only while
`entry + dump <= left`, so both are RIGHT-CENSORED at `left` and the observed
maximum of `anchor + tail` is pinned at the reserve.  `measure` prints that
pinning; it is the arithmetic proof that the budget, not the seed, was the
binding limit.

`predict` applies a candidate constant set to the same banked captures and
reports how many measured requirements fit -- and, separately and always, how
many captures carry NO measured requirement, for which it makes no prediction.
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import sys

SW = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SW)
ROOT = os.path.dirname(SW)

import fuzz_campaign as fzc                                  # noqa: E402
import fuzz_classify as fc                                   # noqa: E402
import testimage as ti                                       # noqa: E402

CAMPAIGNS = os.path.join(ROOT, "sw", "testdata", "campaigns")
# THE TWO BANKS ARE NEVER POOLED BY DEFAULT.  `archive` is INV-2's -- the
# capture A-3's constants were measured on, taken under the pre-A-3 budget --
# and `current` is whatever the live banks hold.  Mixing them would average two
# different rigs' tails into one table, which is the one thing this instrument
# must not do; `--bank all` exists only to say so out loud.
BANKS = {"archive": ("fz2c-INV2-archive", "fz2e-INV2-archive"),
         # A-6 archived the A-5-scored capture by RENAME -- NOT an
         # invalidation: no constant moved, its rows are true silicon taken
         # under the same budget the A-6 capture uses.  Reachable so a reviewer
         # can re-run every A-6 number on the bank they were measured on.
         "prior": ("fz2c-A5-archive", "fz2e-A5-archive"),
         "current": ("fz2c", "fz2e")}
BANKS["all"] = BANKS["archive"] + BANKS["prior"] + BANKS["current"]
LAST_ROW = fzc.CAP_ROWS - 1


def _measure_one(path):
    d = json.load(gzip.open(path, "rt"))
    line, real = d["line"], d["real"]
    if not real:
        return None
    term = line.get("term") or {}
    tc = term.get("term_clocks")
    runs = ((term.get("hold_rows") or {}).get("pin_nmi")) or []
    base = real[0]["idx"]
    # THE TERMINATING NMI, and only it: `_pin_runs` returns list positions, so
    # lift them into the capture's own absolute numbering.  `TERM_HOLD` is 20
    # and a stimulus NMI holds 2 or 300, so the length identifies the run
    # without asking which one fired first.
    hits = [s + base for s, L in runs if L == fzc.TERM_HOLD]
    if tc is None or len(hits) != 1:
        return None
    f = hits[0]
    dump0 = done = None
    for r in real:
        if r.get("bs_early") != 2:              # IOW
            continue
        a = r["ad_addr"] & 0xFFFF
        if a == ti.OUT_PORT_REGS and dump0 is None:
            dump0 = r["idx"]
        elif a == ti.OUT_PORT_DONE and done is None:
            done = r["idx"]
    w = line["waits"]
    src = ("wvec" if line.get("wvec") else
           ("wrand%d" % w["wmax"]) if w["wrand"] else "fix%d" % w["fixed"])
    if line.get("wvec"):
        line["wvec"] = dict(line["wvec"])
    # `scale` comes from the seed's OWN effective wait level, through
    # `fuzz_campaign`'s one rule -- NOT by inverting `term_clocks`, because
    # captures taken before and after A-3 were handed delays from two different
    # formulae and inverting the wrong one silently mis-scales the whole table.
    weff = fzc.weff_of({"wvec": line.get("wvec"), "waits": w})
    scale = (fzc.NMAX_SCALE_C + weff) / fzc.NMAX_SCALE_C
    self_term = done is not None and done < f
    entry = (dump0 - f) if (dump0 is not None and dump0 >= f) else None
    dumpc = (done - dump0) if (done is not None and dump0 is not None
                               and dump0 >= f and done > dump0) else None
    # the bus's last transaction BEFORE the NMI: a CPU that has been idle for
    # hundreds of clocks when the pin goes high is not waiting for a boundary
    lastbus = max((r["idx"] for r in real
                   if r["idx"] < f and r["bs_early"] != 7), default=None)
    return {"seed": line["seed"], "tier": line["tier"], "src": src,
            "term_clocks": tc, "f": f, "anchor": f - tc, "left": LAST_ROW - f,
            "scale": scale, "self_term": self_term, "entry": entry,
            "dump": dumpc, "done": done,
            "tail": (done - f) if (done is not None and done >= f) else None,
            "vec_used": term.get("vec_used"), "done_real": line["done_real"],
            "idle_before_nmi": (f - lastbus) if lastbus is not None else None}


def load(bank="archive", paths=None):
    if paths is None:
        paths = []
        for cid in BANKS[bank]:
            paths += sorted(glob.glob(
                os.path.join(CAMPAIGNS, cid, "captures", "*.json.gz")))
    out = []
    for p in paths:
        try:
            m = _measure_one(p)
        except Exception as e:                              # noqa: BLE001
            print(f"  ** unreadable {os.path.basename(p)}: {str(e)[:80]}")
            continue
        if m:
            out.append(m)
    return out


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def cmd_measure(a):
    rows = load(a.bank)
    if not rows:
        print(f"fz2_termcost: no banked captures under bank {a.bank!r} "
              f"({', '.join(BANKS[a.bank])})")
        return 2
    print(f"== bank {a.bank!r} ({', '.join(BANKS[a.bank])})")
    print(f"== {len(rows)} banked captures  "
          f"({collections.Counter(r['tier'] for r in rows)})")

    print("\n== ANCHOR -- the absolute capture row of the anchor's CODE T1")
    print("   (f - term_clocks; fixed-wait strata, where it is a single value)")
    anchor = {}
    for src in ("fix0", "fix1", "fix2", "fix3"):
        for tier in ("soup", "raw"):
            v = [r["anchor"] for r in rows
                 if r["src"] == src and r["tier"] == tier]
            if v:
                anchor.setdefault(src, set()).update(v)
                print(f"   {src} {tier:5s} n={len(v):4d} distinct={sorted(set(v))}")
    same = all(len(v) == 1 for v in anchor.values())
    print(f"   -> IDENTICAL IN BOTH TIERS: {same};  ANCHOR_W0(measured) = "
          f"{sorted(anchor.get('fix0', {0}))[0]}   (the formula carries "
          f"{fzc.ANCHOR_W0})")

    print("\n== DUMP -- first `OUT 0xFE` -> done marker, terminator-entered only")
    for src in ("fix0", "fix1", "fix2", "fix3"):
        for tier in ("soup", "raw"):
            v = [r["dump"] for r in rows
                 if r["src"] == src and r["tier"] == tier and r["dump"]]
            if v:
                print(f"   {src} {tier:5s} n={len(v):4d} distinct={sorted(set(v))}")
    print(f"   -> the formula carries DUMP_W0 = {fzc.DUMP_W0}")

    pop = [r for r in rows if not r["self_term"]]
    obs = [r for r in pop if r["entry"] is not None]
    print(f"\n== ENTRY -- NMI assert -> first `OUT 0xFE`  "
          f"(terminator-needed n={len(pop)}, observed n={len(obs)})")
    e = [r["entry"] for r in obs]
    print(f"   min={min(e)} p50={_q(e,.5)} p90={_q(e,.9)} p99={_q(e,.99)} "
          f"MAX={max(e)}   (the formula carries ENTRY_MAX = {fzc.ENTRY_MAX})")
    for tier in ("soup", "raw"):
        v = [r["entry"] for r in obs if r["tier"] == tier]
        if v:
            print(f"   {tier:5s} n={len(v):4d} min={min(v)} p50={_q(v,.5)} "
                  f"max={max(v)}")
    print("   DOES IT SCALE?  max and max/scale by scale level:")
    by = collections.defaultdict(list)
    for r in obs:
        by[round(r["scale"], 4)].append(r["entry"])
    for s in sorted(by):
        print(f"     scale={s:<7} n={len(by[s]):4d} max={max(by[s]):4d} "
              f"max/scale={max(by[s])/s:7.1f}")
    print(f"   -> the formula treats this as a CLOCK cost (ENTRY_MAX added "
          f"OUTSIDE the scaling),\n      because on the ARCHIVE bank max/scale "
          f"falls monotonically 243 -> 64.  Read the\n      column above and "
          f"judge it; the sentence is not asserted of every bank.")

    print("\n== TAIL ROOM the budget left, against what the tail costs")
    for src in ("fix0", "fix1", "fix2", "fix3"):
        sel = [r for r in rows if r["src"] == src]
        if not sel:
            continue
        left = sorted({r["left"] for r in sel})
        tails = [r["tail"] for r in sel if r["tail"] is not None]
        print(f"   {src} left={left}  tail(observed) "
              f"{'min=%d max=%d n=%d' % (min(tails), max(tails), len(tails))
                 if tails else 'none observed'}")

    print("\n== THE CENSORING, which is the proof the BUDGET was the limit")
    need = [(r["anchor"] + r["tail"]) / r["scale"]
            for r in rows if r["tail"] is not None]
    print(f"   (anchor + tail) / scale over {len(need)} completions: "
          f"min={min(need):.1f} p50={_q(need,.5):.1f} max={max(need):.1f}")
    res = {round((fzc.CAP_ROWS - r["term_clocks"]) / r["scale"], 1)
           for r in rows}
    print(f"   the reserve these captures were actually taken under, per unit "
          f"scale: {sorted(res)}")
    print(f"   (pre-A-3 that was TERM_MARGIN x (145 + 240) = {1.2*385:.1f} flat)")
    # THE DECISIVE, NON-ARBITRARY TEST: how many completions carry a
    # requirement the PRE-A-3 reserve could not have recorded at all?  On the
    # archive bank that number is 0 BY CONSTRUCTION -- which is the whole
    # point, and why its maximum lands one row under 462.0 rather than
    # anywhere in particular.
    done = [r for r in rows if r["tail"] is not None]
    over = sum(1 for r in done
               if (r["anchor"] + r["tail"]) / r["scale"] > 1.2 * 385)
    print(f"   completions whose requirement EXCEEDS the pre-A-3 reserve of "
          f"{1.2*385:.1f}/scale: {over} / {len(done)}")
    if over == 0:
        print("   NONE -- and the maximum lands at the reserve itself.  That "
              "is right-censoring at\n   the budget: the budget, not the "
              "seed, was the binding limit.")
    else:
        print("   These are requirements the pre-A-3 budget COULD NOT HAVE "
              "RECORDED.  The censoring\n   is lifted and the distribution's "
              "upper end is visible for the first time.")

    print("\n== O-2d -- A SECOND, INDEPENDENT MECHANISM, separated here")
    cens = [r for r in pop if r["entry"] is None]
    stopped = [r for r in cens if (r["idle_before_nmi"] or 0) >= 200]
    late = [r for r in cens if (r["idle_before_nmi"] or 0) < 200]
    print(f"   terminator-needed captures whose dump never started: {len(cens)}")
    print(f"     bus ALREADY IDLE >= 200 clocks when the NMI arrived: "
          f"{len(stopped)}   vec_used="
          f"{dict(collections.Counter(r['vec_used'] for r in stopped))}")
    if stopped:
        g = sorted(r["idle_before_nmi"] for r in stopped)
        print(f"       idle clocks before the NMI: min={g[0]} "
              f"p50={_q(g,.5)} max={g[-1]}")
        print(f"       tiers: {dict(collections.Counter(r['tier'] for r in stopped))}")
    print(f"     bus still RUNNING at the NMI (the TERM_CLOCKS class): "
          f"{len(late)}   vec_used="
          f"{dict(collections.Counter(r['vec_used'] for r in late))}")
    print("   The first group is NOT a budget problem: the CPU stopped "
          "issuing bus cycles\n   thousands of clocks before the terminator, "
          "and the terminating NMI does not\n   restart it.  No TERM_CLOCKS "
          "value reaches it.")
    return 0


def cmd_predict(a):
    """Apply a candidate constant set to the SAME banked captures.  Reports
    what fits, and -- separately, never folded in -- what carries no measured
    requirement and therefore gets no prediction."""
    rows = load(a.bank)
    if not rows:
        print(f"fz2_termcost: no banked captures under bank {a.bank!r}")
        return 2
    print(f"== bank {a.bank!r} ({', '.join(BANKS[a.bank])})")
    anchor, dump, entry, marg = a.anchor, a.dump, a.entry, a.margin

    def reserve(scale):
        return math.ceil(marg * (anchor + dump) * scale) + entry

    print(f"== candidate: ANCHOR_W0={anchor} DUMP_W0={dump} "
          f"ENTRY_MAX={entry} TERM_MARGIN={marg}")
    print("   TERM_CLOCKS by weff (floor is "
          f"{fzc.TERM_FLOOR}):")
    for w in (0, 1, 2, 3, 7, 8, 15):
        s = (fzc.NMAX_SCALE_C + w) / fzc.NMAX_SCALE_C
        tc = fzc.CAP_ROWS - reserve(s)
        old = fzc.CAP_ROWS - math.ceil(1.2 * 385 * s)
        print(f"     weff={w:2d} scale={s:4.2f}  pre-A-3={old:5d}  "
              f"candidate={tc:5d}  {'OK' if tc >= fzc.TERM_FLOOR else '*** FLOOR BREACH'}")

    for r in rows:
        r["ntc"] = fzc.CAP_ROWS - reserve(r["scale"])
        r["nleft"] = LAST_ROW - (r["anchor"] + r["ntc"])
    pop = [r for r in rows if not r["self_term"]]
    full = [r for r in pop if r["entry"] is not None and r["dump"] is not None]
    part = [r for r in pop if r["entry"] is not None and r["dump"] is None]
    none = [r for r in pop if r["entry"] is None]
    fit_full = sum(1 for r in full if r["entry"] + r["dump"] <= r["nleft"])
    fit_part = sum(1 for r in part
                   if r["entry"] + math.ceil(fzc.DUMP_W0 * r["scale"])
                   <= r["nleft"])
    print(f"\n   terminator-needed banked captures: {len(pop)}")
    print(f"     entry AND dump measured : {len(full):4d}  fit: {fit_full}")
    print(f"     entry measured only     : {len(part):4d}  fit with the dump "
          f"scaled ({fzc.DUMP_W0} x scale): {fit_part}")
    print(f"     NO measured requirement : {len(none):4d}  -- NO PREDICTION "
          f"IS MADE FOR THESE")
    # THE COST OF THE FIX, reported whether or not anyone asked: an earlier
    # terminator pre-empts runs that would have ended on their own.  That is
    # not a loss -- the terminator's own dump still produces the arch column --
    # but it changes which route ended the run, and it is registered.
    st = [r for r in rows if r["self_term"]]
    pre = [r for r in st if r["done"] > r["anchor"] + r["ntc"]]
    print(f"\n   self-terminating captures: {len(st)};  done marker AFTER the "
          f"new NMI row: {len(pre)} ({100*len(pre)/max(1,len(st)):.1f} %)")
    print(f"     tiers: {dict(collections.Counter(r['tier'] for r in pre))}")
    return 0


# --------------------------------------------------------------------------- #
# AMENDMENT A-6 (prereg §17) -- WHY A CAPTURE DID NOT REACH THE TERMINATOR,
# named per capture off its own rows.  This is a CENSUS, not a discard class:
# nothing here dispositions anything, and `fz2_w1.py bars` does not import it.
#
# The labels are applied in ONE fixed order and every one of them is a fact
# already defined elsewhere in the tree -- there is no new predicate here that
# is not either an existing function or the absence of a bus cycle.
# --------------------------------------------------------------------------- #
MECH = ("REACHED", "WINDOW", "FORGED_DONE", "BUDGET", "LONG_INSN",
        "STALLED", "HALT", "NEAR", "OTHER")


def mechanism(real, sim, line):
    """The label for ONE banked capture's SOCKET rows.

    `fuzz_campaign.term_mechanism` IS the definition and its docstring is the
    taxonomy; THIS FILE OWNS NO SECOND COPY OF IT.  The same function runs at
    capture time and banks its answer as the `mech` column, so a future
    capture needs no retained rows at all -- exactly the shape A-4 gave
    `stalled`.  What is here is the BACKFILL, for captures taken before A-6."""
    if not real:
        return None
    holds = ((line.get("term") or {}).get("hold_rows")) or None
    return fzc.term_mechanism(real, sim, holds)


def cmd_mechanism(a):
    for bank in (["current", "prior", "archive"] if a.bank == "all"
                 else [a.bank]):
        tot = collections.Counter()
        per_tier = collections.defaultdict(collections.Counter)
        named = collections.defaultdict(list)
        n = noev = 0
        for cid in BANKS[bank]:
            for p in sorted(glob.glob(os.path.join(
                    CAMPAIGNS, cid, "captures", "*.json.gz"))):
                d = json.load(gzip.open(p, "rt"))
                lab = mechanism(d.get("real"), d.get("sim"), d["line"])
                if lab is None:
                    noev += 1
                    continue
                n += 1
                tot[lab] += 1
                per_tier[d["line"]["tier"]][lab] += 1
                if lab != "REACHED":
                    named[lab].append(f"{cid}/{d['line']['k']}")
        print(f"== bank {bank!r} ({', '.join(BANKS[bank])}): "
              f"{n} banked captures")
        for lab in MECH:
            if tot[lab]:
                print(f"   {lab:12s} {tot[lab]:5d}   "
                      f"soup {per_tier['soup'][lab]:4d}  "
                      f"raw {per_tier['raw'][lab]:4d}")
        print(f"   {'TOTAL':12s} {n:5d}   not evaluable {noev}")
        print(f"   NOT REACHED: {n - tot['REACHED']}   of which the two "
              f"INSTRUMENT classes (D-1 WINDOW + D-2 FORGED_DONE) are "
              f"{tot['WINDOW'] + tot['FORGED_DONE']}")
        if a.names:
            for lab in MECH:
                if named[lab]:
                    print(f"   -- {lab}: {' '.join(sorted(named[lab]))}")
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--bank", choices=sorted(BANKS), default="archive")
    p = sub.add_parser("predict")
    p.add_argument("--bank", choices=sorted(BANKS), default="archive")
    p.add_argument("--anchor", type=int, default=fzc.ANCHOR_W0)
    p.add_argument("--dump", type=int, default=fzc.DUMP_W0)
    p.add_argument("--entry", type=int, default=fzc.ENTRY_MAX)
    p.add_argument("--margin", type=float, default=fzc.TERM_MARGIN)
    q = sub.add_parser("mechanism")
    q.add_argument("--bank", choices=sorted(BANKS), default="current")
    q.add_argument("--names", action="store_true")
    a = ap.parse_args()
    return {"measure": cmd_measure, "predict": cmd_predict,
            "mechanism": cmd_mechanism}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
