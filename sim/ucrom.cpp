// ucrom.cpp -- microcode ROM loader.  See ucrom.h; normative spec is
// docs/V20UCDIS.PAS (procedure ReadBits).

#include "ucrom.h"

#include <cstdio>
#include <fstream>

namespace ucrom {

const char* const kStrSource1[32] = {
    "ES    ", "CS    ", "SS    ", "DS    ", "PC    ", "[-05-]", "OPR   ", "Q     ",
    "dir*sz", "ZEROS ", "PFXCNT", "[-0B-]", "tmpa  ", "tmpb  ", "tmpc  ", "FLAGS ",
    "AL:AH ", "COUNT ", "R     ", "M     ", "SIGMA ", "ONES  ", "opc&38", "CONST ",
    "AX    ", "CX    ", "DX    ", "BX    ", "SP    ", "BP    ", "SI    ", "DI    "};

const char* const kStrDest1[32] = {
    "ES    ", "CS    ", "SS    ", "DS    ", "PC    ", "IND   ", "OPR   ", "NULL  ",
    "AL    ", "[-09-]", "[-0A-]", "[-0B-]", "tmpa  ", "tmpb  ", "tmpc  ", "FLAGS ",
    "AH    ", "COUNT ", "R     ", "M     ", "tmpaL ", "tmpbL ", "tmpaH ", "tmpbH ",
    "AX    ", "CX    ", "DX    ", "BX    ", "SP    ", "BP    ", "SI    ", "DI    "};

const char* const kStrSource2[16] = {
    "[-00-]", "[-01-]", "[-02-]", "[-03-]", "SIGMA ", "Q     ", "ZEROS ", "R     ",
    "AX    ", "CX    ", "DX    ", "BX    ", "SP    ", "BP    ", "SI    ", "DI    "};

const char* const kStrDest2[4] = {"tmpa  ", "tmpb  ", "IND   ", "[-03-]"};

const char* const kStrOp[32] = {
    "ADD   ", "OR    ", "ADC   ", "SBB   ", "AND   ", "SUB   ", "XOR   ", "CMP   ",
    "ROL   ", "ROR   ", "RCL   ", "RCR   ", "SHL   ", "SHR   ", "[-0E-]", "SAR   ",
    "ROL12 ", "[-11-]", "DIV   ", "MUL   ", "ADJD  ", "ADJA  ", "OPC   ", "BIT   ",
    "INC   ", "DEC   ", "NOT   ", "NEG   ", "INC2  ", "DEC2  ", "[-1E-]", "PASS  "};

const char* const kStrTmp[4] = {"tmpa  ", "tmpb  ", "tmpc  ", "[-03-]"};

const char* const kStrCond[16] = {
    "[-00-]", "NC    ", "Z     ", "NZ    ", "OP8b  ", "CNTZ  ", "L     ", "OP8   ",
    "      ", "[-09-]", "O     ", "NS    ", "REP   ", "BUSY  ", "INTR  ", "OPC   "};

const char* const kStrInt[16] = {
    "ENDEM ", "CITF  ", "MFC   ", "MFS   ", "[-04-]", "[-05-]", "[-06-]", "[-07-]",
    "SUSP  ", "FLUSH ", "[-0A-]", "[-0B-]", "[-0C-]", "[-0D-]", "FARJMP", "      "};

const char* const kStrExt[8] = {"[-00-]", "MEMR  ", "MEMW  ", "[-03-]",
                                "[-04-]", "[-05-]", "[-06-]", "      "};

const char* const kStrSR[4] = {"ES    ", "IO    ", "SS    ", "      "};

const char* const kStrFar[32] = {
    "[-00-]", "IRET  ", "INT   ", "INTEM ", "MULADJ", "MULX  ", "IMUL  ", "IMULI ",
    "REPX  ", "SHIFT ", "ENTER ", "PUSHA ", "POPA  ", "CALLF ", "INS   ", "IDIV  ",
    "RETF  ", "[-11-]", "IDIV2 ", "[-13-]", "[-14-]", "[-15-]", "[-16-]", "[-17-]",
    "[-18-]", "[-19-]", "[-1A-]", "[-1B-]", "[-1C-]", "[-1D-]", "[-1E-]", "[-1F-]"};

static void strip_eol(std::string& s) {
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
}

bool UcRom::load(const std::string& path, std::string& err) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        err = "cannot open " + path;
        return false;
    }

    ops_.assign(kRowCount, MicroOp{});
    pats_.assign(kOpcCount, MatchPat{});
    rows_read_ = 0;
    pats_read_ = 0;

    std::string line;
    if (!std::getline(in, line)) {  // skip header line
        err = "empty input";
        return false;
    }

    int row = 0;
    while (row < kRowCount && std::getline(in, line)) {
        strip_eol(line);
        if (line.size() < 29) continue;  // Pascal: `if Length(Line) >= 29`

        // Micro-word: 29 chars, MSB first, then inverted as a whole.
        uint32_t bits = 0;
        for (int i = 0; i < 29; ++i)
            if (line[size_t(i)] == '1') bits |= 1u << (28 - i);

        if (row % 4 == 0) {
            // Activation pattern at columns 31..45 (1-based).
            if (line.size() < 45) {
                char buf[80];
                std::snprintf(buf, sizeof buf,
                              "Missing / bad opcode pattern on row %d", row);
                err = buf;
                return false;
            }
            MatchPat adr{};
            for (int i = 30; i < 45; ++i) {
                char c = line[size_t(i)];
                if (c == '0') {
                    adr.mask = uint16_t(adr.mask << 1 | 1);
                    adr.cmp = uint16_t(adr.cmp << 1);
                } else if (c == '1') {
                    adr.mask = uint16_t(adr.mask << 1 | 1);
                    adr.cmp = uint16_t(adr.cmp << 1 | 1);
                } else if (c == '?') {
                    adr.mask = uint16_t(adr.mask << 1);
                    adr.cmp = uint16_t(adr.cmp << 1);
                } else if (c == '.') {
                    // separator, contributes nothing
                } else {
                    char buf[80];
                    std::snprintf(buf, sizeof buf,
                                  "Missing / bad opcode pattern on row %d", row);
                    err = buf;
                    return false;
                }
            }
            pats_[size_t(row / 4)] = adr;
            ++pats_read_;
        }

        bits = ~bits;  // Pascal: `Bits := not Bits`

        MicroOp& m = ops_[size_t(row)];
        m.rom_addr = uint16_t(row);
        m.s1 = uint8_t((bits >> 24) & 31);
        m.d1 = uint8_t((bits >> 19) & 31);
        m.s2 = uint8_t((bits >> 15) & 15);
        m.d2 = uint8_t((bits >> 13) & 3);
        // F/W/E are active-low in the raw word; after inversion the Pascal
        // tests `= 0`, i.e. the flag is set when the inverted bit is clear.
        m.f = (bits & (1u << 12)) == 0;
        m.w = (bits & (1u << 11)) == 0;
        m.e = (bits & (1u << 10)) == 0;
        if (bits & (1u << 9)) {
            m.type = MicroType::CTL;
            m.ictl = uint8_t((bits >> 5) & 15);
            m.ectl = uint8_t((bits >> 2) & 7);
            m.sr = uint8_t(bits & 3);
        } else if (bits & (1u << 8)) {
            m.type = MicroType::JMP;
            m.cond = uint8_t((bits >> 4) & 15);
            m.loc = uint8_t(bits & 15);
        } else {
            m.type = MicroType::ALU;
            m.alu_op = uint8_t((bits >> 3) & 31);
            m.alu_tmp = uint8_t((bits >> 1) & 3);
            m.r = (bits & 1) != 0;
        }
        ++row;
    }

    rows_read_ = row;
    build_decode();
    return true;
}

void UcRom::build_decode() {
    for (int p = 0; p < 8; ++p)
        for (int o = 0; o < 256; ++o)
            for (int r = 0; r < 4; ++r) {
                bank_of_[p][o][r] = -1;
                bank_alt_[p][o][r] = -1;
            }

    unmapped_ = 0;
    ambiguous_ = 0;
    for (int addr = 0; addr < 8192; ++addr) {
        int page = (addr >> 10) & 7;
        int opc = (addr >> 2) & 0xFF;
        int row = addr & 3;
        int hits = 0;
        for (size_t b = 0; b < pats_.size(); ++b) {
            if (!pats_[b].matches(uint16_t(addr))) continue;
            if (hits == 0) bank_of_[page][opc][row] = int16_t(b);
            else if (hits == 1) bank_alt_[page][opc][row] = int16_t(b);
            ++hits;
        }
        if (hits == 0) ++unmapped_;
        if (hits > 1) ++ambiguous_;
    }
}

}  // namespace ucrom
