# fuzz-v2 T10 — THE CORPUS PRE-REGISTRATION

**Committed 2026-08-08, BEFORE any generation at scale and BEFORE any board
contact.**  Plan: `~/.claude/plans/explain-how-the-current-proud-nest.md`
(Phase 5, task T10).  Tree: branch `fuzz-v2-on-relanding`.  Driver:
`sw/fz2_w1.py`.  Frozen population: `sw/testdata/fz2/fz2_population.json`.

⚠ **THE TREE MOVED UNDER THIS DOCUMENT WHILE IT WAS BEING WRITTEN, and the
correction is recorded rather than tidied away.**  Every static reading in §7
and every measurement in §3.2 / §5.3 was taken at **`c5f29a405b`**; the frozen
population was written at **`ce7fa2c073`** (its own `gen_git` field says so);
the commit landed on **`9fbbc55a91`**.  The two intervening commits are the
concurrent Quartus task's retention-build pre-registration and its receipt, and
`git diff c5f29a405b 9fbbc55a91 -- sw/ hdl/ sim/` is **one line in
`sw/testdata/receipts/quartus_bitstream.jsonl`** — no code moved, so nothing
read or measured here is stale.  `SEEDS_SHA256` and `SEED_LIST_SHA256` are
unchanged across all three (they do not carry `gen_git`, which is exactly why
the corpus is named by them and not by the file's sha256 — §2.5).

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

Everything below is registered.  A number in this document may be **met**,
**missed** or **superseded**, and a missed bar is **reported as registered and
never restated**.  Per the plan's own integrity rules, **a first registration
is not a ratchet**: every v2 column here is explicitly non-monotone until it
has been measured a second time on a different tree.

---

## §1 WHAT THIS DOCUMENT FIXES

After it is committed, **what gets captured and how it is scored are no longer
choices.**  It fixes, in advance:

* the strata, their sizes and their k-blocks (§2) — with **every seed named
  before it is generated**, in a frozen file with a content hash (§2.5);
* the two populations, their promotion rules and their disjointness (§4);
* the parameters the capture needs and the code does not yet carry — most of
  all `TERM_CLOCKS` and `TVEC` (§3);
* **the E-1 VALUE** (§5), which the erratum deliberately left unset;
* the capture-integrity bars C-1 … C-11, each a **STOP** and not a tolerance
  (§6);
* the capture-path preconditions that do not exist on this tree, so that a
  capture cannot quietly happen without them (§7);
* the acceptance criterion, **which is not a rate** (§8).

Named constants, for the driver's own `lint` to check this document against
`sw/fz2_w1.py` (a pre-registration that can drift from its driver constrains
nothing):

CORPUS_N = 3840
SEED_LIST_SHA256 = 45d25f31a325c4965da81117d5f4217b86487aa1abb0078faed26a72ed9bec32
SEEDS_SHA256 = 386c65fd641b84a11b8721fd237d8fbf7b857006cbf2689f3ae4e8f675ee24bd
CENSUS_BANK_N = 480
C9_N = 192
C9_REPS = 3
CAP_ROWS = 4096
ANCHOR_W0 = 145
DUMP_W0 = 240
TERM_MARGIN = 1.2

`python3 sw/fz2_w1.py lint` parses the table in §2.2, the bar names in §6 and
every constant above out of THIS FILE and compares them to the code and to the
frozen population.  It exits non-zero on any disagreement.

---

## §2 THE STRATIFICATION

### 2.1 The grid

**One rule per population, not a hand-built table**: `tier × event class ×
wait source`.

| axis | levels | why these |
|---|---|---|
| **tier** | `soup`, `raw` | the two generators.  They differ by a stated mechanism, not by degree — see §5.2 |
| **event class** | `noevt`, `stim` | the two configurations `fuzz_campaign.derive_case` can express today (`no_evt` / `force_evt`).  `stim` draws INT or NMI 70/30 from its own frozen RNG namespace, so **which pin each seed gets is fixed before generation and is enumerated in the frozen population** rather than being a stratum of its own.  Measured over the frozen corpus: **INT 1,359 · NMI 561 · POLL 0** |
| **wait source** | census: `fix0`, `wrand3`, `wvec-uni`; enriched: `fix0` `fix1` `fix2` `fix3` `wrand1` `wrand3` `wrand7` `wrand15` `wvec-uni` | fixed, seeded-random and per-access-vector, i.e. all three wait mechanisms the rig has.  The census takes one of each so its unweighted per-stratum mean is a mean over MECHANISMS; the enriched set widens the levels |

> **CENSUS = 2 × 2 × 3 = 12 strata × 80 = 960 seeds** (`cid = fz2c`)
> **ENRICHED = 2 × 2 × 9 = 36 strata × 80 = 2,880 seeds** (`cid = fz2e`)
> **TOTAL = 3,840 seeds.**

**Why n = 80 per stratum, and why the totals are what they are.**  Not board
time.  ⚠ **Two different measured rates exist and they are not the same
number**: `sw/testdata/wrfuzz/w1_capture.json` records 3,150 seeds in
**386.4 s = 8.2 seeds/s** for the whole W1 session, while the per-campaign
heartbeats record **6.0 /s** (`mc1` 6.01 over 810 seeds, `mc2` 6.04 over
5,000).  This document budgets at the SLOWER of the two, derated a further
1.5× to **4.0 /s** (§6), which puts the whole corpus plus the C-9 repetitions
at **≈ 18 minutes**.  The binding constraints are (a) **offline scoring
wall-time** — every banked seed is replayed on every gate run, so the standing
bank is capped at **≤ 3,500** — and (b) **`fuzz_bank.CAP_MB = 25` per campaign
id**, which at the measured ~22 KB per banked entry truncates a bank at about
1,150 seeds.  n = 80 gives a 95 % interval half-width of **±6.6 points at
p ≈ 0.9** per stratum, and 12 census strata make the census's own unweighted
mean tight enough to read while leaving both caps unbreached (§4.3).

**The strata are INDEPENDENT populations, not a paired design.**  `nmax_eff`
is a function of the effective wait level (`NMAX_SCALE_C = 4`), so "the same
program at a different wait level" is not available without breaking the
capture budget.  Stated here so nobody reads the table as paired.

### 2.2 The k-blocks — every seed named before it is generated

Blocks are 1,000 apart from each population's own `k_base`, in the order
below; stratum *i* occupies `k ∈ [k_base + 1000·i, k_base + 1000·i + 80)`.
`fz2c` starts at 400000 and `fz2e` at 500000, so **the two populations are
disjoint seed for seed by construction**, not by a rule someone must remember.

| i | pop | cid | tier | evt | wait | k range | n |
|---|---|---|---|---|---|---|---|
| 0 | census | fz2c | soup | noevt | fix0 | 400000-400079 | 80 |
| 1 | census | fz2c | soup | noevt | wrand3 | 401000-401079 | 80 |
| 2 | census | fz2c | soup | noevt | wvec-uni | 402000-402079 | 80 |
| 3 | census | fz2c | soup | stim | fix0 | 403000-403079 | 80 |
| 4 | census | fz2c | soup | stim | wrand3 | 404000-404079 | 80 |
| 5 | census | fz2c | soup | stim | wvec-uni | 405000-405079 | 80 |
| 6 | census | fz2c | raw | noevt | fix0 | 406000-406079 | 80 |
| 7 | census | fz2c | raw | noevt | wrand3 | 407000-407079 | 80 |
| 8 | census | fz2c | raw | noevt | wvec-uni | 408000-408079 | 80 |
| 9 | census | fz2c | raw | stim | fix0 | 409000-409079 | 80 |
| 10 | census | fz2c | raw | stim | wrand3 | 410000-410079 | 80 |
| 11 | census | fz2c | raw | stim | wvec-uni | 411000-411079 | 80 |
| 0 | enriched | fz2e | soup | noevt | fix0 | 500000-500079 | 80 |
| 1 | enriched | fz2e | soup | noevt | fix1 | 501000-501079 | 80 |
| 2 | enriched | fz2e | soup | noevt | fix2 | 502000-502079 | 80 |
| 3 | enriched | fz2e | soup | noevt | fix3 | 503000-503079 | 80 |
| 4 | enriched | fz2e | soup | noevt | wrand1 | 504000-504079 | 80 |
| 5 | enriched | fz2e | soup | noevt | wrand3 | 505000-505079 | 80 |
| 6 | enriched | fz2e | soup | noevt | wrand7 | 506000-506079 | 80 |
| 7 | enriched | fz2e | soup | noevt | wrand15 | 507000-507079 | 80 |
| 8 | enriched | fz2e | soup | noevt | wvec-uni | 508000-508079 | 80 |
| 9 | enriched | fz2e | soup | stim | fix0 | 509000-509079 | 80 |
| 10 | enriched | fz2e | soup | stim | fix1 | 510000-510079 | 80 |
| 11 | enriched | fz2e | soup | stim | fix2 | 511000-511079 | 80 |
| 12 | enriched | fz2e | soup | stim | fix3 | 512000-512079 | 80 |
| 13 | enriched | fz2e | soup | stim | wrand1 | 513000-513079 | 80 |
| 14 | enriched | fz2e | soup | stim | wrand3 | 514000-514079 | 80 |
| 15 | enriched | fz2e | soup | stim | wrand7 | 515000-515079 | 80 |
| 16 | enriched | fz2e | soup | stim | wrand15 | 516000-516079 | 80 |
| 17 | enriched | fz2e | soup | stim | wvec-uni | 517000-517079 | 80 |
| 18 | enriched | fz2e | raw | noevt | fix0 | 518000-518079 | 80 |
| 19 | enriched | fz2e | raw | noevt | fix1 | 519000-519079 | 80 |
| 20 | enriched | fz2e | raw | noevt | fix2 | 520000-520079 | 80 |
| 21 | enriched | fz2e | raw | noevt | fix3 | 521000-521079 | 80 |
| 22 | enriched | fz2e | raw | noevt | wrand1 | 522000-522079 | 80 |
| 23 | enriched | fz2e | raw | noevt | wrand3 | 523000-523079 | 80 |
| 24 | enriched | fz2e | raw | noevt | wrand7 | 524000-524079 | 80 |
| 25 | enriched | fz2e | raw | noevt | wrand15 | 525000-525079 | 80 |
| 26 | enriched | fz2e | raw | noevt | wvec-uni | 526000-526079 | 80 |
| 27 | enriched | fz2e | raw | stim | fix0 | 527000-527079 | 80 |
| 28 | enriched | fz2e | raw | stim | fix1 | 528000-528079 | 80 |
| 29 | enriched | fz2e | raw | stim | fix2 | 529000-529079 | 80 |
| 30 | enriched | fz2e | raw | stim | fix3 | 530000-530079 | 80 |
| 31 | enriched | fz2e | raw | stim | wrand1 | 531000-531079 | 80 |
| 32 | enriched | fz2e | raw | stim | wrand3 | 532000-532079 | 80 |
| 33 | enriched | fz2e | raw | stim | wrand7 | 533000-533079 | 80 |
| 34 | enriched | fz2e | raw | stim | wrand15 | 534000-534079 | 80 |
| 35 | enriched | fz2e | raw | stim | wvec-uni | 535000-535079 | 80 |

**RESERVED AND NOT TO BE USED BY THIS CORPUS**: `k ≥ 600000`.  Any later
directed or victory tranche draws from there and is therefore **disjoint from
every seed above by construction** — §64.1's disjoint-validation discipline,
applied to the corpus rather than to a law.

### 2.3 What the frozen corpus contains, counted in advance

From `sw/testdata/fz2/fz2_population.json` (`freeze`, 3,840 seeds, 4.6 s):

| | census | enriched |
|---|---|---|
| seeds | 960 | 2,880 |
| with a stimulus event | 480 | 1,440 |
| … INT / NMI / POLL | 334 / 146 / 0 | 1,025 / 415 / 0 |
| … `hold = 2` / `hold = 300` | 307 / 173 | 934 / 506 |
| `has_tf` | 31 | 70 |
| `has_halt` | 173 | 506 |
| raw whole-image mode | 332 | 1,032 |
| `TERM_CLOCKS` range | 2,710 … 3,634 | 1,901 … 3,634 |

Two things follow and are registered here rather than discovered later:

1. **Both hold values C-6 needs are in the corpus by construction** — 1,241
   seeds at `hold = 2` and 679 at `hold = 300` (`build()` raises the hold to
   300 when the program contains a HALT).  The pin-level proof costs no extra
   board time.
2. **The three classes the terminating NMI exists to rescue are present and
   counted**: 101 TF seeds, 679 HALT seeds, 1,364 raw whole-image seeds.  They
   are reported per class in the census and **nothing gates on a per-class
   rate** — see §5.3.

### 2.4 The invocation, per stratum

```
python3 sw/fuzz_campaign.py run <fz2c|fz2e> \
    --start <k_lo> --session-seeds 80 --force-tier {soup|raw} \
    {--no-evt | --force-evt} --survey \
    [ --force-fixed W | --force-wrand W | --wvec-shapes uni ]
```

driven by `python3 sw/fz2_w1.py capture`, which owns the order, the resume and
the halt rule.  `--survey` keeps census mode (all w0 TIMING and
non-provenance FUNCTIONAL divergences are surveyed instead of stopping on the
first) while the HARD capture-integrity stops stay armed: any provenance alarm
and the ≥ 5-consecutive-quarantine circuit breaker still abort.

**Resume is by `fz2_w1._done_ks()`** — every k actually present in
`results.jsonl` — and explicitly **not** by `fuzz_campaign._resume_k`, which
returns `max(k) + 1` and in a block-stratified corpus would silently skip every
unwritten k below the highest one.  **A stratum that writes fewer lines than it
was asked for HALTS the driver.  It is not nursed.**

### 2.5 The frozen population file

`sw/fz2_w1.py freeze` derives and builds all 3,840 seeds and writes
`sw/testdata/fz2/fz2_population.json`: per seed, the tier, `cfg_hash`,
`nmax_eff`, effective wait level, `TERM_CLOCKS`, the event directive
(pin/delay/hold), the vector spec, `has_tf`, `has_halt` and `raw_mode`.  It is
committed with this document.

The file's own sha256 **moves with `gen_git`** and is therefore not the
corpus's name.  The two names that are:

* `SEEDS_SHA256` — sha256 over the derived seed rows alone.  A reviewer
  re-running `freeze` at any later HEAD reproduces it byte for byte, or the
  generator moved.
* `SEED_LIST_SHA256` — sha256 over the `<cid> <k>` list, a pure function of the
  strata.

---

## §3 THE PARAMETERS THIS DOCUMENT FIXES

### 3.1 The two termination routes

| route | reached by | broken by |
|---|---|---|
| **INT3** | any escape into the `0xCC` fill, at any alignment, vector 3 → `TERM_AT` | a runtime write over IVT[3] or over the terminator |
| **NMI** | the terminating scheduler at `TERM_CLOCKS`, vector read intercepted, `TVEC` served from a register | a runtime write over the terminator; 8080 entry; a frame landing on the terminator |

The NMI route is **immune to the IVT** by construction (D3 substitutes the
vector DATA), which is the whole reason it is a register and not a pre-written
image word.  The soup tier has both routes; the raw whole-image tier has
effectively one (§5.2).

### 3.2 `TERM_CLOCKS` — ONE FORMULA, reusing the capture budget's own constant

The terminating NMI's delay is measured from the anchor's `CODE` T1 + 2.  It
must be late enough not to truncate a normal run and early enough to leave the
dump inside the rig's 4,096-record capture.  Both scale with the cost of a bus
cycle, so:

```
scale        = (NMAX_SCALE_C + weff) / NMAX_SCALE_C          # 4, the existing constant
TERM_CLOCKS  = CAP_ROWS − ceil(TERM_MARGIN × (ANCHOR_W0 + DUMP_W0) × scale)
             = 4096 − ceil(1.2 × 385 × scale)
```

`weff` is `fuzz_campaign`'s own effective wait level (`_wvec_weff`'s ceil-mean
for a vector seed, `wmax`/`fixed` otherwise) — a third rule is not invented.

**Both w0 constants are MEASURED, on the ucore TB, on a scratch cid disjoint
from every corpus k-block** (2026-08-08, 24 seeds): the anchor's first `CODE`
T1 lands at **row 145**, and the dump costs **219 clocks** from its first
`OUT 0xFE` to the done marker; `DUMP_W0 = 240` adds the NMI entry's two vector
reads and three pushes.  At fixed w3 the same seeds give **273** and **425**,
i.e. both scale as the formula says, inside the declared margin.
`TERM_MARGIN = 1.2` is a **stated margin, not a fit.**

Registered floor: `TERM_CLOCKS ≥ 512` for every seed in the corpus; the driver
asserts it at import and again per seed in `preflight`.  Measured range over
the frozen corpus: **1,901 … 3,634**.

### 3.3 `TVEC`, and the control values

The corpus runs with `TVEC = (CS 0x0000, IP 0xBF00) → TERM_AT` and
`vecsub_en` set for the terminating scheduler **only**.  C-6's interception
proof uses a second value that differs in **both halves** and lands on a
**different physical address** — `TVEC_B = (CS 0x0BF0, IP 0x0008) → 0xBF08` —
so what is proved is that the whole 32-bit word is served, not that some
default happened to work.

### 3.4 The declared discard classes

Three, each independently detected, each named before the capture:

| class | detector | why it is a discard and not a failure |
|---|---|---|
| `arch_restart` | more than one `MAGIC` before the done marker (`fuzz_classify.dump_restarted`) | the terminating NMI landed mid-dump; the second run's `AW` is the first run's shuttle, so the dump is unrepairable (D7) |
| `ps3_8080` | PS3 set on a `CODE` T1 on **either** leg (`timed_fuzz.native_exclusion`'s predicate) | 8080/BRKEM is deferred by user decision; D9's binding capture-side clause |
| `wrote_term` | a MEMW/IOW into `[TERM_AT, CODE_HI)` before the first done marker | the program overwrote the thing that terminates it — the one leak D2 says is not preventable |

**A non-dumping seed matching none of the three is UNDISPOSITIONED, and the
undispositioned count is a STOP at zero** (§5.3).

---

## §4 THE TWO POPULATIONS

### 4.1 CENSUS (`fz2c`) — a population rate, because nothing selects on the outcome

* **Every one of the 960 seeds is captured and every one produces a result
  line.**  The census's rates are computed from the lines, so no seed is
  omitted for any reason, including its verdict.
* **The bank is promoted by a FROZEN ARITHMETIC RULE**: every second k of every
  census stratum — `(k − k_lo) % 2 == 0` — **480 seeds, enumerated before the
  first capture**, listed in the frozen population file.  There is **no
  divergence-driven quota, no per-signature cap, no ballast quota and no
  first-N-per-class rule** anywhere in it.
* The old bank's rates were a selection artefact and `standing_gates.md` says
  so.  This is the structure that does not repeat it.

### 4.2 ENRICHED (`fz2e`) — an additive regression corpus, and not a rate

* 2,880 seeds, banked under **`fuzz_bank.promote`'s existing quota rule**
  (every FUNCTIONAL; provenance QUARANTINEs capped at 20; unexplained TIMING
  capped at 10 per signature; first 50 per KNOWN_ACCEPTED class; a 1-in-50
  CADENCE sample; 100 stratified SUCCESS ballast).
* **Its promotion is divergence-driven, so no rate computed on it is a
  population rate, and `fz2_w1 bars` does not compute one.**  It exists to make
  the standing bank cover mechanisms the census's 960 would miss.

### 4.3 Never pooled — and the arithmetic that keeps both caps unbreached

Different campaign ids, disjoint k-blocks, separate bank directories, separate
result files, separate roll-ups.  No figure in any deliverable may be a count
over the union.

| | seeds banked | at ~22 KB | vs `CAP_MB = 25` |
|---|---|---|---|
| `fz2c` (frozen rule) | 480 | ~10.6 MB | inside |
| `fz2e` (quota rule) | ≤ ~1,150 (the cap binds first) | ~25 MB | at the cap |
| **standing bank** | **≤ ~1,630** | | **vs the ≤ 3,500 ceiling** |

**`_capped` must be 0 on both ids (C-11).**  A truncated bank is a prefix of
the promotion order, which is a selection artefact of exactly the kind this
design exists to avoid.  If the enriched promotion would exceed the cap, the
registered response is: **HALT, report the count, raise `CAP_MB` in its own
commit and RE-BANK the whole population.**  The bank is never left truncated
and the corpus is never trimmed after the numbers are seen.

---

## §5 ERRATUM E-1 — THE VALUE

E-1 registered the **predicate** — containment is measured as
**terminator-reached** (a `MAGIC`-anchored 15-word dump), with
`escaped_code_region` retained as a **diagnostic counter on the result line**
— and deliberately left the **VALUE** unset, because fitting it to the
2,000-seed population that motivated the restatement would be the same error
twice.  **The value is set here, against these strata.**

### 5.1 WHICH INSTRUMENT — and one that is disqualified

⚠ **The offline column (b) is a FLOOR, not the figure.**
`fuzz_campaign measure` runs through `tb_v30_core`, whose batch grammar carries
**one `evt` tuple, no `TVEC` and no `vecsub`**, so **the terminating NMI cannot
fire there at all** — and the three classes below 90 % (TF **47.1 %**,
HALT/POLL **72.1 %**, raw whole-image **23.3 %**, all on the ucore) are exactly
the ones D3's backstop exists to rescue.

> **The bar is set on the instruments that carry the backstop: the board's
> socket leg, pre-validated on `tb_sys`.  `tb_v30_core` is DISQUALIFIED from
> this bar in both directions — no `measure` and no `--tb-only` figure may be
> quoted for or against it, ever.**

This also inherits `standing_gates.md` §F-4: `check_seq.CORE` is pinned to the
archived `fsm` core, so a `--tb-only` number is not even an ucore number.

**The `tb_sys` pre-run is a DRY RUN, not the score.**  `sw/fz2_tbsys.py`'s four
legs — (a) three events fire, (b) interception, (c) the `vecsub_en = 0`
negative control, (d) the must-not-fire control — are the plan's Phase-3 gate
and must pass before any flash.  Running §5.3's clauses over the frozen
population on `tb_sys` beforehand is allowed and its numbers are **reported**;
they do **not** replace the registered values and **they do not license
changing them.**  The values above are scored on the board's socket leg.

### 5.2 HOW MANY NUMBERS — two, per TIER

**Not one.**  The two tiers differ by a **stated mechanism**, not by degree:
soup's code region is `0xCC` outside the body, so an escape traps to INT3 at
any alignment and the image terminates itself; raw's whole-image mode (**1,364
of the 3,840 frozen seeds**) is random bytes over `0x0000-0xFDFF` with no fill,
so it has **one** termination route where soup has **two**.  A single number
would be either the raw number (vacuous for soup) or the soup number (a bar on
a mechanism raw does not have).

**Not per class.**  TF / HALT / undoc are mixtures the generator draws *inside*
the soup tier at fixed probabilities.  A bar per class is a many-cased rule and
a fitted table — the signal the standing design principle names.  They are
counted in advance (§2.3), reported per class in the census, and **nothing
gates on a per-class rate.**

### 5.3 THE VALUES

| clause | registered | the arithmetic behind it |
|---|---|---|
| **E-1a soup** | **terminator-reached ≥ 99.0 %**, per population, over the FULL stratum (discards included) | the offline floor without the backstop is 97.1 % on clean soup, and the backstop is monotone — it can only add — so the design's own claim is 100 %.  The 1.0 point is the budget for the two mechanisms the design admits it cannot prevent: a frame landing on the terminator (D2) and a restarted dump (D7).  **Measured mechanism input** (24 soup seeds, ucore TB, scratch cid): 0.25 MEMW into the 16 KB code region per run and **0 into the terminator page**, so P(overwrite) ≈ 0.1 % and the expectation is ≈ 99.9 % |
| **E-1b raw** | **terminator-reached ≥ 95.0 %**, same basis | after the backstop the only raw-specific leak is a **runtime** write over the terminator: the generator's random band already stops at `IHT_AT`, and the vector overlay makes the NMI route immune to a scribbled IVT.  The terminator is **70 bytes** (`len(_TERM)`, 16 + 54) inside a 16 KB code region, and 24 raw seeds executed **9.7 MEMW into that region per run** → P(hit) ≈ 1 − (1 − 70/16384)^9.7 ≈ **4.1 %**, i.e. an expectation of ≈ 95.9 %.  **The bar is set below the expectation by less than two points, and it can be missed.**  That is deliberate |
| **E-1c undispositioned** | **0 seeds**, and this is the clause that is **not a rate** | every seed that does not dump must carry one of §3.4's three signatures.  One that carries none is the catch-all, and the catch-all must be EMPTY.  The two rate clauses bound the discard fraction from above; this one bounds the unexplained residue from below, so the bar cannot be met by discarding |

**What is NOT registered as a bar**: the escape count.  E-1's own ruling keeps
it as a **diagnostic counter** — it measures the prefetch shadow (median 2
fetches, bounded by the 6-byte queue), not a containment failure — and it is
reported per stratum with its median and maximum and gates nothing.

**Falsifiers, written before the run.**  E-1a fails if the backstop does not
rescue TF/HALT: the same three classes will still be visible per class, and a
soup miss whose non-dumping seeds are concentrated in them refutes D3 rather
than the corpus.  E-1b fails if `wrote_term` exceeds ~5 %, which refutes the
arithmetic above (and is itself a result about the raw tier, not a rig defect).
E-1c fails if any non-dumping seed carries none of the three signatures, which
means a fourth mechanism exists and must be named before anything else is
quoted.

---

## §6 THE CAPTURE-INTEGRITY BARS

Each is a **STOP**, not a tolerance.  A bar that fires means fix the rig and
**RE-CAPTURE** — the correctness directive's own clause.  Scored by
`python3 sw/fz2_w1.py bars`, offline, off the banked results.  A bar whose
input field is absent reads **NOT SCOREABLE**, never MET.

| bar | statement | registered value |
|---|---|---|
| **C-1** | **CONTAINMENT**, measured as terminator-reached (E-1's predicate), the escape count retained as a diagnostic | soup **≥ 99.0 %**, raw **≥ 95.0 %**, per population; **0 UNDISPOSITIONED** non-dumping seeds (§5.3) |
| **C-2** | **THE ARCH COLUMN IS NON-VACUOUS — demonstrated, not assumed** | `MAGIC == 0x5EED` on **every** dump, and each of the other **14** `STORE_ORDER` words takes **≥ 2 distinct values** across the corpus.  A constant word means the dump is reporting the harness, not the seed |
| **C-3** | **8080-FREE, BOTH CLAUSES.**  Generation: `fuzz_campaign.bad_0f_pairs` over `optable.CODE_SPANS`.  Runtime: PS3 on a `CODE` T1 on **either** leg | **0** forbidden `0F xx` pairs on every composed image **and 0** captures with a PS3 entry.  ⚠ Both are required; the generation clause alone cannot see a pair a runtime write creates |
| **C-4** | **ERA.**  Every capture carries the RTL input-manifest hash, the generator SHA, `RIG_EVT_HOLD_BITS` and the pinned `flash_log` entry | **0** captures with an absent, incomplete or mixed era stamp; `build_stale` **0** |
| **C-5** | **NO GEN-DRIFT.**  Every image regenerates byte-identically from `(cid, k, ov)` through `compose_case`; every vector re-derives to its banked `wvec_hex` | **0** GEN_DRIFT, **0** vector mismatches, over **all 3,840** |
| **C-6** | **THE RIG APPLIED THE DIRECTIVES IT WAS HANDED.**  Three parts, all required | (a) `EVT2_CFG` / `EVT3_CFG` / `TVEC` / `VECCTL` **round-trip on the readback path** (INV-1's actual lesson); (b) a **PIN-LEVEL proof by counted rows at ≥ 2 hold values** — every event seed's counted high-row run equals its own `hold` ± 1 clock, and the corpus carries 1,241 seeds at `hold = 2` and 679 at `hold = 300`; (c) **interception proven on the rows at ≥ 2 distinct `TVEC` values** (§3.3), with the negative control `vecsub_en = 0` **not** terminating |
| **C-7** | **THE BUS-CYCLE BOUND.**  Past 4,096 the three legs do three different things with a vector | **0** captures at or beyond **4,096** bus cycles.  Any such seed is QUARANTINED and reported, never scored |
| **C-8** | **BOARD DISCIPLINE.**  `div_guard` at every stratum boundary with its readback recorded; socket-vs-fabric A/B differing only in `use_core`; every capture this driver banks retained as **full per-clock rows with a sha256 beside them**, never a digest alone; `board_idle()` after the session with `use_core=0` left selected | **`div_guard` PINNED on 100 % of probes**; **0** unpinned readbacks — an unpinned readback is a rig-integrity FINDING and a hard stop |
| **C-9** | **THE CAPTURE IS STABLE**, in rows **and** in the arch column | a declared **5 % stratified sub-sample = 192 seeds × 3 repetitions**, compared in `fuzz_classify.diff_rows`' own window; **192 / 192 stable**, and the 15-word dump identical across all three reps.  A stable row set with an unstable dump is a finding the row diff cannot see, which is why both are compared |
| **C-10** | **TRANSPORT.**  RunError → one reconnect + one retry, else QUARANTINE; ≥ 5 consecutive quarantines trips the circuit breaker; a short stratum HALTS the driver | circuit breaker **not tripped**, **no halted stratum**; the transport-error count is REPORTED, not barred |
| **C-11** | **BANK INTEGRITY.**  The census bank IS the frozen rule and the populations are never pooled | the census bank equals the **480** enumerated seeds **seed for seed**; **`_capped` = 0** on both ids; standing bank **≤ 3,500**; **0** seeds in both banks |

**Board-time budget, registered.**  At the slower of the two measured rates
(6.0 /s, §2.1), derated a further 1.5× to 4.0 /s:

| pass | seed-loops | at 4.0/s |
|---|---|---|
| the corpus | 3,840 | 16.0 min |
| C-9 (192 seeds, 2 extra reps) | 384 | 1.6 min |
| C-6's control legs + reconnect slack + the closing `use_core=0` | — | ~7 min |
| **registered session bound** | | **≤ 30 minutes of board time** |

---

## §7 THE CAPTURE-PATH PRECONDITIONS — WHAT DOES NOT EXIST YET

The v2 rig RTL, `v30ctl`'s host registers and `tb_sys` all carry the three
schedulers and the NMI vector overlay (T5/T6/T8, landed).  **The capture path
does not.**  Verified against the artifact at `c5f29a405b`, not recalled:

```
$ python3 sw/fz2_w1.py preflight --sample 3
== capture-path preconditions (prereg §6)
  *** MISSING: serve client -- v30run.ServeRunner.run lacks ['evts', 'tvec', 'vecsub'];
      the board's `serve` accepts evt2/evt3/tvec/vecsub and the client never sends them
  *** MISSING: run_image -- v30run.run_image lacks ['evts', 'tvec', 'vecsub']
  *** MISSING: run_chip -- check_seq.run_chip lacks ['evts', 'tvec', 'vecsub']
  *** MISSING: capture_board -- fuzz_campaign.capture_board never programs TVEC/VECCTL,
      so the terminating NMI cannot be armed
  *** MISSING: keep_rows -- fuzz_campaign.cmd_run has no keep-rows control, so the frozen
      census bank's rows are not retained
  *** MISSING: result line -- fields absent: ['arch_words', 'arch_sim_ok', 'arch_sim_words',
      'arch_match', 'ps3_8080', 'wrote_term', 'term']
  *** MISSING: row decode -- analyze_capture.decode_words does not expose
      ['pin_int', 'pin_nmi', 'pin_poll_n', 'vec_armed']
```

Each is a **STOP that this driver checks before board time is spent**, and
`fz2_w1 capture`, `stability` and `control` all REFUSE while any remains.  The
list is registered here so that T11 delivers a named thing rather than
whatever the capture happened to need:

1. **The terminating NMI must be armable from the host.**  The board's `serve`
   already parses `evt2` / `evt3` / `tvec` / `vecsub`; the client
   (`v30run.ServeRunner.run` → `run_image` → `check_seq.run_chip` →
   `fuzz_campaign.capture_board`) never sends them.  **Without this the corpus
   has no backstop and §5's values are unmeasurable.**
2. **The frozen census bank's rows must be retained.**  `eval_case` already
   takes `keep_rows`; `cmd_run` never sets it, and its ballast path is quota'd
   (100 total, ~17 per stratum) so it cannot serve as the frozen rule.
3. **The result line must carry the columns the bars are scored on**:
   `arch_words`, `arch_sim_ok`, `arch_sim_words`, `arch_match` (C-1/C-2 and the
   arch-exact decomposition), `ps3_8080` (C-3's binding clause, D9's own
   words: *"promoted inline as a DISCARD with the reason on the result line"*),
   `wrote_term` (§3.4), and `term` = `{fired[3], vec_used, tvec, term_clocks,
   hold_rows}` (C-6).  All are computable in `eval_case` from rows already in
   hand.
4. **The row decoder must expose what the RTL already records**:
   `nec_bus.sv` puts the **effective** pins at `[54:52]` and `vec_armed` at
   `[59]`, and `analyze_capture.decode_words` — which every comparison goes
   through — skips both.  Without them C-6(b) and C-6(c) cannot be scored on
   the rows at all.

**Each of these must be verified as EXISTING AND HONOURED, never merely
accepted.**  That is CLAUDE.md's `want_raw` lesson, and its mirror image: a
`keep_rows_every` that `cmd_run` accepts into its Namespace and ignores would
produce a census bank that is silently the ballast quota.

---

## §8 THE DELIVERABLE, AND THE ACCEPTANCE CRITERION

### 8.1 The three decompositions — reported separately, never as one aggregate

| decomposition | what it is | how it is aggregated |
|---|---|---|
| **rows-exact rate** | per-clock socket-vs-fabric rows identical (`bad_rows == 0`) | the **unweighted mean of the per-stratum rates**, per population.  A pooled count is not computed anywhere |
| **arch-exact rate** | the 15-word `MAGIC`-anchored dump identical on both legs (`arch_match`) | the same |
| **unscoreable count** | seeds for which neither can be computed | a **count**, never a rate.  It must be ~0 by construction; if it is not, escape elimination or the terminator failed, **and that is the finding rather than a footnote** |

The census's per-stratum table also carries: `n`, captured, the verdict
census, the three declared discard classes separately, the escape diagnostic
(median and max), and the per-class breakdown of §2.3 (TF / HALT / undoc /
raw-mode).

### 8.2 Acceptance — which is NOT a rate

> **Accepted when: every bar C-1 … C-11 is MET; the residue taxonomy's
> catch-all is EMPTY; and the arch column is demonstrably non-vacuous (C-2,
> demonstrated, not assumed).**

No rate appears in that sentence.  A high rows-exact rate with a non-empty
catch-all is not acceptance; a low one with every bar met is a survey result to
be routed, not a failure of the corpus.

Two further conditions carried from the plan's integrity rules:

* **Re-measurability.**  A second run on a different tree must reproduce the
  corpus seed for seed — `SEEDS_SHA256` is how that is checked, and `C-5` is
  how it is proved on the images.
* **A first registration is not a ratchet.**  Every number this corpus
  produces is non-monotone until it has been measured a second time on a
  different tree.  None of them may be quoted as a bar before that.

---

## §9 WHAT IS NOT IN THIS CORPUS, AND WHY

* **No POLL stimulus.**  `force_evt` draws INT or NMI only; POLL is not an
  interrupt pin and the plan's requirement is "both external interrupt pins".
  0 POLL seeds, stated rather than discovered.
* **Only the `uni` wait-vector shape.**  `walk` / `skew` / `burst` / `edge` are
  wrfuzz's *directed* shapes with their own campaign and their own quoting
  rule; `uni` is here as the **composition control** — evidence that the v2
  changes did not break the vector axis — and nothing more.  An **EVT ×
  directed-shape** cell is NAMED and reserved for a later campaign.
* **No 8080/BRKEM.**  Deferred by user decision, eliminated by construction,
  and **counted** by C-3's runtime clause rather than filtered after the
  numbers are seen.
* **No `--strict` / `--mainline` suppression.**  Those knobs remove
  deliberately divergent classes for a bug hunt.  This is a survey, and undoc /
  TF / random-DS breadth is part of what it should be asked about.
* **No victory tranche.**  This document registers a survey corpus.  A victory
  tranche, if one is wanted, draws from `k ≥ 600000` and is disjoint from every
  seed here by construction.

---

## §10 WHAT T10 DID NOT DO

* **No board was contacted.**  No `v30ctl`, no serve session, no `div_guard`,
  no flashing.  The only board-touching code paths in `fz2_w1.py` are behind
  `--board` or behind the capture-path refusal, and neither ran.
* **No Quartus.**  A concurrent task holds it.
* **No capture, and none is possible**: §7's preconditions are unmet and the
  driver refuses.
* **No RTL, no `sim/`, no `sw/` mechanism change.**  The only files added are
  this document, `sw/fz2_w1.py` and the frozen population; nothing existing was
  edited, so no standing gate's inputs moved.
* **No ratchet moved and no number restated.**

---

## §11 AMENDMENTS — APPENDED, NEVER BACK-EDITED

Everything above this line is the document as committed on 2026-08-08 at
`9fbbc55a91`, plus the §0 erratum it already carried.  **Nothing above has been
edited by any amendment below**, so a reviewer can read the original bar and
the change to it side by side.  Each amendment states WHAT changed, WHEN it was
decided relative to the board work, and WHICH registered values moved.

### A-1 — `escaped_code_region` LEAVES THE PROVENANCE-ALARM SET, IN BOTH TIERS

**Decided 2026-08-08, T11, AFTER a 2-seed board result and BEFORE the capture.
The timing is stated first because an amendment that hides its own timing is
worse than the contradiction it settles.**  The census ran `fz2c` stratum 0 and
halted itself on its SECOND seed:

```
=== run fz2c: 2 seeds in 0.5s STOPPED escalation:provenance_alarm @k=400001
  verdicts (2): {'SUCCESS': 1, 'QUARANTINE': 1}
*** cen/soup/noevt/fix0 wrote 2/80 rc=0 -- STOPPED, not nursed ***
```

on `provenance_alarm:escaped_code_region_real_123b@765,escaped_code_region_sim_123b@765`
— an escape at the same row and the same address on BOTH legs, with the seed
otherwise clean (`arch_ok` true, `arch_match` true, MAGIC `0x5EED`, `bad_rows`
0, `term.readback_ok` true, `escaped_n` 2).  Two seeds is not a population and
no number below is offered as one.

**WHAT CHANGED.**  `escaped_code_region` is removed from
`fuzz_classify.provenance_alarms` — **entirely, in both tiers, with no
soup/raw split.**  It therefore no longer QUARANTINEs a seed and no longer
raises `("STOP", "provenance_alarm")` in `EscalationPolicy`.  It is still
COMPUTED and still REPORTED, on every result line, as `escaped` (row, physical
offset) and `escaped_n` (the count) — `fuzz_campaign.eval_case`, unchanged.

**IT COMPLETES E-1; IT DOES NOT REVISE IT.**  §5.3 already ruled, in writing
and before any board contact, that the escape count is *"a diagnostic
counter … and it GATES NOTHING"*.  Only half of that landed: the result-line
half.  The escalation half never did, and §2.4's blanket *"any provenance alarm
… still abort"* silently re-armed the thing §5.3 had disarmed.  The two clauses
contradicted each other, the contradiction was reachable only on the board, and
the driver was right to halt on it rather than nurse it.  A-1 makes the code do
what E-1 said, in one place instead of two.

**WHY GLOBAL AND NOT A SOUP/RAW SPLIT.**  A two-tier predicate would be a
many-cased rule invented after a result, which is the signal the standing design
principle names, and it would be a second decision where one was already taken.
The mechanism points the same way: the predicate justifies itself with *"every
other byte of the code region is `0xCC`, so an escape traps to INT3"* — a
**soup-tier** property.  The raw tier's whole-image mode is, by §5.2 of this
document, *"random bytes over `0x0000-0xFDFF` with NO FILL"*, so it executes
where the predicate forbids **by design**.  One predicate, two tiers, written
for one of them.  And a raw seed that escapes *and* fails to terminate is
already caught, by the terminator-reached bar itself.

**THE MEASURED RATES THAT MOTIVATED FINDING IT.**  Recorded at `902ec0de17`, a
scratchpad probe over 72 corpus seeds (6 per census stratum), **on the
`tb_v30_core` leg**:

* soup **1/36 = 2.8 %**, raw **16/35 = 45.7 %**, total **17/72 = 23.6 %**
  (1 harness error).  All 17 escape addresses lay outside `0x8000-0xBFFF` and
  inside the raw band (`0x15bd` … `0xfb88`).
* On the board itself, n = 2: **1 of 2 soup seeds escaped** (`fz2c/400001`,
  `escaped_n` 2, at physical `0x123b`).

⚠ **THE 72-SEED FIGURE IS A SCALE ESTIMATE AND IS NOT AN E-1 NUMBER.**  §5.1
disqualifies `tb_v30_core` from the E-1 bar in both directions and nothing here
is quoted for or against it; on a TB leg there is no terminating NMI, so the
scan window is not cut short.  It is quoted for one purpose only: as a hard
STOP the predicate would have halted the run within a seed or two of every raw
stratum, i.e. the raw half of the corpus was **uncapturable** under it.

**WHICH REGISTERED VALUES MOVED: NONE.**  Every bar that gates is untouched,
character for character — soup ≥ 99.0 %, raw ≥ 95.0 %, UNDISPOSITIONED = 0, and
C-1 … C-11 as written.  C-1 is scored on `arch_ok` (terminator-reached) and its
disposition set, neither of which reads the escape.  The strata, the frozen
population, `SEEDS_SHA256` and `SEED_LIST_SHA256` are unmoved; `fz2_w1 lint`
still passes.  **Nothing else is demoted**: `tw_in_w0_chip`, the shared
corrupt-store `done_data_both_*`, and `mid_rst_*` are all still QUARANTINE and
still STOP.

**PROVED, NOT ASSERTED** — a stop-condition change that cannot be shown to
still stop is not a safe change.  Three legs, all offline:

* `sw/test_fuzz_classify.py` gains section 6, which asserts on one set of rows
  that the escape is still MEASURED, that it raises no alarm and no STOP and the
  seed SCORES, and that a phantom-`Tw` and a shared corrupt-store alarm on the
  same rows both still QUARANTINE **and** still return
  `('STOP', 'provenance_alarm')`.
* `sw/test_fuzz_accept.py`'s full-classify check changed its expectation from
  QUARANTINE to SCORED, with the reason written beside it.
* The seed that stopped the run was REPLAYED from its own banked rows against
  the pre-amendment module and against the tree.  The control reproduces the
  banked verdict exactly (`QUARANTINE/provenance_alarm:escaped_code_region_…`
  plus `[('STOP', 'provenance_alarm')]`); the tree returns **`SUCCESS/clean`,
  no alarms, no escalation, and `escaped_code_region` still reporting
  `(765, 4667)` with `escaped_n` 2**.  `fz2c/400000` is byte-identical before
  and after.

**THE TWO BANKED SEEDS ARE DISCARDED FROM THE CORPUS.**  They were scored under
a rule that no longer exists, and `_done_ks()` resume would otherwise carry the
superseded QUARANTINE line into the census's own rates.
`sw/testdata/campaigns/fz2c/` is therefore ARCHIVED BY RENAME to
`sw/testdata/campaigns/fz2c-prereg-A1-archive/` with this entry as its ledger
note — **nothing deleted, both raw captures retained byte for byte on disk
(`sha256` `2d9faf7570ad04d2…` and `1adfa2647d348d2f…`; campaign captures are
`.gitignore`d by design, as all of them are), nothing gating on them** — so
that whenever the census does run, it runs from
`k = 400000` under ONE rule.  (The archive-by-rename precedent is the
`w1evt-biased` one named in `CLAUDE.md`.)  ⚠ **The census was NOT re-captured in
this sitting: O-1 below blocks it.**

### O-1 — OPEN FINDING: `ps3_8080` IS TRUE ON EVERY BOARD CAPTURE, AND IT IS THE INSTRUMENT

**NO DISPOSITION IS MADE HERE.  No bar is changed, no predicate is edited, and
the capture is BLOCKED until this is ruled.**  It is recorded in this document
rather than in a commit message alone because it is a statement about what two
of this document's own bars can and cannot measure.

**WHAT WAS MEASURED.**  Both banked board seeds carry `ps3_8080: true` on their
result line.  Neither contains BRKEM (`has_brkem` false, and C-3's generation
clause is 0 forbidden `0F xx` pairs).  Reading the rows:

* on the **socket/chip** leg (`real`, `use_core=0`), a `CODE` T1's `ps` column
  is the STATUS nibble — the reset fetch at linear `0xFFFF0` reads `0x2`,
  i.e. `{md, ie, CS}` — and **0** rows in either seed set PS3;
* on the **fabric-core** leg (`sim`, `use_core=1`), the same fetch at the same
  row reads **`0xF`**, the ADDRESS nibble `A19-16`.  That is exactly the
  signature `fuzz_campaign._ps3_8080`'s own docstring attributes to the
  *Verilator TB* leg, and on whose basis it says the caller must not ask the TB.
  At T2 both legs read `0x2`, which is precisely why `diff_rows` — which
  compares `ps` at T2 only — has never had to notice.

`eval_case` asks the predicate of **both** legs (§3.4 registers it as *"on
either leg"*).  The reset fetch is present in every capture by construction and
its `A19-16` is `0xF`, so **`_ps3_8080(sim, …)` returns True unconditionally,
from row 9, for every seed of both tiers** — a property of the rig, not of the
program.  **The control is 382 archived board captures across two campaigns
(`wr1` + `fz2c`, both tiers, v1 era and v2 era): on 382 of 382 core legs the
FIRST row the predicate fires on is that reset fetch at `0xFFFF0`, with no
exceptions.**  On the same `wr1` sample the chip leg reads `0x2` there on 25 of
25 checked.

**WHAT IT WOULD DO TO THIS DOCUMENT'S BARS, IF A CAPTURE WERE TAKEN NOW.**

* C-3's runtime clause (*"0 captures showing PS3 on a `CODE` T1"*) would read
  3,840 of 3,840 and score MISSED for a reason that has nothing to do with 8080
  mode.
* **Worse, and the reason this blocks rather than merely disappoints**: C-1's
  disposition set is `arch_restart or ps3_8080 or wrote_term`.  With `ps3_8080`
  true on every line, **every** non-dumping seed is "dispositioned" and
  UNDISPOSITIONED is 0 by arithmetic.  §5.3 calls E-1c *"the clause that is not
  a rate … it bounds the unexplained residue from below, so the bar cannot be
  met by discarding"*.  It would be met vacuously — the exact failure mode it
  exists to prevent.
* §3.4 makes a `ps3_8080` seed a declared DISCARD, so under the document as
  written the entire corpus is a declared discard.

**WHY IT CANNOT BE LEFT TO BE FIXED AFTER THE CAPTURE.**  `ps3_8080` is
computed from rows, and rows are retained for 480 census seeds (the frozen
every-second-k rule) and for a quota'd subset of the enriched population.  For
the ~3,360 seeds that keep no rows the column **cannot be recomputed offline**,
so a capture taken now would have to be RE-TAKEN in full — the correctness
directive's own "fix the rig and RE-CAPTURE", paid twice.

**WHAT IS NOT DECIDED HERE.**  Whether the fix is to read the mode status where
both legs carry it (both read `0x2` at T2 of the same fetch), or to ask the
predicate of the socket leg alone, or to change what the core drives at T1, is a
DECISION about a registered bar's predicate, made after seeing data, and it
belongs to the coordinator in its own amendment — before a capture, not in a
patch after one.  Its own falsifier is already available: whichever form is
chosen must still return True on a seed that genuinely enters 8080 mode, and
`sw/timed_fuzz.native_exclusion`'s population is where such seeds exist.

### A-2 — `ps3_8080` IS ASKED OF THE SOCKET LEG ALONE; THE CORE-LEG HALF IS RETIRED

**Decided 2026-08-09, T12, BEFORE any board contact in this sitting and BEFORE
the capture.  The timing is stated first because an amendment that hides its own
timing is worse than the contradiction it settles.**  This is a COMPARATOR
decision taken on a **382-pair archived control**, not on the 2-seed board result
that surfaced it.  It disposes of finding O-1 (§11, A-1's tail), which blocked
the capture.

**WHAT CHANGED, IN ONE LINE.**  `fuzz_campaign.eval_case` computed
`ps3_8080` as `_ps3_8080(real) or _ps3_8080(sim)` — §3.4's *"on either leg"*.
It now computes it from the **socket leg (`real`, `use_core=0`) alone**.  The
predicate itself — PS3 set on a `CODE` T1 inside the window — is **not edited**:
same rows, same terms, same T-state.  The core leg's answer is still COMPUTED
and still REPORTED, on every result line, as the non-gating diagnostic
**`ps3_8080_core`** (A-1's `escaped` precedent — retired, not dropped, so the
retirement stays auditable in the bank).

**THE MEASUREMENT — BOTH ARMS, ON THE 382-PAIR CONTROL.**  The coordinator's
preferred disposition was to sample the mode status at **T2**, where the O-1
entry above observed both legs reading `0x2` on the reset fetch.  That had to be
tested, not assumed, because T1 was chosen deliberately:
`timed_fuzz.native_exclusion`'s own comment says requiring `CODE` + T1 *"avoids
treating the separately-booked retained PS3 value on a few stack writes as mode
entry"*.  Control = the **382 archived board capture pairs** named in O-1
(`wr1` 380, v1 era; `fz2c-prereg-A1-archive` 2, v2 era; both tiers).  Falsifier
population = the **`t30-brkem` bank, 116 pairs**, which is where seeds that
genuinely enter 8080 mode exist.  Tool: `sw/fz2_a2_replay.py`, checked in, board-
free, re-runnable.

| form | socket leg, control | core leg, control | socket, t30-brkem | core, t30-brkem |
|---|---|---|---|---|
| `T1+CODE` (as registered) | **99 / 382** | **382 / 382** | **87 / 116** | **116 / 116** |
| `T2+CODE` (the candidate) | **99 / 382** | **103 / 382** | **87 / 116** | **0 / 116** |

**ARM 1 — DOES A T2 SAMPLE REINTRODUCE THE NAMED FALSE POSITIVE?  NO.**  On the
socket leg the T1 and T2 forms select the **identical seed set** — 99 of 382 on
the control and 87 of 116 on the falsifier bank, set for set, with the first
firing row exactly **+1** in every one of those 186 cases.  And the retained-PS3
class the `T1` term was credited with excluding is excluded by the **`CODE`
term**, not by the T-state: over all 382 pairs the only thing `CODE` removes is
**one** seed, `wr1/219060`, whose PS3 sits on a **MEMW** cycle — and it is
removed identically at T1 and at T2.  So T1 was doing none of that work.

**ARM 2 — BUT T2 DOES NOT CLOSE O-1, AND THIS IS WHERE THE PREFERRED ARM FAILS.**
O-1's premise was that *both legs measurably read the status nibble at T2*.  It
was observed on one row — the reset fetch — of two seeds.  Over 382 pairs it is
**false**: at T2 the core leg still fires on **103 of 382**, agreeing with the
socket leg on only 96 of its 99 (7 core-only, 3 socket-only).  T2 shrinks O-1
from 382 to 103; it does not close it, and 103 of 3,840 would still be a
declared DISCARD for a reason that is not 8080 mode.

**AND THE FALSIFIER SETTLES IT.**  On the `t30-brkem` bank a T2 core-leg sample
detects **0 of 116** — while the socket leg detects **87**.  The core leg at T2
therefore has **zero measured true positives on the only population where 8080
entry is known to exist**, and 7 uncorroborated firings on the control.  Keeping
it would be keeping a false-positive-only clause.

**THE MECHANISM, AND IT IS THE SIMPLE ONE.**  Not a comparator quirk — the RTL.
`v30u_biu.sv`'s status nibble is `data_ps = {md8080, psw_ie, segc}`; `md8080` is
`v30u_eu.sv`'s `mode8080`; and `mode8080` is set **only by an `MFC` row**, on the
8080 loader / BRKEM path that is **ledger R4, unimplemented** — the RTL says so
in its own words at `v30u_eu.sv:704`, *"UNREACHABLE ON THE CURRENT STIMULUS"*.
**The ucore's status PS3 is structurally 0.**  A core-leg mode clause has nothing
to detect even in principle, which is why it reads 0/116 where truth exists, and
every PS3 it does show is the pads carrying something that is not the mode bit —
at T1 the address nibble A19-16, which is O-1.  The two legs switch the pads from
address to status **one clock apart**; that is one pin group and one clock, and
it is the same family as F53/F55's display-pin work, not a new law.

**WHY NOT "CHANGE WHAT THE CORE DRIVES AT T1".**  O-1 left that open as a third
option.  It is declined: it would be an RTL landing (Quartus receipt, re-flash,
re-validation of every fabric figure on this branch) taken to repair a clause
that, once repaired, would still detect nothing — because `md8080` is 0
regardless of when the pads present it.  It would also change the core's pin
behaviour to suit a scorer, which is the wrong direction under a silicon-match
target.

**WHY T1 AND NOT T2 FOR THE SURVIVING SOCKET CLAUSE.**  They are the same
predicate on that leg (measured above, both populations).  T1 is kept because it
is the **unchanged** form, because it is `timed_fuzz.native_exclusion`'s own form
and keeps the repo's two transcriptions of one predicate identical, and because a
gratuitous edit to a registered predicate is a second decision where none is
needed.

**WHICH REGISTERED VALUES MOVED: NONE.**  Every bar that gates is untouched,
character for character — soup ≥ 99.0 %, raw ≥ 95.0 %, UNDISPOSITIONED = 0, and
C-1 … C-11 as written.  **C-1's and C-3's text is not edited**, nor is any
threshold, stratum, seed, `SEEDS_SHA256` or `SEED_LIST_SHA256`.  What moved is
what the column `ps3_8080` *means* — one leg instead of two — and that is stated
here rather than in a patch.  Note the direction: the socket-only form
dispositions **fewer** seeds, so C-1's UNDISPOSITIONED bar and C-3's runtime
clause both get **HARDER**, never easier.  E-1c's whole purpose — *"it bounds the
unexplained residue from below, so the bar cannot be met by discarding"* — is
restored rather than traded away.

**PROVED, NOT ASSERTED.**  Three legs, all offline, all board-free:

* `sw/fz2_a2_replay.py` — the table above, re-derivable from checked-in captures,
  with five assertions including the registered falsifier (*the chosen form must
  still return True on a seed that genuinely enters 8080 mode*): **PASS, 0
  failures**, socket `T1+CODE` **87/116** on `t30-brkem`.
* `sw/t11_clientpath_gate.py` — **ALL PASS**, including L6's *"every registered
  column is ON THE LINE"* (`absent=[]`) with `ps3_8080_core` additive.
* `sw/test_fuzz_classify.py` **0 failures**, `sw/test_fuzz_accept.py` **0
  failures**, `sw/fz2_a1_replay.py` unchanged in both directions — A-1's
  disposition is not disturbed.

**WHAT THIS PREDICTS FOR THE CAPTURE, REGISTERED BEFORE IT.**  On the two banked
v2-era `fz2c` seeds the socket leg reads `ps3_8080` **false** on both (it read
`true` on both under the OR, entirely from the core leg: 39 and 15 firing rows
there, 0 on the socket leg).  With D9's unconditional `0F` scrub on every composed
image, C-3's runtime clause is expected to read **0 of 3,840**; `ps3_8080_core` is
expected to read **true on essentially every line** and to gate nothing.

---

## §12 THE T12 CAPTURE — TAKEN 2026-08-09, AND SCORED AS REGISTERED

**The capture was taken.**  FLASH #12 resident (`sof 8db6dadf5c4c…`, receipt
`27fb750f925c…`), not re-flashed.  `preflight --board` **OK** after the `fz2c`
manifest was re-created (A-1's archive-by-rename took it; the new manifest is
identical to the archived one except `gen_git`, and the flash pin is unmoved).
**3,840 seeds in 10.8 minutes of board time** — inside §6's registered ≤ 30 min
— **48 of 48 strata `written == n` with `rc = 0`, `halted: None`**, resumed by
`_done_ks()`.  `div_guard` **PINNED on 53 of 53 probes, 0 unpinned**; socket
only, `use_core=False`; **0 transport errors, 0 quarantines**; closing
`use_core=0` chip proof **MATCH over 800 rows**; `board_idle()` clean.

### 12.1 THE BARS, AS REGISTERED — 6 MET / 3 MISSED / 2 NOT SCOREABLE

| bar | verdict | measured |
|---|---|---|
| **C-1** | **MISSED** | census/soup **92.29 %** (443/480, bar ≥ 99.0) · census/raw **54.79 %** (263/480, bar ≥ 95.0) · enriched/soup **89.86 %** (1,294/1,440) · enriched/raw **51.88 %** (747/1,440); **UNDISPOSITIONED 1,048**, bar **0** |
| **C-2** | MET | 2,747 dumps, `MAGIC` constant `0x5EED`, all 14 other words ≥ 2 distinct (min `PSW` 161, `CW` 1,562); 0 flat words |
| **C-3** | **MISSED** | generation **0** forbidden `0F xx` pairs over 3,840; runtime **1** capture with PS3 on a `CODE` T1 |
| **C-4** | MET | 1 distinct era, 0 absent, 0 incomplete, `build_stale` 0, over 3,840 |
| **C-5** | MET | 0 GEN_DRIFT, 0 wvec re-derive mismatches, over all 3,840 |
| **C-6** | **NOT SCOREABLE** | the board legs do not exist on this tree (`cmd_control` is unimplemented, `fz2_control.json` absent) **and** finding O-2 below |
| **C-7** | MET | 3,840 scored, max **1,006** bus cycles, 0 at or over 4,096 |
| **C-8** | MET | **53 `div_guard` probes, 0 unpinned** |
| **C-9** | **MISSED** | **191/192 stable**, 1 unstable, 0 errors |
| **C-10** | MET | 0 quarantines, 0 run-error lines, breaker not tripped, no halted stratum |
| **C-11** | **NOT SCOREABLE** | the bank promotion was not run this sitting (`census_banked` 0 of 480) |

Decompositions, never one aggregate — census: captured 960, rows-exact
**94.9 %**, arch-exact **72.08 %**, unscoreable 261.  Enriched: captured 2,880,
rows-exact **94.34 %**, arch-exact **69.72 %**, unscoreable 860.

### 12.2 A-2 IS VINDICATED AT CORPUS SCALE, AND IT IS WHY C-1 IS READABLE AT ALL

* `ps3_8080_core` — the retired core-leg half, banked as a non-gating
  diagnostic — is **true on 3,840 of 3,840**.  O-1 reproduces exactly, at full
  scale, on the v2 corpus.
* **Under the pre-A-2 `either leg` predicate, UNDISPOSITIONED would have read
  `0`.**  Measured on these very lines: 0, not 1,048.  E-1c — *"the clause that
  is not a rate … it bounds the unexplained residue from below, so the bar
  cannot be met by discarding"* — would have been met **vacuously**, and the
  1,048-seed mechanism in §12.3 would have been invisible and **unrecoverable**,
  because rows are retained for only 480 census seeds.
* A-2's own registered prediction was *"C-3's runtime clause is expected to read
  **0 of 3,840**"*.  **It read 1.  THE PREDICTION IS MISSED**, and it is
  reported as registered rather than restated.  The seed is `fz2e/509069`
  (soup, `has_brkem` false, **0** forbidden `0F xx` pairs at generation) — i.e.
  a `0F xx` pair created at RUNTIME, which is exactly the case §6 C-3 warns
  its two clauses exist for: *"the generation clause alone cannot see a pair a
  runtime write creates."*  One seed in 3,840 on the socket leg; under the OR it
  would have been one signal inside 3,840 false positives.

### 12.3 O-2a — THE FOURTH MECHANISM, NAMED AS §5.3'S FALSIFIER DEMANDS

E-1c's registered falsifier: *"E-1c fails if any non-dumping seed carries none
of the three signatures, which means a fourth mechanism exists and must be named
before anything else is quoted."*  It fired on **1,048** seeds.  Named, from the
bank, before anything else is quoted:

**THE TERMINATOR FIRES AND IS INTERCEPTED, BUT THE DUMP DOES NOT COMPLETE
INSIDE THE 4,096-ROW CAPTURE.**

* **1,039 of 1,048 (99.1 %)** never reached the done marker (`done_real` false).
* **1,045 of 1,048 (99.7 %)** have `term.fired ≥ 4` — the terminating NMI DID
  assert — and **819 (78.1 %)** also have `term.vec_used` true, so the vector
  overlay DID intercept.  This is not a rig that failed to arm.
* `sub` is `window_truncated` **752**, `runaway_both` **164**, `open_bus` 106 —
  **916 of 1,048** on the two window classes.
* **`bus_cycles` max is 1,006** against C-7's bound of 4,096, and C-7 is MET.
  **The binding limit is the 4,096-ROW capture, not the bus-cycle bound.**
* Tier split **raw 867 / soup 181**, which matches the reached rates: raw ~52-55 %
  against soup ~90-92 %.

This points at **§3.2's `TERM_CLOCKS` budget**, not at the rig and not at any of
§3.4's three signatures: `TERM_CLOCKS = CAP_ROWS − ceil(TERM_MARGIN × (ANCHOR_W0
+ DUMP_W0) × scale)` costs the dump from w0 constants measured on **soup** seeds
and scaled by `weff`.  A raw-tier seed is not sitting at the anchor when the NMI
lands, so the entry-plus-dump cost that budget allows is not the cost it pays.
**NO DISPOSITION IS MADE HERE** — a fourth declared discard class, or a
re-derived `TERM_CLOCKS` and a re-capture, is a decision about a registered bar
and belongs to the coordinator.

### 12.4 O-2b — C-6(b) IS NOT EVALUABLE AS WRITTEN

C-6(b) reads *"every event seed's counted high-row run equals its own `hold`
± 1 clock"* — **singular**.  The instrument that supplies the evidence,
`fuzz_campaign._pin_runs`, returns **every** run on **all three** pins as a dict
of `[start, length]` lists, and says in its own docstring that picking one
*"would be answering the question in the instrument"*, because a stimulus NMI
and the terminating NMI share the wire.  `fz2_w1.cmd_bars` was written as though
it returned a scalar and evaluates `abs(dict - int)`:

```
TypeError: unsupported operand type(s) for -: 'dict' and 'int'
```

Before T12 no board capture had ever reached that line.  **The bar's text and
its own instrument were never reconciled.**

**NOT REPAIRED, AND NOTHING IS LOST.**  `cmd_bars` now DECLINES to evaluate the
clause (records the shape, reads NOT SCOREABLE) instead of crashing, so the other
ten bars can be reported; it does **not** invent a reading.  C-6's verdict is
unchanged either way — it was already NOT SCOREABLE because `cmd_control` is
unimplemented on this tree.  `term.hold_rows` is banked on **every** result line,
counted over the whole capture, so C-6(b) is fully scoreable offline whenever it
is ruled on.  For information only, and **not** offered as a score: on the
reading *"a run of length `hold` ± 1 exists on the event's own `evt_pin`"*,
**240 of 240** census event seeds satisfy it.  The corpus carries `hold = 2` on
**1,241** seeds and `hold = 300` on **679**, so §6's ≥ 2 hold values is present.

### 12.5 O-2c — C-9's ONE UNSTABLE SEED IS A FIRST-REPETITION EFFECT, SOCKET LEG ONLY

`enr/raw/stim/fix3` **k = 530060**, rows retained at
`fz2e/captures/c9/raw_530060_05b48d31db04.json.gz`, sha256
`d0f2a3282a36d970bba6c23bfe035b9185472679cc82f6909e334a0ec09d25c9`.

* **fabric leg: rep1 = rep2 = rep3, `bad` 0 on every pair.**
* **socket leg: rep2 ≡ rep3 exactly (`bad` 0)**, and rep1 differs from *both*
  identically — `bad` **3,257**, `flick` 1, first divergence row **691**.
* The **arch dump is identical across all three reps**, and `pin_int`,
  `pin_nmi`, `pin_poll_n` and `rst` are identical on **all 4,000 rows**, so the
  directive was applied identically and the divergence is not a pin.
* At row 690 both reps sit in `TW` of a waited `MEMR` at `0x72079`; rep2/rep3
  take one more wait row and complete, rep1 does not.  The stratum is **`fix3`**
  — a FIXED wait level.
* The seed's own accesses are **39 of 39 open-bus feedthrough**
  (`ob_escape.frac 1.0`).

So it is **reproducible from the second repetition onward** and the outlier is
the FIRST capture of that seed — a carry-in, not nondeterminism.  **NO
DISPOSITION IS MADE HERE.**  C-9 is reported as registered: **191/192 against a
bar of 192/192, MISSED.**
