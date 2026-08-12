# FLASH #20 — PRE-REGISTRATION: **THE GHOST LAUNCH RELOCATION'S FABRIC CONFIRMATION**

**COMMITTED BEFORE ANY QUARTUS BUILD AND BEFORE ANY BOARD CONTACT.**
Branch `fuzz-v2-on-relanding`, HEAD **`b5051a24f3`** (`git rev-parse` verified).
Board contact — flashing included, **`sw/safe_flash.sh` only** — is authorised
by the user (standing grant, the option-3 sequence's final step). Main
checkout. No Codex, no nested tasks.

---

## 0. WHAT THIS SITTING IS FOR

**ONE QUESTION: is the ghost LAUNCH relocation TRUE IN FABRIC?**

Every figure the relocation has is offline. `ghost_preflash20_results_2026-08-12.md`
§7's own closing words: *"Every replay figure in this document is
ERA-GUARD-BYPASSED and is an OFFLINE core-side number. No fabric figure exists
for this tree and none is implied. That is exactly what FLASH #20 would
produce."* `fz2_flash19_results_2026-08-12.md`'s banner says the same from the
other side: *"The relocation's own 528-cell column (275 → 384) is an offline
result on a bitstream that does not exist yet. It has had no fabric
confirmation, and this sitting supplies none."*

**SILICON MATCH is the only correctness bar** (CLAUDE.md, user directive
2026-08-04). This sitting supplies the missing column.

### 0.1 THE BUNDLE, NAMED AND VERIFIED — AND IT IS **NOT** UNBUNDLED

Unlike FLASH #19, this flash carries **RTL**. Measured at the top of this
sitting, against FLASH #19's flashed receipt (`dba7c75533bc0f79…`, inputs
`b2e50a482ca1123b…`, 88 declared inputs):

    88 declared inputs, 88 present, 4 DIFFERING:
        hdl/rtl/ucore/v30_core.sv
        hdl/rtl/ucore/v30u_biu.sv
        hdl/rtl/ucore/v30u_eu.sv
        hdl/rtl/ucore/v30u_ss_pkg.sv
    hdl/nec_test.sdc              IDENTICAL  (E-1 is already in FLASH #19)
    hdl/nec_test_ucore.qsf        IDENTICAL

**Four files, three landings, and they are not separable by this sitting:**

| landing | commit | what it is |
|---|---|---|
| the ghost LAUNCH relocation | `093efbcfc2` / merge `ef19010e63` | `dGR` in RTL: 46 flops, `g_sp`/`g_bare`/`g_age`/`g_row_q`/`rq_ghost`/`cmt_ghost`, the 3:1 mux at the commit; wave-4's fitted V2 arm DELETED. `SS_VERSION` 0x8D → **0x8E**, `SS_COUNT` 226 → **232**, census 214 → **220** |
| **F-A** — the `imul` arm | `292f30bcf8` | `ghost_uses_mul_hi` and all three of its uses **DELETED** |
| **F-B′** — the split law | `292f30bcf8` | `acc_split` = *an access splits iff it transfers a WORD across an ODD boundary*; the `ghost_uses_ea` rail case deleted |

⚠ **THIS IS A THREE-MECHANISM BUNDLE AND THE CAMPAIGN'S OWN PRECEDENT IS
AGAINST BUNDLES** (CLAUDE.md, *"a bundle's benefit is not evidence for any
member of it"*). It is taken as one anyway, and the reason is registered here
rather than argued later: **the per-mechanism attribution was already measured
OFFLINE, exactly and separately** (`ghost_preflash20_results` §4.6 — F-A alone
moves 0 of 264 seeds; F-B′ alone moves 6; combined is byte-identical to F-B′
alone on all 264). What fabric adds is not attribution, which is already
settled, but **existence**: does the synthesised core do what the model says?

**Consequence, and it is the point:** a deviation from the corpus bar is
attributed to **the relocation first**, because the four RTL files are the only
delta.

### 0.2 THE NOISE FLOOR GOVERNS EVERY AGGREGATE CLAIM

`docs/notes/fz2_capture_noise_2026-08-10.md`: **10 / 3,840 = 0.2604 %**
ledger-class flips. FLASH #17 spent 7; FLASH #18 spent 0; FLASH #19 spent 6 and
**measured all six non-reproducible on the same bitstream** (F19 §4.6).

**This flash DOES change logic**, so unlike FLASH #19 the predicted corpus delta
is **not** zero. It is derived, seed by seed, in §4. **Movement on a NAMED seat
is the bar. Movement anywhere else is charged against the 10-seed budget and
itemised**, with the escaped-seed caveat: seeds carrying a large `escaped`
count reach memory the harness does not model and their row streams are known
to be less stable than the rest of the corpus.

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS, TWO DRAWS EACH (`E-1` … `E-12`)

`python3 sw/quartus_gate.py` (CONTROL) and `--retention` (RETENTION). **Each
draw from a deleted `db` / `incremental_db` / `output_files_ucore`. THE WORST
DRAW IS THE FIGURE.** If two draws of a configuration disagree by more than
1.0 MHz a third is taken and worst-of-three is quoted.

| # | bar |
|---|---|
| **E-1** | `gen_ucore_qsf --check` PASSES before each draw |
| **E-2** | 0 compile errors, every stage Successful, 0 latches, 0 `lpm_divide` |
| **E-3** | `divclk` Fmax **≥ 32.0** (G6) **and ≥ 38.0** (this branch's live STOP) |
| **E-4** | worst setup slack **> 0** on every domain |
| **E-5** | **TNS 0.000, setup AND hold, every domain** |
| **E-6** | the RETENTION receipt's **DERIVED** `configuration` self-labels `RETENTION (X1_AD_RETENTION=1)` |
| **E-7** | the CONTROL receipt's **DERIVED** `configuration` self-labels `CONTROL/DEFAULT` |
| **E-8** | the RETENTION `.rbf` **DIFFERS** from the CONTROL `.rbf` |
| **E-9** | the 88-file input manifest reads **`304b5d67ccd2cd5c…`** on all four draws |
| **E-10** | `.qsf` regenerated and re-checked after each draw |
| **E-11** | all four receipts retained in `sw/testdata/receipts/quartus_bitstream.jsonl` |

### 1.1 THE POINT PREDICTION, AND WHY A POINT IS LEGITIMATE HERE

**The main checkout at HEAD hashes IDENTICALLY on all 88 declared inputs of the
pre-F20 wave's four receipts** — measured before this document was committed:
`input_manifest()` → **88 files, `304b5d67ccd2cd5c…`**, the same string those
four receipts carry. Same inputs, same flow, same tool, different checkout.
FLASH #19 registered points on exactly this ground and hit all four.

| | **REGISTERED POINT** | band (containment) |
|---|---|---|
| **P-1** CONTROL worst-of-2 | **45.61 MHz**, worst setup **+8.892 ns**, ALMs **12,282** | [43.0, 48.0] |
| **P-2** RETENTION worst-of-2 | **44.32 MHz**, worst setup **+8.689 ns**, ALMs **12,245** | [42.0, 47.0] |
| **P-3** CONTROL `.rbf` | **`277e7de5f8fcfcde…`** byte-identical | — |
| **P-4** RETENTION `.rbf` | **`15742aa2f00431c4…`** byte-identical | — |

**A DIFFERING DRAW IS NOT A FAILURE OF THIS SITTING — IT IS §74.4 EVIDENCE AND
IT WILL BE QUOTED AS SUCH.** `standing_gates.md` §A governs: one green build is
not closure, and the same tree has drawn 19.42 and 45.91 MHz.

⚠ **THE BAND HAS FALLEN ACROSS THIS BRANCH AND THE REASON IS NAMED, NOT
GUESSED**: `ghost_preflash20_results` §6.2 located the binding cone with
`sta_census`/`sta_probe` and it is **`c_int_q → v30u_eu|row_posted`, the INT
pin's capture register reaching the EU's post decision, OUT→CORE, single-cycle,
46–47 logic levels** — **not** the relocation's mux (`g_sp`, `g_bare`, `g_age`,
`g_row_q`, `rq_ghost`, `cmt_ghost`, `cmt_addr`, `acc_split` and the string
`ghost` appear **zero** times in either census) and **not** the retention
observation path (excluding all 48 observation registers leaves the same path at
the same 8.689). No SDC change is taken here; §6.3 booked the derivation it
would need.

**HARD STOP: RETENTION worst-of-2 < 38.0 MHz → NOTHING IS FLASHED.**

---

## 2. THE FLASH (`F-1`)

**`sw/safe_flash.sh` ONLY**, with its VERIFY leg, on the **RETENTION** build.

| # | bar |
|---|---|
| **F-1** | flash succeeds, **VERIFY OK**, `flash_log.jsonl` **22 → 23 entries**, tail `verify: "OK"`; `.sof` and `.rbf` sha256 recorded here and in the results |

Single-writer is asked of the board **before first contact** and again before
each subsequent leg. `div_guard()` on every probe; an **UNPINNED readback is a
rig-integrity HARD STOP**. Socket legs are `use_core=False`, explicit.

---

## 3. **THE DIRECTED-CELL FABRIC LEG — THE SITTING'S PRIMARY EVIDENCE**

`ghost_pred_cell`'s 528-cell directed grid is the relocation's own instrument:
33 legs × 4 waits × 4 aligns, each cell one 20-bit number read straight off the
pins, no engine and no golden in the observable. 520 of the 528 are
structurally valid in both legs.

**Its every existing figure is offline.** This section puts it on silicon.

### 3.1 THE THREE COLUMNS, AND WHICH ONE IS NEW

| column | position | status |
|---|---|---|
| **chip** | the socketed part, `use_core=False` | **SILICON.** Banked at FLASH #18 (`board/`, 528 cells, `flash entries 21`) |
| **fabric** | **the ucore INSIDE THE FPGA, `use_core=True`** | **NEW. It has never been taken.** |
| **core** | the ucore on `tb_sys ret`, Verilator | offline; the 398/122 every wave quotes |

**TWO TOOLS ARE ADDED AND BOTH ARE COMMITTED WITH THIS DOCUMENT, BEFORE THE
BUILD AND BEFORE THE BOARD:**

1. **`ghost_pred_cell run --fabric`** — the identical driver, identical images,
   identical divider, `use_core=True`, writing to its **own** directory
   (`ghost-pred/fabric/`). It **cannot** overwrite the banked socket column.
2. **`sw/f20_cell.py`** — the scorer. **Proved non-vacuous before the board was
   touched**, on the identity pair (`--fabric …/core`):

       plain      CHIP vs FABRIC 398/122    FABRIC vs CORE 528/0
       --null 5   CHIP vs FABRIC 393/127    FABRIC vs CORE 523/5

   The null moves both live comparisons by exactly 5 and leaves CHIP-vs-CORE
   at 398 — it perturbs only the fabric table, and the scorer notices.

### 3.2 THE REGISTERED BARS

| # | bar | registered | why it is the right falsifier |
|---|---|---|---|
| **G-1** | **THE PRIMARY. `CHIP vs FABRIC`** — the relocation's claim, on silicon | **identical 398 / different 122**, and **the same 122 cells** as the offline column | if the synthesised core does not do what the model does, this is where it shows, on the instrument built to see exactly this quantity |
| **G-2** | **THE SHARPEST FORM. `FABRIC vs CORE`** — synthesised vs modelled, engine vs engine, no golden in it | **528 / 528 identical, 0 differing** | it has no comparator noise and no golden: any non-zero is a synthesis-vs-simulation divergence and is itemised cell for cell |
| **G-3** | `imul` closes **in fabric** | `imul` **16 / 16** chip == fabric (it was **2/16** before F-A) | F-A's whole measurable benefit is here; the fuzz population cannot see it |
| **G-4** | the per-leg profile reproduces | `alu08` `alu44` `alu88` `imul` `mul` `v_or` `v_sub` **16/16** · `v_inc` **8/16** · `mov8e` **4/16** · `mempop` **2/16** · `v_lea` **2/16** · `memw` **0/16** · `pfxpro` **0/16** | thirteen legs on their registered numbers; a bundle that moved one leg and not the others would say so here |
| **G-5** | **THE SOCKET COLUMN DID NOT MOVE.** Fresh `run` on FLASH #20 vs the banked FLASH #18 column | **528 / 528 cells BYTE-IDENTICAL** by per-cell `sha256` | silicon cannot be changed by reflashing an FPGA. A mover here is a **rig** finding and outranks the cell |
| **G-6** | the offline comparand is **HEAD's**, not a stale one | the `core` column is **RE-TAKEN at HEAD before the build** and reads **398 / 122** against the banked chip column; the banked `core/` is copied aside first and **restored byte-identical**, verified by sha256 | the banked `core/` table was captured at `7df621ba89`; F-B′ is proved not to move the cell (`B′-7`), but "proved not to move" is not "measured at HEAD" |
| **G-7** | rig integrity on both board legs | `div_guard` **PINNED on every probe**, single-writer OK before each leg, **0 transport errors**, **0 GHOST-unstable**, 0 `RigMismatch` | |

**AND THE SPOT-CHECKS, SOCKET-ONLY, WHICH MEASURE SILICON AND THEREFORE
CANNOT MOVE** (F19 §6's form):

| # | leg | registered |
|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` (48 cells) + `score` | **0 chip-column movers**; `n_entries` 6 on every probe; NULL `notf`/`v_notf` **[0]** |
| **S-2** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells) + `score` | **0 chip-column movers**; the six invariant columns **0 disagreements** |
| **S-3** | restoration | every banked tree copied aside before and restored **byte-identical** by sha256 manifest; the F20 rows retained **beside** them, never merged over them |

⚠ **A chip-column mover on S-1/S-2 is NOT a relocation finding** — it is a rig
or silicon observation, reported with its own denominator.

---

## 4. THE CORPUS — **THE HEADLINE IS DERIVED, NOT ASSUMED** (`C-1` … `C-13`)

Full fz2 capture on FLASH #20, then `fz2_ledger`, scored against the **FLASH
#19 ledger** `sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json`
(**114 failures**, denominator **3,837**, Σ`diverging_rows` **118,221**).

### 4.1 THE DERIVATION

The offline wave measured, seed by seed, what the four RTL files do to the
replayed population: the relocation's **28 movers** (`fz2_f19_housekeeping_results`
§2.4, net −1,331 rows, 26 improved / 2 worse / **3 closed**) and the F-A+F-B′
wave's **six** (`ghost_preflash20_results` §4.4, all six improved, net −10,134
rows, **1 closed**). Composed — three seeds appear in both lists — that is
**31 seeds** and **4 closures**.

**THE HEADLINE PREDICTION IS THEREFORE ARITHMETIC, NOT A GUESS:**

| | registered |
|---|---|
| **C-4 — THE HEADLINE** | **failures 110** of denominator **3,837** (114 − 4 closures). **POINT.** Containment band **[100, 120]** = ±10 = the 0.2604 % floor |
| **C-7 — the row metric** | Σ`diverging_rows` **118,221 → 108,720** (Δ **−9,501**), reported in both units; **not barred** (long-tail row counts drift) |

### 4.2 **THE 31 NAMED SEATS** (`C-14`) — REGISTERED VALUE FOR VALUE

`diverging_rows` and `first_bad_row` are the ledger's own units. `first_bad`
values marked `?` were not measured offline and are **reported, not barred**.

| seed | family | F19 `div` | **F20 registered `div`** | F19 `first` | **F20 `first`** |
|---|---|---:|---:|---:|---:|
| `fz2c/406063` | E1 | 3,149 | **3,165** ⚠ WORSE | 245 | 249 |
| `fz2c/408021` | E1 | 26 | **22** | 720 | 728 |
| `fz2c/408068` | D2 | 405 | **401** | 426 | 432 |
| `fz2c/409065` | A3 | 16 | **12** | 1534 | 1538 |
| `fz2c/409077` | D1 | 3,023 | **2,683** | 820 | ? |
| `fz2e/518039` | C1 | 1,587 | **531** | 2363 | 2367 |
| `fz2e/518053` | E1 | 3,413 | **8** | 567 | ? |
| `fz2e/518067` | E1 | 3,278 | **45** | 325 | ? |
| `fz2e/520000` | E1 | 838 | **822** | 502 | 2113 |
| `fz2e/520005` | D1 | 2,870 | **2,866** | 484 | 491 |
| `fz2e/521006` | NEW | 9 | **8** | 368 | 369 |
| `fz2e/521016` | D3 | 16 | **14** | 352 | 362 |
| `fz2e/521049` | A3 | 14 | **10** | 2150 | 2158 |
| `fz2e/525017` | A3 | 12 | **8** | 1141 | 1150 |
| `fz2e/526054` | E1 | 320 | **48** | 265 | 269 |
| `fz2e/527008` | D3 | 2,185 | **2,181** | 929 | 933 |
| `fz2e/527037` | E1 | 3,183 | **3,179** | 404 | 411 |
| `fz2e/528010` | E1 | 4 | **7** ⚠ WORSE | 1383 | 1383 |
| `fz2e/529058` | NEW | 8 | **4** | 1792 | 1799 |
| `fz2e/529067` | E1 | 16 | **12** | 611 | 619 |
| `fz2e/530017` | D2 | 1,672 | **1,668** | 1440 | 1448 |
| `fz2e/530046` | D1 | 2,084 | **1,634** | 1345 | 1353 |
| `fz2e/530070` | C4 | 1,753 | **1,749** | 2225 | 2233 |
| `fz2e/532000` | D1 | 3,002 | **2,998** | 426 | 434 |
| `fz2e/533025` | E1 | 1,041 | **1,039** | 1678 | unmoved |
| `fz2e/534062` | D2 | 1,271 | **1,267** | 1271 | 1291 |
| `fz2e/535004` | D1 | 812 | **808** | 1131 | 1138 |
| **`fz2e/521024`** | NEW | 4 | **0 — CLOSES** | 304 | — |
| **`fz2e/522002`** | NEW | 4 | **0 — CLOSES** | 444 | — |
| **`fz2e/530020`** | D1 | 671 | **0 — CLOSES** | 296 | — |
| **`fz2e/534003`** | NEW | 4 | **0 — CLOSES** | 564 | — |

**C-14 is scored in three parts, separately:**

* **C-14a — THE FOUR CLOSURES.** All four leave the ledger. *Falsifier: any of
  them still present.*
* **C-14b — THE TWENTY-SEVEN SURVIVORS.** Each reads its registered
  `diverging_rows` **exactly**. Deviations are itemised seed by seed with the
  offline value beside the fabric one; **a survivor off by any amount is
  reported as a miss, not absorbed.**
* **C-14c — DIRECTION.** **0 seeds LOST** (no seed at `bad == 0` in F19 goes
  non-zero) and **0 `first_bad` EARLIER** anywhere in the corpus. This is the
  offline wave's own strongest clause (`B′-5`) and it is the one that would say
  the relocation broke something.

⚠ **`fz2c/406063` AND `fz2e/528010` ARE REGISTERED TO GET WORSE.** Both are
diagnosed to mechanism offline — 406063 to the un-relocated SPLIT PARTNER
(relocation prereg §7(b), first measurement), 528010's residual +3 to `UBE`/`A0`
not being recomputed from the relocated address (§7(c), its falsifier firing).
Registering a regression is the point of registering.

### 4.3 THE REST OF THE CORPUS BARS

| # | bar | registered |
|---|---|---|
| **C-1** | corpus identity | `SEED_LIST_SHA256 45d25f31a325c496…`, 960 + 2,880 = **3,840**, 48 strata, `fz2_w1 lint` PASS |
| **C-2** | completeness | **48 / 48 strata, every `rc 0`** |
| **C-3** | the flash pin | `distinct_eras` **1**, `absent` 0, `incomplete` 0, `build_stale` 0, every row's `era.sof_sha256` = FLASH #20's |
| **C-5** | **UNREGISTERED membership flips** | **0**, budget **10** (the 0.2604 % floor). The four registered closures are **not** charged against it. Every flip is itemised with tier, `escaped`, `ps3_8080` and both eras' `bad_rows`/`first_bad_row` |
| **C-6** | first divergence, **off the named seats** | **0 of the 79 unnamed shared failures move `first_bad_row` in either direction** |
| **C-8** | discards | **3** (`fz2e/509069`, `fz2e/524027`, `fz2e/535070`), denominator **3,837**. ⚠ `_ps3_8080` is a **SOCKET-leg** predicate (A-2) and **RTL cannot reach it by construction** — a mover here is a chip/rig observation. It has re-rolled on three consecutive eras (2 → 2 → 3 → 1 → 3), so this is reported with both bases, **not** barred |
| **C-9** | the named non-movers, **silicon-side** | `fz2c/405002` **840 / 527** · `fz2c/405013` **921 / 1331** · `fz2c/405072` **891 / 636** · `fz2e/512056` **984 / 1475** · `fz2c/410047` **3589 / 227** · `fz2e/535027` **3226 / 296** — **6 / 6 unmoved in both columns** |
| **C-9b** | ⚠ **TWO W7-4 §64.1 NAMED NON-MOVERS ARE REGISTERED TO MOVE** — `fz2c/406063` (§4.2) and `fz2e/518053` (3,413 → 8). Both were already recorded as non-mover MISSES offline (`fz2_f19_housekeeping_results` §3.4a, `ghost_preflash20_results` §4.4). **The clause is not re-written to fit; it is scored as MISSED again, in fabric this time** |
| **C-10** | the six FLASH #18 seats | KM's three (`fz2c/404041`, `fz2e/501066`, `fz2e/513019`) stay **ABSENT**; phantom-T1's three (`fz2c/404071`, `fz2e/514044`, `fz2e/516001`) stay at `diverging_rows` **1** with `first_bad_row` **243 / 234 / 583** |
| **C-11** | **the falsifier** | **`fz2c/404040` stays ABSENT from the ledger** |
| **C-12** | M10's LEA-mod3 six | `fz2c/406054` 3141/470 · `fz2c/408019` 1087/1617 · `fz2e/518038` 194/429 · `fz2e/522019` 3075/396 · `fz2e/524034` 3479/457 · `fz2e/530001` 20/442 — **6 / 6 unmoved**. ⚠ `fz2e/520066` is registered at **8 / 1249** (it SELECTED F-B′'s `eu_word` term, so its own value is **not evidence**, CLAUDE.md's standing rule — it is registered as a regression check only) |
| **C-13** | the standing gates on this era | `fz2_w1 bars`, `fz2_w1 lint`, `check_fuzz_bank`, `r7_lint`, `ss_lint`, `gen_ucore_qsf`, `test_artifact` — §6 |

### 4.4 `fz2_immaterial falsify` ON THE F20 LEDGER (`C-15`)

Measured on the **F19** ledger before this document was written: **PASS G1–G8**,
members **24** (COSMETIC 19 · TRANSIENT 5), working residue **90**,
UNSCOREABLE **11**, TIMING_RECONVERGED **7**.

**REGISTERED FOR F20, DERIVED FROM THE CLAUSES:**

| # | registered |
|---|---|
| **C-15a** | **the class goes 24 → 22, and the two leavers are exactly `fz2e/521024` and `fz2e/522002`** — both COSMETIC members and both registered closures. Sub-classes **COSMETIC 17 · TRANSIENT 5**; working residue **110 − 22 = 88** |
| **C-15b** | **`fz2e/528010` STAYS COSMETIC at 7 rows.** Derived, not hoped: `ghost_preflash20_results` §4.5 measures its divergence as 4 RAIL rows plus 3 rows differing in **`ube_n` alone**, and `ube` is a **value** column, not one of `fz2_materiality.CYCLE_DEFINING`. Its columns should read ≈ `addr=1, data=2, nxta=1, ube=3` |
| **C-15c** | **the other four IMMATERIAL movers stay in their sub-classes** — `fz2c/409065` 16→12 COSMETIC, `fz2e/521049` 14→10 COSMETIC, `fz2e/525017` 12→8 COSMETIC, `fz2c/408021` 26→22 TRANSIENT (it carries `bs=12`, cycle-defining) |
| **C-15d** | **0 LEAVERS other than the two closures.** Entrants are **reported and itemised, not barred**: six seeds whose row counts collapse (`518053` → 8, `526054` → 48, `518067` → 45, `518039` → 531, `530046` → 1,634, `409077` → 2,683) could newly qualify if their dumps became identical, and that is not derivable from the offline row counts |
| **C-15e** | ⚠ **G6 AND G7 ARE REGISTERED TO FAIL, ON DOCUMENT STALENESS ALONE.** They are doc-vs-derivation cross-checks against `fz2_materiality_census_2026-08-11.md`, which was re-pinned to the **F19** numbers (114 / 24 / 90) at `5cdca40b60`. The F20 derivation gives (110 / 22 / 88). **The F20 re-pin is the NEXT housekeeping, not this sitting** — the `fz2_w1 lint` rule applies (*if a doc edit trips it, fix the doc*) and the fix is **booked, not applied**. G1–G5 and G8 must PASS |
| **C-15f** | TIMING_RECONVERGED **7**, UNSCOREABLE **11** — reported, **not barred** (F19's own falsifier fired on this quantity: 8 was never a ratchet) |

---

## 5. THE ERA-GUARD RE-SYNC AND THE CLOSING CONTROL (`Q-1`, `Q-2`)

**Every offline replay figure for this tree is `--no-fabric-era-guard`-bypassed**
(`ghost_preflash20_results` §1). The guard is right to refuse: the four RTL
files postdate FLASH #19's bitstream. **This sitting's job is to make the bypass
unnecessary.**

| # | bar | registered |
|---|---|---|
| **Q-1** | **`fz2_replay` PASSES the fabric era guard with NO bypass.** It **REFUSES at HEAD today**, by name, on the four `hdl/rtl/ucore/` files (84/88 identical). After FLASH #20 it must read **88 / 88** (or 87/88 with `hdl/nec_test_ucore.qsf` the single declared exemption, if a draw rewrites it). **`--no-fabric-era-guard` is NOT used anywhere in this sitting** |
| **Q-2** | the closing control: `fz2_replay --ledger <F20> --all-failures --pass-sample 150 --leg ret --jobs 8`, era guard **ON**. Population **110 + 150 = 260** | agreement **≥ 255 / 260**; **point 260 / 260** with `first_bad` identical on 110/110. F19 measured 264/264 across the era boundary; with the fabric core and the offline core now the SAME core, anything less is a finding |

**Q-2 is the strongest single statement this sitting can make about the
relocation**, and it is worth saying why in advance: at FLASH #19 the offline
core carried the relocation and the fabric core did not, and the replay still
agreed 264/264 — because `fz2_replay` feeds the offline core the **chip's** rows
and asks where it diverges, which is a question about the model, not about the
bitstream. **After FLASH #20 the two cores are the same core**, so Q-2 becomes a
statement that the synthesised core and the modelled core divide the same
population the same way.

---

## 6. THE STANDING GATES ON THIS ERA (`C-13`)

| gate | registered |
|---|---|
| `fz2_w1 bars` | **10 / 11**, leaf-diffed against the F19 state with the moved verdicts named. ⚠ **C-6 was MISSED at FLASH #19** on a single directive (`fz2e/509050` stim/`pin_int`/hold 300) **which reverted in F19's run B** — so C-6 is registered **MET at `hold_rows_off` 0**, and `bars` **11 / 11**, with the F19 miss named as the reason the prediction is not simply "unchanged" |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 control` (C-6 board legs) | **9 legs**, holds `[2, 20, 300]` proved on `pin_int` and `pin_nmi` to the clock, INTA vector `0xFF`, N1 negative control PASS, **0 unpinned** |
| `fz2_w1 preflight --board` | **OK** — single writer, era pinned to FLASH #20's receipt self-labelling RETENTION, regeneration sample **0 hits**, RBCHECK **8 registers**, MATCH 800 ×3 |
| `check_fuzz_bank` | **PASS — 621 banked seeds**, stable 621 / improved 0 / worse 0, `gen_drift` 0, `regen_err` 0, new-sig TIMING 0 |
| `r7_lint` | **PASS** — 0 undeclared carriers, 51 `stop` sites, 0 violations |
| `ss_lint --core ucore` | **PASS at `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8, census 220 flops, 0 UNMAPPED** (`SS_BIU_COUNT` 109 / `SS_EU_COUNT` 122). ⚠ This is the RELOCATION's map; FLASH #19's era was 0x8D / 226 / 214 |
| `gen_ucore_qsf --check` | **PASS** |
| `test_artifact` | **45 / 45** |
| `check_ab_hw all 800` (first light) | **MATCH ×3** — chip-vs-golden, core-vs-chip, core-vs-golden |
| `check_ab_hw chip 800` (close-out) | **MATCH over 800 rows**, `use_core=0` |
| §38.9 missed-trap overlay | **4** (F19's figure) |

⚠ **THE FOLLOWING CANNOT BE RUN OR QUOTED ON THIS BRANCH AND WILL NOT BE**:
`timed_scenario`, `timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`
(`gen_seq._v1_anchor_stop`); **`x1_retention` and `x1_fabric`**, which FLASH #19
found GEN-DRIFTED (§2.1 there) and which therefore supply **no** golden-relative
sweep column this sitting; and the four v1 fuzz banks (SUP-1 / D9).

**A CONSEQUENCE WORTH STATING PLAINLY: the 283-cell HLT sweep column that has
confirmed the last several flashes is NOT AVAILABLE HERE.** Its role — "does the
fabric core reproduce the offline core cell for cell?" — is carried in this
sitting by **§3's 528-cell directed grid**, which is not gen-drifted, is
engine-free in its observable, and is the relocation's own instrument.

### 6.1 HOUSEKEEPING (`H-1`)

The F19 era's `fz2_bars.json` / `fz2_capture.json` / `fz2_control.json` /
`fz2_preflight.json` are **archived to `*_F19-archive.json` before the F20
capture overwrites them** — F19 did not archive them and the convention has held
since F12. This is bookkeeping, not a measurement.

---

## 7. HARD STOPS

1. RETENTION worst-of-2 **< 38.0 MHz**, or any G6 essential RED → **nothing is
   flashed**.
2. The RETENTION receipt self-labelling `CONTROL/DEFAULT`, or its `.rbf` equal
   to CONTROL's (E-6 / E-8) → **nothing is flashed on that build**. *This stop
   fired at FLASH #18 and was obeyed.*
3. `safe_flash` VERIFY not OK.
4. Any `div_guard` **UNPINNED** readback.
5. Any `RigMismatch` / transport quarantine.
6. A failed single-writer check that is not resolved (`--force` is **not** used).
7. `check_ab_hw` first light failing on any of its three legs.
8. **G-5 (the socket column moved)** — a rig finding outranks the cell; the
   sitting stops and reports rather than scoring a cell against a moving
   reference.
9. `ss_lint` not reading 0x8E / 232 / 220 → the bitstream is not this tree's.

**And the §3.3 re-run rule of FLASH #19 is adopted verbatim**: if a leg fails,
**the failing leg is re-run once on the same bitstream before anything is
concluded**, and the finding is reported before any repair is attempted. No
repair is attempted in this sitting.

---

## 8. WHAT THIS SITTING CAN AND CANNOT ESTABLISH

**CAN**: that the synthesised ucore composes the `8F` ghost read's address at
LAUNCH, in fabric, on 520 directed cells whose observable is one number off the
pins; that F-A's `imul` closure is real silicon-side; and that the corpus moves
exactly where the offline wave said it would and nowhere else.

**CANNOT**: attribute anything to one of the three landings. That attribution
was made offline (§0.1) and this sitting does not re-make it. **CANNOT** close
the relocation's named residue either: the un-relocated SPLIT PARTNER (§7(b)),
`UBE`/`A0` at the post (§7(c)), and the RAIL (§7(a), 80 of the law's 208 cells)
are all still open, and two of them are registered to be **visible** in the
results as `fz2c/406063` and `fz2e/528010`.

---

## Appendix A — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                   # b5051a24f3
python3 -c "import sys;sys.path.insert(0,'sw');import quartus_gate as q;m=q.input_manifest();print(m['n_files'],m['sha256'][:16])"
                                                     # 88 304b5d67ccd2cd5c

# the offline comparand for G-6, taken BEFORE the build (banked core/ aside)
python3 sw/ghost_pred_cell.py core                   # ~140 s, HEAD tree

# the build -- two draws each, worst-of-2
python3 sw/quartus_gate.py             --label "fz2 FLASH#20 CONTROL draw1"
python3 sw/quartus_gate.py             --label "fz2 FLASH#20 CONTROL draw2"
python3 sw/quartus_gate.py --retention --label "fz2 FLASH#20 RETENTION ret1"
python3 sw/quartus_gate.py --retention --label "fz2 FLASH#20 RETENTION ret2"

sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof
python3 sw/check_ab_hw.py all 800                    # first light

# THE PRIMARY -- the directed cell, three columns
python3 sw/ghost_pred_cell.py run                    # socket, G-5
python3 sw/ghost_pred_cell.py run --fabric           # ucore in FPGA, NEW
python3 sw/ghost_pred_cell.py idle                   # use_core back to False
python3 sw/f20_cell.py --chip-ref <banked board dir> --json …/f20_cell.json

# the corpus
python3 sw/fz2_w1.py control ; python3 sw/fz2_w1.py preflight --board
python3 sw/fz2_w1.py capture
python3 sw/fz2_ledger.py --out sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json

# era guard ON, no bypass anywhere
python3 sw/fz2_replay.py --ledger <F20> --all-failures --pass-sample 150 --leg ret --jobs 8
python3 sw/fz2_immaterial.py --ledger <F20> falsify
python3 sw/fz2_w1.py bars ; python3 sw/fz2_w1.py lint

python3 sw/tf0f_cell.py run --strata nop,x1b,z1b ; python3 sw/tf0f_cell.py score
python3 sw/ie_pinfall_cell.py run --strata eihlt_w0,ierun_w0 --limit 20 ; python3 sw/ie_pinfall_cell.py score
python3 sw/check_ab_hw.py chip 800                   # close-out
```

## Appendix B — THE BAR IN ONE TABLE, FOR THE SCORER

| clause | registered value |
|---|---|
| **G-1 CHIP vs FABRIC** | **398 identical / 122 different**, the same 122 cells |
| **G-2 FABRIC vs CORE** | **528 / 528 identical, 0 differing** |
| G-3 `imul` in fabric | **16 / 16** |
| G-4 per-leg profile | 13 legs on their registered numbers |
| G-5 socket column | **528 / 528 byte-identical** to the FLASH #18 bank |
| G-6 HEAD offline comparand | **398 / 122**, banked `core/` restored byte-identical |
| P-1 / P-2 G6 worst-of-2 | **45.61 / 44.32**, `.rbf` `277e7de5…` / `15742aa2…` |
| F-1 flash | VERIFY OK, log **22 → 23** |
| first light | **MATCH 800 ×3** |
| **C-4 headline** | **110 / 3,837**, band [100, 120] |
| C-5 unregistered flips | **0**, budget 10 |
| C-6 first divergence off the named seats | **0 of 79** |
| **C-14a** four closures | `521024` · `522002` · `530020` · `534003` all LEAVE |
| **C-14b** 27 survivors | each on its registered `diverging_rows` |
| **C-14c** direction | **0 LOST · 0 `first_bad` EARLIER** |
| C-9 / C-10 / C-11 / C-12 | 6/6 unmoved · 3 absent + 3 at (1, 243/234/583) · `404040` ABSENT · LEA-mod3 6/6 |
| C-15a class | **24 → 22**, leavers exactly `521024` + `522002` |
| C-15e G6/G7 | **registered to FAIL on doc staleness alone**; G1–G5, G8 PASS |
| Q-1 era guard | **PASS, no bypass** |
| Q-2 closing control | **260 / 260**, floor 255 |
| S-1 / S-2 chip columns | **0 movers** |
| close-out | `board_idle()` clean, `use_core=0`, **MATCH 800** |
