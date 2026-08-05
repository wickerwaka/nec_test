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
  2. Region counts match the package: 82 BIU + 120 EU + 1 tag = 203 (SS_COUNT).
  3. The declared SSA_* symbol sets are exactly the ones referenced by the RTL
     (no orphan address constants, no undeclared references).
  4. Package header constants: SS_VERSION == 0x03, SS_COUNT == 203,
     SS_TAG == {SS_VERSION, SS_COUNT} == 0x03CB.
  5. (via sw/ss_flopcensus.py, invoked here) the FLOP-CENSUS-vs-MAP invariant:
     every architectural flop declared in the RTL is SSA_-mapped or whitelisted
     -- closing the "new unmapped flop passes vacuously" blind spot booked in
     docs/notes/standing_gates.md (meta-finding #3).

Exit 0 = clean, non-zero = a listed violation. No build required.

--core {fsm,ucore}
------------------
Two cores, two maps, one lint. `--core fsm` (default) is the standing gate and
its output is byte-stable. `--core ucore` audits hdl/rtl/ucore's map.

The ucore's EU is SPLIT ACROSS `.svh` INCLUDES -- both save arms
(v30u_eu_ss_read.svh / v30u_eu_ss_write.svh) live in includes, and so does most
of the state that is mapped. A symbol reached only from an include is still
mapped, so the includes MUST be in the scanned set: scan the `.sv` alone and
every SSA_E_ symbol counts 0x and the census is vacuous, not clean.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UCORE = ROOT / "hdl/rtl/ucore"

CORES = {
    "fsm": {
        "pkg": ROOT / "hdl/rtl/core/v30_ss_pkg.sv",
        "biu": [ROOT / "hdl/rtl/core/v30_biu.sv"],
        "eu": [ROOT / "hdl/rtl/core/v30_eu.sv"],
        "expect": {
            "SS_VERSION": 0x03,   # v3: +SSA_E_LAST_EA (task #30 LEA-mod3 latch)
            "SS_BIU_COUNT": 82,
            "SS_EU_COUNT": 120,
            "SS_COUNT": 203,
            "SS_TAG": 0x03CB,     # (0x03 << 8) | 203
        },
    },
    "ucore": {
        "pkg": UCORE / "v30u_ss_pkg.sv",
        "biu": [UCORE / "v30u_biu.sv"],
        # the EU body and BOTH save arms are in the includes -- see the note
        # in the module docstring; omitting them makes the EU census vacuous.
        "eu": [UCORE / "v30u_eu.sv"] + sorted(UCORE.glob("v30u_eu_*.svh")),
        "expect": {
            # SM3 sitting 3 / F52: map v3.  H1's recognition floor is four new
            # BIU flops (bnd_pending, bnd_arm, bnd_stamp, bnd_cnt), appended at
            # 0x066-0x069 -- addresses added, so the version moves again.
            # v2 was 0x82 / 101 / 116 / 218 / 0x82DA;
            # v1 was 0x81 /  96 / 115 / 212 / 0x81D4.
            # SM3 sitting 11: v3 -> v4.  H1's four `bnd_*` BIU flops are DELETED
            # (the recognition floor is one term on the EU's IE gate now), so
            # 0x066-0x069 leave the map.  Removing addresses moves the version
            # for the same reason adding them does.
            # SM3 sitting 21 / F56: v4 -> v5.  `pf_land` is DELETED (M6 is
            # refuted by its own firing census and is gone from both engines),
            # so SSA_B_PF_LAND / 0x038 leaves the map.  It is the first
            # MID-REGION retirement: the code is a HOLE `ss_addr_of` steps
            # over and NO symbol is renumbered.
            # SM3 sitting 25 / §86: v5 -> v6.  The BRK/TF single-step arm
            # APPENDS one EU address, SSA_E_BRK at 0x174 -- seven bits carrying
            # the TF pipeline `brk_p[3:0]`, the ARM itself, its sample-instant
            # pulse `brk_smp` and the trap's kind bit `irq_sel_brk`.  Same rule
            # and same reason as every append before it.
            "SS_VERSION": 0x86,   # ucore map v6 (0x80 family: never an FSM stream)
            "SS_BIU_COUNT": 100,
            "SS_EU_COUNT": 117,
            "SS_COUNT": 218,
            "SS_TAG": 0x86DA,     # (0x86 << 8) | 218
        },
    },
}


def declared(pkg_text, prefix):
    # localparam declarations of address constants: `localparam ... SSA_B_FOO = 9'h...;`
    return sorted(set(re.findall(rf"\b({prefix}[A-Z0-9_]+)\s*=", pkg_text)))


def refs(rtl_text, prefix):
    counts = {}
    for m in re.findall(rf"\b({prefix}[A-Z0-9_]+)\b", rtl_text):
        counts[m] = counts.get(m, 0) + 1
    return counts


def field_widths(pkg_text):
    """The `ss_field_width` case arms: symbol -> declared width."""
    return {sym: int(w) for sym, w in re.findall(
        r"\b(SSA_[BE]_[A-Z0-9_]+)\s*:\s*ss_field_width\s*=\s*(\d+)\s*;",
        pkg_text)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", choices=tuple(CORES), default="ucore",
                    help="which core's save-state map to lint (default: ucore "
                         "since 2026-08-04; 'fsm' is the ARCHIVED core's map, "
                         "still linted on demand - "
                         "docs/notes/fsm_core_archive_2026-08-04.md)")
    args = ap.parse_args()
    cfg = CORES[args.core]
    PKG, EXPECT = cfg["pkg"], cfg["expect"]

    errs = []
    pkg = PKG.read_text()
    widths = field_widths(pkg)

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
    for prefix, rtls, region, want_n in (
        ("SSA_B_", cfg["biu"], "BIU", EXPECT["SS_BIU_COUNT"]),
        ("SSA_E_", cfg["eu"], "EU", EXPECT["SS_EU_COUNT"]),
    ):
        # one region may be spread over several files (the ucore EU is split
        # across its .svh includes, and BOTH save arms live in them).
        name = rtls[0].name if len(rtls) == 1 else \
            f"{rtls[0].name} +{len(rtls) - 1} includes"
        decl = declared(pkg, prefix)
        if len(decl) != want_n:
            errs.append(f"{region}: {len(decl)} {prefix} symbols declared "
                        f"(expected {want_n})")
        ref = {}
        for rtl in rtls:
            for sym, n in refs(rtl.read_text(), prefix).items():
                ref[sym] = ref.get(sym, 0) + n
        # declared but not referenced exactly twice
        for sym in decl:
            n = ref.get(sym, 0)
            if n != 2:
                errs.append(f"{region}: {sym} referenced {n}x in "
                            f"{name} (expected 2: read arm + write arm)")
        # referenced but not declared (orphan)
        for sym in ref:
            if sym not in decl:
                errs.append(f"{region}: {sym} referenced in {name} "
                            f"but not declared in package")
        # WIDTH COVERAGE (static half of --ss-mode 5): a symbol with no
        # `ss_field_width` arm falls through to `default: 0`, and mode 5 then
        # SKIPS it silently -- the failure mode that hid the ucore's whole EU
        # half (provenance sec.42.2). A zero width is the same hole.
        for sym in decl:
            w = widths.get(sym)
            if w is None:
                errs.append(f"{region}: {sym} has no ss_field_width arm "
                            f"(falls through to default 0; --ss-mode 5 skips it)")
            elif w <= 0:
                errs.append(f"{region}: {sym} has ss_field_width {w}")

        print(f"{region}: {len(decl)} symbols, each x2 in {name} "
              f"-> {'OK' if not any(region in e for e in errs) else 'FAIL'}")

    if errs:
        print("\nss_lint: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"ss_lint: PASS ({EXPECT['SS_BIU_COUNT']}x2 BIU + "
          f"{EXPECT['SS_EU_COUNT']}x2 EU + tag = {EXPECT['SS_COUNT']}; "
          f"constants OK)")

    # --- flop-census-vs-map (sibling check; the unmapped-flop blind-spot fix) ---
    print()
    sys.stdout.flush()
    census = subprocess.run(
        [sys.executable, str(ROOT / "sw/ss_flopcensus.py"), "--core", args.core])
    if census.returncode != 0:
        print("ss_lint: FAIL (flop census)")
        return census.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
