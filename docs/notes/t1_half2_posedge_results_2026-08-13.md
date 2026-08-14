# `t1_half2` POSEDGE — **NOT LANDED**, AND THE REASON IS A RIG FINDING

Pre-registration `docs/notes/t1_half2_posedge_prereg_2026-08-13.md`.
Tree `0f9f165382` (`master`), isolated worktree.
**Offline.  Quartus through the distribution gate.  NO board, NO flash.**

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

⚠ **ONE DISCIPLINE ERRATUM, STATED FIRST BECAUSE IT IS ABOUT THIS DOCUMENT'S
OWN EVIDENCE.**  The pre-registration was **WRITTEN before the edit** (it is the
sitting's first artifact and every number in its §7 was measured at HEAD before
a byte of RTL moved) but it was **NOT COMMITTED before the edit**, so it carries
**no commit hash proving the ordering**.  Under this repo's own rule — *a number
with no artifact id is not quotable* — the reader should treat §7's predictions
as pre-registered on the strength of the sitting's transcript and nothing
stronger.  Both documents are committed together, after the fact, and this
paragraph is why.

---

## §0 HEADLINE

**The registered revert rule FIRED on the first ladder leg.  The RTL, the SDC
and the instrument changes are all REVERTED.**  What the miss uncovered is worth
more than the change was:

> **`sw/check_core.py` — the scorer for all 169,000 golden cases, the four HLT
> sweeps, the `evt` cells and `ulockstep` — runs the ucore at `--ce-div 1`,
> where `hdl/tb/tb_v30_core.sv` asserts `CE` and `CE_HALF` ON THE SAME CLOCK.
> That is precisely what premise **C-a** of the ce/ce_half portability contract
> forbids.  The core has been scored outside its own declared operating
> contract since that contract was written (USER RULING, 2026-08-12), and
> NOTHING SAW IT — because the negedge flop supplies the mid-clock event a 1:1
> enable train cannot.**

| | |
|---|---|
| `check_core --opcodes all --cases 0` — the REGISTERED invocation, `--ce-div 1` | **104,628 / 169,000** (cycles 104,628, arch 168,999) — **P-1 MISSED** |
| the SAME suite, SAME binary, at `--ce-div 8` | **169,000 / 169,000** (cycles 169,000, **arch 169,000**) |
| `NMI.B8` at `--ce-div` 1 / 2 / 3 / 8 | **0/200** · **200/200** · **200/200** · **200/200** |
| `fz2_replay --leg ret` — `tb_sys`, the REAL integration at div 8 | **IDENTICAL: 306 seeds, 1,243,278 replayed rows** |
| `ghost_pred_cell core` — 528 directed cells on `tb_sys ret` | **IDENTICAL, 528 cells, `sha256` included** |
| `ie_pinfall_cell core` — 2,200 directed cells on `tb_sys ret` | **IDENTICAL, 2,200 cells, `sha256` included** |
| where the break lives | **`ce_div == 1` ONLY** — the degenerate 1:1 train.  It is a **C-a violation**, not a divider size and not a margin |
| disposition | **REVERTED** |

**The change is behaviourally identical on every contract-legal platform,
including the exact integration that gets flashed, and it breaks exactly one
thing: the scorer that runs the core outside the contract.**

---

## §1 THE MECHANISM, EXACTLY

`hdl/tb/tb_v30_core.sv:67-85`:

```systemverilog
//   +ce_div=1 (default): CE and CE_HALF high every clk = the pre-CE core
integer ce_div = 1;
initial if (!$value$plusargs("ce_div=%d", ce_div)) ce_div = 1;
wire    ce = !ss_park && (ce_cnt == 0);
logic   ce_half = 1'b1;
always @(posedge clk) begin
    if (!ss_park) ce_cnt <= (ce_cnt >= ce_div - 1) ? 0 : ce_cnt + 1;
    ce_half <= ce;
end
```

At `ce_div == 1`, `ce` is high on **every** fabric clock and `ce_half` is `ce`
delayed one clock, so it is high on every fabric clock too.  **One fabric clock
IS one CPU clock**, and there is no clock edge between `ce_half` and the end of
the cycle.

* **Negedge form**: `t1_half2` flips at the negedge *inside* the T1 clock, so
  the WRITE's AD address→data turnaround lands mid-cycle.  Correct.
* **Posedge form**: `t1_half2` flips at the posedge *ending* the T1 clock — one
  CPU cycle late, when `ad_o` has already moved to the PS/data mux.  **The T1
  data half never appears on AD at all.**

The first-divergence census says exactly that with no interpretation needed:
**100 % of the failing cells are the `data` field.**

```
0F12:      129/500  first-div: (20,'data')x104, (18,'data')x83, (21,'data')x71
INT.90:      0/200  first-div: (40,'data')x108, (36,'data')x50, (42,'data')x21
F2AA:      125/500  first-div: (11,'data')x184, (9,'data')x100, (10,'data')x91
HLT.RES:   200/200                      <- the one HLT form with no write
```

**ONE MECHANISM, NO SECOND CLASS.**  `HLT.RES` — the HALT form that performs no
write — is 200/200.  The **two** HLT sweeps that were run score **49/97** (w0)
and **49/95** (w1), and `standing_gates.md` records `HLT.RES` as **49 · 49** on
those two suites: the survivor count matches the no-write form's cell count
exactly on both.  ⚠ That is an inference from two matching counts, **not a
cell-by-cell verification** — the surviving cells were not enumerated, and the
other two sweeps (`s13-w2`, `s13-w3`) were not run at all.

### 1.1 THE ONE ARCHITECTURAL FAILURE IS DOWNSTREAM OF THE SAME MECHANISM

`arch` reads **168,999 / 169,000** — a single case, in `0F12` (arch 499/500).
An architectural divergence from a pin-timing change would be a second
mechanism, so it is chased rather than waved past: `tb_v30_core`'s **memory is
the bus's other party**, and it stores what the core drove.  With the T1 data
half missing, one case's write commits the wrong word to `mem[]`, a later read
returns it, and the architectural state follows.  **It is the same single
mechanism reaching the register file through the testbench's memory**, and it
disappears with the mechanism: at `--ce-div 8` arch is **169,000 / 169,000**.

### 1.2 THE THRESHOLD IS `ce_div >= 2`, WHICH IS THE CONTRACT'S OWN MINIMUM

Measured on `NMI.B8`, all four points:

| `--ce-div` | `CE`/`CE_HALF` relationship | score |
|---:|---|---|
| **1** | **asserted on the SAME clock — C-a violated** | **0 / 200** |
| 2 | one clock apart | **200 / 200** |
| 3 | one clock apart | **200 / 200** |
| 8 | one clock apart | **200 / 200** |

**This is not a margin and it is not a divider-size effect.**  At `ce_div = 2`
there is exactly one fabric clock between `ce_half` and the end of the CPU
cycle, and one is enough: the turnaround lands strictly inside the cycle and the
two forms are indistinguishable.  The break is a step function at the single
point the contract excludes.

---

## §2 THE PRE-REGISTRATION'S OWN PROOFS — WHICH ONE FAILED, AND WHY

**Neither §2 nor §3 of the prereg was refuted, and neither was the cause.**

* **§3, D-cone stability: HELD.**  The cone is register-only, and the
  simulation-only shadow falsifier planted beside the flop
  (`assert (cond === t1h2_negd)`) **never fired** on any leg that ran —
  169,000 golden cases at `--ce-div 1`, 169,000 more at `--ce-div 8`, 306
  `tb_sys` programs, 528 + 2,200 directed cells, and 4 × 400,000 fabric clocks
  of LFSR bytes.  ⚠ Its non-vacuity is **NOT established**: no perturbation was
  built that would make it fire, so "it never fired" is weaker evidence than it
  looks.  Booked as such.
* **§2, the hold windows: SOUND, AND ITS PREMISE WAS FALSE ON THE SCORER.**
  §2.3(b) reads *"By C-b there is no enable assertion in cycle `n_k`+1"* — it
  names its own premise.  At `ce_div = 1` there is one, on every clock.

> **THE OMISSION, NAMED RATHER THAN SOFTENED: the pre-registration proved the
> change against the platform the design is SPECIFIED for (`nec_bus`, div 8,
> and `nec_test.sdc`'s C-a/C-b/C-c) and never asked what the platform the design
> is SCORED on actually does.  Those turned out to be different platforms.
> THAT DIFFERENCE IS THE FINDING.**

The prereg's §9 scope list even says *"NOT touched: `hdl/tb/*`"* — which was
true, and was exactly the wrong place to stop looking.

---

## §3 THE LADDER, AS REGISTERED

**Legs that ran on `tb_v30_core` at the REGISTERED `--ce-div 1`:**

| leg | registered | measured | |
|---|---|---|---|
| `check_core --opcodes all --cases 0` | 169,000 | **104,628 / 169,000** | **MISSED** |
| HLT sweep `s10-hltsweep-w0 --waits 0` | 97 | **49 / 97** | **MISSED** |
| HLT sweep `s10-hltsweep-w1 --waits 1` | 93 | **49 / 95** | **MISSED** |
| `NMI.B8` (representative) | 200 | **0 / 200** | **MISSED** |

**The remaining `tb_v30_core` legs — the two `s13` sweeps, the four `evt`
cells, `v0.1-w1`/`-w3`/`EB`/`w1evt-biased`, `ulockstep`, `check_boot`,
`sm3_s16_score`, `check_ab_sim`, `ghost_launch_law` — WERE NOT RUN.**  The
revert rule fires on *any* row, the mechanism was already established and
categorised to a single field over the whole 169,000-case batch, and running a
doomed hour of the ladder to re-observe one mechanism is not a survey.  **They
are recorded as NOT RUN, not as passing and not as failing.**

**Legs that ran on `tb_sys` (the real integration, `nec_bus` at div 8):**

| leg | registered | measured | |
|---|---|---|---|
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | 306 seeds byte-identical | **IDENTICAL: 306 seeds, 1,243,278 replayed rows**, `tables` block identical, every `sys` and banked reference field unmoved | **MET** |
| `ghost_pred_cell core` (528 cells) | identical | **IDENTICAL, 528 cells, every measured field** | **MET** |
| `ie_pinfall_cell core` (2,200 cells) | identical | **IDENTICAL, 2,200 cells, every measured field** | **MET** |

Both `fz2_replay` legs ran `--no-fabric-era-guard`; the guard already refused on
the **pre-edit** tree, so this is a BEFORE-vs-AFTER comparison on one tree and
**no fabric claim is made from it**.  Both `before` columns were captured on
this worktree at HEAD, because the committed tables are another era's
(`adcone_l1_results_2026-08-13.md` §1.3 books the `ie-pinfall` one as STALE on
`master`).

**Structural gates — all UNCHANGED, as registered (P-3 MET):**

| gate | registered | measured |
|---|---|---|
| `r7_lint` | PASS, 0 violations | **PASS**, 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations |
| `ss_lint --core ucore` | `SS_COUNT` 232, 221 flops, 3 whitelist, 0 UNMAPPED | **exactly that** — the posedge form adds **no register** |
| `ucrom_mif_check` | PASS | **PASS**, 1,028 words identical |

### 3.1 ⚠ ONE BAR I MIS-REGISTERED, REPORTED AS REGISTERED

**P-2's `chain_lfsr_gate` clause was the wrong shape and it is a MISS by my
error, not by the RTL's.**  The gate accumulates a signature over **every core
output on every fabric clock**, so it is *by construction* the one instrument in
the tree that samples inside the half-period window this change moves.  A
per-fabric-clock signature **must** move when a pin moves by half a fabric
clock, even under a perfectly CPU-cycle-identical change.

Measured, all four seeds moved — and **every structural quantity is identical
seed for seed**:

| | before | after |
|---|---|---|
| seed 1 signature | `2138eabbcea8796c` | `e45c12542641125a` |
| seed 2 | `fad6633fc67db084` | `b8ef0f3726afb3d2` |
| seed 3 | `f90444c46a589273` | `7700da7fa41ae0f6` |
| seed 4 | `5404f98f2d8bc343` | `ddf21bcf9bf4dc7a` |
| `CHAIN_DEPTH_MAX` / `entry_st` / `coincide` | 6 / 25 / 0 | **6 / 25 / 0** |
| `ce_clocks`, all eight gap counts | — | **identical on all four seeds** |
| `live` bus census (`fpops` `qpops` `INTA` `IOR` `IOW` `HALT` `CODE` `MEMR` `MEMW`) | — | **identical on all four seeds** |

So the gate's own charter — the `CHAIN OVERFLOW` bound — is untouched, and the
signature move is a **positive control**: it is the instrument confirming the
pin moved where the design said it would.  **Registering it as a pin-IDENTITY
bar was a mis-registration**, in the shape §82.4 already has a precedent for.
*A signature is only an identity bar at the granularity it samples.*

---

## §4 G6 — THE TIMING MODEL'S OWN FALSIFIER

**This is the half of the wave that is worth keeping even though the RTL is
not**, because it is a MEASUREMENT of the SDC re-derivation §5 of the
pre-registration made, taken on the netlist and not argued.

Both configurations, `--seeds 5`, one shared `quartus_map` per configuration,
from a clean `db`.  Input manifest **`b7b5dff2353c4747…`** — **different** from
L1's `d47c1d003d64c4c5…`, which is the check that the edit reached the compiler
(**P-4h MET**).

### 4.1 CONTROL — `worst-of-5@seeds{1,2,3,4,5}`, record `e6eccba417c122aa…`

| seed | Fmax | worst setup | ALMs | core-domain | class |
|---|---:|---:|---:|---:|---|
| **1** | **42.06** | **+7.473** | 10,053 (24 %) | 62.39 | CE4 |
| 2 | 44.30 | +8.677 | 10,085 (24 %) | 58.42 | CE4 |
| 3 | 43.96 | +8.504 | 10,014 (24 %) | 61.87 | CE4 |
| 4 | 43.85 | +8.446 | 10,053 (24 %) | 63.57 | CE4 |
| 5 | 46.20 | +9.603 | 10,027 (24 %) | 60.68 | CE4 |

> **WHOLE-DESIGN `worst-of-5` = 42.06 MHz** (seed 1, `k = 1.0`), bound by
> `ucdecode M10K → nec_bus|ad_in_q[8]` — median 43.96, best 46.20, **spread
> 4.14**.  *THE PROMOTION GATE.*
> **CORE-DOMAIN `worst-of-5` = 58.42 MHz** (`CE4`, `k = 4.0`, seed 2), bound by
> `ucdecode M10K → v30u_eu|Mux58~0` — median 61.87, best 63.57.  *NOT a gate;
> no bar reads it.*

`verdict PASS`, all five draws PASS, **TNS 0.000 setup AND hold on every
domain**, 0 errors / 0 latches / 0 `lpm_divide`, E7 `n_moved` 1 /
`moved_offending` 0 (the one declared §70.7 `.qsf` exemption), E8 5/5, E10 N=5.

### 4.2 RETENTION — record `00d397da91f83e0a…`

| seed | Fmax | worst setup | ALMs | core-domain | class |
|---|---:|---:|---:|---:|---|
| 1 | 43.30 | +8.156 | 10,079 (24 %) | 61.12 | CE4 |
| 2 | 42.49 | +7.714 | 10,066 (24 %) | 60.37 | CE4 |
| 3 | 43.79 | +8.416 | 10,073 (24 %) | 60.67 | CE4 |
| **4** | **41.49** | **+7.150** | 10,033 (24 %) | 58.77 | CE4 |
| 5 | 45.49 | +9.268 | 10,066 (24 %) | 62.25 | CE4 |

> **WHOLE-DESIGN `worst-of-5` = 41.49 MHz** (seed 4, `k = 1.0`), bound by
> `ucdecode M10K → nec_bus|ad_in_q[15]` — median 43.30, best 45.49, **spread
> 4.00**.
> **CORE-DOMAIN `worst-of-5` = 58.77 MHz** (`CE4`, `k = 4.0`, seed 4), bound by
> `ucdecode M10K → v30u_eu|opc_base[3]~DUPLICATE`.

`verdict PASS`, all five draws PASS, TNS 0.000 setup AND hold on every domain,
0 errors / 0 latches / 0 `lpm_divide`, E7 1 moved / 0 offending, E8 5/5, E10
N=5.  The receipt **self-labels `RETENTION (X1_AD_RETENTION=1)`, DERIVED from
the reports**, and every `.rbf` differs from the CONTROL draw of the same seed
(seed 1: `3d4700c0b0453ee3…` vs `a9667cf1aa6d3715…`) — **E-6 and E-9 both
satisfied, P-4f MET.**

### 4.2a ⚠ **THE SECOND REVERT TRIGGER ALSO FIRED — BY 0.01 MHz**

The registered rule reads: *"either configuration's `worst-of-5` collapses more
than 2.0 MHz below its band floor (CONTROL < 39.71, **RETENTION < 41.50**)"*.

**RETENTION measured 41.49.  41.49 < 41.50.  IT FIRES.**

It is reported at the registered precision and **not rounded in the wave's
favour**.  Two things follow and neither softens it:

* **The revert was already determined by §3**, so this trigger changes no
  decision — it is recorded because a pre-registered bar that fires must be
  reported whether or not it is load-bearing.
* **It is NOT evidence that the edit cost 2 MHz.**  CONTROL moved the other way
  (41.71 → 42.06, **up**) and BOTH spreads widened (CTL 2.65 → 4.14, RET 1.71 →
  4.00).  `standing_gates.md` §A's own findings govern: the bands overlap, no
  control-vs-retention delta may be computed from a draw pair, map variance is
  measured at ~2.3 MHz, and *the same tree has drawn 19.42 and 45.91*.
  **Recorded, not explained, and not attributed to the edit.**

### 4.3 THE PREDICTIONS, SCORED

| id | registered | measured | |
|---|---|---|---|
| **P-4a** | CONTROL ≥ 39.06, RETENTION ≥ 41.79 (band floor minus its own spread) | CONTROL **42.06** — and it is INSIDE the L1 band [41.71, 44.36] itself, not merely above its floor · RETENTION **41.49 — BELOW the 41.79 floor by 0.30 MHz** | ⚠ **CONTROL MET · RETENTION MISSED**, §4.2a |
| **P-4b** | **the `k = 0.5` class is GONE** — `ENABLE` measures `k = 1.0000` on 10 of 10 draws | **CONTROL 5/5 at exactly `k = 1.0000`**, and the class's ceiling moved **90.91 → 112.10 (worst) / 141.20 (median) / 168.86 (best) MHz**.  RETENTION **5/5 at exactly `k = 1.0000`**, ceiling 142.13 / 160.54 / 185.08 MHz | **MET, 10 of 10** |
| **P-4c** | `INTO` and `OUTOF` both measure 2.0 | **CONTROL 5/5: `INTO` 2.0000, `OUTOF` 2.0000** (they were 1.5 and 2.5).  RETENTION **5/5: 2.0000 and 2.0000** | **MET, 10 of 10** |
| **P-4d** | ⚠ *measure, do not assume*: does `t1_half2~DUPLICATE` still contaminate the `CE4` row? | **`off_class` is EMPTY on all five CONTROL draws** — `CE4` reads `k = 4.0000` on every one, against **3 of 10 contaminated draws** on the negedge tree at `intcone`.  **REPORTED, NOT EXPLAINED** — the SDC's exact-name hazard is a property of the NAME and this wave did not touch it, so a clean run is a *measurement about these draws*, not a repair | **MEASURED: 0 of 10 contaminated** — §4.4 |
| **P-4e** | every draw a G6 PASS, E7/E8/E10 clean, TNS 0.000 setup AND hold | **10/10 PASS**, TNS 0.000 setup AND hold on every domain of all ten draws, 0 errors / 0 latches / 0 `lpm_divide`, E7 1 moved / **0 offending** on both sweeps, E8 5+5, E10 N=5 | |
| **P-4f** | the RETENTION receipt self-labels, `.rbf` differs (E-6 / E-9) | **MET** — the receipt self-labels `RETENTION (X1_AD_RETENTION=1)`, DERIVED from the reports, and every `.rbf` differs from the CONTROL draw of the same seed | |
| **P-4g** | ALMs within ±2 % of the L1 band | CONTROL 10,014-10,085 against L1's 10,085-10,154 (**−0.7 %**) · RETENTION 10,033-10,079 against L1's 10,134-10,194 (**−0.9 %**) | **MET** |
| **P-4h** | input manifest differs from `d47c1d003d64c4c5…` | **`b7b5dff2353c4747…`** | **MET** |

### 4.4 ⚠ THE `upper_bound` CAVEAT DOES **NOT** LIFT, AND THAT IS CORRECT

The pre-registration allowed that it *might*.  It does not, and the reason is
worth stating because it separates two things that were bundled:

* **The `~DUPLICATE` CONTAMINATION did not occur** — `off_class` empty on every
  draw taken here.
* **The caveat is NOT about the duplicate.**  Its text is *"each class row is
  that collection's worst BY SLACK, not by slack/k, so a row can return a path
  carrying a different exception than the class collects"* — a **structural**
  property of a slack-ordered `get_timing_paths` query, true on any tree with
  more than one `k`.  `core_domain_fmax()` sets `upper_bound: True`
  unconditionally and **this wave did not change that.**

**So: the contamination is absent on these draws; the upper bound stands.**
A clean `off_class` is evidence about ten draws, not a repair of the query.

### 4.5 WHAT THE TIMING RESULT MEANS FOR THE REVERT

**Nothing.**  P-4b confirms §5's derivation exactly — the arithmetic in
`nec_test.sdc` was right and the enable arc's budget doubles — and the wave is
reverted anyway, because the revert rule is written on §7.1's ladder and the
ladder is not a timing measurement.  **A correct derivation does not buy a
behaviour change; it only means the derivation was correct.**

The arc was already fourth-ranked at 90.91 / 83.43 MHz
(`t1_half2_results_2026-08-13.md` §3.2/§7.2).  Taking it to 112-169 MHz moves
nothing: the design binds at 42.06 in the DEFAULT class, on a cone with one
endpoint in the rig, on **5 distinct endpoint pairs over 5 draws**.

---

## §5 THE FINDING, WRITTEN SO IT SURVIVES THE REVERT

### 5.1 `tb_v30_core --ce-div 1` VIOLATES C-a, AND IT IS THE DEFAULT

The USER RULING of 2026-08-12, quoted verbatim in `hdl/nec_test.sdc`:

> *"With respect to ce/ce_half, you are not allowed to make assumptions based on
> how you are currently setting those clock enables. All you can assume is the
> ce and ce_half will not be asserted at the same time and there will be a one
> cycle gap between each assertion."*

`tb_v30_core` at `ce_div = 1` asserts them **at the same time, on every clock**.
Under Reading B the design is *entitled* to assume that never happens; the
scorer does it on every one of 169,000 cases.

**This is live in the tree today and is INDEPENDENT of this wave.**  Nothing
here proposes changing the default — that is a decision about the tree's primary
comparator and it belongs to the coordinator.  What this wave establishes is
that the contradiction is **load-bearing**: it is what makes `t1_half2`'s edge
un-removable.

**FALSIFIER, cheap and standing — AND IT WAS RUN, ON THE REVERTED TREE:**

```
python3 sw/check_core.py --core ucore --opcodes all --cases 0 --ce-div 2
TOTAL: 169000/169000 full (cycles 169000, arch 169000)
```

**The unmodified core IS contract-portable, and the 169,000 ratchet holds
byte-for-byte on a contract-legal train.**  Measured post-revert, alongside the
`--ce-div 1` control which reads **169,000/169,000** as registered.

That is the load-bearing fact for whoever rules on §5.3: **moving
`tb_v30_core`'s default off `ce_div = 1` costs this ratchet NOTHING.**  It is
a re-registration whose largest single leg is already known to be a no-op — so
the decision is about the other legs and about principle, not about losing
169,000 cases.  ⚠ **It is ONE leg.**  The sweeps, the `evt` cells, `ulockstep`,
`check_boot`, the S16 walk and `check_ab_sim` were **not** re-measured at
`--ce-div 2` and nothing here says what they would read.

### 5.2 THE NEGEDGE FLOP IS NOT WASTE — IT IS THE MODEL OF THE FALLING EDGE

The standing design principle decides how to read this, and it reads the
opposite way from the brief's premise.

At `ce_div = 1` the fabric clock **is** the CPU clock, so `t1_half2`'s negedge
**is the CPU clock's own falling edge** — which is literally where the part
performs the turnaround, and `ce_div = 1` is therefore the mode in which the
model is most faithful, not least.  The divided-clock integration approximates
that falling edge at `ce_half`+0.5 fabric periods.

> **The negedge flop is the one place in the design that says "mid-CPU-clock",
> and removing it costs the core the ability to be clocked 1:1.  That is not a
> clocking special case being tidied away; it is the only construct that
> expresses a real property of the part.  Nothing on the die is wasted.**

`t1_half2_results_2026-08-13.md` §8 already declined this change on cost and
benefit (the arc is 48.8 / 43.4 MHz clear of binding).  **This wave adds a
second, independent reason: it NARROWS THE CORE'S OPERATING ENVELOPE**, from
*"any train satisfying C-a/C-b, plus the degenerate 1:1 train"* to *"any train
satisfying C-a/C-b"*.  The 1:1 train is not hypothetical — it is what the whole
golden ladder runs on.

### 5.3 WHAT A FUTURE SITTING WOULD NEED, IF IT EVER WANTS THIS

Not a redesign — a **decision**, and then a re-scoring:

1. Rule on whether `tb_v30_core`'s `ce_div = 1` default is legitimate given
   C-a.  If it is, `t1_half2` **cannot** leave the negedge and this question is
   closed permanently.
2. If it is not, the default moves to a contract-legal `ce_div`, **every
   registered ratchet in `standing_gates.md` is re-measured on the new default
   BEFORE any RTL is touched**, and only then does the posedge form become
   evaluable.  Re-registering ratchets *after* seeing this result would be
   choosing a comparator after seeing a result, which is exactly what this
   sitting refused to do.
3. The silicon bar (prereg §8, the FLASH #21 clause) still applies unchanged if
   it ever lands.

### 5.4 THE M72 DOWNSTREAM READING, VERIFIED

`m72_downstream_timing_2026-08-12.md` §1.1's reading is **confirmed as the brief
stated it**: M72's adapter flops `v30_bus|addr_neg` / `ube_neg` are negedge
flops enabled by `ce_half`, so they capture the AD address at **`ce_half`+0.5**
— the same instant `t1_half2` flips today.  This tree carries two instances of
the identical construct (`tb_v30_core.sv:332`, `tb_chain_lfsr.sv:267`).  A
posedge `t1_half2` would give every such downstream latch a full extra half
period of address hold and remove the same-edge coincidence.  **That benefit is
real and it is now booked against a change that cannot be made** — which is
worth recording, because it is the only argument that was ever *for* the
posedge form and it is not enough on its own.

---

## §6 DISPOSITION AND WHAT IS LEFT IN THE TREE

**REVERTED, in full:**

| file | state |
|---|---|
| `hdl/rtl/ucore/v30u_biu.sv` | restored to `0f9f165382` — the negedge process, its header sentence and the pin-drive comment |
| `hdl/nec_test.sdc` | restored — the negedge accounting, `-setup 3 -hold 2` on `ce_half → ce`, the `k = 0.5` paragraph |
| `sw/sta_truefmax_probe.tcl` | restored — the `k=`-valued class labels |
| `sw/quartus_gate.py`, `sw/test_quartus_gate.py` | restored — `TRUEFMAX_CLASSES`, `CORE_DOMAIN_CLASSES`, the `nominal` table, Q14/Q16 |
| `sw/testdata/ie-pinfall/core/`, `sw/testdata/ghost-pred/core/` | restored byte-identical (they were re-measured in place by the before/after legs) |

**POST-REVERT CONTROLS, all measured on the reverted tree:**

| leg | measured |
|---|---|
| `check_core --core ucore --opcodes all --cases 0` | **169,000 / 169,000** — the registered value, restored |
| `check_core … --ce-div 2` (§5.1's falsifier) | **169,000 / 169,000** |
| `test_quartus_gate` | **240 / 240 PASS** — the instrument revert confirmed by its own falsifier |
| `r7_lint` | **PASS**, 0 violations |
| `ss_lint --core ucore` | **PASS**, 232 / 221 flops / 3 whitelist / 0 UNMAPPED |

**KEPT:** this document, the pre-registration, and the append-only receipt
histories the ten G6 draws and the Verilator rebuilds wrote
(`sw/testdata/receipts/quartus_bitstream.jsonl` +10,
`quartus_distribution.jsonl` +2, `verilator_binary.jsonl` +8 — appends only,
0 deletions), plus the two G6 distribution records
`sw/testdata/g6dist/t1half2-posedge-{control,retention}-n5/`.  **Those records
describe a tree that no longer exists and say so in their own `git` field.**
Nothing else.

**The `k = 0.5` class, the `ce_half → ce` `-setup 3`, and every "exactly ONE
negedge process" sentence in the tree are therefore all still TRUE and still
correct.**  `t1_half2_results_2026-08-13.md`'s §8 disposition — *no RTL change* —
stands, now for two reasons instead of one.
