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
observable settles it — the `F` and `S` pops are on the SAME ABSOLUTE CLOCKS in
chip and sim.  **The EU is exactly where the model puts it.  The prefetcher is
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

**Board session log.**  One session, ~15 minutes of board time in total across
five probes (the persistent serve runner turns a 4,063-clock socket capture
into ~0.3 s, so the budget was never the constraint).  Single-writer checked
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
