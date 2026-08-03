#!/usr/bin/env python3
"""timed_gate - the standing CYCLE gate for sim/v30sim's TIMED mode (ucsim-t).

Drives `v30sim timed-run` over a golden suite and pipes the emitted per-clock
records through the UNMODIFIED sw/check_core.py comparison machinery:

    check_core.parse_out       reads the record stream (`= / r / f / .`)
    check_core.build_rows_sim  shadow-queue reconstruction + 11-column synthesis
    check_core.diff_rows       column policy (COMPARED_COLS + the idle-row mask)
    check_core.dontcare_cells  the documented golden-schema don't-cares
    check_core.n_fpops         the golden's window-closing F-pop count

check_core is IMPORTED, never forked.  If the timed model ever needs a
comparison rule the RTL gate does not have, that is a finding to argue in the
ledger, not a local edit here.

The flags-mask policy is imported from sw/ucsim_check.py for the same reason.

What is reported, per form and in total:

  arch      final registers, sparse-delta reconstruction (`initial.regs`
            updated by `final.regs`), flags under the metadata mask.  This is
            the T0 gate: the architectural answer must survive the swap of the
            bus policy, exactly.
  window    whether build_rows_sim could find the golden's window (it needs
            n_fpops(golden) queue-F pops in the record stream).
  rows      per-case count of column mismatches inside the window.  At T0 this
            is EXPECTED to be large: the naive bus is strictly serial with no
            prefetch scheduler.  The number is a baseline to ratchet down, and
            the per-column histogram is the work list.

Usage:
  timed_gate.py [--suite tests/v30/v0.1] [--forms B8,88,...] [--cases N]
                [--waits N] [--raw-flags] [--details N] [--report out.json]
                [--sbs FORM:IDX]     print one case's golden vs sim rows
"""

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_core                      # noqa: E402
from ucsim_check import flags_mask_of, load_meta   # noqa: E402

SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
V01 = ROOT / "tests" / "v30" / "v0.1"

REGS = check_core.REGS


def form_files(suite: Path, forms: str):
    if forms == "all":
        names = sorted(p.name.split(".json")[0]
                       for p in suite.glob("*.json.gz"))
    else:
        names = [f.strip() for f in forms.split(",") if f.strip()]
    return [(n, suite / f"{n}.json.gz") for n in names
            if (suite / f"{n}.json.gz").exists()]


def run_form(cases, waits, mirror):
    """-> check_core.parse_out dict keyed by input order."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "rows.txt"
        argv = [str(SIM), "timed-run", str(ROM), f"--waits={waits}"]
        if mirror:
            argv.append("--mirror")
        payload = json.dumps(cases).encode()
        with open(out, "wb") as fo:
            r = subprocess.run(argv, input=payload, stdout=fo)
        if r.returncode != 0:
            raise RuntimeError(f"timed-run exited {r.returncode}")
        return check_core.parse_out(out)


def arch_check(c, sim, flags_mask, events=None, i0=None, i1=None):
    """Sparse-delta final-register comparison, check_core's policy.
    -> (ok, bad_field_list)"""
    if sim is None or sim.get("final") is None:
        return False, ["no-final"]
    exp = dict(c["initial"]["regs"])
    exp.update(c["final"]["regs"])
    got = sim["final"]

    # PIN-EVENT FORMS: the golden's recorded final.flags is the POST-HANDLER
    # store-stub PUSH PSW, an unreliable capture on both sides; the
    # ARCHITECTURAL final flags are the interrupt-pushed PSW with IE/BRK
    # cleared.  check_core.check_case applies exactly this rule for the RTL
    # gate (`_pushed_psw_flags`), so it is IMPORTED here rather than forked --
    # otherwise the POP-PSW boundary race (INT.9D) scores as a model failure
    # when both sides agree on the frame they pushed.
    if events is not None and (c.get("evt") is not None or "close_addr" in c):
        init_ram = {a & 0xFFFFF: v for a, v in c["initial"]["ram"]}
        golden_img = dict(init_ram)
        golden_img.update({a & 0xFFFFF: v for a, v in c["final"]["ram"]})
        memv = dict(init_ram)
        for a, b in check_core.sim_writes(events, i0, i1):
            memv[a & 0xFFFFF] = b
        gp = check_core._pushed_psw_flags(exp.get("sp"), exp.get("ss"),
                                          golden_img)
        sp_ = check_core._pushed_psw_flags(got.get("sp"), got.get("ss"), memv)
        if gp is not None and sp_ is not None and (gp & 0xF000) == 0xF000:
            exp = dict(exp)
            exp["flags"] = gp
            got = dict(got)
            got["flags"] = sp_

    bad = []
    for k in REGS:
        if k == "flags":
            if (exp[k] & flags_mask) != (got[k] & flags_mask):
                bad.append(k)
        elif exp[k] != got[k]:
            bad.append(k)
    return not bad, bad


def row_check(c, sim):
    """-> (window_ok, n_mismatch, Counter(column), rows_sim, events, i0, i1)"""
    rows, events, i0, i1 = check_core.build_rows_sim(
        sim["recs"], c["initial"]["queue"], n_close=check_core.n_fpops(c) - 1)
    if rows is None:
        return False, None, Counter(), None, events, i0, i1
    mm, _masked = check_core.diff_rows(c["cycles"], rows)
    dc = check_core.dontcare_cells(c)
    if dc:
        mm = [m for m in mm if (m[0], m[1]) not in dc]
    hist = Counter(check_core.COL_NAME.get(m[1], str(m[1])) for m in mm)
    return True, len(mm), hist, rows, events, i0, i1


def side_by_side(c, rows_sim, title):
    gold = c["cycles"]
    print(f"\n=== {title} ===")
    print(f"    {c['name']}   bytes={[hex(b) for b in c['bytes']]}   "
          f"queue={c['initial']['queue']}")
    hdr = "%-3s | %-4s %-5s %-6s %-3s %-6s %-2s %-4s | %-4s %-5s %-6s %-3s %-6s %-2s %-4s"
    print(hdr % ("#", "T", "stat", "bus", "seg", "data", "q", "qb",
                 "T", "stat", "bus", "seg", "data", "q", "qb"))
    print("-" * 108)
    n = max(len(gold), len(rows_sim))
    for i in range(n):
        g = gold[i] if i < len(gold) else None
        s = rows_sim[i] if i < len(rows_sim) else None

        def cell(r):
            if r is None:
                return "%-4s %-5s %-6s %-3s %-6s %-2s %-4s" % ("-", "-", "-",
                                                               "-", "-", "-",
                                                               "-")
            return "%-4s %-5s %06X %-3s %04X   %-2s %02X" % (
                r[8], r[7], r[1], r[2], r[6], r[9], r[10])
        mark = " " if (g and s and
                       all(g[k] == s[k] for k in check_core.COMPARED_COLS)) \
            else "*"
        print("%-3d%s| %s | %s" % (i, mark, cell(g), cell(s)))
    print("-" * 108)
    print("GOLDEN rows: %d   SIM rows: %d" % (len(gold), len(rows_sim)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(V01))
    ap.add_argument("--forms", default="B8")
    ap.add_argument("--cases", type=int, default=0, help="0 = all")
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--raw-flags", action="store_true")
    ap.add_argument("--details", type=int, default=4)
    ap.add_argument("--report", default="")
    ap.add_argument("--sbs", default="",
                    help="FORM:IDX -- print that case's golden vs sim rows")
    args = ap.parse_args()

    suite = Path(args.suite)
    meta = load_meta(suite)

    sbs_form, sbs_idx = None, None
    if args.sbs:
        sbs_form, _, n = args.sbs.partition(":")
        sbs_idx = int(n or 0)

    forms = form_files(suite, sbs_form or args.forms)
    tot = Counter()
    hist = Counter()
    per_form = {}
    rc = 0

    for name, path in forms:
        cases = json.load(gzip.open(path))
        if args.cases:
            cases = cases[:args.cases]
        if sbs_form:
            cases = cases[sbs_idx:sbs_idx + 1]
        mask = 0xFFFF if args.raw_flags else flags_mask_of(name, meta)
        sims = run_form(cases, args.waits, args.mirror)

        f = Counter()
        shown = 0
        for i, c in enumerate(cases):
            sim = sims.get(i)
            f["n"] += 1
            if sim is None:
                f["arch_bad"] += 1
                f["no_rows"] += 1
                continue
            wok, nmm, h, rows, events, i0, i1 = row_check(c, sim)
            # the row window is built FIRST: the pin-event flags policy reads
            # the sim's own writes out of it (see arch_check)
            ok, bad = arch_check(c, sim, mask, events if wok else None, i0, i1)
            f["arch_ok" if ok else "arch_bad"] += 1
            if not ok and shown < args.details:
                shown += 1
                print(f"  {name}[{i}] ARCH {bad}: {c['name']}")
            if not wok:
                f["no_window"] += 1
                continue
            f["window"] += 1
            f["row_mm"] += nmm
            if nmm == 0:
                f["rows_exact"] += 1
            hist += h
            if sbs_form:
                side_by_side(c, rows, f"{name} case {sbs_idx} (waits={args.waits})")

        per_form[name] = dict(f)
        tot += f
        if f["arch_bad"]:
            rc = 1
        print("%-8s arch %5d/%-5d   window %5d/%-5d   rows-exact %5d   "
              "row-diffs %d"
              % (name, f["arch_ok"], f["n"], f["window"], f["n"],
                 f["rows_exact"], f["row_mm"]))

    print("\nTOTAL   arch %d/%d   window %d/%d   rows-exact %d   row-diffs %d"
          % (tot["arch_ok"], tot["n"], tot["window"], tot["n"],
             tot["rows_exact"], tot["row_mm"]))
    if hist:
        print("row-diff columns: " +
              ", ".join(f"{k}={v}" for k, v in hist.most_common()))
    if args.report:
        json.dump({"suite": str(suite), "waits": args.waits,
                   "total": dict(tot), "columns": dict(hist),
                   "forms": per_form}, open(args.report, "w"), indent=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
