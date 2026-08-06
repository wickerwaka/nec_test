#!/usr/bin/env python3
"""W7 regression gate for the native BRKEM entry write chain.

The retained captures continue into 8080 execution, which is explicitly out of
scope.  This gate therefore stops at the handoff: all rows before the third
frame write must be exact, the four-idle-clock logical-write boundary must match,
and the first remaining difference must be only the already-booked 8080-mode
QS=E sample on that third write's T1.

The registered native-scope attribution floors combine the legacy whole-stream
floors with these 21 disjoint entries.  They are implementation attribution
figures on wr1's divergent-by-construction subset, not silicon-match rates.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc  # noqa: E402
import simbin               # noqa: E402
import w32_launch as w32    # noqa: E402

SEEDS = (
    215006, 215015, 215031, 215042, 215071, 216006, 216048,
    218062, 220005, 220023, 220026, 220030, 221046, 222013,
    222023, 224070, 224073, 225005, 225027, 226034, 207062,
)
DEFAULT_SEEDDIR = Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2/seeds"
WHOLE_STREAM_FLOORS = {"sim": 84, "ucore": 91}
WR1_DENOMINATOR = 184


def t_of(row):
    return row.get("t_state", row.get("t"))


def load_seed(seeddir, seed):
    hits = list(seeddir.glob(f"*_{seed}_*.json.gz"))
    if len(hits) != 1:
        raise RuntimeError(f"seed {seed}: expected one record, got {len(hits)}")
    return json.loads(gzip.decompress(hits[0].read_bytes()))


def write_chain(rows, stop):
    cycles = w32.cycles(rows, len(rows))
    pos = next((j for j, c in enumerate(cycles) if c["row"] == stop), None)
    if pos is None or cycles[pos]["bs"] != "MEMW":
        raise RuntimeError(f"row {stop}: not a MEMW T1")
    lo = pos
    while lo and cycles[lo - 1]["bs"] == "MEMW":
        lo -= 1
    chain = cycles[lo:pos + 1]
    gaps = [b["row"] - a["row"] - a["alen"]
            for a, b in zip(chain, chain[1:])]
    return chain, gaps


def logical_gaps(chain):
    """Collapse the two physical cycles of an odd-addressed word write."""
    groups = []
    i = 0
    while i < len(chain):
        end = i
        if (i + 1 < len(chain) and
                chain[i + 1]["addr"] == chain[i]["addr"] + 1 and
                chain[i + 1]["row"] - chain[i]["row"] -
                chain[i]["alen"] == 1):
            end = i + 1
        groups.append((i, end))
        i = end + 1
    return [chain[b[0]]["row"] - chain[a[1]]["row"] -
            chain[a[1]]["alen"] for a, b in zip(groups, groups[1:])]


def check(core, entry):
    rows, err = w32.engine_rows(entry, core)
    if err:
        raise RuntimeError(err[-1000:])
    diff = fc.diff_rows(entry["chip_rows"], rows)
    if not diff.rows:
        raise RuntimeError("capture unexpectedly whole-stream exact")
    first = diff.rows[0]
    i = first.i
    chip = entry["chip_rows"][i]
    got = rows[i]
    if (first.qs_txt != "qs E!=-" or first.other or first.flicker or
            t_of(chip) != 1 or chip["bs_early"] != 6 or chip["qs"] != 2 or
            t_of(got) != 1 or got["bs_early"] != 6 or got["qs"] != 0):
        raise RuntimeError(f"first residual is not the 8080 handoff E: {first}")

    # diff_rows already proves the complete prefix.  Check the mechanism's
    # own bus observable explicitly as well: the first logical-write boundary
    # in the ending chain has four idle clocks, for even and split odd stacks.
    cc, cg = write_chain(entry["chip_rows"], i)
    ec, eg = write_chain(rows, i)
    ckey = [(c["row"], c["bs"], c["addr"], c["alen"]) for c in cc]
    ekey = [(c["row"], c["bs"], c["addr"], c["alen"]) for c in ec]
    if ckey != ekey:
        raise RuntimeError("frame write-cycle stream differs before 8080 handoff")
    clg, elg = logical_gaps(cc), logical_gaps(ec)
    if cg != eg or clg != elg or not clg or clg[0] != 4:
        raise RuntimeError(f"paired-write gap law differs: "
                           f"chip={cg}/{clg} {core}={eg}/{elg}")
    return i, cg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", choices=("sim", "ucore", "both"), default="both")
    ap.add_argument("--seeddir", type=Path, default=DEFAULT_SEEDDIR)
    args = ap.parse_args()
    if not args.seeddir.is_dir():
        raise SystemExit(f"seeddir absent: {args.seeddir}")
    simbin.ensure(why=__name__)
    cores = ("sim", "ucore") if args.core == "both" else (args.core,)
    ok = True
    for core in cores:
        passed = 0
        for seed in SEEDS:
            try:
                check(core, load_seed(args.seeddir, seed))
                passed += 1
            except Exception as exc:
                ok = False
                print(f"[{core}] {seed}: FAIL: {exc}")
        print(f"{core}: native write-chain exact through 8080 handoff "
              f"{passed}/{len(SEEDS)}")
        floor = WHOLE_STREAM_FLOORS[core] + passed
        print(f"{core}: native-scope attribution floor {floor}/"
              f"{WR1_DENOMINATOR} ({WHOLE_STREAM_FLOORS[core]} whole-stream "
              f"+ {passed} W7 native-prefix)")
    print("GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
