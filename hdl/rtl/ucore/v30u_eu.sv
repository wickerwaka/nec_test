//============================================================================
//
//  v30u_eu - STAGE-U1 PLACEHOLDER.
//
//  U1 is the BIU-only stage: the sequencer (upc, the ucrom/ucdecode pair, the
//  loader march, the datapath) is U2's deliverable.  Until then this module
//  exists so the top's port/instantiation shape is the one U2 inherits, and
//  every output is tied off to its INERT value -- the same thing the FSM
//  core's scripted-consumer mode (`scr_en`) does to its EU side.
//
//  It carries NO state and NO save-state addresses (SS_EU_COUNT == 0 in
//  v30u_ss_pkg.sv); U2 seeds the EU region.
//
//============================================================================

module v30u_eu (
    input             clk,
    input             ce,
    input             srst,

    // queue port
    input       [7:0] q_byte,
    input             q_ripe,
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
    output      [1:0] eu_seg,
    output            eu_word,
    input             eu_slot_busy,
    output            eu_pair,
    output     [15:0] eu_wdata,
    input      [15:0] eu_rdata,
    input             eu_rd_done,
    input             eu_wr_done,
    input             eu_opr_free,

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

    // save-state (no EU addresses yet)
    input       [8:0] ss_addr,
    input      [15:0] ss_wdata,
    input             ss_we,
    output     [15:0] ss_rdata
);

assign q_pop     = 1'b0;
assign q_first   = 1'b0;
assign q_flush   = 1'b0;
assign flush_cs  = 16'h0000;
assign flush_ip  = 16'h0000;
assign eu_post   = 1'b0;
assign eu_bs     = 3'd7;
assign eu_addr   = 20'h00000;
assign eu_seg    = 2'd2;
assign eu_word   = 1'b0;
assign eu_pair   = 1'b0;
assign eu_wdata  = 16'h0000;
assign eu_susp   = 1'b0;
assign eu_resume = 1'b0;
assign eu_halt   = 1'b0;
assign eu_unhalt = 1'b0;

// M9: the PS nibble the BIU drives is {MD, IE, seg}.  With no EU the two
// machine bits come straight from the injected PSW so the boot / backdoor
// streams still carry the right S6:S5.
assign psw_ie  = bkd_regs[208 + 9];   // PSW bit 9 = IE
assign md8080  = 1'b0;                // ucore has no BRKEM path (ledger R4)

assign dbg_regs      = bkd_regs;
assign dbg_first_pop = 1'b0;
assign dbg_pend      = 1'b0;
assign ss_rdata      = 16'h0000;

wire _unused = &{1'b0, clk, ce, srst, q_byte, q_ripe, q_cnt, eu_slot_busy,
                 eu_rdata, eu_rd_done, eu_wr_done, eu_opr_free, halted,
                 pin_int, pin_nmi, pin_poll_n, bkd_load,
                 ss_addr, ss_wdata, ss_we};

endmodule
