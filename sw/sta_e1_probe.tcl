# sta_e1_probe.tcl -- THE E-1 DELETION'S OWN PROBE, run on an already-fitted db.
#
# WHY IT EXISTS.  `docs/notes/timing50_e1_rederivation_2026-08-12.md` registers
# R-3 and R-5 before the builds, and neither is readable off `sta_census.tcl`'s
# class table:
#
#   R-3  the binding class returns to `CORE -> ANY`, launching from
#        `v30u_eu|upc_opc[*]` / `upc_page[*]` and latching on
#        `nec_bus|ad_in_q[*]` -- the class E-1 was written to hide.
#   R-5  `core_ad_hold` is NOT on the RETENTION build's binding cone.  §3 of
#        that note derives a contract-only `-setup 2` for `core_ad_hold[19:16]`
#        and declines to land it, ON THE PREDICTION that the register is one
#        flop UPSTREAM of `ad_in_q` on the same cone, so `core -> ad_in_q`
#        binds first whatever `core_ad_hold` is given.  This is the falsifier:
#        if `core_ad_hold`'s worst incoming slack is BELOW `ad_in_q`'s, the
#        booked narrowing re-opens with a measured value.
#
# It reports the worst setup slack into each observation endpoint group
# separately, and the worst path from the ucore into each.  It creates its own
# timing netlist; it does not re-fit and cannot change the build it reads.
#
#     quartus_sta -t ../sw/sta_e1_probe.tcl nec_test nec_test_ucore <outprefix>

set proj [lindex $quartus(args) 0]
set rev  [lindex $quartus(args) 1]
set out  [lindex $quartus(args) 2]

project_open $proj -revision $rev
# The corner the gate scores, named rather than defaulted (sta_census.tcl's
# reasoning, unchanged): `<rev>.sta.rpt` records "Slow 1100mV 100C Model".
create_timing_netlist -model slow -speed 7 -temperature 100 -voltage 1100
read_sdc
update_timing_netlist

set fh [open "$out.e1probe.txt" w]

proc emit {fh s} { puts $fh $s ; puts $s }

# --- the endpoint groups, by name, exactly as `nec_test.sdc` used to ------- #
set g_adin  [get_registers -nowarn {*|nec_bus:*|ad_in_q[*]}]
set g_bs    [get_registers -nowarn {*|nec_bus:*|bs_q[*]}]
set g_qs    [get_registers -nowarn {*|nec_bus:*|qs_q[*]}]
set g_rd    [get_registers -nowarn {*|nec_bus:*|rd_n_q}]
set g_ube   [get_registers -nowarn {*|nec_bus:*|ube_n_q}]
set g_lock  [get_registers -nowarn {*|nec_bus:*|buslock_n_q}]
set g_hold  [get_registers -nowarn {*|core_ad_hold[*]}]

set ucore [add_to_collection \
               [get_registers -nowarn {*|v30u_eu:*|*}] \
               [get_registers -nowarn {*|v30u_biu:*|*}]]

emit $fh "== E-1 PROBE =="
emit $fh [format "ucore registers: %d" [get_collection_size $ucore]]

foreach {name grp} [list ad_in_q $g_adin bs_q $g_bs qs_q $g_qs rd_n_q $g_rd \
                         ube_n_q $g_ube buslock_n_q $g_lock \
                         core_ad_hold $g_hold] {
    set n [get_collection_size $grp]
    if {$n == 0} {
        emit $fh [format "%-14s  n=0   (absent in this configuration)" $name]
        continue
    }
    # worst setup path into the group from ANY launch
    set any "n/a"
    foreach_in_collection p [get_timing_paths -setup -to $grp -npaths 1] {
        set any [format "%.3f" [get_path_info $p -slack]]
    }
    # worst setup path into the group launched by the ucore
    set frm "n/a"
    set frmlaunch ""
    set frmlatch ""
    set frmlev ""
    foreach_in_collection p [get_timing_paths -setup -from $ucore -to $grp -npaths 1] {
        set frm [format "%.3f" [get_path_info $p -slack]]
        set frmlaunch [get_node_info -name [get_path_info $p -from]]
        set frmlatch  [get_node_info -name [get_path_info $p -to]]
        set frmlev    [get_path_info $p -num_logic_levels]
    }
    emit $fh [format "%-14s  n=%-3d  worst_any=%-9s  worst_from_ucore=%-9s  lev=%s" \
                  $name $n $any $frm $frmlev]
    if {$frmlaunch ne ""} {
        emit $fh [format "                 %s" $frmlaunch]
        emit $fh [format "              -> %s" $frmlatch]
    }
}

# --- and the design's own worst, for the comparison the note needs --------- #
emit $fh "-- design worst setup path (any -> any) --"
foreach_in_collection p [get_timing_paths -setup -npaths 1] {
    emit $fh [format "  slack %.3f  levels %s" \
                  [get_path_info $p -slack] [get_path_info $p -num_logic_levels]]
    emit $fh [format "  %s" [get_node_info -name [get_path_info $p -from]]]
    emit $fh [format "  -> %s" [get_node_info -name [get_path_info $p -to]]]
}

close $fh
project_close
