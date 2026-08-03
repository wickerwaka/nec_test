//============================================================================
//  v30u_eu_step.svh -- ONE step of the model's program.
//
//  Included inside v30u_eu.sv's bounded chain loop.  Each arm either
//    * STALLS  (`stop = 1'b1`, `st` unchanged) -- a `while (...) tick()`, or
//    * COMPLETES and hands over to a state that occupies the NEXT clock
//      (`st = ...; stop = 1'b1;`), or
//    * is ZERO-COST and falls through to the next arm inside this same edge
//      (`st = ...;` with no `stop`) -- the model's steps that charge nothing.
//
//  Governance: sim/loader_impl.h and sim/exec_impl.h are the SPEC.
//============================================================================
case (st)

//----------------------------------------------------------------------------
// loader_impl.h -- `pop_opcode`, the prefix loop
//----------------------------------------------------------------------------
S_OPC_POP: begin
    // pop_opcode with an EMPTY latch: the pop rides this clock, then the
    // decoder spends one (`if (!pre) biu.charge(1)`).
    if (!q_ripe) stop = 1'b1;
    else begin
        ld_b = q_byte;
        pc   = pc + 16'd1;
        pop_is_first = 1'b0;
        st = S_DECODE;
    end
end

S_TAKE_OPC: begin
    // ZERO-COST: the successor's opcode was pre-popped on the E row's clock.
    ld_b = opc_byte;
    opc_valid = 1'b0;
    pc = pc + 16'd1;
    st = S_DECODE;
end

S_DECODE: begin
    // ZERO-COST: the prefix test.
    pv = pla3_native(ld_b);
    if (pla3_is_prefix(pv)) begin
        case (pla3_xop(pv))
            PLA3_BL1_SEG_PREFIX: begin
                seg_override = 1'b1; seg_ovr = ld_b[4:3];
            end
            PLA3_BL1_REP_PFX:   rep_kind = REP_E;
            PLA3_BL1_REPNE_PFX: rep_kind = REP_NE;
            PLA3_BL1_REPC_PFX:  rep_kind = REP_C;
            PLA3_BL1_REPNC_PFX: rep_kind = REP_NC;
            PLA3_BL1_LOCK, PLA3_BL1_LOCK_ALIAS: lock_pfx = 1'b1;
            PLA3_BL1_EXT_PREFIX: ld_ext = 1'b1;
            default: ;
        endcase
        pfxcnt = pfxcnt + 8'd1;
        // the 0F escape is a 2-clock re-decode; every other prefix retires as
        // its own 2-clock instruction with its own F pop
        st = (pla3_xop(pv) == PLA3_BL1_EXT_PREFIX) ? S_EXT_CHG1 : S_PFX_CHG;
        stop = 1'b1;
    end else begin
        st = S_DECODE2;
    end
end

S_PFX_CHG: begin
    pop_is_first = 1'b1;                        // prefix_retire()
    st = S_OPC_POP;
    stop = 1'b1;
end

S_EXT_CHG1: begin
    st = S_EXT_POP;
    stop = 1'b1;
end

S_EXT_POP: begin
    // the second byte of the 0F page IS the opcode, and it pops as an S
    if (!q_ripe) stop = 1'b1;
    else begin
        ld_b = q_byte;
        pc   = pc + 16'd1;
        st = S_DECODE2;
    end
end

//----------------------------------------------------------------------------
// loader_impl.h -- the post-prefix-loop decode
//----------------------------------------------------------------------------
S_DECODE2: begin
    pv = ld_ext ? pla3_ext(ld_b) : pla3_native(ld_b);
    ld_pla = pv;
    if (!ld_ext && pla3_one_byte_logic(pv)) begin
        if (pla3_xop(pv) == PLA3_BL1_HALT) begin
            // S9a: `eu_halt` already rode the opcode's own pop clock.
            eu_halted = 1'b1;
            psw = (psw & PSW_WRITABLE) | PSW_FORCED;
            st = S_HALTED;
        end else begin
            st = S_1BL_LEAD;
        end
        stop = 1'b1;
    end else begin
        ld_byte = pla3_byte_only(pv) ? 1'b1
                : pla3_w_from_bit0(pv) ? (ld_b[0] == 1'b0)
                : 1'b0;
        op8  = ld_byte;
        imm8 = ld_byte || (ld_b == 8'h83) || (ld_b == 8'h6B);
        xop  = pla3_xop(pv);
        ld_page = ld_ext ? 3'd4 : ((rep_kind != REP_NONE) ? 3'd1 : 3'd0);
        opc_reg = ld_b;
        ld_hasrm = pla3_has_modrm(pv);
        st = pla3_has_modrm(pv) ? S_MODRM : S_NORM_CHG;
        stop = 1'b1;
    end
end

S_1BL_LEAD: begin
    // `wait_retire_lead`: the execute strobe is the clock BEFORE the
    // successor's opcode pop, so a late queue takes the flag write with it.
    if (!q_ripe_lead_n) stop = 1'b1;
    else begin
        case (pla3_xop(ld_pla))
            PLA3_BL1_SET_DIR: psw[FDIR] = 1'b1;
            PLA3_BL1_CLR_DIR: psw[FDIR] = 1'b0;
            PLA3_BL1_SET_IE:  psw[FIE]  = 1'b1;
            PLA3_BL1_CLR_IE:  psw[FIE]  = 1'b0;
            PLA3_BL1_SET_CY:  psw[FCY]  = 1'b1;
            PLA3_BL1_CLR_CY:  psw[FCY]  = 1'b0;
            PLA3_BL1_NOT_CY:  psw[FCY]  = ~psw[FCY];
            default: ;
        endcase
        psw = (psw & PSW_WRITABLE) | PSW_FORCED;
        st = S_INSTR_END;
    end
end

//----------------------------------------------------------------------------
// loader_impl.h -- ModR/M, displacement, effective address
//----------------------------------------------------------------------------
S_MODRM: begin
    if (!q_ripe) stop = 1'b1;
    else begin
        ld_rm = q_byte;
        pc = pc + 16'd1;
        ld_disp = 16'd0;
        ld_ripe_prev = 1'b0;
        chg = 2'd0;
        if (q_byte[7:6] == 2'd1)                        st = S_D8_A;
        else if (q_byte[7:6] == 2'd2)                   st = S_D16_LO;
        else if ((q_byte[7:6] == 2'd0) && (q_byte[2:0] == 3'd6))
                                                        st = S_D16_LO;
        else if (q_byte[7:6] != 2'd3)                   st = S_EA_CHG;
        else                                            st = S_BIND;
        if (st != S_BIND) stop = 1'b1;
    end
end

S_D8_A: begin
    // opcode+2: no byte is demanded.  M8's `pen` needs to know whether the
    // byte was ALREADY poppable when the demand arrives.
    ld_ripe_prev = q_ripe;
    st = S_D8_B;
    stop = 1'b1;
end

S_D8_B: begin
    if (!q_ripe) stop = 1'b1;
    else if (!ld_ripe_prev && (chg == 2'd0)) begin
        chg = 2'd1;                                     // the `pen` clock
        stop = 1'b1;
    end else begin
        ld_disp = {{8{q_byte[7]}}, q_byte};
        pc = pc + 16'd1;
        st = S_EA_CALC;          // ...and the trailing charge(1) spent this clk
    end
end

S_D16_LO: begin
    if (!q_ripe) stop = 1'b1;
    else begin
        ld_dlo = q_byte;
        pc = pc + 16'd1;
        st = S_D16_A;
        stop = 1'b1;
    end
end

S_D16_A: begin
    ld_ripe_prev = q_ripe;
    chg = 2'd0;
    st = S_D16_HI;
    stop = 1'b1;
end

S_D16_HI: begin
    if (!q_ripe) stop = 1'b1;
    else if (!ld_ripe_prev && (chg == 2'd0)) begin
        chg = 2'd1;
        stop = 1'b1;
    end else begin
        ld_disp = {q_byte, ld_dlo};
        pc = pc + 16'd1;
        st = S_EA_CALC;          // ...and the trailing charge(1) spent this clk
    end
end

S_EA_CHG: begin
    st = S_EA_CALC;              // the EA-compute clock is THIS one
end

S_EA_CALC: begin
    // ZERO-COST: the address adder; the clocks it needs were spent above.
    rmmod = ld_rm[7:6];
    rmrm  = ld_rm[2:0];
    case (rmrm)
        3'd0: ea = gpr[R_BW] + gpr[R_IX];
        3'd1: ea = gpr[R_BW] + gpr[R_IY];
        3'd2: ea = gpr[R_BP] + gpr[R_IX];
        3'd3: ea = gpr[R_BP] + gpr[R_IY];
        3'd4: ea = gpr[R_IX];
        3'd5: ea = gpr[R_IY];
        3'd6: ea = (rmmod == 2'd0) ? 16'd0 : gpr[R_BP];
        default: ea = gpr[R_BW];
    endcase
    ea = ea + ld_disp;
    rseg = seg_override ? {1'b0, seg_ovr}
         : ((rmrm == 3'd2) || (rmrm == 3'd3) ||
            ((rmrm == 3'd6) && (rmmod != 2'd0))) ? 3'd2 : 3'd3;
    ind = ea;
    al_eaconst = 1'b1;
    al_eaval   = ea;
    m_ea = ea;  m_seg = rseg;
    st = S_BIND;
end

//----------------------------------------------------------------------------
// loader_impl.h -- group dispatch, OPC select, operand binding
//----------------------------------------------------------------------------
S_NORM_CHG: begin
    st = S_BIND;                 // the opcode+1 clock is THIS one
end

S_BIND: begin
    // ZERO-COST.
    pv = ld_pla;
    rmmod = ld_rm[7:6];
    rmreg = ld_rm[5:3];
    rmrm  = ld_rm[2:0];
    ld_grpd = 1'b0;
    if (ld_hasrm && (pla3_xop(pv) == 4'hB)) begin
        ld_page = ld_b[3] ? 3'd3 : 3'd2;
        opc_reg = ld_rm;
        ld_grpd = 1'b1;
    end
    modrm_reg = rmreg;
    opc_from_modrm = 1'b0;
    opc_base = 5'd0;
    if ((ld_page == 3'd2) || (ld_page == 3'd3)) begin
        opc_base = A_INC; opc_from_modrm = 1'b1;
    end else if (!ld_ext && (ld_b[7:2] == 6'b100000)) begin
        opc_base = 5'd0;  opc_from_modrm = 1'b1;
    end else if (!ld_ext && ((ld_b == 8'hC0) || (ld_b == 8'hC1) ||
                             (ld_b[7:2] == 6'b110100))) begin
        opc_base = A_ROL; opc_from_modrm = 1'b1;
    end else if (pla3_xop(pv) == 4'hC) begin
        opc_base = A_INC;
    end
    rep_test = TEST_NONE;
    rep_pol  = 1'b0;
    if (pla3_xop(pv) == 4'hE) begin
        if (!ld_ext && (ld_b[7:1] == 7'b1110000)) begin
            rep_test = TEST_Z; rep_pol = ld_b[0];
        end else if ((rep_kind == REP_E) || (rep_kind == REP_NE)) begin
            rep_test = TEST_Z; rep_pol = (rep_kind == REP_E);
        end else if ((rep_kind == REP_C) || (rep_kind == REP_NC)) begin
            rep_test = TEST_CY; rep_pol = (rep_kind == REP_C);
        end
    end
    // the 0F BIT-FIELD group selects BYTE registers for both ModR/M operands
    bsw = ld_byte || (ld_ext && (pla3_xop(pv) == 4'h3));
    m_kind = OK_NONE; m_idx = 3'd0; m_byte = 1'b0;
    r_kind = OK_NONE; r_idx = 3'd0; r_byte = 1'b0; r_ea = 16'd0; r_seg = 3'd3;
    if (ld_hasrm) begin
        if (pla3_sreg_mov(pv)) begin
            r_kind = OK_SREG; r_idx = {1'b0, rmreg[1:0]}; r_byte = 1'b0;
        end else begin
            r_kind = OK_REG;  r_idx = rmreg; r_byte = bsw;
        end
        if (rmmod == 2'd3) begin
            m_kind = OK_REG; m_idx = rmrm; m_byte = bsw;
        end else begin
            m_kind = OK_MEM; m_byte = ld_byte;
        end
        if (pla3_dir_from_bit1(pv) && ld_b[1]) begin
            tk = m_kind; m_kind = r_kind; r_kind = tk;
            ti = m_idx;  m_idx  = r_idx;  r_idx  = ti;
            te = m_ea;   m_ea   = r_ea;   r_ea   = te;
            ts = m_seg;  m_seg  = r_seg;  r_seg  = ts;
            tb = m_byte; m_byte = r_byte; r_byte = tb;
        end
    end else if (pla3_acc_w_operand(pv)) begin
        m_kind = OK_REG; m_idx = R_AW; m_byte = ld_byte;
    end else if ((ld_b < 8'h40) && (ld_b[2:0] >= 3'd6)) begin
        r_kind = OK_SREG; r_idx = {1'b0, ld_b[4:3]};
    end else begin
        m_kind = OK_REG; m_idx = ld_b[2:0]; m_byte = ld_byte;
    end
    wb_kind = m_kind; wb_idx = m_idx; wb_ea = m_ea;
    wb_seg = m_seg;   wb_byte = m_byte;

    ld_preread = 1'b0;
    if (ld_hasrm && (rmmod != 2'd3) && !(!ld_ext && pla3_modrm_store(pv)))
        if ((m_kind == OK_MEM) || (r_kind == OK_MEM)) ld_preread = 1'b1;

    row_posted = 1'b0;
    if (ld_preread)     st = S_PRERD;
    else if (ld_grpd)   st = S_GRPD_CHG;
    else                st = S_ENTER;
    if (st != S_ENTER) stop = 1'b1;
end

S_PRERD: begin
    // the pre-decode operand read; `wait_opr` opens micro-row 0 at its T4 + 2
    if (!row_posted) begin
        if (eu_slot_busy_n) stop = 1'b1;
        else begin
            row_posted = 1'b1;
            rd_pending = rd_pending + 2'd1;
            stop = 1'b1;
        end
    end else if (rd_done_cnt == 2'd0) begin
        stop = 1'b1;
    end else begin
        rd_done_cnt = rd_done_cnt - 2'd1;
        if (rdq_n != 2'd0) begin
            opr = rdq0; rdq0 = rdq1; rdq_n = rdq_n - 2'd1;
        end
        opr_fresh = 1'b1;
        row_posted = 1'b0;
        st = ld_grpd ? S_GRPD_CHG : S_ENTER;
        if (ld_grpd) stop = 1'b1;
    end
end

S_GRPD_CHG: begin
    st = S_ENTER;
end

S_ENTER: begin
    // ZERO-COST: micro-row 0 opens on the clock the caller handed over
    upc_page = ld_page;
    upc_opc  = opc_reg;
    upc_loc  = 4'd0;
    ending = 1'b0; rowq = 2'd0; row_posted = 1'b0; row_paired = 1'b0;
    suppress_commit = 1'b0;
    st = S_ROW;
    stop = 1'b1;
end

//----------------------------------------------------------------------------
// exec_impl.h -- run_micro
//----------------------------------------------------------------------------
S_ROW: begin
    if (row_blocked_n) begin
        stop = 1'b1;                                    // stall_opr
    end else if (row_need_q && !q_ripe) begin
        stop = 1'b1;                                    // stall_q
    end else if (row_need_q) begin
        if (row_q1 && (rowq == 2'd0)) rowb0 = q_byte; else rowb1 = q_byte;
        pc = pc + 16'd1;
        rowq = rowq + 2'd1;
        if ({1'b0, rowq} < row_qn) stop = 1'b1;         // a second byte
    end else if (row_pre_wait_n) begin
        stop = 1'b1;                                    // deliver_read
    end else if (row_bus && !row_posted && eu_slot_busy) begin
        // stall_slot -- F11's rule, in the SLOT dimension.  `BiuTimed::post`
        // waits on the slot and THEN takes it, both inside the row, so a row
        // that posts this clock does NOT wait this clock.  `eu_slot_busy_n`
        // already carries this row's OWN post (it is what set it), so without
        // `!eu_post` the step stalls on an event it itself caused and the row
        // runs one clock too long -- invisible on an aligned store (the pairing
        // still lands before T1) and fatal on a SPLIT one, where the extra
        // clocks push the pairing past the FIRST half's T1 (`50 idx 1`, data
        // 0000 on rows 6-8 against the golden's AX).
        stop = 1'b1;
    end
    if (!stop) begin
        // the F interlock's own delivery, taken once
        if (e_f) begin
            if (row_reads_opr && (rd_done_cnt != 2'd0))
                rd_done_cnt = rd_done_cnt - 2'd1;
            if (rdq_n != 2'd0) begin
                opr = rdq0; rdq0 = rdq1; rdq_n = rdq_n - 2'd1;
                opr_fresh = 1'b1;
            end
        end
        `include "v30u_eu_row.svh"
    end
end

S_ROW_CHG: begin
    // the taken-JMP / FARJMP redirect bubble (M11 / 7.7)
    st = S_ROW;
    stop = 1'b1;
end

S_RLOOP: begin
    // `R`: one iterative step per clock, COUNT times.  The row's own ALU
    // latch drives the ONE shared iterative unit; afterwards it is SPENT.
    count = count - 16'd1;
    rloop_n = rloop_n - 16'd1;
    if (it_fmask != 16'd0)
        stat = (stat & ~it_fmask) | (it_flags & it_fmask);
    if (!e_nopmv) begin
        v1 = it_val;
        bsw = 1'b0;
        `include "v30u_eu_wd1.svh"
    end
    if (it_writes_tmpa) tmpa = it_tmpa;
    if (e_w && (it_fmask != 16'd0)) commit_flags(it_fmask, it_flags);
    // `while (count != 0)`: the model runs the operation COUNT times, so the
    // terminator is read AFTER this clock's decrement -- reading it before
    // (`== 1`) runs COUNT-1 iterations and, at COUNT==1, none at all: the
    // counter wraps and the state never leaves.  All sixteen D0.x/D1.x forms
    // (shift-by-1, so COUNT is always 1) hung on it.
    if (rloop_n == 16'd0) begin      // this was the last iteration
        al_spent = 1'b1;
        st = S_ROW;
    end
    stop = 1'b1;
end

S_EPOP: begin
    // the E row's successor pop, deferred past the retire deadline
    if (!retire_ok_n) stop = 1'b1;
    else if (!q_ripe) stop = 1'b1;
    else begin
        opc_byte = q_byte;
        opc_valid = 1'b1;
        pop_is_first = 1'b0;
        poste = 1'b1; pe_opc_reg = opc_reg; pe_opc8080 = opc8080;  // F23
        st = S_TAIL;          // ...and the E row's own charge(1) spent this clk
    end
end

S_TAIL: begin
    // ZERO-COST: run_micro's tail -- a staged write still owes the bus data.
    if (pend_active) st = S_TAIL_W;
    else if (opc_valid) st = S_INSTR_END;
    else st = S_TAIL_POP;
    if (st != S_INSTR_END) stop = 1'b1;
end

S_TAIL_W: begin
    // `if (!opr_fresh_) deliver_read(); emit_pending();`
    if (!opr_fresh && (nr_wait || !opr_free_now_n)) stop = 1'b1;
    else begin
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
        st = opc_valid ? S_INSTR_END : S_TAIL_POP;
        if (st != S_INSTR_END) stop = 1'b1;
    end
end

S_TAIL_POP: begin
    // the DEFERRED opcode pre-pop: `wait_bus()` then the pop, then M8b's
    // clock after it (`if (deferred) biu.charge(1)`).
    if (!retire_ok_n) stop = 1'b1;
    else if (!q_ripe) stop = 1'b1;
    else begin
        opc_byte = q_byte;
        opc_valid = 1'b1;
        pop_is_first = 1'b0;
        // M8b: the clock AFTER the pop belongs to the successor's decode --
        // `if (deferred) biu.charge(1)` -- which is this clock, spent here.
        st = S_INSTR_END;
    end
end

S_HALTED: begin
    stop = 1'b1;                                        // stall_pin
end

S_RESET: begin
    // F25: `biu.susp(); biu.charge(kResetEntryClocks);` -- the internal reset
    // dispatch, before the ROM's own reset rows at 7.03.0 (01D0).
    rst_ctr = rst_ctr + 3'd1;
    if (rst_ctr == 3'd4) st = S_ROW;
    stop = 1'b1;
end

S_INSTR_END: begin
    // ZERO-COST: `step()` returns; the successor's `clear_consumed()` and
    // `loader_decode()`'s per-instruction latch reset run here.
    seg_override = 1'b0; seg_ovr = 2'd3; rep_kind = REP_NONE; lock_pfx = 1'b0;
    rep_test = TEST_NONE; rep_pol = 1'b0; bus_word = 1'b0; opc8080 = 1'b0;
    ld_ext = 1'b0; ld_hasrm = 1'b0; ld_grpd = 1'b0; ld_preread = 1'b0;
    ld_rm = 8'd0; ld_disp = 16'd0;
    // F22: the four latches the post-`E` row still reads are reset AFTER it,
    // which is the model's own order.  When the discharge has not happened yet
    // the reset is OWED and the `poste` block pays it.
    if (poste) iend_owed = 1'b1;
    else begin
        `include "v30u_eu_iend_late.svh"
    end
    ending = 1'b0; rowq = 2'd0; row_posted = 1'b0; row_paired = 1'b0;
    if (!opc_valid) pop_is_first = 1'b1;                // clear_consumed()
    st = opc_valid ? S_TAKE_OPC : S_OPC_POP;
    if (st == S_OPC_POP) stop = 1'b1;
end

default: stop = 1'b1;
endcase
