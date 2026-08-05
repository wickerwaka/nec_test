set out [lindex $quartus(args) 0]
project_open nec_test -revision nec_test_ucore
create_timing_netlist
read_sdc
update_timing_netlist
set fh [open $out w]
proc o {s} { global fh; puts $fh $s; flush $fh }
proc n {c} { return [get_collection_size $c] }

set scope [add_to_collection [get_registers -nowarn {*|v30u_eu:*|*}] [get_registers -nowarn {*|v30u_biu:*|*}]]
o "SCOPE [n $scope]"

# map: leaf register name -> {d pin, ena pin} for pins under the two core instances
array set dpin {}; array set epin {}
foreach suf {d ena} {
  foreach pref {*u_eu| *u_biu|} {
    foreach_in_collection p [get_pins -nowarn -compatibility_mode "${pref}*|$suf"] {
      set pn [get_node_info $p -name]
      set leaf [string range $pn 0 [expr {[string last "|" $pn]-1}]]
      set leaf [string range $leaf [expr {[string last "|" $leaf]+1}] end]
      if {$suf eq "d"} { set dpin($leaf) $pn } else { set epin($leaf) $pn }
    }
  }
}
o "DPIN_MAP [array size dpin]  EPIN_MAP [array size epin]"

set ce 0; set nod 0; set noce 0; set bad {}
foreach_in_collection x $scope {
  set nm [get_node_info $x -name]
  set leaf [string range $nm [expr {[string last "|" $nm]+1}] end]
  set gated 0
  if {[info exists epin($leaf)]} {
    foreach_in_collection f [get_fanins [get_pins -nowarn -compatibility_mode $epin($leaf)]] {
      if {[string match {*div_cnt*} [get_node_info $f -name]]} { set gated 1; break } }
  }
  if {!$gated && [info exists dpin($leaf)]} {
    foreach_in_collection f [get_fanins [get_pins -nowarn -compatibility_mode $dpin($leaf)]] {
      if {[get_node_info $f -name] eq $nm} { set gated 1; break } }
  }
  if {![info exists dpin($leaf)] && ![info exists epin($leaf)]} { incr nod; if {[llength $bad]<30} {lappend bad "NOPINS $nm"} ; continue }
  if {$gated} { incr ce } else { incr noce; if {[llength $bad]<30} { lappend bad "NOCE   $nm" } }
}
o "CE_GATED $ce   NOT_CE_GATED $noce   NO_PINS_FOUND $nod   (of [n $scope])"
foreach b $bad { o "  $b" }
close $fh
