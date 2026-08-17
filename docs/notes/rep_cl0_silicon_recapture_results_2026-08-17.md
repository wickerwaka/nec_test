# RESULTS — THE `rep_cl0` DERIVATION CELL, RE-CAPTURE

> ⚠ **THE RE-CAPTURE DID NOT COMPLETE.  THE CELL DOES NOT EXIST, AND NOTHING
> HERE CERTIFIES ANYTHING.**  `emit_suite.py emit` **stopped loudly** on the
> twelfth `F3A4` case with `CaptureLengthError` and wrote **0 of 24** cases.
> **RC-1 is MET on the artifact — there is no `reroll:` line — and it is met on
> a zero-case cell**, which is exactly the vacuity RC-2 was registered to catch.
> **RC-2 is MISSED, and MEASURED UNSATISFIABLE through this path on this rig.**
> **RC-4 IS NOT SCOREABLE, and INV-3's *WHY* is therefore neither confirmed nor
> retracted by this sitting.**

Scored against `emit_cap_repair_prereg_2026-08-17.md` §4 (`544d285333`), the
pre-registration `rep_cl0_silicon_prereg_2026-08-17.md` (`0dc40e51dc`), and
amendments **A-1** (`bb37f154f2`) and **A-2** (`5fd01af2c0`).  All were
committed **before** the leg they govern; **nothing was amended after board
contact**, and nothing is reinterpreted here.

| | |
|---|---|
| tree at capture | `master`, HEAD **`1ac78f2ef4`** (the `EMIT_CAP` repair landing) |
| leg | **SOCKET ONLY**, `use_core=False`, `--waits 0`, **NO FLASH** |
| command | `python3 sw/emit_suite.py emit --engine chip --opcodes F3A4,F3A5 --cases 12 --seed rep-cl0-rc1 --force-cx 255,256,257 --force-df 0,1 --waits 0 --out tests/v30/rep_cl0` |
| exit | **1** — `CaptureLengthError`, `sw/emit_suite.py:426` |
| artefact | `tests/v30/rep_cl0/emit_log.txt` only (sha256 `b8d0978ecda002ba…`), **UNCOMMITTED**.  No `.json.gz`, no `seeds.json` — `cmd_emit` writes a form's file only on form completion. |

---

## 0. THE SEED, FIXED BEFORE THE CAPTURE

**Seed base: `rep-cl0-rc1`.**  Fixed **before** board contact by an **offline,
board-free** re-derivation of `gen_case` (deterministic), under a selection rule
written down before it was run:

> candidates in order `rep-cl0-rc1`, `rep-cl0-rc2`, …; take the **first** whose
> twelve `F3A5` images contain **at least one doubly-odd** (`SI` odd **and**
> `DI` odd) image.

**Alignment coverage was the only criterion.**  No outcome, no engine result, no
capture length and no reroll behaviour entered the choice, and no other seed was
scored on anything.  The **first** candidate met it, so exactly one candidate
was ever evaluated.  Probe retained at
`tests/v30/rep_cl0/DIAGNOSTIC-UNREGISTERED/align_probe.py`.

## 0.1 THE `F3A5` ALIGNMENT TABLE — all 12 cases (RC-2's evidence)

Bus alignment is the parity of the **linear** address; `seg << 4` is even, so it
is the parity of `SI`/`DI`.

| idx | CX | DF | preload | `SI` | `DI` | alignment |
|---|---|---|---|---|---|---|
| 0 | 255 | 0 | 0 | `8a13` | `efeb` | **odd/odd** |
| 1 | 255 | 0 | 2 | `1de3` | `b902` | odd/even |
| 2 | 256 | 0 | 0 | `ed2f` | `5a61` | **odd/odd** |
| 3 | 256 | 0 | 2 | `94ba` | `e7d0` | even/even |
| 4 | 257 | 0 | 0 | `7f9f` | `9d64` | odd/even |
| 5 | 257 | 0 | 2 | `915b` | `3304` | odd/even |
| 6 | 255 | 1 | 0 | `f99c` | `def8` | even/even |
| 7 | 255 | 1 | 2 | `761a` | `2c5e` | even/even |
| 8 | 256 | 1 | 0 | `7528` | `1d1a` | even/even |
| 9 | 256 | 1 | 2 | `0d78` | `9c8b` | even/odd |
| 10 | 257 | 1 | 0 | `24f2` | `ef0c` | even/even |
| 11 | 257 | 1 | 2 | `1cfd` | `e688` | odd/even |

**Two doubly-odd images are PRESENT in the seed — idx 0 and idx 2 — and idx 2 is
`CX = 256`, i.e. inside `P-3`, the gating control INV-3 says the class was
excluded from.**  The seed did what RC-2 asked of it.  **Neither is
capturable** (§3).

---

## 1. THE CLAUSES, AS REGISTERED

### RC-1 — ZERO REROLLS · **MET**

`tests/v30/rep_cl0/emit_log.txt` carries **no `reroll:` line** (`grep -c reroll`
= **0**).  The four header lines are the truth-source, divider, directed-override
and wait-rig stamps; there is nothing else in the file.

**The refusal path fired in the field and worked**: the run stopped with
`CaptureLengthError` naming the case, the cap reached and the record count —
F-2 and F-4 behaving exactly as registered, **demonstrated non-vacuously on
hardware, not argued**.

⚠ **RC-1 is MET on a cell of ZERO cases.**  INV-3's falsifier is written as
*"the re-capture must complete the full 24-case cell with ZERO rerolls"*; the
second half holds and **the first half does not**.  It is reported as MET
against its own words and as **not satisfying INV-3's falsifier**, which is a
conjunction.

### RC-2 — ALL ALIGNMENT STRATA · **MISSED**

**No `F3A5` case was captured at all** (the run stopped during `F3A4`), so no
doubly-odd image is present in any artefact.  MISSED on the artifact.

⚠ **And it is worse than an incomplete run — it is MEASURED UNSATISFIABLE
through this path on this rig.**  §3 measures both doubly-odd images directly:
each is cut off mid-loop by the rig's capture buffer and can never reach its
done marker.  **The stratum RC-2 requires cannot be captured, and — correctly —
can no longer be silently rerolled.**  The repair made INV-3's exclusion
**loud**; it did not make the excluded class **capturable**.

### RC-3 — P-1 … P-7 re-scored as registered

| | verdict | why |
|---|---|---|
| **P-1** final state, `F3A4` CX=256 | **VOID** | no cell |
| **P-2** bus census 256 `MEMR` + 256 `MEMW` | **VOID** | no cell |
| **P-3** word control (**GATING**) | **VOID** | no cell; and its doubly-odd stratum is uncapturable (§3) |
| **P-4** bracketing controls 255 / 257 | **VOID** | no cell |
| **P-5** DF symmetry | **VOID** | no cell |
| **P-6** no collateral movement | **MET** | measured, §5 — the one prediction a failed run can still answer |
| **P-7** trace length as discriminator (A-2 §A-2.3) | **VOID** | no cell |
| **A-2 §A-2.3** three-way agreement P-1 = P-2 = P-7 | **NOT EVALUATED** | its inputs are VOID; the STOP condition did not arise |

**A-1 R-3 — waits are ZERO · MET.**  `--waits 0`; the log's wait-rig readback
is `WRAND=0 replay=0 (commanded clean at connect, OK/OK)`.  The capture is not
VOID on R-3's account.

**A-1 R-1 — the retry path is expected, not a fault · CONFIRMED.**  Every case
in this cell exceeds the 2,048 first-attempt cap (§3 measures the shortest at
2,504 records), so **every** case retried, as registered.  Attempts on the
stopping case: **2** (2,048 then the retry).

**A-1 R-4 — per-case record count and margin.**  Reported in §3 from an
unregistered diagnostic, because the registered path produced no case to
report.  ⚠ **The near-miss clause fires broadly**: `F3A5` idx 1/4/5/9/11 land
425–548 records from the ceiling, and three cases **exceed** it.

### RC-4 — the outcome must be `H-ENGINE` · **NOT SCOREABLE**

There is no cell, so no outcome class is certified. **I decline to score RC-4,
and I decline to declare `H-ENGINE`.**  INV-3's bias analysis is therefore
**neither confirmed nor retracted** by this sitting — the clause that would do
either has not been run.  An unregistered observation consistent with
`H-ENGINE` is reported in §6 and is **explicitly not** offered as RC-4.

---

## 2. THE OUTCOME CLASS

> ### **NONE — the cell was not captured.**

Not `H-ENGINE`, not `H-SILICON`, not `H-THIRD`.  Those three name what silicon
did; this sitting did not get to ask, through the registered instrument.

---

## 3. WHY IT STOPPED — TWO MECHANISMS, MEASURED, NOT ARGUED

### 3.1 THE REGISTERED CEILING OF 8,192 DOES NOT EXIST ON THIS RIG

The stopping error reads: *"reached the cap **8192** records (first attempt
2048) … **4096 records captured**"*.  It asked for 8,192 and got 4,096, and the
reason is in the transport:

* `sw/v30ctl.py:10` — *"+0x100000  **32 KB capture buffer (4096 x 64-bit
  records)**"*
* `sw/v30ctl.py:261` — `CAP_RECORDS = 4096`
* `sw/v30ctl.py:744` — `cap = max(1, min(int(v), CAP_RECORDS))`

**The requested cap is CLAMPED to the FPGA capture buffer's depth.**  F-1
registered *"the ceiling rises to 8,192"*; the software constant rose and **the
ceiling did not** — 4,096 records is a **hardware** limit of the harness.
`EMIT_CAP_RETRY = 8192` is **accepted and silently ignored** by the transport:
the same accepted-and-ignored class this repository keeps finding (the
`X1_AD_RETENTION` env-var finding, the `want_raw` finding), in a place with no
gate on it.

⚠ **This is a defect in the repair, not in the registration that asked for it.**
The prereg's own §1 table measures the doubly-odd `F3A5` case at **4,140 clock
rows for the instruction alone**, i.e. **above 4,096 before the prologue and the
store stub are counted**.  The repair could not have worked, and the arithmetic
that shows it was already written in the document that registered it.

### 3.2 THE PER-CASE LENGTH TABLE — **UNREGISTERED DIAGNOSTIC**

Read-only socket captures at the rig's **maximum** cap (4,096), one per cell
image, `use_core=False`, waits 0, **nothing written into any suite**.  This is
**diagnosis of the failure, not the cell** — the registered cell is what
`emit_suite.py emit` produces, and **no prediction is scored from this table**.
"Done-marker record" is the record index of the `OUT 0xFC` done sentinel.

| form | idx | CX | DF | preload | `SI`/`DI` | done-marker record | margin to 4,096 | parse |
|---|---|---|---|---|---|---|---|---|
| `F3A4` | 0 | 255 | 0 | 0 | odd/even | 2504 | 1592 | OK |
| `F3A4` | 1 | 255 | 0 | 2 | odd/odd | 2605 | 1491 | OK |
| `F3A4` | 2 | 256 | 0 | 0 | even/odd | 2512 | 1584 | OK |
| `F3A4` | 3 | 256 | 0 | 2 | odd/even | 2611 | 1485 | OK |
| `F3A4` | 4 | 257 | 0 | 0 | even/even | 2520 | 1576 | OK |
| `F3A4` | 5 | 257 | 0 | 2 | odd/odd | 2619 | 1477 | OK |
| `F3A4` | 6 | 255 | 1 | 0 | even/odd | 2504 | 1592 | OK |
| `F3A4` | 7 | 255 | 1 | 2 | even/odd | 2629 | 1467 | OK |
| `F3A4` | 8 | 256 | 1 | 0 | odd/even | 2512 | 1584 | OK |
| `F3A4` | 9 | 256 | 1 | 2 | even/even | 2637 | 1459 | OK |
| `F3A4` | 10 | 257 | 1 | 0 | odd/even | 2520 | 1576 | OK |
| **`F3A4`** | **11** | 257 | 1 | 2 | even/even | **never** | **exceeded** | **FAIL** |
| **`F3A5`** | **0** | 255 | 0 | 0 | **odd/odd** | **never** | **exceeded** | **FAIL** |
| `F3A5` | 1 | 255 | 0 | 2 | odd/even | 3623 | 473 | OK |
| **`F3A5`** | **2** | 256 | 0 | 0 | **odd/odd** | **never** | **exceeded** | **FAIL** |
| `F3A5` | 3 | 256 | 0 | 2 | even/even | 2637 | 1459 | OK |
| `F3A5` | 4 | 257 | 0 | 0 | odd/even | 3548 | 548 | OK |
| `F3A5` | 5 | 257 | 0 | 2 | odd/even | 3649 | 447 | OK |
| `F3A5` | 6 | 255 | 1 | 0 | even/even | 2528 | 1568 | OK |
| `F3A5` | 7 | 255 | 1 | 2 | even/even | 2627 | 1469 | OK |
| `F3A5` | 8 | 256 | 1 | 0 | even/even | 2512 | 1584 | OK |
| `F3A5` | 9 | 256 | 1 | 2 | even/odd | 3658 | 438 | OK |
| `F3A5` | 10 | 257 | 1 | 0 | even/even | 2520 | 1576 | OK |
| `F3A5` | 11 | 257 | 1 | 2 | odd/even | 3671 | 425 | OK |

**21 of 24 images are capturable at 4,096.  Three are not, for TWO DIFFERENT
REASONS, and the difference is the whole finding.**

### 3.3 `F3A5` idx 0 and idx 2 — **SLOW cases the rig cannot hold**

Both are the doubly-odd images.  At 4,096 records each reached **488 `MEMW` /
489 `MEMR`** of the **512 / 514** the case requires — cut off at ~95 % of the
loop, with the whole register dump still to come.

Extrapolating from this table's own singly-odd pairs — `F3A5` idx 3 (even/even,
CX=256, preload 2) finishes at 2,637 and idx 9 (even/odd, same CX and preload)
at 3,658, so **one split side costs ≈ 1,021 records** — a doubly-odd case at
CX=256 needs **≈ 4,550–4,700 records**.  That is **≈ 460–600 records past a
buffer that physically holds 4,096**, and it agrees with the prereg's own
independent model figure of 4,140 rows for the instruction alone.

**These are SLOW cases, not BAD ones.  Refusing to reroll them is CORRECT — and
they still cannot be captured.**

### 3.4 `F3A4` idx 11 — a **RUNAWAY**, and a **FALSE POSITIVE of the repair**

This is the case the registered run actually stopped on, and it is **not a
length failure at all**:

* it shows **378 `MEMW` / 340 `MEMR`** where the instruction needs **260 / 263**
  — it wrote **more** than the program asked for;
* every other `F3A4` image, at every count and alignment, finishes by record
  2,637, so length is excluded by this table's own controls;
* offline arithmetic (no board): with `DF = 1` its 257-byte destination descends
  through mirrored `[000e … 010e]`, i.e. **into `IVT_REGION`, over interrupt
  vector 3's segment word at `000e`–`000f`**.  Vector 3 is `testimage.TERM_VECTOR`
  — **the harness's own termination path** (`CODE_FILL = 0xCC` is `INT 3`, and
  the terminator sits at `TERM_AT`).  A case that overwrites vector 3 destroys
  the only way its program has to stop.

So it **cannot terminate**, and no cap of any size would capture it.  It is a
**placement collision — a BAD case**, which the emitter rerolled legitimately
before the repair.

⚠ **F-3 merged two mechanisms into one predicate** — *"one predicate, both
symptoms, per the standing simplicity principle"* — but a truncated capture and
a program that never terminates are **two different things** that happen to
surface through one string, `"no done marker"`.  The repair now refuses to
reroll **both**, so a legitimately-rerollable bad case **stops the run**.  The
simplicity principle is not violated by separating them: they are two mechanisms,
not one mechanism with a fitted exception.

⚠ **AND THE DIRECTED OVERRIDE IS WHAT MAKES COLLISIONS LIKELY.**  Undirected
emission draws `CX ∈ [0, 3]` (`sw/emit_suite.py:1100`), so a string destination
spans ≤ 6 bytes and rarely hits anything.  `--force-cx 255,256,257` spans **257
bytes**, and `gen_case` has **no carve-out guard on a string operand's
destination span**.  Measured over these 24 images, **9 destinations land in a
carve-out or the code region**; eight are harmless (they land on `0xCC` fill or
unused data/stack), and the one that hits the IVT is fatal.  **This hazard is
in neither the prereg nor A-1 nor A-2**, and it is the second reason this cell
does not simply "need a bigger buffer".

---

## 4. PER-CASE `sha256` OF THE PER-CLOCK ROWS

**The registered cell captured nothing, so it has no rows and no hashes.**  What
follows are the hashes of the **unregistered diagnostic** captures of §3.2 —
sha256 over the canonical JSON of each capture's full per-clock record list
(4,096 records each, `cap = 4096`, waits 0, socket).  Full rows retained on disk
for three of them (`F3A4` idx 0, `F3A5` idx 0, `F3A5` idx 2) under
`tests/v30/rep_cl0/DIAGNOSTIC-UNREGISTERED/`; the rest are hashed, not banked.

| form | idx | `MEMR` | `MEMW` | final `CW` | sha256 (first 32) |
|---|---|---|---|---|---|
| `F3A4` | 0 | 261 | 258 | 0 | `7dc5e44ee9babaa1bcd3547eed5aefac…` |
| `F3A4` | 1 | 261 | 258 | 0 | `4239f2eaa1fd8dab0b0a5e350fcdb3c9…` |
| `F3A4` | 2 | 262 | 259 | 0 | `3fa840f6b785cce7514a6b5a011a11b5…` |
| `F3A4` | 3 | 262 | 259 | 0 | `a277b96943b7af70ca2a15ced8b9176c…` |
| `F3A4` | 4 | 263 | 260 | 0 | `685c8ee3663745c41ad1f185fbd1a40d…` |
| `F3A4` | 5 | 263 | 260 | 0 | `8ac2f796300dadd7c2f48fbf03157ecd…` |
| `F3A4` | 6 | 261 | 258 | 0 | `5956c2027c5765a98761b171553cf9b4…` |
| `F3A4` | 7 | 264 | 261 | 0 | `c74e7c0db8a3d7c60a161065f6e6db0f…` |
| `F3A4` | 8 | 262 | 259 | 0 | `53771c9b816bca9a94051d910adcad15…` |
| `F3A4` | 9 | 265 | 262 | 0 | `b5b8739d5d3c5e4792f3e2ccbb88e3f7…` |
| `F3A4` | 10 | 263 | 260 | 0 | `8ceea7040716a9a9d638cc9568ee8b65…` |
| `F3A4` | 11 | 340 | 378 | — | `c5fe3f9c816734185bc0f71c869a2969…` |
| `F3A5` | 0 | 489 | 488 | — | `bb72166a9cace17b9b9e7f2c00c3699d…` |
| `F3A5` | 1 | 516 | 258 | 0 | `8f2b4505746812872d0b9f331fad78d3…` |
| `F3A5` | 2 | 489 | 488 | — | `f310c7c328d053e72ffc7bbe11165abf…` |
| `F3A5` | 3 | 265 | 262 | 0 | `40b624ea7af35ac890fe10cd9601e79e…` |
| `F3A5` | 4 | 520 | 260 | 0 | `a35a79f37ec356b673231e130135b4f4…` |
| `F3A5` | 5 | 520 | 260 | 0 | `5f6f0922f33cdac3a312da9455c161de…` |
| `F3A5` | 6 | 264 | 261 | 0 | `62e5f3ad9c4cf0dc07a6da3b8d4bb109…` |
| `F3A5` | 7 | 264 | 261 | 0 | `cd191f8805bfd4e2fccd571cc846581a…` |
| `F3A5` | 8 | 262 | 259 | 0 | `8158f0d1ee92aa3aa008af2de2f683f9…` |
| `F3A5` | 9 | 265 | 518 | 0 | `52b78cbc722fb766ada23c9fd60b592f…` |
| `F3A5` | 10 | 263 | 260 | 0 | `bd40991090601ec08eded00af6cae9e1…` |
| `F3A5` | 11 | 523 | 263 | 0 | `c9b248986156ca0c5705eb39ff1ccc2f…` |

---

## 5. `git diff --stat` OVER THE FOUR GATED SUITES — **P-6 MET**

```
$ git diff --stat tests/v30/v0.1 tests/v30/v0.2 tests/v30/v0.3 tests/v30/v20suite
(empty)
```

`git status --short` shows one new path from this sitting, `?? tests/v30/rep_cl0/`
(the emit log plus the diagnostic directory).  **The INV-3 archive is untouched
and unmodified** — `tests/v30/rep_cl0-INV3-archive/` still carries its
2026-08-17 15:25 mtimes and its five files hash as they did before this sitting
began.  Nothing was pruned, renamed or rewritten.

---

## 6. RIG INTEGRITY

| | |
|---|---|
| single-writer | **OK**, checked FIRST, before any board contact — no `v30ctl`/`serve` process on the board, no local serve client.  Board uptime 36 days. |
| `use_core` | **False** throughout.  The emit path's per-run truth-source assertion passed and stamped the log: `# TRUTH SOURCE: SOCKET (real chip, use_core=False)`.  Not weakened. |
| `div_guard` | **PINNED on every probe** — 6 readbacks (`post-abort`, `diag-case0`, `diag2-open`, `diag2-close`, `diag3-open`, `diag3-close`), every one `div=8 (4 MHz), commanded by this connection`.  **No UNPINNED readback.** |
| wait rig | `WRAND=0 replay=0 (commanded clean at connect, OK/OK)`; `--waits 0` (A-1 R-3). |
| `flash_log.jsonl` | **24 entries / `7eae7942a1d45691f5c36780ead69ed99ece7af440db92494dfaea42701911fe` BEFORE, and 24 entries / the IDENTICAL sha256 AFTER.**  No bitstream built, none written, `safe_flash.sh` not invoked. |
| `board_idle` | **clean**, run after the aborted capture and again after the diagnostics. |
| closing chip proof | **`check_ab_hw chip 800` → MATCH over 800 rows**, run twice (after the abort, and again after the diagnostic captures — the second is the closing control). |
| transport errors | **0.**  No `serve:` failure, no `TRANSPORT DROP` line, no quarantine other than the three parse failures of §3.2, which are the part's behaviour and not the transport's. |

---

## 7. UNREGISTERED

1. **`CAP_RECORDS = 4096` is a hardware ceiling and F-1 could not raise it**
   (§3.1).  The `cap` request is clamped by the transport with no diagnostic;
   `EMIT_CAP_RETRY = 8192` is accepted and ignored.  **No standing gate sees
   this.**
2. **The two mechanisms behind `"no done marker"` are distinct** (§3.4): a
   truncated capture (SLOW) and a non-terminating program (BAD).  F-3 merged
   them, so the repair refuses to reroll a case that ought to be rerolled.
3. **`gen_case` has no carve-out guard on a string operand's destination span**
   (§3.4), and `--force-cx` at 255–257 makes collisions likely where the
   undirected policy (`CX ∈ [0,3]`) made them nearly impossible.  9 of 24
   destinations land in a carve-out or the code region; one destroys
   `TERM_VECTOR`.
4. **An observation consistent with `H-ENGINE`, offered as an observation and
   NOT as RC-4** (§4): in the unregistered diagnostic captures, all four `F3A4`
   `CX = 256` images (idx 2, 3, 8, 9) parse with **final `CW` = 0** and carry
   **259 `MEMW` / 262 `MEMR`** against 258/261 at `CX = 255` and 260/263 at
   `CX = 257` — a clean +1 per element with the same +3 constant, i.e. **256
   iterations executed**.  Both engines perform **zero**.  ⚠ **This is not P-1,
   not P-2 and not P-7**: it is a different instrument path, its bus census is
   over the whole capture rather than `build_rows`' instruction window, and its
   population is missing the doubly-odd stratum exactly as the voided cell was.
   **It certifies nothing, it does not close RC-4, and it must not be quoted as
   the re-capture.**
5. The archived cell's `F3A4` reroll was also at **index 11**
   (`F3A4 case-seed 11 reroll: only 13 register words before the done marker`).
   Different seed, different image — **noted as a coincidence, no mechanism
   claimed.**

---

## 8. WHAT IS OWED, AND WHAT IS NOT DONE

**Nothing is fixed and nothing is derived in this sitting.**  No engine touched,
no width rule, no instrument change after board contact.  The 72-case validation
cell (A-2 §A-2.2) is **not** captured — it waits on a certified derivation cell,
which does not exist.  A per-row special case for microcode row `0094` remains
refused in advance.

**INV-3 stays open.**  Its falsifier is a conjunction — *complete the full
24-case cell* **and** *zero rerolls* — and only the second conjunct is met.  Its
registered consequence (*"the ceiling fix is insufficient and the disposition is
re-opened rather than re-argued"*) is **reported as reached**: the ceiling fix
is insufficient, measured, for a reason the fix's own pre-registration
contained.

**The disposition is the user's.**  It is not mine to choose among a deeper
capture buffer, a per-case capture that is not a single contiguous prefix, a
shorter cell (the doubly-odd stratum's `CX` is what puts it over), a destination
carve-out guard, or splitting F-3's predicate — and each of those is a change to
an instrument that must be **pre-registered before** the leg it governs.
