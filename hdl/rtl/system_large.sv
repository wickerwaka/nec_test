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

// THE number of pin-event schedulers.  One localparam, passed to both the
// bridge and the bus, so the register map and the hardware cannot disagree.
// Compile-time only: nothing the host writes can change it.
localparam int EVT_N = 3;

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
wire        cfg_wait_rand;   // Phase 1 rig: seeded random per-access waits
wire  [3:0] cfg_wmax;
wire [15:0] cfg_wseed;
wire        cfg_wait_replay; // Phase 2a: replay host wait-vector
wire  [9:0] h_wvec_addr;     // wvec RAM host write port
wire        h_wvec_wr;
wire [31:0] h_wvec_wdata;
wire  [9:0] wvec_raddr;      // wvec RAM bus read port (nec_bus)
wire [31:0] wvec_rdata;
wire        int_req, nmi_req, poll_n_host;
wire [15:0] cfg_iord;
// iords sequence buffer (INS / REP INS per-element port serving)
wire  [5:0] h_iords_addr;    // iords buf host write port
wire        h_iords_wr;
wire [15:0] h_iords_wdata;
wire  [6:0] cfg_iords_cnt;   // number of loaded entries
wire        cfg_iords_en;    // serve the sequence on IOR cycles
wire  [6:0] iords_raddr;     // IOR read index from nec_bus
wire [15:0] iords_rdata;     // buffered value at that index
// serve mux: the sequenced value while enabled and in range, else the scalar
// cfg_iord (IN forms E4/E5/EC/ED and any disabled run are byte-identical).
wire        iords_active = cfg_iords_en && (iords_raddr < cfg_iords_cnt);
wire [15:0] iord_eff     = iords_active ? iords_rdata : cfg_iord;
// Pin-event schedulers, EVT_N packed slices per field (see nec_bus.sv)
wire [EVT_N*20-1:0] evt_addr;
wire [EVT_N*16-1:0] evt_delay;
wire [EVT_N*12-1:0] evt_hold;   // 12 b/slice since 2026-08-04 (F46 / gap R1)
wire [EVT_N*3-1:0]  evt_pin;
wire [EVT_N-1:0]    evt_arm, evt_fired, evt_vecsub_en;
// NMI vector-read overlay (fuzz v2 terminator)
wire [31:0] cfg_tvec;
wire        vec_used;

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

hps_axi_slave #(.EVT_N(EVT_N)) bridge
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
    .cfg_wait_rand(cfg_wait_rand),
    .cfg_wmax(cfg_wmax),
    .cfg_wseed(cfg_wseed),
    .cfg_wait_replay(cfg_wait_replay),
    .h_wvec_addr(h_wvec_addr),
    .h_wvec_wr(h_wvec_wr),
    .h_wvec_wdata(h_wvec_wdata),
    .h_iords_addr(h_iords_addr),
    .h_iords_wr(h_iords_wr),
    .h_iords_wdata(h_iords_wdata),
    .cfg_iords_cnt(cfg_iords_cnt),
    .cfg_iords_en(cfg_iords_en),
    .int_req(int_req),
    .nmi_req(nmi_req),
    .poll_n_out(poll_n_host),
    .cfg_iord(cfg_iord),
    .evt_addr(evt_addr),
    .evt_delay(evt_delay),
    .evt_hold(evt_hold),
    .evt_pin(evt_pin),
    .evt_arm(evt_arm),
    .evt_vecsub_en(evt_vecsub_en),
    .cfg_tvec(cfg_tvec),
    .evt_fired(evt_fired),
    .vec_used(vec_used),

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
wire [19:0] core_ad_oe;      // the core's OWN pad output enable (task #37)
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
`ifdef SYNTHESIS
wire [15:0] core_ss_rdata_unused;
`else
wire [15:0] core_ss_rdata;      // M10-SYS probe reads it (see the block below)
`endif
wire        core_ss_err_unused;
wire        core_ss_bus_quiet_unused;

`ifndef SYNTHESIS
//----------------------------------------------------------------------------
// M10-SYS -- THE SAVE-STATE FREEZE PROBE.  SIMULATION ONLY, AND THE GUARD IS
// THE PROOF: both QSFs set `VERILOG_MACRO "SYNTHESIS=1"`
// (hdl/nec_test_ucore.qsf:71, hdl/nec_test.qsf:60), so Quartus never sees a
// character of this block, and the five port connections above are written as
// `ifdef SYNTHESIS <the line exactly as it stood at 6cbb01a642> `else <the
// probe's line>`.  Strip the `ifndef` blocks, take the `ifdef` arms, and the
// file is byte-identical to 6cbb01a642's -- which is a stronger inertness
// claim than "one build looked the same", and it is checkable by reading.
//
// WHY IT EXISTS (fz2_w8_ghostsel_results_2026-08-11.md sec.2 and sec.3).  The
// M10 register solve freezes the core through the save-state map and asks
// which named register formed the chip's address.  It could only do that on
// `tb_v30_core`, which has ONE pin-event scheduler: SIX of thirteen wave-8
// DERIVE seats are NOREPRO there for harness reasons, and the derivation
// starved at n = 1.  On this harness the SAME 28 seeds reproduce the fabric
// verdict AND the fabric first-bad row 28/28.  The port was already in the
// DUT and tied off; this routes it out.
//
// IT IS A READ-ONLY TERMINAL FREEZE, and all three words carry weight.
//
//   READ-ONLY.  `SS_WE` is never asserted -- the port stays tied to 1'b0 even
//   here.  `tb_v30_core`'s mode 6 does save -> print -> LOAD, and that load
//   writes back exactly what it read purely so the run can RESUME.  This probe
//   never resumes, so it never writes, which removes the whole
//   SS_WE-while-CE-high hazard class (v30_core.sv:138) by construction.
//
//   TERMINAL.  `fz2_m10._one_solve` DISCARDS the rows of every freeze run --
//   the fork validation is a separate un-frozen replay -- so the freeze need
//   not be resumable.  That is why parking only the CORE is sufficient and
//   `nec_bus` is left running: it cannot move the core.
//
//   FREEZE.  Every architectural flop in v30u_eu/v30u_biu is gated by
//   `ss_we || srst || ce`, while the save-state read path (`ss_addr_q` and the
//   two read muxes) is `always @(posedge clk)` with NO `ce`.  So the stream
//   runs on the fast clock while the core is stopped -- which is exactly the
//   property `ss_park` relies on in `tb_v30_core`.
//
// WHERE THE FREEZE POINT IS, DERIVED AND NOT ASSUMED.  `nec_bus.sv:687` writes
// one `cap_record` per CPU clock at the `tick_rise` posedge, and the core's CE
// IS `bus_tick_rise` -- the same edge.  `tb_v30_core` emits its row at its own
// CE posedge recording the cycle just ending.  So row k means the same core
// clock on both harnesses by construction.  The counter below skips leading
// RESET records (`cap_record[55]`), which is `fz2_replay._drop_reset`'s own
// rule -- the rule that makes a tb_sys row index mean what a banked row index
// means -- and the park waits for that cycle's `tick_fall` so cycle k gets
// both its CE and its CE_HALF, mirroring `ss_park`'s release discipline.
//
// The falsifier is registered, not asserted: on the three seats `tb_v30_core`
// already solves, this leg must return byte-identical register terms at every
// freeze d.  fz2_m10sys_prereg_2026-08-11.md sec.3.
//----------------------------------------------------------------------------
integer m10_ss_at   = -1;      // freeze after this row index (-1 = disarmed)
integer m10_ss_mode = 0;       // 6 = stream the addressed map, as tb_v30_core
integer m10_row     = -1;      // rows emitted so far, RESET records skipped
reg     m10_seen    = 1'b0;
reg     m10_park    = 1'b0;
reg [8:0] m10_ss_addr = 9'b0;

initial begin
    if (!$value$plusargs("ss_at=%d",   m10_ss_at))   m10_ss_at   = -1;
    if (!$value$plusargs("ss_mode=%d", m10_ss_mode)) m10_ss_mode = 0;
end

wire m10_rowtick = cap_valid && !cap_record[55];

always_ff @(posedge clk) begin
    if (m10_rowtick) begin
        m10_row <= m10_row + 1;
        if (m10_ss_at >= 0 && m10_ss_mode == 6 && (m10_row + 1) == m10_ss_at)
            m10_seen <= 1'b1;
    end
    // park AFTER this cycle's CE_HALF has been delivered and before the next
    // CE: `tick_fall` is mid-cycle, `tick_rise` starts the next one.
    if (m10_seen && bus_tick_fall) m10_park <= 1'b1;
end

integer m10_i;
initial begin
    wait (m10_park === 1'b1);
    @(posedge clk);                       // one settled parked clock
    for (m10_i = 0; m10_i < v30_ss_pkg::SS_COUNT; m10_i = m10_i + 1) begin
        m10_ss_addr = v30_ss_pkg::ss_addr_of(m10_i);
        // SS_ADDR -> ss_addr_q (stage) -> the module read mux -> SS_RDATA:
        // three posedges to settle, sampled at a negedge.  `tb_v30_core`'s
        // `ss_read` timing, unchanged, because the path is the same path.
        @(posedge clk); @(posedge clk); @(posedge clk); @(negedge clk);
        $display("SS6 idx=%0d word=%0d addr=%03x val=%04x",
                 m10_ss_at, m10_i, v30_ss_pkg::ss_addr_of(m10_i),
                 core_ss_rdata);
    end
    $display("M10SYS DONE row=%0d ss_at=%0d", m10_row, m10_ss_at);
    $finish;
end
`endif
// harness read data driven onto the core's AD[15:0] during its read cycles
assign core_ad[15:0] = c_addrv_q ? c_rdata_q : 16'hzzzz;

// ⚠ THE MACRO GUARD -- `V30_MUXED_AD` MUST REACH THE COMPILER, AND "it
// compiled" IS NOT EVIDENCE THAT IT DID.
//
// This harness's ENTIRE observation path is multiplexed pins: `nec_bus` samples
// `core_ad` twice per CPU clock and the X1 retention model keys on
// `core_ad_oe`.  If the macro were dropped from `hdl/nec_test.qsf`, this file's
// `ifdef`s and the core's would agree with each other, the build would succeed,
// and the rig would observe an undriven bus -- an ACCEPTED-AND-IGNORED define,
// which is the exact class of defect the FLASH #18 `X1_AD_RETENTION` finding
// (E-6) records.  So the combination is refused at ELABORATION, by naming a
// module that does not exist: the error message IS the diagnosis.
`ifdef SYNTHESIS
`ifndef V30_MUXED_AD
V30_MUXED_AD_IS_REQUIRED_TO_SYNTHESISE_system_large __bus_shape_guard ();
`endif
`endif

v30_core u_core
(
    .CLK       (clk),
`ifdef SYNTHESIS
    .CE        (bus_tick_rise),
`ifdef V30_MUXED_AD
    .CE_HALF   (bus_tick_fall),
`endif
`else
    .CE        (bus_tick_rise & ~m10_park),
`ifdef V30_MUXED_AD
    .CE_HALF   (bus_tick_fall & ~m10_park),
`endif
`endif
    .RESET     (core_reset),
    .READY     (c_ready_q),
    .INT       (c_int_q),
    .NMI       (c_nmi_q),
    .POLL_N    (c_polln_q),
`ifdef V30_MUXED_AD
    .AD        (core_ad),
    .AD_OE     (core_ad_oe),
`else
    // Without the multiplexed bus the core has no AD to receive on; the
    // harness's read word goes straight in.  This integration does not
    // otherwise consume the de-muxed bus -- adopting it is M72's work, and
    // `nec_bus` is a MULTIPLEXED-pin instrument by construction.
    .DATA_I    (c_rdata_q),
`endif
    // The de-muxed bus is published and DELIBERATELY UNCONNECTED here, so
    // Quartus prunes it and this integration costs nothing for it.
    /* verilator lint_off PINCONNECTEMPTY */
    .ADDR_O    (),
    .DATA_O    (),
    .STATUS_O  (),
    /* verilator lint_on PINCONNECTEMPTY */
    .QS        (core_qs),
    .BS        (core_bs),
    .RD_N      (core_rd_n),
    .UBE_N     (core_ube_n),
    .BUSLOCK_N (core_buslock_n),
`ifdef SYNTHESIS
    .SS_ADDR   (9'b0),
    .SS_WDATA  (16'b0),
    .SS_WE     (1'b0),
    .SS_RDATA  (core_ss_rdata_unused),
`else
    .SS_ADDR   (m10_ss_addr),
    .SS_WDATA  (16'b0),                 // M10-SYS never writes: READ-ONLY probe
    .SS_WE     (1'b0),                  // ditto -- the tie-off is the reality
    .SS_RDATA  (core_ss_rdata),
`endif
    .SS_ERR    (core_ss_err_unused),
    .SS_BUS_QUIET(core_ss_bus_quiet_unused)
);

// one-directional status pins: chip vs core
assign hb_qs        = cfg_use_core ? core_qs        : NEC_QS;
assign hb_bs        = cfg_use_core ? core_bs        : NEC_BS;
assign hb_rd_n      = cfg_use_core ? core_rd_n      : NEC_RD_N;
assign hb_ube_n     = cfg_use_core ? core_ube_n     : NEC_UBE_N;
assign hb_buslock_n = cfg_use_core ? core_buslock_n : NEC_BUSLOCK_N;

//----------------------------------------------------------------------------
// X1 / §56.3a -- THE PAD-RETENTION MODEL FOR THE INTERNAL CORE'S AD.
// OFF unless `X1_AD_RETENTION` is defined.  Default builds are bit-identical.
//
// On the real part the AD pads FLOAT at an INTA's T1 and RETAIN the previous
// data phase.  Inside the FPGA `core_ad` is an internal net with no keeper, so
// there is nothing to retain and the analyser reads whatever the resolution
// gives it -- the reading §56.3 offers for the 116 fabric-only INTA cells, and
// the reading C11 refused to promote to a finding without an INTERVENTION.
// This is that intervention: a register that captures the last DRIVEN value of
// AD and supplies it when no driver is active.
//
// NOTHING IN EITHER CORE CHANGES.  `v30u_biu.sv`'s INTA path deliberately
// drives no address (`sim/biu_timed.cpp`'s `Access::no_addr`) and is not
// touched, exactly as the registration requires.
//
// THE ONE DEVIATION FROM THE LETTER OF §56.3a, STATED BEFORE THE RUN: the
// retention is applied on the OBSERVATION path (`hb_ad_sample`, what nec_bus
// captures) and NOT as a keeper driving `core_ad` itself.  It keeps the core's
// INPUT untouched -- feeding a retained value back into the core would change
// what the core SEES, and an intervention that also changes the core confounds
// the question, which is the registration's own stated constraint.  So this
// tests the claim as it is actually made ("the row READS the harness's INTA
// vector byte instead of the retained previous data phase") and no more.
//
// THE "IS ANYONE DRIVING" TERM (task #37, user-approved 2026-08-04).  The
// original model asked the NET -- `core_ad[i] === 1'bz` -- and §59.7.1 measured
// what that costs: Quartus 17.1 folds `=== 1'bz` on an INTERNAL tri-state to a
// constant, `core_ad_eff` collapses to `core_ad`, `core_ad_hold` loses its
// fanout and is DELETED at elaboration.  The construct is simulation-only, so
// the fabric leg was blocked and the intervention could not be run in silicon.
//
// It now asks the CORE, through `AD_OE` -- the pads' own output enable, which
// the real part has and which the core publishes as a wire off the same
// expression its `assign AD[...]` already uses.  §56.3a's prohibition is on
// MANUFACTURING an OE in the harness (re-deriving it from the status pins);
// this is the core stating its own truth, so the prohibition is satisfied and
// not evaded.  The core is unchanged in behaviour: one output port, one wire.
//
// EQUIVALENCE WITH THE `=== 1'bz` FORM, which is what the offline re-run
// proves.  `core_ad` has EXACTLY TWO drivers: the core's `AD` (enabled by
// `AD_OE`) and the harness read-data assign above (enabled by `c_addrv_q`, and
// only on [15:0]).  So the net is z at bit i iff no driver is enabled at bit i,
// which is exactly `!core_ad_drv[i]` below.  `tb_sys --leg ret` must reproduce
// its recorded 265/283 cell for cell, and that is the check.
//----------------------------------------------------------------------------
`ifdef X1_AD_RETENTION
wire [19:0] core_ad_drv = core_ad_oe | {4'b0, {16{c_addrv_q}}};
reg  [19:0] core_ad_hold;
wire [19:0] core_ad_eff;
genvar gad;
generate
    for (gad = 0; gad < 20; gad = gad + 1) begin : g_ad_ret
        assign core_ad_eff[gad] = core_ad_drv[gad] ? core_ad[gad]
                                                   : core_ad_hold[gad];
    end
endgenerate
always_ff @(posedge clk)
    for (int i = 0; i < 20; i = i + 1)
        if (core_ad_drv[i]) core_ad_hold[i] <= core_ad[i];
`else
wire [19:0] core_ad_eff = core_ad;
`endif

// AD sample fed back to nec_bus, and the physical drive to the chip. No
// feedback loop: NEC_AD's driver (hb_ad_drive) is registered inside nec_bus.
assign hb_ad_sample  = cfg_use_core ? core_ad_eff : NEC_AD;
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
nec_bus #(.EVT_N(EVT_N)) bus
(
    .clk(clk),
    .reset(harness_reset),

    .cfg_small_mode(cfg_small_mode),
    .cfg_cpu_off(cpu_power_off),
    .cfg_short_pwrup(skip_pwrup),
    .cfg_clk_div(cfg_clk_div),
    .cfg_wait_states(cfg_wait_states),
    .cfg_int_vector(cfg_int_vector),
    .cfg_wait_rand(cfg_wait_rand),
    .cfg_wmax(cfg_wmax),
    .cfg_wseed(cfg_wseed),
    .cfg_wait_replay(cfg_wait_replay),
    .wvec_raddr(wvec_raddr),
    .wvec_rdata(wvec_rdata),
    .iords_raddr(iords_raddr),

    .int_req(int_req),
    .nmi_req(nmi_req),
    .poll_n_in(poll_n_host),

    .evt_arm(evt_arm & {EVT_N{~harness_reset}}),
    .evt_addr(evt_addr),
    .evt_delay(evt_delay),
    .evt_hold(evt_hold),
    .evt_pin(evt_pin),
    .evt_vecsub_en(evt_vecsub_en),
    .evt_fired(evt_fired),
    .cfg_tvec(cfg_tvec),
    .vec_used(vec_used),

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

// Wait-vector replay RAM (Phase 2a): host-loaded exact Tw-per-bus-cycle
// sequence, read by nec_bus at the current bus-cycle index.
wvec_buf wvec
(
    .clk(clk),
    .h_waddr(h_wvec_addr),
    .h_we(h_wvec_wr),
    .h_wdata(h_wvec_wdata),
    .raddr(wvec_raddr),
    .rdata(wvec_rdata)
);

// iords sequence buffer (INS / REP INS): host-loaded per-element I/O-read data,
// read by nec_bus at the current IOR index. iord_eff (above) muxes it against
// the scalar cfg_iord and feeds test_mem's existing I/O-read serving path.
iords_buf iords
(
    .clk(clk),
    .h_waddr(h_iords_addr),
    .h_we(h_iords_wr),
    .h_wdata(h_iords_wdata),
    .raddr(iords_raddr[5:0]),
    .rdata(iords_rdata)
);

test_mem mem
(
    .clk(clk),
    .addr      (host_owns ? h_mem_addr   : mem_addr_cpu),
    .cycle_type(host_owns ? (h_mem_wr_req ? BS_MEMW : BS_MEMR) : mem_cycle_type_cpu),
    .rdata(mem_rdata),
    .wr_req    (host_owns ? h_mem_wr_req : mem_wr_req_cpu),
    .wdata     (host_owns ? h_mem_wdata  : mem_wdata_cpu),
    .be        (host_owns ? h_mem_be     : mem_be_cpu),
    .cfg_iord  (iord_eff)
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
