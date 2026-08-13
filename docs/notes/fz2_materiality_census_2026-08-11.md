# fz2 MATERIALITY CENSUS — WHAT THE RESIDUE ACTUALLY COSTS

    tool        sw/fz2_materiality.py           (reviewer-re-runnable, offline)
    LIVE ERA    FLASH #20 -- see PART I
    input       sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json
                (= `sw/fz2_ledger.py:CURRENT`)
                + the 106 banked FABRIC captures it names, sha256-verified
    branch      master @ 298d522872
    era         sof 26d6e79166183a21…  (FLASH #20)
    date        2026-08-12
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.

    HISTORY     FLASH #19 (114 / 24 / 90) is retained VERBATIM as PART I-F19.
                Its `input` was fz2_failure_ledger_f19_2026-08-12.json,
                branch @ 6e91923853, era sof 03365b1115e1f338….
                FLASH #18 (110 / 24 / 86) is retained VERBATIM as PART I-F18.
                Its `input` was fz2_failure_ledger_f18_2026-08-11.json,
                branch @ 770c0d1b85, era sof b2a1fe5f83167fbf….
                FLASH #17 (113 / 21 / 92) is retained VERBATIM as PART II.
                Its `input` was fz2_failure_ledger_f17_2026-08-11.json,
                branch @ 1ad5074ebe, era sof 26c19f613e2caae8….

    ⚠ READING NOTE ON THE PART NAMES.  The blocks are ordered NEWEST FIRST and
    the older ones are NOT renumbered, because each older block's prose refers
    to its own sections as "§I.x" and to the block below it by the name it had
    when it was written.  Renumbering would mean editing superseded text, which
    this document forbids.  So the live block is PART I (FLASH #20), the
    previous live blocks keep their own §I.x numbering under the headings PART
    I-F19 and PART I-F18, and PART II is still FLASH #17.  **Inside a block, a
    bare §I.x reference means that block's.**

    reproduce   python3 sw/fz2_materiality.py
                python3 sw/fz2_materiality.py --seed fz2e/517046   (one seed)

⚠ **THE PARTITION IS PARSED FROM THIS FILE, AND ONLY FROM BETWEEN THE ANCHORS
IN §I.0.**  `sw/fz2_immaterial.py falsify`'s **G6** reads the
`CENSUS-PARTITION-BEGIN` / `-END` HTML-comment pair and nothing else, so
**PART II's tables are history and are not claims**.  If the anchors go
missing, G6 FAILS — it never falls back to reading the whole file, because
falling back is exactly how a superseded table would be read as the live
registration.

⚠ **THE ANCHOR LITERALS ARE DELIBERATELY NOT SPELT OUT IN PROSE ANYWHERE IN
THIS FILE.**  `census_doc()` splits on the FIRST occurrence of each, so a
mention of the exact comment in running text would truncate the parsed region
and G6 would score an empty partition.  Read them off §I.0.

---
---

# PART I — FLASH #20.  **THE LIVE CENSUS.**

    re-derived 2026-08-12 under `docs/notes/fz2_f20_housekeeping_prereg_2026-08-12.md`,
    which was committed at `18dc133914` BEFORE either tool was run against the
    F20 ledger in this sitting.
    results     docs/notes/fz2_f20_housekeeping_results_2026-08-12.md

**WHY THIS PART EXISTS, AND WHY IT IS ONLY AN ERA RE-PIN.**  FLASH #20 flashed
the ghost LAUNCH relocation and **re-captured the whole corpus**
(`fz2_flash20_results_2026-08-12.md`).  The population this census partitions
moved **114 → 106** with **eight leavers and zero entrants**, and the
denominator moved **3,837 → 3,839** because two of FLASH #19's three
`ps3_8080` discards reverted.  FLASH #20's own `C-15e` **registered G6 and G7 to
FAIL on document staleness alone** and booked the re-pin for the next
housekeeping sitting; `timing50_phase2_results_2026-08-12.md` §6.3 then found
`fz2_immaterial falsify` could not run at all against the F19 pointer
(`capture sha OK: 0 / MISMATCH: 107 / missing: 7`) and recorded it **OWED, not
claimed**.  This is that payment.

⚠ **THE MOVEMENT IS MOSTLY FLASH #19's NOISE REVERTING, AND THAT IS NOT THIS
CENSUS'S CLAIM — IT IS FLASH #20's.**  Four of the eight leavers are four of the
six seeds FLASH #19 measured as its capture noise floor (`fz2_flash20_results`
§0: *"the miss is entirely FLASH #19's noise reverting"*).  **The residue
shrank 90 → 84 and no seed became less material by being re-read.**

## I.0 THE PARTITION — THE REGISTERED CELLS

    C-ROW   diff_rows reproduces the ledger   106 / 106   PASS
    C-ARCH  arch_dump reproduces the ledger   106 / 106   PASS
    exit 0

<!-- CENSUS-PARTITION-BEGIN -->

| class | seeds | % of 106 | % of 3,839 |
|---|---:|---:|---:|
| **FUNCTIONAL** — the architectural result differs | **44** | 41.51 % | 1.15 % |
| **TIMING** — dumps identical, the bus schedule differs | **30** | 28.30 % | 0.78 % |
| **TRANSIENT** — dumps identical, schedule identical, a cycle-defining pin moved | **5** | 4.72 % | 0.13 % |
| **COSMETIC** — dumps identical, schedule identical, value-only diffs | **17** | 16.04 % | 0.44 % |
| **UNSCOREABLE** — neither leg dumped; no proof either way | **10** | 9.43 % | 0.26 % |

    MATERIAL    (functional + timing)   74 / 106 = 69.81 %   =  1.93 % of 3,839
    IMMATERIAL  (transient + cosmetic)  22 / 106 = 20.75 %   =  0.57 % of 3,839
    UNPROVEN    (no dump either leg)    10 / 106 =  9.43 %   =  0.26 % of 3,839

    TIMING (30), split by whether the program's total length moved:
        a bus cycle starts on a clock the other leg has none : 30
        done-marker clock differs, cycle starts all match    :  0
        unmatched cycle STARTS per seed: min 1  median 103  max 433
        done-marker clock IDENTICAL (local re-schedule only) :  7
        done-marker clock MOVED (total run length changed)   : 23
        |done-clock delta| over the 23 that moved: min 1  median 3  max 715 clocks

<!-- CENSUS-PARTITION-END -->

**The headline on FLASH #20: of the 106 residual seeds, 22 have no measured
consequence at all, 10 cannot be asked, and 74 do.**  Read against the corpus,
**3,755 of 3,839 seeds (97.81 %) either match the chip outright or differ in a
way with no measured functional or timing consequence**; 74 (1.93 %) carry one;
10 (0.26 %) cannot be adjudicated.

## I.1 WHAT MOVED, F19 → F20, CELL BY CELL

| cell | F19 | **F20** | Δ | why |
|---|---:|---:|---:|---|
| FUNCTIONAL | 49 | **44** | −5 | four FUNCTIONAL leavers (§I.2) **and** `fz2e/527051`, whose two dumps became identical and which is now TIMING |
| TIMING | 30 | **30** | 0 | `fz2e/530020` LEFT and `fz2e/527051` ARRIVED — **the cell did not move and its membership did** |
| TRANSIENT | 5 | **5** | 0 | unmoved, seed for seed |
| COSMETIC | 19 | **17** | −2 | `fz2e/521024` and `fz2e/522002` LEFT the ledger |
| UNSCOREABLE | 11 | **10** | −1 | `fz2e/534003` LEFT the ledger |
| **total** | **114** | **106** | −8 | LEFT 8 / ENTERED 0 |
| **IMMATERIAL** | **24** | **22** | −2 | zero entrants; the two COSMETIC leavers |
| `TIMING_RECONVERGED` | 7 | **7** | 0 | **membership identical seed for seed**, §I.4 |

**Five of G6's eight cells moved, which is exactly the `5 / 8` FLASH #20
measured** (`fz2_flash20_results_2026-08-12.md` §3.5) — and the
pre-registration used that 5 as an arithmetic constraint to make the class table
a POINT prediction rather than a guess.  **Every cell above was registered at
`18dc133914` and every one is MET.**

## I.2 THE EIGHT LEAVERS AND THE ONE SEED THAT CHANGED CLASS

**Nothing entered the ledger at FLASH #20.**  The eight that left, with the
class each held on FLASH #19 and its F20 `results.jsonl` verdict:

| seed | family | F19 CLASS | F20 verdict |
|---|---|---|---|
| `fz2e/508068` | NEW/UNCLASSIFIED | FUNCTIONAL | SUCCESS / clean |
| `fz2e/509050` | NEW/UNCLASSIFIED | FUNCTIONAL | SUCCESS / clean |
| `fz2e/514001` | NEW/UNCLASSIFIED | FUNCTIONAL | SUCCESS / clean |
| `fz2e/526075` | NEW/UNCLASSIFIED | FUNCTIONAL | SUCCESS / window_truncated |
| `fz2e/521024` | NEW/UNCLASSIFIED | COSMETIC *(an `IMMATERIAL` member)* | SUCCESS / clean |
| `fz2e/522002` | NEW/UNCLASSIFIED | COSMETIC *(an `IMMATERIAL` member)* | SUCCESS / clean |
| `fz2e/530020` | D1 chip fetched, core did not | **TIMING** | SUCCESS / clean |
| `fz2e/534003` | NEW/UNCLASSIFIED | **UNSCOREABLE** | SUCCESS / window_truncated |

⚠ **AN ERRATUM AGAINST A SUPERSEDED RESULTS DOCUMENT.**
`fz2_f19_housekeeping_results_2026-08-12.md` §2.4 calls its three offline
closures — `fz2e/521024`, `fz2e/522002`, `fz2e/534003` — *"all three … 4-row
COSMETIC IMMATERIAL members"*.  **`fz2e/534003` is not a member and never
was**: its F19 ledger row reads `done_chip` **False** and `done_core` **False**,
so neither leg dumped and it is one of the eleven UNSCOREABLE.  The statement is
true of the other two.  **Nothing is edited in that document** — it is
superseded history — and the erratum was registered in this re-pin's
pre-registration before either tool was run.  `fz2e/530020` was likewise never a
member: it is TIMING.

**THE ONE CLASS CHANGE AMONG THE 106 SEEDS IN BOTH LEDGERS IS `fz2e/527051`.**

| seed | F19 ledger | F20 ledger | consequence |
|---|---|---|---|
| `fz2e/527051` | `arch` `AW,BP,BW,CW,IX,IY,PSW`, `arch_match` **False** | `arch` **`OK`**, `arch_match` **True** | the 15-word dumps became identical, so `measure()`'s first branch no longer fires — **FUNCTIONAL → TIMING**, `cycle_starts chip-only 174 / core-only 176; done_clock −17` |

Twenty-eight of the 106 shared seeds moved a scored field; `527051` is the only
one that moved a CLASS, and both of the two independent derivations in the
pre-registration predicted it before the run.

## I.3 CLASS × FAMILY, ON THE F20 LEDGER

| family | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| A1 qs-pop one clock late | 0 | 5 | 0 | 0 | 0 | 5 |
| A2 qs-pop other offset | 0 | 1 | 0 | 2 | 1 | 4 |
| A3 cycle-time slip (non-qs) | 4 | 6 | 1 | 4 | 0 | 15 |
| B1 HALT-cycle address | 0 | 1 | 0 | 0 | 0 | 1 |
| B2 HALT entry (one leg only) | 0 | 2 | 0 | 0 | 0 | 2 |
| C1 vector-1 trap MISSED by core | 0 | 0 | 0 | 0 | 1 | 1 |
| C2 INTA-vectored delivery | 6 | 0 | 3 | 0 | 0 | 9 |
| C3 NMI(vec2) entry | 1 | 0 | 0 | 0 | 0 | 1 |
| C4 other-vector delivery | 1 | 0 | 0 | 0 | 0 | 1 |
| **D1 chip fetched, core did not** | 7 | **2** | 0 | 0 | 0 | **9** |
| D2 core fetched, chip did not | 2 | 6 | 0 | 0 | 0 | 8 |
| **D3 both fetched, different address** | **3** | **2** | 0 | 0 | 0 | 5 |
| E1 same-status data cycle, different address | 19 | 4 | 1 | 10 | 5 | 39 |
| E2 different-status data cycle | 0 | 1 | 0 | 0 | 1 | 2 |
| **NEW/UNCLASSIFIED** | **1** | 0 | 0 | **1** | **2** | **4** |
| **TOTAL** | **44** | **30** | **5** | **17** | **10** | **106** |

**TWELVE OF THE FIFTEEN FAMILY ROWS ARE BYTE-IDENTICAL TO PART I-F19's**, and
the three that moved are exactly the three the ledger's own `family_counts`
predicted: **D1 10 → 9** (`fz2e/530020` out of its TIMING cell),
**NEW/UNCLASSIFIED 11 → 4** (four FUNCTIONAL + two COSMETIC + one UNSCOREABLE
out), and **D3 5 → 5 with FUNC 4 → 3 and TIME 1 → 2** (`fz2e/527051` moving
inside its own family).  This table was registered row for row before the run
as the re-pin's **second, independent derivation** of the 44/30 split, and it
agrees with the first cell for cell.

## I.4 `TIMING_RECONVERGED` ON FLASH #20 — 7 SEEDS, MEMBERSHIP UNMOVED

> **THE RULING STANDS, RE-STATED ON THIS ERA (user, 2026-08-11): "Timing
> reconvergence seeds are material."**  All **7** stay MATERIAL, all 7 are
> inside the 30 TIMING and inside the 84 working residue, and the sub-class
> remains a named lens (`fz2_immaterial.py reconverged`), not a disposition.
> The ruling is a rule about a PREDICATE, not about a seed list, so it carries
> across a membership change without being re-asked.

The membership is **the F19 seven, seed for seed**: `fz2c/406073`,
`fz2c/407064`, `fz2e/511014`, `fz2e/512062`, `fz2e/518006`, `fz2e/518044`,
`fz2e/520000`.

⚠ **THE COUNT AND THE MEMBERSHIP ARE DIFFERENT CLAIMS, AND THIS ERA IS THE
FIRST IN WHICH BOTH WERE CHECKED.**  `fz2e/520000` moved its `first_bad_row`
502 → 2113 and `fz2e/527051` newly joined TIMING; **neither changed the
membership**.  The cell had moved by one seed with no mechanism in each of the
two preceding eras (7 → 8 at F18, 8 → 7 at F19), and **it is still not a
ratchet** — a third era of stability is evidence, not a warrant.

## I.5 WHAT PART I-F19'S NON-PARTITION SECTIONS STILL SAY, AND WHERE THEY DO NOT

Re-measured on the F20 ledger:

* **the dump-proof audit**: **19 of 106 without a two-sided dump — 9 one-sided
  → FUNCTIONAL, 10 neither → UNSCOREABLE** (F19: 24 = 13 + 11), 8 re-aligning
  and 2 diverging to the window end, and **0 class-3/4 seeds classified without
  a dump proof**.  ⚠ The pre-registration predicted **20 = 10 + 10** and **34**
  for the two-sided-differing pool; the measurement is **19** and **35**.  Both
  misses are **equal and opposite**, they are the same root, and **neither is a
  G6 cell** — §I.6 item 2 names the root.
* **the ten UNSCOREABLE seeds are the F19 eleven minus `fz2e/534003`**, all
  `raw`, all escaped, counterfactual `would be` TIMING 4 · TRANSIENT 1 ·
  COSMETIC **5** (F19: 4 · 1 · 6).  **Exactly one COSMETIC counterfactual cell
  moved, and `fz2e/534003`'s own shape is a 4-row would-be COSMETIC** — which is
  the check that no seed silently entered or left this class alongside it;
* **the escaped overlap is 59 of 106** (F19: 64 of 114);
* the ledger's own `new_failure` set is **4** (F19: 11), and three of F17's six
  new-at-F17 anchors are now `NOT IN LEDGER`.

⚠ **THE CLASS × BANKED VERDICT TABLE IS STILL A WITHIN-ERA TABLE ONLY** and must
not be diffed across eras, for PART I-F18 §I.5's reason (`80075d049a` retired
the `open_bus` accept rule).  On F20 it reads:

| banked verdict | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| `FUNCTIONAL` | 41 | 12 | 1 | 13 | 7 | 74 |
| `KNOWN_ACCEPTED` | 2 | 11 | 4 | 4 | 2 | 23 |
| `TIMING` | 1 | 7 | 0 | 0 | 1 | 9 |

## I.6 WHAT PART I LEAVES OPEN

1. **The 10 UNSCOREABLE seeds** — unmoved for a fourth era apart from the one
   that left, still all `raw` and all escaped; the instrument fix is still *a
   terminator that survives an escaped program*.
2. **The `arch: NODUMP` / census-row-scan disagreement is WIDER than PART I-F19
   §I.2 recorded, and it is the root of this era's G1/G2 miss.**  That section
   named six seeds whose ledger `arch` reads `NODUMP` while the census finds
   both dumps.  The re-pin's own per-seed derivation then assumed the converse
   never happens — and it does: **`fz2c/406063` and `fz2e/518039` are
   UNSCOREABLE in the census (neither leg dumped) in BOTH eras, while their
   ledger `done_core` flag MOVED across the era** (False → True and True →
   False respectively).  The class was right both times; the pool sizes were
   not.  **Booked with the seeds named; not fixed here**, because changing a
   derivation rule inside a re-pin is changing the instrument in the sitting
   that found it.
3. **The G3 pool was registered at 79 by exclusion and measured 76.**  The
   eight non-IMMATERIAL seeds with an unchanged schedule are 6 → 8: one left
   (`fz2e/534003`) and **three arrived — `fz2e/518053`, `fz2e/518067`,
   `fz2e/526054`**, whose row counts collapsed at FLASH #20 (3,413 → 8,
   3,278 → 45, 320 → 48).  A seed that stops diverging on a schedule stops
   being in the schedule pool; the prereg flagged this cell as the one derived
   by exclusion, and it is reported as registered.
4. **phantom-T1's one remaining `bs` cell** — unchanged from PART I-F19 §I.6.
5. **The honesty clause's blind spot is unchanged**: the dump-identity proof
   covers 15 registers at the end of the run and nothing else.
6. **The residue is still mostly material — 74 of 106 (69.81 %)**, essentially
   flat against F19's 69.30 %.  **No seed became more or less material by being
   re-read**; the population around the classes moved.

---
---

# PART I-F19 — FLASH #19.  ⚠ **SUPERSEDED 2026-08-12 BY PART I (FLASH #20).  HISTORY, NOT A CLAIM.**

**Everything below this line to the PART I-F18 divider is the FLASH #19-era
census, retained VERBATIM apart from this heading line and the two anchor
comments, which are renamed `CENSUS-PARTITION-F19-BEGIN/END` so that exactly one
LIVE anchor pair exists in this file.  No number in it is edited or restated.**

    re-derived 2026-08-12 under `docs/notes/fz2_f19_housekeeping_prereg_2026-08-12.md`,
    which was committed at `6e91923853` BEFORE either tool was run against the
    F19 ledger.
    results     docs/notes/fz2_f19_housekeeping_results_2026-08-12.md

**WHY THIS PART EXISTS, AND WHY IT IS ONLY AN ERA RE-PIN.**  FLASH #19 landed
**E-1 alone** (one `set_multicycle_path` pair, no RTL) and re-captured the
corpus.  Six seeds moved, **all six measured as the capture noise floor** by a
second capture on the same bitstream minutes later that reverted every one of
them (`fz2_flash19_results_2026-08-12.md` §4.6); four of the six ENTERED the
ledger and two became `ps3_8080` DISCARDS, so the population this census
partitions moved **110 → 114**.  `fz2_immaterial falsify` reported **G6 (3 of
8 cells) and G7 (1 of 25) FAIL** against PART I-F18 for exactly that reason,
and that sitting **booked the re-derivation rather than doing it in the sitting
that measured the failure**.  This is that re-derivation.

⚠ **THE GHOST LAUNCH RELOCATION IS NOT IN THIS CENSUS AND CANNOT BE.**  It
merged at `ef19010e63`, **after** FLASH #19 was flashed and captured, and it is
on no flashed bitstream.  Both legs of every row here are fabric: the socket
leg is silicon, the core leg is the FPGA core of `.sof 03365b1115e1f338…`,
built from `fc0ae65d56`.  **Zero cells in this part are relocation-driven, and
that was registered before the run.**  What the relocation *does* move is the
OFFLINE replay column, which is a different instrument and is reported in
`fz2_f19_housekeeping_results_2026-08-12.md`, never here.

## I.0 THE PARTITION — THE REGISTERED CELLS

    C-ROW   diff_rows reproduces the ledger   114 / 114   PASS
    C-ARCH  arch_dump reproduces the ledger   114 / 114   PASS
    exit 0

<!-- CENSUS-PARTITION-F19-BEGIN -->

| class | seeds | % of 114 | % of 3,837 |
|---|---:|---:|---:|
| **FUNCTIONAL** — the architectural result differs | **49** | 42.98 % | 1.28 % |
| **TIMING** — dumps identical, the bus schedule differs | **30** | 26.32 % | 0.78 % |
| **TRANSIENT** — dumps identical, schedule identical, a cycle-defining pin moved | **5** | 4.39 % | 0.13 % |
| **COSMETIC** — dumps identical, schedule identical, value-only diffs | **19** | 16.67 % | 0.50 % |
| **UNSCOREABLE** — neither leg dumped; no proof either way | **11** | 9.65 % | 0.29 % |

    MATERIAL    (functional + timing)   79 / 114 = 69.30 %   =  2.06 % of 3,837
    IMMATERIAL  (transient + cosmetic)  24 / 114 = 21.05 %   =  0.63 % of 3,837
    UNPROVEN    (no dump either leg)    11 / 114 =  9.65 %   =  0.29 % of 3,837

    TIMING (30), split by whether the program's total length moved:
        a bus cycle starts on a clock the other leg has none : 30
        done-marker clock differs, cycle starts all match    :  0
        unmatched cycle STARTS per seed: min 1  median 97  max 433
        done-marker clock IDENTICAL (local re-schedule only) :  7
        done-marker clock MOVED (total run length changed)   : 23
        |done-clock delta| over the 23 that moved: min 1  median 3  max 715 clocks

<!-- CENSUS-PARTITION-F19-END -->

**The headline on FLASH #19: of the 114 residual seeds, 24 have no measured
consequence at all, 11 cannot be asked, and 79 do.**  Read against the corpus,
**3,747 of 3,837 seeds (97.65 %) either match the chip outright or differ in a
way with no measured functional or timing consequence**; 79 (2.06 %) carry one;
11 (0.29 %) cannot be adjudicated.

⚠ **THE RESIDUE GOT BIGGER, AND NOT BECAUSE ANYTHING GOT WORSE.**  The working
residue is 86 → **90**.  Four seeds entered the ledger, all four classify
MATERIAL, and **all four are inside the six FLASH #19 measured as the noise
floor**.  This is a lens on a re-captured corpus, not a re-score; `bars` is
untouched and no gate moved.

## I.1 WHAT MOVED, F18 → F19, CELL BY CELL

| cell | F18 | **F19** | Δ | why |
|---|---:|---:|---:|---|
| FUNCTIONAL | 45 | **49** | +4 | **all four ledger entrants classify FUNCTIONAL** — `fz2e/508068`, `fz2e/509050`, `fz2e/514001`, `fz2e/526075` |
| TIMING | 30 | **30** | 0 | unmoved, seed for seed |
| TRANSIENT | 5 | **5** | 0 | unmoved, seed for seed |
| COSMETIC | 19 | **19** | 0 | unmoved, seed for seed |
| UNSCOREABLE | 11 | **11** | 0 | unmoved, seed for seed |
| **total** | **110** | **114** | +4 | ENTERED 4 / LEFT 0 |
| **IMMATERIAL** | **24** | **24** | 0 | zero entrants, zero leavers, every cell byte-identical |
| `TIMING_RECONVERGED` | 8 | **7** | −1 | **`fz2e/530020` LEFT** — its own F18 falsifier fired, §I.4 |

**Three of G6's eight cells moved, which is exactly the `3 / 8` the FLASH #19
sitting measured** (`fz2_flash19_results_2026-08-12.md` §4.5) — and the
pre-registration used that 3 as an arithmetic constraint to make the class
table a POINT prediction rather than a guess.  **Every cell above was
registered at `6e91923853` and every one is MET.**

## I.2 THE FOUR NEW FUNCTIONAL SEEDS — THE F19 LEDGER ENTRANTS

| seed | family | tier | `bad_rows` | first_bad | done chip/core | `evidence()` branch |
|---|---|---|---:|---:|---|---|
| `fz2e/508068` | NEW/UNCLASSIFIED | soup | 359 | 681 | 1045 / **1525** | dumps differ, 14 words |
| `fz2e/509050` | NEW/UNCLASSIFIED | soup | 2,863 | 688 | 3605 / 3575 | dumps differ, 14 words |
| `fz2e/514001` | NEW/UNCLASSIFIED | soup | 1,681 | 696 | 3405 / 1983 | dumps differ, 14 words |
| `fz2e/526075` | NEW/UNCLASSIFIED | raw | 3,295 | 697 | 3535 / **None** | terminator reached by CHIP only |

⚠ **THESE FOUR ARE THE NOISE FLOOR, CLASSIFIED — NOT FOUR NEW DEFECTS.**  FLASH
#19 §4.6 re-captured their strata on the same bitstream minutes later and **all
of them reverted to `bad_rows` 0 / SUCCESS**.  The census partitions the
sitting's corpus (run A) because choosing the run after seeing it is the move
this campaign's rules exist to prevent.  **A reader who wants the noise-free
number should read §4.6 of that document, not adjust this table.**

⚠ **ONE PER-SEED DERIVATION IN THE PRE-REGISTRATION WAS WRONG, AND IT IS
REPORTED RATHER THAN QUIETLY CORRECT.**  `fz2e/508068` was predicted to take
the CHIP-only branch, because the ledger's `done_core` reads **False**.  It
took the both-dumped branch: `fz2_materiality` re-scans the rows and finds a
MAGIC-anchored core dump at clock **1525**.  The two derivations disagree
because `fz2_ledger`'s `arch` rule reads the campaign's own `done_sim` FLAG
while the census runs `fuzz_classify._done_idx` over the banked rows.  **The
CLASS is FUNCTIONAL either way**, so the registered partition is unaffected —
but the G1/G2 pool sizes are off by one each, and §I.5 reports them.
**This is PRE-EXISTING and era-independent: six seeds in this ledger read
`arch: NODUMP` while the census finds both dumps** (`fz2c/405002`,
`fz2c/405013`, `fz2e/508068`, `fz2e/512056`, `fz2e/516001`, `fz2e/529009`),
four of them already in the F18 ledger.  Booked, not fixed here; fixing a
derivation rule inside a re-pin would be changing the instrument in the sitting
that found it.

## I.3 CLASS × FAMILY, ON THE F19 LEDGER

| family | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| A1 qs-pop one clock late | 0 | 5 | 0 | 0 | 0 | 5 |
| A2 qs-pop other offset | 0 | 1 | 0 | 2 | 1 | 4 |
| A3 cycle-time slip (non-qs) | 4 | 6 | 1 | 4 | 0 | 15 |
| B1 HALT-cycle address | 0 | 1 | 0 | 0 | 0 | 1 |
| B2 HALT entry (one leg only) | 0 | 2 | 0 | 0 | 0 | 2 |
| C1 vector-1 trap MISSED by core | 0 | 0 | 0 | 0 | 1 | 1 |
| C2 INTA-vectored delivery | 6 | 0 | 3 | 0 | 0 | 9 |
| C3 NMI(vec2) entry | 1 | 0 | 0 | 0 | 0 | 1 |
| C4 other-vector delivery | 1 | 0 | 0 | 0 | 0 | 1 |
| D1 chip fetched, core did not | 7 | 3 | 0 | 0 | 0 | 10 |
| D2 core fetched, chip did not | 2 | 6 | 0 | 0 | 0 | 8 |
| D3 both fetched, different address | 4 | 1 | 0 | 0 | 0 | 5 |
| E1 same-status data cycle, different address | 19 | 4 | 1 | 10 | 5 | 39 |
| E2 different-status data cycle | 0 | 1 | 0 | 0 | 1 | 2 |
| **NEW/UNCLASSIFIED** | **5** | 0 | 0 | **3** | **3** | **11** |
| **TOTAL** | **49** | **30** | **5** | **19** | **11** | **114** |

**FOURTEEN OF THE FIFTEEN FAMILY ROWS ARE BYTE-IDENTICAL TO PART I-F18's.**
The only row that moved is `NEW/UNCLASSIFIED`, 7 → 11, and it took all four
entrants into its FUNCTIONAL cell (1 → 5).  That is the containment check for
an era re-pin: a re-capture that moved six seeds moved exactly one row of this
table, and it is the row whose label means *"this seed has no carried-forward
family"*.

## I.4 `TIMING_RECONVERGED` ON FLASH #19 — 7 SEEDS, AND THE USER RULING CARRIES

> **THE RULING STANDS, RE-STATED ON THIS ERA (user, 2026-08-11): "Timing
> reconvergence seeds are material."**  All **7** stay MATERIAL, all 7 are
> inside the 30 TIMING and inside the 90 working residue, and the sub-class
> remains a named lens (`fz2_immaterial.py reconverged`), not a disposition.
> The ruling is a rule about a PREDICATE, not about a seed list, so it carries
> across a membership change without being re-asked — as it did at F18.

The membership is **exactly the F17 seven, restored**: `fz2c/406073`,
`fz2c/407064`, `fz2e/511014`, `fz2e/512062`, `fz2e/518006`, `fz2e/518044`,
`fz2e/520000`.

⚠ **`fz2e/530020` LEFT, AND THAT IS ITS OWN FALSIFIER FIRING.**  PART I-F18
§I.4 admitted it (7 → 8) *with this falsifier written beside it*: *"a double
capture on one bitstream in which `fz2e/530020`'s `done_chip`/`done_core` are
stable — if they flicker, this membership is capture noise and the count is not
a ratchet."*  FLASH #19 §4.3 records that its `diverging_rows` moved 326 → 671
— **the only shared-failure row count that moved in the whole corpus** — and
the count reads 7.  **The falsifier FIRED.  8 was not a ratchet.**

⚠ **REGISTERED CONSEQUENCE: `TIMING_RECONVERGED` IS NOT A RATCHET AND MUST NOT
BE QUOTED AS ONE.**  It has now moved by one seed in each of two consecutive
eras with no mechanism on either side.  The honest reading is that this cell
tracks the capture noise floor, not a property of the core.

## I.5 WHAT PART I-F18'S NON-PARTITION SECTIONS STILL SAY, AND WHERE THEY DO NOT

Re-measured on the F19 ledger:

* **the dump-proof audit moved by one seed in each direction of the split**:
  **24 of 114 without a two-sided dump — 13 one-sided → FUNCTIONAL, 11 neither
  → UNSCOREABLE** (F18: 23 = 12 + 11), 8 re-aligning and 3 diverging to the
  window end, and **0 class-3/4 seeds classified without a dump proof**.
  ⚠ The pre-registration predicted **25 = 13 + 12** here and **35** for the
  two-sided-differing pool; the measurement is **24** and **36**.  Both misses
  are the single `fz2e/508068` branch error of §I.2 and nothing else, they are
  equal and opposite, and neither is a G6 cell.
* **the eleven UNSCOREABLE seeds are unmoved, seed for seed**, all `raw`, all
  escaped, counterfactual still `would be` TIMING 4 · TRANSIENT 1 · COSMETIC 6;
* **the escaped overlap is 64 of 114** (F18: 63 of 110);
* both sanity-anchor sets still land on identical classes, and the ledger's own
  `new_failure` set has grown 7 → 11 with the four entrants in it.

⚠ **THE CLASS × BANKED VERDICT TABLE IS STILL A WITHIN-ERA TABLE ONLY** and
must not be diffed across eras, for PART I-F18 §I.5's reason (`80075d049a`
retired the `open_bus` accept rule).  On F19 it reads:

| banked verdict | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| `FUNCTIONAL` | 45 | 12 | 1 | 15 | 8 | 81 |
| `KNOWN_ACCEPTED` | 3 | 11 | 4 | 4 | 2 | 24 |
| `TIMING` | 1 | 7 | 0 | 0 | 1 | 9 |

## I.6 WHAT PART I LEAVES OPEN

1. **The 11 UNSCOREABLE seeds** — unmoved for a third era, still all `raw` and
   all escaped; the instrument fix is still *a terminator that survives an
   escaped program*.
2. **The six `arch: NODUMP` / census-has-both-dumps seeds** (§I.2) — two
   derivations of the same quantity disagree, and neither is wrong on its own
   terms.  Booked with the seeds named.
3. **phantom-T1's one remaining `bs` cell** — unchanged from PART I-F18 §I.6.
4. **The honesty clause's blind spot is unchanged**: the dump-identity proof
   covers 15 registers at the end of the run and nothing else.
5. **The residue is still mostly material — 79 of 114 (69.30 %)**, and the
   share rose from 68.18 % only because four MATERIAL seeds entered.  **No seed
   became more material by being re-read.**

---
---

# PART I-F18 — FLASH #18.  ⚠ **SUPERSEDED 2026-08-12 BY PART I (FLASH #19).  HISTORY, NOT A CLAIM.**

**Everything below this line to the PART II divider is the FLASH #18-era
census, retained byte-for-byte as it was registered**, apart from this heading
and the two anchor comments, which are renamed `CENSUS-PARTITION-F18-BEGIN/END`
so that exactly one LIVE anchor pair exists in the file.  Its sections are
numbered `I.x`, as they were when it was live; **a bare `§I.x` reference inside
this block means this block's.**

    re-derived 2026-08-11 under `docs/notes/fz2_f18_housekeeping_prereg_2026-08-11.md`,
    which was committed at `a05af666aa` BEFORE this run.
    results     docs/notes/fz2_f18_housekeeping_results_2026-08-11.md

**WHY THIS PART EXISTS.**  FLASH #18 landed `KM` and `phantom-T1`
(`fz2_flash18_results_2026-08-11.md`).  Three seeds LEFT the ledger and none
entered, so the population this census partitions moved **113 → 110** — and
`fz2_immaterial falsify` reported **G6 and G7 FAIL** against PART II for
exactly that reason.  The F18 sitting **booked the re-derivation rather than
doing it in the sitting that measured the failure**, because editing a document
to clear its own falsifier in the same sitting is the move this campaign's
rules distrust.  This is that re-derivation.

## I.0 THE PARTITION — THE REGISTERED CELLS

    C-ROW   diff_rows reproduces the ledger   110 / 110   PASS
    C-ARCH  arch_dump reproduces the ledger   110 / 110   PASS
    exit 0

<!-- CENSUS-PARTITION-F18-BEGIN -->

| class | seeds | % of 110 | % of 3,839 |
|---|---:|---:|---:|
| **FUNCTIONAL** — the architectural result differs | **45** | 40.91 % | 1.17 % |
| **TIMING** — dumps identical, the bus schedule differs | **30** | 27.27 % | 0.78 % |
| **TRANSIENT** — dumps identical, schedule identical, a cycle-defining pin moved | **5** | 4.55 % | 0.13 % |
| **COSMETIC** — dumps identical, schedule identical, value-only diffs | **19** | 17.27 % | 0.49 % |
| **UNSCOREABLE** — neither leg dumped; no proof either way | **11** | 10.00 % | 0.29 % |

    MATERIAL    (functional + timing)   75 / 110 = 68.18 %   =  1.95 % of 3,839
    IMMATERIAL  (transient + cosmetic)  24 / 110 = 21.82 %   =  0.63 % of 3,839
    UNPROVEN    (no dump either leg)    11 / 110 =  9.99 %   =  0.29 % of 3,839

    TIMING (30), split by whether the program's total length moved:
        a bus cycle starts on a clock the other leg has none : 30
        done-marker clock differs, cycle starts all match    :  0
        unmatched cycle STARTS per seed: min 1  median 97  max 433
        done-marker clock IDENTICAL (local re-schedule only) :  8
        done-marker clock MOVED (total run length changed)   : 22
        no done marker on one or both legs                   :  0
        |done-clock delta| over the 22 that moved: min 1  median 3  max 715 clocks

<!-- CENSUS-PARTITION-F18-END -->

⚠ The `9.99 %` on the UNPROVEN line is the tool's `10.00 %` restated to one
more place only where rounding makes `21.82 + 68.18 + 10.00` read as exactly
100; the parsed cells are the **counts**, and no percentage is parsed.

**The headline the user asked for, on FLASH #18: of the 110 residual seeds, 24
have no measured consequence at all, 11 cannot be asked, and 75 do.**  Read
against the corpus, **3,753 of 3,839 seeds (97.76 %) either match the chip
outright or differ in a way with no measured functional or timing
consequence**; 75 (1.95 %) carry one; 11 (0.29 %) cannot be adjudicated.

⚠ **The residue did not shrink *by this document*.**  It shrank because three
seeds left the ledger in fabric; this is still a lens, not a re-score.  Every
seed below is still a ledger failure, `bars` is untouched, and no gate moved.

## I.1 WHAT MOVED, F17 → F18, CELL BY CELL

| cell | F17 | **F18** | Δ | why |
|---|---:|---:|---:|---|
| FUNCTIONAL | 48 | **45** | −3 | **KM's three seats LEFT the ledger** — `fz2c/404041`, `fz2e/501066`, `fz2e/513019`, all three two-sided FUNCTIONAL at F17 (PART II §4.1), `bad_rows` 2,437 / 572 / 2,843 → **0** |
| TIMING | 33 | **30** | −3 | **phantom-T1's three seats moved TIMING → TRANSIENT** |
| TRANSIENT | 2 | **5** | +3 | the same three, at `bs=1` |
| COSMETIC | 19 | **19** | 0 | unmoved, seed for seed |
| UNSCOREABLE | 11 | **11** | 0 | unmoved, seed for seed |
| **total** | **113** | **110** | −3 | LEFT 3 / ENTERED 0 |
| **IMMATERIAL** | **21** | **24** | +3 | zero leavers |
| `TIMING_RECONVERGED` | 7 | **8** | +1 | **`fz2e/530020` joined**, §I.4 |

**Six of G6's eight cells moved, which is exactly the `6 / 8` the FLASH #18
sitting measured** (`fz2_flash18_results_2026-08-11.md` §4.7a) — COSMETIC and
UNSCOREABLE are the two that agreed.

## I.2 THE THREE NEW TRANSIENT SEEDS — phantom-T1's SEATS

| seed | family | `bad_rows` F17 → F18 | first_bad | window | cyc chip/core | done chip/core | columns |
|---|---|---:|---:|---:|---|---|---|
| `fz2c/404071` | C2 INTA-vectored delivery | 905 → **1** | **243** | 1,204 | 174 / 174 | 1196 / 1196 | `bs`=1 |
| `fz2e/514044` | C2 INTA-vectored delivery | 1,261 → **1** | **234** | 1,587 | 233 / 233 | 1579 / 1579 | `bs`=1 |
| `fz2e/516001` | C2 INTA-vectored delivery | 1,154 → **1** | **583** | 2,611 | 204 / 204 | 2603 / 2603 | `bs`=1 |

The `first_bad` values **243 / 234 / 583** are the FLASH #18 pre-registration's
own POINT predictions (results §4.2), reproduced here by an independent
instrument that never reads them.

**They are the third instrument to say the residue is one status cell**, beside
the fabric ledger and the HLT sweeps' `busstat: exp 'CODE' got 'PASV'`.
⚠ **They are DISPOSITIONED, NOT CLOSED**: `bad_rows == 0` was registered as a
FINDING and did not occur, and the remaining cell is the `system_large`
status-pin observation model the ack-wake landing booked and did not take
(results §9 OPEN item 6).

## I.3 CLASS × FAMILY, ON THE F18 LEDGER

| family | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| A1 qs-pop one clock late | 0 | 5 | 0 | 0 | 0 | 5 |
| A2 qs-pop other offset | 0 | 1 | 0 | 2 | 1 | 4 |
| A3 cycle-time slip (non-qs) | 4 | 6 | 1 | 4 | 0 | 15 |
| B1 HALT-cycle address | 0 | 1 | 0 | 0 | 0 | 1 |
| B2 HALT entry (one leg only) | 0 | 2 | 0 | 0 | 0 | 2 |
| C1 vector-1 trap MISSED by core | 0 | 0 | 0 | 0 | 1 | 1 |
| **C2 INTA-vectored delivery** | **6** | **0** | **3** | 0 | 0 | **9** |
| C3 NMI(vec2) entry | 1 | 0 | 0 | 0 | 0 | 1 |
| C4 other-vector delivery | 1 | 0 | 0 | 0 | 0 | 1 |
| D1 chip fetched, core did not | 7 | 3 | 0 | 0 | 0 | 10 |
| **D2 core fetched, chip did not** | **2** | **6** | 0 | 0 | 0 | **8** |
| D3 both fetched, different address | 4 | 1 | 0 | 0 | 0 | 5 |
| E1 same-status data cycle, different address | 19 | 4 | 1 | 10 | 5 | 39 |
| E2 different-status data cycle | 0 | 1 | 0 | 0 | 1 | 2 |
| NEW/UNCLASSIFIED | 1 | 0 | 0 | 3 | 3 | 7 |
| **TOTAL** | **45** | **30** | **5** | **19** | **11** | **110** |

**C2 is the row the two landings rewrote.**  At F17 it was 7 FUNCTIONAL /
3 TIMING / 0 immaterial and PART II §3.2 called it *"the densest material
family in the table"*.  It is now **6 / 0 / 3 immaterial of 9**: KM took one
FUNCTIONAL seat out of the ledger entirely and phantom-T1 moved all three
TIMING seats to TRANSIENT.  ⚠ **The remaining six are still there, and five of
the six are `soup`-tier and not escaped** — PART II §5's *"highest-confidence
functional residue"* reading is unchanged in kind and one seed shorter.

**D2 fell 10 → 8** (KM's `fz2c/404041` and `fz2e/501066`).
**Every other family row is byte-identical to PART II's**, which is the
containment check: neither landing touched a family it did not name.

## I.4 `TIMING_RECONVERGED` ON FLASH #18 — 8 SEEDS, AND THE USER RULING CARRIES

> **THE RULING STANDS, RE-STATED ON THIS ERA (user, 2026-08-11): "Timing
> reconvergence seeds are material."**  All **8** stay MATERIAL, all 8 are
> inside the 30 TIMING and inside the 86 working residue, and the sub-class
> remains a named lens (`fz2_immaterial.py reconverged`), not a disposition.
> **The ruling was given on a 7-seed membership and is re-derived here on an
> 8-seed one; it is a rule about a PREDICATE, not about a seed list, so it
> carries without re-asking.**

The F17 seven are **all still members, unmoved**, and one seed joined:

| seed | tier | esc | bad | starts chip-only / core-only | done (both) | family | F17? |
|---|---|---:|---:|---|---:|---|---|
| `fz2c/406073` | raw | 142 | 5 | 0 / 1 | 3599 | B2 HALT entry (one leg only) | yes |
| `fz2c/407064` | raw | 63 | 998 | 131 / 130 | 3583 | B1 HALT-cycle address | yes |
| `fz2e/511014` | soup | — | 744 | 97 / 95 | 3596 | D1 chip fetched, core did not | yes |
| `fz2e/512062` | soup | — | 504 | 60 / 61 | 3569 | D2 core fetched, chip did not | yes |
| `fz2e/518006` | raw | 87 | 479 | 6 / 7 | 3599 | E1 same-status data cycle | yes |
| `fz2e/518044` | raw | 69 | 5 | 0 / 1 | 3599 | B2 HALT entry (one leg only) | yes |
| `fz2e/520000` | raw | — | 836 | 13 / 12 | 3596 | E1 same-status data cycle | yes |
| **`fz2e/530020`** | raw | 15 | 326 | **3 / 3** | **1090** | D1 chip fetched, core did not | **NEW** |

⚠ **`fz2e/530020` IS NOT A SEAT AND WAS NOT PREDICTED BY MECHANISM.**  It is a
still-TIMING seed whose `done_delta` became 0; it stayed in the ledger, in
TIMING, and in the residue throughout, and only its position **inside** TIMING
moved.  This is the ordinary downstream row-count movement FLASH #18 reported
and did not explain — the corpus lost **345 rows more** than the six seats
alone account for (results §4.3 P-3a).  **Reported, not attributed.**
*Falsifier, registered here*: a double capture on one bitstream in which
`fz2e/530020`'s `done_chip`/`done_core` are stable — if they flicker, this
membership is capture noise and the count is not a ratchet.

## I.5 WHAT PART II'S NON-PARTITION SECTIONS STILL SAY, AND WHERE THEY DO NOT

Re-measured on the F18 ledger and **UNCHANGED from PART II**: the dump-proof
audit's shape (**23 of 110 without a two-sided dump — 12 one-sided → FUNCTIONAL,
11 neither → UNSCOREABLE**, 8 re-aligning and 3 diverging to the window end,
and **0 class-3/4 seeds classified without a dump proof**); the eleven
UNSCOREABLE seeds **seed for seed**, with their counterfactual now reading
`would be` TIMING 4 · TRANSIENT 1 · COSMETIC 6; the escaped overlap at **63 of
110**; and both sanity-anchor sets (F17's six new-at-F17 failures and the
ledger's own seven `new_failure` seeds) landing on identical classes.

⚠ **ONE PART II TABLE IS NOT COMPARABLE ACROSS THE ERAS AND MUST NOT BE
DIFFED — §8, class × BANKED VERDICT.**  On F18 it reads `FUNCTIONAL` 78 ·
`KNOWN_ACCEPTED` 23 · `TIMING` 9 against PART II's 16 · 94 · 3.  **That is not
a measurement of either landing.**  `80075d049a` retired the `open_bus` accept
rule and is **not** an ancestor of the FLASH #17 flash commit, so seeds
previously labelled `KNOWN_ACCEPTED / open_bus` are now labelled `FUNCTIONAL`
with **byte-identical rows and dumps** (`fz2_flash18_results_2026-08-11.md`
§3.2).  **No class in this census depends on `verdict`** — every one is
assigned from dump identity and row alignment — so the partition is unaffected
and the §8 table alone is unreadable across the pair.  It is reproduced here
for the F18 era **as a within-era table only**:

| banked verdict | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| `FUNCTIONAL` | 42 | 12 | 1 | 15 | 8 | 78 |
| `KNOWN_ACCEPTED` | 2 | 11 | 4 | 4 | 2 | 23 |
| `TIMING` | 1 | 7 | 0 | 0 | 1 | 9 |

## I.6 WHAT PART I LEAVES OPEN

1. **The 11 UNSCOREABLE seeds** — unmoved, still all `raw` and all escaped, and
   the instrument fix is still *a terminator that survives an escaped program*.
2. **`fz2e/530020`'s reconvergence is unattributed** (§I.4), with its falsifier
   registered above.
3. **phantom-T1's one remaining `bs` cell** — the `system_large` status-pin
   observation model, to be measured as its own mechanism with its own G6.
4. **The honesty clause's blind spot is unchanged**: the dump-identity proof
   covers 15 registers at the end of the run and nothing else.
5. **The residue is still mostly material — 75 of 110 (68.18 %).**  The share
   fell from 71.68 % only because three FUNCTIONAL seeds left and three TIMING
   seeds were dispositioned; **no seed became less material by being
   re-read.**

---
---

# PART II — FLASH #17.  ⚠ **SUPERSEDED 2026-08-11 BY PART I.  HISTORY, NOT A CLAIM.**

**Everything below this line is the FLASH #17-era census, retained byte-for-byte
as it was registered.**  Its population is 113 seeds against era sof
`26c19f613e2caae8…` and ledger `fz2_failure_ledger_f17_2026-08-11.json`; the
live population is 110 against `b2a1fe5f8316…`.  **None of its tables is inside
the G6 anchors, and none of its numbers may be quoted against this tree** — a
census figure is only readable against its own ledger, exactly as a fabric
figure is only readable against its own bitstream.  It is kept because a
ratchet is only readable against its own history, and because PART I's §I.1
delta table is meaningless without it.

---

## 0. THE QUESTION, AND THE ANSWER IN ONE TABLE

The user asked, verbatim:

> "How many of these divergences have impacts on functionality or timing. An
> address value being presented on the bus that is never used does not impact
> functionality or timing, for instance. A pin changing state slightly earlier
> or later is not significant if it doesn't change the overall timing."

The failure ledger counts **seeds that differ**. It has never said what the
difference **costs**. This document partitions its 113 entries into measured
consequence classes.

| class | seeds | % of 113 | % of 3,837 |
|---|---:|---:|---:|
| **FUNCTIONAL** — the architectural result differs | **48** | 42.48 % | 1.251 % |
| **TIMING** — dumps identical, the bus schedule differs | **33** | 29.20 % | 0.860 % |
| **TRANSIENT** — dumps identical, schedule identical, a cycle-defining pin moved | **2** | 1.77 % | 0.052 % |
| **COSMETIC** — dumps identical, schedule identical, value-only diffs | **19** | 16.81 % | 0.495 % |
| **UNSCOREABLE** — neither leg dumped; no proof either way | **11** | 9.73 % | 0.287 % |

    MATERIAL    (functional + timing)   81 / 113 = 71.68 %   =  2.111 % of 3,837
    IMMATERIAL  (transient + cosmetic)  21 / 113 = 18.58 %   =  0.547 % of 3,837
    UNPROVEN    (no dump either leg)    11 / 113 =  9.73 %   =  0.287 % of 3,837

**The headline the user asked for: of the 113 residual seeds, 21 have no
measured consequence at all, 11 cannot be asked, and 81 do.** Read against the
corpus, **3,745 of 3,837 seeds (97.60 %) either match the chip outright or
differ in a way with no measured functional or timing consequence**; 81
(2.11 %) carry one; 11 (0.29 %) cannot be adjudicated.

⚠ **The residue did not shrink.** This is a lens, not a re-score. Every seed
below is still a ledger failure, `bars` is untouched, and no gate moved.

---

## 1. HOW EACH CLASS IS DECIDED — OPERATIONAL DEFINITIONS

A seed takes the **most material** class it qualifies for.

**FUNCTIONAL.** Both legs produced a 15-word `MAGIC`-anchored terminator dump
and the dumps differ in any word — or exactly one leg produced a dump at all.
The 15 words are `AW BW CW DW BP IX IY SP PC PS PSW DS0 DS1 SS MAGIC`.

**TIMING.** Dumps identical, but the **schedule** differs. Measured in the
**clock domain, not the cycle-index domain**: a bus cycle *starts* on a clock
in one leg where the other leg starts none, or the two legs reach the done
marker on different clocks. The clock-domain formulation is deliberate — a
cycle-index comparison cannot tell an inserted cycle apart from a shifted one,
because one insertion offsets every later index. (Both formulations were
computed; they agree on the boolean for all 113, with an index-paired final
offset of exactly 0 on all 34 seeds the clock-domain test calls unchanged.)

**TRANSIENT.** Dumps identical, **every** bus cycle in the window starts on the
same clock in both legs, and at least one diff lands on a cycle-defining column
(`t`, `bs_early`).

**COSMETIC.** Dumps identical, every bus cycle starts on the same clock, and
every diff is a value on `ad_addr` / `ad_data` / `ps` / `qs` / `ube_n` at a
matched position.

**UNSCOREABLE.** Neither leg produced a dump. Classes 3 and 4 rest on a
**dump-identity proof of non-propagation**; without a dump there is no proof,
so these seeds are reported separately and never forced into a class.

The TRANSIENT / COSMETIC boundary is the only judgement call in the tool, and
it lives in exactly one place: `CYCLE_DEFINING = ("bs", "t")` versus
`VALUE_ONLY = ("addr", "data", "nxta", "ps", "ube", "qs")`.

### 1.1 The two controls, run on every invocation

A lens that reads the rows differently from the scorer is measuring its own
parser. Both controls are checked before anything is classified, and a failure
of either makes the census unquotable (exit 2):

| control | what it re-derives | result |
|---|---|---|
| **C-ROW** | `fuzz_classify.diff_rows(real, sim, window=line["win"])` must reproduce the ledger's `first_bad_row`, `diverging_rows`, `compare_window` | **113 / 113 PASS** |
| **C-ARCH** | `fuzz_classify.arch_dump(rows, len(rows), sentinel_only=True)` — `fuzz_campaign.eval_case`'s own parameters — must reproduce the banked `arch_words` and `arch_sim_words` | **113 / 113 PASS** |

### 1.2 The row source, and what it does to the F17 §8 caveat

The brief asked for the offline-replay bias to be bounded. **It does not apply
here, because there is no replay in the loop.** `fuzz_campaign.capture_board`
banks BOTH legs from the board: `real` = `run_chip(use_core=False)`, the socket
leg (the real µPD70116); `sim` = `run_chip(use_core=True)`, the fabric ucore.
Both are FLASH #17 silicon captures of the same image under the same directive,
4,063 rows each. `fz2_flash17_results` §5.3's one-sided +1..+5 row under-count
is a property of the **offline replay**, which this tool never calls.

The cost of that choice: the census can only be taken where the capture was
banked. For the 113 failures that is **113 of 113**, each verified by sha256
against the ledger before it was read.

### 1.3 What is *not* measured, stated so it is not assumed

* The capture is a **fixed 4,063-row window on both legs**, so the brief's
  first TIMING probe — "total row counts differ" — is never true on this
  population and carries no information. Its usable equivalent is the
  **done-marker clock** (`_done_idx`), and that *is* scored.
* Everything is measured inside the ledger's own compare window `win`. A
  schedule change beyond it is not seen.
* `family` is **carried forward** from the ledger and never re-derived —
  `fz2_ledger`'s rule for `fz2_ledger`'s reason (§38.9: the partition is a
  record of how the bus structure classified each seed, not a re-reading).
* **Nothing here says whose fault a divergence is.** See §5.

---

## 2. (a) BY CONSEQUENCE CLASS — THE DETAIL

### 2.1 TIMING (33), split by whether the program's total length moved

    a bus cycle starts on a clock the other leg has none : 33
    done-marker clock differs, cycle starts all match    :  0
    unmatched cycle STARTS per seed: min 1  median 103  max 433

The user's criterion is **overall** timing, so the census separates the seeds
whose local schedule moved from the ones whose **total run length** also moved:

    done-marker clock IDENTICAL (local re-schedule only)  :  7
    done-marker clock MOVED (total run length changed)    : 26
    no done marker on one or both legs                    :  0
    |done-clock delta| over the 26 that moved: min 1  median 2  max 715 clocks

⚠ **Both halves stay TIMING.** A bus cycle that exists in one leg and not the
other is a schedule difference whatever the total comes to — the bus is
occupied on a clock where the other leg's is free, which is visible to any
device sharing it. The **7** seeds where the program still finished on exactly
the same clock are the weakest members of the material set and are flagged as
such; the median cost of the other 26 is **2 clocks**, and one seed
(the 715-clock outlier) dominates the tail.

### 2.2 TRANSIENT (2) — both named, because two is small enough to read

| seed | family | what moved |
|---|---|---|
| `fz2e/513026` | A3 cycle-time slip | **one row**, `bs PASV != CODE`, at row 543 of a 544-row window — the core announces the next fetch's status one clock before the chip, on the last compared clock. All 103 bus cycles start on identical clocks; dumps identical. This is the user's "pin changing state slightly earlier", exactly. |
| `fz2c/408021` | E1 same-status data cycle | **a two-cycle REORDER.** Both legs run 261 cycles, all starting on identical clocks, and both perform the same `MEMW` to `0x777dc` and the same `CODE` fetch of `0x881a2` — **in the opposite order**, in the same two slots. 12 `bs` rows, 20 `ube` rows, dumps identical, done marker identical at 1459. |

`fz2c/408021` is reported as TRANSIENT under the stated rule (cycle-defining
column, no schedule change) but it is **not** the "1–2 isolated rows" shape the
brief describes, and it is named here so it is not absorbed silently. It is a
real ordering difference between a write and a fetch that costs nothing
measurable: same clocks, same cycles, same architectural result.

### 2.3 COSMETIC (19) — and the ghost-read signature

Column totals over the 19: `data=72, nxta=25, addr=25, qs=5`. **Not one `t` or
`bs` row among them.**

**Eleven of the nineteen** carry an identical 2-row or 4-row signature —
`nxta=1, addr=1, data=2` (or `addr=1, nxta=1` where the data phase agrees).
That is **the ghost read, drawn in full**: the core drives a different address
on the T1 (`addr`) and on the preceding next-address phase (`nxta`), reads back
whatever that address answers with (`data`, both data-phase rows), the cycle
starts and ends on the same clocks as the chip's, and **the 15-word dump is
bit-identical**. The dump identity is the direct measurement that the fetched
value never propagated — it is not an argument that it could not.

**Five more are the same signature repeated** over 2–8 instances
(`fz2c/409065` 16 rows, `fz2e/521049` 14, `fz2e/522029` 32, `fz2e/525017` 12,
`fz2e/529009` 8 — the last is data-only, the address agreed) and **three
(`fz2e/515056`, `fz2e/516029`, `fz2e/532032`) are pure `qs` diffs**: 1–2 rows
of queue-status pin, no bus effect at all. 11 + 5 + 3 = 19.

### 2.4 UNSCOREABLE (11) — and their counterfactual

All eleven are `raw` tier, all escaped, none produced a dump on either leg.

| seed | bad rows | first_bad | trailing clean | *would be* | mech |
|---|---:|---:|---:|---|---|
| `fz2c/406006` | 16 | 478 | 3,501 | COSMETIC | STALLED |
| `fz2c/406063` | 3,149 | 245 | 0 | TIMING | LONG_INSN |
| `fz2e/518039` | 1,587 | 2,363 | 0 | TIMING | STALLED |
| `fz2e/520066` | 8 | 1,249 | 2,743 | COSMETIC | STALLED |
| `fz2e/521006` | 9 | 368 | 3,623 | COSMETIC | STALLED |
| `fz2e/524007` | 2,257 | 319 | 750 | TIMING | BUDGET |
| `fz2e/529034` | 2,340 | 1,069 | 0 | TIMING | LONG_INSN |
| `fz2e/529058` | 8 | 1,792 | 2,197 | COSMETIC | STALLED |
| `fz2e/529067` | 16 | 611 | 3,369 | TRANSIENT | LONG_INSN |
| `fz2e/530001` | 20 | 442 | 3,531 | COSMETIC | LONG_INSN |
| `fz2e/534003` | 4 | 564 | 3,432 | COSMETIC | STALLED |

⚠ **The `would be` column is a COUNTERFACTUAL, not a verdict**, and no seed is
promoted by it. It says: *if* a dump existed and *if* it were identical, this is
the class the row evidence would put the seed in. Seven of the eleven would be
immaterial and four would be TIMING. **They are counted as UNPROVEN in every
figure in this document.**

Eight of the eleven re-align before the window ends (≥ 64 clean trailing rows);
three (`fz2c/406063`, `fz2e/518039`, `fz2e/529034`) diverge to the last
compared row.

---

## 3. (b) CONSEQUENCE CLASS × MECHANISM FAMILY

Family labels are the ledger's A-15 partition, carried forward unmodified.

| family | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| A1 qs-pop one clock late | 0 | 5 | 0 | 0 | 0 | 5 |
| A2 qs-pop other offset | 0 | 1 | 0 | 2 | 1 | 4 |
| A3 cycle-time slip (non-qs) | 4 | 6 | 1 | 4 | 0 | 15 |
| B1 HALT-cycle address | 0 | 1 | 0 | 0 | 0 | 1 |
| B2 HALT entry (one leg only) | 0 | 2 | 0 | 0 | 0 | 2 |
| C1 vector-1 trap MISSED by core | 0 | 0 | 0 | 0 | 1 | 1 |
| C2 INTA-vectored delivery | 7 | 3 | 0 | 0 | 0 | 10 |
| C3 NMI(vec2) entry | 1 | 0 | 0 | 0 | 0 | 1 |
| C4 other-vector delivery | 1 | 0 | 0 | 0 | 0 | 1 |
| D1 chip fetched, core did not | 7 | 3 | 0 | 0 | 0 | 10 |
| D2 core fetched, chip did not | 4 | 6 | 0 | 0 | 0 | 10 |
| D3 both fetched, different address | 4 | 1 | 0 | 0 | 0 | 5 |
| **E1 same-status data cycle, different address** | **19** | **4** | **1** | **10** | **5** | **39** |
| E2 different-status data cycle | 0 | 1 | 0 | 0 | 1 | 2 |
| NEW/UNCLASSIFIED | 1 | 0 | 0 | 3 | 3 | 7 |
| **TOTAL** | **48** | **33** | **2** | **19** | **11** | **113** |

### 3.1 The ghost family (E1, 39) — the answer the brief asked for by name

**Of the 39 E1 "same-status data cycle, different address" seeds: 19
FUNCTIONAL, 4 TIMING, 1 TRANSIENT, 10 COSMETIC, 5 UNSCOREABLE.**

So **11 of 39 (28 %) are immaterial or arguably so, and 23 of 39 (59 %) are
material** — the family is **not** uniformly the harmless ghost address. Where
it is harmless it is cleanly harmless (the 10 COSMETIC seeds carry the 4-row
signature of §2.3 and nothing else); where it is not, the divergent address is
accompanied by a real architectural or schedule consequence. **A family label
is not a materiality claim, and this is the strongest instance of that in the
table.**

### 3.2 The other readable rows

* **A1 (qs-pop one clock late), 5 of 5 TIMING.** Every one carries an
  unmatched cycle start. A "qs pop one clock late" is not, on this population,
  confined to the queue-status pin.
* **A2, 3 of 4 immaterial.** Two are pure `qs` rows.
* **C2 (INTA-vectored delivery), 7 FUNCTIONAL / 3 TIMING, 0 immaterial** —
  the densest material family in the table, and **6 of its 7 FUNCTIONAL seeds
  are `soup` tier and not escaped**, i.e. the cleanest signal in the census.
* **D1 / D2 / D3 (a fetch one leg made and the other did not), 15 FUNCTIONAL /
  10 TIMING, 0 immaterial across all 25.** A prefetch difference is never free
  on this population.
* **B1 / B2 (HALT), 3 of 3 TIMING, 0 FUNCTIONAL.**

---

## 4. (c) EVERY FUNCTIONAL SEED, NAMED

48 seeds. `chip/core` per differing word. Ten of the 48 are dump-asymmetric —
one leg produced a terminator dump and the other did not — and those are listed
with their done-marker positions instead.

### 4.1 Both legs dumped, the dumps differ (36)

| seed | tier | escaped | family | differing words — chip/core |
|---|---|---:|---|---|
| `fz2c/404041` | soup | — | D2 | `BW` d895/5105 · `CW` 0000/0006 · `IY` a76b/2efb · `PC` 8b0c/c880 · `PS` 3f62/5f62 · `PSW` f183/f003 · `SP` 48e0/48da |
| `fz2c/405002` | soup | — | C2 | `BP` 9c52/8a6c |
| `fz2c/405013` | soup | — | C2 | `BW` f806/f903 · `IX` 7807/7904 |
| `fz2c/405072` | soup | — | C2 | `IY` 1e7b/1e7c |
| `fz2c/406046` | raw | 138 | A3 | `DW` 1af1/8fbd |
| `fz2c/406054` | raw | 42 | E1 | `AW` 64ff/0258 · `BW` d710/122d · `CW` 843d/4a95 · `DW` 7675/7676 · `IX` 6dc2/6dec · `IY` fb7e/fba5 · `PC` b755/9976 · `PS` b426/01e2 · `PSW` f203/f206 · `SP` a5f6/4a95 |
| `fz2c/407000` | raw | 39 | D1 | `PC` 908e/9090 |
| `fz2c/407036` | raw | — | D3 | `PC` 0932/0931 |
| `fz2c/408019` | raw | — | E1 | `BP` 7571/8dd5 · `IX` 8c3d/8c3c |
| `fz2c/410028` | raw | 76 | C3 | `PS` ffff/3617 |
| `fz2e/501066` | soup | — | D2 | `IX` f5ef/f1aa |
| `fz2e/501069` | soup | — | E1 | `AW` 00d9/50ff · `PC` f640/f647 · `PSW` f402/f406 |
| `fz2e/510043` | soup | — | E1 | `BW` 0001/ec22 · `IX` ae04/ad00 · `PC` d938/d93c |
| `fz2e/512056` | soup | — | C2 | `BP` 0969/f064 · `DW` bcea/0969 · `IY` f0e3/e768 |
| `fz2e/513019` | soup | — | C2 | `BW` 8a00/3e1a · `DS1` 6e58/9e58 · `DW` faff/ffff |
| `fz2e/516065` | soup | — | C2 | `CW` 2b6e/2b69 · `IX` 2b42/2b4c · `IY` 3080/308a · `PSW` f202/f206 |
| `fz2e/518022` | raw | 49 | E1 | `SP` df5e/b643 |
| `fz2e/518038` | raw | 39 | E1 | `BP` 8079/7262 |
| `fz2e/518050` | raw | 6 | E1 | `AW` 9ca7/ea2c · `CW` 6441/6442 · `IX` 4730/472e |
| `fz2e/518067` | raw | 49 | E1 | `IY` 3684/ff84 · `PSW` fa16/f297 |
| `fz2e/520005` | raw | — | D1 | `CW` 8645/8646 · `IX` 3f8e/3f8d · `IY` 9d44/9d43 |
| `fz2e/520013` | raw | 11 | D3 | `AW` 130a/f206 · `BP` f831/1c64 · `BW` fa58/7fd3 · `CW` bd2d/bd23 · `DW` fd5d/ffff · `IX` 4e86/f206 · `IY` 7eb9/2010 · `PC` be56/b447 · `PS` 7e48/9c48 · `PSW` f283/f213 · `SP` 3aa8/97bc · `SS` b343/48b3 |
| `fz2e/521016` | raw | — | D3 | `PC` 9091/0001 |
| `fz2e/521059` | raw | 30 | E1 | `CW` c775/cbda · `PSW` f282/f202 |
| `fz2e/522003` | raw | 46 | E1 | `BP` 7f2a/3949 · `CW` eaeb/eaec · `PC` f749/f74a · `PSW` f896/f082 · `SP` f98d/7d0d |
| `fz2e/524030` | raw | 155 | E1 | `AW` 5a03/5fd3 · `PC` f331/f337 · `PSW` f286/f202 |
| `fz2e/526054` | raw | — | E1 | `AW` b6d6/b688 · `PSW` f217/fa13 · `SS` 58fb/b9b8 |
| `fz2e/527037` | raw | — | E1 | `AW` ff07/ff37 · `PC` 9b5b/9b5a · `PSW` f202/f282 |
| `fz2e/527051` | raw | 31 | D3 | `AW` 5276/dbf9 · `BP` d577/bfa1 · `BW` f2cb/b4cb · `CW` 638c/e90d · `IX` cb49/4699 · `IY` a210/c051 · `PSW` fa83/f283 |
| `fz2e/531030` | raw | — | D1 | `CW` 18f1/18f0 · `IY` e710/e712 |
| `fz2e/531032` | raw | — | D2 | `CW` 5d57/5dd1 · `IY` b6cd/b5d9 |
| `fz2e/531039` | raw | 40 | A3 | `BW` 3558/34fc |
| `fz2e/532021` | raw | — | D1 | `CW` 90b8/90b7 · `IX` 8d80/8d82 · `IY` 2cbe/2cc0 |
| `fz2e/534041` | raw | 24 | NEW | `CW` b73c/14d5 · `SP` b443/b445 |
| `fz2e/534062` | raw | — | D2 | `CW` 970d/060d · `DW` 130a/ae0a · `PC` e514/ad8a · `PS` 9d8f/b562 · `PSW` f482/f617 · `SP` 6614/6620 |
| `fz2e/535027` | raw | — | E1 | `AW` eb11/93b3 · `BP` 4411/2a1f · `BW` 41a0/d24d · `CW` 650a/dfb3 · `DS1` 018d/3c93 · `DW` 2959/c7e6 · `IX` 0852/e34c · `IY` e065/0100 · `PC` 683a/3c96 · `PS` f18d/595d · `PSW` f282/f302 · `SP` 2632/0e2b |

### 4.2 Exactly one leg produced a dump (12)

| seed | tier | escaped | family | evidence |
|---|---|---:|---|---|
| `fz2c/407067` | raw | 44 | A3 | dump by CHIP only (done chip 3440 / core none) |
| `fz2c/409077` | raw | 251 | D1 | dump by CHIP only (done chip 3604 / core none) |
| `fz2c/410047` | raw | 43 | C2 | dump by CORE only (done chip none / core 3383) |
| `fz2e/518053` | raw | 3 | E1 | dump by CHIP only (done chip 992 / core none) |
| `fz2e/522019` | raw | 51 | E1 | dump by CHIP only (done chip 3563 / core none) |
| `fz2e/524034` | raw | 5 | E1 | dump by CORE only (done chip none / core 3150) |
| `fz2e/527065` | raw | — | A3 | dump by CHIP only (done chip 3858 / core none) |
| `fz2e/530046` | raw | 197 | D1 | dump by CHIP only (done chip 3617 / core none) |
| `fz2e/530070` | raw | 108 | C4 | dump by CHIP only (done chip 3617 / core none) |
| `fz2e/531018` | raw | 131 | E1 | dump by CORE only (done chip none / core 3539) |
| **`fz2e/532000`** | raw | — | D1 | ⚠ **BOTH legs wrote a done marker (3453 / 3450) and only the CHIP's 15-word `MAGIC`-anchored dump formed.** The core reached the terminator and did not complete the register store. |
| `fz2e/534060` | raw | — | E1 | dump by CORE only (done chip none / core 2468) |

### 4.3 What moved, across the 36 two-sided FUNCTIONAL seeds

    CW 15 · PSW 14 · IY 13 · PC 13 · IX 12 · BW 9 · AW 9 · SP 8 · BP 8
    DW 7 · PS 6 · DS1 2 · SS 2 · DS0 0

**11 of the 36 differ in exactly one word**, and **14 of 36 move `PC` or `PS`**
— i.e. the two legs ended at a different instruction. `DS0` never moved.

---

## 5. (d) THE ESCAPED OVERLAP — READ THIS BEFORE ATTRIBUTING ANYTHING

> ⚠ **CORRECTION, 2026-08-11 (same day, after the census was written).** This
> section was headed *"THE ESCAPED / OPEN-BUS OVERLAP"* and quoted F14 §4's
> *"an escaped program has no reproducible bus"* as its reason. **That reason is
> withdrawn** — there is no open bus on this rig (`hdl/rtl/test_mem.sv` decodes
> `addr[15:1]` and mirrors the image across the whole 1 MB space), so an escaped
> program's instruction stream **is** defined, on both legs. The erratum is
> `fz2_f14_results_2026-08-10.md` §4.1. **THE CENSUS'S CLASSIFICATION IS
> UNAFFECTED, AND THIS IS THE LOAD-BEARING POINT:** every class in §§1–4 is
> assigned from **dump identity and row alignment** — `arch_dump` equality, the
> clock-domain and cycle-index schedule tests, and the differing-column
> partition. **The escape is REPORTED beside the classes and is never an input
> to them.** No class count, control, rate or seed list in this document moves;
> what changes is the *reason* the escaped overlap is flagged as a caveat.

**63 of the 113 are escaped seeds** (`escaped_n > 0`).

| class | escaped | not escaped |  | soup | raw |
|---|---:|---:|---|---:|---:|
| FUNCTIONAL | 25 | 23 | | 10 | 38 |
| TIMING | 13 | 20 | | 15 | 18 |
| TRANSIENT | 1 | 1 | | 1 | 1 |
| COSMETIC | 13 | 6 | | 3 | 16 |
| UNSCOREABLE | **11** | **0** | | 0 | 11 |

⚠ **THE ESCAPED CLASS FLICKERS CAPTURE TO CAPTURE** (F14 §4, invoked again at
F17 §4.3a), so a divergence measured on one is weaker evidence about the core —
F17 §4.3a withdrew a seat-level claim for that reason, and F17 §4.3b then
refuted the obvious rule ("an escaped seed may not be a seat") because 7 of that
sitting's 8 registered seats were escaped. **So this is a caveat on attribution,
not an exclusion, and nothing in this document is adjusted for it.**

**As corrected above: the flicker is a MEASURED CORRELATION and its MECHANISM IS
UNPROVEN.** The standing hypothesis — chaotic path amplification, where one
row flip at the corpus's ~0.26 % noise floor early in a long garbage path
separates the two trajectories — is stated with its falsifier in
`fz2_f14_results_2026-08-10.md` §4.1 and **has not been run**. Do not cite this
section, or F14 §4, for a mechanism.

The practical consequence: **the highest-confidence functional residue is the
10 `soup`-tier, non-escaped FUNCTIONAL seeds** — `fz2c/404041`, `fz2c/405002`,
`fz2c/405013`, `fz2c/405072`, `fz2e/501066`, `fz2e/501069`, `fz2e/510043`,
`fz2e/512056`, `fz2e/513019`, `fz2e/516065`. **Six of those ten are family C2
(INTA-vectored delivery).** A further 13 are `raw` but not escaped. The
remaining 25 are escaped and carry the F14 §4 caveat.

**All 11 UNSCOREABLE seeds are escaped raw seeds.** The class is not scattered
across the corpus; it is concentrated exactly where the campaign already knows
the captures are least reproducible (corrected 2026-08-11: *"where the bus is
not reproducible"*, which asserted the withdrawn mechanism).

---

## 6. (e) SANITY ANCHORS — INCLUDING ONE THE BRIEF GOT HALF-RIGHT

### 6.1 The six new-at-F17 failures

The brief's anchor was: *the 6 new-at-F17 failures were measured
dump-bit-identical, so they should land in classes 2–4 or 5, not 1.*
F17 §4.3's own list of six, measured:

| seed | class | escaped | evidence |
|---|---|---:|---|
| `fz2e/521006` | UNSCOREABLE | 23 | no dump either leg; legs re-align (3,623 clean trailing rows) |
| `fz2e/521024` | COSMETIC | 60 | value-only, 4 rows (the ghost signature) |
| `fz2e/522002` | COSMETIC | 115 | value-only, 4 rows (the ghost signature) |
| **`fz2e/527051`** | **FUNCTIONAL** | 31 | `arch:AW,BP,BW,CW,IX,IY,PSW` |
| `fz2e/529058` | UNSCOREABLE | 79 | no dump either leg; legs re-align (2,197 clean trailing rows) |
| `fz2e/534003` | UNSCOREABLE | 4 | no dump either leg; legs re-align (3,432 clean trailing rows) |

**Five of six land where the anchor predicted. `fz2e/527051` does not, and the
anchor is misread rather than the measurement being wrong.** F17 §4.3's
"CORE dump IDENTICAL" is an **era-to-era** statement — the core's F17 dump is
bit-identical to its F16 dump — while its CHIP dump **MOVED** between eras
(§4.3a). This census compares **CHIP vs CORE within F17**, and finds them
different. **The ledger's own `arch` column agrees, verbatim:
`"AW,BP,BW,CW,IX,IY,PSW"`.** So this is not a new finding and not a
contradiction; it is the same seed read on a different axis, and its class is
correct as printed. It remains the seed F17 §4.3a already withdrew from
seat-level use.

### 6.2 The ledger's own `new_failure` flag is a *different* set

The ledger derives `new_failure` against the **F13-era committed ledger**, not
against F16, and it names **seven**: the five above (excluding `fz2e/527051`,
which carries a family and so is not "new" to F13) plus `fz2e/532032`
(**COSMETIC**, 2 `qs` rows) and `fz2e/534041` (**FUNCTIONAL**, `CW`+`SP`, the
seed F16 §5.4 already handled under the same escaped-seed caveat). Both sets are
printed by the tool, because quoting one under the other's name is how an anchor
stops anchoring.

---

## 7. (f) THE DUMP-PROOF AUDIT — THE HONESTY CLAUSE

    seeds with a TWO-SIDED dump (the proof is available): 90 / 113
    seeds WITHOUT one                                   : 23 / 113
        exactly one leg dumped :  12  -> FUNCTIONAL (the asymmetry IS the divergence)
        neither leg dumped     :  11  -> UNSCOREABLE (no proof either way)
            legs re-align before the window ends : 8
            rows diverge to the window end       : 3
    class-3/4 seeds classified WITHOUT a dump proof: 0   (0 by construction)

**The non-propagation proof used by COSMETIC and TRANSIENT holds only where
both legs dump. It is available on 90 of 113 and unavailable on 23**, and no
seed was classified immaterial without it.

⚠ **What the proof does and does not cover.** It is measured on the 15 words
the terminator dumps: `AW BW CW DW BP IX IY SP PC PS PSW DS0 DS1 SS MAGIC`. A
divergence that changed only memory the program never re-read, or a register
the terminator's own prologue overwrites before the store, would be invisible
to it. **COSMETIC therefore means "no architectural consequence was observed on
15 registers at the end of the run", not "provably none exists."**

---

## 8. (h) THIS CENSUS'S CLASS × THE CAMPAIGN'S OWN BANKED VERDICT

⚠ **The word FUNCTIONAL means two different things in this repo and the table
exists to say so.** `fuzz_classify` calls a seed FUNCTIONAL when the **bus
transaction stream** diverges — a write, a read address, or an INTA position
the other leg did not produce. This census calls a seed FUNCTIONAL when the
**architectural result** diverges. A read at a different address whose value
never reaches a register is the first and not the second, **and that gap is
precisely the user's question.**

| banked verdict | FUNC | TIME | TRAN | COSM | UNSC | tot |
|---|---:|---:|---:|---:|---:|---:|
| `FUNCTIONAL` | 11 | 4 | 0 | **1** | 0 | 16 |
| `KNOWN_ACCEPTED` | **37** | 26 | 2 | 18 | 11 | 94 |
| `TIMING` | 0 | 3 | 0 | 0 | 0 | 3 |

Two rows read against each other:

* **One seed the campaign calls `FUNCTIONAL` is COSMETIC here** —
  `fz2e/517046`, banked `func:R@29`: a read at a different address, 2 diff rows
  (`addr`, `nxta`), 251 bus cycles starting on identical clocks in both legs,
  done marker identical at 1,489, and a **bit-identical 15-word dump**. The bus
  stream diverged; the machine's state did not.
* **37 seeds the campaign calls `KNOWN_ACCEPTED` are FUNCTIONAL here.**
  `KNOWN_ACCEPTED` means *a named accept rule covers this signature*, not
  *nothing happened*. Twenty-five of the 37 are escaped (§5), which is where
  most of those accept rules come from; **12 are not**. Neither column is
  wrong — they answer different questions — but a reader who takes
  `KNOWN_ACCEPTED` to mean "immaterial" is reading it wrong, and this row is
  the measurement of by how much.

---

## 9. SURPRISES, AND WHAT THIS LEAVES OPEN

1. **The residue is mostly material — 81 of 113 (71.68 %).** The prior
   expectation implicit in the brief (that the ghost-address family would carry
   most of the residue harmlessly) is **not** what the data says.
2. **The E1 ghost family splits 19 FUNCTIONAL / 4 TIMING / 1 TRANSIENT /
   10 COSMETIC / 5 UNSCOREABLE.** Only about a quarter of it is the harmless
   ghost address. **A family label is not a materiality claim.**
3. **Every one of the 25 D1/D2/D3 prefetch-asymmetry seeds is FUNCTIONAL or
   TIMING — none is immaterial.** A fetch one leg made and the other did not
   always costs something on this population.
4. **All 11 UNSCOREABLE seeds are escaped raw seeds**, and 7 of the 11 would be
   immaterial if a dump existed. The single cheapest way to shrink the
   unadjudicated set is a terminator that survives an escaped program.
5. **7 of the 33 TIMING seeds finish on exactly the same clock** — their
   schedule differs mid-run and re-converges. They are the weakest material
   seeds in the census and would be the first to re-classify under a stricter
   reading of "overall timing".
6. **`fz2e/532000` is a shape nothing else in the census has**: both legs wrote
   a done marker, three clocks apart, and only the chip's 15-word dump formed.
   Booked, not explained.
7. **The clock-domain and cycle-index schedule tests agree on all 113.** That
   was not guaranteed — the index test conflates insertion with shift — and it
   means the census's TIMING boundary is not an artifact of which formulation
   was chosen.

**Nothing here is a fix, a gate, or a verdict.** No seed left the ledger, no
rate moved, `bars` was not run and did not need to be. The one actionable
reading is §5's: **the highest-confidence functional residue is 10 soup-tier,
non-escaped seeds, six of them family C2 (INTA-vectored delivery)** — which is
where a mechanism hunt would start if one is wanted.
