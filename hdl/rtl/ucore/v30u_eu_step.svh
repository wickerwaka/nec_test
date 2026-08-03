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
    //
    // ...and when this pop is an INSTRUCTION BOUNDARY (`bnd_armed` -- a
    // pre-decode-executed predecessor, or the wake from HALT) the recognition
    // is tested FIRST and needs no byte.
    if (bnd_armed && irq_take) begin
        bnd_armed   = 1'b0;
        irq_shadow  = 1'b0;
        irq_sel_nmi = irq_nmi_lvl;
        st = S_IRQ_D;
        stop = 1'b1;
    end else if (!q_ripe) stop = 1'b1;
    else begin
        // the pop closes the window and spends the shadow
        bnd_armed = 1'b0; irq_shadow = 1'b0;
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
            // S9a: `halt_decode()` is called HERE, after `pop_opcode`'s own
            // `charge(1)`, so `eu_halt` rides the DECODE clock -- the state
            // this arm hands over to.  One rule, both paths.
            eu_halted = 1'b1;
            // clear_consumed(): the wake's pop is a fresh instruction's `F`,
            // and the HALT path never reaches `S_INSTR_END` to say so.
            pop_is_first = 1'b1;
            psw = (psw & PSW_WRITABLE) | PSW_FORCED;
            st = S_HALTED;
        end else begin
            // §35.3 -- THE 1BL EXECUTE STROBE IS THIS EDGE, NOT THE NEXT ONE.
            // The model is `charge(1); wait_retire_lead(); <write>; charge(1);`
            // -- the write commits at clk_ = pop+1, i.e. it is VISIBLE DURING
            // the clock this arm hands over to, so it has to be made on the
            // edge that hands over.  The wait's condition is available here:
            // `q_ripe_lead_n` is the next-state view and says "the head is
            // poppable by pop+2", which is `wait_retire_lead`'s test AT
            // clk_ = pop+1, exactly.
            //
            // `S_1BL_LEAD` keeps the case where it is NOT yet satisfied and
            // becomes a PURE WAIT; `S_1BL_CHG` is the trailing `charge(1)`
            // both paths owe.  MEASURED, `FA idx 4`: the golden's status
            // nibble is already 2 (IE=0) on clock 1 and `S_1BL_LEAD` was
            // standing there, so the write landed on the edge ENDING clock 1.
            if (q_ripe_lead_n) begin
                `include "v30u_eu_1bl.svh"
                st = S_1BL_CHG;
            end else begin
                st = S_1BL_LEAD;
            end
        end
        stop = 1'b1;
    end else begin
        ld_byte = pla3_byte_only(pv) ? 1'b1
                : pla3_w_from_bit0(pv) ? (ld_b[0] == 1'b0)
                : 1'b0;
        op8  = ld_byte;
        imm8 = ld_byte || (ld_b == 8'h83) || (ld_b == 8'h6B);
        xop  = pla3_xop(pv);
        // ...and the sreg-MOV class arms the recognition shadow (`8C` / `8E`,
        // load AND store -- both measured).  One boundary, spent by it.
        if (!ld_ext && pla3_sreg_mov(pv)) irq_shadow = 1'b1;
        ld_page = ld_ext ? 3'd4 : ((rep_kind != REP_NONE) ? 3'd1 : 3'd0);
        opc_reg = ld_b;
        ld_hasrm = pla3_has_modrm(pv);
        st = pla3_has_modrm(pv) ? S_MODRM : S_NORM_CHG;
        stop = 1'b1;
    end
end

S_1BL_LEAD: begin
    // `wait_retire_lead`, and NOTHING ELSE: the execute strobe is the clock
    // BEFORE the successor's opcode pop, so a late queue takes the flag write
    // with it -- but the write itself is made on the edge that hands over to
    // the clock it must be visible during (see S_DECODE2).
    if (!q_ripe_lead_n) stop = 1'b1;
    else begin
        `include "v30u_eu_1bl.svh"
        st = S_1BL_CHG;
        stop = 1'b1;
    end
end

S_1BL_CHG: begin
    // "pre-decode-executed forms retire in 2 clocks" -- the trailing
    // `biu.charge(1)`, which both arms of the strobe owe.
    st = S_INSTR_END;
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
        // F27 -- THE PRE-DECODE READ DOES NOT MAKE OPR "FRESH".  The loader
        // assigns `m.opr = biu.mem_read(...)` DIRECTLY (loader_impl.h:495) and
        // never touches `opr_fresh_`, which `begin_sequence()` left false --
        // the pairing latch is armed by a `-> OPR` TRANSFER, not by a read.
        // With it set, `86`/`87`'s write-back row emitted the store the instant
        // it posted, handing the bus the operand the pre-read had just brought
        // IN (`86 idx 0`: 9054) instead of the register the post-`E` row
        // `tmpb -> M` is about to swap OUT (9f3e).
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
    if (row_blocked) begin
        stop = 1'b1;                                    // stall_opr
    end else if (row_need_q && !q_ripe) begin
        stop = 1'b1;                                    // stall_q
    end else if (row_need_q) begin
        if (row_q1 && (rowq == 2'd0)) rowb0 = q_byte; else rowb1 = q_byte;
        pc = pc + 16'd1;
        rowq = rowq + 2'd1;
        if ({1'b0, rowq} < row_qn) stop = 1'b1;         // a second byte
    end else if (row_pre_wait) begin
        stop = 1'b1;                                    // deliver_read
    end else if (row_bus && !row_posted && eu_slot_busy) begin
        // F11 AGAIN, AND THIS TIME IN THE PAIRING DIMENSION.  `bus_write` is
        //     if (pend_.active) { if (!opr_fresh_) deliver_read();
        //                         emit_pending(); }
        //     biu_.write_request(...);        <- the slot wait is IN HERE
        // so the staged write is PAIRED BEFORE the slot is waited on.  The act
        // decode had that right (`eu_pair` carries no slot term, and the BIU
        // took the word), and only the STEP stalled first -- so `pend_active`
        // stayed set, the row re-ran `row_pre_wait` against an OPR the pairing
        // had just re-taken, and the row cost two extra clocks.
        // MEASURED, `F3AA idx 2`: the third store row stands on golden rows
        // 13-17 where the model stands on 13-15, and rows 14-16 are exactly
        // this -- `eu_pair` already asserted on 13 with `pnd` still 1.
        if (row_bus && pend_active) begin
            if (!opr_fresh) begin
                if (rd_done_cnt != 2'd0) rd_done_cnt = rd_done_cnt - 2'd1;
                if (rdq_n != 2'd0) begin
                    opr = rdq0; rdq0 = rdq1; rdq_n = rdq_n - 2'd1;
                end
            end
            pend_active = 1'b0;
            opr_fresh   = 1'b0;
        end
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
        // F26: the sequencer leaves the `R` row HERE, not before the loop.
        if (upc_loc == 4'hF) upc_opc = upc_opc + 8'd1;
        upc_loc = upc_loc + 4'd1;
        st = S_ROW;
    end
    stop = 1'b1;
end

S_EPOP: begin
    // the E row's successor pop, deferred past the retire deadline
    if (!retire_ok_n) stop = 1'b1;
    // ...and the BOUNDARY is that deadline alone (`boundary_no_pop`'s
    // `wait_bus()`), so it is taken here whether or not the byte is ripe.
    // The post-`E` row still runs -- the model reaches it through the same
    // `ending` pass -- so the debt is raised exactly as the pop path raises it.
    else if (irq_take) begin
        irq_shadow = 1'b0;
        irq_sel_nmi = irq_nmi_lvl;
        poste = 1'b1; pe_opc_reg = opc_reg; pe_opc8080 = opc8080;
        pe_op8 = op8; pe_pfxcnt = pfxcnt;
        st = S_IRQ_D;
        stop = 1'b1;
    end
    else if (!q_ripe) stop = 1'b1;
    else begin
        irq_shadow = 1'b0;
        opc_byte = q_byte;
        opc_valid = 1'b1;
        pop_is_first = 1'b0;
        poste = 1'b1; pe_opc_reg = opc_reg; pe_opc8080 = opc8080;  // F23
        pe_op8 = op8; pe_pfxcnt = pfxcnt;                         // D1 / F22
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
    if (!opr_fresh && (nr_wait || !opr_free_now)) stop = 1'b1;
    else begin
        if (!opr_fresh) begin
            if (rd_done_cnt != 2'd0) rd_done_cnt = rd_done_cnt - 2'd1;
            if (rdq_n != 2'd0) begin
                opr = rdq0; rdq0 = rdq1; rdq_n = rdq_n - 2'd1;
            end
        end
        pend_active = 1'b0;
        opr_fresh   = 1'b0;
        // §35.4 -- `emit_pending()` IS ZERO CLOCKS, ALWAYS (it fills a slot the
        // bus has already reserved), and `deliver_read()` is a WAIT: zero when
        // the condition already holds.  So the satisfied arm must FALL THROUGH
        // to the tail's pop inside this same edge, not hand it the next clock.
        // The `stop` that stood here charged one clock against a step the
        // model charges nothing for.
        if (opc_valid) begin
            st = S_INSTR_END;
        end else if (retire_ok_n && irq_take) begin
            // the tail's own boundary, taken right where the model takes it
            irq_shadow  = 1'b0;
            irq_sel_nmi = irq_nmi_lvl;
            st = S_IRQ_D;
            stop = 1'b1;
        end else begin
            st = S_TAIL_POP;
        end
    end
end

S_TAIL_POP: begin
    // the DEFERRED opcode pre-pop: `wait_bus()` then the pop, then M8b's
    // clock after it (`if (deferred) biu.charge(1)`).
    if (!retire_ok_n) stop = 1'b1;
    // the same boundary, on the deferred arm (`exec_impl.h`'s second
    // `at_fire_boundary()` call).  `poste` was raised by the `E` row itself
    // here, so only the decision is owed.
    else if (irq_take) begin
        irq_shadow = 1'b0;
        irq_sel_nmi = irq_nmi_lvl;
        st = S_IRQ_D;
        stop = 1'b1;
    end
    else if (!q_ripe) stop = 1'b1;
    else begin
        irq_shadow = 1'b0;
        opc_byte = q_byte;
        opc_valid = 1'b1;
        pop_is_first = 1'b0;
        // M8b: the clock AFTER the pop belongs to the successor's decode --
        // `if (deferred) biu.charge(1)` -- which is this clock, spent here.
        st = S_INSTR_END;
    end
end

S_HALTED: begin
    // stall_pin -- and THE WAKE.  A halted part has no boundary of its own, so
    // the decision clock D is simply the first clock the pin pipeline has
    // matured the event on; the would-pop clock is D+1 and the entry, as ever,
    // is two clocks past that.  `eu_unhalt` is combinational off this state
    // (INT) or owed to the entry clock (NMI, where the bus is HELD).
    if (irq_nmi_lvl) begin
        bnd_armed = 1'b1;
        st = S_OPC_POP;
    end else if (irq_pin_int) begin
        eu_halted = 1'b0;              // `eu_unhalt` rides THIS clock
        bnd_armed = 1'b1;
        st = S_OPC_POP;
    end
    stop = 1'b1;
end

S_IRQ_D: begin
    // `CpuT::interrupt()`.  ONE internal decision clock (the boundary was the
    // clock before), then the entry's first row.  The loader is BYPASSED, so
    // every latch it would have written is presented explicitly -- in
    // particular `xop`, without which the vector fetch's `SR = IO` would be
    // re-classified as a port access (ledger A24), and `op8`, without which
    // 01EC's `2*vector` truncates.
    upc_page = 3'd7;
    upc_opc  = irq_sel_nmi ? 8'h00 : 8'h02;   // 01D8 (BRK/NMI) / 01E0 (INTA)
    upc_loc  = irq_sel_nmi ? 4'd2  : 4'd0;
    if (irq_sel_nmi) nmi_latch = 1'b0;
    seg_override = 1'b0; seg_ovr = 2'd3; rep_kind = REP_NONE; lock_pfx = 1'b0;
    pfxcnt = 8'd0;
    m_kind = OK_NONE; m_idx = 3'd0; m_ea = 16'd0; m_seg = 3'd3; m_byte = 1'b0;
    r_kind = OK_NONE; r_idx = 3'd0; r_ea = 16'd0; r_seg = 3'd3; r_byte = 1'b0;
    wb_kind = OK_NONE; wb_idx = 3'd0; wb_ea = 16'd0; wb_seg = 3'd3;
    wb_byte = 1'b0;
    opc_base = 5'd0; opc_from_modrm = 1'b0; modrm_reg = 3'd0; opc_reg = 8'd0;
    rep_test = TEST_NONE; rep_pol = 1'b0; xop = 4'd0;
    op8 = 1'b0; imm8 = 1'b0; bus_word = 1'b0; opc8080 = 1'b0;
    al_op = A_ADD; al_tmp = 2'd0; al_byte = 1'b0;
    al_eaconst = 1'b0; al_eaval = 16'd0;
    al_adjust = 2'd0; al_adjtmp = 2'd0; al_bitarm = 1'b0; al_bitn = 4'd0;
    al_spent = 1'b0;
    // begin_sequence(): the pairing latch and the completed-read store
    pend_active = 1'b0; pend_off = 16'd0; pend_seg = 3'd3;
    pend_byte = 1'b0; pend_io = 1'b0; opr_fresh = 1'b0;
    rdq0 = 16'd0; rdq1 = 16'd0; rdq_n = 2'd0;
    ld_ext = 1'b0; ld_hasrm = 1'b0; ld_grpd = 1'b0; ld_preread = 1'b0;
    ld_rm = 8'd0; ld_disp = 16'd0;
    ending = 1'b0; rowq = 2'd0; row_posted = 1'b0; row_paired = 1'b0;
    suppress_commit = 1'b0;
    opc_valid = 1'b0; pop_is_first = 1'b1; bnd_armed = 1'b0;
    irq_shadow = 1'b0;
    intr_pending = 1'b0;                       // `m_.intr_pending = false`
    rep_chain = 1'b0;                          // `begin_sequence()`
    if (eu_halted) begin
        eu_halted = 1'b0;
        unhalt_pend = 1'b1;   // the NMI wake: `unhalt()` AT the entry clock
    end
    st = S_ROW;
    stop = 1'b1;
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
    // F22 SETTLED: `pfxcnt` is reset HERE, with the rest of the prologue, and
    // NOT in `iend_late` -- the prefix arm below writes it on this same edge,
    // so a deferred reset would land on top of the successor's own count.  The
    // post-`E` row reads its travelling copy (`pfxcnt_eff`).
    pfxcnt = 8'd0;
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
    rep_chain = 1'b0;                    // `begin_sequence()`: rep_elems_ = 0
    // S9b: a form the PRE-DECODE executed (`FA` `FB` `F5` `F8` ... -- no `E`
    // row, so no boundary was taken above) retires at a boundary too, and it
    // is the cold pop that follows.  Everything else has already had its.
    if (!opc_valid) begin
        pop_is_first = 1'b1;                            // clear_consumed()
        bnd_armed = 1'b1;
    end
    st = opc_valid ? S_TAKE_OPC : S_OPC_POP;
    if (st == S_OPC_POP) stop = 1'b1;
end

default: stop = 1'b1;
endcase
