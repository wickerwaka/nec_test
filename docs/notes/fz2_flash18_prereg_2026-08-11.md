# FLASH #18 — PRE-REGISTRATION

**Committed BEFORE any Quartus build and BEFORE any board contact.**  Branch
`fuzz-v2-on-relanding`, HEAD **`98855f782c`**.  Board contact — flashing
included, `sw/safe_flash.sh` only — is authorised by the user for this sitting
("Flash as you need to" + "Push forward on all work", 2026-08-11).

---

## 0. WHAT THIS SITTING IS FOR

The board carries **FLASH #17** (`.sof 26c19f613e2caae8…`, flashed
2026-08-11T13:49:17Z, `flash_log.jsonl` **20 entries**).  Since then the branch
landed **exactly two RTL mechanisms**, plus one **synthesis-inert instrument**:

    git diff 1ad5074ebe 98855f782c --stat -- hdl/rtl/
      hdl/rtl/system_large.sv        | 112 +++++++++    <- M10-SYS, INSTRUMENT
      hdl/rtl/ucore/v30u_biu.sv      |  45 +++---       <- phantom-T1 (ack-wake)
      hdl/rtl/ucore/v30u_eu.sv       |  62 +++++--      <- KM
      hdl/rtl/ucore/v30u_eu_step.svh |   9 +++-         <- KM (comment)

| landing | commit | mechanism | offline reach |
|---|---|---|---|
| **KM** | `e57c3b4d12` | the `0F` escape's OPCODE pop is a TF boundary sample — `q_bnd_pop = q_first \|\| (st == S_EXT_POP)`.  ONE term, no flop, no SS address, no opcode named, QS pins unmoved | **3 seats CLOSE** |
| **phantom-T1** | `26d0d135cd` | `halt_withdraw_preview` **DELETED** from the `bs` mux — a WITHDRAWN announcement is released on its own clock.  ONE bit, a deletion, the RTL shrinks | **3 seats COLLAPSE to 1 row each — they do NOT close** |
| M10-SYS | `9b28b7cb30` | the save-state freeze probe on `tb_sys` | **synthesis-inert, see §0.1** |

### 0.1 M10-SYS IS SYNTHESIS-INERT, AND THE CLAIM IS **VERIFIED MECHANICALLY, NOT ASSERTED**

The block's own comment claims *"strip the `ifndef` blocks, take the `ifdef`
arms, and the file is byte-identical to `6cbb01a642`'s"*.  **That claim was
checked by running it, before this document was written:**

* every added line lies inside `` `ifndef SYNTHESIS `` (lines 394-489), and each
  of the two port-connection edits is written
  `` `ifdef SYNTHESIS <the original line> `else <the probe's line> `endif ``
  (386-390, 496-502, 515-525);
* the file's only other directives are `` `ifdef VERILATOR `` (54, 171) and
  `` `ifdef X1_AD_RETENTION `` (583), untouched by the landing;
* preprocessing `hdl/rtl/system_large.sv` at HEAD with `SYNTHESIS` **defined**
  and diffing against `git show 6cbb01a642:hdl/rtl/system_large.sv` returns
  **BYTE-IDENTICAL** (`diff -u`, empty);
* **both** QSFs set the macro — `hdl/nec_test_ucore.qsf:71` and
  `hdl/nec_test.qsf:60`, `set_global_assignment -name VERILOG_MACRO
  "SYNTHESIS=1"`.

**Therefore Quartus's post-preprocessing input at HEAD is identical to the
ack-wake tree's, and §2 registers that as a claim the build TESTS.**

### 0.2 THE ERA GUARD IS FIRING AT HEAD, BY NAME, AND CORRECTLY

    its inputs  83/88 hash IDENTICAL in the tree at HEAD
      MOVED     hdl/nec_test_ucore.qsf         [EXEMPT: §70.7]
      MOVED     hdl/rtl/system_large.sv         <-- RTL
      MOVED     hdl/rtl/ucore/v30u_biu.sv       <-- RTL
      MOVED     hdl/rtl/ucore/v30u_eu.sv        <-- RTL
      MOVED     hdl/rtl/ucore/v30u_eu_step.svh  <-- RTL
    ERA MISMATCH -- REFUSING TO SCORE.

Re-syncing it is a **registered clause of this sitting** (`Q-1`).  Note that
`system_large.sv` is a declared input of the bitstream receipt and the guard
fires on it even though §0.1 proves the compiler cannot see the change — **the
guard hashes FILES, not netlists, and that is the conservative direction.**

### 0.3 THE NOISE FLOOR GOVERNS EVERY AGGREGATE CLAIM

`docs/notes/fz2_capture_noise_2026-08-10.md`: **the floor is 10 / 3,840 =
0.2604 % ledger-class flips**, CORE leg bit-identical on 730/730.  FLASH #17
measured **7 of that 10-seed budget**.

This sitting's predicted aggregate delta is **3 seeds — BELOW the floor.**
Therefore, exactly as at FLASH #17:

**THE REGISTERED CLAIM OF THIS SITTING IS THE SIX NAMED SEATS (§4.1, §4.2).
THE HEADLINE IS REGISTERED AS A BAND (§4.3) AND A RESULT INSIDE THAT BAND IS
NOT EVIDENCE FOR EITHER LANDING AND WILL NOT BE QUOTED AS SUCH.**  Six named
seats carry an expected **6 × 0.2604 % = 0.016** spoiled seats.

---

## 1. THE OFFLINE MEASUREMENT THIS PRE-REGISTRATION IS BUILT ON

Run before this document was written, with **no board contact and no Quartus**,
on the **merged** tree — the first time either landing has been scored beside
the other:

```
python3 sw/fz2_tbsys.py build --leg ret        # REBUILT, receipt 6e6589e25c2b90aa…
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json \
        --all-failures --pass-sample 550 --leg ret --jobs 8 --no-fabric-era-guard
```

⚠ **It carries `--no-fabric-era-guard` (§0.2) and this document says so beside
every number derived from it.**

**Result — 651 seeds (113 fabric failures + 538 fabric passes), 0 errors:**

|  | replay PASS | replay FAIL |
|---|---:|---:|
| fabric PASS (538) | **538** | **0** |
| fabric FAIL (113) | **3** | 110 |

**3 CLOSED, 0 LOST, and EXACTLY SIX SEEDS MOVED AT ALL over the 651** — KM's
three closures and phantom-T1's three collapses.  Not one other seed moved by a
single row.  **The two landings are additive with zero interaction**, which is
itself worth stating: each was measured on a tree that did not carry the other.

Standing offline gates re-measured at HEAD before this document:
`gen_ucore_qsf --check` **PASS (up to date)** · `r7_lint` **PASS — 20 nets /
1 carrier / 3 tainted / 51 `stop` sites / 0 violations** · `ss_lint --core
ucore` **PASS — 103 BIU + 122 EU = 226, 214 flops, 0 UNMAPPED** ·
`test_artifact` **45/45, NON-VACUOUS** · `fz2_immaterial falsify` **PASS, G1-G8,
21 members / 92 non-members / 113 failures**.

### 1.1 ⚠ **AN ERRATUM AGAINST FLASH #17 §5.3, FOUND OFFLINE BEFORE THIS CAPTURE**

FLASH #17 §5.3 booked an open instrument question:

> *"Every one of the 24 'near' rows is a POSITIVE offset of 1–5 rows — the
> offline replay systematically predicts one to five fewer diverging rows than
> silicon on long-tail seeds, and never the other way.  That is a one-sided
> residue with a shape, it is reported and NOT explained."*

**IT IS `flick`, AND IT IS NOT A RESIDUE AT ALL — IT IS TWO DIFFERENT
QUANTITIES.**  `sw/fz2_ledger.py:219` writes each entry's

    diverging_rows = bad_rows + flick

while `sw/fz2_ledger.py:209` accumulates the corpus total as `bad_rows` ALONE,
and `fz2_replay`'s `fabric_bad` is `bad_rows`.  The F17 pre-registration's
Appendix A predicted from the replay (`bad`) and the F17 results scored against
the ledger entry (`bad + flick`).  **The gap is `flick`, seed for seed:**

| seed | ledger `diverging_rows` | replay `bad` | banked `flick` | F17 §5.3 "offset" |
|---|---:|---:|---:|---:|
| `fz2c/404049` | 1637 | 1636 | **1** | +1 |
| `fz2c/404071` | 906 | 905 | **1** | +1 |
| `fz2c/410028` | 429 | 426 | **3** | +3 |
| `fz2e/535004` | 812 | 807 | **5** | +5 |
| `fz2e/510043` | 2259 | 2238 | **21** | **+21 — F17's one "off by more"** |

and over the whole F17 ledger **Σ`diverging_rows` 119,258 − Σ`bad_rows` 119,192
= 66 = Σ`flick`**, on exactly the 25 seeds whose two figures differ.

**CONSEQUENCE, REGISTERED: every row prediction in this document is stated in
BOTH units, named.**  F17 §5.3 is **CLOSED as an instrument-bookkeeping
artifact**, not carried forward as a physical residue.  ⚠ It also means F17's
§5.3 table read "18/43 EXACT" where the correct comparison would have read
**43/43 exact on `bad_rows`**; that is an erratum against the F17 results
document and is filed as one.

---

## 2. THE BUILD — G6 (`E-*`)

Two configurations, **ONE clean draw each** (the RTL is already-drawn; the
two-draw norm applies to an RTL *landing*, and this is a *flash*).
`db` / `incremental_db` / `output_files_ucore` deleted before each.
**Order is fixed: CONTROL first, at HEAD, then RETENTION.**  The RETENTION
build is what flashes.

| # | bar | registered |
|---|---|---|
| **E-1** | `gen_ucore_qsf.py --check` BEFORE each draw | PASS (measured PASS at HEAD at registration) |
| **E-2** | 0 errors, every stage `Successful`, 0 latches, 0 `lpm_divide` | both draws |
| **E-3** | `divclk` Fmax | **≥ 32 MHz** (G6), and **≥ 38.0 MHz is THIS SITTING'S HARD STOP**, both draws |
| **E-4** | worst setup slack | **> 0 ns**, both draws |
| **E-5** | TNS setup **AND** hold | **0.000 on every domain**, both draws |
| **E-6** | the RETENTION receipt **self-labels RETENTION** | `configuration` begins `RETENTION (X1_AD_RETENTION=1) -- DERIVED from …` |
| **E-7** | the CONTROL receipt self-labels `CONTROL/DEFAULT` | derived, not asserted |
| **E-8** | `gen_ucore_qsf.py` regenerated and re-checked AFTER each draw | PASS |
| **E-9** | the macro's effect is CHECKED, not asserted | the retention `.rbf` sha256 **differs** from this tree's CONTROL `.rbf` sha256 |
| **E-10** | both receipts retained in `sw/testdata/receipts/quartus_bitstream.jsonl` | ids quoted with every figure |

**E-6 and E-3 are HARD STOPS; nothing is flashed on either.**

### 2.1 **THE M10-SYS INERTNESS CLAIM, REGISTERED AS SOMETHING THE BUILD TESTS**

The ack-wake tree `26d0d135cd` — HEAD minus M10-SYS — drew G6 CONTROL **TWICE,
bit-identically**: **40.13 MHz**, worst setup **+6.333 ns**, ALMs **12,246
(29 %)**, TNS 0.000 everywhere, 88-file input manifest **`7db533790f51ff18…`**
on both draws.  §0.1 proves the compiler's post-preprocessing input at HEAD is
the same text.  Therefore:

| # | registered | direction |
|---|---|---|
| **E-11** | the 88-file input manifest **WILL DIFFER** from `7db533790f51ff18…` | the manifest hashes FILE BYTES and `system_large.sv`'s bytes moved.  A manifest that did NOT move would mean the gate is not hashing what it says it hashes — **that would be the finding** |
| **E-12** | **PRIMARY POINT: the CONTROL draw reproduces `40.13 MHz` / `+6.333 ns` / `12,246 ALMs` EXACTLY** | this is the strong form §0.1 licenses.  A deviation is **NOT** evidence against M10-SYS's inertness (the preprocessed source is provably identical); it is a measurement of **Quartus's run-to-run determinism**, and `standing_gates.md` §A already says the same tree has drawn 19.42 and 45.91 MHz.  It is reported either way |
| **E-13** | **SOFT band, if E-12 misses: 38.4 – 42 MHz** | outside it, reported as an observation; below **38.0**, a HARD STOP |

### 2.2 **THE RETENTION-VS-CONTROL SIGN — THE SIXTH OBSERVATION**

On this branch retention has drawn **ABOVE** control **five consecutive times**
(FLASH #13 +0.46, #14 +1.50, #15 +2.24, #16 +0.12, #17 +0.71).  **REGISTERED
REPORTING OBLIGATION: this sitting states the sign of (retention − control)
explicitly and it is the SIXTH observation regardless of which way it falls.**
FLASH #17 additionally saw Fmax and worst setup disagree in sign with each
other for the first time; whether that recurs is reported, not predicted.

---

## 3. THE FLASH AND FIRST LIGHT (`F-*`)

| # | bar | registered |
|---|---|---|
| **F-1** | `sw/safe_flash.sh <ucore .sof>` — PREP / `quartus_pgm` / VERIFY | VERIFY OK; `sw/testdata/flash_log.jsonl` **20 → 21 entries**, tail `verify: "OK"`; `.sof` and `.rbf` sha256 recorded |
| **F-2** | first light `check_ab_hw.py all 800` | **MATCH over 800 rows on all three legs** (chip-vs-golden, core-vs-chip, core-vs-golden), `rc 0` |
| **F-3** | RBCHECK (`fz2_w1.py control`) | **exactly 8 registers** round-trip: `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, `TVEC`, `VECCTL` |
| **F-4** | C-6 control (`fz2_w1.py control`) | **9 legs / 51 checks / 51 PASS**, `holds_proved [2, 20, 300]`, `pins_proved [pin_int, pin_nmi]`, `tvecs_proved [[0,48896],[3056,8]]`, P1–P5 run lengths **2 · 300 · 2 · 300 · 20**, N1 negative control PASS |
| **F-5** | `use_core=0` chip proof **after everything** | `check_ab_hw.py chip 800` → **MATCH over 800 rows** |
| **F-6** | `div_guard()` tally | **0 UNPINNED** — that is the bar; the count is reported |
| **F-7** | transport | **0 `RigMismatch`**, 0 quarantines, 0 transport errors |
| **F-8** | `board_idle()` | clean, `use_core = 0` left selected |
| **F-9** | single-writer / socket-only | `single_writer OK`, `use_core False` on every socket leg — checked before first contact |

**F-2 justification, registered in advance.**  KM moves the **TF trap boundary**
and needs `PSW.TF` set with a `0F`-escaped instruction; phantom-T1 needs a
**HALT wake whose withdrawn announcement is followed by an acknowledge**.  The
boot program sets neither `TF` nor executes a HALT/INTA sequence, so **MATCH 800
is the correct prediction and it is a control on the flash, not a test of either
landing.**  Any deviation is a **HARD STOP**.

**F-4 is scored on its VERDICTS, not on row sha256** (FLASH #13's registered
erratum: two `control` runs on one flash give differing row sha256 and 51/51
both times).

---

## 4. THE SEAT-LEVEL PREDICTIONS (`P-*`)

**Reference ledger: FLASH #17's** —
`sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json`, **113 failures**,
denominator **3,837**, matched 3,724, era `.sof 26c19f613e2c…`.
Membership is `bad_rows != 0`; `arch` is REPORTED, not a membership criterion.

**Every "predicted" figure below is the §1 offline replay's, on the merged
tree, taken with `--no-fabric-era-guard`.**

### 4.1 — **P-1: KM's THREE SEATS CLOSE, SEED FOR SEED**

| # | seat | family | `first_bad_row` F17 | `bad_rows` F17 → predicted | ledger `diverging_rows` F17 → predicted |
|---|---|---|---:|---|---|
| 1 | `fz2c/404041` | D2 core fetched, chip did not | 933 | **2,437 → 0** | 2,437 → **0** |
| 2 | `fz2e/501066` | D2 core fetched, chip did not | 515 | **572 → 0** | 572 → **0** |
| 3 | `fz2e/513019` | C2 INTA-vectored delivery | 656 | **2,843 → 0** | 2,843 → **0** |

**P-1 REGISTERED: all three LEAVE the ledger (`bad_rows == 0`).  Scored seat by
seat.**  All three have banked `flick == 0`, so both units agree.

**P-1a — the signal weighting is stated in advance, not counted equally.**
`fz2c/404041` (2,437 rows) and `fz2e/513019` (2,843 rows) are high-signal;
`fz2e/501066` (572 rows) is mid.  **None is below the noise magnitude**
(`fz2_capture_noise` measured movers at 1,189–3,312 rows), so this is a stronger
seat set than FLASH #17's, six of whose eight closed from 2–12 rows.

**P-1b — `fz2c/404041` closed against its OWN pre-registration** (KM results
§3.1: registered as *"moves, does not close"*, `S-3` MISSED in the favourable
direction).  It is quoted here as a seat because the offline instrument has now
measured it twice; **the reach registered by the cell was "2–3 seeds" and 3 is
the top of that range — nothing here licenses more.**

### 4.2 — **P-2: phantom-T1's THREE SEATS COLLAPSE TO ONE ROW.  THEY DO NOT CLOSE, AND THAT IS THE PREDICTION.**

The mechanism's own booking (`ackwake_results_2026-08-11.md` §2.5): **the ucore
has ONE status value per CPU clock where silicon has TWO.**  The landing buys
the end-of-clock sample at the price of the address-phase one, so the withdrawal
clock becomes a single `bs CODE != PASV` cell.  **A closure to 0 would mean the
integration renders the half-clock, which it does not.**

| # | seat | family | `first_bad_row` F17 → predicted | `bad_rows` F17 → predicted | banked `flick` → predicted |
|---|---|---|---|---|---|
| 4 | `fz2c/404071` | C2 INTA-vectored delivery | **244 → 243** | **905 → 1** | 1 → **0** |
| 5 | `fz2e/514044` | C2 INTA-vectored delivery | **235 → 234** | **1,261 → 1** | 2 → **0** |
| 6 | `fz2e/516001` | C2 INTA-vectored delivery | **584 → 583** | **1,154 → 1** | 2 → **0** |

**P-2 REGISTERED, in the form the fabric scorer will read it:**

* **PRIMARY POINT: `bad_rows == 1` EXACTLY on each of the three, `flick == 0`,
  ledger `diverging_rows == 1`, and `first_bad_row` EXACTLY 243 / 234 / 583.**
* **BAND: `1 ≤ bad_rows ≤ 6` on each.**
* **`bad_rows == 0` on any of the three is a FINDING, not a success** — it would
  refute §2.5's booking that the residual is the harness's one-status-per-clock
  limit, and it must be reported as a finding and investigated, **not quoted as
  a closure**.
* **`bad_rows > 6` on any of the three is a FINDING.**

**P-2a — THE DERIVATION OF THE FABRIC EXPECTATION, AND ITS UNCERTAINTY,
STATED BEFORE CAPTURE.**  The scored `bs` column is `nec_bus`'s **`bs_early`**
(the falling-edge, address-phase sample).  `nec_bus` is **the same RTL in
fabric and in `tb_sys`** — `system_large` instantiates it in both — so the
one-status-per-clock limit is a property of the **DUT + harness pair**, not of
the offline instrument, and the fabric expectation is therefore the *same* one
row.  **This is a derivation, not an extrapolation of the offline number.**

The uncertainty, named:

1. **The band's upper end is 6, not 1**, because at FLASH #17 the offline
   replay's `bad` was the ledger's `diverging_rows` minus `flick`, and `flick`
   ran 1–21 on 25 seeds (§1.1).  A fabric `flick` of 1–5 on these three would
   put `diverging_rows` at 2–6 with `bad_rows` still 1.  **`bad_rows` is the
   scored quantity; `diverging_rows` is reported beside it.**
2. **The instrument's track record is stated so a miss is legible**: at FLASH
   #17 the `tb_sys ret` replay agreed with fabric on **membership 263/263** and
   on **`first_bad` 113/113**.  A membership disagreement on any of these six
   seats would be the first this campaign has measured.
3. Three cells in the directed HLT sweeps moved one row earlier and one column
   over on the candidate (`ackwake_results` §4, `busstat: exp 'CODE' got
   'PASV'`) — the same residue seen from a third instrument. It stays at 279/283.

### 4.3 — **P-3: THE HEADLINE, REGISTERED AS A BAND BEFORE CAPTURE**

|  | FLASH #17 (measured) | FLASH #18 (registered) |
|---|---|---|
| corpus seeds | 3,840 | 3,840 |
| discards (`ps3_8080`) | 3 | **3 predicted; a re-roll is itemised, not a stop** (§5, G-6) |
| denominator | 3,837 | **3,837** |
| **failures** | **113** | **PRIMARY POINT 110** |
| **failures, REGISTERED BAND** | — | **100 ≤ failures ≤ 120  (110 ± 10)** |
| matched | 3,724 = 97.0550 % | **3,727 = 97.1332 % (point)** |
| corpus `rows_diverging` (Σ`bad_rows`) | 119,192 | **110,023 (point)** |
| Σ ledger `diverging_rows` (Σ`bad`+`flick`) | 119,258 | **110,084 (point)** |
| row match | 98.9475 % | **99.0284 % (point, on Σ`bad_rows`)** |

**±10 is the measured socket-capture floor** (`fz2_capture_noise_2026-08-10.md`),
**registered here BEFORE the capture and not derived from it.**

⚠ **HOW THIS BAR MAY AND MAY NOT BE QUOTED.**  The band is **10/3 = 3.3× the
effect** — worse than FLASH #17's 1.25×.  It is registered as a **containment
check, not as evidence**:

* a result **inside** the band **says nothing about either landing** and will
  not be quoted as confirming one;
* a result **outside** the band is a **finding** and is investigated;
* **the evidence is P-1 and P-2, seat by seat, and nothing else.**

**The two row arithmetics, shown so neither is a net that hides a cost:**

    Sigma bad_rows      119,192 - 5,852 (KM's three) - 3,317 (phantom-T1's three) = 110,023
    Sigma diverging_rows 119,258 - 5,852            - 3,317 - 5 (the three flicks) = 110,084

**There is no registered cost half this time** — unlike FLASH #17's ghost-address
landing, neither mechanism was measured to make any seed worse, offline, on any
of 651 seeds.

### 4.4 — **P-4: ZERO LOSSES, ON A BUDGET**

**Registered: no seed matched at FLASH #17 becomes a failure through a KM or
phantom-T1 mechanism.**  The faithful replay measured **LOST 0 over 651 seeds**
(538/538 fabric-PASS seeds still PASS, and 0 of the 110 still-failing seeds
gained a row).

* **new failures ≤ 10** (the floor), **every one itemised** — seed, family,
  `first_bad_row`, tier, `escaped_n`, whether its CHIP leg moved, whether its
  CORE dump moved.
* **ATTRIBUTION IS A DICHOTOMY, NOT AN EXCUSE.**  A new failure is attributed to
  **this sitting's landings** — a landing-level finding — if it carries either:
  **`PSW.TF` set at a `0F`-escaped instruction within six `F` pops of its fork
  row** (KM), or **a HALT wake whose withdrawn announcement is followed by an
  acknowledge within 12 rows of its fork** (phantom-T1).  Otherwise it is a
  **noise candidate**, and calling it noise requires the positive evidence the
  floor document used: **the CORE leg bit-identical** and/or **the terminator's
  `fired` count moved**.  ⚠ **KM's population is TF seeds, of which the corpus
  carries ~101 (`fz2_f14_results` §, the `C1` population) — a TF seed among the
  entrants is the case that must be looked at hardest.**
  **"Not obviously ours" is NOT an attribution and will not be written.**
* **more than 10 new failures, or ANY new failure carrying either mechanism, is
  a FINDING reported as such.**

### 4.5 — **P-5: NO UNREGISTERED CLOSURE**

**Registered: exits from the ledger are EXACTLY the three of §4.1.**  Any other
exit is itemised with the P-4 dichotomy.  Unregistered exits count against the
same **10-seed** budget — the budget is on **total unregistered ledger
membership flips, entries and exits together**.

### 4.6 — **P-6: `fz2c/404040` MUST NOT APPEAR**

The branch's sharpest falsifier — a banked SUCCESS whose silicon refuted the
`C2` sitting's registered form.  **ABSENT from the F17 ledger, and predicted
`bad 0` by the merged-tree replay.**  If it is a failure at FLASH #18, a
landing has broken a mechanism nobody claimed, and that is a **landing-level
finding**, not a noise candidate.

### 4.7 — **P-7: THE NAMED NON-MOVERS, SEAT-LEVEL**

All measured UNMOVED by the merged-tree replay (§1), in `bad` **and** `first`.
**Registered: unmoved in fabric, on both columns.**

⚠ **AMENDMENT A-1 (committed with the scorer, while the CONTROL build was still
running, BEFORE the flash and BEFORE the F18 ledger existed).**  The table below
quotes the **replay's `bad_rows`**, and two of its cells therefore differ from
the F17 **ledger** entry by that seed's `flick` — `fz2c/408019` reads 1086 here
and 1087 in the ledger.  **The bar is and always was "UNMOVED", so the scorer
compares `N[s]` against `R[s]` directly**, which is unit-consistent by
construction; the literals below are printed by the scorer as a *transcription
check* and any mismatch is labelled as one.  This was caught by running
`sw/fz2_f18_score.py` against the **F17 null** before the board was touched —
which is what the null run is for — and it is the same §1.1 units trap, found a
second time in a second place.

| group | seeds | F17 `bad` / `first`, all predicted UNMOVED |
|---|---|---|
| **the §64.1 four** (KM/N1 list) | `fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` | 840/**527** · 921/**1331** · 891/**636** · 984/**1475** |
| **the W7-4 older §64.1 four** | `fz2c/406063` · `fz2c/410047` · `fz2e/518053` · `fz2e/535027` | 3149/245 · 3589/227 · 3413/567 · 3226/296 |
| **the M10 LEA-mod3 six** | `fz2c/406054` · `fz2c/408019` · `fz2e/518038` · `fz2e/522019` · `fz2e/524034` · `fz2e/530001` | 3141/470 · 1086/1617 · 194/429 · 3075/396 · 3479/457 · 20/442 |
| **the falsifier** | `fz2c/404040` | `bad 0` (§4.6) |

**P-7a — the 21 IMMATERIAL seeds stay CLASS-STABLE.**  `fz2_immaterial.py
falsify` on the **new** F18 ledger must read **PASS on G1-G8** with the residue
arithmetic intact.  ⚠ **The membership COUNT is NOT registered at 21**: three of
the 21 (`fz2e/521024`, `fz2e/522002`, `fz2e/532032`) are `NEW/UNCLASSIFIED`
escaped raw seeds from FLASH #17's own noise entrants, and the class is derived
from the live ledger.  **What is registered is that G1-G8 PASS and that no
member of the class is one of this sitting's six seats** (none is).

### 4.8 — **P-8: THE FAMILY TABLE**

From §4.1 and §4.2 and nothing else.  Note **phantom-T1's three stay in C2** —
they collapse, they do not leave.

| ledger family | F17 | predicted F18 |
|---|---:|---:|
| **C2 INTA-vectored delivery** | 10 | **9** (`fz2e/513019` leaves) |
| **D2 core fetched, chip did not** | 10 | **8** (`fz2c/404041`, `fz2e/501066` leave) |
| all thirteen others | (unchanged) | (unchanged) |
| **total** | **113** | **110** |

⚠ **A family re-classification of the three collapsed seats is possible and is
NOT a miss**: at `bad_rows == 1` the ledger's classifier sees one cell, and
`fz2_ledger` may name that cell differently from the 905-row signature it named
before.  **Registered: if any of the three moves family, it is REPORTED with the
new family and the single differing column, and P-8's C2 row is scored against
the seats that actually stayed.**

### 4.9 — **P-9: THE FIRST-DIVERGENCE BAR**

**REGISTERED: no still-failing seed's `first_bad_row` DECREASES, with exactly
three named exemptions — `fz2c/404071` 244→243, `fz2e/514044` 235→234,
`fz2e/516001` 584→583.**  Any other decrease is itemised.  This is the strong
form of the bar (FLASH #17 had to name nineteen exemptions; this sitting's
replay names three and no others over all 651 seeds).

---

## 5. THE CORPUS RE-CAPTURE (`G-*`)

Archive by rename first — the SUP discipline, **nothing deleted**:

    sw/testdata/campaigns/fz2c          -> fz2c-F17-archive
    sw/testdata/campaigns/fz2e          -> fz2e-F17-archive
    sw/testdata/fz2/fz2_capture.json    -> fz2_capture_F17-archive.json
    sw/testdata/fz2/fz2_bars.json       -> fz2_bars_F17-archive.json
    sw/testdata/fz2/fz2_preflight.json  -> fz2_preflight_F17-archive.json
    sw/testdata/fz2/fz2_control.json    -> fz2_control_F17-archive.json

then `fuzz_campaign.py new fz2c` / `new fz2e`, `fz2_w1.py preflight --board`,
`fz2_w1.py capture`.  **Same driver as the F17 ledger's own provenance.**

| # | bar | registered |
|---|---|---|
| **G-1** | corpus identity unchanged | `SEED_LIST_SHA256 = 45d25f31a325c496…`, 48 strata, `fz2c` 960 + `fz2e` 2,880 = **3,840** |
| **G-2** | preflight | `verdict: "OK"`, `board_leg: true`, **0 GEN_DRIFT** on the regeneration sample |
| **G-3** | capture completeness | **48 / 48 strata**, `rc 0`, no `halted`, `results.jsonl` **960 / 2,880** rows |
| **G-4** | retained captures | **NOT BARRED — reported.**  The bar is only that **every seed named in any prediction above is still retained and scored**, except a seat that closes, which has no divergence to retain |
| **G-5** | the flash pin | every result row's `era.sof_sha256` = FLASH #18's `.sof` sha256; **`distinct_eras 1`, `absent 0`, `incomplete 0`, `build_stale 0`** over 3,840 |
| **G-6** | discards | **3** predicted, denominator **3,837**.  `_ps3_8080` is a **SOCKET-leg** predicate (A-2) that a core landing cannot move by construction; a re-roll is **itemised loudly, seed by seed, with its `escaped_n`**, the denominator moves with it, and the rate is reported on **both** bases (A-12/A-13).  **NOT a hard stop.**  ⚠ The set has re-rolled on THREE consecutive flashes (2 → 2 → 3, five distinct seeds); a fourth re-roll is expected and is reported, not explained |

**IF THE CAPTURE STOPS ITSELF ON AN INTEGRITY ALARM, THIS SITTING HALTS AND
REPORTS.  Alarms are not cleared on the live population.**

---

## 6. THE ERA GUARD AND THE CLOSING CONTROL (`Q-*`)

| # | bar | registered |
|---|---|---|
| **Q-1** | **`fz2_replay` runs WITHOUT `--no-fabric-era-guard`** | after FLASH #18 the guard must **PASS**: the flashed receipt's inputs hash identical in the tree at HEAD, with `hdl/nec_test_ucore.qsf` the one declared §70.7 exemption.  **This is a REGISTERED CLAUSE — it is the point of re-flashing, and if the bypass is still needed that is a FINDING** |
| **Q-2** | the closing control | `fz2_replay --ledger <F18> --all-failures --pass-sample 150 --leg ret`, era guard **ON**.  **Registered: AGREEMENT ≥ 255/260** (F17 was 263/263 = 100 %).  Below that is a fidelity finding |
| **Q-3** | `fz2_w1 bars` | **11 / 11 MET**, leaf-diffed against the F17 archive; any verdict that moves is itemised |
| **Q-4** | `fz2_ledger --control --suffix=-F13-archive` | **PASS 9/9** — the derivation stays quotable.  ⚠ the reference is the **F13** archive, not "the previous era" (F17 §6's recorded mis-invocation) |
| **Q-5** | `fz2_ledger.CURRENT` | it points at **F17**.  **Registered action: move it to the F18 ledger in the results commit, and say so.**  Every invocation in this sitting passes `--ledger` explicitly until then |
| **Q-6** | `check_fuzz_bank` | **PASS at 621 seeds**, `gen_drift 0`, `regen_err 0` |
| **Q-7** | `r7_lint` · `ss_lint --core ucore` · `test_artifact` · `gen_ucore_qsf --check` | unchanged from §1 |

---

## 7. THE DIRECTED-CELL SPOT-CHECKS (`S-*`)

Both cells' board legs are **socket-only (`use_core=False`)**, so they measure
**SILICON**, which no bitstream can move.  Their banked directories are copied
aside before the run and **restored afterwards**, so the banked columns stay
byte-identical (the ack-wake sitting's own discipline).

| # | leg | registered |
|---|---|---|
| **S-1** | `tf0f_cell.py run --strata nop,x1b,z1b` (3 probes × 4 waits × 4 aligns = **48 cells**) | the CHIP column reproduces the banked board column **cell for cell**: `nop` **6**, `x1b` **8**, `z1b` **9**, every cell single-valued over its 6 traps.  **A chip move is a RIG-INTEGRITY FINDING, not a result** |
| **S-2** | `tf0f_cell.py score` on the merged board+core tables | **`chip == core` on all 48**, because KM landed: `x1b` core 9 → 8 onto the chip, `z1b` core 9 unmoved (SATURATION).  This is KM's fabric-era spot-check and it is the CORE column that is allowed to have moved |
| **S-3** | `ie_pinfall_cell.py run --limit <small>` | the CHIP column reproduces its banked values on every sampled cell; the six invariant columns (`wake_prefetch`, `rise`, `fall`, `t_ei`, `anchor_t1`, `n_rows`) stay **0-diff** on the free-running legs |
| **S-4** | `div_guard` on both legs | **0 UNPINNED**; `single_writer OK` before each |
| **S-5** | restoration | both `sw/testdata/{tf0f,ie-pinfall}/` trees byte-identical to HEAD afterwards, verified by sha256 |

**REGISTERED EXPECTATION, in one sentence: the chip columns are UNCHANGED
because silicon did not change, and the only permitted movement is in the CORE
columns where KM and phantom-T1 predict it.**

---

## 8. HARD STOPS

1. `hdl/rtl` differing between `98855f782c` and the tree at build time →
   **STOP before anything**.
2. **E-3** Fmax < 38.0 MHz, **E-4** worst setup ≤ 0, or **E-5** any non-zero
   TNS → **nothing is flashed**.
3. **E-6** the retention receipt self-labelling `CONTROL/DEFAULT` → **nothing is
   flashed**.
4. `safe_flash` **VERIFY failure** → **physical power cycle, no blind retry**.
5. **F-2** first light not MATCH 800 on all three legs → **STOP**.
6. Any `div_guard` **UNPINNED** readback → **rig-integrity FINDING, STOP**.
7. Any capture-integrity alarm (`G-1`…`G-5`) → **HALT and report; do not clear
   the alarm on the live population**.
8. **F-5** `use_core=0` chip proof not MATCH 800 after everything → **STOP**.
9. **S-1 / S-3**: a CHIP-column move on either directed cell → **rig-integrity
   FINDING, STOP** (it would mean the socket leg is not measuring what it was).

**Nothing is flashed except through `sw/safe_flash.sh` with its VERIFY leg.**

---

## Appendix A — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                   # 98855f782c
git diff 1ad5074ebe 98855f782c --stat -- hdl/rtl/    # 4 files, as sec.0

# the inertness proof (no board, no Quartus)
python3 - <<'PY'   # strip `ifndef SYNTHESIS, take the `ifdef arms, diff
PY
git show 6cbb01a642:hdl/rtl/system_large.sv          # the reference

L17=sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json

# the predictor (offline, cross-era -- SAY SO beside every number)
python3 sw/fz2_tbsys.py build --leg ret              # receipt 6e6589e25c2b90aa…
python3 sw/fz2_replay.py --ledger $L17 --all-failures --pass-sample 550 \
        --leg ret --jobs 8 --no-fabric-era-guard --out /tmp/f18_predict.json

# the build
python3 sw/quartus_gate.py                           # CONTROL, at HEAD
X1_AD_RETENTION=1 python3 sw/quartus_gate.py         # RETENTION, the one that flashes

# the flash
sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof
python3 sw/check_ab_hw.py all 800

# the corpus
python3 sw/fz2_w1.py control
python3 sw/fz2_w1.py preflight --board
python3 sw/fz2_w1.py capture
python3 sw/fz2_ledger.py --out sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json

# the closing control -- NO --no-fabric-era-guard (Q-1)
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8

# the directed-cell spot-checks (sec.7), banked dirs copied aside and restored
python3 sw/tf0f_cell.py run --strata nop,x1b,z1b ; python3 sw/tf0f_cell.py score
python3 sw/ie_pinfall_cell.py run --limit <small>  ; python3 sw/ie_pinfall_cell.py score

python3 sw/check_ab_hw.py chip 800                   # F-5
```

## Appendix B — THE SIX SEATS, IN ONE TABLE, FOR THE SCORER

| seat | landing | F17 `bad`/`first`/`flick` | **F18 registered** |
|---|---|---|---|
| `fz2c/404041` | KM | 2437 / 933 / 0 | **0 — LEAVES** |
| `fz2e/501066` | KM | 572 / 515 / 0 | **0 — LEAVES** |
| `fz2e/513019` | KM | 2843 / 656 / 0 | **0 — LEAVES** |
| `fz2c/404071` | phantom-T1 | 905 / 244 / 1 | **`bad` 1 (band 1-6), `first` 243, STAYS** |
| `fz2e/514044` | phantom-T1 | 1261 / 235 / 2 | **`bad` 1 (band 1-6), `first` 234, STAYS** |
| `fz2e/516001` | phantom-T1 | 1154 / 584 / 2 | **`bad` 1 (band 1-6), `first` 583, STAYS** |
