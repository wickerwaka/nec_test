# wrfuzz W0 — THE CORPUS PRE-REGISTRATION

**Committed 2026-08-05, BEFORE any generation at scale and BEFORE any board
contact.**  Campaign: `docs/notes/wrfuzz_campaign_plan.md` (task #38).
Ledger: `docs/notes/wrfuzz_provenance.md` §1.
Tree: branch `ucsim`, from HEAD `1a2a9eff4e`.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

Everything below is registered.  A number in this document may be **met**,
**missed** or **superseded**, and a missed bar is **reported as registered and
never restated**.

---

## §1 THE NEW AXIS — PER-ACCESS WAIT VECTORS

### 1.1 What the rig can express, and where that is proved

A wait VECTOR is one Tw count per BUS CYCLE, indexed by the bus-cycle ordinal
counted from the run's start.  Four implementations index it by that one
ordinal:

| leg | mechanism | how it is armed |
|---|---|---|
| **the board** | `hdl/rtl/wvec_buf.sv` (1024 × 32 bit = **4,096 byte entries**), read by `hdl/rtl/nec_bus.sv` at `bus_idx`, priority **replay > random > uniform** | `WRAND.replay` (`v30ctl.set_wrand(replay=1)`); host load via `v30ctl.load_wvec` / the serve `WVEC` command; `v30run.ServeRunner.replay()`; `run_image(..., wvec=)` |
| **the same board, other A/B position** | THE SAME BUFFER serves `use_core=0` and `use_core=1` | `CFG.use_core` is the only difference between the two captures |
| **the TB** | `hdl/tb/tb_v30_core.sv` `+wvec=<file>` → `wvec_arr[wbus_idx]` | `check_seq.run_tb(..., wvec=)` |
| **the model** | `sim/biu_timed.cpp::next_waits` → `wvec_[bus_idx_]` | `v30sim timed-boot --wvec=<file>` |

**The index agreement is MEASURED.**  `ucore_provenance.md` §68.6 bar **R0**:
the chip's ACHIEVED per-cycle waits against the vector it was handed,
**45,699 / 45,699 = 100.0 %** over 186 fresh captures on the socket.

**Does it generalise to fuzz-length programs?  YES, with ONE stated limit, and
the limit is measured rather than assumed.**

* **THE LIMIT IS 4,096 BUS CYCLES.**  `wvec_buf` holds 4,096 entries and
  `nec_bus`'s `bus_idx` is 12 bits.  Past that the three legs do **three
  different things**: the board **WRAPS** to entry 0 of whatever is in the RAM;
  the model falls back to the **uniform `--waits`** level; and the TB's
  `wbus_idx` is an unbounded `integer` indexing `wvec_arr[0:4095]`, so the read
  is **OUT OF RANGE and its value is not defined by the language** — the
  zero-fill at `tb_v30_core.sv:128` covers 0…4095 and says nothing about 4096.
  (A **SHORT** vector is a separate and equally three-way case: model → uniform,
  TB → 0 from the zero-fill, board → the previous run's bytes.)  §68.6's own
  vectors were 4,096 entries for this reason.
* **Fuzz-length programs sit inside it with ~4× headroom.**  A capture is
  `TB_ROWS = 4,200` clocks / `LIMIT_ROWS = 4,000` scored rows, and a bus cycle
  is at least 4 clocks, so a run cannot exceed ~1,050 bus cycles even at zero
  waits — and waits make cycles LONGER, i.e. fewer of them.  **Measured on the
  W0 smoke**: the largest capture over 20 seeds × 2 engines was **728 bus
  cycles**.  It is nonetheless a **BAR (B-5)**, not an argument: every capture's
  bus-cycle count is computed and a seed at or beyond 4,096 is QUARANTINED.
* **The host transport carries it.**  `v30ctl.load_wvec` packs 4 entries per
  32-bit word and writes the whole vector in 1 KB chunks; the serve `WVEC`
  command base64s the raw 4,096 bytes in one line.  §68.6 drove exactly this
  with 186 captures and 0 errors.

**⚠ THREE RIG PROPERTIES THAT ARE DESIGN RULES, NOT OBSERVATIONS.**

1. **ALWAYS EXACTLY 4,096 ENTRIES.**  `load_wvec` writes only what it is
   given and the RAM is **not cleared between runs**, so a short load leaves
   the PREVIOUS run's tail in place and the chip reads it.
2. **VALUES 0…31 ONLY.**  All three legs take `[4:0]` and mask identically, so
   a larger value is not a divergence — it is a false statement in the ledger
   about what the part was told.  `wvec_shapes.build()` raises instead.
3. **THE TWO ENGINE FILE FORMATS ARE DIFFERENT AND THE MISMATCH IS SILENT.**
   The TB reads `$readmemh` (HEX); the model reads `fscanf("%d")` (DECIMAL).
   A TB file handed to the model parses `1f` as `1`, fails on `f`, **stops**,
   and silently runs a truncated vector under the uniform level.  There is no
   diagnostic anywhere in the tree.  `wvec_shapes.write_tb` / `write_sim` are
   separate functions and `check_encodings()` proves on every lint that they
   round-trip to the same list AND are different text.

### 1.2 The five shapes

Five, each with a purpose and at most four parameters.  A larger family would
be the corpus-shaped version of a fitted law table.

| shape | rule | parameters (drawn per seed) | what it is for |
|---|---|---|---|
| **`uni`** | i.i.d. uniform over 0…wmax | `wmax ∈ {1,2,3,7,15}`, 16-bit seed | **the control shape.**  The `wrand` distribution with a HOST-side draw, so any agreement that depends on the rig's LFSR *mirror* rather than on the wait VALUES is separated from any that does not |
| **`walk`** | `w` everywhere, `w+extra` on one access in every `period` | `w ∈ {0..3}`, `extra ∈ {1,2,3}`, `period ∈ {5,7,11,13}`, `phase ∈ [0,period)` | sweeps the arbitration instant in **CLOCK** steps.  `period` is co-prime with the natural 4/5/6-clock bus cadence, so the perturbation **drifts** across the program's own instants without anybody predicting where they are — §65.2's spec made self-sweeping, and §68.6's measured-period form generalised |
| **`skew`** | alternating BLOCKS of `wlo` and `whi` | `wlo ∈ {0,1}`, `whi ∈ {3,7,15}`, `blk ∈ {16,24,32}`, `phase ∈ [0,2·blk)` | **the H3-B-directed shape.**  The point is the block INTERIOR: after 8+ accesses at one level the prefetcher is in **STEADY STATE**, not recovering.  §68.6: all three stimuli that missed class B reached their access through an `EB 00` flush and a cold refill, and *"drive the access from a prefetcher in STEADY STATE, never flushed"* is the one it named and did not try |
| **`burst`** | `wbase` everywhere, one very long wait every `gap` accesses | `wbase ∈ {0,1}`, `wbig ∈ {16,24,31}`, `gap ∈ {29,37,53}`, `phase ∈ [0,gap)` | the high end of the 5-bit field, which the LFSR reduction `(x·(wmax+1))>>8` reaches only at wmax = 15 and never above.  Also the **long single wait run** — see §4.2 |
| **`edge`** | i.i.d. over `{0, 1, 30, 31}` | 16-bit seed | the corners of the field, and the 0-vs-1 boundary where *"no Tw row at all"* becomes *"one Tw row"* |

**Why `skew` avoids the flush-resync failure mode.**  §65.2 diagnosed why its
cell missed: the pad moved the EU request in **whole bytes** (2-3 clocks at a
time) and every access was preceded by a `CODE` fetch on **312/312** because
the `EB 00` flush resynchronises the refill, so the request never landed ON the
eligibility instant.  `skew`'s block length is **≥ 16 accesses**, so the
overwhelming majority of accesses inside a block are ≥ 8 accesses from any
level change: whatever prefetcher state the PROGRAM produced is what the access
meets, and the vector is not itself the thing resynchronising it.  The vector
cannot remove a program's own `EB`/`JMP` flushes — nothing can, in a fuzz
corpus — but it stops the STIMULUS from adding one.

### 1.3 The banked form

Every seed's record carries, and the bank inherits:

| field | content |
|---|---|
| `wvec` | the shape spec dict (shape + its ≤ 4 parameters) |
| `wvec_hex` | **THE VECTOR IN FULL** — 8,192 hex chars, entry *k* at `[2k,2k+2)`.  Literal, not a digest and not a derivation |
| `wvec_sha256` | sha256 of the 4,096 raw bytes |
| `wvec_n` | 4,096 |
| `no8080` | the BRKEM-free generation axis |

`timed_fuzz.banked_wvec()` **recomputes the sha and RAISES on a mismatch**, and
raises on a length mismatch — a record that has been edited or truncated since
the capture would otherwise be scored silently, which is **INV-1's shape
exactly** (a capture scored against a directive nobody gave).

---

## §2 THE STRATIFICATION

### 2.1 The grid

**2 tiers × 14 wait sources = 28 strata.**  The nine EXISTING wait classes are
in the corpus as **CONTROLS**, generated in the same sittings, captured in the
same session, scored by the same comparator — so the new axis is read against
them and never against a remembered number.

| | soup (`n` per stratum) | raw (`n` per stratum) |
|---|---|---|
| `fix0` `fix1` `fix2` `fix3` | 150 each | 75 each |
| `wrand1` `wrand2` `wrand3` `wrand7` `wrand15` | 150 each | 75 each |
| `wvec-uni` `wvec-walk` `wvec-skew` `wvec-burst` `wvec-edge` | 150 each | 75 each |
| **subtotal** | **14 × 150 = 2,100** | **14 × 75 = 1,050** |

> **TOTAL CORPUS = 3,150 SEEDS**, `cid = wr1`.

**Why these sizes.**  Per-stratum resolution, not board time: at p ≈ 0.9 the
95 % interval half-width is **±4.8 points at n = 150** and **±6.8 at n = 75**.
raw is 20 % of the natural tier mix and is the harsher tier; 75 keeps every raw
stratum above the point where a per-cell rate has a usable interval without
doubling the corpus.

**The strata are INDEPENDENT populations, not a paired design.**  Programs are
not shared across wait classes, because `nmax_eff` is a function of the
effective wait level (the capture-budget coupling, `NMAX_SCALE_C = 4`), so a
"same program, different waits" pairing is not available without breaking the
budget rule.  Stated here so nobody reads the table as paired.

### 2.2 The k-blocks — every seed named before it is generated

`cid = wr1`, blocks 1,000 apart from `k_base = 200000`, in the order below.
Stratum *i* (0-indexed) occupies `k ∈ [200000 + 1000·i, 200000 + 1000·i + n_i)`.

| i | tier | source | k range | n |
|---|---|---|---|---|
| 0 | soup | `fix0` | 200000-200149 | 150 |
| 1 | soup | `fix1` | 201000-201149 | 150 |
| 2 | soup | `fix2` | 202000-202149 | 150 |
| 3 | soup | `fix3` | 203000-203149 | 150 |
| 4 | soup | `wrand1` | 204000-204149 | 150 |
| 5 | soup | `wrand2` | 205000-205149 | 150 |
| 6 | soup | `wrand3` | 206000-206149 | 150 |
| 7 | soup | `wrand7` | 207000-207149 | 150 |
| 8 | soup | `wrand15` | 208000-208149 | 150 |
| 9 | soup | `wvec-uni` | 209000-209149 | 150 |
| 10 | soup | `wvec-walk` | 210000-210149 | 150 |
| 11 | soup | `wvec-skew` | 211000-211149 | 150 |
| 12 | soup | `wvec-burst` | 212000-212149 | 150 |
| 13 | soup | `wvec-edge` | 213000-213149 | 150 |
| 14 | raw | `fix0` | 214000-214074 | 75 |
| 15 | raw | `fix1` | 215000-215074 | 75 |
| 16 | raw | `fix2` | 216000-216074 | 75 |
| 17 | raw | `fix3` | 217000-217074 | 75 |
| 18 | raw | `wrand1` | 218000-218074 | 75 |
| 19 | raw | `wrand2` | 219000-219074 | 75 |
| 20 | raw | `wrand3` | 220000-220074 | 75 |
| 21 | raw | `wrand7` | 221000-221074 | 75 |
| 22 | raw | `wrand15` | 222000-222074 | 75 |
| 23 | raw | `wvec-uni` | 223000-223074 | 75 |
| 24 | raw | `wvec-walk` | 224000-224074 | 75 |
| 25 | raw | `wvec-skew` | 225000-225074 | 75 |
| 26 | raw | `wvec-burst` | 226000-226074 | 75 |
| 27 | raw | `wvec-edge` | 227000-227074 | 75 |

**RESERVED AND NOT TO BE USED BY THE SURVEY**: `k ≥ 300000` is the victory
tranche's block (§5), **disjoint from every survey seed by construction** —
§64.1's disjoint-validation discipline, applied to the corpus rather than to a
law.

### 2.3 The invocation, per stratum

```
python3 sw/fuzz_campaign.py run wr1 \
    --start <k_lo> --session-seeds <n> --force-tier {soup|raw} \
    --no-evt --no8080 --survey \
    [ --force-fixed W  |  --force-wrand W  |  --wvec-shapes <shape> ]
```

`--survey` keeps the census mode (all w0 TIMING and non-provenance FUNCTIONAL
divergences are surveyed instead of stopping on the first) while the HARD
capture-integrity stops stay armed: any provenance alarm and the
≥ 5-consecutive-quarantine circuit breaker still abort.

### 2.4 The exclusions, DECLARED HERE AND IN ADVANCE

| exclusion | detector | why |
|---|---|---|
| **`OPEN_BUS`** | `fuzz_classify._open_bus_escaped_before`, the bank's own detector | the program left the image and the chip is reading the rig's open bus; the divergence is the RIG.  Inherited unchanged |
| **class-A 8080 landings** | §63.5's mechanical, board-free criterion: the chip's cell at the first contested slot is `CODE 00484` **and** the window contains `CODE:00008` | 8080/BRKEM is DEFERRED by user decision.  ⚠ **COUNTED AND REPORTED, never a filter applied after the numbers are seen** — see §3.3 |
| **B-5 bus-cycle overrun** | `wvec_shapes.bus_cycle_bound(rows) ≥ 4096` | outside the regime in which the three legs agree about what the vector says |

### 2.5 What is NOT in the corpus, and why

* **No pin events (`--no-evt`).**  A brand-new wait axis crossed with the pin
  axis confounds two things at once, and the EVT column carries its own
  quoting rule (`standing_gates.md`).  An **EVT × vector** cell is NAMED and
  reserved for W3+.
* **No BRKEM (`--no8080`).**  §3.
* **No `--strict` / `--mainline` suppression.**  Those knobs exist to remove
  DELIBERATELY divergent classes for a bug hunt; this is a survey, and undoc /
  TF / random-DS breadth is part of what a random-wait corpus should be asked
  about.

---

## §3 BRKEM-FREE BY CONSTRUCTION — THE MECHANISM, AND WHAT IT DOES NOT DO

### 3.1 The mechanism (a generation axis, in three places, not a post-filter)

| where | what |
|---|---|
| **soup** | `SoupKnobs.p_brkem = 0.0`, applied as a `dataclasses.replace` MODIFIER so it composes with every other knob set instead of replacing one |
| **raw** | `gen_raw.scrub(buf, no8080=True)` adds the pair `0F FF` to the banned set and rewrites **BOTH** bytes to `90`.  Both, not just the second (which is the existing rule for the lockup band), because a bare `FF` left behind is a group-5 ModR/M whose `/3` and `/5` are a far CALL / far JMP through a random word — trading a deferred-scope entry for an ESCAPE |
| **the composed image** | `fuzz_campaign.compose_case()` rewrites every residual `0F FF` pair to `90 90`.  ONE rule; it cannot create a new pair (`0x90` is neither `0x0F` nor `0xFF`), so one left-to-right pass reaches a fixed point |

`compose_case()` is **THE ONE PLACE** a fuzz case's image is built, and
`ucsim_fuzz.regen` was moved onto it: a regeneration path that composes
differently from the capture path is the GEN-DRIFT the bank's sha gate exists
to catch.

### 3.2 Why the knob alone is not the mechanism — MEASURED

Over **1,500 soup seeds with `p_brkem = 0` and the image pass disabled**:

> **118 `0F FF` pairs in 114 of 1,500 seeds — 7.6 % of seeds still carry a
> BRKEM byte pair the generator never emitted.**

They are an immediate byte meeting the next opcode.  With the image pass on:
**0 pairs**.  On the raw tier the generator's own in-context scrub is already
sufficient (**0 residual pairs in 400 composed images**) and the image pass is
the cover for the IVT / handler / fill seams.  This is `ucore_provenance.md`
§63.5's own observation from the other side — 18 of the 42 class-A seeds with
the knob off carried a `0F FF` pair.

### 3.3 ⚠ WHAT IT DOES NOT DO

**A BRKEM-free corpus is not an 8080-free corpus.**  §63.5's other **24**
class-A seeds have **no `0F FF` in the image at all**, and how they enter 8080
mode is **NOT ESTABLISHED** and is booked as an open question.  So:

> class-A landings are **COUNTED at W2** with §63.5's criterion and reported
> per stratum.  A **non-zero count is a FINDING that is routed**, not a filter
> that is applied after the numbers are seen.  If the count is materially above
> the banked corpus's rate, that is itself a result about the wait axis.

---

## §4 WHAT THIS CORPUS EXERCISES OF THE SM3 SUCCESSOR ITEMS

Designed **for** where it is cheap; **not** distorted where it is not.

### 4.1 Designed for, at no cost to the stratification

* **`mc2/584`** — *"a missed `F` pop inside an **eight-clock wait run**"*
  (§86.H, booked and undiagnosed).  `burst` puts single waits of **16, 24 or
  31** clocks on one access in every 29-53, and `skew` holds **3, 7 or 15** for
  blocks of 16-32 accesses.  Both straddle 8 by construction, and neither
  parameter was chosen for this seed — they were chosen for the field corners
  and for steady state, and this falls out.  **Cheap, and it distorts nothing.**
* **H3-B** — the whole point of `skew` (§1.2) and of the four directed cells
  (§5.2).

### 4.2 Counted, not chased

* **`mc1/721`** — DIAGNOSED to the clock and its fix **cannot be taken** (it
  needs a second full micro-ROM read in one clock).  It needs §87.B's directed
  cell, which one seed cannot replace.  The survey **counts** seeds whose first
  divergence carries the signature and hands the count to W3+.
* **the `8F` mod-3 ghost cell** (§84.6) — `8F` at `mod == 3` is the one
  documented architectural don't-care being scored by an instrument that has
  none.  Soup **never** emits it (`emit_stack` forces a windowed EA), the
  **raw tier carries it naturally**, and **no knob is added for it** — a knob
  would distort the stratification to chase 12 seeds.  Counted.

### 4.3 NOT exercised, and said so

* **H7** (the rig's assert instant, BLOCKED, §81.B) needs a **pin event**.
  This corpus is evt-free, so **H7 is not touched by it** and no W2 number may
  be read as bearing on it.
* **the 27 S16 `ARCH` cells** are a directed-walk population, not a fuzz one.
* **family D** is an instrument class scored on `tb_sys` by user disposition.

---

## §5 THE VICTORY TRANCHE — RESERVED, SPECIFIED AS CELLS

**Seeds are drawn at W2.  Cells are frozen NOW.**

### 5.1 The stratified body

The **same 28 strata**, **7 seeds per stratum = 196**, drawn from
`k ∈ [300000, …)` in the same 1,000-apart block layout as §2.2 — **disjoint
from every survey seed by construction**.  The population is frozen to
`sw/testdata/wrfuzz/victory_population.json` with its **sha256 committed before
the first capture** (the b2 precedent, `ucsim_t_provenance.md` §14.4).

Repetitions: **3 per cell**, and **5** on the 12 promotion cells — b2's
protocol, unchanged.

### 5.2 The four directed law-cells

H3-B's steady-state stimulus, the one §68.6 named and did not try.  All four
are `skew` at `blk = 32` (the longest block, i.e. the deepest interior), no pin
event, and they are scored as their own cells and not folded into the 196:

| cell | tier | `wlo` / `whi` | what it separates |
|---|---|---|---|
| **D1** | soup | 0 / 7 | steady state at a level the queue can keep full |
| **D2** | soup | 1 / 15 | steady state at a level that starves it |
| **D3** | raw | 0 / 7 | the same, with no program structure at all |
| **D4** | raw | 1 / 15 | " |

The class-B observable is §68.6's: **same-clock / different-owner pairs**,
paired by ordinal against both engines.  §68.6 measured **0 over 7,254 paired
accesses** with a clock-resolution walk after a flush; these cells ask the same
question in the block interior.  **A registered negative here is a result** and
is reported as one.

### 5.3 The bar

Registered in `wrfuzz_campaign_plan.md` §5 and repeated here so the two
documents cannot drift:

> **B = S − 5.0 percentage points**, where `S` is the survey's
> hardware-versus-silicon cycle-exact rate computed as the **unweighted mean of
> the 28 per-stratum rates**, converted to a whole seed count on the tranche's
> own scored denominator, rounded DOWN.  `S` is computed at W2, written into
> the census and **FROZEN there**; neither `S` nor the allowance may be
> re-derived after the tranche is scored.

Outcomes **MET / MISSED / VOID** as registered in the plan.  The plan's
**falsifier for the axis itself** — the `wvec` strata indistinguishable from
the `wrand` strata — is registered with it.

---

## §6 THE CAPTURE-INTEGRITY BARS FOR W1

Each is a **STOP**, not a tolerance.  A bar that fires means fix the rig and
**RE-CAPTURE** — the correctness directive's own clause.

| bar | statement | how it is measured | registered value |
|---|---|---|---|
| **B-1** | **THE VECTOR WAS APPLIED.**  The chip's ACHIEVED per-cycle waits equal the vector it was handed | `wvec_shapes.applied_score()` over a declared **5 % sub-sample**, on the SOCKET leg (`use_core=0`) | **≥ 99.9 %.**  ⚠ The expectation is **100.0 %** — §68.6 measured 45,699/45,699 on the same mechanism, and the W0 smoke measured **100.00 %** on both offline engines (5,223/5,223 model, 4,809/4,809 `ucore`).  **Anything below 100.0 % is reported as a FINDING**, not absorbed by the 0.1 % |
| **B-2** | **ERA.**  Every capture embeds the artifact layer's input-manifest hash for the bitstream/RTL layer, the generator git SHA, `RIG_EVT_HOLD_BITS`, and the pinned `flash_log` entry | `sw/artifact.py`'s receipt schema + `fuzz_campaign new`'s `flash_pin`; the era guard REFUSES on ABSENT / MIXED / MISMATCH | **0 captures with an absent or mixed era stamp** |
| **B-3** | **THE VECTOR IS BANKED IN FULL.**  `wvec_hex` is exactly 4,096 entries, `sha256(bytes) == wvec_sha256`, and the vector handed to the board equals the banked one | `timed_fuzz.banked_wvec()` RAISES on either mismatch; `fuzz_campaign.wvec_of()` asserts the length before every capture | **0 mismatches; 0 records with a vector spec and no `wvec_hex`** |
| **B-4** | **NO GEN-DRIFT.**  Every seed's image regenerates byte-identically from `(cid, k, ov)` | `ucsim_fuzz.regen`'s sha gate, through `compose_case` | **0** GEN_DRIFT, **0** REGEN_ERROR |
| **B-5** | **THE BUS-CYCLE BOUND.**  No capture reaches 4,096 bus cycles | `wvec_shapes.bus_cycle_bound()` per capture | **0 seeds at or beyond 4,096.**  Any such seed is QUARANTINED and reported, never scored |
| **B-6** | **BRKEM-FREE.**  Zero `0F FF` byte pairs in every composed image | `fuzz_campaign.no_brkem_pairs()`, on the artifact, at generation | **0 pairs over the whole corpus** |
| **B-7** | **BOARD DISCIPLINE.**  `div_guard()` PINNED with its readback recorded on every probe; socket-vs-fabric A/B differing only in `use_core`; full per-clock rows retained with sha256; `board_idle()` after the session; `use_core=0` left selected | `s13_board.div_guard`, `fuzz_campaign.capture_board`'s post-session leg | **`div_guard` PINNED on 100 % of probes**; **0** unpinned readbacks (an unpinned readback is a rig-integrity FINDING and a hard stop) |
| **B-8** | **TRANSPORT.**  RunError → one reconnect + one retry, else QUARANTINE; ≥ 5 consecutive quarantines trips the circuit breaker | `fuzz_campaign.cmd_run` | **circuit breaker not tripped**; the transport-error count is REPORTED, not barred (the SM3 sitting-27 comparison is 0 errors in 2,394 captures) |

**Board-time budget, registered.**  The measured hw-ab rate is **6.0 seeds/s**
(`heartbeat.json`: mc1 `rate 6.01` over 810 seeds, mc2 `rate 6.04` over 5,000 —
chip capture + fabric capture + inline classify per seed).  Budgeted at a
1.5×-derated **4.0 seeds/s**:

| pass | seed-loops | at 4.0/s |
|---|---|---|
| the corpus | 3,150 | **13.1 min** |
| the B-1 sub-sample re-runs (5 %, 3 reps) | 316 | 1.3 min |
| slack for reconnects and the post-session `use_core=0` leg | — | ~5 min |
| **registered W1 session bound** | | **≤ 30 minutes of board time** |

Board time is **not** the binding constraint at this corpus size; §2.1's sizes
are chosen for per-stratum resolution.

---

## §7 THE W2 SURVEY'S DELIVERABLE SHAPE

One census document, over **one tree**, with **one instrument set**, produced
before any fix is planned.  **Nothing lands at W2.**

1. **The per-stratum table** — 28 rows: `n`, scored, excluded (OPEN_BUS /
   class-A / B-5), and three exact-rates: **hardware-vs-silicon** (the fabric
   A/B, the campaign's own comparator), chip-vs-model and chip-vs-`ucore`-TB
   (the offline replays of the same vectors, for attribution only).
2. **The family taxonomy** — every non-exact seed assigned by
   `s15_census --core <matched to the report's core>`.  ⚠ Matching the `--core`
   to the report is a **hard requirement** (gap R4): pointed at a `--core
   ucore` report with the default `sim`, `s15_census` runs clean and reports
   the MODEL's families for the `ucore`'s seeds.
3. **The residue partition** — model-shared (routed `sim/`-first), H3-B,
   class-A 8080 (excluded by user decision, counted), instrument-class,
   catch-all.  Computed, not asserted, with the arithmetic shown.
4. **The H3-B number** — same-clock / different-owner pairs per stratum, the
   statistic the campaign exists to move, against §68.6's 0-of-7,254.
5. **The counts §4.2 asks for** — `mc1/721`-signature seeds, `8F` mod-3 seeds,
   INTA rows per stratum (the §56 float class, plan §4's registered risk).
6. **`S`, and `B = S − 5.0`** — computed, written down, **FROZEN**.
7. **The directed-cell specs for W3+**, each with its own falsifier.

**And the survey reports its own negatives.**  If the `wvec` strata are
indistinguishable from the `wrand` strata (plan §5's falsifier), the census
says so in those words, in its own summary, and the campaign's scope is
re-routed rather than the corpus re-drawn.

---

## §8 W0's OWN FINDINGS

Three, all recorded before they could be forgotten.  Detail:
`wrfuzz_provenance.md` §1.4.

1. **F-1 — a PRE-EXISTING `cfg_hash` provenance drift, and it is NOT this
   campaign's.**  Over 400 banked seeds sampled from all four banks, only
   **156** re-derive their stored `cfg_hash`; 244 do not, because the hashed
   key set grew (`fence`, `mainline`) after they were banked.  **Attributed by
   measurement, not by argument**: the PRE-task-#38 formula, computed by hand
   on the same 400, reproduces the identical 156.  **Nothing gates on
   `cfg_hash`** — it is provenance and a filename, and the images (which
   everything does gate on) regenerate at **300/300** across the banks and
   **216/216** on the b2 tranche.  Booked, not fixed.
2. **F-2 — the BRKEM knob alone leaves 7.6 % of soup seeds carrying `0F FF`.**
   §3.2.  This is why the mechanism is three places and not one.
3. **F-3 — the DECIMAL/HEX asymmetry between the two engines' vector files is
   a live, silent trap.**  §1.1 rule 3.  It has never fired in this tree
   because the only two consumers each wrote their own file; a shared writer
   would have hit it on the first vector containing a value ≥ 10.  Now guarded
   by two named functions and a lint that proves they differ.
4. **F-4 — the vacuous-instrument pattern, in this sitting's own smoke tool,
   caught before its number was quoted.**  `wrfuzz_smoke` reached the RTL
   through `check_seq.run_tb`, whose `CORE` is pinned to **`"fsm"`** — so it
   asserted and printed the **`ucore`'s** receipt and ran the **archived FSM
   core**.  Caught by the receipt layer (an unexpected `tb_v30_core/fsm` line
   appearing in `verilator_binary.jsonl`).  Both legs read 100.00 %, so the
   BAR would have passed either way and the mislabel would have reached W1.
   Fixed by invoking `tf.tb_bin(core)` directly plus a postcondition asserting
   the binary path matches the named core.
   ⚠ **The trap is still live elsewhere and is booked, not patched**:
   `fuzz_campaign run <cid> --tb-only` also goes through `check_seq.run_tb`
   and therefore runs the **FSM** core.  `check_seq.CORE` is **NOT** changed —
   it is pinned deliberately for the archived gates.  **No wrfuzz number may
   be taken from a `--tb-only` run and called an `ucore` number.**

---

## §9 WHAT W0 DID NOT DO

* **No board was contacted.**  No `v30ctl`, no `s10_board`, no serve session,
  no `div_guard`, no flashing.
* **No generation at scale** — the largest population built is the 20-seed
  smoke, which is marked **NON-GATE** in its own report.
* **No mechanism work**, no RTL, no `sim/`, no save-state, no `SS_VERSION`
  move; `git diff` over `hdl/` and `sim/` is empty.
* **No memory file touched, and Codex was not launched** — the coordinator
  routes this package.
* **No ratchet moved.**  The two non-regression legs re-measured this sitting
  are reported in `wrfuzz_provenance.md` §1.3 and are unmoved.
