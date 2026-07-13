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

    output        NEC_LG_N,     // S/LG strap: 1 = small-scale, 0 = large-scale.
                                // Follows CFG.small_mode so the physical strap
                                // and the harness datapath cannot disagree.
                                // Change only while host_reset is held.

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
wire        cfg_use_core;    // Campaign 4 A/B: 1 = internal v30_core
wire        int_req, nmi_req, poll_n_host;
wire [15:0] cfg_iord;
wire [19:0] evt_addr;
wire [15:0] evt_delay;
wire  [7:0] evt_hold;
wire  [2:0] evt_pin;
wire        evt_arm, evt_fired;

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
    .cfg_use_core(cfg_use_core),
    .int_req(int_req),
    .nmi_req(nmi_req),
    .poll_n_out(poll_n_host),
    .cfg_iord(cfg_iord),
    .evt_addr(evt_addr),
    .evt_delay(evt_delay),
    .evt_hold(evt_hold),
    .evt_pin(evt_pin),
    .evt_arm(evt_arm),
    .evt_fired(evt_fired),

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
// A/B pin mux (Campaign 4). nec_bus talks to a "harness-bus" pin bundle
// (hb_*) that is routed either to the socketed chip (physical NEC_* pins)
// or to the internally instantiated v30_core, selected by cfg_use_core.
//
// Every one-directional signal muxes with a plain 2:1. AD uses nec_bus's
// unidirectional trio (ad_drive / ad_drive_en / ad_sample), so there is no
// inout-to-inout bridge and no combinational loop: the harness read data
// (registered inside nec_bus) drives the selected device's AD, and the
// device's AD is muxed back onto ad_sample. Chip-mode behavior is thus
// bit-identical to the known-good build.
//----------------------------------------------------------------------------
wire [15:0] hb_ad_drive;    // read/INTA data from nec_bus
wire        hb_ad_dir;      // ad_drive_en: 1 = harness driving AD
wire [19:0] hb_ad_sample;   // AD fed back to nec_bus
wire        hb_clk, hb_poll_n, hb_ready, hb_reset, hb_int, hb_nmi, hb_enable_n;
wire  [1:0] hb_qs;
wire  [2:0] hb_bs;
wire        hb_buslock_n, hb_ube_n, hb_rd_n;

// CPU-clock cadence strobes from nec_bus: the internal core runs on the
// fast sys clk but only advances state on these (CE = tick_rise, CE_HALF =
// tick_fall), so it steps on the same sys edges the old core-on-NEC_CLK did.
wire        bus_tick_rise, bus_tick_fall;

// shared internal AD bus for the core (like tb_v30_core's memory-driven AD)
tri  [19:0] core_ad;
wire  [1:0] core_qs;
wire  [2:0] core_bs;
wire        core_rd_n, core_ube_n, core_buslock_n;

//----------------------------------------------------------------------------
// Core-side input pipeline (hold-margin fix, Campaign 4 Mission A2).
//
// The physical chip samples its inputs at its internal clock edge; board
// propagation (FPGA output register + IO + level shifters, ~10-15 ns)
// naturally holds each signal PAST that edge, so the chip always sees the
// pre-edge value. The internal core's CLK posedge derives from the very
// sys-clock edge that updates nec_bus's outputs (drive_en/rdata, RESET,
// READY, INT/NMI/POLL), so in delta-cycle semantics the core would sample
// the POST-edge values with zero hold: it saw RESET released one CPU cycle
// early and lost the read-data race at the T3->T4 sampling edge (the boot
// desync, bringup_log 2026-07-13). Re-registering every nec_bus->core
// input once on the sys clock hands the core the pre-edge value at its
// sampling edge, reproducing the chip's electrical hold margin.
//
// The piped AD drive enable extends one sys clock into T4, so the core's
// own next-address drive can overlap it for that single sys clock on the
// internal net. Harmless: the core samples ad_i only at its CLK posedges
// (a full CPU cycle away) and nec_bus's address/data samples land at
// tick_fall / end-of-cycle strobes, never on the first sys clock of T4
// (cfg_clk_div >= 4).
//
// Core-side only: the physical NEC_* datapath below uses the un-piped
// signals and stays bit-identical to the known-good chip build.
//----------------------------------------------------------------------------
reg        c_ready_q, c_reset_q, c_int_q, c_nmi_q, c_polln_q;
reg [15:0] c_rdata_q;
reg        c_addrv_q;

always_ff @(posedge clk) begin
    c_ready_q <= hb_ready;
    c_reset_q <= hb_reset;
    c_int_q   <= hb_int;
    c_nmi_q   <= hb_nmi;
    c_polln_q <= hb_poll_n;
    c_rdata_q <= hb_ad_drive;
    c_addrv_q <= hb_ad_dir;
end

wire core_reset = c_reset_q | ~cfg_use_core;   // held in reset unless A/B=core

// harness read data driven onto the core's AD[15:0] during its read cycles
assign core_ad[15:0] = c_addrv_q ? c_rdata_q : 16'hzzzz;

v30_core u_core
(
    .CLK       (clk),
    .CE        (bus_tick_rise),
    .CE_HALF   (bus_tick_fall),
    .RESET     (core_reset),
    .READY     (c_ready_q),
    .INT       (c_int_q),
    .NMI       (c_nmi_q),
    .POLL_N    (c_polln_q),
    .AD        (core_ad),
    .QS        (core_qs),
    .BS        (core_bs),
    .RD_N      (core_rd_n),
    .UBE_N     (core_ube_n),
    .BUSLOCK_N (core_buslock_n)
);

// one-directional status pins: chip vs core
assign hb_qs        = cfg_use_core ? core_qs        : NEC_QS;
assign hb_bs        = cfg_use_core ? core_bs        : NEC_BS;
assign hb_rd_n      = cfg_use_core ? core_rd_n      : NEC_RD_N;
assign hb_ube_n     = cfg_use_core ? core_ube_n     : NEC_UBE_N;
assign hb_buslock_n = cfg_use_core ? core_buslock_n : NEC_BUSLOCK_N;

// AD sample fed back to nec_bus, and the physical drive to the chip. No
// feedback loop: NEC_AD's driver (hb_ad_drive) is registered inside nec_bus.
assign hb_ad_sample  = cfg_use_core ? core_ad : NEC_AD;
assign NEC_AD[15:0]  = (!cfg_use_core && hb_ad_dir) ? hb_ad_drive : 16'hzzzz;
assign NEC_AD[19:16] = 4'hz;

// nec_bus outputs fan out to the physical pins (chip) and, via hb_*, the
// core. The chip is powered off while the core is selected.
assign NEC_CLK      = hb_clk;
assign NEC_POLL_N   = hb_poll_n;
assign NEC_READY    = hb_ready;
assign NEC_RESET    = hb_reset;
assign NEC_INT      = hb_int;
assign NEC_NMI      = hb_nmi;
assign NEC_AD_DIR   = hb_ad_dir;
assign NEC_ENABLE_N = hb_enable_n | cfg_use_core;

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

    .evt_arm(evt_arm & ~harness_reset),
    .evt_addr(evt_addr),
    .evt_delay(evt_delay),
    .evt_hold(evt_hold),
    .evt_pin(evt_pin),
    .evt_fired(evt_fired),

    .ad_drive(hb_ad_drive),
    .ad_drive_en(hb_ad_dir),
    .ad_sample(hb_ad_sample),
    .NEC_CLK(hb_clk),
    .NEC_POLL_N(hb_poll_n),
    .NEC_READY(hb_ready),
    .NEC_RESET(hb_reset),
    .NEC_INT(hb_int),
    .NEC_NMI(hb_nmi),
    .NEC_QS(hb_qs),
    .NEC_BS(hb_bs),
    .NEC_BUSLOCK_N(hb_buslock_n),
    .NEC_UBE_N(hb_ube_n),
    .NEC_RD_N(hb_rd_n),
    .NEC_ENABLE_N(hb_enable_n),

    .mem_addr(mem_addr_cpu),
    .mem_cycle_type(mem_cycle_type_cpu),
    .mem_rdata(mem_rdata),
    .mem_wr_req(mem_wr_req_cpu),
    .mem_wdata(mem_wdata_cpu),
    .mem_be(mem_be_cpu),

    .cap_valid(cap_valid),
    .cap_record(cap_record),

    .cpu_running(cpu_running),
    .pwr_good_o(pwr_good),

    .tick_rise_o(bus_tick_rise),
    .tick_fall_o(bus_tick_fall)
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
    .be        (host_owns ? h_mem_be     : mem_be_cpu),
    .cfg_iord  (cfg_iord)
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

assign NEC_LG_N = cfg_small_mode;

assign dbg_led = cap_full;

endmodule
