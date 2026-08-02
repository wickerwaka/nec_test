#!/usr/bin/env python3
"""timed_probe -- first-divergence triage for the ucsim-t cycle ratchet.

Reuses sw/timed_gate.py wholesale (same runner, same check_core comparison
policy) and reports, per form, the failing cases grouped by their FIRST
divergent row -- (row index, column, golden cell, sim cell).  That grouping is
what turns "N cases fail" into "one mechanism is missing here".

  timed_probe.py --forms EB --top 8            # divergence classes
  timed_probe.py --forms EB --show 3           # side-by-side of 3 failures
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import check_core                       # noqa: E402
import timed_gate                       # noqa: E402
from ucsim_check import flags_mask_of, load_meta   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(timed_gate.V01))
    ap.add_argument("--forms", default="EB")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--only", default="", help="only show cases whose first "
                                               "divergence column matches this")
    args = ap.parse_args()

    suite = Path(args.suite)
    meta = load_meta(suite)
    for name, path in timed_gate.form_files(suite, args.forms):
        cases = json.load(gzip.open(path))
        if args.cases:
            cases = cases[:args.cases]
        _mask = flags_mask_of(name, meta)
        sims = timed_gate.run_form(cases, args.waits, False)
        classes = Counter()
        examples = defaultdict(list)
        nexact = 0
        for i, c in enumerate(cases):
            sim = sims.get(i)
            if sim is None:
                classes["<no-rows>"] += 1
                continue
            rows, _e, _a, _b = check_core.build_rows_sim(
                sim["recs"], c["initial"]["queue"],
                n_close=check_core.n_fpops(c) - 1)
            if rows is None:
                classes["<no-window>"] += 1
                continue
            mm, _masked = check_core.diff_rows(c["cycles"], rows)
            dc = check_core.dontcare_cells(c)
            if dc:
                mm = [m for m in mm if (m[0], m[1]) not in dc]
            if not mm:
                nexact += 1
                continue
            ri, ci = mm[0][0], mm[0][1]
            col = check_core.COL_NAME.get(ci, str(ci))
            g = c["cycles"][ri] if ri < len(c["cycles"]) else None
            s = rows[ri] if ri < len(rows) else None
            key = "row%+d/%d %s: %r -> %r" % (
                ri - len(c["cycles"]), len(c["cycles"]), col,
                (g[ci] if g else None), (s[ci] if s else None))
            classes[key] += 1
            examples[key].append(i)
        print("=== %s   exact %d/%d" % (name, nexact, len(cases)))
        for k, n in classes.most_common(args.top):
            print("  %5d  %-58s  e.g. %s" % (n, k, examples[k][:6]))
        if args.show:
            keys = [k for k in classes if not args.only or args.only in k]
            keys.sort(key=lambda k: -classes[k])
            for k in keys[:1]:
                for i in examples[k][:args.show]:
                    c = cases[i]
                    sim = sims[i]
                    rows, _e, _a, _b = check_core.build_rows_sim(
                        sim["recs"], c["initial"]["queue"],
                        n_close=check_core.n_fpops(c) - 1)
                    timed_gate.side_by_side(c, rows, "%s case %d" % (name, i))


if __name__ == "__main__":
    sys.exit(main())
