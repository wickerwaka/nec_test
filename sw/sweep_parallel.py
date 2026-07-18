#!/usr/bin/env python3
"""Parallel arch-only sweep driver (Path B).

One check_core.py process per opcode via a bounded pool, each writing its OWN
result-log; the shards are concatenated at the end (never a shared append
target, which would interleave/corrupt). The Verilator model is built ONCE
up-front so the workers only run it. Opcodes are independent, so this is an
embarrassingly-parallel ~Nx speedup over the serial per-opcode loop.

  python3 sw/sweep_parallel.py [--suite-dir DIR] [--opcodes all|a,b,..]
                               [--cases N] [--waits W] [-P 8] [--out FILE]
"""
import sys, subprocess, argparse, concurrent.futures, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "sw" / "check_core.py"


def run_one(op, suite_dir, cases, waits, shard_dir):
    lf = shard_dir / f"{op}.jsonl"
    cmd = [sys.executable, str(CHECK), "--arch-only",
           "--suite-dir", suite_dir, "--opcodes", op,
           "--result-log", str(lf), "--details", "0", "--waits", str(waits)]
    if cases:
        cmd += ["--cases", str(cases)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # check_core writes the result-log line itself; capture stdout tail for the
    # summary and surface non-zero exits.
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return op, r.returncode, lf, tail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-dir", default="tests/v30/v20suite")
    ap.add_argument("--opcodes", default="all")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--waits", type=int, default=0)
    ap.add_argument("-P", "--procs", type=int, default=8)
    ap.add_argument("--out", default="sw/v20_arch_sweep_parallel.jsonl")
    a = ap.parse_args()

    suite = Path(a.suite_dir)
    if a.opcodes == "all":
        ops = sorted(p.name[:-len(".json.gz")] for p in suite.glob("*.json.gz"))
    else:
        ops = a.opcodes.split(",")

    # Build the model ONCE up-front (workers then see BIN fresh and skip build).
    print("pre-building model (if stale) ...", flush=True)
    sys.path.insert(0, str(ROOT / "sw"))
    import check_core
    check_core.build(force=False)

    import time
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        shard_dir = Path(td)
        done = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.procs) as ex:
            futs = {ex.submit(run_one, op, a.suite_dir, a.cases, a.waits,
                              shard_dir): op for op in ops}
            for f in concurrent.futures.as_completed(futs):
                op, rc, lf, tail = f.result()
                done += 1
                if rc != 0:
                    print(f"  [{done}/{len(ops)}] {op}: RC={rc}", flush=True)
                elif done % 20 == 0 or done == len(ops):
                    print(f"  [{done}/{len(ops)}] {tail}", flush=True)
        # concatenate shards in opcode order into the single out file
        out = Path(a.out)
        with out.open("w") as of:
            for op in ops:
                lf = shard_dir / f"{op}.jsonl"
                if lf.exists():
                    of.write(lf.read_text())
    print(f"done: {len(ops)} opcodes in {time.time()-t0:.0f}s -> {a.out}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
