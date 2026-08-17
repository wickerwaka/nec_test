#!/usr/bin/env python3
"""Drive sim/build/v30sim with the SAME hand-built REP cases as repdrive.py."""
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
SIM = ROOT / "sim" / "build" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "es", "cs", "ss", "ds", "ip", "flags"]

FILL = 2100

FORMS = {
    "F3A4": [0xF3, 0xA4], "F3A5": [0xF3, 0xA5],
    "F3AA": [0xF3, 0xAA], "F3AB": [0xF3, 0xAB],
    "F3AC": [0xF3, 0xAC], "F3AD": [0xF3, 0xAD],
    "F3A6": [0xF3, 0xA6], "F3A7": [0xF3, 0xA7],
    "F3AE": [0xF3, 0xAE], "F3AF": [0xF3, 0xAF],
    "F36C": [0xF3, 0x6C], "F36D": [0xF3, 0x6D],
    "F36E": [0xF3, 0x6E], "F36F": [0xF3, 0x6F],
}


def make_case(name, opbytes, cx):
    ram = [[0x10000 + i, b] for i, b in enumerate(opbytes)]
    ram += [[0x10000 + i, 0x90] for i in range(len(opbytes), len(opbytes) + 8)]
    # explicit 0x90 fill of the source and destination string regions so the
    # two engines see IDENTICAL memory (their unset-memory defaults differ:
    # the TB fills 0x90, the model fills 0x00).
    for i in range(FILL):
        ram.append([0x20400 + i, 0x90])
        ram.append([0x30400 + i, 0x90])
    return {
        "name": name,
        "bytes": opbytes,
        "initial": {
            "regs": dict(ax=0x9090, cx=cx, dx=0x0000, bx=0x0000, sp=0x1000,
                         bp=0x0000, si=0x0400, di=0x0400,
                         cs=0x1000, ip=0x0000, ds=0x2000, es=0x3000,
                         ss=0x4000, flags=0xF052),
            "ram": ram,
            "queue": [],
        },
        "final": {"regs": {}, "ram": [], "queue": []},
    }


if __name__ == "__main__":
    forms = sys.argv[1].split(",")
    cxs = [int(x, 0) for x in sys.argv[2].split(",")]
    cases, meta = [], []
    for fm in forms:
        for cx in cxs:
            cases.append(make_case(f"{fm} cx={cx}", FORMS[fm], cx))
            meta.append((fm, cx))
    p = subprocess.run([str(SIM), "run", str(ROM), "--emit-final"],
                       input=json.dumps(cases).encode(),
                       stdout=subprocess.PIPE)
    recs = {}
    for line in p.stdout.decode().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "i" in r:
            recs[r["i"]] = r
    if not recs:
        print("NO RECORDS; raw output follows:")
        print(p.stdout.decode()[:2000])
        raise SystemExit(1)
    print(json.dumps(recs[0])[:600])
    print()
    print(f"{'form':6} {'CXin':>6} {'CXfin':>6} {'SI':>6} {'DI':>6} {'IP':>5}")
    rows = []
    for i, (fm, cx) in enumerate(meta):
        r = recs.get(i)
        g = dict(zip(REGS, r["r"]))
        print(f"{fm:6} {cx:6} {g.get('cx'):>6} {g.get('si'):>6} "
              f"{g.get('di'):>6} {g.get('ip'):>5}")
        rows.append(dict(form=fm, cx_in=cx, final=g))
    json.dump(rows, open(Path(os.environ.get("REP_CL0_TMP") or
                         tempfile.mkdtemp(prefix="rep_cl0_")) / "model_rows.json", "w"),
              indent=1)
