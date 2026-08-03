# ucsim-t provenance ledger — cycle-accurate timing mode

Companion to `docs/notes/ucsim_provenance.md`, which covers the ARCHITECTURAL
model.  This file covers TIME: every timing behaviour the simulator implements,
tagged with where it comes from.  Same discipline, same rule — at closure, the
set of entries still tagged **ASSUMPTION** is precisely "what the assets do not
determine about timing".

Provenance classes:

| class | meaning |
|---|---|
| **ROM** | read directly out of `docs/V20BITS.TXT` via `docs/V20UCDIS.PAS` |
| **LAW** | a law card / frozen black-box oracle inherited from the retired biu-rebuild campaign; cited by artifact |
| **MEASURED** | measured on silicon and recorded in a golden suite, `docs/facts/*`, or a frozen capture; cited by fact |
| **ASSUMPTION** | not determined by the assets; adopted because it reproduces the goldens. Evidence and falsifier recorded. |
| **SCAFFOLDING** | a deliberate placeholder that is KNOWN wrong, kept only so the next stage has something to replace. Every entry names the stage that removes it. |

**Guiding principle (user directive, carried into every entry).** This is 1980s
hardware; NEC wasted no silicon on anything unnecessary.  Complex or confusing
observed behaviour is most likely simple systems interacting in ways we do not
yet understand.  A large fitted table or a many-cased rule is a SIGNAL OF
MISUNDERSTANDING, not a deliverable.  Where an entry below needs a special
case, the special case is written down as an open question, not as a law.

Status: **T0 complete, 2026-08-01.  T1 IN PROGRESS — the w0 timing core and
the T1 mechanism set exist; the ratchet stands at 155,011 / 169,000 rows-exact
at w0 with 282 of 347 forms 100 % exact (§8).  The T1 exit gate (v0.1
166,800/166,800 cycle-row exact at w0) is NOT met.**

---

## 0. Inherited constraint set

The biu-rebuild campaign (task #34) was retired by user decision on 2026-08-01
(`docs/notes/biu_rebuild_retirement_2026-08-01.md`).  Its law corpus — law
cards C1-C16, the 104 frozen black-box oracle/validation JSONs under
`sw/testdata/biu_blackbox/`, the census artifacts, and the B1-B4 tooling — is
formally INHERITED here as this campaign's constraint set.  Nothing in that
corpus is re-derived; it is either replayed as a gate or explicitly retired
with a reason.

### 0.1 B4 closure adjudication — **NOT ESTABLISHED (the NO-GO stands)**

The campaign plan flagged a documentation contradiction to settle in T0 before
anything relies on `(grid_phase, occupancy, fill)` closure.  Adjudicated here.

**The two claims.**

* `docs/notes/biu_blackbox_campaign.md:3-4` (untracked; mtime 2026-07-30
  22:16): *"Status: **PAUSED before Stage C**. `sw/b4_closure_v2.py` remains a
  NO-GO result and is not evidence that `(phase, occupancy, fill)` closes the
  machine."*
* `docs/notes/biu_rebuild_P1.md:90` (written by commit c23c6c1808,
  2026-07-28 21:29): *"## 6. B4 exp_resume closure — **GO (non-circular
  re-analysis, P1-review blocker 1)**"*, on the strength of w1 0/494 + w3 0/494
  = **0/988** violations, with **21/185 w0** violations excused via design §4a
  coarse-tuple lossiness.

**The plan's hypothesis was that these answer different questions — that the
blackbox doc's NO-GO refers to an ORIGINAL b4_closure predating the
non-circular reanalysis.  That hypothesis is FALSE.**

1. The blackbox doc names `sw/b4_closure_v2.py` **by filename**; it is talking
   about the v2 non-circular script itself.  There is no `sw/b4_closure.py`
   (v1) in the repo or in any commit on any branch — `git log --all
   --diff-filter=A -- 'sw/b4*'` yields only `b4_capture.log`,
   `b4_closure_v2.log`, `b4_closure_v2.py`, `b4_resume_events.json`.  The v1
   analysis was `sw/exp_resume.py sweep` (commit 0b9b00243a), a different tool
   with a different (coarse-tuple + excusal) method.
2. The chronology runs the OPPOSITE way from the hypothesis: c23c6c1808 =
   2026-07-28 21:29; the blackbox doc = 2026-07-30 22:16; the audit in
   `docs/notes/biu_eu_session_summary_2026-08-01.md` = 2026-08-01 09:07.  The
   NO-GO line is the LATER artifact, not the earlier one.
3. The blackbox doc's assertion is literally true of the artifact c23c6c1
   itself committed: `sw/b4_closure_v2.log:31` reads
   `=== B4_V2_VERDICT: NO-GO  (violations=21) ===`.

**Both sides agree on the numbers.**  Re-derived independently from
`sw/b4_resume_events.json` (14,536 events; seeds 0-7, k 0-7,
w ∈ {0:1184, 1:6676, 3:6676}; 9,936 excluded as `eu_ord = -1`):

| w | testable cells | clean | violations |
|---|---|---|---|
| 0 | 185 | 164 | **21** |
| 1 | 494 | 494 | 0 |
| 3 | 494 | 494 | 0 |

1173 testable cells total; 988 at w ≥ 1.  This reproduces
`docs/notes/biu_rebuild_P1.md:98-103` exactly.

**The dispute is therefore about the VERDICT RULE, not the data.**
`sw/b4_closure_v2.py:26-27` pre-registers: *"VERDICT: GO iff 0 testable-cell
violations. Any violation ⇒ NO-GO (routes to the user per the plan).
CONSTANT/CLEAN-PARITY counting is NOT used as the verdict."*  `w` is INSIDE
the match key (line 11-13) and there is no w0 carve-out anywhere in the
pre-registration, even though two other exemptions (non-EU `eu_ord = -1`, and
untestable cells) ARE carved out explicitly in the same block.  The
pre-registration was committed at 21:26:02 and the data run at 21:29:11 —
three minutes later — and the domain was then narrowed to w ≥ 1 in the
interpretive commit.  `docs/notes/biu_rebuild_P1.md:112-114` concedes this in
its own words: *"the literal all-w pre-registration fires on the 21 w0 cells"*.

**The physical excusal is principled; the verdict change is not.**  Design
§4a (`docs/notes/biu_rebuild_design.md:134-182`, dated **2026-07-14**, fourteen
days BEFORE the run) predicts the failure and names the exact violating cell in
advance: *"seed0 eu_ord0 has two phase-shifts (k1,k3) with identical
(phase-parity, occ=4, fill) but resume gap 4 vs 5"* — which is verbatim
`sw/b4_closure_v2.log:9`.  Its argument (the RTL reproduces w0 bit-exactly, so
the distinguishing state is MODELLED and not hidden) is genuine and
falsifiable.  What is post-hoc is changing the falsifier's DOMAIN after seeing
which cells fired, in the one exercise whose entire purpose was to install a
falsifier that could not be argued around.

**Two later objections that have nothing to do with w0** settle it.
`docs/notes/biu_eu_session_summary_2026-08-01.md:31-47`:

> - `sw/b4_closure_v2.py` defines any violation as a NO-GO, and its retained log reports 21 violations and NO-GO.
> - Its match key contains program `seed` and structural `eu_ord`, preventing distinct preparation histories from being compared as the same observable state.
> - It excludes 9,936 non-EU events.
> - Reclassifying `w0` failures using RTL knowledge shows that additional state exists, but does not prove that `(phase, occupancy, fill)` is sufficient.
>
> Accordingly, the reported `w1/w3 0/988` result is treated only as
> within-history repeatability.

With `seed` and `eu_ord` in the match key the test never compares two DIFFERENT
preparation histories, so `0/988` measures repeatability within one program
trace — not state sufficiency — regardless of what one does about w0.

**VERDICT (this ledger, 2026-08-01): B4 closure is NOT ESTABLISHED.  Treat
`B4 = GO` as RETRACTED.**  The defensible residual claim, and the only one this
campaign may cite, is: *within-history phase-parity repeatability holds 988/988
at w1/w3 on EU-preceded resumes.*  `(grid_phase, occ, fill)` may NOT be assumed
to close the machine; per the architecture plan the resume state is keyed on
the full grid state and — per the simplicity principle — the T2 objective is to
collapse it into a mechanism rather than to tabulate it.

**ERRATUM notice (no historical doc edited).**  The following artifacts still
assert `B4 = GO` and are STALE as of the 2026-08-01 audit.  They are historical
records of the retired campaign and are deliberately left untouched:

* `docs/notes/biu_rebuild_P1.md:90` (§6 header) — undercut by its own line 112.
* `docs/notes/biu_rebuild_state.md:50`, `:334`, `:484-488`.
* the biu-rebuild campaign memory file (`B4 exp_resume closure = GO` / `GO
  stands`), which was updated on 2026-08-01 at 11:11 — two hours AFTER the
  audit — without amending the B4 claim.  Highest-priority stale artifact,
  since it is what a future session loads first.

`docs/notes/biu_blackbox_campaign.md:3` is **NOT** an erratum: it is the
current governing statement.

### 0.2 Board scope at T0

None.  T0 is offline by construction; no socket capture, no FPGA flashing.

---

## 1. Architecture — the policy split

### 1.1 `CpuT<Bus>` / `loader_decode<Bus>` — **(refactor, zero behaviour change)**

The interpreter body moved from `sim/exec.cpp` to `sim/exec_impl.h` as
`template <class Bus> class CpuT`, and the pre-decode hardware from
`sim/loader.cpp` to `sim/loader_impl.h` as
`template <class Bus> LoadResult loader_decode(Machine&, Bus&)`.  Two
instantiations exist:

* `sim/exec.cpp` — `template class CpuT<Biu>;`, aliased `using Cpu = CpuT<Biu>;`
  in `sim/exec.h`.  The FUNCTIONAL model.  `sim/biu.{h,cpp}` is untouched.
* `sim/exec_timed.cpp` — `template class CpuT<BiuTimed>;`, aliased
  `using CpuTimed = CpuT<BiuTimed>;`.  The TIMED model.

`sim/exec.h` and `sim/loader.h` carry explicit-instantiation DECLARATIONS
(`extern template`).  That is what makes the split codegen-preserving rather
than merely behaviour-preserving: no translation unit that merely *uses* `Cpu`
instantiates the interpreter for itself, so `case_runner.o` and
`image_runner.o` still hold nothing but undefined references to the single
out-of-line copy in `exec.o` — verified with `nm -C`:

```
case_runner.o:   U sim::CpuT<sim::Biu>::step()
case_runner.o:   U sim::CpuT<sim::Biu>::interrupt(...)
exec.o:          U sim::LoadResult sim::loader_decode<sim::Biu>(...)
loader.o:        W sim::LoadResult sim::loader_decode<sim::Biu>(...)
```

**The Bus concept** (the entire surface the interpreter and the loader need):

```
uint8_t  next_byte(uint16_t cs, uint16_t upc)
uint16_t mem_read (uint16_t seg_val, uint16_t off, bool word, uint8_t seg_idx, uint16_t upc)
void     mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word, uint8_t seg_idx, uint16_t upc)
uint16_t io_read  (uint16_t port, bool word, uint16_t upc)
void     io_write (uint16_t port, uint16_t data, bool word, uint16_t upc)
uint16_t inta_read(uint16_t upc)
void     susp();  void flush(uint16_t pc);  void clear_consumed()
long     ev_count() const
```

Ten calls.  That the whole EU/BIU interface is ten calls is itself the reason
the split is cheap, and it is why the timed model can be swapped in without
touching one line of micro-sequencing.

**GATE (measured, this machine, 2026-08-01):**

| gate | before | after |
|---|---|---|
| `sw/ucsim_check.py --suite tests/v30/v0.1` | 169000/169000 | 169000/169000 |
| ... wall time, 3 runs | 17.62 / 17.76 / 17.89 s (mean 17.76) | 17.76 / 17.70 / 17.74 s (mean 17.73) |
| `sw/ucsim_check.py --suite tests/v30/v0.2` | 347000/347000, 38.06 s | 347000/347000, 38.71 s then 37.53 s |
| `make -C sim test` (disasm) | PASS | PASS |
| `sw/pla3_check.py` | OK (21 checks) | OK (21 checks) |

v0.1 mean delta = **−0.03 s (−0.2 %)**, inside the 0.27 s spread of the
before-runs.  A later clean-build re-run of the same gate came in at 17.44 s
and v0.2 at 37.53 s, i.e. both suites straddle their pre-refactor times in both
directions — the difference is measurement noise, not a trend.  Zero functional
regression, no measurable perf change.

---

## 2. The naive timed BIU (`sim/biu_timed.{h,cpp}`)

`BiuTimed` implements the same Bus concept and owns a CPU clock.  It COMPOSES a
functional `Biu core_` for the 1 MB epoch-stamped memory, the transaction log,
the write stream and `ev_count()`, and owns only what timing changes: the
prefetch queue and the fetch pointer (a timed fetch is a real word-wide bus
cycle; the functional core fetches one byte at a time on demand).

### 2.1 Bus-cycle shape `T1 T2 T3 [Tw×N] T4` — **MEASURED**

*Evidence:* `tests/v30/v0.1` cycle rows (T-state column), at three wait levels
(`v0.1`, `v0.1-w1`, `v0.1-w3`).

### 2.2 Status is a REGISTERED output, driven ONE clock early — **MEASURED**

The clock immediately before a cycle's T1 already carries that cycle's BS and
its address on AD/PS.  This is the v0.1 README's column-7 note ("the V30
asserts the next cycle's status during T4") stated as a mechanism rather than
as a T4 special case, and the mechanism form is what the goldens actually show:

* `v0.1/B8` case 0 rows 2-3: `T4 CODE 0EBE16` → `T1 CODE 0EBE16` — the T4 row
  carries the NEXT cycle's status AND its address.
* `v0.1/8A` case 0 rows 7-9: `Ti PASV` → `Ti MEMR 5DE73` → `T1 MEMR 5DE73` —
  after an idle gap it is an IDLE row, not a T4 row, that carries the early
  status.  A "T4 shows the next status" rule cannot express this; "one clock
  early, whatever that clock is" can.

*Implementation:* a ONE-CLOCK DELAY BUFFER (`BiuTimed::emit`).  The row for
clock N is handed to the sink only once clock N+1 exists, so committing a cycle
patches its status and address into the row still in flight.  No look-ahead
into the EU is used; the mechanism is exactly a registered output.

*Falsifier:* any golden row where the clock before T1 does not carry the
upcoming BS, or where a clock two before T1 carries it.

### 2.3 Status goes passive after the last data clock — **MEASURED, mechanism OPEN**

Measured on `B8` case 0 at three wait levels:

| waits | active clocks | first passive clock |
|---|---|---|
| 0 | T1, T2 | T3 (cycle-relative index 2) |
| 1 | T1, T2, T3, Tw | T4 (index 4) |
| 3 | T1, T2, T3, Tw, Tw, Tw | T4 (index 6) |

Implemented as `passive_at = (waits == 0) ? 2 : 3 + waits`.

**OPEN QUESTION (T1).**  That conditional is a special case, and by this
campaign's own rule a special case is a signal that two simple machines are
interacting and we have only seen the envelope.  The w0 / w>0 discontinuity is
almost certainly a READY-sampling instant interacting with the T-state
annotation the harness FSM applies, not two different behaviours of the part.
Do not promote this to a LAW until the single mechanism is found.

*Corollary already visible:* combining 2.2 and 2.3, PASV occupies exactly the
clock two before the next T1 and the early status the clock one before, at all
three wait levels — a cleaner statement that may be the real law.

### 2.4 AD phasing — **MEASURED**

* T1: the address-phase (mid-cycle) sample is the address.  The end-of-cycle
  sample is the address too, EXCEPT on a WRITE, where the CPU has already
  switched AD to the write data by the end of T1.  *Evidence:* `v0.1/88` case 0
  row 15 — `MEMW T1`, address `6E259`, data `3F40`.  (This is the same fact
  `sw/check_core.py::diff_rows` records in its col6 comment.)
* T2 through Tw: the data phase, and PS carries S6:S3.
* T4 / Ti: retention of whatever was last driven, unless patched by 2.2.
  *Evidence:* `v0.1/88` case 0 rows 17-19 hold `3F40` through T3, T4, Ti.

### 2.5 PS = S6:S3 = `0 | IE | segment(2)` — **MEASURED**

Segment codes on the pins are ES=0, SS=1, CS=2, DS=3 (note: NOT the same order
as `sim::Sreg`, which is ES,CS,SS,DS — the timed model maps between them).
S5 = the IE flag, read live from the interpreter's PSW (`BiuTimed::bind_psw`).
S6 = 0.

*Evidence:* `v0.1/B8` case 0 `ps=6` = IE|CS with IE set; `v0.1/8A` case 0 row 10
`ps=1` = SS with IE clear; `v0.1/88` case 0 row 16 `ps=5` = IE|SS.

I/O cycles drive the "no segment" code, which is the same encoding as CS —
**MEASURED**, `v0.1/E4` case 0 row 8 (`IOR T2`, `ps=6`).

The internal INT routine's segment-less vector fetch (`kSegZero`) is
**ASSUMPTION**: same "no segment" code.  *Falsifier:* the PS column on the
vector-fetch rows of any `INT.*` golden.

### 2.6 Undriven byte lanes retain — **MEASURED**

A transfer that drives only one lane leaves the other at its previous value.
*Evidence:* `v0.1/8A` case 0 row 10 — an odd-address BYTE read shows the
fetched byte `EC` on AD15-8 beside the stale `90` on AD7-0.

### 2.7 Fetch width and alignment — **MEASURED**

Word fetch from an even address; a single BYTE fetch when the fetch pointer is
odd (the state a flush to an odd PC leaves behind), on the high lane.
*Evidence:* `v0.1/B8` case 0 — CS:IP = `EBE13`, and the golden's fetch stream is
`EBE13` (byte, pre-window) then `EBE14`, `EBE16`, `EBE18` (words).

### 2.8 QS = F on the first pop after an instruction boundary or a flush — **ASSUMPTION**

`Cpu::step()` calls `clear_consumed()` at every instruction boundary and
`kIctlFlush` calls `flush()`; both arm "the next pop is an F".  All other pops
are S.

*Known WRONG for prefixed forms:* the chip emits F for each prefix byte AND for
the opcode after the prefixes (`sw/check_core.py::n_prefix`), so a prefixed
case gets F,S where the golden has F,F.  Consequence: `build_rows_sim` cannot
close the window on a prefixed case, because it needs `n_fpops(golden)` F pops.
*Falsifier / fix:* any prefixed form in the row gate.  **T1.**

---

## 3. SCAFFOLDING — the T0 simplifications, each with its replacement stage

Every entry here is KNOWN wrong and exists only so the next stage has something
to replace.  None of them may be cited as a law.

**S9a UPDATE (2026-08-02, §19):** S9's SINGLE-INSTRUCTION half is **REMOVED** —
`timed-run` executes all thirteen pin-event forms cycle-exactly and the w0
denominator is the full 169,000.  What remains of S9 is `timed-boot`'s missing
event replay (the fuzz bank's 1,165 `EVT` seeds) and the interrupt/INTA WAIT
AXIS, which has no oracle.

**T1 UPDATE:** S1, S2, S3, S4 and S10 are **REMOVED** (replaced by the
mechanisms in §7.1-§7.8).  S5 is **partly removed** — the write cycle is now
scheduled by the BIU at a grid slot, but the write-data pairing latch is still
the interpreter's.  S6 (uniform waits), S7 (no arbitration reservations), S8
(no flush/BUSLOCK/HALT timing) and S9 (no interrupt/INTA timing) STAND.

| # | scaffolding | why it is wrong | replaced by |
|---|---|---|---|
| S1 | **Strictly serial bus.** One bus cycle at a time; the EU is not a client of the clock, so its actions serialise with the bus instead of overlapping it. | The chip overlaps EU work with bus cycles; a queue pop is a point sample riding an existing bus clock, not a clock of its own. | T1 (BIU master clock, EU as client) |
| S2 | **No prefetch scheduler.** The queue is demand-filled: a fetch is issued only when the decoder asks for a byte the queue does not have. | The chip fetches ahead on a scheduler; the goldens show back-to-back CODE cycles with the queue still holding bytes. | T1 (fetch-scheduler decision at eval points) |
| S3 | **No queue push/pop latency.** A fetched byte is poppable the instant its cycle ends; a pop is instantaneous. | Measured law: push lands at eval+1, poppable at push+2, plus the fresh-on-T2 rule. | T1 (queue latency pipeline) |
| S4 | **No micro-row cadence.** A micro-row costs zero clocks; only bus cycles, queue pops and flushes advance the clock. | `docs/facts/timing_measured.json` holds 306 F-spacing retirement measurements; the ROM's own row cadence is real time. | T1 (cadence calibration ratchet) |
| S5 | **No push/write latency, no write pairing delay.** `emit_pending` issues the write cycle at the moment the interpreter pairs the data. | The chip's write cycle is scheduled by the BIU, not issued by the EU. | T1/T2 |
| S6 | **Uniform waits only.** `--waits N` applies N wait states to every cycle. | The wait axis needs per-access wait vectors and the `wrand` Galois-LFSR generator (`docs/notes/random_wait_rig.md`). | T2 (wait axis) |
| S7 | **No arbitration / maturity model.** Fetch and data accesses never contend, because they cannot overlap (S1). | The whole chip-oracle-v2..v7 corpus is about that contention. | T1 (arbitration rules A/B) |
| S8 | **No flush timing, no BUSLOCK, no HALT display.** `flush()` costs exactly one clock and emits a QS=E point sample; `lock_n` is hardwired inactive. | Measured flush law + NEAR +1-late; BUSLOCK and HALT have their own display rules. | T1 (flush/BUSLOCK/HALT) |
| S9 | **No interrupt/INTA timing.** `timed-run` runs instructions only; the pin-event replay that `case_runner` performs is not implemented in the timed path, so `INT.* / NMI.* / HLT.* / POLL.*` pseudo-forms have no timed arch result. | Scope exclusion inherited from the RTL campaign: interrupt/INTA timing under waits stays OUT of every timed gate until measured. | **S9a (§19): the single-instruction half is REMOVED — 2,600 / 2,600 cycle-exact at w0.**  `timed-boot`'s event replay (S9b) and the wait axis stand. |
| S10 | **Instruction-boundary QS=F rule.** See 2.8. | Prefixes each pop an F. | T1 |

---

## 4. Row emission (`sim/rows.{h,cpp}`)

One `ClockRow` per CPU clock, carrying the RAW pin sample set — deliberately
not a synthesized 11-column row.  The golden 11-column `cycles` rows are
DERIVED from these by `sw/check_core.py::build_rows_sim`, and the fuzz /
black-box replay tooling consumes the same raw records
(`sw/check_seq.py::run_image`).  Emitting raw records and letting the
UNMODIFIED python machinery synthesize is what makes the cycle gate cost zero
new comparison code.

* **Emitter (a) `TextRowEmitter`** — `sw/check_core.py::parse_out`'s textual
  format (`= <idx>` / `r <t> <bs> <qs> <ube_n> <ad_addr> <ad_data> <ps> <lock>`
  / `f <14 regs>` / `.`).  Field order, radix and widths are fixed by
  `check_core.py:219` and match `hdl/tb/tb_v30_core.sv:327` exactly; the
  trailing BUSLOCK_N field is emitted for TB parity and ignored by `parse_out`.
* **Emitter (b) `ChipRowsEmitter`** — chip_rows NDJSON, one object per clock,
  keys as `sw/check_seq.py::run_image` builds them (`t`, `bs_early`, `qs`,
  `ube_n`, `ad_addr`, `ad_data`, `ps`) plus `clk` and `upc`.

`upc` attribution is carried on every row: the ROM row that issued the access,
which the functional model already tracked per transaction.  Row-level
attribution therefore comes free.

---

## 5. Gates

### 5.1 T0 gate commands (runnable, as recorded)

```
make -C sim                                                   # builds both modes
make -C sim test                                              # disasm gate
python3 sw/pla3_check.py                                      # PLA gate
python3 sw/ucsim_check.py --suite tests/v30/v0.1              # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2              # 347000/347000
python3 sw/timed_gate.py --suite tests/v30/v0.2 \
        --forms 88,00,50,C8                                   # arch through the TIMED path
python3 sw/timed_gate.py --sbs B8:0                           # the hand side-by-side
```

### 5.1a T1 gate commands (runnable, as recorded)

```
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all   # THE CYCLE RATCHET
python3 sw/ucsim_check.py --suite tests/v30/v0.3              # mass functional sweep
python3 sw/ucsim_check.py --suite tests/v30/v20suite          # V20 arch oracle
python3 sw/timed_gate.py --sbs 50:1                           # split-word write (M5)
python3 sw/timed_gate.py --sbs B8:1                           # idle-slot eval (M1)
```

### 5.2 T0 results

* **Arch through the timed path:** `tests/v30/v0.2` forms 88, 00, 50, C8,
  1000 cases each = **4000/4000 exact**.  The architectural answer survives the
  swap of the bus policy, which is the T0 claim.
* **Row stream format:** `build_rows_sim` accepted the stream and located the
  golden window in **4000/4000** cases.  Zero parse or synthesis errors.
* **Rows exact:** 0/4000, as expected and pre-stated — there is no timing model
  yet.  Baseline row-diff total 321,961 over 4000 cases, by column:
  `bus 53268, data 51249, tstate 49938, busstat 43771, ube 29288, memcmd 23814,
  seg 23038, pins 21819, qbyte 11375, qop 10596, len 3805`.  This is the
  number T1 ratchets down; it may only ever decrease.

**Full-suite T0 baseline** (`sw/timed_gate.py --suite tests/v30/v0.1 --forms
all`, 169,000 cases, ~40 s).  Recorded so T1 has a complete starting point; not
a gate:

| metric | T0 |
|---|---|
| arch exact | 166,800 / 169,000 |
| golden window located | 152,063 / 169,000 |
| rows exact | 0 / 169,000 |
| row diffs | 9,164,377 |

Both shortfalls are exactly the scaffolding entries this ledger names, with
nothing left over:

* **2,200 arch failures = the 11 pin-event pseudo-forms** at 200 cases each
  (`INT.90 INT.B8 INT.8ED0 INT.8ED8 INT.FB INT.9D INT.F3AA NMI.90 NMI.B8
  HLT.INT HLT.NMI`).  `timed-run` executes instructions only — scaffolding
  **S9**.  The pin-event forms that do NOT fire (`IE0.90`, `HLT.RES`,
  `POLL.LO`, `POLL.REL`) pass.  All 339 other forms are 100 % arch exact.
* **16,937 windows not located** = 15,500 from the 31 PREFIXED forms
  (`26.* 2E.* 36.* 3E.* 64** 65** F2** F3**`, all 500/500) — scaffolding
  **S10** / §2.8, one missing F pop per prefix byte — plus 1,437 from the
  pin-event forms.

Column histogram: `bus 1452888, data 1450343, tstate 1403809, busstat 1197903,
ube 870100, seg 630695, memcmd 613401, pins 557269, qbyte 428085, qop 409346,
len 143977, iocmd 6561`.

**Wait-state path exercised** (`--suite tests/v30/v0.1-w1 --waits 1`, all six
forms, 1200 cases): arch 1200/1200 exact, window 1200/1200, rows exact 0,
row diffs 97,290.  Confirms the §2.3 wait behaviour is wired (status stays
active through T3/Tw at w1 and drops at T4) even though the cycle stream is
still the naive serial one.

**Emitter (b) exercised:** `timed-run --ndjson` produces one well-formed JSON
object per clock plus a finals object; all records parse.

### 5.3 The hand-verified case — `v0.1/B8` case 0, w0

`mov ax, 1580h`, CS:IP = `EBE13`, injected queue empty.  Golden 9 rows, sim 12.

```
#   | GOLDEN                                | SIM (T0 naive)
    | T    stat  bus    seg data   q  qb    | T    stat  bus    seg data   q  qb
 0 *| T2   CODE  061580 CS  1580   F  B8    | Ti   CODE  0EBE14 --  BE14   F  B8
 1 *| T3   PASV  061580 --  1580   -  00    | T1   CODE  0EBE14 --  BE14   -  00
 2 *| T4   CODE  0EBE16 --  BE16   -  00    | T2   CODE  061580 CS  1580   -  00
 3 *| T1   CODE  0EBE16 --  BE16   -  00    | T3   PASV  061580 --  1580   -  00
 4 *| T2   CODE  069090 CS  9090   S  80    | T4   PASV  061580 --  1580   -  00
 5 *| T3   PASV  069090 --  9090   S  15    | Ti   PASV  061580 --  1580   S  80
 6 *| T4   CODE  0EBE18 --  BE18   -  00    | Ti   CODE  0EBE16 --  BE16   S  15
 7  | T1   CODE  0EBE18 --  BE18   -  00    | T1   CODE  0EBE16 --  BE16   -  00
 8 *| T2   CODE  069090 CS  9090   F  90    | T2   CODE  069090 CS  9090   -  00
 9 *| -                                     | T3   PASV  069090 --  9090   -  00
10 *| -                                     | T4   PASV  069090 --  9090   -  00
11 *| -                                     | Ti   PASV  069090 --  9090   F  90
```

**What already lines up (and therefore needs no work in T1):**

1. **The cycle shape and the pin composition are right.** Sim rows 2-3 are
   byte-identical to golden rows 0-1: `T2 CODE 061580 CS 1580` /
   `T3 PASV 061580 -- 1580`.  Composed bus value, PS→segment decode with the IE
   bit, PASV-at-T3, and the data phase are all correct.
2. **The registered-status handover (§2.2) works.** Sim row 0 is an idle pop
   clock that already carries `CODE 0EBE14`, and sim row 6 carries
   `CODE 0EBE16` — the same one-clock-early mechanism the golden shows at rows
   2 and 6.  The general mechanism was written, not the T4 special case, and it
   fires on a Ti row here exactly as it does on the chip in `8A`.
3. **Fetch addresses, widths and alignment are right**, and the queue byte
   stream is right and in the right ORDER: `B8, 80, 15, 90` on both sides.
4. **The architectural answer is exact** (AX = `1580`, IP = `8556`).
5. **Sim row 7 matches golden row 7 outright** — the one unmarked row.

**What the naive model gets wrong (the T1 work list, in priority order):**

1. **No prefetch scheduler (S2) — the dominant error.** The golden runs code
   fetches back-to-back with zero idle clocks: golden rows 2→3 are T4→T1 of
   consecutive fetches, and the second fetch is issued while the queue STILL
   HOLDS BYTES.  The sim issues a fetch only when the queue runs dry, so
   sim rows 4→7 are T4, Ti, Ti, T1.  Queue occupancy currently decides nothing.
2. **A queue pop costs a whole clock (S1).** Sim rows 0, 5, 6 and 11 are idle
   clocks whose only content is the pop.  On the chip the pop is a point sample
   riding an existing bus clock — golden row 0 is `F` on a T2, row 4 is `S` on
   a T2, row 5 is `S` on a T3.  This is the EU/BIU overlap, and it is the same
   root cause as (1): the EU is not yet a client of the clock.
3. **Consequence of (1)+(2): the stream is 12 rows against the golden's 9**, so
   after row 0 everything is phase-shifted and nearly every column reports a
   diff.  The 45 mismatches on this case are almost entirely alignment, not
   independent errors — which is why the T1 ratchet should be judged on
   `rows_exact`, not on the raw diff total.
4. **T4 shows PASV where the golden shows the next cycle** (sim rows 4 and 10).
   Not a separate bug: the handover can only fire once the EU has asked for the
   next access, and with a scheduler (1) that request would already exist.
5. **The chip overlaps the pop with the in-flight fetch.**  The golden's window
   OPENS with the `B8` pop happening during T2 of the ALREADY-RUNNING fetch of
   `EBE14`; the sim performs the same two events in the same order but
   serialises them.  T1 needs a defined pre-window priming convention so the
   first window row lands on the same clock on both sides.

Nothing in this list is a surprise, and nothing in it contradicts a measured
law — every item is one of the S1-S4 scaffolding entries showing up in the
place the ledger predicted it would.

### 5.4 Standing regressions

The functional gates in 5.1 are standing: every ucsim-t commit keeps them
green, and the functional mode must not regress in behaviour or in measurable
performance.

---

## 6. Open items entering T1

1. **§2.3 mechanism.**  Find the single machine behind the `w == 0 ? 2 : 3+w`
   passive-clock conditional.  Suspect: a READY-sampling instant interacting
   with the harness FSM's T-state labels.  Do not tabulate.
2. **Prefix QS=F rule (§2.8 / S10).**  Blocks the row gate on every prefixed
   form.
3. **Pre-window priming convention.**  Define where the sim's record stream has
   to start so that the golden's window-opening F pop lands on the same clock.
4. **Ratchet definition.**  T1's exact-case counter is `rows_exact` from
   `sw/timed_gate.py`; the pre-registered rule is that it may only grow and
   that the functional gates re-run at every step.
5. **`kSegZero` PS code (§2.5)** is still an ASSUMPTION; the `INT.*` goldens can
   settle it offline.
6. **Inherited oracles are not yet replayed.**  None of the 104 frozen
   black-box JSONs, the `case250` INS factorials, or the INS/ENTER pilot planes
   are wired to the sim yet; those are T1 (L1 unit gates) and T2 (L2 image
   replay).

---

## 7. T1 — the w0 timing core

T1 replaced the T0 scaffolding S1, S2, S3, S4, S5 and S10 with mechanisms.  The
BIU now owns the clock and the EU is a CLIENT of it: `sim/biu_timed.{h,cpp}` is
a per-clock FSM, and `CpuT<Bus>` / `loader_decode<Bus>` carry the cadence call
sites (`charge`, `wait_read`, `opcode_prefetch`, `prefix_retire`) in ONE body
shared by both instantiations — on the functional `sim::Biu` every one of them
is an empty inline, so the functional model is untouched (gates in §7.10).

**T1 IS NOT CLOSED.**  The stage exit (v0.1 166,800/166,800 cycle-row exact at
w0) is not met, and neither is Milestone A (the six mission-H fitted forms at
w0 + w1/w3) or Milestone B (the 35-opcode bring-up tranche): of the six
Milestone-A forms only `B8` is exact.  What T1 delivers is the CORE — the
clock, the grid, the queue pipeline, the scheduler and the cadence — plus a
ratchet that moved 0 -> 50,207 and a survey (§7.11) that maps every remaining
case to a named missing mechanism.

Everything below is a MECHANISM, not a table.  The only tabulated thing in the
whole stage is the decoder's five-row byte-demand schedule (§7.6), and its
irreducibility is flagged as an open question, not claimed.  There is no
per-opcode timing exception anywhere in `sim/` — grep for one.

### 7.1 M1 — grid geometry and the completion eval — **MEASURED**

A bus cycle is `T1 T2 T3 (Tw x N) T4`.  The next cycle is chosen at a
COMPLETION EVAL; the winner's status and address are driven on the clock AFTER
the eval (the DISPLAY clock) and its T1 opens the clock after that:

```
    eval at end of clock c   ->   status/address displayed on c+1   ->   T1 on c+2
```

Eval points at w0: the **end of T3** of a zero-wait cycle, and the **end of
every idle clock**.  T4 is NOT an eval point.  (Under waits the eval moves to
the end of T4 — the mission-H deferral — which is why the same three-clock
relation still produces T1 at T4+2.)

*Evidence (both directions of the rule, from one case each):*

* `v0.1/B8` case 0 (queue injected EMPTY, so every cycle is a fetch): the eval
  at the end of fetch#2's T3 puts fetch#3's status on fetch#2's T4 and its T1
  on the next clock — golden rows 1-3 `T3 PASV / T4 CODE 0EBE16 / T1 CODE
  0EBE16`.  Back-to-back CODE with no idle clock between them.
* `v0.1/B8` case 1 (queue injected FULL at 5): clock 0 is an IDLE clock whose
  only content is the opcode pop; that pop drops occupancy to 4, the eval at
  the END of clock 0 fires, the status appears on clock 1 (still an idle clock)
  and T1 opens on clock 2 — golden rows 0-2 `Ti PASV (F pop) / Ti CODE 0C91CE /
  T1 CODE 0C91CE`.  Same rule, idle instead of T3.

*Falsifier:* any golden where a committed cycle's T1 is not exactly two clocks
after the eval that could have chosen it, or where a status appears on the eval
clock itself.

### 7.2 M2 — the status register, and the death of `w == 0 ? 2 : 3+w`

**T0 open item 1 is RESOLVED, and the answer is that there was never a
conditional.**  The status output is a REGISTER: it is LOADED at the eval (M1)
and RELEASED exactly one clock before the next display clock.  So every bus
cycle is followed by exactly ONE passive clock, and where that clock falls is a
consequence of the eval geometry, not of the wait count:

| waits | eval at | display | T1 | the one PASV clock |
|---|---|---|---|---|
| 0 | end of T3 | T4 | T4+1 | **T3** (= 2 before the display) |
| 1 | end of T4 | T4+1 | T4+2 | **T4** |
| 3 | end of T4 | T4+1 | T4+2 | **T4** |

The implementation still writes `passive_i = (waits_ == 0) ? 2 : 3 + waits_`,
but that expression is now a *derived index*, not a law: it is "one clock
before the display clock" evaluated for the two eval geometries M1 already
carries.  The T0 ledger's own corollary — *"PASV occupies exactly the clock two
before the next T1 and the early status the clock one before, at all three wait
levels"* — is the same statement, and it now falls out of the mechanism.

*Why the two simple machines produce the envelope:* the 8086-family datasheet
rule ("status returns passive during T3, or during Tw when READY is HIGH") is
about the READY sampling instant; the harness's wait generator raises READY so
that the CPU's ready-high sample lands at the end of T2 at w0 and at the end of
the last Tw at w>0.  One register + one sampling instant = the apparent
conditional.  **Not promoted to a LAW beyond w0** — T2 owns the wait axis and
must re-derive the release point from the READY sample directly rather than
from the eval index.

### 7.3 M3 — queue geometry, push and pop latency — **MEASURED / LAW**

* 6 bytes; word fetch from an even address (+2), single upper-lane byte from an
  odd one (+1).  (biu_model.md exp 1; T0 §2.7.)
* A completed fetch PUSHES at the end of its T4 and the pushed byte becomes
  POPPABLE two clocks later (`ready = t4_clk + 2`).
* A pop is a POINT SAMPLE riding a clock that already exists — `next_byte()`
  sets the QS code for the clock the caller is about to charge, it never
  charges a clock of its own.  Scaffolding S1 and S3 are gone.

*Evidence:* `v0.1/B8` case 0 — fetch#1 (the odd-address byte at `EBE13`) ends
T4 on clock 3 and its byte is popped on clock 5, which is fetch#2's T2; the
word `80 15` pushed at fetch#2's T4 (clock 7) is popped on clocks 9 and 10.
Every pop in that case lands on the FIRST clock the two-clock latency allows,
which is what makes the case a pure push/pop-latency measurement.

### 7.4 M4 — the prefetch scheduler: the resume predicate's T1 form

**The resume predicate is an occupancy threshold evaluated at a grid slot, and
nothing else.**  At every eval point (M1), with no EU request pending and no
SUSP outstanding, a fetch is issued iff

```
    occupancy(queue) + bytes-in-flight  <=  4          (i.e. 2 bytes free)
```

where *bytes-in-flight* counts a fetch that has been committed or is running
but has not pushed yet.  That is the measured refill threshold (biu_model.md
exp 1) plus the in-flight accounting the threshold obviously needs; there is NO
table, no phase key, no fill-history, no `(phase, occ, fill)` tuple.

This is deliberately the SIMPLEST thing consistent with LC1/LC2, and it is
exactly the "first grid_phase-0 slot with queue occupancy <= 4" predictor that
`biu_model.md` measured at **97.9 % at w0**.  The w0 goldens are now the
discipline on it: whatever the residual 2 % is, it will show up as a form
family in the survey (§7.11) rather than as a fitted parameter.  **LC1's
"steady-state ~3-idle gap" and LC2's aged-band PAUSE are NOT implemented** —
neither is needed to reproduce anything measured so far at w0, and inventing
them before a w0 golden demands them would be exactly the fitted-table failure
mode the campaign is trying to avoid.  LC8 (pf_drain / mid-band pause) remains
DELETED and is not reimplemented.

*Falsifier for the whole predicate:* a w0 golden whose prefetch T1 lands on a
grid slot where occupancy was already > 4, or which skips a slot where it was
<= 4.  Such a case is a T2 discovery input, not a patch site.

### 7.5 M5 — a write drives the whole datapath value — **MEASURED**

On a WRITE the CPU drives AD15-0 with its internal 16-bit value and lets
UBE/A0 select which lane the memory latches; it does NOT compose a per-lane
value.  Both byte cycles of a SPLIT (unaligned) word write therefore show the
same full word.  *Evidence:* `v0.1/50` case 1 (`PUSH AX` at an ODD SP) drives
`0BCD` on BOTH halves.  READS keep the retention rule (T0 §2.6): there the CPU
floats AD and the system drives, so the undriven lane holds its last value.

### 7.6 The decoder's byte-demand schedule — **MEASURED (small table, mechanism OPEN)**

Relative to the opcode pop at clock 0, with a saturated queue:

| class | byte pops | first micro-row |
|---|---|---|
| no ModR/M | — | 2 |
| mod 3 | modrm @1 | 2 |
| mod != 3, no disp | modrm @1 | 3 |
| disp8 | modrm @1, disp @3 | 4 |
| disp16 | modrm @1, disp-lo @2, disp-hi @4 | 5 |
| `0F` escape | 0F @0 (F), opcode2 @2 (S), then as above shifted by 2 | |

Derived from the v0.1 saturated-queue goldens across 88/8A/89/8B/00/01/80.0/
81.0/83.0/C6.0/C7.0/0F10 and **independently identical to the frozen oracles**
`decoder-displacement-oracle-v1` (disp8 `[(1,F),(2,S),(4,S)]`, disp16
`[(1,F),(2,S),(3,S)]`) and `decoder-multibyte-oracle-v1` (`imm16`
`[(1,F),(3,S),(4,S),(5,F)]` = B8's `0,2,3,4`; `modrm_reg` gap 4 = the mod3
spacing of 3; `test_reg` gap 4 = TEST reg,reg at 2).

**OPEN (mechanism).**  Five rows is small, but two of them are still just
numbers: why disp8 pops at 3 while disp16 pops its LOW byte at 2 and skips
clock 3, and why a mem form with no displacement still costs one clock more
than mod 3.  The shape smells like a two-clock EA stage whose second clock is
the adder pass, with the displacement pops hung off its ends — but that is a
hypothesis, not a law, and it is not encoded as one.  **Do not grow this table
per opcode.**  If a new form needs a sixth row, that is the signal that the EA
stage needs to be modelled as the machine it is.

### 7.7 The micro-row cadence, and the max-of-two-deadlines retire

* **One ROM row = one CPU clock.**
* **A taken micro-JMP costs one more** (the sequencer's redirect bubble).
  *Evidence:* `04` (ADD AL,imm8) and `B8` (MOV AW,imm16) share the row `Q ->
  tmp / JMP OP8 2` and both retire in 4 clocks, yet `04` executes THREE rows
  and `B8` FOUR.  The difference is exactly that `04` takes the OP8 jump and
  `B8` does not.  This is the whole cadence model — there is no per-opcode
  cost anywhere in the sim.
* **An `R` (iterative-ALU) row costs one clock per iteration** on top of its
  own.  PROVISIONAL: the shift/rotate families are not yet exact (§7.11 C2), so
  this is the starting point, not a fitted result.
* **The successor's opcode pop rides the E row's own clock.**  Every saturated
  golden puts the closing F pop exactly two clocks before the successor's first
  micro-row, and the E row is two rows before that row; so the decoder pops the
  next opcode while the E row and the post-E row are still executing, and those
  two rows are charged by the successor's decode rather than by their own
  instruction.
* **...but an instruction does not retire until its bus work is done.**  The
  pop is the LATER of the E-row clock and `eu_done` (the completion of the
  instruction's last EU access, T4+1 at w0) — including a write still STAGED in
  the write-data-pairing latch, which has not reached the bus at all yet.
  *Evidence:* `88` mod0 (`mov byte [bx+si], al`) — the closing F lands on the
  MEMW's T4+1, ten clocks after the opcode pop, not on the E row; `50` (`PUSH
  AX`) — the closing F lands after the SECOND half of the split stack write.
  This is the campaign's own "max-of-two-deadlines" shape: one march (the row
  engine) and one interlock (the bus), and the retire is their max.

### 7.8 Prefix F pops — **S10 REMOVED**

Each prefix byte retires as its own 2-clock instruction with its OWN F pop
(`measurements.md`, "prefix retires as its own instruction (own F pop, 2
cycles)"); the `0F` escape is the same 2-clock re-decode but its second byte is
an **S**, because `0F` is not one of `check_core::PREFIXES`.  Consequence: the
golden window now closes on prefixed forms.  All 31 prefixed forms (15,500
cases) went from "window not located" to located.

### 7.9 Pre-window priming convention — **T0 open item 3, SETTLED**


`begin_case()` starts the bus IDLE with the queue preloaded from
`initial.queue` and `fetch_ptr = ip + len(queue)`, and clock 0 is the first
clock on which the EU runs.  Nothing else is injected.  The convention works
because `build_rows_sim` locates the window at the FIRST F pop, so only the
geometry from that pop onward has to match — and it does, in both regimes:

* queue EMPTY: the sim's first two fetches are issued from the idle-slot eval
  and the T3 eval respectively, so the opening F pop lands on the second
  fetch's T2, exactly as in the golden.
* queue FULL (5 or 6): the opening F pop rides clock 0 and the eval at the end
  of that clock sees the post-pop occupancy — which is what makes `B8` case 1
  (occ 5, fetch commits immediately) and `04` case 1 (occ 6, fetch commits one
  pop later) differ by exactly the clock the goldens show.

v0.1 injects only occupancies 0, 5 and 6, so no partially-filled priming case
exists to settle.  A capture with occ 1-4 would need an in-flight-fetch
convention as well; recorded as a T2 input.

### 7.10 Gates, and the T1 ratchet curve

Standing functional regressions, re-run after every mechanism change
(all GREEN at the numbers below, unchanged from T0):

```
make -C sim test                                    # disasm gate: PASS
python3 sw/pla3_check.py                            # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1    # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2    # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3    # 3699998/3699998 (507 s)
```

**The full ~7.34M functional sweep is GREEN on the T1 binary**, zero
regressions:

| suite | result | time |
|---|---|---|
| v0.1 | 169,000 / 169,000 | 17 s |
| v0.2 | 347,000 / 347,000 | 38 s |
| v0.3 | 3,699,998 / 3,699,998 | 507 s |
| v20suite | 3,125,000 / 3,125,000 | 414 s |
| **total** | **7,340,998** | |

(`v0.3`'s 2-case shortfall against its nominal 3,700,000 is the documented
pre-existing exclusion, not a T1 effect.)

*One observation, NOT a T1 result:* `sw/ucsim_check.py --suite
tests/v30/mod3_illegal` returns `0/128 (0.0s)` — 128 cases in zero seconds
means the harness never ran them, so this reads as a suite/invocation mismatch
rather than a functional failure.  `mod3_illegal` is not part of the campaign's
standing gate set and was not part of the 7.34M above; it was run here only
opportunistically.  **Unverified either way — confirm against a pre-T1 binary
before treating it as anything.**

*Environment note, for whoever re-runs this:* the machine's `/tmp` tmpfs hit its
quota during T1 (`g++`: "error writing to /tmp/ccXXXX.s: Disk quota exceeded"),
which breaks builds and every `tempfile`-using harness.  Point `TMPDIR` at a
real filesystem (`export TMPDIR=~/.cache/ucsimt-tmp`) before building or running
`sw/timed_gate.py`.

The cycle ratchet (`sw/timed_gate.py --suite tests/v30/v0.1 --forms all`,
`rows_exact`, pre-registered to only ever GROW):

| step | rows exact | windows located | row diffs |
|---|---|---|---|
| T0 baseline (naive serial bus) | 0 | 152,063 | 9,164,377 |
| T1a grid + queue latency + scheduler + cadence + prefix F | 49,818 | 168,720 | 4,298,266 |
| T1b staged-write retire (§7.7) | 50,202 | 168,720 | 4,427,805 |
| T1c write drives the datapath value (M5) | **50,207** | 168,720 | 4,431,246 |

29.7 % of the suite (30.1 % of the 166,800 non-pin-event cases) is cycle-row
exact at w0.  The row-diff TOTAL grew between T1a and T1c while `rows_exact`
grew: that is expected and is why the pre-registered ratchet is `rows_exact`
and not the diff count — a window that used to close after 4 rows now closes
after 15, so a case that was "wrong in 3 cells" becomes "wrong in 11 cells"
while being strictly closer to the chip.

Arch through the timed path stays 166,800/169,000 — the 2,200 shortfall is
exactly the 11 pin-event pseudo-forms (scaffolding **S9**), unchanged.
Windows: 168,720/169,000; the 280 unlocated are pin-event forms only.

### 7.11 Survey-then-fix — where the remaining cases are

Of 347 forms: **47 are 100 % cycle-row exact**, 193 are partially exact, 107
are 0 %.  Categorised (no fix is per-opcode; every category names one missing
MECHANISM):

| # | category | forms | cases | missing mechanism |
|---|---|---|---|---|
| C1 | **flush / branch timing** | `EB E9 E8 EA 9A C8 CA CB CC CD CF FF.2-5` + the taken half of `74 75 7C E2` | ~10,000 | scaffolding **S8**: the measured flush law (redirect commit points, the flush-only prefetch-T4 eval, doomed-fetch completion, NEAR +1-late) |
| C2 | **`R`-row / shift-rotate cadence** | `C0.0-7 C1.0-7 D2.0-7 D3.0-7 D0.* D1.*` | ~16,000 | §7.7's one-clock-per-iteration is a guess; the measured law is 10+n (n>=1) / 9 (n=0) with shift-by-1 at 6 |
| C3 | **string / REP loop cadence** | `A4 A5 A6 A7 AC AD AE AF` + all 23 prefixed variants | ~15,500 | the string micro-loop's per-element grid interaction (measurements.md REP slopes 9+4n / 9+8n / 11+14n) |
| C4 | **byte-lane companion on writes** | every byte-store form (`88` byte, `C6.*`, byte RMW) | ~6,000 | §7.12 item 1 — the datapath truncation, not a bus law |
| C5 | **multi-access stack sequences** | `60 61 8F.0` | 1,500 | the inter-write march (`eu_wdone` chaining) that PUSHA/POPA use |
| C6 | **EU-burn cadence** | `F6.4-7 F7.4-7 69 6B 0F20 0F22 0F26` (MUL / DIV / BCD strings) | ~5,500 | the wait-insensitive compute burns are CPU-cycle counts the model does not carry yet (grid law 8) |
| C7 | **I/O cycles** | `E4 E5 EC ED EE EF` | ~3,000 | I/O request scheduling / IOR data timing |
| C8 | **pin-event forms** | `INT.* NMI.* HLT.*` (11 forms) | 2,200 | scaffolding **S9**, out of T1 scope by construction |

Nothing in that list is a per-case exception, and no category was "fixed" by a
special case: C1, C5, C6 and C7 are mechanisms that were never written, C2 and
C3 are cadences whose measured law is known but not yet expressed, C4 is an
architectural-model truncation, C8 is a declared exclusion.  The partially
exact forms are dominated by the mod3 / mem split (the register-operand cases
of a mem-capable form are exact, its memory cases are not) — which is C4 plus,
for the loads, the pre-decode read's request timing.

### 7.12 Open items entering T2

1. **The byte-lane companion.**  A byte write's UNDRIVEN lane carries the
   sibling register byte (`88`/`8A`) or the sign-extended imm8 (`C6`) —
   `measurements.md`, "Byte-store data lane law".  M5 (§7.5) is the right
   mechanism (the CPU drives its internal 16-bit value) but the *simulator's*
   internal value is truncated for byte sources, because `rd_operand` returns
   `m_.rb(idx)` for a byte register.  The physically true fix is to widen the
   byte-register read to the 16-bit pair and mask at the ALU / register
   writeback instead — an ARCHITECTURAL-model change, so it must ride the full
   7.3M functional sweep, not a timing-only gate.  Left undone deliberately.
2. **§7.6's EA stage.**  Replace the five-row demand table with the two-clock
   EA machine it is shadowing.
3. **`R`-row cadence.**  One clock per iteration is unvalidated; the shift /
   rotate families (`C0.*`, `C1.*`, `D0-D3`) are the discriminator.
4. **Flush / branch timing.**  `flush()` still just clears the queue, redirects
   the pointer and drops a QS=E point sample on the current clock; the measured
   flush law (redirect commit points, the flush-only prefetch-T4 eval, NEAR +1
   late, the doomed-fetch completion) is NOT implemented.  Scaffolding **S8**
   stands.
5. **BUSLOCK and HALT display.**  Not implemented; **S8** stands.
6. **Arbitration reservations (LC4 C9-C12).**  Not implemented — at w0 the eval
   sees requests live, which has been sufficient so far.  The store-vs-prefetch
   lead reservation is the first one a golden is likely to demand.
7. **Oracle replay adapters.**  The decoder-drain v2 / multibyte / prefix-phase
   schedules were used as CROSS-CHECKS on §7.6 by hand, but no `timed-scenario`
   L1 replay harness exists yet.  Still owed.
8. **`kSegZero` PS code** (T0 open 5) is still an ASSUMPTION.

---

## 8. T1 second pass — the datapath, the flush, and the two requesters

This section is the continuation of §7.  Nothing in §7 is retracted except
where an entry below says so explicitly.  The ratchet
(`sw/timed_gate.py --suite tests/v30/v0.1 --forms all`, `rows_exact`) moved

| step | rows exact | row diffs |
|---|---|---|
| §7 close (T1c) | 50,207 | 4,431,246 |
| M5b + rb16 — the byte-lane companion (C4) | 50,906 | 4,324,751 |
| F1/F2/F3 flush mechanisms + UBE-at-T1 + pre-window priming (C1) | 64,530 | 3,279,389 |
| the pre-decode OPR hand-over (T4+2) | 81,277 | 2,810,805 |
| the FARJMP redirect bubble (C2) | 95,408 | 2,552,934 |
| reads show the ALIGNED WORD + the rig's NOP fill | 113,929 | 2,325,915 |
| read-side byte swapper + width-confined shifter + M3b decoder miss | 125,528 | 1,555,953 |
| **S5 retired** — the BIU schedules the write cycle | 128,891 | 1,294,021 |
| the F interlock is per-read and in-order (C3/C5) | 137,370 | 853,021 |
| the second-byte group dispatch costs one clock | 145,680 | 654,937 |
| I/O through the same swapper and the same split (C7) | 147,672 | 638,536 |
| the shifter is 16 bits wide, only its taps move | 152,954 | 612,126 |
| retire deadline = the STORE only | 152,954 | 612,126 |
| E frees on the EU access's status cycle; flush carries CS | 153,335 | 612,140 |
| the shifter's right-shift MSB entry + the rotate wrap bus | **155,011** | 603,760 |

**282 of 347 forms are now 100 % cycle-row exact at w0** (was 47).  Arch
through the timed path is unchanged at 166,800/169,000 and windows at
168,720/169,000 — both shortfalls are still exactly the pin-event pseudo-forms
(scaffolding **S9**).

### 8.1 M5b — the A0 BYTE SWAPPER, and the datapath is 16 bits wide everywhere

One rotator, applied on both sides of the bus, is the whole of category C4 and
most of the "companion byte" folklore:

* **Register read.**  The register file has no byte read port.  It presents the
  whole PAIR and an 8-bit rotator puts the selected half in the low lane
  (`state.h::rb16`): a low-byte read is the pair as-is, a high-byte read is the
  pair swapped.  Byte-width consumers mask the low byte off; the write-data
  latch does not.
* **Memory / IO read.**  The 16-bit system presents the whole ALIGNED WORD; the
  CPU routes the ADDRESSED byte to the low half of its datapath and carries the
  COMPANION byte in the high half (`Biu::mem_read`, `Biu::io_read` — one
  expression for both widths).
* **Bus display.**  The AD value is always the datapath value rotated by A0.
  On a write that is `swap8(data)` at an odd address, ONCE PER ACCESS, so both
  cycles of a split write drive the same rotated value.  On a read it is the
  system word, which is the same statement read backwards.

*Evidence.*  `88` byte-store T1 rows, **366/366** predicted by
`rot(pair) -> rot(A0)`.  All four address/width quadrants, one case each:
`88` (`mov [odd], dl`, DX=403F -> 3F40; `mov [even], dl`, DX=6720 -> 6720),
`C6.0` (imm8 A3 sign-extended to FFA3, odd -> A3FF), `50` (PUSH AX, AX=CD0B at
an odd SP -> 0BCD on BOTH halves; AX=1B17 at an even SP -> 1B17).  Read side:
over every v0.1 MEMR byte cycle whose aligned partner byte is poked to
something other than 0x90, the free lane carries that partner byte in
**19,237** cases and differs in **747** — and every one of the 747 is an RMW
form (`0F20/0F22/0F26`) whose partner the same instruction had already
overwritten, i.e. the rule holds there too.  Discriminating case for
"aligned word" over "undriven lane retains": `58` case 0, a split POP at an odd
SP whose SECOND half (even address) shows `9007`, the aligned word, and NOT the
`A2` the first half had just put on the high lane.

**T0 §2.6 ("undriven byte lanes retain") is RETRACTED.**  It was an alias of
the rig's 0x90 NOP fill.

*Consequence — the rig's memory fill.*  A prefetch or a read outside a case's
poked bytes shows **0x90** on the rig, so the timed model needs that fill.
`Biu::set_fill` is settable; the FUNCTIONAL model keeps its 0x00 default
byte-identically and only `timed_runner` sets 0x90.  That arch through the
timed path stayed at 166,800 is the check that no golden depends on the fill
architecturally.

*Consequences inside the ALU, both previously unobservable because the high
half of a byte memory operand was always zero:*

* The iterative SHIFT/ROTATE unit is a **16-bit shift register whose ENTRY
  POINTS move with the operand width**, and the two directions are not
  symmetric because the register is not:
  * a LEFT shift is a plain 16-bit shift — there is only one LSB entry, it
    takes the byte-width feedback (rotate bit / carry-in), and bit 8 gets bit 7
    naturally;
  * a RIGHT shift has an MSB entry PER BYTE LANE, and the only thing that
    reaches the HIGH lane's entry is the ROTATE WRAP-AROUND BUS: `ROR`/`RCR`
    drive bit 15 with the same bit they drive bit 7, while `SHR` and `SAR`
    leave it at 0 (SAR's sign replicate is a mux on the LOW lane only).

  Settled by census, not by fitting — over the v0.1 `D0.*` byte memory RMW
  stores, reconstructing the datapath value on both sides of the A0 swapper and
  testing the two candidate high-lane models:

  | op | cases | two-lane | plain 16-bit |
  |---|---|---|---|
  | ROL | 377 | 377 | 377 |
  | ROR | 379 | **379** | 181 |
  | RCL | 369 | 179 | **369** |
  | RCR | 366 | **366** | 195 |
  | SHL | 381 | 185 | **381** |
  | SHR | 384 | 384 | 384 |
  | SAR | 382 | 201 | **382** |

  Every left-shift column picks plain-16-bit; on the right, the two ROTATES
  pick two-lane and the two SHIFTS pick plain-16-bit, with ROL and SHR
  indifferent because their feedback bits coincide.  That split is the wrap
  bus: it exists only for a rotate.
  Worked example: `ror byte, 1` on datapath 9029 stores **C894** — a single
  16-bit shift gives C814 and a fully confined shifter 0094.

**C4 is CLOSED.**  It rode the FULL functional sweep (§8.7).

### 8.2 C1 — the flush mechanisms.  Scaffolding **S8** is removed for the
near family; BUSLOCK and HALT display are still not implemented.

* **F1 — the QS=E display is a QS-PORT ARBITRATION.**  The queue-clear event is
  a point sample and the port carries one event per clock, so a flush parks and
  takes the port on the first clock that is free: not on the flush clock itself
  if a bus cycle still owns the port, not while a doomed fetch is still inside
  T1..Tw (it shows at that fetch's T4), not on the clock a completed fetch's
  bytes are absorbed, not on a clock already carrying a pop, and not while a
  ready-but-not-yet-STARTED EU request owns the next slot — except on the flush
  clock itself.  *Evidence:* `EB` case 0 (flush at a fetch's T3 -> E at its T4),
  case 1 (flush AT a fetch's T4 -> E one later), case 3 (quiet bus -> E on the
  flush clock); `E8` case 0 (E on the flush clock, push posted the clock after)
  and case 7 (E deferred to the push's status cycle); `E8` case 6 (CALL at an
  odd SP — E on the FIRST half's status cycle, the second half does not hold
  it).
* **F2 — THE ROM's BUS-CONTROL FIELD IS DECODED ONE ROW EARLY.**  `SUSP` and an
  EU bus request both reach the BIU on the clock edge that LOADS the prefetch
  commit register, so a fetch the eval just chose does not survive — but only
  while it has not reached the status PINS (once its display clock has been
  emitted the cycle is irrevocably announced).  **This one mechanism replaces
  two fitted laws:** biu_model.md's per-opcode "reservation starts at the
  final-pop cycle" (EB reserves at its last-disp pop although its SUSP row 0159
  runs one clock later; E9 at pop+1 although 0156 runs at pop+2) and the
  "reservation must LEAD the request by one cycle" S_RSV table for PUSH r16 /
  reg-EA store / PUSHA / mem-RMW.  The loop family's `dly<=3 blocked /
  dly>=4 free` cutoff is the same fact seen from the SUSP row's position.
* **F3 — the flush-only eval point** (biu_model.md "Redirect commit"): from the
  end of the flush onward the end of a PREFETCH cycle's T4 is an eval point,
  and it commits the REDIRECT ONLY.  A pending EU request owns the first slot
  and an EU access is never granted at a T4, so with a request outstanding the
  point simply does not fire and both wait for the next normal eval.
  *Evidence:* `EB` case 1 (redirect T1 on the doomed fetch's T4+1) vs `E8`
  case 7 (the push waits for the next idle eval).
* **`flush()` carries the NEW CS.**  A far transfer loads CS on an earlier
  micro-row than the FLUSH; taking CS from the last queue pop sent the redirect
  into the OLD segment (`CF` case 0 fetched 04646A where the chip fetches
  09B11A).

Result: the whole NEAR control-flow tranche is exact — `EB E9 74 75 7C E2 E8
C3 C2 EA C8` all **500/500**, which is biu_model.md's own 4,500-case
control-flow family gate plus EA/C8.  `FF.2` is 463/500.  The far/interrupt
half (`9A CC CD CE CF FF.3`) is a residual (§8.6).

### 8.3 UBE is NOT part of the status register

The status register (M2) drives BS, the address and PS one clock early.  **UBE
is not in it**: it changes at T1, one clock after the status and address do.
Invisible until an EU access sits next to a fetch, because every CODE cycle
drives UBE low.  *Evidence:* `E8` case 0 golden rows 14-15 (the split push's
second half is DISPLAYED with the first half's UBE and asserts its own at T1)
and rows 18-19 (the redirect fetch is displayed with the write's UBE).

### 8.4 The two requesters on one queue, and the two deadlines on one bus

* **M3b — a queue MISS costs the DECODER two clocks.**  The decoder's byte
  demand is a two-clock PLA pipeline and restarts it on a miss, so its pop
  lands at `max(ready, demand + 2)`; the EU's `Q` source read and the
  instruction-boundary pre-pop are combinational reads of the queue head and
  pop at `max(ready, demand)`.  Same queue, two requesters, no table.
  MEASURED on the queue-empty goldens, where every byte's ready clock is its
  fetch's T4 + 2: with demand 3 and ready 4, `8A`'s DECODER disp8 pops at 5
  while `B8`'s MICRO-ROW imm-hi pops at 4; `C6`'s disp16-lo (demand 2) pops at
  4 and its disp16-hi (demand 4) at 6; `04`'s imm8, already in the queue, pops
  on its demand clock.
* **The pre-decode operand read hands OPR over at its T4 + 2**, one clock after
  the F/OPR interlock releases — the decoder's own hand-over clock, the same
  one that puts micro-row 0 at opcode+2 and never at opcode+1.  Census over all
  347 forms (retire clock minus last data-cycle T4): every WRITE-terminated
  form is +1 with **no exceptions (52,752 cases)**, and every PRE-READ-
  terminated form is +1 plus the number of micro-rows that still have to run —
  2 rows (`8A/8B/02/03/0A/0B/12/13/1A/1B/22/23/2A/2B/32/33/38/3A/3B`) -> +3
  (9,043 cases), 1 row (`84/85/8E/66/67/D8-DF`) -> +2, 3 rows (`0F10/0F11`) ->
  +4.  Nothing per-op: the row count comes from the cadence engine.
* **The F interlock is PER READ and IN ORDER.**  Each `F` row waits for the
  NEXT completed read, not for the whole outstanding set — and a SPLIT access
  is ONE read to the EU, releasing on the LAST of its two byte cycles.
  *Evidence:* `A6` (CMPSB) issues both loads back to back and then runs
  `00A0 F / 00A1 / 00A2 F E`; the first F releases on load 1's T4+1 and the
  retire lands on load 2's T4+1, three clocks apart.  `8B` case 11 (word load
  from an odd address) retires off the SECOND half's T4.
* **The retire deadline is the STORE, not the bus.**  §7.7's
  max-of-two-deadlines in its true form: the successor pops its opcode on the E
  row's own clock, and the only thing that can push that later is a store the
  write-pairing latch still owes data.  An outstanding READ does not hold the
  retire — the ROM's own `F` rows do that where it matters.  *Evidence:* `88`
  mod0 pops it on the MEMW's T4+1; `8F.0` mod3 pops it on the E row while its
  stack read has not reached T1.  Removing the generic wait changed the ratchet
  by exactly zero, which is the argument for removing it.

### 8.5 Cadence additions — **S5 REMOVED**

* **Scaffolding S5 is fully retired.**  The write CYCLE is reserved by the BIU
  at the eval that follows the ROM row which ISSUES the store
  (`BiuTimed::write_request`); the write-data-pairing latch fills the value in
  later, always before the T1 that drives it.  MEASURED: `A4` (MOVSB, rows
  008D MEMR / 008F MEMW) puts the store's status on the LOAD's T4 and its T1 on
  the very next clock — the eval at the end of the load's T3 granting a request
  whose DATA does not exist yet.  With the latch owning the schedule the model
  inserted a whole prefetch there instead.
* **A FARJMP pays the same sequencer redirect bubble as a taken micro-JMP.**
  Independently predicted by the measured shift law: with the bubble, the
  `D2/D3/C0/C1` path (`011B FARJMP SHIFT -> 0228 JMP Z -> 0229 R -> 022A ->
  022B E`) retires at pop+10+n for n>=1 and pop+9 for n==0, and `D0/D1` — which
  reach the same R row WITHOUT a FARJMP — stay at pop+6.  Those are exactly
  measurements.md's numbers and none of them is written down in the sim.
  **This is also what disciplines §7.7's provisional "R row = one clock per
  iteration": the law survives unchanged; what was missing was the jump.**
* **The second-byte group dispatch costs one clock.**  `F6/F7 -> page 2` and
  `FE/FF -> page 3` re-enter the decode with the ModR/M byte standing in the
  opcode slot; that second look-up costs ONE CLOCK, charged AFTER the operand
  pre-read (it runs in parallel with the read and shows up as one extra clock
  before micro-row 0 — charging it before the read moves nothing, because
  `wait_opr` absorbs it, which is how the placement was settled).  MEASURED:
  `FE.0` (`inc byte [mem]`, 01B8/01B9) puts its store exactly one clock later
  than the structurally identical `00`/`10`/`D1` stores (0000/0001, 0115..0117)
  which share the same `[-06-]` write-back strobe on their second row.
* **Pre-window pin priming** (T0 open item 3, second half): `begin_case` replays
  the fetch ADDRESS sequence that filled the injected queue so the pins start
  where the chip's do.  Now largely redundant given §8.1 but kept, since it is
  what the chip's pins actually carry.

### 8.6 Residuals entering the rest of T1 / T2

13,989 cases still miss, of which 2,400 are the declared pin-event exclusion
(**S9**: `INT.* NMI.* HLT.*` 2,200 + `POLL.REL` 200).  The remaining 11,589,
each written as a family with its first-divergence pattern:

| family | cases | first divergence | hypothesis |
|---|---|---|---|
| `9A CC CD CE CF FF.3` far/interrupt flush | 2,763 | the SECOND push of the chain misses the first push's T3 eval by one clock and lands two clocks late (`9A` case 1: golden T1 at 17, model at 15), and the `E` follows it | the CALLF/INT push chain (022C-0231, 01D8+) carries one more clock somewhere between its two `MEMW` rows than the model gives it.  The same signature as `FE.0` before the group-dispatch clock was found -- a UNIVERSAL store lead-in was tested against the whole suite and REJECTED (it cost 24k cases), so the clock is in the chain, not in the store |
| 0F-escape page (`0F10-0F1F`, `0F28`, `0F2A`, `0F31`, `0F33`, `0F39`, `0F3B`) | ~2,000 | `qop S -> -`, a pop one clock late | the `0F` second byte is a DECODER pop and now pays the M3b miss penalty; its demand clock inside the 2-clock re-decode is not yet right |
| REP strings `F3A4 F3A5 F3AA F3AB F2AA` | 1,506 | iteration-2 onward | REP loop chaining: the non-REP forms are all 500/500, so this is the loop's re-entry cadence only |
| MUL/DIV `F6.6 F6.7 F7.6 F7.7` | 1,254 | length | category **C6**, the wait-insensitive compute burns, untouched |
| `8F.0` POP mem, `60` PUSHA | 1,000 | 8F.0: the golden's in-window MEMR address is NOT SS:SP and the sim's is (case 5: golden 0C87B8, SS:SP = 0C683A) — *possible golden-schema artefact, needs adjudication before any model change*; 60: the write chain | category **C5** |
| BCD strings `0F20 0F22`, `62` BOUND | 1,301 | length | C6-adjacent; multi-access loops |
| prefixed loads `26.8B 2E.8B 36.8B 3E.8B` | 520 | `qop S -> -` | same as the 0F page: the prefix byte's own demand clock under M3b |
| `FF.4 FF.2 FA FB` | 279 | mixed | small tails |
| `C0.7 D0.7 D2.7` SAR | 533 | data on the store | the SAR sign-replicate is settled for the low lane and bit 15 (0); one residue remains |

**Known regression, recorded rather than patched:** the M3b decoder miss
penalty cost ~600 previously-exact cases in the 0F/prefix families while
buying ~7,600 elsewhere.  It is the same open item as the 0F row above.

### 8.7 Gates (measured, this machine)

The FULL functional sweep, re-run on the FINAL binary of this pass — every
one of the mechanisms below that touches the shared interpreter (`rb16`, the
read-side byte swapper in `Biu::mem_read` / `Biu::io_read`, the shifter's
lanes) is ARCHITECTURAL, so it rode all of it:

| suite | result | time |
|---|---|---|
| v0.1 | 169,000 / 169,000 | 20 s |
| v0.2 | 347,000 / 347,000 | 43 s |
| v0.3 | 3,699,998 / 3,699,998 | 507 s |
| v20suite | 3,125,000 / 3,125,000 | 385 s |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 | 0 s |
| **total** | **7,341,126** | |

(`mod3_illegal` is the loose thread §7.10 flagged as "unverified either way":
it needs the `--residue stale-ea` flag, and with it the suite is 128/128.  It
is now part of the standing set.)

```
make -C sim test                                    # disasm gate: PASS
python3 sw/pla3_check.py                            # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1    # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2    # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3    # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite         # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all   # THE RATCHET
python3 sw/timed_probe.py --forms EB --top 8         # first-divergence triage
```

**Environment note (unchanged from §7.10):** `export TMPDIR=~/.cache/ucsimt-tmp`
before building or running anything that uses `tempfile`; `/tmp` is a small
tmpfs on this machine.  Do NOT write row dumps there.

`sw/timed_probe.py` is new: it reuses `timed_gate`'s runner and `check_core`'s
comparison policy unchanged and groups the failing cases of a form by their
FIRST divergent cell.  Every mechanism in §8 was found by reading one of its
classes; it is the tool that turns "N cases fail" into "one mechanism is
missing here".

### 8.8 Still owed inside T1 (unchanged from §7.12)

* the **L1 `timed-scenario` oracle-replay adapters** (decoder-drain v2,
  decoder-multibyte, decoder-displacement, prefix-phase) are STILL only
  hand-checked cross-references on §7.6; no replay harness exists.
* **BUSLOCK and HALT display** — S8's remaining half.
* **`kSegZero` PS code** — still an ASSUMPTION; the `INT.*` goldens can settle
  it but they are the S9 exclusion, so it stays open until S9 opens.
* **§7.6's EA stage.**  The five-row decoder table is UNCHANGED and its two
  bare numbers (disp8 @3 vs disp16-lo @2; mod0-no-disp costing one clock more
  than mod3) are STILL not derived from a two-clock EA machine.  What this
  pass added around it is the M3b miss penalty, which interacts with those two
  numbers directly — the queue-empty goldens now discriminate demand clocks to
  the clock, so the EA stage is a better-posed question than it was, and the
  0F/prefix residual in §8.6 is most likely the same question.

### 8.9 Milestones

* **Milestone A** (B8 8B 89 F7.6 EB E8 at w0 + w1/w3): **NOT MET.**  At w0
  FIVE of the six are 500/500 — `B8 8B 89 EB E8` — and `F7.6` is 245/500
  (category **C6**, the MUL/DIV compute burns, untouched this pass).  At w1
  and w3 the same six forms are 158/1200 and 162/1200: the wait axis is T2
  work and M2's register-release still has to be re-derived from the READY
  sample, exactly as §7.2 requires.
* **Milestone B** (the 35-opcode S1a tranche at w0): not separately measured;
  276/347 forms are 100 % exact, which covers most of it.
* **Milestone C** (T1 exit, 166,800/166,800): **NOT MET** — 155,011.


---

## 9. T1 third pass — one decode march, one OPR

This section continues §8.  Nothing earlier is retracted except where an entry
below says so.  Two mechanisms were found; between them they closed SIX of the
nine residual families of §8.6.  The ratchet
(`sw/timed_gate.py --suite tests/v30/v0.1 --forms all`, `rows_exact`):

| step | rows exact | row diffs |
|---|---|---|
| §8 close | 155,011 | 603,760 |
| M3c — a decode step that misses RE-RUNS (replaces M3b) | 158,285 | 460,217 |
| the OPR interlock — `F` is per ACCESS, writes included | 162,721 | 45,283 |
| the OPR SHADOW + only a fetch owns the QS port | 163,820 | 36,853 |
| `F`'s direction picks the wait (9.3) | **164,320** | **24,030** |

**319 of 347 forms are 100 % cycle-row exact at w0** (was 282).  Arch through
the timed path is unchanged at 166,800/169,000 and windows at 168,720/169,000.

Both mechanisms were found the same way: a census of the GOLDENS' own rows,
not of the model's.  The two instruments are new and are standing tools:

* `sw/qcensus.py` — every queue POP with the READY clock of the byte it took,
  reconstructed from the golden's own fetch stream (that fetch's T4 + 2).
  This is what separates "the byte was late" from "the decoder was late", and
  it is what killed M3b.
* `sw/wchain.py` — the spacing from one bus cycle's T4 to the next cycle's T1,
  keyed by the two statuses, with the halves of a split folded together.  One
  run of it over the whole suite located the write-chain law.

### 9.1 M3c — the decode march, and the death of the flat two-clock miss

**§8.4's M3b is RETRACTED.**  There is no "queue miss costs two clocks".  The
decoder walks its byte demands as a march of STEPS; a step that has to take a
queue byte takes it on the step's LAST clock, and **a step that does not get
its byte runs again**:

```
    pop = min { demand + k*step : k >= 0,  demand + k*step >= ready }
```

`step` is not a parameter and not a table — it is the march's own stride, the
clocks the decoder has advanced since its previous pop.  The implementation
carries one new field (`last_dec_`, the previous decoder pop's clock) and
derives everything else.

*Evidence — every cell, over every v0.1 golden* (`sw/qcensus.py --map`, the
previous decoder pop at clock 0; `ready` from the golden's own fetch stream):

| stride | which demands | ready -> pop |
|---|---|---|
| 1 | ModR/M after the opcode or after the `0F` byte; disp16-**LO** after the ModR/M | 0->1, 2->2, 3->3, 4->4 |
| 2 | the `0F` page's opcode; the opcode after a PREFIX; disp8 after the ModR/M; disp16-**HI** after disp16-lo | 0->2, 1->2, **3->4**, 4->4 |

A flat `max(ready, demand+2)` fits the stride-2 rows and is wrong for every
stride-1 row where the byte arrives two clocks late — `26.8B` takes its
ModR/M on the clock the byte arrives (ready = opcode + 2) and the flat penalty
pushed it one clock late.  That was the **~2,500-case 0F-escape /
segment-prefixed residual** of §8.6, and it was also §8.6's recorded
"known regression" (M3b bought ~7,600 cases and cost ~600 in these families).
Both are now closed: `0F10 0F11 0F1F 26.8B 2E.8B 36.8B 3E.8B` and the rest of
the `0F` page are **500/500**, and so is the `C0.7/D0.7/D2.7` **SAR tail**
(533 cases), which turns out to have been the same pop landing one clock late.

*What this says about §7.6's EA stage.*  The five-row demand table is
unchanged, but it is no longer five bare numbers plus a penalty: it is a march
of 1- and 2-clock steps, and the STRIDE is now a measured, load-bearing
quantity rather than a derived one.  The two numbers §8.8 called out —
disp8 at 3 while disp16-lo is at 2, and mod0-no-disp costing one clock more
than mod3 — are exactly "the disp8 step is two clocks long and the disp16-lo
step is one".  **That is still a description, not yet a derivation**: why the
byte-displacement step is the long one is not answered here.  See §9.4.

### 9.2 The `F` interlock is the **OPR** interlock — and it is what spaces a push chain

**§8.4's "the F interlock is PER READ" is AMENDED** (its read half stands).
`F` marks the row that loads OPR.  OPR is ONE register and it is both the
read-data and the write-data register, so an `F` row has TWO reasons to wait:

1. **the read side (unchanged).**  Wait for the next outstanding READ, in
   order; a split is one read, releasing on the last of its byte cycles.
2. **the write side (new).**  Wait while a store still OWNS OPR.  A store owns
   OPR from the moment its data is PAIRED into it until the bus has driven
   that data out — measured as the **end of T2**, so the `-> OPR` row that
   reloads it runs on **T3**.

A store that is only RESERVED (S5) does **not** own OPR: the very `F` row that
would wait for it is the row about to load it.  That distinction is not a
special case, it is the whole difference between ENTER's prologue and its
epilogue, and getting it wrong is a hang.

*Why the two conditions are separate and not one queue:* they are ordered
differently.  The read side is a FIFO of completions the rows consume one
apiece; the write side is a level, not an event — "is OPR occupied right now".

*Evidence — the ROM, then the whole suite.*  The chain law falls straight out
of the microcode once `F` is read as the OPR interlock:

```
  60  PUSHA   023A          MEMW SS      0239/023B/023D/... `x -> OPR   F`
  9A  CALLF   022E          MEMW SS      022D `CS -> OPR F` / 022F `PC -> OPR F`
                 022F  PC -> OPR    F
                 0230          MEMW SS
  C8  ENTER   026D          MEMW SS      the loop: NO `-> OPR` row between
                 026E JMP CNTZ            two stores -- the pushed word is
                 026F                     still standing in OPR from the
                 0270          MEMW SS    loop's own MEMR
```

so a store followed by an `-> OPR F` row cannot be re-issued until that F
releases on T3; its own clock puts the next `MEMW` row at T4, whose request
misses the T4 eval (T4 is not an eval point at w0) and is taken at the next
idle eval — **the second store's T1 lands on the first's T4 + 3**.  Where the
ROM has no `-> OPR` row between two stores there is nothing to wait for and
the chain is **T4 + 1**, back to back.

`sw/wchain.py` over all 169,000 goldens confirms exactly that split, with no
exceptions:

| write -> write spacing | forms |
|---|---|
| **T4+3** (an `-> OPR F` row between the stores) | `60 9A CC CD CE FF.3 62 F6.6 F6.7 F7.6 F7.7` + the `INT.*`/`NMI.*`/`HLT.*` pseudo-forms |
| **T4+1** (none) | `C8` ENTER's nesting loop (267 of its 277 chains), `F2AA F3AA F3AB` REP STOS (the stored AW never leaves OPR) |
| T4+1 | every `split` pair — one access, one load of OPR |

**A universal store lead-in is still REJECTED** (§8.6 recorded that test): the
clock is in the chain, and this is where it is — in the ROM's own `-> OPR`
row, not in the bus.

*What it closed.*  `9A CC CD CE FF.3` (the far/interrupt push chain, 2,763
cases) → **500/500 each**; `60` PUSHA → 500/500; `62` BOUND → 500/500;
`F6.6 F6.7 F7.6 F7.7` **MUL/DIV** → 500/500.  The MUL/DIV family (§8.6's
category **C6**, 1,254 cases, "untouched") needed **no compute-burn model at
all** — its length was never a burn, it was the R-loop's stores waiting on
OPR.  `F7.6` was the last open leg of **Milestone A at w0**.

### 9.3 The `F` flag names OPR, and the DIRECTION of the touch picks the wait

The two conditions of 9.2 are not both armed by every `F` row.  `F` marks a row
that TOUCHES OPR, and which way it touches picks which half of the interlock
applies:

* the row READS OPR (`OPR -> R`, `OPR -> tmpa`, `OPR -> PC`, ...) -> it waits
  for the read that fills OPR, in order;
* the row LOADS OPR, or touches neither -> it waits only for a store to give
  OPR back.  It does NOT wait for the read: the read it is nominally
  synchronising with is consumed by the NEXT row's bus cycle, which takes
  OPR's contents at its own T1 (9.2's shadow) and does not need the datapath
  to have caught up.

*Evidence — `8F.0` (POP mem/reg), 0058-005B:*

```
  0059 SP -> IND   SP -> tmpb        CTL  MEMR SS
  005A SIGMA -> SP                F  ALU PASS tmpa      <- touches no OPR
  005B SIGMA -> IND             E    CTL  [-06-]
```

With 005A blocking, the write-back's cycle can only be reserved after the
load's data has landed.  The golden reserves it at the LOAD's T3 eval, three
clocks earlier, and drives that data anyway (case 18: MEMW status on the
load's T4, T1 on the next clock, data = the word the load returned).  The
mod3 half is the same fact seen through the ghost read: the E row pre-pops the
successor's opcode at pop+5, before the load has even reached T1 — which is
exactly what 8.4 recorded as evidence for the retire deadline and could not
reproduce.

**`8F.0` ADJUDICATION — the golden schema is SOUND; no change was needed.**
8.6 flagged the in-window MEMR address as a "possible golden-schema artefact".
It is not one.  `check_core.dontcare_cells` already masks that read's address
and data (col 1 and col 6) for `8F` + mod3, and `timed_gate.row_check` /
`timed_probe` already apply it — the masking was wired all along.  What
remained after the mask was the QS column, a real mechanism, and with the
direction split `8F.0` is **500/500**, mod3 and mem alike.

### 9.4 Residuals entering the rest of T1 / T2

4,680 cases still miss, of which 2,400 are the declared pin-event exclusion
(**S9**).  The remaining 2,280, each with its first-divergence pattern:

| family | cases | first divergence | what is missing |
|---|---|---|---|
| BCD strings `0F22` `0F20` | 882 | the COMPANION byte of the byte store, always off by one (`C342` vs `C343`; `20B6` vs `21B6`) — every clock, every status and every addressed byte is exact | the BCD block's DATAPATH HIGH HALF.  This is 8.1's C4 question (the datapath is 16 bits wide everywhere) applied to `0F 20-27`: the model's ALU result is byte-wide there, so the free lane carries the wrong sibling.  ARCHITECTURAL -- the fix must ride the full 7.34M sweep, exactly as `rb16` did |
| REP strings `F3A4 F3A5 F3AA F2AA F3AB` | 907 | the CLOSING `F` pop is one clock early (`F3AA` case 16: golden at the last store's T4+2, model at T4+1) | one clock in the REP EXIT path -- the not-taken `JMP REP` (`00C0` for STOS, `00AE` for MOVS), the `FARJMP REPX` that follows it (`00C1`/`00AF`) and REPX's own 0220/0221/0222 -> 0224 `E`.  The LOOP is right: `00BF MEMW` / `00C0 JMP REP` carries no `-> OPR` row, which is why REP STOS chains its stores at T4+1 (9.2) and the model reproduces that.  Only the cases where the E row rather than the store is the binding deadline show it, which is why 336-411 of each 500 are already exact.  The data half of this family is CLOSED (9.2's shadow) |
| `FF.4` JMP mem, `FF.2` CALL mem | 137 | the closing `F` pop is EARLY by ~5 clocks (`FF.2` case 2: golden at 20, model at 15) | the post-flush retire: the model pre-pops the successor before the redirect fetch can deliver, so the window closes on a byte the queue does not have yet |
| `FA` CLI, `FB` STI | 142 | S5 (IE) on the fetch's T3, one clock late | the flag write's clock.  MEASURED and clean: with an EVEN `ip` the golden shows the new IE at T3, with an ODD one it does not (250/250 split, `qcensus`-style census over the form).  The variable is the QUEUE STATE at the opcode pop -- odd `ip` leaves the queue EMPTY after it, even leaves one byte -- so the flag write rides a decode step that is itself waiting on the queue.  **A "PS is a register loaded at T2" model was tried and FALSIFIED**: the even-`ip` half shows PS changing WITHIN one data phase.  It scored better (112 bad vs 142) and was reverted anyway |
| `0F39` `0F12` `C1.6` `F7.4` | 12 | mixed | tails, unexamined |

### 9.5 Milestones

* **Milestone A** (B8 8B 89 F7.6 EB E8 at w0): **MET AT w0** — all six are
  500/500.  The w1/w3 legs stay open for T2 (the wait axis; M2's release point
  must be re-derived from the READY sample, §7.2).
* **Milestone B** (the 35-opcode S1a tranche at w0): 317/347 forms are 100 %
  exact and every form in the tranche is among them.
* **Milestone C** (T1 exit, 166,800/166,800): **NOT MET** — 164,320.

### 9.6 The owed items — what landed, and what the T1 exit actually requires

**LANDED: the L1 `timed-scenario` oracle-replay adapter** (§7.12 item 7,
§8.8 first bullet).  `sw/timed_scenario.py` plants a saturated-queue case for
one representative encoding of each frozen decoder class and asserts the sim's
QS schedule against the FROZEN oracle files, read as-is:

```
python3 sw/timed_scenario.py
PASS modrm_reg  mov ax,ax          oracle [(0,F),(1,S),(3,F)]        sim identical
PASS test_reg   test ax,ax         oracle [(0,F),(1,S),(2,F)]        sim identical
PASS imm16      mov ax,1234h       oracle [(0,F),(2,S),(3,S),(4,F)]  sim identical
PASS branch     jmp short +2       oracle [(0,F),(2,S),(5,E)]        sim identical
PASS disp8      mov ax,[bp+10h]    oracle [(0,F),(1,S),(3,S)]        sim identical
PASS disp16     mov ax,[bp+1234h]  oracle [(0,F),(1,S),(2,S)]        sim identical
timed-scenario: 6 PASS, 0 FAIL, 12 SKIP
```

covering `decoder-multibyte-oracle-v1` and `decoder-displacement-oracle-v1`
whole (zero-wait half).  The frame shift between the oracles' "clocks from the
selected cycle's T4" and the ledger's "clocks from the opening F pop" is ONE,
the constant §7.6 established by hand; it is the only constant in the adapter.
Two things are SKIPPED and say so rather than passing quietly: each rule's
POSITIVE-WAIT half (T2), and each rule's `gap` (`t1_from_selected_t4`), which
is a BUS quantity in the arbitration frame and needs the REP-successor
scenario the oracles were captured in.  `decoder-drain-oracle-v2` is stated on
the same arbitration frame (`*_code_gap`) and is therefore also not replayed
here; its QS half is the same schedule the two above already pin.

**NOT LANDED, and the reason is structural, not effort:**

* **The law-card MUST set C1-C7, C9-C12 cannot be gated in this pass.**  Read
  the manifest's own Stimulus and Gate columns (`biu_law_cards.md` §A): C1
  "fetch-limited stream, WAITED"; C2 "queue-fill ramp, WAITED"; C3 "wvec/
  directed"; C4/C5 "WAITED resume"; C6/C7 "EVEN/ODD **Tw** parity" plus the
  board-only uRMW capture; C9 "w1/w3 + wvec"; C10/C11/C12 "wvec".  Every one
  of the eleven is stated on a WAIT VECTOR.  At w0 there is no Tw, no aged
  band and no deferred eval, so nine of them have no stimulus at all and two
  (C6/C7) additionally need a capture no golden carries.  §7.4 already
  recorded that LC1's steady-state gap and LC2's aged band are deliberately
  NOT implemented for exactly this reason.  **The plan's T1-exit clause "law-
  card MUST set green as sim unit gates" is mis-scoped: it is a T2 gate.**
  Recorded here rather than satisfied with a gate that cannot fail.
* **Boot replay** (`sw/testdata/largemode_boot_real.hex`).  `sw/check_boot.py`
  drives the VERILATED RTL testbench (`hdl/tb/obj_dir/Vtb_v30_core`) from a
  held RESET; the C++ timed sim has no reset entry point at all — `begin_case`
  injects architectural state and starts the bus idle.  Replaying the boot
  capture needs a `timed-boot` mode (reset -> first fetch -> the EA far jump ->
  the 64-cycle loop) and the capture's own column policy ported.  Owed, sized,
  not started.
* **BUSLOCK and HALT display** (S8's remaining half) and **`kSegZero`** — both
  unchanged from §8.8.  `kSegZero` is still an ASSUMPTION and the `INT.*`
  goldens that could settle it are still the S9 exclusion.

### 9.7 The FULL functional sweep on this pass's binary

Two of this pass's changes touch the SHARED interpreter (`deliver_read`'s
direction split in `exec_impl.h`, and the `wait_opr_free` no-op added to the
functional `sim::Biu` so both instantiations carry the same call sites), so
the whole architectural corpus was re-run on the final binary:

| suite | result | time |
|---|---|---|
| v0.1 | 169,000 / 169,000 | 19 s |
| v0.2 | 347,000 / 347,000 | 40 s |
| v0.3 | 3,699,998 / 3,699,998 | 536 s |
| v20suite | 3,125,000 / 3,125,000 | 386 s |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 | 0 s |
| **total** | **7,341,126** | |

plus `make -C sim test` (disasm) PASS and `sw/pla3_check.py` OK (21 checks).
Zero regressions -- the architectural corpus is byte-identical across the
whole pass.

### 9.8 Standing gates, this pass

```
make -C sim test                                          # disasm: PASS
python3 sw/pla3_check.py                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite      # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all   # THE RATCHET
python3 sw/timed_scenario.py                              # L1 oracle replay
python3 sw/timed_probe.py  --forms EB --top 8             # first-divergence triage
python3 sw/qcensus.py --forms all --empty --by role --map # the pop census
python3 sw/wchain.py  --forms all --pair MEMW\>MEMW       # the bus-chain census
```

---

## 10. T1 CLOSE-OUT — four mechanisms, a reset entry point, and one honest hole

This section closes the stage.  Nothing earlier is retracted.  The ratchet
(`sw/timed_gate.py --suite tests/v30/v0.1 --forms all`, `rows_exact`):

| step | rows exact | row diffs |
|---|---|---|
| §9 close | 164,320 | 24,030 |
| the BCD adjust is one 16-bit adder pass (§10.1) | 165,202 | 16,185 |
| a flush's doomed fetch pushes nothing (§10.2) | 165,299 | 15,991 |
| the redirect outlives the withdrawal (§10.2) | 165,339 | 15,671 |
| a pre-decode form's flag write rides its LAST clock (§10.3) | **165,481** | **15,490** |

**325 of 347 forms are 100 % cycle-row exact at w0** (was 319).  Arch through
the timed path is unchanged at 166,800/169,000 and windows at 168,720/169,000.

### 10.0 SCOPE AMENDMENT (coordinator-approved), recorded

**The law-card MUST set clause moves to T2.**  §9.6 argued it from the
manifest's own Stimulus/Gate columns — every one of C1-C7 and C9-C12 is stated
on a WAIT VECTOR, and at w0 there is no Tw, no aged band and no deferred eval,
so nine of the eleven have no stimulus at all and two (C6/C7) additionally need
a capture no golden carries.  That argument is now the accepted scope: the
cards are a **T2** gate.  T1 is not credited with them and does not pretend to
a gate that cannot fail.

### 10.1 The BCD adjust is ONE PASS THROUGH THE ADDER, and the adder is 16 bits

§8.1's C4 question — *the datapath is 16 bits wide everywhere* — applied to the
`0F 20-27` block, which is where §9.4 had left it.

The decimal-correction unit sits on the **low lane of port B only**: it
replaces that lane with `corr`, the high lane of port B goes through raw, and
the one carry chain runs the whole 16 bits.  So an adjust row produces

```
    hi = A_hi  +/- B_hi  +/- carry-out-of-the-low-lane
    lo = the decimally corrected byte
```

and because the ROM's own adjust rows are `02D6 ONES -> tmpa / ALU ADD tmpa`
and `02E6 ONES -> tmpa / ALU SUB tmpa`, **B = 0xFFFF** and the byte store's
COMPANION lane comes out one BELOW (ADD4S) / one ABOVE (SUB4S) the ADC/SBB
result's high half.

*Settled by census, in two steps, over every divergent v0.1 store:*

| high-lane model | `0F20` residue | `0F22` residue |
|---|---|---|
| `A_hi` (the §9 model — the adjust preserves the high half) | 1,262 stores, **every one exactly −1** | 1,876 stores, **every one exactly +1** |
| `A_hi +/- B_hi`, lanes independent | 778 (exactly the stores whose low lane carried) | 164 (ditto) |
| `A_hi +/- B_hi +/- carry` | **0** | **0** |

`0F20 0F22 0F26` are **500/500** each (were 99 / 19 / 500).  The 882 cases
§9.4 booked to this family are closed and nothing else moved.

**ARCHITECTURAL** (it is in `alu_eval`), so it rode the FULL corpus (§10.8).
It is architecturally *invisible* — every consumer of an adjust result is a
byte write (`-> AL` for the native `27/2F/37/3F` and the 8080 `DAA`, a BYTE
memory store for the strings) — which is exactly why it could only ever have
been found on the pins.

### 10.2 The flush law had a hole on each side of "irrevocably announced"

§8.2's F1/F2/F3 were right; `BiuTimed::flush` implemented them with two bugs,
one per side of the line `withdraw_fetch()` draws.

* **The doomed fetch's bytes.**  `flush()` zeroed `push_n` only for a fetch
  already RUNNING.  A fetch whose status is on the pins but whose T1 opens on
  the flush clock itself (`cmt_t1_ == clk_` — precisely the case
  `withdraw_fetch` refuses, because the cycle is irrevocably announced) went on
  to push into the flushed queue.  `FF.2` (CALL mem/reg) is the form that shows
  it: `01BD` FLUSHes two rows before `01BF`'s `E`, so the retire pre-popped a
  byte the chip does not have and the window closed five clocks early (case 2:
  golden 20, model 15).  §9.4's "the model pre-pops the successor before the
  redirect fetch can deliver" — the *reason* is that the redirect had already
  delivered a byte it should never have had.  **`FF.2` 463 → 500/500.**
* **The redirect vs the withdrawal.**  `withdraw_fetch()` rewinds `fetch_ptr_`
  to what it was before the withdrawn fetch was chosen — and `flush()` called
  it AFTER loading the redirect, so the rewind threw the redirect away and the
  next eval went straight back into the OLD instruction stream.  Visible only
  when the flush lands on a T4 whose F3 flush-only eval is the first one after
  it: `FF.4` case 8, the chip fetches `0D8163` and the model re-fetched
  `0CE096`.  **`FF.4` 400 → 500/500.**

The whole near control-flow tranche stays exact: `EB E9 E8 EA C8 9A CC CD CF
C3 C2 74 E2 FF.2 FF.4` are 500/500 each, 7,500/7,500.

### 10.3 A pre-decode-executed form's flag write rides its LAST clock

`FA`/`FB` and every other ONE_BYTE_LOGIC form have no ROM row and no `E`: the
pre-decode logic decodes AND executes them, in two clocks.  The DECODE clock
is the opcode pop's own; the **execute strobe** — the clock the flag write
commits on — is the instruction's **last** clock, which is the clock BEFORE the
successor's opcode pop.  **So when the queue makes that pop late, the write
goes late with it.**

MEASURED on the pins: IE rides the PS nibble of every data-phase clock, and
v0.1 injects an EMPTY queue for half of each form's cases, where the opcode's
own address parity decides how much the priming fetch delivered.

| | priming fetch | successor pop | golden IE at pop+1 | cases |
|---|---|---|---|---|
| even `ip` | word (2 bytes) | pop+2 | **the NEW value** | 250/250 |
| odd `ip` | single upper-lane byte | pop+4 | **still the OLD value** | 250/250 |

That is §9.4's "split cleanly by queue state (ip parity)" with the QUEUE, not
the parity, as the variable — the parity only picks the fetch width.  The even
half rules out "the write rides the successor's pop clock" (it would land one
late); the odd half rules out the unconditional write.  Nothing in the suite
separates pop+3 from pop+4 on the odd half, and one rule gives pop+3.  §9.4's
falsified "PS is a register loaded at T2" stays dead — the even half shows PS
changing WITHIN one data phase.

`FA FB F8 F9 F5 FC FD` are **500/500 each** (`FA` was 426, `FB` 432).  The five
that were already exact staying exact is the control on the new call site.

### 10.4 `timed-boot` — the RESET entry point, and the boot capture

§9.6's "owed, sized, not started" is started, and it is a standing gate.

`v30sim timed-boot <rom> <image.bin> [--clocks N] [--ndjson]` loads a flat
64 KB image into the 64 KB-mirrored memory the capture board is wired as, runs
the ROM's OWN reset sequence (page 7 opcode 03: `01D0 / 01D1 SUSP / 01D2 /
01D3 FLUSH / 01D4 E MFS` — `CpuT::reset()`, which the image runner has always
used) and keeps stepping, emitting one record per CPU clock in the capture's
frame: **clock 0 = RESET RELEASE**.  `sw/check_boot.py --timed` drives it; the
column policy is NOT forked, the timed engine is a second `run_*` inside the
existing script so both legs are compared by the same code (qs from release,
bs from +8, t/ube/addr/data/ps from +9).

**ONE constant: the ROM's reset rows start on release+4.**  Read off the
capture twice over — the reset FLUSH's `E` blip is on release+7 and the first
CODE T1 on release+9, and the ROM puts FLUSH four rows after the block's first
row.  Everything between is the ordinary machine: the `E` takes the QS port on
its own clock (the bus is quiet), the eval at the end of that clock commits the
redirect, its status shows on +8 and its T1 opens on +9.

**RESULT: 205 of 220 rows from RESET release, and the 64-clock boot loop is
exact** — `CODE T1 @00100` at rows 26 / 90 / 154 / 218 in real and sim alike,
period 64 in both, every bus cycle of the EA far jump and of the loop body
matching cell for cell.

The 15 rows that differ are THREE identical occurrences of ONE mechanism (5
rows per loop iteration): at the loop's closing `EB` the model commits one more
prefetch (`00114`) at the eval immediately preceding the instruction's first
micro-row, where the chip's bus stays idle.  **That is the falsifier §7.4
pre-registered for the resume predicate**, and it names the SUSP LEAD.

*On the RTL leg:* `sw/check_boot.py` with no flag still drives the Verilated
core and was NOT re-verified in this pass — this working tree carries
uncommitted `hdl/rtl` changes from a different campaign and
`hdl/tb/obj_dir/Vtb_v30_core` is a stale build, so that leg reports 206/220 for
reasons that have nothing to do with ucsim-t.  The edit here adds a second
engine to the script and touches the RTL path not at all.

**A literal F2 lookahead was tried and REJECTED.**  Decoding the successor
row's bus-control field one row early (so `0159`'s SUSP reaches the BIU on
`0158`'s clock) makes the boot replay **220/220 EXACT** — and costs the v0.1
ratchet **3,446** cases (165,481 → 162,035); a withdraw-only variant still
costs 2,254 (→ 163,227).  169,000 goldens outrank one capture, so it is
recorded, not landed.  The two legs are now a sharp stated conflict for the
arbitration/reservation work (§7.12 item 6, law cards C9-C12) instead of a
vague open item: **the boot loop wants the SUSP one row earlier than the v0.1
goldens permit, and one of the two frames is mis-stated.**

### 10.5 `kSegZero` — **SETTLED, and the assumption was right**

T0 open item 5 / §8.8 / §9.6: the PS segment code the internal INT routine's
"no segment" accesses drive.  §9.6 said the `INT.*` goldens could settle it but
were the S9 exclusion — that is a constraint on the *model*, not on *reading
the goldens*.  Census of every IVT-read data-phase row in all eleven pin-event
forms (`INT.90 INT.9D INT.B8 INT.8ED0 INT.8ED8 INT.F3AA INT.FB NMI.90 NMI.B8
HLT.INT HLT.NMI`), at `0x3FC/0x3FE` (INT vector 0xFF) and `0x8/0xA` (NMI
vector 2):

* **4,800 rows, segment code 2 in every one** — `seg` column `CS`, PS nibble
  `6` where IE was set and `2` where it was not, with the IE split falling
  exactly where the case's entry IE does.

`kSegZero` drives the SAME code as CS.  `BiuTimed::seg_code`'s
`default: return 2` is now MEASURED, not assumed.  The class of the claim moves
ASSUMPTION → **MEASURED**; its falsifier (any no-segment access driving a code
other than 2) has 4,800 chances to fire and does not.

### 10.6 The residual — 919 cases, two families, both stated

At the T1 close the v0.1 w0 census is:

```
169,000 total
 −2,600 pin-event forms (S9): the eleven arch-excluded INT./NMI./HLT. forms
        (2,200) + HLT.RES (200) + POLL.REL (200)
  ------
166,400 reachable at w0      165,481 exact      919 short
```

**An accounting correction, stated rather than hidden.**  §7.10 wrote the exit
target as 166,800 = 169,000 − 2,200, taking the S9 set to be the eleven forms
whose ARCH is excluded.  That is the wrong set: `HLT.RES` and `POLL.REL` are
architecturally exact (200/200 each) and so were never in the 2,200, but both
are pin-event forms whose ROWS the model cannot produce — `HLT.RES` needs the
HALT pseudo-cycle plus a RESET event mid-case, `POLL.REL` needs the POLL pin
sampled every 5 clocks (`interrupt_model.md`).  They belong to **S9** by the
same construction as the other eleven, and the reachable-at-w0 denominator is
**166,400**, not 166,800.  This is a re-labelling of 400 cases that were always
pin-event, not a relaxation: no case moves from "should be exact" to "excused"
on any ground but the one S9 already stands on.

| family | cases | what is missing |
|---|---|---|
| REP strings `F3A4 F3A5 F3AA F2AA F3AB` | 907 | §10.7 |
| tails `0F39` (9), `0F12` `C1.6` `F7.4` (1 each) | 12 | `0F39` is one extra prefetch slot — the same resume-predicate falsifier §10.4's boot leg names; the other three are one case each, an address on one cycle, unexamined |

### 10.7 REP strings — §9.4's "one clock in the exit path" is **FALSIFIED**

§9.4 booked this family as "the CLOSING `F` pop is one clock early ... one clock
in the REP EXIT path".  That is not what the data says, and the new census says
so cleanly.  Per case, the offset from the LAST store's T4 to the window-closing
pop, golden vs model:

| | golden offset | model offset | verdict |
|---|---|---|---|
| `cx = 0` (615 cases, all five forms) | — no store — | — | **100 % exact** |
| `cx = 1`, `F3AA F2AA F3AB` (370) | 1, 2 or 3 — it VARIES | tracks it exactly | **100 % exact** |
| `cx >= 2`, `F3AA` (259) | **always 2** | 1, 2 **or 3** | 164 bad |
| `cx >= 2`, the other four | 1 or 2 | 1, 2 or 3 | the rest |

Two facts kill the "one clock" reading:

1. the model is **early in some cases and LATE in others** (`F3AA` `cx=2`: 44
   cases at T4+1, 67 at T4+3, against a golden that is T4+2 in all 138);
2. `cx = 0` and `cx = 1` — which run the WHOLE exit path, `00C0` not taken,
   `00C1 FARJMP REPX`, `0220-0224` — are **exact**.  A constant added anywhere
   in that path shifts them too.  It was tried: +1 on the taken `JMP REP` and
   +1 on any taken BACKWARD micro-JMP each cost `F3AA` 28 cases (336 → 308) and
   bought nothing.

What the data says instead: **with `cx >= 2` the chip's row engine is PINNED to
the bus and the model's free-runs.**  The discriminator is a pair of `F3AA`
`cx=2` cases whose GOLDEN bus streams are identical cell for cell (both stores
at rows 11-18, the pop at row 20) but whose EU starts two clocks apart (case 16
pops its opcode at row 2, case 10 at row 4, and the model reproduces both) —
the chip retires both at row 20, the model at 19 and 21.  Working backwards
through the exit path, both land on row 20 if the loop's SECOND store row
`00BF` runs on the FIRST store's T2 and free-runs from there.

That is a WRITE-SIDE interlock one clock tighter than §9.2's: OPR is released
to a `-> OPR` row at T3, and this wants the store ROW released at T2 — i.e.
when the data is DRIVEN (T1) rather than when the bus has taken it.  Two
release points on one register is the shape the campaign distrusts, so it is
**not landed**.  A probe that released the store row at the previous store's T1
was measured over the whole family and bought only +25 cases while introducing
146 data and 67 bus diffs — a better score for a worse model, which §8/§9
precedent says to revert.  Reverted.

**Recorded as an open mechanism, with its discriminating pair named**, for the
T2 pass that owns the write-side interlock.  The DATA half of this family stays
closed (§9.2's shadow) and the LOOP stays exact; it is only the position of the
closing pop that is open, and only for `cx >= 2`.

### 10.8 Gates (measured, this machine)

The FULL architectural corpus, re-run on the FINAL binary of this pass — §10.1
is in `alu_eval` and §10.3 adds a call site to the shared `loader_decode<Bus>`
body, so both are shared-interpreter changes and had to ride all of it:

| suite | result |
|---|---|
| v0.1 | 169,000 / 169,000 |
| v0.2 | 347,000 / 347,000 |
| v0.3 | 3,699,998 / 3,699,998 |
| v20suite | 3,125,000 / 3,125,000 |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 |
| **total** | **7,341,126** |

plus `make -C sim test` (disasm) PASS, `sw/pla3_check.py` OK (21 checks),
`sw/timed_scenario.py` 6 PASS / 0 FAIL / 12 honest SKIP (unchanged: each rule's
positive-wait half is T2 and each rule's `gap` is an arbitration-frame
quantity).  Zero regressions; the architectural corpus is byte-identical
across the pass.

```
make -C sim test                                          # disasm: PASS
python3 sw/pla3_check.py                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite      # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all   # THE RATCHET
python3 sw/check_boot.py --timed 220                      # THE BOOT REPLAY
python3 sw/timed_scenario.py                              # L1 oracle replay
python3 sw/timed_probe.py  --forms EB --top 8             # first-divergence triage
python3 sw/qcensus.py --forms all --empty --by role --map # the pop census
python3 sw/wchain.py  --forms all --pair MEMW\>MEMW       # the bus-chain census
```

### 10.9 T1 EXIT — status against the gate

| clause | status |
|---|---|
| **166,800 / 166,800 rows-exact at w0** | **NOT MET** — 165,481 of a reachable 166,400 (§10.6 corrects the denominator).  919 short: 907 REP + 12 tails, both with a stated mechanism hypothesis (§10.7, §10.6) and NO fitted patch anywhere |
| **boot replay green** | **205/220 rows, loop period exact**, with the residual reduced to one named mechanism and a rejected alternative measured on both legs (§10.4) |
| **adapters green** | **MET** — `timed_scenario` 6 PASS / 0 FAIL / 12 honest SKIP |
| **ledger closing the stage, scope amendment recorded** | this section; §10.0 |
| functional v0.1+v0.2 after every change, FULL 7.34M after the BCD change and before the final commit | **MET** (§10.8) |
| ratchet may only grow | **MET** — 164,320 → 165,481, monotone at every one of the four steps |

**Milestone A** (`B8 8B 89 F7.6 EB E8` at w0): still MET.  **Milestone B**: 325
of 347 forms are 100 % exact and every form of the S1a tranche is among them.
**Milestone C** (T1 exit): NOT MET, by 919 cases.

### 10.10 T2 handoff

1. **The REP write-side interlock** (§10.7) — the one open mechanism inside the
   w0 suite.  Discriminating pair named: `F3AA` cases 16 and 10.
2. **The SUSP lead** (§10.4) — the boot loop and the v0.1 goldens disagree by
   one row about when a bus-control field reaches the BIU.  Both legs measured,
   both numbers recorded.  This is also `0F39`'s 9 cases and §7.12 item 6.
3. **The wait axis** — M2's status-register release must be re-derived from the
   READY sample rather than from the eval index (§7.2); Milestone A's w1/w3
   legs; every law card's MUST set (§10.0).
4. **S9** — the pin-event exclusion is now 2,600 cases in thirteen forms
   (§10.6).  It needs the HALT display pseudo-cycle (`interrupt_model.md`: BS =
   HALT with an ALE/T1 driving the prefetch pointer, no data phase), the POLL
   pin's 5-clock sampling, and the INT/NMI/RESET event scheduler.
5. **BUSLOCK** — `ClockRow::lock_n` is still a constant; the `f0lock_tranche`
   rows are not replayed.  No non-S9 v0.1 form exercises it, so it is a T2
   stimulus question, not a T1 hole.
6. **§7.6's EA stage** — unchanged from §8.8/§9.4: the five-row demand table is
   now a march of 1- and 2-clock steps (§9.1) but WHY the byte-displacement
   step is the long one is still not derived.

---

## 11. T2a — the wait axis, offline.  ONE INSTANT, and four things hanging off it

This section is the wait-axis stage.  Nothing earlier is retracted.  The two
ratchets, reported together as the stage discipline requires:

| step | v0.1 **w0** rows exact | w1 | w3 |
|---|---|---|---|
| T1 close (§10) | 165,481 | 158 / 1,200 | 162 / 1,200 |
| M2r — the eval instant and its offsets (§11.1) | **165,481** | 874 | 994 |
| the QS port is held through the eval (§11.3) | **165,481** | 925 | 1,097 |
| the completion eval's display clock is not an eval point (§11.2) | **165,481** | 1,046 | 1,097 |
| the OPR release does NOT stretch (§11.4) | **165,481** | 1,148 | **1,200** |
| a pushing fetch owns the QS port until its bytes are in (§11.3) | **165,481** | **1,200** | **1,200** |

**MILESTONE A IS MET**: `B8 8B 89 F7.6 EB E8` are 200/200 at w1 and at w3,
2,400/2,400, and the w0 ratchet did not move by a single case at any step —
every mechanism below is w0-neutral BY CONSTRUCTION, not by luck.

### 11.1 M2r — the wait-state conditional lives in the RIG, not in the part

§7.2 resolved T0's `w == 0 ? 2 : 3 + w` into "one register + one sampling
instant" but refused to promote it past w0 and demanded T2 re-derive the
release point **from the READY sample**.  Done, and the derivation is a read of
the harness's own generator (`hdl/rtl/nec_bus.sv`, the `tick_rise` branch):

```
    at T1 entry:      wait_cnt <= N;  ready_q <= (N == 0)
    at each T3/Tw:    if (wait_cnt) begin wait_cnt <= wait_cnt-1;
                                          ready_q <= (wait_cnt == 1); end
    next_t_state:     from T3 or Tw ->  ready_q ? T4 : Tw
```

so the READY *line* the CPU sees is HIGH for exactly the clocks the T-state
machine may leave for T4 — **from T2 when N = 0, and from the LAST Tw when
N > 0**.  The CPU registers that line at the end of every clock and ONE CLOCK
LATER does two things at once: it RELEASES the status register (that clock
displays PASV) and it runs the COMPLETION EVAL at the clock's end.  So there
is exactly one instant `e` per bus cycle,

```
    e_i = (N == 0) ? 2 : 3 + N          T3 at zero waits, T4 otherwise
```

and every other quantity in the model is a fixed offset from it:

| offset | what happens |
|---|---|
| `e`   | status goes passive; OPR is released to a `-> OPR` row |
| `e+1` | the DISPLAY clock — the winner's status / address / PS |
| `e+2` | the winner's T1, **and** eu_done (read handover, store retire) |
| `e+3` | a fetched byte becomes POPPABLE |

At w0 that reads T3 / T4 / T4+1 / T4+2 — M1, M2 and M3's zero-wait numbers
UNCHANGED.  At w>0 it reads T4 / T4+1 / T4+2 / T4+3, which is mission-H's
**completion-eval deferral** plus **queue-push defer** plus **"post-access EU
schedules stretch by exactly one cycle per waited access"**: three separately
fitted laws that are the same offset seen from three places.  The apparent
N = 0 discontinuity is entirely the rig's counter short-circuiting at zero; the
CPU only ever waits one clock after a level.

*Evidence (the single case that names it):* `B8` case 0 at w1 — before M2r
every queue pop in the case is exactly ONE CLOCK EARLY and the bus geometry is
already right; the whole 13-row window is the push/pop latency and nothing
else.  100 -> 200/200 for `B8`, 17 -> 200 for `8B`.

*Falsifier:* any waited golden where a fetched byte is poppable at its T4+2,
or where a read's data reaches the EU at its T4+1.

**Wait plumbing.**  The model now carries the rig's other two wait sources in
`nec_bus.sv`'s own priority order (replay > random > uniform), all keyed on a
bus-cycle index and latched at T1 ENTRY, so a cycle's wait count belongs to the
order the cycles RUN in, not the order the EU requested them:
`BiuTimed::set_wvec` (explicit per-access vector) and `set_wrand` (16-bit
Galois LFSR, poly 0xB400, seed 0 -> 0xACE1, `n = (l[7:0]*(wmax+1))>>8`, drawn
once per bus cycle).  `v30sim timed-boot --wvec F | --wmax K --wseed S` exposes
both.  The LFSR is validated end-to-end by the ENTER wrand slices (§11.7).

### 11.2 The completion eval's DISPLAY CLOCK is not an eval point — and the grid is NOT the eval cadence

The T2 brief's hypothesis was that the stretched `grid_phase` might BE the eval
cadence.  **Tested first, and FALSIFIED at w0.**  The strong form — every eval,
idle ones included, reserving the next clock as its display slot and so barring
an eval there, i.e. a genuine 2-clock grid — costs the w0 ratchet
**165,481 -> 119,311**.  Idle evals run on EVERY clock; there is no 2-clock
idle grid.  Recorded so nobody re-derives it.

What IS true is the narrow, measured statement: **the COMPLETION eval's display
clock is not an eval point.**  At w0 that clock is T4, which is inside the
cycle and so was never an idle-eval candidate — M1's "T4 is NOT an eval point"
is this same statement, and the model already had it for free from the T-state.
Under waits the display clock is T4+1, an IDLE clock, and the rule has to be
said out loud; it is mission-H's *"the end of that deferred-eval cycle is NOT an
eval point — a request that first asserts inside it waits for the next
idle-cycle end"*.

*Evidence:* `89` case 48 at w1 — the store's status appears two idle clocks
after the fetch's T4, not one.  `89` 176 -> 200/200, `E8` 51 -> 148.

### 11.3 A fetch owns the QS port from its T1 until its bytes are IN

Two conditions in §8.2's F1 collapse into one sentence.  A fetch holds the
queue-status port

* from its T1 **through its completion eval** (`ci <= e_i`), and
* if it PUSHES, for the two clocks its bytes take to land — the push edge
  `e+1` and the absorb clock `e+2`, the clock before they are poppable.

A DOOMED fetch pushes nothing and therefore lets go at the eval, which is why
`EB` case 0 shows the flush `E` on the doomed fetch's T4 at w0.  At w0 the two
absorb clocks are T4 and T4+1 and **the w0 ratchet is identical either way** —
no w0 stimulus separates one absorb clock from two.  The wait axis does:

*Evidence:* `EB` case 9 at w1 — golden `E` on the doomed fetch's T4+1, which is
mission-H's *"a doomed fetch counts as busy through its (deferred) completion
eval — E moves from the doomed fetch's T4 to the following cycle"* (`EB`
149 -> 200/200).  `E8` case 4 at w1 — golden `E` on the push's own status clock
at T4+3, which needs BOTH absorb clocks (`E8` 148 -> 200/200).

### 11.4 The OPR release does NOT stretch — and the wait axis is what proves it

§10.7 left the REP write-side interlock open with the campaign's own distrust
recorded: *"two release points on one register is the shape the campaign
distrusts"*.  The wait axis settles which one release point it is.

A store hands its word to the **AD output latch** at T2 and OPR is free from
T3; how much longer the BUS holds that word out is the memory's business, not
OPR's.  So the release sits at a FIXED cycle-relative index (2) at every wait
level — while eu_done, which is the READY sample, stretches.  That asymmetry is
exactly mission-H's *"eu_done shifts identically"* set against its
*"the trap chain marches on from the ZERO-WAIT completion point (eu_wdone)"*:
**two clocks in one bus cycle, and only one of them is the READY sample.**

*Evidence — `sw/wchain.py --pair MEMW>MEMW` over `F7.6`, whose divide-trap push
chain has two chains differing by exactly the two extra ROM rows between
`01F5 -> 01F9` and `01F9 -> 01FB`:*

| chain | w0 | w1 | w3 |
|---|---|---|---|
| PSW -> PS  (+2 rows) | T4+4 | T4+4 | T4+2 |
| PS  -> PC            | T4+3 | T4+2 | T4+2 |
| either half of a split | T4+1 | T4+2 | T4+2 |

With the release FIXED at index 2 the two issuing rows land at cycle-relative
index 5 and 3 at EVERY wait level, and the eval geometry of §11.1/§11.2 alone
produces all nine numbers.  With the release STRETCHED to the eval they walk
out to T4+5 / T4+4 at w1 — measured, and rejected.  `F7.6` 98 -> 200/200 at w1
and 97 -> 200/200 at w3.

`sw/wchain.py` now LOCATES T4 by scanning instead of assuming `t1+3`, so the
census works under waits at all; that was a real (silent) w0-only assumption.

**REP write-release (T2 handoff item 1): DISCRIMINATED — the wait axis rules
OUT the second release point.**  §10.7's probe wanted the store ROW released at
the previous store's T1/T2 (when the data is DRIVEN); the F7.6 chain census
above shows the release is at the FIXED index 2 and does not move with N, and
the T1-release probe was already measured to buy +25 cases while introducing
213 new diffs.  The 907-case `F3AA` residual therefore does **not** come from a
second OPR release point.  It stays open with its discriminating pair (`F3AA`
cases 16 and 10) intact, and it is now a NARROWER question: what pins the row
engine to the bus at `cx >= 2` if not the OPR register.

### 11.5 The reset entry — the part comes out of RESET SUSPENDED

`timed-boot` committed a prefetch from `0000:0000` during the reset-entry
clocks, before the reset block's FLUSH (01D3) has loaded PS:PC.  It is
INVISIBLE to `sw/check_boot.py`, whose column policy starts at release+8
because the pins float before the first T1 — but it is a whole spurious BUS
CYCLE, and it shifted every wait-vector ordinal by one, which is what made the
case250 L2 replay unresolvable.

The fix is the physical statement: there is no fetch pointer until the reset
block flushes, so the prefetcher comes up SUSPENDED and `flush()` releases it.
Boot replay unchanged at 205/220 with the loop period exact.

### 11.6 L2 — the case250 INS factorial plane, reproduced THROUGH THE SIM

`sw/timed_ins_replay.py` (new).  For each of the 800 cells it regenerates the
fuzz program image offline (`gen_seq.generate` + `check_seq.compose`), rebuilds
the run's per-access wait vector from the recorded LFSR seed, applies the
history permutation and the cell's selected-access wait, drives
`v30sim timed-boot --wvec` from RESET, and resolves the semantic roles the way
the CAPTURE SCRIPT resolves them (by bus kind and address, over the
intervention's neighbourhood — NOT by ordinal, because at high `C1` waits the
CHIP ITSELF reorders `R2` ahead of the second prefetch).

| | offline pilot (reads the chip's own t1/t4/tw) | **through the sim** |
|---|---|---|
| cells resolved | 800 | **800 / 800** |
| write rails (W1 + W2) | 1312 / 1312 | **1312 / 1312** |
| R2 issue | 782 / 800 | **782 / 800** |

**Full pilot parity, computed from the simulator's own bus timings.**  The
R2-issue residue is the pilot's own recorded "grid parity, BIU layer" class,
reproduced rather than fixed — same COUNT (18), same shape (every one of them
is a `C1` or `C2` intervention, i.e. a wait forced onto a PREFETCH cycle
adjacent to the INS, never onto `R1`/`R2`/`W1`), and **12 of the 18 are
literally the same cell**.  Stated exactly, because the difference matters:

```
both        12302 A/B C1 w13 | 12466 A/B C1 w4, C1 w12, C2 w1
            12547 A/B C1 w12 | 12569 A/B C1 w12
pilot only  12302 A/B C1 w1, C2 w0 (delta -1)  | 12547 A/B C1 w2
sim only    12302 A/B C1 w4  | 12547 A/B C1 w5, C2 w3
```

Every sim residual is `+1` (the sim's R2 opens one clock LATE); the pilot's set
contains one `-1` cell.  So the model does not merely inherit the pilot's
arithmetic residue — it has its own, of the same size and in the same
prefetch-intervention family.  Both are the same open question: the `+/-1` on
`R2.T1` that the pilot itself booked to the bus grid.

The STRICT leg (each rail's T1 measured from R1's T4 equal to the frozen chip
capture's same difference) is **1766 / 2624**: `fz12466` 1024/1024 and `fz12569`
256/256 are chip-exact, `fz12547` 368/1024 and `fz12302` 118/320 are not.  The
whole-program measure over the same runs: the sim reproduces **56,736 of
173,556** leading bus cycles in kind+address, of which **55,936** also land on
the same T1 (98.6 % of the agreeing prefix is cycle-exact, i.e. where the sim
agrees at all it agrees to the clock).  Both numbers are T3 inputs.

### 11.7 The ENTER waited tranche, replayed in-sim

`sw/timed_enter_replay.py` (new).  Each of the 154 socket digests is rebuilt
with the rig's own composer, run at the same wait setting — uniform N, **or the
seeded wrand LFSR for the two wrand slices**, which is what validates the LFSR
plumbing end to end — and compared transaction for transaction.

| level | result |
|---|---|
| stack-region MEMW count == nest+1 (the pilot's own check) | **154 / 154** |
| the stack-region MEMW/MEMR (kind, addr, data) walk | **154 / 154** |
| active bus-cycle count of the whole run | **154 / 154** |
| the FULL (kind, addr, data, duration) stream from the anchor | **130 / 154** |

The 24 misses are ONE mechanism and it is a **w0** one: at w0 (and at
`wrand(3,4660)`), for `nest >= 2` only, the chip runs `IOW 254` then
`CODE 274` and the sim runs `CODE 274` then `IOW 254` — a single
prefetch-vs-EU-request ARBITRATION ORDER swap at one eval, with every
transaction before and after identical in kind, address, data AND duration.
At w1/w2/w3/w7 the sim gets the order right, because the later eval lets the
request arrive in time.  Reproduce with

```
python3 sw/timed_enter_replay.py --waits 0 --verbose
```

This is a **third leg of the SUSP-lead conflict** (§10.4, T2 handoff item 2):
the boot loop and now the ENTER store stub both want the EU's bus-control field
to reach the BIU one row earlier than the v0.1 goldens permit, and both are
whole-program stimuli.  Two independent legs pulling the same way against
169,000 goldens is a much sharper statement of the conflict than §10.4 had, and
it says the answer is NOT a uniform one-row lookahead (v0.1 costs 3,446 cases
for that) but something that distinguishes these evals from v0.1's.  **Not
patched.**

The HALT bus pseudo-cycle is still scaffolding **S8/S9**: the sim executes the
store stub's `HLT` architecturally and then keeps prefetching instead of
parking the bus, so the chip's trailing `HALT` transaction is OUT of the
compared prefix (`halt_display 0/154`, reported as the missing mechanism it is,
not counted as a pass).

### 11.7a The ENTER pilot's GRANT LAW is the eval geometry — it emerges

`sw/enter_ucode_pilot.py` carries a fitted grant law as one of its seven
constants:

```
    bus slots exist at busfree+1 and busfree+3; after that the bus is
    free-running and T1 = req exactly.
```

That is not a law, it is §11.1 + §11.2 read off the timeline.  With `busfree`
= the previous cycle's T4 and the eval instant at `e = T4-1` at w0:

| the request is ready... | the eval that takes it | its T1 |
|---|---|---|
| by the end of `e` (= busfree-1) | the COMPLETION eval | `e+2` = **busfree+1** |
| after that | *(busfree is the DISPLAY clock — dead, §11.2)* | — |
| by the end of busfree+1 | the first idle eval | **busfree+3** |
| later | every clock is an eval | `req+2` — free-running |

The "2-clock grid running out" the campaign's own guiding-principle note cites
as a precedent is exactly the DEAD DISPLAY CLOCK, and the third-slot-onward
free-running is just "there is nothing left to skip".  Nothing in the sim
encodes `busfree+1` or `busfree+3`.

**And it makes a wait-axis prediction, which the tranche confirms**: under
waits `e = T4`, so the two slots move to `busfree+2` and `busfree+4` (the
pilot's constants were fitted on the w0 `C8` goldens and would be wrong under
waits if written down).  The waited ENTER replay's walk is 154/154 and its
active-cycle count 154/154 at w0/w1/w2/w3/w7 and both wrand slices — the whole
push chain lands on the moved slots.

### 11.8 L1 adapters — the positive-wait halves are UN-SKIPPED

`sw/timed_scenario.py` was 6 PASS / 0 FAIL / **12 SKIP**, half of those skips
being "each rule's positive-wait half -> T2".  Reading the frozen files settles
what that half contains: in EVERY rule of both oracles `positive_wait_qs` is
`zero_wait_qs` shifted by exactly **+1**, and `positive_wait_gap ==
zero_wait_gap + 1` (and `positive_wait_code_gap` likewise in drain-v2).  That
is M2r's own offset seen in the oracle's frame — the oracle counts from the
selected cycle's T4 and the completion eval moves from T4-1 to T4 when that
cycle is waited, so everything after it, the opening `F` pop included, shifts by
one.  In the ledger's OPENING-F frame the two schedules are therefore
IDENTICAL, and the whole content of the positive-wait half is that shift.

Each class is now replayed at **w0, w1 AND w3** — running both positive legs is
what makes it non-vacuous, since the oracle's state input is the BOOLEAN
"selected wait is zero" and the schedule must not depend on N:

```
python3 sw/timed_scenario.py        # 18 PASS, 0 FAIL, 9 SKIP
```

Still skipped, and said so: each rule's `gap` (`t1_from_selected_t4`) is a BUS
quantity in the ARBITRATION frame needing the REP-successor scenario the
oracles were captured in, and `decoder-drain-oracle-v2` is stated entirely on
that frame.  Its wait half is the same `+1`, so the LAW is not in doubt; the
STIMULUS is missing.

### 11.9 The frozen wvec baseline is HALF VACUOUS — an adjudication, not a gate

`sw/timed_wvec_gate.py` (new) replays `docs/notes/biu_rebuild_wvec_baseline.json`
— 22 fuzz seeds x 4 explicit per-access wait vectors, 4,200 clocks each — and
recomputes the freeze's own cadence-sensitive digest (`bs, tw, addr, npops,
gap-from-previous-T1`) from the sim.  Building it exposed a defect in the
BASELINE:

| wvec config | distinct digests over 22 DIFFERENT programs |
|---|---|
| `ws0:wmax0` | 22 |
| `ws5:wmax1` | 22 |
| `ws7:wmax3` | **1** |
| `ws11:wmax7` | **1** |

Twenty-two different programs cannot produce one bus stream.  **Half of the
frozen wvec corpus (44 of 88 cells) is vacuous** — the signature of the
`wv_of` bug the law cards themselves record ("the landing's census predates the
`wv_of` bug fix").  The mutation battery's `wvec` column is not thereby
invalidated — its two discriminating directed seeds fire at `ws5:wmax1`, in the
sound half — but the corpus must be re-frozen before it is used as a reference
again.  Recorded here rather than silently replayed.

Against the two SOUND configs the sim is not digest-identical anywhere (0/44),
and the whole-program bus-cycle count diverges **in both directions**: `+6.0 %`
at `ws0:wmax0` (all-zero waits) and `-12.2 %` at `ws5:wmax1`.  A two-directional
whole-program cadence error is precisely `biu_model.md`'s Round-3 A2 signature
("the prefetch-resume divergence FLIPS DIRECTION with aperiodic leading-phase
parity").  **This is a T3 input, not a T2 verdict**: the reference is TBR-class,
its Verilator TB was not rebuilt in this pass, and no chip capture backs these
88 cells.

### 11.10 Law cards — what is now gated, and what still cannot be

§10.0 moved the MUST set C1-C7 / C9-C12 to T2 because every one of them is
stated on a wait vector.  With the wait axis closed, the honest position is:

| card | status after T2a |
|---|---|
| **C9** LC4 general lead reservation (WRITE) | **the mechanism is implemented and exercised**: F2's one-row-early bus-control decode (`post()` -> `withdraw_fetch()`) is what §8.2 replaced the per-form `S_RSV` table with, and it now runs at w1/w3 in every `89`/`E8`/`F7.6` case (2,400/2,400).  Its wait-vector cell is also the §11.7 ENTER finding, which is the one place it is measurably WRONG (w0, whole-program) |
| **C1/C2** LC1 resume steady-state gap / fill ramp | **NOT implemented and deliberately so** (§7.4).  The w0+w1+w3 goldens do not demand them; the wvec corpus that would is the one §11.9 shows is half vacuous.  Their real stimulus is the T3 fuzz corpus |
| **C3** LC1 cidle at N=8 / N=12 | no stimulus in this repo's offline corpora (the Arm-C sled was a board capture; nothing frozen) |
| **C4/C5** LC2 aged-band PAUSE / GO | **NOT implemented** (§7.4), and their gate is the directed seed `fz90364` in the wvec corpus — replayable now that `--wvec` exists, but there is no CHIP reference for it, only the RTL baseline of §11.9 |
| **C6/C7** LC3 RMW-write Tw parity | board-by-construction (`uRMW`), unchanged.  No golden carries an RMW mem-write ready-at-T4 with controlled Tw parity |
| **C10/C11/C12** LC4 late reservation / owns_slot / pf_rsv_lead | CEN-provenance, gated on the same wvec corpus; `fz90270` is replayable, reference is not |

**The honest summary: the law cards' MUST set cannot be turned into sim unit
gates in T2a, and the reason is provenance, not effort.** Nine of the eleven
are stated against a chip decision on a wait-vector stimulus for which this
repo holds no frozen CHIP capture — only an RTL baseline, half of which
§11.9 just showed to be vacuous.  Building a gate on that would be exactly the
cannot-fail gate §9.6 refused to build at T1.  What T2a delivers instead is
the REPLAY MACHINERY those cards need (`--wvec`, `--wmax/--wseed`,
`timed_wvec_gate.py`, `timed_ins_replay.py`), so the cards become gateable the
moment T2b banks the chip captures.  **The board probe specs are in §11.12.**

### 11.11 Gates (measured, this machine)

The FULL architectural corpus, re-run on the FINAL binary of this pass.  Every
mechanism in 11.1-11.4 is inside `BiuTimed` (the TIMED bus only) and 11.5 is
inside `timed-boot`, so none of them touches the shared interpreter -- but the
corpus was re-run anyway, as the standing discipline requires:

| suite | result |
|---|---|
| v0.1 | 169,000 / 169,000 |
| v0.2 | 347,000 / 347,000 |
| v0.3 | 3,699,998 / 3,699,998 |
| v20suite | 3,125,000 / 3,125,000 |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 |
| **total** | **7,341,126** |

plus `make -C sim test` (disasm) PASS and `sw/pla3_check.py` OK (21 checks).
Zero regressions.

```
python3 sw/ucsim_check.py --suite tests/v30/v0.1                 # 169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                 # 347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                 # 3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite             # 3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea
make -C sim test                                # disasm gate: PASS
python3 sw/pla3_check.py                        # OK (21 checks)
python3 sw/timed_gate.py --suite tests/v30/v0.1                 # 165,481 (w0)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --waits 1    # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --waits 3    # 1,200/1,200
python3 sw/timed_scenario.py                    # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_ins_replay.py --raw            # rails 1312/1312, R2 782/800
python3 sw/timed_enter_replay.py                # walk/pushes/active 154/154
python3 sw/timed_wvec_gate.py --wvecs 0,1       # 0/44 -- see 11.9
python3 sw/check_boot.py --timed 220            # 205/220, loop period exact
python3 sw/wchain.py --suite tests/v30/v0.1-w3 --forms F7.6 --pair MEMW\>MEMW
```

### 11.12 T2b handoff — the board probes, specified

1. **The SUSP-lead discriminator (the campaign's sharpest open conflict).**
   Three legs now disagree with v0.1: the boot loop (§10.4, one extra prefetch
   per iteration), `0F39` (9 cases), and the ENTER store stub (§11.7, 24 of 154
   digests, w0, `nest >= 2`).  All three are WHOLE-PROGRAM; v0.1 is
   single-instruction windows.  **Probe:** capture the ENTER `nest = 2`,
   `ctx = 1`, w0 case on the socket with the FULL per-clock row stream (not the
   digest), and read off the exact clock on which the `IOW` request reaches the
   BIU relative to the preceding prefetch's T3 eval and its display clock.  One
   capture decides whether the EU's bus-control field leads by one ROW (the
   boot leg's ask) or whether the prefetch's commit is one clock late.  Cheap:
   one image, one wait setting, one capture.
2. **Re-freeze the wvec corpus (§11.9).**  `ws7:wmax3` and `ws11:wmax7` are
   degenerate in the frozen baseline.  Re-run `biu_rebuild_wvec_freeze.py`
   after confirming `wv_of` and the TB build, and — this is the point — bank a
   CHIP capture for at least the two directed seeds `fz90270` / `fz90364` at
   `ws5:wmax1`, which converts C4/C5/C12 from RTL-referenced to silicon-
   referenced and makes them sim-gateable.
3. **The HALT bus pseudo-cycle (S8/S9).**  `interrupt_model.md` describes it
   (BS = HALT, an ALE/T1 driving the prefetch pointer, no data phase) but no
   frozen capture pins it under waits.  The ENTER store stub ends in `HLT` in
   all 154 digests, so the stimulus already exists: capture the per-clock rows
   from the last `IOW` to 40 clocks past the `HLT` at w0/w1/w3.
4. **The `F3AA cx >= 2` row-engine pin (§10.7, narrowed by §11.4).**  It is NOT
   a second OPR release point.  **Probe:** the discriminating pair `F3AA`
   cases 16 and 10 at w1 and w3 — if the closing pop stays at the last store's
   T4+2 at w0 and moves to T4+3 under waits it rides the eval; if it stays at
   +2 it rides a fixed cycle index, like the OPR release does.
5. **C3's Arm-C sled** (N = 8 and N = 12 fetch-limited sled, resume-gap
   histogram) — nothing frozen; needs the board or it stays ungated.

### 11.13 Ledger delta against the T2 handoff (§10.10)

| §10.10 item | outcome |
|---|---|
| 1. REP write-side interlock | **DISCRIMINATED** (§11.4): the wait axis rules out the second release point; the residual is narrowed, not closed |
| 2. SUSP lead | **THIRD LEG FOUND** (§11.7), and **the wait axis takes the v0.1 side**: w1 and w3 are 1,200/1,200 with NO lookahead, so the waited goldens add 2,400 cases to the "no one-row lead" column and none to the boot loop's.  The conflict is now three whole-program legs (boot, `0F39`, ENTER) against 171,400 windowed cases; probe spec written (§11.12.1) |
| 3. The wait axis: M2's re-derivation, Milestone A w1/w3, the law cards | **re-derivation DONE from the rig's own generator** (§11.1); **Milestone A MET** 2,400/2,400; **law cards: provenance-blocked, argued** (§11.10) |
| 4. S9 pin events | unchanged; the HALT half now has a named stimulus (§11.12.3) |
| 5. BUSLOCK | unchanged — `lock_n` is still a constant, no non-S9 stimulus |
| 6. §7.6's EA stage | unchanged; the wait axis did not touch the decoder march |

**The 12 w0 tails and the 907-case REP residual are unchanged at 165,481.**

## 12. T2b — the wait axis, ON THE BOARD.  The campaign's first board contact

Board discipline for this whole section: SINGLE WRITER (checked, no foreign
`v30run serve` / `v30ctl` runner), **socket chip only** (`use_core=False`), **no
FPGA flashing anywhere**, `board_idle()` after every session.  Every capture is
retained under `sw/testdata/t2b/` with the raw 64-bit capture words and a
sha256 beside the derived record.

### 12.0 PRE-REGISTRATION — written and committed BEFORE the board was touched

The stage's own discipline (§S4r, and the plan's "pre-registration discipline …
freeze before run") applied to a board stage: each probe's expected values are
written down *first*, so a post-hoc reading of an ambiguous capture cannot be
dressed up as a prediction.  What follows is that register, verbatim.

#### P1 — the SUSP-lead discriminator (§11.12.1)

*Stimulus.* `char_enter` ENTER case, `nest = 2`, both BP/SP contexts
(ctx0 = the second preparation history the blackbox protocol demands), w0,
socket, FULL per-clock row stream.  5 repetitions; 4 MHz (`div=8`) **and**
8 MHz (`div=4`).

*The sim's own geometry for ctx1/nest2/w0*, which is what the chip is measured
against (absolute clocks; `c` = the `CODE 0x110` prefetch's T1):

```
    CODE 0x110   T1 = c        T4 = c+3
    CODE 0x112   T1 = c+6      T4 = c+9      (= 0x110's T4+3: the FIRST IDLE eval)
    IOW  0x00FE  T1 = c+10                   (= 0x112's T4+1: its COMPLETION eval)
```

The chip's digest instead runs `IOW 0x00FE` **before** `CODE 0x112`.  The three
readings, pre-registered with the clock each predicts:

| | reading | prediction |
|---|---|---|
| **A** | the EU's bus-control field is ready EARLIER — the IOW request makes the first idle eval and out-ranks the prefetch | chip `IOW` T1 = **c+6**, every clock strictly before c+6 identical to the sim, `CODE 0x112` displaced to c+10 or later |
| **B** | the prefetch's commit is one clock LATE / the prefetch is not eligible at that eval | the first divergence appears **at or before c+3** — the 0x110 cycle itself, or the gap out of it, differs |
| **C** | the request is ready a full further row early and takes the COMPLETION eval of 0x110 | chip `IOW` T1 = **c+4** (= 0x110's T4+1) |

*Second, independent observable, recorded either way:* the QS pin sequence.  In
the sim the byte that arms the IOW is popped (`S`) at c+6, on `CODE 0x112`'s own
T1.  If the chip pops that byte at an EARLIER clock than the sim does, the cause
is a QUEUE (push/pop-latency) difference and NOT an EU-side row lead, and the
"SUSP lead" framing is itself wrong.  This is the falsifier for all three
readings at once.

*Promotion rule.* A reading is adopted only if it holds bit-identically over the
5 repetitions at BOTH frequencies AND in BOTH preparation histories (ctx0/ctx1),
and only if landing it in the sim leaves the w0 ratchet at 165,481 and w1/w3 at
1,200/1,200.  If it cannot reconcile all three legs (boot, `0F39`, ENTER) that
is reported as a discovery, not patched away.

#### P2 — the wvec corpus, re-frozen against SILICON

*Finding that motivates the change of reference:* §11.9 recorded that
`docs/notes/biu_rebuild_wvec_baseline.json` is degenerate at 2 of its 4 configs.
Offline, before the board: the **timed sim produces 22 DISTINCT digests at ALL
FOUR configs** (checked on 6 seeds per config), so the stimulus is not
degenerate — the defect is in the reference.  The frozen baseline is TBR-class
(a Verilator-TB reference), so the campaign-correct repair is not to re-freeze
against the TB at all; it is to **freeze the corpus against the CHIP**, which
converts C4/C5/C12 from RTL-referenced to silicon-referenced in one move.

*Stimulus.* The 22 seeds (`fz90000-90019` + the directed `fz90270`, `fz90364`)
x the 4 explicit per-access wait vectors (`ws0:wmax0`, `ws5:wmax1`, `ws7:wmax3`,
`ws11:wmax7`), 4,200 clocks, socket, `wvec` replay.

*Predictions.*
1. the chip produces **22 distinct digests in every one of the 4 configs** — in
   particular at `ws7:wmax3` and `ws11:wmax7`, where the TB baseline collapsed to
   one.  A chip collapse would instead mean the stimulus IS degenerate and the
   sim is the thing that is wrong; that outcome is reported, not smoothed.
2. every capture is bit-repeatable across repetitions.
3. the two directed cells (`fz90270`, `fz90364` at `ws5:wmax1`) reproduce
   identically at 4 MHz and 8 MHz — the promotion condition for using them as the
   C4/C5/C12 silicon reference.

#### P3 — the HALT bus pseudo-cycle (S8/S9, §11.12.3)

*Stimulus.* The SAME ENTER traces as P1 — the store stub ends in `HLT` in all
154 digests — at w0, w1 and w3, read from the last `IOW` to 40 clocks past it.

*Predictions.*
1. the chip shows a bus cycle with `BS = HALT (3)` — a T1 with an address phase
   and **no data phase**.
2. **the HALT pseudo-cycle does not take wait states**: its clock length is the
   same at w0, w1 and w3.  Falsifier: it stretches with N like an ordinary cycle,
   which would make it a real access and not a display.
3. nothing is prefetched after it (the bus parks).

#### P4 — `F3AA cx >= 2`: does the closing pop ride the eval? (§11.12.4)

*Stimulus.* The named discriminating pair, `F3AA` v0.1 cases **16** and **10**
(seed base `v30-v0.1`, re-emitted at the same index so the program is
byte-identical), captured from the socket at **w1** and **w3**.

*Predictions.*  At w0 the golden closing pop is at the last store's **T4+2** in
all 138 `cx = 2` cases (§10.7).
- **A — it rides the eval:** at w1 and w3 the pop moves to **T4+3** (the eval
  moves T4-1 -> T4, §11.1, so everything hanging off it shifts by exactly one).
- **B — it rides a fixed cycle-relative index,** as the OPR release does
  (§11.4): it stays at **T4+2** at every wait level.

#### P5 — C3's Arm-C sled (§11.12.5)

*Stimulus.* `sw/class5_armc.py` at **N = 8** and **N = 12**, 20 programs each,
CODE-only waits converged to a fixed point ON THE CHIP STREAM, socket.

*Prediction (this is C3's card text, and it has a 2026-07-17 unfrozen board log
behind it — the point of this probe is to FREEZE it with a sha, not to discover
it):* the chip's `cidle` distribution **pins at 3**: N=8 -> 22:12, N=12 -> 28:2,
within sampling.  Falsifier: a distribution centred on 4, which is what the
`q_aged`-blackout staged path can emit and the direct path cannot.

### 12.1 P1 — the SUSP-lead conflict is RESOLVED, and it was never an EU lead

`sw/t2b_board.py p1` — ENTER `nest = 2`, both BP/SP contexts, w0/w1/w3, 5
repetitions at 4 MHz **and** 8 MHz, full per-clock rows, raw 64-bit records
retained (`sw/testdata/t2b/p1-susp/`, SHA256SUMS beside them).  Every cell is
bit-repeatable across its five repetitions and identical across the two
frequencies.

**A protocol correction, measured not assumed.**  The first attempt reported
`freq_identical = False`.  The difference is 249 of 4,063 rows and lives in
exactly two fields: `rd_n` and the raw `bs_late`.  Both are WITHIN-CYCLE pulses
read at a fixed sampling edge, so halving the clock divider moves the sampler
relative to them.  `rd_n` was then checked for independent content and has
none: at `div=8` it is an exact function of `(t_state, bs)` over the whole
trace (0 ambiguous cells) and at `div=4` exactly one cell is ambiguous
(`T3/PASV`, the read data phase) — the sampling edge racing the strobe.  Both
fields are therefore excluded from the stability projection and the exclusion
is recorded here rather than buried in the tool.

**What the capture shows.**  Against the sim, ctx1/nest2/w0:

```
      chip                        sim
196   T4 PASV   (0x10E's T4)      T4 PASV
197   TI PASV  F                  TI PASV  F      <- the F pop
198   TI PASV                     TI CODE 0x110   <- SIM COMMITS HERE
199   TI CODE 0x110               T1 CODE 0x110
200   T1 CODE 0x110               T2 ...
```

The two are **clock-identical for 197 clocks** and part on one thing: the eval
at the end of clock 197.  The sim grants a prefetch there; the chip does not,
and grants at 198.  Everything downstream — the chip running `IOW 0x00FE`
before `CODE 0x112`, which is the 24-digest ENTER symptom — follows from that
single clock, because by the time the chip's prefetch is eligible the store
stub's IOW request has arrived and outranks it.

Against the pre-registration (§12.0 P1): **reading B**, and the second
observable settles it — through the whole divergence window the `F` and `S`
pops are on the SAME ABSOLUTE CLOCKS in chip and sim (197 `F`, 200 `F`,
205 `S`), even where the bus geometry around them has already parted.  **The EU is exactly where the model puts it.  The prefetcher is
one eval early.**  So the "SUSP lead" framing of §10.4 / §11.7 — the EU's
bus-control field reaching the BIU one row sooner — is WRONG, and the wait
axis's vote for the v0.1 side (§11.13 item 2) was right for the wrong reason.

**M6 — the mechanism.  A fetch's bytes are written into the queue on T4+1, and
that clock is not a prefetch-grant point.**  One clock, keyed to **T4**, not to
the completion eval.  The consequence is one wait-independent number:

```
    the earliest eval that may resume a prefetch after a pushing fetch
    is T4+2, and that fetch's T1 opens at T4+4 — at EVERY wait level.
```

That is a FIXED CYCLE-RELATIVE INDEX, and it joins two others measured the same
way: the OPR release at index 2 (§11.4) and the `F3AA` closing pop at T4+2
(§12.4 below).  Three quantities, three independent stimuli, all pinned to the
cycle and none of them riding the eval.

The keying matters and was measured, not chosen.  Keyed to the eval
(`[e+1, e+2]`) the block gives a minimum resume of T4+2 at w0 but T4+3 under
waits, and the Arm-C sled (§12.5) says the chip's minimum is T4+2 at N = 8 and
N = 12 as well — a `cidle` of 3, which an eval-keyed block cannot emit.  Keyed
to T4 both regimes come out right.

The window is a SEPARATE pair of fields from §11.3's QS-port hold for one
measured reason: a FLUSH discards the bytes, so nothing is written and the
redirect prefetch is not held off — while the QS port stays busy anyway.
Clearing the QS window at the flush costs 6,848 `qop` rows; NOT clearing the
scheduler window costs 1,555 cases, and every one of them is a branch form
(`E9 EA EB E2 E3 70-7F`).

**All three legs of the conflict close on it, together:**

| leg | before | after |
|---|---|---|
| the boot loop (§10.4) | 205 / 220 rows | **220 / 220, loop period exact** |
| `0F39` (§10.6's tail) | 491 / 500 | **500 / 500** |
| the ENTER waited tranche (§11.7) | full 130 / 154 | **152 / 154** |
| v0.1 w0 ratchet | 165,481 | **165,490** |
| v0.1-w1 / -w3 | 1,200 / 1,200 | **unchanged, 1,200 / 1,200** |

**Falsified along the way, recorded so nobody re-derives them:**
- *the occupancy the prefetch decision reads is a REGISTER (a pop is visible one
  clock later)* — costs `B8` 500 -> 250; the primed-window cases show the chip
  granting on the same clock as a pop.
- *the block runs for BOTH landing clocks, `[e+1, e+2]`, with the QS window
  shared* — the branch forms above.
- *the block starts at the eval, `[e, e+2]`* — kills w0 back-to-back chaining.

**The residual, named exactly.**  2 of 154 ENTER cells — ctx0 and ctx1,
`nest = 4`, `wrand(3, 4660)` — still show the same `IOW`/`CODE` swap.  Both are
a 2-wait fetch's own COMPLETION eval at occupancy 4 with all four bytes already
counted; the chip declines to chain there and the model chains.  A matched w1
cell (occupancy 2) has the chip chaining at the same geometry, so the
discriminator is occupancy, not the eval — and no rule tried here separates
occupancy 4 at a waited completion eval from occupancy 4 at a w0 one, where the
chip DOES chain.  Left open with its two cells and its discriminating pair.

### 12.2 P2 — the wvec corpus is re-frozen AGAINST SILICON, and why the old one collapsed

§11.9 found `docs/notes/biu_rebuild_wvec_baseline.json` degenerate at 2 of its
4 configs.  Two offline checks located the fault before the board was touched:

1. the **timed sim** produces 22 DISTINCT digests at ALL FOUR configs — so the
   stimulus is not degenerate;
2. re-running `biu_rebuild_wvec_freeze.py` today does not reproduce the
   collapse either, but produces something worse: an access count that is
   **independent of the wait vector** (fz90000: 201 / 200 / 198 accesses at
   `wmax` 0 / 1 / 3).  The `Vtb_v30_core` binary is from 2026-07-31 and the RTL
   under it has been modified since; the TB reference is not a controlled
   artifact.

So the repair is not to re-freeze against the TB at all.  `sw/t2b_board.py p2`
freezes the corpus **against the CHIP** — 22 seeds x 4 explicit per-access wait
vectors, socket, `use_core=False`, `sw/testdata/t2b/p2-wvec/`:

| config | distinct digests over 22 programs |
|---|---|
| `ws0:wmax0` | **22** |
| `ws5:wmax1` | **22** |
| `ws7:wmax3` | **22** (the old baseline: 1) |
| `ws11:wmax7` | **22** (the old baseline: 1) |

All 88 cells bit-repeatable; the two directed law seeds (`fz90270`, `fz90364`
at `ws5:wmax1`) promoted with 5 repetitions at 4 AND 8 MHz.  Pre-registration
prediction 1 CONFIRMED: the collapse was the reference, not the stimulus.
`sw/timed_wvec_gate.py` now scores against this silicon freeze by default
(`--tb` for the old one).

**And it exposed a much larger error in §11.9's own numbers.**  The chip runs
~183 bus cycles per 4,200-clock program; the old TB baseline recorded ~700 and
the sim was emitting ~840.  The reason is §12.3: the programs HALT at about
clock 950 and the chip parks the bus, while the model kept prefetching for the
remaining 3,000 clocks.  Cut at the chip's own HALT clock, `fz90000:ws0:wmax0`
is **sim 201 vs chip 200**.  §11.9's "+6.0 % / −12.2 %, a two-directional
whole-program cadence error, the Round-3 A2 signature" was an artifact of a
missing mechanism plus a broken reference and is **RETRACTED**.  Against
silicon, with the HALT modelled:

```
python3 sw/timed_wvec_gate.py     # access count 78/88, bus cycles -3.6 %
                                  # digest identical 0/88  (a T3 input)
```

### 12.3 P3 — the HALT bus pseudo-cycle, MEASURED, and S8/S9 CLOSED

The same P1 captures carry it (the ENTER store stub ends in `HLT`), at w0, w1
and w3 x two preparation histories.  What the pins say:

| | measured |
|---|---|
| status | `BS = HALT` for exactly **two clocks** — the display clock and T1 — passive from T2, at every wait level |
| T1 | UBE **high** (no data phase); A15-0 = the LAST FETCH's address; A19-16 = the segment code (2 = CS), never an address phase on the upper nibble |
| position | the display lands on the previous cycle's **e+2** at w0, w1 and w3 alike — one clock later than a granted cycle's display |
| length | the RIG runs a full T-state cycle over it and **DOES insert Tw** (T1..T4 = 4 / 5 / 7 clocks at w0 / w1 / w3) |
| after | the bus PARKS: zero non-passive status rows for the rest of the capture |

The pre-registered prediction 2 (*"the HALT pseudo-cycle does not take wait
states"*) is **FALSIFIED**: the rig treats it as a bus cycle and stretches it,
consuming a wait draw and a bus-cycle ordinal.  What IS wait-independent is the
CPU's side — the 2-clock status display.  Predictions 1 and 3 hold.

The position has a simple reading and it is the one implemented: **HALT is not
a bus request that goes through the arbiter.**  The `HLT` micro-row drives the
status register directly, so it takes the register on the first clock the
register is FREE — the bus idle and not the completion eval's display slot.
That is `e+2` at w0 (where `e+1` is T4, inside the cycle) and `e+2` at w>0
(where `e+1` is the display slot), which is exactly what the pins show at all
three wait levels without a special case.

Landed in `sim/biu_timed.{h,cpp}` (`Access::is_halt`, `halt_pending_`) and
`sim/timed_runner.cpp`.  **Scaffolding S8/S9 is REMOVED.**  With M6 and the
HALT together, all four captured P1 cells are **clock-identical to the socket
over the whole 4,063-clock capture** — reset entry, the ENTER walk, the store
stub, the HALT and the parked bus — and `halt_display` goes 0/154 -> **154/154**.

### 12.4 P4 — `F3AA cx >= 2`: the closing pop rides a FIXED INDEX, not the eval

`sw/t2b_board.py p4` re-emits the named discriminating pair (`F3AA` v0.1 cases
**16** and **10**, seed base `v30-v0.1`, byte-identical programs) from the
socket at w0, w1 and w3 (`sw/testdata/t2b/p4-f3aa/`).  Offset from the LAST
store's T4 to the window-closing `F` pop:

| case | w0 | w1 | w3 |
|---|---|---|---|
| `F3AA` 16 | T4+2 | **T4+2** | **T4+2** |
| `F3AA` 10 | T4+2 | **T4+2** | **T4+2** |

**Pre-registered reading B.**  It does NOT ride the eval (which would have
moved it to T4+3 under waits); it sits at a fixed cycle-relative index, exactly
as the OPR release does (§11.4) and as M6 does (§12.1).  §10.7's open question
— *"what pins the row engine to the bus at `cx >= 2` if not the OPR register"*
— is answered in KIND: a fixed index, one clock tighter than OPR's.

And the model, on the same six cases:

| case | golden | sim | row diffs |
|---|---|---|---|
| 16 / 10 at w0 | T4+2 | T4+1 / T4+3 | 3 each |
| 16 / 10 at **w1** | T4+2 | **T4+2** | **0** |
| 16 / 10 at **w3** | T4+2 | **T4+2** | **0** |

So the 907-case REP residual is **w0-only**: under waits the bus is slow enough
that the row engine's free-run is no longer the binding deadline and the model
lands on the silicon index by itself.  Not landed as a mechanism — §10.7
measured that the obvious form (releasing the store ROW at the previous store's
T1) buys +25 cases for 213 new diffs, and the campaign reverts a better score
for a worse model.  It is now a much narrower question with a wait-axis answer
attached.

### 12.5 P5 — C3's Arm-C sled, re-captured and FROZEN

`sw/class5_armc.py --Ns 8 12 --nprog 20`, socket, CODE-only waits converged to
a fixed point on the chip's own access stream.  Frozen with a sha at
`sw/testdata/t2b/p5-armc/` (4,432 events).

| N | chip `cidle` distribution | verdict |
|---|---|---|
| 8 | `{3: 22, 4: 12, 5: 8, 12: 1}` | chip PINS AT 3 |
| 12 | `{3: 28, 4: 2}` | chip PINS AT 3 |

**Pre-registered prediction CONFIRMED, and bit-identical to the unfrozen
2026-07-17 board log** (22:12 and 28:2) — an independent re-capture two weeks
later reproducing the card's numbers exactly.  C3 now has a frozen silicon
reference instead of a log.

### 12.6 Law cards — the MUST set as SIM gates on silicon (`sw/timed_lawcards.py`)

§11.10's position was *"the cards cannot be turned into sim unit gates in T2a,
and the reason is provenance, not effort."*  T2b banks the provenance, so the
cards are now SCOREABLE — and most of them score RED.  That is the honest
result and it is strictly more informative than being unscoreable.

| card | verdict | on what |
|---|---|---|
| **C1** LC1 steady-state gap | **RED** | the frozen Arm-C sled.  The `cidle = 3` pin is now REACHABLE (M6 — before T2b the model could not emit 3 at high N at all) but the PAUSE POPULATION is not: sim 12 vs chip 43 events at N=8, 1 vs 30 at N=12.  The model still resumes far more eagerly than the part |
| **C2** LC1 fill ramp | **UNRESOLVED** | the ramp needs a queue-fill transient the sled's steady state does not isolate |
| **C3** LC1 cidle pin | **RED** | same sled, same reason as C1 |
| **C4/C5** LC2 aged-band PAUSE / GO | **RED** | the directed seed `fz90364` at `ws5:wmax1`, now a promoted silicon cell: bus-cycle COUNT identical (139/139), per-cycle digest differs |
| **C6/C7** LC3 RMW Tw parity | **UNRESOLVED** | board-by-construction (uRMW).  No golden, no fuzz seed and no T2b capture carries an RMW mem-write ready-AT-T4 with a controlled Tw parity |
| **C9** LC4 general lead reservation | **GREEN** | 2,400/2,400 at w1/w3 plus, now, the ENTER store stub's own store-vs-prefetch cell at w0 — 4/4 P1 cells clock-identical to the socket |
| **C10** LC4 late reservation yields | **RED** | rides the same directed wvec cells as C12 |
| **C11** LC4 owns_slot | **UNRESOLVED** | an ENUMERATED source set; no directed capture isolates a single source.  `P-LC4-matrix` stays booked |
| **C12** LC4 pf_rsv_lead | **RED** | `fz90270` at `ws5:wmax1`, promoted silicon cell: count 187/187, digest differs |

**1 GREEN / 6 RED / 4 UNRESOLVED.**  The six REDs are one statement: the model
gets the bus-cycle IDENTITY and COUNT right and the per-cycle CADENCE wrong,
and the specific shape of the error is that it resumes the prefetch too
eagerly — LC1/LC2, which §7.4 and §11.10 both record as deliberately
unimplemented.  That is T3's subject, and it now has silicon to aim at.

### 12.7 Gates (measured, this machine)

| suite | result |
|---|---|
| v0.1 arch | 169,000 / 169,000 |
| v0.2 arch | 347,000 / 347,000 |
| v0.3 arch | 3,699,998 / 3,699,998 |
| v20suite arch | 3,125,000 / 3,125,000 |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 |
| **total** | **7,341,126** |

```
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all              # 165,490 (w0, +9)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1 # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3 # 1,200/1,200
python3 sw/timed_enter_replay.py     # walk/pushes/active/halt 154/154, full 152/154
python3 sw/check_boot.py --timed 220 # MATCHES over 220 rows, loop period exact
python3 sw/timed_scenario.py         # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_ins_replay.py --raw # rails 1312/1312, R2 780/800, vs-chip 1768/2624
python3 sw/timed_wvec_gate.py        # vs SILICON: count 78/88, cycles -3.6 %, digest 0/88
python3 sw/timed_lawcards.py         # 1 GREEN / 6 RED / 4 UNRESOLVED
python3 sw/t2b_board.py p1|p2|p4|idle          # the board probes
python3 sw/class5_armc.py --Ns 8 12 --nprog 20 # P5
```

**Board session log.**  One session, five probes, roughly **650 socket
captures** and **under two minutes of actual board time** (the persistent serve
runner turns a 4,063-clock capture into ~0.3 s, so the two-hour budget was
never the constraint -- the session's wall time was analysis, not the board).  Single-writer checked
before contact (no foreign `v30run serve` / `v30ctl`); socket only
(`use_core=False`) on every capture; nothing flashed; no bitstream touched.
`b1_recapture.board_idle()` run at the end — **board idle, use_core=0,
confirmed**.

### 12.8 Ledger delta against the T2b handoff (§11.12)

| §11.12 item | outcome |
|---|---|
| 1. the SUSP-lead discriminator | **RESOLVED, and the premise was wrong** (§12.1).  Not an EU lead — the model's prefetcher was one eval early.  M6 landed; all three legs (boot, `0F39`, ENTER) close together; w0 ratchet +9, w1/w3 unmoved.  2 named residual cells |
| 2. re-freeze the wvec corpus | **DONE AND PROMOTED TO SILICON** (§12.2).  22 distinct digests in all four configs; the collapse was the TB reference.  §11.9's whole-program cadence numbers RETRACTED |
| 3. the HALT bus pseudo-cycle | **MEASURED AND LANDED; S8/S9 REMOVED** (§12.3).  One pre-registered prediction falsified (it does stretch) |
| 4. `F3AA cx >= 2` | **ANSWERED** (§12.4): a fixed cycle index, not the eval, at w0/w1/w3.  Residual now w0-only |
| 5. C3's Arm-C sled | **CAPTURED AND FROZEN** (§12.5), prediction confirmed, bit-identical to the 07-17 log |
| law cards C1-C7, C9-C12 as sim gates | **SCOREABLE AT LAST**: 1 GREEN / 6 RED / 4 UNRESOLVED (§12.6), each against a named silicon capture |

**T3 handoff.**  (a) The six RED cards are one error with one shape — the
prefetch resume is too eager, LC1/LC2 unimplemented — and the Arm-C sled plus
the 88-cell silicon wvec corpus are the stimulus.  (b) `timed_wvec_gate` is
0/88 on the per-cycle digest with the COUNT already 78/88: that gap is the T3
target and it is now measured against silicon, not against a TBR baseline.
(c) The two ENTER wrand cells and the w0-only `F3AA` residual are named,
narrow, and carry their discriminating pairs.  (d) `sw/biu_rebuild_wvec_freeze.py`
and the `Vtb_v30_core` binary are NOT a controlled reference and should not be
cited as one until rebuilt from a clean tree.

---

## 13. T3 — sequence timing.  ONE FLOP, READ ONE CLOCK TOO LATE

This section is the T3 stage.  Nothing earlier is retracted.

Part A closes the six RED law cards' shared shape with **one mechanism and one
bug fix**, both of them w0-neutral by construction; Part B pre-registers and
runs the fuzz-bank cycle-replay gate.  The ratchets:

| step | v0.1 **w0** | w1 | w3 | sled events | wvec count | INS vs-chip rails |
|---|---|---|---|---|---|---|
| T2b close (§12) | 165,490 | 1,200 | 1,200 | 3,587 / 3,639 | 78 / 88 | 1,768 / 2,624 |
| M7 — the eligibility sample is at a FIXED index (§13.1) | 165,490 | 1,200 | 1,200 | 3,625 / 3,639 | 82 / 88 | 1,772 / 2,624 |
| M7b — ...and the outstanding term clears at POPPABLE (§13.2) | 165,490 | 1,200 | 1,200 | **3,768 / 3,769** | 82 / 88 | 1,772 / 2,624 |
| R-STALL — the leaked OPR hold (§13.3) | **165,490** | **1,200** | **1,200** | 3,768 / 3,769 | **87 / 88** | **2,624 / 2,624** |

### 13.0 PRE-REGISTRATION — the fuzz-bank cycle gate, written and committed BEFORE the first full run

The S4r lesson applied to a corpus gate: the population, the comparison policy
and the numeric bar are frozen *here*, from a 50-seed pilot, so that no
post-hoc reading of the full run can be dressed up as the gate.  Verbatim
register:

**Harness.** `sw/timed_fuzz.py`, three things inherited rather than
re-invented: the regeneration path and its sha256 gate (`ucsim_fuzz.regen` —
a drift is a HARD failure, because the image the simulator would run is then
not the image the chip ran), the comparison WINDOW (`ucsim_fuzz.window_of`:
row 0 = RESET RELEASE to `min(len(chip_rows), 4000, done+8)`), and the COLUMN
POLICY (`fuzz_classify.diff_rows`, byte for byte the policy the banks' own
`first_bad`/`bad_rows` were computed with — the same masking family as
`check_core`/`timed_gate`: `bs_late`, `rd_n`, `lock_n`, `rst` are never
compared, AD is an ADDRESS at T1 and DATA at T2/T3 and nothing on a TI or T4
clock, `ps` only at T2 of an active cycle, `qs` on every row with the
documented F/S flicker exemption, and rows 0-8 are the capture's reset
settling).

**Wait vectors** are rebuilt from each seed's own `waits` record: a fixed
level to `--waits`, a random one to `--wmax/--wseed`, which drives the model's
copy of the rig's Galois LFSR (poly 0xB400, drawn once per bus cycle at T1
entry, §11.1).

**Population.** All **3,242** banked seeds of `mc1` + `mc2` + `t30-raw` +
`t30-brkem`.  **Verdict class is NOT a filter**: a bank verdict
(TIMING/FUNCTIONAL/SUCCESS/KNOWN_ACCEPTED) records what the FABRIC did against
the chip and says nothing about what the SIM does — and the reference here is
the chip capture itself, which every banked seed carries.  Two exclusions,
both declared in advance and both properties of the CAPTURE, not of the
model's answer on it:

* **EVT** — the seed carries an external event.  Interrupt/INTA timing under
  waits is an explicit scope exclusion of the whole campaign; a gate must not
  pretend a law it has never measured.
* **OPEN_BUS** — the program escaped the image and the chip is reading the
  rig's open bus (`ad_data == ad_addr` feedthrough), detected with the bank's
  OWN detector (`fuzz_classify._open_bus_escaped_before`).  The simulator's
  memory is the 64 KB-mirrored image the board is wired as, so it reads image
  bytes there: that divergence is the rig's, not the model's.

`GEN_DRIFT`, `REGEN_ERROR` and `SIM_ERROR` are **hard failures**, not
exclusions.

**Pilot (50 stratified seeds, deterministic, `--pilot 50`; 26 scored, 17 EVT,
7 OPEN_BUS):**

| metric | pilot value |
|---|---|
| M1 cycle-exact seeds (whole window divergence-free) | **0 / 26 (0.0 %)** |
| M2 median divergence-free prefix, rows from RESET | **277** |
| M3 median prefix FRACTION (`first_bad / n`) | **0.177** |
| M4 seeds with prefix fraction >= 0.5 / >= 0.9 | **0 / 26**, **0 / 26** |
| first-divergence family census | `qs` 20, `data` 3, `bs` 3 |

**The bar, stated honestly.**  The pilot says the model is NOT cycle-exact over
whole 1,300-4,000-clock programs, so an absolute pass threshold would be either
vacuous or unreachable and the gate does not claim one.  What it claims, and
what can fail:

1. **Zero hard failures** on the full population (`GEN_DRIFT`/`REGEN_ERROR`/
   `SIM_ERROR` = 0).
2. **A closed taxonomy**: every scored seed's first divergence falls in a named
   family; an "unknown" bucket is a failure of the survey, reported as one.
3. **A RATCHET**: M1, M2, M3 and M4 measured on the first full run are the
   baseline of record and may only GROW thereafter.  The scored-population size
   and the EVT/OPEN_BUS counts are frozen with them, so the ratchet cannot be
   met by shrinking the denominator.
4. **A falsifiable prediction from the pilot**: the full run's first-divergence
   census is dominated by `qs` (pilot 77 %), with `data` and `bs` the only
   other families.  A large family the pilot did not see is a FINDING and is
   reported as one.

### 13.1 M7 — the prefetch-eligibility test is SAMPLED AT A FIXED CYCLE INDEX

**The six RED cards were one flop, read one clock too late.**

§7.4's M4 predicate is right and is unchanged: a fetch is issued at an eval iff
`occupancy(queue) + bytes-in-flight <= 4`.  What was wrong was *when the model
reads it*.  The model read it AT THE EVAL — and §11.1 moved the eval, with the
READY sample, from T3 (w0) out to T4 (waited).  The part does not: the
eligibility answer is decided at **cycle index 2** and latched, and the
completion eval only applies what that clock decided.  Every queue POP that
happens between T3 and T4 — i.e. during the whole Tw stretch — is therefore
INVISIBLE to the decision, and the part declines refills the model granted.
That is the entire "the model resumes too eagerly" shape the six REDs share.

**w0-neutral BY CONSTRUCTION, not by luck:** at w0 the eval instant IS index 2
(§11.1: `e = 2` when `N = 0`), so the sample and its consumer are the same
clock and nothing can move.  Measured: the w0 ratchet is 165,490 before and
after, to the case.

*The measurement.*  The T2b Arm-C silicon sled (`sw/testdata/t2b/p5-armc`) is
the only stimulus in this repo that scores the resume decision EVENT BY EVENT:
20 programs x 2 wait levels, the chip's `cidle` per CODE->CODE pair.  Over the
divergence-free prefix (2,252 aligned completion evals, 26 of them a chip
PAUSE), reading the occupancy at each candidate index and applying the
UNCHANGED `<= 4` threshold:

| sampled at | N = 8 errors | N = 12 errors |
|---|---|---|
| T1 | 44 | — |
| T2 | 22 | 20 |
| **T3 (index 2)** | **4** | **0** |
| T4 (the eval — the model's own instant) | 15 | 12 |

T3 is the minimum at BOTH wait levels and is EXACT at N = 12; the model's own
instant is the worst at both.

*One consequence had to be said out loud:* **a FLUSH zeroes the queue counter,
and therefore the latch.**  The sampled quantity is the counter, so a sample
taken at index 2 of a cycle the flush then invalidates cannot hold the redirect
off.  Without that clause `EB` is the ONLY form the whole waited suite loses —
149/200 at w1 and 145/200 at w3; with it, 200/200 at both.

*Falsifier:* any waited capture where a pop between T3 and T4 changes the
decision.

### 13.2 M7b — ...and the outstanding-fetch term clears at POPPABLE, not at WRITTEN

M7 alone reproduces the sled's `cidle = 3` population and leaves a second,
smaller one: 13 events where the chip's completion eval declines AND its next
idle eval declines too, granting only at T4+3 (`cidle = 4`) where the model
granted at T4+2.

The queue counter takes a fetch's bytes at the PUSH EDGE (`e+1`, M3).  The
"a fetch is out" term the scheduler adds to it clears one clock LATER, at
`e+2` — the clock before the bytes may be popped.  Two flops, two clear
conditions; across the two landing clocks the scheduler counts those bytes
TWICE and the threshold bites two bytes early.

*Measured on the same sled*, over the 53 aligned events whose completion eval
the chip declined: the chip grants at T4+2 in 40 and at T4+3 in 13, and the
queue count at T4+2 separates the two sets with **ZERO exceptions** — `q <= 2`
grants, `q = 3` or `4` waits a clock.  With the fetch's own two bytes still
counted that is exactly the unchanged `occupancy <= 4`; **without them no
threshold on any single clock separates the two sets at all**, which is the
argument for the double count rather than for a new number.

**w0-neutral BY CONSTRUCTION again:** at w0 the window is [T4, T4+1], of which
T4 is not an eval point (M1) and T4+1 is M6's blocked clock — no w0 eval can
see it.  Under waits the window is [T4+1, T4+2] and only T4+2 is a live eval.

**Result on the sled: 3,768 of 3,769 aligned CODE->CODE events exact** (was
3,587 of 3,639; the aligned population itself grows because three seed-cells
that used to run short now align).  The chip's own `cidle` histogram is
reproduced bucket for bucket at 4, 5 and 12; the single residual is
`fz90002` at N=8, event 72, where a pop lands ON the sample clock and the chip
behaves as though it had not yet been seen — the "occupancy is a register"
reading §12.1 falsified at w0, alive in exactly one cell.

### 13.3 R-STALL — a LEAKED OPR hold, and it was worth 856 chip-exact INS rails

Building the fuzz replay exposed a defect that is not a law at all.  `mem_write`
/ `io_write` claim OPR when the write data is PAIRED (§9.2), and `tick()`
releases it at the store's **T2** (the fixed index 2 of §11.4).  Since S5's
retirement (§8.5) the BIU may RESERVE and even START a write cycle before its
data exists — so a pairing that happens after that cycle's T2 has already gone
by has no release instant left, and the hold LEAKS.  The next `-> OPR` row then
burns `wait_opr_free`'s whole 4,096-tick guard, the bus parks, and the run is
silently truncated.

The fix is the physical statement: OPR is held only until the AD output latch
takes the word at T2; if the pairing is later than that, OPR was never held.

MEASURED, and it is the largest single move of the stage:

| gate | before | after |
|---|---|---|
| `timed_wvec_gate` access count (vs SILICON) | 82 / 88 | **87 / 88** |
| `timed_wvec_gate` whole-program bus cycles | −3.6 % | **−0.0 %** (16,047 vs 16,048) |
| `timed_ins_replay` STRICT rails vs the chip capture | 1,772 / 2,624 | **2,624 / 2,624** |
| `timed_ins_replay` R2 issue | 780 / 800 | **782 / 800** (= the offline pilot exactly) |
| whole-program leading-access agreement | 102,960 / 173,556 | **127,712 / 173,556** (127,584 also same-T1) |

`v30sim timed-boot` now also prints `STEP-ABORT` on stderr when the EU gives up
on an instruction: a silently truncated run looks like a cadence result and is
not one.

### 13.4 Law cards — three of the six REDs turn GREEN, and the other three are a DIGEST

`python3 sw/timed_lawcards.py`:

| card | T2b | T3 | on what |
|---|---|---|---|
| **C1** LC1 steady-state gap | RED | **GREEN** | the frozen Arm-C sled: pause population sim 38 vs chip 43 (N=8), 26 vs 30 (N=12), `cidle` pinned at 3 on both |
| **C3** LC1 cidle pin | RED | **GREEN** | same sled |
| **C9** LC4 general lead reservation | GREEN | GREEN | unchanged |
| **C4/C5** LC2 aged band | RED | RED | `fz90364:ws5:wmax1`: count 139/139, **digest** differs |
| **C10/C12** LC4 late reservation / pf_rsv_lead | RED | RED | `fz90270:ws5:wmax1`: count 187/187, **digest** differs |
| C2, C6, C7, C11 | UNRESOLVED | UNRESOLVED | unchanged (no stimulus / board-by-construction) |

**3 GREEN / 4 RED / 4 UNRESOLVED** (was 1 / 6 / 4).

**And an honest limit on the four remaining REDs, found by trying to work on
them.**  `sw/testdata/t2b/p2-wvec/wvec_chip_baseline.json` stores, per cell,
only a 16-hex-digit sha of the whole per-cycle digest plus the access count and
the raw capture's sha — **no per-cycle stream and no retained raw words**.  So
C4/C5/C10/C12 are pass/fail with NO GRADIENT: the sim now matches the access
count on every one of them and there is no way to read WHERE the digest parts.
That is a provenance gap in the T2b freeze, not a modelling one, and it is the
first item of the T4 handoff (§13.7): the P2 capture must be re-banked with the
per-cycle `parts` list (or the raw words retained) before those four cards can
be worked on at all.  The Arm-C sled is the only graded resume stimulus this
repo holds, and it is now essentially closed.

### 13.5 Part B — the fuzz-bank cycle gate, RUN, surveyed, fixed, re-run

`python3 sw/timed_fuzz.py` over the whole registered population, 3,242 seeds,
~52 s wall on this machine.  Against the register of §13.0:

| | pre-registered pilot | **first full run** | after the survey's one fix |
|---|---|---|---|
| hard failures (GEN_DRIFT / REGEN_ERROR / SIM_ERROR) | — | **0** | **0** |
| scored / EVT / OPEN_BUS | 26 / 17 / 7 | **1,702 / 1,165 / 375** | 1,702 / 1,165 / 375 |
| M1 cycle-exact seeds | 0 / 26 | **32 / 1,702 (1.9 %)** | **44 / 1,702 (2.6 %)** |
| M2 median divergence-free prefix (rows) | 277 | **315** | **329** |
| M3 median prefix fraction | 0.177 | **0.234** | **0.241** |
| M4 prefix fraction >= 0.5 / >= 0.9 | 0 / 0 | **119 / 34** | **144 / 46** |

The **denominator is frozen** exactly as registered: the scored population, the
EVT count and the OPEN_BUS count are identical across every run in this
section, so none of the movement is a shrinking denominator.

**The pilot's prediction, scored.**  Predicted: the census is dominated by `qs`
(pilot 77 %) with `data` and `bs` the only other families.  Outcome: **`qs`
dominates (1,137 + 151 flicker = 76 % of the first full run)** and `data`
(227) and `bs` (121) are the next two — but the full run also turned up three
families the 50-seed pilot never sampled: `ps` (24), `addr` (8) and `ube` (2).
Recorded as the partial miss it is: a pilot that size does not see a 24-seed
family.

**Where the model stood BEFORE this stage.**  The same harness on a binary
built from the T2b commit (`git show HEAD:sim/...`, built in a scratch tree):

| | T2b | + M7/M7b | + R-STALL | + the rig's I/O constant |
|---|---|---|---|---|
| M1 cycle-exact | 17 | — | 32 | **44** |
| M4 >= 0.5 / >= 0.9 | 96 / 19 | — | 119 / 34 | **144 / 46** |
| `bs` first-divergence family | 248 | — | 121 | 133 |
| `data` first-divergence family | 207 | — | 227 | **4** |

and, per seed, **341 seeds gained a longer divergence-free prefix and NOT ONE
lost any** — the ratchet holds at the level of the individual capture, not just
in aggregate.

**Survey-then-fix: the one thing the survey found that was a MECHANISM (a
rig one) and not a law.**  227 seeds' first divergence was `data ffff != 0000`
on an `IOR` data phase.  Census over the four banks: **4,594 of 4,594 chip
I/O-read data-phase rows carry 0xFFFF**, across 8+ distinct ports — the capture
board has no readable I/O device and an `IN` reads the floating bus.
`image_runner.cpp` has carried that constant since the fuzz campaign and
`timed-boot` never got it, so every `IN` in a replayed program returned 0x0000
and the run diverged ARCHITECTURALLY from that clock on.  Landed (§13.3's
paragraph in `timed_runner.cpp`); the family goes **227 -> 4**.

**The closed taxonomy of what is left** (post-fix, 1,658 diverging seeds):

| family | seeds | what it is |
|---|---|---|
| **Q1 — the decoder march under waits** | 1,290 + 192 flicker | a queue POP displaced by 1 or 2 clocks, in BOTH directions (chip-early 393, sim-early 421 at the +-1 shift), and it lands on **T2 of a CODE cycle** in ~4 of every 5.  This is §9.1's M3c -- the decode march of 1- and 2-clock STEPS, whose strides are MEASURED at w0 (v0.1 is 165,490 exact) -- meeting the wait axis, where neither the demand clock nor the stride has ever been measured.  The 192 are the documented F/S QS flicker |
| **Q2 — the redirect one clock late** | 133 | `qs E!=- bs CODE!=PASV` (72) and its relatives: the chip displays the flush's `E` and the redirect fetch at the previous cycle's T4+2 and the model at T4+3, with every cell before and after identical.  A branch/flush cadence law under waits |
| **PS3 on a stack write** | 28 | the chip drives PS bit 3 = 1 on a `MEMW` whose segment code is SS (`ps d!=5`, one cell `9!=1`).  A19 is 0 at the cycle's own T1 in **all 36 rows**, so it is not a stale address bit; present in brkem and non-brkem seeds alike, so it is not emulation mode.  UNEXPLAINED, and rare -- 36 rows in 3,242 captures |
| tails | 9 addr, 4 data, 2 ube | control-flow divergences downstream of an earlier displacement |

Nothing is booked "unknown": every scored seed's first divergence is in one of
those four rows.

**What the gate is now.**  M1 = 44, M2 = 329, M3 = 0.241, M4 = 144 / 46 over a
frozen 1,702-seed denominator, with the taxonomy above.  Those are the baseline
of record and may only grow.

### 13.6 Gates (measured, this machine)

| suite | result |
|---|---|
| v0.1 arch | 169,000 / 169,000 |
| v0.2 arch | 347,000 / 347,000 |
| v0.3 arch | 3,699,998 / 3,699,998 |
| v20suite arch | 3,125,000 / 3,125,000 |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 |
| **total** | **7,341,126** |

```
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all              # 165,490 (w0)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1 # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3 # 1,200/1,200
python3 sw/check_boot.py --timed 220 # MATCHES over 220 rows
python3 sw/timed_scenario.py         # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py     # walk/pushes/active/halt/full 154/154
python3 sw/timed_ins_replay.py --raw # rails 1312/1312, R2 782/800, vs-chip 2624/2624
python3 sw/timed_wvec_gate.py        # count 87/88, cycles -0.0 %, digest 0/88
python3 sw/timed_lawcards.py         # 3 GREEN / 4 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py             # THE T3 GATE -- 44/1702 exact, 0 hard failures
```

A diagnostic, not a gate: `V30SIM_EVALTRACE=1 v30sim timed-boot ...` writes one
`ET` line per eval point (the decision and the state it saw) and one `QT` line
per clock (the queue). It is the instrument M7 and M7b were found with, it is
env-gated, and it touches no model state.

### 13.7 T4 handoff

1. **Re-bank the P2 wvec capture WITH ITS PER-CYCLE STREAM.**  §13.4: the
   T2b freeze stores only a 16-hex sha per cell, so C4/C5/C10/C12 are
   gradientless — the sim matches the access count on all four and there is no
   way to see where the digest parts.  This is the single cheapest unblock in
   the campaign: one board session, same stimulus, retain `parts` (or the raw
   words) beside the sha.
2. **Q1, the decoder march under waits** — the stage's own biggest residual
   (87 % of the fuzz first-divergences after the I/O fix) and the one with the
   most stimulus already banked.  It wants a `qcensus`-style census done UNDER
   WAITS: every pop with the ready clock of the byte it took, over the fuzz
   banks' chip_rows, keyed by (step kind, stride, wait count).  The w0 strides
   of §9.1 are exact; what is unmeasured is what the stride does when the cycle
   that delivers the byte stretches.
   *One negative result to start from, measured here so nobody re-derives it:*
   **the displacement is NOT a function of the local wait counts.**  Over 150
   sampled first-divergences, keyed by the Tw of the cycle the pop rides and of
   the cycle before it, the largest single cell is `(tw 0, prev tw 0)` with 23
   — a pop displaced by one clock where NEITHER adjacent cycle is waited at
   all.  Whatever carries the error is further back in the history than the two
   cycles around the pop, which is why a "+1 per wait" correction cannot be
   it.
3. **Q2, the redirect one clock late under waits** (133 seeds) — the flush
   family, with a named window per seed and both sides identical either side
   of the one clock.
4. **PS3 on an SS write** (36 rows) — unexplained, and cheap to settle from
   the banks alone (no board): find the instruction that issues those stores.
5. **The one sled cell left**, `fz90002` N=8 event 72, where a pop lands ON the
   index-2 sample clock: it is the "occupancy is a register" reading §12.1
   falsified at w0, alive in exactly one waited cell.  A directed capture (the
   same program, a pop forced onto the sample clock) decides it.
6. Unchanged from §12.8: the w0-only `F3AA cx >= 2` residual (907 cases), C2 /
   C6 / C7 / C11's missing stimuli, and `sw/biu_rebuild_wvec_freeze.py` +
   `Vtb_v30_core` remaining NOT a controlled reference.

## 14. T4 — the board block.  Q1 closed OFFLINE, and the board register

This section is the T4 stage.  Nothing earlier is retracted except where an
entry below says so — and two things below **are** retracted, both of them
laws this campaign fitted itself: **M3c** (§9.1) and the **PS3 reading** of
§13.5.

The stage opened with the whole Q1 family (87 % of T3's fuzz first
divergences) still open and a board session budgeted for it.  It did not need
one: the mechanism came out of the banked chip captures with a new instrument,
and the board time was re-aimed at the two things that genuinely require
silicon — the P2 provenance gap and the victory tranche.

### 14.0 PRE-REGISTRATION — written and committed BEFORE the board was touched

Board discipline for this whole section: SINGLE WRITER (checked, no foreign
`v30run serve` / `v30ctl` / fork-session runner), **socket only**
(`use_core=False`), **no FPGA flashing anywhere**, `board_idle()` after every
session, raw 64-bit capture words retained with a sha256 beside every derived
record, and — the P2 lesson (§13.4) — **the full per-cycle stream retained,
never a digest alone**.

#### B1 — the P2 wvec re-capture, with its parts

*Why.* §13.4: `sw/testdata/t2b/p2-wvec/wvec_chip_baseline.json` stores only a
16-hex sha per cell, so law cards C4/C5/C10/C12 are pass/fail with NO
GRADIENT — the sim matches the access COUNT on all four and there is no way to
read where the digest parts.  This is the cheapest unblock in the campaign.

*Stimulus.* Byte-identical to T2b P2: the 22 seeds (`fz90000-90019` +
`fz90270`, `fz90364`) x the 4 explicit per-access wait vectors (`ws0:wmax0`,
`ws5:wmax1`, `ws7:wmax3`, `ws11:wmax7`), 4,200 clocks, socket, 2 repetitions
per cell; the 2 directed law seeds at `ws5:wmax1` promoted with 5 repetitions
at 4 MHz **and** 8 MHz.  What is NEW is only what is RETAINED: the full
per-access `parts` list for every cell, and the complete per-clock row stream
for the four law-card cells.

*Predictions, and the falsifier.*
1. every one of the 88 cells reproduces its T2b 16-hex digest **exactly**.
   A cell that does not is a CAPTURE-SIDE drift (board, rig or harness), not a
   model finding, and it invalidates the T2b freeze rather than the model —
   that outcome is reported as such and the law cards stay blocked.
2. all 88 cells bit-repeatable across their repetitions; the promoted cells
   identical at both frequencies.
3. the parts lists make C4/C5/C10/C12 gradable: for each card the FIRST
   differing access index is nameable.  If the sim's parts are identical and
   only the digest differed, the T2b digest is not a function of the parts and
   that is a harness bug, reported as one.

#### B2 — THE VICTORY TRANCHE

*The population, frozen before capture.*  **216 fresh seeds** = 3 generators
(`mc1`, `mc2`, `t30-raw`) x 9 wait classes (`fix0` `fix1` `fix2` `fix3`,
`wrand1` `wrand2` `wrand3` `wrand7` `wrand15`) x 8 seeds.  Seeds are drawn
deterministically: for each (cid, class), scan `k` upward from **100000** —
strictly outside every banked range (`mc1` max 3744, `mc2` 3868, `t30-raw`
999) — and take the first 8 whose `fuzz_campaign.derive_case(cid, k,
{"no_evt": True})` lands in that class.  **Never-before-seen by construction**,
and reproducible from those three lines.  The (cid, k) list is written to disk
and committed BEFORE the first capture.

*Why `no_evt` is set at GENERATION and not filtered afterwards.*
Interrupt/INTA timing under waits is an explicit scope exclusion of the whole
campaign.  T3 excluded it post hoc (1,165 of 3,242 banked seeds); here it is
excluded by construction so the denominator is fixed before anything is
measured and cannot move.

*Capture.* Socket, `use_core=False`, no flashing.  **3 repetitions per cell at
div=8**; a cell whose 3 captures are not pin-identical is EXCLUDED and
REPORTED, never scored.  **12 declared promotion cells** (the first seed of
each of the 9 wait classes for `mc1`, plus `wrand15` for `mc2` and `t30-raw`,
plus `mc1`/`fix0`) additionally get 5 repetitions at 4 MHz AND 8 MHz.  Raw
64-bit words and the full per-clock rows retained for every cell, sha256
beside each.  If the wall time proves excessive the POPULATION is cut (whole
strata, evenly), never the repetitions — and the cut is stated.

*Replay.* Identical to `sw/timed_fuzz.py` in every particular: the regeneration
path and its sha256 gate, the comparison WINDOW (`ucsim_fuzz.window_of`), and
the COLUMN POLICY (`fuzz_classify.diff_rows`).  Wait vectors rebuilt from each
seed's own derived `waits` record.

*Exclusions, declared in advance, both properties of the CAPTURE:*
* **OPEN_BUS** — the program escaped the image and the chip is reading the
  rig's open bus, by the bank's OWN detector.
* **UNSTABLE** — the 3 repetitions are not pin-identical.
`GEN_DRIFT`, `REGEN_ERROR`, `SIM_ERROR` and capture errors are HARD FAILURES.

*THE BAR — frozen here, before the capture, and scored as written.*

| | metric | bar |
|---|---|---|
| **V0** | hard failures | **0** |
| **V1** | scored seeds cycle-exact over the whole window | **>= 55.6 %** |
| **V2** | median divergence-free prefix FRACTION | **>= 1.000** |
| **V3** | every non-exact seed's first divergence in a NAMED family | **100 %** |
| **V4** | cycle-exact rate in the five `wrand` strata vs the four fixed strata | **within 10 points** |
| **V5** | the campaign's literal victory phrasing, "fresh random-wait tranche cycle-exact" | **V1 = 100 %** |

V1's and V2's numbers are the post-Q1 banked figures (947/1,702 = 55.6 %,
median prefix fraction 1.000, §14.2) and the bar is that a FRESH tranche must
be **at least as good** as the banked one.  Stated as a falsifiable prediction
rather than a bar: the fresh tranche should be **BETTER**, because the fuzz
bank is an adversarially selected population — every seed in it was PROMOTED
for diverging against an earlier model — while a fresh tranche is unselected.
A fresh tranche that scores WORSE than the bank means the bank is not
representative of the wait axis and is reported as the finding it would be.

V4 is the project's #1 priority written as a gate: a model that is only
accurate at zero waits fails this stage even if V1 passes.

**V5 is registered so that it cannot be quietly redefined.**  The T3 evidence
says the model is not cycle-exact over whole 1,300-4,000-clock programs, so V5
is expected to FAIL, and the campaign's victory will be reported as PARTIAL
with V1-V4 scored as written.  No post-hoc restatement of "cycle-exact" is
permitted; if V5 fails it is reported failed.

#### B3 — A30, if the board session has room

*Parked from the functional campaign.*  `BRKEM` -> stay in 8080 mode -> INTR:
which INTA bank does the acknowledge use?  It settles the 14th-decoder-input
assumption.  Registered as best-effort: it runs only after B1 and B2 are
complete and verified, and if it does not run that is recorded, not hidden.

### 14.1 Q1 — the pop is a MAX, and M3c's re-run was a POOLING ARTIFACT

**Q1 needed no board time.**  It came out of the banked chip captures with one
new instrument, and the mechanism is one clock and one constant.

*The instrument.*  `sw/q1census.py` reads the queue-pop stream straight out of
a PER-CLOCK PIN ROW STREAM — chip capture or sim emission — the way §9.1's
`sw/qcensus.py` reads it out of the v0.1 goldens.  CODE cycles give every byte
its deliverer and its ready clock; the QS pins drive a queue model that gives
every pop its byte, its address and (via the `F`s) its instruction boundary, so
every pop gets a ROLE.  `sw/q1diff.py` runs the identical reconstruction over
both streams and reports WHICH POP MOVED.  Both are standing tools.

**M8a — the ready clock steps by ONE when the delivering fetch was waited.**
Over all 3,242 banked captures, a byte-limited pop lands at its deliverer's
**T4 + 2** when that fetch was unwaited and at **T4 + 3** for every `Tw` from
**1 to 15** — flat, not proportional.  The model already had this for free
(M2r puts the push at eval + 3, and the eval moves T4-1 → T4 under waits).
This is exactly why §13.7's negative held: the displacement is carried by the
DELIVERING FETCH, which can be several cycles back in the history, so it is
not a function of the wait counts local to the pop.

**M8 — `pop = max(demand, ready + pen)`, and there is NO RE-RUN.**

| class | demand | pen | measured cells |
|---|---|---|---|
| modrm after the opcode / after the `0F` byte, disp16-LO, a micro-row's imm-hi | 1 | 0 | ready<=1 -> 1, 2 -> 2, 3 -> 3, 4 -> 4, ... |
| the `0F` page's opcode, the opcode after a prefix, a prefix after a prefix, a micro-row's first immediate | 2 | 0 | ready<=2 -> 2, 3 -> 3, 4 -> 4, 5 -> 5, ... |
| the byte that COMPLETES a displacement (disp8, or disp16-HI) | 2 | **1** | ready<=1 -> 2, 2 -> 3, 3 -> 4, 4 -> 5, ... |

**§9.1's M3c is RETRACTED.**  It was fitted with the four "stride 2" classes
POOLED, and the pooled cells `ready 3 -> pop 4` and `ready 4 -> pop 4` cannot
both be a max — so a re-run was invented to hold them together.  Split by
role each class is a plain max and **every cell is single-valued**, on the
goldens and on the chip captures, at w0 and at every wait level.  The goldens
never sample `ready 3` for the demand-2 classes nor `ready >= 4` for the pen-1
ones, which is exactly how a wrong law survived a 165,490-case w0 gate and
still owned 87 % of the fuzz bank's first divergences.  `last_dec_` and the
stride are DELETED: the model is smaller than before.

*The economical reading of `pen`* (offered, not relied on): the displacement's
last byte is what the EA adder needs, and the adder stands one stage behind
the decode port — it reads the byte the clock after the queue can give it up.

**M8b — the DEFERRED instruction boundary was one clock short.**  With the
march families cleared, the whole residual was one role pair: `O -> I0`, where
the chip pops at opcode+2 and the model popped at opcode+1 with the byte long
ready and both sides agreeing on the opcode pop clock itself.  Two boundary
paths exist and only one spent the clock after the pop: the E-row path
pre-pops and then runs `charge(row_clocks)`, while the max-of-two-deadlines
DEFERRED release (an instruction whose write was still staged in the pairing
latch) pops at the tail of `step()`, after that charge has gone by.  So the
failing boundaries are exactly those whose predecessor did bus work.
**No gate could see it**: the v0.1 harness runs ONE instruction per case from
an injected queue, so `opcode_pending()` is never true and neither boundary
path is exercised at all.

**M9 — PS3 is the EMULATION-MODE bit**, and §13.5's negative was reading a
flag.  All 73 first-divergences of the `ps d!=5` family begin at an opcode
`0F xx`; the chip reads an interrupt VECTOR, pushes PSW / CS / IP, and PS3
comes up BETWEEN the PSW push and the CS push — the clock BRKEM's microcode
clears MD — then stays up on every following cycle, CODE fetches included
(`ps e` on a CS fetch).  It is not an SS-write property; the family looked
that way only because the first cycle after MD clears happens to be the CS
push.  §13.5 concluded the opposite from the BANK's `has_brkem` flag, which
counts only the documented `0F FF` encoding — while the chip's PLA decodes a
wide spread of undefined `0F xx` second bytes as BRKEM as well (`0F F7`,
`0F FD`, `0F D3`, `0F 40`, `0F 73`, `0F 90`, `0F 65`, `0F 8D`, `0F 7C`,
`0F C2`, ...), each taking the NEXT byte as its vector.  **`has_brkem`
under-reports — a live finding for the functional side too.**

*The Q1 ratchet, measured on this machine, against the T3 register of record:*

| gate | T3 close | + M8 | + M8b | + M9 |
|---|---|---|---|---|
| v0.1 **w0** rows-exact | 165,490 | 165,490 | 165,490 | **165,490** |
| v0.1-w1 / -w3 | 1,200 / 1,200 | 1,200 | 1,200 | **1,200 / 1,200** |
| `timed_fuzz` M1 cycle-exact | 44 / 1,702 | 136 | 947 | **947 / 1,702 (55.6 %)** |
| M2 median prefix (rows) | 329 | 417 | 1,068 | **1,068** |
| M3 median prefix FRACTION | 0.241 | 0.307 | 1.000 | **1.000** |
| M4 >= 0.5 / >= 0.9 | 144 / 46 | 399 / 138 | 1,192 / 950 | **1,192 / 950** |
| `timed_wvec_gate` access count | 87 / 88 | 87 / 88 | **88 / 88** | 88 / 88 |
| `timed_wvec_gate` bus cycles | -0.0 % | -0.0 % | **+0.0 %** | +0.0 % |

The denominator is frozen exactly as T3 registered it (1,702 scored, 1,165
EVT, 375 OPEN_BUS) at every step, and **no seed lost divergence-free prefix at
any step** (M8: 682 gained / 0 lost; M8b: 1,265 / 0; M9: 73 / 0).

**GATE (§13.7 item 2): the Q1 family COLLAPSES.**  Taxonomy delta over the
fuzz bank's first divergences:

| family | T3 close | T4 | |
|---|---|---|---|
| **Q1 decoder march** | 1,290 + 192 flicker | **0** | closed |
| **Q2 redirect one clock late** | 133 | 381 | *unchanged in kind*; it is now the largest family because seeds that used to stop at Q1 reach it |
| **PS3 on an SS write** | 28 | **0** | closed (M9) |
| `qs` (pop display) | — | 324 | the Q1 family's successor at a later clock |
| tails (addr / data / ube) | 15 | 50 | control flow downstream of an earlier displacement |
| cycle-exact seeds | 44 | **947** | |

### 14.2 Q2 — half MEASURED, half NOT, and it is stated as half

The redirect family is **not closed**, and the honest position is worth more
than a patch.

*What is measured.*  Over the 293 seeds whose first divergence is
`qs E!=- bs CODE!=PASV`, the chip shows the flush `E` and the redirect's
status at the previous cycle's **T4 + 2** in 293 of 293 and the model showed
them at **T4 + 3** in 293 of 293, with every clock before and after identical;
the completed cycle carried `Tw >= 1` in all 293.  So under waits **the queue
port frees at T4 + 2**, not T4 + 3 — the model's absorb window (`eval + 1` to
`eval + 2`, §12.1 F1(b)) holds it one clock too long, exactly the correction
M6 already makes for the landing window.

*What is NOT measured, and why the fix was NOT landed.*  Over the whole
corpus both `T4+2` and `T4+3` occur (at `tw = 1`: 65 vs 112; `tw = 2`: 51 vs
57; `tw = 3`: 35 vs 18), so the display is `max(EU raise, port free)` and only
the PORT half is pinned.  Solving the census for the EU half gives a raise
clock of `last pop + a` with **`a` varying 4..7 by microcode path** —
unmeasured.  Landing the port correction alone moves M1 **947 -> 753** and
turns 360 seeds into `qs -!=E` (the model's E now too EARLY), because the
over-long port hold was MASKING an EU-side raise clock that is too early in
several paths.  Reverted, and recorded: **the port half of Q2 is measured, the
EU half needs a directed factorial over the branch forms, and the model is
left in the state that maximises the ratchet.**  This is the T5 handoff's
first item.

### 14.3 B1 — the P2 corpus re-captured WITH ITS PARTS, and the four RED cards close

`python3 sw/t4_board.py b1` — the T2b P2 stimulus byte for byte, socket,
`use_core=False`, no flashing, 11 s of board time.
`sw/testdata/t4/b1-wvec/wvec_chip_parts.json`.

*Pre-registration prediction 1 (§14.0), scored:* **88 / 88 cells reproduce
their T2b 16-hex digest EXACTLY.**  No capture-side drift; the T2b freeze
stands and this is the same reference with a gradient attached.  Prediction 2:
88/88 repeatable and pin-identical; both promoted cells identical at 4 and
8 MHz.  Prediction 3: the parts made the cards gradable — see below.

**And the gradient found the bug in one look.**  Of **139** accesses in
`fz90364:ws5:wmax1` and **187** in `fz90270:ws5:wmax1`, **exactly ONE parts
away — the LAST one, the closing HALT — and only in its PS nibble**: chip
`0x6`, model `0x2`.

**M10 — the HALT display's upper nibble is a LIVE PS, not a constant.**
`note_halt()` hard-coded it to the bare segment code (CS = 2); the chip
carries IE on the HALT display like any other cycle.  One line.

| gate | before B1 | after M10 |
|---|---|---|
| `timed_lawcards` | 3 GREEN / **4 RED** / 4 UNRESOLVED | **7 GREEN / 0 RED** / 4 UNRESOLVED |
| `timed_wvec_gate` digest identical | 0 / 88 | **63 / 88** |

C4, C5, C10 and C12 — RED since T2b and gradientless since T3 — are **GREEN**.
C1 and C3 are GREEN with their pause populations now reproduced EXACTLY
(sim 43 vs chip 43 events at N=8, 30 vs 30 at N=12; they were 38/43 and 26/30
at T3), which is Q1 paying out on the Arm-C sled.  The four UNRESOLVED cards
(C2, C6, C7, C11) are unchanged and are stimulus gaps, not model failures.

**There are now NO RED law cards.**

### 14.4 B2 — THE VICTORY TRANCHE, captured and scored against the frozen bar

`python3 sw/t4_board.py b2` — the 216-seed population frozen and committed in
`sw/testdata/t4/b2-tranche/population.json`
(sha256 `08ec6dc4...`) BEFORE the first capture; socket, `use_core=False`, no
flashing; 46 s of board time; raw 64-bit words and full per-clock rows retained
per cell with sha256.

**A protocol correction, MEASURED not assumed, and declared as a deviation.**
The first pass flagged 84 of 216 cells "unstable" under the T2b blackbox
projection.  Diagnosed on the board before anything was scored: over four
cells x three repetitions each, **every differing row is in indices 0-8 and
NOT ONE row from 9 on differs.**  Rows 0-8 are the capture's reset settling and
are excluded by `fuzz_classify.diff_rows` — the frozen T3 column policy this
gate is scored with.  The stability projection was therefore changed to the
gate's OWN window (rows 9+); the stricter T2b number is retained beside it.
This is a post-capture change to a registered criterion and is recorded as
one.  With it: **0 cells excluded for instability.**  A direct check of the 12
promotion cells at 5 repetitions each gives **12/12 stable at 4 MHz and 12/12
at 8 MHz**; 6 of 12 differ BETWEEN the two frequencies, which is the T2b P1
phenomenon (within-cycle pulses read at a fixed sampling edge) and is recorded,
not scored.  Every stored row stream is the 4 MHz capture, matching the whole
banked corpus.

**THE SCORE, against §14.0's bar, as written:**

| | metric | bar | measured | |
|---|---|---|---|---|
| **V0** | hard failures | 0 | **0** | **PASS** |
| **V1** | scored seeds cycle-exact over the whole window | >= 55.6 % | **117 / 188 = 62.2 %** | **PASS** |
| **V2** | median divergence-free prefix FRACTION | >= 1.000 | **1.000** | **PASS** |
| **V3** | every non-exact seed's first divergence in a NAMED family | 100 % | **100 %** (Q2 42, `qs` 18, arbitration 10, `data` 1) | **PASS** |
| **V4** | `wrand` strata vs fixed strata | within 10 points | **wrand 71/107 = 66.4 % vs fixed 46/81 = 56.8 %** — 9.6 points, and the random-wait side is BETTER | **PASS** |
| **V5** | the campaign's literal phrasing: "fresh random-wait tranche **cycle-exact**" | V1 = 100 % | **62.2 %** | **FAIL** |

Population 216, scored 188, excluded 28 OPEN_BUS (declared in advance,
detected with the bank's own detector), 0 UNSTABLE, 0 EVT (excluded at
GENERATION, so the denominator could not move).

**The pre-registered falsifiable prediction is CONFIRMED**: the fresh
unselected tranche scores **62.2 %** against the adversarially-selected bank's
**55.6 %** — the bank is a harder population, as predicted in advance and for
the reason predicted (every seed in it was PROMOTED for diverging against an
earlier model).

**The verdict, stated honestly.**  V0-V4 PASS.  **V5 FAILS**, exactly as
pre-registered: the model is not cycle-exact over whole 1,300-4,000-clock
programs and no restatement of "cycle-exact" is offered.  The campaign's
victory condition is therefore **PARTIAL**: the wait axis is not the weak axis
any more — it is the STRONG one (V4, and by a margin) — and 62 % of fresh
never-before-seen random-wait programs are reproduced clock for clock from
RESET to the done marker with zero exceptions, against 2.6 % at T3 entry.
What remains is Q2 and its `qs` successor, both named, both localised to a
clock, and one of them half-measured (§14.2).

### 14.5 A30 — settled to a DATAPOINT, from the banks, because M9 made MD observable

The parked probe A30 (`ucsim_campaign_verdict_2026-08-01.md` §61/§34) asks
which bank the ROM's one ambiguous micro-address `111.00000010.00` selects:
bank A is a SINGLE acknowledge, bank B a two-cycle INTA pair.  Silicon runs
bank B; the open question is *why* — an emulation-mode 14th input to the
micro-address decoder, or a fixed priority with bank A dead silicon.  The
verdict doc's own limit was that the three candidate acknowledges were ones
**"the model BELIEVES were taken with `MD = 0`"**, i.e. contaminated by the
model, and all three sat in already-divergent seeds.

**M9 removes exactly that limitation: MD is now readable straight off the
pins**, on the PS nibble of every cycle, with no model in the loop.  Re-running
the census over all 3,242 banked captures with MD read from PS3:

* **189 of 3,242 seeds put MD = 1 on the pins at some point** — emulation mode
  is far commoner in the corpus than `has_brkem` reports (§14.1).
* INTA runs, keyed by run length and by the MD observed on the acknowledge
  cycles THEMSELVES: `len=2, MD=0` **760**; `len=1, MD=0` **8** (4 seeds x 2,
  acknowledges separated by an intervening cycle); **`len=2, MD=1` — 1**.
* That one is `t30-raw/raw_3821`, rows 969-981, deep inside the capture: two
  complete INTA cycles, **both carrying `ps = 0xE` = MD | IE | CS**.  A clean,
  uncontaminated, two-cycle pair taken in emulation mode.

**Verdict: a DATAPOINT, not a closure, and it is reported as one.**  It is the
first A30 observation that does not depend on the model's belief about MD, and
it points at **bank B / fixed priority** — the emulation-mode-input hypothesis
predicts a SINGLE acknowledge here and a single acknowledge is not what the
chip did.  n = 1.  The settling experiment is still the ledger's own directed
capture (a contained program that runs `BRKEM`, stays in 8080 mode with IE set,
and takes an INTR) — but it is now much cheaper to score, because MD no longer
has to be inferred.

*The other parked probes were NOT run* and that is recorded rather than
hidden: status-latch persistence (its ROM-sweep precondition was not verified
offline in this stage), R6 BCD `CL=0`, the two POLL BUSY split probes, R7
CMP4S, and F1 BUSLOCK.  The board session was spent on B1 and B2, which is
where the pre-registration put it, and A30 turned out not to need board time
at all.

### 14.6 Gates (measured, this machine)

| suite | result |
|---|---|
| v0.1 arch | 169,000 / 169,000 |
| v0.2 arch | 347,000 / 347,000 |
| v0.3 arch | 3,699,998 / 3,699,998 |
| v20suite arch | 3,125,000 / 3,125,000 |
| mod3_illegal (`--residue stale-ea`) | 128 / 128 |
| **total** | **7,341,126** |

```
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all              # 165,490 (w0)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1 # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3 # 1,200/1,200
python3 sw/check_boot.py --timed 220 # MATCHES over 220 rows
python3 sw/timed_scenario.py         # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py     # walk/pushes/active/halt/full 154/154
python3 sw/timed_ins_replay.py --raw # rails 1312/1312, R2 782/800, vs-chip 2624/2624
python3 sw/timed_wvec_gate.py        # count 88/88, cycles +0.0 %, digest 63/88
python3 sw/timed_lawcards.py         # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py             # THE T3 GATE -- 947/1702 exact, 0 hard failures
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds
                                     # THE VICTORY TRANCHE -- 117/188 exact
```

Two new standing instruments, both read-only and both usable on either side:
`sw/q1census.py` (the queue-pop census over any per-clock row stream) and
`sw/q1diff.py` (chip vs sim, pop by pop, naming which pop moved).

### 14.7 T5 handoff

1. **Q2's EU half** — the stage's largest named residual and the one with the
   most evidence already attached (§14.2).  The PORT half is measured (the
   queue port frees at T4+2 under waits, 293/293); the EU-side flush RAISE
   clock is `last pop + a` with `a` varying 4..7 by microcode path and is
   UNMEASURED.  Landing the port half alone costs 194 cycle-exact seeds, so it
   must be landed WITH the raise clock, not before it.  A directed factorial
   over the branch forms (`70-7F`, `E9`, `EB`, and the trap/flush paths) at
   controlled wait levels is the experiment.
2. **The `qs` successor family** (324 seeds, `qs -!=F` dominant): a pop display
   one clock out, downstream of Q2's neighbourhood.  Very likely the same
   mechanism seen from the other side; do it with Q2, not separately.
3. **The arbitration tail** (`bs PASV!=MEMR` / `CODE!=MEMR` / `CODE!=MEMW`,
   ~50 seeds in the bank and 10 in the fresh tranche) — an EU access and a
   fetch swapping the same slot.
4. **`has_brkem` under-reports** (§14.1) — a FUNCTIONAL-side finding, not a
   timing one: the chip decodes a wide spread of undefined `0F xx` second
   bytes as BRKEM and the bank's flag counts only `0F FF`.  Any campaign
   statistic keyed on that flag (including the ucsim verdict's own 8080-mode
   counts) is understated and should be re-derived from PS3, which is now
   observable.
5. **A30** (§14.5) — one uncontaminated datapoint favouring bank B / fixed
   priority; the directed BRKEM+INTR capture still settles it and is now cheap.
6. **The parked probes not run**: status-latch persistence (verify its
   ROM-sweep precondition offline first), R6 BCD `CL=0` uninterrupted, the two
   POLL BUSY split probes, R7 CMP4S, F1 BUSLOCK.
7. Unchanged from §13.7: the four UNRESOLVED law cards (C2, C6, C7, C11) are
   STIMULUS gaps — C6/C7 are board-by-construction (a uRMW mem-write ready at
   T4 with a controlled Tw parity), C2 needs a queue-fill transient, C11 needs
   a capture that isolates one `owns_slot` source.  The w0-only `F3AA cx >= 2`
   residual (907 cases) and the `fz90002` N=8 event-72 sled cell also stand.

---

## 15. T5 — CLOSURE

The campaign is closed.  The answer document is
`docs/notes/ucsim_t_campaign_verdict_2026-08-02.md`; the plan as executed is in
the repo verbatim at `docs/notes/ucsim_t_campaign_plan.md`.  Nothing in §0-§14
is retracted by this section.

**Status: CLOSED 2026-08-02.  Victory condition PARTIAL — V0-V4 PASS, V5 FAIL
(§14.4), reported as pre-registered.**

### 15.1 Final counts

| | |
|---|---|
| v0.1 cycle rows at w0 | **165,490 / 166,400 (99.45 %)** — 910 short: 907 REP `cx>=2` + 3 tails |
| v0.1-w1 / -w3 | **1,200 / 1,200** and **1,200 / 1,200** |
| arch through the TIMED path | 166,800 / 169,000 (the 2,200 pin-event forms, **S9**) |
| golden window located | 168,720 / 169,000 |
| boot replay from RESET release | **220 / 220 rows**, loop period 64 exact on both legs |
| ENTER waited tranche | **154 / 154** on all five levels |
| INS `case250` STRICT rails vs the chip capture | **2,624 / 2,624**; write rails 1,312/1,312; R2 issue 782/800 (= the offline pilot) |
| INS whole-program leading accesses | **173,556 / 173,556** in kind+address, **all 173,556 on the same T1** |
| L1 oracle replay | **18 PASS / 0 FAIL / 9 SKIP** |
| wvec corpus vs SILICON | access count **88 / 88**; bus cycles 16,048 vs 16,048 (**+0.0 %**); per-cycle digest **63 / 88** |
| law cards | **7 GREEN / 0 RED / 4 UNRESOLVED** (C2, C6, C7, C11 — all stimulus gaps) |
| `timed_fuzz`, banked | **947 / 1,702 (55.6 %)** cycle-exact; median prefix 1,068 rows, fraction **1.000**; >=0.5 / >=0.9 = 1,192 / 950; 0 hard failures |
| `timed_fuzz`, the VICTORY TRANCHE | **117 / 188 (62.2 %)** cycle-exact; median prefix fraction **1.000**; 0 hard failures |
| functional corpus | **7,341,126 / 7,341,126**, zero regressions |

**One number improved and the campaign did not notice it.**  §11.6 recorded the
INS whole-program measure at 56,736 of 173,556 leading bus cycles and §13.3 at
127,712 / 173,556; §14 never re-ran it.  Re-measured at T5 it is
**173,556 / 173,556, every one on the same T1** — the Q1 mechanisms (M8/M8a/M8b)
closed it.  Recorded here rather than in a stage section, because that is where
it was measured.

### 15.2 T5 gate ledger — every standing gate, re-run immediately before the commit

```
make -C sim test                                                          # disasm: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 165,490 (w0)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py                                          # 154/154 x5
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800
python3 sw/timed_wvec_gate.py             # count 88/88, cycles +0.0 %, digest 63/88
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 947/1702 exact, 0 hard failures
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 117/188 exact
```

**Zero regressions.**  Every figure above is identical to the T4 close (§14.6)
except the two that were never measured at T4: the INS whole-program agreement
(§15.1) and the wvec bus-cycle absolute (16,048 vs 16,048, previously reported
only as a percentage).

*Environment note, unchanged since §7.10:* `export TMPDIR=~/.cache/ucsimt-tmp`
before building or running anything that uses `tempfile`; `/tmp` is a small
tmpfs on this machine.

### 15.3 What remains ASSUMPTION at closure

The ledger's own rule is that at closure the set still tagged **ASSUMPTION** is
precisely "what the assets do not determine about timing".  That set is now
**empty of load-bearing entries**: every ASSUMPTION booked in §2-§9 was either
promoted or retracted —

* §2.5 `kSegZero` PS code: **ASSUMPTION -> MEASURED** (§10.5, 4,800 rows).
* §2.6 undriven byte lanes retain: **RETRACTED** (§8.1); it was the rig's fill.
* §2.8 the instruction-boundary QS=F rule (S10): **REMOVED** (§7.8).
* §7.7's `R`-row one-clock-per-iteration, booked PROVISIONAL: **survives
  unchanged**, disciplined by the FARJMP bubble (§8.5).

What stands in their place is not assumption but **absence of stimulus** — the
four UNRESOLVED law cards, the scoped-out interrupt/INTA axis, 8080-mode
timing, and Q2's EU-raise clock.  Each is named in the verdict's §(c) with the
capture that would close it.  Scaffolding S1-S10 are all removed or, for S9's
event scheduler, converted into a named open item.

### 15.4 Housekeeping done at T5

* `ROADMAP.md` — dated `ucsim-t` section: the campaign, its outcome, the retired
  biu-rebuild disposition, and what regenerating the RTL from the mechanism
  ledger would look like as the natural next campaign.
* `sim/README.md` — the timed-mode section refreshed off T0 (it still described
  the T0 scaffolding as current).
* `docs/notes/ucsim_t_campaign_plan.md` — the plan committed in-repo verbatim,
  the functional campaign's S4r lesson applied.
* `docs/notes/ucsim_provenance.md` — an **erratum** added recording the
  `has_brkem` under-report (M9, §14.1), routed to the functional campaign's
  ledger where the flag is used.
* Thirteen inconsistencies found while consolidating are in the verdict's §(g),
  reported rather than papered over; two of them (the stale "12 w0 tails" and
  the stale T3 "tails = 15") are corrected numbers, and one is an improvement
  the campaign under-reported (§15.1).

---

## 16. POST-CLOSURE ADDENDUM — R1, the REP re-entry session (2026-08-02)

**This section is an ADDENDUM.  Nothing in §0-§15 is edited or retracted by it;
the registered V1-V5 record in the verdict stands exactly as written.**  The
campaign closed (§15) with one open w0 physics question — the REP string family
at `cx >= 2`, 907 cases, the entire non-tail w0 shortfall (§10.7, §12.4).  This
session went after it offline, found it, and re-scored everything downstream.

**Outcome: the 907-case residual is CLOSED.  Two mechanisms, one correction.**
`v0.1` at w0 goes **165,490 -> 166,397 of 166,400**; all five REP forms are
**500/500**; the only w0 cases left in the whole suite are the three
single-case tails (`0F12`, `C1.6`, `F7.4`), which did NOT close for free.
Board contact was authorised and NOT used: R1 was decisive offline, so the
pre-registration rule for R2 never fired.

### 16.0 The instrument — `sw/repcensus.py`

The q1census lesson is the whole design: the chip rows and the model rows go
through the SAME reconstruction.  Golden rows are `case["cycles"]` (built by
`sw/emit_suite.build_rows`), model rows come from
`check_core.build_rows_sim` over the record stream; nothing is re-derived
locally.  Per case it extracts every bus cycle as (T1 row, T4 row, status,
address), the store/load sequence and its per-iteration period, the
window-closing F pop and its offset from the last store's T4 and T1, `cx`, and
the ENTRY PHASE (the row the opcode itself popped on).  It reads the 2,500 v0.1
goldens and, with `--p4`, the T2b silicon pair (`sw/testdata/t2b/p4-f3aa`,
same schema, same extractor) at w0/w1/w3.

A second instrument, **`V30SIM_ROWTRACE=1`**, is an env-gated stderr line per
micro-row — the clock the row is REACHED on, the ROM row index and its
disassembly.  It is the diagnostic the row schedule was read out of, it touches
no model state, and it is the direct analogue of T3's `V30SIM_EVALTRACE`.
(`sim::Biu::clock()` returns -1 so the shared interpreter compiles on both bus
policies.)

### 16.1 H1's four predictions, SCORED

| prediction (plan, verbatim) | census verdict |
|---|---|
| the chip's iteration cadence LOCKS to the bus at `cx >= 2` and absorbs the entry phase | **CONFIRMED.** 18 groups of cases share an identical store grid but differ in entry phase; the chip's closing pop is CONSTANT across the group in **18 / 18**, the model's in **12 / 18** (before) and **18 / 18** (after) |
| `cx = 1` never enters the pinned regime -> EU-path-variable exit | **CONFIRMED, and the ledger's statement of it was INCOMPLETE** — see §16.5 |
| under waits the bus period exceeds the row path everywhere -> w1/w3 unaffected | **CONFIRMED.** w1 and w3 are 1,200/1,200 before and after; the P4 silicon pair is exact at w1/w3 both ways |
| REP STOS slope 4/iter, MOVS 8/iter stay emergent | **CONFIRMED, and they were ALREADY exact.** Store-to-store T1 delta, chip vs model, is identical in every case of every form both before and after (`F3AA` 4, `F3A4` 8, `F3AB` 4, `F2AA` 4, `F3A5` {4,8,12}).  The loop BODY was never the problem |

**H1 itself is CONFIRMED in kind and CORRECTED in detail.**  The plan named
three candidate release indices — prior-access accept, completion eval, or
T4+2.  The measured one is **prior-access ACCEPT**, and the w0 STOS 4-clock
period discriminated it exactly as the plan predicted it would.  H2 (the
max-of-deadlines reading) was not needed.

### 16.2 M10 — ONE REQUEST SLOT, and it frees when the bus TAKES the request

The EU has a single bus-request register.  A micro-row that asks for a bus
cycle cannot hand its request over while the previous one is still sitting in
that register; the register is freed when the bus takes the request — **the
accepted cycle's own T1** — and the blocked row issues ON that clock.  A SPLIT
word access is ONE request that the BIU serves with two cycles, so the slot is
taken once and freed at the **LAST** of the two cycles' T1.

*What it changes.*  The row engine, and only the row engine.  The bus grid, the
eval, the queue, the prefetch scheduler and the OPR interlock are untouched.
What it removes is the model's ability to let the ROM row cadence free-run
arbitrarily far ahead of the bus.  The string loops are the only sequences in
the corpus whose row body is SHORTER than their bus period, which is why they
are the only place the free-run was visible — and why w1/w3 were already exact
(§12.4): under waits the bus period exceeds the row path everywhere and the
slot is never the binding deadline.

*How it was measured, on the discriminating pair (§10.7's own).*  With
`V30SIM_ROWTRACE` the STOS-family exit path is nine clocks from the store row
`00BF` to the successor's pop, and `cx = 0` / `cx = 1` pin both that path and
the entry (micro-row 0 at the opcode pop + 2, M8b).  Working backwards from the
chip's closing pop, `F3AA` case 16 and case 10 — whose EU entries are two
clocks apart and whose store grids are identical — BOTH require the second
store row to run on the FIRST store's own **T1**.  §10.7 read that same
geometry as "the first store's T2"; it is T1, and the difference is that the
released row issues ON the freeing clock rather than after it.

*The last-cycle half was measured separately, and cleanly.*  Releasing at the
FIRST cycle's T1 leaves `F3A5` (`REP MOVSW`) at 406/500, and the residual is
exactly the geometry (**split load, aligned store**) in every `cx` band — 94
cases, and every other geometry exact.  Releasing at the LAST cycle's T1 takes
`F3A5` to **500/500** and changes **nothing else in the 169,000-case suite**.
That is the whole evidence for the half, and it is one-sided.

### 16.3 M5b, said once — the shadow store rotates on the ACCESS's address

M10 exposed a latent disagreement between the two write-data paths.  `mem_write`
already implemented M5b ("ONE pass through the A0 byte swapper, on the ACCESS's
own address — both cycles of a split then drive that same rotated value"); the
OPR-**shadow** path (a store that reaches T1 without having been given data)
re-derived the rotation from each CYCLE's address, so it drove the second half
of a split unrotated.  Before M10 the shadow almost never covered a split
store (12 `data` cases in the whole suite); after it, 97.

**The chip settles it and it settles the pre-existing 12 too.**  `F3AB` case 0
(`rep stosw` at an odd DI, AW = `B852`) drives **`52B8` on all six cycles**, the
even-address halves included; `F3A5` case 6 drives `29A0` on both halves of its
last store.  The shadow now uses the access's own `odd_base`.  `data` column
diffs over the five REP forms: **12 -> 0**.

### 16.4 M11 — the redirect bubble is not paid on a jump BACK BY ONE ROW

With M10 landed, 166 cases remained: `F3AA`/`F3AB`/`F2AA` at `cx = 2` whose EU
entered late enough that the slot was already free (store T1 minus the row's own
clock = 2).  Those cases are a **subtraction, not a fit**.  Write `j` for the
clocks from the opcode's own pop to the FIRST store row `00BF`, `K` for the
clocks from a store row to the successor's pop along the exit path, and `L` for
the loop body `00BF -> 00C0 -> 00BF`.

* `cx = 1` is 100 % exact and its closing pop is `entry + j + K` wherever the
  EU is the binding deadline, so **`j + K = 14`** is fixed by the closed record.
* Take the `cx = 2` cases with **lead 7** (`first store T1 - entry = 7`, so the
  first store row free-runs at `T1_1 - 7 + j`).  The chip's closing pop is
  `T4_2 + 2 = T1_1 + 9`, so the LAST store row runs at `T1_1 + 9 - K`; M10 pins
  it to `T1_1`, hence **`K = 9`** and therefore **`j = 5`**.
* M10's block can only pin it if the free-run reaches `T1_1` or earlier:
  `(T1_1 - 7 + j) + L <= T1_1`, i.e. `L <= 7 - j = ` **2**.

The STOS REP loop is exactly two rows — `00BF` (MEMW) and `00C0`
(`JMP REP 3`, taken) — so the taken `JMP REP` costs no redirect bubble.  Every
quantity in that chain is pinned by cases the model already reproduced
exactly; nothing in it was chosen.

Stated generally: **a taken micro-JMP whose target is the row immediately
before it costs no redirect bubble** — the target is the row the sequencer read
one clock ago, so no new ROM read is needed, and the ROM's tightest loop runs
at one row per clock.  Everything else keeps §7.7's bubble.

**SCOPE, stated because it is thin.**  A census of every taken micro-JMP the
suite executes (first six cases of every form) finds **59 distinct sites, 8 of
them backward, and exactly ONE by a single row** — `00C0`, the STOS/SCAS REP
loop.  So the assets do NOT separate the general form from "the STOS REP
loop-back is free".  The general form is kept because it is the falsifiable
one.  Two rejected alternatives, both measured over the full 169,000-case
suite:

| variant | v0.1 w0 | verdict |
|---|---|---|
| no bubble on any taken `JMP REP` (`cond == REP`) | 163,508 | **FALSIFIED** — closes F3AA/F3AB/F2AA but destroys `F3AC F3AD F3AE 64Ax 65Ax E0` (LODS/SCAS/LOOP, 500 -> 253…342 each), whose loops are 4-6 rows and DO pay it |
| no bubble on any taken BACKWARD micro-JMP | 162,536 | **FALSIFIED** — same, plus `0F20/0F22/0F26` |
| no bubble on a jump to `loc - 1` (**landed**) | **166,397** | moves three forms, all upward, all to 500/500, and nothing else at all |

### 16.5 What the census CORRECTS in the closed record

* §10.7's table reads "`cx = 1`, `F3AA F2AA F3AB` (370) — 100 % exact".  That
  is true of those three forms.  It is **not** true of `cx = 1` as a band: at
  entry to this session `F3A4` was **60 / 119** and `F3A5` **73 / 123** at
  `cx = 1` — 109 further cases inside the 907.  The plan's context section
  ("`cx = 0` and `cx = 1`: 100 % exact") inherits the over-claim.  Both are now
  500/500 and the band is **612 / 612**.
* §10.7's "`cx >= 2`, `F3AA`: golden always 2" generalises to the byte forms
  only.  `F3A5` and `F3AB` show golden offsets of **1 AND 2** at `cx >= 2`, and
  the census separates them with no exceptions: **offset 1 iff the last store
  is the second half of a SPLIT** (123/123 and 126/126).
* §10.7's reading of the discriminating pair — "both land on row 20 if the
  loop's SECOND store row `00BF` runs on the FIRST store's **T2**" — is off by
  one against the model's own row schedule: it is the first store's **T1**.
  §10.7's probe "released the store row at the previous store's T1" (+25 cases,
  213 new diffs) is not this mechanism: it had no last-cycle rule, no
  `first_of_access` scoping, and no M5b unification, and its 146 `data` diffs
  are §16.3.

### 16.6 Q2 — RE-MEASURED, NOT LANDED, and RE-DIAGNOSED

R3's condition was to land Q2's measured port half **together with** the
mechanism-derived EU raise, gate: the 133-case redirect family to 0 without the
masking regression §14.2 recorded.  H1 predicted the EU-raise clock would stop
being a free parameter once the row cadence was bus-derived.  **That prediction
is FALSIFIED.**  With M10/M11 landed, the port half was re-tried in both of its
possible expressions:

| Q2 port-half variant | v0.1 w0 | v0.1-w1 | v0.1-w3 | timed_fuzz |
|---|---|---|---|---|
| baseline (this session's model) | **166,397** | **1,200** | **1,200** | **1,002 / 1,702** |
| absorb window shortened to `eval+1` | 164,615 | 1,143 | 1,200 | 532 / 1,702 |
| absorb window **keyed to T4** (`[T4, T4+1]`, the correct expression) | **166,397** (neutral) | **1,143** | 1,200 | 796 / 1,702 |

The T4-keyed form is the right one — it is M6's own keying, it is exactly
w0-NEUTRAL by construction (at w0 `e = T3`, so `[e+1, e+2] == [T4, T4+1]`),
and it produces Q2's measured "the port frees at T4+2" under waits.  It is
still a net regression, and the w1 leg is a number §14.2 never had: the loss is
**entirely one form, `EB`, 200 -> 143**, all 114 diffs in the `qop` column.

**And the diagnosis is sharper than "the EU half is unmeasured".**  In the `EB`
w1 cases the chip shows the flush `E` on the SAME clock as the redirect fetch's
status (row 6, `T4+3`), and model and chip AGREE on the redirect's status
clock; the port change moves only the `E`, to `T4+2`, breaking the pairing.  In
Q2's own 293 seeds the chip likewise shows **the `E` and the redirect's status
on one clock** (`T4+2`), and the model shows **both** at `T4+3`.  So the two
populations agree on the rule and disagree on the clock: **the `E` rides the
redirect's own display clock, and Q2 is a REDIRECT-COMMIT question, not a
QS-port question.**  The port half is a symptom of it.  That reframing is the
session's contribution to open item 1; it does not close it, and the directed
branch-form factorial §14.2 asked for is still the capture that would.

Reverted.  The model is left in the state that maximises the ratchet, exactly
as §14.2 left it.

### 16.7 The three tails — checked, NOT closed, NOT chased

`0F12`, `C1.6` and `F7.4` are still one case each (499/500, 9 / 4 / 4 row
diffs).  They did not close for free.  Per the plan they were not chased.

### 16.8 Gates (measured, this machine, immediately before the commit)

```
make -C sim test                                                          # disasm: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 166,397 (was 165,490)
python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms F3A4,F3A5,F3AA,F3AB,F2AA
                                                                          # 2,500/2,500 (was 1,593)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py                                          # 154/154 x5
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800,
                                          # whole-program 173,556/173,556 all on the same T1
python3 sw/timed_wvec_gate.py             # count 88/88, cycles +0.0 %, digest 69/88 (was 63)
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 1,002/1,702 exact (was 947), 0 hard failures
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 117/188 (unchanged)
python3 sw/repcensus.py --p4              # the census above
```

**Monotonicity, checked per FORM and not just in aggregate.**  Over all 347
forms of the v0.1 suite, exactly five moved and every one of them upward:
`F3A4` 192 -> 500, `F3A5` 303 -> 500, `F3AA` 336 -> 500, `F3AB` 411 -> 500,
`F2AA` 351 -> 500.  Arch (166,800) and window-located (168,720) are unchanged.

### 16.8a Provenance class, per finding

The ledger's own rule: every behaviour carries ROM / LAW / MEASURED /
ASSUMPTION, its evidence and its falsifier.

| finding | class | evidence | falsifier |
|---|---|---|---|
| **M10** the EU has ONE bus-request slot, blocking a row that carries a new access | **MEASURED** | the P4 silicon pair (`F3AA` 16/10, byte-identical programs, EU entries two clocks apart, chip retires both on one clock) plus 1,249 `cx >= 2` goldens; the w0 STOS 4-clock bus period is what makes the free-run visible | any capture where a micro-row issues a bus request while a previous EU access is still unaccepted — e.g. a string loop whose stores are spaced tighter than the bus period |
| **M10a** the slot frees at the accepted cycle's own **T1**, and the released row issues ON that clock | **MEASURED** | the same pair; T1-1 (commit) and T1+1 (T2) each miss the chip on one of the two cases | any `cx = 2` case whose closing pop is not `last store T4 + 2` while the row engine is bus-bound |
| **M10b** a SPLIT word access is ONE request; the slot frees at the LAST cycle's T1 | **MEASURED, one-sided** | `F3A5` 406/500 -> 500/500, residual before the fix exactly "split load, aligned store" in every `cx` band; nothing else in 169,000 cases moves | any split access whose successor row issues before the split's second cycle opens |
| **M11** no redirect bubble on a taken micro-JMP back by ONE row | **MEASURED for the one site the corpus reaches; the GENERAL form is the falsifiable statement, not an independently witnessed one** | the `j + K = 14` / `K = 9` / `L <= 2` subtraction in §16.4, 166 cases; two alternative predicates falsified at 163,508 and 162,536 | any OTHER `loc - 1` backward micro-JMP a future stimulus reaches that DOES pay a bubble |
| **M5b unified** the OPR-shadow store rotates on the ACCESS's A0, not the cycle's | **MEASURED** | `F3AB` case 0 (`52B8` on all six cycles of a split-store `rep stosw`), `F3A5` case 6; `data` diffs 12 -> 0 | any split store whose two cycles drive DIFFERENT words |
| **Q2 is a redirect-COMMIT question, not a QS-port one** | **OBSERVATION, not landed** | in the Q2 293 seeds and in all 57 `EB` w1 cases the chip shows the flush `E` on the same clock as the redirect fetch's status | any capture where the chip's `E` and its redirect's status fall on different clocks |
| the ROM loop bodies and their slopes | **unchanged, ROM + LAW** | store-to-store T1 deltas identical chip vs model in every case, before and after | — |

### 16.9 Ledger delta

| | at T5 close (§15.1) | after this addendum |
|---|---|---|
| v0.1 cycle rows at w0 | 165,490 / 166,400 (99.45 %) | **166,397 / 166,400 (99.998 %)** |
| v0.1 forms 100 % cycle-row exact at w0 | 326 / 347 | **331 / 347** |
| the five REP forms at w0 | 1,593 / 2,500 | **2,500 / 2,500** |
| v0.1-w1 / -w3 | 1,200 / 1,200 | unchanged |
| wvec per-cycle digest vs silicon | 63 / 88 | **69 / 88** |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | unchanged |
| `timed_fuzz`, banked | 947 / 1,702 (55.6 %) | **1,002 / 1,702 (58.9 %)** |
| `timed_fuzz`, >= 0.5 / >= 0.9 prefix | 1,192 / 950 | **1,221 / 1,005** |
| `timed_fuzz`, median first-divergence row | 1,068 | **1,105** |
| `timed_fuzz`, the VICTORY TRANCHE | 117 / 188 (62.2 %) | **117 / 188 (62.2 %)** — unchanged |
| functional corpus | 7,341,126 / 7,341,126 | unchanged |
| open w0 physics questions | REP `cx >= 2` (907) + 3 tails | **3 tails only** |
| mechanisms | M1-M9, M2r, M3c(retracted), M5b, M6, M7, M7b, M8 | **+ M10, M11** |

**The victory tranche did not move**, and that is worth saying plainly: the
REP mechanism buys +55 seeds on the banked population and 0 on the frozen
tranche.  V5 remains a registered FAILURE and this addendum does not touch it.
The tranche's largest named family is Q2 (42 of its 71 misses), which §16.6
re-measured and did not land.

## 17. POST-CLOSURE ADDENDUM #2 — Q2, the REDIRECT COMMIT (2026-08-02)

**This section is an ADDENDUM.  Nothing in §0-§16 is edited or retracted by
it; the registered V1-V5 record in the verdict stands exactly as written, and
so does §16.**  It closes the open item §16.6 named and re-diagnosed: Q2, the
redirect family, the largest named residual in the campaign and the largest
named family in the frozen victory tranche.

**Outcome: Q2 is CLOSED.  ONE mechanism, no new state, w0-neutral BY
CONSTRUCTION.**  The `timed_fuzz` bank goes **1,002 -> 1,272 of 1,702**
(58.9 % -> 74.7 %), the Q2 first-divergence family **300 -> 0** with **zero**
seeds newly broken, the frozen victory tranche **117 -> 154 of 188**, and the
silicon per-cycle wvec digest **69 -> 88 of 88**.  w0 is byte-identical form by
form (166,397; 0 of 347 forms moved) and w1/w3 stay 1,200/1,200.  Board contact
was authorised and NOT used: the census was decisive offline, so the
pre-registration rule for a board session never fired.

### 17.0 The instrument — `sw/q2census.py`, `sw/q2law.py`, `V30SIM_FLUSHTRACE`

The repcensus lesson again: the chip rows and the model rows go through the
SAME extractor.  `q2census.py` reads a row stream — golden `case["cycles"]`,
model `check_core.build_rows_sim`, or the fuzz bank's own `chip_rows` and the
sim's ndjson, i.e. exactly the two streams `sw/timed_fuzz.py` compares — and
returns, per FLUSH EVENT: the QS=E clock, the redirect fetch's STATUS DISPLAY
clock (`T1 - 1`, M2) and its T1, the cycle RUNNING at the flush and the last
one COMPLETED, with wait counts.

The flush INSTANT itself is an EU quantity and is not in question (the model
reproduces the whole w0 control-flow tranche), so it is read out of the model
with **`V30SIM_FLUSHTRACE=1`** — an env-gated stderr line per `flush()`, per
commit and per `E` display, touching no model state, the direct analogue of
`V30SIM_EVALTRACE` and `V30SIM_ROWTRACE` — and used as the census's
INDEPENDENT VARIABLE `x`.  `q2law.py` scores the chip's own answer against it.

### 17.1 The census — three candidate machines, and what the data said

The plan named three candidates.  The census settles all three, and the
answer is none of them as stated:

| candidate (plan, verbatim) | census verdict |
|---|---|
| (a) the flush commit rides the SAME eval instant family as everything else (`e_i`) rather than F3's flush-only T4 point | **FALSIFIED as stated, and RIGHT in kind.** The redirect does not ride `e_i`; what it rides is the eval at the END OF THE FLUSH CLOCK, which the model was suppressing — see §17.2 |
| (b) the redirect's request occupies the M10 request slot and the `E` is emitted at its accept (T1-keyed) | **FALSIFIED.** The `E` is not T1-keyed: over 12,259 w0 flush events the chip's `E` sits at the flush clock + 0/+1/+2/+3 and tracks the QS PORT, not any T1.  M10 is an EU-side register and never sees a fetch |
| (c) F1's parking is the artifact and the `E` is emitted unconditionally at the commit | **FALSIFIED.** 4,814 of the 12,259 w0 events show the `E` one clock BEFORE the redirect's display (the quiet-bus flush shows `E` on the flush clock itself), and 500 show it three before.  F1's port arbitration is real and is exactly right at w0 |

**What the census actually found** is that the two populations §16.6 could not
reconcile are ONE geometry seen at two flush instants.  Writing `x` for the
flush clock and `T4` for the last completed cycle's T4:

* the **300** Q2 fuzz seeds (§16.6's 293, re-counted after M10/M11): in
  **300 / 300** the flush lands at `x = T4 + 1`, the completed cycle is a CODE
  fetch, and the chip shows the `E` at `T4 + 2` — which is `x + 1`, and which
  is **the redirect's own status display clock in 300 / 300**.  The model
  showed both one clock later.
* the **57** failing `EB` w1 cases: in **57 / 57** the flush lands at
  `x = T4 + 2` and the chip shows the `E` at `T4 + 3` — again `x + 1`, and
  again **the redirect's status display clock in 57 / 57**.

So the chip's answer is the same in both: the port is released by the flush,
but not before the flush's own clock.  §14.2's "the port frees at T4+2 under
waits" is that statement read on a population whose flush happens to sit at
`T4+1`; the `EB` cases are the same rule read at `T4+2`.  A window keyed to T4
gets the first population right and the second wrong, which is exactly the
masking §14.2 and §16.6 recorded — twice.

### 17.2 M12 — THE FLUSH INVALIDATES EVERY LATCH THE COMPLETING CYCLE LEFT BEHIND

`flush()` already cleared three of them, and the code already carried the
sentence: *"a latch taken at index 2 of a cycle the flush then invalidates
cannot hold the eval off — the redirect must be free to go at once"* (M7's
`pf_arm_`, M6's `pf_land_`, M7b's `pf_infl_`).  **Two more latches were being
left standing, and they are precisely the two halves of Q2:**

* **the COMPLETION EVAL's reserved DISPLAY SLOT** (§11.2, `no_eval_`).  It is
  the completing cycle's decision that the next clock is its display clock; a
  flush invalidates that decision, so the end of the flush clock is an eval
  point again and **the REDIRECT commits there**.
* **the QUEUE-PORT ABSORB HOLD** (§11.3, F1(b), `push_absorb_`).  The hold
  exists because the fetch's bytes are LANDING; the flush discards them, so
  the port is released — **but not before the flush's own clock**, which the
  dying absorb still occupies (`push_absorb_clk_ = min(push_absorb_clk_, x)`).

That is the whole mechanism: two lines, no new state, no new field, no table,
no per-form case.

**W0-NEUTRAL BY CONSTRUCTION, and for the same reason the rest of M2r is.**
At w0 the completion eval sits at T3, so its display slot is T4 — a clock
INSIDE the cycle, which the idle-eval path never reaches.  And at w0 the
absorb hold is `[T4, T4+1]`, whose LAST clock is the EARLIEST clock a flush
can see it on at all: a flush at or before T4 finds the fetch still running
and zeroes its `push_n`, so no hold is created.  Under waits the eval is at T4,
the display slot is `T4+1`, and the hold is `[T4+1, T4+2]` — so a flush at
`T4+1` frees the port at `T4+2` (Q2's own 300 seeds) while a flush at `T4+2`
leaves the hold alone and the `E` stays at `T4+3` (the 57 `EB` w1 cases).
**One rule, both populations.**  Measured, not argued: w0 is identical form by
form, 0 of 347 forms moved.

### 17.3 The two halves are ONE mechanism — measured, and it is why the two prior attempts failed

Each half ALONE is exactly neutral on every scored population; only together
do they move anything.  That is the strongest available statement that they
are one mechanism and not two coincidences, and it explains both reverted
landings: §14.2 and §16.6 each landed a port half alone, and the port half
alone cannot pay because the redirect's own commit is what the `E` rides.

| variant | v0.1 w0 | v0.1-w1 | v0.1-w3 | `timed_fuzz` |
|---|---|---|---|---|
| baseline (the §16 model) | 166,397 | 1,200 | 1,200 | 1,002 / 1,702 |
| §16.6's absorb window keyed to T4 (the prior attempt) | 166,397 | **1,143** | 1,200 | **796** |
| ...T4-keyed absorb + the display-slot clear | 166,397 | **1,143** | 1,200 | 986 |
| display-slot clear ALONE | 166,397 | 1,200 | 1,200 | 1,002 (neutral) |
| absorb TRUNCATION alone | 166,397 | 1,200 | 1,200 | 1,002 (neutral) |
| **M12 — both (landed)** | **166,397** | **1,200** | **1,200** | **1,272** |

### 17.4 What is left in the neighbourhood, named

The same census over the whole bank after M12 leaves **93** flush events (of
16,148) whose `E` the model still misses, and they are ONE family, not Q2's:
**77 of them** have the chip's `E` at `x + 2` and the model's at `x + 0`, with
the last completed cycle a **ZERO-WAIT MEMW whose T4 is `x - 1`**.  After a
w0-length WRITE the chip defers BOTH the `E` and the redirect by one further
clock — a post-write bus turnaround, not a queue-port fact.  It is the
`qs -!=E` fuzz family (93 seeds).  **Named, not chased**, per the plan; its
falsifier is any capture where a flush one clock after a zero-wait store's T4
shows the `E` on the flush clock.

The three tails (`0F12`, `C1.6`, `F7.4`) did NOT close for free: 499/500 each,
9 / 4 / 4 row diffs, unchanged.  Per the plan they were not chased.

### 17.5 Gates (measured, this machine, immediately before the commit)

```
make -C sim test                                                          # disasm: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 166,397 (unchanged, 0/347 forms moved)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py                                          # 154/154 x5
python3 sw/check_enter_nesting.py --sim ucsim-timed                       # PASS
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800,
                                          # whole-program 173,556/173,556 all on the same T1
python3 sw/timed_wvec_gate.py             # count 88/88, cycles +0.0 %, digest 88/88 (was 69)
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 1,272/1,702 exact (was 1,002), 0 hard failures
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 154/188 (was 117)
python3 sw/q2law.py --fuzz ALL            # the census above
```

**Monotonicity, checked per FORM and per SEED, not just in aggregate.**  Over
all 347 forms of the v0.1 w0 suite **zero moved** (331/347 at 100 %, before and
after).  Over the 1,702 scored fuzz seeds, **270 newly exact and ZERO newly
broken**.  w1/w3 are 1,200/1,200 either way, `EB` w1 200/200 — the masking
regression §14.2 and §16.6 each hit is checked directly and does NOT reappear.

### 17.5a Provenance class, per finding

| finding | class | evidence | falsifier |
|---|---|---|---|
| **M12** a flush invalidates the completion eval's reserved DISPLAY SLOT, so the end of the flush clock is an eval point and the redirect commits there | **MEASURED** | 300/300 Q2 fuzz events (flush at `T4+1`, chip redirect display at `T4+2`, model at `T4+3`) and 57/57 `EB` w1 events (flush at `T4+2`, both at `T4+3`); w0 identical form by form | any waited capture where a flush lands on the completion eval's display clock and the redirect is NOT displayed on the next clock |
| **M12b** a flush releases the QS-port absorb hold, but not before the flush's own clock | **MEASURED** | the same two populations: the `E` is on the redirect's display clock in 300/300 and 57/57; keying the hold to T4 instead costs `EB` w1 200 -> 143 and the bank 1,002 -> 796 | any capture where the `E` after a flush inside the absorb window falls other than one clock after the flush |
| the two halves are ONE mechanism | **MEASURED, one-sided** | each half alone is EXACTLY neutral on w0, w1, w3 and all 1,702 scored seeds; together +270 seeds and 0 losses | any stimulus separating them |
| **the post-write turnaround** (`E` and redirect both one clock later after a zero-wait MEMW ending at `x-1`) | **OBSERVATION, not landed** | 77 of the 93 residual `E` events, one signature, zero exceptions inside it | see §17.4 |

### 17.6 Ledger delta

| | after §16 | after this addendum |
|---|---|---|
| v0.1 cycle rows at w0 | 166,397 / 166,400 | **166,397 / 166,400** (identical, 0/347 forms moved) |
| v0.1 forms 100 % cycle-row exact at w0 | 331 / 347 | 331 / 347 |
| v0.1-w1 / -w3 | 1,200 / 1,200 | 1,200 / 1,200 |
| `EB` at w1 | 200 / 200 | **200 / 200** (the masking regression does NOT reappear) |
| wvec per-cycle digest vs silicon | 69 / 88 | **88 / 88** |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | unchanged |
| `timed_fuzz`, banked | 1,002 / 1,702 (58.9 %) | **1,272 / 1,702 (74.7 %)** |
| `timed_fuzz`, >= 0.5 / >= 0.9 prefix | 1,221 / 1,005 | **1,393 / 1,273** |
| `timed_fuzz`, median first-divergence row | 1,105 | **1,216** |
| `timed_fuzz`, the VICTORY TRANCHE | 117 / 188 (62.2 %) | **154 / 188 (81.9 %)** |
| functional corpus | 7,341,126 / 7,341,126 | unchanged |
| open w0 physics questions | 3 tails | 3 tails |
| mechanisms | M1-M11, M2r, M5b, M6, M7, M7b | **+ M12** |

**V5 stays a registered FAILURE.**  The tranche re-score is 154/188, not
100 %, so the registered bar is NOT met and the registration is not rewritten:
V5 reproduces as a registered failure, and this addendum improves it by 37
seeds.  Q2 was 42 of the tranche's 71 misses at T4 (§14.4); 37 of the 71 now
close, and the tranche's remaining 34 misses have NOT been re-classified here
— that is the next stage's survey, not a claim of this one.

## 18. POST-CLOSURE ADDENDUM #3 — THE TURNAROUND RESIDUAL IS NOT A TURNAROUND (2026-08-02)

**This section is an ADDENDUM.  No text in §0-§17 is edited, and the registered
V1-V5 record in the verdict stands exactly as written — but this addendum DOES
retract one recorded reading, §17.4's "post-write turnaround", and says so in
its own §18.1 and §18.4a.  §17.4 is left standing as written and is superseded
here, not rewritten.**  It goes after the residual §17.4 named: 93 flush events
(of 16,148) whose `E` the model misses, 77 of them one shape — the chip's `E`
at `x+2`, the model's at `x+0`, with the last completed cycle a ZERO-WAIT MEMW
ending at `x-1`.  §17.4 read that as a POST-WRITE BUS TURNAROUND.

**Outcome: that reading is FALSIFIED BY ITS OWN CONTROL, and the residual is
TWO MACHINES, neither of them a turnaround.**  475 events carry §17.4's stated
signature and **398 of them are already exact**; the discriminator is not the
write, the wait level, or the flush's position in the bus cycle.  It is the
**8080 EMULATION MODE FLAG**, and the chip announces it on the pins (M9's PS3).
One mechanism — **M13** — closes 80 of the 93; the other 13 are a separate,
waited family and are named, not chased.  Board contact was authorised and NOT
used: the census was decisive offline, so the pre-registration rule for a board
session never fired.

**Said plainly up front: NO SCORED POPULATION MOVES.**  `timed_fuzz` stays
1,272 / 1,702, the frozen tranche stays 154 / 188, w0 stays 166,397 and w1/w3
stay 1,200/1,200.  What moves is the residual census (93 → 13 events) and the
first-divergence row of 122 seeds, all of them LATER and none earlier.  The
reason the seed counts do not move is a SECOND fact in the same family that is
measured here and deliberately NOT landed (§18.3).

### 18.0 The instrument — `sw/tacensus.py`

Two censuses, both in one file, and the second is the one that settled it.

* the MODEL-PAIRED census (default) extends `q2law`'s per-event record with the
  full `V30SIM_FLUSHTRACE` `FX` state at the flush clock (outstanding EU
  request, committed-but-not-started cycle, queue occupancy, the pre-flush
  `no_eval_` and absorb window) and with the NEXT bus cycle on each side, so
  the `E` and the redirect COMMIT are scored separately.  Chip and model go
  through the SAME extractor (`q2census.cycles_of`), the repcensus/q2census
  discipline unchanged.
* the CHIP-ONLY census (`--chains`) reads `entry["chip_rows"]` and nothing
  else: every TRAP PUSH CHAIN in the bank — three back-to-back MEMW cycles
  whose addresses step down by 2, followed by a CODE fetch — with the
  store-2-to-store-3 T1 gap and **PS3, the emulation-mode status bit (M9)**, on
  each store's data phase.  No model and no micro-row trace, so it is valid on
  every seed in the bank, including the ones whose model run diverges earlier.

A third view, used for diagnosis only and not committed, joined each event to
the `V30SIM_ROWTRACE` micro-row the flush was called from.

### 18.1 The census — §17.4's shape, scored against its own control

| reading | verdict |
|---|---|
| §17.4, verbatim: "after a w0-length WRITE the chip defers BOTH the `E` and the redirect by one further clock — a post-write bus turnaround" | **FALSIFIED.**  **475** flush events carry the stated signature (last completed cycle a zero-wait MEMW with `T4 = x-1`, bus idle at the flush).  **398** of them show the `E` on the flush clock and the model is exact; **77** show it at `x+2`.  The BIU state at the flush is byte-identical across all 475 — `run=0`, no committed cycle, occupancy 0, `no_eval_ = x-1`, `e_from_ = x`, an EU request outstanding, and the next chip cycle a MEMW in every one |
| the plan's COINCIDENCE hypothesis (M12's release rule interacting with the zero-wait write's eval geometry, where the write's completion eval and the flush clock coincide) | **FALSIFIED by the same control.**  The coincidence class is exactly the 475, and it is 398 / 475 exact.  Neither half of M12 is armed at any of these events (`no_eval_` is already spent, the absorb window is thousands of clocks in the past) |
| the residual is ONE machine | **FALSIFIED.**  Splitting by the micro-row the flush is called from separates it with **no exceptions**: 80 events on ROM row `01FC` reached via `0093`, all wrong; 628 events on the SAME row `01FC` reached via `01F7`, all right; 13 events on three other flush rows |

`01FC` is the shared tail of the interrupt entry (`111.0001?000.11`, rows
`01F8-01FB` and `01FC`).  The two ways in are the two `rowgrp 2` blocks:
`01F4-01F7` (`INT`, opc `0x10`) and `0090-0093` (`INTEM`, opc `0x18`, i.e.
**BRKEM**).  They differ in exactly one thing that outlives them: `0093` is
`CTL MFC` — it SETS the 8080 emulation-mode flag.  (`0092`'s `JMP CNTZ 12`
skips `0093` when `COUNT` is zero, which is how `CALLN` (`0401
ZEROS -> COUNT / FARJMP INTEM`) runs the same chain and stays native, while
BRKEM (`0349 CONST -> COUNT 1`) does not.  No `CALLN` occurs in the bank.)

**And the chip says so on the pins.**  `tacensus.py --chains`, model-free:

```
trap push chains (chip rows only): 1566
  (MD at push 1/2/3, store-2 wait count) -> store-2 -> store-3 T1 gap
    MD=(0,0,0) tw=0  6:696     tw=1  6:395    tw=2  7:186   tw=3  8:126
               tw=4  9:15      tw=5 10:16     ...  tw=15 20:4      (1488 chains)
    MD=(0,1,1) tw=0  7:73      tw=1  9:3      tw=3 11:2            (78 chains)
```

**1,488 chains at the native law and 78 at another one, split perfectly by
PS3, with zero exceptions on either side** — and PS3 comes up exactly where M9
measured it, between the PSW push and the CS push, i.e. on `0093`.

### 18.2 M13 — IN 8080 EMULATION MODE THE STORE HOLDS OPR UNTIL IT HAS RETIRED

**What is measured and what is inferred, separated first.**  The pins measure a
BUS GAP — the store-2-to-store-3 T1 distance — and the status bit it splits on.
They do NOT observe OPR, the `F` row, or any release instant; nothing in this
campaign can.  So "the store holds OPR until it has retired" is the MINIMAL
MODEL that reproduces the measured gaps using quantities the model already has,
not a directly witnessed internal event.  What is measured is the gap and the
split; what is landed is the smallest re-keying of an existing deadline that
reproduces them.

The gap that splits is the one spanned by `01FA` (`PC -> OPR ... F`, the F/OPR
interlock) and `01FB` (the third store).  Writing `T1`, `e` and `T4` for the
SECOND store's own instants:

* **native** (§11.4): the store hands its word to the AD output latch at T2 and
  OPR is free from T3 — a FIXED cycle-relative index 2 that does NOT stretch.
  `01FA` releases at `T1+2`, `01FB` runs at `T1+3`.
* **emulation mode**: the release is the store's own **eu_done — the completion
  eval + 2**, the deadline `wait_bus()` already carries.  `01FA` releases at
  `e+2`, `01FB` runs at `e+3`, and it STRETCHES with the eval like every other
  eval-keyed quantity.

That reproduces all three measured minority gaps and the native ones with the
same arithmetic and nothing added:

| store-2 waits | eval `e` | native `01FB` | native gap | MD `01FB` | MD gap | measured MD |
|---|---|---|---|---|---|---|
| 0 | `T1+2` | `T1+3` | 6 | `T1+5` | **7** | 7 (73) |
| 1 | `T1+4` | `T1+3` | 6 | `T1+7` | **9** | 9 (3) |
| 3 | `T1+6` | `T1+3` | 8 | `T1+9` | **11** | 11 (2) |

*The implementation is one line* — `wait_opr_free()` calls `wait_bus()` when MD
is set.  No new state (the BIU has held a live view of MD since M9's `bind_md`),
no new deadline, no table, no per-form case.

**The rivals that were TRIED are falsified, and the WAIT AXIS is what falsifies
them.  UNIQUENESS IS NOT ESTABLISHED:** five minority chains above `w0` (three
at `tw=1`, two at `tw=3`) kill any hypothesis with a wrong closed form, but they
cannot exclude every other wait- or path-conditioned law that also yields
7 / 9 / 11.  What the table below claims is refutation of the named rivals, not
that M13 is the only law consistent with the data.

| rival | prediction | measured |
|---|---|---|
| the BRKEM path simply runs `k` EXTRA MICRO-ROWS | a CONSTANT extra gap at every wait level | +1 at `tw=0`, +3 at `tw=1`, +3 at `tw=3` — no constant fits |
| the extra cost is `2 * (1 + tw)` (fits `tw=0` and `tw=1`) | gap 13 at `tw=3` | **11** |
| a BUS-side rule: the flush's commit is deferred one clock after a write | the third store's T1 late by 1 at every wait level | late by 1 at `tw=0` but by **3** at `tw=1` |
| the release rides the eval in NATIVE mode too (i.e. §11.4 is simply wrong) | native gap 7 / 9 / 11 | native gap **6 / 6 / 8**, 1,488 chains |

**Scope, stated because it is thin.**  Every chain in which MD is set at the
`F` row is a BRKEM entry chain (MD goes up between push 1 and push 2 in all 78;
there is no chain in the bank with MD already set at push 1, and no `CALLN`).
So the assets do NOT separate "MD is set at the `-> OPR F` row" from "this is
the BRKEM push chain".  The MD form is kept for the same reason M11's general
form was: it is the falsifiable one, and it is the only one expressible without
naming an opcode.

### 18.3 What is left in the neighbourhood, named — and one thing MEASURED and NOT LANDED

**(a) The two-clock `E`.**  With M13 landed the 80 BRKEM events have the `E` on
the right clock, and every one of them still diverges — one clock later, on the
NEXT clock.  The census is as sharp as M13's: **80 of 80 BRKEM flush events
show `QS=E` on TWO CONSECUTIVE clocks; 0 of the other 16,068 flush events in
the bank do.**  Two `E` codes are two queue-clear events one clock apart, and
no mechanism for the second one is established: the mode change happens at
`0093`, ten clocks earlier, on a clock where the QS port is provably free.
A probe that simply re-arms the `E` for one more clock when a flush is raised
with MD set moves the same 122 seeds' first divergence LATER again with **0
newly broken and still 0 newly exact** — the next block is a different family
(`bs CODE!=PASV`, the emulation-mode PREFETCH, 58 of the 122).  It is NOT
landed: as written it is a restatement of the observation with a new state
field, which is the fitted special case the standing principle forbids.
Falsifier: any BRKEM flush whose `E` is one clock wide, or any non-BRKEM flush
whose `E` is two.

**(b) The emulation-mode prefetch.**  The obvious candidate for (a)'s successor
family — the V20's 8080-mode queue being shorter, i.e. M7's threshold dropping
from `occupancy() <= 4` — was probed at `<= 2` and is **FALSIFIED**: 12 seeds
diverge EARLIER and none later.  Not chased further.

**(c) Machine B — 13 events, a WAITED family, not this one.**  The other 13
misses sit on three flush rows: `00F3` (`OPR -> PC F E CTL FLUSH`, the near
return, 7 of 523), `0237` (`tmpc -> PC E CTL FLUSH`, the far return, 5 of 387)
and `01BD` (1 of 195).  They are NOT path-separated — the same rows are exact
in 516 / 523, 382 / 387 and 194 / 195 events respectively — and they do not
share the BRKEM signature.  What they do share: in **12 of 13** an EU **MEMR is
RUNNING at or straddling the flush clock**, the chip's redirect fetch opens 2-3
clocks LATER than the model's, and the chip's `E` sits on that redirect's own
display clock while the model's sits on the flush clock; 11 of the 13 are
waited captures (`w1`, `w2` or `wrand`).  The one event that does NOT fit that
shape (`mc1/1721`, row `01BD`, `w0`, chip redirect four clocks EARLIER than the
model's) is a singleton and is left as one.  The rest is a wait-axis
redirect-commit question in the M12 family, and it is the next stage's survey,
not a claim of this one.

**(d) The three tails.**  `0F12`, `C1.6`, `F7.4` are still one case each
(499/500; 9 / 4 / 4 row diffs).  They did NOT close for free, and per the plan
they were not chased.  M13 is exactly neutral on them — none is an
emulation-mode form.

### 18.4 Gates (measured, this machine, immediately before the commit)

```
make -C sim test                                                          # disasm gate: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
                                                              # functional total 7,341,126
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 166,397 (unchanged)
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms EB  --waits 1  # 200/200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py                                          # full/active/halt 154/154 x3
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800,
                                          # whole-program 173,556/173,556 all on the same T1
python3 sw/timed_wvec_gate.py             # count 88/88, digest 88/88, cycles +0.0 %
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 1,272/1,702 exact, 0 hard failures
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 154/188
python3 sw/tacensus.py                    # residual E events 93 -> 13 of 16,148
python3 sw/tacensus.py --chains           # the pins-only census above
```

`sw/check_enter_nesting.py` is the VERILATOR/RTL leg (CLAUDE.md) and is NOT in
this set: M13 touches `sim/` only, and the working tree carries unrelated
uncommitted `hdl/` changes from another branch, so running it here would score
something other than this change.

**Monotonicity, checked per FORM and per SEED.**  Over the 347 forms of the
v0.1 w0 suite **zero moved**; w1/w3 and `EB` w1 are byte-identical.  Over the
1,702 scored fuzz seeds: **0 newly exact, 0 newly broken**, and of the 122
seeds whose first-divergence row moved, **122 moved LATER and 0 earlier**
(p10 of the first-divergence row 500 → 503; the median and the prefix
fractions are unchanged).

### 18.4a Provenance class, per finding

| finding | class | evidence | falsifier |
|---|---|---|---|
| §17.4's POST-WRITE TURNAROUND reading | **RETRACTED** | its own control: 475 events carry the stated signature, 398 exact | — (retracted) |
| the BUS GAP and the split that carries M13 | **MEASURED** | pins only, no model: 1,566 trap push chains in the bank split perfectly on PS3 (M9's emulation-mode bit) — 1,488 native chains at store-2-to-store-3 gap 6/6/7/8/…/20 by wait level, 78 emulation chains at 7 (`tw=0`), 9 (`tw=1`), 11 (`tw=3`); three wait levels, zero exceptions on either side | any chain that breaks the split, at any wait level |
| **M13** the reading of that gap: in 8080 emulation mode the F/OPR interlock's write half releases at the store's RETIRE (completion eval + 2), not at the fixed index 2 | **MODEL, minimal and consistent — NOT a witnessed internal event** | it reproduces all six gaps from quantities the model already has (`wait_bus()`'s deadline, `bind_md`'s MD view), adds no state, and closes the 80 residual `E` events; the named rivals are refuted by the wait axis, but UNIQUENESS IS NOT ESTABLISHED (five minority chains above `w0`) | any emulation-mode `-> OPR F` row between two stores that releases at the store's index 2, or any native-mode one that releases at its retire; or any competing law that fits 6/6/8 native and 7/9/11 emulation with less state |
| the discriminator is MD and not "the BRKEM chain" | **MEASURED IN KIND, NOT SEPARATED BY THE ASSETS** | every chain with MD set at the `F` row is a BRKEM entry; no `CALLN` (the entry that runs the same rows with MD clear) occurs in the bank | a `CALLN` capture, or any emulation-mode push chain that is not a BRKEM entry |
| **the two-clock `E`** after a BRKEM flush | **OBSERVATION, NOT LANDED** | 80 of 80 BRKEM flush events, 0 of 16,068 others; a probe moves 122 seeds later with 0 newly broken and 0 newly exact | see §18.3(a) |
| the emulation-mode prefetch threshold is 2 | **FALSIFIED** | 12 seeds diverge EARLIER, none later | — |
| machine B (13 events on `00F3` / `0237` / `01BD`) | **NAMED, NOT CHASED** | not path-separated (516/523, 382/387, 194/195 of the same rows are exact); 12 of 13 have an EU MEMR running at the flush, the chip's redirect 2-3 clocks later than the model's and the chip's `E` on that redirect's display clock; 11 of 13 waited | see §18.3(c) |

### 18.5 Ledger delta

| | after §17 | after this addendum |
|---|---|---|
| residual flush `E` events the model misses | 93 / 16,148 | **13 / 16,148** |
| ...of which the §17.4 "turnaround" family | 77 (read as a bus fact) | **0 — the reading is retracted; the family was BRKEM** |
| v0.1 cycle rows at w0 | 166,397 / 166,400 | 166,397 / 166,400 (0 / 347 forms moved) |
| v0.1-w1 / -w3, `EB` w1 | 1,200 / 1,200, 200/200 | unchanged |
| wvec per-cycle digest vs silicon | 88 / 88 | 88 / 88 |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | unchanged |
| `timed_fuzz`, banked | 1,272 / 1,702 | **1,272 / 1,702 (unchanged)** |
| `timed_fuzz`, first-divergence row p10 | 500 | **503** (122 seeds later, 0 earlier) |
| `timed_fuzz`, the VICTORY TRANCHE | 154 / 188 | 154 / 188 (unchanged) |
| functional corpus | 7,341,126 / 7,341,126 | unchanged |
| open w0 physics questions | 3 tails | 3 tails |
| mechanisms | M1-M12, M2r, M5b | **+ M13** |

**V5 stays a registered FAILURE**, and this addendum does not improve it: the
tranche re-score is 154 / 188, the same number §17 recorded.  What the session
bought is a retraction, a mechanism, and a residual that is now 13 events
instead of 93 — with the next two blockers (§18.3(a) and (c)) measured and
named rather than guessed at.

---

## 19. POST-CLOSURE ADDENDUM #4 — S9a, THE TIMED PIN-EVENT PATH (2026-08-02)

**This section is an ADDENDUM.  Nothing in §0-§18 is edited or retracted by it.**
It closes the last standing piece of scaffolding **S9** for the OFFLINE w0
oracles: `timed-run` now executes the thirteen arch-excluded pin-event forms
cycle-exactly, and the reachable w0 denominator moves from **166,400 to the
full 169,000**.

### 19.0 What was excluded, and what the exclusion now is

§10.6 booked the w0 denominator as `169,000 - 2,600`, the 2,600 being the
thirteen pin-event forms whose ROWS the timed model could not produce
(`INT.90 INT.B8 INT.9D INT.8ED0 INT.8ED8 INT.F3AA INT.FB NMI.90 NMI.B8
HLT.INT HLT.NMI HLT.RES POLL.REL`; `IE0.90` and `POLL.LO` were always in the
scored set because neither fires).  All 2,600 are now **cycle-exact**, so:

```
169,000 total
      0 excluded                <- S9's single-instruction half is REMOVED
  ------
169,000 reachable at w0      168,997 exact      3 short
```

The 3 short are the SAME three tails §10.6 named (`0F12`, `C1.6`, `F7.4`, one
case each) — no new residual, and no pin-event case among them.  **The
ratchet is stated on the new denominator: 168,997 / 169,000 (99.998 %),
against the previous 166,397 / 166,400.**  In absolute terms 2,600 cases moved
from "not attempted" to "exact" and none moved the other way.

What S9 still covers is the **multi-instruction** half: `timed-boot` has no
event replay, so the fuzz bank's 1,165 `EVT` seeds remain the registered
exclusion (untouched this session; see §19.7 for the preview).  Interrupt/INTA
timing **UNDER WAITS** also stays scoped out and is scoped out again here
explicitly: the pin-event goldens are w0 only, so w0 INTA is fully oracled and
nothing above w0 is.  No wait-axis behaviour was guessed at.

### 19.1 The firing policy — REPLAY, and where the rig's own schedule is used

The functional policy (ledger §38, now `sim/pin_replay.h`, shared verbatim by
`case_runner.cpp` and `timed_runner.cpp`) is unchanged: the golden's own
pushed frame at `SS:SP` names the instruction the interrupt preempted, and a
mid-string `REP` abort is identified by its completed-element count read off
the golden's bus trace.  Nothing about WHICH boundary fires is predicted.

The timed path needs one coordinate the functional path does not — the clock
the rig's pin goes active — and it is read verbatim out of the golden's `evt`
/ `pins` fields, in the same class as `iord` and the INTA constant.  The
translation is `hdl/tb/tb_v30_core.sv`'s scheduler, mirrored exactly and with
no fitted offset, because the BIU tracks the scheduler's OWN anchors on its
own row stream:

| trigger | anchor | assert clock `A` |
|---|---|---|
| `fetch` | the `CODE` T1 whose 20-bit address is `evt.addr` | anchor + 2 + `delay` |
| `fpop` | the window-opening `F` pop | anchor + `delay` |

held for `evt.hold` clocks (0 = to the end of the case); `pins` bit 2 is the
static POLL_N level.  (`BiuTimed::set_evt` / `assert_clk`.)

### 19.2 M14 — THE INTERRUPT ENTRY SEQUENCE RUNS AT THE DECISION CLOCK + 2, AND THE DECISION CLOCK IS A MAX OF TWO THINGS

**MEASURED.**  One rule replaces every separate number
`docs/facts/interrupt_model.md` records for the running case:

```
D = max(B, A + 3)      INT   (the pin LEVEL through three flops)
D = max(B, A + 4)      NMI   (the EDGE latches at +3, read the clock after)
entry = D + 2
```

`B` is the replayed boundary's **retire** clock — `wait_bus()`'s deadline, the
`E` row's own clock — and NOT the would-pop clock (§19.3).  Everything else
falls out of the ROM's own rows and the ordinary bus grid:

* **INT**: the entry row `01E0` IS the acknowledge, so the INTA request is
  ready at `D+2` — the measured *"the INTA request is READY during B+2"*, and
  the measured 7/8/10 assert-to-INTA1 spread is then just the arbitration.
* **NMI**: `01DA`, `01DB` (FARJMP, 2 clocks), `01EC`, `01ED`, and `01EE`
  issues the IVT read — `D+2+5 = D+7`, the measured *"ready during B+7, IVT
  T1 = B+9 on a quiet bus"*.  The five clocks are ROM rows, not a constant.
* **INTA1 -> INTA2** needs no rule at all: `01E1`'s `F` releases at the
  acknowledge's `eu_done` and `01E2` posts one clock later, which puts INTA2's
  T1 exactly 7 clocks after INTA1's on a quiet bus.  Measured 200/200 per form.

**Both terms of the max are load-bearing, and the census says so.**  Over the
800 running `INT.90 / INT.B8 / NMI.90 / NMI.B8` goldens, scored cell by cell
in `(A, B)` against the window the golden's own eval grid leaves for the
acknowledge request (16 + 23 + 12 + 20 distinct cells):

| model | exact |
|---|---|
| `entry = B + 2` alone | 768 / 800 (32 late-assert cases 1-2 clocks early) |
| `entry = max(B+2, A+p)`, p = 5 / 6 | **800 / 800** |

and `p` is pinned from both sides: `p = 4` breaks the `A=1, B=3` cell, `p = 6`
(for INT) breaks `A=0, B=3`.  Falsifier: any case whose acknowledge is
inconsistent with the max.

### 19.3 The recognition boundary is the RETIRE, not the POP — and the pop is SUPPRESSED

`opcode_prefetch` takes the successor's opcode at `max(retire, byte poppable)`
(M8).  The recognition decision sits at the FIRST of those two only: it is the
decision NOT to take a byte, so it does not slide when the queue is dry.

The queue geometry separates the two readings for free: the anchor
instruction's fetch delivers TWO bytes at an even address and ONE at an odd
one, so half the goldens have the successor byte standing at the retire and
half do not.  With the POP deadline `INT.90` scores 177/200 and `NMI.90`
186/200 and **every one of the 37 failures is an odd-address, dry-queue case**;
with the RETIRE deadline both are 200/200.

And the pop itself does not happen: the byte stays in the queue and the QS
port stays idle.  `INT.90` case 0 row 3 against `IE0.90` case 0 row 3 is the
same geometry with and without the recognition — `F` in one, nothing in the
other.  (`BiuTimed::boundary_no_pop`, `CpuT::set_fire_pc`.)  The sequence
still runs its post-`E` row, which costs no clocks but carries datapath work:
`9D`'s `SIGMA -> SP` lives there, and dropping it put every `INT.9D` push two
bytes low.

### 19.4 M15 — THE INTA CYCLE DRIVES NO ADDRESS

**MEASURED** (`interrupt_model.md` "INTA cycle drive", and all 1,400 vectored
golden acknowledge cycles): AD15-0 FLOAT through the commit display and T1 —
they keep whatever the last data phase left standing — and AD19-16 are driven
to 0 over both.  From T2 on it is an ordinary read display: the acknowledge
byte on the lanes, PS = IE:seg as usual, UBE low.  Modelled as one flag
(`Access::no_addr`) that freezes the floating AD into the access on its
display clock, so the display row and T1 both reach the pins through the
ordinary address path.

### 19.5 M16 — HLT IS DECODED, NOT MICROCODED, AND THE DECODE IS WHERE IT ACTS

`HLT` is a pre-decode-executed (ONE_BYTE_LOGIC) form, and the measured HALT
display law is a statement about its DECODE clock, not its retire:

* the HALT status takes the register on the first clock the register is free
  **from the decode cycle on** (the pop clock + 1);
* **prefetch is blocked from the decode cycle** — so the eval at the end of
  the OPCODE POP clock still grants a fetch and the one at the end of the
  decode clock does not;
* and it does **NOT** take a committed fetch back.  "Blocked from the decode
  cycle" is about the DECISION, not a retroactive withdrawal.

The three are separated by the corpus itself: `HLT.RES` case 0 (a fetch
running over the pop) shows that fetch completing and NOTHING following it;
case 1 (the pop on an idle bus) shows `CODE` display / T1 / T2 / T3 / T4 and
only then the HALT.  Arming at the retire puts the display one clock late on
the first and withdrawing the fetch loses the second — 300 of the 600 HALT
cases each way.  The pre-window fetch-address replay (`queue_preload`) now
also primes `last_fetch_addr_`, because a part that halts before making a
fetch of its own still drives the last PRE-window fetch's address.

**And the HALT pseudo-cycle is not an EU access.**  It never went through
`post()`, so it must not complete one either: before this session's guard it
decremented `eu_pending_` and pushed a phantom read-completion clock into
`rd_done_q_`, which the first `F` row after the wake then consumed instead of
waiting for its own acknowledge (`HLT.INT`'s second INTA landed 3 clocks
early).  A latent corruption that only a wake could expose.

### 19.6 The HALT wake — one clock, then the same machinery

**MEASURED** (`interrupt_model.md` "HALT wake", reproduced 600/600):

| | |
|---|---|
| `HLT.RES` (masked INT) | the prefetcher restarts at the decision clock `A+3`; the resumed opcode pops at `A+4` |
| `HLT.INT` | entry at `A+6`; the prefetcher restarts at `A+3` and a cold queue lets one fetch commit before the acknowledge |
| `HLT.NMI` | entry at `A+7`, IVT read posted at `A+12`, its T1 at `A+14` — and **the bus is HELD**: the prefetcher does not restart before the entry |

Read against §19.2 this is ONE statement: **the HALT wake costs one clock.**
The decision sits at the earliest clock the pin pipeline allows (`A+3` for the
INT level, `A+4` for the NMI latch) and the machine's would-pop clock is one
later — `B = A+4` / `A+5` — after which `entry = B+2` is the running rule
unchanged, and the masked resume's pop is that same `B`.  The bus-held
asymmetry on NMI is measured, not derived.

### 19.7 POLL — the ROM's last substantive rows, and the SAME 3-deep pin pipeline

The 9B `BUSY` loop is three ROM rows and nothing else:

```
006C  JMP BUSY 3     taken   = 2 clocks
006F  JMP INTR 5     not taken = 1
0070  JMP 0          taken   = 2
                     ---------------
                     5 clocks per sample
```

That IS the measured *"sampling the pin every 5 clocks"* — no timer, no
counter.  `kCondBusy` stops being hard-FALSE and becomes the rig's replayed
POLL_N level; on the functional bus there is no clock and no pin, so it is a
constant false and 9B still retires in one pass (ledger R2 unchanged).

**And the level is read through the SAME three flops the INT level is.**  The
row running on clock `c` decides on POLL_N at `c-3`.  MEASURED and a clean
fit: over the 200 `POLL.REL` goldens the missed-sample count `k` — the
golden's own `gap = 3 + 5k` to the next `F` pop — is reproduced by
`k = min{ j : 2 + 5j - d >= A }` at

| d | 0 | 1 | 2 | **3** | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| cases matched | 65 | 124 | 164 | **200** | 171 | 135 | 76 |

zero exceptions at d = 3 over `A` = 1..27 and `k` = 1..6.  Falsifier: any POLL
release whose `k` needs a different depth.  Rows `0070`/`0071` and the `BUSY`
branch are now EXECUTED — the ROM's last substantive unexecuted surface.

### 19.8 REP interruption — the withdrawal is the same boundary, and one clock is MEASURED but UNEXPLAINED

The mid-string withdrawal machinery is the ROM's own (`REPX` 0223 -> 0225-0227:
the PFXCNT rewind and the FLUSH) and the timed path reproduces it unchanged.
Two things had to be said:

1. **The rewound PC IS `resume_ip`, so the recognised-boundary rule applies
   without modification** — including the suppressed pop, which is why the
   golden shows no `F` between the withdrawal flush and the acknowledge.  With
   the boundary armed, all 35 one-element aborts are exact and the flush lands
   at the loop row + 10 = the measured `pop+16 = edge+9`.

2. **A CHAINED abort (>= 2 elements) takes its decision one clock later.**
   `interrupt_model.md` already records the two anchors separately — the first
   boundary POP-anchored at `pop+7`, a chained one WRITE-ACCEPT-anchored — and
   the row cadence lands on the first by itself.  MEASURED, uniform, no
   exceptions: over the 56 `INT.F3AA` withdrawals the model matches all 35
   one-element aborts and is EXACTLY +1 early in all 21 chained ones (14 at
   two elements, 7 at three) — a single clock, not a per-iteration drift.

   **PROVENANCE: MEASURED offset, MECHANISM OPEN.**  Two anchors were tried
   and refuted against the goldens: the completing store's display clock
   (+2 on the chained cases) and the previous store's display (no change).
   Falsifier: any chained abort whose flush is not at the loop row + 10, or
   any one-element abort that needs the +1.

### 19.9 The checker — the pin-event flags policy, imported not forked

`sw/timed_gate.py` compared the golden's recorded `final.flags` literally,
which for a vectored form is the POST-HANDLER store-stub PUSH PSW — an
unreliable capture on both sides.  `check_core.check_case` has had the right
rule since block 4 (`_pushed_psw_flags`: the architectural finals are the
interrupt-pushed PSW with IE/BRK cleared, derived from each side's own memory
image).  It is now IMPORTED into the timed gate, per the file's own standing
rule that `check_core` is never forked.  Without it `INT.9D` scored 148/200
ARCH while both sides agreed on the frame they pushed — the POP-PSW boundary
race, read as a model failure.

### 19.10 Recognition-law consistency — a free measurement

The firing boundary is REPLAYED, so the recognition laws are not used to
decide WHETHER a case fires.  They are, however, checkable against the timed
row stream, and §19.2's census IS that check: over the 800 running INT/NMI
goldens the decision clock implied by the golden's own acknowledge position is
`max(B, A + 3)` for INT and `max(B, A + 4)` for NMI in **800 / 800** cases,
with `A` computed from the rig's schedule and `B` from the model's own retire.
The measured recognition laws (would-pop-3, edge+3 latched) are therefore
consistent with the timed model's clocks on every running case in the corpus,
and the 600 HALT cases add the same statement at the pin's own earliest clock.

### 19.11 Gates (measured, this machine, immediately before the commit)

```
make -C sim test                                                          # disasm gate: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
                                                              # functional total 7,341,126
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 168,997 / 169,000
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms EB  --waits 1  # 200/200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py          # pushes/walk/full/active/halt_display 154/154 x5
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800,
                                          # whole-program 173,556/173,556 all on the same T1
python3 sw/timed_wvec_gate.py             # count 88/88, digest 88/88, cycles +0.0 %
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 1,272/1,702 exact, EVT 1,165 excluded (unchanged)
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 154/188
```

`sw/check_enter_nesting.py` is the VERILATOR/RTL leg (CLAUDE.md) and is NOT in
this set: S9a touches `sim/` and `sw/timed_gate.py` only, and the working tree
carries unrelated uncommitted `hdl/` changes from another branch.

**Monotonicity.** Over the 347 forms of the v0.1 w0 suite the 13 pin-event
forms went 0 -> 200 each and **no other form moved**; the three tails
(`0F12`, `C1.6`, `F7.4`) are the same three cases with the same diffs.  w1/w3
and `EB` w1 are byte-identical.  `timed_fuzz` is byte-identical on all 1,702
scored seeds (0 newly exact, 0 newly broken, no first-divergence row moved),
which is expected: every shared-code change is inert without an armed
`fire_pc` / `rep_abort` / pin schedule, and the two that are not
(`halt_decode`, the HALT pseudo-cycle guard) are exercised by the ENTER
tranche's own `HLT`, which stays 154/154.

### 19.12 EVT pilot preview (S9b), 20 stratified seeds — NOT a gate

The registered `EVT` exclusion was NOT touched.  As a preview, 20 of the
bank's 1,165 `EVT` seeds were scored through the UNCHANGED `timed-boot` path
(which still has no event replay):

* **4 of 20 are already cycle-exact over the whole capture** — their event has
  no bus consequence inside the window;
* of the 12 whose capture contains an `INTA` row, **9 part within 4 rows of
  that acknowledge** (gaps 0, 0, 3, 3, 3, 4, 4, 4, 7) and the first-divergence
  column is the bus STATUS in every one;
* the remaining 3 (gaps 125, 259, 989) part earlier, in the ordinary `qs`
  family the non-EVT population already has.

Reading: the population is blocked on the DRIVER, not on bus physics — what
`timed-boot` needs is the event replay `image_runner.cpp` already has in the
bus-ordinal coordinate, plus §19.2's decision clock expressed in it.  Nothing
in the preview suggests a missing law.

### 19.13 Ledger delta

| | after §18 | after this addendum |
|---|---|---|
| v0.1 w0 REACHABLE denominator | 166,400 (S9: −2,600) | **169,000 (S9 single-instruction half REMOVED)** |
| v0.1 cycle rows at w0 | 166,397 / 166,400 | **168,997 / 169,000** |
| ...pin-event forms | 0 / 2,600 (excluded) | **2,600 / 2,600** |
| arch through the TIMED path | 166,800 / 169,000 | **169,000 / 169,000** |
| v0.1-w1 / -w3, `EB` w1 | 1,200 / 1,200, 200/200 | unchanged |
| boot / scenario / ENTER / INS / wvec / law cards | as §18.4 | unchanged |
| `timed_fuzz`, banked / tranche | 1,272 / 1,702, 154 / 188 | unchanged (EVT still excluded) |
| functional corpus | 7,341,126 / 7,341,126 | unchanged |
| open w0 physics questions | 3 tails | 3 tails (same three cases) |
| mechanisms | M1-M13, M2r, M5b | **+ M14 (decision clock), M15 (INTA drives no address), M16 (the HLT decode)** |
| scaffolding | S9 (pin events) | S9 **half removed**: single-instruction closed, `timed-boot` EVT replay open (S9b) |

### 19.14 S9b handoff

1. **`timed-boot` event replay.**  The one thing the 1,165-seed `EVT`
   population needs.  `image_runner.cpp` already carries the coordinate (the
   ordered bus position plus the recorded resume `CS:IP`); the timed driver
   needs the same two coordinates plus §19.2's `entry = max(B, A+3/4) + 2`,
   and `A` in that path comes from the capture's own pin schedule rather than
   from a golden `evt` record.  Re-freeze the fuzz bar before scoring.
2. **The chained-REP-abort clock (§19.8.2)** is MEASURED but its mechanism is
   open.  The stimulus that would close it is a waited capture of a chained
   withdrawal — which is also the first thing that would test whether it is
   eval-keyed or index-keyed.
3. **INTA under waits stays scoped out.**  The pin-event goldens are w0 only.
   A w1/w3 pin-event tranche is the capture that would open it; until then no
   gate may pretend a law exists.
4. The three w0 tails (`0F12`, `C1.6`, `F7.4`) are untouched and unrelated.

## 20. POST-CLOSURE ADDENDUM #5 — S9b, THE EVT POPULATION UNLOCK (2026-08-02)

**This section is an ADDENDUM.  Nothing in §0-§19 is edited or retracted by it.**
S9a closed the SINGLE-INSTRUCTION half of scaffolding S9; this section closes
the MULTI-INSTRUCTION half — `timed-boot` now replays pin events — and scores
the population that half was blocking.

### 20.0 PRE-REGISTRATION — written and committed BEFORE the full run

The S4r lesson, applied again: population, comparison policy and the numeric
bar are frozen HERE, from a 50-seed stratified pilot, so that no post-hoc
reading of the full run can be dressed up as the gate.

**Harness.**  `sw/timed_fuzz.py --evt-replay`, and everything that decides a
verdict is INHERITED, not re-invented: the regeneration path and its sha256
gate (`ucsim_fuzz.regen`), the comparison WINDOW (`ucsim_fuzz.window_of`), and
the COLUMN POLICY (`fuzz_classify.diff_rows`) — byte for byte §13.0's, with no
change of any kind.  The wait vectors come from each seed's own `waits` record
exactly as before.

**The two REPLAYED coordinates.**  The pin-event directive `timed-boot` now
takes is two inputs and no predictions:

| | |
|---|---|
| the RIG's schedule | the seed's own `evt` axis (`pin` / `delay` / `hold`) plus the fetch anchor `meta["anchor_linear"]` — the *identical* tuple `fuzz_campaign._evt_tuple` handed the board.  Assert clock `A` = (the `CODE` T1 at that address) + 2 + `delay`, `nec_bus.sv`'s own scheduler mirrored. |
| the CAPTURE's boundaries | for each firing, the ordered bus position of the acknowledge and the CS:IP the chip's own pushed frame recorded — `ucsim_fuzz.entry_points` / `frame_of`, the SAME functions the functional replay uses, imported not forked. |

`pins` is the rig's static PINS register, which `check_seq.run_chip` never
writes: it holds its reset value 0 (`hps_axi_slave.sv`), so POLL_N sits
statically LOW and 9B is never busy — the model's standing behaviour.

**Population, frozen.**

```
1,165  EVT seeds in the four banks (mc1 502, mc2 503, t30-raw 160, t30-brkem 0)
  157  ...OPEN_BUS                 <- STAYS EXCLUDED (a property of the CAPTURE)
------
1,008  the S9b UNLOCKED population
```

`OPEN_BUS` is tested FIRST for an EVT seed, so the unlocked table and the
registered table cannot overlap.  **The registered denominators are UNTOUCHED**:
`sw/timed_fuzz.py` with no flags still excludes every EVT seed and still scores
1,702 / 1,165 EVT / 375 OPEN_BUS, and the tranche still scores 188.

**The tranche contributes ZERO EVT seeds, by construction.**  §14.0 set
`no_evt` at GENERATION for all 216 tranche cells; re-checked here, 216 / 216
carry no `evt` axis.  There is no "tranche EVT population" to unlock, and the
tranche's 188-seed denominator is unchanged.

**Pilot** (`--pop evt --pilot 50 --evt-replay`, deterministic, stratified over
(bank, pin, wait class); 33 scored, 17 OPEN_BUS):

| metric | pilot value |
|---|---|
| M1 cycle-exact seeds (whole window divergence-free) | **19 / 33 (57.6 %)** |
| M2 median divergence-free prefix, rows from RESET | **1,188** |
| M3 median prefix FRACTION (`first_bad / n`) | **1.000** |
| M4 seeds with prefix fraction >= 0.5 / >= 0.9 | **20 / 33**, **19 / 33** |
| first-divergence family census | `bs` 10, `qs` 3, `data` 1 |
| by pin | INT 6/14, NMI 8/14, POLL 5/5 |
| divergences within 4 rows of an ACKNOWLEDGE | **0 / 14** |

The pilot's selection is reproducible and is pinned by its own sha256 over the
sorted seed paths: **`92689dac4b5e8e86`** (re-derived after the session's fixes,
unchanged; the pilot's own re-score on the final model is 26 / 33).

**The bar, stated before the run, and what can fail:**

1. **Zero hard failures** over the full 1,008 (`GEN_DRIFT` / `REGEN_ERROR` /
   `SIM_ERROR` = 0), and zero `REP-WITHDRAW-UNMATCHED` reports — a replayed
   boundary that does not land where the chip's did is a DRIVER failure and is
   reported as one, never swallowed.
2. **A closed taxonomy**: every diverging seed's first divergence falls in a
   named family; an "unknown" bucket is a failure of the survey.
3. **A numeric floor**: **>= 45 %** of the 1,008 cycle-exact on the first full
   run.  Rationale: the pilot's point estimate is 57.6 % on n = 33, whose
   one-sided 95 % lower bound is 43.5 %; 45 % is that bound rounded to the
   nearest achievable-and-still-falsifiable figure.  A full run below it says
   the pilot's strata are not the population and the driver is reported as NOT
   closing this half of S9.
4. **A ratchet**: M1-M4 on the first full run become the baseline of record and
   may only GROW.  The 1,008 / 157 split is frozen with them, so the ratchet
   cannot be met by shrinking the denominator.
5. **Zero newly broken on the REGISTERED 1,702** — a hard gate.  The
   registered run must stay at or above 1,272 exact with no seed losing
   divergence-free prefix.
6. **A falsifiable prediction from the pilot**: the ACKNOWLEDGE is no longer a
   divergence site (0 / 14 in the pilot, against the S9a preview's 9 / 12
   within four rows), and the residual is dominated by `bs` divergences sitting
   6-11 rows BEFORE the chip's HALT status display.  A first-divergence family
   AT the acknowledge, or any family the pilot did not see at scale, is a
   FINDING and is reported as one.

### 20.1 The driver — two replayed coordinates, and nothing else new

`timed-boot --evt=<file>` (`sim/timed_runner.cpp`).  The rig's schedule goes
into the SAME `BiuTimed::set_evt` S9a already had, and the recorded boundaries
go into the SAME `CpuT` predicate S9a already had, with the two guards a
whole-program run needs:

```
set_fire_pc(ip)   the CS:IP the chip's frame recorded    (S9a)
set_fire_cs(cs)   ...and its segment                     (S9b, -1 = off)
set_fire_ev(at)   ...at or after the recorded bus ordinal(S9b, -1 = off)
set_evt_at(at)    the mid-string coordinate (image_runner.cpp's own call)
```

With both guards at -1 the predicate is byte for byte S9a's, which is why the
whole single-instruction corpus is unmoved (§20.7).  Every consequence then
comes out of the existing mechanisms: M14's `D = max(B, A+3|4)`, `entry = D+2`;
the suppressed pop (§19.3); the ROM's own REPX withdrawal and PFXCNT rewind;
§19.6's HALT wake, re-expressed once as

```
dec = max(A + pipe, the clock the part is halted on)
      vectored:  prefetcher restarts at dec (INT) / bus held (NMI), entry dec+3
      masked:    prefetcher restarts at dec, the resumed opcode pops at dec+1
```

which reproduces §19.6's A+3 / A+4 / A+6 / A+7 exactly when `A + pipe` is the
later term, i.e. in every single-instruction golden.

### 20.2 What the S9a pilot's "4 rows from the acknowledge" turned out to be

§19.12 read 9 of 12 EVT captures parting within 4 rows of the acknowledge and
called the population "blocked on the DRIVER, not on bus physics".  That is
what it was: with the driver in place the acknowledge stops being the
divergence site for the seeds that were parting there, and the residual moves
to two OTHER places, one of which is a genuine model error and one of which is
the campaign's own standing wait-axis exclusion:

| | 50-seed pilot (pre-fix) | full run, after §20.3-20.5 |
|---|---|---|
| within 4 rows of an acknowledge | 0 / 14 | 24 / 330 |
| within 12 rows of an acknowledge | — | 55 / 330, **44 of them WAITED** |
| within 12 rows of the HALT status | 7 / 14 | 81 / 330, 64 of them at w0 |
| neither (the ordinary `qs`/`bs` families) | 7 / 14 | 194 / 330 |

So the pilot's own falsifiable prediction (§20.0 item 6) is **half FALSIFIED
and reported as such**: the acknowledge is NOT clean at scale.  It is, however,
clean at w0 and a WAITED family above it — which is exactly "INTA under waits
is scoped out" (§19.14 item 3) showing up as data for the first time.

### 20.3 M17 — THE HLT BLOCK IS ONE MORE TERM OF M7's INDEX-2 SAMPLE, AND THE HALT DISPLAY DRIVES THE ADDRESS LATCH AS IT STANDS

**MEASURED.**  M16 (§19.5) says prefetch is blocked FROM THE HLT DECODE CYCLE,
and it was measured on the w0 pin-event goldens where the decode clock and the
completion eval are the same clock.  Under waits they are not, and the chip
grants a refill the model refused.  The block is not a rule of its own:

```
M7  (T3):   eligibility is decided at CYCLE INDEX 2 and merely APPLIED at the
            completion eval
M17 (S9b):  ...and the HALT is one of its terms:
            pf_arm = (occupancy <= 4) && !halted     -- sampled at index 2
```

w0-neutral BY CONSTRUCTION, exactly as M7 is: at w0 index 2 IS the eval, so the
sample and its consumer are the same clock (measured: the w0 ratchet is 168,997
before and after, to the case, and the 600 HALT goldens are unmoved).

**And the HALT display's ADDRESS is read at the display clock, not at the
decode.**  M16 already says the decode does not take a committed fetch back, so
the fetch granted at the decode's own eval RUNS — and it is then that fetch's
address the HALT cycle drives.  The model snapshotted `last_fetch_addr_` at
`note_halt()` time and drove the address of the fetch BEFORE it.

**The two are one statement and the census says so.**  Each alone is worth
nothing; together they are worth 210 seeds:

| model | EVT population cycle-exact |
|---|---|
| neither | **468 / 1,008** |
| index-2 HALT sample only | 468 / 1,008 |
| display-clock address only | 469 / 1,008 |
| **both** | **678 / 1,008** |

and the gain is entirely in the WAITED classes, which is where M16's w0
measurement had nothing to say:

| | fix0 | fix1 | fix2 | fix3 | wrand1 | wrand2 | wrand3 | wrand7 | wrand15 |
|---|---|---|---|---|---|---|---|---|---|
| before | 238/410 | 19/51 | 5/39 | 17/54 | 57/128 | 44/105 | 42/95 | 28/64 | 18/62 |
| after | 238/410 | **38**/51 | **33**/39 | **38**/54 | **95**/128 | **69**/105 | **74**/95 | **50**/64 | **43**/62 |

Falsifier: any capture whose HLT blocks a refill its index-2 clock permitted,
or whose HALT display carries an address other than the last fetch's.

### 20.4 A PRE-DECODE-EXECUTED FORM RETIRES AT A BOUNDARY TOO

`HLT`, `EI`, `DI`, `STC`, `CMC`, ... are ONE_BYTE_LOGIC: `loader_decode`
executes them and `step()` returns before `run_micro`, so they have **no `E`
row** and S9a's recognition check never ran for them.  In a single-instruction
case that is invisible (the case IS the ROM form).  In a whole-program replay
it means every firing boundary that follows one of these was silently skipped —
and the replay then withdrew from whatever string loop it met next, which is
precisely the `REP-WITHDRAW-UNMATCHED` report.  Measured: 9 of the 1,008 before,
5 after.  A HALT is excluded from the check by construction: a halted part's
wake is its own sequence (§19.6).

### 20.5 The DISPLAY CLOCK and the T1 are two different things

M1/M2 put the winner's status on the pins at `eval + 1` and its T1 at
`eval + 2`.  For every ordinary access those are the same statement, because
the eval sits at `last_i - 1` (w0) or at `last_i` (waited) and `eval + 2` IS
the first free clock.  The HALT pseudo-cycle is the one access where they come
apart: its eval is at index 1 (S8/S9's measured status release) while its T4 is
still at index 3.  So:

```
display = eval + 1        T1 = max(eval + 2, the bus's first FREE clock)
```

Before this the model tied the T1 to the display and put the woken fetch's T1
INSIDE the still-running HALT cycle, where it could never open at all: the
commit stranded, the M10 request slot stayed taken, and every following EU
access spun out its 4,096-clock backpressure guard — a silent 78,000-clock
garbage run, not a visible failure.  w-neutral by construction for every
non-HALT access (measured: w0 168,997, w1/w3 1,200/1,200, the whole registered
fuzz population byte-identical).

### 20.6 §19.8.2 RESOLVED — the chained REP-abort's extra clock is CADENCE-KEYED, and the rival is FALSIFIED

§19.8.2 left the +1 clock MEASURED but its anchor open, and named the closer:
"a WAITED capture of a chained withdrawal — which is also the first thing that
would test whether it is eval-keyed or index-keyed."  **The bank already had
them.**  The S9b census is every EVT seed whose replay takes a mid-string
withdrawal: 24 seeds, 12 of them chained (>= 2 elements), and 7 of the chained
ones have a divergence-free prefix that runs THROUGH the acknowledge — three of
those at w1, w2 and random-w7.

The rival is runnable (`V30SIM_REPCHAIN=eval`): a WRITE-ACCEPT / completion-
EVAL anchor moves with the completing store's wait count, because the store's
eval moves from T3 to T4+N.  The two are IDENTICAL at w0, which is why the w0
corpus never separated them.

| seed | waits | elements | cadence anchor (the model) | eval-keyed rival |
|---|---|---|---|---|
| mc1/2305 | fix1 | 2 | **EXACT** (0 diffs) | DIVERGE at row 393 |
| mc2/409 | wrand7 | 4 | **EXACT** (0 diffs) | DIVERGE at row 585 |
| mc2/2748 | fix2 | 3 | diverges at 495 (elsewhere) | first divergence moves to **315** |
| mc1/3209, mc2/2625, mc2/3561, mc2/573 | w0 | 9,3,3,7 | unchanged | unchanged |

and the whole 169,000-case w0 suite scores **168,997 under BOTH**, as predicted.

**Verdict: the extra clock does NOT move with the bus.**  It is a row-cadence /
decode-pipeline clock, not a bus-completion one; the write-accept anchor
`interrupt_model.md` records is FALSIFIED as the *timing* anchor at three
distinct wait levels.  The offset itself stays MEASURED-without-a-named-row (it
is still "one clock", not a ROM row), so the honest status is: **anchor
RESOLVED, magnitude still measured.**  Falsifier: any waited chained withdrawal
whose flush is not at the loop row + 10.

### 20.7 The registered bar, scored

The registration's clauses, in order, against the run:

| # | the registered clause | result |
|---|---|---|
| 1a | zero `GEN_DRIFT` / `REGEN_ERROR` / `SIM_ERROR` over the 1,008 | **PASS** (0 / 0 / 0) |
| 1b | zero `REP-WITHDRAW-UNMATCHED` | **FAIL — 9 on the first full run, 5 after §20.4** |
| 2 | a closed taxonomy | **PASS** (§20.8; no "unknown" bucket) |
| 3 | >= 45 % of the 1,008 cycle-exact on the FIRST full run | **PASS**, 468 / 1,008 = **46.4 %** |
| 4 | M1-M4 on the first full run are the ratchet baseline | **RECORDED** (below) |
| 5 | zero newly broken on the registered 1,702 | **PASS**, 0 moved / 0 newly broken / 0 lost prefix |
| 6 | the acknowledge is no longer a divergence site | **HALF FALSIFIED** (§20.2) |

**Clause 1b is a registered FAILURE and is reported as one, not restated.**
What the 5 are: in every one of them the timed model's OWN first divergence is
earlier than the chip's acknowledge (543 vs 579, 535 vs the NMI entry, 163 vs
197, 383 vs 411, 190 vs 250), so the model reached the recorded bus ordinal at
a different instruction and withdrew from the string loop it was in.  Four of
the five ALSO fail the FUNCTIONAL replay (`ucsim_fuzz`: mc1/1620, mc1/444,
mc1/150, mc2/2788 are STREAM divergences today), i.e. they are inherited, not
introduced.  The fifth (mc1/2389) passes functionally and is an open S9b item.
**No fix was applied to make clause 1b pass**; §20.4 removed the four it was
right to remove and the rest stand.

**The ratchet, as registered — the FIRST full run is the baseline of record:**

| metric | baseline (first full run) | after §20.3-20.5 (the new standing value) |
|---|---|---|
| M1 cycle-exact | 468 / 1,008 (46.4 %) | **678 / 1,008 (67.3 %)** |
| M2 median divergence-free prefix (rows) | 940 | **1,341** |
| M3 median prefix fraction | 0.691 | **1.000** |
| M4 fraction >= 0.5 / >= 0.9 | 540 / 469 | **774 / 679** |
| population / OPEN_BUS | 1,008 / 157 | 1,008 / 157 (frozen) |

By pin: INT 556 / 813, NMI 104 / 174, POLL 18 / 21.  897 of the 1,008 replay a
firing; 111 carry a pin event that the capture shows never fired (masked INT,
POLL, a window that closed before the entry) and are scored with the schedule
armed and no boundary.

### 20.8 The divergence taxonomy — closed, 330 seeds

Every diverging seed's first divergence is classified by the nearest marker in
the CHIP capture (an acknowledge or the HALT status, within 12 rows):

| family | seeds | kinds | w0 / waited | reading |
|---|---|---|---|---|
| **ORDINARY** | 194 | `qs` 121, `bs` 61, `data` 9, `nxta` 3 | 97 / 97 | the SAME families the registered 1,702 already has (`qs` 277, `bs` 100, `data` 27, `nxta` 26 there).  Not an event question. |
| **HALTWAKE** | 81 | `qs` 54, `bs` 27 | 64 / 17 | the wake's own geometry -- the woken fetch's display clock, and the HALT status that the chip sometimes never drives at all because the wake beat it to the register (32 seeds `bs PASV!=HALT`).  §19.6 was measured on w0 goldens whose assert clock is far from the HALT display; these are the ones where it is not. |
| **ACK** | 55 | `bs` 47, `qs` 8 | 11 / **44** | the acknowledge neighbourhood, and it is a WAIT-AXIS family -- INTA under waits, the campaign's standing exclusion (§19.14 item 3), measured here for the first time. |

There is no unknown bucket.  9 seeds also emit a `STEP-ABORT` (the pre-existing
runaway-sequence report; 28 of the registered 3,242 do too, so it is not an S9b
family): 5 are OPEN_BUS-excluded, 2 are cycle-EXACT over their window (the
runaway is past the compare window) and 2 are already in the taxonomy above.

### 20.9 ADDENDUM #5 — the dated re-scores (2026-08-02)

**Fuzz bank, the REGISTERED population (§13.0) — UNTOUCHED:**

| | after §19 | after S9b |
|---|---|---|
| scored / EVT / OPEN_BUS | 1,702 / 1,165 / 375 | **1,702 / 1,165 / 375** |
| cycle-exact | 1,272 / 1,702 (74.7 %) | **1,272 / 1,702 (74.7 %)** |
| first-divergence family | `qs` 277, `bs` 100, `data` 27, `nxta` 26 | identical |

byte-identical over all 1,702 scored seeds: 0 moved, 0 newly exact, 0 newly
broken, no first-divergence row changed.

**Fuzz bank, the S9b UNLOCKED population — NEW TABLE:**

| | |
|---|---|
| population | **1,008** (1,165 EVT − 157 OPEN_BUS) |
| cycle-exact | **678 / 1,008 (67.3 %)** |
| median prefix fraction | 1.000 |
| first-divergence family | `qs` 183, `bs` 135, `data` 9, `nxta` 3 |

**COMBINED, both populations, clearly labelled as such:**

| | |
|---|---|
| scored | **2,710** = 1,702 registered + 1,008 unlocked |
| cycle-exact | **1,950 / 2,710 (72.0 %)** |

**Victory tranche (B2) — UNTOUCHED, and it has no EVT half:** 154 / 188
(81.9 %), 216 cells, 28 OPEN_BUS, **0 EVT by construction** (§14.0 set `no_evt`
at generation; re-checked 216 / 216 this session).  **V5 therefore remains a
registered FAILURE**, unchanged by this addendum: the tranche's denominator,
numerator and exclusions are all exactly what §18 recorded.

**Law cards:** 7 GREEN / 0 RED / 4 UNRESOLVED — unchanged.
**wvec (silicon, T2b P2):** 88 / 88 count, 88 / 88 digest, bus cycles +0.0 % —
unchanged.

### 20.10 Gates (measured, this machine, immediately before the commit)

```
make -C sim test                                                          # disasm gate: PASS
python3 sw/pla3_check.py                                                  # OK (21 checks)
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
                                                              # functional total 7,341,126
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 168,997 / 169,000
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms EB  --waits 1  # 200/200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_enter_replay.py          # pushes/walk/full/active/halt_display 154/154 x5
python3 sw/timed_ins_replay.py --raw      # rails 1312/1312, vs-chip 2624/2624, R2 782/800,
                                          # whole-program 173,556/173,556 all on the same T1
python3 sw/timed_wvec_gate.py             # count 88/88, digest 88/88, cycles +0.0 %
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED
python3 sw/timed_fuzz.py                  # 1,272/1,702 exact, EVT 1,165 excluded (unchanged)
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds        # 154/188
python3 sw/timed_fuzz.py --pop evt --evt-replay                           # 678/1,008  (NEW)
python3 sw/timed_fuzz.py --evt-replay      # REGISTERED 1,272/1,702  EVT-unlocked 678/1,008
                                           # COMBINED   1,950/2,710  (NEW)
```

`sw/check_enter_nesting.py` is the VERILATOR/RTL leg (CLAUDE.md) and is NOT in
this set: S9b touches `sim/` and `sw/timed_fuzz.py` only, and the working tree
carries unrelated uncommitted `hdl/` and `sw/` changes from another branch.

### 20.11 Ledger delta

| | after §19 | after this addendum |
|---|---|---|
| `timed_fuzz`, REGISTERED | 1,272 / 1,702 | unchanged (byte-identical) |
| `timed_fuzz`, EVT | 1,165 EXCLUDED | **678 / 1,008 scored** (157 OPEN_BUS still excluded) |
| `timed_fuzz`, COMBINED | — | **1,950 / 2,710 (72.0 %)** |
| `timed_fuzz`, VICTORY TRANCHE | 154 / 188 | unchanged; 0 EVT by construction |
| v0.1 w0 / w1 / w3 / `EB` w1 | 168,997 / 1,200 / 1,200 / 200 | unchanged |
| boot / scenario / ENTER / INS / wvec / law cards | as §19.11 | unchanged |
| functional corpus | 7,341,126 | unchanged |
| mechanisms | M1-M16, M2r, M5b | **+ M17 (the HLT block is M7's index-2 sample; the HALT display drives the live address latch)** |
| §19.8.2 chained REP abort | MEASURED, mechanism OPEN | **ANCHOR RESOLVED (cadence-keyed); the eval/write-accept rival FALSIFIED at w1, w2, wrand7** |
| scaffolding | S9 half removed | **S9 REMOVED** — both halves; `timed-boot` replays pin events |
| open w0 physics questions | 3 tails | 3 tails + the HALTWAKE family (§20.8) |

### 20.12 What is left, and the stimulus for each

1. **INTA UNDER WAITS is still not a law** — but it is now DATA: 44 waited
   seeds part within 12 rows of an acknowledge (§20.8 `ACK`).  The capture that
   would close it is unchanged from §19.14: a w1/w3 pin-event tranche of
   SINGLE-INSTRUCTION goldens, where the acknowledge geometry can be read
   directly instead of inferred from a 1,000-row program.  Until then no gate
   claims a law and this family is reported, not modelled.
2. **The HALT WAKE geometry** (81 seeds, 64 of them at w0) is the one genuinely
   NEW open surface this session opened.  Two shapes, both nameable: the woken
   fetch's display clock (the chip drives it one clock earlier than the model
   when the wake lands inside the HALT cycle), and 32 seeds where the chip
   never drives the HALT status at all because the wake reached the register
   first.  The stimulus is a single-instruction `HLT.INT` / `HLT.RES` sweep with
   the assert clock walked ACROSS the HALT display window — the existing
   pin-event generator already produces it, only the `delay` axis needs the
   sweep.  NOT modelled here: it would be a fitted offset.
3. **The 5 `REP-WITHDRAW-UNMATCHED`** (registered FAIL, §20.7).  Four are
   inherited functional-stream divergences; mc1/2389 is the one open case.
4. **The chained REP abort's MAGNITUDE** is still a measured clock without a
   ROM row, even though §20.6 resolved its anchor.
5. The three w0 tails (`0F12`, `C1.6`, `F7.4`) are untouched and unrelated.
6. **No board session was used.**  The conditional board items (the waited
   chained-withdrawal capture, a w1/w3 pin-event tranche, the four card
   stimuli) were NOT run: the waited chained withdrawal turned out to be
   already IN the bank (§20.6), which is what the board session was for, and
   nothing else in this session's plan reached the point of needing silicon.
   No pre-registration was written for a board session and none was taken.

## 21. POST-CLOSURE ADDENDUM #6 — S10, THE CAPTURE-FIRST BOARD SESSION (2026-08-03)

**This section is an ADDENDUM.  Nothing in §0-§20 is edited or retracted by it.**
S9b closed the EVT driver and, in closing it, produced three things that are
DATA and not LAW: the 44 waited seeds of the `ACK` family (§20.8), the 81 seeds
of the `HALTWAKE` family, and a chained-REP-abort magnitude whose anchor is
resolved but whose size is still a bare clock (§20.6, §20.12 item 4).  Every
one of those is a *stimulus* request, and every one of them names silicon.
This section is the board session that goes and gets it.

### 21.0 PRE-REGISTRATION — written and committed BEFORE the board was touched

The discipline is §12.0's and §14.0's, unchanged, and it is restated because
this session has FIVE probes and a 30-minute budget and is therefore exactly
the kind of session in which a post-hoc reading gets dressed up as a
prediction:

* **SINGLE WRITER**, checked before contact — no foreign `v30run serve` /
  `v30ctl` / fork-session runner, locally or on the target.  Nothing in the
  code enforces this; it is a manual pre-contact procedure and the check is
  recorded in the session log.
* **SOCKET ONLY** (`use_core=False`, passed explicitly on EVERY call because
  the board's CFG is sticky), **no FPGA flashing anywhere**, no
  `safe_flash.sh`, no `v30ctl.py prep`.
* **Raw 64-bit capture words retained** with a sha256 beside every derived
  record, and — the P2 lesson (§13.4) — **the full per-clock row stream
  retained, never a digest alone**.  A `SHA256SUMS` per probe directory.
* `board_idle()` at the end of the session, and the result stated.
* A **wedge stops the session**: if the board or the serve runner wedges, the
  session stops and reports; it is not nursed along.

#### 21.0.0 Instrument provenance — the harness is NOT wholly committed, and that is declared here

An honest declaration, because §12.8 item (d) is the standing lesson (*"…are
NOT a controlled reference and should not be cited as one"*).  The working tree
at the moment of registration carries UNCOMMITTED changes to two files in the
board path, from another branch's in-flight work:

| file | sha256 (as used) | state |
|---|---|---|
| `sw/v30run.py` | `884bce6402c36e46…` | **MODIFIED** — adds `want_raw=` to `ServeRunner.run` / `run_image` |
| `sw/check_seq.py` | `ec8a95fe378e6382…` | **MODIFIED** — folds `bs_late` into `bs_early` on TI/T4 rows in `run_chip` |
| `sw/emit_suite.py` | `903c07ec4d3a4248…` | committed (HEAD `d8159d3b`) |
| `sw/t2b_board.py` | `1fae26e3333e6014…` | committed |
| `sw/timed_lawcards.py` | `03928f71d2b30768…` | committed |
| `sw/timed_fuzz.py` | `2fe9d7ff06588896…` | committed |

Two consequences, both stated rather than worked around:

1. **`want_raw` is load-bearing and uncommitted.**  `sw/t2b_board.capture()` —
   COMMITTED code, the primitive every capture in §12 and §14 went through —
   calls `run_image(..., want_raw=True)`.  The committed board tooling does not
   run without the uncommitted library change.  This session uses the same
   primitive and therefore inherits the same dependency; the sha above pins
   exactly which bytes were used.
2. **The TI/T4 `bs_late` fold is the campaign's ESTABLISHED capture semantics,
   not a novelty of this session.**  `t2b_board.capture()` applies it inline
   (it does not go through `run_chip`), and `t2b_board`'s own docstring
   describes it as *"run_chip's own like-sampling rule"*.  Every banked t2b/t4
   capture was taken with it.  Capturing WITHOUT it would be the deviation.
   S10 therefore uses `t2b_board.capture()` unmodified, so the fold is applied
   identically and this session's captures are comparable to the banked ones.

The RTL working-tree changes (`hdl/`) are inert for this session **by
construction**: `use_core=False` selects the socketed physical part, so no
fabric is in the measurement path at any point.  Nothing is flashed, so the
bitstream on the board is whatever §14's session left, and it is not read.

#### 21.0.1 What this session is FOR, and the three standing exclusions it attacks

| open item | where it was booked | the stimulus this session takes |
|---|---|---|
| INTA under waits is not a law — 44 waited `ACK` seeds | §19.14 item 3, §20.12 item 1 | **S1**, a w1/w3 pin-event tranche |
| the HALT-wake geometry — 81 `HALTWAKE` seeds | §20.12 item 2 | **S2**, a fine-grained HLT delay sweep |
| the four UNRESOLVED law cards C2/C6/C7/C11 | §(c) item 3, `biu_law_cards.md` §A.1 | **S3**, the four card stimuli |
| the chained-abort MAGNITUDE | §20.12 item 4 | **S4**, waits × chain length |
| A30 — bank A vs bank B | §(c) item 10, `ucsim_provenance.md` §61 | **S5**, the directed BRKEM capture |

**GUIDING PRINCIPLE, restated because it constrains what may be LANDED from
this session (CLAUDE.md, user directive 2026-08-01):** this is 80's era
hardware; nothing on the die is wasted; complex behaviour is simple systems
interacting in ways not yet understood.  A large fitted table, a many-cased
rule or a per-form special case is a signal of misunderstanding, not a
deliverable.  In particular the HALT-wake geometry (S2) is registered as
**UNMODELLED — MEASURING**: §20.12 item 2 already refused to model it because
it would be a fitted offset, and that refusal stands into this session.  S2
produces a MEASUREMENT; a mechanism is landed only if one falls out.

#### 21.0.2 The budget, and the CUT RULE (registered in advance)

Board time is budgeted at **under 30 minutes** total.  Throughput precedent:
§12.7 ~650 captures in under 2 min; §14.3 176 cells in 11 s; §14.4 648 captures
in 46 s.  The planned census is ≈5,300 captures.

**CUT RULE, as §14.0's:** if wall time runs over, the **POPULATION** is cut by
whole strata, evenly, and the cut is STATED — the **repetitions are never
cut**, and no probe is silently dropped.  A probe that is not run is reported
as not run (the §14.5 precedent for B3).

Every probe is a directed factorial with **5 repetitions** at `div=8` (4 MHz).
**Dual-frequency (`div=4`, 8 MHz) promotion is applied only where the blackbox
protocol requires it** — i.e. to the cells a card or a verdict will be FROZEN
against (S3's law-card cells, S5's A30 cells), not to bulk tranche emission.
The §12.1 exclusion stands and is not re-litigated: `rd_n` and raw `bs_late`
are within-cycle pulses read at a fixed sampling edge and are excluded from the
cross-frequency stability projection.

---

#### S1 — the w1/w3 PIN-EVENT TRANCHE (opens INTA under waits)

*Why.* The pin-event goldens are **w0 only** (§19.0), so w0 INTA is fully
oracled and nothing above w0 is.  §20.8's `ACK` family is 55 seeds of which
**44 are WAITED** — the standing exclusion showing up as data.  Reading the
acknowledge geometry off a 1,000-row whole-program capture is inference; a
single-instruction golden reads it directly.

*Stimulus.*  `emit_suite._emit_one_index(spec, is_evt=True, op, idx, HOST,
seed_base, preload_n=-1, waits=N)` — byte for byte the path §12.4's P4 used to
emit the `F3AA` pair at w1/w3, and the path that emitted the whole w0
pin-event corpus at §19.  `EMIT_USE_CORE is False` is asserted at the call site
(goldens may come from the socket and nothing else).

*Factorial axes.*

| axis | levels |
|---|---|
| form | **INT.90, NMI.90, HLT.INT, HLT.RES, INT.F3AA, INT.9D** (6) |
| waits | **1, 3** (2) |
| case index | **0..199** (200) — the same 200/form/wait the existing w1/w3 tranches use |
| evt delay | each form's OWN stratum, unchanged: INT.90 `1..7`, NMI.90 `1..7`, HLT.INT/HLT.RES `14..40`, INT.F3AA `1..28`, INT.9D `1..10` (`emit_suite.EVT_FORMS`) |

= **2,400 emitted cases**.  Repeatability control: 24 declared cells (2 per
form per wait) re-captured at **5 repetitions**, and 6 of those (one per form,
w1) promoted to both frequencies.

The six forms are chosen for discrimination, not coverage: `INT.90` is the
minimal vectored acknowledge, `NMI.90` the edge-latched twin that separates the
pipeline depth (3 vs 4), `HLT.INT`/`HLT.RES` carry the wake (vectored and
masked), `INT.F3AA` carries the mid-string withdrawal (and feeds S4), `INT.9D`
carries the POP-PSW boundary race whose flags policy §19.9 fixed.

*Predictions.  From the mechanisms, where they predict:*

1. **M14 is wait-INVARIANT.**  `D = max(B, A+3)` (INT) / `max(B, A+4)` (NMI),
   `entry = D+2`, with `A` = (the CODE T1 at the anchor) + 2 + `delay` and `B`
   = the replayed boundary's RETIRE clock.  `A`'s pipeline term is a FLOP
   CHAIN — three flops for the INT level, an edge latch read one clock later
   for NMI — and a flop chain is counted in CLOCKS, not in bus cycles.  So the
   depth **must not stretch with waits**: the census that scored 800/800 at w0
   with `p = 5` (INT) / `6` (NMI) in the `max(B+2, A+p)` form must score the
   same `p` at w1 and w3, on the goldens' own acknowledge positions.
   *Falsifier:* any w1/w3 case whose acknowledge is inconsistent with
   `max(B, A+3|4)+2`, or a `p` that moves with `N`.
2. **M15 is wait-INVARIANT.**  The acknowledge cycle drives no address:
   AD15-0 float through the commit display and T1, AD19-16 driven to 0 over
   both; from T2 on it is an ordinary read display.  Waits add Tw between T3
   and T4 and touch none of that.
   *Falsifier:* any w1/w3 INTA cycle that drives an address phase.
3. **THE ONE GENUINELY NEW DISCRIMINATOR — the INTA1→INTA2 gap.**  §19.2
   derives it with no rule at all: `01E1`'s `F` releases at the acknowledge's
   `eu_done` and `01E2` posts one clock later, which puts INTA2's T1 exactly
   **7 clocks** after INTA1's on a quiet bus (measured 200/200 per form at w0).
   `eu_done` is a BUS-COMPLETION event, so it moves with the acknowledge
   cycle's own wait count.  Two readings, registered with the clock each
   predicts, exactly as §12.0's P4 registered A/B:
   - **Reading A — BUS-KEYED (what the model's mechanism says today):** the gap
     is `7 + N_ack`, where `N_ack` is the Tw count of the FIRST acknowledge
     cycle.  At uniform w1 → **8**; at uniform w3 → **10**.
   - **Reading B — CADENCE-KEYED (the campaign's own recurring answer):** the
     gap stays at **7** at every wait level, joining M6's T4+2 (§12.1), the OPR
     release at index 2 (§11.4), the `F3AA` closing pop at T4+2 (§12.4) and
     §20.6's chained-abort clock as a FIXED cycle-relative index.
   Reading A is the model's current prediction and is what will be scored; but
   the campaign has now measured FOUR separate quantities that turned out to be
   fixed indices rather than eval/completion-keyed, so Reading B is the live
   rival and is registered as such.  *Falsifier for both:* a gap that is
   neither 7 nor `7+N_ack` — which would be a genuinely new term and is
   reported as one.
4. **`entry = D+2` and the NMI ROM tail are ROM rows, not constants.**  NMI's
   `D+2+5 = D+7` to the IVT read is five ROM rows (`01DA 01DB 01EC 01ED 01EE`);
   ROM rows cost clocks, not bus cycles, so the five clocks stand at w1/w3
   while the IVT READ's own T1 slides by the bus.
   *Falsifier:* an NMI IVT-read post clock that is not `D+7`.
5. **The suppressed pop (§19.3) is wait-invariant.**  The recognition decision
   sits at the RETIRE, not the would-pop, and the byte is not popped: the QS
   port stays idle across the recognition at w1/w3 as at w0.
   *Falsifier:* an `F` on the recognition clock in any waited case.

*The numeric bar, stated before the run.*  The w0 pin-event forms score
**2,600 / 2,600 exact** (§19.13).  The same model, unchanged, is scored on the
new w1/w3 tranche and **the FIRST full run is the ratchet baseline of record**
(§20.0 clause 4's rule, applied here).  What is registered as falsifiable now:

* **B1a** — zero emission hard failures (`event did not fire`, `ComposeError`,
  `no done marker` after retry) over the 2,400.  A form that cannot be emitted
  at a wait level is a FINDING, reported, not silently dropped.
* **B1b** — the 24 repeatability cells are **pin-identical over 5
  repetitions**, and the 6 promoted cells identical at 4 MHz and 8 MHz under
  the §12.1 projection.  A cell that is not is a capture-side result and
  invalidates that cell, not the model.
* **B1c** — **any form scoring 200/200 at BOTH waits proves that form's
  waited acknowledge geometry needs NO new term**, and the count of such forms
  is the session's headline number for this probe.  Predicted: `INT.90` and
  `NMI.90` (the minimal acknowledges) score 200/200 at both waits if and only
  if reading A above is right and nothing else is missing.
* **B1d** — the shortfall, if any, is localised to a CLOCK and a named field
  before any mechanism is proposed.  A shortfall that cannot be localised is
  reported as un-localised.

*What may NOT happen:* no gate anywhere is re-scoped to include w1/w3
pin-events until this tranche exists and is frozen.  Until then, and if this
probe fails to produce a clean tranche, INTA-under-waits **remains a stated
exclusion** — §19.14 item 3 stands unmodified.

---

#### S2 — the HLT DELAY SWEEP (the HALT-wake geometry)

*Why.* §20.8's `HALTWAKE` family is 81 seeds, **64 of them at w0** — the one
genuinely NEW open surface S9b opened.  §20.12 item 2 names two shapes and
refuses to model either: the woken fetch's display clock (the chip drives it
one clock earlier than the model when the wake lands INSIDE the HALT cycle),
and **32 seeds where the chip never drives the HALT status at all because the
wake reached the register first**.  §19.6's wake was measured on w0 goldens
whose assert clock is FAR from the HALT display; these are the ones where it
is not.  The named stimulus is exactly this sweep: *"the existing pin-event
generator already produces it, only the `delay` axis needs the sweep."*

*Stimulus.*  `HLT.INT` (vectored, `ie=1`) and `HLT.RES` (masked resume,
`ie=0`, `close="next"`) emitted through the same `emit_evt_case` path, with
`case["delay"]` **overridden to a swept value** instead of drawn from the
form's `14..40` stratum — the only change, and it is a change of the RIG's
schedule, not of the model.

*Factorial axes.*

| axis | levels |
|---|---|
| form | **HLT.INT, HLT.RES** (2) |
| delay | **0..48 step 1** (49) — deliberately brackets the form's own `14..40` on both sides so the sweep walks the assert clock from BEFORE the pop to well past the HALT display |
| waits | **0, 1** (2) |
| reps | **5** |

= 980 captures.  One preparation history (the sweep is the axis; a second
history is the falsifier's job, below).

*Predictions.  Where the mechanisms predict:*

1. **A THRESHOLD EXISTS, and it is sharp.**  M16 (§19.5) says the HALT status
   takes the register on the first clock the register is FREE from the DECODE
   cycle on, and §20.5 says `display = eval+1` while `T1 = max(eval+2, the
   bus's first FREE clock)`.  Together these predict a single threshold delay
   `d*` such that
   - `delay < d*`: the wake reaches the register FIRST and **the chip never
     drives the HALT status at all** (the 32-seed shape, reproduced
     deliberately);
   - `delay >= d*`: the chip drives the HALT display and then wakes.
   Predicted: **one threshold, not a scatter** — a scattered boundary would
   mean the wake and the display are not competing for one register and M16 is
   wrong about what the competition is.
   *Falsifier:* two or more disjoint delay bands that drive the status, or a
   band whose behaviour alternates.
2. **`d*` MOVES WITH THE RIG'S Tw, BY EXACTLY THE ADDED WAIT.**  §12.3
   measured that the RIG runs a full T-state cycle over the HALT pseudo-cycle
   and **does insert Tw** (T1..T4 = 4 / 5 / 7 clocks at w0 / w1 / w3), while
   the CPU's own side — the 2-clock status display — is wait-independent.  So
   the window in which "the wake lands inside the HALT cycle" is **one clock
   wider at w1 than at w0**, and therefore:
   ```
   d*(w1) - d*(w0) = +1        (the single Tw the rig inserts)
   ```
   This is the sharp registered prediction and it discriminates cleanly: a `d*`
   that does NOT move says the wake geometry is keyed to the decode CADENCE and
   not to the bus cycle at all, which would be the §12.4 / §20.6 answer again
   and would be a genuine finding.
   *Falsifier:* `d*(w1) - d*(w0) ∉ {0, +1}`, or a shift that is not an integer
   number of clocks.
3. **The HALT display is 2 clocks at every delay and both wait levels**
   (§12.3's measured status display), whenever it is driven at all.
   *Falsifier:* any capture with a 1- or 3-clock HALT status.
4. **HLT.RES's resumed pop tracks `dec+1`; HLT.INT's entry tracks `dec+3`**
   (§20.1's one re-expression of §19.6), with `dec = max(A + pipe, the clock
   the part is halted on)`.  Over the sweep, `A + pipe` is the later term for
   large `delay` and the halted clock is the later term for small `delay`, so
   **the sweep crosses the max** — and the crossing point is the second,
   independent estimate of `d*`.  Predicted: the two estimates agree.
   *Falsifier:* the entry/pop threshold and the display threshold disagree by
   more than a clock — which would mean the wake decision and the display
   competition are two different events, not one.

*Registered as UNMODELLED — MEASURING (the brief's explicit case).*  The
woken fetch's **display clock** when the wake lands inside the HALT cycle is
NOT predicted here.  §20.12 refused it as a fitted offset and that refusal
stands.  This probe produces the measured table `delay × waits → (status
driven?, display clock, first fetch T1, entry/pop clock)` and the mechanism
question is asked of that table afterwards.  **A per-delay offset table is NOT
a deliverable** — if the geometry does not collapse to a statement about ONE
competing register, it is reported as measured-and-open, in the §19.8.2 style
("MEASURED offset, MECHANISM OPEN"), not landed.

---

#### S3 — THE FOUR CARD STIMULI (C2, C6/C7, C11)

*Why.* `timed_lawcards.py` scores **7 GREEN / 0 RED / 4 UNRESOLVED**, and all
four UNRESOLVED are STIMULUS GAPS, not model failures — the tool hard-codes
each with its missing capture (`sw/timed_lawcards.py:210, 234, 241`).  The
booked probes are `biu_law_cards.md` §A.1's.

**TARGET, registered: 11 GREEN / 0 RED / 0 UNRESOLVED.**  Registered equally
plainly: a card may come back **RED** (the stimulus exists and the model fails
it — a model finding, reported as one) or **stay UNRESOLVED** (the stimulus did
not isolate what the card names — a probe-design finding, reported as one).
Neither outcome is smoothed, and a card is NOT moved to GREEN by weakening what
it asserts.

**S3a — C2, LC1's queue-fill RAMP.**  The card: *"queue-fill ramp, waited →
prefetch resumes IMMEDIATELY at the fill threshold"*, against C1/C3's
steady-state `cidle` pin of 3.  The gap is that the Arm-C sled isolates the
STEADY STATE and not the transient.
*Stimulus:* a `gen_seq.Prog` program that repeatedly FLUSHES the queue to empty
(`emit_farjmp_next()`, a contained far JMP — the same construct the sled corpus
uses) and then runs a fetch-limited sled, so every flush restarts the fill from
zero.  Axes: flush period × trailing sled length × the four corpus wait vectors
`ws0:wmax0, ws5:wmax1, ws7:wmax3, ws11:wmax7`, 3 reps, plus 5 reps + both
frequencies on the two cells the card is frozen against.
*Prediction:* at the FIRST refill after a flush the chip's idle gap is
**strictly smaller than the steady-state `cidle` of 3** (the card's "resumes
immediately"), and the sim reproduces the ramp's gap distribution.
*Falsifier:* a post-flush gap distribution centred on 3 — i.e. no ramp
transient exists and C2's premise is wrong, which is reported as refuting the
CARD, not the model.

**S3b — C6/C7, LC3's Tw-parity RMW commit (the uRMW gate of record).**
`biu_law_cards.md` §B is unambiguous and its protocol is adopted verbatim:
**the check MUST carry a CHIP-SIDE POSITIVE CONTROL**, because a non-firing
structure verifies nothing, and **the check FAILS VACUOUS if the chip signature
cannot be produced** — a flagged outcome, not a pass.  It also warns that the
synthetic gadgets did NOT reproduce the firing structure and must not be reused
as-is.
*Stimulus:* the RMW-write gadget construction (`ADD word[disp16],imm16` =
`81 06 lo hi 01 00`; `INC word[disp16]` = `FF 06 lo hi`; `NEG word[disp16]` =
`F7 1E lo hi`) over `j_lead` leading NOPs × `k_fill` back-to-back RMW writes,
per `sw/biu_law_lc3_gadget.py`'s `build_image` — **but captured from the
SOCKET, which that script never did** (it is a board-free Verilator search).
*Protocol, in this order and no other:*
1. **POSITIVE-CONTROL SEARCH.**  Coarse grid `kind ∈ {ADD, INC}` × `j ∈
   {0,2,4,6}` × `k ∈ {1,2,4,8}` × uniform `w ∈ {1,2,3,4,5,6}`, socket, 1 rep,
   scanning the CHIP stream for the documented firing signature: an RMW
   mem-write ready AT a prefetch's T4 with an EVEN Tw parity, committing EARLY
   (the eval_ext direct slot, **T4+2**).
2. If and only if the signature is FOUND on silicon: promote those cells to 5
   reps at both frequencies, retain full rows, and score sim-vs-chip.
3. If the signature is NOT found: **report C6/C7 as FAILED-VACUOUS** with the
   grid that was searched.  This is a registered possible outcome and it is not
   a pass.
*Predictions (these are REPRODUCTIONS — the silicon is already banked at 15/15
and 30/30, RTL unchanged since):* C6 — even-Tw-parity RMW write ready-at-T4
commits EARLY at T4+2.  C7 — a MEMR **load** ready at T4 does NOT split on
parity at either parity (write-scoped).
*Falsifier:* an even-parity RMW write that commits LATE, or a load that splits
on parity — either refutes the banked 15/15 and is a much bigger finding than a
card colour.
*The honest-tension note is carried into this probe as registered
(§B of `biu_law_cards.md`):* the H-PHASE landing recorded a −50u census effect
while the raw diff shows zero census-combo dependence.  If the firing structure
is found, that tension is re-examined against it; it is not asserted away.

**S3c — C11, LC4's `owns_slot`, the SINGLE-SOURCE matrix.**  The card is
"MUST (enum)": the claim is that reservation is **NOT uniform** — exactly two
enumerated sources make the prefetch lose the slot, and *"every other source
keeps baseline yield; a rebuild making reservation uniform refutes"*.  The gap
is that no directed capture isolates a SINGLE source.
*Stimulus, as architecture (the RTL state names are translated to the
instruction forms that produce them):*

| cell | source | instruction form |
|---|---|---|
| **P** (positive) | `S_DHI` final-displacement pop | `MOV [disp16], reg` — a disp16 STORE, reservation asserting at the final displacement byte's pop |
| **P** (positive) | `S_PUSH_CALC` @ q≥2 | `PUSH reg` with the queue held at occupancy ≥ 2 |
| **N** (held-out negative) | reg-EA store | `MOV [BX], reg` |
| **N** (held-out negative) | disp16 LOAD | `MOV reg, [disp16]` |
| **N** (held-out negative) | RMW | `INC word [disp16]` |

Axes: 5 sources × leading phase `j ∈ 0..7` × the 4 corpus wait vectors × 3
reps; the 2 positive cells promoted to 5 reps at both frequencies.
*Prediction:* the prefetch **loses the coincident slot at exactly the two
enumerated sources** and keeps baseline yield at all three negative controls,
and the sim reproduces the same split.
*Falsifier — and it is a real one:* a THIRD source at which the prefetch also
loses (reservation is uniform → the enumeration is an artifact and C11's "enum"
qualifier is wrong), or an enumerated source at which it does NOT.  Under the
SIMPLICITY principle a uniform answer would be the *better* one, and it is
registered here as the outcome that would REFUTE the card's enumeration rather
than as a failure to be avoided.

---

#### S4 — THE CHAINED-WITHDRAWAL MAGNITUDE

*Why.* §20.6 RESOLVED the anchor — the extra clock is cadence-keyed and the
eval/write-accept rival is FALSIFIED at w1, w2 and wrand7 — but left the
MAGNITUDE as *"a measured clock without a ROM row"* (§20.11, §20.12 item 4).
The bank's evidence is 21 chained withdrawals, all exactly +1, but at only 3
distinct wait levels and with chain length confounded with seed.

*Stimulus.*  `INT.F3AA` (`REP STOSB`, `cx` set by the form's own builder) with
the evt delay swept to select WHICH element the abort lands on, so chain length
becomes a controlled axis instead of an incidental one.

*Factorial axes.*

| axis | levels |
|---|---|
| waits | **0, 1, 2, 3** (4) |
| chain length (completed elements at the abort) | **2, 3, 4** (3) |
| delay cells per (wait, chain) | **10**, swept to land the abort on the intended element |
| reps | **5** |

= 600 captures.  A one-element (chain = 1) control cell is captured at every
wait level as the baseline the offset is measured AGAINST.

*Prediction, from §20.6's resolved anchor.*  The extra clock is a row-cadence /
decode-pipeline clock and NOT a bus-completion one.  Therefore:
```
offset(chain >= 2) = +1     for chain in {2,3,4} and waits in {0,1,2,3}
offset(chain == 1) =  0     at every wait level
```
— **12 cells, all +1; a single clock, wait-invariant AND chain-length-invariant**,
and the flush at the loop row + 10 in every case.
*Falsifiers, each of which names a different mechanism:*
- an offset that GROWS with chain length (e.g. +2 at chain 4) → the clock is
  per-iteration drift after all, and §19.8.2's "a single clock, not a
  per-iteration drift" is refuted at chain lengths the bank did not sample;
- an offset that grows with `N` (e.g. `+1+N`) → it IS bus-keyed and §20.6's
  falsification of the write-accept anchor was under-powered;
- any chained abort whose flush is not at the loop row + 10 (§20.6's own
  standing falsifier).

*Closure condition, registered.*  If all 12 cells read +1 with the chain-1
control at 0, §20.12 item 4 is **CLOSED as far as measurement can close it**:
the magnitude is one clock, cadence-keyed, invariant in both the wait axis and
the chain axis.  It is stated in the §20.6 style — **anchor resolved, magnitude
measured, ROM row still unnamed** — and NOT dressed as a derived row.  Naming
the row would require the ROM to show a row that costs exactly this clock, and
no such row is claimed.

---

#### S5 — A30, THE DIRECTED CAPTURE

*Why.* The ledger's own wording (`ucsim_provenance.md` §61): *"A30 needs a
directed capture: a contained program that does `BRKEM`, stays in 8080 mode,
and takes an INTR — at which point one INTA cycle instead of two settles it in
a single seed."*  §14.5 turned it into an **n = 1 datapoint** by reading MD off
the pins (M9: PS3 is the emulation-mode bit) across the banks:
`len=2, MD=0` 760, `len=1, MD=0` 8, **`len=2, MD=1` — exactly 1**
(`t30-raw/raw_3821`, rows 969-981, both acknowledge cycles carrying
`ps = 0xE` = MD | IE | CS).  It points at bank B / fixed priority.  n = 1 is a
datapoint, not a closure.

*Stimulus.*  A contained program, built with `testimage.compose`:
1. `EI` (`FB`) then `BRKEM vec` (`0F FF nn`) — BRKEM pushes PSW/CS/IP and
   enters emulation mode with **IE cleared**, so
2. the 8080-mode stub at the vector begins with 8080 `EI` (`FB`, the same
   encoding) and continues with 8080 `NOP`s (`00`), keeping the part in
   emulation mode and interruptible;
3. the rig asserts **INTR** (`pin=0`) at a controlled delay after the anchor,
   landing inside the 8080 NOP run;
4. the capture is read for the INTA run and, on the acknowledge cycles
   THEMSELVES, for PS3.

*Factorial axes.*  2 preparation histories (two vectors / two stub locations)
× waits **{0, 1}** × 10 delay cells × **5 reps** = 200 captures, at both
frequencies for the four cells the verdict is frozen against.  Target: **≥ 20
independent acknowledges taken with MD observed = 1 on the acknowledge cycle**.

*Predictions — and the whole point is that they are OPPOSITE and both cheap to
read:*

| reading | mechanism | prediction |
|---|---|---|
| **bank B / FIXED PRIORITY** (the model, and the n=1 datapoint) | bank A is dead silicon; the micro-address decoder has no mode input | **TWO** INTA cycles, both with **PS3 = 1** |
| **bank A / EMULATION-MODE INPUT** (assumption A30, the 14th decoder input) | the decoder takes MD as a 14th input and selects `01DC`-`01DF` | **ONE** INTA cycle, with **PS3 = 1**, and the vector taken off the HIGH lane |

*Falsifier for the bank-B verdict:* a SINGLE acknowledge in any repetition of
any cell.  One such capture flips A30 and it is reported immediately.
*Instrument falsifier (checked first, and it can void the whole probe):* if
PS3 is **0** on the acknowledge cycles, the part was NOT in emulation mode when
the interrupt landed and the probe measured nothing — the cell is VOID, not
evidence, and the stub is fixed before anything is scored.  This is the exact
contamination §61 and §14.5 both name as the reason the earlier evidence did
not count.

*What may be claimed.*  A30 is an **ASSUMPTION with a free-choice
classification** (`ucsim_campaign_verdict_2026-08-01.md` §365: one of six
EU-semantic free choices).  A clean n ≥ 20 of two-cycle MD=1 acknowledges
UPGRADES the ledger entry from "free choice" to **MEASURED: silicon takes bank
B in emulation mode**, and REFUTES the emulation-mode-decoder-input mechanism
as the explanation — it does not by itself prove bank A is dead silicon
(nothing observable distinguishes "dead" from "never selected"), and that
distinction is stated rather than claimed.  A cross-reference erratum goes to
the FUNCTIONAL ledger either way, because §(d) already records that the
`has_brkem` flag under-reports 8080 excursions and that A30's "unreached even
with 8080 mode live" was evaluated over a set now known to be too small.

---

#### 21.0.3 The standing ratchets this session may not move backwards

Registered so that no S10 landing can be scored against a moved denominator:

| ratchet | value entering S10 |
|---|---|
| functional corpus | **7,341,126 / 7,341,126** |
| v0.1 w0 timed | **168,997 / 169,000** |
| v0.1-w1 / -w3 | **1,200 / 1,200** each; `EB` w1 200/200 |
| `timed_fuzz` REGISTERED | **1,272 / 1,702** |
| `timed_fuzz` EVT-unlocked | **678 / 1,008** (population 1,008 / 157 OPEN_BUS, FROZEN) |
| `timed_fuzz` COMBINED | **1,950 / 2,710** |
| victory tranche B2 | **154 / 188** (216 cells, 28 OPEN_BUS, 0 EVT by construction) |
| `timed_wvec_gate` | count 88/88, digest 63/88, cycles +0.0 % |
| `timed_lawcards` | **7 GREEN / 0 RED / 4 UNRESOLVED** |
| boot / scenario / ENTER / INS | 220 rows; 18/0/9; 154/154 ×5; 173,556/173,556 |

**Every one is monotone.**  Zero-newly-broken on all scored populations is a
HARD gate for any mechanism this session lands, and the functional 7,341,126
is re-run before the final commit.

**V-registrations are untouched.**  §14.0's V0-V5 are not re-opened by this
session.  **V5 remains a registered FAILURE**; it changes standing only if a
re-score meets its bar (V1 = 100 %), and in that event it is reported as
*registered-FAIL-plus-addendum*, never as a restatement.

#### 21.0.4 Deviation policy

Any post-capture change to a criterion registered above is recorded AS a
deviation, in the §14.4 style ("a post-capture change to a registered criterion
and is recorded as one"), with the measurement that motivated it.  A registered
clause that fails is reported as **FAILED**, in the §20.7 style, and not
restated.

#### 21.0.5 Instrument facts established OFFLINE, before contact (so no capture discovers them)

Confirmed by reading the harness, not by running it:

1. **The new tranche gets its OWN suite directory and seed base.**  The existing
   `tests/v30/v0.1-w1` / `-w3` are 6 ORDINARY forms (`B8 8B 89 F7.6 EB E8`) ×
   200 = 1,200 each, seed bases `v30-w1` / `v30-w3`, and they contain **no
   pin-event form**.  S1 emits into `tests/v30/v0.1-w1evt` / `-w3evt` with seed
   bases `v30-s10-w1evt` / `v30-s10-w3evt`, so the **registered 1,200/1,200
   denominators cannot move** and the S1 tranche is a NEW, separately named
   population from the first capture on.
2. **Every pin-event form alternates two anchor laws** (`emit_evt_case`,
   `sw/emit_suite.py:1293-1319`): EVEN case indices are COLD and anchor on the
   `CODE` T1 at the trigger address (`trigger="fetch"`, assert = anchor + 2 +
   `delay`); ODD indices are PREFETCHED (two `63 C0` preloads) and anchor on the
   window-opening `F` pop (`trigger="fpop"`, assert = anchor + `delay`,
   `delay >= 1`, `delay_hw = delay + 50·preload_n`).  **Both laws are in the S1
   tranche by construction** (100 of each per form per wait) and the S1 analysis
   reports the two anchors SEPARATELY — a waited term that appears on one anchor
   and not the other is a finding about the anchor, not about INTA.
3. **The capture depth scales with waits already:** `EMIT_CAP = min(4096,
   2048·(1+waits))` (`sw/emit_suite.py:2299-2301`), and the rig's capture buffer
   is a hard **4,096 records** (`sw/v30ctl.py:98`, `hdl/rtl/hps_axi_slave.sv:11`).
   At w3 that is exactly 4,096 — so a w3 pin-event case whose window does not
   close inside 4,096 clocks is a CAPTURE limit, not a model failure, and is
   reported as such.  `HLT.*` at `delay` up to 40 plus a waited wake is the form
   at risk; S2's sweep to `delay = 48` at w1 is inside it.
4. **`evt_fired` is the only confirmation the rig matched the anchor.**
   `emit_evt_case` already raises `RunError("event did not fire")` on a miss, so
   a mistyped anchor cannot silently produce a clean event-free golden.  S2 and
   S5, which build their own images, check `fired` explicitly for the same
   reason.
5. **POLL_N is active low and needs the static PINS register.**  `pins=0x4`
   holds POLL_N high so a `pin=2` event can pull it low.  No S10 probe uses
   POLL; `pins` stays 0 throughout, which is the model's standing behaviour
   (§20.0) and keeps 9B non-busy.
6. **`timed_lawcards.py` always exits 0** — it is a report, not an exit-code
   gate.  Its verdict counts are read from stdout, and the C1/C3 explanatory
   note string is known-stale (it still describes the pre-B1 RED reading while
   printing GREEN); the stale string is a booked cleanup and is NOT evidence.

### 21.1 THE INSTRUMENT FIRST — the board's clock divider is STICKY, and the emission path never pinned it

**This subsection is placed FIRST because two of this session's early readings
were INSTRUMENT ARTIFACTS, and they were caught, retracted and re-measured
before anything was landed.**  Reporting the catch is more useful than
reporting only the survivors.

`ServeRunner.cfg` sends `CFG <div> <waits> - 0 <use_core>`, and `div = None`
sends `'-'`, meaning *leave the board default*.  The divider lives ON THE BOARD:
it survives process exit and session exit.  **`emit_suite.py` never passes
`div`** — no golden suite in this repo records the frequency it was emitted at,
and every emission inherits whatever the previous session left behind.

**The board was found at `div = 4` (8 MHz) at the start of this session**, and
the first two S1 emissions inherited it.  What that does, MEASURED as a
controlled A/B over 12 IDENTICAL cases (same seeds, same images, same waits,
same code path — only the divider changed), 143 pre-T1 `Ti` rows in each arm:

| board divider | `bs_early` on the `Ti` row immediately before a `T1` |
|---|---|
| `div = 8` (4 MHz) | the NEW cycle's status — `CODE`/`INTA`/`MEMR`/`MEMW`, **143 / 143** |
| `div = 4` (8 MHz) | **`PASV`, 143 / 143** |

At 8 MHz the address-phase sampling edge lands *before* the status pulse and
**the DISPLAY CLOCK disappears from the capture entirely**.  This is the T2b
§12.1 phenomenon — "within-cycle pulses read at a fixed sampling edge" — but
§12.1 met it in `rd_n` and raw `bs_late`, which are EXCLUDED fields.  At 8 MHz
it lands in `bs_early`, which is a **COMPARED** column, so it corrupts the gate
instead of a projection.

**The two readings it produced, both RETRACTED before landing:**

1. *"the pre-T1 display clock is absent under waits"* — 12,480 / 12,480 `PASV`
   on the first emission, against 4,244 / 4,244 real status in the existing
   `v0.1-w1` tranche.  100 % vs 0 % is not physics, which is what prompted the
   diagnosis.
2. *"the HALT status display is 1 clock under waits, not 2"* — 800 / 800, and
   apparently a clean falsification of §12.3.  **It was the divider.**

**Re-measured with the divider PINNED at `div = 8`, both reverse completely**,
and the corrected data independently REPRODUCES §12.3 on a stimulus §12.3 never
used: the HALT status is **2 clocks, first row `Ti`, at w0, w1 AND w3 —
200/200 per form per wait level, 1,200 cases**.  §12.3 stands, confirmed twice
by two different instruments.

**Nothing in the banked corpus is retracted.**  `v0.1`, `v0.1-w1` and
`v0.1-w3` all carry the correct display status in their stored rows, so they
were emitted at 4 MHz; their divider provenance was never RECORDED, but it is
recoverable from their content and it is right.

**Booked instrument fixes** (not made here — this session does not modify the
committed emission path):
- `emit_suite.cmd_emit` should PIN `div` and stamp it into `emit_log.txt`
  beside the existing `# TRUTH SOURCE` and `# WAIT-RIG` lines.  The wait-rig
  guard already exists for exactly this class of hazard; the divider has no
  equivalent.
- `board_idle()` should leave the divider at the corpus frequency, so a session
  cannot hand the next one a surprise.

`sw/s10_board.py` pins the divider explicitly in every probe
(`DIV_OF_RECORD = 8`, `pin_div()`) and records it in every manifest.  The
uncorrected first emission is retained as evidence under
`sw/testdata/s10/s1-instrument/`.

### 21.2 M18 — THE SECOND ACKNOWLEDGE SITS AT THE FIRST'S COMPLETION EVAL + 5, AND INTA UNDER WAITS NEEDS NO NEW TERM

**MEASURED.**  The registered discriminator (§21.0 S1 prediction 3) offered two
readings for the INTA1→INTA2 gap.  **Both are FALSIFIED**, and the resolution is
not a new term at all — it is the campaign's own ONE INSTANT.

The measured gap, over the S1 tranche plus the w0 corpus:

| `Tw` on the acknowledge | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| INTA1 T1 → INTA2 T1 | **7** | **9** | **10** | **11** |
| reading A, bus-keyed `7 + N` | 7 ✓ | 8 ✗ | 9 ✗ | 10 ✗ |
| reading B, cadence-keyed `7` | 7 ✓ | 7 ✗ | 7 ✗ | 7 ✗ |

Reading A is right only at w0, where it is degenerate with B — which is exactly
why the w0 corpus never separated them.

**The one statement that covers all four:**

```
INTA2's T1  =  (INTA1's COMPLETION EVAL) + 5      at every wait level
```

with the eval being §11.1's instant and nothing else: at w0 it sits at
`last_i - 1` = `T1 + 2`; when the cycle carries waits it sits at `last_i` =
`T1 + 3 + N`.  Substituting gives 7 / 9 / 10 / 11 with no free parameter.

**The census: 2,339 / 2,339, zero exceptions, three wait levels**
(w0 800, w1 763, w3 776), and **w2 was HELD OUT of the derivation and then
confirmed at 177 / 177** — the gap is 10 there, which only the eval-relative
form predicts.

The constant 5 is not fitted: §19.2 already derives the w0 number from the
ROM's own rows (`01E1`'s `F` releases at the acknowledge's `eu_done`, `01E2`
posts one clock later) plus M1/M2's display law.  What S10 adds is that the
anchor those rows hang off is the EVAL, and the eval moves once — at w0→w1 —
and never again.  **The apparent wait dependence of the acknowledge is entirely
the eval's own step.**

*Falsifier:* any acknowledge pair whose second T1 is not at the first's
completion eval + 5, at any wait level.

**And the model already contains this.**  Scored on the fresh S1 tranche, with
no model change of any kind:

| form | w1 rows-exact | w3 rows-exact |
|---|---|---|
| `INT.90` | **200/200** | **200/200** |
| `NMI.90` | **200/200** | **200/200** |
| `HLT.INT` | **200/200** | **200/200** |
| `HLT.RES` | **200/200** | **200/200** |
| `INT.9D` | **200/200** | **200/200** |
| `INT.F3AA` | 163/200 | 176/200 |
| **TOTAL** | **1,163 / 1,200** | **1,176 / 1,200** |

arch **1,200/1,200** and window **1,200/1,200** at both wait levels.

**Registered clause B1c, scored: FIVE of the six forms score 200/200 at BOTH
waits.**  The registered meaning of that number is explicit — *"any form
scoring 200/200 at BOTH waits proves that form's waited acknowledge geometry
needs NO new term"* — so:

> **INTA UNDER WAITS IS NO LONGER AN OPEN LAW.**  M14 (the decision clock),
> M15 (the acknowledge drives no address) and the one-instant machine predict
> the waited acknowledge geometry exactly, on 2,000 fresh single-instruction
> goldens at two wait levels, with ZERO row diffs.  §19.14 item 3 and §20.12
> item 1 are CLOSED for the single-instruction population.

M15 was checked separately and holds under waits: AD19-16 = 0 on every
acknowledge T1 at w1 and w3, and AD15-0 carries the previous data phase.

### 21.3 The one S1 residual is a PREFETCH IN THE ACKNOWLEDGE GAP — and it is exhaustively localised

`INT.F3AA` is the only form that is not exact, and the reason is not the
interrupt.  Between INTA1 and INTA2 the chip sometimes grants a **CODE
prefetch**; the model does not.  The correspondence is exact — not
approximate — in every cell:

| waits | clean INTA pairs (nothing between) | `rows-exact` |
|---|---|---|
| 0 | 200 / 200 | **200 / 200** |
| 1 | 163 / 200 | **163 / 200** |
| 2 | 177 / 200 | **177 / 200** |
| 3 | 176 / 200 | **176 / 200** |

**Every** case with a clean pair is cycle-exact and **every** case with a
prefetch in the gap is not: 37 of 37 at w1, 23 of 23 at w2, 24 of 24 at w3, and
the intervening cycle is `CODE` in 100 % of them.

So the residual is an **arbitration** question — does the prefetch win the slot
the second acknowledge has reserved — and it belongs to the LC1/LC4 resume
family the campaign already tracks, not to interrupt timing.  It is named,
bounded (61 of 2,400) and carries its own discriminating population.

### 21.4 S4 — the chained withdrawal is EXACT at four wait levels, and w2 is new silicon

§20.6 resolved the chained abort's anchor as cadence-keyed and left the
magnitude measured-without-a-row.  S4 puts the chain length and the wait level
on the same factorial for the first time (`w2` had never been captured):

| waits | chain 2 | chain 3 | chain 4 | non-exact at chain >= 2 |
|---|---|---|---|---|
| 0 | 53-ish | | | **0** |
| 1 | 53 | 38 | 10 | 19 (all prefetch-in-gap) |
| 2 | 53 | 42 | 16 | **0** |
| 3 | 44 | 44 | 25 | **0** |

**325 chain >= 2 cases at w0/w2/w3: zero failures.**  At w1 the 19 failures are
the SAME prefetch-in-gap phenomenon that also hits chain-1 (18 of them are
chain-1), so they are not a chain effect.

**The registered prediction needed restating, and is restated honestly rather
than scored as written.**  §21.0 S4 registered `offset(chain>=2) = +1` — that
was the offset of the model *before* §20.6, and §20.6 already landed the
cadence-keyed anchor.  What S4 therefore measures is whether the LANDED anchor
survives a wait level it was never fitted on, and it does: **w2 is a held-out
cell and the chained withdrawal is cycle-exact there.**

**§20.12 item 4 is closed as far as measurement can close it:** the extra clock
is chain-length-invariant and wait-invariant, confirmed at four wait levels and
three chain lengths.  It remains, as §20.6 said, **a clock without a named ROM
row** — no row is claimed here either.

### 21.5 S2 — the HALT wake, MEASURED; one registered prediction CONFIRMED, one FALSIFIED, and a race found

Registered as **UNMODELLED — MEASURING**, and it stays that way: no offset is
fitted below.

| registered prediction | result |
|---|---|
| 1. a SINGLE sharp threshold `d*` in the delay axis | **CONFIRMED** — `sharp = True` for both forms at both wait levels; below `d*` the chip never drives the HALT status, at and above it always does.  No scatter, no second band |
| 3. the HALT display is 2 clocks whenever driven | **CONFIRMED** — `halt_len = 2` at every delay and both wait levels (and this is the §12.3 reproduction of §21.1) |
| 4. the sweep CROSSES the max, and the two estimates of `d*` agree | **CONFIRMED** — the woken fetch's T1 is flat (floor-bound) below the crossing and then tracks the delay one-for-one above it: at w0, `woke = 158` for `d <= 6` then `152 + d`; at w1, flat then `214 + d`.  That IS §20.1's `dec = max(A + pipe, the clock the part is halted on)`, visible directly |
| 2. `d*(w1) - d*(w0) = +1` | **FALSIFIED — measured +4** (`d* = 4` at w0, `8` at w1, both forms) |

**Clause 2 is a registered FAILURE and is reported as one.**  The diagnosis is
that the prediction was posed in the WRONG COORDINATE, and that is itself the
useful part: `delay` is measured from the anchor's `CODE` T1, and **both** the
anchor clock and the HALT display clock move when the wait level changes, so
`d*` in the delay coordinate measures the difference of two moving points and
has no reason to shift by the pseudo-cycle's single `Tw`.  The HALT display's
own clock is fixed per program and independent of the delay (153 at w0, 219 at
w1, over all 49 delays), which is what makes the threshold sharp.  No
re-derived offset is claimed; the correct coordinate is `A` relative to the
HALT display clock, and stating it is left as the measurement it is.

**And the sweep found something that was not predicted at all.**  AT the
threshold — `d = 8, 9` at w1, i.e. exactly the delays where the wake and the
HALT display race for the status register — the woken fetch's T1 jumps to
**284**, against 225-227 on both sides of it.  A ~57-clock excursion confined
to the two delay cells at the race point, with the acknowledge itself unmoved
(`inta1` = 227 there, in line with its neighbours).  This is the `HALTWAKE`
family's own geometry caught in a directed sweep instead of inferred from a
1,000-row program.  **It is REPORTED, not modelled** — §20.12 item 2 refused a
fitted offset and that refusal stands.  The stimulus that would close it is the
same sweep at finer delay granularity around the race with the full row stream
diffed against the model, which is now cheap: the captures are banked.

*Instrument note, reported not hidden:* `HLT.INT` at w1 produced **0 of 49
goldens** (`implausible final PSW 0` on every delay) from the single fixed
program state the sweep holds constant, while `HLT.RES` produced 49/49 and both
forms produced 49/49 at w0.  The pins-only sweep (which is what §21.5 is scored
on) is unaffected — it uses the directed capture path, and all 196 cells fired.
The missing golden half of that one cell is recorded as a gap.

### 21.6 S5 — A30 IS SETTLED: silicon takes BANK B in emulation mode, and the 14th-decoder-input mechanism is REFUTED

The ledger's own directed capture (`ucsim_provenance.md` §61: *"a contained
program that does `BRKEM`, stays in 8080 mode, and takes an INTR"*), built and
run.  The program is three instructions and a stub: `BRKEM 0x20` at the anchor,
`IVT[0x20]` pointing at an 8080 stub of `FB` (8080 `EI`, since BRKEM clears IE)
followed by 8080 `NOP`s, and the rig asserting INTR at a swept delay.

**The capture does exactly what it was designed to do**, read off the pins with
no model in the loop (`h0_w0_d60`, bus cycles 36-54):

```
36  CODE  0x00506           the BRKEM bytes
37  MEMR  0x00080  \        IVT[0x20] -- the BRKEM vector fetch
38  MEMR  0x00082  /
39  MEMW  0x03efe   ps=5    PSW push        MD=0
40  MEMW  0x03efc   ps=d    CS  push        MD=1   <- the mode bit takes effect
41  MEMW  0x03efa   ps=d    IP  push        MD=1        mid-push-chain
42..47 CODE 0x00800..0x0080a  ps=e  MD=1 IE=1   the 8080 stub, interruptible
48  INTA  ps=e  MD=1 IE=1  \   THE ACKNOWLEDGE
49  INTA  ps=e  MD=1 IE=1  /   -- a TWO-CYCLE PAIR in emulation mode
50  MEMR  0x003fc  \        IVT[0xFF] -- the acknowledged vector
51  MEMR  0x003fe  /
```

**The census, over 2 preparation histories x waits {0,1} x 8 delays x 3 reps:**

| | |
|---|---|
| acknowledges with **MD = 1 on every cycle of the run** | **32** |
| acknowledges with MD = 0 somewhere (VOID by the registered instrument falsifier) | **0** |
| run-length histogram over the MD=1 acknowledges | **{2: 32}** |

Registered target was >= 20 independent MD=1 acknowledges; 32 were taken, and
**not one cell was voided** — the stub kept the part in emulation mode with IE
set through every acknowledge, which is precisely the contamination §61 and
§14.5 named as the reason the earlier evidence did not count.

**VERDICT, against the two registered predictions:**

> **BANK B / FIXED PRIORITY.**  Every emulation-mode acknowledge is a
> **two-cycle pair**.  The emulation-mode-input hypothesis — A30, the 14th input
> to the micro-address decoder — predicts a **SINGLE** acknowledge, and a single
> acknowledge does not occur in 32 of 32 deliberately-produced,
> uncontaminated observations.  **A30's mechanism is REFUTED.**

This moves A30 from `n = 1` incidental datapoint (§14.5) to a directed result
at `n = 32`, and from the ledger's **free choice (EU-semantic)** class to
**MEASURED**.  What is NOT claimed, and is stated so it is not read in: this
refutes the *selection mechanism*, it does not prove bank A is dead silicon —
nothing observable distinguishes "dead" from "never selected", and the ROM rows
`01DC`-`01DF` remain 0/4 executed.  The honest ledger entry is *"silicon takes
bank B in emulation mode; the emulation-mode decoder input is refuted; whether
bank A is reachable at all is unobservable from the bus."*

A cross-reference erratum goes to the functional ledger regardless, because
§(d) already records that `has_brkem` under-reports 8080 excursions and that
A30's "bank A unreached even with 8080 mode live" was evaluated over a set now
known to be too small.  That statement is now superseded by a directed
measurement rather than by a corpus count.

### 21.7 S3 — THE CARD STIMULI WERE NOT RUN, and that is recorded rather than hidden

Registered as three sub-probes (C2's fill ramp, C6/C7's positive-control-first
uRMW, C11's single-source matrix) with a target of 11 GREEN / 0 RED / 0
UNRESOLVED.  **None of the three was run.**  The session's board time went to
S1 (which had to be emitted three times before the instrument was trustworthy,
§21.1), S2, S4 and S5.

`timed_lawcards.py` is therefore **unchanged at 7 GREEN / 0 RED / 4
UNRESOLVED**, and C2/C6/C7/C11 remain stimulus gaps with exactly the booked
probes they had entering the session (`biu_law_cards.md` §A.1).  This follows
the §14.5 precedent for B3: an un-run probe is reported as un-run.  No card was
moved, weakened or scored on a substitute stimulus.

The registered protocol for C6/C7 stands unmodified for whoever runs it — the
**positive control comes FIRST**, and **FAILED-VACUOUS is a reportable outcome,
not a pass**.

### 21.8 Gates (measured, this machine, immediately before the commit)

```
python3 sw/ucsim_check.py --suite tests/v30/v0.1                          # 169000/169000
python3 sw/ucsim_check.py --suite tests/v30/v0.2                          # 347000/347000
python3 sw/ucsim_check.py --suite tests/v30/v0.3                          # 3699998/3699998
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror          # 3125000/3125000
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --residue stale-ea  # 128/128
                                                              # functional total 7,341,126
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all            # 168,997 / 169,000
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1  # 1,200/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3  # 1,200/1,200
python3 sw/check_boot.py --timed 220                                      # MATCHES over 220 rows
python3 sw/timed_scenario.py                                              # 18 PASS, 0 FAIL, 9 SKIP
python3 sw/timed_wvec_gate.py             # count 88/88, digest 88/88, cycles +0.0 %
python3 sw/timed_lawcards.py              # 7 GREEN / 0 RED / 4 UNRESOLVED (S3 not run)
python3 sw/timed_fuzz.py --evt-replay     # REGISTERED 1,272/1,702  EVT 678/1,008
                                          # COMBINED   1,950/2,710
                                                              # --- NEW, this session ---
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1evt --forms all --waits 1  # 1,163/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3evt --forms all --waits 3  # 1,176/1,200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w0evt --forms INT.F3AA --waits 0  # 200/200
python3 sw/timed_gate.py --suite tests/v30/v0.1-w2evt --forms INT.F3AA --waits 2  # 177/200
python3 sw/s10_analyze.py inta --suite tests/v30/v0.1-w1evt                  # the eval+5 law
```

`sw/check_enter_nesting.py` is the VERILATOR/RTL leg (CLAUDE.md) and is NOT in
this set: S10 adds `sw/s10_board.py`, `sw/s10_analyze.py`, captures and golden
tranches only — **no `sim/` source and no model behaviour was changed at any
point in this session** — and the working tree carries unrelated uncommitted
`hdl/` and `sw/` changes from another branch (§21.0.0).

**Monotonicity.** Every standing ratchet is at or above its entry value and
none moved down.  Because no model code was touched, the w0/w1/w3 suites, the
fuzz populations, wvec, boot, scenario and the law cards are unchanged to the
case; the S1/S4 tranches are NEW populations with their own new denominators
and do not enter any existing ratchet.

**Board session log.** One session, socket only (`use_core=False` on every
call), **nothing flashed, no bitstream touched, `safe_flash.sh` and
`v30ctl.py prep` never invoked**.  Single-writer checked before contact — no
foreign `v30run serve` / `v30ctl` locally or on `root@mister-nec`.  Roughly
**12,000 socket captures in ~8.5 minutes of board time** against a 30-minute
budget (the emitted case counts plus their rerolls, at 0.03-0.15 s/case): shakedown 0.7 s; S1 emitted THREE times (mixed-anchor 120 s,
cold-anchor at the inherited divider 97 s, cold-anchor with the divider pinned
97 s) plus ~120 s of divider A/B diagnosis; S4 12 s; S5 6.4 s; S2 35 s;
`s1cells` 7.9 s.  The CUT RULE was never invoked — the population was not cut
and repetitions were not cut.  `board_idle()` run at the end —
**board idle, `use_core=0`, confirmed**.

**Retention.** `sw/testdata/s10/` — `s1-tranche` (24 declared protocol cells,
full per-clock rows + raw 64-bit words, 5 reps each, 6 promoted to both
frequencies), `s2-hltsweep` (196 cells + the pins-only sweep table),
`s5-a30` (32 cells + the observation table), `s1-instrument` (the uncorrected
first emission, retained as the §21.1 evidence).  **`SHA256SUMS` over all 535
files, one per probe directory.**  All 24 S1 protocol cells fired, and all are
pin-identical over their 5 repetitions; one cell (`INT.9D_w1_0`) differs
BETWEEN the two frequencies, which is the §12.1 within-cycle-pulse phenomenon
and is recorded, not scored.

### 21.9 Ledger delta

| | after §20 | after this addendum |
|---|---|---|
| INTA under waits | **SCOPED OUT**, 44 waited `ACK` seeds as data | **CLOSED for the single-instruction population** — M18; 5 of 6 forms 200/200 at w1 AND w3 |
| pin-event goldens | w0 only (2,600) | **+ 2,800 waited**: w1 1,200, w3 1,200, w0evt 200, w2evt 200 |
| the acknowledge pair's geometry | `7` clocks at w0, unexplained above | **`INTA2 T1 = INTA1's completion eval + 5`, 2,339/2,339 at N = 0,1,2,3** (w2 held out) |
| §20.12 item 4, the chained abort's magnitude | measured clock, chain axis confounded | **chain- and wait-invariant over {0,1,2,3} x {2,3,4}; 325 chain>=2 cases at w0/w2/w3 exact.  ROM row still unnamed** |
| A30 | free choice; n = 1 incidental datapoint | **MEASURED, n = 32: silicon takes BANK B in emulation mode; the 14th-decoder-input mechanism REFUTED** |
| the HALT wake geometry | 81 seeds, two named shapes, unmodelled | **swept and measured**: sharp threshold, 2-clock display at all waits, the `max` visible; a **~57-clock excursion AT the race point** found and reported.  Still unmodelled, deliberately |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | **unchanged — S3 NOT RUN** |
| mechanisms | M1-M17, M2r, M5b | **+ M18 (the acknowledge pair rides the completion eval)** |
| instrument | — | **the STICKY CLOCK DIVIDER (§21.1): a rig-integrity hazard in the emission path, caught, two false readings retracted, fixes booked** |
| functional corpus | 7,341,126 | unchanged |
| v0.1 w0 / w1 / w3 | 168,997 / 1,200 / 1,200 | unchanged |
| `timed_fuzz` REG / EVT / COMBINED | 1,272/1,702, 678/1,008, 1,950/2,710 | unchanged, all three |
| victory tranche V0-V5 | V0-V4 PASS, **V5 registered FAILURE** | **UNTOUCHED — V5 remains a registered FAILURE** (no re-score was run, so its bar was not met and no addendum is offered) |

### 21.10 What is left, and the stimulus for each

1. **The prefetch in the acknowledge gap** (§21.3) — 61 of 2,400, exhaustively
   localised, 100 % `CODE`.  The single largest and cleanest open item this
   session produced, and it is an ARBITRATION question in the LC1/LC4 family,
   not an interrupt one.  The stimulus exists and is banked: the 61 cases carry
   their own discriminating pairs at three wait levels.
2. **The HALT-wake race** (§21.5) — the ~57-clock excursion at `d = 8, 9` at
   w1.  Stimulus: the same sweep at finer granularity around the race point
   with full row streams diffed against the model.  Captures are banked; only
   the diff is missing.  **Not modelled — a fitted offset is still refused.**
3. **S3's four law cards** (§21.7) — C2, C6, C7, C11, un-run, with their
   registered protocols intact.  C6/C7's positive-control-first rule and its
   FAILED-VACUOUS outcome stay as written.
4. **The divider-provenance fixes** (§21.1) — pin and stamp `div` in
   `emit_suite.cmd_emit`; leave a known divider in `board_idle()`.  Neither is
   made here.
5. **`HLT.INT` at w1 emitted 0/49 goldens** from the S2 sweep's fixed program
   state (`implausible final PSW 0`).  The pins-only measurement is unaffected;
   the golden half of that cell is a gap.
6. **The whole-program `ACK` family is NOT explained by the acknowledge
   geometry, and that is now established rather than assumed.**  `evtsurvey`
   was re-run over a fresh `timed_fuzz --pop evt --evt-replay --report` and the
   §20.8 taxonomy is **byte-identical**: 330 diverging seeds, 24/330 within 4
   rows of an acknowledge, families `qs/INTA` 86, `bs/INTA` 59, `qs/HALT` 54,
   `bs/HALT` 29.  It could not have moved — **M18 is a CONFIRMATION that the
   model already contained the law, not a change to it**, and no model code was
   touched.  The consequence is the useful part: since the waited acknowledge
   geometry is now measured EXACT on 2,000 directed single-instruction goldens,
   the 44 waited `ACK` seeds must part for some other reason, and §21.3 names
   the leading candidate — a prefetch taking the slot between the two
   acknowledge cycles, which a 1,000-row program has far more opportunity to do
   than a single-instruction golden.  **Testing that candidate against the 44 is
   the cheapest next step in the whole campaign** and it is board-free.
7. The three w0 tails (`0F12`, `C1.6`, `F7.4`) are untouched and unrelated.
