# RESULTS — THE F20 ERA RE-PIN OF THE MATERIALITY CENSUS AND THE `IMMATERIAL` DISPOSITION

    branch      master @ 298d522872  (isolated worktree
                `worktree-agent-a1a16db2b619a4a58`, same commit)
    prereg      docs/notes/fz2_f20_housekeeping_prereg_2026-08-12.md  @ 18dc133914
    date        2026-08-12
    board       NOT TOUCHED.  No capture, no flash, no socket command, no
                Quartus compile, no RTL or testbench edit.  Offline throughout.

    inputs      sw/testdata/fz2/fz2_failure_ledger_f20_2026-08-12.json  (committed)
                sw/testdata/fz2/fz2_failure_ledger_f19_2026-08-12.json  (committed)
                the 107 banked FABRIC captures the F20 ledger names,
                reached through a READ-ONLY symlink to the main checkout and
                sha256-verified 107 / 107 before anything was classified
                (the captures are gitignored and live only in the main tree;
                the symlinks were removed before every commit)

---

## §0 THE FIVE HEADLINES

1. **THE PARTITION HIT ITS POINT PREDICTION ON ALL EIGHT G6 CELLS**, and the
   two independent derivations the pre-registration built agree cell for cell:
   **FUNCTIONAL 44 · TIMING 30 · TRANSIENT 5 · COSMETIC 17 · UNSCOREABLE 10 =
   106**, `IMMATERIAL` **22**, working residue **84**, `TIMING_RECONVERGED`
   **7**.  Registered branch **A** was the right call; branch **B** is refuted.
   §1.
2. **`fz2_immaterial falsify` IS PASS, G1–G8, exit 0** — the debt FLASH #20's
   `C-15e` booked and `timing50_phase2_results` §6.3 recorded as **OWED, not
   claimed**, is discharged.  It is demonstrated to FAIL on four perturbations
   and to IGNORE a fifth applied to the superseded history.  §2, §3.
3. **THE `IMMATERIAL` CLASS LOST TWO MEMBERS AND NEITHER FAILED A CLAUSE.**
   `fz2e/521024` and `fz2e/522002` read `SUCCESS / clean` at FLASH #20 and left
   the LEDGER; **zero entrants; 17 of the surviving 22 rows are byte-identical
   to FLASH #19's, and the five that moved moved only their row count and value
   columns.**  §1.3.
4. **THE `fz2c/404049` / SEVEN-ABSENT QUESTION IS ANSWERED BY MECHANISM AND IS
   NOT A FINDING.**  The campaign directory is re-made per flash era; a capture
   survives iff the seed is non-SUCCESS or a keep-rows seed.  **`0 OK / 107
   MISMATCH / 7 missing` reconciles exactly**, and the one survivor among the
   departed is `fz2e/509050` = 50 × 10181.  §4.
5. **THREE REGISTERED SECONDARY CELLS MISSED AND ONE FINDING CAME OUT OF THEM.**
   The `arch: NODUMP` vs census-row-scan disagreement that FLASH #19 booked in
   one direction **runs in BOTH**: `fz2c/406063` and `fz2e/518039` are
   UNSCOREABLE in the census in both eras while their ledger `done_core` flag
   moved across the era.  §1.5.

---

## §1 THE RE-DERIVATION — EVERY G6 CELL MET

Pre-registered at `18dc133914`, **before either tool was run against the F20
ledger in this sitting**.

### 1.1 THE PARTITION — K-2

| cell | F19 | **PREDICTED** | **MEASURED** | verdict |
|---|---:|---:|---:|---|
| FUNCTIONAL | 49 | **44** | **44** | MET |
| TIMING | 30 | **30** | **30** | MET |
| TRANSIENT | 5 | **5** | **5** | MET |
| COSMETIC | 19 | **17** | **17** | MET |
| UNSCOREABLE | 11 | **10** | **10** | MET |
| total | 114 | **106** | **106** | MET |
| IMMATERIAL | 24 | **22** | **22** | MET |
| `TIMING_RECONVERGED` | 7 | **7** | **7** | MET |

**Eight of eight.**  `C-ROW` **106/106** and `C-ARCH` **106/106**, exit 0 —
**K-1 MET**.  Registered branch **A** (FUNCTIONAL 44 / TIMING 30) is confirmed
and branch **B** (FUNCTIONAL 49 / TIMING 25) refuted; the partition did **not**
split across two cells, so FLASH #20's own `G6 5 / 8` stands.

**The five disagreeing cells `falsify` named against the stale document, before
the re-pin, were exactly the five predicted**: FUNCTIONAL, COSMETIC,
UNSCOREABLE, IMMATERIAL and total — with TIMING, TRANSIENT and
`TIMING_RECONVERGED` agreeing.

### 1.2 THE SECOND, INDEPENDENT DERIVATION — K-2b MET

The class × family table is **row for row** the pre-registration's §1.4(b), and
twelve of its fifteen rows are byte-identical to FLASH #19's.  The three that
moved are the three the F20 ledger's own `family_counts` forced: **D1 10 → 9**,
**NEW/UNCLASSIFIED 11 → 4**, and **D3 5 → 5 with FUNC 4 → 3, TIME 1 → 2**.

**This is the part of the sitting worth keeping.**  One derivation reads a
falsifier's own cell count (`G6 5 / 8` pins six cells and fixes
FUNCTIONAL + TIMING at 74); the other reads the ledger's family counts and the
eight leavers' rows.  They share no input beyond the ledger and they reach the
same 44/30.

### 1.3 THE `IMMATERIAL` MEMBERSHIP — K-3 MET, WITH ONE SUB-PREDICTION MISSED

**22 members = FLASH #19's 24 minus `fz2e/521024` and `fz2e/522002`, ZERO
entrants**, measured by parsing both anchored tables and diffing them cell by
cell:

    F20 members 22   F19 members 24
    left: fz2e/521024, fz2e/522002      entered: (none)
    rows byte-identical: 17
    rows that changed:    5   -- and every one of them in ONE column

| member | the only cell that moved |
|---|---|
| `fz2c/408021` | `26 rows: addr=3, bs=12, data=6, nxta=3, ps=2, qs=2, ube=20` → `22 rows: addr=2, bs=12, data=4, nxta=2, ps=2, qs=2, ube=20` |
| `fz2c/409065` | `16 rows: addr=2, data=12, nxta=2` → `12 rows: addr=1, data=10, nxta=1` |
| `fz2e/521049` | `14 rows: addr=2, data=10, nxta=2` → `10 rows: addr=1, data=8, nxta=1` |
| `fz2e/525017` | `12 rows: addr=2, data=8, nxta=2` → `8 rows: addr=1, data=6, nxta=1` |
| `fz2e/528010` | `4 rows: addr=1, data=2, nxta=1` → `7 rows: addr=1, data=2, nxta=1, ube=6` |

**`sub`, `tier`, `escaped`, `family`, `cyc` and `done` are unchanged on all 22
members**, including the five above.  The row counts were predicted exactly, the
sub-classes were predicted exactly, and the membership was predicted exactly.

⚠ **MISSED AS REGISTERED: three of the five column lists.**  The
pre-registration predicted `409065` `addr=2, data=8, nxta=2`, `521049`
`addr=2, data=6, nxta=2` and `525017` `addr=2, data=4, nxta=2` by carrying the
family's own shape forward.  All three are wrong the same way — **`addr` and
`nxta` each fell 2 → 1 and `data` absorbed the remainder** — and `408021`'s was
registered as NOT derived.  `528010`'s was carried from FLASH #20's own C-15b
measurement and is exact.  **No clause reads a column tally**, and the one split
that reads a column NAME (`CYCLE_DEFINING`) is untouched: none of the three
carries `bs` or `t`.

**NO MEMBER WAS EVICTED AND NONE COULD BE.**  `fz2e/521024` and `fz2e/522002`
read `SUCCESS / clean` in the FLASH #20 `results.jsonl`, so they are not ledger
entries and `evidence()` is never asked about them.  Hard stop 4 (*admitting or
evicting a member in order to reach a count*) was never approached.

### 1.4 `fz2e/527051` — K-4 MET

    fz2e/527051, the known flicker seed: TIMING
        -- cycle_starts chip-only 174 / core-only 176; done_clock -17

Its two 15-word dumps became **identical** at FLASH #20 (`arch`
`AW,BP,BW,CW,IX,IY,PSW` → `OK`, `arch_match` False → True), so `measure()`'s
first branch no longer fires and it leaves FUNCTIONAL.  It is the **only** class
change among the 106 seeds present in both ledgers, out of **28** that moved a
scored field, and it was named in advance with the branch it would take.

### 1.5 THE SECONDARY CELLS — THREE MISSES, AND A FINDING UNDER TWO OF THEM

| cell | PREDICTED | MEASURED | verdict |
|---|---:|---:|---|
| C-ROW / C-ARCH | 106/106 · 106/106 | **106/106 · 106/106** | MET |
| G1 pool (no dump proof) | 20 = 10 + 10 | **19 = 9 + 10** | MISSED by 1 |
| G2 pool (two-sided dumps that differ) | 34 | **35** | MISSED by 1 |
| G3 pool (schedule) | 79 | **76** | MISSED by 3 |
| G4 FALSE on | 84 / 106 | **84 / 106** | MET |
| G4 by first failing clause | arch 34 · cycle_starts 30 · no_dump_proof 20 | **arch 35 · cycle_starts 30 · no_dump_proof 19** | MISSED, same root |

**G1 and G2 are equal and opposite, and their root is a FINDING.**  The
pre-registration's §1.2 asserted that six seeds whose `arch` / `done_*` fields
moved *"stay FUNCTIONAL on both sides of the move"*.  Two of them are not
FUNCTIONAL at all: **`fz2c/406063` and `fz2e/518039` are UNSCOREABLE in the
census — the row scan finds NO `MAGIC`-anchored dump on EITHER leg — in BOTH
eras, while their ledger `done_core` flag MOVED across the era** (False → True
and True → False respectively).  FLASH #19's census §I.2 booked this
disagreement in ONE direction (six seeds whose ledger says `NODUMP` while the
census finds both dumps); **it runs in both, and this is the first measurement
of the other direction.**  The CLASS was right on both seeds in both eras — the
partition is unaffected and no G6 cell moves — but the pool sizes were not.
Booked in census PART I §I.6 item 2 with the seeds named; **not fixed here**,
because changing a derivation rule inside a re-pin is changing the instrument in
the sitting that found it.

**G3 was registered *"derived by exclusion"* and flagged in the prereg as the
one secondary cell that was.**  The non-IMMATERIAL seeds with an unchanged
schedule went 6 → 8: `fz2e/534003` left the ledger, and **three arrived —
`fz2e/518053`, `fz2e/518067`, `fz2e/526054`**, whose row counts collapsed at
FLASH #20 (3,413 → 8, 3,278 → 45, 320 → 48).  A seed that stops diverging on a
schedule stops being in the schedule pool.  Census PART I §I.6 item 3.

### 1.6 THE ERRATUM THE PRE-REGISTRATION RAISED, RE-STATED ON THE MEASUREMENT

`fz2_f19_housekeeping_results_2026-08-12.md` §2.4 calls its three offline
closures — `fz2e/521024`, `fz2e/522002`, `fz2e/534003` — *"all three … 4-row
COSMETIC IMMATERIAL members"*.  **`fz2e/534003` is not a member and never was.**
Its F19 ledger row reads `done_chip` **False** and `done_core` **False**, so
neither leg dumped and clause (2) D-PROOF holds it out; it is one of the eleven
UNSCOREABLE, and the measurement confirms it — **the UNSCOREABLE counterfactual
split moved by exactly one cell, COSMETIC 6 → 5, which is `fz2e/534003`'s own
4-row would-be-COSMETIC shape**, with TIMING 4 and TRANSIENT 1 unmoved.  That is
also the check that no other seed silently entered or left UNSCOREABLE.

`fz2e/530020` was likewise never a member: it is **TIMING**, and it is the seed
whose F18 admission to `TIMING_RECONVERGED` its own falsifier evicted at F19.

**Nothing is edited in that document** — it is superseded history — and the
erratum was registered in the pre-registration before either tool was run.

### 1.7 `TIMING_RECONVERGED` — MEMBERSHIP CHECKED, NOT ONLY THE COUNT

**7 seeds, and the membership is FLASH #19's seed for seed**: `fz2c/406073`,
`fz2c/407064`, `fz2e/511014`, `fz2e/512062`, `fz2e/518006`, `fz2e/518044`,
`fz2e/520000`.

The pre-registration registered this as a distinct claim from the count, because
two seeds could swap at a constant 7 — and the two candidates for that were
named in advance: `fz2e/520000` moved its `first_bad_row` 502 → 2113, and
`fz2e/527051` newly joined TIMING.  **Neither moved the membership.**

**RULED 2026-08-11 and carried verbatim: *"Timing reconvergence seeds are
material."***  The ruling is a rule about a PREDICATE, so it carries without
being re-asked; all 7 stay MATERIAL and inside the 84.  ⚠ **It is still NOT a
ratchet** — it moved by one seed with no mechanism in each of the two preceding
eras, and one stable era is evidence, not a warrant.

---

## §2 `falsify` ON THE F20 LEDGER — K-5 MET

    G1 DUMP PROOF     : 0 / 19   [PASS]
    G2 DUMP IDENTITY  : 0 / 35   [PASS]
    G3 SCHEDULE       : 0 / 76   [PASS]
    G4 NOT UNIVERSAL  : FALSE on 84 / 106   [PASS]
    G5 CONTROLS       : C-ROW 106/106 · C-ARCH 106/106   [PASS]
    G6 THE CENSUS     : 0 / 8 cells disagree   [PASS]
    G7 THE DOCUMENT   : 0 / 23 disagreements   [PASS]
    G8 NO FORK        : 0 / 106   [PASS]
    IMMATERIAL FALSIFIERS: PASS      exit 0

**Before the two documents were touched, the same invocation on the same ledger
read `G6 5 / 8` and `G7 3 / 25`, naming `fz2e/521024`, `fz2e/522002` and the
`WORKING-RESIDUE` headline** — reproducing FLASH #20's `C-15e` exactly, from a
different checkout.  That run is the control that the re-pin moved the
documents and nothing else: **G1–G5 and G8 were already PASS with identical
denominators**.

---

## §3 K-6 — THE FALSIFIER IS DEMONSTRATED TO FAIL, AND THE HISTORY IS PROVED INERT

Five perturbations on a shadow tree outside the repo (`docs/notes/` copied, `sw`
symlinked read-only), each applied to a pristine copy, scored, and reverted.
**The repo was never perturbed**, and the shadow was deleted afterwards.

| # | perturbation | caught by | exit |
|---|---|---|---|
| **P0** | control — the unperturbed shadow | `IMMATERIAL FALSIFIERS: PASS` | **0** |
| **P1** | a member row DELETED from the LIVE anchored table (`fz2e/532032`) | **G7** 1 / 23 — *"derived but NOT named"* | **1** |
| **P2** | the LIVE `WORKING-RESIDUE` headline reverted to F19's (`84 = 106 − 22` → `90 = 114 − 24`) | **G7** 1 / 23, printing both triples | **1** |
| **P3** | one LIVE census class cell moved (FUNCTIONAL 44 → 49) | **G6** 1 / 8 | **1** |
| **P4** | the LIVE census anchors REMOVED | **G6** — *"partition anchors … absent"*, **naming them**, with **no fallback to the F19 block sitting below** | **1** |
| **P5** | **THE APPEND-ONLY CONTROL** — the SUPERSEDED F19 blocks perturbed instead (F19 FUNCTIONAL 49 → 99, F19 headline → `1 = 2 − 3`) | nothing: **G6 0/8 PASS, G7 0/23 PASS** | **0** |

**P4 and P5 are the pair that matters for an append-only ledger**, and they now
carry one more superseded block than they did at F19: P4 proves the parser never
falls back when the live anchors go missing even with **two** superseded
partitions below it, and P5 proves those blocks are genuinely inert — history
that can be read and cannot lie.

---

## §4 THE CAPTURE-FILE RECONCILIATION — K-9 MET, BY NAME

`timing50_phase2_results_2026-08-12.md` §6.3 reported, over the **F19** ledger's
114 failures: **`capture sha OK: 0   MISMATCH: 107   missing: 7`**, and recorded
`fz2_immaterial falsify` as **OWED**.

### 4.1 BYTE MOVEMENT ≠ SCORED-FIELD MOVEMENT — BOTH QUANTIFIED

| population | measured |
|---|---:|
| capture files pinned by the F19 ledger (114 failures + 3 discards) | **117** |
| still present on disk | **108** |
| of those present, **byte-identical** to their F19 `sha256` | **0** |
| of those present, **MOVED** | **108 / 108 = 100 %** |
| **ABSENT** from disk | **9** (7 failures + 2 discards) |
| F19-pinned capture **paths** that changed in the F20 ledger | **0** |
| **F20**-pinned captures (106 failures + 1 discard) verified against disk | **107 / 107 sha256 MATCH, 0 mismatch, 0 missing** |
| seeds in **both** ledgers | **106** |
| of those, with any change in `first_bad_row` / `diverging_rows` / `compare_window` / `arch` / `arch_match` / `done_chip` / `done_core` / `mech` / `family` / `tier` / `banked_verdict` / `banked_sub` / `image_sha256` | **28** |
| `image_sha256` movers (generator drift) | **0** |

**100 % byte movement against 26.4 % scored-field movement.**  FLASH #20
re-captured all 3,840 seeds, so new bytes on every retained file are EXPECTED;
the registered noise class is about **scored fields**, and the byte question and
the scored question have different answers for 78 of the 106 shared seeds.  This
is the FLASH #19 precedent restated one era on, and the F20 side of it is
**cleaner than F19's**: the live ledger and the disk agree on all 107.

### 4.2 THE SEVEN ABSENT FILES — THE MECHANISM

**The campaign directory is re-made for each flash era, so `captures/` holds
exactly the CURRENT era's banked captures and nothing else.**  Measured:

* `sw/testdata/campaigns/{fz2c,fz2e}/results.jsonl` carry **960 + 2,880 = 3,840
  rows and ONE era each — `sof 26d6e79166183a21…`, FLASH #20's** (the F20
  prereg's own `C-3`, `distinct_eras 1`);
* **every one of the 645 capture files on disk was written between 2026-08-12
  04:55:16 and 05:06:01 PDT** — the FLASH #20 capture window.  **Not one file
  predates it**; a surviving F19-era file would have an older mtime and none
  does.

`fuzz_campaign.cmd_run` writes a capture iff `verdict != SUCCESS`, **or** the
seed is in the frozen keep-rows bank (`k % N == 0`), **or** it is drawn as
SUCCESS ballast.  On this corpus: **107 non-SUCCESS seeds, 107 with a capture,
0 missing**, plus **538 SUCCESS captures** whose `k` are `fz2c` every **2** and
`fz2e` every **50** — the keep-rows bank, not a quota.

All ten F19-pinned seeds absent from the F20 ledger read **`SUCCESS`** at FLASH
#20, and a capture survives **iff** the seed is a keep-rows seed:

| F19-pinned, F20-absent | F20 verdict | `k mod 50` | capture on disk |
|---|---|---:|---|
| `fz2e/508068` | SUCCESS / clean | 18 | **absent** |
| `fz2e/514001` | SUCCESS / clean | odd | **absent** |
| `fz2e/521024` | SUCCESS / clean | 24 | **absent** |
| `fz2e/522002` | SUCCESS / clean | 2 | **absent** |
| `fz2e/526075` | SUCCESS / window_truncated | odd | **absent** |
| `fz2e/530020` | SUCCESS / clean | 20 | **absent** |
| `fz2e/534003` | SUCCESS / window_truncated | odd | **absent** |
| **`fz2e/509050`** | SUCCESS / clean | **0** — `509050 = 50 × 10181` | **PRESENT, new bytes** |
| `fz2e/524027` *(F19 discard)* | SUCCESS / clean | odd | **absent** |
| `fz2e/535070` *(F19 discard)* | SUCCESS / clean | 20 | **absent** |

**THE `0 / 107 / 7` RECONCILES EXACTLY AND IS NOT A FINDING.**  That sweep
covered the 114 **failures** only: 106 are still failures (present, all bytes
new), `fz2e/509050` is present because it is a **keep-rows** seed, and the
remaining **7** have no F20 capture because they passed and are not in the
bank — `106 + 1 = 107 MISMATCH`, `7 missing`, `0 OK`.  The two absent
**discards** are outside that sweep's population and are absent for the same
reason.  `fz2c/404049`, the seed the gate names, is simply the first entry in
the F19 ledger.

⚠ **THE SIDE-EFFECT WORTH NAMING: A SEED THAT PASSES LOSES ITS EVIDENCE.**  The
F19-era rows for those seven no longer exist in the tree, so **no era-to-era
row-level comparison can be made for a seed that closes**, and the F19 census's
classification of them can never be re-derived from artifacts.  This sitting had
to take those eight leavers' F19 classes from the F19 census and disposition
DOCUMENTS rather than from their rows, which is exactly why those documents are
append-only.  **Booked, not repaired.**  FLASH #19 already booked *bank a
per-seed capture digest*; this sitting adds: **retain the capture of any seed
named in a committed ledger, even when it passes.**

---

## §5 THE GATES

| gate | measured | verdict |
|---|---|---|
| `fz2_materiality` controls | **C-ROW 106/106 · C-ARCH 106/106**, exit 0 | **K-1 PASS** |
| `fz2_immaterial falsify` | **G1–G8 PASS**, exit 0 | **K-5 PASS** |
| perturbation demonstration | P1–P4 caught by a NAMED bar, P5 inert | **K-6 PASS** |
| `sw/fz2_ledger.py:CURRENT` | names `fz2_failure_ledger_f20_2026-08-12.json`; every consumer prints the file it read, visible in every transcript above | **K-7 PASS** |
| `fz2_w1 lint` | **PASS, 0 hits, 48 stratum rows** | PASS |
| `fz2_w1 bars` | **11 / 11 MET**, C-6 MET (`hold_rows_exact` 4,638 / `hold_rows_off` **0**) | **CARRIED AS REGISTERED** — FLASH #20 reported these verdicts; not re-litigated here |
| `test_artifact` | **45 / 45**, non-vacuous | PASS |
| `sw/testdata/` cleanliness | **ZERO diffs.**  `bars` rewrote `fz2_bars.json` with a new `ts` and **every other byte identical**; the timestamp churn was reverted | **K-8 PASS** |
| the capture symlinks | created read-only for the run, **removed before every commit**; `git status` clean under `sw/testdata/campaigns/` | PASS |

**Nothing under `hdl/` was read, written or built** (prereg §0.1 / hard stop 5 —
a parallel sitting owns `v30u_eu.sv` and its testbench).  No RTL, no Quartus, no
board.

---

## §6 WHAT THIS SITTING CHANGED

1. `sw/fz2_ledger.py:CURRENT` → the F20 ledger.  **One line.**
2. `docs/notes/fz2_materiality_census_2026-08-11.md` — a new **PART I (FLASH
   #20)**; the previous live block demoted to **PART I-F19** with a dated
   SUPERSEDED banner and its anchors renamed `CENSUS-PARTITION-F19-BEGIN/END`.
3. `docs/notes/fz2_immaterial_disposition_2026-08-11.md` — the same shape, with
   `IMMATERIAL-MEMBERS-F19-BEGIN/END`.

**PART I-F18 and PART II (FLASH #17) are byte-identical in both files.**  No
FLASH #17, #18 or #19 number was edited, deleted or restated; the two errata
this sitting raises are recorded HERE and in the live PART I, never in the
superseded text.  **No clause of `evidence()`, no class boundary, no
`CYCLE_DEFINING` / `VALUE_ONLY` entry and no seed list was touched.**

## §7 WHAT IS STILL OPEN

1. **The `arch: NODUMP` ↔ census-row-scan disagreement, now known to run in
   both directions** (§1.5).  Two derivations of "did this leg dump?" disagree
   and neither is wrong on its own terms.  Seeds named; the fix is an
   instrument decision, not a re-pin's.
2. **The 10 UNSCOREABLE seeds** — all `raw`, all escaped; the instrument fix is
   still *a terminator that survives an escaped program*.
3. **`TIMING_RECONVERGED` is booked as a cell, not a result** — one stable era
   after two unstable ones.
4. **Evidence retention** (§4.2) — a seed that closes loses the rows that
   justified its last classification.

---

## §8 RE-RUNNING THIS

```bash
git rev-parse HEAD                                  # 298d522872 + this sitting
# the captures are gitignored and live only in the main checkout
ln -s <main>/sw/testdata/campaigns/fz2c/captures sw/testdata/campaigns/fz2c/captures
ln -s <main>/sw/testdata/campaigns/fz2e/captures sw/testdata/campaigns/fz2e/captures

python3 sw/fz2_materiality.py                       # CURRENT is now the F20 ledger
python3 sw/fz2_immaterial.py census
python3 sw/fz2_immaterial.py reconverged
python3 sw/fz2_immaterial.py falsify                # exit 0, G1-G8 PASS

python3 sw/fz2_w1.py lint ; python3 sw/fz2_w1.py bars ; python3 sw/test_artifact.py
rm sw/testdata/campaigns/fz2{c,e}/captures          # before any commit
```
