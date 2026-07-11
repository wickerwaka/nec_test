//============================================================================
//
//  test_mem - simulated memory for the V30 test harness
//
//  64 KB of BRAM organized as two byte lanes (even = AD7:0, odd = AD15:8),
//  mirrored across the full 1 MB address space. Initialized from hex files
//  so the reset vector at FFFF0h (mirrored to FFF0h) holds the bring-up
//  program. I/O cycles are stubbed: reads return 0000h, writes are dropped
//  (the capture buffer records them regardless, which is how store-routine
//  style register exfiltration will work).
//
//============================================================================

module test_mem #(
    parameter LOG2_BYTES = 16,   // 64 KB
    parameter INIT_EVEN  = "rtl/boot_even.hex",
    parameter INIT_ODD   = "rtl/boot_odd.hex"
)(
    input             clk,

    input      [19:0] addr,          // latched bus address
    input       [2:0] cycle_type,    // BS encoding (see nec_bus)
    output     [15:0] rdata,

    input             wr_req,        // 1-clk pulse
    input      [15:0] wdata,
    input       [1:0] be             // [0] even lane, [1] odd lane
);

localparam bit [2:0] BS_IOR  = 3'b001;
localparam bit [2:0] BS_IOW  = 3'b010;
localparam bit [2:0] BS_MEMW = 3'b110;

localparam int WORDS = 1 << (LOG2_BYTES - 1);

reg [7:0] mem_even [0:WORDS-1];
reg [7:0] mem_odd  [0:WORDS-1];

initial begin
    $readmemh(INIT_EVEN, mem_even);
    $readmemh(INIT_ODD,  mem_odd);
end

wire [LOG2_BYTES-2:0] word_addr = addr[LOG2_BYTES-1:1];

reg [7:0] rdata_even, rdata_odd;
reg       is_io_read;

always_ff @(posedge clk) begin
    rdata_even <= mem_even[word_addr];
    rdata_odd  <= mem_odd[word_addr];
    is_io_read <= cycle_type == BS_IOR;

    if (wr_req && cycle_type == BS_MEMW) begin
        if (be[0]) mem_even[word_addr] <= wdata[7:0];
        if (be[1]) mem_odd[word_addr]  <= wdata[15:8];
    end
end

assign rdata = is_io_read ? 16'h0000 : {rdata_odd, rdata_even};

endmodule
