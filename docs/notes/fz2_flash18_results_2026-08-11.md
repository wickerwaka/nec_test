# FLASH #18 — RESULTS, AS REGISTERED

Pre-registration `docs/notes/fz2_flash18_prereg_2026-08-11.md`, committed
**`7c4a639ca4`** — before any Quartus build and before any board contact.
Scorer `sw/fz2_f18_score.py` + amendment **A-1**, committed **`30b46f07d3`** —
written while the CONTROL build was still running, before the flash and before
the F18 ledger existed, and **non-vacuous against the F17 null (P-1 0/3, P-2
0/3, eleven clauses MISSED)**.

Every bar is reported in the form it was registered in.  **Nothing is
re-registered after the fact.**

---

## 0. THE HEADLINE, IN ONE PARAGRAPH

**BOTH LANDINGS ARE CONFIRMED IN SILICON, SEAT FOR SEAT, AND THE SITTING IS
CLEAN: KM's three seats CLOSED 3/3, phantom-T1's three seats COLLAPSED 3/3 to
`bad_rows == 1` with `flick == 0` and `first_bad_row` EXACTLY 243 / 234 / 583 —
the POINT prediction, not merely the band — and there were ZERO unregistered
ledger membership flips against a budget of ten.**  The headline reads **110
failures**, which is the registered PRIMARY POINT **to the seed** (+0), and —
exactly as the pre-registration required — *that is not quoted as evidence*:
**the evidence is the six seats.**  `fz2c/404040` stayed absent, all fourteen
named non-movers were unmoved in both columns, the family table landed on C2 9
and D2 8 as predicted, and **not one seed outside phantom-T1's three moved its
first divergence in either direction.**  **The fabric era guard PASSES without
the bypass** (87/88, `nec_test_ucore.qsf` the one declared exemption) and the
closing control is **260/260 = 100.0 %** with `first_bad` identical on 110/110.
**Three clauses MISSED and are reported as registered**: G-6's discard count
(1, registered 3 — the fourth consecutive socket-leg re-roll), and P-7a's two
clauses (the IMMATERIAL census's *document* cross-checks G6/G7 now disagree with
the derivation, and three of the six seats have entered the IMMATERIAL class —
a miss in the favourable direction).  ⚠ **And a HARD STOP fired mid-sitting and
was obeyed**: the first RETENTION draw self-labelled `CONTROL/DEFAULT` because
`X1_AD_RETENTION=1` never reached the compiler, and **nothing was flashed on
it** (§1.2).  This sitting also **closes FLASH #17 §5.3's open instrument
question** — it was `flick` (§1.1).

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS (`E-1` … `E-13`)

Quartus 17.1.0 Build 590, each from a deleted `db` / `incremental_db` /
`output_files_ucore`.  **ONE clean draw per configuration, as registered.**

| | **CONTROL** | **RETENTION (flashed)** |
|---|---|---|
| verdict | **PASS** | **PASS** |
| receipt | **`6d07f59376f86196…`** | **`277d5ccf0f8b9398…`** |
| label | `fz2 FLASH#18 CONTROL draw1` | `fz2 FLASH#18 RETENTION ret1` |
| configuration (**derived**) | `CONTROL/DEFAULT (no X1_AD_RETENTION)` | **`RETENTION (X1_AD_RETENTION=1)`** |
| **Fmax (`divclk`)** | **40.13 MHz** | **38.82 MHz** |
| **worst setup** | **+6.333 ns** | **+5.492 ns** |
| **TNS setup / hold** | **0.000, every domain** | **0.000, every domain** |
| ALMs | 12,246 / 41,910 (**29 %**) | 12,276 / 41,910 (**29 %**) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `98bef5844cede505…` | `8a3ee8f734e911bb…` |
| `.sof` sha256 | `82656c80acf4c065…` | **`b2a1fe5f83167fbf…`** |
| `.rbf` sha256 | `b1fcbb0eac30…` | **`ecda4b90c646ba49…`** |
| compile | 582 s | 533 s (map 180 s + fit 353 s) |
| git | `7c4a639ca4`, **CLEAN** | `30b46f07d3-dirty` — see §1.3 |

| # | bar | verdict |
|---|---|---|
| E-1 | `gen_ucore_qsf --check` BEFORE each draw | **MET** — *"up to date"* both |
| E-2 | 0 errors, every stage Successful, 0 latches, 0 `lpm_divide` | **MET** both |
| E-3 | Fmax ≥ 32 (G6) and ≥ 38.0 (this sitting's STOP) | **MET** — 40.13 / 38.82 |
| E-4 | worst setup > 0 | **MET** — +6.333 / +5.492 |
| E-5 | TNS 0.000 setup **and** hold, every domain | **MET** both |
| E-6 | the retention receipt self-labels RETENTION | **MET on the second attempt — §1.2** |
| E-7 | the control receipt self-labels `CONTROL/DEFAULT` | **MET** — derived, not asserted |
| E-8 | `.qsf` regenerated and re-checked AFTER each draw | **MET** — regenerated to `95770c099a9505d6…`, `--check` rc 0 |
| E-9 | the macro's effect is CHECKED, not asserted | **MET on the second attempt** — retention `.rbf ecda4b90…` **differs** from control `.rbf b1fcbb0e…` |
| E-10 | both receipts retained | **MET** — in `sw/testdata/receipts/quartus_bitstream.jsonl` |
| **E-11** | the 88-file manifest **WILL DIFFER** from the ack-wake tree's `7db533790f51ff18…` | **MET** — `98bef5844cede505…` |
| **E-12** | the CONTROL draw reproduces **40.13 / +6.333 / 12,246 EXACTLY** | **MET — ALL THREE EXACT** |
| E-13 | soft band 38.4–42 if E-12 misses | not reached (E-12 MET) |

### 1.1 **FLASH #17 §5.3 IS CLOSED — IT WAS `flick`, AND IT WAS FOUND BEFORE THIS CAPTURE**

F17 §5.3 booked *"a one-sided residue with a shape … reported and NOT
explained"*: 24 of 43 predicted seeds under-counted `diverging_rows` by 1–5 and
one by 21, never the other way.

**It is two different quantities.**  `sw/fz2_ledger.py:219` writes each entry's
`diverging_rows = bad_rows + flick`; `:209` accumulates the corpus total as
`bad_rows` alone; and `fz2_replay`'s `fabric_bad` is `bad_rows`.  The F17
pre-registration predicted from the replay and the F17 results scored against
the ledger entry.  Over the F17 ledger **Σ`diverging_rows` 119,258 −
Σ`bad_rows` 119,192 = 66 = Σ`flick`**, on exactly the 25 seeds whose two figures
differ — and `fz2e/510043`, F17's single *"off by more"* at **+21**, has
`flick` **21**.

**This is an ERRATUM against FLASH #17 §5.3.**  That section's *"18/43 EXACT"*
would read **43/43 exact on `bad_rows`**, and the residue is not physical.  It
was found offline, **before this sitting's capture**, and every row prediction
in the F18 pre-registration is stated in both units by name.  ⚠ The same units
trap was then caught a **second** time, in a second place, by running the scorer
against the F17 null before the board was touched — prereg **AMENDMENT A-1**.

### 1.2 ⚠ **A HARD STOP FIRED — E-6 AND E-9 CAUGHT A MIS-INVOCATION, AND NOTHING WAS FLASHED ON IT**

The first RETENTION attempt was `X1_AD_RETENTION=1 python3 sw/quartus_gate.py`.
It produced a receipt — **`aa3ca3e028dff7d2…`**, label `fz2 FLASH#18 RETENTION
ret1` — whose **derived** `configuration` reads `CONTROL/DEFAULT (no
X1_AD_RETENTION)`, whose gated figures are the CONTROL draw's to the decimal
(40.13 / +6.333 / 12,246, manifest `98bef5844cede505…`), and whose `.rbf` is
**byte-identical to the CONTROL `.rbf`**.

**Cause**: `sw/quartus_gate.py`'s `build()` runs `quartus_sh --flow compile`
with **no `--verilog_macro`** and never reads `X1_AD_RETENTION` from the
environment.  The variable was **accepted and ignored** — the exact trap
CLAUDE.md names.  The recorded recipe
(`fuzzv2_retention_prereg_2026-08-08.md` §6.1, and four earlier pre-registrations
in identical words) is the four-step manual compile:

    quartus_map --verilog_macro="X1_AD_RETENTION=1" nec_test -c nec_test_ucore
    quartus_fit / quartus_asm / quartus_sta   nec_test -c nec_test_ucore
    python3 sw/quartus_gate.py --parse-only --no-qsf-check

Re-run that way, the receipt self-labels **`RETENTION (X1_AD_RETENTION=1)`** and
the `.rbf` differs.  **Two things are owed to the record and neither is
softened:**

1. **AN ERRATUM AGAINST THIS SITTING'S OWN PRE-REGISTRATION.**  Appendix A of
   `fz2_flash18_prereg_2026-08-11.md` writes the retention step as
   `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` — concretely, and **wrong**.
   FLASH #17's Appendix B wrote `X1_AD_RETENTION=1 ...` with an ellipsis, so it
   was under-specified rather than incorrect; this document made it worse by
   spelling it out from a guess instead of from `fuzzv2_retention_prereg` §6.1.
   **That is a pre-registration defect and it is reported as one.**
2. **RECEIPT `aa3ca3e028dff7d2…` STAYS IN THE APPEND-ONLY HISTORY AND IS NAMED
   HERE.**  Its *label* says RETENTION and its *derived* configuration says
   CONTROL.  That disagreement is precisely the `4bb65d2ab6` defect class the
   derived label was built to catch, and it is now a worked example of the
   label catching a **live** mis-invocation rather than a historical one.
   **It is not deleted.**

**A standing recommendation, booked not taken**: `quartus_gate.py` could grow a
`--retention` flag that passes the macro, so the recipe stops living only in
prose.  That is a tool change and it needs its own pre-registration.

### 1.3 **THE RETENTION DRAW WAS TAKEN ON A DIRTY TREE, AND THE RECEIPT SAYS SO**

`git 30b46f07d3-dirty`.  The dirt is enumerated rather than waved at:
`hdl/nec_test_ucore.qsf` (Quartus rewrites it in place — the declared §70.7
exemption) and `sw/testdata/receipts/quartus_bitstream.jsonl` (the gate's own
append-only output).  **No RTL file was modified**, and the check on that claim
is the manifest: the CONTROL and RETENTION 88-file manifests differ in
**exactly one file, `hdl/nec_test_ucore.qsf`**; all 87 others — including
`hdl/rtl/system_large.sv` at `8d3fc7e669b3…` — are byte-identical.

### 1.4 **M10-SYS's INERTNESS: PROVED BY READING, THEN CONFIRMED BY THE COMPILER**

§0.1 of the pre-registration proved by preprocessing that
`hdl/rtl/system_large.sv` at HEAD, with `SYNTHESIS` defined, is **byte-identical**
to `6cbb01a642`'s.  **E-11 and E-12 then tested it as a pair and both MET**: the
manifest moved (the bytes are different) while Fmax, worst setup and ALM count
reproduced the ack-wake tree's **40.13 MHz / +6.333 ns / 12,246 ALMs** — all
three exact, across two different worktrees and three total draws.
**`standing_gates.md` §A still governs**: three draws of one number is three
draws, not a characterised distribution.  What is established is narrower and
sufficient: **the instrument did not reach the compiler.**

### 1.5 **§2.2 — THE SIXTH OBSERVATION: THE RUN OF FIVE INVERSIONS IS BROKEN**

    CONTROL     40.13 MHz   +6.333 ns
    RETENTION   38.82 MHz   +5.492 ns
    difference  -1.31 MHz   -0.841 ns   -- RETENTION BELOW CONTROL

Retention had drawn **above** control five consecutive times (#13 +0.46, #14
+1.50, #15 +2.24, #16 +0.12, #17 +0.71).  **#18 is −1.31**, the first negative
since FLASH #12.  A-1.1a's registered falsifier is now **five of six**.
Secondly, **Fmax and worst setup agree in sign with each other** this time —
F17's first-ever disagreement did not recur.  Both are **reported, not
explained**; `standing_gates.md` §A governs.
⚠ **E-3's margin is thin and is stated as such: 38.82 against this sitting's own
38.0 hard STOP is +0.82 MHz**, the closest any flashed build on this branch has
come to the stop.

---

## 2. THE FLASH AND FIRST LIGHT (`F-1` … `F-9`)

**FLASH #18 IS ON THE BOARD.**  `nec_test_ucore.sof`
**`b2a1fe5f83167fbfd2b7d9f3b67d1ad10a2200448d019ce7b5bc8eed8a88dd58`**, `.rbf`
**`ecda4b90c646ba49…`**, built from `30b46f07d3` **WITH `X1_AD_RETENTION=1`**,
through `sw/safe_flash.sh` with its VERIFY leg.  **IT IS THE FIRST BITSTREAM TO
CARRY KM AND phantom-T1.**

| # | bar | measured | verdict |
|---|---|---|---|
| F-1 | flash + ledger, VERIFY OK, log 20 → 21 | **VERIFY ok try 1** (`pwr_good True`, `cpu_running True`, `use_core False`), **21 entries**, tail `verify: "OK"` | **MET** |
| F-2 | first light MATCH 800 on all three legs | **chip-vs-golden · core-vs-chip · core-vs-golden all MATCH 800**, `rc 0` | **MET** |
| F-3 | RBCHECK exactly 8 registers | **8** — `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, `TVEC`, `VECCTL` | **MET** |
| F-4 | C-6 control, 9 legs / 51 checks | **9 legs, 51 checks, 51 PASS, `failing_legs []`**, INTA vector **255 (0xFF)**, holds `[2,20,300]` on `[pin_int, pin_nmi]`, TVECs `(0,48896)` / `(3056,8)`, **P1–P5 run lengths 2 · 300 · 2 · 300 · 20 to the clock**, N1 negative control PASS | **MET** |
| F-5 | `use_core=0` chip proof **after everything** | **MATCH over 800 rows**, `rc 0` | **MET** |
| F-6 | `div_guard` tally, 0 UNPINNED | **0 UNPINNED** — 10 (control) + 2 (preflight) + 48 (capture) + 5 (tf0f) + 4 (ie-pinfall) + 1 (idle) | **MET** |
| F-7 | transport, 0 `RigMismatch` | **0** — 0 quarantines, 0 run-error lines (C-10) | **MET** |
| F-8 | `board_idle()` | **OK, `use_core = 0` left selected** | **MET** |
| F-9 | single-writer / socket-only | **OK** — asked of the board before first contact and again at preflight, tf0f and ie-pinfall: no `v30ctl`/`serve` process on the board, none locally | **MET** |

**F-2's registered justification held.**  KM needs `PSW.TF` set at a
`0F`-escaped instruction; phantom-T1 needs a HALT wake whose withdrawn
announcement is followed by an acknowledge.  The boot program has neither, so
MATCH 800 was the correct prediction and it is a **control on the flash, not a
test of either landing.**

---

## 3. THE RE-CAPTURE AND THE INTEGRITY BARS (`G-1` … `G-6`)

The FLASH #17 corpus was archived **by rename** first — nothing deleted:
`fz2c`/`fz2e` → `*-F17-archive`, and `fz2_capture` / `fz2_bars` /
`fz2_preflight` / `fz2_control` `.json` → `*_F17-archive.json`.  Then
`fuzz_campaign.py new fz2c` / `new fz2e` re-pinned both manifests to the
resident flash (`pin sha256 b2a1fe5f8316…`).

| # | bar | measured | verdict |
|---|---|---|---|
| G-1 | corpus identity | `SEED_LIST_SHA256 45d25f31a325c496…`, 960 + 2,880 = **3,840**, 48 strata, `fz2_w1 lint` PASS / 0 hits | **MET** |
| G-2 | preflight | `verdict OK`, board leg run, era pinned to receipt `277d5ccf0f8b…` (self-labelling RETENTION), **192-seed regeneration sample hits = 0** | **MET** |
| G-3 | completeness | **48 / 48 strata, every `rc 0`**, `halted null`, **960 / 2,880 rows**, **10.9 min** | **MET** |
| G-4 | retained captures | **not barred — reported.**  Every seed named in any prediction was retained and scored **except KM's three closers, which have no divergence to retain** | **as registered** |
| G-5 | the flash pin | **`distinct_eras 1`, `absent 0`, `incomplete 0`, `build_stale 0`** over **3,840 / 3,840**, every row `era.sof_sha256 = b2a1fe5f83167fbf…` | **MET** |
| G-6 | discards | **1**, denominator **3,839** — registered **3 / 3,837** | **count MISSED, set re-rolled (§3.1)** |

### 3.1 **G-6 — THE DISCARD SET RE-ROLLED A FOURTH TIME, AND THIS TIME IT SHRANK**

Registered `3` = the F17 set.  **Measured `1`.**  Reported as a MISS on the
count, with the A-12 / A-13 process followed and both bases given:

| seed | tier | `ps3_8080` F17 → F18 | `escaped` F17 → F18 | movement |
|---|---|---|---|---|
| `fz2e/509069` | soup | True → **True** | `[500, 16364]` → unchanged | **stayed** — discarded at F15, F16, F17 and F18 |
| `fz2e/515027` | soup | True → **False** | None → None | **LEFT** — now `SUCCESS / clean`, `bad_rows` 618 → **0**, `arch_match` False → **True** |
| `fz2e/524066` | raw | True → **False** | None → **`[732, 7377]`** | **LEFT** — now `SUCCESS / clean`, `bad_rows` 1,127 → **0**, `arch_match` False → **True** |

**`_ps3_8080` is a SOCKET-leg predicate (amendment A-2) and a core-RTL landing
cannot move it by construction.**  Both movers stopped entering 8080 at runtime
and, having stopped, matched.  Both had `first_bad 678` at FLASH #17 — the same
row — which is worth recording as a hint that they share a stimulus, not as a
claim.  This is the **fourth consecutive re-roll** (2 → 2 → 3 → **1**) and the
first in which the set **shrank**.  **NOT a hard stop and NOT a ratchet
violation.**  Both bases:

    on the registered denominator 3,837:  3,727 / 3,837  =  97.1332 %
    on the derived   denominator 3,839:  **3,729 / 3,839  =  97.1347 %**   <- quoted
    including discards            3,840:    3,729 / 3,840  =  97.1094 %

### 3.2 ⚠ **A CLASSIFIER CHANGE BETWEEN THE TWO ERAS, DISCLOSED: `open_bus` WAS RETIRED**

`80075d049a` (*"RETIRE the `open_bus` rule and vocabulary"*, user ruling
2026-08-11) is **NOT an ancestor of `85babd2e4a`**, the FLASH #17 flash commit.
So **F17's capture ran with the `open_bus_escape` accept rule and F18's did
not.**  The visible effect is that seeds previously labelled
`KNOWN_ACCEPTED / open_bus` are now labelled `FUNCTIONAL / func:R@…`; the
clearest example is `fz2e/527051`, whose `bad_rows` **1,003**, `flick` **0**,
`first_bad` **156**, `escaped` `[157, 32518]` and CORE dump are **all
bit-identical** across the pair while its `verdict/sub` moved.

**NO SCORED QUANTITY IN THIS SITTING DEPENDS ON `verdict`.**  Ledger membership
is `bad_rows != 0`; the six seats, the headline, the family table, the
first-divergence bar and the named non-movers are all row-level, and the
discard predicate `ps3_8080` is its own field.  The confound is real, it is
stated here, and it is **why `verdict`/`sub` labels may not be diffed across
the F17 → F18 pair.**

---

## 4. THE SEAT-LEVEL SCORING — `sw/fz2_f18_score.py`

```
python3 sw/fz2_f18_score.py --new sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json
```

### 4.1 **P-1 — KM's THREE SEATS CLOSED IN FABRIC, SEED FOR SEED**

| # | seat | family | mechanism | `bad_rows` F17 → F18 | signal | verdict |
|---|---|---|---|---|---|---|
| 1 | `fz2c/404041` | D2 | **KM** — the `0F` escape's opcode pop is a TF boundary sample | **2,437 → 0** | **high** | **MET** |
| 2 | `fz2e/501066` | D2 | **KM** | **572 → 0** | mid | **MET** |
| 3 | `fz2e/513019` | C2 | **KM** | **2,843 → 0** | **high** | **MET** |

**3 / 3.**  All three have banked `flick == 0`, so both units agree, and none is
below the measured noise **magnitude** (`fz2_capture_noise` measured movers at
1,189–3,312 rows) — a stronger seat set than FLASH #17's, six of whose eight
closed from 2–12 rows.  Expected spoiled seats at the measured floor:
3 × 0.2604 % = **0.008**.

**`fz2c/404041` closed against its own landing's pre-registration** (KM results
§3.1 registered it as *"moves, does not close"*; `S-3` MISSED in the favourable
direction).  Silicon has now agreed with the offline instrument twice.  **The
cell registered the honest reach as "2–3 seeds" and 3 is the top of that range;
nothing here licenses more.**

### 4.2 **P-2 — phantom-T1's THREE SEATS COLLAPSED TO EXACTLY ONE ROW.  THE POINT PREDICTION, NOT THE BAND.**

| # | seat | `bad_rows` F17 → F18 | `flick` | `first_bad_row` F17 → F18 (pred) | verdict |
|---|---|---|---|---|---|
| 4 | `fz2c/404071` | **905 → 1** | **0** | 244 → **243** (243) | **MET, point EXACT** |
| 5 | `fz2e/514044` | **1,261 → 1** | **0** | 235 → **234** (234) | **MET, point EXACT** |
| 6 | `fz2e/516001` | **1,154 → 1** | **0** | 584 → **583** (583) | **MET, point EXACT** |

**3 / 3, and all three hit the PRIMARY POINT rather than merely the [1, 6]
band.**  The registered fabric expectation was *derived* (§4.2a of the
pre-registration): the scored `bs` column is `nec_bus`'s `bs_early`, and
`nec_bus` is the **same RTL in fabric and in `tb_sys`**, so the
one-status-per-clock limit is a property of the DUT + harness pair and the
fabric residual had to be the same single cell.  **It is.**

**`bad_rows == 0` was registered as a FINDING, not a success, and it did not
occur** — which is the clause that makes this a confirmation of the mechanism
rather than of an improvement.  The landing's own booking
(`ackwake_results_2026-08-11.md` §2.5) survives contact with silicon exactly as
written.

**A THIRD INSTRUMENT SAYS THE SAME THING** (§4.7a): all three seats now
disposition **`TRANSIENT` IMMATERIAL with a single differing column, `bs=1`**.
The residue is one status cell and nothing else.

### 4.3 **P-3 — THE HEADLINE: THE REGISTERED PRIMARY POINT, TO THE SEED**

    denominator            3,839        registered 3,837   MISSED (§3.1, the re-roll)
    failures                 110        registered PRIMARY  110      +0
    registered BAND     100 <= 110 <= 120                            MET
    SEED MATCH   3,729 / 3,839 = 97.1347 %    (F17 3,724 / 3,837 = 97.0550 %)
    ROW  MATCH   11,220,552 / 11,330,230 = 99.0320 %   (F17 98.9475 %)
    LEFT the ledger 3    ENTERED 0

⚠ **THE BAND IS 3.3× THE EFFECT AND WAS REGISTERED AS A CONTAINMENT CHECK.
A RESULT INSIDE IT SAYS NOTHING ABOUT EITHER LANDING AND IS NOT QUOTED AS
CONFIRMING ONE.**  That the point was hit exactly is **reported, not claimed as
evidence** — with a ±10 floor and a 3-seed effect, hitting the point to the seed
is as much luck as instrument.  **The evidence is §4.1 and §4.2.**

**P-3a — the row metric, in both units, named** (§1.1):

    corpus rows_diverging (Sigma bad_rows)     119,192 -> 109,678  (-9,514)   predicted 110,023   -345
    Sigma diverging_rows  (Sigma bad + flick)  119,258 -> 109,739  (-9,519)   predicted 110,084   -345

**Both land 345 rows BELOW the prediction, identically** — so the −345 is not a
units effect.  It is the ordinary downstream row-count noise on long-tail seeds
that the pre-registration said was *reported, not barred*: no seed's membership
moved, no first divergence moved, and **no seed anywhere gained a row**.  There
was **no registered row cost this sitting** and none appeared.

### 4.4 **P-4 / P-5 — ZERO UNREGISTERED MEMBERSHIP FLIPS.  THE BUDGET WAS TEN.**

    entered the ledger        0        budget 10
    unregistered exits        0        (exits 3, all three registered)
    TOTAL unregistered flips  0        budget 10        MET

**Zero.**  FLASH #17 used 7 of its 10-seed budget and FLASH #16 used several;
this is the first fz2 flash with **no unregistered ledger movement at all**.
The attribution dichotomy registered in §4.4 of the pre-registration was
therefore never invoked, and no seed needed a noise explanation.

⚠ **`fz2_ledger`'s own printed diff is NOT the previous era** — its default
`--diff` is *"the committed one"*, `fz2_failure_ledger_2026-08-09.json` (198
failures, the FLASH #13 era).  Its `LEFT 95 / ENTERED 7` is the cumulative
F13 → F18 figure and `198 − 95 + 7 = 110` checks it.  **Against FLASH #17 the
movement is LEFT 3 / ENTERED 0.**  This is the same class of trap as F17 §6's
`--suffix` warning and is recorded so the next sitting does not misread it.

### 4.5 **P-6 — THE FALSIFIER: `fz2c/404040` IS ABSENT.  MET.**

The branch's sharpest falsifier did not fire.  Neither landing broke a
mechanism nobody claimed.

### 4.6 **P-7 — ALL FOURTEEN NAMED NON-MOVERS UNMOVED, IN BOTH COLUMNS.  14 / 14 MET.**

| group | seeds | result |
|---|---|---|
| the **§64.1 four** | `fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` | `bad` 840 · 921 · 891 · 984 and `first` **527 · 1331 · 636 · 1475**, all unchanged |
| the **W7-4 older §64.1 four** | `fz2c/406063` · `fz2c/410047` · `fz2e/518053` · `fz2e/535027` | 3149/245 · 3589/227 · 3413/567 · 3226/296, unchanged |
| the **M10 LEA-mod3 six** | `fz2c/406054` · `fz2c/408019` · `fz2e/518038` · `fz2e/522019` · `fz2e/524034` · `fz2e/530001` | 3141/470 · 1087/1617 · 194/429 · 3075/396 · 3479/457 · 20/442, unchanged |

Scored `N[s]` against `R[s]` per amendment A-1; the prereg §4.7 literals are
printed beside it as a transcription check and the one flagged mismatch
(`fz2c/408019`, prereg 1086 vs ledger 1087) is the `flick`, as A-1 predicted.

### 4.7 **P-8 — THE FAMILY TABLE: BOTH PREDICTED CELLS EXACT**

| ledger family | F17 | predicted | **F18** | verdict |
|---|---:|---:|---:|---|
| C2 INTA-vectored delivery | 10 | **9** | **9** | **MET** |
| D2 core fetched, chip did not | 10 | **8** | **8** | **MET** |
| all thirteen others | | (unchanged) | **unchanged** | **MET** |
| **total** | **113** | **110** | **110** | |

The three collapsed seats **stayed in C2**, so the registered
re-classification escape hatch was not needed.

### 4.7a ⚠ **P-7a — MISSED ON BOTH CLAUSES, AND THE SECOND MISS IS THE INTERESTING ONE**

Registered: *"G1-G8 PASS and no member of the [IMMATERIAL] class is one of this
sitting's six seats (none is)."*  Measured:

| clause | result |
|---|---|
| G1 DUMP PROOF · G2 DUMP IDENTITY · G3 SCHEDULE · G4 NOT UNIVERSAL · G5 CONTROLS · G8 NO FORK | **PASS** — every clause that tests the **derivation itself** |
| **G6 THE CENSUS** | **FAIL** — 6 / 8 registered cells disagree |
| **G7 THE DOCUMENT** | **FAIL** — 4 / 25 doc-vs-derivation disagreements |
| *"no member of the class is one of the six seats"* | **FALSE — three of the six ARE** |

**G6 and G7 are both doc-vs-derivation cross-checks against
`fz2_materiality_census_2026-08-11.md`, which is a FLASH #17-era snapshot** (113
failures / 21 IMMATERIAL / residue 92).  On the F18 ledger the derivation is
**110 / 24 / 86**.  This is the `fz2_w1 lint` pattern — *"if a doc edit trips
it, fix the doc"* — and **the fix is deliberately NOT applied in this sitting**:
editing a document to clear a falsifier in the same sitting that measured the
failure is the move this campaign's own rules distrust, even when benign.  The
census document is instead **labelled** as an F17-era snapshot (a labelling
change cannot make G6/G7 pass), and the re-derivation is **booked**.

**The second miss is a result, not a defect.**  The three seeds that entered the
class are exactly **phantom-T1's three seats**, at `TRANSIENT` /
`bs=1` / one differing column:

    fz2c/404071   TRANSIENT   bad 1   bs=1   C2 INTA-vectored delivery
    fz2e/514044   TRANSIENT   bad 1   bs=1   C2 INTA-vectored delivery
    fz2e/516001   TRANSIENT   bad 1   bs=1   C2 INTA-vectored delivery

**phantom-T1 did not close its three seats — it moved them from 905 / 1,261 /
1,154-row failures into the dispositioned-IMMATERIAL class at a single status
cell.**  The pre-registration asserted *"(none is)"* from the F17 ledger and
that assertion was simply wrong about the future; it is reported as a **MISS**
because it was written as a registered clause.  ⚠ **The quoting rule still
applies**: the residue is *"86 material-or-unproven of 110 diverging of 3,839"*,
never `86 / 3,839` alone, and **it did not shrink** — 110 seeds still diverge.

### 4.8 **P-9 — THE FIRST-DIVERGENCE BAR, IN ITS STRONG FORM: 3 / 3 EXACT, 0 UNREGISTERED, 0 INCREASES**

    registered earlier-movers that moved earlier   3 of 3, each to its predicted row
    UNREGISTERED first-divergence DECREASES        0        MET
    first-divergence INCREASES (reported)          0

FLASH #17 needed nineteen named exemptions for this bar; this sitting's replay
named **three** and no other seed moved its first divergence **in either
direction** over all 107 still-failing seeds shared by the two eras.

---

## 5. THE OFFLINE INSTRUMENT'S FIDELITY

### 5.1 **Q-1 — THE FABRIC ERA GUARD PASSES WITHOUT THE BYPASS.  MET.  THIS WAS THE POINT OF THE FLASH.**

    its inputs  87/88 hash IDENTICAL in the tree at HEAD
      MOVED     hdl/nec_test_ucore.qsf   [EXEMPT: Quartus rewrites it in place, §70.7; carries no RTL]
    FABRIC ERA GUARD: PASS

At HEAD before the flash it refused by name on **four RTL files**
(`system_large.sv`, `v30u_biu.sv`, `v30u_eu.sv`, `v30u_eu_step.svh`).  It now
passes.  **87/88 rather than F17's 88/88** because E-8 regenerated the `.qsf`
after the draws, restoring it to `95770c099a9505d6…` while the flashed receipt
records the post-compile `b719d4ff97e5b7d7…`; the file is the one declared
exemption and carries no RTL.  **Every KM and phantom-T1 figure quoted before
this sitting carried `--no-fabric-era-guard` and said so; from FLASH #18 onward
the bypass is not needed and is not used.**

### 5.2 **Q-2 — THE CLOSING CONTROL: 260 / 260 = 100.0 %, `first_bad` IDENTICAL ON 110 / 110**

`fz2_replay --ledger <F18> --all-failures --pass-sample 150 --leg ret`, **era
guard ON, no override**, `tb_sys` receipt `6e6589e25c2b90aa…`, 22 s, 0 errors:

    fabric PASS  150   replay PASS 150   replay FAIL   0
    fabric FAIL  110   replay PASS   0   replay FAIL 110
    AGREEMENT 260 / 260 = 100.0 %      first_bad IDENTICAL on 110 / 110

Registered bar was **≥ 255 / 260**.  **MET in the strongest available form.**

### 5.3 **THE §4.3b ESCAPE-TARGET FLAG — TESTED ON A SECOND ERA PAIR, AND IT HELD**

F17 §4.3b booked: *"`escaped` target movement is a 3-in-1,112 event and every
instance so far changed a disposition"*, with the falsifier *"an era pair in
which a seed's escape target moves and its disposition does not."*  Over the
**1,111** seeds escaped in either F17 or F18:

    escape target MOVED        1 / 1,111      (fz2e/524066, None -> [732, 7377])
    disposition FLIPPED        1 / 1,111      (fz2e/524066)
    BOTH                       1

**The falsifier did NOT fire.**  Sufficiency is now **4 of 4** across two era
pairs.  ⚠ **Necessity is NOT re-established here**: `fz2e/515027` also changed
disposition and its escape target did not move — but it has `escaped_n == 0` in
both eras, so it is outside this population by construction and the F17
measurement of *"NOT NECESSARY (1 of 13)"* stands unchallenged rather than
confirmed.  n = 1 on this pair; the booking is unmoved, not strengthened.

---

## 6. THE STANDING GATES, RE-MEASURED ON THIS ERA

| gate | result |
|---|---|
| `fz2_w1 bars` | **11 / 11 MET** — C-1 … C-11 on the F18 corpus, and **leaf-diffed against the F17 archive: not one of the eleven verdicts moved.** C-6 `hold_rows_exact` **4,638 / `hold_rows_off` 0**, unchanged; C-8 `div_guards` 63 / **unpinned 0**; C-4 `distinct_eras` 1 |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_ledger --control --suffix=-F13-archive` | **PASS 9 / 9** — failure SET identical 198/198 symdiff empty, denominator 3,837, matched 3,639, 3 discards, 14 family counts identical, `first_bad_row` 198/198, `diverging_rows` 198/198, arch 196/198, overlay 40.  **The derivation is quotable.** |
| `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| `gen_ucore_qsf --check` | **PASS** |
| `r7_lint` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / **0 violations** |
| `ss_lint --core ucore` | **PASS** — 103 BIU + 122 EU = **226**, **214 flops, 0 UNMAPPED** |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `fz2_immaterial falsify` | ⚠ **FAIL on G6/G7 only** — §4.7a; G1-G5 and G8 PASS |
| §38.9 missed-trap overlay | **4** (F17: 4) |

---

## 7. HARD STOPS

**ONE FIRED AND WAS OBEYED**: **E-6**, the retention receipt self-labelling
`CONTROL/DEFAULT` (§1.2).  Nothing was flashed on that build; the recipe was
corrected and the build re-run.

**None of the others fired**: `safe_flash` VERIFY ok try 1 · 0 `div_guard`
UNPINNED across 70 probes · 0 `RigMismatch` · 0 quarantines · every
capture-integrity bar (G-1 … G-5) met · first light MATCH 800 ×3 · `use_core = 0`
chip proof MATCH 800 after everything · `board_idle()` clean · **0 chip-column
movers on either directed cell** · no contradiction inside the pre-registration.

**The registered non-stops, reported with their denominators**: the G-6 discard
re-roll (§3.1), P-7a's two clauses (§4.7a), and §1.5's retention-vs-control sign
inversion.

---

## 8. THE DIRECTED-CELL SPOT-CHECKS (`S-1` … `S-5`)

Both cells' board legs are **socket-only (`use_core=False`)**, so they measure
**SILICON**, which no bitstream can move.  The banked trees were copied aside
before the run and **restored afterwards**.

| # | leg | measured | verdict |
|---|---|---|---|
| **S-1** | `tf0f_cell run --strata nop,x1b,z1b` — 48 cells, 2 s, 0 transport errors, 0 TAKE-unstable | **0 CHIP-COLUMN MOVERS over all 48**, `n_entries` 6 on every probe as banked | **MET** |
| **S-2** | `tf0f_cell score` | **chip == core, 0 / 512 differing on ALL SIX columns** (`n_entries`, `pushed_off`, `pushed_off_set`, `lastcode_off_set`, `uniform`, `term_done`).  `nop` **6**, `x1b` **8**, `z1b` **9** — the KM column, in a FLASH #18 era.  **`KM` is the only boundary law surviving on every one of the 30 probes.**  NULL `notf`/`v_notf` **[0]** both.  Stability 64/512 ×3: TAKE-unstable 0, stream-distinct 0 | **MET** |
| **S-3** | `ie_pinfall_cell run --strata eihlt_w0,ierun_w0 --limit 20` (40 cells) then `core` (2,200 cells, 431 s) then `score` | **0 CHIP-COLUMN MOVERS.**  Board-vs-core: **`n_inta` 30, `ack_off` 40, `ack_off_hlt` 40** — reproducing ack-wake's predicted 36 → 30 / 46 → 40 / 46 → 40 **exactly**, now against fresh FLASH #18 silicon.  The six invariant columns `wake_prefetch` · `rise` · `fall` · `t_ei` · `anchor_t1` · `n_rows` all **0 / 1,920**; the free-running legs **0 core disagreements** at every wait | **MET** |
| **S-4** | `div_guard` + single-writer on both legs | **0 UNPINNED**, `single_writer OK` before each | **MET** |
| **S-5** | restoration | **445 banked files byte-identical to HEAD**, verified by sha256 manifest before and after | **MET** |

**The registered expectation held exactly: the chip columns are UNCHANGED
because silicon did not change, and the only movement is in the CORE columns
where KM and phantom-T1 predict it.**  The FLASH #18 rows are retained beside
the banked ones at `sw/testdata/tf0f/f18-spotcheck/` and
`sw/testdata/ie-pinfall/f18-spotcheck/` (163 files) rather than merged into
them.

⚠ **S-3's `core` leg was re-taken on the landed RTL and then restored**, so
`sw/testdata/ie-pinfall/core` remains the pre-landing column the ack-wake
sitting deliberately preserved.  The post-landing figures above are quotable
from the `f18-spotcheck` copy and from this document, **not** from the banked
directory.

---

## 9. WHAT THIS SITTING ESTABLISHED, AND WHAT IT LEAVES OPEN

**ESTABLISHED**

1. **KM is confirmed in silicon, 3 seats of 3**, two of them high-signal
   (2,437 and 2,843 rows), on a bitstream built from the merged tree, scored
   against a pre-registration committed before the build by a scorer committed
   before the flash and proved non-vacuous on the null.
2. **phantom-T1 is confirmed in silicon in the harder form: it hit a NON-ZERO
   point prediction, 3 seats of 3, at `bad_rows == 1` and `first_bad` exactly
   one row earlier.**  A landing that predicts *"this will still fail, and by
   exactly this much"* and is right is stronger evidence than one that predicts
   a closure, because the failure mode is where the model could most easily
   have been wrong.  Three independent instruments agree the residue is one
   `bs` cell: the fabric ledger, the HLT sweeps' `busstat: exp 'CODE' got
   'PASV'`, and the IMMATERIAL census's `bs=1`.
3. **The fabric era guard is re-synced and the bypass is retired** (Q-1).
4. **ZERO unregistered ledger membership flips** — the first fz2 flash with
   none — and **260/260 offline-vs-fabric agreement** with `first_bad`
   identical on 110/110.
5. **FLASH #17 §5.3 is closed**: the "unexplained one-sided residue" was
   `flick`, i.e. two different quantities, found offline before this capture.
6. **M10-SYS is synthesis-inert, proved by reading and confirmed by the
   compiler** (§1.4).

**OPEN, WITH THEIR FALSIFIERS**

1. **The IMMATERIAL census document is one era stale** and G6/G7 fail against
   it (§4.7a).  The re-derivation is booked; it was deliberately not done in
   the sitting that measured the failure.
2. **`quartus_gate.py` has no way to produce a retention build** (§1.2); the
   recipe lives only in prose, and an environment variable is silently
   accepted and ignored.  A `--retention` flag is the obvious fix and needs its
   own pre-registration.
3. **The discard set has now re-rolled on four consecutive flashes**
   (2 → 2 → 3 → 1, seven distinct seeds involved).  `_ps3_8080` is socket-leg.
   *Falsifier*: a double-capture on one bitstream in which `ps3_8080` is stable
   seed for seed.
4. **The retention/control Fmax sign inverted back** after five in the other
   direction (§1.5), and the flashed build sits **+0.82 MHz** above this
   sitting's own hard stop.  Recorded, not explained.
5. **The escape-target flag's NECESSITY is untested on this pair** (§5.3):
   sufficiency is 4/4, but the one non-escaped disposition-changer is outside
   the population by construction.
6. **phantom-T1's remaining single cell is the `system_large` status-pin
   observation model** — the integration change ack-wake §2.5 booked and did
   not take, to be measured as its own mechanism with its own G6.
