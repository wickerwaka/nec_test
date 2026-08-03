//============================================================================
//  v30u_eu_cond.svh -- exec_impl.h::cond_true(op.cond).  Sets `taken`.
//  The ALU STATUS LATCH (`stat`) is what the JMP conditions read; the
//  architectural PSW is what [-0A-] / [-0F-] read.
//============================================================================
case (r_cond)
    C_C:      taken = stat[FCY];
    C_NC:     taken = !stat[FCY];
    C_Z:      taken = stat[FZ];
    C_NZ:     taken = !stat[FZ];
    C_OP8B:   taken = op8;
    // F19 -- BOTH COUNTING CONDITIONS READ THE TERMINATOR ONE CLOCK EARLY.
    // `count` is a LIVE BLOCKING variable here: after `count = count - 1` it
    // IS the post-decrement value, which is exactly what the model tests
    // (`m_.count = count - 1; return m_.count != 0;`).  Testing it against 1
    // stops one iteration early -- and at COUNT==1 the two conditions do
    // OPPOSITE wrong things: CNTZ walks one copy too few, REP takes the loop
    // back when the model falls through, so `REP MOVS` with CX==1 ran a SECOND
    // element, issued a second read nobody consumed, and tripped C3's
    // completed-read-store assertion.  This is F13's bug in its third and
    // fourth instance (sec.16's named class).
    C_CNTZ:   begin
                  count = count - 16'd1;
                  taken = (count != 16'd0);
              end
    C_L:      taken = (stat[FS] != stat[FV]);
    C_OP8:    taken = imm8;
    C_ALWAYS: taken = 1'b1;
    C_SIGN:   taken = !sign_neg;
    C_O:      taken = psw[FV];
    C_NS:     taken = !(op8 ? tmpb[7] : tmpb[15]);
    C_REP:    begin
                  count = count - 16'd1;
                  // `++rep_elems_`: from here on this sequence's boundaries are
                  // CHAINED.  Read BEFORE the update, exactly as the model
                  // reads `rep_elems_ >= 2` after its own increment.
                  rep_chained = rep_chain;
                  rep_chain = 1'b1;
                  if (count == 16'd0) taken = 1'b0;      // F19
                  // "REP iterations are individually interruptible": the sample
                  // is `edge - 4` (interrupt_model.md, "REP abort") and the
                  // EDGE is one clock past this row on the FIRST boundary and
                  // two on a chained one (see `irq_rep_1st`/`irq_rep_chn`); the
                  // recognition is LATCHED -- the withdrawal path's own
                  // `0223 JMP INTR` is what reads it back.
                  else if (intr_pending ||
                           (rep_chained ? irq_rep_chn : irq_rep_1st)) begin
                      intr_pending = 1'b1;
                      taken = 1'b0;
                      // ...and the chained boundary's decision edge being one
                      // clock later moves the WHOLE withdrawal with it: the
                      // model's `if (rep_elems_ >= 2) biu_.charge(1)`, which is
                      // what puts the flush at accept+9 instead of edge+9.
                      if (rep_chained) bubble = 1'b1;
                  end
                  else if (rep_test == TEST_Z)
                      taken = (psw[FZ] == rep_pol);
                  else if (rep_test == TEST_CY)
                      taken = (psw[FCY] == rep_pol);
                  else taken = 1'b1;
              end
    C_BUSY:   taken = poll_busy;
    C_INTR:   taken = intr_pending;
    default:  begin                              // C_OPC -- pla_2
                  case (opc_reg[3:0])
                      4'h0: taken = psw[FV];
                      4'h1: taken = !psw[FV];
                      4'h2: taken = psw[FCY];
                      4'h3: taken = !psw[FCY];
                      4'h4: taken = psw[FZ];
                      4'h5: taken = !psw[FZ];
                      4'h6: taken = psw[FCY] || psw[FZ];
                      4'h7: taken = !psw[FCY] && !psw[FZ];
                      4'h8: taken = psw[FS];
                      4'h9: taken = !psw[FS];
                      4'hA: taken = psw[FP];
                      4'hB: taken = !psw[FP];
                      4'hC: taken = (psw[FS] != psw[FV]);
                      4'hD: taken = (psw[FS] == psw[FV]);
                      4'hE: taken = psw[FZ] || (psw[FS] != psw[FV]);
                      default: taken = !psw[FZ] && (psw[FS] == psw[FV]);
                  endcase
              end
endcase
