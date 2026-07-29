#!/usr/bin/env python3
"""B0 directed-gate search (board-free). Finds, for each narrow law whose break
the standing gates missed (LC2/LC4a/LC6), a DISCRIMINATING seed+wvec where
disabling the law changes the OBSERVABLE model bus stream. Those seeds become
directed gate cases: adding them to the wvec-freeze corpus makes the (timing-
sensitive) wvec gate catch the mutation.

Method: build the UNMUTATED TB, compute per-(seed,wvec) observable digests over a
wide seed range -> baseline. Then per law: apply its predicate-breaking edit,
rebuild, sweep the same range, and report seeds whose digest DIFFERS (early-stop
at MAXHITS). Always restore the RTL via git checkout. NO board.

Usage: nohup setsid python3 -u sw/biu_law_gatesearch.py > sw/biu_law_gatesearch.log 2>&1 &
"""
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
from biu_rebuild_wvec_freeze import digest_case          # noqa: E402
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"

SEED_LO, SEED_HI = 90000, 90400          # up to 400 seeds
WVECS = [(5, 1), (7, 3), (11, 7)]        # random-per-cycle waits (skip w0 control)
MAXHITS = 5                              # discriminators to collect per law

LAWS = [
    dict(id="G-LC2", law="LC2 low-band pause",
         old="wire        lowband_pause = eval_ext && cur_fetch && q_cnt <= 3'd2 &&",
         new="wire        lowband_pause = 1'b0 && eval_ext && cur_fetch && q_cnt <= 3'd2 &&"),
    dict(id="G-LC4a", law="LC4 pf_rsv_lead",
         old="wire        pf_rsv_lead = eval_ext && eu_rsv_lead &&",
         new="wire        pf_rsv_lead = 1'b0 && eval_ext && eu_rsv_lead &&"),
    dict(id="G-LC6", law="LC6 strio pick_t3 veto",
         old="wire        pick_t3    = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio);",
         new="wire        pick_t3    = want_half2 || want_eu || prefetch_ok;"),
]


def sh(cmd, timeout=1200):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def build():
    sh([sys.executable, "sw/check_core.py", "--build", "--suite-dir",
        "tests/v30/v0.1", "--opcodes", "all", "--cases", "1", "--waits", "0"])


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
    print(f"=== B0 gate search  seeds {SEED_LO}-{SEED_HI}  wvecs {WVECS} ===", flush=True)
    restore()
    print("building UNMUTATED baseline binary...", flush=True)
    build()
    print(f"computing baseline over {len(seeds)} seeds x {len(WVECS)} wvecs...", flush=True)
    base = sweep(seeds)
    print("baseline done.", flush=True)

    results = {}
    for law in LAWS:
        print(f"\n### {law['id']} ({law['law']})", flush=True)
        txt = BIU.read_text()
        assert txt.count(law["old"]) == 1, f"{law['id']} target not unique"
        BIU.write_text(txt.replace(law["old"], law["new"], 1))
        try:
            build()
            hits = []
            for s in seeds:
                if len(hits) >= MAXHITS:
                    break
                for ws, wmax in WVECS:
                    b = base.get((s, ws, wmax))
                    try:
                        m = digest_case(s, ws, wmax)["sha"]
                    except Exception as e:
                        m = f"ERR:{e}"
                    if isinstance(b, str) and not b.startswith("ERR") and m != b:
                        hits.append([s, ws, wmax])
                        print(f"  DISCRIMINATOR seed={s} ws={ws} wmax={wmax} "
                              f"base={b} mut={m}", flush=True)
                        break
            results[law["id"]] = hits
            if not hits:
                print(f"  NO discriminator in {SEED_LO}-{SEED_HI} "
                      f"-> needs a hand-built gadget", flush=True)
        finally:
            restore()

    Path(ROOT / "sw/biu_law_gatesearch.json").write_text(
        json.dumps({k: v for k, v in results.items()}, indent=1) + "\n")
    print(f"\n=== GATESEARCH_DONE  {json.dumps(results)} ===", flush=True)
    restore()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        restore()
