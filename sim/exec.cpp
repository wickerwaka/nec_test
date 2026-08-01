// exec.cpp -- see exec.h.

#include "exec.h"

#include <cstring>

#include "alu.h"

namespace sim {

namespace {
constexpr int kMaxRows = 4096;

// Str_Cond indices (docs/V20UCDIS.PAS).
enum Cond : uint8_t {
    kCondNC = 1, kCondZ = 2, kCondNZ = 3, kCondOp8b = 4, kCondCntz = 5,
    kCondL = 6, kCondOp8 = 7, kCondAlways = 8, kCondO = 10, kCondNS = 11,
    kCondRep = 12, kCondBusy = 13, kCondIntr = 14, kCondOpc = 15,
};

// Str_Int / Str_Ext indices.
enum Ictl : uint8_t { kIctlSusp = 8, kIctlFlush = 9, kIctlFarJmp = 14 };
enum Ectl : uint8_t { kEctlMemR = 1, kEctlMemW = 2, kEctlWriteBack = 6 };
}  // namespace

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

uint16_t Cpu::rd_operand(const OperandRef& r) const {
    switch (r.kind) {
        case OperandRef::kReg:
            return r.byte ? uint16_t(m_.rb(r.idx)) : m_.gpr[r.idx];
        case OperandRef::kSregRef: return m_.sreg[r.idx];
        case OperandRef::kMem: return m_.opr;  // pre-read operand data
        default: return 0;
    }
}

void Cpu::wr_operand(const OperandRef& r, uint16_t v) {
    switch (r.kind) {
        case OperandRef::kReg:
            if (r.byte)
                m_.wb(r.idx, uint8_t(v));
            else
                m_.gpr[r.idx] = v;
            break;
        case OperandRef::kSregRef: m_.sreg[r.idx] = v; break;
        case OperandRef::kMem:
            m_.opr = v;  // staged; the [-06-] strobe commits it to memory
            break;
        default: break;
    }
}

uint8_t Cpu::sr_segment(uint8_t sr) const {
    if (sr == 0) return kES;
    if (sr == 2) return kSS;
    // blank: the operand's own (possibly overridden) default segment.
    if (m_.M.kind == OperandRef::kMem) return m_.M.seg;
    if (m_.R.kind == OperandRef::kMem) return m_.R.seg;
    return m_.seg_override ? m_.seg_ovr : uint8_t(kDS);
}

bool Cpu::cond_true(uint8_t cond) const {
    uint16_t f = m_.psw;
    bool cy = f & kFlagCY, z = f & kFlagZ, s = f & kFlagS, v = f & kFlagV;
    bool p = f & kFlagP;
    switch (cond) {
        case kCondNC: return !cy;
        case kCondZ: return z;
        case kCondNZ: return !z;
        case kCondOp8b: return m_.op8;
        case kCondCntz: return m_.count == 0;
        case kCondL: return s != v;
        case kCondOp8: return m_.op8;
        case kCondAlways: return true;
        case kCondO: return v;
        case kCondNS: return !s;
        case kCondRep: return m_.rep != kRepNone;
        case kCondBusy: return false;
        case kCondIntr: return false;
        case kCondOpc: {
            // pla_2 (IDENTIFIED exact, docs/facts/pla_model.md): the textbook
            // x86 condition table over cc = opcode bits 3:0.
            switch (m_.opc_reg & 0x0F) {
                case 0x0: return v;
                case 0x1: return !v;
                case 0x2: return cy;
                case 0x3: return !cy;
                case 0x4: return z;
                case 0x5: return !z;
                case 0x6: return cy || z;
                case 0x7: return !cy && !z;
                case 0x8: return s;
                case 0x9: return !s;
                case 0xA: return p;
                case 0xB: return !p;
                case 0xC: return s != v;
                case 0xD: return s == v;
                case 0xE: return z || (s != v);
                default: return !z && (s == v);
            }
        }
        default: return false;
    }
}

uint16_t Cpu::rd_src1(uint8_t c, const RowCtx& ctx, const ucrom::MicroOp& op) {
    switch (c) {
        case 0: case 1: case 2: case 3: return m_.sreg[c];
        case 4: return m_.pc;
        case 6: return m_.opr;
        case 7: {  // Q: pop one queue byte, advance PC
            uint8_t b = biu_.next_byte(m_.sreg[kCS], op.rom_addr);
            m_.pc = uint16_t(m_.pc + 1);
            return b;
        }
        case 8: {  // dir*sz
            int step = m_.op8 ? 1 : 2;
            if (m_.psw & kFlagDIR) step = -step;
            return uint16_t(int16_t(step));
        }
        case 9: return 0;                       // ZEROS
        case 10: return m_.pfxcnt;              // PFXCNT
        case 12: return m_.tmpa;
        case 13: return m_.tmpb;
        case 14: return m_.tmpc;
        case 15: return m_.flags();
        case 16: return uint16_t((m_.gpr[kAW] << 8) | (m_.gpr[kAW] >> 8));  // AL:AH
        case 17: return m_.count;
        case 18: return rd_operand(m_.R);
        case 19: return rd_operand(m_.M);
        case 20: return ctx.sigma;
        case 21: return 0xFFFF;                 // ONES
        case 22: return uint16_t(m_.opc_reg & 0x38);
        case 23: return op.const_val();         // CONST
        default:
            if (c >= 24) return m_.gpr[c - 24];
            return 0;
    }
}

void Cpu::wr_dst1(uint8_t c, uint16_t v) {
    switch (c) {
        case 0: case 1: case 2: case 3: m_.sreg[c] = v; break;
        case 4: m_.pc = v; break;
        case 5: m_.ind = v; break;
        case 6: m_.opr = v; break;
        case 7: break;  // NULL
        case 8: m_.wb(0, uint8_t(v)); break;   // AL
        case 12: m_.tmpa = v; break;
        case 13: m_.tmpb = v; break;
        case 14: m_.tmpc = v; break;
        case 15: m_.set_flags(v); break;
        case 16: m_.wb(4, uint8_t(v)); break;  // AH
        case 17: m_.count = v; break;
        case 18: wr_operand(m_.R, v); break;
        case 19: wr_operand(m_.M, v); break;
        case 20: m_.tmpa = uint16_t(int16_t(int8_t(v))); break;
        case 21: m_.tmpb = uint16_t(int16_t(int8_t(v))); break;
        case 22: m_.tmpa = uint16_t((m_.tmpa & 0x00FF) | (v << 8)); break;
        case 23: m_.tmpb = uint16_t((m_.tmpb & 0x00FF) | (v << 8)); break;
        default:
            if (c >= 24) m_.gpr[c - 24] = v;
            break;
    }
}

uint16_t Cpu::rd_src2(uint8_t c, const RowCtx& ctx) {
    switch (c) {
        case 4: return ctx.sigma;
        case 5: {
            uint8_t b = biu_.next_byte(m_.sreg[kCS], 0xFFFE);
            m_.pc = uint16_t(m_.pc + 1);
            return b;
        }
        case 6: return 0;
        case 7: return rd_operand(m_.R);
        default:
            if (c >= 8) return m_.gpr[c - 8];
            return 0;
    }
}

void Cpu::wr_dst2(uint8_t c, uint16_t v) {
    switch (c) {
        case 0: m_.tmpa = v; break;
        case 1: m_.tmpb = v; break;
        case 2: m_.ind = v; break;
        default: break;
    }
}

void Cpu::post_write(uint16_t off, uint8_t seg, bool byte, bool io,
                     uint16_t upc) {
    if (pend_.active) retire_posted();
    pend_.active = true;
    pend_.age = 0;
    pend_.off = off;
    pend_.seg = seg;
    pend_.byte = byte;
    pend_.io = io;
    pend_.upc = upc;
}

void Cpu::retire_posted() {
    if (!pend_.active) return;
    if (pend_.io)
        biu_.io_write(pend_.off, m_.opr, !pend_.byte, pend_.upc);
    else
        biu_.mem_write(m_.sreg[pend_.seg], pend_.off, m_.opr, !pend_.byte,
                       pend_.seg, pend_.upc);
    pend_.active = false;
}

void Cpu::tick_posted() {
    if (!pend_.active) return;
    if (pend_.age >= 1)
        retire_posted();
    else
        ++pend_.age;
}

bool Cpu::step() {
    pend_ = Posted{};
    LoadResult ld = loader_decode(m_, biu_);
    if (trace_) {
        std::fprintf(trace_,
                     "  loader: opc=%02X pla=%04X modrm=%s%02X ea=%s%04X "
                     "seg=%d preread=%d page=%d entry_opc=%02X op8=%d\n",
                     ld.opcode, ld.pla, ld.has_modrm ? "" : "-", ld.modrm,
                     ld.ea_valid ? "" : "-", ld.ea, ld.ea_seg, ld.preread,
                     ld.entry.page, ld.entry.opc, m_.op8);
    }
    if (ld.executed) return true;

    m_.upc = ld.entry;
    bool ending = false;
    int guard = 0;

    for (;;) {
        if (++guard > kMaxRows) return false;
        int bank = rom_.bank_of(m_.upc.page, m_.upc.opc, m_.upc.rowgrp());
        const ucrom::MicroOp* rowp = nullptr;
        ucrom::MicroOp nop{};
        nop.s1 = 0x1F;
        nop.d1 = 0x1F;
        nop.s2 = 15;
        nop.d2 = 3;
        nop.type = ucrom::MicroType::CTL;
        nop.ictl = 15;
        nop.ectl = 7;
        nop.sr = 3;
        nop.rom_addr = 0xFFFF;
        if (bank >= 0)
            rowp = &rom_.op(bank * 4 + m_.upc.row());
        else
            rowp = &nop;
        const ucrom::MicroOp& op = *rowp;
        ++rows_;

        // SIGMA and the flag outputs are read from the LATCHED operation
        // evaluated on the tmps as they stand at the START of the row.
        RowCtx ctx;
        AluResult ar = alu_eval(m_, m_.alu);
        ctx.sigma = ar.value;
        ctx.commits = ar.commits;
        ctx.flags = ar.flags;
        ctx.flag_mask = ar.flag_mask;

        if (trace_) {
            std::fprintf(trace_,
                         "  %04X.%X %-64s | SIG=%04X a=%04X b=%04X c=%04X "
                         "OPR=%04X IND=%04X PSW=%04X PC=%04X\n",
                         (m_.upc.page << 10) | (m_.upc.opc << 2) |
                             m_.upc.rowgrp(),
                         m_.upc.row(), row_text(op).c_str(), ctx.sigma, m_.tmpa,
                         m_.tmpb, m_.tmpc, m_.opr, m_.ind, m_.flags(), m_.pc);
        }

        bool suppress_commit = false;

        // --- the two parallel transfers ---------------------------------
        bool have1 = !op.nop_move();
        bool have2 = !op.has_const() && (op.s2 != 15 || op.d2 != 3);
        uint16_t v1 = 0, v2 = 0;
        if (have1) v1 = rd_src1(op.s1, ctx, op);
        if (have2) v2 = rd_src2(op.s2, ctx);
        if (have1) {
            bool from_sigma = (op.s1 == 20);
            if (from_sigma && !ctx.commits) {
                // CMP: the ALU does not drive the result bus, so neither the
                // register/OPR write nor its memory commit happens.
                if (op.d1 == 19 && m_.M.kind == OperandRef::kMem)
                    suppress_commit = true;
            } else {
                wr_dst1(op.d1, v1);
            }
        }
        if (have2) {
            bool from_sigma = (op.s2 == 4);
            if (!(from_sigma && !ctx.commits)) wr_dst2(op.d2, v2);
        }

        // --- flag write --------------------------------------------------
        if (op.w && ctx.flag_mask) {
            uint16_t mask = ctx.flag_mask;
            m_.psw = uint16_t((m_.psw & ~mask) | (ctx.flags & mask));
            m_.set_flags(m_.psw);
        }

        // --- row type ------------------------------------------------------
        uint8_t next_loc = uint8_t((m_.upc.loc + 1) & 0x0F);
        if (op.type == ucrom::MicroType::ALU) {
            m_.alu.op = op.alu_op;
            m_.alu.tmp = op.alu_tmp;
            m_.alu.byte = m_.op8;
            m_.alu.ea_const = false;
        } else if (op.type == ucrom::MicroType::JMP) {
            if (cond_true(op.cond)) next_loc = op.loc;
        } else {
            // CTL
            if (op.is_farjmp()) {
                m_.upc.page = 7;
                m_.upc.opc = uint8_t(op.far_loc() << 3);
                next_loc = 0;
            } else {
                switch (op.ictl) {
                    case kIctlSusp: biu_.susp(); break;
                    case kIctlFlush: biu_.flush(m_.pc); break;
                    default: break;
                }
            }
            uint8_t sr = op.sr;
            bool io = (sr == 1);
            uint8_t seg = sr_segment(sr);
            // Stack accesses are word-wide regardless of the operand width.
            bool byte = m_.op8 && !(sr == 2);
            switch (op.ectl) {
                case kEctlMemR:
                    if (io)
                        m_.opr = biu_.io_read(m_.ind, !byte, op.rom_addr);
                    else
                        m_.opr = biu_.mem_read(m_.sreg[seg], m_.ind, !byte, seg,
                                               op.rom_addr);
                    break;
                case kEctlMemW:
                    post_write(m_.ind, seg, byte, io, op.rom_addr);
                    break;
                case kEctlWriteBack:
                    // [-06-]: the operand write-back strobe.  It commits OPR
                    // to the r/m operand ONLY when that operand is memory; a
                    // register r/m is written by the row's own `-> M`
                    // transfer (evidence: the 8F mod==3 ghost).
                    if (!suppress_commit && m_.M.kind == OperandRef::kMem)
                        post_write(m_.M.ea, m_.M.seg, m_.M.byte, false,
                                   op.rom_addr);
                    break;
                default: break;
            }
        }

        tick_posted();

        if (ending) break;
        if (op.e) ending = true;
        m_.upc.loc = next_loc;
    }

    retire_posted();
    return true;
}

}  // namespace sim
