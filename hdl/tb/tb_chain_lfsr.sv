//============================================================================
//
//  tb_chain_lfsr -- THE CHAIN-DEPTH FALSIFIER, IN AN ALL-LFSR ENVIRONMENT.
//
//  WHY THIS EXISTS.  `v30u_eu.sv`'s `CHAIN_MAX` is a BOUND ON A CLAIM: no more
//  than N of the model's zero-cost steps ever ride one clock.  Three sources
//  agree the true maximum occupancy is 6 -- `ucore_provenance.md` sec.51.2's
//  transition-graph argument plus its (position, state) census, M72's
//  independent re-derivation of the same graph, and M72's own LFSR harness.
//  **None of those is a gate.**  The gate is the `CHAIN OVERFLOW` $fatal at
//  `v30u_eu.sv:3763`, and a $fatal is only evidence over stimulus that could
//  have fired it.
//
//  The golden suite cannot be that stimulus on its own: it is 347 KNOWN forms.
//  This harness executes ARBITRARY BYTES out of an LFSR memory, with LFSR
//  READY, LFSR INT/NMI/POLL_N, and a CE train whose gaps are LFSR-drawn.  It
//  is the port of `m72_downstream_timing_2026-08-12.md` sec.3 item 1, which
//  that report explicitly offered and which existed in NEITHER repo.
//
//  THE ce/ce_half CONTRACT (USER, Reading B -- UNIVERSAL; CORRECTED
//  2026-08-13).  There is now exactly ONE assumable:
//      (a) `ce` and `ce_half` never coincide.
//  Clause (b) ("
//  >= 1 idle cycle between assertions") is DELETED -- *"They do not need to be
//  separated by a clock, they just cannot be enabled at the same time"* (USER
//  RULING 2026-08-13).
//  **No div-based derivation anywhere.**  There is no `div` in this file.  The
//  train below asserts `ce`, idles for h in {0, 1}, asserts `ce_half`, then
//  idles for g in [0, 7] before the next `ce`; both gaps are LFSR-drawn.
//  h = g = 0 is the contract's MINIMUM pattern -- `ce` every TWO fabric clocks,
//  M72's catch-up-burst rate -- and reaching it is a REGISTERED bar (H-2),
//  because a train that never reaches the minimum is our div-8 train wearing a
//  disguise.
//
//  Clause (a) is ASSERTED here (`ce_coincide`) AND, since 2026-08-13, inside
//  `v30_core` itself, where it `$fatal`s -- neither is assumed.
//
//  WHAT IT REPORTS, on $finish:
//      CHAIN_DEPTH_MAX <n> entry_st <s>    (the RTL's own +chaindepth observer)
//      LFSR_SIG <64 hex>                   rolling signature over every core
//                                          output on every fabric clock
//      CE_GAPS g0=<n> g1=<n> ...           the train's own census
//      CE_COINCIDE <n>                     clause (a); must be 0
//      RESULT OK | RESULT FAIL <why>
//
//  A `CHAIN OVERFLOW` does not need reporting from here: it is a $fatal in the
//  DUT and it takes the process down with a non-zero status.  That is the
//  point -- the gate cannot be talked out of it by this file.
//
//  NON-VACUITY.  `sw/chain_lfsr_gate.py --nonvacuity` copies `hdl/rtl/ucore/`
//  to a scratch directory, rewrites `CHAIN_MAX` there to `4'd4` -- BELOW the
//  observed maximum -- builds THAT tree against this same TB and REQUIRES the
//  $fatal.  **The shipped RTL is not touched and carries no test hook**: a
//  `CHAIN_MAX_OVERRIDE` ifdef would be a second definition of the bound living
//  in the file the bound is declared in.  An assertion that cannot fire is not
//  evidence, and a hook that can move the bound is not a bound.
//
//  NO CORRECTNESS CLAIM IS MADE HERE.  This harness does not know what the
//  right answer is and never compares against silicon.  It makes exactly two
//  claims: the chain never overflows, and the output signature does not move
//  when `CHAIN_MAX` does.  Everything architectural is gated elsewhere.
//
//============================================================================
`timescale 1ns/1ps

module tb_chain_lfsr;

//---------------------------------------------------------------------------
// the fabric clock -- FREE-RUNNING.  The core advances on CE only.
//---------------------------------------------------------------------------
logic clk = 0;
initial forever #5 clk = ~clk;

//---------------------------------------------------------------------------
// run configuration
//---------------------------------------------------------------------------
integer      nclocks = 400000;      // fabric clocks to run
logic [31:0] seed_cfg = 32'h1;
integer      verbose = 0;

initial begin
    if (!$value$plusargs("clocks=%d", nclocks)) nclocks = 400000;
    if (!$value$plusargs("seed=%h", seed_cfg))  seed_cfg = 32'h1;
    if (!$value$plusargs("verbose=%d", verbose)) verbose = 0;
end

//---------------------------------------------------------------------------
// THE LFSR BANK.  Five independent 32-bit Galois LFSRs (poly 0xA3000000),
// each seeded from `seed_cfg` through a different odd multiplier so that two
// seeds do not share a stream.  Every environment decision in this file comes
// out of one of them and out of nothing else.
//
//   stream 0 memory initialisation -- consumed by the `initial` that fills
//            `mem`, off its own local `seed_of(seed_cfg, 0)`.  It is a
//            one-shot at time 0, so it needs no persistent register.
//   L_CE     the CE train's gap
//   L_RDY    READY
//   L_PIN    INT / NMI / POLL_N
//   L_MEM, L_AUX  declared, seeded, and DELIBERATELY UNUSED -- spare streams,
//            so that adding a new environment decision later never has to
//            re-tap one of the three above and silently move every signature.
//---------------------------------------------------------------------------
localparam logic [31:0] LFSR_POLY = 32'hA3000000;

function automatic logic [31:0] lfsr_next(input logic [31:0] s);
    lfsr_next = {1'b0, s[31:1]} ^ (s[0] ? LFSR_POLY : 32'h0);
endfunction

function automatic logic [31:0] seed_of(input logic [31:0] s, input int k);
    logic [31:0] v;
    begin
        v = s * (32'h9E3779B1 + 32'd2 * k) + 32'h1234567 * (k + 1);
        seed_of = (v == 32'h0) ? 32'hACE1_0000 + k : v;
    end
endfunction

logic [31:0] l_mem, l_ce, l_rdy, l_pin, l_aux;

//---------------------------------------------------------------------------
// THE CE TRAIN.  Reading B and nothing narrower.
//
// ⚠ CORRECTED 2026-08-13, THEN CORRECTED AGAIN THE SAME DAY.  READ BOTH.
//
// FIRST correction: this train had asserted `ce_half` on the fabric clock
// IMMEDIATELY AFTER `ce` at every gap draw, which violated the then-standing
// clause (b) ("
// >= 1 idle cycle between assertions"), so it was widened to
// `ce@k, ce_half@k+2, ce@k+4`.
//
// SECOND correction -- USER RULING 2026-08-13, verbatim: *"They do not need to
// be separated by a clock, they just cannot be enabled at the same time."*
// **CLAUSE (b) IS DELETED**, and with it the `ce -> ce >= 4` arithmetic that
// was derived from it.  The train the FIRST correction removed was legal all
// along; the widening was over-constraint, not conservatism, and this harness
// spent it drawing gaps the contract never required.
//
//   phase 0 : assert ce            (one fabric clock); draw the two gaps
//   phase 1 : idle for h clocks, h = L_CE[3] in {0, 1}
//   phase 2 : assert ce_half       (never coincident -- the ONE premise)
//   phase 3 : idle for g clocks,   g = L_CE[2:0] in [0, 7]
//
// `h == 0 && g == 0` is `ce@k, ce_half@k+1, ce@k+2` -- **THE CONTRACT'S TRUE
// MINIMUM, and M72's catch-up burst rate** (`m72_downstream_timing_
// 2026-08-12.md` §1: the phases strictly alternate one per fabric clock while
// the chaser is behind).  Reaching it stays a REGISTERED bar (H-2): a train
// that never reaches the minimum is our div-8 train wearing a disguise.
// Drawing BOTH gaps is what makes the minimum reachable at all -- with the
// head gap pinned the harness would merely have swapped one fixed phase
// relationship (2) for another (0).
//
// ⚠ THE PER-SEED SIGNATURES MOVE, AND THAT IS REGISTERED, NOT DISCOVERED.
// The gate accumulates over every core output on EVERY FABRIC CLOCK, so a
// change of train period changes the accumulation.  What may NOT move is the
// per-seed `live` bus census -- that is the actual invariant, and it is
// checked (`ce_contract_correction_prereg_2026-08-13.md` §5, P-3).
//---------------------------------------------------------------------------
logic       ce      = 1'b0;
logic       ce_half = 1'b0;
integer     ce_phase = 0;
integer     ce_gap   = 0;
integer     gap_hist [0:7];
integer     ce_coincide = 0;
integer     ce_count = 0;

initial begin
    for (int gi = 0; gi < 8; gi++) gap_hist[gi] = 0;
end

always @(posedge clk) begin
    // defaults: both low
    ce      <= 1'b0;
    ce_half <= 1'b0;
    case (ce_phase)
        0: begin
            ce        <= 1'b1;
            l_ce       = lfsr_next(l_ce);
            ce_gap    <= l_ce[2:0];    // ce_half -> ce idle clocks, [0, 7]
            gap_hist[l_ce[2:0]] = gap_hist[l_ce[2:0]] + 1;
            // ce -> ce_half idle clocks, {0, 1}.  0 is the contract minimum.
            ce_phase  <= l_ce[3] ? 1 : 2;
        end
        1: begin                       // the LFSR-drawn head idle clock
            ce_phase <= 2;
        end
        2: begin
            ce_half  <= 1'b1;
            ce_phase <= (ce_gap == 3'd0) ? 0 : 3;
        end
        default: begin                 // the LFSR-drawn tail idle
            if (ce_gap <= 1) ce_phase <= 0;
            else             ce_gap   <= ce_gap - 1;
        end
    endcase
end

// clause (a), ASSERTED and not assumed
always @(posedge clk) begin
    if (ce && ce_half) ce_coincide = ce_coincide + 1;
    if (ce) ce_count = ce_count + 1;
end

// ...and the contract itself is asserted INSIDE `v30_core` since the
// 2026-08-13 correction (`hdl/rtl/ucore/v30_core.sv`, `ifndef SYNTHESIS`,
// `$fatal` on C-a and on S-1), which the `dut` instance below inherits.  The
// shared `hdl/tb/ce_contract_check.sv` is RETIRED: its gap clauses enforced a
// premise the correction deleted, and its C-a clause is superseded by a check
// that every instantiation of the core carries.  `ce_coincide` is kept: it is
// this harness's own reported census and the gate reads it.

//---------------------------------------------------------------------------
// reset
//---------------------------------------------------------------------------
logic reset = 1'b1;
integer reset_ce = 0;
always @(posedge clk) if (ce) begin
    if (reset_ce < 24) reset_ce <= reset_ce + 1;
    else               reset    <= 1'b0;
end

//---------------------------------------------------------------------------
// LFSR pins.  INT/NMI are deliberately LOW-DUTY: a pin that is high most of
// the time keeps the core in vector entry and never lets an instruction
// stream develop, and the chain's deep positions are reached by DECODE, not
// by interrupts.  POLL_N is drawn flat.
//---------------------------------------------------------------------------
logic pin_int = 1'b0, pin_nmi = 1'b0, pin_poll_n = 1'b0;
always @(posedge clk) if (ce) begin
    l_pin      = lfsr_next(l_pin);
    pin_int   <= (l_pin[7:0]  == 8'h00);          // ~1/256 CE clocks
    pin_nmi   <= (l_pin[19:8] == 12'h000);        // ~1/4096 CE clocks
    pin_poll_n<= l_pin[20];
end

//---------------------------------------------------------------------------
// LFSR READY.  A free-running random READY is a SUPERSET of any wait
// generator: the core is entitled to see the pin low for any number of clocks
// and must simply wait.  It is redrawn on every CE clock.
//---------------------------------------------------------------------------
logic ready_r = 1'b1;
always @(posedge clk) if (ce) begin
    l_rdy   = lfsr_next(l_rdy);
    ready_r <= (l_rdy[1:0] != 2'b00);             // ~75 % ready
end

//---------------------------------------------------------------------------
// pins
//---------------------------------------------------------------------------
wire [19:0] AD;
wire [19:0] AD_OE;
wire  [1:0] QS;
wire  [2:0] BS;
wire        RD_N, UBE_N, BUSLOCK_N;
wire [15:0] SS_RDATA;
wire        SS_ERR, SS_BUS_QUIET;

v30_core dut (
    .CLK       (clk),
    .CE        (ce),
    .CE_HALF   (ce_half),
    .RESET     (reset),
    .READY     (ready_r),
    .INT       (pin_int),
    .NMI       (pin_nmi),
    .POLL_N    (pin_poll_n),
    .AD        (AD),
    .AD_OE     (AD_OE),
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
// THE BUS TRACKER.  Identical in shape to `tb_v30_core.sv`'s (:290-337): the
// T-state is RECONSTRUCTED from BS/READY, exactly as `nec_bus` does it in
// fabric, and the address is latched at the T1 negedge.  Nothing DUT-internal
// is read anywhere in this file.
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
logic [19:0] lat_addr = '0;
logic        lat_ube  = 1'b1;

always @(posedge clk) if (ce) begin
    tb_t <= tb_t_next;
    if      (tb_t_next == ST_T1) lat_type <= BS;
    else if (tb_t_next == ST_TI) lat_type <= BS_PASV;
end

always @(negedge clk) if (ce_half && tb_t == ST_T1) begin
    lat_addr <= AD;
    lat_ube  <= UBE_N;
end

// bus type encodings (max mode): 000 INTA, 001 IOR, 010 IOW, 011 HALT,
// 100 CODE, 101 MEMR, 110 MEMW, 111 PASV
wire lat_read = (lat_type == 3'b100) || (lat_type == 3'b101) ||
                (lat_type == 3'b001) || (lat_type == 3'b000);
wire lat_memw = (lat_type == 3'b110);

//---------------------------------------------------------------------------
// THE LFSR MEMORY.  1 MiB, initialised from L_MEM, and WRITES LAND -- so a
// store followed by a fetch of the same address reads back what was stored,
// which is what lets a random byte stream be self-consistent instead of
// merely noisy.
//
// INTA returns 0xFF (the harness CFG default, `tb_v30_core.sv:319`), IOR
// returns LFSR-of-address so a port read is not a constant.
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

wire [19:0] lat_a  = lat_addr;
wire        mem_drive = (tb_t == ST_T2 || tb_t == ST_T3 || tb_t == ST_TW) &&
                        lat_read;

function automatic logic [15:0] io_word(input logic [19:0] a);
    logic [31:0] v;
    begin
        v = lfsr_next({12'h0, a} ^ 32'h5A5A_1234);
        io_word = v[15:0];
    end
endfunction

wire [15:0] mem_word = (lat_type == 3'b000) ? {8'h00, INT_VECTOR}
                     : (lat_type == 3'b001) ? io_word(lat_a)
                     : {mem[{lat_a[19:1], 1'b1}], mem[{lat_a[19:1], 1'b0}]};

assign AD[15:0]  = mem_drive ? mem_word : 16'hzzzz;
assign AD[19:16] = 4'hz;

// the write commit: the data phase of a MEMW cycle.  `lat_ube` / A0 select
// the lanes exactly as the bus does.
always @(posedge clk) if (ce) begin
    if (lat_memw && (tb_t == ST_T3) && ready_r) begin
        if (!lat_a[0])              mem[lat_a]              <= AD[7:0];
        if (!lat_ube && !lat_a[0])  mem[{lat_a[19:1],1'b1}] <= AD[15:8];
        if (lat_a[0] && !lat_ube)   mem[lat_a]              <= AD[15:8];
    end
end

//---------------------------------------------------------------------------
// THE OUTPUT SIGNATURE.  Every core output, every FABRIC clock (not every CE
// clock -- a change that moved a value onto a CE-low clock would be invisible
// otherwise).  AD is masked by AD_OE so an undriven lane contributes 0 rather
// than X: `z & 0` is 0 and the signature stays two-state.
//
// ⚠ THE FIRST FORM OF THIS BLOCK WAS DEGENERATE AND THE HARNESS CAUGHT IT.
// It was `sig <= rotl1(sig) ^ rotl32(sig) ^ data`.  Both terms are rotations,
// so the state map is the GF(2) polynomial `R + R^32 = R(1 + R^31)`, which
// shares large factors with `R^64 + 1` and is therefore **SINGULAR**: injected
// data decays into the kernel.  Measured, it returned the IDENTICAL 64-bit
// value `a2f01e4ce7100a3b` on four seeds whose `BS_HIST` differed by a factor
// of five (`b5 = 890` vs `171`).
//
// The form below is a Fibonacci LFSR step -- a shift with feedback into bit 0,
// x^64 + x^63 + x^61 + x^60 -- which is a companion matrix with a non-zero
// constant term and therefore INVERTIBLE.  Data is XORed on top.
//
// AND THE SIGNATURE CARRIES ITS OWN FALSIFIER, which is what found the first
// form: `chain_lfsr_gate.py` requires the signatures to **DIFFER across
// SEEDS** (different stimulus must produce a different trace) at the same time
// as it requires them to **MATCH across CHAIN_MAX values** (the same stimulus
// must produce the same trace).  A signature that only satisfies the second is
// a constant, and a constant proves nothing.
//---------------------------------------------------------------------------
wire [19:0] ad_obs = AD & AD_OE;

wire [63:0] sig_data = {12'h0, SS_BUS_QUIET, SS_ERR, SS_RDATA,
                        BUSLOCK_N, UBE_N, RD_N, BS, QS, ad_obs};

logic [63:0] sig = 64'h0;
wire sig_fb = sig[63] ^ sig[62] ^ sig[60] ^ sig[59];
always @(posedge clk) sig <= {sig[62:0], sig_fb} ^ sig_data;

//---------------------------------------------------------------------------
// THE STIMULUS-LIVENESS CENSUS.  A depth gate that passes on a DEAD core is
// the vacuous-gate pattern: `CHAIN OVERFLOW` cannot fire in a machine that is
// not executing.  So the harness counts what it drove the core to DO, and the
// gate has bars on these numbers as well as on the depth.
//
//   BS_HIST    bus cycles STARTED, by max-mode status (INTA/IOR/IOW/HALT/
//              CODE/MEMR/MEMW)
//   QPOPS      queue pops (QS != 0) -- instruction bytes actually consumed
//   FPOPS      first-byte pops (QS == 1) -- instructions actually STARTED
//---------------------------------------------------------------------------
integer bs_hist [0:7];
integer qpops = 0;
integer fpops = 0;

initial for (int bi = 0; bi < 8; bi++) bs_hist[bi] = 0;

always @(posedge clk) if (ce) begin
    if (tb_t_next == ST_T1 && bs_active) bs_hist[BS] = bs_hist[BS] + 1;
    if (QS != 2'b00) qpops = qpops + 1;
    if (QS == 2'b01) fpops = fpops + 1;
end

//---------------------------------------------------------------------------
// the run
//---------------------------------------------------------------------------
integer clk_n = 0;

initial begin
    l_mem = seed_of(seed_cfg, 1);
    l_ce  = seed_of(seed_cfg, 2);
    l_rdy = seed_of(seed_cfg, 3);
    l_pin = seed_of(seed_cfg, 4);
    l_aux = seed_of(seed_cfg, 5);
end

always @(posedge clk) begin
    clk_n <= clk_n + 1;
    if (clk_n >= nclocks) begin
        $display("CLOCKS %0d", clk_n);
        $display("CE_CLOCKS %0d", ce_count);
        $display("CE_COINCIDE %0d", ce_coincide);
        $write("CE_GAPS");
        for (int gi = 0; gi < 8; gi++) $write(" g%0d=%0d", gi, gap_hist[gi]);
        $write("\n");
        $write("BS_HIST");
        for (int bi = 0; bi < 8; bi++) $write(" b%0d=%0d", bi, bs_hist[bi]);
        $write("\n");
        $display("QPOPS %0d FPOPS %0d", qpops, fpops);
        $display("LFSR_SIG %016h", sig);
        // CHAIN_DEPTH_MAX is printed by the DUT's own +chaindepth observer.
        if (ce_coincide != 0)
            $display("RESULT FAIL ce_coincide=%0d", ce_coincide);
        else if (gap_hist[0] < 1000)
            $display("RESULT FAIL min_gap_reached=%0d", gap_hist[0]);
        else
            $display("RESULT OK");
        $finish;
    end
end

endmodule
