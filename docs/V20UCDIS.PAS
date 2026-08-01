program V20MicrocodeDisassembler;
uses HexRange;

const
    InputName  = 'v20bits.txt';
    OutputName = 'v20uc.txt';
    OpcCount   = 257;
    RowCount   = OpcCount*4;

type
    FlagBit = (Flag_F,
               Flag_W,    {write flags}
               Flag_E,    {end of instruction}
               Flag_R,    {repeat ALU instruction}
               Type_ALU,
               Type_JMP,
               Type_CTL);

    tSource1 = 0..31;
    tDest1   = 0..31;
    tSource2 = 0..15;
    tDest2   = 0..3;
    tAluOp   = 0..31;
    tTmpReg  = 0..3;
    tCond    = 0..15;
    tIntCtl  = 0..15;
    tExtCtl  = 0..7;
    tSR      = 0..3;
    tFarLoc  = 0..31; { ExtCtl shl 2 + SR }

    MicroInstr = record
        Source1 : tSource1;
        Dest1   : tDest1;
        Source2 : tSource2;
        Dest2   : tDest2;
        Flags   : set of FlagBit;
        case FlagBit of
            Type_ALU: (Op   : tAluOp;  Tmp : tTmpReg);
            Type_JMP: (Cond : tCond;   Loc : 0..15);
            Type_CTL: (Int  : tIntCtl; Ext : tExtCtl; SR : tSR);
    end;

    MicroAddr = record
        Mask, Cmp : Word;
    end;

    Str7 = String[7];

const
    Str_Source1 : array[tSource1] of Str7
    = ('ES    ','CS    ','SS    ','DS    ','PC    ','[-05-]','OPR   ','Q     ',
       'dir*sz','ZEROS ','PFXCNT','[-0B-]','tmpa  ','tmpb  ','tmpc  ','FLAGS ',
       'AL:AH ','COUNT ','R     ','M     ','SIGMA ','ONES  ','opc&38','CONST ',
       'AX    ','CX    ','DX    ','BX    ','SP    ','BP    ','SI    ','DI    ');

    Str_Dest1 : array[tDest1] of Str7
    = ('ES    ','CS    ','SS    ','DS    ','PC    ','IND   ','OPR   ','NULL  ',
       'AL    ','[-09-]','[-0A-]','[-0B-]','tmpa  ','tmpb  ','tmpc  ','FLAGS ',
       'AH    ','COUNT ','R     ','M     ','tmpaL ','tmpbL ','tmpaH ','tmpbH ',
       'AX    ','CX    ','DX    ','BX    ','SP    ','BP    ','SI    ','DI    ');

    Str_Source2 : array[tSource2] of Str7
    = ('[-00-]','[-01-]','[-02-]','[-03-]','SIGMA ','Q     ','ZEROS ','R     ',
       'AX    ','CX    ','DX    ','BX    ','SP    ','BP    ','SI    ','DI    ');

    Str_Dest2 : array[tDest2] of Str7
    = ('tmpa  ','tmpb  ','IND   ','[-03-]');

    Str_Op : array[tAluOp] of Str7
    = ('ADD   ','OR    ','ADC   ','SBB   ','AND   ','SUB   ','XOR   ','CMP   ',
       'ROL   ','ROR   ','RCL   ','RCR   ','SHL   ','SHR   ','[-0E-]','SAR   ',
       'ROL12 ','[-11-]','DIV   ','MUL   ','ADJD  ','ADJA  ','OPC   ','BIT   ',
       'INC   ','DEC   ','NOT   ','NEG   ','INC2  ','DEC2  ','[-1E-]','PASS  ');

    Str_Tmp : array[tTmpReg] of Str7
    = ('tmpa  ','tmpb  ','tmpc  ','[-03-]');

    Str_Cond : array[tCond] of Str7
    = ('[-00-]','NC    ','Z     ','NZ    ','OP8b  ','CNTZ  ','L     ','OP8   ',
       '      ','[-09-]','O     ','NS    ','REP   ','BUSY  ','INTR  ','OPC   ');

    Str_Int : array[tIntCtl] of Str7
    = ('ENDEM ','CITF  ','MFC   ','MFS   ','[-04-]','[-05-]','[-06-]','[-07-]',
       'SUSP  ','FLUSH ','[-0A-]','[-0B-]','[-0C-]','[-0D-]','FARJMP','      ');

    Str_Ext : array[tExtCtl] of Str7
    = ('[-00-]','MEMR  ','MEMW  ','[-03-]','[-04-]','[-05-]','[-06-]','      ');

    Str_SR : array[tSR] of Str7
    = ('ES    ','IO    ','SS    ','      ');

    Str_FAR : array[tFarLoc] of Str7
    = ('[-00-]','IRET  ','INT   ','INTEM ','MULADJ','MULX  ','IMUL  ','IMULI ',
       'REPX  ','SHIFT ','ENTER ','PUSHA ','POPA  ','CALLF ','INS   ','IDIV  ',
       'RETF  ','[-11-]','IDIV2 ','[-13-]','[-14-]','[-15-]','[-16-]','[-17-]',
       '[-18-]','[-19-]','[-1A-]','[-1B-]','[-1C-]','[-1D-]','[-1E-]','[-1F-]');

var
    Instrs    : array[0..RowCount-1] of MicroInstr;
    OpcMatch  : array[0..OpcCount-1] of MicroAddr;
    InF, OutF : Text;

procedure ReadBits;
var Line : String;
    Bits : LongInt;
    Adr  : MicroAddr;
    i    : Word;
    Row  : Word;

    procedure MissingOpcode;
    begin
        WriteLn('Missing / bad opcode pattern on row ',Row);
        Close(InF);
        Halt(1);
    end;

begin
    Assign(InF, InputName);
    Reset(InF);
    ReadLn(InF, Line); { skip header line }
    Row := 0;
    while not EOF(InF) and (Row <= High(Instrs)) do begin
        ReadLn(InF, Line);
        if Length(Line) >= 29 then begin
            Bits := 0;
            for i := 1 to 29 do if Line[i] = '1' then Bits := Bits or LongInt(1) shl (29-i);
            if Row mod 4 = 0 then begin
                Adr.Mask := 0;
                Adr.Cmp := 0;
                if Length(Line) >= 45 then for i := 31 to 45 do case Line[i] of
                    '0': begin
                        Adr.Mask := Adr.Mask shl 1 + 1;
                        Adr.Cmp := Adr.Cmp shl 1;
                    end;
                    '1': begin
                        Adr.Mask := Adr.Mask shl 1 + 1;
                        Adr.Cmp := Adr.Cmp shl 1 + 1;
                    end;
                    '?': begin
                        Adr.Mask := Adr.Mask shl 1;
                        Adr.Cmp := Adr.Cmp shl 1;
                    end;
                    '.': ;
                    else MissingOpcode;
                end else MissingOpcode;
                OpcMatch[Row div 4] := Adr;
            end;
            Bits := not Bits;
            with Instrs[Row] do begin
                Source1 := Bits shr 24 and 31;
                Dest1   := Bits shr 19 and 31;
                Source2 := Bits shr 15 and 15;
                Dest2   := Bits shr 13 and 3;
                Flags := [];
                if Bits and (1 shl 12) = 0 then Include(Flags,Flag_F);
                if Bits and (1 shl 11) = 0 then Include(Flags,Flag_W);
                if Bits and (1 shl 10) = 0 then Include(Flags,Flag_E);
                if Bits and (1 shl 9) <> 0 then begin
                    Include(Flags,Type_CTL);
                    Int := Bits shr 5 and 15;
                    Ext := Bits shr 2 and 7;
                    SR := Bits and 3;
                end else if Bits and (1 shl 8) <> 0 then begin
                    Include(Flags,Type_JMP);
                    Cond := Bits shr 4 and 15;
                    Loc := Bits and 15;
                end else begin
                    Include(Flags,Type_ALU);
                    Op := Bits shr 3 and 31;
                    Tmp := Bits shr 1 and 3;
                    if Bits and 1 <> 0 then Include(Flags,Flag_R);
                end;
            end;
            Inc(Row);
        end;
    end;
    Close(InF);
    WriteLn('Read ',Row,' of ',RowCount,' rows.');
end;

procedure PrintOpcode(A: MicroAddr);
var Bit : Word;
    Ch  : Char;
    Opc : tBitPattern;
begin
    Bit := 1 shl 12;
    repeat
        case Bit of
            1 shl 9, 1 shl 1: Write(OutF,'.');
        end;
        if A.Mask and Bit = 0 then Ch := '?'
        else if A.Cmp and Bit = 0 then Ch := '0' else Ch := '1';
        Write(OutF,Ch);
        Bit := Bit shr 1;
    until Bit = 0;
    Write(OutF,' ');

    { print group corresponding to top 3 bits }
    case A.Cmp shr 10 of
        0: if A.Mask shr 10 = 7 then Write(OutF,'<norep> ');
        1: Write(OutF,'<rep> ');
        2: Write(OutF,'<F6/F7> ');
        3: Write(OutF,'<FE/FF> ');
        4: Write(OutF,'<0F> ');
        5: Write(OutF,'<8080,ED> ');
        6: Write(OutF,'<8080> ');
        7: begin
            Write(OutF,'<internal> ');

            { jump target? }
            if A.Cmp and $1C = 0 then Write(OutF,Str_FAR[A.Cmp shr 5 and 31],' ');
        end;
    end;
    Opc.Mask := A.Mask shr 2 and $ff;
    Opc.Compare := A.Cmp shr 2 and $ff;
    Write(OutF,RangeStr(Opc));
end;

procedure PrintInstrs;
var
    Row : Word;
    FarLoc : tFarLoc;
begin
    Assign(OutF, OutputName);
    Rewrite(OutF);
    for Row := Low(Instrs) to High(Instrs) do with Instrs[Row] do begin
        if Row mod 4 = 0 then begin
            Write(OutF,'------- ');
            PrintOpcode(OpcMatch[Row div 4]);
            WriteLn(OutF);
        end;
        Write(OutF,HexW(Row),' ');

        { no-op if Source1 = Dest1 = $1F }
        if (Source1 <> $1F) or (Dest1 <> $1F)
            then Write(OutF,Str_Source1[Source1],' -> ',Str_Dest1[Dest1],'  ')
            else Write(OutF,'                  ');

        if Source1 = $17 then begin
            { constant value in second src/dest field }
            Write(OutF,Byte(Source2) shl 2 or Dest2:2,'                ');
        end else if (Source2 <> 15) or (Dest2 <> 3) then begin
            Write(OutF,Str_Source2[Source2],' -> ',Str_Dest2[Dest2],'  ');
        end else Write(OutF,'                  ');

        if Flag_F in Flags then Write(OutF,'F') else Write(OutF,' ');
        if Flag_W in Flags then Write(OutF,'W') else Write(OutF,' ');
        if Flag_E in Flags then Write(OutF,'E') else Write(OutF,' ');
        if Flag_R in Flags then Write(OutF,'R') else Write(OutF,' ');

        if Type_ALU in Flags then begin
            Write(OutF,' ALU ',Str_Op[Op],' ',Str_Tmp[Tmp]);
        end else if Type_JMP in Flags then begin
            Write(OutF,' JMP ',Str_Cond[Cond],' ',Loc:2);
        end else begin
            Write(OutF,' CTL ',Str_Int[Int],' ');
            if Int = $0E then begin
                { is far jump, target in place of EXT:SR fields }
                FarLoc := Byte(Ext) shl 2 or SR;
                Write(OutF,Str_FAR[FarLoc]);
            end else begin
                Write(OutF,Str_Ext[Ext],' ',Str_SR[SR]);
            end;
        end;
        WriteLn(OutF);
    end;
    Close(OutF);
end;

begin
    FillChar(Instrs,SizeOf(Instrs),0);
    FillChar(OpcMatch,SizeOf(OpcMatch),0);
    ReadBits;
    PrintInstrs;
end.
