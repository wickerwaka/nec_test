# sta_census.tcl -- THE CRITICAL-PATH CENSUS, run on an already-fitted db.
#
# WHY.  `quartus_gate.py` records Fmax, worst slack and TNS.  None of those say
# WHERE the time goes, so every band movement in this repo's history is a scalar
# with no cone attached to it.  This script attaches the cone.
#
# It answers three questions, in the order a reader needs them:
#
#   1. WHAT IS THE WORST PATH -- launch register, latch register, logic levels,
#      and the slack, for the top N paths on the `divclk` domain.
#   2. WHICH CLASS IS IT IN.  `nec_test.sdc` excepts v30u->v30u register paths
#      with a 4/3 CE multicycle; EVERY OTHER class is single-cycle.  The four
#      classes are reported separately with their own worst slack, because a
#      single-cycle boundary path at 40 MHz is a completely different finding
#      from a 4-cycle internal path at 40 MHz.
#   3. WHERE DO THE ENDPOINTS CLUSTER -- a histogram of launch and latch nodes
#      by entity, so a cone that grew is visible as a count and not as prose.
#
# Usage (from hdl/, with the fitted db present):
#     quartus_sta -t ../sw/sta_census.tcl nec_test nec_test_ucore <outprefix>
#
# It creates its own timing netlist; it does not re-fit and cannot change the
# build it is reading.

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
# THE CORNER IS NAMED, NOT DEFAULTED.  `<rev>.sta.rpt` records
# "Delay Model : Slow 1100mV 100C Model", so that is the corner the gate's Fmax
# and worst-slack figures come from and it is the corner this census must read;
# a census taken on a different corner would attribute a cone that is not the
# one the gate scored.
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

set fh [open "$out.census.txt" w]

proc emit {fh s} { puts $fh $s ; puts $s }

emit $fh "=== sta_census: $proj / $rev ==="

# --------------------------------------------------------------------------- #
# 1. the top paths, with launch/latch/levels
# --------------------------------------------------------------------------- #
# `-detail full_path` is what carries the node list the level count comes from.
set npaths 60
set paths [get_timing_paths -setup -npaths $npaths -detail full_path]

emit $fh ""
emit $fh "--- TOP $npaths SETUP PATHS ---"
emit $fh [format "%8s %5s  %-58s  %-58s" "slack" "lvls" "FROM (launch)" "TO (latch)"]

# accumulate the class + entity census while walking the same collection
array set cls_worst {}
array set cls_n {}
array set from_n {}
array set to_n {}

proc entity_of {node} {
    # The hierarchy path's LAST module-ish component before the register name.
    # Quartus node names look like  system_large:sl|v30u_eu:eu|psw[3]
    set parts [split $node "|"]
    set n [llength $parts]
    if {$n < 2} { return $node }
    set mod [lindex $parts end-1]
    set c [split $mod ":"]
    if {[llength $c] >= 1} { return [lindex $c 0] }
    return $mod
}

proc in_core {node} {
    if {[string match "*v30u_eu:*" $node]} { return 1 }
    if {[string match "*v30u_biu:*" $node]} { return 1 }
    if {[string match "*v30u_ucrom:*" $node]} { return 1 }
    return 0
}

foreach_in_collection p $paths {
    set slack [get_path_info $p -slack]
    set from  [get_node_info [get_path_info $p -from] -name]
    set to    [get_node_info [get_path_info $p -to] -name]
    # logic levels: count the CELL (combinational) nodes on the path
    set lvls 0
    foreach_in_collection pt [get_path_info $p -arrival_points] {
        set t [get_point_info $pt -type]
        if {$t == "cell"} { incr lvls }
    }
    emit $fh [format "%8.3f %5d  %-58s  %-58s" $slack $lvls \
                  [string range $from end-57 end] [string range $to end-57 end]]

    set fi [in_core $from] ; set ti [in_core $to]
    set k "[expr {$fi ? {CORE} : {OUT }}]->[expr {$ti ? {CORE} : {OUT }}]"
    if {![info exists cls_worst($k)] || $slack < $cls_worst($k)} {
        set cls_worst($k) $slack
    }
    incr cls_n($k)
    set fe [entity_of $from] ; set te [entity_of $to]
    incr from_n($fe) ; incr to_n($te)
}

# --------------------------------------------------------------------------- #
# 2. the four classes.  CORE->CORE is the only one the 4/3 multicycle covers.
# --------------------------------------------------------------------------- #
emit $fh ""
emit $fh "--- CLASS CENSUS over those $npaths paths ---"
emit $fh "  (CORE = v30u_eu / v30u_biu / v30u_ucrom.  Only CORE->CORE gets the"
emit $fh "   nec_test.sdc 4/3 CE multicycle; every other class is SINGLE-CYCLE.)"
foreach k [lsort [array names cls_worst]] {
    emit $fh [format "  %-12s n=%-4d worst slack %8.3f" $k $cls_n($k) $cls_worst($k)]
}

emit $fh ""
emit $fh "--- LAUNCH ENTITY HISTOGRAM ---"
foreach e [lsort [array names from_n]] {
    emit $fh [format "  %-40s %d" $e $from_n($e)]
}
emit $fh ""
emit $fh "--- LATCH ENTITY HISTOGRAM ---"
foreach e [lsort [array names to_n]] {
    emit $fh [format "  %-40s %d" $e $to_n($e)]
}

# --------------------------------------------------------------------------- #
# 3. worst path per class, asked of the netlist directly (not just the top N)
# --------------------------------------------------------------------------- #
emit $fh ""
emit $fh "--- WORST PATH PER CLASS, asked of the whole netlist ---"
set corereg [add_to_collection [get_registers -nowarn {*|v30u_eu:*|*}] \
                 [add_to_collection [get_registers -nowarn {*|v30u_biu:*|*}] \
                      [get_registers -nowarn {*|v30u_ucrom:*|*}]]]
set allreg  [get_registers *]

proc worst_of {fh label from to} {
    set ps [get_timing_paths -setup -npaths 3 -detail summary -from $from -to $to]
    set n 0
    foreach_in_collection p $ps {
        set slack [get_path_info $p -slack]
        set f [get_node_info [get_path_info $p -from] -name]
        set t [get_node_info [get_path_info $p -to] -name]
        emit $fh [format "  %-14s %8.3f  %s" $label $slack "$f  ->  $t"]
        incr n
        if {$n >= 1} { break }
    }
    if {$n == 0} { emit $fh [format "  %-14s (no paths)" $label] }
}

worst_of $fh "CORE->CORE" $corereg $corereg
worst_of $fh "ANY->CORE"  $allreg  $corereg
worst_of $fh "CORE->ANY"  $corereg $allreg
worst_of $fh "ANY->ANY"   $allreg  $allreg

close $fh
project_close
