# FLASH #21 — RESULTS, AS REGISTERED: **THE NULL HOLDS ON 105 OF 106 SEATS, AND THE THREE PLACES IT DOES NOT ARE NAMED**

Pre-registration `docs/notes/fz2_flash21_prereg_2026-08-13.md`, committed
**`325b2092d7`** — **before any Quartus build and before any board contact** —
together with `sw/f21_wt1.py`, the clause-(v)/(vi) scorer, **proved non-vacuous
on the banked FLASH #20 captures before the board was touched**.

Every bar is reported in the form it was registered in. **Nothing is
re-registered after the fact. A miss is a miss.**

    branch      master
    HEAD        25b2f9bb69 -> prereg 325b2092d7 (the built tree)
    the delta   hdl/nec_test.sdc (the enable-phase split, E-1 deleted, the
                k=0.5 class removed) + hdl/rtl/ucore/{v30u_eu,v30u_biu,
                v30_core}.sv (CHAIN_MAX 12->7, L1, the negedge removal)
    bitstream   nec_test_ucore.sof a84577f6499f132d…
                nec_test_ucore.rbf a9667cf1aa6d3715…
                RETENTION (X1_AD_RETENTION=1), draw@seed1
    flash log   23 -> 24 entries, VERIFY ok try 1, 2026-08-14T04:04:40Z

---

## 0. THE HEADLINE

**THE M10K MICROCODE IS TRUE IN FABRIC.** The first bitstream ever to hold this
part's decode in a block RAM boots and runs the whole corpus. **N-1 PASS** on
the flashed build's own `db` — 8192 × 12 and 1028 × 29, **every word** — with
its non-vacuity control FAILing on one flipped bit in the same sitting.
**N-2 first light MATCH 800 ×3.**

**THE NULL HOLDS WHERE IT CAN BE READ MOST SHARPLY.** Of the 106 FLASH #20
seats, **105 are shared and all 105 reproduce EXACTLY — 0 movers, both
`diverging_rows` AND `first_bad_row`.** The 528-cell directed grid is
**527 / 528 byte-identical** to FLASH #20's fabric column, and the one differing
cell differs only in one repetition's raw stream hash on a cell marked
`stable: False` in **both** eras, with every scored observable identical.

**AND IT DOES NOT HOLD IN THREE PLACES, ALL ITEMISED, NONE ARGUED AWAY.**
**C-4 POINT MISSED**: **107 failures of 3,838**, registered 106 of 3,839. Two
seeds entered (`fz2e/513024`, `fz2e/526056`), one left (`fz2e/527051`), and one
new `ps3_8080` discard appeared (`fz2e/514037`). **C-5 MISSED, 3 flips of a
10-seed budget.** ⚠ **The two entrants are NOT capture noise**: the offline
core reproduces them at the **identical `first_bad`** (Q-2, 257/257).

**THE ROW METRIC RECONCILES TO ZERO.** Σ`diverging_rows` **100,493 → 103,803**,
and that is **+991 + 3,232 − 913** exactly. **Zero unexplained rows over 3,840
seeds and 11.3 million compared rows.**

**CLAUSES (v) AND (vi) ARE MET, AND (vi) IS MET IN ITS STRONGEST FORM.** On
**42,288 write-T1 rows**: the ADDRESS sample agrees with silicon on
**36,874 / 36,874 = 100 %**, the DATA sample holds the write word into T2 on
**42,288 / 42,288**, the turnaround has completed by T2 on **42,288 / 42,288**,
and V-B's clean-row residue is **4 — the same four `ad_data` rows, seed for seed
and position for position, that the FLASH #20 baseline had.**

**V-A MISSED, AND THE MISS IS THE SITTING'S BEST FINDING.** 41 write-T1 rows
moved across the era, **all in one seed and all in one column (`ps`)**. Widened
to every row of every shared capture: the core column moved on **318 rows in 2
seeds**, and **every single one moved TOWARD silicon — 150 / 150 on `ps` and
160 / 160 on `ad_addr`, with 0 away.** None of it lands on a row the corpus
comparator scores, which is why 105 seats did not move.

**G6 REPRODUCED ITS EXPECTED NEIGHBOURHOOD TO THE DIGIT ON BOTH LEGS**:
CONTROL **42.06 / +7.473 / 10,053** and RETENTION **43.30 / +8.156 / 10,079**,
with both `.rbf`s **byte-identical to the ce/ce_half re-land's own draws**.

---

## 1. THE BUILD — G6, ONE DRAW PER CONFIGURATION

Quartus 17.1.0 Build 590. Each leg from a deleted `db` / `incremental_db` /
`output_files_ucore`. **Per the seeds ruling: this compile VERIFIES THE LANDING.
No band, no spread, no worst-of-N and no Fmax claim is made.**

| | **CONTROL `draw@seed1`** | **RETENTION `draw@seed1` (FLASHED)** |
|---|---|---|
| verdict | **PASS** | **PASS** |
| receipt | `654f2784753352af…` | **`c60e7fcf00319254…`** |
| distribution record | `12257ab3a8d82fad…` | `3984053dbb58e717…` |
| configuration (**DERIVED**) | `CONTROL/DEFAULT` | **`RETENTION (X1_AD_RETENTION=1)`** |
| **Fmax (`divclk`)** | **42.06** | **43.30** |
| **worst setup** | **+7.473** | **+8.156** |
| **TNS setup / hold** | **0.000 every domain, both directions** | **0.000 every domain, both directions** |
| hold slacks | +0.253 / +0.264 / +0.357 / +0.426 | +0.255 / +0.268 / +0.360 / +0.396 |
| ALMs | **10,053 / 41,910 (24 %)** | **10,079 / 41,910 (24 %)** |
| fit registers | 5,953 | 5,819 |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `002f2fa4728ecac9…` | `002f2fa4728ecac9…` |
| **`.rbf` sha256** | **`3d4700c0b0453ee3…`** | **`a9667cf1aa6d3715…`** |
| `.sof` sha256 | `4a3054789e49bbc1…` | **`a84577f6499f132d…`** |
| core-domain (**gates nothing**) | 62.39 (`CE4`, k=4.0) | 61.12 (`CE4`, k=4.0) |
| compile | 641 s | 572 s |

| # | bar | verdict |
|---|---|---|
| E-1 | `gen_ucore_qsf --check` before each draw | **MET** — clean on both |
| E-2 | 0 errors, every stage Successful, 0 latches, 0 `lpm_divide` | **MET** ×2 |
| E-3 | Fmax ≥ 32.0 (G6) and ≥ 38.0 (the live STOP) | **MET** — **+5.30 MHz above the STOP** on the worse leg |
| E-4 | worst setup > 0 every domain | **MET** ×2 |
| E-5 | **TNS 0.000 setup AND hold, every domain** | **MET** ×2 |
| E-6 | the RETENTION receipt self-labels RETENTION | **MET — DERIVED** from `flow.rpt` + `map.rpt`, never from the flag |
| E-7 | the CONTROL receipt self-labels `CONTROL/DEFAULT` | **MET — DERIVED** |
| E-8 | the RETENTION `.rbf` DIFFERS from CONTROL's | **MET** — `a9667cf1…` ≠ `3d4700c0…` |
| E-9 | the manifest reads `002f2fa4728ecac9…` on both | **MET** ×2 |
| E-10 | the fitter honoured `--seed=1`, **both readings** | **MET** — `Info: Command:` **1** and the `Fitter Initial Placement Seed` row **1**, on both legs |
| E-11 | receipts retained, labelled `draw@seed1` | **MET** |

### 1.1 THE EXPECTED NEIGHBOURHOOD — REGISTERED AS NOT-A-BAR, AND HIT EXACTLY

| | expected (not a bar) | **measured** |
|---|---|---|
| CONTROL | 42.06 / +7.473 / 10,053, `.rbf` `3d4700c0b0453ee3…` | **42.06 / +7.473 / 10,053, `.rbf` byte-identical** |
| RETENTION | 43.30 / +8.156 / 10,079, `.rbf` `a9667cf1aa6d3715…` | **43.30 / +8.156 / 10,079, `.rbf` byte-identical** |

Two independent sittings, two checkouts, the same 88-file manifest, the same
seed — **and the same bitstream byte for byte on both configurations.** ⚠ This
is **not** a characterised distribution and `standing_gates.md` §A still
governs: the same tree has drawn 19.42 and 45.91 MHz. ⚠ The retention-vs-control
sign is **inverted again (+1.24 MHz)**; **reported, not explained, and not
computed as a delta from a draw pair.**

### 1.2 THE BINDING CONE IS THE M10K NOW, AND THAT IS NEW

The CONTROL leg's whole-design worst path launches from
`v30u_ucrom|altsyncram:ucdecode_rtl_0|…|ram_block1a4~PORT_A_WRITE_ENABLE_REG`
into `nec_bus|ad_in_q[8]`. **The microcode block RAM is the binding endpoint on
this draw** — the thing L1 created. On the RETENTION leg it binds
`v30u_eu|modrm_reg[1] → nec_bus|ad_in_q[3]` instead, with the M10K binding the
core domain. Recorded, **not** turned into a claim: one draw each.

**The SDC re-derivation is confirmed on this netlist too**: the `ENABLE` class
reads **141.20 MHz** (CONTROL) / **142.13** (RETENTION) where the deleted
`k = 0.5` class held it at 90.91.

---

## 2. **N-1 AND N-2 — THE M10K BAR, DISCHARGED**

| # | bar | measured | verdict |
|---|---|---|---|
| **N-1** | `ucrom_mif_check` PASS on the **flashed** build's own `db` | **PASS** — `ram0_…f358d0ef.hdl.mif` **8192 × 12** vs `ucdecode.hex`, **every one of 8192 words identical** (1,656 non-zero); `ram1_…f358d0ef.hdl.mif` **1028 × 29** vs `ucrom.hex`, **every one of 1028 words identical** | **MET** |
| **N-1b** | the non-vacuity control, same sitting | one flipped bit at address 8191 → **`[BAD] … DIFFER 1 word(s), first [8191]`, `@8191: mif 0x1 vs hex 0x0`**, then restored and **PASS** re-confirmed | **MET** |
| **N-2** | first light `check_ab_hw all 800` | **MATCH ×3** — chip-vs-golden, core-vs-chip, core-vs-golden | **MET** |

⚠ **A TOOL FINDING, REPORTED NOT PATCHED**: `ucrom_mif_check.py` **prints
`FAIL` and exits 0**. Its verdict is in its text, not its exit status, so a
caller that tests `$?` would read a corrupted microcode table as a pass. It was
run and read by eye here, and the non-vacuity control is what makes that
readable. *Registered falsifier for the repair*: the tool exits non-zero on any
`[BAD]` table.

**The M10K's own evidence, beyond N-1**: first light MATCH ×3, the whole 3,840-seed
corpus, the 528-cell grid at **FABRIC vs CORE 528/528**, and `check_ab_hw chip
800` at close-out. **A silently empty table cannot produce any of those.**

---

## 3. THE FLASH

| # | bar | measured | verdict |
|---|---|---|---|
| **F-1** | VERIFY OK, `flash_log.jsonl` 23 → 24 | **ok try 1**, **24 entries**, tail `verify: "OK"`, `.sof` `a84577f6499f132d…` | **MET** |

Single writer asked before first contact (`no v30/serve process on the board ->
SINGLE WRITER`) and again inside `preflight`; `--force` never used.

---

## 4. THE CORPUS

`fz2_w1 control` → `preflight --board` → `capture` → `fz2_ledger`, all on
FLASH #21, scored against the FLASH #20 ledger.

| # | bar | registered | measured | verdict |
|---|---|---|---|---|
| **C-1** | corpus identity | 3,840, 48 strata, lint PASS | **as registered**; `fz2_w1 lint` **PASS / 0 hits / 48 stratum rows** | **MET** |
| **C-2** | completeness | 48/48 strata, every `rc 0` | **48 / 48, every `rc 0`, 960 + 2,880, 11.6 min** | **MET** |
| **C-3** | the flash pin | `distinct_eras` 1 | **`distinct_eras` 1 · `absent` 0 · `incomplete` 0 · `build_stale` 0** over 3,840, era `a84577f6499f…` | **MET** |
| **C-4** | **THE NULL** | **106 / 3,839**, band [96, 116] | **107 / 3,838** | **POINT MISSED (+1 failure, −1 denominator), BAND MET** |
| **C-5** | membership flips | **0 entered, 0 left**, budget 10 | **ENTERED 2 · LEFT 1** = **3 flips** | **MISSED, 3 of a 10-seed budget — §4.1** |
| **C-6** | **the seat table** | digest `a6085ccc0dc739a2…`, 106/106 | digest **`c79a41282d08c53a…`** — **DIFFERS**; but **105 / 105 shared seats EXACT, 0 movers in either column** | **DIGEST MISSED; the seat-for-seat clause MET on all 105** |
| **C-7** | direction | 0 LOST, 0 `first_bad` EARLIER | **2 LOST** (the entrants); **0 `first_bad` earlier** anywhere | **MISSED on LOST; MET on EARLIER** |
| **C-8** | the row metric | Σ`div` 100,493 | **103,803**, reconciling to **0 unexplained rows** — §4.2 | **as registered** |
| **C-9** | discards | 1, denominator 3,839, **not barred** | **2** (`fz2e/509069` + **`fz2e/514037`**), denominator **3,838** | **reported, not barred — a SOCKET-leg predicate** |

Corpus headline fields: seed match **97.2121 %** (was 97.2389), row match
**99.0844 %** (was 99.1136), rows compared **11,330,674**.

### 4.1 **C-5 — THE THREE FLIPS AND THE DISCARD, ITEMISED**

| seed | tier | F20 | F21 | `escaped_n` | what it is |
|---|---|---|---|---:|---|
| `fz2e/513024` | soup | **absent** | `bad` 991, `first_bad` 703, `func:R@28`, arch 14 registers differ | 0 | **ENTERED.** No F20 capture was retained (it was clean), so **it was never in the offline zero-behaviour population** |
| `fz2e/526056` | raw | **absent** | `bad` 3,232, `first_bad` 755, `KNOWN_ACCEPTED cadence`, `STALLED` | 2 | **ENTERED.** Same — no retained F20 capture |
| `fz2e/527051` | raw | `bad` 913, `first_bad` 156, D3 | **SUCCESS / clean** | **31** | **LEFT.** FLASH #20's own one unexplained row-count mover (1,003 → 913). **Third distinct value in three eras**, and it is a heavily `escaped` seed — the caveat registered in §0.2 |
| `fz2e/514037` | soup | not a failure, not a discard | **DISCARD** (`ps3_8080`), `bad` 988, `first_bad` 703 | 0 | `_ps3_8080` is a **SOCKET-leg** predicate (A-2) that **no RTL change can reach**. Sixth consecutive era it has moved: 2 → 2 → 3 → 1 → 3 → 1 → **2** |

⚠ **THE TWO ENTRANTS ARE CORE-DETERMINISTIC, NOT CAPTURE NOISE, AND THIS
SITTING CANNOT ATTRIBUTE THEM.** Q-2's offline replay reproduces **both at the
identical `first_bad`** (`NEW/UNCLASSIFIED 6 / 6, 100 %`). So they are what this
RTL does, not what a capture did once. **What is NOT established is whether the
FLASH #20 RTL also failed them offline** — they had no retained F20 capture, so
they were absent from the 306-seed population on which L1 and the negedge
removal were measured byte-identical, and no leg in this sitting looks at the
old tree. ***Registered falsifier***: replay `fz2e/513024` and `fz2e/526056`
against a `3118a2db46` checkout's `tb_sys ret`. If that tree fails them too,
they were fabric-passing at FLASH #20 by luck and the landings are exonerated;
if it passes them, one of the four landings is not zero-behaviour and the
measurement that said it was had a hole in its population. **Booked, not
guessed, and no repair attempted in this sitting.**

### 4.2 **C-8 — THE ROW METRIC RECONCILES TO ZERO**

    Sum diverging_rows   F20 100,493  ->  F21 103,803

    fz2e/513024 ENTERED                  +  991
    fz2e/526056 ENTERED                  +3,232
    fz2e/527051 LEFT                     -  913
    the 105 shared seats                 +    0
    -------------------------------------------
    reconciled prediction                103,803
    measured                             103,803
    UNEXPLAINED                                0 rows

**Zero unexplained rows over 3,840 seeds and 11,330,674 compared rows**, and the
`+ 0` line is the substance: **not one of the 105 shared seats moved a single
row.**

### 4.3 THE NAMED NON-MOVERS — **20 / 20, VALUE FOR VALUE**

| # | group | verdict |
|---|---|---|
| **C-10** | KM's three (`fz2c/404041`, `fz2e/501066`, `fz2e/513019`) | **ABSENT** — **MET** |
| **C-11** | phantom-T1's three | `fz2c/404071` **1 / 243** · `fz2e/514044` **1 / 234** · `fz2e/516001` **1 / 583** — **MET** |
| **C-12** | §64.1's four | **840 / 527** · **921 / 1331** · **891 / 636** · **984 / 1475** — **MET** |
| **C-13** | W7-4's surviving two | `fz2c/410047` **3589 / 227** · `fz2e/535027` **3226 / 296** — **MET** |
| **C-14** | M10's LEA-mod3 six | **3141/470 · 1087/1617 · 194/429 · 3075/396 · 3479/457 · 20/442** — **MET**; `fz2e/520066` **8 / 1249** unmoved (regression check only) |
| **C-15** | **the falsifier** | **`fz2c/404040` ABSENT** — **MET** |

And the two seeds FLASH #20 registered to get worse are unmoved as this sitting
registered them: `fz2c/406063` **3,165 / 249**, `fz2e/528010` **7 / 1383**.

### 4.4 `fz2_immaterial falsify` (C-16)

| # | registered | measured | verdict |
|---|---|---|---|
| **C-16a** | class **22**, COSMETIC 17 · TRANSIENT 5, 0 entrants, 0 leavers | **22 members, COSMETIC 17 · TRANSIENT 5**; G7's member rows all agree with the document, so **membership is unchanged seed for seed** | **MET** |
| **C-16b** | FUNCTIONAL 44 · TIMING 30 · TRANSIENT 5 · COSMETIC 17 · UNSCOREABLE 10 = 106 | **46 · 29 · 5 · 17 · 10 = 107** | **MISSED — and it is C-4's arithmetic**: **+2 FUNCTIONAL** = the two entrants, **−1 TIMING** = `fz2e/527051` (D3) leaving |
| **C-16c** | G1–G8 **all PASS**, exit 0 | **G1 · G2 · G3 · G4 · G5 · G8 PASS** with correct denominators; **G6 3 / 8 and G7 1 / 23 FAIL**, every disagreement being doc (44 / 30 / 106 / 84) vs derivation (46 / 29 / 107 / 85) | **MISSED — pure document staleness, caused by C-4's one net failure** |
| **C-16d** | `528010` COSMETIC at 7; `409065` 12 · `521049` 10 · `525017` 8 COSMETIC; `408021` 22 TRANSIENT | **all five exactly**, `408021` still carrying `bs=12` | **MET** |

⚠ This is **FLASH #20's C-15e in reverse**. There the census document was one
era stale and the miss was registered in advance; here it was re-pinned to the
F20 era and I registered it to PASS, so the corpus's one net failure makes it
fail. **The document is not edited in this sitting** — a document edit on the
day it is load-bearing is what this campaign's rules distrust. Booked.

---

## 5. **CLAUSES (v) AND (vi) — THE PIN THIS WAVE MOVED**

`sw/f21_wt1.py`, committed with the pre-registration. **42,288 write-T1 rows**
(MEMW + IOW, `t == 1`), 647 retained captures.

| # | clause | registered | **measured** | verdict |
|---|---|---|---|---|
| **V-A** | core, era vs era, whole-record | **0 differing** | **41 differing of 42,129**, 0 membership moved, 0 length mismatches | **MISSED — §5.1** |
| **V-B** | core vs the socketed part, clean rows | **≤ 4** | **4 of 36,874** — **the same four rows as the baseline, seed for seed and position for position** | **MET** |
| **VI-A** | ADDRESS sample vs silicon | **100 %** | **36,874 / 36,874 = 100 %, 0 disagreements** | **MET** |
| **VI-B** | DATA sample | `data_moves` 0, ≤ 4 chip | **42,288 / 42,288 hold the write word into T2, `data_moves` 0**; chip **36,870 / 36,874** (the same 4) | **MET** |
| **VI-C** | the control | **0 not-turned** | **42,288 / 42,288 turned by T2, 0 not-turned** | **MET** |

**V-B's four are `fz2c/406046` @3525 · `fz2e/521016` @361 · `fz2e/529009` @907 ·
`fz2e/531039` @1011, all `ad_data` alone** — the identical four the FLASH #20
baseline had, at identical positions. **The residue did not grow and it did not
move.**

**VI-C is what makes VI-A mean something.** VI-A says the address-phase sample
is not the write word; VI-C says the *next row's* address-phase sample **is**
the write word. Same predicate, opposite answer, one row apart, both at 100 %.
**The bus turns around, and it turns around between T1 and T2 and not inside
T1 — on silicon, on 42,288 write cycles, with the flop moved half a CPU clock
later in time.** The offline argument was about a rig; this is not.

⚠ **REPORTED, NOT BARRED**: 7 of the 42,288 rows have `(ad_addr & 0xFFFF) ==
ad_data`, and all 7 also carry the 20-bit `(ps << 16) | ad_data` signature —
because a write whose word equals its own address low half is indistinguishable
from an early turnaround **by construction** (`fz2c/409014` writes 0xcccc to
0x0cccc). The pre-registration measured this and declined to bar it. **An
actually-early turnaround is 42,288 rows, not 7.**

### 5.1 **V-A's 41 — THE MISS, AND IT IS THE SITTING'S BEST FINDING**

All 41 are **one seed** (`fz2e/519072`) and **one column** (`ps`). Widened from
write-T1 rows to **every row of all 644 shared captures**:

| | measured |
|---|---|
| core column rows where `ps` moved | **150**, in **2 seeds** (`fz2e/519072`, `fz2e/528000`) |
| core column rows where `ad_addr` moved | **168**, the same 2 seeds |
| **DIRECTION, on rows where the chip did NOT move** | **`ps`: 150 TOWARD silicon, 0 AWAY.  `ad_addr`: 160 TOWARD silicon, 0 AWAY** (8 more where the chip moved too) |
| where the `ad_addr` movement sits | **almost all at `t == 0` (Ti)** — 93 CODE, 32 IOW, 18 T4, 13 MEMW; `diff_rows` reads `ad_addr` only at T1 |

**318 rows moved and every one of them moved toward the socketed part.** A
random capture perturbation is directionless; this is not. And it lands where
the comparator does not look — `ps` is read only at T2, `ad_addr` only at T1 —
which is exactly why **105 seats did not move while the core column did.**

**The mechanism was predicted in writing before the board was touched.**
`t1_half2_anatomy_2026-08-13.md`'s status block: the address latch used to
sample on *the same edge* the flop flipped on and *"the address survived by NBA
ordering in RTL and by clock-to-Q in fabric"*; at `ce_half`+1.0 *"it now
survives unambiguously… the one place this change is an improvement rather than
a neutral simplification."* **That is what 318 / 318 toward silicon looks like.**

⚠ **AND IT IS AN ATTRIBUTION, NOT A PROOF.** Four landings were flashed as a
bundle; this sitting cannot say which one. What it can say is that the movement
exists, is one-directional, is confined to two seeds, and matches a mechanism
written down in advance.

⚠ **The CHIP column moved `ps` on 1,768 rows across the two captures** — the
socketed part's own run-to-run variation on a column no gate scores, reported
for scale so the 150 is read against it.

---

## 6. THE DIRECTED-CELL SPOT-CHECKS

| # | leg | measured | verdict |
|---|---|---|---|
| **S-1** | `tf0f_cell` 48 cells + `score` | **all 128 banked board captures decode IDENTICAL — 0 chip-column movers**; chip == core **0 / 512 on all six columns**; **KM 16/16 derivation and 14/14 validation legs**, the only key surviving on every one, and 16/16 + 14/14 against the core; stability **0 TAKE-unstable, 0 stream-distinct**; 0 transport errors | **MET** |
| **S-2** | `ie_pinfall_cell` 40 cells + `score` | **`board/table.json` BYTE-IDENTICAL to the bank (`3b2bf686…`)**; of the 40 re-captured cells, **40 / 40 identical, 0 moved**; the six invariant columns `wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows` **0 / 1,920**; the core table is the re-derived **`963a8065eb94b49c…`** by hash | **MET on 0 chip movers — with a registration erratum, §6.1** |
| **S-3** | `ghost_pred_cell run` / `run --fabric` / `core` + `f20_cell` | **socket 528 / 528 BYTE-IDENTICAL** to the FLASH #20 bank (`768967794c03bd86…`); **CHIP vs FABRIC 398 / 122**, the registered numbers, **15 distinct signatures**; **FABRIC vs CORE 528 / 528 identical, 0 differing**; **F21 fabric vs F20 fabric 527 / 528** — §6.2; 0 transport errors, 0 GHOST-unstable, `div_guard` PINNED on every probe | **MET** |
| **S-4** | restoration | all three banks copied aside first and **restored byte-identical — `git status` on `sw/testdata/{tf0f,ie-pinfall,ghost-pred}` is EMPTY**; the F21 rows retained **beside** them at `sw/testdata/{tf0f,ie-pinfall}-f21-spotcheck/` and `sw/testdata/ghost-pred-f21/` | **MET** |

⚠ **`ghost_pred_cell core` is still off the artifact layer** (FLASH #20 §8,
booked). The pre-registration's mitigation was applied: **`artifact.require()`
was called BY HAND on both `tb_sys` legs before the core column was taken** —
`obj_dir_sys/Vtb_sys` receipt `0b015811cd4596df…`, `obj_dir_sys_ret/Vtb_sys`
receipt `dcbcf5c372151744…`, both rebuilt at HEAD through the declared build
first. **The FLASH #20 stale-binary trap did not recur, and it did not recur
because the sitting spent 20 seconds on a rebuild rather than trusting a
directory listing.**

### 6.1 ⚠ **AN ERRATUM IN MY OWN REGISTRATION — S-2's SCALARS**

I registered `n_inta` **36**, `ack_off` **46**, `ack_off_hlt` **46** by copying
FLASH #20's numbers, **while registering in the same document that the core
column at HEAD is the re-derived `963a8065eb94b49c…` one.** Those two clauses
are mutually inconsistent: FLASH #20's scalars were scored against the
**pre**-re-derivation core table. Measured here: **30 / 40 / 40**, deterministic
given two byte-identical tables. **Reported as an erratum in the registration,
not as a deviation in the measurement** — the substantive bar, **0 chip-column
movers**, is MET and is what the clause was written for. (The `v_inc`
denominator precedent, FLASH #20 §2.2.)

⚠ **AND A TOOL FINDING**: `ie_pinfall_cell run --strata X --limit 20`
**overwrites the stratum's raw file with only the freshly captured cells** —
`eihlt_w0` went 219 → 20 and `ierun_w0` 112 → 20 on disk — while the merged
`table.json` is preserved intact. Nothing was lost (S-4 copied the banks aside
first and restored them), and **all 20 shared cells in each file were
identical**. Booked; not patched in a sitting that is measuring with it.

### 6.2 **THE FABRIC COLUMN ACROSS TWO BITSTREAMS — 527 / 528**

`ghost-pred-f20/fabric-f20` vs this sitting's `fabric`: **1 cell of 528
differs**, `alu88_w0_a0`, and it differs **only in `rep_shas[0]`**, the raw
stream hash of the first of three repetitions. Every scored observable is
identical — `ghost_addr`, `ghost_label`, `mode_*`, `n_rows`, `memr`, `n_code`.
**The cell carries `stable: False` in BOTH eras**: its own three repetitions
disagree on both bitstreams, so it is a known-unstable cell and not a mover.

**527 / 528 byte-identical across a bitstream that changed the microcode's
implementation, tightened the constraints twice, cut `CHAIN_MAX` nearly in
half, and moved a pin in time.**

---

## 7. THE ERA GUARD AND THE CLOSING CONTROL

| # | bar | measured | verdict |
|---|---|---|---|
| **Q-1** | era guard PASS, no bypass — **and REFUSING before the flash** | **It REFUSED at HEAD before the flash**, by name: *"its inputs 82/88 hash IDENTICAL"*, naming `hdl/nec_test.qsf`, `hdl/nec_test.sdc`, `v30_core.sv`, `v30u_biu.sv`, `v30u_eu.sv` as MOVED and `nec_test_ucore.qsf` as the declared §70.7 EXEMPT. After the flash it **PASSES with no bypass** | **MET in both halves** |
| **Q-2** | closing control ≥ 99 %, `first_bad` identical | **257 / 257 = 100.0 %** — fabric PASS 150 / replay PASS 150 · fabric FAIL 107 / replay FAIL 107 · **`first_bad` IDENTICAL on 107 / 107**; **100 % in every family, every wait mode and both stimulus classes** | **MET in the strongest available form** |
| **Q-3** | close-out | `check_ab_hw chip 800` **MATCH over 800 rows**, `use_core=0`; **`div_guard` PINNED on 100 % of probes, 0 unpinned**; `board_idle` **OK, use_core=0 left selected** | **MET** |

Q-1's refusal is not a formality: it is the check that the guard can still say
no. It named five files and the one declared exemption, and after the flash the
same invocation passes at 88/88.

---

## 8. THE STANDING GATES ON THIS ERA (C-17)

| gate | result |
|---|---|
| `fz2_w1 bars` | **11 / 11 MET** — C-6 `hold_rows_exact` **4,638** / `hold_rows_off` **0**; C-4 `distinct_eras` 1; C-5 `gen_drift` 0 / `wvec_mismatch` 0; **C-8 `div_guards` 63 / unpinned 0**; C-9 192 stable / 0 unstable; C-10 0 quarantines / 0 run-error lines; C-1 rate clauses validated on `fz2v`/960 |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 control` (C-6 board legs) | **MET — 9 legs**, holds **[2, 20, 300]** proved on `pin_int` and `pin_nmi`, TVECs `(0, 48896)` and `(3056, 8)`, **N1 negative control PASS**, `div_guards` 10 / unpinned 0 |
| `fz2_w1 preflight --board` | **OK** — single writer, era pinned to receipt **`c60e7fcf0031…`** self-labelling RETENTION, **192-seed regeneration sample 0 hits**, RBCHECK **8 registers**, MATCH 800 ×3 |
| `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| `r7_lint` | **PASS** — 0 undeclared carriers, 3 declared tainted, **51 `stop` sites, 0 violations** |
| `ss_lint --core ucore` | **PASS — `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8** (BIU 109 + EU 122). ⚠ census **221** flops, not FLASH #20's 220: L1's **`dec_q`** is a real flop and is **WHITELISTED as DERIVED**, not mapped. **The map did not move and `SS_VERSION` did not move** |
| `gen_ucore_qsf --check` | **PASS** ×3 |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `check_ab_hw all 800` / `chip 800` | first light **MATCH ×3**, again inside `preflight`; close-out **MATCH over 800 rows** |
| §38.9 missed-trap overlay | **4** — the same four as FLASH #18, #19 and #20 |

⚠ **NOT RUN AND NOT QUOTED**, as registered: `timed_scenario`,
`timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`
(`gen_seq._v1_anchor_stop`); `x1_retention` / `x1_fabric` (GEN-DRIFTED), so
**the 283-cell HLT sweep column does not exist for this bitstream**; the four v1
fuzz banks (SUP-1 / D9).

### 8.1 HOUSEKEEPING (H-1)

The F20 era's `fz2_bars` / `fz2_capture` / `fz2_control` / `fz2_preflight`
JSONs were archived to `*_F20-archive.json` **before** the F21 capture
overwrote them, and `fz2c` / `fz2e` were archived **by rename** to
`*-F20-archive` before `fuzz_campaign.py new` re-pinned both manifests to
FLASH #21. **Nothing was deleted.**

---

## 9. HARD STOPS

**NONE FIRED.**

RETENTION `draw@seed1` **43.30 ≥ 38.0** · **N-1 PASS on the flashed `db`** · the
RETENTION receipt self-labelled RETENTION and its `.rbf` differed from
CONTROL's · `safe_flash` VERIFY **ok try 1** · **0 `div_guard` UNPINNED anywhere
in the sitting** · **0 `RigMismatch`, 0 quarantines, 0 run-error lines, 0
transport errors** · single writer asked before first contact and again in
preflight, `--force` never used · first light MATCH 800 ×3 · **S-3's socket
column 528/528 byte-identical** · `ss_lint` at 0x8E / 232 · closing chip proof
MATCH 800 · `board_idle()` clean and **last**.

**The registered non-stops, reported with their denominators**: C-4's point
(+1 failure, −1 denominator, inside a [96,116] band), C-5's three flips (of a
10-seed budget), C-6's digest (with 105/105 shared seats exact beneath it),
C-7's two LOST, C-9's discard re-roll, C-16b/C-16c's document staleness, V-A's
41 rows, and §6.1's S-2 registration erratum.

---

## 10. WHAT THIS SITTING ESTABLISHED, AND WHAT IT LEAVES OPEN

**ESTABLISHED**

1. **The microcode runs from an M10K in fabric.** N-1 PASS word for word on the
   flashed build's own `.mif`, with a non-vacuity control, plus first light,
   the whole corpus, and 528/528 FABRIC vs CORE. The bar L1 owed is discharged.
2. **Four landings — two constraint changes and two RTL changes, one of which
   moves a pin in time — leave 105 of 106 corpus seats at their exact values in
   both columns**, and the row metric reconciles to **zero unexplained rows**.
3. **The turnaround lands in the right place on silicon**: 100 % address-sample
   agreement over 36,874 clean rows, 42,288 / 42,288 on both structural
   predicates, and the T2 control at 100 % that stops VI-A being passable by a
   bus that never turns.
4. **The 528-cell directed grid is 527/528 across the two bitstreams**, and
   FABRIC vs CORE is 528/528 against a core column re-taken at HEAD on a
   receipt-verified binary.
5. **The era is re-synced**: the guard REFUSED before the flash by name and
   PASSES at 88/88 after it, with the closing control at 100.0 %.
6. **G6 reproduced a second sitting's draws to the digit and to the bitstream
   byte on both configurations.**

**OPEN, WITH THEIR FALSIFIERS**

1. **The two entrants are unattributed** (§4.1). *Falsifier*: replay
   `fz2e/513024` and `fz2e/526056` against a `3118a2db46` checkout's
   `tb_sys ret`. **This is the sitting's single most important open item** — it
   is the difference between "the offline zero-behaviour population had a hole
   in it" and "one of these four landings is not zero-behaviour."
2. **The 318-row toward-silicon movement is attributed to a bundle, not a
   landing** (§5.1). *Falsifier*: the same two seeds' `ps` / `ad_addr` columns
   on a `tb_sys` built from each landing in turn.
3. **`ucrom_mif_check` prints FAIL and exits 0** (§2). *Falsifier*: it exits
   non-zero on any `[BAD]` table.
4. **`ie_pinfall_cell run --limit N` truncates the stratum's raw file** (§6.1).
   *Falsifier*: it merges rather than replaces.
5. **`ghost_pred_cell core` is still off the artifact layer** (FLASH #20 §8),
   worked around by hand again rather than fixed.
6. **The IMMATERIAL census document is one era stale again** (C-16c),
   deliberately not edited in the sitting that measured it.
7. **`fz2e/527051` has now read three different values in three eras** on a
   heavily `escaped` seed, and nothing explains the class.

**AND WHAT THIS SITTING CANNOT ESTABLISH**: which of the four landings did
anything. They were flashed as a bundle and **a bundle's benefit is not
evidence for any member of it**. It also measures no Fmax: one draw per
configuration, by ruling.

---

## Appendix A — THE BAR IN ONE TABLE

| clause | registered | measured | verdict |
|---|---|---|---|
| E-1 … E-11 | G6 green both legs, manifest `002f2fa4…`, `.rbf`s differing | all, both legs | **MET** |
| **N-1** | `ucrom_mif_check` PASS on the flashed `db` | **PASS**, 8192 + 1028 words | **MET** |
| **N-1b** | non-vacuity control FAILs | **FAIL on one flipped bit**, restored | **MET** |
| **N-2** | first light MATCH 800 ×3 | **MATCH ×3** | **MET** |
| F-1 | VERIFY OK, log 23 → 24 | **ok try 1, 24 entries** | **MET** |
| **C-4** | **106 / 3,839** | **107 / 3,838** | **POINT MISSED, BAND MET** |
| **C-5** | 0 entered, 0 left, budget 10 | **2 entered, 1 left** | **MISSED, inside budget** |
| **C-6** | digest `a6085ccc…`, 106/106 | digest differs; **105 / 105 shared EXACT** | **DIGEST MISSED, seats MET** |
| C-7 | 0 LOST, 0 earlier | **2 LOST, 0 earlier** | **MISSED / MET** |
| C-8 | Σ`div` 100,493 | **103,803, 0 unexplained** | as registered |
| C-9 | discards 1 | **2** (socket-leg) | reported, not barred |
| C-10 … C-15 | 20 non-movers, `404040` ABSENT | **20 / 20, ABSENT** | **MET** |
| C-16a / C-16d | class 22, the five seats | **22, all five** | **MET** |
| C-16b / C-16c | 44/30/106; G1–G8 PASS | **46/29/107**; G6 3/8, G7 1/23 | **MISSED — doc staleness** |
| **V-A** | 0 differing | **41**, one seed, one column | **MISSED — §5.1** |
| **V-B** | ≤ 4 | **4, the same four** | **MET** |
| **VI-A** | 100 % | **36,874 / 36,874** | **MET** |
| **VI-B** | `data_moves` 0, ≤ 4 | **0 and 4** | **MET** |
| **VI-C** | 0 not-turned | **0 of 42,288** | **MET** |
| S-1 | 0 chip movers | **128 / 128 identical, 0 / 512** | **MET** |
| S-2 | 0 chip movers | **table byte-identical, 40 / 40** | **MET** (§6.1 erratum) |
| S-3 | 398/122, 528/528, socket byte-identical | **all three** | **MET** |
| S-4 | banks restored byte-identical | **`git status` empty** | **MET** |
| Q-1 | guard PASS, no bypass | **82/88 REFUSED pre-flash, 88/88 PASS after** | **MET** |
| Q-2 | ≥ 99 %, `first_bad` identical | **257 / 257 = 100.0 %, 107 / 107** | **MET** |
| Q-3 | chip proof, PINNED, idle | **MATCH 800, 0 unpinned, idle OK** | **MET** |

## Appendix B — REVIEWER RE-RUN

```bash
git rev-parse HEAD                                   # 325b2092d7
python3 sw/ucrom_mif_check.py                        # N-1 (needs that build's db)

python3 - <<'PY'                                     # the seat comparison
import json
A={f['seed']:f for f in json.load(open('sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json'))['failures']}
B={f['seed']:f for f in json.load(open('sw/testdata/fz2/fz2_failure_ledger_f21_2026-08-13.json'))['failures']}
sh=sorted(set(A)&set(B))
print('shared', len(sh), 'moved',
      sum(1 for s in sh if (A[s]['diverging_rows'],A[s]['first_bad_row'])
                        != (B[s]['diverging_rows'],B[s]['first_bad_row'])))
print('entered', sorted(set(B)-set(A)), 'left', sorted(set(A)-set(B)))
PY
# shared 105 moved 0 / entered ['fz2e/513024','fz2e/526056'] left ['fz2e/527051']

python3 sw/f21_wt1.py --ledger sw/testdata/fz2/fz2_failure_ledger_f21_2026-08-13.json
python3 sw/f21_wt1.py --before-suffix -F20-archive --after-suffix -F20-archive \
        --ledger sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json --self-test --null 5
python3 sw/f20_cell.py --chip sw/testdata/ghost-pred-f21/board-f21 \
        --fabric sw/testdata/ghost-pred-f21/fabric-f21 \
        --core  sw/testdata/ghost-pred-f21/core-head-f21 \
        --chip-ref sw/testdata/ghost-pred-f20/board-f20      # 528/528 · 398/122 · 528/0
python3 sw/fz2_replay.py --report sw/testdata/fz2/fz2_replay_f21.json    # 257/257
python3 sw/fz2_immaterial.py --ledger sw/testdata/fz2/fz2_failure_ledger_f21_2026-08-13.json falsify
python3 sw/fz2_w1.py bars ; python3 sw/fz2_w1.py lint ; python3 sw/check_fuzz_bank.py
python3 sw/ss_lint.py --core ucore ; python3 sw/r7_lint.py ; python3 sw/test_artifact.py
```

**A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT BE QUOTED AGAINST THIS
TREE.**

---

> **COORDINATOR NOTE (2026-08-13, post-sitting).** §"Two things to flag" item 1
> — the commit `54849ca0c7` this sitting reported as UNEXPLAINED — is the
> coordinator's: the sitting's own `fz2_idle.json` board-idle record, left
> unstaged at the sitting's close, was committed by the session coordinator
> with the message "board-idle record from the FLASH #21 close (the sitting's
> own last write)". The sitting was right to report an unattributed commit
> rather than guess; the attribution is now on the record. No hook, no
> automation — a human-supervised coordinator action.
