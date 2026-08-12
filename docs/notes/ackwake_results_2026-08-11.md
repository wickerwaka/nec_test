# ACK-WAKE — RESULTS

    pre-registration  docs/notes/ackwake_prereg_2026-08-11.md, committed at
                      `f843319607` BEFORE the RTL was touched
                      (`git diff HEAD -- hdl/` empty at that commit)
    branch            fuzz-v2-on-relanding, base `292d898837`
    scope             OFFLINE ONLY.  NO BOARD, NO FLASH.
                      `sw/testdata/flash_log.jsonl` UNTOUCHED.
    date              2026-08-11

---

## 0. VERDICT

**LANDED.  Every registered bar is MET, including the ones registered as
NEGATIVE results, and the one clause that moved is reported as a MISS.**

The three C2 HALT-wake seats are **NOT** a dropped INTA and **NOT** an
acknowledge-pair defect.  The ucore's arbitration through the wake and through
BOTH acknowledges is silicon's **clock for clock**.  The whole divergence —
3,317 rows across three seeds — is **ONE BIT: the ucore held a WITHDRAWN
announcement's bus status to the END of the clock on which silicon has already
released it**, which manufactures a PHANTOM T1 in `nec_bus`'s T-state tracker
and **steals a wait-LFSR draw**, shifting every later access in the run.

| id | registered | measured |
|---|---|---|
| **A-1** | `fz2c/404071` `bad` 905 → ≤ 5, NOT 0 | **MET — 1**, `first_bad` 244 → 243 |
| **A-2** | `fz2e/514044` `bad` 1261 → ≤ 5, NOT 0 | **MET — 1**, 235 → 234 |
| **A-3** | `fz2e/516001` `bad` 1154 → ≤ 5, NOT 0 | **MET — 1**, 584 → 583 |
| **A-4** | `first_bad_row` earlier by exactly 1 on those three | **MET — exactly 1 on all three, and on no other seed** |
| **A-5** | ZERO PASS → FAIL | **MET — 0** |
| **A-6** | ZERO larger `bad`, ZERO earlier `first_bad` other than A-4's three | **MET — 0 and 0** |
| **B-1** | `fz2c/404040` stays PASS | **MET — `bad` 0** |
| **B-2** | the §64.1 four unmoved | **MET — 840 / 921 / 891 / 984, `first_bad` 527 / 1331 / 636 / 1475, unchanged** |
| **B-3** | the five matching HALT-wake seeds stay PASS | **MET — `bad` 0 on all five** |
| **B-4** | `fz2e/531000` stays PASS | **MET — `bad` 0** |
| **B-5** | the three unpredicted C2 seeds not worse | **MET — bit-identical** |
| **B-6** | `fz2_immaterial falsify` PASS, residue 92 = 113 − 21 | **MET** |
| **C-1** | `gen_ucore_qsf --check` | **PASS** |
| **C-2** | `r7_lint` PASS, no new exception | **PASS — 0 violations**, 20 nets / 1 carrier / 3 tainted / 51 `stop` sites |
| **C-3** | `ss_lint` UNCHANGED 0x8D / 226 / 214 | **MET — 226 addresses, 214 flops, 0 UNMAPPED** |
| **C-4** | `test_artifact` 45/45 | **MET** |
| **C-5** | `check_core --opcodes all` 169,000 | **MET — 169,000/169,000** |
| **C-6** | four HLT sweeps 279/283, survivors the four family-D cells | **COUNT MET — 97 · 93 · 45 · 44 = 279/283.  ⚠ COORDINATE CLAUSE MISSED — see §4** |
| **C-7** | `ulockstep --golden all --cases 50` | **MET — 17,350/17,350 LOCKSTEP** |
| **C-8** | ie-pinfall: free-running 0-diff, HALT map stays or improves | **MET AND IMPROVED — §3** |
| **C-9** | G6 two draws, 38.0 hard STOP | **PASS — §5** |

**The whole-program effect is EXACTLY THREE SEEDS AND NOTHING ELSE.**  Over the
233-seed replay population the total diverging-row count falls
**113,340 → 110,023 = −3,317**, which is `904 + 1260 + 1153` **to the row**.
Not one other seed moved by a single row, and `first_bad_row` is identical on
all 107 other still-failing seeds.

---

## 1. THE ERRATUM — §3.2's "DROPPED FIRST INTA" IS WITHDRAWN

`n1_halt_wake_sample_results_2026-08-11.md` §3.2 counted acknowledge cycles as
rows with `t == T1 && bs_early == INTA`.  Silicon announces INTA on its
acknowledge T1; the ucore can leave PASV there.  **A cycle that is PRESENT was
not counted.**  Counting a cycle as *a T1 row whose T2 row carries INTA*, at
`292d898837` before any edit:

    seed          chip ack cycles       core ack cycles       delta
    fz2c/404071   246, 255, 441, 452    244, 253, 439, 450    -2 on all four
    fz2e/514044   237, 248, 427, 438    235, 246, 425, 436    -2 on all four
    fz2e/516001   586, 604              584, 602              -2 on both

The core runs **every** acknowledge the chip runs.  §3.2's "acknowledge-PAIR
defect", its "the survivor ~7 clocks late" and its "that pair is present and 2
clocks early" are all withdrawn: there was ONE displacement, `-2`, uniform.

**After the landing all three are cell-for-cell identical to the chip**, T1s
and announcement rows alike.

---

## 2. THE DISCRIMINATING CONDITION AND THE MECHANISM

### 2.1 THE POPULATION

All 654 retained fz2 captures were replayed on `tb_sys ret` and their
acknowledge anatomy taken.  132 run at least one acknowledge; the first-cycle
offset core-minus-chip is `0` on **122** of them and non-zero on **8** — and
**every one of the 8 has its first acknowledge within 12 rows of a HALT row.**
The HALT-wake acknowledge population is TEN seeds, five matching and five not,
and the five matching ones are the control that keeps the predicate from being
a HALT-wake blanket.

### 2.2 THE MECHANISM, ON BOTH STATUS SAMPLES

`nec_bus` samples the status pins TWICE per CPU clock: `bs_early` at the
falling edge (the address phase, and the SCORED column), and `bs_q`
continuously — the END-OF-CLOCK sample.  In all three seats silicon reads

    241  TW   bs_early=CODE  bs_late=CODE     the wake fetch's announcement
    242  TW   bs_early=CODE  bs_late=CODE
    243  T4   bs_early=CODE  bs_late=PASV     WITHDRAWN: address phase only
    244  TI   bs_early=PASV  bs_late=PASV     the measured PASV gap
    245  TI   bs_early=INTA  bs_late=INTA     the acknowledge's announcement
    246  T1   bs_early=INTA  bs_late=INTA

(`fz2e/514044` at 232-237, `fz2e/516001` at 581-586, cell for cell.)  **A
GENUINE announcement carries its status on BOTH samples; a WITHDRAWN one
carries it on the address-phase sample and is gone by the end of the clock.**
The control is in the same corpus: `fz2c/403020` row 170 is a genuine
T4-replacement announcement and reads `bs_early=INTA bs_late=INTA`.

### 2.3 WHY IT COST 3,317 ROWS

`nec_bus` — the harness, and the **fabric hardware** — advances its T-state
tracker out of `ST_T4` on `bs_active`, and `bs_active` reads the END-OF-CLOCK
sample (`nec_bus.sv` 322, 364-370).  It also advances the wait-LFSR **once per
bus cycle at T1 entry**.  The ucore's whole-clock CODE at 243 therefore
manufactured a **PHANTOM T1** at 244 and **STOLE A WAIT DRAW**: the core's real
acknowledge at 246 ran with ZERO waits where the chip's ran with ONE, and every
later access in the run drew the shifted count.

**The core's own arbitration was never wrong.**  A temporary `$display` on the
BIU's registered state — added, run, and **REVERTED** — aligned against the
replayed rows with **exactly 6 disagreements in 4,063 rows, and they were rows
244-249 and nothing else**, i.e. exactly the six the phantom cycle mislabels.
Inside the core: idle at 244 with the INTA in the request store, display at
245, T1 at 246 — **silicon's, clock for clock**.  `halt_withdraw_preview` fired
at 243 and the request re-insertion at 244, both as designed.

### 2.4 THE CANDIDATE

ONE token, `hdl/rtl/ucore/v30u_biu.sv`, and it is a **DELETION**: the
`halt_withdraw_preview` arm comes out of the `bs` mux and the mux's own release
logic answers `BS_PASV`.  No flop, no new wire, no save-state address, no
opcode named; the wire itself is retired and **the RTL shrinks**.
`halt_withdraw_preview` arrived in the L1 re-landing bundle `7647e604e0` —
SIXTEEN mechanisms at once — and its own benefit was never measured; *a
bundle's benefit is not evidence for any member of it.*

### 2.5 WHAT IS **NOT** FIXED, AND IT IS THE WHOLE OF THE RESIDUE

**The ucore has ONE status value per CPU clock where silicon has TWO.**  The
landing buys the end-of-clock sample at the price of the address-phase one, so
the withdrawal clock becomes a single `bs CODE!=PASV` cell — row 243 / 234 /
583.  That is why A-1..A-3 registered **`bad` = 1 and NOT 0**: the seats do not
CLOSE, they collapse from 905 / 1261 / 1154 to 1 / 1 / 1.

Rendering the half-clock would need the status pin modelled on the observation
path in `system_large`, as `X1_AD_RETENTION` does for AD (C11's precedent).
That is an INTEGRATION change, a different mechanism, and it is **BOOKED, not
taken** — to be measured as its own mechanism with its own G6.

---

## 3. THE ie-PINFALL DIRECTED CELL — A SECOND, INDEPENDENT POPULATION

Re-measured on the candidate (`ie_pinfall_cell core` + `score`, 2,200 cells).
`sw/testdata/ie-pinfall/` was restored to HEAD afterwards, so the banked
column is unmoved.

    column           HEAD    candidate
    taken              30      30
    n_inta             36  ->  30      <== SIX CELLS CLOSED
    ack_off            46  ->  40      <== SIX CELLS CLOSED
    ack_off_hlt        46  ->  40      <== SIX CELLS CLOSED
    n_halt             11      11
    halt_first          6       6
    halt_off            6       6
    wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows
                      0 / 1,920 throughout, BOTH LEGS

**The 876 free-running cells stay 0-diff** and every one of the six invariant
columns stays `0 / 1,920`.  `n_inta` closing six cells is the mechanism seen
from the other side: the phantom T1 was being COUNTED as an extra acknowledge
cycle by the cell's own instrument.  The distinct differing-cell count is
**30 → 30** — the same 30 cells, six of them now differing in fewer columns —
and that is stated rather than rounded into an improvement.

---

## 4. C-6 — THE COUNT IS MET AND THE COORDINATE CLAUSE IS **MISSED**

    s10-hltsweep-w0 --waits 0   97 / 97   (HLT.INT 48/48, HLT.RES 49/49)
    s10-hltsweep-w1 --waits 1   93 / 95   (HLT.INT 44/46, HLT.RES 49/49)
    s13-hltsweep-w2 --waits 2   45 / 46   (HLT.INT 20/21, HLT.RES 25/25)
    s13-hltsweep-w3 --waits 3   44 / 45   (HLT.INT 19/20, HLT.RES 25/25)
                                279 / 283   -- the registered value, unmoved

**`HLT.RES` is 49 · 49 · 25 · 25, PERFECT at every wait**, unchanged.

⚠ **The four survivors are the same four cases and their first-divergence
coordinates MOVED**, and the pre-registration named the coordinates:

    registered (CLAUDE.md, N-1)          measured on the candidate
    w1 (10,'busstat') + (11,'pins')      w1 (10,'busstat') x2
    w2 (13,'pins')                       w2 (12,'busstat')
    w3 (15,'pins')                       w3 (14,'busstat')

and every one reads **`busstat: exp 'CODE' got 'PASV'`**.  **This is A-4's
residue, and the directed sweeps confirm the mechanism a third time**: silicon
has the withdrawn announcement's address-phase CODE at that row and the ucore
can no longer render it, while the `pins` divergence one row LATER — the
phantom cycle's own signature — is GONE.  Three cells moved one row earlier and
one column over; none was added.

Family D is by USER DISPOSITION of 2026-08-05 scored via `tb_sys`, not on
`tb_v30_core`, so this TB is not the authority on these four cells.  The clause
is nonetheless reported as **MISSED**, not restated.

---

## 5. G6 — TWO DRAWS, BOTH GREEN, AND THE 38.0 STOP DID NOT FIRE

| | draw 1 | draw 2 |
|---|---|---|
| receipt | `2b9096b46411753a…` | `d57a96b9028637fb…` |
| verdict | **PASS** | **PASS** |
| Fmax (CPU domain) | **40.13 MHz** | **40.13 MHz** |
| worst setup | **+6.333 ns** | **+6.333 ns** |
| setup / hold TNS | **0.000 on every domain** | **0.000 on every domain** |
| ALMs | 12,246 / 41,910 (29 %) | 12,246 / 41,910 (29 %) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| E1 `gen_ucore_qsf --check` | PASS | PASS |
| 88-file input manifest | `7db533790f51ff18…` | `7db533790f51ff18…` (identical) |
| configuration | CONTROL/DEFAULT (derived) | CONTROL/DEFAULT (derived) |
| compile | rc=0, 685 s | rc=0, 617 s |

**TWO DRAWS AND THE TIMING FIGURES ARE BIT-IDENTICAL**, off the same 88-file
manifest, so 40.13 is not a lucky draw — it reproduces.  (The 9-file REPORT
hashes differ, `dbf881c904788b0f…` vs `b474a2f66fb62d91…`; the reports carry
timestamps.  Every gated number is identical.)

Both draws sit at the top of this branch's control band (39.16 · 39.37 · 39.47
· 39.63 · 39.81 · 40.11) and **above the registered 38.0 MHz hard STOP**, so
the STOP did not fire.  **ONE GREEN BUILD IS NOT CLOSURE** — `standing_gates.md`
§A governs and the same tree has drawn 19.42 and 45.91 MHz; two draws of a
distribution nobody has characterised is two draws.

---

## 6. INSTRUMENT NOTES, STATED BESIDE THE NUMBERS

* ⚠ **BOTH the baseline and the candidate replays were taken with
  `--no-fabric-era-guard`, and the guard fires at `292d898837` ITSELF** — the
  KM landing (`e57c3b4d12`) moved `v30u_eu_step.svh`, which is a declared input
  of the FLASH #17 bitstream receipt.  **The guard's refusal is therefore
  ENGINE-INDEPENDENT and predates this candidate.**  No figure in this document
  is a fabric figure and none is claimed as one: what is compared is the core
  against banked SOCKET rows, which is untouched silicon.
* The baseline was re-measured at `292d898837` on a freshly built `tb_sys ret`
  (receipt `7a6ccf9f035cc485…`); the candidate's is `c89f27fa92949fda…`.  The
  N-1 banked baselines were NOT reused — KM landed between them.
* The `$display` probe was reverted before the pre-registration was written and
  `git diff HEAD -- hdl/` was empty at `f843319607`.
* `sw/testdata/ie-pinfall/` and `sw/testdata/fz2/` are restored to HEAD; the
  landing's tree diff is the RTL and these two documents.
* No board was touched; `sw/testdata/flash_log.jsonl` has the same entry count
  before and after.

---

## 7. WHAT THIS RE-OPENS AND WHAT IT CLOSES

* **The three C2 HALT-wake seats are EXPLAINED and 99.9 % closed by rows, and
  they remain in the failure ledger at one cell each.**  Their re-open
  condition is §2.5's integration-side status model, not the acknowledge path.
* **`n1_halt_wake_sample_results_2026-08-11.md` §3.2 is amended** by §1 (the
  detector) and §2 (the mechanism).  Its "aim the next attempt at the INTA
  pair's own arbitration/spacing" is WITHDRAWN — the arbitration was already
  exact.
* Its registered falsifier — *"a capture in which the core's missing first INTA
  is present with the pair still mis-spaced"* — is **FIRED**: the first INTA
  was never missing.
* **A NEW STANDING FALSIFIER** for the account: a capture in which a WITHDRAWN
  announcement carries its status on the END-OF-CLOCK sample, or a GENUINE one
  is PASV there on the clock before its T1.  Neither exists in the 654 retained
  fz2 captures.
