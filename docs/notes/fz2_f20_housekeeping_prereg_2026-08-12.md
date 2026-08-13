# PRE-REGISTRATION — THE F20 ERA RE-PIN OF THE MATERIALITY CENSUS AND THE `IMMATERIAL` DISPOSITION

    branch      master @ 298d522872  (isolated worktree
                `worktree-agent-a1a16db2b619a4a58`, same commit)
    date        2026-08-12
    board       NOT TOUCHED.  No capture, no flash, no socket command, no
                Quartus compile, no RTL edit.  Offline throughout.

    item        re-derive the materiality census + IMMATERIAL disposition
                against the **FLASH #20** ledger, move `fz2_ledger.CURRENT`
                to it, and return `fz2_immaterial falsify` to PASS

**THIS FILE IS COMMITTED BEFORE `fz2_materiality` OR `fz2_immaterial` IS RUN
AGAINST THE F20 LEDGER IN THIS SITTING.**  Every number in §1 is DERIVED — from
the F19 and F20 failure ledgers (both committed INPUTS), from the F19-era census
and disposition documents, from `fz2_flash20_results_2026-08-12.md`, and from
the two tools' own source.  Not one of them is read off a run of either tool
here.  Where a derivation is under-determined the alternatives are registered
below rather than chosen after the run.

This is the exact analogue of `fz2_f19_housekeeping_prereg_2026-08-12.md`, one
era on, and it follows that file's shape deliberately.

---

## §0 WHY, AND WHY IT IS *ONLY* AN ERA RE-PIN

FLASH #20 re-captured the corpus (`fz2_flash20_results_2026-08-12.md`) and its
ledger `sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json` records **106
failures of a 3,839 denominator**.  `sw/fz2_ledger.py:CURRENT` still names the
**F19** ledger, so every capture the live pointer names has been overwritten by
the F20 re-capture and **`fz2_immaterial falsify` dies at the sha gate before
classifying a seed** — the guard doing exactly its job, exactly as it did at the
F18 → F19 re-pin.

The debt is two documents old in its statement and one era old in its content,
and it was booked twice rather than paid:

* **`fz2_flash20_prereg_2026-08-12.md` §4.4 (`C-15e`)** registered G6 and G7 to
  **FAIL on document staleness alone** and wrote *"the F20 re-pin is the NEXT
  housekeeping, not this sitting"*.  §3.5 of the results scored them exactly so:
  **G6 5 of 8 cells, G7 3 of 25, every disagreement doc (114/24/90) vs
  derivation (106/22/84); G1–G5 and G8 PASS.**
* **`timing50_phase2_results_2026-08-12.md` §6.3** then found the tool could not
  run at all — `ledger failures: 114  capture sha OK: 0  MISMATCH: 107
  missing: 7` — and recorded `falsify` as **OWED, not claimed**.

This sitting is that payment.  **It is housekeeping and it moves no verdict.**

## §0.1 WHAT THIS DOES *NOT* TOUCH — HARD, AS AT F18 AND F19

No clause of `evidence()`, no class boundary, `CYCLE_DEFINING` stays
`("bs", "t")`, `VALUE_ONLY` stays as it is, no seed list enters either tool, no
bar's meaning moves, and **no parser change is registered**.  What changes is
the two **documents** and the one-line `CURRENT` pointer.

⚠ **AND NOTHING IN THE RTL OR THE TESTBENCH.**  A parallel sitting is working
`hdl/rtl/ucore/v30u_eu.sv` and its testbench in another worktree.  This
sitting's territory is the census/disposition tools and their documents ONLY.
An edit under `hdl/` here would be a HARD STOP (§4).

## §0.2 ONE ORDERING DEVIATION, DECLARED IN ADVANCE RATHER THAN EXPLAINED AFTER

**§3's capture-file reconciliation was MEASURED BEFORE THIS DOCUMENT WAS
WRITTEN, and it is labelled a MEASUREMENT and not a prediction.**  The reason is
structural: it answers *"can the census run against this tree at all, and is the
corpus on disk the F20 corpus?"*, and a pre-registration that predicted the
answer to a question whose answer decides whether the sitting is possible would
be theatre.  It reads only committed artifacts (the two ledgers, the campaign
`results.jsonl`) plus a file inventory; **it runs neither `fz2_materiality` nor
`fz2_immaterial`, and it constrains no cell of §1.**  Everything in §1 and §2 is
a genuine prediction made before either tool was run in this sitting.

---

## §1 THE PREDICTED PARTITION — PRIMARY POINT PREDICTION

The F20 population is the F19 population **minus eight leavers and plus zero
entrants**, with the discard set collapsing **3 → 1** (two of FLASH #19's three
`ps3_8080` discards reverted, so the denominator goes **3,837 → 3,839**).
Derived directly from the two ledgers:

    LEFT     8   fz2e/508068  fz2e/509050  fz2e/514001  fz2e/521024
                 fz2e/522002  fz2e/526075  fz2e/530020  fz2e/534003
    ENTERED  0
    DISCARDS 3 -> 1   (fz2e/524027 and fz2e/535070 reverted; fz2e/509069 stays)
    total  114 -> 106     denominator  3,837 -> 3,839

### §1.1 THE EIGHT LEAVERS, EACH WITH ITS F19 CLASS, DERIVED PER SEED

The F19 class of each leaver is read from the **F19-era census and disposition
documents** (the live PART I blocks) and cross-checked against the F19 ledger's
own fields:

| seed | F19 ledger `arch` / dumps | F19 CLASS | where that class is registered |
|---|---|---|---|
| `fz2e/508068` | dumps differ, 14 words (census row-scan finds the core dump at 1525) | **FUNCTIONAL** | census PART I §I.2, row 1 |
| `fz2e/509050` | dumps differ, 14 words | **FUNCTIONAL** | census PART I §I.2, row 2 |
| `fz2e/514001` | dumps differ, 14 words | **FUNCTIONAL** | census PART I §I.2, row 3 |
| `fz2e/526075` | `NODUMP`, `done_chip` True / `done_core` False — chip-only | **FUNCTIONAL** | census PART I §I.2, row 4 |
| `fz2e/521024` | `arch OK`, 4 rows `addr=1, data=2, nxta=1` | **COSMETIC** | disposition PART I §I.2, member |
| `fz2e/522002` | `arch OK`, 4 rows `addr=1, data=2, nxta=1` | **COSMETIC** | disposition PART I §I.2, member |
| `fz2e/530020` | `arch OK`, both dumped, 671 rows, family D1 | **TIMING** | NOT a disposition member; D1's TIMING cell, census PART I §I.3 |
| `fz2e/534003` | `NODUMP`, `done_chip` **False** AND `done_core` **False** | **UNSCOREABLE** | NOT a member; NEW/UNCLASSIFIED's `UNSC` cell, census PART I §I.3 |

**`fz2e/530020` WAS NOT AN `IMMATERIAL` MEMBER, AND THAT IS ANSWERED HERE
RATHER THAN ASSUMED.**  It does not appear in the disposition's anchored
24-member table at any point in the document's history, and the F19 census
records it LEAVING `TIMING_RECONVERGED` (8 → 7) — a sub-class of TIMING, which
is MATERIAL by the 2026-08-11 user ruling.  Its class is **TIMING**.

⚠ **AN ERRATUM AGAINST A SUPERSEDED RESULTS DOCUMENT, STATED BECAUSE IT WOULD
OTHERWISE PROPAGATE.**  `fz2_f19_housekeeping_results_2026-08-12.md` §2.4 calls
its three offline closures — `fz2e/521024`, `fz2e/522002`, `fz2e/534003` —
*"all three … 4-row COSMETIC IMMATERIAL members (§4)"*.  **`fz2e/534003` is not
a member and never was**: its F19 ledger row reads `done_chip` **False** and
`done_core` **False**, so **neither** leg dumped and clause (2) D-PROOF holds it
out; it is one of the eleven UNSCOREABLE.  The statement is true of the other
two.  **Nothing is edited in that document** (it is superseded history); the
erratum is recorded here and carried into the results.

### §1.2 THE ONE SHARED SEED THAT CHANGES CLASS — `fz2e/527051`

Of the 106 seeds in **both** ledgers, **28 moved a scored field** (§3.2).  Only
one of them can change CENSUS CLASS, and it is derivable from the ledger alone:

| seed | F19 | F20 | consequence |
|---|---|---|---|
| **`fz2e/527051`** | `arch` `AW,BP,BW,CW,IX,IY,PSW`, `arch_match` **False** | `arch` **`OK`**, `arch_match` **True** | the two 15-word dumps became **identical**, so `measure()`'s first branch no longer fires: it leaves **FUNCTIONAL** |

The other six seeds whose `arch` / `done_*` fields moved stay FUNCTIONAL on both
sides of the move — `fz2c/406063` (`arch` unchanged), `fz2c/409077`
(`NODUMP` → `PSW`), `fz2e/518039` (`done_core` True → False, dumps still
differ), `fz2e/518053` (`NODUMP` → `CW`), `fz2e/526054` (`AW,PSW,SS` → `SS`),
`fz2e/530046` (`NODUMP` → `AW,IX,SP`) — because a differing word on either side
gives FUNCTIONAL by the same branch, and a one-sided dump gives FUNCTIONAL by
the third.

**Where does `527051` land?**  Its dumps are identical and it diverges on 913
rows, so it is TIMING, TRANSIENT or COSMETIC.  **REGISTERED CALL: TIMING**, and
it is not a free choice — `fz2_flash20_results_2026-08-12.md` §3.5 measured
`C-15a` as **22 members with `fz2e/521024` and `fz2e/522002` the only leavers
and ZERO entrants**, so `527051` cannot have taken TRANSIENT or COSMETIC without
making the class 23.

### §1.3 THE PARTITION

| class | F19 (live, registered) | movement, derived | **F20 PREDICTED** |
|---|---:|---|---:|
| FUNCTIONAL | 49 | − 4 leavers (§1.1) − `fz2e/527051` (§1.2) | **44** |
| TIMING | 30 | − `fz2e/530020` + `fz2e/527051` | **30** |
| TRANSIENT | 5 | none | **5** |
| COSMETIC | 19 | − `fz2e/521024` − `fz2e/522002` | **17** |
| UNSCOREABLE | 11 | − `fz2e/534003` | **10** |
| **total** | **114** | LEFT 8 / ENTERED 0 | **106** |
| **IMMATERIAL** (transient + cosmetic) | **24** | − the two COSMETIC leavers | **22** |
| **working residue** | **90** | | **84** |
| `TIMING_RECONVERGED` | **7** | none | **7** |

### §1.4 THE TWO INDEPENDENT CROSS-CHECKS THAT MAKE THIS A POINT PREDICTION

**(a) THE `G6 5 / 8` CONSTRAINT.**  `fz2_flash20_results` §3.5 measured G6 at
**5 of 8 cells disagreeing** with the F19-pinned document.  G6's eight cells are
the five class counts, `IMMATERIAL`, the total and `TIMING_RECONVERGED`.  Four
disagreements are certain from that document's own figures — total 114 ≠ 106,
IMMATERIAL 24 ≠ 22, COSMETIC 19 ≠ 17, UNSCOREABLE 11 ≠ 10 — and TRANSIENT (5)
and `TIMING_RECONVERGED` (7) are measured there to AGREE.  **So exactly one of
FUNCTIONAL and TIMING disagrees**, and their sum is fixed at
`106 − 22 − 10 = 74` against F19's `49 + 30 = 79`.  One cell takes all five.
The alternatives, registered:

| branch | what it would mean |
|---|---|
| **A — FUNCTIONAL 44, TIMING 30** *(REGISTERED CALL)* | four FUNCTIONAL leavers plus `fz2e/527051` leaving FUNCTIONAL for TIMING, against `fz2e/530020` leaving TIMING |
| **B — FUNCTIONAL 49, TIMING 25** | FUNCTIONAL would have to regain four seeds it lost and TIMING lose five — contradicted by the leavers' own ledger rows |

A **split** across both cells is a third outcome; it would make G6 read 6 of 8
and would therefore contradict FLASH #20's own measurement.  **That is reported
as a finding against that document, not absorbed.**

**(b) THE FAMILY TABLE, WHICH THE F20 LEDGER FIXES INDEPENDENTLY.**  The
ledger's own `family_counts` moved on exactly three rows: **D1 10 → 9**,
**NEW/UNCLASSIFIED 11 → 4**, **D3 5 → 5** with a scored-field mover inside it.
Applying §1.1's per-seed classes to the F19 class × family table
(census PART I §I.3) gives:

| family | FUNC | TIME | TRAN | COSM | UNSC | tot | vs F19 |
|---|---:|---:|---:|---:|---:|---:|---|
| A1 qs-pop one clock late | 0 | 5 | 0 | 0 | 0 | 5 | unchanged |
| A2 qs-pop other offset | 0 | 1 | 0 | 2 | 1 | 4 | unchanged |
| A3 cycle-time slip (non-qs) | 4 | 6 | 1 | 4 | 0 | 15 | unchanged |
| B1 HALT-cycle address | 0 | 1 | 0 | 0 | 0 | 1 | unchanged |
| B2 HALT entry (one leg only) | 0 | 2 | 0 | 0 | 0 | 2 | unchanged |
| C1 vector-1 trap MISSED by core | 0 | 0 | 0 | 0 | 1 | 1 | unchanged |
| C2 INTA-vectored delivery | 6 | 0 | 3 | 0 | 0 | 9 | unchanged |
| C3 NMI(vec2) entry | 1 | 0 | 0 | 0 | 0 | 1 | unchanged |
| C4 other-vector delivery | 1 | 0 | 0 | 0 | 0 | 1 | unchanged |
| **D1 chip fetched, core did not** | 7 | **2** | 0 | 0 | 0 | **9** | `fz2e/530020` LEFT, from the TIMING cell |
| D2 core fetched, chip did not | 2 | 6 | 0 | 0 | 0 | 8 | unchanged |
| **D3 both fetched, different address** | **3** | **2** | 0 | 0 | 0 | 5 | `fz2e/527051` FUNC → TIME |
| E1 same-status data cycle, different address | 19 | 4 | 1 | 10 | 5 | 39 | unchanged |
| E2 different-status data cycle | 0 | 1 | 0 | 0 | 1 | 2 | unchanged |
| **NEW/UNCLASSIFIED** | **1** | 0 | 0 | **1** | **2** | **4** | 4 FUNC + 2 COSM + 1 UNSC LEFT |
| **TOTAL** | **44** | **30** | **5** | **17** | **10** | **106** | |

**The two derivations are independent and they agree.**  (a) constrains the
FUNCTIONAL/TIMING split from a falsifier's own cell count; (b) reaches the same
44/30 from the ledger's family counts and the eight leavers' rows.  Registered
as a bar in its own right: **K-2b, the class × family table above, row for row.**

### §1.5 THE SECONDARY CELLS — REGISTERED, THOUGH G6 DOES NOT READ THEM

| bar cell | F19 measured | **F20 PREDICTED** | derivation |
|---|---:|---:|---|
| **C-ROW / C-ARCH** | 114/114 · 114/114 | **106/106 · 106/106** | `fz2_flash20_results` §3.5 reports G5 PASS |
| **G1 pool** (no two-sided dump) | 24 = 13 one-sided + 11 UNSC | **20** = 10 + 10 | − `fz2e/526075` (one-sided, left) − `fz2e/534003` (UNSC, left) − `409077`/`518053`/`530046` (gained a second dump) + `518039` (lost one) |
| **G2 pool** (two-sided dumps that differ) | 36 | **34** | − `508068` − `509050` − `514001` (left) − `527051` (dumps became identical) − `518039` (now one-sided) + `409077` + `518053` + `530046` |
| **G3 pool** (schedule moved) | 84 | **79** | − the four FUNCTIONAL entrants of F19, all schedule-changed − `fz2e/530020`; `521024`/`522002`/`534003` were never in it |
| **G4** FALSE on | 90 / 114 | **84 / 106** | the residue |
| **G4** by first failing clause | arch 36 · cycle_starts 30 · no_dump_proof 24 | **arch 34 · cycle_starts 30 · no_dump_proof 20** | sums to 84, and `34 + 10 = 44` reproduces FUNCTIONAL independently |

⚠ **G1, G2 and G3 ARE DERIVED THROUGH THE CENSUS'S ROW SCAN, NOT THROUGH THE
LEDGER'S FLAGS, AND THE TWO ARE KNOWN TO DISAGREE ON SIX SEEDS** (census PART I
§I.2 / §I.6 item 2).  All three are registered anyway, and a miss on any of them
is reported as registered and is **not** a G6 cell.  G3 is again *derived by
exclusion* and is flagged as the one that is.

## §1.6 THE PREDICTED `IMMATERIAL` MEMBERSHIP — 22, CLAUSE BY CLAUSE

**Predicted: the F19 twenty-four, minus `fz2e/521024` and `fz2e/522002`, with
ZERO entrants.  Sub-classes COSMETIC 17 · TRANSIENT 5.**

⚠ **THE TWO LEAVERS DID NOT FAIL A CLAUSE — THEY LEFT THE LEDGER**, and the
distinction is the whole reason this class is derived per invocation instead of
listed.  `evidence()` is only ever asked about entries in the current ledger;
both seeds read `SUCCESS / clean` at FLASH #20, so the population shrank around
a class that did not move.  **No member was evicted and none may be**; §4 hard
stop 4 says so.

**FIVE MEMBERS' EVIDENCE CELLS MOVE AND ALL FIVE STAY MEMBERS.**  Their row
counts are read from the F20 ledger, which is an input:

| member | `bad_rows` F19 → F20 | predicted sub-class | clause-by-clause |
|---|---|---|---|
| `fz2c/409065` | 16 → **12** | COSMETIC | value-only columns; `addr=2, data=8, nxta=2` predicted by the family's own shape (`fz2e/525017` reads exactly that at 12 rows) |
| `fz2c/408021` | 26 → **22** | **TRANSIENT** | it carries `bs`, which is `CYCLE_DEFINING`; the exact column counts are **NOT derived** and are reported |
| `fz2e/521049` | 14 → **10** | COSMETIC | `addr=2, data=6, nxta=2` predicted |
| `fz2e/525017` | 12 → **8** | COSMETIC | `addr=2, data=4, nxta=2` predicted |
| `fz2e/528010` | 4 → **7** | COSMETIC | `fz2_flash20_results` §3.5 (`C-15b`) measured it as COSMETIC with columns `addr=1, data=2, nxta=1, ube=6`; `ube` is `VALUE_ONLY` |

The remaining **17** members are predicted **byte-identical** in every cell of
the anchored table, and **a changed cell there is a FINDING**.

⚠ **`fz2e/528010` IS A MEMBER WHOSE ROW COUNT WENT UP AND IT IS REGISTERED
THAT WAY.**  `fz2_f19_housekeeping_results` §3.4b measured it OFFLINE at
`bad_rows` 4 → **2,067** and named it a FLASH #20 blocker; in FABRIC it reads
**7**.  The disposition takes the fabric rows, which is what every clause here
has always read.  **The offline 2,067 is not this class's input and is not
adjusted for.**

## §1.7 `TIMING_RECONVERGED` — 7, AND THE USER'S RULING CARRIES UNCHANGED

**Predicted membership: the F19 seven, unchanged seed for seed** —
`fz2c/406073`, `fz2c/407064`, `fz2e/511014`, `fz2e/512062`, `fz2e/518006`,
`fz2e/518044`, `fz2e/520000`.  None of the seven left the ledger, and
`fz2_flash20_results` §3.5 (`C-15f`) measures the COUNT at **7**.

⚠ **THE COUNT AND THE MEMBERSHIP ARE DIFFERENT CLAIMS AND ONLY THE COUNT IS
CARRIED FROM THAT DOCUMENT.**  Two seeds could have swapped in and out at a
constant 7.  `fz2e/520000` is a scored-field mover (`first_bad_row` 502 →
2113) and `fz2e/527051` newly joins TIMING; if either changes the membership,
**that is reported as a finding, and the count is still 7.**

**RULED 2026-08-11 and carried forward verbatim: *"Timing reconvergence seeds
are material."*** The ruling is a rule about a PREDICATE, not a seed list, so it
carries to whatever the membership turns out to be without being re-asked.  All
7 stay MATERIAL and inside the 84.

⚠ **Registered again: `TIMING_RECONVERGED` IS NOT A RATCHET.**  It moved by one
seed with no mechanism in each of two consecutive eras (8 → 7 at F19, having
gone 7 → 8 at F18) before holding here.

## §1.8 THE PREDICTED QUOTING FORM

> **84 material-or-unproven of 106 diverging of 3,839**
> — 44 FUNCTIONAL + 30 TIMING + 10 UNSCOREABLE, with 22 dispositioned
> `IMMATERIAL`.

**Never `84 / 3,839` alone.**  The anchored headline in the disposition document
is registered as, literally:

    WORKING-RESIDUE = 84 = 106 − 22

⚠ **THE RESIDUE SHRANK AND THE REASON IS NOT THAT THE CORE IMPROVED ON THE
IMMATERIAL CLASS.**  90 → 84 is six seeds: four FUNCTIONAL, one TIMING and one
UNSCOREABLE left the ledger, and the class itself lost two COSMETIC members to
the same re-capture.  **Four of the six FUNCTIONAL/TIMING departures are the
noise-floor seeds FLASH #19 booked** (`fz2_flash20_results` §0: *"the miss is
entirely FLASH #19's noise reverting"*).  Registered in that direction, with
that attribution, before it is run.

---

## §2 THE DOCUMENT SHAPE — APPEND-ONLY, AS AT F18 AND F19

**Supersession, never overwrite.**  Both documents keep every F19 table
**verbatim**, demoted under a dated *"SUPERSEDED BY FLASH #20"* banner exactly
as the F18 and F17 blocks already sit.  The F20 block becomes **PART I**; the
F19 block keeps its own `§I.x` numbering under the heading **PART I-F19**; PART
I-F18 and PART II (FLASH #17) are **byte-identical** and are not renumbered, for
the reason `fz2_f19_housekeeping_results` §4.6 records (renumbering would edit
superseded text).

The live anchor pairs move to the F20 blocks; the F19 blocks' anchors are
renamed `CENSUS-PARTITION-F19-BEGIN/END` and `IMMATERIAL-MEMBERS-F19-BEGIN/END`
so **exactly one live pair of each exists**.  No F19, F18 or F17 number is
edited, deleted or restated.

⚠ **A MISSING ANCHOR IS A FAIL, AND THE FALSIFIER PARSES *INSIDE* THE ANCHORS.**
`census_doc()` and `dispo_doc()` split on the FIRST occurrence of each literal,
so the anchor strings must not appear in prose; and G6/G7 never fall back to a
superseded block.  Both properties were demonstrated at F19 (P4, P5) and are
re-demonstrated here as K-6.

---

## §3 THE CAPTURE-FILE RECONCILIATION — **MEASURED, NOT PREDICTED** (see §0.2)

### §3.1 THE QUESTION

`timing50_phase2_results_2026-08-12.md` §6.3 reported, over the **F19** ledger's
114 failures: **`capture sha OK: 0   MISMATCH: 107   missing: 7`**.  Which files
moved, are they exactly the registered movers plus the re-capture universe, and
**what mechanism makes seven of them ABSENT**?  *An absence without a mechanism
is a FINDING.*

### §3.2 BYTE MOVEMENT ≠ SCORED-FIELD MOVEMENT — BOTH QUANTIFIED

| population | measured |
|---|---:|
| capture files pinned by the F19 ledger (114 failures + 3 discards) | **117** |
| of those, still present on disk | **108** |
| of those present, **byte-identical** to their F19 `sha256` | **0** |
| of those present, **MOVED** | **108 / 108 = 100 %** |
| **ABSENT** from disk | **9** (7 failures + 2 discards) |
| F19-pinned capture **paths** that changed in the F20 ledger | **0** |
| **F20**-pinned captures (106 failures + 1 discard) verified against disk | **107 / 107 sha256 MATCH, 0 mismatch, 0 missing** |
| seeds in **both** ledgers | **106** |
| of those, with any change in `first_bad_row` / `diverging_rows` / `compare_window` / `arch` / `arch_match` / `done_chip` / `done_core` / `mech` / `family` / `tier` / `banked_verdict` / `banked_sub` / `image_sha256` | **28** |
| `image_sha256` movers (generator drift) | **0** |

**100 % byte movement against 26.4 % scored-field movement**, on a population
where the byte question and the scored question have different answers for 78
seeds.  This is the F19 precedent restated one era on: FLASH #20 re-captured all
3,840 seeds, so new bytes on every retained file are **expected**, and the
registered noise class is about **scored fields**.

### §3.3 THE SEVEN ABSENT FILES — THE MECHANISM, BY NAME

**The campaign directory is re-made for each flash era, so `captures/` holds
exactly the CURRENT era's banked captures and nothing else.**  Measured:

* `sw/testdata/campaigns/{fz2c,fz2e}/results.jsonl` carry **960 + 2,880 = 3,840
  rows and ONE era each — `sof 26d6e79166183a21…`, FLASH #20's** (the F20
  prereg's own `C-3`, `distinct_eras 1`);
* **every one of the 645 capture files on disk was written between 2026-08-12
  04:55:16 and 05:06:01** — the FLASH #20 capture window.  **Not one file
  predates it.**  A surviving F19-era file would have an older mtime; none does.

`fuzz_campaign.cmd_run` writes a capture iff `verdict != SUCCESS`, **or** the
seed is in the frozen keep-rows bank (`k % N == 0`), **or** it is drawn as
SUCCESS ballast.  Measured on this corpus: **107 non-SUCCESS seeds, 107 with a
capture, 0 missing**, plus **538 SUCCESS captures** whose `k` are `fz2c` every
**2** and `fz2e` every **50** — the keep-rows bank, not a quota.

All ten F19-pinned seeds that are absent from the F20 ledger read **`SUCCESS`**
in the F20 `results.jsonl`, and their capture survives **iff** they are
keep-rows seeds:

| F19-pinned, F20-absent seed | F20 verdict | `k mod 50` | capture on disk |
|---|---|---:|---|
| `fz2e/508068` | SUCCESS / clean | 18 | **absent** |
| `fz2e/514001` | SUCCESS / clean | odd | **absent** |
| `fz2e/521024` | SUCCESS / clean | 24 | **absent** |
| `fz2e/522002` | SUCCESS / clean | 2 | **absent** |
| `fz2e/526075` | SUCCESS / window_truncated | odd | **absent** |
| `fz2e/530020` | SUCCESS / clean | 20 | **absent** |
| `fz2e/534003` | SUCCESS / window_truncated | odd | **absent** |
| **`fz2e/509050`** | SUCCESS / clean | **0** — `509050 = 50 × 10181` | **PRESENT, new bytes** |
| `fz2e/524027` *(F19 discard)* | SUCCESS / clean | odd | **absent** |
| `fz2e/535070` *(F19 discard)* | SUCCESS / clean | 20 | **absent** |

**THE P2 SWEEP'S `0 / 107 / 7` IS FULLY RECONCILED AND IS NOT A FINDING.**  It
swept the 114 **failures** only: 106 are still failures (present, all bytes
new), `fz2e/509050` is present because it is a **keep-rows** seed, and the
remaining **7** have no F20 capture because they passed and are not in the
keep-rows bank.  `106 + 1 = 107 MISMATCH`, `7 missing`, `0 OK`.  The two absent
**discards** are outside that sweep's population and are absent for the same
reason.

⚠ **THE SIDE-EFFECT WORTH NAMING: A SEED THAT PASSES LOSES ITS EVIDENCE.**  The
F19-era rows for those seven no longer exist in the tree, so **no era-to-era
row-level comparison can be made for a seed that closes**, and the F19 census's
classification of them can never be re-derived from artifacts.  Booked here, not
repaired; the cheap instrument change is F19's own booked one — *bank a per-seed
capture digest*, to which this sitting adds: **retain the capture of any seed
named in a committed ledger, even when it passes.**

---

## §4 THE BARS

| # | bar | how it is scored |
|---|---|---|
| **K-1** | `fz2_materiality` controls on the F20 ledger: **C-ROW 106/106, C-ARCH 106/106**, exit 0 | the census is quotable or it is not |
| **K-2** | the derived partition equals §1.3's — **FUNCTIONAL 44 · TIMING 30 · TRANSIENT 5 · COSMETIC 17 · UNSCOREABLE 10 · total 106 · IMMATERIAL 22 · TIMING_RECONVERGED 7** — or the miss is reported cell by cell under §1.4's registered branches | point prediction, reported as registered |
| **K-2b** | the class × family table of §1.4(b), **row for row** | the second, independent derivation |
| **K-3** | IMMATERIAL membership = the F19 twenty-four **minus `fz2e/521024` and `fz2e/522002`, zero entrants**; the 17 unmoved members byte-identical, the 5 moved ones at §1.6's row counts and sub-classes | set for set, printed; a changed cell is a FINDING |
| **K-4** | `fz2e/527051` classifies **TIMING**, printed with `evidence()`'s own `why` string, so the clause it failed is visible | §1.2's per-seed derivation |
| **K-5** | `fz2_immaterial falsify` exits **0**, G1–G8 all PASS, on the F20 ledger | the booked repair |
| **K-6** | **the falsifier is DEMONSTRATED TO FAIL** on at least one perturbation applied to a COPY outside the repo, caught by a NAMED bar, plus the append-only control that perturbing a SUPERSEDED block moves nothing | a falsifier that has only ever passed has not been shown to be one |
| **K-7** | `sw/fz2_ledger.py:CURRENT` names the F20 ledger, and every consumer that reads it through `load()` still prints the file it read | the era re-pin |
| **K-8** | `fz2_w1 lint` PASS · `test_artifact` **45/45** · **zero diffs under `sw/testdata/`** except a legitimately regenerated `fz2_bars.json` (timestamp churn reverted) | nothing moves |
| **K-9** | §3's reconciliation stands: **0 F20-pinned captures mismatched or missing**, and the seven absent files each carry the §3.3 mechanism | an absence without a mechanism is a FINDING |

⚠ **`fz2_w1 bars` IS CARRIED AS REGISTERED, NOT RE-LITIGATED.**  FLASH #20
reported its verdicts (`fz2_flash20_results_2026-08-12.md` §4), **C-6 among
them**, and that is this sitting's input, not its subject.  A `bars` run here is
reported for the record; **it is not a bar of this document.**

**K-8's `sw/testdata/` clause is a HARD STOP**: this work writes nothing into any
banked artifact.

---

## §5 HARD STOPS

1. Any write under `sw/testdata/` other than a regenerated `fz2_bars.json`.
2. Any edit to `evidence()`'s clauses, to `CYCLE_DEFINING` / `VALUE_ONLY`, or to
   any class boundary.
3. Any seed list appearing in either tool.
4. Admitting or evicting a member in order to reach a count.
5. Any board contact, Quartus compile, or edit under `hdl/` (§0.1 — a parallel
   sitting owns `v30u_eu.sv` and its testbench).
6. Editing, deleting or restating a FLASH #17, #18 or #19 number.
7. Committing the read-only `captures` symlinks this sitting creates.

## §6 WHAT WOULD MAKE THIS A MISS

* the derived partition contradicting both of §1.4(a)'s branches, or splitting
  across two cells (a finding against FLASH #20's own `5 / 8`);
* the class × family table disagreeing with §1.4(b) on any row;
* any change in the 17 unmoved members' cells, or any entrant to the class;
* a `TIMING_RECONVERGED` membership other than §1.7's seven, at any count;
* `falsify` passing but not being demonstrable as failing (K-6);
* any absent capture file without the §3.3 mechanism.

Each is reported in the form it is registered in here.  **Nothing is
re-registered after the fact.**
