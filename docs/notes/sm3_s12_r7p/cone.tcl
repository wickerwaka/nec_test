# SM3 sitting 12 -- R7' cone measurement.
#   quartus_sta -t cone.tcl <outfile>
# Dumps the worst paths AND the full node list of the worst c_ready_q path,
# so the cone is read structurally rather than inferred.
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
    o [format "  slack %8.3f  levels=%s  delay=%s  from %s  ->  %s" \
        [get_path_info $p -slack] \
        [get_path_info $p -num_logic_levels] \
        [get_path_info $p -data_delay] \
        [get_node_info [get_path_info $p -from] -name] \
        [get_node_info [get_path_info $p -to] -name]]
  }
}
proc nodes {label paths} {
  o "==== NODES $label"
  set n 0
  foreach_in_collection p $paths {
    incr n
    o "  -- path $n  slack [get_path_info $p -slack] levels [get_path_info $p -num_logic_levels]"
    foreach_in_collection pt [get_path_info $p -arrival_points] {
      o [format "      %-9s %8.3f  %s" \
          [get_point_info $pt -type] \
          [get_point_info $pt -total] \
          [get_point_info $pt -node]]
    }
    if {$n >= 1} { break }
  }
}
dump "WORST10" [get_timing_paths -setup -npaths 10]
set cr [get_registers -nowarn {*c_ready_q*}]
o "c_ready_q collection size [get_collection_size $cr]"
dump "from c_ready_q" [get_timing_paths -setup -npaths 10 -from $cr]
nodes "worst from c_ready_q" [get_timing_paths -setup -npaths 1 -from $cr]
dump "c_ready_q -> v30u_eu" [get_timing_paths -setup -npaths 5 -from $cr -to [get_registers -nowarn {*v30u_eu*}]]
dump "c_ready_q -> v30u_biu" [get_timing_paths -setup -npaths 5 -from $cr -to [get_registers -nowarn {*v30u_biu*}]]
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
