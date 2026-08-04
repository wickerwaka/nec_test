# The FSM core — ARCHIVE RECORD, 2026-08-04

**Disposition: ARCHIVED.**  Taken by the campaign owner on 2026-08-04, from the
evidence laid out both ways in
`docs/notes/ucore_campaign_verdict_2026-08-04.md` §(e) item 1.  It is the third
option that verdict named — *"keep the RTL, delete the claim"* — and it is
recorded here so the repo stops asserting numbers a corrected comparator no
longer supports, while the A/B capability and every line of history stay intact.

**Nothing was moved and nothing was deleted.**  `hdl/rtl/core/` is where it has
always been, `--core fsm` still builds and still runs, `hdl/files.qip` still
describes its Quartus build, and its bitstream sha is recorded below.  What
changed is the *default* and the *claim*, not the artifact.

---

## 1. WHAT IT IS

`hdl/rtl/core/` — `v30_core.sv`, `v30_biu.sv`, `v30_eu.sv`, `v30_ss_pkg.sv`,
plus `race_law.svh` and `int9d_race.hex`.

A cycle-accurate NEC V30 (µPD70116) max-mode core, **written directly against
golden traces captured from the socketed part** — no intermediate reference
model, by the explicit project decision of 2026-07-11 (`ROADMAP.md`,
*"Decisions (2026-07-11) — No intermediate software reference model"*).  Its
mechanisms were fitted, opcode family by opcode family, to what a comparator
said about a capture.  That method is the thing this archive is really about:
it is the control arm of the experiment the `ucore` campaign ran, and the only
controlled A/B of a trace-fitted core against a mechanism-derived one that this
project will ever get.

Built by **campaigns 3 and 4** (`ROADMAP.md` §Campaign 3, §Campaign 4) and
extended through the class-5, race-ROM, RR2, opcode-suite, mass-fuzz and
`biu-rebuild` campaigns.

---

## 2. WHAT IT ACHIEVED — the record, stated as it was earned

* **The original FIRST LIGHT, 2026-07-13** (`ROADMAP.md` Campaign 4 block C).
  The first time a core written in this repo ran inside the FPGA behind the
  same `nec_bus` interface as the socketed part and produced a boot capture
  that MATCHED the chip over 800 rows.  Every "first light" figure quoted since
  — including the ucore's own 800/800 ×3 — is measured by an instrument this
  core caused to exist.
* **Campaign 3 closure, 2026-07-13**: **155,500 / 155,500 cycle-exact and
  155,500 / 155,500 architecturally exact over all 311 documented-form
  tranches**, wait-state suites 2 × 1,200/1,200.
* **The campaign-3 exit gate SATISFIED**: 500/500 consecutive fuzz sequences
  (fz600–fz1099) on the real board, chip-vs-core full-trace diff, zero
  divergences, zero QS flickers.
* **The v0.1 golden record: 169,000 / 169,000**, cycles and architecture, on
  the comparator it was graded with for its entire life.  §5 below states
  precisely what that number is and is not today.
* **A clean save-state map** — `ss_lint --core fsm` **rc=0**, 203 addresses,
  181 architectural flops, **0 UNMAPPED** (re-verified on this tree,
  2026-08-04).
* **It predicted the interrupt boundary from the pins alone**, which is what
  told §36 / Codex C5 that the model's `max` term was a replay artefact and not
  a mechanism.  *A second implementation is a falsifier generator*, and this one
  generated falsifiers that changed the ledger.
* **It was the instrument that made the `ucore` campaign meaningful.**  Every
  "the ucore is right" sentence in the verdict is stronger because a
  differently-built core disagreed somewhere and the golden adjudicated.

---

## 3. WHY IT IS ARCHIVED — the four reasons, each with its evidence

### 3.1 The priority axis: 59/178 against 176/178, from the same HEAD

`ucore_campaign_verdict_2026-08-04.md` §(c), ledger §52.6–§52.8.  On the §48.4
priority tranche — 200 fresh stratified `wrand` programs, frozen and committed
before the first capture, 178 scored — **in fabric**:

| | FSM core | ucore |
|---|---|---|
| priority tranche, IN FABRIC | **59 / 178 (33.1 %)** | **176 / 178 (98.9 %)** |
| the same, under Verilator | 59 / 178 | 176 / 178 |
| fabric ↔ Verilator pairwise | 200 / 200 identical | 200 / 200 identical |
| `timed_wvec_gate` silicon freeze | **71 / 88** | 88 / 88, +0.0 % |
| registered fuzz bank (1,702 seeds) | **18 / 1,702 (1.1 %)** | 1,483 / 1,702 |

Both bitstreams were built from the same HEAD and flashed in the same session,
so this is a controlled comparison and not an artefact of staleness — that
control is §51.8b, closed by FLASH #2.

**Arbitrary-wait cycle accuracy is this project's #1 priority** (standing user
directive, memory `wait-state-cycle-accuracy-priority`).  The FSM's 71/88 on the
wvec freeze is **22/22 at `ws0:wmax0` and 17 misses spread over the three WAITED
configs, with the access COUNT matching the chip in all 88 cells** — its deficit
is pure CADENCE on the wait axis.  That is the axis a trace-fitted core cannot
generalise on, because there is no trace to fit for an arbitrary wait sequence.

### 3.2 It regressed 104 seeds and no standing gate saw it

Ledger §52.8; verdict §(c) *"THE FSM REGRESSION FINDING"*.

The **2026-07-30 FSM bitstream scores 163/178** on the priority tranche.
**HEAD's FSM RTL scores 59/178** — in fabric and in Verilator identically, so it
is not a bitstream artefact.  Scored pairwise, the stale bitstream against
HEAD's Verilator model is 76/200 while both same-HEAD pairs are 200/200.

**Why no gate sees it:** the standing ladder runs `check_core --core fsm` on
**four opcodes** (`88,9D,INT.9D,INT.F3AA`), and the FSM's registered fuzz figure
(18/1,702) is so low that a further loss is invisible there.

*Falsifier (carried forward, NOT run):* a bisect between the 2026-07-30 build
and HEAD that does **not** move this number.  Not diagnosed; nothing was changed
to chase it.  **A reference that can silently regress is not a reference** — this
is the single strongest reason for the archive disposition.

### 3.3 It carries the F51 HALT defect, present and unfixed

Ledger §54, §54.1; `CLAUDE.md`'s comparator note.

`v30_biu.sv:1914` drives `{4'h0, fetch_phys[15:0] - 16'd2}` and `ad_oe_ps`
explicitly excludes `cur_kind != K_HALT`, so the core drives **nothing** on
A19-16 across a HALT display and its T1 — where the goldens carry
`data_ps(2)` = `{md, ie, CS}`: **`6` in all 200 `HLT.INT`, `2` in all 200
`HLT.RES`, `{2,6}` in `HLT.NMI`**, and never `0`.

`tb_v30_core.sv`'s composed-AD mask substituted the *retained* nibble there, and
the retained nibble is the previous cycle's PS on a CS fetch with the same IE —
so it read correct **by construction and not by correctness**.  In fabric there
is no pad retention and it does not.

The mask was removed at U5 (engine-neutral: it names no core signal), the ucore
was fixed (F51), and **the FSM core was not** — the campaign does not touch the
frozen core's RTL because its flashed A/B bitstream is built from HEAD and §52.8
established it must stay that way.  **The defect predates the instrument change
by every commit in the repo.**  It is a ONE-LINE fix in `v30_biu.sv`'s
`ad_o` / `ad_oe_ps` and it is deliberately **not taken**.

### 3.4 The rail forest the mechanism ledger superseded

The standing SIMPLICITY directive (`CLAUDE.md`, user directive 2026-08-01) names
*"a large fitted table, a many-cased rule, or a per-opcode special case"* as a
signal of misunderstanding.  The FSM core carries, by name: the **class-5
unified law**, **`race_law.svh`** (a generated race table with its own
regeneration gate), the **IRET race arm**, **two `lpm_divide` instances**, and
**per-opcode timing exceptions**.  The ucore has **zero** per-opcode timing
exceptions ("grep for one" stays true), 0 `lpm_divide`, and **4,785** RTL lines
against the FSM's 5,919.

Every one of those rails was a correct local fit to a real capture.  That is the
finding, not an accusation: *trace-fitting produces rails, and rails do not
generalise off the traces they were fitted to.*

---

## 4. THE MAINTENANCE ARGUMENT, stated once

Keeping it *as a live reference* costs a re-flash whenever HEAD moves, or the
A/B is uncontrolled — measured, §51.8b.  Archiving it costs nothing and keeps
the falsifier-generator value: the RTL is here, the comparator leg is here, and
a future session can rebuild and re-flash it in one command (§6).

---

## 5. WHAT REMAINS VALID — read this before quoting any FSM number

**Its w0 golden record was REAL and it stands.**  The FSM core is
**169,000 / 169,000** on `tests/v30/v0.1`, cycles and architecture, **on the
comparator it was graded with for its whole life**, and 155,500/155,500 over the
311 documented-form tranches before that.  Nothing in this archive retracts a
measurement.

**And the corrected comparator reads it differently, and BOTH numbers are the
record.**  After U5 removed the composed-AD mask (§3.3 above):

| gate | as graded 2026-07-13 → 2026-08-03 | **on the corrected comparator (U5)** |
|---|---|---|
| `check_core --core fsm --opcodes all --cases 0` | 169,000 / 169,000 | **168,400 / 169,000** |
| the four HLT delay sweeps | 216 / 283 (measured for the first time at U5) | **0/97, 4/95, 5/46, 7/45 = 16 / 283** |

The 600-case delta is **exactly** the `HLT.INT` / `HLT.RES` / `HLT.NMI` cases,
0/600.  **Nothing was made worse; something was made visible.**  The correct way
to cite the figure is with the comparator named.

**Also valid, and not affected by any of the above:**

* every historical capture the FSM core produced or adjudicated —
  `sw/testdata/**` is untouched by this archive;
* its **save-state map** (`v30_ss_pkg.sv`, 203 addresses / 181 flops /
  0 UNMAPPED) and the `ss_lint --core fsm` leg, re-verified rc=0 on this tree;
* the **FSM-specific gates** listed in `docs/notes/standing_gates.md` under
  *"ARCHIVED — on demand"*: `check_race_law`, `check_ff_t4`, `check_lc6_gate`,
  `check_enter_nesting`, `check_fuzz_bank`, `prefix_clear_lint`, `ea_step_lint`,
  `check_mod3_illegal`.  They still pass; they now gate an archived artifact, so
  they are run **on demand** (before any FSM re-activation) rather than as part
  of the standing set.  `check_fuzz_bank` in particular is the load-bearing
  instrument-change control (§57.2: 3,242 banked seeds, **worse 0**) and its
  value does not depend on the disposition;
* the two per-core-neutral lints (`ss_lint`, `optable --selfcheck`) and the
  generation-stack gates (`make -C sim test`, `pla3_check`,
  `check_ucore_tables`) — never FSM-specific;
* **the A/B harness itself.**  `system_large` still carries both cores'
  integration path, `gen_ucore_qsf.py --check` still gates that the two
  bitstreams differ by the core and nothing else, and `check_ab_sim.py --core
  fsm` is still 187 rows MATCH.

---

## 6. RE-ACTIVATION PROCEDURE

Nothing below needs a file to move.  All of it works on this tree today.

**Offline (Verilator), one command:**

```
python3 sw/check_core.py --core fsm --opcodes all --cases 0
```

`--core fsm` remains a first-class leg of `check_core.py` (and of
`ulockstep.py`, `timed_fuzz.py`, `timed_wvec_gate.py`, `timed_enter_replay.py`,
`timed_ins_replay.py`, `check_boot.py`, `check_ab_sim.py`, `ss_lint.py`).  Since
2026-08-04 it is **no longer the default** — pass it explicitly.  The build
swaps only the RTL file list, the include path, the `obj_dir` and one define
(`sw/check_core.py`, the "engine selection" block at `:46`): FSM builds into
`hdl/tb/obj_dir/` with
`-DV30_FSM_PROBES`, the ucore into `hdl/tb/obj_dir_ucore/` without it.

**The FSM-specific gate set, before trusting any FSM result:**

```
python3 sw/check_race_law.py
python3 sw/check_ff_t4.py
python3 sw/check_lc6_gate.py
python3 sw/check_enter_nesting.py
python3 sw/check_mod3_illegal.py
python3 sw/prefix_clear_lint.py
python3 sw/ea_step_lint.py
python3 sw/ss_lint.py --core fsm
python3 sw/check_fuzz_bank.py            # add --strict for the mainline config
```

**Synthesis / fabric:**

* Quartus project `nec_test`, file list `hdl/files.qip` — this is the **FSM**
  build (`rtl/core/v30_ss_pkg.sv`, `v30_core.sv`, `v30_biu.sv`, `v30_eu.sv`,
  `SEARCH_PATH rtl/core`).  The ucore build is the separate revision
  `nec_test_ucore` with `hdl/files_ucore.qip`; `sw/gen_ucore_qsf.py --check`
  gates that `hdl/nec_test_ucore.qsf` stays a faithful derivative of
  `nec_test.qsf`, i.e. that the two A/B bitstreams differ by the CORE and
  nothing else.  **Do not merge the two file lists** — `files_ucore.qip:14`
  records that exactly one of the two `ss_pkg` files may be in a build.
* `quartus_sh --flow compile nec_test -c nec_test` produces the FSM bitstream.
* **The last FSM bitstream built from HEAD** (FLASH #2, 2026-08-04T04:06:15Z,
  `sw/testdata/flash_log.jsonl`):

  ```
  nec_test.sof  sha256 a4533dfef09b896ebb08763658b053e7cfb0946877b1ce43831fbd7b89f500e2
  ```

  It is **not** on the board — FLASH #3 put the ucore bitstream
  (`924c4a61e0ad235e6257695a775d86cc51735ebba0cf9cf5f9ffb651bcc5105d`) there and
  left it, §56.5.  Re-flashing is `sw/safe_flash.sh` with its VERIFY leg, under
  the standing board discipline (single-writer check first, pre-register before
  board contact, `board_idle` + verify after).
* **§51.8b is the standing warning**: an FSM bitstream that is not built from
  the same HEAD as the ucore's makes the A/B uncontrolled.  Its 62/178 was
  entirely a stale bitstream.  If the A/B is re-run, **build and flash both from
  one HEAD**.

**Before re-activating it as a REFERENCE (as opposed to running it once):**
the two open FSM findings must be dealt with first, or the reference is not one
— §3.2's 104-seed regression bisect, and §3.3's one-line HALT pad-drive fix.
Both are written down with their falsifiers and neither is started.

---

## 7. WHERE THE REST OF IT IS WRITTEN DOWN

| | |
|---|---|
| the disposition evidence, both ways | `docs/notes/ucore_campaign_verdict_2026-08-04.md` §(c), §(e) item 1 |
| the A/B numbers and the regression | `docs/notes/ucore_provenance.md` §52.6–§52.8 |
| F51 and the comparator change | `docs/notes/ucore_provenance.md` §53–§54, `CLAUDE.md` |
| the fabric legs | `docs/notes/ucore_provenance.md` §55–§56 |
| campaigns 3 and 4, as they were run | `ROADMAP.md`, `docs/notes/closure_checkpoint.md` |
| the class-5 / race-ROM / RR2 rails | `docs/notes/class5_campaign_record.md`, `docs/notes/race_rom_*.md` |
| what the ucore does NOT yet do | `docs/notes/ucore_gaps_2026-08-04.md` |
