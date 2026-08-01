// state.h -- V30 machine state as the microcode sees it.
//
// Register ORDER is dictated by the microcode field encodings in
// docs/V20UCDIS.PAS (transcribed into ucrom.cpp):
//   Source1/Dest1 24..31 = AX CX DX BX SP BP SI DI   (kStrSource1)
//   Source1/Dest1  0.. 3 = ES CS SS DS               (kStrSource1)
// so gpr[]/sreg[] are indexed directly by the ROM field value.
//
// Provenance for every semantic decision: docs/notes/ucsim_provenance.md.

#ifndef STATE_H
#define STATE_H

#include <cstdint>

namespace sim {

// --- register indices (== microcode Source1/Dest1 field values) -------------
enum Gpr : uint8_t { kAW = 0, kCW, kDW, kBW, kSP, kBP, kIX, kIY };
enum Sreg : uint8_t { kES = 0, kCS, kSS, kDS };
// synthetic segment index: physical address = offset (interrupt-vector fetch)
constexpr uint8_t kSegZero = 4;

// --- PSW ------------------------------------------------------------------
// V30 raw PSW: bit1 and bits 15:12 read as 1, bits 5 and 3 as 0.
constexpr uint16_t kPswWritable = 0x0FD5;
constexpr uint16_t kPswForced = 0xF002;

enum PswBit : uint16_t {
    kFlagCY = 1u << 0,
    kFlagP = 1u << 2,
    kFlagAC = 1u << 4,
    kFlagZ = 1u << 6,
    kFlagS = 1u << 7,
    kFlagBRK = 1u << 8,
    kFlagIE = 1u << 9,
    kFlagDIR = 1u << 10,
    kFlagV = 1u << 11,
};

// --- ALU op codes (kStrOp indices) ----------------------------------------
enum AluOp : uint8_t {
    kAdd = 0x00, kOr = 0x01, kAdc = 0x02, kSbb = 0x03,
    kAnd = 0x04, kSub = 0x05, kXor = 0x06, kCmp = 0x07,
    kRol = 0x08, kRor = 0x09, kRcl = 0x0A, kRcr = 0x0B,
    kShl = 0x0C, kShr = 0x0D, kSar = 0x0F,
    kRol12 = 0x10, kDiv = 0x12, kMul = 0x13, kAdjd = 0x14,
    kAdja = 0x15, kOpc = 0x16, kBit = 0x17,
    kInc = 0x18, kDec = 0x19, kNot = 0x1A, kNeg = 0x1B,
    kInc2 = 0x1C, kDec2 = 0x1D, kAbs = 0x1E, kPass = 0x1F,
};

// The ops that step once per `R` iteration and read as a pass-through of
// port A when COUNT has run out (see the ledger, "the R loop").
inline bool alu_is_iterative(uint8_t op) {
    return (op >= kRol && op <= kSar) || op == kRol12 || op == kDiv ||
           op == kMul;
}

// --- an operand binding produced by the loader ----------------------------
struct OperandRef {
    enum Kind : uint8_t { kNone = 0, kReg, kSregRef, kMem } kind = kNone;
    uint8_t idx = 0;    // kReg: 0..7 (byte code AL CL DL BL AH CH DH BH when
                        //             `byte`, else AX..DI); kSregRef: 0..3
    uint16_t ea = 0;    // kMem: 16-bit offset
    uint8_t seg = kDS;  // kMem: resolved segment register index
    bool byte = false;  // operand width
};

// --- the latched micro-ALU ------------------------------------------------
// The ALU operation is LATCHED by the row that names it and SIGMA reads it
// combinationally on the CURRENT tmp registers (see provenance ledger,
// unknown #1).  `ea_const` is the synthetic latch state the pre-decode
// hardware leaves behind: the address adder's standing output.  `adjust`
// carries a pending BCD-adjust mode from a preceding ADJD/ADJA row, which
// turns the ADD/SUB that replaces it into the decimal/ASCII adjust.
struct AluLatch {
    uint8_t op = kPass;
    uint8_t tmp = 0;  // 0=tmpa 1=tmpb 2=tmpc
    bool byte = false;
    bool ea_const = false;
    uint16_t ea_value = 0;
    uint8_t adjust = 0;      // 0 none, 1 = ADJD (decimal), 2 = ADJA (ASCII)
    uint8_t adjust_tmp = 0;  // the `Tmp` field of the ADJx row = the operand
                             // the adjust unit works on (tmpb natively,
                             // tmpa for the 8080 DAA at 03A0)
    // A preceding `ALU BIT` row arms a one-shot BIT-MASK mode: this op's
    // port B is reduced to the single bit `bit_n` (ledger, "BIT").
    bool bit_arm = false;
    uint8_t bit_n = 0;
    // Set once an `R` row has driven this latch through the iterative unit.
    // A SPENT iterative latch reads back as a pass-through of port A; a
    // freshly latched one performs a single combinational step.
    bool spent = false;
};

// --- micro-PC -------------------------------------------------------------
// Micro-address = page(3) : opcode(8) : row-group(2), and each ROM bank holds
// four micro-rows.  Sequential execution and JMP `loc` both walk a 4-bit
// counter {row_group[1:0], row[1:0]} inside the opcode's 16-row block; the
// counter CARRIES into the opcode byte (ledger: IMUL 00B3 -> 0218, INT
// 01FB -> 01FC).
struct MicroPc {
    uint8_t page = 0;
    uint8_t opc = 0;
    uint8_t loc = 0;  // {rowgrp[1:0], row[1:0]}
    uint8_t rowgrp() const { return uint8_t((loc >> 2) & 3); }
    uint8_t row() const { return uint8_t(loc & 3); }
};

enum RepKind : uint8_t { kRepNone = 0, kRepE, kRepNE, kRepC, kRepNC };
enum RepTest : uint8_t { kTestNone = 0, kTestZ, kTestCy };

struct Machine {
    uint16_t gpr[8] = {};
    uint16_t sreg[4] = {};
    uint16_t pc = 0;  // microcode-visible PC: address of the next unconsumed byte
    uint16_t psw = kPswForced;

    uint16_t tmpa = 0, tmpb = 0, tmpc = 0;
    uint16_t opr = 0;    // operand data register (the "OPR" source/dest)
    uint16_t ind = 0;    // address register used by every bus CTL row
    uint16_t count = 0;  // COUNT
    uint8_t pfxcnt = 0;  // PFXCNT

    AluLatch alu;
    MicroPc upc;

    // The ALU status latch the microcode's JMP conditions read.  It is loaded
    // whenever a row gates the ALU result onto the bus (a SIGMA source).
    uint16_t stat = 0;

    // [-09-] / sign tracking for the signed MUL/DIV routines.
    // The auxiliary flip-flop the microcode's [-09-] condition reads INVERTED
    // ("the latch is clear").  Two disjoint users: the signed MUL/DIV sign
    // ([-1E-] loads it, [-0C-] toggles it) and the BCD-string zero
    // accumulator ([-04-] sets it, [-0D-] clears it on a non-zero digit pair).
    bool sign_neg = false;

    // The bit index captured by the row that latched `ALU BIT`.
    uint8_t bit_n = 0;

    // --- prefix latches (cleared by the loader at each instruction start) --
    bool seg_override = false;
    uint8_t seg_ovr = kDS;
    uint8_t rep = kRepNone;
    bool lock = false;

    // --- pre-decode results -----------------------------------------------
    uint8_t opc_reg = 0;  // microcode-visible opcode register (OPC / opc&38)
    bool op8 = false;     // OP8b: the OPERAND is 8 bits
    bool imm8 = false;    // OP8:  the IMMEDIATE is 8 bits
    uint8_t opc_base = 0;  // OPC class offset: 0x00 ALU, 0x08 shift, 0x18 unary
    bool opc_from_modrm = false;  // OPC select comes from the ModR/M reg field
    uint8_t modrm_reg = 0;
    uint8_t xop = 0;      // pla_3 XOP[3:0], carried for SR/REP decisions
    uint8_t rep_test = kTestNone;
    bool rep_pol = false;
    OperandRef M, R;

    uint16_t io_in = 0;  // suite-supplied port data for IN forms

    bool halted = false;

    // External-event recognition latch, as the microcode sees it.  It is the
    // ONLY thing the `INTR` micro-condition reads (9B POLL 006F, REPX 0223) and
    // it also breaks the string loops' `REP` continuation (see the ledger,
    // "pin-event forms").  WHEN it is raised is a replay policy, not a
    // prediction: the golden's recorded firing boundary drives it.
    bool intr_pending = false;

    // byte-register access, AL CL DL BL AH CH DH BH
    uint8_t rb(uint8_t code) const {
        return uint8_t(code < 4 ? (gpr[code] & 0xFF) : (gpr[code & 3] >> 8));
    }
    void wb(uint8_t code, uint8_t v) {
        if (code < 4)
            gpr[code] = uint16_t((gpr[code] & 0xFF00) | v);
        else
            gpr[code & 3] = uint16_t((gpr[code & 3] & 0x00FF) | (v << 8));
    }
    uint16_t flags() const { return uint16_t((psw & kPswWritable) | kPswForced); }
    void set_flags(uint16_t v) { psw = uint16_t((v & kPswWritable) | kPswForced); }
};

}  // namespace sim

#endif  // STATE_H
