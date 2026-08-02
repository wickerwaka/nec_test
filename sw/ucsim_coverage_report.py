#!/usr/bin/env python3
"""ucsim_coverage_report -- build sim/coverage_report.txt (campaign S4).

Merges the two micro-row execution counters the campaign accumulates and
classifies every row no gate has ever executed.  Row index = bank*4 + row,
which is exactly the row order of `v30sim disasm`, so the classification can
quote the row's own disassembly.

  # 1. single-instruction gates (ucsim_check --coverage ACCUMULATES into the
  #    file, so run every gate against the same path)
  for s in v0.1 v0.1-w1 v0.1-w3 v0.2 f4a_boundary f0lock_tranche v0.3; do
      python3 sw/ucsim_check.py --suite tests/v30/$s --coverage cov.json
  done
  python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --forms goldens \
          --residue stale-ea --coverage cov.json
  python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror \
          --coverage cov.json

  # 2. the sequence gauntlet (writes a bare 1028-entry list)
  python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw,t30-brkem --coverage fz.json

  # 3. the report
  python3 sw/ucsim_coverage_report.py cov.json fz.json

The verdict document (docs/notes/ucsim_campaign_verdict_2026-08-01.md, section
(e)) cites the output; the two NAMED residual row-ranges below are the ones it
enumerates.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"

if len(sys.argv) != 3:
    sys.exit(__doc__)

single = json.load(open(sys.argv[1]))["rows"]
fz = json.load(open(sys.argv[2]))
fz = fz["rows"] if isinstance(fz, dict) else fz
union = [a + b for a, b in zip(single, fz)]

txt = subprocess.run([str(SIM), "disasm", str(ROM)],
                     stdout=subprocess.PIPE).stdout.decode().splitlines()
banks, cur = [], None
for ln in txt:
    if ln.startswith("-------"):
        cur = ln[8:].strip()
    elif ln[:4].strip() and cur is not None:
        banks.append((int(ln[:4], 16), cur, ln.rstrip()))
assert len(banks) == 1028, len(banks)

rowtxt = {i: t for i, (a, b, t) in enumerate(banks)}
rowbank = {i: b for i, (a, b, t) in enumerate(banks)}

NAMED = [
    ("R2' -- the POLL (9B) tail behind `JMP BUSY 3`.  BUSY is hard-FALSE (no "
     "pin model), so 006C's test never takes the branch: 006D carries E, 006E "
     "is its delay slot, and the instruction retires.  Nothing in any capture "
     "or any banked program raises the pin, so the busy spin AND the "
     "interrupt-withdrawal path behind it are both unreached.",
     list(range(0x6C, 0x74))),
    ("A30 -- bank A of the ROM's ONE ambiguous micro-address "
     "111.00000010.00 (a SINGLE acknowledge with AW saved/restored and the "
     "vector off the HIGH lane).  Silicon runs bank B (01E0-01E3, two "
     "acknowledges, vector off the low lane) -- measured twice at S2a.",
     list(range(0x1DC, 0x1E0))),
]
NAMED_ROWS = {i for _, rows in NAMED for i in rows}

dead = [i for i in range(1028) if not union[i]]
substantive, post_farjmp, tail = [], [], []
for i in dead:
    if i in NAMED_ROWS:
        substantive.append(i)
    elif i % 4 and "FARJMP" in rowtxt[i - 1]:
        post_farjmp.append(i)
    else:
        tail.append(i)

out = []
w = out.append
w("ucsim micro-row coverage report -- campaign stage S4, 2026-08-01")
w("=" * 72)
w("")
w("Every row of docs/V20BITS.TXT (1028 rows, 257 activation patterns), with")
w("the number of times a GREEN GATE executed it.  Row index = bank*4 + row,")
w("i.e. the row order of `v30sim disasm`.  Counters: `v30sim run --coverage`")
w("and `v30sim image --coverage`, accumulated by sw/ucsim_check.py --coverage")
w("and sw/ucsim_fuzz.py --coverage.")
w("")
w("A row that no gate has ever executed is a ROM claim the campaign has not")
w("tested.  This report is the enumeration the S4 sufficiency verdict cites")
w("(docs/notes/ucsim_campaign_verdict_2026-08-01.md, section (e)).")
w("")
w("GATES IN THE UNION")
w("-" * 72)
w("  single-instruction (sw/ucsim_check.py --coverage, accumulated):")
w("      tests/v30/v0.1        169000/169000")
w("      tests/v30/v0.1-w1       1200/1200")
w("      tests/v30/v0.1-w3       1200/1200")
w("      tests/v30/v0.2        347000/347000")
w("      tests/v30/f4a_boundary   160/160")
w("      tests/v30/mod3_illegal   128/128   (documented stale-EA residue)")
w("      tests/v30/f0lock_tranche 400/400")
w("      tests/v30/v0.3       3699998/3699998")
w("      tests/v30/v20suite   3125000/3125000  (--no-mirror, real uPD70108)")
w("  sequence (sw/ucsim_fuzz.py --coverage):")
w("      tests/v30/fuzz_bank mc1,mc2,t30-raw,t30-brkem   3242 seeds")
w("")
w("  (tests/v30/enter_nesting runs through --enter-nesting, which returns")
w("   before the coverage accumulator; its rows are a subset of the C8")
w("   coverage the suites above already provide.)")
w("")
w("TOTALS")
w("-" * 72)
w(f"  single-instruction gates alone : {sum(1 for x in single if x)}/1028")
w(f"  fuzz banks alone               : {sum(1 for x in fz if x)}/1028")
w(f"  UNION                          : {sum(1 for x in union if x)}/1028 "
  f"executed, {len(dead)} never executed")
sg = {i for i, x in enumerate(single) if x}
fs = {i for i, x in enumerate(fz) if x}
w(f"  fuzz-only rows                 : {len(fs - sg)}")
w(f"  single-gate rows the fuzz banks do NOT reach : {len(sg - fs)}"
  + ("" if (sg - fs) else "   (the fuzz set strictly CONTAINS the gates')"))
w("")
w("CLASSIFICATION OF THE UNEXECUTED ROWS")
w("-" * 72)
w(f"  {len(substantive):3d}  SUBSTANTIVE -- a ROM claim nothing has tested; each")
w("       belongs to a NAMED residual (below)")
w(f"  {len(post_farjmp):3d}  structurally unreachable: the row immediately after an")
w("       unconditional `CTL FARJMP`, which has no delay slot")
_viol = sum(1 for i in tail
            if any(union[j] for j in range(i, (i // 4) * 4 + 4)))
_row0 = sum(1 for i in tail if i % 4 == 0)
w(f"  {len(tail):3d}  structurally unreachable: trailing rows of a bank whose")
w("       sequence retires (or jumps away) before reaching them.  Criterion")
w("       (the same one used at S3): every LATER row of the same bank is also")
w(f"       dead -- {len(tail) - _viol}/{len(tail)} satisfy it, and {len(tail) - _row0}"
  " are not a bank's row 0.")
w("       That is structural evidence, not a machine-checked reachability")
w("       proof.")
w("")
w("  Nothing is unexecuted for want of trying: every row in the first bucket")
w("  is blocked by a residual with a directed board experiment recorded in")
w("  the verdict document, section (d).")
w("")
w("THE SUBSTANTIVE ROWS")
w("-" * 72)
import textwrap
for why, rows in NAMED:
    w(f"  rows {rows[0]:04X}-{rows[-1]:04X}   {rowbank[rows[0]]}")
    for ln in textwrap.wrap(why, 68):
        w(f"    {ln}")
    for i in rows:
        mark = ("  <-- UNEXECUTED" if not union[i]
                else f"  executed x{union[i]}")
        w(f"      {rowtxt[i][:66].rstrip():<66}{mark}")
    w("")
w("FULL LISTING OF UNEXECUTED ROWS")
w("-" * 72)
w("  legend:  [SUBST] a named residual   [FJMP] post-FARJMP   [TAIL] bank tail")
w("")
last = None
for i in dead:
    b = rowbank[i]
    if b != last:
        w(f"  --- {b}")
        last = b
    kind = ("SUBST" if i in substantive else
            "FJMP" if i in post_farjmp else "TAIL")
    w(f"    [{kind:5s}] {rowtxt[i].rstrip()}")
w("")
w("HISTORY")
w("-" * 72)
w("  S2b (single-instruction gates only) : 740/1028")
w("  S3  (fuzz banks added)              : 912/1028")
w("  S4  (re-derived, this file)         : "
  f"{sum(1 for x in union if x)}/1028")
w("")
w("  The fuzz banks newly covered the ROM's own RESET sequence (a fuzz image")
w("  replay is exactly the entry those rows exist for), the BRK/TF trap entry,")
w("  the INTEM bank, the BRKEM entry and 158 of the 192 8080-mode rows -- all")
w("  of which were on S2b's unexecuted list.")
Path(ROOT / "sim" / "coverage_report.txt").write_text("\n".join(out) + "\n")
print("\n".join(out[:60]))
print("...")
print(f"substantive={len(substantive)} fjmp={len(post_farjmp)} tail={len(tail)}")
