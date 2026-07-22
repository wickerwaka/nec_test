#!/usr/bin/env python3
"""Divergence characterization harness (Phase 1, zero board cost).

Runs the current master RTL sim over selected cases of a v0.3 form and reports,
per case: cycle-row mismatches (row, col-name, chip, rtl) and arch (reg/ram/flags)
deltas -- the exact chip-vs-RTL structure. Reuses check_core internals so the
comparison is identical to the gate.
"""
import sys, gzip, json, tempfile, subprocess
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import check_core as CC

FLAGS_MASK = 0xFFFF  # raw compare; families are mask-independent per ledger

def load(form):
    return json.load(gzip.open(f"/home/wickerwaka/src/nec_test/tests/v30/v0.3/{form}.json.gz"))

def run_cases(form, cases, waits=0):
    """Return {idx: sim} for the given case dicts."""
    td = tempfile.mkdtemp(); b = f"{td}/b"
    CC.compose_batch(cases, b)
    r = subprocess.run([str(CC.BIN), f"+batch={b}", f"+out={td}/o",
                        f"+waits={waits}", "+ce_div=1"],
                       cwd=CC.ROOT, capture_output=True, text=True, timeout=120)
    return CC.parse_out(f"{td}/o")

def characterize(form, indices, waits=0):
    gold = load(form)
    gidx = {c["idx"]: c for c in gold}
    cases = [gidx[i] for i in indices if i in gidx]
    sims = run_cases(form, cases, waits)
    out = {}
    for c in cases:
        res = CC.check_case(c, sims.get(c["idx"]), FLAGS_MASK, arch_only=False)
        rowmm = [(m[0], CC.COL_NAME.get(m[1], m[1]), m[2], m[3]) for m in res.get("mm", [])]
        # arch diffs
        exp = dict(c["initial"]["regs"]); exp.update(c["final"]["regs"])
        got = sims.get(c["idx"], {}).get("final") or {}
        reg_bad = [(k, hex(exp[k]), hex(got.get(k, -1))) for k in CC.REGS
                   if got and exp.get(k) != got.get(k)]
        out[c["idx"]] = {
            "bytes": " ".join(f"{x:02X}" for x in c["bytes"]),
            "cyc_ok": res["cycles_ok"], "arch_ok": not reg_bad,
            "rowmm": rowmm, "reg_bad": reg_bad,
            "n_gold_rows": len(c["cycles"]),
        }
    return out

if __name__ == "__main__":
    form = sys.argv[1]
    idxs = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
    if idxs is None:
        # sweep all, report diverging indices
        gold = load(form)
        res = characterize(form, [c["idx"] for c in gold])
        div = {i: r for i, r in res.items() if not (r["cyc_ok"] and r["arch_ok"])}
        print(f"{form}: {len(div)} diverging of {len(gold)}: {sorted(div)}")
    else:
        res = characterize(form, idxs)
        for i in sorted(res):
            r = res[i]
            print(f"\n=== {form} idx {i}  bytes=[{r['bytes']}]  cyc_ok={r['cyc_ok']} arch_ok={r['arch_ok']} rows={r['n_gold_rows']}")
            if r["rowmm"]:
                print("  ROW DIFFS (row, col, chip, rtl):")
                for m in r["rowmm"][:20]:
                    print(f"    row {m[0]:2d} {m[1]:8s} chip={m[2]!r:12s} rtl={m[3]!r}")
            if r["reg_bad"]:
                print("  ARCH DIFFS (reg, chip, rtl):", r["reg_bad"])
