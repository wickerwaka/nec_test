# PRE-REGISTRATION — re-deriving the banked `replay_verdict` column

**Branch** `fuzz-v2-on-relanding`, **tree** `921e756534`, **date** 2026-08-11.
**Offline only. No board, no RTL, no bitstream, no re-capture.**
**This document is committed BEFORE the rewrite it registers.**

This sitting takes the work item `docs/notes/cfb_tier_prereg_2026-08-11.md` §R.6
booked and did not take:

> **THE NEXT WORK ITEM, BOOKED NOT TAKEN: re-derive `replay_verdict` (and the
> ledger's replay signatures) on the mapped classifier**, under its own
> pre-registration, with the movement reported in place — the INV-1 precedent
> (`invalidation_ledger.md` § CLOSURE).

Nothing in this sitting fixes an engine, a testbench or a capture. The
classifier was fixed at `09ec85e4bb`; this sitting brings the bank's **derived**
column into agreement with the fixed classifier, **by recomputation, not by
edit**, and reports every movement.

---

## 0. Baseline, measured at `921e756534` BEFORE this document was committed

```
check_fuzz_bank: FAIL | 621 banked seeds | stable 531 improved 0 worse 90 |
gen_drift 0 regen_err 0 | float-floor 35 | new-sig TIMING 148
```

**Exactly the figure re-registered RED at `921e756534`** — 90 `WORSE` lines
printed, 0 `IMPROVED`, 0 `GEN-DRIFT`, 0 `REGEN/REPLAY ERROR`. The RED is
reproduced on this tree before anything is written.

---

## 1. The exact field set being re-derived — enumerated from the code

`sw/fuzz_bank.py:257-273` (`_write_bank`) is the only site that writes anything
through `check_fuzz_bank.replay_classify`:

```python
from check_fuzz_bank import replay_classify
_sha, rv, rsig, rsub = replay_classify(entry, _ENGINE)
entry["replay_verdict"] = rv
entry["replay_sig"]     = rsig
entry["replay_sub"]     = rsub
...
for _s in {r.get("sig"), rsig}:
    if _s:
        ledger_sigs.append((_s, r["verdict"], r["tier"], r.get("waits"), klass))
```

and `_update_ledger` folds `ledger_sigs` into
`tests/v30/fuzz_bank/sig_ledger.json`.

**Therefore exactly FOUR things are outputs of the defective call site, and
exactly those four are re-derived:**

| # | what | where |
|---|---|---|
| 1 | `replay_verdict` | each of the 621 banked entries |
| 2 | `replay_sig` | each of the 621 banked entries |
| 3 | `replay_sub` | each of the 621 banked entries |
| 4 | the **replay** contribution to `sigs` in `sig_ledger.json` | one file |

**Everything else written by `_write_bank` is derived from `r` (the campaign
result row) and NOT from `replay_classify`, and is therefore NOT re-derived**,
verified field by field against the code:

* `sigs/<sig>.jsonl` — indexed on `r["sig"]`, the **discovery** signature.
* `results/shard_000.jsonl.gz` — its nine keys are
  `k, seed, tier, cfg_hash, verdict, sub, sig, promoted_reason, image_sha256`;
  **no replay field appears in it** (measured on the tree, not asserted).
* `manifest.json` — `verdict_census` is a `Counter` over `r["verdict"]`, the
  **discovery** verdict.
* the ledger's **discovery** sig contributions — `r["sig"]`, computed by
  `fuzz_campaign._ctx_for`, which has always mapped the tier correctly
  (`cfb_tier_prereg_2026-08-11.md` §R.7). The defect never reached them.

### 1.1 A provenance block is ADDED to each rewritten entry

Following INV-1's closure mechanics (each re-captured entry carries a
`recapture` block naming what it replaced), each rewritten entry gains a
**`rederive`** block: the prior `replay_verdict` / `replay_sig` / `replay_sub`,
the prior `banked_ts`, the fix commit `09ec85e4bb`, this document, and the
archive path. **The movement is then derivable from the artifact itself
forever**, not only from this document.

### 1.2 What is EXPLICITLY NOT TOUCHED

`chip_rows` · `chip_arch` · `image_sha256` · `cfg_hash` · `ov` · `gen_git` ·
`verdict` · `sub` · `sig` · `sigv` · `first_bad` · `bad_rows` ·
`func_mismatch` · `done_real` · `done_sim` · `rule_hits` · `alarms` ·
`brkem_pos` · `lea_mod3_pos` · `evt` · `waits` · `wvec` · `wvec_hex` ·
`wvec_sha256` · `wvec_n` · `no8080` · `nmin` · `nmax_eff` · `has_brkem` ·
`has_tf` · `raw_mode` · `promoted_reason` · `banked_ts` · `cid` · `k` ·
`seed` · `tier`.

**The silicon record is untouchable.** No image is regenerated into the bank, no
capture is re-taken, no `bank_status` predicate (`is_superseded`,
`excluded_of`) is edited, no manifest is edited, no seed leaves or enters any
population. The replayed population stays **621** and it stays the population
`bank_status.seed_paths()` computes, printed exclusions and all.

### 1.3 Chip-capture integrity check — mechanical, before AND after

The re-derivation tool computes, for every one of the 621 entries, a **sha256
over the canonical JSON of every key except the four mutable ones**
(`replay_verdict`, `replay_sig`, `replay_sub`, `rederive`) and requires the
before-hash and the after-hash to be **identical, 621 of 621**. A single
mismatch is a **STOP**, not a warning. The 621 hashes are printed as one
aggregate `untouchable_sha256` in the run record so the check is reproducible
by a third party.

### 1.4 The SUPERSEDED banks are NOT re-derived, and why

`mc1` · `mc2` · `t30-raw` · `t30-brkem` (**3,242 seeds**, SUP-1) carry
`replay_verdict` columns written by the same defective call site. **They are NOT
re-derived in this sitting and cannot be**: plan D9 makes the `0F` scrub
unconditional, so every v1 image regenerates to a different `sha256` and
`replay_classify` returns GEN-DRIFT before it classifies (`3,157 GEN-DRIFT + 85
refused, 0 scored`, `standing_gates.md` §B). Re-deriving them needs a checkout
of a pre-fuzz-v2 generator, which is out of scope here. **This is stated as a
known, bounded residue, not as a completion**: their derived column remains the
defective instrument's output and must not be quoted as anything else.

---

## 2. The register form — and why none of the three fits

`docs/notes/invalidation_ledger.md` carries three registers. Read against this
sitting:

| | INV-n | SUP-n | EXC-n | **this** |
|---|---|---|---|---|
| what is wrong with the **capture** | something | nothing | nothing | **nothing** |
| named **rig defect** | required | NONE | NONE | **NONE** — measured: `gen_drift 0`, `regen_err 0`, 8/8 hand-checked `chip_arch` reproduce |
| granularity | per capture | per campaign | per seed | **per derived column, bank-wide** |
| disposition | out of every gate set, permanently | out of the DEFAULT population, back with a flag | out of numerator AND denominator | **nothing leaves any population — a column is RECOMPUTED in place** |

* It is **not an INV-n**: an invalidation *requires a named rig defect* and its
  disposition is *out of every gate set*. There is no rig defect — the socket,
  the board, the images and the captures are all sound and measured sound — and
  nothing leaves any gate set. Filing it as INV-1's kin would assert a defect in
  silicon data that does not exist.
* It is **not a SUP-n**: a supersession's defining clause is *"nothing is wrong
  with a superseded artifact"* and its predicate is `bank_status.is_superseded`
  over a manifest. Something **is** wrong with this column — it is the output of
  a classifier run outside its declared domain — and no manifest status changes.
* It is **not an EXC-n**: an exclusion is *per seed* and takes the seed out of
  every scored rate. No seed is excluded; all 621 stay scored.

**REGISTERED DECISION: none of the three fits, and it is not forced into one.**
It is filed as a **fourth, named register — `ERR-n`, AN ERRATUM AGAINST A
DERIVED COLUMN** — opened in `invalidation_ledger.md` with the same rigor the
other three carry: what, why, which defect (an *instrument* defect, named and
already fixed, not a rig defect), what replaces it, the archive, gate status,
and a falsifier. Its distinguishing clause, stated so it cannot be confused with
the other three:

> An **ERR-n** is filed when a **DERIVED** column — something the tree computes
> from a capture, never something the rig measured — was computed by an
> instrument since found defective. The capture is true and stays. The column is
> **RECOMPUTED IN PLACE** by the corrected instrument, the originals are
> archived byte-identical, every movement is PRINTED, and the gate returns green
> **by arithmetic — because the banker and the checker now compute the same
> corrected function — with no list edited and no seed excused.**

**This entry is `ERR-1`.**

---

## 3. The archive — before a byte is rewritten

Following INV-1's `sw/testdata/inv1-archive/`:

* `sw/testdata/cfb-tier-archive/{fz2c,fz2e}/seeds/*.json.gz` — **byte-identical
  copies of all 621 banked entries** as they stand at `921e756534`.
* `sw/testdata/cfb-tier-archive/sig_ledger.json` — byte-identical copy.
* `sw/testdata/cfb-tier-archive/SHA256SUMS` — one line per archived file.
* `sw/testdata/cfb-tier-archive/manifest.json` — what/why/count/`archived_utc`
  and the sha256 **of `SHA256SUMS` itself**.

**Deliberately OUTSIDE `tests/v30/fuzz_bank/`**, for INV-1's own reason:
`bank_status.seed_paths()` globs `*/seeds/*.json.gz` under that root, so an
archive placed inside it would silently grow the replayed corpus.

The archive is committed **in its own commit, before the rewrite commit**. (The
originals are also in git history at `921e756534`; the copy exists so the
guarantee does not depend on that.)

---

## 4. PREDICTIONS — registered before the rewrite

### P-1 — the gate figure

```
check_fuzz_bank: PASS | 621 banked seeds | stable 621 improved 0 worse 0 |
gen_drift 0 regen_err 0 | float-floor 0 | new-sig TIMING 0
```

`float-floor 0` and `new-sig TIMING 0` are part of the prediction, not
decoration: the first follows because banked and computed agree; the second
follows only if the ledger's replay-sig contribution is re-derived too (field
#4). If the ledger leg is skipped or partial, `new-sig TIMING` will be non-zero
and **that is a MISS**, not a footnote.

### P-2 — the 90 movers must land EXACTLY on §R.2's after-column

`cfb_tier_prereg_2026-08-11.md` §R.2 names all 90 seeds by name. After the
rewrite:

* the **55 soup** seeds listed in §R.2 mechanism A carry
  `replay_verdict = FUNCTIONAL`, `replay_sub = done_mismatch` — **55 of 55**;
* the **35 raw** seeds listed in §R.2 mechanism B carry the tier-B
  fixed-window verdicts — **25 `TIMING`** and **10 `KNOWN_ACCEPTED`**, and the
  25/10 partition is checked against §R.2's own split;
* **no seed outside those 90 changes its `replay_verdict`.**

The mover set is checked **as a set**, against the seed names committed in §R.2
before this sitting existed. Any deviation — a 91st mover, a missing mover, a
verdict that is not the one §R.2 predicts — is a **STOP and report**.

### P-3 — the 531 non-movers are BYTE-IDENTICAL in the verdict column

For the 531 seeds not in §R.2's list, the new `replay_verdict` **and**
`replay_sub` must equal the banked ones exactly. (Their `replay_sig` **will**
move — §R.4/P-4 measured **399** of 621 signatures moving, which is a superset
of the 90 — because `ctx.tier` is hashed into the signature. A signature moving
on a non-mover is **expected and registered here**; a *verdict* or *sub* moving
on a non-mover is a STOP.)

### P-4 — the sub-only movers

§R.5 P-3 measured **10 sub-only movers** (verdict unchanged, all soup,
`func:<kind>@<pos>` → `done_mismatch`). These are **inside** the 531 by P-3's
definition and would violate it. **Registered correction to P-3, made in
advance rather than discovered**: the byte-identity clause is over
`replay_verdict` for all 531, and over `replay_sub` for **521** of them; the 10
seeds §R.5 names are expected to move their `sub` and no other. They are
itemized in the run record. **A sub mover NOT in §R.5's 10 is a STOP.**

### P-5 — the untouchable hash

621 of 621 entries' untouchable-field hash identical before and after
(§1.3). Anything else is a STOP.

### P-6 — the ledger arithmetic

Measured on the tree before the run and registered here so the arithmetic is
falsifiable: of the 621 entries, **364** carry a non-null banked `replay_sig`
and **257** carry `null`; those 364 span **350 distinct** signatures, **all 350
present in `sig_ledger.json`**, and **0** of the 364 equal their own entry's
discovery `sig`. Removing exactly one count per contributing entry takes **273**
of the 350 keys to zero (they are removed) and leaves **77** with a residual
count — those residuals are the SUPERSEDED banks' contributions, which are
**not** re-derived (§1.4) and are **not** touched. **No count may go negative.**
A negative count means the ledger was not written by the arithmetic assumed
here and is a **STOP**.

---

## 5. Discipline

* **Printed, never silent.** The tool prints one line per rewritten entry with
  `seed · tier · verdict before→after · sub before→after · sig before→after`,
  and one line per ledger key added or removed. A silent rewrite of 621 entries
  would be the vacuous-gate pattern with the sign flipped.
* **No list is edited to make the gate green.** There is no exclusion list, no
  allowlist and no special case for the 90. The gate goes green because the
  banker's stored value and the checker's computed value are now the same
  function of the same inputs. If it does not, that is the result.
* **The 90 stay quotable as a finding.** They are recorded in §R.2, in the
  `rederive` block of each entry, and in the ERR-1 gate-status table. The green
  gate does not erase them and must never be quoted as if the 90 never happened.
* **A prediction miss is a STOP**, reported as registered, not restated.

---
---

# RESULTS — appended after the run. Nothing above this line was edited.

Applied by `python3 sw/cfb_rederive.py --apply` (tool `32fd811ed7`), archive
`77ecf565d9`, rewrite `a54cc27454`. **Every prediction P-1…P-6 MET. No STOP
fired.**

## R.0 The after figure

```
check_fuzz_bank: PASS | 621 banked seeds | stable 621 improved 0 worse 0 |
gen_drift 0 regen_err 0 | float-floor 0 | new-sig TIMING 0
```

**P-1 MET, clause for clause, including the two clauses that were part of the
prediction rather than decoration**: `float-floor 0` and `new-sig TIMING 0`.
Zero `WORSE`, zero `IMPROVED`, zero `GEN-DRIFT`, zero `REGEN/REPLAY ERROR`
lines printed. `--strict` follows by arithmetic from `new-sig TIMING 0` — the
`ok` predicate differs from the default leg in that term alone.

Before, on the same tree, same bank, same TB binary
(`hdl/tb/obj_dir/Vtb_v30_core`):

```
check_fuzz_bank: FAIL | 621 banked seeds | stable 531 improved 0 worse 90 |
gen_drift 0 regen_err 0 | float-floor 35 | new-sig TIMING 148
```

## R.1 The tool's own summary — dry run and apply, IDENTICAL

```
cfb_rederive: 621 entries | verdict moved 90 | sub moved 100 | sig moved 399 |
untouchable identical 621/621 | ledger +354 -273 (sigs 12303 -> 12384)
```

**The full dry run was scored against every prediction BEFORE `--apply` was
run**, and the applied record reproduces it line for line. `sub moved 100` is
the 90 verdict movers plus §R.5's 10 sub-only movers, which is the arithmetic
P-4 registered.

## R.2 P-2 — the 90 movers land EXACTLY on the committed §R.2 after-column

Scored against the seed names committed in `cfb_tier_prereg_2026-08-11.md`
§R.2 **before this sitting existed**, as a SET:

| clause | measured |
|---|---|
| verdict movers == §R.2's 90, seed for seed | **90; 0 extra, 0 missing** |
| the 55 mechanism-A seeds → `FUNCTIONAL/done_mismatch`, all `soup` | **55/55** |
| their before-column | **`TIMING` 33 · `KNOWN_ACCEPTED` 22** — §R.2's split exactly |
| the 35 mechanism-B seeds, all `raw`, all `SUCCESS` before | **35/35** |
| their after-column | **`TIMING` 25 · `KNOWN_ACCEPTED` 10** — §R.2's split exactly |

**INDEPENDENT CROSS-CHECK.** The baseline `check_fuzz_bank` run printed its own
90 `WORSE` lines with the before verdict and the after `verdict/sub`. Parsed
straight out of that log and compared against the re-derived column: **90 of 90
agree on the verdict AND on the sub.** The gate and the re-derivation tool are
two readers of the same classifier and they do not disagree on a single seed.

## R.3 P-3 / P-4 — the 531 non-movers

| clause | measured |
|---|---|
| non-movers | **531** |
| `replay_verdict` byte-identical | **531/531 — 0 moved** |
| `replay_sub` byte-identical | **521/531** |
| sub-only movers | **10**, exactly §R.5's class: all `soup`, `func:<kind>@<pos>` → `done_mismatch` |

The 10: `fz2c/400068` `fz2c/400078` `fz2c/401020` `fz2c/403008` `fz2c/403044`
`fz2c/404016` `fz2c/404040` `fz2e/512021` `fz2e/516026` `fz2e/516050`.
**They were registered in advance at §P-4 of this document, not discovered
after the fact** — §R.5 of the earlier prereg had already measured the class
and its count, and the byte-identity clause was written around it before the
rewrite rather than relaxed after it.

## R.4 P-5 — the untouchable record

* The tool's own guard: **621/621** entries' non-mutable-key hash identical
  before and after; a single mismatch aborts before anything is written.
* **A SECOND, INDEPENDENT CHECK that does not use the tool's hash function**:
  the live bank compared against `sw/testdata/cfb-tier-archive/` key by key,
  every key except the mutable four — **621/621 IDENTICAL, 0 differing.**
* `chip_rows` alone, aggregate sha256 over all 621 in sorted path order:
  **`5b93d459a9d21425fa9bc7386e705b732ddf8d163cce1d5e2be794b9c5a5b395`** on the
  live bank **and on the archive**. The silicon record did not move.
* The `rederive` block faithfully names the archived triple on **621/621**.
* ⚠ **ERRATUM against §1.3 of this document, above the line and not edited
  there**: §1.3 says the 621 hashes are printed *"as one aggregate
  `untouchable_sha256`"*. They are not aggregated — the run record carries the
  **per-entry** hash on every one of the 621 rows, which is strictly more
  reproducible by a third party than a single digest would have been. The
  clause's intent (a mechanical, externally-checkable record) is met; its
  literal form is not. Stated, not restated.
* `git status` over `tests/v30/fuzz_bank/`: **622 modified files** — 621
  entries + `sig_ledger.json` — and **nothing else**. No manifest, no sig index,
  no result shard.

## R.5 P-6 — the ledger arithmetic, as registered

| registered | measured |
|---|---|
| 273 keys reach 0 and are removed | **273** |
| 77 keys keep a residual count (the SUPERSEDED banks' contributions, not re-derived) | **77** (350 distinct old sigs − 273) |
| no count negative | **0 negative** — no STOP |
| keys added | **354** |
| `sigs` total | **12,303 → 12,384** |

Every added and every removed key was **printed on its own line**. The
newly-added keys carry `first_campaign: "ERR-1-rederive"`, which is true — they
were first written by this re-derivation, not by a campaign — rather than a
back-dated campaign attribution that would have read like provenance it does
not have.

## R.6 What this sitting did NOT do

* **The SUPERSEDED v1 banks are NOT re-derived** (§1.4): `mc1` · `mc2` ·
  `t30-raw` · `t30-brkem`, **3,242 seeds**, still carry the defective
  instrument's `replay_verdict`. They **cannot** be re-derived on this branch —
  plan D9 makes their images unregenerable (`3,157 GEN-DRIFT + 85 refused`), so
  `replay_classify` STOPs before it classifies. **Bounded, stated, not
  completed**; their derived column must not be quoted as anything but the
  defective instrument's output.
* **Nothing was fixed.** No engine, no testbench, no capture, no image, no
  population predicate. The 90 remain a finding about the bank's derived column
  and are recorded in three places that outlive this document: §R.2 of the
  earlier prereg, each entry's own `rederive` block, and ERR-1's gate-status
  table. **A green gate does not erase them.**
* **No list was edited and no seed was excused.** There is no exclusion list for
  the 90, no allowlist, no special case. The gate is green because the banker's
  stored value and the checker's computed value are now the same function of
  the same inputs — which is exactly the property `stable 621` was always
  supposed to assert and, until this sitting, never did.
