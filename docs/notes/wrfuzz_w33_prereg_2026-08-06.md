# wrfuzz W3.3 — PRE-REGISTRATION: the `mc1/721` collision cell, P1's take
# clock, and the `PIN` five

**Task #42.  Written and committed BEFORE the first board contact of the
sitting and before any engine or RTL file was edited.**  Branch `ucsim`, tree
`32b2d6accb`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

Three owed cells and one family.  New instruments: **`sw/w33_pin5.py`**,
**`sw/w33_poste_cell.py`**, **`sw/w33_take_cell.py`**.

---

## §0 WHAT IS OWED, AND FROM WHERE

| item | booked at | what it owes |
|---|---|---|
| **the `mc1/721` collision cell** | `ucore_provenance.md` §86.G / §87.B | §86.G's own falsifier, run as a DIRECTED CELL, to decide **which of two measured placements moves** |
| **the P1 take-clock cell** | `wrfuzz_provenance.md` §5.4a / §5.7 | the TAKE CLOCK at the contested entry, re-specified around *"where is the take, and what does the prefetcher do in the nine clocks after it"* |
| **the TF floor-cell composition check** | `standing_gates.md` (BRK/TF floor cell) | that the standing populations still compose EXACTLY after W3.1's shadow law and anything W3.3 lands |
| **the `PIN` five** | `wrfuzz_survey_2026-08-05.md` §5 / queue #3 | the two non-`mc1/721` seeds' diagnosis from banked rows; the three signature-carriers ride the cell |

---

## §1 THE BANKED-EVIDENCE LEG, MEASURED BEFORE THE CELL WAS DESIGNED

⚠ **This section is a MEASUREMENT taken from banked silicon and the frozen
tree, not a prediction.**  It is written here so the cell's design cannot be
mistaken for having been chosen after seeing the cell's own result.

`sw/w33_pin5.py` + the RTL's own `+brktrace` probes (`1BL` / `PE`, added at
§86.G) over the seven `PIN` seeds of survey §5 / §5.1:

**ALL FIVE `ucore`-ONLY `PIN` SEEDS CARRY AN EFFECTIVE `1BL`→`PE` ADJACENCY
UPSTREAM OF THEIR FIRST PARTING, AND ON EVERY ONE THE MODEL-ORDER FINAL VALUE
IS WHAT SILICON SHOWS.**

| seed | adjacency | 1BL bits | post-`E` writes | model-order final | what silicon shows |
|---|---|---|---|---|---|
| `wr1/200127` | clk 193→194 | `0001` CY | `fa83` | `fa82` (CY 0) | downstream word `a9d8`, `ucore` `a9d7` (Δ 1) |
| `wr1/203092` | clk 638→639 | `0001` CY | `f217` | **`f216`** | **`f216`** on the lanes, `ucore` `f217` |
| `wr1/205145` | clk 416→417 | `0001` CY | `f017` | **`f016`** | word `ab02` (CY 0), `ucore` `ab03` |
| `wr1/207147` | clk 1221→1222 | `0001` CY | `f246` | `f247` (CY 1) | downstream word `b3be`, `ucore` `b3bd` (Δ 1) |
| `wr1/209095` | clk 393→394 | **`0200` IE** | `f246` | **`f046`** | **`ps.ie = 0`**, `ucore` `ps.ie = 1`, 113 rows |

* The survey said *"three of the five carry `mc1/721`'s signature"*.  Measured,
  it is **five of five**, and the two `ps 2!=6` seeds are the SAME collision one
  flag bit over: `ps` bit 2 is `IE` (`sim/biu_timed.cpp:data_ps`), the 1BL is a
  `DI`, and `9E` SAHF's post-`E` row writes the WHOLE flag word (its `007D` row
  snapshots `FLAGS -> tmpaH`), so it puts IE back.
* **The bus SCHEDULE is identical to silicon on all five** (`schedule_identical
  = YES`, 253 / 172 / 190 / 192 / 175 cycles), through 4, 2, 1, 2 and 3
  adjacencies respectively.  A post-`E` discharged INLINE on the `E` row's own
  edge would be one clock CHEAPER than the `ucore` is, so the schedule would
  move.  **It does not.**  That is a measurement against §86.G's specified fix,
  and it is why this sitting does not re-propose it.
* `wr1/225009` (model-SHARED, `ps 2!=6`, `ndiff` 1) has NO effective adjacency
  before its parting at row 1855; it is **not** this family and stays routed
  `sim`-first.  `wr1/215017` (model-shared) has one at clk 233 and is likewise
  not in the `ucore`-only column.

---

## §2 CELL 1 — THE `mc1/721` COLLISION CELL (`sw/w33_poste_cell.py`)

§86.G's falsifier, verbatim: *any `<ROM form whose post-E row writes a
register>` followed by a `<1BL form that writes the same register>` with a
PRE-POPPED successor, where the `ucore`'s final value is the successor's write
rather than the post-`E`'s.*

The cell manufactures it in **two independent readouts on two different
register bits through two different pin paths**, plus the arm that decides
which placement moves, plus four nulls.

### §2.1 THE ARMS

* **ARM A — IE on the `ps` pins.**  `FB` EI · `9E` SAHF · `FA` DI · 8 × `NOP`.
  `9E`'s post-`E` writes the whole flag word (IE = 1 from its own `E`-row
  snapshot); `FA` is the successor 1BL that clears IE.  The observable is the
  `ie` bit of the status nibble on the `CODE` fetches of the NOP run — **no
  memory write and no frame reader**.
* **ARM B — the flag WORD through a `PUSHF` `MEMW`.**  `33 C0` XOR AW,AW
  (which plants a flag byte of `0x46` that NEITHER candidate can produce, so
  "one write is LOST" is a distinguishable THIRD outcome) · `B4 xx` MOV AH ·
  `9E` SAHF · a CY 1BL (`F5` CMC / `F9` STC / `F8` CLC) · `9C` PUSHF ·
  `5A` POP DX.  40 independent periods per capture.
* **ARM D — the ISOLATED 1BL, and it is the DECIDER.**  `FB` EI · `8A 07`
  MOV AL,[BW] (the bus ANCHOR) · pad · `FA` DI · `8A 07` (the readout) ·
  4 × `NOP`, with the pad walked over six lengths so the prefetch phase sweeps
  the commit clock.  No `9E` anywhere.
* **NULLS.**  `a_noDI` (`9E`, no successor 1BL), `a_no9E` (the 1BL with no
  post-`E`), `b_nobl` (`9E`, no 1BL), `b_no9E` (the 1BL, no `9E`).

### §2.2 THE CANDIDATES

* **C1-A — POST-`E` FIRST.**  The die commits the post-`E` row's register write
  and the successor's 1BL write lands ON TOP of it.  (The C++ model's order.)
* **C1-B — 1BL FIRST.**  The successor's 1BL write commits first and the
  post-`E` overwrites it.  (The `ucore`'s order, §86.G.)
* **C1-C — ONE WRITE IS LOST.**  §49.8's original reading.

### §2.3 THE PREDICTIONS — **measured from both engines on the frozen tree
### BEFORE the board was contacted** (`sw/testdata/w33-postecell/engines.json`)

| cell | **C1-A (post-`E` first)** | **C1-B (1BL first)** | **C1-C (post-`E` lost)** |
|---|---|---|---|
| `b_cmc:w0` PUSHF word, ×40 | **`f0d6`** | `f0d7` | `f047` |
| `b_stc:w0` PUSHF word, ×40 | **`f0d7`** | `f0d6` | `f047` |
| `b_clc:w0` PUSHF word, ×40 | **`f0d6`** | `f0d7` | `f046` |
| `a_none:w0` `CODE` fetches published with `ie = 0` | **> 0** (the model: 192 of 249) | **exactly 0** (the `ucore`: 0 of 249) | n/a |
| `a_none:w3` `CODE` fetches with `ie = 0` | the model's 228 of 268 | the `ucore`'s 148 of 268 | n/a |

⚠ **`b_cmc` and `b_stc` predict OPPOSITE WORDS for the SAME candidate.**  A rig
bias, a stuck lane or a reader defect that favoured one word cannot satisfy
both, and that is why the pair is in the cell.

**THE NULLS, where both candidates agree and both engines already do** — these
are what says the readout reads the collision and not the rig:

| null | both engines, w0 | both engines, w3 |
|---|---|---|
| `a_noDI` `CODE` with `ie = 0` | **0** of 249 | 11 of 268 |
| `a_no9E` `CODE` with `ie = 0` | **192** of 249 | 228 of 268 |
| `b_nobl` word | `f0d7` ×40 | `f0d7` ×41 |
| `b_no9E` word | **`f047`** ×40 | `f047` ×41 |
| `b_*:w3` (all three) | — | both engines AGREE: `f0d6`/`f0d7`/`f0d6` |
| `a_clc` / `a_inc` / `a_movi` (any pad) | both engines AGREE | both engines AGREE |

`b_no9E` producing **`f047`** is what CALIBRATES C1-C's third value on the same
rig, in the same capture set, with the same reader.  The `w3` column and the
padded `a_*` variants are MATCHED CONTROLS in which the pre-pop geometry does
not arise and the two engines therefore agree — so a difference that appeared
there too would be a rig finding, not the collision.

### §2.4 THE BARS, REGISTERED

* **W-1** all four nulls match BOTH engines exactly, at both waits, on every
  rep.  **If any null fails, NO verdict is scored from this cell.**
* **W-2** each of the three `b_*:w0` cells is UNANIMOUS across its 40 periods
  and 3 reps.  A mixture is reported as a mixture and is not a verdict.
* **W-3** `b_cmc:w0` and `b_stc:w0` select the SAME candidate.
* **W-4** `a_none:w0` — a different register bit, a different pin path —
  selects the same candidate as arm B.
* **W-5 (the decider)** the twelve `d_*` cells AND `a_no9E` at both waits match
  BOTH engines exactly.
* **W-6** the 3 reps of every cell are identical.
* **W-7** the matched controls (`b_*:w3`, `a_clc`/`a_inc`/`a_movi`) match both
  engines.

### §2.5 THE DECISION RULE — **written before the run**

1. **W-1…W-4 select C1-A and W-5 FAILS** (the isolated 1BL commit is NOT where
   both engines put it): the 1BL's commit clock is itself misplaced, globally.
   That is a ONE-TERM move that needs no second micro-ROM read and no change to
   the post-`E` row's clock, so **§87.B's collision DISSOLVES** — but the move
   is global and it gets **its own pre-registration and its own ladder**.
   **NOT landed this sitting.**  Booked with its numbers.
2. **W-1…W-4 select C1-A and W-5 PASSES**: silicon commits post-`E` first, and
   the 1BL commit is exactly where both engines put it, and the schedule
   forbids discharging the post-`E` inline (§1).  Then the two measured
   placements really do collide, §87.B's block STANDS, and **NOTHING IS
   LANDED**.  A second micro-ROM read is NOT taken, per the brief.
3. **W-1…W-4 select C1-B**: the `ucore` is RIGHT and the MODEL is wrong on this
   axis.  `mc1/721` is not a `ucore` defect, the five `PIN` seeds are re-routed
   to `sim/`, and **nothing is landed this sitting** — a model landing needs its
   own registration.
4. **C1-C, or a MIXTURE, or any bar unmet**: reported as registered, no verdict,
   nothing landed.

**In no branch does this sitting land a second micro-ROM read.**

---

## §3 CELL 2 — P1's TAKE CLOCK (`sw/w33_take_cell.py`)

§5.4a closed W3.2 with *"the measurement is circular on banked data"*, because
the only instrument for the take clock is an engine's own boundary clock and
every contested `wr1` entry lies AFTER that engine's first divergence.

**THE CIRCULARITY IS BROKEN BY THE POPULATION, NOT BY A NEW INSTRUMENT.**  The
30 retained `sm3-s24tfcell` captures are silicon on which **both engines are
EXACT — 0 row-diffs, all 30** (`standing_gates.md`).  On a capture where every
bus event agrees clock for clock, the engine's take clock IS a coordinate both
sides share.  So the cell's first leg is **OFFLINE and needs no board contact**:
it reads the take out of the engine's own trace (`+brktrace`'s `BRKT`;
`V30SIM_BRKTRACE`'s `BRKR … take=1`) and measures, per entry, `vec − take`,
every `CODE` T1 in the window, and the idle gaps.

### §3.1 THE CANDIDATES

* **T-A — the take is where the engines put it**, and it does NOT suspend the
  prefetcher.  Predicts `vec − take` INVARIANT across the pad walk and both
  waits, and `CODE` fetches PRESENT in the window on the cells that have queue
  room.
* **T-B — the take is EARLIER than the engines' boundary** (§5.4a's named,
  unchased candidate).  Predicts `vec − take` LARGER than the engines' own
  entry cost, and by a constant.
* **T-C — the take SUSPENDS the prefetcher** (§4.7's booked candidate, the one
  §5.4's v1/v2 landings were built on).  Predicts **ZERO** `CODE` T1s strictly
  between the take and the vector read, in every cell, at every wait.

### §3.2 THE BARS

* **T-1** the precondition is REPORTED per cell, never assumed: a cell counts
  only where the engine is exact on that capture.
* **T-2** the two engine legs must agree cell for cell.  They are different
  implementations of the same boundary; a disagreement voids the coordinate.
* **T-3** `vec − take`'s distribution and the `CODE`-in-window distribution are
  reported for all cells, at both waits, whatever they are.

### §3.3 THE BOARD ARM, AND WHEN IT IS TAKEN

Fresh captures of the same sleds are taken **only if T-1 fails on some cell**,
i.e. only if the retained population cannot carry the coordinate.  Re-capturing
sleds whose retained rows already answer the question buys nothing and spends
board time; that is stated here so that NOT contacting the board for cell 2 is
a registered decision and not an omission.

---

## §4 CELL 3 — THE TF FLOOR-CELL COMPOSITION CHECK

A BAR, not an investigation.  After anything this sitting lands, and on the
final tree:

* `sm3_tf_floor_cell.py score --core sim` — floor **3**, **121,890 rows,
  0 row-diffs**, EXACT on all 30, W-0a 0/18, W-1 30/30, W-2 {3} 22/22,
  W-3 [2,2]/[3,3], W-4 0·0, W-5 90/90.
* `sm3_tf_floor_cell.py score --core ucore` — depth **4**, **121,860 rows,
  0 row-diffs**, EXACT on all 30, W-1/W-2 {4} 22/22, W-3/W-4/W-5 as registered.

**Any movement in either is a hard failure of this sitting**, whatever else it
found.

---

## §5 THE `PIN` FIVE — THE DISPOSITION RULE

Written before the cell:

* if cell 1 returns **C1-A**, the five are ONE family — `mc1/721` — and their
  disposition is `mc1/721`'s: **L3, spec'd, awaiting the landing that the
  decision rule §2.5 does or does not authorize.**  They are re-labelled in the
  ledger from "three carry the signature" to **five of five**, which is a
  finding of this sitting and not a re-score of any gate.
* if cell 1 returns **C1-B**, the five are re-routed to `sim/` and the
  `ucore`'s own registered residue on `wr1` drops by five as a CLASSIFICATION
  change, with no engine edit and **no ratchet claimed**.
* `wr1/225009` and `wr1/215017` stay OUT of the family (§1) in every branch.

---

## §6 BOARD DISCIPLINE (CLAUDE.md), REGISTERED

* **Single-writer probed, not assumed**; **SOCKET ONLY**, `use_core=False`
  explicit (the board's CFG is sticky); `div_guard` PINNED and its readback
  RECORDED; the **FULL per-clock rows** retained beside the raw 64-bit words
  and their sha256; `board_idle()` at the end; **5 consecutive transport errors
  STOP the cell**; a wedge is a hard STOP.
* **NO FLASHING.**  The board carries FLASH #10 and this sitting does not
  change that.  Every `ucore` figure in this sitting is a Verilator figure.
* **The cell drives NO PIN AT ALL** — every arm is internal.  There is no
  `evt`, no hold, no `fired`, and none of INV-1's directive-truncation
  exposure.
* **The victory reserve (`k >= 300000`) is NOT touched.**
* Codex is NOT launched; no memory file is touched.

---

## §7 THE MUST-NOT-MOVE LADDER

If and only if something lands, the full ladder of `wrfuzz_provenance.md`
§4.6a is re-run on the final binary, both engines, plus `ss_lint`,
`ulockstep --golden all --cases 50`, `check_core --opcodes all`, the four HLT
sweeps, and G6 for an RTL leg.  **Ratchets are monotone: any column that goes
down is a failure of the landing, not a re-score.**  Nothing landed ⇒ the
ladder legs are VACUOUS and are reported as vacuous, never as green.
