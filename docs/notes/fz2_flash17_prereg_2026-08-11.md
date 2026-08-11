# FLASH #17 — PRE-REGISTRATION

**Committed BEFORE any Quartus build and BEFORE any board contact.**  Branch
`fuzz-v2-on-relanding`, HEAD **`dbc8ffcdc1`**.  Board contact (flashing
included, `sw/safe_flash.sh` only) is authorised by the user for this sitting
("Flash and take stock", 2026-08-11).

---

## 0. WHAT THIS SITTING IS FOR, AND WHAT IT CANNOT SETTLE

The board carries **FLASH #16** (`.sof fed558c0e61173ae…`, flashed
2026-08-10T20:27:33Z, `flash_log.jsonl` **19 entries**).  Since then **exactly
one RTL delta landed**: **wave 4**, whose tip is `8280031c8d`.

    git diff --quiet 8280031c8d dbc8ffcdc1 -- hdl/rtl     ->  CLEAN  (verified, this sitting)

Waves 5, 6 and 7 (`15284289e9` … `dbc8ffcdc1`) are **doc-only bookings**; wave
5's package C was built and **reverted**, and waves 6 and 7 are refutations that
touched no RTL.  So the fabric question this sitting asks is exactly one
question: **does wave 4 do in silicon what it did offline?**

Wave 4 is TWO landings merged:

| commit | landing | offline closures |
|---|---|---|
| `0956c638dd` | the 8F ghost-read **ADDRESS** cone — `ghost_relax` DELETED, the AND unconditional | **2** |
| `abf9b8fb71` | **A P5′-stall** (`flush_cs`/`flush_cs_we` gated by `row_acts_ok`) + **B P4′-space** (the ghost read's I/O space from `pla3_native`'s own class one clock earlier) | **4 + 2** |

⚠ **THE MERGED TREE HAS NEVER HAD A G6 DRAW.**  Package A drew 38.39 MHz twice,
package B 39.55 twice, the ghost cone 39.05 twice — **all three on worktrees
based at `32128b57b4`, none of them carrying the other's edit.**  §2 draws the
merged tree for the first time.

### 0.1 ⚠ THE NOISE FLOOR GOVERNS EVERY AGGREGATE CLAIM IN THIS DOCUMENT

`docs/notes/fz2_capture_noise_2026-08-10.md` measured the socket-capture floor
on three complete passes over the same 3,840 seeds on ONE bitstream:

> **THE FLOOR IS 10 / 3,840 = 0.2604 % ledger-class flips.**  The CORE leg is
> bit-identical on 730/730.  All 12 non-arch socket movers have the
> terminator's `fired` count change.

That document's own instruction to this sitting is quoted verbatim and is
followed:

> **FOR WAVE 5: an aggregate corpus-headline delta below ~10 seeds is not
> resolvable by a single capture** … **A NAMED-seat prediction is safe**:
> P(a named seed is a noise flip) = 0.26 %, so F16's two-seat P-1 carried an
> expected 0.005 spoiled seats.  **Keep pre-registering seats; stop
> pre-registering headline floors to the seed.**

Wave 4's predicted aggregate delta is **8 seats — NEAR the floor.**  Therefore:

**THE REGISTERED CLAIM OF THIS SITTING IS THE EIGHT NAMED SEATS (§4.1).  THE
HEADLINE IS REGISTERED AS A BAND (§4.2) AND A RESULT INSIDE THAT BAND IS NOT
EVIDENCE FOR WAVE 4 AND WILL NOT BE QUOTED AS SUCH.**  The eight seats carry an
expected **0.021** spoiled seats at the measured floor; that is what makes them
quotable and the headline not.

---

## 1. THE OFFLINE MEASUREMENT THIS PRE-REGISTRATION IS BUILT ON

Stated in full because a prediction is only as honest as its provenance.  Before
this document was written, and with **no board contact and no Quartus**, the
faithful offline replay was run **on the merged tree** — the first time either
wave-4 landing has been scored beside the other:

```
python3 sw/fz2_tbsys.py build --leg ret          # up to date, receipt 251ded16c34b4212…
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json \
        --all-failures --pass-sample 550 --leg ret --jobs 8 --no-fabric-era-guard
```

⚠ **It carries `--no-fabric-era-guard` and this document says so beside every
number derived from it.**  The guard REFUSES at HEAD, correctly and by name:

    its inputs  86/88 hash IDENTICAL in the tree at HEAD
      MOVED     hdl/nec_test_ucore.qsf   [EXEMPT: §70.7]
      MOVED     hdl/rtl/ucore/v30u_eu.sv   <-- RTL
    ERA MISMATCH -- REFUSING TO SCORE.

**Result, 654 seeds, 50 s, 0 errors, `tb_sys` receipt `251ded16c34b4212…`:**

|  | replay PASS | replay FAIL |
|---|---:|---:|
| fabric PASS (538) | **538** | **0** |
| fabric FAIL (116) | **8** | 108 |

**8 CLOSED, 0 LOST**, and the 8 are exactly the 8 seats the two landings
registered.  This is the predictor; **silicon is the test.**

Standing offline gates re-measured at HEAD before this document:
`gen_ucore_qsf --check` **PASS (up to date)** · `r7_lint` **PASS — 0 undeclared
carriers, 0 undeclared unresolved, 3 tainted, 51 `stop` sites, 0 violations** ·
`ss_lint --core ucore` **PASS — 103 BIU + 122 EU = 226, 214 flops, 0 UNMAPPED** ·
`test_artifact` **45/45, NON-VACUOUS**.

---

## 2. THE BUILD — G6 (`E-*`)

Two configurations, **ONE clean draw each** (the RTL is wave-4's already-drawn
tree; the campaign's two-draw norm applies to an RTL *landing*, and this is a
*flash*).  `db` / `incremental_db` / `output_files_ucore` deleted before each.

**Order is fixed: CONTROL first, at HEAD, then RETENTION.**  The RETENTION
build is what flashes — matching FLASH #16's configuration.

| # | bar | registered |
|---|---|---|
| **E-1** | `gen_ucore_qsf.py --check` BEFORE each draw | PASS (measured PASS at HEAD at registration) |
| **E-2** | 0 errors, every stage `Successful`, 0 latches, 0 `lpm_divide` | both draws |
| **E-3** | `divclk` Fmax | **≥ 32 MHz**, both draws |
| **E-4** | worst setup slack | **> 0 ns**, both draws |
| **E-5** | TNS setup **AND** hold | **0.000 on every domain**, both draws |
| **E-6** | the RETENTION receipt **self-labels RETENTION** | `configuration` begins `RETENTION (X1_AD_RETENTION=1) -- DERIVED from …`, `configuration_detail.retention == true` |
| **E-7** | the CONTROL receipt self-labels `CONTROL/DEFAULT` | derived, not asserted |
| **E-8** | `gen_ucore_qsf.py` regenerated and re-checked AFTER each draw | PASS |
| **E-9** | the macro's effect is CHECKED, not asserted | the retention `.rbf` sha256 **differs** from this tree's CONTROL `.rbf` sha256 |
| **E-10** | both receipts retained in `sw/testdata/receipts/quartus_bitstream.jsonl` | ids quoted with every figure |

**E-6 IS A HARD STOP if the retention receipt reads `CONTROL/DEFAULT`** (the
`4bb65d2ab6` defect); the bitstream may not be flashed on it.
**E-3 is the other hard stop.**

### 2.1 THE Fmax PREDICTION — REGISTERED AS AN EXPECTATION, NOT A BAR

**No point estimate and no bar beyond E-3.**  `standing_gates.md` §A governs:
one green build is not closure, and the same tree has drawn 19.42 and 45.91 MHz.
What is registered is a **reporting obligation** and one soft expectation:

* **This branch's CONTROL draws, in order**: 39.16 · 39.37 · 39.47 · 39.63 ·
  39.81 · 40.11 · 40.42, then wave 4's three worktrees — **38.39** (pkg A, twice)
  · **39.05** (ghost cone, twice) · **39.55** (pkg B, twice).
* **REGISTERED EXPECTATION (soft): the merged CONTROL draw lands in 38.0–40.5
  MHz.**  Outside that band it is reported as an observation, not a stop.
  Below 32 MHz it is a **HARD STOP** and nothing is flashed.
* **REGISTERED REPORTING OBLIGATION — the retention-vs-control sign.**  On this
  branch retention has drawn **ABOVE** control **four consecutive times**
  (FLASH #13 +0.46, #14 +1.50, #15 +2.24, #16 +0.12).  A-1.1a's falsifier has
  four of four.  **This sitting will state the sign of (retention − control)
  explicitly and it is the FIFTH observation regardless of which way it falls.**

---

## 3. THE FLASH AND FIRST LIGHT (`F-*`)

| # | bar | registered |
|---|---|---|
| **F-1** | `sw/safe_flash.sh <ucore .sof>` — PREP / `quartus_pgm` / VERIFY | VERIFY OK; `sw/testdata/flash_log.jsonl` **19 → 20 entries**, tail `verify: "OK"` |
| **F-2** | first light `check_ab_hw.py all 800` | **MATCH over 800 rows on all three legs** (chip-vs-golden, core-vs-chip, core-vs-golden), `rc 0` |
| **F-3** | RBCHECK (`fz2_w1.py control`) | **exactly 8 registers** round-trip: `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, `TVEC`, `VECCTL` |
| **F-4** | C-6 control (`fz2_w1.py control`) | **9 legs / 51 checks / 51 PASS**, `holds_proved [2, 20, 300]`, `pins_proved [pin_int, pin_nmi]`, `tvecs_proved [[0,48896],[3056,8]]`, P1–P5 run lengths **2 · 300 · 2 · 300 · 20**, N1 negative control PASS |
| **F-5** | `use_core=0` chip proof **after everything** | `check_ab_hw.py chip 800` → **MATCH over 800 rows** |
| **F-6** | `div_guard()` tally | **0 UNPINNED** — that is the bar; the count is reported, not barred |
| **F-7** | transport | **0 `RigMismatch`**, 0 quarantines, 0 transport errors |
| **F-8** | `board_idle()` | clean, `use_core = 0` left selected |
| **F-9** | single-writer / socket-only | `single_writer OK`, `use_core False` on every socket leg — checked before first contact |

**F-2 justification, registered in advance.**  Wave 4's three mechanisms are
(i) a CS write published on the clock its row acts (`8E /1 MOV CS,rm` at a
retarget boundary), (ii) the 8F ghost read's address AND, and (iii) the 8F ghost
read's I/O space.  **The boot program contains no `MOV CS,rm` and no `8F` with
`mod == 3`**, so none of the three is reachable by it and **MATCH 800 is the
correct prediction.**  Any deviation is a **HARD STOP**.

**F-4 is scored on its VERDICTS, not on row sha256** — two `control` runs on the
same flash give differing row sha256s and 51/51 both times (FLASH #13's
registered erratum).  Row-sha movement is **not** a stop.

---

## 4. THE SEAT-LEVEL PREDICTIONS (`P-*`)

**Reference ledger: FLASH #16's** — `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json`,
116 failures, denominator 3,838, matched 3,722, era `.sof fed558c0e611…`.
Membership is `bad_rows != 0`; `arch` is REPORTED, not a membership criterion.

### 4.1 — **P-1: THE EIGHT SEATS CLOSE, SEED FOR SEED.  THIS IS THE SITTING'S CLAIM.**

Every row's "predicted" column is the faithful offline replay of §1
(`--no-fabric-era-guard`).  **All eight are predicted to leave the ledger
(`bad_rows == 0`).**

| # | seat | family | mechanism | `first_bad_row` F16 | `diverging_rows` F16 → predicted |
|---|---|---|---|---:|---|
| 1 | `fz2e/519016` | E1 | **ghost ADDRESS** (`ghost_relax` deleted) | 236 | **2 → 0** |
| 2 | `fz2e/520040` | E1 | **ghost ADDRESS** | 253 | **4 → 0** |
| 3 | `fz2e/520062` | D3 | **P5′-stall** | 700 | **2966 → 0** |
| 4 | `fz2e/528008` | D3 | **P5′-stall** | 628 | **3197 → 0** |
| 5 | `fz2e/532012` | D3 | **P5′-stall** | 328 | **4 → 0** |
| 6 | `fz2e/533028` | D3 | **P5′-stall** | 881 | **12 → 0** |
| 7 | `fz2e/527055` | E2 | **P4′-space** | 655 | **4 → 0** |
| 8 | `fz2e/528030` | E2 | **P4′-space** | 423 | **9 → 0** |

**P-1 REGISTERED: all eight leave the ledger.  Scored SEAT BY SEAT, and the
per-seat result is the sitting's headline.**

**P-1a — the four P5′-stall seats are the sitting's principal uncertainty, and
the reason is on the record.**  At FLASH #16 these same four were registered as
**staying failing** (F16 P-2) and they did, with their row counts landing on the
faithful replay's values (43 → 2966, 3192 → 3197, 4 → 4, 2976 → 12).  Wave 4's
package A is the landing booked to close them.  **The instrument that predicted
their F16 behaviour correctly is the same instrument predicting their closure
now** — which is why they are quotable seats, not a hope.

**P-1b — `fz2e/532012` and `fz2e/527055` are the low-signal seats.**  Both close
from **4** diverging rows.  A 4-row seat is inside the class the noise floor
moves (`fz2_capture_noise` measured movers at 1,189–3,312 rows, so a 4-row seat
is *below* the observed noise magnitude, but its ledger MEMBERSHIP flip is
exactly the class the 10/3,840 counts).  **Registered: a closure on
`fz2e/532012` or `fz2e/527055` alone is weaker evidence than one on
`fz2e/520062` or `fz2e/528008`** (2,966 and 3,197 rows), and the results
document will say so rather than counting all eight equally.

### 4.2 — **P-2: THE HEADLINE, REGISTERED AS A BAND BEFORE CAPTURE**

|  | FLASH #16 (measured) | FLASH #17 (registered) |
|---|---|---|
| corpus seeds | 3,840 | 3,840 |
| discards (`ps3_8080`) | 2 | **2 predicted; a re-roll is itemised, not a stop** (§5, G-6) |
| denominator | 3,838 | **3,838** |
| **failures** | **116** | **PRIMARY POINT 108** |
| **failures, REGISTERED BAND** | — | **98 ≤ failures ≤ 118  (108 ± 10)** |
| matched | 3,722 = 96.9776 % | **3,730 = 97.1861 % (point)** |
| Σ `diverging_rows` over the ledger | 123,084 | **118,662 (point)** |

**±10 is the measured socket-capture floor**, 10/3,840 ledger-class flips
(`fz2_capture_noise_2026-08-10.md`), **registered here BEFORE the capture and
not derived from it.**

⚠ **HOW THIS BAR MAY AND MAY NOT BE QUOTED.**  The band is **10/8 = 1.25× the
effect**.  It is therefore registered as a **containment check, not as
evidence**:

* a result **inside** the band **says nothing about wave 4** and will not be
  quoted as confirming it;
* a result **outside** the band is a **finding** and is investigated;
* the evidence for wave 4 is **P-1, seat by seat**, and nothing else.

**P-2a — the ROW metric is predicted to IMPROVE, and its two known costs are
registered in advance.**  Σ `diverging_rows` over the 116 F16 failures is
predicted **123,084 → 118,662 (−4,422)**, dominated by the two big P5′ closures.
It is a NET figure over two opposing effects and **the cost half is named
here**: the ghost-address landing was measured **+1,841 rows** on its own
population, of which **1,801 are two seeds W-2 named IN ADVANCE as seats the AND
does not govern** — `fz2e/518039` (102 → **1,587**) and `fz2e/526054`
(4 → **320**).  **Both are registered as still-failing with those row counts;
neither is a loss and neither is hidden inside the net.**

### 4.3 — **P-3: ZERO LOSSES, ON A BUDGET**

**Registered: no seed matched at FLASH #16 becomes a failure through a wave-4
mechanism.**  The faithful replay measured **LOST 0 over 654 seeds** (538/538
fabric-PASS seeds still PASS).

The budget, registered before capture:

* **new failures ≤ 10** (the floor).  **Every one is itemised** — seed, family,
  `first_bad_row`, tier, whether its CHIP leg moved, and whether its CORE dump
  moved.
* **ATTRIBUTION IS REGISTERED AS A DICHOTOMY, NOT AS AN EXCUSE.**  A new failure
  is attributed to **wave 4** — a landing-level finding — if it carries any of:
  a `MOV CS,rm` (`8E /1`) at a retarget boundary; an `8F` with `mod == 3` within
  six `F` pops of its fork row; or a fork on an I/O-vs-memory status cell.
  Otherwise it is a **noise candidate**, and calling it noise requires the
  positive evidence the floor document itself used: **the CORE leg unchanged**
  (bit-identical dump) **and/or** the terminator's `fired` count moved.
  **"Not obviously wave 4" is NOT an attribution and will not be written.**
* **more than 10 new failures, or ANY new failure carrying a wave-4 mechanism,
  is a FINDING reported as such.**

### 4.4 — **P-4: NO UNREGISTERED CLOSURE**

**Registered: exits from the ledger are EXACTLY the eight of §4.1.**  Any other
exit is itemised with the same dichotomy as P-3 (a wave-4 mechanism at its F16
fork row, or the noise evidence).  Unregistered exits also count against the
same **10-seed** noise budget — the budget is on **total unregistered ledger
membership flips, entries and exits together**, not on entries alone.

### 4.5 — **P-5: `fz2c/404040` MUST NOT APPEAR**

The branch's sharpest falsifier — a banked SUCCESS whose silicon refuted the
`C2` sitting's registered form.  **It was ABSENT at FLASH #16 and is ABSENT from
the F16 ledger.**  If it is a failure at FLASH #17, wave 4 has broken a
mechanism nobody claimed, and that is a **landing-level finding**, not a noise
candidate.

### 4.6 — **P-6: THE FIRST-DIVERGENCE MOVES ARE REGISTERED, INCLUDING THE 19 THAT GO EARLIER**

⚠ **THIS SITTING DOES NOT REGISTER "NO FIRST-DIVERGENCE DECREASE".**  The
ghost-address landing's `W-4` bar asked for exactly that and was **REFUTED — 19
still-failing seeds move earlier** — and re-registering a bar that is already
known to fail would be dishonest.  Instead the **19 are named here in advance**
and the bar is on everything else.

**REGISTERED: the 43 still-failing seeds in Appendix A move as tabulated (row
counts and first-divergence rows), and the 19 marked in bold move EARLIER.**
Row counts are reported, not barred (downstream noise moves them).
**The bar is: no still-failing seed OUTSIDE Appendix A's 19 has its
`first_bad_row` decrease.**  Any such decrease is itemised.

### 4.7 — **P-7: THE FAMILY TABLE**

Predicted movement, from §4.1's eight seats and nothing else:

| ledger family | F16 | predicted F17 |
|---|---:|---:|
| **D3 both fetched, different address** | 8 | **4** |
| **E1 same-status data cycle, different address** | 41 | **39** |
| **E2 different-status data cycle** | 4 | **2** |
| all twelve others | (unchanged) | (unchanged) |
| **total** | **116** | **108** |

### 4.8 — **P-8: THE THREE NON-CLOSING SEATS THE WAVE ALREADY BOOKED**

Registered as **still failing**, because their landings said so before this
sitting.  A closure on any of the three is an **instrument finding** about the
faithful replay and is reported as one.

| seat | landing | booked reason | F16 rows → predicted |
|---|---|---|---|
| `fz2e/520066` | B P4′-space | its announcement is **LATCHED** (`r_cmt_bs`), so a predicate fixing what the EU publishes cannot reach it (w4 §2.4) | 8 → **8, UNMOVED** |
| `fz2c/410028` | B P4′-space | space fork closed; **re-forks 10 rows later on a `qs` cell**, family A1/A2, a different mechanism (w4 §2.3) | 433 → **426**, first 2994 → **3004** |
| `fz2c/410008` | ghost ADDRESS | **the ghost row IS fixed** — `first_bad` moves PAST the fork row — and the seed keeps failing 6 rows later (w4-ghost §3.2) | 4 → **4**, first 1192 → **1198** |

---

## 5. THE CORPUS RE-CAPTURE (`G-*`)

Archive by rename first — the SUP discipline, **nothing deleted**:

    sw/testdata/campaigns/fz2c          -> fz2c-F16-archive
    sw/testdata/campaigns/fz2e          -> fz2e-F16-archive
    sw/testdata/fz2/fz2_capture.json    -> fz2_capture_F16-archive.json
    sw/testdata/fz2/fz2_bars.json       -> fz2_bars_F16-archive.json
    sw/testdata/fz2/fz2_preflight.json  -> fz2_preflight_F16-archive.json
    sw/testdata/fz2/fz2_control.json    -> fz2_control_F16-archive.json

then `fuzz_campaign.py new fz2c` / `new fz2e` (re-pins each manifest to the
resident flash), `fz2_w1.py preflight --board`, `fz2_w1.py capture`.
**Same driver as the F16 ledger's own provenance.**

| # | bar | registered |
|---|---|---|
| **G-1** | corpus identity unchanged | `SEED_LIST_SHA256 = 45d25f31a325c496…`, 48 strata, `fz2c` 960 + `fz2e` 2,880 = **3,840** |
| **G-2** | preflight | `verdict: "OK"`, `board_leg: true`, **0 GEN_DRIFT** on the regeneration sample |
| **G-3** | capture completeness | **48 / 48 strata**, `rc 0`, no `halted`, `results.jsonl` **960 / 2,880** rows |
| **G-4** | retained captures | **NOT BARRED — reported.**  Retention on the enriched tier is divergence-driven and eight seats closing lowers it.  The bar is only that **every seed named in any prediction above is still retained and scored** |
| **G-5** | the flash pin | every result row's `era.sof_sha256` = FLASH #17's `.sof` sha256; **`distinct_eras 1`, `absent 0`, `incomplete 0`, `build_stale 0`** over 3,840 |
| **G-6** | discards | **2** predicted, denominator **3,838**.  `_ps3_8080` is a **SOCKET-leg** predicate (A-2) that a core landing cannot move by construction; a re-roll is **itemised loudly, seed by seed, with its `escaped_n`**, the denominator moves with it, and the rate is reported on **both** bases (A-12/A-13).  **NOT a hard stop and NOT a ratchet violation** |

**IF THE CAPTURE STOPS ITSELF ON AN INTEGRITY ALARM, THIS SITTING HALTS AND
REPORTS.  Alarms are not cleared on the live population.**

---

## 6. THE ERA GUARD AND THE CLOSING CONTROL (`Q-*`)

| # | bar | registered |
|---|---|---|
| **Q-1** | **`fz2_replay` runs WITHOUT `--no-fabric-era-guard`** | after FLASH #17 the guard must **PASS**: the flashed receipt's inputs hash identical in the tree at HEAD, with `hdl/nec_test_ucore.qsf` the one declared §70.7 exemption.  **If the bypass is still needed, that is a FINDING and is reported as one** |
| **Q-2** | the closing control | `fz2_replay --ledger <F17> --all-failures --pass-sample 150 --leg ret`, era guard **ON**.  **Registered: AGREEMENT ≥ 260/266** — FLASH #16's was 266/266 = 100 %, and the offline column now differs from the F16 fabric column by exactly the eight seats, so a fresh-era control is the honest re-measurement.  Below 260 is a fidelity finding |
| **Q-3** | `fz2_w1 bars` | **11 / 11 MET**, leaf-diffed against the F16 archive; any verdict that moves is itemised |
| **Q-4** | `fz2_ledger --control` | the derivation stays quotable against an archived corpus |
| **Q-5** | `fz2_ledger.CURRENT` | it points at **F15** and is **two eras stale** (booked at w4-ghost §6).  **Registered action: move it to the F17 ledger in the results commit, and say so.**  Every invocation in this sitting passes `--ledger` explicitly until then |

---

## 7. HARD STOPS

1. `hdl/rtl` differing between `8280031c8d` and HEAD → **STOP before anything**
   (checked: CLEAN).
2. **E-3** Fmax < 32 MHz, **E-4** worst setup ≤ 0, or **E-5** any non-zero TNS →
   **nothing is flashed**.
3. **E-6** the retention receipt self-labelling `CONTROL/DEFAULT` → **nothing is
   flashed**.
4. `safe_flash` **VERIFY failure** → **physical power cycle, no blind retry**.
5. **F-2** first light not MATCH 800 on all three legs → **STOP**.
6. Any `div_guard` **UNPINNED** readback → **rig-integrity FINDING, STOP**.
7. Any capture-integrity alarm (`G-1`…`G-5`) → **HALT and report; do not clear
   the alarm on the live population**.
8. **F-5** `use_core=0` chip proof not MATCH 800 after everything → **STOP**.

**Nothing is flashed except through `sw/safe_flash.sh` with its VERIFY leg.**

---

## Appendix A — THE 43 PREDICTED MOVERS AMONG THE 108 STILL-FAILING SEEDS

From the §1 faithful replay (`--no-fabric-era-guard`).  Row counts are
**reported, not barred**.  **Bold `first_bad_row` = predicted to move EARLIER
(19 seeds); these are the only ones exempt from P-6's bar.**

| seed | family | `diverging_rows` F16 → predicted | `first_bad_row` F16 → predicted |
|---|---|---:|---|
| `fz2c/404049` | A3 cycle-time slip (non-qs) | 1637 → 1636 | 221 → 221 |
| `fz2c/404071` | C2 INTA-vectored delivery | 906 → 905 | 244 → 244 |
| `fz2c/405025` | A3 cycle-time slip (non-qs) | 1092 → 1090 | 215 → 215 |
| `fz2c/406063` | E1 same-status data cycle, different address | 3168 → 3149 | **249 → 245** |
| `fz2c/407064` | B1 HALT-cycle address | 1000 → 998 | 1947 → 1947 |
| `fz2c/407065` | A1 qs-pop one clock late | 424 → 422 | 3053 → 3053 |
| `fz2c/408019` | E1 same-status data cycle, different address | 1087 → 1086 | 1617 → 1617 |
| `fz2c/408068` | D2 core fetched, chip did not | 401 → 405 | **432 → 426** |
| `fz2c/409065` | A3 cycle-time slip (non-qs) | 8 → 16 | **1544 → 1534** |
| `fz2c/410008` | E1 same-status data cycle, different address | 4 → 4 | 1192 → 1198 |
| `fz2c/410028` | C3 NMI(vec2) entry | 433 → 426 | 2994 → 3004 |
| `fz2e/501069` | E1 same-status data cycle, different address | 1960 → 1959 | 1547 → 1547 |
| `fz2e/509036` | A1 qs-pop one clock late | 786 → 783 | 562 → 562 |
| `fz2e/510043` | E1 same-status data cycle, different address | 2259 → 2238 | 971 → 971 |
| `fz2e/514044` | C2 INTA-vectored delivery | 1263 → 1261 | 235 → 235 |
| `fz2e/514072` | D2 core fetched, chip did not | 938 → 936 | 326 → 326 |
| `fz2e/515047` | A3 cycle-time slip (non-qs) | 955 → 952 | 410 → 410 |
| `fz2e/516001` | C2 INTA-vectored delivery | 1156 → 1154 | 584 → 584 |
| `fz2e/516066` | A3 cycle-time slip (non-qs) | 390 → 387 | 1811 → 1811 |
| `fz2e/518039` | C1 vector-1 trap MISSED by core | **102 → 1587** | **2371 → 2363** |
| `fz2e/518050` | E1 same-status data cycle, different address | 2561 → 2560 | 748 → 748 |
| `fz2e/518053` | E1 same-status data cycle, different address | 3409 → 3413 | **571 → 567** |
| `fz2e/520000` | E1 same-status data cycle, different address | 834 → 836 | **642 → 502** |
| `fz2e/520005` | D1 chip fetched, core did not | 2866 → 2870 | **491 → 484** |
| `fz2e/521016` | D3 both fetched, different address | 14 → 16 | **362 → 352** |
| `fz2e/521049` | A3 cycle-time slip (non-qs) | 6 → 14 | **2168 → 2150** |
| `fz2e/522003` | E1 same-status data cycle, different address | 404 → 403 | 3164 → 3164 |
| `fz2e/522029` | E1 same-status data cycle, different address | 60 → 32 | 377 → 785 |
| `fz2e/523045` | A1 qs-pop one clock late | 397 → 396 | 3040 → 3040 |
| `fz2e/524030` | E1 same-status data cycle, different address | 2611 → 2610 | 352 → 352 |
| `fz2e/525017` | A3 cycle-time slip (non-qs) | 4 → 12 | **1167 → 1141** |
| `fz2e/526054` | E1 same-status data cycle, different address | **4 → 320** | **279 → 265** |
| `fz2e/527008` | D3 both fetched, different address | 2177 → 2183 | **938 → 929** |
| `fz2e/530017` | D2 core fetched, chip did not | 1668 → 1670 | **1448 → 1440** |
| `fz2e/530020` | D1 chip fetched, core did not | 667 → 671 | **304 → 296** |
| `fz2e/530046` | D1 chip fetched, core did not | 2068 → 2084 | **1402 → 1345** |
| `fz2e/530070` | C4 other-vector delivery | 1749 → 1753 | **2233 → 2225** |
| `fz2e/531030` | D1 chip fetched, core did not | 343 → 342 | 3218 → 3218 |
| `fz2e/532000` | D1 chip fetched, core did not | 2998 → 3001 | **434 → 426** |
| `fz2e/533025` | E1 same-status data cycle, different address | 1039 → 1041 | 1678 → 1678 |
| `fz2e/534062` | D2 core fetched, chip did not | 1267 → 1271 | **1291 → 1271** |
| `fz2e/535004` | D1 chip fetched, core did not | 808 → 807 | **1138 → 1131** |
| `fz2e/535036` | E1 same-status data cycle, different address | 4 → 4 | 1708 → 1716 |

⚠ **Two of the four §64.1 counter-population seeds — `fz2c/406063` and
`fz2e/518053` — are IN this table and are predicted to move earlier.**  The
§64.1 four are therefore **NOT registered as frozen at this flash**, and saying
otherwise would have been a bar this tree already knows to be false.

---

## Appendix B — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                  # dbc8ffcdc1
git diff --quiet 8280031c8d dbc8ffcdc1 -- hdl/rtl   # CLEAN

L16=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json

# the predictor (offline, cross-era -- SAY SO beside every number)
python3 sw/fz2_tbsys.py build --leg ret
python3 sw/fz2_replay.py --ledger $L16 --all-failures --pass-sample 550 \
        --leg ret --jobs 8 --no-fabric-era-guard --out /tmp/f17_predict.json

# the build
python3 sw/quartus_gate.py                          # CONTROL, at HEAD
X1_AD_RETENTION=1 ...                               # RETENTION, the one that flashes

# the flash
sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof
python3 sw/check_ab_hw.py all 800

# the corpus
python3 sw/fz2_w1.py control
python3 sw/fz2_w1.py preflight --board
python3 sw/fz2_w1.py capture
python3 sw/fz2_ledger.py --out sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json

# the closing control -- NO --no-fabric-era-guard (Q-1)
python3 sw/fz2_replay.py --ledger sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json \
        --all-failures --pass-sample 150 --leg ret --jobs 8

python3 sw/check_ab_hw.py chip 800                  # F-5
```
