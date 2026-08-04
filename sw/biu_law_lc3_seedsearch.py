#!/usr/bin/env python3
"""M-LC3 (H-PHASE) discriminating-SEED search (board-free). The synthetic RMW
gadget couldn't reproduce the narrow ready-AT-T4/even-parity cell; but random
soup (gen_seq) emits RMW mem-writes (F6/F7/FE/FF/80/81/83 [mem]) and random
per-cycle waits create diverse Tw parities -- the same approach that closed
G-LC2/G-LC4a. Find a seed where reverting the ext_ok_wr widen (M-LC3) changes the
observable model bus stream; add it to the wvec corpus -> M-LC3 caught board-free.
Restores RTL via git checkout. NO board.
"""
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
from biu_rebuild_wvec_freeze import digest_case          # noqa: E402
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"

LC3_OLD = "(eu_ready_p1 && !eu_ready_p2 && !tw_par);"
LC3_NEW = "(eu_ready_p1 && !eu_ready_p2 && 1'b0);"
SEED_LO, SEED_HI = 90000, 90020  # census seeds (H-PHASE cell lives here)
WVECS = [(ws, wm) for ws in range(0, 6) for wm in (1, 3, 7)]  # EXACT census wvecs
MAXHITS = 8


def sh(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200)


def build():
    # --core fsm EXPLICIT: this tool mutates hdl/rtl/core/v30_biu.sv (the
    # ARCHIVED FSM core) and has no ucore counterpart.  Pinned when
    # check_core.py's default flipped fsm -> ucore, 2026-08-04.
    r = sh([sys.executable, "sw/check_core.py", "--build", "--core", "fsm",
            "--suite-dir",
            "tests/v30/v0.1", "--opcodes", "all", "--cases", "1", "--waits", "0"])
    if r.returncode != 0:
        raise RuntimeError("verilator build FAILED (stale-binary guard)")


def restore():
    sh(["git", "checkout", "--", "hdl/rtl/core/v30_biu.sv"])


def sweep(seeds):
    out = {}
    for s in seeds:
        for ws, wmax in WVECS:
            try:
                out[(s, ws, wmax)] = digest_case(s, ws, wmax)["sha"]
            except Exception as e:
                out[(s, ws, wmax)] = f"ERR:{e}"
    return out


def main():
    seeds = list(range(SEED_LO, SEED_HI))
    print(f"=== M-LC3 seed search {SEED_LO}-{SEED_HI} x {WVECS} ===", flush=True)
    restore()
    print("baseline (unmutated) build...", flush=True)
    build()
    print(f"baseline digests over {len(seeds)} seeds...", flush=True)
    base = sweep(seeds)
    print("baseline done", flush=True)

    t = BIU.read_text()
    assert t.count(LC3_OLD) == 1
    BIU.write_text(t.replace(LC3_OLD, LC3_NEW, 1))
    hits = []
    try:
        build()
        for s in seeds:
            if len(hits) >= MAXHITS:
                break
            for ws, wmax in WVECS:
                b = base.get((s, ws, wmax))
                if not isinstance(b, str) or b.startswith("ERR"):
                    continue
                try:
                    m = digest_case(s, ws, wmax)["sha"]
                except Exception as e:
                    m = f"ERR:{e}"
                if m != b:
                    hits.append([s, ws, wmax])
                    print(f"  DISCRIMINATOR seed={s} ws={ws} wmax={wmax} "
                          f"base={b} mut={m}", flush=True)
                    break
    finally:
        restore()

    Path(ROOT / "sw/biu_law_lc3_seedsearch.json").write_text(
        json.dumps(hits, indent=1) + "\n")
    print(f"=== LC3_SEEDSEARCH_DONE hits={len(hits)} {hits} ===", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        restore()
