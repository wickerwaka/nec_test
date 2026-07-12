//============================================================================
//
//  v30_biu - V30 (uPD70116) bus interface unit
//
//  Implements the measured BIU model (docs/facts/biu_model.md) plus the
//  cycle-level scheduling extracted from the golden traces
//  (tests/v30/v0.1, Campaign 3):
//
//   - 6-byte prefetch queue. A fetch is committed only when >= 2 bytes are
//     free, counting bytes of a committed-but-not-yet-pushed fetch.
//   - Word fetches at even addresses; a single byte (upper lane, UBE_N low)
//     at odd addresses.
//   - Fetched bytes are pushed at the end of T4 and become poppable two
//     cycles later (measured push-to-pop latency).
//   - Bus-cycle commit points: the T3->T4 edge and the end of every idle
//     (Ti) cycle. The committed cycle drives status and the full address
//     during the following cycle; T1 begins one cycle after that. There is
//     NO commit evaluation at the T4->Ti edge (measured: a request that
//     just misses the T3 eval waits one extra idle cycle).
//   - EU accesses win arbitration over prefetch. A pending EU request
//     blocks prefetch commits even while its address is not yet valid
//     (eu_req high, eu_ready low = reservation).
//   - Odd word accesses split into two byte cycles, low address first,
//     back to back. Both halves drive the data word byte-swapped onto the
//     lanes ({wdata[7:0], wdata[15:8]}), as the silicon does.
//   - Queue flush (QS=E) clears the queue, cancels in-flight fetch data
//     and redirects the fetch pointer; the next cycle commits at the
//     normal evaluation points (a pending EU access still wins first).
//
//  Reset-vector sequencing (fetch from FFFF0h after RESET) is not yet
//  implemented: Campaign 3 cores are started exclusively through the TB
//  backdoor (bkd_load while in reset). Campaign 4 adds the real reset flow.
//
//============================================================================

module v30_biu (
    input             clk,
    input             srst,          // synchronous reset (RESET pin level)

    // pin-side values for the current CPU cycle (muxed onto AD by v30_core)
    output      [2:0] bs,            // bus status driven this cycle
    output     [19:0] ad_o,
    output            ad_oe_addr,    // driving the full 20-bit address
    output            ad_oe_ps,      // driving PS3-0 on AD19:16
    output            ad_oe_data,    // driving write data on AD15:0
    output reg        ube_n,
    output            rd_n,
    input      [15:0] ad_i,          // read-data sample (end of T3)
    input             ready,

    input             psw_ie,        // PS2 (IE) bit of the segment status

    // queue consumer (EU). F/S queue status is driven by the EU via
    // v30_core; the E (flush) pin timing is BIU-generated (qs_e) per the
    // measured display law.
    output      [7:0] q_byte,
    output            q_avail,
    output            qs_e,
    input             q_pop,
    input             q_flush,
    input      [15:0] flush_cs,
    input      [15:0] flush_ip,

    // EU bus access. eu_req refers to an access that has not started yet;
    // the EU drops it (or moves to the next access) on eu_started.
    input             eu_req,
    input             eu_ready,
    input             eu_wr,
    input             eu_word,
    input      [19:0] eu_addr,
    input       [1:0] eu_seg,
    input      [15:0] eu_wdata,
    output reg        eu_started,    // pulse: request accepted, params latched
    output            eu_done,       // high during the access's final T4
    output reg [15:0] eu_rdata,

    // TB backdoor: load fetch/queue state while in reset (see v30_core)
    input             bkd_load,
    input      [15:0] bkd_cs,
    input      [15:0] bkd_ip,        // offset of the first byte NOT queued
    input      [47:0] bkd_queue,
    input       [2:0] bkd_qlen
);

localparam bit [2:0] BS_CODE = 3'b100;
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_MEMW = 3'b110;
localparam bit [2:0] BS_PASV = 3'b111;

localparam bit [2:0] ST_TI = 3'd0;
localparam bit [2:0] ST_T1 = 3'd1;
localparam bit [2:0] ST_T2 = 3'd2;
localparam bit [2:0] ST_T3 = 3'd3;
localparam bit [2:0] ST_TW = 3'd4;
localparam bit [2:0] ST_T4 = 3'd5;

localparam bit [1:0] SEG_CS = 2'd2;

//----------------------------------------------------------------------------
// bus-cycle state
//----------------------------------------------------------------------------
reg  [2:0] state;

// current cycle (valid T1..T4)
reg  [2:0] cur_type;
reg [19:0] cur_addr;
reg        cur_fetch;      // prefetch CODE cycle
reg        cur_wr;
reg        cur_swap;       // access started at an odd address: swap lanes
reg        cur_split1;     // first half of a split word access
reg        cur_split2;     // second half of a split word access
reg [15:0] cur_wdata;
reg  [1:0] cur_seg;
reg        cur_ube_n;

// committed next cycle (drives status/address during the current cycle)
reg        nxt_valid;
reg  [2:0] nxt_type;
reg [19:0] nxt_addr;
reg        nxt_fetch;
reg        nxt_wr;
reg        nxt_swap;
reg        nxt_split1;
reg        nxt_split2;
reg [15:0] nxt_wdata;
reg  [1:0] nxt_seg;
reg        nxt_ube_n;

//----------------------------------------------------------------------------
// prefetch queue
//----------------------------------------------------------------------------
reg  [7:0] q_mem [0:5];
reg  [2:0] q_rd, q_wr;
reg  [2:0] q_cnt;          // true occupancy (incl. bytes not yet poppable)
reg  [2:0] q_avl;          // poppable bytes (lags pushes by one cycle)
reg  [1:0] q_aged;         // bytes pushed at the previous edge
reg        fetch_discard;  // in-flight fetch data dropped by a flush
reg [15:0] fetch_cs;
reg [15:0] fetch_off;
reg [15:0] fetch_data;     // read-data latch for the in-flight fetch

wire [19:0] fetch_cs_lin  = {fetch_cs, 4'h0};
wire [15:0] fetch_cs_sel  = q_flush ? flush_cs : fetch_cs;
wire [15:0] fetch_off_sel = q_flush ? flush_ip : fetch_off;
wire [19:0] fetch_phys    = {fetch_cs_sel, 4'h0} + {4'h0, fetch_off_sel};
wire        fetch_word    = ~fetch_phys[0];

wire       pop_now  = q_pop && q_avl != 0;
wire       cur_word = ~cur_addr[0] && !cur_split2;
wire [1:0] push_now = (state == ST_T4 && cur_fetch && !fetch_discard)
                      ? (cur_word ? 2'd2 : 2'd1) : 2'd0;
wire [2:0] cnt_next = q_cnt - {2'b0, pop_now} + {1'b0, push_now};
// bytes of an in-flight fetch not yet pushed (committed-next fetches never
// coincide with a commit evaluation, so only the current cycle counts)
wire [1:0] infl = (cur_fetch && state != ST_TI && push_now == 0 &&
                   !fetch_discard) ? (cur_word ? 2'd2 : 2'd1) : 2'd0;
wire [3:0] occupied = {1'b0, cnt_next} + {2'b0, infl};
wire       prefetch_ok = !q_flush ? (!eu_req && occupied <= 4)
                                  : !eu_req;   // flushed queue is empty

assign q_byte  = q_mem[q_rd];
assign q_avail = q_avl != 0;

//----------------------------------------------------------------------------
// QS=E display law (measured, mission E): the E code appears on the pins
// in the internal-flush cycle when the BIU is quiet; otherwise it waits
// for the first cycle with no doomed fetch in T1-T3/TW, no queue-push
// absorb (q_aged), and no ready-but-not-yet-started EU request (a flush
// raised together with an EU request - the trap - still shows at once).
//----------------------------------------------------------------------------
reg e_wait;
wire flush_busy_fetch = cur_fetch && (state == ST_T1 || state == ST_T2 ||
                                      state == ST_T3 || state == ST_TW);
wire flush_quiet = !(cur_fetch && state != ST_TI) && (q_aged == 2'd0);
wire e_wait_show = e_wait && !flush_busy_fetch && (q_aged == 2'd0) &&
                   !(eu_ready && !eu_started);
assign qs_e = (q_flush && flush_quiet) || e_wait_show;

//----------------------------------------------------------------------------
// commit selection (combinational). Priority: second half of a split EU
// access, then a ready EU request, then prefetch.
//----------------------------------------------------------------------------
wire want_half2 = cur_split1 && !cur_fetch && state != ST_TI;
wire want_eu    = eu_req && eu_ready;

// EU access geometry
wire eu_split   = eu_word && eu_addr[0];
wire eu_ube_n   = eu_word ? 1'b0 : (eu_addr[0] ? 1'b0 : 1'b1);

wire        pick_any   = want_half2 || want_eu || prefetch_ok;
wire  [2:0] pick_type  = want_half2 ? cur_type
                       : want_eu    ? (eu_wr ? BS_MEMW : BS_MEMR)
                                    : BS_CODE;
wire [19:0] pick_addr  = want_half2 ? cur_addr + 20'd1
                       : want_eu    ? eu_addr
                                    : fetch_phys;
wire        pick_fetch = !want_half2 && !want_eu;
wire        pick_wr    = want_half2 ? cur_wr : (want_eu && eu_wr);
wire        pick_swap  = want_half2 ? cur_swap : (want_eu && eu_addr[0]);
wire        pick_split1 = !want_half2 && want_eu && eu_split;
wire        pick_split2 = want_half2;
wire [15:0] pick_wdata = want_half2 ? cur_wdata : eu_wdata;
wire  [1:0] pick_seg   = want_half2 ? cur_seg
                       : want_eu    ? eu_seg : SEG_CS;
wire        pick_ube_n = want_half2 ? 1'b1
                       : want_eu    ? eu_ube_n : 1'b0;

task automatic do_commit();
    nxt_valid  <= 1'b1;
    nxt_type   <= pick_type;
    nxt_addr   <= pick_addr;
    nxt_fetch  <= pick_fetch;
    nxt_wr     <= pick_wr;
    nxt_swap   <= pick_swap;
    nxt_split1 <= pick_split1;
    nxt_split2 <= pick_split2;
    nxt_wdata  <= pick_wdata;
    nxt_seg    <= pick_seg;
    nxt_ube_n  <= pick_ube_n;
    if (pick_fetch) begin
        fetch_off <= fetch_off_sel + (fetch_word ? 16'd2 : 16'd1);
        if (!q_flush) fetch_cs <= fetch_cs;   // (flush handled below)
    end else if (want_eu && !want_half2) begin
        eu_started <= 1'b1;
    end
endtask

//----------------------------------------------------------------------------
// main sequencing
//----------------------------------------------------------------------------
wire t3_done = (state == ST_T3 || state == ST_TW) && ready;

// a committed-but-stale prefetch dies in the flush cycle: transitions must
// not consume it
wire nxt_live = nxt_valid && !(q_flush && nxt_fetch);

assign eu_done = (state == ST_T4) && !cur_fetch && cur_type != BS_PASV
                 && !cur_split1;

always_ff @(posedge clk) begin
    eu_started <= 1'b0;

    if (srst) begin
        state      <= ST_TI;
        nxt_valid  <= 1'b0;
        cur_type   <= BS_PASV;
        cur_fetch  <= 1'b0;
        cur_wr     <= 1'b0;
        cur_split1 <= 1'b0;
        cur_split2 <= 1'b0;
        cur_swap   <= 1'b0;
        cur_seg    <= SEG_CS;
        cur_addr   <= '0;
        cur_wdata  <= '0;
        cur_ube_n  <= 1'b1;
        // reset value 0 matches the pre-window fetch history of the golden
        // traces (both queue variants end on even word / odd byte fetches,
        // UBE_N low); the pin holds its value between address phases
        ube_n      <= 1'b0;
        q_rd       <= '0;
        q_wr       <= '0;
        q_cnt      <= '0;
        q_avl      <= '0;
        q_aged     <= '0;
        fetch_discard <= 1'b0;
        fetch_data <= '0;
        eu_rdata   <= '0;
        e_wait     <= 1'b0;
        if (bkd_load) begin
            fetch_cs  <= bkd_cs;
            fetch_off <= bkd_ip;
            q_cnt     <= bkd_qlen;
            q_avl     <= bkd_qlen;
            q_wr      <= (bkd_qlen >= 3'd6) ? 3'd0 : bkd_qlen;
            for (int i = 0; i < 6; i++)
                q_mem[i] <= bkd_queue[i*8 +: 8];
        end
    end else begin
        // queue occupancy / availability pipeline
        q_cnt  <= cnt_next;
        q_avl  <= q_avl - {2'b0, pop_now} + {1'b0, q_aged};
        q_aged <= push_now;
        if (pop_now)
            q_rd <= (q_rd == 3'd5) ? 3'd0 : q_rd + 3'd1;
        if (push_now != 0) begin
            q_mem[q_wr] <= cur_addr[0] ? fetch_data[15:8] : fetch_data[7:0];
            if (push_now == 2'd2) begin
                q_mem[(q_wr == 3'd5) ? 3'd0 : q_wr + 3'd1] <= fetch_data[15:8];
                q_wr <= (q_wr >= 3'd4) ? q_wr - 3'd4 : q_wr + 3'd2;
            end else begin
                q_wr <= (q_wr == 3'd5) ? 3'd0 : q_wr + 3'd1;
            end
        end

        // flush: clear queue, cancel in-flight data, redirect fetch pointer
        if (q_flush) begin
            q_cnt  <= '0;
            q_avl  <= '0;
            q_aged <= '0;
            q_rd   <= '0;
            q_wr   <= '0;
            fetch_cs  <= flush_cs;
            fetch_off <= flush_ip;
            if (flush_busy_fetch)
                fetch_discard <= 1'b1;    // let the bus cycle finish, drop data
            if (nxt_valid && nxt_fetch)
                nxt_valid <= 1'b0;        // uncommit a stale fetch
        end

        // QS=E display deferral
        if (q_flush && !flush_quiet) e_wait <= 1'b1;
        else if (e_wait_show)        e_wait <= 1'b0;

        unique case (state)
            ST_TI: begin
                if (nxt_live) begin
                    state      <= ST_T1;
                    cur_type   <= nxt_type;
                    cur_addr   <= nxt_addr;
                    cur_fetch  <= nxt_fetch;
                    cur_wr     <= nxt_wr;
                    cur_swap   <= nxt_swap;
                    cur_split1 <= nxt_split1;
                    cur_split2 <= nxt_split2;
                    cur_wdata  <= nxt_wdata;
                    cur_seg    <= nxt_seg;
                    cur_ube_n  <= nxt_ube_n;
                    ube_n      <= nxt_ube_n;
                    nxt_valid  <= 1'b0;
                end else if (pick_any) begin
                    do_commit();
                end
            end
            ST_T1: state <= ST_T2;
            ST_T2: state <= ST_T3;
            ST_T3, ST_TW: begin
                if (ready) begin
                    state <= ST_T4;
                    // read-data sample at the end of T3/TW
                    if (!cur_wr) begin
                        if (cur_fetch)
                            fetch_data <= ad_i;
                        else if (cur_split2)
                            eu_rdata[15:8] <= ad_i[7:0];
                        else if (cur_split1)
                            eu_rdata[7:0]  <= ad_i[15:8];
                        else if (cur_addr[0])
                            eu_rdata <= {ad_i[7:0], ad_i[15:8]};
                        else
                            eu_rdata <= ad_i;
                    end
                    // commit evaluation for the cycle after T4
                    if (pick_any) do_commit();
                end else begin
                    state <= ST_TW;
                end
            end
            ST_T4: begin
                if (cur_fetch && fetch_discard) fetch_discard <= 1'b0;
                if (nxt_live) begin
                    state      <= ST_T1;
                    cur_type   <= nxt_type;
                    cur_addr   <= nxt_addr;
                    cur_fetch  <= nxt_fetch;
                    cur_wr     <= nxt_wr;
                    cur_swap   <= nxt_swap;
                    cur_split1 <= nxt_split1;
                    cur_split2 <= nxt_split2;
                    cur_wdata  <= nxt_wdata;
                    cur_seg    <= nxt_seg;
                    cur_ube_n  <= nxt_ube_n;
                    ube_n      <= nxt_ube_n;
                    nxt_valid  <= 1'b0;
                end else begin
                    state    <= ST_TI;
                    cur_type <= BS_PASV;
                    cur_fetch  <= 1'b0;
                    cur_split1 <= 1'b0;
                    cur_split2 <= 1'b0;
                    cur_wr     <= 1'b0;
                    // NOTE: no commit evaluation at the T4 edge normally
                    // (measured) - EXCEPT a flush redirect at a prefetch
                    // T4, which commits immediately (measured, mission E).
                    // An EU access's T4 still defers to the next Ti eval.
                    if (q_flush && cur_fetch && pick_any) do_commit();
                end
            end
            default: state <= ST_TI;
        endcase
    end
end

//----------------------------------------------------------------------------
// pin-side outputs
//----------------------------------------------------------------------------
wire cycle_active = (state != ST_TI) && cur_type != BS_PASV;

assign bs = nxt_live ? nxt_type
          : (state == ST_T1 || state == ST_T2) ? cur_type
          : BS_PASV;

wire [15:0] wdata_lanes = cur_swap ? {cur_wdata[7:0], cur_wdata[15:8]}
                                   : cur_wdata;

assign ad_oe_addr = nxt_live || state == ST_T1;
assign ad_oe_ps   = !ad_oe_addr && cycle_active &&
                    (state == ST_T2 || state == ST_T3 ||
                     state == ST_TW || state == ST_T4);
assign ad_oe_data = ad_oe_ps && cur_wr;

assign ad_o = nxt_live           ? nxt_addr
            : (state == ST_T1)   ? cur_addr
            : {1'b0, psw_ie, cur_seg, wdata_lanes};

assign rd_n = !((state == ST_T2 || state == ST_T3 || state == ST_TW)
                && cycle_active && !cur_wr);

wire _unused = &{1'b0, fetch_cs_lin, ad_i[7:0]};

endmodule
