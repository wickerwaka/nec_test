# V20/V30 on-die PLA model

Functional identification of the NEC µPD70108/70116 (V20/V30) programmable-logic
arrays whose dumps live in `docs/`.  Everything asserted here is re-derived from
the dumps by the standing gate `python3 sw/pla3_check.py` (exit 0 required).

## Provenance

| Asset | What it is |
|---|---|
| `docs/pla_1.jpg` … `docs/pla_5.jpg` | die photographs of five PLA structures (the die carries nine in total, incl. the microcode ROM) |
| `docs/pla_2.txt` | transcription of `pla_2.jpg` — 26 product terms, 12-bit inputs, no output columns |
| `docs/pla_3.txt` | transcription of `pla_3.jpg` — 59 product terms, 2-bit mode + 8-bit opcode inputs, 14-bit outputs, with hand annotations |
| `docs/pla3_outputs.txt` | `pla_3` expanded per opcode: 3 sections × 256 output vectors |
| `docs/pla4.txt` | transcription of `pla_4.jpg` — ~45 terms, 12-bit inputs, ragged output columns |
| `docs/V20BITS.TXT`, `docs/V20UC.TXT`, `docs/V20UCDIS.PAS` | the microcode ROM (the ninth PLA structure) and its disassembler |

- Dumps entered this repository in commit `e9cef4536c` ("ucsim: commit microcode
  ROM + PLA dump assets"), 2026-08-01.  They are third-party die transcriptions;
  **the upstream author/URL is not recorded in-repo — OPEN provenance item.**
- Die-level context: <https://dev-zzo.github.io/blarg/2025/10/06/nec-v20-pla.html>
  (2025-10-06).  That article is an *electrical* analysis only: it reports nine
  PLA structures on the die including microcode storage, mostly dynamic CMOS
  sum-of-products with pre-charge transistors plus one static variant.  It
  assigns no functional meaning to any of them and publishes no dimension table.
- Functional cross-reference for `pla_3`'s column semantics: Ken Shirriff,
  "The Group Decode ROM in the Intel 8086", <https://www.righto.com/2023/05/8086-processor-group-decode-rom.html>.
  The 8086's Group Decode ROM has 15 outputs; ten of `pla_3`'s fourteen columns
  are recognisably the same signals.  The 8086 table is used as a *hypothesis
  source only* — every V20 column below is proven against V20 metadata
  (`docs/facts/instructions.json`, `sw/optable.py`), not asserted by analogy.
- Instruction metadata authorities used by the gate: `docs/facts/instructions.json`
  (288 forms, encoding bit-strings transcribed from the User's Manual) and
  `sw/optable.py` / `sw/fuzz_cov.py` (ModR/M, group and 0F-page sets).

---

## `pla_3` — per-opcode GROUP-DECODE PLA — **IDENTIFIED**

### Structure (proven)

The 59 product terms are matched against a **2-bit decode-mode prefix followed by
the 8 opcode bits**, and produce a 14-bit output vector.  OR-ing the terms
reproduces all **768** dumped output vectors bit-exactly (check A of the gate),
which fixes the prefix as a mode select:

| prefix | section in `pla3_outputs.txt` | meaning |
|---|---|---|
| `01` | `native opcodes` | native V20/V30 first opcode byte |
| `00` | `8080 opcodes` | 8080 emulation mode (entered by `BRKEM`) |
| `11` | `ext opcodes` | second byte of the `0F` extension page |
| `10` | — | unused; no product term matches it |

The three modes agree with the microcode ROM's own page numbering
(`sim/ucrom.h`: page 4 = `0F`, pages 5/6 = 8080/ED, …), which is independent
corroboration that the prefix is the decode mode and not, say, two more opcode bits.

Output bits are printed MSB-first as **b0 … b13**.  In `sim/pla3_table.h` b0 is
stored at bit 13, so that `XOP[3:0]` (b10..b13) lands in the low nibble.

### The 14 columns

Every column below is checked for **exact** set equality against a predicate
computed from independent metadata; the "exceptions" column lists every opcode
that deviates, with its cause.  All exceptions are *extra* assertions caused by
PLA product-term merging (a shared term whose extra members treat the output as a
don't-care) — there are **no** missing assertions anywhere.

| bit | name | native predicate | # ops | exceptions (all extra) | 8086 GDR analogue |
|---|---|---|---|---|---|
| b0 | `BYTE_ONLY` | byte-width-only data op with no W bit: category `BCD ADJUST` (27/2F/37/3F) ∪ `CVTBD`,`CVTDB`,`TRANS` (D4/D5/D7) ∪ `MOV reg8,imm8` (B0–B7) | 16 | `D6` — undocumented SALC, shares the `110101??` term | Out12 byte-only |
| b1 | `W_FROM_BIT0` | first-byte encoding has `W` in bit 0 | 102 | `E0`,`E1` — LOOPNE/LOOPE, share term `11?0000?` with C0/C1 | Out11 byte/word |
| b2 | `ONE_BYTE_LOGIC` | prefix (26/2E/36/3E/64/65/F0/F2/F3, plus the `0F` page prefix) ∪ flag set/clear (F8–FD, F5) ∪ HALT (F4) | 19 | `F1` — decoded as a **BUSLOCK-alias prefix** | Out10 "1BL" |
| b3 | `ACC_W_OPERAND` | implicit AL/AW operand whose width is the W bit (ALU acc,imm; MOV acc,dmem; TEST acc,imm; STM/LDM/CMPM; IN/OUT) | 40 | `A4`–`A7` (MOVBK/CMPBK) — block term `1010????` | Out7 AL/AX register |
| b4 | `SREG_MOV` | documented `sreg` MOV forms = 8C, 8E | 2 | — | Out8 segment register |
| b5 | `HAS_MODRM` | `sw/optable.py` ModR/M set | 76 | `63` — **the PLA gives 0x63 a ModR/M byte** (term `01100?1?` = 62/63/66/67) | Out4 "2BR" |
| b6 | `MODRM_STORE` | ModR/M op whose r/m operand is *written without being read*: 88, 89, 8C, 8F, C6, C7 | 7 | `8D` (LDEA/LEA — no memory access at all), shares term `100011?1` with 8F | Out1 read-modify-write, inverted sense |
| b7 | `DIR_FROM_BIT1` | opcode bit 1 is the direction bit: `op` and `op^2` share a mnemonic root, both carry ModR/M, operand lists are exact reverses (ALU rm,r/r,rm ×8, MOV 88–8B, MOV sreg 8C/8E) | 42 | `C0`,`C1`,`E0`,`E1` — term `11?0000?` | Out9 direction bit |
| b8 | `NATIVE_HI` | native ∧ opcode ≥ 0x80 (single term `01 1???????`) | 128 | — | *(no 8086 analogue)* |
| b9 | `INCDEC_NO_CY` | INC/DEC r16 (40–4F) ∪ the groups that contain INC/DEC (FE/FF) | 20 | `F6`,`F7` — term `1111?11?` covers F6/F7/FE/FF | Out14 carry update |
| b10–b13 | `XOP[3:0]` | 4-bit encoded auxiliary-operation field — see below | — | — | merges Out0/Out2/Out3/Out5/Out6/Out13 |

`b8` deserves a note: it is exactly "native opcode with bit 7 set", asserted by a
single product term, and it is *not* a pass-through of an opcode wire — the 8080
and 0F sections never assert it even for opcodes ≥ 0x80.  Best reading is a
map-half select for downstream address generation.  Marked **IDENTIFIED (set),
HYPOTHESIS (purpose)**.

`b6`'s naming is the least certain of the ten single-bit columns: the opcode set
is unambiguous, but the 8086's corresponding signal is documented with the
opposite sense (read-modify-write), and the 0F-page members (ROL4/ROR4, INS/EXT)
do read their operand.  The safe reading, and the one the simulator should use,
is "the standard operand-fetch step is skipped; the instruction's own microcode
performs whatever access it needs".  Confidence: **medium**.

### `XOP[3:0]` (b10..b13) — a 4-bit encoded field, not four independent bits

When `ONE_BYTE_LOGIC` (b2) is set the field is a **complete 16-entry hardware-op
table**.  All 16 values are used, and the six operations that exist in *both* the
native and the 8080 sections carry **identical** field values — an independent
confirmation that this is one encoded field and not a coincidence:

| XOP | operation | native | 8080 |
|---|---|---|---|
| `0000` | segment-override prefix | 26, 2E, 36, 3E | — |
| `0001` | extension-page prefix | `0F` | `ED` |
| `0010` | SET1 DIR (STD) | FD | — |
| `0011` | CLR1 DIR (CLD) | FC | — |
| `0100` | EI / STI | FB | FB |
| `0101` | DI / CLI | FA | F3 |
| `0110` | SET1 CY (STC) | F9 | 37 |
| `0111` | CLR1 CY (CLC) | F8 | — |
| `1000` | REPC prefix | 65 | — |
| `1001` | REPNC prefix | 64 | — |
| `1010` | NOT1 CY (CMC) | F5 | 3F |
| `1011` | HALT | F4 | 76 |
| `1100` | REP / REPE prefix | F3 | — |
| `1101` | REPNE prefix | F2 | — |
| `1110` | BUSLOCK alias (undocumented `F1`) | F1 | — |
| `1111` | BUSLOCK | F0 | — |

Note the internal regularity: within F8–FD, b11/b12 select the flag
(CY / IE / DIR) and b13 selects clear(1) vs set(0) — the field is literally the
inverted low opcode bits for that block, which is what a minimised PLA produces.

When `ONE_BYTE_LOGIC` is clear the same four wires carry a different, so-far
**HYPOTHESIS**-grade encoding (an auxiliary EU/ALU operation select).  The class
table below reconstructs all 256 native `XOP` values exactly (gate check C):

| XOP | proposed meaning | native opcodes | corroboration in another mode |
|---|---|---|---|
| `0000` | none | everything not listed | — |
| `0001` | segment-register operand | 07, 17, 1F (POP sreg), 8C, 8E | — |
| `0011` | bit-field operation | — | `0F 30–3F` (INS/EXT) |
| `0100` | multiply / ALU-immediate group | 69, 6B (MUL imm), 80–87 | — |
| `0110` | block I/O | 6C–6F (INM/OUTM) | — |
| `1010` | decimal adjust | 27, 2F, 37, 3F | 8080 `27` (DAA); `0F 20–27` (ADD4S/SUB4S/CMP4S) |
| `1011` | second-byte group dispatch | F6, F7, FE, FF | — |
| `1100` | increment / decrement | 40–4F | 8080 `04/05/0C/0D/…/3C/3D` (INR/DCR) |
| `1101` | 16-bit add | — | 8080 `09/19/29/39` (DAD) |
| `1110` | count / compare-and-loop | A6, A7, AE, AF (CMPBK/CMPM), C0, C1, E0, E1 | — |
| `1111` | port I/O | E4–E7, EC–EF | 8080 `D3` (OUT), `DB` (IN) |

The three cross-mode agreements (`1010` decimal adjust, `1100` inc/dec, `1111`
port I/O all reproduced independently in the 8080 map) are what lifts this from
"a table of observed values" to a plausible shared encoding.  It is still a
hypothesis: the consumers of these four wires are not traced.

### 8080-emulation section (prefix `00`)

Same columns, and they behave consistently:

- `BYTE_ONLY` (b0) is asserted for 173 of 256 opcodes — the 8080 is an 8-bit
  machine.  The 83 non-asserting opcodes are the register-pair/16-bit ops
  (LXI, INX, DCX, DAD, SHLD/LHLD), the whole control-flow and stack half
  (`C0–FF`, except its immediate-ALU column `C6/CE/D6/DE/E6/EE/F6/FE`), the
  logic-executed ops (`37`, `3F`), and the undefined slots.
- `ONE_BYTE_LOGIC` (b2) = {`37` STC, `3F` CMC, `76` HLT, `ED` extension prefix,
  `F3` DI, `FB` EI} — exactly the 8080's logic-executed one-byte instructions.
- `HAS_MODRM` (b5) is asserted for the 144 opcodes that carry a 3-bit register
  field (`INR/DCR r`, `MOV r,r` 40–BF, `ALU A,r`), i.e. the column generalises to
  "an operand-register field is present", with ModR/M being the native-mode form.
- `W_FROM_BIT0`, `ACC_W_OPERAND`, `SREG_MOV`, `MODRM_STORE`, `NATIVE_HI`,
  `INCDEC_NO_CY` are never asserted in 8080 mode.

### `0F` extension page (prefix `11`)

The page **decodes at block granularity** — the low bits inside a block are
ignored, so undocumented aliases share the documented decode:

| block | documented forms | PLA decode |
|---|---|---|
| `0F 10–1F` | TEST1/CLR1/SET1/NOT1, reg/imm variants | `HAS_MODRM`, `W_FROM_BIT0` |
| `0F 20–27` | ADD4S (20), SUB4S (22), CMP4S (26) | `BYTE_ONLY`, `XOP=1010` (decimal adjust); **no** ModR/M |
| `0F 28–2F` | ROL4 (28), ROR4 (2A) | `HAS_MODRM`, `W_FROM_BIT0`, `MODRM_STORE` |
| `0F 30–3F` | INS (31/39), EXT (33/3B) | `HAS_MODRM`, `W_FROM_BIT0`, `MODRM_STORE`, `ACC_W_OPERAND`, `XOP=0011` |

22 documented ModR/M forms plus 18 alias fill-ins
(`29 2B 2C 2D 2E 2F 30 32 34 35 36 37 38 3A 3C 3D 3E 3F`) all consume a ModR/M
byte.  Every `0F` second byte outside `10–3F` produces an all-zero vector —
including `0F FF` (BRKEM), which is therefore dispatched by microcode alone, not
by this PLA.

**Independent hardware confirmation.**  `docs/facts/undocumented_0f.md` records a
live V30 probe of 16 undocumented `0F` second bytes, run long before this PLA
analysis, and it agrees with the block model on every point it touches:

| probed | measured | `pla_3` ext prediction |
|---|---|---|
| `0F 2C` | length 4 — ModR/M + disp8 consumed | in the `28–2F` ModR/M block ✔ |
| `0F 30` | length 4 — ModR/M + disp8 consumed | in the `30–3F` ModR/M block ✔ |
| `0F 21`, `0F 27` | length 2, no ModR/M | `20–27` block asserts **no** ModR/M ✔ |
| `0F 24` | length 2, behaves as a CMP4S-like BCD string op | `20–27` block, `BYTE_ONLY` + `XOP=1010` (decimal adjust) ✔ |
| `0F 00/04/08/0C` | length 2, no effect | all-zero vector ✔ |
| `0F 40/60/80/A0/C0/E4` | BRKEM alias, `0F xx imm8` | all-zero vector — microcode-only dispatch ✔ |

This retires the `OPEN_QUESTIONS` item *"0x00-0x3F fine structure: which bytes
take modrm"* for the whole page: **`0F 10–3F` take a ModR/M byte, everything else
on the page does not.**  It also predicts that `0F 34` (the known silent lockup)
consumes a ModR/M byte before it hangs, and that `0F 35–3F` decode as INS/EXT
aliases rather than as further lockups.

### Notable findings / surprises

1. **`0xF1` is a prefix.**  The PLA decodes it in the `111100??` prefix term and
   gives it its own 1BL op code (`XOP=1110`), adjacent to BUSLOCK's `1111`.
   `sw/optable.py` models it as `undocF1`.
2. **`0x63` carries a ModR/M byte.**  Term `01 01100?1?` covers 62/63/66/67.
   `sw/optable.py` currently models `0x63` as ModR/M-less — a length-decoder
   discrepancy worth a hardware probe.
3. **`0x66`/`0x67` are hard aliases of `0x62`/`0x63`** — the same product term
   (`01 01100?1?`) and therefore the same output vector.  Likewise `0x80–0x87`
   receive a *single identical* vector, so GRP1 / TEST / XCHG (and the `0x82`
   alias of `0x80`) are indistinguishable at group-decode time; they are
   separated further downstream.
4. The 8080 map is a first-class citizen of the same PLA, sharing the
   flag-operation encodings bit-for-bit with native mode.
5. Forty native opcodes get an **all-zero** vector: `06 0E 16 1E` (PUSH sreg),
   `50–5F` (PUSH/POP r16), `60 61` (PUSH R/POP R), `68 6A` (PUSH imm) and the
   whole `70–7F` conditional-branch block.  `pla_3` says nothing about
   conditional branches at all — Jcc decode lives entirely in `pla_2` — and the
   stack group is left entirely to microcode.

---

## `pla_2` — CONDITION-EVALUATION PLA — **IDENTIFIED (exact)**

The prior working hypothesis (condition evaluation; leading-0 terms = Jcc, the
`?` positions = flags) is **confirmed exactly**, and the leading-1 bank is
identified as well — but **not** as the microcode JMP-condition set.

### Input model (all 12 inputs ACTIVE-LOW)

| position | signal |
|---|---|
| 0 | decode mode: 0 = native, 1 = 8080 emulation |
| 1 | `/V` (overflow) |
| 2 | `/CY` |
| 3 | `/Z` |
| 4 | `/S` |
| 5 | `/P` |
| 6–11 | `/op5 /op4 /op3 /op2 /op1 /op0` — opcode-register bits |

Output = a single wide OR: **"branch condition satisfied"**.

### Evidence

A brute-force search over every assignment of the five flag lines (5! × 2⁵
polarities) and every permutation-with-inversion of the four condition-code lines
(4! × 2⁴), against the full x86 condition truth table, yields **exactly one**
solution (up to the trivial cc0-polarity ↔ output-polarity duality), at
**0 mismatching cells out of 512**.  Under that unique assignment:

- bank 0 (18 terms, position 0 = `0`) reproduces **all 16 native conditions ×
  32 flag vectors × 4 values of the unconstrained opcode bits 5:4** — 2048/2048
  cells, with `cc` = opcode bits 3..0 (i.e. the `70–7F` / `0F 8x` low nibble).
- bank 1 (8 terms, position 0 = `1`) reproduces **all 8 8080 conditions ×
  32 flag vectors × 8 values of opcode bits 2:0** — 2048/2048 cells, with
  `ccc` = opcode bits 5..3 (the 8080 `11ccc0xx` conditional jump/call/return
  encoding).

Crucially, the flag-line assignment was derived *only* from the native bank and
then **predicted** the 8080 bank correctly with no free parameters.  Bank 1 uses
only CY/Z/S/P and never V or AC — exactly the four testable 8080 flags.  The
shared use of position 8 by both banks is explained by the wiring: `cc3` and the
8080 polarity bit are both opcode bit 3.

Human-readable term listing (bank 0), with all inputs de-inverted:

```
cc={0}   when V=1        cc={1}   when V=0
cc={2,6} when CY=1       cc={3}   when CY=0
cc={4,6} when Z=1        cc={5}   when Z=0
cc={7}   when CY=0 & Z=0
cc={8}   when S=1        cc={9}   when S=0
cc={A}   when P=1        cc={B}   when P=0
cc={C,E} when V=0 & S=1  cc={C,E} when V=1 & S=0
cc={D}   when V=0 & S=0  cc={D}   when V=1 & S=1
cc={E}   when Z=1
cc={F}   when V=0 & Z=0 & S=0
cc={F}   when V=1 & Z=0 & S=1
```

### Negative result: bank 1 is **not** the microcode JMP condition set

`docs/V20UCDIS.PAS` `Str_Cond` enumerates a **4-bit**, 16-entry microcode
condition field — `NC Z NZ OP8b CNTZ L OP8 O NS REP BUSY INTR OPC` plus three
unused slots.  Bank 1 is a **3-bit** selector over four flags with a polarity bit
(8 conditions), and it can express none of `L` (needs S≠V), `O` (needs V),
`OP8b`, `CNTZ`, `REP`, `BUSY`, `INTR` or `OPC` (not PSW flags at all).  It fits
the 8080 `ccc` field exactly instead.  Microcode condition evaluation therefore
lives elsewhere — a candidate consumer for one of the still-unidentified PLAs.

---

## `pla_4` — effective-address / ModR/M `mem` decode — **HYPOTHESIS (core exact)**

Identified in part.  The `mem`-field portion is an exact fit; roughly 60 % of the
term set is still unexplained, so the PLA as a whole is **not** closed.

### The transcription is ragged — read it as an OR-plane, not a term list

45 non-blank lines contain only **34 distinct 12-bit product terms**; eleven terms
are listed twice under a different output-column group.  The record is
`IN(12) [F3(3)] [F7(7)] [F6(6)]`, and three transcription passes are visible:
rows 1–25 carry a 7-bit field, rows 26–36 a 6-bit field, rows 37–45 a 3-bit plus a
7-bit field — with row 37 (`110???????0? 101 0010101 010011`) carrying three
fields at once, which is what proves the blocks are *output-column groups of one
matrix* rather than independent term lists.  `*` is a transcriber's marker.

Input-position census (0 / 1 / `?` over 45 rows):

```
pos:   0    1    2    3    4    5    6    7    8    9   10   11
 0 :   2   17   29   20    1   18    1   11   14    4    1   10
 1 :  43   28   16    7    2    9    1   18    6   11   38    4
 ? :   0    0    0   18   42   43   16   16   25   30    6   31
```

Positions 0–2 are specified in every term; positions 4 and 6 are specified in
three and two rows respectively; the terms overlap heavily (block A alone covers
1728 of 4096 input points with Σ|term| = 2600), so this is a sum-of-products
plane, not a one-hot decoder.

### Exact fit: `mem[2:0]` = input bits (7, 9, 11), active-HIGH

The six terms with prefix `110` and bit 10 = 1 form an **exact partition of all
eight `mem` encodings** — each encoding covered by exactly one term — and their
6-bit output field reproduces the effective-address **base-register** select
bit-for-bit:

| term | `mem` | `mem_field_mod00` | F6 | F6[1] (BW base) | F6[2] (BP base) |
|---|---|---|---|---|---|
| `110????0?01?` | 000,001 | BW+IX, BW+IY | `010011` | 1 | 0 |
| `110????0?11?` | 010,011 | BP+IX, BP+IY | `001011` | 0 | 1 |
| `110????1?010` | 100 | IX | `000111` | 0 | 0 |
| `110????1?011` | 101 | IY | `000011` | 0 | 0 |
| `110????1?110` | 110 | Direct | `000011` | 0 | 0 |
| `110????1?111` | 111 | BW | `010011` | 1 | 0 |

F6[1] is asserted for exactly the three BW-base forms and F6[2] for exactly the
two BP-base forms; the three encodings with no base register (IX, IY, Direct)
assert neither.  Zero mismatches over all 8 encodings, with the product-term
don't-cares falling exactly on the base-register merges.  Independently
re-derived here from the raw file; see `mem_field_mod00` in
`docs/facts/instructions.json`.

The index select corroborates from the other output group: `110????0??10`
(`mem` ∈ {BW+IX, BP+IX}) → F3 `011` and `110????0??11` (`mem` ∈ {BW+IY, BP+IY})
→ F3 `001` — the two merge along exactly the IX/IY split and differ in one output
bit.  Base and index selects are cleanly orthogonal, as an address-adder control
must be.

### Secondary readings (unproven)

- **bit 8 ≈ `mod == 00`** (MEDIUM).  The only encoding whose meaning depends on
  `mod` is `mem = 110` (Direct when `mod = 00`, BP+disp otherwise), and bit 8 is
  the only input that ever splits a `mem = 110` term
  (`1100?0?11110` → `0001000` vs `1100?0?10110` → `0100001*`).
- **bit 10 = "an EA is required"** (MEDIUM).  Every EA-decoding term needs
  bit 10 = 1, and `mod = 11` (register operand, no EA) has no representation
  anywhere in the term set.  One term (row 37) has bit 10 = 0 and is unexplained.
- Bits 0–3, 5 and the loose terms that use bits 4/6 are **UNRESOLVED**.  All the
  non-`110` prefixes still carry `mem` constraints, so they look like per-phase or
  per-operand-class variants of the same decode rather than a second function.
- Segment select (BP-base ⇒ SS, else DS0) is a natural companion output;
  F6[4]/F6[5] are asserted by *every* term in the 6-bit group, which has the shape
  of a segment/enable pair.  **Untested.**

### Documented negative results

| hypothesis | verdict | killer |
|---|---|---|
| register select (`reg`/`rm` + W → AL..BH / AW..IY) | **KILLED** | the six `mem` terms leave bits 3, 5, 8 don't-care; no 3-bit field behaves like `reg`, and no W-like bit appears in any output group |
| microcode entry-point / opcode translation ROM | **KILLED** | none of the 45 patterns matches any 12-bit window of any of the 257 activation patterns in `docs/V20BITS.TXT`, at either offset, in either polarity (0/45); and there is no contiguous 8-bit opcode field |
| ALU-operation decode | **KILLED** | the only fully decoded field is 3 bits wide and maps onto `mem`, not onto the microcode `Str_Op` set |
| group (`/reg`-field) sub-dispatch for 80-83 / C0-C1 / D0-D3 / F6-F7 / FE-FF | **KILLED** | such a PLA would decode `reg` into 8 terms and ignore `mem`; the observed structure is the exact opposite |
| same 12 input lines as `pla_2` (mode + 5 flags + 6 opcode bits) | **KILLED** | under `pla_2`'s map bits 7/9/11 are `/op4 /op2 /op0`; non-adjacent opcode bits are never decoded as a unit, yet these three form a complete 8-way decode.  Also every term constrains bits 1 and 2 (`/V` and `/CY`) while bit 4 (`/S`) is don't-care in 42/45 terms — not a realizable condition PLA |
| 8080-emulation remapping | **NOT SUPPORTED** | no mode bit partitions the terms; no 8080 character anywhere.  Not formally killed — it could only hide in the unresolved bits 0–2 field |

### Cheapest next experiments

1. Re-read the missing output columns for rows 29 and 32–36 from `docs/pla_4.jpg`.
   Falsifiable prediction: row `110????1?010` (IX) gets index bit F3[1] = 1 and row
   `110????1?011` (IY) gets F3[1] = 0, matching the `110????0??1x` pair; Direct and
   BW get no index bit at all.
2. Diff the derived base/index truth table against the EA decode already
   implemented in `hdl/rtl/core/` — a zero-cost behavioural confirmation of the
   bit assignment.
3. Trace the F6[1] and F6[2] sum lines on the die: if they gate BW and BP out of
   the register file into the address adder, the whole reading is confirmed.

---

## Implications for the simulator

`sim/pla3_table.h` is generated from `docs/pla3_outputs.txt` and exposes the
three 256-entry tables plus named accessors.  For the S1 decode loader:

- **Mode select first.**  `kNative` / `kMode8080` / `kExt`, chosen by the current
  decode mode, is the whole of first-byte decode.  There is no fourth mode.
- **Prefix handling** — `pla3::is_prefix(v)`: true iff `ONE_BYTE_LOGIC` is set
  and `bl1_op(v)` is one of the eight prefix codes.  This gives the prefix set
  for free *including* `0F` and the undocumented `F1`, and separates prefixes
  from the flag ops which share the `ONE_BYTE_LOGIC` bit.
- **Instruction length** — `has_modrm(v)` is authoritative for whether a ModR/M
  byte follows (note `0x63` and the `0F` alias blocks); `w_from_bit0(v)` plus
  `byte_only(v)` give the operand width without a per-opcode table.
- **No-microcode fast path** — `one_byte_logic(v)` marks the instructions the EU
  never sees; `bl1_op(v)` names the action directly (set/clear CY, DIR, IE;
  complement CY; HALT; prefix latch).  This is the correct place to implement
  the flag ops, and it explains why they cost what they cost.
- **Operand routing** — `sreg_mov`, `dir_from_bit1`, `acc_w_operand`,
  `modrm_store` cover the register-select decisions for the ALU/MOV families.
- **`incdec_no_cy`** is the CY-preservation interlock for INC/DEC (and rides
  along on the F6/F7/FE/FF groups, where the second byte resolves it).
- `native_hi` and the non-1BL `XOP` values should be **carried but not consumed**
  until their downstream users are identified.

Condition evaluation (`pla_2`) is a pure function and can be implemented as
written; the simulator does not need the PLA form, only the confirmation that the
V30's Jcc semantics are the textbook x86 ones and that 8080 mode uses the
8080 `ccc` field over CY/Z/S/P.

## Gate

`python3 sw/pla3_check.py` — 21 checks: product-term reproduction of all 768
output vectors, exact predicate match for all 14 native columns, completeness and
cross-mode agreement of the `XOP` 1BL table, `XOP` reconstruction for all 256
native opcodes, the `0F` block-granularity claims, and the full `pla_2`
condition model (4096 cells).  Must exit 0.
