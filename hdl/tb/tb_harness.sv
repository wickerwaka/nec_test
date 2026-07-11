//============================================================================
//
//  tb_harness - smoke test for nec_bus + test_mem + capture_buf
//
//  A crude V30 bus-functional model drives the status/address pins with
//  datasheet-shaped max-mode bus cycles and checks that:
//    - the reset sequence holds RESET for >= 4 CPU clocks
//    - a code fetch at FFFF0h returns the reset-vector bytes (EA 00)
//    - a word write to 02000h lands in memory and reads back
//    - the capture buffer records cycles
//
//  Run: verilator --binary --timing -Ihdl/rtl hdl/tb/tb_harness.sv \
//         hdl/rtl/nec_bus.sv hdl/rtl/test_mem.sv hdl/rtl/capture_buf.sv
//
//============================================================================

`timescale 1ns/1ps

module tb_harness;

localparam bit [2:0] BS_IOR  = 3'b001;
localparam bit [2:0] BS_CODE = 3'b100;
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_MEMW = 3'b110;
localparam bit [2:0] BS_PASV = 3'b111;

logic clk = 0;
logic reset = 1;
always #15.625 clk = ~clk;   // 32 MHz

// DUT pins
wire  [19:0] NEC_AD;
wire         NEC_AD_DIR, NEC_CLK, NEC_POLL_N, NEC_READY, NEC_RESET;
wire         NEC_INT, NEC_NMI, NEC_ENABLE_N;
logic  [1:0] qs_drv = 2'b10;   // small-mode idle: {INTAK=1, ASTB=0}
logic  [2:0] bs_drv = BS_PASV;
logic        buslock_n_drv = 1'b1, ube_n_drv = 1'b1, rd_n_drv = 1'b1;
logic        small_mode = 0;

// BFM drive of the muxed bus: address phase drives all 20 bits, data phase
// (writes) drives 15:0; A19:16 are CPU-driven at all times on real hardware.
// NOTE: keep each continuous assign a simple `en ? val : 'z` — Verilator's
// tristate support silently mishandles nested ternaries.
logic [19:0] ad_drv = '0;
logic        ad_addr_en = 0;   // BFM driving address (T1)
logic        ad_data_en = 0;   // BFM driving write data (T2-T4)
wire         tb_ad_en = ad_addr_en | ad_data_en;
assign NEC_AD[15:0]  = tb_ad_en   ? ad_drv[15:0]  : 16'hzzzz;
assign NEC_AD[19:16] = ad_addr_en ? ad_drv[19:16] : 4'hz;

wire [19:0] mem_addr;
wire  [2:0] mem_cycle_type;
wire [15:0] mem_rdata;
wire        mem_wr_req;
wire [15:0] mem_wdata;
wire  [1:0] mem_be;
wire        cap_valid;
wire [63:0] cap_record;
wire        cpu_running;

nec_bus dut
(
    .clk(clk), .reset(reset),
    .cfg_small_mode(small_mode),
    .cfg_clk_div(6'd8), .cfg_wait_states(4'd0), .cfg_int_vector(8'hFF),
    .int_req(1'b0), .nmi_req(1'b0), .poll_n_in(1'b0),
    .NEC_AD(NEC_AD), .NEC_AD_DIR(NEC_AD_DIR), .NEC_CLK(NEC_CLK),
    .NEC_POLL_N(NEC_POLL_N), .NEC_READY(NEC_READY), .NEC_RESET(NEC_RESET),
    .NEC_INT(NEC_INT), .NEC_NMI(NEC_NMI),
    .NEC_QS(qs_drv), .NEC_BS(bs_drv),
    .NEC_BUSLOCK_N(buslock_n_drv), .NEC_UBE_N(ube_n_drv), .NEC_RD_N(rd_n_drv),
    .NEC_ENABLE_N(NEC_ENABLE_N),
    .mem_addr(mem_addr), .mem_cycle_type(mem_cycle_type), .mem_rdata(mem_rdata),
    .mem_wr_req(mem_wr_req), .mem_wdata(mem_wdata), .mem_be(mem_be),
    .cap_valid(cap_valid), .cap_record(cap_record),
    .cpu_running(cpu_running),
    .pwr_good_o()
);

test_mem #(.INIT_EVEN_SIM("hdl/rtl/boot_even.hex"), .INIT_ODD_SIM("hdl/rtl/boot_odd.hex")) mem
(
    .clk(clk),
    .addr(mem_addr), .cycle_type(mem_cycle_type), .rdata(mem_rdata),
    .wr_req(mem_wr_req), .wdata(mem_wdata), .be(mem_be)
);

wire         cap_full;
wire [12:0]  cap_count;
wire [63:0]  cap_rd_data;

capture_buf #(.LOG2_DEPTH(12)) capture
(
    .clk(clk), .reset(reset),
    .arm(cpu_running), .wr_valid(cap_valid), .wr_data(cap_record),
    .full(cap_full), .count(cap_count),
    .rd_addr(12'd0), .rd_data(cap_rd_data)
);

int errors = 0;

task automatic check(input bit cond, input string msg);
    if (!cond) begin
        errors++;
        $display("FAIL: %s (t=%0t)", msg, $time);
    end else begin
        $display("pass: %s", msg);
    end
endtask

// Delay CPU-output transitions from CLK edges like the real part
// (10-65 ns + 10 ns shifters; use ~40 ns as a representative value).
localparam realtime TDLY = 40ns;

// One max-mode bus cycle, as the CPU would run it
task automatic bus_cycle(
    input bit [2:0]  btype,
    input bit [19:0] addr,
    input bit        ube_n,
    input bit [15:0] wdata,
    output bit [15:0] rdata
);
    // status goes active mid-TI/T4 (after a CLK rising edge)
    @(posedge NEC_CLK); #(TDLY);
    bs_drv = btype;
    // T1: drive address
    @(posedge NEC_CLK); #(TDLY);
    ad_drv = addr; ube_n_drv = ube_n; ad_addr_en = 1;
    // T2: float address; reads assert RD, writes drive data
    @(posedge NEC_CLK); #(TDLY);
    ad_addr_en = 0;
    if (btype == BS_MEMW) begin
        ad_drv = {4'h0, wdata}; ad_data_en = 1;
    end else begin
        rd_n_drv = 0;
    end
    // T3: status returns passive; CPU samples read data at CLK falling edge
    @(posedge NEC_CLK); #(TDLY);
    bs_drv = BS_PASV;
    @(negedge NEC_CLK);
    rdata = NEC_AD[15:0];
    // T4: release everything
    @(posedge NEC_CLK); #(TDLY);
    ad_data_en = 0; rd_n_drv = 1; ube_n_drv = 1;
    @(posedge NEC_CLK);
endtask

// Small-scale mode bus cycle: ASTB address strobe, RD/WR strobes.
// bs_drv[2] carries IO/M (1 = memory), qs_drv = {INTAK, ASTB},
// buslock_n_drv carries WR.
task automatic small_bus_cycle(
    input bit        is_write,
    input bit        is_io,
    input bit [19:0] addr,
    input bit        ube_n,
    input bit [15:0] wdata,
    output bit [15:0] rdata
);
    // T1: raise ASTB with the address; IO/M valid with address
    @(posedge NEC_CLK); #(TDLY);
    ad_drv = addr; ube_n_drv = ube_n; ad_addr_en = 1;
    bs_drv[2] = ~is_io;
    qs_drv[0] = 1;
    @(negedge NEC_CLK); #(TDLY);
    qs_drv[0] = 0;                       // ASTB falls: address latched
    // T2: float address, assert strobe
    @(posedge NEC_CLK); #(TDLY);
    ad_addr_en = 0;
    if (is_write) begin
        ad_drv = {4'h0, wdata}; ad_data_en = 1;
        buslock_n_drv = 0;               // WR low
    end else begin
        rd_n_drv = 0;
    end
    // T3: CPU samples read data at the falling edge
    @(posedge NEC_CLK);
    @(negedge NEC_CLK);
    rdata = NEC_AD[15:0];
    // T4: raise strobes; the CPU holds write data past the WR rising edge
    @(posedge NEC_CLK); #(TDLY);
    rd_n_drv = 1; buslock_n_drv = 1;
    #(TDLY);
    ad_data_en = 0; ube_n_drv = 1;
    @(posedge NEC_CLK);
endtask

bit [15:0] rd;
int reset_clks;

// accumulate strobe bits seen in capture records during the small phase
bit rec_astb = 0, rec_rd = 0, rec_wr = 0;
always @(posedge clk) if (small_mode && cap_valid) begin
    rec_astb |= cap_record[46];
    rec_rd   |= ~cap_record[48];
    rec_wr   |= ~cap_record[50];
end

bit dbg = 0;
always @(posedge NEC_CLK) if (dbg)
    $display("  t=%0t state=%0d bs_pin=%b ad_pin=%05x addr=%05x ctype=%b drv=%b rdata=%04x",
             $time, dut.t_state, bs_drv, NEC_AD, mem_addr, mem_cycle_type, NEC_AD_DIR, mem_rdata);

initial begin
    // release sys reset
    repeat (4) @(posedge clk);
    reset = 0;

    // count CPU clocks while NEC_RESET high
    reset_clks = 0;
    while (NEC_RESET) begin
        @(posedge NEC_CLK);
        reset_clks++;
        if (reset_clks > 1000) break;
    end
    check(reset_clks >= 4, $sformatf("RESET held %0d CPU clocks (>=4)", reset_clks));
    check(!NEC_ENABLE_N, "CPU enabled");
    check(NEC_READY, "READY idles high");

    // code fetch at reset vector FFFF0h -> word 00EAh (EA low byte, 00 high)
    dbg = 1;
    bus_cycle(BS_CODE, 20'hFFFF0, 1'b0, 16'h0, rd);
    dbg = 0;
    check(rd == 16'h00EA, $sformatf("reset-vector fetch returned %04x (expect 00EA)", rd));

    // word write to 02000h, then read back
    bus_cycle(BS_MEMW, 20'h02000, 1'b0, 16'h1234, rd);
    bus_cycle(BS_MEMR, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'h1234, $sformatf("write/readback at 02000h returned %04x (expect 1234)", rd));

    // odd byte write (A0=1, UBE_N=0 -> high lane only), verify merge
    bus_cycle(BS_MEMW, 20'h02001, 1'b0, 16'hAB00, rd);
    bus_cycle(BS_MEMR, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'hAB34, $sformatf("odd-byte write merge returned %04x (expect AB34)", rd));

    // I/O read returns 0
    bus_cycle(BS_IOR, 20'h00080, 1'b0, 16'h0, rd);
    check(rd == 16'h0000, $sformatf("io read returned %04x (expect 0000)", rd));

    // capture buffer is recording
    check(cap_count > 0, $sformatf("capture count %0d > 0", cap_count));

    //------------------------------------------------------------------
    // Small-scale mode phase: reset, switch modes, repeat the checks
    //------------------------------------------------------------------
    reset = 1;
    small_mode = 1;
    bs_drv = BS_PASV; qs_drv = 2'b10; rd_n_drv = 1; buslock_n_drv = 1;
    repeat (4) @(posedge clk);
    reset = 0;
    while (NEC_RESET) @(posedge NEC_CLK);
    $display("-- small-scale mode --");

    // code/memory fetch at reset vector
    small_bus_cycle(0, 0, 20'hFFFF0, 1'b0, 16'h0, rd);
    check(rd == 16'h00EA, $sformatf("sm: vector fetch returned %04x (expect 00EA)", rd));

    // word write + readback
    small_bus_cycle(1, 0, 20'h02000, 1'b0, 16'h5678, rd);
    small_bus_cycle(0, 0, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'h5678, $sformatf("sm: write/readback returned %04x (expect 5678)", rd));

    // odd byte write merges into the high lane
    small_bus_cycle(1, 0, 20'h02001, 1'b0, 16'hCD00, rd);
    small_bus_cycle(0, 0, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'hCD78, $sformatf("sm: odd-byte merge returned %04x (expect CD78)", rd));

    // I/O read returns 0, and the write must NOT hit memory
    small_bus_cycle(1, 1, 20'h02000, 1'b0, 16'hBEEF, rd);
    small_bus_cycle(0, 1, 20'h00080, 1'b0, 16'h0, rd);
    check(rd == 16'h0000, $sformatf("sm: io read returned %04x (expect 0000)", rd));
    small_bus_cycle(0, 0, 20'h02000, 1'b0, 16'h0, rd);
    check(rd == 16'hCD78, $sformatf("sm: io write left memory %04x (expect CD78)", rd));

    // sticky strobe bits made it into capture records
    check(rec_astb, "sm: capture records contain ASTB pulses");
    check(rec_rd,   "sm: capture records contain RD strobes");
    check(rec_wr,   "sm: capture records contain WR strobes");

    if (errors == 0) $display("ALL TESTS PASSED");
    else $display("%0d TEST(S) FAILED", errors);
    $finish;
end

initial begin
    #4ms;
    $display("FAIL: timeout");
    $finish;
end

endmodule
