//============================================================================
//
//  tb_v30_core - golden-trace replay testbench for the v30_core CPU
//
//  Batch-driven: sw/check_core.py converts SingleStepTests-format cases
//  (tests/v30/v0.1) into a text batch file, this TB replays each case on
//  the core and dumps one raw record per CPU cycle plus the architectural
//  state at the second instruction-boundary (F) queue pop. The Python
//  driver synthesizes 11-column cycle rows from the records (with the
//  same logic as the suite emitter) and diffs them against the case.
//
//  The TB treats the core as a black box on its chip pins: T-states, bus
//  cycles and latched addresses are reconstructed from BS/AD/UBE_N alone,
//  exactly as hdl/rtl/nec_bus.sv does with the real part. Only state
//  injection/observation uses the V30_BACKDOOR ports (verification-only).
//
//  Batch file grammar (all values hex, whitespace-separated):
//    <ncases>
//    per case:
//      <idx>
//      <ax> <cx> <dx> <bx> <sp> <bp> <si> <di> <es> <cs> <ss> <ds>
//      <ip> <flags>
//      <qlen> <q0> <q1> <q2> <q3> <q4> <q5> <fetch_ip>
//      <nram>  { <addr20> <byte> } * nram
//      <max_cycles>
//
//  Output stream:
//      = <idx>
//      r <t> <bs> <qs> <ube> <addr20> <data16> <ps>     (one per cycle)
//      f <ax> ... <flags>                               (state at 2nd F pop)
//      .
//
//  Build: sw/check_core.py --build (Verilator --binary --timing
//  -DV30_BACKDOOR over this file plus hdl/rtl/core/*.sv)
//
//============================================================================

`timescale 1ns/1ps

module tb_v30_core;

localparam bit [2:0] BS_PASV = 3'b111;

localparam bit [2:0] ST_TI = 3'd0;
localparam bit [2:0] ST_T1 = 3'd1;
localparam bit [2:0] ST_T2 = 3'd2;
localparam bit [2:0] ST_T3 = 3'd3;
localparam bit [2:0] ST_TW = 3'd4;
localparam bit [2:0] ST_T4 = 3'd5;

logic clk = 0;
initial forever #5 clk = ~clk;

logic reset = 1;

// backdoor
logic         bkd_load = 0;
logic [223:0] bkd_regs = '0;
logic  [47:0] bkd_queue = '0;
logic   [2:0] bkd_qlen = '0;
logic  [15:0] bkd_fetch_ip = '0;
logic         scr_en = 0;
logic   [1:0] scr_qop = 2'b00;
wire  [223:0] dbg_regs;
wire          dbg_first_pop;

// pins
wire [19:0] AD;
wire  [1:0] QS;
wire  [2:0] BS;
wire        RD_N, UBE_N, BUSLOCK_N;

v30_core dut (
    .CLK       (clk),
    .RESET     (reset),
    .READY     (1'b1),
    .INT       (1'b0),
    .NMI       (1'b0),
    .POLL_N    (1'b1),
    .AD        (AD),
    .QS        (QS),
    .BS        (BS),
    .RD_N      (RD_N),
    .UBE_N     (UBE_N),
    .BUSLOCK_N (BUSLOCK_N),
    .bkd_load  (bkd_load),
    .bkd_regs  (bkd_regs),
    .bkd_queue (bkd_queue),
    .bkd_qlen  (bkd_qlen),
    .bkd_fetch_ip (bkd_fetch_ip),
    .scr_en    (scr_en),
    .scr_qop   (scr_qop),
    .dbg_regs  (dbg_regs),
    .dbg_first_pop (dbg_first_pop)
);

//----------------------------------------------------------------------------
// behavioral memory: 64 KB mirrored across the 1 MB space (like test_mem)
//----------------------------------------------------------------------------
logic [7:0] mem [0:65535];

// per-case undo log (initial-ram load + CPU writes), restored last-first
logic [15:0] undo_addr [$];
logic  [7:0] undo_val  [$];
logic        case_active = 0;

//----------------------------------------------------------------------------
// pin observer: T-state tracking from BS, like nec_bus
//----------------------------------------------------------------------------
logic [2:0] tb_t = ST_TI;
wire        bs_active = BS != BS_PASV;

wire [2:0] tb_t_next =
    (tb_t == ST_TI) ? (bs_active ? ST_T1 : ST_TI) :
    (tb_t == ST_T1) ? ST_T2 :
    (tb_t == ST_T2) ? ST_T3 :
    (tb_t == ST_T3) ? ST_T4 :          // READY tied high: no Tw
    (tb_t == ST_TW) ? ST_T4 :
    /* ST_T4 */       (bs_active ? ST_T1 : ST_TI);

logic  [2:0] lat_type = BS_PASV;
logic [19:0] lat_addr = '0;
logic        lat_ube  = 1'b1;

wire lat_read  = lat_type == 3'b100 || lat_type == 3'b101 ||
                 lat_type == 3'b001 || lat_type == 3'b000;
wire lat_write = lat_type == 3'b110 || lat_type == 3'b010;

// memory read drive during T2/T3 of read cycles (nec_bus-equivalent)
wire        mem_drive = (tb_t == ST_T2 || tb_t == ST_T3) && lat_read;
wire [15:0] mem_word  = {mem[{lat_addr[15:1], 1'b1}],
                         mem[{lat_addr[15:1], 1'b0}]};
assign AD[15:0] = mem_drive ? mem_word : 16'hzzzz;

// address/UBE latch at the falling edge of T1 (address phase)
always @(negedge clk) begin
    if (tb_t == ST_T1) begin
        lat_addr <= AD;
        lat_ube  <= UBE_N;
    end
end

// composed bus value with float retention (protocol-inferred drive)
logic [19:0] hold = '0;
wire core_addr_drive = (bs_active && (tb_t == ST_T4 || tb_t == ST_TI)) ||
                       tb_t == ST_T1;
wire cycle_live      = tb_t != ST_TI && lat_type != BS_PASV;
wire core_ps_drive   = cycle_live && (tb_t == ST_T2 || tb_t == ST_T3 ||
                                      tb_t == ST_TW || tb_t == ST_T4);
wire core_data_drive = core_ps_drive && lat_write;

wire [15:0] eff_lo = (core_addr_drive || core_data_drive || mem_drive)
                     ? AD[15:0] : hold[15:0];
wire  [3:0] eff_hi = (core_addr_drive || core_ps_drive)
                     ? AD[19:16] : hold[19:16];

// mid-cycle (address-phase) sample of the composed bus
logic [19:0] ad_mid = '0;
always @(negedge clk) ad_mid <= {eff_hi, eff_lo};

//----------------------------------------------------------------------------
// per-cycle bookkeeping at the end of each cycle
//----------------------------------------------------------------------------
integer fo = 0;
logic   recording = 0;
integer fcount = 0;
logic [223:0] fin_regs = '0;

always @(posedge clk) begin
    if (!reset) begin
        // record for the cycle just ending (pre-edge values throughout)
        if (recording && fo != 0)
            $fdisplay(fo, "r %0d %0d %0d %0d %05x %04x %01x",
                      tb_t, BS, QS, UBE_N, ad_mid, eff_lo, eff_hi);
        if (recording && QS == 2'b01) begin
            fcount <= fcount + 1;
            if (fcount == 1) fin_regs <= dbg_regs;  // state at the 2nd F pop
        end

        // observer FSM / cycle-type latch
        tb_t <= tb_t_next;
        if (tb_t_next == ST_T1) lat_type <= BS;
        else if (tb_t_next == ST_TI) lat_type <= BS_PASV;

        hold <= {eff_hi, eff_lo};

        // apply CPU writes at the end of the first T3 (as nec_bus does)
        if (tb_t == ST_T3 && lat_write && case_active) begin
            if (!lat_addr[0]) begin
                undo_addr.push_back(lat_addr[15:0]);
                undo_val.push_back(mem[lat_addr[15:0]]);
                mem[lat_addr[15:0]] <= AD[7:0];
                if (!lat_ube) begin
                    undo_addr.push_back(lat_addr[15:0] + 16'd1);
                    undo_val.push_back(mem[lat_addr[15:0] + 16'd1]);
                    mem[lat_addr[15:0] + 16'd1] <= AD[15:8];
                end
            end else if (!lat_ube) begin
                undo_addr.push_back(lat_addr[15:0]);
                undo_val.push_back(mem[lat_addr[15:0]]);
                mem[lat_addr[15:0]] <= AD[15:8];
            end
        end
    end else begin
        tb_t     <= ST_TI;
        lat_type <= BS_PASV;
        hold     <= '0;
        fcount   <= 0;
    end
end

//----------------------------------------------------------------------------
// batch runner
//----------------------------------------------------------------------------
string batch_path, out_path;
integer fi, ncases, nram, maxcyc, idx, cyc;
logic [15:0] rv [0:13];
integer i, k, rc;
logic [31:0] t32, t32b;

task automatic read_hex(output logic [31:0] v);
    logic [31:0] t;
    rc = $fscanf(fi, "%h", t);
    if (rc != 1) begin
        $display("FATAL: batch parse error");
        $finish;
    end
    v = t;
endtask

initial begin
    if (!$value$plusargs("batch=%s", batch_path)) batch_path = "batch.txt";
    if (!$value$plusargs("out=%s", out_path))     out_path = "core_out.txt";
    fi = $fopen(batch_path, "r");
    fo = $fopen(out_path, "w");
    if (fi == 0 || fo == 0) begin
        $display("FATAL: cannot open %s / %s", batch_path, out_path);
        $finish;
    end

    for (i = 0; i < 65536; i++) mem[i] = 8'h90;

    read_hex(t32); ncases = int'(t32);

    repeat (4) @(posedge clk);

    for (k = 0; k < ncases; k++) begin
        read_hex(t32); idx = int'(t32);
        for (i = 0; i < 14; i++) begin
            read_hex(t32); rv[i] = t32[15:0];
        end
        read_hex(t32); bkd_qlen = t32[2:0];
        for (i = 0; i < 6; i++) begin
            read_hex(t32); bkd_queue[i*8 +: 8] = t32[7:0];
        end
        read_hex(t32); bkd_fetch_ip = t32[15:0];
        read_hex(t32); nram = int'(t32);
        for (i = 0; i < nram; i++) begin
            read_hex(t32);
            read_hex(t32b);
            undo_addr.push_back(t32[15:0]);
            undo_val.push_back(mem[t32[15:0]]);
            mem[t32[15:0]] = t32b[7:0];
        end
        read_hex(t32); maxcyc = int'(t32);

        for (i = 0; i < 14; i++) bkd_regs[i*16 +: 16] = rv[i];

        // hold the core in reset, inject state
        reset = 1;
        @(posedge clk);
        bkd_load = 1;                 // held until release so the reset
        repeat (2) @(posedge clk);    // branch keeps the injected state
        cyc = 0;
        case_active = 1;
        $fdisplay(fo, "= %0d", idx);
        @(negedge clk);
        reset = 0;
        bkd_load = 0;
        recording = 1;
        // (the first posedge after release emits one benign pre-window row)
        while (fcount < 2 && cyc < maxcyc) begin
            @(posedge clk);
            cyc = cyc + 1;
        end
        repeat (2) @(posedge clk);    // flush the F#1 row itself
        recording = 0;
        case_active = 0;
        $fdisplay(fo, "f %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x %04x",
                  fin_regs[15:0],    fin_regs[31:16],  fin_regs[47:32],
                  fin_regs[63:48],   fin_regs[79:64],  fin_regs[95:80],
                  fin_regs[111:96],  fin_regs[127:112],fin_regs[143:128],
                  fin_regs[159:144], fin_regs[175:160],fin_regs[191:176],
                  fin_regs[207:192], fin_regs[223:208]);
        $fdisplay(fo, ".");

        // revert memory (last-first)
        reset = 1;
        while (undo_addr.size() > 0) begin
            logic [15:0] ua;
            logic [7:0]  uv;
            ua = undo_addr.pop_back();
            uv = undo_val.pop_back();
            mem[ua] = uv;
        end
        @(posedge clk);
    end

    $fclose(fo);
    $fclose(fi);
    $display("DONE %0d cases", ncases);
    $finish;
end

// watchdog
initial begin
    #1s;
    $display("FATAL: timeout");
    $finish;
end

wire _unused = &{1'b0, RD_N, BUSLOCK_N, dbg_first_pop, scr_en, scr_qop};

endmodule
