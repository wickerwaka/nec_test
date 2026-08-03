//============================================================================
//  v30u_ss_pkg - the ucore save-state ADDRESS MAP.
//
//  The PACKAGE NAME is deliberately `v30_ss_pkg`, the same as the FSM core's:
//  the two cores are drop-in alternatives selected by the RTL FILE LIST
//  (sw/check_core.py --core {fsm,ucore}), and hdl/tb/tb_v30_core.sv imports
//  the package by name.  Exactly one of hdl/rtl/core/v30_ss_pkg.sv and
//  hdl/rtl/ucore/v30u_ss_pkg.sv is ever compiled.
//
//  SS_VERSION is in the 0x80 FAMILY (bit 7 set) so a stream can never be
//  mistaken for the FSM core's; the FSM map (0x03 / 82 / 120 / 203) is FROZEN
//  as a reference and is not extended.
//
//  AUDIT INVARIANT (inherited): every RTL state register <-> exactly ONE SSA_*
//  symbol <-> one read-mux arm <-> one write-decode arm.  Each SSA_B_* appears
//  exactly TWICE in v30u_biu.sv, each SSA_E_* exactly twice in v30u_eu.sv.
//
//  APPEND-ONLY: new fields append at the end of their module's dense region
//  (never renumber); any map edit bumps SS_VERSION and the counts.
//
//  Quartus 17.1: localparams + helper functions only.  No packed structs.
//============================================================================
`ifndef V30_SS_PKG_SV
`define V30_SS_PKG_SV

package v30_ss_pkg;

  localparam int          SS_ADDR_W    = 9;
  localparam int          SS_VERSION   = 8'h80;   // ucore map v0 (stage U1)
  localparam logic [8:0]  SSA_TAG      = 9'h000;
  localparam logic [8:0]  SS_BIU_BASE  = 9'h001;
  localparam int          SS_BIU_COUNT = 94;
  localparam logic [8:0]  SS_EU_BASE   = 9'h100;
  localparam int          SS_EU_COUNT  = 0;    // U2 seeds the EU region
  localparam int          SS_COUNT     = 1 + SS_BIU_COUNT + SS_EU_COUNT;
  localparam logic [15:0] SS_TAG       = {8'(SS_VERSION), 8'(SS_COUNT)};

  //--------------------------------------------------------------------------
  // BIU region (module v30u_biu): 0x001-0x05E
  //--------------------------------------------------------------------------
  localparam logic [8:0] SSA_B_T1_HALF2         = 9'h001;
  localparam logic [8:0] SSA_B_RUN              = 9'h002;
  localparam logic [8:0] SSA_B_TS               = 9'h003;
  localparam logic [8:0] SSA_B_CUR_BS           = 9'h004;
  localparam logic [8:0] SSA_B_CUR_ADDR_LO      = 9'h005;
  localparam logic [8:0] SSA_B_CUR_ADDR_HI      = 9'h006;
  localparam logic [8:0] SSA_B_CUR_DATA         = 9'h007;
  localparam logic [8:0] SSA_B_CUR_UBE_N        = 9'h008;
  localparam logic [8:0] SSA_B_CUR_SEG          = 9'h009;
  localparam logic [8:0] SSA_B_CUR_FETCH        = 9'h00A;
  localparam logic [8:0] SSA_B_CUR_HALT         = 9'h00B;
  localparam logic [8:0] SSA_B_CUR_NOADDR       = 9'h00C;
  localparam logic [8:0] SSA_B_CUR_WR           = 9'h00D;
  localparam logic [8:0] SSA_B_CUR_NEED         = 9'h00E;
  localparam logic [8:0] SSA_B_CUR_RDLAST       = 9'h00F;
  localparam logic [8:0] SSA_B_CUR_PN           = 9'h010;
  localparam logic [8:0] SSA_B_CUR_LATET1       = 9'h011;
  localparam logic [8:0] SSA_B_EVALD            = 9'h012;
  localparam logic [8:0] SSA_B_SEV              = 9'h013;
  localparam logic [8:0] SSA_B_DAGE             = 9'h014;
  localparam logic [8:0] SSA_B_CMT_VALID        = 9'h015;
  localparam logic [8:0] SSA_B_CMT_BS           = 9'h016;
  localparam logic [8:0] SSA_B_CMT_ADDR_LO      = 9'h017;
  localparam logic [8:0] SSA_B_CMT_ADDR_HI      = 9'h018;
  localparam logic [8:0] SSA_B_CMT_DATA         = 9'h019;
  localparam logic [8:0] SSA_B_CMT_UBE_N        = 9'h01A;
  localparam logic [8:0] SSA_B_CMT_SEG          = 9'h01B;
  localparam logic [8:0] SSA_B_CMT_FETCH        = 9'h01C;
  localparam logic [8:0] SSA_B_CMT_HALT         = 9'h01D;
  localparam logic [8:0] SSA_B_CMT_NOADDR       = 9'h01E;
  localparam logic [8:0] SSA_B_CMT_WR           = 9'h01F;
  localparam logic [8:0] SSA_B_CMT_NEED         = 9'h020;
  localparam logic [8:0] SSA_B_CMT_RDLAST       = 9'h021;
  localparam logic [8:0] SSA_B_CMT_PN           = 9'h022;
  localparam logic [8:0] SSA_B_CDAGE            = 9'h023;
  localparam logic [8:0] SSA_B_CMT_PREV_FP      = 9'h024;
  localparam logic [8:0] SSA_B_CMT_WAS_OWED     = 9'h025;
  localparam logic [8:0] SSA_B_LAST_FADDR       = 9'h026;
  localparam logic [8:0] SSA_B_Q0               = 9'h027;
  localparam logic [8:0] SSA_B_Q1               = 9'h028;
  localparam logic [8:0] SSA_B_Q2               = 9'h029;
  localparam logic [8:0] SSA_B_Q3               = 9'h02A;
  localparam logic [8:0] SSA_B_Q4               = 9'h02B;
  localparam logic [8:0] SSA_B_Q5               = 9'h02C;
  localparam logic [8:0] SSA_B_Q_HEAD           = 9'h02D;
  localparam logic [8:0] SSA_B_Q_CNT            = 9'h02E;
  localparam logic [8:0] SSA_B_GRN_N            = 9'h02F;
  localparam logic [8:0] SSA_B_GRN_TTL          = 9'h030;
  localparam logic [8:0] SSA_B_FETCH_PTR        = 9'h031;
  localparam logic [8:0] SSA_B_CS               = 9'h032;
  localparam logic [8:0] SSA_B_SUSPENDED        = 9'h033;
  localparam logic [8:0] SSA_B_HALTED           = 9'h034;
  localparam logic [8:0] SSA_B_HALT_PEND        = 9'h035;
  localparam logic [8:0] SSA_B_PF_OWED          = 9'h036;
  localparam logic [8:0] SSA_B_PF_ARM           = 9'h037;
  localparam logic [8:0] SSA_B_PF_LAND          = 9'h038;
  localparam logic [8:0] SSA_B_INFL_TTL         = 9'h039;
  localparam logic [8:0] SSA_B_INFL_N           = 9'h03A;
  localparam logic [8:0] SSA_B_ABSORB_TTL       = 9'h03B;
  localparam logic [8:0] SSA_B_NO_EVAL          = 9'h03C;
  localparam logic [8:0] SSA_B_FLUSH_EVAL       = 9'h03D;
  localparam logic [8:0] SSA_B_E_PEND           = 9'h03E;
  localparam logic [8:0] SSA_B_RQ_N             = 9'h03F;
  localparam logic [8:0] SSA_B_RQ0_BS           = 9'h040;
  localparam logic [8:0] SSA_B_RQ0_ADDR_LO      = 9'h041;
  localparam logic [8:0] SSA_B_RQ0_ADDR_HI      = 9'h042;
  localparam logic [8:0] SSA_B_RQ0_DATA         = 9'h043;
  localparam logic [8:0] SSA_B_RQ0_UBE          = 9'h044;
  localparam logic [8:0] SSA_B_RQ0_SEG          = 9'h045;
  localparam logic [8:0] SSA_B_RQ0_NOADDR       = 9'h046;
  localparam logic [8:0] SSA_B_RQ0_WR           = 9'h047;
  localparam logic [8:0] SSA_B_RQ0_NEED         = 9'h048;
  localparam logic [8:0] SSA_B_RQ0_LAST         = 9'h049;
  localparam logic [8:0] SSA_B_RQ1_BS           = 9'h04A;
  localparam logic [8:0] SSA_B_RQ1_ADDR_LO      = 9'h04B;
  localparam logic [8:0] SSA_B_RQ1_ADDR_HI      = 9'h04C;
  localparam logic [8:0] SSA_B_RQ1_DATA         = 9'h04D;
  localparam logic [8:0] SSA_B_RQ1_UBE          = 9'h04E;
  localparam logic [8:0] SSA_B_RQ1_SEG          = 9'h04F;
  localparam logic [8:0] SSA_B_RQ1_NOADDR       = 9'h050;
  localparam logic [8:0] SSA_B_RQ1_WR           = 9'h051;
  localparam logic [8:0] SSA_B_RQ1_NEED         = 9'h052;
  localparam logic [8:0] SSA_B_RQ1_LAST         = 9'h053;
  localparam logic [8:0] SSA_B_SLOT_BUSY        = 9'h054;
  localparam logic [8:0] SSA_B_SLOT_ACC         = 9'h055;
  localparam logic [8:0] SSA_B_OPR_HELD         = 9'h056;
  localparam logic [8:0] SSA_B_DONE_CTR         = 9'h057;
  localparam logic [8:0] SSA_B_DONE_WR          = 9'h058;
  localparam logic [8:0] SSA_B_RD_DONE_P        = 9'h059;
  localparam logic [8:0] SSA_B_WR_DONE_P        = 9'h05A;
  localparam logic [8:0] SSA_B_OPR_FREE_P       = 9'h05B;
  localparam logic [8:0] SSA_B_RD_VAL           = 9'h05C;
  localparam logic [8:0] SSA_B_READY_PREV       = 9'h05D;
  localparam logic [8:0] SSA_B_LAST_UBE         = 9'h05E;

  // dense-iteration helper (TB/harness): stream index -> address
  function automatic logic [8:0] ss_addr_of(input int i);
    if (i == 0)                 ss_addr_of = SSA_TAG;
    else if (i <= SS_BIU_COUNT) ss_addr_of = SS_BIU_BASE + 9'(i - 1);
    else                        ss_addr_of = SS_EU_BASE  + 9'(i - 1 - SS_BIU_COUNT);
  endfunction

  // field width per address (TB mode-5 round-trip check; 0 = unmapped)
  function automatic int ss_field_width(input logic [8:0] a);
    case (a)
      SSA_TAG: ss_field_width = 16;
      SSA_B_T1_HALF2:        ss_field_width = 1;
      SSA_B_RUN:             ss_field_width = 1;
      SSA_B_TS:              ss_field_width = 3;
      SSA_B_CUR_BS:          ss_field_width = 3;
      SSA_B_CUR_ADDR_LO:     ss_field_width = 16;
      SSA_B_CUR_ADDR_HI:     ss_field_width = 4;
      SSA_B_CUR_DATA:        ss_field_width = 16;
      SSA_B_CUR_UBE_N:       ss_field_width = 1;
      SSA_B_CUR_SEG:         ss_field_width = 2;
      SSA_B_CUR_FETCH:       ss_field_width = 1;
      SSA_B_CUR_HALT:        ss_field_width = 1;
      SSA_B_CUR_NOADDR:      ss_field_width = 1;
      SSA_B_CUR_WR:          ss_field_width = 1;
      SSA_B_CUR_NEED:        ss_field_width = 1;
      SSA_B_CUR_RDLAST:      ss_field_width = 1;
      SSA_B_CUR_PN:          ss_field_width = 2;
      SSA_B_CUR_LATET1:      ss_field_width = 1;
      SSA_B_EVALD:           ss_field_width = 1;
      SSA_B_SEV:             ss_field_width = 2;
      SSA_B_DAGE:            ss_field_width = 3;
      SSA_B_CMT_VALID:       ss_field_width = 1;
      SSA_B_CMT_BS:          ss_field_width = 3;
      SSA_B_CMT_ADDR_LO:     ss_field_width = 16;
      SSA_B_CMT_ADDR_HI:     ss_field_width = 4;
      SSA_B_CMT_DATA:        ss_field_width = 16;
      SSA_B_CMT_UBE_N:       ss_field_width = 1;
      SSA_B_CMT_SEG:         ss_field_width = 2;
      SSA_B_CMT_FETCH:       ss_field_width = 1;
      SSA_B_CMT_HALT:        ss_field_width = 1;
      SSA_B_CMT_NOADDR:      ss_field_width = 1;
      SSA_B_CMT_WR:          ss_field_width = 1;
      SSA_B_CMT_NEED:        ss_field_width = 1;
      SSA_B_CMT_RDLAST:      ss_field_width = 1;
      SSA_B_CMT_PN:          ss_field_width = 2;
      SSA_B_CDAGE:           ss_field_width = 3;
      SSA_B_CMT_PREV_FP:     ss_field_width = 16;
      SSA_B_CMT_WAS_OWED:    ss_field_width = 1;
      SSA_B_LAST_FADDR:      ss_field_width = 16;
      SSA_B_Q0:              ss_field_width = 8;
      SSA_B_Q1:              ss_field_width = 8;
      SSA_B_Q2:              ss_field_width = 8;
      SSA_B_Q3:              ss_field_width = 8;
      SSA_B_Q4:              ss_field_width = 8;
      SSA_B_Q5:              ss_field_width = 8;
      SSA_B_Q_HEAD:          ss_field_width = 3;
      SSA_B_Q_CNT:           ss_field_width = 4;
      SSA_B_GRN_N:           ss_field_width = 2;
      SSA_B_GRN_TTL:         ss_field_width = 2;
      SSA_B_FETCH_PTR:       ss_field_width = 16;
      SSA_B_CS:              ss_field_width = 16;
      SSA_B_SUSPENDED:       ss_field_width = 1;
      SSA_B_HALTED:          ss_field_width = 1;
      SSA_B_HALT_PEND:       ss_field_width = 1;
      SSA_B_PF_OWED:         ss_field_width = 1;
      SSA_B_PF_ARM:          ss_field_width = 1;
      SSA_B_PF_LAND:         ss_field_width = 1;
      SSA_B_INFL_TTL:        ss_field_width = 2;
      SSA_B_INFL_N:          ss_field_width = 2;
      SSA_B_ABSORB_TTL:      ss_field_width = 2;
      SSA_B_NO_EVAL:         ss_field_width = 1;
      SSA_B_FLUSH_EVAL:      ss_field_width = 1;
      SSA_B_E_PEND:          ss_field_width = 1;
      SSA_B_RQ_N:            ss_field_width = 2;
      SSA_B_RQ0_BS:          ss_field_width = 3;
      SSA_B_RQ0_ADDR_LO:     ss_field_width = 16;
      SSA_B_RQ0_ADDR_HI:     ss_field_width = 4;
      SSA_B_RQ0_DATA:        ss_field_width = 16;
      SSA_B_RQ0_UBE:         ss_field_width = 1;
      SSA_B_RQ0_SEG:         ss_field_width = 2;
      SSA_B_RQ0_NOADDR:      ss_field_width = 1;
      SSA_B_RQ0_WR:          ss_field_width = 1;
      SSA_B_RQ0_NEED:        ss_field_width = 1;
      SSA_B_RQ0_LAST:        ss_field_width = 1;
      SSA_B_RQ1_BS:          ss_field_width = 3;
      SSA_B_RQ1_ADDR_LO:     ss_field_width = 16;
      SSA_B_RQ1_ADDR_HI:     ss_field_width = 4;
      SSA_B_RQ1_DATA:        ss_field_width = 16;
      SSA_B_RQ1_UBE:         ss_field_width = 1;
      SSA_B_RQ1_SEG:         ss_field_width = 2;
      SSA_B_RQ1_NOADDR:      ss_field_width = 1;
      SSA_B_RQ1_WR:          ss_field_width = 1;
      SSA_B_RQ1_NEED:        ss_field_width = 1;
      SSA_B_RQ1_LAST:        ss_field_width = 1;
      SSA_B_SLOT_BUSY:       ss_field_width = 1;
      SSA_B_SLOT_ACC:        ss_field_width = 1;
      SSA_B_OPR_HELD:        ss_field_width = 1;
      SSA_B_DONE_CTR:        ss_field_width = 2;
      SSA_B_DONE_WR:         ss_field_width = 1;
      SSA_B_RD_DONE_P:       ss_field_width = 1;
      SSA_B_WR_DONE_P:       ss_field_width = 1;
      SSA_B_OPR_FREE_P:      ss_field_width = 1;
      SSA_B_RD_VAL:          ss_field_width = 16;
      SSA_B_READY_PREV:      ss_field_width = 1;
      SSA_B_LAST_UBE:        ss_field_width = 1;
      default: ss_field_width = 0;
    endcase
  endfunction

endpackage

`endif
