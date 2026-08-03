//============================================================================
//  v30u_eu_iend_late.svh -- the part of `loader_decode`'s per-instruction
//  latch reset that THE POST-`E` ROW STILL READS.
//
//  F22.  In the model the order is fixed and obvious: the post-`E` row runs
//  inside `run_micro`, and only then does `step()` return and the successor's
//  `loader_decode` reset these latches.  In the EU the two land on DIFFERENT
//  edges -- the successor's decode is chained zero-cost into the `E` row's own
//  edge (it must be: `st` has to be S_MODRM/S_NORM_CHG during the decoder's
//  clock or the ModR/M byte is demanded one clock late), while the post-`E`
//  row is F8's one-bit debt, discharged at the top of the NEXT edge.  So the
//  reset arrived FIRST and the post-`E` row read a machine that had already
//  been cleared for its successor:
//
//    `40`  `SIGMA -> M`   wrote nothing   (m_kind cleared)  ax unchanged
//    `9C`  `SIGMA -> SP`  wrote tmpb      (ALU latch reset)  sp unchanged
//    `AA`  `SIGMA -> DI`  same                               di unchanged
//    0225  `PFXCNT -> tmpa`                                  pfxcnt cleared
//
//  These four fields are exactly the ones the post-`E` row reads AND the
//  edge-`c` chain never rewrites (S_TAKE_OPC / S_DECODE / S_DECODE2 write
//  `ld_b`/`op8`/`xop`/`opc_reg`/`ld_hasrm` and nothing here), so deferring them
//  to just after the discharge restores the model's order without moving the
//  decoder's byte-demand schedule by a clock.  The operand BINDING that
//  follows (S_NORM_CHG / the EA states) already runs on the later edge, after
//  the discharge, so it still lands on top of this.
//
//  REGISTERED RESIDUE: a successor that is a PREFIX increments `pfxcnt` in
//  S_DECODE on edge `c`, and this reset then zeroes it on edge `c+1`.  No
//  v0.1 case reaches it (the injected successor is always `90`); it is a real
//  hazard for whole-program replay and is booked, not patched.
//============================================================================
pfxcnt = 8'd0;
m_kind = OK_NONE; r_kind = OK_NONE; wb_kind = OK_NONE;
// ...and the `ALU OPC` permutation base, for the same reason (`40`/`48`, whose
// INC/DEC comes from `opc_base = A_INC`, came out as ADD).
opc_base = 5'd0; opc_from_modrm = 1'b0; modrm_reg = 3'd0;
// the address adder stands on the SIGMA path with its default operation
al_op = A_ADD; al_tmp = 2'd0; al_byte = 1'b0;
al_eaconst = 1'b0; al_adjust = 2'd0; al_bitarm = 1'b0; al_spent = 1'b0;
