// exec.cpp -- the FUNCTIONAL instantiation of the interpreter (see exec.h).
//
// Everything that depends on the bus policy lives in exec_impl.h.  This file
// holds the two bus-independent pieces (the ROM row disassembly used by
// `trace`, and the process-global micro-row coverage counters) and emits the
// one explicit instantiation of the interpreter for the functional bus.

#include "exec.h"

namespace sim {

long g_row_cover[ucrom::kRowCount] = {};

std::string row_text(const ucrom::MicroOp& op) {
    char buf[128];
    char rest[64];
    if (op.type == ucrom::MicroType::ALU)
        std::snprintf(rest, sizeof rest, "ALU %s %s", ucrom::kStrOp[op.alu_op],
                      ucrom::kStrTmp[op.alu_tmp]);
    else if (op.type == ucrom::MicroType::JMP)
        std::snprintf(rest, sizeof rest, "JMP %s %2d", ucrom::kStrCond[op.cond],
                      op.loc);
    else if (op.is_farjmp())
        std::snprintf(rest, sizeof rest, "CTL FARJMP %s",
                      ucrom::kStrFar[op.far_loc()]);
    else
        std::snprintf(rest, sizeof rest, "CTL %s %s %s", ucrom::kStrInt[op.ictl],
                      ucrom::kStrExt[op.ectl], ucrom::kStrSR[op.sr]);
    if (op.nop_move())
        std::snprintf(buf, sizeof buf, "%-18s%-18s%c%c%c%c %s", "", "",
                      op.f ? 'F' : ' ', op.w ? 'W' : ' ', op.e ? 'E' : ' ',
                      op.r ? 'R' : ' ', rest);
    else if (op.has_const())
        std::snprintf(buf, sizeof buf, "CONST  -> %-6s  %-18d%c%c%c%c %s",
                      ucrom::kStrDest1[op.d1], op.const_val(), op.f ? 'F' : ' ',
                      op.w ? 'W' : ' ', op.e ? 'E' : ' ', op.r ? 'R' : ' ',
                      rest);
    else {
        char snd[32] = "                  ";
        if (op.s2 != 15 || op.d2 != 3)
            std::snprintf(snd, sizeof snd, "%s -> %s  ", ucrom::kStrSource2[op.s2],
                          ucrom::kStrDest2[op.d2]);
        std::snprintf(buf, sizeof buf, "%s -> %s  %s%c%c%c%c %s",
                      ucrom::kStrSource1[op.s1], ucrom::kStrDest1[op.d1], snd,
                      op.f ? 'F' : ' ', op.w ? 'W' : ' ', op.e ? 'E' : ' ',
                      op.r ? 'R' : ' ', rest);
    }
    return std::string(buf);
}

template class CpuT<Biu>;

}  // namespace sim
