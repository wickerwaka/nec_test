//============================================================================
//
//  v30u_ucrom - the two build-time microcode tables (U0 finding F1).
//
//  The die holds a MATCH PLA feeding a 1028-row microcode ROM.  U0 flattened
//  the 257 activation patterns at BUILD time, which -- F1 -- is TWO tables and
//  not one:
//
//      ucdecode   8192 x 10   {valid, bank[8:0]} indexed by the 13-bit
//                             {page[2:0], opc[7:0], rowgrp[1:0]}
//      ucrom      1028 x 29   the row word, indexed by {bank[8:0], row[1:0]}
//
//  so the RTL carries ZERO match/priority logic.  `bank` re-evaluates only
//  when {page, opc, rowgrp} changes; `row` advances every row.
//
//  THE READ IS COMBINATIONAL, ON PURPOSE.  The sequencer's `upc` is the
//  architectural flop (SS-mapped in v30u_eu.sv); the two lookups then stand on
//  its output exactly as the die's PLA + ROM stand on the micro-address
//  register.  Registering either output would insert a bubble the part does
//  not have: `loc` crosses a rowgrp boundary every four rows WITHOUT a taken
//  jump, so a registered decode would cost a clock there.  (U4 owns the
//  synthesis shape; the `ramstyle` hints below are what Quartus is asked for.)
//
//  Provenance: hdl/rtl/ucore/ucrom.hex / ucdecode.hex, emitted by
//  sw/gen_ucore_tables.py and gated byte-for-byte against the C++ model by
//  sw/check_ucore_tables.py (G0).
//
//============================================================================

module v30u_ucrom #(
    // The tables live next to the RTL.  Simulation runs from the repo ROOT
    // (sw/check_core.py, sw/ulockstep.py); a synthesis project overrides this
    // with its own relative path.
    parameter string HEXDIR = "hdl/rtl/ucore/"
) (
    // 13-bit micro-address {page[2:0], opc[7:0], rowgrp[1:0]}
    input      [12:0] dec_addr,
    output            dec_valid,
    output      [8:0] dec_bank,

    // {bank[8:0], row[1:0]}
    input      [10:0] rom_addr,
    output     [28:0] rom_word
);

(* ramstyle = "M10K" *) reg [9:0]  ucdecode [0:8191];
(* ramstyle = "M10K" *) reg [28:0] ucrom    [0:1027];

initial begin
    $readmemh({HEXDIR, "ucdecode.hex"}, ucdecode);
    $readmemh({HEXDIR, "ucrom.hex"}, ucrom);
end

wire [9:0] dec_w = ucdecode[dec_addr];

assign dec_valid = dec_w[9];
assign dec_bank  = dec_w[8:0];
assign rom_word  = ucrom[rom_addr];

endmodule
