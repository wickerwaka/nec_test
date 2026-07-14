//============================================================================
//
//  test_mem - simulated memory for the V30 test harness
//
//  64 KB of BRAM organized as two byte lanes (even = AD7:0, odd = AD15:8),
//  mirrored across the full 1 MB address space. Initialized from the boot
//  image so the reset vector at FFFF0h (mirrored to FFF0h) holds the
//  bring-up program. I/O cycles are stubbed: reads return the host-
//  configurable cfg_iord value (default FFFFh), writes are
//  dropped (the capture buffer records them regardless, which is how
//  store-routine style register exfiltration works).
//
//  Both lanes are altsyncram instances with ENABLE_RUNTIME_MOD (instance IDs
//  "ME0" even / "ME1" odd): the host normally loads test programs and
//  inspects memory over the HPS bridge, but these instances also allow it
//  over JTAG with the In-System Memory Content Editor. Regenerate the
//  .mif/.hex boot images with sw/make_boot.py.
//
//============================================================================

module test_mem #(
    parameter LOG2_BYTES = 16,   // 64 KB
    parameter INIT_EVEN  = "rtl/boot_even.mif",
    parameter INIT_ODD   = "rtl/boot_odd.mif",
    // sim-only $readmemh images (byte per line)
    parameter INIT_EVEN_SIM = "hdl/rtl/boot_even.hex",
    parameter INIT_ODD_SIM  = "hdl/rtl/boot_odd.hex"
)(
    input             clk,

    input      [19:0] addr,          // latched bus address
    input       [2:0] cycle_type,    // BS encoding (see nec_bus)
    output     [15:0] rdata,

    input             wr_req,        // 1-clk pulse
    input      [15:0] wdata,
    input       [1:0] be,            // [0] even lane, [1] odd lane

    input      [15:0] cfg_iord       // data returned for I/O reads
);

localparam bit [2:0] BS_IOR  = 3'b001;
localparam bit [2:0] BS_MEMW = 3'b110;

localparam int WORDS = 1 << (LOG2_BYTES - 1);

wire [LOG2_BYTES-2:0] word_addr = addr[LOG2_BYTES-1:1];
wire we_even = wr_req && cycle_type == BS_MEMW && be[0];
wire we_odd  = wr_req && cycle_type == BS_MEMW && be[1];

wire [7:0] rdata_even, rdata_odd;

reg is_io_read;
always_ff @(posedge clk) is_io_read <= cycle_type == BS_IOR;

assign rdata = is_io_read ? cfg_iord : {rdata_odd, rdata_even};

`ifdef VERILATOR

reg [7:0] mem_even [0:WORDS-1];
reg [7:0] mem_odd  [0:WORDS-1];

initial begin
    $readmemh(INIT_EVEN_SIM, mem_even);
    $readmemh(INIT_ODD_SIM,  mem_odd);
end

reg [7:0] rdata_even_q, rdata_odd_q;
always_ff @(posedge clk) begin
    rdata_even_q <= mem_even[word_addr];
    rdata_odd_q  <= mem_odd[word_addr];
    if (we_even) mem_even[word_addr] <= wdata[7:0];
    if (we_odd)  mem_odd[word_addr]  <= wdata[15:8];
end
assign rdata_even = rdata_even_q;
assign rdata_odd  = rdata_odd_q;

`else

altsyncram #(
    .operation_mode("SINGLE_PORT"),
    .width_a(8),
    .widthad_a(LOG2_BYTES - 1),
    .numwords_a(WORDS),
    .outdata_reg_a("UNREGISTERED"),
    .init_file(INIT_EVEN),
    .lpm_type("altsyncram"),
    .lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=ME0")
) mem_even (
    .clock0(clk),
    .address_a(word_addr),
    .data_a(wdata[7:0]),
    .wren_a(we_even),
    .q_a(rdata_even),
    .aclr0(1'b0), .aclr1(1'b0),
    .address_b(1'b1), .addressstall_a(1'b0), .addressstall_b(1'b0),
    .byteena_a(1'b1), .byteena_b(1'b1),
    .clock1(1'b1), .clocken0(1'b1), .clocken1(1'b1),
    .clocken2(1'b1), .clocken3(1'b1),
    .data_b(1'b1), .eccstatus(),
    .q_b(), .rden_a(1'b1), .rden_b(1'b1), .wren_b(1'b0)
);

altsyncram #(
    .operation_mode("SINGLE_PORT"),
    .width_a(8),
    .widthad_a(LOG2_BYTES - 1),
    .numwords_a(WORDS),
    .outdata_reg_a("UNREGISTERED"),
    .init_file(INIT_ODD),
    .lpm_type("altsyncram"),
    .lpm_hint("ENABLE_RUNTIME_MOD=YES, INSTANCE_NAME=ME1")
) mem_odd (
    .clock0(clk),
    .address_a(word_addr),
    .data_a(wdata[15:8]),
    .wren_a(we_odd),
    .q_a(rdata_odd),
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
