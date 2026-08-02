# v30sim

C++20 microcode-driven simulator for the NEC V30 (uPD70116). Every instruction
is executed by walking the rows of `docs/V20BITS.TXT`; nothing is flattened
into per-opcode C++. It implements the native pages AND the 8080 emulation
pages (`110`/`101`, entered by `BRKEM`/`MFC`, left by `RETEM`/`ENDEM` and by
every interrupt's `MFS`). As of stage S2a it is architecturally exact on **all 347
forms** of both `tests/v30/v0.1` (169 000 / 169 000) and `tests/v30/v0.2`
(347 000 / 347 000), including the eleven pin-event pseudo-forms
(`INT.*` / `NMI.*` / `HLT.*`), plus the wait tranches and the specials
(`f4a_boundary`, `mod3_illegal`, `f0lock_tranche`, `enter_nesting`).

No external dependencies; plain `make` and a C++20 compiler.

## What exists

| file | contents |
| --- | --- |
| `ucrom.h` / `ucrom.cpp` | `MicroOp`, `MatchPat`, `UcRom` loader for `docs/V20BITS.TXT`, field-name tables, and the precomputed `bank_of[page][opcode][row]` micro-address decode with `fetch(page, opc, row)` |
| `disasm.h` / `disasm.cpp` | disassembly printer (`PrintOpcode` / `PrintInstrs` / `RangeStr` transliteration) |
| `pla3_table.h` | generated pla_3 group-decode tables (`docs/facts/pla_model.md`) |
| `state.h` | machine state as the microcode sees it: regs, tmps, OPR/IND/COUNT, the latched ALU, the micro-PC |
| `biu.h` / `biu.cpp` | 1 MB epoch-stamped memory + I/O, functional queue, ordered write log |
| `ea.h` / `ea.cpp`, `loader.h` / `loader.cpp` | ModR/M + EA, the pre-decode contract (prefixes, operand binding, pre-read, page select) |
| `alu.h` / `alu.cpp` | the micro-ALU: combinational `alu_eval` and the per-iteration `alu_step` |
| `exec.h` / `exec.cpp` | the per-micro-row interpreter, incl. the hardware interrupt/NMI/trap entries (`Cpu::interrupt`) and the INTA bus cycle |
| `case_runner.h` / `case_runner.cpp` | SingleStepTests ingestion and verdicts |
| `image_runner.h` / `image_runner.cpp` | whole-IMAGE replay (`v30sim image`): 64K-mirrored memory, the ROM's own RESET sequence, multi-instruction execution to the harness done marker, ordered bus stream out. Drives the S3 fuzz-bank sequence gauntlet (`sw/ucsim_fuzz.py`) |
| `main.cpp` | CLI dispatcher (`disasm`, `info`, `run`, `image`, `trace`) |

Provenance for every semantic decision: `docs/notes/ucsim_provenance.md`.

## Normative sources

* `docs/V20BITS.TXT` — raw microcode ROM dump: header line, then 1028 rows of
  29 bits. Every 4th row carries a 15-character activation pattern in columns
  31..45 encoding a 13-bit mask/compare micro-address match.
* `docs/V20UCDIS.PAS` — Turbo Pascal disassembler; the normative encoding spec
  for every field position and printing rule. `docs/HEXRANGE.PAS` supplies the
  opcode-range renderer.
* `docs/V20UC.TXT` — golden output (CRLF line endings).

## Micro-address layout

13 bits: `[12:10]` page, `[9:2]` opcode byte, `[1:0]` row within the 4-row bank.
Pages are `0 = norep, 1 = rep, 2 = F6/F7, 3 = FE/FF, 4 = 0F, 5 = 8080/ED,
6 = 8080, 7 = internal` (microcode-internal entry points / far-jump targets).

## Build and gate

```sh
cd sim
make            # builds ./v30sim
make test       # the gate
```

The gate is:

```sh
sim/v30sim disasm docs/V20BITS.TXT | diff - docs/V20UC.TXT
```

It must produce no output; the streams are byte-identical, CRLF included.

`v30sim info docs/V20BITS.TXT` prints row/pattern counts and micro-address
coverage.

## Running cases

```sh
gunzip -c tests/v30/v0.2/0F28.json.gz | sim/v30sim run docs/V20BITS.TXT
python3 sw/ucsim_smoke.py --suite tests/v30/v0.2 --all      # bring-up survey
sim/v30sim trace docs/V20BITS.TXT <idx>                     # per-micro-row dump
```

The PRODUCTION checker is `sw/ucsim_check.py` (`run --emit-final` + the
`sw/check_core.py::check_case` architectural policy: flags masks, don't-cares,
pushed-PSW derivation for pin events, RAM fallback, 64K-mirror retry):

```sh
python3 sw/ucsim_check.py --suite tests/v30/v0.1 --report ga.json   # G-A
python3 sw/ucsim_check.py --suite tests/v30/v0.1-w1                 # waits
python3 sw/ucsim_check.py --suite tests/v30/f4a_boundary            # G-C
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --forms goldens \
        --residue stale-ea
python3 sw/ucsim_check.py --suite tests/v30/f0lock_tranche
python3 sw/ucsim_check.py --enter-nesting
```

`run --alu-hw-report` adds one summary record attributing each case's FINAL PSW
bits to the three flag behaviours that are NOT emergent from the microcode (the
per-step shift/rotate V law, the logic ops' `AC = 0`, and the fitted BCD
correction). `sw/ucsim_smoke.py --alu-hw` aggregates it across a suite; see
`docs/notes/ucsim_provenance.md` §31 for the P1 numbers.
