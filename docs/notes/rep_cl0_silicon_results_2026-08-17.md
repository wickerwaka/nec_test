# RESULTS — THE `REP` BYTE-STRING `CL == 0` CELL, ON SILICON

> ⚠ **THIS CAPTURE IS INVALIDATED AND GATES NOTHING — `invalidation_ledger.md`
> § INV-3.**  A-1 R-2 fired (§3): eight seeds were rerolled, six of them a
> systematically-excluded doubly-odd-aligned class inside P-3's gating control,
> so **the cell is VOID as registered** and its numbers are **NOT certified**.
> The capture is RETAINED as evidence — archived by rename at
> `tests/v30/rep_cl0-INV3-archive/`, nothing deleted, nothing rewritten — and
> the finding it points to is re-established by the re-capture INV-3 names.
> **Quote no figure from this document as a gate.**


Scored against `rep_cl0_silicon_prereg_2026-08-17.md` (`0dc40e51dc`), amendment
**A-1** (`bb37f154f2`) and amendment **A-2** (`5fd01af2c0`).  All three were
committed **before** the leg they govern; nothing was amended after contact.

| | |
|---|---|
| tree at capture | `master`, HEAD **`5fd01af2c0`** (working tree otherwise unmodified) |
| leg | **SOCKET ONLY**, `use_core=False`, `--waits 0`, **NO FLASH** |
| capture | `python3 sw/emit_suite.py emit --engine chip --opcodes F3A4,F3A5 --cases 12 --seed rep-cl0 --force-cx 255,256,257 --force-df 0,1 --waits 0 --out tests/v30/rep_cl0` |
| artefact | `tests/v30/rep_cl0-INV3-archive/` — 24 cases, full per-clock rows, **UNCOMMITTED** |

⚠ **READ §2 BEFORE QUOTING ANY NUMBER IN §1.**  The observations are
unambiguous and mutually consistent; **A-1 R-2's invalidation clause
nevertheless FIRED**, and that is reported as registered, not restated.

---

## 1. THE PREDICTIONS, AS OBSERVED

Every figure below is read off the 24 captured cases.  `iterations` is derived
from the `SI`/`DI` deltas; the bus census is over the instruction window that
`build_rows` retains (opcode fetch → window-closing `F` pop), which is exactly
the window P-2 is registered against.

### P-1 — final state · **MET (as observed)**

`F3 A4` at `CX = 256`, all four cases (idx 2, 3 at `DF=0`; idx 8, 9 at `DF=1`):

| idx | DF | preload | final `CX` | Δ`SI` | Δ`DI` | elements |
|---|---|---|---|---|---|---|
| 2 | 0 | 0 | **0** | +256 | +256 | **256** |
| 3 | 0 | 2 | **0** | +256 | +256 | **256** |
| 8 | 1 | 0 | **0** | −256 | −256 | **256** |
| 9 | 1 | 2 | **0** | −256 | −256 | **256** |

Registered falsifier — *"any other final `CX`"* — did not fire.
**Silicon executes all 256 iterations.**

Both engines predict final `CX = 256` with `SI`/`DI` **unmoved** (§2 of the
prereg, re-run on this tree at capture time and reproducing exactly — model
`rep_cl0_repro.py`, RTL `repdrive.py`: `F3A4 CX=256 → CXfin 256, iters 0`).
**Silicon and both engines disagree.**

### P-2 — bus census · **MET**

Same four cases, `MEMR`/`MEMW` bus cycles in the instruction window:

| idx | `MEMR` | `MEMW` |
|---|---|---|
| 2 | **256** | **256** |
| 3 | **256** | **256** |
| 8 | **256** | **256** |
| 9 | **256** | **256** |

Registered falsifier — *"any count other than 256/256"* — did not fire.

### P-3 — word control (GATING) · **MET (as observed)**

`F3 A5` at `CX = 256`: idx 2, 3, 8, 9 all final `CX = 0` with Δ`SI` = Δ`DI` =
**±512 bytes = 256 word elements**.  The gating control passes, so P-1 is
interpretable **on the observational axis**.

⚠ **This is the sub-cell in which A-1 R-2's rerolls occurred** — see §2.  The
gate is met by what was captured; the question §2 raises is whether what was
captured is the population that was registered.

### P-4 — bracketing controls · **MET**

| form | CX=255 | CX=257 |
|---|---|---|
| `F3A4` | 255 elements, final `CX`=0 (idx 0,1,6,7) | 257 elements, final `CX`=0 (idx 4,5,10,11) |
| `F3A5` | 255 word elements (idx 0,1,6,7) | 257 word elements (idx 4,5,10,11) |

All eight bracket cases on each form complete their exact registered count.

### P-5 — DF symmetry · **MET**

Iteration counts at `DF=1` are identical to `DF=0` on both forms at all three
counts (255 / 256 / 257).  Only the **sign** of the `SI`/`DI` step reverses,
which the prereg explicitly excludes as a falsifier.  No DF-dependent
difference in any iteration count.

### P-6 — no collateral movement · **MET**

```
$ git diff --stat tests/v30/v0.1 tests/v30/v0.2 tests/v30/v0.3 tests/v30/v20suite
(empty)
```

`git status --short` shows exactly one new path from this sitting:
`?? tests/v30/rep_cl0-INV3-archive/`.  Nothing moved in any gated suite.

### P-7 — trace length as discriminator · **MET, H-ENGINE band**

Registered bands: **H-SILICON ⇒ ~15–17 records**, **H-ENGINE ⇒ ~2,085**.

`F3 A4` at `CX = 256`: **2,061 / 2,059 / 2,061 / 2,059** window rows
(idx 2, 3, 8, 9).  Two orders of magnitude from the H-SILICON band and
adjacent to the H-ENGINE band (A-1's model figure for the neighbouring
`CX = 257` case is 2,085; for `CX = 256`, 2,077).  Not a length in neither
band, so the H-THIRD falsifier did not fire.

### A-2 §A-2.3 — the three-way agreement gate

**P-1 (256 elements) · P-2 (256/256 bus cycles) · P-7 (2,061 rows) AGREE.**
No disagreement among the three independent readings, so the registered
STOP condition did **not** fire.

---

## 2. THE OUTCOME CLASS

> ### **H-ENGINE — silicon runs the loop.**

`REP MOVSB` with `CX = 0x0100` copies **256 bytes** on a real V30.  Both the
C++ model and the ucore RTL perform **zero** iterations on the identical case.
The shared `REP` entry row's Z is **16-bit on the die**, and resolving the row's
ALU flag width from the instruction's w-bit (`sim/exec_impl.h:1284`,
`hdl/rtl/ucore/v30u_eu_row.svh:68`) is **defective in both engines**.

**No fix is derived, proposed or implemented in this sitting**, per prereg §6
and the sitting's own charter.  A per-row special case for microcode row `0094`
remains refused in advance.

⚠ **CERTIFICATION IS WITHHELD.**  The observation above is what silicon did.
It is **not** certified as the registered cell's verdict, because A-1 R-2's
invalidation clause fired (§3).  The disposition of that clause is the user's,
not mine, and I have not re-captured, re-seeded, raised `EMIT_CAP`, or
otherwise adjusted the instrument to make the cell pass.

---

## 3. ⚠ A-1 R-2 FIRED — THE CELL IS **VOID AS REGISTERED**

**A-1 R-2, verbatim:** *"THE SEED IS NEVER REROLLED ON A CAPTURE-LENGTH
FAILURE. … The same image retries at the larger cap. **A rerolled seed in this
cell invalidates the cell.**"*

**Eight seeds were rerolled.**  `tests/v30/rep_cl0-INV3-archive/emit_log.txt`:

| form | attempts rerolled | message |
|---|---|---|
| `F3A5` | 1, 3, 4, 5, 8, 9, 14 (**7**) | `no done marker in trace (runaway test?) — quarantine` |
| `F3A4` | 11 (**1**) | `only 13 register words before the done marker` |

### 3.1 What actually happened — two distinct instrument paths

R-2's registered belief is that a capture-length failure **retries the same
image at 4,096 and never rerolls**.  Measured, that is true only up to a point:

* **`no done marker`** — `emit_case` (`sw/emit_suite.py:1896-1904`) *does*
  retry the same image at `EMIT_CAP_RETRY = 4096`.  When the **retry also
  fails**, the `RunError` propagates to `cmd_emit`'s handler
  (`:2395-2413`), which **rerolls the seed**.  R-2 did not anticipate a
  double failure, and the reroll path is reached through it.
* **`only 13 register words before the done marker`** — this message does
  **not** contain the string `"no done marker"`, so `emit_case`'s retry
  **never fires at all**.  The case is rerolled straight from the 2,048
  attempt, with the 4,096 cap never tried.  This is a **second, distinct**
  capture-window failure mode with **no retry path**.

Both are capture-length failures in mechanism.  R-2's clause therefore fired.

### 3.2 The bias is real, and I measured its shape

Regenerating each attempt offline (same `rng` seeds, no board contact) and
computing the source/destination alignment:

| attempt | output idx | CX | DF | `SI` odd | `DI` odd | est. bus cycles | status |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 255 | 0 | ✔ | ✔ | 1,020 | **QUARANTINED** |
| 3 | 2 | 256 | 0 | ✘ | ✘ | 512 | **QUARANTINED** ⚠ |
| 4 | 2 | 256 | 0 | ✔ | ✔ | 1,024 | **QUARANTINED** |
| 5 | 2 | 256 | 0 | ✔ | ✔ | 1,024 | **QUARANTINED** |
| 8 | 4 | 257 | 0 | ✔ | ✔ | 1,028 | **QUARANTINED** |
| 9 | 4 | 257 | 0 | ✔ | ✔ | 1,028 | **QUARANTINED** |
| 14 | 8 | 256 | 1 | ✔ | ✔ | 1,024 | **QUARANTINED** |

**Six of the seven `F3A5` quarantines are exactly the doubly-odd-aligned
images**, and **every `F3A5` case that survived has at most one odd operand**.
A word access to an odd address splits into two byte bus cycles, so a
doubly-odd `REP MOVSW` at these counts needs ~1,020–1,028 bus cycles ⇒ **over
4,096 clock rows**, beyond the ceiling even on the retry.  The reroll therefore
**systematically excluded the doubly-odd-aligned population from the word
form** — precisely the "biases a suite against long-trace cases" that R-2
exists to forbid.

**The cells that lost candidates are all in the word form**: output 1
(CX=255, DF=0) ×1, output 2 (CX=256, DF=0) ×3, output 4 (CX=257, DF=0) ×2,
output 8 (CX=256, DF=1) ×1 — i.e. inside **P-3's gating control** and P-4/P-5's
word-form legs.  Plus `F3A4` output 11 (CX=257, DF=1) ×1.

### 3.3 What the reroll did **not** touch

`F3A4`'s seed sidecar maps output indices **2, 3, 8, 9 → attempts 2, 3, 8, 9**:
**the four cases that carry P-1, P-2 and P-7 are first-choice, un-rerolled
images.**  No capture-length reroll occurred anywhere in the `F3A4` form.

**Direction-of-bias note, labelled as reasoning and NOT as a waiver:** the
reroll selects *for* short traces, and the short-trace signature (~15–17 rows)
is **H-SILICON's**.  The observed result is the long signature.  The bias
therefore runs opposite to the observation, so it is not a mechanism that could
have manufactured H-ENGINE.  **This argument does not repair the cell** — R-2
invalidates on the artefact, not on the plausibility of the artefact.

### 3.4 One quarantine is NOT explained

Attempt **3** (`F3A5`, output idx 2, CX=256, DF=0) has **both operands
even** ⇒ ≈512 bus cycles ⇒ ≈2,060 rows, with roughly 2,000 rows of headroom
under the 4,096 ceiling.  It should have been captured on the retry and was
not.  Checked and **not** the cause: no code/destination overlap
(`code=ba370`, `dst=2bd74..2bf73`), no source/destination overlap.
**Reported unexplained.**  It is the only quarantine in the sitting that the
alignment mechanism does not account for.

---

## 4. RIG INTEGRITY

| item | result |
|---|---|
| single-writer, re-run immediately before contact | **OK** — `uptime 36 days, 0 users, load 0.00`; `board_procs []`, `local_serve_procs []` |
| truth source | **`SOCKET (real chip, use_core=False)`** — emitted per-run assertion, unweakened (`EMIT_USE_CORE is False`) |
| `div_guard` / divider | **PINNED** — `div=8 (4 MHz), commanded by this connection`, at emission **and** again at idle readback |
| wait rig | `WRAND=0 replay=0 (commanded clean at connect, OK/OK)` — **waits 0**, A-1 R-3 honoured |
| `flash_log.jsonl` **before** | **24 entries**, `sha256 7eae7942a1d45691f5c36780ead69ed99ece7af440db92494dfaea42701911fe` |
| `flash_log.jsonl` **after** | **24 entries**, `sha256 7eae7942…` — **IDENTICAL**.  No `.sof`/`.rbf` built or written; `safe_flash.sh` never invoked |
| transport errors | **0** — no `serve:` transport drop logged; both forms ran to completion |
| `board_idle()` | **clean** — `NOP` image, 4,063 records, divider left at `div=8` |
| closing `use_core=0` chip proof | **`chip-vs-golden: MATCH over 800 rows`** (`sw/check_ab_hw.py chip 800`), run **after** everything |

**A-1 R-1 (retry path expected) — MET as registered.**  Every one of the 24
captured cases has a window longer than `EMIT_CAP = 2048` (minimum 2,052 rows),
so every case failed its first attempt and was captured on the retry at 4,096.
That is the registered normal outcome and is not a fault.

**A-1 R-4 (record count and margin) — MET IN SUBSTANCE, with a stated
limitation.**  No captured case lands within 256 records of the ceiling —
minimum tabulated margin is **1,000** (`F3A5` idx 4 and 10, 3,096 rows) — so
the near-miss clause did not fire on any captured case.  ⚠ **The raw record
count R-4 asks for is not recoverable from the artefact**: the goldens retain
the instruction **window**, not the raw capture, and the raw capture is strictly
longer (preload + store stub + done marker).  The tabulated margins in §5 are
therefore **upper bounds** on the true margin.  The ceiling was nevertheless
demonstrably reached in this cell — by the six excluded images of §3.2.

---

## 5. PER-CASE `sha256` OF THE PER-CLOCK ROWS

`sha256` over `json.dumps(case["cycles"], separators=(",",":"))` — the full
retained per-clock row array, canonical JSON, no digest substitution.
`rows` = window length; `margin` = `4096 − rows` (see the R-4 limitation above).

| form | idx | CX | DF | preload | final CX | rows | margin | MEMR | MEMW | sha256 |
|---|---|---|---|---|---|---|---|---|---|---|
| F3A4 | 0 | 255 | 0 | 0 | 0 | 2053 | 2043 | 255 | 255 | `848f86f689d1bf0b1f7a46c670d168d6ff69ac9ac9ff8912180d1d83cb56f1c8` |
| F3A4 | 1 | 255 | 0 | 1 | 0 | 2052 | 2044 | 255 | 255 | `6b9cc628b80657157a3c1ef35def5df54c3b9f98715271333ba9faf074028a66` |
| F3A4 | 2 | 256 | 0 | 0 | 0 | 2061 | 2035 | 256 | 256 | `a5646d48d8a34f9b7eb09d3807870e474a513e81d8e64714b73dcf629f266bfc` |
| F3A4 | 3 | 256 | 0 | 1 | 0 | 2059 | 2037 | 256 | 256 | `7ccf8f0ae92fe4feb807f51b764d74f661baa8247b35b04e82cc6fab3fa9933d` |
| F3A4 | 4 | 257 | 0 | 0 | 0 | 2069 | 2027 | 257 | 257 | `31465919efb71e8ee75ef607b72139ae83c069772f09a5fcf85ea793ba020c06` |
| F3A4 | 5 | 257 | 0 | 1 | 0 | 2068 | 2028 | 257 | 257 | `592c341fb96db39c771b4ec5b95cf9de8e4144f26a04d2a5d6f85962f3e7c450` |
| F3A4 | 6 | 255 | 1 | 0 | 0 | 2053 | 2043 | 255 | 255 | `64d0d5e3011f418ff13b40f01a1aa78640b007b389f46603b691afd0c6ef828f` |
| F3A4 | 7 | 255 | 1 | 1 | 0 | 2052 | 2044 | 255 | 255 | `51cc75fec38e3e967d5137fe1f4a3deae50d85d7c1b654c8637dc7ca31d0ed9f` |
| F3A4 | 8 | 256 | 1 | 0 | 0 | 2061 | 2035 | 256 | 256 | `3bfbd257c5de4867a8f38b6fe29df9d25f6fa13e1a629f4e1819a61e063047b0` |
| F3A4 | 9 | 256 | 1 | 1 | 0 | 2059 | 2037 | 256 | 256 | `96fb5497fa82184e1e835a655312c01f585b2b9e08f174d7a4387c361dd56448` |
| F3A4 | 10 | 257 | 1 | 0 | 0 | 2069 | 2027 | 257 | 257 | `a29bc5425a626687c285dadd8605604a013586c2d7f5dadafae4efe7251e1eff` |
| F3A4 | 11 | 257 | 1 | 1 | 0 | 2067 | 2029 | 257 | 257 | `a32d1de423d49a50e09cd36114e49596438db2937876a278118b09a42fdf8d17` |
| F3A5 | 0 | 255 | 0 | 0 | 0 | 2053 | 2043 | 255 | 255 | `e466235c147bdd3713eed5fa9a55956ecb14fdeaa29a0d697af19d0e1b3f6b68` |
| F3A5 | 1 | 255 | 0 | 1 | 0 | 3071 | 1025 | 255 | 510 | `f5a609993e57f9e54a61a3eb0bf7127fdc0c53285537456371b2f18daa5af128` |
| F3A5 | 2 | 256 | 0 | 0 | 0 | 3085 | 1011 | 512 | 256 | `bf86b636fa0f60ca83b43f9b9df4ba574b90d174ae678b7ce619544c4e6edafc` |
| F3A5 | 3 | 256 | 0 | 1 | 0 | 3084 | 1012 | 512 | 256 | `4665b407bf131aad3021fac51ad1eda0d00579a3c75aae1dc05766b6fe4bed5e` |
| F3A5 | 4 | 257 | 0 | 0 | 0 | 3096 | 1000 | 257 | 514 | `cc87502ce3cbb503a5d651b053072c2222ca480f1ff30a534d58d55059c39391` |
| F3A5 | 5 | 257 | 0 | 1 | 0 | 3095 | 1001 | 514 | 257 | `6f13b2a7555fafb9d5268a2c62e79ff017f8a3129b072cb8e97a5b1956de3974` |
| F3A5 | 6 | 255 | 1 | 0 | 0 | 3073 | 1023 | 510 | 255 | `e6ceba9d08ffb19e829e84afc266848e827116129ea566f31d747d6ba8e69132` |
| F3A5 | 7 | 255 | 1 | 1 | 0 | 3071 | 1025 | 510 | 255 | `bb940af7600d131d7995f01ed36fa54f1632ee723dc5626cb2f3ef2d282b92c6` |
| F3A5 | 8 | 256 | 1 | 0 | 0 | 3085 | 1011 | 512 | 256 | `aba6ef5c609a7208b4fa8102c8bb3e8cab13b907758fa5f21ebf1d1ffb22b2f5` |
| F3A5 | 9 | 256 | 1 | 1 | 0 | 2059 | 2037 | 256 | 256 | `9998d328dbf61f2288edb94cb55be56e35ef086714bdf2a66bf1788252d4a5b2` |
| F3A5 | 10 | 257 | 1 | 0 | 0 | 3096 | 1000 | 257 | 514 | `2be7af4a38eec6505dd49594325199947e101c297e7924d17ce4919f9f66cc0c` |
| F3A5 | 11 | 257 | 1 | 1 | 0 | 3095 | 1001 | 514 | 257 | `f9206c2a9b1a39175954cba910aa6268a8e60e07cc81f0c7d60380d710793b8d` |

Initial `CX` and initial `DF` were verified equal to the forced value on
**all 24** cases — the `--force-cx` / `--force-df` override reached the wire
and was not accepted-and-ignored.

---

## 6. `git diff --stat` OVER THE FOUR EXISTING SUITES (P-6)

```
$ git diff --stat tests/v30/v0.1 tests/v30/v0.2 tests/v30/v0.3 tests/v30/v20suite
$
```

Empty.  Nothing in `v0.1`, `v0.2`, `v0.3` or `v20suite` moved by a byte.

---

## 7. UNREGISTERED OBSERVATIONS

Everything here is outside the three governing documents and is recorded as an
observation, not as a claim.

1. **UNREGISTERED — the 4,096 ceiling is reached inside the derivation cell,
   and the reroll path is what happens then.**  A-1 assumed a capture-length
   failure always ends in a successful retry.  For doubly-odd-aligned `F3A5`
   images at these counts it ends in a **reroll**.  §3.1–§3.2.
2. **UNREGISTERED — a second capture-window failure mode with no retry path.**
   `only N register words before the done marker` (`sw/v30run.py:727`) does not
   match `emit_case`'s `"no done marker"` retry predicate, so it is rerolled
   from the 2,048 attempt without the 4,096 cap ever being tried.  Fired once
   (`F3A4` attempt 11).
3. **UNREGISTERED — one quarantine unexplained.**  `F3A5` attempt 3, §3.4.
4. **UNREGISTERED — the `F3A5` `MEMR`/`MEMW` asymmetry is operand alignment,
   not an anomaly.**  A word access to an odd address splits into two byte bus
   cycles, so a `REP MOVSW` shows `2N` cycles on whichever side is odd
   (e.g. idx 2: 512 `MEMR` / 256 `MEMW` = odd `SI`, even `DI`).  Expected
   V30 behaviour; noted because it makes the word form's census look
   irregular beside the byte form's clean 256/256.  P-2 is registered on
   `F3A4` only and is unaffected.
5. **UNREGISTERED — the offline engine column of prereg §2 was re-run on this
   tree at capture time and reproduced exactly**, so the silicon-vs-engine
   divergence is measured against a live engine column, not a quoted one.
   Model (`rep_cl0_repro.py`): 9 failing cells, every failure has
   `(CX & 0xFF) == 0` **and** a byte form.  RTL (`repdrive.py`): `F3A4`
   CX=256 → final `CX` 256, `SI`/`DI` unmoved, **0 iterations**; every other
   listed cell completes.
6. **UNREGISTERED — the `--force-cx`/`--force-df` refusal path is live.**
   `_forceable()` (`sw/emit_suite.py:213`) rejects non-`REP` forms and
   non-`emit` subcommands rather than accepting-and-ignoring.  Verified by
   reading, not exercised negatively in this sitting.

---

## 8. WHAT THIS SITTING DID **NOT** DO

* No fix derived, proposed or implemented — prereg §6, and the width rule is a
  separate registration.  A per-row special case for `0094` stays refused.
* No engine changed: no `sim/`, no `hdl/rtl/`, no ucore edit.
* **The 72-case validation cell (A-2 §A-2.2) was NOT captured.**  It is taken
  only after the derivation cell is scored, and the derivation cell's
  registered status is §3's.  **No width rule may be quoted as validated.**
* `EMIT_CAP` was **not** raised — A-2 §A-2.4 keeps that a separate
  registration, and raising it is also the obvious repair for §3, which is
  exactly why it was not taken in the sitting that found the problem.
* Nothing was committed.
* Nothing was flashed.
