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
    C_CNTZ:   begin
                  count = count - 16'd1;
                  taken = (count != 16'd1);   // pre-decrement value tested
              end
    C_L:      taken = (stat[FS] != stat[FV]);
    C_OP8:    taken = imm8;
    C_ALWAYS: taken = 1'b1;
    C_SIGN:   taken = !sign_neg;
    C_O:      taken = psw[FV];
    C_NS:     taken = !(op8 ? tmpb[7] : tmpb[15]);
    C_REP:    begin
                  count = count - 16'd1;
                  if (count == 16'd1) taken = 1'b0;
                  else if (intr_pending) taken = 1'b0;
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
