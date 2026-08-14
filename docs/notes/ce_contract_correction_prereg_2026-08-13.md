# THE ce/ce_half CONTRACT CORRECTION — PRE-REGISTRATION

**Committed BEFORE the first edit.**  Tree at entry **`f0742d88af`** (`master`),
isolated worktree.  **Offline.  NO board, NO flash.**  G6 per the seeds ruling:
**ONE draw per configuration — this is not an Fmax measurement.**

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §0 THE RULING

**USER, 2026-08-13, verbatim:**

> *"Correct the guidance on ce and ce_half. They do not need to be separated by
> a clock, they just cannot be enabled at the same time, we should have an
> assert in the module that prevents that."*

This **supersedes the gap clause** of the 2026-08-12 ruling.  The contract is
now **ONE premise**:

> **C-a.  `ce` and `ce_half` are never asserted on the same fabric clock.**

**Adjacent assertions are LEGAL.**  That is not a hypothetical: `m72_downstream_
timing_2026-08-12.md` §1 records the real downstream train — *"`ce_cpu` is
`~ce_cpu_count[0]` and `ce_cpu_half` is `ce_cpu_count[0]`, so the phases
strictly alternate … 4 in steady state, **2 at the catch-up burst rate**"*.  The
catch-up burst **is** the adjacent train, and this tree has been refusing it.

**C-b is DELETED.**  It was the gap clause and the gap is gone.

**C-c's ARITHMETIC (`ce → ce >= 4`) is DELETED WITH IT**, because that number
was `2 (gap) + 2 (gap)`.  What survives of C-c is not a contract clause at all
and is re-stated in §2 as a STRUCTURAL fact about the core.

**ENFORCEMENT MOVES INTO THE MODULE**, as the ruling directs.

---

## §1 WHAT IS BEING RE-DERIVED, AND WHY NOTHING MAY BE CARRIED OVER

Every number the previous two waves wrote — the divisor floor of 4, the SDC's
`-setup 4 -hold 3`, its two cross-phase `2/1` exceptions, `tb_chain_lfsr`'s
train, `check_core`'s refusal set, `quartus_gate.py`'s `nominal` table and the
`CE4` class label — was derived from **C-b**.  C-b is gone, so **each one is
re-derived from C-a plus structure, or deleted.**  A number that survives must
survive by argument, not by inertia.

---

## §2 THE ONE STRUCTURAL FACT, STATED SEPARATELY FROM THE CONTRACT

> **S-1.  The core REQUIRES at least one `ce_half` between consecutive `ce`s.**

This is **not** an assumption about a train's shape and **not** a premise the
user's ruling governs.  It is the core's own functional requirement, and the
argument is in the RTL: `ce_half` is the only enable on `t1_half2`
(`v30u_biu.sv`), `t1_half2` is the T1 address→data turnaround and gates
`ad_oe_data` (`v30u_biu.sv:1056/1062/1080`), so a `ce → ce` with **no** `ce_half`
between them drives the **address** on AD for a whole write cycle.  A platform
that does this has already broken the core functionally; S-1 is therefore no
stronger than "the core works".

**S-1 IS A LIVE ASSERTION IN THIS WAVE, NOT A COMMENT** — see §3.

### 2.1 THE DERIVED SPACINGS — the whole of the new arithmetic

| spacing | value | derivation |
|---|---:|---|
| `ce → ce_half` | **>= 1** | C-a alone forbids 0.  **Adjacent is legal.** |
| `ce_half → ce` | **>= 1** | C-a alone forbids 0.  **Adjacent is legal.** |
| `ce → ce` | **>= 2** | S-1 puts a `ce_half` in a cycle *m* strictly between the two `ce`s at *n* and *p*; C-a gives `m != n` and `m != p`; so `p >= n+2`. |
| `ce_half → ce_half` | **>= 1** | nothing forbids adjacent extra `ce_half`s; `t1_half2`'s update is idempotent. |

**`ce → ce >= 2` HOLDS CONTRACT-FREE.**  It rests on C-a and S-1 and on no
statement about idle clocks.

---

## §3 DELIVERABLE 1 — THE MODULE ASSERT

`hdl/rtl/ucore/v30_core.sv` already carries an `ifndef SYNTHESIS` assertion
block at `:140-150` (the SS/CE contract).  **The enable-contract assertions go
in that block**, in the core module itself, so **every instantiation inherits
them** — `tb_v30_core`, `tb_chain_lfsr`, `tb_sys`/`system_large`, `tb_ab`,
`tb_harness`, and any downstream integrator's simulation.

| id | fires on | severity |
|---|---|---|
| **C-a** | `CE && CE_HALF` on one fabric clock | **`$fatal`** |
| **S-1** | a `CE` with no `CE_HALF` since the previous `CE` | **`$fatal`** |

`$fatal`, not `$error`, for the reason the retired checker gave and which the
correction does not touch: a train outside the envelope has invalidated every
row downstream of it, so continuing produces a **scored number taken outside
the contract**.

**P-1 (NON-VACUITY, both clauses).**  In a scratch tree under
`~/.cache/ucsimt-tmp/`, with the TB's divisor floor removed, `+ce_div=1` (which
makes the TB train coincident) must abort naming **C-a**, and a scratch train
that issues two `ce`s with no `ce_half` must abort naming **S-1**.  An assertion
that cannot fire is not evidence.

### 3.1 `hdl/tb/ce_contract_check.sv` — **RETIRED**

Its **C-b and C-c clauses enforce a premise that no longer exists.**  Its **C-a
clause is superseded by the module assert**, which is strictly wider: the
checker sees only the three testbenches it is instantiated in, the module assert
sees every instantiation of `v30_core` that has ever been or will ever be
elaborated.

**DISPOSITION: the file is DELETED and its three instantiations removed**
(`tb_v30_core.sv`, `tb_sys.sv`, `tb_chain_lfsr.sv`), along with its entries in
`check_core.py`'s `CORE_RTL`, `chain_lfsr_gate.py` and `x1_retention.py`.
Keeping a reduced copy would leave **two** enforcement points for **one**
premise, and the ruling asked for the one in the module.

**The ARCHIVED FSM core (`hdl/rtl/core/v30_core.sv`) does NOT get the assert.**
It is archived (`fsm_core_archive_2026-08-04.md`) and this wave does not touch
its RTL.  **Consequence, stated: `check_core --core fsm` runs with NO enable
enforcement.**  That is a loss relative to the retired checker and it is
reported as one.

---

## §4 DELIVERABLE 2 — THE CENTRAL TECHNICAL QUESTION

> **Is the POSEDGE `t1_half2` correct on ADJACENT trains?**

`t1_half2` became a posedge flop on 2026-08-13
(`ce_contract_reland_results_2026-08-13.md` §1).  The negedge form flipped the
turnaround at `ce_half`+0.5 fabric periods; the posedge form flips it at
**`ce_half`+1.0**.  With C-b in force the minimum CPU cycle was 4 fabric clocks
and +1.0 was comfortably interior.  **With C-b deleted the minimum CPU cycle is
2 fabric clocks**, and +1.0 could land ON the cycle boundary instead of strictly
inside T1 — which is C-PIN-1's exact prohibition
(`t1_half2_anatomy_2026-08-13.md` §2.4).

### 4.1 THE ANALYSIS, REGISTERED BEFORE THE MEASUREMENT

Convention (`nec_test.sdc`): an enable asserted during fabric cycle *n* is
sampled at posedge *n*+1, and the flop it gates captures there.

Minimum legal train (`ce` in cycle *k*, `ce_half` in *k*+1, `ce` in *k*+2):

| event | posedge |
|---|---|
| core state advances (CPU cycle **opens**) | ***k*+1** |
| **`t1_half2` flips (the turnaround)** | ***k*+2** |
| core state advances (CPU cycle **closes**) | ***k*+3** |

**The turnaround at *k*+2 is STRICTLY INSIDE the open interval (*k*+1, *k*+3),
and it is the ONLY interior posedge there is.**  C-PIN-1 is therefore MET at the
corrected contract's minimum train — with **zero** margin to spare, which is
worth saying plainly: at div 2 the posedge form is not merely adequate, it is
the unique posedge placement that works, and any FURTHER delay would break it.

The negedge form put it at *k*+1.5, also interior.  **Both forms satisfy
C-PIN-1 at the minimum train**; the posedge form additionally gives a
`ce_half`-negedge address latch (the TB's `ad_mid`/`lat_addr`, M72's
`addr_neg`/`ube_neg`) a full half-period of SEPARATION rather than landing on
the same edge.

**PREDICTION P-2: `check_core --opcodes all --cases 0` passes at div 2 and
div 3.**

### 4.2 ⚠ THE PREDICTION IS REGISTERED SO IT CAN BE WRONG

If **div 2 or div 3 FAILS**, that is a **REAL FINDING** and the wave's shape
changes: the posedge form does not cover the corrected envelope, and the
question becomes whether a turnaround placement exists that works for **all**
legal trains.  **If that placement is the negedge form, this document will say
so plainly.**  The user's correction is entitled to re-justify the flop that was
just removed; that would be a finding, not an embarrassment.  **No RTL is landed
beyond what one honest form requires, and if the honest form is ambiguous the
options are booked with their measurements and the wave STOPS.**

### 4.3 A SEPARATE OBSERVATION, REGISTERED SO IT IS NOT MISREAD LATER

`nec_bus`'s own capture pipeline is **two** posedge stages deep on the address
side (`ad_in_q` then `ad_early`, `nec_bus.sv:202/219`).  At `cfg_clk_div = 2`
that pipeline reads a stale CPU cycle **whatever edge `t1_half2` uses**.  That
is a property of the **RIG's sampler**, not of the core, `cfg_clk_div = 8` is
the divider of record, and **nothing in this wave measures or claims anything
about `nec_bus` at div 2.**

---

## §5 DELIVERABLE 3 — THE TOOL MIGRATION

| tool | now | after |
|---|---|---|
| `hdl/tb/tb_v30_core.sv` | `$fatal` on `ce_div < 4` **or odd** | `$fatal` on **`ce_div < 2` only**; the message cites the corrected contract |
| `sw/check_core.py` `ce_div_refuse` | refuses 1, 2, 3 and all odd | refuses **1 only** |
| `CE_DIV_DEFAULT` / `CE_DIV_MIN` | 4 / 4 | **4 / 2** |
| `hdl/tb/tb_chain_lfsr.sv` | `ce@k`, `ce_half@k+2`, `ce@k+4` | **`ce@k`, `ce_half@k+1`, `ce@k+2`** + LFSR gap |

**THE DEFAULT STAYS 4, AND A DEFAULT IS NOT A FLOOR.**  4 is `nec_bus`'s
divider phase at the divider of record and is what every standing figure in the
tree was last re-registered at; keeping it means this wave does not silently
re-base the ladder.  **2 is legal and is now measurable**, which is the point.

**ODD DIVISORS BECOME LEGAL.**  The old refusal argued *"`ce_half` is the
half-cycle marker and an odd divisor cannot place it symmetrically"* — but
symmetry was never a premise, and under the corrected contract `ce_half` need
only fall strictly between two `ce`s.  At `ce_div = 3` the TB places `ce` at
count 0 and `ce_half` at count 1, leaving the turnaround interior.

**`tb_chain_lfsr`'s TRAIN CHANGES, SO ITS REFERENCE SIGNATURES CHANGE.**
Registered in advance: **the four per-seed signatures WILL move**, because the
gate accumulates over every core output on **every fabric clock** and the train's
period changes.  This is an **INSTRUMENT RE-REGISTRATION**, exactly as at the
re-land (`ce_contract_reland_results_2026-08-13.md` §6.1).

**P-3.  `chain_lfsr_gate` must PASS, `coincide` must be 0, `CHAIN_DEPTH_MAX`
must stay 6, `entry_st` 25, and the per-seed `live` bus census
(`fpops`/`qpops`/`INTA`/`IOR`/`IOW`/`HALT`/`CODE`/`MEMR`/`MEMW`) must be
IDENTICAL seed for seed to the current train's.**  A signature may move; the
liveness census may not.

---

## §6 DELIVERABLE 4 — THE SDC, RE-DERIVED FROM C-a + S-1

| arc | now | after | argument |
|---|---|---|---|
| `ce → ce` | `-setup 4 -hold 3` (4.0) | **`-setup 2 -hold 1` (2.0)** | §2.1: `ce → ce >= 2`.  Launch *n*+1, latch *p*+1, `p >= n+2`. |
| `ce → ce_half` | `-setup 2 -hold 1` (2.0) | **DELETED** (1.0, the default) | adjacent is legal: `m >= n+1`, so launch *n*+1, latch *m*+1 = **1.0**.  An exception here would be a false PASS. |
| `ce_half → ce` | `-setup 2 -hold 1` (2.0) | **DELETED** (1.0, the default) | same, the other way. |
| `div_cnt → t1_half2` (ENABLE) | unexcepted, 1.0 | **unchanged** | not touched by this ruling. |

**THE COLLECTION SPLIT SURVIVES AND IS MORE LOAD-BEARING, NOT LESS.**
`$v30u_half` must still be removed from `$v30u_ce`: same-phase is now 2.0 and
cross-phase is 1.0, so leaving `t1_half2` inside would hand a **1.0**-period arc
a **2.0**-period exception — the optimistic direction, the same error in the
same direction as before, at half the magnitude.  **The exact-name
`~DUPLICATE` hazard is unchanged and stays BOOKED.**

**P-4a.  Fmax is EXPECTED TO FALL.**  The binding CE exception loses two
periods of budget.  **No floor is registered for the core-domain class and no
Fmax claim is made** — this is a **correctness** wave: the old number was
computed against an envelope the core does not have.  The G6 PASS bars
(E2/E3/E4/E5: Fmax >= 32.0 on `divclk`, worst setup > 0, TNS 0.000 setup AND
hold on every domain, 0 errors, 0 latches, 0 `lpm_divide`) are unchanged and
are the wave's actual bar.

**P-4b.  MEASURED ON THE NETLIST, to four decimals:** the same-phase class must
read `k = 2.0000`, and the `INTO`/`OUTOF` classes must read `k = 1.0000` —
because their exceptions are gone.

### 6.1 THE `truefmax` CLASS LABELS

`CE4` asserts a `k` in its name and that `k` becomes wrong.  The precedent set
one wave ago is that **labels are STRUCTURAL and the `k` lives in the checked
`nominal` table**; `CE4` is the one label that never complied.

**It is renamed `SAME` (`$v30u_ce → $v30u_ce`).**  `nominal` becomes
`SAME` 2.0 · `INTO` 1.0 · `OUTOF` 1.0 (`DEFAULT` and `ENABLE` stay 1.0).
**CONSEQUENCE, AND IT IS THE CORRECT BEHAVIOUR: every `CE4`-era artifact stops
parsing, `truefmax_complete()` returns False and `core_domain_fmax()` returns no
figure with the missing class named.**  *Absence must not read as data.*
`sw/test_quartus_gate.py` is re-registered against this wave's own G6 CONTROL
seed-1 draw, and the `CE4`-era fixtures are KEPT and ASSERTED TO BE REFUSED BY
ERA.

---

## §7 THE LADDER — WHAT IS RUN, AND AT WHICH DIVISORS

**Every leg below is a re-registration against the CURRENT figure; a delta on
any of them is reported as registered, not restated.**

| leg | divisor |
|---|---|
| `check_core --opcodes all --cases 0` | **2**, **3**, **4** (default), 8 (control) |
| `check_core --opcodes 8F.0` | 4 |
| the four HLT sweeps ⚠ `--waits 0/1/2/3` | 4 |
| `f4a_boundary` / `f0lock_tranche` | 4 |
| `v0.1-w1` / `-w3` / `EB` / the four `evt` cells / `w1evt-biased` | 4 |
| `check_boot --timed 220` and `400` | 4 |
| `ulockstep --golden all --cases 50` | 4 |
| `sm3_s16_score --core ucore` | 4 |
| `check_ab_sim --core ucore` | n/a (`nec_bus`) |
| `ghost_launch_law score` | 4 |
| `chain_lfsr_gate` | new train |
| `ucrom_mif_check` | after G6 |
| `ie_pinfall_cell core`, `ghost_pred_cell core`, `fz2_replay` | `tb_sys` |
| `fz2_immaterial falsify` · `r7_lint` · `ss_lint` · `test_artifact` · `test_quartus_gate` | — |
| **G6** | **ONE draw per configuration** |

**P-5.  The `tb_sys` legs (`fz2_replay`, the 2,200-cell `ie-pinfall` column and
the 528-cell `ghost-pred` column) must be BYTE-IDENTICAL across this wave**,
compared by DECOMPRESSED content (gzip embeds an mtime), with only `receipt`,
`ts` and `seconds` permitted to move.  `nec_bus` runs at `cfg_clk_div = 8` and
this wave changes no RTL that a div-8 train can see — **unless §4 forces an RTL
change**, in which case P-5 is re-registered on the spot and said so.

**THE FABRIC ERA GUARD.**  If this wave lands **no** RTL, the guard should pass
without a bypass (HEAD's RTL == FLASH #21's).  **If it lands RTL, the guard must
be overridden and the leg is a BEFORE-vs-AFTER on one tree with NO fabric claim
made from it.**  Which of the two happened will be STATED, not left to the
reader.

**DEFERRED AND REPORTED AS DEFERRED, NOT AS PASSING:** the block-I/O leg
(23 `v0.3` forms, 229,999 cycles).

---

## §8 WHAT IS OWED TO FABRIC

**If this wave lands NO RTL** — assert + tools + SDC + docs only — then nothing
new is owed: the assert is `ifndef SYNTHESIS`, the tools are offline, and an SDC
change alters the compiler's budget, not a pin.  The FLASH #21 (v)/(vi) debt
from the *re-land* is unaffected and remains outstanding.

**If §4's measurement forces an RTL change**, a pin moves in time and the
FLASH #21 (v)/(vi) clauses are owed again, restated in the results document.

---

## §9 DISCIPLINE

* No board, no flash, no Codex, no nested tasks.
* This document is committed **before the first edit**; the ordering is
  checkable from the commit hash.
* The **div-2 measurement decides the wave's shape.**  Outcome (i) is not
  presumed; §4.2 is the registered alternative.
* Failures are reported **as registered**.
* `standing_gates.md` §A/§B and `CLAUDE.md` carry the corrected contract when
  the wave closes; **history is not rewritten** — superseded text stays, marked.
