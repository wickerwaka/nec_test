# AMENDMENT A-2 to `rep_cl0_silicon_prereg_2026-08-17.md`

**Committed BEFORE the board leg it governs.**  Amends the pre-registration at
`0dc40e51dc` and **corrects amendment A-1** at `bb37f154f2`.

This amendment exists because **the validation cell as I registered it was
wrong**, and the error was found by the Phase-A tool work before any board
contact.  It is stated as an erratum, not restated as a plan.

---

## A-2.1 ERRATUM AGAINST THE PREREG §3 VALIDATION CELL

The prereg registered a validation cell at **CX ∈ {512, 768, 1024}**.  All
three of those values have **`CL == 0`**.  Two defects follow, and both are
mine:

1. **NO BRACKETING CONTROL.**  The derivation cell is readable *because* 255
   and 257 bracket 256.  A validation cell made entirely of `CL == 0` values
   has no in-family neighbour, so a null result there cannot be distinguished
   from a broken case construction.
2. **THE ARITHMETIC IN A-1 §A-1.3 IS WRONG.**  A-1 estimated ~4,200 / 6,300 /
   8,300 records for those counts and deferred the cell as uncapturable.  That
   estimate **assumed every case runs to completion**.  A byte form sitting
   inside the defect does not run at all — it is ~15–17 clocks.  The true
   position is worse than "too long": **the capture length depends on the
   answer**, which is exactly the property an instrument must not have when
   the answer is what is being measured.

A-1's R-1…R-4 stand.  A-1 §A-1.3's numbers and its "deferred as uncapturable"
disposition are **WITHDRAWN** and replaced by §A-2.2.

## A-2.2 THE VALIDATION CELL, RE-REGISTERED — DISJOINT IN **FORM**, NOT IN COUNT

The rule under test is a property of the **shared `REP` entry row**, so the
axis that makes a validation population disjoint is the **opcode**, not the
count.  The counts stay where the brackets are.

| axis | values |
|---|---|
| forms | `F3 AA` STOSB · `F3 AB` STOSW · `F3 AE` SCASB · `F3 AF` SCASW · `F3 6E` OUTSB · `F3 6F` OUTSW |
| CX | **255, 256, 257** |
| DF | 0 and 1 |

= 6 forms × 3 counts × 2 DF × 2 preloads = **72 cases**, none of them sharing
an opcode with the derivation cell.

**MEASURED capturability** (`v30sim timed-run --ndjson`, CX=257, the longest
count, instruction alone):

| form | clock rows | margin to 4096 |
|---|---|---|
| STOSB / STOSW | 1,057 | 3,039 |
| OUTSB / OUTSW | 2,085 | 2,011 |
| SCASB / SCASW | 2,603 | 1,493 |

All six fit, worst case 2,603.  **A-1 R-4's near-miss clause (any case landing
within 256 records of 4096) still governs and is still scored per case.**

## A-2.3 P-7 — THE RECORD COUNT IS ITSELF A DISCRIMINATOR

Registered as a new prediction, because it is the cleanest observable in the
cell and it depends on **neither** the store stub **nor** the reconstructed
final state:

> **P-7.**  For `F3 A4` at `CX = 256`, the captured trace length separates the
> hypotheses by two orders of magnitude:
> **H-SILICON ⇒ ~15–17 records** (the instruction does nothing);
> **H-ENGINE ⇒ ~2,085 records** (256 elements).
> *Falsifier*: a length in neither band.  A length in neither band is
> **H-THIRD** and is reported as such.

P-1 (final state), P-2 (bus-cycle census) and P-7 (trace length) are three
independent readings of one question.  **They must agree.**  Any disagreement
among them is a rig finding and **stops the sitting** — it is not adjudicated
by picking the two that agree.

## A-2.4 WHAT IS STILL DEFERRED

Nothing.  With §A-2.2 the validation cell is capturable, so A-1's blanket
deferral no longer applies.  **The standing constraint is unchanged in
substance**: the validation cell is captured *after* the derivation cell is
scored, and **no width rule derived from the derivation cell may be quoted as
validated until it has been scored on these 72 disjoint-form cases.**

Raising `EMIT_CAP` is still **not** taken in this sitting and is still a
separate registration.  Nothing in this cell now needs it.
