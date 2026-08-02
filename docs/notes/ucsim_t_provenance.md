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

Status: **T0 complete, 2026-08-01.  T1 IN PROGRESS — the w0 timing core exists
and the ratchet is open (see §7).  The T1 exit gate (v0.1 166,800/166,800
cycle-row exact at w0) is NOT met.**

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
| S9 | **No interrupt/INTA timing.** `timed-run` runs instructions only; the pin-event replay that `case_runner` performs is not implemented in the timed path, so `INT.* / NMI.* / HLT.* / POLL.*` pseudo-forms have no timed arch result. | Scope exclusion inherited from the RTL campaign: interrupt/INTA timing under waits stays OUT of every timed gate until measured. | T4 (board block may open it) |
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
```

**MASS SWEEP — OWED.**  `tests/v30/v0.3` and `tests/v30/v20suite` (the ~7.3M
functional sweep) were launched on the committed binary but their result could
not be OBSERVED in the session that produced this commit: the machine's `/tmp`
tmpfs hit its quota, which broke the agent's command channel (`g++`: "error
writing to /tmp/ccXXXX.s: Disk quota exceeded"; builds were completed by
pointing `TMPDIR` at `~/.cache/ucsimt-tmp`, but the result-reporting path stayed
broken).  **Re-run both before relying on this commit.**  The risk is judged low
and the reason is structural, not statistical: every edit to the SHARED
`exec_impl.h` / `loader_impl.h` bodies is either a pure counter (`row_clocks`,
`rloop_iters`) or a call to one of the five new Bus methods, and all five are
`{}` on `sim::Biu` — so `CpuT<Biu>` cannot change behaviour, and v0.1 + v0.2
(516,000 cases) confirm it did not.

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
