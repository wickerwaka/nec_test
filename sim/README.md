# v30sim

C++20 microcode-driven simulator for the NEC V30 (uPD70116). Every instruction
is executed by walking the rows of `docs/V20BITS.TXT`; nothing is flattened
into per-opcode C++. It implements the native pages AND the 8080 emulation
pages (`110`/`101`, entered by `BRKEM`/`MFC`, left by `RETEM`/`ENDEM` and by
every interrupt's `MFS`).

As of the campaign close (S4, 2026-08-01) it is **architecturally exact** on
7.34 M single-instruction captures across two parts — `v0.1` (169 000),
`v0.2` (347 000), `v0.3` (3 699 998) and the real-µPD70108 `v20suite`
(3 125 000), the last two **also with every flags-mask disabled** — on the
specials (`f4a_boundary`, `mod3_illegal`, `f0lock_tranche`, `enter_nesting`)
and the eleven pin-event pseudo-forms, and on **2 125 / 2 125** of the banked
fuzz seeds whose capture recorded a complete architectural dump (register-,
PSW- and ordered-write-stream exact). Micro-row coverage **912 / 1028**.

No external dependencies; plain `make` and a C++20 compiler. Timing is **not**
modelled — see "What is deliberately not modelled" below.

* Verdict / sufficiency answer: `docs/notes/ucsim_campaign_verdict_2026-08-01.md`
* Provenance for every semantic decision: `docs/notes/ucsim_provenance.md`
* Micro-row coverage report: `sim/coverage_report.txt`

## What exists

| file | contents |
| --- | --- |
| `ucrom.h` / `ucrom.cpp` | `MicroOp`, `MatchPat`, `UcRom` loader for `docs/V20BITS.TXT`, field-name tables, and the precomputed `bank_of[page][opcode][row]` micro-address decode with `fetch(page, opc, row)` |
| `disasm.h` / `disasm.cpp` | disassembly printer (`PrintOpcode` / `PrintInstrs` / `RangeStr` transliteration) |
| `pla3_table.h` | generated pla_3 group-decode tables (`docs/facts/pla_model.md`) |
| `state.h` | machine state as the microcode sees it: regs, tmps, OPR/IND/COUNT, the latched ALU, the micro-PC |
| `biu.h` / `biu.cpp` | 1 MB epoch-stamped memory + I/O, functional queue, ordered transaction log. Every access completes instantly; the `F`/`Q` interlock CALL SITES live in `exec.cpp` and are preserved for a future cycle-accurate mode |
| `ea.h` / `ea.cpp`, `loader.h` / `loader.cpp` | ModR/M + EA, the pre-decode contract (prefixes, operand binding, pre-read, page select) |
| `alu.h` / `alu.cpp` | the micro-ALU: combinational `alu_eval` and the per-iteration `alu_step` |
| `exec_impl.h` | the per-micro-row interpreter as `template <class Bus> class CpuT`, incl. the hardware interrupt/NMI/trap entries (`interrupt`), the INTA bus cycle and the 8080 mode flag. `loader_impl.h` is the same treatment for the pre-decode hardware. Bus-policy split, ucsim-t T0 |
| `exec.h` / `exec.cpp` | the FUNCTIONAL instantiation: `using Cpu = CpuT<Biu>`, one out-of-line copy, `extern template` so no other TU instantiates it |
| `exec_timed.h` / `exec_timed.cpp` | the TIMED instantiation: `using CpuTimed = CpuT<BiuTimed>` |
| `biu_timed.h` / `biu_timed.cpp` | the TIMED bus: same Bus concept as `Biu`, owns a CPU clock, emits one row per clock. T0 = naive scaffolding (serial bus, demand-filled queue, no scheduler) |
| `rows.h` / `rows.cpp` | `ClockRow` + the two emitters: `check_core.py::parse_out` text and chip_rows NDJSON |
| `timed_runner.h` / `timed_runner.cpp` | `timed-run`: cases in, per-clock row streams + final regs out |
| `case_runner.h` / `case_runner.cpp` | SingleStepTests ingestion and verdicts |
| `image_runner.h` / `image_runner.cpp` | whole-IMAGE replay (`v30sim image`): 64K-mirrored memory, the ROM's own RESET sequence, multi-instruction execution to the harness done marker, ordered bus stream out. Drives the S3 fuzz-bank sequence gauntlet (`sw/ucsim_fuzz.py`) |
| `main.cpp` | CLI dispatcher (`disasm`, `info`, `run`, `image`, `trace`, `timed-run`) |

## Normative sources

* `docs/V20BITS.TXT` — raw microcode ROM dump: header line, then 1028 rows of
  29 bits. Every 4th row carries a 15-character activation pattern in columns
  31..45 encoding a 13-bit mask/compare micro-address match.
* `docs/V20UCDIS.PAS` — Turbo Pascal disassembler; the normative encoding spec
  for every field position and printing rule. `docs/HEXRANGE.PAS` supplies the
  opcode-range renderer.
* `docs/V20UC.TXT` — golden output (CRLF line endings).
* `docs/pla_3.txt` + `pla3_outputs.txt`, `docs/pla_2.txt`, `docs/pla4.txt` —
  PLA dumps; identification and status in `docs/facts/pla_model.md`.

## Micro-address layout

13 bits: `[12:10]` page, `[9:2]` opcode byte, `[1:0]` row within the 4-row bank.
Pages are `0 = norep, 1 = rep, 2 = F6/F7, 3 = FE/FF, 4 = 0F, 5 = 8080/ED,
6 = 8080, 7 = internal` (microcode-internal entry points / far-jump targets).

## CLI

```
v30sim disasm <romfile>                 microcode disassembly (V20UC.TXT format)
v30sim info   <romfile>                 row/pattern counts, micro-address coverage
v30sim run    <romfile> [--queue] [--emit-final] [--mirror]
                        [--alu-hw-report] [--coverage] [--wrap-scan]
                        [--report=N]    run SingleStepTests cases from stdin
v30sim image  <romfile> [--coverage] [--trace[=idx]]
                                        replay 64 KB test IMAGES from stdin
v30sim trace  <romfile> <idx>           per-micro-row dump of one case
v30sim timed-run <romfile> [--waits N] [--ndjson] [--mirror]
                        [--case=IDX] [--steps=N]
                                        TIMED mode: one record per CPU clock
```

Both `run` and `image` speak NDJSON on stdin/stdout and are long-lived, so the
Python drivers stream whole suites through one process.

## Timed mode (campaign `ucsim-t`)

The simulator has two bus policies behind one interpreter.  `sim/biu.{h,cpp}`
is functional (every access completes instantly) and `sim/biu_timed.{h,cpp}`
models a CPU clock and emits one row per clock; the micro-sequencing code is
literally the same template in both cases, so the architectural answer cannot
drift between them.

`timed-run` emits the RAW per-clock pin records that `sw/check_core.py`'s
`parse_out` / `build_rows_sim` already read — the same textual format
`hdl/tb/tb_v30_core.sv` writes — so the golden 11-column `cycles` rows are
synthesized by the UNMODIFIED python comparator rather than by new C++.
`--ndjson` switches to the chip_rows record shape `sw/check_seq.py` consumes.

```sh
python3 sw/timed_gate.py --suite tests/v30/v0.2 --forms 88,00,50,C8
python3 sw/timed_gate.py --sbs B8:0        # golden vs sim rows, side by side
```

The status column follows the v0.1 README's column-7 semantics (the V30 drives
the NEXT cycle's status during T4) — modelled as a registered output driven one
clock early, not as a T4 special case, because the goldens show an idle Ti row
carrying it too.

**At T0 the rows are NOT yet timing-exact**: the timed bus is deliberate
scaffolding (strictly serial, no prefetch scheduler, no queue latency, no
micro-row cadence, uniform waits only).  Every simplification, the laws that
ARE modelled, and the stage that replaces each one are enumerated in
`docs/notes/ucsim_t_provenance.md`.

## Build and the standing gates

```sh
make -C sim            # builds sim/v30sim
make -C sim test       # GATE 1: the disasm gate
python3 sw/pla3_check.py   # GATE 2: PLA identification, exit 0 / 21 checks
```

The disasm gate is `sim/v30sim disasm docs/V20BITS.TXT | diff - docs/V20UC.TXT`
and must produce no output — the streams are byte-identical, CRLF included.

## Running the suites

`sw/ucsim_check.py` is the PRODUCTION checker (`run --emit-final` plus the
`sw/check_core.py::check_case` architectural policy: metadata flags masks,
`dont_care` cells, pushed-PSW derivation for pin events, RAM reconstruction with
fallback, `known_divergences` by CLASS (VOID excluded / EDGE kept), the `iords`
sidecar and the flat-fail → 64K-mirror retry).

```sh
# G-A  169 000 cases
python3 sw/ucsim_check.py --suite tests/v30/v0.1 --report ga.json
python3 sw/ucsim_check.py --suite tests/v30/v0.1-w1     # wait tranches
python3 sw/ucsim_check.py --suite tests/v30/v0.1-w3
python3 sw/ucsim_check.py --suite tests/v30/v0.2

# G-B  3.7 M cases  (~9 min)
python3 sw/ucsim_check.py --suite tests/v30/v0.3

# G-D  3.125 M cases of real uPD70108 silicon  (~6 min)
#      --no-mirror: that rig is not the 64K-mirrored capture board
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror

# G-C  the specials
python3 sw/ucsim_check.py --suite tests/v30/f4a_boundary
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --forms goldens \
        --residue stale-ea
python3 sw/ucsim_check.py --suite tests/v30/f0lock_tranche
python3 sw/ucsim_check.py --enter-nesting

# the headline rollups
python3 sw/ucsim_check.py --suite tests/v30/v0.3 --raw-flags   # every mask off
python3 sw/ucsim_check.py --suite tests/v30/v0.2 --alu-hw      # PSW attribution
```

Useful flags: `--forms 88,89,...` / `--cases N` to narrow a run, `--subset
subset.json` to run a named case list, `--details N` for per-failure dumps,
`--wrap-scan out.json` for the A12 segment-boundary EXTRACTION pass (writes the
subset, performs no comparison).

`sw/ucsim_smoke.py` is the lighter bring-up survey (`--suite ... --all`,
`--s1b`, `--alu-hw`).

## The fuzz replay (S3 sequence gauntlet)

`sw/ucsim_fuzz.py` regenerates each banked seed's 64 KB image from `(cid, k,
ov)` with the SAME generator the capture used, **verifies `image_sha256` before
every replay** (a mismatch is GEN-DRIFT and a hard failure), runs it through
`v30sim image` from RESET release, and compares the ordered functional bus
stream plus `chip_arch` against the socket capture.

```sh
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw      # F-A, ~22 s, 16 workers
python3 sw/ucsim_fuzz.py --bank t30-brkem            # F-B, the 8080 report
python3 sw/ucsim_fuzz.py --bank mc1 --k 1447 --details 20   # one seed
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw --census    # executed-prefix census
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw --stat-clobber  # the sec.60 falsifier
```

Wait axes are timing-only: the functional stream must be wait-INVARIANT, so a
seed whose architectural outcome depends on its wait axis is a FINDING, not a
simulator bug — the rollup prints the per-wait-class census so a collapse in
one class cannot hide.

## Micro-row coverage

```sh
python3 sw/ucsim_check.py --suite tests/v30/v0.1 --coverage cov.json   # accumulates
python3 sw/ucsim_fuzz.py  --bank mc1,mc2,t30-raw,t30-brkem --coverage fz.json
python3 sw/ucsim_check.py --coverage-report cov.json                   # names dead rows
python3 sw/ucsim_coverage_report.py cov.json fz.json  # -> sim/coverage_report.txt
```

`--coverage` on `ucsim_check.py` ACCUMULATES into the file, so the counter is
the union over every gate; `ucsim_fuzz.py --coverage` writes a bare 1028-entry
list. `sw/ucsim_coverage_report.py` merges the two and classifies every row no
gate executed (its docstring lists the full gate sequence); the committed
result is `sim/coverage_report.txt` — **912 / 1028 executed**, of the 116
unexecuted rows **9 substantive** (the POLL tail behind `JMP BUSY`, and bank A
of the one ambiguous micro-address), 14 post-`FARJMP` and 93 bank tails.

## What is deliberately not modelled

Four numbered policies, each with the timing mechanism that would replace it
(`docs/notes/ucsim_provenance.md` §38, §57, and the verdict's §(d)):

* **cycle timing / prefetch.** The model fetches a byte when the decoder asks
  for it and keeps no speculative queue, so `final.queue` is not compared; the
  consumed-instruction-byte count stands in for it and is asserted on every
  case.
* **I/O port values** are REPLAYED from the capture (case name `iord=XXXX`, an
  `iords/` sidecar, or the case's own bus trace), never predicted.
* **the interrupt firing boundary** is replayed — single-instruction cases from
  the golden's pushed frame, sequence cases from two coordinates (bus position
  AND the recorded resume `CS:IP`). Every *consequence* — acknowledge, vector
  fetch, frame, resume PC, `CW`/`IY` at a REP abort, flush, mode flag — is
  computed from the ROM and diffed.
* **`BUSY`** is hard-FALSE (no pin model), which is why the five POLL busy-loop
  rows are unreached.

The first of those four is what the `ucsim-t` campaign is removing; see
"Timed mode" above and `docs/notes/ucsim_t_provenance.md`.
