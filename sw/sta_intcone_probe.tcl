# sta_intcone_probe.tcl -- TIMING50 PHASE 2's instrument.
#
# The census names the binding cone as `system_large|c_int_q -> v30u_eu|*`.
# This probe asks four questions the scalar Fmax and the top-N census cannot:
#
#   A. the worst path FROM c_int_q, in full detail (node by node)
#   B. the ENDPOINT histogram of the worst N paths launched by c_int_q
#   C. the CEILING: the worst path in the design once c_int_q is excluded as a
#      launch register -- i.e. what Fmax a perfect fix to this cone could reach
#   D. the same, launched from the OTHER free-running pin registers, so the
#      class is characterised rather than one member of it
#
#     quartus_sta -t ../sw/sta_intcone_probe.tcl nec_test nec_test_ucore <out>

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

set fh [open "$out.intcone.txt" w]

proc pslack {p} { return [format %.3f [get_path_info $p -slack]] }

# ---- A. the worst path from c_int_q, in full detail ----------------------- #
set intq [get_registers -nowarn {*system_large*|c_int_q}]
puts $fh "c_int_q collection size: [get_collection_size $intq]"
if {[get_collection_size $intq] > 0} {
    report_timing -setup -npaths 3 -detail full_path -multi_corner \
        -from $intq -file "$out.intcone.worstpath.rpt"
}

# ---- B. endpoint + level histogram over the worst 200 from c_int_q -------- #
array set epc {}
array set lvc {}
set n 0
set worst ""
foreach_in_collection p [get_timing_paths -setup -npaths 200 -detail summary \
                             -from $intq] {
    incr n
    set ep [get_node_info [get_path_info $p -to] -name]
    set lv [get_path_info $p -num_logic_levels]
    if {$worst eq ""} { set worst [pslack $p] }
    if {[info exists epc($ep)]} { incr epc($ep) } else { set epc($ep) 1 }
    if {[info exists lvc($lv)]} { incr lvc($lv) } else { set lvc($lv) 1 }
}
puts $fh ""
puts $fh "B. paths launched by c_int_q: $n   worst slack: $worst"
puts $fh "   endpoint histogram:"
foreach ep [lsort [array names epc]] { puts $fh [format "     %5d  %s" $epc($ep) $ep] }
puts $fh "   logic-level histogram:"
foreach lv [lsort -integer [array names lvc]] { puts $fh [format "     %5d paths at %s levels" $lvc($lv) $lv] }

# ---- C. the ceiling behind this cone -------------------------------------- #
# every free-running pin/observation launch register in the integration
set pins {}
foreach nm {c_int_q c_nmi_q c_ready_q c_reset_q c_polln_q} {
    set r [get_registers -nowarn "*system_large*|$nm"]
    if {[get_collection_size $r] > 0} { lappend pins $nm }
}
puts $fh ""
puts $fh "C. per-launch-register worst slack (the pin class):"
foreach nm $pins {
    set r [get_registers -nowarn "*system_large*|$nm"]
    set ps [get_timing_paths -setup -npaths 1 -detail summary -from $r]
    if {[get_collection_size $ps] > 0} {
        foreach_in_collection p $ps {
            puts $fh [format "     %-12s %8s ns  %3s levels  -> %s" \
                $nm [pslack $p] [get_path_info $p -num_logic_levels] \
                [get_node_info [get_path_info $p -to] -name]]
        }
    } else {
        puts $fh [format "     %-12s (no paths)" $nm]
    }
}

# the design's worst path with c_int_q removed as a launch register
set allr [get_registers *]
set rest [remove_from_collection $allr $intq]
puts $fh ""
puts $fh "D. CEILING -- worst setup path with c_int_q excluded as a LAUNCH register:"
foreach_in_collection p [get_timing_paths -setup -npaths 3 -detail summary -from $rest] {
    puts $fh [format "     %8s ns  %3s levels   %s -> %s" \
        [pslack $p] [get_path_info $p -num_logic_levels] \
        [get_node_info [get_path_info $p -from] -name] \
        [get_node_info [get_path_info $p -to] -name]]
}

# and with the WHOLE pin class excluded
set pc [get_registers -nowarn {*system_large*|c_int_q}]
foreach nm {c_nmi_q c_ready_q c_reset_q c_polln_q} {
    set pc [add_to_collection $pc [get_registers -nowarn "*system_large*|$nm"]]
}
set rest2 [remove_from_collection $allr $pc]
puts $fh ""
puts $fh "E. CEILING -- worst setup path with the WHOLE pin class excluded as launch:"
foreach_in_collection p [get_timing_paths -setup -npaths 3 -detail summary -from $rest2] {
    puts $fh [format "     %8s ns  %3s levels   %s -> %s" \
        [pslack $p] [get_path_info $p -num_logic_levels] \
        [get_node_info [get_path_info $p -from] -name] \
        [get_node_info [get_path_info $p -to] -name]]
}

close $fh
puts "wrote $out.intcone.txt"
project_close
