# FLASH #17 — RESULTS, AS REGISTERED

Pre-registration `docs/notes/fz2_flash17_prereg_2026-08-11.md`, committed
**`b1630239cc`** — before any Quartus build and before any board contact.
Scorer `sw/fz2_f17_score.py`, committed **`85babd2e4a`** — written while the
CONTROL build was still running, before the flash and before the F17 ledger
existed, and **non-vacuous against the F16 null (0/8 seats, 11 clauses
MISSED)**.

Every bar is reported in the form it was registered in.  **Nothing is
re-registered after the fact.**

---

## 0. THE HEADLINE, IN ONE PARAGRAPH

**WAVE 4 IS CONFIRMED IN SILICON, SEAT FOR SEAT: ALL EIGHT NAMED SEATS CLOSED —
8 / 8, both high-signal seats and all six low-signal ones — with ZERO
unregistered first-divergence decreases and the nineteen registered
earlier-movers landing on their predicted rows EXACTLY, 19 of 19.**  The
headline reads **113 failures of 3,837**, inside the registered band
[98, 118] and **+5 over the registered primary of 108** — and, exactly as the
pre-registration required, *that band is not quoted as evidence*: **the evidence
is the eight seats.**  The +5 is fully itemised and fully attributed: **six new
failures, all six ESCAPED seeds running OPEN BUS, all six with the CORE dump
bit-identical between eras**, and **one unregistered ledger EXIT** —
`fz2e/513017`, which is FLASH #16 §5.4's own proven one-off socket artifact
correcting itself, its terminator `fired` going **0 → 5** in a fresh era.  Total
unregistered membership flips **7, inside the registered noise budget of 10**.
**Two clauses MISSED and are reported as registered**: the D3 family reads 5
where 4 was registered, and NEW/UNCLASSIFIED moved 3 → 7 — **both are the same
six escaped seeds**.  ⚠ **And this sitting produces one ERRATUM against FLASH
#16**: `fz2e/527051`, which F16 §5.1 called *"the wave's point"* and *"the
sharper of the two"*, is an **ESCAPED open-bus seed whose bus is not
reproducible by construction**, it has now gone FAIL → PASS → FAIL across three
flashes with its CORE dump bit-identical throughout, and **it was never a
quotable seat.**  P5′ survives that erratum intact on `fz2c/406023`, which held
its closure on a fresh era, and on wave 4's own four stall seats, all four of
which closed here.

---

## 1. THE BUILD — G6, BOTH CONFIGURATIONS (`E-1` … `E-10`)

Each from a deleted `db` / `incremental_db` / `output_files_ucore`, Quartus
17.1.0 Build 590.  **ONE clean draw per configuration, as registered** (the RTL
is wave-4's already-drawn tree).

| | **CONTROL** | **RETENTION (flashed)** |
|---|---|---|
| verdict | **PASS** | **PASS** |
| receipt | **`910c6548094b931b…`** | **`287665a1027b42dd…`** |
| label | `fz2 FLASH#17 CONTROL draw1` | `fz2 FLASH#17 RETENTION ret1` |
| **Fmax (`divclk`)** | **41.33 MHz** | **42.04 MHz** |
| **worst setup** | **+7.053 ns** | **+6.073 ns** |
| **TNS setup / hold** | **0.000, every domain** | **0.000, every domain** |
| ALMs | 12,279 / 41,910 (**29 %**) | 12,210 / 41,910 (**29 %**) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `8e1d999fd5b51560…` | `b6f816c77c8bf81c…` |
| `.sof` sha256 | `ed523981fdada605…` | **`26c19f613e2caae8…`** |
| `.rbf` sha256 | `3ea2761524b9547d…` | **`f08fdd1ad4ef5a15…`** |
| compile | 588 s | ~700 s |
| git | `b1630239cc` (clean) | `85babd2e4a`-dirty — see §1.2 |

| # | bar | verdict |
|---|---|---|
| E-1 | `gen_ucore_qsf --check` BEFORE each draw | **MET** — *"up to date"* both |
| E-2 | 0 errors, every stage Successful, 0 latches, 0 `lpm_divide` | **MET** both |
| E-3 | Fmax ≥ 32 MHz | **MET** — 41.33 / 42.04 |
| E-4 | worst setup > 0 | **MET** — +7.053 / +6.073 |
| E-5 | TNS 0.000 setup **and** hold, every domain | **MET** both |
| E-6 | the retention receipt self-labels RETENTION | **MET** — `RETENTION (X1_AD_RETENTION=1) -- DERIVED from …flow.rpt, …map.rpt` |
| E-7 | the control receipt self-labels `CONTROL/DEFAULT` | **MET** — derived, not asserted |
| E-8 | `.qsf` regenerated and re-checked AFTER each draw | **MET** — `rc 0` |
| E-9 | the macro's effect is CHECKED, not asserted | **MET** — retention `.rbf f08fdd1a…` **differs** from control `.rbf 3ea27615…` |
| E-10 | both receipts retained | **MET** — in `sw/testdata/receipts/quartus_bitstream.jsonl` |

### 1.1 **THE SOFT Fmax EXPECTATION MISSED — HIGH — AND IS REPORTED, NOT EXPLAINED**

§2.1 registered a **soft** expectation of **38.0–40.5 MHz** for the merged
CONTROL draw.  It drew **41.33**, which is **above the band and above every
CONTROL draw this branch has ever taken**:

    39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11 · 40.42        (pre-wave-4)
    38.39 (pkg A, x2) · 39.05 (ghost cone, x2) · 39.55 (pkg B, x2)  (wave 4, three
                                                                     SEPARATE worktrees)
    41.33                                                        (THIS TREE, the
                                                                  first draw of the
                                                                  MERGED tree)

The merged tree had never been drawn before this sitting, so there is no prior
for it and none is invented.  **`standing_gates.md` §A governs: one green build
is not closure, one draw is not a distribution, and the same tree has drawn
19.42 and 45.91 MHz.**  Registered as a soft expectation precisely so this would
be reportable rather than a stop; it is **reported as a MISS in the high
direction and nothing is concluded from it.**

**THE RETENTION-VS-CONTROL SIGN — THE FIFTH OBSERVATION, AND IT INVERTS AGAIN:**

    CONTROL     41.33 MHz   +7.053 ns
    RETENTION   42.04 MHz   +6.073 ns
    difference  +0.71 MHz   -0.980 ns   -- RETENTION ABOVE CONTROL ON Fmax

**Fifth consecutive Fmax inversion on this branch** (#13 +0.46, #14 +1.50,
#15 +2.24, #16 +0.12, **#17 +0.71**).  A-1.1a's registered falsifier now has
five of five.  ⚠ **NEW THIS SITTING, AND REPORTED NOT EXPLAINED: the two figures
disagree in SIGN with each other** — Fmax went **up** while worst setup went
**down** by 0.98 ns.  They are different quantities (`E-4` is the minimum over
all four domains' worst setup, which includes cross-domain paths; `E-3` is the
per-clock Fmax), so there is no arithmetic contradiction — but on this branch
they have moved together every previous time, and this is the first pair that
does not.  **No claim either way.**

### 1.2 **THE RETENTION DRAW WAS TAKEN ON A DIRTY TREE, AND THE RECEIPT SAYS SO**

`git 85babd2e4a-dirty`.  The dirt is enumerated here rather than waved at:
**`hdl/nec_test_ucore.qsf`** (Quartus rewrites it in place — the declared §70.7
exemption) and **`sw/testdata/receipts/quartus_bitstream.jsonl`** (the gate's own
append-only output, carrying the CONTROL receipt taken twenty minutes earlier),
plus two untracked build logs.  **No RTL file was modified**, and the 88-file
input manifest is the check on that claim: `hdl/rtl/` is byte-identical to
`b1630239cc`, which is byte-identical to `8280031c8d` on `hdl/rtl`.

---

## 2. THE FLASH AND FIRST LIGHT (`F-1` … `F-9`)

**FLASH #17 IS ON THE BOARD.**  `nec_test_ucore.sof`
**`26c19f613e2caae8cf3479244319988227a748c000f456c458d901b4ee266a6c`**, `.rbf`
**`f08fdd1ad4ef5a15…`**, built from `85babd2e4a` **WITH `X1_AD_RETENTION=1`**,
through `sw/safe_flash.sh` with its VERIFY leg.  **IT IS THE FIRST BITSTREAM TO
CARRY WAVE 4** — the 8F ghost-read ADDRESS cone (`ghost_relax` deleted), P5′-stall
and P4′-space.

| # | bar | measured | verdict |
|---|---|---|---|
| F-1 | flash + ledger, VERIFY OK, log 19 → 20 | **VERIFY ok try 1** (`pwr_good True`, `cpu_running True`, `use_core False`), **20 entries**, tail `verify: "OK"` | **MET** |
| F-2 | first light MATCH 800 on all three legs | **chip-vs-golden · core-vs-chip · core-vs-golden all MATCH 800**, `rc 0` | **MET** |
| F-3 | RBCHECK exactly 8 registers | **8** — `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, `TVEC`, `VECCTL` | **MET** |
| F-4 | C-6 control, 9 legs / 51 checks | **9 legs, 51 checks, `failing_legs []`**, INTA vector **255 (0xFF)**, holds `[2,20,300]` on `[pin_int, pin_nmi]`, TVECs `(0,48896)` / `(3056,8)`, **P1–P5 run lengths 2 · 300 · 2 · 300 · 20 to the clock**, N1 negative control PASS | **MET** |
| F-5 | `use_core=0` chip proof **after everything** | **MATCH over 800 rows**, `rc 0` | **MET** |
| F-6 | `div_guard` tally, 0 UNPINNED | **0 UNPINNED** — 10 (control) + 1 (preflight) + 1 (preflight-end) + 48 (capture) + 1 (idle) | **MET** |
| F-7 | transport, 0 `RigMismatch` | **0** — 0 quarantines, 0 run-error lines (C-10) | **MET** |
| F-8 | `board_idle()` | **OK, `use_core = 0` left selected** | **MET** |
| F-9 | single-writer / socket-only | **OK** — asked of the board twice (before flash, at preflight): no `v30ctl`/`serve` process on the board, none locally | **MET** |

**F-2's registered justification held.**  Wave 4's three mechanisms need a
`MOV CS,rm` at a retarget boundary, an `8F` with `mod == 3`, or an I/O-space
fork.  The boot program has none, so MATCH 800 was the correct prediction and it
is a control on the flash, not a test of the landing.

---

## 3. THE RE-CAPTURE AND THE INTEGRITY BARS (`G-1` … `G-6`)

The FLASH #16 corpus was archived **by rename** first — nothing deleted:
`fz2c`/`fz2e` → `*-F16-archive`, and `fz2_capture` / `fz2_bars` /
`fz2_preflight` / `fz2_control` `.json` → `*_F16-archive.json`.  Then
`fuzz_campaign.py new fz2c` / `new fz2e` re-pinned both manifests to the
resident flash (`pin sha256 26c19f613e2c…`).

| # | bar | measured | verdict |
|---|---|---|---|
| G-1 | corpus identity | `SEED_LIST_SHA256 45d25f31a325c496…`, 960 + 2,880 = **3,840**, 48 strata | **MET** |
| G-2 | preflight | `verdict OK`, board leg run, era pinned to receipt `287665a1027b…`, **192-seed regeneration sample hits = 0** | **MET** |
| G-3 | completeness | **48 / 48 strata, every `rc 0`**, `halted null`, **960 / 2,880 rows**, 11.0 min, 657 s of board time | **MET** |
| G-4 | retained captures | **not barred — reported.**  495 (`fz2c`) + 159 (`fz2e`) = **654** retained; every seed named in any prediction was retained and scored **except the eight closers, which have no divergence to retain** (that is what a closure means, and §4.1's verdicts are ledger membership, which does not need one) | **as registered** |
| G-5 | the flash pin | **`distinct_eras 1`, `absent 0`, `incomplete 0`, `build_stale 0`** over **3,840 / 3,840**, every row `era.sof_sha256 = 26c19f613e2caae8…` and `era.rtl.receipt_id = 287665a1027b42dd…` | **MET** |
| G-6 | discards | **3**, denominator **3,837** — registered **2 / 3,838** | **count MISSED, set re-rolled (§3.1)** |

### 3.1 **G-6 — THE DISCARD SET RE-ROLLED AGAIN, AND THE COUNT MISSED BY ONE**

Registered `2` = the F16 set.  **Measured `3`.**  Reported as a MISS on the
count, with the A-12 / A-13 process followed and both bases given:

| seed | tier | `ps3_8080` | movement |
|---|---|---|---|
| `fz2e/509069` | soup | True | **stayed** — discarded at F15, F16 and F17 |
| `fz2e/535075` | raw | — | **LEFT** the discard set (it entered at F16) |
| `fz2e/515027` | soup | True | **ENTERED** (`FUNCTIONAL / done_mismatch`, 618 rows) |
| `fz2e/524066` | raw | True | **ENTERED** (`KNOWN_ACCEPTED / open_bus`, 1,127 rows) |

**`_ps3_8080` is a SOCKET-leg predicate (amendment A-2) and a core-RTL landing
cannot move it by construction.**  This is the third consecutive flash on which
the set re-rolled inside the same escaped / non-reproducing socket population
(F15 → F16 moved two, F16 → F17 moves three).  **NOT a hard stop and NOT a
ratchet violation.**  Both bases:

    on the registered denominator 3,838:  3,724 / 3,838  =  97.0297 %
    on the derived  denominator 3,837:  **3,724 / 3,837  =  97.0550 %**   <- quoted
    including discards            3,840:    3,724 / 3,840  =  96.9792 %

---

## 4. THE SEAT-LEVEL SCORING — `sw/fz2_f17_score.py`

```
python3 sw/fz2_f17_score.py --new sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
```

### 4.1 **P-1 — ALL EIGHT SEATS CLOSED IN FABRIC, SEED FOR SEED.  THIS IS THE SITTING'S RESULT.**

| # | seat | family | mechanism | rows F16 → F17 | signal | verdict |
|---|---|---|---|---|---|---|
| 1 | `fz2e/519016` | E1 | ghost ADDRESS | **2 → 0** | low | **MET** |
| 2 | `fz2e/520040` | E1 | ghost ADDRESS | **4 → 0** | low | **MET** |
| 3 | `fz2e/520062` | D3 | **P5′-stall** | **2966 → 0** | **high** | **MET** |
| 4 | `fz2e/528008` | D3 | **P5′-stall** | **3197 → 0** | **high** | **MET** |
| 5 | `fz2e/532012` | D3 | P5′-stall | **4 → 0** | low | **MET** |
| 6 | `fz2e/533028` | D3 | P5′-stall | **12 → 0** | low | **MET** |
| 7 | `fz2e/527055` | E2 | P4′-space | **4 → 0** | low | **MET** |
| 8 | `fz2e/528030` | E2 | P4′-space | **9 → 0** | low | **MET** |

**8 / 8 — high-signal 2 / 2, low-signal 6 / 6.**

**§4.1b is honoured rather than quietly dropped**: the two seats that close from
**2,966** and **3,197** diverging rows carry more evidence than the six that
close from 2–12 rows, and this document does not count all eight equally.  The
weight of the result sits on `fz2e/520062` and `fz2e/528008`, which are P5′'s,
and on the fact that **all four of package A's stall seats closed** — the four
that FLASH #16 registered as *staying failing* and which did stay failing there,
on the same instrument, at the same predicted row counts.  **The instrument that
was right about them at F16 is right about them at F17 in the other direction.**

**Expected spoiled seats at the measured noise floor: 8 × 0.2604 % = 0.021.**

### 4.2 **P-2 — THE HEADLINE: INSIDE THE BAND, +5 OVER THE PRIMARY, AND NOT QUOTED AS EVIDENCE**

    denominator            3,837        registered 3,838   MISSED (§3.1, the re-roll)
    failures                 113        registered PRIMARY  108      +5
    registered BAND     98 <= 113 <= 118                            MET
    SEED MATCH   3,724 / 3,837 = 97.0550 %    (F16 3,722 / 3,838 = 96.9776 %)
    ROW  MATCH   11,205,421 / 11,324,613 = 98.9475 %   (F16 98.9139 %)
    LEFT the ledger 9    ENTERED 6

⚠ **THE BAND IS 1.25× THE EFFECT AND WAS REGISTERED AS A CONTAINMENT CHECK.
A RESULT INSIDE IT SAYS NOTHING ABOUT WAVE 4 AND IS NOT QUOTED AS CONFIRMING
IT.**  It is quoted here for exactly one purpose — the result did not leave the
band, so no aggregate-level investigation is owed.  **The evidence is §4.1.**

**P-2a — the ROW metric, with its two registered costs paid in the open.**
Σ `diverging_rows` over each era's own ledger: **123,084 → 119,258 (−3,826)**,
against a predicted point of 118,662.  The two costs the ghost-address landing
named **in advance** (W-2) both landed **EXACTLY** on their predicted values and
are not netted away:

| seat | F16 → F17 | predicted | why it was predicted not to close |
|---|---|---|---|
| `fz2e/518039` | 102 → **1,587** | 1,587 | its two ghost addresses are IVT entries — trap-delivery timing, not an address (M10 §5.3) |
| `fz2e/526054` | 4 → **320** | 320 | the offsets are IDENTICAL and the fork is the SEGMENT (M10 §5.2) |

### 4.3 **P-3 — SIX NEW FAILURES.  ALL SIX ARE ESCAPED OPEN-BUS SEEDS AND THE CORE IS PROVABLY UNINVOLVED.**

The registered attribution dichotomy was applied to every one.  **None carries a
wave-4 mechanism.  All six carry the positive noise evidence the
pre-registration demanded**, and the evidence is the same on all six:

| seed | tier | F16 verdict → F17 | `escaped_n` | `ob_escape.frac` | **CORE dump** | **CHIP dump** |
|---|---|---|---|---|---|---|
| `fz2e/521006` | raw | `SUCCESS / window_truncated` → `KNOWN_ACCEPTED / open_bus` | 23 | 1.0 | **IDENTICAL** | IDENTICAL |
| `fz2e/521024` | raw | `SUCCESS / clean` → `KNOWN_ACCEPTED / open_bus` | 60 | 1.0 | **IDENTICAL** | IDENTICAL |
| `fz2e/522002` | raw | `SUCCESS / clean` → `KNOWN_ACCEPTED / open_bus` | 115 | 1.0 | **IDENTICAL** | IDENTICAL |
| `fz2e/527051` | raw | `SUCCESS / clean` → `KNOWN_ACCEPTED / open_bus` | 31 | 1.0 | **IDENTICAL** | **MOVED** (§4.3a) |
| `fz2e/529058` | raw | `SUCCESS / window_truncated` → `KNOWN_ACCEPTED / open_bus` | 79 | 1.0 | **IDENTICAL** | IDENTICAL |
| `fz2e/534003` | raw | `SUCCESS / window_truncated` → `KNOWN_ACCEPTED / open_bus` | 4 | 1.0 | **IDENTICAL** | IDENTICAL |

**Six of six are `tier raw`, six of six are escaped, six of six ran fully open
bus (`frac 1.0`), six of six have an image sha256 identical between eras, and
six of six have a bit-identical CORE dump.**  **Escaped programs have no
reproducible bus** — F14 §4, invoked at F16 §5.4 for `fz2e/534041` and again
here — and `fz2_capture_noise_2026-08-10.md` measured escaped seeds flipping at
**0.629 %** against a base rate of 0.110 % (**5.7×**).  Six of 3,840 is
**0.156 %**, comfortably inside that.

**A core-RTL landing cannot move the `use_core = 0` socket leg by
construction**, and the CORE leg is bit-identical on all six, which is the
direct measurement of that and not an appeal to it.

### 4.3a ⚠ **`fz2e/527051` — AN ERRATUM AGAINST FLASH #16 §5.1**

FLASH #16 §5.1 quoted this seat as **P-1's sharper closer** and as *"the wave's
point"*: it was FLASH #15's one scored-row chip mover, the faithful replay
closed it 1011 → 0, and silicon closed it too.  This sitting finds that **the
seat is an ESCAPED open-bus seed and its ledger membership is not a stable
measurement**:

| | FLASH #15 | FLASH #16 | **FLASH #17** |
|---|---|---|---|
| ledger | **FAIL** 1,011 rows, `first_bad` 156 | **PASS** (rows 0) | **FAIL** 1,003 rows, `first_bad` **156** |
| verdict / sub | — | `SUCCESS / clean` | `KNOWN_ACCEPTED / open_bus` |
| `escaped_n` | — | 31 | 31 |
| escape target | — | `[157, 24326]` | `[157, **32518**]` |
| CORE dump | — | *(reference)* | **BIT-IDENTICAL to F16** |
| CHIP dump | — | *(reference)* | **MOVED** |

The seed escapes at instruction 157 in both eras and then runs into a
**different open-bus region** (`24326` → `32518`).  Its `first_bad` at F17 is
**156** — one instruction before the escape, and the same row as FLASH #15's.
**The core did not move; the chip's open-bus trajectory did.**

**What is withdrawn**: F16 §5.1's use of `fz2e/527051` as a seat-level
confirmation of P5′.  A seat whose bus is not reproducible by construction
cannot confirm or refute anything, and it should have been excluded before it
was quoted — the information needed to exclude it (`escaped_n 31`) was in its
own banked row at the time.

**What is NOT withdrawn, and why P5′ still stands:**

1. **`fz2c/406023` — F16's OTHER closer, the "clean closer" — HELD ITS CLOSURE
   ON A FRESH ERA**: `SUCCESS / clean`, `bad_rows 0`, at both F16 and F17, with
   its CORE dump bit-identical.  It is escaped (`escaped_n 22`) but it is
   **stable across two independent captures**, which is the property
   `fz2e/527051` lacks.
2. **All four of wave 4's own P5′-stall seats closed here** (§4.1, rows 2,966 ·
   3,197 · 4 · 12), and two of them are the highest-signal seats in the corpus.
   **P5′ is confirmed in fabric by seats that were registered in advance and did
   not need `fz2e/527051`.**

### 4.3b ⚠ **THE RULE THIS DOCUMENT FIRST DREW IS REFUTED BY THIS SITTING'S OWN SEATS, AND IS WITHDRAWN**

The obvious rule to draw from §4.3a is *"an escaped seed (`escaped_n > 0`,
`ob_escape.frac == 1.0`) may not be pre-registered as a seat."*  **It was drawn,
it was checked against this sitting's own eight seats before it was published,
and it is REFUTED: SEVEN OF THE EIGHT SEATS ARE IN THAT CLASS.**

| seat | `escaped_n` (F16) | `ob_escape.frac` | in the proposed class? |
|---|---:|---|---|
| `fz2e/519016` | 2 | 1.0 | **yes** |
| `fz2e/520040` | **0** | 1.0 | no |
| `fz2e/520062` | 4 | 1.0 | **yes** |
| `fz2e/528008` | 54 | 1.0 | **yes** |
| `fz2e/532012` | 14 | 1.0 | **yes** |
| `fz2e/533028` | 34 | 1.0 | **yes** |
| `fz2e/527055` | 14 | 1.0 | **yes** |
| `fz2e/528030` | 32 | 1.0 | **yes** |

A filter that would have thrown away seven of the eight seats that then closed
**exactly as predicted, on the first fabric era that could test them**, is not a
filter — and the escaped population is **1,112 of 3,840 seeds**, so the rule
would have amputated 29 % of the corpus from seat-level work.  **WITHDRAWN.**

**WHAT IS ACTUALLY MEASURED, AND IT IS SHARPER.**  Over the 1,112 seeds escaped
in either era, F16 → F17:

    escape target ( `escaped` = [instruction, target] ) MOVED :    3 / 1,112  = 0.27 %
    ledger membership FLIPPED                                 :   13 / 1,112
    BOTH                                                      :    1

and **all three escape-target movers are exactly the three seeds whose
DISPOSITION changed** — there are no others:

| seed | `escaped` F16 → F17 | what moved | CORE dump |
|---|---|---|---|
| `fz2e/527051` | `[157, 24326]` → `[157, **32518**]` | **ledger FAIL/PASS** (§4.3a) | **IDENTICAL** |
| `fz2e/524066` | `[732, 7377]` → **None** | **ENTERED the discard set** (§3.1) | **IDENTICAL** |
| `fz2e/535075` | `[2638, 58612]` → **None** | **LEFT the discard set** (§3.1) | **IDENTICAL** |

**Escape-target movement is SUFFICIENT (3 of 3) but NOT NECESSARY (1 of 13) for
a disposition change**, and on all three the CORE leg is bit-identical, so all
three are socket-side.  **It is a post-hoc integrity flag, not a
pre-registration filter** — a single era cannot say whether a seed's escape
target will move next time, which is exactly the question the noise document's
registered double-capture answers.

*Booked, with its falsifier*: **`escaped` movement between eras is a 3-in-1,112
event and every instance so far changed a disposition.**  Cheap to check on any
seat-level claim, and it should be checked.  *Falsifier*: an era pair in which a
seed's escape target moves and its disposition does not.

**What is withdrawn from FLASH #16 remains withdrawn** (§4.3a): `fz2e/527051`
was quoted as a seat-level confirmation of P5′ and its bus is not reproducible.
What defeats it is **not** that it escaped — so did seven of this sitting's
eight — but that **its escape target moved**, and that could only be seen by
capturing it twice.

### 4.4 **P-4 — ONE UNREGISTERED CLOSURE.  MISSED, AND IT IS FLASH #16's OWN ARTIFACT CORRECTING ITSELF.**

    exits 9   registered 8   unregistered 1   MISSED

**`fz2e/513017`** (soup, `enr/soup/stim/wrand1`) left the ledger.  This is the
seed FLASH #16 §5.4 itemised as **a proven one-off socket-capture artifact**,
where five fresh captures on that same bitstream reproduced the GOOD FLASH #15
answer 5/5 and *"the F16 banked row is the anomaly"*.  Its F16 → F17 movement is
that diagnosis, measured in a fresh era:

| | FLASH #16 banked | **FLASH #17** |
|---|---|---|
| verdict / sub | `FUNCTIONAL / func:W@45` | **`SUCCESS / clean`** |
| `bad_rows` / `first_bad` | 502 / 695 | **0 / none** |
| terminator `fired` | **0** | **5** |
| `vec_used` | False | **True** |
| `arch_match` | False | **True** |
| CORE dump | *(reference)* | **BIT-IDENTICAL** |

**The terminator misfired at FLASH #16 — `fired` 0 where every sibling reads 4
or 5 — and it fires normally here.**  The CORE is bit-identical across the
change.  This is **not** an unregistered core closure; it is the socket-noise
population resolving, and F16 §5.4's registered diagnosis is **confirmed on
fresh silicon**.  It is nonetheless reported as a MISS of P-4 because P-4 said
*exactly the eight*, and it was nine.

**Total unregistered membership flips (6 entries + 1 unregistered exit) = 7,
against the registered budget of 10 — MET.**

### 4.5 **P-5 — THE FALSIFIER: `fz2c/404040` IS ABSENT.  MET.**

The branch's sharpest falsifier did not fire.  Wave 4 broke no mechanism nobody
claimed.

### 4.6 **P-6 — THE FIRST-DIVERGENCE BAR: 19 / 19 REGISTERED MOVERS HIT EXACTLY, 0 UNREGISTERED DECREASES.  MET.**

All nineteen seeds named in advance as moving EARLIER moved earlier, and **every
one landed on its predicted row to the row**:

    406063 249->245 · 408068 432->426 · 409065 1544->1534 · 518039 2371->2363
    518053 571->567 · 520000 642->502 · 520005 491->484 · 521016 362->352
    521049 2168->2150 · 525017 1167->1141 · 526054 279->265 · 527008 938->929
    530017 1448->1440 · 530020 304->296 · 530046 1402->1345 · 530070 2233->2225
    532000 434->426 · 534062 1291->1271 · 535004 1138->1131

**UNREGISTERED first-divergence decreases: 0.**  This is the clause the
ghost-address landing's `W-4` bar was refuted on; naming the nineteen in advance
rather than re-registering a bar known to fail is what made it scoreable, and it
scored perfectly.

### 4.7 **P-7 — THE FAMILY TABLE: TWO CLAUSES MISSED, BOTH THE SAME SIX SEEDS**

| ledger family | F16 | predicted | **F17** | verdict |
|---|---:|---:|---:|---|
| D3 both fetched, different address | 8 | **4** | **5** | **MISSED** — `fz2e/527051` re-entered (§4.3a) |
| E1 same-status data cycle, different address | 41 | **39** | **39** | **MET** |
| E2 different-status data cycle | 4 | **2** | **2** | **MET** |
| NEW/UNCLASSIFIED | 3 | (unchanged) | **7** | **MISSED** — the five other escaped entrants minus `fz2e/513017`'s exit |
| all eleven others | | (unchanged) | **unchanged** | **MET** |
| **total** | **116** | **108** | **113** | |

**Both misses are the §4.3 escaped-seed population and neither is a wave-4
effect.**  D3 would read **4 exactly** — the registered value — if `fz2e/527051`
were excluded, and §4.3a argues it should never have been in a scored
population; **that exclusion is proposed for the NEXT sitting and is NOT applied
retroactively here**, because choosing an exclusion after seeing the result is
what the campaign's own rules forbid.  **The number that stands is 5.**

### 4.8 **P-8 — THE THREE BOOKED NON-CLOSING SEATS ALL STAYED FAILING.  MET 3 / 3.**

| seat | rows F16 → F17 (pred) | `first_bad` F16 → F17 (pred) | verdict |
|---|---|---|---|
| `fz2e/520066` | 8 → **8** (8) | 1249 → **1249** (1249) | **MET — UNMOVED, exactly as booked** |
| `fz2c/410028` | 433 → **429** (426) | 2994 → **3004** (3004) | **MET** |
| `fz2c/410008` | 4 → **4** (4) | 1192 → **1198** (1198) | **MET** |

Each landing's own booked reason survives contact with silicon: the latched
`r_cmt_bs` announcement, the `qs`-pop re-fork ten rows later, and the ghost row
being fixed while the seed is not.

---

## 5. THE OFFLINE INSTRUMENT'S FIDELITY — THE STRONGEST COLUMN THIS CAMPAIGN HAS TAKEN

### 5.1 **Q-1 — THE FABRIC ERA GUARD PASSES WITHOUT THE BYPASS.  MET.**

    its inputs  88/88 hash IDENTICAL in the tree at HEAD
    FABRIC ERA GUARD: PASS

**88 of 88**, not 87 of 88 — even `hdl/nec_test_ucore.qsf`, the standing §70.7
exemption, matches, because E-8 regenerated and re-checked it after the draw.
**Every wave-4 figure quoted before this sitting carried `--no-fabric-era-guard`
and said so; from FLASH #17 onward the bypass is not needed and is not used.**

### 5.2 **Q-2 — THE CLOSING CONTROL: 263 / 263 = 100.0 %, `first_bad` IDENTICAL ON 113 / 113**

`fz2_replay --ledger <F17> --all-failures --pass-sample 150 --leg ret`, **era
guard ON, no override**, `tb_sys` receipt `251ded16c34b4212…`, 21 s, 0 errors:

    fabric PASS  150   replay PASS 150   replay FAIL   0
    fabric FAIL  113   replay PASS   0   replay FAIL 113
    AGREEMENT 263 / 263 = 100.0 %      first_bad IDENTICAL on 113 / 113

Registered bar was **≥ 260 / 266**; the population is 263 because retention is
divergence-driven and eight seats closed.  **MET in the strongest available
form**, 100 % on every wait mode (fixed 102/102, wrand 102/102, wvec 59/59) and
on the stimulus-event split (117/117 and 146/146).

### 5.3 **THE PREDICTION-VS-SILICON TABLE — `first_bad_row` EXACT ON 43 OF 43**

The pre-registration's Appendix A named 43 still-failing seeds with a predicted
`diverging_rows` **and** a predicted `first_bad_row` for each, from an offline
replay taken before the board was touched.  Measured against silicon:

| | |
|---|---|
| **`first_bad_row` EXACT** | **43 / 43** |
| `diverging_rows` EXACT | **18 / 43** |
| `diverging_rows` within 8 rows | 24 / 43 |
| `diverging_rows` off by more | **1 / 43** — `fz2e/510043`, 2,238 predicted vs 2,259 measured (+21) |
| exited unexpectedly | **0 / 43** |

**Every one of the 24 "near" rows is a POSITIVE offset of 1–5 rows** — the
offline replay systematically predicts one to five fewer diverging rows than
silicon on long-tail seeds, and never the other way.  That is a one-sided
residue with a shape, it is **reported and NOT explained**, and it is the
cheapest open instrument question this sitting leaves behind.  It is **not** a
bar and was never registered as one.

---

## 6. THE STANDING GATES, RE-MEASURED ON THIS ERA

| gate | result |
|---|---|
| `fz2_w1 bars` | **11 / 11 MET** — C-1 … C-11, on the F17 corpus |
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_ledger --control --suffix=-F13-archive` | **PASS 9 / 9** — failure SET identical 198/198 symdiff empty, denominator 3,837, matched 3,639, 3 discards, 14 family counts identical, `first_bad_row` 198/198, `diverging_rows` 198/198, arch 196/198 (the two known residuals), overlay 40.  **The derivation is quotable.** |
| `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| `gen_ucore_qsf --check` | **PASS** |
| `r7_lint` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / **0 violations** |
| `ss_lint --core ucore` | **PASS** — 103 BIU + 122 EU = **226**, **214 flops, 0 UNMAPPED** |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| §38.9 missed-trap overlay | **4** (F16: 4) |

⚠ **`fz2_ledger --control` TAKES `--suffix` AND ITS REFERENCE IS THE FLASH #13
ARCHIVE, NOT "THE PREVIOUS ERA".**  Invoked as `--suffix=-F16-archive` it
re-derives the F16 corpus and scores it against F13's frozen constants, which
reads **FAIL 0/9** and looks like a catastrophic instrument failure.  That
mis-invocation happened in this sitting and is recorded so the next one does not
repeat it: the control is **`--suffix=-F13-archive`**.

**`fz2_ledger.CURRENT` was moved from FLASH #15 to FLASH #17** (registered action
Q-5).  It had been two eras stale and was booked at w4-ghost §6; every
invocation in this sitting passed `--ledger` explicitly before the move.

---

## 7. HARD STOPS — NONE FIRED

`safe_flash` VERIFY ok try 1 · 0 `div_guard` UNPINNED across 61 probes ·
0 `RigMismatch` · 0 quarantines · every capture-integrity bar (G-1 … G-5) met ·
first light MATCH 800 ×3 · E-6 read RETENTION · `use_core = 0` chip proof MATCH
800 after everything · `board_idle()` clean · no contradiction inside the
pre-registration.

**The registered non-stops, reported with their denominators**: the G-6 discard
re-roll (§3.1), the P-4 unregistered exit (§4.4), the two P-7 family misses
(§4.7), and the §1.1 soft Fmax expectation missing high.

---

## 8. WHAT THIS SITTING ESTABLISHED, AND WHAT IT LEAVES OPEN

**ESTABLISHED**

1. **Wave 4 is confirmed in silicon, 8 seats of 8**, on a bitstream built from
   the merged tree, scored against a pre-registration committed before the
   build, by a scorer committed before the flash and proved non-vacuous on the
   null.  **P5′-stall closes all four of its stall seats in fabric**, including
   the two highest-signal seats in the corpus.
2. **A named-seat prediction is the right instrument at this effect size, and it
   worked.**  The headline moved 116 → 113 where the landing is worth 8; the
   aggregate is unreadable at the floor and the seats are not.  This is the
   noise document's own prescription, executed and vindicated.
3. **The offline `tb_sys` replay predicted every still-failing seed's first
   divergence row EXACTLY — 43 / 43 — and agrees with fabric 263/263 on the
   fresh era.**  The instrument the campaign's attributions rest on is faithful.
4. **FLASH #16 §5.4's socket-artifact diagnosis is confirmed on fresh silicon**
   (`fz2e/513017`, terminator `fired` 0 → 5).

**OPEN, WITH THEIR FALSIFIERS**

1. ⚠ **THE ESCAPE-TARGET FLAG** (§4.3b).  The tempting rule — *escaped seeds may
   not be seats* — was drawn, checked against this sitting's own eight, and
   **REFUTED: seven of the eight are escaped**, and the class is 1,112 of 3,840.
   What is measured instead: **`escaped` target movement is 3 / 1,112 and all
   three movers changed a disposition** (one ledger flip, two discard-set
   moves), CORE bit-identical on all three.  A post-hoc integrity flag, not a
   pre-registration filter.  *Falsifier*: an era pair in which a seed's escape
   target moves and its disposition does not.  **The prospective question — can
   a seed's instability be known from ONE era? — is still open, and the noise
   document's registered double-capture on one bitstream is still the way to
   answer it.**
2. **The +1..+5 one-sided row residue** (§5.3): 24 of 43 predicted seeds
   under-count diverging rows by 1–5 and none over-counts.  One mechanism, one
   look, no code.
3. **The discard set has re-rolled on three consecutive flashes** (2 → 2 → 3,
   with five distinct seeds involved).  `_ps3_8080` is socket-leg; the
   population is escaped/non-reproducing.  *Falsifier*: a double-capture in
   which `ps3_8080` is stable seed for seed.
4. **`fz2e/520066`'s LATCHED `r_cmt_bs`** and **`fz2c/410028`'s `qs`-pop
   re-fork** are the two named remainders of package B, unmoved and unclaimed.
5. **The retention/control Fmax sign inverted a fifth time, and this time Fmax
   and worst setup disagreed in sign with each other** (§1.1).  Recorded, not
   explained; `standing_gates.md` §A governs.
