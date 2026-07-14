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
//   - A prefetch cannot commit during a push-absorb cycle (q_aged
//     nonzero, the cycle after a fetch T4) - measured on the boot loop.
//   - Queue flush: unified law (docs/facts/biu_model.md, mission E):
//     the internal flush cycle clears the queue, discards in-flight
//     fetch data (the bus cycle completes) and redirects the fetch
//     pointer; the redirect commits from the end of that cycle at the
//     normal eval points plus prefetch-T4 (flush-only), never at an EU
//     access's T4. The QS=E pin display follows the measured deferral
//     law (qs_e below). A committed-but-unstarted stale prefetch dies.
//   - Write cycles drive the write data on AD15:0 in the second half
//     of T1 (t1_half2).
//
//  Reset-vector sequencing (mission G): the EU holds a bus reservation
//  for 7 cycles after RESET release, then flush-redirects to FFFF:0000
//  through the ordinary flush machinery - reproducing the measured
//  boot pattern (QS=E at release+7, first fetch T1 at FFFF0h at
//  release+9), verified cycle-exact against the real boot capture
//  (sw/check_boot.py).
//
//  Wait states (mission H, verified cycle-exact on the waits=1 and
//  waits=3 tranches, tests/v30/v0.1-w1/-w3; biu_model.md "Wait states"):
//   - READY low at the end of T3/Tw inserts Tw states; the status pins
//     stay ACTIVE through T3/Tw until READY has been sampled high
//     (ready_prev display law) - at zero waits T3 already shows passive.
//   - The completion eval fires at the T3->T4 edge only in a zero-wait
//     cycle (READY high at two consecutive edges). A waited cycle's
//     eval runs DURING the cycle after T4 (eval_ext): it drives the
//     picked status/address mid-cycle and enters T1 directly; its own
//     cycle end is NOT an eval point. EU requests qualify mid-cycle
//     only with readiness registered during T4, or a 2-cycle-registered
//     req line with live readiness (flush at the T4 edge kills the
//     latter). The queue push and the EU handover (eu_done) follow the
//     eval by one cycle in all cases.
//   - eu_wdone (trap-chain law): the EU microcode marches from the
//     zero-wait completion point of its writes - the cycle after the
//     first T3 - so under waits its next push request sits ready and
//     is picked up by the deferred eval (mid-cycle rule A).
//
//============================================================================

module v30_biu (
    input             clk,
    input             ce,            // clock-enable: advance state this clk
    input             ce_half,       // clock-enable for the T1 negedge process
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
    input             halt_disp,     // EU decoded HALT: show the pseudo
                                     // cycle at the first quiet TI

    // queue consumer (EU). F/S queue status is driven by the EU via
    // v30_core; the E (flush) pin timing is BIU-generated (qs_e) per the
    // measured display law.
    output      [7:0] q_byte,
    output            q_avail,
    output            q_avail2,     // >= 2 poppable bytes
    output            q_fresh,      // head byte became poppable this cycle
    output            q_any,        // queue occupancy (incl. un-aged)
    output            qs_e,
    input             q_pop,
    input             q_flush,
    input      [15:0] flush_cs,
    input      [15:0] flush_ip,

    // EU bus access. eu_req refers to an access that has not started yet;
    // the EU drops it (or moves to the next access) on eu_started.
    input             eu_req,
    input             eu_soon,        // request asserts ready next cycle
    input             eu_soon_ea,     // eu_soon from an S_EA2 reg-EA reader/
                                      // sreg-store: enables the idle-window
                                      // early-commit path (defer_idle)
    input             eu_soon_ivt,    // NMI/INT IVT-read idle-window early-
                                      // commit lead (pre-IVT S_WAITX dly==1);
                                      // arms defer_idle like eu_soon_ea
    input             flush_fast,     // far-flush: redirect commits mid-cycle
    output            bus_phase,      // 2-cycle bus grid parity (T1=0)
    output            bus_t4,         // current cycle is a bus T4
    output      [2:0] bus_ts,         // T-state: 0=Ti 1=T1 2=T2 3=T3 4=T4 5=cTi
    input             eu_hold,      // blocks prefetch, not request history
    input             eu_ready,
    input             eu_wr,
    input             eu_fwd,       // write data = last read data (string
                                    // read->write forwarding at commit)
    input             eu_word,
    input       [1:0] eu_kind,     // 0=mem 1=io 2=inta 3=halt
    input             eu_wrap,     // offset==FFFF: split half2 wraps to
                                   // offset 0 of the same segment
    input      [19:0] eu_addr,
    input       [1:0] eu_seg,
    input      [15:0] eu_wdata,
    output reg        eu_started,    // pulse: request accepted, params latched
    output            eu_t1,         // first T1 cycle of the current EU access
    output            eu_done,       // handover: final T4 (zero-wait) or the
                                     // cycle after it (waited access)
    output            eu_wdone,      // early write completion: the READY
                                     // cycle of a waited write's final half,
                                     // its T4 at zero waits (trap chain law)
                                     // access (trap-chain slot anchor)
    output reg [15:0] eu_rdata,
    output            eu_rd_now,     // comb: EU read final data edge (end
                                     // of T3/TW) - early-consume strobe
    output     [15:0] eu_rdata_now,  // the data at that edge

    // TB backdoor: load fetch/queue state while in reset (see v30_core)
    input             bkd_load,
    input      [15:0] bkd_cs,
    input      [15:0] bkd_ip,        // offset of the first byte NOT queued
    input      [47:0] bkd_queue,
    input       [2:0] bkd_qlen
);

localparam bit [2:0] BS_INTA = 3'b000;
localparam bit [2:0] BS_IOR  = 3'b001;
localparam bit [2:0] BS_IOW  = 3'b010;
localparam bit [2:0] BS_HALT = 3'b011;
localparam bit [2:0] BS_CODE = 3'b100;
localparam bit [2:0] BS_MEMR = 3'b101;
localparam bit [2:0] BS_MEMW = 3'b110;
localparam bit [2:0] BS_PASV = 3'b111;

localparam bit [1:0] K_MEM  = 2'd0;
localparam bit [1:0] K_IO   = 2'd1;
localparam bit [1:0] K_INTA = 2'd2;
localparam bit [1:0] K_HALT = 2'd3;

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
reg        cur_wrap;       // split half2 wraps to offset 0 (eu_wrap)
reg [15:0] cur_wdata;
reg  [1:0] cur_seg;
reg        cur_ube_n;
reg  [1:0] cur_kind;

// committed next cycle (drives status/address during the current cycle)
reg        nxt_valid;
reg  [2:0] nxt_type;
reg [19:0] nxt_addr;
reg        nxt_fetch;
reg        nxt_wr;
reg        nxt_swap;
reg        nxt_split1;
reg        nxt_split2;
reg        nxt_wrap;
reg [15:0] nxt_wdata;
reg  [1:0] nxt_seg;
reg        nxt_ube_n;
reg  [1:0] nxt_kind;

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
// The queue push happens one cycle after the bus cycle's completion eval
// (measured, mission H): at zero waits the eval is the T3->T4 edge and
// the push lands at the end of T4; a waited cycle's eval is deferred to
// the end of T4 (see eval_at_t3/evald below), so its push lands at the
// end of the following cycle. push_pend carries the bytes across.
reg  [1:0] push_pend;      // bytes to push at this cycle's end
reg        push_pend_hi;   // pending byte came from an odd (upper) lane
wire [1:0] push_now = push_pend;
wire [2:0] cnt_next = q_cnt - {2'b0, pop_now} + {1'b0, push_now};
// bytes of an in-flight fetch not yet pushed (committed-next fetches never
// coincide with a commit evaluation, so only the current cycle counts)
wire [1:0] infl = (cur_fetch && state != ST_TI && push_now == 0 &&
                   !fetch_discard) ? (cur_word ? 2'd2 : 2'd1) : 2'd0;
wire [3:0] occupied = {1'b0, cnt_next} + {2'b0, infl};
// a prefetch cannot commit during a push-absorb cycle (q_aged nonzero,
// the cycle after a fetch T4) - measured on the boot loop; flush
// redirects are exempt (measured on the branch tranches)
wire       prefetch_ok = !q_flush ? (!(eu_req || eu_hold) && occupied <= 4 &&
                                     q_aged == 2'd0)
                                  : !(eu_req || eu_hold);   // flushed queue is empty

assign q_byte  = q_mem[q_rd];
assign q_avail = q_avl != 0;
assign q_avail2 = q_avl >= 3'd2;   // a byte remains after this pop
assign q_any    = q_cnt != 3'd0;   // fetched (not yet poppable) counts

// head byte became poppable THIS cycle (head was dry last cycle): the
// final-displacement pops (S_DISP8/S_DHI) defer one cycle when this
// coincides with an in-flight fetch's T2 (Campaign 4 disp-phase law)
reg q_head_dry_q;
always_ff @(posedge clk)
    if (srst) q_head_dry_q <= 1'b1;
    else if (ce) q_head_dry_q <= (q_avl == 3'd0);
assign q_fresh = q_head_dry_q;

//----------------------------------------------------------------------------
// QS=E display law (measured, mission E): the E code appears on the pins
// in the internal-flush cycle when the BIU is quiet; otherwise it waits
// for the first cycle with no doomed fetch in T1-T3/TW, no queue-push
// absorb (q_aged), and no ready-but-not-yet-started EU request (a flush
// raised together with an EU request - the trap - still shows at once).
//----------------------------------------------------------------------------
reg e_wait;
// a flush during T1-T3/TW dooms the in-flight fetch (its data is dropped
// via fetch_discard; a flush at the T4 edge instead suppresses the
// pending queue push directly)
wire flush_doom_fetch = cur_fetch && (state == ST_T1 || state == ST_T2 ||
                                      state == ST_T3 || state == ST_TW);
// for the E display, a doomed fetch counts as busy until its completion
// eval - which a waited cycle defers to the end of T4 (measured: the E
// display moves to the following Ti on the waits tranches). A cleanly
// completed fetch additionally counts as busy while its queue push is
// pending (push_pend, the eval_ext cycle) - a DISCARDED fetch has no
// pending push and shows E during its eval_ext cycle (measured: EB vs
// CALL under waits).
wire flush_busy_fetch = flush_doom_fetch ||
                        (cur_fetch && state == ST_T4 && !evald);
wire flush_quiet = !(cur_fetch && state != ST_TI) && (q_aged == 2'd0) &&
                   (push_pend == 2'd0);
// (c) ready-but-not-started EU request defers E - except when that
// request is being mid-cycle-committed this very cycle (its status
// cycle, measured: CALL's E under waits shows with the push status)
wire e_wait_show = e_wait && !flush_busy_fetch && (q_aged == 2'd0) &&
                   (push_pend == 2'd0) &&
                   !(eu_ready && !eu_started && !(eval_ext && want_eu));
// the far-flush mid-cycle commit displays E with the commit, even
// during a push-absorb cycle (measured, EA tranche)
assign qs_e = (q_flush && flush_quiet) || e_wait_show || ff_show || ff_t4;

//----------------------------------------------------------------------------
// HALT pseudo-cycle display (measured, block 4): the HALT status shows
// at the first idle (TI, nothing committed) cycle after the opcode pop;
// the next cycle is an address-strobe T1 driving the LAST FETCH address
// (fetch_phys - 2) on AD15:0 only, with UBE_N released high; no data
// phase follows. It never enters the commit machinery.
//----------------------------------------------------------------------------
reg halt_t1, halt_done;
wire halt_show = halt_disp && !halt_done && state == ST_TI &&
                 !nxt_live && !eval_ext;
always_ff @(posedge clk) begin
    if (srst || !halt_disp) begin
        halt_t1   <= 1'b0;
        halt_done <= 1'b0;
    end else if (ce) begin
        halt_t1 <= halt_show;
        if (halt_show) halt_done <= 1'b1;
    end
end

//----------------------------------------------------------------------------
// commit selection (combinational). Priority: second half of a split EU
// access, then a ready EU request, then prefetch.
//----------------------------------------------------------------------------
wire want_half2 = cur_split1 && !cur_fetch &&
                  (state != ST_TI || eval_ext);
// The deferred (eval_ext) mid-cycle commit only picks up EU requests
// that were visible early enough: either (A) readiness registered during
// T4, or (B) the req line registered for the two cycles before (up
// during T4 AND the cycle before T4) with readiness arriving live -
// and a flush raised at the T4 edge kills the rule-B slot (CALL's push
// commits one idle later). A request asserting later waits for the next
// idle-cycle-end eval - the eval_ext cycle's own end is NOT an eval
// point. All measured on the waits tranches: load d0 / store d2
// (2-cycle reservations) and requests ready during T4 commit mid-cycle;
// store d0/d1 and CALL's push commit at the following idle end.
reg  eu_req_p1, eu_req_p2, eu_ready_p1;
reg  ext_flushed;
wire ext_ok     = eu_ready_p1 ||
                  (eu_req_p1 && eu_req_p2 && !ext_flushed);
wire want_eu    = eu_req && eu_ready && !(eval_ext && !ext_ok);

// EU access geometry
wire eu_split   = eu_word && eu_addr[0];
wire eu_ube_n   = eu_word ? 1'b0 : (eu_addr[0] ? 1'b0 : 1'b1);

wire        pick_any   = want_half2 || want_eu || prefetch_ok;
wire  [2:0] pick_type  = want_half2 ? cur_type
                       : want_eu    ? (eu_kind == K_INTA ? BS_INTA
                                     : eu_kind == K_HALT ? BS_HALT
                                     : eu_kind == K_IO
                                       ? (eu_wr ? BS_IOW : BS_IOR)
                                       : (eu_wr ? BS_MEMW : BS_MEMR))
                                    : BS_CODE;
wire  [1:0] pick_kind  = want_half2 ? cur_kind
                       : want_eu    ? eu_kind : K_MEM;
// the HALT pseudo-cycle's T1 drives the last bus cycle's address on
// AD15:0 (measured: the stale address latch rides out on the pins)
wire [19:0] pick_addr  = want_half2 ? (cur_wrap ? cur_addr - 20'h0FFFF
                                                 : cur_addr + 20'd1)
                       : want_eu    ? (eu_kind == K_HALT ? cur_addr
                                                         : eu_addr)
                                    : fetch_phys;
wire        pick_fetch = !want_half2 && !want_eu;
wire        pick_wr    = want_half2 ? cur_wr : (want_eu && eu_wr);
wire        pick_swap  = want_half2 ? cur_swap : (want_eu && eu_addr[0]);
wire        pick_split1 = !want_half2 && want_eu && eu_split &&
                          eu_kind != K_INTA && eu_kind != K_HALT;
wire        pick_split2 = want_half2;
wire        pick_wrap  = !want_half2 && want_eu && eu_wrap;
// string read->write forwarding (eu_fwd): the write's data is the last
// read's data - taken live off the bus when the commit coincides with
// the read's own T3/Tw sampling edge, else from the read-data latch
wire [15:0] rd_asm  = cur_split2   ? {ad_i[7:0], eu_rdata[7:0]}
                    : cur_addr[0]  ? {ad_i[7:0], ad_i[15:8]}
                    :                ad_i;
wire [15:0] rd_fwd  = (t3_done && cur_fetch == 1'b0 && !cur_wr)
                      ? rd_asm : eu_rdata;
// early-consume strobe: the final data edge of a (non-split) EU read
assign eu_rd_now    = t3_done && !cur_fetch && !cur_wr && !cur_split1 &&
                      cur_type != BS_PASV;
assign eu_rdata_now = rd_asm;
wire [15:0] pick_wdata = want_half2 ? cur_wdata
                       : (eu_fwd ? rd_fwd : eu_wdata);
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
    nxt_wrap   <= pick_wrap;
    nxt_wdata  <= pick_wdata;
    nxt_seg    <= pick_seg;
    nxt_ube_n  <= pick_ube_n;
    nxt_kind   <= pick_kind;
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

// Commit-eval deferral under wait states (measured on the waits=1/3
// tranches): the completion eval fires at the T3->T4 edge only when READY
// was high at two consecutive sampling edges - i.e. only in a zero-wait
// cycle. A cycle that took any Tw defers its completion eval to the end
// of T4 (commits there at the same edge as the queue push; the following
// push-absorb cycle still blocks prefetch commits as at zero waits).
// evald tracks whether the current bus cycle's completion eval has fired.
wire eval_at_t3 = t3_done && ready_prev;
reg  evald;
reg  defer_t4;     // fetch-T3 eval deferred into T4 (eu_soon reservation)
reg  defer_idle;   // idle-window eu_soon reservation armed: commit the
                   // reg-EA read on the NEXT idle cycle (when it becomes
                   // ready), one cycle ahead of the plain idle do_commit -
                   // the chip's idle-window reader-commit law (no in-flight
                   // fetch for defer_t4's T4 to land on)
reg  eval_ext;     // deferred eval runs during this (post-T4) cycle

// a committed-but-stale prefetch dies in the flush cycle: transitions must
// not consume it
wire nxt_live = nxt_valid && !(q_flush && nxt_fetch);

// EU handover follows the completion eval by one cycle, exactly like the
// queue push (measured, mission H): at zero waits eu_done is the T4
// cycle; a waited access hands over during the cycle after T4.
reg eu_hand;
assign eu_done = eu_hand;
assign eu_t1 = state == ST_T1 && !cur_fetch && cur_type != BS_PASV;

wire eu_completing = !cur_fetch && cur_type != BS_PASV && !cur_split1;

// Early write completion (measured on the F7.6 waits tranches): the trap
// chain's microcode marches on from the write's zero-wait completion
// point - the cycle after the FIRST T3 - while the BIU stretches the
// cycle with Tw states; the next push request then sits ready for the
// (deferred) commit eval. At zero waits that cycle is T4, making
// eu_wdone == the old T4-cycle done there. Reads and the store/RMW
// retire path stay on eu_done. (w3 evidence: PS push T1 lands 2 cycles
// after the PSW push's T4, which needs the request up during T4 and the
// cycle before.)
reg tw_any;    // a Tw of the current bus cycle has already elapsed
assign eu_wdone = eu_completing && cur_wr &&
                  ((state == ST_TW && !tw_any) ||
                   (state == ST_T4 && evald));

always_ff @(posedge clk) begin
    if (srst) begin
        eu_started <= 1'b0;
        defer_t4   <= 1'b0;
        defer_idle <= 1'b0;
        state      <= ST_TI;
        nxt_valid  <= 1'b0;
        cur_type   <= BS_PASV;
        cur_fetch  <= 1'b0;
        cur_wr     <= 1'b0;
        cur_split1 <= 1'b0;
        cur_split2 <= 1'b0;
        cur_wrap   <= 1'b0;
        cur_swap   <= 1'b0;
        cur_seg    <= SEG_CS;
        cur_addr   <= '0;
        cur_wdata  <= '0;
        cur_ube_n  <= 1'b1;
        cur_kind   <= K_MEM;
        nxt_kind   <= K_MEM;
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
        tw_any     <= 1'b0;
        evald      <= 1'b0;
        push_pend  <= 2'd0;
        push_pend_hi <= 1'b0;
        eu_hand    <= 1'b0;
        eval_ext   <= 1'b0;
        ext_flushed <= 1'b0;
        if (bkd_load) begin
            fetch_cs  <= bkd_cs;
            fetch_off <= bkd_ip;
            q_cnt     <= bkd_qlen;
            q_avl     <= bkd_qlen;
            q_wr      <= (bkd_qlen >= 3'd6) ? 3'd0 : bkd_qlen;
            for (int i = 0; i < 6; i++)
                q_mem[i] <= bkd_queue[i*8 +: 8];
        end
    end else if (ce) begin
        eu_started <= 1'b0;
        // queue occupancy / availability pipeline
        q_cnt  <= cnt_next;
        q_avl  <= q_avl - {2'b0, pop_now} + {1'b0, q_aged};
        q_aged <= push_now;
        if (pop_now)
            q_rd <= (q_rd == 3'd5) ? 3'd0 : q_rd + 3'd1;
        push_pend <= 2'd0;      // pend is consumed one edge after it is set
        eu_hand   <= 1'b0;      // eu_done is a single handover cycle
        eval_ext  <= 1'b0;      // deferred eval lasts a single cycle
        if (push_now != 0) begin
            q_mem[q_wr] <= push_pend_hi ? fetch_data[15:8] : fetch_data[7:0];
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
            if (flush_doom_fetch)
                fetch_discard <= 1'b1;    // let the bus cycle finish, drop data
            if (nxt_valid && nxt_fetch)
                nxt_valid <= 1'b0;        // uncommit a stale fetch
        end

        // QS=E display deferral
        if (q_flush && !flush_quiet && !ff_show && !ff_t4) e_wait <= 1'b1;
        else if (e_wait_show)        e_wait <= 1'b0;

        // HALT pseudo-T1 releases UBE_N high
        if (halt_show) ube_n <= 1'b1;

        unique case (state)
            ST_TI: begin
                if (nxt_live) begin
                    state      <= ST_T1;
                    tw_any     <= 1'b0;
                    evald      <= 1'b0;
                    cur_type   <= nxt_type;
                    cur_addr   <= nxt_addr;
                    cur_fetch  <= nxt_fetch;
                    cur_wr     <= nxt_wr;
                    cur_swap   <= nxt_swap;
                    cur_split1 <= nxt_split1;
                    cur_split2 <= nxt_split2;
                    cur_wrap   <= nxt_wrap;
                    cur_wdata  <= nxt_wdata;
                    cur_seg    <= nxt_seg;
                    cur_ube_n  <= nxt_ube_n;
                    cur_kind   <= nxt_kind;
                    ube_n      <= nxt_ube_n;
                    nxt_valid  <= 1'b0;
                end else if (((eval_ext || ff_show) && pick_any) ||
                             (defer_idle && want_eu)) begin
                    // deferred (waited-cycle) completion eval OR the
                    // idle-window reg-EA reader early commit (defer_idle):
                    // the picked cycle is displayed during THIS idle cycle
                    // and enters its T1 directly - one cycle ahead of the
                    // plain do_commit idle path (measured reader-commit law).
                    defer_idle <= 1'b0;
                    state      <= ST_T1;
                    tw_any     <= 1'b0;
                    evald      <= 1'b0;
                    cur_type   <= pick_type;
                    cur_addr   <= pick_addr;
                    cur_fetch  <= pick_fetch;
                    cur_wr     <= pick_wr;
                    cur_swap   <= pick_swap;
                    cur_split1 <= pick_split1;
                    cur_split2 <= pick_split2;
                    cur_wrap   <= pick_wrap;
                    cur_wdata  <= pick_wdata;
                    cur_seg    <= pick_seg;
                    cur_ube_n  <= pick_ube_n;
                    cur_kind   <= pick_kind;
                    ube_n      <= pick_ube_n;
                    if (pick_fetch) begin
                        fetch_off <= fetch_off_sel +
                                     (fetch_word ? 16'd2 : 16'd1);
                    end else if (want_eu && !want_half2) begin
                        eu_started <= 1'b1;
                    end
                end else begin
                    defer_idle <= 1'b0;
                    if (eval_ext) begin
                        // deferred eval found nothing: cycle teardown
                        // deferred from the end of T4
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end else if (pick_any) begin
                        do_commit();
                    end else if ((eu_req && eu_soon_ea && !eu_ready) ||
                                 (eu_soon_ivt && q_cnt <= 3'd2)) begin
                        // idle window with a reg-EA reader reservation that
                        // becomes ready NEXT cycle and has no in-flight fetch
                        // for defer_t4 to land on: arm the early commit so the
                        // read commits directly in the idle window next cycle.
                        // eu_soon_ivt extends this to the NMI IVT read: its
                        // request (S_TRAP_IVT1) goes ready next cycle with
                        // eu_req+eu_ready together, so there is no eu_soon lead
                        // - the pre-IVT wait cycle supplies the lead directly.
                        // Gated on q_cnt<=2 (queue-starved): only a near-empty
                        // queue drove a doomed prefetch through the dispatch
                        // wait, establishing the live bus grid the chip commits
                        // the IVT read onto one cycle early (E+0). A saturated
                        // queue (the NOP-sled golden, occupied>4) runs no such
                        // prefetch -> stale idle -> the chip commits E+1 via the
                        // normal do_commit path, so it is excluded here.
                        defer_idle <= 1'b1;
                    end
                end
            end
            ST_T1: state <= ST_T2;
            ST_T2: state <= ST_T3;
            ST_T3, ST_TW: begin
                if (state == ST_TW) tw_any <= 1'b1;
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
                    // commit evaluation for the cycle after T4 - only in
                    // a zero-wait cycle (see eval_at_t3 above); a waited
                    // cycle evaluates at the end of T4 instead. The queue
                    // push of a completed fetch follows one cycle later.
                    if (eval_at_t3) begin
                        evald <= 1'b1;
                        if (cur_fetch && !fetch_discard && !q_flush) begin
                            push_pend    <= cur_word ? 2'd2 : 2'd1;
                            push_pend_hi <= cur_addr[0];
                        end
                        if (eu_completing) eu_hand <= 1'b1;
                        if (pick_any) do_commit();
                        else if (cur_fetch && eu_req && eu_soon &&
                                 !eu_ready)
                            defer_t4 <= 1'b1;   // re-eval during T4
                    end
                end else begin
                    state <= ST_TW;
                end
            end
            ST_T4: begin
                if (cur_fetch && fetch_discard) fetch_discard <= 1'b0;
                // waited cycle: deferred eval edge - schedule the queue
                // push of a completed fetch for the end of the next
                // cycle, or the EU handover for the next cycle
                if (!evald && cur_fetch && !fetch_discard && !q_flush) begin
                    push_pend    <= cur_word ? 2'd2 : 2'd1;
                    push_pend_hi <= cur_addr[0];
                end
                if (!evald && eu_completing) eu_hand <= 1'b1;
                if (defer_t4) begin
                    // deferred fetch-T3 eval (eu_soon): the request is
                    // ready now - commit mid-T4, enter T1 directly
                    defer_t4 <= 1'b0;
                    if (eu_req && eu_ready) begin
                        state      <= ST_T1;
                        tw_any     <= 1'b0;
                        evald      <= 1'b0;
                        cur_type   <= pick_type;
                        cur_addr   <= pick_addr;
                        cur_fetch  <= pick_fetch;
                        cur_wr     <= pick_wr;
                        cur_swap   <= pick_swap;
                        cur_split1 <= pick_split1;
                        cur_split2 <= pick_split2;
                        cur_wrap   <= pick_wrap;
                        cur_wdata  <= pick_wdata;
                        cur_seg    <= pick_seg;
                        cur_ube_n  <= pick_ube_n;
                        cur_kind   <= pick_kind;
                        ube_n      <= pick_ube_n;
                        eu_started <= 1'b1;
                    end else state <= ST_TI;
                end else if (nxt_live) begin
                    state      <= ST_T1;
                    tw_any     <= 1'b0;
                    evald      <= 1'b0;
                    cur_type   <= nxt_type;
                    cur_addr   <= nxt_addr;
                    cur_fetch  <= nxt_fetch;
                    cur_wr     <= nxt_wr;
                    cur_swap   <= nxt_swap;
                    cur_split1 <= nxt_split1;
                    cur_split2 <= nxt_split2;
                    cur_wrap   <= nxt_wrap;
                    cur_wdata  <= nxt_wdata;
                    cur_seg    <= nxt_seg;
                    cur_ube_n  <= nxt_ube_n;
                    cur_kind   <= nxt_kind;
                    ube_n      <= nxt_ube_n;
                    nxt_valid  <= 1'b0;
                end else begin
                    state <= ST_TI;
                    // NOTE: no commit evaluation at the T4 edge of a
                    // zero-wait cycle (measured) - EXCEPT a flush
                    // redirect at a prefetch T4, which commits
                    // immediately (measured, mission E). A WAITED cycle's
                    // deferred completion eval instead runs DURING the
                    // following cycle (eval_ext): it sees EU requests
                    // that assert in that cycle, drives the committed
                    // status/address mid-cycle, and enters T1 directly at
                    // its end (measured, mission H waits tranches). The
                    // completed cycle's identity (split flags etc.) is
                    // kept across the eval_ext cycle.
                    if (q_flush && cur_fetch && pick_any && flush_fast) begin
                        // EA far flush landing squarely on a prefetch T4: the
                        // redirect commits MID-T4 - the target CODE status/
                        // address ride THIS T4 row (ff_t4 display below, with
                        // QS=E) and T1 follows next cycle, one cycle ahead of
                        // the near-flush nxt_live path below (measured,
                        // fz8304 far-jump; near flushes keep the deferred
                        // display - E9/Jcc/loop golden + sweep exact).
                        state      <= ST_T1;
                        tw_any     <= 1'b0;
                        evald      <= 1'b0;
                        cur_type   <= pick_type;
                        cur_addr   <= pick_addr;
                        cur_fetch  <= pick_fetch;
                        cur_wr     <= pick_wr;
                        cur_swap   <= pick_swap;
                        cur_split1 <= pick_split1;
                        cur_split2 <= pick_split2;
                        cur_wrap   <= pick_wrap;
                        cur_wdata  <= pick_wdata;
                        cur_seg    <= pick_seg;
                        cur_ube_n  <= pick_ube_n;
                        cur_kind   <= pick_kind;
                        ube_n      <= pick_ube_n;
                        if (pick_fetch)
                            fetch_off <= fetch_off_sel +
                                         (fetch_word ? 16'd2 : 16'd1);
                    end else if (q_flush && cur_fetch && pick_any) begin
                        do_commit();
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end else if (!evald) begin
                        eval_ext    <= 1'b1;
                        ext_flushed <= q_flush;
                    end else begin
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end
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

// Internal 2-cycle grid parity: T1/T3 = 0, T2/T4 = 1; idle cycles keep
// toggling freely from the last bus cycle (measured on the BRK tranche:
// the vector-pop cycle's parity selects the IVT-read slot). Zero-wait
// definition; Tw phases not calibrated.
reg  ph_ff;
wire ph_now = (state == ST_T1 || state == ST_T3) ? 1'b0
            : (state == ST_T2 || state == ST_T4) ? 1'b1
            : (state == ST_TI && nxt_live) ? 1'b1   // committed pre-T1 slot
            : ph_ff;
always_ff @(posedge clk) if (ce) ph_ff <= ~ph_now;
assign bus_phase = ph_now;
assign bus_t4 = state == ST_T4;
assign bus_ts = (state == ST_T1) ? 3'd1
              : (state == ST_T2) ? 3'd2
              : (state == ST_T3 || state == ST_TW) ? 3'd3
              : (state == ST_T4) ? 3'd4
              : nxt_live ? 3'd5 : 3'd0;

// Status display: active from commit through T2 always; through T3/TW
// while READY has not yet been sampled high in this bus cycle (measured
// on the waits=1/3 tranches: T3 and every Tw of a waited cycle show the
// active status mid-cycle, T4 is passive again). At zero waits READY is
// already high at the end of T2, so T3 displays passive - the pre-waits
// law. ready_prev is READY at the last sampling edge.
reg ready_prev;
always_ff @(posedge clk) if (ce) ready_prev <= ready;
always_ff @(posedge clk) if (ce) begin
    eu_req_p1   <= eu_req && !eu_started;
    eu_req_p2   <= eu_req_p1;
    eu_ready_p1 <= eu_ready && !eu_started;
end

// ext_show: the deferred eval displays the picked cycle's status/address
// during the eval_ext cycle itself (mid-cycle commit).
// defer_show: a fetch T3 eval that found a held-but-not-yet-ready EU
// request (eu_soon) re-runs during T4: the (now ready) request drives
// its status/address mid-T4 and enters T1 directly at the T4 edge
// (measured on the BRK/BRKV tranches).
wire defer_show = defer_t4 && state == ST_T4 && eu_req && eu_ready;
// far-transfer flush (EA): the redirected prefetch commits mid-cycle in
// the flush cycle itself (E and the CODE commit share the row; measured)
wire ff_show = flush_fast && q_flush && state == ST_TI && !nxt_live &&
               !eval_ext && pick_any;
// ff_t4: the same EA far flush landing on a prefetch T4 (not an idle Ti) -
// the redirect status/address ride that T4 row and T1 follows next cycle
// (measured, fz8304). Mirrors the mid-T4 commit taken in the state machine.
wire ff_t4   = flush_fast && q_flush && state == ST_T4 && cur_fetch && pick_any;
// idle-window reg-EA reader early commit: the armed request (defer_idle,
// now ready) drives its status/address during THIS idle cycle and enters
// T1 next cycle - the mid-cycle commit analogue of defer_show for a
// bus-idle landing rather than a fetch T4.
wire idle_commit = defer_idle && state == ST_TI && !nxt_live && want_eu;
wire ext_show = (eval_ext && pick_any) || defer_show || ff_show || ff_t4 ||
                idle_commit;

assign bs = (halt_show || halt_t1) ? BS_HALT
          : nxt_live ? nxt_type
          : ext_show ? pick_type
          : (state == ST_T1 || state == ST_T2) ? cur_type
          : ((state == ST_T3 || state == ST_TW) && !ready_prev) ? cur_type
          : BS_PASV;

wire [15:0] wdata_lanes = cur_swap ? {cur_wdata[7:0], cur_wdata[15:8]}
                                   : cur_wdata;

// write cycles switch AD15:0 from address to write data in the second
// half of T1 (measured: golden MEMW T1 rows carry the write data in the
// data-phase sample). Negedge-registered so the external T1-falling-edge
// address latch still sees the address.
reg t1_half2;
always @(negedge clk) if (ce_half) t1_half2 <= (state == ST_T1);

// INTA cycles drive no address: the commit display and T1 leave AD15:0
// floating; T1 drives AD19:16 = 0 only (measured float pattern). HALT
// pseudo-cycles drive AD15:0 only (stale address), AD19:16 float.
wire [1:0] disp_kind = nxt_live ? nxt_kind
                     : ext_show ? pick_kind : cur_kind;
wire disp_inta = disp_kind == K_INTA &&
                 (nxt_live || ext_show || state == ST_T1);

assign ad_oe_addr = (nxt_live || ext_show || state == ST_T1) &&
                    !disp_inta;
assign ad_oe_ps   = (!ad_oe_addr && cycle_active &&
                     (state == ST_T2 || state == ST_T3 ||
                      state == ST_TW || state == ST_T4) &&
                     cur_kind != K_HALT && !disp_inta) ||
                    disp_inta;
assign ad_oe_data = (ad_oe_ps && cur_wr && !disp_inta) || halt_t1 ||
                    halt_show;

assign ad_o = (halt_t1 || halt_show)
                                 ? {4'h0, fetch_phys[15:0] - 16'd2}
            : disp_inta          ? 20'h0
            : nxt_live           ? nxt_addr
            : ext_show           ? pick_addr
            : (state == ST_T1)   ? (cur_wr && t1_half2
                                    ? {cur_addr[19:16], wdata_lanes}
                                    : cur_addr)
            : {1'b0, psw_ie, cur_seg, wdata_lanes};

assign rd_n = !((state == ST_T2 || state == ST_T3 || state == ST_TW)
                && cycle_active && !cur_wr);

wire _unused = &{1'b0, fetch_cs_lin, ad_i[7:0]};

endmodule
