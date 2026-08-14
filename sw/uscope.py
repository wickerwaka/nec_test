#!/usr/bin/env python3
"""uscope -- the ucore MICROSCOPE (ucore_provenance.md sec.25 item 5).

One case, three views, ONE row index:

    row index  ==  CE clock index  ==  `+eutrace` line number

so a divergence at row N is read straight off EU-trace line N (+1 for the
header).  The three views are

  GOLDEN   the recorded silicon row (`cycles` in the v0.1 suite)
  RTL      check_core.build_rows_sim over the ucore TB's record stream
  EU       the ucore EU's own per-CE-clock state line (`+eutrace`)

and, with --rowtrace, the MODEL's micro-row schedule
(`V30SIM_ROWTRACE=1 v30sim timed-run`), which names the ROM row standing on
each clock.

    uscope.py FORM IDX [--core ucore] [--waits N] [--from N] [--to N]
              [--rowtrace] [--full]

`--full` prints every row; the default stops eight rows past the first
divergence, which is the only part anyone reads.
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import check_core                                     # noqa: E402

import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"


def fmt(row):
    if row is None:
        return " " * 46
    ale, bus, seg, mem, io, ube, data, bs, t, q, qb = row
    return (f"{ale} {bus:05x} {seg:2} {mem} {io} {ube} {data:04x} "
            f"{bs:4} {t:2} {q} {qb:02x}")


def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    ap.add_argument("form")
    ap.add_argument("idx", type=int)
    ap.add_argument("--core", default="ucore")
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--suite", default=str(ROOT / "tests" / "v30" / "v0.1"))
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=0)
    ap.add_argument("--rowtrace", action="store_true",
                    help="also print the MODEL's micro-row schedule")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()

    cases = json.load(gzip.open(Path(a.suite) / f"{a.form}.json.gz"))
    c = next(x for x in cases if x["idx"] == a.idx)

    binp = check_core.core_bin(a.core)
    with tempfile.TemporaryDirectory() as td:
        batch, outf = Path(td) / "b.txt", Path(td) / "o.txt"
        check_core.compose_batch([c], batch)
        r = subprocess.run([str(binp), f"+batch={batch}", f"+out={outf}",
                            f"+waits={a.waits}", f"+ce_div={check_core.CE_DIV_DEFAULT}", "+eutrace"],
                           cwd=ROOT, capture_output=True, text=True)
        eul = [ln for ln in r.stdout.splitlines() if ln.startswith("EU ")]
        sims = {}
        if not outf.exists():
            print("# TB produced no output (last 40 EU lines + tail):")
            for ln in eul[-40:]:
                print("  " + ln)
            print(r.stdout[-1500:] + r.stderr[-1500:])
        else:
            sims = check_core.parse_out(outf)
        eu_rows = eul

    got = None
    i0 = 0
    if sims.get(c["idx"]) is not None:
        got, _ev, j0, _i1 = check_core.build_rows_sim(
            sims[c["idx"]]["recs"], c["initial"]["queue"],
            n_close=check_core.n_fpops(c) - 1)
        i0 = j0 or 0

    rt = []
    if a.rowtrace:
        env = dict(os.environ, V30SIM_ROWTRACE="1")
        rr = subprocess.run([str(SIM), "timed-run", str(ROM),
                             f"--waits={a.waits}"],
                            input=json.dumps([c]).encode(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            env=env)
        rt = [ln for ln in rr.stderr.decode(errors="replace").splitlines()
              if ln.startswith("RT ")]

    exp = c["cycles"]
    exp = [list(x) for x in exp]
    print(f"# {a.form} idx {a.idx}: {c.get('name', '')}")
    print(f"# golden rows {len(exp)}   RTL rows "
          f"{len(got) if got else 'NONE'}   EU lines {len(eu_rows or [])}"
          f"   i0={i0}")
    first = None
    n = max(len(exp), len(got or []))
    for i in range(n):
        e = exp[i] if i < len(exp) else None
        g = got[i] if got and i < len(got) else None
        bad = ""
        if e and g:
            mm, _ = check_core.diff_rows([e], [g])
            if mm:
                bad = " <<< " + ",".join(check_core.COL_NAME[m[1]] for m in mm)
                if first is None:
                    first = i
        if a.lo and i < a.lo:
            continue
        if a.hi and i > a.hi:
            break
        if not a.full and first is not None and i > first + 8:
            break
        eu = (eu_rows[i0 + i] if eu_rows and i0 + i < len(eu_rows) else "")
        print(f"{i:3} G|{fmt(e)}|R|{fmt(g)}|{bad}")
        if eu:
            print(f"     {eu}")
    if rt:
        print("\n# MODEL row schedule (clock, ROM row, text)")
        for ln in rt:
            print("  " + ln)


if __name__ == "__main__":
    main()
