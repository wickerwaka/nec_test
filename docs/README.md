# docs/ — V30 knowledge base

Layout (see the project plan for rationale):

- `raw/` — original documents (PDF scans). Do not edit.
- `converted/` — machine-readable conversions of `raw/` (pdftotext output). Table OCR is
  imperfect; always verify numeric tables against the scan (page numbers below are PDF pages).
- `facts/` — structured, extracted facts. **Every fact carries provenance** (source + page or
  experiment ID). This is what discovery agents consume and extend.
  - `OPEN_QUESTIONS.md` — living list of unknowns; retire entries into fact files as they resolve.
  - `pins_timing.md` — DC/AC electrical and timing facts for μPD70116.
  - `mnemonic_map.json` — NEC↔Intel register/mnemonic mapping.
  - `instructions.json` — (planned) per-opcode encoding/timing/flags database.
- `notes/` — summaries of mined external resources (SingleStepTests V20, arduinoX86, MAME necv).

## Document inventory

| File (raw/) | What it is | Key sections (PDF pages) |
|---|---|---|
| `1991_16_bit_V-Series_Microprocessor_Data_Book.pdf` | NEC data book, 1107 pp | μPD70116/70116H datasheet: p94–125 (AC tables p101–102, waveforms p103–104) |
| `V20_V30_Users_Manual_Oct86.pdf` | V20/V30 User's Manual, 228 pp | Instruction set with encodings + clock counts: Section 12, p46–225 |
| `U11301EJ5V0UM00_16-BIT_V_Series_Jun97.pdf` | Later 16-bit V-series User's Manual, 220 pp | Architecture/instruction reference (1997 revision) |
| `9800722-03_The_8086_Family_Users_Manual_Oct79.pdf` | Intel 8086 Family User's Manual, 748 pp | Max-mode bus protocol, 8288 decoding, queue-status semantics |

Sources: bitsavers.org (`components/nec/V-Series/`, `components/nec/_dataBooks/`, `components/intel/8086/`), fetched 2026-07-10.
