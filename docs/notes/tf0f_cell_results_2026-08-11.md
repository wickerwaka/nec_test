# RESULTS — THE TF × `0F` TRAP-BOUNDARY DIRECTED BOARD CELL

**`C1`'s registered directed-cell debt is DISCHARGED, and the A3/D1/D2
diagnosis's only lead is CONFIRMED — with a correction to the lead's own shape
and a correction to `ucore_provenance.md` §86's prose.**

| | |
|---|---|
| pre-registration | `docs/notes/tf0f_cell_prereg_2026-08-11.md`, commit **`f08a597ed5`**, before the first board contact |
| amendment A-1 | `docs/notes/tf0f_cell_erratum_2026-08-11.md`, commit **`c13ec814f3`**, before the validation population's first board contact |
| tool | `sw/tf0f_cell.py` |
| artifacts | `sw/testdata/tf0f/` (`board/`, `core/`, `predictions.json`, `calib.json`, `score.json`, `seats.json`, `qs.json`, `SHA256SUMS` per directory) |
| tree | `fuzz-v2-on-relanding`, `310457b2f7` → `c13ec814f3` |
| board | **FLASH #17** (`.sof` `26c19f613e2caae8…`), `flash_log.jsonl` **20 entries before and after** |
| engine leg | `tb_sys ret`, receipt `251ded16c34b4212…` (`base` `11482af7aaa08bad…`) |

---

## 1. THE HEADLINE, IN ONE PARAGRAPH

At the retirement boundary that the BRK/TF single-step arm samples, **silicon
gives an instruction ONE boundary unit, plus ONE MORE if and only if its opcode
byte is not its first byte** — i.e. if it carries a prefix stack and/or an `0F`
escape — and **the extra unit is ONE however deep the decoration is and however
many KINDS of decoration are present**. The `ucore` implements the same
predicate with the `0F` escape omitted from the decoration test. That single
missing term is the whole measured divergence: **576 traps on six `0F` legs in
the derivation population and 480 more on five disjoint `0F` legs in the
validation population, all in the same direction, at every wait level and every
alignment, with zero exceptions** — and it is exactly the shape the A3/D1/D2
diagnosis §6 read off three banked seats and declined to derive a law from.

---

## 2. WHAT WAS RUN

Two board legs, both socket-only (`use_core=False`, explicit), both on FLASH #17.

| | derivation | validation |
|---|---|---|
| legs | 17 (16 scored + 1 null) | 15 (14 scored + 1 null) |
| cells (leg × waits 0-3 × align 0-3) | 272 | 240 |
| scored traps | 1,536 | 1,344 |
| wall clock | 10 s | 8.5 s |
| transport errors | **0** | **0** |
| `div_guard` | **19 boundaries, all PINNED** | **17 boundaries, all PINNED** |
| structurally invalid cells | **0 of 272** | **0 of 240** |

**Totals: 512 board cells, 512 matched `tb_sys` cells, 2,880 scored traps per
engine.** Stability: **64 of 512 cells (12.5 %) captured ×3** — `0`
TAKE-unstable and `0` stream-distinct, i.e. the full 64-bit word streams were
byte-identical across repeats as well. Every leg is **single-valued across all
16 of its cells and all 6 of its traps** on both engines: 96 traps, one number.

---

## 3. THE MEASURED COLUMN

`pushed_off` = pushed return address − block base. The block is
`push 0x100 ; popf ; <probe> ; NOP pad` to 16 bytes; the setter occupies
offsets 0–3, so the probe starts at 4.

| stg | leg | bytes | **chip** | core | Δ |
|---|---|---|---:|---:|---:|
| der | `nop` | `90` | 6 | 6 | 0 |
| der | `clc` | `f8` | 6 | 6 | 0 |
| der | `incaw` | `40` | 6 | 6 | 0 |
| der | `movi` | `b83412` | 8 | 8 | 0 |
| der | `addrr` | `01d8` | 7 | 7 | 0 |
| der | `pfx1` | `2e01d8` | 7 | 7 | 0 |
| der | `pfx2` | `2e3e01d8` | 8 | 8 | 0 |
| der | `pfx3` | `2e3e2601d8` | 9 | 9 | 0 |
| der | `pfx4` | `2e3e263601d8` | 10 | 10 | 0 |
| der | `x13` | `0f13c0` | **7** | 8 | **+1** |
| der | `x1b` | `0f1be84f` | **8** | 9 | **+1** |
| der | `x18` | `0f18c005` | **8** | 9 | **+1** |
| der | `x28` | `0f28c0` | **7** | 8 | **+1** |
| der | `x33` | `0f33c3` | **7** | 8 | **+1** |
| der | `y1e` | `0f1e06002005` | **10** | 11 | **+1** |
| der | `z1b` | `2e0f1be84f` | 9 | 9 | 0 |
| val | `v_p2x` | `2e3e0f1be84f` | 10 | 10 | 0 |
| val | `v_p4x` | `2e3e26360f1be84f` | 12 | 12 | 0 |
| val | `v_pfxi` | `2eb83412` | 8 | 8 | 0 |
| val | `v_rep` | `f301d8` | 7 | 7 | 0 |
| val | `v_lock` | `f001d8` | 7 | 7 | 0 |
| val | `v_x39` | `0f39c004` | **8** | 9 | **+1** |
| val | `v_x1f` | `0f1fc003` | **8** | 9 | **+1** |
| val | `v_x10` | `0f10c0` | **7** | 8 | **+1** |
| val | `v_x2a` | `0f2ac0` | **7** | 8 | **+1** |
| val | `v_y13` | `0f13060000` | **9** | 10 | **+1** |
| val | `v_add` | `81c03412` | 9 | 9 | 0 |
| val | `v_movm` | `a10000` | 8 | 8 | 0 |
| val | `v_push` | `50` | 6 | 6 | 0 |
| val | `v_xchg` | `93` | 6 | 6 | 0 |

**The divergence is exactly the eleven `0F`-escaped legs that carry NO prefix,
and nothing else.** `176 of 512` cells differ; every one of them is one of
those eleven legs, and every one differs by exactly one unit in the same
direction (the chip is earlier).

---

## 4. THE VERDICTS ON THE PRE-REGISTERED HYPOTHESES

Reported as registered, not restated.

| hypothesis | verdict | evidence |
|---|---|---|
| **H-A** — §86-as-registered / "the core is right"; chip = core on all 16 | **REFUTED** | chip ≠ core on 6 derivation legs, 576 traps, no exception |
| **H-B** — the diagnosis's `K5`; chip one unit earlier on ALL `0F` legs | **MISSED** | right on 15 legs of 16; predicts `z1b` = 6, chip measured **9** |
| **H-C** — `K4`, the prefix side alone | **REFUTED** | 7/16 |
| **H-D** — `K2`, §86's prose read literally | **REFUTED** | 12/16; misses `pfx2`, `pfx3`, `pfx4`, `z1b` |
| **H-E** — `K1` / `K7`, architectural | **REFUTED** | 5/16 and 12/16 |
| **H-F** — "none of the six" | **THIS IS THE OUTCOME** | no lattice rule makes the registered 16/16 bar |

The §3 quantitative bar (*"a rule is declared the measured law only if it
reproduces the chip's `pushed_off` on 16 of 16 legs"*) is therefore **not met by
any pre-registered rule**, and none was named. The replacement was stated as an
erratum and validated on a disjoint population, per the standing rule.

### 4.1 The control clauses

* **I-4 THE NULL — PASS.** `notf` and `v_notf`, 32 cells, **0** vector-1 entries.
  With TF clear the identical geometry traps not at all.
* **I-4b THE CONTROL BAND — PASS.** `nop`, `clc`, `incaw`, `movi`, `addrr`:
  chip = core on all five, 480 traps. The divergence is not "the two legs
  disagree about traps".
* **I-1** single writer OK · **I-2** socket only · **I-3** flash pin 20 entries
  before and after · **I-5** 0 invalid cells · **I-6** 36 `div_guard`
  boundaries, all PINNED, 0 UNPINNED · **I-7** 0 transport errors, 0
  `RigMismatch` · **I-8** 12.5 % ×3, 0 TAKE-unstable, 0 stream-distinct ·
  **I-9** full per-clock words retained, `SHA256SUMS` over both directories ·
  **I-10** `board_idle()` clean and **`check_ab_hw.py chip 800` = MATCH over
  800 rows** after everything.

---

## 5. THE MEASURED LAW, AND ITS DISJOINT VALIDATION

> **KM — SILICON.** An instruction contributes **ONE** TF boundary unit, plus
> **ONE MORE iff its opcode byte is not its first byte**. The extra unit is
> **one**, however deep the decoration and however many kinds of it.
>
> **KC — the `ucore`.** The same predicate, with the `0F` escape not counting
> as decoration.

| population | `KM` vs **chip** | `KC` vs **core** | `K5` vs chip | `KC` vs chip |
|---|---|---|---|---|
| DERIVATION (16 legs, 1,536 traps) | **16 / 16** | **16 / 16** | 15 / 16 | 10 / 16 |
| **VALIDATION (14 legs, 1,344 traps)** | **14 / 14** | **14 / 14** | 12 / 14 | 9 / 14 |

**All six registered validation bars are MET:**

* **V-1 MET** — `KM` reproduces the chip on 14/14, each single-valued over 96 traps.
* **V-2 MET** — `KC` reproduces the core on 14/14.
* **V-3 MET** — `K5` **misses** on `v_p2x` (predicts 7, measured 10) and
  `v_p4x` (predicts 9, measured 12). The validation population really does
  separate the replacement from the pre-registered rule it replaces; the score
  is evidence and not a restatement.
* **V-4 MET** — `v_notf`: 0 entries in 16/16 cells.
* **V-5 ANSWERED, not folded** — `v_rep` (`F3`) and `v_lock` (`F0`) both read
  **7**, the decorated value. **A REP prefix and a LOCK prefix are decoration
  exactly as a segment override is**; `KM`'s prefix term is "any prefix byte",
  not "any segment override". This was registered as an open question and is
  reported as its answer.
* **V-6 MET** — integrity bars unchanged, §4.1.

### 5.1 Two things the derivation population got wrong that the data corrected

1. **The diagnosis's shape composes ADDITIVELY; silicon SATURATES.** `K5` — the
   hypothesis the A3/D1/D2 §6.5 prediction implies — says a prefix stack and an
   `0F` escape each add a unit. Silicon adds **one** for both together: `z1b`,
   `v_p2x` and `v_p4x` (288 traps) all read the saturated value. **A landing
   that "adds a boundary for the `0F` escape" without this would REGRESS every
   prefixed-`0F` instruction**, and that regression is measured here rather than
   discovered later.
2. **A prefix STACK is one unit whatever its depth, on BOTH engines.**
   `pfx1`…`pfx4` are chip = core at every depth, 384 traps. §86's *"a prefix
   retires with its own F pop"* is right in kind and wrong in count: four
   prefixes contribute ONE extra boundary, not four.

### 5.2 ⚠ WHAT THIS OBSERVABLE DOES **NOT** RESOLVE

`pushed_off` measures the **COUNT** of units a probe contributes (1 vs 2), not
**where** the second one sits — at a count of 2 the third unit is the first pad
byte whatever the second unit's position. *"The second boundary is at the opcode
byte"* is an **INTERPRETATION** of the count, not a measurement. Resolving it
needs the trap to land one boundary earlier — an `IRET` setter, §86.C's own
W-3 asymmetry — and that cell is **not built here**. Registered in A-1.2a
before the validation data existed.

---

## 6. THE QS-PIN LEG — §86's REGISTERED PREDICATE IS REFUTED IN BOTH DIRECTIONS, ENGINE-FREE

§86 registers the sampling boundary as *"simply the opcode pops the `QS = 1`
pins announce."* That is a claim about a stream this rig **records**, so it is
checkable with no engine in the loop. `sw/tf0f_cell.py qs`.

**(a) The chip and the core emit the SAME QS stream — 480 of 480 cells, every
leg, compared op for op to the earlier leg's first vector-1 entry.** The
trap-boundary divergence is therefore **not** a queue, pop or decode-front-end
divergence; it is localised to what *consumes* the stream.

**(b) The `QS = 1` count is NOT the boundary count**, measured off the pins (the
anchor is the flush the previous trap's `IRET` causes; every op consumes exactly
one byte after it, and the frame is checked against `push imm16 ; popf`):

| leg | bytes | `QS = 1` on the pins | chip units | core units |
|---|---|---:|---:|---:|
| `nop` | `90` | 1 | 1 | 1 |
| `pfx1` | `2e01d8` | 2 | 2 | 2 |
| `pfx2` | `2e3e01d8` | **3** | 2 | 2 |
| `pfx3` | `2e3e2601d8` | **4** | 2 | 2 |
| `pfx4` | `2e3e263601d8` | **5** | 2 | 2 |
| `x1b` | `0f1be84f` | **1** | **2** | 1 |
| `y1e` | `0f1e06002005` | **1** | **2** | 1 |
| `z1b` | `2e0f1be84f` | 2 | 2 | 2 |
| `v_p4x` | `2e3e26360f1be84f` | **5** | 2 | 2 |

Two independent refutations, in **opposite** directions:

* **on a prefix stack the pins announce MORE than the boundary uses** — five
  `QS = 1` on `pfx4`, two boundary units — and this holds on **both engines**,
  so it is a correction to §86's PROSE and not a defect in either;
* **on a bare `0F` escape silicon uses a boundary the pins do NOT announce** —
  the escape's second byte is announced **SUBSEQUENT** (`QS = 3`) on both
  engines, measured, yet silicon's boundary count is 2.

**§86's landed RTL predicate is not touched by this** — `brk_smp_n` is the
SAMPLE side and `pushed_off` is the composite of sample and take. What is
refuted is the *sentence* "the sampling boundaries are simply the opcode pops
the `QS = 1` pins announce", as a description of the composite that decides
where the trap lands. The distinction was registered in the pre-registration
§2.1 before any board contact.

---

## 7. THE THREE ANCHOR SEATS — THE SIGNATURE REPRODUCES EXACTLY

`sw/tf0f_cell.py seats`, banked FLASH-era fabric captures, **both legs read off
the banked rows with no engine run**.

| seat | family | entries chip / core | `CODE` before first, chip / core | chip pushed PCs | core pushed PCs |
|---|---|---|---|---|---|
| `fz2c/404041` | D2 | 10 / 10 | 85 / 87 (**core +2**) | `8af8`, `8a21`, `8afd`, `8aff`, `8b02`, … | `8a21`, `8afd`, `8aff`, `8b02`, … |
| `fz2e/513019` | C2 | 17 / 17 | 82 / 84 (**core +2**) | `9b93`, `9b96`, `9b99`, `9b9a`, `9b9c`, … | `9b96`, `9b99`, `9b9a`, `9b9c`, … |
| `fz2e/501066` | D2 | 1 / 1 | 61 / 62 (**core +1**) | `ede8` | `edeb` |

**On two of the three, the core's pushed-PC list is the chip's list with the
FIRST ENTRY DELETED and every later entry byte-identical.** That is `KM − KC`
seen from the other end: the chip has one boundary unit at the `0F`-escaped
instruction that the core does not, so the chip traps there and the core does
not, and the core's first trap lands where the chip's *second* one did. The
third seat has a single entry and the two legs push three bytes apart — one
instruction, in a soup body whose instruction lengths are not uniform.

The seats are an **ANCHOR, not a derivation** (pre-registration §3.1). Three
seats cannot validate a rule and were not asked to; the rule was validated on
14 disjoint directed legs.

---

## 8. THE RTL CANDIDATE — BOOKED, NOT LANDED, WITH ITS REGRESSION TRAP NAMED

**The mechanism, located in the RTL.** `hdl/rtl/ucore/v30u_eu_step.svh`:

* a prefix byte goes to **`S_PFX_CHG`**, which sets `pop_is_first_n = 1'b1`
  (`prefix_retire()`), so the following pop is a boundary;
* the `0F` escape goes to **`S_EXT_CHG1` → `S_EXT_POP`**, and **`S_EXT_CHG1`
  does not set `pop_is_first_n`.** The comment on the line above the branch
  says it in as many words: *"the 0F escape is a 2-clock re-decode; every other
  prefix retires as its own 2-clock instruction with its own F pop."*

So `ucore_provenance.md` §86's sentence — *"a prefix retires as its own
two-clock instruction with its own F pop … **and the `0F` escape's first byte
does too**"* — is **true of silicon's boundary count and false of the RTL**.
The second half of that sentence was never implemented, and no gate saw it
because no golden and no fuzz seed in the standing set puts `PSW.TF` and an
`0F` escape at the same boundary.

**⚠ THE NAIVE FIX REGRESSES, AND THIS CELL MEASURED THE REGRESSION.** Setting
`pop_is_first_n = 1'b1` in `S_EXT_CHG1` gives a prefixed `0F` instruction
**three** boundary units (the prefix's, the escape's, and the opcode's) where
silicon uses **two**. `z1b`, `v_p2x` and `v_p4x` — **288 traps** — say
saturate. The landing must place **one** boundary per instruction beyond the
first-byte one, at the opcode byte, which means the boundary that
`S_PFX_CHG` schedules has to be **suppressed when the byte it schedules is a
`0F` escape** (a queue-lookahead the current structure does not have) rather
than a second boundary added beside it.

**Blast radius, stated because it is not small.** `q_first` drives the `QS`
pins. §6(a) measured that the chip and the core emit the **identical** QS
stream today on all 480 compared cells, so **any change that moves `q_first`
moves a stream that currently matches silicon exactly** and would have to be
re-scored against every golden that reads `qs`. A landing that changes the
*boundary* without changing the *pins* is the one to look for, and §6(b) says
such a thing must exist in the die, because on silicon the two already
disagree in both directions.

**Falsifier for the booked candidate:** any directed capture in which a
`0F`-escaped instruction with `PSW.TF` set traps at the same boundary on both
legs, or in which a prefixed `0F` instruction traps one unit earlier on the
chip than `KM` says.

---

## 9. PREDICTED SEAT REACH — SCORED AS REGISTERED

Pre-registration §5, registered before the run.

| clause | registered | now |
|---|---|---|
| **P-1** the three anchor seats: **2 of 3** close, `fz2c/404041` predicted NOT to close by this alone | 2 / 3 | **UNCHANGED and now better founded.** `fz2e/501066` and `fz2e/513019` carry the single displaced boundary and nothing else. `fz2c/404041`'s core leg retires a further far `CALL` after the displaced boundary and its streams re-align only 2/342, so one boundary is necessary and not evidently sufficient. |
| **P-2** the seven count-movers: **0 of 7** | 0 / 7 | **UNCHANGED.** They are gross count differences on escaped or runaway seeds and are not this mechanism. |
| **P-3** the wider TF family: **2–3 seeds**, and *"any claim of a two-digit seat gain from this mechanism is registered IN ADVANCE as unsupported"* | 2–3 | **UNCHANGED.** The corpus has 101 `PSW.TF` seeds; only 72 banked captures reach `IVT[1]` at all, 62 of those already agree exactly, and all 10 movers are already ledger failures. **The honest reach is 2–3 seeds.** |
| **P-4** a landing must lose **0** seeds corpus-wide | — | Not measurable here; no RTL was written. It is the bar the landing sitting inherits, and §8's regression trap is the first thing it must clear. |

---

## 10. WHAT THIS SITTING DID NOT DO

* **No RTL was edited**; `hdl/` is byte-identical to `310457b2f7` plus nothing.
* **No bitstream was built and none was flashed**; `flash_log.jsonl` is **20
  entries** before and after, and the board carries FLASH #17 throughout.
* No rule outside the registered lattice was derived from the derivation
  column and then scored on it: `KM` was stated as an erratum, committed, and
  scored on a disjoint 14-leg population.
* No head-to-head "the chip beats the core" figure is computed. Both columns
  are scored against **silicon**, which is the chip column itself.
* `sm3_tf_floor_cell` was **not** repaired or re-anchored. This cell replaces
  its *function* for the two-byte and prefixed cases; its 90 v1-anchored
  captures remain a frozen artefact.
* The `IRET`-setter cell that would resolve where the second boundary sits
  (§5.2) was **not** built.
