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

Status of this file at the end of **S1a**: covers everything the bring-up
families exercise.  Later stages append.

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

### 2.2 `OPC` selection rule — **ASSUMPTION (PLA-corroborated)**

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

### 2.6 `-> tmpaL` / `-> tmpbL` SIGN-EXTEND into the high half — **MEASURED**

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

### 3.4 `JMP OP8` — **ASSUMPTION**

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

### 6.1 Posted writes: the data phase samples `OPR` one row later — **ROM**

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
| `F` (`Flag_F`) is a **bus interlock**, not a flag control | ASSUMPTION | it appears on rows that consume `OPR` after a `MEMR` (`000B`, `002F`, `0087`) and on `005A`, one row before the `[-06-]` that needs the read data — never on a row that computes flags.  `V20UCDIS.PAS` documents `Flag_W` as "write flags" and leaves `Flag_F` uncommented.  Modelled as an instantly-satisfied sync object (call site preserved for the timing campaign) |
| `SUSP` = logged no-op; `FLUSH` = clear queue, refetch from CS:PC | ASSUMPTION | standard BIU semantics; validated indirectly by the green branch forms |

### S0a ambiguous address

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
