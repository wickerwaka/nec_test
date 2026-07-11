//============================================================================
//
//  System Large Module - NEC V30 test harness core
//
//  Ties together the max-mode bus interface (nec_bus), the simulated
//  memory (test_mem), and the per-cycle trace capture (capture_buf).
//
//  Configuration is static for now (4 MHz CPU clock, zero wait states);
//  the HPS bridge will make these host-controlled and drain the capture
//  buffer. DDRAM is unused until traces outgrow BRAM.
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
    inout  [19:0] NEC_AD,       // 20-bit multiplex address and data bus
    output        NEC_AD_DIR,   // 0 - input, 1 - output
    output        NEC_CLK,      // CPU Clock
    output        NEC_POLL_N,   // CPU Poll input (active low)
    output        NEC_READY,    // Tell the CPU the data on the bus is valid
    output        NEC_RESET,    // CPU Reset
    output        NEC_INT,      // CPU interupt request
    output        NEC_NMI,      // CPU Non-maskable interupt request
    input   [1:0] NEC_QS,       // CPU Queue state
    input   [2:0] NEC_BS,       // CPU Bus state
    input         NEC_BUSLOCK_N,// CPU asserts the bus (active low)
    input         NEC_UBE_N,    // Upper byte is valid in the databus (active low)
    input         NEC_RD_N,     // Current cycle is a read cycle (active_low)
    output        NEC_ENABLE_N, // Power on the CPU (active low)

    output        dbg_led       // capture status; also anchors the capture RAM
                                // so it survives synthesis until the HPS
                                // bridge becomes its real consumer
);

// DDRAM - unused, directly assign to 0
assign {DDRAM_CLK, DDRAM_BURSTCNT, DDRAM_ADDR, DDRAM_DIN, DDRAM_BE, DDRAM_RD, DDRAM_WE} = '0;

//----------------------------------------------------------------------------
// Static configuration (host-controlled once the HPS bridge exists)
//----------------------------------------------------------------------------
// 32 MHz sys clock / 8 = 4 MHz CPU clock: comfortably inside the
// uPD70116C-8's 2-8 MHz legal range with 8 sys samples per CPU cycle.
wire [5:0] cfg_clk_div     = 6'd8;
wire [3:0] cfg_wait_states = 4'd0;
wire [7:0] cfg_int_vector  = 8'hFF;

//----------------------------------------------------------------------------
// Bus interface
//----------------------------------------------------------------------------
wire [19:0] mem_addr;
wire  [2:0] mem_cycle_type;
wire [15:0] mem_rdata;
wire        mem_wr_req;
wire [15:0] mem_wdata;
wire  [1:0] mem_be;
wire        cap_valid;
wire [63:0] cap_record;
wire        cpu_running;

nec_bus bus
(
    .clk(clk),
    .reset(reset),

    .cfg_clk_div(cfg_clk_div),
    .cfg_wait_states(cfg_wait_states),
    .cfg_int_vector(cfg_int_vector),

    .int_req(1'b0),
    .nmi_req(1'b0),
    .poll_n_in(1'b0),

    .NEC_AD(NEC_AD),
    .NEC_AD_DIR(NEC_AD_DIR),
    .NEC_CLK(NEC_CLK),
    .NEC_POLL_N(NEC_POLL_N),
    .NEC_READY(NEC_READY),
    .NEC_RESET(NEC_RESET),
    .NEC_INT(NEC_INT),
    .NEC_NMI(NEC_NMI),
    .NEC_QS(NEC_QS),
    .NEC_BS(NEC_BS),
    .NEC_BUSLOCK_N(NEC_BUSLOCK_N),
    .NEC_UBE_N(NEC_UBE_N),
    .NEC_RD_N(NEC_RD_N),
    .NEC_ENABLE_N(NEC_ENABLE_N),

    .mem_addr(mem_addr),
    .mem_cycle_type(mem_cycle_type),
    .mem_rdata(mem_rdata),
    .mem_wr_req(mem_wr_req),
    .mem_wdata(mem_wdata),
    .mem_be(mem_be),

    .cap_valid(cap_valid),
    .cap_record(cap_record),

    .cpu_running(cpu_running)
);

//----------------------------------------------------------------------------
// Simulated memory
//----------------------------------------------------------------------------
test_mem mem
(
    .clk(clk),
    .addr(mem_addr),
    .cycle_type(mem_cycle_type),
    .rdata(mem_rdata),
    .wr_req(mem_wr_req),
    .wdata(mem_wdata),
    .be(mem_be)
);

//----------------------------------------------------------------------------
// Trace capture: arms when the CPU comes out of reset, records every CPU
// cycle until full. Read port is idle until the HPS bridge exists; kept
// observable via SignalTap.
//----------------------------------------------------------------------------
wire                cap_full;
wire [12:0]         cap_count;
wire [63:0]         cap_rd_data;

capture_buf #(.LOG2_DEPTH(12)) capture
(
    .clk(clk),
    .reset(reset),
    .arm(cpu_running),
    .wr_valid(cap_valid),
    .wr_data(cap_record),
    .full(cap_full),
    .count(cap_count),
    .rd_addr(cap_count[11:0]),
    .rd_data(cap_rd_data)
);

// LED on when the trace has filled. The noprune register consumes the read
// port so the buffer RAM survives synthesis until the HPS bridge exists.
(* noprune *) reg [63:0] dbg_cap_rd_q /* synthesis noprune */;
always_ff @(posedge clk) dbg_cap_rd_q <= cap_rd_data;

assign dbg_led = cap_full;

endmodule
