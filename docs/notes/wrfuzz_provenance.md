# wrfuzz — PROVENANCE LEDGER (task #38, the random-wait fuzz campaign)

**Append-only.**  Nothing in this file is rewritten; a correction is an
ERRATUM box beside the original, never a replacement.  Plan:
`docs/notes/wrfuzz_campaign_plan.md`.  Pre-registration:
`docs/notes/wrfuzz_corpus_prereg_2026-08-05.md`.

> **WHY THIS FILE AND NOT `ucore_provenance.md` §89.**  The plan-doc precedent
> in this repository is one ledger per campaign beside one plan per campaign —
> `ucsim_campaign_plan.md` / `ucsim_provenance.md`, `ucsim_t_campaign_plan.md`
> / `ucsim_t_provenance.md`.  `ucore_provenance.md` is the ucore campaign's and
> then the silicon-match phase's ledger; it CLOSED at §88 with an accepted
> verdict on 2026-08-05, and appending a new campaign to a closed ledger makes
> the closure unreadable.  It is CITED here constantly and is not modified.
> A one-line successor pointer was appended to its foot so the trail is
> followable in both directions.

> **The standing principle, verbatim, because every sitting of this campaign
> is briefed with it:**
> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

---

## §1 W0 — CORPUS DESIGN AND PRE-REGISTRATION

**2026-08-05, branch `ucsim`, from HEAD `1a2a9eff4e`.  NO BOARD CONTACT.**

The opening sitting of the campaign the user directed on accepting the
silicon-match verdict.  Deliverables: the plan, the corpus design, the
generator extensions, the smoke proof, and the pre-registrations — all BEFORE
any generation at scale.

### §1.1 WHAT WAS BUILT

| artifact | what it is |
|---|---|
| `docs/notes/wrfuzz_campaign_plan.md` | the formal plan: the W0-W3+ skeleton, the governance carry-over, the stage gates, and **the victory-bar registration protocol** (the FORMULA registered now; the NUMBER computed from the survey at W2 and frozen there) |
| `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md` | the corpus: the five vector shapes, the 28 strata with their sizes and their k-blocks, the BRKEM-free mechanism, the exclusions, the eight capture-integrity bars, the board-time budget, the reserved victory tranche, and W2's deliverable shape |
| **`sw/wvec_shapes.py`** | NEW.  The per-access wait-vector axis: five shapes, the per-seed draw, the two ENGINE-SPECIFIC file writers, the round-trip check, `applied_score()` (the offline R0 statistic) and `bus_cycle_bound()` |
| `sw/fuzz_campaign.py` | the `wvec` and `no8080` axes; `compose_case()`; `scrub_brkem_image()` / `no_brkem_pairs()`; `wvec_of()`; the vector banked in full in the result line; `--force-fixed`; the `_lint_wvec` leg |
| `sw/gen_raw.py` | `scrub(buf, no8080=)` — the BRKEM pair added to the banned set, **both** bytes rewritten |
| `sw/fuzz_bank.py` | the banked entry carries `wvec` / `wvec_hex` / `wvec_sha256` / `wvec_n` / `no8080` |
| `sw/timed_fuzz.py` | `banked_wvec()` with its integrity limbs; `wait_args` / `tb_wait_args` emit the vector in each engine's OWN encoding; `wait_class()` — ONE definition of a stratum label, used by the stratifier and the report |
| `sw/ucsim_fuzz.py` | `regen()` moved onto `compose_case`, so the regeneration path and the capture path are ONE function |
| **`sw/wrfuzz_smoke.py`** | NEW.  The offline both-engine plumbing proof.  **NON-GATE by construction** — it caps its own population at 20 seeds and stamps `"nongate": true` into its report |

### §1.2 THE AXIS — WHAT THE RIG CAN EXPRESS, AND THE LIMIT

**Both rig paths can express per-access vectors at the lengths this campaign
needs, and the limit is ONE NUMBER: 4,096 bus cycles.**

* **the board** — `wvec_buf.sv` is 1024 × 32 bit = **4,096 entries**, read by
  `nec_bus.sv` at a **12-bit** `bus_idx`, armed by `WRAND.replay`, and applied
  by the SAME buffer to `use_core=0` and `use_core=1`.  §68.6 proved the index
  agreement DIRECTLY on this mechanism at **45,699 / 45,699 = 100.0 %** over
  186 captures, through `s10_board.capture(wvec=…)`'s passthrough.
* **the TB** — `+wvec` → `wvec_arr[0:4095]`, the same ordinal.
* **the model** — `--wvec` → `wvec_[bus_idx_]`, the same ordinal.

**It generalises to fuzz-length programs with ~4× headroom, and that is
measured, not argued.**  A capture is 4,200 clocks and a bus cycle is ≥ 4
clocks, so a run cannot exceed ~1,050 bus cycles; the W0 smoke's largest was
**728**.  It is still a BAR (**B-5**) because past 4,096 the three legs do
three different things: the board WRAPS, the TB reads 0 from its zero-filled
array, and the model falls back to the uniform level.

**THREE RIG PROPERTIES BOOKED AS DESIGN RULES** (prereg §1.1): always exactly
4,096 entries (the board's replay RAM is **not cleared between runs**, so a
short load leaves the previous run's tail for the chip to read); values 0…31
only (all three legs mask `[4:0]` identically, so a larger value is a false
statement in the ledger rather than a divergence); and the two engines' file
encodings are **different and the mismatch is silent** — see F-3.

### §1.3 THE NUMBERS — EVERY ONE MEASURED THIS SITTING

**Non-regression.  The two standing legs that this sitting's edits could have
moved were re-run, and both are UNMOVED at their registered values.**

| leg | registered | **measured this sitting** |
|---|---|---|
| `timed_fuzz.py --pop reg` (the model) | 1,338 / 1,702 | **1,338 / 1,702 (78.6 %)**, OPEN_BUS 375, ENGINE ABORTS 0 |
| `timed_fuzz.py --core ucore --pop reg` | 1,557 / 1,702 | **1,557 / 1,702 (91.5 %)**, OPEN_BUS 375, **BOUND WARNINGS 4**, ENGINE ABORTS 0, TB receipt `cede73e73a318753…` |

**Regeneration — the invariant that actually matters.**  Adding the two axes
must not move one byte of any image banked before them:

| population | result |
|---|---|
| 300 seeds sampled across `mc1` / `mc2` / `t30-raw` / `t30-brkem` | **0 GEN_DRIFT, 0 REGEN_ERROR** |
| the whole b2 victory tranche (216 seeds) | **0 GEN_DRIFT** |
| `compose_case(g, cfg)` vs `check_seq.compose(g)` with every axis off, 50 soup + 50 raw | **byte-identical, 100 / 100** |

**The `cfg_hash` rule, and its own falsifier.**  The two axes are added to the
hashed config **only when set**, so a config with the axis off hashes exactly
as it did before task #38 and a config with a vector spec hashes differently
from every other.  Measured: `off / uni / walk / no8080` give **four distinct
hashes**; the axis-off hash equals the pre-task-#38 formula's on **400 / 400**
sampled banked seeds.  ⚠ *The rule's falsifier is written beside it in the
code*: an axis whose default is a CHOICE rather than an absence must be added
UNCONDITIONALLY, or two genuinely different configurations collide.

**The BRKEM mechanism, measured on the artifact.**

| measurement | result |
|---|---|
| soup, `p_brkem = 0`, image pass OFF | **118 `0F FF` pairs in 114 of 1,500 seeds (7.6 %)** |
| soup, the full mechanism | **0 pairs** |
| raw, the generator scrub ON, image pass suppressed | **0 residual pairs in 400 composed images** |
| raw lint, 300 seeds | `scrub_totals` `brkem = 197` (and `pair0f 2862`, `halt 52572`, `poll 53172`) |
| soup lint, 300 seeds, `--no8080` | `brkem = 0` seeds |

**The lint.**  `sw/wvec_shapes.py lint --n 120`: **0 hits**, with 120 / 99 /
113 / 110 / 120 distinct vectors per shape over 120 seeds (the
stratum-degeneracy check).  `fuzz_campaign.py lint --n 300 --raw-n 300
--wvec-n 60 --no8080`: **PASS, 0 hits on all three legs.**  The full-scale
standing form (`--n 10000 --raw-n 100000 --wvec-n 400 --no8080`) was launched
and its result is recorded at §1.5.
⚠ Reminder booked at §72.7a → §73.10 and restated in the code: **there is no
hang** — `--report-every` defaults to 0 and the raw phase is 100,000 seeds at
~59 seeds/s ≈ 28 minutes with nothing on stdout.

**THE SMOKE — the whole path, both engines, offline, no board.**

`python3 sw/wrfuzz_smoke.py --cid wrsmoke --n 20 --core ucore`, report
`sw/testdata/wrfuzz/smoke_w0.json`.  Population: 20 seeds, `--no8080`,
`--no-evt`, all five shapes, both tiers.

| the bar | **measured** |
|---|---|
| the vector was APPLIED, model leg | **5,223 / 5,223 = 100.00 %** |
| the vector was APPLIED, `ucore` leg | **4,809 / 4,809 = 100.00 %** |
| engine errors | **0 / 0** |
| bus-cycle bound (< 4,096) | **OK — largest capture 728 cycles** |
| `0F FF` pairs in the composed images | **0** |
| shapes exercised | `burst` 5 · `edge` 4 · `walk` 4 · `uni` 4 · `skew` 3 |
| tiers exercised | soup 16 · raw 4 |
| `nmax_eff` actually taken | {24, 26, 40, 45, 53, 64} — the vector's MEAN cost driving the capture budget, as designed |

**WHAT THE 100.00 % IS AND IS NOT.**  It is the offline analogue of §68.6's
bar R0 — *the waits the engine took, read off its own pin rows, are the waits
the vector asked for* — and it is what proves **generation → vector application
→ scoring** end to end in both engines.  It is **NOT** a measurement of
silicon, **NOT** a comparison of the two engines, and **NOT** citable as a
ratchet; the report stamps `"nongate": true` and the harness refuses a
population above 20 seeds.

⚠ **The two denominators are DIFFERENT (5,223 vs 4,809) and that is not a
defect.**  Each engine's score is over the cycles THAT ENGINE ran, and the two
engines disagree on the bus-cycle count of **5 of the 20 seeds** — `wrsmoke/2`
728 vs 336, `wrsmoke/19` 574 vs 555, `wrsmoke/1` 668 vs 665, `wrsmoke/15` 675
vs 673, `wrsmoke/6` 167 vs 169 (four raw, one soup).  That is an engine
divergence, i.e. the sort of thing this campaign exists to survey; it is
recorded as an OBSERVATION and nothing is concluded from five seeds.

### §1.4 W0's OWN FINDINGS

**F-1 — a PRE-EXISTING `cfg_hash` provenance drift, ATTRIBUTED BY MEASUREMENT
AND NOT BY ARGUMENT.**  Of 400 banked seeds sampled across all four banks, only
**156 re-derive their stored `cfg_hash`**.  The obvious suspicion is that
task #38 caused it.  It did not: the **pre-task-#38 key set**, computed by hand
on the same 400 seeds, reproduces the **identical 156**.  The cause is that the
hashed key set grew (`fence` at task #32, `mainline`) after those seeds were
banked.  **Nothing gates on `cfg_hash`** — it is provenance and part of a
banked FILENAME, and no tool re-derives and compares it (`check_fuzz_bank`
passes the stored value through into `Ctx`).  The thing everything does gate on
— the IMAGE — regenerates at 300/300 and 216/216.  **Booked, not fixed**; a
"fix" would be to re-hash 3,242 banked filenames for a field nobody reads.

**F-2 — the BRKEM knob alone is not the mechanism.**  `p_brkem = 0` still
leaves a `0F FF` byte pair in **7.6 %** of soup seeds, from an immediate byte
meeting the next opcode.  This is `ucore_provenance.md` §63.5's own observation
approached from the other side (18 of its 42 knob-off class-A seeds carried
such a pair), and it is why the mechanism is three places — the knob, the raw
generator's in-context scrub, and one pass over the composed image.
⚠ And it is why the prereg says in terms that this makes a corpus **BRKEM-free,
NOT 8080-free**: §63.5's other 24 class-A seeds have no `0F FF` at all and
their entry path is still not established.

**F-3 — the DECIMAL/HEX asymmetry between the two engines' vector files is a
live, silent trap.**  `hdl/tb/tb_v30_core.sv` reads `+wvec` with `$readmemh`;
`sim/timed_runner.cpp:404` reads `--wvec` with `fscanf("%d")`.  Hand a TB file
to the model and `1f` parses as `1`, the next `%d` fails on `f`, the read loop
**stops**, and the model runs a silently truncated vector under the uniform
level.  Nothing in the tree diagnoses it.  It has never fired because the only
two consumers (`timed_wvec_gate`, `sm3_h3_cell`) each wrote their own file
inline — a shared writer would have hit it on the first vector containing a
value ≥ 10, which every `uni`, `edge`, `burst` and most `skew` vectors do.
**Now guarded**: `wvec_shapes.write_tb` and `write_sim` are separate named
functions, and `check_encodings()` proves on every lint that they round-trip to
the same list **and** are different text whenever a value ≥ 10 is present — so
the guard fails loudly if either writer is ever changed to match the other.

**F-4 — THE VACUOUS-INSTRUMENT PATTERN, IN THIS SITTING'S OWN TOOL, CAUGHT
BEFORE ITS NUMBER WAS QUOTED ANYWHERE.**

`wrfuzz_smoke.py`'s first version reached the RTL through
`check_seq.run_tb(image, nrows, wvec=…)`, on the stated rationale that it would
then *"exercise the same code the campaign's TB captures will."*  But
**`check_seq.CORE` is `"fsm"`**, pinned there deliberately (`check_seq.py`
§60-63: every gate that reaches the TB through it — `check_fuzz_bank`,
`check_mod3_illegal`, `check_enter_nesting` — is an ARCHIVED on-demand gate
whose registered figures are FSM figures, so *"migrating the plumbing must not
move a number"*).  So the harness:

* asserted the **`ucore`'s** receipt (`art.require(tf.tb_bin("ucore"))`),
* **printed** the `ucore`'s receipt `cede73e73a318753…` on its own banner,
* and then ran the **ARCHIVED FSM CORE** on every seed.

**How it was caught**: `git status` showed `sw/testdata/receipts/verilator_binary.jsonl`
had grown by one line, and the new receipt's label was **`tb_v30_core/fsm`** —
a binary nothing in the sitting had asked to build.  *The receipt layer caught
it, which is what it is for.*

**What it cost, measured**: the FSM leg scored **3,538 / 3,538** applied cycles
and the corrected `ucore` leg scores **4,809 / 4,809** — a 36 % different
denominator, because the FSM core diverges much earlier on the raw seeds
(`wrsmoke/19`: 72 bus cycles on the FSM, **554** on the `ucore`).  **Both are
100.00 %**, so the BAR would have passed either way and the defect would have
survived into W1 as a label on a number.

**The fix, and why it is not just a different call**: `run_tb` now invokes
`tf.tb_bin(core)` DIRECTLY, and `main()` carries a **postcondition asserting
that the binary path it is about to run is the one the `--core` flag named**.
`.exists()` is the test the whole vacuous-gate pattern passes; naming the
binary the runner actually invokes is the one it does not.

⚠ **NOT NUMBERED in `standing_gates.md`'s incarnation count, and the reason is
stated rather than left implicit** (the §87.C.1 lesson): the count enumerates
GATES that ran against bytes nobody proved, and `wrfuzz_smoke` is not a gate,
never was, and was corrected in the sitting that wrote it before any number
left this ledger.  It is recorded here at full length because the pattern is
the project's most repeated failure and a near miss is evidence about it.

**AND IT LEAVES A LIVE TRAP FOR THIS CAMPAIGN, BOOKED HERE**:
`fuzz_campaign.capture_tb` — the `--tb-only` leg — also reaches the TB through
`check_seq.run_tb`, so **`fuzz_campaign run <cid> --tb-only` runs the FSM
core**, whatever anybody assumes.  That is correct and deliberate for the
archived gates it was pinned for, and `check_seq.CORE` is **NOT** changed here.
W1's comparator is the BOARD (chip vs fabric), so the campaign does not depend
on it — but no wrfuzz number may be taken from a `--tb-only` run and called an
`ucore` number.

### §1.5 THE FULL-SCALE LINT

`python3 sw/fuzz_campaign.py lint --cid wrlint --n 10000 --raw-n 100000
--wvec-n 400 --no8080 --report-every 20000`

| leg | result |
|---|---|
| soup, 10,000 seeds | **hits 0, compose_err 0** (`wild` 1486, `brkem` **0**, `halt` 1806, `tf` 570), 22.3 s |
| raw, 100,000 seeds | *(recorded at the sitting's close — see the RESULT line below)* |
| wvec, 400 seeds × 2 tiers × 5 shapes | *(same)* |

> **RESULT** — see `§1.5 CLOSE` appended below when the run completed.

### §1.6 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT.**  No `v30ctl`, no `s10_board`/`s13_board`, no serve
  session, no `div_guard`, no `board_idle` — because nothing was opened.
* **No generation at scale.**  The largest population built is the 20-seed
  smoke, and it is NON-GATE.
* **Nothing landed in either engine.**  `git diff` over `hdl/` and `sim/` is
  EMPTY; no save-state address moved, no `SS_VERSION` bump, no Quartus run,
  no flashing.
* **No mechanism was proposed, diagnosed or refuted.**  H3-B re-enters SCOPE;
  it was not opened.
* **No memory file was touched and Codex was not launched** — the coordinator
  routes this package.
* **No standing gate was re-registered.**  The two legs re-run are reported at
  their existing registered values and no ratchet moved.
