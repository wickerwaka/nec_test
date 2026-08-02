# ucsim-t campaign plan — as executed (verbatim in-repo copy)

The plan the campaign was run against, committed at T5 so that the gates in
`docs/notes/ucsim_t_campaign_verdict_2026-08-02.md` can be read against what
was actually registered.  Source: `~/.claude/plans/zippy-swinging-meerkat.md`,
adopted 2026-08-01.  Reproduced UNMODIFIED below the rule; the verdict's §(a)
"Deviations from pre-registration" records every place execution departed from
it.

---

# Campaign: ucsim-t — cycle-accurate timing mode for the microcode simulator

(Prior plan on this file = the ucsim functional campaign, CLOSED 2026-08-01
with Codex GO; preserved in-repo as `docs/notes/ucsim_campaign_plan.md`.)

## Context

The ucsim campaign proved the microcode ROM + PLAs sufficient for the
*architectural* EU (7.34M cases exact, raw PSW included). This campaign asks
the same sufficiency question for TIME: can the ROM's micro-sequencing plus
the measured BIU law corpus make the C++ simulator **cycle-exact** — per-clock
row streams matching silicon at arbitrary wait vectors? Wait-state cycle
accuracy is the project's standing #1 priority; the gold gate is a FRESH
random-wait tranche captured from the socket.

**User decisions (2026-08-01):**
- **Board freely available** — agents may schedule socket captures whenever a
  law needs a discriminator (single-writer rule enforced; socket only,
  `use_core=False`; no FPGA flashing anywhere in this campaign; board_idle
  cleanup after every session).
- **Retire biu-rebuild (task #34) entirely.** The C++ sim becomes the
  reference model; the RTL is eventually regenerated from the closed laws in
  a fresh campaign. The P1-v2 resume path is discarded; the law corpus, law
  cards, frozen oracles, and census artifacts are INHERITED here as the
  constraint set. Formal retirement note + task closure in T0.
- Same execution mode as ucsim: auto mode, Opus subagents implement, Fable
  coordinator reviews after every task, Codex reviews at stage gates.

## Assets (inventoried 2026-08-01)

**Cycle oracles (offline):**
- Golden `cycles` rows: v0.1 169k cases (11-column format, README-documented;
  waits appear as extra Tw rows; T4 shows NEXT cycle's status; QS point
  samples); v0.1-w1/-w3 (6 forms × 200 each). Comparison logic to port:
  `check_core.py` `build_rows_sim`/`diff_rows`/`COMPARED_COLS` (idle-row
  bus/data masking).
- fuzz_bank `chip_rows`: 3,242 seeds × ~4k per-clock pin records, wait axes
  fixed 0-3 + wrand wmax {1,2,3,7,15} (census in inventory); the banks were
  BUILT to hold timing divergences (TIMING = dominant promoted class).
- `docs/facts/timing_measured.json`: 306 F-spacing retirement measurements.
- The complete BIU black-box corpus (`sw/testdata/biu_blackbox/`, 104 frozen
  oracle/validation JSONs): chip-oracle-v2..v7 (arbitration; 11-tuple keys,
  consumer_byte_role), prefix-phase (mod-3 law), strio-completion v2..v5
  (QS-overlap + maturity), decoder-drain v1/v2 + multibyte (QS schedules =
  measured byte-demand timing), flush/string/multistack/swint/nmi/hwint
  oracles, case250 INS factorials (800 cells, absolute t1/t4/tw per access).
- Pilot laws: `sw/ins_ucode_pilot.py` (eval law e=(tw>0); S-linear deadlines;
  R2 issue = R1.T4+e+18+off), `sw/enter_ucode_pilot.py` (grant law: slots at
  busfree+1/+3 then free-running; chain = prev.T4+1; 7 constants).
- Law documents: `biu_law_cards.md` (11 MUST cards C1-C7,C9-C12 + 5
  provisional; LC8 DELETED — must-not-reimplement), `biu_rebuild_design.md`
  §2/§4 (stretched grid_phase; resume_ok(phase,occ,fill) = "the whole
  ballgame"; truth-table measurement spec), `biu_model.md` (flush law,
  mission-H commit/eval deferral laws, queue-push defer, cadence laws),
  measurements.md (IDIV law, REP slopes, prefix retirement 2-cycle, MOVBK
  forwarding, boot sequence, alignment penalties).

**Sim hooks (verified):** F interlock single call-site (exec.cpp:536
deliver_read), Q demand (Biu::next_byte), write pairing (Pending/
emit_pending), SUSP/FLUSH hooks, per-txn upc attribution (row-level
attribution for free), rows_ counter. `biu.h` explicitly designed to be
replaced by a timed model. NO clock exists yet.

**Inherited unresolved (now this campaign's discovery scope):**
- Stage-C idle-window truth table `resume_slot[phase][occ][fill_state]` per
  wait level (the capture that blocked biu-rebuild; spec in design doc §4;
  BOARD, k=0..7 NOP-prepend sled).
- grid_phase stretched-grid idle-window limitation (post-waited idle offset).
- The 20-28% per-cell fittability residual (fabric-vs-chip; the sim starts
  from mechanism and must beat it), prev_tw sign-flip law, done_mismatch
  directional regime.
- B4 closure DOC CONTRADICTION: biu_blackbox_campaign.md says NO-GO;
  biu_rebuild_P1.md + commit c23c6c1 say GO (0/988 at w1/w3, 21/185 w0
  excused). Adjudicate in T0 before relying on (phase,occ,fill) closure.
- strio mature-RMW cell; ≥2-overlapping-pop completion states; multi-byte
  BCD/imm/branch decoder classes; parked ucsim probes (A30 BRKEM+INTR
  bank-A, status-latch persistence after ROM sweep, R6 CL=0 uninterrupted,
  POLL BUSY split probes, R7 CMP4S sweep-or-unobservable).

## Architecture (Plan-agent design, adopted)

- **Dual mode via compile-time policy split**: `CpuT<Bus>` template;
  `exec.cpp` body moves to `exec_impl.h`; functional instantiation
  `CpuT<Biu>` is codegen-identical (7.3M-case gates preserved by
  construction, provable with a before/after wall-time run). New
  `sim/biu_timed.{h,cpp}` instantiated as `CpuT<BiuTimed>`.
- **BIU master clock, EU as client** (no coroutines): `BiuTimed::tick()`
  advances one CPU clock (T-state FSM, READY sample, stretched grid-phase —
  advances only on COMPLETED slots, Tw never advances it — queue push/pop
  latency pipeline, fetch-scheduler decision at eval points, one ClockRow).
  The EU pumps ticks through blocking primitives: `charge(n)` cadence,
  `wait_for_opr()` (F interlock = completion eval per mission-H deferral +
  handover defer), `pop_q(role)` (push lands eval+1, poppable push+2,
  fresh-on-T2 law), `request_read/write/inta` (maturity timestamps for
  arbitration rules A/B). Existing Pending write pairing survives; emission
  goes through granted slots.
- **Row emission**: status modeled as a REGISTERED output written at the
  commit/eval point — T4-shows-NEXT-status and status-active-through-Tw
  fall out of the mechanism. Two emitters: (a) check_core `parse_out`
  textual format so `build_rows_sim`/`diff_rows`/`COMPARED_COLS`/
  `dontcare_cells` apply UNCHANGED (zero-new-code golden comparator);
  (b) chip_rows NDJSON for fuzz/blackbox replay. `upc` attribution kept
  per row.
- **Law tables split by epistemic status**: code = structural/frozen laws
  (grid geometry, eval deferral, qualification rules A/B, grant law from
  enter_ucode_pilot, flush + NEAR +1-late, BUSLOCK, HALT display); data =
  versioned sha-pinned JSON (`resume.json` — keyed on the FULL grid state
  `(grid_phase, q_occ, fill_state, in_flight, q_aged)` since the coarse
  3-tuple provably does not close; `cadence.json` per-ROM-row + R-loop
  per-iteration costs; `maturity.json` = strio-v5 rules loaded directly;
  `drain.json` = decoder-drain/multibyte schedules as-is).
- **Oracle replay, two layers**: L1 `timed-scenario` state-injection unit
  gates (plant each frozen-oracle key state directly — all 2,687
  chip-oracle-v7 keys, strio v5, drain schedules, prefix-phase — observe
  next decision + exact T1); L2 `timed-image` end-to-end replay with
  explicit per-access wait vectors (case250 800 cells) and wrand (Galois
  LFSR 0xB400, advanced once per bus cycle at T1 entry, bit-exact vs the
  rig spec in docs/notes/random_wait_rig.md).
- **Loader timing seam (top risk)**: architectural consumption stays
  pre-row-0 (correctness untouched); byte-role annotations let the timed
  policy schedule QS pops on the measured drain schedules, which SPAN
  instruction boundaries. This decoupling is the hardest seam and the
  designated redesign point if it leaks.
- New harness `sw/timed_gate.py` (+ `sw/ucsim_cycles.py` naming folded
  into it); CLI subcommands `timed-run`, `timed-image`, `timed-scenario`.
- Known scope exclusion (matches RTL campaign): interrupt/INTA timing
  under waits stays OUT of every timed gate until measured (T4 board
  block may open it).
- Implementation ladder inside the stages: policy-split refactor →
  naive serial BiuTimed → grid/eval/status + queue latency → scheduler +
  arbitration + drain schedules → cadence calibration ratchet →
  flush/BUSLOCK/HALT → chip_rows + wrand + case250. Ratchet discipline:
  exact-case counts only grow; functional gates re-run at every step.

## Stages

**T0 — Scaffolding + adjudication (offline)**
- Retire biu-rebuild: close task #34, retirement note in docs/notes/
  (branch left as archive; law corpus formally inherited), adjudicate the
  B4 GO/NO-GO doc contradiction (re-read both artifacts + b4_closure_v2
  outputs; write the verdict into the timing ledger).
- Clock/row infrastructure in sim (timed mode skeleton, row emitter, cycle
  counter), `sw/ucsim_cycles.py` row-diff harness porting check_core
  comparison policy. New ledger: docs/notes/ucsim_t_provenance.md (same
  provenance discipline: ROM/LAW(artifact)/MEASURED/ASSUMPTION).
- Gate T0: row emitter reproduces a hand-checked golden case's row stream
  format-identically (not yet timing-exact); functional gates all still
  green.

**T1 — grid core + scheduler + cadence (offline; design ladder S2-S5)**
- Grid/eval/status laws + queue latency first (gate: mission-H fitted
  forms B8/8B/89/F7.6/EB/E8 at w0/w1/w3 row-diffed via unmodified
  check_core comparison; enter_nesting waited digests), then prefetch
  scheduler + arbitration/maturity + loader drain schedules (gate: L1
  oracle unit gates + v0.1 w0 ratchet), then cadence calibration
  (timing_measured.json F-spacing corpus; ratchet only grows), then
  flush/branch + BUSLOCK + HALT (gate: control-flow tranche + f0lock rows).
- Stage exit: boot replay exact; v0.1 169k cycle-row exact at w0; law-card
  MUST set (C1-C7, C9-C12) green as sim unit gates; decoder-drain/
  multibyte/prefix-phase oracle replays green. Codex review T1.

**T2 — wait axis (offline + board as needed)**
- Eval-deferral laws, stretched grid_phase (fix the idle-window definition
  — this is discovery, board sled capture per design-doc §4 if retained
  data underdetermines), queue-push defer, grant law under waits, wrand
  input plumbing.
- BOARD: the resume_slot[phase][occ][fill] truth-table capture (the
  blocked Stage-C sled), frozen-then-validated per blackbox protocol
  (5 reps, 4/8MHz, dual histories).
- Gates: v0.1-w1/-w3 cycle-exact (2,400); ALL frozen blackbox oracles
  replayed in-sim and green (chip-oracle-v7, strio v5, prefix-phase,
  case250 INS 800 cells, ENTER waited digests + durations); INS/ENTER
  pilot planes reproduced from the sim (not the offline scripts).

**T3 — sequence timing (offline)**
- fuzz_bank chip_rows: cycle-exact replay across all wait axes. This is
  the monster gate; survey-then-fix with the biu-rebuild diagnostics
  (prev_tw sign-flip, done_mismatch regime) as triage lenses. Target:
  beat the 72-81% fabric fittability decisively; enumerate any residual
  as laws-to-discover, each routed to a directed factorial (board).
- Gate: TBD numerically at T3 entry from the T2 survey (pre-registered
  before the run; no post-hoc redefinition — S4r lesson).
  Codex review T3.

**T4 — board block: fresh tranche + parked probes**
- Fresh random-wait tranche (~200 stratified seeds: wrand×KIND cells +
  waited multi-access + directed wvec law-cells, per the biu-rebuild
  victory spec) captured from socket, then replayed: THE victory gate,
  cycle-exact.
- Parked probes: A30 (BRKEM→8080→INTR bank-A), status-latch (ROM sweep
  first), R6 CL=0 uninterrupted, POLL BUSY split probes, R7, mature-RMW
  cell, ≥2-pop completion — each closes a named residual or becomes a
  documented open with data attached.
- Board discipline: single-writer; socket only; serve-runner etiquette;
  board_idle after every session; captures retained with sha256 beside
  derived records (blackbox conventions).

**T5 — closure**
- Timing sufficiency verdict doc (same standard as the functional one,
  S4r lessons pre-applied: gates presented as defined, exception sets
  complete, plan committed in-repo). Final Codex review to GO. ROADMAP
  update. Micro-row + law coverage rollups.

**Victory** = fresh random-wait tranche cycle-exact + v0.1/w1/w3 cycle
gates + all frozen oracles green in-sim + fuzz_bank gate as pre-registered
at T3 + verdict doc at Codex GO.

## Guiding principle (user directive, 2026-08-01)

**SIMPLICITY.** This is 1980s hardware; NEC wasted no silicon on anything
unnecessary. Complex or confusing observed behavior is likely simple systems
interacting in ways we do not fully understand yet. Operationally:
- Prefer the simplest mechanism that fits; a large fitted table or a
  many-cased rule is a SIGNAL OF MISUNDERSTANDING, not a deliverable.
- Law tables (resume, cadence) are scaffolding: the stage isn't done until
  each has either collapsed into a small mechanism (a counter, a latch, a
  phase bit interacting with another) or its irreducibility is argued from
  the silicon's own economics.
- When a model needs a special case, first ask which two simple machines
  are interacting to produce it (the campaign's own precedents: the
  "max-of-two-deadlines" law = one march + one interlock; the ±1 wait
  adjustments = one eval-deferral flop; the grant law = a 2-clock grid
  running out).
- Every agent brief carries this principle verbatim.

## Mechanics

- Branch: continue on `ucsim` (the sim is the artifact; timing mode is
  additive). Functional gates are standing regressions — every commit keeps
  them green (fast functional mode must not regress).
- Board scripts: reuse sw/ serve-runner infrastructure; nothing flashed.
- Tasks: T0..T5 in the ledger, sub-split as needed; review after each.

## Verification

- Every stage gate is a runnable command recorded in the ledger.
- Row-diff harness `sw/ucsim_cycles.py` (ported comparison policy) is the
  standing cycle gate; oracle-replay adapters are standing unit gates.
- Pre-registration discipline for T3/T4 numeric gates (freeze before run).