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
//     DIVU16 trap: IVT read ready at cycle 14 (reg) / done+14 (mem);
//     IVT offset/segment words read back-to-back; PSW push ready
//     IVTdone+3; PS push ready PSWdone+2; the cycle after PSdone raises
//     the queue flush (QS=E) together with the PC push request; the
//     handler prefetch then wins the slot after the PC push by itself.
//
//  Implemented opcodes: 00/08/10/18/20/28/30/38 (ALU rm8,r8), 40-4F,
//  50-57, 58-5F, 86/87 (XCHG), 88/89/8A/8B, 90, B8-BF, D0/4, F6/4,
//  F7/6, FE/0, and the V30 0F forms 0F18 (TEST1 rm8,imm3), 0F20
//  (ADD4S), 0F28 (ROL4 rm8). Unknown opcodes park the sequencer
//  (S_HALT). 0F forms pop the second byte at F+2 and the modrm at F+3;
//  the standard EA machinery then applies unchanged.
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
    output            q_pop,
    output            q_first,
    output            q_flush,
    output     [15:0] flush_cs,
    output     [15:0] flush_ip,

    // BIU access side
    output reg        eu_req,
    output reg        eu_ready,
    output reg        eu_wr,
    output reg        eu_word,
    output reg [19:0] eu_addr,
    output reg  [1:0] eu_seg,
    output reg [15:0] eu_wdata,
    input             eu_started,
    input             eu_done,
    input      [15:0] eu_rdata,

    output            psw_ie,

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
typedef enum logic [5:0] {
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
    S_TRAP_IVT1, S_TRAP_IVT2, S_TRAP_IVT2W,
    S_TRAP_W1, S_TRAP_PSW, S_TRAP_PSWW,
    S_TRAP_W2, S_TRAP_PS, S_TRAP_PSW2W,
    S_TRAP_FLUSH, S_TRAP_PC, S_TRAP_PCW
} state_e;

state_e     state;
reg  [4:0]  dly;         // countdown for S_WAITX / S_RMWX / S_RSV / S_TRAP_W*
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
reg         flush_now;   // QS=E this cycle (trap path)

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
wire op_0f     = opc == 8'h0F;                       // two-byte forms
wire op_test1  = op_0f && opc2 == 8'h18;             // TEST1 rm8,imm3
wire op_rol4   = op_0f && opc2 == 8'h28;             // ROL4 rm8
wire op_modrm  = op_alu | op_movs8 | op_movs16 | op_movl8 | op_movl16 |
                 op_grpf6 | op_grpf7 | op_grpd0 | op_grpfe |
                 op_xchg8 | op_xchg16;

wire is_store  = op_movs8 | op_movs16;               // write-only mem access
wire is_load   = op_movl8 | op_movl16;
wire is_word_t = op_movs16 | op_movl16 | op_grpf7 |  // word transfer
                 op_xchg16;
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

wire [1:0] ea_seg_sel =
    (mrm_rm == 3'd2 || mrm_rm == 3'd3 ||
     (mrm_rm == 3'd6 && mrm_mod != 2'd0)) ? SEG_SS : SEG_DS;

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
// queue pop control
//----------------------------------------------------------------------------
wire pop_want = (state == S_FIRST) ||
                (state == S_DEC && op_modrm) ||
                (state == S_0F) || (state == S_DEC2) || (state == S_IMM3) ||
                (state == S_IMM_LO) || (state == S_IMM_HI) ||
                (state == S_DISP8) || (state == S_DLO) || (state == S_DHI);

assign q_pop   = pop_want && q_avail;
assign q_first = state == S_FIRST;
assign q_flush = flush_now;
assign flush_cs = ivt_seg;
assign flush_ip = ivt_off;
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
        S_EA1: eu_req = is_reader && mrm_mod == 2'd0;
        S_EA2: eu_req = is_reader;
        S_DISP8, S_DHI: eu_req = is_reader && q_pop;
        // POP r16 reserves the bus already during decode (measured:
        // cold-start POP suppresses the prefetch commit at cycle 1)
        S_DEC:  eu_req = !op_modrm && opc[7:3] == 5'b01011;
        S_REQ, S_WREQ,
        S_A4_SRC, S_A4_DST, S_A4_WR,
        S_TRAP_IVT1, S_TRAP_IVT2,
        S_TRAP_PSW, S_TRAP_PS, S_TRAP_FLUSH, S_TRAP_PC: begin
            eu_req   = 1'b1;
            eu_ready = 1'b1;
        end
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
endtask

// latch memory-operand access parameters (EA paths); off = 16-bit offset
task automatic setup_access(input [15:0] off);
    eu_addr <= {sr[ea_seg_sel], 4'h0} + {4'h0, off};
    eu_seg  <= ea_seg_sel;
    eu_word <= is_word_t;
    eu_wr   <= is_store;
    if (op_movs8)  eu_wdata <= reg8_pair(mrm_reg);
    if (op_movs16) eu_wdata <= rf[mrm_reg];
endtask

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

    if (srst) begin
        state    <= S_HALT;
        dly      <= '0;
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
        eu_wr    <= 1'b0;
        eu_word  <= 1'b0;
        eu_addr  <= '0;
        eu_seg   <= SEG_DS;
        eu_wdata <= '0;
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
        unique case (state)
            S_HALT: ;

            //----------------------------------------------------------------
            S_FIRST: if (q_pop) begin
                opc <= q_byte;
                pc  <= pc + 16'd1;
                state <= S_DEC;
            end

            //----------------------------------------------------------------
            S_DEC: begin
                if (op_modrm) begin
                    if (q_pop) begin
                        mrm <= q_byte;
                        pc  <= pc + 16'd1;
                        if (q_byte[7:6] == 2'd3) begin
                            // register form
                            if (op_alu | op_movs8 | op_movs16 |
                                op_movl8 | op_movl16 |
                                op_xchg8 | op_xchg16)
                                state <= S_EX;
                            else if (op_grpfe && q_byte[5:3] == 3'd0) begin
                                dly <= 5'd1;  wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpd0 && q_byte[5:3] == 3'd4) begin
                                dly <= 5'd3;  wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpf6 && q_byte[5:3] == 3'd4) begin
                                dly <= 5'd21; wnext <= S_EX; state <= S_WAITX;
                            end else if (op_grpf7 && q_byte[5:3] == 3'd6) begin
                                logic [32:0] dv;
                                dv = divu32({rf[2], rf[0]}, rf[q_byte[2:0]]);
                                {mem_op, disp} <= dv[31:0];  // q, r temp
                                psw <= psw_sub16(rf[2], rf[q_byte[2:0]], psw);
                                if (dv[32]) begin
                                    dly <= 5'd12; wnext <= S_TRAP_IVT1;
                                end else begin
                                    dly <= 5'd25; wnext <= S_EX;
                                end
                                state <= S_WAITX;
                            end else
                                state <= S_HALT;
                        end else begin
                            // memory form; group ops with an unimplemented
                            // /reg field park the sequencer
                            if ((op_grpf6 && q_byte[5:3] != 3'd4) ||
                                (op_grpf7 && q_byte[5:3] != 3'd6) ||
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
                    else if (opc[7:3] == 5'b01011) begin            // POP r16
                        eu_addr <= {sr[SEG_SS], 4'h0} + {4'h0, rf[4]};
                        eu_seg  <= SEG_SS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                        state   <= S_REQ;
                    end else state <= S_HALT;
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
                    dly     <= 5'd4;                   // src ready @ pop+5
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
                        dly <= 5'd11; wnext <= S_EX; state <= S_WAITX;
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
                if (dly == 5'd1) begin
                    eu_addr <= {sr[SEG_DS], 4'h0} + {4'h0, rf[6]};
                    eu_seg  <= SEG_DS;
                    eu_wr   <= 1'b0;
                    eu_word <= 1'b0;
                    state   <= (a4_cnt == 8'd0) ? S_HALT : S_A4_SRC;
                end
                dly <= dly - 5'd1;
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
                dly      <= 5'd3;
                state    <= S_A4_G2;
            end
            S_A4_G2: begin
                if (dly == 5'd1) begin
                    eu_wr    <= 1'b1;
                    eu_wdata <= mem_op;
                    state    <= S_A4_WR;
                end
                dly <= dly - 5'd1;
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
                    dly   <= a4_carry ? 5'd4 : 5'd5;
                    state <= S_A4_END;
                end
            end
            S_A4_END: begin
                if (dly == 5'd1) begin
                    // undefined-flag law: S=AC=CY(out), P=Z(out), V=0
                    psw[FB_CY] <= a4_carry;
                    psw[FB_S]  <= a4_carry;
                    psw[FB_AC] <= a4_carry;
                    psw[FB_Z]  <= a4_z;
                    psw[FB_P]  <= a4_z;
                    psw[FB_V]  <= 1'b0;
                    retire();
                end
                dly <= dly - 5'd1;
            end

            //----------------------------------------------------------------
            // effective-address path
            //----------------------------------------------------------------
            S_EA1: state <= (mrm_mod == 2'd1) ? S_DISP8 : S_EA2;
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
                setup_access(ea_base + {{8{q_byte[7]}}, q_byte});
                if (is_store) begin                       // d1 store: rdy @ 5
                    dly <= 5'd1; state <= S_RSV;
                end else state <= S_REQ;                  // d1 load: rdy @ 4
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
                setup_access(ea_base + {q_byte, disp[7:0]});
                if (is_reader) state <= S_REQ;            // d2 load: rdy @ 5
                else begin dly <= 5'd2; state <= S_RSV; end // d2 store: rdy @ 7
            end else begin
                dret <= S_DHI; state <= S_DSTALL;
            end
            S_DSTALL: state <= dret;

            //----------------------------------------------------------------
            // bus access issue / wait
            //----------------------------------------------------------------
            S_RSV: begin
                if (dly == 5'd1) state <= S_REQ;
                dly <= dly - 5'd1;
            end
            S_REQ: if (eu_started) state <= S_BUSW;
            S_BUSW: if (eu_done) begin
                if (opc[7:3] == 5'b01011) begin           // POP r16
                    rf[4] <= rf[4] + 16'd2;
                    rf[opc[2:0]] <= eu_rdata;             // POP SP: load wins
                    retire();
                end else if (opc[7:3] == 5'b01010) begin  // PUSH r16
                    retire();
                end else if (is_store) begin              // MOV 88/89 store
                    retire();
                end else begin
                    mem_op <= eu_rdata;
                    if (is_load || (op_alu && opc[5:3] == 3'd7))
                        state <= S_LD_W1;                 // MOV load / CMP
                    else if (op_test1)
                        state <= S_T1GAP;                 // imm pop done+2
                    else if (op_rol4) begin
                        dly <= 5'd10; state <= S_RMWX;    // wr ready done+11
                    end else if (op_alu || op_xchg8 || op_xchg16) begin
                        dly <= 5'd2; state <= S_RMWX;     // wr ready done+3
                    end else if (op_grpfe) begin
                        dly <= 5'd3; state <= S_RMWX;     // done+4
                    end else if (op_grpd0) begin
                        dly <= 5'd5; state <= S_RMWX;     // done+6
                    end else if (op_grpf6) begin
                        dly <= 5'd22; wnext <= S_EX; state <= S_WAITX;
                    end else if (op_grpf7) begin
                        logic [32:0] dv;
                        dv = divu32({rf[2], rf[0]}, eu_rdata);
                        {mem_op, disp} <= dv[31:0];
                        psw <= psw_sub16(rf[2], eu_rdata, psw);
                        if (dv[32]) begin
                            dly <= 5'd13; wnext <= S_TRAP_IVT1;
                        end else begin
                            dly <= 5'd26; wnext <= S_EX;
                        end
                        state <= S_WAITX;
                    end else state <= S_HALT;
                end
            end

            S_LD_W1: state <= S_LD_W2;
            S_LD_W2: begin
                if (op_movl8)       wr_reg8(mrm_reg, mem_op[7:0]);
                else if (op_movl16) rf[mrm_reg] <= mem_op;
                else if (op_alu)    psw <= ex_alu[23:8];  // CMP mem
                retire();
            end

            //----------------------------------------------------------------
            // generic wait, then execute (reg forms, MUL/DIV finish)
            //----------------------------------------------------------------
            S_WAITX: begin
                if (dly == 5'd1) begin
                    state <= wnext;
                    if (wnext == S_TRAP_IVT1) begin
                        // request params must be valid on state entry
                        eu_addr <= 20'h00000;
                        eu_seg  <= SEG_CS;
                        eu_wr   <= 1'b0;
                        eu_word <= 1'b1;
                    end
                end
                dly <= dly - 5'd1;
            end

            S_EX: begin
                if (op_test1) begin
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
                if (dly == 5'd1) begin
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
                dly <= dly - 5'd1;
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
                eu_addr <= 20'h00002;
                state <= S_TRAP_IVT2;
            end
            S_TRAP_IVT2: begin
                if (eu_done) ivt_off <= eu_rdata;
                if (eu_started) state <= S_TRAP_IVT2W;
            end
            S_TRAP_IVT2W: if (eu_done) begin
                ivt_seg  <= eu_rdata;
                // psw already carries the divide residue (pre-check
                // compare); latch the to-be-pushed value here, and clear
                // the live IE/TF at once - the PS status bits of the push
                // cycles already show IE=0 (measured)
                trap_psw <= psw;
                psw <= psw & ~16'h0300;
                dly <= 5'd2; state <= S_TRAP_W1;
            end
            S_TRAP_W1: begin
                if (dly == 5'd1) begin
                    state <= S_TRAP_PSW;
                    issue_push(trap_psw);
                end
                dly <= dly - 5'd1;
            end
            S_TRAP_PSW: if (eu_started) state <= S_TRAP_PSWW;
            S_TRAP_PSWW: if (eu_done) begin
                dly <= 5'd1; state <= S_TRAP_W2;
            end
            S_TRAP_W2: begin
                if (dly == 5'd1) begin
                    state <= S_TRAP_PS;
                    issue_push(sr[SEG_CS]);
                end
                dly <= dly - 5'd1;
            end
            S_TRAP_PS: if (eu_started) state <= S_TRAP_PSW2W;
            S_TRAP_PSW2W: if (eu_done) begin
                state <= S_TRAP_FLUSH;
                flush_now <= 1'b1;
                issue_push(pc);
                pc <= ivt_off;
                sr[SEG_CS] <= ivt_seg;
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
assign dbg_regs = {psw, arch_ip, sr[SEG_DS], sr[SEG_SS], sr[SEG_CS],
                   sr[SEG_ES], rf[7], rf[6], rf[5], rf[4], rf[3], rf[2],
                   rf[1], rf[0]};

endmodule
