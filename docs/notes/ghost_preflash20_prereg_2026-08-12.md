# PRE-REGISTRATION — THE PRE-FLASH-#20 OFFLINE WAVE

Branch `fuzz-v2-on-relanding`, base **`5cdca40b60`** (`git rev-parse HEAD`
verified; isolated worktree, provisioned at `master` and **RESET** to the base
before anything was read or run).

**OFFLINE ONLY. NO BOARD, NO FLASH.** Quartus IS in scope (G6, two draws per
configuration, worst-of-2). No Codex, no nested tasks.

The three items `5cdca40b60`'s own message names as FLASH #20 blockers, plus
the retention timing yellow flag the relocation landing reported and did not
explain.

**SIMPLICITY (user directive 2026-08-01), verbatim.** *"SIMPLICITY: this is
80's era hardware — nothing on the die is wasted. Complex or confusing observed
behavior is likely simple systems interacting in ways not yet understood. A
large fitted table, a many-cased rule, or a per-opcode special case is a signal
of misunderstanding, not a deliverable."*

---

## §0 THE MEASURED BASELINE THIS FILE IS REGISTERED AGAINST

Taken at `5cdca40b60` with a clean tree, **before any edit**, and reproduced
here so every later number is a delta against a measurement rather than a
recollection.

| instrument | measured at the base |
|---|---|
| `fz2_replay --all-failures --pass-sample 150 --leg ret` (ledger `f19`) | **264 seeds**, 0 errors, verdict agreement **261 / 264 = 98.9 %**, total `bad_rows` **118,854** over the 114 fabric-FAIL seeds |
| `fz2e/528010` | `bad` **2,067** · `flick` **2** · `first` **1,383** |
| `fz2c/406063` | `bad` **3,165** · `flick` **0** · `first` **249** |
| `ghost_pred_cell score` | identical **384** / different **136** |
| `ghost_launch_law score` | **200 / 200**, exit 0 |

⚠ `--no-fabric-era-guard` is in force on every `fz2_replay` figure in this
document, for `5cdca40b60` §1's reason (the four relocation RTL files postdate
FLASH #19's bitstream). Every replay number here is an **offline core-side**
number scored against FLASH #19's banked **socket** rows, which are silicon and
are not in question.

---

## §1 ITEM 1 AND ITEM 2 — THE TWO REGRESSED SEEDS, DIAGNOSED BEFORE ANY FIX

Both were diagnosed by **bisecting the relocation into its two halves** and
building each half alone. The bisect variant is HEAD with wave-4's V2 arm
RESTORED into `ghost_bus_off` and the BIU launch relocation LEFT IN PLACE. It
is a diagnostic only and is not a candidate landing.

| seed | bisect variant vs PRE-relocation | bisect variant vs HEAD |
|---|---|---|
| `fz2e/528010` | **byte-identical, all 4,063 rows** | first differs at row 1,383 |
| `fz2c/406063` | first differs at row 245 | **byte-identical, all 4,063 rows** |

So the two seeds are owned by **different halves** of the relocation, and each
half is INERT on the other's seed:

* **`fz2e/528010` is owned entirely by the EU-side DELETION of wave-4's V2
  arm.** The BIU launch relocation does not touch it.
* **`fz2c/406063` is owned entirely by the BIU launch relocation.** The V2
  deletion does not touch it.

### 1.1 `fz2e/528010` — THE SPLIT, NOT THE ADDRESS

The seed has **exactly ONE** ghost event in its whole 4,063-row window. A
temporary EU probe (added, read, and removed; it is not in any landed tree)
reports it at CE clock 1,376:

```
V2 present  bus_off=9537 off=ff8c sp=9537 and=9504 uses_ea=1 v2fire=1
            addr=863a7 addr2=863a8 split=1 pair2=1   <- TWO bus cycles
HEAD        bus_off=9504 off=ff8c sp=9537 and=9504 uses_ea=1 v2fire=1
            addr=86374 addr2=86375 split=0 pair2=0   <- ONE bus cycle
```

`acc_split`'s ghost branch is
`(ghost_uses_ea || ghost_uses_mul_hi) ? acc_phys_base[0] : ghost_stack_phys[0]`,
and `acc_phys_base[0] == ghost_bus_off[0]`. With `ghost_uses_ea` set, **the
split is the POSTED value's low bit**. V2 posted `SP` = `0x9537`, ODD, so the
access SPLIT. HEAD posts the AND = `0x9504`, EVEN, so it does not.

The replayed row stream is the direct consequence and it is measured, not
inferred: from row 1,383 onward **`post[i] == pre[i+6]` on 2,241 of 2,674 rows
(83.8 %)** against a ~16 % baseline at every other shift in [0, 12]. **One
entire six-clock bus cycle — the split partner — is missing**, and everything
after it moves six rows earlier. That is the whole of `bad_rows` 4 → 2,067.

**THE VERDICT: THE RELOCATION EXPOSED A PRE-EXISTING WRONG, AND ITS OWN §2.1
CLAIM IS FALSE AS WRITTEN.** `ghost_launch_landing_prereg` §2.1 says the
surviving V1 arm *"stays the POSTED value so that every post-time derived
quantity … is computed from the SAME expression it is computed from today"*.
Deleting an arm **is** a change to the expression wherever that arm fired.
`fz2e/528010` is the counterexample, and the quantity that moved is not a
decoration but the **NUMBER OF BUS CYCLES**.

This is prereg **§7(c)**'s registered falsifier firing — *"`UBE` AND `A0` … are
computed at the post from the AND value and are NOT recomputed from the
relocated address"* — one class wider than §7(c) anticipated: the split goes
with them.

V2 was **accidentally right about the SHAPE and wrong about the ADDRESS**: the
chip's own T1 here is `0x8B92D`, which is likewise ODD, so silicon splits too;
V2's `0x863A7` is odd for a reason that has nothing to do with the chip's value.
Restoring V2 is therefore NOT a fix — it is re-installing a fitted arm to
recover a coincidence.

### 1.2 `fz2c/406063` — THE RELOCATION IS RIGHT, THE RESIDUE MOVED TO THE PARTNER

Its single ghost event has `uses_ea=0`, `v2fire=0`, `split=1` from
`ghost_stack_phys[0]`, posted `addr=13eb1` / `addr2=13eb2`.

Row for row, **the relocation CLOSES rows 245-248 exactly onto the chip**
(core `0x13EB1` → `0x1EF01` = the chip's own value, and row 247's
`0x57E6F` likewise). `first_bad` moves 245 → **249**, four rows LATER.

Row 249 is the **split partner**, and it is un-relocated by construction:
`rq_ghost[1] = 1'b0` for the BIU-manufactured second cycle. The core drives
posted+1 = `0x13EB2`; the chip drives `0x1EF4E`, which is not the relocated
first half + 1 either. That is prereg **§7(b) THE SPLIT GHOST**, registered as
residue with *"no measurement exists"* — **this is its first measurement.**

`bad_rows` 3,149 → 3,165 is **+16 on a seed where 3,149 of 4,000 rows already
diverge**; the divergence starts four rows later and re-phases a saturated
cascade. `diverging_rows` is not a quality measure on such a seed —
`5cdca40b60`'s own refutation of the band rule says the same thing from the
other side.

### 1.3 THE HOLDOUT-PREDICTION MISS, RECORDED

`fz2c/406063` was a **wave-8 HOLDOUT seat** predicted *cascade-bound
NON-closure* AND a **W7-4 §64.1 named non-mover**. It did not close (the
holdout prediction H-2 stands) but it MOVED, which the non-mover clause does not
permit. Recorded as a **non-mover miss**, attributed to the BIU launch
relocation, mechanism §1.2.

---

## §2 EDIT F-B — THE SPLIT IS TAKEN FROM THE `dGR == 0` DRIVER

**Registered BEFORE the edit and before any measurement of it.**

### 2.1 The change — a DELETED CASE, not an added one

```systemverilog
wire       acc_split = !acc_byte &&
                       (ghost_read_stale_alu ? ghost_stack_phys[0]
                                             : acc_phys[0]);
```

The `(ghost_uses_ea || ghost_uses_mul_hi) ? acc_phys_base[0] :` case is
**DELETED**. One expression replaces two; no opcode is named; no flop is added
or removed; `acc_split` stays combinational.

### 2.2 Why it is derivable from the law and is not a new mechanism

`dGR` is *"clocks from the FIRST clock the ghost read's own micro-row is current
to the clock the BIU LAUNCHES the cycle"*. **At the POST clock the row is
current and the launch has not happened, so `dGR == 0` there by definition**,
and the law's `dGR == 0` row is `SS:SP` — the posting micro-row's own stack
drive. The pair reservation is taken at the post, so it must be taken from the
`dGR == 0` driver.

`ghost_stack_phys = {acc_segv, 4'd0} + {4'd0, ind_now}` **is** that driver: on
both diagnosed seeds `ind_now` is measured equal to `gpr[R_SP]`
(`stackphys - segv*16 == sp` on both). The other branch of the existing rule
already used it; this edit stops the `ghost_uses_ea` cells from using the
posted AND instead.

The address is untouched. Only the SHAPE decision moves, and it moves to the
driver the law already names.

### 2.3 REGISTERED BARS FOR F-B

| # | bar | falsifier |
|---|---|---|
| **B-1** | **THE PRIMARY.** `fz2e/528010` reads `bad` **4** · `flick` **0** · `first` **1,383** — the pre-relocation and FLASH-#19-ledger value exactly. | any other triple |
| **B-2** | `fz2c/406063` is **UNMOVED** at `bad` **3,165** · `first` **249** (its ghost has `uses_ea == 0`, so the deleted case never applied to it). | any move |
| **B-3** | Over the 264-seed replay: **0 LOST** (no seed at `bad == 0` goes non-zero) and **0 first_bad EARLIER**. | either |
| **B-4** | `check_core --core ucore --opcodes 8F.0 --cases 0` **500/500** and `--opcodes all --cases 0` **169,000/169,000**. **HARD STOP.** | any case |
| **B-5** | `ulockstep --golden all --cases 50` **17,350/17,350**. **HARD STOP.** | any form |
| **B-6** | The four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (`--waits 1/2/3`). | any cell |
| **B-7** | `ghost_pred_cell score` identical **384**, unmoved. The cell measures the ghost T1 ADDRESS; this edit changes only whether a SECOND cycle exists. | any move, itemised cell for cell |
| **B-8** | `ghost_launch_law score` **200/200**, exit 0. | anything else |
| **B-9** | `ss_lint --core ucore` PASS at **0x8E / 232 / census 220 / 0 UNMAPPED**, UNMOVED (no flop added or removed); `r7_lint` PASS with no new carrier and no new tainted signal; `test_artifact` **45/45**; `gen_ucore_qsf --check` up to date. | any |

**B-4 and B-5 are HARD STOPs.** Anything else is reported as registered.

---

## §3 EDIT F-A — THE `imul` FALSIFIER (`ghost_uses_mul_hi` DELETED)

**Pre-registered by the relocation landing itself** (`093efbcfc2`'s message and
`ghost_launch_law_results` §5.3), which measured the finding and deliberately
did not act on it: *"Deleting it after seeing that would be a second mechanism
chosen post-hoc; it stays, with the measurement."* This is that second
mechanism, taken as its own edit.

### 3.1 The change

`wire ghost_uses_mul_hi` is **DELETED**, with all three of its uses:

* `ghost_bus_off` loses the `? (tmpa & opr)` arm and becomes
  `ghost_off & gpr[R_SP]` unconditionally;
* `acc_split` loses it from its case guard (with F-B, the whole guard is gone);
* `eu_ghost_row` becomes `ghost_read_stale_alu` — so the class is no longer
  excluded from the launch relocation.

### 3.2 REGISTERED BARS FOR F-A — the landing's own numbers, not restated

| # | bar | falsifier |
|---|---|---|
| **A-1** | **THE PRIMARY.** The law's own population: `imul` **2/16 → 16/16**. | any other count |
| **A-2** | `mul` **UNMOVED at 16/16**, and every other one of the thirteen legs unmoved (`alu88` `alu44` `alu08` `v_or` `v_sub` 16/16, `v_inc` 8/16, `mov8e` 4/16, `mempop` 2/16, `v_lea` 2/16, `memw` 0/16, `pfxpro` 0/16). | any leg off its number |
| **A-3** | `ghost_pred_cell score` identical **384 → 398** (+14, −0). | any other count; any cell breaking |
| **A-4** | **0 banked seeds moved** over the 264-seed replay — the arm was measured INERT on 654 seeds at wave-4 and on this population it must stay so. | any seed moving, itemised |
| **A-5** | `check_core 8F.0` **500/500**, `all` **169,000/169,000**, `ulockstep` **17,350/17,350**, sweeps **279/283**. **HARD STOP** on the first two. | any |
| **A-6** | `ss_lint` UNMOVED at 0x8E / 232 / 220; `r7_lint` PASS; `test_artifact` 45/45. | any |

**IF A-1 OR A-3 MISSES, THE EDIT IS REVERTED AND BOOKED** — the arm is
load-bearing in a way the cell could not see, exactly as
`ghost_launch_law_results` §5.3 warned.

### 3.3 The order of measurement, fixed now

**F-A ALONE**, then **F-B ALONE**, then **F-A + F-B TOGETHER** if and only if
both pass their own bars. Each is measured on its own `ghost_pred_cell core`
recapture. A bundle's benefit is not evidence for any member of it
(the 8F ghost READ precedent).

---

## §4 ITEM 4 — THE RETENTION TIMING YELLOW FLAG (DIAGNOSTIC ONLY)

The relocation measured G6 worst-of-2 CONTROL **44.67** / RETENTION **41.60**
against the E-1 band CONTROL **44.72** / RETENTION **45.71** — control flat at
−0.05, retention **−4.11**, reported as a registered yellow flag and not
explained.

**REGISTERED SCOPE: DIAGNOSIS ONLY.** `sw/sta_census.tcl` / `sw/sta_probe.tcl`
are run on the retention build and the dominant cone is NAMED with its launch
and capture registers and its logic depth. **NO FIX IS TAKEN THIS WAVE** unless
it is a one-line SDC analogue of E-1 with E-1's own derivation, pre-registered
before the build that scores it, and proved worst-of-2. Otherwise it is BOOKED
for a timing pass.

---

## §5 G6, REGISTERED

**Two draws per configuration, worst-of-2 quoted**, on whatever tree this wave
lands (HEAD if nothing lands).

* **STOP: worst-of-2 < 38.0 MHz on either configuration** — the landing is
  reverted and booked with the cone named.
* Worst setup > 0; setup AND hold TNS 0.000 on every domain; 0 errors, 0
  latches, 0 `lpm_divide`.
* The retention `.rbf` DIFFERENT from the control's, with the receipt
  self-labelling RETENTION.
* Reference band: CONTROL **44.72** / RETENTION **45.71** (E-1). A worst-of-2
  below ~43 MHz on either configuration is a **YELLOW FLAG** — reported,
  itemised, not a stop.

⚠ `standing_gates.md` §A governs: **one green build is not closure**, and the
same tree has drawn 19.42 and 45.91 MHz.

---

## §6 STOP CONDITIONS

1. **`check_core` and `ulockstep` are HARD STOPS** on either edit.
2. **G6 below 38.0 MHz worst-of-2 is a HARD STOP.**
3. **A fix that needs a new special case, a wider counter or a second predicate
   is BOOKED, NOT TAKEN**, and the residue is named. F-B is admissible only
   because it DELETES a case.
4. Everything else is reported AS REGISTERED — registered number, measured
   number, difference — never restated.

---

## §7 RE-RUNNING THIS

```bash
git rev-parse HEAD                                  # 5cdca40b60 at registration
python3 sw/x1_retention.py build --leg base
python3 sw/x1_retention.py build --leg ret
python3 sw/check_core.py --build --core ucore
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8 --no-fabric-era-guard
python3 sw/ghost_pred_cell.py core                  # the recapture
python3 sw/ghost_pred_cell.py score
python3 sw/ghost_launch_law.py score
python3 sw/quartus_gate.py                          # G6 control  x2
python3 sw/quartus_gate.py --retention              # G6 retention x2
```
