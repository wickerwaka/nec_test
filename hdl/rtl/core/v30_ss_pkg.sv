//============================================================================
//
//  v30_ss_pkg - save-state layout (single source of truth)
//
//  Packed-struct layouts for the V30 core save-state chain (task #23,
//  docs/notes/savestate_design.md). ONE definition of every chained flop, its
//  width, and its stream position. Field ORDER is authoritative (design S2
//  table order; pads at each segment's LSB tail). Any RTL/struct drift is caught
//  by the elaboration-time $bits width guards in v30_biu/v30_eu and by the
//  scramble-restore gate (design S6/G4). RULE: any edit to ss_biu_t/ss_eu_t
//  bumps SS_VERSION (the guard forces the editor into this file, two lines up).
//
//  Quartus 17.1: packed structs, positional concatenation, member-wise assigns
//  only. Never the '{field: value} aggregate pattern (synth bug, commit f43927f).
//
//  Inventory verified 2026-07-20 against hdl/rtl/core/v30_biu.sv (295 bits) and
//  v30_eu.sv (851 bits); core RTL byte-identical to the design-doc HEAD (no core
//  commits since 5613000), so zero delta since authoring (see savestate_design
//  "Inventory delta-check").
//
//============================================================================
`ifndef V30_SS_PKG_SV
`define V30_SS_PKG_SV

package v30_ss_pkg;

  localparam int          SS_VERSION   = 8'h02;   // +Family-8 LOCK-stretch flops (task #24)
  localparam int          SS_BIU_WORDS = 19;                 // 304 bits
  localparam int          SS_EU_WORDS  = 54;                 // 864 bits
  localparam int          SS_WORDS     = 1 + SS_BIU_WORDS + SS_EU_WORDS; // +tag = 74
  localparam logic [15:0] SS_TAG       = {8'(SS_VERSION), 8'(SS_WORDS)};

  //--------------------------------------------------------------------------
  // BIU segment - 299 state bits + 5 pad = 304 (19 words). Field order = design
  // Section 2.1 table order. Names match v30_biu.sv exactly (member-wise pack).
  //--------------------------------------------------------------------------
  typedef struct packed {
    // T-state machine
    logic [2:0]  state;
    // current bus cycle (mid-cycle identity)
    logic [2:0]  cur_type;
    logic [19:0] cur_addr;
    logic        cur_fetch;
    logic        cur_wr;
    logic        cur_swap;
    logic        cur_split1;
    logic        cur_split2;
    logic        cur_wrap;
    logic [15:0] cur_wdata;
    logic [1:0]  cur_seg;
    logic        cur_ube_n;
    logic [1:0]  cur_kind;
    // staged commit (committed-next descriptor)
    logic        nxt_valid;
    logic [2:0]  nxt_type;
    logic [19:0] nxt_addr;
    logic        nxt_fetch;
    logic        nxt_wr;
    logic        nxt_swap;
    logic        nxt_split1;
    logic        nxt_split2;
    logic        nxt_wrap;
    logic [15:0] nxt_wdata;
    logic [1:0]  nxt_seg;
    logic        nxt_ube_n;
    logic [1:0]  nxt_kind;
    // pin/handshake flops
    logic        ube_n;
    logic        eu_started;
    logic        eu_hand;
    logic [15:0] eu_rdata;
    // eval / wait-state law machinery
    logic        tw_any;
    logic        evald;
    logic        defer_t4;
    logic        defer_idle;
    logic        eval_ext;
    logic        flush_hold;
    logic        ext_flushed;
    logic        ready_prev;
    logic        eu_req_p1;
    logic        eu_req_p2;
    logic        eu_ready_p1;
    logic        eu_ready_p2;
    logic        tw_par;
    // negedge flop (ce_half domain) - see design 4.4
    logic        t1_half2;
    // grid parity (free-toggling; restore exactly, never re-derive)
    logic        ph_ff;
    logic        gph_ff;
    // LOCK
    logic        lock_active;
    logic        lock_done;
    // Family-8 LOCK-window bus-cycle stretch bookkeeping (task #24)
    logic        cur_bb_grant;    // current cycle committed back-to-back (not TI-grant)
    logic        lock_eu_cnt1;    // >=1 locked EU bus cycle seen this window
    logic        lock_eu_cnt2;    // >=2 locked EU bus cycles seen this window
    logic        lock_s1_fired;   // an S1 fetch stretch fired this lock window
    // prefetch queue (flops, not RAM - design 2.3)
    logic [7:0]  q_mem0;
    logic [7:0]  q_mem1;
    logic [7:0]  q_mem2;
    logic [7:0]  q_mem3;
    logic [7:0]  q_mem4;
    logic [7:0]  q_mem5;
    logic [2:0]  q_rd;
    logic [2:0]  q_wr;
    logic [2:0]  q_cnt;
    logic [2:0]  q_avl;
    logic [1:0]  q_aged;
    logic        q_head_dry_q;
    // fetch pointer / in-flight
    logic        fetch_discard;
    logic [15:0] fetch_cs;
    logic [15:0] fetch_off;
    logic [15:0] fetch_data;
    logic [1:0]  push_pend;
    logic        push_pend_hi;
    // display / halt law
    logic        e_wait;
    logic        halt_t1;
    logic        halt_done;
    // class-5 / heuristic history
    logic [3:0]  occ34_age;
    logic [7:0]  pop_sr;
    logic [3:0]  recent_evx;
    logic        last_was_store;
    // class-5 unified law
    logic [3:0]  law_tw_cnt;
    logic [3:0]  law_dtw;
    logic [2:0]  law_dcnt;
    logic        law_window;
    logic [2:0]  law_ctr;
    logic [2:0]  law_sel;
    logic        law_prov;
    // explicit pad to 19*16
    logic [4:0]  pad;
  } ss_biu_t;

  //--------------------------------------------------------------------------
  // EU segment - 851 state bits + 13 pad = 864 (54 words). Field order = design
  // Section 2.2 table order. state/wnext/dret are state_e enums (7b) - restore
  // with explicit state_e'() casts in v30_eu (implicit slice assign is illegal).
  //--------------------------------------------------------------------------
  typedef struct packed {
    // architectural
    logic [15:0] rf0, rf1, rf2, rf3, rf4, rf5, rf6, rf7;
    logic [15:0] sr0, sr1, sr2, sr3;
    logic [15:0] psw;
    logic [15:0] pc;
    logic [15:0] arch_ip;
    // sequencer (state/wnext/dret carried as raw 7-bit slices; cast on restore)
    logic [6:0]  state;
    logic [6:0]  wnext;
    logic [6:0]  dret;
    logic [5:0]  dly;
    // divider unit
    logic [16:0] div_rem;
    logic [15:0] div_quo;
    logic [15:0] div_den;
    logic [5:0]  div_cnt;
    logic        div_busy;
    logic        div_word;
    logic        div_signed;
    logic        div_nsign;
    logic        div_dsign;
    logic        div_pend;
    logic        div_late;
    // shift/rotate unit
    logic [15:0] sh_r;
    logic [7:0]  sh_x;
    logic [7:0]  sh_oth;
    logic        sh_cy;
    logic [2:0]  sh_op;
    logic        sh_wf;
    logic [7:0]  sh_n;
    logic        sh_busy;
    logic [15:0] sh_fbase;
    logic [15:0] sh_res;
    logic [15:0] sh_fl;
    // instruction latches
    logic [7:0]  opc;
    logic [7:0]  opc2;
    logic [7:0]  mrm;
    logic [7:0]  immb;
    logic [15:0] disp;
    // ADD4S loop
    logic [7:0]  a4_cnt;
    logic [7:0]  a4_k;
    logic [15:0] a4_src;
    logic        a4_carry;
    logic        a4_z;
    // operand/trap latches
    logic [15:0] mem_op;
    logic [15:0] ivt_off;
    logic [15:0] ivt_seg;
    logic [15:0] trap_psw;
    // prefix latches
    logic        seg_ovr_en;
    logic [1:0]  seg_ovr;
    logic        lock_en;
    logic        rep_en;
    logic [1:0]  rep_kind;
    // flush/string/REP
    logic        flush_now;
    logic        str_wr;
    logic [5:0]  rslot;
    logic        rep1_abort;
    logic        str_done;
    logic [15:0] cmp1;
    logic        cmp_r2s;
    logic [15:0] fl_cs;
    logic [15:0] fl_ip;
    // mem-form microstate
    logic [19:0] ea_save;
    logic [1:0]  ea_save_seg;
    logic        ldp2;
    logic [1:0]  fret_ph;
    logic [1:0]  facc;
    logic        iret_pw;
    logic        popr_pend;
    logic        prep_acc;
    logic [2:0]  pracc;
    logic        w4skip;
    logic        prep_bpd;
    logic [8:0]  shw;
    logic [5:0]  popm_hold;
    // INS/EXT bit-field
    logic [3:0]  ie_off;
    logic [4:0]  ie_len;
    logic [15:0] ie_fld;
    logic [15:0] ie_w0;
    logic [1:0]  ie_mode;
    logic        ie_ph2;
    logic [11:0] ie_dly;
    logic        ie_chain;
    logic        ie_rdyhold;
    logic        ie_lgot;
    // interrupt machinery
    logic [3:0]  int_p;
    logic [4:0]  nmi_p;
    logic        nmi_latch;
    logic        poll_s1;
    logic        shadow;
    logic        ie_pend;
    logic        ie_val;
    logic [15:0] psw_old;
    logic        pop_pend;
    logic [3:0]  ie_p;
    logic        waits_seen;
    logic        post_flush;
    logic [15:0] insn_ip;
    logic [7:0]  ivt_vec;
    logic        hwake_ie0;
    logic        irq_disp;
    logic        irq_nmi_ivt;
    // BIU-side output regs (set in the FSM, held across cycles - state)
    logic        eu_wr;
    logic        eu_word;
    logic [19:0] eu_addr;
    logic [1:0]  eu_seg;
    logic [15:0] eu_wdata;
    logic [1:0]  eu_kind;
    logic        halt_disp;
    // explicit pad to 54*16
    logic [12:0] pad;
  } ss_eu_t;

endpackage

`endif
