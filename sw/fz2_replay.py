#!/usr/bin/env python3
"""fz2_replay -- THE FAITHFUL OFFLINE REPLAY OF AN fz2 SEED, ON `tb_sys`.

THE GAP THIS CLOSES (F14 survey, instrument finding #1)
-------------------------------------------------------
Three offline rescorers exist -- `fz2_a1_rescore`, `fz2_c1_rescore`,
`b1_rescore` -- and all three drive `tb_v30_core`, which has **ONE** pin-event
scheduler and no NMI vector-read overlay.  Every fz2 capture is taken with
**TWO** directives live: the seed's own stimulus event on scheduler 0 and the
TERMINATING NMI on scheduler 2, the latter with `vecsub_en` set so the rig
substitutes the vector data at linear 0x00008/0x0000A out of its `TVEC`
register.  A one-scheduler harness must therefore choose, and each of the three
chose differently:

  * `fz2_a1_rescore` / `b1_rescore` spend the scheduler on the STIMULUS and cut
    the window at the terminating NMI's entry -- so nothing past that entry is
    scored at all;
  * `fz2_c1_rescore` spends it on the TERMINATOR and emulates `TVEC` by
    patching IVT entry 2 in the image -- so a seed with a stimulus event never
    gets it (that file's own limitation (b)).

MEASURED COST, from `fz2_f14_results_2026-08-10.md` §5.4: the `C1` landing
closed **19** seeds in fabric where `fz2_c1_rescore` could only show **12**.

`tb_sys` -- the Verilated `system_large`, image and directives driven through
the AXI bridge exactly as the ARM drives them -- has **THREE** schedulers,
`TVEC` and `VECCTL`, and it is the harness the standing rule already prefers:
where the two TBs disagree, fabric sides with `tb_sys`, 1,654 of 1,654 cells.
This file hands it `fuzz_campaign.term_directive`'s OWN output -- the same
tuple list, the same `TVEC`, the same `VECCTL` mask that `capture_board` hands
the rig -- and scores the result against the banked SOCKET rows with
`fuzz_classify.diff_rows`, the corpus's own column policy, over the corpus's
own window.

⚠ THE SURVEY'S ~20-LINE ESTIMATE WAS WRONG, AND THE ARTIFACT WINS
------------------------------------------------------------------
`fz2_tbsys.run_tb()` accepted `evts`/`tvec`/`vecctl` as the survey said -- but
it accepted **`waits` and nothing else** for the wait source, because `tb_sys`
itself had only `CFG.wait_states`.  The fz2 corpus is a RANDOM-WAIT campaign:
of the 145 seeds in the A-15 failure ledger, **73 run at a fixed wait level, 56
draw each access's Tw from the harness's seeded LFSR, and 16 replay an explicit
wait vector**.  Half the ledger could not have been replayed on `tb_sys` at
all, and -- worse -- would have run silently at `waits=0` and reported garbage
divergence.

So `hdl/tb/tb_sys.sv` gained `+wrand/+wmax/+wseed/+wvec`, which write the
board's OWN `WRAND` register (0x24) and the board's OWN 4 KiB wait-vector RAM
(+0x140000) through the same bridge.  They are not a model of the wait source;
they are the wait source.  They are written ONLY when named, so `fz2_tbsys.py
inert` still passes byte-for-byte (it does: both reference runs, 4,000 records,
BYTE-IDENTICAL across the change) and all four T6 legs still pass 61/61.

WHAT IS SCORED, AND AGAINST WHAT
--------------------------------
For each seed:

  1. the image is re-derived through `fuzz_campaign.compose_case` -- the one
     place a fuzz case's image is built -- and it must hash to the banked
     `image_sha256`, else `GEN_DRIFT`;
  2. `fuzz_campaign.term_directive(cfg, meta)` produces the directive -- NOT
     re-derived here, so a change to the terminator's budget moves the board
     and this file together or neither;
  2b. and the directive is then CHECKED AGAINST THE BANKED ONE, field for
     field.  A capture is only readable against the directive it was taken
     under (INV-1), and this is where that is enforced rather than assumed;
  3. `tb_sys` runs it with the seed's own wait source;
  4. leading RESET records are dropped exactly as `check_seq.run_chip` drops
     them (`first row with rst == 0`), which is what makes a `tb_sys` row index
     mean the same thing a banked row index means;
  5. `fuzz_classify.diff_rows(banked_socket_rows, replayed_rows, window=win)`
     with `win` the seed's own banked compare window; `bad` counts NON-FLICKER
     rows, which is the corpus's own definition of `bad_rows`.

THE REFERENCE IS FABRIC, NOT A MODEL.  A seed's fabric verdict is `bad_rows !=
0` on the board's OWN A/B pair (socketed chip vs fabric core), i.e. exactly
"is this seed in the failure ledger".  The replay's verdict is the same
predicate computed offline against the same socket rows.  Agreement between
them is a statement about the INSTRUMENT.

THE FABRIC ERA GUARD
--------------------
An offline replay may only be compared with a fabric verdict if the RTL is the
same RTL.  The banked corpus's `era` block names the `.sof` and the artifact
receipt whose OUTPUT that `.sof` is; this file re-hashes every DECLARED INPUT
of that receipt against the tree and REFUSES when an `hdl/rtl/` file has moved.
`hdl/nec_test_ucore.qsf` is exempt and the exemption is NAMED: Quartus
materialises its sourced assignments into that file during a build (§70.7), it
carries no RTL, and `gen_ucore_qsf --check` is the gate that owns it.

`--no-fabric-era-guard` exists and has exactly one honest use: deliberately
reading a cross-era column, knowing that is what you are doing.

⚠ A DEFECT IN `ucsim_fuzz.regen`, FOUND BY THIS FILE AND NOT REPAIRED HERE
--------------------------------------------------------------------------
`fuzz_campaign.build(cfg)` MUTATES ITS ARGUMENT: when the generated program
contains a HALT it rewrites `cfg["evt"]["hold"] = 300` (a HALTed CPU needs the
pin held long enough to be seen), and it appends `hold_bits`/`hold_applied`.
`regen()` builds on a LOCAL cfg and returns `(image, meta, g, sha)` -- the
mutated cfg is dropped on the floor.  So a caller that does

    image, meta, g, sha = uf.regen(entry)
    cfg = fzc.derive_case(...)          # <-- hold is 2, not 300
    evts, ... = fzc.term_directive(cfg, meta)

arms a 2-clock pin where the capture was taken with a 300-clock one.  679 of
the corpus's 1,920 event seeds are hold=300, and the failure is SILENT: the
scheduler still fires, `STATUS[3]` still sets, and the run merely does not take
the interrupt.  This file therefore derives, builds and composes IN LINE -- the
same three calls in the same order `regen` makes -- and keeps the cfg `build`
mutated.  `regen` is left alone because it is on other tools' paths and its own
contract (image + sha) is met; the falsifier is the directive cross-check in
`one()` below, which would catch it again from the other side.
"""
import argparse
import collections
import glob
import gzip
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import artifact as art                                        # noqa: E402
import check_seq                                              # noqa: E402
import fuzz_campaign as fzc                                   # noqa: E402
import fuzz_classify as fc                                    # noqa: E402
import fz2_ledger as fzl                                      # noqa: E402
import fz2_tbsys as tbs                                       # noqa: E402
import fz2_w1 as fz                                           # noqa: E402
import v30ctl                                                 # noqa: E402
import x1_retention as x1                                     # noqa: E402

CIDS = ("fz2c", "fz2e")
NCAP = v30ctl.CAP_RECORDS          # 4,096 -- the rig's own capture depth
DIV = 8                            # v30run.DIV_OF_RECORD, the pinned divider

# The one file `era_of` names that is NOT RTL.  See the module docstring.
ERA_EXEMPT = {"hdl/nec_test_ucore.qsf"}

OUT = Path.home() / ".cache" / "ucsimt-tmp" / "fz2-replay"


# --------------------------------------------------------------------------- #
# the corpus
# --------------------------------------------------------------------------- #
_LINES = {}


def lines():
    if not _LINES:
        for cid in CIDS:
            with open(ROOT / "sw/testdata/campaigns" / cid / "results.jsonl") as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        r = json.loads(ln)
                        _LINES[r["seed"]] = r
    return _LINES


def retained():
    """{seed: capture path} for every seed whose SOCKET rows were banked."""
    out = {}
    for cid in CIDS:
        d = ROOT / "sw/testdata/campaigns" / cid / "captures"
        for p in sorted(glob.glob(str(d / "*.json.gz"))):
            k = int(os.path.basename(p).split("_")[1])
            out[f"{cid}/{k}"] = p
    return out


def ov_for(cid, k):
    for st in fz.STRATA:
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return fz.ov_of(st)
    raise KeyError((cid, k))


def wait_mode(cfg):
    if cfg.get("wvec"):
        return "wvec"
    return "wrand" if cfg["waits"]["wrand"] else "fixed"


# --------------------------------------------------------------------------- #
# THE FABRIC ERA GUARD
# --------------------------------------------------------------------------- #
def fabric_era(led):
    """-> (ok, report).  Re-hash the bitstream receipt's declared inputs."""
    era = led.get("era") or {}
    rid = (era.get("rtl") or {}).get("receipt_id")
    rp = ROOT / "sw/testdata/receipts/quartus_bitstream.jsonl"
    rec = None
    if rid and rp.exists():
        for ln in rp.read_text().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:                                 # noqa: BLE001
                continue
            if r.get("id") == rid:
                rec = r
    if rec is None:
        return False, [f"no bitstream receipt {str(rid)[:16]}… in "
                       f"{rp.relative_to(ROOT)}"]
    bad, n = [], 0
    for f, h in sorted((rec.get("inputs") or {}).get("files", {}).items()):
        n += 1
        now = art.sha256_file(ROOT / f)
        if now != h:
            bad.append(f)
    hard = [f for f in bad if f not in ERA_EXEMPT]
    rep = [f"bitstream   {era.get('sof_sha256', '?')[:16]}…  "
           f"flashed {era.get('flash_ts')}  git {era.get('flash_git')}",
           f"receipt     {rid[:16]}…  {rec.get('label')}",
           f"its inputs  {n - len(bad)}/{n} hash IDENTICAL in the tree at HEAD"]
    for f in bad:
        rep.append(f"  MOVED     {f}"
                   + ("   [EXEMPT: Quartus rewrites it in place, §70.7; "
                      "carries no RTL]" if f in ERA_EXEMPT else "   <-- RTL"))
    return not hard, rep


# --------------------------------------------------------------------------- #
# THE THREE COMPARATORS
# --------------------------------------------------------------------------- #
def _drop_reset(recs):
    """`check_seq.run_chip`'s own rule, so a row index means one thing."""
    for i, r in enumerate(recs):
        if not r["rst"]:
            return recs[i:]
    return recs


def replay_sys(image, meta, cfg, leg, tag, perturb=0):
    """THE NEW INSTRUMENT.  Both directives, the overlay, the real wait source.

    `perturb` is the NON-VACUITY CONTROL's only knob, and it acts on WHICHEVER
    wait source the seed actually uses -- CFG.wait_states for a fixed seed, the
    LFSR seed for a random one, a rotation of the vector for a replay one.  A
    control that bumped `+waits` on all three would be INERT on two thirds of
    the corpus, because `nec_bus`'s priority is replay > rand > uniform and the
    uniform level is not consulted at all in the other two modes.  The program,
    both directives and the overlay are untouched, so a seed that scored clean
    and still scores clean under a DIFFERENT wait pattern is a comparator that
    is not looking at anything."""
    evts, tvec, vecsub = fzc.term_directive(cfg, meta)
    w = cfg["waits"]
    cs, ip = tvec
    waits = 0 if w["wrand"] else w["fixed"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    wvec = fzc.wvec_of(cfg)
    if perturb:
        if wvec is not None:
            wvec = list(wvec[perturb:]) + list(wvec[:perturb])
        elif wrand is not None:
            wrand = (wrand[0], (wrand[1] ^ perturb) & 0xFFFF)
        else:
            waits += perturb
    cap = OUT / f"{tag}.hex"
    r = tbs.run_tb(leg, image, cap, ncap=NCAP, waits=waits, div=DIV,
                   evts={i: t for i, t in enumerate(evts) if t},
                   tvec=(cs << 16) | ip, vecctl=vecsub,
                   wrand=wrand, wvec=wvec, quiet=True)
    try:
        cap.unlink()
    except OSError:
        pass
    return _drop_reset(tbs.decode(r["words"])), r


def replay_core_stim(image, meta, cfg):
    """`b1_rescore` / `fz2_a1_rescore`'s comparator: tb_v30_core, the seed's
    STIMULUS on its single scheduler, no terminator at all."""
    return fzc.capture_tb(image, meta, cfg, core="ucore")


def replay_core_term(image, meta, cfg):
    """`fz2_c1_rescore`'s comparator: tb_v30_core, the TERMINATOR on the single
    scheduler, `TVEC` emulated by patching IVT entry 2 -- and therefore no
    stimulus event for any seed that has one."""
    import fz2_c1_rescore as c1
    evts, _tv, _vs = fzc.term_directive(cfg, meta)
    w = cfg["waits"]
    return check_seq.run_tb(
        c1.patch_ivt2(image), 4200,
        waits=0 if w["wrand"] else w["fixed"],
        evt=evts[fzc.TERM_SCHED],
        wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
        wvec=fzc.wvec_of(cfg), core="ucore")


def score(chip, rows, win):
    dr = fc.diff_rows(chip, rows, window=win)
    bad = [r for r in dr.rows if not r.flicker]
    return {"n": dr.n, "nrows": len(rows), "bad": len(bad),
            "flick": len(dr.rows) - len(bad),
            "first": bad[0].i if bad else None}


# --------------------------------------------------------------------------- #
_OPT = {}


def _init(opt):
    _OPT.update(opt)


def regen_case(cid, k):
    """`ucsim_fuzz.regen`'s three calls, in its order, KEEPING THE CFG.

    -> (cfg, image, meta, sha).  See the module docstring: `build()` mutates
    `cfg["evt"]["hold"]` and `regen()` throws that cfg away."""
    cfg = fzc.derive_case(cid, k, ov_for(cid, k))
    g = fzc.build(cfg)
    image, meta = fzc.compose_case(g, cfg)
    return cfg, image, meta, hashlib.sha256(bytes(image)).hexdigest()


def directive_drift(cfg, line):
    """The banked directive vs the re-derived one, field for field."""
    bad = []
    be, ce = line.get("evt"), cfg.get("evt")
    if bool(be) != bool(ce):
        bad.append(f"evt {'banked only' if be else 're-derived only'}")
    elif be:
        for f in ("pin", "delay", "hold"):
            if be.get(f) != ce.get(f):
                bad.append(f"evt.{f} banked={be.get(f)} derived={ce.get(f)}")
    bw, cw = line.get("waits") or {}, cfg["waits"]
    for f in ("wrand", "wmax", "wseed", "fixed"):
        if bw.get(f) != cw.get(f):
            bad.append(f"waits.{f} banked={bw.get(f)} derived={cw.get(f)}")
    if bool(line.get("wvec")) != bool(cfg.get("wvec")):
        bad.append(f"wvec banked={line.get('wvec')} derived={cfg.get('wvec')}")
    return bad


def one(job):
    seed, cappath = job
    cid, k = seed.split("/")[0], int(seed.split("/")[1])
    line = lines()[seed]
    out = {"seed": seed, "cid": cid, "k": k, "tier": line["tier"],
           "fabric_bad": line["bad_rows"], "fabric_first": line["first_bad"],
           "win": line["win"]}
    try:
        cfg, image, meta, sha = regen_case(cid, k)
        out["wait_mode"] = wait_mode(cfg)
        out["has_evt"] = bool(cfg.get("evt"))
        if sha != line["image_sha256"]:
            out["err"] = f"GEN_DRIFT {sha[:12]} != {line['image_sha256'][:12]}"
            return out
        drift = directive_drift(cfg, line)
        if drift:
            out["err"] = "DIRECTIVE_DRIFT " + "; ".join(drift)
            return out
        with gzip.open(cappath) as fh:
            chip = json.load(fh)["real"]
        win = int(line["win"])
        rows, rr = replay_sys(image, meta, cfg, _OPT["leg"],
                              f"{cid}_{k}_{os.getpid()}")
        out["sys"] = score(chip, rows, win)
        out["sys"]["fired"] = rr["fired"]
        out["sys"]["vecused"] = rr["vecused"]
        if _OPT.get("also_tbcore"):
            out["core_stim"] = score(chip, replay_core_stim(image, meta, cfg),
                                     win)
            out["core_term"] = score(chip, replay_core_term(image, meta, cfg),
                                     win)
        if _OPT.get("perturb"):
            prows, _pr = replay_sys(image, meta, cfg, _OPT["leg"],
                                    f"{cid}_{k}_{os.getpid()}_p",
                                    perturb=_OPT["perturb"])
            out["perturbed"] = score(chip, prows, win)
    except Exception as e:                                    # noqa: BLE001
        out["err"] = f"{type(e).__name__}: {str(e)[:160]}"
    return out


# --------------------------------------------------------------------------- #
# the fidelity table
# --------------------------------------------------------------------------- #
def table(res, key, name):
    """The 2x2 against the FABRIC verdict, plus the first-bad agreement."""
    cells = collections.Counter()
    dis = {"fabric_pass_replay_fail": [], "fabric_fail_replay_pass": []}
    fb_same = fb_tot = 0
    for r in res:
        if r.get("err") or key not in r:
            continue
        ff = r["fabric_bad"] != 0
        rf = r[key]["bad"] != 0
        cells[(ff, rf)] += 1
        if ff and not rf:
            dis["fabric_fail_replay_pass"].append(r["seed"])
        elif rf and not ff:
            dis["fabric_pass_replay_fail"].append(
                f"{r['seed']}@{r[key]['first']}")
        if ff and rf:
            fb_tot += 1
            fb_same += (r[key]["first"] == r["fabric_first"])
    n = sum(cells.values())
    agree = cells[(True, True)] + cells[(False, False)]
    print(f"\n  --- {name} ---")
    print(f"    {'':22s} {'replay PASS':>12s} {'replay FAIL':>12s}")
    print(f"    {'fabric PASS':22s} {cells[(False, False)]:>12d} "
          f"{cells[(False, True)]:>12d}")
    print(f"    {'fabric FAIL':22s} {cells[(True, False)]:>12d} "
          f"{cells[(True, True)]:>12d}")
    print(f"    AGREEMENT {agree} / {n}"
          + (f" = {100.0 * agree / n:.1f} %" if n else ""))
    print(f"    of the {fb_tot} both-FAIL seeds, first_bad IDENTICAL on "
          f"{fb_same}")
    return {"name": name, "n": n, "agree": agree,
            "cells": {f"{a}_{b}": c for (a, b), c in cells.items()},
            "first_bad_same": fb_same, "first_bad_both_fail": fb_tot,
            "disagreements": dis}


def breakdown(res, key, axis, metric):
    """agreement counts per value of `axis(row)`.

    `metric` is "verdict" (does the instrument agree that the seed diverges?)
    or "firstbad" (does it put the FIRST divergence on the fabric's row?).
    THE SECOND IS THE DISCRIMINATING ONE and the reason both are printed: a
    fabric-FAIL seed comes out FAIL on an instrument whose directive is wrong
    TOO -- for the wrong reason, at the wrong row -- so on the failure families
    the verdict axis separates nothing.  All of the verdict axis's power is in
    the fabric-PASS row, where a wrong directive shows up as a false alarm."""
    per = collections.defaultdict(lambda: [0, 0])
    for r in res:
        if r.get("err") or key not in r:
            continue
        if metric == "firstbad":
            if r["fabric_bad"] == 0 or r[key]["bad"] == 0:
                continue           # only defined where both legs diverge
            p = per[axis(r)]
            p[1] += 1
            p[0] += (r[key]["first"] == r["fabric_first"])
        else:
            p = per[axis(r)]
            p[1] += 1
            p[0] += (r["fabric_bad"] != 0) == (r[key]["bad"] != 0)
    return dict(per)


def show_breakdown(res, keys, axis, title, width=34, metric="verdict"):
    print(f"\n  --- {'VERDICT' if metric == 'verdict' else 'FIRST-BAD-ROW'} "
          f"agreement by {title} ---")
    rows = sorted({axis(r) for r in res if not r.get("err")},
                  key=lambda x: str(x))
    hdr = "".join(f"{nm:>18s}" for _k, nm in keys)
    print(f"    {'':{width}s}{hdr}")
    for v in rows:
        cells = ""
        for k, _nm in keys:
            b = breakdown(res, k, axis, metric).get(v, [0, 0])
            cells += f"{b[0]:>8d} /{b[1]:>4d}" + (
                f" {100.0 * b[0] / b[1]:4.0f}%" if b[1] else "      ")
        print(f"    {str(v)[:width]:{width}s}{cells}")


def report(res, fails, perturb=0):
    """Every table, from rows alone -- so `--report` can re-print a saved run
    without touching a binary, and a reviewer can check the arithmetic."""
    have = [(k, nm) for k, nm in (("sys", "tb_sys"),
                                  ("core_stim", "core/stim"),
                                  ("core_term", "core/term"))
            if any(k in r for r in res)]
    titles = {"sys": "tb_sys REPLAY (both directives + overlay + the seed's "
                     "own wait source)",
              "core_stim": "tb_v30_core, STIMULUS only (b1/a1_rescore's "
                           "comparator)",
              "core_term": "tb_v30_core, TERMINATOR + IVT2 patch "
                           "(c1_rescore's comparator)"}
    print("\n=== THE FIDELITY TABLE: offline verdict vs FABRIC verdict ===")
    tabs = [table(res, k, titles[k]) for k, _nm in have]
    for r in res:
        r["family"] = fails.get(r["seed"], {}).get("family", "(fabric PASS)")
    for metric in ("verdict", "firstbad"):
        show_breakdown(res, have, lambda r: r.get("wait_mode", "?"),
                       "WAIT MODE", width=12, metric=metric)
        show_breakdown(res, have,
                       lambda r: ("stimulus event" if r.get("has_evt")
                                  else "no stimulus event"),
                       "WHETHER THE SEED HAS A STIMULUS EVENT "
                       "(the one-scheduler blindness)", width=20,
                       metric=metric)
        show_breakdown(res, have, lambda r: r["family"], "LEDGER FAMILY",
                       metric=metric)
    if perturb:
        pk = [r for r in res if not r.get("err") and "perturbed" in r]
        clean = [r for r in pk if r["sys"]["bad"] == 0]
        moved = [r for r in clean if r["perturbed"]["bad"] != 0]
        print(f"\n  --- NON-VACUITY CONTROL: the seed's own wait source "
              f"perturbed by {perturb} ---")
        print(f"    seeds the faithful replay scored CLEAN: {len(clean)}")
        print(f"    of those, DIVERGENT once perturbed     : {len(moved)}"
              f"  ({'PASS' if len(moved) == len(clean) and clean else 'FAIL'})")
        for r in [x for x in clean if x["perturbed"]["bad"] == 0][:8]:
            print(f"      STILL CLEAN (vacuous!) {r['seed']}")
    return tabs


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", default=None,
                    help="failure ledger (default: fz2_ledger.CURRENT)")
    ap.add_argument("--seeds", help="comma-separated seed names, e.g. fz2c/400007")
    ap.add_argument("--all-failures", action="store_true",
                    help="every ledger failure with banked socket rows")
    ap.add_argument("--pass-sample", type=int, default=0,
                    help="N passing seeds, sampled deterministically from the "
                         "retained captures that are NOT ledger failures")
    ap.add_argument("--sample-seed", type=int, default=20260810)
    ap.add_argument("--family", help="restrict to a ledger family prefix")
    ap.add_argument("--leg", choices=("base", "ret"), default="ret",
                    help="tb_sys build; `ret` carries the §56.3a retention "
                         "model and is the one the flashed bitstream is")
    ap.add_argument("--also-tbcore", action="store_true",
                    help="also score the two tb_v30_core comparators on the "
                         "SAME population -- this is the head-to-head")
    ap.add_argument("--perturb", type=int, default=0,
                    help="NON-VACUITY CONTROL: re-run every seed with its OWN "
                         "wait source perturbed by N (fixed level / LFSR seed "
                         "/ vector rotation) and require it to diverge")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--report", metavar="RUN.json",
                    help="re-print every table from a saved --out, running "
                         "nothing")
    ap.add_argument("--no-fabric-era-guard", action="store_true")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    led = fzl.load(a.ledger, why="fz2_replay fidelity reference")
    fails = {f["seed"]: f for f in led["failures"]}

    if a.report:
        d = json.loads(Path(a.report).read_text())
        print(f"  RE-PRINTED from {a.report}\n"
              f"    run {d.get('ts')}  leg {d.get('leg')}  "
              f"ledger {d.get('ledger')}\n"
              f"    tb_sys receipt {str(d.get('tb_sys_receipt'))[:16]}…  "
              f"git {(d.get('git') or {}).get('describe')}")
        report(d["rows"], fails, perturb=a.perturb)
        return 0

    ok, rep = fabric_era(led)
    print("\n  --- FABRIC ERA GUARD ---")
    for l in rep:
        print(f"    {l}")
    if not ok:
        if not a.no_fabric_era_guard:
            sys.exit("\n  ERA MISMATCH -- REFUSING TO SCORE.  An offline "
                     "replay of RTL that is not the RTL in the socket is a\n"
                     "  statement about two trees.  Re-flash, or pass "
                     "--no-fabric-era-guard and say so beside the number.\n")
        print("    *** OVERRIDDEN by --no-fabric-era-guard ***")
    else:
        print("    FABRIC ERA GUARD: PASS")

    # the receipts, before a single row is compared
    binp = x1.BIN[a.leg]
    art.require(binp, why="fz2_replay (tb_sys)")
    print(f"\n  DUT tb_sys   {binp.relative_to(ROOT)}\n"
          f"               receipt {art.receipt_id(binp)}\n"
          f"               tree    {x1.tree_key()[:16]}…")
    if a.also_tbcore:
        cb = check_seq.tb_bin("ucore")
        art.require(cb, why="fz2_replay (tb_v30_core comparators)")
        print(f"  DUT tb_v30_core {Path(cb).relative_to(ROOT)}\n"
              f"               receipt {art.receipt_id(cb)}")
    print(f"  git          {art.git_state()['describe']}")

    caps = retained()
    pop = []
    if a.seeds:
        pop = [s.strip() for s in a.seeds.split(",") if s.strip()]
    else:
        if a.all_failures or not a.pass_sample:
            f = sorted(fails)
            if a.family:
                f = [s for s in f if fails[s]["family"].startswith(a.family)]
            pop += f
        if a.pass_sample:
            # the A-12 discards are OUT of the corpus's own denominator, so
            # they are not "passing seeds" and must not pad this one either.
            disc = {d["seed"] for d in led.get("discards", [])}
            passing = sorted(s for s in caps
                             if s not in fails and s not in disc)
            rng = random.Random(a.sample_seed)
            pop += rng.sample(passing, min(a.pass_sample, len(passing)))
    missing = [s for s in pop if s not in caps]
    pop = [s for s in pop if s in caps]
    jobs = [(s, caps[s]) for s in pop]

    nf = sum(1 for s in pop if s in fails)
    print(f"\n  population   {len(jobs)} seeds with banked socket rows "
          f"({nf} fabric-FAIL, {len(jobs) - nf} fabric-PASS)")
    if missing:
        print(f"  NOT SCOREABLE (no retained capture): {len(missing)}  "
              f"{missing[:6]}")

    nj = a.jobs or min(10, max(1, (os.cpu_count() or 2) - 2))
    opt = {"leg": a.leg, "also_tbcore": a.also_tbcore, "perturb": a.perturb}
    t0 = time.time()
    res = []
    from multiprocessing import Pool
    with Pool(nj, initializer=_init, initargs=(opt,)) as pool:
        for r in pool.imap_unordered(one, jobs, chunksize=1):
            res.append(r)
            if len(res) % 25 == 0:
                print(f"    {len(res)}/{len(jobs)}  "
                      f"({time.time() - t0:.0f}s)", flush=True)
    res.sort(key=lambda r: (r["cid"], r["k"]))
    errs = [r for r in res if r.get("err")]
    print(f"  ran in {time.time() - t0:.0f}s, {len(errs)} errors")
    for r in errs[:12]:
        print(f"    ERROR {r['seed']}: {r['err']}")

    tabs = report(res, fails, perturb=a.perturb)

    if a.out:
        Path(a.out).write_text(json.dumps(
            {"tool": "sw/fz2_replay.py",
             "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "ledger": os.path.relpath(os.path.abspath(a.ledger or fzl.CURRENT),
                                       ROOT),
             "leg": a.leg,
             "tb_sys_receipt": art.receipt_id(binp),
             "tb_sys_tree": x1.tree_key(),
             "git": art.git_state(),
             "era_report": rep, "era_ok": ok,
             "tables": tabs, "rows": res}, indent=1))
        print(f"\n  wrote {a.out}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
