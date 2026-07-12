//============================================================================
//
//  v30_core - cycle-accurate NEC V30 (uPD70116) CPU core, max mode
//
//  Campaign 3: EU + BIU verified against golden traces captured from the
//  real chip (tests/v30/v0.1) via hdl/tb/tb_v30_core.sv / sw/check_core.py.
//
//  The port list mirrors the physical chip's maximum-mode pins as seen by
//  the harness (hdl/rtl/nec_bus.sv), so Campaign 4 can instantiate this
//  core behind the same nec_bus interface used for the socketed part:
//    AD[19:0]  muxed address/data; AD[19:16] carry PS3-0 during T2-T4
//    BS[2:0]   bus-cycle status (8086 S2-S0 compatible)
//    QS[1:0]   queue status (00 none, 01 first byte, 10 flush, 11 byte)
//    RD_N, UBE_N, BUSLOCK_N, READY, RESET, INT, NMI, POLL_N, CLK
//
//  V30_BACKDOOR (verification only, set by the testbench build): adds
//  state-injection/observation ports so golden test cases can start from
//  an arbitrary architectural state without a load routine, plus a
//  scripted queue-consumer mode that replaces the EU for BIU-only
//  verification. The backdoor is compiled out of synthesis builds; the
//  normal reset flow (vector fetch at FFFF0h) is a Campaign 4 item and
//  is not implemented yet.
//
//  Not yet implemented (later Campaign 3 mission blocks): INT/NMI/POLL,
//  HALT, BUSLOCK, wait-state-heavy paths beyond READY sampling in T3.
//
//============================================================================

module v30_core (
    input             CLK,
    input             RESET,
    input             READY,
    input             INT,
    input             NMI,
    input             POLL_N,
    inout      [19:0] AD,
    output      [1:0] QS,
    output      [2:0] BS,
    output            RD_N,
    output            UBE_N,
    output            BUSLOCK_N
`ifdef V30_BACKDOOR
    ,
    input             bkd_load,     // pulse while RESET=1: inject state
    input     [223:0] bkd_regs,     // {psw,ip,ds,ss,cs,es,di,si,bp,sp,bx,dx,cx,ax}
    input      [47:0] bkd_queue,    // queue bytes, entry 0 first
    input       [2:0] bkd_qlen,
    input      [15:0] bkd_fetch_ip, // BIU fetch offset (= ip + qlen)
    input             scr_en,       // scripted-consumer mode (BIU-only test)
    input       [1:0] scr_qop,      // per-cycle queue op, QS encoding
    output    [223:0] dbg_regs,     // ip slot holds the retired-instruction IP
    output            dbg_first_pop
`endif
);

`ifndef V30_BACKDOOR
logic         bkd_load = 1'b0;
logic [223:0] bkd_regs = '0;
logic  [47:0] bkd_queue = '0;
logic   [2:0] bkd_qlen = '0;
logic  [15:0] bkd_fetch_ip = '0;
logic         scr_en = 1'b0;
logic   [1:0] scr_qop = '0;
`endif

wire  [7:0] q_byte;
wire        q_avail;
wire        eu_pop, eu_first, eu_flush;
wire [15:0] eu_flush_cs, eu_flush_ip;
wire        eu_req, eu_hold, eu_ready, eu_wr, eu_word;
wire [19:0] eu_addr;
wire  [1:0] eu_seg;
wire [15:0] eu_wdata;
wire        eu_started, eu_done, eu_wdone, eu_t1;
wire [15:0] eu_rdata;
wire        psw_ie;

// scripted-consumer override (BIU-only verification)
wire q_pop   = scr_en ? scr_qop[0]              : eu_pop;
wire q_first = scr_en ? (scr_qop == 2'b01)      : eu_first;
wire q_flush = scr_en ? 1'b0                    : eu_flush;
wire qs_e;   // E display timing is BIU-generated (measured law)

// queue status pins: 00 none, 01 first byte, 10 flush, 11 subsequent byte
assign QS = qs_e   ? 2'b10
          : q_pop  ? (q_first ? 2'b01 : 2'b11)
          : 2'b00;

wire [19:0] ad_o;
wire        ad_oe_addr, ad_oe_ps, ad_oe_data;

v30_biu u_biu (
    .clk        (CLK),
    .srst       (RESET),
    .bs         (BS),
    .ad_o       (ad_o),
    .ad_oe_addr (ad_oe_addr),
    .ad_oe_ps   (ad_oe_ps),
    .ad_oe_data (ad_oe_data),
    .ube_n      (UBE_N),
    .rd_n       (RD_N),
    .ad_i       (AD[15:0]),
    .ready      (READY),
    .psw_ie     (psw_ie),
    .q_byte     (q_byte),
    .q_avail    (q_avail),
    .qs_e       (qs_e),
    .q_pop      (q_pop),
    .q_flush    (q_flush),
    .flush_cs   (eu_flush_cs),
    .flush_ip   (eu_flush_ip),
    .eu_req     (scr_en ? 1'b0 : eu_req),
    .eu_hold    (scr_en ? 1'b0 : eu_hold),
    .eu_ready   (eu_ready),
    .eu_wr      (eu_wr),
    .eu_word    (eu_word),
    .eu_addr    (eu_addr),
    .eu_seg     (eu_seg),
    .eu_wdata   (eu_wdata),
    .eu_started (eu_started),
    .eu_done    (eu_done),
    .eu_wdone   (eu_wdone),
    .eu_t1      (eu_t1),
    .eu_rdata   (eu_rdata),
    .bkd_load   (bkd_load),
    .bkd_cs     (bkd_regs[144 +: 16]),
    .bkd_ip     (bkd_fetch_ip),
    .bkd_queue  (bkd_queue),
    .bkd_qlen   (bkd_qlen)
);

v30_eu u_eu (
    .clk        (CLK),
    .srst       (RESET),
    .q_byte     (q_byte),
    .q_avail    (q_avail),
    .q_pop      (eu_pop),
    .q_first    (eu_first),
    .q_flush    (eu_flush),
    .flush_cs   (eu_flush_cs),
    .flush_ip   (eu_flush_ip),
    .eu_req     (eu_req),
    .eu_hold    (eu_hold),
    .eu_ready   (eu_ready),
    .eu_wr      (eu_wr),
    .eu_word    (eu_word),
    .eu_addr    (eu_addr),
    .eu_seg     (eu_seg),
    .eu_wdata   (eu_wdata),
    .eu_started (eu_started),
    .eu_done    (eu_done),
    .eu_wdone   (eu_wdone),
    .eu_t1      (eu_t1),
    .eu_rdata   (eu_rdata),
    .psw_ie     (psw_ie),
    .bkd_load   (bkd_load),
    .bkd_regs   (bkd_regs)
`ifdef V30_BACKDOOR
    ,
    .dbg_regs      (dbg_regs),
    .dbg_first_pop (dbg_first_pop)
`else
    ,
    /* verilator lint_off PINCONNECTEMPTY */
    .dbg_regs      (),
    .dbg_first_pop ()
    /* verilator lint_on PINCONNECTEMPTY */
`endif
);

// AD drive (simple en?val:'z forms only - Verilator requirement).
// AD[19:16] carry the address during address phases and PS3-0 during
// the data phase; AD[15:0] additionally carry write data.
assign AD[15:0]  = (ad_oe_addr | ad_oe_data) ? ad_o[15:0]  : 16'hzzzz;
assign AD[19:16] = (ad_oe_addr | ad_oe_ps)   ? ad_o[19:16] : 4'hz;

assign BUSLOCK_N = 1'b1;

wire _unused = &{1'b0, INT, NMI, POLL_N, scr_qop[1]};

endmodule
