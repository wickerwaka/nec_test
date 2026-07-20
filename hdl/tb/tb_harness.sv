//============================================================================
//
//  tb_harness - system-level test of the V30 harness core
//
//  Instantiates system_large (the real integration) and drives it from two
//  sides, like the deployed system:
//    - an AXI master BFM standing in for the ARM on the lightweight bridge
//      (system_large exposes the AXI port directly under VERILATOR)
//    - a crude V30 bus-functional model on the NEC pins, in both
//      small-scale and large-scale (max) modes
//
//  Run from the repo root (hex image paths):
//    $ verilator --binary --timing -Wno-fatal --top-module tb_harness \
//        hdl/tb/tb_harness.sv hdl/rtl/system_large.sv hdl/rtl/nec_bus.sv \
//        hdl/rtl/test_mem.sv hdl/rtl/capture_buf.sv hdl/rtl/hps_axi_slave.sv
//
//============================================================================

`timescale 1ns/1ps

module tb_harness;

localparam bit [2:0] BS_IOR  = 3'b001;
localparam bit [2:0] BS_CODE = 3'b100;
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_MEMW = 3'b110;
localparam bit [2:0] BS_PASV = 3'b111;

// register map
localparam bit [20:0] A_MEM      = 21'h000000;
localparam bit [20:0] A_CAP      = 21'h100000;
localparam bit [20:0] R_MAGIC    = 21'h180000;
localparam bit [20:0] R_CTRL     = 21'h180004;
localparam bit [20:0] R_CFG      = 21'h180008;
localparam bit [20:0] R_PINS     = 21'h18000C;
localparam bit [20:0] R_STATUS   = 21'h180010;
localparam bit [20:0] R_CAPCOUNT = 21'h180014;

logic clk = 0;
logic reset = 1;
always #15.625 clk = ~clk;   // 32 MHz

// NEC pins
wire  [19:0] NEC_AD;
wire         NEC_AD_DIR, NEC_CLK, NEC_POLL_N, NEC_READY, NEC_RESET;
wire         NEC_INT, NEC_NMI, NEC_ENABLE_N;
logic  [1:0] qs_drv = 2'b10;   // small-mode idle: {INTAK=1, ASTB=0}
logic  [2:0] bs_drv = BS_PASV;
logic        buslock_n_drv = 1'b1, ube_n_drv = 1'b1, rd_n_drv = 1'b1;

// BFM tristate drive (simple en?val:'z forms only — Verilator requirement)
logic [19:0] ad_drv = '0;
logic        ad_addr_en = 0;
logic        ad_data_en = 0;
wire         tb_ad_en = ad_addr_en | ad_data_en;
assign NEC_AD[15:0]  = tb_ad_en   ? ad_drv[15:0]  : 16'hzzzz;
assign NEC_AD[19:16] = ad_addr_en ? ad_drv[19:16] : 4'hz;

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

    .NEC_LG_N(nec_lg_n),
    .dbg_led()
);
wire nec_lg_n;

int errors = 0;

task automatic check(input bit cond, input string msg);
    if (!cond) begin
        errors++;
        $display("FAIL: %s (t=%0t)", msg, $time);
    end else begin
        $display("pass: %s", msg);
    end
endtask

//----------------------------------------------------------------------------
// AXI master BFM
//----------------------------------------------------------------------------
// Wait until a handshake actually occurs: the DUT samples valid&ready at a
// posedge, so detect using the value that was stable BEFORE that edge.
task automatic wait_hs(ref logic sig);
    bit prev;
    do begin
        prev = sig;
        @(posedge clk);
    end while (!prev);
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
    wait_hs(hs_awready);
    axs_awvalid = 0;
    axs_wdata = d; axs_wstrb = strb; axs_wlast = 1; axs_wvalid = 1;
    wait_hs(hs_wready);
    axs_wvalid = 0; axs_wlast = 0;
    axs_bready = 1;
    wait_hs(hs_bvalid);
    axs_bready = 0;
    @(posedge clk);
endtask

task automatic axi_read32(input bit [20:0] a, output bit [31:0] d);
    axs_araddr = a; axs_arlen = 0; axs_arvalid = 1;
    wait_hs(hs_arready);
    axs_arvalid = 0;
    axs_rready = 1;
    wait_hs(hs_rvalid);
    d = axs_rdata;
    axs_rready = 0;
    @(posedge clk);
endtask

task automatic axi_read_cap(input int rec, output bit [63:0] r);
    bit [31:0] lo, hi;
    axi_read32(A_CAP + 21'(rec * 8), lo);
    axi_read32(A_CAP + 21'(rec * 8 + 4), hi);
    r = {hi, lo};
endtask

//----------------------------------------------------------------------------
// V30 bus-functional model
//----------------------------------------------------------------------------
localparam realtime TDLY = 40ns;

// max-mode bus cycle
task automatic bus_cycle(
    input bit [2:0]  btype,
    input bit [19:0] addr,
    input bit        ube_n,
    input bit [15:0] wdata,
    output bit [15:0] rdata
);
    @(posedge NEC_CLK); #(TDLY);
    bs_drv = btype;
    @(posedge NEC_CLK); #(TDLY);
    ad_drv = addr; ube_n_drv = ube_n; ad_addr_en = 1;
    @(posedge NEC_CLK); #(TDLY);
    ad_addr_en = 0;
    if (btype == BS_MEMW) begin
        ad_drv = {4'h0, wdata}; ad_data_en = 1;
    end else begin
        rd_n_drv = 0;
    end
    @(posedge NEC_CLK); #(TDLY);
    bs_drv = BS_PASV;
    @(negedge NEC_CLK);
    rdata = NEC_AD[15:0];
    @(posedge NEC_CLK); #(TDLY);
    rd_n_drv = 1;
    #(TDLY);
    ad_data_en = 0; ube_n_drv = 1;
    @(posedge NEC_CLK);
endtask

// small-scale mode bus cycle: ASTB address strobe, RD/WR strobes.
task automatic small_bus_cycle(
    input bit        is_write,
    input bit        is_io,
    input bit [19:0] addr,
    input bit        ube_n,
    input bit [15:0] wdata,
    output bit [15:0] rdata
);
    @(posedge NEC_CLK); #(TDLY);
    ad_drv = addr; ube_n_drv = ube_n; ad_addr_en = 1;
    bs_drv[2] = ~is_io;
    qs_drv[0] = 1;
    @(negedge NEC_CLK); #(TDLY);
    qs_drv[0] = 0;
    @(posedge NEC_CLK); #(TDLY);
    ad_addr_en = 0;
    if (is_write) begin
        ad_drv = {4'h0, wdata}; ad_data_en = 1;
        buslock_n_drv = 0;
    end else begin
        rd_n_drv = 0;
    end
    // T3 (+ TW while READY is low): sample READY shortly before the
    // falling edge, like the real part, and extend the cycle if not ready
    @(posedge NEC_CLK); #110ns;
    while (!NEC_READY) begin
        @(posedge NEC_CLK); #110ns;   // TW
    end
    @(negedge NEC_CLK);
    rdata = NEC_AD[15:0];
    @(posedge NEC_CLK); #(TDLY);
    rd_n_drv = 1; buslock_n_drv = 1;
    #(TDLY);
    ad_data_en = 0; ube_n_drv = 1;
    @(posedge NEC_CLK);
endtask

int nec_clks;
always @(posedge NEC_CLK) nec_clks++;

//----------------------------------------------------------------------------
// test sequence
//----------------------------------------------------------------------------
bit [15:0] rd;
bit [31:0] w;
bit [63:0] rec;
int reset_clks;
bit astb_seen_in_cap, rd_seen_in_cap;

initial begin
    repeat (4) @(posedge clk);
    reset = 0;

    //------------------------------------------------------------------
    // bridge sanity
    //------------------------------------------------------------------
    axi_read32(R_MAGIC, w);
    check(w == 32'h56333031, $sformatf("bridge magic %08x", w));

    // take control, poke memory over AXI, read back (incl. byte strobes)
    axi_write32(R_CTRL, 32'h5);            // host_reset | skip_pwrup
    axi_read32(R_STATUS, w);
    check(w[1] == 0, "cpu held in reset under host_reset");

    axi_write32(A_MEM + 21'h3000, 32'hCAFEBABE);
    axi_read32(A_MEM + 21'h3000, w);
    check(w == 32'hCAFEBABE, $sformatf("mem via bridge %08x (expect CAFEBABE)", w));
    axi_write32(A_MEM + 21'h3000, 32'h0000_5A00, 4'b0010);  // byte 1 only
    axi_read32(A_MEM + 21'h3000, w);
    check(w == 32'hCAFE5ABE, $sformatf("byte strobe write %08x (expect CAFE5ABE)", w));

    // boot image visible through the bridge (reset vector far jump)
    axi_read32(A_MEM + 21'hFFF0, w);
    check(w == 32'h0001_00EA, $sformatf("boot image via bridge %08x (expect 000100EA)", w));

    //------------------------------------------------------------------
    // small-scale mode run under host control (default CFG is small mode)
    //------------------------------------------------------------------
    axi_write32(R_CTRL, 32'h4);            // release host_reset, keep skip_pwrup
    while (NEC_RESET !== 1'b1) @(posedge clk);
    reset_clks = 0;
    while (NEC_RESET) begin
        @(posedge NEC_CLK);
        reset_clks++;
        if (reset_clks > 2000) break;
    end
    check(reset_clks >= 4, $sformatf("RESET held %0d CPU clocks (>=4)", reset_clks));
    check(!NEC_ENABLE_N, "CPU powered");

    small_bus_cycle(0, 0, 20'hFFFF0, 1'b0, 16'h0, rd);
    check(rd == 16'h00EA, $sformatf("sm: vector fetch returned %04x (expect 00EA)", rd));
    small_bus_cycle(1, 0, 20'h02000, 1'b0, 16'h5678, rd);
    small_bus_cycle(0, 0, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'h5678, $sformatf("sm: write/readback returned %04x (expect 5678)", rd));

    // stop the run first: capture is only readable while disarmed, and it
    // must survive host_reset
    axi_write32(R_CTRL, 32'h5);            // host_reset | skip_pwrup
    axi_read32(R_CAPCOUNT, w);
    check(w > 4, $sformatf("capcount %0d > 4 (after stop)", w));

    // capture records via the bridge: look for reset tail, ASTB, RD strobes
    astb_seen_in_cap = 0; rd_seen_in_cap = 0;
    axi_read_cap(0, rec);
    check(rec[55] && rec[51], $sformatf("cap[0] reset+ready record %016x", rec));
    for (int i = 30; i < 60; i++) begin
        axi_read_cap(i, rec);
        astb_seen_in_cap |= rec[46];
        rd_seen_in_cap   |= ~rec[48];
    end
    check(astb_seen_in_cap, "capture contains ASTB (via bridge)");
    check(rd_seen_in_cap,   "capture contains RD strobes (via bridge)");

    //------------------------------------------------------------------
    // small-mode wait states: identical read with 0 vs 2 waits
    //------------------------------------------------------------------
    begin
        int base, waited;
        axi_write32(R_CTRL, 32'h4);                    // resume (0 waits)
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);
        base = nec_clks;
        small_bus_cycle(0, 0, 20'hFFFF0, 1'b0, 16'h0, rd);
        base = nec_clks - base;

        axi_write32(R_CTRL, 32'h5);
        axi_write32(R_CFG, (1 << 24) | (8'hFF << 16) | (2 << 8) | 6'd8);
        axi_write32(R_CTRL, 32'h4);
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);
        waited = nec_clks;
        small_bus_cycle(0, 0, 20'hFFFF0, 1'b0, 16'h0, rd);
        waited = nec_clks - waited;

        check(rd == 16'h00EA, $sformatf("sm+waits: fetch returned %04x (expect 00EA)", rd));
        check(waited == base + 2,
              $sformatf("sm: 2 wait states add 2 clks (%0d -> %0d)", base, waited));

        axi_write32(R_CTRL, 32'h5);                    // stop; CFG reset below
    end

    //------------------------------------------------------------------
    // reconfigure to large (max) mode through the bridge and rerun
    //------------------------------------------------------------------
    axi_write32(R_CFG, 32'h00FF_0008);                // small_mode=0, vector FF, div 8
    qs_drv = 2'b00; bs_drv = BS_PASV;
    axi_write32(R_CTRL, 32'h4);                       // run
    while (NEC_RESET !== 1'b1) @(posedge clk);
    while (NEC_RESET) @(posedge NEC_CLK);
    $display("-- large-scale mode --");

    check(!nec_lg_n, "S/LG strap follows CFG into large mode");
    bus_cycle(BS_CODE, 20'hFFFF0, 1'b0, 16'h0, rd);
    check(rd == 16'h00EA, $sformatf("lg: vector fetch returned %04x (expect 00EA)", rd));
    bus_cycle(BS_MEMW, 20'h02100, 1'b0, 16'h1234, rd);
    bus_cycle(BS_MEMR, 20'h02100, 1'b0, 16'h0, rd);
    check(rd == 16'h1234, $sformatf("lg: write/readback returned %04x (expect 1234)", rd));
    bus_cycle(BS_IOR, 20'h00080, 1'b0, 16'h0, rd);
    check(rd == 16'hFFFF, $sformatf("lg: io read returned %04x (expect FFFF, IORD default)", rd));

    // host reclaims memory and sees the CPU's write
    axi_write32(R_CTRL, 32'h5);
    axi_read32(A_MEM + 21'h2100, w);
    check(w[15:0] == 16'h1234, $sformatf("cpu write visible via bridge %04x (expect 1234)", w[15:0]));

    //------------------------------------------------------------------
    // IORD config + pin-event scheduler (large mode)
    //------------------------------------------------------------------
    begin
        int t_fire, t_seen;
        axi_write32(21'h180018, 32'h0000_ABCD);        // IORD = ABCD
        axi_write32(21'h18001C, 32'h000FFFF0);         // EVT_ADDR = FFFF0
        axi_write32(21'h180020, 32'h8000_0000 | (8 << 16) | 16'd3);
                                                       // arm, INT, hold 8, delay 3
        axi_write32(R_CTRL, 32'h4);                    // run
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);

        // IOR returns the configured data
        bus_cycle(BS_IOR, 20'h00080, 1'b0, 16'h0, rd);
        check(rd == 16'hABCD, $sformatf("IORD config returned %04x (expect ABCD)", rd));

        // CODE fetch at the trigger address fires INT after 3 CPU clocks
        check(!NEC_INT, "INT idle before trigger");
        fork
            bus_cycle(BS_CODE, 20'hFFFF0, 1'b0, 16'h0, rd);
            begin
                t_fire = nec_clks;
                while (!NEC_INT && (nec_clks - t_fire) < 40) @(posedge NEC_CLK);
                t_seen = nec_clks - t_fire;
            end
        join
        while (!NEC_INT && (nec_clks - t_fire) < 40) @(posedge NEC_CLK);
        check(NEC_INT, "pin event fired INT");
        axi_read32(R_STATUS, w);
        check(w[3], "STATUS.evt_fired set");
        repeat (12) @(posedge NEC_CLK);
        check(!NEC_INT, "INT released after hold");
        axi_write32(21'h180020, 32'h0);                // disarm
        axi_write32(R_CTRL, 32'h5);
    end

    //------------------------------------------------------------------
    // iords sequence serving (INS / REP INS): a host-loaded per-element
    // I/O-read sequence served one value per IOR cycle, in order; out-of-
    // range and disabled both fall back to the scalar IORD (backward compat).
    //------------------------------------------------------------------
    begin
        logic [15:0] s0, s1, s2, s3;
        axi_write32(21'h180028, 32'h1);                // IORDS_CTL: reset seq
        axi_write32(21'h18002C, 32'h0000_1111);        // push v0
        axi_write32(21'h18002C, 32'h0000_2222);        // push v1
        axi_write32(21'h18002C, 32'h0000_3333);        // push v2
        axi_write32(21'h180028, 32'h2);                // IORDS_CTL: enable
        axi_write32(21'h180018, 32'h0000_ABCD);        // scalar fallback
        axi_write32(R_CTRL, 32'h4);                    // run -> ior_idx=0
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);
        bus_cycle(BS_IOR, 20'h00080, 1'b0, 16'h0, s0);
        bus_cycle(BS_IOR, 20'h00082, 1'b0, 16'h0, s1);
        bus_cycle(BS_IOR, 20'h00084, 1'b0, 16'h0, s2);
        bus_cycle(BS_IOR, 20'h00086, 1'b0, 16'h0, s3);  // idx 3 >= cnt -> scalar
        check(s0 == 16'h1111, $sformatf("iords[0] served %04x (expect 1111)", s0));
        check(s1 == 16'h2222, $sformatf("iords[1] served %04x (expect 2222)", s1));
        check(s2 == 16'h3333, $sformatf("iords[2] served %04x (expect 3333)", s2));
        check(s3 == 16'hABCD, $sformatf("iords out-of-range -> scalar %04x (expect ABCD)", s3));
        axi_write32(21'h180028, 32'h0);                // disable
        axi_write32(R_CTRL, 32'h5);                    // stop
        // disabled again: IOR returns the scalar, byte-identical to legacy
        axi_write32(R_CTRL, 32'h4);
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);
        bus_cycle(BS_IOR, 20'h00080, 1'b0, 16'h0, s0);
        check(s0 == 16'hABCD, $sformatf("iords disabled -> scalar %04x (expect ABCD)", s0));
        axi_write32(R_CTRL, 32'h5);
    end

    //------------------------------------------------------------------
    // synthetic large-mode trace with scripted queue status, dumped via
    // the bridge for analyzer development (sw/analyze_capture.py --large)
    //------------------------------------------------------------------
    begin
        int fd, cnt;
        axi_write32(R_CTRL, 32'h4);                   // rerun large mode
        while (NEC_RESET !== 1'b1) @(posedge clk);
        while (NEC_RESET) @(posedge NEC_CLK);

        fork
            // queue-status script: F/S consumption with one flush, QS
            // changing at CLK rising edges like the real part
            begin
                localparam bit [1:0] SEQ [0:19] = '{
                    2'b00, 2'b00, 2'b00, 2'b00, 2'b00, 2'b01, 2'b11, 2'b00,
                    2'b01, 2'b11, 2'b11, 2'b00, 2'b01, 2'b10, 2'b00, 2'b00,
                    2'b01, 2'b11, 2'b00, 2'b00};
                for (int i = 0; i < 20; i++) begin
                    @(posedge NEC_CLK); #(TDLY);
                    qs_drv = SEQ[i];
                end
                qs_drv = 2'b00;
            end
            // concurrent code fetches feeding the fictional queue
            begin
                bus_cycle(BS_CODE, 20'h00100, 1'b0, 16'h0, rd);
                bus_cycle(BS_CODE, 20'h00102, 1'b0, 16'h0, rd);
                bus_cycle(BS_CODE, 20'h00104, 1'b0, 16'h0, rd);
                // "jump": non-sequential fetch after the scripted flush
                bus_cycle(BS_CODE, 20'h00200, 1'b0, 16'h0, rd);
                bus_cycle(BS_MEMW, 20'h02200, 1'b0, 16'hBEEF, rd);
            end
        join

        axi_write32(R_CTRL, 32'h5);                   // stop, read trace
        axi_read32(R_CAPCOUNT, w);
        cnt = (w > 128) ? 128 : w;
        fd = $fopen("largemode_synth.hex", "w");
        for (int i = 0; i < cnt; i++) begin
            axi_read_cap(i, rec);
            $fwrite(fd, "%016x\n", rec);
        end
        $fclose(fd);
        $display("wrote %0d large-mode records to largemode_synth.hex", cnt);
    end

    if (errors == 0) $display("ALL TESTS PASSED");
    else $display("%0d TEST(S) FAILED", errors);
    $finish;
end

initial begin
    #8ms;
    $display("FAIL: timeout");
    $finish;
end

endmodule
