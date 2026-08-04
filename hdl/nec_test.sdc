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
