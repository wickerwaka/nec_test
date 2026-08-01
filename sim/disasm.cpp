// disasm.cpp -- reproduces docs/V20UC.TXT from docs/V20BITS.TXT.
//
// Transliteration of PrintOpcode / PrintInstrs in docs/V20UCDIS.PAS and of
// RangeStr / BitStr / HexB / HexW in docs/HEXRANGE.PAS.  Output uses CRLF
// line endings, as Turbo Pascal's WriteLn does on DOS.

#include "disasm.h"

#include <cstdio>
#include <string>

#include "ucrom.h"

namespace ucrom {
namespace {

const char kDigits[] = "0123456789ABCDEF";

std::string hex_b(uint8_t b) {
    return std::string{kDigits[b >> 4], kDigits[b & 15]};
}

std::string hex_w(uint16_t w) {
    return std::string{kDigits[(w >> 12) & 15], kDigits[(w >> 8) & 15],
                       kDigits[(w >> 4) & 15], kDigits[w & 15]};
}

struct BitPattern {
    uint8_t mask;
    uint8_t compare;
};

uint8_t next_match(BitPattern p, uint8_t prev) {
    int next = ((prev | p.mask) + 1) & (~p.mask & 0xFF);
    next &= 0xFF;
    if (next != 0) next |= p.compare;
    return uint8_t(next);
}

unsigned count_matches(BitPattern p) {
    uint8_t inv = uint8_t(~p.mask);
    unsigned bits = 0;
    while (inv != 0) {
        ++bits;
        inv = uint8_t(inv & (inv - 1));
    }
    return 1u << bits;
}

std::string bit_str(BitPattern p) {
    std::string r = "xxxxxxxx";
    for (int pos = 7; pos >= 0; --pos)
        if (p.mask & (1u << pos)) r[size_t(7 - pos)] = char('0' + ((p.compare >> pos) & 1));
    return r;
}

// HEXRANGE.PAS RangeStr: renders a mask/compare pair as a hex value list.
std::string range_str(BitPattern p) {
    uint8_t sub_hi;
    if (p.mask == 0) {
        sub_hi = 0xFF;
    } else {
        unsigned s = 1;
        while ((p.mask & s) == 0) s = s * 2 + 1;
        sub_hi = uint8_t(s >> 1);
    }
    BitPattern upper{uint8_t(p.mask | sub_hi), p.compare};
    if (count_matches(upper) > 8) return bit_str(p);

    std::string r;
    do {
        r += hex_b(p.compare);
        if (sub_hi > 0) {
            r += (sub_hi == 1) ? "," : "..";
            r += hex_b(uint8_t(p.compare + sub_hi));
        }
        p.compare = next_match(upper, p.compare);
        if (p.compare != 0) r += ',';
    } while (p.compare != 0);
    return r;
}

// V20UCDIS.PAS PrintOpcode.
std::string print_opcode(const MatchPat& a) {
    std::string r;
    for (int bit = 12; bit >= 0; --bit) {
        if (bit == 9 || bit == 1) r += '.';
        unsigned m = 1u << bit;
        if ((a.mask & m) == 0)
            r += '?';
        else
            r += ((a.cmp & m) == 0) ? '0' : '1';
    }
    r += ' ';

    switch ((a.cmp >> 10) & 7) {
        case 0:
            if ((a.mask >> 10) == 7) r += "<norep> ";
            break;
        case 1: r += "<rep> "; break;
        case 2: r += "<F6/F7> "; break;
        case 3: r += "<FE/FF> "; break;
        case 4: r += "<0F> "; break;
        case 5: r += "<8080,ED> "; break;
        case 6: r += "<8080> "; break;
        case 7:
            r += "<internal> ";
            // Far-jump target naming: only when the low target bits are clear.
            if ((a.cmp & 0x1C) == 0) {
                r += kStrFar[(a.cmp >> 5) & 31];
                r += ' ';
            }
            break;
        default: break;
    }
    r += range_str(BitPattern{a.opc_mask(), a.opc_cmp()});
    return r;
}

}  // namespace

// V20UCDIS.PAS PrintInstrs.
void disassemble(const UcRom& rom, FILE* out) {
    char num[8];
    for (int row = 0; row < rom.rows_read(); ++row) {
        const MicroOp& m = rom.op(row);
        std::string line;

        if (row % 4 == 0) {
            std::string hdr = "------- ";
            hdr += print_opcode(rom.pat(row / 4));
            hdr += "\r\n";
            std::fwrite(hdr.data(), 1, hdr.size(), out);
        }

        line += hex_w(uint16_t(row));
        line += ' ';

        if (!m.nop_move()) {
            line += kStrSource1[m.s1];
            line += " -> ";
            line += kStrDest1[m.d1];
            line += "  ";
        } else {
            line += "                  ";
        }

        if (m.has_const()) {
            std::snprintf(num, sizeof num, "%2d", m.const_val());
            line += num;
            line += "                ";
        } else if (m.s2 != 15 || m.d2 != 3) {
            line += kStrSource2[m.s2];
            line += " -> ";
            line += kStrDest2[m.d2];
            line += "  ";
        } else {
            line += "                  ";
        }

        line += m.f ? 'F' : ' ';
        line += m.w ? 'W' : ' ';
        line += m.e ? 'E' : ' ';
        line += m.r ? 'R' : ' ';

        if (m.type == MicroType::ALU) {
            line += " ALU ";
            line += kStrOp[m.alu_op];
            line += ' ';
            line += kStrTmp[m.alu_tmp];
        } else if (m.type == MicroType::JMP) {
            line += " JMP ";
            line += kStrCond[m.cond];
            line += ' ';
            std::snprintf(num, sizeof num, "%2d", m.loc);
            line += num;
        } else {
            line += " CTL ";
            line += kStrInt[m.ictl];
            line += ' ';
            if (m.is_farjmp()) {
                line += kStrFar[m.far_loc()];
            } else {
                line += kStrExt[m.ectl];
                line += ' ';
                line += kStrSR[m.sr];
            }
        }

        line += "\r\n";
        std::fwrite(line.data(), 1, line.size(), out);
    }
}

}  // namespace ucrom
