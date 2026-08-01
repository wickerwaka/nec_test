# v30sim

C++20 simulator skeleton for the NEC V30 (uPD70116). Stage S0a: microcode ROM
parser plus a `disasm` subcommand that reproduces the reference disassembly
byte-for-byte.

No external dependencies; plain `make` and a C++20 compiler.

## What exists

| file | contents |
| --- | --- |
| `ucrom.h` / `ucrom.cpp` | `MicroOp`, `MatchPat`, `UcRom` loader for `docs/V20BITS.TXT`, field-name tables, and the precomputed `bank_of[page][opcode][row]` micro-address decode with `fetch(page, opc, row)` |
| `disasm.h` / `disasm.cpp` | disassembly printer (`PrintOpcode` / `PrintInstrs` / `RangeStr` transliteration) |
| `main.cpp` | CLI dispatcher (`disasm`, `info`; `run` and `trace` to follow) |

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
