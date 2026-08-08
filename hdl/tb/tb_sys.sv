//============================================================================
//
//  tb_sys - THE VERILATED FABRIC.  system_large, driven exactly the way the
//  ARM drives it on the board, running an ARBITRARY image.
//
//  Why it exists (X1 / ucore_provenance.md §56.3a).  Two Verilator harnesses
//  already existed and NEITHER can ask X1's question:
//
//    tb_v30_core  the core ALONE, with a testbench memory that MODELS PAD
//                 RETENTION (`eff_lo`/`eff_hi`, §R.2).  It is where the 259/283
//                 offline HLT-sweep number comes from -- and it can never see
//                 the fabric's 116 INTA cells, because it retains.
//    tb_ab        system_large, but a FIXED boot image, no event scheduler and
//                 no image load: a 187-row boot-vs-golden gate and nothing more.
//
//  X1 is a claim about the INTEGRATION -- `core_ad` is an internal net with no
//  keeper where the part has pads that float and retain.  Testing it offline
//  needs system_large driven with a real program, a real pin-event directive
//  and the real capture path.  That is this file.  It runs `use_core=1` only;
//  the socketed-chip position has no meaning without a socket.
//
//  Plusargs
//    +img=<file>     64 KiB image, one hex BYTE per line (testimage.compose
//                    output; the harness memory is 64 KiB mirrored to 1 MiB)
//    +cap=<file>     output: one 64-bit capture record per line, hex, the SAME
//                    words `sw/analyze_capture.py::decode_words` parses off the
//                    board.  Nothing here re-formats them.
//    +ncap=<n>       capture records to drain (default 2048 = emit_suite.EMIT_CAP)
//    +waits=<n>      CFG.wait_states
//    +div=<n>        CFG.clk_div (default 8 = emit_suite.EMIT_DIV / DIV_OF_RECORD)
//    +evpin=<p>      arm the pin-event scheduler: 0=INT 1=NMI 2=POLL_N
//    +evaddr=<hex>   its 20-bit fetch-trigger linear address
//    +evdelay=<n>    its delay in CPU clocks
//    +evhold=<n>     its hold in CPU clocks (12-bit register since 2026-08-04)
//    +pins=<hex>     static PINS register ([0] INT [1] NMI [2] POLL_N)
//
//  Plusargs added for the fuzz-v2 rig RTL (EVT_N = 3 schedulers + the NMI
//  vector-read overlay).  There is ONE packer -- `arm_evt` below -- for all
//  three register pairs, because the host packs one layout for all three and a
//  forked packer on either side of the wire is how INV-1 happened.
//    +ev2pin/+ev2addr/+ev2delay/+ev2hold   scheduler 1 (EVT2_* at 0x30/0x34)
//    +ev3pin/+ev3addr/+ev3delay/+ev3hold   scheduler 2 (EVT3_* at 0x38/0x3C)
//    +tvec=<hex>     TVEC   (0x40): [15:0] IP, [31:16] CS -- the words served
//                    for the NMI vector reads at linear 0x00008 / 0x0000A
//    +vecctl=<hex>   VECCTL (0x44): [2:0] vecsub_en, bit n = scheduler n's
//                    FIRE arms the overlay.  A property of WHICH DIRECTIVE
//                    FIRED, not of which pin went high, which is the only
//                    formulation under which a stimulus NMI and a terminating
//                    NMI coexist in one run.
//  TVEC and VECCTL are written ONLY when their plusarg is present, so an
//  invocation that names neither issues byte-identical AXI traffic to the
//  pre-EVT_N harness -- which is what makes the inertness claim checkable
//  (sw/fz2_tbsys.py inert) rather than asserted.
//
//  Every register this file writes is READ BACK and compared before the run.
//  INV-1's root cause was the rig silently applying a directive other than the
//  one it was handed; the readback is what makes that a $fatal instead of a
//  finding six days later.
//
//  Built and run by sw/x1_retention.py.  Define X1_AD_RETENTION at build time
//  to compile system_large's §56.3a retention model in; the two builds differ
//  by that define and by nothing else.
//
//============================================================================

`timescale 1ns/1ps

module tb_sys;

// register map (hdl/rtl/hps_axi_slave.sv)
localparam bit [20:0] A_MEM      = 21'h000000;
localparam bit [20:0] A_CAP      = 21'h100000;
localparam bit [20:0] R_MAGIC    = 21'h180000;
localparam bit [20:0] R_CTRL     = 21'h180004;
localparam bit [20:0] R_CFG      = 21'h180008;
localparam bit [20:0] R_PINS     = 21'h18000C;
localparam bit [20:0] R_STATUS   = 21'h180010;
localparam bit [20:0] R_CAPCOUNT = 21'h180014;
localparam bit [20:0] R_EVT_ADDR = 21'h18001C;
localparam bit [20:0] R_EVT_CFG  = 21'h180020;
// fuzz-v2: schedulers 1 and 2 sit at 0x30 + 8*(n-1); scheduler 0 keeps its
// historical offsets, so a run that arms only it is bit-for-bit unchanged.
localparam bit [20:0] R_EVT2_ADDR = 21'h180030;
localparam bit [20:0] R_EVT2_CFG  = 21'h180034;
localparam bit [20:0] R_EVT3_ADDR = 21'h180038;
localparam bit [20:0] R_EVT3_CFG  = 21'h18003C;
localparam bit [20:0] R_TVEC      = 21'h180040;
localparam bit [20:0] R_VECCTL    = 21'h180044;

logic clk = 0;
logic reset = 1;
always #15.625 clk = ~clk;   // 32 MHz, the board's sys clock

// NEC pins.  The socket is EMPTY in this harness: use_core=1 always, the
// chip is powered off by system_large (`NEC_ENABLE_N = hb_enable_n |
// cfg_use_core`), and nothing drives the physical AD.
wire  [19:0] NEC_AD;
wire         NEC_AD_DIR, NEC_CLK, NEC_POLL_N, NEC_READY, NEC_RESET;
wire         NEC_INT, NEC_NMI, NEC_ENABLE_N;
logic  [1:0] qs_drv = 2'b00;
logic  [2:0] bs_drv = 3'b111;              // PASV
logic        buslock_n_drv = 1'b1, ube_n_drv = 1'b1, rd_n_drv = 1'b1;

assign NEC_AD[15:0]  = 16'hzzzz;
assign NEC_AD[19:16] = 4'hz;

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

//----------------------------------------------------------------------------
// AXI master BFM (the same handshake discipline as tb_ab / tb_harness)
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
// ONE packer for all EVT_N register pairs, mirroring the register writes
// sw/v30ctl.py performs.  EVT_CFG's hold is SPLIT: [23:16] low 8 bits,
// [30:27] high 4 -- the 12-bit widen of 2026-08-04 (F46 / gap R1).
//
// It READS BACK what it wrote and $fatals on a mismatch.  Every bit of the
// CFG word is spoken for, so an exact compare is the right compare.
//----------------------------------------------------------------------------
task automatic arm_evt(input bit [20:0] a_addr, input bit [20:0] a_cfg,
                       input string nm,
                       input integer ea, input integer ed,
                       input integer eh, input integer ep);
    bit [31:0] cfgv, wanta, rba, rbc;
    wanta = 32'(ea) & 32'h000FFFFF;
    axi_write32(a_addr, wanta);
    cfgv        = 32'h0;
    cfgv[15:0]  = ed[15:0];
    cfgv[23:16] = eh[7:0];
    cfgv[26:24] = ep[2:0];
    cfgv[30:27] = eh[11:8];
    cfgv[31]    = 1'b1;                          // arm
    axi_write32(a_cfg, cfgv);
    axi_read32(a_addr, rba);
    axi_read32(a_cfg,  rbc);
    $display("SYS EVT %s ADDR=%08x CFG=%08x  readback ADDR=%08x CFG=%08x",
             nm, wanta, cfgv, rba, rbc);
    if (rba !== wanta)
        $fatal(1, "%s ADDR readback %08x != %08x", nm, rba, wanta);
    if (rbc !== cfgv)
        $fatal(1, "%s CFG readback %08x != %08x", nm, rbc, cfgv);
endtask

// EXACT readback compare, deliberately.  VECCTL stores only EVT_N bits, so
// +vecctl=8 (a fourth scheduler that does not exist) $fatals here rather than
// running with a silently narrowed directive -- which is INV-1's shape.
task automatic wr_verify(input bit [20:0] a, input bit [31:0] d,
                         input string nm);
    bit [31:0] rb;
    axi_write32(a, d);
    axi_read32(a, rb);
    $display("SYS REG %s=%08x  readback %08x", nm, d, rb);
    if (rb !== d) $fatal(1, "%s readback %08x != %08x", nm, rb, d);
endtask

//----------------------------------------------------------------------------
// test sequence
//----------------------------------------------------------------------------
localparam int IMG_BYTES = 65536;          // test_mem is 64 KiB, mirrored

byte unsigned img [0:IMG_BYTES-1];
string img_path, cap_path;
integer ncap, waits, divv, evpin, evdelay, evhold, pinsr;
integer fd, cnt, i, evaddr;
bit [31:0] w, cfgw;
bit [63:0] rec;
bit        armed;
// fuzz-v2: schedulers 1 and 2, and the NMI vector-read overlay
integer evpin2, evdelay2, evhold2, evaddr2;
integer evpin3, evdelay3, evhold3, evaddr3;
bit        armed2, armed3;
integer    tvecv, vecctlv;
bit        havetvec, havevecctl;
// STATUS is LATCHED while the run is live: evt_fired and vec_used live in
// nec_bus and are cleared by the harness reset that CTRL's stop asserts, so
// read after the stop they are always 0.
bit  [2:0] fired;        // STATUS[5:3], one bit per scheduler
bit        vecused;      // STATUS[6], sticky "the overlay served a CS half"
bit        capfull;      // STATUS[2]

initial begin
    if (!$value$plusargs("img=%s", img_path))  $fatal(1, "+img required");
    if (!$value$plusargs("cap=%s", cap_path))  cap_path = "sys_cap.hex";
    if (!$value$plusargs("ncap=%d", ncap))     ncap  = 2048;
    if (!$value$plusargs("waits=%d", waits))   waits = 0;
    if (!$value$plusargs("div=%d", divv))      divv  = 8;
    if (!$value$plusargs("pins=%h", pinsr))    pinsr = 0;
    armed = $value$plusargs("evpin=%d", evpin);
    if (!$value$plusargs("evaddr=%h", evaddr))   evaddr  = 0;
    if (!$value$plusargs("evdelay=%d", evdelay)) evdelay = 0;
    if (!$value$plusargs("evhold=%d", evhold))   evhold  = 0;

    armed2 = $value$plusargs("ev2pin=%d", evpin2);
    if (!$value$plusargs("ev2addr=%h", evaddr2))   evaddr2  = 0;
    if (!$value$plusargs("ev2delay=%d", evdelay2)) evdelay2 = 0;
    if (!$value$plusargs("ev2hold=%d", evhold2))   evhold2  = 0;

    armed3 = $value$plusargs("ev3pin=%d", evpin3);
    if (!$value$plusargs("ev3addr=%h", evaddr3))   evaddr3  = 0;
    if (!$value$plusargs("ev3delay=%d", evdelay3)) evdelay3 = 0;
    if (!$value$plusargs("ev3hold=%d", evhold3))   evhold3  = 0;

    havetvec   = $value$plusargs("tvec=%h", tvecv);
    havevecctl = $value$plusargs("vecctl=%h", vecctlv);
    if (!havetvec)   tvecv   = 0;
    if (!havevecctl) vecctlv = 0;

    for (i = 0; i < IMG_BYTES; i++) img[i] = 8'h00;
    $readmemh(img_path, img);

    repeat (4) @(posedge clk);
    reset = 0;

    axi_read32(R_MAGIC, w);
    if (w !== 32'h56333031) $fatal(1, "bridge magic %08x", w);

    // HOST RESET.  The test-memory port is only valid while host_reset is set
    // (hps_axi_slave.sv), which is the board's own load discipline.
    axi_write32(R_CTRL, 32'h5);                 // host_reset | skip_pwrup

    // CFG: large mode, the internal core, the emitter's pinned divider and the
    // harness INT vector default (0xFF -- hps_axi_slave's reset value, which is
    // what `ServeRunner.cfg` LEAVES ALONE when it sends `-` for the vector).
    cfgw = 32'h0000_0000;
    cfgw[5:0]   = divv[5:0];
    cfgw[11:8]  = waits[3:0];
    cfgw[23:16] = 8'hFF;
    cfgw[24]    = 1'b0;                          // small_mode = 0 (large)
    cfgw[25]    = 1'b1;                          // use_core   = 1
    axi_write32(R_CFG, cfgw);
    axi_write32(R_PINS, 32'(pinsr));

    // the image, through the bridge -- two 16-bit memory words per beat
    for (i = 0; i < IMG_BYTES; i = i + 4)
        axi_write32(A_MEM + 21'(i), {img[i+3], img[i+2], img[i+1], img[i]});

    // the pin-event schedulers, one packer each (see arm_evt above)
    if (armed)
        arm_evt(R_EVT_ADDR,  R_EVT_CFG,  "EVT ", evaddr,  evdelay,
                evhold,  evpin);
    if (armed2)
        arm_evt(R_EVT2_ADDR, R_EVT2_CFG, "EVT2", evaddr2, evdelay2,
                evhold2, evpin2);
    if (armed3)
        arm_evt(R_EVT3_ADDR, R_EVT3_CFG, "EVT3", evaddr3, evdelay3,
                evhold3, evpin3);

    // the NMI vector-read overlay.  WRITTEN ONLY IF ASKED FOR: their reset
    // value is 0 and a run that names neither must issue the same AXI traffic
    // as the pre-EVT_N harness, which is the inertness claim.
    if (havetvec)   wr_verify(R_TVEC,   32'(tvecv),   "TVEC");
    if (havevecctl) wr_verify(R_VECCTL, 32'(vecctlv), "VECCTL");

    axi_write32(R_CTRL, 32'h4);                  // run (skip_pwrup)

    // run until the capture buffer holds what we asked for, or the watchdog
    // fires.  The capture is one record per CPU clock, so this is bounded.
    // `evt_fired` lives in nec_bus and is cleared by the harness reset that
    // CTRL's stop asserts, so it is LATCHED here while the run is live.  Read
    // after the stop it is always 0, and `emit_suite` treats that as
    // "event did not fire" and throws the case away.
    cnt = 0; fired = 3'b000; vecused = 1'b0; capfull = 1'b0;
    while (cnt <= ncap) begin
        repeat (64) @(posedge clk);
        axi_read32(R_STATUS, w);
        fired |= w[5:3];                         // one bit per scheduler
        if (w[6]) vecused = 1'b1;                // NMI overlay served
        if (w[2]) capfull = 1'b1;
        axi_read32(R_CAPCOUNT, w);
        cnt = int'(w);
        // the buffer STOPS when full and its count stops with it, so `cnt`
        // alone can never end this loop once ncap exceeds the depth.  It used
        // to test `cnt >= 8191` against a buffer system_large instantiates
        // 4096 deep, i.e. never, and +ncap above the depth hung until the
        // watchdog.  cap_full is the harness's own statement that there is no
        // more trace coming, and it needs no depth constant here.
        if (capfull) break;
    end
    axi_read32(R_STATUS, w);
    fired |= w[5:3];
    if (w[6]) vecused = 1'b1;
    axi_write32(R_CTRL, 32'h5);                  // stop

    axi_read32(R_CAPCOUNT, w);
    cnt = (int'(w) > ncap) ? ncap : int'(w);

    fd = $fopen(cap_path, "w");
    for (i = 0; i < cnt; i++) begin
        axi_read_cap(i, rec);
        $fwrite(fd, "%016x\n", rec);
    end
    $fclose(fd);
    // `fired` is now a MASK, one bit per scheduler.  With only scheduler 0
    // armed -- every historical invocation, x1_retention.py included -- it is
    // 0 or 1 exactly as before, so `SYS DONE ... fired=(\d)` still means what
    // it meant.
    $display("SYS DONE %0d records fired=%0d vecused=%0d",
             cnt, fired, vecused);
    $finish;
end


initial begin
    #400ms;
    $display("FATAL: timeout");
    $finish;
end

endmodule
