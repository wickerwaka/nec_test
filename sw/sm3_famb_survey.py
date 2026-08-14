#!/usr/bin/env python3
"""sm3_famb_survey -- THE FAMILY-B SURVEY (SM3 sitting 21, task #36).

**A MEASUREMENT TOOL, NOT A GATE.**  It scores nothing and it may never be
quoted as a pass.  Its only job is to produce, from measurement rather than
from a cell count, the CLOSING POPULATION of each of family B's two booked
mechanisms -- `ucore_provenance.md` §79.G -- across every population in the
tree that can carry them.

WHAT THE TWO SIGNATURES ARE, READ OFF THE GOLDEN ALONE (so the partition is a
property of the population, not of the engine being surveyed):

  B-1  THE WAKE'S FIRST PREFETCH, in the regime where F54 CANCELLED the HALT
       announcement.  The golden carries NO `HALT` status row at all: the part
       goes from the running cycle straight to the wake.  What is measured is
       the row the wake's first `CODE` announcement lands on, golden vs engine.

  B-2  THE SECOND ACKNOWLEDGE'S SPACING, in the regime where the announcement
       WAS made.  The golden carries a `HALT` row, and the observable is the
       ANNOUNCEMENT-to-ANNOUNCEMENT gap of the INTA pair -- the row on which
       `busstat` first becomes `INTA` after not being `INTA`, twice.

A cell belongs to a mechanism if the engine's own value of that mechanism's
observable differs from the golden's.  A failing cell that matches NEITHER is
reported in its own bucket and is NOT silently attributed.

POPULATIONS SURVEYED
  * the four HLT delay sweeps        `tests/v30/s10-hltsweep-w{0,1}`,
                                     `tests/v30/s13-hltsweep-w{2,3}`
  * the S16 directed display walk    `tests/v30/s16-dispwalk-w{0..3}-p{0..5}`
  * `--fuzz REPORT.json`             a `timed_fuzz --report` file: counts the
                                     banked seeds whose GOLDEN carries either
                                     regime at all, which is the bound on what
                                     the bank can possibly contribute.

Usage:
    python3 sw/sm3_famb_survey.py --core {sim,ucore} [--fuzz report.json]
"""
import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core as cc                                      # noqa: E402
from sm3_s16_cell import FORMS, PROGRAMS, WAITS, suite_dir    # noqa: E402

BS_C, T_C = 7, 8

SWEEPS = [("tests/v30/s10-hltsweep-w0", 0),
          ("tests/v30/s10-hltsweep-w1", 1),
          ("tests/v30/s13-hltsweep-w2", 2),
          ("tests/v30/s13-hltsweep-w3", 3)]


def announces(rows, kind):
    """Rows on which `busstat` FIRST becomes `kind` after not being it -- the
    ANNOUNCEMENT clocks, which is the coordinate §79.G's B-2 table is in."""
    out, prev = [], None
    for i, r in enumerate(rows):
        if r[BS_C] == kind and prev != kind:
            out.append(i)
        prev = r[BS_C]
    return out


def has_halt(rows):
    return any(r[BS_C] == "HALT" for r in rows)


def observables(rows):
    """The two mechanisms' observables, in one pass."""
    inta = announces(rows, "INTA")
    return {"halt": has_halt(rows),
            "code": announces(rows, "CODE"),
            "inta": inta,
            "gap": (inta[1] - inta[0]) if len(inta) >= 2 else None}


def sims_for(core, cases, w, binp):
    if core == "sim":
        import timed_gate as tg
        s = tg.run_form(cases, w, False)
        return {c["idx"]: s.get(i) for i, c in enumerate(cases)}
    with tempfile.TemporaryDirectory() as td:
        b, o = Path(td) / "b.txt", Path(td) / "o.txt"
        cc.compose_batch(cases, b)
        rr = subprocess.run(
            [str(binp), f"+batch={b}", f"+out={o}",
             f"+waits={w}", f"+ce_div={cc.CE_DIV_DEFAULT}"],
            cwd=ROOT, capture_output=True, text=True)
        if rr.returncode != 0 or not o.exists():
            return None
        return cc.parse_out(o)


def survey_suite(core, binp, sd, w, label, out):
    for fn in sorted(Path(ROOT / sd).glob("*.json.gz")):
        form = fn.name.split(".json")[0]
        cases = json.load(gzip.open(fn))
        sims = sims_for(core, cases, w, binp)
        if sims is None:
            print(f"  ENGINE FAIL {sd}/{form}")
            continue
        for c in cases:
            sim = sims.get(c["idx"])
            if sim is None:
                continue
            rows, _e, _i0, _i1 = cc.build_rows_sim(
                sim["recs"], c["initial"]["queue"],
                n_close=cc.n_fpops(c) - 1)
            if rows is None:
                continue
            mm, _ = cc.diff_rows(c["cycles"], rows)
            if not mm:
                continue
            go, eo = observables(c["cycles"]), observables(rows)
            # the regime is the GOLDEN's; the divergence is the engine's
            if not go["halt"]:
                sig = "B1" if go["code"] != eo["code"] else "B1-regime-other"
            elif go["gap"] is not None and go["gap"] != eo["gap"]:
                sig = "B2"
            elif go["code"] != eo["code"]:
                sig = "B1-late-with-display"
            else:
                sig = "OTHER"
            out.append({"cell": f"{label}/{form}/{c['idx']}", "sig": sig,
                        "first": [mm[0][0], cc.COL_NAME.get(mm[0][1]),
                                  str(mm[0][2]), str(mm[0][3])],
                        "g_code": go["code"][:3], "e_code": eo["code"][:3],
                        "g_inta": go["inta"][:3], "e_inta": eo["inta"][:3],
                        "g_gap": go["gap"], "e_gap": eo["gap"],
                        "halt": go["halt"], "ndiff": len(mm)})


def survey_fuzz(path):
    """The BOUND the banked fuzz seeds can contribute, read off the report.
    A seed can only carry B-1 or B-2 if its capture reaches the regime; this
    counts how many FAILING seeds do, so the bound is measured and not
    assumed."""
    rep = json.load(open(path))
    seeds = rep.get("seeds") or rep.get("results") or []
    tot = fail = halt = inta2 = 0
    for s in seeds:
        if not isinstance(s, dict):
            continue
        tot += 1
        ok = s.get("ok", s.get("pass"))
        if ok:
            continue
        fail += 1
        rows = s.get("chip_rows") or s.get("rows")
        if not rows:
            continue
        bs = [r[BS_C] if isinstance(r, (list, tuple)) else None for r in rows]
        if "HALT" in bs:
            halt += 1
        n, prev = 0, None
        for b in bs:
            if b == "INTA" and prev != "INTA":
                n += 1
            prev = b
        if n >= 2:
            inta2 += 1
    return {"seeds": tot, "failing": fail,
            "failing_with_HALT": halt, "failing_with_INTA_pair": inta2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"))
    ap.add_argument("--fuzz", help="a timed_fuzz --report json")
    ap.add_argument("--save")
    a = ap.parse_args()

    binp = None
    if a.core == "sim":
        import simbin
        simbin.ensure(why="sm3_famb_survey")
    else:
        cc.require_bin(a.core, "sm3_famb_survey")
        binp = cc.core_bin(a.core)

    out = []
    for sd, w in SWEEPS:
        survey_suite(a.core, binp, sd, w, f"sweep-w{w}", out)
    for w in WAITS:
        for p in PROGRAMS:
            sd = suite_dir(w, p)
            if sd.exists():
                survey_suite(a.core, binp, sd.relative_to(ROOT), w,
                             f"s16-w{w}-p{p}", out)

    print(f"=== FAMILY-B SURVEY, core={a.core} ===")
    for scope, pred in (("sweeps", lambda k: k.startswith("sweep")),
                        ("S16", lambda k: k.startswith("s16"))):
        sel = [r for r in out if pred(r["cell"])]
        cen = {}
        for r in sel:
            cen[r["sig"]] = cen.get(r["sig"], 0) + 1
        print(f"\n-- {scope}: {len(sel)} row-failing cells   {cen}")
        for sig in ("B1", "B2", "B1-late-with-display",
                    "B1-regime-other", "OTHER"):
            rs = [r for r in sel if r["sig"] == sig]
            if not rs:
                continue
            print(f"   [{sig}]  {len(rs)}")
            for r in rs:
                print(f"     {r['cell']:26s} first={r['first']} "
                      f"halt={int(r['halt'])} code g{r['g_code']}/e{r['e_code']} "
                      f"inta g{r['g_inta']}/e{r['e_inta']} "
                      f"gap g{r['g_gap']}/e{r['e_gap']} n={r['ndiff']}")

    if a.fuzz:
        print(f"\n-- banked fuzz bound ({a.fuzz}): {survey_fuzz(a.fuzz)}")
    if a.save:
        Path(a.save).write_text(json.dumps(out, indent=1))
        print(f"\n-> {a.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
