# `t1_half2` — THE ANATOMY, AND THE PIN-BEHAVIOUR CONTRACT IT IMPLEMENTS

**Written BEFORE any design was chosen and BEFORE any RTL was edited**, as the
`t1_half2` half-period-arc campaign's first deliverable.  Tree `41a60bd42c`
(`master`).  **Offline.  NO board, NO flash.**

> ## ⚠ STATUS, 2026-08-13 — **THE FLOP IS NO LONGER A NEGEDGE FLOP, AND THIS
> ## DOCUMENT'S ANATOMY IS OTHERWISE UNCHANGED**
>
> `always @(negedge clk)` became `always @(posedge clk)`, one word, same
> `ce_half` enable, no new register
> (`docs/notes/ce_contract_reland_prereg_2026-08-13.md`).  Read this document
> with three substitutions and nothing else:
>
> * **The turnaround sits at `ce_half`+1.0 fabric periods, not +0.5.**  §2.4's
>   window `(ce_half+0, ce_half+div/2)` is unchanged and **+1.0 is strictly
>   inside it for every legal divisor** (the minimum is 4, so the window is at
>   least `(0, 2)`).  **C-PIN-1, C-PIN-2 and C-PIN-3 are all MET** — measured,
>   not argued: every contract-legal instrument in the tree is byte-identical
>   across the change (`tb_sys` 306 seeds / ~1.24 M rows, 2,200 + 528 directed
>   cells, `check_ab_sim`, and the whole `check_core` family).
> * **The margin on the ADDRESS side is 1.0 fabric period of SEPARATION rather
>   than 0.0**: the TB's and M72's `ce_half`-negedge address latches sample at
>   `ce_half`+0.5, which used to be the *same edge* the flop flipped on — the
>   address survived by NBA ordering in RTL and by clock-to-Q in fabric.  It
>   now survives unambiguously.  That is the one place this change is an
>   improvement rather than a neutral simplification.
> * **§1's "the one negedge process" and §3's `k = 0.5` arc are HISTORY.**  The
>   enable arc is `k = 1.0` and the `k = 0.5` class no longer exists anywhere in
>   the design; `nec_test.sdc`'s `ce_half → ce` tightened `-setup 3 -hold 2` →
>   `-setup 2 -hold 1`.
>
> ⚠ **THE SILICON BAR IS OWED AND UNPAID**: this moves a pin in time, so
> FLASH #21 clauses (v) and (vi) — write-T1 rows byte-identical on silicon, and
> the turnaround visible at the correct instant in the two-sample rows — gate
> the landing's confirmation.  Nothing here has been on a board.

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §1 THE FLOP

`hdl/rtl/ucore/v30u_biu.sv:394` and `:1087-1090` — the whole of it:

```systemverilog
reg t1_half2;

always @(negedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (r_run && (r_ts == TS_T1)) ||
                                  vector_follow_preview;
```

It is **the only negedge-clocked flop in the synthesised design** — asserted at
`v30u_biu.sv:96`, at `v30u_eu.sv:48`, and measured over all 88 declared build
inputs by `sw/sta_negedge_probe.tcl`.

### 1.1 THE D-CONE — three register-only terms, no combinational depth

| term | kind | source |
|---|---|---|
| `r_run` | register | BIU state |
| `r_ts == TS_T1` | register compare | BIU T-state |
| `vector_follow_preview` | `eu_vector_post && r_rd_was_split` (`:650`) | one EU wire ANDed with one BIU register |

**The D-cone is shallow and it is not the problem.**  Measured
(`timing50_census_2026-08-12.md` §6.3, both configurations): the DATA arc
`v30u_* → t1_half2` had **+89.047 / +89.958 ns of slack against a 109.375 ns
budget**, i.e. an arrival near **20.3 ns**.  Under the Phase-1 carve-out its
budget is now the honest `-setup 2` = 46.875 ns, so it retains roughly **+26
ns** — three times the binding path's margin.

### 1.2 THE ENABLE PATH — this is the whole of the arc

```
nec_bus|div_cnt[5:0]        (posedge flop, FREE-RUNNING — no clock enable)
   -> wire tick_fall = (div_cnt == half - 6'd1)      nec_bus.sv:176
   -> tick_fall_o                                    nec_bus.sv:178
   -> system_large|bus_tick_fall
   -> v30_core .CE_HALF                              system_large.sv:501
   -> v30u_biu .ce_half                              v30_core.sv:166
   -> t1_half2's ENABLE pin                          v30u_biu.sv:1089
```

`div_cnt` reaches this flop **only** through `ce_half` at the enable pin,
**never in its data cone** (`nec_test.sdc:92-98`).  An enable must be valid at
the negedge *inside* the cycle in which it is asserted, so the arc is a **true
half period** — launch time 0.000 ns, latch time **15.625 ns**,
`setup_end_multicycle 1`, `to_clock_is_inverted 1`, MEASURED
(`timing50_census_2026-08-12.md` §6.3).

**So the critical half is the ENABLE, not the data.**  Six bits of comparator
inside `nec_bus` plus the haul across the chip into `v30u_biu`, against half a
fabric period.

### 1.3 THE CONSUMERS — exactly three, all of them PINS

`grep -n t1_half2 hdl/rtl/ucore/v30u_biu.sv` returns nine lines; four are
comments, one is the declaration, two are the flop itself, one is the
save-state readback (`:2582`).  The functional consumers are **three
expressions and they are all pin drives**:

```systemverilog
assign ad_o = (vector_follow_preview && t1_half2) ? eu_addr          // :1056
            : ...
            : (r_run && (r_ts == TS_T1))  ? (r_cur_wr && t1_half2    // :1062
                                         ? {r_cur_addr[19:16], cur_data_o}
                                         : t1_addr)
            : ...;

assign ad_oe_data = (vector_follow_preview && t1_half2) || ...;      // :1080
```

**`t1_half2` has ZERO consumers inside the core's next-state logic.**  It is a
one-bit phase marker whose entire job is to move the multiplexed bus, which is
why the brief is right that *its timing IS pin behaviour*.

---

## §2 THE PIN-BEHAVIOUR CONTRACT — WRITTEN DOWN BEFORE ANYTHING MOVES

### 2.1 What the flop does at the pins

`t1_half2` means *"we are in the second half of a T1"*.  Its three effects:

1. **A WRITE's T1 address→data turnaround.**  While `t1_half2` is 0, AD19-0 =
   `t1_addr` (the address).  When it goes 1, AD15-0 becomes `cur_data_o` (the
   write word, byte-swapped on an odd address) and AD19-16 becomes
   `r_cur_addr[19:16]`.  This is the switch the external T1-falling-edge
   address latch must not see early (`v30u_biu.sv:868-871`).
2. **The vector-follow preview** publishes `eu_addr` and asserts
   `ad_oe_data` — the split-read follow-on, `:1056`/`:1080`.
3. **Nothing else.**  `ad_oe_addr` and `ad_oe_ps` do not name it; `bs`, `rd_n`,
   `ube` and the status pins do not name it.

**So of the pin transitions that could land on the half-cycle, exactly ONE
does: the AD address→data turnaround (plus the vector-follow preview's use of
the same instant).  It is NOT ALE-equivalent (`ASTB`/`qs` is not in the cone),
it is NOT `UBE` (F53's UBE half is `ad_oe_*`/`last_ube`, not this flop), and it
is NOT `BS`.**

### 2.2 WHERE IT LANDS, in fabric clocks

Let `div_cnt == half-1` during fabric cycle *n* (so `tick_fall`/`ce_half` is
high across cycle *n*).  Then:

| event | instant |
|---|---|
| `div_cnt` takes the value `half-1` | posedge *n* |
| **`t1_half2` flips** | **negedge *n*+0.5** |
| `nec_clk_q` falls (the emulated CLK's falling edge) | posedge *n*+1 |

**The turnaround happens HALF A FABRIC CLOCK BEFORE the emulated CLK falls.**

### 2.3 THE INSTRUMENT — the two samples per clock, from the RTL

`nec_bus.sv` is the `nec_bus` sampler the brief names.  AD is read at
**exactly two instants per CPU clock**, and both are posedge-clocked:

```systemverilog
always_ff @(posedge clk) ad_in_q <= ad_sample;              // :202  free-running
always_ff @(posedge clk) if (tick_fall) ad_early <= ad_in_q; // :219  ADDRESS phase
...
cap_record <= { ... ad_in_q[19:16], ad_in_q[15:0],           // :718-719 DATA phase
                ad_early };                                  // :720    ADDRESS phase
```

`cap_record` is composed at `tick_rise`.  So a banked row's two fields are:

* **`ad_addr` (`bs_early`'s partner)** = `ad_early`, written at posedge *n*+1
  from `ad_in_q`, which holds **AD as it stood at posedge *n*** — i.e. **one
  full fabric period BEFORE the turnaround.**
* **`ad_data`** = `ad_in_q` at `tick_rise` — the end of the CPU cycle, many
  fabric clocks after the turnaround.

Every other rig consumer of AD reads the same two instants:
`mem_addr`/`mem_be` at `tick_fall` from `ad_in_q` (`:483-484`, the ADDRESS
instant), `mem_addr_match` likewise (`:577`), and `mem_wdata` at `tick_rise` in
T3 (`:467`, the DATA instant).

### 2.4 THE CONTRACT, stated as a requirement a redesign must meet

> **C-PIN-1.**  The AD address→data turnaround of a WRITE's T1 (and the
> vector-follow preview's publication) must land **strictly between** the
> ADDRESS instant — AD as sampled at the posedge that OPENS the `ce_half`
> cycle — and the DATA instant, `tick_rise` at the end of the CPU cycle.
>
> **C-PIN-2.**  It must land in the SAME CPU cycle it lands in today; no
> redesign may move it across a `tick_fall`.
>
> **C-PIN-3.**  `ad_oe_data`'s vector-follow term moves with it, so any shift
> applies to the output-enable as well as the data, and the RETENTION model's
> `AD_OE` (`system_large.sv`) sees the same shift.

Today the turnaround sits at `ce_half`+0.5 fabric periods, with **1.0 fabric
period of margin** on the ADDRESS side and `div/2 − 1` on the DATA side.

**The window C-PIN-1 allows is `(ce_half+0, ce_half+div/2)` in fabric periods
— the turnaround may sit anywhere strictly inside it without moving a single
sampled row.**  That is the freedom any redesign gets, and it is measured from
the RTL, not assumed.

---

## §3 WHAT THE CAMPAIGN CALLED "THE WALL", AND THE ARITHMETIC UNDER IT

`timing50_chainmax_results_2026-08-12.md` §7.3/§7.5 and
`timing50_e1_rederivation_2026-08-12.md` §6.3 both rank
`div_cnt → t1_half2` as the ceiling behind the observation class, at
**44.10/44.15 MHz (RETENTION)** and **45.17/44.00 MHz (CONTROL)**.

Both figures are computed as **`Fmax = 1 / (T0 − slack)`**.

**That formula is only correct for a path whose launch-to-latch distance is
exactly one period**, and §1.2 records that this path's distance is
**15.625 ns = 0.5 × 31.250** — MEASURED, by
`sw/sta_negedge_probe.tcl`, and printed in
`timing50_census_2026-08-12.md` §6.3.

A setup path's slack is `slack(T) = k·T + C` where `k` is the launch-to-latch
distance in periods and `C` collects the cell, net and clock-network delays,
the clock uncertainty and the setup time — **none of which scale with the
clock period.**  So the period at which a path stops making timing is

```
   T_min = T0 − slack / k        NOT       T0 − slack.
```

For `k = 1` the two agree, which is why the formula has been right everywhere
it was applied to the single-cycle observation cone.  For **`k = 0.5` it
understates the ceiling by a factor of two in slack**, and for the `CORE→CORE`
class (`-setup 4`, `k = 4`) it **overstates** it by four.

**This anatomy does not assert the correction — it registers the question, and
`sw/sta_halfarc_probe.tcl` (written before the answer was known) answers it two
ways: from the analyser's own launch/latch distances, and by re-analysing the
same fitted netlist at three clock periods and measuring `d(slack)/dT`
directly.  The prediction written into that script before it was run is that
`d(slack)/dT` equals `k` for each class: 1.000 for the observation cone, 0.500
for the ENABLE arc, 4.000 for the CE-multicycle class.**

Its result decides whether this campaign has a wall to break at all.
