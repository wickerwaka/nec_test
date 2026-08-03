#!/usr/bin/env python3
"""ucore table sources: the microcode ROM and the group-decode PLA.

TRANSLITERATION, not a re-derivation.  Every field position, the whole-word
inversion, the active-low F/W/E sense and the fixed-priority match resolution
below are a line-for-line transliteration of `sim/ucrom.cpp` (`UcRom::load` and
`UcRom::build_decode`), whose own normative source is `docs/V20UCDIS.PAS`
(procedure ReadBits).  The PLA reader transliterates the bit numbering
documented at the head of `sim/pla3_table.h`.

Shared by `sw/gen_ucore_tables.py` (emits the RTL artifacts) and consumed by
`sw/check_ucore_tables.py` only as the OBJECT UNDER TEST -- the checker
re-parses independently and diffs against the sim's own dump, so a bug here
cannot pass gate G0 by being consistent with itself.

Micro-address layout (`sim/ucrom.h` + `sim/state.h`):
    upc = {page[2:0], opc[7:0], rowgrp[1:0], row[1:0]}   -- 15 bits
The ACTIVATION PATTERNS are matched against the low-13-bit micro-address
{page, opc, rowgrp}; the winning bank's four rows are then indexed by `row`.
`sim/exec_impl.h:796` is the authority:
    bank = rom_.bank_of(upc.page, upc.opc, upc.rowgrp());
    op   = rom_.op(bank * 4 + upc.row());
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V20BITS = ROOT / "docs/V20BITS.TXT"
PLA3 = ROOT / "docs/pla3_outputs.txt"

OPC_COUNT = 257            # activation patterns
ROW_COUNT = OPC_COUNT * 4  # micro-instruction rows
ADDR_COUNT = 8192          # 13-bit match space {page, opc, rowgrp}
UPC_COUNT = 32768          # 15-bit micro-PC space {page, opc, rowgrp, row}

ALU, JMP, CTL = 0, 1, 2


class MicroOp:
    """One 29-bit micro-instruction row, decoded exactly as sim/ucrom.cpp."""

    __slots__ = ("rom_addr", "word29", "s1", "d1", "s2", "d2", "f", "w", "e",
                 "r", "type", "alu_op", "alu_tmp", "cond", "loc", "ictl",
                 "ectl", "sr")

    def __init__(self, row, bits):
        # `bits` is the POST-INVERSION 29-bit word (sim: `bits = ~bits`).
        self.rom_addr = row
        self.word29 = bits
        self.s1 = (bits >> 24) & 31
        self.d1 = (bits >> 19) & 31
        self.s2 = (bits >> 15) & 15
        self.d2 = (bits >> 13) & 3
        # F/W/E are active-low in the raw word; after inversion the flag is
        # SET when the inverted bit is CLEAR.
        self.f = (bits & (1 << 12)) == 0
        self.w = (bits & (1 << 11)) == 0
        self.e = (bits & (1 << 10)) == 0
        self.r = False
        self.alu_op = self.alu_tmp = self.cond = self.loc = 0
        self.ictl = self.ectl = self.sr = 0
        if bits & (1 << 9):
            self.type = CTL
            self.ictl = (bits >> 5) & 15
            self.ectl = (bits >> 2) & 7
            self.sr = bits & 3
        elif bits & (1 << 8):
            self.type = JMP
            self.cond = (bits >> 4) & 15
            self.loc = bits & 15
        else:
            self.type = ALU
            self.alu_op = (bits >> 3) & 31
            self.alu_tmp = (bits >> 1) & 3
            self.r = (bits & 1) != 0


class MatchPat:
    """13-bit activation pattern: matches when (addr & mask) == cmp."""

    __slots__ = ("mask", "cmp")

    def __init__(self, mask=0, cmp=0):
        self.mask = mask
        self.cmp = cmp

    def matches(self, addr):
        return (addr & self.mask) == self.cmp


class UcRom:
    def __init__(self, path=V20BITS):
        self.ops = [None] * ROW_COUNT
        self.pats = [MatchPat() for _ in range(OPC_COUNT)]
        self.rows_read = 0
        self.pats_read = 0
        self._load(Path(path))
        self._build_decode()

    # --- parse (transliterates UcRom::load) --------------------------------
    def _load(self, path):
        raw = path.read_bytes().decode("latin-1").split("\n")
        raw = [ln.rstrip("\r") for ln in raw]
        if not raw:
            raise ValueError("empty input")
        lines = raw[1:]  # skip header line

        row = 0
        for line in lines:
            if row >= ROW_COUNT:
                break
            if len(line) < 29:
                continue  # Pascal: `if Length(Line) >= 29`
            bits = 0
            for i in range(29):
                if line[i] == "1":
                    bits |= 1 << (28 - i)

            if row % 4 == 0:
                if len(line) < 45:
                    raise ValueError(
                        f"Missing / bad opcode pattern on row {row}")
                mask = cmp = 0
                for i in range(30, 45):
                    c = line[i]
                    if c == "0":
                        mask = ((mask << 1) | 1) & 0xFFFF
                        cmp = (cmp << 1) & 0xFFFF
                    elif c == "1":
                        mask = ((mask << 1) | 1) & 0xFFFF
                        cmp = ((cmp << 1) | 1) & 0xFFFF
                    elif c == "?":
                        mask = (mask << 1) & 0xFFFF
                        cmp = (cmp << 1) & 0xFFFF
                    elif c == ".":
                        pass  # separator, contributes nothing
                    else:
                        raise ValueError(
                            f"Missing / bad opcode pattern on row {row}")
                self.pats[row // 4] = MatchPat(mask, cmp)
                self.pats_read += 1

            bits = (~bits) & 0x1FFFFFFF  # Pascal: `Bits := not Bits`
            self.ops[row] = MicroOp(row, bits)
            row += 1

        self.rows_read = row
        if row < ROW_COUNT:
            raise ValueError(f"short ROM: {row} of {ROW_COUNT} rows")

    # --- decode (transliterates UcRom::build_decode) -----------------------
    def _build_decode(self):
        # bank_first / bank_alt indexed by the 13-bit micro-address.
        self.bank_first = [-1] * ADDR_COUNT
        self.bank_alt = [-1] * ADDR_COUNT
        self.unmapped = 0
        self.ambiguous = []
        for addr in range(ADDR_COUNT):
            hits = 0
            for b, p in enumerate(self.pats):
                if not p.matches(addr):
                    continue
                if hits == 0:
                    self.bank_first[addr] = b
                elif hits == 1:
                    self.bank_alt[addr] = b
                hits += 1
            if hits == 0:
                self.unmapped += 1
            if hits > 1:
                self.ambiguous.append(addr)

    def bank_of(self, addr, emu=False):
        """sim/ucrom.h::bank_of -- native mode takes the SECOND match."""
        alt = self.bank_alt[addr]
        if not emu and alt >= 0:
            return alt
        return self.bank_first[addr]


# --- PLA3 -------------------------------------------------------------------
PLA_SECTIONS = ("native opcodes", "8080 opcodes", "ext opcodes")
PLA_NAMES = {"native opcodes": "native", "8080 opcodes": "mode8080",
             "ext opcodes": "ext"}


def load_pla3(path=PLA3):
    """3 x 256 x 14b vectors.  Bit numbering per sim/pla3_table.h: the dump
    prints the vector MSB-first as b0..b13 and b0 is stored in bit 13."""
    sections = {}
    cur = None
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line in PLA_SECTIONS:
            cur = PLA_NAMES[line]
            sections[cur] = [None] * 256
            continue
        if cur is None:
            raise ValueError(f"data before any section header: {line!r}")
        op_s, bits_s = line.split()
        if len(bits_s) != 14 or set(bits_s) - set("01"):
            raise ValueError(f"bad PLA row {line!r}")
        v = 0
        for i, c in enumerate(bits_s):
            if c == "1":
                v |= 1 << (13 - i)
        idx = int(op_s, 16)
        if sections[cur][idx] is not None:
            raise ValueError(f"duplicate opcode {op_s} in {cur}")
        sections[cur][idx] = v
    for name in PLA_NAMES.values():
        if name not in sections or any(v is None for v in sections[name]):
            raise ValueError(f"PLA section {name} incomplete")
    return sections
