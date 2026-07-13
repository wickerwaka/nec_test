# Roadmap

**Ultimate goal: a cycle-accurate FPGA recreation of the NEC V30 (μPD70116),
verified cycle-for-cycle against the real chip.**

Everything else in this repo — the harness, the tools, the test suites, the
measurements — is instrumentation in service of that. When choosing work,
prefer the item that most directly advances the current campaign below;
resist tool-polishing beyond what the campaign needs.

Definition of done: the V30 core, running in this same FPGA behind the same
harness interface, produces capture traces indistinguishable from the
socketed real chip across the full test corpus (architectural state AND
per-cycle bus/queue behavior).

## Decisions (2026-07-11)

- **No intermediate software reference model.** The RTL core is developed
  directly against captured hardware traces, replayed in the Verilator
  testbench as golden vectors.
- Behavioral (black-box) implementation; the V20 microcode research is
  reference material only.
- Test data format: SingleStepTests V20 schema extended for the 16-bit bus.

## The path

### Campaign 1 — BIU characterization sprint  ✅ COMPLETE (2026-07-12)
The closed set of designed experiments that no documentation ever captured.
Exit criteria: docs/facts/biu_model.md states, with measurements behind
each claim: queue depth and refill threshold; fetch/EU bus arbitration and
idle patterns; flush-to-refetch penalty (even/odd targets); wait-state
interaction; fetch behavior at odd addresses; self-modifying-code distance.
Experiment list:
1. Queue-limit probe: long instruction (DIV) while BIU fetches — count
   fetches until pause → depth + threshold.
2. Flush penalty: jumps to even/odd targets, measure flush→first-fetch→
   first-F latency.
3. Saturated-queue F-spacing: NOP sleds + one variable instruction →
   per-instruction decode+execute isolation (validates method for
   campaign 2).
4. Arbitration: memory-heavy instruction stream during prefetch.
5. Wait-state sweep on 1-4 (BIU-bound vs EU-bound separation).
6. Odd-target first-fetch width; SMC distance probe.

### Campaign 2 — per-opcode database at scale  ✅ COMPLETE (2026-07-12)
Delivered: 306 measured timing forms with class-consistent deviation
tables (docs/facts/timing_measured.json, measurements.md); all 53
instructions.json uncertainties resolved; undefined flags classified per
class and proven bit-exact with the V20 (docs/facts/undefined_flags.md);
undocumented 0F space mapped (docs/facts/undocumented_0f.md); persistent
serve runner at ~0.3 s/case; SingleStepTests-format emitter
(sw/emit_suite.py) with prefetched variants via the 63 C0 preload, and a
26-opcode x 500-case sample tranche (tests/v30/v0.1).

Residuals (pick up during Campaign 3 as needed):
- Full-scale emission runs (all documented forms; tranche is a sample)
- IN/port-read opcodes blocked on configurable IOR data (RTL item 1)
- Denser undocumented-0F second-byte map (class boundaries)
- Prefix/REP randomization in emitted cases
- POLL timing (needs the pin-event scheduler, RTL item 3)

### Campaign 3 — the core  ✅ COMPLETE (2026-07-13, incl. exit gate)
Exit gate SATISFIED: 500/500 consecutive sequences (fz600-fz1099) with
zero divergence on the real board (chip vs core full-trace diff), after
the Campaign 4 Mission D laws landed (disp-reader pop defer, disp16
store-ready, split-access segment wrap). Zero QS flickers in the run.
v30_core.sv (EU + BIU) developed against trace replay in the Verilator TB:
a golden-trace checker feeds captured initial state + memory image, runs
the core, diffs per-cycle bus/queue behavior against the real chip's
capture. Grow opcode by opcode using campaign 2's corpus, BIU first
(campaign 1's model).

**Closure block final (2026-07-13): 155440/155500 cycle-exact (99.96%),
architectural state 155500/155500 (100.0%) over all 311 documented-form
tranches; wait-state suites 2x 1200/1200.** 310/311 forms are 100%
cycle- and state-exact, including the final four implemented forms
INS/EXT (0F 31/33/39/3B) and every previously parked residual
(SUB4S/CMP4S carry+sibling rails, FF.2/FF.6 push slot, C8 PREPARE,
8F.0 reservations, POP-PSW race, REP-abort). Single characterized
residual: 8F.0's mod3 ghost-read ADDRESS on the final captured row
(60 cases, cycles-only; pre-window harness-stub latch state invisible
to the golden schema - see docs/notes/closure_checkpoint.md). The
campaign exit gate (>=500-sequence fuzz run with zero divergences)
was reassigned by the coordinator and remains open.

Status (2026-07-12, blocks 1-4 complete):
- **59 opcode forms cycle- and state-exact**, 500 golden cases each
  (29,500/29,500 full): ALU rm8,r8 x8, MOV family (88/89/8A/8B, sreg
  8C/8E, moffs A0-A3), XCHG 86/87, LDEA, TRANS, CVTBW/CVTWL, INC/DEC/
  PUSH/POP r16, B8-BF, shifts D0/4, MULU8, DIVU16, IDIV8/16 (+ traps),
  INC8 FE/0, 0F18/0F20/0F28, control flow EB/E9/Jcc/DBNZ/CALL/RET(n),
  string singles A4/A5/AA/AB/AC/AD, REP F3AA/F3A4 (CW 0-3), segment-
  prefixed 26/2E/36/3E + 8B; boot replay cycle-exact from RESET.
- **Wait states verified** (mission H): golden tranches at waits=1 and
  waits=3 (2x 1200/1200); the deferred-completion-eval laws are in
  biu_model.md "Wait states, cycle-level laws" — Campaign 4 runs behind
  the same READY path.
- **Block 4 (missions L/M/N): interrupts, HALT, POLL, IN** — Q14
  answered (docs/facts/interrupt_model.md); harness pin-event
  scheduler + IORD in service (serve protocol v2 with per-RUN
  evt/pins/iord); 15 interrupt-form tranches (200 cases each) + 4 IN
  forms (500 each) emitted with evt/pins/iord/close_addr schema
  extensions; INT/NMI recognition + INTA pair + vectoring, HALT
  entry/wake (incl. the V30-specific masked-INT resume), POLL, EI/DI/
  POP-PSW IE laws, REP interruption, and IN implemented in the core.
  13 of 15 interrupt forms + all IN forms are 100% cycle- and
  state-exact; cycle rows are 100% on everything except INT.F3AA.
  Known residuals (documented in interrupt_model.md): the POP-PSW
  boundary-race PSW commit (bimodal, 53/200 arch) and the REP-abort
  flush-slot ±1 (33/200 cycles).
- ~~Full-scale emission + residual documented forms~~ DONE (closure
  blocks, 2026-07-12/13): all 311 documented-form tranches emitted and
  fitted; coverage numbers above. Per-form laws live in the RTL
  headers/comments and the git log.
- Remaining for campaign completion:
  - **Exit gate: sequence-fuzz divergence hunt** (sw/gen_seq.py +
    sw/check_seq.py) - Mission S RAN (2026-07-13), gate NOT yet passed.
    ~110 random sequences + ~150 isolated repros on the real board.
    THREE divergence classes found & FIXED (golden regression held at
    155440/155500 throughout): (1) ALU r/m word+direction forms - 24
    opcodes were UNIMPLEMENTED (parked S_HALT), a real functional gap the
    single-instruction suite missed; (2) PUSH bus-reservation phase; (3)
    reg-EA reader commit-at-T4. Clean rate rose to ~42% (17/40 fresh
    seeds). OPEN blocker: the disp8/disp16 reader commit-phase timing
    class (16/23 of remaining divergences) - a reader read that becomes
    ready exactly on a prefetch T3 commits early on the core but the chip
    defers ~2 cycles; a multi-phase fit entangled with push-absorb that
    needs the Campaign-4 in-FPGA A/B measurement to resolve safely (blind
    BIU edits regress the 155,500 goldens). Minor: a self-correcting QS
    pin flicker; and one gen_seq containment escape (tooling, not core).
    Full taxonomy + repro recipes in docs/notes/closure_checkpoint.md
    (Mission S section).
  - 8F.0 ghost-read address residual (characterized; needs a schema
    extension or the injection stub modeled - or defer to Campaign 4
    where the stub runs for real).
  - Denser undocumented-0F mapping, stacked/randomized prefixes,
    8080-emulation mode (needs the RETEM recovery path), INS/EXT
    mem-mod encodings (undocumented; parked in the core).

### Campaign 4 — in-FPGA A/B verification  ← CURRENT (2026-07-13)
The core instantiated in the harness FPGA behind the same bus interface;
harness runs identical images against core and socketed chip, diffs
captures automatically. Agent loop drives divergence hunting. Done = no
divergence across the corpus, including edge cases (interrupts, 8080
mode, undocumented opcodes, wait-state sweeps).

Progress (mission block 1):
- **A. Integration + sim (landed, 61185d0)**: v30_core instantiated in
  system_large behind CFG.use_core (bit 25). nec_bus AD refactored to a
  unidirectional trio so the A/B mux has no tri-state loop and the
  chip datapath stays bit-identical (tb_harness green, 155440/155500
  golden untouched). tb_ab.sv + sw/check_ab_sim.py exercise both selector
  positions in Verilator. Chip position passes; CORE position boots and
  fetches correct bytes but DESYNCS (EU pops one cycle early) - a
  read-data hold-margin race at the core's T3->T4 sampling edge vs
  nec_bus releasing drive_en at that edge. This is the gate; fix before
  hardware. (Details: docs/notes/bringup_log.md 2026-07-13.)
- **B. Safe-flash (done, tested)**: sw/safe_flash.sh (prep -> quartus_pgm
  -> status/magic verify, timeouts, STOP-on-unreachable). Validated once
  with the known-good bitstream; board round-trips + echo passes.
- **Host path**: CFG.use_core plumbed through v30ctl.py / v30run.py; board
  v30ctl.py updated.
- **Fuzz prep**: gen_seq containment escape fixed (atomic DIV/string
  gadgets, branch-target snap); QS-flicker classified as a display
  artifact in check_seq (--strict-qs to override).
- **A2 (done)**: core-side input hold-margin pipeline; core boot-matches
  the chip golden in-harness in sim; chip path bit-identical.
- **D (done, chip-vs-TB; silicon A/B confirmation rides with C)**: THREE
  laws measured via sw/sweep_dispphase.py (168-cell matrix) + the
  tb_v30_core +eudbg state dump, all golden-neutral (155440/155500
  exact baseline):
  1. disp-reader final-pop defer (fresh queue head + fetch T2) - the
     Mission S blocker;
  2. disp16 store ready @ hi-pop+2 (old rdy@+3 was phase-aliased);
  3. split word access at offset FFFFh wraps to offset 0 of the same
     segment (16-bit offset math; core was doing 20-bit linear +1).
- **E (ALL GATES PASSED)**: base 500/500 (fz600-1099); expansions each
  re-gated at 500/500: callret (fz1100-1599), +sregw (fz1600-2099),
  +popf (fz2264-2763). fz2263 = the documented undocumented-encoding
  park residual (FE /7 reached via deterministic garbage execution; the
  core matched silicon bit-for-bit up to the undocumented opcode).
  ~2560 board-vs-TB sequences total this session; zero QS flickers.
- **C (FIRST LIGHT achieved, 2026-07-13)**: after a second synthesis fix
  (iterative shifter, commit e7c315a - the 255-deep `shrot` cone that
  still dominated quartus_map after the divider), the full-RTL bitstream
  built clean: **quartus_map 3m47s** (was ~25 min), Fmax 84.82 MHz emu
  clock (setup slack +9.151 ns), 23% ALMs; only 2 megafunction dividers
  left, both the intended small 8-bit AAM. safe_flash'd the .sof
  (VERIFY ok, use_core=False). In silicon: chip-position boot MATCHES
  the golden over 800 rows (known-good path undisturbed); **the in-fabric
  core boot MATCHES the socketed chip over 800 rows (first light)**; and
  the in-silicon A/B sequence fuzz (chip vs fabric core, both on the
  FPGA) is fz4000-4539 540/540 clean - the definitive in-silicon
  confirmation of the Mission D disp/split laws. **Campaign 4 A/B
  done-criterion SATISFIED: fz4040-4539 500/500 zero-divergence, the
  true-silicon analogue of the Campaign 3 exit gate.** The in-fabric V30
  core is cycle-for-cycle indistinguishable from the socketed chip
  across the fuzz corpus in real silicon.
- **F. Clock-enable (CE) refactor (DONE, 2026-07-13, all gates passed)**:
  the in-fabric core now runs on the fast sys clk and only advances state
  when CE is asserted (CE=nec_bus tick_rise, CE_HALF=tick_fall), decoupling
  execution rate from the fabric clock while staying lock-step with the
  socketed chip. Every sequential process gated `if(srst) ... else if(ce)`,
  reset ungated (bkd_load still fires on RESET); the two subtle desync bugs
  (pulse-default collapse, negedge t1_half2) handled per docs/notes/
  ce_plan.md. Gates: golden 155440/155500 bit+cycle-identical (w1/w3
  1200/1200); CE-hold sanity (+ce_div>1) rows identical + state frozen on
  CE-low clocks; check_ab_sim core boot MATCH 287 rows; tb_harness ALL
  PASSED + largemode_synth.hex byte-identical (chip path undisturbed);
  build 8m40s, timing MET (emu 32 MHz, Fmax 48.09 MHz, setup +5.227 ns),
  util 23% ALMs. In silicon: chip-vs-golden 800/800, FIRST LIGHT
  CE-core-vs-chip 800/800, A/B fuzz fz5000-5499 500/500 zero-divergence.
  Deferred follow-on: a host-selectable independent core-rate CE divider
  (feed the core CE from a host-controllable divider instead of tick_rise).

## Standing infrastructure (build only when a campaign demands)
- Agent-loop orchestration (campaign 2)
- RTL conveniences: store-done latch, pin-event scheduler (INT/NMI tests),
  capture windowing, IOR data config
- Suite publishing pipeline
- 8080-emulation-mode recovery path (before MD-bit probing)

## Deferred / explicitly not now
- Small-mode improvements beyond what exists (large mode is the platform)
- V35 support (second socket on the adapter)
- MAME-based oracle automation (V20 suite + silicon are the oracles)
- Datasheet OCR cleanup beyond what campaigns consume
