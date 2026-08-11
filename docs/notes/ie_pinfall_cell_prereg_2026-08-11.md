# THE IE-RISE / PIN-FALL DIRECTED BOARD CELL — PRE-REGISTRATION

    tool        sw/ie_pinfall_cell.py
    branch      fuzz-v2-on-relanding, base `ae3da7c59a`
    era         the board carries FLASH #17 (`sw/testdata/flash_log.jsonl`,
                20 entries, sof `26c19f613e2caae8…`).  NO FLASH IS TAKEN.
    board       CAPTURE ONLY, SOCKET ONLY (`use_core=False`, explicit).
                No RTL edit, no bitstream, no flash.
    date        2026-08-11

**COMMITTED BEFORE THE FIRST BOARD CONTACT OF THE SITTING.**  The offline
calibration (`calib`, on `tb_sys ret`) and the offline core leg (`core`) were
taken before this document and are declared in §6 — they set the instrument and
supply the ENGINE's column; they do not set the silicon predictions, which are
enumerated in §4 as a closed table of five.

---

## 1. WHY THIS CELL EXISTS — THREE BOOKINGS, ONE MISSING MEASUREMENT

Three separate campaign bookings name the same absent instrument.

**(a) `fz2_w5_p3_results_2026-08-10.md` §4 — C-γ.**  The vectoring HALT wake's
prefetch suspend is REAL (the three C2 seats' `bad` fell 8–11 % when it was
landed) and its carrier `hlt_wake_int && irq_int_lvl` is WRONG: it also fires on
`fz2c/404040`, a banked SUCCESS, and broke it (`bad` 0 → 1438).  Verbatim
re-open condition:

> *a DIRECTED BOARD CELL on that race — the same cell §64.1 and wave-4's C-β
> both say does not exist — that measures, on silicon, whether the wake
> prefetch is present as a function of the IE/pin phase.*

**(b) `fz2_w4_results_2026-08-10.md` §3.3 — C-β.**  The park cost when the
display is cancelled.  Its falsifier is *"a capture in which `sti; hlt` with the
pin already high delivers INTA with NO idle clocks between the HALT boundary and
the acknowledge"*, and it is explicitly forbidden from being fitted on the three
seats that raised it.

**(c) `fz2_c2_results_2026-08-10.md` §5.2 — the nine load-bearing clocks.**
`run − arm` is the only column that separates anything; `fz2c/404040` (silicon
TAKES) is identical to the four `run − arm == 2` seats (silicon does NOT) on the
arm's offset from the pin fall, the window's opening offset, the window length,
`rep_kind`, the hold and the take's offset.  Verbatim:

> *Closing them needs a directed board cell on the IE-rise / pin-fall race,
> which does not exist; deriving one from these nine rows would be fitting.*

**The blocked population, as it stands in the FLASH #17 ledger**
(`sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json`): family
**`C2 INTA-vectored delivery` = 10 seeds** (`fz2c/404071` · `fz2c/405002` ·
`fz2c/405013` · `fz2c/405072` · `fz2c/410047` · `fz2e/512056` · `fz2e/513019` ·
`fz2e/514044` · `fz2e/516001` · `fz2e/516065`), plus `B2` 2, `C1` 1, `C3` 1,
`C4` 1.  Seven of the ten are classed **FUNCTIONAL** by
`fz2_materiality_census_2026-08-11.md`.

---

## 2. THE STIMULUS

Four directed programs.  **No rng anywhere in this cell** — it is a directed
cell, not a fuzz.  They are identical in length, in byte count, in queue-pop
structure and in every address, and differ in exactly two bytes:

| leg | body | what it is |
|---|---|---|
| `eirun` | `FA` · `90`×6 · `FB` · `90`×64 | `DI`, run, `EI`, free-running sled |
| `eihlt` | `FA` · `90`×6 · `FB` · `F4` · `90`×64 | …and then `HLT` parks |
| `ierun` | `90` · `90`×6 · `90` · `90`×64 | **control**: IE never falls |
| `iehlt` | `90` · `90`×6 · `90` · `F4` · `90`×64 | **control**: IE never falls, parks |

`testimage.normalize_psw` FORCES `IE = 1` into every composed image (a fuzz-v2
rule, `testimage.py:118` — *"a randomized PSW that arrives with interrupts
masked makes the external INT event a no-op"*), so the ONLY route to a cleared
IE is an instruction, and `DI` is it.  The controls put `NOP` where `DI` and
`EI` go, so the **only** difference between a leg and its control is the state
of one flag — not one address, not one cycle, not one pop.

IVT vector `0xFF` → `0x8800`, inside the code region's `0xCC` fill, so the entry
is itself the `INT3` that reaches the composed terminator.

Image sha256 (composed, 64 KB; the same values are carried in
`sw/testdata/ie-pinfall/predictions.json`, which is the artifact of record):

| leg | sha256 |
|---|---|
| `eirun` | `4fe2c705f1a1828e1a8dc37f37f32302c58202eba6a4168e1d90ee30704c2fcd` |
| `eihlt` | `9f03679b9df19bfe7e757745472f9f5c921198e574df66e91d4d937734c5e39f` |
| `ierun` | `fdb83a0d5c4cb1cfef45e4d1953279cfed50971c694f5a262f1d1cd6e0f60be5` |
| `iehlt` | `2f1a09e8a31f01165c604b874e2042ec0bdc99307f4bcc9fd1c33d4336e82dfe` |

## 2.1 THE REFERENCE CLOCK IS MEASURED, NOT MODELLED

Every quantity is reported against **`t_ei`, the EIGHTH queue `F` pop at or
after the CODE T1 whose address is the body anchor.**  The loader's terminal far
jump flushes the queue, so that T1 is the program's first fetch and the eight
pops are `DI` + six `NOP` + the setter, in order — on any engine and on silicon
alike.  `t_ei` is read off the **QS pins**; no model is in the loop.

The pin's own RISE and FALL are read from capture bit **[52] (`pin_int`)**, the
EFFECTIVE level the CPU is shown, **not** from the directive that was sent.
INV-1 is the reason: a directive the rig truncated is not the stimulus the part
saw.

## 2.2 THE SWEEP AXES

    rise_off = rise − t_ei        (clocks; where the pin arrives)
    fall_off = fall − t_ei        (clocks; `fall` = the first low row)

The rig takes `(delay, hold)`.  `rise = anchor_t1 + delay + 2`
(`nec_bus.sv:g_evt` — match latched at the T1, `delay` ticks counted, drive on
the next), and `hold` is the pulse WIDTH, so `fall_off = rise_off + hold`.
`hold = 300` is the banked corpus's own never-falls value and is swept beside
the finite ones.

    rise_off  ∈ {−16,−12,−8,−6,−4,−2,0,2,4,6,8,10,12,16,20}   (full legs)
              ∈ {−16,−8,−4,0,4,8,16}                          (controls)
    fall_off  ∈ [−8, +16]  (one clock apart)  ∪  {never}

**2,200 cells**: `eirun`/`eihlt` × waits 0,1,2,3 at 219 each; `ierun`/`iehlt` ×
waits 0,3 at 112 each.  Full stratum table in `predictions.json`.

## 2.3 THE OBSERVABLES — ALL OFF THE PINS

| name | definition |
|---|---|
| `taken` | **any** INTA T1 in the capture window |
| `ack_off` | first INTA T1 − `t_ei` |
| `ack_off_hlt` | first INTA T1 − `t_hlt` (the HLT pop) — **C-β's quantity** |
| `wake_prefetch` | CODE cycles (T1s) strictly between the HALT display's first row and the first INTA — **C-γ's quantity** |
| `n_halt` | rows on which BS = HALT |

A cell is **structurally invalid** (`ok = False`, RETAINED and REPORTED, never
silently dropped) when the anchor T1 is not in the window, or fewer than eight
`F` pops precede it, or an INTA lands **before** `t_ei` — the last of which
means the pin rise beat the `DI` and the request was recognised while IE was
still SET from the loader.  That is the `PRE_DI` class and it is a coverage
loss, not a result.

---

## 3. WHAT WOULD MAKE THIS CELL WORTHLESS, STATED FIRST

Nothing here is quotable if:

* the controls `ierun`/`iehlt` do NOT take at every sweep point where the pin is
  present at all — that would say the pin path, not the IE path, is what the
  sweep is moving;
* the null cells (no directive) produce an INTA — the rig is manufacturing the
  observable;
* the board and the offline `tb_sys ret` column disagree on `t_ei` or on
  `anchor_t1` — the two are not running the same program.

These are checked and reported before any threshold is quoted.

---

## 4. THE HYPOTHESES — A CLOSED TABLE OF FIVE, EACH NAMING A DISTINCT INTEGER

The measured quantity is

> **T\* = the smallest `fall_off` at which a maskable request is TAKEN**, over
> cells whose RISE is strictly before `t_ei` (so the pin is present across the
> IE rise and the only question is when it LEAVES).

| id | T\* | what it says about silicon | what it implies for the seats |
|---|---:|---|---|
| **H1-ucore-3** | **3** | recognition needs the pin HIGH at `t_ei+2` — the ucore's own threshold; the engine is already right | the §64.1 four and `fz2c/404040` are **not** separated by this cell; C-γ stays blocked and the seats need another mechanism |
| **H2-later-4** | **4** | silicon needs the pin ONE CLOCK LATER than the ucore: the engine takes on a pin the die has already let go | the four `run − arm == 2` seats are explained EXACTLY, and `fz2c/404040` must have its fall one clock later than theirs |
| **H2-later-5** | **5** | as H2-later-4, two clocks later | same shape; separates the seats only if their falls straddle `t_ei+4` |
| **H3-latch** | **−1** | silicon REMEMBERS a request present before IE rose and gone by the time IE is set — a true IE-rise latch | the ucore is right in KIND and too SHORT in reach; the four seats are then not a threshold question at all |
| **H4-level-only** | **9** | no memory whatever — the pin must still be high when the microcode reaches its INTA, i.e. T\* equals the acknowledge latency | registered so the cell can refute it **on its own evidence** rather than by citing `fz2_c2_results` §5.3 (31 of 251 chip acknowledge runs begin at or after the pin's own fall) |

**A sixth outcome is registered in advance: NO SHARP THRESHOLD.**  If the taken
and not-taken `fall_off` sets INTERLEAVE, T\* is not a number and the cell
reports the interleaving rather than a fitted midpoint.  That is a finding.

**A seventh: T\* NOT WAIT-INVARIANT.**  If T\* differs across waits 0–3, the
quantity is not a clock offset from the IE rise and the cell says so.

### 4.0a THE WAIT AXIS IS NOT A REPEAT — IT SEPARATES TWO LAWS OF THE SAME SHAPE

A threshold measured on ONE boundary grid cannot tell

* **L-clock** — *"taken iff the pin is high at `IE_rise + k`"* — from
* **L-boundary** — *"taken iff the pin is high at the sample point of the first
  instruction boundary at or after `IE_rise`"*,

because on one sled the two coincide.  The sled is fetch-limited `NOP`s, so its
boundary spacing is set by the wait level and NOTHING ELSE: at w0/w1/w2/w3 the
same eight bytes put `t_ei` at 170 / 235 / 272 / 309, i.e. the grid stretches by
a measured 1.0 / 1.4 / 1.6 / 1.8.  **L-clock predicts the SAME T\* at all four
wait levels; L-boundary predicts a T\* that stretches with the grid.**  This
reading is registered here so it cannot be reached for afterwards.

### 4.1 WHERE THE CELL DISCRIMINATES, AND WHERE IT PROVES NOTHING

Two hypotheses are separated **only** at `fall_off` values strictly between
their thresholds.  Enumerated in `predictions.json → discrimination`:

| pair | separating `fall_off` |
|---|---|
| H3 vs H1 | −1 … 2 |
| H1 vs H2-4 | 3 |
| H1 vs H2-5 | 3, 4 |
| H2-4 vs H2-5 | 4 |
| any vs H4 | up to 8 |

**`fall_off ≥ 9`: every hypothesis says TAKEN.  `fall_off < −1`: every
hypothesis says NOT TAKEN.  Cells there are COVERAGE, NOT EVIDENCE, and are
reported as such.**  The sweep spends ~40 % of its cells outside the
discriminating band deliberately — a threshold with no shoulder on either side
is a threshold nobody can check.

### 4.2 THE WAKE LEG (C-γ) — THREE REGISTERED OUTCOMES

Measured on `eihlt`, over cells that vector:

| id | prediction |
|---|---|
| **W1-always-suspend** | `wake_prefetch == 0` at EVERY vectoring sweep point — wave-5's C-γ as written, with `irq_int_lvl` a sufficient carrier |
| **W2-always-prefetch** | `wake_prefetch ≥ 1` at EVERY vectoring sweep point — the ucore's current behaviour is the law and the seats are something else |
| **W3-phase-split** | `wake_prefetch` DEPENDS on the pin phase, with a threshold clock this cell names — the outcome wave-5's own measured split implies, and the one that re-opens C-γ keyed on a MEASURED quantity |

### 4.3 THE PARK LEG (C-β)

C-β's falsifier is fired iff, on `eihlt` with the pin already high before the
HLT pop (`rise_off < 0`, `hold = 300`), the acknowledge arrives with **no idle
clock** between the HALT boundary and the first INTA.  `ack_off_hlt` and
`n_halt` are reported per cell; the C-β claim under test is *two idle clocks*.

### 4.4 HOW THE SEATS WILL BE SCORED — AND WHAT CANNOT BE ASKED OF THEM

Registered here, before the measurement, so the scoring rule is not chosen
after seeing the threshold.

**What IS available engine-free on a banked seat capture.**  The fuzz-v2
capture carries both legs as decoded rows (`real` = chip, `sim` = core), each
with `pin_int`, so per seat this cell reads: the pin's rises and falls, the
INTA RUNS on each leg, and for every acknowledge run its offset from the pin's
previous fall.  Measured on the eleven booked seats before any board contact
(`sw/testdata/ie-pinfall/seats.json`): every one has **exactly one pin rise**,
and the four `run − arm == 2` seats are precisely the ones where the CORE runs
MORE acknowledge runs than the CHIP (`fz2c/405002` +1, `fz2c/405013` +1,
`fz2c/405072` +2, `fz2e/512056` +1), while `fz2c/404040` is core == chip with
its second chip acknowledge at **`ack − fall = +7`**.

**What is NOT available.**  The clock IE rises inside a seed is NOT on the
pins.  The §5.2 census obtained it from a CORE-side trace, and this cell has no
such trace for the seats.  **So the seats cannot be placed on the T\* axis
directly**, and any figure that claimed to would be an engine's opinion wearing
a measurement's clothes.

**Therefore the registered seat scoring is a CONSISTENCY test, not a
placement**:

| id | test |
|---|---|
| **S-1** | does the measured T\* differ from the ucore's? If NO, the C2 residue is not a threshold question and this cell says so about all ten C2 seeds at once. |
| **S-2** | if T\*(silicon) > T\*(ucore), the direction is right for the four `run − arm == 2` seats (core takes, chip does not) — and it must ALSO be consistent with `fz2c/404040`, where BOTH take.  If a single threshold cannot hold both, the threshold is not the separator and the cell reports that as its result. |
| **S-3** | `fz2c/404040`'s `ack − fall = +7` must be reproducible IN THE CELL: at some sweep point the chip must acknowledge with the pin already down for ~7 clocks. If no sweep point does, the seat's behaviour is outside the cell's regime and is booked, not explained. |

**S-2 is the one that can go either way, and it is the point of the cell.**

---

## 5. INTEGRITY BARS

| id | bar | STOP? |
|---|---|---|
| **I-1** | single-writer asked of the board (`uptime` + `ps` + local `pgrep`) and **OK** before the first capture | YES |
| **I-2** | `use_core=False` passed explicitly on every capture; `EMIT_USE_CORE is False` asserted at import | YES |
| **I-3** | `div_guard` **PINNED** at the preflight, at every stratum boundary, and at the end — an UNPINNED readback is a rig-integrity FINDING and is recorded, not smoothed | report |
| **I-4** | **0 transport errors**; three CONSECUTIVE errors STOP the cell | YES on 3 consecutive |
| **I-5** | stability: **≥ 5 %** of points captured **3×** and byte-identical on the FULL capture-word stream (the tool takes every 20th cell = 5.0 %) | report |
| **I-6** | full per-clock capture words retained per cell with a **sha256** per cell — never digests alone | YES |
| **I-7** | NO FLASH.  `flash_log.jsonl` has **20 entries** before and after | YES |
| **I-8** | `board_idle()` at the end, result stated | report |
| **I-9** | the four control/null clauses of §3 | report; nothing quoted if they fail |

**A rig-integrity finding OUTRANKS the cell.**  If the rig misbehaves the
sitting stops and reports the rig, and no threshold is quoted from a session
that had to be nursed along.

An **UNSTABLE** cell is not automatically a failure: this is a race cell, and a
point that flips between repetitions is exactly the thing a race cell exists to
characterise (the RR1 / P5 precedent, `s13_board.cmd_race`).  Unstable points
are counted, named, and characterised — never forced to be deterministic and
never averaged away.

---

## 6. WHAT WAS TAKEN BEFORE THIS DOCUMENT, AND WHY IT DOES NOT SET THE SILICON PREDICTIONS

* **`calib`** (offline, `tb_sys ret`) measures `anchor_t1` and `t_ei` per
  (leg, wait).  It is an INSTRUMENT SETTING: it decides where the sweep LOOKS.
  Every scored offset in `run`/`score` is recomputed from the capture's OWN
  measured `t_ei` and its OWN measured pin edges, so a calibration wrong by k
  clocks shifts coverage and biases nothing.  Values:
  `anchor_t1` 145 / 207 / 240 / 273 and `t_ei` 170 / 235 / 272 / 309 at
  waits 0 / 1 / 2 / 3.
* **`core`** (offline, `tb_sys ret`) runs the identical grid on the ucore.  Its
  w0 `eirun` result — **T\* = 3, SHARP** (taken `fall_off` 3…16, not-taken
  −8…2, no interleaving) — is what H1 encodes, and it is stated here rather
  than discovered later.  **The ucore is not the reference**; the correctness
  target is silicon (CLAUDE.md, 2026-08-04).  The core column exists so the
  measured silicon threshold can be put beside the engine's cell for cell on
  the identical stimulus.
* Nothing else.  No board, no flash, no RTL.

---

## 7. WHAT LANDS FROM THIS SITTING

**NOTHING IN `hdl/`.**  The deliverable is a measurement and a booking:
`docs/notes/ie_pinfall_cell_results_2026-08-11.md`, naming the measured law per
leg, the confirmed/refuted hypotheses, and — as NEXT-WAVE CANDIDATES, not
landings — the RTL each verdict would imply.  Any RTL that follows gets its own
pre-registration, its own control build and its own G6 receipt, per the standing
promotion rule.
