# FLASH #21 — PRE-REGISTRATION: **THE TIMING CAMPAIGN'S FABRIC CONFIRMATION, AND ITS PRIMARY PREDICTION IS A NULL**

Committed **before any Quartus build and before any board contact**, together
with `sw/f21_wt1.py`, the clause-(v)/(vi) scorer, which is **proved non-vacuous
on the banked FLASH #20 captures below and before the board is touched**.

Board contact — flashing included, **`sw/safe_flash.sh` ONLY** — is authorised
by standing grant; the sitting discharges registered debt.

    branch      master
    HEAD        25b2f9bb69
    board now   FLASH #20, nec_test_ucore.sof 26d6e79166183a21…, built from
                3118a2db46 WITH X1_AD_RETENTION=1, flash_log.jsonl 23 entries
    manifest    88 declared inputs, 002f2fa4728ecac9…

Every bar below is reported in the form it is registered in. **Nothing is
re-registered after the fact.** A miss is a miss. **The null prediction means
ANY corpus movement is a FINDING TO ITEMISE, not a failure to argue away.**

---

## 0. WHAT THIS FLASH CARRIES, AND WHY THE PREDICTION IS A NULL

`git diff 3118a2db46..HEAD --stat -- hdl/` — everything below has landed since
FLASH #20 and **has never been in fabric**:

| file | ± | what it is |
|---|---|---|
| `hdl/nec_test.sdc` | +324/−… | **CONSTRAINTS.** The CE multicycle SPLIT BY ENABLE PHASE (`ce → ce_half` 2/1, `ce_half → ce` 3/2 beside the 4/3), **E-1 DELETED** (the observation multicycle), and the **`k = 0.5` class REMOVED** — measured gone, `ENABLE` now reads `k` 1.0000 and its ceiling left the ladder 90.91 → 141.20 MHz |
| `hdl/nec_test.qsf`, `hdl/nec_test_ucore.qsf` | +29 each | CRLF restoration + revision bookkeeping; `gen_ucore_qsf --check` is the gate that they remain faithful derivatives |
| `hdl/rtl/ucore/v30u_eu.sv` | +106/−… | **RTL.** `CHAIN_MAX` 12 → 7 (`4dd395a7ad`) **and** L1, the registered microcode decode (`9bf70f2eec`) |
| `hdl/rtl/ucore/v30u_biu.sv` | +37/−… | **RTL.** the `t1_half2` flop `negedge` → `posedge` under the same `ce_half` enable (`638ed01450`) |
| `hdl/rtl/ucore/v30_core.sv` | +3/−1 | the contract assertion's instantiation |
| `hdl/tb/*` (`tb_v30_core`, `tb_sys`, `tb_chain_lfsr`, `ce_contract_check`) | +630 | **TESTBENCH ONLY — IN NO BITSTREAM.** Listed so it is not mistaken for one |

**THREE OF THE FOUR RTL LANDINGS ARE REGISTERED ZERO-BEHAVIOUR AND WERE
MEASURED AS SUCH OFFLINE**, and the fourth is a constraint set:

* **`CHAIN_MAX` 12 → 7** — zero-behaviour by its own registered ladder;
  ALMs −15.6 %.
* **L1** — 306 fz2 seeds / **1,243,278 replayed rows**, 4 × 400,000 LFSR
  clocks and 2,200 ie-pinfall cells **byte-identical**.
* **the negedge removal** — every contract-legal instrument in the tree
  byte-identical across the change (`tb_sys` 306 seeds, the 2,200 + 528
  directed cells, `check_ab_sim`, the whole `check_core` family).

**SO THE PRIMARY PREDICTION OF THIS SITTING IS A NULL, AND A NULL IS THE
STRONGEST FORM AVAILABLE HERE.** Four landings, none of which may move a
single seed.

### 0.1 THE ONE THING THAT HAS NEVER BEEN IN FABRIC, AND IT IS NOT A NULL

**L1 makes Quartus infer an M10K for the microcode decode** —
`altsyncram:ucdecode_rtl_0`, `OPERATION_MODE ROM`, 8192 × 12, with `dec_q[0..9]`
packed in as its address register and `INIT_FILE db/…hdl.mif`. **No bitstream
carrying a block-memory `ucdecode` has ever been programmed into this FPGA.**

F44's failure mode is a **silently empty table**: the design runs and the
microcode is wrong. **Verilator cannot see it** — it reads `ucdecode.hex`
through `$readmemh` while Quartus programs a `.mif` it generates itself, so
every functional gate in this repo is blind to it. That is why **N-1** exists
and why it is not optional.

### 0.2 THE NOISE FLOOR GOVERNS EVERY AGGREGATE CLAIM

`docs/notes/fz2_capture_noise_2026-08-10.md`: **10 / 3,840 = 0.2604 %**
ledger-class flips. FLASH #17 spent 7; #18 spent 0; #19 spent 6; **#20 spent 6
and all six were FLASH #19's own movers reverting.**

**The unregistered-flip budget for this sitting is 10 seeds.** Because the
prediction is a null, **every flip is unregistered by construction**, and each
is itemised with tier, `escaped`, `ps3_8080` and both eras' `bad_rows` /
`first_bad_row`. ⚠ **The escaped-seed caveat is stated in advance**: seeds
carrying a large `escaped` count reach memory the harness does not model and
their row streams are known to be less stable than the rest of the corpus.

---

## 1. THE BUILD — G6, **ONE DRAW PER CONFIGURATION**

**Per the seeds ruling of 2026-08-13**: a landing wave's compile **VERIFIES THE
LANDING**; it is **not an Fmax measurement**. Both legs are
`--seeds 1`, i.e. **`draw@seed1`**, and **no band, no spread, no worst-of-N and
no Fmax claim is made anywhere in this sitting.** §74.4 governs — one green
build is not closure, and the same tree has drawn 19.42 and 45.91 MHz.

| # | bar |
|---|---|
| **E-1** | `gen_ucore_qsf --check` PASSES before each draw |
| **E-2** | 0 compile errors, every stage Successful, 0 latches, 0 `lpm_divide` |
| **E-3** | `divclk` Fmax **≥ 32.0** (G6) **and ≥ 38.0** (this branch's live STOP) |
| **E-4** | worst setup slack **> 0** on every domain |
| **E-5** | **TNS 0.000, setup AND hold, every domain** |
| **E-6** | the RETENTION receipt's **DERIVED** `configuration` self-labels `RETENTION (X1_AD_RETENTION=1)` |
| **E-7** | the CONTROL receipt's **DERIVED** `configuration` self-labels `CONTROL/DEFAULT` |
| **E-8** | the RETENTION `.rbf` **DIFFERS** from the CONTROL `.rbf` — the check that `--verilog_macro` reached the compiler |
| **E-9** | the 88-file input manifest reads **`002f2fa4728ecac9…`** on both draws |
| **E-10** | the fitter honoured `--seed=1` on both readings (`Info: Command:` **and** the `Fitter Initial Placement Seed` row) |
| **E-11** | both receipts retained in `sw/testdata/receipts/quartus_bitstream.jsonl`, each labelled `draw@seed1` |

### 1.1 THE EXPECTED NEIGHBOURHOOD — **REGISTERED, AND NOT A BAR**

The 88-file manifest at HEAD is **`002f2fa4728ecac9…`**, byte-for-byte the
manifest of the ce/ce_half re-land's own two draws. Same inputs, same flow, same
tool, same seed. So this is what is expected, **and a differing draw is NOT a
failure of this sitting — it is §74.4 evidence and will be quoted as such**:

| | expected (NOT a bar) |
|---|---|
| CONTROL `draw@seed1` | **42.06 MHz**, worst setup **+7.473 ns**, ALMs **10,053**, `.rbf` `3d4700c0b0453ee3…` |
| RETENTION `draw@seed1` | **43.30 MHz**, worst setup **+8.156 ns**, ALMs **10,079**, `.rbf` `a9667cf1aa6d3715…`, `.sof` `ecdabe0f56f0ae69…` |

⚠ **The retention-vs-control sign is INVERTED on this tree (+1.24 MHz) and it
is reported, never explained, and never computed as a delta from a draw pair.**

**HARD STOP: RETENTION `draw@seed1` < 38.0 MHz → NOTHING IS FLASHED.**

---

## 2. **N-1 — THE M10K BAR.** THE NEW ONE, AND IT IS NOT OPTIONAL

| # | bar |
|---|---|
| **N-1** | `python3 sw/ucrom_mif_check.py` **PASS on the FLASHED build's own `db`** — it reads `hdl/db/…hdl.mif`, so it is on-demand after that build and **cannot be run in advance**. 8192 × 12 against `ucdecode.hex` **and** 1028 × 29 against `ucrom.hex`, **every word**, an address absent from the `.mif` counting as a MISMATCH and not a skip |
| **N-1b** | its **non-vacuity control** in the same sitting: one flipped bit → FAIL |
| **N-2** | first light `check_ab_hw all 800` — **MATCH ×3** (chip-vs-golden, core-vs-chip, core-vs-golden) |

**N-1 runs against the RETENTION `db`, because the RETENTION build is the one
that is flashed.** A CONTROL-only `.mif` check would be checking a bitstream
nobody programs.

**HARD STOP: N-1 not PASS → NOTHING IS FLASHED.**

---

## 3. THE FLASH (`F-1`)

**`sw/safe_flash.sh` ONLY**, with its VERIFY leg, on the **RETENTION** build.

| # | bar |
|---|---|
| **F-1** | flash succeeds, **VERIFY OK**, `flash_log.jsonl` **23 → 24 entries**, tail `verify: "OK"`; `.sof` and `.rbf` sha256 recorded here and in the results |

Single-writer is asked of the board **before first contact** and again before
each subsequent leg; `--force` is not used. `div_guard()` on every probe — an
**UNPINNED readback is a rig-integrity HARD STOP**. Socket legs are
`use_core=False`, explicit.

---

## 4. THE CORPUS — **THE PREDICTION IS "NOTHING MOVES"** (`C-1` … `C-15`)

`fz2_w1 control` → `preflight --board` → `capture` → `fz2_ledger`, scored
against the FLASH #20 ledger `sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json`.

### 4.1 THE HEADLINE

| # | bar | registered |
|---|---|---|
| **C-1** | corpus identity | `SEED_LIST_SHA256 45d25f31a325c496…`, 960 + 2,880 = **3,840**, 48 strata, `fz2_w1 lint` PASS |
| **C-2** | completeness | **48 / 48 strata, every `rc 0`** |
| **C-3** | the flash pin | `distinct_eras` **1**, `absent` 0, `incomplete` 0, `build_stale` 0, every row's `era.sof_sha256` = FLASH #21's |
| **C-4** | **THE HEADLINE — THE NULL** | **106 failures of 3,839 EXACTLY.** Tolerance: the 0.26 % noise floor, i.e. a **band of [96, 116]**; the **POINT is 106 and a point miss is reported as a miss** |
| **C-5** | membership flips | **0 ENTERED, 0 LEFT.** Budget **10 seeds** (the noise floor). Every flip itemised, with the escaped-seed caveat |
| **C-6** | **THE SEAT TABLE — ALL 106 SEAT-FOR-SEAT** | every FLASH #20 failure present with **the same `diverging_rows` AND the same `first_bad_row`**. Registered as the sha256 of the canonical seat list, **`a6085ccc0dc739a2f56352419f81b3276d701dedbb501302389aad373397b76d`** (derivation in Appendix A) |
| **C-7** | direction | **0 LOST** and **0 `first_bad` EARLIER** anywhere in the corpus |
| **C-8** | the row metric | Σ`diverging_rows` **100,493**, `rows_diverging` **100,431**, `rows_compared` **11,330,230**, seed match **97.2389 %**, row match **99.1136 %** — reported; **a delta must reconcile to zero unexplained rows** |
| **C-9** | discards | **1** (`fz2e/509069`), denominator **3,839**. ⚠ `_ps3_8080` is a **SOCKET-leg** predicate (A-2) that **no RTL change can reach**; it has re-rolled on five consecutive eras (2 → 2 → 3 → 1 → 3 → 1), so this is **reported with both bases and NOT barred** |

### 4.2 THE NAMED NON-MOVERS — REGISTERED VALUE FOR VALUE

`diverging_rows / first_bad_row`, both columns, from the FLASH #20 ledger:

| # | group | registered |
|---|---|---|
| **C-10** | KM's three | `fz2c/404041`, `fz2e/501066`, `fz2e/513019` — **ABSENT** |
| **C-11** | phantom-T1's three | `fz2c/404071` **1 / 243** · `fz2e/514044` **1 / 234** · `fz2e/516001` **1 / 583** |
| **C-12** | §64.1's four | `fz2c/405002` **840 / 527** · `fz2c/405013` **921 / 1331** · `fz2c/405072` **891 / 636** · `fz2e/512056` **984 / 1475** |
| **C-13** | W7-4's surviving two | `fz2c/410047` **3589 / 227** · `fz2e/535027` **3226 / 296** |
| **C-14** | M10's LEA-mod3 six | `fz2c/406054` **3141 / 470** · `fz2c/408019` **1087 / 1617** · `fz2e/518038` **194 / 429** · `fz2e/522019` **3075 / 396** · `fz2e/524034` **3479 / 457** · `fz2e/530001` **20 / 442**. ⚠ `fz2e/520066` **8 / 1249** is registered as a regression check ONLY — it SELECTED F-B′'s `eu_word` term and its own value is not evidence |
| **C-15** | **the falsifier** | **`fz2c/404040` stays ABSENT from the ledger** |

⚠ **THE TWO SEEDS FLASH #20 REGISTERED TO GET WORSE ARE NOW NON-MOVERS**:
`fz2c/406063` at **3,165 / 249** and `fz2e/528010` at **7 / 1383**. They moved
for a named mechanism at FLASH #20 and nothing in this tree touches that
mechanism, so they are inside C-6 like everything else.

### 4.3 `fz2_immaterial falsify` ON THE F21 LEDGER (`C-16`)

| # | registered |
|---|---|
| **C-16a** | the `IMMATERIAL` class is **22 members, COSMETIC 17 · TRANSIENT 5**, **0 entrants and 0 leavers**, working residue **84** |
| **C-16b** | the partition is **FUNCTIONAL 44 · TIMING 30 · TRANSIENT 5 · COSMETIC 17 · UNSCOREABLE 10 = 106**, `TIMING_RECONVERGED` **7** |
| **C-16c** | **G1–G8 all PASS, exit 0** — the F20 housekeeping re-pinned both documents to this era, so unlike FLASH #20 the document clauses G6/G7 are registered to **PASS**, not to fail on staleness |
| **C-16d** | `fz2e/528010` stays **COSMETIC at 7 rows**; `fz2c/409065` 12 COSMETIC · `fz2e/521049` 10 COSMETIC · `fz2e/525017` 8 COSMETIC · `fz2c/408021` 22 TRANSIENT |

---

## 5. **CLAUSES (v) AND (vi) — THE PIN THIS WAVE MOVED**

`ce_contract_reland_results_2026-08-13.md` §10. The `t1_half2` flop moved from
`negedge` to `posedge` under the same `ce_half` enable, so **the AD turnaround
on a write T1 now sits at `ce_half`+1.0 fabric periods instead of +0.5**. That
is the ONLY pin transition this wave moves, so **the MEMW/IOW T1 rows of the
fabric captures are its whole silicon surface**, and the offline argument that
predicts they do not move is an argument **about a rig**. Silicon is not a rig.

Scored by `sw/f21_wt1.py`, committed with this document.

### 5.1 THE FIVE MEASUREMENTS

| # | clause | what it compares | **registered** |
|---|---|---|---|
| **V-A** | (v) as stated: **vs the F20 capture** | the FPGA core against ITSELF across the pin move, whole-record equality on every write-T1 row of every seed retained in both eras | **0 differing, 0 membership moved** |
| **V-B** | (v) read as *on silicon* | core vs the SOCKETED PART on the F21 capture, on rows before `first_bad` | **≤ 4 differing** |
| **VI-A** | (vi) ADDRESS sample | `ad_addr(core) == ad_addr(chip)` on clean rows | **100 %, 0 disagreements** |
| **VI-B** | (vi) DATA sample | `ad_data(T1) == ad_data(T2)` **and** `ad_data(core) == ad_data(chip)` on clean rows | **`data_moves` 0** and **≤ 4** chip disagreements |
| **VI-C** | the control | `(ad_addr & 0xFFFF) == ad_data` on the following **T2** row — the same predicate as VI-A with the opposite expected answer one row apart, so VI-A cannot be passed by a bus that never turns around at all | **0 not-turned** |

### 5.2 THE BASELINE IS **NOT ZERO**, AND IT IS MEASURED BEFORE THE BUILD

Measured on the banked FLASH #20 captures, **645 seeds, 42,185 write-T1 rows**,
before this document was committed:

    V-A  differing 0                     V-B  4 differing of 36,845 clean rows
    VI-A 36,845 / 36,845 vs chip         VI-B 36,841 / 36,845, data_moves 0
    VI-C 42,185 / 42,185 turned          clause counts (0, 4, 0, 4, 0)

**THE FOUR ARE NAMED**: `fz2c/406046` @3525 · `fz2e/521016` @361 ·
`fz2e/529009` @907 · `fz2e/531039` @1011, and **all four differ in `ad_data`
ALONE**.

⚠ **AND THAT IS A FINDING IN ITSELF, REGISTERED BEFORE THE SITTING**:
`fuzz_classify.diff_rows` **does not compare `ad_data` on a T1 row at all** (it
reads `data` only at T2/T3 and `nxta` only at T4/Ti). **So those four rows are
invisible to every standing gate in this repo, and so would a turnaround that
moved by a whole sample be.** That blindness is exactly why clause (vi) is
owed, and `f21_wt1.py` adds `ad_data` to its own column set for that reason and
states so in its header.

### 5.3 THE SCORER'S NON-VACUITY, RUN BEFORE THE BOARD IS TOUCHED

`python3 sw/f21_wt1.py --before-suffix "" --ledger <F20> --self-test --null 5`
— the identity pair, then the same pair with five write-T1 rows perturbed by
one bit each in the T1's `ad_addr`, the T1's `ad_data` and the following T2's
`ad_addr`:

    identity   clause counts (0, 4, 0, 4, 0)     all five MET
    --null 5   clause counts (5, 9, 5, 14, 5)    all five MISSED

**5 / 5 counts move. NON-VACUOUS**, exit 0. A scorer that cannot fail is not a
scorer, and this one is shown to fail before it is asked to pass.

⚠ **TWO CONSTRUCTION ERRORS WERE FOUND BY THAT SELF-TEST AND ARE RECORDED
RATHER THAN SILENTLY FIXED**, because both would have manufactured a false
miss on the day:

1. **`first_bad_row` is a LIST POSITION, not the `idx` field.** The captures
   start at `idx` 33; comparing one to the other mis-split the population.
2. **A DISCARDED seed has no `first_bad_row` and diverges end to end.**
   Treating an absent `first_bad` as "clean everywhere" put all 41 of
   `fz2e/509069`'s write-T1 disagreements into the clean population and made
   the baseline read as a residue it does not have.

⚠ **A SHARPER VI-A PREDICATE WAS TRIED AND DOES NOT DISCRIMINATE.** An early
turnaround should carry the 20-bit signature `ad_addr == (ps << 16) | ad_data`;
measured, **all 7 low-16 coincidences in the F20 population satisfy it too**
(`fz2c/409014` writes 0xcccc to 0x0cccc; `fz2c/400016` writes 0x00fe to
0x000fe), because a write whose word equals its own address low half is
indistinguishable from an early turnaround **by construction**. So it is
**REPORTED and NOT BARRED**, and the barred quantity is agreement with the
socketed part, which sees the same coincidences and would not see the same
early turnaround. **An actually-early turnaround is 42,185 rows, not 7.**

---

## 6. THE DIRECTED-CELL SPOT-CHECKS

Socket legs measure **SILICON**, which no bitstream can move. The `ghost-pred`
fabric leg measures the **synthesised core**, which four zero-behaviour
landings must not move either.

| # | leg | registered |
|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` (48 cells) + `score` | **0 chip-column movers**, sha256 0 differing over 512; KM **16/16** derivation and **14/14** validation legs; NULL `notf` / `v_notf` **[0]** both; 0 transport errors |
| **S-2** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells) + `score` | **0 chip-column movers** over 2,200 cells, sha256 0 differing; the six invariant columns `wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows` **0 / 1,920**; `n_inta` **36**, `ack_off` **46**, `ack_off_hlt` **46**. ⚠ **the core column at HEAD is the re-derived `963a8065eb94b49c…`** and is verified by hash, not re-taken |
| **S-3** | `ghost_pred_cell run` (socket) + `run --fabric` + `f20_cell` | **CHIP vs FABRIC 398 / 122**, **FABRIC vs CORE 528 / 528 identical, 0 differing**, and the fresh socket column **528 / 528 BYTE-IDENTICAL** to the FLASH #20 bank. ⚠ **A SOCKET-COLUMN MOVER IS A RIG FINDING AND OUTRANKS THE CELL** |
| **S-4** | restoration | every banked tree copied aside before and restored **byte-identical** by sha256; the F21 rows retained **beside** them, never merged over them |

⚠ **`ghost_pred_cell core` IS NOT ON THE ARTIFACT LAYER** (FLASH #20 §8, still
booked). **If any `core` column is re-taken in this sitting,
`artifact.require()` is called by hand on both `tb_sys` legs first and the
receipt ids recorded beside the column.** The F20 sitting's stale-binary
finding is the reason this sentence is here.

---

## 7. THE ERA GUARD AND THE CLOSING CONTROL

| # | bar |
|---|---|
| **Q-1** | `fz2_replay` passes the **fabric era guard with NO bypass** — 88 / 88 inputs hash identical in the tree at HEAD. It **MUST REFUSE at HEAD before the flash**, by name, on the four `hdl/rtl/ucore/` + `hdl/nec_test.sdc` files that postdate FLASH #20; a guard that passes before the flash is a guard that is not working |
| **Q-2** | closing control: `fz2_replay --all-failures --pass-sample 150 --leg ret` — **agreement ≥ 99 % on the 256-seed population** (106 + 150), with `first_bad` IDENTICAL on the failures |
| **Q-3** | `use_core=0` chip proof **`check_ab_hw chip 800` MATCH** after everything; `div_guard` **PINNED on 100 % of probes**; `board_idle()` clean and **last** |

---

## 8. THE STANDING GATES ON THIS ERA (`C-17`)

| gate | registered |
|---|---|
| `fz2_w1 bars` | **11 / 11 MET**, leaf-diffed against the F20 archive with any moved verdict named |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 control` (C-6 board legs) | **9 legs**, holds `[2, 20, 300]` on `pin_int` and `pin_nmi`, N1 negative control PASS, **0 unpinned** |
| `fz2_w1 preflight --board` | **OK** — single writer, era pinned to FLASH #21's receipt self-labelling RETENTION, regeneration sample **0 hits**, RBCHECK **8 registers**, MATCH 800 ×3 |
| `check_fuzz_bank` | **PASS — 621 banked seeds**, stable 621 / improved 0 / worse 0, `gen_drift` 0, `regen_err` 0, new-sig TIMING 0 |
| `r7_lint` | **PASS** — 0 undeclared carriers, 3 declared tainted, **51 `stop` sites, 0 violations** |
| `ss_lint --core ucore` | **PASS at `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8** (BIU 109 + EU 122 symbols). ⚠ **the flop census reads 221, not FLASH #20's 220**, and the cause is named: L1's `dec_q` is a real flop and is **WHITELISTED as DERIVED**, not mapped — `{dec_valid,dec_bank} = ucdecode[dec_addr_next]` is reconstructed on the restoring edge, so mapping it would give one fact two sources of truth. **The MAP did not move and `SS_VERSION` did not move** |
| `gen_ucore_qsf --check` | **PASS** |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `check_ab_hw all 800` / `chip 800` | first light **MATCH ×3**; close-out **MATCH over 800 rows** |
| §38.9 missed-trap overlay | **4** |

⚠ **NOT RUNNABLE AND NOT QUOTED ON THIS BRANCH**: `timed_scenario`,
`timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`
(`gen_seq._v1_anchor_stop`); **`x1_retention` / `x1_fabric`** (GEN-DRIFTED since
FLASH #19), so **the 283-cell HLT sweep column that confirmed several earlier
flashes does not exist for this bitstream** — its role is carried by §6's
528-cell grid and §5's 42,185-row write-T1 population; and the four v1 fuzz
banks (SUP-1 / D9).

---

## 9. HARD STOPS

1. RETENTION `draw@seed1` **< 38.0 MHz**, or any G6 essential RED → **nothing is flashed**.
2. **N-1 `ucrom_mif_check` not PASS on the flashed build's `db`** → **nothing is flashed**.
3. The RETENTION receipt self-labelling `CONTROL/DEFAULT`, or its `.rbf` equal to CONTROL's (E-6 / E-8) → **nothing is flashed on that build**.
4. `safe_flash` VERIFY not OK.
5. Any `div_guard` **UNPINNED** readback.
6. Any `RigMismatch` / transport quarantine.
7. A failed single-writer check that is not resolved (`--force` is **not** used).
8. `check_ab_hw` first light failing on any of its three legs.
9. **S-3's socket column moving** — a rig finding outranks the cell.
10. `ss_lint` not reading 0x8E / 232 → the bitstream is not this tree's.

**And FLASH #19's re-run rule is adopted verbatim**: if a leg fails, **the
failing leg is re-run once on the same bitstream before anything is
concluded**, and the finding is reported before any repair is attempted. **No
repair is attempted in this sitting.**

---

## 10. WHAT THIS SITTING CAN AND CANNOT ESTABLISH

**CAN**: that a bitstream whose microcode decode lives in an M10K runs this
part's whole corpus identically to one whose decode is LUT logic; that four
landings measured zero-behaviour offline are zero-behaviour **in fabric**; and
that the AD turnaround, moved half a CPU clock later in time, lands in the same
place on every one of ~42,000 write T1s **on silicon**.

**CANNOT**: attribute anything to any ONE of the four landings — they are
flashed as a bundle and a bundle's benefit is not evidence for any member of
it. It also **cannot** measure Fmax: one draw per configuration, by ruling.

---

## Appendix A — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                   # 25b2f9bb69
python3 -c "import sys;sys.path.insert(0,'sw');import quartus_gate as q;m=q.input_manifest();print(m['n_files'],m['sha256'][:16])"
                                                     # 88 002f2fa4728ecac9

# THE SEAT DIGEST (C-6), from the FLASH #20 ledger
python3 - <<'PY'
import json, hashlib
L=json.load(open('sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json'))
s={f['seed']:(f['diverging_rows'], f['first_bad_row']) for f in L['failures']}
c=json.dumps(sorted((k,)+tuple(v) for k,v in s.items()), sort_keys=True)
print(len(s), hashlib.sha256(c.encode()).hexdigest())
PY
# 106 a6085ccc0dc739a2f56352419f81b3276d701dedbb501302389aad373397b76d

# the scorer, proved before the board
python3 sw/f21_wt1.py --before-suffix "" \
  --ledger sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json \
  --self-test --null 5                               # 5/5 moved, NON-VACUOUS

# the build -- ONE draw each, draw@seed1
python3 sw/quartus_gate.py --seeds 1             --label "fz2 FLASH#21 CONTROL draw@seed1"
python3 sw/quartus_gate.py --seeds 1 --retention --label "fz2 FLASH#21 RETENTION draw@seed1"
python3 sw/ucrom_mif_check.py                        # N-1, on the RETENTION db

sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof
python3 sw/check_ab_hw.py all 800                    # N-2, first light

python3 sw/fz2_w1.py control ; python3 sw/fz2_w1.py preflight --board
python3 sw/fz2_w1.py capture
python3 sw/fz2_ledger.py --out sw/testdata/fz2/fz2_failure_ledger_f21_2026-08-13.json
python3 sw/f21_wt1.py --ledger <F21> --json sw/testdata/fz2/f21_wt1.json
python3 sw/fz2_replay.py --ledger <F21> --all-failures --pass-sample 150 --leg ret --jobs 8
python3 sw/fz2_immaterial.py --ledger <F21> falsify
python3 sw/fz2_w1.py bars ; python3 sw/fz2_w1.py lint

python3 sw/tf0f_cell.py run --strata nop,x1b,z1b ; python3 sw/tf0f_cell.py score
python3 sw/ie_pinfall_cell.py run --strata eihlt_w0,ierun_w0 --limit 20 ; python3 sw/ie_pinfall_cell.py score
python3 sw/ghost_pred_cell.py run ; python3 sw/ghost_pred_cell.py run --fabric
python3 sw/check_ab_hw.py chip 800                   # close-out
```

## Appendix B — THE BAR IN ONE TABLE, FOR THE SCORER

| clause | registered |
|---|---|
| E-1 … E-11 | G6 green on both `draw@seed1` legs, manifest `002f2fa4728ecac9…`, `.rbf`s differing |
| **N-1** | `ucrom_mif_check` **PASS on the flashed `db`**, non-vacuity control FAILs |
| **N-2** | first light **MATCH 800 ×3** |
| F-1 | VERIFY OK, `flash_log` **23 → 24** |
| **C-4** | **106 / 3,839 EXACTLY** |
| **C-5** | **0 entered, 0 left**, budget 10 |
| **C-6** | seat digest **`a6085ccc0dc739a2…`**, 106 / 106 |
| C-7 | 0 LOST, 0 `first_bad` earlier |
| C-10 … C-15 | the named non-movers, value for value; `fz2c/404040` ABSENT |
| C-16 | `falsify` **G1–G8 PASS**, class **22**, partition 44/30/5/17/10 |
| **V-A** | **0 differing** |
| **V-B** | **≤ 4** clean-row differences |
| **VI-A** | **100 %** address-sample agreement with silicon |
| **VI-B** | **`data_moves` 0**, **≤ 4** chip disagreements |
| **VI-C** | **0** not-turned |
| S-1 … S-4 | 0 chip movers; ghost-pred 398/122, 528/528, socket byte-identical |
| Q-1 | era guard **PASS 88 / 88, no bypass**, and REFUSING before the flash |
| Q-2 | closing control ≥ 99 %, `first_bad` identical |
| Q-3 | chip proof MATCH 800, `div_guard` PINNED, `board_idle()` clean |
