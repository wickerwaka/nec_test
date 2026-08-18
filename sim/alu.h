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

// THE ALU'S WIDTH IS THE WIDTH OF THE OPERANDS IT IS HANDED -- EXCEPT FOR THE
// MULTIPLY/DIVIDE UNIT'S OPERAND CONDITIONING, WHICH IS THE INSTRUCTION'S.
//
//     A 16-BIT OPERATION NEEDS TWO 16-BIT OPERANDS.  The ALU works at BYTE
//     width when EITHER of the two it is handed carries only eight
//     significant bits -- OR WHEN THE OPERATION IS ABS.
//
// ---------------------------------------------------------------------------
// CLAUSE 2 -- ABS, AND THE EPISTEMICS OF IT, WHICH ARE THE RISKY DIRECTION.
//
// HOW IT WAS ARRIVED AT, stated because the order matters: `kAbs`-takes-`op8`
// was MEASURED FIRST and it made the score go up (`F6.5 F6.7 F7.5 F7.7 69 6B`
// 3000/3000).  THAT ALONE IS FITTING AND IS NOT EVIDENCE, and the clause was
// refused on exactly that basis when the only thing supporting it was a
// number.
//
// WHAT LICENSES IT IS THE CONFINEMENT, which was checked independently of any
// score: `[-1E-]` occurs in EXACTLY THREE ROWS IN THE WHOLE ROM, and all
// three are the multiply/divide operand-conditioning path --
//
//     0184  <F6/F7> /5 IMUL    M -> tmpa  AX -> tmpb   ALU [-1E-] tmpb
//     0198  <F6/F7> /7 IDIV    M -> tmpb               ALU [-1E-] tmpb
//     0292  69,6B   IMULI      M -> tmpa               ALU [-1E-] tmpb
//
// -- and nowhere else.  NOTE 0198 IS THE DIVIDE ENTRY: the clause is about the
// SHARED ITERATIVE UNIT, not about multiply.  That unit's width is the
// instruction's by construction (8x8->16 or 16x16->32; 16/8 or 32/16), and
// ABS exists only to condition its operand.  So this is a statement about ONE
// STRUCTURAL UNIT, not a per-opcode or per-op-class exception: no opcode is
// named and no opcode is decoded.
//
// *FALSIFIER*: any ABS row found OUTSIDE the multiply/divide path refutes this
// clause outright, and the width must then come from somewhere else.  (`ALU
// OPC` can resolve to ABS through `opc_base = kInc` + a ModR/M reg of 6, so
// the test below is on the RESOLVED operation, and a group form that reached
// it would fire this falsifier.)
//
// A CORRECTED ERRATUM, recorded because the wrong version was reported: an
// earlier analysis claimed ABS was unreachable-by-provenance because "byte
// IMUL reads AX as a byte and byte IDIV reads AX as a word, same encoding,
// opposite tags".  THAT COMPARED TWO DIFFERENT OPERATIONS -- `01A0` is `ALU
// NEG tmpa`, not ABS.  No row asks one rail to carry contradictory widths, and
// the impossibility argument built on it is WITHDRAWN.
// ---------------------------------------------------------------------------
//
// One OR of two tag bits, no operation decode and no port selection.  Port A
// is ALWAYS tmpb (a fixed read port, so its tag is always in the OR); port B
// is the register named by the row's `Tmp` field, where `Tmp == 3` selects a
// hardwired zero rail -- a 16-bit constant, not a register, so WORD.
//
// DERIVED FROM THE ROM.  Each of these refutes a simpler candidate:
//   * NOT the instruction's w-bit (the defect this replaces): `<rep>` 0094
//     `CX -> tmpb | ALU PASS tmpb` tests CX for zero, and a byte string op
//     read it at byte width, so `REP MOVSB` with CX = 0x0100 ran zero times.
//     JCXZ's 0140 is the SAME row shape and was right only because its w-bit
//     happened to be clear.
//   * NOT port B alone: `80/81/83` share rows 003C-0040, where the immediate
//     register can only carry the IMMEDIATE's width, and `83` is a WORD
//     operation with a BYTE immediate.
//   * NOT port A alone: `A8/A9` TEST at 00B4 loads port A from `AX` -- the
//     whole 16-bit register -- at both widths, so only the immediate on
//     port B distinguishes them.  `F6/F7 /4` MUL (0178 `ZEROS -> tmpb`) and
//     `D4` AAM (011D) say the same for the iterative unit.
//   * NOT the widest operand: 80 (byte r/m, sign-extended byte immediate) and
//     A8 (word AX, byte immediate) are both byte operations with one 16-bit
//     rail in them.
bool alu_width_byte(const Machine& m, const AluLatch& lat);

inline bool alu_is_incdec(uint8_t op) {
    return op == kInc || op == kDec || op == kInc2 || op == kDec2;
}

}  // namespace sim

#endif  // ALU_H
