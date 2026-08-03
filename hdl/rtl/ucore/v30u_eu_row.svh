//============================================================================
//  v30u_eu_row.svh -- ONE micro-row's work, exec_impl.h::run_micro's body.
//  Reached with the F interlock clear, every queue byte the row asked for
//  already taken, and its bus request already posted (all three are acts of
//  THIS clock; see the combinational output block in v30u_eu.sv).
//============================================================================
begin
    // --- the two parallel transfers -----------------------------------
    if (e_have1 && !e_is_rloop) begin
        // F21: `opr` is a LIVE BLOCKING variable here -- the `F` interlock's
        // delivery (S_ROW, just above) has already written it, and the model
        // does the delivery at the TOP of the row, before the transfers.
        // `s1_val` is a WIRE off the REGISTER, so it still holds the pre-edge
        // word: `58`'s `OPR -> M` wrote AX = 0 in 500/500 cases.  F11b's trap,
        // third instance -- in this EU a wire named like a step variable is
        // not that step variable.
        v1  = (e_s1 == 5'd7) ? {8'd0, rowb0}
            : (e_s1 == 5'd6) ? opr
            : s1_val;
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
        // F29 -- ...AND SO DO THE ARMING CAPTURES.  `exec_impl.h` builds its
        // `tmps[]` from the LIVE `m_.tmpa/b/c` in the ALU-latch block, which
        // runs AFTER the row's transfers -- and the rows that arm BIT and ABS
        // are exactly the rows that load the tmp they read (`0F10`:
        // `02AC  M -> tmpb  CX -> tmpa  ALU BIT tmpa`).  `tmps_lat` is a WIRE
        // off the REGISTERS, so the bit index came from the PREVIOUS
        // instruction's tmpa and the whole 0F 10-1F block tested the wrong bit.
        // F11b's trap again.
        case (r_alutmp)
            2'd0: tsel = tmpa;
            2'd1: tsel = tmpb;
            2'd2: tsel = tmpc;
            default: tsel = 16'd0;
        endcase
        if (r_aluop == A_BIT)
            bit_n = tsel[3:0] & (op8 ? 4'd7 : 4'd15);
        if (r_aluop == A_ABS)
            sign_neg = op8 ? tsel[7] : tsel[15];
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
        // F20: `if (pend_.active) { if (!opr_fresh_) deliver_read();
        // emit_pending(); }` -- a staged store runs BEFORE this row's own
        // cycle, and it is given the completed-read store's head if the row's
        // transfers did not already refresh OPR.  The wire the BIU reads is
        // `opr_now`'s `row_pre_deliver` arm: same event, same expression.
        if (row_bus && pend_active) begin
            if (!opr_fresh) begin
                if (rd_done_cnt != 2'd0) rd_done_cnt = rd_done_cnt - 2'd1;
                if (rdq_n != 2'd0) begin
                    opr = rdq0; rdq0 = rdq1; rdq_n = rdq_n - 2'd1;
                end
            end
            pend_active = 1'b0;
            opr_fresh   = 1'b0;
            if (opr_owned != 2'd3)
                opr_owned = opr_owned + (pend_split ? 2'd2 : 2'd1);
        end
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
    // F26 -- AN `R` ROW KEEPS THE SEQUENCER WHILE IT ITERATES.  The loop is
    // `while (m_.count != 0) { ... wr_dst1(op.d1, ...) }` INSIDE the row's own
    // iteration, so every step writes THE R ROW'S Dest1.  Advancing `upc`
    // before entering S_RLOOP handed the loop its SUCCESSOR's row word:
    // `D1.4`'s `0116 SIGMA -> tmpb  W R ALU OPC` wrote through `0117`'s
    // `SIGMA -> M` instead, so the shift result never reached tmpb and every
    // shift/rotate form left its operand untouched.  The advance now happens
    // where the loop ENDS -- which is also where the model leaves the row.
    if (!e_is_rloop || (count == 16'd0)) begin
        upc_loc = nloc;
        if (carry) upc_opc = upc_opc + 8'd1;
    end
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
        // pairing latch still owes data defers it to the sequence tail.
        // F11, stated the only way that cannot drift: the demand and the take
        // read THE SAME WIRES.  `retire_ok_e` and `pend_after` are the exact
        // post-row values this block would otherwise recompute from its live
        // blocking copies -- reconstructing them twice is what let the two
        // sides disagree in pass 1.  (`retire_ok_n` reads the REGISTER `wr_out`
        // and is NOT this predicate.)
        // F24 is a term of the TAKE as well as of the demand: a row that
        // FLUSHES has already emptied the queue by the time the model reaches
        // `opcode_prefetch`, so it cannot keep a byte either.
        retire_now = retire_ok_e;
        if (!pend_after && !opc_valid && retire_now && q_ripe && !row_flush)
        begin
            opc_byte = q_byte;
            opc_valid = 1'b1;
            pop_is_first = 1'b0;
            poste = 1'b1; pe_opc_reg = opc_reg; pe_opc8080 = opc8080;  // F23
            pe_op8 = op8; pe_pfxcnt = pfxcnt;                     // D1 / F22
            st = S_TAIL;
        end else if (!pend_after && !opc_valid) begin
            st = S_EPOP;
            stop = 1'b1;
        end else begin
            poste = 1'b1; pe_opc_reg = opc_reg; pe_opc8080 = opc8080;  // F23
            pe_op8 = op8; pe_pfxcnt = pfxcnt;                     // D1 / F22
            st = S_TAIL;
        end
    end else begin
        st = bubble ? S_ROW_CHG : S_ROW;
        stop = 1'b1;
    end
end
