# v30sim

C++20 microcode-driven simulator for the NEC V30 (uPD70116). Every instruction
is executed by walking the rows of `docs/V20BITS.TXT`; nothing is flattened
into per-opcode C++. As of stage S1c it is architecturally exact on all 336
sim-scope forms of `tests/v30/v0.2` (336 000 / 347 000 cases; the remaining 11
files are pin-event pseudo-forms, S2 scope).

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
| `exec.h` / `exec.cpp` | the per-micro-row interpreter |
| `case_runner.h` / `case_runner.cpp` | SingleStepTests ingestion and verdicts |
| `main.cpp` | CLI dispatcher (`disasm`, `info`, `run`, `trace`) |

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
python3 sw/ucsim_smoke.py --suite tests/v30/v0.2 --all      # whole-suite survey
python3 sw/ucsim_smoke.py --suite tests/v30/v0.2 --s1c      # the 0F page
sim/v30sim trace docs/V20BITS.TXT <idx>                     # per-micro-row dump
```

`run --alu-hw-report` adds one summary record attributing each case's FINAL PSW
bits to the three flag behaviours that are NOT emergent from the microcode (the
per-step shift/rotate V law, the logic ops' `AC = 0`, and the fitted BCD
correction). `sw/ucsim_smoke.py --alu-hw` aggregates it across a suite; see
`docs/notes/ucsim_provenance.md` §31 for the P1 numbers.
