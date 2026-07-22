//============================================================================
//
//  tb_ab - Campaign 4 A/B integration testbench
//
//  Instantiates the real integration (system_large) and drives it from the
//  ARM side only (the AXI master BFM on the lightweight bridge, exposed
//  under VERILATOR). It exercises BOTH selector positions of the Campaign 4
//  A/B mux (CFG.use_core, bit 25):
//
//    - chip position (use_core=0): a minimal max-mode bus-functional model
//      on the physical NEC pins answers a couple of cycles, proving the
//      known-good path still runs through the refactored nec_bus.
//    - core position (use_core=1): the internal v30_core boots from the
//      in-memory boot image (test_mem $readmemh), behind the real nec_bus
//      capture path. Its capture is drained through the bridge and written
//      as 64-bit records (same format as the board / the real-chip golden),
//      for sw/check_ab_sim.py to diff against largemode_boot_real.hex.
//
//  Built and run by sw/check_ab_sim.py (Verilator --binary, top tb_ab, over
//  system_large + nec_bus + test_mem + capture_buf + hps_axi_slave + the
//  core rtl). Plusargs: +cap=<out.hex> +ncap=<n>.
//
//============================================================================

`timescale 1ns/1ps

module tb_ab;

localparam bit [2:0] BS_CODE = 3'b100;
localparam bit [2:0] BS_MEMW = 3'b110;
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_PASV = 3'b111;

// register map
localparam bit [20:0] A_MEM      = 21'h000000;
localparam bit [20:0] A_CAP      = 21'h100000;
localparam bit [20:0] R_MAGIC    = 21'h180000;
localparam bit [20:0] R_CTRL     = 21'h180004;
localparam bit [20:0] R_CFG      = 21'h180008;
localparam bit [20:0] R_STATUS   = 21'h180010;
localparam bit [20:0] R_CAPCOUNT = 21'h180014;

logic clk = 0;
logic reset = 1;
always #15.625 clk = ~clk;   // 32 MHz

// NEC pins
wire  [19:0] NEC_AD;
wire         NEC_AD_DIR, NEC_CLK, NEC_POLL_N, NEC_READY, NEC_RESET;
wire         NEC_INT, NEC_NMI, NEC_ENABLE_N;
logic  [1:0] qs_drv = 2'b00;
logic  [2:0] bs_drv = BS_PASV;
logic        buslock_n_drv = 1'b1, ube_n_drv = 1'b1, rd_n_drv = 1'b1;

// BFM tristate drive on the physical AD (chip position only)
logic [19:0] ad_drv = '0;
logic        ad_addr_en = 0, ad_data_en = 0;
assign NEC_AD[15:0]  = (ad_addr_en | ad_data_en) ? ad_drv[15:0]  : 16'hzzzz;
assign NEC_AD[19:16] = ad_addr_en                ? ad_drv[19:16] : 4'hz;

// AXI master signals
logic [11:0] axs_awid = 0, axs_arid = 0;
logic [20:0] axs_awaddr = 0, axs_araddr = 0;
logic  [3:0] axs_awlen = 0, axs_arlen = 0;
logic        axs_awvalid = 0, axs_wvalid = 0, axs_wlast = 0;
logic        axs_bready = 0, axs_arvalid = 0, axs_rready = 0;
logic [31:0] axs_wdata = 0;
logic  [3:0] axs_wstrb = 0;
wire         axs_awready, axs_wready, axs_bvalid, axs_arready;
wire         axs_rlast, axs_rvalid;
wire  [11:0] axs_bid, axs_rid;
wire  [31:0] axs_rdata;
wire   [1:0] axs_bresp, axs_rresp;

wire         nec_lg_n;

// Save-state v2 is intentionally idle here; system_large owns the addressed
// interface tie-off at its v30_core instance.
system_large dut
(
    .clk(clk), .reset(reset),

    .DDRAM_CLK(), .DDRAM_BUSY(1'b0), .DDRAM_BURSTCNT(), .DDRAM_ADDR(),
    .DDRAM_DOUT(64'd0), .DDRAM_DOUT_READY(1'b0), .DDRAM_RD(),
    .DDRAM_DIN(), .DDRAM_BE(), .DDRAM_WE(),

    .NEC_AD(NEC_AD), .NEC_AD_DIR(NEC_AD_DIR), .NEC_CLK(NEC_CLK),
    .NEC_POLL_N(NEC_POLL_N), .NEC_READY(NEC_READY), .NEC_RESET(NEC_RESET),
    .NEC_INT(NEC_INT), .NEC_NMI(NEC_NMI),
    .NEC_QS(qs_drv), .NEC_BS(bs_drv),
    .NEC_BUSLOCK_N(buslock_n_drv), .NEC_UBE_N(ube_n_drv), .NEC_RD_N(rd_n_drv),
    .NEC_ENABLE_N(NEC_ENABLE_N),

    .axs_awid(axs_awid), .axs_awaddr(axs_awaddr), .axs_awlen(axs_awlen),
    .axs_awvalid(axs_awvalid), .axs_awready(axs_awready),
    .axs_wdata(axs_wdata), .axs_wstrb(axs_wstrb), .axs_wvalid(axs_wvalid),
    .axs_wlast(axs_wlast), .axs_wready(axs_wready),
    .axs_bid(axs_bid), .axs_bresp(axs_bresp), .axs_bvalid(axs_bvalid),
    .axs_bready(axs_bready),
    .axs_arid(axs_arid), .axs_araddr(axs_araddr), .axs_arlen(axs_arlen),
    .axs_arvalid(axs_arvalid), .axs_arready(axs_arready),
    .axs_rid(axs_rid), .axs_rdata(axs_rdata), .axs_rresp(axs_rresp),
    .axs_rlast(axs_rlast), .axs_rvalid(axs_rvalid), .axs_rready(axs_rready),

    .NEC_LG_N(nec_lg_n), .dbg_led()
);

int errors = 0;
task automatic check(input bit cond, input string msg);
    if (!cond) begin errors++; $display("FAIL: %s (t=%0t)", msg, $time); end
    else            $display("pass: %s", msg);
endtask

//----------------------------------------------------------------------------
// AXI master BFM (same handshake discipline as tb_harness)
//----------------------------------------------------------------------------
task automatic wait_hs(ref logic sig);
    bit prev;
    do begin prev = sig; @(posedge clk); end while (!prev);
endtask
logic hs_awready, hs_wready, hs_bvalid, hs_arready, hs_rvalid;
always_comb hs_awready = axs_awready;
always_comb hs_wready  = axs_wready;
always_comb hs_bvalid  = axs_bvalid;
always_comb hs_arready = axs_arready;
always_comb hs_rvalid  = axs_rvalid;

task automatic axi_write32(input bit [20:0] a, input bit [31:0] d,
                           input bit [3:0] strb = 4'hF);
    axs_awaddr = a; axs_awlen = 0; axs_awvalid = 1;
    wait_hs(hs_awready); axs_awvalid = 0;
    axs_wdata = d; axs_wstrb = strb; axs_wlast = 1; axs_wvalid = 1;
    wait_hs(hs_wready); axs_wvalid = 0; axs_wlast = 0;
    axs_bready = 1; wait_hs(hs_bvalid); axs_bready = 0;
    @(posedge clk);
endtask

task automatic axi_read32(input bit [20:0] a, output bit [31:0] d);
    axs_araddr = a; axs_arlen = 0; axs_arvalid = 1;
    wait_hs(hs_arready); axs_arvalid = 0;
    axs_rready = 1; wait_hs(hs_rvalid); d = axs_rdata; axs_rready = 0;
    @(posedge clk);
endtask

task automatic axi_read_cap(input int rec, output bit [63:0] r);
    bit [31:0] lo, hi;
    axi_read32(A_CAP + 21'(rec * 8),     lo);
    axi_read32(A_CAP + 21'(rec * 8 + 4), hi);
    r = {hi, lo};
endtask

//----------------------------------------------------------------------------
// minimal max-mode bus cycle BFM (chip position sanity)
//----------------------------------------------------------------------------
localparam realtime TDLY = 40ns;
task automatic bus_cycle(input bit [2:0] btype, input bit [19:0] addr,
                         input bit [15:0] wdata, output bit [15:0] rdata);
    @(posedge NEC_CLK); #(TDLY); bs_drv = btype;
    @(posedge NEC_CLK); #(TDLY); ad_drv = addr; ube_n_drv = 0; ad_addr_en = 1;
    @(posedge NEC_CLK); #(TDLY); ad_addr_en = 0;
    if (btype == BS_MEMW) begin ad_drv = {4'h0, wdata}; ad_data_en = 1; end
    else rd_n_drv = 0;
    @(posedge NEC_CLK); #(TDLY); bs_drv = BS_PASV;
    @(negedge NEC_CLK); rdata = NEC_AD[15:0];
    @(posedge NEC_CLK); #(TDLY); rd_n_drv = 1; #(TDLY);
    ad_data_en = 0; ube_n_drv = 1;
    @(posedge NEC_CLK);
endtask

//----------------------------------------------------------------------------
// test sequence
//----------------------------------------------------------------------------
bit [31:0] w;
bit [15:0] rd;
bit [63:0] rec;
string cap_path;
integer ncap, fd, cnt, i;

initial begin
    if (!$value$plusargs("cap=%s", cap_path)) cap_path = "core_boot_cap.hex";
    if (!$value$plusargs("ncap=%d", ncap))    ncap = 260;

    repeat (4) @(posedge clk);
    reset = 0;

    axi_read32(R_MAGIC, w);
    check(w == 32'h56333031, $sformatf("bridge magic %08x", w));

    //--------------------------------------------------------------------
    // A/B position 0: socketed chip (BFM). Large mode, use_core=0.
    //--------------------------------------------------------------------
    axi_write32(R_CTRL, 32'h5);                     // host_reset | skip_pwrup
    axi_write32(R_CFG,  32'h00FF_0008);             // small=0, use_core=0, div 8
    qs_drv = 2'b00; bs_drv = BS_PASV;
    axi_write32(R_CTRL, 32'h4);                     // run
    while (NEC_RESET !== 1'b1) @(posedge clk);
    while (NEC_RESET) @(posedge NEC_CLK);
    check(!nec_lg_n, "chip pos: S/LG strap in large mode");
    check(!NEC_ENABLE_N, "chip pos: CPU powered (ENABLE_N low)");
    bus_cycle(BS_CODE, 20'hFFFF0, 16'h0, rd);
    check(rd == 16'h00EA, $sformatf("chip pos: vector fetch %04x (expect 00EA)", rd));
    bus_cycle(BS_MEMW, 20'h02100, 16'h1234, rd);
    bus_cycle(BS_MEMR, 20'h02100, 16'h0, rd);
    check(rd == 16'h1234, $sformatf("chip pos: write/readback %04x (expect 1234)", rd));
    axi_write32(R_CTRL, 32'h5);                     // stop

    //--------------------------------------------------------------------
    // A/B position 1: internal v30_core. Large mode, use_core=1.
    // Boots from the in-memory boot image; the chip is powered off.
    //--------------------------------------------------------------------
    axi_write32(R_CFG, 32'h02FF_0008);              // small=0, use_core=1, div 8
    axi_write32(R_CTRL, 32'h4);                     // run (skip_pwrup)
    while (NEC_RESET !== 1'b1) @(posedge clk);
    check(NEC_ENABLE_N, "core pos: socketed chip powered OFF (ENABLE_N high)");
    while (NEC_RESET) @(posedge NEC_CLK);

    // let the core run until the capture fills enough records
    repeat (ncap + 40) @(posedge NEC_CLK);
    axi_write32(R_CTRL, 32'h5);                     // stop; read trace

    axi_read32(R_CAPCOUNT, w);
    check(w > ncap, $sformatf("core pos: capcount %0d > %0d", w, ncap));
    cnt = (w > ncap) ? ncap : w;

    fd = $fopen(cap_path, "w");
    for (i = 0; i < cnt; i++) begin
        axi_read_cap(i, rec);
        $fwrite(fd, "%016x\n", rec);
    end
    $fclose(fd);
    $display("wrote %0d core-mode capture records to %s", cnt, cap_path);

    if (errors == 0) $display("AB TESTS PASSED");
    else             $display("%0d AB TEST(S) FAILED", errors);
    $finish;
end

initial begin
    #12ms;
    $display("FAIL: timeout");
    $finish;
end

endmodule
