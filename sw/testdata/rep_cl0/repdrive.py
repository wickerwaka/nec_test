#!/usr/bin/env python3
"""Drive the ucore RTL TB (and the C++ model) with hand-built REP string cases.

READ-ONLY w.r.t. the repo: writes only into this scratchpad.
Composes hdl/tb/tb_v30_core.sv's batch format directly (mirroring
sw/check_core.compose_batch) and parses the `f` final-register line.
"""
import argparse
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
SCRATCH = Path(os.environ.get("REP_CL0_TMP")
                or tempfile.mkdtemp(prefix="rep_cl0_"))
REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "es", "cs", "ss", "ds", "ip", "flags"]

FILL = 2100

BIN_UCORE = ROOT / "hdl" / "tb" / "obj_dir_ucore" / "Vtb_v30_core"


def make_case(idx, opbytes, cx, si=0x0400, di=0x0400, flags=0xF052):
    regs = dict(ax=0x9090, cx=cx, dx=0x0000, bx=0x0000, sp=0x1000,
                bp=0x0000, si=si, di=di,
                es=0x3000, cs=0x1000, ss=0x4000, ds=0x2000,
                ip=0x0000, flags=flags)
    ram = []
    for i, b in enumerate(opbytes):
        ram.append([0x10000 + i, b])
    for i in range(len(opbytes), len(opbytes) + 8):
        ram.append([0x10000 + i, 0x90])
    for i in range(FILL):
        ram.append([0x20400 + i, 0x90])
        ram.append([0x30400 + i, 0x90])
    return {"idx": idx, "regs": regs, "ram": ram, "bytes": opbytes, "cx": cx}


def compose_batch(cases, path, nf=3, maxcyc_fn=None):
    with open(path, "w") as f:
        f.write(f"{len(cases):x}\n")
        for c in cases:
            r = c["regs"]
            f.write(f"{c['idx']:x}\n")
            f.write(" ".join(f"{r[k]:04x}" for k in REGS) + "\n")
            # empty injected queue; fetch pointer = ip + qlen
            f.write("0 00 00 00 00 00 00 " + f"{r['ip'] & 0xFFFF:04x}\n")
            f.write(f"{len(c['ram']):x}\n")
            for a, v in c["ram"]:
                f.write(f"{a & 0xFFFFF:05x} {v:02x}\n")
            maxcyc = maxcyc_fn(c) if maxcyc_fn else (16 * c["cx"] + 600)
            f.write(f"{maxcyc:x} {nf:x}\n")
            # evt mode 0, pin 0, addr 0, delay 0, hold 0, pins 0, iord FFFF, 0 iords
            f.write("0 0 00000 0 0 0 ffff 0\n")


def parse_out(path):
    out = {}
    cur = None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "=":
            cur = {"final": None, "nrec": 0}
            out[int(p[1])] = cur
        elif p[0] == "r":
            cur["nrec"] += 1
        elif p[0] == "f":
            cur["final"] = {k: int(v, 16) for k, v in zip(REGS, p[1:])}
    return out


def run_rtl(cases, tag, ce_div=4):
    batch = SCRATCH / f"batch_{tag}.txt"
    outf = SCRATCH / f"out_{tag}.txt"
    compose_batch(cases, batch)
    cmd = [str(BIN_UCORE), f"+batch={batch}", f"+out={outf}",
           f"+ce_div={ce_div}"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT),
                       timeout=3600)
    if "DONE" not in p.stdout:
        print("RTL STDOUT:", p.stdout[-3000:], file=sys.stderr)
        print("RTL STDERR:", p.stderr[-3000:], file=sys.stderr)
        raise SystemExit("RTL run did not complete")
    return parse_out(outf), p


def run_model(cases, tag):
    """Drive sim/build/v30sim the same way check_core's sibling tools do."""
    raise NotImplementedError


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ce-div", type=int, default=4)
    ap.add_argument("--forms", default="F3A4,F3A5")
    ap.add_argument("--cx", default="3,255,256,257,512,1000")
    args = ap.parse_args()

    FORMS = {
        "F3A4": [0xF3, 0xA4],  # REP MOVSB
        "F3A5": [0xF3, 0xA5],  # REP MOVSW
        "F3AA": [0xF3, 0xAA],  # REP STOSB
        "F3AB": [0xF3, 0xAB],  # REP STOSW
        "F3AC": [0xF3, 0xAC],  # REP LODSB
        "F3AD": [0xF3, 0xAD],  # REP LODSW
        "F3A6": [0xF3, 0xA6],  # REPE CMPSB
        "F3A7": [0xF3, 0xA7],  # REPE CMPSW
        "F3AE": [0xF3, 0xAE],  # REPE SCASB
        "F3AF": [0xF3, 0xAF],  # REPE SCASW
        "F36C": [0xF3, 0x6C],  # REP INSB
        "F36D": [0xF3, 0x6D],  # REP INSW
        "F36E": [0xF3, 0x6E],  # REP OUTSB
        "F36F": [0xF3, 0x6F],  # REP OUTSW
    }
    forms = args.forms.split(",")
    cxs = [int(x, 0) for x in args.cx.split(",")]

    cases = []
    meta = {}
    idx = 0
    for fm in forms:
        for cx in cxs:
            c = make_case(idx, FORMS[fm], cx)
            cases.append(c)
            meta[idx] = (fm, cx)
            idx += 1

    res, _ = run_rtl(cases, f"d{args.ce_div}", ce_div=args.ce_div)
    rows = []
    print(f"{'form':6} {'CXin':>6} {'CXfin':>6} {'SI':>6} {'DI':>6} "
          f"{'IP':>5} {'iters(SI)':>9} {'closed':>6}")
    for i, c in enumerate(cases):
        fm, cx = meta[i]
        f = res.get(i, {}).get("final")
        if f is None:
            print(f"{fm:6} {cx:6} {'NO-FINAL':>6}")
            continue
        step = 2 if FORMS[fm][1] & 1 else 1
        iters = ((f["si"] - 0x0400) & 0xFFFF) // step
        # LODS/SCAS/CMPS/MOVS all move SI; STOS moves only DI
        if FORMS[fm][1] in (0xAA, 0xAB):
            iters = ((f["di"] - 0x0400) & 0xFFFF) // step
        closed = "yes" if f["ip"] == 2 else f"ip={f['ip']:04x}"
        print(f"{fm:6} {cx:6} {f['cx']:6} {f['si']:6} {f['di']:6} "
              f"{f['ip']:5} {iters:9} {closed:>6}")
        rows.append(dict(form=fm, cx_in=cx, final=f, iters=iters))
    json.dump(rows, open(SCRATCH / f"rtl_rows_d{args.ce_div}.json", "w"),
              indent=1)
