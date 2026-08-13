# sta_intcone_anatomy.tcl -- WHERE DOES THE DELAY ACCUMULATE IN THE `c_int_q`
# LAUNCH CONE?  The `sta_adcone_anatomy.tcl` treatment, aimed at the OTHER
# rig<->core single-cycle crossing.
#
# WHY IT EXISTS.  `timing50_phase2_results_2026-08-12.md` measured this cone
# once, on ONE seed, on a tree that predates BOTH `CHAIN_MAX 12->7` (which took
# the EU's `row_posted_n` cascade out of the tail) and L1 (which moved the
# microcode head onto an M10K and re-placed the whole design).  Its finding --
# "the INT cone is TAIL-limited; the head is worth <= 0.04 ns" -- is a
# measurement of a tree that no longer exists.  This script re-takes it.
#
#   A. REGION HISTOGRAM -- per design region, ns and cells per path
#   B. NET CENSUS -- which named nets are on how many of the top-N paths
#   C. the worst path node by node, with its region tag
#   D. ENDPOINT HISTOGRAM -- what the pin's cone actually latches in
#   E. THE SEGMENT SPLIT -- prefix (pin -> `ann_kill`) vs tail (`ann_kill` ->
#      endpoint), the exact partition Phase 2 scored, so the two are comparable
#      number for number
#   F. own-Fmax per path (k read from the path's OWN launch/latch distance),
#      because a slack is not an Fmax -- `standing_gates.md` §A
#
#     quartus_sta -t ../sw/sta_intcone_anatomy.tcl nec_test nec_test_ucore <out> [npaths]

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]
set np   [lindex $quartus(args) 3]
if {$np eq ""} { set np 60 }

project_open $proj -revision $rev
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

# ---- region classifier ----------------------------------------------------- #
# ⚠ SAME KNOWN LIMITATION AS `sta_adcone_anatomy.tcl`, STATED NOT CORRECTED:
# Quartus names post-fit REGISTER nodes with the full `v30u_eu:u_eu|…` form but
# post-fit COMBINATIONAL nodes with the instance name alone, so EU/BIU
# combinational cells fall into SYS.  §E's split is read off the NODE LIST and
# does not use the region column.
proc region {name} {
    if {[string match "*u_ucrom*" $name]}      { return UCROM }
    if {[string match "*ucdecode*" $name]}     { return UCROM }
    if {[string match "*v30u_eu*" $name]}      { return EU }
    if {[string match "*v30u_biu*" $name]}     { return BIU }
    if {[string match "*v30_core*" $name]}     { return CORE }
    if {[string match "*nec_bus*" $name]}      { return NECBUS }
    if {[string match "*system_large*" $name]} { return SYS }
    return OTHER
}

set fh [open "$out.intanat.txt" w]
puts $fh "npaths requested = $np"

set T0 0.0
foreach_in_collection c [get_clocks] {
    if {[string match "*gpll~PLL_OUTPUT_COUNTER|divclk" [get_clock_info $c -name]] &&
        [string match "emu|pll*" [get_clock_info $c -name]]} {
        set T0 [get_clock_info $c -period]
    }
}
puts $fh [format "T0 = %.3f ns" $T0]

# The launch collection INCLUDES the `~DUPLICATE` forms.  The distribution
# gate's §6 found `sta_truefmax_probe.tcl` missing exactly that by exact name,
# and §4.3 of the L1 results records that the leak now also hits RUNG 2's
# `c_int_q` exclusion -- which is this cone.
set intq [get_registers -nowarn {*system_large*|c_int_q}]
set intq [add_to_collection $intq [get_registers -nowarn {*system_large*|c_int_q~*}]]
puts $fh "c_int_q launch collection size (incl ~DUPLICATE): [get_collection_size $intq]"

set paths [get_timing_paths -setup -npaths $np -detail full_path -from $intq]
puts $fh "paths returned: [get_collection_size $paths]"
puts $fh ""

array set rdelay {}
array set rlevels {}
array set netcount {}
array set netdelay {}
array set epc {}
set npath 0
set worstdump ""
set totdelay 0.0
set sum_prefix 0.0
set sum_tail 0.0
set sum_prefix_cells 0
set sum_tail_cells 0
set n_split 0
set worst_own ""

puts $fh [format "%4s %9s %6s %8s  %-44s %s" "#" "slack" "lvls" "ownFmax" "from" "to"]
foreach_in_collection p $paths {
    incr npath
    set s      [get_path_info $p -slack]
    set lv     [get_path_info $p -num_logic_levels]
    set launch [get_path_info $p -launch_time]
    set latch  [get_path_info $p -latch_time]
    set k      [expr {$T0 > 0 ? ($latch - $launch) / $T0 : 1.0}]
    set tmin   [expr {$k != 0 ? $T0 - $s / $k : 0}]
    set own    [expr {$tmin > 0 ? 1000.0/$tmin : 99999.0}]
    set from   [get_node_info [get_path_info $p -from] -name]
    set to     [get_node_info [get_path_info $p -to] -name]
    if {$worst_own eq ""} { set worst_own [format "%.2f MHz  k=%.3f  slack=%+.3f  %s -> %s" $own $k $s $from $to] }
    if {[info exists epc($to)]} { incr epc($to) } else { set epc($to) 1 }
    if {$npath <= 12} {
        puts $fh [format "%4d %9.3f %6s %8.2f  %-44s %s" $npath $s $lv $own $from $to]
    }

    array set pr {}
    array set pl {}
    array set seen {}
    set dump ""
    set cum 0.0
    set seg_prefix 0.0
    set seg_prefix_cells 0
    set past_kill 0
    set saw_kill 0
    if {[catch {set pts [get_path_info $p -arrival_points]} err]} {
        puts $fh "  (arrival points unavailable: $err)"
        continue
    }
    foreach_in_collection pt $pts {
        set nd [get_point_info $pt -node]
        if {$nd eq ""} { continue }
        set nm  [get_node_info $nd -name]
        set inc [get_point_info $pt -incr]
        set ty  [get_point_info $pt -type]
        if {$inc eq ""} { set inc 0.0 }
        set rg [region $nm]
        set cum [expr {$cum + $inc}]
        if {![info exists pr($rg)]} { set pr($rg) 0.0 ; set pl($rg) 0 }
        set pr($rg) [expr {$pr($rg) + $inc}]
        if {$ty eq "cell"} { incr pl($rg) }
        # E. the Phase-2 partition: everything up to and including the LAST
        # `ann_kill` node is the PREFIX; everything after it is the TAIL.
        # The boundary is decided BEFORE this node is booked, so the first
        # post-`ann_kill` node lands in the tail and not in both.
        if {[string match "*ann_kill*" $nm]} {
            set saw_kill 1
        } elseif {$saw_kill} {
            set past_kill 1
        }
        if {!$past_kill} {
            set seg_prefix $cum
            if {$ty eq "cell"} { incr seg_prefix_cells }
        }
        set base $nm
        set tilde [string first "~" $base]
        if {$tilde >= 0} { set base [string range $base 0 [expr {$tilde-1}]] }
        if {![info exists seen($base)]} {
            set seen($base) 1
            if {![info exists netcount($base)]} {
                set netcount($base) 0 ; set netdelay($base) 0.0
            }
            incr netcount($base)
        }
        set netdelay($base) [expr {$netdelay($base) + $inc}]
        if {$npath == 1} {
            append dump [format "  %8.3f %8.3f %-6s %-6s %s\n" $inc $cum $ty $rg $nm]
        }
    }
    if {$npath == 1} { set worstdump $dump }
    if {$saw_kill} {
        incr n_split
        set sum_prefix [expr {$sum_prefix + $seg_prefix}]
        set sum_tail   [expr {$sum_tail + ($cum - $seg_prefix)}]
        set sum_prefix_cells [expr {$sum_prefix_cells + $seg_prefix_cells}]
    }
    foreach rg [array names pr] {
        if {![info exists rdelay($rg)]} { set rdelay($rg) 0.0 ; set rlevels($rg) 0 }
        set rdelay($rg)  [expr {$rdelay($rg) + $pr($rg)}]
        set rlevels($rg) [expr {$rlevels($rg) + $pl($rg)}]
    }
    set totdelay [expr {$totdelay + $cum}]
    array unset pr ; array unset pl ; array unset seen
}

puts $fh ""
puts $fh "=== A. REGION HISTOGRAM, averaged over $npath paths ==="
puts $fh [format "%-8s %10s %8s %10s" "region" "ns/path" "%" "cells/path"]
set rows {}
foreach rg [array names rdelay] {
    lappend rows [list $rdelay($rg) $rg $rlevels($rg)]
}
foreach r [lsort -real -decreasing -index 0 $rows] {
    set rg [lindex $r 1]
    puts $fh [format "%-8s %10.3f %7.1f%% %10.1f" $rg \
        [expr {[lindex $r 0]/$npath}] \
        [expr {100.0*[lindex $r 0]/$totdelay}] \
        [expr {double([lindex $r 2])/$npath}]]
}
puts $fh [format "%-8s %10.3f" "TOTAL" [expr {$totdelay/$npath}]]

puts $fh ""
puts $fh "=== B. NET CENSUS -- nets on >= 25% of the $npath paths ==="
puts $fh [format "%5s %9s  %s" "paths" "ns/hit" "net"]
set nrows {}
foreach n [array names netcount] {
    if {$netcount($n) * 4 < $npath} { continue }
    lappend nrows [list $netcount($n) $netdelay($n) $n]
}
foreach r [lsort -integer -decreasing -index 0 [lsort -dictionary -index 2 $nrows]] {
    puts $fh [format "%5d %9.3f  %s" [lindex $r 0] \
        [expr {[lindex $r 1]/[lindex $r 0]}] [lindex $r 2]]
}

puts $fh ""
puts $fh "=== D. ENDPOINT HISTOGRAM over $npath paths ==="
foreach ep [lsort [array names epc]] {
    puts $fh [format "  %5d  %s" $epc($ep) $ep]
}

puts $fh ""
puts $fh "=== E. THE SEGMENT SPLIT (Phase 2's own partition) ==="
if {$n_split > 0} {
    puts $fh [format "  paths containing an `ann_kill` node : %d of %d" $n_split $npath]
    puts $fh [format "  PREFIX  c_int_q -> ann_kill (incl clock arrival) : %8.3f ns/path" \
        [expr {$sum_prefix/$n_split}]]
    puts $fh [format "  TAIL    ann_kill -> endpoint                     : %8.3f ns/path" \
        [expr {$sum_tail/$n_split}]]
    puts $fh [format "  tail as a fraction of the two                    : %7.1f%%" \
        [expr {100.0*$sum_tail/($sum_prefix+$sum_tail)}]]
} else {
    puts $fh "  NO PATH IN THIS POPULATION CONTAINS AN `ann_kill` NODE."
    puts $fh "  That is itself a finding: the pin's worst cone does not go"
    puts $fh "  through the announcement display on this draw."
}

puts $fh ""
puts $fh "=== F. THE WORST PATH'S OWN Fmax ==="
puts $fh "  $worst_own"

puts $fh ""
puts $fh "=== C. THE WORST PATH, NODE BY NODE ==="
puts $fh [format "  %8s %8s %-6s %-6s %s" "incr" "cum" "type" "region" "node"]
puts $fh $worstdump
close $fh
puts "wrote $out.intanat.txt  ($npath paths)"
project_close
