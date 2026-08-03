//============================================================================
//
//  v30u_biu - the ucore bus-interface unit.
//
//  THIS MODULE IS A TRANSLITERATION OF sim/biu_timed.{h,cpp}.  Every mechanism
//  carries its ledger tag (M1..M23, M2r, M5b, F1..F3) and the reference
//  model's own words, condensed.  The governance rule (hdl/rtl/ucore/README.md)
//  is that the model is the SPEC: an RTL-vs-sim divergence is a bug HERE.
//
//  --- THE SPINE: ONE EVAL INSTANT, DERIVED FROM ONE FLOP -------------------
//
//  M2r says the READY sample is the only wait-state mechanism and that it is
//  ONE INSTANT: the CPU registers READY at the end of every clock and one
//  clock later it (a) releases the status register and (b) runs the completion
//  eval at that clock's end.  The reference model computes the instant from
//  the wait count it knows (`e = w==0 ? 2 : 3+w`); the RTL does not know the
//  wait count and does not need to -- the instant falls out of two local
//  quantities:
//
//      eval instant  ==  the first clock with  dage >= 3  and  ready_prev
//
//  where `dage` is this cycle's age counted from its DISPLAY clock (0 on the
//  display) and `ready_prev` is the registered READY pin.  That this IS the
//  model's instant at every wait level, for the rig of hdl/rtl/nec_bus.sv:
//
//    w0   READY is high from T1 entry.  T1 = disp+1, so dage>=3 first happens
//         at T3 = index 2 == the model's `eval_i` at zero waits.
//    wN   READY is low from T1 entry and high from the LAST Tw, so ready_prev
//         is first high at T4 == index 3+N == the model's `eval_i`.
//    M22  a cycle whose T1 the bus made WAIT: the model counts the zero-wait
//         instant from the DISPLAY (`disp+3`), not from the T1.  That is
//         literally `dage >= 3`.  No second rule, no wait counter.
//
//  The HALT pseudo-cycle is the one access that does not go through the
//  arbiter (the HLT micro-row writes the status register directly) and its
//  MEASURED status release is at index 1 -- `dage >= 2`, wait-independent.
//  That is M21, and it is the only exception in the module.
//
//  Everything else is a FIXED OFFSET from the eval instant `e`:
//      e     status goes passive; OPR is released to a `-> OPR` row
//      e+1   the DISPLAY clock
//      e+2   the winner's T1; eu_done (read handover, store retire)
//      e+3   a fetched byte becomes POPPABLE
//  ...so the module carries `sev` (clocks since this cycle's own eval) and
//  initialises all three landing windows from it.  See the T4 block.
//
//  --- ABSOLUTE CLOCKS -> BOUNDED RELATIVE COUNTERS -------------------------
//
//  Every absolute `long` clock in the model (cmt_t1_, cmt_expire_, pf_land_*,
//  pf_infl_to_, push_absorb_*, the QByte ready stamps) is re-expressed as a
//  small counter, with a SYNTHESIS bound assertion (campaign risk #2).
//
//  --- THE EDGE ------------------------------------------------------------
//
//  The registers hold the state the model has at the START of `tick(c)`, i.e.
//  AFTER its pre-row block.  One CE-high posedge therefore performs, in the
//  model's own order and with blocking assignments (they ARE its sequential
//  semantics; this is a single process, so nothing observes an intermediate):
//
//     (a) capture the clock-c predicates that later steps must not re-read
//     (b) the EU's own acts, which the model makes at `clk_ == c` BEFORE
//         tick(c) runs: pop, post, pair, susp, flush
//     (c) tick(c)'s end-of-clock block: advance the cycle, land the bytes
//     (d) tick(c)'s completion / idle / flush eval
//     (e) tick(c+1)'s PRE-ROW block: expire the announcement, open the T1,
//         let a pending HALT take the register
//     (f) age the relative counters into their clock-c+1 values
//
//  ONE interface consequence, booked as a mapping note (U1 -> U2): the model's
//  `note_halt` / `unhalt` land in tick(c)'s PRE-ROW block, which in RTL is the
//  edge ending c-1.  `eu_halt` / `eu_unhalt` are therefore specified to LEAD
//  by one clock -- the same one-row-early control decode F2 already measures
//  for SUSP.  Nothing else in the interface leads.
//
//  --- CE DISCIPLINE (docs/notes/ce_plan.md) --------------------------------
//
//  Nothing clocked runs unless `srst` or `ce`; reset is ungated so `bkd_load`
//  fires regardless of CE.  There is exactly ONE negedge process, `t1_half2`
//  (the T1 AD half), gated by `ce_half`.
//
//============================================================================

module v30u_biu (
    input             clk,
    input             ce,
    input             ce_half,
    input             srst,

    // --- chip pins (composed in the top) ---
    output      [2:0] bs,
    output     [19:0] ad_o,
    output            ad_oe_addr,
    output            ad_oe_ps,
    output            ad_oe_data,
    output            ube_n,
    output            rd_n,
    output      [1:0] qs,          // F1: the BIU owns the QS port
    input      [15:0] ad_i,
    input             ready,

    // --- machine state the pins carry (M9) ---
    input             psw_ie,
    input             md8080,

    // --- queue port (the consumer side) ---
    output      [7:0] q_byte,      // the front byte
    output            q_ripe,      // ...and it may be popped THIS clock (M3)
    output      [3:0] q_cnt_o,
    input             q_pop,       // consumer takes it (qualify with q_ripe)
    input             q_first,     // this pop is an F (instruction first byte)
    input             q_flush,     // flush + redirect, acts on THIS clock
    input      [15:0] flush_cs,
    input      [15:0] flush_ip,

    // --- EU bus requests (M10: ONE request slot) ---
    input             eu_post,     // post an access this clock
    input       [2:0] eu_bs,       // 0 INTA 1 IOR 2 IOW 5 MEMR 6 MEMW
    input      [19:0] eu_addr,
    input       [1:0] eu_seg,      // S4:S3 -- 0 ES 1 SS 2 CS/none 3 DS
    input             eu_word,
    output            eu_slot_busy,
    input             eu_pair,     // pair write data into the reserved cycle
    input      [15:0] eu_wdata,
    output     [15:0] eu_rdata,
    output            eu_rd_done,  // pulse at a completed read's e+2
    output            eu_wr_done,  // pulse at a completed write's e+2
    output            eu_opr_free, // 11.4 / M13: the store lets go of OPR

    // --- prefetch control ---
    input             eu_susp,     // F2: SUSP, one row early
    input             eu_resume,
    input             eu_halt,     // M20: the HLT row's status write (leads 1)
    input             eu_unhalt,   // M20: the wake (leads 1)
    output            halted_o,

    // --- backdoor / reset injection ---
    input             bkd_load,
    input      [15:0] bkd_cs,
    input      [15:0] bkd_ip,
    input      [47:0] bkd_queue,
    input       [2:0] bkd_qlen,

    // --- save-state ---
    input       [8:0] ss_addr,
    input      [15:0] ss_wdata,
    input             ss_we,
    output reg [15:0] ss_rdata,
    output            ss_bus_quiet
);

import v30_ss_pkg::*;

// rows.h encodings -- the comparator stack's own
localparam bit [2:0] BS_INTA = 3'd0, BS_IOR = 3'd1, BS_IOW = 3'd2,
                     BS_HALT = 3'd3, BS_CODE = 3'd4, BS_MEMR = 3'd5,
                     BS_MEMW = 3'd6, BS_PASV = 3'd7;
localparam bit [2:0] TS_TI = 3'd0, TS_T1 = 3'd1, TS_T2 = 3'd2,
                     TS_T3 = 3'd3, TS_TW = 3'd4, TS_T4 = 3'd5;
localparam bit [1:0] QS_NONE = 2'd0, QS_FIRST = 2'd1,
                     QS_EMPTY = 2'd2, QS_SUBSEQ = 2'd3;

//============================================================================
// STATE
//============================================================================

// --- the RUNNING cycle -----------------------------------------------------
reg        run;
reg  [2:0] ts;            // T-state during this clock
reg  [2:0] cur_bs;
reg [19:0] cur_addr;
reg [15:0] cur_data;      // read data latched at T2 / paired write data
reg        cur_ube_n;
reg  [1:0] cur_seg;
reg        cur_fetch;
reg        cur_halt;
reg        cur_noaddr;    // M15: an INTA drives no address
reg        cur_wr;
reg        cur_need;      // S5: reserved, data not paired yet
reg        cur_rd_last;   // a SPLIT is ONE access: releases on the 2nd cycle
reg  [1:0] cur_pn;        // queue bytes this fetch delivers (0 = doomed)
reg        cur_late_t1;   // M23: this T1 did NOT open at disp+1
reg        evald;         // the completion eval has fired for this cycle
reg  [1:0] sev;           // clocks since that eval (bounded, asserted)
reg  [2:0] dage;          // this cycle's age from its own DISPLAY clock

// --- the ANNOUNCEMENT (the registered status output, M2) -------------------
reg        cmt_valid;
reg  [2:0] cmt_bs;
reg [19:0] cmt_addr;
reg [15:0] cmt_data;
reg        cmt_ube_n;
reg  [1:0] cmt_seg;
reg        cmt_fetch;
reg        cmt_halt;
reg        cmt_noaddr;
reg        cmt_wr;
reg        cmt_need;
reg        cmt_rd_last;
reg  [1:0] cmt_pn;
reg  [2:0] cdage;         // M22: clocks since the DISPLAY (saturates)
reg [15:0] cmt_prev_fp;   // fetch_ptr before this fetch took it
reg        cmt_was_owed;  // M19's latch as it stood before the grant

// --- pad retention ---------------------------------------------------------
reg        last_ube;
reg [15:0] last_fetch_addr;

// --- the queue (M3) --------------------------------------------------------
reg  [7:0] q_mem [0:5];
reg  [2:0] q_head;
reg  [3:0] q_cnt;
reg  [1:0] grn_n;         // newest bytes not yet POPPABLE
reg  [1:0] grn_ttl;       // ...for this many more clocks (ready at e+3)
reg [15:0] fetch_ptr;
reg [15:0] cs_r;

// --- the prefetch scheduler ------------------------------------------------
reg        suspended;
reg        halted;        // S8/S9: once halted the prefetcher never runs again
reg        halt_pending;  // M20: the HLT row's write WAITING for the register
reg        pf_owed;       // M19: the redirect is a STANDING request
reg        pf_arm;        // M7: the eligibility answer, sampled at T3
reg        pf_land;       // M6: keyed to T4, ONE clock, wait-independent
reg  [1:0] infl_ttl;      // M7b: the outstanding-fetch term
reg  [1:0] infl_n;
reg  [1:0] absorb_ttl;    // F1(b): the QS port while the bytes land
reg        no_eval;       // M2r: the display slot is NOT an eval point
reg        flush_eval;    // F3: the flush-only T4 eval point
reg        e_pend;        // F1: a parked QS=E

// --- the EU request slot (M10) and its 2-deep backing store ----------------
reg  [1:0] rq_n;
reg  [2:0] rq_bs   [0:1];
reg [19:0] rq_addr [0:1];
reg [15:0] rq_data [0:1];
reg        rq_ube  [0:1];
reg  [1:0] rq_seg  [0:1];
reg        rq_noaddr [0:1];
reg        rq_wr   [0:1];
reg        rq_need [0:1];
reg        rq_last [0:1];
reg        slot_busy;
reg        slot_accept;
reg        opr_held;
reg  [1:0] done_ctr;      // eu_done lands at e+2 -- see the T4 block
reg        done_wr;
reg        rd_done_p;
reg        wr_done_p;
reg        opr_free_p;
reg [15:0] rd_val;        // OPR, shadowed (see M5b / the string loops)

// --- M2r: the ONLY wait mechanism -----------------------------------------
reg        ready_prev;

// --- the one negedge process ----------------------------------------------
reg        t1_half2;

//============================================================================
// COMBINATIONAL VIEWS  (all read ONLY at the top of the edge, see step (a))
//============================================================================

// M9: S6 is the 8080 EMULATION-MODE bit, S5 is IE, S4:S3 the segment code.
function automatic [3:0] data_ps(input [1:0] segc);
    data_ps = {md8080, psw_ie, segc};
endfunction

// F2 (generalised): SUSP -- and an EU bus request, which reaches the BIU
// through the same one-row-early control decode -- takes back a fetch the
// eval has just chosen, before its status reaches the pins.
wire ann_kill  = (eu_susp || eu_post || q_flush) && cmt_valid && cmt_fetch &&
                 (cdage == 3'd0);
// M2: `cmt_valid` is cleared when its T1 opens, so "an announcement stands"
// IS "this clock is a display clock".
wire display   = cmt_valid && !ann_kill;

// M1/M2r: the eval instant.  See the header.
wire eval_inst = run && !evald &&
                 (cur_halt ? (dage >= 3'd2)
                           : ((dage >= 3'd3) && ready_prev));
// M2: ...and the status register is RELEASED at that instant (inclusive).
wire st_rel    = evald || eval_inst;
// M21: from the HALT's status release on there is no bus cycle left to
// arbitrate, so EVERY clock is an ordinary idle eval.
wire halt_free = run && cur_halt && evald;

// M3: the front byte is poppable when it is not one of the green ones.
wire [3:0] poppable = (grn_ttl != 2'd0) ? (q_cnt - {2'b0, grn_n}) : q_cnt;
assign q_ripe   = poppable != 4'd0;
assign q_byte   = q_mem[q_head];
assign q_cnt_o  = q_cnt;
assign halted_o = halted;

// F1: a fetch owns the QUEUE PORT from its T1 until its bytes are in.  It
// holds it THROUGH its completion eval (`!evald`); the landing clocks are
// `absorb_ttl`.  A DOOMED fetch pushes nothing and lets go at the eval.
wire qs_port_fetch = run && cur_fetch && !evald;
wire pop_now       = q_pop && q_ripe;
// F1, `e_from`: the queue port is not free on the FLUSH CLOCK ITSELF if a bus
// cycle still owns it -- and only a FETCH owns it, so a flush landing on the
// clock an EU read opens its T1 still takes the port at once.  From the next
// clock on the term is vacuous (`c >= e_from` always holds), which is why it
// is a term of the flush clock and not a flop.
wire e_from_block = q_flush && run && cur_fetch;
wire qs_e_now = (e_pend || q_flush) && !pop_now && !e_from_block &&
                (absorb_ttl == 2'd0) && !qs_port_fetch &&
                // (c) a ready-but-not-started EU request owns the next slot
                // and the flush display waits for that request's STATUS
                // clock -- except on the flush clock itself.
                ((rq_n == 2'd0) || q_flush ||
                 (cmt_valid && !cmt_fetch) || (run && !cur_fetch));

assign qs = qs_e_now ? QS_EMPTY
          : pop_now  ? (q_first ? QS_FIRST : QS_SUBSEQ)
                     : QS_NONE;

assign eu_slot_busy = slot_busy;
assign eu_rdata     = rd_val;
assign eu_rd_done   = rd_done_p;
assign eu_wr_done   = wr_done_p;
assign eu_opr_free  = opr_free_p;
assign ss_bus_quiet = !run && !cmt_valid && (rq_n == 2'd0) && !halt_pending;

//----------------------------------------------------------------------------
// PIN DRIVE.  The comparator stack samples AD twice per clock: mid-clock (the
// ADDRESS phase) and at the clock's end (the DATA phase).  `t1_half2` is the
// negedge flop that switches a WRITE's AD15-0 from address to write data, so
// the external T1-falling-edge address latch still sees the address.
//----------------------------------------------------------------------------
wire disp_inta = display && cmt_noaddr;
wire cur_inta  = run && (ts == TS_T1) && cur_noaddr;
wire halt_pin  = (display && cmt_halt) || (run && cur_halt);

assign bs = display        ? cmt_bs
          : (run && !st_rel) ? cur_bs
                             : BS_PASV;

// M2: UBE is NOT part of the status register -- it changes ONE CLOCK AFTER
// the status does, so the DISPLAY clock keeps the old UBE.
assign ube_n = (display && (cdage != 3'd0)) ? cmt_ube_n
             : run                          ? cur_ube_n
                                            : last_ube;

// M23: the address one-shot is fired by the DISPLAY and is ONE CLOCK LONG;
// where the bus made the T1 wait it has already expired and A19-16 is back on
// the segment status while A15-0 holds the address by pad retention.
wire [19:0] t1_addr = cur_late_t1 ? {data_ps(cur_seg), cur_addr[15:0]}
                                  : cur_addr;

assign ad_o = halt_pin                ? {4'h0, last_fetch_addr}
            : (disp_inta || cur_inta) ? 20'h0
            : display                 ? cmt_addr
            : (run && (ts == TS_T1))  ? (cur_wr && t1_half2
                                         ? {cur_addr[19:16], cur_data}
                                         : t1_addr)
                                      : {data_ps(cur_seg), cur_data};

assign ad_oe_addr = (display || (run && (ts == TS_T1))) &&
                    !disp_inta && !cur_inta && !halt_pin;
assign ad_oe_ps   = (!ad_oe_addr && !halt_pin && run &&
                     (ts != TS_T1) && (ts != TS_TI)) ||
                    disp_inta || cur_inta;
assign ad_oe_data = (run && cur_wr && !cur_halt && !cur_noaddr &&
                     (ts != TS_TI) && !display) || halt_pin;

assign rd_n = !(run && ((ts == TS_T2) || (ts == TS_T3) || (ts == TS_TW)) &&
                !cur_wr && !cur_halt);

always @(negedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= run && (ts == TS_T1);

//============================================================================
// THE CLOCK
//============================================================================

integer i;
// step (a) captures -- clock-c values the later steps must not re-read
reg        ne_now, pl_now, kill_l, evi_l, hfree_l, pop_l, qse_l;
reg  [1:0] sev_now;
reg        infl_now;
reg  [1:0] infl_n_now;
reg        set_oprfree;
// working
reg        ev_here, ev_latch, did_grant, gr_ok;
reg  [4:0] occ;
reg  [1:0] land_ttl;
reg  [3:0] qi;
reg [19:0] fetch_lin;
reg        set_grn, set_infl, set_absorb, set_land, set_noeval;
reg  [1:0] new_ttl;

always @(posedge clk) begin
    if (ss_we) begin
        //--------------------------------------------------------------------
        // save-state WRITE decode (arm #1 of the exactly-twice discipline)
        //--------------------------------------------------------------------
        case (ss_addr)
            SSA_B_RUN:          run           = ss_wdata[0];
            SSA_B_TS:           ts            = ss_wdata[2:0];
            SSA_B_CUR_BS:       cur_bs        = ss_wdata[2:0];
            SSA_B_CUR_ADDR_LO:  cur_addr[15:0]   = ss_wdata;
            SSA_B_CUR_ADDR_HI:  cur_addr[19:16]  = ss_wdata[3:0];
            SSA_B_CUR_DATA:     cur_data      = ss_wdata;
            SSA_B_CUR_UBE_N:    cur_ube_n     = ss_wdata[0];
            SSA_B_CUR_SEG:      cur_seg       = ss_wdata[1:0];
            SSA_B_CUR_FETCH:    cur_fetch     = ss_wdata[0];
            SSA_B_CUR_HALT:     cur_halt      = ss_wdata[0];
            SSA_B_CUR_NOADDR:   cur_noaddr    = ss_wdata[0];
            SSA_B_CUR_WR:       cur_wr        = ss_wdata[0];
            SSA_B_CUR_NEED:     cur_need      = ss_wdata[0];
            SSA_B_CUR_RDLAST:   cur_rd_last   = ss_wdata[0];
            SSA_B_CUR_PN:       cur_pn        = ss_wdata[1:0];
            SSA_B_CUR_LATET1:   cur_late_t1   = ss_wdata[0];
            SSA_B_EVALD:        evald         = ss_wdata[0];
            SSA_B_SEV:          sev           = ss_wdata[1:0];
            SSA_B_DAGE:         dage          = ss_wdata[2:0];
            SSA_B_CMT_VALID:    cmt_valid     = ss_wdata[0];
            SSA_B_CMT_BS:       cmt_bs        = ss_wdata[2:0];
            SSA_B_CMT_ADDR_LO:  cmt_addr[15:0]   = ss_wdata;
            SSA_B_CMT_ADDR_HI:  cmt_addr[19:16]  = ss_wdata[3:0];
            SSA_B_CMT_DATA:     cmt_data      = ss_wdata;
            SSA_B_CMT_UBE_N:    cmt_ube_n     = ss_wdata[0];
            SSA_B_CMT_SEG:      cmt_seg       = ss_wdata[1:0];
            SSA_B_CMT_FETCH:    cmt_fetch     = ss_wdata[0];
            SSA_B_CMT_HALT:     cmt_halt      = ss_wdata[0];
            SSA_B_CMT_NOADDR:   cmt_noaddr    = ss_wdata[0];
            SSA_B_CMT_WR:       cmt_wr        = ss_wdata[0];
            SSA_B_CMT_NEED:     cmt_need      = ss_wdata[0];
            SSA_B_CMT_RDLAST:   cmt_rd_last   = ss_wdata[0];
            SSA_B_CMT_PN:       cmt_pn        = ss_wdata[1:0];
            SSA_B_CDAGE:        cdage         = ss_wdata[2:0];
            SSA_B_CMT_PREV_FP:  cmt_prev_fp   = ss_wdata;
            SSA_B_CMT_WAS_OWED: cmt_was_owed  = ss_wdata[0];
            SSA_B_LAST_FADDR:   last_fetch_addr  = ss_wdata;
            SSA_B_Q0:           q_mem[0]      = ss_wdata[7:0];
            SSA_B_Q1:           q_mem[1]      = ss_wdata[7:0];
            SSA_B_Q2:           q_mem[2]      = ss_wdata[7:0];
            SSA_B_Q3:           q_mem[3]      = ss_wdata[7:0];
            SSA_B_Q4:           q_mem[4]      = ss_wdata[7:0];
            SSA_B_Q5:           q_mem[5]      = ss_wdata[7:0];
            SSA_B_Q_HEAD:       q_head        = ss_wdata[2:0];
            SSA_B_Q_CNT:        q_cnt         = ss_wdata[3:0];
            SSA_B_GRN_N:        grn_n         = ss_wdata[1:0];
            SSA_B_GRN_TTL:      grn_ttl       = ss_wdata[1:0];
            SSA_B_FETCH_PTR:    fetch_ptr     = ss_wdata;
            SSA_B_CS:           cs_r          = ss_wdata;
            SSA_B_SUSPENDED:    suspended     = ss_wdata[0];
            SSA_B_HALTED:       halted        = ss_wdata[0];
            SSA_B_HALT_PEND:    halt_pending  = ss_wdata[0];
            SSA_B_PF_OWED:      pf_owed       = ss_wdata[0];
            SSA_B_PF_ARM:       pf_arm        = ss_wdata[0];
            SSA_B_PF_LAND:      pf_land       = ss_wdata[0];
            SSA_B_INFL_TTL:     infl_ttl      = ss_wdata[1:0];
            SSA_B_INFL_N:       infl_n        = ss_wdata[1:0];
            SSA_B_ABSORB_TTL:   absorb_ttl    = ss_wdata[1:0];
            SSA_B_NO_EVAL:      no_eval       = ss_wdata[0];
            SSA_B_FLUSH_EVAL:   flush_eval    = ss_wdata[0];
            SSA_B_E_PEND:       e_pend        = ss_wdata[0];
            SSA_B_RQ_N:         rq_n          = ss_wdata[1:0];
            SSA_B_RQ0_BS:       rq_bs[0]      = ss_wdata[2:0];
            SSA_B_RQ0_ADDR_LO:  rq_addr[0][15:0]   = ss_wdata;
            SSA_B_RQ0_ADDR_HI:  rq_addr[0][19:16]  = ss_wdata[3:0];
            SSA_B_RQ0_DATA:     rq_data[0]    = ss_wdata;
            SSA_B_RQ0_UBE:      rq_ube[0]     = ss_wdata[0];
            SSA_B_RQ0_SEG:      rq_seg[0]     = ss_wdata[1:0];
            SSA_B_RQ0_NOADDR:   rq_noaddr[0]  = ss_wdata[0];
            SSA_B_RQ0_WR:       rq_wr[0]      = ss_wdata[0];
            SSA_B_RQ0_NEED:     rq_need[0]    = ss_wdata[0];
            SSA_B_RQ0_LAST:     rq_last[0]    = ss_wdata[0];
            SSA_B_RQ1_BS:       rq_bs[1]      = ss_wdata[2:0];
            SSA_B_RQ1_ADDR_LO:  rq_addr[1][15:0]   = ss_wdata;
            SSA_B_RQ1_ADDR_HI:  rq_addr[1][19:16]  = ss_wdata[3:0];
            SSA_B_RQ1_DATA:     rq_data[1]    = ss_wdata;
            SSA_B_RQ1_UBE:      rq_ube[1]     = ss_wdata[0];
            SSA_B_RQ1_SEG:      rq_seg[1]     = ss_wdata[1:0];
            SSA_B_RQ1_NOADDR:   rq_noaddr[1]  = ss_wdata[0];
            SSA_B_RQ1_WR:       rq_wr[1]      = ss_wdata[0];
            SSA_B_RQ1_NEED:     rq_need[1]    = ss_wdata[0];
            SSA_B_RQ1_LAST:     rq_last[1]    = ss_wdata[0];
            SSA_B_SLOT_BUSY:    slot_busy     = ss_wdata[0];
            SSA_B_SLOT_ACC:     slot_accept   = ss_wdata[0];
            SSA_B_OPR_HELD:     opr_held      = ss_wdata[0];
            SSA_B_DONE_CTR:     done_ctr      = ss_wdata[1:0];
            SSA_B_DONE_WR:      done_wr       = ss_wdata[0];
            SSA_B_RD_DONE_P:    rd_done_p     = ss_wdata[0];
            SSA_B_WR_DONE_P:    wr_done_p     = ss_wdata[0];
            SSA_B_OPR_FREE_P:   opr_free_p    = ss_wdata[0];
            SSA_B_RD_VAL:       rd_val        = ss_wdata;
            SSA_B_READY_PREV:   ready_prev    = ss_wdata[0];
            default: ;
        endcase
    end else if (srst) begin
        //--------------------------------------------------------------------
        // RESET == the model's begin_case(), plus the backdoor injection.
        //--------------------------------------------------------------------
        run  = 1'b0; ts  = TS_TI;
        cur_bs  = BS_PASV; cur_addr  = 20'd0; cur_data  = 16'd0;
        cur_ube_n  = 1'b1; cur_seg  = 2'd2; cur_fetch  = 1'b0;
        cur_halt  = 1'b0; cur_noaddr  = 1'b0; cur_wr  = 1'b0;
        cur_need  = 1'b0; cur_rd_last  = 1'b1; cur_pn  = 2'd0;
        cur_late_t1  = 1'b0; evald  = 1'b0; sev  = 2'd0; dage  = 3'd0;
        cmt_valid  = 1'b0; cmt_bs  = BS_PASV; cmt_addr  = 20'd0;
        cmt_data  = 16'd0; cmt_ube_n  = 1'b1; cmt_seg  = 2'd2;
        cmt_fetch  = 1'b0; cmt_halt  = 1'b0; cmt_noaddr  = 1'b0;
        cmt_wr  = 1'b0; cmt_need  = 1'b0; cmt_rd_last  = 1'b1;
        cmt_pn  = 2'd0; cdage  = 3'd0; cmt_prev_fp  = 16'd0;
        cmt_was_owed  = 1'b0;
        q_head  = 3'd0; grn_n  = 2'd0; grn_ttl  = 2'd0;
        suspended  = 1'b0; halted  = 1'b0; halt_pending  = 1'b0;
        pf_owed  = 1'b0; pf_arm  = 1'b1; pf_land  = 1'b0;
        infl_ttl  = 2'd0; infl_n  = 2'd0; absorb_ttl  = 2'd0;
        no_eval  = 1'b0; flush_eval  = 1'b0; e_pend  = 1'b0;
        rq_n  = 2'd0;
        for (i = 0; i < 2; i = i + 1) begin
            rq_bs[i]  = BS_PASV; rq_addr[i]  = 20'd0; rq_data[i]  = 16'd0;
            rq_ube[i]  = 1'b1; rq_seg[i]  = 2'd2; rq_noaddr[i]  = 1'b0;
            rq_wr[i]  = 1'b0; rq_need[i]  = 1'b0; rq_last[i]  = 1'b1;
        end
        slot_busy  = 1'b0; slot_accept  = 1'b0;
        opr_held  = 1'b0; done_ctr  = 2'd0; done_wr  = 1'b0;
        rd_done_p  = 1'b0; wr_done_p  = 1'b0; opr_free_p  = 1'b0;
        rd_val  = 16'd0;
        ready_prev  = 1'b1;
        if (bkd_load) begin
            // The backdoor injects a RIPE queue at CS:IP with the fetch
            // pointer past it -- `queue_preload`'s post-state exactly.
            cs_r       = bkd_cs;
            fetch_ptr  = bkd_ip;
            q_cnt      = {1'b0, bkd_qlen};
            for (i = 0; i < 6; i = i + 1) q_mem[i]  = bkd_queue[i*8 +: 8];
            last_fetch_addr  = 16'd0;
        end else begin
            // The synthesis reset flow: the vector fetch at FFFF0.
            cs_r       = 16'hFFFF;
            fetch_ptr  = 16'h0000;
            q_cnt      = 4'd0;
            for (i = 0; i < 6; i = i + 1) q_mem[i]  = 8'h00;
            last_fetch_addr  = 16'd0;
        end
    end else if (ce) begin
        //====================================================================
        // (a) CAPTURE the clock-c predicates
        //====================================================================
        ne_now     = no_eval;
        pl_now     = pf_land;
        kill_l     = ann_kill;
        evi_l      = eval_inst;
        hfree_l    = halt_free;
        pop_l      = pop_now;
        qse_l      = qs_e_now;
        sev_now    = evald ? sev : 2'd0;
        infl_now   = (infl_ttl != 2'd0);
        infl_n_now = infl_n;
        set_grn = 1'b0; set_infl = 1'b0; set_absorb = 1'b0;
        set_land = 1'b0; set_noeval = 1'b0; new_ttl = 2'd0;
        set_oprfree = 1'b0;
        rd_done_p = 1'b0; wr_done_p = 1'b0;
        // eu_done rides the eval: it lands at e+2, which is T4+1 at
        // zero waits and T4+2 whenever the cycle took any Tw.
        if (done_ctr == 2'd1) begin
            done_ctr = 2'd0;
            if (done_wr) wr_done_p = 1'b1; else rd_done_p = 1'b1;
        end else if (done_ctr != 2'd0) done_ctr = done_ctr - 2'd1;

        //====================================================================
        // (b) THE EU's OWN ACTS -- the model makes them at `clk_ == c`, i.e.
        //     before tick(c) runs, so they are visible to this clock's eval.
        //====================================================================

        // the queue POP: a POINT SAMPLE riding this clock
        if (pop_l) begin
            q_head = (q_head == 3'd5) ? 3'd0 : q_head + 3'd1;
            q_cnt  = q_cnt - 4'd1;
        end
        if (qse_l) e_pend = 1'b0;

        // F2: the withdrawal
        if (kill_l) begin
            cmt_valid = 1'b0;
            fetch_ptr = cmt_prev_fp;
            pf_owed   = cmt_was_owed;   // un-granting un-consumes the request
        end
        if (eu_susp)   suspended = 1'b1;
        if (eu_resume) suspended = 1'b0;
        if (eu_unhalt) begin halted = 1'b0; halt_pending = 1'b0; end
        if (eu_halt)   begin halted = 1'b1; halt_pending = 1'b1; end

        // post(): the request enters the 2-deep backing store; only the cycle
        // that carries the EU's OWN request takes the single slot (M10).
        if (eu_post && (rq_n != 2'd2)) begin
            rq_bs[rq_n[0]]     = eu_bs;
            rq_addr[rq_n[0]]   = eu_addr;
            rq_data[rq_n[0]]   = 16'd0;
            rq_ube[rq_n[0]]    = (eu_word || eu_addr[0]) ? 1'b0 : 1'b1;
            rq_seg[rq_n[0]]    = eu_seg;
            rq_noaddr[rq_n[0]] = (eu_bs == BS_INTA);
            rq_wr[rq_n[0]]     = (eu_bs == BS_MEMW) || (eu_bs == BS_IOW);
            rq_need[rq_n[0]]   = (eu_bs == BS_MEMW) || (eu_bs == BS_IOW);
            rq_last[rq_n[0]]   = 1'b1;
            rq_n            = rq_n + 2'd1;
            slot_busy       = 1'b1;
            slot_accept     = 1'b0;
        end

        // M5b: the write-data register is loaded through an 8-bit rotator
        // controlled by A0 of the ACCESS -- ONE pass, and both cycles of a
        // split then drive that same rotated word.
        if (eu_pair) begin
            rd_val = eu_wdata;
            if (run && cur_need) begin
                cur_data = cur_addr[0] ? {eu_wdata[7:0], eu_wdata[15:8]}
                                       : eu_wdata;
                cur_need = 1'b0;
                // 11.4: ...but only until the AD output latch takes the word
                // at T2.  A pairing that lands after that clock never holds.
                if (ts == TS_T1) opr_held = 1'b1;
            end else if (cmt_valid && cmt_need) begin
                cmt_data = cmt_addr[0] ? {eu_wdata[7:0], eu_wdata[15:8]}
                                       : eu_wdata;
                cmt_need = 1'b0;
                opr_held = 1'b1;
            end else if ((rq_n != 2'd0) && rq_need[0]) begin
                rq_data[0] = rq_addr[0][0] ? {eu_wdata[7:0], eu_wdata[15:8]}
                                           : eu_wdata;
                rq_need[0] = 1'b0;
                opr_held   = 1'b1;
            end else if ((rq_n == 2'd2) && rq_need[1]) begin
                rq_data[1] = rq_addr[1][0] ? {eu_wdata[7:0], eu_wdata[15:8]}
                                           : eu_wdata;
                rq_need[1] = 1'b0;
                opr_held   = 1'b1;
            end
        end

        // flush(): the redirect.  ORDER MATTERS -- withdrawing a fetch rewinds
        // `fetch_ptr`, so the withdrawal (`kill_l`, above) precedes the load.
        if (q_flush) begin
            q_cnt = 4'd0; q_head = 3'd0; grn_n = 2'd0; grn_ttl = 2'd0;
            cs_r      = flush_cs;
            fetch_ptr = flush_ip;
            suspended = 1'b0;
            pf_land   = 1'b0;  pl_now  = 1'b0;   // M6: discards what landed
            infl_ttl  = 2'd0;  infl_now = 1'b0;  // M7b: and its accounting
            // M19: the flush RAISES the prefetcher's request.  It stands until
            // the bus takes it -- a later SUSP does not reset it.
            pf_owed = 1'b1;
            // M7: the sampled quantity is the QUEUE COUNTER, and the flush
            // zeroes it, so a latch taken at index 2 of a cycle the flush has
            // just invalidated cannot hold the redirect off.
            pf_arm = 1'b1;
            // M12: ...AND SO DOES EVERY OTHER LATCH THE COMPLETING CYCLE LEFT
            // BEHIND -- the reserved display slot, and the QS-port absorb
            // hold (released, but not before the flush's own clock).
            no_eval = 1'b0;  ne_now = 1'b0;
            absorb_ttl = 2'd0;
            // ...and DOOMED means doomed on either side of the announcement.
            if (run && cur_fetch)       cur_pn = 2'd0;
            if (cmt_valid && cmt_fetch) cmt_pn = 2'd0;
            flush_eval = 1'b1;
            if (!qse_l) e_pend = 1'b1;
        end

        //====================================================================
        // (c) END OF CLOCK: advance the running cycle
        //====================================================================
        ev_here  = 1'b0;
        ev_latch = 1'b0;
        if (run) begin
            // 11.4 -- THE OPR RELEASE DOES NOT STRETCH.  The store hands its
            // word to the AD output latch at T2 and OPR is free from T3, at
            // every wait level, while eu_done rides the eval.
            if ((ts == TS_T2) && cur_wr && opr_held) begin
                opr_held    = 1'b0;
                set_oprfree = 1'b1;
            end
            // M7 / M17 -- the prefetch-eligibility test (and the HALT block)
            // is SAMPLED at a fixed cycle index (2 = T3) and LATCHED; the
            // completion eval only APPLIES what that clock decided.
            if (ts == TS_T3) begin
                occ = {1'b0, q_cnt}
                    + (cur_fetch ? {3'b0, cur_pn} : 5'd0)
                    + ((cmt_valid && cmt_fetch) ? {3'b0, cmt_pn} : 5'd0)
                    + (infl_now ? {3'b0, infl_n_now} : 5'd0);
                pf_arm = (occ <= 5'd4) && !halted;
            end

            if (evi_l) begin
                ev_here  = 1'b1;
                // M21 (second half): the HALT's eval has no index-2 latch to
                // apply -- it is an ORDINARY IDLE eval, read live.
                ev_latch = !cur_halt;
                evald    = 1'b1;
                sev      = 2'd1;
                // M2r: the completion eval's DISPLAY clock is not an eval pt.
                set_noeval = 1'b1;
            end
            if (hfree_l) ev_here = 1'b1;    // M21

            if (ts == TS_T4) begin
                //--------------------------------------------------------
                // THE LANDING.  All three windows are the SAME OFFSET from
                // the eval, seen from three places:
                //    ready    = e + 3   (M3, the byte is poppable)
                //    infl to  = e + 2   (M7b, the outstanding-fetch term)
                //    absorb   = e+1..e+2 (F1(b), the QS port)
                // `sev_now` is the distance from the eval to this T4, so
                // ONE number initialises all three.
                //--------------------------------------------------------
                land_ttl = (sev_now >= 2'd2) ? 2'd0 : (2'd2 - sev_now);
                if (cur_fetch && (cur_pn != 2'd0)) begin
                    qi = {1'b0, q_head} + q_cnt;
                    if (qi >= 4'd6) qi = qi - 4'd6;
                    if (cur_pn == 2'd2) begin
                        q_mem[qi[2:0]] = cur_data[7:0];
                        qi = (qi == 4'd5) ? 4'd0 : qi + 4'd1;
                        q_mem[qi[2:0]] = cur_data[15:8];
                    end else begin
                        // an ODD-address single-byte fetch takes the UPPER lane
                        q_mem[qi[2:0]] = cur_data[15:8];
                    end
                    q_cnt   = q_cnt + {2'b0, cur_pn};
                    grn_n   = cur_pn;
                    infl_n  = cur_pn;
                    new_ttl = land_ttl;
                    set_grn = 1'b1; set_infl = 1'b1; set_absorb = 1'b1;
                    // M6: keyed to T4, NOT to the eval -- ONE clock, and it
                    // is not a prefetch-grant point.
                    set_land = 1'b1;
                end
                // S9a: the HALT pseudo-cycle is not an EU access at all -- it
                // never went through post(), so it must not complete one.
                if (!cur_fetch && !cur_halt) begin
                    done_wr = cur_wr;
                    // the deadline is e+2: one clock from this T4 at w0, two
                    // whenever the cycle took a Tw.  ONE number again.
                    done_ctr = (land_ttl == 2'd0) ? 2'd1 : land_ttl;
                    if (!cur_wr && cur_rd_last)
                        rd_val = cur_data;      // the read lands in OPR
                end
                run = 1'b0;
                ts  = TS_TI;
            end else begin
                case (ts)
                    TS_T1: ts = TS_T2;   // the data phase opens on T2
                    TS_T2: begin
                        // The 16-bit system always presents the ALIGNED WORD
                        // on a read; UBE/A0 only decide which half is used.
                        if (!cur_wr && !cur_halt) cur_data = ad_i;
                        ts = TS_T3;
                    end
                    // The T3/Tw -> T4 advance IS the READY sample; the eval
                    // is that same sample one flop later (M2r).
                    TS_T3:   ts = ready ? TS_T4 : TS_TW;
                    TS_TW:   ts = ready ? TS_T4 : TS_TW;
                    default: ts = TS_T4;
                endcase
            end
            // F3: the flush-only point commits the REDIRECT PREFETCH only.  A
            // pending EU request still owns the first slot and an EU access is
            // never granted at a T4, so with a request outstanding it does not
            // fire and both wait for the next normal eval.
            if (!run && cur_fetch && flush_eval && (rq_n == 2'd0))
                ev_here = 1'b1;
        end else if (!cmt_valid && !ne_now) begin
            ev_here = 1'b1;                       // end of an idle clock
        end

        //====================================================================
        // (d) THE EVAL: pick the next bus cycle
        //====================================================================
        did_grant = 1'b0;
        if (ev_here && !cmt_valid) begin
            flush_eval = 1'b0;    // F3's point is spent by any commit
            gr_ok = 1'b0;
            if (rq_n != 2'd0) begin
                // M4: an EU access never preempts an in-flight cycle; it wins
                // the next eval.
                cmt_bs = rq_bs[0]; cmt_addr = rq_addr[0];
                cmt_data = rq_data[0]; cmt_ube_n = rq_ube[0];
                cmt_seg = rq_seg[0]; cmt_noaddr = rq_noaddr[0];
                cmt_wr = rq_wr[0]; cmt_need = rq_need[0];
                cmt_rd_last = rq_last[0];
                cmt_fetch = 1'b0; cmt_halt = 1'b0; cmt_pn = 2'd0;
                rq_bs[0] = rq_bs[1]; rq_addr[0] = rq_addr[1];
                rq_data[0] = rq_data[1]; rq_ube[0] = rq_ube[1];
                rq_seg[0] = rq_seg[1]; rq_noaddr[0] = rq_noaddr[1];
                rq_wr[0] = rq_wr[1]; rq_need[0] = rq_need[1];
                rq_last[0] = rq_last[1];
                rq_n = rq_n - 2'd1;
                // M10: the slot's occupant now has the T1 that frees it -- the
                // LAST cycle of the access, so a split holds it across both.
                if (cmt_rd_last) slot_accept = 1'b1;
                gr_ok = 1'b1;
            end else if (suspended && !pf_owed) begin
                // F2 keeps SUSP at the eval; M19 -- but SUSP gates the RAISING
                // of a request, not one the flush already raised.
                gr_ok = 1'b0;
            end else begin
                occ = {1'b0, q_cnt}
                    + ((run && cur_fetch) ? {3'b0, cur_pn} : 5'd0)
                    + (infl_now ? {3'b0, infl_n_now} : 5'd0);
                if (ev_latch ? !pf_arm : ((occ > 5'd4) || halted))
                    gr_ok = 1'b0;
                else if (pl_now)
                    // M6: no fetch is chosen while the previous fetch's bytes
                    // are LANDING in the queue.
                    gr_ok = 1'b0;
                else begin
                    fetch_lin = {cs_r, 4'd0} + {4'd0, fetch_ptr};
                    cmt_bs = BS_CODE; cmt_addr = fetch_lin; cmt_data = 16'd0;
                    cmt_ube_n = 1'b0; cmt_seg = 2'd2; cmt_noaddr = 1'b0;
                    cmt_wr = 1'b0; cmt_need = 1'b0; cmt_rd_last = 1'b1;
                    cmt_fetch = 1'b1; cmt_halt = 1'b0;
                    // word fetch at an even address (+2), single upper-lane
                    // byte at an odd one (+1)
                    cmt_pn = fetch_lin[0] ? 2'd1 : 2'd2;
                    cmt_prev_fp = fetch_ptr;
                    last_fetch_addr = fetch_lin[15:0];
                    fetch_ptr = fetch_ptr + {14'd0, cmt_pn};
                    cmt_was_owed = pf_owed;  // M22: ...given back if it expires
                    pf_owed = 1'b0;          // M19: the arbiter has taken it
                    gr_ok = 1'b1;
                end
            end
            if (gr_ok) begin
                if (!cmt_fetch) cmt_was_owed = pf_owed;
                cmt_valid = 1'b1;
                cdage     = 3'd0;
                did_grant = 1'b1;
            end
        end

        //====================================================================
        // (e) tick(c+1)'s PRE-ROW BLOCK
        //====================================================================
        if (cmt_valid && !did_grant && (cdage != 3'd7))
            cdage = cdage + 3'd1;      // the age the NEXT clock will show

        // M22 -- AN ANNOUNCEMENT EXPIRES.  The register is written at the
        // GRANT and let go at the announced cycle's own release index counted
        // from the DISPLAY; a cycle that never OPENS a T1 never latches a wait
        // count, so that index is the ZERO-WAIT one (display + 3), and it may
        // not be given up before the clock the bus it is waiting for finishes
        // on.  Locally: age >= 3 AND the T1 would open now or on the next
        // clock (`!run` = the bus is free now; `T4` = it frees next clock).
        // ...AND IT UNDOES THE GRANT.
        if (cmt_valid && !did_grant && (cdage >= 3'd3) &&
            (!run || (ts == TS_T4))) begin
            cmt_valid = 1'b0;
            if (cmt_fetch) begin
                fetch_ptr = cmt_prev_fp;
                pf_owed   = cmt_was_owed;
            end else if (rq_n != 2'd2) begin
                // an EU access is not the BIU's to lose: back to the FRONT
                rq_bs[1] = rq_bs[0]; rq_addr[1] = rq_addr[0];
                rq_data[1] = rq_data[0]; rq_ube[1] = rq_ube[0];
                rq_seg[1] = rq_seg[0]; rq_noaddr[1] = rq_noaddr[0];
                rq_wr[1] = rq_wr[0]; rq_need[1] = rq_need[0];
                rq_last[1] = rq_last[0];
                rq_bs[0] = cmt_bs; rq_addr[0] = cmt_addr;
                rq_data[0] = cmt_data; rq_ube[0] = cmt_ube_n;
                rq_seg[0] = cmt_seg; rq_noaddr[0] = cmt_noaddr;
                rq_wr[0] = cmt_wr; rq_need[0] = cmt_need;
                rq_last[0] = cmt_rd_last;
                rq_n = rq_n + 2'd1;
                slot_accept = 1'b0;
            end
        end

        // S9b: the DISPLAY CLOCK AND THE T1 ARE TWO DIFFERENT THINGS, and the
        // only thing between them is whether the bus is free.
        //     display = eval + 1     T1 = max(display + 1, first free clock)
        if (!run && cmt_valid && (cdage != 3'd0)) begin
            run = 1'b1; ts = TS_T1;
            cur_bs = cmt_bs; cur_addr = cmt_addr; cur_data = cmt_data;
            cur_ube_n = cmt_ube_n; cur_seg = cmt_seg;
            cur_fetch = cmt_fetch; cur_halt = cmt_halt;
            cur_noaddr = cmt_noaddr; cur_wr = cmt_wr; cur_need = cmt_need;
            cur_rd_last = cmt_rd_last; cur_pn = cmt_pn;
            cur_late_t1 = (cdage != 3'd1);   // M23: was this T1 at disp+1?
            dage  = cdage;
            evald = 1'b0; sev = 2'd0;
            cmt_valid = 1'b0;
            // M10: the bus has TAKEN the whole request -- the slot is free
            // from this clock, which is the clock the blocked row issues on.
            if (!cmt_fetch && cmt_rd_last && slot_accept) begin
                slot_busy   = 1'b0;
                slot_accept = 1'b0;
            end
            // S5: a store that reaches T1 without having been given data
            // drives whatever is STILL STANDING in OPR, rotated by its own A0.
            if (cur_need && cur_wr)
                cur_data = cur_addr[0] ? {rd_val[7:0], rd_val[15:8]} : rd_val;
        end else if (run) begin
            if (dage != 3'd7) dage = dage + 3'd1;
        end

        // S8/S9: the HALT status takes the register on the FIRST clock the
        // register is FREE -- the bus idle and not the eval's display slot.
        // MEASURED at w0/w1/w3 alike: one clock later than a granted cycle's
        // display, because a grant loads the register AT the eval and the HLT
        // row can only load it once the finishing cycle has let go.
        if (halt_pending && !run && !cmt_valid && !set_noeval) begin
            cmt_bs = BS_HALT;
            // S9b: the HALT display drives the address latch AS IT STANDS when
            // the cycle takes the register.  M10(T4): the upper nibble is a
            // LIVE PS, not a constant -- the chip carries IE on it.
            cmt_addr = {data_ps(2'd2), last_fetch_addr};
            cmt_data = last_fetch_addr;
            cmt_ube_n = 1'b1; cmt_seg = 2'd2; cmt_noaddr = 1'b0;
            cmt_wr = 1'b0; cmt_need = 1'b0; cmt_rd_last = 1'b1;
            cmt_fetch = 1'b0; cmt_halt = 1'b1; cmt_pn = 2'd0;
            cmt_valid = 1'b1; cdage = 3'd0; cmt_was_owed = pf_owed;
            halt_pending = 1'b0;
        end

        //====================================================================
        // (f) AGE the relative counters into their clock-c+1 values
        //====================================================================
        ready_prev = ready;
        no_eval    = set_noeval;
        pf_land    = set_land;
        opr_free_p = set_oprfree;
        if (set_grn)    grn_ttl    = new_ttl;
        else if (grn_ttl    != 2'd0) grn_ttl    = grn_ttl - 2'd1;
        if (set_infl)   infl_ttl   = new_ttl;
        else if (infl_ttl   != 2'd0) infl_ttl   = infl_ttl - 2'd1;
        if (set_absorb) absorb_ttl = new_ttl;
        else if (absorb_ttl != 2'd0) absorb_ttl = absorb_ttl - 2'd1;
        if (run && evald && (sev != 2'd3) && !evi_l) sev = sev + 2'd1;

`ifndef SYNTHESIS
        // --- bounded-counter contracts (campaign risk #2) ------------------
        if (run && evald && (sev > 2'd2))
            $error("v30u_biu: sev bound violated (%0d)", sev);
        if (cmt_valid && (cdage == 3'd7))
            $error("v30u_biu: announcement age saturated");
        if (q_cnt > 4'd6)
            $error("v30u_biu: queue overflow (%0d)", q_cnt);
        if ((grn_ttl != 2'd0) && ({2'd0, grn_n} > q_cnt))
            $error("v30u_biu: green byte count exceeds queue");
`endif
    end
end

//----------------------------------------------------------------------------
// save-state READ mux (arm #2 of the exactly-twice discipline)
//----------------------------------------------------------------------------
always @(posedge clk) begin
    case (ss_addr)
        SSA_B_RUN:          ss_rdata <= {15'b0, run};
        SSA_B_TS:           ss_rdata <= {13'b0, ts};
        SSA_B_CUR_BS:       ss_rdata <= {13'b0, cur_bs};
        SSA_B_CUR_ADDR_LO:  ss_rdata <= cur_addr[15:0];
        SSA_B_CUR_ADDR_HI:  ss_rdata <= {12'b0, cur_addr[19:16]};
        SSA_B_CUR_DATA:     ss_rdata <= cur_data;
        SSA_B_CUR_UBE_N:    ss_rdata <= {15'b0, cur_ube_n};
        SSA_B_CUR_SEG:      ss_rdata <= {14'b0, cur_seg};
        SSA_B_CUR_FETCH:    ss_rdata <= {15'b0, cur_fetch};
        SSA_B_CUR_HALT:     ss_rdata <= {15'b0, cur_halt};
        SSA_B_CUR_NOADDR:   ss_rdata <= {15'b0, cur_noaddr};
        SSA_B_CUR_WR:       ss_rdata <= {15'b0, cur_wr};
        SSA_B_CUR_NEED:     ss_rdata <= {15'b0, cur_need};
        SSA_B_CUR_RDLAST:   ss_rdata <= {15'b0, cur_rd_last};
        SSA_B_CUR_PN:       ss_rdata <= {14'b0, cur_pn};
        SSA_B_CUR_LATET1:   ss_rdata <= {15'b0, cur_late_t1};
        SSA_B_EVALD:        ss_rdata <= {15'b0, evald};
        SSA_B_SEV:          ss_rdata <= {14'b0, sev};
        SSA_B_DAGE:         ss_rdata <= {13'b0, dage};
        SSA_B_CMT_VALID:    ss_rdata <= {15'b0, cmt_valid};
        SSA_B_CMT_BS:       ss_rdata <= {13'b0, cmt_bs};
        SSA_B_CMT_ADDR_LO:  ss_rdata <= cmt_addr[15:0];
        SSA_B_CMT_ADDR_HI:  ss_rdata <= {12'b0, cmt_addr[19:16]};
        SSA_B_CMT_DATA:     ss_rdata <= cmt_data;
        SSA_B_CMT_UBE_N:    ss_rdata <= {15'b0, cmt_ube_n};
        SSA_B_CMT_SEG:      ss_rdata <= {14'b0, cmt_seg};
        SSA_B_CMT_FETCH:    ss_rdata <= {15'b0, cmt_fetch};
        SSA_B_CMT_HALT:     ss_rdata <= {15'b0, cmt_halt};
        SSA_B_CMT_NOADDR:   ss_rdata <= {15'b0, cmt_noaddr};
        SSA_B_CMT_WR:       ss_rdata <= {15'b0, cmt_wr};
        SSA_B_CMT_NEED:     ss_rdata <= {15'b0, cmt_need};
        SSA_B_CMT_RDLAST:   ss_rdata <= {15'b0, cmt_rd_last};
        SSA_B_CMT_PN:       ss_rdata <= {14'b0, cmt_pn};
        SSA_B_CDAGE:        ss_rdata <= {13'b0, cdage};
        SSA_B_CMT_PREV_FP:  ss_rdata <= cmt_prev_fp;
        SSA_B_CMT_WAS_OWED: ss_rdata <= {15'b0, cmt_was_owed};
        SSA_B_LAST_UBE:     ss_rdata <= {15'b0, last_ube};
        SSA_B_LAST_FADDR:   ss_rdata <= last_fetch_addr;
        SSA_B_Q0:           ss_rdata <= {8'b0, q_mem[0]};
        SSA_B_Q1:           ss_rdata <= {8'b0, q_mem[1]};
        SSA_B_Q2:           ss_rdata <= {8'b0, q_mem[2]};
        SSA_B_Q3:           ss_rdata <= {8'b0, q_mem[3]};
        SSA_B_Q4:           ss_rdata <= {8'b0, q_mem[4]};
        SSA_B_Q5:           ss_rdata <= {8'b0, q_mem[5]};
        SSA_B_Q_HEAD:       ss_rdata <= {13'b0, q_head};
        SSA_B_Q_CNT:        ss_rdata <= {12'b0, q_cnt};
        SSA_B_GRN_N:        ss_rdata <= {14'b0, grn_n};
        SSA_B_GRN_TTL:      ss_rdata <= {14'b0, grn_ttl};
        SSA_B_FETCH_PTR:    ss_rdata <= fetch_ptr;
        SSA_B_CS:           ss_rdata <= cs_r;
        SSA_B_SUSPENDED:    ss_rdata <= {15'b0, suspended};
        SSA_B_HALTED:       ss_rdata <= {15'b0, halted};
        SSA_B_HALT_PEND:    ss_rdata <= {15'b0, halt_pending};
        SSA_B_PF_OWED:      ss_rdata <= {15'b0, pf_owed};
        SSA_B_PF_ARM:       ss_rdata <= {15'b0, pf_arm};
        SSA_B_PF_LAND:      ss_rdata <= {15'b0, pf_land};
        SSA_B_INFL_TTL:     ss_rdata <= {14'b0, infl_ttl};
        SSA_B_INFL_N:       ss_rdata <= {14'b0, infl_n};
        SSA_B_ABSORB_TTL:   ss_rdata <= {14'b0, absorb_ttl};
        SSA_B_NO_EVAL:      ss_rdata <= {15'b0, no_eval};
        SSA_B_FLUSH_EVAL:   ss_rdata <= {15'b0, flush_eval};
        SSA_B_E_PEND:       ss_rdata <= {15'b0, e_pend};
        SSA_B_RQ_N:         ss_rdata <= {14'b0, rq_n};
        SSA_B_RQ0_BS:       ss_rdata <= {13'b0, rq_bs[0]};
        SSA_B_RQ0_ADDR_LO:  ss_rdata <= rq_addr[0][15:0];
        SSA_B_RQ0_ADDR_HI:  ss_rdata <= {12'b0, rq_addr[0][19:16]};
        SSA_B_RQ0_DATA:     ss_rdata <= rq_data[0];
        SSA_B_RQ0_UBE:      ss_rdata <= {15'b0, rq_ube[0]};
        SSA_B_RQ0_SEG:      ss_rdata <= {14'b0, rq_seg[0]};
        SSA_B_RQ0_NOADDR:   ss_rdata <= {15'b0, rq_noaddr[0]};
        SSA_B_RQ0_WR:       ss_rdata <= {15'b0, rq_wr[0]};
        SSA_B_RQ0_NEED:     ss_rdata <= {15'b0, rq_need[0]};
        SSA_B_RQ0_LAST:     ss_rdata <= {15'b0, rq_last[0]};
        SSA_B_RQ1_BS:       ss_rdata <= {13'b0, rq_bs[1]};
        SSA_B_RQ1_ADDR_LO:  ss_rdata <= rq_addr[1][15:0];
        SSA_B_RQ1_ADDR_HI:  ss_rdata <= {12'b0, rq_addr[1][19:16]};
        SSA_B_RQ1_DATA:     ss_rdata <= rq_data[1];
        SSA_B_RQ1_UBE:      ss_rdata <= {15'b0, rq_ube[1]};
        SSA_B_RQ1_SEG:      ss_rdata <= {14'b0, rq_seg[1]};
        SSA_B_RQ1_NOADDR:   ss_rdata <= {15'b0, rq_noaddr[1]};
        SSA_B_RQ1_WR:       ss_rdata <= {15'b0, rq_wr[1]};
        SSA_B_RQ1_NEED:     ss_rdata <= {15'b0, rq_need[1]};
        SSA_B_RQ1_LAST:     ss_rdata <= {15'b0, rq_last[1]};
        SSA_B_SLOT_BUSY:    ss_rdata <= {15'b0, slot_busy};
        SSA_B_SLOT_ACC:     ss_rdata <= {15'b0, slot_accept};
        SSA_B_OPR_HELD:     ss_rdata <= {15'b0, opr_held};
        SSA_B_DONE_CTR:     ss_rdata <= {14'b0, done_ctr};
        SSA_B_DONE_WR:      ss_rdata <= {15'b0, done_wr};
        SSA_B_RD_DONE_P:    ss_rdata <= {15'b0, rd_done_p};
        SSA_B_WR_DONE_P:    ss_rdata <= {15'b0, wr_done_p};
        SSA_B_OPR_FREE_P:   ss_rdata <= {15'b0, opr_free_p};
        SSA_B_RD_VAL:       ss_rdata <= rd_val;
        SSA_B_READY_PREV:   ss_rdata <= {15'b0, ready_prev};
        SSA_B_T1_HALF2:     ss_rdata <= {15'b0, t1_half2};
        default:            ss_rdata <= 16'h0000;
    endcase
end

// `last_ube` is pad retention, not a decision: it tracks the pin.
always @(posedge clk) begin
    if (ss_we && ss_addr == SSA_B_LAST_UBE) last_ube <= ss_wdata[0];
    // begin_case() leaves the retained pin at 0, not 1: `last_ube_` is
    // pad retention of an undriven output, and the model's own initial
    // value is what the comparator stack's idle rows carry.
    else if (srst) last_ube <= 1'b0;
    else if (ce)   last_ube <= ube_n;
end

//----------------------------------------------------------------------------
// `+utrace` -- THE ATTRIBUTION CHANNEL (verification only, ucore stage U1).
//
// The campaign's ranked risk #1 is the pumped-clock inversion: the model
// STALLS by ticking inside `pop()` / `post()` / `wait_*()`, while the RTL
// stalls by NOT firing a condition.  When a lockstep run diverges, the row
// stream says WHEN and this says WHY -- one `u` row per clock naming the
// eval-instant terms and the QS-port arbiter's inputs, next to the model's own
// V30SIM_EVALTRACE `ET` / `QT` lines.  Guarded out of synthesis, and gated on
// the plusarg so a normal run is byte-identical without it.
//----------------------------------------------------------------------------
`ifndef SYNTHESIS
logic utrace_en;
integer utrace_clk;
initial begin
    utrace_en = $test$plusargs("utrace");
    utrace_clk = 0;
end
always @(posedge clk) begin
    if (srst) utrace_clk <= 0;
    else if (ce) begin
        if (utrace_en)
            // clk | eval/QS strobes | the terms that gate them
            /* verilator lint_off WIDTHEXPAND */
            $display("u %0d ts=%0d run=%0d dage=%0d rdyp=%0d ev=%0d evald=%0d sev=%0d cmt=%0d cdage=%0d fetch=%0d pn=%0d occ=%0d arm=%0d land=%0d infl=%0d absorb=%0d grn=%0d,%0d q=%0d owed=%0d susp=%0d halt=%0d ne=%0d fe=%0d epend=%0d qse=%0d pop=%0d rq=%0d",
                     utrace_clk, ts, run, dage, ready_prev, eval_inst,
                     evald, sev, cmt_valid, cdage, cur_fetch, cur_pn,
                     q_cnt + ((run && cur_fetch) ? {2'b0, cur_pn} : 4'd0)
                           + ((cmt_valid && cmt_fetch) ? {2'b0, cmt_pn} : 4'd0)
                           + ((infl_ttl != 2'd0) ? {2'b0, infl_n} : 4'd0),
                     pf_arm, pf_land, infl_ttl, absorb_ttl, grn_n,
                     grn_ttl, q_cnt, pf_owed, suspended, halted,
                     no_eval, flush_eval, e_pend, qs_e_now, pop_now,
                     rq_n);
            /* verilator lint_on WIDTHEXPAND */
        utrace_clk <= utrace_clk + 1;
    end
end
`endif

wire _unused = &{1'b0, eu_word, ad_i[15:0], bkd_queue[47:0]};

endmodule
