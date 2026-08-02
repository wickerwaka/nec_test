<!-- Provenance: verbatim copy of the campaign plan `~/.claude/plans/zippy-swinging-meerkat.md` as executed; imported into the repo at stage S4r, 2026-08-01. -->

# Campaign: ucsim — microcode-driven C++ V30 simulator (functional accuracy)

## Context

Two pilots (2026-08-01: `docs/notes/ins_microcode_pilot_2026-08-01.md`,
`enter_microcode_pilot_2026-08-01.md`) showed the real microcode mechanism
predicts chip behavior the hand-fit FSM EU approximates with per-geometry rail
forests. This campaign validates the converse at full scale: **is the microcode
information we hold (ROM dump + PLA dumps) sufficient to build a fully
functional EU?** Vehicle: a C++ simulator driven directly by the ROM. First
goal is functional (architectural) accuracy; cycle timing is a follow-on
campaign, but the design must not preclude it.

**User decisions (2026-08-01):** 8080-emulation pages implemented but not a
victory gate (validation opportunistic). Campaign victory = functional gates
green; timing is a separate later campaign. NOTE: this supersedes ROADMAP.md's
2026-07-11 "no intermediate software reference model" decision — plan includes
a ROADMAP amendment recording the change and its rationale (the ROM/PLA dumps
changed the calculus: this is no longer an *intermediate model*, it is the
sufficiency experiment for the microcode assets).

## Assets (verified)

- **ROM**: `docs/V20BITS.TXT` — 1028 × 29-bit micro-words, 257 match patterns
  (13-bit mask/cmp = 3 page bits + 8 opcode bits + 2 row bits). Pages: 00?
  native, 000/001 REP variants, 010 F6/F7 (ModRM in opcode slot), 011 FE/FF,
  100 0F (full V30 set incl. INS/EXT/BCD-string/bit ops/BRKEM), 101/110 8080
  mode, 111 internal routines (IRET/INT/MUL*/IDIV*/REPX/SHIFT/ENTER/PUSHA/
  POPA/CALLF/INS/RETF).
- **Encoding spec**: `docs/V20UCDIS.PAS` (normative, executable), structured
  copy `docs/v20_microcode_04.xlsx`, disassembly golden `docs/V20UC.TXT`.
- **PLAs**: `docs/pla_3.txt` + `pla3_outputs.txt` = per-opcode group decode
  (14 outputs, annotated). `pla_2.txt` (26 terms; working hypothesis:
  condition-evaluation PLA — 4-bit cc tails + flag inputs) and `pla4.txt`
  (~45 terms, two output planes) = unidentified; identification is an S0 task
  but NOT load-bearing for the v1 simulator. Die photos `pla_[1-5].jpg`;
  electrical background: dev-zzo blog post (implementation only).
- **Hardware boundary** (`docs/notes/microcode_analysis.md`): queue/BIU,
  loader/pre-decode, EA, interrupt sampling, ALU flag circuits are NOT in the
  ROM — they are C++ hardware models informed by measured laws
  (`docs/facts/*`).

## Validation assets (inventoried)

| Oracle | Scale | Checks |
| --- | --- | --- |
| `tests/v30/v0.1` | 169k cases, 347 forms | arch final state, raw PSW, RAM diff, queue |
| `tests/v30/v0.2` | 347k | same |
| `tests/v30/v0.3` | ~3.7M, 370 forms | same; minus `known_divergences.json` VOIDs |
| `tests/v30/v20suite` | ~3M (real V20) | arch-only (queue masked), raw undefined flags + flags-mask DB |
| `f4a_boundary`/`mod3_illegal`/`f0lock_tranche` | 160/128/400 | EA wrap, LEA stale-EA confinement, BUSLOCK strio |
| `enter_nesting` | 512+154 digests | ENTER walk write streams |
| `fuzz_bank` mc1/mc2/t30-raw | ~5.6k banked seeds | multi-instruction: `chip_arch` real-silicon final regs + ordered write stream; image regenerated from `(cid,k,ov)` + sha |
| `fuzz_bank` t30-brkem | 167 seeds | opportunistic 8080-mode silicon validation |
| evt pseudo-forms (v0.1) | 19×200 | INT/NMI/POLL/HALT vectored (`_pushed_psw_flags`) |

Port: `sw/check_core.py::check_case` (sparse-delta regs, flags-mask, RAM diff,
queue, vectored PSW) + `dontcare_cells` + `emit_suite._flags_mask_of`. Decode
reference: `sw/optable.py::ilen` + `docs/facts/instructions.json`. Undefined
flags: `docs/facts/undefined_flags.md`. Fuzz replay:
`fuzz_campaign.derive_case/build` + `check_seq.compose` + `sw/testimage.py`
(OUT 0xFE register dump order, PSW at 0xFFEC, DONE 0xF00D at 0xFC).

## Simulator architecture (sim/, C++20, no deps, plain Makefile)

Modules: `ucrom` (ROM parse + `disasm` self-check byte-diffable vs V20UC.TXT),
`decode_tables` (pla_3 group decode: is_prefix/has_modrm/alu_class/uses_cl…),
`state` (regs, tmpa/b/c, OPR, IND, COUNT, PFXCNT, ALU latch, micro-PC, prefix
latches, ModRM operand bindings), `biu` (1MB epoch-stamped memory + IO,
functional queue, **ordered transaction log**, FLUSH/SUSP), `ea` (ModRM/EA,
default-segment rules), `loader` (prefix loop, ModRM+disp consumption, EA,
operand pre-read, entry-address formation `bank_of[page][byte][rowgrp]`),
`alu` (32 micro-ops incl. MUL/DIV *step* primitives for R-repeat loops,
ADJD/ADJA/ROL12/BIT/OPC; undefined-flag law hooks with `--no-flag-hooks`
diagnostic), `exec` (per-row interpreter: source/dest muxes, JMP conditions,
CTL dispatch, explicit F/Q interlock objects — instantly satisfied in
functional mode, preserved as call sites for the future timing mode), `json`
(mini reader/writer), `case_runner`, `main` (CLI: `run|disasm|trace`).

Key semantics (design bets, resolved empirically in S1): ALU op is *latched*;
SIGMA is the combinational result read as a source; `W` commits flags;
`R` repeats the latched op with COUNT (MUL/DIV/shift loops — the bet: measured
undefined-flag laws EMERGE from step semantics, hooks are the fallback);
CTL ext `[-06-]` = operand write-back strobe; FARJMP target = page 111,
opc = target5<<3. Micro-sequencing is never flattened into per-opcode C++.

CLI protocol: long-lived process, NDJSON over stdin/stdout (Python driver
gunzips); `--check` fast path with in-C++ comparison; `--emit-final`,
`--emit-txns` (ordered transaction log for write-stream diffs);
`v30sim trace` per-micro-row dump; micro-row **coverage counters** (executed
rows / 1028) for the sufficiency report. Target ≪100µs/case.

Python driver: `sw/ucsim_check.py` — loads suites, invokes sim, applies
check_case policy (flags masks, dont_care, vectored PSW), reports per-form.
`sw/ucsim_fuzz.py` — regenerates banked fuzz images, replays, compares
`chip_arch` + write stream via `fuzz_classify.extract_txns` conventions.

## Stages and gates

**S0 — Machine-readable assets + identification (no sim execution yet)**
- ROM parser; `disasm` output byte-identical to `docs/V20UC.TXT` (gate).
- pla_3 column naming: correlate the 14 outputs against predicates derived
  from `instructions.json`/`optable.py` (has_modrm, prefix, ALU class,
  uses-CL…); zero contradictions (gate). → `docs/facts/pla_model.md` with
  provenance.
- pla_2/pla4 identification attempts (pla_2 condition-PLA hypothesis has a
  concrete falsifier: evaluate candidate input wiring against Jcc truth
  tables + microcode JMP cond usage). Non-blocking.
- Start the **provenance ledger** `docs/notes/ucsim_provenance.md`: every
  simulator behavior tagged ROM / PLA / MEASURED-LAW(fact ref) / ASSUMPTION.
  This ledger IS the campaign's answer artifact.

**S1 — Core bring-up** (implementation order: json/ingestion → ucrom →
biu/state → decode_tables/ea/loader → alu/exec + MOV/ALU/PUSH/POP families →
flow/FLUSH + internal page (SHIFT/MUL/IMUL/IDIV/PUSHA/CALLF) → strings/REP →
F6-F7/FE-FF/0F pages → flag hooks). Bring-up oracle: per-opcode v0.2 files.
- Gate P1: bring-up families arch-exact on their v0.2 tranches; the ranked
  semantic unknowns (ALU latch timing, R-loop, `[-06-]`, loader entry
  contract, JMP cond encodings incl. `[-09-]` in IMUL, REP context, SR-blank
  default segment, F6/FE page disp handling) each resolved with a documented
  answer in the ledger. **Codex review of the resolved semantics** (per
  standing codex-phase-review convention).

**S2 — Golden gauntlet (single-instruction)**
- G-A: v0.1 169k arch-exact.
- G-B: v0.2 347k; v0.3 ~3.7M minus VOIDs (EDGE = cycle-only exclusions; arch
  must still pass).
- G-C: specials — f4a_boundary, mod3_illegal (LEA residue confinement),
  f0lock_tranche, enter_nesting walk streams, evt vectored forms.
- G-D: v20suite ~3M arch-only under metadata flag masks, PLUS the
  `--no-flag-hooks` audit: report how many undefined-flag bits emerge from
  microcode alone (headline sufficiency number).
- Discipline: **survey-then-fix** (run full batch, categorize ALL failures,
  then plan fixes — standing rule). Mismatch classification: ROM-misread /
  PLA-misID / hardware-model gap / suite artifact (VOID path).

**S3 — Sequence gauntlet (fuzz bank)**
- Implement testimage replay (reset → load stub → program → store stub).
- F-A: mc1 + mc2 + t30-raw banked seeds: `chip_arch` register-exact + ordered
  memory/IO write-stream match. (These include waits-varied captures; the
  FUNCTIONAL stream must be wait-invariant — any wait-dependence found is a
  discovery, not a sim bug, and routes to the ledger.)
- F-B (report, not gate): t30-brkem — 8080-mode pages against silicon.
- F-C (report, not gate): interrupt/vectored evt forms end-to-end.

**S4 — Sufficiency verdict + closure**
- Micro-row coverage report: rows never executed by any green gate = untested
  ROM claims; enumerate.
- Final provenance ledger: the list of ASSUMPTIONS that remained necessary =
  precisely "what the microcode information does NOT determine". This answers
  the campaign question either way.
- Codex final review; ROADMAP amendment; campaign note in docs/notes/.

**Victory** = S2 (G-A..G-D) + S3 (F-A) green, every residual mismatch either
fixed or documented as a suite artifact under the known-divergences
discipline, and the sufficiency ledger published.

## Mechanics

- **Execution mode (user directive 2026-08-01): auto mode. Implementation work
  runs on Opus subagents; the Fable session agent coordinates, keeps the
  pipeline fed, and REVIEWS each subagent's work product after every task
  completion before the next task launches.** Stage gates remain
  coordinator-verified; STOP verdicts go to the user.
- New branch `ucsim` off master (biu-rebuild stays paused). Single-writer rule
  applies (one subagent owns the tree at a time). **No board access needed
  anywhere in this campaign** — fully offline; board stays idle.
- New files: `sim/` (modules above), `sw/ucsim_check.py`, `sw/ucsim_fuzz.py`,
  `docs/facts/pla_model.md`, `docs/notes/ucsim_provenance.md`; ROADMAP.md
  amendment. No changes to hdl/ or existing sw/ tools.

## Verification

- S0: `sim/v30sim disasm | diff - docs/V20UC.TXT` → empty; pla_3 predicate
  cross-check script output 0 contradictions.
- S1+: `python3 sw/ucsim_check.py --suite tests/v30/v0.2 --forms <family>` per
  bring-up family; then full-suite runs for G-A..G-D (v0.3 and v20suite are
  the long runs — minutes at the perf target, all offline).
- S3: `python3 sw/ucsim_fuzz.py --bank mc1` etc.; image sha verified against
  `image_sha256` before every replay (GEN-DRIFT hard fail, standing rule).
- Continuous: `--no-flag-hooks` delta tracked per gate; micro-row coverage
  accumulated across all green gates.