#!/usr/bin/env python3
"""qdepth_probe -- U2 pass-3, C3: PROVE the completed-read store's bound.

The RTL renders the model's `rdq_` as two slots (`rdq0`/`rdq1` + `rdq_n`) and
its `rd_done_q_` as a 2-bit count, and pass 2 ASSERTED those bounds without
proving them.  This runs the MODEL -- which holds the truth -- over a golden
tranche with `V30SIM_QDEPTH=1` and reports, per form, the deepest either store
ever reached and the ROM row that pushed it.

    qdepth_probe.py [--suite tests/v30/v0.1] [--forms all|A,B] [--cases N]
                    [--waits N]

Measurement tool, NOT a gate.
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"

QD = re.compile(r"^QD (rdq|rd_done)=(\d+) upc=([0-9A-Fa-f]+) clk=(\d+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(ROOT / "tests" / "v30" / "v0.1"))
    ap.add_argument("--forms", default="all")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--waits", type=int, default=0)
    a = ap.parse_args()

    suite = Path(a.suite)
    if a.forms == "all":
        names = sorted(p.name.split(".json")[0] for p in suite.glob("*.json.gz"))
    else:
        names = [x.strip() for x in a.forms.split(",") if x.strip()]

    env = dict(os.environ, V30SIM_QDEPTH="1")
    worst = {}
    for n in names:
        p = suite / f"{n}.json.gz"
        if not p.exists():
            continue
        with gzip.open(p) as f:
            cases = json.load(f)
        if a.cases:
            cases = cases[:a.cases]
        r = subprocess.run(
            [str(SIM), "timed-run", str(ROM), f"--waits={a.waits}"],
            input=json.dumps(cases).encode(), stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, env=env)
        rec = {"rdq": (0, "", 0), "rd_done": (0, "", 0)}
        for line in r.stderr.decode(errors="replace").splitlines():
            m = QD.match(line)
            if m:
                which, d, upc, clk = m.group(1), int(m.group(2)), m.group(3), m.group(4)
                if d > rec[which][0]:
                    rec[which] = (d, upc, int(clk))
        worst[n] = rec
        if rec["rdq"][0] > 2 or rec["rd_done"][0] > 2:
            print(f"  !! {n}: rdq={rec['rdq']} rd_done={rec['rd_done']}")

    for which in ("rdq", "rd_done"):
        mx = max((v[which][0] for v in worst.values()), default=0)
        tops = sorted(k for k, v in worst.items() if v[which][0] == mx)
        print(f"{which}: max depth {mx} over {len(worst)} forms; "
              f"reached by {len(tops)} forms: {' '.join(tops[:24])}")
        for k in tops[:6]:
            print(f"    {k}: pushed at upc={worst[k][which][1]}")
    hist = {}
    for v in worst.values():
        hist[v["rdq"][0]] = hist.get(v["rdq"][0], 0) + 1
    print("rdq depth histogram (forms):",
          " ".join(f"{k}:{v}" for k, v in sorted(hist.items())))
    hist = {}
    for v in worst.values():
        hist[v["rd_done"][0]] = hist.get(v["rd_done"][0], 0) + 1
    print("rd_done depth histogram (forms):",
          " ".join(f"{k}:{v}" for k, v in sorted(hist.items())))


if __name__ == "__main__":
    main()
