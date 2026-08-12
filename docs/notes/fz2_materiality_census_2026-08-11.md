# fz2 MATERIALITY CENSUS — WHAT THE FLASH #17 RESIDUE ACTUALLY COSTS

    tool        sw/fz2_materiality.py           (reviewer-re-runnable, offline)
    input       sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
                + the 113 banked FABRIC captures it names, sha256-verified
    branch      fuzz-v2-on-relanding @ 1ad5074ebe
    era         sof 26c19f613e2caae8…  (FLASH #17)
    date        2026-08-11
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.

    reproduce   python3 sw/fz2_materiality.py
                python3 sw/fz2_materiality.py --seed fz2e/517046   (one seed)

⚠ **THIS IS A FLASH #17-ERA SNAPSHOT AND ITS NUMBERS ARE SUPERSEDED BY FLASH
#18.**  On the F18 ledger the derivation is **110 failures / 24 IMMATERIAL /
residue 86** (45 FUNCTIONAL + 30 TIMING + 11 UNSCOREABLE), against this
document's 113 / 21 / 92.  `fz2_immaterial falsify` therefore reports **G6 and
G7 FAIL** against this file — every clause that tests the *derivation itself*
(G1–G5, G8) still PASSES.  **The three seeds that entered the class are
phantom-T1's three seats** (`fz2c/404071`, `fz2e/514044`, `fz2e/516001`), now
`TRANSIENT` at a single `bs=1` column.  `fz2_flash18_results_2026-08-11.md`
§4.7a.

**THE RE-DERIVATION IS BOOKED AND WAS DELIBERATELY NOT DONE IN THE SITTING THAT
MEASURED THE FAILURE** — editing a document to clear its own falsifier in the
same sitting is the move this campaign's rules distrust.  This banner is a
LABEL, not a fix: it does not and cannot make G6/G7 pass.

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
