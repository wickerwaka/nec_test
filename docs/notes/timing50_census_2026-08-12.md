# THE 50 MHz TIMING-CLOSURE CAMPAIGN — PHASE 0 CENSUS + PRE-REGISTRATION

**Branch `master`, HEAD `82d7561c4b`.  OFFLINE ONLY.  NO BOARD, NO FLASH.**
`flash_log.jsonl` untouched, no socket command issued, no Codex consulted, no
nested task spawned.

**This document is committed BEFORE any edit of this campaign is made.**  That
is its whole purpose: the census below is what the tree looked like before
anything moved, and §7 is the pre-registration the Phase-1 edits are scored
against.

| | |
|---|---|
| **Target** | worst-of-2 **RETENTION ≥ 50.0 MHz** *and* **CONTROL ≥ 50.0 MHz**, TNS 0.000 setup AND hold on every domain, ALMs ≤ 27 % |
| **Instrument** | `sw/quartus_gate.py` (G6) — Quartus 17.1.0 Lite, 5CSEBA6U23I7, Slow 1100 mV 100 C, `divclk` constrained at 31.250 ns (32.0 MHz) |
| **Census tools** | `sw/sta_census.tcl`, `sw/sta_probe.tcl`, and `sw/sta_negedge_probe.tcl` (**new this sitting**, §6) on each build's own fitted `db` |
| **Behaviour terms** | **ZERO behaviour change end to end** (§7.0) |

---

## §0 THE STANDING CONSTRAINT — THE CE/CE_HALF PORTABILITY CONTRACT

**USER RULING, 2026-08-12, recorded verbatim.  It supersedes any part of this
campaign's brief that conflicts with it, and it governs every derivation
below:**

> "With respect to ce/ce_half, you are not allowed to make assumptions based on
> how you are currently setting those clock enables. All you can assume is the
> ce and ce_half will not be asserted at the same time and there will be a one
> cycle gap between each assertion."

**THE TWO PREMISES, and they are the only ones any timing exception on a
`v30u_*` register may rest on:**

* **C-a** — `ce` and `ce_half` are never asserted on the same fabric clock.
* **C-b** — there is at least one idle fabric clock between any two assertions,
  so **successive enable assertions are ≥ 2 fabric clocks apart**.

**WHAT THIS KILLS.**  `cfg_clk_div = 8`, `div_max = 7`, `half = 4`,
`tick_rise`/`tick_fall` placement, `div/2 − 1 = 3` — every one of these is a
property of how **this rig** currently generates the enables, and none of them
may be used.  `nec_bus.sv` is one integration of the core, not the core's
specification.

**WHY IT EXISTS.**  `m72_downstream_timing_2026-08-12.md` §1 is the case: the
ucore in Arcade-IremM72 runs from an `ce_steady` train whose catch-up burst
issues `ce`/`ce_half` on **adjacent** fabric clocks.  A constraint derived from
this rig's divider is silently false there.

**AND IT IMMEDIATELY FOUND A DEFECT** — §6.  This document's own first draft
derived §5 and §6 from `cfg_clk_div = 8` and reached a *wrong* answer that
happened to be reassuring.  The ruling arrived before anything was landed.

### 0.1 The one derived extension, and it is derived from the CORE, not the rig

`ce → ce` spacing is **≥ 4** fabric clocks, and that is a **derivation from
C-a/C-b plus the core's own semantics**, not an assumption about a train:

1. `ce_half` is the CPU clock's **half-cycle** marker — `v30_core.sv:36`
   ("clock-enable for the T1 negedge half-cycle"), `v30u_biu.sv:97` ("the T1 AD
   half, gated by `ce_half`").
2. `t1_half2` is the ONLY thing it enables, and it is a pure function of
   `ce`-gated state: `(r_run && r_ts == TS_T1) || vector_follow_preview`.
3. It gates `ad_oe_data` (`v30u_biu.sv:1080`).  **If no `ce_half` occurs between
   two `ce`s, `t1_half2` holds stale and the BIU drives the wrong thing on AD
   for a whole bus cycle.**  So the core *structurally requires* **at least one
   `ce_half` between consecutive `ce`s** — this is a correctness requirement of
   the core, not a scheduling preference of a platform.
4. Therefore: `ce` at clock *n* → some `ce_half` at ≥ *n+2* (C-b) → the next
   `ce` at ≥ *n+4* (C-b again).  **`ce → ce` ≥ 4.**

**STRICT ALTERNATION IS NOT REQUIRED and is NOT assumed** — only "≥ 1 `ce_half`
between consecutive `ce`s".  Multiple `ce_half`s in a gap are harmless
(`t1_half2`'s update is idempotent).

**FALSIFIER, and it is deliberately not a timing one**: a platform that issues
two `ce`s with no intervening `ce_half`.  Such a platform has already broken
the core **functionally**, so the SDC's premise is no weaker than the core's
own operating requirement.  If that is ever wanted, the SDC must come back to
`-setup 2` on every `v30u_*` arc — and §6.4 sizes what that would cost.

---

## §1 HEADLINE — WHAT THE CENSUS FOUND BEFORE ANY EDIT

**The three "free wins" the brief named are worth ~0.1 MHz between them.  The
sitting's actual result is a CORRECTNESS FINDING the ruling exposed, and it
costs nothing to fix.**

1. **SignalTap** is CONTROL's worst path — but **the JTAG hub is not
   SignalTap's**, it is three `ENABLE_RUNTIME_MOD` hints in the RTL (§2.2), and
   the ceiling on removing it either way is **+0.104 ns ≈ +0.2 MHz** (§3.1).
   ⚠ Also: **`hdl/stp1.stp` has never existed in this repository** (§2.1).
2. **The E-1 `-setup 2 → 3` item is WITHDRAWN by the ruling** (§5).  Its
   "the RTL grants 3" argument was `div/2 − 1`, which §0 forbids.  Under the
   contract the guaranteed window is **1 period**, so **`-setup 3` is not
   derivable and even `-setup 2` rests on a rig-local premise** — reported to
   the user as an open question, not changed.
3. **The negedge item became a real edit, and it is a TIGHTENING** (§6).
   **`nec_test.sdc`'s uniform `-setup 4 -hold 3` is DISHONEST on both
   `t1_half2` arcs** — MEASURED at `setup_end_multicycle = 4`, latch time
   **109.375 ns**, where the contract warrants **46.875**.  The fix carves one
   register out of one collection and is predicted **free** (that arc has
   +89.047 ns of slack).

**The design's floor is two single-cycle boundary crossings whose launch
registers are not CE-gated** — `c_int_q → row_posted` and the **enable** arc
`div_cnt → t1_half2` — at **+8.7 to +9.0 ns**, where the ucore's own
`CORE→CORE` logic has **+38.6**.  Exactly as
`timing_recovery_results_2026-08-11.md` §7 wrote: *"Further Fmax beyond
~45 MHz needs RTL, not constraints."*  **50 MHz is a Phase-2 question, and
Phase 1 cannot reach it.**

---

## §2 THE BASELINE — HEAD `82d7561c4b`, WORST-OF-2, BOTH CONFIGURATIONS

### 2.1 The receipted baseline, and why it was not rebuilt four times

`quartus_gate.py`'s **88-file input manifest at this worktree's HEAD hashes to
`304b5d67ccd2cd5c0e9a5505347bacfed96a09b6514dab23ab602862b6729e8a`**, which is
**byte-identical** to the manifest of four receipted builds taken at
`3118a2db46` (the FLASH #20 G6 wave, `ghost_preflash20_results_2026-08-12.md`
§6.1).  `3118a2db46` is three commits behind HEAD and the three intervening
commits are documents and a `-s ours` merge; **the manifest is the artifact
that proves it, not the reasoning.**

| draw | config | Fmax | worst setup | TNS setup/hold | ALMs | receipt |
|---|---|---:|---:|---|---:|---|
| 1 | CONTROL | 45.61 | +8.892 | 0.000 / 0.000 | 12,282 (29 %) | `5cb7bf587a1a202b…` |
| 2 | CONTROL | 45.61 | +8.892 | 0.000 / 0.000 | 12,282 (29 %) | `9f231a850f9a71a1…` |
| 1 | RETENTION | 44.32 | +8.689 | 0.000 / 0.000 | 12,245 (29 %) | `24a78dc1c617384c…` |
| 2 | RETENTION | 44.32 | +8.689 | 0.000 / 0.000 | 12,245 (29 %) | `517c06c81d51eae8…` |

**WORST-OF-2 AT HEAD: CONTROL 45.61 / RETENTION 44.32.**

### 2.2 This sitting's own draws — an independent third draw per configuration

The receipted pair above is the worst-of-2; this sitting rebuilt both
configurations anyway, **in a different worktree**, because a census needs a
fitted `db` and because "the manifest matches" is a claim worth testing when
testing it is nearly free.

| draw | config | Fmax | worst setup | TNS setup/hold | ALMs | receipt |
|---|---|---:|---:|---|---:|---|
| **3 (this sitting)** | CONTROL | **45.61** | **+8.892** | 0.000 / 0.000 | **12,282 (29 %)** | `c0610ca34053a9d3…` |
| **3 (this sitting)** | RETENTION | **44.32** | **+8.689** | 0.000 / 0.000 | **12,245 (29 %)** | `15a901c4cce28c69…` |

**BOTH DRAWS REPRODUCE THE RECEIPTED FIGURES TO THE LAST DIGIT** — Fmax, worst
setup and ALMs identical in both configurations, 88-file input manifest
`304b5d67ccd2cd5c…`, `git 82d7561c4b`.  Three draws per configuration now
agree.  The retention receipt **self-labels `RETENTION (X1_AD_RETENTION=1)`**,
DERIVED from the reports (E-6/E-9).

⚠ **`standing_gates.md` §A still governs**: three agreeing draws is three
draws, not closure.  The same tree has drawn 19.42 and 45.91 MHz.

---

## §3 SIGNALTAP — WHAT IT IS AND WHAT IT COSTS

### 3.1 ⚠ FINDING: `stp1.stp` HAS NEVER EXISTED IN THIS REPOSITORY

Both `.qsf`s carry, verbatim:

```
set_global_assignment -name ENABLE_SIGNALTAP ON
set_global_assignment -name USE_SIGNALTAP_FILE stp1.stp
set_global_assignment -name SIGNALTAP_FILE stp1.stp
```

**and `hdl/stp1.stp` does not exist** — `git log --all -- hdl/stp1.stp` is
empty, `git log --all -- '*.stp'` is empty, and a filesystem-wide `find` for
the name returns nothing.  So the debug fabric in every bitstream this project
has flashed is whatever Quartus instantiates for `ENABLE_SIGNALTAP ON` with
**no instance file to describe** — at most a JTAG hub with no capture logic on
it.

**Reported, not resolved.**  It bears directly on Phase-1 item 1: the debug
capability being given up may already be zero.

### 3.2 ⚠ FINDING: **THE JTAG HUB IS NOT SIGNALTAP'S**

The census (§4) names CONTROL's worst path in full:

```
8.892   8 levels
  system_large|capture_buf:capture|altsyncram:buffer|altsyncram_ls91:auto_generated
             |sld_mod_ram_rom:mgl_prim2|ram_rom_data_reg[0]
  ->  sld_hub:auto_hub|…|sld_jtag_hub:\jtag_hub_gen:real_sld_jtag_hub|tdo
```

**`sld_mod_ram_rom` is the In-System Memory Content Editor node, and it is
instantiated by the RTL, not by the `.qsf`:**

```systemverilog
// hdl/rtl/capture_buf.sv:91
.lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=CAPT"),
// hdl/rtl/test_mem.sv:88, :112
.lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=ME0")
.lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=ME1")
```

Both modules' headers say what it is for: *"the host **normally** reads it over
the HPS bridge, but it can **also** be dumped over JTAG with the In-System
Memory Content Editor (`sw/dump_capture.tcl`)"*.

**So the brief's premise for item 1 is half right, and the wrong half is the
actionable one.**  The hub really is CONTROL's worst path — but it is pulled in
by three RTL `lpm_hint`s, and stripping `ENABLE_SIGNALTAP` from the `.qsf`
**cannot remove it**.

### 3.3 THE PREDICTION, REGISTERED BEFORE THE DRAW IS TAKEN

**S-1** — with `ENABLE_SIGNALTAP`/`USE_SIGNALTAP_FILE`/`SIGNALTAP_FILE` removed
from a scratch `.qsf` variant, `sld_mod_ram_rom → sld_jtag_hub|tdo`
**SURVIVES** as a timing path, because it is `ENABLE_RUNTIME_MOD`'s.

**S-2** — CONTROL Fmax on that draw lands in **[45.0, 46.5] MHz**.

**S-3** — ALMs move by **< 200** (< 1.6 %) from 12,282.

**If S-1 is REFUTED** — if the hub disappears — then `ENABLE_SIGNALTAP` *was*
instantiating a hub of its own, item 1 has a real (if small) benefit, and §3.1
gets sharper rather than weaker.  Either outcome is informative, which is why
this is written before the build.

**The ceiling on ANY version of item 1 is +0.104 ns**, whatever instantiates
the hub: the census's next-worst path is `div_cnt[4] → t1_half2` at **+8.996**
against the hub's **+8.892**.  Worth roughly **+0.2 MHz**, and no more.

### 3.4 The measurement — **ALL THREE PREDICTIONS MET, AND THE ANSWER IS ZERO**

A CONTROL draw from a clean `db` with the three assignments stripped from a
**scratch** `.qsf` variant (`hdl/nec_test.qsf` edited, `gen_ucore_qsf.py`
re-run so E1 stays green, both files reverted immediately afterwards — the tree
was left byte-identical).  Receipt `1820d66c0f23f784…`, input manifest
`e16f517983cbb361…` (**different** from `304b5d67ccd2cd5c…`, which is the check
that the strip actually reached the compiler).

| | SignalTap **ON** (HEAD) | SignalTap **OFF** (scratch) | Δ |
|---|---:|---:|---:|
| Fmax | 45.61 | **45.61** | **0.00** |
| worst setup | +8.892 | **+8.892** | **0.000** |
| ALMs | 12,282 | **12,282** | **0** |
| `CORE→CORE` | +38.626 | **+38.626** | 0 |
| `ANY→CORE` | +8.996 | **+8.996** | 0 |
| `CORE→ANY` | +27.751 | **+27.751** | 0 |
| `ANY→ANY` | +8.892 | **+8.892** | 0 |
| `sld_jtag_hub` in latch histogram | 4 | **4** | 0 |
| **`nec_test_ucore.rbf`** | `277e7de5f8fcfcde…` | **`277e7de5f8fcfcde…`** | **BYTE-IDENTICAL** |

* **S-1 MET.** `sld_mod_ram_rom → sld_jtag_hub|tdo` **survives**, at the same
  +8.892 over the same 8 levels, with `sld_mod_ram_rom` still 4 in the launch
  histogram and `sld_jtag_hub` still 4 in the latch histogram.  The hub is
  `ENABLE_RUNTIME_MOD`'s, exactly as §3.2 derived.
* **S-2 MET.** 45.61 ∈ [45.0, 46.5].
* **S-3 MET.** ALMs moved **0**, against a < 200 bar.

**AND ONE STRONGER RESULT THAN ANY PREDICTION ASKED FOR: the configuration
bitstream is BYTE-IDENTICAL.**  `ENABLE_SIGNALTAP ON` naming an `stp1.stp` that
does not exist contributes **nothing** to the `.rbf`.  (The `.sof` differs —
`f3351eb6f0c7e252…` vs `de6a89d32d8b6d3e…` — because it carries `.qsf`-derived
settings metadata that the `.rbf` does not.)

**CONSEQUENCE FOR P-1, and it resolves the capability question in §7.1:
removing these lines gives up NO debug capability, because there was none.**
Item 1 lands as **hygiene** — the `.qsf` no longer claims a debug fabric it
does not build and no longer names a file that has never existed — and it may
not be quoted as a timing result of any size.

---

## §4 THE CENSUS — TOP CONES PER CONFIGURATION

`sw/sta_census.tcl` + `sw/sta_probe.tcl` + `sw/sta_negedge_probe.tcl` on each
build's **own** fitted `db`, corner **Slow 1100 mV 100 C** — the corner the gate
scores, named rather than defaulted.

### 4.1 CONTROL — the cone table

| rank | slack | levels | launch → latch | class | **which phase addresses it** |
|---:|---:|---:|---|---|---|
| 1 | **+8.892** | 8 | `capture_buf\|…\|sld_mod_ram_rom\|ram_rom_data_reg[0]` → `sld_jtag_hub\|tdo` | OUT→OUT | **Phase 1 item 1** — ceiling **+0.104 ns**; and §3.2 says the hub is `ENABLE_RUNTIME_MOD`'s. |
| 2 | **+8.996** | 10 | `nec_bus\|div_cnt[4]` → `v30u_biu\|t1_half2~DUPLICATE` | ANY→CORE | **NOT relaxable — §6.3.** A true 0.5-period *enable* arc. **Phase 2, RTL only.** |
| 3 | +9.616 … +9.775 (**48 of the top 60**) | 45–49 | `system_large\|c_int_q` → `v30u_eu\|row_posted` | ANY→CORE | **Phase 2.** Booked with its required derivation by `ghost_preflash20_results_2026-08-12.md` §6.3. |

**Class census over the top 60 setup paths:** `OUT→CORE` n=**56**, worst
**+8.996** · `OUT→OUT` n=**4**, worst **+8.892**.
**Latch histogram:** `v30u_eu` 48 · `v30u_biu` 8 · `sld_jtag_hub` 4.
**Launch histogram:** `system_large` 48 · `nec_bus` 6 · `sld_mod_ram_rom` 4 ·
`hps_axi_slave` 2.

**Worst path per class, asked of the whole netlist (not a top-N scan):**

| class | worst slack | path |
|---|---:|---|
| `CORE→CORE` (the only class the 4/3 CE multicycle covers) | **+38.626** | `v30u_eu\|upc_opc[5]~DUPLICATE` → `v30u_eu\|r_kind[1]` |
| `ANY→CORE` | **+8.996** | `nec_bus\|div_cnt[4]` → `v30u_biu\|t1_half2~DUPLICATE` |
| `CORE→ANY` (**the E-1 cone**) | **+27.751** | `v30u_eu\|upc_opc[5]~DUPLICATE` → `nec_bus\|ad_in_q[1]` |
| `ANY→ANY` | **+8.892** | the JTAG hub path above |

**`sta_probe` ceiling leg**: all **28** observation registers excluded,
complement **15,195** endpoints, and the worst surviving path is **the same
JTAG-hub path at the same +8.892**.  **E-1's cone is not binding.**

### 4.2 RETENTION — the cone table

| rank | slack | levels | launch → latch | class |
|---:|---:|---:|---|---|
| 1 | **+8.689** | 47 | `system_large\|c_int_q` → `v30u_eu\|row_posted~DUPLICATE` | ANY→CORE |
| 2 | **+8.814** | — | `nec_bus\|div_cnt[3]` → `v30u_biu\|t1_half2~DUPLICATE` | ANY→CORE |

**Class census over the top 60:** `OUT→CORE` n=**60**, worst **+8.689** — the
INT cone owns the entire top-60 population.
**Latch histogram:** `v30u_eu` 52 · `v30u_biu` 8.
**Launch histogram:** `system_large` 52 · `nec_bus` 8.

**Worst path per class:**

| class | worst slack | path |
|---|---:|---|
| `CORE→CORE` | **+36.355** | `v30u_eu\|upc_opc[7]~DUPLICATE` → `v30u_eu\|r_kind[0]~DUPLICATE` |
| `ANY→CORE` | **+8.689** | `c_int_q` → `v30u_eu\|row_posted~DUPLICATE` |
| `CORE→ANY` (the E-1 cone) | **+25.579** | `v30u_eu\|upc_opc[7]~DUPLICATE` → `nec_bus\|ad_in_q[7]` |
| `ANY→ANY` | **+8.689** | the INT cone |

**⚠ THE JTAG HUB DOES NOT APPEAR IN THE RETENTION TOP 60 AT ALL.**  That is why
the two configurations differ: **CONTROL is bound by the debug fabric and
RETENTION by the INT cone**, which is
`ghost_preflash20_results_2026-08-12.md` §6.2's finding, reproduced here on
this tree's own builds.  The 1.29 MHz gap is *which of two unrelated cones
happens to bind*, not a cost of the retention model.

### 4.3 The single sentence the census produces

**Both configurations are floored by single-cycle boundary crossings whose
launch registers are not CE-gated, at +8.7 to +9.0 ns, and the ucore's own
logic has +36 to +39 ns.**  Every Phase-1 item lives on the other side of that
sentence.

---

## §5 E-1's THIRD PERIOD — **WITHDRAWN BY THE §0 RULING**

### 5.1 What the item was, and why it is off

The brief asked for `-setup 2 → -setup 3` on the E-1 observation multicycle,
on the ground that *"the RTL grants `div/2 − 1` = 3"*.

**That ground is `cfg_clk_div = 8`.  §0 forbids it.**  `hdl/nec_test.sdc`'s own
comment block is explicit that the number comes from the divider:

> `div = 8 (the divider of record)  ->  3 periods available`
> `div = 6                          ->  2`
> `div = 4                          ->  1   (no relaxation is legal)`

Under **C-a/C-b alone** there is no `div`.  Re-deriving with the contract's
vocabulary only:

* The core launches its pins at a `ce`, so a `v30u_*` output changes just after
  the posedge at which `ce` was asserted.  Call it **`C`**.
* `nec_bus`'s observation registers have **no clock enable** and sample on
  every fabric clock, so the first sample holding the new value is written at
  **`C+1`** — one period after launch.
* The consumers are gated by `tick_rise`/`tick_fall`, i.e. by `ce`/`ce_half`.
  The **earliest** consumer the contract permits fires at the next assertion,
  **`C+2`** (C-b), and a posedge flop firing at `C+2` reads the observation
  register as it stood **before `C+2`** — i.e. the sample written at **`C+1`**.

**That sample had exactly ONE period to settle.  Under the contract, the
honest exception is `-setup 1` — no relaxation at all.**

**So `-setup 3` is not derivable, and P-2 is WITHDRAWN rather than scored.**

### 5.2 ⚠ AND AN OPEN QUESTION FOR THE USER, REPORTED NOT ACTED ON

The same derivation says the **landed** `-setup 2` is not derivable from the
contract either.  It is derivable only on a **rig-local** reading:

* every register in `$obs_regs` lives in `nec_bus` / `system_large`;
* `nec_bus` **is** this rig's CE generator — it is not shipped downstream, and
  M72 replaces it wholesale with its own adapter;
* so its own divider is arguably a legitimate premise **for paths that end
  inside it**, in a way it is never a legitimate premise for a `v30u_*`
  register.

**This document does not change E-1.**  It is landed, it is
fabric-confirmed (`c59c2caf30`, FLASH #19: *"E-1 IS TRUE IN FABRIC ON EVERY LEG
THAT CAN SEE IT"*), and reverting a fabric-confirmed constraint on a reading of
a ruling would be the campaign making a decision that is the user's.

**THE QUESTION, stated so it can be answered:** does the §0 contract govern
only `v30u_* → v30u_*` arcs (the core's portable surface), or every arc the SDC
writes?  On the first reading E-1 stands as landed.  On the second it must come
back to `-setup 1`, and §4 says that costs nothing measurable — the E-1 cone
carries **+27.751 ns** (CONTROL) / **+25.579 ns** (RETENTION) against a binding
+8.7, so even removing the exception entirely leaves it far off the critical
path.  **Either answer is cheap; only one of them is true.**

---

## §6 THE `t1_half2` ARCS — RE-DERIVED FROM THE CONTRACT, AND THE 4/3 AUDIT

### 6.1 The population — ONE destination, enumerated, not assumed

Over **all 88 declared build inputs**, `negedge` appears on 10 lines.  Eight are
comments, an async-reset sensitivity list in `sys/pll_cfg/`, or inside
`system_large.sv`'s `` `ifndef SYNTHESIS `` block (lines 394-489).  **Exactly
one is a synthesised negedge-clocked flop:**

```systemverilog
// hdl/rtl/ucore/v30u_biu.sv:1087
always @(negedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (r_run && (r_ts == TS_T1)) ||
                                  vector_follow_preview;
```

`v30u_biu.sv:96` and `v30u_eu.sv:48` assert this in the RTL's own words; the
grep is the check on the assertion.  **M72's other two negedge destinations
(`v30_bus|addr_neg`, `ube_neg`) are M72's adapter and are NOT in this tree.**

**So the `v30u_*` register set has exactly two enable phases: 1,976 `ce`-gated
posedge flops, and ONE `ce_half`-gated negedge flop.**

### 6.2 The three arcs, derived from C-a/C-b alone

Convention: an enable asserted "in cycle *n*" means a posedge flop captures at
**posedge *n+1***, and a negedge flop captures at **negedge *n+0.5***.

| arc | derivation | true distance | honest constraint |
|---|---|---:|---|
| **`ce` → `ce`** | `ce` at *n*; ≥1 `ce_half` between (§0.1) at ≥ *n+2*; next `ce` at ≥ *n+4*. Launch posedge *n+1*, latch posedge *n+5*. | **4.0** periods | `-setup 4 -hold 3` |
| **`ce` → `ce_half`** (into `t1_half2`) | `ce` at *n*, launch posedge *n+1*. Earliest `ce_half` at *n+2* (C-b), capture negedge *n+2.5*. | **1.5** periods | **`-setup 2 -hold 1`** (a negedge dest's Nth latch edge is at N − 0.5) |
| **`ce_half` → `ce`** (out of `t1_half2`) | `ce_half` at *m*, launch negedge *m+0.5*. Earliest `ce` at *m+2* (C-b), capture posedge *m+3*. | **2.5** periods | **`-setup 3 -hold 2`** (a negedge source's Nth latch edge is at N − 0.5 from the posedge grid) |

**m72's §1.1 answer for the inbound arc is `-setup 2`, and OURS IS ALSO
`-setup 2` — IT COINCIDES, IT IS NOT COPIED.**  m72 reached it from *"two
`ce_cpu` pulses are never closer than TWO clk_sys periods"*, which is C-b in
that document's own words.  Same premise, same arithmetic, independently
written down here.  (Had this document kept its first, `div`-based derivation,
it would have said 3.5 and been **wrong** — see §6.3.)

### 6.3 ⚠ **THE FINDING: THE UNIFORM 4/3 IS DISHONEST ON BOTH `t1_half2` ARCS**

`hdl/nec_test.sdc` applies

```tcl
set_multicycle_path -setup 4 -from $v30u_regs -to $v30u_regs
set_multicycle_path -hold  3 -from $v30u_regs -to $v30u_regs
```

to **all** `v30u_*` registers uniformly, and `t1_half2` is a `v30u_biu`
register, so **it is in both the `-from` and the `-to` collection.**

**MEASURED, by `sw/sta_negedge_probe.tcl` on this sitting's own fitted `db`s** —
the analyser's arithmetic, not this document's:

```
--- DATA arc   v30u_* -> t1_half2 ---                    CONTROL      RETENTION
  dest clock inverted (negedge-triggered)              :       1              1
  setup multicycle start/end                           :   1 / 4          1 / 4
  launch time                                          :   0.000 ns      0.000 ns
  latch  time                                          : 109.375 ns    109.375 ns
  slack                                                : +89.047 ns   +89.958 ns

--- ENABLE arc div_cnt -> t1_half2 ---
  setup multicycle start/end                           :   1 / 1          1 / 1
  latch  time                                          :  15.625 ns     15.625 ns
  slack                                                :  +8.996 ns     +8.814 ns
```

**`109.375 ns = 3.5 × 31.250`.  The contract warrants `46.875 ns = 1.5 ×
31.250`.  THE CONSTRAINT IS OPTIMISTIC BY TWO FULL PERIODS ON THIS ARC.**  The
outbound arc (`t1_half2 → ce`-gated) is likewise constrained at 3.5 where the
contract warrants 2.5 — optimistic by one period.

**This is a live defect, not a hypothetical**: on a platform whose `ce`/`ce_half`
are 2 clocks apart (M72's catch-up burst is exactly that), the fitter has been
told it may take 3.5 periods to reach a flop that latches after 1.5.

**IT WAS NOT VISIBLE TO ANY STANDING GATE.**  `r7_lint` does not model timing
exceptions, Verilator does not see them, and G6 *believes* the SDC.  It became
visible only because §0's ruling forced the arc to be re-derived from premises
that do not include this rig's divider — which is the ruling paying for itself
inside one sitting.

### 6.4 What `ce → ce` would cost if §0.1's derivation were rejected

§0.1 derives `ce → ce ≥ 4` from the contract **plus** the core's structural
need for a `ce_half` per cycle.  If that second premise were ever rejected, the
only honest constraint on the whole core would be `-setup 2`, and the exposure
is large: the `CORE→CORE` worst path carries **+38.626 ns against a 125.0 ns
(4-period) budget**, i.e. an arrival time near **86 ns**, against a 2-period
budget of **62.5 ns**.

**This is independently corroborated by a different design**:
`m72_downstream_timing_2026-08-12.md` §3 measured the *same cone*
(`upc_page/upc_opc → ucdecode → ucrom → the chain → r_kind/modrm_reg`) at
**75.5 ns, ~71 logic levels, against a 62.5 ns 2-period budget — slack
−13.756** — and had to tighten `CHAIN_MAX` from 12 to 7 to close it.

**No such build was taken here**, because §0.1's derivation is sound and taking
one would be measuring a configuration nobody proposes.  It is written down so
the stake in §0.1's premise is visible: **that premise is load-bearing for
roughly 20 ns of budget.**

### 6.5 The `|ena` probe caveat — carried, and moot here

m72 §1 warns that probing `<reg>|ena` in the post-fit netlist **over-reports**:
Quartus folds some enables into a D-side feedback mux, leaving a register with
the right function and no `ena` pin.  Carried for the record, and it **changes
nothing here**, because §6.1's population was derived from the **RTL** — the
authority on what is negedge-clocked — and no `|ena` probe was used to reach
any conclusion in §6.

### 6.6 Disposition — this is Phase 1's real edit

**LAND: carve `t1_half2` out of the uniform 4/3 and give its two arcs the
contract's numbers.**  Predicted **free**: the inbound arc has +89.047 ns of
slack at a 109.375 ns budget, so an arrival near 20.3 ns against the honest
46.875 ns budget should still leave roughly **+26 ns** — three times the
binding +8.9.

**The `div_cnt → t1_half2` ENABLE arc is left alone and cannot be relaxed.**
`div_cnt` reaches `t1_half2` only through `ce_half` at the flop's **enable
pin**, never in its data cone; the enable must be valid at the negedge inside
the cycle in which it is asserted, which is **0.5 periods — exactly the
default**, measured above at `setup_end_multicycle = 1`.  A relaxation here
would be a false **pass**, the dangerous direction.  **It is the #2 cone in
CONTROL and #2 in RETENTION, and it is Phase 2's, as RTL.**

---

## §7 THE PRE-REGISTRATION

### 7.0 The zero-behaviour-change terms, and when they are scored

**Every landed edit must leave all of the following unmoved:**

| gate | registered value |
|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000/169,000 |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | 500/500 |
| HLT sweeps `s10-w0/w1` `s13-w2/w3` (⚠ **`--waits 0/1/2/3`**) | 97 · 93 · 45 · 44 = **279/283** |
| `ulockstep --golden all --cases 50` | 17,350/17,350 |
| `ghost_launch_law.py score` | 200/200, exit 0 |
| `r7_lint.py` | PASS, 0 violations |
| `ss_lint.py --core ucore` | `SS_VERSION` 0x8E / `SS_COUNT` 232 / 220 flops / 0 UNMAPPED |
| `test_artifact.py` | 45/45 |
| `gen_ucore_qsf.py --check` | PASS (it is G6's E1) |

**REGISTERED SCHEDULE, so that "run once at the end" is a declared choice and
not a shortcut discovered afterwards:** the ladder runs **once, at the end of
Phase 1**, not per edit.  Every Phase-1 edit is confined to `hdl/nec_test.sdc`
(a Quartus-only input no simulation gate reads) or to `sw/quartus_gate.py` /
`hdl/*.qsf` (build tooling no engine reads), so per-edit runs would measure the
same bytes four times.

⚠ **`fz2_replay`, `fz2_immaterial falsify` and every leg reading
`sw/testdata/campaigns/fz2*/captures/` CANNOT RUN IN AN ISOLATED WORKTREE** —
`git ls-files` on those directories returns 0; the corpus is untracked and
lives only in the main checkout.  **Owed, not claimed**, exactly as
`timing_recovery_results_2026-08-11.md` §4 booked them.

### 7.1 P-1 — the SignalTap policy

| | |
|---|---|
| **The edit** | `sw/quartus_gate.py` grows `--signaltap` (opt-in, **default off**); the `.qsf` stops carrying `ENABLE_SIGNALTAP`/`USE_SIGNALTAP_FILE`/`SIGNALTAP_FILE` unless asked for. |
| **BAR** | CONTROL worst-of-2 **≥ 45.61 MHz** (no regression) **AND** ALMs **≤ 12,282**. |
| **REVERT RULE** | If CONTROL worst-of-2 **< 45.61**, revert. A policy change that costs Fmax is not a timing win under any argument. |
| **May NOT be quoted as** | a timing win. §3.3's ceiling is **+0.104 ns ≈ +0.2 MHz** whatever the draw shows. It lands as **policy**. |

⚠ **CONSEQUENCE FOR THE USER, STATED EXPLICITLY**: after this edit the flashed
bitstream carries **no SignalTap debug fabric**.  A future in-fabric SignalTap
session needs `--signaltap` **and** an `stp1.stp` that, per §3.1, has never
existed.  Note §3.2: the In-System Memory Content Editor path
(`sw/dump_capture.tcl`) is **not** affected — it is `ENABLE_RUNTIME_MOD`'s and
survives.

⚠ **AND A DERIVATION-GATE CONSEQUENCE**: the lines are removed from
`hdl/nec_test.qsf`, so **both** revisions lose them together.  Removing them
from the ucore revision alone would make `gen_ucore_qsf.py --check` (G6's E1)
fail by construction — and would make the A/B bitstreams differ by the debug
fabric as well as by the core, which is exactly what that gate exists to
prevent.

### 7.2 P-2 — E-1's third period: **WITHDRAWN**

**Not scored, not built.**  §5.1: the item's premise is `div/2 − 1`, which §0
forbids.  §5.2 books the open question about the landed `-setup 2` for the
user, and changes nothing.

### 7.3 P-3 — the `t1_half2` carve-out (**the sitting's real edit**)

| | |
|---|---|
| **The edit** | `hdl/nec_test.sdc`: exclude `t1_half2` from the uniform 4/3 collection, and add `-setup 2 -hold 1` into it and `-setup 3 -hold 2` out of it, with §6.2's derivation written beside them. |
| **NATURE** | a **CORRECTNESS TIGHTENING**, not a win. It removes two periods of budget the contract never granted. |
| **BAR** | CONTROL worst-of-2 **≥ 45.11 MHz** (i.e. it costs **< 0.50 MHz**) **AND** setup **and hold** TNS **0.000** on every domain. |
| **REVERT RULE** | ⚠ **NONE ON THE Fmax CLAUSE.** An honest constraint that costs Fmax is still the honest constraint; if the bar is missed the *finding* is reported and the band moves down, and it is the user's call, not a revert. **The hold clause DOES revert**: a `-hold` companion that is wrong is invisible to every other check, so a non-zero hold TNS reverts the edit and re-derives it. |
| **PREDICTION** | **MET, at ≤ 0.1 MHz cost.** §6.6: the arc should retain ~+26 ns against a binding +8.9. Registered so the result is scored, not restated. |

### 7.4 The campaign-level bars

| | |
|---|---|
| **GO for Phase 2** | requires a named cone, a derivation for it, and a pre-registration of its own. **Not** licensed by this document. |
| **STOP** | any build below **38.0 MHz** on either configuration halts the campaign (the standing STOP, unchanged). |
| **Worst-of-2** | every quoted Fmax is the **worse** of two draws from a clean `db`, both draws printed. |
| **`standing_gates.md` §A governs** | ONE GREEN BUILD IS NOT CLOSURE. The same tree has drawn 19.42 and 45.91 MHz. |
| **§0 governs every SDC derivation** | a constraint on a `v30u_*` register that cannot be derived from C-a/C-b (plus §0.1) is not landable, whatever it buys. |

---

## §8 WHAT PHASE 2 WOULD HAVE TO ADDRESS — BOOKED, NOT OPENED

**Phase 1 cannot reach 50 MHz and this document says so before Phase 1 is
run.**  The gap is ~2 ns of slack (45.6 → 50.0 MHz is +8.9 → ~+11.3 ns) and
both remaining cones are RTL problems:

1. **`c_int_q → v30u_eu|row_posted`** — 45–49 logic levels, ANY→CORE,
   single-cycle, **48 of CONTROL's top 60 and 60 of RETENTION's top 60**.  It is
   structurally the class R7′ closed on `READY`, on the INT pin instead.  Its
   required derivation is already written down
   (`ghost_preflash20_results_2026-08-12.md` §6.3) and **under §0 it is now
   harder**: the E-1-analogue argument must be made from C-a/C-b, not from
   `div/2 − 1`.  A register stage on the pin, or the take moved onto the
   destination's `D` pin the way R7′ moved `eu_rd_edge`, are RTL answers that
   do not need a constraint at all.
2. **`div_cnt → t1_half2`'s ENABLE arc** — a true half-period path (§6.6).  No
   constraint can help.  The RTL answers are (a) register `ce_half` so the
   enable is a flop output, or (b) retime `t1_half2` to a posedge flop with a
   half-cycle-late data path.  Both change the core's clocking and both are
   **behaviour-visible**, so both are outside this campaign's zero-change
   terms and need their own campaign.
3. **The combinational LUT microcode ROM** — `v30u_ucrom`, 1,050 ALUTs and
   **0 registers**, is 9.4 ns at the head of the `CORE→ANY` cone
   (`timing_recovery_results_2026-08-11.md` §7).  Making it an M10K is the
   single biggest structural lever available and costs a cycle of latency, so
   it is banned by the zero-behaviour terms **by their terms, not by its
   merits**.
4. **`CHAIN_MAX`** — §51.2 derived maximum chain depth **6** and deliberately
   left the bound at 12; m72 §3 independently re-derived depth 6 on four LFSR
   seeds and measured that the untightened bound **costs depth, and depth is
   not recovered by the fold**.  M72 runs `CHAIN_MAX = 7`.  ⚠ **This tightens a
   bound §51.2 explicitly declined to tighten**, so it needs this tree's
   treatment and its own pre-registration — but it is the one lever with a
   worked precedent and a measured benefit in another fit.

**None of these is licensed by this document.**
