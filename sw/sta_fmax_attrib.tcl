# sta_fmax_attrib.tcl -- WHICH PATH SETS Fmax?
#
# THE TRAP THIS EXISTS FOR.  `Setup Summary` reports the worst SLACK, and the
# `Fmax Summary` reports Fmax, and on this design THEY ARE NOT THE SAME PATH.
# A posedge->negedge arc latches at 0.5*T, so its slack shrinks TWICE as fast
# as a full-period path's when the clock speeds up; a `-setup 4` arc's shrinks
# four times as SLOWLY.  Comparing raw slacks across those classes is comparing
# different quantities, and the campaign's Phase-2 scope was set by such a
# comparison.
#
# For every path this prints the frequency at which ITS OWN slack reaches zero:
#
#     slack(T) = slack(T0) - M * (T0 - T)      M = latch multiple (0.5, 1, 2, 4)
#     T_crit   = T0 - slack(T0)/M              Fmax_path = 1/T_crit
#
# M is DERIVED from the path's own reported setup relationship divided by T0 --
# never assumed, never read from the SDC.
#
#     quartus_sta -t ../sw/sta_fmax_attrib.tcl nec_test nec_test_ucore <out> [npaths]

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]
set np   [lindex $quartus(args) 3]
if {$np eq ""} { set np 400 }

project_open $proj -revision $rev
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

set T0 31.250
set fh [open "$out.fmaxattrib.txt" w]
puts $fh "T0 = $T0 ns   npaths = $np"
puts $fh ""
puts $fh [format "%9s %6s %8s %8s %6s  %s" "Fmax_MHz" "M" "slack" "relship" "lvls" "from -> to"]

set rows {}
foreach_in_collection p [get_timing_paths -setup -npaths $np -detail summary] {
    set s [get_path_info $p -slack]
    set rel [get_path_info $p -launch_time]
    set lat [get_path_info $p -latch_time]
    set m [expr {($lat - $rel) / $T0}]
    if {$m <= 0} { continue }
    set tc [expr {$T0 - $s / $m}]
    if {$tc <= 0} { continue }
    set f [expr {1000.0 / $tc}]
    lappend rows [list $f $m $s [expr {$lat-$rel}] \
        [get_path_info $p -num_logic_levels] \
        "[get_node_info [get_path_info $p -from] -name] -> [get_node_info [get_path_info $p -to] -name]"]
}
set rows [lsort -real -index 0 $rows]
set n 0
foreach r $rows {
    incr n
    if {$n > 12} { break }
    puts $fh [format "%9.2f %6.2f %8.3f %8.3f %6s  %s" \
        [lindex $r 0] [lindex $r 1] [lindex $r 2] [lindex $r 3] [lindex $r 4] [lindex $r 5]]
}
puts $fh ""
puts $fh "scanned [llength $rows] paths; the 12 with the LOWEST own-Fmax are above."

# --- THE CEILING: the same ranking with the INT cone's launch removed ------- #
puts $fh ""
puts $fh "CEILING -- lowest own-Fmax among paths NOT launched by c_int_q:"
set n 0
foreach r $rows {
    if {[string match "*|c_int_q *" [lindex $r 5]]} { continue }
    incr n
    if {$n > 12} { break }
    puts $fh [format "%9.2f %6.2f %8.3f %8.3f %6s  %s" \
        [lindex $r 0] [lindex $r 1] [lindex $r 2] [lindex $r 3] [lindex $r 4] [lindex $r 5]]
}
close $fh
puts "wrote $out.fmaxattrib.txt"
project_close
