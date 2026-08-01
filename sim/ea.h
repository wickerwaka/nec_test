// ea.h -- ModR/M decode and effective-address arithmetic.
//
// Base/index selection and the BP => SS default-segment rule are the exact
// fit derived from the `pla_4` dump (docs/facts/pla_model.md, "mem[2:0] =
// input bits (7,9,11)": F6[1] = BW base, F6[2] = BP base).

#ifndef EA_H
#define EA_H

#include <cstdint>

#include "state.h"

namespace sim {

struct ModRm {
    uint8_t raw = 0;
    uint8_t mod = 0;
    uint8_t reg = 0;
    uint8_t rm = 0;
    uint8_t disp_bytes = 0;  // 0, 1 (sign-extended) or 2
};

inline ModRm modrm_decode(uint8_t b) {
    ModRm m;
    m.raw = b;
    m.mod = uint8_t(b >> 6);
    m.reg = uint8_t((b >> 3) & 7);
    m.rm = uint8_t(b & 7);
    if (m.mod == 1)
        m.disp_bytes = 1;
    else if (m.mod == 2)
        m.disp_bytes = 2;
    else if (m.mod == 0 && m.rm == 6)
        m.disp_bytes = 2;
    return m;
}

// True when the addressing form uses BP as base -> default segment SS.
inline bool ea_uses_bp(const ModRm& m) {
    if (m.mod == 3) return false;
    if (m.rm == 2 || m.rm == 3) return true;
    return m.rm == 6 && m.mod != 0;
}

// The address adder.  `disp` is the already-sign-extended displacement.
uint16_t ea_compute(const Machine& m, const ModRm& rm, uint16_t disp);

}  // namespace sim

#endif  // EA_H
