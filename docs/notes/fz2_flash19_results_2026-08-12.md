# FLASH #19 — RESULTS, AS REGISTERED: **E-1's FABRIC CONFIRMATION, ALONE**

Pre-registration `docs/notes/fz2_flash19_prereg_2026-08-12.md`, committed
**`fc0ae65d56`** — **before any Quartus build and before any board contact** —
together with its scorer `sw/f19_b2.py`, which was **proved non-vacuous on a
null before the board was touched**.

Every bar is reported in the form it was registered in. **Nothing is
re-registered after the fact.**

    branch      fuzz-v2-on-relanding, HEAD a37f05d4b8 -> prereg fc0ae65d56
    RTL         git diff 770c0d1b85 HEAD -- hdl/rtl/ sim/   ->  EMPTY
                (checked before the build AND before the flash)
    the delta   hdl/nec_test.sdc, and nothing else that a compiler reads

---

## 0. THE HEADLINE

**E-1 IS TRUE IN FABRIC ON EVERY LEG THAT CAN SEE IT.** First light **MATCH 800
on all three legs**; the 283-cell sweep column taken through the FPGA core is
**row-for-row IDENTICAL to the offline Verilated column, 283 / 283, 0 differing
rows**; the closing `use_core=0` chip proof is **MATCH 800**; and the fabric era
guard now passes at **88 / 88 with no bypass**. The offline-vs-fabric replay
control is **264 / 264 = 100.0 %** with `first_bad` identical on all 114.

**G6 REPRODUCED ITS POINT PREDICTION EXACTLY, IN A DIFFERENT CHECKOUT, ON ALL
FOUR DRAWS**: CONTROL **44.72 MHz / +8.887 ns / 12,224 ALMs** twice and
RETENTION **45.71 / +8.081 / 12,200** twice, with **both `.rbf`s byte-identical
to E-1's own isolated-worktree builds**. `--retention`'s first flash-bound
exercise met both of its registered effect-checks.

**THREE CLAUSES MISSED AND THEY ARE ALL ONE EVENT.** The corpus headline read
**114 failures of 3,837**, not the registered **110 of 3,839** (`C-4` point
MISSED, band MET); **four seeds entered the ledger and two more flipped the
`ps3_8080` discard predicate** (`C-5` MISSED, 6 of a 10-seed budget); and
`fz2_w1 bars` read **10 / 11 with C-6 MISSED** on a single directive
(`C-13` MISSED). **All six movers are the same event**: their first divergences
fall in a **17-row band, 681–697**, and C-6's single failing directive belongs
to one of them.

**AND THE SITTING MEASURED WHAT THAT EVENT IS RATHER THAN ARGUING IT.** A
**second capture of the six affected strata on the SAME BITSTREAM, minutes
later**, returns **all six movers to `bad_rows` 0 / `SUCCESS`** — to their FLASH
#18 values field for field — while **474 of the 480 re-captured seeds do not
move at all**. The six are **not reproducible on one bitstream**. §4.6 states
exactly how far that licenses an attribution and where it stops.

**A FINDING THE SITTING HAD TO MAKE BEFORE IT COULD STATE ITS OWN BAR**, written
into the pre-registration rather than discovered afterwards: **`x1_retention`
and `x1_fabric` are GEN-DRIFTED on this branch** and join the four `timed_*`
ratchets that cannot be quoted here. §2.1. The bar was re-derived onto a
**sharper** comparison before the build, and the sitting then **repaired the
measurement** with a reference that does not drift — **silicon** (§2.3).

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS, TWO DRAWS EACH

Quartus 17.1.0 Build 590. Each draw from a deleted `db` / `incremental_db` /
`output_files_ucore`. **Worst-of-2 is the figure; all four draws were clean.**

| | **CONTROL draw 1** | **CONTROL draw 2** | **RETENTION ret1** | **RETENTION ret2 (flashed)** |
|---|---|---|---|---|
| verdict | **PASS** | **PASS** | **PASS** | **PASS** |
| receipt | `1d3c3221459e3370…` | `6c9319833090f4aa…` | `64a346ed7e4d9e7d…` | **`dba7c75533bc0f79…`** |
| configuration (**derived**) | `CONTROL/DEFAULT` | `CONTROL/DEFAULT` | **`RETENTION (X1_AD_RETENTION=1)`** | **`RETENTION (X1_AD_RETENTION=1)`** |
| **Fmax (`divclk`)** | **44.72** | **44.72** | **45.71** | **45.71** |
| **worst setup** | **+8.887** | **+8.887** | **+8.081** | **+8.081** |
| **TNS setup / hold** | 0.000 every domain | 0.000 every domain | 0.000 every domain | 0.000 every domain |
| ALMs | 12,224 (29 %) | 12,224 (29 %) | 12,200 (29 %) | 12,200 (29 %) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `b2e50a482ca1123b…` | `b2e50a482ca1123b…` | `b2e50a482ca1123b…` | `b2e50a482ca1123b…` |
| **`.rbf` sha256** | **`5b8695463675f732…`** | **`5b8695463675f732…`** | **`bcb48f01adf3e94d…`** | **`bcb48f01adf3e94d…`** |
| `.sof` sha256 | `3913c0605332ccc6…` | — | `73cc800232768328…` | **`03365b1115e1f338…`** |
| compile | 569 s | 607 s | 678 s | 647 s |
| git | `fc0ae65d56` | `fc0ae65d56-dirty` | `fc0ae65d56-dirty` | `fc0ae65d56-dirty` |

| # | bar | verdict |
|---|---|---|
| E-1 | `gen_ucore_qsf --check` before each draw | **MET** — *"up to date"* on all four |
| E-2 | 0 errors, every stage Successful, 0 latches, 0 `lpm_divide` | **MET** ×4 |
| E-3 | Fmax ≥ 32 (G6) and ≥ 38.0 (the live STOP) | **MET** — **+7.71 MHz above the STOP** |
| E-4 | worst setup > 0 | **MET** ×4 |
| E-5 | **TNS 0.000 setup AND hold, every domain** | **MET** ×4 — ⚠ **this is E-1's own live risk and it is clean on the bitstream that was flashed** |
| E-6 | the RETENTION receipt self-labels RETENTION | **MET** — **derived**, both draws |
| E-7 | the CONTROL receipt self-labels `CONTROL/DEFAULT` | **MET** — derived, both draws |
| E-8 | the RETENTION `.rbf` DIFFERS from CONTROL's | **MET** — `bcb48f01…` ≠ `5b869546…` |
| E-9 | the manifest reads `b2e50a482ca1123b…` on all four | **MET** ×4 |
| E-10 | `.qsf` regenerated and re-checked after each draw | **MET** |
| E-11 | both receipts retained | **MET** — 4 lines appended to `quartus_bitstream.jsonl` |
| **P-1** | CONTROL worst-of-2 **44.72 / +8.887 / 12,224** | **MET — ALL THREE EXACT, BOTH DRAWS** |
| **P-2** | RETENTION worst-of-2 **45.71 / +8.081 / 12,200** | **MET — ALL THREE EXACT, BOTH DRAWS** |
| **P-3** | CONTROL `.rbf` = `5b8695463675f732…` | **MET — byte-identical, both draws** |
| **P-4** | RETENTION `.rbf` = `bcb48f01adf3e94d…` | **MET — byte-identical, both draws** |

### 1.1 THE POINT PREDICTION HELD ACROSS TWO CHECKOUTS — AND THAT IS F-4 EVIDENCE, NOT A VICTORY LAP

The pre-registration registered **points, not bands**, on one ground: the main
checkout hashes identically on all 88 declared inputs of E-1's own CONTROL
receipt. **Eight draws of this tree now exist** — four in the census wave's
isolated worktree and four here — and **every one of them agrees to the digit
and to the `.rbf` byte.** That is four more data points for the census's **F-4**
(*"A&S is not reproducible run to run" is not supported by the receipt
history*).

⚠ **`standing_gates.md` §A still governs and is not weakened by this.** Eight
draws at one input hash is not a characterised distribution over inputs, and the
19.42 / 45.91 pair the ladder remembers predates the receipt layer and carries
no input hash. **What is established is narrower and sufficient: at a fixed
input manifest and a fixed configuration, this flow is reproducible, and it
reproduces across worktrees.**

### 1.2 `--retention`'s FIRST FLASH-BOUND EXERCISE PASSED BOTH OF ITS EFFECT-CHECKS

FLASH #18's hard stop fired because `X1_AD_RETENTION=1` was **accepted and
ignored** by an environment variable that never reached the compiler. The
`--retention` flag exists because of that. On its first bitstream-producing,
**flash-bound** run it printed
`quartus_map --verilog_macro=X1_AD_RETENTION=1` in its own log, produced a
receipt whose **derived** configuration self-labels RETENTION, and produced an
`.rbf` that **differs from CONTROL's**. Both clauses were registered as stops
and neither fired.

---

## 2. THE E-1 FABRIC BAR — THE SITTING'S ONE QUESTION

| # | bar | measured | verdict |
|---|---|---|---|
| **F-1** | flash via `safe_flash.sh`, VERIFY OK, log 21 → 22 | **VERIFY ok try 1** (`pwr_good True`, `cpu_running True`, `use_core False`), **22 entries**, tail `verify: "OK"` | **MET** |
| **B-1** | first light `check_ab_hw all 800`, MATCH ×3 | **chip-vs-golden · core-vs-chip · core-vs-golden ALL MATCH over 800 rows**, `rc 0` — and **re-run inside `fz2_w1 preflight` and MATCH ×3 again** | **MET** |
| **B-2a** | cell PASS/FAIL + coordinate agreement, fabric vs offline `ret` | **283 / 283, 0 disagreements** — reported, and **near-vacuous as declared** | **MET, not quoted as the result** |
| **B-2b** | **ROW-FOR-ROW: `diff_rows(offline, fabric)` EMPTY on all 283** | **283 / 283 identical, 0 differing rows** | **MET — THE BAR** |
| **B-3** | socket leg run and reported, not barred (§2.1) | **283 / 283 captured, 0 errors** — and it did far more than that, §2.3 | **as registered** |
| **B-4** | closing `use_core=0` chip proof after everything | **MATCH over 800 rows**, `rc 0` | **MET** |
| **B-5** | `board_idle()`, `use_core=0` left selected | **OK**, closing `div_guard` **PINNED** | **MET** |

**B-1 and B-2b are the two legs `timing_recovery_prereg` §6 named, before this
sitting existed, as the ones that *"would show it"* if E-1's constraint were
false.** Neither shows anything. The capture path reads 800 boot rows three
ways and 283 sweep cells row for row, and every row is what an untimed model
says it should be.

### 2.1 THE FINDING THAT CAME FIRST: `x1_retention` AND `x1_fabric` ARE GEN-DRIFTED HERE

Taking B-2's comparand **before the build** surfaced it, and it went into the
pre-registration (§3.1) **before the board was touched**:

    tests/v30/s10-hltsweep-w0/HLT.INT   golden case vs es.gen_evt_case(spec, rng)
        the ONLY differing field is  ip:  33153 (golden)  vs  42352 (regenerated)
    tests/v30/s10-hltsweep-w0/HLT.RES
        the ONLY differing field is  ip:  40473 (golden)  vs  38998 (regenerated)

Every other register, the instruction (`F4`), the event and the delay are
identical. **The fuzz-v2 image anchor moved**; the goldens are frozen at the v1
anchor and still carry its `0x90` fill where the composer now lays `0xCC`. Both
x1 legs regenerate from the same seed, so **both drift identically**:

    x1_retention capture --leg ret   283 cells, 0 errors, 67 s   ->  0 / 283 vs the goldens
    x1_fabric   baseline --leg fab_f19   283 cells, 0 errors      ->  0 / 283 vs the goldens

**`x1_retention` and `x1_fabric` therefore JOIN `timed_scenario`,
`timed_ins_replay`, `timed_wvec_gate` and `timed_enter_replay` as ratchets that
CANNOT BE QUOTED ON `fuzz-v2-on-relanding`.** The last quotable golden-relative
leg is **`fab_f11` at 279/283**. Engine-independent; it predates E-1 by the
whole fuzz-v2 branch.

**The control that makes the diagnosis readable, run before the document was
written**: `check_core --suite-dir tests/v30/s10-hltsweep-w0 --waits 0` is
**97 / 97**, because it reads the case **out of the golden file** instead of
regenerating it. **The HLT population is healthy; the defect is in the two x1
drivers' stimulus regeneration.**

*Falsifier, registered here*: a checkout of a pre-fuzz-v2 generator reproduces
`fab_f11`'s 279/283 on these tools.

### 2.2 THE SCORER, AND ITS NULL

`sw/f19_b2.py` was committed with the pre-registration and **proved non-vacuous
before the board was touched**, on the identity pair:

    plain      B-2a 283/283 agree     B-2b 283/283 identical, 0 differing   MET
    --null 5   B-2a 283/283 agree     B-2b 278/283 identical, 5 differing   MISSED

The null does two jobs: it shows B-2b catches a one-bit, one-row perturbation
in five of five injected cells, and it shows **B-2a did not notice a single one
of them** — the declared near-vacuity **demonstrated**, not asserted.

### 2.3 THE REPAIR — SILICON IS THE REFERENCE, AND IT DOES NOT DRIFT

**The sweep goldens ARE socket captures.** So the socket, re-captured on the
drifted program, *is* the golden for the drifted program. The full 283-cell
socket column was taken (**8 s, 0 errors**) and used as the reference.

**A PREDICTION WAS STATED BEFORE THE MEASUREMENT AND IT MISSED, AND IT IS
REPORTED AS A MISS**: *"fabric-vs-socket = 279/283, failures exactly `w1.INT/8`,
`w1.INT/9`, `w2.INT/12`, `w3.INT/15`; `HLT.RES` perfect 49·49·25·25."*

| | measured |
|---|---|
| **core-in-fabric vs SILICON** | **275 / 283** |
| **offline `tb_sys ret` vs SILICON** | **275 / 283 — THE SAME 275, THE SAME 8, THE SAME COORDINATES** |
| per sweep, fabric vs silicon | w0 `INT` 48/48 · w0 `RES` 49/49 · w1 `INT` 44/46 · w1 `RES` 47/49 · w2 `INT` 20/21 · w2 `RES` 24/25 · w3 `INT` 19/20 · w3 `RES` 24/25 |

**Why the prediction missed**: the eight failures are the **same four delay
indices — 8, 9, 12, 15 — in BOTH forms**, and I predicted `HLT.RES` immunity.
That immunity is a property of the **undrifted** program, and I carried it over
without deriving it. **All eight are ONE signature**, `busstat` `CODE` (chip) vs
`PASV` (core), at rows 10 · 10 · 10 · 10 · 12 · 12 · 14 · 14 — **family D**,
the `nec_bus` two-sample-per-clock class `standing_gates.md` records as
unscoreable on this comparator by construction. **Not a new failure class, and
the miss is mine, not the instrument's.**

**And the A/B was proved live rather than assumed.** A socket capture of the
same cells differs from the fabric capture on **exactly those 4 delay indices
and nowhere else** across 87 `HLT.INT` cells at w1/w2/w3, and is identical on
all 48 at w0 and all 49 `HLT.RES` at w0. **The two legs are different
positions**; the 40 ms-per-cell capture rate is the persistent `serve` session,
not a phantom.

**What §2.3 adds to B-2b**: B-2b says fabric and Verilator agree with each
other. §2.3 says **both agree with silicon on 275 of 283 cells, and their eight
disagreements are the same eight, in a class that predates E-1 by months.**

---

## 3. THE ERA GUARD AND THE CLOSING CONTROL

| # | bar | measured | verdict |
|---|---|---|---|
| **Q-1** | `fz2_replay` passes the fabric era guard with **NO bypass** | **`its inputs 88/88 hash IDENTICAL in the tree at HEAD` — FABRIC ERA GUARD: PASS.** It **REFUSED at HEAD before the flash**, by name, on `hdl/nec_test.sdc` (86/88) | **MET — and stronger than FLASH #18's 87/88** |
| **Q-2** | closing control, era guard ON, ≥ 255 / 260 | **264 / 264 = 100.0 %** — fabric PASS 150 / replay PASS 150 · fabric FAIL 114 / replay FAIL 114 · **`first_bad` IDENTICAL on 114 / 114**, and **100 % agreement in every family, every wait mode and both stimulus classes** | **MET in the strongest available form** |

**Q-1 reads 88/88 where FLASH #18 read 87/88**: the `.qsf` regenerated after the
final draw to the state the flashed receipt records, so this era needs **no
exemption at all**. `--no-fabric-era-guard` was **not used anywhere in this
sitting.**

**E-12 — E-1's outstanding offline debt is DISCHARGED.** The three ladder rows
`timing_recovery_results` §4 booked as *owed, not passed* — because
`sw/testdata/campaigns/*/captures/` is untracked and an isolated worktree never
had it — were all run **here, in the main checkout**: `fz2_replay` (Q-2),
`fz2_immaterial falsify` (§4.5) and the capture-reading fuzz-v2 rows (§5).

---

## 4. THE CORPUS

`fz2_w1 control` → `preflight --board` → `capture` → `fz2_ledger`, all on FLASH
#19, scored against the FLASH #18 ledger.

| # | bar | registered | measured | verdict |
|---|---|---|---|---|
| **C-1** | corpus identity | `45d25f31a325c496…`, 3,840, 48 strata, lint PASS | **as registered** — `fz2_w1 lint` **PASS / 0 hits / 48 stratum rows** | **MET** |
| **C-2** | completeness | 48/48 strata, every `rc 0` | **48 / 48, every `rc 0`, 960 + 2,880, 11.0 min** | **MET** |
| **C-3** | the flash pin | `distinct_eras` 1 | **`distinct_eras` 1 · `absent` 0 · `incomplete` 0 · `build_stale` 0** over 3,840, era `03365b1115e1…` | **MET** |
| **C-4** | **the headline** | **110 / 3,839**, band [100, 120] | **114 / 3,837** | **POINT MISSED (+4), BAND MET** |
| **C-5** | membership flips | **0**, budget 10 | **ENTERED 4 · LEFT 0**, plus **2 discard flips** = **6 of 10** | **MISSED, inside the budget** |
| **C-6** | first-divergence moves | **0** | **0 over all 110 shared failures, in either direction** | **MET** |
| **C-7** | row metric, both units | reported | Σ`bad_rows` **109,678 → 118,221**; Σ`diverging_rows` **109,739 → 118,282**. Among the 110 shared, **exactly one seed moved its row count** | **as registered** |
| **C-8** | discards | 1, `fz2e/509069` | **3** — `fz2e/509069` **stayed**, `fz2e/524027` and `fz2e/535070` **entered**; denominator 3,839 → **3,837** | **MISSED — §4.6** |
| **C-9** | the 14 named non-movers | 14 / 14 | **14 / 14, both columns, seed for seed** | **MET** |
| **C-10** | the six FLASH #18 seats | KM 3 absent; phantom-T1 3 at `bad` 1 / `first` 243·234·583 | **KM 3 / 3 ABSENT**; **phantom-T1 `(1, 243)` · `(1, 234)` · `(1, 583)`, exact** | **MET** |
| **C-11** | `fz2c/404040` ABSENT | ABSENT | **ABSENT** | **MET** |
| **C-12** | `fz2_immaterial falsify` PASS, class stable 24 **set-for-set** | PASS G1–G8 | **G1–G5, G8 PASS; G6/G7 FAIL on doc staleness only.** Class **24, SET-FOR-SET IDENTICAL, 0 leavers, 0 entrants**, every member's `bad`/`done`/`cyc`/`columns` byte-identical to F18 | **membership MET; falsifier MISSED on the two doc clauses** |

**C-10 is worth its own line.** KM's three seats stay closed and phantom-T1's
three stay at exactly one row with the first divergence exactly one row earlier
— **FLASH #18's confirmation survives a second bitstream unchanged**, on a build
whose timing constraints are different.

### 4.1 THE `fz2c` HALF DID NOT MOVE AT ALL

All six movers are `fz2e`. **The 960-seed census population produced zero
membership changes, zero first-divergence changes and zero row-count changes.**

### 4.2 C-6 IS THE SHARPEST NUMBER IN THIS SECTION

**Zero of 110 shared failures moved their first divergence, in either
direction.** FLASH #17 needed nineteen named exemptions for this bar; FLASH #18
named three; **this sitting named none and needed none.** If E-1 had changed
what the observation registers sample, the first divergence is the quantity that
would move, and it is the quantity that moved least.

### 4.3 C-7 — ONE ROW-COUNT MOVER, AND IT IS A REGISTERED FALSIFIER FIRING

Among the 110 shared failures exactly one row count moved: **`fz2e/530020`,
326 → 671.** That is the seed FLASH #18's housekeeping admitted to
`TIMING_RECONVERGED` (7 → 8) **with a falsifier written beside it**: *"a double
capture in which its two `done` clocks are stable — if they flicker, the
membership is capture noise and 8 is not a ratchet."*

**The falsifier FIRED.** `TIMING_RECONVERGED` reads **7** on this era.
**8 was not a ratchet, and the entry was capture noise, exactly as its own
falsifier said it would be if this happened.**

### 4.4 THE SIX MOVERS, ITEMISED AS REGISTERED

| seed | tier | F18 | F19 (run A) | note |
|---|---|---|---|---|
| `fz2e/508068` | soup | `bad` 0, SUCCESS/clean, win 1533 | `bad` **359**, `first` **681**, FUNCTIONAL/done_mismatch, `done_sim` False | entered the ledger |
| `fz2e/509050` | soup | `bad` 0, SUCCESS/clean, win 3583 | `bad` **2863**, `first` **688**, FUNCTIONAL/`func:R@9` | entered; **also C-6's only failing directive** |
| `fz2e/514001` | soup | `bad` 0, SUCCESS/clean | `bad` **1681**, `first` **696**, FUNCTIONAL/`func:R@23` | entered the ledger |
| `fz2e/526075` | raw | `bad` 0, SUCCESS/window_truncated, `mech` STALLED | `bad` **3295**, `first` **697**, KNOWN_ACCEPTED/cadence, `mech` **REACHED** | entered; **the CHIP leg's `done_real` moved** |
| `fz2e/524027` | raw | `bad` 0, `ps3_8080` **False** | `bad` **2453**, `first` **688**, `ps3_8080` **True** | **DISCARDED — a SOCKET-leg predicate** |
| `fz2e/535070` | raw | `bad` 0, `ps3_8080` **False**, escaped `[788, 51779]` | `bad` **2827**, `first` **690**, `ps3_8080` **True**, escaped **`[2157, 16496]`** | **DISCARDED — socket-leg; escape target moved** |

**Every first divergence lies in 681 … 697 — a 17-row band.** FLASH #18's own
results flagged the same neighbourhood: its two discard movers both had
`first_bad` **678**, recorded there as *"a hint that they share a stimulus, not
a claim."* **This is the third consecutive era in which this band produces the
discard re-roll** (2 → 2 → 3 → 1 → **3**).

### 4.5 C-12 — THE CLASS DID NOT MOVE; THE DOCUMENT DID

`fz2_immaterial falsify` on the F19 ledger: **G1 DUMP PROOF · G2 DUMP IDENTITY ·
G3 SCHEDULE · G4 NOT UNIVERSAL · G5 CONTROLS · G8 NO FORK all PASS**, C-ROW
114/114 and C-ARCH 114/114. **G6 (3/8 cells) and G7 (1/25) FAIL, and both are
doc-vs-derivation cross-checks** against a census document that records the F18
numbers (110 / 24 / 86) where the derivation now gives (114 / 24 / 90).

**This is the exact case the pre-registration pre-declared** (*"a G7
disagreement means the document is stale, not that the corpus moved… the fix is
booked, not applied in this sitting"*), and **the fix is not applied**. What the
gate is actually reporting is the C-4/C-5 miss propagating into a document, plus
§4.3's `TIMING_RECONVERGED` 8 → 7.

**The membership clause — the one that says something about the corpus — is
MET in its strongest form: the 24 members are set-for-set identical, and every
member's row count, done clock, cycle count and differing-column list are
byte-identical to FLASH #18's census.**

### 4.6 **THE ATTRIBUTION — MEASURED, NOT ARGUED, AND WITH ITS LIMIT STATED**

The pre-registration (§0.3) required that a seed-level change be treated as **a
FINDING against E-1 first**, because nothing else in this tree can produce one.
That is what was done, and then it was tested.

**THE TEST.** The six affected strata (480 seeds) were re-captured **on the same
bitstream, minutes later**, into a retained second run
(`sw/testdata/campaigns/fz2e-F19runB-repeat/`). Result:

    seeds re-captured                                    480
    seeds whose scored fields moved between the two runs    6   <- exactly the six
    all other seeds                                      474   unmoved, field for field

    and all six revert to bad_rows 0 / SUCCESS -- to their FLASH #18 values:
      508068  win 1053 -> 1533 (= F18's 1533)      509050  win 3613 -> 3583 (= F18's 3583)
      526075  mech REACHED -> STALLED (= F18's)    535070  escaped -> [788, 51779] (= F18's)
      524027  ps3_8080 True -> False               514001  bad 1681 -> 0

**The six are NOT REPRODUCIBLE ON ONE BITSTREAM.** Five independent facts point
the same way:

1. **They revert on a repeat of the same bitstream** — a constraint cannot be
   intermittent, and a build cannot change between two captures of itself.
2. **Two of the six moved `ps3_8080`, a SOCKET-leg predicate (amendment A-2).**
   E-1 constrains the FPGA build; it **cannot reach the socket position** by
   construction. `fz2e/526075` additionally moved the chip leg's own
   `done_real`/`mech`.
3. **`fz2_replay` reproduces all four ledger entrants offline** with `first_bad`
   identical (Q-2, 264/264). The offline core has **no timing constraints at
   all** — E-1 does not exist for it. Fed the same chip rows it finds the same
   divergence, so the fabric core's sampling is not what changed.
4. **The noise floor was characterised on pre-E-1 bitstreams** at
   **10 / 3,840 = 0.2604 %** and `fz2_capture_noise_2026-08-10.md` measured it
   as **BIMODAL, not a jitter band**. *Six seeds flip wholesale and 474 do not
   move at all* is precisely that shape. FLASH #17 spent **7** of the same
   budget with no E-1 anywhere.
5. **Every deterministic leg is clean**: B-1 (800 rows ×3, twice), B-2b (283
   cells row for row), the closing chip proof, C-6 (0 of 110 first divergences),
   C-9 (14/14), C-10 (6 seats exact), C-12's membership (24 set-for-set),
   `check_fuzz_bank` (621 stable), and the C-6 **board control leg**, which
   proved the pin holds `[2, 20, 300]` on both pins **to the clock**, 9 legs,
   51 checks, 51 PASS.

**THE LIMIT, AND IT IS NOT SOFTENED.** This does **not** prove E-1 contributes
nothing to the noise floor. It shows that the floor's **magnitude** (6 of a
10-seed budget) and its **character** (bimodal, non-reproducible, concentrated
in one 17-row band) are what they were before E-1 existed, and that its
socket-leg component is **E-1-unreachable**. **A marginal timing exception that
occasionally corrupts a sample would look like noise** — that is exactly why
§8 of the pre-registration said this sitting can produce a strong negative
result and not a proof. It stands.

**AND THE HEADLINE IS QUOTED FROM RUN A, NOT RUN B.** With the six reverted the
ledger would read 110 of 3,839 — the registered point exactly. **That number is
not quoted and the ledger is not re-derived from run B**: choosing the run after
seeing it is the move this campaign's rules exist to prevent. Run A is the
sitting's corpus, run B is retained beside it as the falsifier's evidence, and
**C-4, C-5, C-8 and C-13 are reported as MISSES.**

*Registered falsifier for §4.6's own reading*: a third capture on this bitstream
in which the same six seeds fail **again**, reproducibly. That would make the
event deterministic and put E-1 back in the frame.

---

## 5. THE STANDING GATES ON THIS ERA

| gate | result |
|---|---|
| `fz2_w1 bars` | **10 / 11 — C-6 MISSED**, `hold_rows_exact` **4,637** / `hold_rows_off` **1**. The single failing directive is **`fz2e/509050` stim/`pin_int`/hold 300, `runs []`, `term_fired 0`** — one of §4.4's six, and it reverts in run B. C-1 MET (rate clauses validated on `fz2v`/960), C-4 `distinct_eras` 1, C-5 `gen_drift` 0, C-7 MET, **C-8 `div_guards` 63 / unpinned 0**, C-9 192 stable / 0 unstable, C-10 0 quarantines / 0 run-error lines, C-11 MET |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 control` (C-6 board legs) | **MET — 9 legs**, holds **[2, 20, 300]** proved on `pin_int` and `pin_nmi`, TVECs `(0, 48896)` and `(3056, 8)`, INTA vector **255**, N1 negative control PASS, `div_guards` 10 / unpinned 0 |
| `fz2_w1 preflight --board` | **OK** — single writer, era pinned to receipt `dba7c75533bc…` self-labelling RETENTION, **192-seed regeneration sample hits 0**, RBCHECK **8 registers**, MATCH 800 ×3 |
| `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| `r7_lint` | **PASS** — 0 undeclared carriers, 0 undeclared unresolved, **51 `stop` sites, 0 violations** |
| `ss_lint --core ucore` | **PASS** — BIU 85 → 85 mapped, EU 129 → 127 mapped + 2 whitelisted, **214 architectural flops, 0 UNMAPPED** |
| `gen_ucore_qsf --check` | **PASS** |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `check_core --suite-dir s10-hltsweep-w0 --waits 0` | **97 / 97** (§2.1's control) |
| §38.9 missed-trap overlay | **4** — the same four seeds as FLASH #18 |

⚠ **`ss_lint` reports 214 flops and 0 UNMAPPED, which is the current tree's
figure and matches E-1's own ladder.** The `SS_VERSION`/`SS_COUNT` line in
CLAUDE.md's quick reference is one era behind this branch; nothing in this
sitting moved it.

---

## 6. THE DIRECTED-CELL SPOT-CHECKS

All three cells' board legs are **socket-only (`use_core=False`)**: they measure
**SILICON**, which no bitstream can move. **Registered: 0 chip-column movers on
all three.**

| # | leg | measured | verdict |
|---|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` (48 cells, 2 s) + `score` | **chip == core, 0 / 512 differing on ALL SIX columns** (`n_entries`, `pushed_off`, `pushed_off_set`, `lastcode_off_set`, `uniform`, `term_done`). **`KM` 14 / 14 legs, the only key surviving on every one** — and 14/14 against the core too. NULL `notf` / `v_notf` **[0]** both. **0 transport errors, 0 TAKE-unstable**; stability 64/512 ×3, **0 unstable, 0 stream-distinct** | **MET** |
| **S-2** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells, 1 s) + `score` | **0 chip-column movers**: board-vs-core reads `n_inta` **36**, `ack_off` **46**, `ack_off_hlt` **46** — **exactly the pre-ack-wake baseline the banked `core` column holds**, reproduced on fresh FLASH #19 silicon. The six invariant columns `wake_prefetch · rise · fall · t_ei · anchor_t1 · n_rows` all **0 / 1,920**; wake-prefetch `rise_off` ranges identical at every wait, **0 core disagreements**; 330 boundary cells ×11 reps, **TAKE-unstable 0** | **MET** |
| **S-3** | `ghost_pred_cell run --legs alu88,mul,pop0,mem1,mov8e,sl4,v_lea` (112 cells, 5 s) | **112 / 112 chip cells BYTE-IDENTICAL to the FLASH #18 column**, 0 differing. **0 transport errors, 0 GHOST-unstable** | **MET** |
| **S-4** | `div_guard` + single-writer on every leg | **0 UNPINNED across every probe this sitting** (10 control + 2 preflight + 48 capture + tf0f + ie-pinfall + ghost-pred + idle; `bars` counts **63 / 0 unpinned** on the capture path). Single writer asked of the board before first contact and again before each leg | **MET** |
| **S-5** | restoration | **884 banked files restored BYTE-IDENTICAL** (tf0f 532 · ie-pinfall 76 · ghost-pred 276), verified by sha256 manifest before and after; the F19 rows retained **beside** them at `sw/testdata/{tf0f,ie-pinfall,ghost-pred}-f19-spotcheck/` | **MET** |

**The registered expectation held exactly: silicon did not change, and E-1
cannot reach the socket position.** ⚠ And that is the control that makes §4.6
readable: **the same board, the same session, the same socket — 0 movers on
three directed cells and 6 movers on the corpus.**

---

## 7. HARD STOPS

**NONE FIRED.**

`git diff 770c0d1b85 HEAD -- hdl/rtl/ sim/` EMPTY at both checks · RETENTION
worst-of-2 **45.71 ≥ 38.0** · the RETENTION receipt self-labelled RETENTION and
its `.rbf` differed from CONTROL's · `safe_flash` VERIFY **ok try 1** · **0
`div_guard` UNPINNED** · **0 `RigMismatch`, 0 quarantines, 0 run-error lines** ·
single writer clean before every leg, `--force` never used · first light MATCH
800 ×3 · closing chip proof MATCH 800 · `board_idle()` clean.

**The registered non-stops, reported with their denominators**: C-4's point
(+4 of a ±10 floor), C-5's six flips (of a 10-seed budget), C-8's discard
re-roll (3, registered 1), C-12's G6/G7 doc staleness, C-13's `bars` 10/11, and
§2.3's own stated prediction (275/283 against a stated 279/283).

### 7.1 TWO PROCESS LAPSES, REPORTED

1. **A banked artifact was overwritten by an exploratory `score` run.**
   `sw/testdata/ghost-pred/score.json` was rewritten while reading the cell's
   interface, before the pre-registration was committed. It was **restored from
   git immediately** and the restoration is verified — the file is unmodified in
   the final tree. It should not have been run against the banked directory at
   all, and the copy-aside discipline §6 applies to the spot-checks was adopted
   only afterwards.
2. **A wait-loop matched its own command line.** Several `until pgrep …` waits
   never terminated because `pgrep -f` matched the waiting shell itself. No
   measurement was affected; it cost wall-clock time and is recorded so the next
   sitting does not repeat it.
3. **`board_idle()` was called, then the board was used again** (§4.6's repeat
   capture came after the first idle). It was re-run at the close, so the
   sitting's *last* board action is an idle — but the ordering was not planned
   and is recorded.

### 7.2 THE CLOSING BOARD STATE, READ AND EXPLAINED RATHER THAN QUOTED AS "CLEAN"

    pwr_good False   cpu_running False   ctrl 0x5   cfg 0xff0008   use_core False

⚠ **`pwr_good False` is the RESTING state, not a fault**, and the claim is not
taken on trust. `STATUS[0]`/`[1]` are live bits: after a run completes the
socketed chip is left held, so they read low. **The proof that the board is
healthy in exactly this state is that `check_ab_hw chip 800` was run FROM it and
returned MATCH over 800 rows** — twice, once before and once after an
intervening `board_idle()`. `use_core` is **False** and the divider readback was
**PINNED** on the final probe.

**This is recorded because "board_idle: OK" alone would have been a weaker
statement than the evidence supports, and because a future sitting that reads
`pwr_good False` at connect should know it is normal at rest.**

---

## 8. WHAT THIS SITTING ESTABLISHED, AND WHAT IT LEAVES OPEN

**ESTABLISHED**

1. **E-1's fabric bar is MET on every leg that can see it**, in the form
   `timing_recovery_results` §5 registered before this sitting was contemplated:
   first light **MATCH 800 ×3**, the 283-cell column **row-for-row identical**
   to the offline one, the closing chip proof **MATCH 800**, and the era guard
   passing at **88/88 with no bypass**.
2. **Both engines agree with SILICON on 275 of 283 sweep cells, and their eight
   disagreements are the same eight** — family D, a class that predates E-1 by
   months.
3. **G6 reproduces to the digit and to the `.rbf` byte across two checkouts**,
   eight draws at one input hash.
4. **`--retention` is exercised flash-bound** and both of its effect-checks hold.
5. **The corpus's deterministic content did not move**: 0 of 110 first
   divergences, 14/14 named non-movers, all six FLASH #18 seats exact, the
   24-member IMMATERIAL class set-for-set with byte-identical evidence, 621
   banked seeds stable.
6. **FLASH #18's housekeeping falsifier fired as written**: `TIMING_RECONVERGED`
   8 → 7, so 8 was never a ratchet.
7. **`x1_retention` / `x1_fabric` are GEN-DRIFTED on this branch** — found while
   taking a comparand, written into the pre-registration before the board was
   touched, with the `check_core` 97/97 control that localises it to stimulus
   regeneration.

**OPEN, WITH THEIR FALSIFIERS**

1. **The 681–697 band.** Three consecutive eras have produced their discard
   re-roll and now their whole membership movement inside it. It is
   non-reproducible per §4.6, and **nothing in this tree explains why that band**.
   *Falsifier*: a directed repeat of those six seeds at high repetition on one
   bitstream, counting the flip rate per seed rather than per corpus.
2. **E-1 cannot be excluded as a contributor to the noise floor** (§4.6's
   limit). *Falsifier*: the same corpus repeat protocol on a CONTROL bitstream —
   E-1 is in the SDC, so a build without the exception is the only true control,
   and it costs one Quartus draw plus one flash.
3. **The x1 GEN-DRIFT is booked, not repaired.** *Falsifier*: a pre-fuzz-v2
   generator checkout reproducing `fab_f11`'s 279/283. The cheap repair — read
   the case out of the golden file, as `check_core` does — is a tool change and
   needs its own pre-registration.
4. **The IMMATERIAL census document is one era stale again** (G6/G7). Booked,
   deliberately not fixed in the sitting that measured the failure.
5. **The four family-D cells remain**, in both engines, at one signature.
   Unchanged and unexplained by this sitting, which did not try.
