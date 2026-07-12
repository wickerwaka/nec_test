#!/usr/bin/env python3
"""exp_biu - Campaign 1: BIU characterization experiments.

Each experiment is a designed program run through the load/store machinery
with the analysis reading the per-cycle capture directly (fetch completions
from CODE T4s, queue pops from QS ops). Results feed docs/facts/biu_model.md.

Usage:
  exp_biu.py queue-limit [--host ...]     # experiment 1: depth + thresholds
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                          # noqa: E402
from v30run import run_test                           # noqa: E402

T_NAMES = {0: "TI", 1: "T1", 2: "T2", 3: "T3", 4: "TW", 5: "T4"}
Q_NAMES = {0: "-", 1: "F", 2: "E", 3: "S"}


def queue_timeline(recs, meta, until_port=0xFE):
    """Per-cycle queue events from the test anchor to the store anchor.

    Returns a list of dicts: cycle index, event kind, running depth, and
    the state needed to spot BIU stalls (cycles with no bus activity while
    instructions execute).
    """
    # find anchor: first T1 CODE at the anchor linear address
    events = []
    depth = 0
    started = False
    fetch_pend = None
    for r in recs:
        t = r["t"]
        bs = r["bs_early"]
        if not started:
            if t == 1 and r["ad_addr"] == meta["anchor_linear"] and bs == 4:
                started = True
            else:
                continue
        # stop at the first IOW touching the store port
        if bs == 2 and t == 1 and (r["ad_addr"] & 0xFFFF) == until_port:
            break
        ev = {"idx": r["idx"], "t": T_NAMES.get(t, "?"), "bs": bs,
              "q": Q_NAMES[r["qs"]], "addr": r["ad_addr"]}
        if t == 1 and bs == 4:                       # CODE fetch begins
            fetch_pend = 2 if (r["ad_addr"] & 1) == 0 and not r["ube_n"] else 1
        if t == 5 and fetch_pend:                    # fetch completes at T4
            depth += fetch_pend
            ev["fetch_done"] = fetch_pend
            fetch_pend = None
        if r["qs"] in (1, 3):                        # F or S pop
            depth = max(depth - 1, 0)
        elif r["qs"] == 2:                           # flush
            depth = 0
        ev["depth"] = depth
        events.append(ev)
    return events


def analyze_queue_limit(events):
    """Find the BIU stall: the gap between CODE fetches while the EU is
    busy. Depth at the last completed fetch before the gap ~= capacity;
    depth when the next fetch STARTS ~= capacity - refill threshold."""
    fetches = [e for e in events if "fetch_done" in e]
    stalls = []
    for a, b in zip(fetches, fetches[1:]):
        gap = b["idx"] - a["idx"]
        if gap > 6:   # more than a back-to-back 4-cycle cadence
            # depth at the T1 of the resuming fetch
            resume_t1 = next((e for e in events
                              if e["idx"] > a["idx"] and e["t"] == "T1"
                              and e["bs"] == 4), None)
            stalls.append({
                "stall_after_idx": a["idx"],
                "depth_at_stall": a["depth"],
                "gap_cycles": gap,
                "depth_at_resume": resume_t1["depth"] if resume_t1 else None,
            })
    return fetches, stalls


def cmd_queue_limit(host):
    a = Assembler()
    # DIVU CW with DW:AW / CW; several operand sets to check timing
    # data-dependence at the same time
    cases = [
        {"AW": 0xFFFF, "DW": 0x0000, "CW": 0x0001},
        {"AW": 0x0001, "DW": 0x0000, "CW": 0x0001},
        {"AW": 0x5678, "DW": 0x1234, "CW": 0xFFFF},
        {"AW": 0x0000, "DW": 0x0000, "CW": 0x8000},
    ]
    divu = a.assemble("DIVU CW")
    print(f"DIVU CW = {divu.hex(' ')}")
    for i, regs in enumerate(cases):
        regs = dict(regs, PS=0x0000, PC=0x0500)
        res = run_test(regs=regs, instr=divu, host=host, tag=f"qlim{i}")
        events = queue_timeline(res["recs"], res["meta"])
        fetches, stalls = analyze_queue_limit(events)

        # DIV execution time: first F pop (the DIV byte) to the F pop that
        # follows its completion (first stub instruction)
        fpops = [e for e in events if e["q"] == "F"]
        div_time = fpops[1]["idx"] - fpops[0]["idx"] if len(fpops) > 1 else None

        max_depth = max((e["depth"] for e in events), default=0)
        print(f"\ncase {i}: DW:AW={regs['DW']:04x}:{regs['AW']:04x} "
              f"/ CW={regs['CW']:04x} -> AW={res['regs']['AW']:04x} "
              f"DW={res['regs']['DW']:04x}")
        print(f"  DIV F-to-next-F: {div_time} cycles | max queue depth: "
              f"{max_depth} | fetches in window: {len(fetches)}")
        for s in stalls:
            print(f"  BIU stall: depth {s['depth_at_stall']} for "
                  f"{s['gap_cycles']} cycles, resumed at depth "
                  f"{s['depth_at_resume']}")
        if i == 0:
            print("  timeline (cycle t bs q depth):")
            for e in events[:60]:
                fd = f" +{e['fetch_done']}" if "fetch_done" in e else ""
                print(f"    {e['idx']:>4} {e['t']:<2} bs={e['bs']} "
                      f"{e['q']} d={e['depth']}{fd}")
    return 0


#----------------------------------------------------------------------------
# exp 2: flush-to-refetch penalty, even vs odd jump targets
# (also answers the odd-target first-fetch width, exp 6a)
#----------------------------------------------------------------------------

def cmd_flush(host):
    a = Assembler()
    for parity, pad in (("even", 2), ("odd", 3)):
        # BR skips `pad` bytes; target parity = anchor(even 0x500)+2+pad
        src = f"    BR t\n" + "    NOP\n" * pad + "t:\n" + "    NOP\n" * 8
        code = a.assemble(src, org=0x0500)
        target = 0x0500 + 2 + pad
        assert (target & 1) == (0 if parity == "even" else 1)
        res = run_test(regs={"PS": 0, "PC": 0x0500}, instr=code, host=host,
                       tag=f"flush{parity}")
        ev = queue_timeline(res["recs"], res["meta"])
        eop = next(e for e in ev if e["q"] == "E")
        t1 = next(e for e in ev if e["idx"] > eop["idx"] and e["t"] == "T1"
                  and e["bs"] == 4)
        # fetch width of the first post-flush fetch
        rec = next(r for r in res["recs"] if r["idx"] == t1["idx"])
        width = 2 if (rec["ad_addr"] & 1) == 0 and not rec["ube_n"] else 1
        f1 = next(e for e in ev if e["idx"] > eop["idx"] and e["q"] == "F")
        print(f"{parity} target 0x{target:04x}: flush@{eop['idx']} -> "
              f"first fetch T1 +{t1['idx']-eop['idx']} "
              f"(addr {t1['addr']:05x}, {width}-byte) -> "
              f"first F +{f1['idx']-eop['idx']}")
    return 0


#----------------------------------------------------------------------------
# exp 3: saturated-queue F-spacing — per-instruction times + EA deltas
#----------------------------------------------------------------------------

def fspacing_case(a, host, name, x_src, regs_extra=None, tag="fsp", ram=None,
                  org=0x0500):
    """16 NOPs, then X, then 8 NOPs; X's time = its F-to-next-F gap."""
    src = "    NOP\n" * 16 + x_src + "    NOP\n" * 8
    code = a.assemble(src, org=org)
    x_len = len(a.assemble(x_src, org=org + 0x10))
    regs = {"PS": 0, "PC": org}
    if regs_extra:
        regs.update(regs_extra)
    res = run_test(regs=regs, instr=code, host=host, tag=tag, ram=ram)
    ev = queue_timeline(res["recs"], res["meta"])
    fpops = [e["idx"] for e in ev if e["q"] == "F"]
    gaps = [b - a2 for a2, b in zip(fpops, fpops[1:])]
    # instruction k (0-based) has F pop k; X is instruction 16
    nop_gaps = gaps[8:15]          # saturated NOP region before X
    x_gap = gaps[16] if len(gaps) > 16 else None
    nop_t = sorted(nop_gaps)[len(nop_gaps) // 2] if nop_gaps else None
    print(f"{name:<28} F-gap {x_gap:>3}  (NOP baseline {nop_t}, "
          f"{len(fpops)} F ops)")
    return x_gap, nop_t


def cmd_fspacing(host):
    a = Assembler()
    mem_regs = {"BW": 0x0800, "IX": 0x0010, "DS0": 0}
    cases = [
        ("NOP (baseline)",        "    NOP\n", None),
        ("MOV AW,imm16",          "    MOV AW, 0x1234\n", None),
        ("ADD AW,imm16",          "    ADD AW, 0x1111\n", None),
        ("INC AW",                "    INC AW\n", None),
        ("DIVU CW",               "    DIVU CW\n", {"AW": 9, "DW": 0, "CW": 3}),
        ("MULU CW",               "    MULU CW\n", {"AW": 7, "CW": 5}),
        ("MOV AW,[BW]",           "    MOV AW, [BW]\n", mem_regs),
        ("MOV AW,[BW+IX]",        "    MOV AW, [BW+IX]\n", mem_regs),
        ("MOV AW,[BW+IX+0x40]",   "    MOV AW, [BW+IX+0x40]\n", mem_regs),
        ("MOV AW,[0x0800] direct", "    MOV AW, [0x0800]\n", mem_regs),
        ("MOV [BW],AW",           "    MOV [BW], AW\n", mem_regs),
    ]
    print("saturated-queue F-to-F gaps (upper bound = true time when "
          "EU-bound):")
    for name, src, extra in cases:
        fspacing_case(a, host, name, src, extra,
                      tag=f"fsp{abs(hash(name)) % 1000}")
    return 0


#----------------------------------------------------------------------------
# exp 4: fetch/EU bus arbitration
#----------------------------------------------------------------------------

def cmd_arbitration(host):
    a = Assembler()
    src = "    MOV [BW], AW\n" * 8
    code = a.assemble(src, org=0x0500)
    res = run_test(regs={"PS": 0, "PC": 0x0500, "BW": 0x0800, "DS0": 0,
                         "AW": 0xBEEF},
                   instr=code, host=host, tag="arb")
    ev = queue_timeline(res["recs"], res["meta"])
    # transaction stream with inter-transaction idle
    txn, last_end = [], None
    cur = None
    for e in ev:
        if e["t"] == "T1":
            cur = {"kind": {4: "CODE", 6: "MEMW", 5: "MEMR"}.get(e["bs"], "?"),
                   "start": e["idx"], "d": e["depth"]}
        elif e["t"] == "T4" and cur:
            gap = cur["start"] - last_end - 1 if last_end else 0
            txn.append((cur["kind"], cur["start"], gap, cur["d"]))
            last_end = e["idx"]
            cur = None
    print("txn stream (kind, T1 cycle, idle-gap before, depth at T1):")
    for k, s, g, d in txn[:24]:
        print(f"  {k:<5} @{s:>4} gap={g} depth={d}")
    memw_gaps = [g for k, s, g, d in txn if k == "MEMW"]
    code_gaps = [g for k, s, g, d in txn if k == "CODE"]
    print(f"MEMW pre-idle gaps: {memw_gaps}")
    print(f"CODE pre-idle gaps: {code_gaps[:12]}")
    return 0


#----------------------------------------------------------------------------
# exp 5: wait-state sweep — BIU-bound vs EU-bound
#----------------------------------------------------------------------------

def cmd_waits(host):
    a = Assembler()
    print("F-gap vs wait states (BIU-bound scales, EU-bound flat):")
    print(f"{'waits':<6} {'NOP':>5} {'DIVU CW':>8}")
    for w in (0, 1, 2, 3):
        nop_code = a.assemble("    NOP\n" * 24, org=0x0500)
        res = run_test(regs={"PS": 0, "PC": 0x0500}, instr=nop_code,
                       host=host, tag=f"wn{w}", waits=w)
        ev = queue_timeline(res["recs"], res["meta"])
        f = [e["idx"] for e in ev if e["q"] == "F"]
        g = [b - a2 for a2, b in zip(f, f[1:])][8:15]
        nop_t = sorted(g)[len(g) // 2] if g else None

        div_code = a.assemble("    NOP\n" * 16 + "    DIVU CW\n" +
                              "    NOP\n" * 8, org=0x0500)
        res = run_test(regs={"PS": 0, "PC": 0x0500, "AW": 9, "DW": 0,
                             "CW": 3},
                       instr=div_code, host=host, tag=f"wd{w}", waits=w)
        ev = queue_timeline(res["recs"], res["meta"])
        f = [e["idx"] for e in ev if e["q"] == "F"]
        g = [b - a2 for a2, b in zip(f, f[1:])]
        div_t = g[16] if len(g) > 16 else None
        print(f"{w:<6} {nop_t:>5} {div_t:>8}")
    return 0


#----------------------------------------------------------------------------
# exp 6b: self-modifying-code distance
#----------------------------------------------------------------------------

def cmd_smc(host):
    a = Assembler()
    print("write to PC+d: does the CPU execute the OLD byte (INC AW) or "
          "the NEW one (NOP)?")
    for k in range(6, 16):
        # MOV byte [T],0x90 at 0x500 (5 bytes); NOP filler; INC AW at 0x500+k
        target = 0x0500 + k
        filler = k - 5 - 1  # -1: leave one slot for INC AW? no: fill to k
        filler = k - 5
        src = (f"    MOV byte [0x{target:04X}], 0x90\n" +
               "    NOP\n" * filler)
        code = a.assemble(src, org=0x0500) + bytes([0x40])  # INC AW
        assert len(code) == k + 1, (len(code), k)
        res = run_test(regs={"PS": 0, "PC": 0x0500, "DS0": 0, "AW": 0x1000},
                       instr=code, host=host, tag=f"smc{k}")
        aw = res["regs"]["AW"]
        stale = aw == 0x1001
        d = k - 5   # distance in bytes from the end of the MOV
        print(f"  d={d:>2} (write target 0x{target:04x}): AW={aw:04x} -> "
              f"{'STALE byte executed' if stale else 'new byte (NOP) executed'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["queue-limit", "flush", "fspacing",
                                    "arbitration", "waits", "smc", "all"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    cmds = {"queue-limit": cmd_queue_limit, "flush": cmd_flush,
            "fspacing": cmd_fspacing, "arbitration": cmd_arbitration,
            "waits": cmd_waits, "smc": cmd_smc}
    if args.cmd == "all":
        for name, fn in cmds.items():
            print(f"\n======== {name} ========")
            fn(args.host)
        sys.exit(0)
    sys.exit(cmds[args.cmd](args.host))


if __name__ == "__main__":
    main()
