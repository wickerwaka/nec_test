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
