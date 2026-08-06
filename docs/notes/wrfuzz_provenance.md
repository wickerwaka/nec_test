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
three different things: the board WRAPS, the model falls back to the uniform
level, and the TB performs an **out-of-range read** of `wvec_arr[0:4095]` whose
value the language does not define (the zero-fill covers 0…4095 and is the
answer to a SHORT vector, which is a different question).

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

### §1.5 THE FULL-SCALE LINT — **PASS**

`python3 sw/fuzz_campaign.py lint --cid wrlint --n 10000 --raw-n 100000
--wvec-n 400 --no8080 --report-every 25000`

**Run against the FINAL code state.**  An earlier run of the same command was
in flight when one module-level constant was moved; it was RESTARTED rather
than quoted, so this result describes the committed bytes and not a state one
edit behind them.  (The abandoned run was clean through 40,000 raw seeds.)

| leg | result |
|---|---|
| soup, 10,000 seeds | **hits 0, compose_err 0** — `wild` 1,486, **`brkem` 0**, `halt` 1,806, `tf` 570; 21.0 s |
| raw, 100,000 seeds | **hits 0, compose_err 0** — `whole` 70,188 / `payload` 29,812; `scrub_totals` `pair0f` 984,539 · `halt` 17,970,307 · `poll` 17,973,935 · **`brkem` 70,578**; 1,405.3 s at 71 seeds/s |
| wvec, 400 seeds × 2 tiers × 5 shapes | **hits 0**; 56.0 s |

> **`LINT PASS: soup hits=0 compose_err=0; raw hits=0 compose_err=0;
> wvec hits=0`**

**`brkem = 70,578`** is the new axis doing visible work: across 100,000 raw
images the scrub removed seventy thousand `0F FF` pairs that the previous
default deliberately left in (`gen_raw`'s docstring: *"other 0F >= 0x40 — LEFT
IN: they alias BRKEM"*).  That is the raw-tier counterpart to §1.4 F-2's 7.6 %
on soup, and between them they are why the mechanism is three places.

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

---

## §2 W1 — THE SOCKET CAPTURE

**2026-08-06, branch `ucsim`, from HEAD `4665a04e64`.  ONE BOARD SITTING, NO
FLASHING.**  Execution note (the deviations, committed before board contact):
`docs/notes/wrfuzz_w1_execution_note_2026-08-05.md`.
Driver: `sw/wrfuzz_w1.py`.  Campaign `cid = wr1`.

W1 **measures and reports; it does not diagnose.**  Its bars are the
pre-registration's B-1 … B-9 and nothing else.  **No engine-versus-silicon rate
is computed or quoted here, and no family census was run** — the survey is W2's
and this sitting does not pre-empt it.

### §2.1 THE HEADLINE

> **3,150 / 3,150 seeds captured, all 28 strata at their registered size, in
> 6.4 minutes of board time.  B-1 … B-9 are 9 / 9 MET.  Total board time
> 7.6 minutes against a registered bound of ≤ 30.  0 transport errors,
> 0 quarantines, 0 provenance alarms, no wedge, `div_guard` PINNED on 33 / 33
> probes, `board_idle()` clean and `use_core=0` left selected.**

### §2.2 THE PRE-FLIGHT

**Offline first, and committed before the board was touched** (commit
`4665a04e64`).

| check | result |
|---|---|
| **single writer** | board reachable, `up 24 days`; **no `v30`/serve process on the board**, no local serve client.  ⚠ The FIRST pass reported a violation and it was the probe **matching its own command line** — `pgrep -af 'v30ctl.py serve'` inside `bash -lc`.  `[v]30ctl` now.  That is the self-matching-`pgrep` lesson (task #29 P7) arriving in a LIVENESS check rather than in a watcher, and it is recorded because a single-writer probe that can report a false positive can also report a false negative |
| **era** | complete and NAMED, not asserted — FLASH #10 `1a01a6975e4aca6f…` `verify OK`, the quartus receipt whose OUTPUT is that `.sof` (`a2d605a47f61af37…`, *"SM3 s27 FLASH#10 RETENTION build"*), RTL input manifest **88 files `42752f3a57483002…`**, `gen_git 4665a04e64`, `RIG_EVT_HOLD_BITS 12` |
| **generation + REGENERATION** | 168 seeds (6 per stratum, all 28): **hits = 0**.  0 gen-drift, **0 `0F FF` pairs**, 0 evt, tier and wait source correct in every stratum, every vector exactly 4,096 entries in [0,31] and distinct per seed |
| **board health** | `check_ab_hw all 187`: **chip-vs-golden MATCH over 187 rows, core-vs-chip MATCH, core-vs-golden MATCH**.  `div_guard` PINNED both ends |

### §2.3 THE CAPTURE — PER STRATUM, AS REGISTERED

Each seed is one `capture_board` call: the socketed chip (`use_core=0`) then
the fabric core (`use_core=1`), same image, same vector, same bitstream,
differing in the A/B select and in nothing else.

| i | tier | source | k range | n | **captured** |
|---|---|---|---|---|---|
| 0 | soup | `fix0` | 200000-200149 | 150 | **150** |
| 1 | soup | `fix1` | 201000-201149 | 150 | **150** |
| 2 | soup | `fix2` | 202000-202149 | 150 | **150** |
| 3 | soup | `fix3` | 203000-203149 | 150 | **150** |
| 4 | soup | `wrand1` | 204000-204149 | 150 | **150** |
| 5 | soup | `wrand2` | 205000-205149 | 150 | **150** |
| 6 | soup | `wrand3` | 206000-206149 | 150 | **150** |
| 7 | soup | `wrand7` | 207000-207149 | 150 | **150** |
| 8 | soup | `wrand15` | 208000-208149 | 150 | **150** |
| 9 | soup | `wvec-uni` | 209000-209149 | 150 | **150** |
| 10 | soup | `wvec-walk` | 210000-210149 | 150 | **150** |
| 11 | soup | `wvec-skew` | 211000-211149 | 150 | **150** |
| 12 | soup | `wvec-burst` | 212000-212149 | 150 | **150** |
| 13 | soup | `wvec-edge` | 213000-213149 | 150 | **150** |
| 14 | raw | `fix0` | 214000-214074 | 75 | **75** |
| 15 | raw | `fix1` | 215000-215074 | 75 | **75** |
| 16 | raw | `fix2` | 216000-216074 | 75 | **75** |
| 17 | raw | `fix3` | 217000-217074 | 75 | **75** |
| 18 | raw | `wrand1` | 218000-218074 | 75 | **75** |
| 19 | raw | `wrand2` | 219000-219074 | 75 | **75** |
| 20 | raw | `wrand3` | 220000-220074 | 75 | **75** |
| 21 | raw | `wrand7` | 221000-221074 | 75 | **75** |
| 22 | raw | `wrand15` | 222000-222074 | 75 | **75** |
| 23 | raw | `wvec-uni` | 223000-223074 | 75 | **75** |
| 24 | raw | `wvec-walk` | 224000-224074 | 75 | **75** |
| 25 | raw | `wvec-skew` | 225000-225074 | 75 | **75** |
| 26 | raw | `wvec-burst` | 226000-226074 | 75 | **75** |
| 27 | raw | `wvec-edge` | 227000-227074 | 75 | **75** |
| | | | | **3,150** | **3,150** |

**MEASURED RATES, by stratum class** (`sw/testdata/wrfuzz/w1_capture.json`):
soup control **10.5-10.9 seeds/s**, soup `wvec` **7.6-8.4**, raw control
**6.2-7.5**, raw `wvec` **5.2-6.0**.  **The vector costs about 30 %**, and it
is the 4,096-byte `WVEC` load the transport sends twice per seed (once per A/B
position) — the rig is not asked to do anything else new.  The budget assumed a
1.5×-derated **4.0 seeds/s**; the slowest stratum in the corpus beat it by 30 %.

### §2.4 THE BARS — **9 / 9 MET**

`sw/testdata/wrfuzz/w1_bars.json`.  Each is a STOP, not a tolerance; none fired.

| bar | registered | **measured** | verdict |
|---|---|---|---|
| **B-1** THE VECTOR WAS APPLIED | ≥ 99.9 %, expectation **100.0 %** | **48,042 / 48,042 = 100.0000 %** over **127 retained socket captures**; 0 captures with a miss, 0 sha mismatches | **MET**, *and at the expectation* — **no finding** |
| **B-2** ERA | 0 absent or mixed | **1 distinct era over 3,150 lines**, 0 absent, 0 incomplete, 0 `build_stale`, one `gen_git` | **MET** |
| **B-3** VECTOR BANKED IN FULL | 0 mismatches | **1,125 vector seeds**; 0 without `wvec_hex`, 0 bad length, 0 bad sha256, **0 re-derive mismatches** | **MET** |
| **B-4** NO GEN-DRIFT | 0 / 0 | **3,150 images regenerated from `(cid, k, ov)`: 0 GEN_DRIFT, 0 REGEN_ERROR** | **MET** |
| **B-5** BUS-CYCLE BOUND | 0 at or beyond 4,096 | **3,150 / 3,150 captures scored**, max **1,010**, p95 **673**, **0 at or over** | **MET** |
| **B-6** BRKEM-FREE | 0 pairs | **0 `0F FF` pairs over 3,150 composed images** | **MET** |
| **B-7** BOARD DISCIPLINE | PINNED on 100 % of probes | **33 / 33 `div_guard` readbacks PINNED** (`div=8`, 4 MHz, commanded by the connection), 0 UNPINNED; `use_core=0` left selected | **MET** |
| **B-8** TRANSPORT | breaker not tripped; errors REPORTED | **0 quarantines, 0 run-errors, 0 provenance alarms, 0 B-9 errors**; no consecutive-quarantine run; no halt | **MET** |
| **B-9** CAPTURE IS STABLE | **158 / 158** stable | **158 / 158 stable**, 0 unstable, 0 errors, **0 QS-flicker rows**, over 474 seed-loops (3 fresh reps × both A/B legs = 4 comparisons per seed) | **MET** |

**B-5, read rather than merely passed.**  The registered concern is that past
4,096 bus cycles the three legs do three different things.  The board cannot
get there: `v30ctl.CAP_RECORDS` is 4,096 **clock** records and a bus cycle is
at least 4 clocks, so a socket capture is structurally capped near ~1,024 — the
measured max is **1,010**, which is that cap and not a property of the corpus.
This was written into the execution note **before** the run so the number could
not be read as a discovery.  **⚠ It does NOT generalise to the offline
engines**, which have no such buffer: W0's smoke reached 728 cycles and W2's
replays are not bounded by the rig.

**B-1, and why 127 captures is the registered sample and not a shortfall.**
The bar is scored over *"every capture whose rows are retained"* — every
divergent seed plus the SUCCESS ballast — and it costs no board time because it
is read off rows already banked.  380 corpus captures were retained, **127** of
them carry a vector; the registered expectation was ≥ 20,000 bus cycles and the
measurement is **48,042**.  The sample is unbiased with respect to what it
measures: the rig applies the vector before any engine has an answer.

### §2.5 WHAT WAS BANKED

| artifact | content |
|---|---|
| `sw/testdata/campaigns/wr1/results.jsonl` | **3,150 lines**, one per seed, each carrying the vector **in full** (`wvec_hex`, 8,192 chars), its sha256, the era stamp, and the capture's own `bus_cycles` |
| `sw/testdata/campaigns/wr1/captures/` | **380 retained full per-clock row pairs** (divergent + the stratified SUCCESS ballast), 17.7 MB |
| `sw/testdata/campaigns/wr1/captures/b9/` | **158 B-9 row files**, each holding **all three repetitions of both legs**, 18.6 MB, with `SHA256SUMS` |
| `sw/testdata/wrfuzz/w1_{preflight,capture,b9,bars,idle}.json` | the session records: div_guard readbacks, per-stratum timings, the B-9 per-seed cells, the scored bars |
| `sw/testdata/wrfuzz/w1_sha256_manifest.txt` | **545 files**, sha256 each — the retention rule (full rows + sha256, never digests alone) made checkable |

The loose captures are `.gitignore`d exactly as `mc1`/`mc2`'s are; the sha256
manifest, the results and the session records are committed.

### §2.6 W1's OWN FINDINGS

**F-5 — THE SINGLE-WRITER PROBE MATCHED ITSELF, AND IT WAS CAUGHT BY ITS OWN
FALSE POSITIVE.**  `pgrep -af 'v30ctl.py serve'` run through `bash -lc` matches
the `bash -lc` process carrying the pattern, so the very first pre-flight
declared a single-writer VIOLATION that did not exist.  Fixed to `[v]30ctl`.
Recorded at length for the same reason §1.4's F-4 was: **the probe reported a
violation that was not there, which means the same construction could have
reported an all-clear that was not there either** — the direction of a false
result is an accident of what was running, not a property of the check.  It is
the task #29 P7 self-matching-`pgrep` lesson, arriving in a liveness check.

**F-6 — THE VECTOR AXIS COSTS ABOUT 30 % OF CAPTURE THROUGHPUT, AND IT IS THE
TRANSPORT, NOT THE PART.**  Measured, not inferred: the control strata run at
10.5-10.9 seeds/s on soup and the `wvec` strata at 7.6-8.4 with everything else
held equal; on raw, 6.2-7.5 against 5.2-6.0.  The difference is the 4,096-byte
`WVEC` base64 load, sent **twice per seed** because `run_image` re-arms replay
for each A/B position and `v30ctl.load_wvec` writes what it is given.  Booked
as a fact about the RIG's cost model, **not fixed** — the obvious "optimisation"
(skip the load when the vector has not changed) would make the board's
NOT-CLEARED replay RAM (`wvec_shapes` property 3) load-bearing, which is
exactly the hazard that rule exists to keep out of the capture path.

**F-7 — B-9 FOUND ZERO INSTABILITY *AND* ZERO QS FLICKER, WHICH IS STRONGER
THAN THE BAR ASKED FOR.**  The registered comparator is
`fuzz_classify.diff_rows`' own policy, which TOLERATES the 1-cycle F↔S
queue-status flicker as cosmetic; the bar would have been met with any number
of flicker rows.  Over 158 seeds × 3 repetitions × 2 legs = **632 row
comparisons**, the flicker count is **0**.  Under a brand-new wait axis, with
`burst` putting single waits of 16/24/31 clocks on one access in 29-53 and
`skew` holding a level for blocks of 16-32 accesses, the socket repeats itself
**exactly**.  §81.B's 193/193 deterministic over 1,089 captures now has a
random-wait-vector counterpart, measured rather than inherited.

### §2.7 WHAT THIS SITTING DID NOT DO

* **NO FLASHING.**  FLASH #10 is resident and is what every capture is stamped
  with.  `--allow-stale` was never passed.
* **No survey.**  No family census, **no engine-vs-silicon rate computed or
  quoted**, no `S`, no residue partition, no class-A count, no H3-B statistic.
  All of that is W2's and this sitting deliberately leaves it untouched — the
  classifier's inline verdict counter is banked in `results.jsonl` because the
  capture path produces it, and **its interpretation is W2's, not W1's**.
* **No `--tb-only` run**, anywhere.  F-4's trap (`check_seq.CORE` pinned to
  `fsm`) is live and W1's comparator is the board.
* **No standing gate moved and no ratchet was re-registered.**
  `standing_gates.md` is untouched at W1 by design.
* **Nothing landed in either engine.**  `git diff` over `hdl/` and `sim/` is
  EMPTY.
* **No memory file was touched and Codex was not launched** — the coordinator
  routes this package.

---

## §3 W2 — THE SURVEY

**2026-08-05, branch `ucsim`, from HEAD `b8020d0229`.  OFFLINE, NO BOARD
CONTACT, NOTHING LANDED.**  Census document:
`docs/notes/wrfuzz_survey_2026-08-05.md`.  Driver: `sw/wrfuzz_w2.py`.

W2 **scores, counts, partitions and freezes.**  It plans no fix, proposes no
mechanism as settled and moves no ratchet.  Its deliverable shape is the
pre-registration's §7, item for item.

### §3.1 THE HEADLINE

> **3,150 seeds scored hardware-versus-silicon.  635 excluded by the
> pre-registered OPEN_BUS detector, 2,515 SCORED, 2,379 cycle-exact
> (94.59 % pooled).  `S` = the unweighted mean of the 28 per-stratum rates =
> 91.6681 %, and `B = S − 5.0 = 86.6681 %` — BOTH FROZEN.  The victory tranche
> is drawn and frozen at sha256 `dcaa48fa991f…`.**
>
> **The residue is 136 seeds and 75 of them — 55 % — carry the single-step
> (TF) trap axis, which is 3.5 % of the scored corpus.**  Seeds with it fail at
> **84.3 %**; seeds without it at **2.51 %**.  With the axis removed thirteen of
> the fourteen soup strata are 98.6-100.0 % and the soup residue is **seven
> seeds**.

### §3.2 THE THREE COMPARATORS AND WHAT EACH WAS TOLD

| leg | told | population | result |
|---|---|---|---|
| **HW-vs-SILICON** — `ucore` in fabric vs the socketed chip, A/B differing only in `use_core` | nothing; it runs the image under the vector | **3,150** | **2,379 / 2,515 scored** |
| chip-vs-model, offline | the same image and the same 4,096-entry vector (decimal) | the **380 retained captures**, 184 offline-scored | 48 / 184 |
| chip-vs-`ucore`-TB, offline | the same, hex encoding | the same 184 | 49 / 184 |

⚠ **The 380 is DIVERGENT BY CONSTRUCTION** (every miss plus a SUCCESS ballast),
so the two offline figures are **attribution only** — the pre-registration's own
words — and are never quoted as a silicon-match rate or used to rank the two
engines.  Cross-engine partition over the 184: **model-shared 130,
`ucore`-only 5, model-only ≥ 6** (the `ucore`-only column is COMPLETE because
every fabric miss has its rows retained; the model-only column is a FLOOR).

### §3.3 THE FAMILY CENSUS

`ucore` **in fabric**, 136 scored misses / 135 classified: `PF_LOST` **43** ·
`SCHEDULE` **42** · `DATA_SEQ` **23** · `PF_GAINED` **18** · `PIN` **7** ·
`PF_ADDR` **2**; `TAIL_EXTRA` / `TAIL_MISS` **0**; **catch-all EMPTY**.
The `ucore` in the Verilator TB gives the **identical** table, cell for cell.
The model's own divergence set is 136: `SCHEDULE` 50 · `PF_LOST` 49 ·
`DATA_SEQ` 17 · `PF_GAINED` 15 · `PIN` 3 · `PF_ADDR` 2.

**Instrument agreement, measured: fabric and `tb_v30_core` reach the same
verdict on 182 / 184** — and **INTA rows are 0 over 380 retained captures**, so
§56's fabric-float class has no members in an evt-free corpus.  **Plan §4's
registered risk #4 is answered by measurement and the answer is a negative.**

### §3.4 THE SURVEY'S OWN FINDINGS

**F-8 — THE PRE-REGISTERED OPEN_BUS EXCLUSION IS NOT THE ONE THE BANK LABELS
WITH, AND THE DIFFERENCE IS 1.7 POINTS OF `S`.**  `fuzz_classify.classify`
consults the accept engine only inside the branches a divergence reaches, so
**a SUCCESS seed can never carry `KNOWN_ACCEPTED/open_bus`** — excluding on that
label removes open-bus MISSES and keeps open-bus EXACTS, an exclusion whose
membership depends on the answer.  The registered detector
(`_open_bus_escaped_before`) was evaluated on all 3,150 through the capture
path's own banked `ob_escape.feed` counter, validated against the row-level
detector at **259 / 260** on the retained raw captures and **0 / 120** false
fires on soup.  `S` is computed under the registered detector — **91.6681 %**,
against 94.9107 % under the label.  **The costlier one is the one used.**

**F-9 — W1's RETENTION POLICY CANNOT SUPPORT A ROW PREDICATE OVER THE
POPULATION.**  Rows exist for 380 of 3,150.  That is exactly enough for the
family census (**every non-exact seed's rows are on disk, 320 of 320**) and not
enough for any predicate that must be evaluated on a SUCCESS seed.  F-8's
exclusion survived only because the capture path happened to bank the counters
it needed.  **BOOKED, not fixed**: retain all rows, or bank the predicates the
survey will need, at capture time.

**F-10 — THE CONTROL STRATA CANNOT BE CHECKED AGAINST A REMEMBERED NUMBER, AND
BOTH CANDIDATE CONTROLS FAIL BY MEASUREMENT.**  (a) The promoted bank's
per-wait-class column is a SELECTION artefact — re-measured this sitting it is
**100.0 % on six of nine soup classes** beside `fix0` at 65.8 %, which is what
`fuzz_bank.promote`'s caps left behind and not a population rate.  (b) The
mc1 / mc2 / t30 campaigns' full populations carry **no era stamp at all**
(0 of 20,203 lines; `wr1` is the first campaign with one, B-2's own gate), so
their fabric leg is a core and a bitstream nothing records.  **`wr1`'s nine
control strata are therefore the FIRST unbiased, era-stamped, per-wait-class
population measurement of the resident era**, and the reproduction check the
work order asked for returns a NEGATIVE.  No delta against either candidate is
computed anywhere.

**F-11 — A BRKEM-FREE CORPUS LANDED IN 8080 MODE 12 TIMES.**  B-6 measured
**0 `0F FF` pairs over 3,150 composed images** and §63.5's class-A criterion
still fires on **12 of 136 scored misses**, all raw tier.  This is W0's F-2 and
prereg §3.3 arriving as a measurement: *a BRKEM-free corpus is not an 8080-free
corpus*, and §63.5's other 24 class-A seeds' entry path is still not
established.  As a share of the residue the class has fallen from **41 %**
(92 of 222, banked corpus) to **8.8 %**.  **COUNTED, REPORTED, LEFT IN THE
DENOMINATOR** — 8080 is DEFERRED BY USER DECISION and is not filtered.
**ROUTED to W3 as a GENERATOR question**, not a core question.

**F-12 — THE VACUOUS-INSTRUMENT PATTERN, AGAIN, IN THIS SITTING's OWN `8F`
MOD-3 COUNTER.**  The first criterion scanned the composed image for the byte
pair `8F`, `mod == 3` and reported **2,951 of 3,150 seeds** — a 64 KB image
with random fill contains the pair by chance almost always.  The number is
recorded and **labelled VACUOUS in the tool's own output**; the count that is
quoted is the execution-based one (the form in flight at the first divergence),
which is **0** — two seeds carry an `8F` form and both are the memory form.
⚠ Not numbered in `standing_gates.md`'s incarnation count: it is a survey
counter, never a gate, and it was labelled in the sitting that wrote it.

### §3.5 THE INVARIANT THAT SHAPES W3, AND ITS OWN CONTROL

`PF_GAINED` is **18 seeds with one geometry**: signature `bs PASV!=CODE`
18/18; the chip's cell at the contested slot **`MEMR 00004`** — interrupt
vector 1, the single-step vector — 18/18; the engine's cell `CODE 005xx` 18/18;
enclosing chip cycle `IDLE` at offset **+1** 18/18; `delta ∈ {−6,−5,−4}`;
recovery a single extra `CODE` on 16/18; `has_tf` **True on 18 of 18**.
**30 of `PF_LOST`'s 43 are the same event with the owners swapped.**  Across
the classified residue **64 of 135** have `MEMR 00004` at the contested slot.

**KNOWN SIGNATURE, NEW EXPOSURE.**  Re-censused this sitting, **8 of the old
bank's 145** registered `ucore` residue seeds carry the same cell and **both**
of that bank's two `PF_GAINED` members are this exact shape.  What is new is
the population: the banked corpus is promotion-selected and `wr1` is the first
whole-stratum capture.  The settled law nearest it — **partition B1, the BRK/TF
trap — is LANDED and its floor cell is EXACT at depth 4**; this survey does not
contradict it, because the floor cell walks the recognition depth and never
interleaves the entry with a live prefetch.

⚠ **AND IT IS NOT A WAIT-AXIS EFFECT**: at `fix0` the TF seeds already fail
**6 of 7**.  ⚠ **`soup/wvec-edge` is 5/5 exact on its TF seeds** where every
other soup stratum is 9 of 84 — and its length confound has a **matched control
inside the corpus**: `soup/wrand15` has the same median `n_ins` (24), the same
`nmax_eff` (24) and the same median bus-cycle count (146 vs 145), and is
**0 / 6** (Fisher p = 0.0022).  The one thing separating them is that
`wrand15` takes intermediate wait lengths and `edge` (`{0,1,30,31}`) never
does.  **Registered as a HYPOTHESIS with its falsifier**, not as a law — see
the census §4.5.

### §3.6 THE AXIS's OWN VERDICT — REPORTED AS A NEGATIVE

The plan §5 falsifier is **NOT triggered**: six of fifty `wvec`-vs-`wrand`
stratum pairs are distinguishable at their combined 95 % intervals
(`soup/wvec-edge` against all five soup `wrand` strata; `raw/wvec-uni` and
`raw/wvec-edge` against `raw/wrand1`).  **⚠ In every one of the six the vector
stratum scores HIGHER.**  Pooled: soup `wvec` 96.80 % vs control 95.70 %
(p = 0.24); raw `wvec` 92.03 % vs control 84.48 % (p = 0.031).

> **After 3,150 seeds, no vector shape has produced a divergence rate above the
> controls'.  The axis DISCRIMINATES — and so far it discriminates towards
> agreement.**  The shapes are not interchangeable with each other
> (`soup/wvec-walk` 92.00 % is the worst soup stratum, `soup/wvec-edge`
> 100.00 % the only perfect one), and §3.5's clue is entirely a `wvec-edge`
> result.  ⚠ **`wvec-skew`, the shape built FOR H3-B, contributes exactly one
> of the eleven H3-B-signature seeds** and its soup stratum is the second best
> in the corpus; the shape has not yet earned its place.

### §3.7 WHAT CHANGED IN THE TREE, AND ITS CONTROL

Two files, both instruments, neither an engine.

* **`sw/wrfuzz_w2.py`** — NEW.  The survey driver: `seeds` (the retained
  captures as banked-entry records, `fuzz_bank`'s own shape, so `timed_fuzz`
  and `s15_census` read them with no flag), `strata`, `fabric`, `counts`,
  `mod3`, `tranche`.
* **`sw/s15_census.py`** — `one()` SPLIT into `classify(entry, chip, sim)` plus
  a wrapper, so the campaign's **fabric** rows (which no replay can regenerate,
  and which §56 says are not the TB's) can be classified by the tool's own
  taxonomy instead of a fork of it.  The same change gave `classify`
  `timed_fuzz.wait_class` for its stratum label, because the inline expression
  reported every `wvec` seed as `fix0`.

**THE CONTROL THAT SAYS NEITHER MOVED A NUMBER**: `s15_census --core ucore
--pop reg` over the banked corpus reproduces SM3 §2.1's own column **to the
seed** — `PF_LOST` 85 · `DATA_SEQ` 33 · `SCHEDULE` 13 · `PF_ADDR` 8 · `PIN` 4 ·
`PF_GAINED` 2 · `TAIL_EXTRA` 0 = **145** — and `timed_fuzz --core ucore --pop
reg` reproduces **1,557 / 1,702** exactly, TB receipt `cede73e73a318753…`.
`git diff` over `hdl/` and `sim/` is EMPTY.

### §3.8 THE VICTORY TRANCHE — FROZEN

`sw/testdata/wrfuzz/victory_population.json`, sha256
**`dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d`**.
**196 body seeds** (7 per stratum, `k ∈ [300000 + 1000·i, +7)`, disjoint from
`wr1` by construction) plus **four directed H3-B cells at 25 seeds each**
(`skew`, `blk = 32`; D1 soup 0/7, D2 soup 1/15, D3 raw 0/7, D4 raw 1/15),
**3 repetitions** and **5 on the 12 declared promotion cells**.  296 seeds,
**912 seed-loops**, ≈ 3.8 minutes of board time at the budgeted rate.
⚠ The directed cells are **SELECTED by searching each k-block for the seeds
whose deterministic draw already is `(skew, 32, wlo, whi)`**, because
`derive_case` has no override that pins a vector shape's parameters; a
`force_wvec_spec` knob is **BOOKED for W3** rather than added in a survey
sitting.

### §3.9 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT.**  No `v30ctl`, no `s10_board`/`s13_board`, no serve
  session, no `div_guard`, no `board_idle`, no flashing — nothing was opened.
* **Nothing landed in either engine.**  `git diff` over `hdl/` and `sim/` is
  EMPTY; no save-state address moved, no `SS_VERSION` bump, no Quartus run.
* **No mechanism was proposed as settled, diagnosed or refuted.**  §3.5 is a
  ranked candidate with an invariant table and a falsifier, and it says so.
* **No fix of any kind**, including the two things the survey found and booked
  (F-9's retention policy, the missing `force_wvec_spec` override).
* **No ratchet moved.**  The two non-regression legs are reported at their
  registered values.  The wr1 columns registered in `standing_gates.md` are a
  **first registration, the survey baseline — NOT ratchets.**
* **No memory file was touched and Codex was not launched** — the coordinator
  routes this package.

### §3.10 WHAT WAS BANKED

| artifact | sha256 |
|---|---|
| `sw/testdata/wrfuzz/victory_population.json` | `dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d` |
| `sw/testdata/wrfuzz/w2_strata.json` (the 28-stratum table under all three exclusions, `S`, `B`) | `190a3d652978507fdc4a2b119265f7af0996a581f94be47134a0d957377690c5` |
| `sw/testdata/wrfuzz/w2_fabric_census.json.gz` (the FABRIC family census) | `5a856a69a3eb6792930ddc832eeaa20a8060a30861d12e8938bc3807aa46a0d6` |
| `sw/testdata/wrfuzz/w2_ucore_census.json.gz` (`s15_census --core ucore`) | `72432869abf24c14f3a22fc5422f88e82fcd37233ba145dccf63026c34931abf` |
| `sw/testdata/wrfuzz/w2_sim_census.json.gz` (`s15_census --core sim`) | `23f4ca7cdfd8d6f843af3a49ab01c8804b0c54e6728cf99a0c131a3069c7f7ee` |
| `sw/testdata/wrfuzz/w2_counts.json` (per-seed INTA / class-A / opsig / `mc1/721`) | `d1e1f4d530711c28b5b3e69e9ce1057b96a0afc391abe73fdc36fe4fa7aba713` |
| `sw/testdata/wrfuzz/w2_mod3.json` (the B-4 re-run over 3,150, and the VACUOUS byte scan) | `0b47fd0d53bef0de2413a4468e3a25434a4e12b78289a1649800ababc509b1be` |

The 380 banked-entry records the offline legs were scored from are a
DERIVATION of `sw/testdata/campaigns/wr1/` (results line + `captures/`'s
`real` and `sim` rows + the stratum's own `ov`) and are rebuilt on demand by
`sw/wrfuzz_w2.py seeds`; they are not committed, for the same reason the loose
captures are not.
