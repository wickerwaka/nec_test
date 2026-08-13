# sta_adcone_anatomy.tcl -- WHERE DO THE LEVELS ACCUMULATE IN THE LAUNCH CONE?
#
# The distribution gate (timing50_distribution_2026-08-13.md) established that
# the binding class is `upc_* -> observation register` on 15 of 16 draws, and
# that the PATH is a property of the draw while the CLASS is a property of the
# tree.  So an anatomy must be taken over a POPULATION of paths, not one path,
# and it must be taken on more than one seed.
#
# This script answers, per draw:
#
#   A. REGION HISTOGRAM -- of the top-N paths into the observation registers,
#      how much DELAY and how many LEVELS fall in the ucrom head, in the EU's
#      rails, in the BIU's `ad_o` mux, and in the rig's routing.
#   B. NET CENSUS -- which named nets appear on how many of the top-N paths.
#      A net on 60/60 is stable sub-structure; a net on 3/60 is that draw.
#   C. The worst path node by node with its region tag.
#
#     quartus_sta -t ../sw/sta_adcone_anatomy.tcl nec_test nec_test_ucore <out> [npaths]

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
# Ordered: first match wins.  `u_ucrom` is INSIDE v30u_eu, so it must be tested
# before the EU pattern or the head would be booked to the rails.
proc region {name} {
    if {[string match "*u_ucrom*" $name]}    { return UCROM }
    if {[string match "*ucdecode*" $name]}   { return UCROM }
    if {[string match "*v30u_eu*" $name]}    { return EU }
    if {[string match "*v30u_biu*" $name]}   { return BIU }
    if {[string match "*v30_core*" $name]}   { return CORE }
    if {[string match "*nec_bus*" $name]}    { return NECBUS }
    if {[string match "*system_large*" $name]} { return SYS }
    return OTHER
}

set fh [open "$out.adcone.txt" w]
puts $fh "npaths requested = $np"

# The observation registers, exactly as sta_probe.tcl names them, PLUS the
# `~DUPLICATE` forms -- the distribution gate's sec.6 found the fitter
# duplicating registers and an exact-name collection silently missing them.
set obs [get_registers -nowarn {*nec_bus:bus|ad_in_q[*]}]
foreach pat {
    {*nec_bus:bus|bs_q[*]} {*nec_bus:bus|qs_q[*]} {*nec_bus:bus|rd_n_q}
    {*nec_bus:bus|ube_n_q} {*nec_bus:bus|buslock_n_q} {*|core_ad_hold[*]}
    {*nec_bus:bus|ad_in_q[*]~*} {*|core_ad_hold[*]~*}
} {
    set obs [add_to_collection $obs [get_registers -nowarn $pat]]
}
puts $fh "observation collection size: [get_collection_size $obs]"

set paths [get_timing_paths -setup -npaths $np -detail full_path -to $obs]
puts $fh "paths returned: [get_collection_size $paths]"
puts $fh ""

array set rdelay {}
array set rlevels {}
array set netcount {}
array set netdelay {}
set npath 0
set worstdump ""
set totdelay 0.0

puts $fh [format "%4s %9s %6s  %-52s %s" "#" "slack" "lvls" "from" "to"]
foreach_in_collection p $paths {
    incr npath
    set s    [get_path_info $p -slack]
    set lv   [get_path_info $p -num_logic_levels]
    set from [get_node_info [get_path_info $p -from] -name]
    set to   [get_node_info [get_path_info $p -to] -name]
    if {$npath <= 12} {
        puts $fh [format "%4d %9.3f %6s  %-52s %s" $npath $s $lv $from $to]
    }

    # per-path region accumulation
    array set pr {}
    array set pl {}
    array set seen {}
    set dump ""
    set cum 0.0
    if {[catch {set pts [get_path_info $p -arrival_points]} err]} {
        puts $fh "  (arrival points unavailable: $err)"
        continue
    }
    foreach_in_collection pt $pts {
        set nd [get_point_info $pt -node]
        if {$nd eq ""} { continue }
        set nm [get_node_info $nd -name]
        set inc [get_point_info $pt -incr]
        set ty  [get_point_info $pt -type]
        if {$inc eq ""} { set inc 0.0 }
        set rg [region $nm]
        set cum [expr {$cum + $inc}]
        if {![info exists pr($rg)]} { set pr($rg) 0.0 ; set pl($rg) 0 }
        set pr($rg) [expr {$pr($rg) + $inc}]
        if {$ty eq "cell"} { incr pl($rg) }
        # net census: strip the Quartus synthetic suffix so `foo~3` and
        # `foo~DUPLICATE` fold onto `foo`.
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
            append dump [format "  %8.3f %8.3f %-6s %-6s %s\n" \
                $inc $cum $ty $rg $nm]
        }
    }
    if {$npath == 1} { set worstdump $dump }
    foreach rg [array names pr] {
        if {![info exists rdelay($rg)]} { set rdelay($rg) 0.0 ; set rlevels($rg) 0 }
        set rdelay($rg)  [expr {$rdelay($rg) + $pr($rg)}]
        set rlevels($rg) [expr {$rlevels($rg) + $pl($rg)}]
    }
    set totdelay [expr {$totdelay + $cum}]
    array unset pr ; array unset pl ; array unset seen
}

# ---- A. region histogram --------------------------------------------------- #
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

# ---- B. net census --------------------------------------------------------- #
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

# ---- C. worst path, node by node ------------------------------------------- #
puts $fh ""
puts $fh "=== C. THE WORST PATH, NODE BY NODE ==="
puts $fh [format "  %8s %8s %-6s %-6s %s" "incr" "cum" "type" "region" "node"]
puts $fh $worstdump
close $fh
puts "wrote $out.adcone.txt  ($npath paths)"
project_close
