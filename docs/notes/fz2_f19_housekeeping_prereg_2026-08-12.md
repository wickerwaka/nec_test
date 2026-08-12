# PRE-REGISTRATION — THE F19 ERA RE-PIN OF THE MATERIALITY CENSUS AND THE `IMMATERIAL` DISPOSITION

    branch      fuzz-v2-on-relanding
    base        29a512f663   (FLASH #19 results banded; ghost LAUNCH relocation merged at ef19010e63)
    date        2026-08-12
    board       NOT TOUCHED.  No capture, no flash, no socket command, no
                Quartus compile.  Offline throughout.

    item        re-derive the materiality census + IMMATERIAL disposition
                against the **FLASH #19** ledger, move `fz2_ledger.CURRENT`
                to it, and return `fz2_immaterial falsify` to PASS

**THIS FILE IS COMMITTED BEFORE `fz2_materiality` OR `fz2_immaterial` IS RUN
AGAINST THE F19 LEDGER.**  Every number in §1 is DERIVED — from
`fz2_flash19_results_2026-08-12.md`, from the F18-era census and disposition
documents, from the F19 ledger itself (which is an INPUT, committed at
`c59c2caf30`), and from the two tools' own source.  Not one of them is read off
a run of either tool on the F19 ledger.  Where a derivation is under-determined
the alternatives are registered here rather than chosen after the run.

This is the exact analogue of `fz2_f18_housekeeping_prereg_2026-08-11.md`
item 1, and it follows that file's shape deliberately.

---

## §0 WHY, AND WHY IT IS *ONLY* AN ERA RE-PIN

`fz2_flash19_results_2026-08-12.md` §4.5 (**C-12**) measured
`fz2_immaterial falsify` on the F19 ledger and reported **G6 (3 of 8 cells) and
G7 (1 of 25) FAIL, and both are doc-vs-derivation cross-checks** against
documents that record the F18 numbers.  That sitting **booked the repair and
did not apply it**, in its own words: *"a G7 disagreement means the document is
stale, not that the corpus moved… the fix is booked, not applied in this
sitting."*  This is that repair.

⚠ **AND THE `CURRENT` POINTER NEVER MOVED.**  `sw/fz2_ledger.py:CURRENT` still
names `fz2_failure_ledger_f18_2026-08-11.json` while the working tree's
captures are F19's.  That is why `fz2_immaterial falsify` currently dies at the
sha gate on `fz2c/404049` before classifying a single seed — **the guard doing
exactly its job**, and the last four eras moved `CURRENT` in the flash sitting's
own results commit (`770c0d1b85`, `1ad5074ebe`, `b2e364fa50`, `b938bc81b3`).
FLASH #19's results commit did not.  Registered here as part of the re-pin.

## §0.1 WHY THE GHOST LAUNCH RELOCATION CANNOT ENTER THIS CENSUS — DERIVED, NOT ASSUMED

The relocation merged at `ef19010e63`, **after** FLASH #19 was flashed and
captured.  It is **not on any flashed bitstream**.  The census's input is the
banked FABRIC capture of each seed: the socket leg is silicon and the core leg
is the **FPGA** core of the flashed `.sof` (`03365b1115e1f338…`, built from
`fc0ae65d56`).  Neither leg can contain a line of RTL that did not exist when
the bitstream was built.

**Registered consequence: ZERO relocation-driven cells in this census.**  The
falsifier is trivial and it is stated anyway — *any* movement in this
re-derivation that is not accounted for by the six F19 movers is a FINDING
against the claim that the census reads fabric rows and nothing else.

## §0.2 WHAT THIS DOES *NOT* TOUCH — HARD, AS AT F18

No clause of `evidence()`, no class boundary, `CYCLE_DEFINING` stays
`("bs", "t")`, no seed list enters either tool, no bar's meaning moves, and
**no parser change is registered this time** (the F18 sitting already made
`census_doc()` / `dispo_doc()` anchor-scoped, and that shape is what makes an
append-only history possible).  What changes is the two **documents** and the
one-line `CURRENT` pointer.

---

## §1 THE PREDICTED PARTITION — PRIMARY POINT PREDICTION

The F19 population is the F18 population **plus four entrants and minus zero
leavers**, with two further F18-era passers becoming **discards** (out of the
denominator entirely, amendment A-12).  From `fz2_flash19_results_2026-08-12.md`
§4.4:

| seed | movement | ledger `arch` / `done_chip` / `done_core` (F19 ledger, the INPUT) |
|---|---|---|
| `fz2e/508068` | ENTERED | `NODUMP` · chip **True** · core **False** |
| `fz2e/509050` | ENTERED | 14 differing words · chip True · core True |
| `fz2e/514001` | ENTERED | 14 differing words · chip True · core True |
| `fz2e/526075` | ENTERED | `NODUMP` · chip **True** · core **False** |
| `fz2e/524027` | → DISCARD (`ps3_8080`) | not in the census population at all |
| `fz2e/535070` | → DISCARD (`ps3_8080`) | not in the census population at all |

**Each of the four is predicted FUNCTIONAL, and the derivation is per seed:**

* `509050` and `514001` — both legs dumped and the dumps differ in 14 words, so
  `fz2_materiality.evidence()`'s first branch (`arch_words` non-empty) gives
  **FUNCTIONAL**;
* `508068` and `526075` — `done_core` is **False**, so the core leg's
  MAGIC-anchored dump did not form while the chip's did.  That is `evidence()`'s
  **third** branch (`else: klass = FUNCTIONAL`, *"dump produced by CHIP only"*).
  ⚠ It is **NOT** UNSCOREABLE: UNSCOREABLE requires `dump_r is None and dump_s
  is None`, i.e. **neither** leg.  This is the distinction the census's own §I.4
  banner records (*"the asymmetry IS the divergence"*), and it is the one place
  this prediction could be wrong in a way that moves two cells at once.

| class | F18 (live, registered) | movement, derived | **F19 PREDICTED** |
|---|---:|---|---:|
| FUNCTIONAL | 45 | + all four entrants | **49** |
| TIMING | 30 | none | **30** |
| TRANSIENT | 5 | none | **5** |
| COSMETIC | 19 | none | **19** |
| UNSCOREABLE | 11 | none | **11** |
| **total** | **110** | ENTERED 4 / LEFT 0 | **114** |
| **IMMATERIAL** (transient + cosmetic) | **24** | none | **24** |
| **working residue** | **86** | | **90** |
| `TIMING_RECONVERGED` | **8** | `fz2e/530020` leaves | **7** |

### §1.1 THE ARITHMETIC CROSS-CHECK THAT MAKES THIS A POINT PREDICTION AND NOT A GUESS

FLASH #19 measured **G6: 3 of 8 cells disagree** with the F18 document.  G6's
eight cells are the five class counts, `IMMATERIAL`, the total, and
`TIMING_RECONVERGED` (`fz2_immaterial.cmd_falsify`).  The F19 results document
independently states **total 114**, **IMMATERIAL 24** and **residue 90** (§4.5)
and **`TIMING_RECONVERGED` reads 7** (§4.3).  So:

1. `total` disagrees (110 ≠ 114) — **cell 1**;
2. `TIMING_RECONVERGED` disagrees (8 ≠ 7) — **cell 2**;
3. `IMMATERIAL` **agrees** (24 = 24), stated outright by §4.5's membership
   clause (*"the 24 members are set-for-set identical, and every member's row
   count, done clock, cycle count and differing-column list are byte-identical
   to FLASH #18's census"*);
4. therefore **exactly one class count disagrees** — cell 3.  TRANSIENT and
   COSMETIC sum to IMMATERIAL = 24, so if either moved the other must move the
   other way, which would be **two** cells and take the total to four.  **Both
   are therefore fixed at 5 and 19**, and the single moving cell is FUNCTIONAL,
   TIMING or UNSCOREABLE.  Their sum must be 114 − 24 = **90**, against 86 at
   F18, so **one cell takes all four**.

The per-seed derivation above says that cell is **FUNCTIONAL, 45 → 49**.  The
two alternatives are named so a miss is legible and not re-narrated:

| branch | what it would mean |
|---|---|
| **A — FUNCTIONAL 49** *(REGISTERED CALL)* | all four entrants classify FUNCTIONAL, per `evidence()`'s first and third branches |
| **B — TIMING 34** | all four have identical dumps and a changed schedule — contradicted by `509050` / `514001`'s 14 differing words in the ledger itself |
| **C — UNSCOREABLE 15** | all four have NO dump on EITHER leg — contradicted by `done_chip` True on all four |

A **split** across two of these cells is a fourth outcome; it would make G6
read 4 of 8 rather than 3 of 8 and would therefore contradict the FLASH #19
results document's own measurement.  **That is reported as a finding against
that document, not absorbed.**

### §1.2 THE SECONDARY CELLS — REGISTERED, THOUGH G6 DOES NOT READ THEM

| bar cell | F18 | **F19 PREDICTED** | derivation |
|---|---:|---:|---|
| **G1 pool** (no dump proof) | 23 | **25** | 11 UNSCOREABLE + 12 one-sided FUNCTIONAL, + `508068` + `526075` |
| **G2 pool** (two-sided dumps that differ) | 33 | **35** | + `509050` + `514001` |
| **G4** FALSE on | 86 / 110 | **90 / 114** | the residue |
| **G4** by first failing clause | arch 33 · cycle_starts 30 · no_dump_proof 23 | **arch 35 · cycle_starts 30 · no_dump_proof 25** | sums to 90 |
| **G3** pool | 80 | **80** | the schedule pool is TIMING+IMMATERIAL+UNSCOREABLE-side, none of which moved |
| **C-ROW / C-ARCH** | 110/110 · 110/110 | **114/114 · 114/114** | measured and published by FLASH #19 §4.5 |

`G3`'s pool is the one cell above that is *derived by exclusion* rather than
stated; if it moves, that is reported, and it is not a class-boundary claim.

## §1.3 THE PREDICTED `IMMATERIAL` MEMBERSHIP — 24, ZERO CHANGE, ZERO LEAVERS

**Predicted: the F18 twenty-four, seed for seed, with every `cyc`, `done`,
row-count and differing-column cell byte-identical.**  FLASH #19 §4.5 states
this as a measurement; this document registers it as the prediction the
re-derivation must reproduce, and **a single changed cell is a FINDING**.

Note what this means and what it does not: it means the four entrants are all
MATERIAL, so the residue grows 86 → 90 while the immaterial class does not
move at all.  **The re-pin makes the residue BIGGER.**  It is registered that
way, in that direction, before it is run.

## §1.4 `TIMING_RECONVERGED` — 8 → 7, AND THE USER'S RULING CARRIES UNCHANGED

The leaver is **`fz2e/530020`**, the D1 seed the F18 housekeeping admitted
(7 → 8) *with a falsifier written beside it*: *"a double capture in which its
two `done` clocks are stable — if they flicker, the membership is capture noise
and 8 is not a ratchet."*  FLASH #19 §4.3 records that **the falsifier FIRED**:
`530020`'s `diverging_rows` moved 326 → 671, the only shared-failure row count
that moved in the whole corpus, and the reconverged count reads 7.

**RULED 2026-08-11 and carried forward verbatim: *"Timing reconvergence seeds
are material."*** The ruling is a rule about a PREDICATE, not a seed list, so
it applies to the seven without being re-asked.  All 7 stay MATERIAL and inside
the 90.

⚠ **Registered explicitly: `TIMING_RECONVERGED` is NOT a ratchet and this is
the second era in a row in which it moved by one seed with no mechanism.**
Its own F18 falsifier fired at F19; the honest reading is that this cell tracks
the capture noise floor, not a property of the core, and it is reported as a
cell rather than as a result.

---

## §2 THE DOCUMENT SHAPE — APPEND-ONLY, AS AT F18

**The A-14 pattern: supersession, never overwrite.**  Both documents keep every
F18 table **verbatim**, demoted under a dated *"SUPERSEDED BY FLASH #19"*
banner exactly as PART II (FLASH #17) already sits under PART I.  The F19 block
becomes PART I, the F18 block becomes PART II, and the FLASH #17 block stays
PART III with its content byte-identical.

The live anchor pairs move to the F19 blocks; the F18 blocks' anchors are
renamed `CENSUS-PARTITION-F18-BEGIN/END` and
`IMMATERIAL-MEMBERS-F18-BEGIN/END` so **exactly one live pair of each exists**
— the rename the F18 sitting applied to F17's.  No F18 or F17 number is edited,
deleted or restated.

---

## §3 THE BARS

| # | bar | how it is scored |
|---|---|---|
| **K-1** | `fz2_materiality` controls on the F19 ledger: **C-ROW 114/114, C-ARCH 114/114**, exit 0 | the census is quotable or it is not |
| **K-2** | the derived partition equals §1's — **FUNCTIONAL 49 · TIMING 30 · TRANSIENT 5 · COSMETIC 19 · UNSCOREABLE 11 · total 114 · IMMATERIAL 24 · TIMING_RECONVERGED 7** — or the miss is reported cell by cell under §1.1's registered branches | point prediction, reported as registered |
| **K-3** | IMMATERIAL membership = the F18 twenty-four, **zero entrants, zero leavers**, every cell byte-identical | set for set, printed; a changed cell is a FINDING |
| **K-4** | the four entrants classify **FUNCTIONAL**, printed with `evidence()`'s own `sub` string, so the branch each took is visible | §1's per-seed derivation |
| **K-5** | `fz2_immaterial falsify` exits **0**, G1–G8 all PASS, on the F19 ledger | the booked repair |
| **K-6** | **the falsifier is DEMONSTRATED TO FAIL** on a perturbation applied to a COPY outside the repo, caught by a NAMED bar | a falsifier that has only ever passed has not been shown to be one |
| **K-7** | `sw/fz2_ledger.py:CURRENT` names the F19 ledger, and every consumer that reads it through `load()` still prints the file it read | the era re-pin |
| **K-8** | `fz2_w1 lint` PASS · `test_artifact` **45/45** · **zero diffs under `sw/testdata/`** except a legitimately regenerated `fz2_bars.json` | nothing moves |

⚠ **`fz2_w1 bars` is carried as REGISTERED, NOT re-litigated.**  FLASH #19
reported **10/11 with C-6 MISSED** (`fz2_flash19_results_2026-08-12.md`), and
that verdict is this sitting's input, not its subject.  A `bars` run here is
reported for the record; **it is not a bar of this document and it is not
re-argued.**

**K-8's `sw/testdata/` clause is a HARD STOP**: this work writes nothing into
any banked artifact.

---

## §4 HARD STOPS

1. Any write under `sw/testdata/` other than a regenerated `fz2_bars.json`.
2. Any edit to `evidence()`'s clauses, to `CYCLE_DEFINING` / `VALUE_ONLY`, or
   to any class boundary.
3. Any seed list appearing in either tool.
4. Admitting or evicting a member in order to reach a count.
5. Any board contact or Quartus compile.
6. Editing, deleting or restating a FLASH #17 or FLASH #18 number.

## §5 WHAT WOULD MAKE THIS A MISS

* the derived partition contradicting all three of §1.1's branches, or
  splitting across two cells (a finding against FLASH #19's own `3 / 8`);
* any change at all in the 24-member table (a finding against FLASH #19 §4.5);
* `falsify` passing but not being demonstrable as failing (K-6);
* any relocation-driven movement in a fabric-derived cell (§0.1).

Each is reported in the form it is registered in here.  Nothing is
re-registered after the fact.
