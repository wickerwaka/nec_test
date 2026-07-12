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

### Campaign 3 — the core  ← CURRENT
v30_core.sv (EU + BIU) developed against trace replay in the Verilator TB:
a golden-trace checker feeds captured initial state + memory image, runs
the core, diffs per-cycle bus/queue behavior against the real chip's
capture. Grow opcode by opcode using campaign 2's corpus, BIU first
(campaign 1's model).

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
- Remaining for campaign completion:
  - Full-scale emission of every documented form (the 78-form corpus
    is the systematic sample). With the emitter, serve runner, and
    event scheduler proven at ~0.4 s/case, a final full-scale emission
    block (~150 documented forms x 500 cases ≈ 10-12 h of board time)
    plus per-form spec additions is the single largest remaining item
    and would close the campaign's behavioral coverage.
  - Residual documented forms not yet golden-tested: OUT (E6/E7/EE/EF)
    and the remaining IO family, CMPBK/SCAS-class flag-writing string
    ops + their REP forms, remaining REP variants (F2/REPNE, word
    strings), ALU imm/rm forms (80-83), TEST/NOT/NEG/MUL signed
    variants beyond the sampled set, rotates/shift-by-CL (D1-D3),
    BCD adjust ops (27/2F/37/3F, 0F 22/26/2A/2E), PUSH/POP sreg +
    PUSHF/POPF, far CALL/RET/JMP + software INT (CC/CD/CE) + IRET
    (RETI), Jcc full set, LDS/LES (C4/C5), IMUL forms 69/6B, INS/EXT
    (0F 31/33/39/3B), BRK3/BRKV vectoring, and the two block-4
    residual laws above.
  - Denser undocumented-0F mapping, stacked/randomized prefixes,
    8080-emulation mode (needs the RETEM recovery path).

### Campaign 4 — in-FPGA A/B verification
The core instantiated in the harness FPGA behind the same bus interface;
harness runs identical images against core and socketed chip, diffs
captures automatically. Agent loop drives divergence hunting. Done = no
divergence across the corpus, including edge cases (interrupts, 8080
mode, undocumented opcodes, wait-state sweeps).

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
