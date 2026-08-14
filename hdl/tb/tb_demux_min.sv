//============================================================================
//
//  tb_demux_min -- THE DE-MUXED CONFIGURATION, PROVEN RATHER THAN ASSUMED.
//
//  A configuration nothing compiles is a configuration nothing knows is
//  broken.  `V30_MUXED_AD` removes three ports from `v30_core` (`AD`, `AD_OE`,
//  `CE_HALF`) and all of the multiplexing machinery behind them; every
//  standing gate in the tree builds the core WITH the define, so without this
//  harness the OTHER configuration would never be elaborated at all.
//
//  It is deliberately the SMALLEST HONEST THING: it drives the core from a
//  memory addressed by `ADDR_O`, returns bytes on `DATA_I`, commits stores
//  from `DATA_O`, records `STATUS_O`, and counts what the core actually did.
//  It is NOT a scorer -- there are no goldens for a bus this shape, and
//  inventing some would be fitting.  What it proves is:
//
//    * the de-muxed core ELABORATES and RUNS,
//    * the three ports carry a real instruction stream (the census bars),
//    * `AD` / `AD_OE` / `CE_HALF` are GONE (a build that connects one fails --
//      `sw/demux_off_gate.py`'s second leg),
//    * and the core needs NO half-cycle enable: there is one `ce` and nothing
//      else, which is the whole point of removing the mux.
//
//  THE BUS PROTOCOL IS THE PART'S OWN, max mode: `BS` (S0-S2) announces, the
//  T-state is reconstructed from `BS`/`READY` exactly as `nec_bus` does it in
//  fabric and as `tb_chain_lfsr.sv` does it here, and NOTHING DUT-INTERNAL IS
//  READ.  The one difference from `tb_chain_lfsr` is the point of the wave:
//  there is no T1 address latch, because `ADDR_O` is valid for the whole
//  cycle and can simply be read.
//
//  +seed=<n>      LFSR seed for the memory image and the pin/READY draws
//  +nclocks=<n>   fabric clocks to run (default 200,000)
//  +cediv=<n>     fabric clocks per CE (default 4)
//
//  docs/notes/demux_bus_prereg_2026-08-14.md §5.
//
//============================================================================
`timescale 1ns/1ps

module tb_demux_min;

//---------------------------------------------------------------------------
// plusargs
//---------------------------------------------------------------------------
integer seed_cfg = 1;
integer nclocks  = 200000;
integer ce_div   = 4;

initial begin
    if (!$value$plusargs("seed=%d",    seed_cfg)) seed_cfg = 1;
    if (!$value$plusargs("nclocks=%d", nclocks))  nclocks  = 200000;
    if (!$value$plusargs("cediv=%d",   ce_div))   ce_div   = 4;
    if (ce_div < 1)
        $fatal(1, "tb_demux_min: +cediv must be >= 1");
end

//---------------------------------------------------------------------------
// clock and the ONE enable.  There is no `ce_half` in this configuration and
// no port to put it on -- that is the deliverable, not an omission.
//---------------------------------------------------------------------------
logic clk = 1'b0;
always #5 clk = ~clk;

integer ce_cnt = 0;
logic   ce = 1'b0;
always @(posedge clk) begin
    if (ce_cnt >= ce_div - 1) begin ce_cnt <= 0;           ce <= 1'b1; end
    else                      begin ce_cnt <= ce_cnt + 1;  ce <= 1'b0; end
end

//---------------------------------------------------------------------------
// LFSR (the same x^32+x^22+x^2+x^1 form tb_chain_lfsr uses)
//---------------------------------------------------------------------------
function automatic logic [31:0] lfsr_next(input logic [31:0] s);
    lfsr_next = {s[30:0], s[31] ^ s[21] ^ s[1] ^ s[0]};
endfunction

function automatic logic [31:0] seed_of(input integer base, input integer k);
    logic [31:0] v;
    begin
        v = 32'h1 + 32'(base) * 32'h9E37_79B9 + 32'(k) * 32'h85EB_CA6B;
        if (v == 32'h0) v = 32'h1;
        seed_of = v;
    end
endfunction

logic [31:0] l_mem, l_rdy, l_pin;

//---------------------------------------------------------------------------
// reset, pins, READY
//---------------------------------------------------------------------------
logic reset = 1'b1;
integer reset_ce = 0;
always @(posedge clk) if (ce) begin
    if (reset_ce < 24) reset_ce <= reset_ce + 1;
    else               reset    <= 1'b0;
end

logic pin_int = 1'b0, pin_nmi = 1'b0, pin_poll_n = 1'b0;
always @(posedge clk) if (ce) begin
    l_pin      = lfsr_next(l_pin);
    pin_int   <= (l_pin[7:0]  == 8'h00);
    pin_nmi   <= (l_pin[19:8] == 12'h000);
    pin_poll_n<= l_pin[20];
end

logic ready_r = 1'b1;
always @(posedge clk) if (ce) begin
    l_rdy   = lfsr_next(l_rdy);
    ready_r <= (l_rdy[1:0] != 2'b00);             // ~75 % ready
end

//---------------------------------------------------------------------------
// THE DE-MUXED PINS.  Note what is NOT here: no `AD`, no `AD_OE`, no
// `ce_half`.  The core has no such ports in this configuration.
//---------------------------------------------------------------------------
wire [19:0] ADDR_O;
wire [15:0] DATA_O;
wire  [3:0] STATUS_O;
logic [15:0] DATA_I;
wire  [1:0] QS;
wire  [2:0] BS;
wire        RD_N, UBE_N, BUSLOCK_N;
wire [15:0] SS_RDATA;
wire        SS_ERR, SS_BUS_QUIET;

v30_core dut (
    .CLK       (clk),
    .CE        (ce),
    .RESET     (reset),
    .READY     (ready_r),
    .INT       (pin_int),
    .NMI       (pin_nmi),
    .POLL_N    (pin_poll_n),
    .DATA_I    (DATA_I),
    .ADDR_O    (ADDR_O),
    .DATA_O    (DATA_O),
    .STATUS_O  (STATUS_O),
    .QS        (QS),
    .BS        (BS),
    .RD_N      (RD_N),
    .UBE_N     (UBE_N),
    .BUSLOCK_N (BUSLOCK_N),
    .SS_ADDR   ('0),
    .SS_WDATA  ('0),
    .SS_WE     (1'b0),
    .SS_RDATA  (SS_RDATA),
    .SS_ERR    (SS_ERR),
    .SS_BUS_QUIET (SS_BUS_QUIET)
);

//---------------------------------------------------------------------------
// THE BUS TRACKER, reconstructed from BS/READY -- `tb_chain_lfsr.sv`'s, with
// its T1 ADDRESS LATCH DELETED.  On a de-muxed bus the address is a port that
// holds for the whole cycle, so the latch has nothing to do.
//---------------------------------------------------------------------------
localparam [2:0] ST_TI = 3'd0, ST_T1 = 3'd1, ST_T2 = 3'd2,
                 ST_T3 = 3'd3, ST_TW = 3'd4, ST_T4 = 3'd5;
localparam [2:0] BS_PASV = 3'b111;

logic [2:0] tb_t = ST_TI;
wire        bs_active = BS != BS_PASV;

wire [2:0] tb_t_next =
    (tb_t == ST_TI) ? (bs_active ? ST_T1 : ST_TI) :
    (tb_t == ST_T1) ? ST_T2 :
    (tb_t == ST_T2) ? ST_T3 :
    (tb_t == ST_T3) ? (ready_r ? ST_T4 : ST_TW) :
    (tb_t == ST_TW) ? (ready_r ? ST_T4 : ST_TW) :
    /* ST_T4 */       (bs_active ? ST_T1 : ST_TI);

logic [2:0]  lat_type = BS_PASV;
logic [19:0] lat_addr = '0;          // ADDR_O sampled at T1, for the WRITE
logic        lat_ube  = 1'b1;        //   commit only -- reads use it live
logic  [3:0] lat_ps   = 4'h0;

always @(posedge clk) if (ce) begin
    tb_t <= tb_t_next;
    if      (tb_t_next == ST_T1) begin
        lat_type <= BS;
        lat_addr <= ADDR_O;          // <- the port, not a pin latch
        lat_ube  <= UBE_N;
        lat_ps   <= STATUS_O;
    end
    else if (tb_t_next == ST_TI) lat_type <= BS_PASV;
end

// max mode: 000 INTA, 001 IOR, 010 IOW, 011 HALT, 100 CODE, 101 MEMR,
//           110 MEMW, 111 PASV
wire lat_read = (lat_type == 3'b100) || (lat_type == 3'b101) ||
                (lat_type == 3'b001) || (lat_type == 3'b000);
wire lat_memw = (lat_type == 3'b110);

//---------------------------------------------------------------------------
// THE MEMORY.  1 MiB, LFSR-filled, and writes land.
//---------------------------------------------------------------------------
logic [7:0] mem [0:(1<<20)-1];

initial begin
    logic [31:0] s;
    s = seed_of(seed_cfg, 0);
    for (int unsigned a = 0; a < (1<<20); a++) begin
        s = lfsr_next(s);
        mem[a] = s[7:0];
    end
end

localparam bit [7:0] INT_VECTOR = 8'hFF;

function automatic logic [15:0] io_word(input logic [19:0] a);
    logic [31:0] v;
    begin
        v = lfsr_next({12'h0, a} ^ 32'h5A5A_1234);
        io_word = v[15:0];
    end
endfunction

// THE READ PATH.  `ADDR_O` is read LIVE in the data phase -- no latch, no
// half-cycle, no knowledge of when the mux would have turned around.  That is
// the whole of what a de-muxed integrator gains.
wire [19:0] rd_a = ADDR_O;
wire        mem_drive = (tb_t == ST_T2 || tb_t == ST_T3 || tb_t == ST_TW) &&
                        lat_read;

always @(*) begin
    if (!mem_drive)                   DATA_I = 16'h0000;
    else if (lat_type == 3'b000)      DATA_I = {8'h00, INT_VECTOR};
    else if (lat_type == 3'b001)      DATA_I = io_word(rd_a);
    else                              DATA_I = {mem[{rd_a[19:1], 1'b1}],
                                                mem[{rd_a[19:1], 1'b0}]};
end

// THE WRITE PATH.  `DATA_O` is the word, `lat_ube`/A0 select the lanes exactly
// as the bus does.  No turnaround to wait for.
integer n_writes = 0;
always @(posedge clk) if (ce) begin
    if (lat_memw && (tb_t == ST_T3) && ready_r) begin
        n_writes = n_writes + 1;
        if (!lat_addr[0])              mem[lat_addr]              <= DATA_O[7:0];
        if (!lat_ube && !lat_addr[0])  mem[{lat_addr[19:1],1'b1}] <= DATA_O[15:8];
        if (lat_addr[0] && !lat_ube)   mem[lat_addr]              <= DATA_O[15:8];
    end
end

//---------------------------------------------------------------------------
// THE CENSUS.  A run that elaborates and does nothing proves nothing, so the
// harness counts what it drove the core to DO and the gate has bars on it.
//---------------------------------------------------------------------------
integer bs_hist [0:7];
integer qpops = 0, fpops = 0;
integer ps_seen = 0;                     // bitmask of STATUS_O values observed
integer addr_moves = 0;                  // ADDR_O changed between bus cycles

logic [19:0] addr_prev = '0;

initial for (int bi = 0; bi < 8; bi++) bs_hist[bi] = 0;

always @(posedge clk) if (ce) begin
    if (tb_t_next == ST_T1 && bs_active) begin
        bs_hist[BS] = bs_hist[BS] + 1;
        if (ADDR_O != addr_prev) addr_moves = addr_moves + 1;
        addr_prev <= ADDR_O;
    end
    ps_seen = ps_seen | (1 << STATUS_O);
    if (QS != 2'b00) qpops = qpops + 1;
    if (QS == 2'b01) fpops = fpops + 1;
end

//---------------------------------------------------------------------------
// the run
//---------------------------------------------------------------------------
integer clk_n = 0;

initial begin
    l_mem = seed_of(seed_cfg, 1);
    l_rdy = seed_of(seed_cfg, 3);
    l_pin = seed_of(seed_cfg, 4);
end

integer bs_kinds;

always @(posedge clk) begin
    clk_n <= clk_n + 1;
    if (clk_n >= nclocks) begin
        bs_kinds = 0;
        for (int bi = 0; bi < 7; bi++) if (bs_hist[bi] > 0) bs_kinds = bs_kinds + 1;
        $display("CLOCKS %0d", clk_n);
        $write("BS_HIST");
        for (int bi = 0; bi < 8; bi++) $write(" b%0d=%0d", bi, bs_hist[bi]);
        $write("\n");
        $display("BS_KINDS %0d", bs_kinds);
        $display("QPOPS %0d FPOPS %0d", qpops, fpops);
        $display("WRITES %0d", n_writes);
        $display("ADDR_MOVES %0d", addr_moves);
        $display("PS_SEEN %04x", ps_seen[15:0]);
        if (fpops > 0 && bs_kinds >= 4 && n_writes > 0 && addr_moves > 0)
            $display("RESULT OK");
        else
            $display("RESULT FAIL fpops=%0d bs_kinds=%0d writes=%0d moves=%0d",
                     fpops, bs_kinds, n_writes, addr_moves);
        $finish;
    end
end

endmodule
