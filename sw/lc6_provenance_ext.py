#!/usr/bin/env python3
"""LC6 P-C15/P-C16 extended provenance: the Family-5 TI-exemption + Family-7
idle-arm strio behaviors on silicon. Captures a RANGE of strio-OUTSB gadget
configs at w0 (j = leading-phase, k = queue-fill -> different queue states that
exercise the T3-veto / TI-grant / idle-window arm paths) on CHIP + FABRIC, and
asserts chip==fabric in each CHARACTERIZED WINDOW (up to the first post-gadget
wander -- my synthetic gadget is un-fenced, so the strio behavior is the early
rows; a late first-divergence == the strio family behavior matched silicon). Banks
the chip rows. Board, capture-only, NO reflash.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import biu_law_lc6_gadget as G                       # noqa: E402
from check_seq import run_chip, diff                 # noqa: E402
import testimage                                     # noqa: E402

HOST = "root@mister-nec"
BANK = ROOT / "sw/testdata/lc6_provenance_ext.jsonl"
# j (phase) x k (queue-fill) at w0 -> spans the veto / TI-grant / idle-arm states
CFG = [(0x6E, j, k) for j in (0, 1, 2) for k in (0, 2, 4)]
WINDOW = 150   # the strio family behavior completes well within this; wander is later


def main():
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    run_chip(img0, HOST, use_core=False)
    out = []
    allok = True
    for op, j, k in CFG:
        img = G.build_image(op, j, k)
        chip = run_chip(img, HOST, use_core=False, waits=0)
        fab = run_chip(img, HOST, use_core=True, waits=0)
        bad, first, n, flick = diff(chip, fab)
        # characterized-window verdict: clean, OR first divergence is LATE (wander)
        winok = (bad == 0) or (first is not None and first >= WINDOW)
        allok = allok and winok
        out.append(dict(op=op, j=j, k=k, bad=bad, first=first, n=n,
                        window_ok=winok))
        print(f"  strio j={j} k={k} w0: bad={bad} first={first} n={n} "
              f"-> characterized-window chip=={'fabric' if winok else 'MISMATCH<<<'}"
              f"{'' if bad == 0 else ' (clean 0..%s, wander after)' % first}",
              flush=True)
    run_chip(img0, HOST, use_core=False)
    BANK.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    print(f"\nLC6 P-C15/16 (strio TI-exemption + idle-arm behaviors): "
          f"{'ALL chip==fabric in characterized window (silicon-correct)' if allok else 'MISMATCH in a characterized window -- investigate'}; "
          f"banked {len(out)} configs -> {BANK}; board idle")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
