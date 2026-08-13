derive_pll_clocks
derive_clock_uncertainty

# core specific constraints

# ---------------------------------------------------------------------------
# THE V30 CORE ADVANCES ON A CLOCK ENABLE  (ucore U4 pass 3, sec.51.7/52;
#        RE-DERIVED 2026-08-12 under the CE/CE_HALF PORTABILITY CONTRACT --
#        docs/notes/timing50_census_2026-08-12.md sec.0)
# ---------------------------------------------------------------------------
# ⚠ THE PREMISES CHANGED, AND SO DID ONE OF THE NUMBERS.  This block used to be
# derived from `cfg_clk_div` -- "8 at the divider of record", so "at least FOUR
# sys clock periods".  THAT IS A PROPERTY OF `nec_bus`, WHICH IS ONE
# INTEGRATION OF THIS CORE, NOT THE CORE'S SPECIFICATION.  The ucore also runs
# in Arcade-IremM72 from a catch-up train that issues `ce` and `ce_half` on
# clocks TWO apart (`m72_downstream_timing_2026-08-12.md` sec.1), where a
# divider-derived constraint is silently false.
#
# USER RULING, 2026-08-12, verbatim:
#
#   "With respect to ce/ce_half, you are not allowed to make assumptions based
#    on how you are currently setting those clock enables. All you can assume
#    is the ce and ce_half will not be asserted at the same time and there will
#    be a one cycle gap between each assertion."
#
# SO THE ONLY PREMISES BELOW ARE:
#   C-a  `ce` and `ce_half` are never asserted on the same clock.
#   C-b  successive enable assertions are >= 2 clocks apart.
#
# AND ONE DERIVED EXTENSION, DERIVED FROM THE CORE AND NOT FROM ANY TRAIN:
#   C-c  `ce -> ce` is >= 4 clocks.  `ce_half` is the CPU clock's HALF-CYCLE
#        marker (`v30_core.sv:36`, `v30u_biu.sv:97`); the only thing it enables
#        is `t1_half2`, which gates `ad_oe_data`, so if no `ce_half` falls
#        between two `ce`s the BIU drives the wrong thing on AD for a whole bus
#        cycle.  The core therefore REQUIRES >= 1 `ce_half` between consecutive
#        `ce`s -- a correctness requirement of the core, not a preference of a
#        platform -- and with C-b that forces `ce -> ce` >= 4.
#        STRICT ALTERNATION IS *NOT* ASSUMED: extra `ce_half`s in a gap are
#        harmless, because `t1_half2`'s update is idempotent.
#        FALSIFIER: a platform issuing two `ce`s with no `ce_half` between.
#        Such a platform has already broken the core FUNCTIONALLY, so this
#        premise is no weaker than the core's own operating requirement.  If it
#        is ever wanted, EVERY exception here collapses to `-setup 2`.
#
# THE CORE HAS TWO ENABLE PHASES AND THEY NEED DIFFERENT NUMBERS.  Measured
# over all 88 declared build inputs: exactly ONE synthesised negedge-clocked
# flop exists, `v30u_biu|t1_half2` (`v30u_biu.sv:1087`), enabled by `ce_half`.
# Everything else is a posedge flop enabled by `ce`.  Convention below: an
# enable asserted "in cycle n" means a posedge flop captures at posedge n+1 and
# a negedge flop captures at negedge n+0.5.
#
#   ce -> ce            launch n+1, latch n+5 (C-c)      4.0 periods  -setup 4
#   ce -> ce_half       launch n+1, latch n+2.5 (C-b)    1.5 periods  -setup 2
#   ce_half -> ce       launch m+0.5, latch m+3 (C-b)    2.5 periods  -setup 3
#
# For a NEGEDGE destination the Nth latch edge is at N-0.5 periods, which is
# why 1.5 is spelled `-setup 2`; for a negedge SOURCE the Nth latch edge is at
# N-0.5 from the posedge grid, which is why 2.5 is spelled `-setup 3`.
#
# ⚠ WHAT THIS FIXED.  Until 2026-08-12 the `-setup 4 -hold 3` below was applied
# to ALL v30u registers UNIFORMLY, and `t1_half2` is a `v30u_biu` register, so
# it sat in both the `-from` and the `-to` collection.  MEASURED by
# `sw/sta_negedge_probe.tcl`: `setup_end_multicycle 1/4`, latch time 109.375 ns
# = 3.5 x 31.250, where the contract warrants 46.875.  THE CONSTRAINT WAS
# OPTIMISTIC BY TWO FULL PERIODS ON THAT ARC and by one on the way back out.
# No standing gate could see it -- `r7_lint` does not model exceptions,
# Verilator does not see them, and G6 believes this file.
#
# THESE EXCEPTIONS ARE ONLY LEGAL BECAUSE OF THE ENABLE-FORM REFACTOR, and it was
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
# EACH `-hold` IS ITS `-setup` MINUS ONE, the canonical companion: without it
# the hold check would demand the launch value be held for the extra cycles,
# which is not what a clock enable does.  Paths that CROSS the boundary --
# `nec_bus` and the save-state pipeline into the core, and the core out to the
# capture path -- are NOT excepted and stay single-cycle, which is correct:
# their launch registers are not CE-gated.
#
# ⚠ AND ONE ARC INSIDE THE CORE IS DELIBERATELY *NOT* EXCEPTED EITHER:
# `nec_bus|div_cnt[*] -> t1_half2`.  `div_cnt` has no clock enable and reaches
# this flop ONLY through `ce_half` at its ENABLE pin, never in its data cone.
# An enable must be valid at the negedge INSIDE the cycle in which it is
# asserted, so that arc is a TRUE half period -- exactly what the default
# posedge->negedge check already assumes, measured at `setup_end_multicycle 1`.
# A relaxation there would be a false PASS, the dangerous direction.  It is the
# #2 cone in both configurations and it is an RTL problem, not an SDC one.
#
# The FSM revision (`nec_test`) has no `v30u_*` instances, so the collections
# are empty there and the guards make this a no-op rather than a warning -- the
# two A/B bitstreams still differ by the CORE and nothing else.
set v30u_regs [add_to_collection \
                   [get_registers -nowarn {*|v30u_eu:*|*}] \
                   [get_registers -nowarn {*|v30u_biu:*|*}]]
# THE TWO ENABLE PHASES, SPLIT.  `t1_half2` is the ONLY `ce_half`-gated flop in
# the core; everything else is `ce`-gated.  Splitting the collection is what
# makes the three arcs above expressible -- a single uniform number cannot be
# honest for all three, and the one that used to be applied was not.
set v30u_half [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
set v30u_ce   [remove_from_collection $v30u_regs $v30u_half]
if {[get_collection_size $v30u_ce] > 0} {
    set_multicycle_path -setup 4 -from $v30u_ce -to $v30u_ce
    set_multicycle_path -hold  3 -from $v30u_ce -to $v30u_ce
    post_message -type info \
        "nec_test.sdc: CE multicycle 4/3 applied to [get_collection_size $v30u_ce] ce-gated v30u core registers"
}
if {[get_collection_size $v30u_ce] > 0 && [get_collection_size $v30u_half] > 0} {
    # ce -> ce_half : 1.5 periods on a negedge destination
    set_multicycle_path -setup 2 -from $v30u_ce   -to $v30u_half
    set_multicycle_path -hold  1 -from $v30u_ce   -to $v30u_half
    # ce_half -> ce : 2.5 periods from a negedge source
    set_multicycle_path -setup 3 -from $v30u_half -to $v30u_ce
    set_multicycle_path -hold  2 -from $v30u_half -to $v30u_ce
    post_message -type info \
        "nec_test.sdc: CE cross-phase multicycles 2/1 (ce->ce_half) and 3/2\
         (ce_half->ce) applied to [get_collection_size $v30u_half] ce_half-gated register(s)"
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
# ⚠ AMENDMENT A-1, 2026-08-12 -- THE `-from` IS `$v30u_ce`, NOT `$v30u_regs`.
# E-1 was written before the core's two enable phases were separated, so its
# `-from` collection included `t1_half2`, the one `ce_half`-gated flop.  Its
# derivation above is entirely about registers that launch at a `ce`: "the core
# launches its pins at E0".  A `ce_half`-launched flop reaches the observation
# registers HALF A CYCLE LATER, so the same reasoning grants it strictly less,
# not the same -- and `t1_half2` does reach them, through `ad_oe_data` -> `ad_o`
# -> the pads -> `ad_in_q`.  Scoping the `-from` to the `ce`-gated phase removes
# an arc this derivation never covered.  It is a TIGHTENING, in the safe
# direction, and it is the same defect class as the 4/3 split above.
if {[get_collection_size $v30u_ce] > 0 && [get_collection_size $obs_regs] > 0} {
    set_multicycle_path -setup 2 -from $v30u_ce -to $obs_regs
    set_multicycle_path -hold  1 -from $v30u_ce -to $obs_regs
    post_message -type info \
        "nec_test.sdc: E-1 observation multicycle 2/1 applied to\
         [get_collection_size $obs_regs] nec_bus/system_large observation registers"
}
