# wrfuzz W4 — THE VICTORY SITTING: PRE-REGISTRATION

**Committed 2026-08-06, BEFORE any board contact and BEFORE FLASH #11.**
Branch `ucsim`, from HEAD `51139e5cde`.
Protocol: `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md` §5 + `wrfuzz_campaign_plan.md` §4/§5.
Population: `sw/testdata/wrfuzz/victory_population.json`.
Ledger: `wrfuzz_provenance.md` §W4 (to be written at the close).
Driver: `sw/wrfuzz_w4.py`.  Prediction instrument: `sw/wrfuzz_w4_predict.py`.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

**W4 RE-REGISTERS NOTHING.**  The tranche, its cells, its repetitions, the
statistic and the bar are the frozen protocol's and are executed as written.
This document exists because the standing discipline is that everything a
sitting will assert — its bar, its predictions, its execution choices and its
flash plan — is committed before the board is touched.

---

## §1 THE FROZEN ARTIFACTS, VERIFIED BEFORE THEY ARE USED

| artifact | frozen value | **verified this sitting** |
|---|---|---|
| `sw/testdata/wrfuzz/victory_population.json` | `dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d` | **MATCHES** |
| the population's shape | 196 body seeds (7 × 28 strata, `k ∈ [300000 + 1000·i, +7)`) + 4 directed cells × 25 = **296 seeds** | **296, and 912 seed-loops** at 3 reps / 5 on the 12 promotion cells — the frozen count exactly |
| `cid` | `wr2`, disjoint from `wr1`'s `k ∈ [200000, 227075)` **by construction** | the block base is 300000; disjointness is arithmetic, not a check |
| **`S`** | **91.6681 %** (`wrfuzz_provenance.md` §3.1) | **REPRODUCED to four decimals** by `wrfuzz_w4_predict.py` from `results.jsonl` + the registered `open_bus` detector.  A tool that could not reproduce it would not be allowed to predict with it |
| **`B = S − 5.0`** | **86.6681 %** | **carried as a literal constant** in `sw/wrfuzz_w4.py`; **NOT re-derived, at any point, for any reason** |

---

## §2 THE STATISTIC — READ EXACTLY, AND THE ONE AMBIGUITY RESOLVED IN ADVANCE

Plan §5 says two things about the bar in two sentences:

> *"Let `S` be the survey's measured hardware-versus-silicon cycle-exact rate,
> computed as the **unweighted mean of the 28 per-stratum rates** … Then
> **B = S − 5.0 percentage points**, converted to a whole seed count on the
> tranche's own scored denominator, rounded DOWN."*

and the `MET` row says *"the tranche's fabric hardware-vs-silicon **rate** ≥ B"*.

The first is a **per-stratum unweighted mean**; the seed-count conversion is a
**pooled** count.  On the tranche the two are close but not identical, because
the raw strata lose most of their seeds to the OPEN_BUS exclusion and so carry
2-3 scored seeds each against soup's 7.  **Registered now, before any number is
seen:**

> **THE DECIDING STATISTIC IS `T`, THE UNWEIGHTED MEAN OF THE 28 PER-STRATUM
> HARDWARE-VERSUS-SILICON EXACT RATES** — the identical construction that
> produced `S`, computed by the identical code path (`wrfuzz_w2.open_bus` is
> IMPORTED, not re-implemented).  **MET iff `T ≥ 86.6681 %`.**
>
> The plan's pooled conversion — `floor(0.866681 × N_scored)` seeds against the
> measured exact count — is **COMPUTED AND REPORTED BESIDE IT**.  If the two
> readings disagree the disagreement is reported in those words and `T`
> decides, because `T` is the construction `S` was built in and comparing a
> number to a bar computed differently is not a comparison.

**AND THE SECOND CONDITION OF `MET` IS NOT OPTIONAL.**  Plan §5: *"**and**
every non-exact seed's first divergence falls in a family NAMED in the W2
census's taxonomy."*  The taxonomy is `s15_census`'s family set — `PF_LOST`,
`PF_GAINED`, `PF_ADDR`, `DATA_SEQ`, `SCHEDULE`, `PIN`, `TAIL_EXTRA`,
`TAIL_MISS`.  W2 populated six of the eight; **`TAIL_EXTRA` / `TAIL_MISS` were
zero there and COUNT AS NAMED here** — they are in the taxonomy, and a member
of one is a result, not a failure of the clause.  What is **NOT** named is the
catch-all, or a classify error.  Stated now so the reading cannot be chosen
after the count.

### 2.1 The empty-stratum rule — arithmetic, declared before it can bite

A raw stratum draws 7 seeds and W1 measured its OPEN_BUS keep-rate at
0.31-0.49, so a stratum can come back with **zero scored seeds**.  Computed
from W1's own per-stratum keep-rates, **P(at least one of the 28 strata has an
empty scored denominator) = 0.385** — likely enough that leaving it to the
moment would be choosing a rule after seeing a result.

> **A stratum with a zero scored denominator HAS NO RATE.**  It is excluded
> from the mean, the mean is taken over the strata that have one, and **the
> count of averaged strata is printed beside `T` every time `T` is printed.**
> Nothing is imputed and no stratum with a rate is ever dropped — plan §5's
> "no stratum is dropped" governs, and it is about dropping a stratum that
> HAS a number, which this never does.

### 2.2 The exclusions, and they are the survey's

Three, all inherited or declared here in advance, applied to the body:

| exclusion | detector | provenance |
|---|---|---|
| **OPEN_BUS** | `wrfuzz_w2.open_bus` — `ob_escape.feed ≥ 8`, the **registered** detector, imported | prereg §2.4, and F-8: the costlier detector is the one used |
| **B-5 bus-cycle bound** | `bus_cycles ≥ 4096` per capture | prereg §2.4 / bar B-5 |
| **UNSTABLE** | a cell whose repetitions differ inside `fuzz_classify.diff_rows`' own window (rows 9+), either A/B leg | **the b2 precedent** (`ucsim_t_provenance.md` §14.4: *"Population 216, scored 188, excluded 28 OPEN_BUS, **0 UNSTABLE**"*).  Declared here **before** the reps are taken |

**class-A 8080 landings are COUNTED AND LEFT IN THE DENOMINATOR** — §3.3's rule,
unchanged: a count that is routed, never a filter applied after the numbers.

---

## §3 THE PREDICTIONS — DISTINCT FROM THE BAR, AND THIS IS WHAT TESTS UNDERSTANDING

The bar is `B` and only `B`.  What follows is what this sitting **expects**,
derived from the CURRENT offline columns per stratum by
`sw/wrfuzz_w4_predict.py`, run and recorded before the board was touched.

**The construction**: for every stratum, the seeds W2 scored and found NOT
exact in fabric are looked up in the CURRENT `ucore` Verilator column over the
same banked captures (`timed_fuzz --core ucore --seeddir <the W2 seeds>`,
measured this sitting at **91 / 184**, against W2's 49).  A seed the current
core replays exactly is predicted to CLOSE.  `predicted_rate_i =
(exact_i + closed_i) / scored_i`; the predicted statistic is the unweighted
mean of the 28 — the same construction as `S` and `T`.

**Its three weaknesses, named before the result:** the proxy is the TB and not
the fabric (W2 measured them agreeing on 182/184, so the substitution costs
about a point); a scored miss with no offline row is held MISSED, the
conservative direction (**0 such seeds, as it happens**); and nothing here
predicts a seed going the other way, which takes W3.1-W3.5's "ZERO LOST" bars
at their measured word.

### 3.1 The headline prediction

| | |
|---|---|
| **predicted `T`** | **93.0017 %** |
| standard error of a 28-stratum mean at the tranche's expected denominators | **2.64 points** (the raw strata's 2-3 scored seeds dominate it) |
| **registered 95 % prediction band** | **[87.82 %, 98.18 %]** |
| the bar | **86.6681 %** — **2.40 SE below the point prediction** |
| expected pooled scored denominator (196 body seeds) | **≈ 137** |
| pooled predicted rate | **96.30 %** (2,422 / 2,515 on the survey's own population) |

**⚠ THE BAND'S LOWER EDGE IS 1.16 POINTS ABOVE THE BAR.**  That is registered
as the honest margin: this is not a comfortable bar, it is a bar that a bad
draw on the raw side can reach.  The 5.0-point allowance was registered at W0
against a 2.1-point SE estimate for a 196-seed mean; the tranche's actual SE is
**2.64**, larger, because the OPEN_BUS exclusion takes two-thirds of the raw
tier. **This is reported as a property of the design, not as a reason to move
anything.**

### 3.2 The per-stratum predictions, all 28

`W2%` is the frozen survey rate; `pred%` is this sitting's expectation.

| i | stratum | scored (W1) | W2 % | scored misses | predicted CLOSED | **pred %** | Δ |
|---|---|---|---|---|---|---|---|
| 0 | soup/fix0 | 150 | 95.33 | 7 | 1 | **96.00** | +0.67 |
| 1 | soup/fix1 | 150 | 96.67 | 5 | 3 | **98.67** | +2.00 |
| 2 | soup/fix2 | 150 | 95.33 | 7 | 2 | **96.67** | +1.33 |
| 3 | soup/fix3 | 150 | 95.33 | 7 | 4 | **98.00** | +2.67 |
| 4 | soup/wrand1 | 150 | 97.33 | 4 | 0 | **97.33** | +0.00 |
| 5 | soup/wrand2 | 150 | 94.00 | 9 | 6 | **98.00** | +4.00 |
| 6 | soup/wrand3 | 150 | 96.00 | 6 | 4 | **98.67** | +2.67 |
| 7 | soup/wrand7 | 150 | 95.33 | 7 | 1 | **96.00** | +0.67 |
| 8 | soup/wrand15 | 150 | 96.00 | 6 | 6 | **100.00** | +4.00 |
| 9 | soup/wvec-uni | 150 | 98.00 | 3 | 1 | **98.67** | +0.67 |
| 10 | soup/wvec-walk | 150 | 92.00 | 12 | 7 | **96.67** | +4.67 |
| 11 | soup/wvec-skew | 150 | 98.67 | 2 | 2 | **100.00** | +1.33 |
| 12 | soup/wvec-burst | 150 | 95.33 | 7 | 3 | **97.33** | +2.00 |
| 13 | soup/wvec-edge | 150 | 100.00 | 0 | 0 | **100.00** | +0.00 |
| 14 | raw/fix0 | 32 | 81.25 | 6 | 0 | **81.25** | +0.00 |
| 15 | raw/fix1 | 36 | 80.56 | 7 | 0 | **80.56** | +0.00 |
| 16 | raw/fix2 | 26 | 92.31 | 2 | 0 | **92.31** | +0.00 |
| 17 | raw/fix3 | 29 | 86.21 | 4 | 1 | **89.66** | +3.45 |
| 18 | raw/wrand1 | 25 | 68.00 | 8 | 1 | **72.00** | +4.00 |
| 19 | raw/wrand2 | 32 | 87.50 | 4 | 0 | **87.50** | +0.00 |
| 20 | raw/wrand3 | 37 | 78.38 | 8 | 0 | **78.38** | +0.00 |
| 21 | raw/wrand7 | 30 | 93.33 | 2 | 0 | **93.33** | +0.00 |
| 22 | raw/wrand15 | 30 | 93.33 | 2 | 0 | **93.33** | +0.00 |
| 23 | raw/wvec-uni | 26 | 96.15 | 1 | 0 | **96.15** | +0.00 |
| 24 | raw/wvec-walk | 28 | 89.29 | 3 | 0 | **89.29** | +0.00 |
| 25 | raw/wvec-skew | 31 | 87.10 | 4 | 1 | **90.32** | +3.23 |
| 26 | raw/wvec-burst | 23 | 91.30 | 2 | 0 | **91.30** | +0.00 |
| 27 | raw/wvec-edge | 30 | 96.67 | 1 | 0 | **96.67** | +0.00 |

**136 scored misses, 43 predicted CLOSED, 93 predicted still missed.**

**⚠ THE PREDICTION'S OWN SHAPE IS A CLAIM AND IS REPORTED AS ONE**: every one
of the 43 predicted closures is in the SOUP tier bar two (`raw/fix3` 1,
`raw/wvec-skew` 1).  The four W3 landings are the BRK/TF single-step trap's
entry and take, and the survey measured that axis at 55 % of the residue —
**soup carries the TF axis and raw largely does not**.  If the tranche's raw
strata move materially, that is a finding against this reading.

### 3.3 The residue-family prediction

The tranche's non-exact seeds are predicted to fall in the six families W2
populated, with `SCHEDULE` and `PF_LOST` the largest, **the catch-all EMPTY**,
and **no member of any family outside the taxonomy**.  A catch-all member is a
`MISSED` under condition 2 and is reported as one.

### 3.4 The directed cells D1-D4 — a registered NEGATIVE is the expectation

§68.6 measured the class-B observable (**same clock, different owner**) at
**0 over 7,254 paired accesses** with a clock-resolution walk after a flush.
D1-D4 ask the same question in the interior of a 32-access `skew` block —
§65.2's own "steady state, never flushed" suggestion, the one stimulus of the
three that has never been tried.

> **PREDICTED: 0 class-B pairs.**  The prediction is a NEGATIVE and is
> registered as one; **a registered negative here is a result and is reported
> as one**, per prereg §5.2.  A NON-ZERO count would be the first class-B
> evidence this project has ever had and would be **BOOKED for the successor
> queue, not chased in this sitting.**

⚠ **The pairing is chip-against-FABRIC**, the campaign's own comparator (plan
§4), not chip-against-an-offline-engine as §68.6 did.  `sm3_h3_cell.measure` is
IMPORTED so the statistic itself is §68.6's.  The directed cells are **scored as
their own cells and are NOT folded into `T`**, per prereg §5.2.

### 3.5 The fabric re-base — the standing instrument-agreement rule

FLASH #11 re-bases every fabric column.  **The offline references were
RE-TAKEN ON THIS TREE BEFORE THE BOARD WAS TOUCHED** (§83.0/§83.0b's lesson
applied, not re-learned), and the fabric predictions are those columns **cell
for cell**:

| leg | offline reference, re-taken this sitting | **registered fabric prediction on FLASH #11** |
|---|---|---|
| the four HLT sweeps | `x1_retention offline` (`tb_v30_core`) **279 / 283**; `ret` (`tb_sys`, `X1_AD_RETENTION` ON) **279 / 283**, BAR (i) and BAR (ii) **MET**, 245 closed, **0 survivors**, **0 cells differing from offline** | `x1_fabric baseline --leg fab_f11` = **279 / 283**, **0 PASS/FAIL disagreements and 0 differing first-divergence coordinates against `ret` over all 283**, and the four failures are **NAMED IN ADVANCE**: `s10-hltsweep-w1/HLT.INT/8` and `/9` at (row 11, `pins`, `PASV`), `s13-hltsweep-w2/HLT.INT/12` at (13, `pins`, `PASV`), `s13-hltsweep-w3/HLT.INT/15` at (15, `pins`, `PASV`) — the four family-D cells and nothing else |
| the S16 directed display walk | `sm3_s16_fabric offline` (`tb_v30_core`, rows only) **1,347 / 1,371** | `sm3_s16_fabric fabric --leg fab_f11` = **1,347 / 1,371**, `= vsys_ret` exactly, 0 disagreements and 0 differing coordinates over all 1,371; the 24 failures are the four family-D coordinates × the six frozen programs, **catch-all EMPTY** |
| the socket control | — | `x1_fabric socket --leg soc_f11` = **49 / 49** |
| first light | — | `check_ab_hw all 800` = **MATCH on all three legs, 800/800** |
| the close | — | `use_core=0` chip proof **MATCH 800**; `div_guard` **PINNED on every probe**; `board_idle()` clean |

**⚠ NOTE THAT THE OFFLINE REFERENCES DID NOT MOVE.**  279/283 and 1,347/1,371
are FLASH #10's figures too.  The registered prediction is therefore that the
four W3 landings **do not touch the HLT sweeps or the S16 walk at all** — they
are the BRK/TF single-step entry and take, and neither population fires a trap.
A movement in either would be a finding against that reading.

---

## §4 THE FLASH PLAN — FLASH #11

**Flashing is AUTHORIZED for this declared milestone** (work order), by
`sw/safe_flash.sh` only.

1. **G6 fresh at HEAD is the promotion receipt.**  `sw/quartus_gate.py` on the
   **CONTROL/DEFAULT** build (no `X1_AD_RETENTION`) from a clean `hdl/` at
   `51139e5cde`, E1 `gen_ucore_qsf --check` first.  Bars E2 0 errors, **E3
   Fmax ≥ 32 MHz**, E4 worst setup > 0, E5 TNS 0.000 setup and hold on every
   domain.  **The gate must be GREEN before anything is flashed.**  W3.5's
   receipt `a658942cff4cceeb…` is NOT reused: it records the tree as
   `734e11c010-dirty` (the landing before its commit), and a promotion receipt
   for a flash must name the committed tree.
   **RUN, AND GREEN, BEFORE THIS DOCUMENT WAS COMMITTED:** E1 `gen_ucore_qsf
   --check` **PASS** · **0 stage errors, 0 error lines**, map/fit/asm all
   Successful · **E3 Fmax 47.31 MHz** (bar ≥ 32) · **E4 +9.226 ns** · **E5 TNS
   0.000 on every domain** · ALMs **11,232 / 41,910 (27 %)**, latches **0**,
   `lpm_divide` **0**.  Receipt **`b9a27bcf5c6427d4…`**, tree **`51139e5cde`
   CLEAN** (`dirty_tracked: false`), input manifest **88 files
   `fc508a1c4c17228e…`** — **byte-identical to W3.5's**, which is the check
   that says `hdl/` has not moved since the take-clock term landed.  `.sof`
   `d2dc04fe8d2186ff…`.  The figures reproduce W3.5's to the digit on a
   different receipt id, which §74.4 says this design does not guarantee.
2. **The FLASHED bitstream is the RETENTION build**, §69.4/§73.8's recipe:
   `quartus_map --verilog_macro="X1_AD_RETENTION=1"` + `fit` + `asm` + `sta`
   from the same regenerated `.qsf`.  **This is the RESTING CONFIGURATION** —
   FLASH #6, #9 and #10 were all retention builds (`standing_gates.md`), the
   whole W1 corpus and therefore `S` itself was captured on one, and a
   control-build FLASH #11 would silently change the comparator that produced
   the frozen bar.  The retention is on the OBSERVATION path (`hb_ad_sample`)
   only, so the `use_core=0` socket position is unaffected by construction and
   is MEASURED unaffected by the closing chip proof.
   ⚠ **Recorded, because it is a real limitation and not a footnote:** the G6
   GATE is the control build; the retention build's figures are RECORDED, not
   barred, and its input-manifest hash differs from the control's for the
   §80.B.1 reason (Quartus appends pin assignments to the revision `.qsf`).
   `gen_ucore_qsf --check` is re-run green afterwards.
3. **`sw/safe_flash.sh` with its VERIFY leg**, `flash_log.jsonl` 13 → **14
   entries**.  Then first light, then `fuzz_campaign.py new wr2` so the
   campaign manifest pins **FLASH #11** and every capture's era stamp names it.
4. **If VERIFY fails the session STOPS.**  A flash is not retried into an
   unreachable board.

---

## §5 THE EXECUTION CHOICES — everything the protocol left open

### 5.1 Rows are retained for EVERY capture

W1 retained 380 of 3,150 and **F-9 booked that as a defect**: *"retain all
rows, or bank the predicates the survey will need, at capture time."*  The
tranche is 296 seeds, so the fix is affordable and is taken: **every seed's
every repetition, both A/B legs, banked gzipped with a per-file sha256 and a
`SHA256SUMS` beside them.**  This is the only place W4 does more than W1, and
it is a booked lesson being paid rather than a scope change.

### 5.2 The repetitions ARE the stability leg, on every seed

W1 bought B-9 on a 5 % sub-sample because the corpus was 3,150.  The tranche's
frozen 3 reps (5 on the 12 promotion cells) are spent as the stability
comparison on **100 % of the population**: rep 1 against every later rep, on
**both** A/B legs, inside `fuzz_classify.diff_rows`' own window (rows 9+) — W1
§2.3's reading of the same sentence, unchanged.  The 1-cycle F↔S queue-status
flicker is counted and reported beside the bar, never folded into it.

### 5.3 The scoring capture is REPETITION 1

Deterministically, always, and stated before any capture: the seed's scored
verdict is repetition 1's, produced by `fuzz_campaign.eval_case` — the exact
path the survey's own corpus pass used.  Later repetitions test stability and
never vote on the verdict.  (If a cell is unstable it is EXCLUDED per §2.2, so
no later repetition can be silently promoted to "the good one".)

### 5.4 The circuit breaker stays armed

`≥ 5 consecutive quarantines` STOPS the driver.  A transport error costs one
reconnect and one retry (`capture_board`'s own contract) and then quarantines
the seed.  The quarantine count is REPORTED, not barred (B-8).

### 5.5 `div_guard` cadence

PINNED and its readback RECORDED at **every cell boundary** (32 cells) plus
preflight, capture end and the close — W1 §2.4's reasoning, unchanged: the
divider is commanded on every single capture by construction, so recording it
912 times would be one fact written 912 times.

---

## §6 WHAT THIS SITTING WILL NOT DO

* **NO MECHANISM WORK.**  Whatever the tranche exposes is **BOOKED for the
  successor queue** and fixed in no sitting that is also scoring a bar.
  Nothing lands in `hdl/` or `sim/` after FLASH #11 is taken.
* **`S` and `B` are not re-derived, re-computed or restated**, whichever way
  the number falls.  A `MISSED` is reported as registered; the tranche is not
  re-drawn and no stratum with a rate is dropped.
* **The comparator is not swapped after a result is seen** — plan §4's own
  clause, and §56 names it in terms.
* **No memory file is touched and Codex is not launched** — the coordinator
  runs the campaign-close review.
* **No standing gate is invented.**  `standing_gates.md`'s fabric rows are
  RE-BASED to FLASH #11 and the tranche figure is registered as a first
  registration, not as a ratchet.
