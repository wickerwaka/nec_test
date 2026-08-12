# fz2 WAVE-8 — THE 8F GHOST-READ **PREDECESSOR-TYPE SELECTION** LAW — PRE-REGISTRATION

Branch `fuzz-v2-on-relanding`, base **`292d898837`** (`git rev-parse HEAD`
verified; the worktree provisioned at `master`/`29dcc5b05f` and was reset).
**Offline throughout. No board. No flash.** Quartus is in scope only if
something lands.

The split is already frozen and committed at **`4f6a2a383f`**, *before* this
document and before any per-seat solve — `docs/notes/fz2_w8_split.json`,
`sw/fz2_w8_split.py`.

---

## §0 WHAT IS ALREADY REFUTED, AND WHY THIS WAVE IS NOT A THIRD GUESS AT THE SAME THING

| wave | hypothesis | verdict |
|---|---|---|
| **W6** (`fz2_w6_ghostrail_results_2026-08-10.md`) | ONE static rail (`m_ea`, `ind`, or any of 21 terms / 190 bitwise pairs) reproduces the chip on every solvable seat | **REFUTED** — the intersection over the three solvable DERIVE seats is EMPTY |
| **W7** (`fz2_w7_ghostretain_results_2026-08-10.md`) | ONE retained flop capturing the 8F's address AT ISSUE subsumes both halves | **REFUTED** — 0 closures, **2 LOST**, 4 `first` earlier; and `fz2e/518022`'s chip ghost is a value `IND` holds at **no** freeze |

W7 §1 states the survivor in one sentence, and it is this wave's subject:

> *"which register mirrors the 8F's stale address depends on the PREDECESSOR
> instruction's type, not on WHEN it is read. A POP-family predecessor leaves
> the address in `IND`/`SP`; a ModR/M predecessor leaves it in `M_EA`."*

**This wave does not test another rail and does not test another retention.**
It asks the mechanism question: *what, on the die, performs the selection?*
The SIMPLICITY reading it starts from — and the only one it is willing to land
— is that **nothing performs it**: the ghost read consumes a latch that the
predecessor's own execution path already wrote, so the "selection" is a
last-writer fact about one register, not a mux, a comparison, or a table.

## §1 THE CANDIDATE MECHANISM, TAKEN FROM THE RTL AND NOT FROM ANY SEAT

Read before any seat was solved; it names no seed and no opcode.

**The tree already has the latch and already has both writer classes.**
`ea_residue` (`v30u_eu.sv:237`) is written from exactly two paths:

```
  (EA)       v30u_eu_step.svh:397   S_EA_CALC        ea_residue_n = ea        (the pre-displacement adder half)
             v30u_eu_step.svh:435   S_BIND, 8D mod!=3 (LEA)   ea_residue_n = ind_n
  (SCRATCH)  v30u_eu_step.svh:664   after v30u_eu_row.svh     if (tmpa_n != tmpa) ea_residue_n = tmpa_n
             v30u_eu_step.svh:692   S_RLOOP                   same
             v30u_eu.sv:3274        the post-E row            same
```

**And the tree asks "which path wrote it last?" TWICE, BY VALUE, in two
different places:**

```
  v30u_eu.sv:1481        wire ghost_uses_ea = (ea_residue != tmpa);
  v30u_eu_step.svh:663   ... && (ea_residue_n != tmpa)      // the 8F row-0058 guard
```

`(ea_residue != tmpa)` is not a property of the die. It is a *proxy* for
"the (EA) writer went last", true because the (SCRATCH) writer sets the two
registers equal on the clock it fires. **A proxy that is right for a reason is
a mechanism written down wrong**, and the SIMPLICITY principle names the
signature exactly: the multi-case rule beside it (`ghost_uses_ea` + the `8E`
special case + the low-bit mask + `ghost_uses_mul_hi`) is what accretes around
a value comparison standing in for a state bit.

### C-W8 — THE LAW THIS WAVE WILL DERIVE AND, IF IT SURVIVES DERIVE, LAND

> **The 8F mod==3 ghost read issues with the datapath's retained
> memory-address latch, and WHICH value is in that latch is decided by which
> execution path last wrote it — a one-bit fact the predecessor sets as a side
> effect of running. There is no selector.**

In RTL that is **ONE BIT** beside `ea_residue`, set by the (EA) writers and
cleared by the (SCRATCH) writers, read in place of BOTH value comparisons. It
adds no case, names no opcode, and DELETES two fitted predicates.

**The disagreement classes with the value comparison, enumerated in advance so
neither a hit nor a miss can be re-narrated afterwards:**

* **(i)** the (EA) writer went last but `ea_residue == tmpa` by coincidence —
  the value comparison says SCRATCH, the bit says EA;
* **(ii)** `S_BIND`'s 8D/mod==3 arm (`v30u_eu_step.svh:488`,
  `tmpa_n = ea_residue_n`) makes the two equal without a (SCRATCH) write — the
  value comparison flips to SCRATCH while the bit correctly stays EA;
* **(iii)** the 8F row-0058 guard becomes mechanical rather than a second copy
  of the same comparison.

**⚠ THE HONEST PRIOR, REGISTERED BEFORE THE SOLVE.** (i) and (ii) are narrow.
If C-W8 in this minimal form misses its closure bar, what is refuted is
precisely *"the selection is a last-writer bit over the tree's EXISTING two
writer classes"* — and the surviving reading is that **silicon's latch has a
writer the ucore does not model**, most likely the FULL, post-displacement
ModR/M EA (`m_ea`) retained ACROSS instruction boundaries, where the ucore
retains only the PRE-displacement adder half (`ea_residue_n = ea`, before
`ea = ea + ld_disp_n`). That is a *different* mechanism and, per the standing
rule, would have to be measured as one — it is **not** to be bolted on to C-W8
mid-wave to rescue a miss.

## §2 THE POPULATION, THE SPLIT, AND THE BASELINE

**Population (28).** F17 ledger (`fz2_failure_ledger_f17_2026-08-11.json`)
family `E1 same-status data cycle, different address` = **39**, MINUS the
**11** of them `fz2_immaterial.partition` disposes as IMMATERIAL, derived
through the census's own `fz2_materiality.measure_all`. KM's three closures
(`fz2c/404041`, `fz2e/501066`, `fz2e/513019`) are D2/C2 and are not in E1.

**Split.** `sha256(seed_id + "w8")[0] < '8'` → DERIVE. **13 DERIVE / 15
HOLDOUT**, committed `4f6a2a383f`. Seed id only: no address, no register, no
solve result. W6's and W7's splits are burned and neither is reused.

**BASELINE, MEASURED BEFORE THIS DOCUMENT AND DISCLOSED AS SUCH.**
`fz2_replay --leg ret --no-fabric-era-guard` over the 28 on
`Vtb_sys` receipt `09e75c03751e6d85…` (tree `3caf766688960339…`), 28/28
replay-FAIL, `first_bad` IDENTICAL to fabric on 28/28. This measures the
BASELINE only — no law, no address, no rail — and it exists because W7 §4.2
required it: *"a future wave should FIRST partition the 39 by 'is the ghost row
the only divergence'."*

```
  seat          leg    bad  first        seat          leg    bad  first
  fz2c/406006   H       16    478        fz2e/501069   D     1959   1547
  fz2e/529067   D       16    611        fz2e/531018   D     2212   1510
  fz2e/521059   H       20   1235        fz2e/510043   D     2238    971
  fz2e/530001   D       20    442        fz2e/524007   D     2257    319
  fz2e/518038   H      194    429        fz2e/518050   H     2560    748
  fz2e/526054   H      320    265        fz2e/524030   D     2610    352
  fz2e/518004   D      388    739        fz2e/534060   H     2670   1067
  fz2e/522003   H      403   3164        fz2e/522019   H     3075    396
  fz2e/518006   D      479   1336        fz2c/406054   H     3141    470
  fz2e/518022   H      742    281        fz2c/406063   H     3149    245
  fz2e/520000   H      836    502        fz2e/527037   H     3183    404
  fz2e/533025   D     1041   1678        fz2e/535027   D     3226    296
  fz2c/408019   H     1086   1617        fz2e/518067   D     3278    325
                                         fz2e/518053   D     3413    567
                                         fz2e/524034   H     3479    457
```

**THE ARITHMETIC THIS FORCES, AND IT SETS THE BAR.** Only **4 of 28** carry a
`bad` a ghost-address fix could plausibly zero (≤ 40). Of the 15 HOLDOUT
seats, **five are M10's LEA-mod3 six** (`fz2c/406054`, `fz2c/408019`,
`fz2e/518038`, `fz2e/522019`, `fz2e/524034` — the sixth, `fz2e/530001`, is
DERIVE) and one (`fz2c/406063`) is named in W7-4's §64.1 list; all are
REGISTERED NON-MOVERS. **The closeable HOLDOUT population is therefore exactly
TWO seats: `fz2c/406006` and `fz2e/521059`.** A bar of "≥ 3 fresh HOLDOUT
closures", as W6 and W7 registered, cannot be met on this population by any
law whatsoever, and registering it would be registering a lie.

## §3 THE REGISTERED PREDICTIONS

| id | clause | falsifier |
|---|---|---|
| **W8-D** | **THE DERIVATION.** On DERIVE ONLY, `fz2_m10.py solve` + a cross-tabulation of (rail that reproduces the chip) × (the ucore's `ea_residue` LAST WRITER at the ghost row) × (the predecessor's decoded type). C-W8 SURVIVES iff the chip-fitting rail is a FUNCTION of the last-writer bit on every solvable DERIVE seat. | two solvable DERIVE seats with the SAME last-writer bit and DIFFERENT chip-fitting rails ⇒ **C-W8 REFUTED on DERIVE; land nothing.** |
| **W8-1** | **THE DELIVERABLE. ≥ 2 HOLDOUT seats close (`bad` → 0).** The closeable HOLDOUT set is named here in advance: **`fz2c/406006`, `fz2e/521059`.** | ≤ 1 closure ⇒ **STOP: BOOK, land nothing.** |
| **W8-1a** | The 13 other HOLDOUT seats are **registered NON-CLOSURES** — cascade-bound (`bad` ≥ 194 with the ghost row one of many) or named non-movers. Their staying open is **NOT** a miss. | — (this clause can only be quoted against an over-claim) |
| **W8-1b** | **ROW-COUNT IMPROVEMENT IS EVIDENCE, NOT A CLOSURE.** Any cascade-bound seat whose `bad` falls or whose `first` moves LATER is reported as mechanism evidence and **may not be counted in W8-1**. | quoting a row improvement as a closure |
| **W8-2** | **LOST = 0.** No seed anywhere in the 113-failure ledger, nor in the passing sample, goes from `bad == 0` to `bad > 0`. | any LOST ⇒ **STOP: BOOK, land nothing.** |
| **W8-3** | No seed's `first` moves EARLIER. | any earlier `first` ⇒ reported as a MISS; combined with W8-2 it is a STOP. |
| **W8-4** | **THE NAMED NON-MOVERS.** M10's LEA-mod3 six (`fz2c/406054`, `fz2c/408019`, `fz2e/518038`, `fz2e/522019`, `fz2e/524034`, `fz2e/530001`) are not claimed. The §64.1 four as KM/N1 last measured them — `fz2c/405002` 527 · `fz2c/405013` 1331 · `fz2c/405072` 636 · `fz2e/512056` 1475 — are UNMOVED in `bad` and `first`. W7-4's older §64.1 list (`fz2c/406063`, `fz2c/410047`, `fz2e/518053`, `fz2e/535027`) is ALSO registered unmoved. `fz2c/404040` stays `bad == 0`. | any move |
| **W8-5** | **THE IMMATERIAL 21 DO NOT SHIFT CLASS.** `fz2_immaterial.py falsify` PASSes and the census still reads **21 of 113**, `COSMETIC 19 · TRANSIENT 2`. | a changed membership or a non-PASS |
| **W8-6** | **NO NEW FLOP unless the derivation demands one**, and if one is taken, `ss_lint` moves by exactly one address under the single-writer rule: `0x8D / 226 / 0x8DE2 / 214` → `0x8E / 227 / 0x8EE3 / 215`. If none, all four are UNMOVED. | any other movement |
| **W8-7** | `check_core.py --core ucore --opcodes all --cases 0` **169,000/169,000** AND `--opcodes 8F.0` **500/500**. | any short |
| **W8-8** | The four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (⚠ `--waits 0/1/2/3`). | any short |
| **W8-9** | `ulockstep.py --golden all --cases 50` **17,350/17,350**. | any short |
| **W8-10** | `r7_lint` PASS, tainted set unchanged (`eu_rd_edge`, `rd_edge_psw_take`, `rd_edge_take_raw`), 0 violations; `gen_ucore_qsf --check` PASS; `test_artifact` **45/45**. | any failure |
| **W8-11** | `fz2_replay` over the FULL 113 ledger failures, DERIVE and HOLDOUT scored and reported **separately**. | a single blended number |
| **W8-12** | **NON-VACUITY.** Any seat claimed closed is shown to have been closed BY the ghost address: its baseline first divergence is on the ghost row's address column. | a closure with no address attribution |
| **W8-13** | **G6, TWO DRAWS, both ≥ 38.0 MHz**, TNS 0.000 setup AND hold, 0 errors / 0 latches / 0 `lpm_divide`, both receipts quoted. **38.0 is a STOP**, not a target. The band on this branch is ~38.4–42 and the ghost neighbourhood has collapsed to **15.3 MHz** once before. | either draw < 38.0 ⇒ **REVERT**. |

**THE STOP CONDITION, STATED ONCE.** If W8-D refutes C-W8 on DERIVE, or W8-1
closes fewer than 2, or W8-2 is violated, **the law is BOOKED and NO RTL IS
LANDED** — and the booking must name the missing measurement precisely enough
to be executed, including the design of a directed board cell if that is what
is missing. Per the brief: *a booked "the mechanism needs a board cell" with
the cell designed beats a third refuted guess.*

## §4 WHAT THIS WAVE MAY NOT DO

* It may not choose a rail by scanning HOLDOUT. The HOLDOUT number is the claim.
* It may not rescue a DERIVE refutation by widening the law mid-wave (§1's
  ⚠ names the specific temptation).
* It may not count a row-count improvement as a closure (W8-1b).
* It may not re-derive W6's or W7's refutations, and it may not quote a fabric
  figure: the board carries FLASH #17 and nothing here touches it.
* Probes are REVERTED unless they land, and the capture symlinks this worktree
  needs are removed before every commit.
