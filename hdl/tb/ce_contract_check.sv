//============================================================================
//  ce_contract_check -- THE ce/ce_half PORTABILITY CONTRACT, AS A GATE
//
//  WHY THIS FILE EXISTS.  On 2026-08-13 the `t1_half2` posedge wave was
//  reverted by ONE ladder leg, and the leg was the instrument: `check_core.py`
//  -- the scorer for all 169,000 golden cases, the four HLT sweeps, the `evt`
//  cells and `ulockstep` -- ran the core at `--ce-div 1`, where
//  `tb_v30_core` asserts CE and CE_HALF ON THE SAME CLOCK.  That is exactly
//  what premise C-a forbids.  The core had been scored outside its own
//  declared operating contract since the contract was written, and NOTHING
//  SAW IT, because a comment is not a gate.
//  (`docs/notes/t1_half2_posedge_results_2026-08-13.md` sec.0/sec.5.)
//
//  THE CONTRACT.  USER RULING, 2026-08-12, verbatim, quoted in
//  `hdl/nec_test.sdc`:
//
//    "With respect to ce/ce_half, you are not allowed to make assumptions
//     based on how you are currently setting those clock enables. All you can
//     assume is the ce and ce_half will not be asserted at the same time and
//     there will be a one cycle gap between each assertion."
//
//  As `nec_test.sdc` states it, and as its arc arithmetic uses it:
//
//    C-a  `ce` and `ce_half` are never asserted on the same clock.
//    C-b  successive enable assertions are >= 2 clocks apart -- i.e. at least
//         ONE IDLE fabric clock between any two assertions, of either enable.
//         (The SDC's own derivation `ce -> ce_half  launch n+1, latch n+2.5`
//         is only true if the next assertion after a `ce` in cycle n is at
//         cycle n+2 at the earliest.)
//    C-c  `ce -> ce` is >= 4 clocks, because the core REQUIRES at least one
//         `ce_half` between consecutive `ce`s: `ce_half` gates `t1_half2`,
//         which gates `ad_oe_data`, so a `ce`-to-`ce` with no `ce_half`
//         between them drives the wrong thing on AD for a whole bus cycle.
//         The SDC names exactly this as C-c's falsifier.
//
//  ALL THREE ARE $fatal HERE, NOT $error: a train that leaves the envelope has
//  invalidated every row downstream of it, so continuing would produce a
//  SCORED NUMBER taken outside the contract -- which is the thing that
//  happened.  The 1:1 trap can never silently return.
//
//  NON-VACUITY.  The registered demonstration is a scratch copy of the TB with
//  its `ce_div` floor removed, driven at `+ce_div=1` (C-a fires) and
//  `+ce_div=2` (C-b fires), each required to exit non-zero.  An assertion that
//  cannot fire is not evidence.
//
//  SCOPE.  Simulation only.  Instantiated in `tb_v30_core` (its own train),
//  `tb_sys` (the real integration's `nec_bus` train) and `tb_chain_lfsr` (the
//  LFSR-gap train).  Both QSFs set `VERILOG_MACRO "SYNTHESIS=1"`, and this
//  file is in no synthesis file list in any case.
//============================================================================
`ifndef SYNTHESIS
`timescale 1ns/1ps

module ce_contract_check #(parameter string WHO = "?") (
    input logic clk,
    input logic ce,
    input logic ce_half
);

// idle fabric clocks observed since the last assertion of EITHER enable.
// Starts large so the first assertion of a run is never reported.
integer idle_since = 32'd1000;
// has a `ce_half` been seen since the last `ce`?  Starts asserted so the run's
// first `ce` is never reported.
logic   half_since_ce = 1'b1;

// census, for a caller that wants to know the train was actually exercised
integer ce_n = 0, ce_half_n = 0;

always @(posedge clk) begin
    // ---- C-a ---------------------------------------------------------
    if (ce && ce_half)
        $fatal(1, "ce_contract_check[%s]: C-a VIOLATED at %0t -- `ce` and `ce_half` asserted on the SAME fabric clock.  1:1 is an unsupported mode (USER RULING 2026-08-13); see hdl/nec_test.sdc and docs/notes/ce_contract_reland_prereg_2026-08-13.md.",
               WHO, $time);

    // ---- C-c ---------------------------------------------------------
    if (ce && !half_since_ce)
        $fatal(1, "ce_contract_check[%s]: C-c VIOLATED at %0t -- two `ce`s with NO `ce_half` between them.  `ce_half` gates t1_half2, which gates ad_oe_data; the BIU drives the wrong thing on AD for a whole bus cycle.",
               WHO, $time);

    // ---- C-b ---------------------------------------------------------
    if (ce || ce_half) begin
        if (idle_since < 1)
            $fatal(1, "ce_contract_check[%s]: C-b VIOLATED at %0t -- enable assertions on ADJACENT fabric clocks (%0d idle clocks between them; the contract requires >= 1).",
                   WHO, $time, idle_since);
        idle_since <= 0;
    end else begin
        idle_since <= idle_since + 1;
    end

    if (ce_half)     half_since_ce <= 1'b1;
    else if (ce)     half_since_ce <= 1'b0;

    if (ce)      ce_n      <= ce_n + 1;
    if (ce_half) ce_half_n <= ce_half_n + 1;
end

endmodule
`endif
