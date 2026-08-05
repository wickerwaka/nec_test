//============================================================================
//
//  tb_v30_core - golden-trace replay testbench for the v30_core CPU
//
//  Batch-driven: sw/check_core.py converts SingleStepTests-format cases
//  (tests/v30/v0.1) into a text batch file, this TB replays each case on
//  the core and dumps one raw record per CPU cycle plus the architectural
//  state at the second instruction-boundary (F) queue pop. The Python
//  driver synthesizes 11-column cycle rows from the records (with the
//  same logic as the suite emitter) and diffs them against the case.
//
//  The TB treats the core as a black box on its chip pins: T-states, bus
//  cycles and latched addresses are reconstructed from BS/AD/UBE_N alone,
//  exactly as hdl/rtl/nec_bus.sv does with the real part. Only state
//  injection/observation uses the V30_BACKDOOR ports (verification-only).
//
//  Batch file grammar (all values hex, whitespace-separated):
//    <ncases>
//    per case:
//      <idx>
//      <ax> <cx> <dx> <bx> <sp> <bp> <si> <di> <es> <cs> <ss> <ds>
//      <ip> <flags>
//      <qlen> <q0> <q1> <q2> <q3> <q4> <q5> <fetch_ip>
//      <nram>  { <addr20> <byte> } * nram
//      <max_cycles> <nf>
//      <evt_mode> <evt_pin> <evt_addr20> <evt_delay> <evt_hold>
//      <pins> <iord>
//    nf = F pops closing the window (the golden window's F-row count);
//    evt_mode 0=none 1=fetch-trigger 2=fpop-trigger (see the scheduler
//    comment block); pins = static INT/NMI/POLL_N levels; iord = data
//    returned for I/O reads
//
//  Output stream:
//      = <idx>
//      r <t> <bs> <qs> <ube> <addr20> <data16> <ps>     (one per cycle)
//      f <ax> ... <flags>                               (state at 2nd F pop)
//      .
//
//  Build: sw/check_core.py --build (Verilator --binary --timing
//  -DV30_BACKDOOR over this file plus hdl/rtl/core/*.sv)
//
//============================================================================

`timescale 1ns/1ps

module tb_v30_core;

import v30_ss_pkg::*;

localparam bit [2:0] BS_PASV = 3'b111;

localparam bit [2:0] ST_TI = 3'd0;
localparam bit [2:0] ST_T1 = 3'd1;
localparam bit [2:0] ST_T2 = 3'd2;
localparam bit [2:0] ST_T3 = 3'd3;
localparam bit [2:0] ST_TW = 3'd4;
localparam bit [2:0] ST_T4 = 3'd5;

logic clk = 0;
initial forever #5 clk = ~clk;

logic reset = 1;

//----------------------------------------------------------------------------
// clock-enable train (Campaign 4 CE refactor). The core runs on the fast
// fabric clk but only advances state when CE is asserted.
//   +ce_div=1 (default): CE and CE_HALF high every clk = the pre-CE core
//     exactly, the golden path (bit- and cycle-identical baseline).
//   +ce_div=N (N>1): CE asserts one posedge in N; CE_HALF is its negedge
//     partner (the clk-low half right after the CE-high posedge). The core
//     AND the TB's own clocked observer/latches below advance only on those
//     enabled clocks, so per-CPU-cycle output must match N=1 and the core's
//     internal state must NOT change on CE-low fabric clocks.
//----------------------------------------------------------------------------
integer ce_div = 1;
initial if (!$value$plusargs("ce_div=%d", ce_div)) ce_div = 1;
integer ce_cnt = 0;
logic   ss_park = 1'b0;
wire    ce = !ss_park && (ce_cnt == 0);
logic   ce_half = 1'b1;
always @(posedge clk) begin
    if (!ss_park)
        ce_cnt <= (ce_cnt >= ce_div - 1) ? 0 : ce_cnt + 1;
    ce_half <= ce;   // high through the clk-low half after a CE-high posedge
end

// backdoor
// wait-state insertion (+waits=N): mirrors hdl/rtl/nec_bus.sv - the
// counter arms when a cycle's T1 is entered and decrements at the end of
// T3/TW, so the CPU sees exactly N Tw states per bus cycle. ready_r
// updated at the posedge entering T3 is the value the CPU samples at the
// posedge ending T3 (the harness re-registers on the falling edge only
// for setup margin).
integer     waits_cfg = 0;
logic [4:0] wait_cnt = '0;
logic       ready_r = 1'b1;

// ==== SHARED SEEDED RANDOM-WAIT GENERATOR ====
// MUST stay byte-for-byte equivalent to the mirror in hdl/rtl/nec_bus.sv so
// a given seed produces the IDENTICAL per-access wait sequence here (chip-
// vs-TB) and on the board (chip-vs-fabric). 16-bit Galois LFSR poly 0xB400,
// seeded at reset from +wseed (0 -> 0xACE1), advanced ONCE per bus cycle at
// T1 entry; per-access Tw count n = (draw[7:0]*(wmax+1))>>8, range 0..wmax.
// +wrand=1 selects random mode; default 0 keeps the uniform +waits path.
integer      wrand_cfg = 0;
integer      wmax_cfg  = 0;
logic [31:0] wseed_tmp = 32'hACE1;
logic [15:0] wlfsr = 16'hACE1;
// explicit wait-vector replay (+wvec=<hex byte file>): mirrors wvec_buf +
// nec_bus's bus-indexed replay. One Tw count per bus cycle. wbus_idx counts
// bus cycles from reset (== nec_bus bus_idx). Priority replay > random > uniform.
integer      wrepl_cfg = 0;
string       wvec_path;
logic  [7:0] wvec_arr [0:4095];
integer      wbus_idx = 0;
wire  [15:0] wseed_eff  = (wseed_tmp[15:0] == 16'd0) ? 16'hACE1 : wseed_tmp[15:0];
wire  [15:0] wlfsr_next = {1'b0, wlfsr[15:1]} ^ (wlfsr[0] ? 16'hB400 : 16'h0000);
wire  [4:0]  wmax_p1 = 5'(wmax_cfg) + 5'd1;                    // 1..16
wire  [12:0] wprod   = {5'b0, wlfsr[7:0]} * {8'b0, wmax_p1};   // 8b * 5b
wire  [4:0]  wrand_n = wprod[12:8];                            // 0..wmax

initial begin
    if (!$value$plusargs("waits=%d", waits_cfg)) waits_cfg = 0;
    if (!$value$plusargs("mirror=%d", mirror_mode)) mirror_mode = 0;
    if (!$value$plusargs("wrand=%d", wrand_cfg)) wrand_cfg = 0;
    if (!$value$plusargs("wmax=%d",  wmax_cfg))  wmax_cfg  = 0;
    if (!$value$plusargs("wseed=%h", wseed_tmp)) wseed_tmp = 32'hACE1;
    for (int wi = 0; wi < 4096; wi++) wvec_arr[wi] = 8'd0;
    if ($value$plusargs("wvec=%s", wvec_path)) begin
        wrepl_cfg = 1;
        $readmemh(wvec_path, wvec_arr);
    end
end

logic         bkd_load = 0;
logic [223:0] bkd_regs = '0;
logic  [47:0] bkd_queue = '0;
logic   [2:0] bkd_qlen = '0;
logic  [15:0] bkd_fetch_ip = '0;
logic         scr_en = 0;
logic   [1:0] scr_qop = 2'b00;
wire  [223:0] dbg_regs;
wire          dbg_first_pop;
wire          dbg_pend;

// pins
wire [19:0] AD;
wire  [1:0] QS;
wire  [2:0] BS;
wire        RD_N, UBE_N, BUSLOCK_N;

//----------------------------------------------------------------------------
// pin-event scheduler + static pins (mirrors the harness semantics):
//   mode 1 (fetch): pin asserted during cycle idx(CODE T1 at ev_addr)+2+D
//   mode 2 (fpop):  pin asserted during cycle idx(first F pop)+D, D >= 1
// hold = assert duration in cycles (0 = until end of case).
// Static pins: b0 INT, b1 NMI, b2 POLL_N (harness default POLL_N low).
//----------------------------------------------------------------------------
integer      ev_mode = 0, ev_pin = 0, ev_delay = 0, ev_hold = 0;
integer      pins_cfg = 0;
logic [19:0] ev_addr = '0;
logic [15:0] iord_r = 16'hFFFF;
// shared iord-SEQUENCE (INS / REP INS, and any multi-IOR case): an ordered
// list of 16-bit port-read values consumed one per IOR cycle in order. When
// iords_n == 0 the scalar iord_r is served on every IOR (IN E4/E5/EC/ED,
// unchanged). Byte forms carry the value in both lanes (see extract_iords.py),
// so the served word is lane-agnostic. See docs/notes/ins_outs_design.md.
localparam int IORDS_MAX = 1024;
logic [15:0] iords_arr [0:IORDS_MAX-1];
integer      iords_n   = 0;   // sequence length (0 = use scalar iord_r)
integer      iords_idx = 0;   // next value to serve
logic        ev_armed = 0;      // waiting for the trigger
logic        ev_drive = 0;
integer      ev_cnt = 0;
integer      ev_hold_cnt = 0;

wire pin_int    = (pins_cfg[0] != 0) | (ev_drive && ev_pin == 0);
wire pin_nmi    = (pins_cfg[1] != 0) | (ev_drive && ev_pin == 1);
wire pin_poll_n = (pins_cfg[2] != 0) & ~(ev_drive && ev_pin == 2);
reg   [8:0] ss_addr_r = 9'b0;
reg  [15:0] ss_wdata_r = 16'b0;
reg         ss_we_r = 1'b0;
wire [15:0] ss_rdata;
wire        ss_err;
wire        ss_bus_quiet;
wire [19:0] dut_ad_oe;   // task #37 / F55: the core's own pad output
                         // enable -- the composer below KEYS ON IT (sec.81.A.3)

v30_core dut (
    .CLK       (clk),
    .CE        (ce),
    .CE_HALF   (ce_half),
    .RESET     (reset),
    .READY     (ready_r),
    .INT       (pin_int),
    .NMI       (pin_nmi),
    .POLL_N    (pin_poll_n),
    .AD        (AD),
    .AD_OE     (dut_ad_oe),   // published pad enable (task #37).  SM3 s20 /
                              // F55: the composer CONSUMES it now -- see
                              // `eff_lo`/`eff_hi` below.  It used to infer the
                              // drive from the protocol, and that inference is
                              // what hid F55 for eleven sittings.
    .QS        (QS),
    .BS        (BS),
    .RD_N      (RD_N),
    .UBE_N     (UBE_N),
    .BUSLOCK_N (BUSLOCK_N),
    .SS_ADDR   (ss_addr_r),
    .SS_WDATA  (ss_wdata_r),
    .SS_WE     (ss_we_r),
    .SS_RDATA  (ss_rdata),
    .SS_ERR    (ss_err),
    .SS_BUS_QUIET(ss_bus_quiet),
    .bkd_load  (bkd_load),
    .bkd_regs  (bkd_regs),
    .bkd_queue (bkd_queue),
    .bkd_qlen  (bkd_qlen),
    .bkd_fetch_ip (bkd_fetch_ip),
    .scr_en    (scr_en),
    .scr_qop   (scr_qop),
    .dbg_regs  (dbg_regs),
    .dbg_first_pop (dbg_first_pop),
    .dbg_pend      (dbg_pend)
);

//----------------------------------------------------------------------------
// behavioral memory: full 1 MB flat (20-bit), matching the real 8086/V30 space
//----------------------------------------------------------------------------
logic [7:0] mem [0:1048575];   // full 1 MB flat (was 64 KB mirrored across 1 MB).
                               // The mirror aliased 20-bit addresses to 16 bits,
                               // so v20 cases whose operand/instruction/stack
                               // footprints collide mod-64K read the wrong byte -
                               // a harness false-divergence. Flat 1 MB matches the
                               // real chip's 20-bit space.
// +mirror=1 re-enables the 64K mirror (masks addresses to 16 bits) so a
// COLLISION-DEPENDENT golden - one captured on the board's own mirrored RAM -
// can be validated under the exact memory model it was captured under. Default
// flat. lat_a / lat_a1 are the (optionally masked) latched byte addresses.
logic        mirror_mode = 1'b0;
wire  [19:0] amask  = mirror_mode ? 20'h0FFFF : 20'hFFFFF;
wire  [19:0] lat_a  = lat_addr & amask;
wire  [19:0] lat_a1 = (lat_addr + 20'd1) & amask;

// per-case undo log (initial-ram load + CPU writes), restored last-first
logic [19:0] undo_addr [$];
logic  [7:0] undo_val  [$];
logic        case_active = 0;

//----------------------------------------------------------------------------
// pin observer: T-state tracking from BS, like nec_bus
//----------------------------------------------------------------------------
logic [2:0] tb_t = ST_TI;
wire        bs_active = BS != BS_PASV;

wire [2:0] tb_t_next =
    (tb_t == ST_TI) ? (bs_active ? ST_T1 : ST_TI) :
    (tb_t == ST_T1) ? ST_T2 :
    (tb_t == ST_T2) ? ST_T3 :
    (tb_t == ST_T3) ? (ready_r ? ST_T4 : ST_TW) :
    (tb_t == ST_TW) ? (ready_r ? ST_T4 : ST_TW) :
    /* ST_T4 */       (bs_active ? ST_T1 : ST_TI);

logic  [2:0] lat_type = BS_PASV;
logic [19:0] lat_addr = '0;
logic        lat_ube  = 1'b1;

wire lat_read  = lat_type == 3'b100 || lat_type == 3'b101 ||
                 lat_type == 3'b001 || lat_type == 3'b000;
// ...and the MEMORY half of it.  SM3 sitting 6 (ledger sec.66.3): the write
// COMMIT below used a plain `lat_write`, so an `IOW` to port P stored into
// `mem[P]`.  The read side was never symmetric -- `IOR` is served from
// `iord_ser` and `INTA` from `INT_VECTOR`, neither from `mem` -- and neither
// the socket harness nor `sim/` does it, which is why the chip reads the
// seed's own image where the RTL legs read the I/O datum.  A write cycle still
// HANDS THE DATA LANES OVER (the composer below asks `AD_OE`, which an `IOW`
// asserts like any other write); only the STORE is memory's, and `lat_memw` is
// what the store is keyed on.
wire lat_memw  = lat_type == 3'b110;

// memory read drive during T2/T3/Tw of read cycles (nec_bus-equivalent);
// INTA cycles return the vector byte, IOR cycles the configured data
localparam bit [7:0] INT_VECTOR = 8'hFF;   // harness CFG default

wire        mem_drive = (tb_t == ST_T2 || tb_t == ST_T3 ||
                         tb_t == ST_TW) && lat_read;
wire [15:0] iord_ser  = (iords_n > 0 && iords_idx < iords_n)
                      ? iords_arr[iords_idx] : iord_r;
wire [15:0] mem_word  = lat_type == 3'b000 ? {8'h00, INT_VECTOR}
                      : lat_type == 3'b001 ? iord_ser
                      : {mem[{lat_a[19:1], 1'b1}],
                         mem[{lat_a[19:1], 1'b0}]};
assign AD[15:0] = mem_drive ? mem_word : 16'hzzzz;

// address/UBE latch at the falling edge of T1 (address phase)
always @(negedge clk) begin
    if (ce_half && tb_t == ST_T1) begin
        lat_addr <= AD;
        lat_ube  <= UBE_N;
    end
end

// COMPOSED BUS VALUE WITH FLOAT RETENTION.
//
// SM3 sitting 20, F55's second half -- **THE COMPOSER ASKS THE CORE NOW.**
// This block used to INFER, from the bus protocol, which clocks the core was
// driving on:
//
//   wire halt_cyc   = lat_type == 3'b011;
//   wire com_phase  = bs_active && (tb_t == ST_T4 || tb_t == ST_TI ||
//                                   (halt_cyc && (tb_t == ST_T2 ||
//                                                 tb_t == ST_T3 ||
//                                                 tb_t == ST_TW)));
//   wire drive_lo_a = (com_phase && BS != 3'b000) ||
//                     (tb_t == ST_T1 && lat_type != 3'b000);
//   wire drive_hi_a = com_phase || (tb_t == ST_T1);
//   wire cycle_live = tb_t != ST_TI && lat_type != BS_PASV &&
//                     lat_type != 3'b011;   // <-- THIS is what hid F55
//   wire core_ps_drive   = cycle_live && (T2 || T3 || TW || T4);
//   wire core_data_drive = core_ps_drive && lat_write;
//   eff_lo = (drive_lo_a || core_data_drive || mem_drive) ? AD : hold;
//   eff_hi = (drive_hi_a || core_ps_drive)                ? AD : hold;
//
// An inference is an ASSERTION about the mechanism, and `standing_gates.md`'s
// meta-finding #5 is that an asserting comparator needs its own falsifier.
// `cycle_live`'s `lat_type != 3'b011` term floated a HALT-typed cycle's body
// WHATEVER THE CORE DID THERE, so for eleven sittings this TB scored the 35
// family-E address cells green ON THE INSTRUMENT'S AUTHORITY while the core
// re-drove the pads -- which is what `system_large` and the fabric saw and
// this TB could not (F55, sec.80.B.3(b) and sec.81.A).
//
// `AD_OE` is the core's OWN pad output enable (task #37, sec.73), the wire
// `system_large` already keys its retention model on and the one the fabric
// agrees with on 1,654 of 1,654 cells.  Consuming it here makes the two
// offline instruments the SAME instrument, structurally, instead of two
// inferences that happen to agree.  The port was already connected and marked
// "deliberately unconsumed"; it is consumed now.
//
// THE RECEIPT (sec.81.A.3, pre-registered as A3b before it was measured, and
// landed ONLY on a zero-delta): with F55 in the RTL, the AD_OE-keyed composer
// reproduces the protocol-inferred one on the four HLT sweeps **273/283 cell
// for cell**, on the S16 display walk **1,321/1,371 with 0 differing
// first-divergence coordinates**, and on `check_core --opcodes all`
// **169,000/169,000** -- plus the whole standing ladder.  It is a rewrite of
// the instrument that moves NOTHING, which is the only form in which an
// instrument may be rewritten.
//
// Engine-neutral: `AD_OE` is a port of `v30_core`, so the `fsm` core publishes
// it too and this names no core-internal signal.
//
// Falsifier for the layer itself: a capture in which the composed row differs
// from what a pad with this enable and this retention would show -- i.e. any
// cell where this TB and `tb_sys` disagree again.  The whole point of F55 is
// that such a disagreement is a FINDING, not a tolerance.
//
// `mem_drive` stays: the TB's MEMORY is the bus's other driver, and it is the
// harness's own truth, not an inference about the core.
logic [19:0] hold = '0;

wire [15:0] eff_lo = (dut_ad_oe[0] || mem_drive) ? AD[15:0] : hold[15:0];
wire  [3:0] eff_hi =  dut_ad_oe[16]              ? AD[19:16] : hold[19:16];

// mid-cycle (address-phase) sample of the composed bus
logic [19:0] ad_mid = '0;
always @(negedge clk) if (ce_half) ad_mid <= {eff_hi, eff_lo};

//----------------------------------------------------------------------------
// per-cycle bookkeeping at the end of each cycle
//----------------------------------------------------------------------------
integer fo = 0;
logic   recording = 0;
integer fcount = 0;
logic [223:0] fin_regs = '0;
logic         fin_ghost = 0;    // a ghost load was pending at the close
logic [4:0]   fin_wait = 0;

always @(posedge clk) begin
    if (!reset && ce) begin
        // record for the cycle just ending (pre-edge values throughout)
        if (recording && fo != 0)
            $fdisplay(fo, "r %0d %0d %0d %0d %05x %04x %01x %0d",
                      tb_t, BS, QS, UBE_N, ad_mid, eff_lo, eff_hi, BUSLOCK_N);
        if (recording && QS == 2'b01) begin
            fcount <= fcount + 1;
            if (fcount == nf - 1) begin
                fin_regs <= dbg_regs;   // state at the window-closing F pop
                fin_wait <= 5'd16;
            end
        end
        // ghost loads (POP-to-reg data still in flight at the closing F)
        // complete within the settle window; re-latch everything except
        // the retired IP (the following NOPs keep retiring)
        if (fin_wait != 0) begin
            fin_wait <= fin_wait - 5'd1;
            if (dbg_pend) fin_ghost <= 1;
            else if (fin_ghost) begin
                fin_ghost <= 0;
                fin_regs[191:0]   <= dbg_regs[191:0];
                fin_regs[223:208] <= dbg_regs[223:208];
            end
        end

        // observer FSM / cycle-type latch
        tb_t <= tb_t_next;
        if (tb_t_next == ST_T1) lat_type <= BS;
        else if (tb_t_next == ST_TI) lat_type <= BS_PASV;

        // advance the iord sequence one value per IOR cycle: at T4 the read
        // data has already been consumed (driven T2/T3/Tw), so the next IOR
        // cycle serves the following element. Scalar-iord cases (iords_n==0)
        // never touch iords_idx.
        if (iords_n > 0 && tb_t == ST_T4 && lat_type == 3'b001)
            iords_idx <= iords_idx + 1;

        // wait-state counter (see comment at ready_r). In random mode draw
        // this access's Tw count from the shared LFSR and advance it once
        // per bus cycle; uniform (+waits) mode is unchanged.
        if (tb_t_next == ST_T1) begin
            if (wrepl_cfg != 0) begin
                wait_cnt <= wvec_arr[wbus_idx][4:0];
                ready_r  <= wvec_arr[wbus_idx][4:0] == 5'd0;
            end else if (wrand_cfg != 0) begin
                wait_cnt <= wrand_n;
                ready_r  <= wrand_n == 5'd0;
                wlfsr    <= wlfsr_next;
            end else begin
                wait_cnt <= 5'(waits_cfg);
                ready_r  <= waits_cfg == 0;
            end
            wbus_idx <= wbus_idx + 1;
        end else if ((tb_t == ST_T3 || tb_t == ST_TW) &&
                     wait_cnt != 0) begin
            wait_cnt <= wait_cnt - 5'd1;
            ready_r  <= wait_cnt == 5'd1;
        end

        // pin-event scheduler (see comment block at the pin wires)
        if (ev_armed) begin
            if (ev_mode == 1 && tb_t == ST_T1 && lat_type == 3'b100 &&
                lat_addr == ev_addr) begin
                ev_armed <= 0;
                ev_cnt   <= ev_delay + 1;
            end else if (ev_mode == 2 && recording && QS == 2'b01 &&
                         fcount == 0) begin
                ev_armed <= 0;
                if (ev_delay <= 1) begin
                    ev_drive    <= 1;
                    ev_hold_cnt <= ev_hold;
                end else
                    ev_cnt <= ev_delay - 1;
            end
        end else if (ev_cnt > 0) begin
            ev_cnt <= ev_cnt - 1;
            if (ev_cnt == 1) begin
                ev_drive    <= 1;
                ev_hold_cnt <= ev_hold;
            end
        end else if (ev_drive && ev_hold != 0) begin
            ev_hold_cnt <= ev_hold_cnt - 1;
            if (ev_hold_cnt == 1) ev_drive <= 0;
        end

        hold <= {eff_hi, eff_lo};

        // apply CPU writes at the end of the first T3 (as nec_bus does)
        if (tb_t == ST_T3 && lat_memw && case_active) begin
            if (!lat_addr[0]) begin
                undo_addr.push_back(lat_a);
                undo_val.push_back(mem[lat_a]);
                mem[lat_a] <= AD[7:0];
                if (!lat_ube) begin
                    undo_addr.push_back(lat_a1);
                    undo_val.push_back(mem[lat_a1]);
                    mem[lat_a1] <= AD[15:8];
                end
            end else if (!lat_ube) begin
                undo_addr.push_back(lat_a);
                undo_val.push_back(mem[lat_a]);
                mem[lat_a] <= AD[15:8];
            end
        end
    end else if (reset) begin
        tb_t     <= ST_TI;
        lat_type <= BS_PASV;
        iords_idx <= 0;          // restart the port-read sequence each case
        fcount   <= 0;
        wait_cnt <= '0;
        ready_r  <= 1'b1;
        wlfsr    <= wseed_eff;   // reseed each run (held until 1st T1)
        wbus_idx <= 0;           // replay index restarts each run
    end
end

//----------------------------------------------------------------------------
// batch runner
//----------------------------------------------------------------------------
string batch_path, out_path;
integer fi, ncases, nram, maxcyc, idx, cyc, nf;
initial nf = 2;
logic [15:0] rv [0:13];
integer i, k, rc;
logic [31:0] t32, t32b;

// Save-state test modes. cpu_cyc is zero-based within each case: the first
// CE-high posedge after reset release is cycle 0.  The controller triggers at
// the following negedge, after that cycle's CE_HALF partner has completed,
// and parks the CE divider before doing any fabric-clock streaming.
integer ss_at = -1;
integer ss_mode = 0;
logic [31:0] ss_scramble_seed = 32'h1;
integer ss_dwell = 0;      // extra parked fabric clks (G5 long-dwell freeze)
integer cpu_cyc = -1;
logic ss_done = 1'b0;
// SS-test assertion quiesce (design 5.3 contingency): the scramble/width-sweep
// modes drive garbage-live state through the ~300-cycle restore window, tripping
// the core's SIM-ONLY equivalence/frame assertions (which assume valid state and
// held under v1's 1-cycle restore). Disable assertions across the whole SS-test
// window; the NEXT case boundary re-enables them. Resume correctness is verified
// by the byte-identical row comparison, not these probes. No effect on G1'
// (SS idle: never entered) or mode 2 (idempotence: no garbage written).
logic ss_asserts_off = 1'b0;
logic [15:0] ss_saved [0:SS_COUNT-1];
logic [15:0] ss_work  [0:SS_COUNT-1];

initial begin
    if (!$value$plusargs("ss_at=%d", ss_at)) ss_at = -1;
    if (!$value$plusargs("ss_mode=%d", ss_mode)) ss_mode = 0;
    if (!$value$plusargs("ss_scramble_seed=%d", ss_scramble_seed))
        ss_scramble_seed = 32'h1;
    if (!$value$plusargs("ss_dwell=%d", ss_dwell)) ss_dwell = 0;
end

always @(posedge clk) begin
    if (reset)
        cpu_cyc <= -1;
    else if (ce)
        cpu_cyc <= cpu_cyc + 1;
end

// A2 addressed-interface tooling (design 7.1). CE parked throughout (ss_park).
// Registered-read latency: present SS_ADDR at posedge N -> SS_RDATA valid after
// posedge N+2 (staging reg + module read-mux reg + sel regs); sample at a negedge
// after two posedges. Writes: 1 clk, SS_WE high for the posedge; effect lands one
// clk later (staging), invisible except that streaming writes run at 1/clk.
task automatic ss_write(input logic [8:0] a, input logic [15:0] d);
    ss_addr_r  = a;
    ss_wdata_r = d;
    ss_we_r    = 1'b1;
    @(posedge clk);      // core staging flop samples SS_WE=1 at this posedge
    @(negedge clk);      // clear PAST the sampling edge: a same-region clear
    ss_we_r    = 1'b0;   // races the staging flop (Verilator ordering) -> no write
endtask

task automatic ss_read(input logic [8:0] a, output logic [15:0] d);
    ss_addr_r = a;
    // SS_ADDR->ss_addr_q(stage)->module read-mux reg->SS_RDATA comb via ss_sel.
    // Settle 3 posedges then sample at a negedge: also covers reading a value
    // written by the immediately-preceding ss_write (its stage->module-flop
    // propagation takes 2 clks; a 2-posedge read would race it).
    @(posedge clk); @(posedge clk); @(posedge clk); @(negedge clk);
    d = ss_rdata;
endtask

task automatic ss_save(output logic [15:0] stream [0:SS_COUNT-1]);
    for (int si = 0; si < SS_COUNT; si++) ss_read(ss_addr_of(si), stream[si]);
endtask

task automatic ss_load(input logic [15:0] stream [0:SS_COUNT-1]);
    for (int si = 0; si < SS_COUNT; si++) ss_write(ss_addr_of(si), stream[si]);
    ss_we_r = 1'b0;
endtask

function automatic logic [15:0] ss_lfsr_next(input logic [15:0] v);
    ss_lfsr_next = {v[14:0], 1'b0} ^ (v[15] ? 16'h002d : 16'h0000);
endfunction

always @(negedge clk) begin : ss_controller
    logic [15:0] lfsr;
    logic idem_ok;
    if (reset) begin
        ss_done = 1'b0;
        ss_park = 1'b0;
        ss_addr_r = 9'b0;
        ss_wdata_r = 16'b0;
        ss_we_r = 1'b0;
    end else if (!ss_done && recording && ss_at >= 0 &&
                 cpu_cyc == ss_at && ce_half) begin
        ss_done = 1'b1;
        ss_park = 1'b1;
        // One parked posedge lowers CE_HALF and establishes a full quiet clk.
        @(posedge clk);
        // G5 long-dwell: hold the freeze for ss_dwell fabric clks (CE parked,
        // core frozen at an arbitrary ce_cnt phase) before streaming. A no-op:
        // the core cannot advance while CE==0, so the resumed stream is unchanged.
        repeat (ss_dwell) @(posedge clk);
        case (ss_mode)
            1: begin
                $assertoff(0); ss_asserts_off = 1'b1;   // quiesce (design 5.3)
                ss_save(ss_saved);
                // Codex review finding 1(b): a corrupt FIRST (tag) word must set
                // SS_ERR. The tag is an integrity word, not a state flop, so
                // restoring a tag-corrupted-but-otherwise-saved stream leaves the
                // core state intact and only trips SS_ERR; re-capture clears it.
                for (int si = 0; si < SS_COUNT; si++) ss_work[si] = ss_saved[si];
                ss_work[0] = SS_TAG ^ 16'hFFFF;
                ss_load(ss_work);
                if (!ss_err)
                    $error("SS_ERR did not set on corrupt tag (finding 1b) idx=%0d",
                           ss_at);
                ss_save(ss_saved);   // Addressed save implementation arrives in A2.
                lfsr = ss_scramble_seed[15:0];
                if (lfsr == 0) lfsr = 16'h1;
                ss_work[0] = SS_TAG; // keep the integrity tag valid
                for (int si = 1; si < SS_COUNT; si++) begin
                    lfsr = ss_lfsr_next(lfsr);
                    ss_work[si] = lfsr ^ (si[0] ? 16'hA5A5 : 16'h5A5A);
                end
                ss_load(ss_work);
                ss_load(ss_saved);
                if (ss_err) begin
                    $display("SS1 ERROR idx=%0d SS_ERR=1", ss_at);
                    $error("saved restore raised SS_ERR");
                end
            end
            2: begin
                ss_save(ss_saved);
                ss_load(ss_saved);
                ss_save(ss_work);
                idem_ok = 1'b1;
                for (int si = 0; si < SS_COUNT; si++)
                    if (ss_saved[si] !== ss_work[si]) idem_ok = 1'b0;
                $display("SS2 IDEMPOTENT idx=%0d %s", ss_at,
                         idem_ok ? "PASS" : "FAIL");
                if (!idem_ok) $error("save-state idempotence failure");
            end
            3: begin
                // RETIRED (design 7.2): no FIFO in the addressed interface; the
                // slot is taken by mode 5. Kept as a no-op for plusarg stability.
                $display("SS3 RETIRED idx=%0d (use mode 5)", ss_at);
            end
            5: begin
                // ROUND-TRIP WIDTH SWEEP (design 7.2 / G4'): per mapped address
                // (except the tag), write FFFF then read back = the field masked
                // to ss_field_width; write 0000 then read back = 0. Dynamically
                // proves, per address: write arm exists, read arm exists, both
                // touch the SAME correctly-sized slice (the v1 unpack blind spot).
                logic [8:0]  a5;
                logic [15:0] r1, r0, mask5;
                int          w5;
                $assertoff(0); ss_asserts_off = 1'b1;   // quiesce (design 5.3)
                ss_save(ss_saved);
                for (int si = 1; si < SS_COUNT; si++) begin
                    a5    = ss_addr_of(si);
                    w5    = ss_field_width(a5);
                    mask5 = (w5 >= 16) ? 16'hFFFF : 16'((1 << w5) - 1);
                    ss_write(a5, 16'hFFFF); ss_read(a5, r1);
                    ss_write(a5, 16'h0000); ss_read(a5, r0);
                    if (r1 !== mask5)
                        $error("SS5 WIDTH @%03x: r1=%04x expected mask=%04x (w=%0d)",
                               a5, r1, mask5, w5);
                    if (r0 !== 16'h0000)
                        $error("SS5 ZERO  @%03x: r0=%04x expected 0000", a5, r0);
                end
                ss_load(ss_saved);   // restore before resume
                $display("SS5 WIDTH-SWEEP idx=%0d done (%0d addrs)", ss_at,
                         SS_COUNT-1);
            end
            6: begin
                // SM3 sitting 25 -- §49.8's DECIDING MEASUREMENT, and it is a
                // READ.  "`SSA_E_PSW` is already in the map, so `+ss_at=<clk>`
                // reads PSW out at the boundary ... on the frozen binary, no
                // RTL change".  Mode 6 is that read: freeze, save the addressed
                // stream, PRINT the words the caller asked for, restore.  It
                // writes nothing the save/restore did not already write and it
                // is the only mode that produces state as OUTPUT rather than as
                // a self-check.  `ss_scramble_seed` selects the address (0 =
                // print the whole stream).
                ss_save(ss_saved);
                if (ss_scramble_seed == 0) begin
                    for (int si = 0; si < SS_COUNT; si++)
                        $display("SS6 idx=%0d word=%0d addr=%03x val=%04x",
                                 ss_at, si, ss_addr_of(si), ss_saved[si]);
                end else begin
                    for (int si = 0; si < SS_COUNT; si++)
                        if (ss_addr_of(si) == 9'(ss_scramble_seed))
                            $display("SS6 idx=%0d addr=%03x val=%04x",
                                     ss_at, ss_addr_of(si), ss_saved[si]);
                end
                ss_load(ss_saved);
            end
            4: begin
                // G4 sensitivity: flip ONE non-tag stream bit, restore the
                // corrupted image, resume. A bit that maps to live state must
                // perturb the continuation (or a visible final delta). The bit
                // index = ss_scramble_seed; word 0 (tag) is skipped.
                //
                // HOW TO DRIVE IT (F45; the guidance here used to read "run
                // many seeds: most flips must diverge", and that builds a BLIND
                // gate).  Mode 4's seed IS the bit index, so a small-seed sweep
                // only ever touches the FIRST WORD of the stream.  STEP THE
                // SEED BY 16 to walk one bit per stream word.  And the bar is
                // "SOME must diverge, and which ones is form- and
                // freeze-point-dependent" -- not "most": a bit that is dead at
                // this freeze point is dead legitimately.
                integer bit_idx, wrd, bpos;
                ss_save(ss_saved);
                for (int si = 0; si < SS_COUNT; si++) ss_work[si] = ss_saved[si];
                bit_idx = ss_scramble_seed % (SS_COUNT*16);
                if (bit_idx < 16) bit_idx = bit_idx + 16;   // skip the tag word
                wrd  = bit_idx / 16;
                bpos = bit_idx % 16;
                ss_work[wrd][bpos] = ~ss_work[wrd][bpos];
                ss_load(ss_work);
                $display("SS4 BITFLIP idx=%0d word=%0d bit=%0d", ss_at, wrd, bpos);
            end
            default: ;
        endcase
        // Drain the SS command staging before resuming. The last ss_write's
        // ss_we_r=0 needs one posedge to reach the core's staged ss_we_q; if we
        // resume with ss_we_q still high, the first ce cycle takes the core's
        // `if (ss_we)` branch and SKIPS its state advance -> a phantom wait.
        // The park must be RELEASED AT A NEGEDGE (mirroring the freeze at
        // line 533): clearing it right after a @(posedge) lands the blocking
        // assign in that posedge's active region, so the FSM samples ce=1 on
        // the very drain posedge while ss_we_q is still high (a scheduling
        // race). One parked drain posedge clears the staging, the @(negedge)
        // moves past it, then the next posedge is the clean first-resume cycle.
        ss_addr_r = 9'b0; ss_wdata_r = 16'b0; ss_we_r = 1'b0;
        @(posedge clk);      // parked (ss_park still 1): ss_we_q -> 0
        @(negedge clk);      // move off the drain posedge before releasing
        ss_park = 1'b0;
    end
end

task automatic read_hex(output logic [31:0] v);
    logic [31:0] t;
    rc = $fscanf(fi, "%h", t);
    if (rc != 1) begin
        $display("FATAL: batch parse error");
        $finish;
    end
    v = t;
endtask

task automatic wait_unparked_clks(input integer n);
    integer nw;
    nw = 0;
    while (nw < n) begin
        @(posedge clk);
        if (!ss_park) nw = nw + 1;
    end
endtask

// boot-replay mode (+bootimg=<hex byte file> +bootn=<cycles>): load the
// 64 KB image, run the real reset flow (no backdoor), record bootn cycles
string  bootimg_path;
integer bootn;
integer      ev_boot_tmp;
logic [31:0] ev_addr_tmp;

// +eudbg: per-cycle EU/BIU state dump alongside the r rows ("d <state>
// <q_pop> <q_avl> <q_cnt>") for phase-fit debugging (bootimg mode only)
logic eudbg_en;
initial eudbg_en = $test$plusargs("eudbg");

//----------------------------------------------------------------------------
// ENGINE-SPECIFIC PROBES.  Everything below the `ifdef reaches INSIDE the DUT
// by hierarchical reference (dut.u_eu.* / dut.u_biu.*) and is therefore bound
// to the FSM core's internal signal names.  The TB itself is ENGINE-NEUTRAL --
// it drives and samples chip pins plus the V30_BACKDOOR group only -- so the
// probes are compiled only when the RTL file list is the FSM core's
// (sw/check_core.py --core fsm passes -DV30_FSM_PROBES).  The ucore file list
// omits the define; its own probe set arrives with the ucore EU in U2.
// Nothing in the FSM build changes: the define is on by default for it.
//----------------------------------------------------------------------------
`ifdef V30_FSM_PROBES
//----------------------------------------------------------------------------
// Phase 2k RESERVATION-ONSET instrumentation (measurement only, TB-side; no
// functional RTL change). Latch, on every eu_req RISING edge, the EU state
// generating the reservation (onset_state = the reservation's OWN source, e.g.
// S_EA1/S_EA2/S_DISP8/S_RMWX/S_PUSH_CALC/S_DEC/...), the absolute CPU-cycle
// clock (onset_clock -> exact onset age), and the opcode/kind/dir identity of
// the pending access. This resolves the 12/24 collision at the eval_ext row
// where the coarse eu_req_p1==0 bit conflates ~10 different reservation states.
// The record is carried until eu_started / withdrawal (eu_req falls) / flush.
//
// The dumped fields are computed COMBINATIONALLY on the onset cycle itself
// (eu_req rises ON this cycle => onset_state = current state, age = 0) so a
// withdrawal/reassert cannot alias the age-0 case to a stale prior onset.
//----------------------------------------------------------------------------
logic [31:0] cpu_clk     = 0;    // free-running CPU-cycle counter (ce-gated)
logic        eu_req_prev = 0;    // eu_req at the previous CPU cycle
logic  [6:0] onset_state = 0;    // EU state at the reservation onset
logic [31:0] onset_clock = 0;    // cpu_clk at the reservation onset
logic  [7:0] onset_opc   = 0;    // opcode at the reservation onset
logic  [1:0] onset_kind  = 0;    // eu_kind at onset (0=MEM 1=IO)
logic        onset_wr    = 0;    // eu_wr   at onset (0=read 1=write)

wire        eu_req_now   = dut.u_eu.eu_req;
wire        eu_req_rise  = eu_req_now && !eu_req_prev;
wire  [6:0] onset_state_eff = eu_req_rise ? dut.u_eu.state   : onset_state;
wire  [7:0] onset_opc_eff   = eu_req_rise ? dut.u_eu.opc     : onset_opc;
wire  [1:0] onset_kind_eff  = eu_req_rise ? dut.u_eu.eu_kind : onset_kind;
wire        onset_wr_eff    = eu_req_rise ? dut.u_biu.eu_wr  : onset_wr;
wire [31:0] onset_age       = eu_req_rise ? 32'd0 : (cpu_clk - onset_clock);

always @(posedge clk) begin
    if (reset) begin
        cpu_clk     <= 0;
        eu_req_prev <= 0;
        onset_state <= 0;
        onset_clock <= 0;
        onset_opc   <= 0;
        onset_kind  <= 0;
        onset_wr    <= 0;
    end else if (ce) begin
        cpu_clk <= cpu_clk + 32'd1;
        if (eu_req_rise) begin
            onset_state <= dut.u_eu.state;
            onset_clock <= cpu_clk;
            onset_opc   <= dut.u_eu.opc;
            onset_kind  <= dut.u_eu.eu_kind;
            onset_wr    <= dut.u_biu.eu_wr;
        end
        eu_req_prev <= eu_req_now;
    end
end

always @(posedge clk) begin
    if (!reset && ce && recording && eudbg_en && fo != 0)
        // d[49]=eu_hold, d[50]=cpu_clk appended (Phase-1/2 flush+trajectory
        // attribution). APPEND-ONLY observability: both are existing signals,
        // the DUT is untouched and remains bit-identical to HEAD 1f6004c.
        // d[62..65]: ARBITER COMMIT-SLOT observability (Arc-2 arbiter-surface
        // probe). want_eu = the ready-EU claim; slot_fire/slot_id = the Phase-R
        // canonical arbiter's fired slot this cycle; eu_kind = the EU access kind
        // (0=mem 1=io 2=inta 3=halt). All existing DUT signals - APPEND-ONLY
        // observability, the DUT is untouched and remains bit-identical to HEAD.
        $fdisplay(fo, "d %0d %0d %0d %0d %0d %0d %05x %0d %02x %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                  dut.u_eu.state, dut.u_eu.q_pop,
                  dut.u_biu.q_avl, dut.u_biu.q_cnt,
                  dut.u_eu.eu_wrap, dut.u_biu.cur_wrap,
                  dut.u_eu.eu_addr, dut.u_eu.eu_seg,
                  dut.u_eu.opc, dut.u_eu.q_byte,
                  dut.u_biu.bus_phase, dut.u_biu.bus_ts, dut.u_biu.q_fresh,
                  dut.u_biu.eu_started, dut.u_eu.eu_req, dut.u_eu.eu_ready,
                  dut.u_biu.q_flush, dut.u_biu.eval_ext, dut.u_biu.evald,
                  dut.u_biu.flush_fast,
                  dut.u_biu.occupied, dut.u_biu.q_aged, dut.u_biu.infl,
                  dut.u_biu.eu_req_p1, dut.u_biu.pf_late_rsv, dut.u_biu.pf_starved,
                  dut.u_biu.prefetch_ext, dut.u_biu.prefetch_ok,
                  dut.u_biu.eu_wr, dut.u_biu.eu_mem_acc,
                  onset_state_eff, onset_age, onset_opc_eff,
                  onset_kind_eff, onset_wr_eff,
                  dut.u_biu.owns_slot, dut.u_biu.eu_rsv_dhi,
                  dut.u_biu.eu_rsv_push_calc,
                  // pf_drain DELETED from the RTL; emit a constant 0 so d[39]
                  // keeps its slot and every later index stays valid.
                  1'b0, dut.u_biu.pop_cnt, dut.u_biu.eu_consuming,
                  dut.u_biu.grid_phase, dut.u_biu.pf_lim,
                  dut.u_biu.push_pend, dut.u_biu.push_now, dut.u_biu.pop_now,
                  dut.u_biu.cnt_next, dut.u_biu.pop_sr,
                  dut.u_biu.eu_hold, cpu_clk,
                  // d[51..54]: EU-SIDE SCHEDULE state (the model-EU forecast
                  // test). pop_want is the EU's byte DEMAND, a function of EU
                  // microcode state alone - q_pop = pop_want && q_avail, so the
                  // bus only ever shows demand AND availability. pop_want &&
                  // !q_avail is EU starvation. dly is the micro-op countdown
                  // (cycles remaining). eu_rsv_lead is the existing
                  // silicon-confirmed EU->BIU schedule signal (v30_eu.sv:1453).
                  // Append-only observability; DUT bit-identical to HEAD.
                  dut.u_eu.pop_want, dut.u_eu.q_avail, dut.u_eu.dly,
                  dut.u_eu.eu_rsv_lead,
                  // d[55..61]: class-5 UNIFIED LAW (direct-path, active) +
                  // lowband. Names updated with the RTL in the same commit
                  // (names are part of the chain). d[55]=law_arm, d[56]=law_sel,
                  // d[57]=law_due, d[58]=law_dcnt, d[59]=law_dtw, d[60]=law_window,
                  // d[61]=lowband_pause.
                  dut.u_biu.law_arm, dut.u_biu.law_sel,
                  dut.u_biu.law_due, dut.u_biu.law_dcnt, dut.u_biu.law_dtw,
                  dut.u_biu.law_window, dut.u_biu.lowband_pause,
                  // d[62]=want_eu, d[63]=slot_fire, d[64]=slot_id (enum ordinal),
                  // d[65]=eu_kind. Arbiter-surface commit-slot fields.
                  dut.u_biu.want_eu, dut.u_biu.slot_fire, dut.u_biu.slot_id,
                  dut.u_biu.eu_kind,
                  // d[66]=recent_evx, d[67]=store_pf_boost. MEMW->CODE store-resume
                  // turnaround fix shadow (log-only until wired into prefetch_ok).
                  dut.u_biu.recent_evx, dut.u_biu.store_pf_boost,
                  // d[68..74]: ext_ok qualification subterms (H-EXT CODE->MEM probe).
                  // Which clause of ext_ok denies the eval_ext DIRECT EU commit. All
                  // existing DUT signals - APPEND-ONLY observability, DUT bit-identical.
                  dut.u_biu.eu_ready_p1, dut.u_biu.eu_ready_p2, dut.u_biu.eu_req_p2,
                  dut.u_biu.ext_flushed, dut.u_biu.ext_ok, dut.u_biu.ext_ok_wr,
                  dut.u_biu.eu_defer_wr, dut.u_biu.tw_par);
end

// +racedbg: RR2 E1/P-I1a race-consumer trace. APPEND-ONLY observability of the
// POP-PSW/IRET boundary-race consumer inputs (v30_eu.sv:5221-5235,
// S_TRAP_IVT2W). All existing DUT signals via XMR - the DUT is untouched and
// remains bit-identical. One "g" row per recorded cycle:
//   g <cpu_clk> <state> <is_ivt2w> <eu_done> <pop_pend> <psw_old> <psw>
//     <race_B> <r9d_pre> <r9d_pop>
// Consumer FIRES iff is_ivt2w && eu_done && pop_pend && psw_old[9] && race_B.
logic racedbg_en;
initial racedbg_en = $test$plusargs("racedbg");
always @(posedge clk) begin
    if (!reset && ce && recording && racedbg_en && fo != 0)
        $fdisplay(fo, "g %0d %0d %0d %0d %0d %04x %04x %0d %02x %02x",
                  cpu_clk, dut.u_eu.state,
                  (dut.u_eu.state == dut.u_eu.S_TRAP_IVT2W),
                  dut.u_eu.eu_done, dut.u_eu.pop_pend,
                  dut.u_eu.psw_old, dut.u_eu.psw, dut.u_eu.race_B,
                  dut.u_eu.r9d_pre, dut.u_eu.r9d_pop);
end

// +pfxdbg: RR4 segment-override leak probe. APPEND-ONLY observability of the
// one-shot prefix latch state per recorded cycle (all existing DUT signals via
// XMR; DUT bit-identical). One "p" row per cycle:
//   p <cpu_clk> <state> <opc> <seg_ovr_en> <seg_ovr> <eu_seg> <eu_addr> <eu_req>
logic pfxdbg_en;
initial pfxdbg_en = $test$plusargs("pfxdbg");
always @(posedge clk) begin
    if (!reset && ce && recording && pfxdbg_en && fo != 0)
        $fdisplay(fo, "p %0d %0d %02x %0d %0d %0d %05x %0d",
                  cpu_clk, dut.u_eu.state, dut.u_eu.opc,
                  dut.u_eu.seg_ovr_en, dut.u_eu.seg_ovr,
                  dut.u_eu.eu_seg, dut.u_eu.eu_addr, dut.u_eu.eu_req);
end

`endif  // V30_FSM_PROBES

//----------------------------------------------------------------------------
// SCRIPTED-CONSUMER MODE (+scr=<file>).  ENGINE-NEUTRAL: it drives scr_en /
// scr_qop and the V30_BACKDOOR injection group only -- the same core ports
// both engines already carry -- and records the ordinary `r` stream.  It is
// the RTL leg of `sw/ulockstep.py`; the sim leg is `v30sim biu-script`, and
// the two read the SAME script file.
//
// The script's ops are consumed in order.  `w n` burns n clocks; `f` / `s`
// hold the pop DEMAND until the BIU serves it (M8: pop = max(demand, ready)),
// which is the clock QS reports it on; `e` flushes for exactly one clock.
//----------------------------------------------------------------------------
string  scr_path;
integer scr_fi;
integer scrn;
logic [7:0]  scr_q [0:5];
logic [31:0] sv;
integer scr_qlen, scr_rc, scr_wait;
string  scr_tok;
logic [1:0] qs_p = 2'b00;   // the QS the row just written carried

always @(posedge clk) if (!reset && ce) qs_p <= QS;

task automatic scr_next(output string tk);
    integer r;
    r = $fscanf(scr_fi, "%s", tk);
    if (r != 1) tk = "end";
endtask

task automatic scr_hex(output logic [31:0] v);
    integer r;
    r = $fscanf(scr_fi, "%h", v);
    if (r != 1) v = 0;
endtask

initial begin
    if ($value$plusargs("scr=%s", scr_path)) begin
        if (!$value$plusargs("out=%s", out_path)) out_path = "core_out.txt";
        scr_fi = $fopen(scr_path, "r");
        fo = $fopen(out_path, "w");
        if (scr_fi == 0 || fo == 0) begin
            $display("FATAL: cannot open %s / %s", scr_path, out_path);
            $finish;
        end
        for (int mi = 0; mi < 1048576; mi++) mem[mi] = 8'h90;
        scr_qlen = 0;
        for (int qi = 0; qi < 6; qi++) scr_q[qi] = 8'h00;
        bkd_regs = '0;
        // header
        forever begin
            scr_next(scr_tok);
            if (scr_tok == "ops" || scr_tok == "end") break;
            if (scr_tok == "waits") begin
                scr_hex(sv); waits_cfg = int'(sv);
            end else if (scr_tok == "fill") begin
                scr_hex(sv);
                for (int mi = 0; mi < 1048576; mi++) mem[mi] = sv[7:0];
            end else if (scr_tok == "psw") begin
                scr_hex(sv); bkd_regs[208 +: 16] = sv[15:0];
            end else if (scr_tok == "cs") begin
                scr_hex(sv); bkd_regs[144 +: 16] = sv[15:0];
            end else if (scr_tok == "ip") begin
                scr_hex(sv); bkd_fetch_ip = sv[15:0];
            end else if (scr_tok == "q") begin
                scr_hex(sv); scr_qlen = int'(sv);
                for (int qi = 0; qi < scr_qlen; qi++) begin
                    scr_hex(sv); scr_q[qi] = sv[7:0];
                end
            end else if (scr_tok == "mem") begin
                scr_hex(sv);
                begin
                    logic [19:0] ma; ma = sv[19:0];
                    scr_hex(sv);
                    mem[ma] = sv[7:0];
                end
            end else begin
                $display("FATAL: bad script header token %s", scr_tok);
                $finish;
            end
        end
        // the fetch pointer is IP + qlen, exactly as compose_batch computes it
        bkd_fetch_ip = bkd_fetch_ip + 16'(scr_qlen);
        bkd_qlen = 3'(scr_qlen);
        for (int qi = 0; qi < 6; qi++) bkd_queue[qi*8 +: 8] = scr_q[qi];
        scr_en = 1;

        reset = 1;
        case_active = 1;
        @(posedge clk);
        bkd_load = 1;
        repeat (2) @(posedge clk);
        $fdisplay(fo, "= 0");
        @(negedge clk);
        reset = 0;
        bkd_load = 0;
        recording = 1;

        // ops.  PHASE CONTRACT: control between ops always sits just after a
        // NEGEDGE, so `scr_qop` is never assigned in the same time slot as the
        // posedge that records the row (that race made the driver look one
        // clock fast).  `scr_qop` for clock k is set in k's low half; the row
        // for clock k is written at k's closing posedge, and `qs_p` carries
        // that row's QS across to the next negedge for the service test.
        forever begin
            scr_next(scr_tok);
            if (scr_tok == "end") break;
            if (scr_tok == "w") begin
                scr_hex(sv);
                scr_qop = 2'b00;
                repeat (int'(sv)) begin @(posedge clk); @(negedge clk); end
            end else if (scr_tok == "f" || scr_tok == "s") begin
                // a pop is a DEMAND held until the BIU serves it (M8)
                scr_qop = (scr_tok == "f") ? 2'b01 : 2'b11;
                scr_wait = 0;
                while (scr_wait < 4096) begin
                    @(posedge clk); @(negedge clk);
                    if (qs_p != 2'b00) break;
                    scr_wait = scr_wait + 1;
                end
                scr_qop = 2'b00;
            end else if (scr_tok == "e") begin
                scr_hex(sv); bkd_regs[144 +: 16] = sv[15:0];  // new CS
                scr_hex(sv); bkd_fetch_ip = sv[15:0];         // new IP
                scr_qop = 2'b10;
                @(posedge clk); @(negedge clk);
                scr_qop = 2'b00;
            end else begin
                $display("FATAL: bad script op %s", scr_tok);
                $finish;
            end
        end
        scr_qop = 2'b00;
        recording = 0;
        $fdisplay(fo, ".");
        $fclose(fo);
        $fclose(scr_fi);
        $display("SCRIPT DONE");
        $finish;
    end
end

initial begin
    if ($test$plusargs("scr")) wait (0);
    if ($value$plusargs("bootimg=%s", bootimg_path)) begin
        if (!$value$plusargs("bootn=%d", bootn)) bootn = 300;
        if (!$value$plusargs("out=%s", out_path)) out_path = "core_out.txt";
        fo = $fopen(out_path, "w");
        $readmemh(bootimg_path, mem);
        // Optional pin-event injection in boot mode (mirrors the chip serve
        // path evt=addr:delay:hold:pin). Arms the SAME fetch-trigger (mode 1)
        // scheduler used by the validated batch INT/NMI tranches: the pin
        // drives at idx(CODE T1 @ evaddr) + 2 + evdelay for evhold cycles.
        if ($value$plusargs("evpin=%d", ev_boot_tmp)) begin
            ev_mode  = 1;
            ev_pin   = ev_boot_tmp;
            if (!$value$plusargs("evaddr=%h", ev_addr_tmp)) ev_addr_tmp = 0;
            ev_addr  = ev_addr_tmp[19:0];
            if (!$value$plusargs("evdelay=%d", ev_delay)) ev_delay = 0;
            if (!$value$plusargs("evhold=%d", ev_hold))   ev_hold  = 2;
            ev_armed = 1;
            ev_drive = 0;
            ev_cnt   = 0;
            ev_hold_cnt = 0;
        end
        reset = 1;
        bkd_load = 0;
        case_active = 1;   // let CPU writes hit mem (no undo needed)
        repeat (8) @(posedge clk);
        @(negedge clk);
        reset = 0;
        recording = 1;
        repeat (bootn * ce_div) @(posedge clk);   // bootn is CPU cycles
        recording = 0;
        $fdisplay(fo, ".");
`ifndef SYNTHESIS
`ifdef V30_FSM_PROBES
`ifdef VERILATOR
        // Family-5/7 hardening coverage (task #24 coda leg b): boot-replay path
        // -- the fuzz corpus runs here, so the strio-gadget gate hits show up.
        $fdisplay(fo, "cov %0d %0d %0d %0d %0d",
                  dut.u_biu.cov_f7a_idle_arm, dut.u_biu.cov_f7a_eval_ext,
                  dut.u_biu.cov_f5a_t3_veto,
                  dut.u_biu.cov_ff_t4, dut.u_biu.cov_ff_ti);
        $display("COV f7a_idle_arm=%0d f7a_eval_ext=%0d f5a_t3_veto=%0d",
                 dut.u_biu.cov_f7a_idle_arm, dut.u_biu.cov_f7a_eval_ext,
                 dut.u_biu.cov_f5a_t3_veto);
        $display("COV ff_t4=%0d ff_ti=%0d",
                 dut.u_biu.cov_ff_t4, dut.u_biu.cov_ff_ti);
`endif
`endif
`endif
        $fclose(fo);
        $display("BOOT DONE");
        $finish;
    end
end

initial begin
    if ($test$plusargs("bootimg")) wait (0);
    if ($test$plusargs("scr")) wait (0);
    if (!$value$plusargs("batch=%s", batch_path)) batch_path = "batch.txt";
    if (!$value$plusargs("out=%s", out_path))     out_path = "core_out.txt";
    fi = $fopen(batch_path, "r");
    fo = $fopen(out_path, "w");
    if (fi == 0 || fo == 0) begin
        $display("FATAL: cannot open %s / %s", batch_path, out_path);
        $finish;
    end

    for (i = 0; i < 1048576; i++) mem[i] = 8'h90;

    read_hex(t32); ncases = int'(t32);

    repeat (4) @(posedge clk);

    for (k = 0; k < ncases; k++) begin
        read_hex(t32); idx = int'(t32);
        for (i = 0; i < 14; i++) begin
            read_hex(t32); rv[i] = t32[15:0];
        end
        read_hex(t32); bkd_qlen = t32[2:0];
        for (i = 0; i < 6; i++) begin
            read_hex(t32); bkd_queue[i*8 +: 8] = t32[7:0];
        end
        read_hex(t32); bkd_fetch_ip = t32[15:0];
        read_hex(t32); nram = int'(t32);
        for (i = 0; i < nram; i++) begin
            read_hex(t32);
            read_hex(t32b);
            undo_addr.push_back(t32[19:0] & amask);
            undo_val.push_back(mem[t32[19:0] & amask]);
            mem[t32[19:0] & amask] = t32b[7:0];
        end
        read_hex(t32); maxcyc = int'(t32);
        read_hex(t32); nf = int'(t32);
        read_hex(t32); ev_mode = int'(t32);
        read_hex(t32); ev_pin = int'(t32);
        read_hex(t32); ev_addr = t32[19:0];
        read_hex(t32); ev_delay = int'(t32);
        read_hex(t32); ev_hold = int'(t32);
        read_hex(t32); pins_cfg = int'(t32);
        read_hex(t32); iord_r = t32[15:0];
        // iord SEQUENCE: <count> followed by <count> 16-bit values, consumed
        // one per IOR cycle (0 = scalar iord_r only). Emitted for every case
        // by compose_batch (0 when the case carries no "iords").
        read_hex(t32); iords_n = int'(t32);
        for (i = 0; i < iords_n; i++) begin
            read_hex(t32);
            if (i < IORDS_MAX) iords_arr[i] = t32[15:0];
        end
        if (iords_n > IORDS_MAX) iords_n = IORDS_MAX;
        iords_idx = 0;
        ev_armed = ev_mode != 0;
        ev_drive = 0;
        ev_cnt = 0;
        ev_hold_cnt = 0;

        for (i = 0; i < 14; i++) bkd_regs[i*16 +: 16] = rv[i];

        // hold the core in reset, inject state
        reset = 1;
        // pre-window float retention: the hardware bus retains the last
        // pre-anchor data phase; its AD19:16 = PS = {0, IE, CS(10)}
        hold = {1'b0, rv[13][9], 2'b10, 16'h0000};
        @(posedge clk);
        bkd_load = 1;                 // held until release so the reset
        repeat (2) @(posedge clk);    // branch keeps the injected state
        cyc = 0;
        case_active = 1;
        // re-enable assertions at the case boundary if a prior SS-test case
        // (mode 1/5 garbage window) quiesced them (design 5.3).
        if (ss_asserts_off) begin $asserton(0); ss_asserts_off = 1'b0; end
        $fdisplay(fo, "= %0d", idx);
        @(negedge clk);
        reset = 0;
        bkd_load = 0;
        recording = 1;
        // (the first posedge after release emits one benign pre-window row)
        // fabric-clock budgets scale with ce_div: the window still closes
        // on fcount (CPU-cycle F pops via the CE-gated observer), maxcyc and
        // the settle repeats are in CPU cycles so multiply by ce_div. All
        // ce_div==1 (default) => unchanged.
        while (fcount < nf && cyc < maxcyc * ce_div) begin
            @(posedge clk);
            if (!ss_park) cyc = cyc + 1;
        end
        wait_unparked_clks(2 * ce_div);         // flush the F#1 row itself
        recording = 0;
        wait_unparked_clks(16 * ce_div);        // ghost-load settle window
        case_active = 0;
        $fdisplay(fo, "f %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x",
                  fin_regs[15:0],    fin_regs[31:16],  fin_regs[47:32],
                  fin_regs[63:48],   fin_regs[79:64],  fin_regs[95:80],
                  fin_regs[111:96],  fin_regs[127:112],fin_regs[143:128],
                  fin_regs[159:144], fin_regs[175:160],fin_regs[191:176],
                  fin_regs[207:192], fin_regs[223:208]);
        $fdisplay(fo, ".");

        // revert memory (last-first)
        reset = 1;
        while (undo_addr.size() > 0) begin
            logic [19:0] ua;
            logic [7:0]  uv;
            ua = undo_addr.pop_back();
            uv = undo_val.pop_back();
            mem[ua] = uv;
        end
        @(posedge clk);
    end

`ifndef SYNTHESIS
`ifdef V30_FSM_PROBES
`ifdef VERILATOR
    // Family-5/7 hardening coverage readout (task #24 coda). Batch-cumulative
    // hit counts for the three new strio gates; leg (b) requires all three
    // NONZERO under the wrand strio-gadget fuzz. Emitted to the out file (a
    // "cov" line parse_out ignores) and to stdout for the A/B flow.
    $fdisplay(fo, "cov %0d %0d %0d",
              dut.u_biu.cov_f7a_idle_arm, dut.u_biu.cov_f7a_eval_ext,
              dut.u_biu.cov_f5a_t3_veto);
    $display("COV f7a_idle_arm=%0d f7a_eval_ext=%0d f5a_t3_veto=%0d",
             dut.u_biu.cov_f7a_idle_arm, dut.u_biu.cov_f7a_eval_ext,
             dut.u_biu.cov_f5a_t3_veto);
`endif
`endif
`endif
    $fclose(fo);
    $fclose(fi);
    $display("DONE %0d cases", ncases);
    $finish;
end

// watchdog
initial begin
    #1s;
    $display("FATAL: timeout");
    $finish;
end

//----------------------------------------------------------------------------
// CE-hold assertion (+ce_hold_check): the core must NOT advance on a
// CE-low fabric clock. Snapshot the watched internal state every fabric
// clock; on any clock whose PRECEDING edge had CE low (ce_p==0) and was
// out of reset, the watched state must be unchanged from that edge. Any
// change is a gating bug (the core ran on a disabled clock). Used with
// +ce_div=N (N>1); harmless at N=1 (ce_p is always high so never checks).
//----------------------------------------------------------------------------
logic        ce_hold_check;
initial      ce_hold_check = $test$plusargs("ce_hold_check");
// The watched state is engine-specific; the CHECK is not.  One concatenation
// per engine keeps the rule ("the core must not advance on a CE-low clock")
// identical for both.
// The probe word is 64 bits and zero-extended for BOTH engines, so an engine's
// watched set can be widened without the declaration becoming an engine fact.
`ifdef V30_FSM_PROBES
wire [63:0]  ce_probe = {dut.u_eu.state, dut.u_biu.state,
                         dut.u_biu.q_cnt, dut.u_eu.div_cnt};
`else
// ucore: `r_*` IS the state (the unprefixed names are the always_comb's
// next-state view, which tracks the pins and so moves on CE-low clocks by
// design -- F7).  Watching the next-state view would make this gate report the
// contract instead of a violation.
//
// R5 / F50 item 3 (2026-08-04): the EU is IN the probe now.  It watched the
// BIU only, so a clean `+ce_div` cell was BIU-state evidence and the EU side
// rested on the golden row match -- the enumerate-the-known blind spot this
// project has hit five times.  The ucore EU's spine is its micro-PC
// (`upc_page` / `upc_opc` / `upc_loc`, the three SSA_E_UPC_* addresses),
// which is what `u_eu.state` was for the archived core.
wire [63:0]  ce_probe = {dut.u_biu.r_ts, dut.u_biu.r_q_cnt,
                         dut.u_biu.r_fetch_ptr[7:0],
                         dut.u_eu.upc_page, dut.u_eu.upc_opc,
                         dut.u_eu.upc_loc};
`endif
logic [63:0] ce_probe_p = '0;
logic        ce_p = 1'b1, reset_p = 1'b1;
integer      ce_hold_viol = 0;

always @(posedge clk) begin
    if (ce_hold_check && !reset_p && !ce_p) begin
        if (ce_probe !== ce_probe_p) begin
            ce_hold_viol <= ce_hold_viol + 1;
            if (ce_hold_viol <= 10)
                $display("CE-HOLD VIOLATION @%0t: probe %016x->%016x",
                         $time, ce_probe_p, ce_probe);
        end
    end
    ce_probe_p <= ce_probe;
    ce_p       <= ce;
    reset_p    <= reset;
end

final if (ce_hold_check)
    $display("CE_HOLD_VIOL %0d (ce_div=%0d)", ce_hold_viol, ce_div);

wire _unused = &{1'b0, RD_N, dbg_first_pop, scr_en, scr_qop};

endmodule
