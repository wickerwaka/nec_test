// alu.h -- the micro-ALU.  Operands come from the two tmp ports:
//   port A = tmpb (fixed), port B = tmp[Tmp field].
// Binary ops compute  A op B ; unary ops operate on port B.
// (Derivation and evidence: docs/notes/ucsim_provenance.md, "ALU operand
//  ports".)

#ifndef ALU_H
#define ALU_H

#include <cstdint>

#include "state.h"

namespace sim {

// The three flag behaviours the microcode does NOT determine -- they live in
// the C++ ALU hardware model (ledger §17, "undefined-flag emergence").  Every
// other flag bit the simulator produces emerges from the ROM.  `--alu-hw-report`
// quantifies how much of the final PSW they actually account for.
enum AluHw : uint8_t {
    kHwNone = 0,
    kHwShiftV = 1,   // the per-STEP shift/rotate overflow law
    kHwLogicAc = 2,  // AND/OR/XOR/TEST: AC is forced to 0
    kHwBcd = 4,      // the fitted ADJD/ADJA decimal correction
};
constexpr int kHwCount = 3;
// The PSW bits each hardware behaviour is responsible for.
constexpr uint16_t kHwAttrib[kHwCount] = {
    kFlagV,                                                     // kHwShiftV
    kFlagAC,                                                    // kHwLogicAc
    kFlagCY | kFlagP | kFlagAC | kFlagZ | kFlagS | kFlagV,       // kHwBcd
};

struct AluResult {
    uint16_t value = 0;
    uint16_t flags = 0;      // CY P AC Z S V at V30 PSW bit positions
    uint16_t flag_mask = 0;  // which of those the op defines
    bool commits = true;     // false for CMP: the result bus is not driven
    uint8_t hw = kHwNone;    // AluHw bits: non-emergent hardware contributions
};

// Evaluates the LATCHED operation against the machine's current tmps.  This
// is the COMBINATIONAL SIGMA path, so it must be side-effect free: the
// iterative ops (shift / rotate / MUL / DIV) read as a pass-through of port A
// here, and their per-iteration stepping lives in alu_step().
AluResult alu_eval(const Machine& m, const AluLatch& lat);

// One `R`-loop iteration of an iterative op.  MUTATES the multiplier /
// quotient register tmpa where the op requires it; the returned value is what
// SIGMA presents (and what the row's `-> tmpb` transfer stores).
AluResult alu_step(Machine& m, const AluLatch& lat);

// The ALU operation selected by the `OPC` field.
uint8_t alu_opc_select(const Machine& m);

inline bool alu_is_incdec(uint8_t op) {
    return op == kInc || op == kDec || op == kInc2 || op == kDec2;
}

}  // namespace sim

#endif  // ALU_H
