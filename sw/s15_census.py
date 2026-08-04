#!/usr/bin/env python3
"""s15_census -- the FUZZ-BANK RESIDUE census (ucsim_t_provenance 26).

OFFLINE, board-free.  NOT a gate: a measurement tool.  It takes a
`timed_fuzz --report` and, for every seed the model does not reproduce
clock-exactly, reads the first divergence IN CONTEXT and lands it in exactly
one named family.

Five sessions (S9b .. S14) scored these populations and none opened them case
by case:

  REGISTERED  1,702 seeds, 1,272 exact ->  430 non-exact
  EVT         1,008 seeds,   708 exact ->  300 non-exact

`timed_fuzz`'s own `kind` (`qs` / `bs` / `data` / `nxta` / `ube` / `ps`) is the
COLUMN that parted, which is an effect.  This file classifies on the BUS
STRUCTURE, which is the thing a BIU is:

  the LAUNCH SEQUENCE   every bus cycle as (status, address) in order, chip
                        against model.  If the sequences agree, the two sides
                        ran the same bus program.
  the LAUNCH TIMES      the T1 clock of each of those cycles.  If the sequences
                        agree and the times do not, the difference is WHEN a
                        cycle was granted -- a scheduling question, and the
                        first offending cycle's delta is the whole content of
                        the divergence.
  the PINS              if sequence and times both agree, what is left is what
                        the part was DRIVING on a row: the queue status, UBE,
                        the multiplexed data lanes.

which gives three top-level families, in order of how much of the machine is
implicated:

  PIN       the bus schedules are IDENTICAL over the window; a pin column
            differs.  No cycle moved.
  SCHEDULE  the same cycles, in the same order, at different clocks.  The
            reported number is the FIRST offending cycle's delta.
  SEQUENCE  the model runs a DIFFERENT bus cycle -- another status, or the
            same status at another address.

and two orthogonal severity axes read with the campaign's own instruments:

  FUNC      `fuzz_classify.compare_functional` -- does the ordered functional
            event stream (the writes, the reads, the acknowledges) part?
  ARCH      `fuzz_classify.arch_dump` -- do the 12 STORE_ORDER registers and
            the PSW the two sides finish with agree?

A seed that is SEQUENCE-clean, FUNC-clean and ARCH-clean is a pure timing
residue.  A seed that is not is a model error with architectural reach, and
the census exists to say which of the 730 are which.

THE ENGINE IS A FLAG (R4, 2026-08-04).  This tool used to call `tf.run_sim`
UNCONDITIONALLY and take only the SEED LIST from `--report`, so pointing it at a
`--core ucore` report ran clean and silently reported the MODEL's families for
the ucore's seeds -- the accepted-and-ignored shape.  `--core` now selects the
replay engine exactly as `timed_fuzz --core` does, with the same `choices=`, so
an RTL core's own residue gets its own census.  **`--core` must match the
report's core**; the report supplies which seeds diverged and the engine
supplies why, and mixing them describes neither.

Usage:
  s15_census.py --report r.json [--core sim|ucore|fsm] [--pop reg|evt|all]
                [--jobs N] [--dump out.json.gz] [--seeds N] [--show FAMILY]
"""
import argparse
import gzip
import json
import os
import sys
import tempfile
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                              # noqa: E402
import timed_fuzz as tf                                 # noqa: E402
import ucsim_fuzz as uf                                 # noqa: E402

BS = fc.BS_NAME
QS = fc.QS_NAME
T = fc.T_NAME


def launches(rows, n):
    """Every bus cycle in row order as (t1_index, status, address).  A cycle is
    its T1 row -- the clock the part opened the access.  Pins only."""
    out = []
    for i in range(min(n, len(rows))):
        r = rows[i]
        if r.get("t_state", r.get("t")) == 1:
            out.append((i, BS[r["bs_early"]], r["ad_addr"] & 0xFFFFF))
    return out


def seq_shift(lc, ls, j, run=24, thr=0.85):
    """At the first cycle whose (status, address) differ, is one side simply
    MISSING a cycle the other ran?

    Returns (shift, match).  shift > 0: the CHIP ran `shift` cycles the model
    did not, and the two sequences agree again after skipping them.  shift < 0:
    the MODEL ran extra cycles.  shift == 0 with a high match cannot happen (it
    is the definition of `j`), so a returned 0 means NOTHING aligns and the two
    sides genuinely diverged."""
    best, bestf = 0, 0.0
    for s in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 8, -8, 12, -12):
        a, b = j + max(s, 0), j + max(-s, 0)
        m = tot = 0
        for i in range(run):
            if a + i >= len(lc) or b + i >= len(ls):
                break
            tot += 1
            if lc[a + i][1:] == ls[b + i][1:]:
                m += 1
        f = m / tot if tot else 0.0
        if f > bestf + 1e-12:
            best, bestf = s, f
    return (best, round(bestf, 3)) if bestf >= thr else (0, round(bestf, 3))


def cyc_context(rows, i):
    """The enclosing bus cycle of row `i` as (status, offset from its T1)."""
    for j in range(i, -1, -1):
        tt = rows[j].get("t_state", rows[j].get("t"))
        if tt == 1:
            return (BS[rows[j]["bs_early"]], i - j)
        if tt == 5 and j != i:
            return ("IDLE", i - j)
    return ("PRE", i)


def markers(rows, n):
    """Chip-side positions of the acknowledge runs, the HALT statuses and the
    queue clears -- the three things the earlier sessions' taxonomies keyed on."""
    inta, halt, flush = [], [], []
    prev = None
    for i in range(min(n, len(rows))):
        r = rows[i]
        if r.get("t_state", r.get("t")) == 1:
            k = BS[r["bs_early"]]
            if k == "INTA" and prev != "INTA":
                inta.append(i)
            if k == "HALT":
                halt.append(i)
            prev = k
        if r["qs"] == 2:
            flush.append(i)
    return inta, halt, flush


def nearest(xs, i):
    return min((abs(i - x) for x in xs), default=None)


def signature(d, chip, sim, i):
    """The first-divergence signature with VALUES NORMALISED OUT, except where
    the value IS the family (a status pair, a queue-status pair, a T-state)."""
    parts = []
    if d.qs_txt:
        parts.append(f"qs {QS[chip[i]['qs']]}!={QS[sim[i]['qs']]}")
    for o in d.other:
        w = o.split()
        parts.append(o if w[0] in ("bs", "t", "ube", "ps") else w[0])
    return " ".join(parts)


def replay(entry, image, meta, chip, win, core, hold_mode):
    """Run the seed through ONE engine and return its rows.

    The two engines take DIFFERENT event inputs and that is the whole reason
    this used to be hard-wired:

      the C++ model  is HANDED the capture's acknowledge positions
                     (`tf.evt_directive`, a REPLAY directive) -- it does not
                     predict them.
      an RTL core    is handed the RIG's own directive (`tf.evt_tuple`,
                     addr/delay/hold/pin) and PREDICTS the acknowledges, which
                     is exactly why the EVT population reads differently
                     between them (F46 / gap T5).

    So the census of an RTL core's residue is not the model's census with a
    different binary; it is a different measurement, and it is one this tool
    could not take until now."""
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            evt = (tf.evt_directive(entry, meta, chip, win)
                   if entry.get("evt") else None)
            rows, _err = tf.run_sim(image, entry, len(chip), td, evt)
        else:
            evt = (tf.evt_tuple(entry, meta, hold_mode)
                   if entry.get("evt") else None)
            rows, _err = tf.run_tb(image, entry, len(chip), td, core, evt)
    return rows


def one(rec):
    path = rec["path"]
    core = rec.get("_core", "sim")
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    image, meta, _g, _sha = uf.regen(entry)
    chip = entry["chip_rows"]
    win = uf.window_of(chip)
    sim = replay(entry, image, meta, chip, win, core,
                 rec.get("_rig_hold", "banked"))
    dr = fc.diff_rows(chip, sim)
    w = entry.get("waits") or {}
    out = {"path": path, "cid": rec["cid"], "k": rec["k"], "pop": rec["pop"],
           "waitclass": (f"wrand{w.get('wmax')}" if w.get("wrand")
                         else f"fix{w.get('fixed') or 0}"),
           "waited": bool(w.get("wrand") or (w.get("fixed") or 0)),
           "pin": (entry.get("evt") or {}).get("pin")}
    if not dr.rows:
        out["cat"] = "NOW_EXACT"
        return out
    n = dr.n
    d0 = dr.rows[0]
    fb = d0.i
    out["cat"] = "DIVERGE"

    # --- the bus structure ------------------------------------------------ #
    lc, ls = launches(chip, n), launches(sim, n)
    m = min(len(lc), len(ls))
    seq_at = next((j for j in range(m) if lc[j][1:] != ls[j][1:]), None)
    tim_at = next((j for j in range(m) if lc[j][0] != ls[j][0]), None)
    out["ncyc_chip"], out["ncyc_sim"] = len(lc), len(ls)
    if seq_at is not None and (tim_at is None or seq_at <= tim_at):
        sh, mf = seq_shift(lc, ls, seq_at)
        # PRIMARY axis -- the ARBITRATION verdict at the first slot the two
        # sides disagree about.  It is always defined, whether or not the
        # sequences ever realign, and it names WHO GOT THE BUS.
        ck, sk = lc[seq_at][1], ls[seq_at][1]
        if ck == "CODE" and sk != "CODE":
            out["fam"] = "PF_LOST"          # chip prefetched, model did not
        elif ck != "CODE" and sk == "CODE":
            out["fam"] = "PF_GAINED"        # model prefetched, chip did not
        elif ck == "CODE":
            out["fam"] = "PF_ADDR"          # both fetched, different address
        else:
            out["fam"] = "DATA_SEQ"         # two data cycles that differ
        out["recov"] = ("MISS" if sh > 0 else "EXTRA" if sh < 0 else "NONE")
        out["seq_shift"], out["seq_match"] = sh, mf
        # is it an ORDER SWAP -- the same two cycles, the other way round?
        out["swap"] = (seq_at + 1 < min(len(lc), len(ls)) and
                       lc[seq_at][1:] == ls[seq_at + 1][1:] and
                       lc[seq_at + 1][1:] == ls[seq_at][1:])
        # the local cycle window, both sides, so a family can be drilled into
        # from the dump without re-running the model.
        out["win_chip"] = [f"{c[1]}:{c[2]:05x}@{c[0]}"
                           for c in lc[max(0, seq_at - 3):seq_at + 6]]
        out["win_sim"] = [f"{c[1]}:{c[2]:05x}@{c[0]}"
                          for c in ls[max(0, seq_at - 3):seq_at + 6]]
        out["at_cyc"] = seq_at
        out["at_row"] = lc[seq_at][0]
        out["chip_cell"] = f"{lc[seq_at][1]} {lc[seq_at][2]:05x}"
        out["sim_cell"] = f"{ls[seq_at][1]} {ls[seq_at][2]:05x}"
        out["delta"] = ls[seq_at][0] - lc[seq_at][0]
        out["seq_what"] = ("status" if ck != sk else "address")
        # the cycle ONE side ran and the other did not, named by the side that
        # ran it -- this is the whole content of a MISS / EXTRA family member.
        if sh > 0:
            out["odd_cell"] = " ".join(f"{lc[seq_at+i][1]}" for i in range(sh))
        elif sh < 0:
            out["odd_cell"] = " ".join(f"{ls[seq_at+i][1]}" for i in range(-sh))
        else:
            out["odd_cell"] = None
    elif tim_at is not None:
        out["fam"] = "SCHEDULE"
        out["recov"] = "-"
        out["seq_shift"], out["seq_match"] = 0, 1.0
        out["swap"] = False
        out["win_chip"] = [f"{c[1]}:{c[2]:05x}@{c[0]}"
                           for c in lc[max(0, tim_at - 3):tim_at + 6]]
        out["win_sim"] = [f"{c[1]}:{c[2]:05x}@{c[0]}"
                          for c in ls[max(0, tim_at - 3):tim_at + 6]]
        out["at_cyc"] = tim_at
        out["at_row"] = lc[tim_at][0]
        out["chip_cell"] = f"{lc[tim_at][1]} {lc[tim_at][2]:05x}"
        out["sim_cell"] = f"{ls[tim_at][1]} {ls[tim_at][2]:05x}"
        out["delta"] = ls[tim_at][0] - lc[tim_at][0]
        out["seq_what"] = None
    else:
        # The sequences agree over the COMMON PREFIX and so do the times.  If
        # one side launched MORE cycles than the other, the difference is at
        # the TAIL -- one side is still running where the other has parked --
        # and that is not a pin question.  It has to be split out or it would
        # sit inside PIN and make the taxonomy lie.
        if len(ls) > len(lc):
            out["fam"] = "TAIL_EXTRA"        # the model runs on past the chip
        elif len(lc) > len(ls):
            out["fam"] = "TAIL_MISS"         # the chip runs on past the model
        else:
            out["fam"] = "PIN"
        out["recov"] = "-"
        out["seq_shift"] = len(ls) - len(lc)
        out["seq_match"] = 1.0
        out["swap"] = False
        out["win_chip"] = [f"{c[1]}:{c[2]:05x}@{c[0]}" for c in lc[-4:]]
        out["win_sim"] = [f"{c[1]}:{c[2]:05x}@{c[0]}" for c in ls[-4:]]
        out["at_cyc"] = None
        out["at_row"] = fb
        out["chip_cell"] = out["sim_cell"] = None
        out["delta"] = 0
        out["seq_what"] = None

    # --- the two severity axes, with the campaign's own instruments ------- #
    f = fc.compare_functional(chip, sim, win)
    out["func_bad"] = bool(f.mismatch)
    out["func_kind"] = f.first_kind
    out["func_trunc"] = bool(f.truncated)
    out["func_detail"] = (f.detail or "")[:120]
    ac, as_ = fc.arch_dump(chip, win), fc.arch_dump(sim, win)
    if ac is None or as_ is None:
        out["arch"] = "NODUMP"
        out["arch_bad"] = None
    else:
        bad = sorted(k for k in ac if ac[k] != as_[k])
        out["arch"] = ",".join(bad) if bad else "OK"
        out["arch_bad"] = bool(bad)

    # --- the first divergence in context ---------------------------------- #
    inta, halt, flush = markers(chip, n)
    cc, sc = cyc_context(chip, fb), cyc_context(sim, fb)
    last = dr.rows[-1].i
    out.update({
        "n": n, "fb": fb, "ndiff": len(dr.rows), "last_bad": last,
        "span": last - fb, "tail": n - last,
        "kind": tf.first_kind(d0), "sig": signature(d0, chip, sim, fb),
        "chip_cyc": cc[0], "chip_off": cc[1],
        "sim_cyc": sc[0], "sim_off": sc[1],
        "d_inta": nearest(inta, fb), "d_halt": nearest(halt, fb),
        "d_flush": nearest(flush, fb),
        "n_inta": len(inta), "n_halt": len(halt),
    })
    return out


def report(rows, show=""):
    div = [r for r in rows if r["cat"] == "DIVERGE"]
    print(f"\n  seeds {len(rows)}   diverging {len(div)}   "
          f"now-exact {len(rows)-len(div)}")

    print("\n  === TOP-LEVEL FAMILY (the bus structure) ===")
    for k, v in Counter(r["fam"] for r in div).most_common():
        sub = [r for r in div if r["fam"] == k]
        d = sorted(x["delta"] for x in sub)
        print(f"    {k:<10} {v:>4}   first offending cycle: median #"
              f"{sorted(x['at_cyc'] or 0 for x in sub)[len(sub)//2]:<5}"
              f"  delta median {d[len(d)//2]:+d}  range {d[0]:+d}..{d[-1]:+d}")

    print("\n  family x population:")
    fams = sorted({r["fam"] for r in div})
    tab = Counter((r["pop"], r["fam"]) for r in div)
    print("    " + "pop".ljust(6) + "".join(f"{f:>11}" for f in fams))
    for p in sorted({r["pop"] for r in div}):
        print("    " + p.ljust(6) + "".join(f"{tab[(p,f)]:>11}" for f in fams))

    print("\n  === SEVERITY (the campaign's own instruments) ===")
    print(f"    functional event stream parts   "
          f"{sum(1 for r in div if r['func_bad']):>4} / {len(div)}")
    print(f"    functional stream TRUNCATED     "
          f"{sum(1 for r in div if r['func_trunc'] and not r['func_bad']):>4} / {len(div)}")
    ok = [r for r in div if r["arch"] == "OK"]
    nd = [r for r in div if r["arch"] == "NODUMP"]
    bad = [r for r in div if r.get("arch_bad")]
    print(f"    architectural state AGREES      {len(ok):>4} / {len(div)}")
    print(f"    architectural state DIFFERS     {len(bad):>4} / {len(div)}")
    print(f"    no arch dump inside the window  {len(nd):>4} / {len(div)}")
    if bad:
        print("      registers that differ:")
        for k, v in Counter(r["arch"] for r in bad).most_common(12):
            print(f"        {v:>4}  {k}")

    print("\n  severity x family:")
    print(f"    {'family':<10}{'n':>6}{'func-bad':>10}{'arch-bad':>10}"
          f"{'arch-OK':>9}{'nodump':>8}")
    for k in fams:
        s = [r for r in div if r["fam"] == k]
        print(f"    {k:<10}{len(s):>6}"
              f"{sum(1 for r in s if r['func_bad']):>10}"
              f"{sum(1 for r in s if r.get('arch_bad')):>10}"
              f"{sum(1 for r in s if r['arch'] == 'OK'):>9}"
              f"{sum(1 for r in s if r['arch'] == 'NODUMP'):>8}")

    print("\n  === SCHEDULE family: the first offending cycle ===")
    sch = [r for r in div if r["fam"] == "SCHEDULE"]
    if sch:
        print("    delta (model T1 minus chip T1) of the FIRST cycle that moved:")
        for k, v in sorted(Counter(r["delta"] for r in sch).items()):
            print(f"      {k:+4d}  {v}")
        print("    its status:")
        for k, v in Counter(r["chip_cell"].split()[0] for r in sch).most_common():
            print(f"      {k:<6} {v}")
        print("    the chip cycle it FOLLOWS (what the schedule reacted to):")
        for k, v in Counter(r["chip_cyc"] for r in sch).most_common(8):
            print(f"      {k:<6} {v}")

    print("\n  === RECOVERY (does the bus sequence realign?) ===")
    print(f"    {'family':<10}{'n':>6}{'MISS':>7}{'EXTRA':>7}{'NONE':>7}"
          f"   the odd cycle(s), top 4")
    for k in fams:
        s_ = [r for r in div if r["fam"] == k]
        odd = Counter(r.get("odd_cell") for r in s_ if r.get("odd_cell"))
        print(f"    {k:<10}{len(s_):>6}"
              f"{sum(1 for r in s_ if r['recov']=='MISS'):>7}"
              f"{sum(1 for r in s_ if r['recov']=='EXTRA'):>7}"
              f"{sum(1 for r in s_ if r['recov']=='NONE'):>7}   "
              + "  ".join(f"{a}x{b}" for a, b in odd.most_common(4)))

    print("\n  === ORDER SWAP (the same two cycles, the other way round) ===")
    for k in fams:
        s_ = [r for r in div if r["fam"] == k]
        sw = sum(1 for r in s_ if r.get("swap"))
        if sw:
            print(f"    {k:<10} {sw}/{len(s_)}")

    print("\n  === the ARBITRATION cell, chip status -> model status ===")
    seq = [r for r in div if r.get("chip_cell") and r["fam"] != "SCHEDULE"]
    for k, v in Counter((r["chip_cell"].split()[0], r["sim_cell"].split()[0])
                        for r in seq).most_common(16):
        print(f"    {k[0]:<6} -> {k[1]:<6} {v}")

    print("\n  === TAIL families: one side still running ===")
    for k in ("TAIL_EXTRA", "TAIL_MISS"):
        t = [r for r in div if r["fam"] == k]
        if not t:
            continue
        d = sorted(abs(r["seq_shift"]) for r in t)
        print(f"    {k:<11} {len(t):>4}   extra cycles: median {d[len(d)//2]}"
              f"  max {d[-1]}   sig: "
              + "  ".join(f"{a}x{b}" for a, b in
                          Counter(r["sig"] for r in t).most_common(3)))

    print("\n  === PIN family: which pin ===")
    pin = [r for r in div if r["fam"] == "PIN"]
    if pin:
        for k, v in Counter(r["sig"] for r in pin).most_common(15):
            print(f"    {v:>4}  {k}")
        print("    chip-side context (cycle + offset):")
        for k, v in Counter((r["chip_cyc"], r["chip_off"])
                            for r in pin).most_common(10):
            print(f"      {v:>4}  {k[0]:<6} +{k[1]}")

    print("\n  === first-divergence SIGNATURE over all diverging seeds ===")
    for k, v in Counter(r["sig"] for r in div).most_common(20):
        print(f"    {v:>4}  {k}")

    print("\n  by wait class (diverging seeds):")
    for k, v in sorted(Counter(r["waitclass"] for r in div).items()):
        print(f"    {k:<10} {v}")
    print("  by bank:")
    for k, v in sorted(Counter(r["cid"] for r in div).items()):
        print(f"    {k:<10} {v}")

    if show:
        print(f"\n  === {show} members ===")
        for r in sorted((r for r in div if r["fam"] == show),
                        key=lambda r: r["fb"]):
            print(f"    {r['cid']}/{r['k']:<6} {r['waitclass']:<8} fb={r['fb']:<5}"
                  f" cyc#{r['at_cyc']} d={r['delta']:+d} "
                  f"chip[{r['chip_cell']}] sim[{r['sim_cell']}] "
                  f"func={'BAD' if r['func_bad'] else 'ok'} arch={r['arch']}"
                  f"  {r['sig']}")



# --------------------------------------------------------------------------- #
# the RMW census -- CHIP ONLY, no model, over EVERY banked seed
#
# `timed_lawcards` carries C6/C7 (LC3, the Tw-parity RMW-write commit) as
# UNRESOLVED with the reason, verbatim: "no golden, no fuzz seed and no T2b
# capture carries an RMW mem-write ready-AT-T4 with a controlled Tw parity",
# and 24.6 declared the positive-control SEARCH board-by-construction.  That is
# a statement about the banked corpus and it is testable offline.  This scans
# every seed's chip capture for a read and a write to the SAME address, reads
# the geometry the card is about, and reports the population.
# --------------------------------------------------------------------------- #
def rmw_pairs(rows, n, maxgap=6):
    """Every (read, write) pair to the same address within `maxgap` cycles, as
    the chip drove them.  Returns dicts carrying the geometry LC3 asks about:
    the cycles between them, whether a PREFETCH took the gap, each cycle's Tw
    count, and the write's T1 measured from the preceding cycle's T4."""
    cyc = []
    cur = None
    for i in range(min(n, len(rows))):
        r = rows[i]
        t = r.get("t_state", r.get("t"))
        if t == 1:
            if cur:
                cyc.append(cur)
            cur = {"t1": i, "kind": BS[r["bs_early"]],
                   "addr": r["ad_addr"] & 0xFFFFF, "tw": 0, "t4": None}
        elif cur is not None:
            if t == 4:
                cur["tw"] += 1
            elif t == 5:
                cur["t4"] = i
    if cur:
        cyc.append(cur)
    out = []
    for a in range(len(cyc)):
        if cyc[a]["kind"] not in ("MEMR", "IOR"):
            continue
        for b in range(a + 1, min(a + 1 + maxgap, len(cyc))):
            if cyc[b]["kind"] not in ("MEMW", "IOW"):
                continue
            if cyc[b]["addr"] != cyc[a]["addr"]:
                continue
            mid = cyc[a + 1:b]
            prev = cyc[b - 1]
            out.append({
                "read_t1": cyc[a]["t1"], "read_tw": cyc[a]["tw"],
                "write_t1": cyc[b]["t1"], "write_tw": cyc[b]["tw"],
                "gap_kinds": [c["kind"] for c in mid],
                "gap_tw": [c["tw"] for c in mid],
                "prefetch_in_gap": any(c["kind"] == "CODE" for c in mid),
                "prev_t4": prev["t4"], "prev_tw": prev["tw"],
                "prev_kind": prev["kind"],
                "t1_minus_prev_t4": (cyc[b]["t1"] - prev["t4"]
                                     if prev["t4"] is not None else None),
                "addr": cyc[a]["addr"],
            })
            break
    return out


def rmw_one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    chip = entry["chip_rows"]
    win = uf.window_of(chip)
    w = entry.get("waits") or {}
    wc = f"wrand{w.get('wmax')}" if w.get("wrand") else f"fix{w.get('fixed') or 0}"
    return {"path": str(path), "cid": Path(path).parent.parent.name,
            "waitclass": wc, "evt": bool(entry.get("evt")),
            "pairs": rmw_pairs(chip, win)}


def cmd_rmw(a):
    paths = []
    for b in ("mc1", "mc2", "t30-raw", "t30-brkem"):
        d = ROOT / "tests" / "v30" / "fuzz_bank" / b / "seeds"
        if d.is_dir():
            paths += sorted(str(p) for p in d.glob("*.json.gz"))
    if a.seeddir:
        paths = sorted(str(p) for p in Path(a.seeddir).glob("*.json.gz"))
    print(f"== RMW census -- CHIP ONLY, {len(paths)} banked seeds", flush=True)
    with Pool(a.jobs) as pool:
        res = pool.map(rmw_one, paths, chunksize=8)
    pairs = [(r, p) for r in res for p in r["pairs"]]
    seeds = {r["path"] for r, _ in pairs}
    print(f"  seeds carrying at least one same-address READ->WRITE pair: "
          f"{len(seeds)} / {len(paths)}")
    print(f"  pairs total: {len(pairs)}")
    print("\n  what occupies the gap between the read and the write:")
    for k, v in Counter(tuple(p["gap_kinds"]) for _, p in pairs).most_common(12):
        print(f"    {v:>6}  {k if k else '(nothing -- back to back)'}")
    pf = [(r, p) for r, p in pairs if p["prefetch_in_gap"]]
    print(f"\n  pairs where a PREFETCH took the gap: {len(pf)} / {len(pairs)}"
          f"   ({len({r['path'] for r, _ in pf})} seeds)")
    print("\n  the LC3 geometry -- the write's T1 measured from the PREVIOUS")
    print("  cycle's T4, against that previous cycle's Tw PARITY:")
    tab = Counter()
    for _, p in pairs:
        if p["t1_minus_prev_t4"] is None:
            continue
        tab[(p["prev_kind"], p["prev_tw"] % 2, p["t1_minus_prev_t4"])] += 1
    print(f"    {'prev':<6}{'Tw par':>7}{'T1 - prevT4':>13}{'n':>9}")
    for k in sorted(tab):
        print(f"    {k[0]:<6}{k[1]:>7}{k[2]:>13}{tab[k]:>9}")
    print("\n  the same, restricted to pairs whose gap is a PREFETCH")
    print("  (LC3's own cell: a prefetch running when the RMW write is ready):")
    tab2 = Counter()
    for _, p in pf:
        if p["t1_minus_prev_t4"] is None:
            continue
        tab2[(p["prev_kind"], p["prev_tw"] % 2, p["t1_minus_prev_t4"])] += 1
    print(f"    {'prev':<6}{'Tw par':>7}{'T1 - prevT4':>13}{'n':>9}")
    for k in sorted(tab2):
        print(f"    {k[0]:<6}{k[1]:>7}{k[2]:>13}{tab2[k]:>9}")
    print("\n  by wait class (pairs with a prefetch in the gap):")
    for k, v in sorted(Counter(r["waitclass"] for r, _ in pf).items()):
        print(f"    {k:<10} {v}")
    if a.dump:
        with gzip.open(a.dump, "wt") as f:
            json.dump([{**r, "pairs": r["pairs"]} for r in res
                       if r["pairs"]], f, separators=(",", ":"))
        print(f"\n  dump -> {a.dump}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    # R4.  The engine, with `choices=` -- a typo must not silently become a
    # different measurement, which is the trap this tool WAS.
    ap.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"),
                    help="replay engine, exactly as timed_fuzz --core: the C++ "
                         "timed model (sim, the default and every historical "
                         "run of this tool) or an RTL core in the Verilator TB "
                         "(ucore / fsm).  MATCH IT TO THE REPORT's core.")
    ap.add_argument("--rig-hold", default="banked",
                    choices=("banked", "reg8", "applied"),
                    help="RTL legs only: the pin hold handed to the predicting "
                         "engine (timed_fuzz.rig_hold).  The model leg is a "
                         "REPLAY and ignores it.")
    ap.add_argument("--pop", default="all", choices=("all", "reg", "evt"))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--dump", default="")
    ap.add_argument("--seeds", type=int, default=0)
    ap.add_argument("--show", default="")
    ap.add_argument("--rmw", action="store_true",
                    help="the CHIP-ONLY read-modify-write census over every "
                         "banked seed (LC3 / C6 / C7's own population)")
    ap.add_argument("--seeddir", default="")
    a = ap.parse_args()
    if a.rmw:
        return cmd_rmw(a)

    res = json.load(open(a.report))
    div = [r for r in res if r["cat"] == "DIVERGE"]
    if a.pop != "all":
        want = "EVT" if a.pop == "evt" else "REG"
        div = [r for r in div if r.get("pop") == want]
    if a.seeds:
        div = div[:a.seeds]
    for r in div:                    # the engine travels with the work item
        r["_core"] = a.core
        r["_rig_hold"] = a.rig_hold
    print(f"== s15_census -- {len(div)} non-exact seeds (pop={a.pop}, "
          f"engine={a.core}"
          f"{'' if a.core == 'sim' else f', rig-hold={a.rig_hold}'})",
          flush=True)
    with Pool(a.jobs) as pool:
        rows = pool.map(one, div, chunksize=4)
    report(rows, a.show)
    if a.dump:
        with gzip.open(a.dump, "wt") as f:
            json.dump(rows, f, separators=(",", ":"))
        print(f"\n  dump -> {a.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
