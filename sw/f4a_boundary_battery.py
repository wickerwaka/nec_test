#!/usr/bin/env python3
"""F4a directed segment-boundary battery (standing regression set).

Covers the six+ witnessed multi-word-operand consumers of ea_step2 at operand
EA offsets 0xFFFC-0xFFFF (where a linear +2 would carry across FFFF->0000 into
the segment base -- the F4a bug). This runs REGARDLESS of the assertion ruling
(architect chose the source-level ea_step_lint over a runtime assertion).

Oracle = the real v0.3 chip goldens for the boundary cases that exist in the
suite; each must pass three-way (cyc+arch). Consumers with NO boundary case in
v0.3 are reported as COVERAGE GAPS to be filled by the L6 silicon wrap mini-
tranche (directed offsets 0xFFFC-0xFFFF, ~40/form, socket).

Standing gate: exit non-zero if any in-suite boundary case diverges.
"""
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_core as CC  # noqa: E402

V03 = CC.ROOT / "tests" / "v30" / "v0.3"
BND = set(range(0xFFFC, 0x10000))


def modrm_ea(b, r, disp_start):
    """16-bit EA offset for a mem-operand modrm form (None for reg-form)."""
    mrm = b[1]
    mod = mrm >> 6
    rm = mrm & 7
    if mod == 3:
        return None
    base = {0: r["bx"] + r["si"], 1: r["bx"] + r["di"], 2: r["bp"] + r["si"],
            3: r["bp"] + r["di"], 4: r["si"], 5: r["di"], 6: r["bp"],
            7: r["bx"]}[rm]
    if mod == 0 and rm == 6:
        base = b[disp_start] | (b[disp_start + 1] << 8)
    elif mod == 1:
        base = base + ((b[disp_start] ^ 0x80) - 0x80)
    elif mod == 2:
        base = base + (b[disp_start] | (b[disp_start + 1] << 8))
    return base & 0xFFFF


# consumer -> how to derive the multi-word operand EA offset
MODRM_FORMS = {"FF.3": 2, "FF.5": 2, "C4": 2, "C5": 2, "62": 2}
REG_FORMS = {"0F31": "di", "0F33": "si", "0F39": "di", "0F3B": "si"}


def boundary_idxs(form):
    fn = V03 / f"{form}.json.gz"
    if not fn.exists():
        return None
    g = json.load(gzip.open(fn))
    if form in MODRM_FORMS:
        ds = MODRM_FORMS[form]
        return [c["idx"] for c in g
                if (modrm_ea(c["bytes"], c["initial"]["regs"], ds) in BND)], g
    reg = REG_FORMS[form]
    return [c["idx"] for c in g
            if (c["initial"]["regs"][reg] & 0xFFFF) in BND], g


def run_three_way(form, cases):
    td = tempfile.mkdtemp()
    b = f"{td}/b"
    CC.compose_batch(cases, b)
    subprocess.run([str(CC.BIN), f"+batch={b}", f"+out={td}/o", "+waits=0",
                    "+ce_div=1"], cwd=CC.ROOT, capture_output=True, text=True)
    sims = CC.parse_out(f"{td}/o")
    bad = []
    for c in cases:
        res = CC.check_case(c, sims.get(c["idx"]), 0xFFFF)
        reg_bad = [k for k in CC.REGS
                   if (dict(c["initial"]["regs"], **c["final"]["regs"]).get(k)
                       != (sims.get(c["idx"], {}).get("final") or {}).get(k))]
        if not res["cycles_ok"] or reg_bad or res["ram_bad"]:
            bad.append(c["idx"])
    return bad


def main():
    fails = 0
    gaps = []
    for form in list(MODRM_FORMS) + list(REG_FORMS):
        r = boundary_idxs(form)
        if r is None:
            print(f"  {form}: (no v0.3 file)")
            continue
        idxs, g = r
        if not idxs:
            gaps.append(form)
            print(f"  {form}: 0 boundary cases in v0.3 -> COVERAGE GAP "
                  f"(fill in L6 silicon mini-tranche)")
            continue
        byidx = {c["idx"]: c for c in g}
        bad = run_three_way(form, [byidx[i] for i in idxs])
        status = "PASS" if not bad else f"FAIL {bad}"
        fails += len(bad)
        print(f"  {form}: {len(idxs)} boundary case(s) {idxs} -> {status}")
    print()
    if gaps:
        print("COVERAGE GAPS (no v0.3 boundary case; L6 silicon mini-tranche): "
              + ", ".join(gaps))
    if fails:
        print(f"f4a_boundary_battery: FAIL ({fails} diverging)")
        return 1
    print("f4a_boundary_battery: PASS (all in-suite 0xFFFC-0xFFFF operand "
          "boundary cases three-way clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
