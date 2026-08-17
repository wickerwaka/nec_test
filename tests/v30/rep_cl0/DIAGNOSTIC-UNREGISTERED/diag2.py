#!/usr/bin/env python3
"""UNREGISTERED DIAGNOSTIC pass 2 -- read-only socket captures at the rig's
maximum cap (4096), to quantify where the cell sits against the buffer depth.
Socket only, use_core=False, waits 0, no flash, no suite directory written."""
import hashlib
import json
import random
import sys
sys.path.insert(0, "/home/wickerwaka/src/nec_test/sw")
import emit_suite as es
import testimage
import s13_board as s13

HOST = "root@mister-nec"
OUT = "/tmp/claude-1000/-home-wickerwaka-src-nec-test/" \
      "e60a38a6-0990-48b8-8214-b56406bae3db/scratchpad"


def build(op, idx):
    spec = es.OPCODES[op]
    rng = random.Random(f"rep-cl0-rc1/{op}/{idx}")
    fcx, fdf = es._forced_cell(idx, [255, 256, 257], [0, 1])
    case = es.gen_case(spec, rng, force_cx=fcx, force_df=fdf)
    nec_regs = {es.INTEL2NEC[k]: v for k, v in case["regs"].items()}
    ram = list(case["ram"])
    ivt = case["ivt"]
    pn = 2 if idx % 2 == 1 else 0
    run_instr = es.PRELOAD_BYTES * pn + case["instr"] if pn else case["instr"]
    if pn:
        nec_regs["PC"] = (nec_regs["PC"] - 2 * pn) & 0xFFFF
    nip = case.get("next_ip")
    if nip is None:
        nip = (case["regs"]["ip"] + len(case["instr"])) & 0xFFFF
    ccs = case.get("next_cs") or case["regs"]["cs"]
    cl = ((ccs << 4) + nip) & 0xFFFF
    if ivt:
        h = bytes([0xEA, cl & 0xFF, cl >> 8, 0x00, 0x00])
        ram += [(es.HANDLER_OFF + k, b) for k, b in enumerate(h)]
    image, meta = testimage.compose(regs=nec_regs, instr=run_instr,
                                    ram=ram, ivt=ivt)
    return case, image, meta


print("div guard:", s13.div_guard("diag2-open"))
summary = []
for op, idx in (("F3A4", 0), ("F3A5", 0), ("F3A5", 2)):
    case, image, meta = build(op, idx)
    r = case["regs"]
    recs = es._capture(image, HOST, f"dg{op}{idx}", waits=0,
                       iord=case.get("iord"), iords=case.get("iords"), cap=4096)
    raw = json.dumps(recs, sort_keys=True, separators=(",", ":")).encode()
    sha = hashlib.sha256(raw).hexdigest()
    open(f"{OUT}/diag_{op}_{idx}.json", "wb").write(raw)
    anchor = meta["anchor_linear"]
    t1 = [(i, x.get("ad_addr"), x.get("bs_early")) for i, x in enumerate(recs)
          if x.get("t") == 1]
    i_anchor = next((i for i, a, b in t1 if a == anchor), None)
    memw = [i for i, a, b in t1 if b == 6]
    memr = [i for i, a, b in t1 if b == 5]
    iow = [i for i, a, b in t1 if b == 2]          # IOW = port writes
    done = [i for i, a, b in t1 if b == 2 and a is not None and
            (a & 0xFF) == 0xFC]
    d = dict(op=op, idx=idx, cx=r["cx"], df=(r["flags"] >> 10) & 1,
             si=r["si"], di=r["di"],
             si_par="odd" if r["si"] & 1 else "even",
             di_par="odd" if r["di"] & 1 else "even",
             n_records=len(recs), anchor_rec=i_anchor,
             n_memw=len(memw), n_memr=len(memr), n_iow=len(iow),
             done_rec=(done[-1] if done else None),
             last_rec=t1[-1][0] if t1 else None, sha256=sha)
    summary.append(d)
    print(json.dumps(d))
print("div guard:", s13.div_guard("diag2-close"))
json.dump(summary, open(f"{OUT}/diag2_summary.json", "w"), indent=1)
