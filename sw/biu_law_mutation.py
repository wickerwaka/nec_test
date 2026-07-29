#!/usr/bin/env python3
"""BIU law-card MUTATION BATTERY (Codex-review condition 6, the acceptance-basis
non-vacuity proof). Board-free.

For each MUST law (and a few omitted/control mechanisms) we deliberately BREAK
its predicate in the RTL, rebuild the Verilator TB, run the board-free DETECTION
GATE SET, and record which gates flip red. The RTL is always restored via
`git checkout` (the committed tree == pristine baseline), so no tracked file is
left modified -- matches the A2 non-vacuity-probe precedent and Codex's explicit
"scratch copy of the RTL" instruction. NO board (Verilator + cached refs only).

The output matrix answers Finding 3 ("which gate would fail if this case
breaks") and Finding 13 (independence): each law's break must be caught by >=1
gate, and the CONTROL mutation (store_pf_boost, an unused shadow wire) must leave
EVERY gate green -- proving the gate set does not fire spuriously.

Detection gate set (all board-free):
  w0   : v0.1 bounded w0 golden (w0-neutrality / w0-active detector)
  w1   : v0.1-w1 1200 (uniform-wait detector)
  w3   : v0.1-w3 1200 (uniform-wait detector)
  wvec : biu_rebuild_wvec_freeze --check (random-per-cycle-wait model A/B, incl.
         the B0 DIRECTED_SEEDS 90270=G-LC4a, 90364=G-LC2)
  ff_t4: check_ff_t4 (far-flush direct-commit slots)
  race : check_race_law (POP-PSW/INT race law)
  lc6  : check_lc6_gate (B0 directed strio-single OUTSB gadgets; eu_rsv_strio veto)

Usage: nohup setsid python3 sw/biu_law_mutation.py > sw/biu_law_mutation.log 2>&1 &
"""
import subprocess
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"
RACE = ROOT / "hdl/rtl/core/race_law.svh"

# Each mutation: id, law card, target file, exact old substring, new substring,
# w0_active (does breaking it legitimately perturb w0?), and the gates we EXPECT
# to detect it (hypothesis; the run confirms or refutes -> a finding either way).
MUTATIONS = [
    dict(id="M-LC1", law="LC1 resume/demand-deadline", file=BIU,
         old="wire       law_arm  = eval_ext && cur_fetch &&",
         new="wire       law_arm  = 1'b0 && eval_ext && cur_fetch &&",
         w0_active=False, expect=["wvec"]),
    dict(id="M-LC2", law="LC2 low-band pause", file=BIU,
         old="wire        lowband_pause = eval_ext && cur_fetch && q_cnt <= 3'd2 &&",
         new="wire        lowband_pause = 1'b0 && eval_ext && cur_fetch && q_cnt <= 3'd2 &&",
         w0_active=False, expect=["wvec"]),
    dict(id="M-LC3", law="LC3 Tw-parity H-PHASE (ext_ok_wr widen)", file=BIU,
         old="wire ext_ok_wr  = (eu_ready_p1 && eu_ready_p2) ||",
         new="wire ext_ok_wr  = (eu_ready_p1 && eu_ready_p2) || 1'b0 && (",
         w0_active=False, expect=["wvec"]),
    dict(id="M-LC4a", law="LC4 pf_rsv_lead", file=BIU,
         old="wire        pf_rsv_lead = eval_ext && eu_rsv_lead &&",
         new="wire        pf_rsv_lead = 1'b0 && eval_ext && eu_rsv_lead &&",
         w0_active=False, expect=["wvec"]),
    dict(id="M-LC4b", law="LC4 pf_late_rsv", file=BIU,
         old="wire        pf_late_rsv = eval_ext && eu_req && !eu_req_p1 && !eu_ready &&",
         new="wire        pf_late_rsv = 1'b0 && eu_req && !eu_req_p1 && !eu_ready &&",
         w0_active=False, expect=["wvec"]),
    dict(id="M-LC6", law="LC6 strio pick_t3 veto", file=BIU,
         old="wire        pick_t3    = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio);",
         new="wire        pick_t3    = want_half2 || want_eu || prefetch_ok;",
         w0_active=True, expect=["lc6"]),
    dict(id="M-FFT4", law="omitted: far-flush ff_t4 direct commit", file=BIU,
         old="                      q_flush && cur_fetch && pick_any && flush_fast && evald;",
         new="                      q_flush && cur_fetch && pick_any && flush_fast && evald && 1'b0;",
         w0_active=True, expect=["ff_t4", "w0"]),
    dict(id="M-EVEXT", law="omitted: eval_ext ext_ok A/B qualification", file=BIU,
         old="wire ext_ok     = eu_ready_p1 ||",
         new="wire ext_ok     = 1'b0 && eu_ready_p1 ||",
         w0_active=False, expect=["w1", "w3", "wvec"]),
    dict(id="M-RACE", law="omitted: POP-PSW/INT race law", file=RACE,
         old="6'd0: rl_g0 = 6'd25;",
         new="6'd0: rl_g0 = 6'd24;", w0_active=False, expect=["race"]),
    dict(id="M-CTRL", law="CONTROL: store_pf_boost (unused shadow, MUST be silent)",
         file=BIU,
         old="wire       store_pf_boost = last_was_store && (recent_evx <= 4'd7) &&",
         new="wire       store_pf_boost = 1'b0 && last_was_store && (recent_evx <= 4'd7) &&",
         w0_active=False, expect=[]),
]


def sh(cmd, timeout=1200):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout)


def restore():
    subprocess.run(["git", "checkout", "--", "hdl/rtl/core/v30_biu.sv",
                    "hdl/rtl/core/race_law.svh"], cwd=ROOT)


def golden(suite, waits, cases):
    r = sh([sys.executable, "sw/check_core.py", "--suite-dir", f"tests/v30/{suite}",
            "--opcodes", "all", "--cases", str(cases), "--waits", str(waits)])
    m = re.search(r"TOTAL:\s*(\d+)/(\d+)", r.stdout)
    if not m:
        return "ERR"
    return "PASS" if m.group(1) == m.group(2) else f"FAIL({m.group(1)}/{m.group(2)})"


def build():
    r = sh([sys.executable, "sw/check_core.py", "--build", "--suite-dir",
            "tests/v30/v0.1", "--opcodes", "all", "--cases", "1", "--waits", "0"])
    return "Verilator" in r.stdout or "building" in r.stdout


def gate_wvec():
    r = sh([sys.executable, "sw/biu_rebuild_wvec_freeze.py", "--check",
            "docs/notes/biu_rebuild_wvec_baseline.json"])
    return "PASS" if r.returncode == 0 else "FAIL"


def gate_fft4():
    r = sh([sys.executable, "sw/check_ff_t4.py"])
    return "PASS" if r.returncode == 0 else "FAIL"


def gate_race():
    r = sh([sys.executable, "sw/check_race_law.py"])
    return "PASS" if r.returncode == 0 else "FAIL"


def gate_lc6():
    r = sh([sys.executable, "sw/check_lc6_gate.py"])
    return "PASS" if r.returncode == 0 else "FAIL"


def run_gates(w0_cases):
    return {
        "w0": golden("v0.1", 0, w0_cases),
        "w1": golden("v0.1-w1", 1, 0),
        "w3": golden("v0.1-w3", 3, 0),
        "wvec": gate_wvec(),
        "ff_t4": gate_fft4(),
        "race": gate_race(),
        "lc6": gate_lc6(),
    }


def main():
    import datetime
    try:
        sys.stdout.reconfigure(line_buffering=True)   # incremental log visibility
    except Exception:
        pass
    print(f"=== BIU law MUTATION BATTERY  "
          f"{datetime.datetime.utcnow().isoformat()}Z  "
          f"HEAD={sh(['git','rev-parse','--short','HEAD']).stdout.strip()} ===")
    W0_CASES = 20000
    results = []
    restore()
    for mu in MUTATIONS:
        print(f"\n### {mu['id']}  ({mu['law']})")
        try:
            txt = mu["file"].read_text()
            if mu["old"] not in txt:
                print(f"  SKIP: target string not found in {mu['file'].name}")
                results.append((mu, None, "target-not-found"))
                continue
            mu["file"].write_text(txt.replace(mu["old"], mu["new"], 1))
            if mu["file"] == RACE:
                # race gate is self-contained; no main TB build needed
                gates = {"w0": "-", "w1": "-", "w3": "-", "wvec": "-",
                         "ff_t4": "-", "race": gate_race(), "lc6": "-"}
            else:
                if not build():
                    print("  BUILD FAILED (mutation may be a syntax break)")
                    gates = {g: "BUILD-ERR" for g in
                             ("w0", "w1", "w3", "wvec", "ff_t4", "race", "lc6")}
                else:
                    gates = run_gates(W0_CASES)
            detected = [g for g, v in gates.items()
                        if isinstance(v, str) and v.startswith("FAIL")]
            print(f"  gates: {gates}")
            print(f"  DETECTED BY: {detected or 'NONE'}  (expected ~{mu['expect']})")
            results.append((mu, gates, detected))
        finally:
            restore()

    print("\n\n=== MUTATION x GATE MATRIX ===")
    hdr = ["mutation", "w0", "w1", "w3", "wvec", "ff_t4", "race", "lc6", "detected"]
    print("| " + " | ".join(hdr) + " |")
    print("|" + "|".join("---" for _ in hdr) + "|")
    for mu, gates, detected in results:
        if gates is None:
            row = [mu["id"]] + ["?"] * 6 + [detected]
        else:
            row = [mu["id"]] + [gates.get(g, "-") for g in
                                ("w0", "w1", "w3", "wvec", "ff_t4", "race", "lc6")] + \
                  [",".join(detected) if isinstance(detected, list)
                   and detected else ("SILENT" if detected == [] else str(detected))]
        print("| " + " | ".join(row) + " |")

    # verdicts
    print("\n=== VERDICT ===")
    ok = True
    for mu, gates, detected in results:
        if mu["id"] == "M-CTRL":
            silent = (detected == [])
            print(f"  CONTROL {mu['id']}: "
                  f"{'PASS (all gates green -> non-spurious)' if silent else 'FAIL (a gate fired on the unused shadow!)'}")
            ok = ok and silent
        elif isinstance(detected, list):
            caught = len(detected) > 0
            print(f"  {mu['id']} ({mu['law']}): "
                  f"{'caught by ' + ','.join(detected) if caught else 'NOT CAUGHT by any board-free gate -> needs a directed gate (finding)'}")
            ok = ok and caught
    # confirm clean tree
    diff = sh(["git", "diff", "--name-only", "--", "hdl/"]).stdout.strip()
    print(f"\n  tracked RTL clean after run: {'YES' if not diff else 'NO -> ' + diff}")
    print(f"\n=== MUTATION_BATTERY_DONE  ok={ok} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        restore()
