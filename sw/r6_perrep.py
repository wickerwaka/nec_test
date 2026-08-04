#!/usr/bin/env python3
"""r6_perrep -- gap R6: BANK THE PER-REPETITION ROWS the sweeps never kept.

THE GAP, verbatim from `ucore_gaps_2026-08-04.md` §R.6:

  `HLT.INT_w2_d0`'s `stable_identical: false` is **NOT verified** as the same
  pad artefact as `HLT.INT_w0_d0` -- `s13/p1b-ahsweep` banks only ONE rows
  stream per cell beside five per-rep raw shas, so the other four repetitions'
  keys cannot be recomputed.  Corroboration exists offline but **verification
  needs per-rep rows banked, which needs the board.**

`s10_board.reps_capture` keeps `rows0` and, per repetition, only `stable_key`
and `raw_sha`.  So a cell that is not stable cannot be DIAGNOSED from the bank:
the shas say the streams differ and nothing says WHERE.  This probe captures
the same cells with the same driver and banks EVERY repetition's full rows.

THE STANDING CAVEAT, CARRIED: `stable_key` changed at `ucsim_t_provenance.md`
§26.1 (`ube_n` gated to T1) and keys stored in manifests BEFORE that change are
internally valid and **NOT comparable across it**.  This probe therefore
compares only keys IT computes, on rows IT captured, in one session.

THE CELLS.  Every cell in the banked sweeps whose manifest records
`stable_identical: false`, plus `HLT.INT_w0_d0` which §26.1 diagnosed at 50
repetitions and which is R6's named reference:

    s10/s2-hltsweep   HLT.INT  w0 d0      the §26.1 reference cell
    s13/p1b-ahsweep   HLT.INT  w2 d0      the cell R6 names
    s10/s1-tranche    INT.90 / NMI.90 / HLT.INT  w1 d0

WHAT IS MEASURED, not assumed: for each cell, over `--reps` repetitions, the
set of distinct `stable_key`s and distinct raw streams, and -- the thing the
gap is about -- the exact ROWS and COLUMNS on which any two repetitions differ.
§26.1's finding for `HLT.INT_w0_d0` was that every difference lay on rows 0..8,
i.e. BEFORE THE FIRST T1, before the part has driven the bus once, in the
MULTIPLEXED pads only (`ube_n`, `ad_addr`, `ad_data`, `ps`) with the DEDICATED
pins (`t`, `bs_early`, `qs`, `lock_n`) differing nowhere.  That is the pad
artefact's signature and it is what `HLT.INT_w2_d0` is being checked against.

Board discipline: socket only (`use_core=False`), `div_guard` recorded, the
divider PINNED at `DIV_OF_RECORD`.
"""
import argparse
import gzip
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                    # noqa: E402
from s10_board import (capture, stable_key, DIV_OF_RECORD,  # noqa: E402
                       _evt_image, HOST)
from s13_board import div_guard                            # noqa: E402

OUT = ROOT / "sw" / "testdata" / "r6-perrep"

# (name, form, waits, delay, the manifest the cell came from)
CELLS = [
    ("HLT.INT_w0_d0", "HLT.INT", 0, 0, "s10/s2-hltsweep"),
    ("HLT.INT_w2_d0", "HLT.INT", 2, 0, "s13/p1b-ahsweep"),
    ("INT.90_w1_d0", "INT.90", 1, 0, "s10/s1-tranche"),
    ("NMI.90_w1_d0", "NMI.90", 1, 0, "s10/s1-tranche"),
    ("HLT.INT_w1_d0", "HLT.INT", 1, 0, "s10/s1-tranche"),
]

# the two classes §26.1 separates.  DEDICATED pins have their own package pin;
# MULTIPLEXED pads share one and therefore HOLD the previous driver's value.
DEDICATED = ("t", "bs_early", "qs", "lock_n", "rst")
MULTIPLEXED = ("ube_n", "ad_addr", "ad_data", "ps")


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    man = {"probe": "R6 -- per-repetition rows for the unstable sweep cells",
           "spec": "docs/notes/ucore_gaps_2026-08-04.md §R.6",
           "use_core": False, "host": a.host, "reps": a.reps,
           "div": DIV_OF_RECORD,
           "caveat": "stable_key changed at ucsim_t_provenance.md §26.1; the "
                     "keys here are computed in this session on rows captured "
                     "in this session and are NOT compared to any manifest key",
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cells": {}}
    man["div_guard"] = div_guard("r6-perrep")
    for name, form, waits, delay, src in CELLS:
        spec = es.EVT_FORMS[form]
        # the sweeps' OWN fixed seed -- s13_board.py:149 reuses s10's, so the
        # program is identical across w0/w1/w2/w3 and the axis is the delay.
        rng = random.Random("v30-s10-hlt/%s" % form)
        case = es.gen_evt_case(spec, rng)
        case["delay"] = delay
        image, evt, _ = _evt_image(spec, case)
        keys, shas, fires = [], [], []
        d = OUT / name
        d.mkdir(exist_ok=True)
        for i in range(a.reps):
            rows, raw, sha, fired = capture(image, waits=waits,
                                            div=DIV_OF_RECORD, evt=evt,
                                            tag="r6")
            keys.append(stable_key(rows))
            shas.append(sha)
            fires.append(bool(fired))
            with gzip.open(d / f"rep{i:02d}.rows.json.gz", "wt") as f:
                json.dump(rows, f, separators=(",", ":"))
            with gzip.open(d / f"rep{i:02d}.raw.hex.gz", "wt") as f:
                f.write("\n".join(raw) + "\n")
        man["cells"][name] = {
            "form": form, "waits": waits, "delay": delay, "source": src,
            "reps": a.reps, "stable_key": keys,
            "n_distinct_keys": len(set(keys)),
            "stable_identical": len(set(keys)) == 1,
            "raw_sha": shas, "n_distinct_raw": len(set(shas)),
            "evt_fired": fires,
        }
        print(f"  {name}: {a.reps} reps, {len(set(keys))} distinct KEYS, "
              f"{len(set(shas))} distinct RAW streams", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"-> {OUT/'manifest.json'}")
    return 0


def _rows(name, i):
    with gzip.open(OUT / name / f"rep{i:02d}.rows.json.gz", "rt") as f:
        return json.load(f)


def cmd_analyse(a):
    man = json.loads((OUT / "manifest.json").read_bytes())
    report = {}
    for name, cell in man["cells"].items():
        reps = cell["reps"]
        base = _rows(name, 0)
        first_t1 = next((i for i, r in enumerate(base) if r["t"] == 1), None)
        diff_rows_idx, diff_cols = set(), Counter()
        for i in range(1, reps):
            other = _rows(name, i)
            n = min(len(base), len(other))
            for j in range(n):
                for c in set(base[j]) | set(other[j]):
                    if c == "idx":
                        continue
                    if base[j].get(c) != other[j].get(c):
                        diff_rows_idx.add(j)
                        diff_cols[c] += 1
        ded = sorted(c for c in diff_cols if c in DEDICATED)
        mux = sorted(c for c in diff_cols if c in MULTIPLEXED)
        other_cols = sorted(c for c in diff_cols
                            if c not in DEDICATED and c not in MULTIPLEXED)
        after = sorted(j for j in diff_rows_idx
                       if first_t1 is not None and j >= first_t1)
        report[name] = {
            "reps": reps, "n_distinct_keys": cell["n_distinct_keys"],
            "n_distinct_raw": cell["n_distinct_raw"],
            "stable_identical": cell["stable_identical"],
            "first_t1_row": first_t1,
            "n_diff_rows": len(diff_rows_idx),
            "diff_rows": sorted(diff_rows_idx)[:40],
            "diff_rows_at_or_after_first_t1": after[:40],
            "n_diff_rows_at_or_after_first_t1": len(after),
            "cols_dedicated": ded, "cols_multiplexed": mux,
            "cols_other": other_cols,
            "col_counts": dict(diff_cols),
            # the §26.1 signature, stated as a predicate over the artifact
            "pad_artefact_signature": (not ded and not other_cols
                                       and not after),
        }
        print(f"=== {name}  ({cell['source']}, w{cell['waits']} d{cell['delay']})")
        print(f"    keys distinct {cell['n_distinct_keys']}/{reps}   raw "
              f"distinct {cell['n_distinct_raw']}/{reps}   "
              f"stable_identical {cell['stable_identical']}")
        print(f"    first T1 at row {first_t1}; differing rows "
              f"{sorted(diff_rows_idx)[:20]}"
              f"{' ...' if len(diff_rows_idx) > 20 else ''}")
        print(f"    rows at/after the first T1 that differ: {len(after)}")
        print(f"    columns: dedicated={ded or '[]'}  multiplexed={mux or '[]'}"
              f"  other={other_cols or '[]'}")
        print(f"    §26.1 PAD-ARTEFACT SIGNATURE: "
              f"{'YES' if report[name]['pad_artefact_signature'] else 'NO'}")
    (OUT / "analysis.json").write_text(json.dumps(report, indent=1) + "\n")
    ref = report.get("HLT.INT_w0_d0", {})
    tgt = report.get("HLT.INT_w2_d0", {})
    if ref and tgt:
        same = (ref["pad_artefact_signature"] and tgt["pad_artefact_signature"])
        print("\n=== R6's QUESTION ===")
        print("  HLT.INT_w2_d0's instability is the SAME pad artefact as "
              f"HLT.INT_w0_d0's: {'VERIFIED' if same else 'NOT VERIFIED'}")
        if not same:
            print("  (reported as measured -- a cell whose differences reach "
                  "a dedicated pin or a row at/after the first T1 is NOT the "
                  "§26.1 artefact and is a finding)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    c = s.add_parser("capture")
    c.add_argument("--host", default=HOST)
    c.add_argument("--reps", type=int, default=10)
    c.set_defaults(fn=cmd_capture)
    v = s.add_parser("analyse")
    v.set_defaults(fn=cmd_analyse)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
