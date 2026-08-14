# sta_truefmax_probe.tcl -- THE TRUE CEILING, CLASS BY CLASS.
#
# `sta_halfarc_probe.tcl` established (and MEASURED, by a three-point period
# sweep) that a path's slack is `k*T + C`, so it stops making timing at
#
#       T_min = T0 - slack / k
#
# where `k` is its launch-to-latch distance in periods.  The consequence this
# script exists for: **the design's binding path is the one with the smallest
# `slack / k`, NOT the one with the smallest `slack`.**  A `get_timing_paths
# -npaths N` scan is sorted by SLACK and therefore CANNOT find it -- a
# 4-period path with +25 ns of slack binds at 40 MHz and ranks thousands deep.
#
# So the scan is done PER EXCEPTION CLASS, because `nec_test.sdc` defines
# exactly five and each has one `k`:
#
#   k = 1.0   everything with no exception (the default single-cycle class)
#   k = 4.0   $v30u_ce   -> $v30u_ce     (-setup 4, the CE multicycle)
#   k = 1.5   $v30u_ce   -> $v30u_half   (-setup 2 onto a negedge destination)
#   k = 2.5   $v30u_half -> $v30u_ce     (-setup 3 from a negedge source)
#   k = 0.5   anything else -> $v30u_half (no exception, posedge->negedge)
#
# Each class's worst path is reported with its own corrected ceiling, and the
# minimum over the five is the design's true Fmax.  That number is then
# compared against Quartus's OWN `Fmax Summary`, which is the authority.
#
#     quartus_sta -t ../sw/sta_truefmax_probe.tcl nec_test nec_test_ucore <out>

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
set fh [open "$out.truefmax.txt" w]
proc emit {fh s} { puts $fh $s ; puts $s }

create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

emit $fh "=== sta_truefmax_probe: $proj / $rev ==="

set T0 0.0
set divclk_name ""
foreach_in_collection c [get_clocks] {
    if {[string match "*gpll~PLL_OUTPUT_COUNTER|divclk" [get_clock_info $c -name]] &&
        [string match "emu|pll*" [get_clock_info $c -name]]} {
        set T0 [get_clock_info $c -period]
        set divclk_name [get_clock_info $c -name]
    }
}
emit $fh [format "T0 = %.3f ns   (clock $divclk_name)" $T0]

# The SDC's own collections, reproduced exactly.
set v30u_regs [add_to_collection \
                   [get_registers -nowarn {*|v30u_eu:*|*}] \
                   [get_registers -nowarn {*|v30u_biu:*|*}]]
set v30u_half [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
set v30u_ce   [remove_from_collection $v30u_regs $v30u_half]
set allreg    [get_registers *]
set notce     [remove_from_collection $allreg $v30u_ce]

emit $fh "v30u_regs [get_collection_size $v30u_regs]  v30u_ce [get_collection_size $v30u_ce]  v30u_half [get_collection_size $v30u_half]"

set worst_t 0.0
set worst_l ""

proc klass {fh label T0 args} {
    upvar worst_t wt
    upvar worst_l wl
    set ps [eval get_timing_paths -setup -npaths 1 -detail full_path $args]
    set n 0
    foreach_in_collection p $ps {
        set slack  [get_path_info $p -slack]
        set launch [get_path_info $p -launch_time]
        set latch  [get_path_info $p -latch_time]
        set f [get_node_info [get_path_info $p -from] -name]
        set t [get_node_info [get_path_info $p -to] -name]
        set k [expr {($latch - $launch) / $T0}]
        set tmin [expr {$T0 - $slack / $k}]
        set fmax [expr {$tmin > 0 ? 1000.0/$tmin : 99999.0}]
        emit $fh ""
        emit $fh "--- $label ---"
        emit $fh "  from  : $f"
        emit $fh "  to    : $t"
        emit $fh [format "  k = %.4f   slack = %+8.3f   ->  T_min %7.3f ns  =  %7.2f MHz" \
                      $k $slack $tmin $fmax]
        if {$tmin > $wt} { set wt $tmin ; set wl "$label   ($f -> $t)" }
        incr n
    }
    if {$n == 0} { emit $fh "" ; emit $fh "--- $label ---" ; emit $fh "  (no paths)" }
}

emit $fh ""
emit $fh "=========================================================================="
emit $fh " THE FIVE EXCEPTION CLASSES, EACH WITH ITS OWN k"
emit $fh " (labels are STRUCTURAL since 2026-08-13; the k each one SHOULD measure"
emit $fh "  lives in quartus_gate.py's checked `nominal` table, not in a string:"
emit $fh "  DEFAULT 1.0 * CE4 4.0 * INTO 2.0 * OUTOF 2.0 * ENABLE 1.0.  A label that"
emit $fh "  ASSERTS a k it no longer measures is a flag nobody reads.)"
emit $fh "=========================================================================="

# k=1: no exception applies.  Approximated as "the whole-design worst path",
# which is legitimate because the excepted classes all have k > 1 and larger
# slack, so the global worst IS in the default class here -- and the class
# queries below prove it rather than assume it.
klass $fh "DEFAULT (whole-design worst, expect k=1)" $T0
klass $fh "CE4    \$v30u_ce -> \$v30u_ce   (the CE multicycle)" $T0 -from $v30u_ce -to $v30u_ce
klass $fh "INTO   \$v30u_ce -> t1_half2" $T0 -from $v30u_ce -to $v30u_half
klass $fh "OUTOF  t1_half2 -> \$v30u_ce" $T0 -from $v30u_half -to $v30u_ce
klass $fh "ENABLE (not \$v30u_ce) -> t1_half2   -- the ENABLE arc" $T0 -from $notce -to $v30u_half

# And the ladder BEHIND the binding cone, so the next lever is named rather
# than guessed.  Each rung excludes the previous rung's latch endpoints.
set obs [get_registers -nowarn {*|nec_bus:*|ad_in_q[*]}]
foreach nm {ad_in_q2[*] bs_q[*] qs_q[*] ube_n_q rd_n_q buslock_n_q} {
    set obs [add_to_collection $obs [get_registers -nowarn "*|nec_bus:*|$nm"]]
}
# RETENTION only: `core_ad_hold` is an observation register too -- it exists
# solely to model the pad float on the path nec_bus samples, and
# `timing50_e1_rederivation_2026-08-12.md` §6.3 counted it in the observation
# set (28 nec_bus + 20 core_ad_hold = 48).  Absent in CONTROL, where the
# collection is empty and this line is a no-op.
set obs [add_to_collection $obs [get_registers -nowarn {*|system_large:*|core_ad_hold[*]}]]
emit $fh ""
emit $fh "  observation endpoints (incl. core_ad_hold if RETENTION): [get_collection_size $obs]"
set rung1 [remove_from_collection $allreg $obs]
emit $fh ""
emit $fh "=========================================================================="
emit $fh " THE LADDER BEHIND THE BINDING CONE"
emit $fh "=========================================================================="
emit $fh ""
emit $fh " ⚠ EVERY RUNG IS RESTRICTED TO divclk -> divclk.  Quartus's own Fmax"
emit $fh "   Summary note says FMAX is computed ONLY for paths whose source and"
emit $fh "   destination are driven by the SAME clock, so a cross-domain path"
emit $fh "   (the JTAG hub, the HPS bridge) is not a divclk ceiling and must not"
emit $fh "   be quoted as one.  A first run of this script without the filter"
emit $fh "   returned the sld_jtag_hub at rung 2; that hit is EXCLUDED here for"
emit $fh "   that reason, and this note is why."
set dc [get_clocks $divclk_name]
klass $fh "RUNG 1: not latching in an observation register" $T0 \
    -from_clock $dc -to_clock $dc -to $rung1
# ⚠ The rung queries return the worst path by SLACK, which is exactly the
# ordering §2 says cannot find the binding path.  RUNG 1a drops t1_half2 as a
# destination as well, so the worst SINGLE-CYCLE survivor is named -- on
# RETENTION the raw-slack survivor was the k=0.5 ENABLE arc, which is precisely
# the substitution the campaign's ceiling made.
klass $fh "RUNG 1a: ...and not t1_half2 either (the worst k=1 survivor)" $T0 \
    -from_clock $dc -to_clock $dc -to [remove_from_collection $rung1 $v30u_half]
set cint [get_registers -nowarn {*|system_large:*|c_int_q}]
set rung2f [remove_from_collection $allreg $cint]
klass $fh "RUNG 2: ...and not launching from c_int_q" $T0 \
    -from_clock $dc -to_clock $dc -to $rung1 -from $rung2f
# rung 3: also drop everything latching inside the EU's row_posted cone's
# entry point, so the next DISTINCT cone is named rather than a sibling.
set rp [get_registers -nowarn {*|v30u_eu:*|row_posted}]
klass $fh "RUNG 3: ...and not latching in row_posted" $T0 \
    -from_clock $dc -to_clock $dc -to [remove_from_collection $rung1 $rp] -from $rung2f

emit $fh ""
emit $fh "=========================================================================="
emit $fh [format " TRUE CEILING over the five classes: T_min %.3f ns = %.2f MHz" \
              $worst_t [expr {$worst_t > 0 ? 1000.0/$worst_t : 0}]]
emit $fh "   bound by: $worst_l"
emit $fh "=========================================================================="
emit $fh ""
emit $fh " Compare against Quartus's OWN Fmax Summary in <rev>.sta.rpt, which is"
emit $fh " the authority.  Its note says it scales the rising and falling edges"
emit $fh " along with FMAX, so it handles the negedge destination itself."

close $fh
project_close
