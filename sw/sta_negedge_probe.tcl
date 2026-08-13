# sta_negedge_probe.tcl -- IS THE ONE NEGEDGE FLOP CONSTRAINED AT THE DISTANCE
#                          THE RTL ACTUALLY GRANTS IT?
#
# WHY THIS EXISTS.  `v30u_biu|t1_half2` is the ONLY negedge-clocked flop in the
# synthesised design (`v30u_biu.sv:1087`; the RTL asserts it at `v30u_biu.sv:96`
# and `v30u_eu.sv:48`, and a grep over all 88 declared build inputs confirms
# it).  A posedge->negedge arc is checked at HALF a period by default, and
# whether that is right depends entirely on where `ce_half` sits in the CE
# train -- which is a per-platform fact, not a property of the core.
#
# `docs/notes/m72_downstream_timing_2026-08-12.md` §1.1 found the default WRONG
# in Arcade-IremM72 (its `ce`/`ce_half` are adjacent fabric clocks, so its data
# arc is 1.5 periods, not 0.5) and wrote the warning this script enforces:
# **re-derive the number, do not copy it.**  In THIS tree the two arcs differ:
#
#   DATA   arc  v30u_* -> t1_half2 : launched at E0 by CE = tick_rise, captured
#               at the negedge inside div_cnt==3, i.e. **3.5 sys periods**.
#               `nec_test.sdc`'s 4/3 CE multicycle already expresses exactly
#               that (for a negedge destination the Nth latch edge is at
#               N-0.5, so `-setup 4` IS 3.5).  Nothing to do -- and copying
#               m72's `-setup 2` would have TIGHTENED a correct arc to 1.5.
#
#   ENABLE arc  nec_bus|div_cnt -> t1_half2 : `div_cnt` has no clock enable and
#               reaches this flop ONLY through `ce_half = (div_cnt == 3)`, at
#               the ENABLE pin.  It takes the value 3 at E3 and is used at
#               E3.5, so the true distance is **0.5 periods** -- exactly the
#               default.  NO relaxation is legal here, and a relaxation would
#               be a false PASS, the dangerous direction.
#
# This script asks the TIMING NETLIST to confirm both, so the claim rests on
# the analyser's own required-time arithmetic and not on the reasoning above.
#
#     quartus_sta -t ../sw/sta_negedge_probe.tcl nec_test nec_test_ucore <outprefix>
#
# It creates its own timing netlist and cannot change the build it reads.

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
# The corner the gate scores, named rather than defaulted (sta_census.tcl's rule).
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

set fh [open "$out.negedge.txt" w]
proc emit {fh s} { puts $fh $s ; puts $s }

emit $fh "=== sta_negedge_probe: $proj / $rev ==="

set t1h [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
emit $fh "t1_half2 collection size: [get_collection_size $t1h]"

set corereg [add_to_collection [get_registers -nowarn {*|v30u_eu:*|*}] \
                 [get_registers -nowarn {*|v30u_biu:*|*}]]
set divcnt [get_registers -nowarn {*|nec_bus:*|div_cnt[*]}]
emit $fh "v30u_* collection size:   [get_collection_size $corereg]"
emit $fh "div_cnt collection size:  [get_collection_size $divcnt]"

# --------------------------------------------------------------------------- #
# The two arcs, in FULL detail, so the launch/latch edge times and the data
# required time are in the artifact and can be read against the derivation.
# --------------------------------------------------------------------------- #
report_timing -setup -npaths 3 -detail full_path -from $corereg -to $t1h \
    -file "$out.negedge_data.rpt"
report_timing -setup -npaths 3 -detail full_path -from $divcnt -to $t1h \
    -file "$out.negedge_enable.rpt"

# --------------------------------------------------------------------------- #
# The scalars, so a reader does not have to open two reports to see the point:
# the DATA arc must show a latch edge 3.5 periods after its launch edge, and
# the ENABLE arc 0.5.
# --------------------------------------------------------------------------- #
proc arc_summary {fh label from to} {
    set ps [get_timing_paths -setup -npaths 1 -detail full_path -from $from -to $to]
    set n 0
    foreach_in_collection p $ps {
        set slack  [get_path_info $p -slack]
        set launch [get_path_info $p -launch_time]
        set latch  [get_path_info $p -latch_time]
        set mcs    [get_path_info $p -setup_start_multicycle]
        set mce    [get_path_info $p -setup_end_multicycle]
        set inv    [get_path_info $p -to_clock_is_inverted]
        set f [get_node_info [get_path_info $p -from] -name]
        set t [get_node_info [get_path_info $p -to] -name]
        emit $fh ""
        emit $fh "--- $label ---"
        emit $fh "  from             : $f"
        emit $fh "  to               : $t"
        emit $fh "  dest clock inverted (negedge-triggered) : $inv"
        emit $fh "  setup multicycle start/end              : $mcs / $mce"
        emit $fh [format "  launch time      : %10.3f ns" $launch]
        emit $fh [format "  latch  time      : %10.3f ns" $latch]
        emit $fh [format "  DISTANCE         : %10.3f ns   <-- the number the derivation predicts" \
                      [expr {$latch - $launch}]]
        emit $fh [format "  slack            : %10.3f ns" $slack]
        incr n
    }
    if {$n == 0} { emit $fh "--- $label ---\n  (no paths)" }
}

arc_summary $fh "DATA arc   v30u_* -> t1_half2   (predicted 3.5 periods = 109.375 ns)" \
    $corereg $t1h
arc_summary $fh "ENABLE arc div_cnt -> t1_half2  (predicted 0.5 periods =  15.625 ns)" \
    $divcnt $t1h

close $fh
project_close
