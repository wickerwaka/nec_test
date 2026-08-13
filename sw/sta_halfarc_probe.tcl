# sta_halfarc_probe.tcl -- DOES THE "WALL" SCALE WITH THE CLOCK PERIOD?
#
# WHY THIS EXISTS.  Every ceiling quoted in the timing50 campaign is computed
# as `Fmax = 1 / (T0 - slack)`.  That formula is only correct for a path whose
# LAUNCH-TO-LATCH DISTANCE IS EXACTLY ONE PERIOD.  This design has three
# classes and only one of them is single-cycle:
#
#   * `CORE->ANY`  (upc_opc -> nec_bus|ad_in_q)   single-cycle    k = 1.0
#   * `CORE->CORE` (the 4/3 CE multicycle)                        k = 4.0
#   * `ANY->CORE`  (div_cnt -> t1_half2, the ENABLE arc)          k = 0.5
#
# `timing50_census_2026-08-12.md` sec.6.3 MEASURED k for the last of these:
# launch 0.000 ns, latch 15.625 ns, `setup_end_multicycle 1`, on a NEGEDGE
# destination -- i.e. HALF a period, not one.
#
# A path's slack is  slack(T) = k*T + C  with C period-independent (cell and
# net delays, clock-network delays, uncertainty and setup time do not scale
# with the clock period).  So it reaches zero at
#
#       T_min = T0 - slack0 / k        and NOT at   T0 - slack0.
#
# For k = 0.5 the campaign's formula UNDERSTATES the path's ceiling by a factor
# of two in slack; for k = 4 it OVERSTATES it by four.  This probe does two
# things about that:
#
#   1. DERIVES the corrected ceiling per class from the analyser's own
#      launch/latch/slack numbers (no reasoning of this script's own).
#   2. MEASURES it, by re-defining the clock at three periods on the SAME
#      fitted netlist and re-reporting each path.  If slack(T) is linear with
#      the derived slope k, the derivation is confirmed by the tool.  If the
#      re-definition does not take, the sweep says so and only (1) stands.
#
# It creates its own timing netlist and cannot change the build it reads.
#
#     quartus_sta -t ../sw/sta_halfarc_probe.tcl nec_test nec_test_ucore <out>

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev

set fh [open "$out.halfarc.txt" w]
proc emit {fh s} { puts $fh $s ; puts $s }

# The corner the gate scores, named rather than defaulted (sta_census.tcl's rule).
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

emit $fh "=== sta_halfarc_probe: $proj / $rev ==="

# --------------------------------------------------------------------------- #
# 0.  THE CLOCK AND ITS PERIOD, from the analyser.
# --------------------------------------------------------------------------- #
emit $fh ""
emit $fh "--- CLOCKS ---"
set divclk_name ""
set divclk_targ ""
set T0 0.0
foreach_in_collection c [get_clocks] {
    set nm [get_clock_info $c -name]
    set pd [get_clock_info $c -period]
    set tg [get_clock_info $c -targets]
    set tgn ""
    foreach_in_collection t $tg { set tgn [get_node_info $t -name] ; break }
    emit $fh [format "  %-70s period %9.3f  target %s" $nm $pd $tgn]
    if {[string match "*divclk*" $nm]} {
        set divclk_name $nm ; set divclk_targ $tgn ; set T0 $pd
    }
}
emit $fh ""
emit $fh "  divclk clock : $divclk_name"
emit $fh "  divclk target: $divclk_targ"
emit $fh [format "  T0           : %.3f ns" $T0]

# --------------------------------------------------------------------------- #
# collections
# --------------------------------------------------------------------------- #
set corereg [add_to_collection [get_registers -nowarn {*|v30u_eu:*|*}] \
                 [add_to_collection [get_registers -nowarn {*|v30u_biu:*|*}] \
                      [get_registers -nowarn {*|v30u_ucrom:*|*}]]]
set t1h     [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
set divcnt  [get_registers -nowarn {*|nec_bus:*|div_cnt[*]}]

emit $fh ""
emit $fh "  core register collection : [get_collection_size $corereg]"
emit $fh "  t1_half2 collection      : [get_collection_size $t1h]"
emit $fh "  div_cnt collection       : [get_collection_size $divcnt]"

# --------------------------------------------------------------------------- #
# 1.  ONE PATH REPORT, with k and the corrected ceiling.
# --------------------------------------------------------------------------- #
# `-npaths 1` on each query: the worst path of that class is the only one that
# can bind, and its k is the k that matters for the class.
proc probe_one {fh label T0 args} {
    set ps [eval get_timing_paths -setup -npaths 1 -detail full_path $args]
    set n 0
    foreach_in_collection p $ps {
        set slack  [get_path_info $p -slack]
        set launch [get_path_info $p -launch_time]
        set latch  [get_path_info $p -latch_time]
        set mce    [get_path_info $p -setup_end_multicycle]
        set inv    [get_path_info $p -to_clock_is_inverted]
        set f [get_node_info [get_path_info $p -from] -name]
        set t [get_node_info [get_path_info $p -to] -name]
        set dist [expr {$latch - $launch}]
        set k    [expr {$T0 > 0 ? $dist / $T0 : 0.0}]
        emit $fh ""
        emit $fh "--- $label ---"
        emit $fh "  from            : $f"
        emit $fh "  to              : $t"
        emit $fh "  dest inverted   : $inv      setup_end_multicycle: $mce"
        emit $fh [format "  launch / latch  : %9.3f / %9.3f ns   DISTANCE %9.3f ns" \
                      $launch $latch $dist]
        emit $fh [format "  k (distance/T0) : %9.4f periods" $k]
        emit $fh [format "  slack           : %+9.3f ns" $slack]
        if {$k > 0} {
            set tmin_wrong [expr {$T0 - $slack}]
            set tmin_right [expr {$T0 - $slack / $k}]
            emit $fh [format "  CAMPAIGN FORMULA 1/(T0-slack)      : T_min %8.3f ns -> %7.2f MHz" \
                          $tmin_wrong [expr {$tmin_wrong > 0 ? 1000.0/$tmin_wrong : 0}]]
            emit $fh [format "  CORRECTED        1/(T0-slack/k)    : T_min %8.3f ns -> %7.2f MHz" \
                          $tmin_right [expr {$tmin_right > 0 ? 1000.0/$tmin_right : 0}]]
        }
        incr n
    }
    if {$n == 0} { emit $fh "" ; emit $fh "--- $label ---" ; emit $fh "  (no paths)" }
}

emit $fh ""
emit $fh "=========================================================================="
emit $fh " 1.  THE CLASSES, WITH THEIR LAUNCH-TO-LATCH DISTANCE"
emit $fh "=========================================================================="

probe_one $fh "WHOLE DESIGN worst setup path" $T0
probe_one $fh "CORE->CORE   (the 4/3 CE multicycle class)" $T0 -from $corereg -to $corereg
probe_one $fh "ANY->t1_half2  (all sources)" $T0 -to $t1h
probe_one $fh "ENABLE arc   div_cnt -> t1_half2" $T0 -from $divcnt -to $t1h
probe_one $fh "DATA arc     core -> t1_half2" $T0 -from $corereg -to $t1h
probe_one $fh "CORE->ANY    (core launch, any latch)" $T0 -from $corereg

# The observation-class-excluded ceiling: everything EXCEPT paths latching in
# nec_bus's samplers.  This reproduces sta_probe's ceiling leg, but reports k.
set obs [get_registers -nowarn {*|nec_bus:*|ad_in_q[*]}]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|ad_in_q2[*]}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|bs_q[*]}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|qs_q[*]}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|ube_n_q}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|rd_n_q}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|nec_bus:*|buslock_n_q}]]
emit $fh ""
emit $fh "  observation-endpoint collection : [get_collection_size $obs]"
set allreg [get_registers *]
set notobs [remove_from_collection $allreg $obs]
probe_one $fh "CEILING: worst path NOT latching in an observation register" $T0 -to $notobs

# --------------------------------------------------------------------------- #
# 2.  THE SWEEP -- the same netlist, re-analysed at three periods.
# --------------------------------------------------------------------------- #
emit $fh ""
emit $fh "=========================================================================="
emit $fh " 2.  PERIOD SWEEP -- slack(T) on the SAME fitted netlist"
emit $fh "=========================================================================="
emit $fh ""
emit $fh "  PRE-REGISTERED PREDICTION (written into this script before it was run):"
emit $fh "    d(slack)/dT must equal the k reported in section 1 for each path."
emit $fh "    A single-cycle path moves 1.000 ns of slack per 1.000 ns of period;"
emit $fh "    the ENABLE arc must move 0.500; the CE-multicycle class 4.000."
emit $fh ""

proc slack_of {args} {
    set ps [eval get_timing_paths -setup -npaths 1 -detail full_path $args]
    foreach_in_collection p $ps { return [get_path_info $p -slack] }
    return "NA"
}

set periods {31.250 28.125 25.000}
emit $fh [format "  %-46s %10s %10s %10s" "path" "T=31.250" "T=28.125" "T=25.000"]

array set res {}
set ok 1
foreach P $periods {
    if {$P != $T0} {
        if {[catch {create_clock -period $P -name $divclk_name [get_pins $divclk_targ]} err]} {
            emit $fh "  !! create_clock at $P FAILED: $err"
            set ok 0
            break
        }
        update_timing_netlist
        # confirm it took
        set got 0.0
        foreach_in_collection c [get_clocks] {
            if {[get_clock_info $c -name] == $divclk_name} { set got [get_clock_info $c -period] }
        }
        if {abs($got - $P) > 0.001} {
            emit $fh "  !! create_clock at $P did NOT take (analyser reports $got)"
            set ok 0
            break
        }
    }
    set res(whole,$P)  [slack_of]
    set res(corecore,$P) [slack_of -from $corereg -to $corereg]
    set res(enable,$P) [slack_of -from $divcnt -to $t1h]
    set res(ceiling,$P) [slack_of -to $notobs]
}

if {$ok} {
    foreach key {whole corecore enable ceiling} {
        set row [format "  %-46s" $key]
        foreach P $periods { append row [format " %10.3f" $res($key,$P)] }
        emit $fh $row
        # slope between the first and last period
        set p0 [lindex $periods 0] ; set pN [lindex $periods end]
        set slope [expr {($res($key,$p0) - $res($key,$pN)) / ($p0 - $pN)}]
        emit $fh [format "  %-46s MEASURED d(slack)/dT = %7.4f" "" $slope]
    }
} else {
    emit $fh ""
    emit $fh "  THE SWEEP DID NOT RUN.  Section 1's derivation stands on the"
    emit $fh "  analyser's own launch/latch distances and is not affected."
}

close $fh
project_close
