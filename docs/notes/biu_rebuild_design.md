# BIU QUEUE/PREFETCH REBUILD — Phase 1 DESIGN

Baseline / rollback commit: **c0c28f1**. Ground truth = the socketed
uPD70116C-8 (reflash-free, chip position); the w0 golden set is a regression-
DIAGNOSTIC reference, NOT a pass/fail gate. Companion docs: the kludge map
(`biu_rebuild_audit.md`), the measured target law (`biu_model.md` §"Consolidated
bus-grid law" + §BUSLOCK), and the prior campaign's evidence
(`waits_structural_plan.md`, `closure_checkpoint.md`).

## 1. Design goal (restated)

A bus-grid-cycle-accurate queue/prefetch/arbitration/eval model that
reproduces the chip through arbitrary APERIODIC instruction sequences at ALL
uniform wait states (w0/w1/w3 gated, general N intended). The decisive
constraint the current model fails and the rebuild must satisfy: the
prefetch-resume divergence FLIPS DIRECTION with aperiodic leading-phase parity
(biu_model §Round 3 A2). Only a model that carries the TRUE bus-grid phase
across the sequence can be correct in both directions.

## 2. The core architectural idea — a bus-grid slot machine

Replace the BIU's "T-state counter + ~12 qualifier flags" (audit K-BIU) with an
explicit **grid model** whose primary state is:

- `grid_phase` — the true 2-cycle bus-grid phase, defined over the STRETCHED
  grid (advances one step per COMPLETED grid slot, i.e. gated so Tw does not
  advance it the way `ph_ff` wrongly does). This is the first-class replacement
  for `ph_ff`/`bus_phase` (KB7). It must be defined identically-valued at w0
  (where it equals the current parity) and meaningfully at w>=1.
- `q_occ` — queue occupancy in bytes (already have `q_cnt`), PLUS a small
  `fill_state` describing where on the fill/steady-state trajectory the queue
  is (rising-fill vs been-saturated), because Round 2 proved occupancy alone
  cannot distinguish the two decisions that both sit at occupied==4.
- `slot_kind` / `t_state` — where in the current bus cycle we are (T1..T4/Tw),
  retained but subordinate to the grid-slot abstraction.

Every decision the audit lists as a fixed-offset kludge is re-expressed as a
function of (grid_phase, q_occ, fill_state, pending EU request, flush):

1. **Commit/eval** happens at a grid SLOT boundary, chosen by the grid (T3->T4
   at w0-cycles, next-slot-after-T4 for waited cycles) — expressed as "the next
   grid slot," collapsing `evald`/`eval_ext`/`defer_t4`/`defer_idle`/`ff_t4`
   (KB1/KB2/KB3/KB5) into one path.
2. **Arbitration** at each grid slot picks {locked split-half2, ready-EU-with-
   grid-slot-lead reservation, prefetch-if-resume-law-allows} — the A/B/RMW
   registered-readiness rules (KB4) become "was the request up at this grid
   slot," derived from `grid_phase`, not from CPU-cycle `_p1/_p2` pipelines.
3. **Prefetch resume** (the floor) is gated by a `resume_ok(grid_phase, q_occ,
   fill_state)` predicate that reproduces the ~3-idle grid gap for steady-state
   fetch-limited streams AND the immediate refill for queue-fill ramps, keyed
   on phase so it flips correctly. THIS predicate is the whole ballgame — see
   §4 (it needs a controlled-sled measurement pass to pin before coding).
4. **Display** (status/QS=E/UBE/RD) regenerates from the grid slot, retiring
   the `e_wait`/`qs_e` condition pile-up (KB10).

The EU side keeps its microcode FSM but its bus-facing timing (KE1 bus-facing
dly gaps, KE2 reservations, KE3 eu_done chains, KE4 eu_soon) converts to
GRID-cycle counts: a `dly` that must track the grid counts DOWN only on
completed grid slots (the `bus_tw`-gated pattern, already prototyped), and
reservations lead by one GRID slot. EU-bound compute burns (KE1 burns) stay
fixed CPU cycles.

## 3. Interfaces (what changes at the BIU<->EU boundary)

The rebuild is largely INSIDE `v30_biu.sv`. The EU boundary changes minimally:

- ADD/keep `grid_phase` (real, w>=1-valid) — replaces `bus_phase` consumers.
- Keep `eu_wdone`/`eu_rdone`/`bus_tw`/`eu_rd_now`/`eu_rdata_now` (correct-
  direction primitives already present). Extend `bus_tw` usage to gate the EU
  bus-facing `dly` families.
- REMOVE the fixed-offset promise signals `eu_soon`/`eu_soon_ea`/`eu_soon_ivt`
  once the grid-slot reservation subsumes them (they are CPU-cycle "ready next
  cycle" hints the grid model does not need).
- ADD `lock_latch` (EU->BIU): set by F0-prefix decode, persists to the next
  instruction, cleared by the BIU at the locked write's T4 grid slot; drives
  the (new) LOCK pin and the (future) HOLD/RQ-AK arbiter gate. Wire the real
  `BUSLOCK_N` output (currently hardwired `1'b1` in v30_core line 239).

## 4a. STAGE 0 RESULT (2026-07-14) — VERDICT: GO. The resume law CLOSES.

Executed reflash-free on the socketed chip via `sw/exp_resume.py`: self-
contained aperiodic streams (mixed 1/2/3-byte register/imm + mem/RMW ops,
non-repeating RNG order, no jumps/flushes) with the leading bus-grid phase
swept by prepending k=0..7 NOPs, captured at w0/w1/w3 (4 seeds x 8 phases x 3
waits). ~7000 resume events reconstructed with (queue occupancy, phase, fill).

The naive question "does resume_slot close over the coarse 3-tuple (phase,
occ, fill)?" is the WRONG test and must not be used as the go/no-go, because it
is CONFOUNDED by feature-lossiness. Proof: the coarse tuple fails to close even
at **w0**, where the current model is bit+cycle-exact (169000/169000) — e.g.
seed0 eu_ord0 has two phase-shifts (k1,k3) with identical (phase-parity, occ=4,
fill) but resume gap 4 vs 5. Since the chip is provably deterministic and FULLY
modeled at w0, that "contradiction" is my 3 coarse features omitting finer
bus-grid state (in-flight-fetch bytes, q_aged, the intra-cycle grid sub-phase),
NOT a hidden chip variable. Direct confirmation: the current TB reproduces the
w0 synthetic streams EXACTLY (chip-vs-TB seed0/1 k1/k3 w0 = 0 divergent rows) —
including the very k1/k3 gap difference the coarse tuple flagged.

The CORRECT test — the controlled aligned phase-sweep (`exp_resume.py sweep`),
which holds the structural context fixed (same seed, same EU-access-resume
ordinal) and varies ONLY the leading phase — is decisive:
- **256/266 aligned cases are CONSTANT (217) or CLEAN-PARITY (39).** The 39
  CLEAN-PARITY cases are the bidirectional-phase flip, isolated cleanly: the
  resume gap is a two-valued function of phase parity (e.g. seed2 eu_ord4 gap
  1/3 by parity; eu_ord5 gap 1/5). This is direct, controlled reproduction of
  the Round-3 A2 finding.
- **10 WANDER cases** (gap takes >2 values not parity-separated) are ALL
  accounted for by the occupancy ALSO varying across the phase shift (the occ
  annotations differ per k) plus the same finer-state lossiness proven at w0 —
  not a hidden variable. Every WANDER case is w0 (where the model is exact) or
  has occ varying across k.
- The floor is genuinely exercised: chip-vs-TB on these streams DIVERGES at
  w1/w3, and the aggregate bad-row count ALTERNATES with k-parity (w1: even-k
  531, odd-k 300) — the bidirectional flip visible even in bulk.

**CONCLUSION (go/no-go): GO.** The chip's resume law is fully deterministic in
the bus-grid state a bus-grid-accurate model tracks (occupancy + in-flight +
q_aged + TRUE grid phase). There is NO evidence of a hidden/unmodelable
variable: at w0 that exact state already reproduces the chip bit-exact; the ONE
thing that breaks at w>=1 is that the current model's phase is CLOCK parity
(`ph_ff`) rather than STRETCHED-GRID phase, and the controlled sweep proves
grid_phase is the necessary and sufficient additional variable (the gap is a
<=2-valued function of it with occ/fill fixed). This greenlights the Stage-3
resume rewrite, keyed on a stretched-grid phase + occupancy(+in-flight) — which
is exactly what Stage 1 makes first-class. The resume_slot "table" closes over
the full grid state; it does NOT reduce to a coarse 3-tuple, so the rewrite
models the grid state, it does not tabulate.

## 4. The resume law — the measurement that produced the Stage-0 verdict

The floor is the prefetch-resume-after-EU-access / retire cadence under waits.
Before writing the resume predicate, take a CONTROLLED-sled board capture
(reflash-free) to pin `resume_ok` as a function of (grid_phase, q_occ,
fill_state) at w0/w1/w3:

- Sweep leading-phase by prepending k NOPs (k=0..7) to a fixed fetch-limited
  unit and to a fixed queue-FILL ramp; capture chip fetch T1 slots vs queue
  reconstruction. This directly measures the resume grid-slot as a function of
  arrival phase — the Round 3 A2 experiment, but recorded as a truth table
  keyed on (phase, occupancy, rising-vs-saturated) rather than as a pass/fail.
- Deliverable: a small table `resume_slot[phase][occ][fill_state]` at each wait
  level, from which the predicate is written (and which the rebuild is
  validated against directly, decoupled from the golden).

The prior campaign's Round 3 tooling (`/tmp/consolidation/*.py`) is gone but
trivially rebuilt from `sw/sweep_*.py` patterns (per-phase chip-vs-TB grid
sweep). This measurement is Phase-2 Stage 0 and BLOCKS the resume rewrite.

## 5. Staged rewrite plan (with blast radius)

Each stage: build the Verilator TB, run the FULL w0 golden (169000) as a
DIAGNOSTIC (not a gate — regressions are expected and adjudicated per §7), run
the arbitrary-sequence chip-vs-TB fuzz at w0/w1/w3 (the real GATE), and record
the drift metrics (bad-rows mean/median, CLEAN count, net@80). Commit per stage.

- **Stage 0 — resume-law measurement** (§4). No RTL. Produces the resume truth
  table. Blast radius: none (measurement). GATES stage 3.
- **Stage 1 — real `grid_phase` primitive.** Add the stretched-grid phase
  counter; prove it equals `ph_ff` at w0 (w0 golden bit-identical) and is
  defined at w>=1. Re-point `bus_phase` consumers. Blast radius: LOW at w0
  (identity), the enabler for everything. This is the concrete first stage
  (§8).
- **Stage 2 — collapse the commit/eval flags into the grid-slot commit.**
  Re-express `evald`/`eval_ext`/`defer_t4`/`defer_idle`/`ff_t4`/`ext_ok*`
  (KB1-KB5) as "commit at the next grid slot with grid-slot-lead arbitration."
  Blast radius: HIGH — this is the shared machinery the whole surface rests on;
  expect w0 golden diagnostic regressions (adjudicate each vs chip). Do it as a
  refactor that is provably grid-equivalent at w0 first, then let the w>=1
  behavior change.
- **Stage 3 — the resume predicate** from the Stage-0 table. Replaces
  KB6+KB1's `occupied<=4 + resume-at-eval_ext`. Blast radius: HIGH; this is the
  bidirectional floor. Validate against the Stage-0 truth table AND the fuzz at
  w0/w1/w3.
- **Stage 4 — EU bus-facing dly/reservations to grid cycles** (KE1 bus legs,
  KE2 reservations via one-grid-slot lead, KE3 spurious-cycle chains via
  wdone/rdone). Keep EU-compute burns fixed. Blast radius: MEDIUM, per-family
  (the plan's family order applies).
- **Stage 5 — flush / branch resolution on the grid** (KB5 far-flush, KE1
  branch dly). Highest risk (wrong-signed under waits, arch-affecting — Round 3
  Track B). Do LAST, measure the chip flush point across waits first.
- **Stage 6 — BUSLOCK implementation.** Wire `BUSLOCK_N` from `lock_latch`
  (§3), F0 decode in the EU prefix path, HOLD/RQ-AK arbiter gate. Validate the
  LOCK pin timing vs `sw/exp_lock.py` chip capture (assert at execute-start,
  transparent to prefetch, release at write T4). Blast radius: LOW/ISOLATED —
  additive, does not touch the queue/resume path. Could be done EARLY (it is
  independent) if a quick win / second grid observable is wanted before the
  hard stages.

## 6. Validation model (establish now — the GATE for all following stages)

- **GROUND TRUTH = chip-vs-TB** on arbitrary-sequence fuzz at w0/w1/w3 (and
  spot w5/w7), per seed, localized per inter-fetch interval. Tooling exists:
  `sw/check_seq.py` (threads `+waits` into the TB — the fix that made the
  waited gate real), `sw/gen_seq.py`, the `sweep_*.py` per-phase grid sweeps,
  and `sw/check_ab_hw.py` (chip-vs-fabric in silicon). Build a per-seed
  divergence localizer (the Round-1 `localize.py` pattern) as the standing
  metric.
- **BUSLOCK gate**: `sw/exp_lock.py` chip capture vs TB LOCK pin (assert point,
  prefetch-transparency, release-at-write-T4).
- **w0 golden = DIAGNOSTIC**: run it every stage; each regression is
  adjudicated vs a FRESH chip capture (§7), never blindly avoided or accepted.
- **Metrics per stage**: bad-rows mean/median, CLEAN seed count, addrMM,
  net-drift@fetch80, per each wait level. Target trajectory: net@80 -> 0 and
  CLEAN -> most seeds at w1/w3, WITHOUT the bidirectional flip.

## 7. w0-golden regression adjudication (the inverted rule)

When the rebuilt model disagrees with a w0 golden case, adjudicate against a
fresh chip capture (reflash-free, chip position, same image):
- (a) new model matches chip, golden differs => the OLD golden passed via a
  kludge; the model is right — DOCUMENT the exposed hack (cite the audit KB#).
- (b) new model differs from chip => genuine model bug — fix it.
- (c) golden itself mis-captured => flag for re-capture.
Never blindly avoid a w0 regression; never blindly accept one.

## 8. Branch vs master recommendation

**Recommend a dedicated branch** (`biu-rebuild`), NOT master. Rationale:
- Blast radius is large (Stages 2/3/5 touch the shared eval/prefetch/flush
  machinery the entire w0-w7 surface rests on) and w0 golden regressions are
  EXPECTED and intentional mid-rewrite — master must stay at the 169000/1200
  cycle-exact baseline for A/B reference and rollback.
- The validation flow needs to A/B the rebuilt TB against BOTH the chip AND the
  current-master TB (to attribute each golden delta to a specific kludge). That
  requires master intact.
- Reflash happens only after a batch of stages banks green on the branch; the
  board's single-writer rule means the branch and master bitstreams are
  swapped deliberately, not continuously.
Merge to master only when the chip-vs-TB fuzz gate at w0/w1/w3 meets or beats
the current w0 baseline AND closes the bidirectional w>=1 drift (or a
documented, adjudicated new floor is reached). Keep `c0c28f1` as the rollback
tag.

## 9. Honest scope / risk assessment

- **Scope is large.** This is a from-scratch rebuild of the BIU's core
  decision machinery (KB1-KB10) plus a per-family EU bus-timing conversion
  (KE1-KE4). The EU microcode FSM (~4800 lines) is largely reused; the rewrite
  concentrates in `v30_biu.sv` (~950 lines) and the BIU<->EU interface.
- **Expected w0 golden regressions and what they expose.** Stage 2/3 will
  regress w0 golden cases that currently pass via `eval_ext`/`defer_idle`/
  `ff_t4`/`ext_ok*` phase-aliases (KB1-KB5) and the `occupied<=4`+`q_aged`
  resume (KB6). Each regression is a candidate "old golden passed by kludge"
  (§7 case a) — most likely the idle-window reader commit (KB3), the far-flush
  fast path (KB5), and the RMW registered-readiness rule (KB4), which are the
  most nakedly fitted. Some will be genuine bugs (case b) — the risk is that
  the grid-slot refactor mis-times a case the flags happened to get right.
- **The central risk is the resume predicate (Stage 3 / the floor).** If the
  Stage-0 measurement does not yield a clean `resume_slot[phase][occ][fill]`
  table — i.e. if the resume depends on MORE history than (phase, occ,
  fill_state) — the rebuild inherits the same floor at a lower level. The
  Round-3 evidence says phase is THE missing variable, but the fill/occupancy
  coupling is not yet fully pinned; Stage 0 must confirm the table closes
  before committing to the resume rewrite.
- **Branch/loop resolution (Stage 5) is wrong-signed under waits** (chip
  flushes ~2 cyc EARLIER). It is the highest arch-regression risk and is
  deliberately last; it may itself be a residual floor if the flush-point-vs-
  wait law is not cleanly grid-expressible.
- **Interrupt timing under waits is out of scope** (fitted at w0; the
  fz10175/fz10460 doomed-prefetch/accept-edge class is separately deferred).
  The rebuild should not regress w0 interrupt behavior but does not aim to
  close waited interrupt vectoring.

## 10. Concrete first rewrite stage to start with

**Stage 1: introduce the real `grid_phase` primitive** (with Stage 0's
resume measurement running in parallel, since it is pure measurement and gates
Stage 3). Specifically, on the `biu-rebuild` branch:

1. Add a `grid_slot_phase` register in `v30_biu.sv` that advances exactly once
   per COMPLETED bus-grid slot (T1..T4 counts as the slots it is; Tw does NOT
   advance it — the bug in `ph_ff`, KB7 line 850, is that idle/Tw cycles toggle
   it freely). Define it so at w0 it is bit-identical to the current
   `ph_ff`/`bus_phase` (prove via the 169000 golden staying bit+cycle-exact
   with `bus_phase` re-sourced from it) and so it carries a well-defined value
   across Tw at w>=1.
2. Re-point the existing `bus_phase` consumers (EU pop-anchored slots: `op_popm`
   disp reads, BRK vector-pop) at it. w0 diagnostic must stay 169000/169000.
3. Measure w1/w3 drift WITH the real phase exported but not yet driving any
   decision — expect baseline (present-but-inert, the same clean-primitive
   proof Round 1 used for `eu_rdone`/`bus_tw`).

This is deliberately the lowest-blast-radius, highest-leverage first move: it
is w0-neutral by construction, it makes the phase variable the whole rebuild
needs first-class, and it is the prerequisite for the Stage-2 commit-collapse
and the Stage-3 resume predicate that actually close the floor. It also lets
Stage 6 (BUSLOCK) proceed independently at any time as an isolated, additive
win and second grid observable.
