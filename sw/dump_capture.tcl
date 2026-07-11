# Dump the V30 harness capture buffer over JTAG.
#
# Usage: quartus_stp -t sw/dump_capture.tcl [outfile]
#
# Reads the 4096 x 64-bit capture RAM (instance ID "CAPT") via the
# In-System Memory Content Editor interface and writes one 16-hex-digit
# record per line, address 0 first. Decode with sw/decode_capture.py.
#
# Notes:
#  - read_content_from_memory returns the content string highest-address
#    first, so each chunk is reversed before output.
#  - Large single reads (4096 words) have been observed to silently return
#    zeros on Quartus 17.1; read in small chunks instead.
#  - The FPGA is device 2 on the DE10-Nano JTAG chain (behind the HPS),
#    matching hdl/Makefile's quartus_pgm invocation.

set outfile "capture.hex"
if {[llength $argv] > 0} { set outfile [lindex $argv 0] }

set CHUNK 64

set hw [lindex [get_hardware_names] 0]
if {$hw eq ""} { puts "ERROR: no JTAG hardware found"; exit 1 }
set dev [lindex [get_device_names -hardware_name $hw] 1]
puts "hardware: $hw / device: $dev"

begin_memory_edit -hardware_name $hw -device_name $dev

set found 0
foreach inst [get_editable_mem_instances -hardware_name $hw -device_name $dev] {
    set idx  [lindex $inst 0]
    set dep  [lindex $inst 1]
    set name [lindex $inst 5]
    puts "instance $idx: $name depth=$dep"
    if {$name eq "CAPT"} {
        set found 1
        set fh [open $outfile w]
        for {set base 0} {$base < $dep} {incr base $CHUNK} {
            # bulk reads are flaky on Quartus 17.1: they can return all-zeros
            # (a valid capture record always has the READY bit set, so an
            # all-zero chunk is bogus) or garbage. Retry until non-zero and
            # stable across two consecutive reads.
            set zeros [string repeat 0 [expr {$CHUNK * 16}]]
            set data $zeros
            for {set try 0} {$try < 20} {incr try} {
                set d1 [read_content_from_memory -instance_index $idx \
                            -start_address $base -word_count $CHUNK -content_in_hex]
                if {$d1 eq $zeros} { continue }
                set d2 [read_content_from_memory -instance_index $idx \
                            -start_address $base -word_count $CHUNK -content_in_hex]
                if {$d1 eq $d2} { set data $d1; break }
            }
            if {$data eq $zeros} { puts "WARNING: chunk at $base read as all-zero" }
            # data is highest-address-first: emit records in reverse
            for {set i [expr {$CHUNK - 1}]} {$i >= 0} {incr i -1} {
                puts $fh [string range $data [expr {$i * 16}] [expr {$i * 16 + 15}]]
            }
        }
        close $fh
        puts "wrote $dep records to $outfile"
    }
}

end_memory_edit

if {!$found} { puts "ERROR: instance CAPT not found"; exit 1 }
