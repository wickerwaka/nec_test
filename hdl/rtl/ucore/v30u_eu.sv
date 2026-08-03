//============================================================================
//
//  v30u_eu - the ucore execution unit: micro-sequencer, loader march,
//            datapath and ALU.
//
//  THIS MODULE IS A TRANSLITERATION OF sim/exec_impl.h + sim/loader_impl.h +
//  sim/alu.cpp.  The governance rule (hdl/rtl/ucore/README.md) is that the
//  model is the SPEC: an RTL-vs-sim divergence is a bug HERE.
//
//  --- THE INVERSION (campaign risk #1) -------------------------------------
//
//  The model PUMPS the clock: the interpreter calls `charge(n)` / `pop()` /
//  `wait_read()` and the BIU ticks underneath it.  The RTL cannot do that, so
//  the interpreter is re-expressed as a state machine whose state is
//  "the step of the model's program that occupies THIS clock":
//
//    * every port the BIU samples (`q_pop`, `eu_post`, `eu_pair`, `q_flush`,
//      `eu_susp`, `eu_halt`) is a COMBINATIONAL function of EU REGISTERS ONLY
//      -- the state, the micro-row word standing on `upc`, and the datapath.
//      The model makes those acts "at clk_ == c, before tick(c)"; the RTL BIU
//      consumes them in its step (b) at the edge ending c.  Same instant.
//    * `charge(n)` becomes "this state occupies n clocks".
//    * every `while (...) tick()` becomes a STALL: the state is re-entered
//      and its acts are withheld.  There are five, and they are named:
//
//        stall_q       a queue byte is demanded and not ripe        (M8)
//        stall_opr     the F / OPR interlock                        (11.4/M13)
//        stall_slot    the EU's ONE bus-request slot is busy        (M10)
//        stall_retire  the retire deadline: a store owes its data   (7.7)
//        stall_pin     the 1BL retire lead / a halted part          (S9a)
//
//    * a model step that charges NOTHING (consuming a pre-popped opcode, the
//      pure-decode logic) is a ZERO-COST state: it is executed inside the same
//      edge that computed it, by the bounded chain loop below.  The loop is
//      how "several model steps ride one clock" is expressed.
//
//  --- THE SEQUENCER --------------------------------------------------------
//
//  upc = {page[2:0], opc[7:0], loc[3:0]}, 15 bits (U0 finding F1), and it is
//  the architectural SS-mapped flop: the two tables stand combinationally on
//  it (see v30u_ucrom.sv), so a restore has no hidden BRAM-address state.
//  `loc` is a 4-bit counter inside the opcode's 16-row block and CARRIES into
//  the opcode byte (ledger: IMUL 00B3 -> 0218).
//
//  --- CE DISCIPLINE --------------------------------------------------------
//
//  Nothing clocked runs unless `srst` or `ce`; reset is ungated so `bkd_load`
//  fires regardless of CE.  There is no negedge process in the EU.
//
//============================================================================

module v30u_eu (
    input             clk,
    input             ce,
    input             srst,

    // queue port
    input       [7:0] q_byte,
    input             q_ripe,
    input             q_ripe_lead_n, // ...and it will be ripe NEXT clock
    input       [3:0] q_cnt,
    output            q_pop,
    output            q_first,
    output            q_flush,
    output     [15:0] flush_cs,
    output     [15:0] flush_ip,

    // bus requests
    output            eu_post,
    output      [2:0] eu_bs,
    output     [19:0] eu_addr,
    output     [19:0] eu_addr2,     // split: the second cycle's own address
    output            eu_split,
    output      [1:0] eu_seg,
    output            eu_word,
    input             eu_slot_busy,
    input             eu_slot_busy_n,
    output            eu_pair,
    output            eu_pair2,     // the pairing fills TWO reserved cycles
    output     [15:0] eu_wdata,
    input      [15:0] eu_rdata_n,
    input             eu_rd_done_n,
    input             eu_wr_done_n,
    input             eu_opr_free,
    input             eu_opr_free_n,

    // prefetch control
    output            eu_susp,
    output            eu_resume,
    output            eu_halt,
    output            eu_unhalt,
    input             halted,

    // machine state the pins carry
    output            psw_ie,
    output            md8080,

    // pins
    input             pin_int,
    input             pin_nmi,
    input             pin_poll_n,

    // backdoor
    input             bkd_load,
    input     [223:0] bkd_regs,
    output    [223:0] dbg_regs,
    output            dbg_first_pop,
    output            dbg_pend,

    // save-state
    input       [8:0] ss_addr,
    input      [15:0] ss_wdata,
    input             ss_we,
    output reg [15:0] ss_rdata
);

import v30_ss_pkg::*;

`include "pla3_tables.svh"

//============================================================================
// ENCODINGS
//============================================================================

// rows.h bus-status encodings -- the comparator stack's own
localparam bit [2:0] BS_INTA = 3'd0, BS_IOR = 3'd1, BS_IOW = 3'd2,
                     BS_MEMR = 3'd5, BS_MEMW = 3'd6, BS_PASV = 3'd7;

// sim/state.h register indices == the microcode Source1/Dest1 field values
localparam bit [2:0] R_AW = 3'd0, R_CW = 3'd1, R_DW = 3'd2, R_BW = 3'd3,
                     R_SP = 3'd4, R_BP = 3'd5, R_IX = 3'd6, R_IY = 3'd7;
localparam bit [1:0] SR_ES = 2'd0, SR_CS = 2'd1, SR_SS = 2'd2, SR_DS = 2'd3;
localparam bit [2:0] SEG_ZERO = 3'd4;   // physical == offset (vector fetch)

// OperandRef::Kind
localparam bit [1:0] OK_NONE = 2'd0, OK_REG = 2'd1, OK_SREG = 2'd2,
                     OK_MEM = 2'd3;

// sim/state.h PSW bits
localparam int FCY = 0, FP = 2, FAC = 4, FZ = 6, FS = 7,
               FBRK = 8, FIE = 9, FDIR = 10, FV = 11;
localparam bit [15:0] PSW_WRITABLE = 16'h0FD5;
localparam bit [15:0] PSW_FORCED   = 16'hF002;
localparam bit [15:0] ARITH_MASK   = 16'h0000 | (16'd1 << FCY) | (16'd1 << FP)
                                   | (16'd1 << FAC) | (16'd1 << FZ)
                                   | (16'd1 << FS) | (16'd1 << FV);

// sim/state.h AluOp
localparam bit [4:0] A_ADD=5'h00, A_OR=5'h01, A_ADC=5'h02, A_SBB=5'h03,
                     A_AND=5'h04, A_SUB=5'h05, A_XOR=5'h06, A_CMP=5'h07,
                     A_ROL=5'h08, A_ROR=5'h09, A_RCL=5'h0A, A_RCR=5'h0B,
                     A_SHL=5'h0C, A_SHR=5'h0D, A_SHL6=5'h0E, A_SAR=5'h0F,
                     A_ROL12=5'h10, A_DIV=5'h12, A_MUL=5'h13, A_ADJD=5'h14,
                     A_ADJA=5'h15, A_OPC=5'h16, A_BIT=5'h17,
                     A_INC=5'h18, A_DEC=5'h19, A_NOT=5'h1A, A_NEG=5'h1B,
                     A_INC2=5'h1C, A_DEC2=5'h1D, A_ABS=5'h1E, A_PASS=5'h1F;

// ucrom.h MicroType
localparam bit [1:0] TY_ALU = 2'd0, TY_JMP = 2'd1, TY_CTL = 2'd2;

// exec_impl.h Cond
localparam bit [3:0] C_C=4'd0, C_NC=4'd1, C_Z=4'd2, C_NZ=4'd3, C_OP8B=4'd4,
                     C_CNTZ=4'd5, C_L=4'd6, C_OP8=4'd7, C_ALWAYS=4'd8,
                     C_SIGN=4'd9, C_O=4'd10, C_NS=4'd11, C_REP=4'd12,
                     C_BUSY=4'd13, C_INTR=4'd14, C_OPC=4'd15;

// exec_impl.h Ictl / Ectl
localparam bit [3:0] I_ENDEM=4'd0, I_CITF=4'd1, I_MFC=4'd2, I_MFS=4'd3,
                     I_BCDINIT=4'd4, I_CLRCYV=4'd6, I_SETCYV=4'd7, I_SUSP=4'd8,
                     I_FLUSH=4'd9, I_SIGNTGL=4'd12, I_BCDNZ=4'd13,
                     I_FARJMP=4'd14;
localparam bit [2:0] E_MEMR=3'd1, E_MEMW=3'd2, E_INTATAIL=3'd3, E_INTA=3'd5,
                     E_WRITEBACK=3'd6;

// RepKind / RepTest
localparam bit [2:0] REP_NONE=3'd0, REP_E=3'd1, REP_NE=3'd2, REP_C=3'd3,
                     REP_NC=3'd4;
localparam bit [1:0] TEST_NONE=2'd0, TEST_Z=2'd1, TEST_CY=2'd2;

//============================================================================
// STATE
//============================================================================

// --- the architectural file ------------------------------------------------
reg [15:0] gpr [0:7];
reg [15:0] sreg [0:3];
reg [15:0] pc;
reg [15:0] psw;
reg [15:0] tmpa, tmpb, tmpc;
reg [15:0] opr;
reg [15:0] ind;
reg [15:0] count;
reg  [7:0] pfxcnt;
reg [15:0] stat;
reg        sign_neg;
reg  [3:0] bit_n;

// --- the latched micro-ALU (sim/state.h::AluLatch) -------------------------
reg  [4:0] al_op;
reg  [1:0] al_tmp;
reg        al_byte;
reg        al_eaconst;
reg [15:0] al_eaval;
reg  [1:0] al_adjust;      // 0 none, 1 ADJD, 2 ADJA
reg  [1:0] al_adjtmp;
reg        al_bitarm;
reg  [3:0] al_bitn;
reg        al_spent;

// --- the micro-PC ----------------------------------------------------------
reg  [2:0] upc_page;
reg  [7:0] upc_opc;
reg  [3:0] upc_loc;

// --- prefix / pre-decode latches -------------------------------------------
reg        seg_override;
reg  [1:0] seg_ovr;
reg  [2:0] rep_kind;
reg        lock_pfx;
reg  [7:0] opc_reg;
reg        op8, imm8;
reg  [4:0] opc_base;
reg        opc_from_modrm;
reg  [2:0] modrm_reg;
reg  [3:0] xop;
reg  [1:0] rep_test;
reg        rep_pol;
reg        bus_word;
reg        opc8080;
reg        mode8080;
reg        intr_pending;
reg        eu_halted;

// operand latches M / R / WB
reg  [1:0] m_kind, r_kind, wb_kind;
reg  [2:0] m_idx,  r_idx,  wb_idx;
reg [15:0] m_ea,   r_ea,   wb_ea;
reg  [2:0] m_seg,  r_seg,  wb_seg;
reg        m_byte, r_byte, wb_byte;

// --- the write-data pairing latch (exec_impl.h::Pending) --------------------
reg        pend_active;
reg [15:0] pend_off;
reg  [2:0] pend_seg;
reg        pend_byte;
reg        pend_io;
reg        opr_fresh;

// --- the bus interlock bookkeeping (the EU's half) -------------------------
reg [15:0] rdq0, rdq1;     // completed reads awaiting OPR delivery
reg  [1:0] rdq_n;
reg  [1:0] rd_pending;     // posted reads (rd_last) not yet completed
reg  [1:0] rd_done_cnt;    // completed, not yet consumed by an F row
reg        rd_age0;        // the oldest completion pulsed on THIS clock
reg  [1:0] wr_out;         // posted write CYCLES not yet done
reg  [1:0] opr_owned;      // stores that have taken OPR and not released it

// --- the opcode latch ------------------------------------------------------
reg        opc_valid;
reg  [7:0] opc_byte;
reg        pop_is_first;

// --- the loader's working set ----------------------------------------------
reg  [7:0] ld_b;
reg [13:0] ld_pla;
reg        ld_ext;
reg  [2:0] ld_page;
reg        ld_hasrm;
reg  [7:0] ld_rm;
reg [15:0] ld_disp;
reg  [7:0] ld_dlo;
reg        ld_grpd;
reg        ld_byte;
reg        ld_preread;
reg        ld_ripe_prev;   // M8's `pen`: was the byte poppable BEFORE demand?

// --- the sequencer ---------------------------------------------------------
reg  [5:0] st;
reg  [1:0] chg;            // remaining charge clocks of the current step
reg        ending;         // the E row has run; the post-E row is next
reg  [1:0] rowq;           // queue bytes this row has already taken
reg        row_posted;     // this row's bus cycle has been posted
reg        row_paired;     // ...and its data handed over
reg [15:0] rloop_n;        // R-loop iterations still owed
reg        suppress_commit;
reg        first_pop_seen;
reg  [7:0] rowb0, rowb1;   // the queue bytes this row has taken
reg        poste;          // the post-E row's work is owed to the NEXT clock

//----------------------------------------------------------------------------
// STATES.  A state occupies one clock unless marked ZERO-COST, in which case
// it is executed inside the edge that reached it (the chain loop).
//----------------------------------------------------------------------------
localparam bit [5:0]
    S_OPC_POP   = 6'd0,   // pop the instruction's first byte (an F)
    S_TAKE_OPC  = 6'd1,   // ZERO-COST: consume the pre-popped opcode
    S_DECODE    = 6'd2,   // ZERO-COST: the prefix test
    S_DECODE2   = 6'd3,   // ZERO-COST: width / 1BL / ModR/M fan-out
    S_PFX_CHG   = 6'd4,   // a prefix's own second clock
    S_EXT_CHG1  = 6'd5,   // 0F: charge(1) before the second byte
    S_EXT_POP   = 6'd6,   // 0F: the real opcode, popped as an S
    S_1BL_LEAD  = 6'd7,   // wait_retire_lead, then the flag write
    S_MODRM     = 6'd8,   // pop the ModR/M byte (opcode+1)
    S_D8_A      = 6'd9,   // opcode+2: no byte demanded
    S_D8_B      = 6'd10,  // opcode+3: the disp8 (M8's `pen`)
    S_D16_LO    = 6'd11,  // opcode+2
    S_D16_A     = 6'd12,  // opcode+3: no byte demanded
    S_D16_HI    = 6'd13,  // opcode+4: the high byte (M8's `pen`)
    S_EA_CHG    = 6'd14,  // mod != 3, no displacement: the EA-compute clock
    S_EA_CALC   = 6'd15,  // ZERO-COST: the address adder
    S_NORM_CHG  = 6'd16,  // no ModR/M: the opcode+1 clock
    S_BIND      = 6'd17,  // ZERO-COST: group dispatch, OPC select, binding
    S_PRERD     = 6'd18,  // the pre-decode operand read + wait_opr
    S_GRPD_CHG  = 6'd19,  // the second-byte group's extra clock
    S_ENTER     = 6'd20,  // ZERO-COST: enter the micro-sequence
    S_ROW       = 6'd22,  // a micro-row's own clock
    S_ROW_CHG   = 6'd23,  // the taken-JMP / FARJMP redirect bubble
    S_RLOOP     = 6'd24,  // one iterative step per clock
    S_EPOP      = 6'd25,  // the E row's successor pop, deferred
    S_TAIL      = 6'd26,  // ZERO-COST: run_micro's tail
    S_TAIL_W    = 6'd27,  // ...its F interlock + emit_pending
    S_TAIL_POP  = 6'd28,  // ...and its deferred opcode pre-pop
    S_INSTR_END = 6'd29,  // ZERO-COST: step() returns
    S_HALTED    = 6'd30;  // the part is parked

//============================================================================
// THE COMPOSITION (campaign risk #1, second half) -- F7, see the ledger
//============================================================================
// The BIU publishes TWO NAMED VIEWS of every quantity this module consumes
// (v30u_biu's "THE EU CONTRACT" block), and WHICH ONE to read is decided by
// WHERE the value is used, not by what a simulator happens to schedule:
//
//   * the COMBINATIONAL ACT DECODE below (`q_pop`, `eu_post`, `eu_pair`,
//     `q_flush`, `eu_susp`, `eu_halt`) reads the REGISTERED view -- `q_ripe`,
//     `q_byte`, `eu_slot_busy`, `eu_wr_done`, `eu_opr_free`.  An act is
//     consumed by the BIU on the clock that names it, so it must be decided
//     from the BIU's level DURING that clock;
//
//   * THE CLOCKED STEP reads the `_n` view -- `eu_slot_busy_n`,
//     `eu_rd_done_n`, `eu_wr_done_n`, `eu_opr_free_n`, `eu_rdata_n`,
//     `q_ripe_lead_n`, and the `*_n` stall wires derived from them.  That step
//     produces the EU's state for the clock this edge OPENS and must therefore
//     see the BIU as it will be then.
//
//   * `q_ripe` / `q_byte` are read by the clocked step in the REGISTERED view
//     and that is not an exception: the byte the step consumes is the one the
//     BIU handed over on the clock that is ending, which is the clock the pop
//     rode.  Everything else the step consults is the BIU it is stepping into.
//
// Nothing here depends on process order, and no `_n` signal reaches a
// combinational output of this module, so the EU->BIU direction stays a
// registered boundary and closes no loop.  REFUTED, and kept refuted: LATCHING
// the levels in this module -- that puts every pop one clock late (B8 500->123)
// because a latch delays the whole view instead of naming the two.

//============================================================================
// THE MICRO-ROW STANDING ON `upc`
//============================================================================
wire [12:0] dec_addr = {upc_page, upc_opc, upc_loc[3:2]};
wire        dec_valid;
wire  [8:0] dec_bank;
wire [28:0] row;

v30u_ucrom u_ucrom (
    .dec_addr (dec_addr),
    .dec_valid(dec_valid),
    .dec_bank (dec_bank),
    .rom_addr ({dec_bank, upc_loc[1:0]}),
    .rom_word (row)
);

// sw/ucore_tables.py::MicroOp -- the field positions, verbatim
wire [4:0] r_s1   = row[28:24];
wire [4:0] r_d1   = row[23:19];
wire [3:0] r_s2   = row[18:15];
wire [1:0] r_d2   = row[14:13];
wire       r_f    = ~row[12];
wire       r_w    = ~row[11];
wire       r_e    = ~row[10];
wire [1:0] r_type = row[9] ? TY_CTL : (row[8] ? TY_JMP : TY_ALU);
wire [4:0] r_aluop= row[7:3];
wire [1:0] r_alutmp = row[2:1];
wire       r_r    = row[0] && (r_type == TY_ALU);
wire [3:0] r_cond = row[7:4];
wire [3:0] r_loc  = row[3:0];
wire [3:0] r_ictl = row[9:6] & 4'hF;   // {row[9]=1 marks CTL}: ictl = row[8:5]
wire [2:0] r_ectl = row[4:2];
wire [1:0] r_sr   = row[1:0];

// The CTL field split, taken literally from the reference parse:
//     ictl = (bits >> 5) & 15 ; ectl = (bits >> 2) & 7 ; sr = bits & 3
wire [3:0] c_ictl = row[8:5];
wire [2:0] c_ectl = row[4:2];
wire [1:0] c_sr   = row[1:0];

wire       r_farjmp = (r_type == TY_CTL) && (c_ictl == I_FARJMP);
wire [4:0] r_farloc = {c_ectl, c_sr};
wire       r_nopmove = (r_s1 == 5'h1F) && (r_d1 == 5'h1F);
wire       r_hasconst = (r_s1 == 5'h17);
wire [5:0] r_constval = {r_s2, r_d2};
// A FARJMP row aliases Ext:SR as its target, so it has no bus cycle.
wire [2:0] r_ect = r_farjmp ? 3'd7 : c_ectl;

// unmapped micro-address: the model substitutes a NOP CTL row
wire       row_nop = !dec_valid;
wire [4:0] e_s1    = row_nop ? 5'h1F : r_s1;
wire [4:0] e_d1    = row_nop ? 5'h1F : r_d1;
wire [3:0] e_s2    = row_nop ? 4'hF  : r_s2;
wire [1:0] e_d2    = row_nop ? 2'd3  : r_d2;
wire       e_f     = row_nop ? 1'b0  : r_f;
wire       e_w     = row_nop ? 1'b0  : r_w;
wire       e_e     = row_nop ? 1'b0  : r_e;
wire       e_r     = row_nop ? 1'b0  : r_r;
wire [1:0] e_type  = row_nop ? TY_CTL : r_type;
wire [3:0] e_ictl  = row_nop ? 4'hF  : c_ictl;
wire [2:0] e_ectl  = row_nop ? 3'd7  : r_ect;
wire [1:0] e_sr    = row_nop ? 2'd3  : c_sr;
wire       e_farjmp= row_nop ? 1'b0  : r_farjmp;
wire       e_nopmv = row_nop ? 1'b1  : r_nopmove;
wire       e_hasc  = row_nop ? 1'b0  : r_hasconst;

wire e_is_rloop = (e_type == TY_ALU) && e_r;
wire e_have1 = !e_nopmv;
wire e_have2 = !e_hasc && ((e_s2 != 4'd15) || (e_d2 != 2'd3));

//============================================================================
// PLA3 (combinational case ROM, generated)
//============================================================================
wire [1:0] pla_mode = mode8080 ? PLA3_MODE_8080 : PLA3_MODE_NATIVE;
// the byte standing on the queue port, decoded for the HALT one-shot below
wire [13:0] pla_qb  = pla3_lookup(pla_mode, q_byte);

//============================================================================
// SEGMENT / WIDTH HELPERS
//============================================================================
// sim/biu_timed.cpp::seg_code -- sim Sreg ES,CS,SS,DS = 0,1,2,3; the S4:S3 pin
// code is ES,SS,CS,DS = 0,1,2,3.  kSegZero and I/O drive the "no segment"
// code, which is the same encoding as CS.
function automatic [1:0] seg_code(input [2:0] s);
    case (s)
        3'd0: seg_code = 2'd0;   // ES
        3'd1: seg_code = 2'd2;   // CS
        3'd2: seg_code = 2'd1;   // SS
        3'd3: seg_code = 2'd3;   // DS
        default: seg_code = 2'd2;
    endcase
endfunction

// exec_impl.h::sr_is_io -- SR == IO selects the I/O space only for the port /
// block-I/O opcode classes.
wire row_io  = (e_sr == 2'd1) && ((xop == 4'hF) || (xop == 4'h6));
// exec_impl.h::sr_segment
wire [2:0] row_seg = (e_sr == 2'd0) ? 3'd0
                   : (e_sr == 2'd1) ? SEG_ZERO
                   : (e_sr == 2'd2) ? 3'd2
                   : (m_kind == OK_MEM) ? m_seg
                   : (r_kind == OK_MEM) ? r_seg
                   : (seg_override ? {1'b0, seg_ovr} : 3'd3);
// Bus width follows OP8b unless Ext [-03-] has forced WORD (ledger A37).
wire row_bbyte = op8 && !bus_word;

wire [15:0] seg_val = (row_seg == SEG_ZERO) ? 16'h0000 : sreg[row_seg[1:0]];
wire [19:0] row_phys = {seg_val, 4'd0} + {4'd0, ind};

//============================================================================
// STALLS (the five named wires)
//============================================================================
// A row's F interlock: which HALF applies is the direction of the row's own
// touch (exec_impl.h::deliver_read).  A row that READS OPR waits for the read
// that fills it; a row that only LOADS OPR waits only for a store to give OPR
// back.
wire row_reads_opr = (e_s1 == 5'd6);

// wait_next_read(extra): the next outstanding EU read, in order.
wire nr_have   = (rd_done_cnt != 2'd0);
wire nr_wait   = !nr_have && (rd_pending != 2'd0);
// ...and `extra` (wait_opr's +1) bites only when the completion is on THIS
// clock -- otherwise the deadline is already past.
wire nr_extra_block = nr_have && rd_age0;

// wait_opr_free: the store lets go of OPR at its own T2+1 (11.4, fixed index).
// F7: the same term in the two views -- the plain name for the act decode, the
// `_n` name for the clocked step.  ONE expression each, differing only in which
// BIU view it reads.
wire opr_free_now   = (opr_owned == 2'd0) ||
                      ((opr_owned == 2'd1) && eu_opr_free);
wire opr_free_now_n = (opr_owned == 2'd0) ||
                      ((opr_owned == 2'd1) && eu_opr_free_n);

// wait_bus (the retire deadline): every posted store, then its e+2.  ONE view
// only -- `eu_wr_done_n` is registered logic (see the BIU's `done_fire`), so
// the act decode may read it, and act and step MUST read the same thing: they
// are the same event seen from two sides (F11).
wire retire_ok_n = (wr_out == 2'd0) ||
                   ((wr_out == 2'd1) && eu_wr_done_n);

wire f_wait   = row_reads_opr ? (nr_wait || !opr_free_now)   : !opr_free_now;
wire f_wait_n = row_reads_opr ? (nr_wait || !opr_free_now_n) : !opr_free_now_n;

// BUSY is the 9B POLL_N pin, sampled through the same 3-deep pin pipeline the
// INT level goes through (biu_timed.h::poll_busy).  The pipeline itself is U3
// work (the pin-event replay); the static level is what U2 needs.
reg [2:0] poll_pipe;
wire poll_busy = poll_pipe[2];

//============================================================================
// THE ROW'S DEMANDS
//============================================================================
// A queue byte: Source1 [-07-] (Q) and Source2 [-05-] (Q).
wire row_q1 = e_have1 && (e_s1 == 5'd7);
wire row_q2 = e_have2 && (e_s2 == 4'd5);
wire [1:0] row_qn = {1'b0, row_q1} + {1'b0, row_q2};
wire row_need_q  = (st == S_ROW) && ({1'b0, rowq} < row_qn);

// The bus rows.  [-06-] commits OPR to the r/m operand only when that operand
// is memory (the 8F mod==3 ghost).
wire row_wb_mem  = (wb_kind == OK_MEM) && !suppress_commit;
wire row_is_read = (e_type == TY_CTL) && (e_ectl == E_MEMR);
wire row_is_wr   = (e_type == TY_CTL) && (e_ectl == E_MEMW);
wire row_is_wb   = (e_type == TY_CTL) && (e_ectl == E_WRITEBACK) && row_wb_mem;
wire row_is_inta = (e_type == TY_CTL) && (e_ectl == E_INTA);
wire row_bus     = row_is_read || row_is_wr || row_is_wb || row_is_inta;

// the access this row asks for
wire [2:0] acc_seg   = row_is_wb ? wb_seg : row_seg;
wire       acc_byte  = row_is_wb ? wb_byte : row_bbyte;
wire [15:0] acc_off  = row_is_wb ? wb_ea : ind;
wire       acc_io    = row_is_wb ? 1'b0 : row_io;
wire [15:0] acc_segv = (acc_seg == SEG_ZERO) ? 16'h0000 : sreg[acc_seg[1:0]];
wire [19:0] acc_phys = acc_io ? {4'd0, acc_off}
                              : ({acc_segv, 4'd0} + {4'd0, acc_off});
wire [19:0] acc_phys2= acc_io ? {4'd0, acc_off + 16'd1}
                              : ({acc_segv, 4'd0} + {4'd0, acc_off + 16'd1});
wire       acc_split = !acc_byte && acc_phys[0];

// The PRE-DECODE operand read (loader_impl.h): the operand the sequence
// READS, and only that one.
wire        pr_use_m = (m_kind == OK_MEM);
wire  [2:0] pr_seg   = pr_use_m ? m_seg  : r_seg;
wire [15:0] pr_ea    = pr_use_m ? m_ea   : r_ea;
wire        pr_byte  = pr_use_m ? m_byte : r_byte;
wire [19:0] pr_phys  = {sreg[pr_seg[1:0]], 4'd0} + {4'd0, pr_ea};
wire [19:0] pr_phys2 = {sreg[pr_seg[1:0]], 4'd0} + {4'd0, pr_ea + 16'd1};
wire        pr_split = !pr_byte && pr_phys[0];

// The staged write in the pairing latch (exec_impl.h::Pending).
wire [15:0] pend_segv = (pend_seg == SEG_ZERO) ? 16'h0000 : sreg[pend_seg[1:0]];
wire [19:0] pend_phys = pend_io ? {4'd0, pend_off}
                                : ({pend_segv, 4'd0} + {4'd0, pend_off});
wire       pend_split = !pend_byte && pend_phys[0];

//============================================================================
// THE ALU
//============================================================================
function automatic [15:0] szp(input [16:0] r, input bbyte);
    logic [15:0] f;
    logic p;
    begin
        f = 16'd0;
        if (bbyte ? (r[7:0] == 8'd0) : (r[15:0] == 16'd0)) f[FZ] = 1'b1;
        if (bbyte ? r[7] : r[15]) f[FS] = 1'b1;
        p = ^r[7:0];
        if (!p) f[FP] = 1'b1;              // even parity -> P = 1
        szp = f;
    end
endfunction

// alu_opc_select
wire [2:0] opc_sel = opc_from_modrm ? modrm_reg : opc_reg[5:3];
function automatic [4:0] opc8080_map(input [2:0] s);
    case (s)
        3'd0: opc8080_map = A_ADD;
        3'd1: opc8080_map = A_ADC;
        3'd2: opc8080_map = A_SUB;
        3'd3: opc8080_map = A_SBB;
        3'd4: opc8080_map = A_AND;
        3'd5: opc8080_map = A_XOR;
        3'd6: opc8080_map = A_OR;
        default: opc8080_map = A_CMP;
    endcase
endfunction
wire [4:0] alu_opc_sel = opc8080 ? opc8080_map(opc_sel)
                                 : (opc_base + {2'b0, opc_sel});

wire [4:0] eff_op = (al_op == A_OPC) ? alu_opc_sel : al_op;
// the operation the row NOW standing latches (exec_impl.h's `new_op`)
wire [4:0] nxt_op = (r_aluop == A_OPC) ? alu_opc_sel : r_aluop;
wire is_iter = ((eff_op >= A_ROL) && (eff_op <= A_SAR)) ||
               (eff_op == A_ROL12) || (eff_op == A_DIV) || (eff_op == A_MUL);

wire [15:0] tmps [0:3];
assign tmps[0] = tmpa;
assign tmps[1] = tmpb;
assign tmps[2] = tmpc;
assign tmps[3] = 16'd0;
// the same three, read by the row that LATCHES BIT / ABS
wire [15:0] tmps_lat [0:3];
assign tmps_lat[0] = tmpa;
assign tmps_lat[1] = tmpb;
assign tmps_lat[2] = tmpc;
assign tmps_lat[3] = 16'd0;

// The datapath is 16 bits ALWAYS for the ADD-class ops; `byte` selects only
// where the flag taps sit (ledger, "ALU width").
wire ev_byte = al_byte && (eff_op != A_INC2) && (eff_op != A_DEC2);
wire [15:0] port_a = tmpb;
wire [15:0] port_b_raw = tmps[al_tmp];
wire [15:0] port_b = al_bitarm ? (port_b_raw & (16'd1 << al_bitn))
                               : port_b_raw;
wire [15:0] a_m = ev_byte ? {8'd0, port_a[7:0]} : port_a;
wire [15:0] b_m = ev_byte ? {8'd0, port_b[7:0]} : port_b;
wire        cin = psw[FCY];

// --- the BCD adjust unit ---------------------------------------------------
wire [15:0] adj_src = tmps[al_adjtmp];
wire [7:0]  adj_al  = adj_src[7:0];
wire adj_lo  = (adj_al[3:0] > 4'd9) || psw[FAC];
wire adj_hi  = (al_adjust == 2'd1) &&
               (((adj_al[7:4] > 4'd9) || psw[FCY]) ||
                ((adj_al[7:4] == 4'd9) && (adj_al[3:0] > 4'd9) && !psw[FAC]));
wire [7:0] adj_corr = (adj_lo ? 8'h06 : 8'h00) + (adj_hi ? 8'h60 : 8'h00);
wire adj_sub = (eff_op == A_SUB);
wire [8:0] adj_sum = adj_sub ? ({1'b0, adj_al} - {1'b0, adj_corr})
                             : ({1'b0, adj_al} + {1'b0, adj_corr});
wire [7:0] adj_val8 = (al_adjust == 2'd2) ? {4'd0, adj_sum[3:0]} : adj_sum[7:0];
wire [7:0] adj_ahi = adj_src[15:8];
wire [7:0] adj_bhi = port_b[15:8];
wire [7:0] adj_rhi = adj_sub ? (adj_ahi - adj_bhi - {7'd0, adj_sum[8]})
                             : (adj_ahi + adj_bhi + {7'd0, adj_sum[8]});
wire [15:0] adj_flags = szp({9'd0, adj_sum[7:0]}, 1'b1)
                      | (16'd1 << FCY) & {16{(al_adjust == 2'd2) ? adj_lo : adj_hi}}
                      | (16'd1 << FAC) & {16{adj_lo}}
                      | (16'd1 << FV) & {16{adj_sub
                          ? (((adj_al ^ adj_corr) & (adj_al ^ adj_sum[7:0])) & 8'h80) != 8'h00
                          : ((~(adj_al ^ adj_corr) & (adj_al ^ adj_sum[7:0])) & 8'h80) != 8'h00}};

// --- the combinational ops -------------------------------------------------
reg [16:0] ar_full;      // 17-bit so the carry-out is visible
reg [16:0] ar_m;
reg [15:0] ev_val;
reg [15:0] ev_flags;
reg [15:0] ev_mask;
reg        ev_commits;

wire [16:0] add_m = {1'b0, a_m} + {1'b0, b_m} +
                    {16'd0, ((eff_op == A_ADC) ? cin : 1'b0)};
wire [16:0] sub_m = {1'b0, a_m} - {1'b0, b_m} -
                    {16'd0, ((eff_op == A_SBB) ? cin : 1'b0)};
wire [15:0] add_f = port_a + port_b + {15'd0, ((eff_op == A_ADC) ? cin : 1'b0)};
wire [15:0] sub_f = port_a - port_b - {15'd0, ((eff_op == A_SBB) ? cin : 1'b0)};
wire add_cy = ev_byte ? add_m[8] : add_m[16];
wire sub_cy = ev_byte ? sub_m[8] : sub_m[16];
wire add_ac = (a_m[4] ^ b_m[4] ^ add_m[4]);
wire sub_ac = (a_m[4] ^ b_m[4] ^ sub_m[4]);
wire add_ov = ev_byte ? ((~(a_m[7] ^ b_m[7])) & (a_m[7] ^ add_m[7]))
                      : ((~(a_m[15] ^ b_m[15])) & (a_m[15] ^ add_m[15]));
wire sub_ov = ev_byte ? ((a_m[7] ^ b_m[7]) & (a_m[7] ^ sub_m[7]))
                      : ((a_m[15] ^ b_m[15]) & (a_m[15] ^ sub_m[15]));
wire [15:0] inc_m = b_m + 16'd1;
wire [15:0] dec_m = b_m - 16'd1;
wire inc_ac = (b_m[4] ^ 1'b0 ^ inc_m[4]) | (b_m[3:0] == 4'hF);
wire dec_ac = (b_m[3:0] == 4'h0);
wire inc_ov = ev_byte ? (b_m[7:0] == 8'h7F) : (b_m == 16'h7FFF);
wire dec_ov = ev_byte ? (b_m[7:0] == 8'h80) : (b_m == 16'h8000);
wire [15:0] neg_m = 16'd0 - b_m;

always @* begin
    ar_full = 17'd0;
    ar_m    = 17'd0;
    ev_val  = 16'd0;
    ev_flags= 16'd0;
    ev_mask = 16'd0;
    ev_commits = 1'b1;
    case (eff_op)
        A_ADD, A_ADC: begin
            ar_m = add_m; ev_val = add_f; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, add_m[15:0]}, ev_byte);
            ev_flags[FCY] = add_cy;
            ev_flags[FAC] = add_ac;
            ev_flags[FV]  = add_ov;
        end
        A_SUB, A_SBB, A_CMP: begin
            ar_m = sub_m; ev_val = sub_f; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, sub_m[15:0]}, ev_byte);
            ev_flags[FCY] = sub_cy;
            ev_flags[FAC] = sub_ac;
            ev_flags[FV]  = sub_ov;
            if (eff_op == A_CMP) ev_commits = 1'b0;
        end
        A_AND: begin
            ev_val = port_a & port_b; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, a_m & b_m}, ev_byte);
        end
        A_OR: begin
            ev_val = port_a | port_b; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, a_m | b_m}, ev_byte);
        end
        A_XOR: begin
            ev_val = port_a ^ port_b; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, a_m ^ b_m}, ev_byte);
        end
        A_INC: begin
            ev_val = port_b + 16'd1;
            ev_mask = (16'd1<<FP)|(16'd1<<FAC)|(16'd1<<FZ)|(16'd1<<FS)|(16'd1<<FV);
            ev_flags = szp({1'b0, inc_m}, ev_byte);
            ev_flags[FAC] = inc_ac;
            ev_flags[FV]  = inc_ov;
        end
        A_DEC: begin
            ev_val = port_b - 16'd1;
            ev_mask = (16'd1<<FP)|(16'd1<<FAC)|(16'd1<<FZ)|(16'd1<<FS)|(16'd1<<FV);
            ev_flags = szp({1'b0, dec_m}, ev_byte);
            ev_flags[FAC] = dec_ac;
            ev_flags[FV]  = dec_ov;
        end
        A_INC2: begin ev_val = port_b + 16'd2; ev_mask = 16'd0; end
        A_DEC2: begin ev_val = port_b - 16'd2; ev_mask = 16'd0; end
        A_NOT:  begin ev_val = ~port_b;        ev_mask = 16'd0; end
        A_NEG:  begin
            ev_val = 16'd0 - port_b; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, neg_m}, ev_byte);
            ev_flags[FCY] = (ev_byte ? (neg_m[7:0] != 8'd0) : (neg_m != 16'd0));
            ev_flags[FAC] = (b_m[4] ^ neg_m[4]);
            ev_flags[FV]  = ev_byte ? (b_m[7:0] == 8'h80) : (b_m == 16'h8000);
        end
        A_ABS: begin
            // [-1E-]: magnitude.  At byte width only the low lane is replaced.
            if (ev_byte) begin
                ev_val = port_b[7] ? {port_b[15:8], (8'd0 - port_b[7:0])}
                                   : port_b;
            end else begin
                ev_val = port_b[15] ? (16'd0 - port_b) : port_b;
            end
            ev_mask = 16'd0;
        end
        A_ADJD, A_ADJA, A_BIT: begin ev_val = port_b; ev_mask = 16'd0; end
        default: begin   // PASS and everything unlisted
            ev_val = port_b; ev_mask = ARITH_MASK;
            ev_flags = szp({1'b0, b_m}, ev_byte);
        end
    endcase
end

// --- the ONE shared iterative stepper --------------------------------------
// MUL (shift-add), DIV (restoring), ROL12 and the shift/rotate family are the
// SAME unit stepped once per clock; no lpm_divide, no per-op datapath.
wire        it_byte = al_byte;
wire [15:0] it_a    = it_byte ? {8'd0, tmpb[7:0]} : tmpb;
wire [15:0] it_bop  = tmps[al_tmp];
wire [15:0] it_mask = it_byte ? 16'h00FF : 16'hFFFF;
wire        it_msb  = it_byte ? it_a[7] : it_a[15];
wire        it_lsb  = it_a[0];
reg  [15:0] it_val;      // the SIGMA the step presents
reg  [15:0] it_tmpa;     // the multiplier / quotient register after the step
reg  [15:0] it_flags;
reg  [15:0] it_fmask;
reg         it_writes_tmpa;

// MUL
wire [15:0] mul_mplier = it_byte ? {8'd0, tmpa[7:0]} : tmpa;
wire [15:0] mul_mcand  = it_byte ? {8'd0, it_bop[7:0]} : it_bop;
wire [16:0] mul_sum    = {1'b0, it_a} +
                         (mul_mplier[0] ? {1'b0, mul_mcand} : 17'd0);
wire        mul_cout   = it_byte ? mul_sum[8] : mul_sum[16];
wire [15:0] mul_hi     = it_byte
                       ? {8'd0, {mul_cout, mul_sum[7:1]}}
                       : {mul_cout, mul_sum[15:1]};
wire [15:0] mul_lo     = it_byte
                       ? {8'd0, {mul_sum[0], mul_mplier[7:1]}}
                       : {mul_sum[0], mul_mplier[15:1]};
// DIV (restoring)
wire [15:0] div_divisor = it_byte ? {8'd0, it_bop[7:0]} : it_bop;
wire [15:0] div_lo0     = it_byte ? {8'd0, tmpa[7:0]} : tmpa;
wire [16:0] div_hi0     = it_byte
                        ? {9'd0, it_a[6:0], div_lo0[7]}
                        : {1'b0, it_a[14:0], div_lo0[15]};
wire [15:0] div_lo1     = (div_lo0 << 1) & it_mask;
wire        div_fits    = (div_hi0 >= {1'b0, div_divisor});
wire [15:0] div_hi1     = div_fits ? (div_hi0[15:0] - div_divisor)
                                   : div_hi0[15:0];
wire [15:0] div_lo2     = div_fits ? (div_lo1 | 16'd1) : div_lo1;
// shifts / rotates
reg  [15:0] sh_r;
reg         sh_cy;
always @* begin
    sh_cy = 1'b0;
    sh_r  = 16'd0;
    case (eff_op)
        A_ROL: begin sh_cy = it_msb; sh_r = ((it_a << 1) | {15'd0, it_msb}) & it_mask; end
        A_ROR: begin sh_cy = it_lsb; sh_r = ((it_a >> 1) | (it_lsb ? (it_byte ? 16'h0080 : 16'h8000) : 16'd0)) & it_mask; end
        A_RCL: begin sh_cy = it_msb; sh_r = ((it_a << 1) | {15'd0, cin}) & it_mask; end
        A_RCR: begin sh_cy = it_lsb; sh_r = ((it_a >> 1) | (cin ? (it_byte ? 16'h0080 : 16'h8000) : 16'd0)) & it_mask; end
        A_SHL, A_SHL6: begin sh_cy = it_msb; sh_r = (it_a << 1) & it_mask; end
        A_SHR: begin sh_cy = it_lsb; sh_r = (it_a >> 1) & it_mask; end
        A_SAR: begin sh_cy = it_lsb; sh_r = ((it_a >> 1) | (it_msb ? (it_byte ? 16'h0080 : 16'h8000) : 16'd0)) & it_mask; end
        default: ;
    endcase
end
wire sh_left = (eff_op == A_ROL) || (eff_op == A_RCL) ||
               (eff_op == A_SHL) || (eff_op == A_SHL6);
wire sh_rmsb = it_byte ? sh_r[7] : sh_r[15];
wire sh_rmsb1= it_byte ? sh_r[6] : sh_r[14];
wire sh_v    = sh_left ? (sh_rmsb != sh_cy) : (sh_rmsb != sh_rmsb1);
// THE SHIFTER IS TWO 8-BIT LANES FED BY ONE FEEDBACK BIT (alu.cpp).
wire sh_wrap = (eff_op == A_ROR) || (eff_op == A_RCR);
wire sh_fb   = sh_wrap ? sh_r[7] : 1'b0;
wire [7:0] sh_hi = sh_left ? {tmpb[14:8], tmpb[7]}
                           : {sh_fb, tmpb[15:9]};

always @* begin
    it_val   = 16'd0;
    it_tmpa  = tmpa;
    it_flags = 16'd0;
    it_fmask = 16'd0;
    it_writes_tmpa = 1'b0;
    case (eff_op)
        A_MUL: begin
            it_val  = it_byte ? {tmpb[15:8], mul_hi[7:0]} : mul_hi;
            it_tmpa = it_byte ? {tmpa[15:8], mul_lo[7:0]} : mul_lo;
            it_writes_tmpa = 1'b1;
        end
        A_DIV: begin
            it_val  = it_byte ? {tmpb[15:8], div_hi1[7:0]} : div_hi1;
            it_tmpa = it_byte ? {tmpa[15:8], div_lo2[7:0]} : div_lo2;
            it_writes_tmpa = 1'b1;
        end
        A_ROL12: begin
            it_val = {tmpb[14:0], tmpb[11]};
        end
        default: begin
            it_flags[FCY] = sh_cy;
            it_flags[FV]  = sh_v;
            if ((eff_op == A_SHL) || (eff_op == A_SHR) ||
                (eff_op == A_SAR) || (eff_op == A_SHL6)) begin
                it_flags = it_flags | szp({1'b0, sh_r}, it_byte);
                it_fmask = ARITH_MASK;
            end else begin
                it_fmask = (16'd1 << FCY) | (16'd1 << FV);
            end
            it_val = it_byte ? {sh_hi, sh_r[7:0]} : sh_r;
        end
    endcase
end

// SIGMA: what the row's Source1 [-14-] presents.
wire [15:0] sigma = al_eaconst ? al_eaval
                  : is_iter ? (al_spent ? tmpb : it_val)
                            : ev_val;
wire [15:0] sig_flags = is_iter ? it_flags : ev_flags;
wire [15:0] sig_mask  = al_eaconst ? 16'd0
                      : is_iter ? (al_spent ? 16'd0 : it_fmask)
                                : ev_mask;
wire        sig_commits = al_eaconst ? 1'b1 : (is_iter ? 1'b1 : ev_commits);

//============================================================================
// SOURCE / DESTINATION MUXES
//============================================================================
wire [15:0] flags_rd = (psw & PSW_WRITABLE) | PSW_FORCED;

// state.h::rb16 -- the byte-register read is 16 bits wide
function automatic [15:0] rb16(input [2:0] code, input [15:0] pair);
    rb16 = code[2] ? {pair[7:0], pair[15:8]} : pair;
endfunction

wire [15:0] m_rd = (m_kind == OK_REG)  ? (m_byte ? rb16(m_idx, gpr[m_idx[1:0]])
                                                 : gpr[m_idx])
                 : (m_kind == OK_SREG) ? sreg[m_idx[1:0]]
                 : (m_kind == OK_MEM)  ? opr : 16'd0;
wire [15:0] r_rd = (r_kind == OK_REG)  ? (r_byte ? rb16(r_idx, gpr[r_idx[1:0]])
                                                 : gpr[r_idx])
                 : (r_kind == OK_SREG) ? sreg[r_idx[1:0]]
                 : (r_kind == OK_MEM)  ? opr : 16'd0;

wire [15:0] dirsz = (op8 ? (psw[FDIR] ? 16'hFFFF : 16'h0001)
                         : (psw[FDIR] ? 16'hFFFE : 16'h0002));

reg  [15:0] s1_val;
reg         s1_byte;
always @* begin
    s1_byte = 1'b0;
    case (e_s1)
        5'd0,5'd1,5'd2,5'd3: s1_val = sreg[e_s1[1:0]];
        5'd4:  s1_val = pc;
        5'd6:  s1_val = opr;
        5'd7:  begin s1_val = {8'd0, q_byte}; s1_byte = 1'b1; end
        5'd8:  s1_val = dirsz;
        5'd9:  s1_val = 16'd0;
        5'd10: s1_val = {8'd0, pfxcnt};
        5'd12: s1_val = tmpa;
        5'd13: s1_val = tmpb;
        5'd14: s1_val = tmpc;
        5'd15: s1_val = flags_rd;
        5'd16: s1_val = {gpr[R_AW][7:0], gpr[R_AW][15:8]};
        5'd17: s1_val = count;
        5'd18: s1_val = r_rd;
        5'd19: s1_val = m_rd;
        5'd20: s1_val = sigma;
        5'd21: s1_val = 16'hFFFF;
        5'd22: s1_val = {8'd0, opc_reg & 8'h38};
        5'd23: begin s1_val = {10'd0, r_constval}; s1_byte = 1'b1; end
        default: s1_val = (e_s1 >= 5'd24) ? gpr[e_s1[2:0]] : 16'd0;
    endcase
end

reg [15:0] s2_val;
always @* begin
    case (e_s2)
        4'd0: s2_val = 16'hFFFF;
        4'd4: s2_val = sigma;
        4'd5: s2_val = {8'd0, q_byte};
        4'd6: s2_val = 16'd0;
        4'd7: s2_val = r_rd;
        default: s2_val = (e_s2 >= 4'd8) ? gpr[e_s2[2:0]] : 16'd0;
    endcase
end

//============================================================================
// COMBINATIONAL OUTPUTS -- what the BIU samples during THIS clock
//============================================================================
// The F interlock has to be clear before any of the row's acts happen.
wire row_blocked   = (st == S_ROW) && e_f && f_wait;
wire row_blocked_n = (st == S_ROW) && e_f && f_wait_n;

// The row's own queue demand
wire q_demand_row = row_need_q && !row_blocked;

// The E row's successor pop (max-of-two-deadlines: the E row's own clock and
// the retire deadline).  A staged write defers it to the sequence tail.
//
// F11: THE DEMAND AND THE TAKE ARE ONE EVENT.  This wire is what puts the pop
// on the bus; v30u_eu_row.svh's cadence block is what consumes the byte.  They
// must be true on exactly the same clocks, so every term the step applies is a
// term here -- the row must RUN this clock (all four stalls), and the retire
// deadline must count THE WRITE THIS ROW IS ABOUT TO POST, which the step sees
// (it reads `wr_out` after its own increment) and the pre-edge wire did not.
wire       row_slot_wait = row_bus && !row_posted && eu_slot_busy;
wire [2:0] row_wr_add    = (row_is_wr || row_is_wb)
                           ? (acc_split ? 3'd2 : 3'd1) : 3'd0;
wire [2:0] wr_after      = {1'b0, wr_out} + row_wr_add;
wire       retire_ok_e   = (wr_after == 3'd0) ||
                           ((wr_after == 3'd1) && eu_wr_done_n);
// ...and the E row's OWN pairing latch.  `exec_impl.h`'s
// `if (pend_.active && opr_fresh_) emit_pending();` runs IMMEDIATELY BEFORE the
// cadence, so the cadence sees the latch CLEARED -- reading the pre-edge
// `pend_active` here would take a byte the bus was never asked for.  Same two
// terms as `eu_pair` below, which is the act that does the clearing.
wire pend_new   = pend_active || (row_is_wr || row_is_wb);
wire pend_after = pend_new && !(opr_fresh || row_wr_opr);
wire row_epop = (st == S_ROW) && e_e && !pend_after && !opc_valid &&
                !row_blocked && (rowq >= row_qn) && !row_pre_wait &&
                !row_slot_wait && retire_ok_e;

wire q_demand = (st == S_OPC_POP) || (st == S_EXT_POP) || (st == S_MODRM) ||
                (st == S_D16_LO) ||
                ((st == S_D8_B)   && (!ld_ripe_prev ? (chg == 2'd1) : 1'b1)) ||
                ((st == S_D16_HI) && (!ld_ripe_prev ? (chg == 2'd1) : 1'b1)) ||
                q_demand_row || row_epop ||
                // F11 again: both deferred-pop states TAKE the byte only past
                // the retire deadline, so neither may DEMAND it before.
                (((st == S_EPOP) || (st == S_TAIL_POP)) && retire_ok_n);

assign q_pop   = q_demand;
assign q_first = (st == S_OPC_POP) ? pop_is_first
               : (st == S_EPOP) || (st == S_TAIL_POP) || row_epop ? 1'b1
               : 1'b0;

// --- the bus request -------------------------------------------------------
// exec_impl.h::bus_read / bus_write: a staged write must run before the next
// cycle, so the row first pairs it (`emit_pending`) and then posts its own.
wire pend_go = pend_active && opr_fresh;
wire row_pre_pair = row_bus && pend_active;
wire row_pre_wait   = row_pre_pair && !opr_fresh && !opr_free_now;
wire row_pre_wait_n = row_pre_pair && !opr_fresh && !opr_free_now_n;

wire row_acts_ok = (st == S_ROW) && !row_blocked && (rowq >= row_qn) &&
                   !row_pre_wait;

wire pr_active = (st == S_PRERD) && !row_posted;
assign eu_post = (pr_active || (row_acts_ok && row_bus && !row_posted)) &&
                 !eu_slot_busy;
assign eu_bs   = pr_active   ? BS_MEMR
               : row_is_inta ? BS_INTA
               : row_is_read ? (acc_io ? BS_IOR : BS_MEMR)
                             : (acc_io ? BS_IOW : BS_MEMW);
assign eu_addr = pr_active ? pr_phys : (row_is_inta ? 20'd0 : acc_phys);
assign eu_addr2= pr_active ? pr_phys2 : acc_phys2;
assign eu_split= pr_active ? pr_split : (!row_is_inta && acc_split);
assign eu_seg  = pr_active ? seg_code(pr_seg)
               : row_is_inta ? 2'd2 : (acc_io ? 2'd2 : seg_code(acc_seg));
assign eu_word = pr_active ? !pr_byte : (row_is_inta ? 1'b1 : !acc_byte);

// The data pairing (`emit_pending`).  The row's OWN `-> OPR` write counts:
// the model writes OPR and then emits, both on the row's clock, so the value
// the store takes is the one this row is about to put there.
wire row_wr_opr = (st == S_ROW) && e_have1 && !row_blocked &&
                  (rowq >= row_qn) &&
                  ((e_d1 == 5'd6) ||
                   ((e_d1 == 5'd18) && (r_kind == OK_MEM)) ||
                   ((e_d1 == 5'd19) && (m_kind == OK_MEM))) &&
                  !((e_s1 == 5'd20) && !sig_commits);
wire [15:0] opr_now = row_wr_opr
                    ? ((e_s1 == 5'd7) ? {8'd0, q_byte} : s1_val)
                    : opr;
assign eu_pair  = (st == S_ROW) && !row_blocked && (rowq >= row_qn) &&
                  !row_pre_wait &&
                  (pend_active || row_is_wr || row_is_wb) &&
                  (opr_fresh || row_wr_opr);
assign eu_pair2 = pend_active ? pend_split : acc_split;
assign eu_wdata = opr_now;

// --- the CTL strobes -------------------------------------------------------
assign q_flush  = row_acts_ok && (e_type == TY_CTL) && !e_farjmp &&
                  (e_ictl == I_FLUSH);
assign flush_cs = sreg[SR_CS];
assign flush_ip = pc;
assign eu_susp  = row_acts_ok && (e_type == TY_CTL) && !e_farjmp &&
                  (e_ictl == I_SUSP);
assign eu_resume = 1'b0;

// S9a -- HLT IS DECODED, NOT MICROCODED, AND THE DECODE IS WHERE IT ACTS.
// The model's `note_halt` lands in tick(c)'s PRE-ROW block, which in RTL is
// the edge ending c-1 (U1 finding, provenance sec.11.6) -- so `eu_halt` LEADS
// by one clock, and the clock it must ride is the OPCODE'S OWN POP CLOCK.
// One rule, both paths: the loader's own F pop and the E row's pre-pop.
wire qb_is_halt = pla3_one_byte_logic(pla_qb) &&
                  (pla3_xop(pla_qb) == PLA3_BL1_HALT);
assign eu_halt = q_pop && q_ripe && q_first && qb_is_halt && !mode8080 &&
                 !eu_halted;
assign eu_unhalt = 1'b0;

assign psw_ie  = psw[FIE];
assign md8080  = mode8080;

//----------------------------------------------------------------------------
// the backdoor / debug view
//----------------------------------------------------------------------------
assign dbg_regs = {psw, pc, sreg[3], sreg[2], sreg[1], sreg[0],
                   gpr[7], gpr[6], gpr[5], gpr[4],
                   gpr[3], gpr[2], gpr[1], gpr[0]};
assign dbg_first_pop = first_pop_seen;
assign dbg_pend = (rd_pending != 2'd0) || (rdq_n != 2'd0) || poste;

//============================================================================
// THE CLOCK
//============================================================================
`ifndef SYNTHESIS
reg eutrace = 0;
initial if ($test$plusargs("eutrace")) eutrace = 1;
`endif
integer i;
reg        stop;
reg  [3:0] chain;
reg [15:0] v1, v2;
reg        bsw;             // the row's byte-source flag (Q / CONST)
reg [13:0] pv;
reg  [3:0] nloc;
reg        carry, taken, bubble, retire_now;
reg [15:0] ea;
reg  [2:0] rseg;
reg  [1:0] rmmod;
reg  [2:0] rmreg, rmrm;
reg  [1:0] tk;
reg  [2:0] ti, ts;
reg [15:0] te;
reg        tb;

`define SETPSW(v) begin psw = ((v) & PSW_WRITABLE) | PSW_FORCED; end

// commit_flags
task automatic commit_flags(input [15:0] mask, input [15:0] fl);
    begin
        psw = ((psw & ~mask) | (fl & mask));
        psw = (psw & PSW_WRITABLE) | PSW_FORCED;
    end
endtask

always @(posedge clk) begin
    if (ss_we) begin
        `include "v30u_eu_ss_write.svh"
    end else if (srst) begin
        //--------------------------------------------------------------------
        // RESET == begin_case() plus the backdoor injection
        //--------------------------------------------------------------------
        for (i = 0; i < 8; i = i + 1) gpr[i] = 16'd0;
        for (i = 0; i < 4; i = i + 1) sreg[i] = 16'd0;
        pc = 16'd0; psw = PSW_FORCED;
        tmpa = 16'd0; tmpb = 16'd0; tmpc = 16'd0;
        opr = 16'd0; ind = 16'd0; count = 16'd0; pfxcnt = 8'd0;
        stat = 16'd0; sign_neg = 1'b0; bit_n = 4'd0;
        al_op = A_ADD; al_tmp = 2'd0; al_byte = 1'b0;
        al_eaconst = 1'b0; al_eaval = 16'd0;
        al_adjust = 2'd0; al_adjtmp = 2'd0; al_bitarm = 1'b0; al_bitn = 4'd0;
        al_spent = 1'b0;
        upc_page = 3'd0; upc_opc = 8'd0; upc_loc = 4'd0;
        seg_override = 1'b0; seg_ovr = 2'd3; rep_kind = REP_NONE;
        lock_pfx = 1'b0; opc_reg = 8'd0; op8 = 1'b0; imm8 = 1'b0;
        opc_base = 5'd0; opc_from_modrm = 1'b0; modrm_reg = 3'd0; xop = 4'd0;
        rep_test = TEST_NONE; rep_pol = 1'b0; bus_word = 1'b0;
        opc8080 = 1'b0; mode8080 = 1'b0; intr_pending = 1'b0; eu_halted = 1'b0;
        m_kind = OK_NONE; m_idx = 3'd0; m_ea = 16'd0; m_seg = 3'd3; m_byte = 1'b0;
        r_kind = OK_NONE; r_idx = 3'd0; r_ea = 16'd0; r_seg = 3'd3; r_byte = 1'b0;
        wb_kind = OK_NONE; wb_idx = 3'd0; wb_ea = 16'd0; wb_seg = 3'd3;
        wb_byte = 1'b0;
        pend_active = 1'b0; pend_off = 16'd0; pend_seg = 3'd3;
        pend_byte = 1'b0; pend_io = 1'b0; opr_fresh = 1'b0;
        rdq0 = 16'd0; rdq1 = 16'd0; rdq_n = 2'd0;
        rd_pending = 2'd0; rd_done_cnt = 2'd0; rd_age0 = 1'b0;
        wr_out = 2'd0; opr_owned = 2'd0;
        opc_valid = 1'b0; opc_byte = 8'd0; pop_is_first = 1'b1;
        ld_b = 8'd0; ld_pla = 14'd0; ld_ext = 1'b0; ld_page = 3'd0;
        ld_hasrm = 1'b0; ld_rm = 8'd0; ld_disp = 16'd0; ld_dlo = 8'd0;
        ld_grpd = 1'b0; ld_byte = 1'b0; ld_preread = 1'b0; ld_ripe_prev = 1'b0;
        st = S_OPC_POP; chg = 2'd0; ending = 1'b0; poste = 1'b0;
        rowq = 2'd0; row_posted = 1'b0; row_paired = 1'b0; rloop_n = 16'd0;
        suppress_commit = 1'b0; first_pop_seen = 1'b0;
        rowb0 = 8'd0; rowb1 = 8'd0; poste = 1'b0; poll_pipe = 3'b111;
        if (bkd_load) begin
            gpr[0] = bkd_regs[  0 +: 16];  gpr[1] = bkd_regs[ 16 +: 16];
            gpr[2] = bkd_regs[ 32 +: 16];  gpr[3] = bkd_regs[ 48 +: 16];
            gpr[4] = bkd_regs[ 64 +: 16];  gpr[5] = bkd_regs[ 80 +: 16];
            gpr[6] = bkd_regs[ 96 +: 16];  gpr[7] = bkd_regs[112 +: 16];
            sreg[0] = bkd_regs[128 +: 16]; sreg[1] = bkd_regs[144 +: 16];
            sreg[2] = bkd_regs[160 +: 16]; sreg[3] = bkd_regs[176 +: 16];
            pc = bkd_regs[192 +: 16];
            psw = (bkd_regs[208 +: 16] & PSW_WRITABLE) | PSW_FORCED;
        end
    end else if (ce) begin
        //====================================================================
        // (a) the BIU's completion pulses, sampled on the clock they ride
        //====================================================================
        poll_pipe = {poll_pipe[1:0], pin_poll_n};
        rd_age0 = 1'b0;
        if (eu_rd_done_n) begin
`ifndef SYNTHESIS
            // campaign risk #2.  The model's `rd_done_q_` is an unbounded
            // deque; this EU stores TWO completed reads.  That bound is a
            // CLAIM about the microcode, so it is asserted, not assumed --
            // and asserted HERE, where both values are the live ones.
            if (rdq_n == 2'd2)
                $error("v30u_eu: completed-read store overflow (rdq_n=2)");
            if (rd_done_cnt == 2'd3)
                $error("v30u_eu: rd_done_cnt saturated");
`endif
            if (rd_done_cnt == 2'd0) rd_age0 = 1'b1;
            rd_done_cnt = rd_done_cnt + 2'd1;
            if (rd_pending != 2'd0) rd_pending = rd_pending - 2'd1;
            if (rdq_n == 2'd0) rdq0 = eu_rdata_n; else rdq1 = eu_rdata_n;
            rdq_n = rdq_n + 2'd1;
        end
        if (eu_wr_done_n && (wr_out != 2'd0)) wr_out = wr_out - 2'd1;
        if (eu_opr_free_n && (opr_owned != 2'd0)) opr_owned = opr_owned - 2'd1;
        if (q_pop && q_ripe && q_first && !first_pop_seen) first_pop_seen = 1'b1;

        //====================================================================
        // (b) the post-E row's work, owed to THIS clock: it overlaps the
        //     successor's decode (exec_impl.h's cadence note) and the model
        //     runs it BEFORE the successor's step.
        //====================================================================
        if (poste) begin
            poste = 1'b0;
            `include "v30u_eu_poste.svh"
        end

`ifndef SYNTHESIS
        if (eutrace)
            $display("EU st=%0d upc=%0d.%02X.%0d row=%07x q=%02x ripe=%0d slot=%0d post=%0d bs=%0d a=%05x pair=%0d rdd=%0d wrd=%0d oprf=%0d wr_out=%0d pc=%04x",
                     st, upc_page, upc_opc, upc_loc, row, q_byte, q_ripe,
                     eu_slot_busy_n, eu_post, eu_bs, eu_addr, eu_pair,
                     eu_rd_done_n, eu_wr_done_n, eu_opr_free_n, wr_out, pc);
`endif
        stop = 1'b0;
        for (chain = 0; chain < 4'd12; chain = chain + 4'd1) begin
            if (!stop) begin
                `include "v30u_eu_step.svh"
            end
        end
    end
end

//============================================================================
// save-state READ mux (arm #2 of the exactly-twice discipline)
//============================================================================
always @(posedge clk) begin
    `include "v30u_eu_ss_read.svh"
end

wire _unused_eu = &{1'b0, pin_int, pin_nmi, q_cnt, halted, lock_pfx,
                    ar_full, ar_m, row_paired, imm8,
                    adj_val8, adj_rhi, adj_flags,
                    r_ictl, r_ectl, r_sr, r_f, r_w, r_e, r_type, r_nopmove,
                    r_hasconst, r_s1, r_d1, r_s2, r_d2, r_r, dec_valid,
                    SR_ES, SR_SS, SR_DS, R_CW, R_DW, R_SP, BS_PASV,
                    A_SHL6, A_NOT, A_PASS, C_OPC, I_SUSP, I_FLUSH, E_MEMR,
                    TEST_NONE, tk, ti, ts, te, tb, ea, rseg, nloc};

endmodule
