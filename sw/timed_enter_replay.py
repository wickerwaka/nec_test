#!/usr/bin/env python3
"""timed_enter_replay -- the ENTER/PREPARE waited tranche, replayed IN-SIM.

`tests/v30/enter_nesting/goldens_waited.json.gz` is 154 SOCKET digests: for
each (context, nesting, wait) the WHOLE ordered bus-transaction stream from
the test instruction's anchor -- [kind, addr16, data, duration] per
transaction -- plus the run's active-bus-cycle count.  Its metadata states the
check as "full txn stream (kind,addr,data,dur) + active count == chip, STRICT
at ALL waits".

The offline pilot (sw/enter_ucode_pilot.py) reads those digests and checks two
STRUCTURAL properties of them (MEMW count == nest+1; every duration == 3+w).
This harness instead rebuilds each case's image with the same composer the rig
used (sw/testimage.compose), runs it through `v30sim timed-boot` at the same
wait setting -- uniform N, or the seeded wrand LFSR for the two wrand slices --
and compares the SIM's transaction stream against the chip's, transaction for
transaction.

Levels reported, weakest to strongest:
    pushes    stack-region MEMW count == nest+1        (the pilot's own check)
    walk      the stack-region MEMW/MEMR (kind,addr,data) subsequence
    full      the whole (kind,addr,data,dur) stream from the anchor
    active    the active-bus-cycle count of the whole run

Usage:  python3 sw/timed_enter_replay.py [--verbose] [--waits 0,1,2,3,7]
"""

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage                                    # noqa: E402
import char_enter as ce                             # noqa: E402
import fuzz_classify as fc                          # noqa: E402

SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
GOLD = ROOT / "tests" / "v30" / "enter_nesting" / "goldens_waited.json.gz"

# The rig captures TB_WINDOW clocks (char_enter.TB_WINDOW); the digest runs to
# the program's HALT, so the sim needs at least as long a window.
CLOCKS = 12000


def run_sim(image, waits, wrand, td):
    img = Path(td) / "enter.bin"
    img.write_bytes(image)
    argv = [str(SIM), "timed-boot", str(ROM), str(img),
            f"--clocks={CLOCKS}", "--ndjson"]
    if wrand:
        wmax, wseed = wrand
        argv += [f"--wmax={wmax}", f"--wseed={wseed}"]
    else:
        argv.append(f"--waits={waits}")
    r = subprocess.run(argv, capture_output=True)
    return [x for x in (json.loads(l) for l in r.stdout.decode().splitlines()
                        if l.startswith("{")) if "t" in x]


def anchored(rows, anchor16):
    """char_enter.full_txns, but keeping each transaction's ROW SPAN so the
    active-cycle count can be taken over exactly the compared prefix."""
    out, started = [], False
    for tx in fc.extract_txns(rows):
        k = fc.KIND[tx["kind"]]
        a = tx["addr"] & 0xFFFF
        if not started:
            if k == "CODE" and a == (anchor16 & 0xFFFF):
                started = True
            else:
                continue
        out.append(([k, a, tx.get("data"),
                     tx.get("end", tx["start"]) - tx["start"]],
                    tx.get("end", tx["start"])))
    return out


def active_upto(rows, end_row):
    return sum(1 for r in rows[:end_row + 1]
               if fc._tstate(r) == 1 and r["bs_early"] != 7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--waits", default="")
    args = ap.parse_args()

    only = ({int(x) for x in args.waits.split(",") if x}
            if args.waits else None)
    goldens = json.load(gzip.open(GOLD))
    n = Counter()
    with tempfile.TemporaryDirectory() as td:
        for g in goldens:
            if only is not None and g.get("waits") not in only:
                continue
            instr = ce.enter_case_instr(g["bp"], g["fsize"], g["nest"])
            image, meta = testimage.compose(regs={"BP": g["bp"],
                                                  "SP": g["sp"]},
                                            instr=instr)
            anchor16 = meta["anchor_linear"] & 0xFFFF
            assert anchor16 == g["anchor16"], (anchor16, g["anchor16"])
            rows = run_sim(image, g.get("waits") or 0,
                           tuple(g["wrand"]) if g.get("wrand") else None, td)
            # SCOPE.  The chip digest's last transaction is the store stub's
            # HALT display pseudo-cycle, which the timed model does not have
            # (scaffolding S8/S9, declared open since T0 and unchanged here):
            # the sim executes the HLT architecturally and then keeps
            # prefetching instead of parking the bus.  So the comparison runs
            # over the chip's stream WITHOUT its trailing HALT, and the HALT
            # cycle is reported separately as the missing mechanism it is.
            gf = g["full"]
            k = len(gf) - 1 if gf and gf[-1][0] == "HALT" else len(gf)
            n["cells"] += 1
            n["halt_display"] += any(t[0] == "HALT"
                                     for t, _e in anchored(rows, anchor16))
            aa = anchored(rows, anchor16)
            full = [t for t, _e in aa[:k]]
            memw = [t for t in full
                    if t[0] == "MEMW" and ce.STK_LO <= t[1] <= ce.STK_HI]
            n["pushes"] += (len(memw) == g["nest"] + 1)
            n["walk"] += (ce.walk_of(full) == ce.walk_of(gf[:k]))
            n["full"] += (full == gf[:k])
            if len(aa) >= k:
                n["active"] += (active_upto(rows, aa[k - 1][1])
                                == g["active"] - (len(gf) - k))
            if args.verbose and full != gf[:k]:
                w = (f"w{g['waits']}" if g.get("waits") is not None
                     else f"wrand{tuple(g['wrand'])}")
                first = next((i for i, (a, b) in enumerate(zip(full, gf))
                              if a != b), min(len(full), len(gf)))
                a = full[first] if first < len(full) else None
                b = gf[first] if first < k else None
                print(f"  ctx{g['ctx']} nest={g['nest']:2d} {w}: "
                      f"len sim {len(full)} chip {len(gf)}, "
                      f"first diff at txn {first}: sim {a} chip {b}")

    print("== ENTER waited tranche, replayed through the timed sim ==")
    for k in ("pushes", "walk", "full", "active"):
        print(f"  {k:13s} {n[k]}/{n['cells']}")
    print(f"  halt_display  {n['halt_display']}/{n['cells']}"
          "   (S8/S9: the HALT bus pseudo-cycle is not modelled -- "
          "OUT of the compared prefix, not counted as a pass)")
    return 0 if n["full"] == n["cells"] else 1


if __name__ == "__main__":
    sys.exit(main())
