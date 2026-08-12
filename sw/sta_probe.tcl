# sta_probe.tcl -- the worst path in FULL DETAIL, plus the ceiling behind it.
#
# Two questions the scalar Fmax cannot answer:
#   A. WHAT IS IN the worst cone -- node by node, so a structure can be named.
#   B. WHAT IS BEHIND IT -- the worst path once the binding class is excluded,
#      i.e. the Fmax ceiling any fix to that class could possibly reach.
#
#     quartus_sta -t ../sw/sta_probe.tcl nec_test nec_test_ucore <outprefix>

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

# --- A. the worst path, full detail ---------------------------------------- #
report_timing -setup -npaths 2 -detail full_path -multi_corner \
    -file "$out.worstpath.rpt"

# --- B. the ceiling: worst path EXCLUDING the free-running observation
#        registers in nec_bus that sample the core's pins.
#        `-to_clock` cannot express this, so it is done by excluding the
#        endpoints by name and asking for the worst of what is left. ------- #
set obs [get_registers -nowarn {*nec_bus:bus|ad_in_q[*]}]
set obs [add_to_collection $obs [get_registers -nowarn {*nec_bus:bus|bs_q[*]}]]
set obs [add_to_collection $obs [get_registers -nowarn {*nec_bus:bus|qs_q[*]}]]
set obs [add_to_collection $obs [get_registers -nowarn {*nec_bus:bus|rd_n_q}]]
set obs [add_to_collection $obs [get_registers -nowarn {*nec_bus:bus|ube_n_q}]]
set obs [add_to_collection $obs [get_registers -nowarn {*nec_bus:bus|buslock_n_q}]]
set obs [add_to_collection $obs [get_registers -nowarn {*|core_ad_hold[*]}]]

puts "OBSERVATION-REGISTER COLLECTION SIZE: [get_collection_size $obs]"

# Everything that is NOT one of those, as a destination.
set fh [open "$out.ceiling.txt" w]
puts $fh "observation registers excluded: [get_collection_size $obs]"

# report_timing accepts -to with a collection; to EXCLUDE we ask for the worst
# path to every OTHER register.  Build the complement explicitly.
set allr [get_registers *]
set excl {}
foreach_in_collection r $obs { lappend excl [get_node_info $r -name] }
puts $fh "excluded endpoints:"
foreach e [lsort $excl] { puts $fh "  $e" }

# The complement is expensive to build as a collection; instead ask the tool
# for many paths and report the worst whose endpoint is not in the excluded set.
array set isexcl {}
foreach e $excl { set isexcl($e) 1 }

# The complement, built by SUBTRACTION rather than by scanning a top-N window:
# a scan cannot answer this, because all 4,000 worst paths in the design end on
# one of the 28 observation registers -- which is itself the finding.
set rest [remove_from_collection $allr $obs]
puts $fh "complement size: [get_collection_size $rest]"
set paths [get_timing_paths -setup -npaths 20 -detail summary -to $rest]
set best ""
set bestslack 1e9
set nseen 0
foreach_in_collection p $paths {
    incr nseen
    set to [get_node_info [get_path_info $p -to] -name]
    set s [get_path_info $p -slack]
    if {$s < $bestslack} {
        set bestslack $s
        set best "$s  [get_node_info [get_path_info $p -from] -name]  ->  $to"
    }
}
puts $fh ""
puts $fh "paths examined: $nseen"
puts $fh "WORST PATH NOT ENDING ON AN OBSERVATION REGISTER:"
puts $fh "  $best"
puts "paths examined: $nseen"
puts "CEILING (worst non-observation path): $best"
close $fh

project_close
