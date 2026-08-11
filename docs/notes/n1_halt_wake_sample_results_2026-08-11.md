# N-1 — THE HALT-WAKE RECOGNITION SAMPLE: RESULTS

    pre-registration  docs/notes/n1_halt_wake_sample_prereg_2026-08-11.md,
                      committed at `4aa3a9cc2e` BEFORE the RTL was touched
                      (`git diff --stat 310457b2f7 4aa3a9cc2e -- hdl/rtl/` empty)
    branch            fuzz-v2-on-relanding, base `310457b2f7`
                      (+ `2aff7bc844`, the E1 qsf housekeeping — no RTL)
    scope             OFFLINE ONLY.  NO BOARD, NO FLASH.  Quartus in scope.
                      `sw/testdata/flash_log.jsonl` untouched; FLASH #17 resident.
    date              2026-08-11

---

## 0. VERDICT

**N-1 IS REFUTED AS REGISTERED, AND THE EDIT IS REVERTED.**  `hdl/` ends this
sitting byte-identical to `310457b2f7`.

**It is refuted THREE times over, independently**, and any one of the three
would have stopped it on its own: the seats it was for did not close, the seed
it was registered not to break broke, and **G6 drew 20.80 MHz on two draws**.

Three registered clauses missed, and one of them is a hard bar:

| id | registered | measured |
|---|---|---|
| **N1-1** | the three C2 HALT-wake seats CLOSE, 3 of 3 | **MISSED — 0 of 3.** `fz2c/404071` · `fz2e/514044` · `fz2e/516001` are bit-identical before and after: `bad` 905 / 1261 / 1154, `first_bad_row` 244 / 235 / 584. Not one row moved. |
| **N1-3** | the §64.1 four MUST NOT MOVE | **MISSED — all four moved.** And they moved to **PASS**: `fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` all go `bad` 840 / 921 / 891 / 984 → **0**. |
| **N1-2 / N1-5** | `fz2c/404040` stays PASS; **0 seeds go PASS → FAIL** | **REFUTED.** `fz2c/404040` — wave-5's own falsifier — goes **PASS → FAIL, `bad` 0 → 1,325, `first_bad_row` 651.** |
| **G6** | ≥ 32 MHz standing, **38.0 MHz hard STOP this sitting**, two draws | **RED ON BOTH DRAWS — 20.80 MHz, worst setup −16.824 ns, setup TNS −10,847.667, figures bit-identical across the two draws.** ~19 MHz below the branch's control band. §6.1. |

Two clauses were met and are stated so they are not lost in the refutation:
**N1-A/B/C/D/E/F all MET on the directed cell** (the 30 take-flip cells closed,
`eirun` untouched, 57 → 27 set-identically), and **`fz2e/531000` and all 109
other still-failing seeds were bit-identical**.

The pre-registration's §6 disposition is unconditional on that last row and it
is executed: **the edit is REVERTED and N-1 is re-booked with the block
characterised and the mechanism NOT condemned.**

**The arithmetic was favourable and it is not the bar.**  Over the 235 scored
seeds the edit was **+4 closed / −1 lost**.  The zero-loss clause was written
before the run precisely so a net trade could not be argued after it, and the
one seed lost is the single seed the whole §64.1 analysis rests on.

**But the sitting's deliverable is not the edit.**  §3 is a finding: **§64.1's
wall now has a coordinate, and it is one bit.**

---

## 1. THE MECHANISM, MEASURED

The directed cell measured the LAW and not the term.  A temporary `$display`
probe (added, run, **reverted**; `hdl/` byte-identical to `310457b2f7` before
the edit) found the term, on `sw/testdata/ie-pinfall/` cell `eihlt_w0:r-8:h9`
— `t_ei = 170`, pin high on rows 162…170, `fall = 171`, `t_hlt = 172`:

    c=172  st=S_OPC_POP  int_p=1110  ie_p=0001  ipend=1  iil=0  eu_halt=1
    c=173  st=S_HALTED   int_p=1100  ie_p=0011  ipend=1  iil=0  eu_unhalt=1
    c=174  st=S_OPC_POP  int_p=1000  ie_p=0111  ipend=1  iil=1  irq_take=1
    c=175  st=S_IRQ_D

At the wake's own boundary clock `c=174` the ordinary tap **`int_p[2]` is
already 0** — the pin at 171 is gone — so the take is carried by the OTHER
disjunct of `irq_int_lvl`, the `intr_pending` latch.  That latch was armed at
`c=171`, the clock `ie_now` rises, by

```
if (ie_now && !ie_p_n[0] && int_p[0])
```

where `int_p[0]` at `c=171` is **the pin of clock 170** while `ie_now` is the
IE of clock **171**.  The two operands are one clock apart, and the comment
above the line already asserted they were not.

Two controls on the same instrument: at `fall = 172` the take is carried by
`int_p[2]` and silicon agrees, so the ucore's extra clock is exactly and only
the `intr_pending` disjunct; and on the free-running leg the boundary lands
where `ie_p[3]` is already set, so the `!ie_p[3]` floor has already retired the
latch.

**THE MECHANISM ACCOUNT IS CORRECT AND IS NOT WITHDRAWN.**  What was wrong was
the scope claimed for it — see §4.

### 1.1 THE EDIT THAT WAS BUILT AND REVERTED

One token, `hdl/rtl/ucore/v30u_eu.sv`, block (a) of the next-state function:

```
-    if (ie_now && !ie_p_n[0] && int_p[0])
+    if (ie_now && !ie_p_n[0] && pin_int)
         intr_pending_n = 1'b1;
```

No flop, no new signal, no state, no opcode named, `HLT` nowhere in the change.
`ss_lint` confirmed it: `SS_VERSION` 0x8D / 226 addresses / 214 flops,
**unchanged**.

---

## 2. THE DIRECTED-CELL REPLAY — EVERY BAR MET, AND IT IS A CONSISTENCY CHECK

The pre-registration (§0.2) declared this leg a consistency check, not
evidence, because the mechanism was selected by probing the cells it scores.
It is reported as one.

**The leg was validated before it was used**: re-run at `310457b2f7` on a
freshly built binary it reproduced the banked ucore column on **2,200 / 2,200
cells — every scored column AND the raw-word `sha256`**, `core/table.json`
byte-identical to the banked one.

    leg      w | board T* | core T* BEFORE | core T* AFTER | delta AFTER
    eirun  0-3 |  3/4/5/6 |    3/4/5/6     |    3/4/5/6    |  0 0 0 0
    eihlt  0-3 |  2/3/4/5 |    1/2/3/4     |    2/3/4/5    |  0 0 0 0

    board vs core, distinct differing cells:  57 -> 27
    taken       30 / 1,920  ->   0 / 1,920
    n_inta      36 / 1,920  ->   6 / 1,920
    ack_off     46 / 1,920  ->  16 / 1,920
    ack_off_hlt 46 / 1,920  ->  16 / 1,920
    n_halt      11 / 1,920  ->  11 / 1,920   (unmoved)
    halt_first   6 / 1,920  ->   6 / 1,920   (unmoved)
    halt_off     6 / 1,920  ->   6 / 1,920   (unmoved)
    wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows : 0 / 1,920 throughout

| id | bar | result |
|---|---|---|
| **N1-A** | the 30 take-flip cells close | **MET — `taken` 0 / 1,920** |
| **N1-B** | `eirun` stays identical | **MET — 0 differing cells at all four waits** |
| **N1-C** | `board T* − core T*` = 0 at all eight strata | **MET** |
| **N1-D** | the other 27 do not move | **MET, and set-identically**: the 27 remaining cells are **the same 27**, seed for seed, with **the same differing columns on every one** |
| **N1-E** | the six invariant columns stay 0 / 1,920 | **MET** |
| **N1-F** | the `ierun` / `iehlt` controls keep their shape | **MET** |

The registered falsifier (a silicon take at `fall_off == T*_ucore` on a HALT
leg) did not fire.

---

## 3. THE FINDING — §64.1's WALL HAS A COORDINATE, AND IT IS ONE BIT

This is what the sitting is for.

`ucore_provenance.md` §64.1 and the C2 landing both record that **`fz2c/404040`
could not be separated from the four `run − arm == 2` seats** — silicon TAKES
on the first and does NOT on the other four, and they are identical on every
column then known in the recognition path.  The directed cell converted the
wall into a measurement but did not move it: *"a predicate that separates them
cannot be a recognition-threshold predicate."*

**It is not a recognition-threshold predicate. It is the arm's pin CLOCK, and
the two populations sit on opposite sides of one bit.**

| population | arm reads the pin at `c−1` (`int_p[0]`, HEAD) | arm reads the pin at `c` (`pin_int`) |
|---|---|---|
| `fz2c/404040` (silicon TAKES) | **matches silicon** (`bad` 0) | **misses the take** (`bad` 1,325) |
| the §64.1 four (silicon does NOT take) | **takes where silicon does not** (`bad` 840·921·891·984) | **matches silicon** (`bad` 0 ×4) |
| the 30 `eihlt` cells (silicon does NOT take) | **takes where silicon does not** | **matches silicon** |

Confirmed on the rows themselves, not on a verdict:

* `fz2c/404040` — chip runs **4** INTA T1 rows (358, 365, 654, 664); with the
  fresher tap the core runs **2** (358, 365) and drives **4** HALT rows where
  the chip drives 2. **The core MISSES an acknowledge silicon makes** — which
  is exactly §64.1's description of this seed, *"SILICON RUNS THE ACKNOWLEDGE,
  seven clocks after its own pin fell."*
* `fz2c/405002` — chip 4 INTA T1 rows at 231, 238, 379, 388; the core now runs
  **the same four at the same rows**.  `fz2e/512056` — chip 2 at 1179, 1190;
  core **the same two**.  They closed for the mechanism's own reason, not by
  reconvergence.

**AND THE SYMMETRY IS MEASURED IN BOTH DIRECTIONS ON THE SAME INSTRUMENT**, by
re-running the same three seeds on the REVERTED build after the revert:

    seed          chip INTA T1 rows      core, tap int_p[0] (HEAD)     core, tap pin_int
    fz2c/404040   358, 365, 654, 664     358, 365, 654, 664   bad 0    358, 365            bad 1325
    fz2c/405002   231, 238, 379, 388     231,238,379,388,528,537 b 840  231, 238, 379, 388  bad 0
    fz2e/512056   1179, 1190             1179,1190,1476,1487   bad 984  1179, 1190          bad 0

    HALT rows: 2 chip / 2 core on all three, under BOTH taps.

**With the HEAD tap the arm fires an acknowledge pair silicon does not run; with
the fresher tap it fails to fire one silicon does.  One bit, both directions,
on the rows, with the HALT-cycle count identical throughout so nothing about
HALT is in play.**  That is the sharpest statement §64.1's wall has had.

**SO BOTH TAPS ARE NOW REFUTED against the union of the three populations, and
no one-bit choice of the arm's pin clock can satisfy all three.**  That is
strictly more than was known this morning: the wall is no longer *"we cannot
find a column"* — the column is found, it is load-bearing in both directions,
and it is still not the separator.  Whatever separates `fz2c/404040` from the
four is a term that has not been named, and any successor should start from
the fact that **the pin level on the IE-rise clock is not it.**

### 3.1 THE WHOLE-PROGRAM EFFECT IS EXACTLY FIVE SEEDS AND NOTHING ELSE

Over the 233-seed disjoint population the edit moved **exactly four seeds** and
the total diverging-row count fell **119,192 → 115,556 = −3,636**, which is
`840 + 921 + 891 + 984` **to the row**.  **Not one other seed moved by a single
row**, and `first_bad_row` was identical on all 109 seeds that stayed FAIL.
`fz2e/531000` stayed PASS.  The three unpredicted C2 seeds (`fz2e/513019`,
`fz2e/516065`, `fz2c/410047`) were bit-identical.

A mechanism whose entire measured footprint over 233 seeds is five seeds, all
in one family, is not a fitted rule — which is why the finding survives the
refutation of the landing.

### 3.2 THE THREE C2 HALT-WAKE SEATS ARE RE-ATTRIBUTED

`ie_pinfall_cell_results_2026-08-11.md` §4 named `fz2c/404071`, `fz2e/514044`
and `fz2e/516001` as *"the seats the next wave should take"* under N-1.  **That
attribution is WITHDRAWN, on the rows:**

    seed          chip INTA T1 rows       core INTA T1 rows      HALT rows
    fz2c/404071   246, 255, 441, 452      253, 439, 450          2 / 2
    fz2e/514044   237, 248, 427, 438      246, 425, 436          2 / 2
    fz2e/516001   586, 604                602                    2 / 2

The core is **not failing to recognise** — it vectors, and it drives the same
number of HALT cycles as the chip.  What it does is **drop the FIRST INTA of
the first acknowledge pair** and place the survivor ~7 clocks late; on the two
seeds with a second pair, that pair is present and 2 clocks early.  **This is
an acknowledge-PAIR defect, not a pin-sampling one**, which is why N-1's
predicate could not touch it and why the edit left all three bit-identical.
It is consistent with the cell's own §3.2 (*"eight clocks of acknowledge
latency with ZERO prefetch cycles on either engine"*) and with wave-5's
refutation of a prefetch-suspend.

**Booked**: the next attempt on these three should be aimed at the INTA pair's
own arbitration/spacing, and it should be measured as one mechanism.  Its
falsifier: a capture in which the chip runs a single-cycle acknowledge, or in
which the core's missing first INTA is present with the pair still mis-spaced.

---

## 4. ERRATUM — WHAT THE PRE-REGISTRATION GOT WRONG, AND WHY

§0.1 claimed the free-running leg **"cannot move under this edit, by
construction"**, on a probed control: the free-running boundary lands where
`ie_p[3]` is already set, so the three-clock floor has already retired
`intr_pending`.

**That control was true of the directed cell's program and I generalised it to
the corpus, where it is false.**  The cell's program (`DI · NOP×6 · EI · sled`)
puts its free-running boundary at `run − arm = 4`, outside the floor.  The fz2
corpus contains free-running boundaries at `run − arm ∈ {2, 3}` — **inside**
the floor — and those are precisely the §64.1 seats.  The floor bounds how long
the latch lives; it does not make the latch unreachable, and one program's
geometry is not a proof about a population.

**This is the erratum, stated rather than smoothed**: a "by construction"
argument measured on one program is a measurement, not a construction.  It is
the same shape of error the standing rule about validating a replacement on
data that did not select it exists to catch, and it was caught by the disjoint
population doing its job — which is the one part of this sitting that worked
exactly as designed.

---

## 5. N-2 — ASSESSED, BOOKED SEPARATELY, NOT LANDED

N-2 is the 11 cells of groups G3 + G5: silicon announces a HALT the ucore does
not, on a **one-clock** request at the park (`n_halt` `(2,0)` ×6 and `(4,2)`
×5).

**It is NOT the same predicate, and the argument is structural, not
numerical.**  All 11 sit at `rise_off ∈ {+2,+4,+6,+8,+10,+12}` — the pin
arrives AFTER `t_ei`, in the park window — so at the arm clock (one clock after
`t_ei`) the pin is **LOW on all 11 under either tap**.  Three of the 11 are on
`iehlt`, where IE never rises and the arm therefore never fires at all, which
is the same statement from the other side and is why the cell calls N-2
IE-independent.  They are also a different observable: N-2 moves `n_halt` with
`taken = False` on both engines in all 11.

**Registered as a NON-MOVER (N1-D) and MEASURED AS ONE: all 11 unmoved, same
cells, same columns.**  That is the prediction that would have falsified the
§1 mechanism account if it had failed, and it held.

**N-2 stays BOOKED.**  It is a HALT-ANNOUNCEMENT question in the F43/F54 zone
(`hlt_wake_disp` / `eu_unhalt_disp`), not a recognition question, and its
stimulus axis is one clock wide — the cell swept `hold` and only `hold = 1`
fires it.  Falsifier unchanged: **any `hold ≥ 2` cell with an `n_halt`
difference**; none exists in 2,200 cells.  **A successor must widen the
park-window stimulus before naming a mechanism**: 11 cells at one stimulus
width would fit a rule rather than find one, and that is the fitted table the
standing principle forbids.

---

## 6. THE LADDER, AS RUN ON THE CANDIDATE

Every gate below was run on the EDITED tree, i.e. on the candidate that is now
reverted.  They are reported because a candidate's ladder is the evidence that
its refutation came from the corpus and not from a broken build.

| gate | result |
|---|---|
| `gen_ucore_qsf.py --check` | **PASS** (green since `2aff7bc844`; **it was RED at `310457b2f7`** for a pre-existing, engine-independent reason — see §7) |
| `r7_lint.py` | **PASS — 0 violations**, 20 nets / 1 carrier / 3 tainted / 51 `stop` sites; **no new declared exception** |
| `x1_retention.py build --leg ret` | REBUILT, receipt `8b9d350ebb7c036b…` (baseline binary `f4472a1c27ab07e2…`) |
| `ss_lint.py` | **exit 0, UNCHANGED**: `SS_VERSION` **0x8D**, BIU 103 / EU 122 / `SS_COUNT` **226**; census **214 architectural flops, 0 UNMAPPED, 2 whitelisted** |
| `test_artifact.py` | **45 / 45** |
| `check_core.py --core ucore --opcodes all --cases 0` | **169,000 / 169,000** |
| `s10-hltsweep-w0 --waits 0` | **97 / 97** (HLT.INT 48/48, HLT.RES 49/49) |
| `s10-hltsweep-w1 --waits 1` | **93 / 95** — `HLT.INT` 44/46 at `(10,'busstat')` and `(11,'pins')`, `HLT.RES` **49/49** |
| `s13-hltsweep-w2 --waits 2` | **45 / 46** — `HLT.INT` 20/21 at `(13,'pins')`, `HLT.RES` **25/25** |
| `s13-hltsweep-w3 --waits 3` | **44 / 45** — `HLT.INT` 19/20 at `(15,'pins')`, `HLT.RES` **25/25** |
| **the four sweeps** | **279 / 283 — the registered value, unmoved, and the four survivors are the four family-D cells and nothing else** |
| `ulockstep.py --golden all --cases 50` | **17,350 / 17,350 LOCKSTEP** |
| `ie_pinfall_cell.py core` + `score` | §2 — every bar met |
| `fz2_replay.py` (233 + 2) | §3 — **N1-1 MISSED 0/3, N1-3 MISSED, N1-2/N1-5 REFUTED** |
| `fz2_immaterial.py falsify` | **PASS** — G6 census 0/8, G7 doc 0/22, G8 no-fork 0/113; residue 92 = 113 − 21 |
| **G6, `quartus_gate.py`, two draws** | §6.1 |

### 6.0 THE OFFLINE REPLAY INSTRUMENT, VALIDATED BEFORE IT WAS BELIEVED

`fz2_replay.py` on 113 F17 ledger failures + 120 deterministically sampled
fabric-PASS seeds reproduced the **FABRIC** verdict **233 / 233 = 100.0 %**
with `first_bad_row` **identical on 113 / 113**, fabric era guard **PASS**,
`tb_sys` receipt `f4472a1c27ab07e2…`, at `310457b2f7`.  The named non-movers
`fz2c/404040` and `fz2e/531000` replayed PASS 2 / 2.  Baselines banked at
`sw/testdata/fz2/_n1_base_all.json` and `_n1_base_named.json`.

⚠ **THE POST-EDIT RUNS WERE TAKEN WITH `--no-fabric-era-guard`, AND THAT IS
SAID BESIDE EVERY POST-EDIT NUMBER.**  `v30u_eu.sv` is a declared input of the
FLASH #17 bitstream receipt, so the guard fires the moment the RTL is touched
and is right to: it is saying the tree is no longer the socket's tree.  **No
post-edit figure in this document is a fabric figure and none is claimed as
one.**  What is compared is a modified core against banked SOCKET rows, which
is untouched silicon; the seeds' captures were sha256-verified against the F17
ledger, **113 / 113**, before a row was scored.

### 6.1 G6 — TWO DRAWS, BOTH RED, AND IDENTICAL

**THE REGISTERED 38.0 MHz HARD STOP FIRED ON BOTH DRAWS.**

| | draw 1 | draw 2 |
|---|---|---|
| receipt | `b611ac6eb3ba6f11…` | `61ae7c4b8b3704c6…` |
| label | *N-1 candidate draw 1 (intr_pending arm on pin_int)* | *…draw 2…* |
| verdict | **RED** | **RED** |
| **Fmax (CPU domain)** | **20.80 MHz** | **20.80 MHz** |
| worst setup | **−16.824 ns** | **−16.824 ns** |
| setup TNS | **−10,847.667** | **−10,847.667** |
| hold TNS | 0.000 on every domain | 0.000 on every domain |
| ALMs | 12,243 / 41,910 (29 %) | 12,243 / 41,910 (29 %) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| E1 `gen_ucore_qsf --check` | PASS | PASS |
| 88-file input manifest | `6b7d512107c2a77c…` | `6b7d512107c2a77c…` (identical) |
| compile | rc=0, 700 s | rc=0, 698 s |
| other domains | `FPGA_CLK2_50` 150.76 · `pll_audio` 57.24 · `altera_reserved_tck` 62.99 | same |

**TWO DRAWS AND THE FIGURES ARE BIT-IDENTICAL, so 20.80 is not a bad draw — it
reproduces.**  Against this branch's CONTROL band (39.16 · 39.37 · 39.47 ·
39.63 · 39.81 · 40.11) the candidate costs about **19 MHz**, and it is 11 MHz
below even the standing 32 MHz floor.  The pre-registration's clause — *"if G6
lands below 38.0, the landing STOPS regardless of how green everything above it
is"* — is executed.

**THIS IS A THIRD, INDEPENDENT REFUTATION.**  §3's loss of `fz2c/404040` and
§0's 0-of-3 seat miss would each have stopped it on their own; G6 stops it for
a reason that has nothing to do with either, and it is the reason that would
have survived a successful corpus result.  It is the 8F ghost FEED precedent
exactly (`r7_lint` PASS, **G6 15.3 MHz**, unlandable as designed) and the same
lesson: **`r7_lint` PASSING IS NOT A TIMING CLAIM.**  `r7_lint` was green on
this candidate and was right to be — `pin_int` is not a `READY` carrier and no
`stop` moved.

**WHY, ARGUED FROM THE SOURCE — AND LABELLED AS AN ARGUMENT, NOT A MEASURED
PATH.**  The retained `sta` reports are summaries and do not carry the failing
path's launch node, so the launch register was **not** read out and is not
quoted.  What the source says: `pin_int` at the core boundary is
`system_large|c_int_q`, already a **register** (`system_large.sv` line 371/378),
so this is not a pad-to-EU route.  The arm sits at the **top of block (a)**,
before the EU's twelve-position chain, and `intr_pending_n` is **overwritten by
later arms in that chain** (`S_IRQ_D` clears it, among others) — so under
blocking-assignment semantics the final value at the `intr_pending` register's
`D` pin is a mux tree whose selects are the whole chain.  Feeding a register
into position 0 of that chain therefore makes it traverse all twelve.  **That
is R7′'s shape with a different source register** (§73 measured 19.42 MHz for
`system_large|c_ready_q` into `v30u_eu` at 62–63 logic levels; this measures
20.80 MHz), and §73's fix shape is the obvious reformulation — see §8.

---

## 7. `gen_ucore_qsf --check` WAS RED AT HEAD, AND IT IS NOT THIS LANDING'S

Measured on a clean tree at `310457b2f7`, before any RTL was touched:
`sw/gen_ucore_qsf.py --check` **exits 1**.  Quartus REWRITES the revision
`.qsf` it compiles (§70.7) and the FLASH #17 build's materialised copy was
committed at `1ad5074ebe` without the post-build regeneration `quartus_gate.py`
itself performs — 107 `set_location_assignment` lines that `hdl/nec_test.qsf`
does not carry.  Regenerated and committed at `2aff7bc844`, identical in kind
to `c7198e210f` after FLASH #6.  **PRE-EXISTING and ENGINE-INDEPENDENT; no gate
value moves; G6's E1 leg could not run until it was green.**

---

## 8. DISPOSITION

* **The RTL edit is REVERTED.**  `hdl/` is byte-identical to `310457b2f7`.
* **N-1 is RE-BOOKED, mechanism NOT condemned.**  The §1 account is measured
  and stands; what is refuted is that a one-bit move of the arm's pin clock is
  the whole law.  It re-opens on **both** of the following, and neither alone
  is enough:
  1. a formulation that separates `fz2c/404040` from the §64.1 four **on a
     column that is not the arm's pin clock** — §3 is now the map of where that
     column is *not*; and
  2. a formulation whose arm does **not** sit at the head of the twelve-position
     chain.  §6.1's 20.80 MHz is a property of WHERE the term was written, not
     of what it says: `intr_pending_n` is set at the top of block (a) and
     overwritten by later arms, so a register entering there traverses all
     twelve positions.  **The shape to try is §73's** — express the arm on the
     `intr_pending` register's own `D` pin, gated by a register-only
     qualifier, exactly as `eu_rd_edge`'s PSW load was moved off the head of
     that chain onto `psw`'s `D` pin.  **To be measured as its own mechanism,
     with its own G6, before any corpus number from it is believed.**
  Anyone re-opening this should note that a reformulation which fixes only (2)
  still loses `fz2c/404040`, and one which fixes only (1) may still draw 20 MHz.
* **N-2 is BOOKED SEPARATELY** (§5), with its non-mover bar met and its
  stimulus-width caveat registered.
* **The three C2 HALT-wake seats are RE-ATTRIBUTED** (§3.2) from a recognition
  defect to an acknowledge-pair defect, on their own rows.
* **`ie_pinfall_cell_results_2026-08-11.md` §5's N-1 shape statement is
  amended** by §1 (the carrier is `intr_pending`'s arm, not the wake tap) and
  its §4 seat attribution by §3.2.
* No board was touched; `sw/testdata/flash_log.jsonl` has the same entry count
  before and after.
