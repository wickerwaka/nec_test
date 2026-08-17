#!/usr/bin/env python3
"""UNREGISTERED DIAGNOSTIC pass 3 -- per-case capture-length sweep over all 24
cell images at the rig's MAXIMUM cap (4096 = CAP_RECORDS).  Read-only: socket,
use_core=False, waits 0, no flash, and NOTHING is written into tests/v30.

This is DIAGNOSIS of why the registered run stopped.  It is NOT the registered
cell (that is `emit_suite.py emit`), and no prediction is scored from it."""
import hashlib
import json
import random
import sys
import time
sys.path.insert(0, "/home/wickerwaka/src/nec_test/sw")
import emit_suite as es
import testimage
import s13_board as s13
from v30run import parse_result

HOST = "root@mister-nec"
OUT = "/tmp/claude-1000/-home-wickerwaka-src-nec-test/" \
      "e60a38a6-0990-48b8-8214-b56406bae3db/scratchpad"


def build(op, idx):
    spec = es.OPCODES[op]
    rng = random.Random(f"rep-cl0-rc1/{op}/{idx}")
    fcx, fdf = es._forced_cell(idx, [255, 256, 257], [0, 1])
    case = es.gen_case(spec, rng, force_cx=fcx, force_df=fdf)
    nec = {es.INTEL2NEC[k]: v for k, v in case["regs"].items()}
    ram = list(case["ram"])
    ivt = case["ivt"]
    pn = 2 if idx % 2 == 1 else 0
    instr = case["instr"]
    if pn:
        nec["PC"] = (nec["PC"] - 2 * pn) & 0xFFFF
        instr = es.PRELOAD_BYTES * pn + instr
    nip = case.get("next_ip")
    if nip is None:
        nip = (case["regs"]["ip"] + len(case["instr"])) & 0xFFFF
    ccs = case.get("next_cs") or case["regs"]["cs"]
    cl = ((ccs << 4) + nip) & 0xFFFF
    if ivt:
        h = bytes([0xEA, cl & 0xFF, cl >> 8, 0x00, 0x00])
        ram += [(es.HANDLER_OFF + k, b) for k, b in enumerate(h)]
    image, meta = testimage.compose(regs=nec, instr=instr, ram=ram, ivt=ivt)
    return case, image, meta, pn


print("div guard:", s13.div_guard("diag3-open")["state"])
rows = []
for op in ("F3A4", "F3A5"):
    for idx in range(12):
        case, image, meta, pn = build(op, idx)
        r = case["regs"]
        t0 = time.time()
        recs = es._capture(image, HOST, f"d3{op}{idx}", waits=0,
                           iord=case.get("iord"), iords=case.get("iords"),
                           cap=4096)
        raw = json.dumps(recs, sort_keys=True, separators=(",", ":")).encode()
        sha = hashlib.sha256(raw).hexdigest()
        t1s = [(i, x.get("ad_addr"), x.get("bs_early")) for i, x in
               enumerate(recs) if x.get("t") == 1]
        done = [i for i, a, b in t1s
                if b == 2 and a is not None and (a & 0xFF) == 0xFC]
        try:
            res = parse_result(recs, meta)
            ok, err = True, ""
            cxf = res["regs"].get("CW")
        except Exception as e:                      # noqa: BLE001
            ok, err, cxf = False, f"{type(e).__name__}: {e}", None
        d = dict(op=op, idx=idx, cx=r["cx"], df=(r["flags"] >> 10) & 1,
                 preload=pn,
                 align=("odd" if r["si"] & 1 else "even") + "/" +
                       ("odd" if r["di"] & 1 else "even"),
                 n_records=len(recs),
                 done_rec=(done[-1] if done else None),
                 last_used=(t1s[-1][0] if t1s else None),
                 n_memw=sum(1 for _, _, b in t1s if b == 6),
                 n_memr=sum(1 for _, _, b in t1s if b == 5),
                 parse_ok=ok, err=err[:110], cx_final=cxf,
                 secs=round(time.time() - t0, 2), sha256=sha)
        rows.append(d)
        print(f"{op} idx{idx:2d} cx={d['cx']} df={d['df']} pl={pn} "
              f"{d['align']:9s} recs={d['n_records']} done@{d['done_rec']} "
              f"memw={d['n_memw']} memr={d['n_memr']} "
              f"parse={'OK' if ok else 'FAIL'} cxf={cxf} {d['err']}",
              flush=True)
print("div guard:", s13.div_guard("diag3-close")["state"])
json.dump(rows, open(f"{OUT}/diag3_summary.json", "w"), indent=1)
