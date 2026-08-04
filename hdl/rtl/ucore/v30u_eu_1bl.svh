//============================================================================
//  v30u_eu_1bl.svh -- the ONE_BYTE_LOGIC execute strobe (loader_impl.h).
//  The flag write these forms make instead of entering the ROM.  Included
//  from BOTH arms of the strobe (S_DECODE2 when the retire lead is already
//  satisfied, S_1BL_LEAD when it was not) -- one expression, both paths.
//============================================================================
begin
    case (pla3_xop(ld_pla_n))
        PLA3_BL1_SET_DIR: psw_n[FDIR] = 1'b1;
        PLA3_BL1_CLR_DIR: psw_n[FDIR] = 1'b0;
        PLA3_BL1_SET_IE:  psw_n[FIE]  = 1'b1;
        PLA3_BL1_CLR_IE:  psw_n[FIE]  = 1'b0;
        PLA3_BL1_SET_CY:  psw_n[FCY]  = 1'b1;
        PLA3_BL1_CLR_CY:  psw_n[FCY]  = 1'b0;
        PLA3_BL1_NOT_CY:  psw_n[FCY]  = ~psw_n[FCY];
        default: ;
    endcase
    psw_n = (psw_n & PSW_WRITABLE) | PSW_FORCED;
end
