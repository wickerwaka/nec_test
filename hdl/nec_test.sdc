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
# E-1 -- THE OBSERVATION PATH:  **DELETED 2026-08-12 UNDER READING B**
#        (docs/notes/timing50_e1_rederivation_2026-08-12.md)
# ---------------------------------------------------------------------------
# THE USER RULING OF 2026-08-12 HAS TWO PARTS.  Part 1 is the ce/ce_half
# portability contract quoted at the top of this file.  Part 2 answered the
# scope question `timing50_census_2026-08-12.md` sec.5.2 asked -- does the
# contract govern only the core's portable surface, or every arc the SDC
# writes? -- with **B: it is UNIVERSAL.  No constraint anywhere in this design,
# RIG-SIDE INCLUDED, may assume the enable train's shape.**
#
# E-1 WAS A `-setup 2 -hold 1` FROM $v30u_regs TO 28 OBSERVATION REGISTERS, AND
# IT IS GONE.  Its derivation was `div/2 - 1 = 3 periods available` -- a
# property of `nec_bus`'s divider, which is precisely what part 2 forbids as a
# premise.  It was fabric-confirmed at FLASH #19 (`c59c2caf30`), and under
# Reading B "currently true on this rig" is a RECORD, NOT A WARRANT.
#
# THE RE-DERIVATION FROM C-a/C-b/C-c ALONE, AND WHY IT FAILS BY EXACTLY ONE
# FABRIC CLOCK.  The samplers (`nec_bus.sv:201-209`) are FREE-RUNNING -- no
# clock enable, they re-capture every sys clock -- so `-setup 2` never claimed
# a two-period path.  It claimed that the FIRST sample after the source
# launches is never read.  Let the core launch at posedge L (its `ce` was
# asserted the cycle before):
#
#   * the sampler writes the first post-launch value at posedge L+1;
#   * `CE_HALF` IS `bus_tick_fall` (`system_large.sv:501`), so the
#     `tick_fall`-gated consumers -- `ad_early`/`bs_early`/`qs_early`/
#     `ube_n_early` (`nec_bus.sv:217-224`), `mem_addr`/`mem_be` (`:481-486`)
#     and `mem_addr_match` (`:576-578`) -- are gated by the very signal the
#     contract governs;
#   * C-b puts the earliest `ce_half` TWO clocks after that `ce`, so the
#     earliest such consumer captures at posedge L+2;
#   * a posedge flop capturing at L+2 reads its input as it stood BEFORE L+2 --
#     which is exactly the sample written at L+1.
#
# THE SAMPLE THAT IS ACTUALLY READ HAD ONE PERIOD TO SETTLE.  `-setup 2` needs
# the train to guarantee >= 3 idle clocks between a `ce` and the next
# `ce_half`; THE CONTRACT GUARANTEES 2.  (This rig's `div = 8` supplies 3,
# which is why the constraint has always measured true here and always will --
# and is exactly the reasoning Reading B disallows.)
#
# ESCAPES WORKED AND CLOSED (full text in the note): a second free-running
# stage (`ad_in_q2`) re-times METASTABILITY, not a wrong value; a carve-out for
# `ce`-gated consumers would be worth `-setup 3` under C-c, but every sampler
# has at least one `ce_half`-gated reader so no register qualifies; no consumer
# gate is registered (`tick_fall` is combinational off `div_cnt`, `:176`).
#
# ONE FRAGMENT SURVIVED THE CONTRACT AND IS DELIBERATELY NOT KEPT.
# `core_ad_hold` (retention builds only) is a last-driven-value retainer whose
# intermediate captures are UNOBSERVABLE -- only the last capture before the
# driver turns off is ever read -- and since `core_ad_oe` changes only at
# enable edges, C-b puts that survivor >= 2 periods after the data's launch.
# It fails anyway for two independent reasons: `core_ad_drv` is
# `core_ad_oe | c_addrv_q` and `c_addrv_q` is FREE-RUNNING
# (`system_large.sv:381`), so the argument holds only on bits [19:16]; and the
# register is one flop UPSTREAM of `ad_in_q` on the same combinational cone, so
# `core -> ad_in_q` binds first whatever `core_ad_hold` is given.  A four-bit
# exception in the RETENTION configuration -- the one that gets flashed -- for
# a predicted zero is the dangerous direction for no return.  BOOKED, not
# landed; it re-opens only if a build shows `core_ad_hold` binding.
#
# AMENDMENT A-1 IS PERMANENTLY WITHDRAWN, AND THIS DELETION SUPERSEDES IT IN
# BOTH DIRECTIONS.  A-1 scoped E-1's `-from` to $v30u_ce (measured -2.41 MHz,
# `timing50_phase1_results_2026-08-12.md` sec.7.2) because E-1 also handed the
# NEGEDGE `t1_half2 -> obs` arc two periods where the default is 0.5.  Deleting
# E-1 fixes that arc AND the `ce` arcs, and STA computes the negedge launch
# correctly without being told.
#
# WHAT IT COST, MEASURED AND NOT SOFTENED: see sec.5 of the note.  The
# observation crossing is the rig's honest Fmax bound and it is an RTL problem
# now, not an SDC one.
#
# ⚠ DO NOT RESTORE THIS EXCEPTION FROM `git show`.  Anything of this shape
# needs a derivation from C-a/C-b/C-c that does not name a divider, and sec.2.3
# of the note is the arithmetic it has to beat.

