# FLASH #20 — RESULTS, AS REGISTERED: **THE GHOST LAUNCH RELOCATION IS TRUE IN FABRIC**

Pre-registration `docs/notes/fz2_flash20_prereg_2026-08-12.md`, committed
**`044086af1d`** — **before any Quartus build and before any board contact** —
together with `sw/ghost_pred_cell.py --fabric` and the scorer `sw/f20_cell.py`,
which was **proved non-vacuous on a null before the board was touched**.

Every bar is reported in the form it was registered in. **Nothing is
re-registered after the fact.**

    branch      fuzz-v2-on-relanding
    HEAD        b5051a24f3 -> prereg 044086af1d -> 3118a2db46 (the built tree)
    the delta   hdl/rtl/ucore/{v30_core,v30u_biu,v30u_eu,v30u_ss_pkg}.sv
                and nothing else a compiler reads (88 declared inputs, 4 moved)
    bitstream   nec_test_ucore.sof 26d6e79166183a21…
                nec_test_ucore.rbf 15742aa2f00431c4…
                RETENTION (X1_AD_RETENTION=1), draw ret2 of 2
    flash log   22 -> 23 entries, VERIFY ok try 1

---

## 0. THE HEADLINE

**THE RELOCATION IS TRUE IN FABRIC, AND THE SHARPEST FORM OF THE ANSWER IS THE
528-CELL CORE COLUMN ON SILICON.** `CHIP vs FABRIC` reads **398 identical / 122
different** — the registered numbers exactly, on the same 122 cells — and
`FABRIC vs CORE` reads **528 / 528 identical, 0 differing**: the synthesised
core and the modelled core do not disagree on one cell of 528. The socket
column is **528 / 528 byte-identical** to the FLASH #18 bank, so the reference
this is scored against demonstrably did not move.

**ALL 31 REGISTERED CORPUS SEATS HIT EXACTLY.** The four registered closures
left the ledger, **4 / 4**. The twenty-seven registered survivors read their
registered `diverging_rows` **27 / 27, value for value** — including **both
seeds that were registered to get WORSE** (`fz2c/406063` 3,149 → 3,165 and
`fz2e/528010` 4 → 7). The twenty named non-movers are **20 / 20** unmoved.
**0 LOST and 0 `first_bad` EARLIER anywhere in the corpus.**

**THE ROW METRIC RECONCILES TO ZERO.** Σ`diverging_rows` **118,282 → 100,493**,
and that is the registered seats (**−9,501**) plus FLASH #19's four noise
leavers (**−8,198**) plus `fz2e/527051` (**−90**). **Zero unexplained rows over
3,840 seeds.**

**THE HEADLINE POINT IS MISSED AND THE MISS IS ENTIRELY FLASH #19's NOISE
REVERTING.** Measured **106 failures of 3,839** against a registered **110 of
3,837** (**C-4 point MISSED, band MET**). Four seeds left the ledger that
nothing registered, and they are **exactly four of FLASH #19's six movers**; the
other two were its `ps3_8080` discard flips and those reverted too (discards
**3 → 1**). **All six of FLASH #19's movers have now reverted on a different
bitstream, and §4.6's registered falsifier did not fire.**

**THE ERA GUARD PASSES AT 88/88 WITH NO BYPASS.** Every offline replay figure
this branch had for the relocation carried `--no-fabric-era-guard`. That debt
is discharged, and the closing control is **256 / 256 = 100.0 %** with
`first_bad` identical on **106 / 106**.

**G6 REPRODUCED ITS POINT PREDICTION EXACTLY ON ALL FOUR DRAWS**: CONTROL
**45.61 / +8.892 / 12,282** twice and RETENTION **44.32 / +8.689 / 12,245**
twice, with both `.rbf`s byte-identical to the pre-F20 wave's own builds in a
different checkout.

**AND ONE FINDING, CAUGHT BEFORE IT COULD CONTAMINATE ANYTHING** (§8): the main
checkout's `tb_sys` binaries were **STALE**, and `ghost_pred_cell core` is not
on the artifact layer and ran against them.

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS, TWO DRAWS EACH

Quartus 17.1.0 Build 590. Each draw from a deleted `db` / `incremental_db` /
`output_files_ucore`. **Worst-of-2 is the figure; all four draws were clean.**

| | **CONTROL draw 1** | **CONTROL draw 2** | **RETENTION ret1** | **RETENTION ret2 (flashed)** |
|---|---|---|---|---|
| verdict | **PASS** | **PASS** | **PASS** | **PASS** |
| receipt | `06dcf73755e959a8…` | `f9338b2192ad9b67…` | `be54a31a79571713…` | **`e71c45a9c1580550…`** |
| configuration (**derived**) | `CONTROL/DEFAULT` | `CONTROL/DEFAULT` | **`RETENTION (X1_AD_RETENTION=1)`** | **`RETENTION (X1_AD_RETENTION=1)`** |
| **Fmax (`divclk`)** | **45.61** | **45.61** | **44.32** | **44.32** |
| **worst setup** | **+8.892** | **+8.892** | **+8.689** | **+8.689** |
| **TNS setup / hold** | 0.000 every domain | 0.000 every domain | 0.000 every domain | 0.000 every domain |
| ALMs | 12,282 (29 %) | 12,282 (29 %) | 12,245 (29 %) | 12,245 (29 %) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `304b5d67ccd2cd5c…` | `304b5d67ccd2cd5c…` | `304b5d67ccd2cd5c…` | `304b5d67ccd2cd5c…` |
| **`.rbf` sha256** | **`277e7de5f8fcfcde…`** | **`277e7de5f8fcfcde…`** | **`15742aa2f00431c4…`** | **`15742aa2f00431c4…`** |
| `.sof` sha256 | `581bf1b0e1ea7d97…` | `90abeb0fe168e4b9…` | `8c3b94f83b01a886…` | **`26d6e79166183a21…`** |
| compile | 568 s | 567 s | 563 s | 564 s |
| git | `3118a2db46` | `3118a2db46-dirty` | `3118a2db46-dirty` | `3118a2db46-dirty` |

| # | bar | verdict |
|---|---|---|
| E-1 | `gen_ucore_qsf --check` before each draw | **MET** — *"up to date"* on all four |
| E-2 | 0 errors, every stage Successful, 0 latches, 0 `lpm_divide` | **MET** ×4 |
| E-3 | Fmax ≥ 32 (G6) and ≥ 38.0 (the live STOP) | **MET** — **+6.32 MHz above the STOP** on the worse configuration |
| E-4 | worst setup > 0 | **MET** ×4 |
| E-5 | **TNS 0.000 setup AND hold, every domain** | **MET** ×4 |
| E-6 | the RETENTION receipt self-labels RETENTION | **MET** — **derived**, both draws |
| E-7 | the CONTROL receipt self-labels `CONTROL/DEFAULT` | **MET** — derived, both draws |
| E-8 | the RETENTION `.rbf` DIFFERS from CONTROL's | **MET** — `15742aa2…` ≠ `277e7de5…` |
| E-9 | the manifest reads `304b5d67ccd2cd5c…` on all four | **MET** ×4 |
| E-10 / E-11 | `.qsf` re-checked; all four receipts retained | **MET** |
| **P-1** | CONTROL worst-of-2 **45.61 / +8.892 / 12,282** | **MET — ALL THREE EXACT, BOTH DRAWS** |
| **P-2** | RETENTION worst-of-2 **44.32 / +8.689 / 12,245** | **MET — ALL THREE EXACT, BOTH DRAWS** |
| **P-3** | CONTROL `.rbf` = `277e7de5f8fcfcde…` | **MET — byte-identical, both draws** |
| **P-4** | RETENTION `.rbf` = `15742aa2f00431c4…` | **MET — byte-identical, both draws** |

⚠ **The `-dirty` on three of the four draws is not a compiler input.** The dirt
is the F19 archive files and the receipt ledger that draw 1 appended to; the
88-file input manifest is **identical on all four** and the `.rbf` is
**byte-identical to clean-tree draw 1's**. Stated rather than hidden.

### 1.1 EIGHT DRAWS AT ONE INPUT HASH, ACROSS TWO CHECKOUTS

The pre-F20 wave took four draws of this input manifest in an isolated
worktree; these are four more in the main checkout. **All eight agree to the
digit and to the `.rbf` byte.** That is further evidence for the census's
**F-4**, and it is not a victory lap: ⚠ **`standing_gates.md` §A still
governs.** Eight draws at one input hash is not a characterised distribution
over inputs, and the 19.42 / 45.91 pair the ladder remembers predates the
receipt layer.

**THE BINDING CONE WAS NAMED BEFORE THIS SITTING AND IS NOT THE RELOCATION.**
`ghost_preflash20_results` §6.2 measured it with `sta_census`/`sta_probe`:
`c_int_q → v30u_eu|row_posted`, the INT pin's capture register into the EU's
post decision, OUT→CORE, single-cycle, 46–47 levels. `g_sp`, `g_bare`, `g_age`,
`g_row_q`, `rq_ghost`, `cmt_ghost`, `cmt_addr`, `acc_split` and the string
`ghost` appear **zero** times in either census. No SDC change was taken; §6.3's
derivation stays booked.

---

## 2. **THE DIRECTED CELL — THE SITTING'S PRIMARY EVIDENCE**

Three columns of the same 528-cell grid (33 legs × 4 waits × 4 aligns), 520
structurally valid in both legs, the observable one 20-bit number off the pins
with no engine and no golden in it.

| # | bar | registered | **measured** | verdict |
|---|---|---|---|---|
| **G-1** | **THE PRIMARY. `CHIP vs FABRIC`** | **398 / 122**, the same 122 cells | **398 identical / 122 different**, **15 distinct (leg, label) signatures — the same 15 the offline column shows** | **MET** |
| **G-2** | **THE SHARPEST FORM. `FABRIC vs CORE`** | **528 / 528 identical, 0 differing** | **528 / 528 identical, 0 differing** | **MET** |
| **G-3** | `imul` closes **in fabric** | **16 / 16** | **16 / 16** | **MET** |
| **G-4** | the per-leg profile | 13 legs on their registered numbers | **13 / 13 on their registered HIT counts** — see the erratum below | **MET, with a registered denominator corrected** |
| **G-5** | the socket column did not move | **528 / 528 BYTE-IDENTICAL** to the FLASH #18 bank | **528 / 528 byte-identical, 0 moved** | **MET** |
| **G-6** | the offline comparand is HEAD's | **398 / 122**, bank restored byte-identical | **398 / 122**; `git status` on `ghost-pred/core/` **empty** | **MET — and it produced §8's finding** |
| **G-7** | rig integrity | `div_guard` PINNED every probe, 0 transport errors, 0 GHOST-unstable | **0 unpinned, 0 transport errors, 0 GHOST-unstable** on both 528-cell legs (22 s each) | **MET** |

### 2.1 WHAT G-2 MEANS, AND WHY IT IS THE ANSWER TO THE SITTING'S QUESTION

`ghost_pred_cell run --fabric` runs the **ucore inside the FPGA** (`use_core =
True`) on the identical images, the identical divider and the identical driver
as the socket leg. `FABRIC vs CORE` therefore compares **the synthesised core
against the modelled core on the same stimulus**, engine to engine, with no
golden and no comparator policy anywhere in it.

**It is 528 of 528, zero differing.** Every claim the relocation's offline
column made about the ucore is now a claim about a bitstream: the `dGR` law's
three cases, the 3:1 mux at the commit, the deleted V2 arm, F-A's deleted
`imul` arm and F-B′'s split predicate all do in fabric exactly what they do in
Verilator, cell for cell.

**And G-5 is what makes G-1 readable.** The chip column it is scored against is
byte-identical to one captured on FLASH #18, eight days and two bitstreams
earlier. Silicon did not move; the core did.

### 2.2 THE PER-LEG PROFILE, AND AN ERRATUM IN MY OWN REGISTRATION

| leg | registered | measured | | leg | registered | measured |
|---|---|---|---|---|---|---|
| `alu08` | 16/16 | **16/16** | | `mov8e` | 4/16 | **4/16** |
| `alu44` | 16/16 | **16/16** | | `mempop` | 2/16 | **2/16** |
| `alu88` | 16/16 | **16/16** | | `v_lea` | 2/16 | **2/16** |
| `imul` | 16/16 | **16/16** | | `memw` | 0/16 | **0/16** |
| `mul` | 16/16 | **16/16** | | `pfxpro` | 0/16 | **0/16** |
| `v_or` | 16/16 | **16/16** | | **`v_inc`** | **8/16** | **8 / 8** |
| `v_sub` | 16/16 | **16/16** | | | | |

⚠ **`v_inc`'s registered DENOMINATOR was wrong and it is mine.** Its **hit
count is 8, exactly as registered**, but 8 of its 16 cells are structurally
invalid in one leg, so the grid's denominator is 8, not 16. The `8/16` was
transcribed out of `ghost_launch_landing_prereg` **G-3**, whose population is
the law's 208 cells and not this grid. **Reported as an erratum in the
registration, not as a deviation in the measurement** — the number that carries
information, the hit count, is exact on all thirteen legs.

The full three-column score is retained at
`sw/testdata/ghost-pred-f20/f20_cell.json` with its three columns
(`board-f20`, `fabric-f20`, `core-head`).

### 2.3 THE SCORER'S NULL, RUN BEFORE THE BOARD WAS TOUCHED

`sw/f20_cell.py`, committed with the pre-registration, on the identity pair:

    plain      CHIP vs FABRIC 398/122    FABRIC vs CORE 528/0     MET
    --null 5   CHIP vs FABRIC 393/127    FABRIC vs CORE 523/5     MISSED

Both live comparisons move by exactly 5 and `CHIP vs CORE` stays at 398,
because the null perturbs only the fabric table. **A scorer that cannot fail is
not a scorer**, and this one was shown to fail before it was asked to pass.

---

## 3. THE CORPUS

`fz2_w1 control` → `preflight --board` → `capture` → `fz2_ledger`, all on FLASH
#20, scored against the FLASH #19 ledger.

| # | bar | registered | measured | verdict |
|---|---|---|---|---|
| **C-1** | corpus identity | `45d25f31a325c496…`, 3,840, 48 strata, lint PASS | **as registered**; `fz2_w1 lint` **PASS / 0 hits / 48 stratum rows** | **MET** |
| **C-2** | completeness | 48/48 strata, every `rc 0` | **48 / 48, every `rc 0`, 960 + 2,880, 10.9 min** | **MET** |
| **C-3** | the flash pin | `distinct_eras` 1 | **`distinct_eras` 1 · `absent` 0 · `incomplete` 0 · `build_stale` 0** over 3,840 | **MET** |
| **C-4** | **the headline** | **110 / 3,837**, band [100, 120] | **106 / 3,837 → reported as 106 / 3,839** | **POINT MISSED (−4 failures, +2 denominator), BAND MET** |
| **C-5** | unregistered membership flips | **0**, budget 10 | **ENTERED 0 · LEFT 8** = the 4 registered closures + **4 unregistered leavers** | **MISSED, 4 of a 10-seed budget — §3.3** |
| **C-6** | first divergence off the named seats | **0 of the 79** | **0 of 79, in either direction** | **MET** |
| **C-7** | the row metric | Σ`diverging_rows` **108,720**, reported not barred | **100,493**, and it reconciles to **zero unexplained rows** — §3.4 | **as registered** |
| **C-8** | discards | **3**, denominator 3,837 | **1** (`fz2e/509069`), denominator **3,839** | **MISSED — and it is a SOCKET-leg predicate reverting, §3.3** |
| **C-9 / C-10 / C-12** | the 20 named non-movers | value for value | **20 / 20, both columns, seed for seed** | **MET** |
| **C-11** | **the falsifier** | `fz2c/404040` ABSENT | **ABSENT** | **MET** |
| **C-14a** | the four registered closures | all four LEAVE | **4 / 4** | **MET** |
| **C-14b** | the 27 registered survivors | each on its registered `diverging_rows` | **27 / 27 EXACT** | **MET** |
| **C-14c** | direction | **0 LOST · 0 `first_bad` EARLIER** | **0 and 0** | **MET** |

### 3.1 **C-14b — THE TWENTY-SEVEN, VALUE FOR VALUE**

Registered in `fz2_flash20_prereg` §4.2, before the build and before the board.

| seat | registered | measured | | seat | registered | measured |
|---|---:|---:|---|---|---:|---:|
| `fz2c/406063` | **3,165** ⚠ | **3,165** | | `fz2e/526054` | 48 | **48** |
| `fz2c/408021` | 22 | **22** | | `fz2e/527008` | 2,181 | **2,181** |
| `fz2c/408068` | 401 | **401** | | `fz2e/527037` | 3,179 | **3,179** |
| `fz2c/409065` | 12 | **12** | | `fz2e/528010` | **7** ⚠ | **7** |
| `fz2c/409077` | 2,683 | **2,683** | | `fz2e/529058` | 4 | **4** |
| `fz2e/518039` | 531 | **531** | | `fz2e/529067` | 12 | **12** |
| `fz2e/518053` | 8 | **8** | | `fz2e/530017` | 1,668 | **1,668** |
| `fz2e/518067` | 45 | **45** | | `fz2e/530046` | 1,634 | **1,634** |
| `fz2e/520000` | 822 | **822** | | `fz2e/530070` | 1,749 | **1,749** |
| `fz2e/520005` | 2,866 | **2,866** | | `fz2e/532000` | 2,998 | **2,998** |
| `fz2e/521006` | 8 | **8** | | `fz2e/533025` | 1,039 | **1,039** |
| `fz2e/521016` | 14 | **14** | | `fz2e/534062` | 1,267 | **1,267** |
| `fz2e/521049` | 10 | **10** | | `fz2e/535004` | 808 | **808** |
| `fz2e/525017` | 8 | **8** | | | | |

**27 of 27, exact.** And the two marked ⚠ are the ones **registered to get
WORSE**: `fz2c/406063` 3,149 → **3,165** (the un-relocated split partner,
relocation prereg §7(b)) and `fz2e/528010` 4 → **7** (`UBE`/`A0` not recomputed
from the relocated address, §7(c)). **Both regressions landed on their
registered value to the row.** Registering a regression is what makes the rest
of the table mean anything.

**C-14a**, the four closures — `fz2e/521024`, `fz2e/522002`, `fz2e/530020`,
`fz2e/534003` — **all four left the ledger**.

### 3.2 THE NAMED NON-MOVERS, 20 / 20

§64.1 four `fz2c/405002` **840 / 527** · `fz2c/405013` **921 / 1331** ·
`fz2c/405072` **891 / 636** · `fz2e/512056` **984 / 1475**; W7-4's surviving two
`fz2c/410047` **3589 / 227** · `fz2e/535027` **3226 / 296**; KM's three
**ABSENT**; phantom-T1's three at **(1, 243) · (1, 234) · (1, 583)**; M10's
LEA-mod3 six all exact; `fz2e/520066` **8 / 1249**; `fz2c/404040` **ABSENT**.

⚠ **C-9b was registered as a MISS in advance and is reported as one**:
`fz2c/406063` and `fz2e/518053` are W7-4 §64.1 named non-movers and **both
moved**, exactly as the offline wave already recorded. The clause was not
re-written to fit; it is scored MISSED again, in fabric this time.

### 3.3 **C-4 / C-5 / C-8 — THE MISS, AND WHAT IT IS**

**Registered 110 of 3,837. Measured 106 of 3,839.** Reported as a MISS. What
moved, itemised:

| seed | tier | F19 | F20 | what it is |
|---|---|---|---|---|
| `fz2e/508068` | soup | `bad` 359 | **absent** | FLASH #19 mover — reverted |
| `fz2e/509050` | soup | `bad` 2,863 | **absent** | FLASH #19 mover — reverted (it was also F19's only failing `bars` C-6 directive) |
| `fz2e/514001` | soup | `bad` 1,681 | **absent** | FLASH #19 mover — reverted |
| `fz2e/526075` | raw | `bad` 3,295 | **absent** | FLASH #19 mover — reverted |
| `fz2e/524027` | raw | DISCARD (`ps3_8080`) | **not a discard, not a failure** | FLASH #19 discard flip — reverted |
| `fz2e/535070` | raw | DISCARD (`ps3_8080`) | **not a discard, not a failure** | FLASH #19 discard flip — reverted |

**THESE ARE FLASH #19's SIX MOVERS, ALL SIX, AND THEY HAVE ALL REVERTED ON A
DIFFERENT BITSTREAM.** FLASH #19 §4.6 measured them non-reproducible on its own
bitstream and registered the falsifier for that reading: *"a third capture on
this bitstream in which the same six seeds fail again, reproducibly."* **This
sitting is a fourth capture, on a new bitstream, and the falsifier did not
fire.** Every one of the six is back at its FLASH #18 value.

Three things follow, and only the first two are claims:

1. **The F20 headline is arithmetically the registered prediction applied to a
   noise-corrected F19 baseline.** F19's own run B read 110 of 3,839; minus the
   four registered closures is **106 of 3,839**, which is what was measured.
2. **`ENTERED` is ZERO.** Not one seed entered the ledger. Every membership
   change is a departure, four of them registered and four of them a known
   noise class reverting. **The relocation broke nothing that this corpus can
   see.**
3. **It does NOT establish that the 681–697 band is understood.** It is still
   unexplained, and F19's open item #1 stands unchanged.

**C-8** is the same event on the socket leg: `ps3_8080` is a **SOCKET-leg**
predicate (amendment A-2) that no RTL change can reach, and it re-rolled from 3
back to 1. Registered 3, measured 1: **MISSED**, and it is a chip/rig
observation, not a relocation one. That is the fourth consecutive era in which
this predicate has moved (2 → 2 → 3 → 1 → 3 → **1**).

### 3.4 **C-7 — THE ROW METRIC RECONCILES TO ZERO**

    Sum diverging_rows   F19 118,282  ->  F20 100,493

    the 31 registered seats            -9,501
    FLASH #19's four noise leavers     -8,198
    fz2e/527051  (1,003 -> 913)           -90
    -------------------------------------------
    reconciled prediction             100,493
    measured                          100,493
    UNEXPLAINED                             0 rows

**Zero unexplained rows over 3,840 seeds and 11.3 million compared rows.** The
one row-count mover outside the registered seats is **`fz2e/527051`, 1,003 →
913**, which did **not** move its `first_bad_row`; it is an `escaped` seed and
is reported, not explained.

The corpus's own headline fields: seed match **97.2389 %** (was 97.0289), row
match **99.1136 %** (was 98.9559), rows compared **11,330,230**.

### 3.5 `fz2_immaterial falsify` — C-15, EVERY CLAUSE AS REGISTERED

| # | registered | measured | verdict |
|---|---|---|---|
| **C-15a** | class **24 → 22**, leavers exactly `fz2e/521024` + `fz2e/522002`; COSMETIC 17 · TRANSIENT 5; residue 88 | **22 members, COSMETIC 17 · TRANSIENT 5**; G7 names the two leavers by seed; residue **84** (= 110 − 22 registered, 106 − 22 measured) | **MET on the class; the residue follows C-4's miss** |
| **C-15b** | **`fz2e/528010` STAYS COSMETIC at 7 rows**, columns ≈ `addr=1, data=2, nxta=1, ube=3` | **COSMETIC, `bad` 7, columns `addr=1, data=2, nxta=1, ube=6`** | **MET — the class and the new column derived correctly; the `ube` COUNT was registered as a ROW count and the census column counter is not one** |
| **C-15c** | `409065` 12 COSMETIC · `521049` 10 COSMETIC · `525017` 8 COSMETIC · `408021` 22 TRANSIENT | **12 · 10 · 8 · 22, sub-classes exactly as registered** (`408021` still carries `bs=12`) | **MET** |
| **C-15d** | 0 leavers other than the two closures; entrants reported not barred | **0 other leavers, 0 entrants** | **MET** |
| **C-15e** | ⚠ **G6 and G7 registered to FAIL on document staleness alone**; G1–G5, G8 PASS | **G1 · G2 · G3 · G4 · G5 · G8 PASS; G6 5/8 cells, G7 3/25 — every disagreement is doc (114/24/90) vs derivation (106/22/84)** | **AS REGISTERED — the fix is booked, not applied** |
| **C-15f** | TIMING_RECONVERGED 7, UNSCOREABLE 11 | **7** and **10** | reported, not barred |

C-15b deserves a line of its own. The prediction was **derived, not hoped**:
`ghost_preflash20_results` §4.5 measured `fz2e/528010`'s residual as 4 RAIL rows
plus **3 rows differing in `ube_n` alone**, and `ube` is a value column, not one
of `fz2_materiality.CYCLE_DEFINING`. The census now reads exactly that —
**`ube` has appeared in its column list and the seed is still COSMETIC**.

---

## 4. THE ERA GUARD AND THE CLOSING CONTROL

| # | bar | measured | verdict |
|---|---|---|---|
| **Q-1** | `fz2_replay` passes the fabric era guard with **NO bypass** | **`its inputs 88/88 hash IDENTICAL in the tree at HEAD` — FABRIC ERA GUARD: PASS.** It **REFUSED at HEAD before the flash**, by name, on all four `hdl/rtl/ucore/` files (84/88) | **MET** |
| **Q-2** | closing control, era guard ON | **256 / 256 = 100.0 %** — fabric PASS 150 / replay PASS 150 · fabric FAIL 106 / replay FAIL 106 · **`first_bad` IDENTICAL on 106 / 106**, 0 errors, 21 s, and **100 % agreement in every family, every wait mode and both stimulus classes** | **MET in the strongest available form** |

⚠ The registered Q-2 population was **260** (110 + 150); the measured
population is **256** (106 + 150), because four fewer seeds are in the ledger.
The registered floor of 255 is quoted against the population it was written
for; on the actual population the figure is **100.0 %**.

**WHY Q-1 IS THE POINT OF THIS SITTING AND NOT A FORMALITY.** Every replay
figure the relocation has ever had — the 264-seed population, the 28 movers,
the six F-B′ movers, the holdout unseal — was taken with
`--no-fabric-era-guard` in force, because the four RTL files postdated FLASH
#19's bitstream. **The guard now passes at 88/88 in the main checkout with no
bypass anywhere in this sitting**, so those figures are re-derivable against a
bitstream that exists.

---

## 5. THE STANDING GATES ON THIS ERA

| gate | result |
|---|---|
| `fz2_w1 bars` | **11 / 11 MET** — leaf-diffed against the F19 archive: **exactly one verdict moved, C-6 MISSED → MET**, `hold_rows_exact` **4,638** / `hold_rows_off` **0**. C-1 rate clauses validated on `fz2v`/960; C-4 `distinct_eras` 1; C-5 `gen_drift` 0; **C-8 `div_guards` 63 / unpinned 0**; C-9 192 stable / 0 unstable; C-10 0 quarantines / 0 run-error lines |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 control` (C-6 board legs) | **MET — 9 legs**, holds **[2, 20, 300]** proved on `pin_int` and `pin_nmi`, TVECs `(0, 48896)` and `(3056, 8)`, N1 negative control PASS, `div_guards` 10 / unpinned 0 |
| `fz2_w1 preflight --board` | **OK** — single writer, era pinned to receipt `e71c45a9c158…` self-labelling RETENTION, **192-seed regeneration sample hits 0**, RBCHECK **8 registers**, MATCH 800 ×3 |
| `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| `r7_lint` | **PASS** — 0 undeclared carriers, 3 declared tainted, **51 `stop` sites, 0 violations** |
| `ss_lint --core ucore` | **PASS — `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8**, BIU 109 + EU 122 symbols, census **220 architectural flops, 0 UNMAPPED** (BIU 91 → 91 mapped; EU 129 → 127 mapped + 2 whitelisted) |
| `gen_ucore_qsf --check` | **PASS** ×4 |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `check_ab_hw all 800` | first light **MATCH ×3**, and **again inside `preflight`** |
| `check_ab_hw chip 800` | close-out **MATCH over 800 rows**, `use_core=0` |
| §38.9 missed-trap overlay | **4** — the same four as FLASH #18 and #19 |

⚠ **The four `timed_*` ratchets, `x1_retention` and `x1_fabric` were NOT run and
are NOT quoted** (`gen_seq._v1_anchor_stop`; FLASH #19 §2.1's GEN-DRIFT
finding). **The 283-cell HLT sweep column that confirmed the last several
flashes does not exist for this bitstream, and the pre-registration said so
before the build.** Its role was carried by §2's 528-cell directed grid.

### 5.1 HOUSEKEEPING (H-1)

The F19 era's `fz2_bars` / `fz2_capture` / `fz2_control` / `fz2_preflight`
JSONs were archived to `*_F19-archive.json` **before** the F20 capture
overwrote them (FLASH #19 did not archive them and the convention has held
since F12), and `fz2c` / `fz2e` were archived **by rename** to
`*-F19-archive` before `fuzz_campaign.py new` re-pinned both manifests to
FLASH #20. **Nothing was deleted.**

---

## 6. THE DIRECTED-CELL SPOT-CHECKS

Socket-only (`use_core=False`): they measure **SILICON**, which no bitstream can
move. **Registered: 0 chip-column movers.**

| # | leg | measured | verdict |
|---|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` (48 cells, 2 s) + `score` | **chip == core, 0 / 512 differing on ALL SIX columns**; **KM 16/16 derivation legs and 14/14 validation legs, the only key surviving on every one**, and 16/16 + 14/14 against the core too; NULL `notf` / `v_notf` **[0]** both; 0 transport errors, stability 64/512 ×3 with **0 TAKE-unstable, 0 stream-distinct**. **And the 48 re-captured cells are BYTE-IDENTICAL to the bank** (sha256 0 differing over 512) | **MET, in a stronger form than registered** |
| **S-2** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells, 1 s) + `score` | **0 chip-column movers over 2,200 cells, sha256 0 differing, 0 scalar columns differing**; the six invariant columns `wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows` all **0 / 1,920**; `n_inta` **36**, `ack_off` **46**, `ack_off_hlt` **46** — the pre-ack-wake baseline, **identical to FLASH #19's**; 330 boundary cells ×11 reps, TAKE-unstable **0** | **MET** |
| **S-3** | restoration | **both banks copied aside and RESTORED BYTE-IDENTICAL** — `git status` empty on `sw/testdata/tf0f`, `sw/testdata/ie-pinfall` **and** `sw/testdata/ghost-pred` — with the F20 rows retained **beside** them at `sw/testdata/{tf0f,ie-pinfall}-f20-spotcheck/` and `sw/testdata/ghost-pred-f20/` | **MET** |

**The control that makes §3.3 readable**: the same board, the same session, the
same socket — **0 movers on two directed cells and a byte-identical 528-cell
socket column**, against four corpus seeds that moved.

---

## 7. HARD STOPS

**NONE FIRED.**

RETENTION worst-of-2 **44.32 ≥ 38.0** · the RETENTION receipt self-labelled
RETENTION and its `.rbf` differed from CONTROL's · `safe_flash` VERIFY **ok try
1** · **0 `div_guard` UNPINNED anywhere in the sitting** · **0 `RigMismatch`, 0
quarantines, 0 run-error lines, 0 transport errors** · single writer asked
before first contact and before every leg, `--force` never used · first light
MATCH 800 ×3 · G-5 socket column unmoved · `ss_lint` at 0x8E / 232 / 220 ·
closing chip proof MATCH 800 · `board_idle()` clean and **last**.

**The registered non-stops, reported with their denominators**: C-4's point
(−4 failures of a ±10 floor, +2 denominator), C-5's four unregistered leavers
(of a 10-seed budget), C-8's discard re-roll (1, registered 3), C-15e's G6/G7
doc staleness (pre-registered as a miss), C-9b's two named non-movers moving
(pre-registered as a miss), and §2.2's `v_inc` denominator erratum.

### 7.1 THE CLOSING BOARD STATE, READ AND EXPLAINED

    pwr_good False   cpu_running False   ctrl 0x5   cfg 0xff0008   use_core False

⚠ **`pwr_good False` is the RESTING state, not a fault** — FLASH #19 §7.2
established this and it is re-confirmed here the same way: **`check_ab_hw chip
800` was run and returned MATCH over 800 rows**, and the final `div_guard`
readback was **PINNED**. `use_core` is **False**.

---

## 8. **THE FINDING: A STALE BINARY, AND A TOOL THAT IS NOT ON THE ARTIFACT LAYER**

G-6 asked for the offline comparand to be **re-taken at HEAD** rather than
inherited, on the stated ground that *"proved not to move is not measured at
HEAD."* It caught something much larger than the clause was written for.

**The main checkout's `tb_sys` binaries were STALE.** Both legs were built
2026-08-12T08:41 from a `v30u_eu.sv` that is not this tree's — F-A and F-B′
landed in an **isolated worktree** (`292f30bcf8`) and the main checkout was
never rebuilt after the merge. `artifact.require()` names the file and both
hashes:

    INPUT  hdl/rtl/ucore/v30u_eu.sv   receipt ff1675214cad9c0b…  tree 4fb842b200d1922a…

**AND `ghost_pred_cell core` IS NOT ON THE ARTIFACT LAYER.** It calls
`tb_sys.run_tb` directly, never asks `artifact.require()`, and it produced a
column against the stale binary without complaint: **384 identical / 136
different**, which is the pre-F-A number exactly.

**THE DELTA IS EXACTLY F-A, QUANTIFIED.** Stale column vs HEAD column: **14 of
528 cells differ, all fourteen `imul`**, sha256-differing on the same 14. That
is F-A's registered benefit (**+14 / −0**, `ghost_preflash20_results` A-3) cell
for cell — the stale binary was precisely *HEAD minus F-A* and nothing else.

Rebuilt through the declared build (`x1_retention build --leg all`; receipts
`a59266319ee168f2…` base, `b80e16916e34e6a8…` ret) and re-taken: **398 / 122**.
Both columns are retained — `ghost-pred-f20/core-head` (the comparand every
figure here is scored against) and `ghost-pred-f20/core-head-STALEBIN` (the
finding's own evidence).

**BOOKED, NOT PATCHED.** A gate edit on the day the gate is load-bearing is
what this campaign's rules distrust. The mitigation used instead was to call
`artifact.require()` by hand on both legs and record the receipt ids beside
every column. ***Registered falsifier for the booked repair***: `ghost_pred_cell
core` refuses to run against a binary whose declared inputs no longer hash to
the tree, in the way `fz2_replay` already does.

**What this says about the campaign, not about the tool**: `fz2_replay` refused
and said why; `ghost_pred_cell core` did not, and the same tree produced two
different 528-cell columns four minutes apart. §75's *"a number with no artifact
id is not quotable"* had a hole in it, and the hole was found by a clause that
was written for a different reason.

---

## 9. WHAT THIS SITTING ESTABLISHED, AND WHAT IT LEAVES OPEN

**ESTABLISHED**

1. **The ghost LAUNCH relocation, F-A and F-B′ are TRUE IN FABRIC.** The
   synthesised core reproduces the modelled core on **528 of 528** directed
   cells and reproduces silicon on **398 of 520**, against a socket reference
   proved byte-identical across two bitstreams.
2. **`imul` closes in silicon**: 2/16 → **16/16**. F-A's whole measurable
   benefit is in this cell and it is now a fabric figure.
3. **The corpus moved exactly where the offline wave said and nowhere else** —
   31 seats registered, **31 hit**, **0 entered**, **0 LOST**, **0 `first_bad`
   earlier**, and the row metric reconciles to **zero unexplained rows**.
4. **Both registered regressions landed on their registered value to the row**,
   which is what makes the other 29 seats evidence rather than coincidence.
5. **The relocation's era is re-synced**: the fabric era guard passes at 88/88
   with no bypass, and the closing control is 256/256 with `first_bad`
   identical on all 106.
6. **FLASH #19's six movers were capture noise**, confirmed a second time on a
   different bitstream; its registered falsifier did not fire.
7. **G6 reproduces to the digit and to the `.rbf` byte across two checkouts**,
   eight draws at one input hash.

**OPEN, WITH THEIR FALSIFIERS**

1. **The relocation's named residue is untouched and two of its three pieces
   are VISIBLE in this ledger.** (a) the un-relocated **SPLIT PARTNER**
   (relocation prereg §7(b)) is `fz2c/406063`'s +16 rows; (b) **`UBE`/`A0` at
   the post** (§7(c)) is `fz2e/528010`'s +3; (c) **the RAIL** (§7(a)) is 80 of
   the law's 208 cells and 122 of this grid's 520. *(a) and (b) are the same
   second mechanism and belong together.*
2. **The 681–697 band is still unexplained.** Six seeds have now reverted out
   of it and nothing in this tree says why that band. *Falsifier*: a directed
   repeat of those six at high repetition on one bitstream, counting the flip
   rate per seed.
3. **`ghost_pred_cell core` is off the artifact layer** (§8). *Falsifier*: it
   refuses a stale binary.
4. **The IMMATERIAL census document is one era stale** (C-15e). Booked,
   deliberately not fixed in the sitting that measured it.
5. **`x1_retention` / `x1_fabric` remain GEN-DRIFTED**, so this branch still has
   no golden-relative sweep column. *Falsifier*: a pre-fuzz-v2 generator
   checkout reproducing `fab_f11`'s 279/283.
6. **The binding timing cone `c_int_q → v30u_eu|row_posted` is booked, not
   fixed**, with the derivation an E-1 analogue would need written out in
   `ghost_preflash20_results` §6.3.

**AND WHAT THIS SITTING CANNOT ESTABLISH**, as registered: it attributes
nothing to any one of the three landings. That attribution was made offline and
exactly (F-A alone 0 of 264 seeds, F-B′ alone 6, combined byte-identical to F-B′
alone), and this sitting does not re-make it. What fabric added is **existence**,
and existence is what was missing.

---

## Appendix A — THE BAR IN ONE TABLE

| clause | registered | measured | verdict |
|---|---|---|---|
| **G-1 CHIP vs FABRIC** | 398 / 122 | **398 / 122** | **MET** |
| **G-2 FABRIC vs CORE** | 528 / 528, 0 differing | **528 / 528, 0** | **MET** |
| G-3 `imul` in fabric | 16 / 16 | **16 / 16** | **MET** |
| G-4 per-leg profile | 13 legs | **13 / 13 hit counts**; `v_inc` denominator erratum | **MET** |
| G-5 socket column | 528 / 528 byte-identical | **528 / 528** | **MET** |
| G-6 HEAD offline comparand | 398 / 122 | **398 / 122** | **MET** |
| P-1 / P-2 G6 worst-of-2 | 45.61 / 44.32 | **45.61 / 44.32** | **MET** |
| P-3 / P-4 `.rbf` | `277e7de5…` / `15742aa2…` | **both exact, both draws** | **MET** |
| F-1 flash | VERIFY OK, log 22 → 23 | **ok try 1, 23 entries** | **MET** |
| first light | MATCH 800 ×3 | **MATCH ×3** | **MET** |
| **C-4 headline** | 110 / 3,837 | **106 / 3,839** | **POINT MISSED, BAND MET** |
| C-5 unregistered flips | 0, budget 10 | **4 leavers, 0 entrants** | **MISSED, inside budget** |
| C-6 first divergence off the seats | 0 of 79 | **0 of 79** | **MET** |
| **C-14a** four closures | all LEAVE | **4 / 4** | **MET** |
| **C-14b** 27 survivors | value for value | **27 / 27** | **MET** |
| **C-14c** direction | 0 LOST, 0 earlier | **0 / 0** | **MET** |
| C-7 row metric | 108,720 | **100,493, 0 unexplained** | as registered |
| C-8 discards | 3 | **1** | **MISSED (socket-leg)** |
| C-9 / C-10 / C-11 / C-12 | 20 non-movers + `404040` absent | **20 / 20, ABSENT** | **MET** |
| C-9b two named non-movers move | registered MISS | **both moved** | **MISSED as registered** |
| C-15a class | 24 → 22, named leavers | **22, exactly those two** | **MET** |
| C-15b `fz2e/528010` | COSMETIC at 7 rows | **COSMETIC, 7, `ube` present** | **MET** |
| C-15e G6/G7 | registered to FAIL | **FAIL, doc staleness only** | **as registered** |
| Q-1 era guard | PASS, no bypass | **88 / 88 PASS** | **MET** |
| Q-2 closing control | ≥ 255 / 260 | **256 / 256 = 100.0 %** | **MET** |
| S-1 / S-2 chip columns | 0 movers | **0 / 512 and 0 / 2,200** | **MET** |
| close-out | idle, `use_core=0`, MATCH 800 | **all three** | **MET** |

## Appendix B — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                    # 3118a2db46 (built) / 20908c8082 (artifacts)
python3 sw/f20_cell.py --chip sw/testdata/ghost-pred-f20/board-f20 \
                       --fabric sw/testdata/ghost-pred-f20/fabric-f20 \
                       --core  sw/testdata/ghost-pred-f20/core-head
                                                      # 398/122 · 528/0 · 398/122
python3 sw/f20_cell.py --fabric sw/testdata/ghost-pred-f20/core-head --null 5
                                                      # the scorer's own null
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8      # 256/256, guard PASS 88/88
python3 sw/fz2_immaterial.py --ledger sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json census
python3 sw/fz2_w1.py bars ; python3 sw/fz2_w1.py lint ; python3 sw/check_fuzz_bank.py
python3 sw/ss_lint.py --core ucore ; python3 sw/r7_lint.py ; python3 sw/test_artifact.py
```

**A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT BE QUOTED AGAINST THIS
TREE.**
