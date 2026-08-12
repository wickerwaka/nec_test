# ACK-WAKE — THE WITHDRAWN ANNOUNCEMENT'S LATE SAMPLE: PRE-REGISTRATION

    branch    fuzz-v2-on-relanding, base `292d898837`
    scope     OFFLINE ONLY.  NO BOARD, NO FLASH.  Quartus in scope iff a
              landing is taken.  `sw/testdata/flash_log.jsonl` untouched.
    date      2026-08-11
    governs   the 3 C2 HALT-wake seats `fz2c/404071` · `fz2e/514044` ·
              `fz2e/516001`, re-attributed by
              `n1_halt_wake_sample_results_2026-08-11.md` §3.2

**This document is committed BEFORE `hdl/` is touched.**  A temporary
`$display` probe was added to `v30u_biu.sv`, run, and REVERTED before this was
written; `git diff HEAD -- hdl/` is empty at the commit that carries this file.

---

## 0. THE MEASUREMENT THAT MOTIVATES IT — AND AN ERRATUM AGAINST §3.2

### 0.1 ERRATUM: THE CORE DOES NOT DROP AN INTA CYCLE

`n1_halt_wake_sample_results_2026-08-11.md` §3.2 reports

    seed          chip INTA T1 rows       core INTA T1 rows
    fz2c/404071   246, 255, 441, 452      253, 439, 450

and concludes the core "DROPS THE FIRST INTA CYCLE of the first acknowledge
pair".  **That count is an artifact of the detector.**  It counts rows with
`t == T1 && bs_early == INTA`.  Silicon announces INTA on its acknowledge T1;
the ucore can leave PASV on that row, so a cycle that is PRESENT is not
counted.  Counting an acknowledge CYCLE as *a T1 row whose T2 row carries
`bs_early == INTA`* gives, on the same replay, at `292d898837`:

    seed          chip ack cycles       core ack cycles       delta
    fz2c/404071   246, 255, 441, 452    244, 253, 439, 450    -2 on all four
    fz2e/514044   237, 248, 427, 438    235, 246, 425, 436    -2 on all four
    fz2e/516001   586, 604              584, 602              -2 on both

**The core runs EVERY acknowledge the chip runs.**  What it does is run the
first one two rows early, without its announcement row.  §3.2's "acknowledge-
PAIR defect" and its "the pair is present and 2 clocks early" are therefore
both withdrawn: there is one displacement, `-2`, and it is uniform.

### 0.2 THE DISCRIMINATING CONDITION, ON THE POPULATION

Every retained fz2 capture (654) was replayed on `tb_sys ret` and its
acknowledge anatomy taken.  **132 seeds run at least one acknowledge.**  Of
those, `core_ack[0] - chip_ack[0]` is:

    off   0 : 122 seeds        off -1 : 1     off -2 : 3
    off  +6 : 2                off -5 : 1     off +17 : 1

and **every one of the 8 non-zero seeds has its first acknowledge within 12
rows of a HALT row, while all 122 zero-offset seeds but five have it 13 rows
or further away.**  The HALT-WAKE acknowledge population is TEN seeds:

    seed          halt->ack  off   chip ann0  core ann0  fabric bad
    fz2c/404049       7       -1     yes        yes         1636
    fz2c/404071       8       -2     yes        NO           905
    fz2c/403004       9        0     no         no             0
    fz2e/514044       9       -2     yes        NO          1261
    fz2e/516001      10       -2     yes        NO          1154
    fz2c/405034      12        0     no         no             0
    fz2e/512038      12       -5     yes        NO          1722
    fz2c/403020      13        0     no         no             0
    fz2c/404036      16        0     no         no             0
    fz2c/405022      20        0     yes        yes            0

### 0.3 THE MECHANISM, MEASURED ON THE ROWS AND FROM INSIDE THE CORE

In all three seats the wake has ONE shape.  Taking `fz2c/404071`, chip rows,
**both** status samples:

    241  TW   bs_early=CODE  bs_late=CODE     <- the wake fetch's announcement
    242  TW   bs_early=CODE  bs_late=CODE
    243  T4   bs_early=CODE  bs_late=PASV     <- WITHDRAWN: early only
    244  TI   bs_early=PASV  bs_late=PASV     <- the measured PASV gap
    245  TI   bs_early=INTA  bs_late=INTA     <- the acknowledge's announcement
    246  T1   bs_early=INTA  bs_late=INTA

`fz2e/514044` is 232/233/234/235/236/237 and `fz2e/516001` is
581/582/583/584/585/586, cell for cell.  **A GENUINE announcement carries its
status on BOTH samples; the WITHDRAWN one carries it on the address-phase
sample and is gone by the end of the clock.**  The control is in the same
corpus: `fz2c/403020` row 170 is a real T4-replacement announcement and reads
`bs_early=INTA bs_late=INTA`.

A temporary `$display` on the BIU's registered state, aligned against the
replayed rows (**exactly 6 disagreements in 4,063 rows, and they are rows
244–249 and nothing else**), says the core's own sequence is

    244  idle, request store holds the INTA, `suspended`
    245  INTA display, `cdage = 0`
    246  INTA T1

— which is **silicon's, clock for clock**.  `halt_withdraw_preview` fires at
243 and the §2026 request re-insertion fires at 244, both as designed.

**THE CORE'S ARBITRATION IS NOT WRONG.  ITS STATUS PIN IS.**
`v30u_biu.sv` drives `bs = halt_withdraw_preview ? BS_CODE : …`, one value for
the whole CPU clock.  `nec_bus`'s T-state tracker — **the harness that is also
the fabric hardware** — advances out of `ST_T4` on `bs_active`, and
`bs_active` reads `bs_q`, the **END-OF-CLOCK** sample (`nec_bus.sv` 197-208,
322, 364-370), while the scored `bs_early` column is latched at `tick_fall`
(211-222).  So the ucore's whole-clock CODE at 243 promotes row 244 to a
**PHANTOM T1**, and `nec_bus` advances its wait-LFSR **once per bus cycle at
T1 entry** — so the phantom cycle **STEALS A WAIT DRAW**.  Measured
consequence on `fz2c/404071`: the core's real acknowledge at 246 runs with
ZERO waits where the chip's runs with ONE (core T4 at 249, chip TW at 249 /
T4 at 250), and every later access draws the shifted count.  That is the whole
of the 905 diverging rows.

**This is ONE BIT — the status pins at the END of the clock on which a
withdrawn announcement is released — and it is not in the acknowledge path at
all.**

---

## 1. THE CANDIDATE

ONE token, `hdl/rtl/ucore/v30u_biu.sv`, and it is a **DELETION**: the
`halt_withdraw_preview` arm comes out of the `bs` mux, leaving the withdrawn
announcement to the mux's own release logic (`display` is false because the
commit was rewound; `st_rel` is set on the HALT's T4), which yields `BS_PASV`.

No flop, no new wire, no save-state address, no opcode named, and **the RTL
shrinks**.  `halt_withdraw_preview` entered in the L1 re-landing bundle
`7647e604e0` — SIXTEEN mechanisms at once — and its own benefit was never
measured; the standing precedent is that *a bundle's benefit is not evidence
for any member of it.*

---

## 2. WHAT IS REGISTERED

### 2.1 THE SEATS DO **NOT** CLOSE, AND THAT IS THE PREDICTION

The ucore has **one status value per CPU clock and silicon has two**.  The
candidate buys the END-OF-CLOCK sample at the price of the ADDRESS-PHASE one,
so row 243 / 234 / 583 becomes a `bs CODE!=PASV` cell that is correct today.

| id | bar |
|---|---|
| **A-1** | `fz2c/404071` `bad` **905 → ≤ 5**, and **NOT 0** |
| **A-2** | `fz2e/514044` `bad` **1261 → ≤ 5**, and **NOT 0** |
| **A-3** | `fz2e/516001` `bad` **1154 → ≤ 5**, and **NOT 0** |
| **A-4** | on all three, `first_bad_row` moves **EARLIER by exactly 1**, to the withdrawn-announcement T4 (244→243, 235→234, 584→583). Registered as EXPECTED, not as a regression: it is the half-clock residue named in §0.3 |
| **A-5** | **ZERO seeds go PASS → FAIL** over the full 113-failure + sampled-PASS replay population |
| **A-6** | **ZERO seeds get a LARGER `bad`** than at `292d898837`, and **zero get an EARLIER `first_bad_row`** other than the three named in A-4 |

### 2.2 THE NAMED NON-MOVERS

| id | bar |
|---|---|
| **B-1** | `fz2c/404040` stays **PASS**, `bad` 0 |
| **B-2** | the §64.1 four — `fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` — keep their N1-3 values `bad` 840 / 921 / 891 / 984 and their `first_bad_row` **unchanged** |
| **B-3** | the other five HALT-wake seeds — `fz2c/403004` · `fz2c/405034` · `fz2c/403020` · `fz2c/404036` · `fz2c/405022` — stay **PASS at `bad` 0** (they are the population that proves the predicate is not a HALT-wake blanket) |
| **B-4** | `fz2e/531000` stays **PASS** |
| **B-5** | the three unpredicted C2 seeds `fz2e/513019` · `fz2e/516065` · `fz2c/410047` do not get worse |
| **B-6** | `fz2_immaterial.py falsify` **PASS**, residue **92 = 113 − 21** |

⚠ **`fz2c/404049` (off −1) and `fz2e/512038` (off −5) are NOT registered
either way.**  They are in the wake population and may move in either
direction; they are reported as measured.  Registering them would be fitting —
their shapes were not derived.

### 2.3 THE LADDER

| id | bar |
|---|---|
| **C-1** | `gen_ucore_qsf.py --check` PASS |
| **C-2** | `r7_lint.py` PASS, **no new declared exception** |
| **C-3** | `ss_lint.py` **UNCHANGED**: `SS_VERSION` **0x8D** / `SS_COUNT` **226** / **214** flops / 0 UNMAPPED. The candidate adds no flop; if this moves, the landing is wrong by construction |
| **C-4** | `test_artifact.py` **45/45** |
| **C-5** | `check_core.py --core ucore --opcodes all --cases 0` **169,000/169,000** |
| **C-6** | the four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (⚠ `--waits 0/1/2/3`), and the four survivors the four family-D cells |
| **C-7** | `ulockstep.py --golden all --cases 50` **17,350/17,350** |
| **C-8** | the ie-pinfall replay: 876 free-running cells stay 0-diff and the HALT-leg map stays **57 → 27 or better** |
| **C-9** | **G6, `quartus_gate.py`, TWO DRAWS, BOTH QUOTED.  38.0 MHz is a HARD STOP** — below it the landing does not happen however green everything above is.  Band on this branch 38.4–42. |

### 2.4 DISPOSITION, UNCONDITIONAL

* **If A-5 or A-6 misses, the edit is REVERTED** and the mechanism is booked.
* **If G6 draws below 38.0 on either draw, the edit is REVERTED**, whatever
  the corpus says.  §6.1 of the N-1 results is the precedent and it is one
  sitting old.
* **If A-1/A-2/A-3 miss high** (`bad` stays large), the §0.3 account is
  REFUTED as the whole cause and is to be reported as such, not restated.
* A landing that leaves all three seats FAILING is still a landing **only if**
  A-5 and A-6 hold: it trades ~3,300 diverging rows for three cells, on a
  mechanism, with the RTL shrinking.  If the user prefers the three cells, the
  amputation is trivially reversible and this document is the derivation.

### 2.5 THE FALSIFIER FOR THE ACCOUNT ITSELF

A capture in which a WITHDRAWN announcement carries its status on the
END-OF-CLOCK sample (`bs_late != PASV` on the withdrawal clock), or in which a
GENUINE announcement is `bs_late == PASV` on the clock before its T1.  Neither
exists in the 654 retained captures.
