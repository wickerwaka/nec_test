set out [lindex $quartus(args) 0]
project_open nec_test -revision nec_test_ucore
create_timing_netlist
read_sdc
update_timing_netlist
set fh [open $out w]
proc o {s} { global fh; puts $fh $s; flush $fh }
proc dump {label paths} {
  o "==== $label : [get_collection_size $paths] paths"
  foreach_in_collection p $paths {
    o [format "  slack %8.3f  mcp_setup=%s  from %s  ->  %s" \
        [get_path_info $p -slack] \
        [get_path_info $p -num_logic_levels] \
        [get_node_info [get_path_info $p -from] -name] \
        [get_node_info [get_path_info $p -to] -name]]
  }
}
dump "WORST10" [get_timing_paths -setup -npaths 10]
dump "c_ready_q -> wb_kind" [get_timing_paths -setup -npaths 5 -from [get_registers -nowarn {*c_ready_q*}] -to [get_registers -nowarn {*wb_kind*}]]
dump "from c_ready_q" [get_timing_paths -setup -npaths 5 -from [get_registers -nowarn {*c_ready_q*}]]
dump "to core_ad_hold" [get_timing_paths -setup -npaths 5 -to [get_registers -nowarn {*core_ad_hold*}]]
dump "from core_ad_hold" [get_timing_paths -setup -npaths 5 -from [get_registers -nowarn {*core_ad_hold*}]]
set bad [get_timing_paths -setup -npaths 20000 -less_than_slack 0]
o "FAILING_PATHS [get_collection_size $bad]"
array set fromc {}; array set toc {}
foreach_in_collection p $bad {
  set f [get_node_info [get_path_info $p -from] -name]
  set t [get_node_info [get_path_info $p -to] -name]
  incr fromc($f)
  if {[string match {*v30u_eu*} $t]} { set b EU } elseif {[string match {*v30u_biu*} $t]} { set b BIU } else { set b "OTHER" }
  incr toc($b)
}
o "--- launch registers of failing paths ---"
set l {}
foreach {k v} [array get fromc] { lappend l [list $v $k] }
foreach e [lsort -integer -index 0 -decreasing $l] { o "  [lindex $e 0]  [lindex $e 1]" }
o "--- capture buckets ---"
foreach {k v} [array get toc] { o "  $v  $k" }
close $fh
