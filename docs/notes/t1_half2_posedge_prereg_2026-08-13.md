# `t1_half2` — REMOVING THE DESIGN'S LAST NEGEDGE PROCESS

**PRE-REGISTRATION.  Written and committed BEFORE any RTL, SDC or instrument
was edited.**  Tree `0f9f165382` (`master`), isolated worktree.
**Offline.  Quartus through the distribution gate.  NO board, NO flash.**

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §0 WHAT THIS WAVE IS, AND WHAT IT IS NOT

`t1_half2` is the **only negedge-clocked flop in the synthesised design**
(`v30u_biu.sv:1087`; asserted at `v30u_biu.sv:96`, `v30u_eu.sv:48`, measured
over all 88 declared build inputs by `sw/sta_negedge_probe.tcl`).  This wave
replaces it with a **posedge** flop enabled by the same `ce_half`, which moves
the WRITE-T1 AD address→data turnaround from `ce_half`+0.5 fabric periods to
`ce_half`+1.0.

**IT IS NOT A TIMING WAVE.**  `t1_half2_results_2026-08-13.md` §8 measured the
enable arc at **90.91 MHz (CTL) / 83.43 MHz (RET)**, fourth-ranked on both
configurations and 48.8 / 43.4 MHz clear of the path that binds, and withdrew
all three redesign candidates *"for ONE reason … the arc is at 90.91 / 83.43
MHz and the design binds at 42.09 / 39.99."*  **That measurement stands and is
not re-opened.**  Nothing here claims an Fmax benefit, and **no Fmax floor is
registered**: this is a **simplification** wave whose deliverable is the
deletion of a clocking special case and the five documentation/SDC/instrument
special cases that exist only to describe it.

Its predecessor document is explicit that candidate (b) — *"retime `t1_half2`
to a posedge flop"* — is **provably instrument-identical on this rig** and that
what it costs is a **silicon bar**.  §8.1 of that document wrote the bar down
in advance so a later sitting would not have to re-derive it.  **This sitting
takes candidate (b) and owes that bar**; it is restated verbatim in §8 below
and appended to the pending FLASH #21 skeleton.

---

## §1 THE EDIT — EXACT, AND IT IS ONE WORD PLUS ONE PROCESS MOVE

### 1.1 The flop

`hdl/rtl/ucore/v30u_biu.sv:1087-1090`, today:

```systemverilog
always @(negedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (r_run && (r_ts == TS_T1)) ||
                                  vector_follow_preview;
```

after:

```systemverilog
always @(posedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (r_run && (r_ts == TS_T1)) ||
                                  vector_follow_preview;
```

**`negedge` → `posedge`.  Nothing else in the process moves.**  The `ss_we` arm
travels with it, keeps `SSA_B_T1_HALF2` and keeps its meaning, so the
save-state stream stays compatible: same address, same bit, same semantics.

### 1.2 ⚠ THE BRIEF'S SUGGESTED SHAPE IS OFF BY ONE CLOCK, AND IS NOT TAKEN

The brief proposes an enable delayed one clock —
`ce_half_q <= ce_half;` free-running, then `else if (ce_half_q) t1_half2 <= …`.
**That form places the flip at `ce_half`+2.0, not +1.0**, and it costs a
register.  The brief's own target is +1.0.

**A plain posedge flop enabled by `ce_half` IS the +1.0 form and it preserves
hold**, because an enable is not a term:

| form | flips at | between flips |
|---|---|---|
| `always @(negedge clk) … else if (ce_half) t1_half2 <= cond;` | `ce_half`+0.5 | **HOLDS** |
| `always @(posedge clk) … else if (ce_half) t1_half2 <= cond;` | **`ce_half`+1.0** | **HOLDS** |
| `always @(posedge clk) t1_half2 <= ce_half && cond;` | every clock | **PULSE — WRONG** |
| `… else if (ce_half_q) …` (the brief's) | `ce_half`+2.0 | HOLDS, but late and +1 flop |

The third row is the trap the brief names and it is real: `ad_o` would revert
to `t1_addr` one fabric clock into the data phase and corrupt every write.
**The second row avoids it without a delayed enable at all**, which is why
**no new register is created and the save-state map does not move.**

### 1.3 CONSEQUENTLY: NO `ce_half_q`, NO SS DISPOSITION TO REGISTER

The brief asks for `ce_half_q`'s save-state disposition to be pre-registered.
**There is no `ce_half_q`.**  The registered expectation is therefore that
`ss_lint --core ucore` is **byte-identical**: `SS_COUNT` **232**, `SS_TAG`
unchanged, **221** architectural flops, **3** whitelist entries, **0
UNMAPPED** — measured at HEAD before the edit and re-measured after.

---

## §2 TRAP 1 — THE HOLD WINDOWS, INSTANT BY INSTANT

### 2.1 Notation

Let `ce_half` be asserted (high) throughout fabric cycle `n`, i.e. between
posedge *n* and posedge *n*+1.  Write `V_k` for the value
`(r_run && (r_ts == TS_T1)) || vector_follow_preview` settled during the
*k*-th such cycle `n_k`.  §4 of `nec_test.sdc` (contract C-a/C-b) gives
`n_{k+1} >= n_k + 2`.

| | value `V_k` is held on |
|---|---|
| **OLD (negedge)** | `[n_k + 0.5, n_{k+1} + 0.5)` |
| **NEW (posedge)** | `[n_k + 1.0, n_{k+1} + 1.0)` |

**The new waveform is the old one delayed by exactly half a fabric period.**
The two differ on, and only on, the half-open interval
`[n_k + 0.5, n_k + 1.0)` — half a fabric period per `ce_half`, once per CPU
half-cycle.

### 2.2 What that interval reaches

`t1_half2` has **exactly three consumers and all three are pin drives**
(`ad_o` `:1056` and `:1062`, `ad_oe_data` `:1080`); it has **zero consumers in
the core's next-state logic** (`t1_half2_anatomy_2026-08-13.md` §1.3,
re-verified here by `grep -n t1_half2 hdl/rtl/ucore/v30u_biu.sv`: nine hits =
four comments, one declaration, two process lines, one `ss_rdata` readback, and
the three drives).  So the whole question is **which sampled instants see AD /
`AD_OE` inside `[n_k+0.5, n_k+1.0)`.**

### 2.3 THE SAMPLED INSTANTS — EVERY ONE OF THEM, AND THE VERDICT

`nec_bus.sv` is the instrument.  AD enters it through **one free-running
posedge register**, `ad_in_q <= ad_sample` (`:202`), with a second free-running
stage `ad_in_q2 <= ad_in_q` (`:203`).  Every other consumer reads one of those
two, gated.

**(a) the free-running stage itself.**  A posedge flop at posedge *m* captures
the value settled during cycle *m*−1.  The only capture whose source cycle
intersects the differing interval is the one at **posedge `n_k`+1**.  So
`ad_in_q` differs between the two forms **during cycle `n_k`+1 and nowhere
else**; `ad_in_q2` differs **during cycle `n_k`+2 and nowhere else**.

**(b) every GATED consumer of `ad_in_q`.**  A consumer enabled during cycle *p*
captures at posedge *p*+1 the `ad_in_q` written at posedge *p*.  It differs iff
`p = n_k + 1`.  **By C-b there is no enable assertion in cycle `n_k`+1** — the
next enable after the `ce_half` in `n_k` is at `n_k`+2 at the earliest.  So
**no gated consumer of `ad_in_q` can read the differing sample.**  This covers
`ad_early` / `bs_early` / `qs_early` / `ube_n_early` (`:217-224`, gated
`tick_fall`), `mem_addr` / `mem_be` (`:481-486`, gated `tick_fall && T1`),
`mem_addr_match` (`:576-578`, gated `tick_fall`), `mem_wdata` (`:467`, gated
`tick_rise` in T3) and `cap_record` (`:718-720`, composed at `tick_rise`).

**(c) the one `ad_in_q2` consumer.**  `mem_wdata <= ad_in_q2[15:0]` (`:420`) is
**small-mode only** and is gated by the rising edge of the `WR` strobe, which
occurs at the end of T3 — never inside a T1's `ce_half`+1..+2 window.  It is
listed because C-b alone would permit an enable at `n_k`+2 (this rig's divider
puts it at `n_k`+4, but Reading B forbids quoting the divider), and it is
disposed of by the strobe's position, not by the divider.

**(d) the ADDRESS instant, in full.**  `ad_early` is written at posedge
`n_k`+1 from the `ad_in_q` written at posedge `n_k`, which holds AD as it stood
during cycle `n_k`−1 — **a full fabric period before the differing interval
opens under either form.**  Unchanged, and with **more** margin, not less.

**(e) the DATA instant.**  `cap_record`/`mem_wdata` at `tick_rise` sit `div/2`
fabric clocks later.  Unchanged.

**(f) the two negedge samplers in the TESTBENCHES.**
`tb_v30_core.sv:401` (`ad_mid <= {eff_hi, eff_lo}` at `negedge clk` when
`ce_half`) and `tb_v30_core.sv:332` / `tb_chain_lfsr.sv:267` (`lat_addr <= AD`
at `negedge clk` when `ce_half && ST_T1`) all capture at **negedge `n_k`+0.5 —
the exact instant the old flop flips.**  Under the old form these are
NBA-vs-NBA in one time slot, so they read the **pre-flip** value (the address).
Under the new form `t1_half2` has not flipped yet, so they read the **same**
address value **unambiguously**.  **Identical value, and a delta-cycle race
removed.**

> **THE INSTANT-BY-INSTANT VERDICT.  Every sampled instant in the rig and in
> both testbenches reads a byte-identical value.  The two forms differ only on
> a half-period window that no gated consumer, and no negedge sampler, can
> observe — which is exactly C-PIN-1's window theorem: the window
> `(ce_half+0, ce_half+div/2)` is free, and `+1.0` is strictly inside it.**

### 2.4 The retention model

`system_large.sv:583-597` (`X1_AD_RETENTION`).  `core_ad_hold[i]` is
free-running and captures `core_ad[i]` on every posedge while `core_ad_drv[i]`
is high, so its capture at posedge `n_k`+1 differs.  **It is unobservable**:
only the LAST capture before the driver turns off is ever read
(`core_ad_eff = core_ad_drv ? core_ad : core_ad_hold`), and during a T1 the
drive is asserted for the whole cycle and beyond, so posedge `n_k`+2 overwrites
it with the settled value.  This is `nec_test.sdc:177-189`'s own argument about
the same register, re-applied.  **`ad_oe_data`'s vector-follow term moves with
`t1_half2` (C-PIN-3) and `AD_OE` sees the identical shift**, which is why the
retention leg is scored as a first-class leg below and not assumed.

---

## §3 TRAP 2 — D-CONE STABILITY

### 3.1 The claim, in its strongest available form

The posedge form samples its D one fabric clock later than the negedge form
did.  The required proof is that **the value sampled is the same**.

> **S1.  Every source in `t1_half2`'s D-cone is a posedge-clocked register or a
> combinational function of posedge-clocked registers.**
> **S2.  Therefore the D value is constant across each fabric cycle, and its
> value at negedge `n`+0.5 equals its value immediately before posedge
> `n`+1.**

**S2 does not depend on C-a at all.**  C-a additionally guarantees that no
`ce`-gated register *changes* at posedge `n_k`+1, which is a second, independent
reason the sampled value cannot move; but S1/S2 alone already close it, and
they close it for free-running registers and pin-registered inputs too.

### 3.2 S1, term by term — from the RTL, not from a comment

The D expression is `(r_run && (r_ts == TS_T1)) || vector_follow_preview`.

| term | what it is | evidence |
|---|---|---|
| `r_run` | BIU register | written only by `always_ff @(posedge clk) if (ss_we \|\| srst \|\| ce)` at `v30u_biu.sv:2346` |
| `r_ts` | BIU register | same bank |
| `vector_follow_preview` | `eu_vector_post && r_rd_was_split` (`:650`) | `r_rd_was_split` same bank (`:2406`) |
| `eu_vector_post` | EU combinational output | `v30u_eu.sv:2139` `= eu_post && vector_first` |

`eu_vector_post`'s cone, walked:

* `vector_first` (`:1830`) = `(st == S_ROW) && upc_page/upc_opc/upc_loc` — four
  EU registers.
* `eu_post` (`:2132`) = `(vector_early || pr_active || row_post_now) &&
  !eu_slot_busy`.
  * `eu_slot_busy` = `r_slot_busy` (`v30u_biu.sv:844`) — **the REGISTERED view**,
    not `eu_slot_busy_n`.
  * `pr_active` = `(st == S_PRERD) && !row_posted` — EU registers.
  * `vector_early` / `row_post_now` reach `row_blocked` (§73's register-only
    wire), `q_ripe`, `eu_direct_fetch`, `eu_fetch_tail`, `eu_access_active`,
    `irq_sel_nmi`, `irq_fast_inta`, `opr_fresh`, `row_bus`, `row_posted`,
    `rowq`, `row_qn`.
  * The four BIU-published levels in that list are **register-only by
    inspection**: `q_ripe = (poppable != 0)` off `r_grn_ttl` / `r_grn_n` /
    `r_q_cnt` (`:781-782`); `eu_direct_fetch` off `r_run` / `r_cur_fetch` /
    `r_cdage` (`:696`); `eu_fetch_tail` off `r_absorb_ttl` / `q_ripe` / `r_dage`
    (`:697`); `eu_access_active` off `r_run` / `r_cur_fetch` / `r_cur_halt`
    (`:846`).

**THREE INDEPENDENT STRUCTURAL FACTS CLOSE IT:**

1. **`v30u_eu` has NO pin inputs at all** — its port list carries `pin_int`,
   `pin_nmi`, `pin_poll_n` and *no* `ready`, `ad_i` or bus port.  In
   `system_large` those three arrive through the **free-running posedge**
   registers `c_int_q` / `c_nmi_q` / `c_polln_q` (`:375-381`), so even a
   combinational path from them is piecewise-constant per fabric cycle (S2).
2. **`r7_lint` is the standing gate for the live-`READY` question** and it
   names the complete set of carriers crossing BIU → EU: `eu_rd_edge`
   (declared exception) plus `eu_slot_busy_n` and `q_ripe_lead_n` (declared
   unresolved).  **None of those three appears anywhere in the cone above** —
   the cone reads `eu_slot_busy`, not `eu_slot_busy_n`, and `q_ripe`, not
   `q_ripe_lead_n`, which is exactly the EU's own §"THE COMPOSITION" contract
   (`v30u_eu.sv:495-522`): *the combinational act decode reads the REGISTERED
   view; the clocked step reads the `_n` view.*
3. **After this edit there is NO negedge-clocked or latch-inferred state
   anywhere in `v30u_biu` / `v30u_eu` / `v30_core`** (`grep -n negedge` over
   `hdl/rtl/ucore/` returns the single line this wave deletes).  The only
   negedge-driven signals reachable at all are in the **testbenches**
   (`tb_v30_core.sv:332`, `:401`, `:613`, `tb_chain_lfsr.sv:267` and the
   scripted-consumer `scr_qop`), and none of them reaches the D-cone: the TB
   negedge latches drive `AD` → `ad_i`, which the BIU consumes only into
   registers, and under `scr_en` the core forces `eu_vector_post` to `1'b0`
   (`v30_core.sv:200`) leaving the cone as `r_run && (r_ts == TS_T1)`.

**NOTHING IN THE CONE IS LIVE.  The stability condition holds and the wave
proceeds.**

### 3.3 …AND IT IS GIVEN A FALSIFIER, BECAUSE A DERIVATION IS NOT A GATE

A simulation-only shadow is added beside the flop (`ifndef SYNTHESIS`, the
idiom §73 established for `row_blocked`): the old form's D is captured at the
negedge and compared, at the posedge the new form uses, against what the new
form is about to sample.

```systemverilog
`ifndef SYNTHESIS
// D-CONE STABILITY FALSIFIER ...
reg t1h2_negd, t1h2_negv;
always @(negedge clk) begin
    t1h2_negv <= ce_half;
    t1h2_negd <= (r_run && (r_ts == TS_T1)) || vector_follow_preview;
end
always @(posedge clk)
    if (!srst && t1h2_negv)
        assert (((r_run && (r_ts == TS_T1)) || vector_follow_preview)
                === t1h2_negd)
            else $error("v30u_biu: t1_half2 D-cone moved inside the half period");
`endif
```

It fires iff §3.1's S2 is false on any clock of any run, and it rides **every
leg of the ladder below**, including `chain_lfsr`'s 4 × 400,000 fabric clocks
of arbitrary bytes with LFSR `READY`, LFSR `INT/NMI` and LFSR-drawn CE gaps —
a stimulus distribution with nothing in common with the golden suite.
**Registered: it must never fire.**  It is `assert … else $error`, not a bare
`$error`, so `$assertoff` still quiesces it for the save-state scramble
(U2 pass 5's rule).

⚠ **This re-introduces a negedge process in SIMULATION ONLY.**  Both QSFs set
`VERILOG_MACRO "SYNTHESIS=1"`, so Quartus never reads a character of it, and
`sw/sta_negedge_probe.tcl` — which measures the **synthesised** netlist — is
the check that it did not.

---

## §4 THE M72 DOWNSTREAM READING, VERIFIED AND STATED

`m72_downstream_timing_2026-08-12.md` §1.1 says, of the Arcade-IremM72 adapter:

> *"`v30u_biu|t1_half2` and (M72's adapter) `v30_bus|addr_neg` / `ube_neg` are
> **negedge** flops enabled by `ce_half`."*

**The reading, stated as this wave verifies it:** those adapter flops capture
the AD address at **`ce_half`+0.5** — the same instant `t1_half2` flips today.
Under the current form the adapter's capture and the turnaround are the **same
edge**, so the address survives only by NBA ordering (in RTL) and by clock-to-Q
exceeding the adapter's hold requirement (in fabric).  **Moving the turnaround
to `ce_half`+1.0 gives every downstream `ce_half`-negedge address latch a full
extra half period of address hold, and removes the coincidence entirely.**
This tree's own two instances of the same construct — `tb_v30_core.sv:332` and
`tb_chain_lfsr.sv:267` — are §2.3(f), and they are the in-tree evidence for the
claim.

**This is a downstream benefit and it is NOT a bar of this wave** (no M72 build
is run here, and `m72_downstream_timing` carries no gate).  It is recorded
because it is the one place where the change is an improvement rather than a
neutral simplification.

⚠ **AND IT IS ALSO M72's `-setup 2 -hold 1` PROBLEM, HALF SOLVED.**  §1.1
reports the default posedge→negedge check WRONG in M72 at −2.380 ns.  With
`t1_half2` a posedge flop, M72's `ce`→`t1_half2` arc becomes an ordinary
posedge→posedge arc and M72's re-derivation applies to its OWN adapter flops
only.  **Not measured here; recorded as a prediction for a downstream sitting,
not as a claim.**

---

## §5 THE SDC — WHAT DIES WITH THE NEGEDGE, RE-DERIVED FROM C-a/C-b/C-c ALONE

`hdl/nec_test.sdc`'s three arcs are re-derived under the same convention the
file already states (an enable asserted "in cycle *n*" means a posedge flop
captures at posedge *n*+1).  `t1_half2` becomes a posedge flop enabled by
`ce_half`; everything else is a posedge flop enabled by `ce`.

| arc | today | after | change |
|---|---|---|---|
| `ce → ce` (`$v30u_ce → $v30u_ce`) | launch *n*+1, latch *n*+5 (C-c) = **4.0** → `-setup 4 -hold 3` | unchanged | — |
| `ce → ce_half` (`$v30u_ce → t1_half2`) | launch *n*+1, latch *m*+2.5 (C-b) = **1.5**, spelled `-setup 2` | launch *n*+1, latch *m*+3 = **2.0**, spelled `-setup 2` | **text only** — the same `-setup 2` now means 2.0 because the destination edge moved; STA computes it, it is not told |
| `ce_half → ce` (`t1_half2 → $v30u_ce`) | launch *m*+0.5, latch *m*+3 = **2.5**, spelled `-setup 3` | launch *m*+1, latch *m*+3 = **2.0**, spelled `-setup 2` | **`-setup 3 -hold 2` → `-setup 2 -hold 1`.  A TIGHTENING** |
| `div_cnt → t1_half2` (the ENABLE arc, deliberately unexcepted) | launch *n*, latch *n*+0.5 = **0.5** | launch *n*, latch *n*+1 = **1.0** | **the `k=0.5` CLASS CEASES TO EXIST.**  The arc's budget DOUBLES, by construction and with no exception written |

**Three special cases are deleted outright**, and they are deleted because the
thing they describe is gone, not because anyone decided they were unnecessary:

1. *"For a NEGEDGE destination the Nth latch edge is at N−0.5 periods, which is
   why 1.5 is spelled `-setup 2`; for a negedge SOURCE …"* — the whole
   half-edge accounting paragraph (`nec_test.sdc:56-58`).
2. The *"⚠ WHAT THIS FIXED"* block (`:60-67`) — the Phase-1 finding that the
   uniform 4/3 was **optimistic by two full periods** on a negedge destination.
   **Retained as HISTORY with a dated marker**, because a ratchet is only
   readable against its own history, but no longer describing this tree.
3. The *"⚠ AND ONE ARC INSIDE THE CORE IS DELIBERATELY NOT EXCEPTED EITHER"*
   block (`:91-98`).  Its **disposition survives** — the arc is still not
   excepted, and still must not be — but its content changes completely: it is
   no longer a *"TRUE half period"*, and `t1_half2_results` §9 already struck
   its *"#2 cone in both configurations"* clause as false-as-a-ceiling.  With
   `k = 1.0` the default check is now **exactly right** rather than
   **exactly-right-and-tight**.

**⚠ THE `$v30u_half` NAME-SELECTION HAZARD IS EXAMINED AND DELIBERATELY NOT
TOUCHED.**  `set v30u_half [get_registers {*|v30u_biu:*|t1_half2}]` matches by
EXACT NAME, so a fitter-created `t1_half2~DUPLICATE` falls into `$v30u_ce`
instead and would draw `-setup 4` where 2 is honest — the UNSAFE direction.
That hazard is **unchanged by this wave** (it is a property of the name, not of
the edge) and it is the same defect
`timing50_distribution_2026-08-13.md` §6 and `quartus_gate.py`'s
`core_domain_fmax()` already book against the probe.  **Widening the pattern to
`t1_half2*` would silently re-base every figure taken with the current
collections**, so it stays BOOKED, with this paragraph as its record and
`sw/sta_negedge_probe.tcl`'s collection-size line as its live falsifier.

### 5.1 What no longer needs saying anywhere

`hdl/rtl/ucore/v30u_biu.sv:96` — *"There is exactly ONE negedge process,
`t1_half2` (the T1 AD half), gated by `ce_half`"* — becomes **ZERO** in the
synthesised design.  `v30u_eu.sv:48`'s *"There is no negedge process in the EU"*
is unchanged and now describes the whole core.

**The ARCHIVED FSM core (`hdl/rtl/core/v30_biu.sv:1917`) keeps its negedge
`t1_half2` and is NOT touched** — `fsm_core_archive_2026-08-04.md` governs.
The SDC's `$v30u_*` collections are empty in the `nec_test` revision, so none
of the changes above reaches it.  Every "exactly one negedge flop" statement
is therefore re-scoped to **the `nec_test_ucore` revision**, which is what the
88-file manifest it was measured over always was.

---

## §6 THE ATTRIBUTION INSTRUMENT — THE `k` LABELS ARE PART OF THE TIMING MODEL

`sw/sta_truefmax_probe.tcl` walks five classes and each label **asserts a `k`**;
`sw/quartus_gate.py` compares the label's `k` against the measured one and
flags `off_class`.  After §5 the measured `k`s are **1.0 / 4.0 / 2.0 / 2.0 /
1.0**, so three of the five labels would be permanently wrong and
`core_domain_fmax()` would flag two rows off-class on **every** draw.  **A
permanently-firing flag is a flag nobody reads**, which is exactly the failure
mode `r7_lint` exists to prevent.

**The labels are therefore changed from `k`-values to STRUCTURAL names**, and
the `k` each one should measure moves into `quartus_gate.py`'s `nominal` table
where it can be checked rather than asserted in a string:

| was | becomes | nominal `k` |
|---|---|---|
| `DEFAULT` | `DEFAULT` | 1.0 |
| `k=4.0  $v30u_ce -> $v30u_ce` | `CE4    $v30u_ce -> $v30u_ce` | 4.0 |
| `k=1.5  $v30u_ce -> t1_half2` | `INTO   $v30u_ce -> t1_half2` | **2.0** |
| `k=2.5  t1_half2 -> $v30u_ce` | `OUTOF  t1_half2 -> $v30u_ce` | **2.0** |
| `k=0.5  (not $v30u_ce) -> t1_half2` | `ENABLE (not $v30u_ce) -> t1_half2` | **1.0** |

Two labels could not both stay `k=2.0` in any case: `parse_truefmax()` keys by
label and `core_domain_fmax()` matches by PREFIX, so a shared prefix would
silently take the first row twice.

⚠ **CONSEQUENCE, REGISTERED IN ADVANCE: EVERY NEGEDGE-ERA `truefmax` ARTIFACT
STOPS PARSING INTO THE NEW CLASS NAMES, AND THAT IS THE CORRECT BEHAVIOUR.**
`docs/notes/t1half2/{ctl,ret}_baseline.truefmax.txt` and
`sw/testdata/intcone/fixtures/ctl_seed1_offclass.truefmax.txt` are frozen
records of a tree with a negedge flop in it.  Fed to the new constants,
`truefmax_complete()` returns **False** and `core_domain_fmax()` returns **no
figure with the missing classes listed** — *absence must not read as data*,
this repo's own rule, doing exactly what it was built to do.  `test_quartus_gate.py`
is re-registered accordingly: the negedge-era artifacts are kept and asserted
to be **REFUSED BY ERA**, and the new-era checks run against a fixture produced
by this wave's own G6 draws.

**`sw/sta_negedge_probe.tcl` and `sw/sta_halfarc_probe.tcl` keep their queries
and get corrected predictions** (`0.5 → 1.0` on the enable arc, `3.5 → 2.0`
periods on the data arc).  Neither is a standing gate; both need a fitted `db`.

---

## §7 THE REGISTERED PREDICTIONS

Every figure below is the value measured **at HEAD, before the edit**, on this
worktree.  The bar is **byte-identical**, not "unmoved within tolerance".

### 7.1 P-1 — THE GOLDEN + PIN-SENSITIVE LADDER IS BYTE-IDENTICAL

| leg | registered |
|---|---|
| `check_core --core ucore --opcodes all --cases 0` | **169,000/169,000** |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | **500/500** |
| HLT sweeps ⚠ `--waits 0/1/2/3` | **97 · 93 · 45 · 44 = 279/283** |
| the four `evt` cells ⚠ `--waits 0/1/2/3` | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1` / `-w3` · `v0.1-w1 --opcodes EB` · `v0.1-w1evt-biased` | **1,200 · 1,200 · 200 · 1,200** |
| `ulockstep --golden all --cases 50` | **17,350/17,350, every form LOCKSTEP** |
| `sm3_s16_score --core ucore` | **1,320/1,371**, census `busstat_other` 24 · `ARCH` 27 |
| `check_boot --core ucore` | **MATCH over 220** and **over 400** rows |
| `check_ab_sim --core ucore` | **MATCH over 187 rows** |
| `ghost_launch_law score` | **200/200 = 100.0 %** |
| `ucrom_mif_check` | **PASS** |
| `fz2_immaterial falsify` | **G1-G8 PASS** |
| `test_artifact` | **45/45, non-vacuous** |

### 7.2 P-2 — THE THREE LEGS THAT ANSWER *"DID ANYTHING AT ALL CHANGE"*

`check_core` scores against goldens; these score against **the tree itself**,
and a pin that moved on any clock moves at least one field.  **Each is captured
BEFORE the edit on THIS worktree** — the committed tables are another era's
(`adcone_l1_results_2026-08-13.md` §1.3 books
`sw/testdata/ie-pinfall/core/table.json` as STALE on `master`) and are not used
as the reference.

| leg | registered |
|---|---|
| `chain_lfsr_gate` 4 seeds × 400,000 clocks | signatures **`2138eabbcea8796c` · `fad6633fc67db084` · `f90444c46a589273` · `5404f98f2d8bc343`**, `CHAIN_DEPTH_MAX 6`, `entry_st 25`, `coincide 0`, all eight gap counts and `ce_clocks` identical |
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | **306 seeds / ~1.24 M replayed rows byte-identical**, `tables` block identical, every `sys` and banked reference field unmoved |
| `ie_pinfall_cell core` | **2,200 directed cells identical, `sha256` included** |
| `ghost_pred_cell core` | **528 directed cells identical, `sha256` included** |

⚠ **THE `fz2_replay` ERA OVERRIDE IS STATED, NOT WORKED AROUND.**  Both legs
run `--no-fabric-era-guard`.  The guard **already refuses on the PRE-edit
tree** — HEAD differs from FLASH #20's bitstream in files committed before this
wave — so this is a BEFORE-vs-AFTER comparison **on one tree** and **no fabric
claim is made from it**.

### 7.3 P-3 — THE STRUCTURAL GATES

| gate | registered |
|---|---|
| `r7_lint` | **PASS**, 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / **0 violations** — unchanged |
| `ss_lint --core ucore` | **PASS**, `SS_COUNT` **232**, 109×2 BIU + 122×2 EU + tag, **221** flops, **3** whitelist, **0 UNMAPPED** — unchanged (§1.3) |
| the D-cone falsifier (§3.3) | **NEVER FIRES**, on every leg of §7.1 and §7.2 |
| `sta_negedge_probe` `t1_half2` **destination-clock-inverted** | **`1` → `0`**, and the DATA arc's measured distance **3.5 → 2.0** periods, the ENABLE arc's **0.5 → 1.0** |

### 7.4 P-4 — G6, THE DISTRIBUTION GATE, PAIRED

`python3 sw/quartus_gate.py --seeds 5` and `--retention --seeds 5`, quoted as
`standing_gates.md` §A requires: **two numbers, each with its binding cone and
its `k`, neither standing in for the other.**

**The registered band is the current one** (`intcone_results_2026-08-13.md` §3,
input manifest `d47c1d003d64c4c5…`, no RTL moved since L1):

| | whole-design `worst-of-5@seeds{1..5}` | spread | band |
|---|---:|---:|---|
| CONTROL | **41.71** | 2.65 | **[41.71, 44.36]** |
| RETENTION | **43.50** | 1.71 | **[43.50, 45.21]** |

| id | registered |
|---|---|
| **P-4a** | both `worst-of-5` figures land **within their band's spread**, i.e. CONTROL ≥ 39.06 and RETENTION ≥ 41.79 (band floor minus the band's own spread). **No Fmax FLOOR and no Fmax BENEFIT is claimed** — this is a simplification wave |
| **P-4b** | **the `k=0.5` CLASS IS GONE.** The `ENABLE` row measures **`k = 1.0000`** on **10 of 10** draws (allowing the measured 0.008 `derive_clock_uncertainty` deficit the halfarc probe characterised, i.e. ≥ 0.99). Its ceiling leaves the ladder entirely |
| **P-4c** | `INTO` measures **2.0** and `OUTOF` measures **2.0** on every draw where the class is populated |
| **P-4d** | **MEASURE, DO NOT ASSUME: does `t1_half2~DUPLICATE` still contaminate the `CE4` row?** It contaminated 3 of 10 draws at `intcone`. The `upper_bound: True` caveat **lifts only if `off_class` is empty on all ten draws**; otherwise it stands and is reported as standing |
| **P-4e** | every draw a G6 **PASS**; E7 `n_moved` ≤ 1 with `moved_offending` 0 (the one §70.7 `.qsf` exemption); E8 5/5 both readings; TNS **0.000 setup AND hold on every domain of all ten draws**; E10 N = 5 |
| **P-4f** | the RETENTION receipt **self-labels `RETENTION (X1_AD_RETENTION=1)`** and its `.rbf` differs from the CONTROL one (E-6 / E-9) |
| **P-4g** | ALMs move **< ±2 %** from the L1 band (CTL 10,085-10,154 · RET 10,134-10,194) |
| **P-4h** | the input manifest **differs** from `d47c1d003d64c4c5…` — the check that the edit reached the compiler |

### 7.5 THE REVERT RULE, REGISTERED BEFORE THE FIRST BUILD

**REVERT** if either of the following is true:

* **any** row of §7.1, §7.2 or §7.3 is not byte-identical / not at its
  registered value; **or**
* either configuration's `worst-of-5` collapses **more than 2.0 MHz below its
  band floor** (CONTROL < 39.71, RETENTION < 41.50).

A miss on P-4b, P-4c or P-4d is **reported as registered** and is not on its
own a revert trigger: those describe the timing MODEL, and a model that does
not move where §5's derivation says it must is a finding to be published, not a
reason to unwind a behaviour-neutral simplification.  **If P-4b misses, §5's
derivation is wrong and the SDC changes come back out with it.**

---

## §8 THE SILICON BAR — THE FLASH #21 CLAUSE

**This wave MOVES A PIN IN TIME.**  Under the correctness target of 2026-08-04
that is behaviour-visible at the pads and owes a fabric leg.  The landing is
**PROVISIONAL until the next flash sitting.**  `t1_half2_results_2026-08-13.md`
§8.1 wrote the bar in advance for exactly this case and it is adopted verbatim,
with the two clauses this brief adds:

> **APPEND TO THE PENDING FLASH #21 PRE-REGISTRATION SKELETON**
>
> **(i)** first light `check_ab_hw` **MATCH 800 ×3**.
> **(ii)** directed pin-level cells — a named sample of `tf0f`, `ie-pinfall`
> and the 528-cell ghost-pred column — whose **chip** columns must be
> UNCHANGED (they are the socket leg and cannot move) and whose
> **core-vs-chip** comparison must reproduce this wave's offline column cell
> for cell.
> **(iii)** the full fz2 corpus with its named non-movers, **106 exactly**.
> **(iv)** `use_core=0` chip proof **MATCH 800** after everything, `div_guard`
> **PINNED** on every probe, `board_idle()` clean.
> **(v) ⚠ THE WRITE-T1 ROWS MUST BE BYTE-IDENTICAL ON SILICON.**  The turnaround
> is the ONLY pin transition this wave moves, so the MEMW/IOW T1 rows of the
> fabric captures are its whole silicon surface.  Any diff there is this wave's
> and nothing else's.
> **(vi) ⚠ AND THE TURNAROUND MUST BE VISIBLE AT THE CORRECT INSTANT IN THE
> TWO-SAMPLE ROWS.**  `nec_bus` banks two AD samples per CPU clock; the
> ADDRESS sample (`ad_early`, taken at the posedge that opens the `ce_half`
> cycle) must still carry the **address** and the DATA sample (`tick_rise`)
> must still carry the **write word**, on **100 %** of write T1s in the
> captured population.  §2.3 predicts this exactly; the fabric leg is where it
> is either confirmed or refuted, because §2.3 is an argument about a rig and
> silicon is not a rig.
>
> **A rig-side-only redesign (candidate (a)) would have owed NO silicon bar.**
> It was withdrawn with (b) and this wave chose (b) over it, so the bar is
> owed by choice and is recorded as such.

---

## §9 SCOPE — WHAT THIS WAVE TOUCHES

| file | why |
|---|---|
| `hdl/rtl/ucore/v30u_biu.sv` | the flop (§1.1), the falsifier (§3.3), the header's negedge sentence (§5.1) |
| `hdl/nec_test.sdc` | §5 — one `-setup`/`-hold` pair tightened, three explanatory special cases retired |
| `sw/sta_truefmax_probe.tcl` | §6 — class labels |
| `sw/quartus_gate.py` | §6 — `TRUEFMAX_CLASSES`, `CORE_DOMAIN_CLASSES`, `nominal` |
| `sw/test_quartus_gate.py` | §6 — the era re-registration |
| `sw/sta_negedge_probe.tcl`, `sw/sta_halfarc_probe.tcl` | §6 — corrected predictions in their headers |
| `docs/notes/t1_half2_anatomy_2026-08-13.md` | C-PIN status |
| `docs/notes/standing_gates.md` | the rows that reference the `k=0.5` arc |

**NOT touched:** `hdl/rtl/core/` (archived FSM core), `hdl/rtl/system_large.sv`,
`hdl/rtl/nec_bus.sv`, `hdl/tb/*`, `hdl/rtl/ucore/v30u_eu.sv`,
`hdl/rtl/ucore/v30_core.sv`, and every save-state map file.
