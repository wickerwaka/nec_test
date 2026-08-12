# FLASH #19 — PRE-REGISTRATION: **E-1's FABRIC CONFIRMATION, ALONE**

**COMMITTED BEFORE ANY QUARTUS BUILD AND BEFORE ANY BOARD CONTACT.**
Branch `fuzz-v2-on-relanding`, HEAD **`a37f05d4b8`**.
Board contact — flashing included, **`sw/safe_flash.sh` only** — is authorised
by the user (standing grant + the option-3 sequence: *timing recovery, then
land*).

---

## 0. WHAT THIS SITTING IS FOR, AND WHAT IT IS NOT

**ONE QUESTION: is E-1 true in fabric?**

E-1 (`7ad102098f`, pre-registered `22c6f8b540`, census `84cec65cfe`) is **one
`set_multicycle_path -setup 2 / -hold 1` pair** in `hdl/nec_test.sdc`, from the
`v30u_*` registers to the harness's free-running input-registration flops
(`nec_bus|ad_in_q[*]` and siblings — 28 endpoints in CONTROL, 48 under
`X1_AD_RETENTION`). It is derived from the RTL's own tick structure: the RTL
grants **3** sys periods at the divider of record and the constraint claims
**2**.

`timing_recovery_results_2026-08-11.md` §5 states, before this sitting existed:

> **A timing exception is a claim about the real circuit and no offline gate can
> falsify it.** Verilator does not model it, `check_core` does not model it, and
> G6 merely *believes* it.

If the multicycle assumption is wrong, the analyser has been told to ignore a
path that really is single-cycle, the fabric samples the bus mid-transition, and
**the observation path corrupts**. That is what the board legs below test.

### 0.1 THE FLASH IS **UNBUNDLED**, AND THAT IS VERIFIED, NOT ASSERTED

E-1 is `hdl/nec_test.sdc` + tools + docs. **No RTL, no `sim/`.** Measured at the
top of this sitting, before anything else:

    git diff 770c0d1b85 HEAD -- hdl/rtl/ sim/      ->  EMPTY (0 files, 0 lines)

`770c0d1b85` is FLASH #18's results commit. **The RTL in this flash is FLASH
#18's RTL, byte for byte.** A second agent is working OFFLINE in a worktree
(`.claude/worktrees/agent-a235820721ac7b80a`) on the ghost relocation; **none of
that work is in this tree and none of it is in this flash.** The check above is
re-run immediately before the build and immediately before the flash, and a
non-empty result is a **HARD STOP**.

Consequence, and it is the point of unbundling: **any deviation from the bar is
attributed to E-1 FIRST**, because the SDC is the only delta.

### 0.2 THE MANIFEST DELTA, NAMED

Against FLASH #18's flashed receipt (`277d5ccf0f8b9398…`, 88 declared inputs),
the tree at HEAD differs in **exactly two files**:

    MOVED   hdl/nec_test.sdc          <-- E-1, the whole of it
    MOVED   hdl/nec_test_ucore.qsf    [EXEMPT: Quartus rewrites it in place, §70.7]

and the **fabric era guard is therefore FIRING at HEAD, by name**, on
`hdl/nec_test.sdc`. Re-syncing it is a registered clause (`Q-1`).

⚠ The guard prints `<-- RTL` beside `hdl/nec_test.sdc`. **That label is wrong
and the guard's behaviour is right**: the SDC is a declared, non-exempt input of
the bitstream and it moved. Noted so the label is not read as a claim that RTL
moved. **No tool change is made in this sitting** — a cosmetic edit to a gate on
the day the gate is load-bearing is exactly what this campaign's rules distrust.

### 0.3 THE NOISE FLOOR GOVERNS EVERY AGGREGATE CLAIM

`docs/notes/fz2_capture_noise_2026-08-10.md`: the floor is **10 / 3,840 =
0.2604 %** ledger-class flips. FLASH #17 spent **7** of that budget; FLASH #18
spent **0**.

**E-1 CHANGES NO LOGIC.** The predicted corpus delta is therefore **ZERO
seeds** — below the floor by construction. So:

**THE REGISTERED CLAIM OF THIS SITTING IS THE THREE FABRIC-BAR LEGS (§3).
THE CORPUS IS A REGRESSION, NOT EVIDENCE FOR E-1.** But the direction of
inference is not symmetric, and this is registered before the run:

> **A seed-level change IS a FINDING against E-1's timing claim** — because
> nothing else in this tree can produce one — **and it is itemised against the
> 10-seed noise budget with the escaped-seed caveat, not waved at.**

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS, TWO DRAWS EACH (`E-1` … `E-12`)

`python3 sw/quartus_gate.py` (CONTROL) and `python3 sw/quartus_gate.py
--retention` (RETENTION). **This is `--retention`'s first FLASH-BOUND
exercise** — it existed and was exercised at F18 housekeeping, but no bitstream
it produced has ever been flashed. Its two effect-checks are therefore
registered clauses here, not assumed.

**Each draw from a deleted `db` / `incremental_db` / `output_files_ucore`.
Two draws per configuration. THE WORST DRAW IS THE FIGURE.** If two draws
disagree by more than 1.0 MHz a third is taken and the worst of three is quoted.

| # | bar |
|---|---|
| **E-1** | `gen_ucore_qsf --check` PASSES before each draw (it is G6's own E1) |
| **E-2** | 0 compile errors, every stage Successful, 0 latches, 0 `lpm_divide` |
| **E-3** | `divclk` Fmax **≥ 32.0** (G6) **and ≥ 38.0** (this branch's live STOP) |
| **E-4** | worst setup slack **> 0** on every domain |
| **E-5** | **TNS 0.000, setup AND hold, every domain.** ⚠ **Hold is E-1's own live risk** — a wrong `-hold` companion is invisible everywhere else |
| **E-6** | the RETENTION receipt's **DERIVED** `configuration` self-labels **`RETENTION (X1_AD_RETENTION=1)`** |
| **E-7** | the CONTROL receipt's **DERIVED** `configuration` self-labels `CONTROL/DEFAULT` |
| **E-8** | the RETENTION `.rbf` **DIFFERS** from the CONTROL `.rbf` (the check that the macro reached the compiler) |
| **E-9** | the 88-file input manifest reads **`b2e50a482ca1123b…`** on all four draws |
| **E-10** | `.qsf` regenerated and re-checked after each draw |
| **E-11** | both receipts retained in `sw/testdata/receipts/quartus_bitstream.jsonl` |
| **E-12** | E-1's own zero-delta ladder rows that could **not** run in the isolated worktree are run **here** (§5) |

### 1.1 THE POINT PREDICTION — AND WHY IT IS A POINT AND NOT A BAND

**The main checkout at HEAD hashes IDENTICALLY on all 88 declared inputs of the
E-1 CONTROL receipt `a799a8d56d88d9e4…`** (measured: 88 files, 0 differing,
`inputs.sha256 b2e50a482ca1123b…`). Same inputs, same flow, same tool.

The census's **F-4** finding is that Analysis & Synthesis **is** reproducible
run-to-run once inputs and configuration are held fixed (28 of 30 multi-draw
receipt groups exactly identical). E-1's own four draws were pairwise identical
including **byte-identical `.rbf`**. So:

| | **REGISTERED POINT** | band (containment) |
|---|---|---|
| **P-1** CONTROL worst-of-2 | **44.72 MHz**, worst setup **+8.887 ns**, ALMs **12,224** | [43.0, 47.0] |
| **P-2** RETENTION worst-of-2 | **45.71 MHz**, worst setup **+8.081 ns**, ALMs **12,200** | [42.0, 46.0] |
| **P-3** CONTROL `.rbf` | **`5b8695463675f732…`** byte-identical | — |
| **P-4** RETENTION `.rbf` | **`bcb48f01adf3e94d…`** byte-identical | — |

**A DIFFERING DRAW IS NOT A FAILURE OF THIS SITTING — IT IS §74.4 EVIDENCE AND
IT WILL BE QUOTED AS SUCH.** `standing_gates.md` §A governs: one green build is
not closure, and the same tree has drawn 19.42 and 45.91 MHz. A point that
reproduces across two worktrees strengthens F-4; a point that does not is the
most interesting number this sitting could produce about the build flow, and it
is reported, not buried.

**HARD STOP: RETENTION worst-of-2 < 38.0 MHz → NOTHING IS FLASHED.**

---

## 2. THE FLASH (`F-1`)

**`sw/safe_flash.sh` ONLY**, with its VERIFY leg, on the **RETENTION** build.

| # | bar |
|---|---|
| **F-1** | flash succeeds, **VERIFY OK**, `flash_log.jsonl` **21 → 22 entries**, tail `verify: "OK"`; `.sof` and `.rbf` sha256 recorded here and in the results |

Single-writer is asked of the board **before first contact** and again before
each subsequent leg. Socket legs are `use_core=False`, explicit. `div_guard()`
is called on every probe and an **UNPINNED readback is a rig-integrity HARD
STOP**.

---

## 3. **THE REGISTERED FABRIC BAR — THIS IS THE SITTING'S ONE QUESTION**

Quoted **verbatim** from `timing_recovery_results_2026-08-11.md` §5, written
before this sitting was contemplated:

> **The registered fabric bar for the first bitstream carrying E-1**:
> `check_ab_hw` first light **MATCH 800 ×3**, `x1_fabric baseline` reproducing
> its offline column with **0 PASS/FAIL disagreements and 0 differing
> coordinates**, and the closing `use_core=0` chip proof **MATCH 800**. Any
> deviation is attributed to E-1 **first**, because E-1 is the only thing that
> changed how the capture path is timed.

| # | bar | why it is the right falsifier |
|---|---|---|
| **B-1** | `check_ab_hw all 800` — **chip-vs-golden, core-vs-chip, core-vs-golden, all MATCH over 800 rows** | it reads the capture path **end to end**: every row is a sample taken by exactly the `nec_bus` registers E-1 relaxed |
| **B-2** | `x1_fabric baseline --leg fab_f19` reproduces the **offline `tb_sys ret` column** taken on this tree — see §3.1, the bar is **RE-DERIVED before the run** and B-2b carries the weight | 283 cells of the same path on identical stimuli; and `tb_sys` has **no** timing model at all, so agreement means the constraint did not change what fabric samples |
| **B-3** | `x1_fabric socket --leg soc_f19` — captured and reported | §52.9's rig-integrity control. ⚠ **NOT SCOREABLE AS 49/49 ON THIS BRANCH** — §3.2. Its rig-integrity role is carried by B-1 and B-4 |
| **B-4** | `check_ab_hw chip 800` **after everything** — **MATCH over 800 rows** | the socket position is `use_core=0`; E-1 cannot reach it, so a move here is a rig finding, not an E-1 finding |
| **B-5** | `board_idle()` clean, `use_core = 0` left selected | |

### 3.1 THE OFFLINE COLUMN B-2 IS SCORED AGAINST — TAKEN **BEFORE** THE BUILD, AND IT SURFACED A DEFECT

`python3 sw/x1_retention.py capture --leg ret` was run on this tree **offline,
no board, before this document was finished**: **283 cells, 0 errors, 67 s**,
DUT `hdl/tb/obj_dir_sys_ret/Vtb_sys`, receipt **`6e6589e25c2b90aa…`**, era stamp
`6141fe700d4db0f3…` = the current tree. Taking it first is deliberate: a column
taken after seeing the fabric number is not a prediction.

**Scored against the frozen goldens it reads 0 / 283**, every cell diverging at
row 0. **That is NOT a regression and NOT E-1.** It is GEN-DRIFT, and the
mechanism was isolated before this document was committed:

    tests/v30/s10-hltsweep-w0/HLT.INT  golden case vs es.gen_evt_case(spec, rng)
        the ONLY differing field is  ip:  33153 (golden)  vs  42352 (regenerated)
    tests/v30/s10-hltsweep-w0/HLT.RES
        the ONLY differing field is  ip:  40473 (golden)  vs  38998 (regenerated)

Every other register, the instruction (`F4`), the event and the delay are
**identical**. **The IMAGE ANCHOR MOVED under fuzz-v2** — the same
`gen_seq._v1_anchor_stop` class CLAUDE.md already names for `timed_scenario`,
`timed_ins_replay`, `timed_wvec_gate` and `timed_enter_replay`, and the reason
the goldens' RAM still carries the v1 `0x90` fill (`[634250, 144] …`) where the
composer now lays `0xCC`.

**BOTH x1 LEGS REGENERATE FROM THE SAME `random.Random("v30-s10-hlt/<form>")`
SEED**, so `x1_fabric baseline` drifts **identically**. Three consequences,
registered here rather than discovered later:

1. **`x1_retention` and `x1_fabric` JOIN THE LIST OF RATCHETS THAT CANNOT BE
   QUOTED ON `fuzz-v2-on-relanding`.** Engine-independent, predates E-1 by the
   whole fuzz-v2 branch. The last quotable leg is `fab_f11` at **279/283**.
   **No golden-relative x1 total may be quoted against this tree**, and none
   will be. This is a **FINDING of this sitting**, booked with its falsifier
   (a checkout of a pre-fuzz-v2 generator reproduces 279/283).
2. **The `check_core` HLT sweeps are UNAFFECTED and were re-measured**:
   `check_core --suite-dir tests/v30/s10-hltsweep-w0 --waits 0` = **97 / 97**.
   They read the case **out of the golden file** instead of regenerating it,
   which is precisely why they do not drift. So the HLT population itself is
   healthy and the defect is in the two x1 drivers' *stimulus regeneration*.
3. **THE BAR IS RE-DERIVED, AND THE RE-DERIVATION IS COMMITTED BEFORE THE
   BUILD AND BEFORE THE BOARD.** It is not weakened — it is moved onto the
   comparison the bar's own words name (*"reproducing its offline column"*),
   which is the E-1-relevant one and is **sharper** than the golden-relative
   form:

| | re-derived bar |
|---|---|
| **B-2a** | cell-level **PASS/FAIL and first-divergence-coordinate agreement** between `score_fab_f19` and the offline `ret` column, both scored by `check_core.diff_rows` against the same goldens: **283 / 283 agree.** ⚠ **DECLARED NEAR-VACUOUS UNDER GEN-DRIFT** — both legs fail nearly every cell, so agreement is cheap. It is reported because it is the bar's literal form, and it is **not** quoted as the result |
| **B-2b** | **THE LOAD-BEARING FORM: ROW-FOR-ROW.** For each of the 283 cells, `check_core.diff_rows(offline_ret_cycles, fabric_cycles)` must be **EMPTY**. Registered: **283 / 283 cells identical, 0 differing rows.** Fabric and Verilator run the *same regenerated stimulus*, so this compares what the board's `nec_bus` registers sampled against what an untimed model says they should have sampled — **exactly what a false multicycle would break**. Any differing cell is itemised with its coordinate and is **attributed to E-1 first** |

**THE SCORER IS `sw/f19_b2.py`, COMMITTED WITH THIS DOCUMENT AND BEFORE THE
BUILD, AND IT IS PROVED NON-VACUOUS ON A NULL BEFORE THE BOARD IS TOUCHED.**
`--null N` perturbs N offline cells in memory. Measured on the identity pair
(`--fab ret --off ret`):

    plain      B-2a 283/283 agree     B-2b 283/283 identical, 0 differing   MET
    --null 5   B-2a 283/283 agree     B-2b 278/283 identical, 5 differing   MISSED

**That null does two jobs at once.** It shows B-2b detects a one-bit,
one-row perturbation in five of five injected cells — and it shows **B-2a did
not notice any of them**, which is the declared near-vacuity **demonstrated**
rather than asserted.

⚠ **A KNOWN NON-E-1 CLASS IS PRE-DECLARED FOR B-2b**: the INTA pad-float
(§56.3a / C11). FLASH #19 is a **RETENTION** build, so the model is compiled in
and this class closed 119/119 at FLASH #6 and agreed cell-for-cell at FLASH #10.
If B-2b misses **only** on INTA-status rows, that is the float class re-opening
and it is reported as such — with the note that it would then also be the first
time a retention bitstream failed to close it.

⚠ **`x1_retention score` cannot run on this tree at all**: its era guard refuses
because the stored `base` column carries tree `2e71f4a8ab7c…` against the
current `6141fe700d4d…`. **The guard is NOT bypassed** and the stale `base` and
`offline` legs are **not quoted**. B-2 is computed directly from the two
columns' capture files.

### 3.2 B-3 — WHY THE 49/49 SOCKET CONTROL IS NOT A BAR HERE

`x1_fabric socket` regenerates its 49 `HLT.RES` cases from the **same** drifted
seed, so it too cannot reach the frozen golden. **Registering 49/49 would be
registering a bar that cannot be met for a reason that has nothing to do with
this sitting.** It is therefore **run and reported, not barred**, and the
rig-integrity role it plays is carried by bars that are unaffected:
**B-1** (`check_ab_hw all 800`, whose chip-vs-golden leg is the socket against a
boot capture that is not regenerated), **B-4**, and `div_guard` on every probe.

### 3.3 WHAT A FAILURE WOULD LOOK LIKE, WRITTEN DOWN BEFORE IT COULD HAPPEN

Registered so a post-hoc story cannot be substituted:

* **A metastable / mid-transition sample** is not a clean functional error. It
  looks like **sporadic, non-reproducible row differences** concentrated in the
  sampled columns (`ad`/`addr`/`data`, `bs`, `qs`, `ube`) — *not* a stable
  offset, and *not* reproducible cell-for-cell between two runs.
* **THE DISCRIMINATOR IS REPRODUCIBILITY, AND IT IS CHEAP**: if B-1 or B-2
  fails, **the failing leg is re-run once on the same bitstream before anything
  is concluded**. Reproducible-and-identical ⇒ a deterministic mechanism, which
  E-1 cannot be (a constraint cannot change logic); **non-reproducible ⇒ E-1's
  claim is false and the SDC comes back out**, per the revert rule already
  registered in `timing_recovery_prereg_2026-08-11.md` §4.
* Either way **the finding is reported before any repair is attempted**, and no
  repair is attempted in this sitting.

---

## 4. THE CORPUS — REGRESSION, WITH A FINDING RULE (`C-1` … `C-8`)

Full fz2 capture on FLASH #19, then `fz2_ledger`, scored against the **FLASH
#18 ledger** `sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json`.

**THE HEADLINE PREDICTION IS *UNCHANGED*: 110 failures of denominator 3,839.**

| # | bar | registered |
|---|---|---|
| **C-1** | corpus identity | `SEED_LIST_SHA256 45d25f31a325c496…`, 960 + 2,880 = **3,840**, 48 strata, `fz2_w1 lint` PASS |
| **C-2** | completeness | **48 / 48 strata, every `rc 0`**, 960 / 2,880 rows |
| **C-3** | the flash pin | `distinct_eras` **1**, `absent` 0, `incomplete` 0, `build_stale` 0, every row's `era.sof_sha256` = FLASH #19's |
| **C-4** | **the headline** | **failures 110**, denominator **3,839** (discards **1**, `fz2e/509069`) — **PRIMARY POINT = UNCHANGED**; containment band **[100, 120]** |
| **C-5** | **membership** | **entered 0 · left 0**, budget **10** (the 0.2604 % floor). ⚠ **Any flip is a FINDING against E-1**, itemised seed by seed with tier, `escaped`, `ps3_8080` and both eras' `bad_rows`/`first_bad_row` |
| **C-6** | **first divergence** | **0 seeds move `first_bad_row` in either direction** over all 110 |
| **C-7** | the row metric, **in both units** (F18 §1.1's erratum) | Σ`bad_rows` **109,678** and Σ`diverging_rows` **109,739** — reported; **not barred**, because long-tail row counts drifted −345 at F18 with zero membership movement |
| **C-8** | discards | **1**, `fz2e/509069`, denominator **3,839**. A re-roll is reported with both bases (A-12 / A-13); `_ps3_8080` is a **SOCKET-leg** predicate (A-2) and **E-1 cannot reach it by construction** — a mover here is a chip/rig observation, not an E-1 one |

### 4.1 THE FOURTEEN NAMED NON-MOVERS — SEAT-LEVEL, BOTH COLUMNS (`C-9`)

Registered in the ledger's `diverging_rows` unit (= `bad_rows` + `flick`) and
`first_bad_row`, read from the F18 ledger:

| group | seed | `diverging_rows` | `first_bad_row` |
|---|---|---:|---:|
| **§64.1 four** | `fz2c/405002` | 840 | **527** |
| | `fz2c/405013` | 921 | **1331** |
| | `fz2c/405072` | 891 | **636** |
| | `fz2e/512056` | 984 | **1475** |
| **W7-4 (older §64.1 four)** | `fz2c/406063` | 3149 | 245 |
| | `fz2c/410047` | 3589 | 227 |
| | `fz2e/518053` | 3413 | 567 |
| | `fz2e/535027` | 3226 | 296 |
| **M10 LEA-mod3 six** | `fz2c/406054` | 3141 | 470 |
| | `fz2c/408019` | 1087 | 1617 |
| | `fz2e/518038` | 194 | 429 |
| | `fz2e/522019` | 3075 | 396 |
| | `fz2e/524034` | 3479 | 457 |
| | `fz2e/530001` | 20 | 442 |

**C-9: all fourteen unmoved in BOTH columns. 14 / 14.**

The **KM three** (`fz2c/404041`, `fz2e/501066`, `fz2e/513019`) stay **ABSENT**;
the **phantom-T1 three** (`fz2c/404071`, `fz2e/514044`, `fz2e/516001`) stay at
`diverging_rows` **1** with `first_bad_row` **243 / 234 / 583**. That is
**C-10**, and it doubles as FLASH #18's confirmation surviving one more
bitstream.

### 4.2 THE FALSIFIER (`C-11`)

**`fz2c/404040` stays ABSENT from the ledger.** The branch's sharpest falsifier;
if a pure constraint change resurrects it, the constraint is not pure.

### 4.3 `fz2_immaterial falsify` (`C-12`)

**PASS, G1–G8, on the F19 ledger, with the class STABLE at 24 members**
(19 COSMETIC + 5 TRANSIENT), working residue **86 = 110 − 24**.
Measured on the F18 ledger before this document was written: **PASS, G1–G8, 24
members, 86 residue, UNSCOREABLE 11 · TIMING_RECONVERGED 8.**

**Class stability is scored SET-FOR-SET, not by count**, against these 24:

    fz2e/515056  fz2e/516029  fz2c/409065  fz2e/513026  fz2e/521049  fz2e/525017
    fz2e/529009  fz2c/404071  fz2e/514044  fz2e/516001  fz2c/408021  fz2c/409025
    fz2c/410008  fz2e/517046  fz2e/518033  fz2e/519072  fz2e/522029  fz2e/524055
    fz2e/528010  fz2e/530034  fz2e/535036  fz2e/521024  fz2e/522002  fz2e/532032

⚠ **G6 and G7 are doc-vs-derivation cross-checks and they PASS today** because
the census document was re-derived at F18 housekeeping. If a G7 disagreement
appears it means the document is stale, **not** that the corpus moved — the
`fz2_w1 lint` rule applies (*if a doc edit trips it, fix the doc*), and the fix
is **booked, not applied in this sitting.**

### 4.4 THE STANDING GATES ON THIS ERA (`C-13`)

`fz2_w1 bars` **11 / 11 MET**, leaf-diffed against the F18 archive with **no
verdict moved**; `fz2_w1 lint` PASS / 0 hits / 48 stratum rows;
`check_fuzz_bank` PASS at **621** seeds; `r7_lint` PASS; `ss_lint --core ucore`
PASS at **226 / 214 flops / 0 UNMAPPED**; `gen_ucore_qsf --check` PASS;
`test_artifact` **45 / 45**.

---

## 5. THE ERA-GUARD RE-SYNC AND THE CLOSING CONTROL (`Q-1`, `Q-2`)

| # | bar | registered |
|---|---|---|
| **Q-1** | **`fz2_replay` PASSES the fabric era guard with NO bypass.** It **REFUSES at HEAD today**, by name, on `hdl/nec_test.sdc` (86/88 identical). After FLASH #19 it must read **87/88 identical** with `hdl/nec_test_ucore.qsf` the single declared exemption | **PASS, `--no-fabric-era-guard` NOT used anywhere in this sitting** |
| **Q-2** | the closing control: `fz2_replay --ledger <F19> --all-failures --pass-sample 150 --leg ret --jobs 8`, era guard **ON** | agreement **≥ 255 / 260**; F18 measured **260 / 260** with `first_bad` identical on 110/110 |

**E-12 — the three ladder rows E-1's own wave could not run in an isolated
worktree** (`timing_recovery_results_2026-08-11.md` §4 booked them as *owed, not
passed*, because `sw/testdata/campaigns/*/captures/` is untracked and exists
only in this checkout) **are run HERE**: `fz2_replay` (Q-2), `fz2_immaterial
falsify` (C-12), and the fuzz-v2 capture-reading rows (C-13). **This discharges
E-1's outstanding offline debt in the same sitting that tests it in fabric.**

---

## 6. THE DIRECTED-CELL SPOT-CHECKS (`S-1` … `S-5`)

All three cells' board legs are **socket-only (`use_core=False`)**, so they
measure **SILICON**. E-1 is a constraint on the FPGA build and **cannot reach
the socket position**. Therefore:

**REGISTERED: 0 CHIP-COLUMN MOVERS ON ALL THREE CELLS.**

| # | leg | registered |
|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` (48 cells) + `score` | **0 chip-column movers**; `n_entries` 6 on every probe; `nop` **6**, `x1b` **8**, `z1b` **9** as at F18; NULL `notf`/`v_notf` **[0]** |
| **S-2** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells) + `score` | **0 chip-column movers**; the six invariant columns `wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows` **0 disagreements** |
| **S-3** | `ghost_pred_cell run --legs <a small sample>` + `score` | **0 chip-column movers** against the banked board column (captured at `flash entries 21`, i.e. FLASH #18, `git b70dbb32f0`) |
| **S-4** | `div_guard` + single-writer on every leg | **0 UNPINNED**, `single_writer OK` before each |
| **S-5** | restoration | the banked trees are **copied aside before and restored after**, verified byte-identical by sha256 manifest; the F19 rows are retained **beside** them at `sw/testdata/*/f19-spotcheck/`, never merged over them |

⚠ **A chip-column mover on any of the three is NOT an E-1 finding** — it is a
rig or silicon observation, and it would be reported as one, with its own
denominator, and **not** attributed to the SDC.

---

## 7. HARD STOPS

1. `git diff 770c0d1b85 HEAD -- hdl/rtl/ sim/` **non-empty** at any check.
2. RETENTION worst-of-2 **< 38.0 MHz**, or any G6 essential RED → **nothing is
   flashed**.
3. The RETENTION receipt self-labelling `CONTROL/DEFAULT`, or its `.rbf` equal
   to CONTROL's (E-6 / E-8) → **nothing is flashed on that build**. *This stop
   fired at FLASH #18 and was obeyed.*
4. `safe_flash` VERIFY not OK.
5. Any `div_guard` **UNPINNED** readback.
6. Any `RigMismatch` / transport quarantine.
7. A failed single-writer check that is not resolved (`--force` is **not** used).
8. `check_ab_hw` first light (B-1) failing on any of its three legs — **and the
   §3.3 re-run rule applies before any conclusion is drawn**.

---

## 8. WHAT THIS SITTING CAN AND CANNOT ESTABLISH

**CAN**: that the bitstream built under E-1's relaxed constraint observes the
bus correctly in fabric, on 800 boot rows ×3 legs, 283 sweep cells, 3,840 corpus
seeds and three directed cells — i.e. that the multicycle claim is not visibly
false on every path this rig can see.

**CANNOT**: prove the exception is *safe with margin*. A timing exception that
is marginally wrong can pass a day of captures and fail at another temperature,
another device, or after a re-fit. **What is established is a strong negative
result, not a proof**, and it will be written that way. The permanent guarantee
would be a `-setup 1` build (i.e. no exception) meeting timing, which is exactly
what the census showed it does not.

**AND ONE THING IS ALREADY TRUE AND IS NOT RE-LITIGATED HERE**: the design
CLOSES at its real 32.0 MHz constraint with positive slack in every
configuration measured this campaign. Fmax is a capability figure. E-1 buys
headroom for the ghost relocation; it does not rescue a design that was failing.

---

## Appendix A — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                    # a37f05d4b8
git diff 770c0d1b85 HEAD -- hdl/rtl/ sim/             # MUST BE EMPTY

# the offline comparand for B-2, taken BEFORE the build
python3 sw/x1_retention.py capture --leg ret

# the build -- two draws each, worst-of-2
python3 sw/quartus_gate.py             --label "fz2 FLASH#19 CONTROL draw1"
python3 sw/quartus_gate.py             --label "fz2 FLASH#19 CONTROL draw2"
python3 sw/quartus_gate.py --retention --label "fz2 FLASH#19 RETENTION ret1"
python3 sw/quartus_gate.py --retention --label "fz2 FLASH#19 RETENTION ret2"

# the flash (RETENTION build)
sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof
python3 sw/check_ab_hw.py all 800                     # B-1

# the E-1 fabric leg.  B-2b is computed directly from the two columns'
# capture files with check_core.diff_rows -- see sw/f19_b2.py, committed
# WITH this pre-registration and before the board is touched.
python3 sw/x1_fabric.py baseline --leg fab_f19 && python3 sw/x1_fabric.py score --leg fab_f19
python3 sw/x1_fabric.py socket   --leg soc_f19 && python3 sw/x1_fabric.py score-socket --leg soc_f19
python3 sw/f19_b2.py --fab fab_f19 --off ret          # B-2a and B-2b

# the corpus
python3 sw/fz2_w1.py control
python3 sw/fz2_w1.py preflight --board
python3 sw/fz2_w1.py capture
python3 sw/fz2_ledger.py --out sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json

# era guard ON, no bypass anywhere
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8
python3 sw/fz2_immaterial.py falsify
python3 sw/fz2_w1.py bars ; python3 sw/fz2_w1.py lint

# the spot-checks (banked dirs copied aside and restored)
python3 sw/tf0f_cell.py       run --strata nop,x1b,z1b ; python3 sw/tf0f_cell.py score
python3 sw/ie_pinfall_cell.py run --strata eihlt_w0,ierun_w0 --limit 20 ; python3 sw/ie_pinfall_cell.py score
python3 sw/ghost_pred_cell.py run --legs <sample> ; python3 sw/ghost_pred_cell.py score

python3 sw/check_ab_hw.py chip 800                    # B-4
```

## Appendix B — THE BAR IN ONE TABLE, FOR THE SCORER

| clause | registered value |
|---|---|
| B-1 first light | **MATCH 800 ×3** |
| B-2a `x1_fabric` vs offline `tb_sys ret`, cell level | **283 / 283 agree** — declared near-vacuous under GEN-DRIFT (§3.1) |
| **B-2b** `x1_fabric` vs offline `tb_sys ret`, **row for row** | **283 / 283 cells identical, 0 differing rows** — THE load-bearing form |
| B-3 socket control | **run and reported, NOT barred** (§3.2) |
| B-4 closing chip proof | **MATCH 800** |
| C-4 headline | **110 / 3,839, UNCHANGED** |
| C-5 membership flips | **0**, budget 10 |
| C-6 first-divergence moves | **0** |
| C-9 named non-movers | **14 / 14** |
| C-10 the six F18 seats | **3 ABSENT + 3 at `bad` 1 / `first` 243·234·583** |
| C-11 `fz2c/404040` | **ABSENT** |
| C-12 `fz2_immaterial falsify` | **PASS G1–G8, 24 members set-for-set** |
| Q-1 era guard | **PASS, no bypass, 87/88** |
| Q-2 closing control | **≥ 255 / 260** |
| S-1/2/3 chip columns | **0 movers on all three cells** |
| P-1 / P-2 G6 worst-of-2 | **44.72 / 45.71**, `.rbf` `5b869546…` / `bcb48f01…` |
