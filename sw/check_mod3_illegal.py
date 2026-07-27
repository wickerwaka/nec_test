#!/usr/bin/env python3
"""check_mod3_illegal - standing gate for the task #30 LEA mod=11 fix.

Replays the board-emitted mod3_illegal tranche (tests/v30/mod3_illegal) against
the current-RTL Verilator core and asserts:

  1. CYCLE ROWS EXACT - the 5-row no-bus-access fall-through window matches the
     chip golden byte-for-byte (busstat/tstate/qop/qbyte). This is the primary
     cycle-accuracy gate.
  2. ARCH CONFINED - the only architectural difference vs the chip is the LEA
     destination register (the stale-EA-latch residue the behavioural core
     cannot reproduce across all contexts). If ANYTHING else differs, FAIL (a
     real regression, not the documented residue).
  3. MOFFS EXACT - in a moffs preceding-context (MOV [imm16],AW then LEA), the
     core loads the EXACT chip value (the accept rule's residue is not needed).

PASS proves the wedge is gone, the timing is chip-exact, and every value
mismatch is the documented dest-register residue covered by fuzz_accept.lea_mod3.
"""
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                        # noqa: E402
import check_seq                                        # noqa: E402
import emit_suite as es                                 # noqa: E402
from v30run import parse_result                         # noqa: E402

TRANCHE = SW.parent / "tests" / "v30" / "mod3_illegal"
NEC = {"ax": "AW", "bx": "BW", "cx": "CW", "dx": "DW", "sp": "SP", "bp": "BP",
       "si": "IX", "di": "IY", "cs": "PS", "ds": "DS0", "es": "DS1",
       "ss": "SS", "ip": "PC", "flags": "PSW"}
R16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]


def _run(regs, instr):
    img, meta = testimage.compose(regs=regs, instr=bytes(instr))
    recs = check_seq.run_tb(img, 4200, waits=0)
    recs = [dict(r, idx=i) for i, r in enumerate(recs)]
    return recs, meta


def main():
    gold = json.loads(gzip.decompress((TRANCHE / "goldens.json.gz").read_bytes()))
    meta = json.loads((TRANCHE / "metadata.json").read_text())
    bad_cycles = bad_arch = 0
    exact_val = residue_val = 0
    for t in gold:
        ireg = {NEC[k]: v for k, v in t["initial"]["regs"].items()}
        recs, cmeta = _run(ireg, t["bytes"])
        rows, ev, i0, i1, q0, qf, fe, mr = es.build_rows(
            recs, cmeta["anchor_linear"], n_skip_f=0, n_close=1)
        gc = t["cycles"]
        # 1. cycle rows exact (busstat/tstate/qop/qbyte)
        if len(gc) != len(rows) or any(gc[i][7:11] != rows[i][7:11]
                                       for i in range(len(gc))):
            bad_cycles += 1
            if bad_cycles <= 3:
                print(f"  CYCLE MISMATCH {t['name']}: golden {len(gc)} core "
                      f"{len(rows)} rows")
            continue
        # 2. arch confined to the LEA dest reg
        arch = parse_result(recs, cmeta)["regs"]
        reg = R16[(t["bytes"][1] >> 3) & 7]
        want_dest = t["final"]["regs"].get(reg, t["initial"]["regs"][reg])
        got_dest = arch.get(NEC[reg])
        if got_dest == want_dest:
            exact_val += 1
        else:
            residue_val += 1
        # anything OTHER than the dest reg differing = real regression
        for ik, nk in NEC.items():
            if ik in ("ip", "cs", reg):
                continue
            want = t["final"]["regs"].get(ik, t["initial"]["regs"].get(ik))
            got = arch.get(nk)
            if got is not None and want is not None and got != want:
                bad_arch += 1
                if bad_arch <= 3:
                    print(f"  ARCH LEAK {t['name']}: {ik} chip {want:#x} "
                          f"core {got:#x} (not the LEA dest)")
                break

    # 3. moffs-context exact value
    moffs_ok = moffs_tot = 0
    regs = {"PS": 0, "PC": 0x0500, "SS": 0, "SP": 0x3F00, "DS0": 0x1000,
            "DS1": 0, "PSW": 0xF002, "AW": 0x1111, "BW": 0, "CW": 0, "DW": 0,
            "BP": 0, "IX": 0x7777, "IY": 0x8888}
    for pre, ea in ((b"\xA3\x34\x12", 0x1234), (b"\xA3\xEF\xBE", 0xBEEF)):
        recs, cmeta = _run(regs, pre + b"\x8D\xF7")   # MOV[imm],AW ; LEA SI,DI
        si = parse_result(recs, cmeta)["regs"].get("IX")
        moffs_tot += 1
        if si == ea:
            moffs_ok += 1
        else:
            print(f"  MOFFS MISMATCH: LEA after MOV[{ea:04x}] -> SI {si:#x}")

    ok = bad_cycles == 0 and bad_arch == 0 and moffs_ok == moffs_tot
    print(f"\ncheck_mod3_illegal: {'PASS' if ok else 'FAIL'} | "
          f"{len(gold)} goldens: cycle-exact {len(gold)-bad_cycles}/{len(gold)}, "
          f"arch-confined {len(gold)-bad_arch}/{len(gold)} "
          f"(value exact {exact_val}, residue {residue_val}); "
          f"moffs-exact {moffs_ok}/{moffs_tot}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
