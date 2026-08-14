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
# THE CORE HAS TWO ENABLE PHASES AND THEY NEED DIFFERENT NUMBERS.
#
# ⚠ RE-DERIVED 2026-08-13.  THERE IS NO LONGER A NEGEDGE FLOP IN THE
# SYNTHESISED DESIGN.  `v30u_biu|t1_half2` -- the last one -- became a POSEDGE
# flop enabled by `ce_half` (`v30u_biu.sv`, one word); the enable phase is
# unchanged, only the edge.  So EVERY register in the core is now a posedge
# flop, and the split below is about WHICH ENABLE gates it and nothing else.
# `docs/notes/ce_contract_reland_prereg_2026-08-13.md` §6.
#
# Convention below: an enable asserted "in cycle n" means the flop it gates
# captures at posedge n+1.  (It used to need a second sentence for negedge
# destinations and sources; that sentence is deleted with the thing it
# described.)
#
#   ce -> ce            launch n+1, latch n+5 (C-c)      4.0 periods  -setup 4
#   ce -> ce_half       launch n+1, latch m+1, m >= n+2  2.0 periods  -setup 2
#   ce_half -> ce       launch m+1, latch p+1, p >= m+2  2.0 periods  -setup 2
#
# ⚠ THE `-setup 2` ON `ce -> ce_half` IS THE SAME NUMBER IT WAS AND MEANS
# SOMETHING DIFFERENT: it used to be 1.5 periods spelled `-setup 2` because the
# destination edge was half a period early.  STA computes the destination edge;
# it is not told.  `ce_half -> ce` DID move, 2.5 -> 2.0, i.e.
# `-setup 3 -hold 2` -> `-setup 2 -hold 1`, WHICH IS A TIGHTENING.
#
# ⚠ AND THE `div_cnt -> t1_half2` ENABLE ARC WENT FROM 0.5 PERIODS TO 1.0.
# An enable had to be valid at the NEGEDGE inside the cycle it is asserted in,
# so that arc was a TRUE half period and the `k = 0.5` class existed.  It does
# not any more: the enable must be valid at the POSEDGE ending that cycle, the
# default single-cycle check is now EXACTLY right rather than exactly-right-
# and-tight, and the arc's budget DOUBLES with no exception written.
#
# ⚠ WHAT THE 2026-08-12 SPLIT FIXED -- HISTORY, NOT A DESCRIPTION OF THIS TREE.
# Until 2026-08-12 the `-setup 4 -hold 3` below was applied to ALL v30u
# registers UNIFORMLY, and `t1_half2` is a `v30u_biu` register, so it sat in
# both the `-from` and the `-to` collection.  MEASURED by
# `sw/sta_negedge_probe.tcl` ON THE NEGEDGE TREE: `setup_end_multicycle 1/4`,
# latch time 109.375 ns = 3.5 x 31.250, where the contract warranted 46.875.
# THE CONSTRAINT WAS OPTIMISTIC BY TWO FULL PERIODS ON THAT ARC and by one on
# the way back out.  No standing gate could see it -- `r7_lint` does not model
# exceptions, Verilator does not see them, and G6 believes this file.  Kept
# because a ratchet is only readable against its own history; the tree it
# describes no longer exists.
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
# THE DISPOSITION SURVIVES 2026-08-13 AND ITS CONTENT DOES NOT: the enable must
# now be valid at the POSEDGE ENDING the cycle it is asserted in, so the arc is
# a FULL period and the plain single-cycle check is exactly right.  It is no
# longer a "TRUE half period" and there is no longer a `k = 0.5` class.  An
# exception here would still be a false PASS, the dangerous direction, so there
# still is none -- the reason is now "the default is correct" rather than "the
# default is correct and tight".
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
#
# ⚠ THIS COLLECTION SURVIVES THE NEGEDGE'S REMOVAL, AND SO DOES ITS HAZARD.
# It exists because `t1_half2` is the one flop gated by the OTHER ENABLE, NOT
# because it was negedge-clocked: `ce_half -> ce` is 2.0 periods where
# `ce -> ce` is 4.0, so leaving it inside `$v30u_ce` would hand a 2.0-period
# arc a 4.0-period exception -- the optimistic direction.
# `set v30u_half` matches by EXACT NAME, so a fitter-created `t1_half2~DUPLICATE`
# falls into `$v30u_ce` instead and would draw `-setup 4` where 2 is honest.
# That hazard is a property of the NAME, was not created by the edge and is not
# removed by removing it; widening the pattern to `t1_half2*` would silently
# re-base every figure taken with the current collections, so it stays BOOKED,
# with this paragraph as its record and `sw/sta_negedge_probe.tcl`'s
# collection-size line as its live falsifier.
# (`docs/notes/ce_contract_reland_prereg_2026-08-13.md` §6.1 registered this
# answer BEFORE the measurement, and `timing50_distribution_2026-08-13.md` §6
# and `quartus_gate.py`'s `core_domain_fmax()` already book it.)
set v30u_half [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
set v30u_ce   [remove_from_collection $v30u_regs $v30u_half]
if {[get_collection_size $v30u_ce] > 0} {
    set_multicycle_path -setup 4 -from $v30u_ce -to $v30u_ce
    set_multicycle_path -hold  3 -from $v30u_ce -to $v30u_ce
    post_message -type info \
        "nec_test.sdc: CE multicycle 4/3 applied to [get_collection_size $v30u_ce] ce-gated v30u core registers"
}
if {[get_collection_size $v30u_ce] > 0 && [get_collection_size $v30u_half] > 0} {
    # ce -> ce_half : 2.0 periods (C-b puts the ce_half >= 2 clocks after)
    set_multicycle_path -setup 2 -from $v30u_ce   -to $v30u_half
    set_multicycle_path -hold  1 -from $v30u_ce   -to $v30u_half
    # ce_half -> ce : 2.0 periods (C-b again, the other way).  This was
    # `-setup 3 -hold 2` while t1_half2 was a negedge flop; a POSEDGE source
    # launches half a period later, so it is 2.0 now -- a TIGHTENING.
    set_multicycle_path -setup 2 -from $v30u_half -to $v30u_ce
    set_multicycle_path -hold  1 -from $v30u_half -to $v30u_ce
    post_message -type info \
        "nec_test.sdc: CE cross-phase multicycles 2/1 (ce->ce_half) and 2/1\
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

