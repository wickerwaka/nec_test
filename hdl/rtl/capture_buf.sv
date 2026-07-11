//============================================================================
//
//  capture_buf - per-CPU-clock trace capture
//
//  Records one 64-bit record per CPU clock cycle (see nec_bus for the record
//  layout). Arms when `arm` rises, fills linearly, and stops when full so the
//  earliest cycles (reset release, first fetch) are always retained. The read
//  port is synchronous and idle-safe; the future HPS bridge drains it.
//
//  4096 x 64 = 256 Kbit of BRAM at the default depth (~1 ms of trace at
//  4 MHz CPU clock).
//
//============================================================================

module capture_buf #(
    parameter LOG2_DEPTH = 12
)(
    input                    clk,
    input                    reset,

    input                    arm,        // rising edge re-arms and clears
    input                    wr_valid,
    input             [63:0] wr_data,

    output reg               full,
    output reg [LOG2_DEPTH:0] count,     // records captured

    input   [LOG2_DEPTH-1:0] rd_addr,
    output reg        [63:0] rd_data
);

localparam int DEPTH = 1 << LOG2_DEPTH;

reg [63:0] buffer [0:DEPTH-1];
reg        armed;
reg        arm_q;

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
        end else if (armed && wr_valid) begin
            buffer[count[LOG2_DEPTH-1:0]] <= wr_data;
            count <= count + 1'd1;
            if (count == DEPTH - 1) begin
                full  <= 1'b1;
                armed <= 1'b0;
            end
        end
    end

    rd_data <= buffer[rd_addr];
end

endmodule
