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
(0 of 21,203 lines -- mc1 10,003 + mc2 10,000 + t30-raw 1,000 + t30-brkem 200;
`wr1` is the first campaign with one, B-2's own gate), so
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

---

## §4 W3.1 — **THE SINGLE-STEP TRAP'S ENTRY.  IT IS TWO THINGS, NOT ONE, AND ONE OF THEM IS A SHADOW THE TREE ALREADY DECODES FOR THE OTHER RECOGNITION.**

**2026-08-05, branch `ucsim`, from HEAD `f22f888feb`.  OFFLINE, NO BOARD
CONTACT, NO FLASHING, `use_core` never set.**  Pre-registration:
`docs/notes/wrfuzz_w31_prereg_2026-08-05.md`, committed at **`a78a3de16f`
before any engine file was edited**.  New instrument: `sw/w31_shadow.py`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §4.1 THE HEADLINE

> **The survey's 75-seed trap family is TWO mechanisms.**  Partitioned by entry
> geometry: **50 seeds where the two sides trap at DIFFERENT instruction
> boundaries**, **32 where they trap at the SAME boundary and the engine's
> vector read is 2-6 clocks LATE**, and 53 with no entry difference at all.
>
> **The first is the RECOGNITION SHADOW, and the trap was not riding it.**
> §86.A booked that as a divergence with a falsifier written down; the
> falsifier fired.  **LANDED IN BOTH ENGINES**, one term each.
>
> **The second is booked, not landed** — the prefetcher SUSPEND, gated on
> `irq_take` in the RTL and on `maskable()` in the model, which the trap never
> satisfies.

### §4.2 ⚠ THE SURVEY'S §4.1 READING IS CORRECTED

`wrfuzz_survey_2026-08-05.md` §4.1 read `PF_LOST`'s 30 `MEMR 00004` seeds as
*"the SAME event with the owners swapped"* as `PF_GAINED`'s 18.  **They are not
the same event.**  `PF_GAINED` 18/18 are SAME_BOUNDARY (a bus-launch question)
and the `PF_LOST` 30 are DIFF_BOUNDARY (a recognition-class question).  Same
family label, same contested address, two causes.  The survey's candidate-1 row
is superseded by this section.

### §4.3 THE LAW, MEASURED ON SILICON ALONE

`sw/w31_shadow.py` is engine-free on the chip side: consecutive vector-1
entries publish their return IPs on the pads (§83.4's readout) and the
GENERATOR'S OWN instruction layout — `fuzz_campaign.build(cfg)['ins']` plus
`testimage.compose`'s store stub — says where instructions start.  `grace` is
the number of instruction boundaries the part ran PAST between one trap and the
next; §84/§85 measured the storm cadence at **0** on 1,742 + 90 pairs.

**380 retained `wr1` captures · 3,411 chip vector-1 entries · 1,363 ruled
consecutive pairs:**

| class | opcodes | grace 0 | grace ≥ 1 |
|---|---|---|---|
| **`MOV` sreg** | `8C` `8E` | **0** | **69** (68 × g1, 1 × g2) |
| **`POP` sreg** | `07` `17` | **0** | **6** |
| `PUSH` sreg | `06` `16` | **5** | 0 |
| `LES` / `LDS` | `C4` `C5` | **11** | 0 |
| everything else | **195 distinct opcodes** | **1,277** | **0** |

**75 of 75 grace-≥1 pairs are inside the class; 1,288 of 1,288 grace-0 pairs
are outside it.  Not one exception in either direction.**  The single grace-2
pair is two consecutive `8E`s — the shadow COMPOSING, a consequence of gating
the take and not the arm.

> **THE LAW.**  An instruction of the shadow class does not permit a
> single-step trap to be TAKEN at its own retire boundary.  The arm is
> untouched — the boundary still SAMPLES — and the take moves to the next
> boundary.
>
> **THE CLASS IS TWO MICROCODE ENTRIES, NOT A LIST OF OPCODES:**
> `00?.100011?0.00` (`8C`, `8E` — `R -> M`) and `00?.000??111.00`
> (`07`, `0F`, `17`, `1F` — `OPR -> R`).  `PUSH` sreg is the ADJACENT entry
> `00?.000??110.00` (`R -> OPR`) and does NOT shadow; `LES`/`LDS` are their own
> entries and do NOT shadow.

That framing is what earns `8C` — a segment-register **READ** — its membership:
it shares an entry with `8E`.  §84.7's write-derived rendering was already
refuted in the RTL for the same reason, and the two negatives above are the
class boundary measured rather than assumed.

**WHAT WAS ALREADY IN THE TREE, AND WHAT WAS NOT.**  `v30u_eu.sv:270`'s
`irq_shadow` — *"a segment-register write skips ONE boundary"* — has gated the
maskable/NMI recognition since the ucore existed, from `pla3_sreg_mov`, which
the generated table confirms is exactly `8C`/`8E`.  **It did not gate the
trap** (`wire bnd_take = irq_take || brk_arm;`), and **the `POP`-sreg entry was
in no class in either engine.**

### §4.4 THE LANDINGS — one term each, no flop added

* **`sim/exec_impl.h`**: `brk_take_ = brk_arm_ && !sreg_shadow(m_, ld)`.
  Plus `LoadResult::ext` (`sim/loader.h`, `loader_impl.h`) — **load-bearing,
  and found by this landing's own A-1 bar**: on the `0F` page `out.opcode` is
  the SECOND byte, so an unguarded `opcode == 0x1F` shadows `0F 1F`, a
  different entry entirely.  It moved `wr1/207098`'s first divergence EARLIER,
  the bar caught it, and the RTL already guards its own copy with `!ld_ext_n`.
* **`hdl/rtl/ucore/v30u_eu.sv`**: `wire brk_take = brk_arm && !irq_shadow;`
  `wire bnd_take = irq_take || brk_take;` — a WIRE, no flop, no `SS_VERSION`
  bump (`ss_lint` exits 0, 0 UNMAPPED, census unchanged).
* **`hdl/rtl/ucore/v30u_eu_step.svh`**: the `POP`-sreg entry joins the shadow
  class, three opcodes named in ONE place because no PLA column carries them.
  ⚠ **It reaches the maskable recognition too**, which is deliberate — silicon
  has one class — and prereg §3.3's falsifier #3 says an INT/EVT regression
  reverts that half.  **It did not fire: the EVT column went UP.**

### §4.5 THE NUMBERS — measured, seed by seed, both engines

| leg | before (this tree) | **after** |
|---|---|---|
| `wr1` retained-and-scored 184, **model** | 48 | **73** |
| `wr1` retained-and-scored 184, **`ucore` TB** | 49 | **77** |
| `timed_fuzz --core sim` REGISTERED | 1,338 | **1,339** |
| … EVT | 798 | **799** |
| … COMBINED | 2,136 | **2,138** |
| `--core sim --seeddir b2-tranche` | 159 | **161** |
| `timed_fuzz --core ucore` REGISTERED | 1,557 | **1,559** |
| … EVT | 931 | **934** |
| … COMBINED | 2,488 | **2,493** |
| `--core ucore --seeddir b2-tranche` | 177 | **181** |

**A-2 (no loss) is MET on every population and both engines: ZERO seeds lost,
ZERO first divergences moved earlier**, over `wr1`'s 380 and the bank's 3,242,
checked seed by seed against a baseline re-measured on this tree with the
change stashed.

⚠ **THE `wr1` MOVEMENT IS 25× THE BANK'S, AND THAT IS THE SURVEY'S OWN POINT.**
The standing bank's 197 vector-1 seeds carry `has_tf = False` on all of them
(§83.3b: TF there is INCIDENTAL), while `wr1` has a deliberate `tf` generator
form.  The family lives in `wr1` and barely exists in the promoted corpus —
which is why an unbiased whole-stratum capture found it.

**ALL 28 `ucore` GAINS ARE DIFF_BOUNDARY SEEDS** — the shadow's own class, 50
→ 22 remaining.  The 32 SAME_BOUNDARY seeds are untouched, exactly as §4.7
says they must be.

### §4.6 THE BARS AS REGISTERED

| bar | outcome |
|---|---|
| **A-1** mechanism: each of the 39 predicted seeds' first divergence moves later or the seed becomes EXACT, zero exceptions | **NOT MET.  6 exceptions on the model, 3 on the `ucore`** |
| **A-2** no EXACT lost, any population, either engine | **MET — 0 lost, 0 moved earlier** |
| **A-3** ratchets may only go up | **MET — every column up, none down** |
| **A-4** the SM trap cells must not move at all | **MET** |
| **A-5** the must-not-move ladder | **MET** |
| **A-6** `ulockstep`, `ss_lint`, G6 | **MET** — `ss_lint` rc 0, `ulockstep` **17,350 / 17,350**, **G6 PASS** |

**G6, the CONTROL/DEFAULT Quartus build** (`sw/quartus_gate.py`, 88 input files
`d58b8c588655c928…`, receipt **`b5badb7ed3cc68e0…`**): E1 `gen_ucore_qsf
--check` PASS · **E2** 0 compile errors, every stage `Successful` · **E3**
`divclk` Fmax **45.51 MHz** against a registered ≥ 32 · **E4** worst setup
**+6.541 ns** · **E5** TNS **0.000, setup AND hold, every domain**.  Recorded,
not gated: **ALMs 11,209 / 41,910 (27 %)**, 0 latches, 0 `lpm_divide`.
**NO BITSTREAM WAS FLASHED.**  The board still carries FLASH #10, so every
fabric figure in this ledger is a FLASH #10 figure and none of this sitting's
`ucore` numbers is one.

**A-1 IS REPORTED AS REGISTERED AND IS NOT RESTATED.**  What the misses are is
a separate statement, and it is **POST-HOC**: on all six the engine's first
divergence is **UPSTREAM of the contested trap entry** (e.g. `wr1/200024` fb
1203 against an entry at row 1774; `wr1/210132` fb 505 against 1222).  The
predicted SET was selected on *the first divergent trap ENTRY* while the BAR
was written on *the engine's first divergence*, and on those seeds a different,
earlier divergence owns that coordinate.  The selection was mine and the
mismatch is mine; it is written down rather than smoothed.

⚠ **AND ONE ERRATUM IN THE PRE-REGISTRATION ITSELF.**  A-3's numbers were
quoted from `CLAUDE.md`'s quick reference (1,282 / 789 / 2,071 sim,
1,502 / 920 / 2,422 ucore), which is **STALE**: `standing_gates.md` has carried
**1,338 / 798 / 2,136** and **1,557 / 931 / 2,488** since SM3 sitting 26's
illegal-form stall.  The measured results clear the CURRENT registered figures,
which is the bar that counts; the pre-registered numbers were a floor set too
low and they are named here rather than quietly met.

#### §4.6a THE MUST-NOT-MOVE LADDER, both engines

**Model**: `make -C sim test` PASS · `pla3_check` 21 · `ucsim_check v0.1`
169,000 · `mod3_illegal --residue stale-ea` 128 · `timed_gate v0.1 --forms all`
169,000, row-diffs 0 · `v0.1-w1` / `-w3` 1,200 each · the four HLT sweeps
**97 + 95 + 46 + 45 = 283 / 283** · `check_boot --timed 220` MATCH ·
`timed_scenario` 18 / 0 / 9 · `timed_enter_replay` 154 ×5 ·
`timed_ins_replay --raw` 1,312 and 2,624 · `timed_wvec_gate` 88 / 88, +0.0 % ·
`timed_lawcards` 8 GREEN / 0 RED / 3 UNRESOLVED ·
**`sm3_tf_floor_cell score --core sim`: floor 3, 121,890 rows, 0 row-diffs,
EXACT on all 30, W-0a 0/18, W-1 30/30, W-2 {3} 22/22, W-3 [2,2]/[3,3], W-4 0·0,
W-5 90/90.**

**`ucore`**: **`sm3_tf_floor_cell score --core ucore`: floor 4, 121,860 rows,
0 row-diffs, EXACT on all 30, W-1/W-2 {4} 22/22, W-3, W-4, W-5 all as
registered** · `ss_lint` exit 0, 0 UNMAPPED, no `SS_VERSION` bump (the landing
is a WIRE) · `ulockstep --golden all --cases 50` **17,350 / 17,350** ·
`check_core --opcodes all --cases 0` **169,000 / 169,000** ·
`--suite-dir v0.1-w1 --waits 1` / `-w3 --waits 3` **1,200 / 1,200** each ·
`EB --waits 1` **200 / 200** · the four `evt` cells
**200 / 1,200 / 200 / 1,200** · `w1evt-biased --waits 1` **1,200 / 1,200** ·
`f4a_boundary` **160 / 160** · `f0lock_tranche` **400 / 400** ·
the four HLT sweeps **97 + 93 + 45 + 44 = 279 / 283** (the four family-D cells,
unchanged) · `check_boot --timed 220` MATCH · `timed_wvec_gate --core ucore`
**88 / 88, +0.0 %** · `timed_enter_replay --core ucore` **154 / 154 ×5** ·
`timed_ins_replay --core ucore --raw` **1,312** and **2,624** ·
`check_ab_sim --core ucore` MATCH over 187 rows.

⚠ **THE `evt` CELLS ARE THE ONE THAT MATTERS FOR FALSIFIER #3** — the
`POP`-sreg half widens the SHARED `irq_shadow`, so it reaches the maskable
recognition.  `w0evt` / `w1evt` / `w2evt` / `w3evt` / `w1evt-biased` are
**200 / 1,200 / 200 / 1,200 / 1,200, unmoved**, and the bank's EVT column went
**UP** (931 → 934).  **The falsifier did not fire and the `POP` half stands.**

**⚠ TWO INSTRUMENT-INVOCATION ERRORS OF THIS SITTING'S OWN, BOTH CAUGHT BY THE
LADDER AND BOTH WORTH RECORDING** — this is `CLAUDE.md`'s *"verify a flag
exists before trusting a run that used it"* earning its place twice in one
sitting:

1. `check_boot.py` **DOES NOT TAKE `--core`**: `check_boot.py --core sim
   --timed 220` raises `ValueError` on the positional parse.  The correct
   invocation is `check_boot.py --timed 220` and it MATCHES over 220 rows.
2. `check_core.py --suite-dir tests/v30/v0.1-w1` **without `--waits 1`** runs
   the w1 suite at w0 and reports **94 / 1,200**.  The same shape made the four
   HLT sweeps read **0 / 95, 0 / 46, 0 / 45**.  With the registered `--waits`
   they are 1,200 / 1,200 and 93 / 45 / 44.  **A silent wrong-argument run of a
   ratchet gate reads exactly like a catastrophic regression, and neither
   reading was true.**

### §4.7 THE SECOND HALF — **BOOKED, NOT LANDED: THE ENTRY'S LAUNCH**

32 seeds; the two sides trap at the SAME boundary and the engine's vector read
is late by **+2 (×12), +4 (×11), +5 (×3), +6 (×5)** with one outlier at −6.  On
**19 of the 32** the engine runs one extra `CODE` prefetch the chip does not;
on the rest it runs the same fetches and is still 2 clocks late.  `PF_GAINED`
18/18 live here, and all 18 have an ODD return address, so the chip's refill is
3 bytes and the queue has room — the chip declines a fetch it could make.

*The mechanism candidate is the OTHER half of the same wire*, and both engines
say it in as many words: `v30u_eu.sv`'s `assign eu_bnd_post = irq_take && …`
(the prefetcher SUSPEND, §86.A: *"the suspend belongs to the recognition that
PAYS the IE floor, which the trap never does"*), and the model's, inside
`live = maskable() && …` with `maskable()` = `ev_pin_ == 0`, which is every
seed a trap fires in.

**NOT LANDED.  No figure is claimed for it.**  Its own cell and
pre-registration are owed, and the standing rule holds: the sitting that
measures a class does not also land it.

### §4.8 THE RIDERS

#### §4.8a THE 12 ZERO-`0F FF` 8080 LANDINGS — **ANSWERED, AND IT IS A CORE BEHAVIOUR**

Chip-side and engine-free.  On each of the 12 the row where `PS3` first goes
high is inside an interrupt entry, and the instruction that entry returns to is
three bytes long and begins with `0F`.  **On 10 of the 12 the THIRD byte IS the
vector the entry read** — `BRKEM`'s `imm8` semantics exactly.  The other two
have byte-split (odd-SP) frames whose pushed CS reads back as garbage; they are
reported unreadable, not as counterexamples.

The ten second bytes are `90 90 90 4A 77 F5 73 CA 7E 53`.  **Not one is `FF`
and none is a documented `0F` form.**

> **The `0F` extension page's PLA does not fully decode its second byte; the
> undecoded rows fall through to `BRKEM`.**  A `0F FF`-free image is therefore
> not an 8080-free image, which answers survey §7.1's open question — *"by what
> path does a BRKEM-free image enter 8080 mode"*.  **It is ROUTED TO THE CORE
> (the `0F` page's don't-care), NOT to the generator**, which corrects the
> survey's routing.  It joins the 8080 / BRKEM family, **DEFERRED BY USER
> DECISION**: counted and reported, not worked.

#### §4.8b `wvec-edge` 5/5 — **THE REGISTERED FALSIFIER'S PREMISE FAILS, AND THE DIRECTED CELL IS NOT RUN**

Survey §4.5 rested on a matched control inside the corpus: `soup/wrand15` with
"the same median `n_ins` (24), the same `nmax_eff` (24) and the same median
bus-cycle count (146 vs 145)".  **Those are STRATUM medians.  Restricted to the
TF seeds — the population the 5/5 is about — the two do not overlap:**

| stratum | TF seeds | `n_ins` | **bus cycles** |
|---|---|---|---|
| `soup/wvec-edge` | 5, all EXACT | 24 – 26 | **144 – 204** |
| `soup/wrand15` | 6, all MISS | 24 – 25 | **291 – 326** |

The control is not matched on the quantity that decides exposure, and
`p = 0.0022` is confounded by exactly the length coupling the survey named and
believed it had controlled.  **The mechanism this sitting establishes has no
wait term at all** — it is a microcode-entry class — which is what survey §4.4
already measured from the other side (at `fix0`, no waits, the TF seeds fail 6
of 7).  **The intermediate-wait hypothesis is UNNECESSARY and its directed cell
is NOT RUN.**  Recorded as a negative with its numbers.

### §4.9 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  No `div_guard`, no
  `board_idle` — nothing was opened.  The board still carries FLASH #10.
* **The victory reserve (`k >= 300000`) was NOT touched**, and no directed cell
  was run: the bank determined the law and no board time was needed.
* **§4.7's entry-launch half is NOT landed** and no figure is claimed for it.
* **Queue items #2 (the raw tier's `SCHEDULE` residue) and #3 (the `ucore`-only
  `PIN` five) were not opened.**
* **No memory file was touched and Codex was not launched.**
* **The `wr1` columns are the SURVEY BASELINE MOVING, not ratchets** — they are
  not registered as ratchets until W-victory registers them.

---

## §5 W3.2 — **THE ENTRY'S LAUNCH IS NOT ONE THING EITHER, AND HALF OF IT WAS NEVER THE TRAP.  NOTHING IS LANDED.**

**2026-08-05, branch `ucsim`, from HEAD `4bd041117e`.  OFFLINE, NO BOARD
CONTACT, NO FLASHING, `use_core` never set.**  Pre-registration:
`docs/notes/wrfuzz_w32_prereg_2026-08-05.md`, committed at **`4711069152`
before any engine file was edited**.  New instrument: `sw/w32_launch.py`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §5.1 THE HEADLINE

> **§4.7's 32-seed "entry launch" family is TWO families and only one of them
> is the trap.**
>
> * **P1, 23 seeds** — the engine runs ONE extra `CODE` fetch the part
>   declines.  Its invariant is three exact numbers on both engines and it is
>   wait-independent.  **The registered landing was attempted in three forms
>   and NOT TAKEN: all three cost `wr1` seeds and gained none**, and the
>   sitting's own bound test refutes *"a hold beginning at the recognition
>   boundary"* as a sufficient account.  **B-1 is NOT MET.**
> * **P2, 20 seeds — IS NOT A TRAP FAMILY AT ALL.  It is `SCHEDULE`'s `+2`
>   mode**, half B's own queue item, arriving from the other side: all 20 are
>   classified `SCHEDULE` by `s15_census` and all 20 are a strict subset of
>   half B's 26.  §4.7's "13 with no extra prefetch and still 2 clocks late"
>   was this, mis-filed.
>
> **And half B's `SCHEDULE` trimodal is BIMODAL: `-3` and `-1` are ONE mode**,
> and this sitting **ANSWERS the discriminator `ucsim_t_provenance` §26.10 D
> item 4 registered for it** — the offset is **INVARIANT**, a fixed index, not
> bus-keyed.  **Not landed: implementing a measured constant as a constant is
> the fitted table the standing principle forbids**, and §26.10's mechanism is
> still open.
>
> **NOTHING WAS LANDED THIS SITTING.**  `sim/` and `hdl/rtl/` are byte-identical
> to `4bd041117e` (the build receipt's `build_key` `8a3b54aa…` is W3.1's own),
> and both `wr1` legs re-measure at their registered baselines: **`sim` 73/184,
> `ucore` 77/184.**

### §5.2 THE POPULATION, RE-PARTITIONED — AND IT GREW

W3.1's partition was taken on the PRE-shadow tree.  Re-measured on
`4bd041117e` over the 380 retained captures (184 scored, 196 `OPEN_BUS`):

| class | `sim` | `ucore` |
|---|---|---|
| **SAME_BOUNDARY** | **50** | **45** |
| DIFF_BOUNDARY | 7 | 7 |
| NO_ENTRY_DIFF | 126 | 118 |
| COUNT_DIFF | 0 | 12 |
| UNREADABLE | 1 | 2 |

The shadow landing moved 28 `ucore` seeds out of DIFF_BOUNDARY and **what was
underneath some of them is this class**, so it is bigger than §4.7's 32.

⚠ **ONE INSTRUMENT CHANGE, declared in the pre-registration before it was
used**: an odd-SP (byte-split) frame publishes no readable IP, and W3.1's
classifier declared a whole capture UNREADABLE the moment *any* paired entry
was one.  `w32_launch` does so only if that pair actually DIFFERS.
`UNREADABLE` falls, `NO_ENTRY_DIFF` / `COUNT_DIFF` rise.  **`COUNT_DIFF` is not
a mechanism claim** — it is "every paired entry agrees and one side has more",
a window-edge property.

**AND THE INSTRUMENT DOES NOT OPEN A WINDOW.**  `w32_launch` aligns the two
sides' BUS-CYCLE STREAMS index by index from row 0 and reports the first index
at which they part as either a cycle one side ran and the other did not
(`CYCLE`) or the same cycle at a different row (`SHIFT`).  W3.1's window was
anchored at the first divergent ROW, which cannot tell those apart — and the
whole P1/P2 split is exactly that distinction.

### §5.3 P1's INVARIANT — three numbers, exact, on both engines

| measured | `sim` | `ucore` |
|---|---|---|
| the engine's extra cycle is a `CODE` fetch of the **next word** (chip's last `CODE` address **+ 2**) | **21 / 21** | **23 / 23** |
| **the CHIP's vector-read T1 is exactly 12 clocks after the T1 of the last bus cycle before it** | **21 / 21** | **23 / 23** |
| the ENGINE's vector-read T1 is exactly **10** clocks after the T1 of its own extra fetch | **21 / 21** | **23 / 23** |

**The 12 is wait-independent** — `fix1`, `fix2`, `fix3`, `wrand1/2/3/7` and all
four `wvec` shapes — so on the part the entry's first read is not waiting for a
bus: it goes out the clock the microcode asks for it and the prefetcher is not
in its way.  `delta` follows as `(previous cycle length) − 2` = `+4` / `+5` /
`+6`.  The `+ 2` address says the declined fetch was a LEGAL one: **the chip
declines a fetch it could make.**

`sim`'s 21 are a strict subset of the `ucore`'s 23 (the `ucore` adds `203018`
and `203121`), so the family is model-shared, as `CLAUDE.md` §64.1 requires
before a `sim`-first landing.

### §5.4 THE LANDING — **ATTEMPTED IN THREE FORMS, TAKEN IN NONE.  EVERY FIGURE IS MEASURED.**

The registered mechanism was *the suspend belongs to the recognition, not to
the floor it paid*: `boundary_no_pop`'s `if (post_redirect && live)` becomes
`(live || brk)`, with `brk_take_` handed down from `exec_impl.h`'s three
boundary call sites.  `wr1`, `--core sim`, baseline **73 / 184**:

| form | what it does at the take | **`wr1`** | lost | gained |
|---|---|---|---|---|
| **v1** | `susp()` — set `suspended_` AND take back an un-displayed grant (F2) | **52 / 184** | **28** | 0 |
| **v2** | `susp(withdraw=false)` — set `suspended_` only | **55 / 184** | **18** | 0 |
| **v3** | hold from display clock `B + 2`, no withdraw | **73 / 184** | 0 | **0 — INERT, not one seed's first divergence moved** |

**Registered falsifier #2 fired on v1 and v2 exactly as written**: every one of
the 18 v2 losses has first-divergence signature **`bs CODE!=PASV`** — the chip
prefetches and the engine has gone quiet.  Read on the rows: on `wr1/200078`
the part runs FOUR `CODE` fetches before the vector read and the suspended
engine runs three; on `wr1/201099` the part runs `C00570` and the engine does
not.  **The part's hold begins LATER than the model's boundary clock.**

#### §5.4a THE BOUND TEST, and what it refutes

`V30SIM_BNDTRACE` publishes the model's own boundary clock `B`.  Over the
**600** chip vector-1 entries that lie BEFORE the model's first divergence (so
`B` is a clock both sides agree on):

* **the chip's vector-read T1 is `B + 9` on 482 of 600**, and the whole tail is
  wait pressure (`fix3`, `wrand15`, `wvec`).  **The engines already get this
  right**; the entry's launch time is not in question.
* Restricted to those 482, a prefetch the part GRANTED has its display clock at
  `B + 1` or earlier on **433 of 434** (the single exception has a zero idle
  gap).  P1's contested grant sits at `B + 2`.

So an onset "block grants from display `B + 2`" fits 433/434 grants and forbids
P1's — **but v3 implements exactly that and moves nothing**, because on P1's own
seeds `B` is not where that arithmetic needs it: `wr1/201055`'s contested grant
displays at `B + 0`.  **There is no onset clock relative to the model's boundary
clock that both permits the 552 observed grants and forbids P1's.**  The
candidate as booked — *a hold beginning at the recognition boundary* — is
REFUTED at that resolution, and what replaces it is a sharper question, not a
weaker claim:

> **The open quantity is the TAKE CLOCK at the contested entry**, and it cannot
> be measured from this corpus: the only instrument for it is an engine's own
> boundary clock, and every contested entry lies AFTER that engine's first
> divergence.  **The measurement is circular on banked data.  That is what the
> directed cell is for**, and §5.7 rewrites the cell around it.

⚠ **A candidate this sitting did NOT chase and is naming rather than losing**:
if the part's take were **2 clocks EARLIER** than the model's boundary on these
seeds, ONE number would explain P1 (the prefetcher wins an eval it should not)
**and** P2's `+2` — but P2 is now known to be `SCHEDULE` and TF-free, so the
unification would have to be a bus law, not a recognition law.

### §5.5 THE BARS AS REGISTERED

| bar | outcome |
|---|---|
| **B-1** P1's 23 lose the insert, zero exceptions | **NOT MET — 0 of 23 on every form tried.  The landing is not taken.** |
| **B-2** ≥ 15 of P2's 20 lose the `+2` | **NOT MET, and the prediction was mis-aimed**: P2 is not a trap family (§5.6b) |
| **B-3** no loss, any population, either engine | **MET as the tree stands (nothing landed).  It is what REFUSED v1 and v2**, at 28 and 18 losses on `wr1` |
| **B-4** ratchets may only go up | **MET — unmoved.**  `sim` 1,339 / 799 / 2,138, b2 161; `ucore` 1,559 / 934 / 2,493, b2 181, all re-measured on this tree BEFORE the first edit |
| **B-5** the SM trap cells must not move | **VACUOUS — no engine file changed.**  Not re-run, and not claimed |
| **B-6** the shadow law's populations | **MET — re-run GREEN before the first edit: 75 / 75 grace-≥1 inside the class, 1,288 / 1,288 grace-0 outside it, 1,363 ruled pairs.**  DIFF_BOUNDARY did not rise: 7 on both engines |
| **B-7** the must-not-move ladder | **VACUOUS — no engine file changed.**  Not re-run, and not claimed |
| **B-8** G6 | **VACUOUS — no RTL leg landed.**  Not run |

**The tree is proved unchanged, not asserted**: `git status` is clean over
`sim/` and `hdl/rtl/`, the final build receipt's `build_key` is `8a3b54aa…`
(byte-identical to W3.1's own row), and both `wr1` legs re-measure at
**73 / 184** and **77 / 184**.

### §5.6 HALF B — **THE RAW-TIER `SCHEDULE` RESIDUE, SPLIT**

`s15_census --core` matched to the report, on this tree:
**`sim` 56 `SCHEDULE` (raw 26 / soup 30), `ucore` 48 (raw 25 / soup 23).**

⚠ **AN ERRATUM IN THE SURVEY'S QUEUE ITEM #2.**  It reads *"25 seeds of the raw
tier's 54 … delta trimodal `+2` ×18, `−3` ×11, `−1` ×10"*.  Those delta counts
are the FAMILY-WIDE 42-seed statistics, not the raw tier's 25: measured now the
raw tier is `−3` ×10, `−1` ×10, `+2` ×5 and **the `+2` mode lives in the SOUP
tier** (21 of its 26).  The item's own headline count (25) is right; its delta
histogram belongs to a different denominator.

#### §5.6a `−3` AND `−1` ARE **ONE MODE**, and the registered discriminator is ANSWERED

`ucore`, 21 seeds (raw 20 + soup 1), every figure exact:

| measured | `−3` (11) | `−1` (10) |
|---|---|---|
| the contested cycle is a `MEMW` | 11 / 11 | 10 / 10 |
| the previous cycle is a `MEMW`, ALIGNED on both sides | 11 / 11 | 10 / 10 |
| the three cycles before are `MEMR MEMR MEMW` | 10 / 11 | 8 / 10 |
| **the CHIP's idle gap between the two writes** | **4 / 4 / 4 …  11 of 11** | **4 …  10 of 10** |
| the ENGINE's idle gap | **1**, 11 of 11 | **3**, 10 of 10 |
| the previous cycle's active length | 6, 7, 9, 11, **19** | **5**, 10 of 10 |

> **THE PART LEAVES EXACTLY 4 IDLE CLOCKS BETWEEN THE TWO WRITES — 21 of 21, at
> every wait level and for every completing-cycle length from 5 to 19 clocks.**
> The engine's gap is not a constant: it is 1 when the completing write is 6 or
> more clocks long and 3 when it is 5, i.e. **it moves with the completing
> cycle**, and the `−3` / `−1` split is that movement and nothing else.

`ucsim_t_provenance.md` §26.10 D item 4 registered the discriminator as
*"a directed cell at a `MEMR`→next-cycle boundary at four wait levels: if the
offset is invariant it is a fixed index (the campaign's seventh such), if it
moves with `N` it is bus-keyed"*.  **ANSWERED, and from the corpus rather than
from a cell: the CHIP's number is INVARIANT and the ENGINE's is bus-keyed.**
§26.4.2's "mode `−3`" is retired as a description; there is one geometry and
one constant.

**AND THE CONTROL SAYS THE GEOMETRY IS THE WHOLE SELECTOR.**  Over the 99 `wr1`
seeds the `ucore` reproduces CYCLE-EXACT, the chip's gap between two
consecutive `MEMW` cycles is 1 (×1,567), 3 (×635), 2 (×403), 0 (×207), 5, 6,
10 — and **4 does not occur once in 2,819 opportunities.**  Every occurrence of
"gap 4 between two writes" in the corpus is one of these 21 seeds.

**NOT LANDED, deliberately.**  A `MEMW`→`MEMW` gap written as the constant 4 is
the fitted table the standing principle names, and §26.10's mechanism is open.
What this sitting adds is the measurement that mechanism has to reproduce.

#### §5.6b `+2` IS 26 SEEDS, AND **HALF A's P2 IS A STRICT SUBSET OF IT**

`ucore`, 26 seeds (raw 5 + soup 21), measured at the first parting of the two
bus-cycle streams:

| measured | |
|---|---|
| the previous cycle is a `CODE` fetch | **26 / 26** |
| the contested cycle is `CODE` (17) or `MEMR` (9) | 26 / 26 |
| the previous cycle is ALIGNED on both sides | 26 / 26 |
| **the ENGINE's idle gap is the CHIP's + 2** | **26 / 26** — chip 0→engine 2, 1→3, 3→5, 4→6 |
| the three cycles before are `CODE CODE CODE` | 25 / 26 |

**And half A's P2, measured the same way, is the same statement**: previous
cycle `CODE` 20/20, contested `CODE` 11 / `MEMR` 9, engine gap = chip gap + 2
on **20 / 20** — and `s15_census` classifies all 20 as `SCHEDULE`, all 20 with
`delta +2`.  **P2 ⊂ the `+2` mode; the union is 26, not 46.**  The trap entry is
where the `+2` first becomes VISIBLE on those seeds, not where it is caused.

⚠ **THE CONTROL REFUSES THE OBVIOUS LAW.**  Over the same 99 cycle-exact seeds
the chip's idle gap after a `CODE` fetch is 0 on **3,847** occasions and 1 on
**12,860**, out of **18,990** — and the engine reproduces every one.  So *"the
engine cannot launch back-to-back after a fetch"* is false, by 18,990 counts.
**The `+2` mode's discriminator is NOT the surface geometry and this sitting
does not have it.**  The survey's *"the `+2` mode with `CODE` status is NOT
named by any settled law"* stands, and it is **NOT forced into one** — the brief
for this sitting says so and the evidence agrees.

#### §5.6c THE PARTITION, FOR THE QUEUE

| mode | n (`ucore`) | status |
|---|---|---|
| **`MEMW`→ 4 idle →`MEMW`** (`−3` + `−1`) | **21** | invariant MEASURED, mechanism OPEN (`ucsim_t_provenance` §26.10 D item 4), discriminator ANSWERED, **not landed** |
| **`CODE`→ gap + 2** (`+2`, absorbs half A's P2) | **26** | invariant MEASURED, discriminator NOT FOUND, **not landed** |
| the remainder (`+3` ×1, and `sim`-only `−2` ×3) | 1 | counted, not worked |

### §5.7 THE DIRECTED CELL — **RE-SPECIFIED AROUND THE QUESTION THAT IS ACTUALLY OPEN, AND NOT RUN**

The pre-registration's §6 arms (C-1 room / C-2 full / C-3 in flight) are kept,
and the OBSERVABLE changes: it is no longer *"does the part suspend"* but
**"where is the take, and what does the prefetcher do in the nine clocks after
it"**.  `sm3_tf_floor_cell.py`'s sled makes that measurable with NO engine —
the sled is periodic, every instruction start is known, and the pushed IP names
the boundary the part chose, so the take clock is a chip-side quantity there
and a banked-corpus quantity nowhere.  The cell must therefore report, per
(sled, wait) cell: the take clock from the pushed IP, the vector-read T1, every
`CODE` T1 between them, and the idle gaps either side.  **C-2 remains the
control on which the candidate predicts NO difference.**

**IT WAS NOT RUN.  NO BOARD WAS CONTACTED THIS SITTING** — building the arm is
a sitting of its own and running a cell whose observable was wrong until §5.4a
would have bought nothing.  Recorded as owed, with its question sharpened.

### §5.8 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  No `div_guard`, no
  `board_idle` — nothing was opened.  The board still carries FLASH #10.
* **The victory reserve (`k >= 300000`) was NOT touched.**
* **NOTHING WAS LANDED IN EITHER ENGINE**, and no ratchet figure is claimed to
  have moved.  The three attempted forms are recorded with their numbers and
  reverted; the sim binary is byte-identical to W3.1's.
* **The `PIN` five (queue item #3 / W3.3) was NOT opened.**
* **No memory file was touched and Codex was not launched.**
* B-5, B-7 and B-8 are VACUOUS and are reported as vacuous, not as green.

---

## §6 W3.3 — **THE `mc1/721` COLLISION IS DECIDED ON SILICON AND IT IS THE MODEL'S ORDER; THE `PIN` FIVE ARE ONE FAMILY, FIVE OF FIVE; AND THE TRAP'S TAKE DOES NOT SUSPEND THE PREFETCHER — MEASURED, NOT INFERRED. NOTHING IS LANDED, BY THE PRE-REGISTERED RULE.**

**2026-08-06, branch `ucsim`, from HEAD `32b2d6accb`.  ONE BOARD SESSION,
SOCKET ONLY, NO FLASHING, `use_core` never set.**  Pre-registration:
`docs/notes/wrfuzz_w33_prereg_2026-08-06.md`, committed at **`f883c2b6e2`
before the first board contact and before any engine file was touched**.  New
instruments: `sw/w33_pin5.py`, `sw/w33_poste_cell.py`, `sw/w33_take_cell.py`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §6.1 THE HEADLINE

> * **CELL 1 — `mc1/721` IS DECIDED.  The die commits the POST-`E` write FIRST
>   and the successor's one-byte-logic write lands ON TOP of it** — the C++
>   model's order, `ucore_provenance.md` §86.G's candidate **C1-A**.  Measured
>   on **two register bits through two pin paths**, unanimous over 40 periods ×
>   3 reps in every measurement cell, with **four nulls green and one of them
>   producing C1-C's "a write is LOST" value on the same rig with the same
>   reader**.  §49.8's *"which of the two fails to land"* is answered:
>   **NEITHER**.
> * **AND THE DECIDER SAYS THE BLOCK STANDS.**  Bar **W-5** — the ISOLATED 1BL
>   with no post-`E` anywhere near it — is **MET on 13 cells × 2 waits × 3 reps,
>   chip identical to BOTH engines**.  The 1BL commit clock is exactly where
>   both engines put it; §1's banked evidence forbids discharging the post-`E`
>   inline; so the two independently measured placements really do collide and
>   §87.B's honest block is CONFIRMED, not dissolved.  **NOTHING IS LANDED, and
>   no second micro-ROM read is taken** — decision-rule branch 2, written before
>   the run.
> * **CELL 2 — THE TAKE DOES NOT SUSPEND THE PREFETCHER, AND `vec − take` IS
>   INVARIANT.**  On 563 directed vector-1 entries over 20 (sled, wait) cells,
>   **`vec − take` is 9 on 500 and 10 on 63**, and the chip runs a `CODE`
>   prefetch INSIDE the window on **121 of 563**.  §4.7's booked candidate —
>   *the take suspends the prefetcher* — is **REFUTED on silicon**, which is
>   what §5.4's v1/v2 losses predicted and could not prove.  **No board contact
>   was needed**: the circularity §5.4a named is broken by the POPULATION.
> * **CELL 3 — the TF floor cell composes EXACTLY**, both engines, every
>   registered bar.
> * **THE `PIN` FIVE ARE ONE FAMILY AND IT IS `mc1/721`.**  The survey said
>   *"three of the five carry the signature"*; measured, it is **five of five**,
>   and the two `ps 2!=6` seeds are the same collision one flag bit over.
>
> **NOTHING WAS LANDED.**  `sim/` and `hdl/rtl/` are byte-identical to
> `32b2d6accb` (`git diff` empty over both trees), so every ratchet is UNMOVED
> and none is claimed.

### §6.2 THE BANKED-EVIDENCE LEG — **THE `PIN` FIVE ARE `mc1/721`, FIVE OF FIVE**

`sw/w33_pin5.py` plus the RTL's own §86.G probes (`+brktrace`'s `1BL` and `PE`
lines).  Measured on the frozen tree BEFORE the cell was designed, and written
into the pre-registration §1 so the cell's design cannot be mistaken for having
been chosen after seeing its result.

| seed | stratum | first parting | adjacency | 1BL bits | post-`E` writes | model-order final | silicon |
|---|---|---|---|---|---|---|---|
| `wr1/200127` | soup/`fix0` | row 262 `data` | clk 193→194 | `0001` CY | `fa83` | `fa82` | word `a9d8`, `ucore` `a9d7` (Δ 1) |
| `wr1/203092` | soup/`fix3` | row 802 `data` | clk 638→639 | `0001` CY | `f217` | **`f216`** | **`f216`**, `ucore` `f217` |
| `wr1/205145` | soup/`wrand2` | row 439 `data` | clk 416→417 | `0001` CY | `f017` | **`f016`** | `ab02` (CY 0), `ucore` `ab03` |
| `wr1/207147` | soup/`wrand7` | row 1591 `data` | clk 1221→1222 | `0001` CY | `f246` | `f247` | `b3be`, `ucore` `b3bd` (Δ 1) |
| `wr1/209095` | soup/`wvec-uni` | row 404 `ps` | clk 393→394 | **`0200` IE** | `f246` | **`f046`** | **`ps.ie = 0`**, `ucore` `ps.ie = 1`, 113 rows |

**FIVE OF FIVE carry an EFFECTIVE `1BL`→`PE` adjacency upstream of the first
parting, and on every one the MODEL-ORDER final value is what silicon shows.**
Two are DIRECT (`203092`'s flag word on the lanes; `209095`'s IE bit on the
`ps` nibble), one is near-direct (`205145`'s low bit), and two are a Δ-1
downstream consumer of CY, which is §86.G's own *"the `sigma` that differs by 1
two instructions later"*.

⚠ **THE TWO `ps 2!=6` SEEDS ARE THE SAME MECHANISM ONE FLAG BIT OVER.**  `ps`
bit 2 is `IE` (`sim/biu_timed.cpp:data_ps`), the 1BL is a `DI`, and **`9E`
SAHF's post-`E` row writes the WHOLE flag word** — its `007D` row snapshots
`FLAGS -> tmpaH`, so the post-`E` puts IE back on top of the `DI`.  The survey's
§5 reading ("four part on `data`, the fifth parts on `ps`", three carrying the
signature) is superseded: **there is one family, not two shapes.**

⚠ **AND THE SCHEDULE IS A MEASUREMENT AGAINST §86.G's SPECIFIED FIX.**  All
five have `schedule_identical = YES` against silicon — 253 / 172 / 190 / 192 /
175 bus cycles, through 4, 2, 1, 2 and 3 adjacencies.  A post-`E` discharged
INLINE on the `E` row's own edge is one clock CHEAPER than the `ucore` is, so
the schedule would move.  **It does not.**  §86.G's fix as specified is
therefore refuted by the `ucore`'s own cycle-exactness before it is refuted by
§87.B's ROM-law argument, and this sitting does not re-propose it.

**NOT IN THE FAMILY.**  `wr1/225009` (raw/`wvec-skew`, `ps 2!=6`, `ndiff` 1)
has NO effective adjacency before its parting at row 1855 — its nearest is at
clk 2483, after it.  `wr1/215017` (raw/`fix1`) has one at clk 233 but is
model-SHARED.  Both stay routed `sim`-first and out of the `ucore`-only column,
in every branch, as the pre-registration §5 requires.

### §6.3 CELL 1 — THE INSTRUMENT

`sw/w33_poste_cell.py`.  §86.G's falsifier — *any ROM form whose post-`E` row
writes register R, followed by a 1BL form writing R, with a PRE-POPPED
successor* — manufactured in **two independent readouts on two different
register bits through two different pin paths**, plus the decider, plus four
nulls.  17 sled variants × 2 waits × 3 reps = **102 socket captures**, 4,063
rows each, ~40 independent periods per capture.

* **ARM A — IE on the `ps` pins.**  `FB` EI · `9E` SAHF · `FA` DI · 8 × `NOP`.
  The observable is the `ie` bit of the status nibble on the `CODE` fetches of
  the NOP run — **no memory write and no frame reader at all**.
* **ARM B — the flag WORD through a `PUSHF` `MEMW`.**  `33 C0` XOR AW,AW plants
  a flag byte of `0x46` that NEITHER candidate can produce, so *"one write is
  LOST"* is a distinguishable THIRD outcome and not a tie.  Then `B4 xx` ·
  `9E` · a CY 1BL (`F5`/`F9`/`F8`) · `9C` PUSHF · `5A` POP DX.
* **ARM D — the ISOLATED 1BL, the DECIDER.**  `FB` · `8A 07` (bus anchor) ·
  pad · `FA` · `8A 07` · 4 × `NOP`, the pad walked over six lengths so the
  prefetch phase sweeps the commit clock.  No `9E` anywhere.
* **NULLS.**  `a_noDI`, `a_no9E`, `b_nobl`, `b_no9E`.

### §6.4 CELL 1 — THE RESULT, SCORED AS REGISTERED

**Every measurement cell selects C1-A — POST-`E` FIRST — and every null and
every matched control is green.**

| cell | **chip (silicon)** | model | `ucore` | verdict |
|---|---|---|---|---|
| `b_cmc:w0` PUSHF word ×40 ×3 | **`f0d6`** | `f0d6` | `f0d7` | **C1-A** |
| `b_stc:w0` ×40 ×3 | **`f0d7`** | `f0d7` | `f0d6` | **C1-A** |
| `b_clc:w0` ×40 ×3 | **`f0d6`** | `f0d6` | `f0d7` | **C1-A** |
| `a_none:w0` `CODE` with `ie=0` | **192 of 249** | 192 | **0** | **C1-A** |
| `a_none:w3` `CODE` with `ie=0` | **228 of 268** | 228 | 148 | **C1-A** |

| bar | outcome |
|---|---|
| **W-1** all four nulls match BOTH engines, both waits, every rep | **MET** — `a_noDI` 0/249 and 11/268, `a_no9E` 192/249 and 228/268, `b_nobl` `f0d7`, `b_no9E` **`f047`** |
| **W-2** each `b_*:w0` cell unanimous over 40 periods × 3 reps | **MET — one word, no mixture, in all three** |
| **W-3** `b_cmc` and `b_stc` select the SAME candidate | **MET** — they carry OPPOSITE words (`f0d6` / `f0d7`) and both say C1-A |
| **W-4** `a_none:w0`, a different bit and a different pin path, agrees with arm B | **MET** |
| **W-5** the twelve `d_*` cells and `a_no9E`, both waits, match BOTH engines | **MET — chip identical to both, every cell, every rep** |
| **W-6** the 3 reps of every cell identical | **MET — 102 of 102** |
| **W-7** the matched controls (`b_*:w3`, `a_clc`/`a_inc`/`a_movi`) | **MET** |

Scored whole: **chip == model on 102 of 102 cells; chip == `ucore` on 87 of
102**, and the 15 are EXACTLY the measurement cells (`a_none` ×6, `b_cmc:w0`
×3, `b_stc:w0` ×3, `b_clc:w0` ×3).  **Not one control is among them.**

> **THE LAW, MEASURED.**  A post-`E` microcode row's register write commits
> BEFORE the successor instruction's one-byte-logic write.  Both writes land;
> the order is post-`E` → successor.  **`9E` SAHF's post-`E` writes the whole
> flag word, IE included.**
>
> *Falsifier*: any (post-`E` writer, 1BL writer of the same register) pair with
> a pre-popped successor whose final value on silicon is the post-`E`'s rather
> than the successor's.

⚠ **`b_no9E` IS WHY C1-C IS REFUTED RATHER THAN ARGUED AWAY.**  It produces
**`f047`** on silicon — the exact value the "post-`E` was LOST" branch predicts
for the measurement cells — on the same rig, in the same capture set, with the
same reader.  The third outcome was reachable and was not reached.

⚠ **THE CELL IS *NOT* REGISTERED AS A STANDING GATE, DELIBERATELY.**  Its
`ucore` column is the open `mc1/721` block (87 of 102), and a gate whose
registered value is a known-unclosed defect is a ratchet pointed at the wrong
thing.  The 102 captures, their raw words and their `SHA256SUMS` are RETAINED
in `sw/testdata/w33-postecell/` and the cell re-scores offline with no board
contact — it is a directed cell with retained silicon, available to whatever
sitting takes the structure on, and it is what that sitting's landing must be
scored against.

### §6.5 CELL 1 — **THE BLOCK STANDS, AND WHY.  NOTHING IS LANDED.**

The pre-registration's decision rule, branch 2, applies verbatim:

> **W-1…W-4 select C1-A and W-5 PASSES**: silicon commits post-`E` first, the
> 1BL commit is exactly where both engines put it, and the schedule forbids
> discharging the post-`E` inline.  Then the two measured placements really do
> collide, §87.B's block STANDS, and **NOTHING IS LANDED**.

The three legs, each measured rather than argued:

1. **The ORDER is the model's** — §6.4, 15 measurement cells, two register
   bits, two pin paths.
2. **The 1BL commit clock is RIGHT WHERE IT IS** — W-5, the isolated 1BL, chip
   identical to both engines on 13 cells × 2 waits × 3 reps.  §35.3's *"the
   golden's status nibble is already 2 on clock 1"* is re-confirmed on a
   directed population, so the 1BL placement is not the one that moves.
3. **The post-`E` row's OWN CLOCK is right too** — §6.2's `schedule_identical`
   over five seeds and eleven adjacencies.  So the post-`E` placement is not the
   one that moves either.

All three placements are individually correct against silicon and they cannot
all be honoured in the `ucore`'s current structure, because on the `E`-row
PRE-POP path the successor's zero-cost loader chain rides the `E` row's own
edge (`v30u_eu_step.svh` `S_DECODE2` → `v30u_eu_1bl.svh`) while block (b)
discharges `poste` at the TOP of the NEXT edge.  **That is a structural
collision between three measurements, not a scheduling slip**, and §87.B's
disqualifier holds: closing it by discharging `poste` inline needs a SECOND
FULL micro-ROM lookup in one clock (`ucdecode` 8192×10 **and** `ucrom` 1028×29,
because the post-`E` row crosses a bank boundary in the general case), **and an
80s die does not read its microcode ROM twice in a clock.**

**IT IS BOOKED, NOT GUESSED.**  What is now known that §87.B did not know: the
ORDER is settled on silicon, C1-C is refuted, the family is five seeds rather
than one, and **both** of the colliding placements have been re-measured
independently against silicon this sitting.  What is still not known is a
structure that honours all three without a second ROM read, and this sitting
does not invent one.  `mc1/721` stays **L3 — spec'd, awaiting a structure**.

### §6.6 CELL 2 — P1's TAKE CLOCK.  **THE CIRCULARITY IS BROKEN BY THE POPULATION, AND THE SUSPEND IS REFUTED.**

§5.4a closed W3.2 with *"the measurement is circular on banked data"*: the only
instrument for the take clock is an engine's own boundary clock, and every
contested `wr1` entry lies AFTER that engine's first divergence.

**The 30 retained `sm3-s24tfcell` captures are silicon on which BOTH ENGINES
ARE EXACT** — 121,890 / 121,860 rows, 0 row-diffs (`standing_gates.md`).  On a
capture where every bus event agrees clock for clock, the engine's take clock
IS a coordinate both sides share.  `sw/w33_take_cell.py geom` reads it out of
the engine's own trace (`+brktrace`'s `BRKT`; `V30SIM_BRKTRACE`'s
`BRKR … take=1`) and measures the §5.7 observables per entry.

**20 (sled, wait) cells, `exact = YES` on all 20, 563 chip vector-1 entries,
and the two engine legs agree CELL FOR CELL:**

| measured | result |
|---|---|
| `vec − take` | **9 on 500 of 563, 10 on 63** |
| `CODE` T1s strictly between the take and the vector read | **0 on 442, 1 on 121** |

| candidate | prediction | outcome |
|---|---|---|
| **T-A** the take is where the engines put it and does NOT suspend | `vec − take` invariant; `CODE` present where there is room | **SELECTED** |
| **T-B** the take is EARLIER than the engines' boundary | `vec − take` larger by a constant | **REFUTED** — it is the engines' own 9 |
| **T-C** the take SUSPENDS the prefetcher (§4.7's booked candidate) | **ZERO** `CODE` T1s in the window, every cell | **REFUTED — 121 of 563 entries carry one** |

**63 of the 121 entries that carry a prefetch also carry the extra clock** —
the granted fetch pushes the vector read out by one — and the other 58 do not,
so the grant is not automatically in the entry's way.  ⚠ That asymmetry is
REPORTED, not explained; `popfmovi:w3` grants 21 fetches at `vec − take = 9`
while `popfnone:w3` grants 21 at 10.  The 121 grants are concentrated in five
cells (`popftest:w0` 35; `popfnone`/`popfxchg`/`popfadd`/`popfmovi` at `w3`,
21 each; plus 2 singletons at `w0`), which is the C-1 room / C-2 full contrast
arising inside the retained population rather than being manufactured.

> **THE LAW, MEASURED, AND IT IS A NEGATIVE.**  The BRK/TF take does NOT
> suspend the prefetcher.  The chip grants `CODE` fetches inside the nine
> clocks between the take and the entry's vector read, at both wait levels and
> on five different sleds.  The entry's launch cost is a CONSTANT 9 clocks
> from the take, plus whatever a granted fetch in the window costs.
>
> *Falsifier*: any directed cell in which the chip runs ZERO `CODE` fetches
> between take and vector read on a sled where the queue demonstrably has room.

**AND THAT CLOSES §4.7's BOOKED CANDIDATE FROM THE OTHER END.**  §5.4's v1 and
v2 landings lost 28 and 18 `wr1` seeds with first-divergence signature
`bs CODE!=PASV` — *"the chip prefetches and the engine has gone quiet"*.  This
is the same statement measured chip-side on a directed population instead of
inferred from losses.  **The suspend was never the mechanism, and it is now a
measurement rather than a failed landing.**

⚠ **NO BOARD CONTACT WAS TAKEN FOR CELL 2, AND THAT IS A REGISTERED DECISION**
(pre-registration §3.3): fresh captures were to be taken only if the
precondition failed on some cell.  It failed on none.  Re-capturing sleds whose
retained rows already answer the question buys nothing and spends board time.

⚠⚠ **AN ERRATUM IN THIS SITTING'S OWN PRE-REGISTRATION, AND IT IS CELL 2's.**
Cell 2's offline geometry runs against RETAINED captures, so it needed no board
and it was **RUN BEFORE the pre-registration was written** — both legs'
`geom_*.json` are in the pre-registration's own commit `f883c2b6e2`, which is
how this is checkable rather than merely confessed.  **The pre-registration's
§3.1 therefore states T-A / T-B / T-C as candidates when the result was already
in hand, and that is NOT a pre-registration.**  It is written down instead of
smoothed, and the disposition is stated rather than argued:

* **Cell 2's verdict is reported as a MEASUREMENT, not as a met prediction.**
  Its bars T-1…T-3 are integrity conditions (report the precondition per cell;
  the two engine legs must agree; report every distribution whatever it is),
  and those are still worth what they say — but *"T-C was refuted"* carries the
  weight of a measurement, not of a falsifier that could have fired against a
  committed prediction.
* **Cell 1 is NOT affected and the distinction matters.**  Its ENGINE
  predictions were measured on the frozen tree before the pre-registration, as
  §2.3 says in as many words; its CHIP result was not in existence until after
  `f883c2b6e2`, because the board had not been contacted.  W-1…W-7 are
  pre-registered bars in the full sense.
* **The lesson, for the next sitting**: an offline leg that reads RETAINED
  silicon is a board-free measurement and must be pre-registered *before it is
  run*, on the same terms as a board leg.  "No board contact" is not the same
  property as "no result yet".

⚠ **WHAT CELL 2 DOES *NOT* SETTLE, STATED PLAINLY.**  P1's own contested case —
the engine runs one extra `CODE` fetch the chip declines — **does not occur in
this population**, because both engines are exact on all 30 captures.  What is
established is that the take is where the engines put it and that it does not
suspend; therefore **P1 is a GRANT question at the contested slot, not a
recognition question**, and the two candidates still standing are bus-side.
That is a narrowing, not a closure, and it is recorded as one.

### §6.7 CELL 3 — THE TF FLOOR-CELL COMPOSITION CHECK.  **EXACT, BOTH ENGINES.**

The rider bar, run on the final tree:

* `sm3_tf_floor_cell.py score --core sim` — floor **3**, **121,890 rows,
  0 row-diffs**, EXACT on all 30 captures; W-0a 0 vector-1 entries over 18
  captures; W-0b 24,378 rows 0 row-diffs; W-1 determinism MET; W-2 surviving
  floors **{3}**, 22/22; W-3 `iret` [2,2] vs `popfnone` [3,3]; W-4 0 · 0;
  W-5 90 pairs 0 bad.  Nearest non-exact floor 11,032 (floor 4).
* `sm3_tf_floor_cell.py score --core ucore` — depth **4**, **121,860 rows,
  0 row-diffs**, EXACT on all 30; W-0b 24,372 rows 0 row-diffs; W-2 surviving
  depths **{4}**, 22/22; W-3/W-4/W-5 as registered.  Nearest non-exact depth
  14,630 (depth 5).

**Every figure is its registered value.  Nothing moved.**

### §6.8 THE BARS AND THE RATCHETS

| bar | outcome |
|---|---|
| **W-1 … W-7** (cell 1) | **ALL SEVEN MET**, §6.4 |
| **T-1 … T-3** (cell 2) | **ALL THREE MET**, §6.6 — precondition reported per cell, both engine legs agree cell for cell |
| the TF floor composition | **MET, both engines**, §6.7 |
| ratchets may only go up | **VACUOUSLY MET — NOTHING WAS LANDED.**  `git diff 32b2d6accb -- sim/ hdl/rtl/` is EMPTY; the sim binary and the `ucore` TB are the ones W3.2 closed on |
| the must-not-move ladder | **VACUOUS — no engine file changed.**  Not re-run, and **not claimed** |
| G6 | **VACUOUS — no RTL leg landed.**  Not run |

**No ratchet figure moved and none is claimed to have moved.**

### §6.9 THE `PIN` FIVE — FINAL STATE

Cell 1 returned **C1-A**, so the pre-registration §5's first branch applies:

* **The five are ONE family and it is `mc1/721`** — re-labelled in this ledger
  from the survey's *"three of the five carry the signature"* to **five of
  five**.  That is a CLASSIFICATION finding of this sitting; **no gate is
  re-scored and no ratchet is claimed.**
* Their disposition is `mc1/721`'s: **L3 — spec'd, awaiting a structure that
  honours three measured placements without a second micro-ROM read.**  §88.B's
  L3 row (`mc1/721`, `mc2/584`) is unchanged in count and better characterised
  in content.
* `wr1/225009` and `wr1/215017` are **OUT** of the family and stay routed
  `sim`-first (§6.2).
* Survey queue item **#3 is CLOSED as an investigation** — the five needed a
  diagnosis, they have one, and it is a settled item's, not a new one's.

### §6.10 WHAT THIS SITTING DID NOT DO

* **NO FLASHING.**  The board still carries FLASH #10; every `ucore` figure
  here is a Verilator figure and none is a fabric figure.
* **The victory reserve (`k >= 300000`) was NOT touched.**
* **NOTHING WAS LANDED IN EITHER ENGINE.**  `sim/` and `hdl/rtl/` are
  byte-identical to `32b2d6accb`.
* **`mc2/584` was not opened** (§86.H); H3-B, the raw-tier `SCHEDULE` residue
  (§5.6) and the 8080/BRKEM family were not opened.
* **No memory file was touched and Codex was not launched.**
* The must-not-move ladder, G6 and `ss_lint` are VACUOUS and are reported as
  vacuous, not as green.

### §6.11 THE BOARD SESSION — DISCIPLINE, RECORDED

* **Single-writer PROBED** before first contact (`ps w | grep v30ctl|serve` on
  `root@mister-nec`: none; no local `v30ctl.py serve`).
* **SOCKET ONLY** — `emit_suite.EMIT_USE_CORE is False` asserted by the cell
  itself, `use_core=False` passed explicitly on every capture.
* **`div_guard` PINNED and RECORDED** — `div=8 (4 MHz), commanded by this
  connection -> PINNED`, in `manifest.json` and again per run.
* **Full per-clock rows retained** beside the raw 64-bit words, with
  `SHA256SUMS` over every artefact
  (`sw/testdata/w33-postecell/`, 102 captures × 2 files).
* **ZERO transport errors**; the 5-consecutive-error STOP never armed.
* **`board_idle()` run at the end and VERIFIED** — no `v30ctl`/`serve` process
  left on the board.
* **The cell drives NO PIN** — every arm is internal, `evt=None` throughout, so
  there is no INV-1 directive-truncation exposure.

---

## §7 W3.4 — **P1 IS NOT A GRANT QUESTION.  IT IS THE TAKE CLOCK, AND THE RETIRE LEAD LEADS THE SUCCESSOR'S *POP*.  LANDED IN THE MODEL; THE `ucore` LEG IS BOOKED WITH ITS SECOND, STRUCTURAL HALF NAMED.**

**2026-08-06, branch `ucsim`, from HEAD `40800bf6f0`.  OFFLINE, NO BOARD
CONTACT, NO FLASHING, `use_core` never set.**  Pre-registration:
`docs/notes/wrfuzz_w34_prereg_2026-08-06.md`, committed at **`b84277a414`
BEFORE the first line of the sitting's instrument existed** — W3.3 §6.6's own
erratum, applied: an offline leg over RETAINED silicon is a measurement in the
full sense and is registered before it is run.  New instrument:
`sw/w34_grant.py`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §7.1 THE HEADLINE

> **§6.6's closing sentence — *"P1 is a GRANT question at the contested slot,
> not a recognition question"* — is RETIRED BY MEASUREMENT.**  On all 23 seeds
> the engine's TAKE is late by exactly `delta`, and **both engines' `vec − take`
> is 9 — the same constant as the 500 directed entries.**  The entry's cost is
> right and the grant machinery is right; the extra `CODE` fetch W3.2 chased
> through three refused landings is a **CONSEQUENCE of a late take**.
>
> **THE CLASS IS STRUCTURALLY IDENTIFIED, CHIP-SIDE, WITH NO ENGINE IN THE
> LOOP AND ZERO EXCEPTIONS**: the trapping instruction is `FC` ×18 / `FD` ×4 /
> `F8` ×1 — **ONE-BYTE-LOGIC, 23/23**; its fetch address is **ODD, 23/23**, so
> the redirect's refill delivered a single byte and **the queue is DRY (`occ`
> 0) at the retire, 23/23**; and **the chip's take is its own opcode pop + 2 on
> 23/23, WAIT-INDEPENDENT** across cycle lengths 5, 6 and 7.
>
> **THE LAW IS ONE PREDICATE AND IT IS ALREADY LANDED — ON ANOTHER PATH.**
> `boundary_no_pop()` and `v30u_eu.sv`'s own boundary block both say *"the
> recognition decision does not need the byte (it is the decision NOT to take
> one), so a recognised boundary does not slide when the queue is dry"* —
> measured there as `INT.90` **200/200** with the retire deadline against
> **177** with the pop deadline.  **The ROM path got that treatment; the
> ONE-BYTE-LOGIC path never did**, because on it the flag write's lead and the
> recognition boundary ride ONE call.  `wait_retire_lead()` now returns
> immediately when the BRK/TF arm is set: **the lead leads the successor's POP,
> and a boundary that fires cancels that pop.**
>
> **LANDED IN `sim/` ONLY.  Every registered bar met, `ucore` UNTOUCHED**
> (`git diff` empty over `hdl/`, and the `ucore`'s `wr1` leg re-measures at its
> registered **77 / 184** on a TB rebuilt from HEAD).

### §7.2 THE POPULATIONS, AND THE INTEGRITY BARS

| # | population | n | role |
|---|---|---|---|
| **P** | the P1 seeds — chip DECLINES, engine GRANTS | **23** | the class |
| **G** | directed entries with a `CODE` granted in the window | **121** | positive control |
| **N** | directed entries with none | **442** | split into no-room / declined |
| disjoint | the `iret` / `iretnotf` / `notf*` / `storm` cells | **144** entries | registered in the pre-registration §4 as the population NOT used to select |

* **I-1 MET** — every directed cell re-reported `exact = YES`; nothing excluded.
* **I-2 MET** — the `sim` and `ucore` legs agree cell for cell on every
  chip-side quantity.
* **I-3 MET** — the totals reproduce §6.6 **exactly**: `vec − take` 9 ×500 /
  10 ×63, `code_in_window` 0 ×442 / 1 ×121.
* **I-4 MET** — every distribution below is reported, including the two that
  refute candidates of mine.

### §7.3 THE CANDIDATES, SCORED AS REGISTERED

| id | prediction | outcome |
|---|---|---|
| **G-A ROOM (M4 at the take)** | granted ⟺ `occ + inflight ≤ 4` | **REFUTED.**  The chip declines at `occ + inflight` = **2** on 23/23, and **144 of the 442** directed no-grant entries have `occ ≤ 4` at the free clock.  §63.6's negative result about M4's bound is re-confirmed on a second population |
| **G-B ARM-BEFORE-TAKE** | grant ⟺ decision clock < take | **NOT SEPARATING.**  Grants launch at `take + 1` (57) and `take + 2` (64); no onset relative to the take both permits those and forbids P1's |
| **G-C PHASE** | disjoint phase bands | **NOT SEPARATING** — `take − prev T1` = 3 occurs in G (36), N (51) **and** P (23) |
| **G-D THE TAKE IS MISPLACED ON P** | `take_eng − take_vec9 = delta` | **FIRES, 23 / 23, exactly** |
| **G-E ENGINE MIS-EVALUATION of M4** | the engine's occupancy differs | **REFUTED** — the engine's occupancy is correct **for its own, late, take** |

### §7.4 THE MEASUREMENT, SEED BY SEED

Chip-side, from the banked captures alone (`sw/w34_grant.py p1`):

| measured | result |
|---|---|
| trapping instruction | **`FC` ×18, `FD` ×4, `F8` ×1 — ONE-BYTE-LOGIC 23/23** |
| its fetch address | **ODD, 23/23** |
| `occ` at the take | **0, 23/23** (with a fetch in flight, `inflight` 2) |
| chip take − own opcode pop | **+2, 23/23**, at cycle lengths 5, 6 and 7 |
| chip take − the in-flight fetch's T1 | **+3, 23/23** |
| `take_eng − take_vec9` | **= `delta`, 23/23** |
| both engines' `vec − take` | **9** |

⚠ **THE ODD ADDRESS IS §4.7's OWN OBSERVATION, NOW MECHANISED.**  §4.7 read
*"all 18 have an ODD return address, so the chip's refill is 3 bytes and the
queue has room — the chip declines a fetch it could make."*  The room was
never the point: the odd address is what makes the refill **one byte**, so the
one-byte-logic form pops the whole queue and the engine's lead has nothing to
wait for but a byte that has not arrived.

### §7.5 THE LANDING — **AND THE FIRST CANDIDATE WAS FALSIFIED BY THE LADDER, WHICH IS WHY THE WAIT IS KEPT**

Two forms were built and both are reported with their numbers.

| form | what it does | `wr1` (`sim`) | `v0.1` row-diffs | disposition |
|---|---|---|---|---|
| **FORM 3** | delete the `q_.empty()` disjunct — *"a lead waits for a byte the queue HOLDS to mature"* | **84 / 184** | **181** (`FA` 74, `FB` 68, `INT.FB` 39) | **NOT TAKEN** |
| **FORM 7** | `wait_retire_lead()` returns at once when the BRK/TF arm is set | **84 / 184** | **0** | **TAKEN** |

> **FORM 3's 181 row-diffs are the tree's own 250/250 golden defending itself.**
> `loader_impl.h`'s comment above the call carries it: *"odd `ip` — a single
> upper-lane byte, so the successor's pop waits for the next fetch's T4+2, and
> the golden still shows the OLD IE at pop+1, 250/250."*  **The FLAG WRITE
> really does wait for the byte to ARRIVE.**  Two laws rode one call; the
> sitting's first candidate deleted the wrong one, the registered ladder caught
> it, and the number is written here rather than smoothed.
>
> FORM 7 separates them by the single condition that distinguishes them: when
> the arm is set, this instruction retires INTO the trap and **its successor is
> never popped — there is no pop to lead.**  `FA` / `FB` / `INT.FB` are
> untouched by construction; their goldens fire no trap.
>
> *Falsifier*: any capture in which a `ONE_BYTE_LOGIC` form retiring into a
> BRK/TF take has its boundary later than its own opcode pop + 2 with a dry
> queue; or any `FA` / `FB` golden that moves when this gate is armed.

### §7.6 THE BARS AS REGISTERED

| bar | outcome |
|---|---|
| **B-1** P's 23 lose the inserted fetch | **MET** — `w32_launch --core sim`: the `n_ins = +1` class is **21 → 0** |
| **B-2** no loss, any population, either engine | **MET — ZERO LOST, seed by seed, and 0 first divergences moved earlier.**  Bank 3,242: **17 gained, 0 lost**.  `wr1`: **15 gained, 0 lost, 13 first divergences moved LATER** |
| **B-3** ratchets monotone | **RAISED.**  `sim` REGISTERED **1,339 → 1,343**, EVT **799 → 802**, COMBINED **2,138 → 2,145**.  Every column up, none down.  Baselines re-measured on THIS tree with the change reverted, not quoted |
| **B-4** the shadow law's populations | **MET on the law** — 75 grace-≥1, 1,288 grace-0, 1,363 ruled, unchanged.  ⚠ **ITS `DIFF_BOUNDARY` CLAUSE MOVED, 7 → 17, AND IS REPORTED AS REGISTERED** (§7.7) |
| **B-5** the SM trap cells | **MET** — `sm3_tf_floor_cell score --core sim`: floor **3**, **121,890 rows, 0 row-diffs**, EXACT on all 30; W-0a 0/18, W-1, W-2 `{3}` 22/22, W-3 `[2,2]`/`[3,3]`, W-4 0·0, W-5 90/90 |
| **B-6** the §4.6a model ladder | **MET, every figure at its registered value** — `make -C sim test` PASS · `pla3_check` 21 · `ucsim_check v0.1` 169,000 · `mod3_illegal` 128 · `timed_gate v0.1 --forms all` **169,000, row-diffs 0** · `-w1` / `-w3` 1,200 each · the four HLT sweeps **97 + 95 + 46 + 45 = 283 / 283** · `check_boot --timed 220` MATCH · `timed_scenario` 18/0/9 · `timed_enter_replay` 154 ×5 · `timed_ins_replay --raw` 1,312 and 2,624 · `timed_wvec_gate` 88/88 **+0.0 %** · `timed_lawcards` **8 GREEN / 0 RED / 3 UNRESOLVED** |
| **B-7 / B-8** `ss_lint`, `ulockstep`, G6 | **VACUOUS — no RTL file changed.  Not run, and NOT claimed** |

### §7.7 ⚠ THE ONE CLAUSE THAT MOVED, REPORTED AS REGISTERED

`w32_launch --core sim`'s entry partition goes
`DIFF_BOUNDARY 7 → 17`, `SAME_BOUNDARY 50 → 26`, `NO_ENTRY_DIFF 126 → 140`.

**It is not a loss and it is not restated as one.**  Zero seeds left EXACT,
zero first divergences moved earlier, and the `wr1` and bank columns both went
up.  What happened is that seeds whose FIRST divergent entry was P1's now run
past it and are classified at a LATER entry, where the boundary differs.
`DIFF_BOUNDARY` is an **attribution** counter over a divergent-by-construction
subset, not a ratchet (`standing_gates.md` says so of the whole 184).  I
registered it in B-4 anyway, so it is reported as **NOT MET** and the law it
was standing in for — the shadow's own 75 / 1,288 / 1,363 — is reported
separately and is **unmoved**.

### §7.8 THE `ucore` LEG — **BUILT, MEASURED, AND DELIBERATELY REVERTED.  ITS SECOND HALF IS NAMED.**

The mirror change was made (`v30u_eu_step.svh`: `q_ripe_lead_n` becomes
`q_ripe_lead_n || brk_arm` at the `S_DECODE2` hand-over and at `S_1BL_LEAD`),
the TB was rebuilt, and it was measured rather than assumed:

* `wr1 --core ucore` **77 → 78**.  `check_core --opcodes all --cases 0`
  **169,000 / 169,000**, unmoved.
* On `wr1/201055` the `ucore`'s `BRKT` moved **2733 → 2731**.  **The model's
  lands at 2729.**  The prefetch at 2731 is therefore still not blocked, and
  the seed is still not exact.

> **THE `ucore` NEEDS A SECOND, STRUCTURAL CHANGE AND THIS SITTING DOES NOT
> INVENT IT.**  Its one-byte-logic boundary is `bnd_opc = (st == S_OPC_POP) &&
> bnd_armed` — the SUCCESSOR'S POP STATE — while the model's is
> `boundary_no_pop()` at the retire deadline.  With the lead gated, `S_1BL_CHG`
> and `S_OPC_POP` still stand between the retire and the boundary, which is the
> remaining 2 clocks exactly.  The fix is to give the 1BL path its own boundary
> arm at the retire deadline, beside `bnd_row` / `bnd_epop` / `bnd_opc`, and
> that is a structure question with its own bars — `ss_lint`, `ulockstep` and
> **G6** among them.
>
> **The RTL is REVERTED.**  `git diff` is empty over `hdl/`, the TB is rebuilt
> from HEAD, and the `ucore`'s `wr1` leg re-measures at **77 / 184** — a +1
> partial landing that misdescribes the defect is not worth a synthesis gate.
> ⚠ One question the next sitting must answer before re-taking it: the model's
> gate is `brk_arm_` and a `ONE_BYTE_LOGIC` form is never in the shadow class,
> so there `brk_arm_ == brk_take_`; in the RTL `irq_shadow` is a FLOP that may
> carry the PREVIOUS instruction's set, so `brk_arm` and `brk_take` are not
> interchangeable there.  **Measure it; do not assume it.**

### §7.9 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  No `div_guard`, no
  `board_idle` — nothing was opened.  The board still carries FLASH #10, so
  every figure here is offline and none is a fabric figure.
* **The victory reserve (`k ≥ 300000`) was NOT touched.**
* **NOTHING WAS LANDED IN THE `ucore`.**  `git diff` over `hdl/` is empty.
* **The 12 P1 seeds that are still not EXACT are reported, not excused**: 8 of
  them have their first divergence LATER than before (the P1 defect closed and
  a downstream one remains), and 4 (`203018`, `203121`, `204143`, `205000`)
  have an UPSTREAM divergence that predates the contested entry — §4.6a's A-1
  shape, and it is named here rather than counted as a miss of this law.
* `mc1/721`, `mc2/584`, the `MEMW`→4-idle→`MEMW` mode (§5.6a), the
  `CODE`→gap+2 mode (§5.6b), H3-B and the 8080/BRKEM family were NOT opened.
* **No memory file was touched and Codex was not launched.**
* B-7 and B-8 are VACUOUS and are reported as vacuous, not as green.

---

## §8 W3.5 — **THE `ucore`'s TAKE-CLOCK LEG IS LANDED, AND IT IS ONE TERM.  §7.8's "SECOND, STRUCTURAL CHANGE" IS RETIRED BY MEASUREMENT: THE BOUNDARY WAS ALWAYS IN THE RIGHT PLACE, THE ARM WAS ONE CLOCK LATE.**

**2026-08-06, branch `ucsim`, from HEAD `cb4fad5e38`.  OFFLINE, NO BOARD
CONTACT, NO FLASHING, `use_core` never set.**  Pre-registration:
`docs/notes/wrfuzz_w35_prereg_2026-08-06.md`, committed at **`734e11c010`
BEFORE any candidate was landed and BEFORE any candidate was scored.**  New
instrument: `sw/w35_take.py`, plus the `1BLD` probe in the RTL's `+brktrace`
stream.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §8.0 ⚠ THE SITTING WAS INTERRUPTED MID-FLIGHT, AND THE RECORD SAYS SO

A connection error terminated this sitting while the pre-registration was being
written.  On disk at that moment were the two RTL files carrying the **`1BLD`
MEASUREMENT PROBE** — a `+brktrace` `$display` inside `\`ifndef SYNTHESIS`, five
trace registers and one assignment — and **nothing else**.  No candidate had
been landed; no candidate had been scored.  The coordinator's path **(a)** was
taken: the pre-registration was committed first, with the probe, and only then
was the candidate landed and scored.  The extra `verilator_binary.jsonl`
receipts (`a7e4335f62d1…`, `2ee02b6f5fd5…`) are the probe builds and are the
interruption's only visible residue.

**THE PROBE'S INERTNESS IS MEASURED, THREE WAYS, BEFORE ANYTHING IS READ OFF
IT** — `w32_launch --core ucore` **77 / 184 with a byte-identical entry
partition** on the pre-probe tree and on both probe builds, and
`timed_fuzz --core ucore --evt-replay` **1,559 / 934 / 2,493**, the registered
values to the seed.  A ruler that moved the numbers would have made §8.1 a
measurement of the ruler.

### §8.1 THE HEADLINE

> **§7.8's structural reading is RETIRED BY MEASUREMENT.**  It booked the
> `ucore` leg as needing *"a second, structural change … give the 1BL path its
> own boundary arm at the retire deadline, beside `bnd_row` / `bnd_epop` /
> `bnd_opc`"*.  **It does not.**  `bnd_opc` was always in the right place:
> `S_1BL_CHG` plus the zero-cost `S_INSTR_END` put the successor's `S_OPC_POP`
> at **decode + 2**, and **decode + 2 IS the chip's take on 23 of 23** — §7.4's
> *"its own opcode pop + 2, WAIT-INDEPENDENT"*, read straight off the `ucore`'s
> own state machine.
>
> **THE WHOLE DEFECT WAS ONE CLOCK OF ARM LATENCY AT ONE DECODE.**
> `S_DECODE2`'s ONE_BYTE_LOGIC arm runs INSIDE the chain the opcode pop rode,
> so `brk_smp` — the sample instant §85.2a fixed at pop + 1 — has not happened
> yet, and the arm flop still carries the value the previous boundary spent.
> **MEASURED: `brk_arm` = 0 at that decode on 23 of 23.**  W3.4's mirror gate
> read `brk_arm` there, could not fire, fell through to `S_1BL_LEAD` and fired
> at decode + 2 — putting the take at decode + 4, which is `wr1/201055`'s
> **2731 against the model's 2729, §7.8's reported miss, explained to the
> clock.**
>
> **§7.8's NAMED TRAP IS ANSWERED AND IT IS INERT.**  `irq_shadow_n` is **0** at
> every one of the 23 decodes — every pop state clears it and every opcode is
> popped by one — so on this path `brk_arm` and `brk_take` **are**
> interchangeable.  The difference that mattered was never the shadow.
>
> **LANDED: ONE TERM, `q_ripe_lead_n` → `q_ripe_lead_n || brk_seen`, in
> `v30u_eu_step.svh`.  No flop, no new state, no second boundary, no opcode
> named, `sim/` untouched.**  Every registered bar met; `wr1--core ucore`
> **77 → 91**, the bank **1,559 / 934 / 2,493 → 1,564 / 937 / 2,501**, b2
> **181 → 182**, **ZERO LOST anywhere and ZERO first divergences moved
> earlier**, `ss_lint` rc 0 with **no `SS_VERSION` bump**, `ulockstep`
> 17,350 / 17,350, **G6 PASS**.

### §8.2 THE MEASUREMENT §7.8 ASKED FOR — 23 SEEDS, ZERO EXCEPTIONS

`sw/w35_take.py arm`, reading the `ucore`'s own `+brktrace` stream against the
chip's take (the capture's vector-read row **− 9**, §6.6/§7.4's constant):

| measured at the 1BL decode that owns the contested take | value | n |
|---|---|---|
| `q_ripe_lead_n` — the queue is dry, which is the class | **0** | 23/23 |
| **`brk_arm`** | **0** | **23/23** |
| **`brk_seen`** | **1** | **23/23** |
| `irq_shadow_n` | **0** | 23/23 |
| `brk_smp_n` — the opcode pop rode THIS clock | **1** | 23/23 |
| sample clock − decode clock | **+1** | 23/23 |
| **decode + 2 == the CHIP's take** | **MATCH** | **23/23** |

**`brk_smp_n` = 1 at the decode IS the proof that the pop rode the decode's own
clock**, on every one of the 23 — that wire is `q_pop && q_ripe && q_first`
evaluated on that clock, and it is what schedules the sample for the NEXT one.
Traced state by state on `wr1/201055` (`+eutrace`), the chain is
`S_EPOP → S_TAIL → S_INSTR_END → S_TAKE_OPC → S_DECODE → S_DECODE2`, every step
of it zero-cost, and the `QS = F` pin rides clock 2727 with `BRKS` at 2728,
`1BL` at 2731 and `BRKT` at 2733 = decode + 6 = the chip's 2729 plus this
seed's `delta` of 4.  **The arm's absence is a property of the CHAIN, not of
these seeds.**

### §8.3 THE CANDIDATES, SCORED AS REGISTERED

| id | the term added to `q_ripe_lead_n` | outcome |
|---|---|---|
| **U-A** | `brk_arm` — W3.4's mirror | **REFUTED IN ADVANCE BY §8.2 and NOT BUILT.**  The arm is 0 at the decode on 23/23, so the gate cannot fire there; it is the sitting's registered ANTI-BAR (`BRKT` 2731) |
| **U-B** | **`brk_seen`** | **TAKEN.**  Take = decode + 2 = the chip's take on **23 / 23, gap +0 on every one**; `BRKT` on `wr1/201055` = **2729**, the model's own landed clock |
| **U-C** | `brk_smp_n ? brk_seen : brk_arm` | **NOT NEEDED AND NOT BUILT.**  The selection rule fixed in the pre-registration says U-C only if U-B loses a seed or moves a first divergence earlier; **it did neither, on any population.**  U-C would also drag `q_ripe`/`q_pop` into the `st_n` cone, which is §52's timing-critical path |

### §8.4 THE BARS AS REGISTERED

| bar | outcome |
|---|---|
| **Y-1** the P1 take clock closes, 23/23 | **MET — 23 / 23, `take − chip_take` = 0 on every seed** |
| **Y-2** `SAME_BOUNDARY ∧ n_ins = +1` goes 23 → 0 | **MET — 0** |
| **Y-3** ⚠ NO LOSS on `wr1`; ≥ 77 | **MET AND BEATEN — 77 → 91.  14 gained, 0 LOST, 0 first divergences moved earlier, 31 moved LATER.**  The registered POINT PREDICTION was **88** (77 + the model's 11); the outcome is **91**, and it is reported against the prediction, not in place of it |
| **Y-4** `BRKT` on `wr1/201055` = 2729 | **MET — 2729.**  The anti-bar 2731 was named in advance and is not reproduced |
| **Y-5** the `ucore` ladder at its registered values | **MET, every figure**: `check_core --opcodes all` **169,000 / 169,000** · `v0.1-w1` / `-w3` **1,200** each · `EB` w1 **200** · the four `evt` cells **200 / 1,200 / 200 / 1,200** · `w1evt-biased` **1,200** · block I/O **229,999 / 229,999** · `f4a_boundary` **160 / 160** · `f0lock_tranche` **400 / 400** · `check_boot --timed 220` and `--timed 400` **MATCH** · `timed_wvec_gate --core ucore` **88 / 88, +0.0 %** · `timed_enter_replay --core ucore` **154 / 154 ×5** · `timed_ins_replay --core ucore --raw` **1,312 / 1,312** and **2,624 / 2,624** · `check_ab_sim` **187 rows MATCH** |
| **Y-6** the registered fuzz bank, monotone, 0 lost seed by seed | **MET AND RAISED — REGISTERED 1,559 → 1,564, EVT 934 → 937, COMBINED 2,493 → 2,501; b2 tranche 181 → 182.  21 seeds gained, ZERO LOST over all 3,242, 0 first divergences moved earlier**, checked seed by seed against a baseline measured on this tree.  `BOUND WARNINGS` **4 → 4**, `ENGINE ABORTS` **0** |
| **Y-7** the SM trap cells, ucore depth-4 cell exact | **MET EXACTLY — 121,860 rows, 0 row-diffs, EXACT on all 30** at depth **4**, and **0 at no other depth in [1,7]** (nearest **14,630**, at 5); surviving depths **{4}**, W-2 **22 / 22**; W-0a 0/18, W-0b 24,372 rows 0 diffs, W-1, W-3 `[2,2]`/`[3,3]`, W-4 0 · 0, W-5 90/90.  ⚠ **The strongest control in the sitting: the regenerated `sw/testdata/sm3-s24tfcell/score-ucore.json` is BYTE-IDENTICAL to the committed one** — every floor, every cell, every diff count.  The trap's own sharpest gate did not move by one row |
| **Y-8** the shadow law's populations | **MET, UNMOVED — 75 grace-≥1, 1,288 grace-0, 1,363 ruled**; `MOV`sreg 68 g1 + 1 g2 / 0 g0, `POP`sreg 6 / 0, `LES`/`LDS` 0 / 11, all other 0 / 1,277 |
| **Y-9** `ss_lint` rc 0, no SS bump expected | **MET — rc 0, 205 architectural flops, 0 UNMAPPED, `SS_VERSION` 0x87 unchanged.  NO flop landed**, exactly as registered: the change is a TERM in an existing next-state expression |
| **Y-10** `ulockstep --golden all --cases 50` | **MET — 17,350 / 17,350, ALL CASES LOCKSTEP** |
| **Y-11** G6 | **MET — PASS.**  E1 `gen_ucore_qsf --check` PASS · **0 stage errors, 0 error lines** · **Fmax 47.31 MHz** against the registered ≥ 32 · worst setup **+9.226 ns** · **TNS 0.000 on EVERY clock domain** · **ALMs 11,232 / 41,910 (27 %)** · **latches 0** · **`lpm_divide` 0**.  Receipt `a658942cff4cceeb…`, 88 input files `fc508a1c4c17228e…`, compile 579 s.  ⚠ The receipt records the tree as `734e11c010-dirty` — the gate ran on the LANDING before its commit, which is the only order in which an RTL change can be gated before it is committed |
| **Y-12** HLT sweeps 279/283, S16 walk 1,320/1,371 | **MET — 97 + 93 + 45 + 44 = 279 / 283** and **1,320 / 1,371** with `w0` **372 / 372**; the S16 residue is still exactly `D_tstate` **24** + `ARCH` **27** and no third class |

### §8.5 THE 10 P1 SEEDS THAT ARE STILL NOT EXACT — REPORTED, NOT EXCUSED

13 of the 23 became EXACT.  The other 10 are itemised rather than counted as a
miss of this law, and **9 of them have their first divergence LATER**, which is
the P1 defect closing with a downstream one remaining:

| seed | first divergence before → after | class |
|---|---|---|
| `wr1/202058` | 1553 → 1779 (**+226**) | DIFF_BOUNDARY |
| `wr1/203121` | 1328 → 3100 (**+1772**) | DIFF_BOUNDARY |
| `wr1/204007` | 984 → 1787 (**+803**) | NO_ENTRY_DIFF |
| `wr1/204092` | 342 → 3469 (**+3127**) | DIFF_BOUNDARY |
| **`wr1/204143`** | **1113 → 1113 (+0)** | NO_ENTRY_DIFF |
| `wr1/206034` | 1314 → 1517 (**+203**) | DIFF_BOUNDARY |
| `wr1/206097` | 634 → 850 (**+216**) | DIFF_BOUNDARY |
| `wr1/210130` | 1468 → 2390 (**+922**) | SAME_BOUNDARY |
| `wr1/212046` | 1888 → 2100 (**+212**) | DIFF_BOUNDARY |
| `wr1/212122` | 2497 → 2722 (**+225**) | DIFF_BOUNDARY |

**`wr1/204143` is the ONE that did not move**, and its divergence at row 1113 is
far UPSTREAM of its contested take at clock 2341 — §4.6a's A-1 shape and §7.9's
own reading, named here rather than absorbed.  Its take clock DID close
(§8.2 scores it MATCH); the seed is not exact for a reason that predates the
entry.

⚠ **ONE GAIN WAS NOT PREDICTED**: `wr1/206062` is not one of the 23 and became
EXACT.  It is reported, not claimed.

### §8.6 THE ENTRY PARTITION MOVED AGAIN, AND IT IS AGAIN NOT A BAR

`w32_launch --core ucore` goes `SAME_BOUNDARY 45 → 15`, `DIFF_BOUNDARY 7 → 20`,
`NO_ENTRY_DIFF 118 → 135`, `COUNT_DIFF 12 → 12`, `UNREADABLE 2 → 2`,
`OPEN_BUS 196 → 196`.

**This is §7.7's shape and the pre-registration DECLINED to register it**,
precisely because W3.4 had to report a bar NOT MET for a landing that lost
nothing.  It is an **ATTRIBUTION counter over a divergent-by-construction
subset**, not a ratchet (`standing_gates.md` says so of the whole 184).  Seeds
whose FIRST divergent entry was P1's now run past it and are classified at a
LATER entry.  Zero seeds left EXACT and zero first divergences moved earlier,
which is what the actual bar (Y-3) measures.

### §8.6a G6, AND THE BITSTREAM THAT WAS NOT FLASHED

`sw/quartus_gate.py`, the CONTROL/DEFAULT build, Quartus 17.1.0 Build 590:

| | |
|---|---|
| E1 `gen_ucore_qsf --check` | **PASS** — the two A/B bitstreams still differ by the CORE and nothing else |
| E2 zero errors | **PASS** — 0 stage errors, 0 error lines; map, fit and asm all Successful |
| E3 Fmax | **PASS — 47.31 MHz** (registered bar **≥ 32**) |
| E4 worst setup | **PASS — +9.226 ns** |
| E5 TNS | **PASS — 0.000 on every clock domain** |
| resources | **ALMs 11,232 / 41,910 (27 %)**, **latches 0**, **`lpm_divide` 0** |

The previous registered figures were 26 % ALMs and 45.56 MHz (U4 pass 3, §52);
this build is **27 % / 47.31 MHz** — one term of combinational logic, and the
fitter's own run-to-run spread is larger than its cost.  **`nec_test.sdc` was
NOT edited.**

⚠ **A BITSTREAM WAS PRODUCED AND NOT FLASHED.**  `nec_test_ucore.sof` and
`.rbf` exist in `hdl/output_files_ucore/`; **the board still carries FLASH
#10** and nothing was opened.  Every fabric column in `standing_gates.md` is a
FLASH #10 figure and is unchanged, because **this landing is not in any
bitstream on the board.**

### §8.7 THE LANDING — **ONE TERM, AND EVERY REASON FOR IT IS A MEASUREMENT**

`hdl/rtl/ucore/v30u_eu_step.svh`, `S_DECODE2`'s ONE_BYTE_LOGIC arm:

```
-  if (q_ripe_lead_n) begin
+  if (q_ripe_lead_n || brk_seen) begin
```

**No flop.  No new state.  No second boundary.  No opcode named.  `sim/`
byte-identical.**  `ss_lint` exits 0 with `SS_VERSION` **0x87** and **205
architectural flops** unchanged, which is what "no flop" means when it is
checked rather than asserted.

Three things it deliberately does NOT do, each for a measured reason:

* **It does not gate `S_1BL_LEAD`.**  The model tests `brk_pending_` **once**,
  at `wait_retire_lead()`'s entry, and then loops.  Gating the wait's body would
  be a second law, and it is the shape W3.4's mirror accidentally had.
* **It does not delete the wait.**  §7.5 falsified that: the odd-`ip` half of
  `loader_impl.h`'s 250/250 golden says the FLAG WRITE does wait for its byte,
  and deleting the queue test moved `FA` (74), `FB` (68) and `INT.FB` (39) —
  181 row-diffs where the ladder is 0.  **Two laws, one call**, and this leg
  separates them by the same single condition the model does.
* **It does not add `irq_shadow`.**  Measured 0 at all 23 decodes (§8.2), for a
  structural reason: every pop state clears it and every opcode is popped by
  one.  Adding an inert term would be machinery the die does not need.

*Falsifier*: any capture in which a `ONE_BYTE_LOGIC` form retiring into a
BRK/TF take has its boundary later than its own opcode pop + 2 with a dry
queue; or any `FA` / `FB` / `INT.FB` golden that moves when this gate is armed
(they fire no trap, so `brk_seen` is 0 in their goldens — checked, not asserted:
`check_core --opcodes all` is 169,000 / 169,000 and `INT.FB` is inside it).

### §8.7a THE DETERMINISM CONTROL

The `ucore` TB was rebuilt from the SAME sources after the ladder was scored
(the content key `dfeb32ead17646f1…` is identical either side; only the receipt
hash moves, because two builds of one tree are two different binaries).  On the
fresh binary `w32_launch --core ucore` re-reads **91 / 184 with a
byte-identical entry partition**.  A landing whose number depended on a
particular build would have shown here.

### §8.8 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  No `div_guard`, no
  `board_idle` — nothing was opened.  The board still carries FLASH #10, so
  every figure here is OFFLINE and **none is a fabric figure**.  ⚠ The landing
  is in RTL and **not in any bitstream**; the fabric columns are unchanged
  because nothing was flashed.
* **The victory reserve (`k ≥ 300000`) was NOT touched.**
* **The MODEL (`sim/`) was NOT touched.**  W3.4's landing is the semantic
  reference; this is the `ucore`'s rendering of it, edge-for-edge on OBSERVABLE
  behaviour and not line-for-line on structure.  The model's own columns
  (1,343 / 802 / 2,145, `wr1` 84 / 184) are unchanged and were not re-run.
* **Candidates U-A and U-C were NOT BUILT** — U-A because §8.2 refutes it before
  a build, U-C because the pre-registered selection rule only reaches it if U-B
  loses something, and U-B lost nothing.
* `mc1/721`, `mc2/584`, the §5.6a / §5.6b modes, H3-B and the 8080/BRKEM family
  were NOT opened.
* **No memory file was touched and Codex was not launched.**
* ⚠ **One mis-invocation is recorded rather than hidden**: `--ss-sweep 1` was
  first run as if `1` were a MODE; it is a STRIDE, and the run was an
  unbounded sweep over every case.  It was killed and the REGISTERED forms
  (`--ss-mode 1` / `2` / `5`) were run instead.  Nothing was scored off the
  wrong invocation.

---

## §9 W4 — **THE VICTORY SITTING.  THE BAR IS MET.  `T` = 90.0170 % AGAINST A BAR OF 86.6681 % FROZEN AT W2, ON A FRESH DISJOINT TRANCHE NO ENGINE HAS EVER SEEN, IN FABRIC, AGAINST SILICON.**

**2026-08-06, branch `ucsim`, from HEAD `51139e5cde`.  BOARD SESSION, FLASH #11
TAKEN.**  Pre-registration: `docs/notes/wrfuzz_w4_prereg_2026-08-06.md`,
committed at **`b66c4702c4` before any board contact and before the flash**,
with two addenda (`f99660b9c9` §3.4a, `6f58a9b157` §2.0a) **also before the
board was touched and before any tranche number existed**.  Driver:
`sw/wrfuzz_w4.py`.  Prediction instrument: `sw/wrfuzz_w4_predict.py`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

### §9.1 THE HEADLINE

> **VICTORY: MET.**  The 196-seed stratified body, drawn from `k ≥ 300000` and
> **disjoint from every survey seed by construction**, scores
> **`T` = 90.0170 %** — the unweighted mean of the 28 per-stratum
> hardware-versus-silicon cycle-exact rates, the identical construction that
> produced `S` — against the **FROZEN `B` = 86.6681 %**.  **+3.3489 points.**
> Both `MET` conditions hold: `T ≥ B`, **and** every one of the 12 scored
> non-exact seeds' first divergence falls in a family named in the W2 census's
> taxonomy (`SCHEDULE` 7 · `PF_LOST` 2 · `DATA_SEQ` 2 · `PIN` 1, **catch-all
> EMPTY**).
>
> **The plan's other reading agrees and is reported beside it**, as registered:
> the pooled conversion is `floor(86.6681 % × 141) = 122` seeds and the measured
> exact count is **129**.  The two readings do not disagree, so nothing had to
> decide between them.
>
> **NINE CAPTURE-INTEGRITY BARS, NINE MET, NOTHING VOID.**  296 seeds, **912
> seed-loops in 2.6 minutes**, **0 quarantines, 0 transport errors, 0 unstable
> cells over 296 × (3 or 5) repetitions on both A/B legs**, `div_guard`
> **PINNED on 33 of 33 probes**, and **B-1 = 100.00 % over 43,266 bus cycles**
> — the vector the rig applied was the vector it was handed, on every capture,
> every cycle.
>
> **AND THE FABRIC RE-BASE REPRODUCED EVERY REGISTERED PREDICTION CELL FOR
> CELL**: the HLT sweeps **279 / 283** with **0 PASS/FAIL disagreements and 0
> differing first-divergence coordinates against the fresh `ret` column over all
> 283**, the four failures being the four cells NAMED IN ADVANCE at the
> coordinates named in advance; the S16 walk **1,347 / 1,371** with **0
> disagreements and 0 differing coordinates over all 1,371**, its 24 failures
> being the four family-D coordinates × the six frozen programs and **nothing
> else**.  Socket controls **49 / 49** and **41 / 41**.

### §9.2 FLASH #11 — THE BITSTREAM, AND WHAT WAS GREEN BEFORE IT

**G6 at HEAD on a CLEAN tree is the promotion receipt**, run and green before
the pre-registration was committed.  W3.5's receipt was NOT reused: it records
the tree as `734e11c010-dirty`, and a promotion receipt for a flash must name a
committed tree.

| | CONTROL/DEFAULT (the GATE) | RETENTION (the FLASHED build) |
|---|---|---|
| E1 `gen_ucore_qsf --check` | **PASS** | (control's) |
| E2 errors / stages | **0 / 0**, map·fit·asm Successful | **0**, all four stages Successful |
| E3 Fmax (bar ≥ 32) | **47.31 MHz** | **46.74 MHz** |
| E4 worst setup | **+9.226 ns** | **+6.724 ns** |
| E5 TNS, setup AND hold, every domain | **0.000** | **0.000** |
| ALMs / latches / `lpm_divide` | **11,232 / 41,910 (27 %)** · 0 · 0 | **11,332 (27 %)** · 0 · 0 |
| receipt | **`b9a27bcf5c6427d4…`** | **`7aef327c763f0d65…`** |
| tree | **`51139e5cde`, `dirty_tracked: false`** | same `hdl/` |
| input manifest | **88 files `fc508a1c4c17228e…` — BYTE-IDENTICAL to W3.5's**, the check that says `hdl/` has not moved since the take-clock term landed | `1ee7778b027a6920…`, the §80.B.1 artefact (Quartus appends pin assignments to the revision `.qsf` before it is parsed); **RECORDED, not barred** |

**⚠ THE MACRO'S EFFECT IS CHECKED, NOT ASSERTED.**  The retention `.sof`
**`82b4935092d6fb99…`** is DIFFERENT from the control build's
**`d2dc04fe8d2186ff…`** produced from the same tree minutes earlier.  A
`--verilog_macro` that never reached the compiler would have produced the same
bitstream.  The `.qsf` was restored from the generator afterwards and
`gen_ucore_qsf --check` is green.

**WHY THE RETENTION BUILD IS THE ONE FLASHED**, stated in the pre-registration
before the number existed: it is the **resting configuration** (FLASH #6, #9 and
#10 were all retention builds), and **the whole W1 corpus — and therefore `S`
itself — was captured on one.**  A control-build FLASH #11 would have silently
changed the comparator that produced the frozen bar.  The retention is on the
OBSERVATION path (`hb_ad_sample`) only, so the `use_core=0` socket position is
unaffected by construction and is MEASURED unaffected below.

**FLASH #11** through `sw/safe_flash.sh` with its VERIFY leg:
`nec_test_ucore.sof`
**`82b4935092d6fb99644227ee2c1f08b4eaaeb4f0661351e00a07902f121e23b0`**,
`.rbf` **`9363a7c72c9f9dca00b32e26b7b4a7bb6a7c66bebd6b22cc05b9c00dc49f23fc`**,
VERIFY **OK** (`pwr_good True`, `cpu_running True`, `cfg 0x1ff0008`, `use_core
False`), `flash_log.jsonl` 13 → **14 entries**.  **It is the first bitstream to
carry the `ucore`'s take-clock term** (W3.5's `q_ripe_lead_n || brk_seen`).
First light immediately after the flash: **`check_ab_hw all 800` MATCH on all
three legs.**

### §9.3 THE TRANCHE, AS REGISTERED

`sw/testdata/wrfuzz/victory_population.json`, sha256 **verified
`dcaa48fa991f…`** before it was read.  `cid = wr2`, **196 body seeds** over the
same 28 strata + **four directed cells × 25**, **3 repetitions** and **5 on the
12 promotion cells** = **912 seed-loops**, the frozen count exactly.

| i | stratum | n | OPEN_BUS | scored | exact | **rate %** | predicted % | W2 % |
|---|---|---|---|---|---|---|---|---|
| 0 | soup/fix0 | 7 | 0 | 7 | 7 | **100.00** | 96.00 | 95.33 |
| 1 | soup/fix1 | 7 | 0 | 7 | 7 | **100.00** | 98.67 | 96.67 |
| 2 | soup/fix2 | 7 | 0 | 7 | 7 | **100.00** | 96.67 | 95.33 |
| 3 | soup/fix3 | 7 | 0 | 7 | 6 | **85.71** | 98.00 | 95.33 |
| 4 | soup/wrand1 | 7 | 0 | 7 | 7 | **100.00** | 97.33 | 97.33 |
| 5 | soup/wrand2 | 7 | 0 | 7 | 7 | **100.00** | 98.00 | 94.00 |
| 6 | soup/wrand3 | 7 | 0 | 7 | 7 | **100.00** | 98.67 | 96.00 |
| 7 | soup/wrand7 | 7 | 0 | 7 | 6 | **85.71** | 96.00 | 95.33 |
| 8 | soup/wrand15 | 7 | 0 | 7 | 7 | **100.00** | 100.00 | 96.00 |
| 9 | soup/wvec-uni | 7 | 0 | 7 | 7 | **100.00** | 98.67 | 98.00 |
| 10 | soup/wvec-walk | 7 | 0 | 7 | 7 | **100.00** | 96.67 | 92.00 |
| 11 | soup/wvec-skew | 7 | 0 | 7 | 6 | **85.71** | 100.00 | 98.67 |
| 12 | soup/wvec-burst | 7 | 0 | 7 | 7 | **100.00** | 97.33 | 95.33 |
| 13 | soup/wvec-edge | 7 | 0 | 7 | 7 | **100.00** | 100.00 | 100.00 |
| 14 | raw/fix0 | 7 | 4 | 3 | 3 | **100.00** | 81.25 | 81.25 |
| 15 | raw/fix1 | 7 | 3 | 4 | 3 | **75.00** | 80.56 | 80.56 |
| 16 | raw/fix2 | 7 | 6 | 1 | 1 | **100.00** | 92.31 | 92.31 |
| 17 | raw/fix3 | 7 | 3 | 4 | 2 | **50.00** | 89.66 | 86.21 |
| 18 | raw/wrand1 | 7 | 4 | 3 | 2 | **66.67** | 72.00 | 68.00 |
| 19 | raw/wrand2 | 7 | 5 | 2 | 2 | **100.00** | 87.50 | 87.50 |
| 20 | raw/wrand3 | 7 | 6 | 1 | 1 | **100.00** | 78.38 | 78.38 |
| 21 | raw/wrand7 | 7 | 3 | 4 | 3 | **75.00** | 93.33 | 93.33 |
| 22 | raw/wrand15 | 7 | 4 | 3 | 3 | **100.00** | 93.33 | 93.33 |
| 23 | raw/wvec-uni | 7 | 6 | 1 | 1 | **100.00** | 96.15 | 96.15 |
| 24 | raw/wvec-walk | 7 | 4 | 3 | 2 | **66.67** | 89.29 | 89.29 |
| 25 | raw/wvec-skew | 7 | 4 | 3 | 2 | **66.67** | 90.32 | 87.10 |
| 26 | raw/wvec-burst | 7 | 2 | 5 | 4 | **80.00** | 91.30 | 91.30 |
| 27 | raw/wvec-edge | 7 | 1 | 6 | 5 | **83.33** | 96.67 | 96.67 |

**scored 141 of 196** (55 OPEN_BUS, all raw tier, 0 soup), **exact 129**,
pooled **91.49 %**.  **`T` = 90.0170 %.**  **No stratum came back with an empty
scored denominator**, so §2.1's rule was armed and never needed: the mean is
over all **28**.  **B-5 fired on 0 seeds and instability on 0**, so OPEN_BUS
was the only exclusion that had any members — exactly the survey's shape.

### §9.4 THE PREDICTION, AND IT IS REPORTED AGAINST — NOT IN PLACE OF — THE BAR

The registered point prediction was **`T` = 93.0017 %** with a registered 95 %
band of **[87.82 %, 98.18 %]**.

> **MEASURED 90.0170 % — INSIDE the registered band, and 2.985 points BELOW the
> point prediction, i.e. 1.13 standard errors low.**  Reported as registered,
> not restated.

**WHERE THE PREDICTION WAS WRONG, ITEMISED.**  The shortfall is **not** noise
spread evenly; it has a shape, and the shape contradicts the reading §3.2
registered:

* **SOUP BEAT THE PREDICTION AND THE MISS IS ELSEWHERE.**  Soup measured
  **95 / 98** pooled, mean **96.94 %**, against a predicted soup mean of
  **97.71 %** — within noise, and **eleven of the fourteen soup strata are
  100.00 %**.  The three that are not (`fix3`, `wrand7`, `wvec-skew`) are one
  seed each.
* **RAW CARRIED THE WHOLE SHORTFALL**: **34 / 43** pooled, mean **83.10 %**,
  against a predicted raw mean of **88.29 %**.  ⚠ **AND §3.2's REGISTERED
  READING SAID THE OPPOSITE** — it predicted the four W3 landings would close
  soup seeds (41 of the 43 predicted closures were soup) and leave raw
  untouched, so raw was predicted to reproduce W2 *unchanged*.  It did not
  reproduce W2; it came in **5.2 points below its own W2 column**.
* **THE HONEST ARITHMETIC**: the raw strata carry **1 to 6 scored seeds each**
  after the OPEN_BUS exclusion, so one seed is worth 16-100 points of a
  stratum's rate and the 28-stratum mean inherits that.  `raw/fix3` at
  **50.00 %** is *two seeds of four*.  This is the design property registered
  in §3.1 as *"not a comfortable bar, a bar that a bad draw on the raw side can
  reach"*, arriving as a measurement.  **It is BOOKED, not explained away** —
  see §9.8.

### §9.5 THE RESIDUE — 12 SEEDS, FOUR FAMILIES, CATCH-ALL EMPTY

| family | n | at W2 (3,150 seeds) |
|---|---|---|
| `SCHEDULE` | **7** | 42 |
| `PF_LOST` | **2** | 43 |
| `DATA_SEQ` | **2** | 23 |
| `PIN` | **1** | 7 |
| `PF_GAINED` | **0** | 18 |
| `PF_ADDR` | **0** | 2 |
| `NOW_EXACT` | **0** | 1 |
| catch-all / classify error | **0** | **0** |

**Condition 2 of `MET` is satisfied at 100 %** — the V3 precedent's own bar.
⚠ **`PF_GAINED` IS EMPTY.**  At W2 it was 18 seeds with ONE geometry, `has_tf`
true on 18 of 18, and §3.5 named it as the invariant that shapes W3.  W3.1-W3.5
landed on exactly that axis; the tranche's `PF_GAINED` column is **0**.  On 141
scored seeds that is **not proof of closure** — W2's rate would predict about
one — and it is recorded as consistent, not as established.

### §9.6 THE FOUR DIRECTED H3-B CELLS — **THE REGISTERED NEGATIVE FIRES, AT §68.6's OWN SCALE**

`skew`, `blk = 32`, the deepest block interior — §65.2's *"steady state, never
flushed"*, the one of its three stimuli never tried.  Class-B observable:
**same clock, different owner**, chip against the fabric core, paired by
ordinal, `sm3_h3_cell.measure` imported.

| cell | tier | `wlo`/`whi` | seeds | exact | **(a) paired accesses, EXACT seeds** | **class-B** | (b) all seeds | class-B |
|---|---|---|---|---|---|---|---|---|
| **D1** | soup | 0 / 7 | 25 | **25** | 1,305 | **0** | 1,305 | 0 |
| **D2** | soup | 1 / 15 | 25 | 24 | 1,021 | **0** | 1,182 | 0 |
| **D3** | raw | 0 / 7 | 25 | 20 | 3,228 | **0** | 4,173 | 1 |
| **D4** | raw | 1 / 15 | 25 | 18 | 1,741 | **0** | 2,110 | 0 |
| | | | **100** | **87** | **7,295** | **0** | **8,770** | **1** |

> **ZERO class-B pairs over 7,295 paired accesses in the block interior** —
> and 7,295 is **§68.6's own 7,254 to within half a percent**, which was not
> arranged and is reported because it makes the two numbers directly readable
> against each other.  **§68.6's negative REPRODUCES under a stimulus it was
> explicitly not able to reach.**  Class B is now not at a queue-occupancy
> threshold (§63.6), not in a byte-step sweep (§65.2), not in a clock-step
> sweep of the eligibility instant (§68.6), **and not in steady state inside a
> 32-access wait block.**  All four of the stimuli anyone has named have now
> missed.
>
> **D1 IS 25 / 25 CYCLE-EXACT** — a whole directed cell of `skew` soup seeds
> reproduced clock for clock from RESET to the done marker.

**⚠ AND §3.4a's REGISTERED TRAP FIRED EXACTLY WHERE IT WAS PREDICTED TO.**  The
(b) population — every seed, pairing ambiguous past a divergence — reports
**one** class-B pair, in **D3**, on `wr2/330039` at access #89 (`chip MEMW` vs
`fabric MEMR`, occupancy 6), a seed that is **not cycle-exact**.  That is the
pairing artefact §3.4a described in advance, in the population §3.4a labelled
in advance, and it is **NOT a class-B event**.  Had the split been made after
the numbers were seen it would have been indistinguishable from choosing a
statistic to get a zero.

### §9.7 THE BARS — **9 / 9 MET, NOTHING VOID**

| bar | registered | **measured** |
|---|---|---|
| **B-1** the vector was APPLIED | ≥ 99.9 %, expected 100.0 % | **100.00 % — 43,266 / 43,266 bus cycles, 0 seeds with a mismatch.**  Evaluated on the WHOLE tranche, not a sub-sample, because §5.1 retained every capture's rows |
| **B-2** era on every capture | 0 absent or mixed | **0 absent; exactly ONE distinct `sof_sha256` over all 296** = FLASH #11, with `rtl.receipt_id` `7aef327c763f0d65…`, `gen_git cd6f457775`, `rig_evt_hold_bits 12` |
| **B-3** the vector is banked in full | 0 mismatches | **0 specs without `wvec_hex`, 0 wrong lengths** |
| **B-4** no gen-drift | 0 | **0 GEN_DRIFT over all 296**, evaluated before board time was spent |
| **B-5** the bus-cycle bound | 0 at or beyond 4,096 | **0** |
| **B-6** BRKEM-free | 0 pairs | **0 `0F FF` pairs over 296 composed images** |
| **B-7** board discipline | `div_guard` PINNED on 100 % of probes | **PINNED on 33 / 33**; socket-vs-fabric A/B differing only in `use_core`; every capture's rows retained with sha256 and a `SHA256SUMS`; `board_idle()` at the close with `use_core=0` |
| **B-8** transport | breaker not tripped | **0 quarantines, 0 transport errors in 912 seed-loops** |
| **B-9** the capture is stable | 158 / 158 at W1's sub-sample; here 296 / 296 | **296 / 296 STABLE**, rep 1 against every later rep on BOTH A/B legs, **0 bad rows and 0 flicker rows** across 912 captures |

### §9.8 THE FABRIC RE-BASE — EVERY PREDICTION MET CELL FOR CELL

The offline references were **RE-TAKEN ON THIS TREE BEFORE THE BOARD WAS
TOUCHED** (§83.0/§83.0b's lesson applied, not re-learned), and both reproduced
FLASH #10's era exactly — which was itself the registered prediction that the
four W3 landings touch neither population.

| leg | offline reference (re-taken) | **IN FABRIC on FLASH #11** |
|---|---|---|
| the four HLT sweeps | `x1_retention` `offline` **279/283**, `ret` **279/283**; BAR (i) 245 closed / **0 SURVIVED**, BAR (ii) **0 cells differing** | `x1_fabric fab_f11` **279 / 283** — **0 PASS/FAIL disagreements and 0 differing first-divergence coordinates against `ret` over all 283**.  Per suite **48/48 · 49/49 · 44/46 · 49/49 · 20/21 · 25/25 · 19/20 · 25/25**.  The four failures are the four NAMED IN ADVANCE, at the coordinates named in advance: `s10-w1/HLT.INT/8` and `/9` at (11, `pins`), `s13-w2/HLT.INT/12` at (13, `pins`), `s13-w3/HLT.INT/15` at (15, `pins`) — family D, and nothing else |
| the S16 directed display walk | `sm3_s16_fabric offline` **1,347/1,371**, `vsys_ret` **1,347/1,371**, 0 disagreements | `fab_f11` **1,347 / 1,371** — **0 PASS/FAIL disagreements and 0 differing coordinates over all 1,371**.  Its **24** failures are the four family-D coordinates (`HLT.INT` 8, 9, 12, 15) × the six frozen programs, **catch-all EMPTY** |
| socket controls | — | `x1_fabric soc_f11` **49 / 49**; `sm3_s16_fabric soc_f11` **41 / 41**, 0 disagreements vs `offline` |
| first light / close | — | `check_ab_hw all 800` **MATCH ×3** after the flash; **`use_core=0` chip proof MATCH over 800 rows after everything**, which is the measurement that the retention build leaves the socket position untouched |

### §9.9 WHAT THIS SITTING BOOKS FOR THE SUCCESSOR QUEUE — **BOOKED, NOT FIXED**

Nothing below was touched.  No mechanism work was done in a sitting that was
also scoring a bar.

| # | item | evidence |
|---|---|---|
| **W4-1** | **THE RAW TIER IS THE CAMPAIGN'S REMAINING AXIS, AND IT IS NOT THE TF AXIS.**  Raw scored 34/43 (mean 83.10 %) against soup's 95/98 (96.94 %), and §3.2's registered reading — that the W3 landings are a soup/TF phenomenon and raw would reproduce W2 unchanged — is CONTRADICTED: raw came in 5.2 points below its own W2 column | §9.4 |
| **W4-2** | **THE OPEN_BUS EXCLUSION COSTS THE RAW TIER ITS RESOLUTION.**  55 of 98 raw body seeds excluded; strata left with 1-6 scored seeds each, so one seed moves a stratum 16-100 points and the 28-stratum mean inherits it.  A future tranche wanting per-stratum raw resolution must oversample raw, not draw it 7-per-stratum | §9.3, §9.4 |
| **W4-3** | `SCHEDULE` is **7 of 12** of the residue — the largest family, and larger in share than at W2 (42 of 136).  Not diagnosed here | §9.5 |
| **W4-4** | `PF_GAINED` is **0 of 141**, consistent with W3.1-W3.5 having closed §3.5's invariant, **NOT established** at this population size | §9.5 |
| **W4-5** | The directed cells' vectors are **not all distinct** — D1 draws 22 distinct vectors for 25 seeds, D2 19, D3 23, D4 20 — because the cells SELECT seeds whose `skew` spec matches `(blk 32, wlo, whi)` and the spec does not determine the whole vector's identity. A `force_wvec_spec` knob (W2's own booked gap) would remove the coincidence | `w4_preflight.json` |
| **W4-6** | **Class B has now missed under all four named stimuli.**  Either it does not exist as an observable of this design, or nobody has yet named the stimulus.  A campaign should say which it believes before designing a fifth cell | §9.6 |

### §9.10 WHAT THIS SITTING DID NOT DO

* **NO MECHANISM WORK.**  `git diff` over `hdl/rtl`, `hdl/tb` and `sim/` across
  the whole sitting is **EMPTY** — nothing landed in either engine after the
  bitstream was built, and nothing landed at all in `sim/`.
* **`S` and `B` were NOT re-derived.**  `B = 86.6681` is a literal constant in
  `sw/wrfuzz_w4.py`; `S` was re-computed only as a REPRODUCTION CHECK on the
  W2 artifact (91.6681 %, to four decimals) and never as a new value.
* **The comparator was not swapped.**  The scorer is `capture_board`'s own
  inline chip-vs-fabric verdict, chosen at W0 and untouched.
* **No stratum was dropped, the tranche was not re-drawn**, and the empty-
  stratum rule registered in §2.1 was armed and never needed.
* **No memory file was touched and Codex was NOT launched** — the coordinator
  runs the campaign-close review.
* **No new gate was invented.**  `standing_gates.md`'s fabric rows are RE-BASED
  to FLASH #11 and the tranche figure is registered as a FIRST REGISTRATION,
  not as a ratchet.
* The board is left carrying **FLASH #11**, `use_core` **False**, `div_guard`
  PINNED, `board_idle()` clean.
