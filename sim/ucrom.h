// ucrom.h -- NEC V20/V30 EU microcode ROM decoder.
//
// NORMATIVE SOURCE: docs/V20UCDIS.PAS (Turbo Pascal microcode disassembler,
// with docs/HEXRANGE.PAS for the opcode-range printer).  Every field position,
// the whole-word inversion (`Bits := not Bits`), the active-low F/W/E flag
// sense, the type selection order (CTL before JMP before ALU), the CONST
// convention (Source1 == 0x17), the no-op convention (Source1 == Dest1 ==
// 0x1F) and the FARJMP aliasing of Ext:SR (Int == 0x0E) are transliterated
// from that program.  Raw ROM bits come from docs/V20BITS.TXT; the golden
// disassembly is docs/V20UC.TXT.
//
// Micro-address layout (13 bits, from the activation-pattern column):
//     [12:10] page   (0=norep, 1=rep, 2=F6/F7, 3=FE/FF, 4=0F,
//                     5=8080/ED, 6=8080, 7=internal)
//     [ 9: 2] opcode byte
//     [ 1: 0] row within the 4-row micro-instruction bank

#ifndef UCROM_H
#define UCROM_H

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace ucrom {

constexpr int kOpcCount = 257;             // activation patterns
constexpr int kRowCount = kOpcCount * 4;   // micro-instruction rows

enum class MicroType : uint8_t { ALU, JMP, CTL };

struct MicroOp {
    uint16_t rom_addr = 0;  // row index within the ROM image (0..kRowCount-1)

    uint8_t s1 = 0;  // Source1, 5 bits
    uint8_t d1 = 0;  // Dest1,   5 bits
    uint8_t s2 = 0;  // Source2, 4 bits
    uint8_t d2 = 0;  // Dest2,   2 bits

    bool f = false;  // update flags source
    bool w = false;  // write flags
    bool e = false;  // end of instruction
    bool r = false;  // repeat ALU instruction (ALU rows only)

    MicroType type = MicroType::ALU;

    uint8_t alu_op = 0;   // ALU: operation, 5 bits
    uint8_t alu_tmp = 0;  // ALU: temp register, 2 bits

    uint8_t cond = 0;  // JMP: condition, 4 bits
    uint8_t loc = 0;   // JMP: target, 4 bits

    uint8_t ictl = 0;  // CTL: internal control, 4 bits
    uint8_t ectl = 0;  // CTL: external control, 3 bits
    uint8_t sr = 0;    // CTL: segment register, 2 bits

    // CTL with ictl == 0x0E is a far jump; ectl:sr holds the 5-bit target.
    bool is_farjmp() const { return type == MicroType::CTL && ictl == 0x0E; }
    uint8_t far_loc() const { return uint8_t((ectl << 2) | sr); }

    // Row is a no-op move if Source1 == Dest1 == 0x1F.
    bool nop_move() const { return s1 == 0x1F && d1 == 0x1F; }
    // Source1 == 0x17 repurposes Source2:Dest2 as a 6-bit constant.
    bool has_const() const { return s1 == 0x17; }
    uint8_t const_val() const { return uint8_t((s2 << 2) | d2); }
};

// 13-bit micro-address match pattern: address matches when (a & mask) == cmp.
struct MatchPat {
    uint16_t mask = 0;
    uint16_t cmp = 0;

    bool matches(uint16_t addr) const { return (addr & mask) == cmp; }
    uint8_t page() const { return uint8_t((cmp >> 10) & 7); }
    // Opcode-byte mask/compare (bits 9..2), as used by the range printer.
    uint8_t opc_mask() const { return uint8_t((mask >> 2) & 0xFF); }
    uint8_t opc_cmp() const { return uint8_t((cmp >> 2) & 0xFF); }
};

class UcRom {
public:
    // Parses V20BITS.TXT.  Returns false and fills `err` on failure.
    bool load(const std::string& path, std::string& err);

    int rows_read() const { return rows_read_; }
    int pats_read() const { return pats_read_; }

    const std::vector<MicroOp>& ops() const { return ops_; }
    const std::vector<MatchPat>& pats() const { return pats_; }

    const MicroOp& op(int row) const { return ops_[size_t(row)]; }
    const MatchPat& pat(int bank) const { return pats_[size_t(bank)]; }

    // Precomputed micro-address decode: bank index, or -1 if unmapped.
    int bank_of(int page, int opc, int row) const {
        return bank_of_[page][opc][row];
    }

    // Returns the micro-instruction at (page, opcode, row), or nullptr when
    // that micro-address is not covered by any activation pattern.
    const MicroOp* fetch(int page, int opc_byte, int row) const {
        int b = bank_of_[page][opc_byte][row];
        if (b < 0) return nullptr;
        return &ops_[size_t(b * 4 + row)];
    }

    // Diagnostics from the decode-table build.
    int unmapped_addrs() const { return unmapped_; }
    int ambiguous_addrs() const { return ambiguous_; }

private:
    void build_decode();

    std::vector<MicroOp> ops_;
    std::vector<MatchPat> pats_;
    int rows_read_ = 0;
    int pats_read_ = 0;
    int unmapped_ = 0;
    int ambiguous_ = 0;
    // [page][opcode byte][row] -> bank index (-1 = unmapped)
    int16_t bank_of_[8][256][4];
};

// Field-name tables (6 characters each), exactly as in V20UCDIS.PAS.
extern const char* const kStrSource1[32];
extern const char* const kStrDest1[32];
extern const char* const kStrSource2[16];
extern const char* const kStrDest2[4];
extern const char* const kStrOp[32];
extern const char* const kStrTmp[4];
extern const char* const kStrCond[16];
extern const char* const kStrInt[16];
extern const char* const kStrExt[8];
extern const char* const kStrSR[4];
extern const char* const kStrFar[32];

}  // namespace ucrom

#endif  // UCROM_H
