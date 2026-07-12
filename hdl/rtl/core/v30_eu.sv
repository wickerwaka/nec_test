//============================================================================
//
//  v30_eu - V30 (uPD70116) execution unit, Campaign 3 opcode tranche
//
//  Microsequenced FSM whose per-state timing is written directly against
//  the golden-trace event schedules (tests/v30/v0.1, summarized by
//  sw/trace_stats.py). Cycle offsets below are relative to the
//  instruction's first-byte queue pop (F @ 0), prefetched (saturated)
//  variants:
//
//   pops:    modrm @ 1; disp8 @ 3; disp16 lo @ 2, hi @ 4; imm16 @ 2,3
//   EU bus requests become visible to the BIU commit evaluator at the
//   end of the cycle in which eu_req/eu_ready are asserted:
//     loads  (incl. RMW read):  d0/d1: ready @ 4     d2: req @ 4, ready @ 5
//     stores (MOV 88/89):       d0: ready @ 4   d1: req @ 4, ready @ 5
//                               d2: req @ 5-6, ready @ 7
//     PUSH: ready @ 3    POP: ready @ 2
//   post-access:
//     MOV/ALU load: writeback 2 cycles after the access's final T4, F +1
//     store/PUSH/POP: next F directly after the final T4
//     RMW writeback ready: ALU done+3, INC/DEC (FE) done+4, shift (D0)
//     done+6
//     MULU8 exec: EX at cycle 23 (reg) / done+23 (mem)
//     DIVU16:     EX at cycle 27 (reg) / done+27 (mem)
//     IDIV (F6.7/F7.7, mission I; dly relative to the first wait cycle,
//     mem forms +1, s = 3 extra cycles when the dividend is negative):
//       early trap (den=0 or |num_hi| >= |den|): IVT ready @ dly 21+s
//       (byte AND word); late trap (|q| > 2^(n-1)-1, symmetric): byte
//       36+s, word 44+s; non-trap EX: byte 37+s, word 44+s. Divisor and
//       quotient signs cost nothing - only the dividend negate does.
//     DIVU16 trap: IVT read ready at cycle 14 (reg) / done+14 (mem);
//     IVT offset/segment words read back-to-back; PSW push ready
//     IVTdone+3; PS push ready PSWdone+2; the cycle after PSdone raises
//     the queue flush (QS=E) together with the PC push request; the
//     handler prefetch then wins the slot after the PC push by itself.
//
//  Implemented opcodes: 00/08/10/18/20/28/30/38 (ALU rm8,r8), 40-4F,
//  50-57, 58-5F, 86/87 (XCHG), 88/89/8A/8B, 8C/8E (sreg MOV), 8D
//  (LDEA), 90, 98/99 (CVTBW/CVTWL), 9B (POLL), 9D (POP PSW), A0-A3
//  (acc moffs), A4/A5/AA/AB/AC/AD (MOVBK/STM/LDM singles), B8-BF,
//  D0/4, D7 (TRANS), E4/E5/EC/ED (IN), F4 (HALT), F6/4, F6/7 F7/7
//  (IDIV), F7/6, FA/FB (DI/EI), FE/0, the prefixes 26/2E/36/3E
//  (segment override) and F3 (REP), the V30 0F forms 0F18 (TEST1
//  rm8,imm3), 0F20 (ADD4S), 0F28 (ROL4 rm8), and control flow EB/E9
//  (BR), 74/75/7C (Bcc), E2 (DBNZ), E8 (CALL near), C3/C2 (RET).
//  Unknown opcodes park the sequencer (S_HALT). 0F forms pop the
//  second byte at F+2 and the modrm at F+3; standard EA machinery.
//
//  Block 4 (missions L/M/N): INT/NMI recognition at instruction
//  boundaries, the INTA pair + trap-chain vectoring, HALT entry/wake,
//  POLL, IN, EI/DI/POP-PSW IE laws, REP interruption - all timing per
//  docs/facts/interrupt_model.md (fitted against the 15 interrupt
//  tranches + 4 IN tranches, tests/v30/v0.1).
//
//  Mission J laws (per-form goldens, 500 cases each, all cycle-exact):
//   - prefixes retire as their own instruction (own F pop, 2 cycles);
//     the override/REP latch lives until the prefixed instruction
//     retires. A segment override absorbs into the EA machinery
//     (ea_seg_sel mux) at no extra cost - measurements.md law.
//   - moffs forms (A0-A3): address pops @2/3, reservation during the
//     hi pop (like disp pops), access ready hi+1, loads retire at
//     done, stores at done (store data = acc pair).
//   - sreg MOVs: reg forms retire in 2 cycles (S_DEC); 8C mem follows
//     the READER reservation+ready schedule (d0/d1 @4, d2 @5); 8E
//     writeback at done+1 (one faster than 8B).
//   - LDEA: no bus access or reservation; mod0 retires at cycle 2,
//     disp forms at their final disp pop.
//   - TRANS: BX+AL byte read ready @3, retire at done (9 cycles).
//   - string singles: access ready @3 (LDM/STM), retire at done;
//     MOVBK queues its WRITE while the read is in flight - it commits
//     at the read's own T3 edge with the data forwarded inside the
//     BIU (eu_fwd), retire at write done (13 cycles).
//   - REP: first access 2 cycles later than the single form (the
//     extra wait does not reserve the bus); iterations chain via
//     requests raised during the running access (slopes 8/4); CW=0
//     early-out retires at pop+11; REP STM CW=1 retires at the pop+12
//     slot (or completion if later), all other REP retires done+1.
//
//  Control-flow timing (mission E; see docs/facts/biu_model.md for the
//  unified flush law): internal flush X = lastpop+3 (EB/E9), pop+4
//  (Jcc taken), pop+6 (DBNZ taken), hi+3 (CALL, one cycle before its
//  push request; push ready hi+4), done+1 (RET/RET-pop; RET-pop read
//  ready hi+1). Not-taken: Jcc retires end of pop+1, DBNZ pop+2.
//  Reservation starts: EB/E8/C2 at their final pop, E9 pop+1, Jcc/E2
//  pop+2; RET reserves from decode through the stack read.
//
//  Undefined-flag behavior per docs/facts/undefined_flags.md, with laws
//  discovered from the golden traces (each verified on all 500 cases):
//   - DIVU's entire flag residue = the flags of its 16-bit overflow
//     pre-check compare SUB(DW, divisor); the trap condition is that
//     compare's !borrow, and the trapped and non-trapped paths leave
//     exactly those compare flags (pushed PSW included).
//   - Byte RMW memory ops compute across the full 16-bit internal pair
//     ({sibling, byte}, source pair likewise) and drive the whole
//     16-bit result on the bus; carries/shifts propagate into the
//     driven (unwritten) sibling lane. Flags come from the byte op.
//   - XCHG mem timing = the ALU RMW path (write ready done+3); the
//     write drives the pre-exchange register pair, no flags.
//   - ROL4 rotates the WHOLE AL: rm <- {rm[3:0], AL[3:0]},
//     AL <- {AL[3:0], rm[7:4]} (manual implies AL[7:4] preserved; it
//     is not). Mem form drives {AL_new, mem_new}; write ready done+11;
//     reg form takes 11 wait cycles. No flags.
//   - ADD4S is a nibble-serial BCD adder: see bcd_add8 below for the
//     carry-rail quirk, pre-adjust Z, and the driven-sibling law.
//     Flags: CY=S=AC=carry, Z=P=zacc, V=0. Loop: src(DS0:IX+k) rd,
//     dst(DS1:IY+k) rd, wr per byte; ready offsets src=pop2+5 /
//     wrdone+1, dst=srcdone+2, wr=dstdone+4; the EU holds a bus
//     reservation from the first src request through retire; retire
//     at last wrdone+4 (carry) / +5 (no carry).
//
//============================================================================

module v30_eu (
    input             clk,
    input             srst,

    // queue side
    input       [7:0] q_byte,
    input             q_avail,
    input             q_avail2,
    input             q_any,
    output            q_pop,
    output            q_first,
    output            q_flush,
    output     [15:0] flush_cs,
    output     [15:0] flush_ip,

    // BIU access side
    output reg        eu_req,
    output            eu_hold,     // blocks prefetch without counting as
                                   // request history (trap-chain gaps)
    output reg        eu_ready,
    output reg        eu_wr,
    output            eu_fwd,     // write data = the BIU's last read data
                                  // (string-op read->write forwarding)
    output reg        eu_word,
    output reg [19:0] eu_addr,
    output reg  [1:0] eu_seg,
    output reg [15:0] eu_wdata,
    output reg  [1:0] eu_kind,    // 0=mem 1=io 2=inta 3=halt
    input             eu_started,
    input             eu_done,
    input             eu_wdone,   // early write completion (trap chain law)
    input             eu_t1,      // pulse: first T1 of the current EU access
    input      [15:0] eu_rdata,
    input             eu_rd_now,   // early strobe: read data edge (end T3)
    input      [15:0] eu_rdata_now,

    output            psw_ie,
    output reg        halt_disp,   // HALT decoded: BIU shows the HALT
                                   // pseudo-cycle at its display law

    // external event pins (synchronized here)
    input             pin_int,
    input             pin_nmi,
    input             pin_poll_n,

    // TB backdoor (verification only): load/observe architectural state
    input             bkd_load,
    input     [223:0] bkd_regs,   // {psw,ip,ds,ss,cs,es,di,si,bp,sp,bx,dx,cx,ax}
    output    [223:0] dbg_regs,
    output            dbg_first_pop
);

// PS1:0 segment-status codes (= AD17:16 during T2-T4)
localparam bit [1:0] SEG_ES = 2'd0;   // DS1
localparam bit [1:0] SEG_SS = 2'd1;
localparam bit [1:0] SEG_CS = 2'd2;   // PS
localparam bit [1:0] SEG_DS = 2'd3;   // DS0

// PSW bits
localparam int FB_CY = 0, FB_P = 2, FB_AC = 4, FB_Z = 6, FB_S = 7,
               FB_V = 11;

// BIU access kinds
localparam bit [1:0] K_MEM  = 2'd0;
localparam bit [1:0] K_IO   = 2'd1;
localparam bit [1:0] K_INTA = 2'd2;

//----------------------------------------------------------------------------
// architectural state
//----------------------------------------------------------------------------
reg [15:0] rf [0:7];    // AW CW DW BW SP BP IX IY
reg [15:0] sr [0:3];    // DS1(ES) SS PS(CS) DS0(DS)
reg [15:0] psw;
reg [15:0] pc;          // running fetch-stream offset (past popped bytes)
reg [15:0] arch_ip;     // instruction-boundary IP (retire-updated)

assign psw_ie = psw[9];

//----------------------------------------------------------------------------
// microsequencer state
//----------------------------------------------------------------------------
typedef enum logic [6:0] {
    S_HALT, S_FIRST, S_DEC,
    S_IMM_LO, S_IMM_HI, S_NOP,
    S_EA1, S_EA2, S_DISP8, S_DLO, S_DGAP, S_DHI, S_DSTALL,
    S_RSV, S_REQ, S_BUSW,
    S_PUSH_CALC,
    S_LD_W1, S_LD_W2,
    S_WAITX, S_EX,
    S_RMWX, S_WREQ, S_WBUSW,
    S_0F, S_DEC2, S_T1GAP, S_IMM3,
    S_A4_SETUP, S_A4_SRC, S_A4_SRCW, S_A4_G1, S_A4_DST, S_A4_DSTW,
    S_A4_G2, S_A4_WR, S_A4_WRW, S_A4_END,
    S_JDISP, S_JDLO, S_JDHI, S_JWAIT, S_JNT, S_JFLUSH,
    S_JSLO, S_JSHI, S_MLO, S_MHI, S_RESET,
    S_STRW, S_STRR, S_STRS, S_STRE,
    S_CALLFL, S_CALLPUSH, S_CALLW, S_RETF,
    S_TRAP_IVT1, S_TRAP_IVT2, S_TRAP_IVT2W,
    S_TRAP_W1, S_TRAP_PSW, S_TRAP_PSWW,
    S_TRAP_W2, S_TRAP_PS, S_TRAP_PSW2W,
    S_TRAP_FLUSH, S_TRAP_PC, S_TRAP_PCW,
    S_IRQ_D, S_INT_W0, S_INT_A1, S_INT_A1W, S_INT_G, S_INT_A2, S_INT_A2W,
    S_IRQ_REPW, S_IRQ_REPFL,
    S_HALTED, S_HWAIT,
    S_POLL_WAIT, S_POLL_X,
    S_IN_PORT
} state_e;

state_e     state;
reg  [5:0]  dly;         // countdown for S_WAITX / S_RMWX / S_RSV / S_TRAP_W*
state_e     wnext;       // state entered when S_WAITX expires
state_e     dret;        // disp-pop state resumed after a queue-dry stall

reg  [7:0]  opc;
reg  [7:0]  opc2;        // 0F-prefixed second byte
reg  [7:0]  mrm;
reg  [7:0]  immb;        // TEST1 imm3 byte
reg [15:0]  disp;
// ADD4S loop state
reg  [7:0]  a4_cnt;      // bytes remaining
reg  [7:0]  a4_k;        // byte index (address offset)
reg [15:0]  a4_src;      // latched source read ({other lane, byte})
reg         a4_carry;    // BCD carry chain
reg         a4_z;        // accumulated zero flag (pre-adjust bytes)
reg [15:0]  mem_op;      // operand as read ({sibling, byte} for byte ops)
reg [15:0]  ivt_off, ivt_seg;
reg [15:0]  trap_psw;
// prefix latches (segment override / REP), cleared when the prefixed
// instruction retires
reg         seg_ovr_en;
reg  [1:0]  seg_ovr;
reg         rep_en;
reg         flush_now;   // registered flush (trap path)
reg         str_wr;      // MOVBK phase: write half of the element
reg  [5:0]  rslot;       // REP retire slot: counts from the opcode pop
reg         str_done;    // final string access completed (S_STRE)
reg [15:0]  fl_cs, fl_ip; // flush redirect target
// external-event machinery (block 4). The recognition sample is the
// boundary-decision cycle reading a 4-deep pin pipeline (fitted: the
// latest catching INT assert is boundary-4, NMI edge boundary-5).
reg  [3:0]  int_p;
reg  [4:0]  nmi_p;
reg         nmi_latch;           // NMI is edge-triggered and latched
reg         poll_s1;             // POLL_N synchronizer
reg         shadow;              // recognition shadow (sreg loads)
reg         ie_pend, ie_val;     // deferred EI/DI IE write (dry queue)
reg  [15:0] psw_old;             // pre-POP-PSW value (see pop_pend)
reg         pop_pend;            // POP PSW committed early; an interrupt
                                 // at its boundary pushes the NEW value
                                 // but the LIVE psw reverts to psw_old
                                 // before the IE/BRK clear (measured)
reg  [2:0]  ie_p;                // IE history: the boundary decision
                                 // uses IE@B-3 (this delay IS the EI /
                                 // POP-PSW enable shadow - measured)
reg [15:0]  insn_ip;             // first byte of the current instruction
                                 // INCLUDING prefixes (REP resume point)
reg  [7:0]  ivt_vec;             // vector for the S_TRAP_IVT1 chain
reg         hwake_ie0;           // HALT released by masked INT: resume
reg         irq_disp;            // current WAITX is an interrupt dispatch

wire [2:0] mrm_reg = mrm[5:3];
wire [2:0] mrm_rm  = mrm[2:0];
wire [1:0] mrm_mod = mrm[7:6];

//----------------------------------------------------------------------------
// decode
//----------------------------------------------------------------------------
wire op_alu    = (opc & 8'hC7) == 8'h00;             // 00,08,..,38 rm8,r8
wire op_movs8  = opc == 8'h88;
wire op_movs16 = opc == 8'h89;
wire op_movl8  = opc == 8'h8A;
wire op_movl16 = opc == 8'h8B;
wire op_grpf6  = opc == 8'hF6;                       // /4 MULU8 only
wire op_grpf7  = opc == 8'hF7;                       // /6 DIVU16 only
wire op_grpd0  = opc == 8'hD0;                       // /4 SHL8,1 only
wire op_grpfe  = opc == 8'hFE;                       // /0 INC8 only
wire op_xchg8  = opc == 8'h86;
wire op_xchg16 = opc == 8'h87;
wire op_jcc    = opc == 8'h74 || opc == 8'h75 || opc == 8'h7C;
wire op_ret    = opc == 8'hC3 || opc == 8'hC2;
wire op_moff   = opc == 8'hA0 || opc == 8'hA1;   // MOV AL/AW, moffs16
wire op_moffw  = opc == 8'hA2 || opc == 8'hA3;   // MOV moffs16, AL/AW
wire op_lea    = opc == 8'h8D;                   // LDEA
wire op_srst   = opc == 8'h8C;                   // MOV rm16, sreg
wire op_srld   = opc == 8'h8E;                   // MOV sreg, rm16
wire op_xlat   = opc == 8'hD7;                   // TRANS
wire op_movstr = opc == 8'hA4 || opc == 8'hA5;   // MOVBK
wire op_stostr = opc == 8'hAA || opc == 8'hAB;   // STM
wire op_lodstr = opc == 8'hAC || opc == 8'hAD;   // LDM
wire op_str    = op_movstr | op_stostr | op_lodstr;
wire op_segp   = opc == 8'h26 || opc == 8'h2E ||
                 opc == 8'h36 || opc == 8'h3E;   // segment override
wire op_repp   = opc == 8'hF3;                   // REP/REPE prefix
wire jcc_taken = (opc == 8'h74) ?  psw[FB_Z] :
                 (opc == 8'h75) ? !psw[FB_Z] :
                                   psw[FB_S] ^ psw[FB_V];   // 7C BLT
wire op_in     = opc == 8'hE4 || opc == 8'hE5 ||
                 opc == 8'hEC || opc == 8'hED;   // IN acc,imm8 / acc,DW
wire op_0f     = opc == 8'h0F;                       // two-byte forms
wire op_test1  = op_0f && opc2 == 8'h18;             // TEST1 rm8,imm3
wire op_rol4   = op_0f && opc2 == 8'h28;             // ROL4 rm8
wire op_modrm  = op_alu | op_movs8 | op_movs16 | op_movl8 | op_movl16 |
                 op_grpf6 | op_grpf7 | op_grpd0 | op_grpfe |
                 op_xchg8 | op_xchg16 | op_lea | op_srst | op_srld;

wire is_store  = op_movs8 | op_movs16 | op_srst;     // write-only mem access
wire is_load   = op_movl8 | op_movl16 | op_srld;
wire is_word_t = op_movs16 | op_movl16 | op_grpf7 |  // word transfer
                 op_xchg16 | op_srst | op_srld;
wire is_reader = !is_store;                          // mem forms read first

//----------------------------------------------------------------------------
// effective address
//----------------------------------------------------------------------------
wire [15:0] ea_base =
    (mrm_rm == 3'd0) ? rf[3] + rf[6] :
    (mrm_rm == 3'd1) ? rf[3] + rf[7] :
    (mrm_rm == 3'd2) ? rf[5] + rf[6] :
    (mrm_rm == 3'd3) ? rf[5] + rf[7] :
    (mrm_rm == 3'd4) ? rf[6] :
    (mrm_rm == 3'd5) ? rf[7] :
    (mrm_rm == 3'd6) ? ((mrm_mod == 2'd0) ? 16'd0 : rf[5]) :
                       rf[3];

wire [1:0] ea_seg_def =
    (mrm_rm == 3'd2 || mrm_rm == 3'd3 ||
     (mrm_rm == 3'd6 && mrm_mod != 2'd0)) ? SEG_SS : SEG_DS;
// a segment-override prefix absorbs the default (measurements.md law)
wire [1:0] ea_seg_sel = seg_ovr_en ? seg_ovr : ea_seg_def;

// modrm sreg field (0=ES 1=CS 2=SS 3=DS) -> sr[] index
function automatic [1:0] srmap(input [1:0] f);
    srmap = (f == 2'd1) ? SEG_CS : (f == 2'd2) ? SEG_SS : f;
endfunction

//----------------------------------------------------------------------------
// register-operand helpers
//----------------------------------------------------------------------------
function automatic [7:0] reg8_get(input [2:0] r);
    reg8_get = r[2] ? rf[{1'b0, r[1:0]}][15:8] : rf[{1'b0, r[1:0]}][7:0];
endfunction

// 16-bit register pair holding a byte register, arranged {sibling, byte}
function automatic [15:0] reg8_pair(input [2:0] r);
    logic [15:0] w;
    w = rf[{1'b0, r[1:0]}];
    reg8_pair = r[2] ? {w[7:0], w[15:8]} : w;
endfunction

task automatic wr_reg8(input [2:0] r, input [7:0] v);
    if (r[2]) rf[{1'b0, r[1:0]}][15:8] <= v;
    else      rf[{1'b0, r[1:0]}][7:0]  <= v;
endtask

//----------------------------------------------------------------------------
// flag/ALU helpers. Return {new_psw[15:0], result}.
//----------------------------------------------------------------------------
function automatic [23:0] alu8(input [2:0] op, input [7:0] a, input [7:0] b,
                               input [15:0] f);
    logic [8:0]  t;
    logic [4:0]  tn;
    logic [7:0]  r;
    logic [15:0] nf;
    logic        logic_op;
    logic_op = (op == 3'd1) || (op == 3'd4) || (op == 3'd6);
    tn = '0;
    unique case (op)
        3'd0: begin t = {1'b0,a} + {1'b0,b};
                    tn = {1'b0,a[3:0]} + {1'b0,b[3:0]}; end
        3'd2: begin t = {1'b0,a} + {1'b0,b} + {8'd0, f[FB_CY]};
                    tn = {1'b0,a[3:0]} + {1'b0,b[3:0]} + {4'd0, f[FB_CY]}; end
        3'd3: begin t = {1'b0,a} - {1'b0,b} - {8'd0, f[FB_CY]};
                    tn = {1'b0,a[3:0]} - {1'b0,b[3:0]} - {4'd0, f[FB_CY]}; end
        3'd5, 3'd7:
              begin t = {1'b0,a} - {1'b0,b};
                    tn = {1'b0,a[3:0]} - {1'b0,b[3:0]}; end
        3'd1: t = {1'b0, a | b};
        3'd4: t = {1'b0, a & b};
        3'd6: t = {1'b0, a ^ b};
        default: t = '0;
    endcase
    r = t[7:0];
    nf = f;
    if (logic_op) begin
        nf[FB_CY] = 1'b0;
        nf[FB_AC] = 1'b0;
        nf[FB_V]  = 1'b0;
    end else begin
        nf[FB_CY] = t[8];
        nf[FB_AC] = tn[4];
        if (op == 3'd0 || op == 3'd2)
            nf[FB_V] = (~(a[7] ^ b[7])) & (a[7] ^ r[7]);
        else
            nf[FB_V] = (a[7] ^ b[7]) & (a[7] ^ r[7]);
    end
    nf[FB_S] = r[7];
    nf[FB_Z] = r == 8'd0;
    nf[FB_P] = ~^r;
    alu8 = {nf, r};
endfunction

function automatic [23:0] inc8(input [7:0] a, input [15:0] f);
    logic [7:0] r;
    logic [15:0] nf;
    r = a + 8'd1;
    nf = f;
    nf[FB_AC] = a[3:0] == 4'hF;
    nf[FB_V]  = r == 8'h80;
    nf[FB_S]  = r[7];
    nf[FB_Z]  = r == 8'd0;
    nf[FB_P]  = ~^r;
    inc8 = {nf, r};
endfunction

function automatic [23:0] shl8_1(input [7:0] a, input [15:0] f);
    logic [7:0] r;
    logic [15:0] nf;
    r = {a[6:0], 1'b0};
    nf = f;
    nf[FB_CY] = a[7];
    nf[FB_V]  = r[7] ^ a[7];
    nf[FB_AC] = 1'b0;
    nf[FB_S]  = r[7];
    nf[FB_Z]  = r == 8'd0;
    nf[FB_P]  = ~^r;
    shl8_1 = {nf, r};
endfunction

function automatic [31:0] incdec16(input dec, input [15:0] a,
                                   input [15:0] f);
    logic [15:0] r;
    logic [15:0] nf;
    r = dec ? a - 16'd1 : a + 16'd1;
    nf = f;
    nf[FB_AC] = dec ? (a[3:0] == 4'h0) : (a[3:0] == 4'hF);
    nf[FB_V]  = dec ? (a == 16'h8000) : (r == 16'h8000);
    nf[FB_S]  = r[15];
    nf[FB_Z]  = r == 16'd0;
    nf[FB_P]  = ~^r[7:0];
    incdec16 = {nf, r};
endfunction

// 32/16 unsigned divide: {trap, quotient, remainder}. The trap condition
// is "no borrow" from the overflow pre-check compare (below).
function automatic [32:0] divu32(input [31:0] num, input [15:0] den);
    logic [31:0] q32, r32;
    if (den == 16'd0 || num[31:16] >= den) begin
        divu32 = {1'b1, 32'd0};
    end else begin
        q32 = num / {16'd0, den};
        r32 = num % {16'd0, den};
        divu32 = {1'b0, q32[15:0], r32[15:0]};
    end
endfunction

// Signed divides (IDIV): magnitude divide + sign fixups, per the laws in
// docs/facts/undefined_flags.md (mission F) and the mission-I timing fit.
// Returns {early, late, flags, quotient, remainder}:
//  - early trap = divisor 0 or magnitude pre-check |num_high| >=
//    |divisor|; late trap = unsigned quotient magnitude exceeds
//    2^(n-1)-1 (SYMMETRIC: quotient -2^(n-1) traps too).
//  - flags: early trap leaves the residue of the magnitude pre-check
//    compare SUB(|num_high|, |divisor|) at operand width; late-trap and
//    non-trap paths leave S/Z/P of the UNSIGNED quotient magnitude with
//    CY=AC=V=0 (the sign-fixup micro-ops never touch flags).
//  - quotient truncates toward zero, remainder sign follows the
//    dividend.
function automatic [49:0] idiv32(input [31:0] num, input [15:0] den,
                                 input [15:0] f);
    logic [31:0] an, q32, r32;
    logic [15:0] ad, q, r, nf;
    logic early, late;
    an = num[31] ? (~num + 32'd1) : num;
    ad = den[15] ? (~den + 16'd1) : den;
    early = (den == 16'd0) || (an[31:16] >= ad);
    if (early) begin
        q32 = '0; r32 = '0;
    end else begin
        q32 = an / {16'd0, ad};
        r32 = an % {16'd0, ad};
    end
    late = !early && (q32 > 32'd32767);
    if (early)
        nf = psw_sub16(an[31:16], ad, f);
    else begin
        nf = f;
        nf[FB_S]  = q32[15];
        nf[FB_Z]  = q32[15:0] == 16'd0;
        nf[FB_P]  = ~^q32[7:0];
        nf[FB_CY] = 1'b0;
        nf[FB_AC] = 1'b0;
        nf[FB_V]  = 1'b0;
    end
    q = (num[31] ^ den[15]) ? (~q32[15:0] + 16'd1) : q32[15:0];
    r = num[31] ? (~r32[15:0] + 16'd1) : r32[15:0];
    idiv32 = {early, late, nf, q, r};
endfunction

function automatic [33:0] idiv16(input [15:0] num, input [7:0] den,
                                 input [15:0] f);
    logic [15:0] an, q16, r16, nf;
    logic  [7:0] ad, q, r;
    logic [23:0] t;
    logic early, late;
    an = num[15] ? (~num + 16'd1) : num;
    ad = den[7] ? (~den + 8'd1) : den;
    early = (den == 8'd0) || (an[15:8] >= ad);
    if (early) begin
        q16 = '0; r16 = '0;
    end else begin
        q16 = an / {8'd0, ad};
        r16 = an % {8'd0, ad};
    end
    late = !early && (q16 > 16'd127);
    if (early) begin
        t = alu8(3'd5, an[15:8], ad, f);    // SUB8 compare residue
        nf = t[23:8];
    end else begin
        nf = f;
        nf[FB_S]  = q16[7];
        nf[FB_Z]  = q16[7:0] == 8'd0;
        nf[FB_P]  = ~^q16[7:0];
        nf[FB_CY] = 1'b0;
        nf[FB_AC] = 1'b0;
        nf[FB_V]  = 1'b0;
    end
    q = (num[15] ^ den[7]) ? (~q16[7:0] + 8'd1) : q16[7:0];
    r = num[15] ? (~r16[7:0] + 8'd1) : r16[7:0];
    idiv16 = {early, late, nf, q, r};
endfunction

// ADD4S packed-BCD byte add, nibble-serial as the silicon does it
// (fitted bit-exact on all 1020 golden byte iterations):
//  - low digit: binary nibble add; +6 adjust if it carried (c1) or
//    exceeded 9 (c2);
//  - high digit SUM takes c1+c2 as two carries, but the high ADJUST
//    DECISION sees only c1|c2 (single carry rail): fire = ahi+bhi+
//    (c1|c2) > 9. CY out = fire.
//  - sibx marks the extra +1 the driven sibling lane picks up when the
//    high sum carried (c3) and its pre-adjust digit exceeds 9.
//  - prez: the PRE-adjust byte was zero (Z accumulates on this, not on
//    the adjusted result).
// Returns {fire, sibx, prez, result}.
function automatic [10:0] bcd_add8(input [7:0] a, input [7:0] b, input cin);
    logic [4:0] lo, hi;
    logic       c1, c2, c3, fire, sibx, prez;
    logic [3:0] dlo0, dlo, dhi0, dhi;
    lo = {1'b0, a[3:0]} + {1'b0, b[3:0]} + {4'd0, cin};
    c1 = lo[4];
    dlo0 = lo[3:0];
    c2 = dlo0 > 4'd9;
    dlo = (c1 || c2) ? dlo0 + 4'd6 : dlo0;
    hi = {1'b0, a[7:4]} + {1'b0, b[7:4]} + {4'd0, c1} + {4'd0, c2};
    c3 = hi[4];
    dhi0 = hi[3:0];
    fire = ({1'b0, a[7:4]} + {1'b0, b[7:4]} + {4'd0, c1 | c2}) > 5'd9;
    dhi = fire ? dhi0 + 4'd6 : dhi0;
    sibx = c3 && (dhi0 > 4'd9);
    prez = (dhi0 == 4'd0) && (dlo0 == 4'd0);
    bcd_add8 = {fire, sibx, prez, dhi, dlo};
endfunction

// DIVU leaves the flags of its 16-bit overflow pre-check compare
// SUB(DW, divisor) - verified bit-exact on all 500 golden cases, both
// the trap residue (pushed PSW) and the non-trap final flags. The
// "forced constant" pattern in undefined_flags.md is the special case
// dx < den of this law.
function automatic [15:0] psw_sub16(input [15:0] a, input [15:0] b,
                                    input [15:0] f);
    logic [15:0] r;
    logic [15:0] nf;
    r = a - b;
    nf = f;
    nf[FB_CY] = b > a;
    nf[FB_AC] = b[3:0] > a[3:0];
    nf[FB_V]  = ((a[15] ^ b[15]) & (a[15] ^ r[15]));
    nf[FB_S]  = r[15];
    nf[FB_Z]  = r == 16'd0;
    nf[FB_P]  = ~^r[7:0];
    psw_sub16 = nf;
endfunction

//----------------------------------------------------------------------------
// execute-stage combinational results (operand a = rm, b = reg)
//----------------------------------------------------------------------------
wire [7:0]  rm_byte = (mrm_mod == 2'd3) ? reg8_get(mrm_rm) : mem_op[7:0];
wire [23:0] ex_alu  = alu8(opc[5:3], rm_byte, reg8_get(mrm_reg), psw);
wire [23:0] ex_inc  = inc8(rm_byte, psw);
wire [23:0] ex_shl  = shl8_1(rm_byte, psw);

// Byte RMW mem ops run their operation across the full 16-bit internal
// pair ({sibling, byte}) and drive the whole result onto the bus; only
// the active lane commits to memory but carries/shifts propagate into
// the driven sibling byte (measured). Flags still come from the byte op.
wire [15:0] src_pair = reg8_pair(mrm_reg);
wire [15:0] rmw_wide =
    op_grpfe ? mem_op + 16'd1 :
    op_grpd0 ? {mem_op[14:0], 1'b0} :
    (opc[5:3] == 3'd0) ? mem_op + src_pair :
    (opc[5:3] == 3'd2) ? mem_op + src_pair + {15'd0, psw[FB_CY]} :
    (opc[5:3] == 3'd3) ? mem_op - src_pair - {15'd0, psw[FB_CY]} :
    (opc[5:3] == 3'd5) ? mem_op - src_pair :
    (opc[5:3] == 3'd1) ? (mem_op | src_pair) :
    (opc[5:3] == 3'd4) ? (mem_op & src_pair) :
                         (mem_op ^ src_pair);

//----------------------------------------------------------------------------
// interrupt recognition (measured laws: docs/facts/interrupt_model.md)
// - sampled once per instruction at its boundary (S_FIRST)
// - blocked for one boundary by sreg loads and EI (shadow), and always
//   between a prefix and its instruction (live prefix latches)
// - NMI is edge-latched and ignores IE; INT is a level gated by IE
//----------------------------------------------------------------------------
wire irq_int  = int_p[2] && ie_p[2];
wire irq_any  = nmi_latch || irq_int;
wire irq_take = irq_any && !shadow && !rep_en && !seg_ovr_en;
// REP iteration-boundary sampling runs one stage deeper (fitted)
wire irq_rep  = nmi_latch || (int_p[3] && psw[9]);

//----------------------------------------------------------------------------
// queue pop control
//----------------------------------------------------------------------------
wire pop_want = (state == S_FIRST && !irq_take) ||
                (state == S_DEC && op_modrm) ||
                (state == S_0F) || (state == S_DEC2) || (state == S_IMM3) ||
                (state == S_IMM_LO) || (state == S_IMM_HI) ||
                (state == S_IN_PORT) ||
                (state == S_DISP8) || (state == S_DLO) || (state == S_DHI) ||
                (state == S_JDISP) || (state == S_JDLO) ||
                (state == S_JDHI) || (state == S_JSLO) ||
                (state == S_JSHI) || (state == S_MLO) || (state == S_MHI);

assign q_pop   = pop_want && q_avail;
assign q_first = state == S_FIRST;
// flush: registered for the trap path; combinational for branch flush
// cycles (S_JFLUSH/S_RETF) and CALL's push-status cycle
assign q_flush = flush_now || (state == S_JFLUSH) || (state == S_RETF) ||
                 (state == S_CALLFL) || (state == S_IRQ_REPFL);
assign flush_cs = fl_cs;
assign flush_ip = fl_ip;
assign dbg_first_pop = q_pop && q_first;

//----------------------------------------------------------------------------
// EU request outputs (combinational Moore per state)
//----------------------------------------------------------------------------
always_comb begin
    eu_req   = 1'b0;
    eu_ready = 1'b0;
    unique case (state)
        S_RSV:  eu_req = 1'b1;
        // reader reservations (measured on cold-start traces): no-disp
        // forms reserve through the EA-compute cycles; disp forms only
        // in the cycle their final displacement byte actually pops
        // the sreg store (8C) follows the READER reservation + ready
        // schedule throughout (measured); LEA reserves nothing
        S_EA1: eu_req = (is_reader || op_srst) && !op_lea &&
                        mrm_mod == 2'd0;
        S_EA2: eu_req = (is_reader || op_srst) && !op_lea;
        S_DISP8, S_DHI: eu_req = (is_reader || op_srst) && !op_lea &&
                                 q_pop;
        // moffs forms (A0-A3) reserve during their final address-byte
        // pop, exactly like the disp pops (measured: cold A2 blocks the
        // prefetch commit at the in-flight fetch's T3 edge); IN's port
        // pop reserves identically
        S_MHI: eu_req = q_pop;
        S_IN_PORT: eu_req = q_pop;
        // POP r16 / RET reserve the bus already during decode (measured:
        // cold-start POP suppresses the prefetch commit at cycle 1)
        S_DEC:  eu_req = !op_modrm && (opc[7:3] == 5'b01011 ||
                                       opc == 8'hC3 || opc == 8'h9D ||
                                       opc == 8'hF4 ||
                                       opc == 8'hEC || opc == 8'hED);
        // reservation start (measured per opcode from old-stream commits
        // inside the resolution window): EB/E8 at the final pop cycle,
        // E9 at pop+1, Jcc/E2 at pop+2
        S_JDISP: eu_req = q_pop && opc == 8'hEB;
        S_JDHI:  eu_req = q_pop && (opc == 8'hE8 || opc == 8'hC2);
        S_JWAIT: eu_req = !(op_jcc && dly == 6'd3) &&
                          !(opc == 8'hE2 &&
                            (dly == 6'd5 || wnext == S_JNT));
        // CALL: the flush cycle keeps the reservation so the push (ready
        // next cycle) wins the first slot ahead of the redirected prefetch
        S_CALLFL: eu_req = 1'b1;
        // RET holds its reservation through the stack read (measured: no
        // prefetch commit at the read's T3 edge; plain POP r16 allows it)
        S_BUSW: eu_req = op_ret;

        // reset countdown: the bus stays quiet until the reset flush
        S_RESET: eu_req = 1'b1;
        S_REQ, S_WREQ,
        S_A4_SRC, S_A4_DST, S_A4_WR,
        S_CALLPUSH,
        S_STRW, S_STRR, S_STRS,
        S_TRAP_IVT1, S_TRAP_IVT2,
        S_TRAP_PSW, S_TRAP_PS, S_TRAP_FLUSH, S_TRAP_PC,
        S_INT_A1, S_INT_A2: begin
            eu_req   = 1'b1;
            eu_ready = 1'b1;
        end
        // INTA sequence holds the bus between its cycles (measured: no
        // prefetch in the inter-INTA gap); the wake-wait states hold too
        S_IRQ_D, S_INT_W0, S_INT_A1W, S_INT_G, S_INT_A2W: eu_req = 1'b1;
        // ADD4S holds the bus reservation between its accesses through
        // retire (measured: no prefetch commit inside the loop)
        S_A4_SRCW, S_A4_G1, S_A4_DSTW, S_A4_G2, S_A4_WRW, S_A4_END:
            eu_req = 1'b1;
        default: ;
    endcase
end

//----------------------------------------------------------------------------
// edge-time helper tasks
//----------------------------------------------------------------------------
task automatic retire();
    arch_ip <= pc;
    state   <= S_FIRST;
    seg_ovr_en <= 1'b0;      // prefix latches end with their instruction
    rep_en     <= 1'b0;
    shadow     <= 1'b0;      // shadowing instructions re-set it after
endtask

// latch memory-operand access parameters (EA paths); off = 16-bit offset
task automatic setup_access(input [15:0] off);
    eu_addr <= {sr[ea_seg_sel], 4'h0} + {4'h0, off};
    eu_seg  <= ea_seg_sel;
    eu_word <= is_word_t;
    eu_wr   <= is_store;
    if (op_movs8)  eu_wdata <= reg8_pair(mrm_reg);
    if (op_movs16) eu_wdata <= rf[mrm_reg];
    if (op_srst)   eu_wdata <= sr[srmap(mrm_reg[1:0])];
endtask

// string-op element step (DF = PSW bit 10)
wire [15:0] str_step = opc[0] ? (psw[10] ? 16'hFFFE : 16'd2)
                              : (psw[10] ? 16'hFFFF : 16'd1);

// MOVBK's write takes its data from the BIU's read latch (forwarded at
// the commit edge - the write commits at the read's own T3 edge)
assign eu_fwd = state == S_STRW;

// stack push at SP-2 (also decrements SP)
task automatic issue_push(input [15:0] wdata);
    eu_addr  <= {sr[SEG_SS], 4'h0} + {4'h0, rf[4] - 16'd2};
    eu_seg   <= SEG_SS;
    eu_wr    <= 1'b1;
    eu_word  <= 1'b1;
    eu_wdata <= wdata;
    rf[4]    <= rf[4] - 16'd2;
endtask

//----------------------------------------------------------------------------
// main FSM
//----------------------------------------------------------------------------
always_ff @(posedge clk) begin
    flush_now <= 1'b0;
    if (rslot != 6'd0) rslot <= rslot - 6'd1;

    // pin pipelines + NMI edge latch (run in every state)
    int_p   <= {int_p[2:0], pin_int};
    nmi_p   <= {nmi_p[3:0], pin_nmi};
    if (nmi_p[2] && !nmi_p[3]) nmi_latch <= 1'b1;   // set at edge+3
    poll_s1 <= pin_poll_n;
    ie_p    <= {ie_p[1:0], psw[9]};

    if (srst) begin
        // real reset flow: PS=FFFF, PC=0, PSW cleared; the sequencer
        // idles 7 cycles after release, then flush-redirects to FFFF0
        state    <= S_RESET;
        dly      <= 6'd7;
        wnext    <= S_HALT;
        opc      <= '0;
        opc2     <= '0;
        mrm      <= '0;
        immb     <= '0;
        disp     <= '0;
        a4_cnt   <= '0;
        a4_k     <= '0;
        a4_src   <= '0;
        a4_carry <= 1'b0;
        a4_z     <= 1'b0;
        mem_op   <= '0;
        ivt_off  <= '0;
        ivt_seg  <= '0;
        trap_psw <= '0;
        fl_cs    <= 16'hFFFF;
        fl_ip    <= '0;
        seg_ovr_en <= 1'b0;
        seg_ovr  <= 2'd0;
        rep_en   <= 1'b0;
        str_wr   <= 1'b0;
        rslot    <= 6'd0;
        str_done <= 1'b0;
        int_p    <= '0;
        nmi_p    <= '0;
        nmi_latch <= 1'b0;
        poll_s1  <= 1'b1;
        shadow   <= 1'b0;
        ie_p     <= '0;
        ie_pend  <= 1'b0;
        ie_val   <= 1'b0;
        psw_old  <= '0;
        pop_pend <= 1'b0;
        insn_ip  <= '0;
        ivt_vec  <= '0;
        hwake_ie0 <= 1'b0;
        irq_disp <= 1'b0;
        eu_kind  <= K_MEM;
        halt_disp <= 1'b0;
        eu_wr    <= 1'b0;
        eu_word  <= 1'b0;
        eu_addr  <= '0;
        eu_seg   <= SEG_DS;
        eu_wdata <= '0;
        for (int i = 0; i < 8; i++) rf[i] <= '0;
        sr[SEG_ES] <= '0;
        sr[SEG_CS] <= 16'hFFFF;
        sr[SEG_SS] <= '0;
        sr[SEG_DS] <= '0;
        pc      <= '0;
        arch_ip <= '0;
        psw     <= 16'hF002;
        if (bkd_load) begin
            for (int i = 0; i < 8; i++) rf[i] <= bkd_regs[i*16 +: 16];
            sr[SEG_ES] <= bkd_regs[128 +: 16];
            sr[SEG_CS] <= bkd_regs[144 +: 16];
            sr[SEG_SS] <= bkd_regs[160 +: 16];
            sr[SEG_DS] <= bkd_regs[176 +: 16];
            pc         <= bkd_regs[192 +: 16];
            arch_ip    <= bkd_regs[192 +: 16];
            psw        <= (bkd_regs[208 +: 16] & 16'h0FD5) | 16'hF002;
            state      <= S_FIRST;
        end
    end else begin
        // POP PSW consumes the popped image at the read's own data
        // edge (measured: the new IE shows in the PS bits during T4).
        // The commit is provisional until the next boundary (pop_pend).
        if (state == S_BUSW && opc == 8'h9D && eu_rd_now) begin
            psw_old  <= psw;
            psw      <= (eu_rdata_now & 16'h0FD5) | 16'hF002;
            pop_pend <= 1'b1;
        end

        // deferred EI/DI IE write lands when the queue holds a byte
        if (ie_pend && q_any) begin
            psw[9] <= ie_val;
            ie_pend <= 1'b0;
        end

        unique case (state)
            S_HALT: ;

            //----------------------------------------------------------------
            S_FIRST: begin
                if (irq_take) begin
                    // boundary recognition (interrupt_model.md): the
                    // next instruction is not executed; its address is
                    // the pushed PC (pc already points at it)
                    if (nmi_latch) begin
                        nmi_latch <= 1'b0;
                        ivt_vec   <= 8'd2;
                        dly <= 6'd6; wnext <= S_TRAP_IVT1;
                        irq_disp <= 1'b1;
                        state <= S_WAITX;
                    end else begin
                        state <= S_IRQ_D;   // one internal decision cycle
                    end
                end else if (q_pop) begin
                    opc <= q_byte;
                    if (!rep_en && !seg_ovr_en) insn_ip <= pc;
                    pc  <= pc + 16'd1;
                    rslot <= 6'd12;    // REP retire-slot anchor (pop+12)
                    ivt_vec  <= '0;    // divide trap uses vector 0
                    irq_disp <= 1'b0;
                    eu_kind  <= K_MEM;
                    halt_disp <= (q_byte == 8'hF4);
                    pop_pend <= 1'b0;
                    // EI/DI commit IE when the NEXT opcode byte is
                    // present: at the pop edge if a byte remains, else
                    // when the queue refills (measured on dry-queue EI)
                    if (q_byte == 8'hFB || q_byte == 8'hFA) begin
                        if (q_avail2) psw[9] <= q_byte[0];
                        else begin
                            ie_pend <= 1'b1;
                            ie_val  <= q_byte[0];
                        end
                    end
                    state <= S_DEC;
                end
            end

            //----------------------------------------------------------------
            S_DEC: begin
                if (op_modrm) begin
                    if (q_pop) begin
                        mrm <= q_byte;
                        pc  <= pc + 16'd1;
                        if (q_byte[7:6] == 2'd3) begin
                            // register form
                            if (op_srst || op_srld) begin
                                // sreg MOV reg forms retire in 2 cycles
                                // (faster than reg,reg MOV - measured)
                                logic [1:0] sx;
                                sx = srmap(q_byte[4:3]);
                                if (op_srst)
                                    rf[q_byte[2:0]] <= sr[sx];
                                else begin
                                    sr[sx] <= rf[q_byte[2:0]];
                                    shadow <= 1'b1;   // sreg-load shadow
                                end
                                arch_ip <= pc + 16'd1;
                                seg_ovr_en <= 1'b0;
                                rep_en     <= 1'b0;
                                state <= S_FIRST;
                            end else if (op_alu | op_movs8 | op_movs16 |
                                op_movl8 | op_movl16 |
                                op_xchg8 | op_xchg16)
                                state <= S_EX;
                            else if (op_grpfe && q_byte[5:3] == 3'd0) begin
                                dly <= 6'd1;  wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpd0 && q_byte[5:3] == 3'd4) begin
                                dly <= 6'd3;  wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpf6 && q_byte[5:3] == 3'd4) begin
                                dly <= 6'd21; wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpf7 && q_byte[5:3] == 3'd6) begin
                                logic [32:0] dv;
                                dv = divu32({rf[2], rf[0]}, rf[q_byte[2:0]]);
                                {mem_op, disp} <= dv[31:0];  // q, r temp
                                psw <= psw_sub16(rf[2], rf[q_byte[2:0]], psw);
                                if (dv[32]) begin
                                    dly <= 6'd12; wnext <= S_TRAP_IVT1;
                                end else begin
                                    dly <= 6'd25; wnext <= S_EX;
                                end
                                state <= S_WAITX;
                            end else if (op_grpf7 && q_byte[5:3] == 3'd7) begin
                                // IDIV16 reg (mission I timing law):
                                // early trap IVT ready @ +21, late trap
                                // and EX @ +44; +3 if dividend < 0
                                logic [49:0] dv;
                                logic [5:0] sfix;
                                dv = idiv32({rf[2], rf[0]},
                                            rf[q_byte[2:0]], psw);
                                sfix = rf[2][15] ? 6'd3 : 6'd0;
                                {mem_op, disp} <= dv[31:0];  // q, r temp
                                psw <= dv[47:32];
                                if (dv[49]) begin            // early trap
                                    dly <= 6'd21 + sfix;
                                    wnext <= S_TRAP_IVT1;
                                end else if (dv[48]) begin   // late trap
                                    dly <= 6'd44 + sfix;
                                    wnext <= S_TRAP_IVT1;
                                end else begin
                                    dly <= 6'd44 + sfix;
                                    wnext <= S_EX;
                                end
                                state <= S_WAITX;
                            end else if (op_grpf6 && q_byte[5:3] == 3'd7) begin
                                // IDIV8 reg: early @ +21, late @ +36,
                                // EX @ +37; +3 if dividend < 0
                                logic [33:0] dv8;
                                logic [5:0] sfix;
                                dv8 = idiv16(rf[0], reg8_get(q_byte[2:0]),
                                             psw);
                                sfix = rf[0][15] ? 6'd3 : 6'd0;
                                mem_op <= {dv8[7:0], dv8[15:8]}; // {AH=r,AL=q}
                                psw <= dv8[31:16];
                                if (dv8[33]) begin           // early trap
                                    dly <= 6'd21 + sfix;
                                    wnext <= S_TRAP_IVT1;
                                end else if (dv8[32]) begin  // late trap
                                    dly <= 6'd36 + sfix;
                                    wnext <= S_TRAP_IVT1;
                                end else begin
                                    dly <= 6'd37 + sfix;
                                    wnext <= S_EX;
                                end
                                state <= S_WAITX;
                            end else
                                state <= S_HALT;
                        end else begin
                            // memory form; group ops with an unimplemented
                            // /reg field park the sequencer
                            if ((op_grpf6 && q_byte[5:3] != 3'd4 &&
                                 q_byte[5:3] != 3'd7) ||
                                (op_grpf7 && q_byte[5:3] != 3'd6 &&
                                 q_byte[5:3] != 3'd7) ||
                                (op_grpd0 && q_byte[5:3] != 3'd4) ||
                                (op_grpfe && q_byte[5:3] != 3'd0))
                                state <= S_HALT;
                            else if ((q_byte[7:6] == 2'd0 &&
                                      q_byte[2:0] == 3'd6) ||
                                     q_byte[7:6] == 2'd2)
                                state <= S_DLO;
                            else
                                state <= S_EA1;   // mod0 reg-EA / mod1
                        end
                    end
                end else begin
                    // no modrm
                    if (op_0f) state <= S_0F;       // 2nd byte pops at F+2
                    else if (opc[7:3] == 5'b10111) state <= S_IMM_LO; // B8-BF
                    else if (opc[7:3] == 5'b01000) begin            // INC r16
                        {psw, rf[opc[2:0]]} <=
                            incdec16(1'b0, rf[opc[2:0]], psw);
                        retire();
                    end else if (opc[7:3] == 5'b01001) begin        // DEC r16
                        {psw, rf[opc[2:0]]} <=
                            incdec16(1'b1, rf[opc[2:0]], psw);
                        retire();
                    end else if (opc == 8'h90) state <= S_NOP;
                    else if (opc[7:3] == 5'b01010) state <= S_PUSH_CALC;
                    else if (opc[7:3] == 5'b01011 ||
                             opc == 8'hC3) begin      // POP r16 / RET
                        eu_addr <= {sr[SEG_SS], 4'h0} + {4'h0, rf[4]};
                        eu_seg  <= SEG_SS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        state   <= S_REQ;
                    end else if (opc == 8'hEB || op_jcc || opc == 8'hE2)
                        state <= S_JDISP;
                    else if (opc == 8'hE9 || opc == 8'hE8 ||
                             opc == 8'hC2 || opc == 8'hEA)
                        state <= S_JDLO;
                    else if (op_moff || op_moffw) state <= S_MLO;
                    else if (op_segp) begin
                        // segment override: retires as its own
                        // instruction (2 cycles, own F pop); the latch
                        // lives until the prefixed instruction retires
                        seg_ovr_en <= 1'b1;
                        seg_ovr    <= srmap(opc[4:3]);
                        arch_ip    <= pc;
                        state      <= S_FIRST;
                    end else if (op_repp) begin
                        rep_en  <= 1'b1;
                        arch_ip <= pc;
                        state   <= S_FIRST;
                    end else if (opc == 8'h98) begin      // CVTBW
                        rf[0][15:8] <= {8{rf[0][7]}};
                        retire();
                    end else if (opc == 8'h99) begin      // CVTWL
                        dly <= 6'd2; wnext <= S_EX; state <= S_WAITX;
                    end else if (op_xlat) begin           // TRANS
                        eu_addr <= {sr[seg_ovr_en ? seg_ovr : SEG_DS],
                                    4'h0} +
                                   {4'h0, rf[3] + {8'd0, rf[0][7:0]}};
                        eu_seg  <= seg_ovr_en ? seg_ovr : SEG_DS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b0;
                        dly <= 6'd1; state <= S_RSV;
                    end else if (op_str) begin
                        if (rep_en && rf[1] == 16'd0) begin
                            // REP with CW=0: uniform early-out
                            dly <= 6'd9; wnext <= S_EX; state <= S_WAITX;
                        end else if (op_stostr) begin
                            eu_addr <= {sr[SEG_ES], 4'h0} + {4'h0, rf[7]};
                            eu_seg  <= SEG_ES;
                            eu_wr   <= 1'b1;
                            eu_word <= opc[0];
                            eu_wdata <= rf[0];
                            // REP setup: first access 2 cycles later
                            // than the single form, and the extra wait
                            // does NOT reserve the bus (measured: a
                            // prefetch commits inside it)
                            if (rep_en) begin
                                dly <= 6'd2; wnext <= S_RSV;
                                state <= S_WAITX;
                            end else begin
                                dly <= 6'd1; state <= S_RSV;
                            end
                        end else begin                    // MOVBK / LDM
                            eu_addr <= {sr[seg_ovr_en ? seg_ovr : SEG_DS],
                                        4'h0} + {4'h0, rf[6]};
                            eu_seg  <= seg_ovr_en ? seg_ovr : SEG_DS;
                            eu_wr   <= 1'b0;
                            eu_word <= opc[0];
                            str_wr  <= 1'b0;
                            if (rep_en) begin  // REP setup (see STM note)
                                dly <= 6'd2; wnext <= S_RSV;
                                state <= S_WAITX;
                            end else begin
                                dly <= 6'd1; state <= S_RSV;
                            end
                        end
                    end
                    else if (opc == 8'hF4) begin          // HALT
                        state   <= S_HALTED;   // BIU displays the
                                               // pseudo-cycle (halt_disp)
                    end else if (opc == 8'h9B) begin      // POLL
                        // initial check: synchronized pin; the wait
                        // loop samples LIVE (measured: a release in the
                        // sample cycle itself is caught)
                        if (!poll_s1) state <= S_NOP;     // low: 3-cyc nop
                        else begin
                            dly <= 6'd3;                  // 1st sample @F+4
                            state <= S_POLL_WAIT;
                        end
                    end else if (opc == 8'hFB ||
                                 opc == 8'hFA) begin      // EI / DI
                        retire();     // IE was written at the pop edge
                    end else if (opc == 8'h9D) begin      // POP PSW
                        eu_addr <= {sr[SEG_SS], 4'h0} + {4'h0, rf[4]};
                        eu_seg  <= SEG_SS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        state   <= S_REQ;
                    end else if (op_in) begin             // IN
                        if (opc[3]) begin                 // EC/ED: port=DW
                            eu_addr <= {4'h0, rf[2]};
                            eu_seg  <= SEG_CS;
                            eu_wr   <= 1'b0;
                            eu_word <= opc[0];
                            eu_kind <= K_IO;
                            state   <= S_REQ;
                        end else
                            state <= S_IN_PORT;           // imm8 pops @F+2
                    end
                    else state <= S_HALT;
                end
            end

            //----------------------------------------------------------------
            S_IMM_LO: if (q_pop) begin
                disp[7:0] <= q_byte;
                pc <= pc + 16'd1;
                state <= S_IMM_HI;
            end
            S_IMM_HI: if (q_pop) begin
                rf[opc[2:0]] <= {q_byte, disp[7:0]};
                pc <= pc + 16'd1;
                arch_ip <= pc + 16'd1;   // retire on the same edge as the pop
                state <= S_FIRST;
            end

            S_NOP: retire();

            //----------------------------------------------------------------
            // control flow (mission E; offsets from the golden tranches):
            //   EB:  disp8 pop P -> flush @ P+3
            //   E9:  disp16 hi pop H -> flush @ H+3
            //   Jcc: taken flush @ P+4; not-taken retire end of P+1
            //   E2:  taken flush @ P+6; not-taken retire end of P+2
            //   E8:  push ready @ H+4, flush during the push status cycle
            //   C3/C2: SP read; flush @ done+1 (C2: imm16 pops first,
            //          read ready @ H+1)
            //----------------------------------------------------------------
            S_JDISP: if (q_pop) begin
                pc   <= pc + 16'd1;
                disp <= pc + 16'd1 + {{8{q_byte[7]}}, q_byte};  // target
                if (opc == 8'hEB) begin
                    dly <= 6'd2; wnext <= S_JFLUSH; state <= S_JWAIT;
                end else if (opc == 8'hE2) begin                // DBNZ
                    rf[1] <= rf[1] - 16'd1;
                    if (rf[1] != 16'd1) begin
                        dly <= 6'd5; wnext <= S_JFLUSH; state <= S_JWAIT;
                    end else begin
                        dly <= 6'd1; wnext <= S_JNT; state <= S_JWAIT;
                    end
                end else begin                                  // Jcc
                    if (jcc_taken) begin
                        dly <= 6'd3; wnext <= S_JFLUSH; state <= S_JWAIT;
                    end else state <= S_JNT;
                end
            end
            S_JDLO: if (q_pop) begin
                disp[7:0] <= q_byte;
                pc <= pc + 16'd1;
                state <= S_JDHI;
            end
            S_JDHI: if (q_pop) begin
                pc <= pc + 16'd1;
                if (opc == 8'hEA) begin           // BR far: seg follows
                    disp[15:8] <= q_byte;         // absolute target offset
                    state <= S_JSLO;
                end else if (opc == 8'hC2) begin
                    disp[15:8] <= q_byte;                       // pop count
                    eu_addr <= {sr[SEG_SS], 4'h0} + {4'h0, rf[4]};
                    eu_seg  <= SEG_SS;
                    eu_wr   <= 1'b0;
                    eu_word <= 1'b1;
                    state   <= S_REQ;                           // rdy @ H+1
                end else begin
                    disp <= pc + 16'd1 + {q_byte, disp[7:0]};   // target
                    if (opc == 8'hE9) begin
                        dly <= 6'd2; wnext <= S_JFLUSH; state <= S_JWAIT;
                    end else begin                 // E8: flush @ H+3 like E9,
                        dly <= 6'd2; wnext <= S_CALLFL; state <= S_JWAIT;
                    end                            // push ready @ H+4
                end
            end
            // branch-resolution wait (holds a bus reservation)
            S_JWAIT: begin
                if (dly == 6'd1) begin
                    state <= wnext;
                    // near transfers redirect within CS; EA (far) has
                    // already latched its target in S_JSHI
                    if ((wnext == S_JFLUSH || wnext == S_CALLFL) &&
                        opc != 8'hEA) begin
                        fl_cs <= sr[SEG_CS];
                        fl_ip <= disp;
                    end
                end
                dly <= dly - 6'd1;
            end
            S_JNT: retire();                                    // not taken
            // BR far (EA) segment bytes; flush at seghi-pop+2 (measured
            // on the boot capture; reservation from pop+1 via S_JWAIT)
            S_JSLO: if (q_pop) begin
                immb <= q_byte;
                pc   <= pc + 16'd1;
                state <= S_JSHI;
            end
            S_JSHI: if (q_pop) begin
                pc    <= pc + 16'd1;
                fl_cs <= {q_byte, immb};
                fl_ip <= disp;
                dly   <= 6'd1; wnext <= S_JFLUSH; state <= S_JWAIT;
            end
            // MOV AL/AW, moffs16 (A0/A1): direct address pops at F+2/F+3,
            // read ready hi+1, retire at done (boot capture)
            S_MLO: if (q_pop) begin
                disp[7:0] <= q_byte;
                pc <= pc + 16'd1;
                state <= S_MHI;
            end
            S_MHI: if (q_pop) begin
                pc <= pc + 16'd1;
                eu_addr <= {sr[seg_ovr_en ? seg_ovr : SEG_DS], 4'h0} +
                           {4'h0, {q_byte, disp[7:0]}};
                eu_seg  <= seg_ovr_en ? seg_ovr : SEG_DS;
                eu_wr   <= op_moffw;
                eu_word <= opc[0];
                if (op_moffw) eu_wdata <= rf[0];
                state   <= S_REQ;
            end
            // reset flow: 7 idle cycles after RESET release, then the
            // standard flush machinery redirects to FFFF:0000 (measured:
            // QS=E at release+7, first fetch T1 at release+9)
            S_RESET: begin
                if (dly == 6'd1) state <= S_JFLUSH;
                dly <= dly - 6'd1;
            end
            S_JFLUSH: begin      // q_flush high this cycle (comb)
                pc      <= fl_ip;
                arch_ip <= fl_ip;
                sr[SEG_CS] <= fl_cs;   // no-op for near flushes
                state   <= S_FIRST;
            end
            S_CALLFL: begin      // q_flush high this cycle (comb)
                issue_push(pc);  // return address = fall-through
                pc    <= fl_ip;
                state <= S_CALLPUSH;
            end
            S_CALLPUSH: if (eu_started) state <= S_CALLW;
            S_CALLW: if (eu_done) begin
                arch_ip <= pc;
                state <= S_FIRST;
            end
            S_RETF: begin        // q_flush high this cycle (comb)
                pc      <= fl_ip;
                arch_ip <= fl_ip;
                state   <= S_FIRST;
            end

            //----------------------------------------------------------------
            // 0F-prefixed forms: second byte pops at F+2, modrm at F+3
            //----------------------------------------------------------------
            S_0F: if (q_pop) begin
                opc2 <= q_byte;
                pc   <= pc + 16'd1;
                if (q_byte == 8'h18 || q_byte == 8'h28)
                    state <= S_DEC2;
                else if (q_byte == 8'h20) begin        // ADD4S
                    a4_cnt  <= 8'(({1'b0, rf[1][7:0]} + 9'd1) >> 1);
                    a4_k    <= 8'd0;
                    a4_carry <= 1'b0;
                    a4_z    <= 1'b1;
                    dly     <= 6'd4;                   // src ready @ pop+5
                    state   <= S_A4_SETUP;
                end else
                    state <= S_HALT;
            end
            S_DEC2: if (q_pop) begin
                mrm <= q_byte;
                pc  <= pc + 16'd1;
                if (q_byte[7:6] == 2'd3) begin
                    if (op_test1) state <= S_IMM3;     // imm pops at F+4
                    else begin                         // ROL4 reg: EX @ F+15
                        dly <= 6'd11; wnext <= S_EX; state <= S_WAITX;
                    end
                end else if ((q_byte[7:6] == 2'd0 && q_byte[2:0] == 3'd6) ||
                             q_byte[7:6] == 2'd2)
                    state <= S_DLO;
                else
                    state <= S_EA1;
            end
            S_T1GAP: state <= S_IMM3;                  // mem TEST1: done+2 pop
            S_IMM3: if (q_pop) begin
                immb <= q_byte;
                pc   <= pc + 16'd1;
                state <= S_EX;
            end

            //----------------------------------------------------------------
            // ADD4S: per-byte loop src(DS0:IX+k) rd, dst(DS1:IY+k) rd, wr.
            // Ready offsets measured: src @ pop2+5 / wrdone+1, dst @
            // srcdone+2, write @ dstdone+4, retire @ last wrdone+4.
            //----------------------------------------------------------------
            S_A4_SETUP: begin
                if (dly == 6'd1) begin
                    eu_addr <= {sr[SEG_DS], 4'h0} + {4'h0, rf[6]};
                    eu_seg  <= SEG_DS;
                    eu_wr   <= 1'b0;
                    eu_word <= 1'b0;
                    state   <= (a4_cnt == 8'd0) ? S_HALT : S_A4_SRC;
                end
                dly <= dly - 6'd1;
            end
            S_A4_SRC: if (eu_started) state <= S_A4_SRCW;
            S_A4_SRCW: if (eu_done) begin
                a4_src  <= eu_rdata;
                eu_addr <= {sr[SEG_ES], 4'h0} + {4'h0, rf[7] + {8'd0, a4_k}};
                eu_seg  <= SEG_ES;
                state   <= S_A4_G1;
            end
            S_A4_G1: state <= S_A4_DST;
            S_A4_DST: if (eu_started) state <= S_A4_DSTW;
            S_A4_DSTW: if (eu_done) begin
                // {fire, sibx, prez, res}; driven sibling lane =
                // src_other + dst_other + fire + sibx - 1 (measured law)
                logic [10:0] s;
                s = bcd_add8(eu_rdata[7:0], a4_src[7:0], a4_carry);
                a4_carry <= s[10];
                a4_z     <= a4_z && s[8];
                mem_op   <= {a4_src[15:8] + eu_rdata[15:8] +
                             {7'd0, s[10]} + {7'd0, s[9]} - 8'd1, s[7:0]};
                dly      <= 6'd3;
                state    <= S_A4_G2;
            end
            S_A4_G2: begin
                if (dly == 6'd1) begin
                    eu_wr    <= 1'b1;
                    eu_wdata <= mem_op;
                    state    <= S_A4_WR;
                end
                dly <= dly - 6'd1;
            end
            S_A4_WR: if (eu_started) state <= S_A4_WRW;
            S_A4_WRW: if (eu_done) begin
                if (a4_cnt > 8'd1) begin
                    a4_cnt  <= a4_cnt - 8'd1;
                    a4_k    <= a4_k + 8'd1;
                    eu_addr <= {sr[SEG_DS], 4'h0} +
                               {4'h0, rf[6] + {8'd0, a4_k} + 16'd1};
                    eu_seg  <= SEG_DS;
                    eu_wr   <= 1'b0;
                    state   <= S_A4_SRC;
                end else begin
                    // retire at wrdone+4 with final carry, +5 without
                    // (measured: the no-carry path costs one extra cycle)
                    dly   <= a4_carry ? 6'd4 : 6'd5;
                    state <= S_A4_END;
                end
            end
            S_A4_END: begin
                if (dly == 6'd1) begin
                    // undefined-flag law: S=AC=CY(out), P=Z(out), V=0
                    psw[FB_CY] <= a4_carry;
                    psw[FB_S]  <= a4_carry;
                    psw[FB_AC] <= a4_carry;
                    psw[FB_Z]  <= a4_z;
                    psw[FB_P]  <= a4_z;
                    psw[FB_V]  <= 1'b0;
                    retire();
                end
                dly <= dly - 6'd1;
            end

            //----------------------------------------------------------------
            // effective-address path
            //----------------------------------------------------------------
            S_EA1: begin
                if (op_lea && mrm_mod == 2'd0) begin
                    // LDEA mod0: one EA cycle, retire at cycle 2, no
                    // bus access or reservation (measured: F@3)
                    rf[mrm_reg] <= ea_base;
                    retire();
                end else
                    state <= (mrm_mod == 2'd1) ? S_DISP8 : S_EA2;
            end
            S_EA2: begin                                  // mod0, reg EA
                setup_access(ea_base);
                state <= S_REQ;                           // ready @ 4
            end
            // displacement pops retry on a 2-cycle grain when the queue
            // runs dry (measured on cold-start traces; modrm/imm/F pops
            // poll every cycle instead)
            S_DISP8: if (q_pop) begin                     // mod1 disp pop @ 3
                disp <= {{8{q_byte[7]}}, q_byte};
                pc <= pc + 16'd1;
                if (op_lea) begin
                    rf[mrm_reg] <= ea_base + {{8{q_byte[7]}}, q_byte};
                    arch_ip <= pc + 16'd1;
                    seg_ovr_en <= 1'b0;
                    rep_en     <= 1'b0;
                    state <= S_FIRST;
                end else begin
                    setup_access(ea_base + {{8{q_byte[7]}}, q_byte});
                    // the sreg store (8C) follows the READER ready
                    // schedule (d0/d1 @ 4, d2 @ 5 - measured)
                    if (is_store && !op_srst) begin       // d1 store: rdy @ 5
                        dly <= 6'd1; state <= S_RSV;
                    end else state <= S_REQ;              // d1 load: rdy @ 4
                end
            end else begin
                dret <= S_DISP8; state <= S_DSTALL;
            end
            S_DLO: if (q_pop) begin                       // disp16 low @ 2
                disp[7:0] <= q_byte;
                pc <= pc + 16'd1;
                state <= S_DGAP;
            end else begin
                dret <= S_DLO; state <= S_DSTALL;
            end
            S_DGAP: state <= S_DHI;
            S_DHI: if (q_pop) begin                       // disp16 high @ 4
                disp[15:8] <= q_byte;
                pc <= pc + 16'd1;
                if (op_lea) begin
                    rf[mrm_reg] <= ea_base + {q_byte, disp[7:0]};
                    arch_ip <= pc + 16'd1;
                    seg_ovr_en <= 1'b0;
                    rep_en     <= 1'b0;
                    state <= S_FIRST;
                end else begin
                    setup_access(ea_base + {q_byte, disp[7:0]});
                    // d2 loads and the sreg store (uniform @5): rdy @ 5;
                    // other d2 stores: rdy @ 7
                    if (is_reader || op_srst) state <= S_REQ;
                    else begin dly <= 6'd2; state <= S_RSV; end
                end
            end else begin
                dret <= S_DHI; state <= S_DSTALL;
            end
            S_DSTALL: state <= dret;

            //----------------------------------------------------------------
            // bus access issue / wait
            //----------------------------------------------------------------
            S_RSV: begin
                if (dly == 6'd1) state <= S_REQ;
                dly <= dly - 6'd1;
            end
            //----------------------------------------------------------------
            // string micro-loop (mission J): the MOVBK write is requested
            // WHILE its read is in flight and commits at the read's T3
            // edge (data forwarded inside the BIU, eu_fwd); REP chains
            // the next element's access the same way - reads and writes
            // run back to back (slopes 8/4, measured).
            //----------------------------------------------------------------
            S_REQ: if (eu_started) begin
                if (op_movstr) begin           // read accepted: queue write
                    eu_addr <= {sr[SEG_ES], 4'h0} + {4'h0, rf[7]};
                    eu_seg  <= SEG_ES;
                    eu_wr   <= 1'b1;
                    state   <= S_STRW;
                end else if (op_stostr) begin  // write accepted
                    rf[7] <= rf[7] + str_step;
                    if (rep_en) begin
                        rf[1] <= rf[1] - 16'd1;
                        if (rf[1] != 16'd1 && irq_rep) begin
                            // interrupted between iterations: finish the
                            // in-flight write, rewind to the first
                            // prefix, refetch, then vector at
                            // decision+9 (fitted; see interrupt_model)
                            state <= S_IRQ_REPW;
                            dly   <= 6'd8;
                        end else if (rf[1] != 16'd1) begin
                            eu_addr <= {sr[SEG_ES], 4'h0} +
                                       {4'h0, rf[7] + str_step};
                            state <= S_STRS;
                        end else begin
                            // REP cx=1: retire at the pop+12 slot or
                            // the write's completion, whichever later
                            str_done <= 1'b0;
                            state <= S_STRE;
                        end
                    end else state <= S_BUSW;
                end else state <= S_BUSW;
            end
            // REP cx=1 slot-bound retire (measured: the closing F sits
            // at pop+13 regardless of when the single write completes)
            S_STRE: begin
                if (eu_done) str_done <= 1'b1;
                if (rslot <= 6'd1 && (str_done || eu_done)) retire();
            end
            S_STRW: if (eu_started) begin      // MOVBK write accepted
                rf[6] <= rf[6] + str_step;
                rf[7] <= rf[7] + str_step;
                if (rep_en) begin
                    rf[1] <= rf[1] - 16'd1;
                    if (rf[1] != 16'd1) begin
                        eu_addr <= {sr[seg_ovr_en ? seg_ovr : SEG_DS],
                                    4'h0} + {4'h0, rf[6] + str_step};
                        eu_seg  <= seg_ovr_en ? seg_ovr : SEG_DS;
                        eu_wr   <= 1'b0;
                        state <= S_STRR;
                    end else state <= S_BUSW;
                end else state <= S_BUSW;
            end
            S_STRR: if (eu_started) begin      // next read accepted
                eu_addr <= {sr[SEG_ES], 4'h0} + {4'h0, rf[7]};
                eu_seg  <= SEG_ES;
                eu_wr   <= 1'b1;
                state   <= S_STRW;
            end
            S_STRS: if (eu_started) begin      // next STM write accepted
                rf[7] <= rf[7] + str_step;
                if (rep_en) begin
                    rf[1] <= rf[1] - 16'd1;
                    if (rf[1] != 16'd1 && irq_rep) begin
                        state <= S_IRQ_REPW;
                        dly   <= 6'd8;
                    end else if (rf[1] != 16'd1) begin
                        eu_addr <= {sr[SEG_ES], 4'h0} +
                                   {4'h0, rf[7] + str_step};
                        state <= S_STRS;
                    end else state <= S_BUSW;
                end else state <= S_BUSW;
            end
            S_BUSW: if (eu_done) begin
                if (op_moff) begin                        // A0 / A1
                    if (opc[0]) rf[0] <= eu_rdata;
                    else        rf[0][7:0] <= eu_rdata[7:0];
                    retire();
                end else if (op_moffw) begin              // A2 / A3
                    retire();
                end else if (op_xlat) begin               // TRANS
                    rf[0][7:0] <= eu_rdata[7:0];
                    retire();
                end else if (op_lodstr) begin             // LDM
                    if (opc[0]) rf[0] <= eu_rdata;
                    else        rf[0][7:0] <= eu_rdata[7:0];
                    rf[6] <= rf[6] + str_step;
                    retire();
                end else if (op_stostr || op_movstr) begin // STM / MOVBK end
                    // REP (cx>=2) termination: one extra cycle after the
                    // last write's done (measured); singles retire at done
                    if (rep_en) state <= S_EX;
                    else retire();
                end else if (op_ret) begin                // C3 / C2
                    rf[4] <= rf[4] + 16'd2 +
                             ((opc == 8'hC2) ? disp : 16'd0);
                    fl_cs <= sr[SEG_CS];
                    fl_ip <= eu_rdata;
                    state <= S_RETF;                      // flush @ done+1
                end else if (opc == 8'h9D) begin          // POP PSW
                    rf[4] <= rf[4] + 16'd2;
                    retire();     // psw was consumed at the data edge
                end else if (op_in) begin                 // IN acc
                    if (opc[0]) rf[0] <= eu_rdata;
                    else        rf[0][7:0] <= eu_rdata[7:0];
                    eu_kind <= K_MEM;
                    retire();
                end else if (opc[7:3] == 5'b01011) begin  // POP r16
                    rf[4] <= rf[4] + 16'd2;
                    rf[opc[2:0]] <= eu_rdata;             // POP SP: load wins
                    retire();
                end else if (opc[7:3] == 5'b01010) begin  // PUSH r16
                    retire();
                end else if (is_store) begin              // MOV 88/89 store
                    retire();
                end else begin
                    mem_op <= eu_rdata;
                    if (op_srld)
                        state <= S_LD_W2;   // sreg load: writeback done+1
                    else if (is_load || (op_alu && opc[5:3] == 3'd7))
                        state <= S_LD_W1;                 // MOV load / CMP
                    else if (op_test1)
                        state <= S_T1GAP;                 // imm pop done+2
                    else if (op_rol4) begin
                        dly <= 6'd10; state <= S_RMWX;    // wr ready done+11
                    end else if (op_alu || op_xchg8 || op_xchg16) begin
                        dly <= 6'd2; state <= S_RMWX;     // wr ready done+3
                    end else if (op_grpfe) begin
                        dly <= 6'd3; state <= S_RMWX;     // done+4
                    end else if (op_grpd0) begin
                        dly <= 6'd5; state <= S_RMWX;     // done+6
                    end else if (op_grpf6 && mrm_reg == 3'd7) begin
                        // IDIV8 mem: reg-form law + 1 (like DIVU)
                        logic [33:0] dv8;
                        logic [5:0] sfix;
                        dv8 = idiv16(rf[0], eu_rdata[7:0], psw);
                        sfix = rf[0][15] ? 6'd3 : 6'd0;
                        mem_op <= {dv8[7:0], dv8[15:8]};  // {AH=r, AL=q}
                        psw <= dv8[31:16];
                        if (dv8[33]) begin
                            dly <= 6'd22 + sfix; wnext <= S_TRAP_IVT1;
                        end else if (dv8[32]) begin
                            dly <= 6'd37 + sfix; wnext <= S_TRAP_IVT1;
                        end else begin
                            dly <= 6'd38 + sfix; wnext <= S_EX;
                        end
                        state <= S_WAITX;
                    end else if (op_grpf6) begin
                        dly <= 6'd22; wnext <= S_EX; state <= S_WAITX;
                    end else if (op_grpf7 && mrm_reg == 3'd7) begin
                        // IDIV16 mem: reg-form law + 1 (like DIVU)
                        logic [49:0] dv;
                        logic [5:0] sfix;
                        dv = idiv32({rf[2], rf[0]}, eu_rdata, psw);
                        sfix = rf[2][15] ? 6'd3 : 6'd0;
                        {mem_op, disp} <= dv[31:0];
                        psw <= dv[47:32];
                        if (dv[49]) begin
                            dly <= 6'd22 + sfix; wnext <= S_TRAP_IVT1;
                        end else if (dv[48]) begin
                            dly <= 6'd45 + sfix; wnext <= S_TRAP_IVT1;
                        end else begin
                            dly <= 6'd45 + sfix; wnext <= S_EX;
                        end
                        state <= S_WAITX;
                    end else if (op_grpf7) begin
                        logic [32:0] dv;
                        dv = divu32({rf[2], rf[0]}, eu_rdata);
                        {mem_op, disp} <= dv[31:0];
                        psw <= psw_sub16(rf[2], eu_rdata, psw);
                        if (dv[32]) begin
                            dly <= 6'd13; wnext <= S_TRAP_IVT1;
                        end else begin
                            dly <= 6'd26; wnext <= S_EX;
                        end
                        state <= S_WAITX;
                    end else state <= S_HALT;
                end
            end

            S_LD_W1: state <= S_LD_W2;
            S_LD_W2: begin
                logic [1:0] sx;
                sx = srmap(mrm_reg[1:0]);
                if (op_movl8)       wr_reg8(mrm_reg, mem_op[7:0]);
                else if (op_movl16) rf[mrm_reg] <= mem_op;
                else if (op_srld)   sr[sx] <= mem_op;
                else if (op_alu)    psw <= ex_alu[23:8];  // CMP mem
                retire();
                if (op_srld) shadow <= 1'b1;   // sreg-load shadow
            end

            //----------------------------------------------------------------
            // generic wait, then execute (reg forms, MUL/DIV finish)
            //----------------------------------------------------------------
            S_WAITX: begin
                if (dly == 6'd1) begin
                    state <= wnext;
                    if (wnext == S_TRAP_IVT1) begin
                        // request params must be valid on state entry
                        eu_addr <= {10'h0, ivt_vec, 2'b00};
                        eu_seg  <= SEG_CS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        eu_kind <= K_MEM;
                    end
                    if (wnext == S_RSV) dly <= 6'd1;   // REP setup tail
                end
                if (!(dly == 6'd1 && wnext == S_RSV))
                    dly <= dly - 6'd1;
            end

            S_EX: begin
                if (opc == 8'h99) begin                // CVTWL
                    rf[2] <= {16{rf[0][15]}};
                end else if (op_str) begin
                    // REP with CW=0 early-out: no effects
                end else if (op_test1) begin
                    // t = op AND (1<<n): Z=(t==0), S=t[7], P=par(t),
                    // AC=CY=V=0 (undefined_flags.md TEST1 law)
                    logic [7:0] t;
                    t = rm_byte & (8'd1 << immb[2:0]);
                    psw[FB_Z]  <= t == 8'd0;
                    psw[FB_S]  <= t[7];
                    psw[FB_P]  <= ~^t;
                    psw[FB_AC] <= 1'b0;
                    psw[FB_CY] <= 1'b0;
                    psw[FB_V]  <= 1'b0;
                end else if (op_rol4) begin            // reg form
                    wr_reg8(mrm_rm, {rm_byte[3:0], rf[0][3:0]});
                    rf[0][7:0] <= {rf[0][3:0], rm_byte[7:4]};
                end else if (op_xchg8) begin
                    wr_reg8(mrm_rm, reg8_get(mrm_reg));
                    wr_reg8(mrm_reg, reg8_get(mrm_rm));
                end else if (op_xchg16) begin
                    rf[mrm_rm]  <= rf[mrm_reg];
                    rf[mrm_reg] <= rf[mrm_rm];
                end else if (op_alu) begin
                    psw <= ex_alu[23:8];
                    if (opc[5:3] != 3'd7) wr_reg8(mrm_rm, ex_alu[7:0]);
                end else if (op_movs8)  wr_reg8(mrm_rm, reg8_get(mrm_reg));
                else if (op_movs16) rf[mrm_rm]  <= rf[mrm_reg];
                else if (op_movl8)  wr_reg8(mrm_reg, reg8_get(mrm_rm));
                else if (op_movl16) rf[mrm_reg] <= rf[mrm_rm];
                else if (op_grpfe) begin
                    psw <= ex_inc[23:8];
                    wr_reg8(mrm_rm, ex_inc[7:0]);
                end else if (op_grpd0) begin
                    psw <= ex_shl[23:8];
                    wr_reg8(mrm_rm, ex_shl[7:0]);
                end else if (op_grpf6 && mrm_reg == 3'd7) begin
                    // IDIV8 writeback: AL=q, AH=r (flags set at dispatch)
                    rf[0] <= mem_op;
                end else if (op_grpf6) begin
                    // MULU8: AW = AL * op8; CY=V = (AH != 0);
                    // S/Z/AC/P preserved (undefined_flags.md)
                    logic [15:0] m;
                    m = {8'd0, rm_byte} * {8'd0, rf[0][7:0]};
                    rf[0] <= m;
                    psw[FB_CY] <= m[15:8] != 8'd0;
                    psw[FB_V]  <= m[15:8] != 8'd0;
                end else if (op_grpf7) begin
                    // DIVU16 (no trap): AW=quot (mem_op), DW=rem (disp);
                    // flags were set by the pre-check compare at dispatch
                    rf[0] <= mem_op;
                    rf[2] <= disp;
                end
                retire();
            end

            //----------------------------------------------------------------
            // RMW writeback (byte ops: sibling lane preserved from the read)
            //----------------------------------------------------------------
            S_RMWX: begin
                if (dly == 6'd1) begin
                    state <= S_WREQ;
                    eu_wr <= 1'b1;
                    if (op_xchg8) begin
                        eu_wdata <= src_pair;
                        wr_reg8(mrm_reg, mem_op[7:0]);
                    end else if (op_xchg16) begin
                        eu_wdata <= rf[mrm_reg];
                        rf[mrm_reg] <= mem_op;
                    end else if (op_rol4) begin
                        // driven pair = {AL_new, mem_new}: AL rides the
                        // sibling lane of the internal operand pair
                        eu_wdata <= {rf[0][3:0], mem_op[7:4],
                                     mem_op[3:0], rf[0][3:0]};
                        rf[0][7:0] <= {rf[0][3:0], mem_op[7:4]};
                    end else begin
                        eu_wdata <= rmw_wide;
                        if (op_alu)        psw <= ex_alu[23:8];
                        else if (op_grpfe) psw <= ex_inc[23:8];
                        else               psw <= ex_shl[23:8];
                    end
                end
                dly <= dly - 6'd1;
            end
            S_WREQ: if (eu_started) state <= S_WBUSW;
            S_WBUSW: if (eu_done) retire();

            //----------------------------------------------------------------
            // PUSH r16 (PUSH SP pushes the decremented value, 8086-style)
            //----------------------------------------------------------------
            S_PUSH_CALC: begin
                issue_push(rf[opc[2:0]] -
                           ((opc[2:0] == 3'd4) ? 16'd2 : 16'd0));
                state <= S_REQ;
            end

            //----------------------------------------------------------------
            // divide trap sequence (timing from F7.6 golden traces)
            //----------------------------------------------------------------
            S_TRAP_IVT1: if (eu_started) begin
                eu_addr <= eu_addr + 20'd2;   // vector high word
                state <= S_TRAP_IVT2;
            end
            S_TRAP_IVT2: begin
                if (eu_done) ivt_off <= eu_rdata;
                if (eu_started) state <= S_TRAP_IVT2W;
            end
            S_TRAP_IVT2W: if (eu_done) begin
                ivt_seg  <= eu_rdata;
                fl_cs    <= eu_rdata;
                fl_ip    <= ivt_off;
                // psw already carries the divide residue (pre-check
                // compare); latch the to-be-pushed value here, and clear
                // the live IE/TF at once - the PS status bits of the push
                // cycles already show IE=0 (measured)
                trap_psw <= psw;
                // KNOWN RESIDUAL (block 4): when the interrupt lands on
                // POP PSW's own boundary the silicon splits ~50/50
                // between keeping the popped value and reverting to the
                // pre-pop value (with IE/BRK cleared); the discriminator
                // is not timing (identical stimulus signatures show both
                // classes). Majority rule implemented: popped value kept.
                psw <= psw & ~16'h0300;
                pop_pend <= 1'b0;
                dly <= 6'd2; state <= S_TRAP_W1;
            end
            S_TRAP_W1: begin
                if (dly == 6'd1) begin
                    state <= S_TRAP_PSW;
                    issue_push(trap_psw);
                end
                dly <= dly - 6'd1;
            end
            S_TRAP_PSW: if (eu_started) begin
                state <= S_TRAP_PSWW;
                dly   <= 6'd11;      // fixed microcode slot: PS at started+12
            end
            // The trap chain issues the next push at the EARLIER of two
            // paths (measured on the F7.6 waits tranches): the
            // completion-gated path - early write-done strobe (ready
            // edge under waits, the old T4 law at zero waits) + 2 - and
            // the microcode's own fixed 12-cycle push slot from
            // eu_started. Splits + waits can stretch the bus cycle past
            // the slot; the request then waits only on BIU arbitration.
            S_TRAP_PSWW: begin
                if (eu_wdone) begin
                    dly <= 6'd1; state <= S_TRAP_W2;
                end else if (dly == 6'd1) begin
                    state <= S_TRAP_PS;
                    issue_push(sr[SEG_CS]);
                end else begin
                    dly <= dly - 6'd1;
                end
            end
            S_TRAP_W2: begin
                if (dly == 6'd1) begin
                    state <= S_TRAP_PS;
                    issue_push(sr[SEG_CS]);
                end
                dly <= dly - 6'd1;
            end
            S_TRAP_PS: if (eu_started) state <= S_TRAP_PSW2W;
            S_TRAP_PSW2W: if (eu_wdone) begin
                state <= S_TRAP_FLUSH;
                flush_now <= 1'b1;
                issue_push(pc);
                pc <= ivt_off;
                sr[SEG_CS] <= ivt_seg;
            end
            //----------------------------------------------------------------
            // REP interruption tail: wait for the in-flight access, then
            // rewind pc to the first prefix, flush + refetch there
            // (measured: the resume refetch precedes the INTA pair),
            // then the INT/NMI entry sequence.
            //----------------------------------------------------------------
            S_IRQ_REPW: begin
                dly <= dly - 6'd1;
                if (eu_done) begin
                    pc <= insn_ip;
                    fl_cs <= sr[SEG_CS];
                    fl_ip <= insn_ip;
                end
                if (dly == 6'd1) state <= S_IRQ_REPFL;
            end
            S_IRQ_REPFL: begin   // q_flush high this cycle (comb)
                if (nmi_latch) begin
                    nmi_latch <= 1'b0;
                    ivt_vec   <= 8'd2;
                    dly <= 6'd8; wnext <= S_TRAP_IVT1;
                    irq_disp <= 1'b1;
                    state <= S_WAITX;
                end else begin
                    dly <= 6'd2;
                    state <= S_INT_W0;
                end
            end

            //----------------------------------------------------------------
            // INT entry: 2 INTA bus cycles 7 apart (vector byte taken
            // from the second), then the divide-trap IVT/push/flush
            // chain (interrupt_model.md)
            //----------------------------------------------------------------
            S_IRQ_D: begin      // INT dispatch: request ready 2 cycles
                eu_addr <= '0;  // after the blocked boundary pop slot
                eu_seg  <= SEG_CS;
                eu_wr   <= 1'b0;
                eu_word <= 1'b1;
                eu_kind <= K_INTA;
                state   <= S_INT_A1;
            end
            S_INT_W0: begin
                if (dly == 6'd1) begin
                    state <= S_INT_A1;
                    eu_addr <= '0;
                    eu_seg  <= SEG_CS;
                    eu_wr   <= 1'b0;
                    eu_word <= 1'b1;
                    eu_kind <= K_INTA;
                end
                dly <= dly - 6'd1;
            end
            S_INT_A1:  if (eu_started) state <= S_INT_A1W;
            S_INT_A1W: if (eu_done) state <= S_INT_G;
            S_INT_G:   begin
                state <= S_INT_A2;    // one gap cycle: T1-to-T1 = 7
                eu_kind <= K_INTA;
            end
            S_INT_A2:  if (eu_started) state <= S_INT_A2W;
            S_INT_A2W: if (eu_done) begin
                ivt_vec <= eu_rdata[7:0];
                eu_kind <= K_MEM;
                dly <= 6'd4; wnext <= S_TRAP_IVT1;   // IVT T1 = T4+7
                irq_disp <= 1'b1;
                state <= S_WAITX;
            end

            //----------------------------------------------------------------
            // HALT: one pseudo bus cycle, then idle with the bus held.
            // Wake: NMI -> vector 2; INT with IE=1 -> INTA sequence;
            // INT with IE=0 -> resume at the next instruction WITHOUT
            // vectoring (measured, != 8086).
            //----------------------------------------------------------------
            S_HALTED: begin
                if (nmi_latch) begin
                    nmi_latch <= 1'b0;
                    ivt_vec   <= 8'd2;
                    halt_disp <= 1'b0;
                    dly <= 6'd7; wnext <= S_TRAP_IVT1;
                    state <= S_HWAIT;
                end else if (int_p[1] && psw[9]) begin
                    halt_disp <= 1'b0;
                    dly <= 6'd3; wnext <= S_INT_A1;
                    state <= S_HWAIT;
                end else if (int_p[2]) begin
                    halt_disp <= 1'b0;
                    retire();          // masked INT releases the halt
                end
            end
            S_HWAIT: begin   // wake wait (bus stays held: no prefetch)
                if (dly == 6'd1) begin
                    state <= wnext;
                    if (wnext == S_TRAP_IVT1) begin
                        eu_addr <= {10'h0, ivt_vec, 2'b00};
                        eu_seg  <= SEG_CS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        eu_kind <= K_MEM;
                        irq_disp <= 1'b1;
                    end else begin     // S_INT_A1
                        eu_addr <= '0;
                        eu_seg  <= SEG_CS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        eu_kind <= K_INTA;
                    end
                end
                dly <= dly - 6'd1;
            end

            //----------------------------------------------------------------
            // POLL: pin low = 3-cycle no-op; else sample every 5 clocks,
            // resume 4 cycles after the satisfied sample
            //----------------------------------------------------------------
            S_POLL_WAIT: begin
                if (dly == 6'd1) begin
                    if (!pin_poll_n) begin  // live sample every 5 clocks
                        dly <= 6'd3;        // next F = sample + 4
                        state <= S_POLL_X;
                    end else
                        dly <= 6'd5;   // next sample in 5 clocks
                end else
                    dly <= dly - 6'd1;
            end
            S_POLL_X: begin
                if (dly == 6'd1) retire();
                dly <= dly - 6'd1;
            end

            S_IN_PORT: if (q_pop) begin        // E4/E5 imm8 port @F+2
                pc <= pc + 16'd1;
                eu_addr <= {12'h0, q_byte};
                eu_seg  <= SEG_CS;
                eu_wr   <= 1'b0;
                eu_word <= opc[0];
                eu_kind <= K_IO;
                state   <= S_REQ;
            end

            S_TRAP_FLUSH: state <= eu_started ? S_TRAP_PCW : S_TRAP_PC;
            S_TRAP_PC:    if (eu_started) state <= S_TRAP_PCW;
            S_TRAP_PCW:   if (eu_done) begin
                arch_ip <= pc;
                state <= S_FIRST;
            end

            default: state <= S_HALT;
        endcase
    end
end

//----------------------------------------------------------------------------
// backdoor observation
//----------------------------------------------------------------------------
// The divide-trap chain holds the bus across its whole IVT-read/push
// sequence up to the flush (measured on the waits tranches: cold traps
// with a non-full queue show no prefetch in the inter-access gaps).
// This hold blocks prefetch commits but is NOT an EU request: it must
// not feed the mid-cycle-commit request history (eu_req_p1/p2) - the
// w1 traps' PS push takes the idle-end slot, not the mid-cycle one.
// The post-flush PC-push wait (S_TRAP_PCW) does not hold: the handler
// prefetch commits at that push's T3 edge.
assign eu_hold = state == S_TRAP_IVT2W || state == S_TRAP_W1 ||
                 state == S_TRAP_PSWW  || state == S_TRAP_W2 ||
                 state == S_TRAP_PSW2W ||
                 (state == S_HALTED && !(int_p[2] && !psw[9])) ||
                 (state == S_HWAIT && wnext == S_TRAP_IVT1) ||
                 (state == S_WAITX && (wnext == S_TRAP_IVT1 ||
                                       wnext == S_INT_A1) && irq_disp);

assign dbg_regs = {psw, arch_ip, sr[SEG_DS], sr[SEG_SS], sr[SEG_CS],
                   sr[SEG_ES], rf[7], rf[6], rf[5], rf[4], rf[3], rf[2],
                   rf[1], rf[0]};

endmodule
