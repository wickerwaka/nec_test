//============================================================================
//
//  System Large Module - NEC V30 test harness core
//
//  Ties together the max-mode bus interface (nec_bus), the simulated
//  memory (test_mem), the per-cycle trace capture (capture_buf), and the
//  host control bridge (hps_axi_slave on the lightweight HPS-to-FPGA
//  bridge, 2 MB window at ARM physical 0xFF200000 — see hps_axi_slave.sv
//  for the register map).
//
//  Host flow: set CTRL.host_reset, load test memory through the bridge,
//  clear host_reset (with CTRL.skip_pwrup for fast re-runs), poll
//  STATUS/CAPCOUNT, read the capture buffer. Without a host the harness
//  boots standalone with the same defaults as before (small mode, 4 MHz,
//  boot image from boot_even/odd.mif).
//
//  DDRAM is unused until traces outgrow BRAM.
//
//============================================================================

module system_large
(
    input         clk,
    input         reset,

    // DDRAM interface
    output        DDRAM_CLK,
    input         DDRAM_BUSY,
    output  [7:0] DDRAM_BURSTCNT,
    output [28:0] DDRAM_ADDR,
    input  [63:0] DDRAM_DOUT,
    input         DDRAM_DOUT_READY,
    output        DDRAM_RD,
    output [63:0] DDRAM_DIN,
    output  [7:0] DDRAM_BE,
    output        DDRAM_WE,

    // NEC processor interface
    inout  [19:0] NEC_AD,       // 20-bit multiplex address and data bus
    output        NEC_AD_DIR,   // 0 - input, 1 - output
    output        NEC_CLK,      // CPU Clock
    output        NEC_POLL_N,   // CPU Poll input (active low)
    output        NEC_READY,    // Tell the CPU the data on the bus is valid
    output        NEC_RESET,    // CPU Reset
    output        NEC_INT,      // CPU interupt request
    output        NEC_NMI,      // CPU Non-maskable interupt request
    input   [1:0] NEC_QS,       // CPU Queue state
    input   [2:0] NEC_BS,       // CPU Bus state
    input         NEC_BUSLOCK_N,// CPU asserts the bus (active low)
    input         NEC_UBE_N,    // Upper byte is valid in the databus (active low)
    input         NEC_RD_N,     // Current cycle is a read cycle (active_low)
    output        NEC_ENABLE_N, // Power on the CPU (active low)

`ifdef VERILATOR
    // AXI slave exposed to the testbench in place of the HPS primitive
    input      [11:0] axs_awid,
    input      [20:0] axs_awaddr,
    input       [3:0] axs_awlen,
    input             axs_awvalid,
    output            axs_awready,
    input      [31:0] axs_wdata,
    input       [3:0] axs_wstrb,
    input             axs_wvalid,
    input             axs_wlast,
    output            axs_wready,
    output     [11:0] axs_bid,
    output      [1:0] axs_bresp,
    output            axs_bvalid,
    input             axs_bready,
    input      [11:0] axs_arid,
    input      [20:0] axs_araddr,
    input       [3:0] axs_arlen,
    input             axs_arvalid,
    output            axs_arready,
    output     [11:0] axs_rid,
    output     [31:0] axs_rdata,
    output      [1:0] axs_rresp,
    output            axs_rlast,
    output            axs_rvalid,
    input             axs_rready,
`endif

    output        dbg_led       // capture-full status (needs IO board to see)
);

// Bus status encodings shared with nec_bus/test_mem
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_MEMW = 3'b110;

// DDRAM - unused, directly assign to 0
assign {DDRAM_CLK, DDRAM_BURSTCNT, DDRAM_ADDR, DDRAM_DIN, DDRAM_BE, DDRAM_RD, DDRAM_WE} = '0;

//----------------------------------------------------------------------------
// Host bridge
//----------------------------------------------------------------------------
wire        host_reset, cpu_power_off, skip_pwrup;
wire  [5:0] cfg_clk_div;
wire  [3:0] cfg_wait_states;
wire  [7:0] cfg_int_vector;
wire        cfg_small_mode;
wire        int_req, nmi_req, poll_n_host;

wire [19:0] h_mem_addr;
wire        h_mem_wr_req;
wire [15:0] h_mem_wdata;
wire  [1:0] h_mem_be;
wire [11:0] h_cap_addr;
wire [63:0] h_cap_rdata;

wire [19:0] mem_addr_cpu;
wire  [2:0] mem_cycle_type_cpu;
wire [15:0] mem_rdata;
wire        mem_wr_req_cpu;
wire [15:0] mem_wdata_cpu;
wire  [1:0] mem_be_cpu;
wire        cap_valid;
wire [63:0] cap_record;

wire [11:0] axi_awid, axi_arid, axi_bid, axi_rid;
wire [20:0] axi_awaddr, axi_araddr;
wire  [3:0] axi_awlen, axi_arlen;
wire        axi_awvalid, axi_awready, axi_wvalid, axi_wready, axi_wlast;
wire [31:0] axi_wdata, axi_rdata;
wire  [3:0] axi_wstrb;
wire  [1:0] axi_bresp, axi_rresp;
wire        axi_bvalid, axi_bready, axi_arvalid, axi_arready;
wire        axi_rlast, axi_rvalid, axi_rready;

`ifdef VERILATOR
assign axi_awid    = axs_awid;
assign axi_awaddr  = axs_awaddr;
assign axi_awlen   = axs_awlen;
assign axi_awvalid = axs_awvalid;
assign axs_awready = axi_awready;
assign axi_wdata   = axs_wdata;
assign axi_wstrb   = axs_wstrb;
assign axi_wvalid  = axs_wvalid;
assign axi_wlast   = axs_wlast;
assign axs_wready  = axi_wready;
assign axs_bid     = axi_bid;
assign axs_bresp   = axi_bresp;
assign axs_bvalid  = axi_bvalid;
assign axi_bready  = axs_bready;
assign axi_arid    = axs_arid;
assign axi_araddr  = axs_araddr;
assign axi_arlen   = axs_arlen;
assign axi_arvalid = axs_arvalid;
assign axs_arready = axi_arready;
assign axs_rid     = axi_rid;
assign axs_rdata   = axi_rdata;
assign axs_rresp   = axi_rresp;
assign axs_rlast   = axi_rlast;
assign axs_rvalid  = axi_rvalid;
assign axi_rready  = axs_rready;
`else
// Lightweight HPS-to-FPGA bridge, synchronous to clk (the primitive
// handles the clock crossing to the HPS internally).
cyclonev_hps_interface_hps2fpga_light_weight hps_lw
(
    .clk(clk),
    .awid(axi_awid),
    .awaddr(axi_awaddr),
    .awlen(axi_awlen),
    .awvalid(axi_awvalid),
    .awready(axi_awready),
    .wdata(axi_wdata),
    .wstrb(axi_wstrb),
    .wvalid(axi_wvalid),
    .wlast(axi_wlast),
    .wready(axi_wready),
    .bid(axi_bid),
    .bresp(axi_bresp),
    .bvalid(axi_bvalid),
    .bready(axi_bready),
    .arid(axi_arid),
    .araddr(axi_araddr),
    .arlen(axi_arlen),
    .arvalid(axi_arvalid),
    .arready(axi_arready),
    .rid(axi_rid),
    .rdata(axi_rdata),
    .rresp(axi_rresp),
    .rlast(axi_rlast),
    .rvalid(axi_rvalid),
    .rready(axi_rready)
);
`endif

wire        pwr_good;
wire        cpu_running;
wire        cap_full;
wire [12:0] cap_count;

// The bridge must always respond — an unanswered lightweight-bridge access
// hard-locks the ARM. Reset it only by a local power-on pulse, never by the
// MiSTer framework reset (undefined when MiSTer Main isn't running).
reg [3:0] por_cnt = '0;
wire      por = ~&por_cnt;
always_ff @(posedge clk) if (por) por_cnt <= por_cnt + 4'd1;

hps_axi_slave bridge
(
    .clk(clk),
    .reset(por),

    .awid(axi_awid), .awaddr(axi_awaddr), .awlen(axi_awlen),
    .awvalid(axi_awvalid), .awready(axi_awready),
    .wdata(axi_wdata), .wstrb(axi_wstrb), .wvalid(axi_wvalid),
    .wlast(axi_wlast), .wready(axi_wready),
    .bid(axi_bid), .bresp(axi_bresp), .bvalid(axi_bvalid), .bready(axi_bready),
    .arid(axi_arid), .araddr(axi_araddr), .arlen(axi_arlen),
    .arvalid(axi_arvalid), .arready(axi_arready),
    .rid(axi_rid), .rdata(axi_rdata), .rresp(axi_rresp),
    .rlast(axi_rlast), .rvalid(axi_rvalid), .rready(axi_rready),

    .host_attached(host_attached),
    .host_reset(host_reset),
    .cpu_power_off(cpu_power_off),
    .skip_pwrup(skip_pwrup),
    .cfg_clk_div(cfg_clk_div),
    .cfg_wait_states(cfg_wait_states),
    .cfg_int_vector(cfg_int_vector),
    .cfg_small_mode(cfg_small_mode),
    .int_req(int_req),
    .nmi_req(nmi_req),
    .poll_n_out(poll_n_host),

    .pwr_good(pwr_good),
    .cpu_running(cpu_running),
    .cap_full(cap_full),
    .cap_count(cap_count),

    .h_mem_addr(h_mem_addr),
    .h_mem_wr_req(h_mem_wr_req),
    .h_mem_wdata(h_mem_wdata),
    .h_mem_be(h_mem_be),
    .h_mem_rdata(mem_rdata),

    .h_cap_addr(h_cap_addr),
    .h_cap_rdata(h_cap_rdata)
);

// Standalone (no host): the framework reset governs, as always. Once the
// host writes CTRL, it owns the harness lifecycle and the framework reset
// is ignored — it is undefined when MiSTer Main isn't running.
wire host_attached;
wire harness_reset = por | host_reset | (reset & ~host_attached);

//----------------------------------------------------------------------------
// Bus interface
//----------------------------------------------------------------------------
nec_bus bus
(
    .clk(clk),
    .reset(harness_reset),

    .cfg_small_mode(cfg_small_mode),
    .cfg_cpu_off(cpu_power_off),
    .cfg_short_pwrup(skip_pwrup),
    .cfg_clk_div(cfg_clk_div),
    .cfg_wait_states(cfg_wait_states),
    .cfg_int_vector(cfg_int_vector),

    .int_req(int_req),
    .nmi_req(nmi_req),
    .poll_n_in(poll_n_host),

    .NEC_AD(NEC_AD),
    .NEC_AD_DIR(NEC_AD_DIR),
    .NEC_CLK(NEC_CLK),
    .NEC_POLL_N(NEC_POLL_N),
    .NEC_READY(NEC_READY),
    .NEC_RESET(NEC_RESET),
    .NEC_INT(NEC_INT),
    .NEC_NMI(NEC_NMI),
    .NEC_QS(NEC_QS),
    .NEC_BS(NEC_BS),
    .NEC_BUSLOCK_N(NEC_BUSLOCK_N),
    .NEC_UBE_N(NEC_UBE_N),
    .NEC_RD_N(NEC_RD_N),
    .NEC_ENABLE_N(NEC_ENABLE_N),

    .mem_addr(mem_addr_cpu),
    .mem_cycle_type(mem_cycle_type_cpu),
    .mem_rdata(mem_rdata),
    .mem_wr_req(mem_wr_req_cpu),
    .mem_wdata(mem_wdata_cpu),
    .mem_be(mem_be_cpu),

    .cap_valid(cap_valid),
    .cap_record(cap_record),

    .cpu_running(cpu_running),
    .pwr_good_o(pwr_good)
);

//----------------------------------------------------------------------------
// Simulated memory. The host owns the port while it holds the harness in
// reset; the CPU-side signals are inert then (nec_bus is reset).
//----------------------------------------------------------------------------
wire host_owns = host_reset;

test_mem mem
(
    .clk(clk),
    .addr      (host_owns ? h_mem_addr   : mem_addr_cpu),
    .cycle_type(host_owns ? (h_mem_wr_req ? BS_MEMW : BS_MEMR) : mem_cycle_type_cpu),
    .rdata(mem_rdata),
    .wr_req    (host_owns ? h_mem_wr_req : mem_wr_req_cpu),
    .wdata     (host_owns ? h_mem_wdata  : mem_wdata_cpu),
    .be        (host_owns ? h_mem_be     : mem_be_cpu)
);

//----------------------------------------------------------------------------
// Trace capture: arms when the CPU comes out of reset, records every CPU
// cycle until full. The bridge reads it; JTAG (ISMCE instance CAPT)
// remains as a fallback path.
//----------------------------------------------------------------------------
// POR only: the trace must survive host_reset (host reads it afterwards)
// and must not depend on the framework reset
capture_buf #(.LOG2_DEPTH(12)) capture
(
    .clk(clk),
    .reset(por),
    .arm(pwr_good),      // record the tail of the reset sequence too
    .wr_valid(cap_valid),
    .wr_data(cap_record),
    .full(cap_full),
    .count(cap_count),
    .rd_addr(h_cap_addr),
    .rd_data(h_cap_rdata)
);

assign dbg_led = cap_full;

endmodule
