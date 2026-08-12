derive_pll_clocks
derive_clock_uncertainty

# core specific constraints

# ---------------------------------------------------------------------------
# THE V30 CORE ADVANCES ON A DIVIDED CLOCK ENABLE  (ucore U4 pass 3, sec.51.7/52)
# ---------------------------------------------------------------------------
# `nec_bus` divides the sys clock down to the CPU clock: `cfg_clk_div` sys
# clocks per CPU cycle, documented "even, >= 4" and 8 at the divider of record
# (`hps_axi_slave.sv` resets it to 8 = 4 MHz, and `s13_board.div_guard()` PINS
# it on every board probe).  So a core register only ever takes a new value on
# one sys clock in `cfg_clk_div`, and a core register-to-register path has at
# least FOUR sys clock periods to settle, not one.
#
# THIS EXCEPTION IS ONLY LEGAL BECAUSE OF THE ENABLE-FORM REFACTOR, and it was
# measured false before it.  Until U4 pass 3 the two core modules put `ce`
# inside their next-state functions, so Quartus extracted no clock enable,
# every core register clocked on every sys clock, and `report_timing` on the
# worst path showed `nec_bus|div_cnt[1]` reaching a flip-flop's `datac` input
# through 61 logic levels with no `ena` node anywhere in the path.  An
# exception written then was INVALID BY ITS OWN FALSIFIER and was reverted
# (ledger sec.51.7).  Both modules are now a next-state function plus a register
# bank gated `if (ss_we || srst || ce)`, which is where `ce` and only `ce`
# reaches the registers.
#
# FALSIFIER, and it is checkable in the post-fit netlist: a `v30u_eu` or
# `v30u_biu` state register with no clock-enable input.  If one exists this
# exception is lying about that register and must come back out.
#
# `-hold 3` goes with `-setup 4`: without it the hold check would demand the
# launch value be held for three extra cycles, which is not what a clock
# enable does.  Paths that CROSS the boundary -- `nec_bus` and the save-state
# pipeline into the core, and the core out to the capture path -- are NOT
# excepted and stay single-cycle, which is correct: their launch registers are
# not CE-gated.
#
# The FSM revision (`nec_test`) has no `v30u_*` instances, so the collection is
# empty there and the guard makes this a no-op rather than a warning -- the two
# A/B bitstreams still differ by the CORE and nothing else.
set v30u_regs [add_to_collection \
                   [get_registers -nowarn {*|v30u_eu:*|*}] \
                   [get_registers -nowarn {*|v30u_biu:*|*}]]
if {[get_collection_size $v30u_regs] > 0} {
    set_multicycle_path -setup 4 -from $v30u_regs -to $v30u_regs
    set_multicycle_path -hold  3 -from $v30u_regs -to $v30u_regs
    post_message -type info \
        "nec_test.sdc: CE multicycle 4/3 applied to [get_collection_size $v30u_regs] v30u core registers"
}

# ---------------------------------------------------------------------------
# E-1 -- THE OBSERVATION PATH  (timing_recovery_census_2026-08-11.md F-2,
#        timing_recovery_prereg_2026-08-11.md sec.2)
# ---------------------------------------------------------------------------
# THE MEASUREMENT THAT MOTIVATES THIS.  With only the exception above in place,
# ALL 60 of the worst setup paths -- and all 4,000 the analyser will return --
# launch from `v30u_eu|upc_opc[*]` / `upc_page[*]` at 34-39 logic levels and
# latch on `nec_bus|ad_in_q[*]`.  The core's OWN worst path (`v30u_* ->
# v30u_*`) has +39.594 ns of slack against a 31.250 ns period.  The ucore is
# not the timing problem; this class is, and it is checked SINGLE-CYCLE
# because the exception above covers only `v30u_* -> v30u_*`.
#
# WHAT THESE REGISTERS ARE.  `nec_bus.sv:201-209` registers the bus pins with
# NO clock enable -- they sample on every sys clock.  They are the harness's
# OBSERVATION of a bus whose driver, with the core selected, only changes on
# the divided CPU tick.  Nothing in the CPU reads them; they feed the capture
# record, the address latch and the test memory.
#
# WHY 2 IS TRUE.  `div = cfg_clk_div` sys clocks per CPU cycle.  The core's CE
# is `bus_tick_rise` (system_large.sv:497), so its registers update on the sys
# edge E0 at which `div_cnt == div-1`.  `tick_fall` acts at E(div/2).  EVERY
# large-mode consumer of these registers is gated by `tick_rise` or
# `tick_fall` -- ad_early/bs_early/qs_early/ube_n_early (217-223), mem_addr and
# mem_be (482-484), mem_addr_match (577), mem_wdata (467), cap_record (700-721)
# and the sticky strobe accumulators (233-239).  The EARLIEST sample any of
# them reads is the one taken at E(div/2 - 1), which has had `div/2 - 1` sys
# periods to settle:
#
#       div = 8 (the divider of record)  ->  3 periods available
#       div = 6                          ->  2
#       div = 4                          ->  1   (no relaxation is legal)
#
# `-setup 2` claims TWO of the three the divider of record grants.  It is
# deliberately one period short, so the constraint survives div = 6 and so a
# future change to `tick_fall`'s phase has a whole sys clock of margin before
# it makes this a lie.  `-hold 1` is the canonical `setup-1` companion, the
# same pairing the 4/3 exception above uses.
#
# `core_ad_hold[*]` (present only under `X1_AD_RETENTION`) is included on a
# separate argument: it is a transparent-latch retainer that re-captures on
# every sys clock its bit is DRIVEN, and only the LAST capture before the
# driver turns off is ever read back.  `core_ad_drv` derives from the
# CE-gated `ad_oe_*`, so a driven bit is driven for essentially the whole CPU
# cycle and the surviving capture is at E(div-1).
#
# THE DECLARED OPERATING TRIPLE.  This exception is written for
#
#       cfg_use_core = 1,  cfg_small_mode = 0,  cfg_clk_div >= 6
#
# and it is NOT claimed outside it.  In small mode `mem_addr`/`mem_wdata`
# capture on the `sm_astb` LEVEL and a `sm_wr_n` EDGE rather than on a tick.
# That combination is never commanded -- `sw/v30run.py`'s `cfg()` sends
# `small = 0` on every rig run, with the comment "force large mode" -- and the
# ucore has no small-mode pin behaviour at all (there is no ASTB anywhere in
# `hdl/rtl/ucore/`), so with the core selected small mode decodes queue-status
# bits as strobes and is meaningless independently of any constraint.  `div=4`
# is likewise already a documented-broken capture configuration for an
# unrelated reason (`sw/v30run.py:44`, two retracted S10 readings).
#
# FALSIFIER, and it is checkable in the RTL rather than in fabric: a read of
# any register in `$obs_regs` that is NOT gated by `tick_rise` or `tick_fall`,
# in a path reachable with `cfg_use_core = 1` and `cfg_small_mode = 0`.  One
# such read makes this exception false and it must come back out.
#
# ⚠ AND A FABRIC FALSIFIER THIS TREE CANNOT RUN: no offline gate models a
# timing exception.  Verilator does not see it, `check_core` does not see it,
# and G6 merely believes it.  The first bitstream carrying this owes
# `check_ab_hw` first light (MATCH 800 x3) and `x1_fabric baseline`
# reproducing its offline column -- the capture path is exactly what breaks if
# this is wrong, and those are exactly the legs that read it.
set obs_regs [add_to_collection \
                  [get_registers -nowarn {*|nec_bus:*|ad_in_q[*]}] \
                  [add_to_collection \
                       [get_registers -nowarn {*|nec_bus:*|bs_q[*]}] \
                       [add_to_collection \
                            [get_registers -nowarn {*|nec_bus:*|qs_q[*]}] \
                            [add_to_collection \
                                 [get_registers -nowarn {*|nec_bus:*|rd_n_q}] \
                                 [add_to_collection \
                                      [get_registers -nowarn {*|nec_bus:*|ube_n_q}] \
                                      [add_to_collection \
                                           [get_registers -nowarn {*|nec_bus:*|buslock_n_q}] \
                                           [get_registers -nowarn {*|core_ad_hold[*]}]]]]]]]
if {[get_collection_size $v30u_regs] > 0 && [get_collection_size $obs_regs] > 0} {
    set_multicycle_path -setup 2 -from $v30u_regs -to $obs_regs
    set_multicycle_path -hold  1 -from $v30u_regs -to $obs_regs
    post_message -type info \
        "nec_test.sdc: E-1 observation multicycle 2/1 applied to\
         [get_collection_size $obs_regs] nec_bus/system_large observation registers"
}
