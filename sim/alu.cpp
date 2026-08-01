// alu.cpp -- see alu.h.

#include "alu.h"

namespace sim {

namespace {

inline uint16_t parity8(uint16_t r) {
    uint8_t v = uint8_t(r & 0xFF);
    v ^= uint8_t(v >> 4);
    v ^= uint8_t(v >> 2);
    v ^= uint8_t(v >> 1);
    return (v & 1) ? 0 : kFlagP;  // even parity -> P = 1
}

inline uint16_t szp(uint32_t r, bool byte) {
    uint16_t f = 0;
    uint32_t mask = byte ? 0xFFu : 0xFFFFu;
    uint32_t msb = byte ? 0x80u : 0x8000u;
    if ((r & mask) == 0) f |= kFlagZ;
    if (r & msb) f |= kFlagS;
    f |= parity8(uint16_t(r));
    return f;
}

constexpr uint16_t kArithMask =
    kFlagCY | kFlagP | kFlagAC | kFlagZ | kFlagS | kFlagV;

}  // namespace

uint8_t alu_opc_select(const Machine& m) {
    uint8_t sel = uint8_t((m.opc_reg >> 3) & 7);
    if (m.incdec_class) return uint8_t(kInc + (sel & 1));  // INC / DEC
    return sel;  // ADD OR ADC SBB AND SUB XOR CMP == kStrOp[0..7]
}

AluResult alu_eval(const Machine& m, const AluLatch& lat) {
    AluResult res;
    if (lat.ea_const) {
        res.value = lat.ea_value;
        res.flag_mask = 0;
        return res;
    }

    uint8_t op = lat.op;
    if (op == kOpc) op = alu_opc_select(m);

    // The datapath is 16 bits wide ALWAYS; `byte` selects only where the flag
    // taps sit.  (Forced by the string blocks: MOVBK/CMPBK are byte-width
    // instructions whose SI/DI updates go through the same ALU and must be
    // 16-bit -- see the ledger, "ALU width".)  So the RESULT is computed on
    // the full registers and the FLAGS on the width-masked operands.
    bool byte = lat.byte && op != kInc2 && op != kDec2;
    const uint16_t tmps[4] = {m.tmpa, m.tmpb, m.tmpc, 0};
    uint32_t af = m.tmpb;                     // port A
    uint32_t bf = tmps[lat.tmp & 3];          // port B
    uint32_t mask = byte ? 0xFFu : 0xFFFFu;
    uint32_t msb = byte ? 0x80u : 0x8000u;
    uint32_t a = af & mask;
    uint32_t b = bf & mask;
    uint32_t rfull = 0;
    uint32_t r = 0;
    uint16_t f = 0;
    uint16_t fm = 0;
    uint32_t cin = (m.psw & kFlagCY) ? 1u : 0u;

    switch (op) {
        case kAdd:
        case kAdc: {
            uint32_t c = (op == kAdc) ? cin : 0u;
            r = a + b + c;
            rfull = af + bf + c;
            fm = kArithMask;
            if (r & (mask + 1)) f |= kFlagCY;
            if ((a ^ b ^ r) & 0x10u) f |= kFlagAC;
            if ((~(a ^ b) & (a ^ r)) & msb) f |= kFlagV;
            f |= szp(r, byte);
            break;
        }
        case kSub:
        case kSbb:
        case kCmp: {
            uint32_t c = (op == kSbb) ? cin : 0u;
            r = a - b - c;
            rfull = af - bf - c;
            fm = kArithMask;
            if (r & (mask + 1)) f |= kFlagCY;
            if ((a ^ b ^ r) & 0x10u) f |= kFlagAC;
            if (((a ^ b) & (a ^ r)) & msb) f |= kFlagV;
            f |= szp(r, byte);
            if (op == kCmp) res.commits = false;
            break;
        }
        case kAnd:
        case kOr:
        case kXor: {
            r = (op == kAnd) ? (a & b) : (op == kOr) ? (a | b) : (a ^ b);
            rfull = (op == kAnd) ? (af & bf) : (op == kOr) ? (af | bf) : (af ^ bf);
            fm = kArithMask;
            // MEASURED (docs/facts/undefined_flags.md): AC always 0 for the
            // logic ops; CY and V always 0 (documented).
            f |= szp(r, byte);
            break;
        }
        case kInc: {
            r = b + 1u;
            rfull = bf + 1u;
            fm = kFlagP | kFlagAC | kFlagZ | kFlagS | kFlagV;  // CY preserved
            if ((b ^ 1u ^ r) & 0x10u) f |= kFlagAC;
            if ((~(b ^ 1u) & (b ^ r)) & msb) f |= kFlagV;
            f |= szp(r, byte);
            break;
        }
        case kDec: {
            r = b - 1u;
            rfull = bf - 1u;
            fm = kFlagP | kFlagAC | kFlagZ | kFlagS | kFlagV;  // CY preserved
            if ((b ^ 1u ^ r) & 0x10u) f |= kFlagAC;
            if (((b ^ 1u) & (b ^ r)) & msb) f |= kFlagV;
            f |= szp(r, byte);
            break;
        }
        case kInc2:
            r = b + 2u;
            rfull = bf + 2u;
            fm = 0;
            break;
        case kDec2:
            r = b - 2u;
            rfull = bf - 2u;
            fm = 0;
            break;
        case kNot:
            r = ~b;
            rfull = ~bf;
            fm = 0;  // V30 NOT touches no flags
            break;
        case kNeg:
            r = 0u - b;
            rfull = 0u - bf;
            fm = kArithMask;
            if ((r & mask) != 0) f |= kFlagCY;
            if ((b ^ r) & 0x10u) f |= kFlagAC;
            if (b == msb) f |= kFlagV;
            f |= szp(r, byte);
            break;
        case kPass:
        default:
            r = b;
            rfull = bf;
            fm = 0;
            break;
    }

    res.value = uint16_t(rfull & 0xFFFFu);
    res.flags = f;
    res.flag_mask = fm;
    return res;
}

}  // namespace sim
