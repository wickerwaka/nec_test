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

## CURRENT STATE (re-verified 2026-07-14) — see closure_checkpoint.md

The single-read handoff is **docs/notes/closure_checkpoint.md** (top
"AUTHORITATIVE PROJECT STATE" block). In brief:
- The whole **waits=0 deterministic surface** (golden 169000/169000 +
  arbitrary-sequence fuzz) and the **hardware-interrupt surface**
  (498/500 chip-vs-TB) are cycle-exact vs silicon; fabric == HEAD
  (no reflash pending).
- ONE deferred class remains: the **doomed-prefetch / accept-edge flush
  machinery** (residuals fz10460 REP-LODS, fz10175 NMI; and swint CD-imm)
  — deferred on risk/reward, would touch the shared flush/vectoring
  machinery for <1% gain.
- **Caveat root-caused 2026-07-14:** a live waits>=1 *chip-vs-TB* fuzz gate
  over arbitrary sequences DIVERGES — a real, accumulating core-vs-chip
  cycle-cadence drift under waits (NOT wait-routing: the chip waits fine;
  NOT tooling: hw-ab chip-vs-fabric drifts identically). The mission-H wait
  model is fitted-exact for its 6 forms (golden w1/w3 pass) but does not
  generalize. Deferred CORE-RTL/reflash item; waits=0 unaffected. Details in
  closure_checkpoint.md "WAITS>=1 caveat".

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

**Closure block final (2026-07-13): 155500/155500 cycle-exact (100.0%),
architectural state 155500/155500 (100.0%) over all 311 documented-form
tranches; wait-state suites 2x 1200/1200.** All 311 forms are 100%
cycle- and state-exact, including the final four implemented forms
INS/EXT (0F 31/33/39/3B) and every previously parked residual
(SUB4S/CMP4S carry+sibling rails, FF.2/FF.6 push slot, C8 PREPARE,
8F.0 reservations, POP-PSW race, REP-abort). The last residual - 8F.0's
mod3 ghost-read ADDRESS (60 cases) - was RESOLVED 2026-07-13 as a
documented golden-schema don't-care: the undocumented 8F /0 mod3
register-POP writes no register and its single stack read is discarded,
so the chip's committed read address (stale pre-window injection-stub
latch state, deterministic but unreproducible by a backdoor-injected
core) is architecturally inert and masked in the replay comparison. No
RTL/reflash; evidence + resolution in docs/notes/closure_checkpoint.md.
The campaign exit gate (>=500-sequence fuzz run with zero divergences)
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
  ALL 15 interrupt forms + all IN forms are now 100% cycle- AND
  state-exact in the golden suite (the earlier POP-PSW boundary-race and
  REP-abort flush-slot ±1 residuals were RESOLVED in the closure block —
  INT.F3AA is 200/200; see interrupt_model.md). The remaining interrupt
  imperfection lives only in the arbitrary-context INJECT fuzz gate
  (498/500 chip-vs-TB), not the golden suite.
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
  - ~~8F.0 ghost-read address residual~~ RESOLVED 2026-07-13 as a
    documented golden-schema don't-care (undocumented mod3 register-POP's
    discarded stack-read address; architecturally inert stale injection-
    stub latch state). Grand regression now 155500/155500. See
    docs/notes/closure_checkpoint.md 8F.0 section.
  - Denser undocumented-0F mapping, stacked/randomized prefixes,
    8080-emulation mode (needs the RETEM recovery path), INS/EXT
    mem-mod encodings (undocumented; parked in the core).

### Campaign 4 — in-FPGA A/B verification
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
- **G. Golden-coverage audit + B0-B7/C6/C7 deadlock fix (DONE, 2026-07-13,
  all gates passed)**: a bounded correctness pass. Audited emit_suite's form
  matrix against docs/facts/instructions.json and found the two breadth-fuzz
  deadlocks (B0-B7 MOV reg8,imm8; C6/C7 MOV r/m,imm - no core dispatch) plus
  24 silently-omitted ALU word/direction forms (the core implemented them in
  Mission S but no golden tranche existed - the suite only had the rm8,r8
  representative). Implemented B0-B7 (S_IMM8 + one-idle tail) and C6/C7
  (op_movri store, byte-lane sign-extend law, reserve-then-write cadence);
  emitted all 27 as golden tranches (500 each, both queue variants) from the
  socketed chip. **Grand regression now 169000/169000 cycle- AND arch-exact
  (was 155500; +13500 from the new forms), 347 tranches, no regression.**
  The 24 ALU forms passed with ZERO RTL change - closing the integrity gap
  in the old "155,500 complete" claim. ONE reflash (0 errors, timing MET,
  setup slack +4.185 ns emu clock). Hardware A/B: chip-vs-golden 400,
  core-vs-chip FIRST LIGHT 400, core-vs-golden 400; direct chip-vs-core
  spot-check B0/C6/C7 6/6 each; A/B fuzz fz11000-11499 500/500 zero-
  divergence (now exercising the fixed forms via gen_seq _gen_mov). Deferred
  (documented in closure_checkpoint.md): INM/OUTM 6C-6F, BUSLOCK F0, BRKEM/
  8080-mode, the 0x82 undocumented alias, and the pre-existing wait-state /
  interrupt / 3-cadence-marginal-family generalization gaps.

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

---

## Amendment (2026-08-01) — the `ucsim` campaign

### Decision superseded: "no intermediate software reference model"

The 2026-07-11 decision block above says **"No intermediate software reference
model. The RTL core is developed directly against captured hardware traces."**
That decision is **superseded as of 2026-08-01 (user-directed)** for the
microcode-driven simulator specifically. The earlier text stands as the record
of what was decided then; it is no longer the operative rule.

**Rationale — the calculus changed with the assets, not with the taste.** The
2026-07-11 decision was made when the V20 microcode was "reference material
only": a software model would then have been an *intermediate artifact*, a
second thing to maintain between the traces and the RTL, with no independent
source of truth. What we now hold is a **dumped 1028-row microcode ROM plus
dumped PLAs**. A simulator driven directly by those dumps is not an
intermediate model of the chip — it is **the experiment that measures whether
those dumps are sufficient to build the EU**, and it answers that question
either way. The 2026-07-11 rule remains in force for its original target:
behavioural hand-written stand-ins for the RTL are still not wanted.

The related clause "the V20 microcode research is reference material only" is
likewise superseded: the ROM is now a *normative* source with its own standing
gate (`sim/v30sim disasm` byte-identical to `docs/V20UC.TXT`).

### The campaign and its outcome

Branch `ucsim`, stages S0-S4, **fully offline — zero board time**. The question:
*is the microcode information we hold sufficient to build a fully functional
EU?* Vehicle: `sim/`, a C++20 interpreter that walks ROM rows and never
flattens micro-sequencing into per-opcode C++. Functional (architectural)
accuracy only; cycle timing is a separate later campaign, and the design does
not preclude it.

**Answer: yes for the architectural EU, with an enumerated exception list.**

- Architecturally exact on **7.34 M single-instruction captures across two
  parts**: `v0.1` 169 000/169 000, `v0.2` 347 000/347 000, `v0.3`
  3 699 998/3 699 998, and the real-µPD70108 `v20suite` 3 125 000/3 125 000 —
  the two mass suites **also with every flags-mask disabled** (raw 16-bit PSW),
  so not one undefined flag bit is wrong on either part. Specials
  (`f4a_boundary`, `mod3_illegal`, `f0lock_tranche`, `enter_nesting`) and the
  eleven pin-event pseudo-forms green.
- On **programs**: 3 242 banked fuzz seeds replayed from RESET release. The F-A
  gate **as written scored 2 873 / 3 157 (91.0 %)**; the 100 % result is the
  architectural-anchor subset — **2 125 / 2 125** of the seeds whose capture
  recorded a complete architectural dump are register-, PSW- and
  ordered-write-stream exact (2 123 of them inside F-A's three banks, 2 in F-B's
  `t30-brkem`). 0 GEN-DRIFT, 0 arch-only divergences. The 284 F-A failures are
  **unresolved and unanchored** — the chip's own run never reached the store
  stub in any of them — and are not proven suite artifacts.
- **V20 vs V30: no architectural difference found across complementary suites**
  — 3.125 M real-silicon cases over 282 opcodes and 3.7 M V30 cases against the
  same model. No paired same-vector cross-part A/B was performed, so this is
  "none found", not "none exists". One ROM (dumped from a V20) drives an exact
  V30 model.
- **~76 % of cases end with a PSW every bit of which came out of the microcode
  ROM**; the residue is three named C++ hardware laws.
- The measured "undefined"-flag laws, the REPX prefix-chain rewind, the BCD
  laws and the ENTER walk are **outputs** of the microcode, not inputs to the
  model — there are no flag hooks in the simulator.
- pla_3 (group decode) and pla_2 (condition evaluation) are **identified
  exactly**; `pla_4`'s `mem` portion fits and the rest is open.
- **Micro-row coverage 912 / 1028.** Every unexecuted row is either accounted
  for by a named residual or structurally dead under the stated criterion (not
  machine-proved unreachable); the whole untested ROM surface is **9 substantive
  rows** (the POLL tail behind `JMP BUSY`, 5 rows; bank A of the one ambiguous
  micro-address, 4 rows).
- The scientific product is the **assumption census**: 43 numbered assumptions,
  **41 standing**, of which **6 are free choices** that no dumped asset and no
  capture discriminates (plus two global naming-isomorphism classes and one
  test-bench convention). With the four policy entries and the open residuals,
  that set is precisely "what the microcode information does not determine".

Verdict document: `docs/notes/ucsim_campaign_verdict_2026-08-01.md` (revised at
stage S4r). Plan as executed: `docs/notes/ucsim_campaign_plan.md`.
Provenance ledger (every behaviour tagged ROM / PLA / MEASURED / ASSUMPTION):
`docs/notes/ucsim_provenance.md`. Coverage report: `sim/coverage_report.txt`.
Simulator usage: `sim/README.md`.

### What ucsim adds to the verification arsenal

1. **A second, independent implementation of the EU.** The RTL core was derived
   from silicon traces; ucsim is derived from the microcode ROM. Two
   implementations from two different sources can be cross-checked against each
   other on any input, offline and at mass-suite throughput (3.7 M cases in
   ~9 min end to end, decompression and the Python checker included), without
   consuming board time. Where they agree the agreement is evidence; where they disagree, one
   has a bug and the provenance ledger names the claim to check.
2. **A mechanism oracle for the RTL's fitted rails.** The two 2026-08-01 pilots
   (`docs/notes/ins_microcode_pilot_2026-08-01.md`,
   `enter_microcode_pilot_2026-08-01.md`) showed the real micro-march predicts
   what `v30_eu.sv` approximates with per-geometry rail forests; ucsim supplies
   the architectural half of the same argument and lands on the same families.
   `enter_nesting` 666/666 with the nesting *not* masked mod 32 is the sharp
   case: the task-#31 RTL bug class is unrepresentable in a march that walks
   those rows.
3. **A pre-board filter.** Any question that can be settled from the ROM plus
   retained captures no longer costs a board session; the campaign closed A19,
   R8, `F1`, A12 and R4 that way, and it also *proved* which residuals cannot
   be settled that way (status-latch persistence: 0 of 3 242 seeds discriminate;
   A30: bank A unreached even with 8080 mode live; R6: no `CL = 0` case exists
   anywhere in either mass suite).
4. **A carried-forward timing scaffold.** The `F`/`Q` interlock call sites are
   preserved in `sim/exec.cpp` for a future cycle-accurate mode, and the four
   deliberate non-modelling policies each name the timing mechanism that would
   replace them.

### Residuals routed out of this campaign (board work, future campaign fodder)

Directed experiments, each with the residual it closes, are tabulated in the
verdict document §(d):

- ALU **status-latch persistence across an interrupt** — a two-instruction probe.
- **A30**, the bank-A selection mechanism — a directed BRKEM + INTR capture; one
  INTA cycle instead of two settles it in a single seed.
- **R1**, the byte-shifter's hidden high byte — undiscriminated by 6.8 M cases.
- **R6**, `0F 20/22/26` with `CL = 0` — un-closable from the existing suites.
- **R2′**, POLL `BUSY` — a POLL tranche with the pin actually raised.
- a **controlled wait-invariance tranche** — needs a re-emission with
  `(program, wait)` as independent axes, not a re-analysis.

---

## Amendment (2026-08-02) — the `ucsim-t` timing campaign

### The campaign

Branch `ucsim`, stages T0-T5. The question: *can the microcode ROM's own
micro-sequencing plus the measured BIU law corpus make the C++ simulator
**cycle-exact** — per-clock row streams matching silicon at arbitrary wait
vectors?* This is the TIME half of the sufficiency question the `ucsim`
campaign answered for ARCHITECTURE.

Vehicle: a second bus policy behind the same interpreter. `sim/exec.cpp` and
`sim/loader.cpp` became `template <class Bus>` bodies with two instantiations —
`CpuT<Biu>` (functional, unchanged, codegen-preserving, verified with `nm -C`)
and `CpuT<BiuTimed>` (timed, owns a CPU clock, emits one row per clock). The
architectural answer therefore cannot drift between the two modes, and every
architectural mechanism the timing work found rode the full 7.34 M sweep before
it landed.

Board policy: socket only (`use_core=False`), **nothing flashed anywhere in the
campaign**, single-writer, `board_idle()` after every session, raw 64-bit
capture words retained with a sha256 beside every derived record. Two board
sessions, roughly a minute of actual board time each; every other stage was
offline.

### The outcome — PARTIAL victory, and the wait axis inverted

**Cycle-exact at the instruction scale, the measured-law scale and the wait
axis; 62.2 % at whole-program scale.**

| gate | result |
| --- | --- |
| `v0.1` cycle rows at w0 | **165 490 / 166 400 (99.45 %)** |
| `v0.1-w1` / `v0.1-w3` | **1 200 / 1 200** each |
| boot replay from RESET release | **220 / 220** rows, loop period exact |
| ENTER waited tranche (154 socket digests) | **154 / 154** on all five levels |
| INS `case250` factorial vs the chip capture | **2 624 / 2 624** strict rails |
| inherited law cards, silicon-referenced | **7 GREEN / 0 RED / 4 UNRESOLVED** |
| banked fuzz programs (3 242 seeds, 1 702 scored) | **947 / 1 702 (55.6 %)** whole-window cycle-exact |
| **THE VICTORY TRANCHE** — 216 fresh never-before-seen seeds | **V0-V4 PASS, V5 FAIL** |

The victory tranche's population was frozen and committed before the first
capture. Scored 188 (28 OPEN_BUS excluded by the bank's own detector, 0
unstable, 0 EVT by construction): **117 / 188 = 62.2 % cycle-exact over the
whole window**, median divergence-free prefix fraction **1.000** — the median
seed is exact through its entire multi-thousand-row capture. **V5, "fresh
random-wait tranche cycle-exact", was pre-registered at 100 % and FAILS; it is
reported failed and no restatement of "cycle-exact" is offered.**

**The project's #1 priority inverted.** Wait-state cycle accuracy was the
standing top priority and the 2026-07-14 caveat in CURRENT STATE above records a
real accumulating core-vs-chip cadence drift under waits. In the SIMULATOR that
axis is now the *strong* one: the fresh tranche's five `wrand` strata score
66.4 % against the four fixed strata's 56.8 % — the random-wait side is BETTER,
by 9.6 points. (The caveat above is about the RTL core and is unchanged; no RTL
work was in scope here.)

Verdict document: `docs/notes/ucsim_t_campaign_verdict_2026-08-02.md`. Plan as
executed: `docs/notes/ucsim_t_campaign_plan.md`. Provenance ledger, every timing
behaviour tagged ROM / LAW / MEASURED / ASSUMPTION:
`docs/notes/ucsim_t_provenance.md` (§0-§15).

**POST-CLOSURE ADDENDUM, same day.** The campaign's one remaining w0 physics
question — the REP string family at `cx >= 2`, 907 cases — was found and closed
offline, no board contact: **M10, one EU bus-request slot that frees when the
bus takes the request**, and **M11, no redirect bubble on a micro-JMP back by
one row**, plus a unification of the OPR-shadow store onto M5b's single A0
rotation. `v0.1` at w0 goes **165 490 -> 166 397 / 166 400 (99.998 %)**, all
five REP forms 500/500, banked fuzz **947 -> 1 002 / 1 702**, wvec digest
**63 -> 69 / 88**; every other standing gate unchanged, five forms moved and all
upward. **The victory tranche did NOT move (117 / 188) and V5 remains a
registered FAILURE** — the tranche's misses are Q2, which was re-measured,
re-diagnosed as a redirect-COMMIT question rather than a QS-port one, and NOT
landed. Ledger `docs/notes/ucsim_t_provenance.md` §16; verdict addendum at the
foot of the verdict document. The registered V0-V5 record is unedited.

### The scientific product — a mechanism ledger, and a model that SHRANK

The deliverable is not the exactness number, it is **fifteen mechanism entries plus
one eval instant, every one of them a register, a threshold or a fixed cycle
index**. There is no fitted table in `sim/biu_timed.{h,cpp}` and no per-opcode
timing exception anywhere in `sim/`.

The whole wait axis reduces to ONE instant per bus cycle,
`e = (N == 0) ? 2 : 3 + N`, derived from the rig's own READY generator rather
than fitted — with the status release at `e`, the display clock at `e+1`, T1 and
`eu_done` at `e+2` and the queue push at `e+3`. That single offset replaced
mission-H's three separately fitted wait laws.

**Four fitted constructs were RETRACTED when the real machine was found, and
nothing larger replaced them:**

1. the T0 "undriven byte lanes retain" rule — an alias of the rig's 0x90 NOP
   fill; replaced by one 8-bit rotator applied on both sides of the bus, which
   closed a ~6 000-case family;
2. the "SUSP lead" — three whole-program legs seemed to want the EU's
   bus-control field one ROM row earlier than 169 000 goldens permit; the socket
   capture showed the EU exactly where the model put it and the PREFETCHER one
   eval early. Premise wrong, not constant;
3. `M3c`'s decode-march "re-run" — a pooling artifact; split by role the pop is
   a plain `max(demand, ready + pen)` and the model is literally smaller (a
   field deleted). A wrong law had survived a 165 490-case w0 gate and still
   owned 87 % of the fuzz bank's first divergences;
4. the grid-is-eval-cadence hypothesis — the stage's own opening hypothesis,
   tested first and falsified at w0 before it could be fitted.

Fitted things that never had to be written at all: the ENTER pilot's grant law
(it is the eval geometry), the per-form `S_RSV` reservation table and the
per-opcode "reservation starts at the final-pop cycle" rule (one mechanism
replaced both), and the MUL/DIV compute-burn model (the length was the R-loop's
stores waiting on one register). Twice the campaign measured a change that
scored BETTER and reverted it because the model was worse.

### The retired biu-rebuild campaign (task #34) — disposition

Retired by user decision on 2026-08-01, before T0;
`docs/notes/biu_rebuild_retirement_2026-08-01.md`. **Closed, not paused**: the
P1-v2 resume path is discarded and there is no resume path. Its law corpus — law
cards C1-C16, the 104 frozen black-box oracle/validation JSONs, the census
artifacts and the B1-B4 tooling — was formally INHERITED by `ucsim-t` as the
constraint set, and every item was either replayed as a gate or explicitly
retired with a reason.

What became of it:

* **Its blocker dissolved rather than being solved.** biu-rebuild was blocked on
  capturing the `resume_slot[phase][occ][fill]` truth table per wait level (the
  Stage-C sled). That table does not exist in the answer. The resume decision is
  `occupancy + bytes-in-flight <= 4`, sampled at a fixed cycle index and latched,
  with one landing window keyed to T4. **The sled was never needed.**
* **Its `B4 = GO` claim is RETRACTED.** Adjudicated at T0 against both artifacts
  and the raw event file: the pre-registered verdict rule was all-`w` and the
  domain was narrowed to `w >= 1` after seeing which cells fired, and the match
  key contains `seed` and `eu_ord` so `0/988` measures within-history
  repeatability, not state sufficiency. `(grid_phase, occ, fill)` may not be
  assumed to close the machine. **The biu-rebuild campaign memory file still
  asserts `B4 = GO` and is stale.**
* **`LC8` (`pf_drain`) stays DELETED** and was never reimplemented, per its own
  must-not-reimplement note. `LC1`'s steady-state gap and `LC2`'s aged band were
  deliberately never implemented either — and both score GREEN, because they
  fall out of three mechanisms none of which is a resume table.
* **Its RTL baseline was found not to be a controlled reference.**
  `sw/biu_rebuild_wvec_freeze.py` + the `Vtb_v30_core` binary produced a wvec
  corpus that was degenerate at 2 of its 4 configs; the campaign re-froze that
  corpus **against silicon** instead, which is what converted four law cards
  from RTL-referenced to silicon-referenced. Do not cite the TB reference until
  it is rebuilt from a clean tree.

### The natural next campaign — regenerate the RTL from the mechanism ledger

**The mechanism ledger IS the RTL spec.** This is the campaign the 2026-08-01
retirement decision deferred ("the RTL is eventually regenerated from the closed
laws in a fresh campaign"), and it is now specified rather than aspirational.

What it would look like:

* **A BIU written from verdict §(b)** is a T-state FSM, a status register, a
  6-byte queue with two latency flops, one occupancy comparator sampled at cycle
  index 2, one landing-window pair keyed to T4, one 8-bit rotator and three
  flush rules. That is a small module, and every one of those parts has a
  measured falsifier attached.
* **Every `v30_eu.sv` / `v30_biu.sv` rail forest now has a documented mechanism
  replacement.** The two 2026-08-01 pilots did INS (≈8 per-geometry qualifier
  families and ≈79 fitted rail constants → 4 global integers) and ENTER (6 FSM
  states, three fitted delays, two patch flags → the ROM row sequence plus 7
  integers). This campaign extends it to the BIU: `S_RSV` → F2; the per-opcode
  reservation rule → F2; the loop family's `dly<=3/dly>=4` cutoff → the SUSP
  row's position; mission-H's three wait laws → the eval instant; the grant law
  → the eval geometry; the MUL/DIV burn table → the OPR interlock; the resume
  truth table → one threshold plus three mechanisms.
* **It can be graded without board time.** `timed_gate` (w0/w1/w3),
  `check_boot --timed`, `timed_scenario`, `timed_enter_replay`,
  `timed_ins_replay`, `timed_wvec_gate`, `timed_lawcards`, `timed_fuzz` (banked
  + the frozen victory tranche) are standing regressions, and four read-only
  instruments turn "N cases fail" into "one mechanism is missing here". The
  simulator is the reference model; the RTL becomes a downstream consumer, which
  is exactly what the retirement decision said.
* **And it inherits the honest caveat.** The model is not cycle-exact over whole
  programs. A regenerated RTL inherits Q2's unmeasured EU-raise clock (`a`
  varying 4..7 by microcode path — the first item for any successor), the four
  UNRESOLVED law cards' missing stimuli, the 907-case w0 REP family, and the
  untouched interrupt/INTA and 8080-mode timing axes. **It would be a better
  starting point than the current rail forest, not a finished core.**

### Routed out of this campaign

* **Q2's EU-raise half** — the largest named residual, half measured (the queue
  port frees at T4+2 under waits, 293/293) and half not. A directed factorial
  over the branch forms at controlled wait levels is the experiment.
* **`has_brkem` under-reports** — a FUNCTIONAL-side finding. The chip's PLA
  decodes a wide spread of undefined `0F xx` second bytes as BRKEM; the banks'
  flag counts only `0F FF`, and 189 of 3 242 seeds put emulation mode on the
  pins. Erratum filed in `docs/notes/ucsim_provenance.md` §67; re-derive any
  8080-mode statistic from PS3, which is now observable.
* **A30** — one uncontaminated datapoint (a two-cycle INTA pair taken in
  emulation mode) favouring bank B / fixed priority. n = 1; the directed
  BRKEM + INTR capture still settles it and is now cheap to score.
* **Parked probes not run**, recorded rather than hidden: status-latch
  persistence (verify its ROM-sweep precondition offline first), R6 BCD `CL=0`,
  the two POLL `BUSY` split probes, R7 CMP4S, F1 BUSLOCK.
