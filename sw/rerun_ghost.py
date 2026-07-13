#!/usr/bin/env python3
"""Re-run selected 8F.0 golden cases on the board and report the mod3
ghost-read address on the window-closing row. Used to test determinism
(ladder step 2) and history-dependence (step 3) of the ghost address.

Usage:
  rerun_ghost.py --idxs 5,25,... --reps 4 [--use-core 0|1]
                 [--preload N] [--mutate-load]
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage
import emit_suite as es
from v30run import run_image

SUITE = SW.parent / "tests" / "v30" / "v0.1"


def compose_case(test, preload_n, mutate_load=None):
    regs = {es.INTEL2NEC[k]: v for k, v in test["initial"]["regs"].items()}
    instr = bytes(test["bytes"])
    ram = [(a, v) for a, v in test["initial"]["ram"]]
    ir = test["initial"]["regs"]
    fr = test["final"]["regs"]
    next_ip = fr.get("ip", (ir["ip"] + len(instr)) & 0xFFFF)
    next_cs = fr.get("cs", ir["cs"])
    nec = dict(regs)
    if preload_n:
        nec["PC"] = (nec["PC"] - 2 * preload_n) & 0xFFFF
        run_instr = es.PRELOAD_BYTES * preload_n + instr
    else:
        run_instr = instr
    stub_linear = ((next_cs << 4) + next_ip) & 0xFFFF
    image, meta = testimage.compose(regs=nec, instr=run_instr, ram=ram,
                                    ivt=None, stub_linear=stub_linear)
    if mutate_load is not None:
        # overwrite the load-routine region with the mutation callback
        image = mutate_load(bytearray(image), meta)
    return bytes(image), meta


def ghost_addr(test, host, preload_n, use_core, tag, mutate_load=None):
    image, meta = compose_case(test, preload_n, mutate_load)
    recs = run_image(image, host, tag=tag, use_core=use_core, cap=es.EMIT_CAP)
    rows, events, i0, i1, q0, qf, fetched, memrd = es.build_rows(
        recs, meta["anchor_linear"], n_skip_f=preload_n, n_close=1)
    # window-closing row is the last row; its bus col (index 1) is the
    # committed next-cycle address (the ghost read for mod3)
    last = rows[-1]
    return last[1], last[7], rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idxs", default="5,25,29,44,92,143,246,384")
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--use-core", type=int, default=0)
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()

    cases = {c["idx"]: c for c in json.load(gzip.open(SUITE / "8F.0.json.gz"))}
    idxs = [int(x) for x in args.idxs.split(",")]
    uc = bool(args.use_core)

    for idx in idxs:
        test = cases[idx]
        preload_n = 2 if idx % 2 == 1 else 0
        golden = None
        for row in test["cycles"]:
            pass
        golden = test["cycles"][-1][1]
        vals = []
        for rep in range(args.reps):
            try:
                a, bs, _ = ghost_addr(test, args.host, preload_n, uc,
                                      tag=f"rg{idx}_{rep}")
                vals.append(a)
            except Exception as e:
                vals.append(f"ERR:{str(e)[:40]}")
        stable = len(set(v for v in vals if isinstance(v, int))) <= 1
        print(f"idx {idx:4d} ({'pf' if preload_n else 'cold'}) golden={golden:6d}({golden:05X})  "
              f"reruns={[v if not isinstance(v,int) else f'{v}' for v in vals]}  "
              f"stable={stable}  match_golden={all(v==golden for v in vals if isinstance(v,int))}")


if __name__ == "__main__":
    main()
