//============================================================================
//  v30u_eu_wd1.svh -- exec_impl.h::wr_dst1(c, v1, bsrc1), verbatim.
//  Inputs: `e_d1` (the row's Dest1 field), `v1`, `b1` (the byte-source flag).
//============================================================================
case (e_d1)
    5'd0, 5'd1, 5'd2, 5'd3: sreg[e_d1[1:0]] = v1;
    5'd4:  pc = v1;
    5'd5:  ind = v1;
    5'd6:  begin opr = v1; opr_fresh = 1'b1; end
    5'd7:  ;                                        // NULL
    5'd8:  gpr[R_AW][7:0] = v1[7:0];                // AL
    5'd12: tmpa = v1;
    5'd13: tmpb = v1;
    5'd14: tmpc = v1;
    5'd15: psw = (v1 & PSW_WRITABLE) | PSW_FORCED;
    5'd16: gpr[R_AW][15:8] = v1[7:0];               // AH
    5'd17: count = v1;
    5'd18: begin                                    // wr_operand(R, v)
        case (r_kind)
            OK_REG:  if (r_byte) begin
                         if (r_idx[2]) gpr[r_idx[1:0]][15:8] = v1[7:0];
                         else          gpr[r_idx[1:0]][7:0]  = v1[7:0];
                     end else gpr[r_idx] = v1;
            OK_SREG: sreg[r_idx[1:0]] = v1;
            OK_MEM:  begin opr = v1; opr_fresh = 1'b1; end
            default: ;
        endcase
    end
    5'd19: begin                                    // wr_operand(M, v)
        case (m_kind)
            OK_REG:  if (m_byte) begin
                         if (m_idx[2]) gpr[m_idx[1:0]][15:8] = v1[7:0];
                         else          gpr[m_idx[1:0]][7:0]  = v1[7:0];
                     end else gpr[m_idx] = v1;
            OK_SREG: sreg[m_idx[1:0]] = v1;
            OK_MEM:  begin opr = v1; opr_fresh = 1'b1; end
            default: ;
        endcase
    end
    // tmpaL zero-extends, tmpbL SIGN-extends (ledger, "L-half writes")
    5'd20: tmpa = {8'd0, v1[7:0]};
    5'd21: tmpb = {{8{v1[7]}}, v1[7:0]};
    // the H-half write takes bus bits 15:8; a byte source presents its byte
    // there
    5'd22: tmpa[15:8] = bsw ? v1[7:0] : v1[15:8];
    5'd23: tmpb[15:8] = bsw ? v1[7:0] : v1[15:8];
    default: if (e_d1 >= 5'd24) gpr[e_d1[2:0]] = v1;
endcase
