# PRE-REGISTRATION — closing the `check_fuzz_bank` dead-tier-branch finding

**Branch** `fuzz-v2-on-relanding`, **tree** `8b8b89a7fe`, **date** 2026-08-11.
**Offline only.** No board, no RTL, no bitstream.
**This document is committed BEFORE the one-line fix it registers.**

The finding is booked in `docs/notes/standing_gates.md` (⚠ BOOKED FINDING
2026-08-11, beside the 621 row). This sitting closes it. It is an
**INSTRUMENT FIX**, so the **U5 comparator precedent governs**: *"nothing was
made worse, something was made visible."* Any figure that moves is quoted with
the instrument change named and itemized mover by mover; nothing is re-scored
silently.

---

## 1. The defect, restated from the artifact

`check_fuzz_bank.replay_classify` (`sw/check_fuzz_bank.py:81`) builds

```python
ctx = fc.Ctx(tier=entry["tier"], ...)
```

`entry["tier"]` is the banked **config literal** `"soup"` / `"raw"`
(`sw/fuzz_bank.py:214`, written straight from `cfg["tier"]`).
`fuzz_classify.Ctx.tier`'s declared domain is `'A'` / `'B'`
(`sw/fuzz_classify.py:511`). `fuzz_campaign._ctx_for` (`sw/fuzz_campaign.py:660`)
performs the mapping `"A" if cfg["tier"] == "soup" else "B"`; **this call site
does not**.

Measured population, this tree: **621 replayed seeds — 296 `soup`, 325 `raw`.**
Every one of them is handed a `tier` outside the domain, so **every**
`ctx.tier == "A"` and `ctx.tier == "B"` test in the replay is False.

The **six** live sites in `fuzz_classify.py`, and what the defect does to each:

| line | branch | with the defect |
|---|---|---|
| 458 | `if ctx.tier == "A":` — the `done_data_both_XXXX` provenance alarm | never fires (alarm → QUARANTINE, so this can only *suppress* a quarantine) |
| 562 | `if ctx.tier == "B":` — raw's **4,000-row capped** diff window | never taken; raw seeds diffed on the UNCAPPED window |
| 586 | `done_real != done_sim and ctx.tier == "A"` — soup's `done_mismatch` | never fires; a soup done-mismatch falls through to the cycle compare |
| 592 | `elif ctx.tier == "A" and done_real and done_sim:` — **the arch-dump comparison** | **DEAD.** The gate replays rows and never compares the architectural dump |
| 598 | `sub = "runaway_both" if ctx.tier == "A" else "window_truncated"` | always `window_truncated`, including on soup |
| 687 | `parts = (SIGV, ctx.tier, …)` — the signature hash | signatures are computed over `"soup"`/`"raw"`, not `A`/`B` |

## 2. Why the gate reads green today — and why that is not evidence

`sw/fuzz_bank.py:261` computes the banked `replay_verdict` by calling
**`check_fuzz_bank.replay_classify` itself**:

```python
from check_fuzz_bank import replay_classify
_sha, rv, rsig, rsub = replay_classify(entry, _ENGINE)
entry["replay_verdict"] = rv
```

So the **same defective call site is both the banker and the checker**. The
round-trip compares a defective computation against itself and is stable by
construction. `stable 621 / improved 0 / worse 0` is a statement about the
*determinism of the instrument*, not about the arch column. The same holds for
`new-sig TIMING 0`: the ledger's replay sigs were written by this call site too,
so a `"soup"`-keyed signature matches a `"soup"`-keyed ledger entry.

This is exactly the vacuous-gate pattern `standing_gates.md` records elsewhere,
and it is why the finding was booked rather than quietly patched.

## 3. The fix — one mapping, one home

`sw/fuzz_campaign.py` gains the mapping as a **named function** and
`_ctx_for` is rewritten to call it (so the mapping does not exist twice in the
same module):

```python
def ctx_tier(tier):
    """The ONE mapping from a config/banked tier literal to Ctx.tier's domain."""
    if tier not in ("soup", "raw"):
        raise ValueError(...)
    return "A" if tier == "soup" else "B"
```

It **raises** on anything outside `{"soup", "raw"}` rather than falling through
to `"B"`, because the whole defect was a silent domain mismatch: a domain error
must be loud.

`sw/check_fuzz_bank.py:81` becomes the one-line change:

```python
ctx = fc.Ctx(tier=fzc.ctx_tier(entry["tier"]), ...)
```

`fuzz_campaign` is already imported there as `fzc`. **No mapping is
duplicated** and no behaviour other than the tier is touched.

## 4. Predictions — what comes alive

Registered before the fixed run:

* **P-1** The **arch-dump comparison comes alive on the 296 `soup` seeds.** A
  soup seed with `done_real and done_sim` and a differing `arch_dump` now
  classifies FUNCTIONAL with `sub = "arch:<fields>"` where it previously fell
  through to the cycle compare.
* **P-2** The **capped raw window comes alive on the 325 `raw` seeds**: the diff
  window becomes `min(len(real), len(sim), 4000)`. Where a raw seed's captures
  are longer than 4,000 rows this can only *shrink* the compared region, so a
  raw verdict can only stay the same or improve on this account.
* **P-3** `sub` strings change on soup runaways: `window_truncated` →
  `runaway_both`. **A `sub` change with an unchanged `verdict` is NOT a mover**
  for the gate (the gate compares verdicts) and is reported separately.
* **P-4** **Signatures change for every seed that has one**, because `ctx.tier`
  is hashed into the signature. Against a ledger written by the defective call
  site this could raise `new-sig TIMING`. **This is registered in advance as an
  instrument effect, not a new mechanism**: a signature is a key over the
  classifier's inputs, and one of those inputs was wrong.
* **P-5** `done_mismatch` comes alive on soup, and the tier-A `done_data_both`
  provenance alarm comes alive — the latter can only turn a non-quarantine into
  a QUARANTINE.
* **P-6 (the null)** It is possible that **zero verdicts move** — that every
  newly-live comparison happens to agree. That is the best outcome and it will
  be stated **as measured**, never as assumed, with the mover table printed
  empty and the arch column proved live by an independent instrument (§6).

## 5. Accounting rule — how a mover is reported

Every seed whose **verdict** moves is itemized with:

`seed · tier · banked replay_verdict → fixed verdict · banked sub → fixed sub ·
WHICH newly-live branch produced it`

and the attribution is made **from the classifier's own fields** (`done_real`,
`done_sim`, `n`, `bad_rows`, `alarms`, arch dumps), not by narration.

**Disposition rule.** A seed that scores **WORSE** after the fix is **a seed
that was being mis-scored as stable**. Its banked `replay_verdict` was written
by the same defective call site (§2), so the "before" is not a truth the tree
regressed away from — it is a defective reading. Such a seed is a **FINDING
ABOUT THE BANK'S DERIVED COLUMN, NOT A REGRESSION OF THE TREE**, and it is
reported that way.

**The banked entries are NOT rewritten in this sitting.** `chip_rows` are true
silicon and are never touched; `replay_verdict` is a *derived* column, and
re-deriving it is a separate decision with its own pre-registration — it is not
smuggled in behind an instrument fix. If movers exist, the gate goes RED and is
**re-registered RED with its mover table**, which is a truthful gate; it is not
made green by editing the data it scores.

**Rig-defect stop.** If the fixed run surfaces something that is not a
mis-scoring — banked dumps that cannot be read at all, `regen_err`, GEN-DRIFT —
the sitting **STOPS and reports** rather than repairing banked data.

## 6. Independent check on the newly-live arch column

The arch comparison is verified **outside the gate**: every banked entry carries
`chip_arch` (`sw/fuzz_bank.py:_entry`), computed by the same `arch_dump` the
classifier calls. On a sample of seeds the replay's `arch_dump(sim)` is compared
against the banked `chip_arch` **by hand**, and the gate's verdict must agree
with that hand comparison. `sw/fz2_materiality.py` reads the same dumps and is
the second reader.

⚠ **The 621 banked seeds are a DIFFERENT POPULATION from the 3,840-seed fz2
corpus** that `fz2_w1 bars` and `fz2_materiality` score. No count from one may
be quoted against the other.

## 7. Re-registration form

* The booked finding in `standing_gates.md` gets an **append-only CLOSED
  addendum** citing this sitting, naming the fix and the measured mover count.
* The gate's 621 row is re-quoted **with the instrument change named**, in the
  three-numbers-all-true style already used there: the old figure is not
  retracted, it is labelled as the figure of the defective instrument.

## 8. Global audit — registered scope

Every `fc.Ctx(` construction in `sw/` is inspected. **Same-mechanism instances
(a tier literal outside `{'A','B'}` reaching classify machinery) are ALL fixed
in this sitting and each is named.** Anything that is a *different* defect is
**BOOKED, not fixed** — including, already identified at this call site and
NOT touched here:

* `has_halt` — `entry.get("has_halt", False)` is False on **621 of 621** banked
  entries because `fuzz_bank._entry` never writes the key. **Inert**: no code in
  `fuzz_classify.py` or `fuzz_accept.py` reads `ctx.has_halt`.
* `with_drift` — never passed by `replay_classify`, so `drift_metrics` is never
  computed on the replay leg. Affects the `drift` field only, not the verdict.
* **the `wvec` axis** — `_ctx_for` treats a wait *vector* as varying
  (`wrand=True, waits=0`); `replay_classify` does not, so **169 of 621** banked
  seeds are classified under a wait class the campaign would not have given
  them. This reaches `fuzz_classify.py:394` (the `tw_in_w0_chip` alarm), the
  signature's wait class, and `fuzz_accept.py:443`. **A DIFFERENT MECHANISM
  FROM THE TIER DOMAIN — BOOKED HERE, NOT FIXED HERE.**

## 9. Regression sweep registered for this sitting

`sw/test_fuzz_accept.py` PASS · `sw/fz2_w1.py lint` PASS · `sw/fz2_w1.py bars`
**11/11** · `sw/fz2_materiality.py` controls **113/113** and class counts
**48/33/2/19/11** byte-identical · `sw/test_artifact.py` **45/45** ·
**zero diffs under `sw/testdata/`** and **zero diffs under
`tests/v30/fuzz_bank/`** (the bank is git-tracked; a diff there would be a
rewrite of banked data and is forbidden).

A **falsifier is added to the test suite** so the defect cannot silently return:
a `Ctx` built from a banked-style entry must carry `'A'`/`'B'`, and
`ctx_tier` must raise on a literal outside its domain.

---
---

# RESULTS — measured 2026-08-11, reported as registered

Appended after the run. **Nothing above this line was edited.**
Fix commit: the one-line call-site change + `fuzz_campaign.ctx_tier`.

## R.0 Baseline (unfixed, tree `8b8b89a7fe`)

```
check_fuzz_bank: PASS | 621 banked seeds | stable 621 improved 0 worse 0 |
gen_drift 0 regen_err 0 | float-floor 0 | new-sig TIMING 0
```

Exactly the registered figure. Population **296 soup + 325 raw = 621**.

## R.1 Fixed (same tree, same TB binary, same bank — only the tier is mapped)

```
check_fuzz_bank: FAIL | 621 banked seeds | stable 531 improved 0 worse 90 |
gen_drift 0 regen_err 0 | float-floor 35 | new-sig TIMING 148
```

**`gen_drift 0` and `regen_err 0`** — every image still regenerates to its
banked `sha256` and every banked capture still reads. **The §5 rig-defect STOP
did not trigger**: this is a scoring movement, not a data defect.

## R.2 The mover table — 90 seeds, 90 attributed, 0 unattributed

Measured by replaying each seed **ONCE** and classifying the same
`(chip, sim)` pair **twice** — once with the literal, once mapped — so the
before/after differ in the tier and in nothing else (no second TB run, no
re-capture). The `bug` column reproduces the banked `replay_verdict` on
**621 / 621**, which is the control that the two columns are comparable.

| n | before | after | mechanism |
|---:|---|---|---|
| 33 | `TIMING/timing` | `FUNCTIONAL/done_mismatch` | **A — soup `done_mismatch` came alive (P-5 MET)** |
| 22 | `KNOWN_ACCEPTED/cadence` | `FUNCTIONAL/done_mismatch` | **A — soup `done_mismatch` came alive (P-5 MET)** |
| 25 | `SUCCESS/clean` | `TIMING/timing` | **B — raw's fixed 4,000-row window came alive (P-2 MET, direction MIS-REGISTERED, §R.4)** |
| 10 | `SUCCESS/clean` | `KNOWN_ACCEPTED/cadence` | **B — raw's fixed 4,000-row window came alive (P-2 MET, direction MIS-REGISTERED, §R.4)** |
| **90** | | | **all raw movers are raw-tier; all soup movers are soup-tier** |

**Mechanism A — 55 movers, every one `soup`.** `fuzz_classify.py:586`
(`done_real != done_sim and ctx.tier == "A"`). All 55 have the done marker on
**exactly one leg** (54 chip-only, 1 sim-only: `fz2c/403000`). The row window
`n` and the divergent-row count `bad_rows` are **byte-identical before and
after** on all 55 — nothing about the comparison changed, only whether a
one-sided done marker is functional evidence. It is, on soup, and the gate was
not asking.

The 55: `fz2c/` 400006 400028 400034 400054 400060 400072 400076 401012 401028
401052 401058 401064 401068 401076 403000 403004 403024 403030 403036 403038
403040 403048 403056 403064 403066 403078 404008 404010 404014 404020 404028
404032 404034 404036 404042 404044 404048 404054 404066 404068 404072 · `fz2e/`
501066 504000 509050 510000 511014 511030 511050 512000 512050 513050 514000
514072 516000 516065.

**Mechanism B — 35 movers, every one `raw`.** `fuzz_classify.py:562`
(`if ctx.tier == "B"` → `diff_rows(..., window=4000)`). `n` moves from the
done-shrunk historical window to the flat 4,000 on every one (e.g.
`fz2c/406004` 580 → 4,000; `fz2c/409034` 2,128 → 4,000) and `bad_rows`
0 → 274…1,962.

The 35: `fz2c/` 406004 406026 406038 406040 406048 406052 406070 406072 407010
407020 407042 407048 407058 407062 409002 409004 409018 409022 409034 409038
409044 409048 409050 409052 409058 409060 409072 409076 410006 410030 · `fz2e/`
518000 518059 523000 527050 528000.

**`float-floor 35` is exactly mechanism B** — 35 banked-SUCCESS seeds that no
longer classify SUCCESS, all raw, cross-checked seed for seed. Not a
fab-vs-TB float event.

## R.3 P-1 — **THE ARCH COLUMN IS LIVE AND IT IS CLEAN. ZERO MOVERS, MEASURED.**

Of the 296 soup seeds:

| | |
|---:|---|
| 296 | soup seeds |
| −65 | the done marker on **one leg only** → mechanism A takes them first |
| −87 | done on **neither** leg (85 QUARANTINE `tw_in_w0_chip`, 1 `ASSERT_PARK`, 1 timing) |
| −21 | a functional **store** mismatch (`func:…`) outranks the arch compare |
| **123** | **REACH the arch-dump comparison — the branch that was dead** |
| **0** | **of them differ.** No seed classifies `FUNCTIONAL/arch:…` |

Verdicts on the 123: `TIMING` 61 · `SUCCESS` 36 · `KNOWN_ACCEPTED` 26.

**This is the best available outcome for the column the finding was written
about, and it is stated as MEASURED, not assumed.** The 90 movers come from the
two *other* dead branches; the arch column, once switched on, agrees on every
seed that reaches it.

**Independent hand-check (§6 of the pre-registration).** Eight soup seeds were
replayed outside the gate and their `arch_dump(chip)` compared against the
banked `chip_arch` field — written at bank time by `fuzz_bank._arch`, a path
the replay never executes. **8 / 8 identical**, so the banked dumps are
readable and reproducible (again: no rig defect). The check also found
`fz2c/402000` with all ten architectural words differing between chip and TB
while classifying `func:…` — i.e. **the arch dumps are not trivially equal, and
the 0 above is precedence, not vacuity**: a store mismatch is reported before
the dump is consulted.

⚠ The 621 banked seeds are a **DIFFERENT POPULATION** from the 3,840-seed fz2
corpus that `fz2_w1 bars` and `fz2_materiality` score. No count here may be
quoted against those.

## R.4 ERRATUM — P-2's DIRECTION WAS MIS-REGISTERED

**§4 P-2 said**: *"the diff window becomes `min(len(real), len(sim), 4000)`.
Where a raw seed's captures are longer than 4,000 rows this can only shrink the
compared region, so a raw verdict can only stay the same or improve on this
account."*

**That is wrong, and it is wrong in the direction that matters.** The window
does become `min(len, len, 4000)` — but the *unmapped* path is not "the whole
capture", it is `diff_rows`'s **done-shrunk** default,
`min(len, len, 4000, dend + 8)` (`fuzz_classify.py:150-163`). On a raw seed the
chip **forges** a done marker out of random bytes, so `dend` lands early and the
default window collapses to a few hundred rows. Tier B exists precisely to
refuse that marker. So the window **GROWS** (440–2,606 → 4,000) and every one
of the 35 raw movers goes the other way: `SUCCESS` → `TIMING`/`KNOWN_ACCEPTED`.

The **mechanism** was predicted correctly and the **prediction of the
direction** was not. It is reported here as registered; the erratum is not a
restatement of P-2.

## R.5 P-3, P-4, P-5, P-6 as measured

* **P-3 — 10 sub-only movers**, verdict unchanged, all soup, all
  `func:<kind>@<pos>` → `done_mismatch` (the same precedence as mechanism A,
  on seeds already FUNCTIONAL). **The `window_truncated` → `runaway_both`
  half of P-3 produced 0**, and the reason is measured, not absent: all 87
  neither-leg-done soup seeds are taken by an earlier `return` (85
  QUARANTINE, 1 `ASSERT_PARK`, 1 downstream sub), so line 598 is not reached.
* **P-4 — MET, and it is the loudest number.** **399** seeds' signatures
  change; **0** seeds keep a non-null signature unchanged. `ctx.tier` is hashed
  into the signature (`fuzz_classify.py:687`), so the ledger's replay sigs are
  all keyed on `"soup"`/`"raw"` and none of them can match a mapped run. This
  is the whole of `new-sig TIMING 148`. **It is an instrument effect, registered
  in advance, and NOT 148 new mechanisms.**
* **P-5 — MET**, 55 movers (§R.2 mechanism A).
* **P-6 (the null) — NOT MET.** 90 verdicts moved.

## R.6 Disposition, per §5 — and what is NOT done here

Every one of the 90 is a seed whose banked `replay_verdict` was written by the
**same defective call site** (`fuzz_bank.py:261` calls `replay_classify`), so
the "before" is not a truth the tree regressed away from. **These are 90
MIS-SCORINGS OF THE BANK'S DERIVED COLUMN, NOT 90 REGRESSIONS OF THE TREE.**
Nothing about the RTL, the model, the TB binary or the silicon captures moved
in this sitting: the identical `(chip, sim)` row pairs are being read by a
classifier that is finally in its own domain.

**THE BANK WAS NOT REWRITTEN.** `git status` over `tests/v30/fuzz_bank/` is
clean; `chip_rows` are true silicon and were never candidates, and
`replay_verdict` — though derived — is **not** re-derived behind an instrument
fix. **The gate is therefore RED, and it is re-registered RED with this table.**
A truthful RED gate is worth more than a green one whose data was edited to
agree with it.

**THE NEXT WORK ITEM, BOOKED NOT TAKEN: re-derive `replay_verdict` (and the
ledger's replay signatures) on the mapped classifier**, under its own
pre-registration, with the movement reported in place — the INV-1 precedent
(`invalidation_ledger.md` § CLOSURE: *"`replay_verdict` was recomputed and the
movement REPORTED"*). Until that is taken and accepted, `check_fuzz_bank`
FAILS by exactly these 90 seeds and the failure is expected, itemized and
attributed.

## R.7 The global audit (§8) — result

**Exactly ONE instance of this defect exists in `sw/`, and it is fixed.**
Every `fc.Ctx(` construction was inspected:

| site | tier passed | verdict |
|---|---|---|
| `sw/check_fuzz_bank.py:81` | `entry["tier"]` — **"soup"/"raw"** | **THE DEFECT — FIXED** |
| `sw/fuzz_campaign.py:660` | mapped | correct; now calls `ctx_tier` |
| `sw/fz2_a1_replay.py:78` | mapped inline | correct — but it maps into an **old `fuzz_classify` loaded from git**, so it cannot import today's helper; left as is, named here |
| `sw/fz2_a10_replay.py:72` | mapped inline | same, same reason |
| `sw/f7a_arbitrate.py:112`, `sw/calibrate_cadence.py:50` | literal `"A"` | in domain; both drive `force_tier: "soup"` campaigns |
| `sw/test_fuzz_classify.py`, `sw/test_fuzz_accept.py` (24 sites) | literal `"A"`/`"B"` | in domain |

No other site reads `entry["tier"]` into classify machinery; the remaining
`r["tier"]` / `e["tier"]` readers (`fuzz_report`, `fz2_ledger`, `fz2_m10`,
`fz2_replay`, `fz2_failview`, `fz2_longinsn`, `fz2_stall`, `sm3_h7_repeat`,
`inv1_recapture`, `fuzz_bank`) are **reporting and provenance**, where the
config vocabulary is the correct one.

**Booked, not fixed** (different mechanisms, §8): `has_halt`, `with_drift`, and
the `wvec` wait-class axis at this same call site.

## R.8 The falsifier (§9)

`sw/test_fuzz_classify.py` gains `_tier_domain_falsifier()` — 9 checks, board-
free and TB-free. It asserts `ctx_tier` maps `soup→A` / `raw→B` and **RAISES**
on `'A'`, `'B'`, `'Soup'`, `''`, `None`, `0`; then, with the regeneration and TB
legs stubbed, it runs `replay_classify` itself on a banked-style entry and
asserts the `Ctx` handed to `classify` carries `'A'`/`'B'`.

**Proved non-vacuous**: with `ctx_tier` monkeypatched back to the identity (the
pre-fix behaviour) all 9 checks FAIL, and the two call-site checks fail with
exactly the defect's signature — `(got 'soup')` and `(got 'raw')`.
