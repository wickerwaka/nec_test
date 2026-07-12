//============================================================================
//
//  nec_bus - V30 (uPD70116) maximum-mode bus interface
//
//  Generates the CPU clock and reset sequence, tracks bus T-states from the
//  BS0-BS2 status lines, latches addresses, drives read data onto AD[15:0],
//  inserts wait states via READY, and emits one 64-bit capture record per
//  CPU clock cycle.
//
//  Timing notes (docs/facts/pins_timing.md):
//   - Installed part is uPD70116C-8: clock must stay within 2-8 MHz.
//   - All pins pass through level shifters, ~5 ns per direction.
//   - CPU output delays are up to ~65 ns from a CLK edge, so at the FPGA
//     they can arrive ~75 ns after the internal edge. Address-phase signals
//     are sampled on the falling CLK edge; data-phase signals at the end of
//     the cycle (just before the next rising edge).
//   - AD[19:16] carry CPU-driven segment status (PS0-PS3) during T2-T4 of
//     every cycle. On the adapter PCB they are fixed CPU->FPGA nets; only
//     AD[15:0] pass through the F_AD_DIR-controlled transceivers. Never
//     drive AD[19:16].
//
//============================================================================

module nec_bus
(
    input             clk,
    input             reset,

    // Configuration (quasi-static; change only while CPU is held in reset)
    input             cfg_small_mode,  // 1: CPU strapped small-scale (S/LG high)
    input             cfg_cpu_off,     // 1: cut the CPU's 5V (ENABLE_N high)
    input             cfg_short_pwrup, // 1: short rail-settle wait (power
                                       //    already stable across a re-run)
    input       [5:0] cfg_clk_div,     // sys clocks per CPU clock, even, >= 4
    input       [3:0] cfg_wait_states, // wait states inserted in every bus cycle
    input       [7:0] cfg_int_vector,  // vector byte returned in INTA cycles

    // Request inputs (synchronous to clk)
    input             int_req,
    input             nmi_req,
    input             poll_n_in,

    // Pin-event scheduler: on a CODE T1 at evt_addr, wait evt_delay CPU
    // clocks, then drive the selected pin for evt_hold clocks (0 = until
    // disarmed). Gives interrupt tests a cycle-deterministic stimulus.
    input             evt_arm,
    input      [19:0] evt_addr,
    input      [15:0] evt_delay,
    input       [7:0] evt_hold,
    input       [2:0] evt_pin,     // 0=INT 1=NMI 2=POLL_N(active low)
    output reg        evt_fired,

    // NEC processor pins
    inout      [19:0] NEC_AD,
    output            NEC_AD_DIR,      // 0 - input, 1 - output (AD[15:0] transceivers)
    output            NEC_CLK,
    output            NEC_POLL_N,
    output            NEC_READY,
    output            NEC_RESET,
    output            NEC_INT,
    output            NEC_NMI,
    input       [1:0] NEC_QS,
    input       [2:0] NEC_BS,
    input             NEC_BUSLOCK_N,
    input             NEC_UBE_N,
    input             NEC_RD_N,
    output            NEC_ENABLE_N,

    // Memory-model interface. mem_addr/cycle_type are valid from the end of
    // T1 until the end of the bus cycle; rdata must be valid within
    // (cfg_clk_div - 2) sys clocks of mem_addr changing (i.e. before T2 ends).
    output reg [19:0] mem_addr,
    output reg  [2:0] mem_cycle_type,
    input      [15:0] mem_rdata,
    output reg        mem_wr_req,      // 1-clk pulse, end of first T3 of a write cycle
    output reg [15:0] mem_wdata,
    output reg  [1:0] mem_be,          // [0] = AD7:0 (A0==0), [1] = AD15:8 (UBE_N==0)

    // Capture interface: cap_valid pulses once per CPU clock cycle
    output reg        cap_valid,
    output reg [63:0] cap_record,

    output            cpu_running,     // reset sequence finished
    output            pwr_good_o       // 5V rail settle time elapsed
);

// Bus status (BS2,BS1,BS0), 8086 S2-S0 compatible
localparam bit [2:0] BS_INTA  = 3'b000;
localparam bit [2:0] BS_IOR   = 3'b001;
localparam bit [2:0] BS_IOW   = 3'b010;
localparam bit [2:0] BS_HALT  = 3'b011;
localparam bit [2:0] BS_CODE  = 3'b100;
localparam bit [2:0] BS_MEMR  = 3'b101;
localparam bit [2:0] BS_MEMW  = 3'b110;
localparam bit [2:0] BS_PASV  = 3'b111;

// T-state encoding used in capture records
localparam bit [2:0] ST_TI = 3'd0;
localparam bit [2:0] ST_T1 = 3'd1;
localparam bit [2:0] ST_T2 = 3'd2;
localparam bit [2:0] ST_T3 = 3'd3;
localparam bit [2:0] ST_TW = 3'd4;
localparam bit [2:0] ST_T4 = 3'd5;

//----------------------------------------------------------------------------
// CPU clock generation and sample strobes
//----------------------------------------------------------------------------
reg [5:0] div_cnt;
reg       nec_clk_q;
wire [5:0] div_max = cfg_clk_div - 6'd1;
wire [5:0] half    = {1'b0, cfg_clk_div[5:1]};

wire tick_rise  = div_cnt == div_max;      // next sys edge starts a CPU cycle
wire tick_fall  = div_cnt == half - 6'd1;  // next sys edge is the falling CLK edge

always_ff @(posedge clk) begin
    if (reset) begin
        div_cnt   <= '0;
        nec_clk_q <= 1'b0;
    end else begin
        div_cnt <= tick_rise ? 6'd0 : div_cnt + 6'd1;
        if (tick_rise) nec_clk_q <= 1'b1;
        else if (tick_fall) nec_clk_q <= 1'b0;
    end
end

assign NEC_CLK = nec_clk_q;

//----------------------------------------------------------------------------
// Input registration and per-phase samples
//----------------------------------------------------------------------------
reg [19:0] ad_in_q, ad_in_q2;
reg  [2:0] bs_q;
reg  [1:0] qs_q;
reg        buslock_n_q, ube_n_q, rd_n_q;

always_ff @(posedge clk) begin
    ad_in_q     <= NEC_AD;
    ad_in_q2    <= ad_in_q;    // aligned with strobe edge detectors
    bs_q        <= NEC_BS;
    qs_q        <= NEC_QS;
    buslock_n_q <= NEC_BUSLOCK_N;
    ube_n_q     <= NEC_UBE_N;
    rd_n_q      <= NEC_RD_N;
end

// Address-phase samples (falling CLK edge)
reg [19:0] ad_early;
reg  [2:0] bs_early;
reg  [1:0] qs_early;
reg        ube_n_early;

always_ff @(posedge clk) begin
    if (tick_fall) begin
        ad_early    <= ad_in_q;
        bs_early    <= bs_q;
        qs_early    <= qs_q;
        ube_n_early <= ube_n_q;
    end
end

// Sticky strobe accumulators (small mode). Short strobes — ASTB in
// particular is only ~half a CPU cycle — can fall between the two point
// samples, so capture records accumulate "seen active during this cycle"
// instead. Large mode keeps point samples: QS is a 2-bit code there and
// OR-ing across a transition would fabricate invalid codes.
reg astb_seen, intak_low_seen, rd_low_seen, wr_low_seen;

always_ff @(posedge clk) begin
    if (tick_rise) begin
        astb_seen      <= qs_q[0];
        intak_low_seen <= ~qs_q[1];
        rd_low_seen    <= ~rd_n_q;
        wr_low_seen    <= ~buslock_n_q;
    end else begin
        astb_seen      <= astb_seen      | qs_q[0];
        intak_low_seen <= intak_low_seen | ~qs_q[1];
        rd_low_seen    <= rd_low_seen    | ~rd_n_q;
        wr_low_seen    <= wr_low_seen    | ~buslock_n_q;
    end
end

// Cycle-complete values including the current (capture-edge) sample
wire astb_cyc      = astb_seen      | qs_q[0];
wire intak_low_cyc = intak_low_seen | ~qs_q[1];
wire rd_low_cyc    = rd_low_seen    | ~rd_n_q;
wire wr_low_cyc    = wr_low_seen    | ~buslock_n_q;

//----------------------------------------------------------------------------
// Power-on / reset sequencing. ENABLE_N gates the V30's 5V supply through a
// P-MOSFET on the adapter, so this is a true power-up sequence:
//   1. assert ENABLE_N (power on) with RESET held high
//   2. wait PWRUP_CLKS sys clocks for the 5V rail to stabilize (~130 ms)
//   3. hold RESET a further 32 CPU clocks (>= 4 required), then release
//----------------------------------------------------------------------------
`ifdef VERILATOR
localparam int PWRUP_CLKS = 64;          // keep simulation fast
localparam int PWRUP_CLKS_SHORT = 16;
`else
localparam int PWRUP_CLKS = 1 << 22;     // ~131 ms at 32 MHz
localparam int PWRUP_CLKS_SHORT = 1 << 10;  // ~32 us: rail already stable
`endif

reg [22:0] pwrup_cnt;
reg        pwr_good;
reg  [5:0] reset_cnt;
reg        nec_reset_q;

wire [22:0] pwrup_target = cfg_short_pwrup ? 23'(PWRUP_CLKS_SHORT) : 23'(PWRUP_CLKS);

always_ff @(posedge clk) begin
    if (reset) begin
        pwrup_cnt   <= '0;
        pwr_good    <= 1'b0;
        reset_cnt   <= 6'd32;
        nec_reset_q <= 1'b1;
    end else if (!pwr_good) begin
        pwrup_cnt <= pwrup_cnt + 23'd1;
        if (pwrup_cnt >= pwrup_target - 23'd1) pwr_good <= 1'b1;
    end else if (tick_rise) begin
        if (reset_cnt != 0) reset_cnt <= reset_cnt - 6'd1;
        else nec_reset_q <= 1'b0;
    end
end

assign NEC_RESET    = nec_reset_q;
assign NEC_ENABLE_N = cfg_cpu_off;
assign cpu_running  = ~nec_reset_q;
assign pwr_good_o   = pwr_good;

//----------------------------------------------------------------------------
// Small-scale mode pin aliases. When S/LG is strapped high the max-mode
// status pins carry their small-scale functions instead (datasheet block
// diagram, PDF p96): BS0=BUFEN, BS1=BUFR/W, BS2=IO/M (low = I/O),
// QS0=ASTB, QS1=INTAK, BUSLOCK pin=WR.
//----------------------------------------------------------------------------
wire sm_astb    = qs_q[0];
wire sm_intak_n = qs_q[1];
wire sm_io_m    = bs_q[2];        // 1 = memory, 0 = I/O
wire sm_wr_n    = buslock_n_q;
reg  sm_wr_n_d;

//----------------------------------------------------------------------------
// T-state tracker. State advances once per CPU cycle, at the rising edge.
// bs_q at that moment holds the end-of-cycle status: it goes active (!= PASV)
// during the T4/TI cycle preceding T1.
// In small mode the FSM idles (t_state stays TI in capture records); the
// datapath is driven directly by ASTB/RD/WR/INTAK strobes instead.
//----------------------------------------------------------------------------
reg [2:0] t_state;
reg [4:0] wait_cnt;
reg       ready_q;
reg       ready_pin;
reg       drive_en;
reg       is_read_cycle, is_write_cycle;
reg       mem_wr_req_done;

wire bs_active = bs_q != BS_PASV;

wire [2:0] next_t_state =
    (t_state == ST_TI) ? (bs_active ? ST_T1 : ST_TI) :
    (t_state == ST_T1) ? ST_T2 :
    (t_state == ST_T2) ? ST_T3 :
    (t_state == ST_T3) ? (ready_q ? ST_T4 : ST_TW) :
    (t_state == ST_TW) ? (ready_q ? ST_T4 : ST_TW) :
    /* ST_T4 */          (bs_active ? ST_T1 : ST_TI);

wire read_type  = bs_q == BS_CODE || bs_q == BS_MEMR || bs_q == BS_IOR || bs_q == BS_INTA;
wire write_type = bs_q == BS_MEMW || bs_q == BS_IOW;

always_ff @(posedge clk) begin
    mem_wr_req <= 1'b0;

    if (reset || nec_reset_q) begin
        t_state         <= ST_TI;
        wait_cnt        <= '0;
        ready_q         <= 1'b1;
        drive_en        <= 1'b0;
        is_read_cycle   <= 1'b0;
        is_write_cycle  <= 1'b0;
        mem_wr_req_done <= 1'b0;
        sm_wr_n_d       <= 1'b1;
        mem_cycle_type  <= BS_PASV;
    end else if (cfg_small_mode) begin
        // strobe-driven datapath, evaluated every sys clock
        sm_wr_n_d <= sm_wr_n;

        // wait-state insertion: arm at the ASTB pulse (T1) with cfg+1 so
        // the countdown spans T2 (one CPU clock before the first READY
        // sample at the end of T3), then one wait per CPU clock. READY is
        // re-registered on the falling CLK edge, giving setup to the
        // sampling edge.
        if (sm_astb) begin
            wait_cnt <= {1'b0, cfg_wait_states} + 5'd1;
            ready_q  <= cfg_wait_states == 0;
        end else if (tick_rise && wait_cnt != 0) begin
            wait_cnt <= wait_cnt - 5'd1;
            ready_q  <= wait_cnt == 5'd1;
        end

        if (!sm_intak_n)    mem_cycle_type <= BS_INTA;
        else if (!rd_n_q)   mem_cycle_type <= sm_io_m ? BS_MEMR : BS_IOR;
        else if (!sm_wr_n)  mem_cycle_type <= sm_io_m ? BS_MEMW : BS_IOW;

        // drive read data (or INTA vector) while the strobe is low
        drive_en <= ~rd_n_q | ~sm_intak_n;

        // latch write data at the rising edge of WR. sm_wr_n/sm_wr_n_d are
        // 1 and 2 ticks old, so ad_in_q2 (2 ticks old) is the bus value at
        // or before the edge — data is guaranteed held until WR rises.
        if (sm_wr_n && !sm_wr_n_d) begin
            mem_wr_req <= 1'b1;
            mem_wdata  <= ad_in_q2[15:0];
        end
    end else if (tick_rise) begin
        t_state <= next_t_state;

        if (next_t_state == ST_T1) begin
            // status is live in bs_q now; latch the cycle type
            mem_cycle_type <= bs_q;
            is_read_cycle  <= read_type;
            is_write_cycle <= write_type;
            wait_cnt       <= {1'b0, cfg_wait_states};
            ready_q        <= cfg_wait_states == 0;
        end

        if (next_t_state == ST_T2 && is_read_cycle)
            drive_en <= 1'b1;

        if (t_state == ST_T3 || t_state == ST_TW) begin
            if (wait_cnt != 0) begin
                wait_cnt <= wait_cnt - 5'd1;
                ready_q  <= wait_cnt == 5'd1;
            end
        end

        // capture write data at the end of the first T3
        if (t_state == ST_T3 && is_write_cycle && !mem_wr_req_done) begin
            mem_wr_req      <= 1'b1;
            mem_wdata       <= ad_in_q[15:0];
            mem_wr_req_done <= 1'b1;
        end

        if (next_t_state == ST_T4 || next_t_state == ST_TI) begin
            drive_en        <= 1'b0;
            mem_wr_req_done <= 1'b0;
        end
    end
end

// Address latch. Large mode: falling edge of T1 (address phase sample).
// Small mode: transparent latch while ASTB is high, frozen at its falling
// edge — the same behavior as the 74373 latch the pin is designed to drive.
always_ff @(posedge clk) begin
    if (cfg_small_mode ? sm_astb : (tick_fall && t_state == ST_T1)) begin
        mem_addr <= ad_in_q;
        mem_be   <= { ~ube_n_q, ~ad_in_q[0] };
    end
end

//----------------------------------------------------------------------------
// AD bus drive (read data). AD[19:16] are input-only on the adapter.
//----------------------------------------------------------------------------
reg [15:0] rdata_q;
always_ff @(posedge clk) begin
    rdata_q <= mem_cycle_type == BS_INTA ? {8'h00, cfg_int_vector} : mem_rdata;
end

assign NEC_AD[15:0]  = drive_en ? rdata_q : 16'hzzzz;
assign NEC_AD[19:16] = 4'hz;
assign NEC_AD_DIR    = drive_en;

//----------------------------------------------------------------------------
// Pin-event scheduler
//----------------------------------------------------------------------------
localparam bit [1:0] EV_IDLE = 2'd0, EV_DELAY = 2'd1, EV_ACTIVE = 2'd2,
                     EV_DONE = 2'd3;
reg  [1:0] ev_st;
reg [15:0] ev_cnt;
reg  [7:0] ev_hold_cnt;
reg        ev_drive;

// address match latched at the falling edge (address phase) so the
// trigger evaluates at the edge that ENDS the matching CODE T1 cycle
reg mem_addr_match;
always_ff @(posedge clk) begin
    if (tick_fall) mem_addr_match <= (ad_in_q == evt_addr);
end

wire ev_match = (t_state == ST_T1) && mem_cycle_type == BS_CODE &&
                mem_addr_match;

always_ff @(posedge clk) begin
    if (reset || !evt_arm) begin
        ev_st       <= EV_IDLE;
        ev_drive    <= 1'b0;
        evt_fired   <= 1'b0;
        ev_cnt      <= '0;
        ev_hold_cnt <= '0;
    end else if (tick_rise) begin
        case (ev_st)
        EV_IDLE: if (ev_match) begin
            ev_cnt <= evt_delay;
            ev_st  <= EV_DELAY;
        end
        EV_DELAY: begin
            if (ev_cnt == 0) begin
                ev_drive    <= 1'b1;
                evt_fired   <= 1'b1;
                ev_hold_cnt <= evt_hold;
                ev_st       <= EV_ACTIVE;
            end else ev_cnt <= ev_cnt - 16'd1;
        end
        EV_ACTIVE: begin
            if (evt_hold != 0) begin
                if (ev_hold_cnt <= 1) begin
                    ev_drive <= 1'b0;
                    ev_st    <= EV_DONE;
                end else ev_hold_cnt <= ev_hold_cnt - 8'd1;
            end
            // evt_hold==0: hold until disarmed
        end
        EV_DONE: ;
        endcase
    end
end

wire ev_int    = ev_drive && evt_pin == 3'd0;
wire ev_nmi    = ev_drive && evt_pin == 3'd1;
wire ev_poll   = ev_drive && evt_pin == 3'd2;

//----------------------------------------------------------------------------
// Static request outputs
//----------------------------------------------------------------------------
// READY is re-registered on the falling CLK edge so it changes a half CPU
// cycle before the rising edge where the CPU samples it (tSRYHK ~= tKKL-8).
// The exact wait-count seen by the CPU is a bring-up calibration item.
always_ff @(posedge clk) begin
    if (reset) ready_pin <= 1'b1;
    else if (tick_fall) ready_pin <= ready_q;
end

assign NEC_READY  = ready_pin;
assign NEC_INT    = int_req | ev_int;
assign NEC_NMI    = nmi_req | ev_nmi;
assign NEC_POLL_N = poll_n_in & ~ev_poll;

//----------------------------------------------------------------------------
// Capture record, one per CPU clock cycle
//----------------------------------------------------------------------------
always_ff @(posedge clk) begin
    cap_valid <= 1'b0;
    if (tick_rise && !reset) begin
        cap_valid  <= 1'b1;
        cap_record <= {
            5'd0,             // [63:59] reserved
            t_state,          // [58:56] T-state during this cycle
            nec_reset_q,      // [55]    RESET driven
            poll_n_in,        // [54]    POLL_N driven
            nmi_req,          // [53]    NMI driven
            int_req,          // [52]    INT driven
            ready_q,          // [51]    READY driven
            // [50] BUSLOCK_N / WR_N, [48] RD_N, [47:46] QS / {INTAK_N,ASTB}:
            // small mode records sticky seen-active-this-cycle values,
            // large mode records point samples
            cfg_small_mode ? ~wr_low_cyc : buslock_n_q,                  // [50]
            ube_n_early,                                                 // [49]
            cfg_small_mode ? ~rd_low_cyc : rd_n_q,                       // [48]
            cfg_small_mode ? {~intak_low_cyc, astb_cyc} : qs_early,      // [47:46]
            bs_q,             // [45:43] BS (end of cycle)
            bs_early,         // [42:40] BS (address phase)
            ad_in_q[19:16],   // [39:36] A19-A16 / PS3-PS0 (end of cycle)
            ad_in_q[15:0],    // [35:20] AD data phase (end of cycle)
            ad_early          // [19:0]  AD address phase
        };
    end
end

endmodule
