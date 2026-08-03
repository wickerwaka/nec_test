//============================================================================
//  v30u_eu_poste.svh -- the POST-`E` ROW.
//
//  exec_impl.h's cadence note: "the E row and the row after it are charged by
//  the SUCCESSOR's decode, which overlaps them".  The post-`E` row therefore
//  costs NO clock of its own but its datapath work is real (`9D`'s
//  `SIGMA -> SP` lives there), and it lands on the clock the successor's first
//  loader step also rides.  This block runs at the top of that clock's edge,
//  before the successor's step -- the model's order.
//
//  The row carries no bus cycle and no queue pop (asserted below); everything
//  else -- both transfers, the flag write, the ALU latch and the internal
//  control strobes -- is the ordinary row body.
//============================================================================
begin
    if (e_have1) begin
        v1 = s1_val;
        bsw = (e_s1 == 5'd23);
        if (e_s1 == 5'd6) opr_fresh = 1'b0;
        if (e_s1 == 5'd20) begin
            if (sig_mask != 16'd0)
                stat = (stat & ~sig_mask) | (sig_flags & sig_mask);
        end
        if (!((e_s1 == 5'd20) && !sig_commits)) begin
            `include "v30u_eu_wd1.svh"
        end
    end
    if (e_have2) begin
        v2 = s2_val;
        if (e_s2 == 4'd4) begin
            if (sig_mask != 16'd0)
                stat = (stat & ~sig_mask) | (sig_flags & sig_mask);
        end
        if (!((e_s2 == 4'd4) && !sig_commits)) begin
            case (e_d2)
                2'd0: tmpa = v2;
                2'd1: tmpb = v2;
                2'd2: ind  = v2;
                default: ;
            endcase
        end
    end
    if (e_w && (sig_mask != 16'd0)) commit_flags(sig_mask, sig_flags);

    if (e_type == TY_ALU) begin
        al_adjust  = (al_op == A_ADJD) ? 2'd1 : (al_op == A_ADJA) ? 2'd2 : 2'd0;
        al_adjtmp  = al_tmp;
        al_bitarm  = (al_op == A_BIT);
        al_bitn    = bit_n;
        al_spent   = 1'b0;
        al_op      = r_aluop;
        al_tmp     = r_alutmp;
        al_byte    = op8_eff;                     // D1
        al_eaconst = 1'b0;
    end else if (e_type == TY_CTL && !e_farjmp) begin
        case (e_ictl)
            4'd3:  mode8080 = 1'b0;                 // MFS
            4'd2:  mode8080 = 1'b1;                 // MFC
            4'd0:  mode8080 = 1'b0;                 // ENDEM
            4'd1:  begin psw[FIE] = 1'b0; psw[FBRK] = 1'b0; end
            4'd6:  begin psw[FCY] = 1'b0; psw[FV] = 1'b0; end
            4'd7:  begin psw[FCY] = 1'b1; psw[FV] = 1'b1; end
            4'd12: sign_neg = sign_neg ^ (op8_eff ? tmpb[7] : tmpb[15]);
            4'd4:  begin psw[FCY] = 1'b0; sign_neg = 1'b1; end
            4'd13: if (!stat[FZ]) sign_neg = 1'b0;
            default: ;
        endcase
        psw = (psw & PSW_WRITABLE) | PSW_FORCED;
    end
`ifndef SYNTHESIS
    if (row_bus)
        $error("v30u_eu: a post-E row carries a bus cycle (upc %0d.%02X.%0d)",
               upc_page, upc_opc, upc_loc);
    if (row_q1 || row_q2)
        $error("v30u_eu: a post-E row pops a queue byte");
`endif
end
