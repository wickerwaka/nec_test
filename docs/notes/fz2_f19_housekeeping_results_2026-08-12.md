# RESULTS — THE OWED OFFLINE LEGS OF THE GHOST LAUNCH RELOCATION, AND THE F19 ERA RE-PIN

    branch      fuzz-v2-on-relanding
    base        29a512f663  (FLASH #19 results banded; relocation merged at ef19010e63)
    prereg      docs/notes/fz2_f19_housekeeping_prereg_2026-08-12.md  @ 6e91923853
                docs/notes/ghost_launch_landing_prereg_2026-08-12.md  @ 4f33ff4685
    date        2026-08-12
    board       NOT TOUCHED.  No capture, no flash, no socket command, no
                Quartus compile.  Offline throughout.

    tb_sys      base  receipt 85c720c19ee47c29…   hdl/tb/obj_dir_sys/Vtb_sys
                ret   receipt abd3c4be9b566fd8…   hdl/tb/obj_dir_sys_ret/Vtb_sys
                (both REBUILT here through `x1_retention.py build`; the
                relocation moved four RTL files and the receipted binaries
                predated them, so `fz2_replay` REFUSED to run — correctly)

This sitting discharges the three legs the relocation landing declared OWED
(`ghost_launch_landing_prereg_2026-08-12.md` §5) and re-pins the two
materiality documents to the FLASH #19 era.  It contains **one loud deviation
from a registered prediction** (§2.3) and **one measured regression** (§3.4);
both gate FLASH #20 and are stated first in §0.

---

## §0 THE FIVE HEADLINES

1. **THE HOLDOUT UNSEAL IS CLEAN ON ITS FOUR REGISTERED BARS AND ITS BAND RULE
   IS REFUTED.** H-1 (zero closures) **MET**, H-2 (the twelve cascade-bound do
   not close) **MET**, H-3 (lost = 0) **MET**, H-4 (≥ 1 strict decrease)
   **MET at 3 of 15**.  But **all three improvers came from the CASCADE-BOUND
   class and both "closure plausible" seats are FLAT** — the `diverging_rows`
   band that generated the predictions has **no measured discriminating power
   on this population**.  §3.
2. **ONE HOLDOUT SEAT GOT WORSE**: `fz2c/406063`, `bad_rows` 3,149 → 3,165
   (+16) with `first_bad` 245 → 249.  No registered clause permits a holdout
   seat to regress.  **FINDING.**  §3.4.
3. **THE CORPUS-WIDE REPLAY DEVIATES FROM §3.1's "E1 FAMILY ONLY".**  0 lost
   and 0 first_bad earlier — both MET — but the 28 moved seeds span **eight**
   ledger families, not one, and there are **3 unregistered CLOSURES**
   (`fz2e/521024`, `fz2e/522002`, `fz2e/534003`).  §2.
4. **THE F19 ERA RE-PIN HIT ITS POINT PREDICTION ON ALL EIGHT G6 CELLS**, the
   24 IMMATERIAL members are unmoved cell for cell, `falsify` **exits 0 with
   G1–G8 PASS**, and it is demonstrated to FAIL on four perturbations and to
   IGNORE a fifth applied to the superseded history.  §4.
5. **THE `fz2c/404049` QUESTION IS ANSWERED AND IS NOT A FINDING.**  **111 of
   111** F18-pinned capture files moved, not six — because FLASH #19
   re-captured the whole corpus.  Exactly **7** seeds moved a SCORED field,
   and they are exactly the F19 sitting's six registered movers plus its one
   registered falsifier firing.  §5.

---

## §1 THE TWO GUARDS THAT REFUSED, AND WHY BOTH WERE RIGHT

Both owed legs were blocked on arrival, by guards doing their job.

**(a) `fz2_replay` — the artifact receipt layer.**  The `tb_sys` binaries were
built before the relocation, so their declared inputs no longer hashed to the
tree and the layer refused to run them.  **Fixed the only legal way: rebuilt
through the documented `build()`**, receipts above.  No `--force`, no bypass.

**(b) `fz2_replay` — the FABRIC ERA GUARD.**  It refuses to score an offline
replay of RTL that is not the RTL in the socket, and it named the four files:

    its inputs  84/88 hash IDENTICAL in the tree at HEAD
      MOVED     hdl/rtl/ucore/v30_core.sv       <-- RTL
      MOVED     hdl/rtl/ucore/v30u_biu.sv       <-- RTL
      MOVED     hdl/rtl/ucore/v30u_eu.sv        <-- RTL
      MOVED     hdl/rtl/ucore/v30u_ss_pkg.sv    <-- RTL

**`--no-fabric-era-guard` was used, and this is the sentence beside the number
the guard's own message demands.**  The relocation RTL is AHEAD of FLASH #19's
bitstream by exactly those four files and by nothing else; the whole point of
this leg is to ask what that RTL does against banked silicon rows, which is a
statement about two trees and is labelled as one.  **Every number in §2 and §3
is a cross-era number.**

**(c) `fz2_immaterial falsify` — the capture sha gate.**  It died on
`fz2c/404049` before classifying a seed, because `fz2_ledger.CURRENT` still
named the F18 ledger while the disk carried F19 rows.  §4 and §5.

## §1.1 THE BASELINE — BUILT, NOT ASSUMED

A before/after claim needs a before.  `fz2_replay`'s pre-relocation column was
not retained by the FLASH #19 sitting, so it was **re-created**: an isolated
git worktree at **`3836779ade`** (the last pre-merge commit, which carries the
F19 ledger and the F19 `results.jsonl` byte-identically), the live capture
directories symlinked in read-only, and `tb_sys ret` built there
(receipt `19d34e23c79a77b1…`).

**That baseline reproduces the FLASH #19 sitting's Q-2 control exactly**:

    FABRIC ERA GUARD: PASS      its inputs 88/88 hash IDENTICAL
    AGREEMENT 264 / 264 = 100.0 %
    of the 114 both-FAIL seeds, first_bad IDENTICAL on 114

— era guard green with **no bypass**, which is the control that the baseline is
genuinely the F19 era and that the only thing separating the two columns in
§2 is the relocation.  It is also an independent reproduction of FLASH #19's
**Q-2**, in a different checkout, by a different sitting.

---

## §2 OWED LEG A — THE FULL `fz2_replay --leg ret` ON THE F19 POPULATION

    population   264 seeds with banked socket rows (114 fabric-FAIL, 150 fabric-PASS)
    ran in 22s, 0 errors

|  | pre-relocation (`3836779ade`) | **post-relocation (`29a512f663`)** |
|---|---|---|
| agreement, verdict | **264 / 264 = 100.0 %** | **261 / 264 = 98.9 %** |
| fabric-PASS → replay PASS | 150 / 150 | **150 / 150** |
| fabric-FAIL → replay FAIL | 114 / 114 | 111 / 114 |
| `first_bad` identical, both-FAIL | **114 / 114** | 88 / 111 |

⚠ **THE AGREEMENT NUMBER FALLING IS NOT A REGRESSION AND MUST NOT BE READ AS
ONE.**  `fz2_replay` scores the offline core against **FLASH #19's fabric
verdict**, and the relocation is not on FLASH #19.  A core that legitimately
improves *must* disagree with a fabric column taken before the improvement.
The three seeds that "lost agreement" are three seeds that **stopped
diverging**.  This is the instrument's structural limit at a cross-era
measurement and it is why §1's bypass sentence exists.

### 2.1 THE REGISTERED CLAUSES OF §3.1, SCORED

| registered | measured | verdict |
|---|---|---|
| **0 LOST** — no seed at `bad_rows == 0` goes non-zero | **0** over all 264; all 150 fabric-PASS seeds stay replay-PASS | **MET** |
| **0 `first_bad` EARLIER** corpus-wide | **0 earlier**, 23 later | **MET** |
| the E1 family's predicted movers **ONLY** | **movers span EIGHT families** — E1 8 · D1 5 · NEW/UNCLASSIFIED 5 · D2 3 · A3 3 · D3 2 · C1 1 · C4 1 | **MISSED — §2.3** |

### 2.2 THE NAMED NON-MOVERS OF §3.1 — BOTH READINGS, STATED SEPARATELY

§3.1 registers its non-movers **"silicon-side, seat level"**.  The relocation
is on no bitstream, so the silicon column *cannot* move and that reading was
already scored by FLASH #19 (C-9 14/14, C-10 6/6).  Re-verified here directly
from the two ledgers: **every one of the named seats is byte-identical F18 →
F19 in `diverging_rows`, `first_bad_row`, `compare_window`, `arch`, `mech`,
`family` and `image_sha256`.**

| seat group | registered | silicon (F18 vs F19 ledger) | **core-side (offline replay, pre → post)** |
|---|---|---|---|
| `fz2c/404040` | stays `bad == 0` | absent from both ledgers ⇒ `bad == 0` | not in the replay population (fabric-PASS, unsampled) |
| §64.1 four — `fz2c/405002` 527 · `fz2c/405013` 1331 · `fz2c/405072` 636 · `fz2e/512056` 1475 | unmoved | **4 / 4 unmoved**, `first_bad` exactly 527 / 1331 / 636 / 1475 | **4 / 4 UNMOVED** |
| W7-4's §64.1 four — `fz2c/406063` · `fz2c/410047` · `fz2e/518053` · `fz2e/535027` | unmoved | **4 / 4 unmoved** | **3 / 4 unmoved — `fz2c/406063` MOVED, and it moved the WRONG WAY (§3.4)** |
| KM's three — `fz2c/404041` · `fz2e/501066` · `fz2e/513019` | ABSENT from the ledger | **3 / 3 absent** | n/a |
| phantom-T1's three at `bad_rows == 1`, `first_bad` 243 / 234 / 583 | unmoved | **3 / 3 at exactly 1 row and 243 / 234 / 583** | **3 / 3 UNMOVED** |
| the 24 IMMATERIAL, class-stable | unmoved | **24 / 24, every cell** (§4) | **23 / 24 unmoved — `fz2e/528010` MOVED (§3.4)** |
| M10's LEA-mod3 six — `fz2c/406054` · `fz2c/408019` · `fz2e/518038` · `fz2e/522019` · `fz2e/524034` · `fz2e/530001` | unmoved | **6 / 6 unmoved** | **6 / 6 UNMOVED** |

**On silicon the non-mover list is 100 % correct.  On the core side it is
correct on 39 of 41 named seats**, and the two exceptions are §3.4's.

### 2.3 THE DEVIATION — "E1 ONLY" IS WRONG, AND BY A WIDE MARGIN

**REGISTERED:** the relocation moves *"the E1 family's predicted movers only"*.
**MEASURED:** 28 seeds moved a scored field and **only 8 are E1**.

| family | movers | of family size |
|---|---:|---:|
| E1 same-status data cycle, different address | 8 | 39 |
| D1 chip fetched, core did not | 5 | 10 |
| NEW/UNCLASSIFIED | 5 | 11 |
| D2 core fetched, chip did not | 3 | 8 |
| A3 cycle-time slip (non-qs) | 3 | 15 |
| D3 both fetched, different address | 2 | 5 |
| C1 vector-1 trap MISSED by core | 1 | 1 |
| C4 other-vector delivery | 1 | 1 |

**This is reported, not explained.**  The honest reading is that the E1
restriction was never derived — §3.1's list is a transcription of *seat*
predictions from two earlier waves, and the ghost address is a BIU-launch
quantity that no family label bounds.  **The D-family concentration (10 of 23
D-family seeds moved) is the single most interesting unregistered fact in this
sitting** and it has no mechanism attached to it here.

**Every one of the 28 is itemised** in §2.4, and **26 of the 28 improved**.

### 2.4 THE 28 MOVED SEEDS

Net over the population: **Σ`bad_rows` −1,331 rows**, 26 down, 2 up, 3 to zero.

| seed | family | `bad` pre → post | `first_bad` pre → post |
|---|---|---|---|
| `fz2e/518039` | C1 | 1,587 → **531** | 2363 → 2367 |
| `fz2e/526054` | E1 | 320 → **48** | 265 → 269 |
| `fz2e/530046` | D1 | 2,084 → 2,063 | 1345 → 1353 |
| `fz2e/520000` | E1 | 836 → 820 | 502 → **2113** |
| `fz2c/408068` | D2 | 405 → 401 | 426 → 432 |
| `fz2c/408021` | E1 | 26 → 22 | 720 → 728 |
| `fz2c/409065` | A3 | 16 → 12 | 1534 → 1538 |
| `fz2e/520005` | D1 | 2,870 → 2,866 | 484 → 491 |
| `fz2e/521016` | D3 | 16 → 14 | 352 → 362 |
| `fz2e/521049` | A3 | 14 → 10 | 2150 → 2158 |
| `fz2e/525017` | A3 | 12 → 8 | 1141 → 1150 |
| `fz2e/527008` | D3 | 2,183 → 2,179 | 929 → 933 |
| `fz2e/527037` | E1 | 3,183 → 3,179 | 404 → 411 |
| `fz2e/529058` | NEW | 8 → 4 | 1792 → 1799 |
| `fz2e/529067` | E1 | 16 → 12 | 611 → 619 |
| `fz2e/530017` | D2 | 1,670 → 1,666 | 1440 → 1448 |
| `fz2e/530020` | D1 | 671 → 667 | 296 → 304 |
| `fz2e/530070` | C4 | 1,753 → 1,749 | 2225 → 2233 |
| `fz2e/532000` | D1 | 3,001 → 2,997 | 426 → 434 |
| `fz2e/533025` | E1 | 1,041 → 1,039 | unmoved |
| `fz2e/534062` | D2 | 1,271 → 1,267 | 1271 → 1291 |
| `fz2e/535004` | D1 | 807 → 803 | 1131 → 1138 |
| `fz2e/521006` | NEW | 9 → 8 | 368 → 369 |
| **`fz2e/521024`** | NEW | 4 → **0** | 304 → — | **CLOSED** |
| **`fz2e/522002`** | NEW | 4 → **0** | 444 → — | **CLOSED** |
| **`fz2e/534003`** | NEW | 4 → **0** | 564 → — | **CLOSED** |
| **`fz2c/406063`** | E1 | 3,149 → **3,165** | 245 → 249 | ⚠ **WORSE** |
| **`fz2e/528010`** | E1 | 4 → **2,067** (flicker 0 → 2) | unmoved | ⚠ **WORSE** |

**THE THREE CLOSURES ARE UNREGISTERED AND ARE REPORTED AS A BONUS, NOT AS A
BAR.**  All three are `NEW/UNCLASSIFIED`, all three are 4-row `COSMETIC`
IMMATERIAL members (§4), and none is a holdout or derive seat.  A closure
nobody predicted is worth exactly as much as it is worth: it is evidence the
mechanism reaches the banked population, and it is not evidence for any
registered claim.

---

## §3 OWED LEG B — THE WAVE-8 HOLDOUT UNSEAL

The split is `docs/notes/fz2_w8_split.json`, frozen at `fz2_w8_split.py` and
untouched.  **Every predicted value below was committed at `4f33ff4685`,
before the first RTL edit of the relocation and before any holdout seat was
replayed, solved or inspected.**

**The registered baseline is still the baseline.**  All 15 seats read
identically in the F18 and F19 ledgers — `diverging_rows` and `first_bad_row`
byte-for-byte the prereg's table, 15 of 15 — so the unseal scores the
predictions the prereg wrote and not a moved target.

### 3.1 PREDICTED vs MEASURED, SEAT BY SEAT

Offline `tb_sys(ret)` replay, pre-relocation → post-relocation.

| seat | **PREDICTED** | `bad` pre | `bad` post | Δ | `first_bad` pre → post | **MEASURED** |
|---|---|---:|---:|---:|---|---|
| `fz2c/406006` | closure plausible | 16 | 16 | 0 | 478 → 478 | **flat** |
| `fz2e/521059` | closure plausible | 20 | 20 | 0 | 1235 → 1235 | **flat** |
| `fz2e/518038` | row-improvement, NOT closure | 194 | 194 | 0 | 429 → 429 | **flat** |
| `fz2e/526054` | cascade-bound NON-closure | 320 | **48** | **−272** | 265 → 269 | **row-improvement** |
| `fz2e/522003` | cascade-bound NON-closure | 403 | 403 | 0 | 3164 → 3164 | flat |
| `fz2e/518022` | cascade-bound NON-closure | 742 | 742 | 0 | 281 → 281 | flat |
| `fz2e/520000` | cascade-bound NON-closure | 836 | **820** | **−16** | 502 → **2113** | **row-improvement** |
| `fz2c/408019` | cascade-bound NON-closure | 1,086 | 1,086 | 0 | 1617 → 1617 | flat |
| `fz2e/518050` | cascade-bound NON-closure | 2,560 | 2,560 | 0 | 748 → 748 | flat |
| `fz2e/534060` | cascade-bound NON-closure | 2,670 | 2,670 | 0 | 1067 → 1067 | flat |
| `fz2e/522019` | cascade-bound NON-closure | 3,075 | 3,075 | 0 | 396 → 396 | flat |
| `fz2c/406054` | cascade-bound NON-closure | 3,141 | 3,141 | 0 | 470 → 470 | flat |
| **`fz2c/406063`** | cascade-bound NON-closure | 3,149 | **3,165** | **+16** | 245 → 249 | ⚠ **WORSE** |
| `fz2e/527037` | cascade-bound NON-closure | 3,183 | **3,179** | **−4** | 404 → 411 | **row-improvement** |
| `fz2e/524034` | cascade-bound NON-closure | 3,479 | 3,479 | 0 | 457 → 457 | flat |

    closed 0   row-improvement 3   flat 11   worse 1

### 3.2 THE FOUR REGISTERED HOLDOUT BARS

| bar | registered | measured | verdict |
|---|---|---|---|
| **H-1** | REGISTERED CLOSURES: **ZERO** | **0 of 15 closed.** Both "closure plausible" seats are FLAT at 16 and 20 rows | **MET** |
| **H-2** | the twelve seats at ≥ 320 rows **DO NOT CLOSE**; falsifier = any reaching `bad_rows == 0` | **0 of 12 closed** | **MET** |
| **H-3** | **LOST = 0** over the replayed population | **0** over all 264 (§2.1) | **MET** |
| **H-4** | at least **ONE** of the 15 shows a strict decrease | **3 of 15**: `fz2e/526054` −272, `fz2e/520000` −16, `fz2e/527037` −4 | **MET** |

**All four MET.  This is the law's fuzz-population validation, and it passed on
a genuinely sealed set.**

### 3.3 ⚠ THE BAND RULE IS REFUTED AS A PREDICTOR, AND THAT IS THE MOST USEFUL
### THING THE UNSEAL PRODUCED

The prereg's rule was mechanical: `diverging_rows` ≤ 40 ⇒ closure plausible,
40 < rows < 320 ⇒ row-improvement, rows ≥ 320 ⇒ cascade-bound.  Measured:

    non-cascade seats (rows < 320):   3 seats,  0 moved
    cascade-bound seats (rows >= 320): 12 seats, 3 moved  (one of them -272 rows)

**Every seat the mechanism reached was in the class predicted least likely to
move, and no seat in the two classes predicted to move did.**  `diverging_rows`
is a measure of how far a divergence CASCADED, not of whether the ghost address
is on the seed's path — those are different questions and the band rule
conflated them.  **Registered consequence: `diverging_rows` must not be used
again as a proxy for reachability**, and the next holdout split should band on
something derived from the mechanism (e.g. whether the seed executes an `8F`
mod=3 form at all).

Note also `fz2e/526054`: **320 → 48 rows, an 85 % reduction**, the single
largest benefit in the whole population — sitting exactly on the band boundary
and predicted not to move.

### 3.4 ⚠ TWO SEEDS GOT WORSE — REPORTED LOUDLY, BECAUSE NOTHING REGISTERED THEM

**(a) `fz2c/406063` — a HOLDOUT seat AND a W7-4 §64.1 named non-mover.**
`bad_rows` 3,149 → **3,165** (+16), `first_bad` 245 → **249** (four rows
later).  It is the only seat in the unseal that regressed, and it is doubly
registered as a non-mover.  **No clause of the relocation prereg permits it.**
Note the mixed sign: the divergence starts four rows *later* (an improvement in
`first_bad`) and then cascades sixteen rows *further*.

**(b) `fz2e/528010` — an IMMATERIAL / COSMETIC member.**  `bad_rows` 4 →
**2,067** with `flicker` 0 → 2 and `first_bad` unmoved.  **This is the largest
single regression in the population** and it lands on a seed the campaign has
formally dispositioned as costing nothing.  It is the seed the F17 disposition's
**P2** perturbation was built on, so its evidence path is unusually well
understood.

**Neither is diagnosed here, and neither is absorbed.**  Both are offline,
core-side, cross-era numbers (§1); both are reproducible from the two run
JSONs; and both are named in §7 as FLASH #20 blockers.

---

## §4 THE F19 ERA RE-PIN — EVERY REGISTERED CELL MET

Pre-registered at `6e91923853`, **before either tool was run against the F19
ledger**.

### 4.1 THE PARTITION — K-2

| cell | F18 | **PREDICTED** | **MEASURED** | verdict |
|---|---:|---:|---:|---|
| FUNCTIONAL | 45 | **49** | **49** | MET |
| TIMING | 30 | **30** | **30** | MET |
| TRANSIENT | 5 | **5** | **5** | MET |
| COSMETIC | 19 | **19** | **19** | MET |
| UNSCOREABLE | 11 | **11** | **11** | MET |
| total | 110 | **114** | **114** | MET |
| IMMATERIAL | 24 | **24** | **24** | MET |
| `TIMING_RECONVERGED` | 8 | **7** | **7** | MET |

**Eight of eight.  Registered branch A was the right call**, and branches B
(TIMING 34) and C (UNSCOREABLE 15) are refuted.  `C-ROW` **114/114** and
`C-ARCH` **114/114**, exit 0 — **K-1 MET**.

**K-3 MET**: the 24 members are the F18 twenty-four, zero entrants, zero
leavers, every `cyc` / `done` / row-count / differing-column cell
byte-identical.

**K-4 MET on the class, MISSED on one branch.**  All four entrants classify
**FUNCTIONAL**, as registered.  But `fz2e/508068` was predicted to take the
CHIP-only branch (the ledger reads `done_core` **False**) and took the
both-dumped branch instead — `fz2_materiality` re-scans the rows and finds a
MAGIC-anchored core dump at clock **1525**.  **Reported, not smoothed.**  It is
a pre-existing, era-independent disagreement between `fz2_ledger`'s
`done_sim`-FLAG rule and the census's row scan: **six seeds in this ledger read
`arch: NODUMP` while the census finds both dumps** (`fz2c/405002`,
`fz2c/405013`, `fz2e/508068`, `fz2e/512056`, `fz2e/516001`, `fz2e/529009`),
four of them already present at F18.  Booked in census §I.6 item 2; not fixed
here, because changing a derivation rule inside a re-pin is changing the
instrument in the sitting that found it.

### 4.2 THE SECONDARY CELLS — TWO MISSES, ALL THREE FROM THE SAME ROOT

| cell | PREDICTED | MEASURED | verdict |
|---|---:|---:|---|
| G1 pool (no dump proof) | 25 | **24** | MISSED by 1 |
| G2 pool (two-sided dumps that differ) | 35 | **36** | MISSED by 1 |
| G3 pool (schedule) | 80 | **84** | MISSED by 4 |
| G4 FALSE on | 90 / 114 | **90 / 114** | MET |
| G4 by first failing clause | arch 35 · cycle_starts 30 · no_dump_proof 25 | **arch 36 · cycle_starts 30 · no_dump_proof 24** | MISSED, same root |

G1/G2 are **equal and opposite** and are the single `fz2e/508068` branch error
above.  G3 was registered *"derived by exclusion"* and flagged in the prereg as
the one secondary cell that was: all four entrants have a changed schedule, so
the pool grew by four.  **No G6 cell is affected by any of these.**

### 4.3 `falsify` — K-5 MET

    G1 DUMP PROOF     : 0 / 24   [PASS]
    G2 DUMP IDENTITY  : 0 / 36   [PASS]
    G3 SCHEDULE       : 0 / 84   [PASS]
    G4 NOT UNIVERSAL  : FALSE on 90 / 114   [PASS]
    G5 CONTROLS       : C-ROW 114/114 · C-ARCH 114/114   [PASS]
    G6 THE CENSUS     : 0 / 8 cells disagree   [PASS]
    G7 THE DOCUMENT   : 0 / 25 disagreements   [PASS]
    G8 NO FORK        : 0 / 114   [PASS]
    IMMATERIAL FALSIFIERS: PASS      exit 0

### 4.4 K-6 — THE FALSIFIER IS DEMONSTRATED TO FAIL, AND THE HISTORY IS PROVED INERT

Five perturbations on a shadow tree outside the repo (`sw/` and `docs/notes/`
copied, captures symlinked read-only), each applied to a pristine copy, scored,
and reverted.  **The repo was never perturbed.**

| # | perturbation | caught by | exit |
|---|---|---|---|
| **P0** | control — the unperturbed shadow | `IMMATERIAL FALSIFIERS: PASS` | **0** |
| **P1** | a member row DELETED from the LIVE anchored table (`fz2e/532032`) | **G7** 1 / 25 | **1** |
| **P2** | the LIVE `WORKING-RESIDUE` headline reverted to F18's (`90 = 114 − 24` → `86 = 110 − 24`) | **G7** 1 / 25 | **1** |
| **P3** | one LIVE census class cell moved (FUNCTIONAL 49 → 45) | **G6** 1 / 8 | **1** |
| **P4** | the LIVE census anchors REMOVED | **G6** — *"partition anchors … absent"*, **naming them**, with **no fallback to the F18 block sitting below** | **1** |
| **P5** | **THE APPEND-ONLY CONTROL** — the SUPERSEDED F18 blocks perturbed instead (F18 FUNCTIONAL 45 → 99, F18 headline → `1 = 2 − 3`) | nothing: **G6 0/8 PASS, G7 0/25 PASS** | **0** |

**P4 and P5 are the pair that matters for an append-only ledger.**  P4 proves
the parser never falls back to a superseded table when the live anchors go
missing; P5 proves the superseded tables are genuinely inert — history that can
be read and cannot lie.  This is the property the F18 sitting's scope change
was built for, and it is now measured rather than argued.

### 4.5 K-7 — THE ERA RE-PIN

`sw/fz2_ledger.py:CURRENT` now names
`sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json`.  Every consumer reads
it through `load()` and prints the file it read beside its numbers, which is
visible in every transcript in this document.  **The last four eras moved this
pointer in the flash sitting's own results commit; FLASH #19's did not, and
that omission is what the sha gate caught.**

### 4.6 THE DOCUMENT SHAPE — ONE DECLARED DEVIATION FROM PREREG §2

§2 registered *"the F19 block becomes PART I, the F18 block becomes PART II,
and the FLASH #17 block stays PART III"*.  **That was not done, and the reason
is the sitting's own HARD STOP 6** (*"editing, deleting or restating a FLASH
#17 or FLASH #18 number"*): the F18 block's prose refers to the F17 block as
**"PART II"** and to its own sections as **"§I.x"**, so renumbering F17 to
PART III would have forced edits inside superseded text.

**Taken instead**: the live block is **PART I (FLASH #19)**, the previous live
block keeps its own `§I.x` numbering under the heading **PART I-F18** with a
dated SUPERSEDED banner, and **PART II is still FLASH #17**.  A reading note at
the top of each document states the ordering and the scoping rule.  Both files'
F18 and F17 bodies are byte-identical apart from **the heading line and the two
anchor-comment renames**, which §2 registered.

---

## §5 THE `fz2c/404049` QUESTION, ANSWERED BY NAME

**Which capture files moved F18 → F19, and are they exactly the F19 sitting's
registered noise class?**

**No — and the framing conflates two different quantities.**

| population | answer |
|---|---:|
| seeds for which an F18-era capture `sha256` was COMMITTED (110 failures + 1 discard) | **111** |
| of those, whose capture file on disk is **byte-identical** to its F18 sha | **0** |
| whose capture file **MOVED** | **111 / 111 = 100 %** |
| whose capture file is **absent** | 0 |
| whose capture **path** changed | 0 |
| F19-pinned population (114 failures + 3 discards) vs disk | **117 / 117 MATCH** |

`fz2c/404049` is simply the first entry in the F18 ledger, so it is the seed the
gate names; its F18 sha is `5ecc16b862863782…` and the file on disk hashes to
`30a2d1febdae012d…`, **which is exactly the F19 ledger's recorded sha for it**.
The disk is F19, wholly and consistently.

**THIS IS NOT A FINDING, AND HERE IS THE MEASUREMENT THAT SAYS SO.**  FLASH #19
**re-captured all 3,840 seeds**, so every capture file was rewritten and new
bytes are expected on every one of them.  The registered noise class is about
**scored fields**, not bytes.  Scored-field movement, measured independently
from the two ledgers over all 111 shared seeds and the 6 non-shared:

    seeds pinned in BOTH ledgers                                111
    with ANY change in diverging_rows / first_bad_row /
      compare_window / arch / arch_match / mech / family /
      tier / banked_verdict / banked_sub / image_sha256           1
        fz2e/530020   diverging_rows 326 -> 671
    F18-only (left the ledger)                                    0
    F19-only (entered)                                            6
        fz2e/508068  fz2e/509050  fz2e/514001  fz2e/526075
        fz2e/524027  fz2e/535070   <- the last two as DISCARDS
    image_sha256 movers (generator drift)                         0

**Seven seeds moved a scored field, and all seven are registered**: the six are
FLASH #19 §4.4's movers verbatim, and `fz2e/530020` is §4.3's registered
falsifier firing (the F18 housekeeping admitted it to `TIMING_RECONVERGED` with
exactly this falsifier written beside it).  **Nothing moved outside the class in
the sense the class is about**, and **zero** images drifted.

⚠ **THE LIMIT, STATED RATHER THAN PAPERED OVER.**  `results.jsonl` carries no
capture digest, so **no F18-era sha exists for the 3,726 seeds outside the F18
ledger** and the byte-level question is unanswerable for them from committed
artifacts.  The scored-field question *is* answerable for all 3,840 and is
answered above.  **A future flash sitting that wants the byte-level answer must
bank a per-seed capture digest**; that is a cheap instrument change and it is
booked, not done.

---

## §6 THE GATES

| gate | measured | verdict |
|---|---|---|
| `fz2_w1 lint` | **PASS, 0 hits, 48 stratum rows** | PASS |
| `fz2_w1 bars` | **10/11 MET, C-6 MISSED** (`hold_rows_exact` 4,637 / `hold_rows_off` **1**) | **CARRIED AS REGISTERED** — FLASH #19 reported 10/11 with C-6 MISSED; not re-litigated here |
| `test_artifact` | **45 / 45** | PASS |
| `ghost_launch_law score` | **200 / 200 = 100.0 %**, exit 0 | PASS — the instrument did not drift |
| `r7_lint` | **PASS** — 0 undeclared carriers, 3 tainted (`eu_rd_edge`, `rd_edge_psw_take`, `rd_edge_take_raw`), 51 `stop` sites, 0 violations | PASS |
| `ss_lint --core ucore` | **PASS** — `SS_VERSION` **0x8E**, BIU 109 + EU 122 + tag = **232**, census **220** flops (BIU 91 + EU 129), **0 UNMAPPED** | PASS |
| `sw/testdata/` cleanliness | **only `receipts/verilator_binary.jsonl`, +2 lines** — the two `tb_sys` rebuild receipts this work required | PASS |

⚠ **ONE OBSERVATION AGAINST A BANKED ARTIFACT, AND `fz2_bars.json` WAS
DELIBERATELY NOT OVERWRITTEN.**  Re-running `bars` reproduces every verdict but
gives `C-8 div_guards` **21** where the banked file (`c59c2caf30`) records
**63**.  The five record files `C-8` aggregates —
`fz2_preflight/capture/c9/control/idle.json` — hold **2 + 6 + 2 + 10 + 1 = 21**
guards **at that very commit and at `3836779ade`**, so the 63 was never
reproducible from the tree it was committed with.  **No bar verdict moves**
(`unpinned` is 0 either way and C-8 reads MET), so this is reported as an
artifact-provenance observation and not as a bar failure, and the banked file
is left exactly as FLASH #19 banked it.

---

## §7 FLASH #20 — RECOMMENDATION: **NO-GO AS THINGS STAND**, WITH THREE NAMED ITEMS

The relocation's own ladder is green and its holdout validation passed all four
registered bars, so this is **not** a recommendation to revert.  It is a
recommendation not to spend a bitstream until three things are answered
offline, because each is cheap offline and expensive to diagnose in fabric.

1. **`fz2e/528010`: `bad_rows` 4 → 2,067 on a formally IMMATERIAL seed.**  The
   largest regression in the population, on a seed whose evidence path is
   already instrumented (it is the F17 disposition's **P2** subject).  Diagnose
   before flashing; a 2,000-row regression that reaches fabric will contaminate
   the next corpus's noise-floor argument.
2. **`fz2c/406063`: +16 rows on a doubly-registered non-mover** (§3.4a).
   Smaller, but it is the *registered* one — a named non-mover that moved.
3. **The `imul` finding the landing booked** (`093efbcfc2`): on the directed
   leg the chip's rail is `TMPA` = 0x1100 and `ghost_uses_mul_hi`'s value is
   `tmpa & opr` = 0x1000 = `E3 & SP`, so the arm has been invisible on every
   population that could not tell them apart.  Removing it predicts `imul`
   2/16 → 16/16 and **0 banked seeds moved** — a clean, testable, offline
   prediction that would take the law's own population from 114/208 to 128/208
   and close the whole registered G-3 shortfall.  **Measure it as its own
   mechanism before the next flash, not after.**

**Two further inputs to the decision, neither a blocker:**

* **G6 tripped its own registered YELLOW FLAG.**  The landing measured
  worst-of-2 **CONTROL 44.67 / RETENTION 41.60** against E-1's band of
  44.72 / 45.71; the retention configuration is **−4.11 MHz**, unexplained, and
  the STOP (38.0) cleared by +3.60.  `standing_gates.md` §A governs and one
  green build is not closure.
* **The band-rule refutation (§3.3) changes how the next holdout should be
  split.**  If FLASH #20 is to carry a fresh sealed set, band it on something
  derived from the mechanism, not on `diverging_rows`.

**What a GO would look like:** items 1 and 2 diagnosed (or explicitly booked
with mechanisms named and falsifiers registered), item 3 measured offline as
its own mechanism, and a fresh G6 worst-of-2 on the tree that is actually to be
flashed.  None of that needs the board.

---

## §8 RE-RUNNING THIS

```bash
git rev-parse HEAD
python3 sw/x1_retention.py build --leg all          # receipts 85c720c1… / abd3c4be…

# owed leg A -- cross-era, the bypass is deliberate and §1 is its sentence
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8 --no-fabric-era-guard

# the baseline (§1.1) -- an isolated worktree at the last pre-merge commit
git worktree add <tmp> 3836779ade
ln -s <repo>/sw/testdata/campaigns/fz2{c,e}/captures <tmp>/sw/testdata/campaigns/fz2{c,e}/captures
( cd <tmp> && python3 sw/x1_retention.py build --leg ret &&
  python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json \
          --all-failures --pass-sample 150 --leg ret --jobs 8 )   # era guard PASSES here

# the re-pin
python3 sw/fz2_materiality.py                       # CURRENT is now the F19 ledger
python3 sw/fz2_immaterial.py census
python3 sw/fz2_immaterial.py falsify                # exit 0, G1-G8 PASS

# the gates
python3 sw/fz2_w1.py lint ; python3 sw/fz2_w1.py bars
python3 sw/test_artifact.py ; python3 sw/ghost_launch_law.py score
python3 sw/r7_lint.py ; python3 sw/ss_lint.py --core ucore
```
