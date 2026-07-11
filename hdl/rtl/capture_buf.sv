//============================================================================
//
//  capture_buf - per-CPU-clock trace capture
//
//  Records one 64-bit record per CPU clock cycle (see nec_bus for the record
//  layout). Arms when `arm` rises, fills linearly, and stops when full so the
//  earliest cycles (reset release, first fetch) are always retained.
//
//  The buffer is a single-port altsyncram with ENABLE_RUNTIME_MOD, instance
//  ID "CAPT": until the HPS bridge exists, dump it over JTAG with the
//  In-System Memory Content Editor (sw/dump_capture.tcl). The port address
//  muxes to the write pointer while armed and to rd_addr afterwards.
//
//  4096 x 64 = 256 Kbit of BRAM at the default depth (~1 ms of trace at
//  4 MHz CPU clock).
//
//============================================================================

module capture_buf #(
    parameter LOG2_DEPTH = 12
)(
    input                     clk,
    input                     reset,

    input                     arm,        // rising edge re-arms and clears
    input                     wr_valid,
    input              [63:0] wr_data,

    output reg                full,
    output reg [LOG2_DEPTH:0] count,      // records captured

    input    [LOG2_DEPTH-1:0] rd_addr,
    output             [63:0] rd_data
);

localparam int DEPTH = 1 << LOG2_DEPTH;

reg  armed;
reg  arm_q;

wire                  ram_we   = armed && wr_valid;
wire [LOG2_DEPTH-1:0] ram_addr = armed ? count[LOG2_DEPTH-1:0] : rd_addr;

always_ff @(posedge clk) begin
    arm_q <= arm;

    if (reset) begin
        armed <= 1'b0;
        full  <= 1'b0;
        count <= '0;
    end else begin
        if (arm && !arm_q) begin
            armed <= 1'b1;
            full  <= 1'b0;
            count <= '0;
        end else if (ram_we) begin
            count <= count + 1'd1;
            if (count == (LOG2_DEPTH+1)'(DEPTH - 1)) begin
                full  <= 1'b1;
                armed <= 1'b0;
            end
        end
    end
end

`ifdef VERILATOR

reg [63:0] buffer [0:DEPTH-1];
reg [63:0] rd_data_q;
always_ff @(posedge clk) begin
    if (ram_we) buffer[ram_addr] <= wr_data;
    rd_data_q <= buffer[ram_addr];
end
assign rd_data = rd_data_q;

`else

altsyncram #(
    .operation_mode("SINGLE_PORT"),
    .width_a(64),
    .widthad_a(LOG2_DEPTH),
    .numwords_a(DEPTH),
    .outdata_reg_a("UNREGISTERED"),  // 1-cycle latency, matches the sim model
    .lpm_type("altsyncram"),
    .lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=CAPT"),
    .power_up_uninitialized("FALSE")
) buffer (
    .clock0(clk),
    .address_a(ram_addr),
    .data_a(wr_data),
    .wren_a(ram_we),
    .q_a(rd_data),
    .aclr0(1'b0), .aclr1(1'b0),
    .address_b(1'b1), .addressstall_a(1'b0), .addressstall_b(1'b0),
    .byteena_a(1'b1), .byteena_b(1'b1),
    .clock1(1'b1), .clocken0(1'b1), .clocken1(1'b1),
    .clocken2(1'b1), .clocken3(1'b1),
    .data_b(1'b1), .eccstatus(),
    .q_b(), .rden_a(1'b1), .rden_b(1'b1), .wren_b(1'b0)
);

`endif

endmodule
