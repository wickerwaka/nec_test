# THE SOCKET-CAPTURE NOISE FLOOR — MEASURED (2026-08-10)

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Wave-4 measurement package, job 2.  **Offline, `sw/` + `docs/` only** — no RTL,
no board, no flash, no Quartus, no re-capture.  Tree `fuzz-v2-on-relanding` at
`32128b57b4`.

---

## 0. THE HEADLINE, IN FIVE SENTENCES

1. **FLASH #15 §5.2's registered falsifier — "capture the whole 3,840 twice on
   one bitstream and count the seeds whose socket leg does not reproduce" — was
   already run, three times, and nobody scored it.**  `fz2c/fz2e-INV2-archive`,
   `-A5-archive` and `-F12-archive` are three complete passes over the same
   3,840 seeds on one bitstream (`.sof 8db6dadf5c4c…`, `flash_git b629296e3a`)
   taken on 2026-08-09 at 05:42, 14:26 and 16:32.
2. **`A5 → F12` is a true repeat** — identical bitstream, identical stimulus on
   all 3,840 seeds, and (checked commit by commit, §2.3) **no change to the
   board/capture/arming path** between the two.  `INV2 → A5` is **not** a
   repeat and is not scored: the terminator schedule moved (`term_clocks`
   3,634 → 3,154 on every seed).
3. **THE FLOOR IS 10 / 3,840 = 0.2604 %** measured in the units the campaign's
   headline is quoted in — a seed changing its `fz2_ledger.py` class
   (MATCHED / FAILURE / DISCARD) between the two passes.
4. **It is not diffuse jitter; it is bimodal and it is the TERMINATOR.**  On the
   730 seeds with a banked capture in both passes, **727 socket row streams are
   IDENTICAL cell for cell** — not one scored row, not one tolerated flicker —
   and the 3 that move go 1,189 to 3,312 diverging rows.  **All 12 seeds whose
   socket leg moved at all had the terminating NMI's `fired` count change, and
   the ledger flips are 10 of those 12.**  The **CORE leg is bit-identical on
   730 / 730**, which is the control that says the FPGA side of the rig is
   deterministic.
5. **What this does to FLASH #16:** its headline missed the registered floor by
   **one** seed and its primary by **two**, and both are deep inside a 10-seed
   noise floor.  **An aggregate corpus-headline delta below about ten seeds is
   not resolvable by a single capture.**  A *seat-level* registered prediction
   is a different animal and is safe: the probability that a NAMED seed is a
   noise flip is 0.26 % each, so F16's two-seat P-1 carried an expected 0.005
   spoiled seats.

---

## 1. PROVENANCE

| thing | id |
|---|---|
| tool | `sw/fz2_noise.py` (this package's; `triple` / `rows` / `ledger` / `eras`) |
| passes | `sw/testdata/campaigns/fz2{c,e}{-INV2-archive,-A5-archive,-F12-archive,-F13-archive,-F14-archive,-F15-archive,}` |
| the repeat | `A5` → `F12`, `.sof 8db6dadf5c4c621ceb6bac9b0935146a4193fa3709051636a260e451e0bee205`, `flash_git b629296e3a` |
| ledger predicate | `sw/fz2_ledger.py::derive` — DISCARD iff `ps3_8080`, else FAILURE iff `bad_rows != 0`.  Nothing else. |
| row comparator | `fuzz_classify.diff_rows`, **the corpus's own**, pointed chip-A vs chip-B |
| outputs | `sw/testdata/fz2/fz2_noise_{triple,rows,ledger,eras}.json` |

Every number below regenerates from the four commands; nothing in this document
is typed by hand.

---

## 2. THE EXPERIMENT, AND WHY IT IS ONE

### 2.1 Seven archived passes

```
pass    seeds  .sof          flash_git         gen_git     first ts
INV2     3840  8db6dadf5c4c  b629296e3a        986f7a0249  2026-08-09T05:42:04Z
A5       3840  8db6dadf5c4c  b629296e3a        e26157c296  2026-08-09T14:26:50Z
F12      3840  8db6dadf5c4c  b629296e3a        8cc02326e9  2026-08-09T16:32:28Z
F13      3840  e4a2056a2de5  f18ad478b9-dirty  f18ad478b9  2026-08-10T00:51:10Z
F14      3840  060215e43c5d  2fa3dd33b3-dirty  2fa3dd33b3  2026-08-10T14:29:53Z
F15      3840  2dc38a17d6c3  77838ef777        77838ef777  2026-08-10T17:57:52Z
F16      3840  fed558c0e611  ddaed64457-dirty  ddaed64457  2026-08-10T20:30:23Z
```

**Three of them share a bitstream.**  That is the registered double-capture,
sitting in the bank since 2026-08-09.

### 2.2 The stimulus gate — what makes a pair a repeat

A pair of rows is scored only if **every** stimulus field is equal:
`image_sha256`, `tier`, `cfg_hash`, `nmin`, `nmax_eff`, `raw_mode`, `ivt_mode`,
`no8080`, `wvec_sha256`, `wvec_n`, the whole `waits` directive
(`wrand/wmax/wseed/fixed`), the whole `evt` directive
(`kind/delay/hold/applied/pin`) and the whole terminator directive
(`tvec/term_clocks/term_hold/vecsub`).

* `INV2 → A5`: **0 / 3,840 scored.**  `term.term_clocks` moved 3,634 → 3,154 on
  every seed — the terminating NMI was rescheduled 480 clocks earlier.  Not a
  repeat.  Reported, not scored, not worked around.
* `A5 → F12`: **3,840 / 3,840 scored.**  Every stimulus field equal on every
  seed.

### 2.3 The tool moved between A5 and F12 — and the capture path did not

`gen_git` differs (`e26157c296` → `8cc02326e9`), so this was checked rather than
assumed.  `git diff e26157c296 8cc02326e9 -- sw/fuzz_campaign.py sw/fuzz_classify.py`:

* **added** `stall_evidence`, `term_mechanism`, `STALL_IDLE`, `SCORER_WINDOW`
  (amendment A-4/A-6 post-hoc classification), and `sentinel_only` on
  `dump_words` / `arch_dump` / `dump_restarted` (finding D-2);
* **removed**, in total, four lines, all in the post-capture scoring block
  (`fc.arch_dump(real, v.n)`, `fc.arch_dump(sim, v.n)`, `dump_restarted`, and a
  moved `hold_rows`);
* **`fuzz_classify.diff_rows` IS UNTOUCHED**, so `bad_rows`, `first_bad`,
  `flick` and `win` are computed by identical code in both passes;
* **`ps3_8080` is untouched**, so the discard predicate is too;
* **nothing in the board / arming / transport path changed at all.**

**Consequence, and it is the load-bearing one: the §4 ledger-flip measurement is
scorer-invariant.**  Both of its inputs come from unchanged code.

**What is NOT scorer-invariant, and is therefore excluded:** the arch-dump
fields.  D-1/D-2 changed the dump reader between the passes, and **10 seeds move
on `arch_words` / `arch_ok` and on NOTHING ELSE** (`fz2c/410064`,
`fz2e/521054`, `523061`, `526039`, `527058`, `528008`, `529009`, `532068`,
`533037`, `535055`).  Those are the tool, not the chip, and they are struck from
every figure below.  So are the 11 "core moved" seeds of `fz2_noise.py triple`:
all 11 are `arch_sim_ok False → True` with `ps3_8080_core` True on both sides —
one-directional, the D-1 window fix exactly.

---

## 3. THE STRONGEST FORM — SOCKET ROWS, CELL FOR CELL

`python3 sw/fz2_noise.py rows`, comparator `fuzz_classify.diff_rows` at the
seed's own `win`, chip-A vs chip-B and core-A vs core-B:

```
seeds with a banked capture in BOTH passes : 730
  chip AND core streams reproduce EXACTLY  : 727
  something moved                          :   3
  pairs not scored (stimulus differed)     :   0

  CHIP moved, CORE did not : 3
  CORE moved, CHIP did not : 0
  both moved               : 0
```

| seed | chip diverging rows | first row | core |
|---|---:|---:|---|
| `fz2c/411076` | 3,312 | 684 | **0 — bit-identical** |
| `fz2e/521059` | 1,189 | 696 | **0 — bit-identical** |
| `fz2e/526025` | 2,850 | 691 | **0 — bit-identical** |

Two things to take from this table and no more.

**(a) The floor is BIMODAL, not a jitter band.**  Re-run against the same
comparator with flicker included, **727 of 730 have not a single differing
`RowDiff` of any kind**, and there are **zero flicker-only pairs**.  A socket
capture either reproduces exactly or it takes a completely different trajectory.
There is no "a few rows wobble" population.  This is why F15 §5.1's and F16
§5.4's five-shot reprobes both came back 5/5 identical: that is the normal case,
and it is normal to four significant figures.

**(b) The CORE leg is the control and it is clean.**  730 / 730 bit-identical
across two passes hours apart.  Whatever moves, it is not the FPGA, not the
memory server, not the transport, and not the readback.

### 3.1 A BAND, REPORTED AND NOT EXPLAINED

All three divergences begin at capture index **717, 729, 724** — a 13-row band
around index ≈ 720, out of a 4,063-row capture.  With **n = 3** that is an
observation, not a finding, and it is written here so the next double-capture
can kill it.

**Falsifier**: double-capture the full 3,840 on one bitstream and histogram the
first-divergence index of every moving seed.  If they scatter over the capture,
the band is three coincidences.  If they pile at ≈ 720 again, something in the
rig happens there and the "noise" floor has a mechanism and an address.

---

## 4. THE FLOOR, IN THE UNITS THE HEADLINE IS QUOTED IN

`python3 sw/fz2_noise.py ledger` — the predicate is `fz2_ledger.py::derive`'s,
verbatim:

```
THE LEDGER-LEVEL FLIP RATE, same bitstream, same stimulus, A5 -> F12
  seeds scored : 3840
  DISCARD->MATCHED          1   fz2e/534020
  FAILURE->DISCARD          1   fz2e/521059
  FAILURE->MATCHED          1   fz2e/534022
  MATCHED->FAILURE          7   fz2c/405055, fz2c/411076, fz2e/518059,
                                fz2e/523040, fz2e/528016, fz2e/530063,
                                fz2e/531045
  TOTAL FLIPS  : 10 / 3840 = 0.2604 %
  A5 : MATCHED 3630  FAILURE 208  DISCARD 2
  F12: MATCHED 3625  FAILURE 213  DISCARD 2
```

**THE MEASURED NOISE FLOOR IS 10 SEEDS IN 3,840, WITH A DENOMINATOR OF 3,840.**

The failure SET moved by 9 (symmetric difference `|A5 △ F12| = 9`) while the
COUNT moved by 5 (208 → 213) — i.e. the count understates the churn by almost
half, which is the trap FLASH #16 §3.1's "the count is as registered, the SET
re-rolled" fell into from the other side.

---

## 5. CONCENTRATION — IT IS THE TERMINATOR, 12 OF 12

```
seeds whose terminator `fired` count moved        : 12 / 3840
... of the 10 ledger flips, `fired` moved on      : 10 / 10
... and the terminating NMI's OWN pin row moved on:  6 / 10
flips that were ESCAPED at A5                     :  7 / 10
   flip rate among escaped seeds : 7 / 1112 = 0.629 %
   flip rate among the rest      : 3 / 2728 = 0.110 %
```

**Every seed whose socket leg moved on any non-arch observable — all 12 of them
— has the terminator's `fired` count change.**  There is no second population.

Seed by seed:

| seat | escaped n | `fired` | terminating NMI pin row |
|---|---|---|---|
| `fz2c/405055` | 0 → 0 | 5 → 1 | 3140 → **3207** |
| `fz2c/411076` | 29 → 29 | 5 → 1 | 3212 → **3132** |
| `fz2e/518059` | 0 → 71 | 4 → 0 | 3301 → 3301 |
| `fz2e/523040` | 49 → 9 | 4 → 0 | 3022 → **3035** |
| `fz2e/528016` | 0 → 0 | 5 → 0 | 3243 → 3243 |
| `fz2e/530063` | 31 → 22 | 5 → 0 | 3070 → 3070 |
| `fz2e/531045` | 9 → 0 | 5 → 0 | **[[1616,2],[3213,20]] → [[3210,20]]** |
| `fz2e/521059` | 30 → 2 | 4 → 0 | 3070 → 3070 |
| `fz2e/534020` | 13 → 2 | 0 → 5 | 1738 → **1717** |
| `fz2e/534022` | 54 → 0 | 0 → 5 | 1766 → **1737** |

Two sub-populations fall out, and they are different mechanisms:

* **the pin moved** (6 seeds) — the terminating NMI asserted up to **80 rows**
  away from where it did in the other pass.  That is the RIG's schedule, not the
  chip.  `fz2e/531045` is the sharpest: the `A5` pass carries an **extra**
  `pin_nmi` run at row 1616 (hold 2) that the `F12` pass does not have at all.
* **the pin did not move and the part did not take it** (4 seeds:
  `518059`, `528016`, `530063`, `521059`) — same row, `fired` → 0.  On three of
  these four the run's `escaped_n` also moved, so the part was already somewhere
  else by then and this is a consequence rather than a cause.  **It is NOT
  established which way round `fired` and the trajectory stand**, and this
  document does not assert it.

The escaped enrichment is real and modest: **5.7×** (0.629 % vs 0.110 %).  It is
not the whole story — 3 of the 10 flips are seeds with `escaped_n == 0` at both
ends, `fz2c/405055` and `fz2e/528016` conspicuously so (0 → 0, clean → 885 and
clean → 2,858 diverging rows).

---

## 6. THE CROSS-ERA PAIRS, FOR CALIBRATION

Same rule, same tool, pairs that do **not** share a bitstream.  These mix the
noise floor with whatever the landing did to the core, so only the CHIP-only
column is readable at all — and even that mixes in any change to the harness
half of the bitstream.

```
pair        same .sof    scored  stim≠  CHIP moved  CORE moved  chip-only
INV2→A5     True              0   3840           0           0          0
A5→F12      True           3840      0          22          11         14
F12→F13     False          3840      0          12          60          9
F13→F14     False          3840      0           4          40          4
F14→F15     False          3840      0           2          22          2
F15→F16     False          3840      0           4           5          3
```

(The `A5→F12` row's 22 and 11 are the **unfiltered** summary-field counts; §2.3
strikes 10 of the 22 and all 11 as the arch-dump tool change, leaving **12**.)

### 6.1 `F15 → F16` against FLASH #16's own hand count — and one erratum

FLASH #16 §7 hand-counted **four** socket seeds moved "with the core provably
uninvolved": `fz2e/513017`, `fz2e/534041`, `fz2e/506039`, `fz2e/535075`.  This
tool, from a different rule and without being told the answer, returns
**chip-moved 4** — the same count — and **agrees on three of the four seeds**:

| seed | this tool | FLASH #16 §7 |
|---|---|---|
| `fz2e/513017` | chip moved, core identical | named |
| `fz2e/506039` | chip moved, core identical | named |
| `fz2e/535075` | chip moved, **core also moved** | named |
| `fz2e/524015` | chip moved (`term.vec_used` False → True), core identical, **no ledger flip** | not named |
| `fz2e/534041` | **chip fields IDENTICAL; the CORE moved** | named |

**ERRATUM, offered to whoever owns the FLASH #16 record.**  §5.4 writes of
`fz2e/534041`: *"**CHIP and CORE dumps byte-identical between eras**"*.  Read
off the banked rows:

```
fz2e/534041   arch_words      (CHIP)  F15 vs F16 : IDENTICAL          <- as stated
              arch_sim_words  (CORE)  F15 vs F16 : SP 46147 -> 46149
                                                   CW 46908 ->  5333  <- NOT identical
```

The chip half of the sentence is right and the core half is wrong.  It does not
touch F16's arithmetic — the seed is a ledger failure either way and the
denominator is unchanged — but it does touch the **attribution**: §5.4's
exoneration of P5′ on that seed rests on the core dump being unchanged, and it
is not.  `fz2e/513017`'s half of the same claim **checks out exactly** (chip
dump moved on 14 of 15 words, core dump byte-identical), so the paragraph's
principal seed is sound.  A P5′-era core move on an escaped open-bus seed is
also entirely expected — F15 → F16 carries a real RTL landing — which is why
`F15 → F16` is a poor floor estimate and the same-bitstream pair is the one to
quote.

### 6.2 Why the same-bitstream number is the one to quote

The flash-to-flash pairs run 2–9 chip-only movers; the same-bitstream repeat
runs 12.  A flash-to-flash pair is the WORSE instrument in both directions at
once: it adds the landing (the core leg moves for real, so `bad_rows` moves for
reasons that are not noise) and it subtracts nothing, so its chip-only column is
neither an upper nor a lower bound on the floor.  The same-bitstream pair has
one confound, the post-hoc tool revision, and §2.3 identifies and strikes every
field it touches.  **Quote 10 / 3,840.**

---

## 7. WHAT THIS LICENSES, AND WHAT IT DOES NOT

**Licensed.**

1. **The corpus headline carries a ±10-seed floor at 3,840.**  FLASH #16's
   `3,722 / 3,838` against a registered primary of `3,724` and a floor of
   `3,723` is **inside it**, and so is any comparable future miss.  A wave whose
   whole case rests on the headline moving by fewer than ~10 seeds has not
   measured anything.
2. **Seat-level registered predictions are unaffected and should carry the
   argument.**  P(a named seed is a noise flip) = 10 / 3,840 = **0.26 %**.  For
   a prediction naming `N` seats the expected spoilage is `N × 0.0026`: F16's
   two-seat P-1 = **0.005**, F15's 29-seat set = **0.075**.  Neither is
   material.  **This is the reason to keep pre-registering seats and to stop
   pre-registering headline floors to the seed.**
3. **A single seed's flip is not evidence of a mechanism** unless it is one of a
   registered set, or it has been reprobed.  Both known singletons —
   `fz2e/506039` (F15) and `fz2e/513017` (F16) — reprobed 5/5 to the *other*
   pass's answer, which §3 now explains: reproducing exactly is the normal case.
4. **The instrument is not the FPGA.**  Core leg bit-identical on 730 / 730
   across passes hours apart.

**NOT licensed.**

5. **This is not a chip-nondeterminism measurement.**  Every one of the 12
   movers has the terminator involved, and 6 of them have the NMI *pin* landing
   in a different place.  Whether the socketed V30 is itself nondeterministic is
   **NOT ESTABLISHED** by this data and may well be zero.
6. **No banked-row substitution.**  Nothing here is used to change a banked
   figure.  FLASH #16's `3,722 / 3,838` remains the figure.
7. **No re-scoring of any past wave.**  The floor is a lens for reading future
   waves; the archived verdicts stand as written.
8. **The ≈ 720 band is not a finding** (§3.1, n = 3).

---

## 8. WHAT A BOARD DOUBLE-CAPTURE WOULD ADD THAT THIS CANNOT

Precisely five things.  Everything else in FLASH #15 §5.2's falsifier is now
answered offline.

1. **A within-session floor.**  `A5 → F12` is separated by two hours, one tool
   revision (post-hoc only, §2.3) and an unknown number of board operations.
   Two captures back to back in one session with one tool build isolate the
   *irreducible* component from the session-to-session one.  Prediction worth
   registering in advance: **fewer than 10 flips**, because the terminator
   schedule is re-derived per session.
2. **A power-cycle term.**  Capture 1, `board_idle`, power cycle, capture 2.
   Nothing in the bank separates thermal / contact / power-up state from
   run-to-run variation.
3. **Causality on the four "pin did not move, part did not take it" seeds.**
   The rig can instrument what it *armed* (`vec_armed`, the armed clock, the
   `EVT_CFG` readback) alongside what it *observed*.  Banked captures carry
   `vec_armed` but not the arming intent, so the direction of causation between
   `fired → 0` and the run's escape is unrecoverable offline.
4. **A denominator on the row-exact leg.**  §3's 727 / 730 is measured on the
   *banked-capture* subset, which is selected toward failures and escaped seeds
   and is **not** the population rate.  A double capture that retains all 3,840
   row streams gives the row-exact floor with a 3,840 denominator.  (Storage:
   ≈ 29 MB + 18 MB per pass at current retention, so retaining all 3,840 is a
   real decision, not free.)
5. **The ≈ 720 band** (§3.1).  Three points cannot resolve it; a full
   double-capture gives one point per mover.

**What a double capture would NOT add**: the flash-to-flash calibration (§6 has
it), the ledger-class flip rate (§4 has it, scorer-invariant), the concentration
(§5 has it), and the core-leg determinism control (§3 has it at 730 / 730).

---

## 9. FALSIFIERS

* **The floor** is refuted if a same-bitstream double capture of 3,840 returns
  0 ledger flips.  Then `A5 → F12` carried an unlogged stimulus difference and
  §2.3's diff missed it; the first place to look is the terminator arming, which
  §2.2 already caught moving between `INV2` and `A5`.
* **The concentration** is refuted by a single moving seed whose `term.fired` is
  unchanged.  There is not one in 3,840.
* **"It is bimodal"** is refuted by a repeat pair with a small non-zero
  `chip_bad` (say, under 50 diverging rows).  The three observed are 1,189,
  2,850 and 3,312 against windows of 4,000.
* **"The FPGA side is deterministic"** is refuted by any core-leg row difference
  between two passes on one bitstream.  730 / 730 identical.
* **The escaped enrichment** is refuted if a larger repeat puts the escaped and
  non-escaped flip rates within each other's intervals; at 7 / 1,112 vs
  3 / 2,728 the separation is suggestive and not strong.

---

## 10. WHAT WAS NOT DONE, AND WHY

* **No board, no flash, no re-capture, no Quartus.**  Every number is banked.
* **No seed was excluded for moving**, and no probe result was substituted for a
  banked row.
* **`INV2` was not repaired into the comparison.**  Its terminator schedule
  differs and it is reported as unscored rather than made comparable, which
  would have been choosing a stimulus definition after seeing the answer.
* **The arch-dump-field movers were struck rather than argued about**, and both
  their count (10 chip, 11 core) and their seeds are listed in §2.3 so the
  decision is auditable.
