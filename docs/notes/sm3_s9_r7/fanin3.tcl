set out [lindex $quartus(args) 0]
project_open nec_test -revision nec_test_ucore
create_timing_netlist
read_sdc
update_timing_netlist
set fh [open $out w]
proc o {s} { global fh; puts $fh $s; flush $fh }
proc n {c} { return [get_collection_size $c] }

proc regpins {nm} {
  set r {}
  foreach s {d ena asdata sclr sload} {
    set p [get_pins -nowarn -compatibility_mode "$nm|$s"]
    if {[n $p] > 0} { lappend r $s }
  }
  return $r
}
foreach t {wb_kind row_posted st opc_byte} {
  set c 0
  foreach_in_collection r [get_registers -nowarn "*u_eu*|$t*"] {
    set nm [get_node_info $r -name]
    set pins [regpins $nm]
    set hit ""; set div 0; set self 0; set tot 0
    foreach s $pins {
      set fi [get_fanins [get_pins -nowarn -compatibility_mode "$nm|$s"]]
      incr tot [n $fi]
      foreach_in_collection f $fi { set fn [get_node_info $f -name]
        if {[string match {*c_ready_q*} $fn]} { append hit "READY@$s " }
        if {[string match {*div_cnt*} $fn]} { set div 1 }
        if {$fn eq $nm} { set self 1 } }
    }
    o "REG $nm pins={$pins} faninkeepers=$tot self=$self divcnt=$div : $hit"
    incr c; if {$c>=6} break
  }
}
close $fh
