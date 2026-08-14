# THE ce/ce_half CONTRACT CORRECTION — **LANDED**

Pre-registration **`ae916ab641`**
(`docs/notes/ce_contract_correction_prereg_2026-08-13.md`), **committed BEFORE
the first edit**; the ordering is checkable from the hash.

Tree at entry **`f0742d88af`** (`master`), isolated worktree.  **Offline.
Quartus through the distribution gate.  NO board, NO flash.  No Codex, no
nested tasks.**

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

The contract is now **ONE premise — C-a: `ce` and `ce_half` are never asserted
on the same fabric clock.**  **Adjacent assertions are LEGAL.**  C-b (the gap
clause) is deleted and C-c's `ce → ce >= 4` arithmetic with it, because that
number was `2 + 2` and nothing else.

---

## §1 HEADLINE

| | |
|---|---|
| the assert | **`hdl/rtl/ucore/v30_core.sv:140-200`**, `ifndef SYNTHESIS`, `$fatal` on **C-a** *and* on **S-1**.  In the CORE, so **every instantiation inherits it** — `tb_v30_core`, `tb_chain_lfsr`, `tb_sys`/`system_large`, and any downstream integrator's sim.  **Non-vacuity demonstrated on both clauses** |
| the retirement | **`hdl/tb/ce_contract_check.sv` DELETED** with its three instantiations and its three build-list entries.  Its gap clauses enforced a premise that no longer exists; its C-a clause is superseded by a strictly wider check |
| **THE CENTRAL QUESTION — ANSWERED, OUTCOME (i)** | **the POSEDGE `t1_half2` COVERS THE WHOLE CORRECTED ENVELOPE.**  `check_core --opcodes all --cases 0` is **169,000 / 169,000 at div 2, div 3, div 4 and div 8**.  **No RTL flop changed.  The negedge form is NOT re-justified** |
| the tools | `check_core` / `tb_v30_core` refuse **div 1 only**; **2, 3 and odd divisors are legal**; the default **stays 4, and a default is not a floor** |
| `tb_chain_lfsr` | train relaxed to never-coincident, **both** gaps LFSR-drawn; signatures re-registered as an INSTRUMENT re-registration, **liveness census identical seed for seed** |
| **the SDC** | `ce → ce` **`-setup 4 -hold 3` → `-setup 2 -hold 1`**; **BOTH cross-phase exceptions DELETED** (they are 1.0 periods now — the default) |
| the SDC, **measured on the netlist** | `DEFAULT` **1.0000** · **`SAME` 2.0000** (was `CE4` 4.0) · **`INTO` 1.0000** (was 2.0) · **`OUTOF` 1.0000** (was 2.0) · `ENABLE` 1.0000, `off_class` **EMPTY** |
| **G6** | **CONTROL `draw@seed1` 38.01 MHz / +6.618 ns / 10,155 ALMs** (`a417e4c4e08faced…`) · **RETENTION `draw@seed1` 39.62 MHz / +7.277 ns / 10,162 ALMs** (`465cc54b9554f3a3…`).  Both **PASS**, TNS **0.000** setup AND hold on every domain of both, 0 errors / 0 latches / 0 `lpm_divide`, `.rbf`s differ.  **ONE draw each, by ruling — NOT an Fmax claim** |
| **Fmax FELL, AS REGISTERED** | CONTROL 42.06 → **38.01** · RETENTION 43.30 → **39.62**.  **P-4a said it would.**  The old budget was computed against an envelope the core does not have; this is a **correctness** change, and both draws clear the 32.0 bar by ≥ 6 MHz |
| the ladder | **ZERO DELTA on every re-registered leg**, plus **2,728 directed cells byte-identical by decompressed content** |
| `test_quartus_gate` | **254 / 254** (was 252 / 252), **255 / 255** with a build tree on disk; `CE4`-era artifacts KEPT and **asserted to be REFUSED BY ERA** |
| **owed to fabric** | **NOTHING NEW.**  No synthesised logic changed.  §10 |

---

## §2 THE CONTRACT, AS IT NOW STANDS

> **C-a (CONTRACT).**  `ce` and `ce_half` are never asserted on the same fabric
> clock.

> **S-1 (STRUCTURAL — *not* a contract clause).**  At least one `ce_half` falls
> between consecutive `ce`s.

**S-1 is not an assumption about a train's shape.**  `ce_half` is the only
enable on `v30u_biu|t1_half2`; `t1_half2` is the T1 address→data turnaround and
gates `ad_oe_data`; so a `ce → ce` with no `ce_half` between them leaves the
**address** on AD for a whole write cycle.  A platform that does this has
already broken the core functionally, so **S-1 is no stronger than "the core
works"**.

### 2.1 THE DERIVED SPACINGS — the whole of the new arithmetic

| spacing | value | derivation |
|---|---:|---|
| `ce → ce_half` | **>= 1** | C-a alone forbids 0.  **Adjacent is legal.** |
| `ce_half → ce` | **>= 1** | C-a alone forbids 0.  **Adjacent is legal.** |
| `ce → ce` | **>= 2** | S-1 puts a `ce_half` in cycle *m* strictly between the `ce`s at *n* and *p*; C-a gives `m != n` and `m != p`; so `p >= n+2`.  **CONTRACT-FREE** |
| `ce_half → ce_half` | **>= 1** | nothing forbids extra `ce_half`s; `t1_half2`'s update is idempotent |

**THE GAP THAT WAS DELETED WAS NEVER SPARE MARGIN.**
`m72_downstream_timing_2026-08-12.md` §1 records the ucore running in
Arcade-IremM72 from a catch-up train whose phases *"strictly alternate"* **one
per fabric clock** during a burst.  **That is the adjacent train**, and this
tree had been constraining, scoring and refusing as though it could not happen.

---

## §3 THE MODULE ASSERT, AND ITS NON-VACUITY

`hdl/rtl/ucore/v30_core.sv`, inside the file's existing `ifndef SYNTHESIS`
assertion block (which already carried the SS/CE freeze contract).  One extra
flop, `ce_half_since_ce`, **simulation-only** — `ss_lint`'s architectural census
is unmoved at 221 flops, which is the check that it did not leak into the
design.

**MEASURED, on scratch trees under `~/.cache/ucsimt-tmp/`:**

| tree | invocation | fires | exit |
|---|---|---|---|
| this tree's train, divisor floor removed | `+ce_div=1` | **S-1** — `v30_core.sv:195`, *"two CEs with NO CE_HALF between them"* | abort |
| **HISTORICAL train restored** (`ce_half <= ce`), floor removed | `+ce_div=1` | **C-a** — `v30_core.sv:191`, *"CE and CE_HALF asserted on the SAME fabric clock"* | abort |
| **HISTORICAL train restored**, `+ce_div=4` | — | *(nothing — 374 rows written)* | **0** |

⚠ **REPORTED PRECISELY: at `ce_div = 1` on THIS tree's train the clause that
fires is S-1, not C-a.**  `tb_v30_core` computes `ce_half` from
`ce_cnt == (ce_div/2) - 1`, which at `ce_div = 1` is `ce_cnt == -1` and is never
true — so div 1 on this train emits **no `ce_half` at all** rather than a
coincident one.  C-a is the HISTORICAL train's div-1 signature and is
demonstrated on the historical train.  (The re-land wave recorded the identical
asymmetry for its C-c; the structure is unchanged, only the clause name.)

**THE THIRD ROW IS THE CORRECTION'S OWN CONTROL.**  `ce_half <= ce` — the
train the *previous* wave removed as a C-b violation — **runs clean at div 4**
under the corrected contract, because adjacent is legal.  The wave both widened
the envelope and kept a gate on it.

### 3.1 THE TB CHECKER IS RETIRED, AND WHAT THAT COSTS

`hdl/tb/ce_contract_check.sv` is **deleted**, with its instantiations in
`tb_v30_core.sv`, `tb_sys.sv` and `tb_chain_lfsr.sv` and its entries in
`check_core.CORE_RTL`, `chain_lfsr_gate.py` and `x1_retention.py`.  Keeping a
reduced copy would leave **two** enforcement points for **one** premise.

⚠ **THE ONE THING THIS COSTS, STATED AS A LOSS: `check_core --core fsm` NOW RUNS
WITH NO ENABLE ENFORCEMENT.**  The assert is in the ucore's `v30_core.sv`; the
ARCHIVED FSM core (`hdl/rtl/core/v30_core.sv`) is not touched by this wave, so
its legs are unchecked where the retired TB checker used to cover them.  It
gates an archived artifact and no standing figure depends on it; it is recorded,
not repaired.

---

## §4 THE CENTRAL TECHNICAL QUESTION — **OUTCOME (i), MEASURED**

### 4.1 THE ANALYSIS, REGISTERED BEFORE THE MEASUREMENT (prereg §4.1)

Minimum legal train — `ce` in cycle *k*, `ce_half` in *k*+1, `ce` in *k*+2:

| event | posedge |
|---|---|
| core state advances (CPU cycle **opens**) | ***k*+1** |
| **`t1_half2` flips (the turnaround)** | ***k*+2** |
| core state advances (CPU cycle **closes**) | ***k*+3** |

**`k`+2 is strictly inside the open interval (`k`+1, `k`+3), and it is the ONLY
interior posedge there is.**  C-PIN-1 is MET at the corrected minimum — with
**zero margin to spare**, which is worth saying plainly: at div 2 the posedge
form is not merely adequate, it is the **unique** posedge placement that works,
and any further delay would break it.

### 4.2 THE MEASUREMENT — **P-2 MET**

`sw/check_core.py --opcodes all --cases 0 --core ucore`:

| `--ce-div` | train | result |
|---:|---|---|
| 1 | coincident | **REFUSED, exit 2** (C-a cited) |
| **2** | **`ce@k`, `ce_half@k+1`, `ce@k+2` — the contract minimum, M72's burst rate** | **169,000 / 169,000** |
| **3** | odd; `ce@k`, `ce_half@k+1`, `ce@k+3` | **169,000 / 169,000** |
| **4** | the default (`nec_bus`'s phase) | **169,000 / 169,000** |
| 8 | cross-divisor control (the divider of record) | **169,000 / 169,000** |

`--ce-hold-check` on `B8,F3AA,HLT.INT` (1,200 cases): **`CE_HOLD_VIOL 0` at div
2, div 3 and div 8** — the core's state does not move on CE-low fabric clocks
anywhere in the envelope.

> **THE POSEDGE `t1_half2` COVERS THE WHOLE CORRECTED ENVELOPE.  §4.2 of the
> pre-registration — the branch in which the honest form turns out to be the
> negedge flop that was just removed — IS NOT TAKEN, and no RTL flop was
> changed.  The re-land stands.**

**WHY THIS WAS WORTH MEASURING RATHER THAN ARGUING.**  The posedge form moved
the turnaround from `ce_half`+0.5 to `ce_half`+1.0.  Under C-b the minimum CPU
cycle was 4 fabric clocks and +1.0 was comfortably interior; with C-b deleted
the minimum is **2**, and +1.0 is the last placement that still fits.  The
analysis said it fits; the golden corpus says so at 169,000 cases per divisor.

### 4.3 ONE OBSERVATION, REGISTERED IN ADVANCE SO IT IS NOT MISREAD

`nec_bus`'s capture pipeline is **two** posedge stages deep on the address side
(`ad_in_q` then `ad_early`, `nec_bus.sv:202/219`).  At `cfg_clk_div = 2` that
pipeline reads a stale CPU cycle **whatever edge `t1_half2` uses** — a property
of the **RIG's sampler**, not of the core.  `cfg_clk_div = 8` is the divider of
record and **nothing in this wave measures or claims anything about `nec_bus` at
div 2.**

---

## §5 THE TOOL MIGRATION

| tool | before | after |
|---|---|---|
| `hdl/tb/tb_v30_core.sv` | `$fatal` on `ce_div < 4` **or odd** | **`$fatal` on `ce_div < 2` only**; message cites the corrected contract |
| `sw/check_core.py` `CE_DIV_MIN` | **4** | **2** |
| `sw/check_core.py` `CE_DIV_DEFAULT` | 4 | **4, unchanged** |
| `ce_div_refuse()` | refused 1, 2, 3, all odd | **refuses 1 only** |
| `--ce-div` help text | *"values below 4, and odd values, are REFUSED"* | *"a default is not a floor … odd divisors are legal"* |
| `hdl/tb/tb_chain_lfsr.sv` | `ce@k`, `ce_half@k+2`, `ce@k+4` | **`ce@k`, `ce_half@k+1+h`, `ce@k+2+h+g`**, `h ∈ {0,1}` and `g ∈ [0,7]` both LFSR-drawn |
| `hdl/tb/ce_contract_check.sv` | instantiated in 3 TBs | **DELETED** |

**THE DEFAULT STAYS 4 AND A DEFAULT IS NOT A FLOOR.**  4 is `nec_bus`'s phase at
the divider of record and the divisor every standing figure in this tree is
registered at.  Keeping it means the correction **does not silently re-base the
ladder**; 2 and 3 are legal, are measured (§4.2), and may be selected.

**ODD DIVISORS.**  The old refusal argued `ce_half` *"cannot be placed
symmetrically"* at an odd divisor.  **Symmetry was never a premise** — `ce_half`
need only fall strictly between two `ce`s, which it does at every divisor >= 2.

### 5.1 `tb_chain_lfsr` — THE SIGNATURES MOVED, AND IT WAS REGISTERED (P-3)

Registered in advance (prereg §5) that the four signatures WOULD move: the gate
accumulates over every core output on **every fabric clock**, so a change of
train period changes the accumulation.  **A per-fabric-clock signature is not a
pin-identity bar.**  What may not move is the liveness census.

| | old train (this RTL) | **new train** |
|---|---|---|
| seed 1 | `fd126e6583256ad0` | **`0a3882a30ec09b82`** |
| seed 2 | `74625bb8de1fdfbf` | **`a4a24f1bff8dbf4b`** |
| seed 3 | `b978ae684e51f13f` | **`b978…` → `1eaefc62aaa6f126`** |
| seed 4 | `58c8078932e27d9c` | **`c762272d5aa08f6e`** |
| `ce_clocks` | 53,341 / 53,294 / 53,234 / 53,291 | **66,648 / 66,664 / 66,521 / 66,559** |
| `CHAIN_DEPTH_MAX` / `entry_st` / `coincide` | 6 / 25 / 0 | **6 / 25 / 0** |
| **the `live` bus census** (`fpops` `qpops` `INTA` `IOR` `IOW` `HALT` `CODE` `MEMR` `MEMW`) | — | **IDENTICAL SEED FOR SEED, all four** |

The old-train column was measured on **this wave's RTL** in a scratch tree, so
the comparison is train-vs-train with the engine fixed — and its four signatures
reproduce `ce_contract_reland_results_2026-08-13.md` §6.1's STEP 2 column
exactly, which is the control that the scratch is the committed baseline.

`ce_clocks` **rises ~25 %** because the minimum train period fell from ~4+g to
~2+h+g fabric clocks: more CPU cycles fit in 400,000 fabric clocks.  **The
liveness census is nevertheless identical to the event** — that is the measured
form of *"per-CPU-cycle behaviour is independent of the enable train"*, on
arbitrary LFSR bytes with LFSR `READY`, LFSR `INT`/`NMI` and LFSR-drawn CE gaps.

`chain_lfsr_gate`: **PASS**, `CHAIN_MAX 7`, observed depth `[6]`, 0 overflows,
4 seeds × 400,000 clocks.  **H-3 non-vacuity still MET** — `CHAIN OVERFLOW`
fires on 4/4 seeds at `CHAIN_MAX = 4`.

⚠ **AN INSTRUMENT FINDING FOUND WHILE RE-REGISTERING: `sw/testdata/chain_lfsr_sig.json`
WAS ALREADY STALE BY A WAVE.**  It still held the **pre-re-land** signatures
(`2138eabbcea8796c`, …) — the re-land moved the train twice and never refreshed
it.  Nothing noticed because **the gate does not read that file unless
`--sig-ref` is passed**; it is a reference, not a bar.  Refreshed here with
`--sig-out`; the superseded values are in git history and in the re-land
results.  **Recorded because a reference nobody checks is the shape of a vacuous
gate.**

---

## §6 THE SDC, RE-DERIVED FROM C-a + S-1

| arc | before | **after** | argument |
|---|---|---|---|
| `ce → ce` | `-setup 4 -hold 3` (4.0) | **`-setup 2 -hold 1` (2.0)** | §2.1: `ce → ce >= 2`.  Launch *n*+1, latch *p*+1, `p >= n+2` |
| `ce → ce_half` | `-setup 2 -hold 1` (2.0) | **DELETED** (1.0, the default) | adjacent is legal: `m >= n+1`, so launch *n*+1, latch *m*+1 = **1.0** |
| `ce_half → ce` | `-setup 2 -hold 1` (2.0) | **DELETED** (1.0, the default) | the same, the other way |
| `div_cnt → t1_half2` (ENABLE) | unexcepted, 1.0 | **unchanged** | not touched by this ruling |

**THE TWO CROSS-PHASE EXCEPTIONS ARE DELETED, NOT RE-SPELLED.**  1.0 period IS
the default single-cycle check, so the honest constraint is **no constraint**.
Writing `-setup 1` would be writing the default down twice; leaving `-setup 2`
would be a **false PASS by a factor of two, in the optimistic direction**, on
the exact arc the collection split exists to protect.

**THE COLLECTION SPLIT SURVIVES AND IS MORE LOAD-BEARING, NOT LESS.**
`$v30u_half` must still be removed from `$v30u_ce`: same-phase is 2.0 and
cross-phase is 1.0, so leaving `t1_half2` inside would hand a 1.0-period arc a
2.0-period exception.  The ratio is unchanged at 2×; only the magnitudes fell.
**The exact-name `~DUPLICATE` hazard is unchanged and stays BOOKED.**

**TWO PARAGRAPHS ELSEWHERE IN THE FILE GOT *WEAKER*, AND SAY SO.**  The deleted
E-1 observation exception and the BOOKED `core_ad_hold` fragment both rested on
C-b's *"the earliest `ce_half` is TWO clocks after that `ce`"*.  It is **ONE**
now.  E-1's arithmetic is off by a further clock in the direction that already
condemned it (the earliest `ce_half`-gated consumer now captures at posedge
`L`+1 and reads a **pre-launch** sample); `core_ad_hold` stays booked and is
weaker.  **Neither is re-derived, because neither exists.**

### 6.1 THE `truefmax` CLASS LABELS — `CE4` BECOMES `SAME`

`CE4` asserted a `k` in its own name, which is the pattern the previous wave
removed from the other four labels and could not remove from this one without
changing the number.  The correction changes the number, so the label goes:
**`SAME`** (`$v30u_ce → $v30u_ce`), structural, asserting no `k`.
`quartus_gate.py`'s **checked** `nominal` table becomes
**`SAME` 2.0 · `INTO` 1.0 · `OUTOF` 1.0** (`DEFAULT` and `ENABLE` stay 1.0).

⚠ **CONSEQUENCE, AND IT IS THE CORRECT BEHAVIOUR: every `CE4`-era `truefmax`
artifact now REFUSES TO PARSE**, `truefmax_complete()` returns False and
`core_domain_fmax()` returns **no figure with the missing class named**.
*Absence must not read as data.*

⚠ **AND THE ERA WALL IS THINNER THAN THE NEGEDGE ONE, SAID PLAINLY.**  A
negedge-era artifact goes missing on **all three** core classes; a `CE4`-era one
goes missing on **exactly one**, because the correction RENAMED `CE4` but only
DELETED the exceptions behind `INTO`/`OUTOF`, leaving those two labels intact.
**A future correction that changes every `k` and renames nothing would leave a
stale artifact parsing CLEAN** — only the `nominal` k check would catch it.  The
two mechanisms are independent on purpose, and `test_quartus_gate` now asserts
the per-era behaviour separately rather than accepting either.

---

## §7 THE LADDER — RE-REGISTERED, ZERO DELTA

| leg | figure | Δ |
|---|---|---|
| `check_core --opcodes all --cases 0` (div **2** / **3** / **4** / 8) | **169,000 / 169,000** each | **0** |
| `--opcodes 8F.0` | 500 / 500 | 0 |
| `s10-hltsweep-w0 --waits 0` | 97 / 97 | 0 |
| `s10-hltsweep-w1 --waits 1` | 93 / 95 | 0 |
| `s13-hltsweep-w2 --waits 2` | 45 / 46 | 0 |
| `s13-hltsweep-w3 --waits 3` | 44 / 45 | 0 |
| **the four sweeps** | **279 / 283** | **0** |
| `f4a_boundary --waits 0` | 160 / 160 | 0 |
| `f0lock_tranche --waits 0` | 400 / 400 | 0 |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 each | 0 |
| `v0.1-w1 --opcodes EB` | 200 / 200 | 0 |
| the four `evt` cells | 200 · 1,200 · 200 · 1,200 | 0 |
| `v0.1-w1evt-biased` | 1,200 / 1,200 | 0 |
| `check_boot --timed 220` / `400` | MATCH / MATCH | 0 |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** | 0 |
| `sm3_s16_score --core ucore` | `busstat_other` **24** · `ARCH` **27** | 0 |
| `check_ab_sim --core ucore` | MATCH **187** rows | 0 |
| `ghost_launch_law score` | **200 / 200 = 100.0 %** | 0 |
| `qdepth_probe` | `rdq` 0:264 1:49 2:34 · `rd_done` 0:102 1:245 | 0 |
| `--ce-hold-check` @ div 2 / 3 / 8 | `CE_HOLD_VIOL` **0**, 1,200 / 1,200 each | — |
| `chain_lfsr_gate` | **PASS**, depth [6], 0 overflows; **H-3 MET** | signatures re-registered (§5.1) |
| `r7_lint` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations | 0 |
| `ss_lint --core ucore` | **PASS**, `SS_COUNT` **232**, **221** flops, 3 whitelist, **0 UNMAPPED** | 0 |
| `test_artifact` | **45 / 45**, non-vacuous | 0 |
| `test_quartus_gate` | **254 / 254** on a fresh worktree, **255 / 255** with a build tree on disk | was 252/252 (§6.1) |
| `gen_ucore_qsf --check` | clean | 0 |
| `ucrom_mif_check` (needs a `db` on disk — run after G6) | **PASS**, `ucdecode` 8,192 / 8,192 and `ucrom` **1,028 / 1,028** words identical | — |

### 7.1 THE `tb_sys` LEGS — 2,728 CELLS BYTE-IDENTICAL BY CONTENT (P-5 MET)

| leg | result |
|---|---|
| `ie_pinfall_cell core` | **2,200 cells**, **13 / 13 data files IDENTICAL**; `manifest.json` moved on `receipt`, `seconds`, `ts` only |
| `ghost_pred_cell core` | **528 cells**, **133 / 133 data files IDENTICAL**; `manifest.json` moved on `git`, `receipt`, `seconds`, `ts` only — `R`, `block`, `cells`, `leg`, `tool` equal |
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | **307 seeds** (107 fabric-FAIL, 200 fabric-PASS), **AGREEMENT 307 / 307 = 100.0 %**, `first_bad` **IDENTICAL on 107 / 107** |

⚠ **COMPARED BY DECOMPRESSED CONTENT, NOT BY `.gz` BYTES.**  gzip embeds an
mtime, so a `.gz` `sha256` diff is not evidence of a data change.
`ghost-pred/core/SHA256SUMS` differs for exactly that reason — it is a list of
`.gz` hashes — and its 133 underlying files are content-identical.

⚠ **AND THE RE-MEASURED COLUMNS WERE THEN DISCARDED, NOT COMMITTED.**  Both
directories are reverted to their committed bytes.  They carry **no new
information** — that is exactly what this section measured — and committing 147
`.gz` files whose only change is an embedded mtime would put unreadable churn in
front of the next person to diff them.  **The measurement is this table; the
artifact is the one already in the tree.**

⚠ **THE `fz2_replay` ERA OVERRIDE IS STATED, NOT WORKED AROUND.**  The guard
refused with **85 / 88 inputs identical** to FLASH #21's and three MOVED:
`hdl/nec_test.sdc`, `hdl/rtl/ucore/v30_core.sv`, and `hdl/nec_test_ucore.qsf`
(the declared §70.7 exemption).  Run with `--no-fabric-era-guard`; **no fabric
claim is made from it.**  See §10 for why the two real movers do not owe a
silicon bar.

**AND THE STRONGER ARGUMENT, BECAUSE THE CELLS ARE THE MEASUREMENT:** the only
Verilator-visible change in this wave is an `ifndef SYNTHESIS` block whose sole
effect is `$fatal`.  It cannot alter a value — it can only stop the run — and it
did not fire on any leg.  2,728 directed cells identical is the direct
confirmation.

### 7.2 ⚠ TWO LEGS DID NOT COME BACK CLEAN, AND NEITHER IS THIS WAVE'S

**(a) `fz2_immaterial falsify` — G6 and G7 FAIL; G1-G5 and G8 PASS.**

    G6 THE CENSUS   : 3 / 8 registered cells disagree with the derivation
                      FUNCTIONAL doc 44 != derived 46
                      TIMING     doc 30 != derived 29
                      total      doc 106 != derived 107
    G7 THE DOCUMENT : WORKING-RESIDUE headline (84, 106, 22)
                      != derived (85, 107, 22)

These clauses compare the **census document's** numbers against the **ledger's**.
This wave edited neither: `git status` carries no `fz2_*` change, and nothing in
the diff can reach a markdown census or a JSON ledger.  It is the same
document-lag pattern the tree has recorded and closed before (CLAUDE.md, the
F17 → F18 entry: *"`fz2_immaterial falsify` reported G6/G7 FAIL against … an
F17-era snapshot"*).  **BOOKED as pre-existing, deliberately NOT re-derived in
the wave that measured it** — re-deriving a census inside an unrelated wave is
how a number stops being readable against its own history.

**(b) the DEFAULT ledger cannot be scored in this worktree at all.**
`fz2_immaterial falsify` with no `--ledger` selects
`fz2_failure_ledger_f20_2026-08-12.json` and dies on
`CAPTURE SHA MISMATCH fz2c/404049`.  The fz2 captures are **gitignored and
main-only**; this worktree reaches them by read-only symlink, and the live
`captures/` directory in the main checkout has since moved on to the FLASH #21
population.  Both legs above were therefore run against
**`fz2_failure_ledger_f21_2026-08-13.json`**, which is this tree's current era.
**An environment property, stated, not a defect of the wave.**

---

## §8 WHAT THE ZERO MEANS, AND WHAT IT DOES NOT

The ladder is zero-delta because **nothing in this wave can move a scored
value**: the RTL edit is simulation-only, the SDC is invisible to Verilator, and
the tool changes widen an envelope rather than move inside it.

**The number that DID move is the one that should have: Fmax.**  The design was
being closed against `-setup 4` on the CE arc, which the corrected contract does
not warrant.  Under `-setup 2` the same netlist measures **38.01 MHz** where it
measured 42.06.  **That is not a regression — the 42.06 was measured against an
envelope the core does not have.**

⚠ **AND THE BINDING CONE MOVED INTO THE CORE.**  On this draw the whole-design
Fmax (38.01) **equals** the core-domain figure, bound by class **`SAME`** at
`k = 2.0` — where the previous wave's core-domain figure was 62.39 MHz on `CE4`
at `k = 4.0` and the design was bound elsewhere.  **The CE multicycle was
carrying this design, and the honest contract hands the ceiling back to the
core's own `ce → ce` cone.**  Recorded as a structural finding; **no RTL was
written on the strength of it**, and it is one draw.

---

## §9 G6 — **ONE DRAW PER CONFIGURATION, AND NOT AN Fmax CLAIM**

Per the standing ruling (*"only run more than one seed if the compile is
explicitly being done to measure fmax"*), both legs are a single
**`draw@seed1`**.  `--seeds 1` is used rather than a bare invocation **only**
because the per-class `truefmax` probe is on the sweep code path; it is still
exactly one fit.  **No band, no spread, no worst-of-N, and no Fmax claim.**
`standing_gates.md` §A governs — one green build is not closure, and the same
tree has drawn 19.42 and 45.91 MHz.

### 9.1 CONTROL — `draw@seed1`, receipt `a417e4c4e08faced…`

| | |
|---|---|
| verdict | **PASS** |
| **E3** `divclk` Fmax ≥ 32.0 | **38.01 MHz** |
| **E4** worst setup > 0 every domain | **+6.618 ns** |
| **E5** TNS 0.000 setup AND hold, every domain | **0 violations** (hold slacks +0.246 / +0.273 / +0.427 / +0.493) |
| **E2** 0 errors, every stage Successful | **0** |
| latches / `lpm_divide` | **0 / 0** |
| ALMs | **10,155 / 41,910 (24 %)** |
| **E8** the fitter honoured `--seed=1` | asked 1 · command line 1 · `Fitter Initial Placement Seed` row 1 |
| **E7** inputs re-hashed after the build | PASS (1 moved: `hdl/nec_test_ucore.qsf`, the declared §70.7 exemption; OFFENDING none) |
| **E1** `gen_ucore_qsf --check` | clean |
| input manifest | **`00ddcf38e5d0668d…`**, 88 files |
| `.rbf` / `.sof` | `19d3d876c6276f87…` / `284ff61281ac2ee0…` |
| core-domain | **38.01 MHz**, class **`SAME`**, `k = 2.0` — *NOT a gate, no bar reads it* |
| all four `divclk` Fmax figures | `divclk` 38.01 · `FPGA_CLK2_50` 126.79 · audio `divclk` 56.84 · `altera_reserved_tck` 67.27 |

**THE INPUT MANIFEST DIFFERS from the re-land's `002f2fa4728ecac9…`** — that is
the check that the edit reached the compiler.

### 9.2 THE SDC RE-DERIVATION, **CONFIRMED ON THE NETLIST** — P-4b MET

Measured to four decimals on the CONTROL draw, from the analyser's own
launch/latch arithmetic and **not from this wave's reasoning**:

| class | measured `k` | was | ceiling on this draw |
|---|---:|---:|---:|
| `DEFAULT` | **1.0000** | 1.0 | 40.60 MHz |
| **`SAME`** (was `CE4`) | **2.0000** | **4.0** | **38.01** *(the design's bound)* |
| **`INTO`** | **1.0000** | **2.0** | 61.90 |
| **`OUTOF`** | **1.0000** | **2.0** | 69.02 |
| `ENABLE` | **1.0000** | 1.0 | 116.27 |

* **P-4b MET.**  `SAME` measures exactly 2.0; **`INTO` and `OUTOF` measure
  exactly 1.0, which is the netlist confirming that their exceptions are GONE**
  rather than mis-spelled.
* **`off_class` is EMPTY on this draw** (`k_measured` = `SAME` 2.0 · `INTO` 1.0
  · `OUTOF` 1.0, each equal to nominal).  ⚠ The `upper_bound` caveat does **not**
  lift and that is correct: it is a structural property of a slack-ordered
  `get_timing_paths` query, and this wave did not change it.
* **P-4a MET as registered: Fmax FELL**, 42.06 → 38.01 (−4.05 MHz).  ALMs rose
  10,053 → 10,155 (+1.0 %) — the fitter working harder against a tighter budget.
  **No floor was registered and none is claimed.**

### 9.3 RETENTION — `draw@seed1`, receipt `465cc54b9554f3a3…`

| | |
|---|---|
| verdict | **PASS** |
| configuration | **`RETENTION (X1_AD_RETENTION=1)` — DERIVED from the flow and map reports, never from the flag** (**E-6 satisfied**) |
| the compiler's own line | `quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore` |
| **E3** `divclk` Fmax ≥ 32.0 | **39.62 MHz** |
| **E4** worst setup > 0 every domain | **+7.277 ns** (then +8.542 · …) |
| **E5** TNS 0.000 setup AND hold, every domain | **0 violations**, all four domains, both directions (hold +0.253 / +0.267 / +0.356 / +0.374) |
| **E2** 0 errors, every stage Successful | **0** |
| latches / `lpm_divide` | **0 / 0** |
| ALMs | **10,162 / 41,910 (24 %)**, fit registers 6,071 |
| **E8** the fitter honoured `--seed=1` | asked 1 · command line 1 · `Fitter Initial Placement Seed` row 1 |
| **E1** `gen_ucore_qsf --check` | clean |
| input manifest | **`00ddcf38e5d0668d…`**, 88 files — identical to CONTROL's, which is correct: the macro is not an input |
| `.rbf` | **`3ed5b643193d4fb5…`** — **DIFFERENT** from CONTROL's `19d3d876c6276f87…` (**E-9 satisfied**: the check that the macro reached the compiler) |
| `.sof` | `f2dcc65057adefd6…` |
| core-domain | **39.62 MHz**, class **`SAME`**, `k = 2.0` |

**Per-class `k`, RETENTION draw** — `DEFAULT` **1.0000** (41.71 MHz) ·
**`SAME` 2.0000** (39.62) · **`INTO` 1.0000** (57.59) · **`OUTOF` 1.0000**
(97.60) · `ENABLE` **1.0000** (151.93).  `off_class` **EMPTY**.  **P-4b holds on
BOTH configurations** — the re-derivation is confirmed twice, independently
fitted.

⚠ **THE RETENTION-VS-CONTROL SIGN IS POSITIVE AGAIN: +1.61 MHz** (39.62 against
38.01).  Reported, **not explained**, and **not a delta anyone may compute from
a draw pair** — `standing_gates.md` §A governs.  The sign has now inverted in
both directions across the last several waves.

⚠ **AND THE BAND FELL ON BOTH CONFIGURATIONS**, which is the wave's registered
expectation and not a surprise: CONTROL 42.06 → **38.01**, RETENTION 43.30 →
**39.62**.  **P-4a MET.**  Both draws clear the E3 bar of 32.0 by ≥ 6 MHz.

---

## §10 WHAT IS OWED TO FABRIC — **NOTHING NEW**

**This wave lands no synthesised logic.**  The only RTL edit is inside
`v30_core.sv`'s `ifndef SYNTHESIS` block; both QSFs set `SYNTHESIS=1`, so it
compiles to nothing.  The SDC change alters the **compiler's budget**, not a
pin: it can move placement and routing, and it does move Fmax, but it cannot
change what the design does.

* **No pin moves in time**, so **FLASH #21 clauses (v) and (vi) are NOT
  re-incurred by this wave.**
* **The re-land's own (v)/(vi) debt is UNCHANGED and still OUTSTANDING** — the
  `t1_half2` posedge move has never been on a board.  This wave does not
  discharge it and does not add to it.
* ⚠ **A BITSTREAM BUILT FROM THIS TREE IS NEVERTHELESS A DIFFERENT BITSTREAM**
  (`.rbf` `19d3d876c6276f87…` against FLASH #21's `a84577f6499f132d…`), because
  the fitter closed against a different constraint set.  **The fabric era guard
  is right to refuse**, and every `tb_sys` leg here ran with the override
  declared and makes no fabric claim.

---

## §11 WHAT THIS SITTING DID NOT DO

* **No board, no flash, no Codex, no nested tasks** — as directed.
* **The block-I/O leg (23 `v0.3` forms, 229,999 cycles) was NOT run.**
  DEFERRED, not passing.
* **The ARCHIVED FSM core was not touched** and none of its figures re-measured.
  Its on-demand gates now run at `--ce-div 4` by default and **with no enable
  enforcement at all** (§3.1).
* **`fz2_immaterial`'s G6/G7 census lag was NOT re-derived** (§7.2a).
* **The `~DUPLICATE` collection hazard stays BOOKED**, unchanged by this wave.
* **`ce → ce_half` gap variation in `tb_chain_lfsr` is `{0, 1}`, not `[0, 7]`** —
  wide enough to reach the contract minimum at a rate the H-2 bar can see, and
  deliberately not widened further in a wave that was not about stimulus.
