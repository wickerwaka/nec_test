#!/usr/bin/env python3
"""sm3_s16_score -- score an engine on the S16 directed display walk, and
classify every residual cell against the pre-registered bar.

`docs/notes/sm3_s16_prereg_2026-08-05.md` §4.2:

  L1  ZERO cells fail with a family-A/C signature -- a `seg`/`bus` mismatch on a
      display-window row whose ONLY difference is the A19-16 nibble.
  L2  ZERO cells fail with a family-E signature -- a `ube` mismatch.
  L3  every cell whose GOLDEN carries neither the family-B shape (a whole-capture
      one-row shift) nor the family-D two-sample signature PASSES.

The two BOOKED shapes are read off the GOLDEN alone, so the partition is a
property of the population and not of the engine being scored:

  family-B shape   the engine's rows are the golden's shifted by one -- detected
                   as `golden[r:] == core[r+1:]` over the rest of the capture;
  family-D shape   `bs(r) != PASV and t(r) in {T4,Ti} and t(r+1) == Ti`, which
                   the analyser can only record because it samples BS TWICE per
                   clock (`nec_bus.sv` `bs_early` at the falling edge vs `bs_q`
                   at the end).  A whole-clock BS level cannot produce it.

Usage:
    python3 sw/sm3_s16_score.py [--core ucore] [--jobs 4] [--details 6]
"""
import argparse
import gzip
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core as cc                                     # noqa: E402
from sm3_s16_cell import FORMS, PROGRAMS, WAITS, suite_dir   # noqa: E402

BS_C, T_C = 7, 8


def golden_shapes(cy):
    """(has_family_D_signature,) read off the golden rows alone."""
    d = False
    for i in range(len(cy) - 1):
        if cy[i][BS_C] != "PASV" and cy[i][T_C] in ("T4", "Ti") \
                and cy[i + 1][T_C] == "Ti":
            d = True
    return d


def is_late(exp, got, r, n=8):
    """The family-B shape, tested AT the first divergence: the engine's rows
    from `r` on are the golden's from `r` on, shifted one row LATE.  `n` rows
    of agreement is the test -- a whole-suffix identity is too strong, because
    a one-row lag re-converges and then diverges again downstream."""
    if r + 1 + n > len(got) or r + n > len(exp):
        return False
    return all(exp[r + k] == got[r + 1 + k] for k in range(n))


def is_early(exp, got, r, n=8):
    """...and its mirror: the engine's rows are one row EARLY."""
    if r + 1 + n > len(exp) or r + n > len(got):
        return False
    return all(exp[r + 1 + k] == got[r + k] for k in range(n))


def classify_first(exp, got, mm):
    """The cell's SIGNATURE = the class of its FIRST divergence, which is the
    convention every partition in `ucore_provenance.md` §76 uses."""
    r, c, e, g = mm[0]
    if c == "len":
        return "LEN"
    name = cc.COL_NAME.get(c, str(c))
    if name == "ube":
        return "E_ube"
    if name == "seg":
        return "AC_seg"
    if name == "bus" and r < len(exp) and exp[r][T_C] != "T1" \
            and isinstance(e, int) and isinstance(g, int) \
            and (e & 0xFFFF) == (g & 0xFFFF) and (e >> 16) != (g >> 16):
        return "AC_nibble"
    if name == "busstat":
        if is_late(exp, got, r):
            return "B_late"
        if is_early(exp, got, r):
            return "B_early"
        return "busstat_other"
    if name in ("pins", "tstate"):
        if is_late(exp, got, r):
            return "B_late"
        if is_early(exp, got, r):
            return "B_early"
        return "D_tstate"
    return name


def sims_for(core, cases, w, binp):
    """The engine's record stream for one form file, keyed as `parse_out` keys
    it.  `--core sim` is the C++ model through `timed_gate.run_form`, which is
    the STANDING sim driver and returns `check_core.parse_out`'s own dict -- so
    every line below this is engine-neutral and the PASS definition is
    identical on both legs (SM3 sitting 18)."""
    if core == "sim":
        # RIG NOTE (SM3 s18).  `v30sim timed-run` keys its record stream by the
        # ARRAY POSITION of the case it was handed (`timed_runner.cpp` 658-662),
        # while `compose_batch` keys the RTL batch by the golden's own `idx`.
        # The S16 suites' `idx` is the DELAY and starts at 1..4 with gaps (141
        # non-composable cells), so a `sims.get(c["idx"])` written for the RTL
        # leg silently reads the WRONG CASE on the model leg.  Re-key here, once.
        import timed_gate as tg
        s = tg.run_form(cases, w, False)
        return {c["idx"]: s.get(i) for i, c in enumerate(cases)}
    import tempfile
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


def run_one(args):
    waits, p, core, details = args
    sd = suite_dir(waits, p)
    if not sd.exists():
        return None
    r = subprocess.run(
        [sys.executable, str(SW / "check_core.py"), "--core", core,
         "--suite-dir", str(sd.relative_to(ROOT)), "--opcodes", "all",
         "--cases", "0", "--waits", str(waits), "--details", "0"],
        capture_output=True, text=True, cwd=ROOT, timeout=7200)
    out = {"waits": waits, "p": p, "forms": {}}
    # NB `TOTAL:` also matches this shape -- excluding it is the
    # difference between 1,371 cells and a doubled 2,742.
    for m in re.finditer(r"^(\S+): (\d+)/(\d+) full", r.stdout, re.M):
        if m.group(1) == "TOTAL":
            continue
        out["forms"][m.group(1)] = (int(m.group(2)), int(m.group(3)))
    if not out["forms"]:
        out["error"] = r.stdout[-400:] + r.stderr[-200:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default="ucore", choices=("ucore", "fsm", "sim"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--details", type=int, default=8)
    ap.add_argument("--save", help="write the per-cell PASS map here")
    a = ap.parse_args()

    if a.core == "sim":
        # the model has no `check_core.py --core sim` leg; its headline figure
        # is derived from the SAME per-cell map the RTL legs' `--save` writes
        # (`not mm and arch_ok`), which is what `N/M full` counts.
        import simbin
        simbin.ensure(why="sm3_s16_score")
    else:
        cc.require_bin(a.core, "sm3_s16_score")
        jobs = [(w, p, a.core, a.details) for w in WAITS for p in PROGRAMS]
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            res = [r for r in ex.map(run_one, jobs) if r]

        tot_p = tot_n = 0
        per_w = {}
        for r in res:
            for form, (ok, n) in r["forms"].items():
                tot_p += ok
                tot_n += n
                w = per_w.setdefault(r["waits"], [0, 0])
                w[0] += ok
                w[1] += n
            if "error" in r:
                print(f"  ERROR w{r['waits']} p{r['p']}: {r['error'][:200]}")
        for w in sorted(per_w):
            print(f"  w{w}: {per_w[w][0]}/{per_w[w][1]}")
        print(f"S16 TOTAL ({a.core}): {tot_p}/{tot_n}")

    # ---- the per-cell classification (in-process, one binary invocation per
    # suite dir would double the work; re-run the engine here through
    # check_core's own helpers instead)
    binp = None if a.core == "sim" else cc.core_bin(a.core)
    L1 = L2 = 0
    L3_bad = []
    arch_bad = []
    fam = {}
    cellmap = {}
    shown = 0
    for w in WAITS:
        for p in PROGRAMS:
            sd = suite_dir(w, p)
            if not sd.exists():
                continue
            for form in FORMS:
                fn = sd / f"{form}.json.gz"
                if not fn.exists():
                    continue
                cases = json.load(gzip.open(fn))
                sims = sims_for(a.core, cases, w, binp)
                if sims is None:
                    print(f"  SIM FAIL {sd.name}/{form}")
                    continue
                for c in cases:
                    sim = sims.get(c["idx"])
                    if sim is None:
                        fam["NO_SIM"] = fam.get("NO_SIM", 0) + 1
                        continue
                    res = cc.check_case(c, sim, 0xFFFF)
                    if not res.get("arch_ok"):
                        fam["ARCH"] = fam.get("ARCH", 0) + 1
                        arch_bad.append((f"w{w}/p{p}/{form}/{c['idx']}",
                                         res.get("reg_bad"),
                                         len(res.get("ram_bad") or []),
                                         res.get("q_ok")))
                    rows, _e, _i0, _i1 = cc.build_rows_sim(
                        sim["recs"], c["initial"]["queue"],
                        n_close=cc.n_fpops(c) - 1)
                    if rows is None:
                        fam["NO_ROWS"] = fam.get("NO_ROWS", 0) + 1
                        continue
                    mm, _ = cc.diff_rows(c["cycles"], rows)
                    hasD = golden_shapes(c["cycles"])
                    key = f"w{w}/p{p}/{form}/{c['idx']}"
                    cellmap[key] = bool(not mm and res.get("arch_ok"))
                    if not mm:
                        continue
                    tag = classify_first(c["cycles"], rows, mm)
                    fam[tag] = fam.get(tag, 0) + 1
                    if tag in ("AC_nibble", "AC_seg"):
                        L1 += 1
                        print(f"  L1 {key}: first={mm[0]}")
                    if tag == "E_ube":
                        L2 += 1
                        print(f"  L2 {key}: first={mm[0]}")
                    booked = tag in ("B_late", "B_early") or \
                        (hasD and tag == "D_tstate")
                    if not booked:
                        L3_bad.append((key, tag, mm[0], hasD))
                    if shown < a.details:
                        print(f"  FAIL {key}: tag={tag} golden_D={hasD} "
                              f"first={mm[0]}")
                        shown += 1
    print(f"\nBAR L1 (family A/C nibble signatures): {L1}   [bar: 0]")
    print(f"BAR L2 (family E ube signatures):      {L2}   [bar: 0]")
    print(f"BAR L3 (fails with neither booked shape): {len(L3_bad)}   [bar: 0]")
    for k in L3_bad[:400]:
        print(f"    {k}")
    if a.save:
        Path(a.save).write_text(json.dumps(cellmap, indent=0))
        print(f"per-cell map -> {a.save} ({sum(cellmap.values())}/{len(cellmap)} pass)")
    print(f"ARCH failures: {len(arch_bad)}")
    for k in arch_bad[:12]:
        print(f"    {k}")
    print(f"signature census: {fam}")
    return 0 if (L1 == 0 and L2 == 0 and not L3_bad) else 1


if __name__ == "__main__":
    sys.exit(main())
