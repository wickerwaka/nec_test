//============================================================================
//  v30u_eu_1bl.svh -- the ONE_BYTE_LOGIC execute strobe (loader_impl.h).
//  The flag write these forms make instead of entering the ROM.  Included
//  from BOTH arms of the strobe (S_DECODE2 when the retire lead is already
//  satisfied, S_1BL_LEAD when it was not) -- one expression, both paths.
//============================================================================
begin
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
end
