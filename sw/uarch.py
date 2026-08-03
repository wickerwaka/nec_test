#!/usr/bin/env python3
"""uarch -- which ARCHITECTURAL field diverges, per form.

check_core scores `arch` but only names the ROW columns.  This runs the same
comparison and reports the FINAL-REGISTER field histogram, which is what a
cycle-exact / arch-wrong form (family B) needs.

    uarch.py FORM[,FORM...] [--cases N] [--core ucore] [--show N]

Measurement tool, NOT a gate.
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
import check_core                                     # noqa: E402
from ucsim_check import flags_mask_of, load_meta      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms")
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--core", default="ucore")
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("--show", type=int, default=3)
    ap.add_argument("--suite", default=str(ROOT / "tests" / "v30" / "v0.1"))
    a = ap.parse_args()

    suite = Path(a.suite)
    meta = json.load(open(suite / "metadata.json"))
    binp = check_core.core_bin(a.core)
    forms = (sorted(p.name[:-8] for p in suite.glob("*.json.gz"))
             if a.forms == "all" else a.forms.split(","))
    for form in forms:
        fn = suite / f"{form}.json.gz"
        if not fn.exists():
            continue
        cases = json.load(gzip.open(fn))[:a.cases]
        base = form.split(".")[0]
        entry = meta["opcodes"].get(form) or meta["opcodes"].get(base, {})
        if "." in form and "reg" in entry:
            fm = entry["reg"].get(form.split(".", 1)[1], {}).get("flags-mask", 0xFFFF)
        else:
            fm = entry.get("flags-mask", 0xFFFF)
        with tempfile.TemporaryDirectory() as td:
            b, o = Path(td) / "b", Path(td) / "o"
            check_core.compose_batch(cases, b)
            r = subprocess.run([str(binp), f"+batch={b}", f"+out={o}",
                                f"+waits={a.waits}", "+ce_div=1"],
                               cwd=ROOT, capture_output=True, text=True)
            if not o.exists():
                print(f"{form}: SIM FAILED")
                continue
            sims = check_core.parse_out(o)
        hist = Counter()
        shown = 0
        nbad = 0
        for c in cases:
            s = sims.get(c["idx"])
            if s is None or s.get("final") is None:
                hist["no-final"] += 1
                continue
            exp = dict(c["initial"]["regs"])
            exp.update(c["final"]["regs"])
            got = s["final"]
            bad = []
            for k in check_core.REGS:
                if k == "flags":
                    if (exp[k] & fm) != (got[k] & fm):
                        bad.append(k)
                elif exp[k] != got[k]:
                    bad.append(k)
            if bad:
                nbad += 1
                hist["+".join(bad)] += 1
                if shown < a.show:
                    shown += 1
                    print(f"  {form} idx {c['idx']} ({c.get('name','')}): " +
                          ", ".join(f"{k} exp {exp[k]:04x} got {got[k]:04x}"
                                    for k in bad))
        print(f"{form}: {len(cases)-nbad}/{len(cases)} arch  " +
              " ".join(f"{k}x{v}" for k, v in hist.most_common(6)))


if __name__ == "__main__":
    main()
