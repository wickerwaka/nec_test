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
wire    ce = (ce_cnt == 0);
logic   ce_half = 1'b1;
always @(posedge clk) begin
    ce_cnt  <= (ce_cnt >= ce_div - 1) ? 0 : ce_cnt + 1;
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
logic        ev_armed = 0;      // waiting for the trigger
logic        ev_drive = 0;
integer      ev_cnt = 0;
integer      ev_hold_cnt = 0;

wire pin_int    = (pins_cfg[0] != 0) | (ev_drive && ev_pin == 0);
wire pin_nmi    = (pins_cfg[1] != 0) | (ev_drive && ev_pin == 1);
wire pin_poll_n = (pins_cfg[2] != 0) & ~(ev_drive && ev_pin == 2);

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
    .QS        (QS),
    .BS        (BS),
    .RD_N      (RD_N),
    .UBE_N     (UBE_N),
    .BUSLOCK_N (BUSLOCK_N),
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
// behavioral memory: 64 KB mirrored across the 1 MB space (like test_mem)
//----------------------------------------------------------------------------
logic [7:0] mem [0:65535];

// per-case undo log (initial-ram load + CPU writes), restored last-first
logic [15:0] undo_addr [$];
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
wire lat_write = lat_type == 3'b110 || lat_type == 3'b010;

// memory read drive during T2/T3/Tw of read cycles (nec_bus-equivalent);
// INTA cycles return the vector byte, IOR cycles the configured data
localparam bit [7:0] INT_VECTOR = 8'hFF;   // harness CFG default

wire        mem_drive = (tb_t == ST_T2 || tb_t == ST_T3 ||
                         tb_t == ST_TW) && lat_read;
wire [15:0] mem_word  = lat_type == 3'b000 ? {8'h00, INT_VECTOR}
                      : lat_type == 3'b001 ? iord_r
                      : {mem[{lat_addr[15:1], 1'b1}],
                         mem[{lat_addr[15:1], 1'b0}]};
assign AD[15:0] = mem_drive ? mem_word : 16'hzzzz;

// address/UBE latch at the falling edge of T1 (address phase)
always @(negedge clk) begin
    if (ce_half && tb_t == ST_T1) begin
        lat_addr <= AD;
        lat_ube  <= UBE_N;
    end
end

// composed bus value with float retention (protocol-inferred drive).
// INTA cycles drive no address (AD19:16 = 0 during T1 only); HALT
// pseudo-cycles drive AD15:0 only.
logic [19:0] hold = '0;
wire com_phase  = bs_active && (tb_t == ST_T4 || tb_t == ST_TI);
wire drive_lo_a = (com_phase && BS != 3'b000) ||
                  (tb_t == ST_T1 && lat_type != 3'b000);
wire drive_hi_a = (com_phase && BS != 3'b011) ||
                  (tb_t == ST_T1 && lat_type != 3'b011);
wire cycle_live      = tb_t != ST_TI && lat_type != BS_PASV &&
                       lat_type != 3'b011;
wire core_ps_drive   = cycle_live && (tb_t == ST_T2 || tb_t == ST_T3 ||
                                      tb_t == ST_TW || tb_t == ST_T4);
wire core_data_drive = core_ps_drive && lat_write;

wire [15:0] eff_lo = (drive_lo_a || core_data_drive || mem_drive)
                     ? AD[15:0] : hold[15:0];
wire  [3:0] eff_hi = (drive_hi_a || core_ps_drive)
                     ? AD[19:16] : hold[19:16];

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
        if (tb_t == ST_T3 && lat_write && case_active) begin
            if (!lat_addr[0]) begin
                undo_addr.push_back(lat_addr[15:0]);
                undo_val.push_back(mem[lat_addr[15:0]]);
                mem[lat_addr[15:0]] <= AD[7:0];
                if (!lat_ube) begin
                    undo_addr.push_back(lat_addr[15:0] + 16'd1);
                    undo_val.push_back(mem[lat_addr[15:0] + 16'd1]);
                    mem[lat_addr[15:0] + 16'd1] <= AD[15:8];
                end
            end else if (!lat_ube) begin
                undo_addr.push_back(lat_addr[15:0]);
                undo_val.push_back(mem[lat_addr[15:0]]);
                mem[lat_addr[15:0]] <= AD[15:8];
            end
        end
    end else if (reset) begin
        tb_t     <= ST_TI;
        lat_type <= BS_PASV;
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

task automatic read_hex(output logic [31:0] v);
    logic [31:0] t;
    rc = $fscanf(fi, "%h", t);
    if (rc != 1) begin
        $display("FATAL: batch parse error");
        $finish;
    end
    v = t;
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
        $fdisplay(fo, "d %0d %0d %0d %0d %0d %0d %05x %0d %02x %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %02x %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
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
                  dut.u_biu.law_window, dut.u_biu.lowband_pause);
end

initial begin
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
        $fclose(fo);
        $display("BOOT DONE");
        $finish;
    end
end

initial begin
    if ($test$plusargs("bootimg")) wait (0);
    if (!$value$plusargs("batch=%s", batch_path)) batch_path = "batch.txt";
    if (!$value$plusargs("out=%s", out_path))     out_path = "core_out.txt";
    fi = $fopen(batch_path, "r");
    fo = $fopen(out_path, "w");
    if (fi == 0 || fo == 0) begin
        $display("FATAL: cannot open %s / %s", batch_path, out_path);
        $finish;
    end

    for (i = 0; i < 65536; i++) mem[i] = 8'h90;

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
            undo_addr.push_back(t32[15:0]);
            undo_val.push_back(mem[t32[15:0]]);
            mem[t32[15:0]] = t32b[7:0];
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
            cyc = cyc + 1;
        end
        repeat (2 * ce_div) @(posedge clk);    // flush the F#1 row itself
        recording = 0;
        repeat (16 * ce_div) @(posedge clk);   // ghost-load settle window
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
            logic [15:0] ua;
            logic [7:0]  uv;
            ua = undo_addr.pop_back();
            uv = undo_val.pop_back();
            mem[ua] = uv;
        end
        @(posedge clk);
    end

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
logic       ce_hold_check;
initial     ce_hold_check = $test$plusargs("ce_hold_check");
logic [6:0] eu_state_p  = '0;
logic [2:0] biu_state_p = '0;
logic [2:0] q_cnt_p     = '0;
logic [5:0] div_cnt_p   = '0;
logic       ce_p = 1'b1, reset_p = 1'b1;
integer     ce_hold_viol = 0;

always @(posedge clk) begin
    if (ce_hold_check && !reset_p && !ce_p) begin
        if (dut.u_eu.state  !== eu_state_p  ||
            dut.u_biu.state !== biu_state_p ||
            dut.u_biu.q_cnt !== q_cnt_p     ||
            dut.u_eu.div_cnt !== div_cnt_p) begin
            ce_hold_viol <= ce_hold_viol + 1;
            if (ce_hold_viol <= 10)
                $display("CE-HOLD VIOLATION @%0t: eu %0d->%0d biu %0d->%0d qcnt %0d->%0d div %0d->%0d",
                         $time, eu_state_p, dut.u_eu.state,
                         biu_state_p, dut.u_biu.state,
                         q_cnt_p, dut.u_biu.q_cnt,
                         div_cnt_p, dut.u_eu.div_cnt);
        end
    end
    eu_state_p  <= dut.u_eu.state;
    biu_state_p <= dut.u_biu.state;
    q_cnt_p     <= dut.u_biu.q_cnt;
    div_cnt_p   <= dut.u_eu.div_cnt;
    ce_p        <= ce;
    reset_p     <= reset;
end

final if (ce_hold_check)
    $display("CE_HOLD_VIOL %0d (ce_div=%0d)", ce_hold_viol, ce_div);

wire _unused = &{1'b0, RD_N, dbg_first_pop, scr_en, scr_qop};

endmodule
