# THE `IMMATERIAL` DISPOSITION — A FORMAL CLASS FOR THE DIVERGENCES THAT COST NOTHING

    tool        sw/fz2_immaterial.py            (reviewer-re-runnable, offline)
    census      sw/fz2_materiality.py           (imported as a library, not forked)
    LIVE ERA    FLASH #18 -- see PART I
    input       sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json
                (= `sw/fz2_ledger.py:CURRENT`)
                + the 110 banked FABRIC captures it names, sha256-verified
    branch      fuzz-v2-on-relanding @ 770c0d1b85
    era         sof b2a1fe5f83167fbf…  (FLASH #18)
    date        2026-08-11
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.

    HISTORY     FLASH #17 (21 members, residue 92 = 113 - 21) is retained
                VERBATIM as PART II.  Its input was
                fz2_failure_ledger_f17_2026-08-11.json, branch @ ae3da7c59a,
                era sof 26c19f613e2caae8….

    reproduce   python3 sw/fz2_immaterial.py falsify       # the eight bars
                python3 sw/fz2_immaterial.py census        # members + evidence
                python3 sw/fz2_immaterial.py reconverged   # the sub-class NOT taken

⚠ **THE MEMBERSHIP IS PARSED FROM THIS FILE, AND ONLY FROM BETWEEN THE ANCHORS
IN §I.2.**  `falsify`'s **G7** reads the `IMMATERIAL-MEMBERS-BEGIN` /
`-END` HTML-comment pair — the member rows **and**, since 2026-08-11, the
`WORKING-RESIDUE` headline — and nothing else.  **PART II's table is history
and is not a claim**; its anchors are renamed `IMMATERIAL-MEMBERS-F17-*` so
exactly one live pair exists.

⚠ **THE ANCHOR LITERALS ARE DELIBERATELY NOT SPELT OUT IN PROSE ANYWHERE IN
THIS FILE.**  `dispo_doc()` splits on the FIRST occurrence of each, so a
mention of the exact comment in running text would truncate the parsed region
to nothing and G7 would score an empty member set.  Read them off §I.2.

---
---

# PART I — FLASH #18.  **THE LIVE DISPOSITION.**

    re-derived 2026-08-11 under `docs/notes/fz2_f18_housekeeping_prereg_2026-08-11.md`,
    committed at `a05af666aa` BEFORE this run.
    results     docs/notes/fz2_f18_housekeeping_results_2026-08-11.md

## I.0 WHAT CHANGED, AND WHAT DID NOT

**The class did not change.  The population did.**  Not one clause of
`evidence()` was touched, `CYCLE_DEFINING` is still `("bs", "t")`, no class
boundary moved and **no seed list exists in the tool** — the 24 below are
COMPUTED on every invocation and G7 is the bar that this table is exactly what
the code derives.

FLASH #18 landed `KM` and `phantom-T1`.  Against the F17 ledger:

    LEFT the ledger  3   (KM's seats; all three FUNCTIONAL, so none was a member)
    ENTERED          0
    total          113 -> 110

    IMMATERIAL      21 -> 24     ZERO leavers, THREE entrants
    WORKING RESIDUE 92 -> 86     45 FUNCTIONAL + 30 TIMING + 11 UNSCOREABLE

**The three entrants are phantom-T1's three seats**, and the quoting form for
this era is:

> **86 material-or-unproven of 110 diverging of 3,839**
> — 45 FUNCTIONAL + 30 TIMING + 11 UNSCOREABLE, with 24 dispositioned
> `IMMATERIAL`.

⚠ **NO RATE, BAR OR VERDICT MOVES, ON THIS ERA EITHER.**  `sw/fz2_w1.py bars`
is **11/11 MET** and byte-identical across this work; this disposition is still
deliberately **not wired into any scorer**.

## I.1 THE THREE ENTRANTS — CLAUSE BY CLAUSE, BECAUSE ADMISSION IS NOT ASSUMED

The housekeeping pre-registration §1.3 predicted all six clauses would pass on
each of the three, **with the explicit rule that a failing clause is a FINDING
and the seed is NOT admitted**.  Measured, from `fz2_materiality.measure()`'s
own leaves:

| clause | `fz2c/404071` | `fz2e/514044` | `fz2e/516001` |
|---|---|---|---|
| **(1) C-CONTROL** | PASS — C-ROW ✓ C-ARCH ✓ | PASS — C-ROW ✓ C-ARCH ✓ | PASS — C-ROW ✓ C-ARCH ✓ |
| **(2) D-PROOF** | PASS — both legs dumped | PASS — both legs dumped | PASS — both legs dumped |
| **(3) D-IDENT** | PASS — `arch_diff_words` **[]**, 15/15 | PASS — **[]** | PASS — **[]** |
| **(4) S-STARTS** | PASS — **0 / 0**, cycles **174 / 174** | PASS — **0 / 0**, **233 / 233** | PASS — **0 / 0**, **204 / 204** |
| **(5) S-DONE** | PASS — done **1196 / 1196**, δ **0** | PASS — **1579 / 1579**, δ **0** | PASS — **2603 / 2603**, δ **0** |
| **(6) DIVERGENT** | PASS — `bad_rows` **1**, flicker 0 | PASS — **1**, 0 | PASS — **1**, 0 |
| **verdict** | **IMMATERIAL / TRANSIENT** | **IMMATERIAL / TRANSIENT** | **IMMATERIAL / TRANSIENT** |

**18 of 18 clause cells PASS.  `why` is `None` on all three.**

**Clause (4) is the one that carried the weight, and it is worth saying why it
is not circular.**  The pre-registration argued it from the parser rather than
from the result: the residual diff is one row on `bs`, and
`fuzz_classify.extract_txns` keys a bus cycle on **`t`, not `bs`** — the same
fact PART II §6.1's **P1** perturbation rests on. A one-row `bs` difference
therefore *cannot* create a cycle start the other leg lacks, and the measured
`0 / 0` with identical cycle counts is the confirmation, not the argument.

⚠ **This is a DISPOSITION, not a closure.**  `bad_rows == 0` was registered by
the ack-wake landing as a FINDING and did not occur; the ucore has ONE status
value per CPU clock where silicon has TWO, and the one remaining cell is the
`system_large` status-pin observation model — booked, not taken.  **The seeds
stay in the ledger, in the denominator, and in every rate.**

## I.2 THE 24, NAMED WITH THEIR EVIDENCE

Grouped by the ledger's A-15 family, carried forward unmodified.  `cyc` is the
bus cycles each leg ran inside the compare window — **identical in both legs on
all 24, by clause (4)**; `done` is the done-marker clock, **identical in both
legs on all 24, by clause (5)**.

⚠ **This table is the reader's copy, not the class.**  The class is COMPUTED by
`evidence()` on every invocation, and **G7 fails loudly if this table and the
derivation ever disagree, in either direction.**

⚠ **`banked verdict / sub` IS AN F18-ERA READING AND MAY NOT BE DIFFED AGAINST
PART II's COLUMN.**  `80075d049a` retired the `open_bus` accept rule and is not
an ancestor of the FLASH #17 flash commit, so fifteen members' labels moved
`KNOWN_ACCEPTED / open_bus` → `FUNCTIONAL / func:…` **with byte-identical rows
and dumps**.  **No clause in §II.2 can see `banked_sub` at all**, so the class
is unaffected — which is the structural reason this costs the disposition
nothing.

<!-- IMMATERIAL-MEMBERS-BEGIN -->

    WORKING-RESIDUE = 86 = 110 − 24

| seed | sub | tier | escaped | family | what differs | cyc | done |
|---|---|---|---:|---|---|---:|---:|
| `fz2e/515056` | COSMETIC | soup | — | A2 qs-pop other offset | 2 rows: `qs`=2 | 137 | 1140 |
| `fz2e/516029` | COSMETIC | soup | — | A2 qs-pop other offset | 1 rows: `qs`=1 | 203 | 2591 |
| `fz2c/409065` | COSMETIC | raw | 225 | A3 cycle-time slip (non-qs) | 16 rows: `addr`=2, `data`=12, `nxta`=2 | 757 | 3600 |
| `fz2e/513026` | TRANSIENT | soup | 2 | A3 cycle-time slip (non-qs) | 1 rows: `bs`=1 | 103 | 536 |
| `fz2e/521049` | COSMETIC | raw | 64 | A3 cycle-time slip (non-qs) | 14 rows: `addr`=2, `data`=10, `nxta`=2 | 346 | 3617 |
| `fz2e/525017` | COSMETIC | raw | 39 | A3 cycle-time slip (non-qs) | 12 rows: `addr`=2, `data`=8, `nxta`=2 | 208 | 2644 |
| `fz2e/529009` | COSMETIC | raw | — | A3 cycle-time slip (non-qs) | 8 rows: `data`=8 | 264 | 1688 |
| `fz2c/404071` | **TRANSIENT** | soup | — | C2 INTA-vectored delivery | **1 rows: `bs`=1** — phantom-T1 seat | 174 | 1196 |
| `fz2e/514044` | **TRANSIENT** | soup | — | C2 INTA-vectored delivery | **1 rows: `bs`=1** — phantom-T1 seat | 233 | 1579 |
| `fz2e/516001` | **TRANSIENT** | soup | — | C2 INTA-vectored delivery | **1 rows: `bs`=1** — phantom-T1 seat | 204 | 2603 |
| `fz2c/408021` | TRANSIENT | raw | — | E1 same-status data cycle, different address | 26 rows: `addr`=3, `bs`=12, `data`=6, `nxta`=3, `ps`=2, `qs`=2, `ube`=20 | 261 | 1459 |
| `fz2c/409025` | COSMETIC | raw | 51 | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 451 | 3599 |
| `fz2c/410008` | COSMETIC | raw | — | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 339 | 2406 |
| `fz2e/517046` | COSMETIC | soup | — | E1 same-status data cycle, different address | 2 rows: `addr`=1, `nxta`=1 | 251 | 1489 |
| `fz2e/518033` | COSMETIC | raw | 20 | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 805 | 3574 |
| `fz2e/519072` | COSMETIC | raw | 18 | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 266 | 1386 |
| `fz2e/522029` | COSMETIC | raw | 280 | E1 same-status data cycle, different address | 32 rows: `addr`=8, `data`=16, `nxta`=8 | 550 | 3603 |
| `fz2e/524055` | COSMETIC | raw | 214 | E1 same-status data cycle, different address | 2 rows: `addr`=1, `nxta`=1 | 376 | 3172 |
| `fz2e/528010` | COSMETIC | raw | 128 | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 540 | 3665 |
| `fz2e/530034` | COSMETIC | raw | — | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 246 | 968 |
| `fz2e/535036` | COSMETIC | raw | 56 | E1 same-status data cycle, different address | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 289 | 3576 |
| `fz2e/521024` | COSMETIC | raw | 60 | NEW/UNCLASSIFIED | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 444 | 3613 |
| `fz2e/522002` | COSMETIC | raw | 115 | NEW/UNCLASSIFIED | 4 rows: `addr`=1, `data`=2, `nxta`=1 | 331 | 3572 |
| `fz2e/532032` | COSMETIC | raw | 127 | NEW/UNCLASSIFIED | 2 rows: `qs`=2 | 492 | 3451 |

<!-- IMMATERIAL-MEMBERS-END -->

**By family: E1 11 · A3 5 · C2 3 · NEW/UNCLASSIFIED 3 · A2 2.**  By tier:
**raw 17 · soup 7**.  Escaped: **14 of 24**.  By sub-class: **COSMETIC 19 ·
TRANSIENT 5**.

**The twenty-one PART II members are all still here, seed for seed, with their
row counts, cycle counts and done clocks unchanged.**  The only movement in
this table between the two eras is the three C2 rows.

## I.3 WHAT IS STILL **NOT** DISPOSITIONED

* **The 11 UNSCOREABLE seeds stay open** — unmoved from PART II §4, seed for
  seed, all `raw`, all escaped.  Their counterfactual on F18 reads `would be`
  TIMING 4 · TRANSIENT 1 · COSMETIC 6.  **G1 is the bar that none of them can
  take this class.**
* **`TIMING_RECONVERGED` is now 8 seeds, and the user's ruling carries.**
  RULED 2026-08-11: *"Timing reconvergence seeds are material."*  The F17 seven
  are all still members and **`fz2e/530020` joined** — a still-TIMING D1 seed
  whose `done_delta` became 0, not a seat and not predicted by mechanism.
  **All 8 stay MATERIAL and inside the 86.**  The ruling is a rule about a
  PREDICATE, not about a seed list, so it applies to the new member without
  being re-asked.  Census PART I §I.4 has the table and the falsifier.

## I.4 THE FALSIFIER ON THIS ERA — `falsify` EXITS 0, G1–G8 PASS

| bar | measured on FLASH #18 |
|---|---|
| **G1 DUMP PROOF** | **0 / 23** — PASS |
| **G2 DUMP IDENTITY** | **0 / 33** — PASS.  ⚠ the pool is the **two-sided** dumps that differ (33), not all 45 FUNCTIONAL: the other 12 are one-sided and sit in G1's pool |
| **G3 SCHEDULE** | **0 / 80** — PASS |
| **G4 NOT UNIVERSAL** | **FALSE on 86 / 110** — PASS.  By first failing clause: `arch` 33 · `cycle_starts` 30 · `no_dump_proof` 23 |
| **G5 CONTROLS** | **110 / 110 · 110 / 110** — PASS |
| **G6 THE CENSUS** | **0 / 8 cells disagree** — PASS, against the census's **anchored** PART I block |
| **G7 THE DOCUMENT** | **0 disagreements** — PASS, against §I.2's anchored table and its `WORKING-RESIDUE` headline |
| **G8 NO FORK** | **0 / 110 disagree** — PASS |

**One tool change went with this re-derivation, and it is a SCOPE change, not a
bar change** — pre-registered at `a05af666aa` §1.5.  `census_doc()` now parses
only between `<!-- CENSUS-PARTITION-BEGIN/END -->`, and `dispo_doc()` reads the
`WORKING-RESIDUE` headline from inside the member anchors instead of from the
whole file.  It was necessary: unanchored, `_CENSUS_ROW` took the **last**
match in the file while `_CENSUS_IMM`/`_CENSUS_RECONV` took the **first**, so
**no placement of a history section satisfied both** and the census could not
carry PART II without lying to its own falsifier.  Both edits can only make the
gate **stricter** — a missing anchor is now a FAIL that did not exist before,
and a table outside the anchors has stopped counting as a claim.  **P6 below
demonstrates the falsifier still fails.**

### I.4.1 P6–P9 — THE FALSIFIER DEMONSTRATED TO FAIL AFTER THE PARSER CHANGE

A falsifier that has only ever passed has not been shown to be one, and a
falsifier whose parser was just re-scoped has to be shown again.  Registered at
prereg §1.6 **H-6**, run on a **shadow tree**: `sw/*.py` and `docs/notes/*` are
real copies in the scratchpad and every other path — `sw/testdata/` included —
is a **symlink to the repo, read-only**.  **Nothing under `sw/testdata/` was
touched by any of these.**

| # | perturbation | caught by, verbatim | result |
|---|---|---|---|
| **P0** | *control* — the unperturbed shadow tree | `IMMATERIAL FALSIFIERS: PASS` | **PASS**, exit **0** — the copy reproduces the repo |
| **P6** | the census document's live `TRANSIENT` cell moved **5 → 4** **inside** the anchors | **G6** — `1 / 8 registered cells disagree`, `** TRANSIENT: doc 4 != derived 5` | **FAIL**, exit **1** |
| **P7** | the partition anchors **deleted** — the failure mode the scope change creates, which did not exist before it | **G6** — `partition anchors (…-BEGIN … …-END) absent  [FAIL]` | **FAIL**, exit **1** |
| **P8** | one member seed (`fz2e/516001`) removed from §I.2's anchored table | **G7** — `1 / 25 disagreements`, `** derived but NOT named: fz2e/516001` | **FAIL**, exit **1** |
| **P9** | *control, and the one that proves the scope change is real* — **PART II's** superseded `TRANSIENT` cell set to a nonsense **99** | `IMMATERIAL FALSIFIERS: PASS` | **PASS**, exit **0** |

**P9 is the load-bearing control.**  Before the scope change, `_CENSUS_ROW`
took the **last** matching row in the whole file, so PART II's table would have
been read as the live registration and P9 would have failed.  It passes, which
is the measurement that **history outside the anchors has stopped being a
claim** — and P7 is the measurement that the anchors cannot simply be dropped
to get the same effect.

PART II §6.1's five perturbations (P1–P5) are unchanged in kind and are **not**
re-run: they perturb **captures and ledgers**, which the scope change does not
touch, and re-running them would need the banked-capture rewrite harness that
is deliberately not committed.

---
---

# PART II — FLASH #17.  ⚠ **SUPERSEDED 2026-08-11 BY PART I.  HISTORY, NOT A CLAIM.**

**Everything below this line is the FLASH #17-era disposition, retained
byte-for-byte as it was registered**, except that its member-table anchors are
renamed `IMMATERIAL-MEMBERS-F17-BEGIN/END` so that exactly one live pair exists
in the file.  Its population is 113 seeds and 21 members against era sof
`26c19f613e2caae8…`; the live population is 110 and 24 against
`b2a1fe5f8316…`.  **None of its numbers may be quoted against this tree.**  It
is kept because a disposition is only readable against its own ledger, and
because PART I's delta statements are meaningless without it.

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

<!-- IMMATERIAL-MEMBERS-F17-BEGIN -->

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

<!-- IMMATERIAL-MEMBERS-F17-END -->

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
