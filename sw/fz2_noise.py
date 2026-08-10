#!/usr/bin/env python3
"""THE SOCKET-CAPTURE NOISE FLOOR, measured from banked data.

FLASH #15 §5.2 registered an open falsifier: *"a non-reproducing socket capture
has never been characterised in this corpus.  Capture the whole 3,840 twice on
one bitstream and count the seeds whose socket leg does not reproduce."*  FLASH
#16 §7 partially answered it -- four seeds of 3,840 moved between two flashes
with the core provably uninvolved -- and left it OPEN.

**It is already answered in the bank.**  `fz2c/fz2e-INV2-archive`,
`-A5-archive` and `-F12-archive` are THREE COMPLETE PASSES over the same 3,840
seeds on ONE bitstream (`.sof 8db6dadf5c4c…`, `flash_git b629296e3a`), taken
2026-08-09 at 05:42, 14:26 and 16:32.  That is the registered experiment, run
three times instead of two, and nobody scored it.

This tool scores it.  It compares only the SOCKET leg, only between passes whose
stimulus is byte-identical for that seed (`image_sha256`, tier, wait source and
directive, event directive, terminator directive), and it reports the CORE leg
beside it as the control that says whether a move is the chip or the rig.

Nothing here re-captures, nothing here substitutes a probe for a banked row, and
no seed is excluded for moving.

  python3 sw/fz2_noise.py triple      # the three same-bitstream passes
  python3 sw/fz2_noise.py rows        # row-exact, on the banked captures
  python3 sw/fz2_noise.py ledger      # the flip rate in the ledger's own units
  python3 sw/fz2_noise.py eras        # every archived era pair, reported
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMP = ROOT / "sw/testdata/campaigns"

# every archived pass of the fz2 corpus, oldest first.  The suffix is the
# campaign-dir suffix; `""` is the live dir.
ERAS = ["-INV2-archive", "-A5-archive", "-F12-archive", "-F13-archive",
        "-F14-archive", "-F15-archive", ""]
ERA_LABEL = {"-INV2-archive": "INV2", "-A5-archive": "A5",
             "-F12-archive": "F12", "-F13-archive": "F13",
             "-F14-archive": "F14", "-F15-archive": "F15", "": "F16"}
CIDS = ["fz2c", "fz2e"]

# The stimulus a socket capture is a function of.  If any of these differ the
# two rows are not a repeat and the pair is NOT SCORED -- that is the whole
# discipline of this measurement.
STIM = ["image_sha256", "tier", "cfg_hash", "nmin", "nmax_eff", "raw_mode",
        "ivt_mode", "no8080", "wvec_sha256", "wvec_n"]

# What the SOCKET leg produced.  Every one of these is measured on the chip's
# own pins or its own architectural dump; none of them is a comparison against
# the core, because a comparison would fold the core's behaviour back in.
CHIP = ["arch_words", "arch_ok", "bus_cycles", "escaped_n", "ps3_8080",
        "wrote_term", "wrote_term_at", "stalled", "mech"]
CORE = ["arch_sim_words", "arch_sim_ok", "ps3_8080_core"]


def load(era):
    """{seed: row} over both campaign ids for one pass."""
    out = {}
    for cid in CIDS:
        p = CAMP / f"{cid}{era}" / "results.jsonl"
        if not p.exists():
            continue
        for line in p.open():
            r = json.loads(line)
            out[r["seed"]] = r
    return out


def stim_key(r):
    w = r.get("waits") or {}
    e = r.get("evt") or {}
    t = r.get("term") or {}
    return json.dumps([[r.get(k) for k in STIM],
                       [w.get(k) for k in ("wrand", "wmax", "wseed", "fixed")],
                       [e.get(k) for k in ("kind", "delay", "hold", "applied",
                                           "pin")],
                       [t.get(k) for k in ("tvec", "term_clocks", "term_hold",
                                           "vecsub")]], sort_keys=True)


CHIP_SUB = [("stalled_at", ("f", "last", "last_bs", "idle", "after")),
            ("long_insn_at", ("f", "after", "code_after", "qs_nz")),
            ("term", ("fired", "vec_used", "vec_rows"))]
CORE_SUB = [("stalled_at", ("core_last", "core_after", "core_stalled")),
            ("long_insn_at", ("core_after", "core_code", "core_qs_nz"))]


def fields(r, top, sub):
    """{field_name: value} -- flat, so a field the two passes' SCHEMAS do not
    share can be dropped rather than counted as a move.  The `A5` pass predates
    `mech` / `stalled` / `stalled_at`; a field the older tool never wrote is a
    tool difference, not a chip difference, and scoring it as one would invent
    the very number this file exists to measure."""
    out = {k: r.get(k) for k in top}
    for grp, keys in sub:
        g = r.get(grp) or {}
        for k in keys:
            out[f"{grp}.{k}"] = g.get(k)
    return out


def chip_fields(r):
    return fields(r, CHIP, CHIP_SUB)


def core_fields(r):
    return fields(r, CORE, CORE_SUB)


def shared_schema(P, fn):
    """Fields that at least one seed of EVERY pass writes non-null."""
    live = None
    for rows in P.values():
        here = set()
        for r in rows.values():
            for k, v in fn(r).items():
                if v is not None:
                    here.add(k)
        live = here if live is None else (live & here)
    return sorted(live or [])


def classify(r):
    """The coarse class a moving seed falls in, for the concentration table."""
    if r.get("escaped_n"):
        return "escaped"
    if r.get("ps3_8080"):
        return "runtime-8080"
    t = r.get("term") or {}
    if not t.get("fired"):
        return "terminator-misfire"
    if r.get("stalled"):
        return "stalled"
    return "plain"


# --------------------------------------------------------------------------- #
def pair_report(a_era, b_era, A, B):
    """One ordered pass pair, scored on the seeds whose stimulus is identical
    and over the fields both passes' tools actually wrote."""
    seeds = sorted(set(A) & set(B))
    P = {a_era: A, b_era: B}
    ck = shared_schema(P, chip_fields)
    kk = shared_schema(P, core_fields)
    same_stim, chip_move, core_move, both = [], [], [], []
    why = Counter()
    for s in seeds:
        if stim_key(A[s]) != stim_key(B[s]):
            continue
        same_stim.append(s)
        fa, fb = chip_fields(A[s]), chip_fields(B[s])
        d = [k for k in ck if fa[k] != fb[k]]
        ga, gb = core_fields(A[s]), core_fields(B[s])
        e = [k for k in kk if ga[k] != gb[k]]
        if d:
            chip_move.append(s)
            for k in d:
                why[k] += 1
        if e:
            core_move.append(s)
        if d and e:
            both.append(s)
    return {"a": ERA_LABEL[a_era], "b": ERA_LABEL[b_era],
            "seeds_common": len(seeds), "scored": len(same_stim),
            "stim_differs": len(seeds) - len(same_stim),
            "chip_fields": ck, "core_fields": kk,
            "chip_move_fields": dict(why),
            "chip_moved": chip_move, "core_moved": core_move,
            "both_moved": both}


def cmd_triple(a):
    """The three passes on ONE bitstream -- the registered experiment."""
    eras = ["-INV2-archive", "-A5-archive", "-F12-archive"]
    P = {e: load(e) for e in eras}
    sof = {e: next(iter(P[e].values()))["era"]["sof_sha256"] for e in eras}
    assert len({v for v in sof.values()}) == 1, sof
    print(f"THE SAME-BITSTREAM TRIPLE  .sof {list(sof.values())[0][:12]}…")
    for e in eras:
        ts = sorted(r["ts"] for r in P[e].values())
        print(f"  {ERA_LABEL[e]:<5} {len(P[e]):>5} seeds   "
              f"{ts[0]} .. {ts[-1]}   gen_git "
              f"{next(iter(P[e].values()))['gen_git']}")
    pairs = [(eras[0], eras[1]), (eras[1], eras[2]), (eras[0], eras[2])]
    reps = [pair_report(x, y, P[x], P[y]) for x, y in pairs]
    print()
    hdr = (f"{'pair':<12}{'common':>8}{'scored':>8}{'stim≠':>7}"
           f"{'CHIP moved':>12}{'CORE moved':>12}{'both':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in reps:
        print(f"{r['a']+'→'+r['b']:<12}{r['seeds_common']:>8}{r['scored']:>8}"
              f"{r['stim_differs']:>7}{len(r['chip_moved']):>12}"
              f"{len(r['core_moved']):>12}{len(r['both_moved']):>7}")

    # the union over the three ordered pairs, and its concentration
    union = sorted({s for r in reps for s in r["chip_moved"]})
    core_union = sorted({s for r in reps for s in r["core_moved"]})
    chip_only = [s for s in union if s not in set(core_union)]
    print(f"\n  union of CHIP-moving seeds over the three pairs: {len(union)}")
    print(f"  union of CORE-moving seeds                      : "
          f"{len(core_union)}")
    print(f"  CHIP moved and CORE did NOT                     : "
          f"{len(chip_only)}")
    ref = eras[1]                     # A5 -- the base of the scored repeat
    cls = Counter(classify(P[ref][s]) for s in chip_only)
    print(f"  concentration of the chip-only movers (class at A5)  : "
          f"{dict(cls)}")
    base = Counter(classify(r) for r in P[ref].values())
    print(f"  the same classes over the whole 3,840                : "
          f"{dict(base)}")
    for r in reps:
        if r["scored"]:
            print(f"  fields that moved on {r['a']}→{r['b']}: "
                  f"{r['chip_move_fields']}")
    det = []
    for s in chip_only:
        row = {"seed": s, "class_INV2": classify(P[eras[0]][s])}
        for e in eras:
            r = P[e][s]
            t = r.get("term") or {}
            row[ERA_LABEL[e]] = {
                "verdict": r["verdict"], "sub": r["sub"],
                "bad_rows": r["bad_rows"], "first_bad": r["first_bad"],
                "bus_cycles": r["bus_cycles"], "escaped_n": r["escaped_n"],
                "ps3_8080": r["ps3_8080"], "fired": t.get("fired"),
                "vec_used": t.get("vec_used"),
                "arch_words": r["arch_words"],
                "arch_sim_words": r["arch_sim_words"]}
        det.append(row)
    out = {"tool": "fz2_noise.triple", "sof": list(sof.values())[0],
           "passes": [ERA_LABEL[e] for e in eras], "pairs": reps,
           "chip_moved_union": union, "core_moved_union": core_union,
           "chip_only": chip_only, "detail": det,
           "class_counts_chip_only": dict(cls),
           "class_counts_population": dict(base)}
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"\n  -> {Path(a.out).name}")
    for r in det:
        print(f"\n  {r['seed']}  ({r['class_INV2']})")
        for e in ("INV2", "A5", "F12"):
            v = r[e]
            print(f"    {e:<5} {v['verdict']:<16}{str(v['sub'])[:14]:<15}"
                  f"bad {v['bad_rows']:<6} bus {v['bus_cycles']:<6}"
                  f"esc {v['escaped_n']:<4} 8080 {int(bool(v['ps3_8080']))} "
                  f"fired {v['fired']}  archOK "
                  f"{int(v['arch_words'] is not None)}")


def cmd_rows(a):
    """SOCKET-vs-SOCKET, row for row, on every seed banked in both passes of
    the same-bitstream repeat.  The comparator is the CORPUS'S OWN --
    `fuzz_classify.diff_rows`, the same column policy and the same flicker
    tolerance that produce `bad_rows` -- pointed at chip-A vs chip-B instead of
    chip vs core.  A row this instrument scores is a row that would have moved
    the ledger; a row it does not score is one the campaign never reads."""
    import sys
    sys.path.insert(0, str(ROOT / "sw"))
    import fuzz_classify as fc                                   # noqa: E402
    A_ERA, B_ERA = "-A5-archive", "-F12-archive"
    P = {e: load(e) for e in (A_ERA, B_ERA)}
    idx = {}
    for e in (A_ERA, B_ERA):
        for cid in CIDS:
            d = CAMP / f"{cid}{e}" / "captures"
            if not d.exists():
                continue
            for p in d.glob("*.json.gz"):
                parts = p.name.split("_")
                if len(parts) > 1:
                    idx.setdefault(f"{cid}/{parts[1]}", {})[e] = p
    both = {s: v for s, v in idx.items() if len(v) == 2}
    print(f"the same-bitstream repeat {ERA_LABEL[A_ERA]} -> {ERA_LABEL[B_ERA]}")
    print(f"seeds with a banked capture in BOTH passes: {len(both)}")
    clean, moved, skipped, det = 0, 0, 0, []
    for s, v in sorted(both.items()):
        ra_, rb_ = P[A_ERA].get(s), P[B_ERA].get(s)
        if ra_ is None or rb_ is None or stim_key(ra_) != stim_key(rb_):
            skipped += 1
            continue
        A = json.loads(gzip.decompress(v[A_ERA].read_bytes()))
        B = json.loads(gzip.decompress(v[B_ERA].read_bytes()))
        win = ra_.get("win") or 4000
        d = fc.diff_rows(A["real"], B["real"], window=win)
        e = fc.diff_rows(A["sim"], B["sim"], window=win)
        if d.bad == 0 and e.bad == 0:
            clean += 1
        else:
            moved += 1
            det.append({"seed": s, "window": d.n,
                        "chip_bad": d.bad, "chip_flick": d.flick,
                        "chip_first": d.first,
                        "core_bad": e.bad, "core_first": e.first,
                        "bad_rows_A": ra_["bad_rows"],
                        "bad_rows_B": rb_["bad_rows"]})
    print(f"  chip AND core streams reproduce EXACTLY : {clean}")
    print(f"  something moved                         : {moved}")
    print(f"  pairs not scored (stimulus differed)    : {skipped}")
    for x in det:
        print(f"    {x['seed']:<14} chip bad {x['chip_bad']:<6} "
              f"first {str(x['chip_first']):<7} core bad {x['core_bad']:<6} "
              f"first {str(x['core_first']):<7} "
              f"ledger bad_rows {x['bad_rows_A']} -> {x['bad_rows_B']}")
    chip_only = [x for x in det if x["chip_bad"] and not x["core_bad"]]
    core_only = [x for x in det if x["core_bad"] and not x["chip_bad"]]
    print(f"\n  CHIP moved, CORE did not : {len(chip_only)}")
    print(f"  CORE moved, CHIP did not : {len(core_only)}")
    print(f"  both moved               : "
          f"{len(det) - len(chip_only) - len(core_only)}")
    json.dump({"tool": "fz2_noise.rows", "pair": [ERA_LABEL[A_ERA],
                                                  ERA_LABEL[B_ERA]],
               "seeds_with_both_captures": len(both), "scored":
                   len(both) - skipped, "clean": clean, "moved": det,
               "skipped": skipped, "chip_only": [x["seed"] for x in chip_only],
               "core_only": [x["seed"] for x in core_only]},
              open(a.out, "w"), indent=1)
    print(f"  -> {Path(a.out).name}")


def cmd_ledger(a):
    """The measurement in the units the campaign's headline is quoted in.

    `sw/fz2_ledger.py::derive` is the whole predicate: a seed is a DISCARD iff
    `ps3_8080`, otherwise a FAILURE iff `bad_rows != 0`.  Both are read off the
    banked row, so the flip rate is computable exactly -- no re-capture, no
    model, no judgement."""
    A_ERA, B_ERA = "-A5-archive", "-F12-archive"
    A, B = load(A_ERA), load(B_ERA)

    def cls(r):
        if r.get("ps3_8080"):
            return "DISCARD"
        return "MATCHED" if r["bad_rows"] == 0 else "FAILURE"

    scored, moves = 0, defaultdict(list)
    for s in sorted(set(A) & set(B)):
        if stim_key(A[s]) != stim_key(B[s]):
            continue
        scored += 1
        ca, cb = cls(A[s]), cls(B[s])
        if ca != cb:
            moves[f"{ca}->{cb}"].append(s)
    tot = sum(len(v) for v in moves.values())
    print(f"THE LEDGER-LEVEL FLIP RATE, same bitstream, same stimulus, "
          f"{ERA_LABEL[A_ERA]} -> {ERA_LABEL[B_ERA]}")
    print(f"  seeds scored : {scored}")
    for k in sorted(moves):
        print(f"  {k:<22}{len(moves[k]):>5}   {', '.join(moves[k])}")
    print(f"  TOTAL FLIPS  : {tot} / {scored} = "
          f"{100.0 * tot / max(scored, 1):.4f} %")
    ca = Counter(cls(A[s]) for s in A)
    cb = Counter(cls(B[s]) for s in B)
    print(f"  {ERA_LABEL[A_ERA]}: {dict(ca)}")
    print(f"  {ERA_LABEL[B_ERA]}: {dict(cb)}")

    # ---- CONCENTRATION.  Measured, with its denominator, not asserted.
    flip = [s for v in moves.values() for s in v]
    fired = [s for s in sorted(set(A) & set(B))
             if stim_key(A[s]) == stim_key(B[s])
             and (A[s].get("term") or {}).get("fired")
             != (B[s].get("term") or {}).get("fired")]
    esc = [s for s in flip if A[s]["escaped_n"]]
    pop_esc = [s for s in A if A[s]["escaped_n"]]
    nmi = []
    for s in flip:
        ra = (A[s]["term"]["hold_rows"] or {}).get("pin_nmi")
        rb = (B[s]["term"]["hold_rows"] or {}).get("pin_nmi")
        if ra != rb:
            nmi.append(s)
    print(f"\n  CONCENTRATION")
    print(f"    seeds whose terminator `fired` count moved : {len(fired)}"
          f" / {scored}")
    print(f"    ... of the {tot} ledger flips, `fired` moved on : "
          f"{sum(1 for s in flip if s in set(fired))}")
    print(f"    ... and the terminating NMI's OWN pin row moved on: "
          f"{len(nmi)}  {nmi}")
    print(f"    flips that were ESCAPED at {ERA_LABEL[A_ERA]}      : "
          f"{len(esc)} / {tot}   (population {len(pop_esc)} / {len(A)})")
    if pop_esc and len(A) - len(pop_esc):
        print(f"    flip rate among escaped   : "
              f"{len(esc)}/{len(pop_esc)} = "
              f"{100.0 * len(esc) / len(pop_esc):.3f} %")
        print(f"    flip rate among the rest  : "
              f"{tot - len(esc)}/{len(A) - len(pop_esc)} = "
              f"{100.0 * (tot - len(esc)) / (len(A) - len(pop_esc)):.3f} %")
    json.dump({"tool": "fz2_noise.ledger", "pair": [ERA_LABEL[A_ERA],
                                                    ERA_LABEL[B_ERA]],
               "scored": scored, "moves": {k: v for k, v in moves.items()},
               "total": tot, "class_counts": {ERA_LABEL[A_ERA]: dict(ca),
                                              ERA_LABEL[B_ERA]: dict(cb)},
               "fired_moved": fired, "flip_nmi_row_moved": nmi,
               "flip_escaped": esc, "population_escaped": len(pop_esc)},
              open(a.out, "w"), indent=1)
    print(f"  -> {Path(a.out).name}")


def cmd_eras(a):
    """Every consecutive archived pass, reported with its bitstream, so a
    reader can see which pairs are same-bitstream repeats and which are not."""
    P = {e: load(e) for e in ERAS}
    print(f"{'pass':<6}{'seeds':>7}  {'.sof':<14}{'flash_git':<18}"
          f"{'gen_git':<12}first ts")
    for e in ERAS:
        r = next(iter(P[e].values()))
        ts = min(x["ts"] for x in P[e].values())
        print(f"{ERA_LABEL[e]:<6}{len(P[e]):>7}  "
              f"{r['era']['sof_sha256'][:12]:<14}"
              f"{str(r['era'].get('flash_git'))[:16]:<18}{r['gen_git']:<12}{ts}")
    print()
    hdr = (f"{'pair':<12}{'same .sof':<11}{'scored':>8}{'stim≠':>7}"
           f"{'CHIP moved':>12}{'CORE moved':>12}{'chip-only':>11}")
    print(hdr)
    print("-" * len(hdr))
    out = []
    for x, y in zip(ERAS, ERAS[1:]):
        r = pair_report(x, y, P[x], P[y])
        sx = next(iter(P[x].values()))["era"]["sof_sha256"]
        sy = next(iter(P[y].values()))["era"]["sof_sha256"]
        co = [s for s in r["chip_moved"] if s not in set(r["core_moved"])]
        r["same_sof"] = (sx == sy)
        r["chip_only"] = co
        out.append(r)
        print(f"{r['a']+'→'+r['b']:<12}{str(r['same_sof']):<11}"
              f"{r['scored']:>8}{r['stim_differs']:>7}"
              f"{len(r['chip_moved']):>12}{len(r['core_moved']):>12}"
              f"{len(co):>11}")
    json.dump({"tool": "fz2_noise.eras", "pairs": out},
              open(a.out, "w"), indent=1)
    print(f"\n  -> {Path(a.out).name}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = ROOT / "sw/testdata/fz2"
    for name, fn in (("triple", cmd_triple), ("rows", cmd_rows),
                     ("ledger", cmd_ledger), ("eras", cmd_eras)):
        s = sub.add_parser(name)
        s.add_argument("--out", default=str(d / f"fz2_noise_{name}.json"))
        s.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
