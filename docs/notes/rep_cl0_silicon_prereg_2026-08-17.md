# PRE-REGISTRATION — THE `REP` BYTE-STRING `CL == 0` CELL, ON SILICON

**Committed BEFORE any board contact.** Everything below is registered; the
results sitting reports it **as registered, never restated**.

| | |
|---|---|
| tree | `master`, HEAD **`930216440f`** (verified `git rev-parse`) |
| the question | does a real V30 execute `REP MOVSB` with `CX = 0x0100`? |
| scope | **SOCKET ONLY (`use_core=False`).** **NO FLASH.** No bitstream is built, and none is needed — the socketed part is the DUT and the FPGA is only the harness. |
| offline finding under test | `docs/notes/` — this document is the first entry; the finding is reproduced by `sw/`-external scratch probes named in §2 and is restated here in full so this file stands alone. |

---

## 0. WHY THIS CELL EXISTS AT ALL

Both engines — the C++ model **and** the ucore RTL, which is what is in the
bitstream — perform **zero iterations** for a `REP`-prefixed **byte** string op
whenever `CL == 0 && CX != 0`.  Measured, both engines, all fourteen final
registers identical over 84 cases:

| broken (byte) | clean (word) |
|---|---|
| `A4` MOVSB · `A6` CMPSB · `AA` STOSB · `AC` LODSB · `AE` SCASB · `6C` INSB · `6E` OUTSB | `A5` MOVSW · `A7` CMPSW · `AB` STOSW · `AD` LODSW · `AF` SCASW · `6D` INSW · `6F` OUTSW |

**Nothing in this repository has ever asked silicon the question.**  Across
`v0.1`/`v0.2`/`v0.3` every one of the 45 `REP` string forms carries
`CX ∈ [0, 3]` on all 252,500 of its cases (`rng.randrange(0, 4)`,
`sw/emit_suite.py:1100`); the block-I/O forms reach 16
(`sw/emit_suite.py:1150-1151`); `v20suite` carries no `REP` form at all.  There
is therefore **no recorded silicon evidence either way**, and this cell exists
to create some.

### 0.1 The mechanism, so the two outcomes are distinguishable in advance

The `REP` entry test is one microcode row bank, and `docs/V20UC.TXT:186` shows
it is **shared between the byte and the word form** — the `?` is the W bit:

```
------- 001.1010010?.00 <rep> A4,A5
0094 CX -> COUNT   CX -> tmpb      ALU PASS tmpb
0095 SIGMA -> NULL                 ALU ADD  tmpc      <- flags latched here
0096 dir*sz -> tmpc                JMP Z     7        <- skips the whole loop
```

The 29-bit ROM row carries **no width field**.  Both engines therefore resolve
the row's ALU flag width from the *instruction's* w-bit —
`sim/exec_impl.h:1284` (`nl.byte = m_.op8;`) and
`hdl/rtl/ucore/v30u_eu_row.svh:68` (`al_byte_n = op8_n;`) — so the byte form
tests only `CL`.  Traced at `CX = 0x0100`, the same rows diverge on `op8`
alone: `A4` gives `ST = 0x0044` (Z **set**, the byte view of `0x00`) and `A5`
gives `ST = 0x0004` (Z clear).  Same row, same `SIGMA`, different Z.

**This is a shared defect by construction, not a coincidence** — one ROM, and
two independent implementations with the same missing information.  That is
precisely why model-vs-RTL agreement proves nothing here and why silicon must
be asked.

---

## 1. THE TWO RIVAL OUTCOMES, NAMED BEFORE THE RUN

**H-ENGINE** — silicon runs the loop (`CX = 0x0100` → 256 elements).  The
shared row's Z is 16-bit on the die; both engines are defective; the width rule
is ours to derive and fix.

**H-SILICON** — silicon also does nothing.  The engines are RIGHT, this is a
genuine V30 behaviour, no engine changes, and the suites are extended so the
behaviour is *gated* rather than accidental.

**H-THIRD** — silicon does something that is neither (a partial count, a wrap,
a hang, a different count per form).  **Registered in advance as a live
outcome**, so that it is reported as a finding and not as a surprise or an
instrument fault.  If H-THIRD is observed, no fix is derived in the same
sitting that observes it.

---

## 2. THE OFFLINE COLUMN, FROZEN NOW

Reproducers, committed with this document's sitting and re-runnable:

* model — `sw/testdata/rep_cl0/rep_cl0_repro.py` (~2 s, exits non-zero on the defect)
* RTL — `sw/testdata/rep_cl0/repdrive.py --forms F3A4,F3A5 --cx 3,255,256,257,512`

The engine column this cell is scored against, **registered as the prediction
for what the two engines will say**, so that any drift between now and the run
is caught:

| form | CX=255 | **CX=256** | CX=257 | CX=512 |
|---|---|---|---|---|
| `F3A4` MOVSB | 255 | **0** | 257 | **0** |
| `F3A5` MOVSW | 255 | 256 | 257 | 512 |

⚠ **Instrument limit, registered**: the C++ model returns an all-zero record
above roughly 10,000 true iterations (`CX = 40,000` fails, `10,000` is fine).
Every CX in this cell is far below that.  The RTL completes `CX = 65,535`.

---

## 3. THE CELL

**Derivation cell** — what the width rule, if any, may be derived from:

| axis | values |
|---|---|
| forms | `F3 A4` (MOVSB) and `F3 A5` (MOVSW) |
| CX | **255, 256, 257** |
| DF | 0 and 1 |
| preload | both conventions (non-prefetched / `63 C0` ×2), per the suites' own alternation |

= 2 forms × 3 counts × 2 DF × 2 preloads = **24 directed cases**, each captured
with full per-clock rows.

**Validation cell — DISJOINT, and not used to derive anything** (the standing
rule that a replacement key must be validated on data that did not select it):

| axis | values |
|---|---|
| forms | `F3 AA` (STOSB) · `F3 AB` (STOSW) · `F3 AE` (SCASB) · `F3 AF` (SCASW) · `F3 6E` (OUTSB) · `F3 6F` (OUTSW) |
| CX | **512, 768, 1024** |
| DF | 0 and 1 |

= 6 forms × 3 counts × 2 DF = **36 directed cases**.

**No number derived from the derivation cell may be quoted as validated until
it has been scored on the validation cell**, and the validation cell is not
captured until the derivation cell's predictions are scored.

---

## 4. PREDICTIONS — SCORED AS WRITTEN

Each is MET or MISSED.  A MISSED prediction is reported as missed.

* **P-1 (primary).**  On silicon, `F3 A4` at `CX = 256` completes **256
  elements**: final `CX = 0`, `SI = DI = initial ± 256`, and the store stub
  shows 256 bytes moved.  *Falsifier*: any other final `CX`.
  P-1 MET ⇒ **H-ENGINE**.  P-1 refuted with final `CX = 256` and `SI`/`DI`
  unmoved ⇒ **H-SILICON**.  Anything else ⇒ **H-THIRD**.

* **P-2 (bus-level discriminator, independent of the store stub).**  For the
  same case the per-clock capture carries **256 `MEMR` + 256 `MEMW`** data
  cycles between the `A4` opcode fetch and the next instruction's fetch.
  *Falsifier*: any count other than 256/256.  P-2 exists because P-1 reads a
  reconstructed final state and P-2 reads the wire; **they must agree**, and a
  disagreement is a rig finding, not a result.

* **P-3 (word control — RIG INTEGRITY).**  `F3 A5` at `CX = 256` completes
  **256 word elements** (512 bytes moved).  *Falsifier*: anything else.
  ⚠ **P-3 is a gating control: if P-3 is MISSED the cell is VOID and P-1 is
  uninterpretable**, because the case construction or the rig, not the part,
  is then in question.

* **P-4 (bracketing controls).**  `CX = 255` and `CX = 257` complete 255 and
  257 elements on **both** forms.  *Falsifier*: anything else.  These bracket
  the predicate and are the in-family controls that make the 256 cell readable.

* **P-5 (DF symmetry).**  Every prediction above holds identically at `DF = 1`
  with the sign of the `SI`/`DI` step reversed.  *Falsifier*: any DF-dependent
  difference in the ITERATION COUNT (a difference in addresses is expected and
  is not a falsifier).

* **P-6 (no collateral movement).**  After the run,
  `git diff --stat tests/v30/v0.1 tests/v30/v0.2 tests/v30/v0.3 tests/v30/v20suite`
  is **EMPTY**.  The probe writes only into its own new suite directory.
  *Falsifier*: any byte moving in an existing gated suite.

---

## 5. METHOD, AND THE ONE TOOL CHANGE IT NEEDS

The capture uses the standard emission path — `sw/emit_suite.py emit
--engine chip` — because that path already carries the socket pin, the
per-run assertions and the golden format the standing scorers read.

**The one change**: the string-op and block-I/O generators hard-code the count
(`sw/emit_suite.py:1100`, `:1150-1151`).  A directed override is added — a
`--force-cx` list consulted **only** when explicitly passed, leaving the
default random policy byte-identical when it is not.  Registered constraints
on that change:

1. It writes into a **NEW** suite directory (`tests/v30/rep_cl0/`), never into
   an existing suite.  P-6 is its falsifier.
2. With `--force-cx` absent, `emit_suite.py` must generate **byte-identical**
   cases to HEAD for a fixed `--seed`.  Registered as a gate on the change
   itself, scored before the board is touched.
3. `EMIT_USE_CORE` stays `False` and the existing per-run assertions
   (`sw/emit_suite.py:2223`, `:2370`) are not weakened.

### 5.1 Board discipline — the standing list, none of it waived

* single-writer check FIRST; abort if another writer holds the device.
* **socket only, `use_core=False`, explicit** — the board's CFG is sticky.
* `div_guard()` on every probe; an **UNPINNED readback is a rig-integrity
  FINDING** and stops the sitting.
* **NO FLASHING.**  No `.sof`/`.rbf` is built or written.  `flash_log.jsonl`
  must hold the **same number of entries** after the sitting as before, and
  that count is recorded in the results.
* full per-clock rows retained **with `sha256`** — never digests alone.
* `board_idle()` verified clean after the session.
* a `use_core=0` chip proof (`check_ab_hw chip 800` MATCH) **after** everything,
  as the closing control.

---

## 6. WHAT THIS CELL DOES NOT DO

* It does **not** derive the correct ALU flag-width rule.  `op8` is evidently
  right nearly everywhere else — 7,341,126 architectural cases pass with it —
  so the general rule is a separate derivation, and **a per-row special case
  for `0094` is refused in advance** as exactly the fitted rule the standing
  simplicity principle forbids.  This cell establishes only *what silicon
  does*.
* It does **not** change any engine.  No RTL, no `sim/`, no fix, in the sitting
  that takes the capture.
* It does **not** retire the blind spot.  Extending the suites' CX policy so
  `CL == 0` is permanently gated is a separate, later registration; this cell
  is 60 directed cases, not a suite.

---

## 7. THE RESULTS DOCUMENT OWES

`docs/notes/rep_cl0_silicon_results_2026-08-17.md` (or the date it is taken)
must carry, in this order:

1. P-1 … P-6, each **MET / MISSED / VOID**, as registered.
2. The outcome class — **H-ENGINE / H-SILICON / H-THIRD** — named explicitly.
3. The rig-integrity line: single-writer, `use_core`, `div_guard` pinned,
   `flash_log.jsonl` entry count before and after, `board_idle` clean,
   transport error count.
4. Per-clock row `sha256`s for every captured case.
5. `git diff --stat` over the four existing suites, expected empty (P-6).
6. Anything observed that is not in this document, labelled **UNREGISTERED**.
