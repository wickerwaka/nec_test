#!/usr/bin/env python3
"""Save-state v2 structural lint (standing gate, run alongside G1'/G2'/G4').

Mechanises the "lint-grep symbol counts" invariant so a mis-swap of the
addressed register-file interface (a dropped read arm, a duplicated write arm,
a count drift vs the package) fails loudly in CI instead of surfacing as a
silent restore divergence.

Checks:
  1. Every SSA_B_* symbol declared in the package appears EXACTLY twice in
     v30_biu.sv (once in the registered read mux, once in the write decode),
     and every SSA_E_* EXACTLY twice in v30_eu.sv. A count != 2 means a missing
     or duplicated read/write arm.
  2. Region counts match the package: 82 BIU + 119 EU + 1 tag = 202 (SS_COUNT).
  3. The declared SSA_* symbol sets are exactly the ones referenced by the RTL
     (no orphan address constants, no undeclared references).
  4. Package header constants: SS_VERSION == 0x02, SS_COUNT == 202,
     SS_TAG == {SS_VERSION, SS_COUNT} == 0x02CA.

Exit 0 = clean, non-zero = a listed violation. No build required.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "hdl/rtl/core/v30_ss_pkg.sv"
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"
EU = ROOT / "hdl/rtl/core/v30_eu.sv"

EXPECT = {
    "SS_VERSION": 0x02,
    "SS_BIU_COUNT": 82,
    "SS_EU_COUNT": 119,
    "SS_COUNT": 202,
    "SS_TAG": 0x02CA,
}


def declared(pkg_text, prefix):
    # localparam declarations of address constants: `localparam ... SSA_B_FOO = 9'h...;`
    return sorted(set(re.findall(rf"\b({prefix}[A-Z0-9_]+)\s*=", pkg_text)))


def refs(rtl_text, prefix):
    counts = {}
    for m in re.findall(rf"\b({prefix}[A-Z0-9_]+)\b", rtl_text):
        counts[m] = counts.get(m, 0) + 1
    return counts


def main():
    errs = []
    pkg = PKG.read_text()

    # --- header constants ---
    # Literals parsed directly; SS_COUNT and SS_TAG are derived expressions in
    # the package, so recompute them from the parts and check the arithmetic.
    def lit(name, base):
        m = re.search(rf"\b{name}\s*=\s*(?:\d+'[hH])?([0-9A-Fa-f]+)", pkg)
        return int(m.group(1), base) if m else None

    ver = lit("SS_VERSION", 16)
    biu_n = lit("SS_BIU_COUNT", 10)
    eu_n = lit("SS_EU_COUNT", 10)
    got = {
        "SS_VERSION": ver,
        "SS_BIU_COUNT": biu_n,
        "SS_EU_COUNT": eu_n,
        "SS_COUNT": (1 + biu_n + eu_n) if (biu_n and eu_n) else None,
    }
    got["SS_TAG"] = ((ver << 8) | got["SS_COUNT"]) if (
        ver is not None and got["SS_COUNT"]) else None
    for name, want in EXPECT.items():
        if got[name] != want:
            errs.append(f"constant {name} = {got[name]} (expected {want})")

    # --- per-region symbol / ref invariant ---
    for prefix, rtl, region, want_n in (
        ("SSA_B_", BIU, "BIU", EXPECT["SS_BIU_COUNT"]),
        ("SSA_E_", EU, "EU", EXPECT["SS_EU_COUNT"]),
    ):
        decl = declared(pkg, prefix)
        if len(decl) != want_n:
            errs.append(f"{region}: {len(decl)} {prefix} symbols declared "
                        f"(expected {want_n})")
        ref = refs(rtl.read_text(), prefix)
        # declared but not referenced exactly twice
        for sym in decl:
            n = ref.get(sym, 0)
            if n != 2:
                errs.append(f"{region}: {sym} referenced {n}x in "
                            f"{rtl.name} (expected 2: read arm + write arm)")
        # referenced but not declared (orphan)
        for sym in ref:
            if sym not in decl:
                errs.append(f"{region}: {sym} referenced in {rtl.name} "
                            f"but not declared in package")
        print(f"{region}: {len(decl)} symbols, each x2 in {rtl.name} "
              f"-> {'OK' if not any(region in e for e in errs) else 'FAIL'}")

    if errs:
        print("\nss_lint: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("ss_lint: PASS (82x2 BIU + 119x2 EU + tag = 202; constants OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
