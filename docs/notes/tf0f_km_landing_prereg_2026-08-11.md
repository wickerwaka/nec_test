# PRE-REGISTRATION — LANDING `KM`, THE TF TRAP-BOUNDARY LAW

**Committed BEFORE the RTL is touched.** Everything below is registered; the
results sitting reports it as registered, never restated.

| | |
|---|---|
| tree | `fuzz-v2-on-relanding`, HEAD **`38a34dc70e`** (verified `git rev-parse`) |
| the law | `KM`, measured on silicon at `docs/notes/tf0f_cell_results_2026-08-11.md` (prereg `f08a597ed5`, amendment `c13ec814f3`) |
| scope | **offline only.** No board, no flash. Quartus IS in scope (G6, two draws). |
| the cell's RTL | `hdl/rtl/` and `hdl/tb/` are **byte-identical** between `c13ec814f3` (the cell's tree) and HEAD — `git diff c13ec814f3 38a34dc70e -- hdl/` touches only `nec_test_ucore.qsf`, which carries no RTL. The cell's core column is therefore this tree's core column, and §1.1 below MEASURES that rather than assuming it. |

---

## 0. THE ERRATUM AGAINST THE TASK BRIEF, STATED FIRST

The brief names *"predicted closures `fz2c/404041` and `fz2e/513019` (the pushed-PC
first-entry-deleted pair)"*. **The artifact says otherwise and the artifact wins.**
`tf0f_cell_prereg_2026-08-11.md` §5 P-1, committed before the board ran, registers

> `fz2e/501066` … is predicted to close; `fz2e/513019` carries the same `CORE +2`
> shape and is predicted to close; **`fz2c/404041` is predicted NOT to close by
> this alone**

and `tf0f_cell_results_2026-08-11.md` §9 P-1 reports that clause **UNCHANGED and
now better founded**. The registered pair is therefore **`fz2e/501066` +
`fz2e/513019`**, with `fz2c/404041` registered as a **MOVER, NOT A CLOSER**. This
document scores that, not the brief's.

---

## 1. THE LAW, AND WHERE THE ucore DIFFERS FROM IT

> **KM — SILICON.** An instruction contributes **ONE** TF boundary unit, plus
> **ONE MORE iff its opcode byte is not its first byte**. The extra unit is
> **one**, however deep the decoration and however many kinds of it.
>
> **KC — the `ucore` at HEAD.** The same predicate with the `0F` escape not
> counting as decoration.

Validated 16/16 (derivation) + **14/14 disjoint** (validation). One term is the
whole divergence.

### 1.1 The mechanism in this tree, read off the RTL — and why "units" are not "pops"

Three signals, all already present:

* `brk_smp_n = (q_pop && q_ripe && q_first) || (bnd_fire && irq_take)` —
  `v30u_eu.sv:3126`. This is the **SAMPLE**: one clock later,
  `if (brk_smp) brk_arm_n = brk_seen` (`:3089`).
* `brk_arm` is **ONE FLOP** (`:360`), assigned a LEVEL, not incremented.
* `bnd_fire = at_bnd && bnd_take` (`:1866`) with
  `at_bnd = bnd_row || bnd_epop || bnd_opc` and
  `bnd_opc = (st == S_OPC_POP) && bnd_armed` (`:1769`). This is the **TAKE**, and
  `bnd_armed` is set only at `S_INSTR_END` / the HALT wake — **never at a prefix
  hand-over**.

So the observable `pushed_off` is *"how many SAMPLE opportunities does the probe
offer before its own TAKE boundary?"*, collapsed to *"was the arm standing at the
probe's own retire?"* — **and it saturates because the arm is a BIT and the take is
at a retire.** That is why `pfx1 … pfx4` all read **2 units** on both engines
(§6(b) of the results: the pins announce 2 · 3 · 4 · 5, the boundary uses 2), and
it is the reason KM's saturation clause needs **no counter and no special case**:
this tree already implements saturation, for prefixes, structurally.

**What it does not implement is the `0F` escape's sample.** The escape's opcode
byte is popped in `S_EXT_POP`, and `q_first` (`:1905`) is
`(st == S_OPC_POP) ? pop_is_first : <E-row pops> ? 1 : 0` — **`S_EXT_POP` is not
in it**, so the escape's pop raises no `brk_smp`. Hence `KC`.

### 1.2 ⚠ THE NAIVE FIX IS NOT WRONG — IT IS A NO-OP, AND §8 OF THE RESULTS OVERSTATES ITS DANGER

`tf0f_cell_results_2026-08-11.md` §8 warns that *"setting `pop_is_first_n = 1'b1`
in `S_EXT_CHG1`"* would give a prefixed `0F` instruction three units. **Registered
correction, derived from the RTL before any edit:**

1. `pop_is_first` has exactly **two** readers in the tree —
   `assign q_first` (`:1905`) and the save-state read (`v30u_eu_ss_read.svh:98`).
   `q_first` consults it **only when `st == S_OPC_POP`**.
2. `S_EXT_CHG1`'s successor is `S_EXT_POP`, not `S_OPC_POP`. The next
   `S_OPC_POP` is the NEXT instruction's first-byte pop, where `pop_is_first` is
   already 1 from `S_INSTR_END` / `S_IRQ_D`.

So that edit changes **nothing at all** — neither the boundary nor the pins. It is
rejected here not as a regression but as **inert**, and §8's "three units" reading
is registered as **withdrawn** (it also could not have regressed the observable,
because §1.1's saturation is structural).

---

## 2. THE EDIT, EXACTLY, REGISTERED BEFORE IT IS MADE

**Two lines, one file, `hdl/rtl/ucore/v30u_eu.sv`. NO new flop. NO new
save-state address. NO opcode named.**

(a) beside `assign q_first`, a second consumer's term:

```systemverilog
wire q_bnd_pop = q_first || (st == S_EXT_POP);
```

(b) `:3126`, the sample:

```systemverilog
brk_smp_n = (q_pop && q_ripe && q_bnd_pop) || (bnd_fire && irq_take);
```

**The one honest sentence it implements:** *the boundary the BRK/TF arm samples
is the pop of the byte the LOADER DECODES — the instruction's first byte, the
byte a prefix hands over to, and the `0F` escape's second byte — whereas the
`QS` pins announce the pop that STARTS an instruction. Silicon already says
these are two different things, in both directions (§6(b): the pins announce
MORE than the boundary uses on a prefix stack, and LESS on a bare `0F`).*

Saturation is inherited, not added: §1.1.

### 2.1 THE QS-PIN CONSTRAINT IS MET BY CONSTRUCTION, AND THAT IS REGISTERED AS A CLAIM TO BE MEASURED

`q_first` is the ONLY term `v30u_biu.sv:767` reads for `QS_FIRST`/`QS_SUBSEQ`,
and it is **not edited**. `q_bnd_pop` is a new wire with **one** consumer,
`brk_smp_n`. The other two `q_first` consumers — `eu_halt` (`:2203`) and
`first_pop_seen_n` (`:3180`) — are **deliberately left on `q_first`**; they ask
"does this pop start an instruction?", which is the pin question, not the
boundary question.

### 2.2 WHY THE CHANGE IS INERT WHENEVER `PSW.TF` IS CLEAR

`brk_smp` has exactly one consumer: `if (brk_smp) brk_arm_n = brk_seen;`, and
`brk_seen = psw[FBRK] && brk_p[BRK_FLOOR-1]` (`:1812`). With `TF` clear,
`brk_seen` is 0 and an extra sample writes the value the flop already holds.
**Every golden suite, every HLT sweep and every lockstep form runs TF-clear**, so
§3's zero-delta predictions are structural, not hopeful.

---

## 3. REGISTERED PREDICTIONS

### 3.1 THE PRIMARY EVIDENCE LEG — the banked TF × `0F` cell (`sw/testdata/tf0f/`)

Scorer `sw/tf0f_cell.py score`, whose `KM` rows already carry a `*_core` leg.
The **board column is silicon and is NOT re-run** (no board this sitting); only
the `tb_sys ret` core column is re-taken, over **all 512 cells**
(`--strata` = every probe), and the pre-landing core column is archived
byte-identical first.

| # | clause | registered |
|---|---|---|
| **E-1** | `KM` vs **core**, DERIVATION | **16 / 16** (is 10/16; the six misses are `x13 x1b x18 x28 x33 y1e`) |
| **E-2** | `KM` vs **core**, VALIDATION | **14 / 14** (is 9/14; the five misses are `v_x39 v_x1f v_x10 v_x2a v_y13`) |
| **E-3** | the `diff` list (cells where chip ≠ core) | **0** (is 176 of 512) |
| **E-4** | the CONTROL BAND `nop clc incaw movi addrr` | chip = core, **480 traps**, UNMOVED |
| **E-5** | the NULL `notf` / `v_notf` | **0** vector-1 entries in all 32 cells, UNMOVED |
| **E-6** | the eleven bare-`0F` legs' `core_off` | each **−1**, onto the chip's value, and single-valued over its 96 traps |
| **E-7** | the prefixed-`0F` legs `z1b` `v_p2x` `v_p4x` — **THE SATURATION PROOF** | `core_off` **UNMOVED** at 9 · 10 · 12 (288 traps). *If any of these moves, saturation is not structural and the landing is REVERTED.* |
| **E-8** | every other leg's `core_off` | UNMOVED |
| **E-9** | `tf0f_cell.py qs`: `stream_diff` | **[]**, `compared` **480** |
| **E-10** | `qs` `pins_core`, every probe | **byte-identical** to the banked `qs.json` |
| **E-11** | `qs` `core_units` on the bare-`0F` legs | **1 → 2**, i.e. onto `chip_units` |

**E-1 … E-3 and E-7 and E-9/E-10 are the landing's own falsifiers.**

### 3.2 SEATS

Population and instrument: `sw/fz2_replay.py --leg ret`, the `tb_sys` faithful
replay, scored against the banked FLASH #17 socket rows.
⚠ **Every post-edit `fz2_replay` run needs `--no-fabric-era-guard`** — the guard
re-hashes the flashed bitstream's declared RTL inputs and this landing moves one
of them. It will be passed, and the override is printed by the tool and quoted
beside every number.

**Measured baselines at HEAD, before the edit** (both runs retained):

* `--all-failures` — **113 seeds, 113 fabric-FAIL, 113 replay-FAIL, agreement
  113/113 = 100.0 %, `first_bad` IDENTICAL on 113**, 0 errors.
* `--pass-sample 600` — **538 seeds, 538 fabric-PASS, 538 replay-PASS,
  538/538 = 100.0 %**, 0 errors.

| # | clause | registered |
|---|---|---|
| **S-1** | `fz2e/501066` | **CLOSES** (replay FAIL → PASS). Its probe is `0F 1B e8 4f`, which is the derivation leg `x1b` verbatim; chip pushes `0xede8`, core `0xedeb`, `CODE`-before-first-entry 61 / 62. One displaced boundary, streams re-align 87/87. |
| **S-2** | `fz2e/513019` | **CLOSES**. `CORE +2`, pushed-PC list = the chip's with the first entry deleted and every later entry byte-identical. |
| **S-3** | `fz2c/404041` | **MOVES, DOES NOT CLOSE.** Registered as a MISS in advance: its core leg retires a further far `CALL` past the displaced boundary and its streams re-align 2/342. A *close* here would be a surprise and would be reported as unregistered. |
| **S-4** | total ledger closures | **2 of 113**, and **P-3's clause stands: any two-digit seat gain from this mechanism is registered IN ADVANCE as unsupported.** 3 would already be at the top of the cell's own 2–3 estimate. |
| **S-5** | **THE REGRESSION BAR (P-4)** | **0 seeds lost.** Of the 538 replay-PASS seeds, **538 must still PASS**. Of the 113, **0 may have its `first_bad` move EARLIER**. |
| **S-6** | the count-movers (P-2) | **0 of them close.** Named at HEAD, before the edit, by re-deriving `fz2_a3d1d2_diagnosis_2026-08-11.md` §6.4's control with `tf0f_cell._seat_features`'s own extractor: **`fz2c/406063` · `fz2c/410047` · `fz2e/518039` · `fz2e/518053` · `fz2e/522019` · `fz2e/535027`**. ⚠ **THAT RE-DERIVATION READS `67 / 58 / 6 / 3` WHERE §6.4 READS `72 / 62 / 7 / 3`** — a different extractor over the same 654 captures (identical with the `IVT[1]` search widened to `0x00004` *and* `0x00006`). **REPORTED, NOT EXPLAINED**; §6.4's own falsifier is written against its own tool, not this one. What DOES reproduce exactly is the part this landing rests on: the **three clean movers, with §6.4's `CODE`-before-first-entry counts to the unit** — `fz2c/404041` 85/87, `fz2e/501066` 61/62, `fz2e/513019` 82/84. No gate below depends on 6 vs 7. |
| **S-7** | `fz2c/404040` | registered NON-MOVER. Measured at HEAD inside the 538: `tier soup`, `wrand`, `fabric_bad 0`, replay `bad 0` over `nrows 4063` / `win 2001`. Checked by name as well as in bulk. |
| **S-8** | `python3 sw/fz2_immaterial.py falsify` | **PASS**, G1–G8, **21 members / 92 non-members / 113 failures** — unmoved. It scores banked fabric captures against the ledger and is engine-free, so a move here would be an instrument finding, not a result. |

### 3.3 THE STANDING LADDER — every clause is ZERO DELTA, for §2.2's reason

| gate | registered |
|---|---|
| `gen_ucore_qsf.py --check` | up to date |
| `r7_lint.py` | **PASS**, 0 undeclared carriers, **3 tainted** (`eu_rd_edge`, `rd_edge_psw_take`, `rd_edge_take_raw`), **51 `stop` sites**, 0 violations, **no new exception** |
| `ss_lint.py --core ucore` | **PASS**, `SS_VERSION` **0x8D** / `SS_BIU_COUNT` **103** / `SS_EU_COUNT` **122** / `SS_COUNT` **226** / `SS_TAG` **0x8DE2**, **214** architectural flops (85 BIU + 129 EU), 0 UNMAPPED, 2 whitelisted. ⚠ **CLAUDE.md's `0x8C / 224 / 0x8CE0 / 212` is STALE for this branch tip** — measured at HEAD, before the edit. **THE EDIT ADDS NO FLOP AND NO ADDRESS: every one of these numbers must be UNCHANGED.** |
| `test_artifact.py` | **45/45** |
| `check_core.py --core ucore --opcodes all --cases 0` | **169,000 / 169,000** |
| the four HLT sweeps (⚠ `--waits 1/2/3`) | **97 · 93 · 45 · 44 = 279 / 283**, the four survivors the four family-D cells |
| `ulockstep.py --core ucore --golden all --cases 50` | **17,350 / 17,350** |

Any non-zero delta on this ladder REFUTES §2.2 and the landing is reverted.

### 3.4 G6 — SYNTHESIS

Registered before the build. The edit adds **one OR term** into a next-state
expression whose operands are all already there (`q_pop`, `q_ripe`, `q_first`)
plus `st`, a **register-only** term — it introduces no new `READY` carrier and
touches no `stop`.

* **Prediction: both draws land in the CONTROL band `38.4 – 42` MHz**, worst
  setup > 0, **TNS 0.000 setup AND hold on every domain**, 0 errors, 0 latches,
  0 `lpm_divide`.
* **HARD STOP AT 38.0 MHz**: if EITHER draw is below 38.0, the landing is
  **BOOKED, NOT LANDED**, and reverted.
* **BOTH DRAWS ARE QUOTED**, with receipts. One green build is not closure
  (`standing_gates.md` §A; the same tree has drawn 19.42 and 45.91 MHz).
* Context, quoted honestly: the immediately preceding sitting (N-1) *collapsed
  to 20.80 MHz on a pin-path edit*. **This edit is in the step/decode zone, a
  different cone** — which is a reason to expect the band, not a guarantee of
  it, and the STOP is what settles it.

### 3.5 ss EXPECTATION, STATED

**No flop is added.** `SS_VERSION` stays **0x8D**, `SS_COUNT` **226**, `SS_TAG`
**0x8DE2**, the census **214**. `v30u_ss_pkg.sv` is **not edited**. If the
implementation turns out to need a flop, this document is amended with the exact
free SSA and the version bump BEFORE the flop is written.

---

## 4. THE §86 ERRATUM, DRAFTED HERE AND LANDED WITH THE EDIT

To be appended to `ucore_provenance.md` as part of the landing:

> **§86 ERRATUM (KM, 2026-08-11).** §86 registers the sampling boundary as
> *"ONE predicate, the `QS = 1` opcode pop, because a prefix retires with its own
> F pop"*, and the RTL comment at `v30u_eu.sv:3335-3340` extends it *"…and the
> `0F` escape's first byte does too"*. The directed board cell
> (`docs/notes/tf0f_cell_results_2026-08-11.md`, FLASH #17, 512 cells, 2,880
> scored traps per engine, derivation 16/16 + disjoint validation 14/14)
> **corrects both halves IN COUNT, and leaves the first RIGHT IN KIND**:
>
> * *"a prefix retires with its own F pop"* is right in kind and **wrong in
>   count**. A prefix STACK contributes **ONE** extra boundary unit whatever its
>   depth — `pfx1…pfx4` read 7 · 8 · 9 · 10, i.e. two units at every depth, on
>   BOTH engines, 384 traps. The pins say otherwise and are not the boundary:
>   `pfx4` announces **five** `QS = 1` and uses **two** units.
> * *"…and the `0F` escape's first byte does too"* was **never implemented**
>   (`S_EXT_CHG1` sets nothing) and, as written, is the wrong byte: what silicon
>   counts is the escape's **SECOND** byte — the opcode — which the pins announce
>   **SUBSEQUENT** (`QS = 3`) on both engines.
> * therefore *"the sampling boundaries are simply the opcode pops the `QS = 1`
>   pins announce"* is **REFUTED IN BOTH DIRECTIONS, ENGINE-FREE** (§6 of the
>   cell: the pins announce MORE than the boundary uses on a prefix stack, and
>   LESS on a bare `0F`).
>
> **§86's landed RTL predicate — `brk_smp_n`'s SAMPLE side — is not otherwise
> touched.** The sample instant is unmoved (one clock past the pop), `brk_arm`
> is still one flop, the take is still `bnd_fire`, and the saturation KM
> requires was ALREADY structural in this tree because the arm is a bit and the
> take is at a retire. The landing adds ONE TERM: the escape's opcode pop is a
> sample. `pushed_off` measures the COUNT of units, not WHERE the second one
> sits (cell §5.2); *"the second boundary is at the opcode byte"* remains an
> INTERPRETATION and the `IRET`-setter cell that would resolve it is still not
> built.

---

## 5. STOP CONDITIONS

1. **E-7 moves** (a prefixed-`0F` leg's `core_off` changes) → saturation is not
   structural → REVERT, book, report.
2. **E-9 / E-10 move** (the QS stream or `pins_core` changes) → the pin
   constraint is broken → REVERT.
3. **Any §3.3 ladder delta** → REVERT.
4. **Either G6 draw < 38.0 MHz** → BOOKED, NOT LANDED.
5. **S-5 violated** (a passing seed lost, or a `first_bad` earlier) → REVERT.

A reverted probe is proved reverted (`git diff` empty against the pre-edit tree)
and said so.

## 6. WHAT THIS SITTING WILL NOT DO

* **No board.** No flash. `flash_log.jsonl` is not touched. Every fabric figure
  in the repo stays FLASH #17's and none is re-quoted against this tree.
* **No Codex delegation and no nested tasks** (task directive).
* The **board column** of `sw/testdata/tf0f/` is not re-run and not modified;
  only `core/` is re-taken, and its pre-landing state is archived byte-identical
  at `sw/testdata/tf0f/core-pre-km/` first.
* `timed_scenario`, `timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`
  are **not run and not quoted** — they die in `gen_seq._v1_anchor_stop` on this
  branch, engine-independently.
* No head-to-head between the ucore and the model is computed anywhere.
