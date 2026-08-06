# wrfuzz W3.5 — PRE-REGISTRATION: **the `ucore`'s LEG of W3.4's TAKE-CLOCK LAW**

**Task #44.  Branch `ucsim`, tree `cb4fad5e38`.  OFFLINE — NO BOARD, NO
FLASHING, `use_core` NEVER SET.**

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

---

## §0 ⚠ THE ORDERING, DECLARED — THE SITTING WAS INTERRUPTED MID-FLIGHT

This sitting was terminated by a connection error while this file was being
written, and the record says so rather than presenting a tidy sequence that did
not happen.  What was on disk at the interruption, and what it was:

* `hdl/rtl/ucore/v30u_eu.sv` and `v30u_eu_step.svh` carried the **`1BLD`
  measurement probe** — a `+brktrace` `$display` inside `\`ifndef SYNTHESIS`,
  five trace registers, and one assignment in `S_DECODE2`'s ONE_BYTE_LOGIC arm.
  **It is an INSTRUMENT, not a candidate landing**, and it drives nothing.
* **NO candidate had been landed and NO candidate had been scored.**  The order
  measurement → pre-registration → landing → scoring is therefore intact, and
  the coordinator's path **(a)** is the one taken: nothing to revert and
  re-apply, because the only edits were the ruler.
* The `sw/testdata/receipts/verilator_binary.jsonl` churn is the two probe
  builds (`a7e4335f62d1…`, `2ee02b6f5fd5…`) and one pre-probe build.  Those
  entries are the interruption's visible residue and are explained here.

**THE PROBE'S OWN INERTNESS IS MEASURED, THREE WAYS, BEFORE IT IS TRUSTED** —
this is the control that lets §1's measurement be read as a measurement of the
`ucore` and not of the ruler:

| control | pre-probe (HEAD) | probe build 1 | probe build 2 |
|---|---|---|---|
| `w32_launch --core ucore` EXACT / 184 | **77** | **77** | **77** |
| …its entry partition | `COUNT_DIFF 12 · DIFF_BOUNDARY 7 · NO_ENTRY_DIFF 118 · OPEN_BUS 196 · SAME_BOUNDARY 45 · UNREADABLE 2` | identical | identical |
| `timed_fuzz --core ucore --evt-replay` | — | — | **1,559 / 934 / 2,493**, the registered values to the seed |

⚠ **§1's arm/take measurement was RUN BEFORE THIS FILE EXISTED**, as the
sitting's work order directs (*"1. Measure first"*).  It is reported below as a
**RULER, NOT A SCORE**: it has no bar to hit, it reads the `ucore`'s own trace
stream plus the chip's `vec − 9`, and every number in it is stated as measured.
The bars that ARE pre-registered are §3's, and none of them has been run.

---

## §1 THE MEASUREMENT §7.8 ASKED FOR — **TAKEN, AND IT REFUTES §7.8's OWN STRUCTURAL READING**

`wrfuzz_provenance.md` §7.8 booked the `ucore` leg with a named trap, verbatim:

> *"the model's gate is `brk_arm_` and a `ONE_BYTE_LOGIC` form is never in the
> shadow class, so there `brk_arm_ == brk_take_`; in the RTL `irq_shadow` is a
> FLOP that may carry the PREVIOUS instruction's set, so `brk_arm` and
> `brk_take` are not interchangeable there.  **Measure it; do not assume it.**"*

New instrument **`sw/w35_take.py`** (`arm`), driving the `1BLD` probe over the
**23 P1 seeds**.  Per seed it reports, at the ONE_BYTE_LOGIC decode that owns
the contested take: `q_ripe_lead_n`, `brk_seen`, `brk_arm`, `irq_shadow_n`,
`brk_smp_n`; the sample clock, the flag-write clock, the take clock; and the
CHIP's take, which is the capture's own vector-read row **− 9** (§6.6 and §7.4's
constant, measured on 563 directed entries and all 23 P1 seeds).

**23 seeds, ZERO EXCEPTIONS on every row:**

| measured at the 1BL decode | value | n |
|---|---|---|
| `q_ripe_lead_n` — the queue is dry | **0** | 23/23 |
| **`brk_arm`** | **0** | **23/23** |
| **`brk_seen`** | **1** | **23/23** |
| `irq_shadow_n` | **0** | 23/23 |
| `brk_smp_n` — *the opcode pop rode THIS clock* | **1** | 23/23 |
| sample clock − decode clock | **+1** | 23/23 |
| **decode + 2 == the CHIP's take** | **MATCH** | **23/23** |

**WHAT THIS SAYS, AND IT IS NOT WHAT §7.8 GUESSED.**

1. **`S_DECODE2`'s 1BL arm RIDES THE OPCODE POP's OWN CLOCK.**  The chain
   `S_OPC_POP → S_DECODE → S_DECODE2` is zero-cost after the pop (and so is
   `S_EPOP → S_TAIL → S_INSTR_END → S_TAKE_OPC → S_DECODE → S_DECODE2`, which is
   the path all 23 actually take).  `brk_smp` — the sample instant §85.2a fixed
   at **pop + 1** — has therefore **not happened yet**.
2. **So `brk_arm` is 0 at the decode on 23 of 23, and the W3.4 mirror gate
   COULD NOT FIRE THERE.**  It fell through to `S_1BL_LEAD` and fired on the
   first clock the arm was up, at decode + 2, putting the take at decode + 4.
   For `wr1/201055` that is **2731** — **the reported number, explained to the
   clock.**  §7.8's reading that *"`S_1BL_CHG` and `S_OPC_POP` still stand
   between the retire and the boundary, which is the remaining 2 clocks
   exactly"* measured the consequence of a gate that landed one state too late,
   not a property of the boundary.
3. **`bnd_opc` IS ALREADY IN THE RIGHT PLACE.**  `S_1BL_CHG` (one clock) plus
   the zero-cost `S_INSTR_END` put the successor's `S_OPC_POP` at **decode + 2**
   — and decode + 2 **is** the chip's take on 23 of 23, which is §7.4's
   *"the chip's take is its own opcode pop + 2, WAIT-INDEPENDENT"* read off the
   `ucore`'s own state machine.  **§7.8's "second, structural change" — a
   separate boundary arm for the 1BL path beside `bnd_row`/`bnd_epop`/`bnd_opc`
   — IS NOT NEEDED, and this pre-registration retires that reading.**
4. **§7.8's NAMED TRAP IS ANSWERED AND IT IS INERT.**  `irq_shadow_n` is **0**
   at every one of the 23 decodes, because every pop state (`S_OPC_POP`,
   `S_EPOP`, `S_TAIL_POP`, `row_epop`) clears it and every instruction's opcode
   is popped by one of them.  On this path `brk_arm` and `brk_take` **are**
   interchangeable — the difference that mattered was never the shadow, it was
   the **arm's AVAILABILITY**.

**THE DEFECT IS ONE CLOCK OF ARM LATENCY AT ONE DECODE, AND NOTHING ELSE.**

---

## §2 THE CANDIDATES, WITH PER-CANDIDATE PREDICTIONS

All three are ONE TERM at ONE PLACE — the `S_DECODE2` ONE_BYTE_LOGIC arm's
`if (q_ripe_lead_n)`.  **`S_1BL_LEAD` IS DELIBERATELY NOT GATED IN ANY OF
THEM**, and that is the model's own shape: `wait_retire_lead()` tests
`brk_pending_` **once, at entry**, and then loops.  A gate on the wait's body
would be a second law.

| id | the term added to `q_ripe_lead_n` | prediction |
|---|---|---|
| **U-A** | `brk_arm` — **W3.4's mirror.  THE CONTROL AND THE ANTI-BAR.** | **REFUTED IN ADVANCE by §1**: the arm is 0 at the decode on 23/23, so the gate cannot fire there; take = decode + 4; `BRKT` on `wr1/201055` = **2731**; `wr1` = **78 / 184**.  ⚠ **A landing that reproduces 2731 IS THIS SITTING'S FAILURE MODE and is not to be taken.** |
| **U-B** | **`brk_seen`** — `psw[FBRK] && brk_p[BRK_FLOOR-1]`, the SAME wire the sample reads | take = decode + 2 = the chip's take on **23/23**; `BRKT` on `wr1/201055` = **2729**, which is the MODEL's own landed clock |
| **U-C** | `brk_smp_n ? brk_seen : brk_arm` — *"the arm as of the end of this clock"* | **identical to U-B on all 23** (`brk_smp_n` is 1 at every one of the 23 decodes).  It differs only where the decode does NOT ride the pop, and it drags `q_ripe`/`q_pop` into the `st_n` cone, which is the §52 timing-critical path |

**THE SELECTION RULE, FIXED HERE AND NOT AFTER THE NUMBERS:**
take **U-B**.  Move to **U-C** only if U-B **loses a seed or moves a first
divergence earlier** on any population in §3.  If both do, **book the honest
block with its measurement** and land nothing.  U-B is preferred on the standing
principle (one existing wire, no new cone, no flop) and on G6 risk.

*Falsifier for the law itself*: any capture in which a `ONE_BYTE_LOGIC` form
retiring into a BRK/TF take has its boundary later than its own opcode pop + 2
with a dry queue; or any `FA`/`FB`/`INT.FB` golden that moves when this gate is
armed.  (`FA`/`FB` fire no trap, so `brk_seen` is 0 in their goldens and they
are untouched by construction — the same argument FORM 7 rests on, and §3's
`Y-5` is where it is checked rather than asserted.)

---

## §3 THE BARS, REGISTERED BEFORE THE RUN

| id | bar | how it is scored |
|---|---|---|
| **Y-1** | the P1 TAKE CLOCK closes: `w35_take arm` reports **take == chip take on 23 / 23** | zero exceptions.  Any seed still late is a MISS, reported as registered |
| **Y-2** | `w32_launch --core ucore`: the `SAME_BOUNDARY ∧ n_ins = +1` class goes **23 → 0** | the class IS P1 |
| **Y-3** | ⚠ **NO LOSS.**  `wr1 --core ucore` EXACT **≥ 77**, **0 seeds lost**, **0 first divergences moved earlier**, seed by seed against `base_ucore.json` (measured on THIS tree) | hard bar.  **POINT PREDICTION: 88** = 77 + the 11 the model gained on the same 184 at W3.4 (73 → 84).  The prediction is reported against the outcome, not restated |
| **Y-4** | `BRKT` on `wr1/201055` is **2729** | the anti-bar is **2731** (§2 U-A).  Naming the failure number in advance is the point |
| **Y-5** | **the `ucore` ladder, every figure at its registered value** — `check_core --opcodes all --cases 0` **169,000**; `v0.1-w1`/`-w3` **1,200** each; `EB` w1 **200**; the four `evt` cells **200 / 1,200 / 200 / 1,200**; `w1evt-biased` **1,200**; block I/O **229,999**; `f4a_boundary` **160**; `f0lock_tranche` **400**; `check_boot --timed 220` and `--timed 400` **MATCH**; `timed_wvec_gate --core ucore` **88 / 88, +0.0 %**; `timed_enter_replay --core ucore` **154 ×5**; `timed_ins_replay --core ucore --raw` **1,312** and **2,624**; `check_ab_sim` **187 MATCH**; `--ss-sweep` modes 1/2/5 **80 / 24 / PASS**; `--ce-div 4 --ce-hold-check` **CE_HOLD_VIOL 0** | any figure down is a hard STOP |
| **Y-6** | the registered fuzz bank: `timed_fuzz --core ucore --evt-replay` REGISTERED **≥ 1,559**, EVT **≥ 934**, COMBINED **≥ 2,493**; `--seeddir b2-tranche` **≥ 181**; **0 lost seed by seed** against `base_bank_ucore.json`; `ENGINE ABORTS` **0** | monotone |
| **Y-7** | the SM trap cells: `sm3_tf_floor_cell score --core ucore --floors 4` — **121,860 rows, 0 row-diffs, EXACT on all 30**, surviving depth **{4}**, W-2 **22 / 22** | the ucore depth-4 cell exact, as the brief requires |
| **Y-8** | the shadow law's populations: `w31_shadow` unmoved — `MOV`sreg **69** g≥1 / **0** g0, `POP`sreg **6** / **0**, `PUSH`sreg **0** / **5**, `LES`/`LDS` **0** / **11**, all other **0** / **1,277** | the W3.1 law must not move |
| **Y-9** | `sw/ss_lint.py` **rc 0**.  **NO `SS_VERSION` BUMP IS EXPECTED** — U-B and U-C add a TERM to an existing next-state expression and **no flop**.  If a flop lands, `SS_VERSION` / `SS_COUNT` / `SS_TAG` bump and the census is re-reported | `219 addresses, 205 flops, 0 UNMAPPED, SS_VERSION 0x87` must be unchanged |
| **Y-10** | `sw/ulockstep.py --golden all --cases 50` **17,350 / 17,350** | |
| **Y-11** | **G6**: `sw/quartus_gate.py` — E1 `gen_ucore_qsf --check` green, **0 errors, 0 latches, 0 `lpm_divide`, Fmax ≥ 32 MHz, TNS 0.000 on every domain**, receipt written | the RTL-change → receipt rule |
| **Y-12** | the four HLT sweeps **279 / 283** and the S16 walk **1,320 / 1,371** (`sm3_s16_score --core ucore`) | must not move |

**⚠ WHAT IS NOT A BAR.**  `w32_launch`'s entry partition (`DIFF_BOUNDARY` /
`SAME_BOUNDARY` / `NO_ENTRY_DIFF` / `COUNT_DIFF`) is an **ATTRIBUTION counter
over a divergent-by-construction subset**, not a ratchet — `standing_gates.md`
says so of the whole 184.  W3.4 registered it in a bar and had to report it NOT
MET for a landing that lost nothing (§7.7).  It is **reported, not registered**,
here.

---

## §4 WHAT THIS SITTING WILL NOT DO

* **No board contact, no flashing, `use_core` never set.**  Every figure is
  offline.  The board still carries FLASH #10 and no fabric number is claimed.
* **The victory reserve (`k ≥ 300000`) is NOT touched.**
* **No memory file, no Codex.**
* `mc1/721`, `mc2/584`, the §5.6a/§5.6b modes, H3-B and the 8080/BRKEM family
  are NOT opened.
* **The model (`sim/`) is NOT touched.**  W3.4's landing is the semantic
  reference and this sitting is the `ucore`'s rendering of it, edge-for-edge on
  OBSERVABLE behaviour and not line-for-line on structure.
