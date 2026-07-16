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
    input             eu_defer_wr,    // RMW write: exclude from the deferred
                                      // (eval_ext) commit; take the next plain
                                      // idle do_commit instead (measured law)
    input             eu_mem_acc,     // eu_req is a real load/store (not a
                                      // branch reservation) - starved-prefetch
                                      // override qualifier (F1 load extension)
    output            bus_phase,      // 2-cycle bus grid parity (T1=0)
    output            grid_phase,     // rebuild Stage 1: TRUE stretched-grid
                                      // parity (Tw holds the T3 slot; == bus_
                                      // phase at w0). Exported, not yet a
                                      // consumer (inert this stage).
    output            bus_t4,         // current cycle is a bus T4
    output      [2:0] bus_ts,         // T-state: 0=Ti 1=T1 2=T2 3=T3 4=T4 5=cTi
    input             eu_lock,      // LOCK (F0) active for the executing op
                                    // (Stage 6): drive BUSLOCK_N low from the
                                    // op's execution through its final locked
                                    // write's T4. Transparent to prefetch.
    output            buslock_n,    // max-mode LOCK output pin (active low)
    input             eu_hold,      // blocks prefetch, not request history
    input             eu_ready,
    input             eu_rsv_dhi,   // Phase 3: current coincident reservation
                                    // is the S_DHI reader/RMW-read disp-pop
                                    // class (owns the bus slot vs prefetch)
    input             eu_rsv_lead,  // eu_req=0 onset fix: mem-access reservation
                                    // LEADS eu_req by one EU-state (disp16 store
                                    // @ S_DHI). Consulted ONLY in eval_ext ->
                                    // w0-NEUTRAL. See pf_rsv_lead below.
    input             eu_rsv_push_calc, // Phase 3: ... the S_PUSH_CALC push
                                    // class (owns the slot only at q_cnt>=2)
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
    output            eu_rdone,      // early READ completion (mirror of
                                     // eu_wdone, cur_wr==0): the read's
                                     // zero-wait completion point (T4 at w0,
                                     // first Tw under waits). == eu_done at w0.
                                     // Marches read->read address chains on
                                     // the bus grid; read DATA is decoupled to
                                     // eu_rd_now (see biu_model / waits plan).
    output            bus_tw,        // "bus stretched this cycle" = state==TW.
                                     // Zero at w0; under waits it is the extra
                                     // wait cycles. Gate a dly countdown with
                                     // !bus_tw to make it count BUS cycles
                                     // (stay on the grid) instead of CPU cycles.
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
// Phase R: canonical commit descriptor. One packed struct carrying everything
// a bus cycle needs. During Phase R this is a pure alias of the existing
// pick_* wires (pick_desc below); direct-vs-staged delivery is metadata only.
//----------------------------------------------------------------------------
typedef struct packed {
    logic [2:0]  bus_type;
    logic [19:0] addr;
    logic        fetch;
    logic        wr;
    logic        swap;
    logic        split1;
    logic        split2;
    logic        wrap;
    logic [15:0] wdata;
    logic [1:0]  seg;
    logic        ube_n;
    logic [1:0]  kind;
} commit_desc_t;

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
// Stage 3 two-rhythm scheduler (discriminator: EU consumption activity).
// Isolation (biu_rebuild_isolation.md) found the fill-vs-steady discriminator:
// after a WAITED prefetch, if the EU is actively CONSUMING (recent q_pop
// activity) the chip paces the next fetch by draining the queue further
// (resume near occ<=2); if the EU is STALLED (no recent pops) the queue fills
// and the fetch resumes immediately at the occ<=4 refill threshold. The
// eval_ext immediate-resume-at-occ<=4 ignored consumption (the dominant waits
// drift). pf_drain applies the tighter threshold ONLY in the post-waited-
// prefetch window AND only while the EU is consuming.
// w0-NEUTRAL: pf_drain is only ever set on a Tw cycle -> always 0 at w0 ->
// prefetch_ok bit-identical (occ<=4).
reg        pf_drain;
reg  [7:0] pop_sr;                     // recent pop-now history (consumption)
wire [3:0] pop_cnt = {3'b0, pop_sr[0]} + {3'b0, pop_sr[1]} +
                     {3'b0, pop_sr[2]} + {3'b0, pop_sr[3]} +
                     {3'b0, pop_sr[4]} + {3'b0, pop_sr[5]} +
                     {3'b0, pop_sr[6]} + {3'b0, pop_sr[7]};
wire       eu_consuming = pop_cnt >= 4'd2;
wire [3:0] pf_lim = (pf_drain && eu_consuming) ? 4'd3 : 4'd4;
wire       prefetch_ok = !q_flush ? (!(eu_req || eu_hold) && occupied <= pf_lim &&
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
// during a push-absorb cycle (measured, EA tranche). ff_show requires
// !eval_ext (the idle-Ti far flush); a far flush whose redirect commits
// during the deferred-completion eval (eval_ext) cycle is the waited analog
// and must show E on that same commit row too (measured seed90018 w1, opc EA
// far jump: chip shows E at the eval_ext redirect commit, the TB deferred it
// to e_wait one cycle late). w0-NEUTRAL: eval_ext never fires at w0.
wire ff_evalext = flush_fast && q_flush && eval_ext && pick_ext && pick_fetch;
assign qs_e = (q_flush && flush_quiet) || e_wait_show || ff_show || ff_t4 ||
              ff_evalext;

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
reg  eu_req_p1, eu_req_p2, eu_ready_p1, eu_ready_p2;
reg  ext_flushed;
wire ext_ok     = eu_ready_p1 ||
                  (eu_req_p1 && eu_req_p2 && !ext_flushed);
// The RMW mem write (eu_defer_wr) qualifies for the deferred (eval_ext)
// commit under a STRICTER rule than the fitted store/load forms: only if
// its readiness was registered for the two sampling edges ending at T4
// (eu_ready_p1 && eu_ready_p2, i.e. ready ENTERING T4), not via rule A
// (ready only AT the T4 edge) or rule B (req-only reservation). Measured
// (sweep_rmw.py, ADD word[mem],imm w0-w5): when the write-ready asserts
// exactly AT the post-read prefetch's T4 (w1: rdy first high at that T4),
// the chip does NOT take the deferred eval - it commits at the next plain
// idle (rdT1->wrT1 = 14). When readiness asserts one+ cycle BEFORE T4
// (w3: rdy high through the prefetch's Tw), the chip DOES commit at the
// deferred eval (16). ext_ok_wr captures exactly this. The eu_req
// reservation blocks prefetch through the gap either way. S_WREQ is
// RMW-write-only (88/89 stores use S_REQ) so the fitted forms keep ext_ok.
wire ext_ok_wr  = eu_ready_p1 && eu_ready_p2;
wire want_eu    = eu_req && eu_ready &&
                  !(eval_ext && !(eu_defer_wr ? ext_ok_wr : ext_ok));

// EU access geometry
wire eu_split   = eu_word && eu_addr[0];
wire eu_ube_n   = eu_word ? 1'b0 : (eu_addr[0] ? 1'b0 : 1'b1);

wire        pick_any   = want_half2 || want_eu || prefetch_ok;
// EU-arbitration front (Stage 3): under waits, when a deferred-completion eval
// finds the queue STARVED (empty) and the pending EU access still only
// RESERVING (eu_req high, not yet ready - its address/data delayed by the
// wait), the chip prefetches to refill BEFORE the EU access (measured:
// seed90008 STM empties the queue, chip fetches 0x51a then stores; the
// eu_req reservation must not starve the prefetcher here). prefetch_ext adds
// exactly that override, and only in the eval_ext (waited) window -> w0-NEUTRAL
// (at w0 eval_ext never fires, so prefetch_ext == prefetch_ok bit-identical).
wire        pf_starved = (q_cnt == 3'd0) && !eu_hold && q_aged == 2'd0 &&
                         !q_flush;
// EU-arbitration front 3 (Stage 3): a mem-access reservation that first
// asserts AT the deferred-completion eval (eu_req high now but eu_req_p1==0 =
// did NOT lead the eval) is TOO LATE to claim this eval's slot. The fitted
// WRITE-half reservation law blocks the fresh prefetch only when the
// reservation LEADS the eval (eu_req present the cycle before); a coincident
// late reservation does not. Measured on the REP-string arbitration seeds
// (90020/90010/90017/90000/90012, all a4/a5/ab/ac/ad): at the last CODE
// fetch's T4 eu_req==0, at the eval_ext Ti eu_req==1/eu_ready==0/q_cnt==1 -
// the chip commits a refill CODE prefetch and the string access takes the
// next slot; the TB blocked prefetch on the coincident eu_req. Gated on
// occupied<=4 (queue has room) so it never fires when the queue is full (the
// fitted single-store forms sit at occ>4 with a LEADING reservation - both
// excluded). w0-NEUTRAL: eval_ext never fires at w0.
// Phase 3 (measured Phase 2k, chip ground truth + Codex GO, session 019f663c):
// a coincident (age-0) pending reservation OWNS the bus slot - the chip
// IDLEs/reserves rather than let the deferred-eval prefetch win - for an
// ENUMERATED source set: the S_DHI reader/RMW-read final-disp-pop class (chip
// reserves at q_cnt=1, the dominant over-prefetch cell), and the S_PUSH_CALC
// push class ONLY when the queue can still feed the decoder (q_cnt>=2). Every
// other/unobserved reservation source (S_RSV/S_MHI/S_JWAIT/S_DEC/...) keeps the
// baseline pf_late_rsv yield-to-CODE - do NOT force absent sources to reserve.
// The veto only narrows pf_late_rsv (the eval_ext waited-window override); it
// leaves prefetch_ok, pf_starved, ext_ok, ext_ok_wr untouched. w0-NEUTRAL:
// pf_late_rsv already requires eval_ext, which never fires at w0.
wire        owns_slot   = eu_rsv_dhi ||
                          (eu_rsv_push_calc && q_cnt >= 3'd2);
wire        pf_late_rsv = eval_ext && eu_req && !eu_req_p1 && !eu_ready &&
                          eu_mem_acc && eu_kind == K_MEM &&
                          occupied <= 4'd4 && q_aged == 2'd0 &&
                          !q_flush && !eu_hold && !owns_slot;
// eu_req=0 onset fix (session 019f663c, chip ground truth eureq0_char census +
// Codex staged GO): the chip's mem-access reservation LEADS the model's eu_req
// by one EU-state (measured: disp16 store reserves at S_DHI, model eu_req rises
// at S_RSV). At the eval_ext deferred-completion eval the model's eu_req is
// still 0, so prefetch_ok lets a DOOMED CODE prefetch win the slot where the
// chip has already reserved (7/7 class-1 cases). pf_rsv_lead SUPPRESSES that
// prefetch in the waited window only. w0-NEUTRAL: eval_ext never fires at w0
// (there the model's post-EA prefetch legitimately commits - 169000 golden).
// Distinct from pf_late_rsv/owns_slot: those require eu_req==1 (a coincident
// LATE reservation); here eu_req==0 (the reservation LEADS, not yet signalled).
wire        pf_rsv_lead = eval_ext && eu_rsv_lead &&
                          q_aged == 2'd0 && !q_flush && !eu_hold;
wire        prefetch_ext = (prefetch_ok ||
                           (eval_ext && pf_starved && eu_req && !eu_ready &&
                            eu_mem_acc && eu_kind == K_MEM) ||
                           pf_late_rsv) && !pf_rsv_lead;
wire        pick_ext   = want_half2 || want_eu || prefetch_ext;
// the eval_ext cycle would commit a NEAR-flush redirect prefetch: defer it one
// idle cycle (flush_hold) instead of committing here (see flush_hold decl).
wire        flush_defer = eval_ext && q_flush && !flush_fast &&
                          pick_ext && pick_fetch && !flush_hold;
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

// Phase R (R1): canonical commit descriptor as a pure alias of the pick_*
// wires. Not connected to sequential logic yet (unused this stage).
commit_desc_t pick_desc;
assign pick_desc = '{
    bus_type: pick_type,
    addr:     pick_addr,
    fetch:    pick_fetch,
    wr:       pick_wr,
    swap:     pick_swap,
    split1:   pick_split1,
    split2:   pick_split2,
    wrap:     pick_wrap,
    wdata:    pick_wdata,
    seg:      pick_seg,
    ube_n:    pick_ube_n,
    kind:     pick_kind
};

`ifndef SYNTHESIS
`ifdef VERILATOR
// Shadow check: every descriptor field equals its source wire (trivially
// true while pick_desc is a pure alias). Not compiled into synthesis.
always @(*) begin
    assert (pick_desc.bus_type == pick_type);
    assert (pick_desc.addr     == pick_addr);
    assert (pick_desc.fetch    == pick_fetch);
    assert (pick_desc.wr       == pick_wr);
    assert (pick_desc.swap     == pick_swap);
    assert (pick_desc.split1   == pick_split1);
    assert (pick_desc.split2   == pick_split2);
    assert (pick_desc.wrap     == pick_wrap);
    assert (pick_desc.wdata    == pick_wdata);
    assert (pick_desc.seg      == pick_seg);
    assert (pick_desc.ube_n    == pick_ube_n);
    assert (pick_desc.kind     == pick_kind);
end
`endif
`endif

//----------------------------------------------------------------------------
// Phase R (R4): named slot-request aliases. Each is textually equivalent to
// the state-machine branch condition that performs that commit today (state
// priority is part of the condition). Unused this stage - named, not
// consumed: R5 builds the shadow arbiter from them, R6 consumes them.
// (Forward references to eval_ext / ff_show / eval_at_t3 / nxt_live etc. are
// module-level nets/regs, resolved order-independently as elsewhere here.)
//----------------------------------------------------------------------------
// direct_request: the ST_TI combined direct-entry guard (eval_ext OR far-flush
// idle OR armed reader OR held near-flush) - one-clock-ahead display commits.
wire direct_request = ((eval_ext && pick_ext && !flush_defer) ||
                       (ff_show && pick_any)) ||
                      (defer_idle && want_eu) ||
                      (flush_hold && pick_ext && pick_fetch);

// ST_TI direct slots (below nxt_live in priority):
wire req_eval_ext   = state == ST_TI && !nxt_live &&
                      eval_ext && pick_ext && !flush_defer;
wire req_ff_ti      = state == ST_TI && !nxt_live && ff_show && pick_any;
wire req_defer_idle = state == ST_TI && !nxt_live && defer_idle && want_eu;
wire req_flush_hold = state == ST_TI && !nxt_live &&
                      flush_hold && pick_ext && pick_fetch;
// ST_TI staged plain prefetch/EU commit (stage_commit path), below the
// direct slots and the flush_defer/eval_ext teardown branches:
wire req_ti_plain   = state == ST_TI && !nxt_live &&
                      !direct_request && !flush_defer && !eval_ext && pick_any;
// ST_T3/TW staged completion eval (zero-wait T3->T4 edge):
wire req_t3_eval    = eval_at_t3 && pick_any;
// ST_T4 direct defer_t4 commit (below nothing; defer_t4 is first in T4):
wire req_defer_t4   = state == ST_T4 && defer_t4 && eu_req && eu_ready;
// ST_T4 far-flush mid-T4 direct commit (below defer_t4 and nxt_live):
wire req_ff_t4      = state == ST_T4 && !defer_t4 && !nxt_live &&
                      q_flush && cur_fetch && pick_any && flush_fast && evald;
// ST_T4 flush-fallback staged commit (below ff_t4 in the same else chain):
wire req_t4_flush_staged = state == ST_T4 && !defer_t4 && !nxt_live &&
                      q_flush && cur_fetch && pick_any && !(flush_fast && evald);

// Phase R (R2): staged capture as a descriptor-parameterized task. Writes
// d.* into nxt_*; delivery is staged (nxt_valid + nxt_live transition).
// Side effects preserved exactly: a fetch descriptor advances fetch_off; a
// new EU access (not a split-half continuation) asserts eu_started. Callers
// pass pick_desc, so d.* == pick_* bit-for-bit.
task automatic stage_commit(input commit_desc_t d);
    nxt_valid  <= 1'b1;
    nxt_type   <= d.bus_type;
    nxt_addr   <= d.addr;
    nxt_fetch  <= d.fetch;
    nxt_wr     <= d.wr;
    nxt_swap   <= d.swap;
    nxt_split1 <= d.split1;
    nxt_split2 <= d.split2;
    nxt_wrap   <= d.wrap;
    nxt_wdata  <= d.wdata;
    nxt_seg    <= d.seg;
    nxt_ube_n  <= d.ube_n;
    nxt_kind   <= d.kind;
    if (d.fetch) begin
        fetch_off <= fetch_off_sel + (fetch_word ? 16'd2 : 16'd1);
        if (!q_flush) fetch_cs <= fetch_cs;   // (flush handled below)
    end else if (want_eu && !want_half2) begin
        eu_started <= 1'b1;
    end
endtask

// Phase R (R3): direct-entry descriptor load. Performs ONLY the mechanically
// common operations shared by every one-clock-ahead direct commit: enter T1,
// clear tw_any/evald, load cur_* and ube_n from the descriptor. Source-
// specific side effects (fetch_off advance, eu_started, defer_idle/flush_hold/
// defer_t4 clearing) remain at the call sites. Callers pass pick_desc, so
// d.* == pick_* bit-for-bit.
task automatic enter_t1_direct(input commit_desc_t d);
    state      <= ST_T1;
    tw_any     <= 1'b0;
    evald      <= 1'b0;
    cur_type   <= d.bus_type;
    cur_addr   <= d.addr;
    cur_fetch  <= d.fetch;
    cur_wr     <= d.wr;
    cur_swap   <= d.swap;
    cur_split1 <= d.split1;
    cur_split2 <= d.split2;
    cur_wrap   <= d.wrap;
    cur_wdata  <= d.wdata;
    cur_seg    <= d.seg;
    cur_ube_n  <= d.ube_n;
    cur_kind   <= d.kind;
    ube_n      <= d.ube_n;
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

// NEAR-flush (Jcc/E9/loop) redirect +1-late under waits (Stage 5 / front-2b).
// Measured (seed90003/90018/90005, opc 73 Jcc, w1): when a near flush's
// q_flush asserts DURING the deferred-completion eval (eval_ext) cycle, the
// TB commits the redirect prefetch via the eval_ext mid-cycle path THAT cycle
// (display @T4+1), but the CHIP inserts exactly ONE more idle and mid-cycle-
// commits the redirect the NEXT idle cycle (display @T4+2). The far-flush
// (flush_fast: EA/BR/far-CALL) redirect is NOT deferred (it already matches at
// T4+1 via the ff/do_commit path) - only the NEAR flush gets the extra idle.
// flush_hold latches the deferral for exactly one cycle, then commits via the
// SAME mid-cycle path (state->T1 with the display this cycle) so it inserts
// ONE idle, not two (a plain do_commit here would over-shoot to T4+3).
// w0-NEUTRAL: eval_ext never fires at w0, so flush_defer/flush_hold are 0.
reg  flush_hold;

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
// Read-completion mirror of eu_wdone (cur_wr==0). At w0 there is no Tw so
// this is (T4 && evald) - the same cycle eu_done (eu_hand) asserts, i.e.
// bit-identical to eu_done at zero waits. Under waits it fires at the FIRST
// Tw (the zero-wait completion point), one cycle ahead of eu_done, so a
// read->read address chain marched on it keeps the next request/reservation
// up in time for the deferred completion eval to place it on the bus grid.
// The read DATA is NOT available at the first Tw (it lands at the last
// Tw/eu_rd_now); consumers must decouple the data via eu_rd_now/eu_rdata_now.
assign eu_rdone = eu_completing && !cur_wr &&
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
        flush_hold <= 1'b0;
        pf_drain   <= 1'b0;
        pop_sr     <= 8'd0;
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
        pop_sr <= {pop_sr[6:0], pop_now};   // recent consumption history
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
        if (q_flush && !flush_quiet && !ff_show && !ff_t4 && !ff_evalext)
            e_wait <= 1'b1;
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
                end else if (((eval_ext && pick_ext && !flush_defer) ||
                              (ff_show && pick_any)) ||
                             (defer_idle && want_eu) ||
                             (flush_hold && pick_ext && pick_fetch)) begin
                    // deferred (waited-cycle) completion eval OR the
                    // idle-window reg-EA reader early commit (defer_idle) OR
                    // the held near-flush redirect (flush_hold, one idle late):
                    // the picked cycle is displayed during THIS idle cycle
                    // and enters its T1 directly - one cycle ahead of the
                    // plain do_commit idle path (measured reader-commit law).
                    defer_idle <= 1'b0;
                    flush_hold <= 1'b0;
                    enter_t1_direct(pick_desc);
                    if (pick_fetch) begin
                        fetch_off <= fetch_off_sel +
                                     (fetch_word ? 16'd2 : 16'd1);
                    end else if (want_eu && !want_half2) begin
                        eu_started <= 1'b1;
                    end
                end else begin
                    defer_idle <= 1'b0;
                    if (flush_defer) begin
                        // near-flush redirect deferred one idle cycle: hold the
                        // redirect (queue already cleared + pointer redirected
                        // by the flush block) and commit it next idle cycle via
                        // the mid-cycle path (flush_hold trigger above).
                        flush_hold <= 1'b1;
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end else if (eval_ext) begin
                        // deferred eval found nothing: cycle teardown
                        // deferred from the end of T4
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end else if (pick_any) begin
                        stage_commit(pick_desc);
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
            ST_T1: begin state <= ST_T2; pf_drain <= 1'b0; end
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
                        if (pick_any) stage_commit(pick_desc);
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
                        enter_t1_direct(pick_desc);
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
                    if (q_flush && cur_fetch && pick_any && flush_fast &&
                        evald) begin
                        // EA far flush landing squarely on a prefetch T4: the
                        // redirect commits MID-T4 - the target CODE status/
                        // address ride THIS T4 row (ff_t4 display below, with
                        // QS=E) and T1 follows next cycle, one cycle ahead of
                        // the near-flush nxt_live path below (measured,
                        // fz8304 far-jump; near flushes keep the deferred
                        // display - E9/Jcc/loop golden + sweep exact).
                        // GATED ON evald (zero-wait cycle): at zero waits a
                        // fetch's completion eval always fires at the T3->T4
                        // edge (READY high), so evald==1 here - the fast
                        // mid-T4 commit is preserved. Under WAITS the eval is
                        // deferred (evald==0), and the chip likewise defers
                        // the far-flush redirect by one cycle (measured:
                        // fz84xxx w1 - the redirect commits during the cycle
                        // after T4, not mid-T4); evald==0 falls through to
                        // the near-flush do_commit path below (one cycle
                        // later), matching the chip's deferred display.
                        enter_t1_direct(pick_desc);
                        if (pick_fetch)
                            fetch_off <= fetch_off_sel +
                                         (fetch_word ? 16'd2 : 16'd1);
                    end else if (q_flush && cur_fetch && pick_any) begin
                        stage_commit(pick_desc);
                        cur_type   <= BS_PASV;
                        cur_fetch  <= 1'b0;
                        cur_split1 <= 1'b0;
                        cur_split2 <= 1'b0;
                        cur_wr     <= 1'b0;
                    end else if (!evald) begin
                        eval_ext    <= 1'b1;
                        ext_flushed <= q_flush;
                        pf_drain    <= cur_fetch && !q_flush;
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

// grid_phase (rebuild Stage 1) - the TRUE stretched-grid parity, the first-
// class replacement for ph_ff/bus_phase that the Stage-2/3 resume/eval/
// arbitration rewrite keys off. Identical to bus_phase EXCEPT a Tw cycle holds
// the T3 grid slot (phase 0) instead of toggling every clock - so every bus
// cycle contributes exactly two grid positions (T1/T3=0, T2/T4=1) regardless
// of the wait count N, and T4 is phase 1 for ANY N. The Stage-0 measurement
// (biu_rebuild_design.md 4a) proved grid_phase is the necessary+sufficient
// variable that the resume law flips on. w0-NEUTRAL: with no Tw, gph_now==ph_now
// and gph_ff tracks ph_ff, so grid_phase is bit-identical to bus_phase at w0
// (SVA below; the 169000 golden). INERT this stage: exported, no consumer
// re-pointed yet (that is Stage 2's intended behavior change).
reg  gph_ff;
wire gph_now = (state == ST_T1 || state == ST_T3) ? 1'b0
             : (state == ST_T2 || state == ST_T4) ? 1'b1
             : (state == ST_TW)                    ? 1'b0   // Tw = T3 slot
             : (state == ST_TI && nxt_live)        ? 1'b1
             :                                        gph_ff;
always_ff @(posedge clk) if (ce)
    gph_ff <= (state == ST_TW) ? gph_ff : ~gph_now;        // Tw: do not advance
assign grid_phase = gph_now;

`ifndef SYNTHESIS
// Stage-1 inertness invariant: in a bus cycle that has taken no Tw (the w0
// condition), grid_phase should equal bus_phase. Tracks whether a Tw has
// occurred since the last T1; the check is disabled once one has (that is
// exactly where the two are DESIGNED to diverge under waits).
//
// KNOWN LIMITATION (pre-existing since Stage 1, confirmed at 01c31e7): under
// waits this invariant is OVER-STRICT. For the load / MOV-imm forms (8B/89/B8)
// grid_phase diverges from bus_phase in a post-waited-cycle idle window even
// though cyc_saw_tw has reset at an intervening T1 - the gph_ff "hold across
// Tw" carry vs ph_ff's free toggle leaves the two idle-window phases offset
// until the next fetch re-syncs. grid_phase is currently INERT: the EU port
// (v30_eu grid_phase) is UNCONSUMED - every EU phase decision uses bus_phase -
// so this divergence has ZERO behavioral effect (w0/w1/w3 golden are all
// cycle-exact: 169000 / 1200 / 1200; silicon A/B w0/w1/w3 15/15 exact). The
// strict $error is therefore gated OFF by default so it does not abort the
// golden validation of those forms; re-enable `GRID_PHASE_STRICT` once the
// Phase-B resume scheduler CONSUMES grid_phase and its stretched-grid
// definition is corrected + re-validated (resume_scheduler_design.md).
reg cyc_saw_tw;
always_ff @(posedge clk)
    if (srst) cyc_saw_tw <= 1'b0;
    else if (ce)
        cyc_saw_tw <= (state == ST_T1) ? 1'b0 : (cyc_saw_tw | bus_tw);
`ifdef GRID_PHASE_STRICT
always_ff @(posedge clk)
    if (!srst && ce && !cyc_saw_tw && !bus_tw && (grid_phase !== bus_phase))
        $error("grid_phase != bus_phase in a no-Tw cycle (Stage-1 invariant)");
`endif
`endif

assign bus_t4 = state == ST_T4;

// BUSLOCK pin (Stage 6, measured law - sw/exp_lock.py / biu_model.md BUSLOCK):
// the LOCK output is a single continuous low pulse bracketing the locked op's
// bus footprint. It asserts while the locked instruction executes (eu_lock),
// stays low across the interleaved prefetch between the RMW read and write
// (transparent to prefetch), and RELEASES at the final locked WRITE's T4 (a
// bus-grid event). lock_done latches the release so a lingering eu_lock (the
// op has not fully retired yet) does not re-assert it; both clear when eu_lock
// drops at the locked op's retire.
reg lock_active, lock_done;
wire lock_wr_t4 = lock_active && cur_wr && !cur_fetch && (state == ST_T4);
always_ff @(posedge clk) begin
    if (srst) begin
        lock_active <= 1'b0;
        lock_done   <= 1'b0;
    end else if (ce) begin
        if (!eu_lock) begin
            lock_active <= 1'b0;
            lock_done   <= 1'b0;
        end else if (lock_wr_t4) begin
            lock_active <= 1'b0;
            lock_done   <= 1'b1;      // release at the locked write's T4
        end else if (!lock_done) begin
            lock_active <= 1'b1;      // assert through the locked op's cycles
        end
    end
end
// Pin: assert combinationally the cycle eu_lock first goes high (no register
// delay on the rising edge), and deassert AT the locked write's T4
// (combinational) - the chip holds LOCK high during that T4, not the cycle
// after. lock_active/lock_done carry the state across the interleaved prefetch
// and latch the release. Residual: the leading edge is ~2 cycles later than
// the chip (the chip sets its lock latch earlier in the F0 decode pipeline);
// the RELEASE (the grid-keyed, informative edge), prefetch-transparency, and
// single-continuous-span all match the chip exactly (sw/exp_lock.py).
assign buslock_n = ~((lock_active || (eu_lock && !lock_done)) && !lock_wr_t4);

// "bus stretched this cycle" tick: exactly the extra wait cycles a waited
// bus cycle inserts. Zero at w0 (no Tw), so a dly gated `if(!bus_tw)` is
// bit-identical at w0 and stays on the bus grid under waits.
assign bus_tw = state == ST_TW;
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
    eu_ready_p2 <= eu_ready_p1;
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
wire ff_t4   = flush_fast && q_flush && state == ST_T4 && cur_fetch &&
               pick_any && evald;
// idle-window reg-EA reader early commit: the armed request (defer_idle,
// now ready) drives its status/address during THIS idle cycle and enters
// T1 next cycle - the mid-cycle commit analogue of defer_show for a
// bus-idle landing rather than a fetch T4.
wire idle_commit = defer_idle && state == ST_TI && !nxt_live && want_eu;
wire ext_show = (eval_ext && pick_ext && !flush_defer) || defer_show ||
                ff_show || ff_t4 || idle_commit ||
                (flush_hold && pick_ext && pick_fetch);

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
