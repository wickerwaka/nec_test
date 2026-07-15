//============================================================================
//
//  wvec_buf - explicit wait-vector replay buffer (Phase 2a)
//
//  Holds an exact per-bus-cycle Tw (wait-state) count so the harness can
//  replay a HOST-SPECIFIED wait sequence instead of the uniform-N or seeded-
//  LFSR generators. Applied identically to the socketed chip and the fabric
//  v30_core (same buffer, same per-bus-cycle index), so two runs can be made
//  byte-identical except for ONE selected access's wait - the enabler for the
//  controlled single-wait impulse experiments of the causal-radius campaign.
//
//  Organized as 1024 x 32-bit words = 4096 byte entries (one Tw count per bus
//  cycle, 0..255). The host writes whole 32-bit words over the HPS bridge; the
//  bus reads a word and selects the byte for the current bus-cycle index. A
//  true dual-port RAM: host write port (valid while the harness is stopped),
//  bus read port (address = bus-cycle index while running). Same clock, no CDC.
//
//============================================================================

module wvec_buf #(
    parameter LOG2_WORDS = 10          // 1024 words x 4 bytes = 4096 entries
)(
    input                       clk,

    // host write port (32-bit words, while stopped)
    input      [LOG2_WORDS-1:0] h_waddr,
    input                       h_we,
    input                [31:0] h_wdata,

    // bus read port (registered, 1-clk latency like the other harness RAMs)
    input      [LOG2_WORDS-1:0] raddr,
    output               [31:0] rdata
);

localparam int WORDS = 1 << LOG2_WORDS;

// Inferred simple dual-port block RAM (one write port, one registered read
// port, distinct addresses, single clock). Quartus infers M10K BRAM from this
// pattern; the same code is the Verilator model. 1-cycle read latency matches
// the harness's other RAMs.
reg [31:0] buffer [0:WORDS-1];
reg [31:0] rdata_q;
always_ff @(posedge clk) begin
    if (h_we) buffer[h_waddr] <= h_wdata;
    rdata_q <= buffer[raddr];
end
assign rdata = rdata_q;

endmodule
