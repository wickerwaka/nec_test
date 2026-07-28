#!/usr/bin/env python3
"""check_enter_nesting - standing gate for the task #31 ENTER fixes.

TWO tranches, both board-frozen (chip = ground truth, use_core=False), replayed
against the current-RTL Verilator core:

1. MASK tranche (tests/v30/enter_nesting/goldens.json.gz) - nesting 0..255 x 2
   BP/stack contexts at w0. Asserts the ENTER stack-frame WALK matches the chip:
     * push/copy COUNT in the stack region (0x2000..0x3fff) == chip (the full
       8-bit walk; a mod-32 mask would drop pushes for nesting>=32).
     * push/copy STREAM (ordered kind,addr,data) == chip byte-for-byte.
   Proves the nesting-mask bug is gone (task #31 first ENTER bug).

2. WAITED tranche (goldens_waited.json.gz) - a nesting set x uniform waits
   {0,1,2,3,7} + a wrand slice x 2 contexts. Guards the task #31 SECOND ENTER
   bug (the PUSH-BP drop under waits, fixed by gating pop_want on prep_acc):
     * WALK-STREAM STRICT at ALL waits - the stack-region MEMW/MEMR (kind,addr,
       data,order) == chip. This is the VALUE-bug invariant: a dropped BP push
       removes a MEMW. Holds at every wait (the w2 prefetch interleave, when
       present, only moves a CODE fetch, never the walk).
     * CYCLE-EXACT (full txn stream kind/addr/data/dur + active-cycle count ==
       chip) STRICT everywhere EXCEPT the metadata's enumerated known_divergences
       (the ENTER-walk-vs-prefetch interleave, booked to #33). Enumerated cells
       are COUNTED and REPORTED, never silently skipped; an UNEXPECTED cycle
       divergence (not in the known set) is a HARD FAIL, and a known cell that no
       longer diverges is reported as a stale exclusion.
"""
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                        # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import char_enter as ce                                 # noqa: E402

TRANCHE = SW.parent / "tests" / "v30" / "enter_nesting"
STK_LO, STK_HI = 0x2000, 0x3FFF
TB_WINDOW = ce.TB_WINDOW


# --------------------------------------------------------------------------- #
# 1. MASK tranche (w0, nesting 0..255) - the existing walk-stream check.
# --------------------------------------------------------------------------- #
def _mask_walk(rows):
    out = []
    for tx in fc.extract_txns(rows):
        k = fc.KIND[tx["kind"]]
        if k in ("MEMW", "MEMR") and STK_LO <= (tx["addr"] & 0xFFFF) <= STK_HI:
            out.append([k, tx["addr"] & 0xFFFF, tx.get("data")])
    return out


def check_mask():
    goldens = json.load(gzip.open(TRANCHE / "goldens.json.gz", "rt"))
    fails, checked, max_push = [], 0, 0
    for g in goldens:
        instr = (bytes([0xBD]) + int(g["bp"]).to_bytes(2, "little")
                 + bytes([0xC8]) + int(g["fsize"]).to_bytes(2, "little")
                 + bytes([g["nest"]]))
        image, _ = testimage.compose(regs={"BP": g["bp"], "SP": g["sp"]},
                                     instr=instr)
        rows = check_seq.run_tb(image, TB_WINDOW, waits=0)
        tb = _mask_walk(rows)
        chip = [[k, a, d] for k, a, d in g["digest"]["txns"]
                if STK_LO <= a <= STK_HI]
        checked += 1
        max_push = max(max_push, sum(1 for t in chip if t[0] == "MEMW"))
        if tb != chip:
            fails.append((g["ctx"], g["nest"]))
    ok = not fails
    print(f"  MASK (w0, nesting 0..255 x2): {'PASS' if ok else 'FAIL'} | "
          f"{checked} goldens | max stack pushes {max_push} (nest=255=>256) | "
          f"walk-mismatches {len(fails)}")
    for ctx, nest in fails[:12]:
        print(f"    ctx{ctx} nest={nest}: walk mismatch")
    return ok


# --------------------------------------------------------------------------- #
# 2. WAITED tranche - walk-stream strict + cycle-exact w/ known-divergence set.
# --------------------------------------------------------------------------- #
def _known_cell(meta, g):
    """The enumerated cycle-exact known-divergence entry matching (g), or None.
    A cell is [ctx, nest, waits] (waits an int; wrand cases are never enumerated
    exclusions - they are gated on walk-stream only)."""
    for kd in meta.get("known_divergences", []):
        for cell in kd.get("cells", []):
            if cell == [g["ctx"], g["nest"], g.get("waits")]:
                return kd
    return None


def check_waited():
    path = TRANCHE / "goldens_waited.json.gz"
    if not path.exists():
        print("  WAITED: MISSING goldens_waited.json.gz (run "
              "sw/char_enter.py --waited --freeze)")
        return False
    goldens = json.load(gzip.open(path, "rt"))
    meta = json.loads((TRANCHE / "metadata_waited.json").read_text())
    walk_fail, cyc_unexpected, known_hit, known_stale = [], [], [], []
    checked = 0
    for g in goldens:
        instr = ce.enter_case_instr(g["bp"], g["fsize"], g["nest"])
        image, m = testimage.compose(regs={"BP": g["bp"], "SP": g["sp"]},
                                     instr=instr)
        a16 = g.get("anchor16", m["anchor_linear"] & 0xFFFF)
        if "wrand" in g:
            rows = check_seq.run_tb(image, TB_WINDOW, wrand=tuple(g["wrand"]))
        else:
            rows = check_seq.run_tb(image, TB_WINDOW, waits=g["waits"])
        tb_full = ce.full_txns(rows, a16)
        tb_active = ce.active_count(rows)
        checked += 1
        wsel = g.get("waits", g.get("wrand"))
        # (a) walk-stream strict, ALL cases (the value-bug invariant)
        if ce.walk_of(tb_full) != ce.walk_of(g["full"]):
            walk_fail.append((g["ctx"], g["nest"], wsel))
        # (b) cycle-exact (full stream + active count)
        cyc_ok = (tb_full == g["full"] and tb_active == g["active"])
        kd = _known_cell(meta, g)
        if not cyc_ok:
            if kd is not None:
                known_hit.append((g["ctx"], g["nest"], wsel))
            elif "wrand" not in g:
                cyc_unexpected.append((g["ctx"], g["nest"], wsel))
        elif kd is not None:
            known_stale.append((g["ctx"], g["nest"], wsel))
    ok = not walk_fail and not cyc_unexpected
    print(f"  WAITED ({checked} goldens: nesting set x waits{ce.WAITS_FIXED} + "
          f"wrand x2 ctx): {'PASS' if ok else 'FAIL'}")
    print(f"    walk-stream (value-bug invariant, ALL waits): "
          f"{'PASS' if not walk_fail else f'FAIL x{len(walk_fail)}'}")
    print(f"    cycle-exact: {len(cyc_unexpected)} UNEXPECTED divergence(s); "
          f"{len(known_hit)} booked #33-interleave cell(s) hit; "
          f"{len(known_stale)} stale exclusion(s)")
    for tag, lst in (("WALK-FAIL", walk_fail), ("CYC-UNEXPECTED", cyc_unexpected),
                     ("STALE-EXCLUSION", known_stale)):
        for ctx, nest, w in lst[:12]:
            print(f"    {tag}: ctx{ctx} nest={nest} w={w}")
    return ok


def main():
    print("check_enter_nesting:")
    m_ok = check_mask()
    w_ok = check_waited()
    ok = m_ok and w_ok
    print(f"check_enter_nesting: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
