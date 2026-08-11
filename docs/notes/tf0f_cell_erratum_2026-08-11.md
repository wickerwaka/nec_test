# AMENDMENT A-1 TO THE TF × `0F` CELL — THE DERIVATION LEG IS MEASURED, THE REGISTERED H-B IS **MISSED**, AND THE REPLACEMENT IS REGISTERED HERE BEFORE ITS VALIDATION POPULATION IS CAPTURED

**Committed BEFORE the validation population's first board contact.** Amends
`docs/notes/tf0f_cell_prereg_2026-08-11.md` (committed `f08a597ed5`, before the
derivation leg's first board contact). Board still carries **FLASH #17**,
`flash_log.jsonl` still **20 entries**; no RTL touched, no bitstream built.

---

## A-1.0 WHY THIS DOCUMENT EXISTS

The standing rule, verbatim (CLAUDE.md): *"A refuted key's REPLACEMENT must be
validated on data that was not used to select it. … choosing its successor by
scanning the same capture and then scoring the successor on that capture is
fitting, and the score is not evidence. **State the erratum, then validate on a
disjoint population before the replacement is quoted.**"*

The derivation leg refuted five of the six pre-registered lattice rules and
**missed the sixth on one leg of sixteen**. A replacement is derivable from the
measured column. This document states the erratum and registers the replacement
**and its disjoint validation population and per-leg predictions** before that
population is captured.

---

## A-1.1 THE DERIVATION LEG, AS MEASURED

`sw/testdata/tf0f/board/` — 272 cells, 1,536 traps, 0 transport errors,
0 TAKE-unstable, `div_guard` **PINNED** at all 18 boundaries, socket only,
`flash_log.jsonl` 20 entries throughout.

| leg | bytes | **chip** | core | K1 | K7 | K3 | K5 | K4 | K2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `nop` | `90` | **6** | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| `clc` | `f8` | **6** | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| `incaw` | `40` | **6** | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| `movi` | `b83412` | **8** | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| `addrr` | `01d8` | **7** | 7 | 7 | 7 | 7 | 7 | 7 | 7 |
| `pfx1` | `2e01d8` | **7** | 7 | 8 | 8 | 7 | 7 | 7 | 7 |
| `pfx2` | `2e3e01d8` | **8** | 8 | 9 | 9 | 8 | 8 | 6 | 6 |
| `pfx3` | `2e3e2601d8` | **9** | 9 | 10 | 10 | 9 | 9 | 6 | 6 |
| `pfx4` | `2e3e263601d8` | **10** | 10 | 11 | 11 | 10 | 10 | 6 | 6 |
| `x13` | `0f13c0` | **7** | 8 | 8 | 7 | 8 | 7 | 8 | 7 |
| `x1b` | `0f1be84f` | **8** | 9 | 9 | 8 | 9 | 8 | 9 | 8 |
| `x18` | `0f18c005` | **8** | 9 | 9 | 8 | 9 | 8 | 9 | 8 |
| `x28` | `0f28c0` | **7** | 8 | 8 | 7 | 8 | 7 | 8 | 7 |
| `x33` | `0f33c3` | **7** | 8 | 8 | 7 | 8 | 7 | 8 | 7 |
| `y1e` | `0f1e06002005` | **10** | 11 | 11 | 10 | 11 | 10 | 11 | 10 |
| `z1b` | `2e0f1be84f` | **9** | 9 | 10 | 9 | 9 | **6** | 9 | 6 |
| | agreement, of 16 | | | 5 | 12 | 10 | **15** | 7 | 12 |

Every leg is **single-valued across all 16 of its cells and all 6 of its
traps** — 96 traps per leg, one value each, on both engines.

### A-1.1a The verdicts on the registered hypotheses

* **H-A (§86-as-registered / "the core is right") — REFUTED.** The chip differs
  from the core on **six legs**: `x13`, `x1b`, `x18`, `x28`, `x33`, `y1e` — every
  `0F`-escaped leg that carries **no prefix** — and on each the chip's boundary
  is **exactly one unit EARLIER**. 576 traps, no exception, at every wait level
  and every alignment.
* **H-B (the diagnosis's K5) — MISSED, ON ONE LEG OF SIXTEEN.** It predicted the
  chip column exactly on 15 legs and predicted `z1b` (`2E 0F 1B E8 4F`,
  prefix **and** escape) = **6**; the chip measured **9**. **Reported as
  registered, not restated.**
* **H-C (K4) — REFUTED** (misses `pfx2`, `pfx3`, `pfx4` and all six `0F` legs).
* **H-D (K2, §86's prose read literally) — REFUTED** (12/16; misses `pfx2-4`,
  `z1b`).
* **H-E (K1 / K7) — REFUTED** (5/16 and 12/16).
* **H-F ("none of the six") — THIS IS THE REGISTERED OUTCOME.** No lattice rule
  reproduces the chip column on 16 of 16, so the §3 quantitative bar is **not
  met by any pre-registered rule** and none may be named the measured law.

### A-1.1b The control clauses

* **I-4 THE NULL — PASS.** `notf`, 16 cells, **0** vector-1 entries.
* **I-4b THE CONTROL BAND — PASS.** `nop`, `clc`, `incaw`, `movi`, `addrr`:
  chip = core on all five, all 480 traps. The divergence is not "the chip and
  the core disagree about traps"; it is confined to the `0F` escape.
* **The prefix ladder is NOT the divergence.** `pfx1`…`pfx4` are chip = core at
  every depth, and both engines saturate: **one extra unit however deep the
  stack**. §86's *"a prefix retires with its own F pop"* is right in kind and
  wrong in count on both engines — a stack of four prefixes contributes ONE
  extra boundary, not four.

---

## A-1.2 THE REPLACEMENT, STATED BEFORE IT IS VALIDATED

> **KM — THE MEASURED SILICON LAW.** An instruction contributes **ONE** TF
> boundary unit, plus **ONE MORE if and only if its opcode byte is not its
> first byte** — that is, iff it carries a prefix stack and/or an `0F` escape.
> The extra unit is **one**, however deep the decoration is and however many
> KINDS of decoration are present.

> **KC — the ucore's own measured behaviour.** The same predicate with the `0F`
> escape not counting as decoration.

**Their difference is ONE term**, and it is the whole chip-vs-core divergence
this cell measured: silicon counts the `0F` escape as decoration; the ucore
does not.

`z1b` is what separates `KM` from the registered `K5`: `K5` composes the two
decorations **additively** and predicts three units; `KM` **saturates** and
predicts two. The chip measured two. `KM` is therefore not "K5 plus an
exception" — it is a simpler predicate than K5, with one clause instead of two,
and no per-opcode case anywhere (standing simplicity principle).

### A-1.2a ⚠ WHAT THE OBSERVABLE DOES **NOT** RESOLVE

`pushed_off` measures the **COUNT** of units a probe contributes (1 vs 2), not
**where** the second one sits: at a count of 2 the third unit is the first pad
byte whatever the second unit's position inside the probe. *"The second boundary
is AT the opcode byte"* is therefore an **INTERPRETATION** of the count, not a
measurement. Every writing of `KM` in this campaign carries that flag. A cell
that resolved the position would need the trap to land one boundary earlier —
an `IRET` setter (§86.C's W-3 asymmetry) — and is **not built here**.

---

## A-1.3 THE DISJOINT VALIDATION POPULATION AND ITS PER-LEG PREDICTIONS

**Fifteen legs. Every byte sequence appears nowhere in the derivation set.**
Same axes (waits 0–3 × align 0–3), same reader, same 6 traps per cell: **240
cells, 1,344 scored traps** plus a 16-cell null. Predictions are the chip's
`pushed_off`.

| leg | bytes | dec? | **KM** | KC | K5 | K3 | separates |
|---|---|---|---:|---:|---:|---:|---|
| `v_p2x` | `2e 3e 0f 1b e8 4f` | pfx+esc | **10** | 10 | 7 | 10 | **KM vs K5** — the saturation test on new bytes |
| `v_p4x` | `2e 3e 26 36 0f 1b e8 4f` | pfx+esc | **12** | 12 | 9 | 12 | **KM vs K5**, deepest decoration in the campaign |
| `v_x39` | `0f 39 c0 04` | esc | **8** | 9 | 8 | 9 | **KM vs KC** (chip vs core) |
| `v_x1f` | `0f 1f c0 03` | esc | **8** | 9 | 8 | 9 | **KM vs KC** |
| `v_x10` | `0f 10 c0` | esc | **7** | 8 | 7 | 8 | **KM vs KC** |
| `v_x2a` | `0f 2a c0` | esc | **7** | 8 | 7 | 8 | **KM vs KC** |
| `v_y13` | `0f 13 06 00 00` | esc, mod≠3 | **9** | 10 | 9 | 10 | **KM vs KC**, memory EA |
| `v_pfxi` | `2e b8 34 12` | pfx | **8** | 8 | 8 | 8 | prefix on a non-escaped multi-byte op |
| `v_rep` | `f3 01 d8` | pfx | **7** | 7 | 7 | 7 | **is a REP prefix "decoration"?** |
| `v_lock` | `f0 01 d8` | pfx | **7** | 7 | 7 | 7 | **is a LOCK prefix "decoration"?** |
| `v_add` | `81 c0 34 12` | none | **9** | 9 | 9 | 9 | undecorated, 4 bytes, opcode+ModR/M+imm16 |
| `v_movm` | `a1 00 00` | none | **8** | 8 | 8 | 8 | undecorated, 3 bytes, memory operand |
| `v_push` | `50` | none | **6** | 6 | 6 | 6 | undecorated, 1 byte |
| `v_xchg` | `93` | none | **6** | 6 | 6 | 6 | undecorated, 1 byte |
| `v_notf` | `2e 0f 1b e8 4f` | — | **0 entries** | | | | THE NULL again, on a decorated probe |

**REGISTERED BARS FOR THE VALIDATION LEG:**

* **V-1** `KM` reproduces the **chip** column on **14 of 14** scored legs, each
  single-valued over its 96 traps. Anything less and `KM` is **not** quotable as
  the measured law and the campaign books a partial.
* **V-2** `KC` reproduces the **core** column on **14 of 14**. This is the
  cross-check that the one-term difference is the whole difference; a `KC` miss
  means the ucore's own rule is also not `KC` and the two-engine story is
  incomplete.
* **V-3** `K5` **must MISS** on `v_p2x` and `v_p4x` (it predicts 7 and 9 where
  `KM` predicts 10 and 12). If `K5` and `KM` agree everywhere in this
  population, the population did not validate anything and says so.
* **V-4** `v_notf` produces **0** vector-1 entries in all 16 cells.
* **V-5** `v_rep` and `v_lock` are the only legs whose "decoration" class is not
  a segment override. **They are registered as an OPEN QUESTION, not as a
  prediction of `KM`'s truth**: if either reads `8` instead of `7`, `KM`'s
  "prefix stack" term is narrower than "any prefix byte" and that is a FINDING,
  reported as one, not folded into `KM`.
* **V-6** integrity bars **I-1…I-10** of the pre-registration apply unchanged.

---

## A-1.4 THE THREE ANCHOR SEATS — READ, AND THEY REPRODUCE THE SIGNATURE

`sw/tf0f_cell.py seats`, banked fabric captures, both legs read (no engine run):

| seat | entries chip / core | `CODE` before first, chip / core | chip pushed PCs | core pushed PCs |
|---|---|---|---|---|
| `fz2c/404041` | 10 / 10 | 85 / 87 (**core +2**) | `8af8`, `8a21`, `8afd`, `8aff`, … | `8a21`, `8afd`, `8aff`, … |
| `fz2e/513019` | 17 / 17 | 82 / 84 (**core +2**) | `9b93`, `9b96`, `9b99`, `9b9a`, … | `9b96`, `9b99`, `9b9a`, … |
| `fz2e/501066` | 1 / 1 | 61 / 62 (**core +1**) | `ede8` | `edeb` |

**On two of the three seats the core's pushed-PC list is the chip's list with
the FIRST ENTRY DELETED and every later entry byte-identical.** That is exactly
`KM` − `KC`: the chip has one boundary unit that the core does not, at the
`0F`-escaped instruction; the chip traps there, the core does not, and the
core's first trap lands where the chip's second one did. The third seat has a
single entry and the two legs push 3 bytes apart — one instruction, in a soup
body whose instruction lengths are not uniform.

**This is an ANCHOR, not a derivation** (§3.1 of the pre-registration): three
seats cannot validate a rule and are not being asked to.
