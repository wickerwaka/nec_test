# ucsim provenance ledger

Every behavior the microcode-driven simulator (`sim/`) implements, tagged with
where it comes from.  This ledger IS the campaign's answer artifact: at S4 the
set of entries still tagged **ASSUMPTION** is precisely "what the microcode
information does not determine".

Provenance classes:

| class | meaning |
|---|---|
| **ROM** | read directly out of `docs/V20BITS.TXT` via the normative decoder `docs/V20UCDIS.PAS` |
| **PLA** | derived from a dumped PLA, as identified in `docs/facts/pla_model.md` |
| **MEASURED** | a law measured on silicon and recorded in `docs/facts/*` or a golden suite |
| **ASSUMPTION** | not determined by the assets; adopted because it reproduces the goldens.  Evidence and falsifier recorded. |

**Campaign CLOSED at S4, 2026-08-01.**  The answer document is
`docs/notes/ucsim_campaign_verdict_2026-08-01.md`; §66 below is this ledger's
closing record (final counts, gate ledger, consolidation findings).  Read the
verdict for the sufficiency answer and this file for the evidence behind every
individual behaviour.

Status of this file at the end of **S2b**: covers every form in
`tests/v30/v0.1`, `tests/v30/v0.2`, `tests/v30/v0.3` (370 forms, 3.7 M cases)
and `tests/v30/v20suite` (360 forms, 3.1 M cases of real µPD70108 silicon) —
the bring-up families, the flow/stack forms, the internal-routine page, the
arithmetic groups, the whole `0F` page, the eleven pin-event pseudo-forms and
the V20's undocumented/alias opcodes.  §29-§32 are the P1 accounting
(provenance census, the assumption list with falsifiers, the `--alu-hw-report`
sufficiency numbers and the residual uncertainties); §33-§42 are S2a; §43-§51
are S2b (gates G-B and G-D, the micro-row coverage report and the raw-PSW
headline); §52-§65 are S3 (the fuzz-bank sequence gauntlet, 8080 mode, the
interrupt interleaving) and §66 is the S4 closure.

---

## 1. Micro-sequencing

### 1.1 Micro-address space and the `loc` counter — **ROM**

The activation patterns are 13 bits `page(3) : opcode(8) : rowgrp(2)`, and each
matched bank holds **four** micro-rows.  So an opcode's microcode is a 16-row
block addressed by a 4-bit counter

```
loc[3:0] = { rowgrp[1:0], row[1:0] }
```

Sequential execution increments `loc` (wrapping into the next row-group), and a
`JMP`'s 4-bit `Loc` field is that same counter.

*Evidence (ROM, unambiguous):* `70..7F` has banks `00?.0111????.00` (rows
0034-0037) and `00?.0111????.01` (rows 0038-003B).  Row 0035 is `JMP OPC 4`;
`loc = 4 = {rowgrp 1, row 0}` = row 0038, which is the taken-branch path
(`SUSP` / `SIGMA -> PC` / `FLUSH`).  The alternative bit order gives a
self-loop.  Cross-checked by `JMP NC 5` at 001B (AAA) reaching 001D, the `E`
row of `00?.0011?111.01`.

Unmapped micro-addresses are executed as no-op rows.

### 1.2 `E` retires the instruction **one row late** — **ROM (structural), MEASURED (gate)**

*This is the single most load-bearing sequencing decision.*  `E` (`Flag_E`,
"end of instruction" per `V20UCDIS.PAS`) marks the row **after which one more
row still executes**.

*Evidence (ROM):* four independent sequences are unintelligible without it —

| opcode | rows | why |
|---|---|---|
| `8D` LEA | `0054` is *empty* + `E`; `0055` is `SIGMA -> R` | the only row that does anything is after `E` |
| `98` CBW | `0060 AX -> tmpbL  E`; `0061 tmpb -> AX` | same |
| `50-57` PUSH | `0029 … MEMW SS  E`; `002A M -> OPR` | the write data is produced after `E` |
| `04/05` ALU acc,imm | `0006  E  ALU OPC tmpa`; `0007 SIGMA -> M  W` | the result and the flag write are after `E` |
| `A2/A3` MOV dmem,acc | `008A … MEMW  E`; `008B M -> OPR` | same as PUSH |

*Falsifier, run:* retiring at the `E` row instead makes `40` 0/1000, `04`
0/1000, `50` 18/1000 and `A2` 26/1000 (negative control, 2026-08-01).  With the
delay row all four are 1000/1000.

`JMP` has **no** delay slot: `JMP OP8 2` at `0100` (C6/C7) must not execute
`0101` (`Q -> tmpbH`), or the immediate length would be wrong.  ROM-forced.

### 1.3 `FARJMP` target — **ROM**

`CTL` with `Int == 0x0E` jumps to page 7, opcode byte `far_loc << 3`, `loc = 0`
— exactly the addressing the range printer in `V20UCDIS.PAS` uses to name the
internal routines (`A.Cmp shr 5 and 31`).

---

## 2. Unknown #1 — the ALU-latch / SIGMA / `W` row-relative timing — **RESOLVED**

**Model.** The `ALU` row's `Op`/`Tmp` fields *latch* an operation.  `SIGMA` is
the **combinational** output of the latched operation evaluated on the tmp
registers **as they stand at the start of the row that reads it**.  The
operation named by a row therefore takes effect from the *following* row.  `W`
commits the flag outputs of that same (old-latch) evaluation.  `CTL` and `JMP`
rows leave the latch untouched.

*Evidence (ROM), `8F` POP mem, rows 0058-005B:*

```
0058 SIGMA -> tmpa                     ALU INC2 tmpb
0059 SP -> IND   SP -> tmpb            CTL      MEMR SS
005A SIGMA -> SP                    F  ALU PASS tmpa
005B SIGMA -> IND                   E  CTL      [-06-]
```

* Row 0058 reads `SIGMA` while `tmpb` is still unloaded — so `SIGMA` there
  cannot be this row's `INC2 tmpb`; it is the *pre-decode* value (§4).
* Row 005A's `SIGMA -> SP` must be `SP+2`, i.e. `INC2 tmpb` latched at 0058 and
  evaluated on the `tmpb` **written by row 0059** — so the evaluation is
  combinational on current tmps, not a value captured when the op was latched.
* Row 005B's `SIGMA -> IND` must be the EA, i.e. `PASS tmpa` latched at 005A.

*Cross-check that `W` uses the old latch:* `84/85` TEST is
`0044 M->tmpa R->tmpb E ALU AND tmpa` / `0045 SIGMA -> NULL W` — the only
possible flag source at 0045 is the AND latched at 0044.  Also `37` AAA row
001A carries `W` **and** an `ALU INC tmpb` field; if `W` used the new latch the
flags would come from an operation whose operand is not yet loaded.

*Status:* MEASURED-consistent — 35/35 bring-up families 1000/1000, plus 113
further v0.2 forms green with no per-opcode tuning.

### 2.1 ALU operand ports — **ASSUMPTION (ROM-constrained)**

Binary ops compute **`tmpb` OP `tmp[Tmp]`**; unary ops operate on `tmp[Tmp]`.

*Evidence:* `SUB`/`CMP` are non-commutative and pin the order.  ALU rm,r
(`0000`) loads `M -> tmpb`, `R -> tmpa` and computes `OPC tmpa`; for `28`
(SUB rm,r) the answer must be `rm - r` = `tmpb - tmpa`; with the direction bit
set (`2A`, SUB r,rm) the hardware swap (§3.2) makes `tmpb = reg`, `tmpa = rm`
and the *same* `tmpb - tmpa` is again correct.  ALU acc,imm (`0004`) loads
`M -> tmpb` (acc), `Q -> tmpa` (imm) and the same expression holds.  The
non-`tmpa` case is fixed by `008C` (`dir*sz -> tmpc`, `SI -> tmpb`,
`ALU ADD tmpc`) which must be `SI + dir*sz`, i.e. `tmpb + tmp[Tmp]`.
*Falsifier:* any binary row with `Tmp = tmpb` and a non-commutative op would
disambiguate further; none is reachable from the bring-up families.

### 2.2 `OPC` selection rule — **ASSUMPTION (PLA-corroborated)** — *superseded by §11*

```
sel = (opc_reg >> 3) & 7
OPC = incdec_class ? (INC + (sel & 1)) : sel
```

`kStrOp[0..7]` is literally `ADD OR ADC SBB AND SUB XOR CMP`, which is the x86
`op` field, so for `00-3F` and for `04/05`-style acc,imm forms `sel` is a
direct read of opcode bits 5:3.  `Source1` code `0x16` is *named* `opc&38` in
`V20UCDIS.PAS`, which is that field being routed out of the opcode register —
independent ROM corroboration that bits 5:3 of the opcode register are the ALU
op select.

`incdec_class` is the INC/DEC remap (`sel 0 -> INC`, `1 -> DEC`).  It is
asserted for `40-4F` (pla_3 `XOP = 1100`, "increment/decrement") and for the
whole `FE/FF` page (page 3, where `opc_reg` holds the ModR/M byte so `sel` is
the `reg` field: 0 = INC, 1 = DEC).  Note pla_3's `INCDEC_NO_CY` (b9) also
covers `F6/F7` through term merging, so b9 alone is **not** used as the class
signal (`NEG` on that page does write CY).

`80-83` need `sel` from the ModR/M `reg` field instead; implemented for
`XOP = 0100` ("multiply / ALU-immediate group") — **untested at S1a**, `80.0`
and `81.0` pass but `80.1`-`80.7` do not yet (they fail for other reasons, see
§8), so this rule is **OPEN for S1b**.

### 2.3 `CMP` does not drive the result bus — **MEASURED**

Block `00?.00???0??.00` serves *all* of `00-3B`, including `38-3B` (CMP), and
its row 0001 is `SIGMA -> M  WE  CTL [-06-]`.  The goldens say CMP writes
nothing: `39` mod==3 cases leave the destination register untouched, `3C`
touches only `ip`/`flags`, and **no** `38` case in the golden cycle traces
contains a `MEMW` (0 of 200 sampled).

*Implementation:* `AluResult::commits = false` for `CMP`; any transfer whose
source is `SIGMA` is skipped, and the `[-06-]` strobe on the same row is
suppressed with it.  *Falsifier:* a form where CMP's result must reach a
destination.  None exists.

### 2.4 Flag semantics — **MEASURED / documented**

* PSW layout `CY(0) -(1)=1 P(2) -(3)=0 AC(4) -(5)=0 Z(6) S(7) BRK(8) IE(9)
  DIR(10) V(11) 15:12=1`; writable mask `0x0FD5`, forced `0xF002`.  Confirmed
  against every `flags` field in the v0.2 goldens.
* `INC`/`DEC` (and `INC2`/`DEC2`) **do not write CY**; everything else in their
  arithmetic mask does.  Corroborated by pla_3 b9 `INCDEC_NO_CY`.
* `AND/OR/XOR` clear CY, V and AC (AC "always 0" — MEASURED,
  `docs/facts/undefined_flags.md`).
* `NOT` writes no flags; `NEG` writes the full arithmetic set with
  `V = (operand == MSB)`, `CY = (result != 0)`.
* `PASS` **does** write the full arithmetic set, with `CY = AC = V = 0` — see
  §17.1.  (S1a had it flagless; no bring-up form carried `W` over a `PASS`
  latch, the arithmetic groups do.)
* `INC2`/`DEC2` are the address adder's ±2 and are **always 16-bit**, never
  byte-width, regardless of the instruction's operand width.  ASSUMPTION;
  falsifier = a byte-width instruction that also does stack arithmetic
  (`FE`-page PUSH/CALL forms would show it; `FF.6`/`FF.2` pass).

### 2.5 ALU width: the datapath is 16 bits, `byte` only moves the flag taps — **MEASURED**

The operand width does **not** narrow the ALU.  The result is computed on the
full 16-bit tmp registers; the width only selects where CY/S/Z/AC/V are tapped.

*Evidence (MEASURED):* the string block `008C-008F` is shared by `A4` (MOVBK
**byte**) and `A5` (word) and advances SI/DI through the same ALU
(`dir*sz -> tmpc`, `SI -> tmpb`, `ALU ADD tmpc`, `SIGMA -> SI`).  A byte-wide
ALU zeroes the pointer's high half: `A4` idx 0 gave `si exp=312B got=002B`,
`di exp=C226 got=0026`.  With the 16-bit datapath `A4 AA AC AE 26.A4 3E.AC`
all become 1000/1000 and no previously green form regresses.

### 2.6 `-> tmpaL` / `-> tmpbL` SIGN-EXTEND into the high half — **MEASURED** — *refined at §20: only `tmpbL` sign-extends*

Writing a byte through `Dest1` codes `0x14`/`0x15` (`tmpaL`/`tmpbL`) sets the
matching high half to the sign of that byte.

*Evidence (MEASURED):* the `70-7F` Jcc block is
`0034 Q -> tmpbL  ALU ADD tmpa` / `0038 PC -> tmpa` / `0039 SIGMA -> PC`, and
the ROM contains **no** sign-extension row.  With zero-extension every
backward branch landed exactly `0x100` high (`74` idx 1: `ip exp=7D37
got=7E37`).  Sign-extending the L-half write makes the whole `70-7F` block,
`EB`, `98` and `26.A4` green (18 + 3 forms) and regresses nothing — the other
users of `-> tmpbL` (`B0-B7`, `C6`, `80/82`) only ever read the low half back.
*Open:* whether the sign extension is unconditional or gated by a decode
signal cannot be settled from the forms available at S1a; `83` (§3.4) is the
place it will be decided.

---

## 3. The loader → microcode entry contract

### 3.1 What is latched before micro-row 0 — **ASSUMPTION (goldens)**

At row 0 of every instruction the pre-decode hardware has already:

1. consumed all prefixes and latched segment-override / REP / BUSLOCK, with
   `PFXCNT` counting them;
2. consumed the opcode byte into the **opcode register** `opc_reg` (the source
   of `OPC` and `opc&38`) and advanced `PC` past it;
3. consumed the ModR/M byte and its displacement when `pla_3` says
   `HAS_MODRM`;
4. computed the effective address, written it to **`IND`**, and left the
   address adder's output standing on the **SIGMA** path (§4);
5. bound the **`M`** and **`R`** operand references (§3.2);
6. performed the operand **pre-read** into `OPR` (§5);
7. selected the microcode page.

`IND` being pre-loaded is ROM-forced: ALU rm,r writes memory through
`[-06-]` at row 0001 and *no row of that block ever writes IND*.

### 3.2 `M` / `R` binding and the direction swap — **PLA + ASSUMPTION**

* `HAS_MODRM` (pla_3 b5): `R` = the `reg`-field operand (a segment register
  when `SREG_MOV` b4 is set, else a GPR at the operand width), `M` = the `r/m`
  operand (register when `mod == 3`, else memory).
* `DIR_FROM_BIT1` (pla_3 b7) **and** opcode bit 1 set ⇒ **`M` and `R` are
  exchanged**.  This is what lets one 2-row block (`004C/004D`) serve all of
  `88-8B`, and one 2-row block (`0000/0001`) serve both directions of every ALU
  form.  *Falsifier:* `8A/8B` would write the wrong operand; they are
  1000/1000.
* `ACC_W_OPERAND` (pla_3 b3): `M` = `AL` (byte) / `AW` (word).
* No ModR/M, opcode `< 0x40` with low 3 bits ≥ 6 (`06/0E/16/1E`,
  `07/17/1F`): `R` = segment register `(opcode >> 3) & 3`.  **ASSUMPTION** —
  pla_3 gives `06/0E/16/1E` an all-zero vector and only tags the POP forms
  (`XOP = 0001`, "segment-register operand"), so the PUSH half is not covered
  by any dumped asset.
* Otherwise `M` = GPR `opcode & 7` at the operand width (`40-5F`, `90-97`,
  `B0-BF`).  **ASSUMPTION**, same reason.

Operand width: `BYTE_ONLY` (b0) ⇒ byte; else `W_FROM_BIT0` (b1) ⇒ opcode bit 0;
else word.  (PLA.)  This reproduces `B0-B7` byte / `B8-BF` word, `8C/8E` word,
`50-5F` word with no per-opcode table.

### 3.3 Page selection — **ROM + PLA**

`page = 0` native, `1` when a REP prefix is latched (the ROM's `00?` patterns
match both, so only the string ops actually split), `4` for the `0F` page with
the second byte in the opcode slot, and for `XOP = 1011` ("second-byte group
dispatch"): `page = 2` for `F6/F7`, `page = 3` for `FE/FF`, selected by opcode
bit 3, with the **ModR/M byte moved into the opcode slot**.  ROM-forced by the
`<F6/F7>` / `<FE/FF>` activation patterns, whose opcode field is manifestly a
ModR/M byte (`??00????` = `reg` field 0/1 = INC/DEC).

### 3.4 `JMP OP8` — **ASSUMPTION** — *resolved at §10*

`OP8` is taken as "the operand/immediate is 8 bits" = the operand width
computed in §3.2.  It gates the high-immediate-byte fetch in `04/05`,
`B0-BF` and `C6/C7` (all 1000/1000).  **Known incomplete:** `83`
(ALU rm16,imm8) must take the same jump — its immediate is one byte — but its
operand width is *word*, so the width-derived `OP8` does not fire and the
simulator consumes an extra immediate byte (`83.0` idx 0: `ip exp=7509
got=750A`).  §2.6 already supplies the sign extension `83` needs, so the
remaining question is purely the condition: `OP8` is probably "the immediate
is 8 bits" while the unexplained second condition `OP8b` (`Str_Cond[4]`,
never used by a bring-up form) is the operand-width one.  Handed to **S1b**.

---

## 4. EA-in-SIGMA at micro-row 0 — **ROM**

The address adder's output is on the SIGMA path when microcode starts.

* `8D` LEA: the entire instruction is `0055 SIGMA -> R`.  Nothing else could
  produce the EA.
* `8F` POP mem: `0058 SIGMA -> tmpa` saves it before the stack read clobbers
  `IND`, and `005B SIGMA -> IND` (via `PASS tmpa`) restores it for the
  write-back.

Modelled as a synthetic latch state (`AluLatch::ea_const`).  For `mod == 3` the
loader leaves the latch **untouched**, so a stale value from the previous
instruction stands — the documented LEA stale-EA residue
(`tests/v30/mod3_illegal`).  Confirming that residue is an **S2** item.

---

## 5. Unknown #4 — operand pre-read vs. first M access — **RESOLVED (PLA)**

The pre-decode hardware performs the operand read **before micro-row 0** and
`M`/`R` as a *source* returns `OPR`.  The gate is pla_3 `MODRM_STORE` (b6):
when set, the r/m operand is written without being read and there is **no**
pre-read.

*Evidence:* the ALU rm,r block reads `M -> tmpb` with **no `MEMR` anywhere in
the block** — the read must already have happened.  `MODRM_STORE`'s membership
(`88 89 8C 8F C6 C7` + `8D`) is exactly the set of ModR/M forms whose blocks
contain no read: `88/89` (`004C/004D`), `8C` (`0050`), `C6/C7` (`0100-0102`),
`8D` (`0054/0055`), and `8F`, whose only `MEMR` is the *stack* read.
This retires the medium-confidence naming question in `pla_model.md` §b6 in
favour of the "the standard operand-fetch step is skipped" reading.
**Refined at S1c (§23.3): the suppression is NATIVE-decode-mode only** — pla_3
asserts b6 for the `0F 28-2F` and `0F 30-3F` blocks too, and those DO read
their r/m operand.

Direction-swapped forms are handled by pre-reading whichever of `M`/`R` is the
memory operand (pla_3's b6 is already per-opcode, so `8A/8B`, `02/03`, `8E`
correctly pre-read).

---

## 6. Unknown #3 — the `[-06-]` external-control code — **RESOLVED**

`Ext == 6` is the **operand write-back strobe**: it commits `OPR` to the r/m
operand, and it does so **only when that operand is memory**.  A register r/m
is written by the row's own `-> M` transfer; the strobe does nothing.

*Evidence — the `8F` mod==3 ghost (MEASURED).*  `8F` with `mod == 3` (`POP
mem` onto a register) has **no `-> M` transfer anywhere in its block**; the
popped word reaches memory purely through `[-06-]` at row 005B.  The goldens
say the register is **not** written: `8F C4` ("pop mem sp") changes only
`sp += 2` and `ip`, `8F C5` leaves `BP` untouched, and `final.ram` is empty
(263 mod-3 cases in `tests/v30/v0.2/8F.0.json.gz`, all consistent).
*Falsifier, run:* making `[-06-]` also commit to registers gives `8F.0`
"sp exp=7CAF got=84A9", and breaks `88` (734/1000), `00` (765/1000) and `8C`
(734/1000) as well, because their `-> M` write would be applied twice from a
stale `OPR`.

Where the strobe appears is exactly where `M` *can* be memory — `0001`
(ALU rm,r), `004D` (MOV 88-8B), `0050` (MOV 8C/8E), `0049` (XCHG 86/87),
`0102` (C6/C7), `005B` (POP mem), `01B9` (FE/FF INC/DEC) — and never on a row
whose `M` is structurally a register (`002F`, `00E2`, `0087`, `005D`).

### 6.1 Posted writes: the data phase samples `OPR` one row later — **ROM** — *superseded by §18.2 (write-data pairing); PUSHA falsifies the fixed one-row model*

A `MEMW` (or `[-06-]`) row supplies only the *address*; the data is taken from
`OPR` one micro-row later.  ROM-forced by three blocks:

| block | address row | data row |
|---|---|---|
| `50-57` PUSH | `0029 SIGMA -> IND … MEMW SS` | `002A M -> OPR` |
| `A2/A3` MOV dmem,acc | `008A tmpb -> IND … MEMW` | `008B M -> OPR` |
| `86/87` XCHG | `0049 tmpa -> R  E  [-06-]` | `004A tmpb -> M` |

XCHG is decisive: the value the strobe must write is produced on the row
*after* the strobe.  Implemented as a one-row-aged posted write, flushed at
instruction end.

---

## 7. Unknown #7 — the blank `SR` field = operand default segment — **RESOLVED**

`Str_SR` is `ES / IO / SS / (blank)`.  Blank resolves to **the operand's own
effective segment**: the ModR/M memory operand's segment when there is one
(SS when the addressing form uses BP as base, else DS — the `pla_4` fit in
`docs/facts/pla_model.md`), otherwise the segment-override latch, otherwise DS.

*Evidence:* `A0-A3` (MOV acc,dmem / dmem,acc) issue `CTL MEMR` / `CTL MEMW`
with a blank SR and must use DS (or the override) — `26.8B`/`2E.8B`/`36.8B`/
`3E.8B` and `A0-A3` are all 1000/1000.  `[-06-]` rows likewise carry a blank
SR and must hit the operand's segment.  `MEMW ES` in the string block and
`MEMR/MEMW SS` in every stack block are the explicit, non-overridable cases.

Additional rule (**ASSUMPTION**): `SR == SS` accesses are word-wide regardless
of the instruction's operand width.  No bring-up form distinguishes it; the
falsifier is a byte-width instruction whose microcode touches the stack.

---

## 8. Other decisions made at S1a

| decision | class | note |
|---|---|---|
| `M`/`R` as a source when the operand is memory returns `OPR` | ASSUMPTION | the pre-read staging register; `-> M` on a memory operand stages into `OPR` for the strobe |
| Prefix set and 1BL op table come from pla_3 `is_prefix` / `Bl1Op` | PLA | gives `0F` and the undocumented `F1` for free; `F8-FD`,`F5`,`F4` execute in the loader with **no microcode**, which is why they have no ROM bank |
| ONE_BYTE_LOGIC flag ops (`F5 F8 F9 FA FB FC FD`) | PLA | all 1000/1000 |
| segment-prefix decode `26/2E/36/3E -> (b>>3)&3` | ASSUMPTION | matches the ES/CS/SS/DS index order the ROM's `Source1` field uses |
| `PC` is the **microcode-visible** PC = address of the next unconsumed byte; the BIU keeps a separate fetch pointer | ASSUMPTION | required by the Jcc block (`0038 PC -> tmpa` after `SUSP`, then `ADD` of the displacement).  Retirement `IP` = this PC.  All branch forms (`70-7F`, `E8`, `E9`, `EA`, `EB`, `C2`, `C3`) that are green confirm it |
| `Q` source pops one queue byte and advances PC | ROM | the same path the loader uses |
| `ONES` = `0xFFFF`, `ZEROS` = 0, `dir*sz` = ±1/±2 from DIR and the operand width | ASSUMPTION | names from `V20UCDIS.PAS`; `dir*sz` confirmed by the string block `008C` |
| `AL:AH` (Source1 `0x10`) = byte-swapped AW | ASSUMPTION | required by AAA/AAS (`001B AL:AH -> tmpb`, then `SIGMA -> AH`); **not yet gated** (`37`/`3F` still fail) |
| word memory accesses wrap the **offset** at 16 bits inside the segment | ASSUMPTION | falsifier = `tests/v30/v0.3-f4a-boundary` (S2) |
| unlisted memory reads as `0x00` | ASSUMPTION | suite artifact management; no bring-up case depends on it |
| final **queue** comparison is DEFERRED | policy | the functional model fetches on demand and keeps no speculative queue, so `final.queue` is not reproducible without the timing model.  Registers (incl. raw PSW) and RAM are compared; queue is an S2/timing item |
| `F` (`Flag_F`) is a **bus interlock**, not a flag control (made concrete at §18.1: it is what delivers read data into OPR) | ASSUMPTION | it appears on rows that consume `OPR` after a `MEMR` (`000B`, `002F`, `0087`) and on `005A`, one row before the `[-06-]` that needs the read data — never on a row that computes flags.  `V20UCDIS.PAS` documents `Flag_W` as "write flags" and leaves `Flag_F` uncommented.  Modelled as an instantly-satisfied sync object (call site preserved for the timing campaign) |
| `SUSP` = logged no-op; `FLUSH` = clear queue, refetch from CS:PC | ASSUMPTION | standard BIU semantics; validated indirectly by the green branch forms |

### S0a ambiguous address — *analysed at §21.1*

`v30sim info` reports **1 ambiguous micro-address of 8192**: two activation
patterns both match `111.00000010.00` (the two `<internal> 02` banks at
disassembly lines 596 and 601).  The decode table keeps **first match wins**.
No bring-up family reaches page 7, so the choice is currently untested; it is
carried forward as an open item for whichever internal routine dispatches
there.

---

## 9. S1a result

Gate: bring-up families **arch-exact** (registers incl. raw PSW + RAM) on their
full v0.2 tranches, 1000 cases each.

| family | forms | result |
|---|---|---|
| MOV | `88 89 8A 8B B0 B8 C6.0 C7.0 A0 A1 A2 A3` | 12 × 1000/1000 |
| ALU rm,r / acc,imm | `00 01 02 03 04 05 30 31 38 39 3C` | 11 × 1000/1000 |
| INC/DEC | `40 48 FE.0` | 3 × 1000/1000 |
| PUSH/POP | `50 58 8F.0 06 0E 1E 07 17 1F` | 9 × 1000/1000 |

**35 / 35 forms, 35000 / 35000 cases.**

Whole-suite survey at the same commit (no per-family tuning): **172 of 351
v0.2 forms fully green, 179 475 of 347 000 cases passing.**  Everything still
failing is a feature the S1a core does not implement yet — shifts/rotates
(`C0/C1/D0-D3`), MUL/DIV and the rest of the `F6/F7` page, the `0F` page, the
internal-routine page (`CALLF`/`RETF`/`INT`/`ENTER`/`PUSHA`/`POPA`), REP
string loops, the BCD adjust group, LOOP (`E0-E2`), IN/OUT (`E4/E5/EC/ED`) and
the interrupt/pin pseudo-forms.

Negative controls run at S1a (each restores to 1000/1000 when reverted):

| control | effect |
|---|---|
| retire at the `E` row instead of one row later | `40` 0/1000, `04` 0/1000, `50` 18/1000, `A2` 26/1000 |
| let `[-06-]` commit `OPR` to a register r/m | `8F.0` fails the mod-3 ghost, `88` 734/1000, `00` 765/1000, `8C` 734/1000 |
| byte-wide ALU datapath | `A4`/`AA`/`AC`/`AE` zero the SI/DI high half |
| zero-extending `-> tmpbL` | every backward `70-7F`/`EB` branch off by `0x100` |

---

# S1b — flow, the internal-routine page, and the arithmetic groups

Everything below was resolved at S1b.  Every entry that changes an S1a
decision says so explicitly.  Every negative control listed was actually run
and restores to 1000/1000 when reverted (§18).

## 10. The two "immediate width" conditions — **RESOLVED**

`OP8` (`Str_Cond[7]`) means **"the immediate operand is one byte"**.
`OP8b` (`Str_Cond[4]`) means **"the operand is byte-wide"**.  S1a had both
bound to the operand width, which is why `83` failed.

*Evidence (ROM, decisive):* `0290` (`69`/`6B`, MUL rm16,imm) is
`Q -> tmpbL  JMP OP8 2` — the high immediate byte is skipped for `6B` and
fetched for `69`, yet **both are word-operand** forms.  Symmetrically `003C`
(`80`-`83`) skips the high byte for `83`, a word-operand form.  Meanwhile the
*same* internal IMUL block reached from `69`/`6B` uses `OP8b` at `020F` to
choose `COUNT = 8` vs `16`, and there it must read **word** for `6B`.  One
condition cannot be both, so the two are distinct signals.

Wherever an opcode has no immediate (`F6`/`F7` MUL/DIV, the internal IMUL /
IDIV2 tails) the two coincide, which is why `JMP OP8` is used there too.

*Implementation:* the loader computes `imm8 = byte_operand || opcode in
{0x83, 0x6B}` — **ASSUMPTION** for the membership of that two-opcode set: no
dumped PLA column separates it (pla_3 gives `80`-`87` a single shared vector,
and `69`/`6B` sit in `XOP = 0100` together).
*Negative control, run:* `OP8 = operand width` → `83.0` 0/1000, `6B` 0/1000,
`69` and `80.0` unaffected.

## 11. `OPC` select: field source and op block — **RESOLVED (ROM-forced)**

`OPC` resolves to `opc_base + sel`:

| class | `opc_base` | members | kStrOp block |
|---|---|---|---|
| ALU | `0x00` | `00-3F`, `04/05`-style, `80-83` | ADD OR ADC SBB AND SUB XOR CMP |
| shift | `0x08` | `C0 C1 D0 D1 D2 D3` | ROL ROR RCL RCR SHL SHR [-0E-] SAR |
| unary | `0x18` | `40-4F`, page 2 (`F6/F7`), page 3 (`FE/FF`) | INC DEC NOT NEG |

and `sel` is opcode bits 5:3 **except** for the ModR/M *group* opcodes
(`80-83`, `C0 C1`, `D0-D3`, and pages 2/3 where the ModR/M byte already
occupies the opcode slot), where it is the ModR/M `reg` field.

*Evidence:* page 2's two OPC blocks are `010.??010???` (reg = 2) and
`010.??011???` (reg = 3), which must be NOT and NEG — `0x18 + 2` and
`0x18 + 3` in `kStrOp`.  This retires S1a §2.4's `incdec_class` remap
(`kInc + (sel & 1)`), which could not reach NOT/NEG.  The shift block is
forced by `D0-D3`'s eight sub-forms mapping onto `kStrOp[8..15]`.
*Negative control, run:* `sel` from opcode bits 5:3 everywhere → `80.1`
98/1000, `81.5` 1/1000, `D2.4` 64/1000.

`kStrOp[0x0E]` (`[-0E-]`, group `/6`) is a **second SHL encoding** — the
suite names those forms `shl6`, and SHL semantics make all six `.6` forms
1000/1000.  **MEASURED.**

## 12. The `R` loop — **RESOLVED** (unknown #2)

**Model.**  An `R` row latches its own operation and then runs it **COUNT
times inside that row**, writing the row's `Dest1` (always `tmpb` in this ROM)
and, if `W`, the flags on *every* iteration.  COUNT ends at 0.  The row's
`Source1 = SIGMA` transfer is the loop, not a separate old-latch evaluation:
the delay-slot rule of §2 does **not** apply to an `R` row.

Afterwards the iterative unit has no count left, so a later row that reads
`SIGMA` with the same operation still latched gets a **pass-through of port A**
(`tmpb`) rather than one more step.

*Evidence (ROM):*
* `0114-0117` (`D0/D1`, shift by 1) is `CONST -> COUNT 1` / `M -> tmpb` /
  `SIGMA -> tmpb W R ALU OPC tmpb` / `SIGMA -> M E [-06-]`.  Exactly **one**
  shift must happen and its flags must be written.  Only "the R row does the
  shift, and `0117`'s read is a pass-through" produces that.
* `0178-017F` (`F6/F7` MULU) initialises `tmpb` to `ZEROS` on `0178` and the
  R row `017C` must start the shift-add from that zero.  If the R row first
  executed the old latch (`PASS tmpc`) it would overwrite the accumulator with
  the multiplicand.
* `0190/0191` and `011F/0120` (DIV, AAM) re-latch `DIV` on the row after the
  loop and read `SIGMA` there; with COUNT exhausted that read must not disturb
  the quotient/remainder.

This settles Codex's alternative in favour of the **internal iterative phase**
reading: the iteration completes within the R row with registered feedback;
it is not a per-row re-evaluation.
*Negative controls, run:* R row executes the old latch first → `F6.4` 11/1000,
`F7.4` 4/1000, `F6.6`/`F7.6` 527/1000, `D4` 0/1000.  Iterative op re-steps on
the post-loop `SIGMA` read → `D0.4` 17/1000, `D1.5` 6/1000, `D2.4` 670/1000,
`C0.4` 795/1000, `F6.6` 538/1000.

**COUNT is not masked.**  `0119` (`CX -> tmpaL`) loads the raw CL and the
microcode never reduces it; 426 of the 1000 `D2.4` cases have `CL >= 32` and
all pass.  So the V30 shifts the full 0..255 count.

## 13. `CNTZ` is a loop-continue, not a zero test — **RESOLVED**

`JMP CNTZ` **decrements COUNT and jumps while it is still non-zero**.

*Evidence:* ENTER's copy walk is `026A..026E` with `026E JMP CNTZ 6`
(back to `026A`) and `0269 SIGMA -> COUNT` loading `level - 1`.  The
architectural walk copies `level - 1` frame words, which is exactly
"decrement, jump if non-zero"; "jump if zero" gives one copy for every level.
*Negative control, run:* `CNTZ = (COUNT == 0)` → `C8` 647/1000, with the
missing copy visible as `sp` off by 2 per level.

`REP` (`Str_Cond[12]`) has the same decrement plus a data test, see §15.

## 14. Microcode JMP conditions: three different taps — **RESOLVED**

The 16-entry `Str_Cond` table does **not** read one register.  Three sources
are needed, and each is forced by a different block:

| condition | source |
|---|---|
| `[-00-]`(0)=C, `NC`(1), `Z`(2), `NZ`(3), `L`(6) | the **ALU status latch** |
| `O`(10), `OPC`(15) | the architectural **PSW** |
| `NS`(11) | the **sign of `tmpb`** at the operand width |
| `CNTZ`(5), `REP`(12) | COUNT (§13, §15) |
| `OP8`(7), `OP8b`(4) | pre-decode (§10) |
| `[-09-]`(9) | the MUL/DIV sign latch (§16) |
| `BUSY`(13), `INTR`(14) | pins — always false in the functional model |

### 14.1 The ALU status latch loads when SIGMA is gated onto the bus

**ASSUMPTION (ROM-constrained).**  A separate status register is loaded from
the ALU's flag outputs on every row whose `Source1` or `Source2` is `SIGMA`
— i.e. when the result is actually driven.  `W` is what copies those same
outputs into the PSW; the two are independent.

*Evidence:* four blocks branch on `Z` with **no `W` anywhere before the
branch**, so the PSW cannot be the source —
`0141 SIGMA -> NULL` / `0142 JMP Z 5` (`E3` JCXZ, Z = CX==0),
`0095 SIGMA -> NULL` / `0096 JMP Z 7` (REP entry, Z = CX==0),
`0221 SIGMA -> [-03-]` / `0222 JMP Z 4` (REPX),
`011A SIGMA -> [-03-]` / … / `0228 JMP Z 3` (SHIFT, Z = shift count == 0).
The SHIFT case also fixes *when* the latch loads: row `011B` (`CTL FARJMP`)
sits between the two and must **not** disturb it, and `011B` is precisely a
row that does not read SIGMA.
*Negative control, run:* conditions read the PSW → `E2` 519/1000, `E3`
511/1000, `D2.4` 499/1000, `C8` 411/1000, `F3A4` 505/1000.

`[-00-]` (condition 0) is the **carry-set** partner of `NC`: IDIV2's
`01A8 JMP [-00-] 2` must take the divide-error exit when the magnitude
pre-check `SUB` at `01A6/01A7` produced **no** borrow.  ROM-forced.

### 14.2 `NS` is a direct sign tap on `tmpb`

**ASSUMPTION (ROM-constrained), three independent confirmations:**
* `99` CWD: `0064 ZEROS -> DX  AX -> tmpb  CTL` / `0065 JMP NS 3`.  Row `0064`
  is a CTL row that names no ALU operation and reads no SIGMA, so nothing but
  a direct tap on the just-loaded `tmpb` can give sign(AW).
* `01A1 tmpb -> OPR  JMP NS 6` (IDIV) must branch on the sign of the dividend
  **high half**, which is what `019B`/`019D` put in `tmpb`; the latched ALU
  operation at that row is `NEG tmpa`.
* `01B2 JMP NS 12` (IDIV2) must branch on the sign of the original dividend,
  which `01AD` restored into `tmpb` from OPR.

The width follows the operand width, which is what makes byte IDIV work:
`AL:AH -> tmpb` puts AH in the low byte, and the byte-width sign tap is
AH bit 7 = sign(AW).
*Negative control, run:* `NS` from the ALU status sign → `99` 506/1000,
`F6.7` 472/1000, `F7.7` 461/1000.

### 14.3 `O` reads the PSW

`010C CONST -> tmpbL 4  JMP O 3` (`CE` INTO) is the only user, and it must
test the architectural overflow flag left by an earlier instruction.  The
status latch holds nothing at that point.  **ROM-forced.**

## 15. `REP` — the string / loop continuation test — **RESOLVED**

`JMP REP` decrements COUNT and jumps when the result is non-zero **and** the
data test passes.  The data test is selected by pla_3's `XOP = 1110`
("count / compare-and-loop" — `A6 A7 AE AF C0 C1 E0 E1`), which is exactly the
set of opcodes for which the continuation is flag-sensitive:

* `E0`/`E1` (LOOPNE/LOOPE): test Z, polarity = opcode bit 0.
* `A6 A7 AE AF` under a repeat prefix: test Z for `REPE`/`REPNE`, CY for the
  V30's `REPC`/`REPNC` (`65`/`64`).
* everything else (MOVBK, STM, LDM, INM, OUTM): no data test.

**PLA + ASSUMPTION** (the prefix → polarity mapping is not in a dump).
`C0`/`C1` also carry `XOP = 1110` and never execute a `JMP REP`, so the
merge is harmless.

The interrupt term of the real condition (`REP` also fails when an interrupt
is pending, which is what makes REPX's `0223 JMP INTR 5` back the PC up over
the prefixes) is modelled as permanently false — no pin events at S1b.

## 16. Signed MUL / DIV: `[-1E-]`, `[-0C-]`, `[-09-]` — **RESOLVED**

* `[-1E-]` (`Str_Op[0x1E]`) is **ABS**: it drives |port B| at the operand
  width.  *Evidence:* `0184` (`F6.5`/`F7.5`) and `0198` (`F6.7`/`F7.7`) latch
  it over AW and over the divisor respectively, and the following
  `SIGMA -> tmpa` / `SIGMA -> tmpc` rows feed the *unsigned* shift-add and
  restoring-division loops.
* The row that **latches** `[-1E-]` also loads the sign latch from the sign of
  `tmp[Tmp]` as it stands at the end of that row.
* `CTL [-0C-]` (`Str_Int[12]`) **toggles** the sign latch by the sign of
  `tmpb`.  It appears exactly twice — `020C` (IMUL/IMULI entry, where `tmpb`
  has just received the *other* factor) and `019E` (IDIV, where `tmpb` holds
  the dividend high half) — i.e. exactly where the second operand's sign has
  to be folded in.
* `[-09-]` (`Str_Cond[9]`) is **"the result sign is positive"** = sign latch
  clear.  `0212 JMP [-09-] 12` skips the product negation; `01AF JMP [-09-] 9`
  skips the quotient negation.

All three are **ASSUMPTION (ROM-constrained)**; the assets name none of them.
*Negative control, run:* `[-1E-]` as a plain PASS and `[-0C-]` as a no-op →
`F6.5` 523/1000, `F7.5` 542/1000, `69` 511/1000, `6B` 481/1000, `F6.7`
885/1000, `F7.7` 871/1000.

`CTL [-06-]` (`Str_Int[6]`) **clears CY and V**, `CTL [-07-]` (`Str_Int[7]`)
**sets** them.  Forced by MULX (`0208 [-06-]` / `0209 JMP Z 3` /
`020A [-07-]`), the two-row overflow decision shared by MULU and IMUL.
*Negative control, run:* both as no-ops → `F6.4` 263/1000, `F7.4` 248/1000,
`F6.5` 280/1000, `F7.5` 273/1000, `69` 244/1000, `6B` 243/1000.
Note the field collision: this is the **Int** code 6, not the `[-06-]`
write-back strobe of §6, which is the **Ext** code 6.

### 16.1 MUL and DIV as microcode STEP primitives

`ALU MUL` is one shift-add step over the triple `(tmpb = running high half,
tmpa = multiplier and low product, tmp[Tmp] = multiplicand)`: conditionally
add, then shift the double register right one place.  `ALU DIV` is one
**restoring**-division step over `(tmpb = remainder, tmpa = dividend low and
quotient, tmp[Tmp] = divisor)`: shift left, subtract if it fits, quotient bit
into `tmpa`.  Both write `tmpa` internally — the ROM row only names
`SIGMA -> tmpb`.  **ASSUMPTION** (the step algebra is a hardware model), but
it is what makes every `F6.4-F6.7`, `F7.4-F7.7`, `69`, `6B`, `D4` case exact,
including the undefined flags (§17).

Restoring (not non-restoring) division is forced by `0191`/`0120`, which run
no correction pass: with COUNT exhausted their `DIV` re-read is a
pass-through, so the loop must already leave a corrected remainder.

## 17. Undefined-flag emergence — the S1b scorecard

**No flag hooks exist in the simulator.**  Every `F6.*`, `F7.*`, `69`, `6B`,
`D4`, `D5`, `27`, `2F`, `37`, `3F` and shift/rotate form is exact against the
**raw** PSW, so the measured laws of `docs/facts/undefined_flags.md` are
reproduced by the microcode plus the ALU model alone.

| measured law | status | where it comes from |
|---|---|---|
| MULU leaves S/Z/AC/P **preserved** | **EMERGED** | the MULU path (`0178-017F` → MULX) contains no `W` row at all |
| signed MUL writes the **lo+lo self-add** residue (S = bit6/bit14, Z = (result & 0x7F/0x7FFF)==0, AC = bit3, P = parity(result<<1)) | **EMERGED** | MULADJ `0204 tmpa -> tmpb  ALU ADD tmpb` / `0205 SIGMA -> NULL W` *is* literally lo+lo, and MULADJ is on the IMUL path only |
| MUL CY/V = "the high half is not the sign extension" | **EMERGED** | MULX's `0206` ADC + `0209 JMP Z 3` + Int `[-06-]`/`[-07-]` |
| DIVU leaves the flags of the 16-bit pre-check `SUB(DW, divisor)` | **EMERGED** | `018B`/`018E` are the only `W` rows on the DIVU path |
| signed DIV **early trap** = flags of `SUB(|num_high|, |divisor|)` | **EMERGED** | IDIV `01A6/01A7` |
| signed DIV **late/non-trap** = S/Z/P of the unsigned quotient, CY=AC=V=0 | **EMERGED**, conditional on the PASS flag model (§17.1) | IDIV2 `01AD SIGMA -> [-03-] W` with `PASS tmpa` latched |
| AAM (CVTBD) V=AC=CY=0, S/Z/P defined | **EMERGED**, same condition | `D4` `0121/0122` `PASS tmpb` + `W` |
| AAD (CVTDB) AC/CY = internal-add residue | **EMERGED** | `D5` `012A/012B` `ADD tmpa` + `W` |
| shift/rotate with count 0 leaves **every** flag untouched | **EMERGED** | the R loop runs zero iterations, and `0228 JMP Z 3` skips the write-back entirely |
| shift/rotate V law (left: MSB(result) xor CY(out); right: MSB xor MSB-1 of the result) | **NOT emergent** — it is the per-step ALU flag model | `alu_step` |
| AND/OR/XOR/TEST AC always 0 | **NOT emergent** — ALU model (already S1a) | `alu_eval` |
| ADJ4A/ADJ4S/ADJBA/ADJBS flags | **NOT emergent** — fitted, §17.2 | `bcd_adjust` |

### 17.1 `PASS` drives the full arithmetic flag set — **MEASURED**

S1a modelled `PASS` as writing no flags (no bring-up form had a `W` over a
`PASS` latch).  The arithmetic groups force the opposite: `PASS` produces
S/Z/P from the value with **CY = AC = V = 0**.  Confirmed independently by
AAM (`0122`, measured "V, AC, CY always 0") and by signed DIV (`01AD`,
measured "S/Z/P of the unsigned quotient with CY = AC = V = 0").
`INC2`/`DEC2` remain flagless (§2.4 unchanged).

### 17.2 The BCD adjust: `ADJD`/`ADJA` arm, `ADD`/`SUB` execute — **RESOLVED**

`ALU ADJD tmpb` / `ALU ADJA tmpb` do not produce a result of their own; they
**arm a decimal / ASCII adjust mode** that the *next* latched `ADD` or `SUB`
executes.  This is what makes the four BCD blocks intelligible: each is
`AX -> tmpbL` + `ALU ADJx tmpb`, then `ONES -> tmpa` + `ALU ADD|SUB tmpa`,
then `SIGMA -> AL  SIGMA -> [-03-]  W` — the `ONES` operand is never used, and
the ADD/SUB only selects the direction of the correction.  **ASSUMPTION.**

The correction itself is a **MEASURED fit** (2000/2000 over `27` + `2F`,
1000/1000 each on `37`/`3F`):

```
lo_adj = (AL & 0x0F) > 9 || AC_in
hi_adj = (AL >> 4) > 9 || CY_in
       || ((AL >> 4) == 9 && (AL & 0x0F) > 9 && !AC_in)      <-- ADJD only
corr   = (lo_adj ? 6 : 0) + (hi_adj ? 0x60 : 0)
sum    = AL +/- corr                       (+ for ADJ4A/ADJBA, - for ADJ4S/ADJBS)
result = ADJA ? (sum & 0x0F) : (sum & 0xFF)
flags  = S/Z/P of (sum & 0xFF)   -- the UNTRUNCATED byte, even for ADJA
         AC = lo_adj,  CY = (ADJA ? lo_adj : hi_adj),  V = the byte overflow
```

Two departures from the x86 definition are real and measured:

1. **The high correction is a nibble test with a conditional decimal carry.**
   x86 uses `old_AL > 0x99`; the V30 uses `high nibble > 9`, plus a carry out
   of the low digit that is generated **only** by the "digit > 9" test and not
   by a correction that `AC_in` forced.  The two differ exactly on
   `AL = 0x9A..0x9F`: with `AC_in = 1` the V30 does **not** correct the high
   digit (`ADJ4A` of `0x9A` with AC gives `0xA0`, CY = 0; without AC it gives
   `0x00`, CY = 1).  The pure x86 rule misses 11 of the 2000 `27`/`2F` cases;
   the pure "high nibble > 9" rule misses 9; only the combined form fits all
   2000.
2. **ADJBA/ADJBS take their S/Z/P from the untruncated sum**, not from the
   `& 0x0F` result: `37` with AL = 0xB5 and no adjust reports S = 1 while
   writing AL = 0x05.

The AH increment/decrement is not part of the ALU op — it is the microcode's
own `JMP NC 5` + `ALU INC/DEC tmpb` tail, and it works because CY = lo_adj.

## 18. Bus semantics forced by the internal page

### 18.1 `F` is a read interlock; read data reaches OPR only through it

**RESOLVED, replaces the S1a "MEMR writes OPR immediately" behaviour.**  A
`MEMR` row *issues* a read; the datum is delivered into OPR by the next row
that carries `F`, in issue order.

*Evidence (ROM, decisive):* the INT routine issues two vector reads two rows
apart (`01EE`, `01F0`) and then consumes them in order on `01F1` (`OPR ->
tmpc`, the new IP) and `01F3` (`OPR -> tmpa`, the new CS), both `F` rows.  If
the second read landed in OPR when it was issued, both rows would read the CS
word.  POPA (`024C`-`025C`) does the same thing seven times over with a
one-read-deep lead.  Every `OPR ->` **source** row in the whole ROM carries
`F`, which is what makes the rule total.
*Negative control, run:* read data lands in OPR at issue → `CD` 0/1000, `CF`
0/1000, `61` 0/1000, `CB` 0/1000 (`58`, `8F.0` unaffected — one read in
flight).

Rows that consume a read *without* `F` do not exist; the one place the datum
is needed with no `F` row in sight is a **write data phase** (MOVBK `008D`
read → `008F` `MEMW ES`), which §18.2 covers.

### 18.2 Write-data pairing — **RESOLVED, replaces S1a §6.1**

S1a modelled a posted write whose data phase sampled OPR exactly one row
later.  PUSHA falsifies that: `0239 AX -> OPR` / `023A MEMW` / `023B CX ->
OPR` must push **AW** at SP-2, i.e. the value loaded *before* the MEMW row.
ENTER falsifies the mirror image: `0262 MEMW` / `0263 BP -> OPR` must push
**BP**, loaded *after*.

The rule that satisfies both, and every other write in the ROM, is
**pairing**: each write consumes the OPR value that has been (re)loaded since
the previous write consumed one.

```
a write issued while OPR already holds an unconsumed value  -> runs at once
otherwise                                                   -> waits for the
   next OPR load (a transfer to OPR, a `-> M` on a memory operand, or a read
   delivered by `F`), or for the next bus cycle / end of instruction
```

This keeps every S1a case (`50-57` `0029`/`002A`, `A2/A3` `008A`/`008B`,
`86/87` `0049`/`004A`) and adds `6A` (`0285` MEMW, OPR loaded **two** rows
later at `0287`), the string blocks (`008F`'s data is the `008D` read), CALLF,
the INT pushes and the ENTER walk.  **ASSUMPTION** — it is a functional
stand-in for "the bus takes the data when the cycle runs, and the microcode's
`F` markers order it".
*Negative control, run:* a write always waits for the *next* OPR load (the
ENTER half of the rule alone) -> `60` 0/1000; `C8`, `50`, `A2`, `86`, `6A`,
`00`, `88` all unaffected.  The mirror half -- always take the value present
when the MEMW issues -- is what S1a's one-row posting did to ENTER, and it
drops the BP push.

### 18.3 `SR = IO` selects the I/O space only for the I/O opcode classes

`Str_SR[1]` is printed `IO`, but the internal INT routine uses it for the
**interrupt-vector fetch** (`01EE`, `01F0`), which is a memory read at
physical `vector*4` — segment zero, not an I/O cycle.  The discriminator is
pla_3's `XOP`: `1111` (port I/O: `E4-E7`, `EC-EF`) and `0110` (block I/O:
`6C-6F`) are the only classes that mean the I/O space; everywhere else
`SR = IO` means **segment base 0**.  Vector fetches are also word-wide
regardless of the instruction's operand width (a byte `F6.6` DIVU that traps
still fetches a word vector).  **PLA + ASSUMPTION.**
*Negative control, run:* `SR = IO` always I/O → `CD` 0/1000, `CC` 0/1000,
`CE` 490/1000, `F6.6` 473/1000.

### 18.4 A `FARJMP` row has no bus cycle

`Int == 0x0E` aliases `Ext:SR` as the 5-bit far target, so those five bits
must not be decoded as a bus request.  `FARJMP SHIFT` (target 9) aliases to
`Ext = 2` (`MEMW`) with `SR = 1`, and `FARJMP MULADJ`/`IMUL` alias to `MEMR`.
**ROM-forced** (and the reason `D2/D3`/`C0/C1` wrote a spurious word to
physical `EA` before the fix).

## 19. The micro-PC carries out of `loc` into the opcode byte — **ROM**

Sequential execution past `loc = 15` increments the **opcode** field of the
micro-address; it does not wrap inside the 16-row block.

*Evidence, two independent blocks:*
* byte IMUL: `00B0 JMP OP8 15` sends the byte case to `00B3 tmpb -> AH`
  (page 7, opcode `0x30`, loc 15), which has no `E`.  The next row must be
  `0218` — `111.00110001.00`, opcode `0x31`, `tmpa -> AL  FARJMP MULADJ` —
  the byte product's low half.  Wrapping to loc 0 re-enters IMUL.
* INT: `01FB tmpc -> PC  MEMW SS` is opcode `0x10` loc 15 and must fall into
  `01FC` `SIGMA -> SP  E  FLUSH`, which the disassembly labels
  `111.0001?001.00  <internal> 11,19`.

*Negative control, run:* no carry → `CD` 0/1000, `CC` 0/1000, `F6.5` 0/1000
(word IMUL, which never crosses the boundary, is unaffected).

## 20. L-half writes: `tmpbL` sign-extends, `tmpaL` does not — **RESOLVED**

S1a §2.6 left open whether the L-half sign extension is unconditional.  It is
**per-register**: `-> tmpbL` (Dest1 `0x15`) sign-extends into the high half,
`-> tmpaL` (Dest1 `0x14`) zero-extends.

*Evidence for `tmpbL` (MEASURED):* `83` needs it (`003C Q -> tmpbL`, and 492
of the 1000 `83.0` cases have a negative imm8; with zero extension `83.0`
falls to 508/1000), as do `70-7F` (`0034`), `EB` (`0158`) and `6A`
(`0286 tmpa -> tmpbL`, PUSH imm8 sign-extends).
*Evidence for `tmpaL`:*
* architectural (MEASURED): `0119 CX -> tmpaL` feeds COUNT, and the rotate
  forms are sensitive to the count modulo 9 / 17.  Sign-extending CL breaks
  `D2.2` (745/1000), `D2.3` (778/1000) and `C0.2` (759/1000) — the byte
  RCL/RCR forms, whose modulus does not divide the 0xFF00 the sign extension
  adds.  (`D3.2`/`D3.3`/`C1.2` are unaffected: 65408 ≡ 128 mod 17.)
* bus (MEASURED, cycle records): `0144 Q -> tmpaL` feeds the port address for
  `E4/E5`.  The `E4` golden records the IOR address as `0x00A1` for
  `in al, a1h`, not `0xFFA1`.  This is **not** covered by the arch-only gate —
  the checker never compares I/O addresses — so it is recorded here as the
  reason the zero extension is right rather than merely harmless.

The H-half writes (`-> tmpaH` / `-> tmpbH`) take bus bits 15:8; a **byte**
source (`Q`, `CONST`) presents its byte there, a 16-bit source presents its
own high half.  Forced by `9E` SAHF: `007D FLAGS -> tmpaH` must lift the PSW's
**high** byte, while `0005 Q -> tmpaH` must lift the immediate's only byte.
**ROM-forced.**

## 21. Miscellaneous decisions

| decision | class | note |
|---|---|---|
| the ALU latch at instruction entry is `ADD tmpa` (the address adder's default), plus the synthetic EA constant for a ModR/M memory operand | ASSUMPTION | forced by `D7` XLAT: `012C AX -> tmpaL  BX -> tmpb  CTL` / `012D SIGMA -> IND  MEMR` computes BW + AL with **no** ALU row of its own |
| `CITF` (`Str_Int[1]`) clears IE and BRK | ROM-forced | `01F5`, on the row that pushes the *pre-clear* PSW |
| `MFS`/`MFC`, `[-03-]`/`[-05-]` Ext, `[-0A-]` | ASSUMPTION (no-op) | 8080-mode and pin-event machinery; no scoped form observes them.  **`[-04-]` and `[-0D-]` were resolved at S1c, §25.1** |
| word I/O at an **odd** port splits into two byte cycles | MEASURED | the `ED` cycle records show two IOR cycles at DW and DW+1 whenever DW is odd, and the byte lane follows address parity, so `in ax, dx` returns the recorded word byte-swapped |
| the suite's `iord=XXXX` case-name field is the port datum | policy | there is no I/O model; `sim/case_runner.cpp` replays it verbatim.  This is an *input*, not a prediction — `E4/E5/EC/ED` are exact only in that sense |

### 21.1 The S0a ambiguous address — **analysed, not exercised**

`111.00000010.00` is matched by two banks (`01DC-01DF` and `01E0-01E3`).
Structurally the second is the interrupt-acknowledge routine: two
`[-05-] IO` cycles with `IND = 0` whose data is collected into `tmpb` before
`FARJMP INT` — i.e. the classic two-cycle INTA vector fetch.  The first bank
saves and restores AW around a single `[-05-]` cycle and looks like the 8080
/ BRKEM variant.

**No scoped form reaches it.**  `CC`/`CD`/`CE` jump straight to `FARJMP INT`
(page 7, opcode `0x10`); only a hardware INTA does, and pin-event forms are
S2 scope.  The decode table still keeps first-match-wins.  Carried forward to
whoever brings up the INT/NMI pseudo-forms.

## 22. S1b result

Gate: every scoped form **arch-exact** (registers incl. raw PSW + RAM) on its
full v0.2 tranche, 1000 cases each.

| family | forms | result |
|---|---|---|
| S1a handoff (`83`, `80`/`81` groups, NOT/NEG, CWD, SAHF) | 28 | 28 × 1000/1000 |
| shifts / rotates + internal SHIFT | `C0.* C1.* D0.*-D3.*` | 48 × 1000/1000 |
| multiply / divide + MULADJ MULX IMUL IMULI IDIV IDIV2 | `F6.4-7 F7.4-7 69 6B` | 10 × 1000/1000 |
| BCD | `27 2F 37 3F D4 D5` | 6 × 1000/1000 |
| flow / stack / internal routines | `9A CA CB CC CD CE CF C8 C9 60 61 62 6A E0-E3 D7 E4 E5 EC ED` | 22 × 1000/1000 |

**114 / 114 forms, 114 000 / 114 000 cases** (`python3 sw/ucsim_smoke.py --s1b`).

Whole-suite survey at the same commit: **311 of 351 v0.2 forms fully green,
312 128 of 347 000 cases passing** (S1a baseline: 172 forms / 179 475 cases).
**Zero regressions** — every form green at S1a is still green.

Everything still failing is out of S1b scope: the 25 `0F`-page forms
(`0F10-0F1F` bit ops, `0F20/22/26` BCD strings, `0F28/2A` ROL4/ROR4,
`0F31/33/39/3B` INS/EXT) and the 11 pin-event pseudo-forms
(`HLT.INT`, `HLT.NMI`, `INT.*`, `NMI.*`).

---

# S1c — the `0F` page

The last 25 sim-scope forms of v0.2: the bit-manipulation block
(`0F 10-1F`), the BCD strings (`0F 20/22/26`), the nibble rotates
(`0F 28/2A`) and the bit-field group (`0F 31/33/39/3B`).  Everything below
was resolved at S1c; every negative control listed was actually run.

## 23. Decode: how the `0F` page re-purposes the pla_3 columns

### 23.1 `ALU BIT` (`Str_Op[0x17]`) is a one-shot PORT-B BIT MASK — **RESOLVED**

`ALU BIT tmp` captures `n = tmp[Tmp] & (width - 1)` and arms a **one-shot**
mode: the **next** latched operation has its port-B operand replaced by
`tmp[Tmp] & (1 << n)`.  The arm is consumed by that one operation, exactly the
way `ADJD`/`ADJA` arm the following `ADD`/`SUB` (§17.2).  A bare `BIT` row's
own SIGMA is a pass-through and is never read in the ROM.

*Evidence (ROM, decisive).*  One shared shape serves all sixteen `0F 1x`
opcodes, and only the bit-mask reading makes any of them mean anything:

| block | rows | second op | result |
|---|---|---|---|
| `10/11`, `18/19` TEST1 | `02AC-02AF`, `02B0-02B3` | `AND tmpa` (`tmpa = ONES`) | `tmpb & (1<<n)`, `SIGMA -> NULL WE` |
| `14/15`, `1C/1D` SET1 | `02B4`, `02B8` | `OR tmpa` | `tmpb \| (1<<n)` |
| `16/17`, `1E/1F` NOT1 | `02C4`, `02C8` | `XOR tmpa` | `tmpb ^ (1<<n)` |
| `12/13`, `1A/1B` CLR1 | `02BC-02BF` | `NOT tmpa` then `AND tmpa` | `~(ONES & (1<<n))` into tmpa, then `tmpb & ~(1<<n)` |

CLR1 is what forces **both** halves of the rule: `02BD` loads `ONES` over the
bit number, so the index must have been **captured at the BIT row** and not
re-read; and `02BE` latches a *second* `AND tmpa` which must see the plain
`~(1<<n)` in tmpa, so the arm must already be **spent**.  A persistent arm
gives `tmpb & (~(1<<n) & (1<<n))` = 0.

The bit number is taken **modulo the operand width** — `n = CL & 7` for the
byte forms, `& 15` for the word forms (`W_FROM_BIT0`, opcode bit 0).  The
reg forms read `CX -> tmpa` (the whole CW; only the low bits survive the
mask), the imm forms `Q -> tmpa`.

Flags follow the ordinary logic-op model (§2.4): `AND` sets S/Z/P of the
masked value with CY = V = AC = 0 — which is exactly the measured TEST1 law in
`docs/facts/undefined_flags.md` ("TEST1 sets S/Z/P of the masked value ...
AC=0").  **EMERGED**: no TEST1-specific code exists.

*Negative controls, run:*
* arm PERSISTS instead of being one-shot → `0F 12` 12/1000, `0F 13` 8/1000,
  `0F 1A` 10/1000, `0F 1B` 7/1000 (CLR1 only — TEST1/SET1/NOT1 latch just one
  op after the BIT row and are unaffected);
* index re-read from port B at USE time instead of captured at the BIT row →
  `0F 10` 343/1000, `0F 11` 277/1000, `0F 12` 348/1000, `0F 13` 289/1000,
  `0F 1A` 327/1000, `0F 1B` 285/1000.

*Falsifier:* a `0F 1x` form whose result needs the unmasked operand.  None.

### 23.2 `ALU ROL12` (`Str_Op[0x10]`) is a 16-bit left shift with the rotate tap at BIT 11 — **RESOLVED (MEASURED)**

One `R`-loop step of `ROL12` is

```
tmpb = (tmpb << 1) | ((tmpb >> 11) & 1)      -- 16 bits, feedback from bit 11
```

so bits 11:0 rotate while bits 15:12 are a plain shift register fed from
bit 11.  `0F 28` (ROL4) runs it **4** times, `0F 2A` (ROR4) **8** times —
a left rotate of 8 within a 12-bit field *is* a right rotate of 4.

*How the ROM builds the operand* (`02EC-02F7`, entry rows `02EC`/`02F8`):
`M -> tmpbL` then `AL:AH -> tmpbH` assemble `tmpb = (AL << 8) | operand`, so
the rotating 12-bit field is `AL[3:0] : operand[7:4] : operand[3:0]` and
`tmpb[15:12]` holds `AL[7:4]`.  After the loop, `tmpb -> M` + `[-06-]` store
the new operand byte, and `tmpb -> AX` / `AL:AH -> tmpb` / `tmpa -> tmpbH` /
`tmpb -> AX` swap the new AL into place while restoring AH from the copy
`02F1` took.

*Why the tap is at 11 and not "rotate the low 12 bits" (MEASURED):* the real
chip does **not** preserve AL's high nibble.  `0F 28` idx 2 (`rol4 byte
[bx+di+50h]`, AL = 0x81, mem = 0xE5) writes mem = 0x51 and **AL = 0x1E** — the
old AL *low* nibble has been shifted up into AL's high nibble.  A clean 12-bit
rotate predicts AL = 0x8E.  The bit-11 tap predicts 0x1E, and makes all 2000
`0F 28`/`0F 2A` cases exact.
*Negative controls, run:* a true 12-bit rotate (bits 15:12 preserved) →
`0F 28` 88/1000, `0F 2A` 91/1000; rotating the whole 16-bit word by one nibble
per step (the S1b placeholder) → `0F 28` 1/1000, `0F 2A` 31/1000.

### 23.3 `MODRM_STORE` (pla_3 b6) suppresses the pre-read in NATIVE MODE ONLY — **RESOLVED (MEASURED)**

This closes the Codex concern carried from the S1b phase review.  §5 read b6 as
"the standard operand-fetch step is skipped".  pla_3 also asserts b6 for the
ext-section blocks `0F 28-2F` (ROL4/ROR4) and `0F 30-3F` (INS/EXT), and those
**do** read their r/m operand: `0F 28`'s row `02ED` is `M -> tmpbL` and its
block contains no `MEMR` at all, so the datum can only have come from the
pre-decode fetch.

*Evidence (MEASURED, v0.2 cycle records, `mod != 3` cases):*

| form | b6 | MEMR cycles | MEMW cycles |
|---|---|---|---|
| `88`, `89`, `8C` | set | **0** | 3 / 6 |
| `C6.0`, `C7.0` | set | **0** | 3 / 6 |
| `8D` LEA | set (merge) | 0 | 0 |
| `0F 28`, `0F 2A` | set (ext) | **3** | 3 |
| `0F 12`, `0F 14` | clear | 3 | 3 |

The discriminator the concern asked for is direct: 745 of the 1000 `0F 28`
cases and 749 of `0F 2A` have a memory r/m operand, and all 1494 are exact only
with the pre-read enabled.
*Negative control, run:* honouring b6 on the ext page → `0F 28` 258/1000,
`0F 2A` 253/1000 — i.e. **exactly the `mod == 3` cases survive** (255 and 251,
plus a handful of memory cases whose stale OPR happens to match).  `0F 31` and
`0F 33` are unaffected (1000/1000): the v0.2 bit-field tranches are entirely
`mod == 3`, which is why R8 below stays open.

`sim/loader.cpp` therefore gates the suppression on `!ext`.  `docs/facts/pla_model.md`
carries the same refinement; **the column MEMBERSHIP is unchanged** — it is dump
fact — only the declared semantics are qualified, and `sw/pla3_check.py` states
the qualification alongside the (unchanged) predicate.  Class: **MEASURED** for
the two senses; **ASSUMPTION** for the mechanism (a mode-gated consumer of b6
versus a separate, undumped ext-page fetch-enable term).

### 23.4 The bit-field group takes BYTE register operands — **MEASURED**

pla_3 gives `0F 30-3F` `W_FROM_BIT0`, and all four documented forms
(`31 33 39 3B`) have bit 0 set, i.e. **word**.  The string accesses through
`IND` are indeed word-wide.  The two ModR/M register operands are **byte**
registers regardless.

*Evidence:* `0F 33 D5` is `ext dl, ch` — ModR/M `mod=3 reg=2 rm=5`.  At word
width `rm = 5` is BP; the case's BP is `0xC480`, whose low byte 0x80 would make
the bit offset 128.  As the byte register CH (0x05) it is a legal offset and
the case is exact, with the updated offset landing back in **CH**.  All 4000
`0F 31/33/39/3B` cases are exact under the byte binding.
*Negative control, run:* word registers (the plain `W_FROM_BIT0` width) →
`0F 31` 5/1000, `0F 33` 78/1000, `0F 39` 15/1000, `0F 3B` 132/1000.
The simulator keys this off `XOP = 0011` ("bit-field operation") in the ext
section — the only ext-page marker for the block.  **ASSUMPTION** for the
choice of signal.

pla_3's `ACC_W_OPERAND` is also asserted on this block; it does **not** bind
AL/AW here (the block carries a ModR/M byte, so the §3.2 accumulator branch is
not reached).  Both re-purposings are recorded in `docs/facts/pla_model.md`.

## 24. The iterative unit: SPENT vs. freshly latched — **REFINEMENT of §12**

§12 established that a *post-loop* `SIGMA` read of an iterative op is a
pass-through of port A.  The BCD strings force the complement: a **freshly
latched** iterative op that no `R` row has driven presents **one step**
combinationally.

*Evidence (ROM, decisive):* `02CC-02CE` computes the byte count as

```
02CC CX -> tmpaL                ALU INC tmpa
02CD SIGMA -> tmpb              ALU SHR tmpb
02CE SIGMA -> COUNT             CTL [-04-]
```

`COUNT` must be `(CL + 1) >> 1` and there is no `R` row anywhere near it.  The
tail repeats the shape at `02DF-02E1` to reconstruct the byte count for the
SI/DI restore.  Meanwhile every §12 witness (`0117`, `022A`, `0120`, `0191`)
reads its SIGMA on the row *after* an `R` row, so "the `R` row leaves the latch
spent" separates the two cleanly.  Model: `AluLatch::spent` is set by any `R`
row and cleared when a new operation is latched.
*Negative controls, run:* always pass through → `0F 20` 0/1000, `0F 22`
0/1000 (COUNT comes out as `CL + 1` instead of `(CL + 1) >> 1`, so a 1-digit
ADD4S writes two bytes); `0F 26` (CMP4S, which writes nothing and restores
SI/DI through the same doubled count) and the shift forms `D0.4`/`D2.4` are
unaffected, which is what makes the two halves of the rule independent.
Always step → the whole `C0/C1/D0-D3` block and `F6.4-7`/`F7.4-7` collapse
(§12's own control).

No ROM row reads a freshly latched `MUL`/`DIV`, so the single step is
evaluated side-effect free (it never touches the multiplier/quotient register).

## 25. The BCD string ops `0F 20/22/26` — **RESOLVED**

Shape (`02CC-02EB` + the shared tail `02D8-02E3`): `COUNT = (CL + 1) >> 1`
whole bytes; per iteration read `[DS:SI]` into tmpc and `[ES:DI]` into tmpb,
`ADC tmpc` (ADD4S) or `SBB tmpc` (SUB4S/CMP4S), `ADJD`-armed `ADD`/`SUB`,
`MEMW ES` (absent for CMP4S — `02EB` carries no Ext code, which is the whole
difference between `0F 22` and `0F 26`), advance SI and DI, `JMP CNTZ`.

### 25.1 `CTL [-04-]` (Int 4) and `CTL [-0D-]` (Int 13) — **RESOLVED**

Both codes appear on exactly **one row each in the whole ROM**, both in this
block, so they are fully determined by it.

* **`[-04-]` (row `02CE`) initialises the digit chain: CY = 0, and the
  auxiliary latch (§16's `[-09-]` flip-flop) is SET.**  Clearing CY is forced
  arithmetically: `0F 20` idx 0 has PSW CY = 1 on entry, `0x78 + 0xD0` and the
  golden result byte 0xA8; with the incoming carry the adjusted result is 0xA9.
  *Negative control, run:* drop only the CY clear → `0F 20` 525/1000,
  `0F 22` 492/1000, `0F 26` 999/1000.
* **`[-0D-]` (row `02D8`) CLEARS that latch whenever the digit pair just
  produced is non-zero.**  It is the sticky "the whole result is not zero"
  accumulator, read by the tail's `JMP [-09-]`.
  *Negative control, run:* `[-0D-]` a no-op (the latch stays set, so `[-09-]`
  reads "everything was zero") → `0F 20` 804/1000, `0F 22` 598/1000,
  `0F 26` 555/1000.  The survivors are the cases that leave a final BCD carry,
  where `02DC`'s `JMP [-00-]` short-circuits `[-09-]` entirely.
  *Negative control, run:* drop only `[-04-]`'s latch SET → `0F 20` 1000/1000,
  `0F 22` 999/1000, `0F 26` 1000/1000.  The set is only weakly discriminated
  because the simulator's latch happens to power up clear; it is kept because
  it is the only reading under which `[-04-]` and `[-0D-]` are one
  initialise/accumulate pair, and one `0F 22` case does need it.

The two together give a coherent reading of the one auxiliary flip-flop the
ROM has: `[-1E-]` loads it from a sign, `[-0C-]` toggles it by a sign,
`[-04-]` sets it, `[-0D-]` clears it on a non-zero result, and `[-09-]` tests
it **clear**.  Class: **MEASURED (fit)** — the assets name none of the codes.

### 25.2 The tail computes the architectural CY and Z out of `tmpb + tmpb`

```
02DB CX -> tmpaL                       ALU ADD tmpb     <- port A and port B are both tmpb
02DC                                   JMP [-00-] 3     <- final BCD carry?  -> 02DF
02DD CONST -> tmpb 1                   JMP [-09-] 3     <- result non-zero?  -> 02DF
02DE ZEROS -> tmpb                     CTL
02DF SIGMA -> NULL                 W   ALU INC tmpa     <- the ONLY flag write that survives
```

At byte width `tmpb + tmpb` turns a seed value into the pair (CY, Z):
seed 1 → 0x02 (CY 0, Z 0), seed 0 → 0x00 (CY 0, Z 1), and the carry path needs
a seed with bit 7 set.

**`Source2 [-00-]` = ONES.**  Row `02DA` (`SIGMA -> DI   [-00-] -> tmpb`) is
the *only* use of Source2 code 0 in the entire ROM, and it supplies that seed.
`0xFFFF + 0xFFFF` at byte width is 0xFE: CY = 1, Z = 0, S = 1, AC = 1, P = 0 —
bit-for-bit the golden final PSW of `0F 20` idx 0 (`0xF493`).  No other
plausible source (`ES`, `ZEROS`, a register) reproduces AC and P together.
Class: **ASSUMPTION (MEASURED-constrained)**; falsifier = any second use of
Source2 `[-00-]`, of which there is none.
*Negative control, run:* `[-00-]` = ZEROS → `0F 20` 196/1000, `0F 22` 403/1000,
`0F 26` 445/1000 (exactly the carry-out cases fail).

This is also where the measured law "`ADD4S/SUB4S/CMP4S: S = AC = CY(out),
P = Z(out), V = 0`" (`docs/facts/undefined_flags.md`) comes from — it is
**EMERGED**: the four "undefined" bits are simply what `tmpb + tmpb` produces
for the three reachable seeds.

### 25.3 Where silicon departs from the manual

1. **The digit count is rounded UP to whole bytes.**  `COUNT = (CL + 1) >> 1`
   and every iteration adds/subtracts a full byte, so with an **odd** CL the
   high digit of the last byte pair takes part — the manual's "CL = number of
   BCD digits" does not survive.  Exercised by 492 / 498 / 502 of the 1000
   `0F 20` / `0F 22` / `0F 26` cases (odd CL with a non-zero high digit in the
   last pair), all exact.
2. **The correction is the V30's own nibble rule**, not x86 `AL > 0x99` — the
   §17.2 fit, reused here unchanged.  The hand-fitted "one-carry-rail decision
   quirk" of `docs/facts/undefined_flags.md` (high adjust decides on
   `ahi + bhi + (c1|c2)`) is **EMERGED** from that fit plus the microcode: the
   V30 rule `hi_adj = (AL>>4) > 9 || CY_in || ((AL>>4) == 9 && (AL&0xF) > 9 &&
   !AC_in)` applied to the ADC result reproduces all 3000 cases with no
   BCD-string-specific code.
3. **CMP4S writes nothing** but still advances and restores SI/DI exactly like
   ADD4S/SUB4S, and still runs `DI -> IND` on `02EB`; only the Ext field
   differs.
4. `CL = 0` underflows `JMP CNTZ` into a very long loop (the documented
   `0F 24` note in `docs/facts/undocumented_0f.md`).  The v0.2 tranche excludes
   it, so the simulator's behaviour there is **untested** — carried to S2.

## 26. `0F 31/39` INS and `0F 33/3B` EXT — **RESOLVED**

Operand roles (MEASURED, and the same for both instructions): the ModR/M
**`reg`** field is the **bit-length** register (the field is `len + 1` bits
wide) and the **`r/m`** field is the **bit-offset** register, which is the one
the instruction updates.  For the imm forms the length comes from the
`Q -> tmpaL` byte (`0347` for INS, `0315` for EXT) instead.

### 26.1 EXT's `JMP Z` / `JMP NC` chain — **RESOLVED**

Row `0304` computes `15 - (off + len)` and `W`-commits it; the chain then is

| condition | rows | meaning |
|---|---|---|
| `Z` (`0305 JMP Z 11`) | → `0307` → `JMP Z 14` → `030A` | the field ends exactly at bit 15: advance IX by 2, but do **not** fetch a second word |
| `NC` (`0306 JMP NC 14`) | → `030A` | `off + len < 15`: the field is inside the first word, IX unchanged |
| else | `0307`, `0308`, `0309` | the field straddles: IX += 2 **and** a second word is read at IX+2 |

Confirmed by the cycle records: `0F 3B` idx 16/19 (both `off + len == 15`)
issue exactly **one** word read, and `0F 33` idx 5 likewise; the straddling
cases issue two.

The extraction itself is two `MUL`-with-zero (= right-shift) `R` loops over the
32-bit pair `{tmpb : tmpa}`: first by `COUNT = ((off+len) & 15) + 1`, then by
`COUNT = AX = 15 - len`, with `0312 JMP Z 8` skipping the second shift when
`len == 15` (a full 16-bit field needs no masking).  `0200 tmpa -> AX  E`
delivers the result.

**Aliasing is architecturally visible and the goldens keep it.**  `02FE`
(`0317` for the imm form) writes `AX = 15 - len` *before* `0301` reads the
offset register, and `030D` writes the updated offset *before* `0310` reads AX
as the second shift count.  When the offset or length register is AL or AH the
instruction therefore reads its own scratch: e.g. `0F 33 EC` (`ext ch, ah`)
extracts with offset 0 rather than the AH the programmer loaded, and
`0F 3B C0 08` (`ext imm4 al 08h`) ends up returning the whole first word.
Both are exact in the simulator with no special case — the ROM order produces
them.

### 26.2 `ALU ADJA` as EXT's modulo-16, and the ADJx DISCHARGE rule — **RESOLVED**

`030B` (`SIGMA -> COUNT   SIGMA -> tmpb   ALU ADJA tmpb`) writes the *same*
value 16 to COUNT and to tmpb when `off + len == 15`, yet `030D`'s
`tmpb -> M` must store **0** (the new bit offset, mod 16) while the shift at
`030F` must still run **16** times.  The two are separated by the ADJA.

**Rule:** an armed `ADJD`/`ADJA` is normally consumed by the `ADD`/`SUB`
latched on the following row (§17.2).  If the next latched operation is **not**
an `ADD`/`SUB`, the arm **discharges** instead: the adjust unit writes its plain
truncation — a nibble for `ADJA`, a byte for `ADJD`, with **no** decimal
correction, since the correction needs an adder pass — back into its operand
register.

`030B` is the **only** row in the whole ROM whose ADJx arm is not followed by an
`ADD`/`SUB` (the other seven are `0010`, `0014`, `0018`, `0020`, `02D5`,
`02E5`, `02E9`, `03A0`, all followed by one), so the rule cannot disturb
anything else, and INS does the identical job with an explicit `AND 15` at
`0323`/`0325` — independent confirmation that mod-16 is the intent.
Class: **ASSUMPTION (ROM-constrained)**.
*Negative controls, run:* no discharge → `0F 33` 836/1000, `0F 3B` 826/1000
(and `27`/`2F`/`37`/`3F` unaffected at 1000/1000 each, confirming the rule
cannot reach the native BCD blocks); discharge WITH the decimal correction →
`0F 33` 697/1000, `0F 3B` 702/1000 — every case whose new offset should be 15
comes out 5, which is what pins the discharge as a **plain** truncation.

### 26.3 The adjust unit works on the ADJx row's own `Tmp` operand — **ROM**

S1b hard-wired the BCD operand to `tmpb`.  It is the register named by the
**`Tmp` field of the ADJx row**: `tmpb` for the native `27/2F/37/3F`, for the
`0F` BCD strings and for `030B`, but `tmpa` for the 8080 `DAA` at `03A0`
(`AX -> tmpa   ALU ADJD tmpa` / `ONES -> tmpb   ALU ADD tmpa`), where the ONES
operand sits on the other port.  Behaviourally identical for every native form;
it makes the 8080 page right for free.

## 27. Write-data pairing: reading OPR CONSUMES it — **REFINEMENT of §18.2**

§18.2's rule is "a write issued while OPR already holds an unconsumed value runs
at once, otherwise it waits for the next OPR load".  S1c pins what *unconsumed*
means: **an `OPR ->` source read consumes the value.**

*Evidence (ROM, two independent blocks):*
* BCD strings — `02D4 OPR -> tmpb  F` takes the `[ES:DI]` datum out of OPR;
  `02D7` then issues `MEMW ES` and `02D9 SIGMA -> OPR` supplies the adjusted
  result.  Without consumption the write posts immediately and stores the
  operand back unchanged.
* INS — `032B OPR -> tmpa` drains the saved low bits, `032F MEMW ES` issues and
  `0330 tmpa -> OPR` supplies the data.

*Negative control, run:* reads do not consume → `0F 20` 6/1000, `0F 22`
1/1000, `0F 31` 486/1000, `0F 39` 451/1000.  `0F 26` (no write at all) and
every previously green OPR-heavy form (`58`, `8F.0`, `60`, `61`, `C8`, `CD`)
are unaffected at 1000/1000, so the refinement is strictly additive to §18.2.

## 28. S1c result

Gate: every `0F`-page form **arch-exact** (registers incl. raw PSW + RAM) on its
full v0.2 tranche, 1000 cases each.

| family | forms | result |
|---|---|---|
| bit manipulation | `0F10-0F1F` (TEST1/CLR1/SET1/NOT1, reg + imm) | 16 × 1000/1000 |
| BCD strings | `0F20 0F22 0F26` (ADD4S/SUB4S/CMP4S) | 3 × 1000/1000 |
| nibble rotate | `0F28 0F2A` (ROL4/ROR4) | 2 × 1000/1000 |
| bit field | `0F31 0F33 0F39 0F3B` (INS/EXT, reg + imm) | 4 × 1000/1000 |

**25 / 25 forms, 25 000 / 25 000 cases.**

Whole-suite survey at the same commit
(`python3 sw/ucsim_smoke.py --suite tests/v30/v0.2 --all`):
**336 of 347 v0.2 form files fully green, 336 000 of 347 000 cases**
(S1a 172 forms / 179 475 cases; S1b 311 forms / 312 128 cases).
**Zero regressions** — every form green at S1b is still green, and the case
delta is exactly the 23 872 `0F` cases that were failing.

The remaining 11 files are the pin-event pseudo-forms (`HLT.INT`, `HLT.NMI`,
`INT.*`, `NMI.*`), which need the interrupt-acknowledge machinery and are S2
scope by the plan.

---

# P1 — bring-up gate summary

Gate P1 (campaign plan): *"bring-up families arch-exact on their v0.2 tranches;
the ranked semantic unknowns each resolved with a documented answer in the
ledger."*  All sim-scope v0.2 forms are green and every ranked unknown is
answered.  This section is the consolidated provenance accounting.

## 29. Provenance census

Every behaviour the simulator implements carries a class tag in §1-§28.
Counting them (a "decision" = one named behaviour with its own evidence
paragraph or its own row in a decision table; the tag counts below are
mechanically greppable from this file — `**ROM**`, `**PLA**`, `**MEASURED**`,
`**ASSUMPTION**` plus the class column of the §8/§21 tables):

| class | meaning | count |
|---|---|---:|
| **ROM** | read directly out of `docs/V20BITS.TXT` through `docs/V20UCDIS.PAS`; the ROM admits no alternative | 18 |
| **PLA** | derived from a dumped PLA as identified in `docs/facts/pla_model.md` | 7 |
| **MEASURED** | fitted or confirmed against a silicon golden or `docs/facts/*` | 17 |
| **ASSUMPTION** | not determined by the assets; adopted because it reproduces the goldens | 28 |
| policy | deliberate non-modelling (queue deferral, `iord` replay) | 2 |
| **total** | | **72** |

> **Exhaustiveness (corrected at S2a).**  §30's table A1..A28 enumerates the
> assumptions the simulator makes *when it executes a row*.  It is NOT the whole
> assumption surface: the microcode codes that no scoped form reaches are
> assumptions **by omission** (modelled as no-ops on no evidence), and the P1
> text listed them only as prose.  S2a promotes every such code the pin-event
> work touches into the numbered table (A29..A35 in §38) and re-classifies the
> rest by whether a green form actually executes them (§39).  The census below
> is therefore the P1 snapshot; §38's totals supersede it.

The **ASSUMPTION** row is the campaign's answer so far, and §30 enumerates it
with A1..A28, one line each, plus the falsifier that would kill it.
Twelve of the 28 are tagged *ROM-constrained* (A1, A14, A17, A18, A20, A21,
A22, A23, A25, A26, A27 and the §3.1 entry A3): the ROM admits exactly one
behaviour that makes the affected block intelligible, but no dumped asset names
it.  Four are *MEASURED-constrained* (A11, A16, A24 and the Source2 `[-00-]`
value of §25.2): a golden pins the value uniquely, nothing in the dumps does.
The remaining twelve are free choices that the goldens merely fail to
contradict — those are the ones a die trace would have to settle.

## 30. The assumption list, with falsifiers

| # | assumption | § | falsifier |
|---|---|---|---|
| A1 | binary ALU ops compute `tmpb OP tmp[Tmp]`; unary ops act on `tmp[Tmp]` | 2.1 | a non-commutative binary row with `Tmp = tmpb`; none is reachable |
| A2 | `INC2`/`DEC2` are always 16-bit regardless of operand width | 2.4 | a byte-width instruction whose microcode also does stack arithmetic |
| A3 | the pre-decode contract of §3.1 (prefixes, opcode reg, ModR/M+disp, EA→IND, M/R binding, pre-read, page select) | 3.1 | any form needing a different split between loader and microcode |
| A4 | `R` = segment register `(opcode>>3)&3` for `06/0E/16/1E` (pla_3 gives them an all-zero vector) | 3.2 | a PUSH-sreg form writing the wrong register |
| A5 | `M` = GPR `opcode & 7` for `40-5F`, `90-97`, `B0-BF` | 3.2 | same |
| A6 | segment-prefix decode `26/2E/36/3E → (b>>3)&3` | 8 | a segment-override form using the wrong segment |
| A7 | `SR == SS` accesses are word-wide regardless of operand width | 7 | a byte-width instruction whose microcode touches the stack |
| A8 | `M`/`R` as a **source** on a memory operand returns OPR; `-> M` stages into OPR | 8 | a form that must read memory twice from one binding |
| A9 | `PC` is the microcode-visible "next unconsumed byte" pointer, separate from the BIU fetch pointer | 8 | any branch form; all green |
| A10 | `ONES` = 0xFFFF, `ZEROS` = 0, `dir*sz` = ±1/±2 from DIR and operand width | 8 | `dir*sz` is confirmed by `008C`; `ONES`/`ZEROS` are named in the PAS |
| A11 | `AL:AH` (Source1 0x10) is the byte-swapped AW | 8 | AAA/AAS/ROL4/XLAT would break; all green |
| A12 | word memory accesses wrap the **offset** at 16 bits inside the segment | 8 | `tests/v30/v0.3-f4a-boundary` (S2) |
| A13 | unlisted memory reads as 0x00 | 8 | suite-artifact management only |
| A14 | `F` is a bus interlock (delivers a completed read into OPR), not a flag control | 8, 18.1 | a row that consumes read data with no `F` and no pending write |
| A15 | `SUSP` = logged no-op; `FLUSH` = clear queue and refetch from CS:PC | 8 | the queue gate (deferred) |
| A16 | `OP8` (imm-is-one-byte) membership is `byte_operand ∪ {0x83, 0x6B}` | 10 | no dumped column separates that pair |
| A17 | the ALU **status latch** loads on every row that gates SIGMA onto the bus | 14.1 | a `JMP` on a condition set by a row that does not read SIGMA |
| A18 | `NS` is a direct sign tap on `tmpb` at the operand width | 14.2 | a `JMP NS` whose answer differs from sign(tmpb) |
| A19 | the repeat-prefix → data-test polarity map (`F3/F2` → Z, `65/64` → CY) | 15 | not in any dump |
| A20 | `[-1E-]` = ABS and loads the sign latch; `[-0C-]` toggles it by sign(tmpb); `[-09-]` tests it clear | 16 | signed MUL/DIV results |
| A21 | the `MUL` / `DIV` micro-step algebra (shift-add; **restoring** division) | 16.1 | any `F6.4-7`/`F7.4-7`/`69`/`6B`/`D4` case, incl. undefined flags |
| A22 | `ADJD`/`ADJA` **arm** a mode that the following `ADD`/`SUB` executes | 17.2 | the four native BCD blocks |
| A23 | write-data **pairing**: a posted write runs as soon as OPR carries a value that no earlier write has already consumed. §27 *refines* this — freshness is consumed not only by a write's data phase but by **any** read of OPR as a Source1/Source2 operand, so the two paragraphs describe one rule with two consumers, not two rules. The implementation (`opr_fresh_`) has a single clear site per consumer | 18.2, 27 | PUSHA vs. ENTER pin the write consumer from both sides; the BCD strings 02D4/02D7 and INS 032B/032F pin the source consumer |
| A24 | `SR = IO` means the **zero segment** except for pla_3 `XOP` 1111 / 0110 | 18.3 | INT vector fetch vs. `E4/EC` |
| A25 | the ALU latch at instruction entry is `ADD tmpa` plus the synthetic EA constant | 21 | `D7` XLAT |
| A26 | `ALU BIT` captures the index at its own row and masks port B of the **next** latched op only | 23.1 | a `0F 1x` form needing the unmasked operand |
| A27 | an ADJx arm not consumed by an `ADD`/`SUB` **discharges** as a plain truncation into its operand | 26.2 | only one ROM row (`030B`) takes this path |
| A28 | the bit-field group's byte register binding is keyed off ext `XOP = 0011` | 23.4 | another ext block needing byte registers, or `0F 30-3F` aliases with `mod != 3` |

Still-no-op microcode codes at P1 (no scoped form observed them, so they were
assumptions by omission): `ENDEM`, `MFC`, `MFS`, Ext `[-03-]`/`[-05-]`,
Int `[-0A-]`.  Ext `[-03-]` (`01ED`) and Ext `[-05-]` (`01DC`/`01E0`/`01E2`)
were read as the **interrupt-acknowledge** bus cycles.  Dest2 `[-03-]` **is**
resolved: it is a sink that still gates SIGMA onto the bus, i.e. a
status-latch-only write (§14.1).

> **Corrected at S2a.**  Three of the P1 claims above were wrong or stale.
> (a) The P1 list also named Int `[-0B-]`, Dest1 `[-09-]/[-0A-]/[-0B-]` and
> Source1 `[-05-]/[-0B-]`; **no ROM row uses any of them**, so they are not
> assumptions at all — they are unused encodings (§39).  (b) `MFS` and Int
> `[-0A-]` were *already* being executed at P1 — `MFS` on `01F6` by every
> software `INT`/`INT3`/`INTO`/`CHKIND`/divide trap, Int `[-0A-]` on `006D` by
> `POLL.LO`/`POLL.REL` — and those forms were green with both modelled as
> no-ops, so they are *executed-inert*, not unobserved (§39).  (c) Ext
> `[-03-]` is likewise executed by every software INT (it sits on `01ED`,
> inside the SHARED `INT` routine, not in the acknowledge banks), which
> **falsifies** the "INTA-with-hold" reading: an acknowledge bus cycle there
> would be an acknowledge on `INT 21h`.  §35 settles both Ext codes.

## 31. `--alu-hw-report`: how much of the PSW the microcode does NOT determine

`sim/v30sim run <rom> --alu-hw-report` (driver: `sw/ucsim_smoke.py --alu-hw`)
attributes each case's **final** PSW bits to the three flag behaviours that are
*not* emergent — they live in the C++ ALU hardware model:

1. the per-**step** shift/rotate overflow law (`alu_step`),
2. the logic ops' `AC = 0` (`alu_eval`),
3. the fitted BCD correction (`bcd_adjust`).

A bit is booked to a behaviour only while that behaviour's write is the *last*
one to have touched it, so what the report counts is the hardware model's
contribution to the state the golden actually compares.

Whole v0.2 suite, 347 000 cases:

| behaviour | flag commits | cases keeping a bit | final-PSW bits |
|---|---:|---:|---:|
| per-step shift/rotate V law | 2 118 140 | 46 412 | 46 412 |
| logic-op `AC = 0` | 37 000 | 37 000 | 37 000 |
| BCD correction | 9 939 | 4 000 | 24 000 |
| **any** | | **87 412 (25.19 %)** | **107 412** |

So **74.8 % of v0.2 cases end with a PSW every bit of which came out of the
microcode**, and of the 2 082 000 architectural flag bits compared across the
suite, 107 412 (5.2 %) are attributable to the three hardware laws.  The BCD
row is the sharpest illustration: `0F 20` runs 1 983 corrected flag commits per
1 000 cases and **none** of them survive — the tail at `02DF` (§25.2) overwrites
the whole PSW, so ADD4S's architectural flags are pure microcode.

Everything else in `docs/facts/undefined_flags.md` that S1a-S1c touched is
**EMERGED** (§17 scorecard, plus TEST1's masked S/Z/P and the BCD-string
`S = AC = CY, P = Z, V = 0` law at §23.1 / §25.2).

## 32. Residual uncertainties carried out of P1

| # | item | why it is open | route |
|---|---|---|---|
| R1 | **byte-shifter hidden high byte** (S1b item 1) — `alu_step` keeps `tmpb`'s high half across a byte-width shift (`hi_keep`).  No scoped form reads it back at word width, so the real chip's high byte during a byte shift is unobserved | no golden discriminates | S2 (`v0.3`, `v20suite`) |
| R2 | `BUSY` and `INTR` micro-conditions are hard-FALSE | no pin model | S2 pin-event forms |
| R3 | the `iord=` case-name field is **replayed**, not predicted — `E4/E5/EC/ED` are exact only as inputs | there is no I/O model | permanent policy |
| R4 | the S0a **ambiguous micro-address** `111.00000010.00` (two matching banks; first-match-wins) — structurally the INTA vector-fetch routine vs. its 8080/BRKEM variant | no scoped form reaches page 7 opcode 02 | S2, with §30's Ext `[-03-]`/`[-05-]` |
| R5 | final **queue** comparison is deferred: the functional model fetches on demand | needs the timing model | timing campaign |
| R6 | `0F 20/22/26` with **CL = 0** underflows `JMP CNTZ` into a ~2^n-iteration loop | the v0.2 tranche excludes it (as does the V20 suite) | S2 / `undocumented_0f.md` |
| R7 | the measured "**Z accumulates on the PRE-adjust bytes**" clause of the ADD4S law (`docs/facts/undefined_flags.md`) is not discriminated by the v0.2 tranche; the simulator accumulates `[-0D-]` on the post-adjust byte and is 3000/3000 | needs a case whose adjusted byte is 00 while the raw ADC byte is not, as the only non-zero pair | S2 (`v0.3`) — falsifier is a directed case |
| R8 | `0F 30-3F` **alias forms with `mod != 3`** (memory bit-offset/length operands) are absent from v0.2, so the byte-register binding of §23.4 is untested against a memory r/m | suite coverage | S2 (`v0.3` / `v20suite`) |
| R9 | b6's **mechanism** — mode-gated consumer versus a separate ext-page fetch-enable term the dumps do not expose | the dump has no such column | die/PLA re-read (`pla_model.md` "cheapest next experiments") |
| R10 | 8080-emulation pages (`ENDEM`, `MFC`/`MFS`, `BRKEM`) remain unexecuted | not a victory gate (user decision) | opportunistic, `t30-brkem` bank |

---

# S2a — the pin-event pseudo-forms, the production checker, gates G-A / G-C

Scope: the eleven forms P1 left out (`INT.90`, `INT.B8`, `INT.9D`, `INT.8ED0`,
`INT.8ED8`, `INT.F3AA`, `INT.FB`, `NMI.90`, `NMI.B8`, `HLT.INT`, `HLT.NMI`),
the production checker `sw/ucsim_check.py`, and the G-A / G-C gates.  The
behavioural reference is `docs/facts/interrupt_model.md`.

## 33. The external-event entry points are HARDWARE addresses — **ROM (structural) + ASSUMPTION (A29)**

Nothing in the ROM *jumps* to the interrupt routines from outside; three
micro-addresses in page 7 are only reachable if the pre-decode hardware forces
the micro-PC there instead of running the loader.  The ROM makes which ones
unambiguous:

| entry | rows | what the rows say |
|---|---|---|
| `111.00000000.00` loc 0 | `01D8 CONST -> tmpbL 1` / `01D9 FARJMP INT` | vector **1** — the BRK / single-step trap |
| `111.00000000.00` loc 2 | `01DA CONST -> tmpbL 2` / `01DB FARJMP INT` | vector **2** — **NMI** |
| `111.00000010.00`       | the two `[-05-]` acknowledge banks (§34) | the **INT pin** |

`CONST 1` and `CONST 2` are the architectural trap and NMI vectors, and the
`02` bank is the only place in the ROM that issues an acknowledge cycle, so the
assignment is forced by the ROM even though no dumped asset names the
entry-address generator.  `sim/exec.cpp::Cpu::interrupt(EventKind)` implements
exactly these three.  `F4` HALT, by contrast, has **no bank at all** — no
activation pattern in the whole ROM matches opcode `F4` in any native page — so
HALT is pure pre-decode hardware, which is precisely what the measured HALT
display law says ("HALT never enters the bus-commit machinery",
`docs/facts/interrupt_model.md`).

## 34. R4 RESOLVED — the ambiguous micro-address `111.00000010.00` — **MEASURED**

`v30sim info` reports **exactly one** ambiguous address in the 8192-entry
micro-address space, and it is this one.  Two activation patterns match it:

```
------- 111.00000010.00 <internal> 02        (bank A, first in ROM order)
01DC AX     -> tmpc            CTL SUSP  [-05-] IO      <- ONE acknowledge
01DD OPR    -> AX          F   CTL
01DE AL:AH  -> tmpbL           CTL                      <- vector = HIGH lane
01DF tmpc   -> AX              CTL FARJMP INT           <- AW restored

------- 111.00000010.00 <internal> 02        (bank B, second in ROM order)
01E0 ZEROS  -> IND             CTL SUSP  [-05-] IO      <- acknowledge 1
01E1 OPR    -> tmpb        F   CTL
01E2 ZEROS  -> IND             CTL       [-05-] IO      <- acknowledge 2
01E3 OPR    -> tmpb        F   CTL FARJMP INT           <- vector = LOW lane of #2
```

**Silicon runs bank B.**  Two independent discriminators, both from the golden
records themselves:

1. **Cycle count.**  `tests/v30/v0.1/INT.90` idx 0 shows *two* `INTA` bus cycles
   (rows 6-11 and 13-20 of its `cycles` array), matching bank B's two `[-05-]`
   rows.  Bank A has one.  This is the same "INTA2 T1 = INTA1 T1 + 7" the
   interrupt model measured directly.
2. **Which lane the vector comes off.**  The acknowledge data in the trace is
   `0x00FF` — `0xFF` on AD7:0, `0x00` on AD15:8.  Bank B takes `OPR -> tmpb`
   and §36's `ZEROS -> tmpbH` keeps the **low** byte → vector `0xFF` → vector
   table at `0x03FC/0x03FE`, which is exactly where the golden's `MEMR` cycles
   go.  Bank A routes the read through `AL:AH -> tmpbL`, i.e. the **high** byte
   → vector `0x00` → table at `0x0000`.

**Falsifier, run:** forcing bank A (`rom_.bank_of(..., /*emu=*/true)`) takes
`INT.90` from 200/200 to **0/200**, every case failing as `ip exp=58E2
got=0000`; `NMI.90` (which never enters the `02` bank) and `CD` (software INT)
stay 200/200 and 500/500.  The discriminator is sharp and confined to the
INT-pin forms.

**The selection rule** — this is the part that is *not* measured.  The 13 dumped
address bits cannot separate the two patterns, and a silicon decoder cannot
drive two banks onto one output.  So the decoder takes a **14th input**, and the
only distinction the two banks make is an 8080-flavoured one (bank A saves and
restores AW around the acknowledge and takes the byte off the high lane, which
is how the 8080/BRKEM pages move data).  The simulator models it as a
`bool emu` argument to `UcRom::bank_of` — native mode takes the second bank,
emulation mode the first — and, since this is the only ambiguous address in the
ROM, that argument is inert everywhere else.  The alternative reading (a fixed
priority encoder that always picks the later pattern, with bank A dead silicon)
is not excluded by anything we hold; distinguishing them needs a `BRKEM`
capture, which is R10 territory.  Booked as **A30**.

## 35. Ext `[-05-]` and Ext `[-03-]` — **RESOLVED**

`[-05-]` is the **interrupt-acknowledge bus cycle**.  It appears only on `01DC`,
`01E0` and `01E2` — inside the two acknowledge banks — always with `SUSP` and
`SR = IO`.  In the model it behaves as an ordinary read: the acknowledge data
enters the read queue and the following `F` row delivers it into OPR
(`01E0`/`01E1`, `01E2`/`01E3`).  That the delivery works through the ordinary
`F` interlock is *verified*, not assumed: a wrong delivery (dropping the first
acknowledge, or delivering it twice) puts the wrong word in `tmpb` and the
vector-table read lands somewhere other than `0x03FC`, which all 2200 INT-pin
golden cases would catch.

`[-03-]` is **NOT** the acknowledge's second half, contrary to the P1 reading.
It sits on `01ED`, inside the routine `FARJMP INT` reaches — the routine every
`INT n` / `INT3` / `INTO` / `CHKIND` trap / divide trap also runs.  Those forms
are architecturally exact (7 500 cases over `CC`/`CD`/`CE`/`CF`/`62` in
v0.1+v0.2) with `[-03-]` modelled as a no-op, so whatever it drives has **no architectural
consequence**; it cannot be an acknowledge, because `INT 21h` does not
acknowledge anything.  The remaining readings are bus-control (the acknowledge's
trailing hold / a `BUSLOCK` release, which the row's `SUSP` company would fit) —
a timing-campaign question.  Modelled as inert and booked as **A31**.

## 36. The shared `INT` routine, walked — **ROM**

Reached by `FARJMP INT` (far index 2 → page 7, opcode `0x10`) from *all* of:
the acknowledge banks, `01D9`/`01DB` (trap 1 / NMI 2), `0105`/`0108`/`010F`
(`INT3`/`INT n`/`INTO`), `0195`/`01A9` (divide overflow, vector 0), `0283`
(`CHKIND`, vector 5).  One routine, one set of pushes:

```
01EC ZEROS -> tmpbH        ALU ADD tmpb      vector byte only; latch ADD
01ED SIGMA -> tmpb    SUSP [-03-] IO         tmpb = 2*vector
01EE SIGMA -> IND          MEMR IO           read IVT lo  @ 4*vector   (zero segment)
01EF SIGMA -> tmpb         ALU INC2 tmpb     tmpb = 4*vector
01F0 SIGMA -> IND          MEMR IO           read IVT hi  @ 4*vector+2
01F1 OPR   -> tmpc    F                      tmpc = handler PC
01F2 SP    -> tmpb         ALU DEC2 tmpb
01F3 OPR   -> tmpa    F                      tmpa = handler PS
01F4 FLAGS -> OPR     F                      PSW captured BEFORE CITF
01F5 SIGMA -> tmpb,IND     CITF  MEMW SS     push PSW @ SP-2, then IE=BRK=0
01F6 CS    -> OPR     F    MFS               IND = SP-4
01F9 tmpa  -> CS           MEMW SS           push old PS @ SP-4
01FA PC    -> OPR     F                      IND = SP-6; OPR = the RESUME PC
01FB tmpc  -> PC           MEMW SS           push resume PC @ SP-6
01FC SIGMA -> SP      E    FLUSH             SP -= 6, refetch at the handler
```

Three ROM facts fall out and all three match the measured model:

* **the pushed PSW is the pre-entry value** — `FLAGS -> OPR` at `01F4` runs one
  row before `CITF` at `01F5`, so IE/BRK are still as loaded
  (`docs/facts/interrupt_model.md`: "Pushed PSW = pre-recognition value");
* **the vector fetch is a ZERO-segment access** — `SR = IO` with a non-port
  `xop` (A24), so `4*vector` is a physical address; the golden's `MEMR` rows at
  `0x03FC`/`0x03FE` carry no segment;
* **the push order is PSW, PS, PC at SP-2/SP-4/SP-6** and `SP` lands 6 lower.

**A12 (16-bit offset wrap) is exercised hard here**: 40 v0.1 and 213 v0.2
pin-event cases start with `SP < 6`, so the three pushes wrap the stack offset
through zero (e.g. `INT.90` idx 3: `SP=0x0000`, `SS=0x77BF` → frame at
`0x87BEA/0x87BEC/0x87BEE`, physical addresses that stay inside the segment).
All pass.

## 37. The REP abort is a ROM mechanism, not a model bolt-on — **RESOLVED (ROM)**

The string loops end with `JMP REP <loop>` and fall through to
`COUNT -> CW; FARJMP REPX`.  `REPX` is where the external event is consumed:

```
0220 CX     -> tmpb            ALU PASS tmpb
0221 PC     -> tmpb   SIGMA -> [-03-]   ALU SUB tmpa     status <- CW; tmpb = PC
0222                           JMP Z    4                CW == 0 -> just end
0223                           JMP INTR 5                event pending?
0224                        E  CTL                       normal end
0225 PFXCNT -> tmpa            CTL
0226 SIGMA  -> tmpb            ALU DEC  tmpb             tmpb = PC - PFXCNT
0227 SIGMA  -> PC           E  CTL FLUSH                 PC = PC - PFXCNT - 1
```

`PC - PFXCNT - 1` backs the resume PC over **every** prefix and the opcode byte
— which is the measured "pushed PC = the FIRST prefix byte, no 8086 lost-prefix
bug" law, straight out of the ROM.  `PFXCNT` is used on exactly this one row in
the entire ROM, which is what it is for.

The only exit the string loop has is its `JMP REP`, so the recognition must
enter through that condition: **`REP` continues only while COUNT is non-zero AND
no event is pending**, and `INTR` then reads the same latch at `0223`.  The
simulator implements exactly that (`Machine::intr_pending`, read by `kCondRep`
and `kCondIntr`); everything else — the partial `CW` write-back, the `IY`
advance, the completed element's memory write, the resume PC — is computed by
the ROM.  Booked as **A32**.

`JMP INTR` also appears at `006F`, inside `POLL` (`9B`): a pending event makes
POLL back its own PC up by one and flush, i.e. re-execute after the handler.
Same latch, and the `POLL.LO`/`POLL.REL` tranches (2400 cases) stay green with
it never raised, because no POLL golden fires.

## 38. Policy: the FIRING BOUNDARY is replayed, its consequences are computed

Functional mode does not predict *when* the pin is caught — that is the
cycle-exact recognition pipeline of `docs/facts/interrupt_model.md` (pin@B-3,
IE@B-3, single-boundary shadows, taken-branch flush anchoring), which belongs to
the timing campaign.  It is the same class of deliberate non-modelling as the
`iord=` replay (R3).  **Policy P3:** the boundary the golden recorded is
replayed; every architectural consequence is computed and compared.

Two numbers identify the boundary, both taken from the golden's own record
(`sim/case_runner.cpp::derive_replay`):

| number | source | meaning |
|---|---|---|
| `resume_ip` | the golden's **pushed frame**: the word at final `SS:SP` | the instruction the event preempted.  The simulator retires instructions until its live PC equals it, then enters. |
| `elements` | the golden's **bus trace**: `MEMW` cycles ahead of the first `INTA` row | only for a REP that resumes at its own prefix address: how many string elements completed.  Armed as `set_rep_abort`, consumed by §37's ROM mechanism. |

A case whose golden shows **no frame** (SP unchanged, no PSW word with the V30's
forced `15:12` bits at `SS:SP+4`) did not fire — masked INT, HALT masked-resume,
POLL — and runs as an ordinary single-instruction case.  That predicate is the
same one `sw/check_core.py` uses to decide whether to derive flags from the
pushed PSW, so the checker and the model agree by construction.

What this does **not** hide: the vector, the acknowledge, the table read, the
frame contents, the resume PC, `CW`/`IY` at the abort, the flush, `IE`/`BRK`
after entry and the whole final state are all produced by the ROM and diffed.
`INT.FB` is the sharp case — `EI`'s one-instruction recognition shadow means the
golden's resume PC is *past* the following instruction, so the simulator must
execute that instruction too and must push a PSW with `IE` already set; 400
cases across v0.1+v0.2 agree.

### New assumptions from S2a

| # | assumption | § | falsifier |
|---|---|---|---|
| A29 | the three hardware entry addresses of §33 (INT pin → `111.00000010.00`, NMI → `111.00000000.00` loc 2, BRK/TF trap → loc 0), and that `F4` HALT has no microcode at all | 33 | a pin-event form landing on the wrong vector; `HLT.INT`/`HLT.NMI`/`HLT.RES`, 3 600 cases, exercise the HALT half |
| A30 | the `111.00000010.00` bank pair is selected by an **emulation-mode input** to the micro-address decoder (native = bank B), rather than by a fixed priority with bank A dead | 34 | a `BRKEM` capture reaching page 7 opcode 02 (R10); nothing we hold decides it |
| A31 | Ext `[-03-]` is architecturally inert | 35 | any `INT`/trap form: 7 500 software-INT/trap cases plus 13 200 pin-event cases execute it |
| A32 | `INTR` is the recognition latch AND the `REP` continuation's second term | 37 | `INT.F3AA`'s aborted cases: a wrong term gives the wrong `CW`/`IY`/element writes |
| A33 | the hardware presents a **cleared loader context** at an internal entry — in particular `xop`, or the vector fetch's `SR = IO` would be re-classified as a port access (A24) | 40 | directed probe, §40; no golden covers it |
| A34 | the acknowledge data is the harness constant `0x00FF` (CFG `int_vector`), replayed like `iord` | 35 | the golden traces show it on both `INTA` cycles; a different controller would change the vector, not the mechanism |
| A35 | the final **queue** stays deferred; in its place the bytes the decoder consumed must equal the case's `bytes` | checker | any form whose decode length is wrong; 516 000 cases assert it |

Running total: **35** numbered assumptions (A1..A35).  Policy entries: 3
(queue deferral, `iord` replay, pin-event boundary replay).

## 39. The "assumption by omission" list, cleaned up

| code | rows | status after S2a |
|---|---|---|
| Ext `[-05-]` | `01DC`, `01E0`, `01E2` | **RESOLVED** — the acknowledge cycle (§35) |
| Ext `[-03-]` | `01ED` | **EXECUTED-INERT** — 20 700 green cases run it (§35, A31) |
| `MFS` | `0091`, `01D4`, `01F6` | **EXECUTED-INERT** on `01F6` (every INT/trap form, same 20 700 cases); `0091`/`01D4` unreached |
| Int `[-0A-]` | `006D` | **EXECUTED-INERT** — `POLL.LO`/`POLL.REL`, 2400 green cases |
| `ENDEM` | `03FD` | unreached (8080 page, R10) |
| `MFC` | `0093` | unreached (INTEM bank, R10) |
| Int `[-0B-]`, Dest1 `[-09-]/[-0A-]/[-0B-]`, Source1 `[-05-]/[-0B-]` | *none* | **not assumptions** — no ROM row uses these encodings at all.  The P1 text listed them in error. |

"Executed-inert" is a weaker claim than "resolved" and a much stronger one than
"unobserved": the code runs on every one of thousands of green cases, so it has
no architectural effect, but what it *does* drive (bus control, most likely) is
unknown and is timing-campaign work.

## 40. The `xop` inheritance trap — **found in review, closed by directed probe**

`Cpu::sr_is_io()` classifies an `SR = IO` access as a port access from
`Machine::xop`, the pla_3 group of the instruction the **loader last decoded**.
A hardware interrupt entry runs no loader, so without an explicit reset `xop`
survives into page 7 — and the shared INT routine's vector fetch (`01EE`,
`01F0`) is an `SR = IO` access.  Interrupting an `IN`/`INS` opcode (`xop` `1111`
or `0110`) would therefore send the vector-table read into the **I/O space**.

No golden covers it: every pin-event anchor is `90`, `B8`, `9D`, `8E D0`,
`8E D8`, `F3 AA`, `FB` or `F4`.  So it is closed by a directed probe instead —
`INT.90` idx 0 with its anchor byte rewritten to `EC` (`IN AL,DW`, `xop = 1111`)
and to `6C` (`INSB`, `xop = 0110`), all three variants byte-identical in
handler `PS:PC`, `SP` and the pushed frame:

```
nop                          CS=0000 IP=58E2 SP=7394 frame=(0xb6c7, 0x67c4, 0xf646)
in al,dw (xop = port class)  CS=0000 IP=58E2 SP=7394 frame=(0xb6c7, 0x67c4, 0xf646)
insb     (xop = block I/O)   CS=0000 IP=58E2 SP=7394 frame=(0xb6c7, 0x67c4, 0xf646)
```

**The probe is not vacuous:** deleting the `m_.xop = 0` reset makes the two I/O
variants return `IP=0000` while the NOP variant is unaffected.  The acknowledge
itself is separately protected — `Ext [-05-]` bypasses `sr_segment()`/
`sr_is_io()` entirely (`Cpu::bus_inta`), because an acknowledge has no segment
and no address.  Booked as **A33**.

## 41. S2a result — gates

`sw/ucsim_check.py` is the production checker: `sim/v30sim run --emit-final`
returns final registers, the ordered byte write stream and the consumed
instruction bytes; the checker applies `sw/check_core.py::check_case`'s
architectural policy (sparse-delta registers, metadata flags-masks with
`emit_suite._flags_mask_of` grouped-form resolution, `--raw-flags`, RAM
reconstruction with fallback, the pushed-PSW rule for pin events, `dont_care`
honouring, `known_divergences`, the `iords` sidecar, and check_core's
flat-fail → 64K-mirror retry) and writes a JSON report.

| gate | suite | result |
|---|---|---|
| **G-A** | `tests/v30/v0.1`, 347 forms | **169 000 / 169 000** (1 collision-dependent golden validated on 64K-mirrored RAM, as captured: `0F12` idx 219) |
| **G-A** | `tests/v30/v0.1-w1`, 6 forms | **1 200 / 1 200** |
| **G-A** | `tests/v30/v0.1-w3`, 6 forms | **1 200 / 1 200** |
| consistency | `tests/v30/v0.2`, 347 forms | **347 000 / 347 000** |
| **G-C** | `tests/v30/f4a_boundary` | **160 / 160** |
| **G-C** | `tests/v30/mod3_illegal` | **128 / 128** under the documented stale-EA residue |
| **G-C** | `tests/v30/f0lock_tranche` | **400 / 400** |
| **G-C** | `tests/v30/enter_nesting` | **512 / 512** + **154 / 154** walk streams |

**Wait invariance.**  The w1 and w3 tranches are the same six forms as their w0
counterparts, and the functional model has no wait notion at all — it runs one
identical computation for all three.  All three are green
(`89`,`8B`,`B8`,`E8`,`EB`,`F7.6`: 3000/3000 at w0, 1200/1200 at w1, 1200/1200 at
w3), so the architectural state of those forms is wait-invariant on silicon.
**No wait-dependence was found; there is nothing to report loudly.**  Note the
coverage limit honestly: the wait tranches only exist for six forms, so this is
a *confirmation over those six*, not a suite-wide proof.

**mod3 residue confinement.**  With the residue policy off, `mod3_illegal` is
0/128 and every single failure is `reg_bad == [the ModR/M reg field's register]`
— 16 cases per destination register, no RAM diff, no other register, no length
error.  That is exactly the confinement the tranche's metadata claims: LEA mod3
loads the EU's stale effective-address latch, whose silicon value comes from the
harness's pre-window injection history and which a from-scratch model cannot
have.  Confinement is the gate; the value is not transferable.

**ENTER nesting.**  Replaying `ENTER fsize,nest` with BP pre-loaded and the
NOP-filled image reproduces the chip's stack-region walk write stream
byte-for-byte for all 512 mask-tranche goldens (max 256 pushes at `nest=255` —
the nesting is **not** masked mod 32) and all 154 waited-tranche goldens.  The
waited goldens' walk is wait-invariant on silicon and trivially so in the model,
which is the value-bug invariant `sw/check_enter_nesting.py` gates on.

**Survey-then-fix.**  The full G-A batch was run before any fix.  Exactly one
failure category appeared across 169 000 cases: `0F12` idx 219, a RAM diff at
`0x2713A` — a *collision-dependent golden*, not a model bug.  Its footprint
holds `0x2713A` and `0x5713A` (a `63 C0` preload byte), which alias to the same
cell on the capture board's 64K-mirrored RAM; the chip read `0x63`, cleared bit
1 and wrote `0x61`, while a flat 1 MB model reads the recorded `0x8F` and writes
`0x8D`.  `sw/check_core.py` already handles this class with a `+mirror` retry;
the fix was to port that retry (`Biu::set_mirror`, `v30sim run --mirror`), not
to touch the model or the golden.  No other category was found, so no
survey-then-fix triage was needed.

## 42. Residual updates

* **R2 — `BUSY`/`INTR` hard-FALSE — CLOSED for `INTR`.**  `INTR` is now the
  recognition latch (§37, A32) and drives both the `REPX` abort and `POLL`'s
  re-execute path.  `BUSY` stays hard-FALSE: `POLL.LO`/`POLL.REL` both end with
  the pin low, so no golden ever needs it true, and there is no pin model.
  Re-booked as **R2'** (BUSY only).
* **R4 — the ambiguous micro-address — RESOLVED**, §34.  Which bank silicon runs
  is measured; the *selection mechanism* remains open and is now the numbered
  assumption A30.
* **R5 — final queue deferral** — unchanged, and now paired with the consumed-
  bytes assertion (A35) so the deferral is not a hole.
* **R10 — 8080 pages** — gains a concrete stake: bank A of §34 is (on the A30
  reading) the emulation-mode acknowledge, so a `BRKEM` capture would settle
  A30 as a side effect.

---

# S2b — the mass gauntlet: G-B (`v0.3`) and G-D (`v20suite`)

Scope: the two multi-million-case suites, run under **survey-then-fix**
discipline, preceded by two ordered exposure gates so that a boundary or a
memory-operand failure could not masquerade as an OPR/segment bug downstream.

## 43. Gate order and why

Codex's sequencing for S2b was: (1) the A12 segment-boundary exposure, (2) the
`0F 31/33/39/3B` `mod != 3` memory subset, (3) full `v0.3`, (4) `v20suite`.
Both pre-gates turned out to have no ready-made tranche, and the reason is
itself a finding in each case (§44, §45).

## 44. The A12 boundary exposure — **A12 falsifier DISCHARGED**

A12 (§8) says a word memory access wraps the **offset** at 16 bits inside the
segment.  Its recorded falsifier was `tests/v30/v0.3-f4a-boundary` — which
**was never captured**: the directory holds an `emit_log.txt` and no data.  So
the exposure was *extracted* from the mass suite instead.

`sim/v30sim run --wrap-scan` adds three counters to the BIU (`Biu::note_access`
/ `code_wrap_`) and reports them per case: **near_wrap** = a DATA access whose
offset lands in `0xFFFC..0xFFFF`, **wrapped** = an access that actually took its
second byte from offset `0x0000`, **code_wrap** = the instruction fetch pointer
rolling over.  `sw/ucsim_check.py --wrap-scan <file>` runs a suite in that mode
and writes the subset; it performs **no comparison**, so the gate that follows
is a genuine first look and not a re-reading of results already seen.

| | |
|---|---|
| scanned | 3 700 000 cases (whole `v0.3`), 468.1 s |
| boundary subset | **8 820 cases over 195 of the 370 forms** |
| of which an ACTUAL 16-bit offset wrap | **47** |
| additionally wrapping the code-fetch pointer | 66 |
| **result** | **8 820 / 8 820 arch-exact** (189.7 s) |

The subset is broad: word data operands, both stack directions (`FF.2`/`FF.3`
each contribute ~197 cases), every string form, and all eleven pin-event
pseudo-forms (the interrupt frame's three pushes are what reach the boundary
there).  A12 is therefore no longer an assumption resting on an unbuilt
tranche: it is **MEASURED**, against 8 820 real captures including 47 that
exercise the wrap itself.

## 45. `0F 31/33/39/3B` with `mod != 3` — **R8 RESOLVED**, and a `v0.3` vacuity

R8 asked for the INS/EXT bit-field group with a **memory** r/m, because A28
(§23.4) binds those forms' byte registers off ext `XOP = 0011` and no v0.2 case
had a memory operand.  The route recorded for it was `v0.3`.

**`v0.3` does not discharge it.**  All 40 000 `0F31`/`0F33`/`0F39`/`0F3B` cases
in `v0.3` carry `mod == 3`; the emitter never produced a memory form.  This is
the wait-axis vacuity lesson in a new place: a residual routed to a suite is
not closed by that suite being green.

The coverage exists in **`v20suite`** (~50 % of each form), so the gate was run
there, ahead of G-D, as its own first look:

| form | `mod != 3` cases | result |
|---|---:|---|
| `0F31` INS reg8,reg8 | 4 947 | 4 947 / 4 947 |
| `0F33` EXT reg8,reg8 | 5 010 | 5 010 / 5 010 |
| `0F39` INS reg8,imm4 | 4 947 | 4 947 / 4 947 |
| `0F3B` EXT reg8,imm4 | 5 010 | 5 010 / 5 010 |
| **total** | **19 914** | **19 914 / 19 914** (9.7 s) |

A memory-`M` INS/EXT stresses binding, pre-read, OPR and write-back in one
instruction, and all four are exact.  **R8 is CLOSED and A28's falsifier is
discharged** — the byte-register binding does not depend on the r/m being a
register.

## 46. The V20 suite's port-read replay — **POLICY (R3), extended**

R3 is standing policy: there is no I/O model, so the value a port presented is
**replayed** from the capture.  The V30 suites encode it two ways (the case name
`iord=XXXX`, or an `iords/` sidecar built by `sw/extract_iords.py`).  The V20
SingleStepTests suite encodes it a third way — **in its own bus trace** — and
two consequences fell out:

1. `sw/extract_iords.py` looks for `r[7] == "IOR" and r[8] == "T3"`, which never
   matches: **both** trace conventions stop labelling the bus status at T2, so
   the data column has to be taken off the row that *follows* an IOR cycle at
   T3.  `sw/ucsim_check.py::iords_from_cycles` does that.
2. `v0.3`'s eight **REP-INS** forms (`F36C`…`656D`) had no sidecar at all; they
   were generated with `sw/extract_iords.py` (0 ambiguous cases over 80 000
   cases / ~297 000 IORs) before G-B ran.

**The extraction is load-bearing, not decorative.**  With it removed,
`v20suite` `E4`/`E5`/`EC`/`ED` are **0 / 40 000** (`in al,4Bh`: `AX` exp `52FF`
got `5200`); with it, 40 000 / 40 000.

The µPD70108 has an **8-bit** bus, so a word port read is two byte cycles while
the simulator's port model is one 16-bit `src` word with a parity-selected lane.
The fold is `lo | hi << 8` for a word and the byte **replicated on both lanes**
for a byte (replication is what an 8-bit bus physically does).  Every one of the
~200 000 IOR cycles in the V20 suite carries `0xFF`, so both lanes are equal and
the lane transform is provably inert; the checker counts word reads whose two
byte cycles disagreed and reports them — **0 in 3 125 000 cases**.  Booked as
**A36**.

## 47. G-B — `tests/v30/v0.3` — **GREEN, first pass**

```
TOTAL ARCH: 3699998/3699998  [2 documented pre-existing excluded]  (526.9s)
```

370 forms, 3 700 000 cases.  **Zero failures**, so survey-then-fix found nothing
to triage and no fix was made: the model that entered S2b is the model that left
it.  Zero collision-dependent (64K-mirror) rescues were needed anywhere in
`v0.3` — the one in `v0.1` (`0F12` idx 219) remains the only case of that class
in the campaign.

**`known_divergences.json` is now read by CLASS, not as a flat exclusion list.**
The file tags each case `VOID` (a contaminated *capture* — a ram-vs-instruction
physical collision, so the golden is not a statement about the chip) or `EDGE`
(a genuine but known pre-existing **cycle** edge, explicitly recorded
"arch-CLEAN").  This checker compares architectural state only, so excluding an
EDGE case would silently drop a case the ledger says is architecturally sound.
The checker now excludes only VOID and keeps EDGE in the totals, tracked
separately:

* VOID excluded: `0F1B` idx 3917, `83.5` idx 8683 (2 cases).
* EDGE kept: `646F` idx 8988 (`repnc outsw cx=13`) — **arch-clean, and it
  passes**, so the ledger's "cycle-only" classification is confirmed live
  rather than assumed.

`8F.0`'s `dont_care` entry covers 2 502 cases, so it is not vacuous either.

## 48. G-D — `tests/v30/v20suite` — **GREEN, first pass**

```
TOTAL ARCH: 3125000/3125000  (373.8s)
```

360 forms / 282 metadata opcodes, 3 125 000 cases of **real µPD70108 silicon**
(arduino8088 rig, NEC V20 8902NX D70108C-8), run `--no-mirror` because that rig
is not the 64K-mirrored capture board.  Queue is masked (R5/A35 — the V20 has a
4-byte byte-fetch queue our functional model does not model at all); the
consumed-bytes assertion stands in for it, and it holds on every case.

### 48.1 V20 vs. V30 — **no architectural difference found**

The stated expectation was that the V20 is the SAME EU with an 8-bit BIU, so
architectural behaviour should be identical, and **any** difference would be a
discovery.  Across 3 125 000 cases spanning 282 opcodes there is **not one
architectural divergence** — same microcode ROM, same PLA decode, same C++
hardware laws, no V20-specific branch anywhere in `sim/`.  The only V20-specific
code in the whole campaign is the port-read *fold* of §46, which is a property
of the bus width, not of the EU.  Nothing was routed to `docs/facts/`.

That is a strong statement about the assets: the ROM we hold is dumped from a
V20, and it drives a V30 model that is exact on both parts.

### 48.2 Undocumented / alias opcodes — first empirical test

These forms exist in no V30 suite we emitted; `v20suite` is their first test.
All are exact:

| form | what the suite calls it | cases | result |
|---|---|---:|---|
| `63` | `undef word [ds:bx+4Dh]` — **HAS a ModR/M** | 10 000 | 10 000 / 10 000 |
| `66`, `67` | `fpo2` (FPO2 escape; `66` reg form, `67` memory form) | 20 000 | 20 000 / 20 000 |
| `82.0`…`82.7` | alias of the `80` group | 80 000 | 80 000 / 80 000 |
| `D6` | **`xlat`** — on the V20 `D6` aliases `D7`, it is *not* SALC | 10 000 | 10 000 / 10 000 |
| `F6.1`, `F7.1` | `test` — the undocumented `/1` alias of `/0` | 20 000 | 20 000 / 20 000 |
| `FF.7` | `push` — `FF /7` aliases the `/6` PUSH r/m | 10 000 | 10 000 / 10 000 |
| `8F`, `C6`, `C7` | ungrouped (all `reg` fields, not just `/0`) | 30 000 | 30 000 / 30 000 |
| `0F31/33/39/3B` `mod != 3` | INS/EXT with a memory bit field | 19 914 | 19 914 / 19 914 (§45) |
| `D8`…`DF` | FPU escapes | 80 000 | 80 000 / 80 000 |

`0x63` having a ModR/M and `0x66/0x67` decoding as a two-operand escape were
optable/pla *predictions*; consuming the right number of bytes on 30 000 real
captures is their first empirical confirmation (A35's consumed-bytes assertion
is what makes the length claim a real test rather than a coincidence).

**`F1` is NOT tested here.**  The suite's own metadata classes it
`"status": "prefix"` and emits no file for it, exactly as for `F0`/`F2`/`F3`.
So the optable/pla finding "`F1` = BUSLOCK-alias prefix" is *corroborated by the
suite's classification* and still **untested empirically**.  It stays open.

### 48.3 Coverage the V20 suite adds and does not add

58 forms are V20-only (`41`-`4F`, `51`-`5F` — every INC/DEC/PUSH/POP register
slot rather than one representative; `B1`-`BF`; the alias forms above).  68
forms are `v0.3`-only: **every segment-override form, every REP form, every
string form with a prefix, and all eleven pin-event pseudo-forms** — the V20
suite tests no prefixed instruction at all.  The two suites are complements, not
one containing the other, which is why both are gates.

The V20 tranche also widens the BCD-string loop: `0F20/22/26` run `CL` up to
**238** there versus a maximum of **6** in `v0.3`, so the `R`-loop / `CNTZ`
continuation (§12, §24) is exercised two orders of magnitude deeper.

## 49. Rollups

### 49.1 The raw PSW — the headline sufficiency number

Both mass suites were re-run with `--raw-flags`, i.e. **every metadata
flags-mask disabled and the full 16-bit PSW compared**:

| suite | masked | **raw PSW, no masking** |
|---|---|---|
| `v0.3` | 3 699 998 / 3 699 998 | **3 699 998 / 3 699 998** (489.9 s) |
| `v20suite` | 3 125 000 / 3 125 000 | **3 125 000 / 3 125 000** (371.4 s) |

For reference, 2 299 000 of the 3 125 000 V20 cases carry no flags-mask in the
suite metadata at all, so they were *already* raw; the `--raw-flags` run adds
the other 826 000.  **Not one undefined flag bit is wrong on either part.**

### 49.2 `--alu-hw-report`: what the microcode does NOT determine

`sw/ucsim_check.py --alu-hw` now carries the attribution through the production
checker (the accumulator used to sit behind `--emit-final`'s early return, so
the gates could never contribute to it; fixed in `case_runner.cpp`).

| suite | cases | cases keeping a hardware-owned PSW bit | shift-V bits | logic-`AC` bits | BCD bits |
|---|---:|---:|---:|---:|---:|
| `v0.2` (§31) | 347 000 | 87 412 (25.19 %) | 46 412 | 37 000 | 24 000 |
| `v0.3` | 3 700 000 | **873 999 (23.62 %)** | 463 999 | 370 000 | 240 000 |
| `v20suite` | 3 125 000 | **777 495 (24.88 %)** | 317 495 | 420 000 | 240 000 |

So on ~6.8 million cases across two different parts, **~76 % of cases end with a
PSW every bit of which came out of the microcode ROM**, and the residue is
confined to the same three named hardware laws — the per-step shift/rotate `V`
law, the logic ops' `AC = 0`, and the fitted BCD correction.  The BCD row stays
the sharp illustration: 21.2 M shift-V commits and 336 k BCD commits across the
two suites, of which the BCD ones survive into only 40 000 cases each, because
§25.2's tail overwrites the PSW.

### 49.3 Micro-row coverage — 740 / 1028

`sim/v30sim run --coverage` emits a per-ROM-row execution counter (`bank * 4 +
row`); `sw/ucsim_check.py --coverage <file>` accumulates it across gates and
`--coverage-report <file>` names the rows nothing ever executed.  Union over
every green gate (`v0.1`, `v0.1-w1`, `v0.1-w3`, `v0.2`, `v0.3`, `v20suite`,
`f4a_boundary`, `f0lock_tranche`, `mod3_illegal`):

**740 / 1028 rows executed; 288 never executed.**  Classified:

| n | class | status |
|---:|---|---|
| 184 | the **8080 emulation pages** (`110.*`, `101.*`) | R10 — not a victory gate (user decision) |
| 77 | **trailing dead `CTL` padding** — the 4th row of a bank whose sequence retires earlier | structurally unreachable; no ROM claim |
| 8 | `111.00000011` — the **RESET** sequence (`ZEROS -> DS/FLAGS/ES/SS`, `ONES -> CS`, FLUSH) | no suite resets the part |
| 5 | `9B` **POLL busy loop**: `006F JMP INTR 5`, `0070 JMP 0`, `0071 SUSP`, `0072 PC-1`, `0073 FLUSH` | **R2'** — `BUSY` is hard-FALSE, so the poll loop and its interrupt withdrawal are unreached |
| 4 | `111.00000010.00` **bank A** (`[-05-] IO` acknowledge) | A30 — the emulation-mode acknowledge |
| 4 | the **INTEM** bank (`0090`-`0093`, `MFS`/`MFC`) | R10 |
| 4 | `100.11111111` — **`0F FF` BRKEM** entry | R10 |
| 2 | `01D8`/`01D9` — the **BRK/TF trap** entry (loc 0/1 of the NMI bank) | no golden traps on TF; A29's NMI half (loc 2/3) *is* executed |

The honest reading: **every unexecuted row is accounted for by a named residual
or is structurally unreachable.**  Nothing is unexecuted for want of trying.
Removing R10 (the 192 rows of 8080/BRKEM/INTEM/`0F FF`) and the 77 padding rows
leaves **19 rows** — RESET, the POLL busy loop, bank A, and the TF trap — as the
whole of the campaign's untested ROM surface.

### 49.4 Performance

Below the ~30 min budget with room to spare.  The one change made was payload
slimming: the simulator reads `cycles` only for a pin-event case (the REP-abort
element count), and never reads `hash`, so `sw/ucsim_check.py::_slim` drops both
from non-event cases.  `cycles` is ~70 % of a `v0.3` form's bytes.

| pass | cases | time |
|---|---:|---:|
| `v0.1` (G-A) | 169 000 | 17.7 s (was 28 s) |
| A12 extraction scan | 3 700 000 | 468.1 s |
| A12 boundary gate | 8 820 | 189.7 s |
| INS/EXT `mod != 3` gate | 19 914 | 9.7 s |
| **G-B** `v0.3` | 3 700 000 | **526.9 s** |
| **G-D** `v20suite` | 3 125 000 | **373.8 s** |

The A12 gate's 189.7 s for 8 820 cases is *all* decompression: the subset is
spread over 195 forms, each of which has to be gunzipped whole to select a
handful of cases.

## 50. New assumption from S2b

| # | assumption | § | falsifier |
|---|---|---|---|
| A36 | the V20 port-read fold: an 8-bit bus places every byte on AD0-7, so a byte read is REPLICATED across both lanes and a word read is `lo \| hi << 8` | 46 | a word port read whose two byte cycles differ — the checker counts them; **0 in 3 125 000 cases**, and every IOR cycle in the suite carries `0xFF`, so the lane transform is provably inert here |

Running total: **36** numbered assumptions (A1..A36).  Policy entries: 3
(queue deferral, `iord` replay, pin-event boundary replay).

## 51. Residual updates after S2b

* **A12 — CLOSED as MEASURED** (§44).  Its falsifier tranche was never
  captured; the exposure was extracted from `v0.3` instead — 8 820 boundary
  cases, 47 real wraps, all exact.
* **R8 — RESOLVED** (§45), but *not* by the suite it was routed to: `v0.3`
  emits `0F 3x` at `mod == 3` only.  Closed on `v20suite`'s 19 914 memory-r/m
  cases.  **Lesson repeated: a residual routed to a suite is not closed by that
  suite being green — check that the suite actually contains the discriminator.**
* **R7 — the ADD4S leg CLOSED; SUB4S/CMP4S legs undiscriminated.**  R7 wanted a
  case whose adjusted byte is `00` while the raw ADC byte is not.  `v0.3` +
  `v20suite` contain **ten** such ADD4S cases (e.g. `v0.3` `0F20` idx 1106,
  `CL=1`, src `FE` + dst `9C` -> stored `00`).  On all ten the chip reports
  **`Z = 0`**, and the simulator is exact on all ten at RAW PSW — because
  §25.2's tail (`tmpb + tmpb` at `02DF`) overwrites the accumulated `Z`
  entirely.  So for ADD4S the pre- vs post-adjust distinction is **not
  architecturally observable**, which is why the model was 3000/3000 with the
  "wrong" accumulation.  CMP4S stores no result, so no equivalent probe exists
  in these suites; that leg stays open.
* **R6 — still OPEN, and now known to be un-closable from these suites.**  No
  `0F 20/22/26` case anywhere in `v0.3` or `v20suite` has `CL = 0`
  (`v0.3` `CL` 1..6, `v20suite` `CL` 1..238).  A directed capture is required.
* **R1 — byte-shifter hidden high byte — still OPEN.**  6.8 M cases, both
  parts, raw PSW exact, so nothing contradicts `hi_keep`; but no golden reads
  the high half back at word width, so it remains undiscriminated rather than
  confirmed.
* **R2' — `BUSY` hard-FALSE — now QUANTIFIED**: exactly 5 ROM rows
  (`006F`-`0073`, the POLL busy loop and its interrupt withdrawal) are unreached
  because of it (§49.3).
* **R5 — queue deferral** — unchanged; A35's consumed-bytes assertion now
  carries 6.8 M more cases, including the V20's byte-fetch queue, where it is
  the *only* thing standing between the model and a wrong instruction length.
* **R10 — 8080 pages** — unchanged, and now measured: 192 of the 288 unexecuted
  rows are R10's.
* **NEW: `F1` untested** (§48.2).  The one optable/pla finding S2b was expected
  to test empirically and could not, because the V20 suite classes `F1` as a
  prefix and emits no cases for it.  Routes to S3 (a fuzz sequence can execute
  `F1` directly) or a directed capture.

---

# S3 — the sequence gauntlet: `tests/v30/fuzz_bank`

Everything before this stage injects an architectural state and executes ONE
instruction.  S3 executes **programs**: 3 242 banked fuzz seeds, each a 64 KB
image regenerated bit-for-bit from `(cid, k, ov)`, run from RESET RELEASE
through the load stub, a 24-80 instruction random program and the store stub,
compared against the SOCKET capture of the same image on real silicon.

Driver: `sw/ucsim_fuzz.py`.  Simulator mode: `sim/v30sim image` (new,
`sim/image_runner.cpp`).

## 52. What the image replay actually compares

`sim/v30sim image` takes a 64 KB image, loads it into the 64K-mirrored 1 MB
space the capture board is wired as, runs the ROM's **own RESET sequence**
(`111.00000011`, rows `01D0`-`01D5`) and then executes until the machine halts
or the caller's bus-cycle budget runs out.  Nothing is injected: `CS = FFFF`,
`PC = 0`, `DS/ES/SS = 0`, `FLAGS = 0` all come out of the ROM.  Those 8 rows
were on S2b's unexecuted list ("no suite resets the part"); a fuzz image
replay is exactly the entry they exist for, and 6 of the 8 now execute (the
other two are trailing dead `CTL` padding).

Two streams are compared, both derived by `sw/fuzz_classify.py`'s conventions:

* the **ordered functional bus stream** — CODE fetches excluded (so nothing in
  the comparison depends on prefetch, which the functional model does not
  have), read DATA excluded (it is an input), `INTA` a bare position marker;
* **`chip_arch`** — the twelve `STORE_ORDER` registers off the ordered
  `OUT 0xFE` cycles plus the PSW off the last `PUSH PSW` at `0xFFEC`, read out
  of the SIMULATOR's own bus stream by the same `arch_dump` rules.

`image_sha256` is verified before every replay.  **0 GEN-DRIFT in 3 242
seeds**, so the generator path (`fuzz_campaign.derive_case` -> `build` ->
`check_seq.compose`) is still bit-reproducible at this git revision.

### 52.1 The byte-lane law — **MEASURED, and load-bearing**

The V30 has a 16-bit bus, so an unaligned word access is **two** byte cycles.
The chip drives the whole 16-bit pattern on AD in *both* of them and `UBE`/`A0`
select which lane commits:

| cycle | commits |
|---|---|
| `ube_n == 1` | one byte at `addr` = `data & 0xFF` |
| `ube_n == 0`, `addr` odd | one byte at `addr` = `data >> 8` |
| `ube_n == 0`, `addr` even | `data & 0xFF` @ `addr`, `data >> 8` @ `addr+1` |

Read off the capture directly (`mc1/1023`: `MEMW 0x53B7 ube 0 data 0x4012`
followed by `MEMW 0x53B8 ube 1 data 0x4012` = the word `0x1240` written at an
odd offset), and cross-checked against `hdl/rtl/test_mem.sv`, whose byte lanes
are wired `mem_even <= wdata[7:0]` / `mem_odd <= wdata[15:8]`.  A write is
therefore compared as the `(address, byte)` commits it actually made, which is
lane-exact and never reads the indeterminate lane of a byte cycle.  Getting
this wrong makes every unaligned access look like a divergence.

### 52.2 What is NOT compared, and why

* **`HALT`.**  The halt acknowledge is a status-only cycle with no address and
  no data, and whether the capture even yields a transaction for it depends on
  whether its `T1` was followed by a `T4` before the part parked in `Ti`
  (`extract_txns` only closes a transaction on `T4`).  It is dropped from both
  streams; that a side halted at all is reported separately.
* **the `8F /0 mod3` ghost read's ADDRESS** — the one documented don't-care,
  declared in `tests/v30/v0.1/metadata.json` and honoured by
  `sw/check_core.py::dontcare_cells` for the single-instruction gates.  The
  sequence gauntlet honours it identically and **counts** it: 78 ghost reads
  over 54 seeds, so the entry is not vacuous here either.  Note that in a
  sequence replay the "pre-window execution history" the metadata blames is
  now *inside* the window, so this address is in principle predictable — an S4
  question, not an S3 one.

## 53. A37 — Ext `[-03-]` forces WORD bus width — **RESOLVED (MEASURED)**

The model that entered S3 forced word width for every `SR = SS` and every
vector fetch, on the reading "stack accesses and interrupt-vector fetches are
word-wide regardless of the instruction's operand width".  The fuzz bank
**falsifies** that: the undefined byte members of the `FE` group — `FE /2`
(CALL near), `FE /3` (CALL far), `FE /6` (PUSH r/m) — push a single **BYTE** on
silicon.  `raw` seeds hit them constantly; e.g. `FE 31` (`/6`, PUSH r/m8)
writes one byte at `0x3EFE` with `ube_n = 1`.

Removing the forcing outright breaks the other end: the **byte `DIV`
divide-error trap** (`F6.6`/`F6.7`, 625 `v0.1` cases) reaches the shared `INT`
routine with `OP8b` still set and pushes three **WORDS**.

The discriminator that separates them is in the ROM.  The divide trap's path is
`019C ... FARJMP IDIV -> 01A9 FARJMP INT`, and the INT routine's first row pair
is `01EC`/`01ED` — and `01ED` carries **Ext `[-03-]`**.  `CALLF`, `RETF`,
`PUSHA`, `POPA`, `ENTER` and the `FE`/`FF` group's own stack rows do **not**.
So:

> **`[-03-]` sets a WORD-width override for the rest of the micro-sequence.**
> Every bus row after it — the two vector-table reads and the three frame
> pushes — runs word-wide whatever the interrupted instruction decoded.
> Cleared by the next instruction decode.

This *replaces* the S1 assumption rather than adding to it: the old rule was a
description of the outcome for the forms then in scope, this is the mechanism.
It also retires `[-03-]`'s "inert" booking (A31): the code is not inert, it was
*unobservable* until a byte-width instruction reached an internal stack routine
**without** passing through `01ED`, which only the undefined `FE` group does.

**A37**, falsifier: any form that executes `01ED` and then writes a byte to the
stack, or any `FE`-group form that writes a word.  `v0.1` 169 000 / `v0.2`
347 000 re-verified green with the new rule.

## 54. The `[-06-]` write-back strobe binds to the DESTINATION

`[-06-]` was modelled as "commit OPR to the r/m operand `M` when `M` is
memory", which is correct in native mode because `M` is the only operand that
*can* be memory.  8080 mode breaks that: `MOV M,r` and `MOV r,M` put memory on
either side of the same micro-bank (`0350`-`0352`).  The strobe is therefore
re-bound to an explicit `Machine::WB` reference — `WB = M` in native mode,
`WB = R` (the destination field) in 8080 mode.  Native behaviour is unchanged
by construction and re-verified on `v0.1`/`v0.2`.

## 55. 8080 emulation mode — IMPLEMENTED (R10)

R10 was carried for two stages as "not a victory gate".  S3 forced it: **169
of the 403 F-A failures at the half-way point were seeds that had entered 8080
mode**, because raw byte-soup hits `BRKEM` constantly and, once the mode flag
is clear, every following opcode decodes differently.  Implementing it was the
single biggest failure class, not an optional report.

What the ROM gives, walked:

* **`0F FF` BRKEM** (`0348`-`0349`): `Q -> tmpbL` (the imm8 vector),
  `CONST -> COUNT 1`, `FARJMP INTEM`.
* **`FARJMP INTEM`** does not land on `0090`; it lands on **`01EC`**, i.e. the
  *shared INT routine*, because `INTEM` = far-target 3 = page 7 opcode `0x18`
  and the INT routine's first bank `111.0001?000.00` is shared between opcodes
  `0x10` and `0x18`.  BRKEM therefore runs the ordinary vector fetch and frame
  push.  Only the third bank differs: opcode `0x10` (INT) gets `01F4`-`01F7`
  with `CITF`; opcode `0x18` gets `0090`-`0093`, which does **not** clear IE
  and instead does the mode switch.
* **the switch itself** is `0092 JMP CNTZ 12` over `COUNT`: BRKEM entered with
  `COUNT = 1`, so `CNTZ` decrements it to 0, the jump is NOT taken, and `0093
  MFC` runs -> **MD = 0, 8080 mode**.  `CALLN` (`ED ED`, `0400`-`0401`) enters
  with `COUNT = 0`, `CNTZ` sees `0xFFFF != 0`, jumps over `0093`, and the `MFS`
  already executed at `0091` leaves the part **native**.  One shared routine,
  one counter, both directions.  Nothing about this was modelled before; it all
  falls out of the ROM.
* **`ED FD` RETEM** (`03FC`-`03FE`): read `[SS:SP]`, `ENDEM`, `FARJMP IRET`.
* `MFS` (`0091`, `01D4`, `01F6`) sets MD; every interrupt entry and RESET
  therefore returns the part to native mode, which is why an `MFS` on `01F6`
  looked "executed-inert" for two stages.

What the ROM does **not** give, and had to be modelled as loader hardware —
each read off the microcode where possible:

| item | how it was fixed | ledger |
|---|---|---|
| register map | `EB` is `BX <-> DX`, `F9` is `BX -> BP`, `E9` is `BX -> PC`, `LDAX B/D` is `R -> IND` => HL=BX, DE=DX, SP=BP, BC=CX; A=AL from `SIGMA -> AL` | **A38** |
| operand fields | `MOV` is `M -> tmpa` / `tmpa -> R` => M = opcode bits 2:0 (source), R = bits 5:3 (destination), code `110` = memory at `DS:BX` | **A38** |
| pair vs byte `R` | `pla_3` `kMode8080`'s `ByteOnly` column, plus `STAX`/`LDAX` (`02/0A/12/1A`), whose data is a byte but whose `R` is a pointer pair | **A38** |
| micro-page | `110` for the main table, `101` for the `ED` page | ROM |
| `ALU OPC` order | 8080 group order ADD ADC SUB SBB ANA XRA ORA CMP, a different permutation of `kStrOp` than the native ADD OR ADC SBB AND SUB XOR CMP the same field selects; the rotate block `07/0F/17/1F` keeps the native ROL/ROR/RCL/RCR | **A39** |
| `JMP OPC` | the 8080 condition bank: opcode bits **5:3** = NZ Z NC C PO PE P M (native reads bits 3:0) | **A40** |
| `ENDEM` | modelled as "return to native", exact whenever the BRKEM frame carried MD = 1 — which it always does, because `0090` pushes FLAGS *before* `0093` clears the flag | **A41** |

Result: **+96 F-A seeds** and 153/176 of the `110` page plus 5/8 of the `101`
page now execute (§62).

## 56. F-A — the gate

`python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw` (22 s for all four banks,
3 242 seeds, 16 workers):

| bank | seeds | exact | arch compared | note |
|---|---:|---:|---:|---|
| `mc1` | 1 295 | **1 256** | 1 072 | |
| `mc2` | 1 294 | **1 243** | 1 048 | |
| `t30-raw` | 568 | **374** | 3 | raw byte soup; almost no seed reaches the store stub inside the capture window, so this bank is a pure write-stream gate |
| **F-A total** | **3 157** | **2 873 (91.0 %)** | **2 123** | |
| `t30-brkem` (F-B) | 85 | **76 (89.4 %)** | 2 | |

* **0 GEN-DRIFT**, 0 regeneration errors.
* **Split the banks by whether the CAPTURE recorded an architectural dump at
  all, and the picture sharpens completely:**

| | seeds | exact |
|---|---:|---:|
| capture reached the store stub (`chip_arch` present) | 2 125 | **2 125 (100 %)** |
| capture did not (window ran out / program wandered) | 1 117 | 824 (73.8 %) |

  **Every single banked seed whose capture recorded a complete architectural
  dump is register-exact, PSW-exact AND write-stream order-exact.**  2 125 of
  them, across all four banks, including 1 048 `mc2` and 1 072 `mc1` seeds
  spanning every wait axis.  Not one register, not one PSW bit, not one
  transaction out of order.  There is no ARCH-only failure anywhere: the
  architectural outcome never diverges independently of the bus stream.
* Every one of the 284 F-A failures is therefore a seed whose *chip* run never
  completed — raw byte soup that wandered off, or a capture window that ran out
  mid-program — so the comparison there is a bus-stream **prefix** match with no
  architectural anchor at its end.
* the four `soup`-tier failures are all the same shape: the PSW pushed by an
  interrupt frame differs in the **P** bit, i.e. a state divergence that
  produced no observable bus event before the frame.

### 56.1 Wait-axis: no wait-dependence found

The banked seeds span `w0`, `w1`, `w2`, `w3` fixed and `wmax` 1/2/3/7/15
random.  The simulator has **no wait input at all** — it computes one
functional stream per image — so any wait-dependence in the chip's functional
outcome would appear as a pass rate that collapses in one wait class:

| axis | exact | | axis | exact |
|---|---|---|---|---|
| `w0` | 738/852 | | `wrand1` | 481/532 |
| `w1` | 167/178 | | `wrand2` | 435/461 |
| `w2` | 159/168 | | `wrand3` | 355/378 |
| `w3` | 175/194 | | `wrand7` | 194/215 |
| | | | `wrand15` | 169/179 |

86-95 % everywhere, and the *worst* class is `w0` (which carries the highest
share of raw-tier seeds).  **No counter-example to functional wait-invariance
exists in the bank.**  This is not a controlled A/B — the wait axis and the
program are drawn from the same seed, so no two banked seeds run the same
program at different waits — and that limitation is itself worth recording: a
controlled wait-invariance tranche would need a re-emission, not a re-analysis.

### 56.2 The 284 F-A failures, categorised (survey-then-fix, third pass)

| n | class | reading |
|---:|---|---|
| 70 | **8080-mode residue** (`mfc > 0`) | the mode is implemented and 96 seeds were recovered by it, but 8080 execution paths still diverge somewhere; each is a *raw* program running arbitrary 8080 code |
| 4 | `soup` tier | the pushed-PSW `P` bit (above) |
| 210 | `raw` tier, native | long tail: no instruction context accounts for more than **5** seeds, and the modal shape (88 of them) is a write at the RIGHT address with the WRONG byte — i.e. a register/flag value that diverged earlier without emitting a bus event.  46 of the 284 hit the simulator's own instruction budget or a runaway micro-sequence, which is what a wandering raw program looks like from this side |
| 0 | GEN-DRIFT | — |
| 0 | arch-only | — |

Three mechanism-level fixes were made during the survey and each was re-run
against the full banks and against the single-instruction gates: the boundary
replay of §57, A37 (§53), and 8080 mode (§55).  They moved F-A from 1 979 to
2 873.  The remaining tail is **not** a single mechanism: it is spread across
~200 distinct instruction contexts in random byte soup, which is the regime
where undefined encodings, self-modifying writes into the prefetch window and
8080 excursions all coincide.  Deliberately **not** chased instruction by
instruction — that is a hunt, not a mechanism.

## 57. Interrupt interleaving (F-C) — the firing boundary needs TWO coordinates

The S2a policy (§38) is "replay the boundary, compute the consequences".  In a
single-instruction case the boundary is named by the golden's pushed `IP`.  In
a **sequence** that is not enough, and neither is the obvious alternative:

* a **bus-stream position** (how many bus cycles preceded the acknowledge)
  cannot separate two instruction boundaries with no bus access between them —
  the load stub's run of register `MOV`s is a dozen such boundaries, and the
  first model fired the interrupt at the wrong one on 602 seeds;
* the **recorded resume CS:IP** alone cannot separate a string instruction's
  start boundary from the mid-string withdrawal that rewinds PC back to exactly
  that address.

Together they are unambiguous, and that is the policy now: **fire at the first
instruction boundary at or after the recorded bus position whose live `CS:PC`
is the `CS:IP` the chip's own frame pushed.**  Both coordinates are read out of
the capture; every consequence — acknowledge, vector fetch, frame, resume,
mode flag — is computed from the ROM.

Mid-instruction recognition is implemented where the ROM puts it: `Cpu::
cond_true(kCondRep)` raises the recognition latch when the bus stream reaches
the recorded position, the `REP` continuation fails, and the ROM's own
withdrawal path (`009A`/`009B` -> `REPX 0220`) runs.  **The element's own store
is still PENDING at that test** (write-data pairing, §18.2/§27: after the first
iteration nothing refreshes OPR, so the cycle only runs when the next one is
registered), so the pending cycle has to be counted or the model withdraws one
element late — measured on `mc1/1447`, a `REP STOSB` the chip aborted after two
elements and the model after three.

Results over the four banks:

| | |
|---|---:|
| seeds carrying an `evt` axis | 1 165 |
| ... exact | **1 075 (92.3 %)** |
| interrupt entries actually replayed | **953** (762 INTR, 191 NMI) |
| ... seeds exact | **918 / 953 (96.3 %)** |
| `evt` seeds with no entry inside the window | 212 (fired past the capture, masked, or `POLL`) |

### 57.1 The REPX rewind, including STACKED prefixes — **the law EMERGES**

`REPX 0223 JMP INTR 5` is reachable and reached.  21 mid-string withdrawals
landed on the boundary the chip recorded, bucketed by the number of prefix
bytes `PFXCNT` had to unwind:

| `PFXCNT` | withdrawals |
|---:|---:|
| 0 | 2 |
| 1 | 15 |
| **2** | **4** |

The rewind is `0225 PFXCNT -> tmpa`, `0226 SIGMA -> tmpb / ALU DEC tmpb`,
`0227 SIGMA -> PC / FLUSH`, i.e. `PC := PC - PFXCNT - 1`.  In S2a only
single-prefix forms tested it.  The four `PFXCNT = 2` withdrawals are the
general case — a REP-prefixed string instruction that *also* carries a segment
override — and on all four the address the ROM computed is bit-identical to the
`IP` the chip pushed.  **"The saved IP covers the whole prefix chain" is not a
modelled rule anywhere in the simulator; it is what rows `0225`-`0227` do.**
6 further withdrawals rewound to an address that was not the recorded one and
are counted (`repbad`) rather than swallowed; all 6 are in already-divergent
raw seeds.

## 58. `F1` — **first empirical test, and it PASSES**

S2b left `F1` as the one optable/pla finding that had never been executed: the
V20 suite classes it `"status": "prefix"` and emits no file for it.  A fuzz
sequence executes whatever byte is there.

`sw/ucsim_fuzz.py --census` reports, per seed, which bytes the loader consumed
in a **prefix position** (a statement about executed code, not about bytes
lying in the image):

```
0F:2333  26:1629  2E:1638  36:1702  3E:1662  64:1689  65:1745
F0:1541  F1:278   F2:1725  F3:1904
```

**278 seeds executed `F1` as a prefix**, and not one of the 284 F-A failures
has its divergence at an `F1`-prefixed instruction.  `F1` seeds pass at
177/278 against 515/703 for raw seeds without `F1` — the same regime, no
`F1`-specific penalty.  pla_3's reading (`Bl1Op::kLockAlias`, an undocumented
`BUSLOCK` alias) is now **corroborated by execution on real silicon** rather
than by classification alone.

## 59. A19 — REP-prefix precedence — **RESOLVED: LAST ONE WINS**

A19 asked what a chain carrying two *different* REP-family prefixes does.  No
directed probe existed and the residual said "needs board access".  It does
not: the bank is full of them.  The census counts an instruction whose prefix
chain carries two or more distinct members of `{F2, F3, 64, 65}`:

```
2 032 conflicting chains over 1 303 seeds
e.g.  mc1/1015: 3E F2 F3 02 36 C6 22      (REPNE then REP)
      mc1/1012: 65 F2 65 2A 36 21 29      (REPC, REPNE, REPC)
      mc1/1019: F0 65 64 81 1E F0 2E 7F   (BUSLOCK, REPC, REPNC, ...)
```

every ordered pair of the four is represented (97-132 instances each).
**1 296 of the 1 303 seeds are exact, and of the 7 that are not, ZERO have
their divergence at a conflicting-chain instruction.**  The simulator's model
is the prefix loop's plain "each prefix overwrites the `rep` latch", i.e. the
LAST REP-family prefix decides both the abort test and the page-1 dispatch.
A19 is **CLOSED** on 2 032 real-silicon instances.

## 60. Status-latch persistence across an interrupt — **NOT DISCRIMINATED**

Codex item 8 asks whether the ALU status latch (`Machine::stat`, what the
microcode's `JMP C/NC/Z/NZ/L/NS` read) survives an interrupt.  The model says
it does — nothing in the simulator clears it — and a two-instruction probe
would settle it.

`--stat-clobber` is the falsifier: overwrite `stat` with `0x5555` at every
interrupt entry and re-run the whole bank.  If any seed's outcome changes,
that seed discriminates; if none does, no banked seed can settle it.

**0 of 3 242 seeds changed outcome** — not the verdict, not the first
divergent event, not the stream length.  953 replayed interrupt entries are not
enough: no banked program reads a condition set before an interrupt *after*
that interrupt without recomputing it in between.  The residual stands, and it
now has a measured size: a directed two-instruction probe is required, which
needs the board and is out of campaign scope.

## 61. A30 — the ambiguous micro-address — **still OPEN, now bounded**

A30 says bank A of `111.00000010.00` (`01DC`-`01DF`, which saves and restores
AX around **one** `[-05-]` acknowledge) is the *emulation-mode* acknowledge,
selected by a 14th, mode input to the micro-address decoder; the model runs
bank B (`01E0`-`01E3`, **two** acknowledges) always.  S2b's route for it was
"a BRKEM capture reaching page 7 opcode 02".

S3 has BRKEM captures — 73 seeds enter 8080 mode — and the answer is still no:

* **bank A is 0/4 executed** across 3 242 seeds even with 8080 mode
  implemented;
* **every acknowledge in the entire bank is a two-cycle pair.**  764 INTA runs,
  all of length 2, including 7 in seeds that entered 8080 mode.
* the simulator believes exactly **3** acknowledges were taken with `MD = 0` —
  and all three are in seeds that had ALREADY diverged before the entry, so the
  model's mode state there is not evidence.

So the bank contains no trustworthy MD = 0 acknowledge.  A30 needs a **directed
capture**: a contained program that does `BRKEM`, stays in 8080 mode, and takes
an INTR — at which point one INTA cycle instead of two settles it in a single
seed.  Recorded as the concrete S4 board request.

## 62. Micro-row coverage from the fuzz banks alone — 912 / 1028

`--coverage` over all four banks:

| block | rows executed | was, at S2b |
|---|---|---|
| RESET `111.00000011` | **6/8** | 0/8 |
| BRK/TF trap `01D8`-`01D9` | **2/2** | 0/2 |
| NMI `01DA`-`01DB` | 2/2 | 2/2 |
| INTA bank A `01DC`-`01DF` | **0/4** | 0/4 (A30) |
| INTA bank B `01E0`-`01E3` | 4/4 | 4/4 |
| INTEM `0090`-`0093` | **4/4** | 0/4 |
| BRKEM `0F FF` `0348`-`034B` | **2/4** | 0/4 |
| 8080 page `110` `034C`-`03FB` | **153/176** | 0/176 |
| 8080 `ED` page `101` `03FC`-`0403` | **5/8** | 0/8 |
| REPX `0220`-`0227` | 8/8 | 8/8 |
| POLL busy loop `006F`-`0073` | 0/5 | 0/5 (R2') |

912 of 1028 rows are executed by the fuzz banks **on their own** — more than
the 740 the whole of S0-S2 reached — and the fuzz set strictly **contains** the
724 rows `v0.1` + `v0.2` + the specials reach, so the union is 912 as well.
Every block S2b listed as untested is now either covered or explained:

* **RESET, the BRK/TF trap, INTEM and the 8080 pages: newly covered.**  The TF
  trap is reached because raw byte soup sets TF and the replay models the
  single-step trap (TF sampled at the START of an instruction, so the
  instruction that sets it does not trap — **A42**).
* **bank A (4 rows)** — A30, §61.
* **the POLL busy loop (5 rows)** — R2', unchanged: `BUSY` is hard-FALSE and no
  banked program parks on the pin.

Of the 116 rows still unexecuted, **108 are trailing dead rows of their bank**
(row >= 2 with every later row of the same bank also dead) — structurally
unreachable, no ROM claim.  The remaining **8** are:

```
0070 0071   the POLL busy loop's JMP 0 / SUSP   (R2', BUSY hard-FALSE)
01DC 01DD   INTA bank A                          (A30, sec. 61)
0109 0181 0219 021D  four single rows inside banks whose sequence takes the
            other JMP arm on every case the banks contain
```

That is the whole of the campaign's untested ROM surface after S3: **two named
residuals and four unexercised JMP arms.**

## 63. Assumptions added at S3

| # | assumption | § | falsifier |
|---|---|---|---|
| A37 | Ext `[-03-]` (`01ED`) forces WORD bus width for the rest of the micro-sequence; bus width otherwise follows `OP8b` | 53 | a form executing `01ED` that then writes a BYTE to the stack, or an `FE`-group form that writes a WORD |
| A38 | the 8080 register map (A=AL, B=CH, C=CL, D=DH, E=DL, H=BH, L=BL, HL=BX, DE=DX, BC=CX, SP=BP, `110` = memory at `DS:BX`) and the M=source / R=destination field binding | 55 | any 8080 form touching the wrong V30 register; 153 executed `110`-page rows and 76/85 `t30-brkem` seeds constrain it |
| A39 | the 8080 `ALU OPC` permutation ADD ADC SUB SBB ANA XRA ORA CMP | 55 | an 8080 `80`-`BF`/`C6`-`FE` form computing the wrong operation |
| A40 | the 8080 `JMP OPC` condition bank reads opcode bits 5:3 (NZ Z NC C PO PE P M) | 55 | an 8080 conditional jump/call/return taking the wrong branch |
| A41 | `ENDEM` returns to native mode unconditionally (exact whenever the BRKEM frame carried MD = 1, which `0090`-before-`0093` guarantees) | 55 | a `RETEM` from a frame pushed with MD = 0 |
| A42 | the BRK/TF single-step trap is armed from the TF bit as it stood at the START of the instruction | 62 | a golden where the instruction that sets TF traps immediately |

Running total: **42** numbered assumptions.  A31 (`[-03-]` inert) is
**withdrawn** — §53 replaces it with a mechanism.  Policy entries: 4 (queue
deferral, `iord` replay, single-instruction pin-event boundary replay, and the
sequence boundary replay of §57).

## 64. Residual updates after S3

* **`F1` — CLOSED** (§58).  Executed as a prefix in 278 banked seeds, zero
  attributable divergences.
* **A19 — CLOSED** (§59).  2 032 conflicting REP-family chains; last one wins.
* **A31 — WITHDRAWN**, replaced by **A37** (§53).
* **R10 — largely CLOSED** (§55).  8080 mode is implemented from the ROM; 158
  of its 192 rows execute; `t30-brkem` scores 76/85.  What remains is a
  *quality* residual (the 70 seeds of §56.2), not an unimplemented feature.
* **A30 — OPEN, bounded** (§61).  Bank A is unreached even with 8080 mode live;
  the bank holds no trustworthy MD = 0 acknowledge.  Needs a directed capture.
* **NEW: cross-instruction status-latch survival — UNDISCRIMINATED** (§60).
  0 of 3 242 seeds change outcome under `--stat-clobber`.  Directed
  two-instruction probe, board required.
* **NEW: no controlled wait-invariance tranche** (§56.1).  The wait axis and
  the program are drawn from the same seed, so the bank contains no two seeds
  running the same program at different waits.  The evidence is "no
  counter-example", not "same program, both waits".
* **R5 — queue deferral** — now the sharpest it has been.  The functional model
  has NO prefetch: it fetches an instruction byte when the decoder asks for it.
  Every one of the 2 873 exact seeds is a sequence whose *functional* stream is
  independent of the queue, which is the strongest evidence yet that the
  deferral is sound; the raw-tier tail (§56.2) is where a self-modifying write
  into the prefetch window would hide, and it is not separated from the other
  causes there.

## 65. Every single-instruction gate re-verified after the mechanism changes

S3 changed three mechanisms in the shared model — the bus-width rule (A37), the
write-back strobe's binding (§54) and the addition of 8080 mode (§55) — so
every S2 gate was re-run, not just the ones the changes obviously touch:

| gate | result |
|---|---|
| `v0.1` | **169 000 / 169 000** |
| `v0.1-w1` / `v0.1-w3` | 1 200 / 1 200 each |
| `v0.2` | **347 000 / 347 000** |
| `v0.3` | **3 699 998 / 3 699 998** (2 documented VOID excluded) |
| `v20suite` | **3 125 000 / 3 125 000** |
| `f4a_boundary` | 160 / 160 |
| `mod3_illegal` | 128 / 128 (128 documented residue) |
| `f0lock_tranche` | 400 / 400 |
| `enter_nesting` | 666 / 666 walk digests |

~7.2 M single-instruction cases, all green, with the model that also runs the
sequence gauntlet.  A37 in particular is not a special case bolted on for the
fuzz bank: it is the rule the divide trap needed all along.

---

# S4 — closure (2026-08-01)

The campaign's answer document is
**`docs/notes/ucsim_campaign_verdict_2026-08-01.md`**.  This section is the
ledger's own closing record: the final counts, the gate ledger, the
consolidation findings, and the S4 re-verification.

## 66. Final counts

| | |
|---|---:|
| micro-rows in the ROM | 1028 (257 activation patterns) |
| micro-rows executed by a green gate | **912 / 1028** (`sim/coverage_report.txt`) |
| ... of the 116 unexecuted: substantive (a ROM claim, untested) | **9**, in exactly 2 residuals (POLL tail 5, INTA bank A 4) |
| ... structurally unreachable (14 post-`FARJMP` rows + 93 bank tails) | 107 |
| numbered assumptions booked A1..A42 | 42 |
| ... withdrawn (A31, §53) / falsified (A7, §66.3) | 2 |
| ... **standing** | **40** |
| ... of the 40: ROM-constrained / MEASURED-constrained / free choice / policy | 16 / 11 / 12 / 1 |
| policy entries (deliberate non-modelling) | 4 |
| single-instruction cases compared | 7 343 398 (+ the four specials tranches) |
| fuzz-bank seeds replayed | 3 242 (2 125 with an architectural anchor, **all exact**) |
| cases whose final PSW is 100 % microcode-produced | **~76 %** on both parts (§49.2) |

The free-choice dozen — the only entries no dumped asset and no capture
discriminates — is A2, A4, A5, A6, A8, A9, A10, A13, A15, A30, A33, A36.
None of them is in the computational core; see the verdict document §(c) for
the row-by-row derivation.  (The §66.3 A40 re-class moves one entry out of the
MEASURED-constrained group into a PLA-determined one — 16 / 10 / 12 / 1 / 1 —
and leaves the free-choice dozen untouched.)

## 66.1 Gate ledger

| stage | gate | number | commit |
|---|---|---|---|
| S0a | `disasm` byte-identical to `docs/V20UC.TXT` | 1028 rows / 257 patterns, empty diff | `840ed97` |
| S0b | pla_3 identification (`sw/pla3_check.py`) | 3 × 256 output vectors bit-exact; 21 checks, 0 contradictions | `dcfdfa7` (+ `ab37957`) |
| S0b | pla_2 identification | 2048/2048 native + 2048/2048 8080 cells, unique solution | `dcfdfa7` |
| S1a | bring-up families on `v0.2` | 35/35 forms, 35 000/35 000 | `6619417` |
| S1b | flow / internal page / arithmetic | 114/114 forms, 114 000/114 000 | `cb0e4d6` |
| S1c | `0F` page; **P1** | 25/25 forms, 25 000/25 000 | `3fd2f63` |
| S2a | **G-A** `v0.1` | 169 000 / 169 000 | `dd21069` |
| S2a | **G-A** `v0.1-w1` / `-w3` | 1 200 / 1 200 each | `dd21069` |
| S2a | **G-C** specials | 160/160, 128/128, 400/400, 512+154 walk digests | `dd21069` |
| S2b | A12 boundary exposure | 8 820 / 8 820 (47 real wraps) | `7688919` |
| S2b | INS/EXT `mod != 3` (R8) | 19 914 / 19 914 | `7688919` |
| S2b | **G-B** `v0.3` | 3 699 998 / 3 699 998 | `7688919` |
| S2b | **G-D** `v20suite` | 3 125 000 / 3 125 000 | `7688919` |
| S2b | raw-PSW rollup | both mass suites 100 % with every mask disabled | `7688919` |
| S3 | **F-A** `mc1`+`mc2`+`t30-raw` | 2 873/3 157 seeds; **2 125/2 125** arch-anchored | `1c95689` |
| S3 | F-B `t30-brkem` | 76 / 85 | `1c95689` |
| S3 | F-C interrupt interleaving | 1 075/1 165 `evt` seeds; 918/953 replayed entries | `1c95689` |
| S3 | all single-instruction gates re-verified (§65) | ~7.34 M cases green | `1c95689` |
| S4 | micro-row coverage | **912 / 1028** | this commit |

## 66.2 S4 re-verification

Run immediately before this commit, on the tree as committed:

* `make -C sim test` — **disasm gate PASS** (empty diff vs `docs/V20UC.TXT`).
* `python3 sw/pla3_check.py` — **OK, 21 checks passed**, exit 0.
* `v0.1` — **169 000 / 169 000** (1 collision-dependent golden validated on
  64K-mirrored RAM, as captured).
* the full coverage union was re-derived from scratch across every gate
  (`v0.1` 169 000/169 000, `v0.1-w1` 1 200/1 200, `v0.1-w3` 1 200/1 200,
  `v0.2` 347 000/347 000, `f4a_boundary` 160/160, `mod3_illegal` 128/128,
  `f0lock_tranche` 400/400, `v0.3` 3 699 998/3 699 998 in 520.3 s,
  `v20suite` 3 125 000/3 125 000 in 392.2 s, and the four fuzz banks —
  F-A **2 873 / 3 157** again).  Every gate reported its S2/S3 number.
  Union **912 / 1028**, written by the new `sw/ucsim_coverage_report.py` to
  `sim/coverage_report.txt`.

## 66.3 Consolidation findings

Found while writing the verdict document.  None changes a gate result; all are
recorded rather than silently fixed.

1. **A7 is FALSIFIED, not standing.**  §30's A7 ("`SR == SS` accesses are
   word-wide regardless of operand width") carries the falsifier "a byte-width
   instruction whose microcode touches the stack".  §53 *ran* it: the undefined
   `FE`-group byte forms (`FE /2`, `/3`, `/6`) push a single **byte** on
   silicon, and A37 replaced the rule.  The ledger withdrew A31 explicitly but
   left A7 in the count.  **Standing assumptions: 40, not 41.**
2. **A2's falsifier is now reachable.**  A2 ("`INC2`/`DEC2` are always 16-bit
   regardless of operand width") records the same falsifier shape as A7 — "a
   byte-width instruction whose microcode also does stack arithmetic" — and the
   §53 `FE`-group byte pushes are exactly that.  The model is exact on them
   (F-A, 2 125/2 125 anchored seeds), so A2 is at least MEASURED-constrained.
   Booked as a bookkeeping upgrade only; no new mechanism is claimed here.
3. **A40 should be re-classed ASSUMPTION → PLA-corroborated.**  A40 (§63) says
   the 8080 `JMP OPC` condition bank reads opcode bits 5:3 in the order
   NZ Z NC C PO PE P M.  `docs/facts/pla_model.md`'s pla_2 identification —
   completed at S0b, *before* A40 was written — fits **bank 1 of pla_2 to
   exactly that encoding** (`ccc` = opcode bits 5..3, the 8080 `11ccc0xx` form)
   at 2048/2048 cells, with the flag-line assignment derived from the native
   bank alone and no free parameters.  The residual assumption is only that the
   microcode's `JMP OPC` consumes that PLA output rather than recomputing the
   condition.  S3 booked it without cross-referencing the S0b work.
4. **§30's census arithmetic is off by one.**  "Twelve ROM-constrained, four
   MEASURED-constrained (one unnumbered), the remaining twelve free" is
   12 + 3 + 12 = 27 numbered, not 28.  The remaining numbered set is thirteen
   (A2, A4, A5, A6, A7, A8, A9, A10, A12, A13, A15, A19, A28).  The verdict
   document re-derives the census row by row instead of by subtraction.
5. **§59 restates A19 as a different question than §30 booked.**  §30's A19 is
   the repeat-prefix → *data-test polarity* map; §59 answers the *precedence*
   question ("last one wins").  Both are now MEASURED-constrained — the
   polarity map by every REP form in `v0.3`, precedence by 2 032 conflicting
   chains over 1 303 seeds — so the closure stands, but the two questions are
   not the same one.
6. **§62's NARRATIVE split of the unexecuted rows is wrong in both
   directions** — its *block table*, three paragraphs earlier in the same
   section, is right (`006F`-`0073` 0/5, bank A 0/4).  The four rows the
   narrative names "unexercised JMP arms" (`0109`, `0181`, `0219`, `021D`) are
   each the row *immediately after an unconditional `CTL FARJMP`* (`0108`,
   `0180`, `0218`, `021C`), which has no delay slot — structurally unreachable,
   no ROM claim; and ten further rows of that same shape sat unremarked in the
   other bucket.  Conversely the "trailing dead rows" bucket (defined as
   "row ≥ 2 with every later row of the bank also dead") swallows **five rows
   that DO carry a ROM claim**: `006F` (POLL's `JMP INTR 5` — unreached because
   `006C`'s `JMP BUSY 3` never branches, so `006D`'s `E` retires POLL two rows
   earlier), `0072`/`0073` (the withdrawal's `PC-1` and `FLUSH`) and
   `01DE`/`01DF` (bank A's high-lane vector read and AW restore).  Corrected
   split, now in `sim/coverage_report.txt`: **9 substantive rows across the two
   named residuals (R2′ 5, A30 4), 14 post-`FARJMP`, 93 bank tails.**  The
   totals (912 / 116) are unaffected.  A knock-on: §37's "`JMP INTR` also
   appears at `006F`, inside `POLL` … the `POLL.LO`/`POLL.REL` tranches stay
   green with it never raised" reads as though the row runs and evaluates
   false.  It is never reached at all — `006D`'s `E` retires POLL two rows
   earlier — so those 2 400 green cases constrain `006C`-`006E` only.
7. **§62's containment baseline is the wrong set, but the claim holds.**  §62
   compares the fuzz coverage against "the 724 rows `v0.1` + `v0.2` + the
   specials reach"; §49.3's union over *every* S0-S2 gate (adding `v0.3` and
   `v20suite`) is **740**.  Re-derived at S4: the fuzz set contains all 740 —
   `single − fuzz` is **empty**, `fuzz − single` is 172 — so the union is 912
   either way.
8. **`tests/v30/v0.3-f4a-boundary` does not exist as data** (§44): the
   directory holds an `emit_log.txt` and nothing else.  It is still cited as
   A12's route in §30/§32; the live artifact is the `--wrap-scan` subset.

## 66.4 What the campaign hands forward

* **Board work** (verdict §(d)): the status-latch persistence probe, the A30
  BRKEM+INTR capture, R1's byte-shifter discriminator, R6 (`CL = 0`), the
  POLL `BUSY` tranche, and a controlled wait-invariance re-emission.
* **Timing campaign**: R5 (queue/prefetch), R2′, the four replay policies, and
  the preserved `F`/`Q` interlock call sites in `sim/exec.cpp`.
* **RTL**: the INS and ENTER micro-march replacements (the two 2026-08-01
  pilots) now have an architectural cross-check; `enter_nesting` 666/666 with
  the nesting *not* masked mod 32 is the sharp case.
* **Documentation**: `ROADMAP.md` carries the dated amendment superseding the
  2026-07-11 "no intermediate software reference model" decision.
