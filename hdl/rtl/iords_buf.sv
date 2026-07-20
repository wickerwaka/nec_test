//============================================================================
//
//  iords_buf - per-case I/O-read sequence buffer (INS / REP INS port serving)
//
//  Holds an ordered list of up to DEPTH 16-bit values, one served per IOR bus
//  cycle so the harness can return real, varied per-element port data for a
//  string-input instruction (6C/6D) - the V30 suite's upstream differentiator
//  over the open-bus V20 captures. The host loads the sequence over the HPS
//  bridge (write port) while the harness is between cases; nec_bus supplies the
//  read index (ior_idx, one per IOR). Byte forms carry the value in BOTH lanes
//  (v * 0x0101) so the served word is port-parity-agnostic - the exact same
//  convention as hdl/tb/tb_v30_core.sv (iords_arr) and sw/extract_iords.py.
//
//  COMBINATIONAL read (a small register file, DEPTH=64): the served value is
//  available with zero latency, so it drops into the existing scalar-cfg_iord
//  serving path in test_mem unchanged (system_large muxes it). Sized for the
//  emitter's worst REP case: the generator's CW distribution caps at 16 (see
//  sw/emit_suite.py gen_case strio), so DEPTH=64 is a 4x margin.
//
//============================================================================

module iords_buf #(
    parameter int DEPTH = 64,
    parameter int AW    = 6            // clog2(DEPTH)
)(
    input                clk,

    // host write port (load the sequence while stopped/between cases)
    input       [AW-1:0] h_waddr,
    input                h_we,
    input        [15:0]  h_wdata,

    // bus read port (index from nec_bus; combinational - zero latency)
    input       [AW-1:0] raddr,
    output      [15:0]   rdata
);

reg [15:0] mem [0:DEPTH-1];

always_ff @(posedge clk)
    if (h_we) mem[h_waddr] <= h_wdata;

// Combinational read: the value must be stable for the whole IOR cycle it
// indexes (it is - ior_idx only changes at cycle boundaries), matching the
// zero-latency scalar cfg_iord it replaces.
assign rdata = mem[raddr];

endmodule
