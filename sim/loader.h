// loader.h -- the pre-decode hardware that sits between the queue and the
// microcode ROM.  None of this is in the ROM (docs/notes/microcode_analysis.md);
// it is driven by the pla_3 group-decode PLA (docs/facts/pla_model.md) plus the
// documented ASSUMPTIONS in docs/notes/ucsim_provenance.md.

#ifndef LOADER_H
#define LOADER_H

#include "biu.h"
#include "state.h"

namespace sim {

struct LoadResult {
    bool executed = false;  // ONE_BYTE_LOGIC: retired without microcode
    bool halt = false;
    MicroPc entry;
    // pre-decode diagnostics (for `trace`)
    uint8_t opcode = 0;
    bool has_modrm = false;
    uint8_t modrm = 0;
    uint16_t disp = 0;
    bool ea_valid = false;
    uint16_t ea = 0;
    uint8_t ea_seg = kDS;
    bool preread = false;
    uint16_t pla = 0;
};

// Runs the prefix loop, fetches the opcode (and ModR/M + displacement),
// computes the EA, binds M/R and performs the operand pre-read.  Leaves the
// machine ready to execute row 0 of the returned micro-address.
//
// Templated over the BUS POLICY (ucsim-t T0).  The definition lives in
// loader_impl.h; this header only declares it, plus the explicit-instantiation
// DECLARATION for the functional bus.  That declaration is what keeps the
// functional build byte-for-byte the same shape as before the split: no
// translation unit implicitly instantiates `loader_decode<Biu>`, they all call
// the single out-of-line copy that loader.cpp emits.
template <class Bus>
LoadResult loader_decode(Machine& m, Bus& biu);

extern template LoadResult loader_decode<Biu>(Machine&, Biu&);

}  // namespace sim

#endif  // LOADER_H
