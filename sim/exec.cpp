// exec.cpp -- see exec.h.

#include "exec.h"

#include <cstring>

#include "alu.h"

namespace sim {

long g_row_cover[ucrom::kRowCount] = {};

namespace {
constexpr int kMaxRows = 100000;

// Str_Cond indices (docs/V20UCDIS.PAS).
enum Cond : uint8_t {
    kCondC = 0, kCondNC = 1, kCondZ = 2, kCondNZ = 3, kCondOp8b = 4,
    kCondCntz = 5, kCondL = 6, kCondOp8 = 7, kCondAlways = 8, kCondSign = 9,
    kCondO = 10, kCondNS = 11, kCondRep = 12, kCondBusy = 13, kCondIntr = 14,
    kCondOpc = 15,
};

// Str_Int / Str_Ext indices.
enum Ictl : uint8_t {
    kIctlEndem = 0, kIctlCitf = 1, kIctlMfc = 2, kIctlMfs = 3,
    kIctlBcdInit = 4, kIctlClrCyV = 6, kIctlSetCyV = 7, kIctlSusp = 8,
    kIctlFlush = 9, kIctlSignTgl = 12, kIctlBcdNz = 13, kIctlFarJmp = 14,
};
// Ext [-05-] is the INTERRUPT-ACKNOWLEDGE bus cycle and Ext [-03-] rides the
// row that follows the vector into the shared INT routine (01ED, which EVERY
// software INT / trap also executes -- so it cannot itself move data; see the
// ledger).  Both occur only with SR = IO, and the SR field is NOT consulted for
// them: the acknowledge has no segment and no address.
enum Ectl : uint8_t {
    kEctlMemR = 1, kEctlMemW = 2, kEctlIntaTail = 3, kEctlInta = 5,
    kEctlWriteBack = 6
};
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
            opr_fresh_ = true;
            break;
        default: break;
    }
}

// SR == IO selects the I/O space only for the port/block-I/O opcode classes
// (pla_3 XOP 0xF / 0x6).  Everywhere else -- i.e. the internal INT routine's
// vector fetch -- it selects the ZERO segment (physical == offset).
bool Cpu::sr_is_io(uint8_t sr) const {
    if (sr != 1) return false;
    return m_.xop == 0xF || m_.xop == 0x6;
}

uint8_t Cpu::sr_segment(uint8_t sr) const {
    if (sr == 0) return kES;
    if (sr == 1) return kSegZero;
    if (sr == 2) return kSS;
    // blank: the operand's own (possibly overridden) default segment.
    if (m_.M.kind == OperandRef::kMem) return m_.M.seg;
    if (m_.R.kind == OperandRef::kMem) return m_.R.seg;
    return m_.seg_override ? m_.seg_ovr : uint8_t(kDS);
}

// Commits `flags` under `mask` to the PSW and books the bits against the
// non-emergent ALU-hardware behaviour that produced them, if any.  A later
// write always takes ownership away from an earlier one, so what survives to
// the end of the instruction is exactly the hardware model's contribution to
// the final PSW.
void Cpu::commit_flags(uint16_t mask, uint16_t flags, uint8_t hw) {
    m_.psw = uint16_t((m_.psw & ~mask) | (flags & mask));
    m_.set_flags(m_.psw);
    for (int i = 0; i < kHwCount; ++i) hw_owned_[i] &= uint16_t(~mask);
    for (int i = 0; i < kHwCount; ++i) {
        if (!(hw & (1u << i))) continue;
        ++hw_writes_[i];
        hw_owned_[i] |= uint16_t(mask & kHwAttrib[i]);
    }
}

void Cpu::set_stat(const RowCtx& ctx) {
    if (!ctx.flag_mask) return;
    m_.stat = uint16_t((m_.stat & ~ctx.flag_mask) | (ctx.flags & ctx.flag_mask));
}

bool Cpu::cond_true(uint8_t cond) {
    uint16_t f = m_.stat;
    uint16_t psw = m_.psw;
    bool cy = f & kFlagCY, z = f & kFlagZ, s = f & kFlagS, v = f & kFlagV;
    switch (cond) {
        case kCondC: return cy;
        case kCondNC: return !cy;
        case kCondZ: return z;
        case kCondNZ: return !z;
        case kCondOp8b: return m_.op8;
        case kCondCntz:
            // "count not zero": the loop-continue test decrements COUNT and
            // jumps while it is still non-zero (ENTER walk = level-1 copies).
            m_.count = uint16_t(m_.count - 1);
            return m_.count != 0;
        case kCondL: return s != bool(v);
        case kCondOp8: return m_.imm8;
        case kCondAlways: return true;
        case kCondSign: return !m_.sign_neg;
        case kCondO: return (psw & kFlagV) != 0;
        case kCondNS: return (m_.tmpb & (m_.op8 ? 0x0080u : 0x8000u)) == 0;
        case kCondRep: {
            m_.count = uint16_t(m_.count - 1);
            // Mid-instruction recognition, image mode: the capture says the
            // acknowledge landed after N bus cycles, so the string loop that
            // has already emitted N of them is the one that must withdraw.
            // The element's own store is still PENDING here (write-data
            // pairing, ledger sec. 18.2/27: after the first iteration nothing
            // refreshes OPR, so the cycle only runs when the NEXT one is
            // registered) -- it has to be counted, or the model withdraws one
            // element late.
            {
                long pending = pend_.active
                                   ? ((!pend_.byte && (pend_.off & 1)) ? 2 : 1)
                                   : 0;
                if (evt_at_ >= 0 && biu_.ev_count() + pending >= evt_at_)
                    m_.intr_pending = true;
            }
            // One string ELEMENT has completed by the time the loop asks to
            // repeat.  This is the recognition boundary the measured law calls
            // "REP iterations are individually interruptible"
            // (docs/facts/interrupt_model.md): a pending external event makes
            // the continuation fail, and the fall-through (009B: COUNT -> CW,
            // FARJMP REPX) writes the PARTIAL count back before REPX 0223's
            // `JMP INTR` backs PC up over the prefixes.
            ++rep_elems_;
            if (rep_abort_at_ >= 0 && rep_elems_ >= rep_abort_at_)
                m_.intr_pending = true;
            if (m_.count == 0) return false;
            if (m_.intr_pending) return false;
            if (m_.rep_test == kTestZ)
                return ((psw & kFlagZ) != 0) == m_.rep_pol;
            if (m_.rep_test == kTestCy)
                return ((psw & kFlagCY) != 0) == m_.rep_pol;
            return true;
        }
        // BUSY (the 9B POLL pin) has no model: POLL_N low is the only case the
        // suite's POLL.LO/POLL.REL forms end in, and both retire the
        // instruction, so the condition is hard-FALSE (ledger R2).
        case kCondBusy: return false;
        case kCondIntr: return m_.intr_pending;
        case kCondOpc: {
            if (m_.mode8080) {
                // The 8080 condition field is opcode bits 5:3:
                //   NZ Z NC C PO PE P M
                bool pcy = psw & kFlagCY, pz = psw & kFlagZ, ps = psw & kFlagS;
                bool pp = psw & kFlagP;
                switch ((m_.opc_reg >> 3) & 7) {
                    case 0: return !pz;
                    case 1: return pz;
                    case 2: return !pcy;
                    case 3: return pcy;
                    case 4: return !pp;
                    case 5: return pp;
                    case 6: return !ps;
                    default: return ps;
                }
            }
            // pla_2 (IDENTIFIED exact, docs/facts/pla_model.md): the textbook
            // x86 condition table over cc = opcode bits 3:0, evaluated on the
            // architectural PSW.
            bool pcy = psw & kFlagCY, pz = psw & kFlagZ, ps = psw & kFlagS;
            bool pv = psw & kFlagV, pp = psw & kFlagP;
            switch (m_.opc_reg & 0x0F) {
                case 0x0: return pv;
                case 0x1: return !pv;
                case 0x2: return pcy;
                case 0x3: return !pcy;
                case 0x4: return pz;
                case 0x5: return !pz;
                case 0x6: return pcy || pz;
                case 0x7: return !pcy && !pz;
                case 0x8: return ps;
                case 0x9: return !ps;
                case 0xA: return pp;
                case 0xB: return !pp;
                case 0xC: return ps != pv;
                case 0xD: return ps == pv;
                case 0xE: return pz || (ps != pv);
                default: return !pz && (ps == pv);
            }
        }
        default: return false;
    }
}

uint16_t Cpu::rd_src1(uint8_t c, const RowCtx& ctx, const ucrom::MicroOp& op,
                      bool& byte_src) {
    byte_src = false;
    switch (c) {
        case 0: case 1: case 2: case 3: return m_.sreg[c];
        case 4: return m_.pc;
        // Reading OPR as a source CONSUMES it: a later MEMW that has not yet
        // been given data will wait for the next OPR load rather than reuse
        // the value the microcode has already taken out of the register.
        // (Ledger, "write-data pairing"; forced by the BCD strings 02D4/02D7
        // and by INS 032B/032F.)
        case 6: opr_fresh_ = false; return m_.opr;
        case 7: {  // Q: pop one queue byte, advance PC
            uint8_t b = biu_.next_byte(m_.sreg[kCS], op.rom_addr);
            m_.pc = uint16_t(m_.pc + 1);
            byte_src = true;
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
        case 23: byte_src = true; return op.const_val();  // CONST
        default:
            if (c >= 24) return m_.gpr[c - 24];
            return 0;
    }
}

void Cpu::wr_dst1(uint8_t c, uint16_t v, bool byte_src) {
    switch (c) {
        case 0: case 1: case 2: case 3: m_.sreg[c] = v; break;
        case 4: m_.pc = v; break;
        case 5: m_.ind = v; break;
        case 6: m_.opr = v; opr_fresh_ = true; break;
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
        // tmpaL zero-extends, tmpbL SIGN-extends (ledger, "L-half writes").
        case 20: m_.tmpa = uint16_t(v & 0x00FF); break;
        case 21: m_.tmpb = uint16_t(int16_t(int8_t(v))); break;
        // The H-half write takes bus bits 15:8; a byte source (Q / CONST)
        // presents its byte there.
        case 22:
            m_.tmpa = uint16_t((m_.tmpa & 0x00FF) |
                               ((byte_src ? (v & 0xFF) : (v >> 8)) << 8));
            break;
        case 23:
            m_.tmpb = uint16_t((m_.tmpb & 0x00FF) |
                               ((byte_src ? (v & 0xFF) : (v >> 8)) << 8));
            break;
        default:
            if (c >= 24) m_.gpr[c - 24] = v;
            break;
    }
}

uint16_t Cpu::rd_src2(uint8_t c, const RowCtx& ctx) {
    switch (c) {
        // Source2 [-00-] is used on exactly ONE row in the whole ROM (02DA,
        // the BCD-string loop) and it must present all-ones there -- see the
        // ledger, "the BCD string ops": the tail computes the final CY/Z as
        // `tmpb + tmpb` at byte width, and the carry-out path needs 0xFF.
        case 0: return 0xFFFF;
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

// --- bus plumbing ----------------------------------------------------------

void Cpu::deliver_read() {
    if (rdq_.empty()) return;
    m_.opr = rdq_.front();
    rdq_.erase(rdq_.begin());
    opr_fresh_ = true;
}

void Cpu::emit_pending() {
    if (!pend_.active) return;
    if (pend_.io)
        biu_.io_write(pend_.off, m_.opr, !pend_.byte, pend_.upc);
    else
        biu_.mem_write(pend_.seg == kSegZero ? 0 : m_.sreg[pend_.seg], pend_.off,
                       m_.opr, !pend_.byte, pend_.seg, pend_.upc);
    pend_.active = false;
    opr_fresh_ = false;
}

void Cpu::bus_read(uint8_t seg, uint16_t off, bool byte, bool io, uint16_t upc) {
    if (pend_.active) {  // a queued write must run before the next cycle
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    uint16_t v;
    if (io)
        v = biu_.io_read(off, !byte, upc);
    else
        v = biu_.mem_read(seg == kSegZero ? 0 : m_.sreg[seg], off, !byte, seg,
                          upc);
    rdq_.push_back(v);
}

void Cpu::bus_write(uint8_t seg, uint16_t off, bool byte, bool io,
                    uint16_t upc) {
    if (pend_.active) {
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    pend_.active = true;
    pend_.off = off;
    pend_.seg = seg;
    pend_.byte = byte;
    pend_.io = io;
    pend_.upc = upc;
    if (opr_fresh_) emit_pending();
}

// Ext [-05-]: the interrupt-acknowledge cycle.  It behaves as an ordinary read
// as far as the microcode is concerned -- the acknowledge data lands in the
// read queue and the next `F` row delivers it into OPR (01E0/01E1 and
// 01E2/01E3) -- but it carries NO address and NO segment, so it must NOT go
// through sr_segment()/sr_is_io(): those read `xop`, which at this point still
// belongs to the INTERRUPTED instruction (an `IN`/`INS` opcode would otherwise
// re-classify the acknowledge).
void Cpu::bus_inta(uint16_t upc) {
    if (pend_.active) {
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    rdq_.push_back(biu_.inta_read(upc));
}

// --- the interpreter -------------------------------------------------------

void Cpu::begin_sequence() {
    pend_ = Pending{};
    rdq_.clear();
    opr_fresh_ = false;
    rep_elems_ = 0;
    for (int i = 0; i < kHwCount; ++i) { hw_owned_[i] = 0; hw_writes_[i] = 0; }
}

// A hardware entry into one of the page-7 interrupt routines.  Nothing is
// decoded: the loader is bypassed, so every latch it would have written has to
// be presented explicitly.  In particular `xop` MUST be cleared -- the shared
// INT routine's vector fetch is an `SR = IO` access that means the ZERO segment
// (ledger A24) only while `xop` is not one of the port classes, and `xop` would
// otherwise still hold the INTERRUPTED instruction's value.
bool Cpu::reset() {
    begin_sequence();
    rep_abort_at_ = -1;
    m_ = Machine{};
    m_.alu = AluLatch{};
    m_.alu.op = kAdd;
    MicroPc e{};
    e.page = 7;
    e.opc = 0x03;
    e.loc = 0;
    return run_micro(e);
}

bool Cpu::interrupt(EventKind kind) {
    begin_sequence();
    rep_abort_at_ = -1;
    m_.seg_override = false;
    m_.seg_ovr = kDS;
    m_.rep = kRepNone;
    m_.lock = false;
    m_.pfxcnt = 0;
    m_.M = OperandRef{};
    m_.R = OperandRef{};
    m_.opc_base = 0;
    m_.opc_from_modrm = false;
    m_.modrm_reg = 0;
    m_.opc_reg = 0;
    m_.rep_test = kTestNone;
    m_.rep_pol = false;
    m_.xop = 0;
    // The vector arithmetic (01EC `ALU ADD tmpb` -> vector*4) is 16-bit; an
    // inherited byte width would truncate 2*vector.
    m_.op8 = false;
    m_.imm8 = false;
    m_.bus_word = false;
    m_.alu = AluLatch{};
    m_.alu.op = kAdd;
    m_.alu.tmp = 0;
    m_.alu.byte = false;
    m_.halted = false;
    MicroPc e{};
    e.page = 7;
    e.opc = (kind == kEvtInt) ? uint8_t(0x02) : uint8_t(0x00);
    e.loc = (kind == kEvtNmi) ? uint8_t(2) : uint8_t(0);
    bool ok = run_micro(e);
    m_.intr_pending = false;
    return ok;
}

bool Cpu::step() {
    begin_sequence();
    biu_.clear_consumed();
    LoadResult ld = loader_decode(m_, biu_);
    if (trace_) {
        std::fprintf(trace_,
                     "  loader: opc=%02X pla=%04X modrm=%s%02X ea=%s%04X "
                     "seg=%d preread=%d page=%d entry_opc=%02X op8=%d imm8=%d\n",
                     ld.opcode, ld.pla, ld.has_modrm ? "" : "-", ld.modrm,
                     ld.ea_valid ? "" : "-", ld.ea, ld.ea_seg, ld.preread,
                     ld.entry.page, ld.entry.opc, m_.op8, m_.imm8);
    }
    if (ld.executed) {
        rep_abort_at_ = -1;
        return true;
    }

    bool ok = run_micro(ld.entry);
    rep_abort_at_ = -1;
    return ok;
}

bool Cpu::run_micro(const MicroPc& entry) {
    m_.upc = entry;
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
        if (bank >= 0) ++g_row_cover[bank * 4 + m_.upc.row()];

        // `F` is the bus interlock: the row waits for the outstanding read to
        // land in OPR (ledger, "F = bus interlock").
        if (op.f) deliver_read();

        // SIGMA and the flag outputs are read from the LATCHED operation
        // evaluated on the tmps as they stand at the START of the row.
        RowCtx ctx;
        AluResult ar = alu_eval(m_, m_.alu);
        ctx.sigma = ar.value;
        ctx.commits = ar.commits;
        ctx.flags = ar.flags;
        ctx.flag_mask = ar.flag_mask;
        ctx.hw = ar.hw;

        if (trace_) {
            std::fprintf(trace_,
                         "  %04X.%X %-64s | SIG=%04X a=%04X b=%04X c=%04X "
                         "OPR=%04X IND=%04X PSW=%04X ST=%04X CNT=%04X PC=%04X\n",
                         (m_.upc.page << 10) | (m_.upc.opc << 2) |
                             m_.upc.rowgrp(),
                         m_.upc.row(), row_text(op).c_str(), ctx.sigma, m_.tmpa,
                         m_.tmpb, m_.tmpc, m_.opr, m_.ind, m_.flags(), m_.stat,
                         m_.count, m_.pc);
        }

        bool suppress_commit = false;
        bool is_rloop = (op.type == ucrom::MicroType::ALU) && op.r;

        if (!is_rloop) {
            // --- the two parallel transfers ------------------------------
            bool have1 = !op.nop_move();
            bool have2 = !op.has_const() && (op.s2 != 15 || op.d2 != 3);
            uint16_t v1 = 0, v2 = 0;
            bool bsrc1 = false;
            if (have1) v1 = rd_src1(op.s1, ctx, op, bsrc1);
            if (have2) v2 = rd_src2(op.s2, ctx);
            if (have1) {
                if (op.s1 == 20) set_stat(ctx);
                bool from_sigma = (op.s1 == 20);
                if (from_sigma && !ctx.commits) {
                    // CMP: the ALU does not drive the result bus, so neither
                    // the register/OPR write nor its memory commit happens.
                    if (op.d1 == 19 && m_.M.kind == OperandRef::kMem)
                        suppress_commit = true;
                } else {
                    wr_dst1(op.d1, v1, bsrc1);
                }
            }
            if (have2) {
                if (op.s2 == 4) set_stat(ctx);
                bool from_sigma = (op.s2 == 4);
                if (!(from_sigma && !ctx.commits)) wr_dst2(op.d2, v2);
            }

            // --- flag write ----------------------------------------------
            if (op.w && ctx.flag_mask)
                commit_flags(ctx.flag_mask, ctx.flags, ctx.hw);
        }

        // --- row type ------------------------------------------------------
        uint8_t next_loc = uint8_t((m_.upc.loc + 1) & 0x0F);
        bool carry = (m_.upc.loc == 0x0F);
        if (op.type == ucrom::MicroType::ALU) {
            AluLatch nl;
            nl.op = op.alu_op;
            nl.tmp = op.alu_tmp;
            nl.byte = m_.op8;
            nl.ea_const = false;
            nl.adjust = (m_.alu.op == kAdjd) ? 1
                        : (m_.alu.op == kAdja) ? 2
                                               : 0;
            nl.adjust_tmp = m_.alu.tmp;
            // A BIT row arms the same way ADJD/ADJA do: the NEXT latched
            // operation sees port B masked to the selected bit.
            nl.bit_arm = (m_.alu.op == kBit);
            nl.bit_n = m_.bit_n;
            uint8_t new_op = (op.alu_op == kOpc) ? alu_opc_select(m_) : op.alu_op;
            m_.alu = nl;
            // An armed ADJD/ADJA is normally consumed by the ADD/SUB latched
            // on this row.  If the next latched operation is NOT an ADD/SUB
            // the arm DISCHARGES instead: the adjust unit writes its plain
            // truncation (a nibble for ADJA, a byte for ADJD -- no decimal
            // correction, that needs an adder pass) back into its operand.
            // 030B (EXT) is the ONLY row in the ROM that takes this path, and
            // it is how EXT reduces the updated bit offset modulo 16 while
            // COUNT keeps the unmasked 16.  (Ledger, "0F 33/3B EXT".)
            if (nl.adjust && new_op != kAdd && new_op != kSub) {
                uint16_t* tp = nl.adjust_tmp == 0   ? &m_.tmpa
                               : nl.adjust_tmp == 1 ? &m_.tmpb
                                                    : &m_.tmpc;
                *tp = uint16_t(*tp & (nl.adjust == 2 ? 0x000Fu : 0x00FFu));
                m_.alu.adjust = 0;
            }
            if (op.alu_op == kBit) {
                // The bit index is captured when BIT is latched (the 0F 12/1A
                // CLR1 block overwrites tmpa on the very next row), modulo the
                // operand width.
                const uint16_t tmps[4] = {m_.tmpa, m_.tmpb, m_.tmpc, 0};
                m_.bit_n = uint8_t(tmps[op.alu_tmp & 3] & (m_.op8 ? 7u : 15u));
            }
            if (op.alu_op == kAbs) {
                // [-1E-] records the sign it is about to strip, for [-09-].
                const uint16_t tmps[4] = {m_.tmpa, m_.tmpb, m_.tmpc, 0};
                uint16_t v = tmps[op.alu_tmp & 3];
                m_.sign_neg = (v & (m_.op8 ? 0x0080u : 0x8000u)) != 0;
            }
            if (is_rloop) {
                // `R`: the row's own operation runs COUNT times, writing its
                // destination (always tmpb in the ROM) on every iteration.
                // Afterwards the latch is SPENT (see alu_eval).
                m_.alu.spent = true;
                while (m_.count != 0) {
                    m_.count = uint16_t(m_.count - 1);
                    AluResult sr = alu_step(m_, m_.alu);
                    RowCtx sc;
                    sc.sigma = sr.value;
                    sc.flags = sr.flags;
                    sc.flag_mask = sr.flag_mask;
                    set_stat(sc);
                    if (!op.nop_move()) wr_dst1(op.d1, sr.value, false);
                    if (op.w && sr.flag_mask)
                        commit_flags(sr.flag_mask, sr.flags, sr.hw);
                }
            }
        } else if (op.type == ucrom::MicroType::JMP) {
            if (cond_true(op.cond)) {
                next_loc = op.loc;
                carry = false;
            }
        } else {
            // CTL
            if (op.is_farjmp()) {
                m_.upc.page = 7;
                m_.upc.opc = uint8_t(op.far_loc() << 3);
                next_loc = 0;
                carry = false;
            } else {
                switch (op.ictl) {
                    case kIctlSusp: biu_.susp(); break;
                    // The mode flag.  MFS = native, MFC = 8080 emulation,
                    // ENDEM = leave emulation (RETEM restores the MD the
                    // BRKEM frame carried, which is always 1 because 0090
                    // pushes FLAGS BEFORE 0093 clears the flag).
                    case kIctlMfs: m_.mode8080 = false; break;
                    case kIctlMfc: m_.mode8080 = true; break;
                    case kIctlEndem: m_.mode8080 = false; break;
                    case kIctlFlush: biu_.flush(m_.pc); break;
                    case kIctlCitf:
                        m_.psw &= uint16_t(~(kFlagIE | kFlagBRK));
                        m_.set_flags(m_.psw);
                        break;
                    case kIctlClrCyV:
                        m_.psw &= uint16_t(~(kFlagCY | kFlagV));
                        m_.set_flags(m_.psw);
                        break;
                    case kIctlSetCyV:
                        m_.psw |= uint16_t(kFlagCY | kFlagV);
                        m_.set_flags(m_.psw);
                        break;
                    case kIctlSignTgl:
                        m_.sign_neg ^=
                            (m_.tmpb & (m_.op8 ? 0x0080u : 0x8000u)) != 0;
                        break;
                    // [-04-] / [-0D-] appear ONLY in the BCD-string block
                    // (0F 20/22/24/26).  [-04-] initialises the digit chain:
                    // CY = 0 and the aux latch set ("everything zero so far").
                    // [-0D-] clears the aux latch as soon as a corrected digit
                    // pair comes out non-zero, so the tail's `JMP [-09-]`
                    // resolves the final Z.  (Ledger, "the BCD string ops".)
                    case kIctlBcdInit:
                        m_.psw &= uint16_t(~kFlagCY);
                        m_.set_flags(m_.psw);
                        m_.sign_neg = true;
                        break;
                    case kIctlBcdNz:
                        if (!(m_.stat & kFlagZ)) m_.sign_neg = false;
                        break;
                    default: break;
                }
            }
            // A FARJMP row aliases Ext:SR as the 5-bit target, so it has no
            // bus cycle of its own.
            uint8_t sr = op.sr;
            uint8_t ect = op.is_farjmp() ? uint8_t(7) : op.ectl;
            bool io = sr_is_io(sr);
            uint8_t seg = sr_segment(sr);
            // Bus width follows the decoded operand width (OP8b) unless Ext
            // `[-03-]` (01ED) has forced WORD for the rest of the sequence.
            // See state.h / ledger A37.
            bool byte = m_.op8 && !m_.bus_word;
            switch (ect) {
                case kEctlMemR: bus_read(seg, m_.ind, byte, io, op.rom_addr); break;
                case kEctlMemW: bus_write(seg, m_.ind, byte, io, op.rom_addr); break;
                case kEctlWriteBack:
                    // [-06-]: the operand write-back strobe.  It commits OPR
                    // to the r/m operand ONLY when that operand is memory; a
                    // register r/m is written by the row's own `-> M`
                    // transfer (evidence: the 8F mod==3 ghost).
                    if (!suppress_commit && m_.WB.kind == OperandRef::kMem)
                        bus_write(m_.WB.seg, m_.WB.ea, m_.WB.byte, false,
                                  op.rom_addr);
                    break;
                case kEctlInta: bus_inta(op.rom_addr); break;
                case kEctlIntaTail:
                    m_.bus_word = true;
                    // 01ED, the row after the vector reaches tmpb.  Every
                    // software INT / INT3 / INTO / CHKIND / divide trap runs it
                    // too, and all of those forms are architecturally exact
                    // with it modelled as a no-op -- so whatever it drives on
                    // the bus (the acknowledge's trailing hold) has no
                    // architectural consequence.  Logged as inert.
                    break;
                default: break;
            }
        }

        if (pend_.active && opr_fresh_) emit_pending();

        if (ending) break;
        if (op.e) ending = true;
        m_.upc.loc = next_loc;
        if (carry) m_.upc.opc = uint8_t(m_.upc.opc + 1);
    }

    if (pend_.active) {
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    return true;
}

}  // namespace sim
