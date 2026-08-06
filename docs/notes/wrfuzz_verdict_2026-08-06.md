# THE RANDOM-WAIT FUZZ CAMPAIGN (wrfuzz, task #38) — VERDICT

**FINALIZED at W6 after the Codex closing review (GO-WITH-CONCERNS, seven
concerns, all applied).  ⚠ It is NOT ACCEPTED: acceptance is the user's and is
not recorded as given.**  See the REVIEW TRAIL at the foot.

**Phase**: 2026-08-05 → 2026-08-06, branch `ucsim`, sittings **W0**, **W1**,
**W2**, **W3.1 – W3.5**, **W4** and the finalization sitting **W6**.  Ledger: `docs/notes/wrfuzz_provenance.md`
**§1 – §9**.  Plan: `docs/notes/wrfuzz_campaign_plan.md`.  Corpus
pre-registration: `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md`.  Survey /
census: `docs/notes/wrfuzz_survey_2026-08-05.md`.  Gate authority:
`docs/notes/standing_gates.md`.  Invalidation register:
`docs/notes/invalidation_ledger.md` (**not touched this campaign — INV-1
remains the project's only invalidation**).

> **Standing principle, applied in every sitting's brief and quoted verbatim in
> every one of them.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

**This document CITES.  It does not measure.**  Every figure is quoted from the
ledger, the survey, the pre-registrations or `standing_gates.md`, with its
section named.  **Six items were spot-verified against the artifacts for this
document** and are marked ⓥ where they appear:

| ⓥ spot-verified | result |
|---|---|
| `T` recomputed from §9.3's own 28 per-stratum exact/scored counts | **90.0170 %** — the ledger's figure to four decimals |
| `S` recomputed from the survey §1's own 28 rows | **91.6681 %**; `B = S − 5.0` = **86.6681 %** |
| `floor(0.866681 × 141)` | **122** seeds against a measured **129** |
| `sha256 sw/testdata/wrfuzz/victory_population.json` | **`dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d`** — the value frozen at W2 |
| `sw/testdata/wrfuzz/w4_score.json` fields | `T` 90.01700680272108 · `B_frozen` 86.6681 · `pooled` 129/141 · `n_rates_averaged` **28** · `unnamed` **[]** · B-1 **43,266 / 43,266** · B-9 **296 stable, 0 flicker** |
| `sw/testdata/wrfuzz/w2_strata.json` | `S` 91.6680668… · `B` 86.6680668… · pooled 2,379 / 2,515; both alternative exclusions present and unused |

**No engine was touched, no board was contacted, and no figure in this document
is new.**  ⚠ **One thing changed at W6 and it is stated rather than left to be
noticed**: finalization REGISTERED a standing gate — `sw/wrfuzz_wr1_guard.py`,
the `wr1` offline guard — and **ran its two legs once to prove it green**.  They
reproduced the receipted columns exactly (model **84 / 184**, `ucore`
**91 / 184**, 0 lost, 0 moved earlier), so **no figure here moved**; but *"no
gate was re-run"* is no longer true of this document and the earlier wording has
been withdrawn rather than kept.  §(f.3).

---

## (a) THE DIRECTIVE, THE PLAN'S STAGE GATES, AND EACH ONE'S TERMINAL STATE

### (a.1) The directive

The user closed the silicon-match phase on 2026-08-05 (*"Okay.  Let's close
this campaign"*, `sm3_verdict_2026-08-05.md` head) and directed **a successor
campaign focused on fuzz testing with random waits**.  That is the whole
directive, and the plan reads it against the project's own standing priority:

> **Wait-state cycle accuracy is the project's standing #1 priority** —
> *arbitrary-wait accuracy beats w0, and the target is a random-wait
> physical-versus-core match* (`wrfuzz_campaign_plan.md` §1).  Every campaign
> since ucsim-t has moved that number and **none has been about it directly**.

The plan's answer to *"what is new here"* is one sentence and it is a stimulus,
not a mechanism: the rig has had a **PER-ACCESS WAIT VECTOR** since Phase 2a —
an explicit host-specified Tw count for every bus cycle, applied by the same
buffer to the socketed chip and to the fabric core — and it had been driven
**exactly twice** (`timed_wvec_gate`'s frozen 88-cell corpus; §68.6's directed
H3-B cell) and **never by a fuzz corpus** (plan §1).

**Governance carried in full and restated so it could not be assumed away**
(plan §2): SILICON MATCH is the only correctness bar; pre-registration before
every run; directed cells over fitted tables; §64.1's disjoint validation;
`sim/`-first routing for shared mechanisms; monotone ratchets; receipts and era
guards on every artifact a number is computed from; Codex at phase boundaries;
`CLAUDE.md`'s board discipline in full.

### (a.2) The stage gates, and where each one ended

| stage | what the plan required | **terminal state** |
|---|---|---|
| **W0** — corpus design and pre-registration | plan + corpus prereg committed, generator extensions, a ≤ 20-seed smoke through BOTH offline engines, the W1 bars, W2's deliverable shape, the ledger opened.  **No board, no generation at scale, no mechanism work** | **CLOSED, exit condition met** (§1).  Both prereg documents committed; `sw/wvec_shapes.py` new; the full-scale lint **PASS** (10,000 soup / 100,000 raw / 400 wvec, hits 0); the 20-seed smoke **100.00 % applied on both engines**, stamped `"nongate": true`.  `git diff` over `hdl/` and `sim/` EMPTY.  **Three findings booked (F-1, F-2, F-3) and one instrument catch (F-4)** |
| **W1** — socket capture | generate and capture the pre-registered corpus, one `capture_board` per seed (socket then fabric, differing only in `use_core`).  **Measure and report; do not diagnose.**  Bars B-1…B-9 and nothing else | **CLOSED, 9 / 9 BARS MET** (§2).  **3,150 / 3,150 seeds, all 28 strata at their registered size**, 6.4 min of capture and **7.6 min total board time against a registered ≤ 30**; 0 transport errors, 0 quarantines, 0 provenance alarms, `div_guard` PINNED **33 / 33**, `board_idle()` clean, `use_core=0` left selected.  Deviations committed **before** board contact (`wrfuzz_w1_execution_note_2026-08-05.md`).  **Two findings (F-5, F-6) and one positive (F-7)** |
| **W2** — the survey | run the full batch, categorise **all** failures, plan nothing.  One census over one tree; **`S` computed by §5's registered formula and FROZEN** | **CLOSED** (§3, `wrfuzz_survey_2026-08-05.md`).  3,150 scored hardware-versus-silicon, 635 OPEN_BUS-excluded, **2,515 scored / 2,379 exact (94.59 % pooled)**; **`S` = 91.6681 %** and **`B` = 86.6681 %** FROZEN ⓥ; victory tranche drawn and frozen at sha256 `dcaa48fa991f…` ⓥ.  **Nothing landed** — `git diff` over `hdl/` and `sim/` EMPTY.  **Five findings (F-8 … F-12)**, one of them a vacuous-instrument catch in the sitting's own counter |
| **W3+** — mechanism sittings | one mechanism per sitting, each with its own pre-registration, its own directed cell where the bank cannot discriminate, its own falsifier; shared mechanisms land `sim/` first; the full ladder re-scored between sittings | **FIVE SITTINGS RUN, W3.1 – W3.5.**  **Three landings** (W3.1 both engines, W3.4 `sim/`, W3.5 `ucore`), **two sittings that landed nothing by their own pre-registered rules** (W3.2, W3.3).  Every landing scored **ZERO LOST, ZERO first divergences moved earlier**, seed by seed, against a baseline measured on the sitting's own tree.  §(c) |
| **VICTORY** | a pre-registered numeric bar on a **fresh stratified tranche**, **scored IN FABRIC, hardware-versus-silicon**, the number registered from the survey and **never after** | **MET** (§9).  **`T` = 90.0170 % against the frozen `B` = 86.6681 %, +3.3489 points**, condition 2 satisfied on **12/12 scored non-exact seeds** (the denominator was **141 scored = 129 exact + 12 non-exact**), nine capture-integrity bars met, nothing VOID.  §(e) |

### (a.3) The scope decisions the campaign inherited or took, and who took them

| item | disposition | authority |
|---|---|---|
| **H3-B — the grant-order swap** | **RE-ENTERED SCOPE.**  Its SM3 deferral was campaign-scoped and it is a random-wait ARBITRATION mechanism | the campaign directive; plan §2 |
| **8080 / BRKEM** | **DEFERRED — carried.**  Corpora BRKEM-free **by construction**, by a generation axis and not by post-filtering | user decision 2026-08-05; SM3 verdict §(a.3) |
| **the model-only residue** | **FROZEN — carried** | user decision 2026-08-05 |
| **V5** | **SEALED — carried.**  A standing REGISTERED FAILURE, not re-opened, not re-negotiated, and **not re-scored by this campaign** | ucsim-t; SM3 verdict §(d.3) |
| **the pin-event (EVT) axis** | **OUT of W0-W2 by design** — a brand-new wait axis crossed with the pin axis confounds two things at once.  An EVT × vector cell is NAMED and reserved | plan §2 / §6.  ⚠ **It was never taken**: no wrfuzz sitting ran an EVT × vector cell |
| the SM3 nine catch-all seeds / the 27 `ARCH` cells | **not this campaign's**; the survey counts them where they appear and does not chase them | SM3 verdict §(f); plan §7 |

**One reading of the bar was resolved in advance rather than after the count**
(`wrfuzz_w4_prereg_2026-08-06.md` §2, §2.0a): the deciding statistic is `T`, the
unweighted mean of the 28 per-stratum rates — *the same registered construction,
independently implemented for W4; the strata definitions and OPEN_BUS detector
are imported from W1/W2, while the aggregation is repeated and its result was
artifact-cross-checked* (`w1.STRATA` and `w2.open_bus` are imported by
`sw/wrfuzz_w4.py`; the per-stratum tally and the mean are its own loop, and the
cross-check is this document's ⓥ recomputation of `T` from §9.3's own 28
exact/scored counts) — with the plan's pooled
seed-count conversion **computed and reported beside it**; condition 2's
"family named in the W2 census's taxonomy" is `s15_census`'s **eight**-family
set, so `TAIL_EXTRA` / `TAIL_MISS` (zero at W2) **count as named**, and
`NOW_EXACT` was located **in the banked W2 census with one member** before the
tranche existed.  ⚠ *This is a broadening of the plan's literal words (§9's
"named in §3's taxonomy" could have been read as "the six families W2
populated"), and it is registered as a broadening before any tranche number
existed.  It did not bite: the tranche's twelve non-exact seeds fell in four
families W2 populated, and `unnamed` is the empty list in `w4_score.json`* ⓥ.

---

## (b) THE CORPUS AND THE RIG RECORD

### (b.1) The axis, and the one limit that is a number

A wait VECTOR is one Tw count per BUS CYCLE, indexed by the bus-cycle ordinal
from the run's start, and **four implementations index it by that one ordinal**
— `wvec_buf.sv` on the board (which serves `use_core=0` and `use_core=1` from
the SAME buffer), `tb_v30_core.sv`'s `+wvec`, and the model's `next_waits`
(prereg §1.1).  The index agreement was already MEASURED before this campaign:
**45,699 / 45,699 = 100.0 %** over 186 socket captures (§68.6 bar R0).

**THE LIMIT IS 4,096 BUS CYCLES**, and past it the three legs do **three
different things** — the board WRAPS, the model falls back to the uniform
level, and the TB performs an out-of-range read of `wvec_arr[0:4095]` whose
value the language does not define.  It is a **BAR (B-5)**, not an argument.
Three rig properties were booked as **design rules rather than observations**:
always exactly 4,096 entries (the board's replay RAM is **not cleared between
runs**); values 0…31 only (a larger value is *a false statement in the ledger
about what the part was told*, not a divergence); and the two engines' file
encodings are **different and the mismatch is silent** — F-3.

**Five shapes, at most four parameters each** — `uni`, `walk`, `skew`, `burst`,
`edge` — with the standing principle applied to the corpus itself: *"five vector
shapes with four parameters each, not a family of stimuli tuned until a number
moves"* (plan §1).

### (b.2) The corpus, and BRKEM-free by construction

**2 tiers × 14 wait sources = 28 strata; 150 per soup stratum, 75 per raw =
3,150 seeds, `cid = wr1`**, every seed's k named before it was generated
(prereg §2.2), sized for **per-stratum resolution** (±4.8 points at n = 150,
±6.8 at n = 75) and not for board time.  **The nine existing wait classes are
in the corpus as CONTROLS**, generated in the same sittings and captured in the
same session, *so the new axis is read against them and never against a
remembered number*.

**BRKEM-free is a generation axis in three places, and the knob alone is not
the mechanism — measured.**  With `p_brkem = 0` and the image pass off,
**118 `0F FF` pairs survive in 114 of 1,500 soup seeds (7.6 %)**, from an
immediate byte meeting the next opcode; with the full mechanism, **0 pairs**
(§1.3, F-2).  Across 100,000 raw images the generator scrub removed **70,578**
pairs (§1.5).  **B-6 measured 0 pairs over the 3,150 composed images**, and
over W4's 296.

⚠ **And the prereg said in advance what that does NOT do**: *a BRKEM-free corpus
is not an 8080-free corpus*.  It landed in 8080 mode **12 times** anyway
(F-11) — see §(c.3).

### (b.3) The capture record, and the bars

| | **W1 (3,150 seeds)** | **W4 (296 seeds, 912 seed-loops)** |
|---|---|---|
| **B-1** the vector was APPLIED | **48,042 / 48,042 = 100.0000 %** over the 127 retained socket captures carrying a vector — **at the expectation, no finding** | **43,266 / 43,266 = 100.00 %**, on the WHOLE tranche because §5.1 retained every capture's rows ⓥ |
| **B-2** ERA | **1 distinct era over 3,150 lines**, 0 absent, 0 incomplete | **0 absent; exactly ONE distinct `sof_sha256` over all 296** = FLASH #11 |
| **B-3** the vector banked IN FULL | 1,125 vector seeds; 0 bad length, 0 bad sha, **0 re-derive mismatches** | 0 specs without `wvec_hex`, 0 wrong lengths |
| **B-4** no GEN-DRIFT | **3,150 images regenerated: 0 GEN_DRIFT, 0 REGEN_ERROR** | **0 over all 296**, evaluated before board time was spent |
| **B-5** the bus-cycle bound | **0 at or beyond 4,096**; max **1,010**, p95 673 | **0** |
| **B-6** BRKEM-free | **0 `0F FF` pairs over 3,150 images** | **0 over 296** |
| **B-7** board discipline | `div_guard` PINNED **33 / 33**, 0 UNPINNED | PINNED **33 / 33** |
| **B-8** transport | 0 quarantines, 0 run-errors, breaker never armed | **0 quarantines, 0 transport errors in 912 seed-loops** |
| **B-9** the capture is STABLE | **158 / 158** on the declared 5 % stratified sub-sample, **0 QS-flicker rows** | **296 / 296**, rep 1 against every later rep on BOTH A/B legs, **0 bad rows, 0 flicker rows** ⓥ |

**B-5 was read rather than merely passed**: the board *cannot* reach 4,096 —
`v30ctl.CAP_RECORDS` is 4,096 **clock** records and a bus cycle is ≥ 4 clocks —
and that was written into the execution note **before** the run so the max of
1,010 could not be read as a discovery.  ⚠ **It does not generalise to the
offline engines**, which have no such buffer.

**B-1's sample is unbiased with respect to what it measures** and costs no board
time: the rig applies the vector before any engine has an answer, so *"was the
vector applied"* cannot depend on whether the seed diverged.

### (b.4) The instrument catches — every one, and the two that carry the pattern

| # | sitting | what it was | disposition |
|---|---|---|---|
| **F-1** | W0 | a **pre-existing** `cfg_hash` provenance drift: only 156 of 400 sampled banked seeds re-derive their stored hash | **ATTRIBUTED BY MEASUREMENT, not argument** — the pre-task-#38 key set reproduces the identical 156, so task #38 did not cause it.  **Nothing gates on `cfg_hash`**; images regenerate 300/300 and 216/216.  **BOOKED, NOT FIXED** |
| **F-2** | W0 | the BRKEM knob alone leaves 7.6 % of soup seeds carrying `0F FF` | why the mechanism is three places.  §(b.2) |
| **F-3** | W0 | the TB reads `$readmemh` (HEX) and the model `fscanf("%d")` (DECIMAL); a TB file handed to the model **silently runs a truncated vector** | **NEVER FIRED IN THIS TREE** because the only two consumers each wrote their own file inline.  Now two named writers plus `check_encodings()` on every lint |
| **F-4** | W0 | ⚠ **THE VACUOUS-INSTRUMENT PATTERN, IN THE SITTING'S OWN SMOKE TOOL.**  `wrfuzz_smoke` reached the RTL through `check_seq.run_tb`, whose `CORE` is pinned to **`"fsm"`** — so it asserted and printed the **`ucore`'s** receipt and ran the **ARCHIVED FSM CORE** | **CAUGHT BY THE RECEIPT LAYER** (an unexpected `tb_v30_core/fsm` line in `verilator_binary.jsonl`).  Measured cost: FSM 3,538 applied cycles against the corrected `ucore`'s 4,809 — **a 36 % different denominator, and BOTH read 100.00 %, so the bar would have passed either way and the mislabel would have reached W1.**  Fixed by invoking `tf.tb_bin(core)` directly **plus a postcondition asserting the binary path matches the named core**.  ⚠ **The trap is LIVE elsewhere and is booked, not patched**: `fuzz_campaign run <cid> --tb-only` also runs the FSM core, and `check_seq.CORE` is deliberately unchanged.  **No wrfuzz number may be taken from a `--tb-only` run and called an `ucore` number** — and none was |
| **F-5** | W1 | ⚠ **THE SINGLE-WRITER PROBE MATCHED ITSELF.**  `pgrep -af 'v30ctl.py serve'` through `bash -lc` matched the `bash -lc` carrying the pattern; the first pre-flight declared a violation that did not exist | Fixed to `[v]30ctl`.  Recorded at length for the reason that matters: **the probe reported a violation that was not there, which means the same construction could have reported an all-clear that was not there either.**  The task #29 P7 lesson arriving in a liveness check |
| **F-6** | W1 | the vector axis costs ~30 % of capture throughput, and it is the **transport** (a 4,096-byte `WVEC` load sent twice per seed), not the part | **BOOKED, NOT FIXED** — the obvious optimisation would make the board's NOT-CLEARED replay RAM load-bearing, *which is the hazard that rule exists to keep out of the capture path* |
| **F-7** | W1 | B-9 found **zero instability AND zero QS flicker**, which is stronger than the bar asked for (the comparator TOLERATES the flicker as cosmetic) | a positive.  §81.B's 193/193-deterministic now has a random-wait-vector counterpart, **measured rather than inherited** |
| **F-8** | W2 | ⚠ **THE PRE-REGISTERED OPEN_BUS EXCLUSION IS NOT THE ONE THE BANK LABELS WITH, AND THE DIFFERENCE IS 1.7 POINTS OF `S`.**  A SUCCESS seed can never carry `KNOWN_ACCEPTED/open_bus`, so excluding on that label removes open-bus MISSES and keeps open-bus EXACTS — **an exclusion whose membership depends on the answer** | the registered detector was evaluated on all 3,150 through the capture path's own banked counter, validated **259 / 260** against the row-level function and **0 / 120** false fires on soup.  **`S` = 91.6681 % under the registered detector against 94.9107 % under the label.  THE COSTLIER ONE IS THE ONE USED**, and both alternatives are banked in `w2_strata.json` ⓥ |
| **F-9** | W2 | W1's retention policy (rows for 380 of 3,150) **cannot support a row predicate over the population** — enough for the family census (every non-exact seed's rows on disk, 320/320) and not for any predicate needing a SUCCESS seed | **BOOKED, NOT FIXED at W2 — and PAID at W4**, where §5.1 retains every capture's rows |
| **F-10** | W2 | ⚠ **THE CONTROL STRATA CANNOT BE CHECKED AGAINST A REMEMBERED NUMBER, AND BOTH CANDIDATES FAIL BY MEASUREMENT** | (a) the promoted bank's per-wait-class column is a **SELECTION artefact** — 100.0 % on six of nine soup classes beside `fix0` at 65.8 %, *which is what `fuzz_bank.promote`'s caps left behind*; (b) the mc1/mc2/t30 populations carry **no era stamp on any line** (21,203 lines), so their fabric leg is a core and a bitstream nothing records.  **`wr1`'s nine control strata are the FIRST unbiased, era-stamped, per-wait-class population measurement of the resident era, and the reproduction check the work order asked for returns a NEGATIVE.  No delta against either candidate is computed anywhere** |
| **F-11** | W2 | **a BRKEM-free corpus landed in 8080 mode 12 times** | COUNTED, REPORTED, **LEFT IN THE DENOMINATOR**.  §(c.3) |
| **F-12** | W2 | ⚠ **THE VACUOUS-INSTRUMENT PATTERN AGAIN, IN THE SITTING'S OWN `8F` MOD-3 COUNTER.**  The first criterion scanned the composed image for the byte pair and reported **2,951 of 3,150** — a 64 KB image with random fill contains it by chance almost always | **LABELLED VACUOUS IN THE TOOL'S OWN OUTPUT**; the quoted count is the execution-based one, which is **0** |

⚠ **Neither F-4 nor F-12 is numbered in `standing_gates.md`'s vacuous-gate
incarnation count, and in both cases the reason is stated rather than left
implicit** (the §87.C.1 lesson): the count enumerates **GATES**, and both were
non-gates corrected in the sitting that wrote them, before any number left the
ledger.

### (b.5) The era and receipt discipline, and whether it held

**It held, and `wr1` is the first campaign in the project with a per-capture era
stamp at all.**  B-2 was made measurable by an instrument change committed
before board contact (`wrfuzz_w1_execution_note` §1.2): `era_of()` assembles the
`.sof` sha256, the **quartus receipt whose OUTPUT is that `.sof`**, the 88-file
RTL input manifest, `gen_git` and `RIG_EVT_HOLD_BITS`, and `cmd_run` stamps it
onto every line — *the RTL layer is NAMED, not asserted*, and
`rtl.inputs_sha256 = None` is itself a B-2 failure the pre-flight refuses on.
W1 measured **one distinct era over 3,150 lines** (FLASH #10 `1a01a6975e4a…`,
manifest `42752f3a57483002…`) and W4 **one distinct `sof_sha256` over 296**
(FLASH #11, receipt `7aef327c763f0d65…`).

Two further places the discipline did work rather than decorate: W3.5's G6
receipt was **NOT reused as FLASH #11's promotion receipt** because it records
the tree as `734e11c010-dirty`, and *a promotion receipt for a flash must name a
committed tree*; and FLASH #11's control-build input manifest is
**byte-identical to W3.5's** (`fc508a1c4c17228e…`), *which is the check that
says `hdl/` had not moved since the take-clock term landed*.

---

## (c) WHAT WAS LANDED, AND WHAT WAS DECIDED WITHOUT LANDING

### (c.1) The three laws landed

Evidence class is stated for each.  **Falsifier locations are given because a
law without one is not a law in this project.**

| # | the law, in one sentence | engines | evidence class | falsifier |
|---|---|---|---|---|
| **THE RECOGNITION SHADOW** (W3.1, §4) | **An instruction of the shadow class does not permit a single-step trap to be TAKEN at its own retire boundary; the arm is untouched — the boundary still SAMPLES — and the take moves to the next boundary.  The class is TWO MICROCODE ENTRIES, not a list of opcodes** (`00?.100011?0.00` = `8C`/`8E`; `00?.000??111.00` = `07`/`0F`/`17`/`1F`) | **BOTH** (`sim/exec_impl.h` one term; `v30u_eu.sv` a WIRE) | **bank, chip-side and ENGINE-FREE** — 380 retained `wr1` captures, 3,411 chip vector-1 entries, 1,363 ruled pairs: **75 of 75 grace-≥1 pairs inside the class, 1,288 of 1,288 grace-0 pairs outside it, not one exception in either direction** | §4.3; the class boundary is measured, not assumed (`PUSH` sreg is the ADJACENT entry and does NOT shadow; `LES`/`LDS` do not) |
| **THE RETIRE LEAD** (W3.4, §7) | **`wait_retire_lead()` leads the SUCCESSOR'S POP, and a BRK/TF boundary that fires cancels that pop — so it returns at once when the arm is set.**  The predicate *"a recognised boundary does not slide when the queue is dry"* was **ALREADY LANDED on the ROM path** (`boundary_no_pop()`, `INT.90` 200/200 with the retire deadline against 177 with the pop deadline); the ONE-BYTE-LOGIC path never had it | **`sim/` ONLY** | **bank, chip-side, zero exceptions** — the class is structurally identified with no engine in the loop: trapping instruction ONE-BYTE-LOGIC **23/23**, fetch address ODD **23/23**, queue DRY at the retire **23/23**, chip take = its own opcode pop **+2 on 23/23, WAIT-INDEPENDENT** at cycle lengths 5, 6 and 7 | §7.5, written at the gate: *any capture in which a `ONE_BYTE_LOGIC` form retiring into a BRK/TF take has its boundary later than its own opcode pop + 2 with a dry queue; or any `FA`/`FB` golden that moves when this gate is armed* |
| **THE TAKE CLOCK** (W3.5, §8) | **`q_ripe_lead_n` becomes `q_ripe_lead_n \|\| brk_seen` at `S_DECODE2`'s ONE_BYTE_LOGIC arm.**  §7.8's booked *"second, structural change"* is **RETIRED BY MEASUREMENT**: `bnd_opc` was always in the right place — decode + 2 **IS** the chip's take on 23/23 — and the whole defect was **one clock of arm latency at one decode** | **`ucore` ONLY** (the model's is the semantic reference) | **bank** + the `ucore`'s own trace: at the contested decode `brk_arm` = **0 on 23/23** (so W3.4's mirror gate could not fire), `brk_seen` = 1 on 23/23, `brk_smp_n` = 1 on 23/23, decode + 2 == the chip's take **23/23** | §8.7, and the registered **ANTI-BAR**: candidate U-A's `BRKT` = 2731 on `wr1/201055`, named in advance and **not reproduced** (U-B gives 2729, the model's own landed clock) |

**WHAT THE ENGINES GAINED IN STATE — ITEMISED, NOT SUMMARISED.**  *No
architectural or save-state-visible state was added.  W3.1 added the transient
decode field `LoadResult::ext` and renders the entry class with native opcode
literals where no PLA class bit exists; W3.4 added the transient BIU member
`brk_pending_`; W3.5 is one RTL term with no state.  `SS_VERSION` and the
`ucore`'s 205 architectural flops remained unchanged.*  (`ss_lint` exits 0 at
**`SS_VERSION` 0x87, 205 flops, 0 UNMAPPED** throughout — W3.1 §4.4, W3.5 Y-9.)
`LoadResult::ext` was **found by the landing's own A-1 bar**, because on the
`0F` page `out.opcode` is the SECOND byte and an unguarded literal would have
shadowed a different microcode entry entirely.

**AND THE NARROWER CLAIM, WHICH IS THE ONE THE STANDING PRINCIPLE ASKS FOR**:
*no per-delay fitted table or opcode-specific behavioural exception; the shadow
class is one measured microcode-entry class, rendered by three native opcode
literals in RTL/model.*  Those three are `07` / `17` / `1F`, the POP-sreg
entry's members that no PLA class bit names (`8C` / `8E` come from
`pla3::sreg_mov`, and `0F` is the extension page, taken by `ext`); the same
three appear in `v30u_eu_step.svh` and in `exec_impl.h`, and the class boundary
they render is the one §4.3 MEASURED — **not a list chosen to fit.**

**AND TWO LANDINGS WERE BUILT AND NOT TAKEN, each with its numbers.**  W3.2
attempted the suspend in **three forms** — `52 / 184` (28 lost), `55 / 184`
(18 lost), and an INERT `73 / 184` — and **took none**; W3.4's **FORM 3**
(delete the `q_.empty()` disjunct) scored the same 84 on `wr1` as the taken form
and moved **181 `v0.1` row-diffs** (`FA` 74, `FB` 68, `INT.FB` 39) where the
ladder is 0, *because the odd-`ip` half of `loader_impl.h`'s 250/250 golden says
the FLAG WRITE does wait for its byte to arrive.*  **Two laws rode one call**;
the registered ladder caught the wrong one being deleted and the number is
written down rather than smoothed.  W3.4's `ucore` mirror was **built, measured
at +1, and DELIBERATELY REVERTED** — *a +1 partial landing that misdescribes the
defect is not worth a synthesis gate.*

### (c.2) Questions decided or materially narrowed without landing

⚠ **The heading is "or materially narrowed" deliberately.**  Two of the six rows
below are NARROWED, not decided, and each says so in its own cell: the
`SCHEDULE` **`+2` mode's discriminator is NOT FOUND** (its invariant is measured
and its obvious reading is refuted by 18,990 counts), and **`mc1/721` has its
write order decided on silicon but no viable STRUCTURE** that honours the three
independently-measured placements.  Those two remain open at the campaign's
close.

| question | **what was decided** | evidence class | falsifier / where the block is written |
|---|---|---|---|
| **`mc1/721` — which of the two writes wins** | **DECIDED ON SILICON, AND IT IS THE MODEL'S ORDER** (candidate C1-A): a post-`E` microcode row's register write commits BEFORE the successor's one-byte-logic write; **both writes land**, and §49.8's *"which of the two fails to land"* is answered **NEITHER**.  `9E` SAHF's post-`E` writes the whole flag word, IE included | **DIRECTED BOARD CELL** — 17 sled variants × 2 waits × 3 reps = **102 socket captures**, two register bits through two pin paths; **every measurement cell selects C1-A**, W-1…W-7 all MET, chip == model on **102 / 102**, chip == `ucore` on **87 / 102** and the 15 are **EXACTLY the measurement cells, not one control among them** | §6.4.  ⚠ **C1-C IS REFUTED, NOT ARGUED AWAY**: the `b_no9E` null produces **`f047`** on silicon — the exact value the "post-`E` was LOST" branch predicts — *on the same rig, in the same capture set, with the same reader.*  **The third outcome was reachable and was not reached** |
| **…and whether it can be fixed** | **THE BLOCK STANDS AND NOTHING IS LANDED**, by the pre-registered decision rule's branch 2.  Three placements are **individually correct against silicon** — the ORDER (§6.4), the 1BL commit clock (W-5, isolated, chip identical to BOTH engines on 13 cells × 2 waits × 3 reps) and the post-`E` row's own clock (`schedule_identical` on all five seeds through eleven adjacencies) — **and they cannot all be honoured in the `ucore`'s current structure.**  §86.G's specified fix is refuted **by the `ucore`'s own cycle-exactness before it is refuted by §87.B's ROM-law argument** | directed cell + banked | §6.5.  *An 80s die does not read its microcode ROM twice in a clock* — `ucdecode` 8192×10 **and** `ucrom` 1028×29 across a bank boundary.  **`mc1/721` stays L3: spec'd, awaiting a STRUCTURE** |
| **does the BRK/TF take SUSPEND the prefetcher** (§4.7's booked candidate) | **REFUTED ON SILICON.**  On 563 directed vector-1 entries over 20 (sled, wait) cells the chip runs a `CODE` prefetch INSIDE the take-to-vector window on **121 of 563**, and `vec − take` is **9 on 500, 10 on 63** — the engines' own constant.  The entry's launch cost is a CONSTANT 9 clocks from the take | **retained silicon on a population where BOTH ENGINES ARE EXACT** (121,890 / 121,860 rows, 0 row-diffs), which is how §5.4a's *"the measurement is circular on banked data"* was broken **by the population rather than by a board** | §6.6.  ⚠ **REPORTED AS A MEASUREMENT, NOT AS A MET PREDICTION** — §6.6's own erratum: the offline leg was **RUN BEFORE its pre-registration was written**, checkably so (both `geom_*.json` are in the prereg's own commit).  *"No board contact" is not the same property as "no result yet"* |
| **the `SCHEDULE` `−3`/`−1` split** | **`−3` AND `−1` ARE ONE MODE, and `ucsim_t_provenance` §26.10 D item 4's registered discriminator is ANSWERED FROM THE CORPUS**: **the part leaves exactly 4 idle clocks between the two writes — 21 of 21**, at every wait level and for completing-cycle lengths 5 to 19, while **the engine's gap moves with the completing cycle** (1 when ≥ 6 clocks, 3 when 5).  **The chip's number is a FIXED INDEX; the engine's is bus-keyed** | bank, exact, with a control: over the 99 `wr1` seeds the `ucore` reproduces cycle-exact, the chip's `MEMW`→`MEMW` gap is 1/3/2/0/5/6/10 and **4 does not occur once in 2,819 opportunities** | **NOT LANDED, DELIBERATELY** — §5.6a: *a `MEMW`→`MEMW` gap written as the constant 4 is the fitted table the standing principle names*, and §26.10's mechanism is open.  What the sitting adds is the measurement that mechanism has to reproduce |
| **the `SCHEDULE` `+2` mode** | **26 seeds with an exact invariant** (previous cycle `CODE` 26/26, previous cycle aligned 26/26, **engine idle gap = chip's + 2 on 26/26**) — **and W3.2's half A P2 is a STRICT SUBSET of it, not a trap family**: the union is 26, not 46 | bank | **NOT LANDED, and NOT FORCED INTO A LAW.**  ⚠ **The control refuses the obvious one**: over the same 99 cycle-exact seeds the chip's idle gap after a `CODE` fetch is 0 on 3,847 and 1 on 12,860 of 18,990, **and the engine reproduces every one** — so *"the engine cannot launch back-to-back after a fetch"* is false by 18,990 counts.  **The discriminator is not found and this sitting does not have it** |
| **by what path a BRKEM-free image enters 8080 mode** | **ANSWERED, AND IT IS A CORE BEHAVIOUR.**  On each of the 12 the row where `PS3` first goes high is inside an interrupt entry returning to a three-byte `0F xx imm8`, and **on 10 of the 12 the THIRD byte IS the vector the entry read** — `BRKEM`'s `imm8` semantics.  The ten second bytes are `90 90 90 4A 77 F5 73 CA 7E 53`: **not one is `FF` and none is a documented `0F` form.**  *The `0F` extension page's PLA does not fully decode its second byte; the undecoded rows fall through to `BRKEM`* | chip-side and **engine-free** | §4.8a.  **THE SURVEY'S ROUTING IS CORRECTED**: it is a **CORE** question, not a generator one.  It joins the 8080/BRKEM family — **DEFERRED BY USER DECISION: counted and reported, not worked** |
| **`wvec-edge`'s 5/5 and the intermediate-wait hypothesis** | **THE REGISTERED FALSIFIER'S PREMISE FAILS AND THE DIRECTED CELL IS NOT RUN.**  Survey §4.5 rested on a matched control; restricted to the TF seeds — the population the 5/5 is about — `wvec-edge` runs **144-204** bus cycles and `wrand15` **291-326**, **no overlap**, so `p = 0.0022` is confounded by exactly the length coupling the survey named and believed it had controlled | bank | §4.8b.  **The mechanism W3.1 established has NO WAIT TERM AT ALL** (it is a microcode-entry class), which is what survey §4.4 measures from the other side — at `fix0`, no waits, the TF seeds already fail 6 of 7.  **The hypothesis is UNNECESSARY; recorded as a negative with its numbers** |

### (c.3) One number that is a finding and was not filtered

**12 of 136 scored misses are 8080 class-A landings, all raw tier, on a corpus
with 0 `0F FF` pairs in 3,150 composed images** (F-11).  As a share of the
residue the class has fallen from **41 %** (92 of 222, the banked corpus) to
**8.8 %** — the BRKEM-free mechanism working.  As an absolute it is 12 seeds
that should not exist, and **they are COUNTED, REPORTED and LEFT IN THE
DENOMINATOR: `S` is computed with them in.**

---

## (d) THE NUMBERS, PHASE-START → PHASE-END, AS REGISTERED

### (d.1) The ratchets that moved, and what each figure's scope is

| ratchet | **phase start** (SM3 close, `f3f7b6b20d`) | **phase end** | scope |
|---|---|---|---|
| `timed_fuzz --core ucore` **REGISTERED** | 1,557 / 1,702 | **1,564 / 1,702** | the banked corpus, Verilator TB, PREDICTING engine.  +2 at W3.1, +5 at W3.5 |
| … **EVT** | 931 / 1,008 | **937 / 1,008** | ⚠ **the EVT quoting rule applies**: under `--evt-replay` the model is handed the capture's acknowledge positions and REPLAYS while the `ucore` PREDICTS.  **Each figure is a ratchet for its own engine and NO delta, margin or ranking between them is computed anywhere in this document** |
| … **COMBINED** | 2,488 / 2,710 | **2,501 / 2,710** | as above |
| `timed_fuzz --core sim` **REGISTERED / EVT / COMBINED** | 1,338 / 798 / 2,136 | **1,343 / 802 / 2,145** | +1/+1/+2 at W3.1, +4/+3/+7 at W3.4.  **`sim/` was NOT touched after W3.4** |
| the b2 victory tranche, `ucore` / model | 177 / 159 | **182 / 161** | `ucore` +4 at W3.1 and +1 at W3.5; model +2 at W3.1 and unmoved since.  **V5 remains a standing REGISTERED FAILURE and was NOT re-scored, re-opened or re-negotiated by this campaign** |
| `BOUND WARNINGS` (`ucore`) / `ENGINE ABORTS` | 4 / 0 | **4 / 0** | unmoved |
| **`wr1` offline, model** | 48 / 184 (W2's first measurement) | **84 / 184** | ⚠ **ATTRIBUTION ONLY.**  The 184 is the retained-and-scored subset of 380 captures that is **DIVERGENT BY CONSTRUCTION**.  Never a silicon-match rate, never a ranking |
| **`wr1` offline, `ucore` TB** | 49 / 184 | **91 / 184** | as above.  The `ucore` move is 49 → 77 (W3.1) → 91 (W3.5); **13 of the 14 W3.5 gains are P1 seeds** |
| `ss_lint` — flops / `SS_VERSION` | 205 / 0x87 | **205 / 0x87**, 0 UNMAPPED | **no flop landed in the whole campaign** |
| G6 — Fmax / ALMs (CONTROL build) | 47.85 MHz / 11,147 (27 %) | **47.31 MHz / 11,232 (27 %)**, 0 latches, 0 `lpm_divide` | ⚠ **one Quartus draw**; §(g) |
| `flash_log.jsonl` | 13 entries (FLASH #10) | **14 entries (FLASH #11)** ⓥ | |

### (d.2) The campaign's own first registrations — **BASELINES, NOT RATCHETS**

`standing_gates.md` records these in terms: *"These figures have never been
measured before, nothing has been ratcheted to them, and a later measurement
that moves them is not a regression until a sitting says in writing that it
is."*

| column | value | how it must be quoted |
|---|---|---|
| `wr1` hardware-vs-silicon, **pooled** | **2,379 / 2,515 = 94.59 %** | the `ucore` **IN FABRIC on FLASH #10** against the socketed chip, 3,150-seed corpus, **635 excluded by the pre-registered OPEN_BUS detector**.  **Name the bitstream and the exclusion or do not quote it** |
| **`S`** | **91.6681 % — FROZEN** ⓥ | the unweighted mean of the 28 per-stratum rates.  **May not be re-derived after the tranche is scored** |
| **`B = S − 5.0`** | **86.6681 % — FROZEN** ⓥ | the bar |
| the `ucore`'s `wr1` residue | **136 seeds** — `PF_LOST` 43 · `SCHEDULE` 42 · `DATA_SEQ` 23 · `PF_GAINED` 18 · `PIN` 7 · `PF_ADDR` 2 · `NOW_EXACT` 1, **catch-all EMPTY** | the FABRIC census; the TB census is **identical cell for cell, delta for delta and signature for signature** |
| the `ucore`-**only** `wr1` residue | **5 seeds**, all family `PIN` | **COMPLETE** (every fabric miss has rows retained).  The model-only column is a **FLOOR of 6** and is not |
| INTA rows in `wr1` | **0 over 380 retained captures** | plan §4's registered **risk #4, answered by measurement and the answer is a NEGATIVE**: §56's fabric-float class has no members in an evt-free corpus.  **The scorer was chosen at W0 and was not swapped** |
| 8080 class-A in `wr1` | **12 of 136 scored misses**, all raw | counted, reported, left in the denominator |
| the axis's own verdict | **the plan §5 falsifier is NOT TRIGGERED** — six of fifty `wvec`-vs-`wrand` stratum pairs are distinguishable | ⚠ **and in every one of the six the vector stratum scores HIGHER.**  Pooled: soup `wvec` 96.80 % vs control 95.70 % (p = 0.24); raw `wvec` 92.03 % vs control 84.48 % (p = 0.031).  **After 3,150 seeds no vector shape has produced a divergence rate above the controls'.  The axis DISCRIMINATES — and so far it discriminates towards AGREEMENT** |

### (d.3) The negative control, stated as the survey states it

**The nine control strata were meant to double as a reproduction of the known
wait-class columns.  They do not reproduce them, and the reason is that no
comparable column exists** (F-10).  The promoted bank's per-wait-class figures
are a selection artefact; the mc1 / mc2 / t30 populations carry **no era stamp
on any line**, so their fabric leg is a core and a bitstream nothing records.
**The check the work order asked for returns a NEGATIVE, the negative is the
finding, and no delta against either candidate is computed anywhere.**  The
control that *does* work is the one the corpus design built in: **the nine
control strata against the five vector strata, same session, same bitstream,
same generator, same sitting.**

### (d.4) THE REGISTERED FAILURES AND ERRATA OF THIS CAMPAIGN — reported as registered, never restated

| # | where | registered | what happened |
|---|---|---|---|
| **A-1** | W3.1 §4.6 | each of the 39 predicted seeds' first divergence moves later or the seed becomes EXACT, **zero exceptions** | **NOT MET.  6 exceptions on the model, 3 on the `ucore`.**  What the misses are is a **POST-HOC** statement and is labelled one: on all six the engine's first divergence is UPSTREAM of the contested trap entry.  *"The predicted SET was selected on the first divergent trap ENTRY while the BAR was written on the engine's first divergence.  The selection was mine and the mismatch is mine"* |
| **B-1 / B-2** | W3.2 §5.5 | P1's 23 lose the insert, zero exceptions; ≥ 15 of P2's 20 lose the `+2` | **BOTH NOT MET.  0 of 23 on every form tried, and the landing was not taken.**  B-2's prediction was additionally **mis-aimed**: P2 is not a trap family |
| **B-4's `DIFF_BOUNDARY` clause** | W3.4 §7.7 | the shadow law's populations, `DIFF_BOUNDARY` included | **NOT MET — 7 → 17.**  *"It is not a loss and it is not restated as one"*: zero seeds left EXACT, zero first divergences moved earlier, and the law it was standing in for (75 / 1,288 / 1,363) is **unmoved**.  It is an ATTRIBUTION counter over a divergent-by-construction subset and **should not have been registered as a bar** — W3.5 declined to register it again |
| **the W3.1 pre-registration's own A-3 baselines** | W3.1 §4.6 | 1,282 / 789 / 2,071 and 1,502 / 920 / 2,422 | ⚠ **ERRATUM: quoted from `CLAUDE.md`'s quick reference, which was STALE.**  The results clear the CURRENT registered figures, *"which is the bar that counts; the pre-registered numbers were a floor set too low and they are named here rather than quietly met"* |
| **the W3.3 pre-registration, cell 2** | W3.3 §6.6 | T-A / T-B / T-C as candidates | ⚠⚠ **IT WAS RUN BEFORE THE PRE-REGISTRATION WAS WRITTEN**, checkably (both `geom_*.json` are in the prereg's own commit).  **"T-C was refuted" carries the weight of a MEASUREMENT, not of a falsifier that could have fired against a committed prediction.**  Cell 1 is NOT affected and the distinction is stated |
| **W3.2's B-5 / B-7 / B-8, W3.3's ladder and G6, W3.4's B-7 / B-8** | §5.5, §6.8, §7.6 | the must-not-move ladder, `ss_lint`, `ulockstep`, G6 | **VACUOUS — no engine or RTL file changed.  Reported as vacuous, not as green, and NOT CLAIMED** |
| **W3.5's Y-3 point prediction** | W3.5 §8.4 | `wr1 --core ucore` ≥ 77, point prediction **88** | **MET AND BEATEN — 91.**  *"Reported against the prediction, not in place of it"* |
| **W4's headline prediction** | W4 §3.1 | `T` = **93.0017 %**, 95 % band [87.82, 98.18] | **MEASURED 90.0170 % — inside the band, 2.985 points below the point prediction, 1.13 SE low.**  §(e.3) |
| **W4's §3.2 registered READING** | W4 §3.2 | the four W3 landings are a soup/TF phenomenon; raw reproduces W2 unchanged | ⚠ **CONTRADICTED.  Raw came in 5.2 points below its own W2 column and carried the whole shortfall.**  §(e.3), and it is **W4-1** in the successor queue |
| **two instrument mis-invocations** | W3.1 §4.6a | — | `check_boot.py` **does not take `--core`**; `check_core.py --suite-dir …-w1` **without `--waits 1`** reads 94 / 1,200.  *"A silent wrong-argument run of a ratchet gate reads exactly like a catastrophic regression, and neither reading was true."*  And W3.5: `--ss-sweep 1` was first run as if `1` were a MODE when it is a STRIDE — **killed, and nothing was scored off it** |
| **one erratum after the fact** | commit `ad78e2b8dd` | — | §8.6a's *"a bitstream was produced and NOT flashed"* was **true at its timestamp (02:14)** and superseded at 02:48 by W4's FLASH #11.  Recorded as a coordinator erratum rather than by rewriting the append-only entry |

**And two corrections the campaign made to its own earlier documents**, both
recorded as errata beside the originals and neither smoothed: **W3.1 §4.2**
corrected the survey's reading that `PF_LOST`'s 30 `MEMR 00004` seeds are *"the
SAME event with the owners swapped"* as `PF_GAINED`'s 18 (**they are not** — one
is a bus-launch question, the other a recognition-class question); and **W3.2
§5.6** corrected the survey's queue item #2, whose delta histogram is a
family-wide 42-seed statistic and not the raw tier's 25.

---

## (e) THE VICTORY

### (e.1) The bar, and that it was frozen before it could be chosen

**Registered at W0, before any survey number existed** (plan §5, prereg §5.3):
`B = S − 5.0` percentage points, `S` computed at W2 as the unweighted mean of
the 28 per-stratum rates and **FROZEN there**; neither `S` nor the allowance may
be re-derived after the tranche is scored.  The 5.0 points were registered
**for SAMPLING, not for slack**, against a 2.1-point SE estimate for a 196-seed
mean, and with the ucsim-t precedent named — *a fresh disjoint tranche is not
expected to be the harder population.*

`B = 86.6681 %` was a **literal constant in `sw/wrfuzz_w4.py`**, and `S` was
re-computed at W4 **only as a reproduction check on the W2 artifact**
(91.6681 % to four decimals) and never as a new value.

### (e.2) The tranche, the bitstream, and the result

**The tranche** (§9.3): `cid = wr2`, **196 body seeds** over the same 28 strata
at `k ≥ 300000`, **disjoint from every survey seed by construction, not by a
check**, plus **four directed H3-B cells × 25**; 3 repetitions and 5 on the 12
declared promotion cells = **912 seed-loops**.  Population sha256 **verified
before it was read** ⓥ.

**The bitstream**: **FLASH #11**, `nec_test_ucore.sof 82b4935092d6fb99…`, `.rbf
9363a7c72c9f9dca…`, through `sw/safe_flash.sh` with its VERIFY leg,
`flash_log` 13 → **14** ⓥ.  **G6 fresh at HEAD on a CLEAN tree is the promotion
receipt**, green *before the pre-registration was committed*: 0 errors, **Fmax
47.31 MHz** against a registered ≥ 32, +9.226 ns, **TNS 0.000 on every domain**.
The FLASHED build is the **RETENTION** build — *the resting configuration, and
the whole W1 corpus and therefore `S` itself was captured on one, so a control
build would silently have changed the comparator that produced the frozen bar.*
⚠ **The macro's effect is CHECKED, not asserted**: the retention `.sof` differs
from the control build's produced from the same tree minutes earlier.

> ### **`T` = 90.0170 % ⓥ against the FROZEN `B` = 86.6681 % ⓥ — MET, +3.3489 points.**

**Both `MET` conditions hold.**  Condition 1 is `T ≥ B`.  Condition 2 —
*every non-exact seed's first divergence falls in a family named in the W2
census's taxonomy* — is **satisfied on 12/12 scored non-exact seeds; the tranche
denominator was 141 scored, comprising 129 exact and 12 non-exact**:
`SCHEDULE` 7 · `PF_LOST` 2 · `DATA_SEQ` 2 · `PIN` 1, **catch-all
EMPTY** and `w4_score.json`'s `unnamed` the empty list ⓥ.  *The "100 %" is over
the twelve seeds condition 2 can apply to, not over the 141 — a seed that is
cycle-exact has no first divergence to classify.*

**The denominators, stated so the population total is never read as a test
count**: 196 body seeds were **drawn**; **141 were SCORED** (55 excluded
OPEN_BUS, all raw tier, 0 soup); **129 were cycle-exact**, pooled 91.49 %.
`T` is the mean of 28 per-stratum rates, `n_rates_averaged` = **28** — the
empty-stratum rule registered in prereg §2.1 was **armed and never needed**.
**The plan's other reading is reported beside it as registered**:
`floor(86.6681 % × 141)` = **122** seeds against a measured **129** ⓥ — *the two
readings do not disagree, so nothing had to decide between them.*

### (e.3) The prediction, and the shape of the miss

The registered point prediction was **`T` = 93.0017 %** with a 95 % band of
**[87.82 %, 98.18 %]**, derived from the current offline columns per stratum by
an instrument run and recorded **before the board was touched**, and with its
**three weaknesses named before the result**.

> **MEASURED 90.0170 % — INSIDE the registered band, 2.985 points BELOW the
> point prediction, 1.13 standard errors low.  Reported as registered, not
> restated.**

**The shortfall is not noise spread evenly; it has a shape, and the shape
contradicts the sitting's own registered reading** (§9.4):

* **soup beat expectation** — 95 / 98 pooled, mean **96.94 %** against a
  predicted 97.71 %, with **eleven of the fourteen soup strata at 100.00 %** and
  the other three one seed each;
* **raw carried the whole shortfall** — 34 / 43 pooled, mean **83.10 %** against
  a predicted 88.29 %, and **5.2 points below its own W2 column**, where §3.2
  predicted it would reproduce W2 *unchanged*;
* **the honest arithmetic**: after the OPEN_BUS exclusion the raw strata carry
  **1 to 6 scored seeds each**, so one seed is worth 16-100 points of a
  stratum's rate and the 28-stratum mean inherits that.  `raw/fix3` at 50.00 %
  is **two seeds of four**.

**THE HONEST MARGIN, registered before the run and repeated here**: the band's
lower edge is **1.16 points above the bar**, the tranche's actual SE is **2.64
points** (larger than W0's 2.1 estimate, because the OPEN_BUS exclusion takes
two-thirds of the raw tier), and *"this is not a comfortable bar, it is a bar
that a bad draw on the raw side can reach."*  **The measured +3.3489-point
margin is about 1.27 of that standard error.**

### (e.4) The four directed H3-B cells — the registered NEGATIVE fires

`skew` at `blk = 32`, the deepest block interior — §65.2's *"steady state, never
flushed"*, the one of its three stimuli never tried.  The class-B observable is
§68.6's own (**same clock, different owner**), with `sm3_h3_cell.measure`
IMPORTED so the statistic is §68.6's, paired chip-against-**fabric**.

> **ZERO class-B pairs over 7,295 paired accesses on the cycle-exact
> population** — and 7,295 is §68.6's own **7,254** to within half a percent,
> which was not arranged and is reported because it makes the two numbers
> directly readable.  **D1 is 25 / 25 cycle-exact.**

⚠ **AND THE PAIRING'S OWN LIMIT, DECLARED IN ADVANCE, FIRED EXACTLY WHERE IT WAS
PREDICTED TO.**  Prereg §3.4a registered **both** populations before any capture
— (a) the cycle-exact seeds, the strict statistic comparable to §68.6's; (b)
every seed, *"pairing is ambiguous past a divergence"* — and (b) reports **one**
class-B pair, in D3, on `wr2/330039` at access #89, **a seed that is not
cycle-exact** ⓥ.  *Had the split been made after the numbers were seen it would
have been indistinguishable from choosing a statistic to get a zero.*

### (e.5) The fabric re-base — every registered prediction met cell for cell

The offline references were **RE-TAKEN ON THIS TREE BEFORE THE BOARD WAS
TOUCHED** (§83.0/§83.0b's lesson applied, not re-learned), and the registered
prediction was that **the four W3 landings** (three laws, four engine legs)
**touch neither population at all**:

| leg | offline reference (re-taken) | **IN FABRIC on FLASH #11** |
|---|---|---|
| the four HLT sweeps | `offline` **279 / 283**, `ret` **279 / 283**, 0 cells differing | **279 / 283**, **0 PASS/FAIL disagreements and 0 differing first-divergence coordinates over all 283**; the four failures the four family-D cells **NAMED IN ADVANCE at the coordinates named in advance** |
| the S16 directed display walk | `offline` **1,347 / 1,371** | **1,347 / 1,371**, **0 disagreements and 0 differing coordinates over all 1,371**; its 24 failures the four family-D coordinates × the six frozen programs, **catch-all EMPTY** |
| socket controls | — | **49 / 49** and **41 / 41** |
| first light / close | — | `check_ab_hw all 800` **MATCH ×3** after the flash; **`use_core=0` chip proof MATCH over 800 rows after everything**, which is the measurement that the retention build leaves the socket position untouched |

---

## (f) THE RESIDUE AND THE SUCCESSOR QUEUE

### (f.1) What the campaign booked and did not fix

| # | item | state |
|---|---|---|
| **W4-1** | **THE RAW TIER IS THE CAMPAIGN'S REMAINING AXIS, AND IT IS NOT THE TF AXIS.**  Raw 34/43 (83.10 %) against soup 95/98 (96.94 %), and 5.2 points below raw's own W2 column | the sitting's own registered reading is **CONTRADICTED**.  Not diagnosed |
| **W4-2** | **THE OPEN_BUS EXCLUSION COSTS THE RAW TIER ITS RESOLUTION** — 55 of 98 raw body seeds excluded, strata left with 1-6 scored seeds | a future tranche wanting raw resolution must **oversample raw**, not draw it 7-per-stratum |
| **W4-3** | `SCHEDULE` is **7 of 12** of the tranche residue — the largest family, and larger in share than at W2 (42 of 136) | not diagnosed |
| **W4-4** | `PF_GAINED` is **0 of 141**, consistent with W3.1-W3.5 having closed §3.5's invariant | ⚠ **NOT ESTABLISHED at this population size** — W2's rate would predict about one.  **Recorded as consistent, not as closure** |
| **W4-5** | the directed cells' vectors are **not all distinct** (D1 draws 22 for 25 seeds, D2 19, D3 23, D4 20) because the cells **SELECT** rather than FORCE | a `force_wvec_spec` knob — W2's own booked gap — would remove the coincidence |
| **W4-6** | **class B has now missed under ALL FOUR named stimuli** | *"Either it does not exist as an observable of this design, or nobody has yet named the stimulus.  A campaign should say which it believes before designing a fifth cell"* |
| **F-9** | W1's retention policy | booked at W2, **PAID at W4** for the tranche (every row retained); **not fixed for a 3,150-seed corpus** |
| — | the `wvec-skew` shape | ⚠ **has not yet earned its place**: the shape built FOR H3-B contributes **exactly one** of W2's eleven H3-B-signature seeds and its soup stratum is the second best in the corpus.  W2 said W3 should say so; **W4's D-cells are the answer and it is a negative** |

### (f.2) The open mechanism surface

* **The 10 P1 seeds still not EXACT on the `ucore`** (§8.5, itemised rather than
  counted as a miss): 13 of the 23 closed; **9 of the remaining 10 have their
  first divergence LATER**, which is the P1 defect closing with a downstream one
  remaining.  **`wr1/204143` is the one that did not move**, and its divergence
  at row 1113 is far UPSTREAM of its contested take at clock 2341 — its take
  clock DID close.  ⚠ On the **model** leg the corresponding count is **12**
  (§7.9), of which 4 have an upstream divergence predating the contested entry.
  ⚠ **One gain was not predicted**: `wr1/206062` is not one of the 23 and became
  EXACT — *reported, not claimed.*
* **`SCHEDULE`'s two modes** (§5.6c): **`MEMW`→ 4 idle →`MEMW`, 21 seeds** —
  invariant MEASURED, discriminator ANSWERED (fixed index), **mechanism OPEN**
  (`ucsim_t_provenance` §26.10 D item 4), not landed because the constant would
  be a fitted table; and **`CODE`→ gap + 2, 26 seeds** — invariant MEASURED,
  **discriminator NOT FOUND**, not landed and **not forced into a law**.
* **`mc1/721` — the structural block.**  Decided on silicon (order = C1-A),
  C1-C refuted, the family re-classified from *"three of the five carry the
  signature"* to **five of five**, and **both** colliding placements
  independently re-measured against silicon.  **What is still not known is a
  structure that honours three measured placements without a second micro-ROM
  read, and this campaign does not invent one.**  Its 102 retained captures are
  banked with `SHA256SUMS` and re-score offline with no board — *"it is what
  that sitting's landing must be scored against"*.  ⚠ **The cell is deliberately
  NOT registered as a standing gate**: its `ucore` column is the open block
  (87 of 102), *and a gate whose registered value is a known-unclosed defect is
  a ratchet pointed at the wrong thing.*
* **`mc2/584`** — booked, undiagnosed, **not opened by this campaign**.  The
  survey counted no seed carrying its signature.
* **H3-B — WHAT THIS CAMPAIGN SAYS ABOUT IT NOW, PLAINLY.**  It re-entered scope
  by the campaign directive; the corpus carried a shape (`skew`) designed for
  it; W2 counted **11 seeds** under the census's own criterion (**35** under
  SM3's L2 definition) and observed that `wvec-skew` contributes **exactly one**
  of the eleven; and W4 ran the four directed cells that §68.6 named and could
  not reach.  **The result is a REGISTERED NEGATIVE at §68.6's own scale: 0
  class-B pairs over 7,295 paired accesses in the block interior.**  Class B is
  now **not** at a queue-occupancy threshold (§63.6), **not** in a byte-step
  sweep (§65.2), **not** in a clock-step sweep of the eligibility instant
  (§68.6), **and not** in steady state inside a 32-access wait block.
  ⚠ **H3-B IS NOT REFUTED.**  Four named stimuli have missed; the seeds SM3
  assigned to L2 still carry a measured shape; and no cell has yet been designed
  that a class-B event would have to fire in.  **The campaign's own statement is
  W4-6's**: *either the observable does not exist in this design, or nobody has
  named the stimulus, and a campaign should say which it believes before
  designing a fifth cell.*
* **The carried deferrals, untouched and still carried**: **8080 / BRKEM**
  (DEFERRED by user decision — and this campaign **added** to it, by
  establishing the `0F`-page entry path as a CORE question); **the model-only
  residue** (FROZEN by user decision — `sim/` moved only at W3.1 and W3.4, both
  shared mechanisms, both `sim/`-first); **V5** (SEALED — not re-opened and not
  re-scored).
* **Not exercised at all, and said so**: the **EVT × vector** cell the plan
  named and reserved for W3+ was never run, so **no wrfuzz number bears on the
  pin axis**; **H7** needs a pin event and this corpus is evt-free; the 27 S16
  `ARCH` cells and family D are not fuzz populations.

### (f.3) THE ONE GATE THIS CAMPAIGN LEAVES BEHIND — and what it is NOT

The campaign closed with three landings in the tree and **nothing in the tree
guarding them at seed level**.  The Codex closing review named that gap, and
finalization registered the guard for it — **before this document was
finalized, not after** (`standing_gates.md`, wrfuzz section; runner
`sw/wrfuzz_wr1_guard.py`; baseline
`sw/testdata/wrfuzz/w6_wr1_guard_baseline.json`, sha256 `bf6ea3a60d41…`).

| clause | bar | **at registration** |
|---|---|---|
| 1 | model **≥ 84 / 184** | **84 / 184** |
| 2 | `ucore` **≥ 91 / 184** | **91 / 184** |
| 3 | **zero previously-exact `wr1` seeds lost** | **0** |
| 4 | **zero first divergences moved earlier** | **0** |
| (integrity) | the scored denominator is still 184 | **184** |

**Both legs ran once at registration and the guard is GREEN, rc = 0.**  The
`ucore` leg additionally reproduces W3.5 §8.7a's own dump seed for seed.

⚠ **AND THE DISTINCTION THAT IS THE REASON IT IS WORDED THIS WAY.  THIS GUARD IS
AN *IMPLEMENTATION* GUARD AND IT IS NOT THE VICTORY MEASUREMENT.**

* It is **not a silicon-match rate**.  The 184 is the retained-and-scored subset
  of the 380 captures and that subset is **DIVERGENT BY CONSTRUCTION**; 84 and
  91 are ATTRIBUTION figures, exactly as §(d.1) and §(d.2) label them every time
  they appear.
* It is **not a ranking of the two engines** — no delta between the legs is
  computed by the guard or anywhere in this document.
* It is **not a new sample and it does not re-claim `T`.**  **`T` = 90.0170 % is
  a FIRST REGISTRATION on a population that is now spent** — the tranche was
  frozen, drawn and scored ONCE, and a second run of the same seeds is not a
  second sample.  **Nothing is ratcheted to 90.0170 %, and a green run of this
  guard is not evidence about it.**  The guard runs OFFLINE and touches no
  board; the 90.0170 % is a FABRIC measurement against silicon.  They are
  different instruments on different populations answering different questions,
  and the guard exists so that the campaign's *code* cannot silently regress —
  **not so that its *victory* can be re-claimed.**

---

## (g) THE VERDICT

> **The user's directive is ANSWERED and the campaign's own pre-registered bar
> is MET on the axis it was written for.**  A per-access random-wait stimulus
> the part had never been asked to answer at scale was designed, pre-registered
> and captured — **3,150 seeds over 28 strata with the nine existing wait
> classes inside the same session as CONTROLS, B-1 … B-9 nine of nine, in 7.6
> minutes of board time** — and surveyed on one tree into one census under an
> exclusion chosen **against the survey's own convenience** (it costs 1.7 points
> of `S`), from which **`S` = 91.6681 % and `B` = S − 5.0 = 86.6681 % were
> computed once and FROZEN before any tranche existed.**  Five mechanism
> sittings followed: **three laws landed — the recognition shadow (both
> engines), the retire lead (`sim/`), the take clock (`ucore`)** — and the state
> accounting is itemised rather than summarised: *no architectural or
> save-state-visible state was added.  W3.1 added the transient decode field
> `LoadResult::ext` and renders the entry class with native opcode literals
> where no PLA class bit exists; W3.4 added the transient BIU member
> `brk_pending_`; W3.5 is one RTL term with no state.  `SS_VERSION` and the
> `ucore`'s 205 architectural flops remained unchanged.*  The narrower claim is
> the one that carries the standing principle: *no per-delay fitted table or
> opcode-specific behavioural exception; the shadow class is one measured
> microcode-entry class, rendered by three native opcode literals in RTL/model.*
> **Six questions were decided or narrowed; the `+2` discriminator and a viable
> `mc1/721` structure remain open** —
> including `mc1/721`'s write order **settled on silicon by a directed cell
> whose refuting third outcome was reachable and was not reached**, and a
> `MEMW`→`MEMW` gap whose registered discriminator is ANSWERED as a fixed index
> **and deliberately not written down as a constant**.  On a **fresh 196-seed
> tranche drawn from a k-block disjoint from the survey by construction, scored
> IN FABRIC against the socketed chip on FLASH #11 with the A/B pair differing
> in `use_core` and nothing else**, **`T` = 90.0170 % against the frozen
> `B` = 86.6681 % — MET by +3.3489 points**.  **This is a valid MET under the
> pre-registered post-mechanism protocol, but not an apples-to-apples
> FLASH-#10/FLASH-#11 delta: the +3.3489 points combine a fresh population draw
> with two intervening `ucore` landings, and the record does not decompose those
> effects.**  **Condition 2 is satisfied on 12/12 scored non-exact seeds; the
> tranche denominator was 141 scored** (not the 196 drawn), **comprising 129
> exact and 12 non-exact** — the catch-all EMPTY,
> nine capture-integrity bars met and nothing VOID, and the four directed H3-B
> cells returning **their registered NEGATIVE — 0 class-B pairs over 7,295
> paired accesses — under the one stimulus §68.6 could not reach.**  **The
> registered failures stand exactly as registered and are not re-negotiated**:
> W3.1's **A-1 NOT MET** (6 model / 3 `ucore` exceptions), W3.2's **B-1 and B-2
> NOT MET** with three landing forms attempted and none taken, W3.4's **B-4
> `DIFF_BOUNDARY` clause NOT MET**, W3.3's **pre-registration erratum — cell 2
> was run before it was registered, so its verdict is a measurement and not a
> met prediction** — and the sitting's own point prediction of `T` = 93.0017 %
> **missed low by 2.985 points with a shape that CONTRADICTS its registered
> reading**: raw, not soup, carried the whole shortfall and came in 5.2 points
> below its own W2 column.  **`mc1/721` is decided and still blocked, ten of the
> twenty-three P1 seeds are still not exact on the `ucore`, H3-B is not refuted,
> and the winning margin is one draw of a statistic whose registered standard
> error is 2.64 points.**

**What this verdict does NOT claim.**

* **Not "the tranche is a 196-seed test."**  **141 seeds were scored**; 55 were
  excluded by the pre-registered OPEN_BUS detector, all raw tier.  The raw
  strata carry **1 to 6 scored seeds each**, so one seed is worth 16-100 points
  of a stratum's rate and `T` — a 28-stratum unweighted mean — inherits that.
  **The tranche's registered SE is 2.64 points and the +3.3489-point margin is
  about 1.27 of it.  A single draw met a bar; it did not measure a population to
  that precision.**
* **Not "+3.3489 points is what the campaign's mechanism work bought."**  **This
  is a valid MET under the pre-registered post-mechanism protocol, but not an
  apples-to-apples FLASH-#10/FLASH-#11 delta: the +3.3489 points combine a fresh
  population draw with two intervening `ucore` landings, and the record does not
  decompose those effects.**  Appendix B says the same thing from the artifact
  side; it is repeated here because the margin is the number a reader carries
  away.
* **Not "the campaign's landings are confirmed in fabric."**  FLASH #11 carries
  the `ucore`'s shadow and take-clock terms and **the tranche is the only fabric
  population that could exercise them** — and the tranche was never captured on
  FLASH #10, so **there is no fabric before/after at the seed level anywhere in
  this campaign.**  The two populations that WERE re-based (the HLT sweeps, the
  S16 walk) were predicted **not to move and did not**; that is a control on the
  bitstream, not a confirmation of the laws.  The model's W3.4 landing is in no
  bitstream by construction.
* **Not "`PF_GAINED` is closed."**  It is **0 of 141** where W2's rate would
  predict about one.  **Consistent, not established** (W4-4).
* **Not "the residue is explained."**  W2's 136 and W4's 12 are **classified**,
  which is not the same thing: `SCHEDULE`'s two modes have a measured invariant
  and, in one of them, **no discriminator at all**; `DATA_SEQ`'s obvious guess
  (`gaps` §T8's ±1/±2 shape) is **refuted with no replacement offered**.
* **Not "dispositioned means closed."**  8080/BRKEM, the model-only residue and
  V5 are **explicit deferrals carried in**, counted and left in the denominator,
  not work that was done.
* **Not "the vector axis found a harder population."**  It did not.  Six of
  fifty stratum pairs are distinguishable **and in every one the vector stratum
  scores HIGHER**; the shape built for H3-B contributes one of eleven signature
  seeds and returns a negative in its own directed cells.  **The axis
  discriminates towards agreement, and the corpus design is not defended against
  its own result.**
* **Not "the INTA float class was handled."**  It was **measured absent** — 0
  INTA rows over 380 retained captures in an evt-free corpus — so plan §4's
  registered risk #4 is answered by a negative and **not by an instrument that
  was shown to cope with it**.  A corpus with pin events would have to ask
  again.
* **Not "G6 establishes robust timing closure."**  **47.31 MHz is one Quartus
  draw**, and the multi-seed worst-of-N gate SM3 booked is **still not built**.
  FLASH #11's flashed retention build is a **second** single draw whose figures
  are RECORDED, not barred, and whose input manifest differs from the gated
  control's for the §80.B.1 reason.
* **Not "no bar was missed."**  §(d.4) lists every miss, every erratum, every
  vacuous bar and the one pre-registration that was written after its own leg
  had run.
* **Not a ranking of the two engines.**  The `wr1` offline legs (84 / 184 and
  91 / 184) are **attribution figures on a divergent-by-construction subset**,
  the EVT columns carry the standing quoting rule, and **no delta, margin or
  ranking between the engines is computed anywhere in this document.**

---

## APPENDIX A — THE CORRECTION LEDGER

**Five figure discrepancies were found while cross-checking this document at
draft.  ALL FIVE ARE DISCHARGED IN THEIR HOME DOCUMENTS at W6** — the drafting
sitting reported them and deliberately did not touch them (*"reported as
findings, NOT silently corrected"*), and finalization corrected them **where
they live**, which is the only place a correction stops being a footnote.  **Not
one of them moved a number this verdict quotes**, then or now.

**The disposition rule, and it differs by document.**  `standing_gates.md` is a
quick-reference and is corrected IN PLACE, with the correction and its date
written into the cell.  `wrfuzz_provenance.md` is **APPEND-ONLY by its own head
matter** (*"a correction is an ERRATUM box beside the original, never a
replacement"*), so its three are **ERRATUM BOXES beside the originals and the
original text is left standing**.

| # | what was wrong | **home document, corrected location** | how |
|---|---|---|---|
| **A-1** | the era-stamp line count read **20,203**; it is **21,203** (mc1 10,003 + mc2 10,000 + t30-raw 1,000 + t30-brkem 200 — **four campaigns, not two**).  Erratum commit `f22f888feb` had reached the survey §6.2 and ledger §3.4 F-10 and **not** this file | **`docs/notes/standing_gates.md`**, § THE wrfuzz CAMPAIGN → *"AND THE NINE CONTROL STRATA DO NOT REPRODUCE ANY REMEMBERED COLUMN"* | **corrected in place to 21,203**, with the four-campaign breakdown and a note that it read 20,203 until W6 |
| **A-2** | ledger §2's header dates the **W1** sitting 2026-08-06; its own commits are 2026-08-05 (`4665a04e64` at 20:58, `b8020d0229` at 21:10), which dated W1 a day AFTER the W2 survey of W1's own captures | **`docs/notes/wrfuzz_provenance.md` §2**, header | **ERRATUM BOX** beside the header.  Original left standing; the box names both commits, the note's own dateline, and that **the ordering of the work is not in doubt — the header date is** |
| **A-3** | ledger §2.6 F-7 reads *"158 seeds × 3 repetitions × 2 legs = 632"*; 158 × 3 × 2 = 948.  **632 = 158 × 4**, and 4 comparisons per seed is exactly §2.4's B-9 row | **`docs/notes/wrfuzz_provenance.md` §2.6**, F-7 | **ERRATUM BOX** beside F-7.  **The count 632 is right and the expression is wrong**; the bar's 158 / 158 with 0 flicker is unaffected and no figure is computed from the expression |
| **A-4** | ledger §9.7's B-9 row says *"across **912 captures**"*; 912 is the **seed-loop** count and a seed-loop is two captures, so the captures are **1,824**.  B-8 immediately above uses the same 912 and names it correctly | **`docs/notes/wrfuzz_provenance.md` §9.7**, B-9 row | **ERRATUM BOX** beside the table.  Nothing is re-scored: the bar is over the 296 seeds either way and `w4_score.json` carries no capture total ⓥ |
| **A-5** | the `wr1` residue quick-reference row sums to **135** and is labelled **136**; the missing member is the single **`NOW_EXACT`** seed, which the survey §3.1 names in prose and W4 prereg §2.0a located in the banked census by measurement | **`docs/notes/standing_gates.md`**, the W2 `wr1` baseline table, *"the `ucore`'s `wr1` residue"* row | **`· NOW_EXACT 1` added**, so the row sums to its own label, with a note that the census arithmetic was always right and the quick-reference row was incomplete |

⚠ **What discharging them did NOT do.**  No census was re-run, no capture was
re-scored, no engine or board was touched, and **no figure in this verdict, in
the survey or in the ledger changed value.**  A-2, A-3 and A-4 are corrections
to *expressions and a header*, not to results; A-1 and A-5 propagate a figure
that was already right in its source document into a quick-reference that had
fallen behind it.

## APPENDIX B — WHAT THIS CAMPAIGN LEFT AMBIGUOUS

**Flagged rather than resolved, because this document cites and does not
measure.**

* **`T` and `S` were measured on DIFFERENT BITSTREAMS, and the +3.3489 points
  are not decomposed.**  `S` (and therefore `B`) comes from the `wr1` corpus on
  **FLASH #10**; `T` comes from a fresh tranche on **FLASH #11**, which carries
  two `ucore` landings `S` never saw.  Both facts are stated in their home
  documents and the prereg reasons carefully about the *build type* (retention
  vs control) for exactly this comparability reason — but **no document
  separates "the tranche is an easier draw" from "the landings closed seeds",
  and the campaign's own prediction instrument, which tried to, came in 2.985
  points high with a contradicted shape.**  The bar is met either way; the
  attribution is not established.
* **Two different OPEN_BUS detectors are in play in one census.**  The corpus
  exclusion is the registered counter predicate (`ob_escape.feed ≥ 8`, giving
  2,515 scored of 3,150); the offline legs' 184-of-380 denominator is the
  **row-level** detector.  The survey names both and reports that they part on
  exactly one seed (`wr1/223067`), but **the two denominators sit in adjacent
  tables and a reader could take them for one exclusion.**
* **Condition 2's "named family" was broadened in advance** from the six
  families W2 populated to `s15_census`'s eight-family taxonomy plus
  `NOW_EXACT`.  Registered before the tranche existed and it did not bite (the
  twelve fell in four populated families) — but it is a broadening, not a
  restatement, and the plan's §5 wording could have been read the narrower way.
* **The `wr1` offline legs' movement (48 → 84, 49 → 91) is quoted throughout as
  the campaign's own progress signal and is, by its own label, ATTRIBUTION ONLY
  on a divergent-by-construction subset.**  Both `standing_gates.md` and the
  ledger say so every time.  **There is no population-scale offline re-score of
  `wr1` at phase end**, so the only whole-corpus hardware-versus-silicon figure
  the campaign owns is W2's, on FLASH #10, at the pre-landing tree.
* **`PF_GAINED` = 0 and `SCHEDULE` = 7 of 12 in the tranche are read as
  directional evidence in the successor queue** (W4-3, W4-4).  On 141 scored
  seeds with 12 misses, neither is distinguishable from sampling; the ledger
  says so for `PF_GAINED` and does not say it for `SCHEDULE`.
* **"N seeds gained" and the column deltas do not agree, and no document says
  why.**  W3.4 reports *"Bank 3,242: **17 gained**, 0 lost"* beside a combined
  column that moves **+7** (2,138 → 2,145) and a `wr1` leg that moves **+11**
  beside *"15 gained"*; W3.5 reports *"**21 seeds gained**, ZERO LOST over all
  3,242"* beside a combined move of **+8** (2,493 → 2,501).  The obvious
  reconciliation is that the no-loss bar is evaluated over all **3,242** banked
  seeds while the columns score **2,710** (532 are `OPEN_BUS`), so a gain on an
  excluded seed moves no column — **but that is a reading, not a statement any
  document makes**, and W3.1's figures (*"5 seeds gained"* against a combined
  +5) happen to coincide, which makes the divergence easy to miss.
* **The victory tranche is spent, and W6's guard does not un-spend it.**
  `standing_gates.md` states in terms that this is *not* a ratchet — *"a second
  run of the same seeds is not a second sample"* — so **nothing in the tree
  guards the 90.0170 %, and nothing can**: it is a first registration on a
  population that has been drawn.  Finalization registered the `wr1` offline
  guard (§(f.3)) over a **different** population by a **different** instrument,
  and that guard is deliberately worded so it cannot be read as covering `T`.
  What remains forward-facing about the victory itself is §9.9's booked queue,
  not a gate.

---

## REVIEW TRAIL

| | |
|---|---|
| **DRAFTED** | commit **`7607d5f7fb`**, 2026-08-06 — "wrfuzz: the random-wait fuzz campaign VERDICT (DRAFT, pending Codex + user)" |
| **REVIEWED** | **Codex closing review — GO-WITH-CONCERNS**, **seven** concerns raised |
| **APPLIED** | **all seven**, itemised below |
| **GUARD REGISTERED** | concern 6's standing guard — `sw/wrfuzz_wr1_guard.py` over the receipted `wr1` offline columns — **registered in `standing_gates.md` BEFORE finalization and PROVEN GREEN at registration**, both legs, rc = 0: model **84 / 184**, `ucore` **91 / 184**, **0 previously-exact seeds lost, 0 first divergences moved earlier**, denominator 184.  §(f.3) |
| **DISCHARGED** | the **five record discrepancies**, in their home documents — `standing_gates.md` in place, `wrfuzz_provenance.md` by erratum box because it is append-only.  **APPENDIX A is now the correction ledger** and names each corrected location |
| **FINALIZED** | commit **`<pending — filled by the immediately following commit>`**, 2026-08-06 — the commit that applied the seven concerns and removed the DRAFT marking.  (This row is written by the immediately following commit, because a commit cannot name its own hash — the SM3 precedent.) |
| **ACCEPTED** | ⚠ ***pending — the user.***  **Not recorded as given.**  Applying the concerns does not upgrade GO-WITH-CONCERNS to GO; the verdict's standing is the user's to set |

**THE SEVEN CONCERNS, AND WHERE EACH ONE LANDED.**

1. **(HIGH) The simplicity accounting was a blanket claim.**  *"One term, no
   persistent state, no opcode named"* is replaced, at **§(c.1)** and **§(g)**,
   by the review's own itemisation: *no architectural or save-state-visible
   state was added; W3.1 added the transient decode field `LoadResult::ext` and
   renders the entry class with native opcode literals where no PLA class bit
   exists; W3.4 added the transient BIU member `brk_pending_`; W3.5 is one RTL
   term with no state; `SS_VERSION` and the `ucore`'s 205 architectural flops
   remained unchanged.*  And the narrower claim: *no per-delay fitted table or
   opcode-specific behavioural exception; the shadow class is one measured
   microcode-entry class, rendered by three native opcode literals in RTL/model.*
   The three (`07` / `17` / `1F`) were verified in both engines' source for this
   row, not quoted from the ledger.
2. **(HIGH) The victory margin was not qualified as a cross-bitstream delta.**
   Immediately after **§(g)**'s MET clause, and again in the **does-NOT-claim
   block**: *this is a valid MET under the pre-registered post-mechanism
   protocol, but not an apples-to-apples FLASH-#10/FLASH-#11 delta: the +3.3489
   points combine a fresh population draw with two intervening `ucore` landings,
   and the record does not decompose those effects.*
3. **(MEDIUM) Condition 2's denominator read as 141.**  **§(a.2)**, **§(e.2)**
   and **§(g)** now read: *condition 2 satisfied on 12/12 scored non-exact seeds;
   the tranche denominator was 141 scored, comprising 129 exact and 12
   non-exact* — with the reason the two denominators differ stated, because a
   cycle-exact seed has no first divergence to classify.
4. **(MEDIUM) The freeze was described as "the identical imported code path."**
   **§(a.3)** now reads: *the same registered construction, independently
   implemented for W4; the strata definitions and OPEN_BUS detector are imported
   from W1/W2, while the aggregation is repeated and its result was
   artifact-cross-checked.*  Checked against `sw/wrfuzz_w4.py` for this row —
   `w1.STRATA` and `w2.open_bus` are imported; the per-stratum tally and the mean
   are its own loop.
5. **(MEDIUM) "Decided without landing" overstated two rows.**  **§(c.2)** is
   retitled *"Questions decided or materially narrowed without landing"* and
   names the two that are narrowed rather than decided; **§(g)**'s clause becomes
   *six questions were decided or narrowed; the `+2` discriminator and a viable
   `mc1/721` structure remain open.*
6. **(MEDIUM) Nothing in the tree guarded the campaign's landings.**  A standing
   guard was **registered before finalization and proven green** — see the GUARD
   REGISTERED row above and **§(f.3)**, which states in terms that it is an
   **IMPLEMENTATION guard**: not a silicon-match rate, not a ranking, **not a new
   sample and not a re-claim of the spent 90.0170 % fabric measurement**, which
   is a first registration on a population that has been drawn and can never be
   re-claimed.  Appendix B's spent-tranche bullet was corrected to say the guard
   does not un-spend the tranche.
7. **(LOW) The five record discrepancies were reported, not discharged.**  All
   five are now fixed **in their home documents**, and **Appendix A is converted
   from a discrepancy list into a CORRECTION LEDGER** naming each corrected
   location and its disposition (in-place for `standing_gates.md`, erratum box
   for the append-only ledger).

**WHAT FINALIZATION DID NOT DO.**  No engine was touched, no board was
contacted, no memory file was written and Codex was not launched.  **No figure
in this document, in the survey or in the ledger moved.**  ⚠ **One departure
from the SM3 precedent's "no gate was re-run", stated plainly**: concern 6
required a gate to exist, so finalization **registered one and ran its two legs
once to prove it green**.  They reproduced the receipted columns exactly and the
`ucore` leg reproduces W3.5 §8.7a's own dump seed for seed, so nothing moved —
but a gate WAS run for this document, and that is recorded rather than elided.
