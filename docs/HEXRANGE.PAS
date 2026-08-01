unit HexRange;

{
  - Number -> Hex string
  - Pretty-print ranges
    - mask $FF, cmp $63 => '63'
    - mask $FE, cmp $AA => 'AA,AB'
    - mask $F0, cmp $70 => '70..7F'
    - mask $D0, cmp $10 => '10..1F,30..3F'
    - mask $55, cmp $00 => 'x0x0x0x0'
}

interface

type
    Str2 = String[2];
    Str4 = String[4];
    Str8 = String[8];

    tBitPattern = record
        Mask, Compare : Byte;
    end;

function HexB(B: Byte): Str2;
function HexW(W: Word): Str4;
function HexL(L: LongInt): Str8;

{ Return first value matching pattern (trivial) }
function FirstMatch(Pat: tBitPattern): Byte;

{ Return last value matching pattern (trivial) }
function LastMatch(Pat: tBitPattern): Byte;

{ Return next value matching pattern, or 0 }
function NextMatch(Pat: tBitPattern; Prev: Byte): Byte;

{ Return previous value matching pattern, wrapping around to last }
function PrevMatch(Pat: tBitPattern; Next: Byte): Byte;

{ Return number of matching values }
function CountMatches(Pat: tBitPattern): Word;

{ Convert pattern to string of 0/1/x }
function BitStr(Pat: tBitPattern): Str8;

{ Convert pattern to list of hex values/ranges if possible }
function RangeStr(Pat: tBitPattern): String;

implementation

const
    Digits : array [0..15] of Char = '0123456789ABCDEF';

function HexB(B: Byte): Str2;
begin
    HexB := Digits[B shr 4] + Digits[B and 15];
end;

function HexW(W: Word): Str4;
begin
    HexW := Digits[Hi(W) shr 4] + Digits[Hi(W) and 15]
            + Digits[Lo(W) shr 4] + Digits[Lo(W) and 15];
end;

function HexL(L: LongInt): Str8;
begin
    HexL := HexW(L shr 16) + HexW(L and $ffff);
end;

function FirstMatch(Pat: tBitPattern): Byte;
begin
    FirstMatch := Pat.Compare;
end;

function LastMatch(Pat: tBitPattern): Byte;
begin
    LastMatch := Pat.Compare or not Pat.Mask;
end;

function NextMatch(Pat: tBitPattern; Prev: Byte): Byte;
var Next: Byte;
begin
    Next := ((Prev or Pat.Mask)+1) and not Pat.Mask;
    if Next <> 0 then Next := Next or Pat.Compare;
    NextMatch := Next;
end;

function PrevMatch(Pat: tBitPattern; Next: Byte): Byte;
begin
    PrevMatch := ((Next and not Pat.Mask)-1) and not Pat.Mask or Pat.Compare;
end;

function CountMatches(Pat: tBitPattern): Word;
var InvMask : Byte;
    BitCnt  : Byte;
begin
    InvMask := not Pat.Mask;
    BitCnt := 0;
    while InvMask <> 0 do begin
        Inc(BitCnt);
        InvMask := InvMask and (InvMask-1);
    end;
    CountMatches := 1 shl BitCnt;
end;

function BitStr(Pat: tBitPattern): Str8;
var Result : Str8;
    BitPos : Byte;
begin
    Result := 'xxxxxxxx';
    for BitPos := 7 downto 0 do if Pat.Mask and (1 shl BitPos) <> 0 then begin
        Result[8-BitPos] := Chr(Ord('0')+Pat.Compare shr BitPos and 1);
    end;
    BitStr := Result;
end;

function RangeStr(Pat: tBitPattern): String;
var Result      : String;
    UpperPat    : tBitPattern;
    SubRangeHi  : Byte;
begin
    if Pat.Mask = 0 then SubRangeHi := $ff else begin
        SubRangeHi := 1;
        while Pat.Mask and SubRangeHi = 0 do SubRangeHi := SubRangeHi*2 + 1;
        SubRangeHi := SubRangeHi shr 1;
    end;
    UpperPat.Mask := Pat.Mask or SubRangeHi;
    UpperPat.Compare := Pat.Compare;
    if CountMatches(UpperPat) > 8 then Result := BitStr(Pat) else begin
        Result := '';
        repeat
            Result := Result + HexB(Pat.Compare);
            if SubRangeHi > 0 then begin
                if SubRangeHi = 1
                    then Result := Result + ','
                    else Result := Result + '..';
                Result := Result + HexB(Pat.Compare+SubRangeHi);
            end;
            Pat.Compare := NextMatch(UpperPat, Pat.Compare);
            if Pat.Compare <> 0 then Result := Result + ',';
        until Pat.Compare = 0;
    end;
    RangeStr := Result;
end;

end.
