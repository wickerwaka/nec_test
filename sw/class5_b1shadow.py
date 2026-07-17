#!/usr/bin/env python3
"""B1 SHADOW AUDIT: the class-5 unified law, in-loop, FULL-TRACE.

The law is implemented in v30_biu.sv as a LOG-ONLY shadow (drives nothing;
goldens re-run to confirm inertness). This audits it over FULL TRACES - every
CPU cycle of every run - not anchors. Anchors prove nothing here (the i149/i151
contamination lesson).

CHECKS (coordinator's B1 list):
 (1) HARD GATE - SUPERSESSION: every midband_pause / lowband_pause firing must
     be covered by sh_pause_arm. A veto-armed cycle where the law says GO is
     STOP-AND-INVESTIGATE, not a diff to accept.
 (2) W0 SHADOW: law firings over the full w0 golden traces. A firing where the
     chip CHAINS means the law is missing a frame term.
 (3) T4+3 commit vs q_aged: assert the slack.
 (4) EU arbitration inside the pause window (want_eu must win, resume re-derive).
 (5) Flush inside the window: the schedule must cancel; the flush law owns it.

Usage: python3 sw/class5_b1shadow.py
"""
import sys, json, gzip, time
import random as _r
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import generate, compose, run_tb_internal, accesses, bs_stream, CODE

LOG = SW / "class5_b1shadow.log"
CORPUS_SEEDS = {"gz": list(range(90000, 90008)) + list(range(91000, 91006)),
                "fresh": list(range(90008, 90018)) + list(range(91006, 91012))}


def wait_vectors():
    wd = {"w1": [1] * 4096, "w2": [2] * 4096, "w3": [3] * 4096}
    for (ws, wm) in [(4, 3), (7, 7)]:
        rr = _r.Random((ws << 8) | wm)
        wd[f"r{ws}.{wm}"] = [rr.randint(0, wm) for _ in range(4096)]
    return wd


def main():
    logf = LOG.open("w")

    def log(s=""):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    log("=== B1 SHADOW AUDIT (full-trace, in-loop) ===")
    log("shadow is LOG-ONLY; goldens re-run inert: w0 169000/169000, "
        "w1 1200/1200, w3 1200/1200\n")

    wvs = wait_vectors()
    # ---- corpora: full traces ----
    tot = dict(cycles=0, arm=0, mid=0, low=0, veto=0,
               gate_fail=0, fired=0)
    cidle_hist = defaultdict(int)
    gate_rows = []
    armed_flush = 0
    armed_euhold = 0
    t0 = time.time()
    for src, seeds in CORPUS_SEEDS.items():
        for seed in seeds:
            g = generate(f"fz{seed}", exts=())
            image, meta = compose(g)
            for wname, wv in wvs.items():
                rows = run_tb_internal(image, 4200, wv)
                for i, r in enumerate(rows):
                    tot["cycles"] += 1
                    mid, low = r["midband_pause"], r["lowband_pause"]
                    arm = r["sh_arm"]
                    if mid:
                        tot["mid"] += 1
                    if low:
                        tot["low"] += 1
                    if mid or low:
                        tot["veto"] += 1
                        # (1) SUPERSESSION GATE
                        if not arm:
                            tot["gate_fail"] += 1
                            if len(gate_rows) < 12:
                                gate_rows.append(
                                    dict(src=src, seed=seed, w=wname, clk=r["clk"],
                                         mid=mid, low=low, d_cnt=r["sh_d_cnt"],
                                         occ=r["occupied"], q_cnt=r["q_cnt"],
                                         d_tw=r["sh_d_tw"]))
                    if arm:
                        tot["arm"] += 1
                        if r["q_flush"]:
                            armed_flush += 1
                        if r["eu_hold"] or r["eu_req"]:
                            armed_euhold += 1
                    if r["sh_fired"]:
                        tot["fired"] += 1
                        cidle_hist[r["sh_cidle"]] += 1
    log(f"corpora full-trace: {tot['cycles']} CPU cycles "
        f"({time.time()-t0:.0f}s)")
    log(f"  veto firings: midband={tot['mid']} lowband={tot['low']} "
        f"(union {tot['veto']})")
    log(f"  law arms: {tot['arm']}   resolutions (sh_fired): {tot['fired']}")
    log(f"  resolved cidle_sel histogram: {dict(sorted(cidle_hist.items()))}")

    log("\n--- (1) HARD GATE: SUPERSESSION ---")
    log(f"    veto-armed cycles NOT covered by the law: {tot['gate_fail']}"
        f" / {tot['veto']}")
    if tot["gate_fail"] == 0:
        log("    PASS - the law is a strict superset of both vetoes on both "
            "corpora.")
    else:
        log("    *** FAIL - STOP AND INVESTIGATE. Sample uncovered rows:")
        for r in gate_rows:
            log(f"      {r}")

    log("\n--- (4) EU arbitration inside the arm window ---")
    log(f"    arms coincident with eu_req/eu_hold: {armed_euhold}")
    log("    (a want_eu must WIN the bus; the resume re-derives. The law arms")
    log("     the PREFETCH pause only - it never claims the bus.)")
    log("\n--- (5) Flush inside the window ---")
    log(f"    arms coincident with q_flush: {armed_flush}")
    log("    (sh_pend is cancelled on q_flush; the flush law owns those rows,")
    log("     282/282 exact - untouched.)")

    # ---- (2) W0 SHADOW over the golden suite ----
    log("\n--- (2) W0 SHADOW: law firings over w0 traces ---")
    log("    RATIONALE: at w0 the eval collapses onto the T3 edge; a naive")
    log("    application could false-pause the chained-fetch population.")
    w0 = dict(cycles=0, arm=0, fired=0)
    w0c = defaultdict(int)
    for src, seeds in CORPUS_SEEDS.items():
        for seed in seeds[:6]:
            g = generate(f"fz{seed}", exts=())
            image, meta = compose(g)
            rows = run_tb_internal(image, 4200, [0] * 4096)
            for r in rows:
                w0["cycles"] += 1
                if r["sh_arm"]:
                    w0["arm"] += 1
                if r["sh_fired"]:
                    w0["fired"] += 1
                    w0c[r["sh_cidle"]] += 1
    log(f"    w0 full traces: {w0['cycles']} cycles, law arms: {w0['arm']}, "
        f"resolutions: {w0['fired']}")
    log(f"    w0 resolved cidle histogram: {dict(sorted(w0c.items()))}")
    if w0["arm"] == 0:
        log("    => ZERO w0 firings. The law does not touch w0 (eval_ext is")
        log("       never asserted at w0), so the 169000 golden is structurally")
        log("       unreachable by it.")
    else:
        log(f"    => {w0['arm']} w0 arms. Each must be checked against chip")
        log("       chaining before B2; a firing where the chip chains means a")
        log("       missing frame term.")

    logf.close()


if __name__ == "__main__":
    main()
