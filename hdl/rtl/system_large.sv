//============================================================================
//
//  System Large Module - NEC V30/V35 Interface and DDRAM Control
//
//============================================================================

module system_large
(
    input         clk,
    input         reset,

    // DDRAM interface
    output        DDRAM_CLK,
    input         DDRAM_BUSY,
    output  [7:0] DDRAM_BURSTCNT,
    output [28:0] DDRAM_ADDR,
    input  [63:0] DDRAM_DOUT,
    input         DDRAM_DOUT_READY,
    output        DDRAM_RD,
    output [63:0] DDRAM_DIN,
    output  [7:0] DDRAM_BE,
    output        DDRAM_WE,

    // NEC processor interface
    inout  [19:0] NEC_AD,
    output        NEC_CLK,
    output        NEC_POLLn,
    output        NEC_READY,
    output        NEC_RESET,
    output        NEC_INT,
    output        NEC_NMI,
    output        NEC_LGn,
    output        NEC_AD_DIR,
    input         NEC_UBEn,
    input         NEC_RDn,
    input         NEC_WRn,
    input         NEC_IOn,
    input         NEC_BUFRn,
    input         NEC_BUFENn,
    input         NEC_ASTB,
    input         NEC_INTAKn,
    output        NEC_ENABLEn
);

// DDRAM - unused, directly assign to 0
assign {DDRAM_CLK, DDRAM_BURSTCNT, DDRAM_ADDR, DDRAM_DIN, DDRAM_BE, DDRAM_RD, DDRAM_WE} = '0;

// NEC control signals
assign NEC_POLLn = 0;
assign NEC_READY = 1;
assign NEC_INT = 0;
assign NEC_NMI = 0;
assign NEC_LGn = 1;
assign NEC_AD_DIR = 0;
assign NEC_RESET = reset;
assign NEC_ENABLEn = 0;

// NEC clock generation - divide system clock by 4
reg [1:0] clk_div4;
always_ff @(posedge clk) begin
    clk_div4 <= clk_div4 + 2'd1;
end

assign NEC_CLK = clk_div4[1];

endmodule
