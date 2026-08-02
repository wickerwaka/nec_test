# ucsim campaign verdict — 2026-08-01

**The question the campaign asked:** *is the microcode information we hold (the
`docs/V20BITS.TXT` ROM dump plus the PLA dumps) sufficient to build a fully
functional EU?*

**The answer document.**  Every number below is a gate run recorded in
`docs/notes/ucsim_provenance.md` (cited as §n) or a commit in the gate ledger of
§66.  Nothing here is a new claim.

---

## (a) Verdict

**Yes for the architectural EU, and the exceptions are enumerated rather than
estimated.**

A C++ interpreter that executes the dumped micro-rows — micro-sequencing never
flattened into per-opcode C++, no per-opcode fixups, no flag hooks — is
**architecturally exact** on:

| | cases | result | § |
|---|---:|---|---|
| `v0.1` (G-A) | 169 000 | 169 000 / 169 000 | 41, 65 |
| `v0.1-w1` / `v0.1-w3` | 1 200 + 1 200 | both 100 % | 41, 65 |
| `v0.2` | 347 000 | 347 000 / 347 000 | 41, 65 |
| `v0.3` (G-B) | 3 700 000 | 3 699 998 / 3 699 998 (2 VOID captures excluded, 1 EDGE kept and passing) | 47, 65 |
| `v20suite` (G-D), **real µPD70108 silicon** | 3 125 000 | 3 125 000 / 3 125 000 | 48, 65 |
| specials (G-C): `f4a_boundary`, `mod3_illegal`, `f0lock_tranche`, `enter_nesting` | 160 + 128 + 400 + 666 | all green (mod3 under the documented confined stale-EA residue) | 41, 65 |
| A12 segment-boundary subset extracted from `v0.3` | 8 820 (47 real 16-bit offset wraps) | 8 820 / 8 820 | 44 |
| `0F 31/33/39/3B` with `mod != 3` | 19 914 | 19 914 / 19 914 | 45 |

The last two rows are *subsets* of `v0.3` / `v20suite` re-run as their own
first-look gates, so they do not add to the total.  The total is
**7 343 398 single-instruction comparisons plus the four specials
tranches**, on two different parts, and **both mass suites are equally exact with
every flags-mask disabled** — `--raw-flags`, the full 16-bit PSW compared:
`v0.3` 3 699 998/3 699 998 and `v20suite` 3 125 000/3 125 000 (§49.1).  **Not one
undefined flag bit is wrong on either part.**

### Scope of "exact" — read this before any number above

Every number in this document is exactness *within a declared comparison
boundary*, and that boundary is not the whole machine:

* **The final queue is not compared** (policy, numbered A35; residual R5).  The
  functional model has no prefetch at all; in the queue's place the checker
  asserts only that the bytes the decoder consumed equal the case's `bytes`.
  Nothing above is evidence about queue contents.
* **I/O data and event boundaries are replayed inputs, not predictions**
  (policies R3, §38, §57).  `E4/E5/EC/ED` are exact only in the sense that the
  recorded port datum is fed back in; pin events fire at the boundary the golden
  recorded, and in sequence mode at the recorded resume `CS:IP` as well.
* **Non-firing pin cases share their predicate with the checker.**  A pin case
  whose golden shows no pushed frame (masked INT, HALT masked-resume, POLL) is
  run as an ordinary single-instruction case, and the no-frame predicate the
  model uses is *the same one* `sw/check_core.py` uses to decide whether to take
  flags from a pushed PSW (§38).  Model and checker therefore agree on that
  classification by construction: a systematic error in the predicate — or in
  the flag handling downstream of it — would not surface as a failure.
* **`HALT` acknowledges and the `8F /0 mod3` ghost-read address are excluded
  from the compared streams** (§52.2).  The halt cycle carries no address or
  data and may not even close a transaction; the ghost address is the one
  declared don't-care, and it is *not* vacuous here — 78 ghost reads over 54
  seeds ride on the exclusion.
* The sequence comparison excludes **CODE fetches and read DATA** by
  construction (§52), so it is an ordered functional write/IO stream, not a bus
  trace.

Nothing here claims cycle timing; this is architectural exactness only.

### On programs, not just instructions

§56: 3 242 banked fuzz seeds, each a 64 KB image regenerated bit-for-bit from
`(cid, k, ov)` and run from RESET release through a 24-80 instruction random
program.

**The F-A gate as originally planned did not go green as written.**  The plan
(`docs/notes/ucsim_campaign_plan.md`, S3) specified F-A as "mc1 + mc2 + t30-raw
banked seeds: `chip_arch` register-exact + ordered memory/IO write-stream
match".  Run as written, F-A scored **2 873 / 3 157 (91.0 %)**.  The 100 %
figure is the *interpreted* result adopted after the failure survey — the
**architectural-anchor subset**:

* **2 125 / 2 125 (100 %)** of the seeds whose *capture* recorded a complete
  architectural dump (`chip_arch` present) are register-exact, PSW-exact **and**
  ordered-write-stream exact.  That subset is taken over all four banks: 2 123
  of them inside F-A's three banks, plus the 2 anchored seeds of the F-B
  `t30-brkem` bank;
* **0 arch-only divergences** anywhere — the architectural outcome never
  diverges independently of the bus stream;
* 0 GEN-DRIFT over 3 242 `image_sha256` verifications;
* the **284 F-A failures are unresolved and unanchored — not proven suite
  artifacts.**  What is established about them is negative: in every one, the
  *chip's* run never reached the store stub (raw byte soup that wandered, or a
  capture window that ran out), so the comparison is a bus-stream **prefix**
  with no architectural anchor at its end.  The divergence inside that prefix is
  real, and no mechanism has been identified for any of the three groups (210
  native raw-tier, 70 8080-mode, 4 pushed-PSW `P`-bit; §56.2).  The campaign
  decided not to chase them — a decision, not a diagnosis.

Both numbers are the result: full F-A **2 873 / 3 157**, architectural-anchor
subset **2 125 / 2 125**.

**Micro-row coverage: 912 / 1028 rows executed** across all green gates (§62,
re-derived at S4 in `sim/coverage_report.txt`).

**What this buys, stated precisely.**  The claim is *not* "the ROM alone is a
CPU".  The ROM is the EU's control store; a functional EU also needs the
hardware the ROM presupposes (pre-decode/loader, EA adder, ALU datapath, bus
interlocks, interrupt entry addresses).  The campaign's finding is that
**everything the ROM presupposes is either forced to a unique reading by the ROM
itself or pinned by silicon**, *except* for the following, which is the complete
exception set:

1. the **41 standing numbered assumptions** of §(c) — A1..A43 less the withdrawn
   A31 and the falsified A7.  (A43 numbers, as of this revision, the §25.2
   Source2 `[-00-]` = `ONES` entry that S3 booked *unnumbered*; the census is now
   "41 numbered", with nothing left outside the numbering.)  Of the 41, **six are
   EU-semantic free choices** that no asset and no capture discriminates, three
   more are free only as a global naming isomorphism and one is a
   test-environment convention — see §(c) for the row-by-row tally;
2. the **four policy entries** — deliberate non-modelling: final-queue deferral
   (numbered A35), `iord` port-value replay, the single-instruction pin-event
   boundary replay (§38) and the sequence-mode firing-boundary replay (§57);
3. the **open residuals of §(d)** — R1, R2′, R6, R7's SUB4S/CMP4S legs, R9, the
   A30 selection mechanism, cross-interrupt status-latch persistence, the
   `8F /0 mod3` ghost-read address, the absent controlled wait-invariance
   tranche, and the 284-seed F-A tail.

The numbered census is **not** by itself the exception set: (2) and (3) sit
outside it, and the census records what the campaign booked, not everything
nobody thought to ask.  That set as a whole, not the pass rates, is the
campaign's scientific product: it is precisely "what the microcode information
does *not* determine".

Three headline sufficiency numbers:

1. **~76 % of cases end with a PSW every bit of which came out of the microcode
   ROM** (§49.2): 873 999/3 700 000 (23.62 %) of `v0.3` cases and
   777 495/3 125 000 (24.88 %) of `v20suite` cases keep even *one* bit owned by
   a C++ hardware law, and the residue is confined to three named laws (the
   per-step shift/rotate `V` law, the logic ops' `AC = 0`, the fitted BCD
   correction).
2. **V20 vs V30: no architectural difference found across complementary
   suites.**  The same model is exact on 3 125 000 real-µPD70108 cases over 282
   opcodes and on 3 699 998 V30 `v0.3` cases (§48.1).  State the limit plainly:
   **no paired same-vector cross-part A/B was performed.**  `v0.3` and
   `v20suite` are *different* vector sets captured on *different* parts, so the
   two suites are complementary coverage, not a controlled comparison, and no
   vector was run on both parts.  The finding is "no difference found", not "no
   difference exists".  One ROM, dumped from a V20, drives an exact V30 model;
   the only V20-specific code in the whole simulator is the 8-bit port-read
   *fold* (§46), a property of the bus width, not of the EU.
3. **The measured "undefined" flag laws are not inputs to the model — they are
   outputs of it** (§(b) below).

---

## (b) What the ROM + PLAs determined outright

### The ROM is self-describing, and the disassembler proves it

`sim/v30sim disasm docs/V20BITS.TXT` is byte-identical to `docs/V20UC.TXT`,
CRLF included (`make -C sim test`, commit `840ed97`).  1028 micro-rows, 257
activation patterns, 8192-entry micro-address space with **exactly one**
ambiguous address (§34).

### pla_3 = the per-opcode group-decode PLA — IDENTIFIED

59 product terms reproduce all 3 × 256 dumped output vectors bit-exactly; all 14
output columns named and gated against predicates independently computed from
`docs/facts/instructions.json` + `sw/optable.py`, with **zero unexplained
contradictions** (`sw/pla3_check.py`, 21 checks, commit `dcfdfa7`).  The 2-bit
prefix is a decode-mode select (01 native / 00 8080-emulation / 11 `0F` page).
This single dump gives the simulator operand width, ModR/M presence, the
direction swap, prefix membership, the one-byte-logic ops, the accumulator
forms, the pre-read suppression and the `XOP` group used for the I/O-space
discrimination and the REP data test — no per-opcode table anywhere.

### pla_2 = the condition-evaluation PLA — IDENTIFIED (exact)

A brute-force search over every flag-line assignment and every
permutation-with-inversion of the four condition-code lines yields **exactly
one** solution at **0 mismatching cells out of 512**; under it bank 0 reproduces
all 16 native conditions × 32 flag vectors (2048/2048 cells) and bank 1 all 8
**8080** conditions × 32 flag vectors (2048/2048), with the flag assignment
derived from the native bank alone and then *predicting* the 8080 bank with no
free parameters (`docs/facts/pla_model.md`).  pla_2 also carries a clean
**negative** result: bank 1 is *not* the microcode `Str_Cond` set (3-bit selector
over four flags vs. a 4-bit field including `L`, `O`, `OP8b`, `CNTZ`, `REP`,
`BUSY`, `INTR`, `OPC`), so microcode condition evaluation lives in a PLA we do
not hold.

`pla_4`'s `mem`-field portion is an exact fit (the default-segment rule the
simulator uses); ~60 % of its term set is unexplained, so it is **not** closed.

### Emergence: the laws that came out rather than went in

The strongest evidence that the ROM *determines* EU behaviour is that measured
silicon laws which cost the hand-fit RTL dedicated logic **fall out of the
microcode with no code to produce them**.  There are **no flag hooks in the
simulator** (§17):

| measured law (`docs/facts/undefined_flags.md`) | where it comes from | § |
|---|---|---|
| MULU leaves S/Z/AC/P **preserved** | the MULU path contains no `W` row at all | 17 |
| signed MUL writes the **lo+lo self-add** residue (S = bit6/bit14, Z = (result & 0x7F/0x7FFF)==0, AC = bit3, P = parity(result<<1)) | MULADJ `0204/0205` *is* literally `tmpa -> tmpb / ALU ADD tmpb / SIGMA -> NULL W`, and MULADJ is on the IMUL path only | 17 |
| MUL CY/V = "the high half is not the sign extension" | MULX's `0206` ADC + `0209 JMP Z 3` + Int `[-06-]`/`[-07-]` | 17 |
| DIVU leaves the flags of the 16-bit pre-check `SUB` | `018B`/`018E` are the only `W` rows on that path | 17 |
| signed DIV early-trap and late/non-trap flag residues | IDIV `01A6/01A7`; IDIV2 `01AD` with `PASS` latched | 17 |
| AAM / AAD flag residues | `D4` `0121/0122`; `D5` `012A/012B` | 17 |
| shift/rotate with **count 0** leaves every flag untouched | the `R` loop runs zero iterations and `0228 JMP Z 3` skips the write-back | 17 |
| TEST1 sets S/Z/P of the **masked** value, AC = 0 | ordinary logic-op flags over the `ALU BIT` one-shot mask; **no TEST1-specific code exists** | 23.1 |
| ADD4S/SUB4S/CMP4S: `S = AC = CY(out)`, `P = Z(out)`, `V = 0` | the tail's `tmpb + tmpb` over three reachable seeds at `02DF` | 25.2 |
| the hand-fitted BCD-string "one-carry-rail decision quirk" | the §17.2 nibble-rule fit applied to the ADC result, no BCD-string-specific code | 25.3 |
| **"the saved IP covers the whole prefix chain"** (REPX rewind, incl. stacked prefixes) | rows `0225`-`0227`: `PC := PC - PFXCNT - 1`.  Not a modelled rule anywhere in the simulator; 21 mid-string withdrawals land on the recorded boundary, **including 4 with `PFXCNT = 2`** | 37, 57.1 |
| BRKEM vs. CALLN mode switching | one shared routine and one counter: `0092 JMP CNTZ 12` over `COUNT`, entered 1 by BRKEM and 0 by CALLN | 55 |
| ENTER's nesting walk is **not** masked mod 32 | `CNTZ` over `level - 1`; 666/666 chip walk digests, max 256 pushes at `nest = 255` | 41 |

Three ALU behaviours did **not** emerge and are C++ hardware laws: the per-step
shift/rotate `V` law, the logic ops' `AC = 0`, and the fitted BCD correction
(§17, §31).  Those three are the entire hardware residue in the flag domain, and
§49.2 measures exactly how much of the compared state they own.

### Semantics the ROM forced with no alternative reading

Each of these was resolved with a documented negative control that was *actually
run* and that restores to 100 % when reverted (§9, §12, §14.1, §16, §18-§20,
§23-§27):

`E` retires one row late; the 16-row `{rowgrp, row}` `loc` counter; the micro-PC
carrying out of `loc` into the opcode byte; `OPC = opc_base + sel` over three op
blocks; `OP8` = "the immediate is one byte" vs. `OP8b` = "the operand is
byte-wide"; the `R` loop running COUNT iterations inside its own row; `CNTZ` as
decrement-and-continue; the three distinct `JMP`-condition taps; `F` as the read
interlock; write-data **pairing**; `FARJMP` rows issuing no bus cycle; the
`[-06-]` write-back strobe as memory-only; `ALU BIT` as a one-shot port-B mask
with the index captured at its own row; `ALU ROL12`'s rotate tap at **bit 11**
(which is *why* the real ROL4 does not preserve AL's high nibble); the ADJx
arm/discharge rule; Ext `[-05-]` as the interrupt acknowledge and Ext `[-03-]`
as a word-width override (§53).

---

## (c) The assumption census — what the microcode information does NOT determine

This is the campaign's product.  42 numbered assumptions were booked across S1-S3
(§30, §38, §50, §63); **A31 was withdrawn** at S3 (§53) and **A7 was falsified**
by its own recorded falsifier at S3 (see §(g) below).  S3 also left one
assumption standing *unnumbered* — the §25.2 Source2 `[-00-]` = `ONES` value —
which this revision numbers **A43** so that the census is settled and has nothing
outside it.  **41 numbered assumptions stand.**

Kinds:

* **ROM-constrained** — the ROM admits exactly one behaviour that makes the
  affected block intelligible, but no dumped asset *names* it.  A die trace would
  confirm rather than decide.
* **MEASURED-constrained** — a silicon capture pins the value uniquely; nothing
  in the dumps does.  Remove the capture and the assumption is free.
* **PLA-corroborated** — a dumped PLA independently predicts the encoding; the
  residue is only that the microcode consumes that PLA's output.
* **free choice** — nothing we hold contradicts the alternative.  **These are
  what a die/PLA re-read would have to settle**, and they are the honest answer
  to "what does the microcode information not determine".
* **free naming choice (global remap class)** — the proposition as written *is*
  discriminated by silicon, and is free only under a simultaneous relabelling of
  an internal index space.  Defined precisely under the table.
* **test-environment convention** / **policy** — not EU semantics at all.

| # | assumption | § | kind |
|---|---|---|---|
| A1 | binary ALU ops compute `tmpb OP tmp[Tmp]`; unary ops act on `tmp[Tmp]` | 2.1 | ROM-constrained |
| A2 | `INC2`/`DEC2` are always 16-bit regardless of operand width | 2.4 | **MEASURED-constrained** (reclassified at S4r).  Booked as a free choice, but its own recorded falsifier — "a byte-width instruction whose microcode also does stack arithmetic" — became reachable at §53 and **was exercised successfully**: the undefined `FE`-group byte forms (`FE /2`, `/3`, `/6`) push through that path on silicon and the model is exact on them (§(g) item 1a) |
| A3 | the pre-decode contract of §3.1 (prefixes, opcode register, ModR/M + disp, EA→IND, M/R binding, pre-read, page select) | 3.1 | ROM-constrained |
| A4 | `R` = segment register `(opcode>>3)&3` for `06/0E/16/1E` (pla_3 gives them an all-zero vector) | 3.2 | **free naming choice (remap class Σ)** — silicon-discriminated as an isolated proposition; free only under the global segment-index relabelling defined below |
| A5 | `M` = GPR `opcode & 7` for `40-5F`, `90-97`, `B0-BF` | 3.2 | **free naming choice (remap class Γ)** — silicon-discriminated as an isolated proposition; free only under the global GPR-index relabelling defined below |
| A6 | segment-prefix decode `26/2E/36/3E → (b>>3)&3` | 8 | **free naming choice (remap class Σ)** — same class as A4; the two are not independently free |
| ~~A7~~ | ~~`SR == SS` accesses are word-wide regardless of operand width~~ | 7 | **FALSIFIED at S3**, replaced by A37 (§53) |
| A8 | `M`/`R` as a **source** on a memory operand returns OPR; `-> M` stages into OPR | 8 | free choice |
| A9 | `PC` is the microcode-visible "next unconsumed byte" pointer, separate from the BIU fetch pointer | 8 | free choice (every branch form green) |
| A10 | `ONES` = 0xFFFF, `ZEROS` = 0, `dir*sz` = ±1/±2 | 8, 52 | **MEASURED-constrained** (reclassified at S4r).  These are *values*, not names, so no compensating remap exists, and each reaches compared state: the ROM's own RESET rows `01D0`-`01D5` are `ONES -> CS` and `ZEROS -> DS/ES/SS/FLAGS/PC`, executed from RESET release in all 3 242 fuzz-image replays (`CS = FFFF`, the rest 0 — any other constant misses the reset vector entirely); `ONES` is also the mask source for `TEST1`/`SET1`/`NOT1`/`CLR1`; `dir*sz` is confirmed by `008C` and by every string form captured in both directions at both widths |
| A11 | `AL:AH` (Source1 0x10) is the byte-swapped AW | 8 | MEASURED-constrained |
| A12 | word memory accesses wrap the **offset** at 16 bits inside the segment | 8, 44 | **MEASURED** (8 820 boundary cases, 47 real wraps) |
| A13 | unlisted memory reads as 0x00 | 8 | **test-environment convention** — *not* an EU semantic.  It governs how the harness initialises memory a golden does not list, i.e. absent-memory initialisation on the test bench, and no bring-up or gate case depends on the value.  The real chip's answer here is a board property (bus float / RAM contents), not a microcode question |
| A14 | `F` is a bus interlock (delivers a completed read into OPR), not a flag control | 8, 18.1 | ROM-constrained |
| A15 | `SUSP` = logged no-op; `FLUSH` = clear queue and refetch from CS:PC | 8 | free choice |
| A16 | `OP8` membership is `byte_operand ∪ {0x83, 0x6B}` | 10 | MEASURED-constrained (no dumped column separates that pair) |
| A17 | the ALU **status latch** loads on every row that gates SIGMA onto the bus | 14.1 | ROM-constrained |
| A18 | `NS` is a direct sign tap on `tmpb` at the operand width | 14.2 | ROM-constrained |
| A19 | the repeat-prefix → data-test polarity map (`F3/F2` → Z, `65/64` → CY), and *last prefix wins* for a conflicting chain | 15, 59 | MEASURED-constrained (2 032 conflicting chains over 1 303 seeds; every REP form in `v0.3`) |
| A20 | `[-1E-]` = ABS and loads the sign latch; `[-0C-]` toggles it by sign(tmpb); `[-09-]` tests it clear | 16 | ROM-constrained |
| A21 | the `MUL` / `DIV` micro-step algebra (shift-add; **restoring** division) | 16.1 | ROM-constrained |
| A22 | `ADJD`/`ADJA` **arm** a mode that the following `ADD`/`SUB` executes | 17.2 | ROM-constrained |
| A23 | write-data **pairing**, with an `OPR ->` source read consuming freshness | 18.2, 27 | ROM-constrained |
| A24 | `SR = IO` means the **zero segment** except for pla_3 `XOP` 1111 / 0110 | 18.3 | MEASURED-constrained |
| A25 | the ALU latch at instruction entry is `ADD tmpa` plus the synthetic EA constant | 21 | ROM-constrained |
| A26 | `ALU BIT` captures the index at its own row and masks port B of the **next** latched op only | 23.1 | ROM-constrained |
| A27 | an ADJx arm not consumed by an `ADD`/`SUB` **discharges** as a plain truncation | 26.2 | ROM-constrained |
| A28 | the bit-field group's byte-register binding is keyed off ext `XOP = 0011` | 23.4, 45 | MEASURED-constrained (19 914 `mod != 3` cases) |
| A29 | the three hardware entry addresses (INT pin, NMI, BRK/TF trap) and that `F4` HALT has no microcode at all | 33 | ROM-constrained |
| A30 | the `111.00000010.00` bank pair is selected by an **emulation-mode input** to the micro-address decoder, rather than by a fixed priority with bank A dead silicon | 34, 61 | **free choice** — explicitly not excluded by anything we hold |
| ~~A31~~ | ~~Ext `[-03-]` is architecturally inert~~ | 35 | **WITHDRAWN at S3**, replaced by A37 |
| A32 | `INTR` is the recognition latch AND the `REP` continuation's second term | 37 | ROM-constrained |
| A33 | the hardware presents a **cleared loader context** (`xop`) at an internal entry | 40 | free choice — no golden covers it; closed only by a simulator-side directed probe |
| A34 | the acknowledge data is the harness constant `0x00FF`, replayed like `iord` | 35 | MEASURED-constrained (read off the golden traces) |
| A35 | the final **queue** stays deferred; in its place the bytes the decoder consumed must equal the case's `bytes` | checker | policy, asserted by every gate case |
| A36 | the V20 port-read fold (byte replicated on both lanes; word = `lo \| hi << 8`) | 46 | free choice — **provably inert on this data**: every IOR cycle in the V20 suite carries `0xFF`, and 0 of 3 125 000 word reads had disagreeing lanes |
| A37 | Ext `[-03-]` (`01ED`) forces WORD bus width for the rest of the micro-sequence | 53 | MEASURED-constrained (the `FE`-group byte pushes vs. the byte-DIV trap separate it) |
| A38 | the 8080 register map and the M = source / R = destination field binding | 55 | ROM-constrained (each item read off the microcode) + MEASURED (153 executed `110`-page rows, 76/85 `t30-brkem`) |
| A39 | the 8080 `ALU OPC` permutation ADD ADC SUB SBB ANA XRA ORA CMP | 55 | MEASURED-constrained |
| A40 | the 8080 `JMP OPC` condition bank reads opcode bits 5:3 (NZ Z NC C PO PE P M) | 55 | **PLA-corroborated** (reclassified at S4r) — the dumped `pla_2` bank 1 *predicts* exactly this encoding at **2048/2048 cells**, with the flag-line assignment derived from the native bank alone and no free parameters, and it was fitted at S0b *before* A40 was written.  The residue is only that the microcode's `JMP OPC` consumes that PLA output rather than recomputing the condition (§(g) item 2) |
| A41 | `ENDEM` returns to native mode unconditionally | 55 | ROM-constrained (`0090` pushes FLAGS before `0093` clears MD) |
| A42 | the BRK/TF single-step trap is armed from TF as it stood at the START of the instruction | 62 | MEASURED-constrained (fuzz-bank TF traps) |
| A43 | Source2 `[-00-]` = `ONES` | 25.2 | MEASURED-constrained.  **Numbered at S4r** — S3 booked this one standing but unnumbered.  Its *only* use in the entire ROM is `02DF`'s BCD tail seed at `02DA`, and no other plausible source reproduces AC and P together |

### The compensating-remap equivalence behind A4, A5 and A6

A4, A5 and A6 were booked as free choices.  Taken literally they are not: each
is **falsified at mass-suite scale as an isolated change**.  Permute A5's map
alone and `40-47`, `50-5F`, `90-97`, `B0-BF` write the wrong register in
`v0.1`/`v0.2`/`v0.3`; permute A4's alone and `06/0E/16/1E` push the wrong
segment against goldens that carry four distinct segment values; permute A6's
alone and every segment-overridden access reads through the wrong segment.

What is genuinely undetermined is narrower and precise.  Each of these maps sends
an opcode field into an **internal index space** whose *labels* — "AW", "SS" and
so on — come from `V20UCDIS.PAS`'s mnemonics, a documentation artifact, not from
any dumped electrical fact.  Let π be a permutation of such an index space.  The
model is observationally identical under π **iff π is applied simultaneously to
every un-dumped opcode-field→index map and to the labelling of the ROM's dumped
selector values**:

* **class Σ (segments, A4 + A6):** π must be applied to A4's `(opcode>>3)&3`,
  A6's `(b>>3)&3`, the `8C`/`8E` ModR/M `reg`→segment map, the labelling of the
  ROM's `Source1`/`SR` segment selectors and of `pla_4`'s `mem`-field outputs.  π
  must fix the fetch segment (`PS`/CS is pinned by the RESET vector and by
  instruction fetch).  A4 and A6 are therefore **one** free choice between them,
  not two.
* **class Γ (GPRs, A5):** π must be applied to A5's `opcode & 7`, the ModR/M
  `reg` and `r/m` register maps, and the labelling of the ROM's dumped register
  selectors.  π must further preserve structure the ROM does depend on: the
  byte-addressable quartet (`AL:AH` and the byte-register halving), the `AW:DW`
  pair used by MUL/DIV, and the roles the ROM names for `CW` (COUNT/`CNTZ`/REP),
  `SP`/`BP` (stack, ENTER) and `IX`/`IY` (string).

So A4/A5/A6 are free **naming** choices — two equivalence classes, Σ and Γ, of
global relabelling that change no predicted bit anywhere — and are *not* free as
independent propositions.  A die re-read would settle them by naming wires; it
would not change a single predicted capture.  They are booked separately from the
six EU-semantic free choices for exactly that reason.

### The corrected final tally — 41 standing numbered assumptions

This is the single authoritative tally; earlier provisional presentations of the
census (including the "11 or 12 free choices" formulation carried into S4) are
superseded by it.

| kind | n | entries |
|---|---:|---|
| ROM-constrained | **16** | A1, A3, A14, A17, A18, A20, A21, A22, A23, A25, A26, A27, A29, A32, A38, A41 |
| MEASURED-constrained | **13** | A2, A10, A11, A12, A16, A19, A24, A28, A34, A37, A39, A42, A43 |
| PLA-corroborated | **1** | A40 |
| **free choice (EU-semantic)** | **6** | A8, A9, A15, A30, A33, A36 |
| free naming choice (remap classes Σ, Γ) | **3** entries in **2** classes | A4, A6 (Σ); A5 (Γ) |
| test-environment convention | **1** | A13 |
| policy, numbered | **1** | A35 |
| **total** | **41** | |

**The free-choice number is 6** — A8, A9, A15, A30, A33, A36 — plus two global
naming isomorphisms (A4/A6, A5) that no dumped asset labels and no capture can
see.  A13 is a bench convention and A35 is a policy; neither is an undetermined
EU semantic.

**Policy entries (deliberate non-modelling, 4):** final-queue deferral (this one
*is* numbered, as A35 — it is not a fifth entry); `iord` port-value replay; the
single-instruction pin-event boundary replay (§38); the sequence-mode firing
boundary replay (§57, two coordinates: bus position **and** the recorded resume
`CS:IP`).

**The honest shape of the answer.**  Six free choices out of everything a working
EU needs is a small residue, and none of the six is in the *computational* core:
two staging conventions (A8, A9), one BIU control convention (A15), one
decoder-input mechanism (A30), one entry-context reset (A33) and one bus-lane
fold the available data cannot discriminate (A36).  Add the two naming
isomorphisms (A4/A6 for segments, A5 for GPRs) — operand-binding *labels* for
opcode groups the PLAs do not cover — and one bench convention (A13).

Every arithmetic, flag and sequencing decision the campaign compared is either
ROM-forced or pinned by silicon, **with two stated exceptions, both
undiscriminated rather than decided**:

* **R1 — the byte-shifter's hidden high byte.**  `alu_step` keeps `tmpb`'s high
  half across a byte-width shift (`hi_keep`).  6.8 M cases on two parts at raw
  PSW contradict nothing, but no golden reads that half back at word width, so
  the datapath choice is undiscriminated (§(d)).
* **cross-interrupt status-latch persistence.**  Whether the ALU status latch
  that `JMP C/NC/Z/NZ/L/NS` reads survives an interrupt entry is measured to be
  undiscriminable by the retained data: `--stat-clobber` changes nothing in 0 of
  3 242 seeds across 953 replayed entries (§60).  The model's answer — it
  persists — is a sequencing decision that neither the ROM nor any capture
  forces.

Both are sequencing/ALU decisions inside the compared region; neither is
covered by the "ROM-forced or silicon-pinned" claim.

---

## (d) Residuals, and the directed experiment that would close each

Board access is required for the first five; none of it was available (or needed)
during this campaign, which ran fully offline.

| # | residual | status / size | directed experiment |
|---|---|---|---|
| §60 | **ALU status-latch persistence across an interrupt** — does `Machine::stat` (what `JMP C/NC/Z/NZ/L/NS` read) survive an interrupt entry? | **NOT DISCRIMINATED, and now measured to be so**: `--stat-clobber` overwrites `stat` with `0x5555` at every interrupt entry and **0 of 3 242 seeds change outcome** — not the verdict, not the first divergent event, not the stream length, across 953 replayed interrupt entries | **Step 1 (board-free, and a PREREQUISITE — not an optional shortcut):** sweep the ROM for a bank in which a status-latch consumer (`JMP C/NC/Z/NZ/L/NS`) precedes *every* SIGMA-gating row of that bank, i.e. an instruction that reads the latch before rewriting it.  **If no such bank exists, no board probe can be constructed** and the residual closes as architecturally unobservable.  **Step 2, only if step 1 returns a bank:** the two-instruction board probe built *from that bank* — instruction 1 sets the latch, an INT/NMI fires at the boundary, instruction 2 is the identified form and branches on the latch before re-writing it |
| §61, §34 | **A30 — the bank-A selection mechanism** at the ROM's one ambiguous micro-address.  Silicon runs bank B (measured twice, §34); *why* the decoder picks it is open — an emulation-mode 14th input, or a fixed priority with bank A dead silicon | bank A is **0/4 executed** across 3 242 seeds *even with 8080 mode live*; all 764 INTA runs in the bank are two-cycle pairs, including 7 in seeds that entered 8080 mode; the 3 acknowledges the model believes were taken with `MD = 0` are all in already-divergent seeds | A **directed capture** (ledger's own wording, §61): a contained program that executes `BRKEM`, stays in 8080 mode, and takes an INTR.  **One INTA cycle instead of two settles it in a single seed.** |
| R1 | **byte-shifter hidden high byte** — `alu_step` keeps `tmpb`'s high half across a byte-width shift (`hi_keep`); the real chip's high byte there is unobserved | OPEN.  6.8 M cases on both parts at raw PSW contradict nothing, but no golden reads the high half back at word width, so it is *undiscriminated*, not confirmed | A form that runs a byte-width `R` shift and then reads `tmpb` at word width.  **Board-free first step (proposal):** a ROM sweep for such a bank; if none exists, `hi_keep` is architecturally unobservable and closes as a don't-care.  Otherwise capture that form directly |
| R6 | **`0F 20/22/26` with `CL = 0`** — `JMP CNTZ` underflows into a ~2ⁿ-iteration loop (`docs/facts/undocumented_0f.md`) | OPEN and **known un-closable from the existing suites**: no `0F 20/22/26` case anywhere in `v0.3` (`CL` 1..6) or `v20suite` (`CL` 1..238) has `CL = 0` | A **directed capture of the loop running to UNINTERRUPTED COMPLETION** — ADD4S/SUB4S/CMP4S at `CL = 0` with the capture window (and the memory the underflowed loop walks) sized for the full ~2ⁿ iterations, so the final architectural state and the whole write stream are compared.  The interrupt-aborted variant the pin-event scheduler makes cheap is **only a partial discriminator**: it witnesses that the loop is long and where it was when the pin fired, but it does not settle the termination condition, the final counter/pointer values or the tail flags.  Run it as a cheap first probe if wanted; it does not close R6 |
| R2′ | **POLL `BUSY` hard-FALSE** | OPEN and **quantified**: exactly 5 ROM rows (`006F`-`0073`, the POLL busy loop and its interrupt withdrawal) are unreached because of it; `POLL.LO`/`POLL.REL` (2 400 cases) are green with the pin never raised | **Two probes, because one does not reach all five rows.**  (i) **BUSY-high-then-release**: a `9B` POLL tranche with the POLL pin held **high** for N cycles and then released, INTR left clear — `006C`'s `JMP BUSY 3` branches to `006F`, whose `JMP INTR 5` evaluates **false**, and `0070`'s `JMP 0` spins back; this exercises `006F`'s not-taken arm and `0070`, and the observable is the extended, released-on-cue POLL.  (ii) **BUSY-high + INTR**: the same tranche with an interrupt asserted *while* the part spins — `006F` now takes its arm into `0071` `CTL SUSP`, `0072` `PC -> tmpb / ALU DEC tmpb` and `0073` `SIGMA -> PC E CTL FLUSH`, and the observable is a pushed return address pointing **at the POLL instruction itself** plus the flush and the post-handler re-execution.  Both are needed: probe (i) alone never reaches `0072`/`0073`, probe (ii) alone never exercises `006F`'s false arm or `0070`.  The harness pin-event scheduler exists (ROADMAP campaign 3, block 4) |
| §56.1 | **No controlled wait-invariance tranche** | The wait axis and the program are drawn from the same seed, so no two banked seeds run the **same** program at different waits.  Evidence today is "no counter-example" (86-95 % exact in every wait class, worst class is `w0`), not "same program, both waits".  The six-form `v0.1-w1`/`w3` tranches are a confirmation over six forms only | A **re-emission**, not a re-analysis: a fuzz tranche with `(program, wait)` as *independent* axes — the identical image captured at `w0`/`w1`/`w3` — gated on functional-stream identity |
| R7 | the ADD4S "Z accumulates on the PRE-adjust bytes" clause | **ADD4S leg CLOSED** (§51): the ten discriminating cases exist, the chip reports `Z = 0` on all ten, and §25.2's tail overwrites the accumulated `Z`, so the distinction is not architecturally observable.  **SUB4S/CMP4S legs undiscriminated** — CMP4S stores no result, so no equivalent probe exists in these suites | The probe is only defined once a **discriminator** is: CMP4S writes no result, and §25.2's `tmpb + tmpb` tail overwrites the accumulated `Z` in the final PSW, so the pre-adjust accumulation has **no known observable** — neither a final-PSW bit nor a bus event.  **Step 1 (board-free):** sweep the ROM for a `JMP Z`/`JMP NZ` consumer of the accumulated `Z` *before* the `02DF` tail, i.e. a control-flow path (loop termination, digit-count exit) whose direction the clause would change; a directed CMP4S case whose adjusted byte is `00` while the raw SBB byte is not, as the only non-zero pair, is then the vector to run.  **If no such consumer exists, mark the SUB4S/CMP4S legs architecturally unobservable** and close them the same way the ADD4S leg closed at §51 — the residual is then a don't-care, not an open behaviour |
| R9 | pla_3 **b6's mechanism** — a mode-gated consumer versus a separate, undumped ext-page fetch-enable term.  Both *senses* are MEASURED (§23.3); the mechanism is not | OPEN | a die/PLA re-read (`docs/facts/pla_model.md`, "cheapest next experiments") |
| R10 | 8080 emulation | **largely CLOSED** (§55): implemented from the ROM, 158 of its 192 rows execute, `t30-brkem` 76/85.  What remains is a **quality** residual — the 70 `mfc > 0` seeds of §56.2 — not an unimplemented feature | none required for the verdict; the 70 seeds are raw 8080 byte soup with no architectural anchor |
| R3 | the port datum is **replayed**, never predicted | permanent **policy** — there is no I/O model.  `E4/E5/EC/ED` are exact only in the sense that the recorded input is fed in.  Load-bearing, not decorative: removing the V20 trace extraction takes `E4/E5/EC/ED` from 40 000/40 000 to **0/40 000** (§46) | n/a (policy) |
| R5 | final **queue** comparison deferred | the functional model has **no prefetch** at all; A35's consumed-bytes assertion stands in for it and holds on every gate case, including the V20's byte-fetch queue.  §64 records this as the strongest evidence yet that the deferral is sound: every one of the 2 873 exact fuzz seeds is a *sequence* whose functional stream is queue-independent | the **timing campaign** |
| §52.2 | the `8F /0 mod3` **ghost-read address** is a declared don't-care (78 ghost reads over 54 seeds, so not vacuous) — but in a *sequence* replay the "pre-window execution history" the metadata blames is now inside the window, so the address is in principle predictable | OPEN, raised at S3 as an S4 question and **not closed here** | predict the ghost address from the in-window history and re-run the 54 seeds with the don't-care disabled; a board-free experiment on retained data |
| §56.2 | the **F-A tail**: 284 seeds — 210 raw-tier native (no instruction context accounts for more than 5; modal shape = write at the right address with the wrong byte), 70 8080-mode residue, 4 `soup`-tier pushed-PSW `P`-bit | **OPEN, UNRESOLVED and UNANCHORED — explicitly not proven to be suite artifacts.**  What is established is only that the *chip's* run never reached the store stub in any of them, so each comparison is a bus-stream prefix with no architectural anchor; the divergence inside the prefix is real and unexplained.  Deliberately **not** chased instruction-by-instruction — "that is a hunt, not a mechanism" — which is a decision, not a diagnosis.  Full F-A is **2 873 / 3 157**; the 100 % figure quoted elsewhere is the anchored subset (2 123 within F-A, 2 125 over all four banks) | re-capture those seeds with a longer window so the chip reaches the store stub, converting a prefix comparison into an anchored one — the only route that would tell an artifact from a model bug |

---

## (e) The untested ROM surface

Coverage is **912 / 1028** rows (§62; re-derived at S4, `sim/coverage_report.txt`).
Of the 116 unexecuted rows, **9 are substantive** — they carry a ROM claim that
nothing has ever exercised — and they fall into exactly the **two named
residuals** of §(d):

| rows | bank | what they say | why unexecuted |
|---|---|---|---|
| `006F` | `00?.10011011.00` (`9B` POLL) | `JMP INTR 5` — enter the withdrawal path | **R2′**: `BUSY` is hard-FALSE, so `006C`'s `JMP BUSY 3` never branches; `006D` carries `E`, `006E` is its delay slot, and POLL retires **before** `006F` |
| `0070` | `00?.10011011.01` | `JMP 0` — the busy spin | R2′ |
| `0071` | " | `CTL SUSP` | R2′ |
| `0072` | " | `PC -> tmpb  ALU DEC tmpb` — back the PC up over POLL | R2′ |
| `0073` | " | `SIGMA -> PC  E  CTL FLUSH` — re-execute after the handler | R2′ |
| `01DC` | `111.00000010.00` bank A | `AX -> tmpc  CTL SUSP [-05-] IO` — a **single** acknowledge, AW saved | **A30**: silicon runs bank B |
| `01DD` | " | `OPR -> AX  F` | A30 |
| `01DE` | " | `AL:AH -> tmpbL` — vector off the **high** lane | A30 |
| `01DF` | " | `tmpc -> AX  CTL FARJMP INT` — AW restored | A30 |

That is exactly the 5 + 4 rows §49.3 and §62's own block table report as
`006F`-`0073` 0/5 and bank A 0/4; the *narrative* line in §62 named only 8 rows
and picked the wrong 8 (§(g) item 5).

The remaining 107 unexecuted rows carry **no ROM claim we can identify**:

* **14** are the row immediately following an unconditional `CTL FARJMP`, which
  has no delay slot.  These are unreachable by the ROM's own sequencing rule.
* **93** are **structurally dead under the stated criterion** — a trailing row of
  a bank all of whose later rows are also unexecuted, none of them a bank's
  row 0 — which is the same criterion S3 used and which all 93 satisfy.  This is
  a *filter*, not a proof: it says no gate reached them and that nothing
  downstream of them was reached either.  It is **not machine-proved
  unreachability**; no reachability analysis over the micro-address decoder was
  run, and a `JMP` arm or an entry pattern that no suite exercises could in
  principle land in that set.

**Every unexecuted row is either accounted for by a named residual (9 rows) or
structurally dead under the stated criterion (107 rows); none is unexecuted for
want of trying.  "Structurally dead" is an evidential classification, not a
machine-checked proof of unreachability.**

Note what §62's number already includes: the fuzz-bank replay newly covered the
ROM's own **RESET** sequence (6/8 rows — a fuzz image replay is exactly the entry
those rows exist for), the **BRK/TF trap** entry, the **INTEM** bank, the
**BRKEM** entry and 158 of the 192 8080-page rows, all of which were on S2b's
unexecuted list.

---

## (f) Implications

### For the FPGA RTL (`hdl/rtl/core/v30_eu.sv`)

The campaign is the converse of the two 2026-08-01 pilots
(`docs/notes/ins_microcode_pilot_2026-08-01.md`,
`docs/notes/enter_microcode_pilot_2026-08-01.md`), and they meet:

* **INS** — the pilot replaced ~8 per-geometry qualifier families and ~79 fitted
  rail constants in `v30_eu.sv` with 4 global integers derived from ROM loop
  counts; write rails **1312/1312** exact, including the four `fz12569 C1`
  w12/w14 cells the FSM RTL fails.
* **ENTER** — the pilot replaced 6 FSM states, three fitted delays and two patch
  flags (`prep_acc`, `w4skip`) with the ROM row sequence plus 7 integers and a
  shared grant law; **zero residuals** on the frozen validation split, and the
  cross-opcode transfer test (a law fitted on ENTER improving INS's untouched
  data, 782/800 → 796/800) is behaviour a per-opcode rail forest cannot exhibit.

ucsim supplies the *architectural* half of the same argument, and it lands on
the same two families from the other side.  The sharpest datapoint is
**`enter_nesting`: 666/666 chip walk digests, with the nesting explicitly not
masked mod 32** (§41) — the ROM's `CNTZ` over `level - 1` produces that
directly, and the task-#31 RTL bug class (the nesting-mask bug `efdd0b8` and the
PUSH-BP-drop-under-waits bug `d104673`) is *unrepresentable* in a micro-march
that walks those rows.

Concretely, what the RTL can now take from the ROM instead of from a fit:
the undefined-flag laws of §(b) (which the RTL carries as per-class flag logic),
the REPX prefix rewind (`PC - PFXCNT - 1`, an RTL rail today), the BCD-string
digit-count and adjust rules, `ROL4`'s AL-high-nibble behaviour, the ENTER walk,
the BRKEM/CALLN mode switch, and the whole `[-03-]` word-width override — the
last of which the RTL's 8080-mode and `FE`-group parking (ROADMAP campaign 4
item G "Deferred") has never had to face.

**A second independent implementation.**  ucsim is now a second EU derived from
a *different source* (the ROM) than the RTL (silicon traces).  Where they agree,
the agreement is evidence; where they disagree, one of them has a bug and the
provenance ledger says which claim to check.  It costs no board time.

### For the future timing campaign

The simulator was built so timing is not precluded, and S4 hands three things
forward:

1. **The interlock call sites are preserved.**  `sim/biu.h` states it in its
   header: timing is not modelled, every access completes instantly, and the
   `F` / `Q` wait sites live in `exec.cpp` (`deliver_read()` on the `F` row).
   A cycle-accurate mode fills those in rather than restructuring the
   interpreter.
2. **The functional/timing boundary is drawn and measured.**  Everything the
   functional model *replays* rather than predicts is a numbered policy (4 of
   them), and each one names the timing mechanism that would replace it: the
   pin-recognition pipeline of `docs/facts/interrupt_model.md` (pin@B-3,
   IE@B-3, single-boundary shadows, taken-branch flush anchoring) for the two
   boundary-replay policies, the prefetch model for R5, an I/O model for R3.
3. **The bus-order facts are already pinned.**  Write-data pairing (§18.2/§27),
   the byte-lane law (§52.1, cross-checked against `hdl/rtl/test_mem.sv`), the
   `[-03-]` width override (§53), and the fact that the *element's own store is
   still pending* at the REP interrupt test (§57, measured on `mc1/1447`) are
   all functional-mode findings that a timing model inherits rather than
   rediscovers.

The timing campaign's own residuals from this campaign are R5 (queue), R2′
(BUSY), and the controlled wait-invariance tranche of §(d).

---

## (g) Inconsistencies found while consolidating

Recorded rather than papered over.  None of them changes a gate result.

1. **A7 was falsified at S3 but never struck from the running total.**  §30's A7
   is "`SR == SS` accesses are word-wide regardless of operand width", with the
   falsifier "a byte-width instruction whose microcode touches the stack".  §53
   *ran* that falsifier — the undefined `FE`-group byte forms (`FE /2`, `/3`,
   `/6`) push a single **byte** on silicon — and replaced the rule with A37.  The
   ledger withdrew A31 explicitly but left A7 standing in the count.  **Standing
   assumptions are 40, not 41.**
1a. **A2's falsifier is now reachable, and it passes.**  A2 ("`INC2`/`DEC2` are
   always 16-bit regardless of operand width") records the *same* falsifier
   shape as A7 — "a byte-width instruction whose microcode also does stack
   arithmetic" — and the §53 `FE`-group byte pushes are exactly that.  The
   model is exact on them (the anchored subset — F-A 2 123/2 123, 2 125/2 125
   over all four banks), so A2 moves
   from free choice to MEASURED-constrained.  **Applied at S4r** — §(c)'s census
   and tally now carry the reclassification; no new mechanism is claimed.
2. **A40 is corroborated by a dumped PLA and should not be a bare assumption.**
   A40 (booked at S3) says the 8080 `JMP OPC` condition bank reads opcode bits
   5:3 in the order NZ Z NC C PO PE P M.  `docs/facts/pla_model.md`'s pla_2
   identification — completed at S0b, *before* A40 was written — fits bank 1 of
   pla_2 to exactly that encoding (`ccc` = opcode bits 5..3, the 8080
   `11ccc0xx` form) at 2048/2048 cells, with the flag assignment derived from
   the native bank and no free parameters.  The residual assumption is only that
   the microcode's `JMP OPC` consumes that PLA output rather than recomputing
   the condition.  **Re-class: ASSUMPTION → PLA-corroborated, applied at S4r.**
3. **§30's arithmetic is off by one.**  P1 says twelve ROM-constrained, four
   MEASURED-constrained (one of which is unnumbered) and "the remaining twelve
   are free choices"; 12 + 3 numbered + 12 = 27, not 28.  The remaining
   *numbered* set is thirteen (A2, A4, A5, A6, A7, A8, A9, A10, A12, A13, A15,
   A19, A28).  §(c) above re-derives the whole census row by row instead of by
   subtraction.
4. **§59 restates A19 as a different question than §30 booked.**  §30's A19 is
   the repeat-prefix → *data-test polarity* map; §59's "A19 asked what a chain
   carrying two different REP-family prefixes does" is the *precedence*
   question.  Both are now measured-constrained (the polarity map by every REP
   form in `v0.3`; precedence by 2 032 conflicting chains), so the closure
   stands — but the two questions are not the same and the ledger conflates
   them.
5. **§62's narrative split of the unexecuted rows is wrong in both
   directions** (its *block table* in the same section is right).  It names
   `0109`, `0181`, `0219`, `021D` as "four unexercised JMP arms"; all four are
   in fact the row *immediately after an unconditional `CTL FARJMP`* (`0108`,
   `0180`, `0218`, `021C`), which has no delay slot — structurally unreachable,
   no ROM claim, and 10 more rows of that same shape sat unremarked in the
   other bucket.  Conversely its "108 trailing dead rows" bucket — defined as
   "row ≥ 2 with every later row of the same bank also dead" — swallows **five
   rows that do carry a ROM claim**: `006F` (POLL's `JMP INTR`), `0072`/`0073`
   (the withdrawal's `PC-1` and `FLUSH`) and `01DE`/`01DF` (bank A's high-lane
   vector read and AW restore).  The corrected split is the one in §(e):
   **9 substantive rows in two banks (5 + 4, exactly what §49.3 and §62's own
   block table say), 14 post-`FARJMP`, 93 bank tails.**  The totals (912
   executed / 116 unexecuted) are unaffected.
6. **§62's "the fuzz set strictly contains the single-instruction gates' 724"
   compares against the wrong baseline.**  724 is the union over
   `v0.1` + `v0.2` + the specials; §49.3's union over *every* S0-S2 gate
   (including `v0.3` and `v20suite`) is 740.  The S4 re-derivation settles the
   containment against the full 740 and the claim survives: `single − fuzz` is
   **empty** and `fuzz − single` is **172**, so the union is 912 either way
   (`sim/coverage_report.txt`, TOTALS).
7. **`tests/v30/v0.3-f4a-boundary` does not exist as data.**  It is A12's
   recorded falsifier tranche and the directory holds only an `emit_log.txt`
   (§44).  The exposure was extracted from `v0.3` instead.  The stale route is
   still cited in §30/§32; the live artifact is the `--wrap-scan` subset.
8. **`sim/README.md` was stale at S2a** ("As of stage S2a…") while the tree
   carried S3's image runner and 8080 mode.  Refreshed as part of this stage.

### Found while applying the S4r revision

9. **The "2 125 anchored seeds" number spans four banks, F-A only three.**
   §56's own table gives the arch-compared counts as `mc1` 1 072 + `mc2` 1 048 +
   `t30-raw` 3 = **2 123** inside F-A, and `t30-brkem` (which is **F-B**, a
   report and not the gate) contributes the remaining **2**.  Both this document
   and §66 had been quoting "F-A … 2 125/2 125", conflating the gate's three
   banks with the four-bank replay set.  Corrected in both: F-A anchored is
   2 123/2 123, the all-bank anchored subset is 2 125/2 125, and the 284
   failures are counted against F-A's 3 157.
10. **One assumption stood outside the numbering.**  The §25.2 Source2
    `[-00-]` = `ONES` entry was carried as "also standing, unnumbered", which
    made the census non-exhaustive by construction and made "40 standing" an
    undercount of what the model assumes.  **Numbered A43 at S4r** (MEASURED-
    constrained); the census is now 41 numbered with nothing outside it.
11. **Three booked "free choices" were not free, and two were miscategorised.**
    A4, A5 and A6 are each falsified at mass-suite scale as *isolated* changes;
    they are free only under the global index relabellings Σ and Γ defined in
    §(c), which change no predicted bit.  A10 is a set of *values*, not names,
    and every one of them reaches compared state (`ONES -> CS` and
    `ZEROS -> DS/ES/SS/FLAGS/PC` in the ROM's own RESET rows, replayed in all
    3 242 fuzz seeds; `dir*sz` in every string form) — MEASURED-constrained.
    A13 is not an EU semantic at all but a bench convention for absent-memory
    initialisation.  Net effect on the headline: the free-choice count is **6**,
    not 12, and it is smaller because three entries were *stronger* than booked
    and one was out of scope — not because anything was excused.

---

## (h) Gate ledger

Every gate, its number, and the commit that established it.  All gates were
re-verified green immediately before the S4 commit (see §66 of the provenance
ledger).

| stage | gate | number | commit |
|---|---|---|---|
| S0a | `disasm` byte-identical to `docs/V20UC.TXT` | 1028 rows / 257 patterns, empty diff | `840ed97` |
| S0b | pla_3 identification (`sw/pla3_check.py`) | 3 × 256 output vectors bit-exact; 21 checks, 0 contradictions | `dcfdfa7` (+ `ab37957` fixup) |
| S0b | pla_2 identification | 2048/2048 native cells + 2048/2048 8080 cells, unique solution | `dcfdfa7` |
| S1a | bring-up families arch-exact on `v0.2` | 35/35 forms, 35 000/35 000 | `6619417` |
| S1b | flow / internal page / arithmetic groups | 114/114 forms, 114 000/114 000 | `cb0e4d6` |
| S1c | `0F` page; **P1 bring-up gate** | 25/25 forms, 25 000/25 000; whole-suite 336/347 files | `3fd2f63` |
| S2a | **G-A** `v0.1` | 169 000 / 169 000 | `dd21069` |
| S2a | **G-A** `v0.1-w1` / `v0.1-w3` | 1 200 / 1 200 each | `dd21069` |
| S2a | **G-C** specials | 160/160, 128/128, 400/400, 512+154 walk digests | `dd21069` |
| S2b | A12 boundary exposure (extracted) | 8 820 / 8 820, 47 real wraps | `7688919` |
| S2b | INS/EXT `mod != 3` (R8) | 19 914 / 19 914 | `7688919` |
| S2b | **G-B** `v0.3` | 3 699 998 / 3 699 998 | `7688919` |
| S2b | **G-D** `v20suite` (real silicon) | 3 125 000 / 3 125 000 | `7688919` |
| S2b | raw-PSW rollup (`--raw-flags`) | both mass suites 100 % with every mask disabled | `7688919` |
| S3 | **F-A** fuzz banks `mc1`+`mc2`+`t30-raw` | **2 873 / 3 157 seeds as the gate was written**; arch-anchored subset **2 123 / 2 123** within F-A (**2 125 / 2 125** counting the 2 anchored `t30-brkem` seeds of F-B); 0 GEN-DRIFT, 0 arch-only | `1c95689` |
| S3 | F-B `t30-brkem` (report) | 76 / 85 | `1c95689` |
| S3 | F-C interrupt interleaving (report) | 1 075 / 1 165 `evt` seeds; 918 / 953 replayed entries | `1c95689` |
| S3 | every single-instruction gate re-verified after the A37 / `[-06-]` / 8080 mechanism changes | ~7.34 M cases, all green | `1c95689` |
| S4 | micro-row coverage | 912 / 1028, `sim/coverage_report.txt` | this commit |

---

*Campaign closed 2026-08-01; verdict revised at stage S4r the same day against a
review edit list (the revision is recorded in §(g)).  Ledger:
`docs/notes/ucsim_provenance.md`.  Plan as executed:
`docs/notes/ucsim_campaign_plan.md` (verbatim in-repo copy).  Branch `ucsim`,
fully offline, no board time consumed.*
