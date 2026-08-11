# PRE-REGISTRATION — THE TF × `0F` TRAP-BOUNDARY DIRECTED BOARD CELL

**Committed BEFORE the first board contact of this sitting.** Tool
`sw/tf0f_cell.py`; artifacts under `sw/testdata/tf0f/`. Branch
`fuzz-v2-on-relanding`, tree `310457b2f7`. Board carries **FLASH #17**
(`flash_log.jsonl` = **20 entries**, `.sof`
`26c19f613e2caae8cf3479244319988227a748c000f456c458d901b4ee266a6c`); **this
sitting takes NO flash and touches NO RTL**, and `hdl/rtl/` at this tree is
byte-identical to the tree FLASH #17 was built from (`85babd2e4a`; the only
`hdl/` delta is the generated `nec_test_ucore.qsf`).

---

## 0. WHAT IS OWED, AND BY WHOM

Two bookings ask for exactly this population and neither has it.

**(1) `docs/notes/fz2_a3d1d2_diagnosis_2026-08-11.md` §6.6.** The A3/D1/D2
block's only lead is the TF trap boundary after an `0F`-extended instruction.
Three banked seats carry a clean shape — the core issues one or two further
`CODE` prefetches before entering vector 1 and the chip does not, so the two
legs push different return addresses:

| seat | ledger family | `CODE` before first vector-1 entry, chip / core | delta |
|---|---|---|---|
| `fz2c/404041` | D2 | 85 / 87 | **CORE +2** |
| `fz2e/501066` | D2 | 61 / 62 | **CORE +1** |
| `fz2e/513019` | C2 | 82 / 84 | **CORE +2** |

Its verdict, verbatim: *"The derivable population is THREE seats … A clean book
beats a fitted land. **Booked.**"* Its re-open condition, verbatim: *"A directed
TF × `0F` capture … a directed population that crosses TF with the whitelisted
`0F` band … at both `mod = 3` and `mod != 3` would give a two-digit denominator
and a real split. **Register the split before deriving.**"* This document is
that registration.

**(2) `ucore_provenance.md` §86** landed the BRK/TF arm and registered its
sampling boundary as **ONE predicate — the `QS = 1` opcode pop** — on the
reasoning that *"a prefix retires as its own two-clock instruction with its own
F pop … and so does the `0F` escape's first byte, so 'A PREFIX BYTE ENDS AN
INSTRUCTION BOUNDARY' is already what the pop stream says."* **That sentence
has never been measured against silicon on a two-byte opcode or on a prefix
stack**: §86.C's cell (`sm3_tf_floor_cell`) walks a ONE-BYTE pad, and it
**cannot run on this branch** (CLAUDE.md, FLASH #14 line). This is `C1`'s
registered directed-cell debt.

---

## 1. THE INSTRUMENT

### 1.1 The program

`R = 6` identical blocks of `BLOCK = 16` bytes at the fuzz-v2 code anchor:

```
    68 00 01     push 0x100     <- 0x100 IS PSW.TF
    9D           popf              (`testimage.normalize_psw` forces TF CLEAR
    <P>          the probe          into every composed image, so the only way
    90 90 …      pad to 16          to a set TF is an instruction, and this is it)
```

The setter is the seats' own (`fz2c/404041` and `fz2e/501066` both execute
`push 0x100 ; popf` immediately before their `0F` instruction). Vector 1 points
at a handler that **clears TF in the frame it is about to return through**
(`MOV BP,SP ; MOV word [BP+4],0xF002`, `compose` appends `IRET`), so each block
produces **exactly one** trap and one capture is **six independent repeats** of
the same measurement rather than a storm that only ever measures its own first
trap. `sm3_tf_floor_cell`'s trick, one vector over.

`REGS` points the bit-string implicit operands (`DS0:IX`, `DS1:IY`) into the
data carve-out at linear `0x2000`, identically on every leg including the
controls, so no probe's side effect can leave it and the geometry does not move
across the family.

### 1.2 The observable is engine-free and it is one small integer

A vector-1 entry is announced by a `MEMR` at linear `0x00004` (then `0x00006`);
the three descending `MEMW`s that follow are PSW, PS, **PC** in hardware push
order, and the third is **the boundary the part chose**. The body is periodic
with period 16 and every instruction start inside a block is known by
construction, so

> `pushed_off = pushed_PC − block_base`

names that boundary exactly, in bytes, identically in every block. Nothing in
the reader decodes an opcode, runs an engine, or consults a golden. Reported
beside it, as data and **not** as a bar: `lastcode_off` (the prefetch
high-water mark before the entry, relative to the same base) and `code_gap`
(the `CODE`-cycle count between consecutive entries) — these are the diagnosis's
own §6.4 quantities and they are **not** invariant over waits, so no clause
below is written on them.

### 1.3 The probe family — the discriminator

Every probe is `mod = 3` or has an EA in the data carve-out; **no probe is a
BRKEM alias** (`0F` + any byte ≥ 0x40 is the 8080 door,
`docs/facts/undocumented_0f.md`, and `0F FF` is excluded by the same rule); and
**no probe is the parked `0F 31`-with-memory-ModR/M form** (`fz2_a3d1d2_
diagnosis` §5).

| leg | bytes | class |
|---|---|---|
| `nop` | `90` | CONTROL band — §86 says the registered predicate is right here |
| `clc` | `f8` | " |
| `incaw` | `40` | " |
| `movi` | `b8 34 12` | length without a second OPCODE byte |
| `addrr` | `01 d8` | opcode + ModR/M, `mod = 3` |
| `pfx1` | `2e 01 d8` | the prefix ladder, depth 1 |
| `pfx2` | `2e 3e 01 d8` | depth 2 |
| `pfx3` | `2e 3e 26 01 d8` | depth 3 |
| `pfx4` | `2e 3e 26 36 01 d8` | depth 4 |
| `x13` | `0f 13 c0` | `0F`-escaped, `mod = 3`, 3 bytes |
| `x1b` | `0f 1b e8 4f` | **`fz2e/501066`'s LITERAL probe bytes** |
| `x18` | `0f 18 c0 05` | `0F`-escaped, `mod = 3`, 4 bytes |
| `x28` | `0f 28 c0` | ROL4, `mod = 3` |
| `x33` | `0f 33 c3` | EXT reg,reg, `mod = 3` |
| `y1e` | `0f 1e 06 00 20 05` | **`fz2c/404041`'s shape**: `0F 1E`, `mod ≠ 3` |
| `z1b` | `2e 0f 1b e8 4f` | the two mechanisms CROSSED |
| `notf` | `0f 1b e8 4f` | **THE NULL**: `push 0x000` in place of `push 0x100`, same probe, same geometry |

### 1.4 The axes

`waits` ∈ {0, 1, 2, 3} — which is also the queue-fullness axis, because at w3
the prefetcher never gets ahead — and `align` ∈ {0, 1, 2, 3}, which moves every
block's byte phase against the word-aligned fetch so the probe arrives with the
queue in a different state. **17 legs × 4 waits × 4 aligns = 272 cells**, each
carrying **6 traps** (except `notf`, which must carry 0), so
**16 × 16 × 6 = 1,536 scored traps** plus a 16-cell null.

---

## 2. THE HYPOTHESIS LATTICE — the full 3 × 2 product, not a hand-picked list

§84.3 / §86 land that the arm **SAMPLES `TF` at a boundary and TAKES at the
NEXT one**, and §86.B measures the floor at 4 clocks from the rise, which `B0`
(`popf`'s own retire, 1–2 clocks after its flag write) never clears. So `B1` —
the retire of the FIRST unit after the setter — is the first sampling boundary,
the trap is taken at `B2`, and

> **`pushed_off` = the start of the THIRD unit after the setter.**

The whole question this cell asks is **what counts as a unit**, and the
candidates are not a hand-picked list: they are the **full product** of the only
two degrees of freedom the question has —

* **P**, what a PREFIX STACK contributes: `none` | `stack` (one unit, any depth) | `byte` (one per prefix byte)
* **E**, what the `0F` ESCAPE byte does: `no` unit | its own unit

| rule | (P, E) | reading |
|---|---|---|
| **K1** | (none, no) | ONE unit per ARCHITECTURAL instruction |
| **K7** | (none, yes) | — |
| **K3** | (stack, no) | — |
| **K5** | (stack, yes) | **the shape the A3/D1/D2 diagnosis predicts for silicon** |
| **K4** | (byte, no) | — |
| **K2** | (byte, yes) | **§86's PROSE READ LITERALLY** |

No rule can be added after the fact without changing the product, and there is
**no per-opcode special case anywhere in the table** (standing simplicity
principle).

### 2.1 The predicted `pushed_off` per leg per rule — and the CORE's measured column

The core column below is **`tb_sys ret`, measured OFFLINE before this document
was written** (`sw/testdata/tf0f/core/`, 272/272 cells structurally valid,
1,536 traps, every leg giving a **single** `pushed_off` across all 16 of its
cells). It is an instrument, not the reference: **silicon is the correctness
target** (CLAUDE.md, 2026-08-04).

| leg | bytes | **core** | K1 | K7 | K3 | K5 | K4 | K2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `nop` | `90` | **6** | 6 | 6 | 6 | 6 | 6 | 6 |
| `clc` | `f8` | **6** | 6 | 6 | 6 | 6 | 6 | 6 |
| `incaw` | `40` | **6** | 6 | 6 | 6 | 6 | 6 | 6 |
| `movi` | `b83412` | **8** | 8 | 8 | 8 | 8 | 8 | 8 |
| `addrr` | `01d8` | **7** | 7 | 7 | 7 | 7 | 7 | 7 |
| `pfx1` | `2e01d8` | **7** | 8 | 8 | **7** | **7** | **7** | **7** |
| `pfx2` | `2e3e01d8` | **8** | 9 | 9 | **8** | **8** | 6 | 6 |
| `pfx3` | `2e3e2601d8` | **9** | 10 | 10 | **9** | **9** | 6 | 6 |
| `pfx4` | `2e3e263601d8` | **10** | 11 | 11 | **10** | **10** | 6 | 6 |
| `x13` | `0f13c0` | **8** | **8** | 7 | **8** | 7 | **8** | 7 |
| `x1b` | `0f1be84f` | **9** | **9** | 8 | **9** | 8 | **9** | 8 |
| `x18` | `0f18c005` | **9** | **9** | 8 | **9** | 8 | **9** | 8 |
| `x28` | `0f28c0` | **8** | **8** | 7 | **8** | 7 | **8** | 7 |
| `x33` | `0f33c3` | **8** | **8** | 7 | **8** | 7 | **8** | 7 |
| `y1e` | `0f1e06002005` | **11** | **11** | 10 | **11** | 10 | **11** | 10 |
| `z1b` | `2e0f1be84f` | **9** | 10 | **9** | **9** | 6 | **9** | 6 |
| | **agreement, of 16** | | 11 | 6 | **16** | 9 | 13 | 6 |

**THE ucore IS `K3`, UNIQUELY, ON 16 OF 16 LEGS AND 1,536 OF 1,536 TRAPS** —
the prefix STACK contributes exactly ONE extra unit whatever its depth, and the
`0F` escape byte contributes NONE.

⚠ **This already refutes §86's PROSE as a description of the ucore's own
composite behaviour** (`K2` agrees on 6 of 16), and it does so **offline, with
no board involved**. It does **not** refute §86's landed predicate: §86 names
the SAMPLE side (`q_pop && q_ripe && q_first`), and `pushed_off` is the
composite of the sample side and the TAKE side (`at_bnd`). What is measured
here is the composite. **That distinction is registered now, before the board
run, so it cannot be invented afterwards to protect either reading.**

### 2.2 The five non-discriminating legs, declared in advance

`nop`, `clc`, `incaw`, `movi`, `addrr` — all six rules predict the same
`pushed_off`. **They are COVERAGE, not evidence, for the lattice**, and they may
not be quoted as confirming any rule. They carry a different job: they are the
band §86's own cell already walks, so a chip/core disagreement there would mean
the disagreement is not about `0F` or prefixes at all, and would **invalidate
the whole reading** (clause I-4).

---

## 3. THE COMPETING PREDICTIONS, AS CHIP ROWS

Every clause below is a statement about the **chip's** `pushed_off` column.
Exactly one of H-A…H-F can hold.

* **H-A — §86-AS-REGISTERED / "the core is right".** The chip is **K3**: its
  `pushed_off` equals the core column above on **all 16** legs.
  *If H-A holds, the A3/D1/D2 diagnosis §6 lead is **REFUTED** and the three
  seats need a different mechanism; `C1`'s directed-cell debt is discharged with
  a negative result.*
* **H-B — THE DIAGNOSIS'S SHAPE.** The chip is **K5**: identical to the core on
  the nine non-`0F` legs and **one unit EARLIER on all seven `0F` legs** —
  `x13` 7, `x1b` 8, `x18` 8, `x28` 7, `x33` 7, `y1e` 10, `z1b` 6.
  *If H-B holds, the lead is **CONFIRMED**, silicon counts the `0F` escape byte
  as its own boundary unit and the ucore does not, and the seats' `CORE +1/+2`
  prefetch excess is that one unit.*
* **H-C — THE PREFIX SIDE INSTEAD.** The chip is **K4**: identical to the core
  on every `0F` leg and on `pfx1`, and **earlier on `pfx2`/`pfx3`/`pfx4`**
  (6, 6, 6). *The other half of §86's sentence, alone.*
* **H-D — BOTH SIDES.** The chip is **K2** (§86's prose read literally):
  `pfx2`/`pfx3`/`pfx4` = 6, `z1b` = 6, and all seven `0F` legs one earlier.
* **H-E — ARCHITECTURAL.** The chip is **K1** or **K7**: `pfx1`…`pfx4` LATER
  than the core, i.e. silicon does not break a prefix stack at all.
* **H-F — NONE OF THE SIX.** No rule in the lattice reproduces the chip column.
  **Registered as a live outcome**, so the cell may report "none" rather than
  being forced onto the nearest member. If H-F is the outcome, the measured
  column is published as a TABLE and **no law is derived from it in this
  sitting** — deriving a seventh rule from the column that refuted the six is
  fitting.

**Quantitative bar for the headline (pre-registered):** a rule is declared the
measured law only if it reproduces the chip's `pushed_off` on **16 of 16** legs
**and** the chip's column is **single-valued on every leg** (all 16 cells and
all 6 traps of that leg agreeing). Anything less is reported as a partial and
the rule is not named.

### 3.1 The anchor clause — the three banked seats

The three seats are **not** part of the derivation and cannot be: §6.6 is right
that three seats cannot validate a rule. They are an **anchor**: if the measured
law is `K5` (H-B), then re-reading the seats' banked fabric captures must show
the chip entering vector 1 **one unit earlier than the core**, and the
`CODE`-before-entry deltas of **+2 / +1 / +2** must be consistent with one
displaced boundary at those seeds' geometries. **Registered as a CHECK, not as
a bar**: the seats are three, their programs are soup, and a mismatch there is
reported as a mismatch, not smoothed. `tf0f_cell.py seats` reads them, chip
column and core column both banked, with no engine in the loop.

### 3.2 The RTL candidate, registered as a CONDITIONAL

If and only if the measured law is **K5**, the implied landing is: **the
sampling/taking unit must not treat the `0F` escape byte as a retirement**, i.e.
the arm's boundary must exclude the escape's own pop. Predicted seat reach is
registered in §5 **before** the run so it can be scored as registered.

---

## 4. INTEGRITY BARS AND STOP CONDITIONS

| bar | requirement |
|---|---|
| **I-1 SINGLE WRITER** | asked of the board (`uptime` + `ps`), local `serve` clients checked, recorded in the manifest. Not OK → STOP. |
| **I-2 SOCKET ONLY** | `use_core=False` passed EXPLICITLY on every capture (the board's CFG is sticky); `emit_suite.EMIT_USE_CORE is False` asserted at import. |
| **I-3 NO FLASH** | `flash_log.jsonl` is **20 entries** before and after. No `safe_flash.sh`, no `.sof`, no `.rbf`. |
| **I-4 THE NULL** | `notf` (TF never set, same probe, same geometry) must produce **0** vector-1 entries in **all 16** of its cells. Any entry there and the whole column is a rig artefact and nothing else in this document is quotable. |
| **I-4b THE CONTROL BAND** | the five non-discriminating legs must read chip = core. A disagreement there means the divergence is not about `0F` or prefixes and **invalidates the lattice reading** (reported, not smoothed). |
| **I-5 STRUCTURE** | every TF cell must show exactly **6** vector-1 entries with three pushes each. Cells that do not are RETAINED and REPORTED with their reason, never dropped. |
| **I-6 div_guard** | the divider PINNED and its readback RECORDED at every leg boundary and at the end. An UNPINNED readback is a rig-integrity FINDING and is printed, not smoothed. |
| **I-7 TRANSPORT** | target **0** transport errors; **three consecutive** → STOP and report as a rig finding, which outranks the measurement. A `RigMismatch` → immediate STOP (INV-1's own failure mode). |
| **I-8 STABILITY** | ≥ 5 % of cells captured **×3** (`--reps-every 8` → 12.5 %), compared on the FULL 64-bit word stream AND on `pushed_off`. Bar: **0 TAKE-unstable**. Stream-distinct counts are CHARACTERISED, not smoothed — a `notf`-free capture of a periodic program is not guaranteed byte-reproducible and the row-prefix noise of rows 0–8 is known (the F17 / ie-cell precedent). |
| **I-9 RETENTION** | full per-clock 64-bit words retained per cell, gzipped per leg, with a per-cell `sha256` and a `SHA256SUMS` over the directory. |
| **I-10 CLOSEOUT** | `board_idle()` and `check_ab_hw.py chip 800` **MATCH** after the run. |

---

## 5. PREDICTED REACH, REGISTERED BEFORE THE RUN

Registered so that whatever lands later is scored as registered, and so that an
honest denominator exists. **Conditional on H-B (K5) being the measured law and
on an RTL landing that implements it:**

* **P-1 — the three anchor seats.** `fz2c/404041`, `fz2e/501066`,
  `fz2e/513019`. Predicted to close: **2 of 3**. `fz2e/501066` is the clean one
  (single displaced boundary, streams re-align 87/87) and is predicted to close;
  `fz2e/513019` carries the same `CORE +2` shape and is predicted to close;
  **`fz2c/404041` is predicted NOT to close by this alone** — its core leg
  *retires a further far `CALL`* after the displaced boundary and seven
  architectural words diverge with the streams re-aligning only 2/342, so one
  boundary is necessary and is not obviously sufficient.
* **P-2 — the seven count-movers.** §6.4's remaining movers are *"gross count
  differences (one leg never trapping at all) and are all escaped or runaway
  seeds"*. Predicted to close: **0 of 7**. They are not this mechanism and are
  registered as not being it.
* **P-3 — the wider `PSW.TF` family.** The corpus carries **101** TF seeds, of
  which **72** banked captures reach `IVT[1]` at all and **62 already agree
  exactly**. The reachable population is therefore **at most the 10 movers**,
  not 101, and the honest predicted reach is **2–3 seeds**. **Any claim of a
  two-digit seat gain from this mechanism is registered IN ADVANCE as
  unsupported.**
* **P-4 — regression bar.** Any such landing must lose **0** seeds over the
  scored corpus. Not measurable in this sitting (no RTL is written here); it is
  registered as the bar the landing sitting inherits.

**If H-A is the outcome, P-1…P-3 are all ZERO by construction** and the correct
report is that the lead is refuted — which is the outcome this cell exists to be
able to state.

---

## 6. WHAT THIS SITTING WILL NOT DO

* No RTL is edited. No bitstream is built or flashed. No `hdl/` file is touched.
* No rule outside the §2 lattice is derived from the chip column (see H-F).
* The core column is **not** the reference and no "the ucore beats / loses to"
  comparison is computed from it; both columns are scored against **silicon**,
  which is the chip column itself.
* `sm3_tf_floor_cell` is **not** repaired or re-anchored. Its 90 captures are a
  frozen v1-anchored artefact and this cell replaces its *function*, not its
  record.
