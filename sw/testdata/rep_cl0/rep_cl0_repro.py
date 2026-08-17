#!/usr/bin/env python3
"""MINIMAL REPRODUCER -- REP byte-string ops perform ZERO iterations when CL==0.

    python3 rep_cl0_repro.py          # from the repo root

The rule, measured:  a REP-prefixed BYTE string op (A4 A6 AA AC AE) with
CX != 0 and (CX & 0xFF) == 0 retires having done NOTHING -- CX, SI and DI
unchanged, IP advanced past the prefix.  The WORD forms (A5 A7 AB AD AF) are
correct at the same counts.

Mechanism: the REP entry test is the microcode row pair

    0094  CX -> COUNT   CX -> tmpb        ALU PASS tmpb
    0095  SIGMA -> NULL                   ALU ADD  tmpc     <- flags latched
    0096  dir*sz -> tmpc                  JMP Z 7           <- skips the loop

and `docs/V20UC.TXT` line 186 shows that bank is `001.1010010?.00 <rep> A4,A5`
-- ONE bank serving BOTH widths, the `?` being the W bit.  The model gives that
shared row its flag width from the INSTRUCTION (`sim/exec_impl.h:1284`,
`nl.byte = m_.op8;`), so the byte form tests only CL:

    A4 (op8=1) CX=0x0100 -> SIGMA=0x0100 ST=0x0044  Z SET   -> JMP taken, skip
    A5 (op8=0) CX=0x0100 -> SIGMA=0x0100 ST=0x0004  Z CLEAR -> loop runs

Same row, same SIGMA, different Z.  Only `op8` differs.
"""
import json, subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[0]
if not (ROOT / "sim/build/v30sim").exists():
    ROOT = pathlib.Path("/home/wickerwaka/src/nec_test")
SIM, ROM = ROOT / "sim/build/v30sim", ROOT / "docs/V20BITS.TXT"
REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "es", "cs", "ss", "ds", "ip", "flags"]
CS, DS, ES, SS, BASE = 0x1000, 0x2000, 0x3000, 0x4000, 0x0400


def case(op, cx):
    code = CS << 4
    return {"name": f"{op:02X}/{cx}", "bytes": [0xF3, op],
            "initial": {"regs": {"ax": 0, "cx": cx, "dx": 0, "bx": 0,
                                 "sp": 0x1000, "bp": 0, "si": BASE, "di": BASE,
                                 "cs": CS, "ip": 0, "ds": DS, "es": ES,
                                 "ss": SS, "flags": 0xF052},
                        "ram": [[code, 0xF3], [code + 1, op]] +
                               [[code + 2 + i, 0x90] for i in range(8)],
                        "queue": []},
            "final": {"regs": {}, "ram": [], "queue": []}}


def run(cases):
    p = subprocess.run([str(SIM), "run", str(ROM), "--emit-final"],
                       input=json.dumps(cases).encode(), stdout=subprocess.PIPE)
    out = [None] * len(cases)
    for ln in p.stdout.decode().splitlines():
        if ln:
            r = json.loads(ln)
            out[r["i"]] = r
    return out


FORMS = [(0xA4, "MOVSB", 1), (0xA5, "MOVSW", 2), (0xAA, "STOSB", 1),
         (0xAB, "STOSW", 2), (0xAC, "LODSB", 1), (0xAD, "LODSW", 2)]
CXS = [3, 255, 256, 257, 512, 1000, 4096]

cases, meta = [], []
for op, nm, w in FORMS:
    for cx in CXS:
        cases.append(case(op, cx))
        meta.append((nm, w, cx))

res, fails = run(cases), 0
print(f"{'form':>7} {'w':>2} |" + "".join(f"{c:>8}" for c in CXS))
print("-" * (12 + 8 * len(CXS)))
row, cur = [], None
for (nm, w, cx), r in zip(meta, res):
    if cur != nm:
        if row:
            print(row.pop(0) + "".join(row))
        row, cur = [f"{nm:>7} {w:>2} |"], nm
    g = dict(zip(REGS, r["r"]))
    ok = g["cx"] == 0
    fails += not ok
    row.append(f"{'ok' if ok else 'SKIP':>8}")
print(row.pop(0) + "".join(row))

print(f"\n{fails} failing cells.  Every failure has (CX & 0xFF) == 0 and a "
      f"BYTE form.")
sys.exit(1 if fails else 0)
