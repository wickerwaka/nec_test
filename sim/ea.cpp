// ea.cpp -- see ea.h.

#include "ea.h"

namespace sim {

uint16_t ea_compute(const Machine& m, const ModRm& rm, uint16_t disp) {
    uint16_t v = 0;
    switch (rm.rm) {
        case 0: v = uint16_t(m.gpr[kBW] + m.gpr[kIX]); break;
        case 1: v = uint16_t(m.gpr[kBW] + m.gpr[kIY]); break;
        case 2: v = uint16_t(m.gpr[kBP] + m.gpr[kIX]); break;
        case 3: v = uint16_t(m.gpr[kBP] + m.gpr[kIY]); break;
        case 4: v = m.gpr[kIX]; break;
        case 5: v = m.gpr[kIY]; break;
        case 6: v = (rm.mod == 0) ? 0 : m.gpr[kBP]; break;
        case 7: v = m.gpr[kBW]; break;
        default: break;
    }
    return uint16_t(v + disp);
}

}  // namespace sim
