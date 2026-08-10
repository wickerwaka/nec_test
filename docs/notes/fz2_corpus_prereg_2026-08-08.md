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
SEEDS_SHA256 = 48a0f01176fd31b77faf5d13ede719ff6afbbf49293db682e01298de8c810874
CENSUS_BANK_N = 480
C9_N = 192
C9_REPS = 3
CAP_ROWS = 4096
ANCHOR_W0 = 180
DUMP_W0 = 219
ENTRY_MAX = 463
TERM_MARGIN = 1.2

⚠ **`ANCHOR_W0`, `DUMP_W0` and `ENTRY_MAX` were CHANGED by AMENDMENT A-3
(§13), a rig-defect repair after finding O-2a.  `SEEDS_SHA256` moved with
them — every seed's `TERM_CLOCKS` is derived from them — and
`SEED_LIST_SHA256` did NOT, because the corpus is the same 3,840 seeds.
No bar moved: C-1 … C-11 keep their text and their values character for
character.**

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
| `TERM_CLOCKS` range | 2,196 … 3,154 | 1,358 … 3,154 |

⚠ **The `TERM_CLOCKS` row is A-3's (§13); before the amendment it read
`2,710 … 3,634` / `1,901 … 3,634`, and `SEEDS_SHA256` above was
`386c65fd641b84a1…`.  Every other count in this table is unchanged — the
corpus is the same 3,840 seeds.**

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

> ⚠ **SUPERSEDED IN ITS CONSTANTS BY AMENDMENT A-3 (§13), 2026-08-09.**  The
> shape of the formula stands; two of its constants were wrong and a third term
> was missing, and finding O-2a is what that cost.  §3.2 is kept verbatim below
> because A-3 is only readable against it.

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

> ⚠ **THE TWO RATE CLAUSES WERE RE-REGISTERED BY AMENDMENT A-5 (§16),
> 2026-08-09: E-1a soup **99.0 → 90.0 %**, E-1b raw **95.0 → 75.0 %**.  Both
> new values were set by user decision AFTER this corpus measured 98.54 /
> 98.89 % soup and 83.54 / 83.61 % raw, ON that same population, and NEITHER
> IS DERIVED — the arithmetic in the table below belongs to the OLD values and
> does not transfer to the new ones.  **E-1c (= 0) is UNTOUCHED.**  §5.3 is
> kept verbatim because A-5 is only readable against it.**

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

⚠ **C-1's row above is SUPERSEDED IN ITS TWO RATE VALUES by AMENDMENT A-5
(§16), 2026-08-09** — soup **≥ 90.0 %**, raw **≥ 75.0 %**, both set after
measuring 98.54 / 98.89 % and 83.54 / 83.61 % on the population they are scored
against, neither derived, and **UNVALIDATED until measured on a disjoint
population** (§16.2).  C-1's third clause, **0 UNDISPOSITIONED**, is unchanged,
and **C-2 … C-11 keep their text and their values character for character.**

⚠ **C-3's row above is SUPERSEDED IN ITS RUNTIME CLAUSE ONLY by AMENDMENT A-11
(§29), 2026-08-09** — *"0 captures with a PS3 entry"* becomes **"runtime 8080
entries are DETECTED AND DISCARDED"**, scored as the conjunction R1 ∧ R2 ∧ R3 of
§29.3.  **C-3's GENERATION clause is NOT edited** — *0 forbidden `0F xx` pairs
on every composed image* stands character for character and is MET at 3,840 /
3,840 — and **C-1, C-2 and C-4 … C-11 keep their text and their values
character for character.**  §29.0 states the timing: the runtime clause is
re-registered **after** it was missed, on the population that missed it.

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

---

## §13 AMENDMENT A-3 — `TERM_CLOCKS` IS REPAIRED, AND IT IS A RIG DEFECT, NOT A BAR

**Written 2026-08-09, AFTER the T12 capture that MISSED C-1, C-3 and C-9, and
BEFORE any board contact of this sitting.**  The timing is stated first because
it is the thing most easily read wrong: this amendment changes a constant that
sits **upstream of two bars that were missed**, and tuning such a constant until
those bars pass is fitting dressed as repair.  What protects it is written into
§13.4, and the first capture is **retained in full** (INV-2) so that the before
and after are auditable by anyone.

**NO BAR MOVES.**  C-1 … C-11 keep their text and their registered values
character for character.  E-1a (soup ≥ 99.0 %), E-1b (raw ≥ 95.0 %) and E-1c
(UNDISPOSITIONED = 0) are untouched.  This amendment changes only the **rig**:
where §12.3 named a fourth mechanism, this names its cause and repairs it, which
is the correctness directive's own clause — *"where the rig or a golden is found
defective, fix the rig and RE-CAPTURE."*

### 13.0 What the first capture produced — the before, quoted so the after is readable

`fz2_bars.json`, T12, 3,840 seeds, FLASH #12, 10.8 min of board time:

| | value |
|---|---|
| **C-1** | census/soup **92.29 %** · census/raw **54.79 %** · enriched/soup **89.86 %** · enriched/raw **51.88 %** · **UNDISPOSITIONED 1,048** |
| MET | C-2 C-4 C-5 C-7 C-8 C-10 |
| MISSED | C-1 C-3 C-9 |
| NOT SCOREABLE | C-6 C-11 |
| decompositions | census rows-exact **94.9 %**, arch-exact **72.08 %**, unscoreable 261 · enriched rows-exact **94.34 %**, arch-exact **69.72 %**, unscoreable 860 |

### 13.1 `term.fired ≥ 4` IS NOT A COUNT — it is a scheduler BITMASK, and there is no repeat firing

§12.3 reported *"1,045 of 1,048 have `term.fired ≥ 4` — the terminating NMI DID
assert"*.  The predicate is right and the phrasing invites a reading that is
wrong, and the wrong reading suggests a mechanism that does not exist.

`term.fired` is `STATUS[5:3]` (`v30ctl.ST_EVT_FIRED_S`), **one bit per
scheduler**, sticky until that scheduler disarms.  `TERM_SCHED` is **2**, so bit
2 is worth **4**, and `fired ≥ 4` means exactly *"the terminator's own scheduler
fired"* — once.  Measured over all 3,840 result lines:

| `term.fired` | seeds | meaning |
|---|---|---|
| **4** | **1,917** | terminator only — and every one of them is a `noevt` seed |
| **5** | **1,918** | stimulus (bit 0) **and** terminator — and every one has an `evt` |
| 1 | 1 | stimulus fired, terminator did not |
| 0 | 4 | neither fired |

1,920 + 1,920 by construction, and the split is exact.  **The scheduler FSM is
one-shot and the evidence says so**; nothing fired four times, and there is no
second, independent firing mechanism.  Recorded here because the artifact, not
anyone's memory of it, is the authority.

### 13.2 WHAT IS ACTUALLY WRONG — measured, in the capture's own row numbers

Instrument: **`sw/fz2_termcost.py measure`**, offline, over the **734 banked
captures** of the first sitting (480 census by the frozen rule + 254 enriched by
quota).  No board, no TB, no engine.

**(a) `ANCHOR_W0 = 145` is a POST-RESET row number subtracted from a `CAP_ROWS`
that counts from record 0.**  The board holds RESET for the first 33 records and
`check_seq.run_chip` returns `recs[rel:]`, so the TB measurement and the budget
were in different coordinate systems.  On the board the anchor's `CODE` T1 lands
at absolute row:

| | w0 | w1 | w2 | w3 |
|---|---|---|---|---|
| **soup** | **180** | 242 | 275 | 308 |
| **raw** | **180** | 242 | 275 | 308 |

A single exact value per wait level over **353 fixed-wait captures**, zero
variance, **identical in both tiers**.  A 35-row coordinate error.

**(b) `DUMP_W0 = 240` is `219` MEASURED plus `21` ESTIMATED, and the estimate is
the defect.**  The 219 is exact and stands — first `OUT 0xFE` to the done marker
is **219** at w0 (31 captures, both tiers) and **425** at w3, reproducing §3.2's
TB numbers to the clock.  The 21 stood for *"the NMI entry's two vector reads
and three pushes"*.  Measured, the NMI-assert → first-`OUT` cost over **303**
captures is:

    min 53   p50 77   p90 188   p99 357   MAX 463

**(c) THE NMI ACCEPTANCE LATENCY WAS IN NO TERM OF THE FORMULA.**  That is what
(b)'s tail is: the wait for the instruction boundary at which NMI is taken.  A
budget that allows 21 clocks for a cost whose floor is 53 has no room for it at
all.

**(d) The consequence, which is arithmetic and not bad luck.**  Tail room left
after the NMI assert, against the tail's own measured cost:

| | w0 | w1 | w2 | w3 |
|---|---|---|---|---|
| room (`4095 − f`) | **281** | 335 | 417 | **500** |
| measured tail | **273 … 279** | — | — | **499** |
| **slack** | **7 rows** | | | **1 row** |

**Every seed in the corpus ran on 7 rows of slack at w0 and 1 at w3.**  And the
proof that the budget rather than the seed is the binding limit is a censoring
argument: over the 194 captures whose requirement is fully observable,
`(anchor + tail) / scale` has a maximum of **461.1** against a reserve of
**462.0 = 1.2 × (145 + 240)**.  The distribution is **pinned at the reserve**.
Nothing above it is observable, which is exactly what right-censoring looks
like.

**(e) §12.3'S OWN GUESS IS REFUTED.**  It read *"a raw-tier seed is not sitting
at the anchor when the NMI lands, so the entry-plus-dump cost that budget allows
is not the cost it pays"*.  **The anchor row is identical in both tiers to the
clock, and so is the dump, and so is the entry floor (53 in both).**  The tiers
do not differ in dump economics at all.  What differs is the acceptance-latency
*distribution*, which is a property of what the seed is executing and not a
constant of the rig.

### 13.3 THE REPAIR — one formula, one set of constants, no tier parameter

```
scale       = (NMAX_SCALE_C + weff) / NMAX_SCALE_C
TERM_CLOCKS = CAP_ROWS
              − ceil(TERM_MARGIN × (ANCHOR_W0 + DUMP_W0) × scale)
              − ENTRY_MAX
            = 4096 − ceil(1.2 × (180 + 219) × scale) − 463
```

| constant | was | is | basis |
|---|---|---|---|
| `ANCHOR_W0` | 145 | **180** | MEASURED on the board, ABSOLUTE capture row, 353 captures, both tiers, zero variance |
| `DUMP_W0` | 240 | **219** | MEASURED, unchanged in value from §3.2's TB figure; the `+21` estimate is removed and replaced by a measured term |
| `ENTRY_MAX` | *(absent)* | **463** | MEASURED, the largest NMI-assert → first-`OUT` cost over 303 captures |
| `TERM_MARGIN` | 1.2 | **1.2** | unchanged, a stated margin |
| `TERM_FLOOR` | 512 | **512** | unchanged, and asserted per seed as before |

**Why `ENTRY_MAX` sits OUTSIDE the scaling.**  Because the measurement says it
is a **clock** cost and not a bus-cycle cost.  Its maximum shows no trend with
`scale`, and `max/scale` falls monotonically across the eight scale levels the
corpus carries:

| scale | 1.00 | 1.25 | 1.50 | 1.75 | 2.00 | 2.75 | 3.00 | 4.75 |
|---|---|---|---|---|---|---|---|---|
| max entry | 243 | 300 | 317 | 357 | 116 | **463** | 369 | 305 |
| max / scale | 243 | 240 | 211 | 204 | 58 | 168 | 123 | **64** |

**FALSIFIER, registered before the re-capture**: if the residue after this
repair concentrates at high `weff`, the term scales and this form is wrong.

**Why there is no per-tier table.**  §13.2(e).  Soup and raw are identical in
all three measured terms.  A per-tier constant set would be a fitted table with
nothing to fit — the signal the standing design principle names.  **The soup
constants are therefore not merely left standing: they were re-measured, and
they were wrong in exactly the same two ways as raw's**, which is why 181 soup
seeds sit in the 1,048 alongside 867 raw ones.

**What it costs.**  `TERM_CLOCKS` moves from `1,901 … 3,634` to
`1,358 … 3,154`; the floor of 512 holds at every `weff` the corpus uses
(0/1/2/3/7/8/15 → 3,154 / 3,034 / 2,914 / 2,795 / 2,316 / 2,196 / 1,358).  Tail
room rises from 281 → **761** at w0 and 500 → **993** at w3.  The price is that
the earlier terminator pre-empts runs that would have ended on their own:
measured on the banked captures, **10 of 351** self-terminating runs (2.8 %,
8 soup / 2 raw).  That is not a loss — the terminator's own dump still produces
the arch column — but it changes which route ended those runs and it is
registered here rather than discovered later.

### 13.4 THE REGISTERED PREDICTION — and the protections against fitting it

Derive, register, capture **once**.  `python3 sw/fz2_termcost.py predict`
reproduces every line below offline:

* Of the **383** banked captures where the terminator was actually needed
  (i.e. the run had not already dumped), **303 carry a measured requirement**
  and **303 of 303 fit in the new window** — 186 with both entry and dump
  observed, 117 more with the entry observed and the dump at its measured
  `219 × scale`.
* **80 carry no measured requirement, and NO PREDICTION IS MADE FOR THEM.**
  They are §13.5's business.
* **No bar is predicted.**  C-1's rate clauses are not forecast here, and the
  constants were not chosen by evaluating them.  The reserve was derived from
  three measurements of the rig's own tail; had it been chosen to maximise a
  rate, `ENTRY_MAX` would have been swept, and it was not — it is the observed
  maximum of a measured cost.
* **One re-capture.**  If it still misses, that is a result to report and not a
  signal to re-tune.  This paragraph exists so that a second re-tune would have
  to contradict a committed sentence.

### 13.5 O-2d — A SECOND MECHANISM, INDEPENDENT OF THE BUDGET, NAMED NOT DISPOSED

The same measurement separates the 1,048 into two populations, and only one of
them is a budget problem.  Of the **80** terminator-needed banked captures whose
dump never started:

* **49 — THE CPU HAD ALREADY STOPPED.**  The bus was idle (`PASV`, `TI`) for a
  median of **2,582 clocks** (min 276, max 3,627) *before* the terminating NMI
  arrived, and `term.vec_used` is **false on all 49**: the NMI asserts for its
  20 clocks and the part does not respond.  **43 raw / 6 soup.**  Checked on
  both legs: on **40 of 49 the socket chip and the fabric core stop at the same
  clock (±2)**, so this is the part's behaviour reproduced by both engines, not
  a rig fault and not a core divergence.  **No `TERM_CLOCKS` value reaches
  these.**
* **31 — the budget class**, bus still running at the NMI, `vec_used` true on
  29 of 31.

**No disposition is made here**, exactly as §12.3 made none: a fourth declared
discard class is a decision about a registered bar and belongs to the
coordinator.  What is registered is the expectation, so that the re-capture can
falsify it: **the undispositioned residue after this repair is expected to be
non-zero and to be dominated by this class.**  Scaled off the banked captures
(49 of the 271 non-dumping ones, 18.1 %) the order of magnitude is ~190 of the
1,039, but that is an estimate from 734 captures and **not a bar, not a
prediction of C-1, and not to be quoted as either.**

### 13.6 What A-3 changes in the tree

* `sw/fuzz_campaign.py` — the three constants and `term_clocks`.  Nothing else;
  `term_directive`, `TERM_SCHED`, `TERM_HOLD`, `TERM_PIN`, `TERM_VECSUB` and
  `TERM_TVEC` are untouched.
* `sw/fz2_w1.py` — binds `ENTRY_MAX`, lints it against this document, and
  freezes it into the population file.
* `sw/fz2_termcost.py` — **new**, the instrument.  It reads banked captures
  only.
* `docs/notes/fz2_corpus_prereg_2026-08-08.md` — §3.2's supersession note, the
  constants block, and this section.
* `SEEDS_SHA256` moves, because every seed's `TERM_CLOCKS` is derived from the
  constants.  **`SEED_LIST_SHA256` does not**: the corpus is the same 3,840
  seeds in the same order, and that is the name §2.5 says identifies it.

---

## §14 THE RE-CAPTURE — TAKEN 2026-08-09 UNDER A-3, AND SCORED AS REGISTERED

**One capture, as A-3 §13.4 registered.**  FLASH #12 resident (`sof
8db6dadf5c4c…`, receipt `27fb750f925c…`), **not re-flashed**.  Amendment A-3 was
committed at `c32b8cbb9d` and INV-2 at `e26157c296`, both before board contact.
`preflight --board` **OK** after the `fz2c`/`fz2e` manifests were re-created —
the archive-by-rename took them, exactly as A-1's did; the new manifests are
**identical to the archived ones except `gen_git` and `created`**, checked by
diff, and the flash pin is unmoved.

**3,840 seeds in 11.0 minutes of board time**, inside §6's registered ≤ 30 min.
**48 of 48 strata `written == n` with `rc = 0`, `halted: None`**, resumed by
`_done_ks()`.  `div_guard` **PINNED on 53 of 53 probes, 0 unpinned**; socket
only, `use_core=False`; **0 transport errors, 0 quarantines**; C-9 **1.4 min**;
`board_idle()` clean and **`check_ab_hw chip 800` MATCH over 800 rows** taken
after everything.

### 14.1 THE BARS, AS REGISTERED — 7 MET / 2 MISSED / 2 NOT SCOREABLE

Values are the unchanged §6 ones.  The T12 column is INV-2's and is shown only
so the delta is visible; it gates nothing.

| bar | T12 (INV-2) | **re-capture** | measured now |
|---|---|---|---|
| **C-1** | MISSED | **MISSED** | census/soup **98.54 %** · census/raw **83.54 %** · enriched/soup **98.89 %** · enriched/raw **83.61 %**; **UNDISPOSITIONED 312**, bar 0 |
| **C-2** | MET | **MET** | 3,502 dumps, `MAGIC` constant `0x5EED`, all 14 other words ≥ 2 distinct (min `PSW` 199) |
| **C-3** | MISSED | **MISSED** | generation **0** forbidden `0F xx` pairs over 3,840; runtime **2** captures with PS3 on a `CODE` T1 |
| **C-4** | MET | **MET** | 1 distinct era, 0 absent, 0 incomplete, `build_stale` 0, over 3,840 |
| **C-5** | MET | **MET** | 0 GEN_DRIFT, 0 wvec re-derive mismatches, over all 3,840 |
| **C-6** | NOT SCOREABLE | **NOT SCOREABLE** | unchanged: `cmd_control` unimplemented **and** O-2b |
| **C-7** | MET | **MET** | 3,840 scored, max **957** bus cycles, 0 at or over 4,096 |
| **C-8** | MET | **MET** | **53 `div_guard` probes, 0 unpinned** |
| **C-9** | MISSED 191/192 | **MET** | **192 / 192 stable**, 0 unstable, 0 errors |
| **C-10** | MET | **MET** | 0 quarantines, 0 run-error lines, breaker not tripped, no halted stratum |
| **C-11** | NOT SCOREABLE | **NOT SCOREABLE** | unchanged: the bank promotion was not run this sitting |

Decompositions, never one aggregate — **census**: captured 960, rows-exact
**94.38 %**, arch-exact **87.71 %**, unscoreable **95**.  **Enriched**: captured
2,880, rows-exact **94.58 %**, arch-exact **88.33 %**, unscoreable **282**.

### 14.2 WHAT THE REPAIR DID, AND THE PROOF IT IS THE REPAIR

| | T12 (INV-2) | re-capture |
|---|---|---|
| **UNDISPOSITIONED** | **1,048** | **312** (−70.2 %) |
| census/soup reached | 92.29 % | **98.54 %** |
| census/raw reached | 54.79 % | **83.54 %** |
| enriched/soup reached | 89.86 % | **98.89 %** |
| enriched/raw reached | 51.88 % | **83.61 %** |
| census arch-exact | 72.08 % | **87.71 %** |
| enriched arch-exact | 69.72 % | **88.33 %** |
| census unscoreable | 261 | **95** |
| enriched unscoreable | 860 | **282** |
| C-9 | 191/192 | **192/192** |

**THE CAUSAL PROOF IS THE CENSORING, LIFTED** (`fz2_termcost.py measure --bank
{archive,current}`).  On the archived capture, `(anchor + tail)/scale` over 194
completions maxes at **461.1** against a reserve of **462.0**, and **0 of 194**
exceed it — they could not.  On the re-capture, over 327 completions the maximum
is **828.8** and **126 of 327 carry a requirement the pre-A-3 budget could not
have recorded at all.**  The observed tail at `fix0` runs to **557** rows where
the old window ended at **281**, and at `fix3` to **934** where it ended at
**500**.  That is not an improved score; it is the same distribution, seen.

**A-3'S OWN REGISTERED PREDICTION IS MET**: all 303 banked captures with a
measured requirement were predicted to fit, and the tail-room table
(761/819/906/992 rows at w0…w3) is the one the re-capture measured.

**A-3'S FALSIFIER IS NOT MET, and it was a real test.**  §13.3 registered: *"if
the residue after this repair concentrates at high `weff`, the term scales and
this form is wrong."*  The residue by wait source is **flat** — fix0 6.7 % ·
fix1 8.8 % · fix2 5.6 % · fix3 10.0 % · wrand1 6.2 % · wrand3 7.8 % · wrand7
11.2 % · wrand15 8.4 % · wvec 8.1 % — with no trend in `weff`.  `ENTRY_MAX` as a
clock cost outside the scaling stands.

> ⚠ **FORWARD POINTER (A-6, §17.3).**  The paragraph below is right about the
> measurement and its reading of it is the wrong comparison: `ENTRY_MAX` does
> not bound `entry`, it bounds `anchor + tail + 1 − ceil(1.2 × 399 × scale)`,
> whose maximum over the same 327 completions is **438**.  The 719-clock
> capture, `fz2c/402075`, **COMPLETED**.  A-6 re-derives the constant from the
> uncensored distribution and it **does not move**.

**ONE MEASUREMENT WENT THE OTHER WAY AND IS REPORTED AS REGISTERED**: with the
censoring lifted, the observed entry cost now reaches **719** clocks against
`ENTRY_MAX = 463`.  463 was the largest value the archived capture could show;
it was not the largest that exists.  **No constant is re-tuned on that account**
— §13.4 says one re-capture, and a second sweep of `ENTRY_MAX` against a bar
that is still missed is exactly the fitting this amendment was written to
prevent.

### 14.3 C-1 IS STILL MISSED, AND O-2d IS WHY — as §13.5 registered

E-1c is still 312 against 0, and the two rate clauses still miss: raw at
**83.5 %** against 95.0 % and soup at **98.5 % / 98.9 %** against 99.0 %.
**Reported as registered, not restated.**

§13.5 registered, before the re-capture: *"the undispositioned residue after
this repair is expected to be non-zero and to be dominated by this class"*, with
an order-of-magnitude estimate of **~190**.  Measured on the re-capture's own
banked rows:

* **306 of the 312** carry a signature of the stopped-CPU class or the
  window; of the 76 terminator-needed banked captures whose dump never started,
  **44 had a bus already idle ≥ 200 clocks when the NMI arrived** (median
  **2,124**, max **3,147**), `vec_used` **false on all 44**, **39 raw / 5 soup**.
* **`vec_used` is false on 218 of the 312.**  The part never took the vector.
* The tier split is **284 raw / 22 soup**, i.e. the residue is now almost
  entirely raw whole-image — which is where a random byte stream can stop the
  part.

The estimate was **~190 and the measurement is 312**, so the estimate was low by
about 60 %; it was registered as an order of magnitude and not as a bar, and it
is wrong in the direction that says the class is bigger than the archived
capture could show — the same censoring, once more.  **NO DISPOSITION IS MADE
HERE.**  Whether O-2d becomes a fourth declared discard class is a decision
about a registered bar and belongs to the coordinator.

### 14.4 C-3 read 2, not 1 — and both are runtime, both on the socket leg

`fz2e/509069` (soup, `fix0`) reproduces from T12 exactly; `fz2e/534020` (raw,
`wrand15`, `raw_mode: payload`) is new.  **0 forbidden `0F xx` pairs at
generation on all 3,840**, so both are `0F xx` pairs a runtime write created —
the case §6's C-3 says its two clauses exist for.  A-2's arm holds: the SOCKET
leg alone, `ps3_8080_core` still gating nothing.

### 14.5 What is unchanged, and therefore still open

* **C-6 and C-11 are NOT SCOREABLE for the same two reasons as T12** —
  `cmd_control` is unimplemented on this tree (C-6), O-2b's dict-vs-scalar
  clause awaits a ruling (C-6(b)), and the bank promotion was not run this
  sitting (C-11).  Neither was touched, and neither should be read as improved.
* The acceptance criterion of §8.2 is **not met**: four bars are not MET and the
  catch-all is not empty.

---

## §15 AMENDMENT A-4 — A FOURTH DECLARED DISCARD CLASS: THE PART STOPPED BEFORE THE TERMINATOR ARRIVED

**Written 2026-08-09, AFTER the §14 re-capture that MISSED C-1, and COMMITTED
BEFORE the rescore it enables.**  Appended, never back-edited.  This is the
coordinator's disposition of O-2d (§13.5), which named the mechanism and
deliberately made no disposition of it.

**NO BAR MOVES.**  C-1 … C-11 keep their text and their registered values
**character for character** — soup **≥ 99.0 %**, raw **≥ 95.0 %**,
UNDISPOSITIONED **= 0**, and every other bar exactly as §6 wrote it.  What
changes is §3.4's list of declared discard classes: **three become four.**

### 15.0 THE TRAP THIS AMENDMENT IS WRITTEN AGAINST

C-1's disposition set is `arch_restart or ps3_8080 or wrote_term`, and
**adding a fourth term makes UNDISPOSITIONED fall by construction.**  That is
the exact shape amendment A-2 exists to prevent: there, `ps3_8080` fired on
3,840 of 3,840 and would have driven the count to **0 vacuously**, and only a
measured control caught it.  So this class is admitted under four conditions,
all of them met and reported below:

1. the detector is **independent of the thing it explains** and is computed
   from the SOCKET leg's own rows — not "the model stalls" (that predicate
   was measured firing on **96 seeds that DID reach the terminator** and is
   not used here in any role), and not "no dump", which is circular;
2. a **HARD FALSIFIER, run**: the detector must fire on **ZERO** captures
   that reached the terminator, over the whole corpus, both campaigns;
3. **no other bar moves**, and C-1's two rate clauses keep their text and
   values character for character;
4. the rescore is reported **BOTH WAYS**, with and without the class, so the
   delta it buys is visible rather than absorbed.

### 15.1 THE DETECTOR

`fuzz_campaign.stall_evidence` is the definition; `sw/fz2_stall.py` is its
falsifier and its census, and no second copy of the predicate exists anywhere.
On the **SOCKET leg's own rows**, let `f` be the row the terminating NMI
asserts (the unique `pin_nmi` run of length `TERM_HOLD` — `fz2_termcost`'s own
identification; a stimulus NMI holds 2 or 300 and is a different run) and
`last` the last non-`PASV` row before `f`.  **`stalled` is TRUE iff all three
hold:**

| clause | what it says | why it is there |
|---|---|---|
| **(1) NOT A HALT** — `last.bs != HALT` | the bus did not go quiet on a HALT announcement | a HALTed part is **asleep, not stopped**, and the NMI wakes it; §87.A's illegal-form stall drives **no HALT status at all**.  Leaving HALT out is what stops this class from swallowing plan **D3's own subject** — an unwoken HALT is a FINDING about the backstop and must stay visible as UNDISPOSITIONED |
| **(2) STOPPED BEFORE THE TERMINATOR** — `f - last.idx ≥ STALL_IDLE = 200` | the bus was already quiet when the pin went high | whatever stopped the part happened **before** the terminator was scheduled, not because of it.  Clauses (1) and (2) read **PRE-NMI rows only** and are causally prior to everything the terminator does |
| **(3) STILL STOPPED AFTER IT** — not one non-`PASV` row at or after `f` | the NMI asserts for its 20 clocks and the part issues **no bus cycle at all** — not a vector read, not a push | strictly **stronger** than "no dump": of the not-reached captures this class does NOT take, **every one has post-NMI bus activity**, so the clause **partitions** the failures rather than restating them |

**The threshold is not what makes the falsifier pass** — clause (3) alone
fires on 0 of 1,114 terminator-reached captures — and it is not fitted: the
longest non-HALT pre-NMI idle on a capture that DID reach the terminator is
**213** clocks over both banks, and the shortest idle this class carries is
**276**.  200 sits below that gap and is stated, not tuned.  It earns its
place by **withholding** three otherwise-qualifying seeds (idle 11, 32, 61
clocks with a dead post-NMI bus) whose stop cannot be told apart from the
terminator's own arrival; they stay UNDISPOSITIONED.

**Why it is a DISCARD and not a failure**: no `TERM_CLOCKS` value reaches a
part that has already stopped, and no capture-side repair can.  This is not
the budget class A-3 repaired — those seeds' buses are still running when the
NMI lands — and it is not a containment failure, because nothing escaped.

### 15.2 THE FALSIFIER — RUN, AND REPORTED

`python3 sw/fz2_stall.py falsify`, over **every banked capture in both
campaigns**, in the live corpus and in INV-2's archived one:

| bank | campaign | terminator-REACHED captures | **detector fires on** |
|---|---|---|---|
| current | `fz2c` | 458 | **0** |
| current | `fz2e` | 201 | **0** |
| archive | `fz2c-INV2-archive` | 354 | **0** |
| archive | `fz2e-INV2-archive` | 101 | **0** |
| | **total** | **1,114** | **0 — PASS** |

For contrast, on captures that did NOT reach the terminator it fires on
**44 / 73** (current) and **49 / 279** (archive).  `not evaluable` is **0** in
both banks.  The two halves separately, so the reader can see which clause
does the work: clauses (1)+(2) alone — **pre-NMI rows only** — fire on **1** of
659 reached in the current bank (`fz2c/407014`, idle 213) and **0** of 455 in
the archive; clause (3) alone fires on **0** of 1,114.

### 15.3 THE POSITIVE HALF — A STALLED SEED IS NOT A SEED THAT CONTRIBUTED NOTHING

The chip and the fabric core agreeing on the **park clock** is a real
chip-vs-core match on a real mechanism, so the evidence is **banked with the
discard, not thrown away with it**.  `stalled_at` carries the core leg's own
measurement on every such line, and `python3 sw/fz2_stall.py census` reports
it: on the current bank both legs have rows on **44 of 44**, the core stops
under the identical detector on **38 / 44**, and it parks on the **SAME CLOCK
to the clock on 35 / 44** (archive: 43 / 49 and **40 / 49**).  A discard that
discarded this would be a worse instrument than the one it replaced.

### 15.4 ITS OWN TIMING, AND THE MEASUREMENT LIMIT IT CANNOT ARGUE PAST

**This class is being added after a capture that missed C-1**, and that is
stated rather than hidden.  Its protections are §15.0's four conditions, the
falsifier of §15.2, and the both-ways reporting of §15.5.

**Only 67 of the 312 undispositioned seeds can be classified at all.**  The
other **245** carry verdict `SUCCESS`, and `fuzz_campaign` banks rows only for
divergent / keep-rows / ballast captures, so there are no rows to ask.  **They
stay UNDISPOSITIONED and are NOT extrapolated into the class** — an
unclassifiable seed is undispositioned, and that is the honest reading.  The
bar's `classified_from` field reports the three populations (`line`, `rows`,
`none`) on every run so this can never be read off as a rate.

**THE DURABLE FIX, LANDED WITH THIS AMENDMENT**: the detector is computed **at
capture time**, while the rows are in hand, and banked on the result line as
`stalled` + `stalled_at`.  A future capture classifies itself and needs no
retained rows.  `fz2_w1.REQUIRED_LINE_FIELDS` now names both columns, so the
preconditions check refuses a capture whose path would not produce them —
checked before board time, the way §7 checks everything else.

### 15.5 THE RESCORE, BOTH WAYS — the before/after, so the delta is auditable

Measured on the §14 re-capture's own banked results by
`python3 sw/fz2_w1.py bars`, three-class figure beside four-class:

| | **3 classes (as §14 scored it)** | **4 classes (A-4)** | stalled |
|---|---|---|---|
| census / soup | 7 | **2** | 5 |
| census / raw | 75 | **48** | 27 |
| enriched / soup | 15 | **15** | 0 |
| enriched / raw | 215 | **204** | 11 |
| **UNDISPOSITIONED** | **312** | **269** | **43** |

**C-1 IS STILL MISSED.**  The two rate clauses are untouched by this amendment
and still miss — census/raw **83.54 %** and enriched/raw **83.61 %** against
**95.0 %**, census/soup **98.54 %** and enriched/soup **98.89 %** against
**99.0 %** — and E-1c is **269 against 0**.  Reported as registered, not
restated.  **The class buys 43 seeds of the 312, which is 13.8 %, and it is
bounded above by 67 — the number that can be classified at all.**  One seed
(`fz2c/406016`) is both `wrote_term` and stalled and is counted once, by the
existing class, exactly as the other three overlap.

### 15.6 WHAT A-4 CHANGES IN THE TREE

* `sw/fuzz_campaign.py` — `STALL_IDLE`, `BS_HALT`/`BS_PASV`, `stall_evidence`,
  and the two new result-line columns.  **No bar, no constant of A-3's, and no
  part of the capture path is touched.**
* `sw/fz2_stall.py` — **new**: the falsifier, the census, and the backfill
  that classifies a pre-A-4 capture out of its banked rows.  It reads banked
  captures only — no board, no TB, no engine.
* `sw/fz2_w1.py` — C-1's disposition set gains the fourth term; the bar now
  reports `undispositioned_3class`, `stalled_total` and `classified_from`
  beside it, permanently.  `REQUIRED_LINE_FIELDS` gains the two columns.
* This document, appended.

`SEEDS_SHA256`, `SEED_LIST_SHA256` and the corpus itself **do not move**: not
one seed, image, vector or constant changed.

### 15.7 THE RESCORE AS RUN — `sw/testdata/fz2/fz2_bars.json`, 2026-08-09T15:44:39Z

§15.5's table was registered from the same code before the scorer was run;
this is the scorer's own output, and it agrees with it seed for seed.

**`FZ2 BARS: 7/11 MET   NOT MET: C-1, C-3, C-6, C-11`** — the identical
7 MET / 2 MISSED / 2 NOT SCOREABLE of §14.1.

| | 3 classes | **4 classes** |
|---|---|---|
| census/soup undispositioned | 7 | **2** (stalled 5) |
| census/raw | 75 | **48** (stalled 27) |
| enriched/soup | 15 | **15** (stalled 0) |
| enriched/raw | 215 | **204** (stalled 11) |
| **total** | **312** | **269** |
| `classified_from` | | `rows` **67**, `none` **245** |

**NO OTHER BAR MOVED, and this is checked rather than asserted**: the new
`fz2_bars.json` is compared field for field against the one §14 committed, and
**C-1's `measured` is the only object in the file that differs.**  Every other
bar's `verdict`, `measured` and `registered` text, both populations' three
decompositions (census rows-exact **94.38** / arch-exact **87.71** /
unscoreable **95**; enriched **94.58** / **88.33** / **282**) and
`seed_list_sha256` are **identical**.

**C-1 REMAINS MISSED** on all three of its clauses: census/raw **83.54 %** and
enriched/raw **83.61 %** against **95.0 %**; census/soup **98.54 %** and
enriched/soup **98.89 %** against **99.0 %**; E-1c **269** against **0**.  The
two rate clauses did not move by a hundredth — the class disposes seeds, it
does not make them reach the terminator, and nothing in A-4 could have changed
a rate.

### 15.8 WHAT A-4 DOES NOT SETTLE — the 245, and the coordinator's call

**269 is not 43 short of the bar; it is 202 short of what these rows can even
speak to.**  Of the 269 still undispositioned, **24** were classified and
genuinely carry none of the four signatures (20 are A-3's budget class with the
bus still running and the vector taken; 3 stopped too close to the NMI to
attribute; 1 is a HALT that took the vector and did not dump), and **245**
could not be asked at all.

> ⚠ **THE PARENTHESIS IS SUPERSEDED BY A-6 (§17.0), MEASURED SEED FOR SEED ON
> THE SAME ROWS.**  The 24 are **16** `LONG_INSN` (the part is inside one
> block-transfer instruction that outlives the capture — no budget reaches it),
> **2** `WINDOW` + **1** `FORGED_DONE` (two INSTRUMENT defects, complete dumps
> the scorer could not see), **1** genuine `BUDGET`, **3** `NEAR` (A-4's
> withheld, unchanged) and **1** catch-all.  **The budget class is one seed, not
> twenty**, and the "HALT that took the vector and did not dump" **dumped** —
> it is the `FORGED_DONE` seed, `fz2e/529009`.

A re-capture of the corpus with `--keep-rows` on every seed would classify
those 245 — **the cost, and the decision, are the coordinator's** and are
stated in the sitting report, not taken here.  **No board was contacted for
this amendment**: every figure in §15 is read off banked captures and banked
result lines, offline.

---

## §16 AMENDMENT A-5 — THE TWO RATE CLAUSES ARE RE-REGISTERED BY USER DECISION: SOUP **99.0 → 90.0 %**, RAW **95.0 → 75.0 %**

**Written 2026-08-09, AFTER the §15.7 rescore that MISSED C-1 on all three of
its clauses, and COMMITTED BEFORE the rescore it enables.**  Appended, never
back-edited.  Amendments A-3 and A-4 both opened by asserting that **no bar
moves**.  **This one moves two**, and everything below exists so that a reader
in six months can decide for themselves what the resulting numbers are worth.

### 16.0 THE TIMING, STATED FIRST — THIS IS THE THING THAT DECIDES WHETHER THESE NUMBERS MEAN ANYTHING

**Both new values were chosen AFTER seeing the measurement, ON the population
that produced it, and NEITHER IS DERIVED FROM ANY MECHANISM.**

| clause | registered by §5.3 | **measured on THIS corpus (§15.7)** | **re-registered by A-5** |
|---|---|---|---|
| **E-1a soup** | **≥ 99.0 %** | census/soup **98.54 %**, enriched/soup **98.89 %** | **≥ 90.0 %** |
| **E-1b raw** | **≥ 95.0 %** | census/raw **83.54 %**, enriched/raw **83.61 %** | **≥ 75.0 %** |
| **E-1c undispositioned** | **= 0** | **269** | **= 0 — UNTOUCHED** |

The user's instruction was *"Lets set the bar to 75% and proceed"*, extended to
*"Also set the soup clause to 90%"*.  That is the whole provenance of both
numbers.  It is a **decision**, and it is implemented in full — but it is not a
finding, not an expectation, and not an arithmetic.

Contrast §5.3, which is what a derived bar looks like: 99.0 came from a
measured 0.25 MEMW/run into the code region and 0 into the terminator page,
giving an expectation of ≈ 99.9 %; 95.0 came from 70 terminator bytes in a
16 KB region at 9.7 MEMW/run, giving 1 − (1 − 70/16384)^9.7 ≈ 4.1 % leak and an
expectation of ≈ 95.9 %.  **Each old value was set below a computed expectation
and could be missed — and both were.**  **90.0 and 75.0 have no such sentence
behind them and none is offered.**  No attempt has been made to construct one:
a mechanism invented after the fact to land on a number already chosen would be
a fitted rule, which is exactly the signal the standing design principle names.

### 16.1 §64.1 IS THE GOVERNING PRECEDENT, AND IT IS WHY THE VERDICT CARRIES A MARKER

`ucore_provenance.md` §64.1, written after Codex found this pattern in H1's
re-key: **a refuted key's REPLACEMENT must be validated on data that was not
used to select it.**  Rejecting a pre-registered candidate on a directed
capture is what pre-registration is for; choosing its successor by scanning the
same capture and then scoring the successor on that capture is **fitting, and
the score is not evidence.**

Both re-registered clauses are in exactly that position.  So:

> **C-1's verdict carries an explicit `rate clauses UNVALIDATED -- A-5` marker
> whenever the two rate clauses read MET, and the marker stays until they have
> been measured on a DISJOINT population.  A bare `MET` on the selecting
> population is what §64.1 forbids, and `fz2_w1.py` will not print one.**

**Neither 90.0 % nor 75.0 % is quotable as a ratchet until that measurement
exists.**  Not in a commit message, not in `standing_gates.md`, not in
`CLAUDE.md`'s quick reference, not as "C-1's rate clauses are MET".

### 16.2 WHAT WOULD VALIDATE THEM — stated now, so it cannot be chosen later to suit the answer

A **disjoint population**: a k-block of this generator's seeds that is **not**
one of the 3,840 in `SEED_LIST_SHA256`, drawn from the same strata by the same
frozen rule, and **captured on the board before its terminator-reached rate is
looked at**.  Registered in advance:

* **size ≥ 480 seeds**, the census population's own size, split across both
  tiers so each clause is scored on its own mechanism (§5.2 — one number for
  two tiers is either vacuous for soup or a bar on a route raw does not have);
* **0 seed overlap** with either banked bank, checked the way C-11 checks it;
* the clauses scored **as written here**, 90.0 and 75.0, with **no further
  adjustment** — a second re-registration after seeing a second population
  would make this document a record of fitting rather than of deciding.

**Until then the honest reading of a MET on either rate clause is: "the bar was
placed below the number after the number was known."**

### 16.3 WHAT DOES NOT MOVE

* **E-1c stays at `= 0`.**  It is measured at **269** and it is **UNTOUCHED**.
* Every other bar — C-2 … C-11 — keeps its text and its value **character for
  character**.
* No seed, image, vector, wait vector or constant moves.  `SEEDS_SHA256` and
  `SEED_LIST_SHA256` do not move.  The generator, the detector, the capture
  path and A-4's four discard classes are not touched, and **nothing is
  re-captured** — this amendment cannot change a measured rate by a hundredth
  and does not try to.

### 16.4 THE CONSEQUENCE — C-1 IS STILL MISSED, AND NOW FOR EXACTLY ONE REASON

After A-5 the two rate clauses **both pass on both populations**:
soup 98.54 / 98.89 ≥ 90.0, raw 83.54 / 83.61 ≥ 75.0.  **E-1c does not**, at
**269 against 0**.

> **C-1 READS `MISSED`.  A-5 DID NOT RESOLVE IT.**  What A-5 changed is *what
> C-1 means*: before, it was missed on all three clauses; now it is missed on
> **one**, and that one is the **UNDISPOSITIONED** count.  **E-1c is the sole
> remaining blocker.**

### 16.5 WHY E-1c IS NOT THE SAME KIND OF CLAUSE AS THE TWO THAT MOVED

§5.3 says it in its own words — E-1c is *"the clause that is **not a rate** …
it bounds the unexplained residue from below, so the bar cannot be met by
discarding."*

The two rate clauses bound the **discard fraction from above**.  E-1c is the
**anti-vacuity floor**: it is the clause that stops the other two from being
satisfied by explaining seeds away, and it is the reason A-4's fourth discard
class had to arrive with a hard falsifier and a both-ways table (§15.0)
instead of simply lowering a residue.  **Lowering a rate makes a bar easier to
clear; lowering E-1c would remove the thing that makes clearing it mean
anything.**  Those are not the same act.  **It has not been asked for, and this
amendment does not touch it.**

### 16.6 AN OBSERVATION ABOUT THE TWO NUMBERS, RECORDED AS AN OBSERVATION

Both new bars sit **≈ 8.5 points below their measured values** — and on the
census population, **8.54 points below both, exactly**:

| | measured (census) | new bar | margin | measured (enriched) | margin |
|---|---|---|---|---|---|
| soup | 98.54 % | 90.0 % | **8.54** | 98.89 % | 8.89 |
| raw | 83.54 % | 75.0 % | **8.54** | 83.61 % | 8.61 |

This symmetry is **a fact about how the numbers were chosen, not a derivation**,
and it is recorded here so that nobody later mistakes it for one.  It is in
fact the clearest available evidence that both bars were placed **relative to
the measurement** rather than relative to a mechanism — which is precisely what
§16.0 states and §16.1 marks the verdict for.

### 16.7 WHAT A-5 CHANGES IN THE TREE

* `sw/fz2_w1.py` — the `E1` dict's two values (with the old ones kept in the
  comment beside them); C-1's `registered` string, which now carries the
  before/after and the UNVALIDATED qualifier **in the scored artifact itself**;
  and the verdict's A-5 marker.  The `NOT SCOREABLE` branch's duplicate of the
  registered text, which had the old values hard-coded, now reads them from
  `E1` so it cannot go stale again.
* This document, appended, plus a forward pointer at §5.3 and §6.
* **No other file.**  No board, no flash, no Quartus, no re-capture.

### 16.8 THE RESCORE AS RUN — `sw/testdata/fz2/fz2_bars.json`, 2026-08-09T16:01:27Z

`python3 sw/fz2_w1.py bars`, offline, off the same banked results §15.7 scored.
**No capture, no re-capture, no board.**

**`FZ2 BARS: 7/11 MET   NOT MET: C-1, C-3, C-6, C-11`** — the identical
7 MET / 2 MISSED / 2 NOT SCOREABLE of §14.1 and §15.7.  **A-5 moved no bar's
verdict.**

C-1, clause by clause, **as registered**:

| clause | measured | bar (A-5) | | prior bar (§5.3) |
|---|---|---|---|---|
| census / soup | 473/480 = **98.54 %** | ≥ 90.0 % | **MET** | ≥ 99.0 % (missed) |
| enriched / soup | 1424/1440 = **98.89 %** | ≥ 90.0 % | **MET** | ≥ 99.0 % (missed) |
| census / raw | 401/480 = **83.54 %** | ≥ 75.0 % | **MET** | ≥ 95.0 % (missed) |
| enriched / raw | 1204/1440 = **83.61 %** | ≥ 75.0 % | **MET** | ≥ 95.0 % (missed) |
| **E-1c UNDISPOSITIONED** | **269** | **= 0** | **MISSED** | = 0 — **UNTOUCHED** |

> **VERDICT: `MISSED (rate clauses UNVALIDATED -- A-5)`.**  Both marks are load
> bearing.  **MISSED** because E-1c is 269 against 0 — **A-5 did not resolve
> C-1**, it reduced it from three failing clauses to one.  **UNVALIDATED**
> because the four MET cells above are scored against bars that were set after
> those four numbers were read, on those four numbers' own population (§16.0),
> and under §64.1 that is not evidence for the bars.  **E-1c is now C-1's SOLE
> blocker**, and it is the one clause of the three that A-5 did not touch.

**NOT ONE OTHER FIELD MOVED, and this is checked rather than asserted.**  The
new `fz2_bars.json` was compared **leaf for leaf** against the one §15.7
committed: **3 differing leaves in the whole file**, and they are

* `bars/C-1/registered` — the bar text, now carrying the before/after and the
  UNVALIDATED qualifier inside the scored artifact itself;
* `bars/C-1/verdict` — `MISSED` → `MISSED (rate clauses UNVALIDATED -- A-5)`;
* `ts` — the run stamp.

**`bars/C-1/measured` is byte-identical**, object for object, including every
`pct`: A-5 cannot move a measured rate and did not.  Every other bar's
`verdict`, `measured` and `registered`, both populations' three decompositions
(census **94.38** / **87.71** / **95**; enriched **94.58** / **88.33** /
**282**) and `seed_list_sha256` are **identical**.  A-4's figures also stand
unchanged: `undispositioned_3class` **312**, `stalled_total` **43**,
`classified_from` `rows` **67** / `none` **245**.

`python3 sw/fz2_w1.py lint` **PASS, 0 hits, 48 stratum rows**.  `bars` exits
**1**, as it must while any bar is unmet.

### 16.9 WHAT A-5 DOES NOT SETTLE

1. **E-1c, at 269 against 0** — and §15.8's reading of it is undisturbed: 269
   is not 269 short of an explanation, because **245 of them cannot be asked at
   all** (verdict `SUCCESS`, no banked rows).  Only **24** were classified and
   genuinely carry none of the four signatures.  The re-capture with
   `--keep-rows` that would classify the 245 remains the coordinator's call.
2. **The two rate clauses' own validity.**  They read MET on the population
   that set them.  §16.2 says what would change that, and until it is run the
   correct sentence is *"the bar was placed below the number after the number
   was known"* — not *"containment meets its bar."*

### 16.10 ERRATUM — the `ts` §16.8 first quoted was one run stale

As first committed, §16.8's heading quoted **`2026-08-09T16:00:50Z`** while the
artifact committed alongside it carried **`2026-08-09T16:01:27Z`**.  Cause:
`bars` was run **twice** — once for the scored output, then again to confirm
its **exit code 1** — and the second run rewrote `fz2_bars.json` with a fresh
stamp.  Corrected forward, recorded not tidied, per the T10 erratum precedent.

**Nothing else in §16.8 is affected, and this was checked rather than assumed**:
the **committed** artifact was re-diffed leaf for leaf against §15.7's and
differs in exactly the same **three** leaves — `bars/C-1/registered`,
`bars/C-1/verdict`, `ts`.  The two runs therefore agree on **every field but
the stamp**, which is also the only reproducibility evidence this rescore has
and is worth having: the scorer is deterministic over the banked results.

---

## §17 AMENDMENT A-6 — THE 269 ARE MEASURED, NOT ESTIMATED: **ONE MECHANISM (M-1) AND TWO INSTRUMENT DEFECTS (D-1, D-2)**, AND `ENTRY_MAX` IS RE-DERIVED AND **DOES NOT MOVE**

**Written 2026-08-09/10, AFTER A-5, and COMMITTED BEFORE ANY BOARD CONTACT OF
THIS SITTING.**  Appended, never back-edited.

**NO BAR MOVES.**  C-1 … C-11 keep their text and their values character for
character, including A-5's re-registered rate clauses and **E-1c = 0, which is
untouched**.  **NO NEW DISCARD CLASS IS CREATED.**  A-4's four classes are
still the whole disposition set, and `fz2_w1.py bars` still reads
`arch_restart or ps3_8080 or wrote_term or stalled` and nothing else.

**NO SEED, IMAGE, VECTOR, WAIT VECTOR OR CONSTANT MOVES.**  `ENTRY_MAX` stays
**463** — §17.3 is its re-derivation, and the re-derivation returns the value
it started with — so `TERM_CLOCKS` is unmoved, so `SEEDS_SHA256` and
`SEED_LIST_SHA256` are unmoved, and `fz2_w1.py lint` passes against the frozen
population file with no re-freeze.  **The re-capture §17.7 registers is
therefore a REPEAT of the same directive on the same 3,840 seeds**, which is
the strongest form this comparison can take.

### 17.0 WHAT WAS ASKED, AND WHAT THE ARTIFACT SAID BACK

§15.8 characterised the 269 as *"20 are A-3's budget class with the bus still
running and the vector taken; 3 stopped too close to the NMI to attribute; 1 is
a HALT that took the vector and did not dump"*, plus **245 that could not be
asked**.  Measured off the same banked rows, seed for seed, **that
characterisation is wrong in its main term**, and the corrected one is below.
The 24 are:

| what §15.8 said | what the rows say | n |
|---|---|---|
| "20, A-3's budget class" | **M-1 `LONG_INSN`** — the part is inside ONE instruction that outlives the capture | **16** |
| | **D-1 `WINDOW`** — a COMPLETE dump the scorer's window cannot see | **2** |
| | **D-2 `FORGED_DONE`** — a COMPLETE dump a forged done marker truncates | **1** |
| | **`BUDGET`** — genuinely ran out mid-dump | **1** |
| "3 stopped too close to the NMI" | **`NEAR`** — A-4's three withheld seeds, unchanged | **3** |
| "1 HALT that took the vector and did not dump" | it **DID** dump — it is the D-2 seed, `fz2e/529009` | *(counted above)* |
| | catch-all, genuinely unexplained (`fz2c/405062`) | **1** |
| | **total** | **24** |

**The budget class is ONE seed of 732 banked captures, not twenty.**  Everything
else that was being read as a budget failure is either a mechanism no budget
reaches or an instrument that could not see a dump that was already there.

### 17.1 THE INSTRUMENT — `fuzz_campaign.term_mechanism`, and it dispositions NOTHING

ONE function, applied in ONE fixed order, and **every label is either an
existing function's answer or the absence of a bus cycle**.  There is no new
threshold (`STALL_IDLE` is A-4's, unchanged), no tier parameter and no
per-opcode anything.  Its docstring is the definition; `sw/fz2_termcost.py
mechanism` is the backfill over banked captures and owns no second copy.

> **IT IS A CENSUS, NOT A CLASS.**  `fz2_w1.py bars` does not import it.  A seed
> labelled `LONG_INSN` is **UNDISPOSITIONED** and counts against E-1c exactly as
> it did before this amendment.  What changes is that it can be NAMED.

`REACHED` is deliberately computed on the **PRE-A-6** window, so that D-1's and
D-2's repairs appear as their own labels instead of being absorbed into
`REACHED` — the repair stays auditable in the census that measures it.

**THE CENSUS, over every banked capture in both campaigns** (`python3
sw/fz2_termcost.py mechanism --bank all`):

| label | current (`fz2c`+`fz2e`) | soup / raw | archive (INV-2) | soup / raw |
|---|---|---|---|---|
| `REACHED` | **659** | 307 / 352 | 455 | 263 / 192 |
| `WINDOW` (D-1) | **3** | 0 / 3 | **77** | 19 / 58 |
| `FORGED_DONE` (D-2) | **1** | 0 / 1 | 0 | — |
| `BUDGET` | **5** | 1 / 4 | 131 | 23 / 108 |
| `LONG_INSN` (M-1) | **16** | 0 / 16 | 18 | 0 / 18 |
| `STALLED` (A-4) | **44** | 5 / 39 | 49 | 6 / 43 |
| `NEAR` | **3** | 0 / 3 | 1 | 0 / 1 |
| `OTHER` | **1** | 1 / 0 | 3 | 1 / 2 |
| **total** | **732** | | **734** | |
| **not evaluable** | **0** | | **0** | |

The archive column is INV-2's, taken under the pre-A-3 budget; it gates nothing
and is shown because it is what the same instrument says about a capture whose
budget was known to be short — `BUDGET` 131 there against **5** here is A-3's
repair, seen a second way and by a different instrument.

### 17.2 M-1 — THE PART IS INSIDE ONE INSTRUCTION THAT OUTLIVES THE CAPTURE

**This is the mechanism, and it is one sentence: NMI recognition happens at an
instruction boundary, a block-transfer instruction is ONE instruction, and its
iteration count came out of the same random bytes as its opcode.**

The evidence, on the socket leg's own rows, over all 16 (`fz2c/406063` quoted
because it is the median of them, not the extreme):

* **Not one CODE fetch at or after the terminating NMI**, and none for **1,696
  clocks before it** either.  The part has not started an instruction in that
  whole span; it is still finishing one.
* The post-NMI bus is **MEMR and MEMW only**, in equal numbers, at a **constant
  stride** — `−2` per access, or the `+1 / −3` alternation that is one
  descending word split into two byte cycles.  That is a block transfer with
  `DF = 1`, reading one segment and writing another.  No CODE, no INTA, no I/O.
* **`LOCK` is never asserted** (`lock_n` = 1 on every one of the 762 post-NMI
  rows), so this is not the 8086 `LOCK`-prefix interrupt-inhibit story.
* **No vector read happens in the capture at all** — no MEMR anywhere below
  `0x40` after the NMI — **and `term.vec_used` is TRUE on all 16.**  The rig's
  own sticky bit says the overlay served a CS half, and `nec_bus.sv` sets it
  only on a real `vec_hit_cs`.  Both are true because the run continues after
  the 4,096-record capture buffer has filled: **the NMI IS taken, after the
  last row.**  `vec_used` is not lying and the rows are not lying; they are
  answering about different intervals.

  ⚠ **§14.3's *"`vec_used` is false on 218 of the 312 — the part never took the
  vector"* does not invert.**  A `vec_used` of TRUE does **not** mean the vector
  was taken inside the capture, and on this class it means the opposite of what
  it reads like.  Recorded so nobody re-derives the wrong direction from it.

**NO `TERM_CLOCKS` VALUE REACHES THIS CLASS, AND NO `ENTRY_MAX` DOES EITHER.**
The capture is 4,096 records deep.  One block transfer can iterate up to 65,535
times, and at the corpus's own wait levels each iteration is tens of clocks —
hundreds of thousands of clocks for one instruction.  Firing the terminator
earlier does not help: it only moves the pin edge, which is latched and served
later regardless.  This is the same shape as A-4's stalled class — *the part is
not where the budget assumes it is* — and it is **NOT** proposed as a fifth
discard class here.  §17.6 says why that decision is not this document's.

### 17.3 `ENTRY_MAX`, RE-DERIVED FROM THE UNCENSORED DISTRIBUTION — AND IT DOES NOT MOVE

§14.2 recorded, correctly and as registered, that *"the observed entry cost now
reaches 719 clocks against `ENTRY_MAX = 463`"*, and A-3 declined to re-tune
because 463 was the largest value the CENSORED archive could show.  The
censoring is lifted, so the re-derivation is owed.  **Here it is, and it returns
463.**

**719 is not the quantity the constant bounds.**  The formula is

```
    TERM_CLOCKS = CAP_ROWS − ceil(TERM_MARGIN × (ANCHOR_W0 + DUMP_W0) × scale) − ENTRY_MAX
```

so a capture completes iff `anchor + tail + 1 ≤ ceil(1.2 × 399 × scale) + ENTRY_MAX`.
Define, per capture, **the `ENTRY_MAX` that capture actually required**:

```
    need = anchor + tail + 1 − ceil(TERM_MARGIN × (ANCHOR_W0 + DUMP_W0) × scale)
```

`need` is smaller than `entry` because `TERM_MARGIN` is **multiplicative on
(anchor + dump)** and its surplus grows with `scale`, while the entry cost is
additive.  Over the **327 completions of the uncensored current bank**:

| | min | p50 | p90 | p95 | p99 | **MAX** |
|---|---|---|---|---|---|---|
| `need` | −1,185 | −30 | 89 | 195 | 395 | **438** |

**`ENTRY_MAX = 463` covers 327 of 327, with 25 clocks to spare**, and the
distribution shows **no pile-up at the reserve** (p99 = 395).  That is the same
censoring test §13.2(d) used to convict the pre-A-3 budget, run again and
**passing**: the requirement's upper end is now visible and it sits BELOW the
reserve.  The 719-clock capture, `fz2c/402075`, **completed**, with
`need = 319`.

**The one capture in 732 whose requirement exceeds it** is `fz2e/535050`
(raw, `wvec-uni`, `weff` 4): 15 register words written from row 3,590 at a
measured 33.4 rows/word, `MAGIC` present, and the done marker projected ~29
rows past the last usable row — `need ≈ 492`.

**IT IS NOT USED TO RE-TUNE THE CONSTANT, AND THIS PARAGRAPH IS WHY.**  Moving
`ENTRY_MAX` from 463 to ≥ 492 would be choosing a constant after seeing which
single seed it catches, on the same capture that revealed it — `§13.4`'s "one
re-capture" and `ucore_provenance.md` §64.1's rule, both.  It would buy **at
most one seed of 269**, and it would cost 29+ clocks of earlier termination on
every seed in the corpus.  **The derivation is: `ENTRY_MAX` = the observed
maximum of the measured requirement, which is 438, and 463 ≥ 438.  DERIVED
ONCE, REGISTERED HERE, AND NOT SWEPT.**

**AND THE OTHER FOUR `BUDGET` CAPTURES ARE NOT BUDGET FAILURES.**  Their `need`
values are **−6, −113, −881, −289** — they had hundreds of rows to spare — and
**all four are `wrote_term = True`**: the run overwrote the terminator page, so
the handler emitted register words and then never reached its own done marker.
They are already dispositioned by an existing class and the label is describing
the symptom, not the cause.  Only `fz2e/535050` is a budget miss at all.

**FALSIFIER, REGISTERED BEFORE THE RE-CAPTURE:** if the re-capture's `BUDGET`
class is more than a handful, or if its `need` distribution piles up at 463,
then 463 is short and this derivation is wrong.

### 17.4 D-1 — THE ARCH COLUMN WAS READ THROUGH THE **COMPARISON** WINDOW, AND THE BUDGET IS WRITTEN AGAINST THE **CAPTURE**

`fuzz_classify.diff_rows` sets the compare length to
`min(len(real), len(sim), limit = 4000, dend + 8)` — in **POSITIONS** — and
`eval_case` then asked `arch_dump(real, v.n)`.  A board capture is **4,063 rows
beginning at absolute record 33** (the board holds RESET for the first 33 and
`check_seq.run_chip` returns `recs[rel:]`), so the scoreable region ended at
**absolute row 4,032** while `term_clocks` budgets the terminator against
`CAP_ROWS = 4,096`.  **The two ends of one budget were 63 rows apart.**

That is **A-3's anchor defect again, at the other end of the capture**: a row
number in one coordinate system subtracted from a depth in another.  A-3 fixed
the near end (`ANCHOR_W0` 145 → 180) and did not look at the far one.

The consequence is not subtle: a **complete, correct, `MAGIC`-anchored 15-word
dump** landing in rows 4,033-4,095 read as *"the terminator was never
reached"*.  On the current bank that is **3 captures** (`fz2c/410064` done at
absolute **4,051**, `fz2e/521054` at **4,004**, `fz2e/528008` at **4,070**);
on INV-2's archive, where the budget put every dump against the end, it is
**77**.

**THE REPAIR** is one line of intent and it was already precedent in the same
function: `wrote_term` has been read over `len(real)` since T10, with a comment
saying in as many words that `v.n` is the comparison's window and the
terminator's evidence is not the comparison's business.  The arch column is now
read the same way.  **`classify` is untouched** — every verdict, row-diff,
signature and `bad_rows` in this campaign is computed over `v.n` exactly as
before.

### 17.5 D-2 — A DONE MARKER IS ONE THAT CARRIES THE SENTINEL

`classify` states, in its own comment, that *"Tier B (raw) legitimately forges
done markers with random data (a random `OUT 0xFC`) … never trusts them"*.
`dump_words` then took the **first** `OUT 0xFC` as the boundary **whatever it
carried**, truncated the word list there, and returned words that are not a
dump.  `provenance_alarms` calls a non-sentinel done marker **forged** in its
own words, in the same file.

`fz2e/529009` is the case: a raw image writes `OUT 0xFC, 0xE4EE` at absolute
row **1,721**; the part then HALTs; the terminating NMI at 3,189 wakes it; it
dumps 15 words from 3,256 and writes `OUT 0xFC, 0xF00D` at **3,629**.  The
dump is complete, correct and 900 rows inside the window, and the arch column
read `None`.  **This is the seed §15.8 called "a HALT that took the vector and
did not dump".  It dumped.**

**THE REPAIR** is ONE predicate — `DONE_SENTINEL` — with no tier parameter,
because the sentinel is the same in both tiers.  `dump_words`, `arch_dump` and
`dump_restarted` gain `sentinel_only`, **defaulting to False so that every
historical caller means what it meant**; only the fz2 arch column passes True.

### 17.6 WHAT THIS AMENDMENT DELIBERATELY DOES **NOT** DO

* **It does not create a fifth discard class.**  `LONG_INSN` is a mechanism no
  budget reaches, exactly as A-4's stalled class is, and by the same reasoning
  it would qualify.  **Whether it becomes a declared discard class is a
  decision about a registered bar and belongs to the coordinator**, on the A-4
  precedent (§15.0's four conditions, a hard falsifier, and a both-ways
  rescore).  It is named here and disposed nowhere.
* **It does not move `ENTRY_MAX`, `TERM_CLOCKS`, `STALL_IDLE`, `TERM_MARGIN`,
  `ANCHOR_W0`, `DUMP_W0`, `TERM_FLOOR` or any bar.**
* **It does not touch `classify`**, so no verdict, signature or row-diff moves.
* **It does not extrapolate.**  The census above is over 732 banked captures,
  which are the divergent / keep-rows / ballast subset and are **not** a random
  sample of 3,840.  No figure in §17 is scaled up to corpus size, and the
  §17.7 re-capture exists precisely so that none has to be.

### 17.7 THE DURABLE FIX, AND THE ARITHMETIC THAT MADE THE CHEAP ROUTE CHEAP

**245 of the 269 could not be asked because `fuzz_campaign` banks rows only for
divergent / keep-rows / ballast captures.**  §15.8 left the cost of a
`--keep-rows` re-capture with the coordinator; the arithmetic, checked against
the real bank rather than recalled:

* `fz2c` **508** captures / **22.61 MB** → **45.6 KB** each; `fz2e` **224** /
  **10.49 MB** → **48.0 KB** each.  A targeted 245 would be **≈ 11.2 MB**, and
  a full `--keep-rows-every 1` over 3,840 would be **≈ 175 MB**.  Both figures
  in §15.8's framing are arithmetically right.
* ⚠ **but `fuzz_bank.CAP_MB = 25` does NOT govern `captures/`** — it caps the
  promoted regression bank under `tests/v30/fuzz_bank/<cid>/seeds/`, and the
  live `captures/` directories already hold **33 MB** between them with nothing
  enforcing anything.  The 25 MB the decision was measured against is a bar on
  a different artifact.  Recorded as an erratum against the reasoning, not
  against the conclusion: 175 MB of rows is still not worth keeping.

**AND NEITHER RE-CAPTURE IS NEEDED, because the answer costs one string per
line.**  A-4 already computes `stalled` at capture time and banks it; A-6 adds
**`mech`**, computed by the same function that the offline backfill uses, from
rows that are in hand anyway (**2.5 ms per seed**, ≈ 10 s over the whole
corpus, and **zero** extra bytes of capture).  **A capture taken under A-6
classifies every one of its 3,840 seeds off its own result lines, with no rows
retained at all.**

### 17.8 THE REGISTERED PREDICTIONS FOR THE RE-CAPTURE — one capture, as §13.4 requires

Reported as registered, never restated.  **No bar is predicted**, and the two
A-5 rate clauses keep their `UNVALIDATED` marker whatever they read.

* **P1.** `classified_from` reads **`line`: 3,840** and **`none`: 0**.  No seed
  is unclassifiable.
* **P2.** The `mech` census sums to 3,840, with `not evaluable` reported
  separately and expected to be **0**.
* **P3 — A HARD SELF-CONSISTENCY FALSIFIER.**  `arch_ok` is TRUE **iff** `mech`
  ∈ {`REACHED`, `WINDOW`, `FORGED_DONE`}, seed for seed over all 3,840; and
  `mech == STALLED` **iff** `stalled` is TRUE, seed for seed.  The two columns
  are computed from the same rows by the same functions and **any disagreement
  is a defect in this amendment**, not a finding about the part.
* **P4.** **UNDISPOSITIONED WILL STILL BE NON-ZERO**, and `LONG_INSN` will be
  the largest single class inside it.  **E-1c WILL STILL BE MISSED.**  This is
  registered BEFORE the capture so that a non-zero residue is a reported result
  and not a discovery — and so that no reader mistakes A-6 for an attempt to
  clear the bar.  **No number is predicted for it**: the banked 732 are not a
  random sample of 3,840 and §17.6 refuses to scale them.
* **P5.** The two rate clauses RISE, by the D-1 + D-2 repairs only.  On the
  banked sample those repairs move **4 of 732 (0.55 %)**, so the expected move
  is **under one point**; they are not forecast more precisely and they are not
  quotable either way.
* **P6.** C-2, C-4, C-5, C-7, C-8, C-9, C-10 read as they did in §14.1.  C-3's
  generation clause stays **0 forbidden `0F xx` pairs**; its runtime clause is
  a property of the images and the same two seeds are expected.  C-6 and C-11
  stay **NOT SCOREABLE** for §14.5's two unchanged reasons.
* **P7.** `SEEDS_SHA256` and `SEED_LIST_SHA256` are **unmoved**, and
  `fz2_w1.py lint` passes with no re-freeze.  The re-capture is the SAME
  directive on the SAME seeds.

**THE PRIOR CAPTURE IS ARCHIVED BY RENAME, AND IT IS NOT INVALIDATED.**  No
constant moved, so nothing it was scored against is defective in the way INV-2's
was; its rows are true silicon taken under the same budget the re-capture uses.
This is the **w1evt-biased precedent** — an archive-by-rename, which
`CLAUDE.md` distinguishes from an invalidation in as many words — and **no
invalidation-ledger entry is opened.**  Nothing is deleted.

### 17.9 WHAT A-6 CHANGES IN THE TREE

* `sw/fuzz_classify.py` — `dump_words` / `arch_dump` / `dump_restarted` gain
  `sentinel_only`, **default False**.  Nothing else; `classify` is untouched.
* `sw/fuzz_campaign.py` — the arch column is read over the whole capture and
  sentinel-only (D-1, D-2); `SCORER_WINDOW` and `term_mechanism` are added; the
  result line gains **`mech`**.  No constant, no bar, no capture-path change.
* `sw/fz2_termcost.py` — the `mechanism` backfill and its census command.  It
  reads banked captures only — no board, no TB, no engine.
* This document, appended.

### 17.10 M-1's DECISIVE MEASUREMENT — **`QS` NEVER CHANGES**, and an opcode identification that was TRIED and is NOISE

Measured offline on the archived (`prior`) bank while the §17.7 capture ran; no
board, no engine, and it changes no prediction in §17.8.

**THE MEASUREMENT.**  Over all **16** `LONG_INSN` captures, on the socket leg's
own rows, from the terminating NMI to the last row of the capture:

| | |
|---|---|
| rows with **`qs != 0`** after the NMI | **0**, over all 16 seeds, **0 of 15,956 rows** |
| bus cycles after the NMI | 124 … 190 per seed |
| bus-cycle kinds after the NMI | **MEMR and MEMW only** — no CODE, no INTA, no I/O, on all 16 |
| read-pointer stride, per iteration | **−2 bytes**, all 16 |
| write-pointer stride, per iteration | **−2 bytes**, all 16 |
| `LOCK` asserted | **never** |

`QS` is the CPU's own queue-status pin pair, and it is the part telling the
world when it takes a byte out of its prefetch queue.  **`QS` = 0 for the whole
post-NMI span means no byte enters the queue and NO INSTRUCTION IS RETIRED** —
for 124 to 190 bus cycles, on all sixteen, on both engines.  Together with the
two descending pointers moving 2 bytes per iteration, that is a word-size block
transfer with `DF = 1`, **in flight and not finishing**, and it is measured off
the pins rather than inferred from a taxonomy.

**AND WHAT WAS NOT ESTABLISHED, STATED SO IT IS NOT LATER ASSUMED.**  An attempt
was made to name the actual opcode by regenerating each image (`GEN-DRIFT`
checked: `sha256` equal on every one) and scanning back up to 20 bytes from the
last CODE fetch for a block-transfer opcode.  **IT RESOLVED 9 OF 16 AND THE
RESULT IS NOISE, AND IT IS DISCARDED**: 14 of 256 byte values are block-transfer
opcodes, so a 20-byte window of random bytes contains one with probability
≈ 67 % by chance, and the last *fetch* is a prefetch that runs ahead of the
executing instruction by an unknown amount.  **No opcode is named.**  The bus
signature above needs no opcode to be conclusive, and a byte identification at
5.5 % per-byte background is not evidence.

**THE THREE `NEAR` SEEDS, MEASURED THE SAME WAY.**  `fz2c/406078`,
`fz2c/408072`, `fz2c/411070`: the bus is dead from the NMI to the last row —
**761, 1,400 and 1,461 clocks of complete silence**, `qs` never changing, **and
`core_after` is 0 on all three**, so the fabric core parks as well.  They are
`NEAR` and not `STALLED` only because A-4's clause (2) is a **PRE**-NMI
threshold and their pre-NMI idle is 61, 11 and 32 clocks against `STALL_IDLE`
= 200.  **That threshold is registered and A-6 does not touch it**: moving it
after seeing which three seeds it withholds is the fitting §15.1 wrote it to
avoid.  It is recorded here as an observation for the coordinator and nothing
more.

**THE CATCH-ALL, `fz2c/405062`, IS STILL UNEXPLAINED AND STAYS THAT WAY.**
Soup, `wvec-uni`, `has_halt`: the last pre-NMI bus cycle is a MEMR 57 clocks
before the terminator; **one** CODE fetch happens 205 clocks *after* it, with a
single `qs` = 3 pop; and then the bus is silent for the remaining 650 clocks.
It is one seed, it carries none of the four discard signatures, and no
mechanism in this document accounts for it.

---

## §18 THE A-6 RE-CAPTURE — TAKEN 2026-08-09, SCORED AS REGISTERED: **UNDISPOSITIONED 269 → 100, AND ALL 100 ARE NAMED**

**One capture, as §13.4 requires.**  FLASH #12 resident (`sof 8db6dadf5c4c…`,
receipt `27fb750f925c…`), **NOT re-flashed**.  A-6 was committed at
`25e73e4873` and the archive-by-rename at `8cc02326e9`, **both before board
contact**.  `preflight --board` **OK** twice — once before the rename and once
at the new HEAD — each time: SINGLE WRITER (no `v30ctl`/`serve` on the board,
no local serve client), resident bitstream carries this tree's rig RTL, 192
regeneration seeds `hits = 0`, `div_guard` **PINNED**, chip-vs-golden /
core-vs-chip / core-vs-golden **MATCH over 800 rows** each.

**3,840 seeds in 11.1 minutes of board time**, inside §6's registered ≤ 30 min.
**48 of 48 strata `written == n` with `rc = 0`, `halted: None`.**  `div_guard`
**PINNED on 53 of 53 probes, 0 unpinned**; socket only, `use_core=False`;
**0 transport errors, 0 quarantines**, circuit breaker not tripped; C-9 **1.4
min**; `board_idle()` clean and **`check_ab_hw chip 800` MATCH over 800 rows**
taken after everything.  Full per-clock rows retained with `SHA256SUMS` beside
them (509 + 227 captures).

### 18.1 THE REGISTERED PREDICTIONS OF §17.8, SCORED

| | registered | measured | |
|---|---|---|---|
| **P1** | `classified_from` = `line` for all, `none` = 0 | **`{"line": 302}`, `none` absent — every seed asked off its own line, `stalled` is `None` on 0 of 3,840** | **MET** |
| **P2** | the `mech` census sums to 3,840, `not evaluable` 0 | **3,840, and `mech` absent on 0 lines, `None` on 0** | **MET** |
| **P3** | `arch_ok` ⟺ `mech` ∈ {`REACHED`,`WINDOW`,`FORGED_DONE`}; `mech == STALLED` ⟺ `stalled` | **0 disagreements and 0 disagreements**, over all 3,840 | **MET** |
| **P4** | UNDISPOSITIONED non-zero, `LONG_INSN` its largest class; E-1c still MISSED | **100**, of which `LONG_INSN` **73**; **E-1c MISSED** | **MET** |
| **P5** | the rate clauses rise by under one point | soup **98.54 / 98.89 → unchanged to the hundredth**; raw **83.54 → 83.96** and **83.61 → 84.24** | **MET** |
| **P6** | C-2/4/5/7/8/9/10 as §14.1; C-3 generation 0; C-6, C-11 NOT SCOREABLE | all as registered — and **C-9 is 192/192 again** | **MET** |
| **P7** | `SEEDS_SHA256` / `SEED_LIST_SHA256` unmoved, `lint` passes with no re-freeze | both unmoved, `lint` **PASS**, `SEED_LIST_SHA256 45d25f31a325c496…` | **MET** |

**ALL SEVEN MET.**  P5 carries its own reproducibility evidence: this is a
repeat of the same directive on the same seeds, and **the two soup rates came
back identical to the hundredth of a point.**

### 18.2 THE BARS — **7 MET / 2 MISSED / 2 NOT SCOREABLE**, the same shape as §14.1

`sw/testdata/fz2/fz2_bars.json`, `2026-08-09T16:47:16Z`.

| bar | §15.7 | **A-6** | measured now |
|---|---|---|---|
| **C-1** | MISSED | **MISSED** | soup **98.54 / 98.89** · raw **83.96 / 84.24** (A-5's bars 90.0 / 75.0, `UNVALIDATED`) · **UNDISPOSITIONED 100**, bar 0 |
| **C-2** | MET | **MET** | **3,513** dumps, `MAGIC` constant, all 14 other words ≥ 2 distinct |
| **C-3** | MISSED | **MISSED** | generation **0** forbidden `0F xx` pairs over 3,840; runtime **2** |
| **C-4** | MET | **MET** | 1 distinct era, 0 absent, 0 incomplete, `build_stale` 0 |
| **C-5** | MET | **MET** | **0 GEN_DRIFT, 0 wvec mismatches** over all 3,840 |
| **C-6** | NOT SCOREABLE | **NOT SCOREABLE** | unchanged: `cmd_control` unimplemented + O-2b |
| **C-7** | MET | **MET** | 3,840 scored, max **957** bus cycles, 0 at or over 4,096 |
| **C-8** | MET | **MET** | **53 probes, 0 unpinned** |
| **C-9** | MET | **MET** | **192 / 192 stable**, 0 unstable, 0 errors |
| **C-10** | MET | **MET** | 0 quarantines, 0 run-error lines, breaker not tripped, no halted stratum |
| **C-11** | NOT SCOREABLE | **NOT SCOREABLE** | unchanged: the bank promotion was not run this sitting |

Decompositions, never one aggregate — **census**: captured 960, rows-exact
**94.17 %**, arch-exact **87.71 %**, unscoreable **92** (was 94.38 / 87.71 /
95).  **Enriched**: captured 2,880, rows-exact **94.48 %**, arch-exact
**88.61 %**, unscoreable **273** (was 94.58 / 88.33 / 282).

**C-1 IS STILL MISSED, AND NOW ON EXACTLY ONE CLAUSE.**  Under A-5's
re-registered rates all four cells clear their bar; **E-1c is 100 against 0**.
Reported as registered, not restated.

### 18.3 THE RESIDUE, NAMED — which is the whole point of this sitting

`fz2_bars.json` → `bars.C-1.measured.mech_census` and `.mech_undispositioned`:

| `mech` | whole corpus | **inside the 100 UNDISPOSITIONED** |
|---|---|---|
| `REACHED` | 3,503 | — |
| `STALLED` (A-4) | 208 | — (dispositioned) |
| **`LONG_INSN`** (M-1) | **78** | **73** |
| `BUDGET` | 26 | **14** |
| `NEAR` | 10 | **9** |
| `WINDOW` (D-1) | 6 | — (repaired) |
| `FORGED_DONE` (D-2) | 4 | — (repaired) |
| `OTHER` | 5 | **4** |
| **total** | **3,840** | **100** |

**269 → 100, and 245 "could not be asked" → 0.**  The move is three things and
they are separable:

* **the 245 became askable** — A-4's `stalled` and A-6's `mech` are on every
  line, so `classified_from` is `line` for all of them.  Most of what was
  unclassifiable turns out to be A-4's already-declared stalled class:
  `stalled_total` is **202** here against **43** in §15.7, on the same rule;
* **D-1 + D-2 repaired 10 seeds** (6 `WINDOW` + 4 `FORGED_DONE`), each a
  complete `MAGIC`-anchored dump that was in the rows and unreadable;
* **nothing was discarded to get there.**  A-4's four classes are still the
  whole disposition set, and E-1c counts every one of the 100.

**`LONG_INSN` IS 73 % OF THE REMAINING RESIDUE**, which is P4 as registered.
**No `TERM_CLOCKS` or `ENTRY_MAX` value reaches it** (§17.2, §17.10).

### 18.4 THE `ENTRY_MAX` FALSIFIER, SCORED — AND ITS SOFT CLAUSE WAS BADLY WRITTEN

§17.3 registered: *"if the re-capture's `BUDGET` class is more than a handful,
or if its `need` distribution piles up at 463, then 463 is short and this
derivation is wrong."*

* **The sharp clause is NOT met.**  Three of the 14 undispositioned `BUDGET`
  seeds carry banked rows, and their measured requirements are
  **−139, −6 and +492**.  There is no pile-up at 463: **two of the three had
  139 and 6 rows of headroom and still did not finish**, which is not a budget
  failure at all.  Only `fz2e/535050` — the same seed §17.3 named in advance —
  exceeds the reserve, by ~29 clocks.
* **The soft clause reads "more than a handful" at 14, and it was my clause to
  write sharply and I did not.**  Reported as the miss it is.  What the
  measurement says is that the `BUDGET` **label** over-counts the budget class:
  it means *"the register port was written after the NMI and no
  first-anchored sentinel done marker followed"*, and §18.5 is one reason that
  is not the same sentence as *"the window ran out"*.
* **CONCLUSION, STATED AS A CONCLUSION AND NOT AS A PASS: `ENTRY_MAX` = 463 is
  NOT REFUTED, and it is not re-tuned.**  It was derived once, registered, and
  captured against once.

### 18.5 D-3 — A THIRD INSTRUMENT DEFECT, **NAMED AND MEASURED AND NOT REPAIRED**

`dump_words` is anchored to the **FIRST** done marker.  D-2 stopped a *forged*
one from being that anchor.  It did not stop a **genuine earlier** one.

`fz2e/523040` is the case, and it is legible in one column: the board image
**re-runs**, and the capture opens part-way through a run whose dump is
therefore **truncated to its last 8 words** (`0x31b4 … 0x1f89`, no `MAGIC`),
followed by a real `OUT 0xFC, 0xF00D` at row 927.  The terminator then fires at
3,068 and writes a **complete, correct 15-word dump** (`0xF00D, 0x5EED, …`)
ending in `OUT 0xFC, 0xF00D` at 3,472.  `dump_words` stops at row 927, returns
eight words, and `arch_dump` correctly rejects them — **and never sees the
dump that is 2,500 rows further on.**

**Measured, both banks, by taking the LAST complete sentinel-anchored dump
instead of the first**: **2 of 736** banked captures in the A-6 bank, **0 of
732** in the A-5 bank.  Both are currently labelled `BUDGET`, and both are
inside the 100.

**IT IS NOT REPAIRED IN THIS SITTING, ON PURPOSE.**  Two repairs have landed
and the one registered capture has been taken.  Landing a third and
re-capturing would be iterating the instrument against a bar that is still
missed, which is exactly what §13.4 forbids and what this whole sequence of
amendments exists to prevent.  **FALSIFIER, for whoever takes it**: if
`arch_dump` is re-anchored to the last complete sentinel dump, exactly these
2 banked captures move and no capture that currently reaches the terminator
stops reaching it.

### 18.6 WHAT IS STILL OPEN, STATED PLAINLY

* **E-1c is 100 against 0.  C-1 IS MISSED.**  The honest floor §15.8 put
  "somewhere between 24 and 269" is now **100**, and every one of the 100
  carries a name.
* **73 of the 100 are `LONG_INSN`, and no budget reaches them.**  On A-4's own
  reasoning they would qualify as a fifth declared discard class.  **That
  decision belongs to the coordinator and is not taken here.**  If it were
  taken, E-1c would read **27**.
* **9 are `NEAR`** — dead on both legs for 761 to 1,461 clocks after the NMI,
  withheld only by A-4's pre-NMI threshold (§17.10).
* **14 are `BUDGET`**, of which at least 2 are D-3 and 1 is a genuine ~29-clock
  overrun; the remaining 11 have no banked rows and are **not** attributed.
* **4 are `OTHER`** and are genuinely unexplained.  The catch-all is **not**
  empty and was never engineered to be.
* **C-3, C-6 and C-11 are unchanged and unimproved.**  C-3's runtime clause
  reads 2 again; one of the two, `fz2e/509069`, reproduces from both earlier
  captures, and the other is a **different** seed (`fz2e/521059` here,
  `fz2e/534020` in §14.4) — recorded as an observation, not chased.
* **`cmd_stability` still reads its arch column at the pre-A-6 window**
  (`min(len, 4000)`, first-anchored).  C-9 compares three repetitions of the
  same seed through the same reader, so a dump past that window degrades to
  rows-only stability rather than to a false MISS, and C-9 read **192/192**.
  It is left alone rather than changed mid-sitting; recorded so it is not
  mistaken for an oversight.

---

## §19 AMENDMENT A-7 — A FIFTH DECLARED DISCARD CLASS: **`LONG_INSN`, THE CAPTURE WINDOW'S OWN LIMIT**

**Written 2026-08-09/10, AFTER the §18 A-6 re-capture that MISSED C-1 with
UNDISPOSITIONED at 100, and COMMITTED BEFORE the rescore it enables.**
Appended, never back-edited.  This is the coordinator's disposition of M-1
(§17.2), which named the mechanism, measured it (§17.10) and deliberately made
no disposition of it — *"whether it becomes a declared discard class is a
decision about a registered bar and belongs to the coordinator"* (§17.6).

**NO BAR MOVES.**  C-1 … C-11 keep their text and their registered values
**character for character** — including A-5's re-registered rate clauses (soup
**≥ 90.0 %**, raw **≥ 75.0 %**, both still `UNVALIDATED`) and **E-1c = 0, which
is UNTOUCHED**.  What changes is §3.4's list of declared discard classes:
**four become five.**

### 19.0 WHAT THIS CLASS IS, AND — LOUDLY — WHAT IT IS NOT

> **IT IS A LIMIT OF THE CAPTURE WINDOW.  IT IS NOT A DEFECT OF THE PART, AND
> IT IS NOT A FAILURE TO TAKE AN INTERRUPT.**

The name is chosen for the window and not for the part, deliberately, so that a
reader six months from now cannot take it for silicon behaviour.  The
distinction from A-4 is **categorical, not one of degree**:

| | A-4 `stalled` | **A-7 `long_insn`** |
|---|---|---|
| the part is | **STOPPED** | **RUNNING** |
| post-NMI bus | **none at all** | 571 … 1,262 non-`PASV` rows |
| would a longer window help? | **NO — it can never dump** | **YES — it would dump** |
| what the capture ended in the middle of | nothing | **one instruction** |

`term.vec_used` is **TRUE on every capture in this class** and that is not a
contradiction: the rig's sticky bit says the overlay served a CS half, which
happens when the instruction retires — **after the last of the 4,096 records**.
The bit and the rows are answering about different intervals, exactly as §17.2
recorded.  ⚠ **`vec_used` TRUE therefore does not mean "the vector was taken
inside the capture"**, and §14.3's reading of `vec_used` FALSE does not invert.

**Why it is a DISCARD and not a containment failure.**  Nothing escaped, the
image did not overwrite anything, and the terminator was armed and asserted.
The capture is 4,096 records deep; a block transfer is ONE instruction and its
iteration count came out of the same random bytes as its opcode, so it can run
for hundreds of thousands of clocks.  **No `TERM_CLOCKS` and no `ENTRY_MAX`
value reaches it**: firing the terminator earlier only moves the pin edge,
which is latched and served later regardless.

### 19.1 THE TRAP THIS AMENDMENT IS WRITTEN AGAINST — A-4 §15.0's FOUR CONDITIONS, AGAIN

C-1's disposition set is `arch_restart or ps3_8080 or wrote_term or stalled`,
and **adding a fifth term makes UNDISPOSITIONED fall by construction.**  That
is the shape amendment A-2 exists to prevent — there, `ps3_8080` fired on 3,840
of 3,840 and would have driven the count to **0 vacuously**.  So this class is
admitted under **the same four conditions A-4 was**, all met and reported
below:

1. the detector is **independent of the thing it explains** and is computed
   from the SOCKET leg's own rows.  **Neither of its clauses mentions a dump**,
   which is what makes condition 2 a test rather than a tautology;
2. a **HARD FALSIFIER, run**: the detector must fire on **ZERO** captures that
   reached the terminator, over every banked capture in **both campaigns** and
   **all three banks**;
3. **no other bar moves**, and C-1's two rate clauses keep their text and
   values character for character;
4. the rescore is reported **BOTH WAYS**, with and without the class.

### 19.2 THE DETECTOR

`fuzz_campaign.long_insn_evidence` is the definition; `sw/fz2_longinsn.py` is
its falsifier and its census, and **no second copy of the predicate exists
anywhere** — since A-7, `term_mechanism`'s own `LONG_INSN` branch CALLS it.

On the **SOCKET leg's own rows**, let `f` be the row the terminating NMI
asserts (the unique `pin_nmi` run of length `TERM_HOLD` — A-4's identification,
unchanged; a stimulus NMI holds 2 or 300 and is a different run).  Reading
**only rows at or after `f`**, `long_insn` is TRUE iff BOTH hold:

| clause | what it says | why it is there |
|---|---|---|
| **(1) THE PART IS STILL RUNNING** — at least one non-`PASV` row at or after `f` | the bus is live when the terminator arrives and stays live | this is **A-4 clause (3)'s exact negation**, so the two classes are **disjoint by construction** and neither can absorb the other.  `fz2_longinsn falsify` checks it rather than asserting it: **0** captures carry both labels, in every bank |
| **(2) AND IT HAS NOT STARTED AN INSTRUCTION** — not one `CODE` fetch at or after `f` | it is fetching no code and still driving the bus, so it is finishing something it began before the pin went high | this is the clause that does **all** of the falsifier's work — measured below — and it is a statement about the **bus**, not about a dump |

**There is no third clause, no threshold, no tier parameter and no per-opcode
anything.**  `STALL_IDLE` is A-4's and is not read here.

**DO NOT NAME AN OPCODE.**  §17.10 tried: it regenerated every image
(`GEN-DRIFT` checked, `sha256` equal on every one) and scanned back for a
block-transfer byte.  It resolved 9 of 16 and **the result is noise and was
discarded** — 14 of 256 byte values are block-transfer opcodes, so a 20-byte
window of random bytes contains one with probability ≈ 67 % by chance, and the
last *fetch* is a prefetch running ahead of the executing instruction by an
unknown amount.  **The class is defined by the observable and by nothing else,
and that is not re-litigated here.**

### 19.3 THE FALSIFIER — RUN, AND REPORTED WITH ITS DENOMINATORS

`python3 sw/fz2_longinsn.py falsify`, over **every banked capture in every
bank**, both campaigns separately inside each:

| bank | campaign | terminator-REACHED captures | **detector fires on** |
|---|---|---|---|
| current (A-6) | `fz2c` | 461 | **0** |
| current (A-6) | `fz2e` | 205 | **0** |
| prior (A-5, archived by rename) | `fz2c-A5-archive` | 458 | **0** |
| prior (A-5, archived by rename) | `fz2e-A5-archive` | 201 | **0** |
| archive (INV-2) | `fz2c-INV2-archive` | 354 | **0** |
| archive (INV-2) | `fz2e-INV2-archive` | 101 | **0** |
| | **TOTAL** | **1,780** | **0 — PASS** |

`not evaluable` is **0** in all three banks.  For contrast, on captures that did
NOT reach the terminator it fires on **15 / 70** (current), **16 / 73** (prior)
and **18 / 279** (archive).

**WHICH CLAUSE DOES THE WORK, reported so the conjunction is not taken on
trust.**  Clause (1) alone fires on **666 / 666**, **659 / 659** and **455 /
455** reached captures — it does none of it.  **Clause (2) alone fires on 0 of
every reached population**, so the falsifier is carried entirely by *"not one
CODE fetch after the NMI"*, which is a statement about the bus and not about a
dump.  A capture that reaches the terminator **executes its dump**, and
executing means fetching.

**DISJOINTNESS FROM A-4, CHECKED**: **0** captures carry both `stalled` and
`long_insn`, in every bank.  A-4's own falsifier is unmoved and was re-run:
`fz2_stall.py falsify --bank current` is still **0 / 666**.

### 19.4 THE POSITIVE HALF, AND THE MEASUREMENT THAT MAKES IT A MECHANISM

`python3 sw/fz2_longinsn.py census`.  Over the class, in each bank:

| | current | prior | archive |
|---|---|---|---|
| captures in the class | **15** | **16** | **18** |
| tier | **raw 15 / soup 0** | **raw 16 / soup 0** | **raw 18 / soup 0** |
| `term.vec_used` | **TRUE on all** | **TRUE on all** | **TRUE on all** |
| post-NMI rows | 15,105 | 15,956 | 8,915 |
| **rows with ANY queue activity (`qs` != 0)** | **0** | **0** | **0** |
| rows with `LOCK` asserted | **0** | **0** | **0** |
| post-NMI bus cycles, by kind | **MEMW 1,289 · MEMR 1,051** | MEMW 1,375 · MEMR 1,138 | MEMW 747 · MEMR 625 |
| the FABRIC CORE in the same state | **13 / 15** | 14 / 16 | 16 / 18 |

`QS` is the part's own queue-status pin pair — it reports a byte leaving the
prefetch queue.  **`qs` = 0 on every one of 15,105 post-NMI rows means no byte
enters the queue and NO INSTRUCTION IS RETIRED**, for hundreds of bus cycles,
while the bus runs MEMR/MEMW **only** — no CODE, no INTA, no I/O — and `LOCK`
is **never** asserted, so this is not the 8086 `LOCK`-prefix interrupt-inhibit
story.  It is measured off the pins, and **it is not a clause of the detector**:
it is the corroboration that the two-clause detector is finding a real
mechanism.  Both columns (`qs_nz`, `lock_rows`) are banked with the evidence.

**THE POSITIVE HALF IS BANKED WITH THE DISCARD, NOT THROWN AWAY WITH IT**
(A-4 §15.3's precedent): on 13 of 15 the fabric core is in the identical state
at the identical pin edge — bus running, no CODE fetch — which is a real
chip-vs-core agreement on a real mechanism.

### 19.5 HOW A SEED IS ASKED, AND WHY THE ANSWER IS NOT AN EXTRAPOLATION

**THE DURABLE FIX, LANDED WITH THIS AMENDMENT**: the detector is computed **at
capture time**, while the rows are in hand, and banked on the result line as
`long_insn` + `long_insn_at`.  `fz2_w1.REQUIRED_LINE_FIELDS` names both, so the
preconditions check refuses a capture whose path would not produce them —
checked before board time, the way §7 checks everything else.  **A capture
taken under A-7 classifies every seed off its own line and retains no rows to
do it.**

The §18 capture predates that column and its rows exist for **15 of the 73**
seeds this class concerns, so `fz2_longinsn.resolve` answers in this order:

1. **`line`** — A-7's own column.  Absent on this capture, present on every
   future one.
2. **`rows`** — recomputed from a banked capture.  Definitive.
3. **`mech`** — A-6's census column reads `LONG_INSN`.  **This is a banked,
   capture-time record of THIS detector having fired, not an inference about
   it**: since A-7, `term_mechanism` reaches that label by *calling*
   `long_insn_evidence`.  Checked and not asserted — recomputing `mech` from
   the rows of **all 2,202 banked captures in all three banks** reproduces the
   banked value with **0 differences**, so the refactor moved no label.
4. **`mech_inconclusive`** — `mech` is present and is some other label.  The
   labels are applied in a fixed order and an earlier one wins, so this does
   **NOT** say the detector is False.  The seed **stays UNDISPOSITIONED**.
5. **`none`** — neither.  Stays UNDISPOSITIONED.

**THE IMPLICATION RUNS ONE WAY, AND THE DIRECTION IS THE POINT.**
`term_mechanism` reaches its `LONG_INSN` branch only after `REACHED`, `WINDOW`,
`FORGED_DONE` and `BUDGET`, so the label can **UNDER-report** the detector and
can never over-report it.  Every uncertainty in this resolver therefore leaves
the residue **LARGER** — which is the direction that cannot buy a bar.

### 19.6 ITS OWN TIMING, STATED RATHER THAN HIDDEN

**This class is being added after a capture that missed C-1**, and after A-5
lowered two of C-1's three clauses onto the population that measured them.  Its
protections are §19.1's four conditions, the falsifier of §19.3 with its 1,780
denominator, the disjointness check, and the both-ways reporting of §19.7.
**E-1c's value is not touched** and no rate moves by a hundredth: this class
disposes seeds, it does not make them reach the terminator.

**AND IT DOES NOT CLEAR C-1.**  §18.6 stated the arithmetic in advance —
*"if it were taken, E-1c would read 27"* — and **27 is not 0**.  C-1 stays
**MISSED**, on E-1c alone, exactly as it was before this amendment.

### 19.7 WHAT A-7 CHANGES IN THE TREE

* `sw/fuzz_campaign.py` — `long_insn_evidence`; `term_mechanism`'s `LONG_INSN`
  branch now CALLS it instead of inlining the predicate (0 label changes over
  2,202 banked captures); the two new result-line columns.  **No bar, no
  constant, no threshold and no part of the capture path is touched, and
  `classify` is not touched**, so no verdict, signature or row-diff moves.
* `sw/fz2_longinsn.py` — **new**: the detector's falsifier, its census and the
  resolver.  It reads banked captures only — no board, no TB, no engine.
* `sw/fz2_w1.py` — C-1's disposition set gains the fifth term; the bar now
  reports `undispositioned_4class`, `long_insn_total` and
  `classified_from_long_insn` beside A-4's, permanently.
  `REQUIRED_LINE_FIELDS` gains the two columns.
* This document, appended.

`SEEDS_SHA256`, `SEED_LIST_SHA256` and the corpus itself **do not move**: not
one seed, image, vector or constant changed.  **No board was contacted, no
bitstream flashed and no Quartus run** for this amendment; every figure in §19
is read off banked captures, offline.

### 19.8 THE RESCORE AS RUN — `sw/testdata/fz2/fz2_bars.json`, 2026-08-09T17:56:22Z

`python3 sw/fz2_w1.py bars`, offline, off the same banked results §18 scored.
**No capture, no re-capture, no board.**

**`FZ2 BARS: 7/11 MET   NOT MET: C-1, C-3, C-6, C-11`** — the identical
7 MET / 2 MISSED / 2 NOT SCOREABLE of §14.1, §15.7, §16.8 and §18.2.
**A-7 moved no bar's verdict.**

**BOTH WAYS, as §19.1 condition 4 requires** — and the three-class column is
kept beside them permanently, so the whole sequence is visible in one table:

| | **3 classes** (pre-A-4) | **4 classes** (A-4) | **5 classes (A-7)** | `long_insn` |
|---|---|---|---|---|
| census / soup | 7 | 1 | **1** | 0 |
| census / raw | 73 | 18 | **5** | 13 |
| enriched / soup | 15 | 6 | **1** | 5 |
| enriched / raw | 207 | 75 | **20** | 55 |
| **UNDISPOSITIONED** | **302** | **100** | **27** | **73** |

`classified_from_long_insn`: **`rows` 22 · `mech` 58 · `mech_inconclusive`
20**.  Of the 22 asked from banked rows, the detector is **TRUE on 15 — all 15
`mech == LONG_INSN`** — and **FALSE on 7 — 3 `NEAR`, 3 `BUDGET`, 1 `OTHER`**.
**The two sources agree on 22 of 22 where both exist**, which is the check
§19.5 step 3 rests on, run rather than asserted.  The 20 `mech_inconclusive`
seeds are **not** disposed and are counted in the 27.

**THE RESIDUE, ALL 27 NAMED** — `mech_undispositioned`:
**`BUDGET` 14 · `NEAR` 9 · `OTHER` 4**.  `LONG_INSN` has left it entirely.
§18.6's arithmetic, registered before this amendment existed, said *"if it were
taken, E-1c would read **27**"*.  **It reads 27.**

**C-1 IS STILL MISSED, ON E-1c ALONE, AND THE VERDICT STRING DID NOT MOVE.**
Under A-5's re-registered rates all four cells clear their bar — census/soup
**98.54 %**, enriched/soup **98.89 %**, census/raw **83.96 %**, enriched/raw
**84.24 %**, none of them moved by a hundredth — and **E-1c is 27 against 0**.
Reported as registered, not restated.

**NOT ONE OTHER FIELD MOVED, and this is checked rather than asserted.**  The
new `fz2_bars.json` was compared **leaf for leaf** against the one §18
committed — 600 leaves before, 616 after, **26 differing**:

* **25 of them are inside `bars/C-1/measured`** — the per-tier `long_insn` /
  `dispositioned_4class` / `undispositioned_4class` additions, the three
  `classified_from_long_insn` entries, `long_insn_total` **73**,
  `undispositioned_4class` **100**, `undispositioned` **100 → 27**, and
  `mech_undispositioned/LONG_INSN` **73 → absent**;
* **1 is `ts`**, the run stamp.

**`bars/C-1/verdict` is BYTE-IDENTICAL** — `MISSED (rate clauses UNVALIDATED --
A-5)` before and after.  ⚠ The task registered *"only C-1's `measured` and
`verdict` differ"*; **the verdict did NOT differ**, because C-1 was already
MISSED on E-1c and remains MISSED on E-1c.  Recorded as the miss of that
expectation rather than restated as a match.  `bars/C-1/registered`,
`bars/C-1/statement`, every other bar's `verdict` / `measured` / `registered`,
both populations' three decompositions (census **94.17** / **87.71** / **92**;
enriched **94.48** / **88.61** / **273**) and `seed_list_sha256` are
**identical**.  `mech_selfcheck` still reads **0 / 0 / 0**, so A-6's P3
self-consistency falsifier is undisturbed by the refactor.

`python3 sw/fz2_w1.py lint` **PASS, 0 hits, 48 stratum rows**.  `bars` exits
**1**, as it must while any bar is unmet.

---

## §20 AMENDMENT A-8 — C-6(b) IS RULED: **EVALUATE PER DIRECTIVE**, AND WHERE TWO SCHEDULERS SHARE A PIN THE SEED IS **UNEVALUABLE**

**Written 2026-08-09/10, AFTER §19.8's rescore and COMMITTED BEFORE the rescore
it enables.  No board was contacted for it and none can be: clauses (a) and (c)
of C-6 are BOARD legs.**  Appended, never back-edited.  This is the
coordinator's ruling on finding **O-2b** (§12.4), which recorded that the
clause and its own instrument were never reconciled and deliberately made no
disposition.

**NO BAR MOVES.**  C-6's registered text is **not edited, character for
character**, and neither is any other bar's.  A-8 says how the clause the
document already registered is **evaluated**; it does not restate it, relax it
or narrow it.  `SEEDS_SHA256`, `SEED_LIST_SHA256` and the corpus do not move.

### 20.0 WHAT WAS WRONG, IN ONE PARAGRAPH

C-6(b) reads *"every event seed's counted high-row run equals its own `hold`,
± 1 clock"* — **singular**.  `fuzz_campaign._pin_runs` returns **every** run on
**all three** pins as a dict of `[start, length]` lists and says in its own
docstring that picking one *"would be answering the question in the
instrument"*, because a stimulus NMI and the terminating NMI share the wire.
`cmd_bars` evaluated `abs(dict - int)`, raised `TypeError`, and — correctly —
**declined**.

**And a longest-run reading would have been wrong on every seed in the
corpus**, which is worth stating because it is the trap the ruling avoids:
`pin_poll_n` is ACTIVE LOW and is therefore "asserted" for the **whole 4,063-row
capture on all 3,840 seeds**, while **no directive in this corpus names POLL**
(§9: 0 POLL seeds, stated in advance).  Any rule that reaches for "the run"
without asking which directive it belongs to picks that one.

### 20.1 THE RULING

> **EVALUATE PER DIRECTIVE.**  For each **ARMED scheduler**, take the run on
> **the pin that scheduler's directive names**, and compare its length to
> **that scheduler's own `hold`**, ± 1 clock.

There are exactly two schedulers per seed and both are known from the
directive, before a single row is read:

| scheduler | pin | hold | armed on |
|---|---|---|---|
| **terminator** | `TERM_PIN` = NMI | `TERM_HOLD` = **20** | **every** seed (3,840) |
| **stimulus** | `evt.pin` | `evt.hold` (**2** or **300**) | the `stim` strata (1,920) |

**The selection is by the DIRECTIVE and never by the outcome**, which is
precisely what stops the question being answered in the instrument.  `evt.hold`
is what the host ASKED for; `hold_applied` equals it on **1,920 of 1,920**
seeds (12-bit rig register, F46), so the two readings coincide and no choice
between them is being made here.

**A run of length `hold` ± 1 must EXIST on the named pin, and every run on that
pin must have that length.**  No run is selected from among several and none is
discarded — with zero runs there is nothing that equals the hold, and the
directive FAILS.  §20.4 reports the strict *exactly-one-run* reading beside it
so the choice can be audited.

### 20.2 THE UNEVALUABLE CASE, DECLARED AND COUNTED — **NOT GUESSED**

> **Where two schedulers name the SAME pin their runs can merge.  That seed is
> declared UNEVALUABLE and is COUNTED.**

It is a property of the **directive pair** and is decided without reading a
row, so it cannot select on the answer.  In this corpus it is exactly the
**NMI-stimulus** seeds, where the stimulus and the terminator are both on
`pin_nmi`.

**MEASURED: 561 of 3,840 seeds — 14.6 % of the corpus and 29.2 % of the 1,920
event seeds.**  That is the frozen population's own NMI count (§2.3: INT 1,359
/ NMI 561), reproduced exactly.  Split: **census 146 / enriched 415**;
**soup 277 / raw 284**.

### 20.3 A FINDING ABOUT THE CORPUS'S EVENT ASSIGNMENT — **`hold = 300` IS STRUCTURALLY IMPOSSIBLE ON AN NMI SEED**

Asked for by the coordinator, and it is sharper than a fraction.  The stimulus
pin and the stimulus hold are **not independent** in this corpus:

| | `hold = 2` | `hold = 300` |
|---|---|---|
| **INT** (`pin` 0) | **680** | **679** |
| **NMI** (`pin` 1) | **561** | **0** |

**Every one of the 561 unevaluable seeds carries `hold = 2`, and not one NMI
seed anywhere in the corpus carries `hold = 300`.**  It is not chance — it is
two registered rules meeting:

* `fuzz_campaign.build` sets `hold = 300` **iff the program contains a HALT**
  (§2.3 states this);
* `gen_soup` emits a HALT **only when `evt_pin` is INT or POLL**
  (`sw/gen_soup.py:723`, `if (not halt_used and self.evt_pin in (0, 2) ...)`),
  and this corpus has **0 POLL seeds** (§9).

So `has_halt` ⟺ INT, measured **679 / 679 and 561 / 561 with no exceptions**,
and all 679 are **soup** — the raw tier declares no HALT at all.

**WHAT IT COSTS C-6(b), STATED PLAINLY.**  The **NMI pin's stimulus hold is
never scored per-directive** — but it never carried more than one value to
score, so **no hold diversity is lost**.  The evaluated population still
carries **three distinct hold values** (§20.4), and `pin_nmi` itself is scored
on **3,279** directives through the terminator.  **What is genuinely not
proven by this corpus is that the rig applies a 300-clock hold ON THE NMI PIN**
— that cell is empty by construction, and C-6's own control leg (§6 clause (a),
`cmd_control`) is where it would be proved.  Registered here rather than
discovered later.

### 20.4 THE CLAUSE, EVALUATED — `bars/C-6/measured/c6b`

| | |
|---|---|
| seeds with `hold_rows` | **3,840** |
| **UNEVALUABLE (shared pin)** | **561** |
| **DIRECTIVES EVALUATED** | **4,638** (3,279 terminator + 1,359 stimulus) |
| **PASS** | **4,636** |
| **FAIL** | **2** |
| runs on the named pin | `term:1` **3,279** · `stim:1` **1,356** · `stim:2` **1** · `stim:0` **2** |
| distinct holds evaluated | **3** — `20` (3,279) · `300` (679) · `2` (680) |
| strict *exactly-one-run* reading | **3** fail |

**THE TWO FAILURES ARE THE SAME FAILURE, AND THE RIG'S OWN STICKY BIT AGREES
WITH THE ROWS.**  `fz2e/528016` (raw, `fix1`, INT, `delay` 1,536, `hold` 2) and
`fz2e/530063` (raw, `fix3`, INT, `delay` 710, `hold` 2): **`pin_int` carries no
run at all**, and `term.fired` is **0** on both — bit 0, the stimulus
scheduler's own sticky bit, is clear.  **A directive was armed and did not
appear on the pin, and the rows and the STATUS readback say so independently.**
That is what C-6 exists to detect, and it is reported rather than smoothed.

**THE THIRD SEED, AND WHY THE READING DOES NOT DECIDE THE CLAUSE.**  Under the
strict *exactly-one-run* reading a third directive fails: `fz2c/411076` (raw,
INT, `hold` 2) carries **two** runs on `pin_int`, **both of length exactly 2**.
Its `term.fired` is **1** — the terminator's bit is clear while the stimulus
bit is set — and §18.5's D-3 records the same seed class: **the board image
re-runs**, so a one-shot scheduler can appear twice in one 4,063-row capture.
Both readings give **the same clause verdict** and the same order of magnitude
(2 vs 3 of 4,638), which is the evidence that A-8's verdict does not turn on
this choice.  **Neither reading is chosen after looking at which seeds it
catches**: §20.1 registers the "every run must match" form and §20.4 reports
the other beside it, permanently, in the scored artifact.

### 20.5 C-6'S VERDICT, AS REGISTERED

> **C-6 READS `NOT SCOREABLE`, AND A-8 DOES NOT CHANGE THAT.**

C-6 has **three** clauses and all three are required.  A-8 makes clause **(b)**
evaluable and **it does not pass**: 2 of 4,638 directives fail. Clauses **(a)**
(EVT2/EVT3_CFG / TVEC / VECCTL round-trip on the readback path) and **(c)**
(interception at ≥ 2 distinct `TVEC` values with the `vecsub_en = 0` negative
control) are **BOARD legs**, `fz2_w1.cmd_control` is unimplemented on this tree
and returns 2, `sw/testdata/fz2/fz2_control.json` does not exist, and **this
sitting is offline by instruction**.

**So C-6 is NOT SCOREABLE for a DIFFERENT reason than before**, and both halves
of that sentence are load bearing: O-2b is **CLOSED** — the clause is evaluable,
evaluated and reported — while the bar itself stays **NOT SCOREABLE** on
clauses (a) and (c), exactly as §14.5 and §18.2 said it was.  **It is not
improved and must not be read as improved.**  Had the control leg existed and
passed, clause (b)'s 2 failures would make C-6 read **MISSED**, not MET.

### 20.6 WHAT A-8 CHANGES IN THE TREE

* `sw/fz2_w1.py` — `cmd_bars`' C-6 block: the per-directive evaluation, the
  UNEVALUABLE count with its seeds, the runs-per-directive distribution, the
  holds actually evaluated, the failing detail, and the strict single-run
  cross-check, all banked under `bars/C-6/measured/c6b`.  `hold_rows_exact` /
  `hold_rows_off` now count PER DIRECTIVE and `pin_level_clause` carries the
  ruling instead of O-2b's "NOT EVALUABLE" string.  **C-6's `registered` text is
  not touched, and neither is its verdict expression.**
* This document, appended.
* **No other file.**  No detector, no discard class, no capture path, no
  constant, no board, no flash, no Quartus.

### 20.7 THE RESCORE AS RUN — `sw/testdata/fz2/fz2_bars.json`, 2026-08-09T18:01:29Z

`python3 sw/fz2_w1.py bars`, offline, off the same banked results §18 and
§19.8 scored.  **No capture, no board.**

**`FZ2 BARS: 7/11 MET   NOT MET: C-1, C-3, C-6, C-11`** — unchanged.
**A-8 moved no bar's verdict, including C-6's.**

**LEAF FOR LEAF against the §19.8 artifact: 616 leaves → 660, 48 differing —
47 of them inside `bars/C-6/measured` and 1 is `ts`.**  `bars/C-6/verdict`
(`NOT SCOREABLE`), `bars/C-6/registered` and `bars/C-6/statement` are
**byte-identical**; `holds_in_corpus` is unchanged at `{2: 1241, 300: 679}`;
`control_leg` is still `null`.  What moved inside `measured` is
`hold_rows_exact` **0 → 4,636** and `hold_rows_off` **0 → 2** (now counted PER
DIRECTIVE), `pin_level_clause` from O-2b's *"NOT EVALUABLE"* string to the
ruling, and the new `c6b` object.  **C-1's, C-11's and every other bar's
`measured` are identical**, so A-8 touched nothing outside its own clause.

**REPORTED AS REGISTERED: C-6 is NOT SCOREABLE, clause (b) does NOT pass at
2 / 4,638, and 561 seeds are UNEVALUABLE.**  §20.5 is the verdict and it is
unchanged by this run.

---

## §21 C-11 — THE BANK PROMOTION IS RUN, AND THE BAR READS **MET**

**Executed 2026-08-09/10, offline.**  This is **not an amendment**: §4.1, §4.2
and C-11 registered the rules and the clause before the first capture and
nothing about them is edited here.  C-11 read `NOT SCOREABLE` through §12.1,
§14.1, §18.2 and §20.7 for one reason — *"the bank promotion was not run this
sitting"* (`census_banked` **0** of **480**).  It has now been run.

### 21.0 A DISAGREEMENT BETWEEN THE TASK AND THE CODE, REPORTED FIRST

The task described C-11 as unscoreable *"only because the promotion was never
executed"*.  **That was not the whole of it, and the code is the authority.**
`fuzz_bank.promote` implements §4.2's **divergence-driven quota rule and
nothing else** — every FUNCTIONAL, provenance QUARANTINEs capped at 20,
unexplained TIMING capped at 10 per signature, first 50 per KNOWN_ACCEPTED
class, a 1-in-50 CADENCE sample, 100 SUCCESS ballast.  **§4.1's FROZEN
ARITHMETIC RULE did not exist anywhere in the tree**, so running the promotion
as it stood would have produced a census bank chosen by verdict and C-11's
first clause — *"the census bank equals the 480 enumerated seeds, seed for
seed"* — would have read **MISSED**, with a selection artefact banked inside
it.  Building the frozen path is **executing a registered rule**, not inventing
one, and it is the only way that clause can be met.

**A second trap, found before it cost anything.**  `check_fuzz_bank`
re-derives every banked image from `(cid, k, ov)`, and `promote` banked ONE
campaign-wide `ov`.  This corpus uses **a different `ov` in each of its 48
strata** (§2.4), so a flat dict would have regenerated a different image for
47 of them and been reported as **GEN-DRIFT in the seed** rather than as a
defect in the banker.  `ov` is now resolved **per seed** from the seed's own
stratum.

### 21.1 THE COST, MEASURED BEFORE A BYTE WAS WRITTEN

`python3 sw/fz2_w1.py bank --dry-run` selects and compresses the identical
entry the banker writes and reports it against `fuzz_bank.CAP_MB`:

| | seeds selected | compressed | vs `CAP_MB` = 25 |
|---|---|---|---|
| `fz2c` (frozen rule) | **480** | **11.06 MB** | **inside** |
| `fz2e` (quota rule) | **143** | **3.38 MB** | **inside** |

**Neither would trip `_capped`, so §4.3's registered HALT was not reached.**
It is armed in the driver regardless: `cmd_bank` measures first, and on a
`would_cap` it writes nothing, prints §4.3's response — *halt, report, raise
`CAP_MB` in its own commit, re-bank the whole population* — and exits 2.  A
truncated bank is a prefix of the promotion order and therefore a selection
artefact; the cap is not discovered by hitting it.

⚠ **`CAP_MB` CAPS THE PROMOTED BANK, NOT `captures/`** — §17.7's erratum,
carried forward into the code's own comment.  The live capture directories hold
**33 MB** with nothing enforcing anything, and the 25 MB bar is on a different
artifact.  §4.3's estimate of ~22 KB per banked entry was good: the measured
figures are **23.6 KB** (`fz2c`) and **24.2 KB** (`fz2e`).

### 21.2 THE PROMOTION AS RUN

`python3 sw/fz2_w1.py bank`, offline, 284 s:

| | banked | of results | bytes | `_capped` | rule |
|---|---|---|---|---|---|
| `fz2c` | **480** | 960 | 11.10 MB | **0** | `frozen_rule` **480** — no other reason appears |
| `fz2e` | **143** | 2,880 | 3.39 MB | **0** | `rule_first50:open_bus` 50 · `success_ballast` 68 · `functional` 17 · `timing_unexplained` 3 · `rule_first50:lea-mod3` 3 · `cadence_sample` 2 |

**THE PROMOTED BANK REPLAYS SELF-CONSISTENTLY**, checked rather than assumed —
`check_fuzz_bank.replay_classify` re-run over all **623** newly banked entries:
**623 stable, 0 improved, 0 worse, 0 GEN-DRIFT, 0 errors.**  The
banked-vs-replayed verdict matrix is diagonal: QUARANTINE 168 · TIMING 156 ·
FUNCTIONAL 128 · KNOWN_ACCEPTED 82 · SUCCESS 81 · ASSERT_PARK 8.

### 21.3 THE BAR, AS REGISTERED

| clause | registered | measured | |
|---|---|---|---|
| census bank == the 480 enumerated seeds | seed for seed | **480 / 480, `census_exact` true** | **MET** |
| `_capped` | **0** on either cid | **0** and **0** | **MET** |
| standing bank | **≤ 3,500** | **623** | **MET** |
| seeds in both banks | **0** | **0** | **MET** |

> **C-11 READS `MET`.**  `FZ2 BARS: 8/11 MET   NOT MET: C-1, C-3, C-6` —
> the first time this corpus has moved a bar's verdict since §14.

### 21.4 A FINDING ABOUT THE THIRD CLAUSE, AND IT IS FOR THE COORDINATOR

**"Standing bank ≤ 3,500" is scored as `fz2c` + `fz2e` = 623, because that is
what `fz2_w1.cmd_bars` computes AND what §4.3's own table computes** (*"standing
bank ≤ ~1,630 … vs the ≤ 3,500 ceiling"*).  **It is not what §2.1's rationale
describes.**  §2.1 justifies the number with *"every banked seed is replayed on
every gate run"*, and the thing that is replayed on every gate run is
`tests/v30/fuzz_bank/*/seeds/*.json.gz` — `check_fuzz_bank`'s own glob.

**Measured: that bank was 3,242 seeds and is now 3,865** (mc1 1,295 · mc2 1,294
· t30-raw 568 · t30-brkem 85 · **fz2c 480 · fz2e 143**).  Under §2.1's reading
the clause is **breached by 365 seeds**; under §4.3's arithmetic and the
scorer's it is met with 2,877 to spare.

**NO BAR IS RE-READ HERE AND NOTHING IS RESCORED ON THE OTHER READING.**  The
clause is scored as the document's own table and its own scorer compute it, and
the discrepancy is reported rather than resolved: **which of the two the ≤ 3,500
ceiling was meant to bound is a decision about a registered bar and belongs to
the coordinator.**  The gate's wall time is the thing the number was protecting,
and it has gone up by **19.2 %**.

### 21.5 WHAT §21 CHANGES IN THE TREE

* `sw/fuzz_bank.py` — `promote` gains `only_ks` (the frozen rule), `ov_of`
  (per-seed overrides) and `dry_run` (measure, write nothing); the quota rule
  is lifted verbatim into `_quota_select` and the entry body into `_entry`,
  which the writer and the measurement now share so the two cannot drift.
  **All three parameters default to the historical behaviour, so every existing
  caller is unchanged**, and `CAP_MB` is not touched.
* `sw/fz2_w1.py` — the `bank` subcommand: measure, halt-or-write, refuse to
  promote over a bank that already exists.
* `tests/v30/fuzz_bank/fz2c/`, `tests/v30/fuzz_bank/fz2e/` — the 623 banked
  entries, their signature indices, shards and manifests; `sig_ledger.json`
  updated by `promote`'s own `_update_ledger`.
* `sw/testdata/fz2/fz2_bank.json` — the promotion record.
* This document, appended.

**No board, no flash, no Quartus, and no capture.  No bar's text or value
moved.**

### 21.6 THE BARS AFTER §21 — `sw/testdata/fz2/fz2_bars.json`, 2026-08-09T18:10:25Z

**`FZ2 BARS: 8/11 MET   NOT MET: C-1, C-3, C-6`**

**LEAF FOR LEAF against the §20.7 artifact: 660 leaves → 660, 6 differing** —
`census_banked` **0 → 480**, `census_exact` **False → True`,
`enriched_banked` **0 → 143**, `total` **0 → 623**, `bars/C-11/verdict`
**`NOT SCOREABLE` → `MET`**, and `ts`.  **Nothing outside `bars/C-11`
moved**: C-1 is still `MISSED (rate clauses UNVALIDATED -- A-5)` with
UNDISPOSITIONED **27**, C-6 is still `NOT SCOREABLE`, C-3 is still `MISSED`
at **2** runtime PS3 captures, and both populations' three decompositions are
identical.

**THE ACCEPTANCE CRITERION OF §8.2 IS STILL NOT MET**: three bars are not MET
and the catch-all is not empty.

---

## §22 — THE COORDINATOR'S RULING ON §21.4, AND THE v1 CORPUS RETIRED BY STATUS

**2026-08-09, branch `fuzz-v2-on-relanding`.  Offline: no board, no flash, no
Quartus, no capture.  The full entry is `docs/notes/invalidation_ledger.md`
§ SUP-1; this section records only what changes in THIS document's bar.**

### 22.1 THE RULING

§21.4 reported that C-11's third clause — *"standing bank ≤ 3,500"* — was scored
two ways: as `fz2c + fz2e` = **623** by §4.3's table and by `fz2_w1.cmd_bars`,
and as `check_fuzz_bank`'s replayed glob = **3,865** by §2.1's own rationale,
which breaches the ceiling by **365**.  It did not resolve the discrepancy,
because which population a registered bar bounds is a decision about the bar.

> **RULING: §2.1's reading is correct.**  The ceiling bounds the population
> REPLAYED ON EVERY GATE RUN, because gate wall time is the cost the number
> exists to bound.

### 22.2 AND THE REPAIR IS NOT TO SHRINK `fz2`

**3,242 of those 3,865 seeds are the v1 corpus the user discarded outright**
(*"I do not care about the old fuzz data, discard it, move on"*), replayed on
every gate run for **+19.2 % wall time and zero information** about the
population this campaign develops against.  They are retired **BY STATUS, NOT BY
LOCATION**: a `status: "SUPERSEDED"` key in each of the four campaigns' own
`manifest.json`, honoured by every consumer through one predicate
(`sw/bank_status.py`), reachable in full with `--include-superseded`.
**Nothing was moved, renamed or deleted** — the captures are true silicon and
stay exactly where they are, byte for byte.  **No rig defect is alleged**; this
is a SUPERSESSION, filed in its own register, and `f46_invalidated` is **0**
bank-wide before and after.

### 22.3 WHAT MOVES IN C-11

`fz2_w1.cmd_bars` now scores the third clause on **`replayed`** — the §2.1
population, computed by `bank_status.seed_paths()` — and records BOTH readings
in `measured`, so they can never silently diverge again:

| clause | registered | before | after |
|---|---|---|---|
| census bank == the 480 enumerated seeds | seed for seed | 480/480, `census_exact` true | **unchanged** |
| `_capped` | 0 on either cid | 0 and 0 | **unchanged** |
| standing bank, §4.3's reading (`total`) | ≤ 3,500 | 623 | **623** |
| standing bank, §2.1's reading (`replayed`) — **THE SCORED ONE** | ≤ 3,500 | **3,865 — BREACHED by 365** | **623 — MET** |
| seeds in both banks | 0 | 0 | **unchanged** |

C-11's verdict was **MET** and is **MET**; what changed is that it is now MET on
the reading the clause was written for.  **`FZ2 BARS: 8/11 MET   NOT MET: C-1,
C-3, C-6` — the same 8 and the same 3**, and against the §21.6 artifact
**only `bars/C-11` and `ts` differ**: C-11 gains `replayed` 623,
`all_banked_incl_superseded` 3,865 and `superseded_cids`
`[mc1, mc2, t30-brkem, t30-raw]`, and its `registered` string names the reading.
**No other bar's `measured` changed by one character.**

### 22.4 A FINDING THE RULING DID NOT ANTICIPATE — **THE BEFORE WAS RED**

§21.4 costed the v1 corpus at *"+19.2 % wall time and zero information"*.
**Measured, the cost was higher: on this branch the 3,865-seed population FAILS,
and the entire failure is the v1 corpus.**

```
check_fuzz_bank: FAIL | 3865 banked seeds | stable 623 improved 0 worse 0
                      | gen_drift 3157 regen_err 85 | float-floor 0
                      | new-sig TIMING 0                        (1,580 s)
```

`mc1` 1,295 + `mc2` 1,294 + `t30-raw` 568 = **3,157 GEN-DRIFT**; all 85
`t30-brkem` seeds raise `brkem_high: refused -- fuzz-v2 eliminates 8080 entry
unconditionally (plan D9)`; the 623 fz2 seeds are the only stable ones.

**THE CAUSE IS THIS DOCUMENT'S OWN PLAN D9** (`sw/fuzz_campaign.py`,
`e45772e4e0` … `b155b6166b`): the `0F` scrub is unconditional at all three build
sites, so every v1 image regenerates to a different sha256, and `brkem_high` is
refused outright. Both are deliberate and correct. Their side effect is that
**the v1 corpus stopped being replayable the day D9 landed** — which is exactly
what GEN-DRIFT is designed to report.

So the retirement takes `check_fuzz_bank` **FAIL → PASS** and cuts **83.2 %** of
its wall time (**1,580 s → 266 s**). Neither is a repair: nothing was repaired,
a corpus the generator no longer builds stopped being replayed. And the two
`timed_fuzz` v1 fuzz-bank ratchets were **already unmeasurable on this branch
before SUP-1** — with `--include-superseded` they select all 3,242 seeds and
every one categorises `GEN_DRIFT` (`--bank mc1 --limit 40` → `GEN_DRIFT=40
SCORED 0`). Honouring status in `timed_fuzz.seeds_of` costs them nothing D9 had
not already taken; they are re-derivable only on a tree whose generator predates
fuzz-v2 (merge-base `7e949925b7`, or `master`).

**"Reachable on request" therefore means the SEEDS, not the REPLAY.**
`bank_status.seed_paths(include_superseded=True)` is set- and order-identical to
the historical glob and returns all 3,865 path for path; it cannot return a
replay the generator can no longer produce, and SUP-1 does not claim it can.

### 22.5 WHAT §22 CHANGES IN THE TREE

* `sw/bank_status.py` — NEW, a leaf module (stdlib only): `bank_status`,
  `is_superseded`, `bank_cids`, `seed_paths`, `dropped_note`, and a `report`
  main.  Absence of a `status` key means `ACTIVE`, so no existing bank and no
  future promotion has to be edited.
* `tests/v30/fuzz_bank/{mc1,mc2,t30-raw,t30-brkem}/manifest.json` — five keys
  added to each.  **No seed file, sig index, result shard or `chip_rows` was
  touched.**
* `sw/check_fuzz_bank.py`, `sw/timed_fuzz.py`, `sw/sm3_sigctl.py` — the glob is
  replaced by the predicate; each gains `--include-superseded`; each PRINTS the
  exclusion on its own line.
* `sw/inv1_recapture.py` — `include_superseded=True`, explicitly: INV-1's
  population is entirely inside the retired banks and the two predicates are
  independent.
* `sw/tacensus.py`, `sw/q1diff.py`, `sw/q2census.py`, `sw/q2law.py` —
  `include_superseded=True`, explicitly, for the same reason: measurement tools
  whose subject IS the v1 corpus, which gate nothing.
* `sw/fz2_w1.py` — C-11's third clause, as above.
* `docs/notes/invalidation_ledger.md` — the SUPERSEDED register and § SUP-1.
* `docs/notes/standing_gates.md` — `check_fuzz_bank`'s population and its
  FAIL → PASS, and the two `timed_fuzz` v1 fuzz-bank ratchets, each row now
  stating that its figure is **not measurable on this branch** and why (§22.4).

**No board, no flash, no Quartus, and no capture.  No bar's text moved, and no
bar's `measured` moved except C-11's.**

---

## §23 AMENDMENT A-9 — §16.2's VALIDATION POPULATION IS ENUMERATED AND FROZEN, **BEFORE IT IS CAPTURED**

**Written 2026-08-09, branch `fuzz-v2-on-relanding` at `d1d9f168d4`, and
COMMITTED — with the frozen population file and its sha256 — BEFORE ANY BOARD
CONTACT OF THIS SITTING.**  Appended, never back-edited.

**NO BAR MOVES.**  C-1 … C-11 keep their text and their values character for
character, **including A-5's re-registered 90.0 / 75.0 and E-1c = 0**.  No new
discard class is created, no detector changes, no constant moves, and
`SEEDS_SHA256` / `SEED_LIST_SHA256` are untouched — the 3,840-seed corpus is not
re-derived, not re-captured and not re-scored by this amendment.

### 23.0 WHAT THIS IS, IN ONE PARAGRAPH

§16.2 registered, before the answer could be known, what would lift the
`UNVALIDATED` marker A-5 put on C-1's two rate clauses.  This amendment
**enumerates and freezes that population and nothing else**.  It is written and
committed first precisely so that the capture that follows cannot be described
afterwards as having been designed around its own result.

### 23.1 THE POPULATION — the CENSUS grid, moved to the RESERVED band

`cid = fz2v`, `k_base = 600000`, `K_STRIDE = 1000`, `n = 80` — **§2.1's census
grid, unchanged in every axis, at a different base.**

| i | pop | cid | tier | evt | wait | k range | n |
|---|---|---|---|---|---|---|---|
| 0 | val | fz2v | soup | noevt | fix0 | 600000-600079 | 80 |
| 1 | val | fz2v | soup | noevt | wrand3 | 601000-601079 | 80 |
| 2 | val | fz2v | soup | noevt | wvec-uni | 602000-602079 | 80 |
| 3 | val | fz2v | soup | stim | fix0 | 603000-603079 | 80 |
| 4 | val | fz2v | soup | stim | wrand3 | 604000-604079 | 80 |
| 5 | val | fz2v | soup | stim | wvec-uni | 605000-605079 | 80 |
| 6 | val | fz2v | raw | noevt | fix0 | 606000-606079 | 80 |
| 7 | val | fz2v | raw | noevt | wrand3 | 607000-607079 | 80 |
| 8 | val | fz2v | raw | noevt | wvec-uni | 608000-608079 | 80 |
| 9 | val | fz2v | raw | stim | fix0 | 609000-609079 | 80 |
| 10 | val | fz2v | raw | stim | wrand3 | 610000-610079 | 80 |
| 11 | val | fz2v | raw | stim | wvec-uni | 611000-611079 | 80 |

> **960 seeds — 480 soup and 480 raw.**  §16.2 registers *"size ≥ 480 seeds …
> split across both tiers so each clause is scored on its own mechanism"*; this
> population gives **each clause its own 480**, which is the census's own size
> **per tier**, and it costs about three minutes of board time at the corpus's
> measured 5.8 seeds/s.

```
VAL_CID = fz2v
VAL_K_BASE = 600000
VAL_N = 960
VAL_SEED_LIST_SHA256 = 5d83b3a9b6aa7907cbef01eae7f33223b024f1fa9cdf1d56ab879e24925d81be
VAL_SEEDS_SHA256 = 546b23ebd28c22851a8d20b576b4134406028fbdc252f27750a843755234f749
```

**Why `k ≥ 600000` and not a fresh cid at 400000.**  §2.2's last paragraph
reserved that band in advance, in this document, before the corpus was
captured: *"RESERVED AND NOT TO BE USED BY THIS CORPUS: `k ≥ 600000`.  Any later
directed or victory tranche draws from there and is therefore disjoint from
every seed above by construction — §64.1's disjoint-validation discipline,
applied to the corpus rather than to a law."*  This is that tranche.  The
disjointness is a property of the layout; `fz2_w1`'s own `assert max(s["k_lo"] +
s["n"] for s in STRATA) < K_RESERVED` is the other half of it and already stood.

**What the frozen population contains, counted in advance** (from
`sw/testdata/fz2/fz2v_population.json`, `freeze`, 2.7 s):

| | soup | raw |
|---|---|---|
| seeds | 480 | 480 |
| with a stimulus event | 240 | 240 |
| … INT / NMI / POLL | 177 / 63 / 0 | 182 / 58 / 0 |
| … `hold = 2` / `hold = 300` | 63 / 177 | 240 / 0 |
| `has_tf` | 23 | 0 |
| `has_halt` | 177 | 0 |
| raw whole-image mode | 0 | 342 |
| `TERM_CLOCKS` range | 2,196 … 3,154 | 2,196 … 3,154 |

§20.3's structural finding reproduces exactly on this population and is
therefore **not a property of the corpus's own draw**: `hold = 300` ⟺ `has_halt`
⟺ INT, 177/177 in soup and **0 NMI seeds at `hold = 300` anywhere**, raw
declaring no HALT at all.

### 23.2 ZERO OVERLAP, CHECKED THE WAY C-11 CHECKS IT — AND THREE WAYS BESIDES

`python3 sw/fz2_val.py overlap`, run before the capture:

| check | result |
|---|---|
| `(cid, k)` vs the frozen 3,840 | **0** |
| `(cid, k)` vs the banked `fz2c` bank (480) — C-11's own intersection | **0** |
| `(cid, k)` vs the banked `fz2e` bank (143) | **0** |
| raw `k`, cid ignored, vs the frozen 3,840 | **0** |
| **composed image sha256 vs all 3,840 corpus images** | **0** |
| the 960 validation images are pairwise distinct | **0** collisions |
| validation seeds below `K_RESERVED` | **0** |

**AND ONE CHECK THAT WAS WRONG AND IS REPORTED RATHER THAN QUIETLY DROPPED.**
A `cfg_hash` intersection was written as a FAIL condition and **fired at 36**.
It is not a seed identity: `derive_case` hashes the CONFIGURATION AXES
(`fuzz_campaign.py:264` — tier, waits, `nmax`, `evt`, `wvec`), while the program
comes from `build`'s RNG keyed on the string `f"{cid}/{k}"`.  **The control that
settled it is the corpus doing it to itself: the frozen 3,840 carry only 2,969
distinct `cfg_hash`es — 871 internal collisions.**  The check is now REPORTED
with that control beside it and scores nothing; the identity checks are the
`(cid, k)` key, the raw `k` and the composed image, and all three are 0.

### 23.3 WHAT IS SCORED, AND WHAT IS NOT

**Scored — the two clauses §16.2 names, and only those:**

| clause | registered (A-5) | scored on |
|---|---|---|
| **E-1a soup** | **≥ 90.0 %** | the 480 soup seeds' terminator-reached rate |
| **E-1b raw** | **≥ 75.0 %** | the 480 raw seeds' terminator-reached rate |

The rate is C-1's own: **terminator-reached over the FULL stratum, discards
included** (§5.3).  `sw/fz2_val.py` imports `E1` from `sw/fz2_w1.py`, so the two
numbers exist in exactly one place in the tree and this scorer cannot hold a
different pair from the corpus scorer's.

**NOT scored: E-1c.**  §16.2 names the two RATE clauses.  E-1c is C-1's
anti-vacuity floor, it is measured on the corpus at 27, and this population
cannot and does not move it.  The validation population's own discard census and
undispositioned count are **REPORTED** beside the rates, because a containment
rate quoted without its residue is half a number — and they gate nothing here.

**NOT banked.**  `fz2v` is never handed to `fuzz_bank.promote`, `keep_rows_every`
is 0, and C-11's three populations (`census_banked`, `enriched_banked`,
`replayed`) are untouched by construction.

### 23.4 THE INSTRUMENT IS PROVED TO BE THE CORPUS'S BEFORE IT SCORES ANYTHING

`fz2_val score` runs its own rate function over `fz2c` and `fz2e` FIRST and
compares all four cells against the **committed** `sw/testdata/fz2/fz2_bars.json`
— `n`, `reached` and `pct` — and **REFUSES to score `fz2v` if any of them
differs**.  A validation taken with a second, subtly different scorer would be
validating the scorer.  The four cells it must reproduce are the current
committed ones:

| cell | committed |
|---|---|
| census / soup | 473/480 = **98.54 %** |
| census / raw | 403/480 = **83.96 %** |
| enriched / soup | 1424/1440 = **98.89 %** |
| enriched / raw | 1213/1440 = **84.24 %** |

⚠ **These are NOT §16.8's four numbers, and the difference is not an erratum in
either place.**  §16.8 recorded 83.54 / 83.61 on the raw tier; that artifact was
scored **before** the §18 A-6 re-capture, which re-took the corpus.  A-5's two
values were selected against 83.54 / 83.61 and the population they were selected
on has since been re-captured at 83.96 / 84.24.  **This changes nothing about
A-5's provenance — the values were still chosen after seeing that population's
numbers — and it is why §16.2's disjoint measurement, not a re-reading of the
corpus, is the thing that validates them.**

### 23.5 THE REGISTERED OUTCOMES — both of them, written before the capture

> **PASS** — both clauses MET on this population.  Then, and only then, the
> `UNVALIDATED` marker comes off: `fz2_w1._c1_verdict` stops appending
> `(rate clauses UNVALIDATED -- A-5)`, C-1's `registered` string records the
> validation and names this population, and **the two values become quotable**.
> C-1's own verdict does **not** change — E-1c is 27 against 0 and remains its
> sole blocker (§16.4).
>
> **FAIL** — either clause MISSED.  Then **A-5's re-registration is REFUTED on
> its first disjoint measurement**, the marker STAYS, the failure is recorded in
> this trail, and **NOTHING IS ADJUSTED**: §16.2's third bullet forbids a second
> re-registration, and a bar lowered twice to meet two populations is a record of
> fitting.

**No third outcome is available, and no clause is scored per stratum, per wait
source or per event class.**  Two numbers, two bars, as §5.2 registered.

### 23.6 WHAT A-9 CHANGES IN THE TREE

* `sw/fz2_val.py` — NEW.  `strata` / `freeze` / `overlap` / `preflight` /
  `capture` / `score`.  It imports the grid axes, the overrides, the
  `TERM_CLOCKS` formula, `div_guard`, `board_idle`, `_run_args`, `_done_ks` and
  **`E1`** from `fz2_w1`; it re-implements none of them.
* `sw/testdata/fz2/fz2v_population.json` + `.sha256` — the frozen 960, committed
  **with this section and before the capture**.
* This document, appended.
* **No other file.**  No bar, no detector, no discard class, no constant, no
  board, no flash, no Quartus, and nothing in `fz2_w1.py` — the marker-removal
  edit, if the validation earns it, is a SEPARATE commit made after the score.

### 23.7 THE ERA THIS CAPTURE IS TAKEN IN, STATED BEFORE IT IS TAKEN

The board carries **FLASH #12** — `nec_test_ucore.sof`
`8db6dadf5c4c5c62…`(sha256 `8db6dadf5c4c621ceb6bac9b0935146a4193fa3709051636a260e451e0bee205`),
built from `b629296e3a`, quartus receipt `27fb750f925c…` — and **it is not
re-flashed by this sitting.**  HEAD is `d1d9f168d4`, and **one RTL landing has
occurred since that bitstream was built: the 8F ghost READ.**  Three things
follow, and each is checked rather than assumed:

1. **The rig is not affected.**  `fz2_w1.resident_rig_gap()` compares the three
   files the fuzz-v2 directive lives in — `hps_axi_slave.sv`, `nec_bus.sv`,
   `system_large.sv` — against the pinned `.sof`'s own receipt inputs, file for
   file, and the gap is **EMPTY**.  The 8F ghost read is in `hdl/rtl/ucore/`.
2. **The socket leg cannot be affected by any bitstream.**  It is the real
   µPD70116 in its socket at `use_core=0`; the rates this population scores are
   computed from `arch_ok`, which is the SOCKET leg's own dump.  **The
   validation measurement is a silicon measurement and the FPGA is transport.**
3. **The fabric-core leg is one landing behind, and is scored against its own
   bitstream's tree** — the standing rule.  Its figures (`bad_rows`,
   `arch_match`) are reported here as a decomposition and **gate nothing in this
   amendment**; they may not be quoted against HEAD's RTL.

**No re-flash is required for this sitting and none is taken.**

**AND ONE THING THE ERA STAMP DOES NOT SAY, RECORDED BEFORE THE CAPTURE RATHER
THAN DISCOVERED IN IT.**  `fuzz_campaign._gen_git()` is `git rev-parse --short
HEAD` and is blind to an uncommitted edit.  At the start of this sitting the
working tree carries **UNCOMMITTED CHANGES TO `hdl/rtl/ucore/v30u_biu.sv` and
`hdl/rtl/ucore/v30u_eu.sv`** — a prior sitting's work in progress, not this
one's, and not touched by it.  For a SOCKET capture the substance is unaffected
(no RTL file, Verilator binary or bitstream is in the loop of a `use_core=0`
run), but a stamp naming `d1d9f168d4` would otherwise be a claim about a tree
that is not `d1d9f168d4`.  So `fz2_w1.tree_dirty()` records **every dirty
tracked file with its sha256** into `fz2v_preflight.json`, `fz2v_capture.json`,
`fz2_control.json` and `fz2_deadint.json`.  **The delta is recorded beside the
stamp; the stamp is not widened and the tree is not tidied.**

---

## §24 C-6's BOARD LEGS — THE PLAN AND ITS PASS CONDITIONS, REGISTERED BEFORE THE BOARD

**Written 2026-08-09 and COMMITTED BEFORE ANY BOARD CONTACT OF THIS SITTING.**
This is **not an amendment**: C-6's registered text is not edited, character for
character, and neither is A-8's ruling on clause (b).  §6 registered three
clauses and §20.5 recorded that two of them are board legs which had never been
run because `fz2_w1.cmd_control` was a stub.  This section says what the legs
are before they are run, so that what comes back cannot be chosen afterwards.

### 24.1 THE THREE CLAUSES AND WHERE EACH IS ANSWERED

| clause | registered text | where it is answered |
|---|---|---|
| **(a)** | `EVT2_CFG` / `EVT3_CFG` / `TVEC` / `VECCTL` **round-trip on the readback path** | `control` legs **R1** (RBCHECK) and **R2** (a live directive's own readback), board |
| **(b)** | a **PIN-LEVEL proof by counted rows at ≥ 2 hold values** | already EVALUATED offline under A-8, **4,636 / 4,638**, plus `control` legs **P1-P5** |
| **(c)** | **interception proven on the rows at ≥ 2 distinct `TVEC` values**, with the `vecsub_en = 0` negative control **not** terminating | `control` legs **V1**, **V2** and **N1**, board |

### 24.2 THE LEGS, AND WHAT EACH MUST SHOW

Directed probes on a **fixed** image — a NOP sled ending in `JMP $`, the
`fz2_tbsys` shape — **not corpus seeds**.  Every probe is `use_core=False`,
every probe is preceded by `div_guard`, and every probe's full per-clock rows
are retained with a sha256 beside them.

| leg | directive | MUST SHOW |
|---|---|---|
| **R1** | none | `rig_readback_check()` writes **two distinct values** into every fuzz-v2 register and reads each back; the board names the registers it round-tripped |
| **R2** | a live run at `TVEC_B`, `vecsub` set, two schedulers armed | the rig's own `rb=` readback repacks **exactly** to what was sent — `EVT_ADDR[n]`, `EVT_CFG[n]`, `TVEC`, `VECCTL`; a disagreement is `RigMismatch` and a HARD STOP |
| **P1** | INT, `hold = 2` | exactly **one** run on `pin_int` of length **2 ± 1**; **0** runs on `pin_nmi` |
| **P2** | INT, `hold = 300` | exactly **one** run on `pin_int` of length **300 ± 1** |
| **P3** | NMI, `hold = 2` | exactly **one** run on `pin_nmi` of length **2 ± 1**; **0** runs on `pin_int` |
| **P4** | **NMI, `hold = 300`** | exactly **one** run on `pin_nmi` of length **300 ± 1** |
| **P5** | NMI, `hold = 20` (`TERM_HOLD`) | exactly **one** run on `pin_nmi` of length **20 ± 1** |
| **V1** | terminator, `TVEC_A = (0x0000, 0xBF00)`, `vecsub` set, IVT[2] deliberately WRONG | MEMR T1 at linear `0x00008` returns **0xBF00** and at `0x0000A` returns **0x0000**; `vec_armed` high across both; the next `CODE` T1 is at **0xBF00**; the 15-word dump and the done marker appear |
| **V2** | the same, `TVEC_B = (0x0BF0, 0x0008)` | `0x00008` returns **0x0008** and `0x0000A` returns **0x0BF0**; the next `CODE` T1 is at **0xBF08** — a DIFFERENT physical address, so what is proved is that the whole 32-bit word is served |
| **N1** | **NEGATIVE CONTROL** — V1's image and directive with `vecsub = 0` | `vec_armed` **never** rises; the vector reads return the image's own WRONG vector; the CPU does **not** reach `0xBF00` and does **not** dump |

**P4 IS THE POINT OF P1-P5 AND IT IS REGISTERED AS SUCH.**  §20.3 measured that
`hold = 300` is **structurally impossible on an NMI seed** in this corpus —
`build` raises the hold to 300 iff the program contains a HALT, `gen_soup` emits
a HALT only when the stimulus pin is INT or POLL, and there are 0 POLL seeds —
so *"the rig applies a 300-clock hold on the NMI pin"* is **unproven by 3,840
seeds**.  That is the INV-1 axis exactly: a directive the rig may be truncating
in a cell the corpus never visits.  **One directed probe closes it, and if the
counted run comes back anything other than 300 ± 1 that is a RIG FINDING and a
hard stop**, not a result about the part.

**≥ 2 hold values on ≥ 2 pins** is met by construction: holds {2, 20, 300} × pins
{INT, NMI}, with the NMI × 300 cell the corpus cannot reach.

### 24.3 C-6's VERDICT, AS IT WILL BE READ

`cmd_bars` scores C-6 **MET** only if clause (b)'s `hold_rows_off` is **0**, at
least two distinct holds appear in the corpus, **and** `fz2_control.json` carries
`verdict == "MET"`.  Clause (b) is **2 / 4,638** (§20.4) and this sitting does
not re-capture the corpus, so:

> **IF EVERY CONTROL LEG PASSES, C-6 MOVES FROM `NOT SCOREABLE` TO `MISSED`, AND
> THAT IS A RESULT, NOT A REGRESSION.**  §20.5 said it in advance: *"Had the
> control leg existed and passed, clause (b)'s 2 failures would make C-6 read
> MISSED, not MET."*  A bar that can finally be read and is not met is worth
> more than one that could not be read at all.

### 24.4 THE TWO DEAD INT DIRECTIVES

`fz2e/528016` and `fz2e/530063` (§20.4) are re-run **with rows kept**, as
directed probes outside the corpus's `results.jsonl` — nothing is appended to a
banked population.  Registered in advance: **what is looked for is WHY**, from
the rows and the directive.  The candidate explanations are (i) the anchor's
`CODE` T1 never occurs, so no scheduler triggers — testable, because `term.fired`
is **0**, i.e. the TERMINATOR did not fire either; (ii) the delay lands beyond
the capture window; (iii) a scheduler defect.  **If it looks like RTL it is
characterised and reported, and no RTL is patched in this sitting.**

---

## §25 C-6's BOARD LEGS — **RUN, ALL NINE PASS**, AND C-6 IS FINALLY READABLE: **MISSED**

**Executed 2026-08-09 on the board, socket only (`use_core=False`, explicit),
FLASH #12, no re-flash.**  This is the execution of §24, which was committed
before any board contact.  **No bar's text or value moved and none is edited
here.**

### 25.1 THE LEGS, AS REGISTERED — 9 legs, 44 checks, **44 PASS / 0 FAIL**

`python3 sw/fz2_w1.py control` → `sw/testdata/fz2/fz2_control.json`,
`FZ2 CONTROL (C-6 board legs): MET`.

| leg | registered in §24.2 | measured |
|---|---|---|
| **R1** | RBCHECK round-trips every register | **8 registers**: `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, **`TVEC`**, **`VECCTL`** |
| **R2** | a live directive's own readback | `readback_ok` **true on all 9 board probes**; the client repacks with `v30ctl`'s own packers and would raise `RigMismatch` |
| **P1** | INT × hold 2 | `pin_int` **[[547, 2]]** — one run, length **2**; `pin_nmi` **0 runs** |
| **P2** | INT × hold 300 | `pin_int` **[[547, 300]]** — one run, length **300**; `pin_nmi` **0 runs** |
| **P3** | NMI × hold 2 | `pin_nmi` **[[547, 2]]**; `pin_int` **0 runs** |
| **P4** | **NMI × hold 300 — the cell the corpus cannot produce** | `pin_nmi` **[[547, 300]]** — one run, length **300, EXACT**; `pin_int` **0 runs** |
| **P5** | NMI × hold 20 (`TERM_HOLD`) | `pin_nmi` **[[547, 20]]** |
| **V1** | interception at `TVEC_A` | `0x00008` → **0xBF00**, `0x0000A` → **0x0000**, `vec_armed` **1** on both, next `CODE` T1 at **0x0BF00**, `STATUS[6]` **true**, dump + **0xF00D** |
| **V2** | interception at `TVEC_B` | `0x00008` → **0x0008**, `0x0000A` → **0x0BF0**, `vec_armed` **1** on both, next `CODE` T1 at **0x0BF08** — a DIFFERENT physical address |
| **N1** | negative control, `vecsub_en = 0` | `vec_armed` **NEVER rises — 0 rows of 4,063**; `STATUS[6]` **false**; `0x00008` → **0xB000**, the image's own wrong vector; the CPU **reaches 0x0B000**; **no dump, no done marker** |

**HOLDS PROVED: {2, 20, 300} on {`pin_int`, `pin_nmi`} — three holds on two
pins, against a registered "≥ 2 hold values".  TVEC VALUES PROVED: two, differing
in BOTH halves and landing on different physical addresses.**

> **§20.3's EMPTY CELL IS CLOSED.  P4 measures a 300-clock hold on the NMI pin
> at exactly 300 rows.**  The corpus cannot produce that cell by construction —
> `hold = 300` iff the program HALTs, `gen_soup` HALTs only on INT/POLL, and
> there are 0 POLL seeds — so the claim was unproven by all 3,840 seeds and it
> is the INV-1 axis exactly: a directive that could have been silently
> truncated in a cell nothing visits.  It is not truncated.

Two things reported and NOT scored, because §24.2 did not register them:
**V2 does not dump** (`arch_dump` None, done marker `0xF00D` present) — entering
8 bytes into the terminator skips register stores, which is what makes `TVEC_B`
a proof about the 32-bit word rather than about a default; and **the harness's
INT vector, MEASURED off the second INTA cycle's data phase, is `0xFF`**, which
is what the probe image composed a handler for.  `ServeRunner.cfg` sends `-` for
that CFG field, so it was a belief about a sticky register until it was read.

### 25.2 C-6's VERDICT — **MISSED**, EXACTLY AS §24.3 REGISTERED

`python3 sw/fz2_w1.py bars` → **`FZ2 BARS: 8/11 MET   NOT MET: C-1, C-3, C-6`**.

| clause | verdict |
|---|---|
| (a) registers round-trip on the readback path | **PASS** (R1, R2) |
| (b) pin-level proof by counted rows at ≥ 2 hold values | **4,636 / 4,638** — 2 fail |
| (c) interception at ≥ 2 distinct TVEC values + negative control | **PASS** (V1, V2, N1) |

> **C-6 MOVES `NOT SCOREABLE` → `MISSED`.**  §20.5 registered this outcome in
> advance and §24.3 repeated it before the board was touched.  **It is not a
> regression and must not be read as one**: a bar that can finally be read and
> is not met is worth more than one that could not be read at all.

**LEAF FOR LEAF against the §22 artifact: 206 leaves → 251, THREE differing** —
`bars/C-6/verdict` (`NOT SCOREABLE` → `MISSED`), `bars/C-8/measured/div_guards`
(**53 → 63**, this sitting's own probes), and `ts`.  One leaf disappears
(`bars/C-6/measured/control_leg`, which was `null`) and 46 appear, all inside
that object.  **Nothing else moved by one character** — C-1's `measured` is
byte-identical, C-3 is still 2 runtime PS3 captures, C-11 is still MET, and both
populations' three decompositions are unchanged (census **94.17** / **87.71** /
**92**; enriched **94.48** / **88.61** / **273**).

### 25.3 THE TWO DEAD INT DIRECTIVES — **THEY DO NOT REPRODUCE**

`python3 sw/fz2_w1.py deadint`, rows kept, nothing appended to any banked
population.  Both images regenerate byte-identically to their banked
`image_sha256`.

| | `fz2e/528016` | `fz2e/530063` |
|---|---|---|
| anchor `CODE` T1 | row **240** — present, and at the SAME row as the banked capture | row **306**, same |
| `pin_int`, banked | **[]** | **[]** |
| **`pin_int`, re-run** | **[[1745, 2]]** | **[[985, 2]]** |
| predicted start = anchor + delay + 2 − base | **1745** | **985** |
| `pin_nmi` (terminator), banked and re-run | **[[3243, 20]]** both | **[[3070, 20]]** both |
| `term.fired`, banked → re-run | **0 → 5** | **0 → 5** |

**Every pin run lands on the clock the directive names.**  §24.4's candidate (i)
— *the anchor is never fetched* — is **REFUTED**: the anchor `CODE` T1 is
present, at the identical row, in the banked capture too, which is also why the
terminator's own NMI sits at the identical row in both.  Candidate (ii), *the
delay lands beyond the capture*, is refuted by the same arithmetic.

### 25.4 THE FINDING BEHIND THEM — **THE STATUS READBACK, NOT THE SCHEDULER**, AND §20.4's INDEPENDENCE CLAIM IS WITHDRAWN

Chasing the two seeds produced a bank-wide census with **one predicate over two
independent instruments and no tier, wait or verdict term in it**
(`sw/fz2_w1.py statusanom`, a MEASUREMENT TOOL, never a gate).  The terminator
is armed on every seed at `TERM_HOLD = 20`, so its signature in the **ROWS** is a
20-clock run on `pin_nmi` and its signature in the **STATUS** readback is bit
`TERM_SCHED`.  They should agree on all 3,840.

> **THEY DISAGREE ON NINE, AND ALWAYS IN THE SAME DIRECTION: the ROWS carry the
> terminator's 20-clock assertion and the STATUS bit is CLEAR.**

`fz2c/405055` · `fz2c/411076` · `fz2e/518059` · `fz2e/519056` · `fz2e/521059` ·
`fz2e/523040` · **`fz2e/528016`** · **`fz2e/530063`** · `fz2e/531045` —
8 raw / 1 soup, 7 of them `sub: open_bus` (a class with only 168 members in
3,840), and **six of the nine reached the terminator (`arch_ok` true)**.

**RE-RUN ON THE BOARD, ALL NINE, ROWS KEPT: 9 OF 9 FAIL TO REPRODUCE.**  In
every one the terminator's STATUS bit is now SET (`fired` 0 → 4, or 0 → 5, or
1 → 5), **every pin run on every armed directive lands within one clock of
`anchor + delay + 2`**, and every image regenerates byte-identically.  **0 of 9
reproduce the anomaly.**

Two consequences, and the second is the one that matters:

1. **§20.4's sentence *"the rows and the STATUS readback say so independently"*
   is WITHDRAWN as evidence.**  On those same two seeds the STATUS *also* denies
   a terminator firing that the rows prove, so the STATUS word is the unreliable
   instrument of the pair and cannot corroborate the rows.  What survives of the
   original observation is the ROW half alone — `pin_int` empty — and that half
   does not reproduce either.
2. **NOTHING IS RESCORED.**  C-6(b) is scored at **2 / 4,638** exactly as A-8's
   ruling and §20.4 computed it.  Re-reading a registered clause on a capture
   chosen *after* seeing which seeds failed it is `ucore_provenance.md` §64.1's
   error, whichever direction the re-read moves the number.  **Whether a
   non-reproducing directive is a failure of C-6(b) is a decision about a
   registered bar and belongs to the coordinator.**

**NO MECHANISM IS CLAIMED AND NONE IS PATCHED.**  What is established is a rate
(**9 of 3,840, 0.23 %**), a direction (STATUS clear, rows populated), an
association (7 of 9 `open_bus`, base rate 168/3,840) and a reproduction result
(**0 of 9**).  Candidates NOT chosen between: a race on the STATUS sample, which
`v30ctl.do_run` takes after the capture-full wait and before `stop()`; and the
`BASE`/`DELTA` re-baseline that a whole-image raw seed always forces.  A
falsifier that would settle it: arm one scheduler, run the same image N times,
and count STATUS-vs-rows disagreements against N — this sitting ran 9 and got 0.

---

## §26 THE A-9 VALIDATION CAPTURE — **HALTED AT SEED 332 OF 960 ON A REGISTERED CAPTURE-INTEGRITY STOP.  THE VALIDATION IS NOT MEASURED.**

**2026-08-09, board, socket only, FLASH #12, no re-flash.**  Reported as
registered.  **No bar's text or value moved, nothing is adjusted, and no rate is
computed.**

### 26.1 WHAT HAPPENED

`python3 sw/fz2_val.py preflight --board` → **OK**: capture-path preconditions
all present, single writer, frozen population committed and matching the code,
resident rig RTL gap **EMPTY**, era `sof 8db6dadf5c4c… receipt 27fb750f925c…
(88 files)`, 48-seed regeneration sample **0 hits**, `rig_readback_check`
**8 registers**, `check_ab_hw all 800` **MATCH ×3**, `div_guard` **PINNED** both
ends.

`python3 sw/fz2_val.py capture` then ran the strata in the registered order and
**STOPPED**:

```
val/soup/noevt/fix0      80/80   val/soup/stim/fix0     80/80
val/soup/noevt/wrand3    80/80   val/soup/stim/wrand3   12/80  <- HALT
val/soup/noevt/wvec-uni  80/80
```

**332 of 960 seeds.  `escalation:provenance_alarm @k=604011`.**  The driver
halted and did not nurse it, which is `fz2_val.cmd_capture`'s registered
behaviour and §2.4's: *"the HARD capture-integrity stops stay armed: any
provenance alarm and the ≥ 5-consecutive-quarantine circuit breaker still
abort."*  **The stop is CORRECT and it is not overridden.**

### 26.2 WHAT THE ALARM IS — **`done_data_both_179e`**, AND THE MECHANISM IS VISIBLE ROW FOR ROW

`fz2v/604011` — soup, `wrand3`, stimulus **NMI** at `delay` 713 `hold` 2.  It
`arch_ok` **true**, `arch_match` **true**, `bad_rows` **0**, `mech` `REACHED`,
`readback_ok` **true**, and the two legs are **identical**.  The alarm is
`provenance_alarms`' Tier-A clause: both legs' FIRST `OUT 0xFC` carried
**0x179E** instead of `DONE_SENTINEL`, and a *shared* non-sentinel done value is
its definition of a corrupt store.

The banked rows say what actually happened, and it is two instructions wide:

```
 940  CODE  0bf40  0db8   <- B8 0D ..    MOV AW, 0xF00D   (the terminator's own tail)
 956  CODE  0bf42  e7f0   <- .. F0 / E7  imm high byte, then OUT
 964  CODE  0bf44  f4fc   <- FC F4       the port operand, then HLT
 975  MEMR  00008  df10   <- the STIMULUS NMI's vector read -- the SEED's OWN IVT[2],
 983  MEMR  0000a  2def      not intercepted (vec_armed low: vecsub is the terminator's)
 993  MEMW  0ffec  f006   <- push FLAGS
1000  MEMW  0ffea  0000   <- push CS
1007  MEMW  0ffe8  bf43   <- push IP = 0xBF43, the address of `OUT 0xFC, AW`
1013..1120  CODE 3be00..  <- the seed's own D8 interrupt MODIFICATION HANDLER runs
1128..1139  MEMR 0ffe8..  <- IRET pops
1145  CODE  0bf43  e7f0   <- resumes AT `OUT 0xFC, AW`
1164  IOW   000fc  179e   <- and AW is the HANDLER's, not 0xF00D
```

> **THE STIMULUS INTERRUPT WAS TAKEN BETWEEN `MOV AW, 0xF00D` AND
> `OUT 0xFC, AW`, AND THE SEED'S OWN MODIFICATION HANDLER WROTE AW.**  The
> terminator then emitted its done marker carrying the handler's AW.  The image
> re-ran, the terminating NMI fired at row 3004, and the second dump is complete
> and correct with **`OUT 0xFC, 0xF00D`** at row 3439 — which is the dump
> `arch_dump` returns and why `arch_ok` is true.

**Nothing about the rig is wrong.**  Both legs agree row for row, the rig held
the directive, and the seed terminated.  What is wrong is the alarm's premise for
Tier A — *the harness store must emit `0xF00D`* — which D8's modification
handlers exist to violate: the terminator's store is not immune to an interrupt
landing inside it.

### 26.3 THIS IS D-2's SIBLING, ONE FUNCTION OVER — **NAMED, NOT DISPOSED**

§17.5 (A-6, finding **D-2**) ruled that **a done marker is one that carries the
sentinel**, and gave `dump_words` / `arch_dump` / `dump_restarted` a
`sentinel_only` predicate.  **`provenance_alarms` was not given it**, and its
Tier-A clause still identifies a done marker by its PORT.  §17.5 says in its own
words that *"`provenance_alarms` calls a non-sentinel done marker **forged** in
its own words, in the same file"* — and then repaired only the other half.

**NO DISPOSITION IS MADE HERE, AND THAT IS DELIBERATE.**  Demoting or repairing
a registered capture-integrity STOP, after seeing the seed that tripped it, is a
decision about a registered bar.  The governing precedent is **A-1** (§11), which
is this situation exactly — the census halted on its **second** seed for a
provenance alarm whose demotion had already been ruled elsewhere, and A-1
completed that ruling as a numbered amendment.  **Whether D-2's sentinel rule
extends to `provenance_alarms` belongs to the coordinator**, on A-1's shape: a
numbered amendment, a hard falsifier, and a both-ways rescore.

### 26.4 WHAT IS **NOT** REPORTED, AND WHY

> **NO RATE IS COMPUTED ON THE 332.**

The population is a **prefix of the registered order**, truncated at a point that
is not independent of the outcome: the halt is caused by a seed whose dump was
disturbed.  Four of six soup strata are complete, one is 12/80, and **the entire
RAW TIER — all 480 seeds, i.e. the whole of clause E-1b — is uncaptured.**  A
soup number computed on that prefix would be a new statistic on a population
selected by where a halt happened, and quoting it would be the thing §16.2 was
written to prevent.  **`fz2_val score` was not run** and no `fz2v_score.json`
exists.

> **§16.2's VALIDATION IS NOT MEASURED.  A-5's `UNVALIDATED` MARKER STAYS ON
> C-1's TWO RATE CLAUSES, AND IT STAYS FOR THE REASON IT WAS PUT THERE — NOT
> BECAUSE THE VALIDATION FAILED.**  `fz2_w1._c1_verdict` is untouched, C-1 still
> reads `MISSED (rate clauses UNVALIDATED -- A-5)`, and **90.0 and 75.0 remain
> unquotable as ratchets.**

### 26.5 WHAT IS RETAINED

* `sw/testdata/fz2/fz2v_population.json` + `.sha256` — the frozen 960, committed
  before the capture, unchanged by it.
* `sw/testdata/campaigns/fz2v/results.jsonl` — **332 lines**, every one carrying
  its era stamp, kept in full.  **Nothing is deleted and nothing is banked**:
  `fz2v` is not promoted, so C-11's three populations are untouched.
* `sw/testdata/fz2/fz2v_preflight.json`, `fz2v_capture.json` — both carrying
  `tree_dirty`.
* `sw/testdata/campaigns/fz2v/captures/soup_604011_0a5656a31a44.json.gz` — the
  halting seed's full per-clock rows, both legs.

**The capture is RESUMABLE without re-running a seed**: `fz2_val capture`
resumes by `_done_ks()`, every k actually present, never by `max(k) + 1`.  It
will halt again at 604011 until the alarm is disposed of.

### 26.6 THE SESSION'S BOARD DISCIPLINE, REPORTED

Single-writer checked before and after (`NO_PROC` both times); socket only,
`use_core=False` explicit on every probe; **`div_guard` on every probe — 63 in
the scored artifact, `unpinned` 0**; full per-clock rows retained with sha256
beside them for all 9 control probes and all 11 replayed seeds
(`sw/testdata/campaigns/fz2ctl/captures/SHA256SUMS`); `board_idle()` at the
close; and the closing `use_core=0` chip proof **`chip-vs-golden: MATCH over 800
rows`**.  **0 transport errors, 0 `RigMismatch`, 0 quarantines outside the one
that halted the capture.**

### 26.7 A CONCURRENT WRITER IN THE REPOSITORY, REPORTED BECAUSE IT BEARS ON PROVENANCE

**A SECOND SESSION WAS EDITING THIS TREE THROUGHOUT.**  `eb11ffe149`
(*"INT.F3AA repair: PRE-REGISTRATION"*) landed immediately before §23/§24's
commit, and while this sitting ran, that session held uncommitted edits to
`hdl/rtl/ucore/v30u_biu.sv`, `hdl/rtl/ucore/v30u_eu.sv` and later
`sim/exec_impl.h`, and was running `sw/quartus_gate.py` and `sw/ucsim_check.py`.

**This does not touch any measurement above, and that is checked rather than
asserted:**

* **The board was single-writer throughout** — asked of the board before and
  after, `NO_PROC` both times.  No other session contacted it.
* **Nothing this sitting measured passes through a file that session edited.**
  The socket leg is the chip; the fabric leg is FLASH #12's bitstream, which no
  tree edit reaches; and the offline rescore regenerates images through
  `fuzz_campaign` / `gen_soup` / `gen_raw` / `testimage`, none of which moved.
* **`tree_dirty` is identical in all four of this sitting's board artifacts** —
  the same three paths with the same sha256s — so the tree was stable for the
  whole board session and the `sim/exec_impl.h` edit arrived after it closed.
* **Every commit of this sitting stages EXPLICIT PATHS**, never `git add -A`, so
  no in-progress RTL or `sim/` work was swept into it.

Recorded because a reader six months from now, finding two unrelated campaigns
interleaved in the log at the same minute, is owed the fact rather than left to
infer it.

---

## §27 AMENDMENT A-10 — D-2's SENTINEL PREDICATE EXTENDS TO `provenance_alarms`' TIER-A DONE-DATA CLAUSE, **AND THE TIMING IS STATED FIRST**

**Committed BEFORE any board contact of the resuming session.**  This is the
coordinator's ruling on §26.3, which named the question and deliberately made no
disposition.

### 27.0 THE TIMING, FIRST, BECAUSE IT IS THE THING A READER WILL CHECK

> **THIS IS NOT A HALF-LANDED RULING BEING COMPLETED.  IT IS AN EXTENSION OF
> D-2's PREDICATE TO A PLACE A-6 EXPLICITLY LEFT ALONE, DECIDED AFTER SEEING THE
> SEED THAT TRIPPED IT.**

§17.6 does not say A-6 ran out of time on `provenance_alarms`.  It says, in its
own bullet, ***"It does not touch `classify`, so no verdict, signature or
row-diff moves."***  That was a scope decision made on purpose, and
`provenance_alarms` lives in the same file and is `classify`'s step 0.  §17.5 did
observe that *"`provenance_alarms` calls a non-sentinel done marker **forged** in
its own words, in the same file"* — but it observed it while repairing the OTHER
half, and shipped.  **A-6 could have extended the predicate here and chose not
to.**

**The order of events is therefore: the predicate was ruled (A-6, §17.5); this
function was left out on purpose (§17.6); the validation capture ran; it halted
on `fz2v/604011`; and only then was this amendment written.**  A rule changed
after seeing the datum it would have excused is, on its face, the shape of
fitting, and A-4 §15.0's four conditions exist to make that hard.  Nothing below
hides behind the fact that the amendment is numbered.

### 27.1 WHAT MAKES IT DEFENSIBLE ANYWAY — four things, none of them "it is inconvenient"

1. **The mechanism is MEASURED, row for row, on both legs, and there is no rig
   defect.**  §26.2 prints it: the stimulus NMI landed on the instruction
   boundary between the terminator's `MOV AW, 0xF00D` (row 940) and
   `OUT 0xFC, AW` (row 964); the vector read at 975 is the SEED's own IVT[2];
   the seed's D8 modification handler ran at 1013–1120; IRET popped at 1128–1139
   and resumed AT `OUT 0xFC, AW` (1145); and the store emitted `0x179E` at 1164.
   The image re-ran and the second pass dumped cleanly with the true sentinel.
   **`arch_ok` true, `arch_match` true, `bad_rows` 0, both legs IDENTICAL,
   `mech` `REACHED`, `readback_ok` true.**  Nothing is inferred.
2. **The alarm's premise predates the thing that violates it.**  The clause says
   *"the harness store must emit `0xF00D`"*.  It was written for a corrupt store
   STUB — a deterministic, shared defect (task #29 P7, `mc1` k=9192).  **D8
   modification handlers exist to modify registers**; that is their entire
   purpose, and `AW` is a register.  The terminator's store is not immune to an
   interrupt landing inside it, and the alarm was never told that such handlers
   would exist.
3. **The interference window is inherent and cannot be closed.**  It is ONE
   instruction boundary wide.  **NMI is non-maskable, so no `CLI` closes it**,
   and the stimulus event is a rig directive delivered at a `delay` the corpus
   chooses without knowledge of where the program will be.  Widening the
   terminator (loading `AW` twice, or storing an immediate) would change the
   terminator's bytes and therefore **invalidate every `image_sha256` in the
   frozen population and in both committed corpora** — 4,800 of them — for a
   defect that is not the part's.
4. **The A/B property, which is what this campaign actually measures, HOLDS.**
   Both legs took the same NMI at the same row, ran the same handler, emitted the
   same `0x179E`, and produced identical dumps.  A capture-integrity alarm exists
   to say *the evidence cannot be trusted*.  Here the evidence is trustworthy and
   says the two engines agree.

### 27.2 THE RULING, AND THE ONE PLACE IT IS NOT TAKEN LITERALLY

**THE PREDICATE, ONCE, UNIFORMLY: a done marker is an `OUT 0xFC` carrying
`0xF00D`.  A non-sentinel `OUT 0xFC` is not a done marker and raises no
done-related alarm.**  The seed then scores under the existing sentinel-aware
readers — `arch_dump(..., sentinel_only=True)`, which `fuzz_campaign` already
calls over the whole capture and which is why `arch_ok` was true all along.

⚠ **AND READ LITERALLY, THAT DELETES THE ALARM.**  `has_done(...,
sentinel_only=True)` can only ever return `DONE_SENTINEL`, so `ddr !=
DONE_SENTINEL` becomes unreachable and the clause can never fire again.  **An
alarm that can no longer catch anything is a deletion wearing an extension's
clothes**, and this document is not going to record one as the other.  So the
predicate is applied where it decides **EXISTENCE**, and the **accusing**
evidence is left exactly where it was:

> **The clause fires when the harness's own `0xF00D` marker appears NOWHERE in
> either capture AND both legs wrote the SAME non-sentinel value to the done
> port.**

That is the corrupt-store signature and nothing else: a corrupt store stub is
deterministic and SHARED, so it corrupts both legs and **neither of them ever
reaches the sentinel**.  The shared-vs-one-sided discriminator (task #29 P7) is
untouched and is still what separates a corrupt store from a functional
divergence.

**THE TWO READS USE DIFFERENT WINDOWS, ON PURPOSE, AND THAT IS D-1 (§17.4).**
The capture is not one run of the program.  604011's sentinel marker sits at row
**3406 of 4063**, **2,267 rows past** the comparison window of 1,139 — a window
which the forged marker itself set.  So the SUPPRESSING evidence is asked of the
whole CAPTURE (`len(recs)`), exactly as the arch column is; the ACCUSING read
keeps the comparison `window` it has always had.  **The new condition is the old
condition AND one more conjunct, so A-10 can only ever REMOVE an alarm and can
never create one anywhere.**  That is a proof, not a sample.

### 27.3 THE FALSIFIER — RUN, AND REPORTED WITH ITS DENOMINATORS

**A stop-condition change that cannot be SHOWN to still stop is not a safe
change.**  Two instruments, one board-free and one on the real halting rows.

**(a) `python3 sw/test_fuzz_classify.py` — `PASS: 0 failure(s)`, 34 checks.**
The two pre-existing forged-done checks are **UNCHANGED IN TEXT AND STILL
FIRE**:

```
  ok   shared corrupt done -> QUARANTINE  (got QUARANTINE/provenance_alarm:done_data_both_00c5)
  ok   one-sided junk done -> NOT provenance QUARANTINE  (alarms=[])
  ok   A-1(c): the shared corrupt-store alarm still STOPs  ([('STOP', 'provenance_alarm')])
```

They needed **no re-derivation**: the TB fixture's only `OUT 0xFC` is the
terminator's, so mutating its data leaves no sentinel anywhere and the
suppressing conjunct is false.  Ten checks were ADDED, because the shared check
passing is not by itself proof that the discriminator survived:

```
  ok   A-10(a): junk marker + a LATER sentinel -> NO done alarm  (alarms=[])
  ok   A-10(b): and the seed SCORES (not QUARANTINE)  (got SUCCESS/clean)
  ok   A-10(b): with the sentinel-anchored arch dump readable
  ok   A-10(a): and does NOT stop the campaign
  ok   A-10(d): the one-sided fixture has NO sentinel on either leg
  ok   A-10(d): one-sided junk, no sentinel -> NO done alarm (the discriminator, not the predicate)
  ok   A-10(c): the shared fixture has NO sentinel on either leg
  ok   A-10(c): shared corrupt done, no sentinel -> STILL QUARANTINE  (got QUARANTINE/provenance_alarm:done_data_both_00c5)
  ok   A-10(c): and STILL STOPs the campaign
  ok   A-10(e): no marker of any kind -> NO done alarm  (alarms=[])
  ok   A-10(e): and Tier A reads it as runaway_both  (sub=runaway_both)
```

**`A-10(d)` is the one that matters.**  It asserts first that NEITHER leg carries
a sentinel — so the new conjunct does **not** suppress — and then that a
one-sided junk done still raises no alarm.  **The thing refusing it is the
original shared-vs-one-sided discriminator, which is therefore demonstrably
still load-bearing and not dead code behind a always-true guard.**
`python3 sw/test_fuzz_accept.py` is **`PASS: 0 failure(s)`** as well.

**(b) `python3 sw/fz2_a10_replay.py` — `FZ2_A10_REPLAY: PASS`**, on the banked
rows of the halting seed itself.  NEW tool, modelled on `fz2_a1_replay.py`:
`sw/testdata/campaigns/fz2v/captures/soup_604011_0a5656a31a44.json.gz`, sha256
**`41a407c71388b8ba8e9a08661a0fb67c4ba62bb7d97bd956c12f9df83154c13f`**, 4,063
rows per leg.

```
    OUT 0xFC (real): [(1131, '0x179e'), (3406, '0xf00d')]
    OUT 0xFC (sim ): [(1131, '0x179e'), (3406, '0xf00d')]

--- LEG 1: the halting seed, as captured
    BEFORE (b5f2b14f05)    -> QUARANTINE/provenance_alarm:done_data_both_179e
                              alarms=['done_data_both_179e']  win=1139  bad_rows=0  STOP=True
                              CONTROL reproduces the banked line: YES
    AFTER  (tree)          -> SUCCESS/clean
                              alarms=[]  win=1139  bad_rows=0  STOP=False
    arch dumps compared: real=ok sim=ok equal=True
    arch_ok(banked)=True arch_match(banked)=True  replayed arch == banked arch_words: True
```

**THE CONTROL IS THE WHOLE POINT** and it reproduces the banked line exactly —
verdict, sub, alarm list and the `('STOP', 'provenance_alarm')` escalation — so
the AFTER column is evidence.  **The seed now scores: `SUCCESS/clean`, both legs'
arch dumps read through the sentinel-anchored reader, EQUAL to each other and
EQUAL to the banked `arch_words`.**

```
--- LEG 2: THE FALSIFIER -- the same rows with NO sentinel marker anywhere
    sentinel markers moved off the done port: 2
    OUT 0xFC (real): [(1131, '0x179e')]  sentinel_present=False
    OUT 0xFC (sim ): [(1131, '0x179e')]  sentinel_present=False
    AFTER  (tree)          -> QUARANTINE/provenance_alarm:done_data_both_179e
                              alarms=['done_data_both_179e']  win=1139  bad_rows=0  STOP=True
    the alarm STILL CATCHES a corrupt shared store: YES

--- LEG 3: one-sided, and no sentinel on either leg
    sentinel_present real=False sim=False   done-port writes real=1 sim=0
    AFTER  (tree)          -> FUNCTIONAL/done_mismatch
                              alarms=[]  win=1139  bad_rows=1  STOP=False
    the discriminator still refuses a one-sided junk done: YES
```

**Leg 2 is a corrupt shared store built out of REAL SILICON ROWS** — the same
capture, with the second pass's `OUT 0xFC, 0xF00D` moved off the port on both
legs and nothing else touched — **and the tree still QUARANTINEs it and still
STOPs the campaign.**

### 27.4 THE BOTH-WAYS RESCORE — **A-10 MOVES EXACTLY ONE LINE IN THE REPOSITORY**

Two halves, and the first is arithmetic rather than a sample: **the new condition
is the old condition AND one more conjunct, so no line anywhere can newly
alarm.**  For the other direction, every `results.jsonl` in the tree was scanned
for a line carrying `done_data_both`:

```
sw/testdata/campaigns/fz2c-A5-archive/results.jsonl          lines=960     done_data_both=0
sw/testdata/campaigns/fz2c-INV2-archive/results.jsonl        lines=960     done_data_both=0
sw/testdata/campaigns/fz2c-prereg-A1-archive/results.jsonl   lines=2       done_data_both=0
sw/testdata/campaigns/fz2c/results.jsonl                     lines=960     done_data_both=0
sw/testdata/campaigns/fz2e-A5-archive/results.jsonl          lines=2880    done_data_both=0
sw/testdata/campaigns/fz2e-INV2-archive/results.jsonl        lines=2880    done_data_both=0
sw/testdata/campaigns/fz2e/results.jsonl                     lines=2880    done_data_both=0
sw/testdata/campaigns/fz2v/results.jsonl                     lines=332     done_data_both=1
sw/testdata/campaigns/mc1/results.jsonl                      lines=10003   done_data_both=0
sw/testdata/campaigns/mc2/results.jsonl                      lines=10000   done_data_both=0
sw/testdata/campaigns/wr1/results.jsonl                      lines=3150    done_data_both=0
sw/testdata/campaigns/wr2/results.jsonl                      lines=296     done_data_both=0
TOTAL lines 35303  done_data_both lines: 1 [('fz2v', 604011)]
```

**Over 35,303 banked result lines across every campaign this repository holds,
exactly ONE ever carried this alarm, and it is the seed the amendment was
written for.  No committed corpus figure, bar, census, discard class or
`fz2_bars.json` cell moves.**

### 27.5 AN ERRATUM AGAINST §26.5 — **THE RESUME WOULD NOT HAVE RE-HALTED THERE**

§26.5 says: *"It will halt again at 604011 until the alarm is disposed of."*
**That is wrong, checked against the artifact rather than recalled.**
`fz2_val.cmd_capture` resumes by `_done_ks()`, which is **every `k` present in
`results.jsonl`** — and **604011's line IS present** (it is the 332nd, written
with `verdict` `QUARANTINE` before the driver stopped).  Measured:

```
val/soup/stim/wrand3       n=80 done=12 first_missing=604012 last_missing=604079 span=68
```

So the resume begins at **604012** and never touches 604011.  The sentence
should have read *"the seed's line is already banked and the resume steps over
it; what will halt again is the NEXT seed that hits the same mechanism."*

**THE AMENDMENT IS STILL WHAT UNBLOCKS THE RUN, AND THE ARITHMETIC IS WORTH
STATING BEFORE THE CAPTURE RATHER THAN AFTER.**  The clause is Tier-A only, so
the exposed remainder is **SOUP** seeds carrying a **stimulus** event: 68 left in
`val/soup/stim/wrand3` plus 80 in `val/soup/stim/wvec-uni` = **148**.  Of the
soup stimulus seeds captured so far — 80 in `stim/fix0` plus 12 in
`stim/wrand3` = **92** — **one** hit the mechanism.  The remaining 480 raw seeds
are Tier B, where this clause does not apply by construction.

### 27.6 A THIRD SIBLING, **NAMED AND NOT DISPOSED** — `_done_idx`

`fuzz_classify._done_idx` is D-2's other sibling and it identifies a done marker
**by its PORT** as well.  It sets the Tier-A comparison window
(`min(..., dend + 8)`), which is why **604011 was compared over 1,139 of its
4,063 rows** — the window was set by the forged marker.

**IT IS NOT TOUCHED, AND THAT IS DELIBERATE.**  Giving `_done_idx` the sentinel
predicate would move the comparison window on **every Tier-A seed anywhere in
the tree that contains a non-sentinel write to port 0xFC**, and with it `win`,
`bad_rows`, `first_bad`, every signature and potentially every verdict in both
committed corpora.  That is a rescore of the whole campaign, not an amendment to
one clause, and it is **not** what §26.3 put to the coordinator.  It is named
here, with its measurement, so that the next reader finds it recorded rather than
discovers it — the same treatment §26.3 gave this one.

### 27.7 WHAT A-10 CHANGES IN THE TREE

* `sw/fuzz_classify.py` — `has_done` gains `sentinel_only`, **defaulting False so
  every historical caller means what it meant** (it is `dump_words`' parameter
  under `dump_words`' rule); `provenance_alarms`' Tier-A clause gains the one
  suppressing conjunct and its reasoning.  **No other predicate, no tier
  parameter, no per-seed case, no list of excused seeds.**
* `sw/test_fuzz_classify.py` — ten checks added, **none removed or reworded**.
* `sw/fz2_a10_replay.py` — NEW, the replay + falsifier above.
* This document, appended.
* **No other file.**  No bar, no constant, no discard class, no `fz2_w1.py`, no
  `fz2_val.py`, no banked result line rewritten, no capture deleted, no board,
  no flash, no Quartus, no RTL and nothing in `sim/`.

### 27.8 WHAT IS REGISTERED FOR THE RESUME — before the board is touched

* The resume is `fz2_val capture` **by `_done_ks()`**, starting at **604012**.
  **628 seeds** remain; **no seed is re-run and the 332 banked lines stay
  exactly as they are**, including 604011's `QUARANTINE`, which was the honest
  verdict under the rule in force when it was taken.  §27.3(b) is where that
  seed's post-amendment reading lives; **the results file is not rewritten**.
  Its `arch_ok` is `true`, and `_rate` — C-1's arithmetic, and the only
  arithmetic §16.2 scores — counts `arch_ok`, so the line's verdict field does
  not enter either clause either way.
* **The HARD stops stay armed.**  §2.4 is unchanged: any provenance alarm and
  the ≥ 5-consecutive-quarantine circuit breaker still abort.  **If the capture
  halts on a NEW contradiction it will be reported as a halt, not nursed.**
* **NOTHING IS SCORED UNTIL ALL 960 ARE CAPTURED.**  §16.2's *"captured before
  the rate is looked at"* is a property of the population, not of a stratum:
  **no partial rate, no per-stratum rate, and `fz2_val score` is not run on a
  prefix.**
* **The bars are §16.2/A-5's, unmoved: soup ≥ 90.0 %, raw ≥ 75.0 %**, and
  **§23.5's two outcomes are the only two available.**  No adjustment is
  permitted in either direction.
* Board discipline as registered: single-writer first, socket only with
  `use_core=False` explicit, `div_guard()` on every probe with UNPINNED a
  FINDING, `board_idle()` and a closing `use_core=0` chip proof.  **FLASH #12
  (`sof 8db6dadf5c4c…`, receipt `27fb750f925c…`, 88 files) is the era and
  THERE IS NO RE-FLASH.**
* The frozen population is unchanged and is checked at preflight:
  `fz2v_population.json` sha256
  **`abfb39cb6576e3a618675fa7eadfe93f910d482a0197b5c698e678776d0c8d30`**,
  `val_seed_list_sha256`
  **`5d83b3a9b6aa7907cbef01eae7f33223b024f1fa9cdf1d56ab879e24925d81be`**.

---

## §28 THE A-9 VALIDATION, **RESUMED AND FINISHED: 960/960 CAPTURED, AND BOTH RE-REGISTERED RATE CLAUSES ARE MET ON A DISJOINT POPULATION.  THE `UNVALIDATED` MARKER COMES OFF.**

**2026-08-09, board, socket only, FLASH #12, no re-flash.  Reported as
registered: no bar's text or value moved, nothing was adjusted, and nothing was
scored until all 960 were captured.**

### 28.1 THE RESUME, AS §27.8 REGISTERED IT

A-10 (§27) was committed at **`ed8512e67d`, BEFORE any board contact of this
session**.  `python3 sw/fz2_val.py preflight --board` → **OK**, and it had to be
re-run because `_preflight_ok()` refuses a preflight taken at a different
`gen_git` — the amendment commit invalidated §26's preflight by construction,
which is the check working:

* single writer **`no v30/serve process on the board -> SINGLE WRITER`**;
* era `sof 8db6dadf5c4c… receipt 27fb750f925c… (88 files)` **gen_git
  `ed8512e67d`**, resident rig RTL gap **EMPTY**;
* 48-seed regeneration sample **hits=0**; `rig_readback_check` **8 registers**;
* `check_ab_hw all 800` **MATCH ×3** (chip-vs-golden, core-vs-chip,
  core-vs-golden); `div_guard` **PINNED** at both ends.

`python3 sw/fz2_val.py capture` then resumed **by `_done_ks()` from k=604012**,
exactly as §27.5 measured it would, and **ran to the end without halting**:

```
val/soup/noevt/fix0     skipped (80/80)   val/raw/noevt/fix0     80/80
val/soup/noevt/wrand3   skipped (80/80)   val/raw/noevt/wrand3   80/80
val/soup/noevt/wvec-uni skipped (80/80)   val/raw/noevt/wvec-uni 80/80
val/soup/stim/fix0      skipped (80/80)   val/raw/stim/fix0      80/80
val/soup/stim/wrand3           80/80      val/raw/stim/wrand3    80/80
val/soup/stim/wvec-uni         80/80      val/raw/stim/wvec-uni  80/80

FZ2V CAPTURE: 960 seeds in 1.8 min      halted: null
```

**628 seeds captured this session, 0 seeds re-run, and the 332 banked lines are
byte-for-byte the ones §26 left** — including 604011's, which still reads
`QUARANTINE / provenance_alarm:done_data_both_179e`, **the honest verdict under
the rule in force when it was taken.  The results file was not rewritten.**
`sw/testdata/campaigns/fz2v/results.jsonl` is **960 lines**, sha256
`a1a4036eea471925b02443ecb98f43bec59f10646df41deac66672ca55b86e6b`.

**Over the resumed 628: 0 halts, 0 provenance alarms, 0 quarantines, 0
`build_stale`, one distinct era.**  Verdicts, all 960: `SUCCESS` 902,
`KNOWN_ACCEPTED` 47, `FUNCTIONAL` 10, `QUARANTINE` **1** — and that 1 is
604011.

**WHAT A-10 BOUGHT ON THE RESUMED 628 IS NOT CLAIMED, BECAUSE IT IS NOT
MEASURABLE FROM THE ARTIFACTS.**  Only 81 of the 960 seeds banked rows
(`fuzz_campaign` banks divergent / keep-rows / ballast captures), and **among
those 81, exactly one carries the shape — 604011.**  Twelve of the 960 lines
carry `arch_restart`, the column that was `true` on 604011; six are soup, the
only tier this clause reaches, and **three of those six lie in the resumed
block (604030, 605038, 605079)**.  Their rows were not retained, so whether any
of them would have tripped the pre-amendment clause **cannot be determined and
is not asserted either way**.

### 28.2 THE INSTRUMENT PROVED ITSELF FIRST — §23.4's mirror check

`fz2_val score` re-runs C-1's rate arithmetic over `fz2c` and `fz2e` and
compares all four cells against the **committed** `fz2_bars.json` before it
looks at the validation population at all:

```
  census/raw       403/480 = 83.96 %      enriched/raw     1213/1440 = 84.24 %
  census/soup      473/480 = 98.54 %      enriched/soup    1424/1440 = 98.89 %
  PASS: all four committed C-1 cells reproduced exactly
```

**A validation measured with a second, subtly different scorer would be
validating the scorer.**  Disagreements: **0**.

### 28.3 THE SCORE, AS REGISTERED — `sw/testdata/fz2/fz2v_score.json`, 2026-08-09T23:22:46Z

```
stratum                       cap reached  rows=  arch=
val/soup/noevt/fix0            80      76     80     76
val/soup/noevt/wrand3          80      80     78     78
val/soup/noevt/wvec-uni        80      79     79     79
val/soup/stim/fix0             80      77     79     76
val/soup/stim/wrand3           80      80     74     78
val/soup/stim/wvec-uni         80      79     76     76
val/raw/noevt/fix0             80      63     69     60
val/raw/noevt/wrand3           80      66     74     63
val/raw/noevt/wvec-uni         80      61     77     58
val/raw/stim/fix0              80      66     72     62
val/raw/stim/wrand3            80      66     77     64
val/raw/stim/wvec-uni          80      66     68     60

clause                   measured   registered   verdict
E-1a soup     471/480 =  98.12 %    >= 90.0 %   MET
E-1b raw      388/480 =  80.83 %    >= 75.0 %   MET

FZ2V VALIDATION: PASS
```

> **BOTH CLAUSES MET, AT THE REGISTERED VALUES, WITH NO ADJUSTMENT.**  This is
> **§23.5's PASS branch**, and it is the first branch of that pre-registration
> either way.

The margins, stated because a bar met by a hair and a bar met by eight points
are different facts: soup clears by **+8.12 points**, raw by **+5.83**.

**AND NEITHER CLEARS THE VALUE A-5 REPLACED.**  Against §5.3's original bars
(soup 99.0, raw 95.0) this population reads **MISSED on both**, exactly as the
selecting population did.  That is not softened here: **A-5 lowered two bars,
and all this section establishes is that the LOWERED bars survive a population
that did not choose them.**  It does not rehabilitate the originals and it is
not evidence that 90.0 and 75.0 are the right numbers — only that they are not
fitted to their own measurement.

Reported beside the rates, not scored on this population (§16.2 registers the
two RATE clauses and only those): discards `stalled` **67**, `long_insn` **21**,
`wrote_term` **7**, **UNDISPOSITIONED 9**; `quarantines` **1** (604011, above);
`div_guards` **10**, `div_guards_unpinned` **[]**; `halted` **null**;
`board_seconds` **107.3**.

### 28.4 WHAT COMES OFF, AND WHAT DOES **NOT**

* **`fz2_w1._c1_verdict` no longer emits `(rate clauses UNVALIDATED -- A-5)`.**
  It now reads
  `(rate clauses VALIDATED on fz2v/960 -- soup 98.12 %, raw 80.83 %; §16.2 / A-9)`,
  and `E1_A5` records the validating population inline.  **90.0 and 75.0 are
  quotable as ratchets from here**, always with the population named.
* **THE MARKER CAME OFF BY ARTIFACT, NOT BY EDIT.**  A new `fz2_w1._validation()`
  is the only thing that can remove it, and it removes it only while
  `fz2v_score.json` reports `validated`, `captured == 960`, `e1_registered ==
  {soup: 90.0, raw: 75.0}` and the **same `val_seed_list_sha256` as the frozen
  population file committed before the capture**.  Its falsifier, run:

  ```
  with the artifact REMOVED  : MISSED (rate clauses UNVALIDATED -- A-5)
  with validated=False       : MISSED (rate clauses UNVALIDATED -- A-5)
  with captured=332 (prefix) : MISSED (rate clauses UNVALIDATED -- A-5)
  with a DIFFERENT population: MISSED (rate clauses UNVALIDATED -- A-5)
  restored                   : MISSED (rate clauses VALIDATED on fz2v/960 ...)
  ```

  **A prefix cannot validate anything** — that clause is `captured == 960`, and
  it is why §26 could not have removed the marker even if its 332 had read
  well.
* **C-1's OWN VERDICT DOES NOT CHANGE.  IT IS STILL `MISSED`**, exactly as
  §23.5 registered: **E-1c (0 UNDISPOSITIONED) is 27 against 0 and remains its
  sole blocker.**  A validated rate clause does not buy a bar.
* **NO MEASURED NUMBER MOVED.**  `sw/fz2_w1.py bars` was re-run and its output
  diffed field by field against the committed artifact: **the only changes are
  `bars/C-1/registered`, `bars/C-1/verdict` and `ts`.**  Every measurement in
  all eleven bars is byte-identical, and the roll-up is unchanged at
  **8/11 MET, NOT MET: C-1, C-3, C-6**.
* `python3 sw/fz2_w1.py lint` **PASS, 0 hits, 48 stratum rows**;
  `python3 sw/fz2_val.py overlap` **PASS, 0 hits** on all seven disjointness
  checks, re-run after the capture.

### 28.5 BOARD DISCIPLINE, REPORTED

Single-writer asked **before** (preflight: `SINGLE WRITER`) and **after** (no
`v30ctl`/`serve` process remains); **socket only, `use_core=False` explicit on
every probe**; **`div_guard` on EVERY probe — 10 in the scored artifact
(2 preflight + 8 capture) plus the closing one, `unpinned` 0** in all of them;
`board_idle()` at the close (`OK, use_core=0 left selected`); and the closing
`use_core=0` chip proof **`chip-vs-golden: MATCH over 800 rows`** taken after
everything.  **0 transport errors, 0 `RigMismatch`, 0 quarantines in the 628.
NO RE-FLASH: FLASH #12 throughout, one distinct era stamp on all 960 lines,
`build_stale` 0.**

### 28.6 THE CONCURRENT WRITERS — **AND ONE OF THEM COMMITTED RTL WHILE THIS CAPTURE WAS RUNNING**

§26.7 reported two other sessions holding uncommitted edits.  This sitting must
report something sharper, with the clock, because it is exactly the fact a
reader would otherwise have to infer from an interleaved log:

```
23:19:49Z  ed8512e67d  A-10 (this session), committed BEFORE board contact
23:20:19Z              fz2_val preflight --board  -> OK, gen_git ed8512e67d
23:21:06Z  9c98117a03  ANOTHER SESSION commits hdl/rtl/ucore/v30u_biu.sv (+28)
                       and v30u_eu.sv (+8) -- DURING this capture
~23:21-23:23Z          fz2_val capture (628 seeds) and score
```

`077e10ac53` (`sim/exec_impl.h`, +61) had landed at 23:12:50Z, before the
amendment.

**IT TOUCHES NOTHING MEASURED HERE, AND THAT IS CHECKED RATHER THAN ASSERTED:**

* **The board was single-writer before and after** — asked both times; no
  `v30ctl`/`serve` process remains.  No other session contacted the board.
* **A tree RTL commit does not reach the board.**  There was **NO RE-FLASH**;
  the fabric leg is **FLASH #12**, built from `b629296e3a`, and **all 960 lines
  carry one distinct era stamp `sof 8db6dadf5c4c…`** with `build_stale` **0**.
  The socket leg is the chip.
* **Nothing on the capture path moved.**  Images are generated by
  `fuzz_campaign` / `gen_soup` / `gen_raw` / `testimage`; neither commit touches
  any of them, and the preflight's 48-seed regeneration sample was **0 hits**.
  No Verilator binary and no `sim/` model is on this capture's path at all, so
  `077e10ac53` and the `verilator_binary.jsonl` / `quartus_bitstream.jsonl`
  receipt lines in `9c98117a03` are inert here.
* **`tree_dirty` in `fz2v_capture.json` is the pre-commit state** (the three
  paths recorded ` M`), which is consistent with the clock above and is
  retained rather than tidied.
* **Every commit of this sitting stages EXPLICIT PATHS**, never `git add -A`,
  so no RTL, `sim/` or `fz2_statusanom.json` work belonging to another session
  is swept in.

**What a reader may NOT conclude from this section**: that the ucore in FLASH
#12 is the ucore in the tree.  It is not, and it was not at §26 either.  Every
fabric figure in §26 and §28 is readable against **FLASH #12 and nothing
else** — the standing rule of this repository.

---

## §29 AMENDMENT A-11 — C-3's RUNTIME CLAUSE IS RE-REGISTERED FROM *"0 captures showing PS3 on a `CODE` T1"* TO **"runtime 8080 entries are DETECTED AND DISCARDED"**, AND THE TIMING IS STATED FIRST

**BY USER DECISION, 2026-08-09.**  Offline sitting: no board, no flash, no
Quartus.  The **generation clause is NOT EDITED** — *0 forbidden `0F xx` pairs
on every composed image* stands character for character, and it is **MET at
3,840 / 3,840**.

### 29.0 THE TIMING, FIRST, BECAUSE IT IS THE THING A READER WILL CHECK

> **THE RUNTIME CLAUSE IS RE-REGISTERED AFTER IT WAS MISSED, ON THE POPULATION
> THAT MISSED IT.**

The order of events is: §5/§6 registered the runtime clause at **0**; the T12
capture read **1** (§9.x, `fz2e/509069`) and C-3 scored MISSED; the T13
re-capture read **2** (§14.1, §14.4); the current corpus reads **2** again
(§21.6, §22, and every `fz2_bars.json` since); and only then was this amendment
written.  It is the shape `ucore_provenance.md` §64.1 warns about, and nothing
below hides behind the fact that it is numbered.

The one protection that A-5 had and this amendment does **not** need: A-5
re-registered a *threshold*, so a disjoint validation population was required
before its MET could be a ratchet (§16.2, discharged at §28).  A-11
re-registers a *predicate*, and the replacement predicate's non-vacuity is
demonstrated on **`t30-brkem`, a population disjoint from this corpus by
construction** (§29.5) — the same discipline, discharged in the same sitting
rather than deferred.

### 29.1 WHY IT IS DEFENSIBLE ANYWAY — THE OLD CLAUSE IS UNMEETABLE BY CONSTRUCTION

This is a mechanism argument, not an inconvenience argument.

The generation clause scrubs forbidden `0F xx` pairs out of `optable.CODE_SPANS`
**at compose time**.  The image then RUNS.  A random `MEMW` into the code region
writes one byte, at an arbitrary address, at an arbitrary alignment, **after the
scrub has run** — and a `0F` already in the region plus a newly-written second
byte (or a newly-written `0F` beside a byte already there) is a `0F xx` pair the
scrub never saw and structurally could not have seen.  §6's own C-3 row says
this in advance: *"the generation clause alone cannot see a pair a runtime write
creates"*.

So the runtime clause is not a bar on the generator.  **It is a bar on the
part**, and it asks the part not to do a thing the corpus deliberately gives it
the means to do — raw's whole-image mode writes into the code region by design,
and §5's own E-1b arithmetic budgets **9.7 `MEMW` into that region per run** on
raw seeds.  A clause that a correctly-built corpus is expected to violate is not
a bar; it is a prediction, and it was falsified twice.

**What the capture-side clause exists FOR is the other thing**: 8080/BRKEM is
DEFERRED BY USER DECISION, so an entry must be *seen* and *named*, never
silently scored.  That is D9's binding capture-side clause, and it is what the
replacement registers.

### 29.2 THE TWO SEEDS, READ OFF THE ARTIFACT — AND **A CORRECTION THE TASK BRIEF DOES NOT CARRY**

Read from `sw/testdata/campaigns/fz2e/results.jsonl` at this commit, not from
recall.  There are **2** and they are both in the enriched population:

| seed | tier | `ps3_8080` | `ps3_8080_core` | **`arch_ok`** | `mech` | verdict | `bad_rows` |
|---|---|---|---|---|---|---|---|
| `fz2e/509069` | soup | **true** | true | **true** | `REACHED` | `FUNCTIONAL` (`func:R@94`) | 1,126 |
| `fz2e/521059` | raw | **true** | true | **true** | `REACHED` | `KNOWN_ACCEPTED` (`open_bus`) | 2,814 |

`fz2c` (census) carries **0**.  Neither seed has `has_brkem`, and both have
`no8080: true` at generation, so both pairs were created at RUNTIME — §14.4's
reading, unchanged.  (§22.x already records that §14.4's second seed was
`fz2e/534020` and this capture's is `fz2e/521059`; that observation stands and
is not re-opened.)

**THE DETECTOR IS WORKING ON BOTH.**  Both carry `ps3_8080` **true**.  The
brief's first requirement is met on the artifact.

**THE BRIEF'S SECOND REQUIREMENT CONTAINS A STATEMENT THAT THE ARTIFACT
REFUTES, AND IT IS REPORTED HERE RATHER THAN QUIETLY DROPPED.**  The brief
defines *discarded* as *"every such seed is dispositioned by that class (enters
no rate's numerator, per the existing E-1 arithmetic which computes over the
full stratum)"*.  Against `sw/fz2_w1.py`'s C-1 block:

* E-1's numerator is `ok = sum(1 for r in sel if r.get("arch_ok"))` — **seeds
  that REACHED the terminator** — taken over the full stratum `sel`.
* The disposition set `_d3 = arch_restart or ps3_8080 or wrote_term` is
  consulted **only** on `bad = [r for r in sel if not r.get("arch_ok")]`.  It
  feeds E-1c (the UNDISPOSITIONED count) and it feeds **nothing else**.
* **Both `ps3_8080` seeds have `arch_ok: true`.**  Both are inside a scored
  stratum (`fz2e/509069` stratum 21, soup; `fz2e/521059` stratum 33, raw).
  Therefore **both are in E-1's `reached` numerator, for both tiers**, and
  `_d3` is never asked about either of them.

**Nothing in the existing arithmetic discards a runtime 8080 entry that
DUMPED.**  The disposition machinery was built to explain a *non-dump*; these
two seeds dumped.  The brief's parenthetical is therefore not a description of
the existing arithmetic — it is a *proposal to change it* — and it cannot be
both, so this amendment does not pretend otherwise.

### 29.3 THE CLAUSE AS RE-REGISTERED — THREE NAMED COMPONENTS, EACH COMPUTED

C-3 = **generation clause (unchanged)** AND **runtime clause (A-11)**, where the
runtime clause is the conjunction of:

| id | text | teeth |
|---|---|---|
| **R1 — DETECTED** | over **every retained capture in both campaign ids**, the socket-leg predicate `fuzz_campaign._ps3_8080(real, line.win)` recomputed off the banked rows **agrees with the banked `ps3_8080` column**: 0 disagreements.  And the column is present on all 3,840 lines (`ps3_scoreable`) | **YES.**  An independent recomputation from rows.  A detector that silently stopped firing, or a column that stopped being written, fails here |
| **R2 — DISPOSITIONED BY THE CLASS** | **0** `ps3_8080` seeds counted UNDISPOSITIONED by C-1's arithmetic | **NO — THIS IS A TAUTOLOGY OF THE CODE AND IS DECLARED AS ONE.**  `ps3_8080` is a term of `_d3`, so a `ps3_8080` seed can never be undispositioned.  It is computed and reported for completeness and it is worth **nothing** as evidence.  Saying so is the point |
| **R3 — IN NO SCORED RATE'S NUMERATOR** | **0** `ps3_8080` seeds inside a scored stratum with `arch_ok` true, i.e. none in E-1's `reached` count | **YES.**  This is the brief's parenthetical taken literally, and it is the only component with teeth on *discard* |

### 29.4 THE READING IS CHOSEN **AGAINST** CONVENIENCE, AND THE VALUES ARE ALREADY KNOWN

This amendment is written after the three components were measured, so it
registers no prediction and claims none.  **The values are stated here, before
the rescore, so that the choice of reading can be audited against them:**

```
R1  0 disagreements over 736 retained captures   (509 fz2c + 227 fz2e)
R2  0 undispositioned ps3_8080 seeds             (tautological)
R3  2 ps3_8080 seeds in E-1's reached numerator  (fz2e/509069, fz2e/521059)
```

* Gate on **{R1, R2}** only — dropping the brief's parenthetical — and C-3 reads
  **MET**.
* Gate on **{R1, R2, R3}** — the brief's text taken whole — and C-3 reads
  **MISSED**.

**THE GATE IS {R1, R2, R3}.**  The reasons, in order:

1. The brief says, of the two seeds, *"if either is NOT discarded, that is a
   finding and the new clause is MISSED, not MET"*.  R3 is the only component
   under which "NOT discarded" can be true of anything, so dropping it would
   make that sentence unreachable.
2. Dropping R3 **after** measuring it at 2 would be choosing a predicate on the
   data that decides it — the §64.1 pattern, in the same sitting the amendment
   invokes §64.1 against the old clause.
3. {R1, R2} alone is close to vacuous on this corpus: R2 is a tautology and R1
   is a self-consistency check.  A detect-and-discard clause with no discard
   component is a detect clause.

**The stricter reading is the one that fails, and it is taken for that reason,
not in spite of it.**

### 29.5 THE NON-VACUITY DEMONSTRATION — RUN, WITH ITS DENOMINATORS

`python3 sw/fz2_a2_replay.py`, the O-1 / A-2 control, offline, reading only
checked-in captures.  The detector under A-2's chosen form (**socket leg, T1,
`CODE`**):

| population | n | fires | what it shows |
|---|---|---|---|
| **`t30-brkem`** — `timed_fuzz.native_exclusion`'s own 8080 bank, **disjoint from this corpus** | 116 pairs | **87 / 116** | the predicate still detects genuine 8080 entry.  **This is the live-detector proof** |
| **CONTROL** — 380 `wr1` + 2 `fz2c-prereg-A1-archive` archived board pairs, no known 8080 entry | 382 pairs | **99 / 382** | it is not a constant-false predicate off the brkem bank either |
| **this corpus, recomputed off retained rows** (R1) | 736 retained | **2** | it fires in-corpus, and on exactly the seeds the lines name |

The tool's own falsifier block reports `PASS: 0 failure(s)` and additionally
reproduces O-1: the **core** leg at T1 fires **116/116** and **382/382** (fires
on everything), and at T2 fires **0/116** (detects nothing) — which is why A-2
put the clause on the socket leg alone and why neither core-leg form could carry
a detect-and-discard clause.

### 29.6 WHAT A-11 CHANGES IN THE TREE

1. **`docs/notes/fz2_corpus_prereg_2026-08-08.md`** — this section.  §6's C-3
   row is superseded **in its runtime clause only**, by the note appended
   below it; its generation clause is untouched.
2. **`sw/fz2_w1.py`**, C-3's block only — the `registered` string and the
   three measured components.  **No other bar's code is touched**, and E-1's
   arithmetic is **NOT** edited: R3 *reports* that two seeds are in the
   numerator, it does not remove them.  Removing them would move C-1, which
   this sitting is not authorised to do.
3. **`sw/testdata/fz2/fz2_bars.json`** — regenerated.  Registered leaf-diff:
   **only `ts` and leaves under `bars["C-3"]` may move.**

### 29.7 WHAT IS **NOT** DECIDED HERE, AND BELONGS TO THE COORDINATOR

**Whether a `ps3_8080` seed that DUMPED should be removed from E-1's numerator**
is a decision about a registered bar, taken after seeing data, and it is not
taken in a patch.  It would move C-1's four rates and this sitting's leaf-diff
gate forbids that.  It is named, measured (**2 seeds, one per tier**), and left
open — the §26.3 habit.

**And the sharper form of the same question, stated because a reader will reach
it anyway**: `fz2e/509069` is banked `FUNCTIONAL` with **1,126** divergent rows
and signature `8cb79b8ba571898b`.  If it entered 8080 mode, that divergence is a
**deferred-feature** divergence.  Nothing in the corpus currently keeps it out
of the regression bank on that ground.
