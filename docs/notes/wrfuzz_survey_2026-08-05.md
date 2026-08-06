# THE wrfuzz SURVEY — W2, 2026-08-05

**THIS DOCUMENT IS THE CAMPAIGN'S MEASUREMENT OF ITSELF.**  One corpus
(`cid = wr1`, 3,150 seeds, captured at W1 on FLASH #10), one tree
(`b8020d0229`), one instrument set, both engines, **and the victory bar's
number computed and FROZEN in it.**

**NOTHING WAS FIXED, LANDED OR PROPOSED WHILE TAKING IT.**  `git diff` over
`hdl/` and `sim/` is empty for the whole sitting.  **No board was contacted.**

Plan: `wrfuzz_campaign_plan.md`.  Pre-registration:
`wrfuzz_corpus_prereg_2026-08-05.md` (§7 is this document's shape).  Ledger:
`wrfuzz_provenance.md` §3.  Style and inherited dispositions:
`sm3_s27_residue_census_2026-08-05.md`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

---

## §0 THE HEADLINE

| | |
|---|---|
| corpus | **3,150** seeds, 28 strata, all captured (W1, `9/9` bars MET) |
| excluded — **OPEN_BUS**, the pre-registered detector | **635** (all raw tier) |
| **SCORED** | **2,515** |
| **cycle-exact, the `ucore` IN FABRIC against the socketed chip** | **2,379 (94.59 % pooled)** |
| **residue** | **136 seeds** |
| **`S` — the unweighted mean of the 28 per-stratum rates** | **91.6681 %  — FROZEN** |
| **`B = S − 5.0`** | **86.6681 %  — FROZEN** |
| the axis falsifier (plan §5) | **NOT triggered** — six stratum pairs are distinguishable.  ⚠ **Every one of them has the vector stratum scoring HIGHER.**  §6 |
| ⚠ **THE ONE THING THE RESIDUE IS MOSTLY MADE OF** | **the single-step (TF) trap's entry.  75 of the 136 scored misses — 55 % — carry the `has_tf` axis, which is 89 of 2,515 scored seeds (3.5 %).**  §4 |
| the `ucore`-only residue (model exact, both `ucore` legs not) | **5 seeds**, all family `PIN`, **no bus cycle moved in any of them**.  §5 |
| INTA rows in the corpus (plan §4's registered **risk #4**) | **0 over 380 retained captures.**  The §56 fabric-float class does **not** reach this corpus |
| 8080 class-A landings (§63.5's criterion) | **12 of 136**, all raw tier — **on a corpus with 0 `0F FF` pairs in 3,150 images.**  §7 |

**THE NUMBER THE CAMPAIGN NOW TURNS ON IS 75.**  Not a law about arbitration,
not a fitted table: **one trap, one vector fetch, one address.**  In 64 of the
135 classified seeds the two sides' contested bus slot is the chip (or the
engine) reading **`MEMR 00004` — interrupt vector 1, the single-step vector** —
while the other side is still prefetching.  61 of those 64 carry `has_tf`.
Seeds with the axis fail at **84.3 %**; seeds without it fail at **2.51 %**.

**With the TF axis removed, thirteen of the fourteen soup strata are 98.6 % to
100.0 % and the soup residue is SEVEN seeds.**  `S(TF-free)` would be
**93.4461 %** — computed and reported here as a *characterisation*, **not** as
the bar; `B` is derived from `S`, and `S` is the whole scored corpus.

---

## §1 THE PER-STRATUM TABLE — HARDWARE VERSUS SILICON, ALL 3,150

The comparator is the campaign's own and the only one defined over the whole
corpus: **the `ucore` in fabric (`use_core=1`) against the socketed chip
(`use_core=0`)** — same image, same 4,096-entry vector, same bitstream
(FLASH #10 `1a01a6975e4a…`), differing in the A/B select and in nothing else.
It was computed inline by `fuzz_campaign.capture_board` **at capture time**;
this survey reads it and never recomputes it.

`rate` is cycle-exact seeds over scored seeds.  `FUNC` / `TIM` / `KACC` are the
scored misses by verdict class.

| i | tier | source | n | OPEN | scored | exact | rate % | FUNC | TIM | KACC |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | soup | `fix0` | 150 | 0 | 150 | 143 | **95.33** | 7 | 0 | 0 |
| 1 | soup | `fix1` | 150 | 0 | 150 | 145 | **96.67** | 5 | 0 | 0 |
| 2 | soup | `fix2` | 150 | 0 | 150 | 143 | **95.33** | 7 | 0 | 0 |
| 3 | soup | `fix3` | 150 | 0 | 150 | 143 | **95.33** | 6 | 0 | 1 |
| 4 | soup | `wrand1` | 150 | 0 | 150 | 146 | **97.33** | 3 | 1 | 0 |
| 5 | soup | `wrand2` | 150 | 0 | 150 | 141 | **94.00** | 9 | 0 | 0 |
| 6 | soup | `wrand3` | 150 | 0 | 150 | 144 | **96.00** | 6 | 0 | 0 |
| 7 | soup | `wrand7` | 150 | 0 | 150 | 143 | **95.33** | 7 | 0 | 0 |
| 8 | soup | `wrand15` | 150 | 0 | 150 | 144 | **96.00** | 6 | 0 | 0 |
| 9 | soup | **`wvec-uni`** | 150 | 0 | 150 | 147 | **98.00** | 3 | 0 | 0 |
| 10 | soup | **`wvec-walk`** | 150 | 0 | 150 | 138 | **92.00** | 12 | 0 | 0 |
| 11 | soup | **`wvec-skew`** | 150 | 0 | 150 | 148 | **98.67** | 1 | 1 | 0 |
| 12 | soup | **`wvec-burst`** | 150 | 0 | 150 | 143 | **95.33** | 6 | 0 | 1 |
| 13 | soup | **`wvec-edge`** | 150 | 0 | 150 | 150 | **100.00** | 0 | 0 | 0 |
| 14 | raw | `fix0` | 75 | 43 | 32 | 26 | **81.25** | 6 | 0 | 0 |
| 15 | raw | `fix1` | 75 | 39 | 36 | 29 | **80.56** | 6 | 1 | 0 |
| 16 | raw | `fix2` | 75 | 49 | 26 | 24 | **92.31** | 2 | 0 | 0 |
| 17 | raw | `fix3` | 75 | 46 | 29 | 25 | **86.21** | 3 | 0 | 1 |
| 18 | raw | `wrand1` | 75 | 50 | 25 | 17 | **68.00** | 7 | 0 | 1 |
| 19 | raw | `wrand2` | 75 | 43 | 32 | 28 | **87.50** | 4 | 0 | 0 |
| 20 | raw | `wrand3` | 75 | 38 | 37 | 29 | **78.38** | 7 | 0 | 1 |
| 21 | raw | `wrand7` | 75 | 45 | 30 | 28 | **93.33** | 2 | 0 | 0 |
| 22 | raw | `wrand15` | 75 | 45 | 30 | 28 | **93.33** | 2 | 0 | 0 |
| 23 | raw | **`wvec-uni`** | 75 | 49 | 26 | 25 | **96.15** | 1 | 0 | 0 |
| 24 | raw | **`wvec-walk`** | 75 | 47 | 28 | 25 | **89.29** | 2 | 1 | 0 |
| 25 | raw | **`wvec-skew`** | 75 | 44 | 31 | 27 | **87.10** | 3 | 0 | 1 |
| 26 | raw | **`wvec-burst`** | 75 | 52 | 23 | 21 | **91.30** | 2 | 0 | 0 |
| 27 | raw | **`wvec-edge`** | 75 | 45 | 30 | 29 | **96.67** | 1 | 0 | 0 |
| | | | **3,150** | **635** | **2,515** | **2,379** | **94.59 pooled** | 126 | 4 | 6 |

### §1.1 ⚠ THE EXCLUSION, AND WHY IT IS NOT THE BANK'S OWN LABEL

The pre-registration (§2.4) names **`fuzz_classify._open_bus_escaped_before`**
as the OPEN_BUS detector — *did the chip make ≥ 8 out-of-image CODE fetches
reading pure address feedthrough*.  That function needs the chip's ROWS, and
W1 retained rows for **380** of 3,150 captures.  It is nonetheless computable
on every seed, because the capture path banks
`fuzz_accept.open_bus_escape_metrics`' own counters in each record
(`ob_escape = {feed, out, frac}`, present on all 1,050 raw lines, absent on all
2,100 soup lines) and `feed` **is** that function's counter.

**MEASURED, not assumed.**  Over the 260 retained raw captures the predicate
`feed ≥ 8` and the row-level detector agree on **259 / 260**; the one exception
is a seed whose done-shrunk window is shorter than the window the metric was
taken over.  Over the 120 retained soup captures the row detector fires **0
times**, and no soup line carries the field at all.

**AND HERE IS WHY THE BANK's `KNOWN_ACCEPTED/open_bus` LABEL IS NOT USED.**
That label is an accept-engine rule hit, and `fuzz_classify.classify` consults
the accept engine **only inside the two branches a divergence reaches** — so
**a SUCCESS seed can never carry it, by construction of the decision tree.**
Excluding on it removes open-bus MISSES and keeps open-bus EXACTS, i.e. an
exclusion whose membership depends on the answer.  That is precisely the shape
§2.4 and §3.3 forbid.  Both are reported here so the choice is visible:

| exclusion | scored | exact | pooled | **S** |
|---|---|---|---|---|
| **the registered detector (`ob_escape.feed ≥ 8`)** — **USED** | 2,515 | 2,379 | 94.59 % | **91.6681 %** |
| the bank's `KNOWN_ACCEPTED/open_bus` label — *not used* | 2,966 | 2,830 | 95.41 % | 94.9107 % |
| no exclusion at all (the floor) | 3,150 | 2,830 | 89.84 % | 86.7143 % |

The registered detector is the one applied, and it is **1.7 points lower** than
the convenient alternative.  It excludes **451 exact seeds and 184 misses**.

### §1.2 ⚠ AND A RETENTION FINDING, BOOKED

W1 retained rows for the divergent seeds plus a SUCCESS ballast (ledger §2.5).
That is exactly sufficient for the family census (**every non-exact seed's rows
are on disk — 320 of 320**) and it is **not** sufficient to evaluate the
registered row-level detector, or any other row predicate, on the 2,770
non-retained seeds.  The `ob_escape` counters rescued it this time because the
capture path happened to bank them.  **Booked for W3**: either retain all rows,
or bank the row predicates the survey will need at capture time.  Nothing is
changed here.

---

## §2 THE OFFLINE LEGS — ATTRIBUTION ONLY, AND THEIR INFORMATION CONDITIONS

The EVT quoting rule generalises: **state what each engine was told.**

| leg | what it is told | population |
|---|---|---|
| **HW-vs-SILICON** | nothing.  The `ucore` in fabric runs the same image under the same vector and the pins are compared | **all 3,150** |
| **chip-vs-model** | the same image, the same 4,096-entry vector (decimal encoding), replayed from reset offline | the **380 retained captures** |
| **chip-vs-`ucore`-TB** | the same, in the Verilator TB (hex encoding) | the same 380 |

⚠ **THE 380 IS DIVERGENT BY CONSTRUCTION** — 320 misses plus 60 ballast — so
**no rate taken on it is a population rate and none is quoted as one.**  Under
the offline row-level OPEN_BUS excuse, 184 of the 380 are scored:

| leg | cycle-exact on the retained-and-scored 184 |
|---|---|
| the C++ timed model | **48 / 184** |
| the `ucore` in the Verilator TB | **49 / 184** |

These two numbers are what the **attribution** below is computed from and they
are **not** a silicon-match figure for either engine.

### §2.1 THE INSTRUMENT AGREEMENT — FABRIC VERSUS THE TB, MEASURED

**182 / 184.**  On the same RTL, the `ucore` in fabric and the `ucore` in
`tb_v30_core` reach the same exact/non-exact verdict on 182 of the 184 scored
retained seeds, **and their family census is identical family for family,
delta for delta and signature for signature** (§3).  The two disagreements are
`wr1/217022` (the bank's tier-B fixed window versus `window_of`'s done-shrunk
one) and `wr1/223067` (the one seed where the two OPEN_BUS detectors part).

**This does not retire §56.**  §56's fabric-versus-TB gap is the **INTA float
class**, and this corpus is evt-free: **INTA rows measured 0 over 380 retained
captures**, so the class has no members here.  Plan §4's registered **risk #4
is answered by measurement and it is a negative** — the class does not reach
this corpus.  The scorer was chosen before the number was seen and is not
swapped.

### §2.2 THE CROSS-ENGINE PARTITION

Over the 184 retained-and-scored seeds:

| | count |
|---|---|
| diverging in **both** engines (model-shared) — routed `sim/` first | **130** |
| **`ucore`-only** (the model is exact) | **5** |
| **model-only** (both `ucore` legs exact) — **FROZEN by user decision** | **≥ 6** |

⚠ **THE `ucore`-ONLY COLUMN IS COMPLETE AND THE MODEL-ONLY COLUMN IS NOT.**
Every seed on which the fabric `ucore` diverged has its rows retained, so no
`ucore`-only seed can be hiding among the 2,770; a **model**-only seed on a
capture the fabric got exact and W1 did not retain is invisible, so **6 is a
floor and no upper bound is computed**.  Stated rather than left to be read
off a table.

---

## §3 THE FAMILY CENSUS — `s15_census`'s TAXONOMY, ENGINE MATCHED TO THE REPORT

Three censuses, all with `--core` matched to their report (gap R4).  The
**fabric** census is the campaign's own comparator and is the headline; it runs
`s15_census.classify` — the tool's own classifier, imported and not forked —
over the rows the board produced.

### §3.1 The `ucore` IN FABRIC — 136 scored misses, 135 classified

| family | n | first offending cycle, median | delta median | delta range |
|---|---|---|---|---|
| **`PF_LOST`** | **43** | #163 | +3 | −9 … +6 |
| **`SCHEDULE`** | **42** | #110 | −1 | −4 … +3 |
| **`DATA_SEQ`** | **23** | #123 | 0 | −2 … +4 |
| **`PF_GAINED`** | **18** | #195 | −6 | −6 … −4 |
| **`PIN`** | **7** | #0 | 0 | 0 |
| **`PF_ADDR`** | **2** | #97 | 0 | 0 |
| `TAIL_EXTRA` / `TAIL_MISS` | **0** | | | |
| **catch-all (unclassified by the taxonomy)** | **EMPTY** | | | |
| **total** | **135** | | | |

One seed of the 136 is **exact under `window_of`'s done-shrunk window** and
non-exact under the bank's tier-B fixed window; it is counted in the 136 and
carries no family.  The window policy difference is named, not smoothed.

### §3.2 The `ucore` in the Verilator TB — 135 diverging

`PF_LOST` **43** · `SCHEDULE` **42** · `DATA_SEQ` **23** · `PF_GAINED` **18** ·
`PIN` **7** · `PF_ADDR` **2**.  **Identical to §3.1 in every cell**, and
identical in the delta tables, the recovery tables and the signature tables.

### §3.3 The C++ timed model — 136 diverging

`SCHEDULE` **50** · `PF_LOST` **49** · `DATA_SEQ` **17** · `PF_GAINED` **15** ·
`PIN` **3** · `PF_ADDR` **2**.  Catch-all EMPTY.  Its population is its own
divergence set, not the fabric's; the two overlap on 130 seeds (§2.2).

### §3.4 Family × stratum group

| group | `DATA_SEQ` | `PF_ADDR` | `PF_GAINED` | `PF_LOST` | `PIN` | `SCHEDULE` | total |
|---|---|---|---|---|---|---|---|
| soup / control | 5 | 0 | 11 | 25 | 4 | 13 | **58** |
| soup / `wvec` | 5 | 0 | 7 | 7 | 1 | 4 | **24** |
| raw / control | 11 | 1 | 0 | 9 | 1 | 20 | **42** |
| raw / `wvec` | 2 | 1 | 0 | 2 | 1 | 5 | **11** |

`PF_GAINED` is **soup only, 18 of 18**.  `SCHEDULE` is **raw-weighted**
(25 of 42).

---

## §4 ⚠ THE INVARIANT THAT SHAPES W3 — THE SINGLE-STEP TRAP'S ENTRY

### §4.1 The invariant, stated before the count

**`PF_GAINED` is 18 seeds and its first-divergence geometry is IDENTICAL on all
eighteen:**

| what | value | n |
|---|---|---|
| first-divergence signature | `bs PASV!=CODE` | **18 / 18** |
| the chip's cell at the contested slot | **`MEMR 00004`** | **18 / 18** |
| the engine's cell at the same slot | `CODE 005xx` (the handler pad) | **18 / 18** |
| the enclosing chip cycle | `IDLE`, offset **+1** | **18 / 18** |
| `delta` (engine T1 − chip T1) | **−6 (10) · −5 (3) · −4 (5)** | 18 / 18 |
| recovery | `EXTRA`, and the odd cycle is exactly **one `CODE`** | **16 / 18** |
| tier | soup | **18 / 18** |
| the banked `has_tf` axis | **True** | **18 / 18** |

**`0x00004` is interrupt vector 1 — the single-step / BRK vector.**  The chip
takes the trap and reads its vector; the engine takes one more prefetch first.

**`PF_LOST` carries the SAME event with the owners swapped**: in **30 of its
43** the *engine's* cell is `MEMR 00004` while the chip prefetches, at
`delta ∈ {0, +2 … +6}`.  Across the whole classified residue, **64 of 135
seeds** have `MEMR 00004` at the contested slot, and **61 of those 64** carry
`has_tf`.

### §4.2 What it is worth, in numbers

`has_tf` is a **generator axis** (`p_tf = 0.002` per instruction, soup only).

| population | scored | misses | rate |
|---|---|---|---|
| seeds carrying `has_tf` | **89** | **75** | **84.3 %** |
| seeds not carrying it | 2,426 | 61 | **2.51 %** |
| odds ratio | | | **208** |

**75 of the 136 scored misses (55 %) come from 3.5 % of the corpus.**

Removing the axis, the per-stratum rates become:

* **soup**: thirteen of fourteen strata at **98.6 – 100.0 %**; the entire soup
  non-TF residue is **7 seeds**, five of which are §5's `ucore`-only `PIN`
  family.
* **raw**: unchanged (**no raw seed carries `has_tf`** — it is a soup knob), so
  the raw residue of **54 seeds** is a second, separate thing.
* `S(TF-free)` = **93.4461 %**.  *Characterisation only.  The bar is `S`.*

### §4.3 KNOWN SIGNATURE, NEW EXPOSURE — and the exposure is that the corpus is UNBIASED

**The signature is already in the banked corpus** and was never the headline
there: re-censused this sitting, **8 of the old bank's 145 registered `ucore`
residue seeds** carry `MEMR 00004` at the contested slot, and **both** of that
bank's two `PF_GAINED` members are this exact shape
(`mc1/980` `MEMR 00004` → `CODE 0051e`, delta −5; `mc2/3061` → `CODE 00530`,
delta 0).

So this is **not a new mechanism.**  What is new is the population: the banked
corpus is **promotion-selected** (caps of 10 per timing signature, 50 per rule
class, 1-in-50 cadence), and `wr1` is the first **unbiased, whole-stratum**
capture.  The family that was 2 seeds under selection is 18 under a census.

The settled ledger's nearest law is **partition B1 — the BRK/TF trap — which is
LANDED** (§84 / §86) and whose directed floor cell is **EXACT: 121,860 rows,
0 row-diffs, on all 30 captures at depth 4, and non-zero at every other depth
in [1,7]**.  **This survey does not contradict that.**  The floor cell measures
*the recognition depth*; these 75 seeds are the trap's *entry sequence
interleaved with a running prefetcher*, which the directed walk does not
exercise.

### §4.4 IT IS NOT A PURE WAIT-AXIS EFFECT — measured, and it cuts against the obvious reading

| soup stratum | TF seeds exact / total |
|---|---|
| `fix0` | **1 / 7** |
| `fix1` | 1 / 6 |
| `fix2` | 2 / 9 |
| `fix3` | 1 / 7 |
| `wrand1` | 1 / 5 |
| `wrand2` | 0 / 8 |
| `wrand3` | 1 / 7 |
| `wrand7` | 0 / 5 |
| `wrand15` | **0 / 6** |
| `wvec-uni` | 1 / 3 |
| `wvec-walk` | **0 / 11** |
| `wvec-skew` | 1 / 3 |
| `wvec-burst` | 0 / 7 |
| **`wvec-edge`** | **5 / 5** |

**At `fix0` — no waits at all — the TF seeds already fail 6 of 7.**  The wait
axis is not what creates the divergence.

### §4.5 ⚠ `wvec-edge` IS 5 / 5, AND ITS LENGTH CONFOUND HAS A MATCHED CONTROL INSIDE THE CORPUS

Every other soup stratum scores **9 exact of 84** TF seeds (10.7 %);
`wvec-edge` scores **5 of 5**.  Under that rate, `P(5 of 5) = 1.4 × 10⁻⁵`.

**The obvious objection is program length**, and the pre-registration named the
coupling in advance (§2.1: `nmax_eff` is a function of the effective wait
level).  `wvec-edge`'s TF seeds run `n_ins = 24-26` and 144-204 bus cycles;
`wvec-walk`'s run 27-54 and 452-762.  A shorter program has fewer chances to
reach its trap.

**The corpus contains its own matched control and it survives it.**
`soup/wrand15` has the **same** median `n_ins` (**24**), the **same**
`nmax_eff` (**24**) and the **same** median bus-cycle count (**146** vs 145) —
and its TF seeds are **0 / 6**.  Fisher on 5/5 versus 0/6 is **p = 0.0022**.

**The one thing that separates them** is the wait DISTRIBUTION at equal mean
cost: `wrand15` draws i.i.d. over 0…15, so most accesses take an
**intermediate** number of waits; `edge` draws i.i.d. over **{0, 1, 30, 31}**
and takes an intermediate number **never**.

> **HYPOTHESIS, NOT A LAW, and it is W3's first directed cell.**  The trap's
> entry contends with a prefetch, and the contention window is at
> *intermediate* access lengths: at ≤ 1 wait the fetch has already completed
> and at ≥ 30 it has not begun to matter.
> **Falsifier, registered here**: a `burst`-shaped vector has no intermediate
> values either (`wbase ∈ {0,1}`, `wbig ∈ {16,24,31}`) and its TF seeds are
> **0 / 7** — so if the hypothesis is right it must be because `burst`'s MEAN
> is low (`nmax_eff` 53, programs 2× longer) and not because intermediates are
> absent.  **A cell that holds program length fixed and sweeps only the
> presence of intermediate waits decides it.**  If that cell shows no effect,
> this reading is wrong and `wvec-edge`'s 5/5 is a 1-in-450 coincidence.

---

## §5 THE `ucore`-ONLY RESIDUE — FIVE SEEDS, ENUMERATED

**Definition, stated before the count**: a scored seed on which the `ucore`
diverges from silicon *in fabric and in the TB*, the **model does not**, over
the 184 retained-and-scored captures.

| seed | stratum | family | signature | row | `ndiff` / n | opcode in flight | `mc1/721` shape |
|---|---|---|---|---|---|---|---|
| `wr1/200127` | soup/`fix0` | `PIN` | `data` | 262 | **2** / 1,295 | `3a.m` | **yes** |
| `wr1/203092` | soup/`fix3` | `PIN` | `data` | 802 | **6** / 1,411 | `bf` | no |
| `wr1/205145` | soup/`wrand2` | `PIN` | `data` | 439 | **4** / 1,389 | `?` | **yes** |
| `wr1/207147` | soup/`wrand7` | `PIN` | `data` | 1,591 | **2** / 1,684 | `c6` | **yes** |
| `wr1/209095` | soup/`wvec-uni` | `PIN` | `ps 2!=6` | 404 | 113 / 1,212 | `39.r` | no |

**ALL FIVE ARE FAMILY `PIN`: the bus schedules are IDENTICAL over the window
and no cycle moved in any of them.**  Four part on the `data` lanes at the row
**immediately after a `MEMW` or `IOW` T1** (`MEMW+1` ×3, `IOW+1` ×1); the fifth
parts on `ps`.  Three of the five carry **`mc1/721`'s own signature** — a
`data` column parting with `ndiff ≤ 4` — which §86.G part C diagnosed as *both
writes land, in the wrong order*, whose fix is **SPECIFIED and deliberately NOT
TAKEN** (it moves the chain's discharge order; §87.B's B-5).

**This is the SM3 catch-all's counterpart in a fresh corpus, and it is the same
shape**: a handful of seeds, tiny diff streams, no bus cycle moved.

### §5.1 The `PIN` family entire, and the two `ps 2!=6` seeds

The fabric census's `PIN` family is **7** seeds: the five above plus
`wr1/215017` (raw/`fix1`, `data`, `MEMW+1`, `ndiff` 6) and `wr1/225009`
(raw/`wvec-skew`, `ps 2!=6`, `CODE+1`, `ndiff` **1**) — both model-shared, so
they are routed `sim/` first and are not in §5's column.

**`wr1/209095` and `wr1/225009` part on `ps`** (the `{md, ie, CS}` nibble) at
the row after a `CODE` T1.  **`n_halt = 0` on every seed in the census**, so
these are **not** the F51 HALT-display class.  No mechanism is proposed.

---

## §6 THE AXIS — WHAT THE FIVE NEW SHAPES BOUGHT

### §6.1 The registered falsifier (plan §5), applied as written

> *"If at W2 the five `wvec` strata's hardware-vs-silicon rates are **not
> distinguishable** from the five `wrand` strata's — no stratum pair differing
> by more than its combined 95 % interval — then the new axis has bought
> nothing the existing rig did not already buy."*

**The falsifier is NOT triggered.**  Six of the fifty pairs are distinguishable:

* **`soup/wvec-edge` (100.00 %) against all five soup `wrand` strata** — five
  pairs, every one outside its combined interval;
* `raw/wvec-uni` and `raw/wvec-edge` against `raw/wrand1`.

**⚠ AND THE SURVEY REPORTS ITS OWN NEGATIVE.**  In **every one of the six**
the `wvec` stratum scores **HIGHER**, not lower.  Pooled: soup `wvec`
**96.80 %** vs soup control **95.70 %** (Fisher p = 0.24); raw `wvec`
**92.03 %** vs raw control **84.48 %** (p = 0.031).

> **In plain terms: after 3,150 seeds, no vector shape has produced a
> divergence rate above the controls'.  The axis DISCRIMINATES — `edge` is
> measurably different from every `wrand` class — but so far it discriminates
> in the direction of AGREEMENT.**

That discrimination is not nothing: §4.5 is entirely a `wvec-edge` result, and
it is the survey's sharpest mechanism clue.  The shapes are also not
interchangeable with each other — `soup/wvec-walk` is the **worst** soup
stratum (92.00 %) and `soup/wvec-edge` the only perfect stratum in the corpus.

### §6.2 THE CONTROL-STRATA CROSS-CHECK — **THE CONTROLS CANNOT BE CHECKED AGAINST A REMEMBERED NUMBER, AND THAT IS THE ANSWER**

The nine control strata were meant to double as a reproduction of the known
wait-class columns.  **They do not reproduce them, and the reason is that no
comparable column exists.**  Both candidates fail as controls, by measurement:

1. **The promoted bank's per-wait-class column is a SELECTION artefact.**
   Re-measured this sitting (`timed_fuzz --core ucore --pop reg`, which
   reproduces its ratchet at **1,557 / 1,702** exactly): soup `fix1` **88/88**,
   `fix2` **99/99**, `fix3` **94/94**, `wrand1` **282/282**, `wrand2`
   **257/257**, `wrand7` **98/98** — **100.0 % on six of nine classes**, beside
   soup `fix0` at 65.8 %.  Those are not population rates; they are what
   `fuzz_bank.promote`'s caps left behind.
2. **The mc1 / mc2 campaigns' full populations are ERA-UNATTRIBUTABLE.**
   Their lines carry **no era stamp at all** -- `era` is absent on
   **21,203** lines (mc1 10,003 + mc2 10,000 + t30-raw 1,000 +
   t30-brkem 200); `wr1` is the first campaign with one, B-2's own gate.
   Their fabric leg was a different core on a bitstream
   nothing records.  For reference and not as a control, their soup w > 0
   inline rates run **16.7 – 42.3 %**; nothing is concluded from that
   comparison and no delta is computed from it.

> **So `wr1`'s nine control strata are the FIRST unbiased, era-stamped,
> per-wait-class population measurement of the resident era.**  The check the
> work order asked for returns a NEGATIVE, and the negative is the finding.
> The control that *does* work is the one the corpus design built in: the nine
> control strata against the five vector strata, same session, same bitstream,
> same generator, same sitting — §6.1.

### §6.3 The vector's own integrity, re-read at W2

* **B-4 re-run in passing**: all **3,150** images regenerate from `(cid, k, ov)`
  — **0 GEN_DRIFT, 0 REGEN_ERROR**.
* `timed_fuzz.banked_wvec()` raised on nothing across every offline leg
  (its sha256 and length limbs are on the scoring path, not in a separate tool).
* **B-5**: 0 captures at or beyond 4,096 bus cycles (W1 measured max 1,010).

---

## §7 THE COUNTS THE PRE-REGISTRATION ASKS FOR

| count | criterion | **measured** |
|---|---|---|
| **INTA rows** (plan §4 risk #4) | `bs_early == INTA` at a T1 inside the chip's window | **0 seeds, 0 rows, over 380 retained captures.**  The corpus is evt-free and INTA cycles do not arise from software interrupts here.  **The §56 fabric-float class has no members** |
| **8080 class-A** | §63.5 verbatim: the chip's cell at the first contested slot is `CODE 00484` **and** the chip's window contains `CODE:00008` | **12 of 136 scored misses (8.8 %)**, `k =` 214024, 214026, 214029, 214046, 214065, 218031, 218062, 219002, 220005, 220026, 220030, 226022 — **all raw tier**.  §7.1 |
| **`mc1/721` signature** | a `data` first-divergence with `ndiff ≤ 4` (§86.G part C) | **3 of 136** — `wr1/200127` (2), `wr1/205145` (4), `wr1/207147` (2).  All three are §5's `ucore`-only seeds |
| **`8F` mod-3 ghost** (§84.6) | the form in flight at the first divergence | **0.**  Two seeds carry an `8F` form (`8f/0.m`, `8f/3.m`) and **both are the memory form**; the mod-3 ghost's population in this residue is EMPTY.  ⚠ §7.2 |
| **B-5 overruns** | `bus_cycle_bound ≥ 4096` | **0** |
| **OPEN_BUS** | §1.1 | **635**, all raw |

### §7.1 THE CLASS-A COUNT IS A FINDING, AND IT IS ROUTED

**The corpus is BRKEM-FREE — B-6 measured 0 `0F FF` pairs over 3,150 composed
images — and it still lands in 8080 mode on 12 seeds.**  That is §3.3's warning
arriving as a measurement, and W0's F-2 from the other side: *a BRKEM-free
corpus is not an 8080-free corpus*, and §63.5's other 24 class-A seeds' entry
path is **still not established**.

Eight of the twelve are `PF_LOST` with the chip's cell at **`CODE 00484`** (the
IVT-pad handler whose `CF` there is the 8080 `RST 1`) and four are `SCHEDULE`.
As a share of the **residue** the class has shrunk hard — **8.8 %** here
against **41 %** (92 of 222) in the banked corpus — which is the BRKEM-free
mechanism working.  As an **absolute** it is 12 seeds that should not exist.

**DISPOSITION, CARRIED AND NOT RE-LITIGATED**: 8080 / BRKEM is **DEFERRED BY
USER DECISION** (2026-08-05).  The 12 are **counted, reported, and left in the
denominator** — they are not filtered, and `S` is computed with them in.
**ROUTED**: the open question is not 8080 emulation; it is *by what path a
BRKEM-free image enters 8080 mode*, and it is booked for W3 as a **generator**
question, not a core question.

### §7.2 ⚠ AND ONE INSTRUMENT FINDING OF THIS SITTING'S OWN

The first `8F`/mod-3 criterion written for this survey scanned the **composed
image** for the byte pair.  It reports **2,951 of 3,150 seeds** — because a
64 KB image with random fill contains the pair by chance almost always.  **The
criterion is VACUOUS and its number is not quoted anywhere as a population.**
It is recorded because the vacuous-instrument pattern is this project's most
repeated failure and a near miss is evidence about it; the count in §7 is the
execution-based one (the form in flight at the first divergence), and
`sw/wrfuzz_w2.py mod3` prints both with the byte scan labelled.

---

## §8 THE RANKED SITTING QUEUE FOR W3+

Each item is a family, its invariant, whether a settled law fits, and the cell
that decides it.

### **#1 — THE SINGLE-STEP TRAP'S ENTRY AGAINST A RUNNING PREFETCHER.  75 seeds, 55 % of the residue.**

*Invariant*: `MEMR 00004` at the contested slot on **64 of 135** classified
seeds; `PF_GAINED` **18/18** identical (signature, cell, enclosing cycle,
offset, tier, `has_tf`), `delta ∈ {−6,−5,−4}`, recovery a single extra `CODE`
on 16/18; `PF_LOST` carries **30** more with the owners swapped at
`delta ∈ {0,+2…+6}`.
*Settled law*: **partition B1, the BRK/TF trap — LANDED, and its floor cell is
EXACT at depth 4.**  This is **KNOWN LAW, NEW EXPOSURE**: the floor cell walks
the recognition depth and never interleaves the entry with a live prefetch.
*Decides it*: the BRK/TF floor cell re-run **with a prefetcher running** and
across the wait sweep, plus §4.5's intermediate-wait cell.
*Falsifier*: the divergence is present at `fix0` (**6 of 7**), so any account
that requires a wait state is already refuted.

### **#2 — THE RAW TIER's `SCHEDULE` RESIDUE.  25 seeds of the raw tier's 54, TF-free.**

*Invariant*: `delta` is **trimodal and small** — `+2` ×18, `−3` ×11, `−1` ×10,
and nothing else outside `{−4,−2,+3}`; the first offending cycle **follows an
`IDLE`** on 33 of 42 at offset +1 or +3; **21 of 42** carry the single
signature `bs PASV!=MEMW`; status is `MEMW` 21 / `CODE` 14 / `MEMR` 7, and the
sign tracks the status (`MEMW` → negative, `CODE` → `+2`).
*Settled law*: `SCHEDULE`'s **−3** is named and **model-shared**
(`ucsim_t_provenance` §26.10 D item 3, `gaps` §I.5) — it lands `sim/` first.
**The `+2` mode with `CODE` status is NOT named by any settled law.**
*Decides it*: a directed cell that opens a `MEMW` out of an idle bus at a
controlled distance from the previous T4, swept over the wait level.
*Note*: `SCHEDULE` is **9 %** of the old bank's `ucore` residue and **31 %**
here — the raw tier at population scale is where it lives.

### **#3 — THE `ucore`-ONLY `PIN` FIVE.  5 seeds, no bus cycle moved.**

*Invariant*: family `PIN` on 5 of 5; **four part on the `data` lanes at the row
immediately after a write T1** (`MEMW+1` ×3, `IOW+1` ×1) with `ndiff` 2, 4, 6;
three of the five carry `mc1/721`'s signature exactly.
*Settled law*: **`mc1/721` — DIAGNOSED (§86.G part C: both writes land, in the
wrong order) and its fix SPECIFIED and NOT TAKEN** by §87.B's own registered
rule.  This is **a settled diagnosis with three new members**, which is the
first new evidence that item has had since it was booked.
*Decides it*: §86.G's own falsifier — *any ROM form whose post-`E` row writes a
register, followed by a 1BL form writing the same register, with a pre-popped
successor* — checked against these three seeds' opcodes in flight
(`3a.m`, `c6`, and one unreconstructable).

### Booked, not queued

* **`DATA_SEQ`, 23 seeds.**  13 at `delta 0`; cells `MEMR→MEMR` ×11 (same
  status, different **address**), `MEMW→MEMR` ×6, `IOW→MEMR` ×6; 23/23
  functionally bad.  ⚠ **`gaps` §T8's ±1/±2 low-address shape does NOT fit** —
  the eleven address deltas are **−45,274 … +16,146**, not ±1 or ±2.  Recorded
  as a refutation of the obvious guess, with no replacement offered.
* **H3-B, the grant-order swap.**  Under the census's own criterion —
  `delta == 0` with the *status* differing at the first contested slot —
  **11 seeds**, none of them class-A: `soup/wrand15` ×5, `soup/wrand7`,
  `soup/wvec-uni`, `soup/wvec-skew`, `raw/wrand2`, `raw/wrand3`, `raw/wrand7`.
  Under SM3's L2 definition (`PF_LOST` minus class A) it is **35**.  **DEFERRED
  BY USER DECISION; counted, not worked.**  The four directed cells D1-D4 stay
  specified and unrun.  ⚠ **`wvec-skew` — the shape built for H3-B — contributes
  exactly ONE of the eleven**, and `soup/wvec-skew` is the second-best soup
  stratum (98.67 %).  The shape has not yet earned its place; W3 should say so
  or the directed cells should.
* **`mc2/584`** (the missed `F` pop inside an eight-clock wait run): the survey
  counts no seed carrying its signature and does not chase it.
* **The model-only residue (≥ 6 seeds)**: **FROZEN BY USER DECISION.**

---

## §9 THE VICTORY BAR — COMPUTED AND **FROZEN**

> ### **S = 91.6681 %**
> ### **B = S − 5.0 = 86.6681 %**

`S` is the **unweighted mean of the 28 per-stratum hardware-versus-silicon
cycle-exact rates** of §1, under §1.1's registered exclusion.  **Neither `S`
nor the 5.0-point allowance may be re-derived after the tranche is scored**
(plan §5).  Converted to a whole seed count on the tranche's own scored
denominator, **rounded DOWN**, at the victory sitting; if the 196-seed body
scores with nothing excluded that is **169 / 196**, given here as arithmetic
and not as a prediction.

**Registered outcomes, unchanged** (plan §5): **MET** requires the tranche's
fabric rate ≥ `B` **and** every non-exact seed's first divergence falling in a
family named in §3's taxonomy.  **MISSED** is reported as registered and never
restated.  **VOID** if a B-1…B-9 bar fires.

### §9.1 THE TRANCHE — DRAWN AND FROZEN

`sw/testdata/wrfuzz/victory_population.json`,
**sha256 `dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d`**,
committed **before the first capture** (the b2 precedent, `ucsim_t_provenance`
§14.4).

* **The body**: the same 28 strata, **7 seeds each = 196**, at
  `k ∈ [300000 + 1000·i, +7)` — the §2.2 layout at a new base, **disjoint from
  every survey seed by construction**, not by a check.
* **The four directed H3-B cells** (prereg §5.2), all `skew` at `blk = 32`,
  **25 seeds each = 100**:

  | cell | tier | `wlo`/`whi` | k |
  |---|---|---|---|
  | **D1** | soup | 0 / 7 | 328016 … 328478 |
  | **D2** | soup | 1 / 15 | 329046 … 329550 |
  | **D3** | raw | 0 / 7 | 330018 … 330388 |
  | **D4** | raw | 1 / 15 | 331005 … 331347 |

  ⚠ **They are SELECTED, not FORCED, and the reason is booked rather than
  patched.**  `derive_case` has no override that pins a vector shape's
  *parameters* (`ov` carries `wvec_shapes`, a shape list; the parameters come
  from `wvec_shapes.draw_spec`'s own deterministic stream).  Rather than add a
  forcing knob to the generator in a survey sitting, each cell's k-block is
  **searched** for the seeds whose drawn spec already is
  `(skew, blk = 32, wlo, whi)`.  The draw is deterministic in `(cid, k)`, so
  membership is reproducible and frozen.  **BOOKED FOR W3**: a
  `force_wvec_spec` override, if the victory sitting wants forcing.
  `D_N = 25` is sized from §68.6's own statistic — 186 captures carrying 7,254
  paired accesses — so 100 captures at a p95 of 673 bus cycles is the same
  order of paired accesses as the measurement it is read against.
* **Repetitions**: **3 per cell**, **5** on the **12 promotion cells**
  `[300000, 309000, 310000, 311000, 312000, 313000, 314000, 323000, 324000,
  325000, 326000, 327000]` — declared mechanically as *the first seed of each
  of the ten `wvec` strata (the axis under test) plus the first seed of
  `soup/fix0` and `raw/fix0` (its w0 anchor in each tier)*.  b2's rule was "the
  first seed of each of the 9 wait classes plus three named others"; on a
  14-source grid that transposition would be 14, so it names the **new axis and
  its anchor** instead.
* **Cost**: 296 seeds, **912 seed-loops** ≈ 3.8 minutes of board time at the
  budgeted 4.0 seeds/s.

---

## §10 THE NON-REGRESSION LEGS OF THIS SITTING

The survey touched **one** shared instrument, so the legs that could have moved
were re-run.

| leg | registered | **measured this sitting** |
|---|---|---|
| `timed_fuzz --core ucore --pop reg` | 1,557 / 1,702 | **1,557 / 1,702 (91.5 %)**, OPEN_BUS 375, BOUND WARNINGS 4, ENGINE ABORTS 0, TB receipt `cede73e73a318753…` |
| `s15_census --core ucore --pop reg` (SM3 §2.1's own column) | `PF_LOST` 85 · `DATA_SEQ` 33 · `SCHEDULE` 13 · `PF_ADDR` 8 · `PIN` 4 · `PF_GAINED` 2 · `TAIL_EXTRA` 0 = **145** | **identical, to the seed** |
| B-4, all 3,150 images | 0 / 0 | **0 GEN_DRIFT, 0 REGEN_ERROR** |

**The one shared instrument that changed** is `sw/s15_census.py`: `one()` was
split into `classify(entry, chip, sim)` + a wrapper, so the campaign's
**fabric** rows — which no replay can regenerate — can be classified by the
tool's own taxonomy instead of a fork of it.  The same commit gave `classify`
`timed_fuzz.wait_class` for its stratum label, because the inline expression
reported every `wvec` seed as `fix0`.  **For every seed banked before task #38
that returns the identical string**, and the 145-seed column above is the
control that says so.

---

## §11 HOW TO READ THIS DOCUMENT

* **Quote `94.59 %` pooled, or `S = 91.6681 %`, with the exclusion named.**
  Never a bare "accuracy".
* **The offline legs (48/184, 49/184) are ATTRIBUTION FIGURES on a
  divergent-by-construction subset.**  They are not silicon-match rates for
  either engine and they never rank the two.
* **Quote a fabric figure only against its own bitstream** — everything here is
  FLASH #10, `nec_test_ucore.sof 1a01a6975e4a…`.
* **`S` and `B` are FROZEN.**  They were computed once, from §1, under an
  exclusion chosen against the survey's own convenience (it costs 1.7 points).
* **The `ucore`-only residue is 5** and it is complete; the model-only column
  is a floor of 6 and is not.
* **75 is the number the campaign turns on**, and it is one trap, not a table.
* **The axis has not yet found a harder population.**  §6.1 says so in those
  words, and the corpus design is not defended against its own result.
