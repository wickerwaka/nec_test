# THE ce/ce_half CONTRACT IS THE OPERATING ENVELOPE — **LANDED**

Pre-registration **`bb5433fe3e`** (`docs/notes/ce_contract_reland_prereg_2026-08-13.md`),
**committed BEFORE the first edit** — the prior wave's discipline erratum
(*"written before the edit but NOT COMMITTED before it, so it carries no commit
hash proving the ordering"*) is **not repeated**; this document cites that hash
and the ordering is checkable.

Landing **`638ed01450`**.  Tree at entry `58e082111b` (`master`), isolated
worktree.  **Offline.  Quartus through the distribution gate.  NO board, NO
flash.**

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §0 THE TWO RULINGS, ACKNOWLEDGED

**USER RULING, 2026-08-13 — Option 2:** *the ce/ce_half contract IS the ucore's
operating envelope.  Re-land the negedge removal and move the instruments
inside the contract.*  **1:1 is an unsupported mode.**

**SECOND USER RULING, 2026-08-13, received mid-sitting:** *"Unexplained deltas
are not a stop.  The issue is the tests have been incorrect.  We will land this
ce fix and then address the errors."*

**ACKNOWLEDGED AND APPLIED**, exactly as the coordinator scoped it: the
STOP-and-diagnose clause on re-registration deltas is REVOKED; the fix lands
regardless of the table; the table remains the deliverable with every delta
attributed *"div-1 instrument error, to be addressed post-landing"*; and a
delta on a **contract-legal** leg still gates.

**IT DID NOT COME UP.**  There is no delta to attribute anywhere — the
re-registration is zero-delta on every leg, on both bases, in both steps.  The
ruling's work list for the follow-up wave is **EMPTY**, and that is a
measurement, not a claim.

**THIRD USER RULING, 2026-08-13, received while the CONTROL sweep was on its
fourth fit:** *"Five seeds is too slow for this work.  In the future only run
more than one seed if the compile is explicitly being done to measure fmax."*

**ACKNOWLEDGED AND APPLIED IMMEDIATELY**, mid-run: the `--seeds 5` CONTROL
sweep was **KILLED where it stood** and the RETENTION leg was run as a **single
draw**.  This is a **landing** wave — the compile verifies the landing
(PASS / TNS / no collapse); **it is not an Fmax measurement and this document
makes no Fmax claim.**  Both G6 figures below are quoted as **`draw@seed<S>`**,
never as a band.  `standing_gates.md` §A carries the amendment: multi-seed
sweeps are reserved for compiles whose explicit purpose is measuring Fmax; the
worst-of-N machinery stays for when it is asked for.

⚠ **THREE CONTROL DRAWS EXIST BECAUSE THE SWEEP HAD ALREADY TAKEN THEM.**
Seeds 1, 2 and 3 completed before the kill; they are RETAINED at
`sw/testdata/g6dist/cereland-control-3of5-interrupted/` under a directory name
that says what happened.  **The quotable figure is `draw@seed1`.  No band, no
spread and no worst-of-N is computed or claimed from three interrupted draws.**
The receipts' own `label` field still reads `…-control-n5`, because that is what
the invocation asked for before the ruling arrived, and a receipt records what
was asked.

---

## §1 HEADLINE

| | |
|---|---|
| the re-land | **`v30u_biu.sv` `always @(negedge clk)` → `always @(posedge clk)`** — one word, same `ce_half` enable, **no new register**, save-state address/bit/meaning unchanged.  `grep -rn negedge hdl/rtl/ucore/` now returns **comments only** |
| the instruments | `check_core` default `--ce-div` **1 → 4**, 1/2/3 and odd **REFUSED** (exit 2); the TB train's `ce_half` moves to the **CPU-cycle midpoint**; **nine** hard-coded `+ce_div=1` sites migrated; `tb_chain_lfsr`'s train made contract-legal |
| the gate | `hdl/tb/ce_contract_check.sv` **`$fatal`s on C-a, C-b and C-c**, in three testbenches, **non-vacuity demonstrated on all three clauses** |
| **the re-registration** | **ZERO DELTA.  Not one figure moved**, old basis (`--ce-div 1`) vs new (`--ce-div 4`), across BOTH steps, with `--ce-div 8` as a cross-divisor control |
| the contract-legal legs | **BYTE-IDENTICAL across the RTL edit** — `tb_sys` 306 seeds / ~1.24 M rows, 2,200 + 528 directed cells, `fz2_immaterial` G1-G8 |
| the SDC | `ce_half → ce` **TIGHTENS** `-setup 3 -hold 2` → `-setup 2 -hold 1`; the **`k = 0.5` class CEASES TO EXIST**; class labels become structural |
| G6 | **CONTROL `draw@seed1` 42.06 MHz / +7.473 ns · RETENTION `draw@seed1` 43.30 MHz / +8.156 ns**, both **PASS**, TNS **0.000** setup AND hold on every domain of both, 0 errors / 0 latches / 0 `lpm_divide`, `.rbf`s differ.  **ONE draw each, by ruling — NOT an Fmax claim** |
| the SDC, **measured on the netlist** | `DEFAULT` k = **1.0000** · `CE4` **4.0000** · `INTO` **2.0000** (was 1.5) · `OUTOF` **2.0000** (was 2.5) · **`ENABLE` 1.0000** (was 0.5) — **P-4b and P-4c MET, 4 decimal places** |
| `test_quartus_gate` | **252 / 252** (was 240 / 240), negedge-era artifacts asserted **REFUSED BY ERA** |
| **owed** | **FLASH #21 clauses (v) and (vi).**  This moves a pin in time.  Nothing here has been on a board |

---

## §2 ⚠ AMENDMENT A-1 — THE BRIEF SAID `--ce-div 2`; THE CONTRACT SAYS **4**

**This is the sitting's one deviation from the brief.  It was registered in the
pre-registration BEFORE any edit, with its derivation, and it moves the scorer
FURTHER inside the contract — never less far.**

`hdl/nec_test.sdc` states the contract as three premises, and its own arc
arithmetic uses all three:

> **C-a** `ce` and `ce_half` are never asserted on the same clock.
> **C-b** successive enable assertions are **>= 2 clocks apart**.
> **C-c** `ce -> ce` is **>= 4 clocks**.

C-b is about **enable assertions**, not `ce` assertions — the SDC's
*"`ce -> ce_half` launch n+1, latch **n+2.5** (C-b)"* is only true if the next
assertion after a `ce` in cycle *n* is at cycle *n*+2 at the earliest.

**`tb_v30_core` wrote `ce_half <= ce`.**  So `ce_half` was **always the fabric
clock immediately after `ce`** — idle gap **0** — at `ce_div` 1, 2, 3, 8 or 64
alike.  At `ce_div = 1` it was *additionally* a C-a violation.  **Moving the
divisor alone fixes C-a and leaves C-b broken**, and the `$fatal` this wave was
required to add would have fired on the briefed `--ce-div 2`.  Landing div 2
would have re-created, in a second form, the exact failure the wave exists to
remove.

**THE FIX IS THE PHASE, NOT THE DIVISOR — AND IT MAKES THE TB MATCH THE THING
THAT GETS FLASHED.**  `nec_bus.sv:175-176` puts the two enables **half a CPU
cycle apart** (`CE = tick_rise` at `div_cnt == div_max`, `CE_HALF = tick_fall`
at `div_cnt == half - 1`) — four clocks each way at the divider of record.
`tb_v30_core` had **never had the phase relationship of the integration it
stands in for.**

| `ce_div` | `ce` at | `ce_half` at | `ce→ce_half` | `ce_half→ce` | `ce→ce` | verdict |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | — | — | — | 1 | **C-c violated** (no `ce_half` at all) |
| 2 | 0 | 1 | 1 | 1 | 2 | **C-b and C-c violated** |
| 3 | 0 | 1 | 1 | 2 | 3 | **C-b and C-c violated** |
| **4** | 0 | 2 | **2** | **2** | **4** | **LEGAL — the contract MINIMUM** |
| 8 | 0 | 4 | 4 | 4 | 8 | LEGAL (the `nec_bus` phase exactly) |

**`nec_bus` agrees**: at `cfg_clk_div = 2` its `tick_fall` and `tick_rise` are
adjacent.  **4 is the minimum legal divisor of the INTEGRATION, not a
preference of this testbench.**

---

## §3 THE INSTRUMENT MIGRATION — TOOL → OLD → NEW

Audit `grep -rn "ce_div\|ce-div" sw/ hdl/tb/` (excluding `sw/testdata/`).

| tool | old | new |
|---|---|---|
| `hdl/tb/tb_v30_core.sv` (the default itself) | **1** | **4**, and `$fatal` on `< 4` or odd |
| `sw/check_core.py` | `--ce-div` default **1** | **4**; **1/2/3 and odd REFUSED, exit 2, clause cited** |
| `sw/ulockstep.py:318` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/sm3_s16_score.py:124` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/sm3_s16_fabric.py:205` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/sm3_famb_survey.py:96` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/sm3_haltsupp.py:142` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/f4a_boundary_battery.py:74` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/char_divergence.py:23` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/uarch.py:58` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `sw/uscope.py:83` | `+ce_div=1` | `CE_DIV_DEFAULT` |
| `check_boot`, `check_seq`, `check_ab_sim`, `timed_fuzz`, `emit_suite`, `qdepth_probe`, `tb_bootrun`, `timed_wvec_gate`, `class5_hext`, `pi1a_trace`, `check_fuzz_bank`, … | **no plusarg — silently inherited 1** | **inherit 4** by the default flip |
| `hdl/tb/tb_chain_lfsr.sv` | `ce@k`, `ce_half@k+1`, `ce@k+2` | **`ce@k`, `ce_half@k+2`, `ce@k+4`** |
| `hdl/tb/tb_sys.sv`, `tb_ab.sv`, `tb_harness.sv` | `nec_bus` div 8 — already legal | unchanged; `tb_sys` gains the checker |
| `hdl/rtl/core/` (ARCHIVED FSM core) | — | **untouched.**  Its on-demand gates will now run at div 4; **no FSM figure is re-registered here** |

⚠ **`tb_chain_lfsr` VIOLATED ITS OWN HEADER CLAUSE (b).**  Its header states the
assumables as *"(b) >= 1 idle cycle between assertions"* and its train asserted
`ce_half` on the clock immediately after `ce` — zero idle cycles — reaching
`ce → ce` = 2 where C-c requires 4.  **A stimulus harness may not be the one
instrument that disagrees with the contract it says it is built to.**

---

## §4 THE CONTRACT AS A GATE — AND ITS NON-VACUITY

`hdl/tb/ce_contract_check.sv`, `ifndef SYNTHESIS`, instantiated in
`tb_v30_core` (its own train), `tb_sys` (**`nec_bus`'s own train** — the
control that says the contract is satisfiable by the thing that gets flashed)
and `tb_chain_lfsr`.  It `$fatal`s — not `$error` — because a train that leaves
the envelope has invalidated every row downstream of it, and continuing would
produce a SCORED NUMBER taken outside the contract, which is the thing that
happened.

**NON-VACUITY, MEASURED ON ALL THREE CLAUSES**, against scratch trees in
`~/.cache/ucsimt-tmp/` built with the divisor floor removed and the checker
untouched:

| tree | invocation | fires | exit |
|---|---|---|---|
| new train, floor removed | `+ce_div=1` | **C-c** — `ce_contract_check.sv:78`, *"two `ce`s with NO `ce_half` between them"* | **134** (abort) |
| new train, floor removed | `+ce_div=2` | **C-b** — `:84`, *"enable assertions on ADJACENT fabric clocks (0 idle clocks between them)"* | **134** |
| new train, floor removed | `+ce_div=4` | *(nothing)* | **0** |
| **HISTORICAL train restored** (`ce_half <= ce`), floor removed | `+ce_div=1` | **C-a** — `:73`, *"`ce` and `ce_half` asserted on the SAME fabric clock"* | **134** |
| **HISTORICAL train restored**, floor removed | `+ce_div=8` | **C-a** (at the init clock, before C-b can be reached) | **134** |

**The fourth row is the load-bearing one: the gate would have caught the
instrument the tree actually used.**  ⚠ Reported precisely: at `ce_div = 1` on
the NEW train the first clause to fire is **C-c**, not C-a, because the new
train never asserts `ce_half` at that divisor; C-a is the OLD train's div-1
signature and is demonstrated on the old train.

`check_core`'s refusal was exercised directly: `--ce-div 1` and `--ce-div 2`
both **exit 2** and print the three clauses, the ruling and the file to read.

---

## §5 THE RE-REGISTRATION TABLE — **ZERO DELTA**

Measured in **two steps so attribution is free**: STEP 1 is the instruments
alone with the RTL untouched; STEP 2 adds the one-word RTL edit.  The OLD BASIS
column was measured on this worktree at `58e082111b`, unmodified, **before the
pre-registration was committed and before any edit**.

| leg | OLD BASIS `--ce-div 1` | STEP 1 (`--ce-div 4`, old RTL) | STEP 2 (`--ce-div 4`, **new RTL**) | Δ |
|---|---|---|---|---|
| `check_core --opcodes all --cases 0` | **169,000 / 169,000** | **169,000 / 169,000** | **169,000 / 169,000** | **0** |
| the same at `--ce-div 8` (cross-divisor control) | — | — | **169,000 / 169,000** | **0** |
| `--opcodes 8F.0` | 500 / 500 | 500 / 500 | 500 / 500 | 0 |
| `s10-hltsweep-w0 --waits 0` | 97 / 97 | 97 / 97 | 97 / 97 | 0 |
| `s10-hltsweep-w1 --waits 1` | 93 / 95 | 93 / 95 | 93 / 95 | 0 |
| `s13-hltsweep-w2 --waits 2` | 45 / 46 | 45 / 46 | 45 / 46 | 0 |
| `s13-hltsweep-w3 --waits 3` | 44 / 45 | 44 / 45 | 44 / 45 | 0 |
| **the four sweeps** | **279 / 283** | **279 / 283** | **279 / 283** | **0** |
| `f4a_boundary --waits 0` | 160 / 160 | 160 / 160 | 160 / 160 | 0 |
| `f0lock_tranche --waits 0` | 400 / 400 | 400 / 400 | 400 / 400 | 0 |
| `v0.1-w1 --waits 1` | 1,200 / 1,200 | 1,200 / 1,200 | 1,200 / 1,200 | 0 |
| `v0.1-w3 --waits 3` | 1,200 / 1,200 | 1,200 / 1,200 | 1,200 / 1,200 | 0 |
| `v0.1-w1 --opcodes EB` | 200 / 200 | 200 / 200 | 200 / 200 | 0 |
| `v0.1-w0evt` / `-w1evt` / `-w2evt` / `-w3evt` | 200 · 1,200 · 200 · 1,200 | 200 · 1,200 · 200 · 1,200 | 200 · 1,200 · 200 · 1,200 | 0 |
| `v0.1-w1evt-biased` | 1,200 / 1,200 | 1,200 / 1,200 | 1,200 / 1,200 | 0 |
| `check_boot --timed 220` / `--timed 400` | MATCH / MATCH | MATCH / MATCH | MATCH / MATCH | 0 |
| `ulockstep --golden all --cases 50` | 17,350 / 17,350 | 17,350 / 17,350 | 17,350 / 17,350 | 0 |
| `sm3_s16_score --core ucore` | `busstat_other` 24 · `ARCH` 27 | identical | identical | 0 |
| `check_ab_sim --core ucore` | MATCH 187 | MATCH 187 | MATCH 187 | 0 |
| `ghost_launch_law score` | 200 / 200 = 100.0 % | identical | identical | 0 |
| `qdepth_probe` | `rdq` 0:264 1:49 2:34 · `rd_done` 0:102 1:245 | identical | identical | 0 |
| `r7_lint` | PASS, 51 `stop` sites, 0 violations | PASS | PASS | 0 |
| `ss_lint --core ucore` | `SS_COUNT` **232**, **221** flops, **3** whitelist, **0** UNMAPPED | identical | identical | 0 |
| `test_artifact` | 45 / 45, non-vacuous | 45 / 45 | 45 / 45 | 0 |
| `gen_ucore_qsf --check` | up to date | up to date | up to date | 0 |
| `ucrom_mif_check` (needs a `db` on disk — run after G6) | *not runnable on a fresh worktree* | — | **PASS**, 1,028 words identical | — |
| `check_core --core fsm --opcodes 8F.0` (ARCHIVED core, SMOKE ONLY) | — | — | **500 / 500** — it builds and runs at the new default; **no FSM figure is re-registered** | — |
| `check_core --ce-div 8 --ce-hold-check` (B8, F3AA, HLT.INT) | — | — | **`CE_HOLD_VIOL 0`**, 1,200 / 1,200 | — |

**DEFERRED, AND REPORTED AS DEFERRED, NOT AS PASSING:** the **block-I/O leg**
(23 `v0.3` forms, 229,999 cycles).  It was not run in this sitting; nothing here
says what it reads.

**NOT RE-DERIVABLE, AND SAID SO:** `ucrom_mif_check` reports *"NOTHING TO CHECK
— no `hdl/db`"* on a fresh worktree; it needs a build still on disk and is run
after G6 (§6).

### 5.1 WHAT THE ZERO MEANS, AND WHAT IT DOES NOT

It means the ucore's per-CPU-cycle behaviour **is independent of the enable
train** across the whole golden corpus, which is the property the contract
asserts and which nothing in the tree had ever measured.  It does **not** mean
the div-1 basis was harmless in principle — it means the harm it could have
done did not happen to land on any scored row, and the tree now cannot go back
there.

---

## §6 THE CONTRACT-LEGAL LEGS — BYTE-IDENTICAL ACROSS THE RTL EDIT (P-2)

These are scored on `tb_sys`, the Verilated `system_large` with `nec_bus` at
the divider of record — the integration that gets flashed, and the one platform
`--ce-div` cannot reach.

| leg | result |
|---|---|
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | **306 seeds** (106 fabric-FAIL, 200 fabric-PASS), `first_bad` IDENTICAL on 106, **every measured field and every agreement table byte-identical**.  The ONLY diff lines are the era guard's own bookkeeping (`84/88 → 82/88` inputs hashing, `MOVED hdl/rtl/ucore/v30_core.sv`, `MOVED hdl/rtl/ucore/v30u_biu.sv`), the binary receipt, the tree hash and wall-clock timings |
| `ie_pinfall_cell core` | **2,200 cells**, **13 / 13 data files IDENTICAL** |
| `ghost_pred_cell core` | **528 cells**, **133 / 133 data files IDENTICAL** |
| `fz2_immaterial falsify` | **G1-G8 PASS**, output **byte-identical** |
| `check_ab_sim --core ucore` | MATCH 187, unmoved |

⚠ **THE CELLS WERE COMPARED BY DECOMPRESSED CONTENT, NOT BY `.gz` BYTES.**
gzip embeds an mtime, so a `.gz` `sha256` diff is not evidence of a data change
— and on a first pass every one of them differed while the data did not.  The
only fields that moved in either `manifest.json` are `receipt`, `ts` and
`seconds`, which are provenance.

⚠ **THE `fz2_replay` ERA OVERRIDE IS STATED, NOT WORKED AROUND.**  Both legs ran
`--no-fabric-era-guard`.  The guard **already refused on the PRE-edit tree**, so
this is a BEFORE-vs-AFTER comparison **on one tree** and **no fabric claim is
made from it**.

### 6.1 `chain_lfsr_gate` — THE SIGNATURES MOVED TWICE, AND BOTH MOVES ARE ATTRIBUTED

**PASS on every run.**  Registered in advance (prereg §7 P-3a) that the
signatures WOULD move, because the gate accumulates over **every core output on
every fabric clock** — a per-fabric-clock signature is **not** a pin-identity
bar, and registering it as one was the prior wave's own mis-registration.

| | HEAD (old train, old RTL) | STEP 1 (new train, old RTL) | STEP 2 (new train, **new RTL**) |
|---|---|---|---|
| seed 1 | `2138eabbcea8796c` | `2e94e1b264e01e40` | **`fd126e6583256ad0`** |
| seed 2 | `fad6633fc67db084` | `9198e9039e5107cc` | **`74625bb8de1fdfbf`** |
| seed 3 | `f90444c46a589273` | `29de335252e25aec` | **`b978ae684e51f13f`** |
| seed 4 | `5404f98f2d8bc343` | `1e772122bca04728` | **`58c8078932e27d9c`** |
| `ce_clocks` | 72,744 / 72,744 / 72,598 / 72,602 | **53,341 / 53,294 / 53,234 / 53,291** | identical to STEP 1 |
| `CHAIN_DEPTH_MAX` / `entry_st` / `coincide` | 6 / 25 / 0 | **6 / 25 / 0** | **6 / 25 / 0** |
| the `live` bus census (`fpops` `qpops` `INTA` `IOR` `IOW` `HALT` `CODE` `MEMR` `MEMW`) | — | **IDENTICAL seed for seed** | **IDENTICAL seed for seed** |

**`ce_clocks` falls ~27 % because the minimum train period grew from ~2+g to
~4+g fabric clocks** — fewer CPU cycles fit in 400,000 fabric clocks.  **The
liveness census is nevertheless identical to the event**, on all four seeds,
through both changes.  That is the measured form of *"per-CPU-cycle behaviour
is independent of the enable train"*, on a stimulus with nothing in common with
the golden suite: arbitrary LFSR bytes, LFSR `READY`, LFSR `INT`/`NMI` and
LFSR-drawn CE gaps.

---

## §7 THE SDC, RE-DERIVED — AND THE `$v30u_half` QUESTION, ANSWERED

| arc | before | after | change |
|---|---|---|---|
| `ce → ce` | launch n+1, latch n+5 (C-c) = 4.0 → `-setup 4 -hold 3` | unchanged | — |
| `ce → ce_half` | launch n+1, latch m+2.5 = **1.5**, spelled `-setup 2` | launch n+1, latch m+1, m ≥ n+2 = **2.0**, spelled `-setup 2` | **same spelling, different meaning** |
| `ce_half → ce` | launch m+0.5, latch m+3 = **2.5** → `-setup 3 -hold 2` | launch m+1, latch p+1, p ≥ m+2 = **2.0** → **`-setup 2 -hold 1`** | **A TIGHTENING** |
| `div_cnt → t1_half2` (ENABLE, unexcepted) | **0.5** | **1.0** | **the `k = 0.5` class CEASES TO EXIST** |

**Deleted because the thing they described is gone:** the half-edge accounting
paragraph (*"for a NEGEDGE destination the Nth latch edge is at N−0.5 …"*), and
the *"one arc … deliberately NOT excepted"* block's *"TRUE half period"*
content — **its disposition survives**, the arc is still not excepted, and the
reason is now *"the default is correct"* rather than *"correct and tight"*.
**Retained as dated HISTORY:** the Phase-1 *"⚠ WHAT THIS FIXED"* block, because
a ratchet is only readable against its own history.

### 7.1 THE `$v30u_half` NAME HAZARD — THE BRIEF'S QUESTION

The brief asked: *with the negedge gone, can the collection itself be DELETED
(no negedge flop → no half class)?*

> **REGISTERED IN ADVANCE (prereg §6.1) AND CONFIRMED: NO, AND THE HAZARD
> SURVIVES.**  The collection exists because `t1_half2` is the one flop gated by
> the **OTHER ENABLE**, not because it was negedge-clocked.  `ce_half → ce` is
> **2.0** periods where `ce → ce` is **4.0**, so it must still be REMOVED from
> `$v30u_ce` — leaving it in would hand a 2.0-period arc a 4.0-period
> exception, the optimistic direction.  The exact-name `~DUPLICATE` hazard is a
> property of the NAME, was not created by the edge and is not removed by
> removing it.  **It stays BOOKED**, with a paragraph in `nec_test.sdc` beside
> the collection as its record and `sta_negedge_probe.tcl`'s collection-size
> line as its live falsifier.

### 7.2 THE CLASS LABELS ARE STRUCTURAL NOW, AND OLD ARTIFACTS CORRECTLY REFUSE

`DEFAULT` · `CE4` · `INTO` · `OUTOF` · `ENABLE`, with the `k` each should
measure moved into `quartus_gate.py`'s **checked** `nominal` table
(`CE4` 4.0 · `INTO` **2.0** · `OUTOF` **2.0**; `DEFAULT` and `ENABLE` are 1.0).
Three permanently-wrong labels would have flagged two rows off-class on **every**
draw, and a permanently-firing flag is a flag nobody reads.

⚠ **EVERY NEGEDGE-ERA `truefmax` ARTIFACT NOW REFUSES TO PARSE, AND THAT IS THE
CORRECT BEHAVIOUR** — `truefmax_complete()` returns False and
`core_domain_fmax()` returns **no figure with the missing classes listed**.
*Absence must not read as data.*  `sw/test_quartus_gate.py` is re-registered
accordingly (§8).

---

## §8 `test_quartus_gate` — THE ERA RE-REGISTRATION — **252 / 252**

It was **240 / 240** and it **DIED** on the class rename, with a `KeyError` in
Q16.  *That is the contract working, not damage*: Q14 and Q16 were bound to
`docs/notes/t1half2/ctl_baseline.truefmax.txt`, a **negedge-era** artifact.

* **The three negedge-era artifacts are KEPT and are now ASSERTED TO BE REFUSED
  BY ERA** — `ctl_baseline`, `ret_baseline` and
  `sw/testdata/intcone/fixtures/ctl_seed1_offclass.truefmax.txt`.  Each still
  parses to *something* (they are real artifacts), none is
  `truefmax_complete`, and each yields **no core-domain figure with `missing`
  naming exactly `CE4` / `INTO` / `OUTOF`**.
* **The live checks run against `sw/testdata/cecontract/fixtures/ctl_seed1.truefmax.txt`
  — THIS WAVE'S OWN G6 CONTROL seed-1 draw**, a real artifact of the posedge
  tree, not a hand-edited copy of a negedge one.
* **§7's SDC re-derivation is now an ASSERTION, MEASURED ON THE NETLIST** and
  not argued: `DEFAULT` **k = 1.0000** · `CE4` **4.0000** · `INTO` **2.0000**
  (was 1.5) · `OUTOF` **2.0000** (was 2.5) · **`ENABLE` 1.0000 — the `k = 0.5`
  class is GONE**, its ceiling moved **90.91 → 141.20 MHz** on this draw, and
  it still does not bind (141.20 vs the design's 42.06).
* ⚠ **ONE DEMONSTRATION GOT WEAKER, AND IT SAYS SO IN ITS OWN OUTPUT.**  The
  only REAL draw in the tree exhibiting an off-class row is the negedge-era
  `intcone` fixture, which now refuses.  Until a posedge-era draw exhibits the
  condition, the detector is exercised on a **SYNTHETIC** perturbation of the
  new fixture — a unit test of the comparison, **not** a measurement that the
  condition occurs.  Printed `[SYNTHETIC]`, with a standing instruction to
  freeze the first real one that appears and delete the paragraph.

**No Quartus is needed to run it.**

---

## §9 G6 — **ONE DRAW PER CONFIGURATION, PAIRED, AND NOT AN Fmax CLAIM**

Per the third ruling (§0): a landing wave's compile **verifies the landing**.
Both figures are **`draw@seed1`**.  **No band, no spread, no worst-of-N, and no
Fmax claim is made anywhere in this document.**  §74.4 still governs — one green
build is not closure, and the same tree has drawn 19.42 and 45.91 MHz.

### 9.1 CONTROL — `draw@seed1`, receipt `96f9e6481642494e…`

| | |
|---|---|
| verdict | **PASS** |
| **E3** `divclk` Fmax ≥ 32.0 | **42.06 MHz** |
| **E4** worst setup > 0 every domain | **+7.473 ns** |
| **E5** TNS 0.000 setup AND hold, every domain | **0 violations** (hold slacks +0.253 / +0.264 / +0.357 / +0.426) |
| **E2** 0 errors, every stage Successful | **0** |
| latches / `lpm_divide` | **0 / 0** |
| ALMs | **10,053 / 41,910 (24 %)**, fit registers 5,953 |
| **E8** the fitter honoured `--seed=1` | **asked 1 · command line 1 · `Fitter Initial Placement Seed` row 1** |
| **E1** `gen_ucore_qsf --check` | clean |
| input manifest | **`002f2fa4728ecac9…`**, 88 files |
| core-domain | **62.39 MHz**, class **`CE4`**, `k = 4.0` — *NOT a gate, no bar reads it* |

⚠ **Two more CONTROL draws exist and are RETAINED, NOT QUOTED AS A BAND** —
seeds 2 (**44.30** / +8.677 / 5,964 regs) and 3 (**43.96** / +8.504 / 5,965
regs), both **PASS**, both TNS 0.000.  They are what the `--seeds 5` sweep had
finished before the ruling killed it.

### 9.2 THE SDC RE-DERIVATION, **CONFIRMED ON THE NETLIST** — P-4b, P-4c, P-4d

Measured to four decimal places on the CONTROL draw, from the analyser's own
launch/latch arithmetic and not from this wave's reasoning:

| class | measured `k` | was | ceiling on this draw |
|---|---:|---:|---:|
| `DEFAULT` | **1.0000** | 1.0 | 42.06 MHz *(the design's bound)* |
| `CE4` | **4.0000** | 4.0 | 62.39 |
| `INTO` | **2.0000** | **1.5** | 124.12 |
| `OUTOF` | **2.0000** | **2.5** | 183.00 |
| **`ENABLE`** | **1.0000** | **0.5** | **141.20** *(it was 90.91)* |

* **P-4b MET — THE `k = 0.5` CLASS IS GONE**, measured, and its ceiling left the
  ladder (90.91 → 141.20 MHz).
* **P-4c MET** — `INTO` and `OUTOF` both measure exactly 2.0.
* **P-4d MEASURED: `off_class` is EMPTY on this draw** (`k_measured` =
  `CE4` 4.0 · `INTO` 2.0 · `OUTOF` 2.0, all equal to nominal).  ⚠ **The
  `upper_bound` caveat does NOT lift, and that is correct**: it is a structural
  property of a slack-ordered `get_timing_paths` query, true on any tree with
  more than one `k`, and this wave did not change it.  A clean `off_class` is a
  measurement about **this draw**, not a repair of the query.
* **P-4h MET** — the input manifest `002f2fa4728ecac9…` differs from both the
  prior wave's `b7b5dff2353c4747…` and L1's `d47c1d003d64c4c5…`.  That is the
  check that the edit reached the compiler.
* **P-4g** — ALMs **10,053** against the L1 CONTROL band 10,085-10,154, **−0.3 %**.

### 9.3 RETENTION — `draw@seed1`, receipt `d51eb456617a18dd…`

| | |
|---|---|
| verdict | **PASS** |
| configuration | **`RETENTION (X1_AD_RETENTION=1)` — DERIVED from the flow and map reports, never from the flag** (**E-6 satisfied**) |
| the compiler's own line | `quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore` |
| **E3** `divclk` Fmax ≥ 32.0 | **43.30 MHz** |
| **E4** worst setup > 0 every domain | **+8.156 ns** (then +9.140 · +13.415 · +24.213) |
| **E5** TNS 0.000 setup AND hold, every domain | **0 violations**, all four domains, both directions |
| **E2** 0 errors, every stage Successful | **0** |
| latches / `lpm_divide` | **0 / 0** |
| ALMs | **10,079 / 41,910 (24 %)**, fit registers 5,819 |
| **E7** inputs re-hashed after the last stage | `pre == post == 002f2fa4728ecac9…`, **`n_moved` 0** |
| **E1** `gen_ucore_qsf --check` | clean |
| `.rbf` | **`a9667cf1aa6d3715…`** — **DIFFERENT** from CONTROL's `3d4700c0b0453ee3…` (**E-9 satisfied**: the check that the macro reached the compiler) |
| `.sof` | `ecdabe0f56f0ae69…` |

⚠ **NO `truefmax` ARTIFACT ON THIS LEG, STATED RATHER THAN LEFT BLANK.** The
class probe is **sweep-only** in `quartus_gate.py` (`--no-truefmax` is
documented *"sweep only"*), so a single draw records `truefmax: null`.  **§9.2's
per-class `k` measurements are the CONTROL draw's and are quoted as such**;
nothing here measures the retention build's class ceilings.

⚠ **THE RETENTION-VS-CONTROL SIGN IS INVERTED AGAIN: +1.24 MHz.**  Reported,
**not explained**, and **not a delta anyone may compute from a draw pair** —
`standing_gates.md` §A governs.

### 9.3a ⚠ A REPRODUCIBILITY DATAPOINT WORTH MORE THAN EITHER FIGURE

Both draws reproduce the **reverted** wave's seed-1 draws **to the digit and to
the bitstream byte**:

| | this wave | `t1_half2_posedge_results_2026-08-13.md` §4.1/§4.2, seed 1 |
|---|---|---|
| CONTROL Fmax / setup / ALMs | 42.06 / +7.473 / 10,053 | **42.06 / +7.473 / 10,053** |
| RETENTION Fmax / setup / ALMs | 43.30 / +8.156 / 10,079 | **43.30 / +8.156 / 10,079** |
| CONTROL `.rbf` | `3d4700c0b0453ee3…` | **`3d4700c0b0453ee3…`** |
| RETENTION `.rbf` | `a9667cf1aa6d3715…` | **`a9667cf1aa6d3715…`** |

The prior wave built the identical posedge RTL and the identical SDC
re-derivation before reverting them, so this says the re-land **restored that
tree exactly** — measured, not asserted.  ⚠ It also says the `.rbf` **is**
reproducible seed-for-seed across independent sittings on this design, which
`standing_gates.md` §A's *"Analysis & Synthesis is not reproducible run to run"*
warning is about **combinational counts**, not bitstreams; the two statements do
not conflict and neither is generalised here.

### 9.3b ⚠ **R-4 IS NOT EVALUABLE AS WRITTEN, AND THAT IS REPORTED, NOT WAIVED**

The pre-registered revert trigger **R-4** is written on a `worst-of-5`
(*"CONTROL < 39.71, RETENTION < 41.50"*).  **This wave takes ONE draw per
configuration by the third ruling**, so there is no `worst-of-5` to test it
against.  **R-4 is therefore NOT EVALUABLE**, and it is reported that way rather
than declared passed on a single favourable draw.

What IS known, and it is not reassurance: **the prior wave's `worst-of-5` on
this identical RTL was CONTROL 42.06 / RETENTION 41.49, and its RETENTION leg
FIRED R-4 by 0.01 MHz at seed 4.**  That draw exists, it is this RTL's, and
nothing in this sitting removes it.  It was **not attributed to the edit then**
(CONTROL moved the other way and both spreads widened) and it is not attributed
to the edit now.  **The landing does not rest on R-4**; it rests on §5's
zero-delta table, §6's byte-identical contract-legal legs, and the two PASS
draws' bars.

### 9.4 ⚠ ONE E1 STOP FIRED AND WAS OBEYED, AND IT IS A REAL FINDING ABOUT THE FLOW

The first RETENTION invocation **REFUSED at E1** —
*"`hdl/nec_test_ucore.qsf` is STALE — regenerate it"* — and built nothing.
The cause is the **declared §70.7 exemption itself**: Quartus APPENDS the
MiSTer pin assignments to the revision `.qsf` during a compile, so **any
interrupted or completed build leaves the file modified**, and the next gate's
E1 sees a `.qsf` that is no longer a faithful derivative of `nec_test.qsf`.
Restored from git, `gen_ucore_qsf --check` clean, re-run.  **Recorded, not
worked around**: the gate was right to refuse, and this is why the `.qsf` is
never committed out of a build tree.

---

## §10 FLASH #21 — THE DEBT, NOW REAL

The prior wave wrote these clauses and did not owe them, because nothing landed.
**This wave landed, so they are OWED.**

> **(i)** first light `check_ab_hw` **MATCH 800 ×3**.
> **(ii)** directed pin-level cells — a named sample of `tf0f`, `ie-pinfall`
> and the 528-cell ghost-pred column — **chip** columns UNCHANGED (socket leg,
> cannot move), **core-vs-chip** reproducing **this wave's offline column cell
> for cell** (the columns are in the tree and are byte-identical to the pre-edit
> ones, §6).
> **(iii)** the full fz2 corpus with its named non-movers.
> **(iv)** `use_core=0` chip proof **MATCH 800** after everything, `div_guard`
> **PINNED** on every probe, `board_idle()` clean.
> **(v) ⚠ THE WRITE-T1 ROWS MUST BE BYTE-IDENTICAL ON SILICON.**  The turnaround
> is the ONLY pin transition this wave moves, so the MEMW/IOW T1 rows of the
> fabric captures are its whole silicon surface.  **Any diff there is this
> wave's and nothing else's.**
> **(vi) ⚠ AND THE TURNAROUND MUST BE VISIBLE AT THE CORRECT INSTANT IN THE
> TWO-SAMPLE ROWS.**  `nec_bus` banks two AD samples per CPU clock; the ADDRESS
> sample (`ad_early`, at `tick_fall`) must still carry the **address** and the
> DATA sample (`tick_rise`) must still carry the **write word**, on **100 %** of
> write T1s in the captured population.  The offline argument predicts this
> exactly; **the fabric leg is where it is confirmed or refuted, because that
> argument is about a rig and silicon is not a rig.**

**A rig-side-only redesign would have owed NO silicon bar.  This wave chose the
pin move, so the bar is owed BY CHOICE and is recorded as such.**

---

## §11 WHAT THIS SITTING DID NOT DO

* **No board, no flash, no Codex, no nested tasks** — as directed.
* **The block-I/O 229,999-cycle leg was NOT run** (§5).  DEFERRED, not passing.
* **The ARCHIVED FSM core was not touched and none of its figures re-measured.**
  Its on-demand gates will now run at `--ce-div 4` like everything else; what
  they read there is unknown and unclaimed.
* **The D-cone shadow falsifier's non-vacuity is STILL NOT ESTABLISHED.**  It
  was re-planted with the flop, it never fired on any leg — but no perturbation
  was built that would make it fire, so *"it never fired"* remains weaker
  evidence than it looks.  Booked, unchanged, and **not quoted as evidence**.
