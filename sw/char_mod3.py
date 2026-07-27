#!/usr/bin/env python3
"""char_mod3 - directed board characterization of the illegal mod=11
(register-operand) forms of the four memory-operand-REQUIRED opcodes that
wedge v30_core at S_HALT (task #30): LEA (0x8D), BOUND/CHKIND (0x62),
LES (0xC4), LDS (0xC5).

The socket-emit corpora exclude these (emit_suite.gen_case forces mod<3 for
lea/memonly), and even the SingleStepTests V20 oracle has zero mod=11 cases, so
the chip's defined behaviour is unknown. This emits a directed tranche straight
from the socket (EMIT_USE_CORE=False, the standard emit flow via emit_case) so
the fix can match it cycle-for-cycle. It also probes the classic "LEA reg loads
the stale EA latch" hypothesis by varying the instruction that precedes LEA.

Freezes tests/v30/mod3_illegal/{goldens.json, metadata.json}.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import emit_suite as es                                 # noqa: E402
from emit_suite import emit_case, OPCODES               # noqa: E402
from v30run import RunError                             # noqa: E402
from testimage import ComposeError                      # noqa: E402

OUT = SW.parent / "tests" / "v30" / "mod3_illegal"
OPS = ["8D", "62", "C4", "C5"]

# two known register setups so value-dependence is interpretable
SETUPS = [
    {"ax": 0x1111, "cx": 0x2222, "dx": 0x3333, "bx": 0x4444, "sp": 0x3F00,
     "bp": 0x6666, "si": 0x7777, "di": 0x8888, "cs": 0x0000, "ip": 0x0500,
     "ds": 0x1000, "es": 0x2000, "ss": 0x3000, "flags": 0xF002},
    {"ax": 0xF00D, "cx": 0x0BAD, "dx": 0xBEEF, "bx": 0xCAFE, "sp": 0x3F00,
     "bp": 0x1234, "si": 0x5678, "di": 0x9ABC, "cs": 0x0000, "ip": 0x0500,
     "ds": 0x4000, "es": 0x5000, "ss": 0x6000, "flags": 0xF002},
]


def _case(op_bytes, modrm, regs, name, pre=b""):
    """Build an emit_suite case dict directly (mod3, no memory operand)."""
    instr = pre + bytes(op_bytes) + bytes([modrm])
    return {"regs": dict(regs), "instr": instr, "ram": [], "name": name,
            "ivt": None,
            "next_ip": (regs["ip"] + len(instr)) & 0xFFFF, "next_cs": None}


def characterize(host, sweep_setups=2):
    goldens = []
    fails = []
    idx = 0
    t0 = time.time()
    for key in OPS:
        spec = OPCODES[key]
        opb = spec["base"]
        for si in range(sweep_setups):
            regs = SETUPS[si]
            for modrm in range(0xC0, 0x100):
                reg = (modrm >> 3) & 7
                rm = modrm & 7
                nm = f"{key} mod3 /{reg} rm{rm} setup{si}"
                case = _case(opb, modrm, regs, nm)
                try:
                    t = emit_case(spec, case, host, tag="m3")
                    t["idx"] = idx
                    t["meta_key"] = key
                    goldens.append(t)
                except (RunError, ComposeError) as e:
                    fails.append((key, modrm, si, str(e)[:80]))
                idx += 1
        print(f"  {key}: swept, running total {len(goldens)} goldens "
              f"({len(fails)} fails) [{time.time()-t0:.0f}s]", flush=True)

    # LEA stale-EA-latch probe: vary the instruction preceding LEA SI,rm.
    # A3 imm16 = MOV [imm16],AW (EA latch = imm16); 90 = NOP (no EA);
    # 89 06 imm16 = MOV [imm16],AW too. If LEA-target reg == the preceding EA,
    # the stale-latch hypothesis holds.
    regs = SETUPS[0]
    for pre, pdesc, expect in (
            (bytes([0xA3, 0x34, 0x12]), "MOV [1234h],AW", 0x1234),
            (bytes([0xA3, 0xEF, 0xBE]), "MOV [BEEFh],AW", 0xBEEF),
            (bytes([0x90]), "NOP (no EA)", None),
            (bytes([0x88, 0x06, 0x78, 0x56]), "MOV [5678h],AL", 0x5678)):
        # LEA SI, rm=DI (modrm 0xF7): reg=110(si) rm=111(di)
        case = _case([0x8D], 0xF7, regs,
                     f"LEA-stale after {pdesc}", pre=pre)
        try:
            t = emit_case(OPCODES["8D"], case, host, tag="m3s")
            t["idx"] = idx
            t["meta_key"] = "8D-stale"
            t["stale_pre"] = pdesc
            t["stale_expect_ea"] = expect
            goldens.append(t)
        except (RunError, ComposeError) as e:
            fails.append(("8D-stale", 0xF7, pdesc, str(e)[:80]))
        idx += 1

    return goldens, fails


def analyze(goldens):
    """Summarise the chip behaviour per opcode: fall-through vs trap, which
    registers change, and cycle counts."""
    from collections import defaultdict
    print("\n=== behaviour summary ===")
    by = defaultdict(list)
    for t in goldens:
        by[t["meta_key"]].append(t)
    for key, ts in by.items():
        # which final regs change (besides ip)
        changed = defaultdict(int)
        cyc = []
        for t in ts:
            for r in t["final"]["regs"]:
                if r != "ip":
                    changed[r] += 1
            cyc.append(len(t["cycles"]))
        cyc.sort()
        print(f"  {key}: n={len(ts)} | regs-changed {dict(changed)} | "
              f"cycle-rows min={cyc[0]} med={cyc[len(cyc)//2]} max={cyc[-1]}")
    # stale-EA verdict
    stale = [t for t in goldens if t.get("meta_key") == "8D-stale"]
    if stale:
        print("  --- LEA stale-EA-latch probe ---")
        for t in stale:
            fr = t["final"]["regs"]
            si_final = fr.get("si", "unchanged")
            print(f"    {t['stale_pre']}: SI_final={si_final if si_final=='unchanged' else hex(si_final)} "
                  f"(expect stale EA {hex(t['stale_expect_ea']) if t['stale_expect_ea'] is not None else '-'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--setups", type=int, default=2)
    ap.add_argument("--freeze", action="store_true",
                    help="write the frozen tranche to tests/v30/mod3_illegal/")
    a = ap.parse_args()
    goldens, fails = characterize(a.host, a.setups)
    print(f"\ncharacterized {len(goldens)} goldens, {len(fails)} fails")
    for f in fails[:20]:
        print("  FAIL:", f)
    analyze(goldens)
    if a.freeze:
        OUT.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT / "goldens.json.gz", "wt") as fh:
            json.dump(goldens, fh)
        meta = {
            "experiment": "task #30 illegal mod=11 (register operand) forms of "
                          "the memory-operand-required opcodes LEA/BOUND/LES/LDS",
            "rig": "sw/char_mod3.py",
            "truth_source": "SOCKET (real chip, use_core=False; EMIT_USE_CORE pin)",
            "opcodes": OPS,
            "modrm_range": "0xC0-0xFF (mod=11, all reg/rm)",
            "setups": SETUPS,
            "n_goldens": len(goldens),
            "n_fails": len(fails),
            "fails": fails,
            "date": time.strftime("%Y-%m-%d"),
            "note": "The v30_core wedges (S_HALT park) on these forms; the chip "
                    "does not. These goldens are the fix's cycle-accuracy gate. "
                    "Emitted because emit_suite.gen_case forces mod<3 for "
                    "lea/memonly and the V20 SingleStepTests oracle has zero "
                    "mod=11 cases for these opcodes (universal vacuity).",
        }
        (OUT / "metadata.json").write_text(json.dumps(meta, indent=1))
        print(f"\nfroze {len(goldens)} goldens -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
