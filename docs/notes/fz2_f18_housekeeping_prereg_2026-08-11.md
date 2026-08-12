# PRE-REGISTRATION — TWO ITEMS BOOKED BY THE FLASH #18 SITTING

    branch      fuzz-v2-on-relanding
    base        770c0d1b85   (FLASH #18 RESULTS)
    date        2026-08-11
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.
                No Quartus compile.  Offline throughout.

    item 1      re-derive the materiality census + IMMATERIAL disposition
                against the FLASH #18 ledger, and return
                `fz2_immaterial falsify` to PASS
    item 2      `sw/quartus_gate.py --retention`, and make the env-var form
                REFUSE

**THIS FILE IS COMMITTED BEFORE EITHER TOOL IS RUN.**  Every number in §1 is
DERIVED — from `fz2_flash18_results_2026-08-11.md`, from the F17-era census and
disposition documents, and from the two tools' own source — and not one of them
is read off a run of `fz2_materiality` or `fz2_immaterial` on the F18 ledger.
Where the derivation is *provably incomplete*, §1.4 says so and registers the
alternatives instead of guessing between them.

---

## §0 WHY THESE TWO, AND WHY NOW

Both were **booked by the sitting that measured them and deliberately not done
in it**:

* `fz2_flash18_results_2026-08-11.md` §4.7a — **P-7a MISSED on both clauses.**
  `fz2_immaterial falsify` reports **G6 and G7 FAIL** because both are
  doc-vs-derivation cross-checks against a **FLASH #17-era snapshot**
  (113 failures / 21 IMMATERIAL / working residue 92) while the derivation on
  the F18 ledger is **110 / 24 / 86**.  *"Editing a document to clear a
  falsifier in the same sitting that measured the failure is the move this
  campaign's own rules distrust, even when benign."*  §9 OPEN item 1.
* `fz2_flash18_results_2026-08-11.md` §1.2 — **an E-6 HARD STOP fired.**
  `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` is **accepted-and-ignored**:
  `build()` runs `quartus_sh --flow compile` with no `--verilog_macro` and
  never reads the environment.  §9 OPEN item 2, and §1.2's own words: *"a
  `--retention` flag is the obvious fix and it needs its own
  pre-registration."*  **This is that pre-registration.**

---

# ITEM 1 — THE RE-DERIVATION

## §1.1 WHAT IS AND IS NOT BEING RE-DERIVED

The ledger is **already** the F18 one: `sw/fz2_ledger.py:CURRENT` is
`sw/testdata/fz2/fz2_failure_ledger_f18_2026-08-11.json`, and both tools read
it through `fz2_ledger.load()`.  **Nothing about the derivation changes.**  No
clause of `evidence()` is touched, no class boundary moves, `CYCLE_DEFINING`
stays `("bs", "t")`, and no seed is named in any tool.  What changes is the two
**documents** the falsifier PARSES, and — see §1.5 — the **scope** the parser
reads them at.

## §1.2 THE PREDICTED PARTITION — PRIMARY POINT

Derived from the F18 results document's own statements plus F17 arithmetic:

| class | F17 (registered) | movement, derived | **F18 PREDICTED** |
|---|---:|---|---:|
| FUNCTIONAL | 48 | KM's three seats LEFT the ledger, all three FUNCTIONAL at F17 | **45** |
| TIMING | 33 | phantom-T1's three seats moved TIMING → TRANSIENT | **30** |
| TRANSIENT | 2 | + phantom-T1's three | **5** |
| COSMETIC | 19 | unmoved | **19** |
| UNSCOREABLE | 11 | unmoved | **11** |
| **total** | **113** | LEFT 3 / ENTERED 0 | **110** |
| **IMMATERIAL** (transient + cosmetic) | **21** | + the three seats | **24** |
| **working residue** | **92** | | **86** |
| `TIMING_RECONVERGED` | **7** | none of the seven is a seat | **7** |

The derivation, stated so it can be checked rather than trusted:

1. **LEFT 3 / ENTERED 0** (F18 results §4.3, §4.4).  The three that left are
   KM's seats `fz2c/404041`, `fz2e/501066`, `fz2e/513019` — all three named in
   the F17 census §4.1 as two-sided FUNCTIONAL seeds.  So FUNCTIONAL
   48 − 3 = **45**, and total 113 − 3 = **110**.
2. **The three that entered IMMATERIAL are exactly phantom-T1's seats**
   `fz2c/404071`, `fz2e/514044`, `fz2e/516001`, at `TRANSIENT` / `bs=1`
   (F18 results §4.7a, §4.2).  None appears in the F17 census's FUNCTIONAL
   lists (§4.1, §4.2), in its 21 IMMATERIAL (disposition §3) or in its 11
   UNSCOREABLE (§2.4), so all three were **TIMING** at F17.  TIMING
   33 − 3 = **30**; TRANSIENT 2 + 3 = **5**; IMMATERIAL 21 + 3 = **24**.
3. **UNSCOREABLE 11 and residue 86** are stated outright by the F18 results
   document's own banner text (110 / 24 / 86 = 45 + 30 + 11), which is a
   record of that sitting's measurement.
4. **`TIMING_RECONVERGED` = TIMING seeds with `done_delta == 0`.**  The F17
   seven are `fz2c/406073`, `fz2c/407064`, `fz2e/511014`, `fz2e/512062`,
   `fz2e/518006`, `fz2e/518044`, `fz2e/520000` (disposition §5).  None left the
   ledger and none is a seat, so the predicted count is unchanged at **7**.

## §1.3 THE PREDICTED IMMATERIAL MEMBERSHIP — 24 = 21 + 3, ZERO LEAVERS

**Predicted: the F17 twenty-one, every one of them, plus exactly three.**
The 21 are the disposition document §3 table, unchanged seed for seed; the 3
are `fz2c/404071`, `fz2e/514044`, `fz2e/516001`.

**THE THREE ARE PREDICTED TO MEET ALL SIX CLAUSES, AND THE PREDICTION IS
CLAUSE BY CLAUSE** — including (4) S-STARTS, which is the one a "the schedule
now matches" claim actually rests on:

| clause | predicted on each of the three | why |
|---|---|---|
| **(1) C-CONTROL** | PASS | the F18 closing control scored `first_bad` identical on 110/110 (results §5.2); a control failure would have to be a NEW instrument defect |
| **(2) D-PROOF** | PASS, both legs dump | they were TIMING at F17, and TIMING requires two dumps by construction (a missing dump is FUNCTIONAL or UNSCOREABLE) |
| **(3) D-IDENT** | PASS, 15/15 identical | same: TIMING at F17 means the dumps were already bit-identical, and the landing removed rows rather than adding them |
| **(4) S-STARTS** | PASS, 0 / 0 unmatched | **this is the load-bearing one.** The residual diff is ONE row on `bs`. `fz2_materiality._cycles` bounds `fuzz_classify.extract_txns`, which keys the cycle on **`t`, not `bs`** — the fact the disposition document's own P1 perturbation rests on (§6.1: *"it adds no diff row and moves no cycle start — `extract_txns` keys on `t`, not `bs`"*).  A one-row `bs` difference therefore cannot make a cycle start where the other leg has none |
| **(5) S-DONE** | PASS, `done_delta == 0` | at F17 they were TIMING with `done_delta != 0` **or** with unmatched starts; the landing collapsed 905 / 1,261 / 1,154 diverging rows to **1**, so both legs now run the same schedule to the terminator |
| **(6) DIVERGENT** | PASS, `bad_rows == 1` | `bad_rows == 0` was registered as a FINDING and did not occur (results §4.2) |

⚠ **IF ANY CLAUSE FAILS ON ANY OF THE THREE, THAT IS A REGISTERED FINDING AND
THE SEED IS NOT ADMITTED.**  The class is COMPUTED by `evidence()`; this
document does not get to put a seed in it.  A miss here is reported as a miss
and the document is written to whatever the derivation says.

## §1.4 ⚠ THE PREDICTION IN §1.2 CANNOT BE FULLY RIGHT, AND HERE IS THE PROOF

The FLASH #18 sitting measured **G6 FAIL — 6 / 8 registered cells disagree**
(results §4.7a).  G6's eight cells are the five class counts, `IMMATERIAL`, the
total, and `TIMING_RECONVERGED` (`fz2_immaterial.cmd_falsify`).  Scoring §1.2's
partition against the F17 document gives only **FIVE** disagreements —
FUNCTIONAL 48≠45, TIMING 33≠30, TRANSIENT 2≠5, IMMATERIAL 21≠24, total
113≠110 — with COSMETIC (19), UNSCOREABLE (11) and `TIMING_RECONVERGED` (7) all
agreeing.  **Six were measured.  So exactly one more cell disagrees, and
UNSCOREABLE is fixed at 11 by the results document's own arithmetic
(45 + 30 + 11 = 86).**

**Therefore exactly one of these two branches is true, and both are registered
NOW rather than chosen after the run:**

| branch | what it means | consequences |
|---|---|---|
| **A — `TIMING_RECONVERGED` ≠ 7** | COSMETIC stays 19 and TRANSIENT is 5, as §1.2 says; the reconverged count moved because a still-TIMING seed's `done_delta` changed. This is *available*: the corpus lost **345 rows more** than the six seats alone account for (results §4.3, P-3a), so seeds outside the seats did move rows | §1.2's class table stands verbatim; only the reconverged cell is re-registered |
| **B — COSMETIC ≠ 19** | a member moved COSMETIC ↔ TRANSIENT without leaving IMMATERIAL, so TRANSIENT ≠ 5 while TRANSIENT + COSMETIC = 24 and reconverged = 7 | §1.2's TRANSIENT/COSMETIC split is wrong by the same amount in each direction; the IMMATERIAL total and the membership in §1.3 still stand |

**Registered call: BRANCH A**, on the §1.3 clause-4 argument — a `bs`-only row
cannot move a cycle start, so the TRANSIENT/COSMETIC boundary is the *stablest*
cell in the table, while `done_delta` is measured on a quantity that provably
moved elsewhere in the corpus.  **If branch B is what runs, this call is a MISS
and is reported as one.**  A third outcome — anything that contradicts BOTH —
is a finding against the F18 results document's own `6 / 8`, and it is
reported as that and not absorbed.

## §1.5 THE DOCUMENT SHAPE, AND ONE PARSER CHANGE — DECLARED IN ADVANCE

**The A-14 pattern: supersession, never overwrite.**  Both documents keep every
F17 table **verbatim**, under a dated *"SUPERSEDED BY FLASH #18"* banner.  The
F18 block is the LIVE one.  Physical placement follows this repo's dominant
idiom (CLAUDE.md's own board line: current first, *"superseded, kept because a
fabric figure is only readable against its own bitstream"* below).

**THE PARSER CHANGE, AND WHY IT IS NOT MOVING A GOALPOST.**  As written,
`fz2_immaterial.census_doc()` runs its three regexes over the **whole census
document**: `_CENSUS_ROW` takes the LAST match (so a superseded table below
would win) while `_CENSUS_IMM` / `_CENSUS_RECONV` take the FIRST (so a
superseded table below would lose).  Those two rules point in opposite
directions, so **no placement of a history section satisfies both** and the
document could not carry its own history without lying to its own falsifier.

The fix is the idiom **already in the same file** for the other document:
`dispo_doc()` reads only between `<!-- IMMATERIAL-MEMBERS-BEGIN/END -->`,
precisely so *"a seed named in prose elsewhere is not a claim of membership and
must not be parsed as one."*  Registered change:

1. `census_doc()` parses **only** between `<!-- CENSUS-PARTITION-BEGIN -->` and
   `<!-- CENSUS-PARTITION-END -->`.  **Anchors absent ⇒ G6 FAILS**, naming them
   — exactly as `dispo_doc()` fails when its anchors are absent.
2. `dispo_doc()`'s `WORKING-RESIDUE` headline is searched **inside** the member
   anchors instead of over the whole file, so the whole G7 input is one
   anchored region.  §0's prose statement of the headline stays, unparsed.
3. The F17 member table keeps its content byte-identical; its anchors are
   renamed to `<!-- IMMATERIAL-MEMBERS-F17-BEGIN/END -->` so exactly one live
   pair exists.

**Both edits can only make the gate STRICTER** (a missing anchor is a FAIL that
did not exist before, and a claim outside the anchors stops counting as a
claim).  Neither touches a bar's meaning, a clause, or a class boundary.
**Registered: `falsify` must still be demonstrated to FAIL on a perturbation
after the change** — §1.6 P6.

## §1.6 THE BARS FOR ITEM 1

| # | bar | how it is scored |
|---|---|---|
| **H-1** | `fz2_materiality` controls on the F18 ledger: **C-ROW 110/110, C-ARCH 110/110**, exit 0 | the census is quotable or it is not |
| **H-2** | the derived partition equals §1.2's, **or** the miss is reported cell by cell under §1.4's registered branches | point prediction, reported as registered |
| **H-3** | IMMATERIAL membership = the F17 twenty-one **plus exactly** `fz2c/404071`, `fz2e/514044`, `fz2e/516001`, **zero leavers** | set for set, printed |
| **H-4** | each of the three meets **all six clauses**, printed clause by clause | §1.3; a failing clause is a FINDING and the seed is not admitted |
| **H-5** | `fz2_immaterial falsify` exits **0**, G1–G8 all PASS | the booked repair |
| **H-6** | **P6 — the falsifier is demonstrated to FAIL after the parser change.** One perturbation, applied to a COPY outside the repo, caught by a NAMED bar | a falsifier that has only ever passed has not been shown to be one |
| **H-7** | `TIMING_RECONVERGED` membership re-derived and **stated by name** on F18; the user's ruling of 2026-08-11 (*"Timing reconvergence seeds are material"*) **carries forward unchanged** | they stay MATERIAL, in the residue, whatever the count |
| **H-8** | `fz2_w1 lint` PASS · `fz2_w1 bars` **11/11 MET** · `test_artifact` **45/45** · **zero diffs under `sw/testdata/`** except a legitimately regenerated `fz2_bars.json` (timestamp churn reverted) | nothing moves |

**H-8's `sw/testdata/` clause is a HARD STOP**: this work writes nothing into
any banked artifact, exactly as the F17 disposition did not.

---

# ITEM 2 — `sw/quartus_gate.py --retention`

## §2.1 THE FLAG'S CONTRACT, REGISTERED

**`--retention` runs the recorded four-step manual recipe**, verbatim as
`fuzzv2_retention_prereg_2026-08-08.md` §2 and §6.1 record it (and as four
earlier pre-registrations record it in identical words), from the same clean
deleted `db` / `incremental_db` / `output_files_ucore` the control build uses:

    quartus_map --verilog_macro="X1_AD_RETENTION=1" nec_test -c nec_test_ucore
    quartus_fit  nec_test -c nec_test_ucore
    quartus_asm  nec_test -c nec_test_ucore
    quartus_sta  nec_test -c nec_test_ucore

then the gate's **existing** parse, scoring and receipt path — unchanged, and
in particular `parse_configuration()` is **not touched**: the receipt must
derive **`RETENTION (X1_AD_RETENTION=1)`** off the reports, never off the flag.
*A flag that asserted its own configuration would be the `4bb65d2ab6` defect
the derived label was built to catch.*

Registered specifics:

* **E1 (`gen_ucore_qsf --check`) still runs BEFORE**, and the post-build `.qsf`
  regeneration still runs AFTER, exactly as on the control path.
* **All four stages' output goes to the one log** the gate already writes and
  hashes into `reports`; a non-zero rc from any stage stops the remaining
  stages and is recorded.
* `--retention` is **incompatible with `--parse-only`** (there is nothing to
  build) and is refused as a usage error.
* **Default behaviour is unchanged.**  Without the flag the gate is the CONTROL
  build it has always been, byte for byte in its command list.

## §2.2 THE ENV-VAR FORM MUST **REFUSE**, LOUDLY

Registered: **if `X1_AD_RETENTION` is set in the environment and `--retention`
was not given, the gate REFUSES and exits 2** (`2` is already this gate's *"the
gate could not run"* code — a refused invocation is exactly that, and it is not
a PASS and not a RED).  The message names the FLASH #18 finding, the receipt
that caught it (`aa3ca3e028dff7d2…`), and the two correct invocations.

**Accepted-and-ignored becomes refused-with-reason.**  This is the CLAUDE.md
trap — *"verify a flag exists AND that the callee accepts it"* — closed
permanently in the one place it fired: the variable can no longer reach a run
that will not honour it.

With `--retention` **given**, an env var of the same name is harmless (the
macro travels on the command line) and is allowed; the receipt still derives
the configuration from the reports.

## §2.3 THE FALSIFIER — STRUCTURE, NOT A COMPILE

**No full retention build is run this sitting, and that is registered as a
deliberate choice, not an omission.**  The recipe is already proved: FLASH #18
ran it and its receipt `277d5ccf0f8b9398…` self-labels
`RETENTION (X1_AD_RETENTION=1)` with an `.rbf` differing from the control's,
and it is the bitstream on the board.  A ~10-minute compile per configuration
would re-prove Quartus, not the flag.  **What is unproved is the flag's own
plumbing, and that is what is tested.**

`sw/test_quartus_gate.py`, new, offline, no Quartus binary required:

| # | check | what it forbids |
|---|---|---|
| **Q1** | `--retention` produces **exactly** the four commands above, in order, with the macro on `quartus_map` only | a flag that builds a control and calls it retention |
| **Q2** | the default path produces **exactly** `quartus_sh --flow compile nec_test -c nec_test_ucore` — unchanged | a fix that changes the control build |
| **Q3** | `X1_AD_RETENTION=1` in the environment **without** `--retention` exits **2** and the message names `X1_AD_RETENTION` and `--retention` | the accepted-and-ignored trap re-opening |
| **Q4** | `X1_AD_RETENTION=1` **with** `--retention` does NOT refuse | a refusal that blocks the correct invocation |
| **Q5** | with the variable **unset**, the default path does not refuse | a refusal that fires on every run |
| **Q6** | `--retention --parse-only` is refused as a usage error | a flag that silently does nothing |
| **Q7** | `parse_configuration()` is **not** consulted by the flag — the derived label still comes from the reports, demonstrated on a synthetic report tree | a flag that asserts its own configuration |

**`--dry-run` is added** so Q1/Q2 are answerable at the CLI by a reviewer and
not only from inside a test: it prints the command list the invocation would
run and exits without compiling.

## §2.4 THE BARS FOR ITEM 2

| # | bar |
|---|---|
| **Q-A** | `python3 sw/test_quartus_gate.py` — **Q1–Q7 all PASS**, exit 0 |
| **Q-B** | `python3 sw/test_artifact.py` — **45 / 45**, unchanged |
| **Q-C** | `python3 sw/quartus_gate.py --help` names `--retention` and `--dry-run` |
| **Q-D** | **no Quartus compile is run**, and the results document says so |
| **Q-E** | the CONTROL command list is **byte-identical** to the pre-change one (Q2), and no receipt schema key changes |

---

## §3 HARD STOPS

1. **Any write under `sw/testdata/` other than a regenerated `fz2_bars.json`.**
2. **Any edit to `evidence()`'s six clauses, to `CYCLE_DEFINING`/`VALUE_ONLY`,
   or to any class boundary.**  The re-derivation is a document repair plus a
   parser SCOPE change; a clause edit would be re-registering the class after
   seeing the result.
3. **Any seed list appearing in either tool.**  The class is derived per seed
   on every invocation; that is the A-14 property this disposition carries.
4. **`fz2_w1 bars` moving off 11/11**, or any bar's verdict changing.
5. **A Quartus compile.**  Offline sitting; item 2 ships with a structure test.
6. **Admitting a seat that fails a clause** in order to reach 24.

## §4 WHAT WOULD MAKE THIS SITTING A MISS

* the derived partition contradicting BOTH §1.4 branches (a finding against the
  F18 results document's own `6 / 8`);
* any of the three seats failing a clause (reported, seed not admitted);
* `falsify` passing but not being demonstrable as failing (H-6);
* the env-var refusal not firing, or firing on the correct invocation.

Each is reported in the form it is registered in here.  Nothing is
re-registered after the fact.
