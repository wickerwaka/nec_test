# Standing gate set (nec_test)

The regression gates re-run after any RTL or generation-stack change. All are
board-free (cached chip refs + Verilator TB) unless noted.

**THE STANDING CORE IS `ucore` (`hdl/rtl/ucore/`) SINCE 2026-08-04.** The
trace-fitted FSM core (`hdl/rtl/core/`) was ARCHIVED on that date — see
`docs/notes/fsm_core_archive_2026-08-04.md` and the disposition evidence in
`docs/notes/ucore_campaign_verdict_2026-08-04.md` §(e) item 1. Its gates did not
disappear; they moved to the ON-DEMAND section below, because **they gate an
archived artifact.** `--core fsm` still builds and still runs.

`sw/check_core.py`, `sw/check_boot.py`, `sw/check_ab_sim.py`, `sw/ss_lint.py`
and `sw/ss_flopcensus.py` **now default to `--core ucore`** (they defaulted to
`fsm` before 2026-08-04). The `timed_*` tools still default to `--core sim`, the
C++ reference model — that is the spec engine and it did not change.

---

## THE RECEIPT REQUIREMENT (SM3 sitting 14, 2026-08-05)

**Every gate marked ⧉ below refuses to run against a Verilator binary that does
not have a receipt matching THIS tree.** The layer is `sw/artifact.py`, the spec
is `docs/notes/artifact_receipt_layer.md`, the migration record is
`ucore_provenance.md` §75, and its own non-vacuity proof is
`python3 sw/test_artifact.py` (**45/45**, and it must stay green — a freshness
layer that has never rejected anything is this document's own vacuous-gate
pattern one level down).

* **`sw/check_core.py` is the SINGLE PRODUCER** of `Vtb_v30_core`.
  `check_core.recipe(core)` declares what the binary is a function of — the RTL,
  the `.svh` includes, **and the `$readmemh` tables `ucrom.hex` / `ucdecode.hex`,
  which the compiler never opens and the ucore's entire architecture lives in**
  (§75.6a). `build()` rebuilds only when the CONTENT KEY moves, then asserts the
  postcondition.
* **Every other migrated gate asserts, and does not build.** A mismatch is a
  hard error with two hashes in it; deciding to rebuild is the agent's job.
  The fix is `python3 sw/check_core.py --build --core <core>`.
* **What this retires**: §C's standing warning *"rebuild the FSM TB before
  quoting `check_fuzz_bank` until that plumbing is fixed"*. **That is the
  plumbing, and it is fixed** — `check_seq.run_tb` now resolves through
  `check_core.recipe("fsm")`, so `check_fuzz_bank`, `check_mod3_illegal` and
  `check_enter_nesting` inherit it.
* **THE C++ MODEL IS COVERED TOO SINCE SM3 SITTING 15 (§76.A).**
  `sw/simbin.py` is the SINGLE PRODUCER of the model, exactly as
  `sw/check_core.py` is of `Vtb_v30_core`. **The binary is
  `sim/build/v30sim`**, not `sim/v30sim` — `build()` promotes by renaming its
  workdir, and with the artifact in `sim/` the workdir would have been the
  source tree. **`sim/v30sim` is on no scorer's path any more.** Rebuild with
  `python3 sw/simbin.py --build`; assert without building with
  `--require`; print the id with `--id`.
  **`docs/V20BITS.TXT` IS A DECLARED INPUT** (E-1): the model takes the
  microcode ROM as `argv[1]` at RUN time, so under a "files the command reads"
  rule the ROM the whole model executes would have sat outside the identity of
  every `--core sim` number ever scored. Measured consequence, and it is the
  argument for E-1 in one line: perturbing one byte of the ROM does **not**
  move the compiled bytes (`cd2735e645a1cc35…` either way) and **does** move
  the receipt, so a scorer bound to bytes alone could never have seen it.
* **What it does NOT cover**: `ucore_provenance.md` §75.7's U2-U8 — the flash
  log, the table generator, the golden suites (INV-1), three archived FSM
  gates, the measurement tools, the board legs and `ss_lint`. **Read that list
  before assuming a gate is covered.**
* **A/B pairs are checkable**: `python3 sw/receipt_diff.py A B [--expect-command]`
  prints the symmetric difference of two receipts' inputs and exits non-zero if
  the delta is not the intended axis.

---

## A. THE STANDING SET — core-neutral

| Gate | Command | Proves |
|---|---|---|
| ROM disasm ⧉ | `python3 sw/simbin.py --disasm` | the disassembly is byte-exact vs `V20UC.TXT`, **1,285 rows**, on the RECEIPTED binary, printing its receipt id.  (`make -C sim test` is the same diff on an unreceipted `sim/v30sim` built by mtime; kept as a developer convenience, not quoted as this gate) |
| PLA | `python3 sw/pla3_check.py` | 21 PLA checks |
| check_ucore_tables (G0) | `python3 sw/check_ucore_tables.py` | the generated `hdl/rtl/ucore/` tables byte-match `sim/`: 1028 ROM rows + 8192 micro-addresses + 768 PLA entries = **9,988**, on an INDEPENDENT re-parse and on the emitted artifacts (`ucore_provenance.md` §4) |
| optable selfcheck | `python3 sw/optable.py --selfcheck` | the opcode table agrees with fuzz_cov + instructions.json |
| fuzz_campaign lint | `python3 sw/fuzz_campaign.py lint --report-every 5000` | the soup/raw generators never emit a chip-wedging image.  **GREEN, SM3 s12: `LINT PASS: soup hits=0 compose_err=0; raw hits=0 compose_err=0` over 10,000 soup + 100,000 raw seeds.**  §72.7a's NOT-RUN debt is DISCHARGED and the "hang" is EXPLAINED, not fixed: `--report-every` defaults to **0**, so the tool prints NOTHING until each phase ends, and the raw phase is 100,000 seeds at ~69/s ≈ **25 minutes**.  The `do_wait` / 0 % CPU process s11 observed was the WRAPPER SHELL; the worker sits at 99.8 % CPU throughout.  **Pass `--report-every` or it will look hung again** (`ucore_provenance.md` §73.10) |
| test_fuzz_classify / test_fuzz_accept | `python3 sw/test_fuzz_{classify,accept}.py` | the verdict tree + acceptance rules (offline) |
| gen_ucore_qsf | `python3 sw/gen_ucore_qsf.py --check` | `hdl/nec_test_ucore.qsf` is a faithful derivative of `hdl/nec_test.qsf` — the two A/B bitstreams differ by the CORE and nothing else |

### THE QUARTUS LEG (G6) — **NEW, SM3 SITTING 13.  IT IS TRIGGERED, NOT ALWAYS-ON.**

`python3 sw/quartus_gate.py`

**Why it exists**: `ucore_provenance.md` §73.1. Sitting 11 landed RTL, ran no
synthesis — which was ALLOWED, because no gate demanded one — and the DEFAULT
`nec_test_ucore` build was later measured at **19.42 MHz** with 20,000 failing
paths. **Nothing in the tree saw it, because the standing set is board-free by
design and had no Quartus leg at all.** That is this document's own vacuous-gate
pattern by ABSENCE rather than by blindness.

**What it does**: `gen_ucore_qsf --check` first (E1 — it must run BEFORE the
build, because Quartus REWRITES the .qsf it compiles, §70.7), then **ONE clean
CONTROL/DEFAULT build from a deleted `db`/`incremental_db`** — macro OFF, the
configuration every bitstream is derived from — and it gates **only** the
registered G6 essentials:

| | bar |
|---|---|
| **E1** | `gen_ucore_qsf --check` green |
| **E2** | 0 compile errors, every stage `Successful` |
| **E3** | `divclk` Fmax **≥ 32 MHz** |
| **E4** | worst setup slack **> 0** on every domain |
| **E5** | TNS **0.000**, setup **AND** hold, every domain |

ALMs, latches, `lpm_divide` and the register counts are **RECORDED in the
receipt and are NOT bars** — a gate that asserts a resource number fails on
noise, and one that records it lets the next agent see drift.

**WHEN IT TRIGGERS.** Any commit touching `hdl/rtl/ucore/**`, the shared
integration RTL (`hdl/rtl/system_large.sv`, `nec_bus.sv`, `nec_test.sv`,
`hdl/sys/**`), `hdl/files_ucore.qip`, either `.qsf`, `nec_test.sdc`, or the
generated ucore tables. **Its receipt is REQUIRED before any RTL landing is
accepted or any bitstream is flashed.** The FAST LADDER does not wait on it —
Verilator, the goldens and the fuzz bank run as they do today; the RTL
PROMOTION does. That is the line where the ~9-minute cost is paid once.

**THE RECEIPT** (`--receipt`, default `hdl/output_files_ucore/quartus_gate.json`)
carries the input manifest hash over **88 files**, the tool version, the exact
command, the parsed figures and the verdict, to
`docs/notes/artifact_receipt_layer.md` §3's schema. Two receipts differ ONLY in
what the builds differ in — the layer's §5 delta manifest, already load-bearing:
HEAD vs `144e67416b` differ in **exactly one file, `rtl/ucore/v30u_eu.sv`**, which
is what makes the comparison below readable at all.

> **SM3 sitting 14**: this receipt is now written by the SHARED writer
> (`sw/artifact.py`), so `sw/receipt_diff.py` reads it and a copy is appended to
> `sw/testdata/receipts/quartus_bitstream.jsonl` — which matters because the
> gate's own next clean build deletes `hdl/output_files_ucore/`. Every s13 key
> is retained and still means what it meant; the §3 keys (`schema`, `id`,
> `kind`, `inputs`, `outputs`, `command`, `started`/`completed`) are ADDED beside
> them, and `outputs` now carries the `.sof` / `.rbf` hashes. **One thing moved**:
> the manifest is keyed on REPO-relative names, so the file above reads
> `hdl/rtl/ucore/v30u_eu.sv` and the manifest `sha256` changed. The file COUNT
> and the discovery rule are unchanged at **88**, and nothing consumed the old
> hash (`ucore_provenance.md` §75.6b).

> **SM3 sitting 16 (2026-08-05) — the leg RAN on F53 and is GREEN.**  One clean
> CONTROL/DEFAULT build, compile rc 0 in 523 s: **E1 PASS · E2 PASS** (0 errors,
> map/fit/asm all Successful) **· E3 45.57 MHz** (bar ≥ 32) **· E4 +6.974 ns ·
> E5 TNS 0.000 on all four domains, setup AND hold.**  RECORDED, not barred:
> **ALMs 11,058 / 41,910 (26 %)**, 6,111 fit registers, **0 latches, 0
> `lpm_divide`**.  Receipt **`02a71f69e4d58df1…`**, input manifest 88 files
> `1a20fd543311a4cb…`.  The receipt records the tree as `aa31eb2f0f-dirty`; the
> dirt was docs and not-yet-committed test data, and **`hdl/` was byte-identical
> to `aa31eb2f0f` and is byte-identical to HEAD**.  **A bitstream was produced
> and NOT flashed** (`nec_test_ucore.sof f2c1b471ceb58ded…`, `.rbf
> 6dbbc687c3c6ca3d…`); the board still carries FLASH #6, which predates F53.
> §74.4 still governs: one green build is not closure.

> **SM3 sitting 17 (2026-08-05) — the leg RAN on F54 and is GREEN.**  One clean
> CONTROL/DEFAULT build, compile rc 0 in 524 s: **E1 PASS · E2 PASS** (0 errors,
> map/fit/asm all Successful) **· E3 45.49 MHz** (bar ≥ 32) **· E4 +9.146 ns ·
> E5 TNS 0.000 on all four domains, setup AND hold.**  RECORDED, not barred:
> **ALMs 11,126 / 41,910 (27 %)** — **+68** on F53's 11,058, which is what one
> added mux term costs — 6,110 fit registers, **0 latches, 0 `lpm_divide`**.
> Receipt **`d7e27e7c4fe810bc…`**, input manifest 88 files `567b11fffd6414a6…`,
> tree `d6e2d852cb-dirty` (the dirt is F54's one `hdl/` file plus docs).
> **A bitstream was produced and NOT flashed** (`nec_test_ucore.sof
> b4e818965e2bee59…`, `.rbf fc3cb1816ff3b007…`); the board still carries
> FLASH #6, which predates both F53 and F54.  §74.4 still governs.

**NON-VACUITY — PROVED, AND *NOT* THE WAY IT WAS REGISTERED.**
`sm3_s13_prereg_2026-08-05.md` §3 registered **Q2: the gate goes RED on a
worktree of `144e67416b`, reproducing 19.42 MHz.** ***IT DID NOT.*** That build
came back **45.91 MHz / +6.489 / TNS 0.000 / PASS**, and **Q2 IS A REGISTERED
FAILURE, reported and not restated.** Non-vacuity is instead proved on the
**PRESERVED 19.42 MHz REPORT SET ITSELF** — sitting 12's `ctrl_clean`, a real
historical artifact retained under §73.13 — where the gate exits **1** and goes
**RED at E3 (19.42), E4 (−20.254) and E5 (TNS −13,129.815)**. The scoring is
non-vacuous on the exact state it was built to catch.

> ⚠ **AND THE Q2 RESULT IS ITSELF A FINDING ABOUT THIS GATE AND ABOUT §73.
> READ `ucore_provenance.md` §74.4 BEFORE QUOTING ANY SINGLE-BUILD Fmax.**
> Four control builds of two trees that differ in one file:
> | tree | `.qsf` used | Fmax |
> |---|---|---|
> | `144e67416b` | materialised (s12) | **19.42** |
> | `144e67416b` | generated (s13) | **45.91** |
> | form 2 / HEAD | materialised (s12) | **45.89** |
> | form 2 / HEAD | generated (s13) | **43.59** |
> **The DEFAULT build's Fmax is not a function of the RTL alone**, and §73.1's
> "reproduced to the digit from a DELETED `db`" established repeatability of one
> draw, not determinism. **A single green build does not establish closure on
> this design.** The gate's value is that it makes a 26 MHz swing VISIBLE at the
> landing rather than three sittings later; it is not a proof of closure.

## B. THE STANDING SET — the `ucore`

Standing ratchets. Monotone: never re-scored downward without a loud, itemised
entry. Figures are `ucore_provenance.md` §54.4's, re-run 2026-08-04.

| Gate | Command | Standing number |
|---|---|---|
| **G3** ⧉ | `python3 sw/check_core.py --opcodes all --cases 0` | **169,000 / 169,000** (cycles AND arch) |
| wait axis | `check_core.py --suite-dir tests/v30/v0.1-w1 --waits 1` / `-w3 --waits 3` | 1,200 / 1,200 each |
| `EB` at w1 | `… --suite-dir tests/v30/v0.1-w1 --opcodes EB --waits 1` | 200 / 200 |
| the four `evt` cells | `… --suite-dir tests/v30/v0.1-w{0,1,2,3}evt --waits {0,1,2,3}` | 200 / 1,200 / 200 / 1,200 |
| `w1evt-biased` (preserved) | `… --suite-dir tests/v30/v0.1-w1evt-biased --waits 1` | 1,200 / 1,200 |
| **block I/O (INM/OUTM)** | `… --suite-dir tests/v30/v0.3 --opcodes 6C,6D,6E,6F,F26C,F26D,F26E,F26F,F36C,F36D,F36E,F36F,646C,646D,646E,646F,656C,656D,656E,656F,26.6E,2E.6F,36.6E --cases 0` | **229,999 / 229,999** cycles AND arch, 1 documented pre-existing excluded (`646F/[8988]`).  *First measured against the ucore 2026-08-04.*  This is the ONLY gate that reaches 6C-6F — `v0.1` has none, and `timed_ins_replay`'s 1,312/2,624 is the bit-field INS `0F 31`/`0F 39`, not block I/O |
| f4a boundary battery | `… --suite-dir tests/v30/f4a_boundary --cases 0 --waits 0` | **160 / 160** — the EA FFFF→0000 wrap consumers.  *First measured against the ucore 2026-08-04, at the default flip; identical to the FSM core's 160/160* |
| f0lock tranche | `… --suite-dir tests/v30/f0lock_tranche --cases 0 --waits 0` | **400 / 400** — *same provenance as the row above* |
| boot march ⧉ | `python3 sw/check_boot.py --timed 220` and `--timed 400` | MATCH / MATCH |
| lockstep vs the model ⧉ | `python3 sw/ulockstep.py --golden all --cases 50` | **17,350 / 17,350** (`--suite --waits 0,1,2,3` = ALL SCENARIOS LOCKSTEP) |
| wvec silicon freeze ⧉ | `python3 sw/timed_wvec_gate.py --core ucore` | 88 / 88, **+0.0 %** |
| ENTER replay ⧉ | `python3 sw/timed_enter_replay.py --core ucore` | 154 / 154 ×5 |
| INS replay ⧉ | `python3 sw/timed_ins_replay.py --core ucore --raw` | 1,312 / 1,312 and 2,624 / 2,624 |
| the registered fuzz bank ⧉ | `python3 sw/timed_fuzz.py --core ucore --evt-replay` | REGISTERED **1,490 / 1,702**; EVT **918 / 1,008**; COMBINED **2,408 / 2,710** (EVT/COMBINED RAISED by FIVE seeds at **SM3 sitting 21** by **F57**, `ucore_provenance.md` §82.3 — `mc1/1383`, `mc2/594`, `mc2/1052`, `mc2/1068`, `mc2/3530`, and the MODEL gained the SAME FIVE, which is that landing's same-mechanism proof; REGISTERED did not move, to the seed.  It was 913 / 2,403 (EVT/COMBINED RAISED by ONE seed at SM3 sitting 16 by F53, `ucore_provenance.md` §77.G); `INVALIDATED` **0**; `BOUND WARNINGS` 5, `ENGINE ABORTS` 0; denominators 2,710 scored / 532 `OPEN_BUS`.  **INV-1 IS CLOSED (SM2, 2026-08-04): the 760 poisoned EVT seeds were RE-CAPTURED on FLASH #4 at their banked hold of 300, and the full 1,008-seed column is a gate again** (`docs/notes/invalidation_ledger.md` §CLOSURE, `ucore_provenance.md` §59.7.7).  This figure has now been registered three times and every move is itemised: `192/1,008` as banked (STRUCK — rig-poisoned), `170/248` on the un-poisoned sub-population (SM1's interim gate, still true of those 248), **468/1,008 on the rebuilt population**, and **906/1,008** once H1 landed in the ucore (**SM3 sitting 3, 2026-08-04**, `ucore_provenance.md` §62 — the re-entry acknowledge's recognition floor, ONE register, +438 seeds).  REGISTERED has not moved through any of it, to the seed — until **SM3 sitting 6**, which RAISED it **1,483 -> 1,490** by fixing a TESTBENCH defect, not an engine: `tb_v30_core.sv` committed `IOW` cycles into `mem[]`, so an I/O write to port P corrupted memory at address P for the RTL legs only (`ucore_provenance.md` §66.3 / §67.1).  EVT moved **906 -> 908** with it and **-> 910** with F43, and **-> 912** at **SM3 sitting 11** (`ucore_provenance.md` §72 — the floor's arm becomes PSW.IE's rising edge, which DELETES five BIU flops; the two seeds gained are `mc1/2672` and `mc1/356`, and the model gained exactly the same two). |
| the b2 victory tranche ⧉ | `python3 sw/timed_fuzz.py --core ucore --seeddir sw/testdata/t4/b2-tranche/seeds` | **172 / 188** (RAISED from 171 at SM3 sitting 6 by the same TB fix, §67.1) — V5 is a standing REGISTERED FAILURE, not to be re-opened |
| save-state map | `python3 sw/ss_lint.py` | rc=0; **217 addresses, 200 flops, 0 UNMAPPED, `SS_VERSION` 0x85** (SM3 **s21 / F56**: `pf_land` is DELETED — M6 is refuted by its own firing census — and `SSA_B_PF_LAND` / `9'h038` leaves the map.  **It is the FIRST MID-REGION RETIREMENT**: the code becomes a HOLE `ss_addr_of` steps over, NO symbol is renumbered, and `SS_COUNT` 218 → 217 / `SS_TAG` 0x84DA → 0x85D9.  A SECOND hole would need a second term in `ss_addr_of`, and the package says that is the signal to re-think the region rather than add one.  It was 218 / 201 / 0x84 through SM3 s11 (SM3 **s11**: H1's four `bnd_*` BIU flops are DELETED and 0x066-0x069 RETIRED, not reused — the recognition floor is one term on the EU's IE gate now.  It was 222 / 205 / 0x83 at SM3 s3 / F52, and 218 / 201 / 0x82 before that; the address COUNT coincides with the pre-F52 one and the MAP does not — 0x066-0x069 are vacant, so a v3 stream can never be read as a v4 one) |
| save-state sweeps | `check_core.py --ss-sweep …` modes 1 / 2 / 5 | 80/80 · 24/24 · width PASS |
| CE hold | `check_core.py --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` |
| the core inside the real integration ⧉ | `python3 sw/check_ab_sim.py` | 187 rows MATCH |
| the MODEL, unmoved | `python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all` | 169,000 / 169,000, row-diffs 0 |
| the MODEL's fuzz bank | `python3 sw/timed_fuzz.py --core sim --evt-replay` | REGISTERED **1,272 / 1,702**; EVT **788 / 1,008**; COMBINED **2,060 / 2,710** (EVT/COMBINED RAISED by FIVE seeds at **SM3 sitting 21** by **F57** — the same five the ucore gained, §82.3; it was 783 / 2,055 (EVT/COMBINED RAISED by ONE seed at **SM3 sitting 19** by the model's F53 leg — `mc2/672`, whose first-divergence `kind` was `ube`, `ucore_provenance.md` §80.A.4); `INVALIDATED` **0**.  Same INV-1 closure; it was `EVT 709/1,008` as banked (STRUCK), then `144/248` interim.  **RAISED 2026-08-04 by SM3 sitting 2's H1 landing: EVT 363 -> 780, COMBINED 1,635 -> 2,052, +417 seeds, REGISTERED unchanged to the seed (`ucore_provenance.md` §61), and again by SM3 sitting 11's re-arm onto the IE rise: EVT 780 -> 782, COMBINED 2,052 -> 2,054, REGISTERED still 1,272 to the seed (§72).  The ucore leg WAS TAKEN at sitting 3 (§62) and the ucore now LEADS this column: EVT 906 vs 780, COMBINED 2,389 vs 2,052 — on a bank where the ucore PREDICTS and the model REPLAYS.**  Before H1 the rebuilt column read 363 and the ucore led by 105; as banked it appeared to trail by 517.  The 248 never-poisoned seeds are unchanged at 170 / 144, which is the control that says the re-capture moved nothing it did not touch |

### HOW THE EVT COLUMN MAY AND MAY NOT BE QUOTED (SM3 sitting 5, 2026-08-04)

**The two EVT figures above are NOT a head-to-head, and quoting them as one is
a category error.**  Registered here because the two rows sit next to each
other and invite exactly that reading.

Under `--evt-replay` the two engines are given **different information about
the same capture**:

| | what it is handed | what it must produce |
|---|---|---|
| `--core sim` | `timed_fuzz.evt_directive` — the rig's schedule **plus the capture's own acknowledge positions and the chip's pushed CS:IP** (`uf.entry_points` / `uf.frame_of`) | the rest of the trace, with the recognition instants supplied |
| `--core ucore` | `timed_fuzz.evt_tuple` — the rig's `(anchor, delay, hold, pin)` and **nothing from the capture** | the recognition instants **and** the rest of the trace |

So the model **REPLAYS** and the RTL core **PREDICTS**.  Each number is a
silicon-match score, and each is a valid ratchet for its own engine: that is
what they are for, and the correctness target (`CLAUDE.md`) makes silicon the
bar for both.  What they are not is a comparison of the two engines' accuracy,
because a replayer is scored on a strictly easier problem than a predictor.

* **Legitimate**: "the ucore is 906/1,008 against silicon"; "the model is
  780/1,008 against silicon"; "both rose when H1 landed".
* **NOT legitimate**: "the ucore beats the model by 126 seeds"; "the ucore is
  the more accurate engine on the EVT axis"; any ranking, delta or margin
  computed between the two columns.

The **REGISTERED** column (1,702 seeds, no `evt` axis) does not have this
problem — neither engine is handed anything from the capture there — and it is
the column to use when a head-to-head is actually wanted.

*This rule was written after a Codex review of the silicon-match phase found
the head-to-head reading already in circulation, including in the §B rows
above.*  The prose in the two rows is left as written, with this section as its
correction, because rewriting a recorded claim in place would hide that it was
made.  **Where the rows above say the ucore "LEADS this column", read: the two
columns are scored under different information and no lead is established.**

### SUSPENDED — **EMPTY** (the section is kept; the entry closed 2026-08-04)

A suspended gate is not a failing gate and it is not a passing one: its
population was withdrawn and no number over it means anything until the
population is rebuilt.  Suspending is loud on purpose — an unlisted gate that
quietly stopped being run is the failure mode this section exists to prevent.

**Nothing is suspended today.**

| gate | why | **what closed it** |
|---|---|---|
| ~~the FULL 1,008-seed EVT column~~ (`timed_fuzz --evt-replay`, both engines) | **INV-1 / F46** — 760 of its 1,008 seeds were captured under a pin hold the rig could not apply | **CLOSED 2026-08-04, session SM2.**  FLASH #4 (`67ddd59413d5…`) carries the 12-bit `evt_hold`; the board's host tool was replaced with the 12-bit copy; the register AND the pin were proved (`EVT_CFG` 8/8 round-trip; on the pin, 2 INTA T1 rows at `hold=44` vs 6 at 300 vs 12 at 600); all 760 re-captured from the socket with 0 errors and 0 GEN-DRIFT; `f46_invalidated` now False on all 760 by arithmetic.  The gate is live again at **ucore 468/1,008, sim 363/1,008.** |

**Known-RED, standing and registered** (reproduce as exactly this; they are not
passes and must not be quoted as any):

| | number | where it is written down |
|---|---|---|
| the four HLT delay sweeps | ⚠ **279/283 SINCE SM3 SITTING 21 — and the MODEL's leg is 283/283, PERFECT.**  **FAMILY B IS CLOSED IN BOTH ENGINES** (`ucore_provenance.md` **§82**): **F56** deleted M6 (+4 cells) and **F57** moved the read's completion clock to the cycle's own eval (+2).  The ucore's **FOUR** survivors are `w1.INT/8,9` · `w2.INT/12` · `w3.INT/15` — **family D, and by USER DISPOSITION of 2026-08-05 they are SCORED VIA `tb_sys`, not on `tb_v30_core`**, on which they are unfixable by construction (it samples `BS` once).  The model's leg has none of them, which is why §82.4 records the sitting's own registered 283/283 for the ucore as a **MIS-DERIVED bar and a MISS**.  Model 277 → **283**, ucore 273 → **279**.  *The superseded text follows, because a ratchet is only readable against its own history:* **91/97, 93/95, 45/46, 44/45 = 273/283** — UNMOVED at **SM3 sitting 20**, which is F55's own bar P4 (`ucore_provenance.md` §81.A.4), and re-measured there on the `AD_OE`-keyed composer as well (the model is **277/283** since SM3 sitting 19 — `ucore_provenance.md` §80.A; it was 272) — RAISED from 265 at **SM3 sitting 16**: **F53** landed (the address phase is ONE CLOCK on the DISPLAY side of the pin mux as well as the T1 side, for an INTA's zero as well as an address, and UBE is loaded by the address phase and then HELD).  §76.D.2's families **A, C and E are one law and all their signature cells are closed**; the residue is **10 cells, two mechanisms, catch-all empty**: **6 family-B** (`w0.INT/2,3` · `w0.RES/2,3` at `(4,busstat)` and `w0.INT/4,5` at `(17,busstat)` — an announcement one capture row late, MODEL-SHARED) and **4 family-D** (`w1.INT/8,9` · `w2.INT/12` · `w3.INT/15` — the analyser's SECOND BS sample, see §77.A.2: the pattern occurs 4 times in 217,507,379 committed golden rows and they ARE these four cells, and `tb_v30_core` cannot render a fix for them because it samples BS once).  It was 259 before sitting 6 and 265 before this one | `ucore_provenance.md` **§77**, `sm3_s16_prereg_2026-08-05.md` |
| the S16 directed display walk | **1,320 / 1,371** (`python3 sw/sm3_s16_score.py --core ucore`) — **RAISED from 1,294 at SM3 sitting 21**, +14 by **F56** and +12 by **F57**, cell for cell and 0 broken (`ucore_provenance.md` **§82**).  Per wait level **372 · 328 · 318 · 302** — **w0 IS 372/372, PERFECT**.  Its residue is now **TWO classes and no third**: **24 `D_tstate`** (family D, a `tb_sys` item by user disposition) and **27 `ARCH`**; `busstat_other` and `B_late` are **GONE**.  *The superseded text:* **1,294 / 1,371** — a board population captured 2026-08-05 that did not exist when anything was scored: 3 forms × 6 frozen programs × 4 wait levels × 21 delays, socket only, `div_guard` PINNED, raw words + rows + sha256 in `sw/testdata/sm3-s16cell/`, goldens in `tests/v30/s16-dispwalk-w<w>-p<p>/`.  It is the AUTHORISING population for **F53** and for **F54**, and both attributions are controls on the same cells: pre-F53 **1,207** with **72** family-A/C nibble and **5** family-E `ube` cells, post-F53 **1,252** with **0** and **0** (+45 / −0); pre-F54 **1,252**, post-F54 **1,294**, cell for cell **+42 / −0** (**SM3 sitting 17**, `ucore_provenance.md` §78).  Per wait level **346 · 328 · 318 · 302**.  Its 77 residual cells are **10** `busstat_other` (6 `HLT.RES` d2/d3 w0 + 4 `HLT.INT` d2 w0 — the w0 wake race, MODEL-SHARED), 16 one-row-late, 24 family-D and **27** architectural.  **§77.E's reading of the 42 `HLT.NMI` cells as H7 IS WITHDRAWN** — they were F43's missing NMI half (§78.C) and they are closed | `ucore_provenance.md` §77.D/§77.E, **§78** |
| **the S16 directed display walk, the MODEL's leg** | **1,305 / 1,371** (`python3 sw/sm3_s16_score.py --core sim`) — **RAISED from 1,279 at SM3 sitting 21** by F56 (+14) and F57 (+12).  Its residue is **39 `qop` + 30 `ARCH`**, both inside the model-only debt the user FROZE on 2026-08-05; **family B is gone and the catch-all is EMPTY**.  *The superseded text:* **1,279 / 1,371** (NEW at **SM3 sitting 18**, RAISED at **sitting 19**) — the model had never been scored on the authorising population.  Per wait level **343 · 331 · 312 · 293**; it was **1,249** with **343 · 331 · 300 · 275** until sitting 19's F53 leg closed the whole 30-cell `E_ube` class **+30 / −0** (`ucore_provenance.md` §80.A).  It was **1,225** before F54's model leg landed (+24 / −0 cell for cell, the 24 being `HLT.NMI` `w0 d0 · w1 d4 · w2 d6 · w3 d8` on all six programs).  Its 122 residual cells are **10** `busstat_other` + **16** `B_late` — the SAME 26-cell family B the ucore has, identical cell for cell AND diff for diff — plus **39** `qop` and **30** architectural.  **`E_ube` is GONE** (it was 30): sitting 19 landed F53's law in the model as its two sentences — *UBE is loaded by the address phase and then HELD* and *a HALT pseudo-cycle has no data phase* — and family E turned out to be the one-shot's THREE pins, not one.  **`--core sim` scores through `timed_gate.run_form` and then the IDENTICAL `check_case`/`diff_rows`/`classify_first` the RTL legs use**, so the two figures are comparable; the control is that the ucore leg re-run at sitting 18 reproduces 1,294 / 1,371 | `ucore_provenance.md` **§79.B** |
| ⚠ **A RIG DEFECT, FIXED AT SM3 sitting 18 — and it moved a booked number** | `v30sim timed-run` keys its record stream by the case's ARRAY POSITION; `compose_batch` keys the RTL batch by the golden's own `idx`.  The S16 suites are the first population in the tree where the two differ (`idx` is the DELAY, 141 cells non-composable, the sets start at 0 / 1 / 4 with gaps), and `sm3_haltsupp.py` used the RTL lookup on both legs.  **§78.I's model column was measured through it and is WITHDRAWN**: the model gets `HLT.INT` and `HLT.RES` EXACT at all four wait levels, and its NMI constant was `K = 7` against silicon's `K = 6` — one clock, not "three wrong ways".  The old lookup was replayed and reproduces §78.I's table exactly, including why `HLT.RES` escaped (its `idx` starts at 0) | `ucore_provenance.md` **§79.A**, `sm3_s18_prereg_2026-08-05.md` §0 |
| the fabric HLT sweeps | ⚠ **268/283 PREDATES F55** — FLASH #9 was taken at SM3 sitting 19 and F55 landed at sitting 20 (`ucore_provenance.md` §81.A); the registered prediction for FLASH #10 is **273/283**, the 5 F55 cells closing and no others moving (§81.A.7).  Quote 268 as a FLASH #9 figure or not at all.  **268/283 on FLASH #9 (SM3 sitting 19, 2026-08-05) — the fresh `tb_sys ret` column EXACTLY, 0 PASS/FAIL disagreements and 0 differing coordinates over all 283, and the 15 failing cells were NAMED IN ADVANCE with their coordinates.  F53 AND F54 ARE IN FABRIC (the sweeps were 265 on FLASH #6, which predates both).  The 15 are 6 family-B + 2+2 family-D + **5 F55** (`ucore_provenance.md` §80.B).  The FLASH #6 figure, superseded, was: 265/283 on FLASH #6 (SM3 sitting 12, 2026-08-05) — the OFFLINE COLUMN EXACTLY, and the 119-cell INTA class is CLOSED.**  It was 146/283 on FLASH #5, 143/283 on FLASH #4 and #3.  **§56.3a's INTERVENTION RAN IN FABRIC AND C11 IS ESTABLISHED AT THE MECHANISM LEVEL — ⚠ but its REGISTERED NUMERICAL BARS were SUPERSEDED, NOT MET** (`ucore_provenance.md` **§73.9a**, SM3 s13 / Codex concern 3a: §56.3a registered **116 cells / 259 of 283**, F43 then moved the offline reference at sitting 6, and **119 / 265 of 283** is what ran.  What carries the finding is that §56.3a's registered REFUTATION did not occur in any cell): `x1_fabric baseline --leg fab_f6` **265/283**, **119 of 119 closed, 0 survivors**, the 18 remaining cells are the SAME 18 named in advance with the SAME first-divergence coordinate on every one, and scored strictly against the `tb_sys ret` leg over all 283 cells there are **0 PASS/FAIL disagreements and 0 differing coordinates**.  Socket control **49/49**; `check_ab_hw all 800` first light **MATCH ×3**; `use_core=0` chip proof **MATCH 800** after everything; `div_guard` PINNED both sides; **0 transport errors**.  **C11 IS ESTABLISHED** — the INTA pad-float retention attribution is a FINDING (the CODEX REVIEW item in `ucore_campaign_verdict` §(g); **NOT** `timed_lawcards`' C11, which is the LC4 `owns_slot` card and is untouched).  **The 18 survivors are core-owned and unexplained**: 4 `w0` `busstat` (model-shared, §68.2) and 14 `seg`/`bus` at the top of each sweep's `d` band (§67.3) — and fabric and TB now agree on them cell for cell, so they are diagnosable entirely offline | `ucore_provenance.md` **§73.8/§73.9**, §56.3a |
| ~~**R7 / R7′**~~ — **R7′ IS CLOSED, SM3 sitting 12** | R7 was refuted at sitting 9 (its "81 registers escaped the name scope" compared two DIFFERENT STAGES of one flow; stage for stage the collection GREW, and `nec_test.sdc` was NOT and still is NOT edited).  **R7′ — `READY` reaching the EU's next-state cone single-cycle at 55–63 levels, with closure depending on whether the fitter happened to break it — WAS REAL, and at HEAD it had SWAPPED SIDES: the DEFAULT build (macro OFF) measured **19.42 MHz**, worst setup **−20.254**, TNS **−13,129.815**, 20,000/20,000 failing paths launching from `system_large|c_ready_q` into `v30u_eu` at 62–63 levels — reproduced to the digit from a DELETED `db`.  **G6 was RED at HEAD and no gate saw it, because the standing set has no Quartus leg.**  **CLOSED by ONE MUX**: the read's data-edge PSW load (`interrupt_model.md`'s POP-PSW rule, unchanged) moved off the head of the twelve-position chain onto the `psw` register's own `D` pin, gated `row_blocked`.  Control **45.89 MHz / +8.493 / TNS 0.000**, retention **45.87 / +8.802 / 0.000**, **0** failing paths on both, worst `c_ready_q` path **19 levels**.  Ladder **ZERO-DELTA at the seed** (38/38 steps; 5 of 3,242 fuzz report entries differ and every one is a `$warning` LINE NUMBER); no flop added or removed on any entity across six builds.  A first form WITHOUT `row_blocked` was built, worked, and was REVERTED by its own pre-registered falsifier | `ucore_provenance.md` **§73**, `sm3_s12_prereg_2026-08-04.md`, `sm3_s12b_prereg_2026-08-04.md` |
| the b2 tranche | **172/188** — V5, still the standing REGISTERED FAILURE.  ⚠ **This row read 171/188 until SM3 sitting 20 and that was STALE**: §66.3 RAISED it 171 → 172 at SM3 sitting 6 (the TB `IOW` fix) and every sitting since §69 has reported 172.  Corrected against the artifact, not against recall (§81.A.5a) | `ucore_provenance.md` §44.2, §66.3, **§81.A.5a** |

### **H1a — "THE RECOGNITION FLOOR'S ARM IS THE INTERRUPT ENTRY" WAS BUILT AND IS REFUTED (SM3 sitting 10, 2026-08-04).  DO NOT RE-PROPOSE IT WITHOUT READING §71.**

Recorded here, in the gate document, because the landing's AUTHORISING LEG IS
PERFECT and a future sitting reading only that will land it again.  On the
banked h1a cell the entry-generic arm takes `sim` from **671/791 to 791/791**
acknowledges, the `swintnext` w0 column from **0/30 to 30/30**, with every
control unmoved — and on the DISJOINT 3,242-seed bank it improves §64.2's two
named seeds to EXACT and **BREAKS FIVE**, `EVT 780 -> 777`.  All five broken
seeds are `evt.pin = 1` (**NMI**); both improved are `evt.pin = 0` (INT); zero
INT seeds regress; and chip-side the five carry `mc1/2672`'s geometry cycle for
cycle.  **Reverted per its own pre-registration** (`sm3_s10_prereg_2026-08-04.md`
§5.2/§6), proved at the seed — **0 of 3,242 differ on either engine** — and
**no gate in this document moved.**  `sim/biu_timed.h` carries the refutation at
the arm's own declaration and `V30SIM_BNDTRACE=1` is the instrument.

**AND THE QUESTION IS CLOSED — SM3 SITTING 11 (`ucore_provenance.md` §72).**
What survived §71 was the IE-RESTORE reading, and it was AUTHORISED by a NEW
directed board cell (768 captures, `sw/testdata/sm3-s11cell/`, socket, FLASH #5)
whose eight registered outcomes were **all met at the point estimate**: on
`CLI;POPF;NOP;NOP` and `CLI;STI;NOP;NOP` the chip takes the boundary at which IE
ROSE **0 times in 24 delays**, takes the boundary at which IE is CLEAR **0
times**, takes NO ENTRY AT ALL on `CLI;POPF` in **24 of 24** — and on the **NMI**
pin takes all of them freely.  §61.3's `clipopf` silence is EXPLAINED, not
fixed: that chain has no boundary a floored recognition can ever reach.  **THE
LAW IS: a maskable recognition may not act until two clocks after PSW.IE's
rising edge; a non-maskable one is not IE-gated and waits for nothing.**  Landed
in BOTH engines; the ucore's version DELETES five flops, a port and four
save-state addresses and adds none.

The complete, itemised list of what is **not** yet functional or timing-accurate
is `docs/notes/ucore_gaps_2026-08-04.md`, and **the measured census of what is
left against silicon — family × population, the shared/only partitions and the
ranked mechanism hypotheses — is `docs/notes/sm3_residue_census_2026-08-04.md`
(SM3, 2026-08-04).**  Read the census before planning work on the residue: its
**H1** accounted for 445 of the ucore's 540 EVT seeds and 491 of the model's
645, 437 of them the same seed, in ONE mechanism — **and it is CLOSED in both
engines since 2026-08-04** (`ucore_provenance.md` §61 / §62).  **H2 is RETIRED**
(its falsifier fired; it is a signature, not a family).  The current ranked list
is **§62.9**: H3 `PF_LOST`, H4 `DATA_SEQ`, H7 the `0x0008` NMI-vector class,
H5, H6.

**SM3 sitting 22 (2026-08-05, `ucore_provenance.md` §83) SPLIT H4's PARTITION B
AND MOVED NO GATE.**  §67.2's "27 shared REGISTERED seeds with a wrong `MEMR`
launch address" is **not one class and only 12 of the 28 are a BIU question**:
**B1 = 3** (`mc2/1718`, `mc2/3061`, `t30-raw/899`) where the chip takes a
genuine **INT-1 entry** — vector pair at `4`/`6`, three descending word pushes,
handler fetch at `0x00480` on all three — because **NEITHER TIMED ENGINE
IMPLEMENTS THE BRK/TF SINGLE-STEP TRAP AT ALL** (`kEvtBrk` has ONE caller in the
tree, `sim/image_runner.cpp`; `timed_runner.cpp` never tests the flag and the
ucore's `FBRK` is written and never read); **B2a = 12**, architecture-exact and
timing-divergent, the genuine BIU target, cheapest instrument `t30-raw/962`
(`ndiff` 4 of 4,000); **B2b = 13**, where `ucsim_fuzz` shows the ARCHITECTURAL
model already disagrees — inherited functional residue, routed OUT of the timing
census.  Bank-wide the TF class is **145 REGISTERED seeds**, of which 115 are
`OPEN_BUS`-excused, **29 diverge in both engines** and **1 is exact** — and that
one, `mc2/2361`, is the only seed of the 30 whose vector-1 entry is a *software*
`INT 1` rather than a trap.  **NOT LANDED**: the arm's instant is measured to be
one instruction off (`chip == arch[1:]`, 18 of 30 conclusively) but *whose* set
gets the grace is not, and the uniform reading is refuted by the storm cadence.
§83.7 registers the board-free discriminator.

**SM3 sitting 4 (2026-08-04, `ucore_provenance.md` §63) moved NO GATE — it
landed nothing in either engine — but it changed what two of those names mean.**
**H7** is a measured FLOOR (chip `A + 12`, both engines `A + 13`) whose
one-register reading was BUILT AND REFUTED: it breaks 17 golden `NMI.90` /
`NMI.B8` cases, and the conflict reproduces inside the fuzz bank itself, so H7
is BLOCKED with a directed cell.  **H3 is TWO families**: 92 of the ucore's 129
(88 of the model's 309) are the 8080 / BRKEM gap at the harness's own IVT
landing pad (`ucore_gaps_2026-08-04.md` §F.1, now costed), NOT arbitration; the
real arbitration residue is 37 ucore / 221 sim, and M4's `occ + inflight ≤ 4`
boundary was tested chip-side and is NOT the answer.  New MEASUREMENT tool (not
a gate): `sw/sm3_nmigeom.py`.

> **SM3 sitting 17 (2026-08-05) — H7's EVIDENCE SET SHRANK AND ITS DIRECTED
> COLUMN GREW.**  §77.E's 42 `HLT.NMI` cells were attributed to H7; that is
> **WITHDRAWN** (`ucore_provenance.md` §78.C) — on all 42 the golden and the
> ucore put the NMI vector read at the IDENTICAL row and the first divergence is
> `busstat PASV -> HALT`, so they are F43's missing NMI half (F54) and are now
> closed.  The S16 population becomes a FOURTH directed measurement of the NMI
> floor: **`A + 14` on 372/372 halted cells, 13 on the running ones**, both
> engines exact.  With `sm3_h7_cell` (160) and `sm3_h7_opcode`'s board cell
> (640) that is **2,312 directed captures at floor 13** against the banked
> soup's 30 at 12 — the bank is now the ONLY population in the tree that reaches
> 12.  Two more axes eliminated: **the arm is not ambiguous** (28 of the 30
> gap-12 seeds have exactly ONE CODE T1 at the anchor in the whole capture) and
> **the divider is not it** (`DIV_OF_RECORD = 8` on both capture paths;
> `NEC_NMI` is combinational off `ev_drive`).  **H7 stays BLOCKED.**
> New MEASUREMENT tool (not a gate): `sw/sm3_haltsupp.py` — the HALT-announcement
> suppression census, silicon leg from retained rows and engine leg over the
> emitted goldens.

> **SM3 sitting 20 (2026-08-05) — H7's FLOOR DOES NOT REPRODUCE, AND THE
> POPULATION THAT DOES NOT REPRODUCE *IS* THE FLOOR** (`ucore_provenance.md`
> **§81.B**).  The 30 banked `A + 12` seeds were re-captured on the current rig
> (FLASH #9, socket, `div_guard` PINNED), **10 repetitions each**, images
> hash-checked, `arm` and `A` reproducing EXACTLY on all 30.
> * **0 of 30 reproduce their banked gap.**  Over **579** fresh repetitions of
>   the whole 193-seed pin-1 population the minimum gap is **13** and the number
>   reading 12 or less is **0**.
> * **162 of 163 NON-floor seeds reproduce exactly** (banked 14…409: 145/145).
>   The two ADDED controls (declared as added, run after the result) are what
>   make that readable.
> * **193 of 193 seeds are DETERMINISTIC** across their repetitions — zero
>   within-seed variance in **1,089** captures, so the effect is *not* sub-clock
>   jitter within a session.
> * The pin-0 control reproduces **30/30**, including two seeds banked at 12.
> * Row-level: on **14** of the 30 (12 at gap 13, 2 at 14) the fresh run is
>   byte-identical through `A + 10` and the recognition is **EXACTLY ONE CLOCK
>   LATER**; on the other
>   **16** the first divergence is `qs` at `A + 3`, §63.2's own
>   recognition-instant coordinate, and the vector read slides to the next
>   boundary.  **All 31 movers move LATER; none earlier.**
>
> **The registered outcome was (iv)** — 16 seeds read *above* 13, not 13 — so
> per the pre-registration it is REPORTED and NOT FOLDED, and **INV-2 was NOT
> written.  Nothing in the bank was touched.**  What is established: **H7's
> floor of `A + 12` has no live evidence**, both engines' 13 is silicon's number
> on every measurement takeable today, and **H7 remains BLOCKED — but the reason
> is now one named, testable question**: `A` is DERIVED (`arm + delay + 2`),
> never measured, and a one-clock shift in the rig's actual assert instant
> between eras predicts this entire table (only A-limited seeds move, all later,
> boundary-limited ones do not move at all).  **NOT ESTABLISHED**; the direct
> measurement of the assert instant belongs in its own pre-registration.
> New MEASUREMENT tool (not a gate): `sw/sm3_h7_repeat.py`.

### THE S16 WALK THROUGH THE INTEGRATION — NEW, SM3 SITTING 19

`python3 sw/sm3_s16_fabric.py {offline, vsys --ret, fabric, socket, score}`

The 1,371-cell S16 display walk replayed through the ucore instead of the
socket.  **ROWS ONLY** (`check_core.diff_rows`) — a DUT leg has no
architectural readback — so its totals are **NOT** `sm3_s16_score.py`'s
**1,320/1,371** (it was 1,294 before F56 and F57; §82), which is
`not mm and arch_ok`.  Quoting one against the other is a
comparator error; `offline` exists so the fabric total has a same-scale
reference.

| leg | **figure** |
|---|---|
| `offline` — `tb_v30_core` | **1,347 / 1,371 SINCE SM3 SITTING 22** (`ucore_provenance.md` §83.0b).  It was **1,321** and that figure was **PRE-F56**: the column was written before F56 and F57 landed in the ucore and was never re-taken.  **+26 = F56's +14 + F57's +12**, the same two numbers §82 measured on `sm3_s16_score`'s scale |
| `vsys_ret` — Verilated `system_large`, `X1_AD_RETENTION` ON | **1,347 / 1,371 SINCE SM3 SITTING 22**, with **0 PASS/FAIL disagreements and 0 differing coordinates against `offline` over all 1,371** — the expectation was registered before the number was read and was MET.  It was 1,321 and was **PRE-F56 IN THE SAME WAY**, which is why the cross-check read green: *two instruments compared with each other are only as current as the older of them.*  Before that it was 1,291 (**F55**, §81.A) |
| **`fab_f9` — IN FABRIC, the population's first** | **1,291 / 1,371** — **taken on FLASH #9, which PREDATES F55, F56 AND F57.**  Its era is the FLASH LOG, not the tree, and it is deliberately NOT era-stamped.  It matched `vsys_ret` cell for cell when both were 1,291; its "30 disagreements vs `vsys_ret`" was taken against the PRE-F56 column and must be **RE-DERIVED at the next flash, not restated**.  §81.A.7's registered FLASH #10 prediction of **1,321** was written against the pre-F56 offline column and is likewise superseded — the offline reference is now 1,347 |
| `soc_f9` — the socket control, `use_core=False` | **41 / 41** |

**The 30-cell `offline`-vs-`vsys_ret` gap is CLOSED** — it was F55, and F55 is
landed.  The two offline instruments now agree on all 1,654 cells across the two
populations.

### **F55 — LANDED, SM3 sitting 20** (`ucore_provenance.md` §81.A; booked at sitting 19, §80.B.3b)

`v30u_biu.sv`'s `halt_hold = r_run && r_cur_halt` kept `ad_oe_addr` asserted for
the WHOLE HALT pseudo-cycle and published `r_cur_addr` on every clock of it.
Silicon leaves that address on the pads by **RETENTION**, not by **DRIVE**, and
the two differ exactly when a multi-clock announcement takes the pads in between
and is then WITHDRAWN.  It is F53b's sentence one pin over: *a pad is loaded by
a PHASE and held otherwise.*

**THE LANDING, two terms and no new state**: `halt_addr = r_run && r_cur_halt &&
(r_ts == TS_T1)` — the address one-shot ends with the address phase — and
`ad_oe_ps` gains `!r_cur_halt`, so nothing else takes the pads when it expires.
All three enables are LOW for the body of a HALT; the pads float and RETAIN.
**The registered falsifier was met exactly**: `tb_sys ret` **268 → 273**, S16
`vsys_ret` **1,291 → 1,321**, and `tb_v30_core`'s own columns **273/283** and
**1,321/1,371** did **NOT MOVE**.  G6 **PASS** with Fmax **47.15 MHz** (up from
45.49) and ALMs **11,104** (down from 11,126) — deleting a drive is a net
simplification.  **Not in fabric yet**; §81.A.7 registers the prediction.

### **F56 AND F57 — FAMILY B, CLOSED IN BOTH ENGINES (SM3 sitting 21, `ucore_provenance.md` §82)**

Two mechanisms, two pre-registrations, two landings, and **both are a deletion
or a relocation — neither adds a rule, a constant or a flop.**

**F56 — M6 IS DELETED.**  *No fetch is chosen while the previous fetch's bytes
are landing in the queue* was measured in T2b 12.1 and is **refuted by its own
firing census**: counted on the branch, it is reached and taken **22 times in
the whole tree** — **0** on `v0.1`'s 169,000, **0** on the wait axis, **0** on
scenario / enter / ins / wvec, **0 on all 228 `timed_lawcards` processes
including C1/C2/C3, the Arm-C sled that measured it**, **3** in one fuzz seed
whose verdict does not move, and **19** on the HALT sweeps and the S16 walk
where every one is a cell silicon contradicts.  `no_eval_` (M2r) covers M6's
window by construction at every wait level above zero, so it was only ever
reachable at w0 — which is why family B was a w0-only residue.  **`sim/` loses
two fields; the `ucore` loses a flop, and `9'h038` is the map's FIRST
MID-REGION RETIREMENT.**  +18 cells per engine.

**F57 — A READ'S COMPLETION CLOCK IS STAMPED AT THE CYCLE'S OWN EVAL.**
Silicon's second acknowledge is `display + 7` at every delay; both engines gave
`T1 + 6`, which is the same number for every cycle whose T1 opens the clock
after its display and one clock late for the acknowledge after a woken HALT —
the only place in the corpus where a T1 waits.  The stamp's VALUE was already
eval-keyed (`e + 2`); it was PUSHED at T4, so the EU could not learn it before
`T4 + 1`.  **W0-neutral by construction, no new state in either engine**, and
the proof that the two engines share the sentence is that they gain **exactly
the same five fuzz seeds**.  +14 cells per engine.

*Falsifier for F56, standing*: any population on which the deleted branch would
fire AND silicon agrees with it.  *For F57*: any cell whose EU leaves the read
wait at a clock other than `e + 2`.

**AND THE `tb_sys` LEGS FOLLOWED THEM AT SM3 SITTING 22** (`ucore_provenance.md`
§83.0).  F55's `tb_sys ret 273` above is a **F55-era** figure and was left
un-recaptured across F56 and F57, so `x1_retention score` was comparing a
POST-F57 reference column with a PRE-F56 measurement column and reporting
"6 SURVIVED, BAR (i) NOT MET" — the six being exactly the six w0 cells F56/F57
had already closed.  Re-captured on one tree: **`offline` 279/283 (unchanged),
`ret` 273 → 279/283 = `offline` EXACTLY, 0 survivors, BOTH BARS MET**, and
`base` 146 → **34/283** (the diagnostic column, never a ratchet — F55 took the
retention out of the core's DRIVE, so a harness without retention must miss
more).  **Quote 279, or the era it belongs to, or not at all.**

**THE ERA GUARD, added with it (the vacuous-gate pattern, EIGHTH incarnation).**
Every `x1_retention` capture now embeds the artifact layer's input manifest hash
for the binary that produced it, `offline.json` included, and `score` **REFUSES,
naming both hashes**, when a column's era is not this tree's.  It is
command-free so it is identical across the `base`/`ret` A/B pair by
construction.  Demonstrated non-vacuous in three modes — ABSENT, MIXED (it names
"the column's own files DISAGREE") and MISMATCH — and green on the clean tree.
`--no-era-guard` is the single documented escape and it is for reading an
archived column as history.

**AND THE SAME STALENESS WAS FOUND ONE INSTRUMENT OVER (§83.0b).**  BOTH
`sm3_s16_fabric` SOFTWARE columns — `offline` (`tb_v30_core`) and `vsys_ret`
(`tb_sys`) — were written BEFORE F56 and F57 landed in the ucore, and it was
invisible precisely because they are compared with EACH OTHER and were stale
TOGETHER: *a cross-check between two instruments is only as current as the older
of them.*  Re-taken on one tree, with the expectation registered before the
second number was read: **both 1,321 → 1,347 / 1,371, 0 PASS/FAIL disagreements
and 0 differing coordinates over all 1,371** — **+26 each, F56's +14 and F57's
+12 exactly**.  **Quote 1,347, not 1,321.**  `fab_f9` **1,291 / 1,371** is
UNTOUCHED and remains a FLASH #9 figure (its DUT is a bitstream, its era is the
flash log), but its "30 disagreements vs `vsys_ret`" was taken against the
PRE-F56 column and must be RE-DERIVED at the next flash, not restated.
`sm3_s16_fabric vsys` now carries the same tree stamp and `score` refuses a
stale or unstamped `vsys*` leg; a FABRIC leg is deliberately NOT stamped this
way.

### **META-FINDING #5 RETIRED FOR `tb_v30_core` — THE COMPOSER ASKS THE CORE (SM3 sitting 20, §81.A.3)**

F55 was invisible to the DEFAULT TB because its composer INFERRED the core's
drive from the bus protocol, and one term (`cycle_live`'s `lat_type != 3'b011`)
floated a HALT-typed cycle's body **whatever the core did there**.  The composer
now keys on **`AD_OE`**, the core's own pad output enable (task #37) — the wire
`system_large` already uses.  **Two lines replaced eight wires, and it was landed
ONLY on a zero-delta**: sweeps 273/283 cell for cell, S16 1,321/1,371 with 0
differing coordinates, `check_core --opcodes all` 169,000/169,000, and the whole
standing ladder.  *Falsifier for the layer itself*: any cell where `tb_v30_core`
and `tb_sys` disagree again is a FINDING, not a tolerance.

**AND THE GENERAL RULE THIS SITTING ESTABLISHES**: where `tb_v30_core` and
`tb_sys` disagree, **fabric sides with `tb_sys`** — 1,654 of 1,654 cells across
the two populations, PASS/FAIL and coordinate alike.

### BOARD PROBES — NOT GATES, BUT THEY MUST STILL RUN

A rig-integrity finding from SM2, recorded here because it is the *reason* this
subsection exists: **`sw/s10_board.py` and `sw/s13_board.py` could not take a
capture at HEAD** and had not been able to since 2026-08-02.  `s10_board.capture()`
passes `want_raw=True` to `v30run.run_image`, which had no such parameter on any
branch (`git log --all -S want_raw -- sw/v30run.py` is empty), so every s10/s13
probe raised `TypeError` on its first capture.  **No standing gate runs an s10 or
s13 probe**, so nothing saw it until something needed the board.  REPAIRED in SM2
(`ucore_provenance.md` §59.7.11) by adding the parameter and returning the
undecoded 64-bit words that were already being unpacked and discarded.

| probe | command | what it is for |
|---|---|---|
| R6 per-repetition rows | `python3 sw/r6_perrep.py capture --reps 10` then `analyse` | banks EVERY repetition's full rows for the sweep cells whose `stable_identical` is false, and classifies the differences by pad class.  **It is also the live falsifier for the repair above** — it is an s10/s13-path probe and it takes 50 captures. |
| the X1 fabric legs | `python3 sw/x1_fabric.py baseline --leg <tag>` / `socket --leg <tag>` / `score` | the 283 HLT-sweep cells through the FPGA core, and §52.9's 49-cell socket control, written beside `sw/testdata/u4-f42/` rather than over it |
| the INV-1 re-capture | `python3 sw/inv1_recapture.py {archive, probe, holdproof, capture, rebank, verify}` | INV-1's closure apparatus.  `verify` is arithmetic over the artifact and is board-free |
| the b3 priority tranche | `python3 sw/u4_tranche.py capture --leg chip_f5 \| core_f5` then `score --legs chip_f5,core_f5 --ref chip_f5` | §48.4's victory condition, re-captured on every new bitstream as a NEW leg pair written BESIDE the last one.  **FLASH #9 (SM3 sitting 19): `chip_f9` 178/178, `core_f9` 176/178 (98.9 %), residue `bs = 2`, 0 errors in 400 captures — identical to FLASH #5's and FLASH #4's to the seed.  §73.9's re-capture debt for #6/#7/#8 is DISCHARGED at #9.**  Before it: **FLASH #5 (SM3 sitting 7): `chip_f5` 178/178, `core_f5` 176/178 (98.9 %), residue `bs = 2`, 0 errors in 400 captures** |

**THE BOARD CARRIES FLASH #9 SINCE 2026-08-05 (SM3 sitting 19)** —
`nec_test_ucore.sof` **`01aca4c0b1e7…`** (`.rbf 58154c546dba…`), built from
`134249a2ad` with **`X1_AD_RETENTION=1`**, through `sw/safe_flash.sh` with its
VERIFY leg (`sw/testdata/flash_log.jsonl`, now **12 entries**).  **It is the
first bitstream to carry F53 and F54.**  G6 was green on the CONTROL build at
HEAD first (receipt `2bf170fa9eee15f7…`, 45.49 MHz, +9.146 ns, TNS 0.000, 88-file
manifest `567b11fffd6414a6…` = sitting 17's); the retention build measured 44.99
MHz, +9.023 ns, TNS 0.000, ALMs 11,205 (27 %).  First light **800/800 on all
three `check_ab_hw` legs**; `use_core=0` chip proof **MATCH 800** after
everything; `div_guard` **PINNED** on every probe; **0 transport errors**;
`board_idle()` clean.  Resting `cfg 0xff0008`, `use_core` **False**.

*The superseded text, kept because a fabric figure is only readable against its
own bitstream:* **THE BOARD CARRIED FLASH #6 FROM 2026-08-05** — `nec_test_ucore.sof
**626fb30ebee2…**` (`.rbf 460a71907f87…`), built from `536e207c76` with
**`X1_AD_RETENTION=1`**, through `sw/safe_flash.sh` with its VERIFY leg.  **IT IS THE RETENTION
BITSTREAM** — §56.3a's `core_ad` pad-float model is COMPILED IN, on the
OBSERVATION path (`hb_ad_sample`) only, so the `use_core=0` socket position is
unaffected by construction and MEASURED unaffected (`check_ab_hw chip 800`
MATCH after the whole sitting).  It is also the first bitstream to carry the
sitting-11 IE-restore law and the sitting-12 R7′ structural pass.  First light:
**800/800 on all three `check_ab_hw` legs**.  Fmax **45.87 MHz**, worst setup
**+8.802 ns**, TNS **0.000** on every domain.

**FLASH #5 was `nec_test_ucore.sof 315de4bc9e30…`, built from `8339740709`**,
and is superseded; the FSM A/B bitstream is still `nec_test.sof a4533dfef0…`.
**A fabric figure taken on FLASH #5 may not be quoted against this tree.**

---

## C. ARCHIVED — ON DEMAND (the FSM core)

**These gate an ARCHIVED artifact.** They are not part of the standing set and a
green run of them says nothing about the ucore. Run the whole block before
re-activating the FSM core for anything (`fsm_core_archive_2026-08-04.md` §6);
otherwise, on demand only.

Every one is FSM-structural — it reads or mutates `hdl/rtl/core/*.sv`, or it
binds to the FSM `obj_dir` through `sw/check_seq.py`'s `BIN` constant — and has
no ucore counterpart.

| Gate | Command | Proves | binds to FSM via |
|---|---|---|---|
| check_race_law | `python3 sw/check_race_law.py` | the POP-PSW/INT race law is bit-exact | `rtl/core/race_law.svh`, `int9d_race.hex` — no ucore equivalent exists |
| check_ff_t4 | `python3 sw/check_ff_t4.py` | the far-flush direct-commit slots stay reachable (`SLOT_FF_T4` non-vacuous) | its own `hdl/tb/obj_dir/Vtb_v30_core` constant |
| check_lc6_gate | `python3 sw/check_lc6_gate.py` | the Family-5 strio-single uline-1 veto (`eu_rsv_strio`→`pick_t3`) is intact | `biu_law_lc6_gadget` mutates `rtl/core/v30_biu.sv` |
| prefix_clear_lint | `python3 sw/prefix_clear_lint.py` | `clear_prefixes()` single-source at every retire/exit site (RR4) | greps `rtl/core/v30_eu.sv` |
| ea_step_lint | `python3 sw/ea_step_lint.py` | every operand EA step wraps via `ea_step2` (F4a) | greps `rtl/core/v30_eu.sv` |
| check_mod3_illegal | `python3 sw/check_mod3_illegal.py` | LEA mod=11 executes chip-exact (task #30) | `check_seq.BIN` |
| check_enter_nesting | `python3 sw/check_enter_nesting.py` | ENTER walk == chip: MASK tranche + WAITED tranche (task #31, both ENTER bugs) | `check_seq.BIN`; **takes NO arguments** — unknown flags are silently ignored |
| check_fuzz_bank ⧉ | `python3 sw/check_fuzz_bank.py [--strict]` | the 3,242-seed banked corpus round-trips: regenerate → TB replay → re-classify, verdicts stable (task #29 phase 6).  **Re-run 2026-08-04 over the corpus INV-1's re-capture re-based: `PASS \| 3242 seeds \| stable 3242 improved 0 worse 0 \| gen_drift 0 \| float-floor 0 \| new-sig TIMING 166`.**  `--strict` FAILED on that last figure at SM2; the 140 distinct signatures were **ADMITTED at SM3** (`sw/sm3_sig_admit.py`, `sig_ledger.json`'s new `admissions` key, `sigs` 11,705 → 11,845, 0 pre-existing entries touched) after an independent full-bank control (`sw/sm3_sigctl.py`) re-derived **166 / 166 on true-300 / 12-bit re-captured seeds and 0 on any other**.  **`--strict` now exits 0.**  `ucore_provenance.md` §59.7.13 (the decision) and §60.1 (the control and the admission).  **NOTE, SM3**: `hdl/tb/obj_dir/Vtb_v30_core` — the binary this gate binds to — was found **STALE** (built before `5c5fdbf50a` changed `tb_v30_core.sv`), because `check_seq` never calls `check_core.build()`.  Rebuilt; the control reproduces SM2's figures exactly on the new binary, so nothing was scored wrong — but **rebuild the FSM TB before quoting this gate** until that plumbing is fixed.  **RED AGAIN SINCE SM3 SITTING 6, AND FOR A GOOD REASON**: `FAIL | 3242 seeds | stable 3237 improved 5 worse 0 | gen_drift 0 | float-floor 0 | new-sig TIMING 3 (strict-fail)`.  Nothing regressed — the sitting's `tb_v30_core.sv` `IOW` fix (`ucore_provenance.md` §66.3) improves FIVE seeds' verdicts on the FSM leg too, and a better verdict carries a new signature.  **The admission was ROUTED at sitting 6 and TAKEN at SM3 SITTING 7; `--strict` EXITS 0 AGAIN (§68.8).**  The RED was reproduced FIRST on a rebuilt FSM TB (`FAIL \| 3242 seeds \| stable 3237 improved 5 worse 0 \| gen_drift 0 regen_err 0 \| float-floor 0 \| new-sig TIMING 3`, rc 1).  Then an INDEPENDENT control — new tool **`sw/sm3_iowpop.py`**, which derives §66.3's `IOW` population from the CHIP ROWS ALONE (no engine, no testbench: the defect WAS a replay instrument, so a population defined by that instrument would be circular; **47** of the 3,242 banked seeds, and all seven seeds §66.3 names cross-check as members) — put **all 5 improved and all 3 new-signature seeds INSIDE the population and 0 outside it**.  `sw/sm3_sig_admit.py` gained `--cause {inv1,iow}`: the INV-1 control is unchanged to the line and the `iow` cause carries its OWN control, so a new cause got a NEW control rather than a weaker one.  `sigs` **11,845 → 11,848**, 0 pre-existing entries touched, a second `admissions` record written.  The three signatures are `b98079550c897a09`, `bb7f08a4adb12327`, `cea29561559cf048`, from `mc1/1937`, `mc1/3325`, `t30-raw/123` | `check_seq.BIN` |
| ss_lint, FSM leg | `python3 sw/ss_lint.py --core fsm` | the archived core's save-state map is consistent (203 addresses, 181 flops, 0 UNMAPPED) | `--core fsm` |
| the full FSM sweep | `sw/t30_sweep.sh` | the RR-era pre-reflash bar: the lints + gates + every golden suite, **explicitly `--core fsm` on every leg since 2026-08-04** | pinned |

**`check_fuzz_bank` keeps a value the disposition does not touch**: it is the
load-bearing control for the U5 comparator change (3,242 banked seeds replayed
and re-classified, **worse 0** — `ucore_provenance.md` §57.2). Cite it for that.

**READ BEFORE QUOTING ANY FSM NUMBER.** On the corrected comparator (the TB's
composed-AD mask removed at U5) the archived core is **168,400 / 169,000** on
v0.1 and **16 / 283** on the HLT sweeps. `t30_sweep.sh`'s "any non-full suite
total = regression" rule must be read against 168,400, not 169,000.

---

## D. The default flip of 2026-08-04 — what was checked

The flip was `fsm → ucore` on the five tools named at the top. Everything that
consumed the old default was found and made EXPLICIT rather than left to inherit
the new one:

* `sw/t30_sweep.sh` — six `check_core.py` calls and one `ss_lint.py` call, all
  now `--core fsm`. This is the one place where a silent flip would have
  changed a whole regression sweep's meaning.
* `sw/biu_law_mutation.py`, `sw/biu_law_lc3_gadget.py`,
  `sw/biu_law_lc6_gadget.py`, `sw/biu_law_lc3_seedsearch.py` — all four mutate
  `rtl/core/v30_biu.sv`; all four now pass `--core fsm`.
* `sw/sweep_parallel.py` — gained an explicit `--core` (default `ucore`) and
  passes it to `check_core.build()`.
* `sw/check_core.py`'s module-level `RTL` and `BIN` constants stay pinned to the
  FSM layout and have **no consumers** in the tree; annotated as traps.
* The two suites that the flip newly points at the ucore were **measured
  rather than assumed**: `f4a_boundary` **160/160** and `f0lock_tranche`
  **400/400**, identical to the FSM core's, and they are now registered in §B.

---

## Meta-finding: the vacuous-gate pattern (task #29 campaign, and after)

Five times now a green gate was VACUOUS — it passed while blind to a real
defect, because it only checks what it already knows to look at:

1. **F7a strio-domain assert** (`v30_biu.sv`): an over-narrow `assert` that had
   never been exercised outside the w0 strio domain; the fuzz soup reached the
   coincident state under waited/interrupt-shifted timing and it fired. Board
   arbitration proved the state chip-correct → the assert was wrong, downgraded
   to a counter (`cov_f7a_coldarm`).
2. **Terminal-else S_HALT park** (`v30_eu.sv`): register-form opcodes with no
   dispatch branch silently parked at S_HALT with NO assert. LEA mod=11 wedged
   the core there for the entire task #29 pilot corpus before anyone noticed.
   Fixed with a WHITELIST assert.
3. **ss_lint's unmapped-flop blind spot**: ss_lint verifies only symbols ALREADY
   in the map, so it CANNOT see a NEW unmapped architectural flop. `last_ea`
   (task #30) was unmapped and ss_lint passed vacuously until the symbol was
   added. **CLOSED** — `sw/ss_flopcensus.py` now runs RTL→map for both cores and
   is invoked by `ss_lint`; on its first ucore run it found five unmapped flops
   (F49), which is exactly the class no map-walking instrument can see.
4. **check_enter_nesting w0-ONLY blind spot** (task #31): the ENTER-nesting
   tranche captured chip goldens at **w0 only**, so it was VACUOUS for the
   PUSH-BP drop that manifests only under waits (w≥2). Closed by the WAITED
   tranche. The standing rule generalises to *"sweep the wait axis, not just w0,
   for any bus-timing-sensitive behavior."*
5. **The composed-AD mask** (ucore U5, F51): `tb_v30_core.sv` substituted the
   RETAINED A19-16 nibble across a HALT display, and the retained nibble happens
   to equal the correct value by construction — so a gate that BOTH cores failed
   read green for the life of the project, and only the fabric (where pads do
   not retain) could see it. The rule this produced: **a comparator that
   substitutes a value is asserting a mechanism, and the mechanism needs its own
   falsifier.** Mask removed; the ucore fixed, the archived core not.

Common root: a gate that enumerates the KNOWN and asserts consistency, but has
no census of the UNKNOWN.

### The SEVENTH sub-pattern, and what was built against it (SM3 sitting 14)

`ucore_provenance.md` records **seven incarnations of a second, distinct
pattern**: not "the gate is blind to the defect" but **"the gate ran against
bytes nobody proved were the bytes it named."** They are one bug — *a file path
is not an identity* — and the answer is `sw/artifact.py`, specified in
`docs/notes/artifact_receipt_layer.md` and migrated in §75.

**Four of the seven now have a mechanism** (1, 2, 3, 4 in §75.2's table).
**Three do not**, and two of those are a different kind of bug entirely
(engine selection, gate liveness). The seventh — INV-1, a capture whose
conditions were not part of its identity — is the golden-suite step and is
explicitly out of scope until it gets its own sitting.

**The rule this produced**: *a scorer must be able to name the receipt id of
every artifact it executed, and a number with no artifact id is not quotable.*
`sw/test_artifact.py` is the falsifier for the layer itself, because a
freshness layer that has never rejected anything would be incarnation eight.
