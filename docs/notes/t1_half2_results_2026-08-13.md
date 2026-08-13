# `t1_half2` — THE HALF-PERIOD ARC: **THERE IS NO WALL TO BREAK**

Anatomy and probe committed **before** any design or edit: `0e05e2153a`
(`docs/notes/t1_half2_anatomy_2026-08-13.md`, `sw/sta_halfarc_probe.tcl`, whose
pre-registered prediction was written into the script before it was run) and
`3924f5bd43` (`sw/sta_truefmax_probe.tcl`).  Tree `41a60bd42c` (`master`).
**Offline.  NO board, NO flash.  No RTL was changed.**

---

## §0 HEADLINE

**The campaign's premise is REFUTED by measurement, and no RTL landing is
warranted.**

`nec_bus|div_cnt[4] → v30u_biu|t1_half2` is not the wall before ~50 MHz.  It is
not the wall at all.  Measured on this tree's own fitted netlist it sits at
**90.91 MHz (CONTROL)** — the **fourth**-ranked ceiling, and **48.8 MHz clear
of the path that actually binds.**

| | |
|---|---|
| measured on both configurations | **90.91 MHz (CONTROL)** and **83.43 MHz (RETENTION)**, fourth-ranked on each |
| what was believed | `div_cnt → t1_half2` is the ceiling behind the observation class, at **44.10 / 45.17 MHz**, and *"50 MHz is not reachable by any constraint work"* (`timing50_e1_rederivation_2026-08-12.md` §6.3, `timing50_chainmax_results_2026-08-12.md` §7.3/§7.5) |
| why it was believed | both figures compute `Fmax = 1 / (T0 − slack)`, which is **only correct for a path whose launch-to-latch distance is one period** |
| what this arc's distance actually is | **0.5 periods** — launch 0.000 ns, latch **15.625 ns**, `setup_end_multicycle 1`, on an inverted (negedge) destination.  It was MEASURED and PRINTED in `timing50_census_2026-08-12.md` §6.3 and then not carried into the arithmetic |
| the correction | `T_min = T0 − slack / k`, `k` = distance in periods.  For `k = 1` it is the same formula; for `k = 0.5` it is **twice** the slack |
| measured, not argued | a three-point period sweep on the fitted netlist returns **`d(slack)/dT = 0.4920`** for this arc against a pre-registered **0.500** — **on BOTH configurations, to four decimal places, on two independent fits** |
| Quartus agrees, and always did | the `Fmax Summary` panel's own note: *"For paths between a clock and its inversion, FMAX is computed as if the rising and falling edges are scaled along with FMAX, such that the duty cycle (in terms of a percentage) is maintained."*  **G6's Fmax was never wrong; the campaign's derived ceiling was.** |
| disposition | **NO RTL CHANGE.**  A behaviour-visible edit that owes a silicon bar, to a flop 48.8 MHz clear of binding, for zero measurable benefit |
| what this leaves | a corrected ladder (§4) whose next two rungs are single-cycle rig↔core crossings, **not** this arc — and a *"50 MHz is unreachable"* verdict that rested on the wrong arithmetic and is therefore **withdrawn, not overturned** |

**TWO FURTHER FINDINGS, both unlooked for and both reported as registered:**

* **§5 — the draw spread.**  On the byte-identical 88-file input manifest
  `c23e63aa4cf19684…`, CONTROL read **42.09** where three CHAIN_MAX draws read
  39.79, and RETENTION read **39.99** where two read 43.76.  *"Three agreeing
  draws" is not evidence that a number is a property of the tree.*
* **§6.1 — a dead standing gate.**  `check_ab_sim` **could not BUILD either
  leg** at HEAD.  Fixed in `sw/` (no RTL), and both legs then MATCH over 187
  rows.  It is the second time this gate has died of its own file list.

---

## §1 THE ANATOMY (summary — the document is `t1_half2_anatomy_2026-08-13.md`)

* **D-cone**: three register terms (`r_run`, `r_ts == TS_T1`,
  `vector_follow_preview = eu_vector_post && r_rd_was_split`).  Not the
  problem: it carried **+89 ns of slack against a 109.375 ns budget** before
  Phase 1 and retains **+29.462 ns against 46.875** now (measured, §3).
* **Enable path**: `div_cnt` (free-running, no clock enable) → `tick_fall =
  (div_cnt == half-1)` → `bus_tick_fall` → `CE_HALF` → the flop's ENABLE pin.
  Six bits of comparator plus the haul across the chip, against half a period.
  **The critical half is the ENABLE.**
* **Consumers: exactly three, and all three are pin drives** — two terms of
  `assign ad_o` (`v30u_biu.sv:1056`, `:1062`) and one of `assign ad_oe_data`
  (`:1080`).  **ZERO consumers in the core's next-state logic.**
* **Which pin transition lands on the half-cycle**: exactly one — the **AD
  address→data turnaround of a WRITE's T1** (plus the vector-follow preview's
  `eu_addr` / `ad_oe_data`).  It is **not** ALE/`ASTB`, **not** `UBE`, **not**
  `BS`; none of those name this flop.
* **The pin-behaviour contract (C-PIN-1..3)**, derived from `nec_bus.sv`'s two
  sample instants: the turnaround must land strictly between the ADDRESS
  instant (`ad_early`, AD as it stood at the posedge opening the `ce_half`
  cycle) and the DATA instant (`ad_in_q` at `tick_rise`).  Today it sits at
  `ce_half`+0.5 fabric periods, with **1.0 fabric period of margin** on the
  address side.

**The contract is written down and it is not spent** — no design consumed any
of its freedom, because no design was needed.

---

## §2 THE ARITHMETIC ERROR, STATED PLAINLY

A setup path's slack is

```
   slack(T) = k·T + C
```

where `k` is the launch-to-latch distance in clock periods and `C` collects the
cell, net and clock-network delays, the clock uncertainty and the setup time —
**none of which scale with the clock period.**  So the period at which the path
stops making timing is

```
   T_min = T0 − slack / k          NOT       T0 − slack.
```

`nec_test.sdc` defines **five** classes on `divclk` and only ONE of them has
`k = 1`:

| class | exception | `k` |
|---|---|---:|
| default (no exception) | — | **1.0** |
| `$v30u_ce → $v30u_ce` | `-setup 4 -hold 3` | **4.0** |
| `$v30u_ce → t1_half2` | `-setup 2 -hold 1`, negedge destination | **1.5** |
| `t1_half2 → $v30u_ce` | `-setup 3 -hold 2`, negedge source | **2.5** |
| anything else `→ t1_half2` | none (deliberately) | **0.5** |

**`1/(T0 − slack)` is right for the first row and wrong for the other four.**
The campaign applied it to all of them, which is how a 90.9 MHz arc came to be
written down as a 44 MHz wall.

**The consequence for method, and it is the reusable part**: the binding path
is the one with the smallest **`slack / k`**, not the smallest `slack`.
`get_timing_paths -npaths N` is sorted by `slack` and therefore **cannot find
it** — a 4-period path with +25 ns of slack binds at 40 MHz and ranks thousands
deep.  `sw/sta_truefmax_probe.tcl` walks the five classes instead.

---

## §3 THE MEASUREMENT — CONTROL, on this tree's own fitted `db`

Build: `python3 sw/quartus_gate.py --label t1half2-baseline-control-d1`,
**PASS**, receipt `55f8c06426c6e69b…`, Fmax **42.09 MHz**, worst setup
**+7.489 ns**, TNS 0.000 setup and hold, ALMs **10,371 / 41,910 (25 %)**,
0 errors / 0 latches / 0 `lpm_divide`, input manifest
**`c23e63aa4cf19684…`** (88 files).  Corner Slow 1100 mV 100 C,
`divclk` 31.250 ns.

### 3.1 THE PERIOD SWEEP — the prediction was committed before the run

`sw/sta_halfarc_probe.tcl` re-defines `divclk` at three periods on the SAME
fitted netlist and re-reports each path.  The prediction written into the
script at `0e05e2153a`, before it had ever been run, was
*"`d(slack)/dT` must equal the `k` reported in section 1 for each path: 1.000
for the observation cone, 0.500 for the ENABLE arc, 4.000 for the CE-multicycle
class."*

| path | T=31.250 | T=28.125 | T=25.000 | **measured `d(slack)/dT`** | predicted |
|---|---:|---:|---:|---:|---:|
| whole-design worst (`upc_opc → ad_in_q`) | +7.489 | +4.414 | +1.289 | **0.9920** | 1.000 |
| worst `$v30u_ce → t1_half2` (the DATA arc) | +29.462 | +24.824 | +20.137 | **1.4920** | 1.500 |
| **`div_cnt → t1_half2` (the ENABLE arc)** | **+10.125** | **+8.612** | **+7.050** | **0.4920** | **0.500** |
| ceiling behind the observation class | +8.309 | +5.234 | +2.109 | **0.9920** | 1.000 |

**Every row is within 0.008 of its prediction, and the 0.008 is the same on
every row: `derive_clock_uncertainty` recomputing at each period.  It is a
deficit, i.e. in the conservative direction.**

The third row is the whole finding.  *(The `corecore` row of the raw artifact
reads 1.4920 and not 4.000 because the worst `$v30u_ce → $v30u_ce` path by
SLACK is the `k = 1.5` arc into `t1_half2`, which is itself a `v30u_biu`
register — §2's point about slack-ordering, appearing inside the instrument
that was written to make it.  The genuine `k = 4` class is queried separately
in §3.2.)*

### 3.2 THE FIVE CLASSES, EACH WITH ITS OWN `k` — CONTROL

`sw/sta_truefmax_probe.tcl`, artifact `docs/notes/t1half2/ctl_baseline.truefmax.txt`.

| class | worst path | `k` | slack | **campaign formula** | **CORRECTED** |
|---|---|---:|---:|---:|---:|
| default | `upc_opc[6]~DUP → nec_bus\|ad_in_q[16]` | 1.0 | +7.489 | 42.09 | **42.09 MHz — BINDS** |
| `k=4` CE multicycle | `upc_opc[6]~DUP → v30u_eu\|opc_base[4]` | 4.0 | +57.784 | n/a (`T0 − slack` < 0) | **59.51 MHz** |
| `k=1.5` data arc | `upc_opc[6]~DUP → t1_half2` | 1.5 | +29.462 | 559 | **86.14 MHz** |
| `k=2.5` outbound | `t1_half2 → v30u_biu\|r_cur_data[5]` | 2.5 | +66.273 | — | **210.93 MHz** |
| **`k=0.5` ENABLE arc** | **`nec_bus\|div_cnt[4] → t1_half2`** | **0.5** | **+10.125** | **47.34** | **90.91 MHz** |

**TRUE CEILING = 42.09 MHz, bound by the default class — and that is Quartus's
own `Fmax Summary` figure to the digit.**  The two agree because Quartus
computes Fmax by scaling the clock, which is the same operation `T0 − slack/k`
performs by hand.

**So G6 has never quoted a wrong Fmax.**  What was wrong was a *derived*
ceiling computed outside Quartus, on paths Quartus was already handling
correctly.

---

## §4 THE CORRECTED LADDER — AND THE 50 MHz DOOR IS NOT SHUT BY THIS ARC

CONTROL, all observation endpoints excluded, restricted to `divclk → divclk`
because Quartus's own note says FMAX is computed only for same-clock paths.
*(A first run without that filter returned the `sld_jtag_hub` at rung 2; it is
a cross-domain path, it is not a `divclk` ceiling, and it is excluded for that
reason and not for its answer.)*

| rung | cone | `k` | slack | corrected ceiling |
|---|---|---:|---:|---:|
| **binding** | `upc_opc[6]~DUP → nec_bus\|ad_in_q[16]` | 1.0 | +7.489 | **42.09 MHz** |
| **1a** | `c_int_q → v30u_eu\|row_posted` | 1.0 | +8.309 | **43.59 MHz** |
| — | `$v30u_ce → $v30u_ce` (the EU's own 4-period class) | 4.0 | +57.784 | 59.51 MHz |
| — | `$v30u_ce → t1_half2` | 1.5 | +29.462 | 86.14 MHz |
| — | **`div_cnt → t1_half2`** | 0.5 | +10.125 | **90.91 MHz** |
| — | `t1_half2 → $v30u_ce` | 2.5 | +66.273 | 210.93 MHz |

RETENTION is §7.2/§7.3 and ranks identically, with the enable arc fourth at
**83.43 MHz** and the observation class worth **+9.52 MHz** rather than +1.50.

**Three corrections to the record follow, and all three cut against the
campaign's own conclusions:**

1. **The observation class is worth `+1.50 MHz` (CTL) / `+9.52 MHz` (RET), not
   `+1.82`/`+3.99` and not `+0.39`/`+4.21`.**  Every one of those figures is
   the distance to `div_cnt → t1_half2` computed at `k = 1`.  The distance to
   the *correct* wall behind it — `c_int_q → row_posted`, a single-cycle
   crossing — is what is tabulated here.
2. **`c_int_q` DOES bind, once the observation class is fixed.**
   `timing50_e1_rederivation_2026-08-12.md` §6.2 concluded *"closing `c_int_q`
   completely would move Fmax by ZERO"*, having ranked it against the enable
   arc's mis-derived +9.114 → 45.17.  Corrected, `c_int_q → row_posted` is the
   first rung on **both** configurations and the enable arc is 40 MHz behind
   it.  **§6.2's advice against a `c_int_q` wave is withdrawn on its own
   numbers, by arithmetic and not by a new build.**
3. **"50 MHz is not reachable by any constraint work" is not established by the
   evidence offered for it.**  That claim rested on a measured ceiling of
   44.10/45.17 MHz behind the observation class.  The ceiling is **43.59 (CTL)
   / 49.51 (RET)**, and behind *that* the next class is the EU's own 4-period
   cone at **59.51 / 60.29 MHz**.
   **This does not say 50 MHz is reachable** — the two rig↔core single-cycle
   crossings still have to be closed, each with its own equivalence cost, and
   §5 says a single draw is worth ±2 MHz.  It says the *ceiling argument that
   closed the door is arithmetic, and the arithmetic is wrong.*  The door needs
   re-opening on evidence, not on this paragraph.

---

## §5 A SECOND FINDING, REPORTED AS REGISTERED: FOUR DRAWS, ONE MANIFEST, 2.30 MHz

`timing50_chainmax_results_2026-08-12.md` §7.1 records **three agreeing CONTROL
draws** at `39.79 MHz / +6.121 ns / 10,358 ALMs` and concludes *"so the CONTROL
loss is a property of the tree, not of a draw."*

**This wave's CONTROL draw, on the byte-identical 88-file input manifest
`c23e63aa4cf19684…`, read `42.09 MHz / +7.489 ns / 10,371 ALMs`.**

The only `hdl/` difference between `4dd395a7ad` (the CHAIN_MAX landing) and
`41a60bd42c` (HEAD) is `hdl/tb/tb_chain_lfsr.sv`, a testbench, which is **not a
build input** — and the identical manifest hash proves it independently.

**+2.30 MHz and +13 ALMs from an identical input set.**  Recorded, **not
explained**.  `standing_gates.md` §A's *"one green build is not closure"*
governs and this is the sharpest instance of it yet: **three agreeing draws did
not make a fourth agree**, so *"three agreeing draws" is not evidence that a
number is a property of the tree.*

**And the RETENTION leg moved the other way by more.**  CHAIN_MAX registered
`43.76 / +8.396 / 10,355 ALMs` on two agreeing draws; this wave's RETENTION
draw read **`39.99 / +6.242 / 10,257 ALMs`** — **−3.77 MHz**, same manifest.

| | registered (CHAIN_MAX, agreeing draws) | this wave, one draw each | delta |
|---|---:|---:|---:|
| CONTROL | 39.79 (×3) | **42.09** | **+2.30** |
| RETENTION | 43.76 (×2) | **39.99** | **−3.77** |

**The two configurations' ORDER also flipped**: CHAIN_MAX had RETENTION 3.97
MHz above CONTROL; here it is 2.10 MHz below.  This is the same
retention-vs-control sign instability `standing_gates.md` §A has recorded and
declined to explain at FLASH #13 (+0.46), #14 (+1.50), #15 (+2.24), #16
(+0.12), #17 (+0.71) and #18 (−1.31) — reported, not explained, and **this wave
takes ONE draw per configuration and says so rather than calling either number
a band.**

**Everything in §3, §4 and §7 is a RATIO between classes measured on ONE fitted
netlist, and ratios within a netlist are not affected by this.**  The absolute
`42.09` and `39.99` are single draws of a distribution nobody has
characterised.  **The finding is not**: the ENABLE arc ranks fourth on
CONTROL's netlist and fourth on RETENTION's, at 2.16× and 2.09× the binding
path's ceiling, and the `d(slack)/dT = 0.4920` that produces those ranks was
measured identically on both.  **A draw-to-draw swing cannot turn a `k = 0.5`
arc into a `k = 1` arc.**

---

## §6 THE LADDER — RE-MEASURED AT HEAD, ALL AT THEIR REGISTERED VALUES

Nothing in this wave changed a byte of RTL, so these are a control on the
worktree, not an equivalence claim.

| gate | registered | measured |
|---|---|---|
| `test_artifact` | 45/45 | **45/45**, non-vacuous |
| `r7_lint` | PASS, 0 violations | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations |
| `ss_lint --core ucore` | `SS_COUNT` 232 / 220 flops / 0 UNMAPPED | **PASS** — 109×2 BIU + 122×2 EU + tag = **232**; **220** architectural flops, 0 UNMAPPED |
| `gen_ucore_qsf --check` | PASS | **PASS** (G6's E1, on every build) |
| `check_core --opcodes all --cases 0` | 169,000 | **169,000/169,000** |
| `check_core --opcodes 8F.0` | 500 | **500/500** |
| HLT sweeps w0/w1/w2/w3 (⚠ `--waits`) | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** |
| the four `evt` cells `w0`/`w1`/`w2`/`w3` (⚠ `--waits`) | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350/17,350 — ALL CASES LOCKSTEP** |
| `check_boot --core ucore` | 220 MATCH | **MATCH over 220 rows** |
| `sm3_s16_score --core ucore` | 1,320/1,371 | **1,320/1,371** (`busstat_other` 24 · `ARCH` 27) |
| `ghost_launch_law score` | 200/200 | **200/200 = 100.0 %**, all three populations |
| `chain_lfsr_gate` | PASS, depth ≤ 6 | **PASS** — `CHAIN_MAX 7`, depth [6], 0 overflows, 4 seeds × 400,000 clocks, `coincide 0` |
| `check_ab_sim --core ucore` | MATCH 187 rows | **MATCH over 187 rows** — ⚠ **only after a RIG FIX; it could not BUILD at HEAD, see §6.1** |
| `check_ab_sim --core fsm` | MATCH 187 rows | **MATCH over 187 rows** — same fix |
| **G6 CONTROL** | ≥ 32 MHz, setup > 0, TNS 0.000 | **PASS — 42.09 / +7.489 / 0.000 / 0.000 / 10,371 ALMs**, receipt `55f8c06426c6e69b…` |
| **G6 RETENTION** | ≥ 32 MHz, setup > 0, TNS 0.000 | **PASS — 39.99 / +6.242 / 0.000 / 0.000 / 10,257 ALMs**, receipt `f83bdb4400eaeab0…`, self-labelling RETENTION |
| `fz2_replay` | byte-identical | ⚠ **NOT RUN — the FABRIC ERA GUARD REFUSED**, §6.2 |

### 6.1 ⚠ A RIG-INTEGRITY FINDING: `check_ab_sim` COULD NOT BUILD EITHER LEG

`sw/check_ab_sim.py` is a standing gate registered at *"both legs MATCH over
187 rows"*.  **At `41a60bd42c` it could not build at all**, on either core:

```
%Error-PKGNODECL: rtl/system_large.sv:476:29: Package/class 'v30_ss_pkg'
not found, and needs to be predeclared (IEEE 1800-2023 26.3)
```

`_CORE_RTL` lists the save-state package first *within the core list*, and that
list is appended **after** `_PLATFORM` — but `system_large.sv` acquired a
`v30_ss_pkg::SS_COUNT` reference of its own when the **M10-SYS save-state
freeze probe** landed (`:476`, inside the `ifndef SYNTHESIS` arm).  Verilator
requires a package to be predeclared, so from that landing onwards the gate
was dead.

**FIXED** (`b5d8a6bfd4`, `sw/` only, no RTL): the package file moves to the
head of the whole list.  Both legs then **MATCH over 187 rows** — their
registered value, recovered and not restated.

**This is the SECOND death of this gate by its own file list** — the first is
the 2026-07-13 drift already recorded in the file's own comment — and both
times nothing saw it, **because a gate that cannot build reports no failures.**
It is the same shape as the SM2 `want_raw` finding: *verify a flag exists AND
that the callee accepts it* has a twin, *verify a gate BUILDS, because a green
log is not the same as a run.*

### 6.2 `fz2_replay` — REFUSED BY THE ERA GUARD, AND REPORTED AS REFUSED

`sw/fz2_replay.py` refuses to score: HEAD differs from FLASH #20's bitstream
(`26d6e79166183a21…`, flashed 2026-08-12) in `hdl/nec_test.qsf`,
`hdl/nec_test.sdc` and `hdl/rtl/ucore/v30u_eu.sv` — **that is E-1's deletion
and the `CHAIN_MAX` landing, both committed before this wave, and not anything
this wave did.**  84 of 88 inputs hash identical; `hdl/nec_test_ucore.qsf` is
the one declared §70.7 exemption (Quartus rewrites it in place).

**The guard was NOT bypassed and no fabric claim is made.**  Nothing in this
wave changes a byte `fz2_replay` reads, because nothing in this wave changes
RTL at all.

---

## §7 RETENTION — THE CONFIGURATION THE BOARD RUNS, AND IT AGREES

Build: `python3 sw/quartus_gate.py --retention --label
t1half2-baseline-retention-d1`, **PASS**, receipt `f83bdb4400eaeab0…`, which
**self-labels `RETENTION (X1_AD_RETENTION=1)`, DERIVED from the reports** (the
E-6 check).  Fmax **39.99 MHz**, worst setup **+6.242 ns**, TNS 0.000 setup and
hold, ALMs **10,257 / 41,910 (24 %)**, 0 errors / 0 latches / 0 `lpm_divide`,
same input manifest `c23e63aa4cf19684…`.

### 7.1 THE PERIOD SWEEP — the same four slopes, to four decimal places

| path | T=31.250 | T=28.125 | T=25.000 | measured `d(slack)/dT` | predicted |
|---|---:|---:|---:|---:|---:|
| whole-design worst | +6.242 | +3.167 | +0.042 | **0.9920** | 1.000 |
| worst `$v30u_ce → t1_half2` | +30.580 | +25.942 | +21.255 | **1.4920** | 1.500 |
| **`div_cnt → t1_half2`** | **+9.632** | **+8.119** | **+6.557** | **0.4920** | **0.500** |
| ceiling leg | +6.742 | +3.667 | +0.542 | **0.9920** | 1.000 |

**Byte-for-byte the same four slopes as CONTROL, on a different fit of a
different configuration.**  Two independent netlists, one answer.

### 7.2 THE FIVE CLASSES — RETENTION

| class | worst path | `k` | slack | **campaign formula** | **CORRECTED** |
|---|---|---:|---:|---:|---:|
| default | `upc_opc[5]~DUP → nec_bus\|ad_in_q[7]` | 1.0 | +6.242 | 39.99 | **39.99 MHz — BINDS** |
| `k=4` CE multicycle | `upc_opc[7] → v30u_eu\|opc_base[4]` | 4.0 | +58.658 | n/a (< 0) | **60.29 MHz** |
| `k=1.5` data arc | `upc_opc[1]~DUP → t1_half2` | 1.5 | +30.580 | 1493 | **92.05 MHz** |
| `k=2.5` outbound | `t1_half2 → v30u_biu\|r_cur_data[5]` | 2.5 | +67.511 | n/a (< 0) | **235.54 MHz** |
| **`k=0.5` ENABLE arc** | **`div_cnt[4] → t1_half2`** | **0.5** | **+9.632** | **46.26** | **83.43 MHz** |

**TRUE CEILING = 39.99 MHz, = Quartus's own `Fmax Summary` to the digit.**

### 7.3 THE RUNG THAT REPRODUCES THE CAMPAIGN'S OWN QUERY, AND CORRECTS IT

With **all 48** observation endpoints excluded — 28 `nec_bus` samplers **plus
the 20 `core_ad_hold`**, which is the exact set
`timing50_e1_rederivation_2026-08-12.md` §6.3 used — the worst surviving path
by **slack** is:

> **`nec_bus|div_cnt[4] → v30u_biu|t1_half2`, +9.632 ns.**

**That is §6.3's finding, reproduced exactly.**  The measurement was right; the
conversion was not:

| | §6.3 | this wave |
|---|---:|---:|
| surviving path | `div_cnt[4] → t1_half2` | **same path** |
| its slack | +8.573 (that draw) | +9.632 (this draw) |
| `k` used | **1.0 (implicitly)** | **0.5 (measured, twice)** |
| ceiling claimed | **44.10 MHz** | **83.43 MHz** |

And the rung query itself is the trap §2 names: it returns the worst path by
**slack**, so on RETENTION it hands back a `k = 0.5` arc.  Asking instead for
the worst **single-cycle** survivor:

> **RUNG 1a: `c_int_q → v30u_eu|row_posted`, `k = 1.0`, +11.051 → 49.51 MHz.**

**So on RETENTION a perfect fix of the whole observation class is worth
39.99 → 49.51 MHz — `+9.52 MHz`, against the `+1.82` the E-1 re-derivation
registered and the `+0.39` CHAIN_MAX re-quoted it at.**

### 7.4 THE TWO CONFIGURATIONS, SIDE BY SIDE

| | CONTROL | RETENTION |
|---|---:|---:|
| G6 Fmax (= true ceiling) | **42.09** | **39.99** |
| behind the observation class (`c_int_q → row_posted`) | 43.59 | **49.51** |
| the EU's own `k=4` class | 59.51 | 60.29 |
| **`div_cnt → t1_half2`** | **90.91** | **83.43** |
| `$v30u_ce → t1_half2` (`k=1.5`) | 86.14 | 92.05 |
| `t1_half2 → $v30u_ce` (`k=2.5`) | 210.93 | 235.54 |

**`div_cnt → t1_half2` is FOURTH on CONTROL and FOURTH on RETENTION, and it is
48.8 / 43.4 MHz clear of the path that binds.**

⚠ The two configurations disagree by **5.92 MHz** about what the observation
class is worth (43.59 vs 49.51) on the same RTL.  Recorded, **not explained**;
it is the same placement variance §5 measures directly, and `standing_gates.md`
§A governs.  **A next-lever decision taken on one configuration is a decision
about that configuration only** — CHAIN_MAX §7.4's rule, which survives this
correction unchanged.

---

## §8 DISPOSITION

**NO RTL CHANGE, AND NO SILICON BAR IS OWED, BECAUSE NOTHING WAS LANDED.**

The brief's registered floor — *"RETENTION worst-of-2 ≥ 46.0 as this wave's
floor; the wall at ~44 must actually break; below it, revert"* — is **moot, not
missed**: there is no wall at 44 to break.  Reporting it as MISSED would be
false, and reporting it as MET would be worse.

Three candidate designs were carried into the sitting and **all three are
withdrawn unbuilt**, for the same reason and not for three reasons:

* **(a) retime the LAUNCH rig-side.**  A `nec_bus` enable registered on the
  *negedge* (`tick_fall_neg <= (div_cnt == half-2)`) would fire `t1_half2` on
  exactly the same edge with a **full** period of launch-to-latch distance, at
  **zero** core change and **zero** pin change.  It is the simplest of the
  three and it would have been the choice.  **Withdrawn: it buys a path that
  is already 48.8 MHz clear of binding.**
* **(b) retime `t1_half2` to a posedge flop.**  Provably instrument-identical
  on this rig (§2.3 of the anatomy shows the turnaround would still land
  strictly inside C-PIN-1's window), but it moves the pins by half a fabric
  clock and therefore owes a silicon bar.  **Withdrawn: it would spend a board
  sitting on a non-problem.**
* **(c) shorten the cone.**  There is no cone to shorten: six bits of
  comparator and a haul.  **Withdrawn.**

**All three are withdrawn for ONE reason and it is not three reasons: the arc
is at 90.91 / 83.43 MHz and the design binds at 42.09 / 39.99.**

**The standing design principle decides this and is quoted because it is the
actual reason**: *nothing on the die is wasted.*  A negedge flop with three
pin-drive consumers and no next-state fanout is the smallest thing that can
place a mid-cycle bus turnaround, and it is not costing the design anything.
The confusing behaviour was in a spreadsheet, not in the silicon.

### 8.1 THE SILICON BAR THIS WAVE OWES: **NONE — AND WHY THAT IS A CONCLUSION, NOT AN OMISSION**

The brief required a landing to register the directed board legs it owes, to be
run at the next flash, with the landing PROVISIONAL until that sitting.

**Nothing was landed, so nothing is provisional and no board sitting is owed by
this wave.**  `hdl/` is byte-identical to `41a60bd42c`; the only code change is
`sw/check_ab_sim.py` (§6.1), which is a test harness and touches no bitstream.

**The bar is nevertheless written down here, so that a future sitting that
re-opens candidate (b) does not have to re-derive it** — and so that the cost
of re-opening is visible:

> Any redesign that moves the AD address→data turnaround **in time** (candidate
> (b), and any posedge form) is behaviour-visible at the pads and owes, at the
> next flash: (i) first light `check_ab_hw` **MATCH 800 ×3**; (ii) directed
> pin-level cells — a named sample of `tf0f`, `ie-pinfall` and the 528-cell
> ghost-pred column — whose **chip** columns must be UNCHANGED (they are the
> socket leg and cannot move) and whose **core-vs-chip** comparison must
> reproduce the offline column cell for cell; (iii) the full fz2 corpus with
> its **named non-movers, 106 exactly**; (iv) `use_core=0` chip proof MATCH 800
> after everything, `div_guard` PINNED on every probe, `board_idle()` clean.
>
> **A rig-side-only redesign (candidate (a)) fires `t1_half2` on the identical
> edge and owes NO silicon bar** — which is the strongest argument for (a)
> should the arc ever matter.  It does not matter now.

### 8.2 WHAT THIS WAVE RECOMMENDS INSTEAD

Ranked by the corrected ladder and by nothing else:

1. **The AD publication cone** `upc_opc → ucrom → assign ad_o → nec_bus|ad_in_q`
   — the binding path, 36-40 logic levels, worth **+1.50 MHz** to the next
   rung.  Already named by `timing_recovery_results_2026-08-11.md` §7 and by
   `timing50_e1_rederivation_2026-08-12.md` §8.3's "paired RTL item".
2. **`c_int_q → v30u_eu|row_posted`** — rung 1, and **the §6.2 verdict against
   it is withdrawn by this correction, not by a new build.**
3. Behind both, the EU's own 4-period class at 59.51 MHz.

**`div_cnt → t1_half2` is struck from the ranking.**  Every document that ranks
it as a lever is corrected by §4; the erratum list is §9.

---

## §9 THE ERRATUM LIST — what may no longer be quoted

| document | clause | status |
|---|---|---|
| `timing50_e1_rederivation_2026-08-12.md` §6.3 | *"a perfect fix of the entire observation class takes RETENTION from 42.28 to 44.10 MHz and CONTROL from 41.18 to 45.17"* | **WRONG ARITHMETIC.** The surviving path is `k = 0.5`; those figures apply `k = 1`. Corrected on this wave's own draws: **42.09 → 43.59 (CTL)** and **39.99 → 49.51 (RET)**, bound by `c_int_q → row_posted`. |
| same, §6.3 item 2 / §8.3 | *"50 MHz is not reachable by any work on the observation path… the next wall after the samplers is a half-period enable arc"* | **WITHDRAWN.** The next wall is `c_int_q → row_posted` at 43.59, and behind it the EU's 4-period class at 59.51. |
| same, §6.2 | *"closing `c_int_q` completely would move Fmax by ZERO"* | **WITHDRAWN** — it was ranked against the mis-derived enable arc. |
| same, §8.3 last block, lever ordering | *"then `div_cnt → t1_half2` (register `ce_half`, or retime `t1_half2` to a posedge flop — both behaviour-visible)"* | **STRUCK from the ranking.** |
| `timing50_chainmax_results_2026-08-12.md` §7.3 | *"the wall behind it is +8.598 — 0.202 ns apart"*, *"RETENTION, that class fixed PERFECTLY → 44.15 MHz"* | **WRONG ARITHMETIC**, same cause. |
| same, §7.4 / §7.5 | *"THE NEXT LEVER ON RETENTION IS `div_cnt → t1_half2`"*, *"50 MHz remains out of reach by any constraint work"*, the +0.39/+4.21 headroom table | **WITHDRAWN.** |
| same, §7.1 | *"three agreeing CONTROL draws… so the CONTROL loss is a property of the tree, not of a draw"* | **REFUTED by a fourth draw on the identical manifest** — §5. |
| `nec_test.sdc:98` | *"It is the #2 cone in both configurations"* | **FALSE as a ceiling statement.** It is #2 by raw slack and 4th by ceiling. The exception's *disposition* — deliberately not relaxed, because relaxing it would be a false PASS — **STANDS and is untouched**; only the ranking comment is wrong. |
| `timing50_census_2026-08-12.md` §6.6 | *"It is the #2 cone in CONTROL and #2 in RETENTION, and it is Phase 2's, as RTL"* | **WITHDRAWN.** |

**What is NOT in erratum**, and is confirmed by this wave:

* `timing50_census_2026-08-12.md` §6.3's **measurement** — launch 0.000, latch
  15.625, `setup_end_multicycle 1` — is **correct and is the evidence this
  correction rests on.**  The number was measured, printed, and then not used.
* The Phase-1 carve-out of `t1_half2` from the uniform 4/3 (`-setup 2 -hold 1`
  in, `-setup 3 -hold 2` out) **stands**: it fixed a genuinely optimistic
  constraint, and both arcs are measured here at their honest distances
  (1.5 and 2.5 periods).
* The refusal to relax `div_cnt → t1_half2` **stands** and is more clearly
  right than before: it costs nothing.
* Quartus's `Fmax Summary` — and therefore **G6's E3 bar** — has been correct
  throughout.  On both configurations the corrected true ceiling equals
  Quartus's reported Fmax **to the digit** (42.09 and 39.99).  **No gate ever
  quoted a wrong number; a derived figure computed outside Quartus did.**

---

## §10 WHAT TO DO WITH `sw/sta_halfarc_probe.tcl` AND `sw/sta_truefmax_probe.tcl`

Neither is proposed as a standing gate: they need a fitted `db`, which only a
Quartus build produces, and the ladder deliberately does not wait on Quartus.

**They are proposed as the mandatory instrument for any future ceiling claim.**
The rule this wave earns, stated so it can be checked:

> **A ceiling or headroom figure derived from a `report_timing` slack MUST name
> the path's `k` (its launch-to-latch distance in periods) and use
> `T_min = T0 − slack/k`.  A figure quoted as `1/(T0 − slack)` without `k` is
> not quotable, because this design has five classes and only one of them has
> `k = 1`.**
>
> And: **`get_timing_paths -npaths N` is sorted by slack and cannot find the
> binding path.  Rank by `slack / k`, per exception class.**

`sw/sta_truefmax_probe.tcl` implements both, walks the five classes
`nec_test.sdc` defines, and prints the campaign formula beside the corrected
one so a reader can see the size of the difference on the tree in front of
them.
