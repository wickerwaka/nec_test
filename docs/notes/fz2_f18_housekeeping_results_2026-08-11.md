# FLASH #18 HOUSEKEEPING — RESULTS, AS REGISTERED

Pre-registration `docs/notes/fz2_f18_housekeeping_prereg_2026-08-11.md`,
committed **`a05af666aa`** — before either tool was run on the F18 ledger and
before a line of item 2 was written.

    branch      fuzz-v2-on-relanding, from 770c0d1b85
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.
    Quartus     NO COMPILE RUN -- registered as a deliberate choice (§2.3),
                and one was ABORTED when a test harness started it by
                accident.  See §3.4; it is reported, not omitted.

**Every bar is reported in the form it was registered in.  Nothing is
re-registered after the fact.**

---

## 0. THE HEADLINE

**BOTH ITEMS ARE DONE AND BOTH FALSIFIERS ARE GREEN AND DEMONSTRABLY
FALSIFIABLE.**  `fz2_immaterial falsify` is **PASS, G1–G8**, against
re-derived documents whose FLASH #17 content is retained verbatim as history;
the IMMATERIAL class is **24 = the F17 twenty-one + phantom-T1's three seats,
zero leavers**, and **18 of 18 clause cells pass on the three**.
`sw/quartus_gate.py --retention` exists, runs the recorded four-stage recipe,
and **`X1_AD_RETENTION=1` without the flag is now REFUSED with exit 2** —
accepted-and-ignored became refused-with-reason.  Its falsifier
`sw/test_quartus_gate.py` is **75 / 75** and **fails on all six nulls**,
including a null that restores the FLASH #18 defect itself.

**The registered §1.4 branch call was RIGHT and is reported as such**:
`TIMING_RECONVERGED` moved **7 → 8**, COSMETIC stayed 19.  **Two things are
reported as MISSES**: two G-bar *denominators* quoted in a document draft
(§1.7), and **a Quartus compile started by accident** (§3.4).

---

# ITEM 1 — THE RE-DERIVATION

## 1.1 H-1 — THE CONTROLS.  **MET.**

    C-ROW   diff_rows reproduces the ledger   110 / 110   PASS
    C-ARCH  arch_dump reproduces the ledger   110 / 110   PASS
    exit 0                                    ledger fz2_failure_ledger_f18_2026-08-11.json
                                              era sof b2a1fe5f8316…  denominator 3,839

## 1.2 H-2 — THE PARTITION.  **MET, EVERY CELL, INCLUDING THE §1.4 BRANCH.**

| cell | registered | **measured** | verdict |
|---|---:|---:|---|
| FUNCTIONAL | 45 | **45** | MET |
| TIMING | 30 | **30** | MET |
| TRANSIENT | 5 | **5** | MET |
| COSMETIC | 19 | **19** | MET |
| UNSCOREABLE | 11 | **11** | MET |
| total | 110 | **110** | MET |
| IMMATERIAL | 24 | **24** | MET |
| working residue | 86 | **86** | MET |
| `TIMING_RECONVERGED` | **branch A: ≠ 7** | **8** | **MET — branch A** |

**§1.4's registered call was BRANCH A and branch A is what ran.**  The
pre-registration proved its own primary partition could not be fully right —
the F18 sitting measured G6 at **6 / 8** cells disagreeing and the primary
partition scored only **5** against the F17 document — and named the two
possible resolutions before the run.  Measured: the sixth disagreeing cell is
`TIMING_RECONVERGED` (7 → 8) and COSMETIC is unmoved at 19, which is branch A
exactly.  **The `6 / 8` the FLASH #18 sitting measured is now accounted for
cell by cell.**

The entrant is **`fz2e/530020`** — `raw`, escaped 15, family D1, `bad_rows`
326, cycle starts 3 / 3, done **1090 on both legs**.  It is **not a seat, not
predicted by mechanism, and is reported not attributed**: it stayed in the
ledger, in TIMING and in the residue throughout, and only its `done_delta`
moved.  This is the ordinary downstream row movement FLASH #18 reported and did
not explain (−345 rows beyond the six seats, results §4.3).  **A falsifier is
registered beside it** in the census: a double capture on one bitstream in
which its two `done` clocks are stable — if they flicker, the membership is
capture noise and 8 is not a ratchet.

## 1.3 H-3 — THE MEMBERSHIP.  **MET, SET FOR SET.**

    the F17 twenty-one, named in the disposition document : all 21 STILL MEMBERS
    leavers                                               : 0
    entrants                                              : 3
    entrants == phantom-T1's three seats                  : TRUE

`fz2c/404071`, `fz2e/514044`, `fz2e/516001`.  Their row counts, cycle counts
and done clocks are unchanged for the other 21 seed for seed.

## 1.4 H-4 — THE THREE SEATS, CLAUSE BY CLAUSE.  **18 / 18 CELLS PASS.**

| clause | `fz2c/404071` | `fz2e/514044` | `fz2e/516001` |
|---|---|---|---|
| (1) C-CONTROL | PASS | PASS | PASS |
| (2) D-PROOF | PASS, both legs dumped | PASS | PASS |
| (3) D-IDENT | PASS, `arch_diff_words` `[]` | PASS `[]` | PASS `[]` |
| **(4) S-STARTS** | **PASS, 0 / 0**, cycles 174 / 174 | **0 / 0**, 233 / 233 | **0 / 0**, 204 / 204 |
| (5) S-DONE | PASS, 1196 / 1196, δ 0 | 1579 / 1579, δ 0 | 2603 / 2603, δ 0 |
| (6) DIVERGENT | PASS, `bad_rows` 1 | 1 | 1 |
| `why` | `None` | `None` | `None` |

**No clause failed on any seat, so no seat was admitted against a failing
clause — the registered finding rule was never invoked.**  `first_bad` reads
**243 / 234 / 583**, which is FLASH #18's own POINT prediction (results §4.2),
reproduced by an instrument that never reads it.

**Clause (4) was argued from the parser before it was measured** and that is
why it is not circular: the residual diff is one row on `bs`, and
`fuzz_classify.extract_txns` keys a bus cycle on **`t`, not `bs`** — the fact
the F17 document's own **P1** perturbation rests on.  A one-row `bs` difference
cannot create a cycle start the other leg lacks.  The measured `0 / 0` is
confirmation, not argument.

## 1.5 H-5 — `fz2_immaterial falsify`.  **PASS, EXIT 0.**

    G1 DUMP PROOF     : 0 / 23    [PASS]
    G2 DUMP IDENTITY  : 0 / 33    [PASS]
    G3 SCHEDULE       : 0 / 80    [PASS]
    G4 NOT UNIVERSAL  : FALSE on 86 / 110    [PASS]
         by first failing clause: cycle_starts 30 · arch 33 · no_dump_proof 23
    G5 CONTROLS       : C-ROW 110/110 · C-ARCH 110/110    [PASS]
    G6 THE CENSUS     : 0 / 8 registered cells disagree    [PASS]
    G7 THE DOCUMENT   : 0 / 25 disagreements    [PASS]
    G8 NO FORK        : 0 / 110    [PASS]   (0 not askable)

    IMMATERIAL FALSIFIERS: PASS

**G7 earned its keep on the way there.**  The first draft of the member table
bolded the three new seeds' name cells, `` | **`fz2c/404071`** | ``, which the
member regex does not match — G7 reported *"derived but NOT named"* on exactly
those three.  **The document was wrong and the gate said so**; that is the
clause working, not a nuisance.

## 1.6 THE ONE TOOL CHANGE — A SCOPE CHANGE, PRE-REGISTERED AT §1.5

`census_doc()` parses only between `CENSUS-PARTITION-BEGIN/END`; `dispo_doc()`
reads the `WORKING-RESIDUE` headline from inside the member anchors instead of
from the whole file; PART II's member anchors are renamed
`IMMATERIAL-MEMBERS-F17-*`.  **No clause, class boundary or bar meaning was
touched.**

It was **necessary**, and the pre-registration proved it before the edit:
unanchored, `_CENSUS_ROW` took the **LAST** match in the file while
`_CENSUS_IMM` / `_CENSUS_RECONV` took the **FIRST**, so **no placement of a
history section satisfies both** — the census could not carry its own history
without lying to its own falsifier.  Anchoring is the rule `dispo_doc()`
already had, for the reason it had it.

**H-6 — THE FALSIFIER DEMONSTRATED TO FAIL AFTER THE RE-SCOPE.  MET.**  Run on
a shadow tree (`sw/*.py` and `docs/notes/*` real copies; everything else,
`sw/testdata/` included, a **read-only symlink**):

| # | perturbation | caught by, verbatim | result |
|---|---|---|---|
| **P0** | control, unperturbed | `IMMATERIAL FALSIFIERS: PASS` | exit 0 |
| **P6** | live `TRANSIENT` cell 5 → 4 **inside** the anchors | **G6** `TRANSIENT: doc 4 != derived 5` | exit **1** |
| **P7** | the partition anchors deleted | **G6** `partition anchors (…) absent` | exit **1** |
| **P8** | `fz2e/516001` removed from the anchored member table | **G7** `derived but NOT named: fz2e/516001` | exit **1** |
| **P9** | control — **PART II's** superseded cell set to a nonsense 99 | `IMMATERIAL FALSIFIERS: PASS` | exit **0** |

**P9 is the load-bearing one.**  Before the re-scope it would have FAILED,
because `_CENSUS_ROW`'s last-match rule would have read PART II's table as the
live registration.  It passes, which is the measurement that **history outside
the anchors has stopped being a claim** — and P7 is the measurement that the
anchors cannot simply be dropped to get the same effect.

**Nothing under `sw/testdata/` was touched by any of P0–P9.**

## 1.7 ⚠ **REPORTED AS A MISS — TWO DENOMINATORS WERE WRONG IN A DOCUMENT DRAFT**

The disposition document's §I.4 bar table was first written with **G2 `0 / 45`**
and **G3 `0 / 86`**, derived by hand from the class counts.  Measured, they are
**`0 / 33`** and **`0 / 80`**: G2's pool is the **two-sided** dumps that differ
(the other 12 FUNCTIONAL seeds are one-sided and belong to G1's pool), and G3's
pool is not the working residue.  **Corrected in the document, with the reason
written beside G2 so the next reader does not re-derive it wrongly.**  No bar
verdict moved — every one of the eight was and is PASS — but a denominator
quoted from arithmetic instead of from the tool is exactly the class of error
this campaign asks to be reported, so it is.

## 1.8 H-7 — `TIMING_RECONVERGED` AND THE USER RULING.  **MET.**

**The ruling of 2026-08-11 — *"Timing reconvergence seeds are material"* —
CARRIES FORWARD UNCHANGED, and it carries without being re-asked.**  It is a
rule about a PREDICATE (a TIMING seed with `done_delta == 0`), not about a seed
list, so a change of membership does not reopen it.

Re-derived on F18: **8 seeds**, the F17 seven **all still members and unmoved**,
plus `fz2e/530020`.  All 8 stay **MATERIAL**, inside the 30 TIMING and inside
the 86 working residue.  Clause (4) S-STARTS fails on every one of them, so
none takes `IMMATERIAL` under the strict reading.  Named in full in the census
PART I §I.4 and printed on demand by `fz2_immaterial.py reconverged`.

## 1.9 H-8 — NOTHING MOVED.  **MET.**

| gate | result |
|---|---|
| `fz2_w1 lint` | **PASS — 0 hits, 48 stratum rows** |
| `fz2_w1 bars` | **11 / 11 MET**, C-1 … C-11.  The regenerated `fz2_bars.json` differs from HEAD's in **exactly one byte-range, its `ts` field** — verified by diff, then **reverted**, so the artifact is byte-identical to HEAD |
| `test_artifact` | **45 / 45, NON-VACUOUS** |
| `sw/testdata/` | **ZERO tracked diffs.**  ⚠ two entries are UNTRACKED and are declared in §3.3 |

## 1.10 ONE FURTHER TRUTHFULNESS FIX, NOT REGISTERED, REPORTED HERE

`fz2_materiality.py` printed a hard-coded banner **`fz2 MATERIALITY CENSUS --
FLASH #17 FAILURE LEDGER`** and kept printing it after `fz2_ledger.CURRENT`
moved to the F18 ledger — so the tool was emitting an **F18 partition under an
F17 title**.  That is the mislabelled-receipt defect class inside an
instrument's own output.  The banner now names no era and defers to the ledger
line the tool already prints above it.  **No number changed**; the census's
figures are identical before and after.

---

# ITEM 2 — `sw/quartus_gate.py --retention`

## 2.1 THE CONTRACT, AS BUILT

**`--retention` runs the recorded four-stage recipe**, one stage per
subprocess, into the one log the gate already hashes into `reports`, stopping
at the first non-zero rc (a later stage must not run on an earlier one's
failure — it would read the previous build's database and emit reports that
look like this run's).  `python3 sw/quartus_gate.py --dry-run --retention`:

    quartus_gate --dry-run: RETENTION, 4 stage(s), cwd .../hdl
      .../quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore
      .../quartus_fit nec_test -c nec_test_ucore
      .../quartus_asm nec_test -c nec_test_ucore
      .../quartus_sta nec_test -c nec_test_ucore

* **E1 still runs BEFORE** and the `.qsf` is still regenerated AFTER, exactly
  as on the control path.
* **`configuration` is still DERIVED and the flag is NOT an input to it.**
  What the flag asked for is recorded separately, in
  `build.configuration_requested`.  Keeping them independent keeps alive the
  very disagreement that caught FLASH #18.
* **The CONTROL path is unchanged, byte for byte** — `Q2` is the check.
* `--retention --parse-only` is **refused**: it would gate whatever reports are
  on disk while claiming a configuration it never compiled.

### 2.1a ⚠ **THE MACRO IS PASSED UNQUOTED, AND THAT IS NOT A DEVIATION**

Every pre-registration writes `--verilog_macro="X1_AD_RETENTION=1"` because it
is writing a **shell** command line, where the shell strips the quotes.  This
runs through `subprocess` with **no shell**, so quotes would reach the compiler
as literal characters.  **Checked against the artifact rather than recall**:
all **twelve** archived retention receipts in
`sw/testdata/receipts/quartus_bitstream.jsonl` — including FLASH #18's
`277d5ccf0f8b9398…`, the bitstream on the board — record
`configuration_detail.command_line` as

    quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore

i.e. **unquoted is what Quartus actually received, every time.**  Had the
prereg's shell form been transcribed literally, the flag would have passed a
macro named `"X1_AD_RETENTION` — the trap one level down.

## 2.2 THE ENV-VAR REFUSAL — DEMONSTRATED

    $ X1_AD_RETENTION=1 python3 sw/quartus_gate.py
    quartus_gate: REFUSING TO RUN.
      X1_AD_RETENTION='1' is set in the environment, and THIS GATE HAS NEVER READ IT.
      The macro reaches the compiler ONLY via --retention, which puts it on quartus_map's
      command line.  Without that flag the variable reaches nothing and the build would be
      a CONTROL build silently labelled by whatever you called it.  That happened at
      FLASH #18 (receipt aa3ca3e028dff7d2…, label RETENTION / derived CONTROL/DEFAULT) and
      it was caught by the derived label one step before the flash -- see
      docs/notes/fz2_flash18_results_2026-08-11.md §1.2.
      Do one of:
        python3 sw/quartus_gate.py --retention     # the RETENTION build, ...
        unset X1_AD_RETENTION; python3 sw/quartus_gate.py    # the CONTROL build
      (this is exit 2 -- the gate could not run.  Not a PASS and not a RED.)
    rc=2

**Accepted-and-ignored has become refused-with-reason.**  The refusal fires on
any non-empty value (`1`, `0`, `yes` all tested) and **fires under
`--parse-only` too**, which touches no compiler and would otherwise have looked
like a safe way to ignore the variable.  An **empty** value is not "set" and
does not block a control build.  With `--retention` given, the variable is
allowed — the macro travels on the command line — and is **recorded** in the
receipt's `env`.

## 2.3 Q-A — `sw/test_quartus_gate.py`.  **75 / 75, PASS.**  Q1–Q8.

| # | what it forbids | result |
|---|---|---|
| Q1 | a flag that builds a control and calls it retention | PASS — four stages in order, macro on `quartus_map` only, **unquoted** |
| Q2 | a fix that changes the CONTROL build | PASS — command list equal to the historical one |
| Q3 | the accepted-and-ignored trap re-opening | PASS — exit 2, refusal words, names variable / flag / finding, never reaches E1 |
| Q4 | a refusal that blocks the correct invocation | PASS |
| Q5 | a refusal that fires on every run | PASS |
| Q6 | a flag that silently does nothing | PASS |
| Q7 | a flag that asserts its own configuration | PASS — control set → CONTROL, retention set → RETENTION, missing source → UNDETERMINED, and `parse_configuration` takes **only** the tree |
| Q8 | a test that writes to the append-only receipt history | PASS — asked on **every** subprocess |

**Q-D: no Quartus compile was run as part of this work** — registered at §2.3
and honoured, with the §3.4 exception reported.  **Q-B `test_artifact` 45/45.
Q-C `--help` names both flags.  Q-E** the control command list and the receipt
schema keys are unchanged.

## 2.4 NON-VACUITY — THE FALSIFIER FAILS ON SIX NULLS

Run on a shadow tree with **no `hdl/` at all**:

| null | the defect it re-creates | result |
|---|---|---|
| **N0** | control, unperturbed | **PASS**, 75 / 75 |
| **N1** | **`--retention` accepted and ignored — the FLASH #18 defect itself** | **FAIL**, 67 / 72 |
| N2 | the env-var refusal deleted | **FAIL**, 55 / 75 |
| N3 | the refusal fires on every run | **FAIL**, 63 / 75 |
| N4 | the macro quoted, as the shell-form documents write it | **FAIL**, 72 / 75 |
| N5 | `--retention --parse-only` allowed | **FAIL**, 72 / 75 |
| N6 | the CONTROL command list altered | **FAIL**, 74 / 75 |

**N1 is the one that matters**: the exact defect FLASH #18 caught, re-created,
and the falsifier catches it.

---

## 3. HARD STOPS, AND THE ONE THING THAT WENT WRONG

### 3.1 The registered hard stops, all HELD

No write under `sw/testdata/` beyond the reverted `fz2_bars.json`; no edit to
`evidence()`'s six clauses, to `CYCLE_DEFINING`/`VALUE_ONLY` or to any class
boundary; **no seed list in either tool**; `bars` 11/11 with no verdict moved;
no seat admitted against a failing clause.

### 3.2 §4's four MISS conditions, none of which occurred

The partition contradicted neither §1.4 branch; no seat failed a clause;
`falsify` was demonstrated to fail (P6–P8) as well as to pass; the env-var
refusal fired and did not fire on the correct invocation.

### 3.3 ⚠ TWO UNTRACKED SYMLINKS UNDER `sw/testdata/`, DECLARED

`sw/testdata/campaigns/{fz2c,fz2e}/captures` are **gitignored directories that
exist only in the primary worktree**, so this isolated worktree had none and
the census could not read a single capture.  They are **symlinks to the primary
worktree's, used read-only**; `.gitignore`'s pattern ends in `/` and so does
not match a symlink, which is why they appear as untracked rather than ignored.
**They are not repository content, nothing was copied and nothing was written
through them**, and every capture they expose was sha256-verified against the
ledger before it was read — 110 of 110.  **They should be removed before this
branch is used anywhere else.**

### 3.4 ⚠ **A QUARTUS COMPILE WAS STARTED BY ACCIDENT AND ABORTED.  REPORTED AS A MISS.**

While proving `sw/test_quartus_gate.py` non-vacuous, a null run deleted the
env-var refusal — and the test's `run_gate([], {X1_AD_RETENTION: "1"})`, which
in the fixed tool stops at that refusal, therefore fell through into `build()`.
It ran `shutil.rmtree` on `hdl/db`, `hdl/incremental_db`, `hdl/output_files_ucore`
and started `quartus_sh --flow compile`.  **Killed at ~60 s, during
`quartus_map`.**

**Damage, assessed and stated rather than assumed:**

* it ran against **this isolated worktree's** `hdl/`, not the primary one;
* the three directories it deleted **did not exist** in this freshly
  provisioned worktree — they are gitignored build outputs;
* **`hdl/nec_test_ucore.qsf` was NOT modified** (Quartus rewrites it later in
  the flow than the kill point) — `git status` on `hdl/` is empty;
* the aborted `hdl/db`, `hdl/incremental_db` and `hdl/quartus_gate_build.log`
  were removed;
* **no receipt was written by it** — `_finish()` was never reached.

**A SECOND, QUIETER INSTANCE, FOUND BY LOOKING**: a later null run went RED at
E1 (its shadow tree has no `hdl/`) and `_finish()` **appended ten junk entries
to the real `sw/testdata/receipts/quartus_bitstream.jsonl`** — the append-only
history every G6 figure on this branch is quoted from.  They were found by
`git status`, identified by the `qgnull` path inside them, and the file was
**restored to HEAD**.  **The shipped test never wrote any of them**; all ten
came from the perturbation harness.

**BOTH ARE FIXED IN THE TOOL, NOT IN THE PROCEDURE.**  `test_quartus_gate.py`
now disarms **two** things in every subprocess it starts — `QUARTUS_BIN` is
pointed at a non-existent path (and `build()` checks every stage binary
**before** it deletes anything, so the worst case is exit 2 with nothing
touched), and `artifact.RECEIPT_DIR` is redirected to a temp dir the test owns.
**Q8 then asserts, on every single subprocess, that the receipt history did not
grow by one byte.**  The six nulls were re-run under the hardening and all six
still FAIL, so the hardening did not weaken them.

**The lesson, stated plainly: a test whose safety depends on the very code it
is trying to falsify is not safe.**  Both incidents are that one sentence.

---

## 4. WHAT THIS LEAVES OPEN

1. **`fz2e/530020`'s reconvergence is unattributed** — census PART I §I.4, with
   its falsifier (a double capture on one bitstream).
2. **phantom-T1's one remaining `bs` cell** — the `system_large` status-pin
   observation model, booked by the ack-wake landing and not taken, to be
   measured as its own mechanism with its own G6.
3. **The 11 UNSCOREABLE seeds** — unmoved, all `raw`, all escaped; the fix is
   still *a terminator that survives an escaped program*.
4. **`--retention` has not built a bitstream.**  Its plumbing is proved and the
   recipe is proved (twelve archived receipts), but **the two have not been
   proved together**.  *Falsifier, registered here*: the next retention build
   taken with `--retention` must produce a receipt that self-labels
   `RETENTION (X1_AD_RETENTION=1)` with an `.rbf` differing from the control's
   — the same two checks (E-6, E-9) FLASH #18 used.  **Until that runs, the
   flag is tested, not exercised.**
