# THE ce/ce_half CONTRACT IS THE OPERATING ENVELOPE — RE-LANDING THE NEGEDGE REMOVAL AND MOVING THE INSTRUMENTS INSIDE IT

**PRE-REGISTRATION.  Written and COMMITTED BEFORE any RTL, SDC or instrument
was edited** — the erratum `t1_half2_posedge_results_2026-08-13.md` opened with
(*"written before the edit but NOT COMMITTED before it"*) is not repeated; this
document's own commit hash is the ordering proof and is cited in the results.

Tree `58e082111b` (`master`), isolated worktree.
**Offline.  Quartus through the distribution gate.  NO board, NO flash.**

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §0 THE RULING, AND WHAT IT DECIDES

**USER RULING, 2026-08-13 — Option 2:**

> *the ce/ce_half contract IS the ucore's operating envelope.  Re-land the
> negedge removal and move the instruments inside the contract.*
> **1:1 is an unsupported mode.**

**SECOND USER RULING, 2026-08-13, received mid-sitting and superseding this
document's own stop clause as first drafted:**

> *"Unexplained deltas are not a stop.  The issue is the tests have been
> incorrect.  We will land this ce fix and then address the errors."*

Operationally, and registered here before any edit:

1. **The STOP-and-diagnose clause on re-registration deltas is REVOKED.**  A
   delta between the div-1 basis and the new basis is **evidence about the OLD
   instrument's error**, not a blocker.
2. **The ce fix LANDS regardless of what the re-registration table shows.**
3. **The re-registration table remains the load-bearing deliverable** — every
   old-vs-new delta recorded faithfully, attributed *"div-1 instrument error,
   to be addressed post-landing"*, itemized as a work list for the follow-up
   wave.  **Not diagnosed here beyond what falls out for free.**
4. ⚠ **A delta on a CONTRACT-LEGAL leg is NOT covered by the ruling and still
   gates** — `tb_sys` (the real integration, `nec_bus` at div 8), the directed
   cells, and any `check_core` leg run at a contract-legal divisor **against
   another contract-legal divisor**.  §8 writes those triggers.

The prior wave (`5928a77a00` / `58e082111b`) proved the one-word edit correct
on **every contract-legal instrument** and reverted it on **one** leg, the
scorer running the core at `--ce-div 1` where `tb_v30_core` asserts `CE` and
`CE_HALF` on the same clock.  That leg is now the thing being fixed.

---

## §1 THE RE-LAND — CITED, NOT RE-DERIVED

`hdl/rtl/ucore/v30u_biu.sv:1087`, **`negedge` → `posedge`, nothing else**:

```systemverilog
always @(posedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (r_run && (r_ts == TS_T1)) ||
                                  vector_follow_preview;
```

**The plain enabled posedge IS the +1.0 form; no new register, no `ce_half_q`,
and the save-state map does not move** (`t1_half2_posedge_prereg_2026-08-13.md`
§1.2/§1.3).

**The booking's two proofs are ERA-VALID and are CITED, NOT RE-DERIVED.**  The
RTL has not moved since: `hdl/` at `58e082111b` is byte-identical to
`0f9f165382`, which that pre-registration states in its own §6 disposition
table and which is checkable with `git diff 0f9f165382 58e082111b -- hdl/`.

* **§2, THE HOLD WINDOWS** — the two forms differ only on `[n_k+0.5, n_k+1.0)`;
  every sampled instant in `nec_bus` and in both testbenches reads a
  byte-identical value; the negedge samplers at `n_k+0.5` read the **same**
  address value and **lose a delta-cycle race**.  Its one false premise
  (§2.3(b), *"by C-b there is no enable assertion in cycle `n_k`+1"*) was false
  **only on the div-1 scorer** — which is what this wave removes.
* **§3, D-CONE STABILITY: HELD.**  Register-only cone; the planted shadow
  falsifier never fired on 169,000 + 169,000 golden cases, 306 `tb_sys`
  programs, 2,728 directed cells and 1.6 M fabric clocks of LFSR bytes.  ⚠ Its
  **non-vacuity was NOT established** and is not established here either; it is
  re-planted and carried, and is **not quoted as evidence**.

---

## §2 ⚠ AMENDMENT A-1 — THE BRIEF SAYS `--ce-div 2`; THE CONTRACT SAYS **4**, AND 4 IS WHAT IS REGISTERED

**This is a deviation from the brief, registered in advance, with its
derivation, and it moves the scorer FURTHER inside the contract — never less
far.**

### 2.1 The contract, verbatim from `hdl/nec_test.sdc`

> **C-a** `ce` and `ce_half` are never asserted on the same clock.
> **C-b** successive enable assertions are **>= 2 clocks apart**.
> **C-c** `ce -> ce` is **>= 4 clocks** … the core REQUIRES >= 1 `ce_half`
> between consecutive `ce`s.

C-b is about **enable assertions**, not about `ce` assertions: the SDC's own
arc derivation says so arithmetically — *"`ce -> ce_half` launch n+1, latch
**n+2.5** (C-b)"* puts the next assertion after a `ce` in cycle `n` at cycle
`n+2` **at the earliest**.

### 2.2 `tb_v30_core`'s train CANNOT satisfy C-b AT ANY DIVISOR

`hdl/tb/tb_v30_core.sv:80-85` writes `ce_half <= ce`, so **`ce_half` is
always the fabric clock immediately after `ce`** — gap **0** — at
`ce_div` 1, 2, 3, 8 or 64 alike.  At `ce_div = 1` it is additionally a **C-a**
violation (they coincide).  **Moving the divisor alone fixes C-a and leaves
C-b broken**, and the assertion this wave is required to add
(*"$fatal on a zero-gap between assertions"*) **would fire on the briefed
`--ce-div 2`**.  Landing div 2 would therefore have re-created, in a second
form, exactly the failure this wave exists to remove: a scorer outside the
declared contract while claiming to be inside it.

### 2.3 THE FIX IS THE PHASE, NOT THE DIVISOR — AND IT MAKES THE TB MATCH THE THING THAT GETS FLASHED

`nec_bus.sv:175-176` puts the two enables **half a CPU cycle apart**:
`CE = tick_rise` at `div_cnt == div_max`, `CE_HALF = tick_fall` at
`div_cnt == half - 1`.  At `cfg_clk_div = 8` that is **4 clocks each way**.
`tb_v30_core` is therefore not merely outside the contract — **it has never had
the phase relationship of the integration it is a stand-in for.**

The registered TB train:

```systemverilog
wire  ce      = !ss_park && (ce_cnt == 0);              // high during cnt 0
logic ce_half;                                          // high during cnt ce_div/2
always @(posedge clk) begin
    if (!ss_park) ce_cnt <= (ce_cnt >= ce_div - 1) ? 0 : ce_cnt + 1;
    ce_half <= !ss_park && (ce_cnt == (ce_div/2) - 1);
end
```

`ce_half` stays a **registered** signal so `ss_park`'s *"one parked posedge
lowers CE_HALF"* discipline (`tb_v30_core.sv:623-628`) is unchanged.

| `ce_div` | `ce` at | `ce_half` at | `ce→ce_half` | `ce_half→ce` | `ce→ce` | verdict |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0 | 0 | 0 | 1 | **C-a violated** |
| 2 | 0 | 1 | 1 | 1 | 2 | **C-b and C-c violated** |
| 3 | 0 | 1 | 1 | 2 | 3 | **C-b and C-c violated** |
| **4** | 0 | 2 | **2** | **2** | **4** | **LEGAL — the contract MINIMUM** |
| 8 | 0 | 4 | 4 | 4 | 8 | LEGAL (the `nec_bus` phase exactly) |

**`nec_bus` agrees**: at `cfg_clk_div = 2` it too puts `tick_fall` and
`tick_rise` on adjacent clocks.  **4 is the minimum legal divisor of the
INTEGRATION, not a preference of this testbench.**

### 2.4 WHAT IS REGISTERED

* `hdl/tb/tb_v30_core.sv` default `ce_div` **1 → 4**.
* `sw/check_core.py --ce-div` default **1 → 4**.
* `--ce-div` **1, 2 or 3 is REFUSED** — `check_core.py` exits **2** citing
  C-a/C-b/C-c; the TB `$fatal`s if driven there anyway.  *Refuse-with-reason,
  the accepted-and-ignored family's fix pattern.*
* `sw/check_core.py` gains `CE_DIV_DEFAULT = 4` as the SINGLE declaration and
  every migrated caller reads it.

---

## §3 THE INSTRUMENT MIGRATION — EVERY DRIVER OF A 1:1 TRAIN

Audit: `grep -rn "ce_div\|ce-div" sw/ hdl/tb/` (excluding `sw/testdata/`).
**Nine call sites hard-code `+ce_div=1`; every other consumer inherits the TB
default and is migrated by the default flip.**

| tool | old | new | how |
|---|---|---|---|
| `hdl/tb/tb_v30_core.sv` (the default itself) | 1 | **4** | default + `$fatal` on `< 4` |
| `sw/check_core.py` | `--ce-div` default 1 | **4** | default + REFUSE 1/2/3 |
| `sw/ulockstep.py:318` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/sm3_s16_score.py:124` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/sm3_s16_fabric.py:205` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/sm3_famb_survey.py:96` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/sm3_haltsupp.py:142` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/f4a_boundary_battery.py:74` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/char_divergence.py:23` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/uarch.py:58` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/uscope.py:83` | `+ce_div=1` | **`CE_DIV_DEFAULT`** | migrated |
| `sw/check_boot.py`, `sw/check_seq.py`, `sw/check_ab_sim.py`, `sw/timed_fuzz.py`, `sw/emit_suite.py`, `sw/qdepth_probe.py`, `sw/tb_bootrun.py`, `sw/timed_wvec_gate.py`, `sw/class5_hext.py`, `sw/pi1a_trace.py`, … | (no plusarg) | **inherit 4** | default flip |
| `hdl/tb/tb_chain_lfsr.sv` | `ce@k, ce_half@k+1` | **`ce@k, ce_half@k+2`** | ⚠ **its own header clause (b) — *">= 1 idle cycle between assertions"* — was violated by its own train**; the LFSR gap draw is unchanged, the minimum-gap pattern becomes the contract's real minimum (period 4) |
| `hdl/tb/tb_sys.sv`, `tb_ab.sv`, `tb_harness.sv` | `nec_bus` div 8 | unchanged | already legal; gains the assertion |
| `hdl/rtl/core/` (ARCHIVED FSM core) | — | untouched | `fsm_core_archive_2026-08-04.md` governs.  Its gates are on-demand and will now run at div 4; **no FSM figure is re-registered here** |

---

## §4 THE CONTRACT BECOMES A GATE

New TB-only module `hdl/tb/ce_contract_check.sv`, wrapped `ifndef SYNTHESIS`,
instantiated in **`tb_v30_core.sv`** and **`tb_sys.sv`**.  It `$fatal`s on:

* **C-a** `ce && ce_half` on one clock;
* **C-b** any two assertions with **zero idle clocks** between them;
* **C-c** two `ce`s with **no `ce_half`** between them.

**REGISTERED NON-VACUITY**: in a scratch copy the TB's `ce_div` floor is
removed and the binary is driven at `+ce_div=1` and `+ce_div=2`; **the
assertion must fire (C-a at 1, C-b at 2) and the process must exit non-zero.**
An assertion that cannot fire is not evidence.

---

## §5 THE RE-REGISTRATION TABLE — OLD BASIS, **MEASURED AT HEAD BEFORE THE FIRST EDIT**

Every figure below was measured on this worktree at `58e082111b`, unmodified,
**at `--ce-div 1`** — the basis every standing figure was historically taken
on.  These are the *old-basis* column; the *new-basis* column is measured at
`--ce-div 4` and published beside it.

| leg | OLD BASIS (`--ce-div 1`), measured at HEAD |
|---|---|
| `check_core --opcodes all --cases 0` | **169,000 / 169,000** (cycles 169,000, arch 169,000) |
| `check_core --opcodes 8F.0 --cases 0` | **500 / 500** |
| `s10-hltsweep-w0 --waits 0` | **97 / 97** |
| `s10-hltsweep-w1 --waits 1` | **93 / 95** |
| `s13-hltsweep-w2 --waits 2` | **45 / 46** |
| `s13-hltsweep-w3 --waits 3` | **44 / 45**  (**Σ 279 / 283**) |
| `f4a_boundary --waits 0` | **160 / 160** |
| `f0lock_tranche --waits 0` | **400 / 400** |
| `v0.1-w1 --waits 1` / `v0.1-w3 --waits 3` | **1,200 / 1,200** each |
| `v0.1-w1 --opcodes EB --waits 1` | **200 / 200** |
| the four `evt` cells `w0/w1/w2/w3` | **200 · 1,200 · 200 · 1,200** |
| `v0.1-w1evt-biased --waits 1` | **1,200 / 1,200** |
| `check_boot --timed 220` / `--timed 400` | **MATCH 220** / **MATCH 400** |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350**, every form LOCKSTEP |
| `sm3_s16_score --core ucore` | census `busstat_other` **24** · `ARCH` **27** (**1,320 / 1,371**) |
| `check_ab_sim --core ucore` | **MATCH over 187 rows** |
| `ghost_launch_law score` | **200 / 200 = 100.0 %** |
| `qdepth_probe` | `rdq` **0:264 1:49 2:34** · `rd_done` **0:102 1:245** |
| `r7_lint` | **PASS**, 51 `stop` sites, 0 violations |
| `ss_lint --core ucore` | **PASS**, `SS_COUNT` **232** (109×2 + 122×2 + tag), **221** flops, **3** whitelist, **0** UNMAPPED |
| `test_artifact` | **45 / 45**, non-vacuous |
| `gen_ucore_qsf --check` | **up to date** |
| `ucrom_mif_check` | *NOTHING TO CHECK* — no `hdl/db` in this worktree (needs a build on disk); re-run after G6 |
| `chain_lfsr_gate` | measured at HEAD before the edit, in the results |
| `fz2_replay --leg ret` · `ie_pinfall_cell core` · `ghost_pred_cell core` | before-columns captured on THIS worktree at HEAD (the committed tables are another era's — `adcone_l1_results_2026-08-13.md` §1.3) |

**The block-I/O leg** (23 `v0.3` forms, 229,999 cycles) is registered as
**RUN IF RUNTIME PERMITS**; if it is not run it is reported as **DEFERRED**,
not as passing.

### 5.1 THE MEASUREMENT ORDER IS TWO STEPS, SO ATTRIBUTION IS FREE

1. **STEP 1 — instruments only.**  TB train + defaults + refusal + assertion.
   **RTL unchanged (still `negedge`).**  Re-measure the whole table.
   *Every delta here is the INSTRUMENT's, and by the ruling it is booked, not
   diagnosed.*
2. **STEP 2 — the one-word RTL edit.**  Re-measure the whole table again.
   *Every delta here is the RTL's, and §8's triggers apply to it in full.*

---

## §6 THE SDC, RE-DERIVED FROM C-a/C-b/C-c ALONE

`t1_half2` becomes a **posedge** flop enabled by `ce_half`.  Everything else is
a posedge flop enabled by `ce`.

| arc | today | after | change |
|---|---|---|---|
| `ce → ce` | launch n+1, latch n+5 (C-c) = 4.0 → `-setup 4 -hold 3` | unchanged | — |
| `ce → ce_half` | launch n+1, latch m+2.5 = **1.5**, spelled `-setup 2` | launch n+1, latch m+1 with m ≥ n+2 = **2.0**, spelled `-setup 2` | **numbers unchanged, meaning changed** |
| `ce_half → ce` | launch m+0.5, latch m+3 = **2.5** → `-setup 3 -hold 2` | launch m+1, latch p+1 with p ≥ m+2 = **2.0** → **`-setup 2 -hold 1`** | **a TIGHTENING** |
| `div_cnt → t1_half2` (ENABLE, unexcepted) | 0.5 | **1.0** | **the `k = 0.5` class CEASES TO EXIST** |

**Deleted because the thing they describe is gone**: the half-edge accounting
paragraph (`:56-58`); the *"⚠ WHAT THIS FIXED"* block (`:60-67`) — **retained as
dated HISTORY**, not as description; and the *"one arc … deliberately NOT
excepted"* block's *"TRUE half period"* content (`:91-98`) — **its disposition
survives**, the arc is still not excepted.

### 6.1 THE `$v30u_half` NAME HAZARD — THE BRIEF'S QUESTION, ANSWERED IN ADVANCE

**REGISTERED ANSWER: the `$v30u_half` collection CANNOT be deleted, and the
hazard therefore survives.**  The collection exists because `t1_half2` is the
one **`ce_half`-GATED** flop, not because it was **negedge-clocked**.  After the
edit it still needs `-setup 2` both ways, and it must still be *removed from*
the `-setup 4` `$v30u_ce` collection — leaving it in would hand a 2.0-period arc
a 4.0-period exception, the optimistic direction.  **The exact-name
`~DUPLICATE` hazard is unchanged and stays BOOKED**, with
`sw/sta_negedge_probe.tcl`'s collection-size line as its live falsifier.
*If the measurement contradicts this, the measurement is published and this
paragraph is struck.*

### 6.2 THE CLASS LABELS (the prior wave's §6, re-taken)

`sw/sta_truefmax_probe.tcl`'s labels move from `k`-values to STRUCTURAL names
and the `k` moves into `quartus_gate.py`'s checked `nominal` table:
`DEFAULT` 1.0 · `CE4` 4.0 · `INTO` **2.0** · `OUTOF` **2.0** · `ENABLE` **1.0**.
⚠ **Every negedge-era `truefmax` artifact stops parsing, and that is CORRECT** —
*absence must not read as data*.  `sw/test_quartus_gate.py` is re-registered:
the negedge-era fixtures are kept and asserted **REFUSED BY ERA**.

---

## §7 THE LADDER AND ITS BARS

**P-1 — the re-registration table (§5), both steps.**
**P-2 — the CONTRACT-LEGAL legs are BYTE-IDENTICAL across STEP 2** (the RTL
edit): `fz2_replay --leg ret` (306 seeds, ~1.24 M rows), `ie_pinfall_cell core`
(2,200 cells), `ghost_pred_cell core` (528 cells), `check_ab_sim`, `tb_sys`
everything.  ⚠ Both `fz2_replay` legs run `--no-fabric-era-guard`; the guard
already refuses on the PRE-edit tree, so this is a BEFORE-vs-AFTER comparison
**on one tree** and **no fabric claim is made from it**.
**P-3 — structural**: `r7_lint` PASS · `ss_lint` `SS_COUNT` **232** / **221**
flops / **3** whitelist / **0** UNMAPPED, **unchanged** (no register added) ·
`test_artifact` 45/45 · `gen_ucore_qsf --check` clean · `ucrom_mif_check` PASS
(post-build) · `fz2_immaterial falsify` G1-G8 PASS.
**P-3a — `chain_lfsr_gate`**: `CHAIN_DEPTH_MAX` / `entry_st` / `coincide` and
every structural quantity unchanged; **the four signatures ARE EXPECTED TO MOVE
TWICE** (once for the train change, once for the pin move) and are
**RE-REGISTERED on the new tree, stated as such**.  ⚠ A per-fabric-clock
signature is **not** a pin-identity bar — `t1_half2_posedge_results` §3.1's
mis-registration is not repeated.
**P-4 — G6, PAIRED, `--seeds 5` both configurations**, quoted as
`standing_gates.md` §A requires: two numbers, each with its binding cone and
its `k`, neither standing in for the other.

| id | registered |
|---|---|
| **P-4a** | both `worst-of-5` land **within their band's spread** of the L1 band [CONTROL 41.71, RETENTION 43.50]: CONTROL ≥ 39.06, RETENTION ≥ 41.79. **No Fmax floor and no Fmax benefit is claimed.** ⚠ The prior wave measured CONTROL **42.06** / RETENTION **41.49** on the identical RTL, so **RETENTION is expected near its floor and a miss there is a REPEAT OF A KNOWN DRAW, not a new fact** |
| **P-4b** | the `k = 0.5` class is **GONE**: `ENABLE` measures `k = 1.0000` on **10 of 10** draws |
| **P-4c** | `INTO` **2.0** and `OUTOF` **2.0** on every populated draw |
| **P-4d** | ⚠ **MEASURE, DO NOT ASSUME**: is `off_class` empty on all ten draws? It was empty on 10/10 last time and contaminated on 3/10 at `intcone`.  The `upper_bound: True` caveat **does not lift** either way (§6.1) |
| **P-4e** | every draw a G6 PASS, TNS **0.000 setup AND hold on every domain of all ten draws**, 0 errors / 0 latches / 0 `lpm_divide`, E7 ≤ 1 moved / 0 offending, E8 5/5, E10 N=5 |
| **P-4f** | the RETENTION receipt self-labels `RETENTION (X1_AD_RETENTION=1)`, `.rbf` differs from CONTROL (E-6 / E-9) |
| **P-4g** | ALMs within ±2 % of the L1 band (CTL 10,085-10,154 · RET 10,134-10,194) |
| **P-4h** | the input manifest **differs** from `b7b5dff2353c4747…` and from `d47c1d003d64c4c5…` — the check that the edit reached the compiler |

---

## §8 THE REVERT RULES, AS AMENDED BY THE RULING

**The landing STANDS unless one of these fires:**

* **R-1** any **CONTRACT-LEGAL** leg moves across **STEP 2** (the RTL edit):
  `fz2_replay --leg ret`, `ie_pinfall_cell`, `ghost_pred_cell`,
  `check_ab_sim`, or any `check_core` leg at `--ce-div 4` differing from the
  same leg at `--ce-div 8`.
* **R-2** `ss_lint` or `r7_lint` moves, or a register is added.
* **R-3** the contract assertion FIRES on any contract-legal leg.
* **R-4** either G6 configuration's `worst-of-5` collapses **more than 2.0 MHz
  below its band floor** (CONTROL < 39.71, RETENTION < 41.50).  ⚠ **This
  trigger fired last time at 41.49 on the identical RTL and was NOT attributed
  to the edit** (CONTROL moved the other way, both spreads widened).  It is
  kept at the same numbers; if it fires again on a draw whose CONTROL partner
  is healthy it is **reported as registered and NOT treated as attribution** —
  `standing_gates.md` §A governs, the same tree has drawn 19.42 and 45.91.
* **NOT a revert trigger, by the ruling**: any div-1-vs-div-4 delta in §5.
  Recorded, attributed to the old instrument, itemized for the follow-up wave.
* **NOT a revert trigger**: a `chain_lfsr_gate` signature move (P-3a).
* A miss on P-4b/P-4c/P-4d is **reported as registered**; if **P-4b** misses,
  §6's derivation is wrong and the SDC changes come back out with it.

---

## §9 THE SILICON BAR — FLASH #21, NOW **OWED**

The landing is real this time, so the clauses the prior wave wrote and did not
owe are **now owed** and are appended to the pending FLASH #21 skeleton:

> **(i)** first light `check_ab_hw` **MATCH 800 ×3**.
> **(ii)** directed pin-level cells — a named sample of `tf0f`, `ie-pinfall`
> and the 528-cell ghost-pred column — **chip** columns UNCHANGED (socket leg,
> cannot move), **core-vs-chip** reproducing this wave's offline column cell
> for cell.
> **(iii)** the full fz2 corpus with its named non-movers.
> **(iv)** `use_core=0` chip proof **MATCH 800** after everything, `div_guard`
> **PINNED** on every probe, `board_idle()` clean.
> **(v) ⚠ THE WRITE-T1 ROWS MUST BE BYTE-IDENTICAL ON SILICON.**  The
> turnaround is the ONLY pin transition this wave moves, so the MEMW/IOW T1
> rows of the fabric captures are its whole silicon surface.  **Any diff there
> is this wave's and nothing else's.**
> **(vi) ⚠ AND THE TURNAROUND MUST BE VISIBLE AT THE CORRECT INSTANT IN THE
> TWO-SAMPLE ROWS.**  `nec_bus` banks two AD samples per CPU clock; the ADDRESS
> sample (`ad_early`, at `tick_fall`) must still carry the **address** and the
> DATA sample (`tick_rise`) must still carry the **write word**, on **100 %** of
> write T1s in the captured population.  §2.3 of the prior prereg predicts this
> exactly; **the fabric leg is where it is confirmed or refuted, because that
> §2.3 is an argument about a rig and silicon is not a rig.**

**A rig-side-only redesign would have owed NO silicon bar.  This wave chose the
pin move, so the bar is owed BY CHOICE and is recorded as such.**

---

## §10 SCOPE

| file | why |
|---|---|
| `hdl/rtl/ucore/v30u_biu.sv` | the flop (§1), the D-cone falsifier, the header's negedge sentence |
| `hdl/tb/tb_v30_core.sv` | §2.3 the train, §2.4 the default and floor, §4 the assertion instance |
| `hdl/tb/tb_sys.sv` | §4 the assertion instance |
| `hdl/tb/tb_chain_lfsr.sv` | §3 — the train made contract-legal |
| `hdl/tb/ce_contract_check.sv` | **NEW** — §4 |
| `hdl/nec_test.sdc` | §6 |
| `sw/check_core.py` | §2.4 — `CE_DIV_DEFAULT`, the default, the refusal |
| the nine migrated callers | §3 |
| `sw/sta_truefmax_probe.tcl`, `sw/quartus_gate.py`, `sw/test_quartus_gate.py` | §6.2 |
| `sw/sta_negedge_probe.tcl`, `sw/sta_halfarc_probe.tcl` | §6.2 — corrected predictions in their headers |
| `docs/notes/standing_gates.md`, `CLAUDE.md`, `docs/notes/t1_half2_anatomy_2026-08-13.md` | the re-registration and the anatomy note |

**NOT touched:** `hdl/rtl/core/` (ARCHIVED FSM core), `hdl/rtl/system_large.sv`,
`hdl/rtl/nec_bus.sv`, `hdl/rtl/ucore/v30u_eu.sv`, `hdl/rtl/ucore/v30_core.sv`,
every save-state map file.
