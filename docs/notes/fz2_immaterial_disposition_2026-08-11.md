# THE `IMMATERIAL` DISPOSITION — A FORMAL CLASS FOR THE DIVERGENCES THAT COST NOTHING

    tool        sw/fz2_immaterial.py            (reviewer-re-runnable, offline)
    census      sw/fz2_materiality.py           (imported as a library, not forked)
    input       sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
                + the 113 banked FABRIC captures it names, sha256-verified
    branch      fuzz-v2-on-relanding @ ae3da7c59a
    era         sof 26c19f613e2caae8…  (FLASH #17)
    date        2026-08-11
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.

    reproduce   python3 sw/fz2_immaterial.py falsify       # the eight bars
                python3 sw/fz2_immaterial.py census        # the 21, with evidence
                python3 sw/fz2_immaterial.py reconverged   # the 7 still open

---

## 0. THE RULING, AND WHAT THIS DOCUMENT DOES WITH IT

The user, 2026-08-11, verbatim:

> "An address value being presented on the bus that is never used does not
> impact functionality or timing. A pin changing state slightly earlier or
> later is not significant if it doesn't change the overall timing."

and, on the disposition itself: *"Do everything except the merge."*

The materiality census (`docs/notes/fz2_materiality_census_2026-08-11.md`,
`d3ce6b2043`) **measured** that criterion across the 113 F17 ledger failures and
partitioned them **FUNCTIONAL 48 / TIMING 33 / TRANSIENT 2 / COSMETIC 19 /
UNSCOREABLE 11**. It was a lens and nothing more: it dispositioned nothing and
moved nothing.

**This document gives the 21 immaterial seeds — 19 COSMETIC + 2 TRANSIENT — a
FORMAL DISPOSITION.** They leave the **working residue** and **stay in the
ledger**, in the denominator, and in every rate they were already in. Nothing is
excluded, nothing is deleted, nothing is renamed.

    WORKING-RESIDUE = 92 = 113 − 21

**The headline, and the form it must be quoted in:**

> **92 material-or-unproven of 113 diverging of 3,837**
> — 48 FUNCTIONAL + 33 TIMING + 11 UNSCOREABLE, with 21 dispositioned
> `IMMATERIAL`.

⚠ **NO RATE, BAR OR VERDICT MOVES.** `sw/fz2_w1.py bars` is **11/11 MET**,
byte-identical across this work, and this disposition is deliberately **not
wired into any scorer**. It is a lens on the failure ledger, not a scoring
change. Wiring it into a rate would be the thing the A-14 precedent exists to
prevent.

---

## 1. THE PRECEDENT — A-14, FOLLOWED CLAUSE FOR CLAUSE

`ROW_MATCHED` (amendment **A-14**, `sw/fz2_rowmatch.py`, prereg §36–§37) was
created on the user's ruling of 2026-08-09 — *"if these seeds are matching
between real CPU and core, then it doesn't matter if they aren't producing the
final state dump."* Its shape is the shape this disposition takes:

| A-14's property | how `IMMATERIAL` carries it |
|---|---|
| a disposition with its **own falsifier** | `sw/fz2_immaterial.py falsify` — **eight** bars, G1–G8, each with a denominator, non-zero exit on any failure |
| **derived from the record per seed**, never a seed list | `evidence()` computes six clauses from `fz2_materiality.measure()`'s leaves on every invocation. **There is no seed list in the tool.** The 21 named in §3 are named *for the reader*, and **G7 is the bar that they are exactly what the code derives** |
| **dispositioned, not explained** | the census's own mechanism labels (`family`, `mech`, the banked `sub`) stay banked and stay the honest description of *why* each seed diverges. This class says the divergence **costs nothing measurable**, not that it is understood |
| **rates unmoved** | `bars` 11/11 byte-identical; nothing wired into a scorer |
| **its own non-vacuity check** | G4: the predicate must be FALSE on a positive number of entries — it is FALSE on **92 / 113** |

**One thing `IMMATERIAL` is NOT: it is not `ROW_MATCHED`.** `ROW_MATCHED` is the
class for legs that do **not** differ at all. **Every member of `IMMATERIAL`
diverges on at least one row** — clause (6) says so out loud, and G4's breakdown
shows the two classes are answering different questions on different
populations.

---

## 2. THE PREDICATE — SIX CLAUSES, EACH ONE MAKING THE CLASS SMALLER

`sw/fz2_immaterial.py:evidence()` **is** the definition. It reads the leaves
`fz2_materiality.measure()` writes — **the census's own measurement, imported as
a library** — and adds **no second comparator**. `fz2_materiality` gained one
function in this work, `measure_all()`, which is the four statements `main()`
already inlined; **the census's printed output is byte-identical across the
extraction** (verified by diff).

| clause | what it requires | why it is there |
|---|---|---|
| **(1) C-CONTROL** | the census's two controls PASS on this seed, **re-derived from the banked rows on this invocation**: `diff_rows` reproduces the ledger's `first_bad_row` / `diverging_rows` / `compare_window` (C-ROW), and `arch_dump` reproduces its banked `arch_words` / `arch_sim_words` (C-ARCH) | a lens that reads the rows differently from the scorer is measuring its own parser. A disposition resting on one would be dispositioning the parser |
| **(2) D-PROOF** | **both** legs produced a 15-word `MAGIC`-anchored terminator dump | **THE NON-DEGENERACY CLAUSE.** The class rests entirely on a **dump-identity proof of non-propagation**; with no dump there is no proof, and a seed with no proof must not be dispositioned by silence. This clause alone holds all **11 UNSCOREABLE** seeds out, and §4 keeps them open |
| **(3) D-IDENT** | the two dumps are **bit-identical, word for word**, over `AW BW CW DW BP IX IY SP PC PS PSW DS0 DS1 SS MAGIC` | this is the direct measurement that whatever was on the bus **never propagated** — not an argument that it could not |
| **(4) S-STARTS** | every bus cycle starting inside the compare window starts on the **same clock in both legs** — no cycle exists on a clock where the other leg has none | measured in the **clock domain, not the cycle-index domain**: one insertion offsets every later index, so an index comparison cannot tell an inserted cycle from a shifted one |
| **(5) S-DONE** | both legs reach the done marker on the **same clock** (`done_delta == 0`) | the closest thing this rig has to *"how long the program took"*. **`None` fails this clause**; it is never read as zero |
| **(6) DIVERGENT** | the seed differs on **at least one row** | so the class can never absorb a **matching** seed — that is A-14's `ROW_MATCHED`, a different disposition — and so a reader can see this class is a statement about a **real** difference costing nothing |

**The sub-class is the census's own TRANSIENT / COSMETIC split, CARRIED and not
re-derived.** The boundary — `CYCLE_DEFINING = ("bs", "t")` versus everything
else — lives in `fz2_materiality` and in exactly one place. Both sub-classes are
`IMMATERIAL`; the split says **which of the user's two sentences** a seed
answers to:

* **COSMETIC (19)** — *"an address value presented on the bus that is never
  used"*. Every diff is a **value** on `ad_addr` / `ad_data` / `ps` / `qs` /
  `ube_n` at a matched position.
* **TRANSIENT (2)** — *"a pin changing state slightly earlier or later"*. At
  least one diff lands on a **cycle-defining** column (`t`, `bs_early`) while
  every cycle still starts on the same clock.

### 2.1 ⚠ THE HONESTY CLAUSE, INHERITED VERBATIM FROM THE CENSUS

`IMMATERIAL` means **"no architectural consequence WAS OBSERVED on 15 registers
at the end of the run"**, not *"provably none exists"*. A divergence that changed
only memory the program never re-read, or a register the terminator's own
prologue overwrites before the store, would be invisible to it. That limit is
the reason the disposition leaves the seed **in the ledger** rather than
excluding it: **an `IMMATERIAL` seed is still a divergence between silicon and
the core, and the correctness target is silicon match.**

---

## 3. THE 21, NAMED WITH THEIR EVIDENCE

Grouped by the ledger's A-15 family, carried forward unmodified. `cyc` is the
bus cycles each leg ran inside the compare window — **identical in both legs on
all 21, by clause (4)**; `done` is the done-marker clock, **identical in both
legs on all 21, by clause (5)**.

⚠ **This table is the reader's copy, not the class.** The class is COMPUTED by
`evidence()` on every invocation, and **G7 fails loudly if this table and the
derivation ever disagree, in either direction.**

<!-- IMMATERIAL-MEMBERS-BEGIN -->

| seed | sub | tier | escaped | family | banked verdict / sub | what differs | cyc | done |
|---|---|---|---:|---|---|---|---:|---:|
| `fz2e/515056` | COSMETIC | soup | — | A2 qs-pop other offset | `KNOWN_ACCEPTED` / `cadence` | 2 rows: `qs`=2 | 137 | 1140 |
| `fz2e/516029` | COSMETIC | soup | — | A2 qs-pop other offset | `KNOWN_ACCEPTED` / `cadence` | 1 rows: `qs`=1 | 203 | 2591 |
| `fz2c/409065` | COSMETIC | raw | 225 | A3 cycle-time slip (non-qs) | `KNOWN_ACCEPTED` / `open_bus` | 16 rows: `addr`=2, `data`=12, `nxta`=2 | 757 | 3600 |
| `fz2e/513026` | TRANSIENT | soup | 2 | A3 cycle-time slip (non-qs) | `KNOWN_ACCEPTED` / `cadence` | 1 rows: `bs`=1 | 103 | 536 |
| `fz2e/521049` | COSMETIC | raw | 64 | A3 cycle-time slip (non-qs) | `KNOWN_ACCEPTED` / `open_bus` | 14 rows: `addr`=2, `data`=10, `nxta`=2 | 346 | 3617 |
| `fz2e/525017` | COSMETIC | raw | 39 | A3 cycle-time slip (non-qs) | `KNOWN_ACCEPTED` / `open_bus` | 12 rows: `addr`=2, `data`=8, `nxta`=2 | 208 | 2644 |
| `fz2e/529009` | COSMETIC | raw | — | A3 cycle-time slip (non-qs) | `KNOWN_ACCEPTED` / `lea-mod3` | 8 rows: `data`=8 | 264 | 1688 |
| `fz2c/408021` | TRANSIENT | raw | — | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 26 rows: `addr`=3, `bs`=12, `data`=6, `nxta`=3, `ps`=2, `qs`=2, `ube`=20 | 261 | 1459 |
| `fz2c/409025` | COSMETIC | raw | 51 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 451 | 3599 |
| `fz2c/410008` | COSMETIC | raw | — | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 339 | 2406 |
| `fz2e/517046` | COSMETIC | soup | — | E1 same-status data cycle, different address | `FUNCTIONAL` / `func:R@29` | 2 rows: `addr`=1, `nxta`=1 | 251 | 1489 |
| `fz2e/518033` | COSMETIC | raw | 20 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 805 | 3574 |
| `fz2e/519072` | COSMETIC | raw | 18 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 266 | 1386 |
| `fz2e/522029` | COSMETIC | raw | 280 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 32 rows: `addr`=8, `data`=16, `nxta`=8 | 550 | 3603 |
| `fz2e/524055` | COSMETIC | raw | 214 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 2 rows: `addr`=1, `nxta`=1 | 376 | 3172 |
| `fz2e/528010` | COSMETIC | raw | 128 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 540 | 3665 |
| `fz2e/530034` | COSMETIC | raw | — | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 246 | 968 |
| `fz2e/535036` | COSMETIC | raw | 56 | E1 same-status data cycle, different address | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 289 | 3576 |
| `fz2e/521024` | COSMETIC | raw | 60 | NEW/UNCLASSIFIED | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 444 | 3613 |
| `fz2e/522002` | COSMETIC | raw | 115 | NEW/UNCLASSIFIED | `KNOWN_ACCEPTED` / `open_bus` | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 331 | 3572 |
| `fz2e/532032` | COSMETIC | raw | 127 | NEW/UNCLASSIFIED | `KNOWN_ACCEPTED` / `open_bus` | 2 rows: `qs`=2 | 492 | 3451 |

<!-- IMMATERIAL-MEMBERS-END -->

**By family: E1 11 · A3 5 · NEW/UNCLASSIFIED 3 · A2 2.** By tier: **raw 17 ·
soup 4**. Escaped: **14 of 21**.

### 3.1 The shape of the class, read off the table

* **Fourteen of the nineteen COSMETIC seeds carry one signature** — `nxta=1,
  addr=1, data=2` (or `addr=1, nxta=1` where the data phase agreed), repeated 1
  to 8 times. **That is the ghost read drawn in full**: the core drives a
  different address on the T1 and on the preceding next-address phase, reads
  back whatever that address answers with, **the cycle starts and ends on the
  same clocks as the chip's, and the 15-word dump is bit-identical.**
* **Three are pure `qs` diffs** (`fz2e/515056`, `fz2e/516029`, `fz2e/532032`) —
  1–2 rows of queue-status pin and no bus effect at all.
* **Two are the TRANSIENT pair**, and both are named in the census §2.2:
  * `fz2e/513026` — **one row**, `bs PASV != CODE`, at row 543 of a 544-row
    window: the core announces the next fetch's status one clock before the
    chip, on the last compared clock. All 103 bus cycles start on identical
    clocks. **This is the user's "pin changing state slightly earlier", exactly.**
  * `fz2c/408021` — **a two-cycle REORDER.** Both legs run 261 cycles, all
    starting on identical clocks, and both perform the same `MEMW` to `0x777dc`
    and the same `CODE` fetch of `0x881a2` — **in the opposite order, in the
    same two slots.** ⚠ **It is not the "1–2 isolated rows" shape the class
    reads like**, and it is named here rather than absorbed silently: it is a
    real ordering difference between a write and a fetch that costs nothing
    measurable — same clocks, same cycles, same architectural result. **It is
    the member most worth re-reading if the criterion is ever tightened.**

### 3.2 Three things about this table that are worth saying out loud

1. **One member's banked verdict is `FUNCTIONAL`** — `fz2e/517046`,
   `func:R@29`. `fuzz_classify` calls a seed FUNCTIONAL when the **bus
   transaction stream** diverges; this disposition asks whether the
   **architectural result** did. A read at a different address whose value never
   reaches a register is the first and not the second, **and that gap is
   precisely the user's question**. The banked verdict is not retracted and is
   not rewritten.
2. **One member's `mech` is `FORGED_DONE` and the ledger's `arch` column reads
   `NODUMP`** — `fz2e/529009`. That is **not** an absent dump: prereg §17.0
   names this seed and records that it **dumped**, and `FORGED_DONE` is a
   declared **INSTRUMENT** class (D-2) for *a complete dump the pre-A-6 scorer
   could not see*. Clause (2) reads it with `arch_dump(..., sentinel_only=True)`
   — `fuzz_campaign.eval_case`'s own parameters — and **C-ARCH passes on it**,
   i.e. that reading reproduces the seed's own banked `arch_words` /
   `arch_sim_words`. It is named here so no reader concludes the class absorbed
   a NODUMP seed by accident.
3. **Fifteen of the 21 carry the banked sub `open_bus`, whose RULE WAS RETIRED**
   at `80075d049a` (user ruling 2026-08-11; the electrical story was false on
   this rig and the predicate was a tautology). **Banked labels are historical
   record and are not rewritten** — that commit says so explicitly. It costs
   this disposition nothing, and the reason is structural: **the predicate reads
   rows and dumps, never an accept-rule label.** No clause in §2 can see
   `banked_sub` at all.

---

## 4. WHAT IS **NOT** DISPOSITIONED — THE 11 `UNSCOREABLE` STAY OPEN

**The 11 UNSCOREABLE seeds receive NO disposition of any kind.** Neither leg
produced a dump, so the non-propagation proof clause (3) rests on **does not
exist** for them. Dispositioning them would be **acceptance by ignorance**, and
this document declines to do it.

They are, from the census §2.4: `fz2c/406006`, `fz2c/406063`, `fz2e/518039`,
`fz2e/520066`, `fz2e/521006`, `fz2e/524007`, `fz2e/529034`, `fz2e/529058`,
`fz2e/529067`, `fz2e/530001`, `fz2e/534003` — **all `raw` tier, all escaped**.

⚠ The census prints a **`would be`** column for them — the class the row
evidence would put each seed in *if* a dump existed and *if* it were identical —
and **seven of the eleven would be immaterial**. **That is a counterfactual and
no seed is promoted by it.** All eleven are counted in the **92**, in the
`UNSCOREABLE` row, and G1 is the bar that none of them can take this class.

**The single cheapest way to shrink the unadjudicated set is a terminator that
survives an escaped program** (census §9 item 4). That is an open work item, not
a disposition.

---

## 5. `TIMING_RECONVERGED` — 7 SEEDS, NAMED, UNDISPOSITIONED, AND A QUESTION FOR THE USER

> **RULED 2026-08-11 (user): "Timing reconvergence seeds are material."**
> The strict reading stands: all 7 stay MATERIAL, the working residue stays
> **92 = 113 − 21**, and the sub-class remains a named lens
> (`fz2_immaterial.py reconverged`), not a disposition. The question below is
> retained as the record of what was asked; it is CLOSED.

The census's surprise #3: **7 of the 33 TIMING seeds finish on exactly the same
clock.** Their schedule differs *mid-run* and **re-converges**.

**They do NOT take `IMMATERIAL`.** Clause (4) S-STARTS fails on every one of
them — a bus cycle starts on a clock where the other leg starts none — so under
the strict reading of the ruling they stay **MATERIAL**. They are given a
**named sub-class** so the question has an address instead of being a footnote,
and `python3 sw/fz2_immaterial.py reconverged` prints it on demand.

| seed | tier | escaped | family | diverging rows | cycle starts chip-only / core-only | done (both legs) |
|---|---|---:|---|---:|---|---:|
| `fz2c/406073` | raw | 142 | B2 HALT entry (one leg only) | 5 | 0 / 1 | 3599 |
| `fz2c/407064` | raw | 63 | B1 HALT-cycle address | 998 | 131 / 130 | 3583 |
| `fz2e/511014` | soup | — | D1 chip fetched, core did not | 744 | 97 / 95 | 3596 |
| `fz2e/512062` | soup | — | D2 core fetched, chip did not | 504 | 60 / 61 | 3569 |
| `fz2e/518006` | raw | 87 | E1 same-status data cycle, different address | 479 | 6 / 7 | 3599 |
| `fz2e/518044` | raw | 69 | B2 HALT entry (one leg only) | 5 | 0 / 1 | 3599 |
| `fz2e/520000` | raw | — | E1 same-status data cycle, different address | 836 | 13 / 12 | 3596 |

### 5.1 THE QUESTION, STATED FOR THE USER

The ruling says a pin moving early or late is not significant **"if it doesn't
change the overall timing."** On these seven, **the overall timing is
unchanged** — the program finishes on exactly the same clock, and on five of the
seven the two legs run within one cycle of each other in total. But **the bus is
occupied on clocks the other leg leaves free**, which is visible to any device
sharing it.

> **Is "overall timing" the FINISH CLOCK, or the whole bus schedule?**

* If **the finish clock**: these seven join `IMMATERIAL` and the working residue
  becomes **85 = 113 − 28**.
* If **the whole bus schedule** (the reading taken here): they stay MATERIAL and
  the residue is **92**.

**Until the user answers, they stay MATERIAL and the answer is not guessed.**
Note the two shapes inside the seven are not equally strong: `fz2c/406073` and
`fz2e/518044` differ by **one** cycle start over **5** rows, while `fz2c/407064`
differs by 131 over 998 — *"the schedule re-converged"* is a much weaker
statement about the second than about the first.

---

## 6. THE FALSIFIER — `sw/fz2_immaterial.py falsify`, EIGHT BARS

The failure mode for a class like this is **vacuity**: a predicate that says
"harmless" about everything is measuring nothing. Every bar prints its
denominator; any failure exits non-zero.

| bar | what it forbids or requires | measured on this tree |
|---|---|---|
| **G1 DUMP PROOF** | ZERO seeds without a two-sided dump may take the class | **0 / 23** — PASS |
| **G2 DUMP IDENTITY** | ZERO seeds whose 15 words differ may take it | **0 / 36** — PASS |
| **G3 SCHEDULE** | ZERO seeds with an unmatched cycle start or a moved done marker may take it | **0 / 86** — PASS |
| **G4 NOT UNIVERSAL** | the predicate must be FALSE on a positive number of entries | **FALSE on 92 / 113** — PASS. By first failing clause: `arch` 36 · `cycle_starts` 33 · `no_dump_proof` 23 |
| **G5 CONTROLS** | C-ROW and C-ARCH must PASS on EVERY entry, re-derived from the banked rows on this invocation | **113 / 113 · 113 / 113** — PASS. A failure here exits **2**: the census is unquotable and so is the disposition |
| **G6 THE CENSUS** | the partition derived here must equal the one **registered in the census document**, PARSED from it — all five class counts, the IMMATERIAL total, the 113, and the reconverged 7 | **0 / 8 cells disagree** — PASS |
| **G7 THE DOCUMENT** | the 21 seeds NAMED in §3 must be **exactly** the ones derived, set for set, **and** the `WORKING-RESIDUE` headline must match | **0 disagreements** — PASS |
| **G8 NO FORK** | the six clauses must reproduce `fz2_materiality`'s own class on ALL 113 entries | **0 / 113 disagree** — PASS |

**G1–G3 are the three ways the class could be a tautology. G4 is the check that
it is a question at all. G5–G7 are the three ways it could silently drift.
G8 is the check that this file did not fork the census** — the clauses are
written independently of `measure()`'s `if` ladder on purpose, so their agreement
is evidence rather than restatement.

### 6.1 THE FALSIFIER WAS DEMONSTRATED TO FAIL, NOT JUST TO PASS

A falsifier that has only ever passed has not been shown to be one. Both
directions were run on this tree, with the perturbation applied to a **copy** in
the scratchpad and **nothing under `sw/testdata/` touched** — the perturbed
ledger points at a perturbed capture by absolute path, with its `capture_sha256`
recomputed so the run gets past the sha gate and the **classification** is what
is being tested.

| # | perturbation | which bar caught it, verbatim | result |
|---|---|---|---|
| **P1** | **a member's classification silently changes.** `bs_early` flipped on the core leg at an already-diverging row of the COSMETIC member `fz2e/530034` (row 352). It adds no diff row and moves no cycle start — `extract_txns` keys on `t`, not `bs` — so C-ROW and C-ARCH still pass and the seed stays immaterial, but its **sub-class moves COSMETIC → TRANSIENT** | **G6** — `TRANSIENT: doc 2 != derived 3`, `COSMETIC: doc 19 != derived 18` | **FAIL**, exit **1** |
| **P2** | **a member's dump stops being bit-identical.** One word (`IX`) of the COSMETIC member `fz2e/528010`'s core-leg terminator dump moved by one bit, with the capture's own `arch_sim_words` and the ledger's `diverging_rows` recomputed so **both controls still pass** and the CLASS logic is what is under test. The seed becomes FUNCTIONAL and leaves the disposition | **G6** — `FUNCTIONAL: doc 48 != derived 49`, `IMMATERIAL: doc 21 != derived 20` — **and G7** — `named but NOT derived: fz2e/528010`, `WORKING-RESIDUE headline (92, 113, 21) != derived (93, 113, 20)` | **FAIL**, exit **1** |
| **P3** | **a seed that does not meet the predicate carries the disposition.** This is P2's second half and needs no separate run: after P2 the document still names `fz2e/528010` and the derivation no longer does | **G7** — `named but NOT derived` | **FAIL**, exit **1** |
| **P4** | **the instrument stops reproducing the record.** P2's row perturbation with the controls **NOT** repaired | **G5** — `C-ROW 112 / 113 · C-ARCH 112 / 113`, `control failed: fz2e/528010 (C-ROW+C-ARCH)`; then G6 and G7 | **FAIL**, exit **2** — *unquotable*, not merely failing |
| **P5** | **the bytes are not the bytes the ledger names.** P4 with the entry's `capture_sha256` zeroed | the census's own sha gate — `CAPTURE SHA MISMATCH fz2e/528010`, before a single seed is classified | **FAIL**, exit **1** |

Two details worth carrying:

* **The exit code is MONOTONE.** P4 shows why: G5 sets 2 and G6/G7 fail
  afterwards, and a later bar must never downgrade *"the census is unquotable"*
  to *"a bar failed"*. `bar()` uses `max(rc, 1)` for exactly this.
* **G8 is asked only where the controls pass, and prints how many it skipped.**
  Clause (1) makes a control-failed seed a non-member while `measure()` still
  reports the class it computed; that disagreement is **G5's finding, not a
  fork**, and folding it into G8 would report one defect twice under two names.
  P4 shows the skip printed: `0 / 112 … (1 not askable, controls failed)`.

The perturbation harness is deliberately **NOT COMMITTED**: a tool that ships
the ability to rewrite a banked capture is a hazard, and the perturbation is
about thirty lines of `gzip` + `json` that any reviewer can rewrite from this
table. **Nothing under `sw/testdata/` was touched by any of the five** — each
perturbed capture is written to the scratchpad and the perturbed ledger points
at it by absolute path.

---

## 7. THE QUOTING RULE

**The working residue may not be quoted without its denominator, and the full
113 must be co-quoted.** The form:

> **92 material-or-unproven of 113 diverging of 3,837**

**Never `92/3,837` alone**, and never *"the residue shrank to 92"* — **it did
not shrink**. 113 seeds still diverge between the socket chip and the fabric
core on FLASH #17; 21 of them have been **measured to cost nothing observable**
and are dispositioned on that measurement. The seeds are still in the ledger,
still in the denominator, still in every rate.

**And the corpus figure is unchanged**: `3,692 / 3,837` seeds match outright,
`bars` is 11/11, `check_fuzz_bank` is `PASS / 621`. Nothing in this document is
an input to any of them.

---

## 8. WHAT DID NOT MOVE — THE LIST, SO IT IS CHECKABLE

* `sw/fz2_w1.py bars` — **11 / 11 MET**, artifact byte-identical.
* `sw/fz2_w1.py lint` — **PASS, 0 hits, 48 stratum rows.**
* `sw/fz2_materiality.py` — printed output **byte-identical** across the
  `measure_all()` extraction; **C-ROW 113/113, C-ARCH 113/113**, classes
  **48 / 33 / 2 / 19 / 11**.
* `python3 sw/test_artifact.py` — **45 / 45.**
* **No file under `sw/testdata/` changed.** No ledger was rewritten, no seed was
  excluded, no bank was re-derived. This disposition writes **nothing** into any
  banked artifact — it is recomputed from the record on every invocation, which
  is the only reason it needs no archive and no invalidation-ledger entry.
* **`hdl/` untouched.** No board, no flash, no Quartus, no re-capture.

### 8.1 Why this is NOT an `INV-n` / `SUP-n` / `EXC-n` / `ERR-n` entry

The four-register ledger (`docs/notes/invalidation_ledger.md`) is for
**measurements that leave a population**. `IMMATERIAL` takes **no seed out of
any numerator, denominator, bank or gate set** — the seeds stay exactly where
they were and are scored exactly as they were. There is no rig defect (INV),
no superseding instrument (SUP), no seed leaving a rate (EXC), and no derived
column that was written wrong (ERR). **A disposition that changes what a number
*means* to a reader, while changing no number, belongs in the campaign record
and not in the invalidation ledger** — which is exactly where A-14's
`ROW_MATCHED` sits.

⚠ **One difference from A-14, stated because it matters**: A-14 *did* move a
bar — it re-registered E-1c's meaning and took `undispositioned` from 25 to 0,
under an explicit user ruling and its own prereg amendment (§36–§37). **This
disposition moves nothing at all**, so it needs no prereg amendment and takes
none. If it is ever wired into a scored quantity, **that** is the change that
needs pre-registration, and it has not been made.

---

## 9. WHAT THIS LEAVES OPEN

1. **The 11 UNSCOREABLE seeds** — no proof either way, deliberately not
   dispositioned (§4). The instrument fix is a terminator that survives an
   escaped program.
2. **The 7 `TIMING_RECONVERGED` seeds** — a question for the user, stated at
   §5.1, answered by nobody yet.
3. **`fz2c/408021`**, the two-cycle reorder (§3.1) — inside the class by the
   stated rule, and the member most worth re-reading if the criterion tightens.
4. **The honesty clause's blind spot** (§2.1) — the dump-identity proof covers
   15 registers at the end of the run and nothing else. No instrument in this
   tree measures memory the program never re-read.
5. **The 92 that remain** are the work: **48 FUNCTIONAL + 33 TIMING + 11
   UNSCOREABLE**, and the census's §5 reading still points where a mechanism
   hunt would start — **the 10 `soup`-tier non-escaped FUNCTIONAL seeds, six of
   them family C2 (INTA-vectored delivery).**
