//============================================================================
//  v30u_eu_row.svh -- ONE micro-row's work, exec_impl.h::run_micro's body.
//  Reached with the F interlock clear, every queue byte the row asked for
//  already taken, and its bus request already posted (all three are acts of
//  THIS clock; see the combinational output block in v30u_eu.sv).
//============================================================================
begin
    // --- the two parallel transfers -----------------------------------
    if (e_have1 && !e_is_rloop) begin
        v1  = (e_s1 == 5'd7) ? {8'd0, rowb0} : s1_val;
        bsw = (e_s1 == 5'd7) || (e_s1 == 5'd23);
        if (e_s1 == 5'd6) opr_fresh = 1'b0;      // reading OPR CONSUMES it
        if (e_s1 == 5'd20) begin
            if (sig_mask != 16'd0)
                stat = (stat & ~sig_mask) | (sig_flags & sig_mask);
        end
        if ((e_s1 == 5'd20) && !sig_commits) begin
            // CMP: the ALU does not drive the result bus, so neither the
            // register/OPR write nor its memory commit happens
            if ((e_d1 == 5'd19) && (m_kind == OK_MEM)) suppress_commit = 1'b1;
        end else begin
            `include "v30u_eu_wd1.svh"
        end
    end
    if (e_have2 && !e_is_rloop) begin
        v2 = (e_s2 == 4'd5) ? {8'd0, rowb1} : s2_val;
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
    // --- flag write ----------------------------------------------------
    if (!e_is_rloop && e_w && (sig_mask != 16'd0))
        commit_flags(sig_mask, sig_flags);

    // --- row type ------------------------------------------------------
    nloc  = upc_loc + 4'd1;
    carry = (upc_loc == 4'hF);
    taken = 1'b0;
    bubble = 1'b0;

    if (e_type == TY_ALU) begin
        // the NEXT latched operation
        al_adjust  = (al_op == A_ADJD) ? 2'd1 : (al_op == A_ADJA) ? 2'd2 : 2'd0;
        al_adjtmp  = al_tmp;
        al_bitarm  = (al_op == A_BIT);
        al_bitn    = bit_n;
        al_spent   = 1'b0;
        al_op      = r_aluop;
        al_tmp     = r_alutmp;
        al_byte    = op8;
        al_eaconst = 1'b0;
        // An armed ADJD/ADJA the next latched op does NOT consume DISCHARGES:
        // the adjust unit writes its plain truncation back (030B, EXT).
        if ((al_adjust != 2'd0) && (nxt_op != A_ADD) && (nxt_op != A_SUB)) begin
            case (al_adjtmp)
                2'd0: tmpa = tmpa & ((al_adjust == 2'd2) ? 16'h000F : 16'h00FF);
                2'd1: tmpb = tmpb & ((al_adjust == 2'd2) ? 16'h000F : 16'h00FF);
                default: tmpc = tmpc & ((al_adjust == 2'd2) ? 16'h000F : 16'h00FF);
            endcase
            al_adjust = 2'd0;
        end
        if (r_aluop == A_BIT)
            bit_n = tmps_lat[r_alutmp][3:0] & (op8 ? 4'd7 : 4'd15);
        if (r_aluop == A_ABS)
            sign_neg = op8 ? tmps_lat[r_alutmp][7] : tmps_lat[r_alutmp][15];
    end else if (e_type == TY_JMP) begin
        `include "v30u_eu_cond.svh"
        if (taken) begin
            nloc  = r_loc;
            carry = 1'b0;
            // M11: NO bubble on a jump BACK BY ONE ROW -- the target is the
            // row the sequencer read one clock ago.
            if ((r_loc + 4'd1) != upc_loc) bubble = 1'b1;
        end
    end else begin
        // --- CTL -------------------------------------------------------
        if (e_farjmp) begin
            upc_page = 3'd7;
            upc_opc  = {r_farloc, 3'd0};
            nloc  = 4'd0;
            carry = 1'b0;
            bubble = 1'b1;              // a FARJMP pays the redirect bubble
        end else begin
            case (e_ictl)
                I_MFS:     mode8080 = 1'b0;
                I_MFC:     mode8080 = 1'b1;
                I_ENDEM:   mode8080 = 1'b0;
                I_CITF:    begin psw[FIE] = 1'b0; psw[FBRK] = 1'b0; end
                I_CLRCYV:  begin psw[FCY] = 1'b0; psw[FV] = 1'b0; end
                I_SETCYV:  begin psw[FCY] = 1'b1; psw[FV] = 1'b1; end
                I_SIGNTGL: sign_neg = sign_neg ^ (op8 ? tmpb[7] : tmpb[15]);
                I_BCDINIT: begin psw[FCY] = 1'b0; sign_neg = 1'b1; end
                I_BCDNZ:   if (!stat[FZ]) sign_neg = 1'b0;
                default: ;                // SUSP / FLUSH rode this clock
            endcase
            psw = (psw & PSW_WRITABLE) | PSW_FORCED;
        end
        // --- the bus cycle (posted combinationally on this clock) ------
        if (e_ectl == E_INTATAIL) bus_word = 1'b1;
        if (row_bus) begin
            if (row_is_wr || row_is_wb) begin
                pend_active = 1'b1;
                pend_off  = acc_off;
                pend_seg  = acc_seg;
                pend_byte = acc_byte;
                pend_io   = acc_io;
                wr_out    = wr_out + (acc_split ? 2'd2 : 2'd1);
            end else begin
                rd_pending = rd_pending + 2'd1;
            end
        end
    end

    // --- the write-data pairing latch (`emit_pending`) -----------------
    if (pend_active && opr_fresh) begin
        pend_active = 1'b0;
        opr_fresh   = 1'b0;
        if (opr_owned != 2'd3)
            opr_owned = opr_owned + (pend_split ? 2'd2 : 2'd1);
    end

    // --- cadence -------------------------------------------------------
    upc_loc = nloc;
    if (carry) upc_opc = upc_opc + 8'd1;
    rowq = 2'd0; row_posted = 1'b0; row_paired = 1'b0;

    if (e_is_rloop) begin
        // `R`: the row's own operation runs COUNT times, one step per clock
        if (count == 16'd0) begin
            al_spent = 1'b1;
            st = S_ROW;
        end else begin
            rloop_n = count;
            st = S_RLOOP;
        end
        stop = 1'b1;
    end else if (e_e) begin
        // the successor's opcode pop rides the E row's own clock; a store the
        // pairing latch still owes data defers it to the sequence tail
        if (!pend_active && !opc_valid && retire_ok && q_ripe) begin
            opc_byte = q_byte;
            opc_valid = 1'b1;
            pop_is_first = 1'b0;
            poste = 1'b1;
            st = S_TAIL;
        end else if (!pend_active && !opc_valid) begin
            st = S_EPOP;
            stop = 1'b1;
        end else begin
            poste = 1'b1;
            st = S_TAIL;
        end
    end else begin
        st = bubble ? S_ROW_CHG : S_ROW;
        stop = 1'b1;
    end
end
