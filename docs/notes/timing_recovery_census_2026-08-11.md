# THE CRITICAL-PATH CENSUS — where the ucore's 8 MHz went, and what actually binds

Branch `fuzz-v2-on-relanding`, base **`a86f40e45f`** (isolated worktree,
provisioned at `master` and RESET to the branch tip before anything was read).

**OFFLINE ONLY. NO BOARD, NO FLASH** (`flash_log.jsonl` untouched, no socket
command issued). Quartus is the instrument.

**THIS DOCUMENT IS COMMITTED BEFORE ANY EDIT**, which is the point of it: every
band movement in this repo's history from §52 onward is a scalar with no cone
attached to it, and an intervention chosen before the cone is named is a guess.

---

## §0 HEADLINE — four findings, in the order they change what you would do

| # | Finding |
|---|---|
| **F-1** | **THE ucore IS NOWHERE NEAR CRITICAL.** Core-register → core-register worst slack is **+39.594 ns** against a 31.250 ns period. The EU's twelve-position chain, the ROM, the datapath — none of it binds. |
| **F-2** | **FMAX IS SET ENTIRELY BY ONE CONE, AND IT IS AN *OBSERVATION* PATH.** All 60 worst setup paths — and all 4,000 the analyser will return — end on a **free-running sampler in the test harness**: `nec_bus\|ad_in_q[*]`. They launch from `v30u_eu\|upc_opc[*]` / `upc_page[*]` at **34–39 logic levels**. The class is `CORE → OUT`, which the SDC's 4/3 CE multicycle does **not** cover, so it is checked **single-cycle**. |
| **F-3** | **THE 8 MHz WENT INTO THE `ad_o` PIN MUX, NOT INTO THE CORE.** The two big steps are L1 (−3.96) and the 8F ghost READ (−2.23) = −6.19 of the −6.4 from 45.98 to 39.57, and the `git diff` from the R0 baseline shows exactly what they did to the binding cone: **two new leading terms on `assign ad_o`** (one of them a new 20-bit adder, one of them a live EU-combinational address), plus new terms on both `ad_oe_*` enables and a rewritten `ann_kill`. |
| **F-4** | **"ANALYSIS & SYNTHESIS IS NOT REPRODUCIBLE RUN TO RUN" IS NOT SUPPORTED BY THE 87-RECEIPT HISTORY.** Grouped by `inputs.sha256` + derived configuration, **28 of 30 multi-draw groups are EXACTLY identical**, and the two that are not are explained (a 3-day-separated pair differing by 0.35 MHz, and one group where a *different build flow* was used). See §4 — this changes the method, not just the prose. |

---

## §1 THE INSTRUMENT

New, and it is the deliverable that outlives this wave:

* **`sw/sta_census.tcl`** — top-N setup paths with launch/latch/logic-levels, a
  four-way **class** census (`CORE→CORE`, `ANY→CORE`, `CORE→ANY`, `ANY→ANY`),
  and launch/latch entity histograms.
* **`sw/sta_probe.tcl`** — the worst path in full node-by-node detail, plus the
  **ceiling**: the worst path once the observation registers are excluded, i.e.
  the best Fmax any fix to the binding class could reach.

Both name their corner explicitly:

```
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
```

`<rev>.sta.rpt` records `Delay Model : Slow 1100mV 100C Model`, so that is the
corner the gate's own Fmax comes from and the corner the census must read. A
census taken on a different corner attributes a cone that is not the one the
gate scored.

```bash
cd hdl && quartus_sta -t ../sw/sta_census.tcl nec_test nec_test_ucore <prefix>
cd hdl && quartus_sta -t ../sw/sta_probe.tcl  nec_test nec_test_ucore <prefix>
```

## §2 THE BASELINE, AND ITS RECEIPT

`python3 sw/quartus_gate.py` at `a86f40e45f`, clean `db`:

| | |
|---|---|
| verdict | **PASS** |
| Fmax (`divclk`) | **40.13 MHz** |
| worst setup | **+6.333 ns** |
| TNS | 0.000 setup **and** hold, every domain |
| ALMs | 12,246 / 41,910 (29 %) |
| latches / `lpm_divide` | 0 / 0 |
| inputs | 88 files, `98bef5844cede505…` |
| receipt id | `37fcb3691bb39b5a…` |

⚠ **`inputs.sha256` is `98bef5844cede505…`, which is FLASH #18's CONTROL input
hash byte for byte.** The ghost-launch-law wave changed no RTL, exactly as its
own results document says, so this is a **third draw** of a tree that has now
been drawn three times: **40.13 · 40.13 · 40.13**. That is the worst-of-N
evidence for the baseline and it did not cost a build to get.

**The `divclk` constraint is 31.250 ns (32.0 MHz).** Fmax 40.13 MHz is the
*reported capability*; the design **closes** with +6.333 ns of margin against
the constraint it is actually given. This distinction matters for the
ghost-relocation go/no-go and is picked up in §6.

### §2.1 The RETENTION baseline — and the `--retention` flag's first real run

`python3 sw/quartus_gate.py --retention`, clean `db`, same tree:

| | |
|---|---|
| verdict | **PASS**, self-labelling `RETENTION (X1_AD_RETENTION=1)` — **DERIVED**, not asserted |
| Fmax | **38.82 MHz** |
| worst setup | **+5.492 ns** |
| TNS | 0.000 setup **and** hold, every domain |
| ALMs | 12,276 / 41,910 (29 %) |
| receipt id | `638bc4340929d1f0…` |
| `.rbf` | **`ecda4b90c646ba49…`** |

⚠ **THAT `.rbf` IS FLASH #18's FLASHED `.rbf`, BYTE FOR BYTE**, and 38.82 /
+5.492 / 12,276 ALMs are FLASH #18's retention figures to the digit.

CLAUDE.md records of the new `--retention` flag: *"THE FLAG IS TESTED, NOT YET
EXERCISED — no bitstream has been built with it"*, with the registered
falsifier *"its receipt must self-label `RETENTION (X1_AD_RETENTION=1)` with an
`.rbf` differing from the control's"*. **This is that first exercise and the
falsifier passes on both clauses** — the control `.rbf` is
`b1fcbb0eac300352…`, different — and it passes in the strongest available form:
the flag's four-stage recipe reproduces the hand-run recipe's bitstream
**byte-identically**. The caveat is discharged.

## §3 THE CENSUS

### §3.1 The class census — the whole answer in four rows

Worst setup slack, asked of the whole netlist, by class
(`CORE` = `v30u_eu` / `v30u_biu` / `v30u_ucrom`):

| class | worst slack | covered by the SDC 4/3 CE multicycle? |
|---|---|---|
| `CORE → CORE` | **+39.594 ns** | **yes** |
| `ANY  → CORE` | +9.306 ns | no — single-cycle |
| `CORE → ANY`  | **+6.333 ns  ← THE CRITICAL PATH** | no — single-cycle |
| `ANY  → ANY`  | +6.333 ns (the same path) | — |

`CORE→CORE` at **+39.594 ns of a 31.250 ns period** is the finding that reframes
the whole campaign: **the microcoded core has more than a full clock period of
slack to spare on its own state.** Nothing inside `v30u_eu` is a timing problem.

### §3.2 The top-60 population is ONE class

| | |
|---|---|
| launch entity | `v30u_eu` — **60 of 60** |
| latch entity | `nec_bus` — **60 of 60** |
| launch registers | `upc_opc[1,3,5,6]`, `upc_page[0,1]` (and their `~DUPLICATE` copies) |
| latch registers | `ad_in_q[1]`, `ad_in_q[8]`, `ad_in_q[10]` |
| logic levels | **34–39** |
| slack band | +6.333 … +6.758 ns |

**And it is not merely the top 60.** `sw/sta_probe.tcl` asked for the worst
**4,000** paths in the design and *every one of them* ends on one of the 28
free-running observation registers. The complement had to be built by
subtraction because a scan could not find it.

### §3.3 What is in the cone — node by node

`report_timing -detail full_path` on the worst path. Data path **24.322 ns**:

| segment | ns | what it is |
|---|---:|---|
| `upc_opc[3]` → `u_ucrom\|ucdecode~*` (5 LUT levels) | **4.84** | the **decode table**, combinational LUT ROM |
| → `u_ucrom\|ucrom~*` (3 LUT levels) | **4.56** | the **microcode ROM**, combinational LUT ROM |
| → `r_farjmp~0`, `row_is_wr~0`, `comb~18` | 2.53 | micro-row field decode |
| → `Mux277~10/2/7` | 1.92 | EU row mux |
| → `s1_now[0]~32`, `ind_now[0]~1`, `retire_ok_e~0`, `eu_bnd_take` | 3.17 | EU retire / BOUND decision |
| → `u_biu\|pop_now~4`, `qs_e_now~7`, `ann_kill~0/~1` | 2.08 | BIU queue pop / **announcement kill** |
| → `u_biu\|ad_o[2]~10/11`, `ad_o[10]~92/93` | 3.88 | **the `ad_o` pin mux** |
| → `system_large\|core_ad[10]~16` | 1.09 | the pad/observation mux |
| → `nec_bus\|ad_in_q[10]\|d` | — | the free-running sampler |

**The combinational microcode ROM is 9.4 ns — 39 % of the whole path — and it
sits at the HEAD of the cone.** `v30u_ucrom` carries **1,050 ALUTs and 0
registers**: the ROM is LUT logic, not an M10K, so every micro-row field is
combinational from `upc_*`. Making it a block RAM would add a cycle of latency,
which is a timing-behaviour change and is out of scope by construction.

### §3.4 Why this cone exists at all — and it was a deliberate choice

`v30u_biu.sv:1018-1021`, written by the landing that put `eu_pair`/`eu_wdata`
there:

> *Loop rule (§20.2 as corrected by C1): this is REGISTER-ONLY LOOKAHEAD. Its
> cone is `r_run`/`r_cur_*` plus the EU's combinational `eu_pair` / `eu_wdata`,
> which are functions of EU REGISTERS only, and **`ad_o` is a pin that feeds
> nothing inside the core. It never enters the next-state cone.***

That reasoning is **correct and it is the reason `CORE→CORE` has +39.594 ns**.
The designers kept the long lookaheads off the core's own state. What no one
costed is that the pin they were pushed onto is sampled by a **free-running
register in the harness**, which is checked **single-cycle** — so the cost did
not disappear, it moved to the only place in the design that binds Fmax.

## §4 THE DETERMINISM FINDING — and what it does to the method

`sw/testdata/receipts/quartus_bitstream.jsonl`, **87 receipts**, grouped by
`(inputs.sha256, DERIVED configuration)`:

| | |
|---|---|
| groups with more than one draw | **30** |
| groups whose Fmax is **identical** across every draw | **28** |
| groups whose Fmax **varies** | **2**, and both are explained |

The two:

* `92b4ad1205e0…` — six draws, `[45.98, 46.33]`. **Five of the six are 45.98**;
  the 46.33 is from three days earlier. Spread **0.35 MHz**.
* `c2aa6493d55a…` — three draws, `[15.14, 15.14, 14.76]`. The 14.76 is the
  T9-era "RETENTION" run of the **accepted-and-ignored** period, taken with the
  **manual four-stage recipe** rather than `quartus_sh --flow compile` — a
  different flow, and its ALM count differs by 251. Not a redraw of the same
  thing.

And this wave added a 31st data point: a fresh clean-`db` build at input hash
`98bef5844cede505…` returned **40.13 MHz**, the same as FLASH #18's two draws.

**CONSEQUENCE FOR THE METHOD.** `standing_gates.md` §A and `ucore_provenance.md`
§74.4 govern with *"the same tree has drawn 19.42 and 45.91 MHz"*. Those two
figures **predate the receipt layer** and carry no `inputs.sha256`, so they
cannot be checked and are **not contradicted here** — but nothing in 87
receipted builds reproduces that behaviour, and the 19.42/45.91 pair is far more
consistent with two different *trees* than with two draws of one.

What this licenses, stated narrowly:

* **A per-edit delta of ≥ 0.4 MHz between two builds at DIFFERENT input hashes
  is readable as an effect of the edit**, not as draw noise.
* **It licenses nothing about a single build.** Two draws per configuration
  stays the registered method here, because the cost is one build and the
  falsifier is worth more than the hour.
* **The multi-seed worst-of-N gate is still not built.** What is now available
  is cheaper and was sitting in the tree already: **the receipt history is the
  distribution**, keyed by input hash, and §4's grouping is a two-minute query.

## §5 WHERE THE 8 MHz WENT — the band, landing by landing

From the receipt history (labels are the operator's; the `git.describe` in a
receipt names the tree's **base** commit and several builds were of dirty trees,
so the *order and labels* are reliable and the hashes are not):

| tree | CONTROL Fmax | ALMs | Δ |
|---|---:|---:|---:|
| master era (`66e3fddec2`) | 46.33 | 11,210 | |
| R0 baseline (`7e949925b7`) | 45.98 | 11,207 | |
| L0b instrument-only | 45.98 | 11,207 | **0.00** |
| **L1 re-landing (16 mechanisms)** | **42.02** | 11,917 | **−3.96** |
| `fuzz-v2-on-relanding` | 41.80 | 12,096 | −0.22 |
| 8F ghost family (FEED + READ) | *15.30* | 11,995 | *RED — the FEED, not landed* |
| **8F ghost READ alone** | **39.57** | 12,325 | **−2.23** |
| `INT.F3AA` repair | 39.37 | 12,340 | −0.20 |
| … 14 further wave-2/3/4 draws … | 37.28 – 41.48 | ~12,2xx | **no trend** |
| KM landing | 38.70 | 12,212 | |
| **FLASH #18 / HEAD** | **40.13** | 12,246 | |

**Two landings account for −6.19 of the −6.41 from 45.98 to 39.57.** Everything
after that wanders in a 37.28–41.48 band with no monotone direction — that is
placement noise around a design whose critical cone stopped changing.

### §5.1 …and the `git diff` says exactly where it went

`git diff 7e949925b7 HEAD -- hdl/rtl/ucore/v30u_biu.sv`, restricted to the
binding cone:

```
-assign ad_o = disp_inta ? {dinta_hi, 16'h0}                 <- baseline: a 5-way mux, every
                                                                data input REGISTER-sourced
+assign ad_o = (vector_follow_preview && t1_half2) ? eu_addr <- NEW: a LIVE EU-COMBINATIONAL
+            : flush_fast               ? flush_fast_addr        address, and a NEW 20-bit ADDER
+            : disp_inta                ? {dinta_hi, 16'h0}      ({flush_cs,4'd0}+{4'd0,flush_ip})
             : ...

-assign ad_oe_addr = (display || (r_run && (r_ts == TS_T1)) || halt_addr) && ...
+assign ad_oe_addr = (flush_fast || display || ...              <- NEW select term
-assign ad_oe_data = (r_run && r_cur_wr && ...
+assign ad_oe_data = (vector_follow_preview && t1_half2) || ... <- NEW select term

-wire ann_kill = (eu_susp || eu_post || q_flush) && r_cmt_valid && r_cmt_fetch && ...
+wire ann_kill = (q_flush || ...                                <- REWRITTEN, and it is on the
                                                                  measured worst path
```

The re-landed mechanisms are individually cheap **in the core**, where there is
39.6 ns of slack. They are not cheap on `ad_o`, and `ad_o` is the only cone in
the design that sets Fmax. **No standing gate saw this, because G6's bar is
≥ 32 MHz and every one of these builds cleared it.**

### §5.2 The CONTROL → RETENTION delta, explained

FLASH #18 measured CONTROL **40.13** and RETENTION **38.82**, −1.31 MHz, and
`standing_gates.md` records it as *"reported, not explained"*. The census
explains it. `system_large.sv:583-599` under `X1_AD_RETENTION`:

```verilog
assign core_ad_eff[gad] = core_ad_drv[gad] ? core_ad[gad] : core_ad_hold[gad];
```

That mux is inserted **between `core_ad` and `ad_in_q`** — i.e. one extra LUT
level on the last hop of *the single most critical net in the design*, and on
its select as well (`core_ad_drv = core_ad_oe | …`, and `core_ad_oe` is the
`ad_oe_*` expressions, which the same landings also deepened). The retention
delta is not mysterious and it is not placement: **it is one LUT on the worst
path.** Its historical sign changes (five draws where retention was *faster*)
are placement noise on top of a real +1 level.

**And the retention census confirms it structurally**, run on the retention
build's own reports:

| class | CONTROL | RETENTION |
|---|---:|---:|
| `CORE → CORE` | +39.594 | +38.529 |
| `ANY  → CORE` | +9.306 | +8.873 |
| `CORE → ANY` (**binding**) | **+6.333** | **+5.492** |
| top-60 launch entity | `v30u_eu` 60/60 | `v30u_eu` 60/60 |
| top-60 latch entity | `nec_bus` 60/60 | `nec_bus` 60/60 |

**The two configurations have the same critical structure and differ by one hop
on it.** The retention build is not a different timing problem; it is the same
one with the pad-retention mux inserted at the end.

## §6 WHAT THIS MEANS FOR THE GHOST RELOCATION

`ghost_launch_law_results_2026-08-11.md` §7 books ≈ 44 flops and **a 20-bit 3:1
mux on `cmt_addr`**, and names the risk itself: *"`cmt_addr` feeds the AD
pads."*

The census sharpens that from a worry into a measurement:

* `cmt_addr` feeds `t1_addr` feeds `ad_o` — **the binding cone, and only the
  binding cone.** The flops are free (the core has 39.6 ns of slack); the mux
  is not.
* A 20-bit 3:1 mux on the last hop is **the same shape as the retention mux**,
  which is measured at **−1.31 MHz**. That is the honest prior for its cost.
* Landing it on today's band puts RETENTION at ≈ **37.5 MHz**, i.e. **below the
  38.0 STOP**.

So the relocation's go/no-go is not about the relocation. **It is about whether
the observation-path cone can be taken off the critical path first**, which is
what this wave's intervention (§7) attempts and what the results document
scores.

## §7 THE INTERVENTION THE CENSUS POINTS AT — registered separately

The census names one candidate and it is **not an RTL edit**:

The binding class is `v30u_*` registers → `nec_bus`'s **free-running input
registration** flops. Those registers are the harness's *observation* of a bus
whose driver only changes on the divided CPU tick, and every one of their
consumers reads them at `tick_fall` / `tick_rise`, several sys clocks later.
The single-cycle check is therefore **stricter than the design requires**, and
that is a constraint gap, not a logic problem.

**It is pre-registered on its own, with its own bar, its own revert rule and its
own falsifier, in `timing_recovery_prereg_2026-08-11.md` — written and committed
BEFORE it is built.** It is not folded into this document, because a census that
also proposes its own answer is not a census.

## §8 WHAT THIS DOCUMENT DOES NOT CLAIM

1. **No fabric claim.** Every figure here is Quartus on `a86f40e45f`. No board
   was touched.
2. **§74.4 is not overturned**, it is bounded: 87 receipted builds show
   determinism at identical input hashes; the 19.42/45.91 pair predates the
   receipt layer and remains unexplained rather than refuted.
3. **The census is one draw's placement.** The *class* result (all 4,000 worst
   paths ending on 28 observation registers, `CORE→CORE` at +39.594) is
   structural and will not move; the exact node list of the single worst path is
   placement-specific and will.
4. **Nothing here says the re-landed mechanisms were wrong.** They are correct
   and they are cheap where the designers put them. What is reported is that
   their cost landed on the one cone nobody was measuring.
