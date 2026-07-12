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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["queue-limit"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    if args.cmd == "queue-limit":
        sys.exit(cmd_queue_limit(args.host))


if __name__ == "__main__":
    main()
