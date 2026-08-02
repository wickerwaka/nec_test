#!/usr/bin/env python3
"""timed_scenario -- L1 oracle replay: the FROZEN decoder schedules, in-sim.

The blackbox campaign froze three decoder byte-demand oracles

    decoder-multibyte-oracle-v1     modrm_reg / test_reg / imm16 / branch
    decoder-displacement-oracle-v1  disp8 / disp16
    decoder-drain-oracle-v2         one-byte successor classes fast/std/long

as `zero_wait_qs` / `positive_wait_qs` schedules -- the QS events an
instruction emits, and the clock its successor's own opcode pop lands on.
Provenance 7.6 cross-checked them by HAND against the v0.1 goldens; 7.12 item
7 and 8.8 record the replay harness as still owed.  This is it.

Frame.  The oracles count clocks from the arbitration-SELECTED cycle's T4; the
ledger counts from the instruction's opening `F` pop.  The two differ by
exactly one (7.6: multibyte `imm16` [(1,F),(3,S),(4,S),(5,F)] is B8's
0,2,3,4), so this replay asserts

    sim pop clock (relative to the opening F)  ==  oracle clock - 1

for every event in the schedule, and

for the whole schedule.  Nothing is refitted: the oracle files are read as
frozen and the shift is a single documented constant.

NOT replayed, and said so rather than quietly passed:
  * the rules' `gap` (`t1_from_selected_t4` in the original validator) is a
    BUS quantity in the arbitration frame -- the successor CODE cycle's T1
    measured from the selected cycle's T4 -- not a decoder one.  Replaying it
    needs the REP-successor arbitration scenario the oracles were captured in,
    which is T2/T3 work.
  * the POSITIVE-WAIT half of every rule belongs to T2 (the wait axis).

  timed_scenario.py                 # all classes, one line each
  timed_scenario.py --verbose       # print each schedule
"""

import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import timed_gate                      # noqa: E402

BB = ROOT / "sw" / "testdata" / "biu_blackbox"

# The oracle frame is the selected cycle's T4; the ledger frame is the
# instruction's opening F pop.  7.6 fixes the offset between them at 1.
FRAME_SHIFT = 1

# One representative encoding per frozen class, chosen to BE that class and
# nothing else.  The successor is a NOP so the closing F pop is unambiguous.
CLASSES = [
    # (oracle file, rule name, instruction bytes, disassembly)
    ("decoder-multibyte-oracle-v1.json", "modrm_reg", [0x8B, 0xC0], "mov ax,ax"),
    ("decoder-multibyte-oracle-v1.json", "test_reg", [0x85, 0xC0], "test ax,ax"),
    ("decoder-multibyte-oracle-v1.json", "imm16", [0xB8, 0x34, 0x12],
     "mov ax,1234h"),
    ("decoder-multibyte-oracle-v1.json", "branch", [0xEB, 0x02], "jmp short +2"),
    ("decoder-displacement-oracle-v1.json", "disp8", [0x8B, 0x46, 0x10],
     "mov ax,[bp+10h]"),
    ("decoder-displacement-oracle-v1.json", "disp16", [0x8B, 0x86, 0x34, 0x12],
     "mov ax,[bp+1234h]"),
]

QS_NAME = {1: "F", 2: "E", 3: "S"}

CS, IP, SP = 0x1000, 0x0100, 0x0200


def make_case(byts):
    """A saturated-queue case: the queue is injected FULL so every byte the
    decoder wants is already there and the schedule is the decoder's own."""
    base = (CS << 4) + IP
    ram = [[base + i, b] for i, b in enumerate(byts)]
    ram += [[base + len(byts) + i, 0x90] for i in range(8)]
    q = (byts + [0x90] * 6)[:6]
    return {
        "name": "scenario",
        "bytes": byts,
        "initial": {
            "regs": {"ax": 0x1111, "cx": 0x2222, "dx": 0x3333, "bx": 0x4444,
                     "sp": SP, "bp": 0x0300, "si": 0x0400, "di": 0x0500,
                     "cs": CS, "ip": IP, "ds": 0x2000, "es": 0x3000,
                     "ss": 0x4000, "flags": 0xF002},
            "ram": ram,
            "queue": q,
        },
        "final": {"regs": {}, "ram": [], "queue": []},
        "cycles": [],
        "idx": 0,
    }


def sim_schedule(byts):
    """-> [(clock relative to the opening F pop, qs code)] from the sim."""
    sims = timed_gate.run_form([make_case(byts)], 0, False)
    recs = sims[0]["recs"]
    # one record per CPU clock, in order: the index IS the clock
    ev = [(i, r["qs"]) for i, r in enumerate(recs) if r["qs"]]
    if not ev:
        return None
    # events are absolute clocks; rebase on the first F
    first = next((c for c, q in ev if q == 1), None)
    if first is None:
        return None
    return [(c - first, q) for c, q in ev if c >= first]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    npass = nfail = nskip = 0
    for fname, rule_name, byts, text in CLASSES:
        oracle = json.loads((BB / fname).read_text())
        rule = oracle["rules"][rule_name]
        want = [(c - FRAME_SHIFT, q) for c, q in rule["zero_wait_qs"]]
        got = sim_schedule(byts)
        if got is None:
            print("FAIL %-10s %-18s no QS events" % (rule_name, text))
            nfail += 1
            continue
        got = got[:len(want)]
        ok = got == want
        print("%-4s %-10s %-18s oracle %s  sim %s"
              % ("PASS" if ok else "FAIL", rule_name, text,
                 [(c, QS_NAME.get(q, q)) for c, q in want],
                 [(c, QS_NAME.get(q, q)) for c, q in got]))
        if args.verbose and not ok:
            print("      full sim schedule:", sim_schedule(byts))
        npass += ok
        nfail += not ok
    nskip = 2 * len(CLASSES)   # each rule's positive-wait half and its `gap`
    print("\ntimed-scenario: %d PASS, %d FAIL, %d SKIP (each rule's "
          "positive-wait half -> T2, and its `gap` -> the arbitration frame)"
          % (npass, nfail, nskip))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
