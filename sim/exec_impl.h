// exec_impl.h -- the per-micro-row interpreter, as a template over the BUS
// POLICY.  Micro-sequences are NEVER flattened into per-opcode C++: every
// instruction is executed by walking the ROM rows that docs/V20BITS.TXT
// actually contains.
//
// Split out of exec.{h,cpp} for the ucsim-t timing campaign (T0).  The
// interpreter body is UNCHANGED; the concrete `Biu&` member became a `Bus&`
// template parameter, and exec.cpp's file-static tables moved from an
// anonymous namespace into `sim::exec_detail`.
//
//   exec.cpp        emits `CpuT<Biu>`      -- the FUNCTIONAL bus (no timing)
//   exec_timed.cpp  emits `CpuT<BiuTimed>` -- the TIMED bus (clock + rows)
//
// The explicit-instantiation DECLARATION in exec.h (`extern template class
// CpuT<Biu>;`) is what preserves the functional build's codegen shape: no
// other translation unit instantiates the interpreter, they all call the
// single out-of-line copy in exec.o, exactly as before the split.
//
// Bus concept (the whole surface the interpreter and the loader need):
//   uint8_t  next_byte(uint16_t cs, uint16_t upc)
//   uint16_t mem_read (uint16_t seg_val, uint16_t off, bool word,
//                      uint8_t seg_idx, uint16_t upc)
//   void     mem_write(uint16_t seg_val, uint16_t off, uint16_t data,
//                      bool word, uint8_t seg_idx, uint16_t upc)
//   uint16_t io_read  (uint16_t port, bool word, uint16_t upc)
//   void     io_write (uint16_t port, uint16_t data, bool word, uint16_t upc)
//   uint16_t inta_read(uint16_t upc)
//   void     susp()
//   void     flush(uint16_t pc)
//   void     clear_consumed()
//   long     ev_count() const
// plus the five TIMED extensions added in ucsim-t T1 -- all `{}` on sim::Biu,
// so the functional instantiation is behaviourally and codegen-wise unchanged:
//   void     charge(int n)                 EU burns n clocks of row cadence
//   void     wait_read()                   the F / OPR bus interlock
//   void     opcode_prefetch(uint16_t cs)  decoder pops the successor's opcode
//   bool     opcode_pending() const        is one already latched?
//   void     prefix_retire()               the next pop is an F again

#ifndef EXEC_IMPL_H
#define EXEC_IMPL_H

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "alu.h"
#include "loader_impl.h"
#include "state.h"
#include "ucrom.h"

namespace sim {

std::string row_text(const ucrom::MicroOp& op);


template <class Bus>
class CpuT {
public:
    CpuT(const ucrom::UcRom& rom, Bus& biu) : rom_(rom), biu_(biu) {}

    Machine& state() { return m_; }
    const Machine& state() const { return m_; }

    // Executes exactly one instruction (pre-decode + micro-sequence).
    // Returns false if the step limit was hit (runaway sequence).
    bool step();

    // --- external events ---------------------------------------------------
    // Kinds of hardware entry into the internal (page 7) interrupt routines.
    // The entry ADDRESS is hardware, not ROM: the loader is bypassed and the
    // micro-PC is forced to the routine's first row.
    enum EventKind : uint8_t {
        kEvtBrk = 0,   // 111.00000000.00 row 0 -- CONST 1, the BRK/TF trap
        kEvtNmi = 1,   // 111.00000000.00 row 2 -- CONST 2, the NMI vector
        kEvtInt = 2,   // 111.00000010.00      -- the INTA vector fetch
    };
    // Runs one interrupt entry to completion (acknowledge if any, vector fetch,
    // PSW/PS/PC pushes, queue flush).  Returns false on a runaway sequence.
    bool interrupt(EventKind kind);

    // --- power-on reset -----------------------------------------------------
    // Runs the ROM's OWN reset sequence (page 111 opcode 00000011, rows
    // 01D0-01D5: ZEROS -> DS/FLAGS/ES/SS, ONES -> CS, ZEROS -> PC, FLUSH,
    // MFS).  No suite ever resets the part, so these rows were unexecuted
    // through S2; a fuzz-bank image replay starts at RESET RELEASE, which is
    // exactly the entry they exist for.
    bool reset();

    // Multi-instruction interrupt replay (image mode).  The firing boundary is
    // REPLAYED from the capture, expressed as a position in the ORDERED BUS
    // STREAM (Biu::ev_count) rather than as an instruction index, because that
    // is the only coordinate that also names a point INSIDE a string loop.
    // Once the sim's stream reaches `ev`, the `REP` continuation fails and the
    // ROM's own withdrawal path (009A -> 009B -> REPX 0223) runs.  -1 disables.
    void set_evt_at(long ev) { evt_at_ = ev; }

    // Replay hook for an aborted REP: after `n` completed elements the string
    // loop's `REP` continuation fails and `INTR` reads true, which is how the
    // ROM itself (009A -> 009B -> REPX 0223) withdraws from the string and
    // backs PC up over the prefixes.  -1 disables.  Cleared by every step().
    void set_rep_abort(int n) { rep_abort_at_ = n; }
    int rep_elements() const { return rep_elems_; }

    void set_trace(std::FILE* f) { trace_ = f; }

    int rows_executed() const { return rows_; }

    // --- ALU-hardware attribution (`run --alu-hw-report`) -----------------
    // Reset at every step().  `hw_owned(i)` is the set of PSW bits still
    // standing at the end of the instruction whose LAST write came out of
    // hardware behaviour `i` (AluHw bit 1<<i); `hw_writes(i)` counts the flag
    // commits that behaviour drove.
    uint16_t hw_owned(int i) const { return hw_owned_[i]; }
    long hw_writes(int i) const { return hw_writes_[i]; }

private:
    void commit_flags(uint16_t mask, uint16_t flags, uint8_t hw);

    struct RowCtx {
        uint16_t sigma = 0;
        bool commits = true;
        uint16_t flags = 0;
        uint16_t flag_mask = 0;
        uint8_t hw = 0;  // AluHw attribution of `flags`
    };

    // A bus write whose data phase has not run yet.  The data is OPR at the
    // moment the cycle runs, and the cycle runs as soon as OPR carries a
    // value that has not already been consumed by an earlier write
    // (ledger: "write-data pairing").
    struct Pending {
        bool active = false;
        uint16_t off = 0;
        uint8_t seg = 0;
        bool byte = false;
        bool io = false;
        uint16_t upc = 0;
    };

    uint16_t rd_src1(uint8_t c, const RowCtx& ctx, const ucrom::MicroOp& op,
                     bool& byte_src);
    void wr_dst1(uint8_t c, uint16_t v, bool byte_src);
    uint16_t rd_src2(uint8_t c, const RowCtx& ctx);
    void wr_dst2(uint8_t c, uint16_t v);
    uint16_t rd_operand(const OperandRef& r) const;
    void wr_operand(const OperandRef& r, uint16_t v);
    uint8_t sr_segment(uint8_t sr) const;
    bool sr_is_io(uint8_t sr) const;
    bool cond_true(uint8_t cond);
    void set_stat(const RowCtx& ctx);

    void deliver_read();
    void emit_pending();
    void bus_read(uint8_t seg, uint16_t off, bool byte, bool io, uint16_t upc);
    void bus_write(uint8_t seg, uint16_t off, bool byte, bool io, uint16_t upc);
    void bus_inta(uint16_t upc);
    void begin_sequence();
    bool run_micro(const MicroPc& entry);

    const ucrom::UcRom& rom_;
    Bus& biu_;
    Machine m_;
    Pending pend_;
    std::vector<uint16_t> rdq_;  // completed reads awaiting OPR delivery
    bool opr_fresh_ = false;
    std::FILE* trace_ = nullptr;
    int rows_ = 0;
    int rep_abort_at_ = -1;
    int rep_elems_ = 0;
    long evt_at_ = -1;
    uint16_t hw_owned_[kHwCount] = {};
    long hw_writes_[kHwCount] = {};
};

std::string row_text(const ucrom::MicroOp& op);

// --- micro-row coverage (the S4 sufficiency counter) ------------------------
// One counter per ROM row (`bank * 4 + row`, i.e. the same index space as
// `ucrom::UcRom::op()`), accumulated across every case a process runs.  A row
// that no green gate ever executes is an UNTESTED ROM claim; the campaign's
// closure report enumerates them.  Process-global on purpose -- the counter is
// a property of the run, not of a Cpu instance.
extern long g_row_cover[ucrom::kRowCount];


namespace exec_detail {
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
}  // namespace exec_detail

template <class Bus>
uint16_t CpuT<Bus>::rd_operand(const OperandRef& r) const {
    switch (r.kind) {
        case OperandRef::kReg:
            return r.byte ? uint16_t(m_.rb(r.idx)) : m_.gpr[r.idx];
        case OperandRef::kSregRef: return m_.sreg[r.idx];
        case OperandRef::kMem: return m_.opr;  // pre-read operand data
        default: return 0;
    }
}

template <class Bus>
void CpuT<Bus>::wr_operand(const OperandRef& r, uint16_t v) {
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
template <class Bus>
bool CpuT<Bus>::sr_is_io(uint8_t sr) const {
    if (sr != 1) return false;
    return m_.xop == 0xF || m_.xop == 0x6;
}

template <class Bus>
uint8_t CpuT<Bus>::sr_segment(uint8_t sr) const {
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
template <class Bus>
void CpuT<Bus>::commit_flags(uint16_t mask, uint16_t flags, uint8_t hw) {
    m_.psw = uint16_t((m_.psw & ~mask) | (flags & mask));
    m_.set_flags(m_.psw);
    for (int i = 0; i < kHwCount; ++i) hw_owned_[i] &= uint16_t(~mask);
    for (int i = 0; i < kHwCount; ++i) {
        if (!(hw & (1u << i))) continue;
        ++hw_writes_[i];
        hw_owned_[i] |= uint16_t(mask & kHwAttrib[i]);
    }
}

template <class Bus>
void CpuT<Bus>::set_stat(const RowCtx& ctx) {
    if (!ctx.flag_mask) return;
    m_.stat = uint16_t((m_.stat & ~ctx.flag_mask) | (ctx.flags & ctx.flag_mask));
}

template <class Bus>
bool CpuT<Bus>::cond_true(uint8_t cond) {
    uint16_t f = m_.stat;
    uint16_t psw = m_.psw;
    bool cy = f & kFlagCY, z = f & kFlagZ, s = f & kFlagS, v = f & kFlagV;
    switch (cond) {
        case exec_detail::kCondC: return cy;
        case exec_detail::kCondNC: return !cy;
        case exec_detail::kCondZ: return z;
        case exec_detail::kCondNZ: return !z;
        case exec_detail::kCondOp8b: return m_.op8;
        case exec_detail::kCondCntz:
            // "count not zero": the loop-continue test decrements COUNT and
            // jumps while it is still non-zero (ENTER walk = level-1 copies).
            m_.count = uint16_t(m_.count - 1);
            return m_.count != 0;
        case exec_detail::kCondL: return s != bool(v);
        case exec_detail::kCondOp8: return m_.imm8;
        case exec_detail::kCondAlways: return true;
        case exec_detail::kCondSign: return !m_.sign_neg;
        case exec_detail::kCondO: return (psw & kFlagV) != 0;
        case exec_detail::kCondNS: return (m_.tmpb & (m_.op8 ? 0x0080u : 0x8000u)) == 0;
        case exec_detail::kCondRep: {
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
        case exec_detail::kCondBusy: return false;
        case exec_detail::kCondIntr: return m_.intr_pending;
        case exec_detail::kCondOpc: {
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

template <class Bus>
uint16_t CpuT<Bus>::rd_src1(uint8_t c, const RowCtx& ctx, const ucrom::MicroOp& op,
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

template <class Bus>
void CpuT<Bus>::wr_dst1(uint8_t c, uint16_t v, bool byte_src) {
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

template <class Bus>
uint16_t CpuT<Bus>::rd_src2(uint8_t c, const RowCtx& ctx) {
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

template <class Bus>
void CpuT<Bus>::wr_dst2(uint8_t c, uint16_t v) {
    switch (c) {
        case 0: m_.tmpa = v; break;
        case 1: m_.tmpb = v; break;
        case 2: m_.ind = v; break;
        default: break;
    }
}

// --- bus plumbing ----------------------------------------------------------

template <class Bus>
void CpuT<Bus>::deliver_read() {
    if (rdq_.empty()) return;
    // The F / OPR interlock: the EU stalls here until the outstanding bus
    // read has landed (the ONLY EU<->BIU data sync -- biu_model.md, ROM
    // confirmations).  No-op in the functional model.
    biu_.wait_read();
    m_.opr = rdq_.front();
    rdq_.erase(rdq_.begin());
    opr_fresh_ = true;
}

template <class Bus>
void CpuT<Bus>::emit_pending() {
    if (!pend_.active) return;
    if (pend_.io)
        biu_.io_write(pend_.off, m_.opr, !pend_.byte, pend_.upc);
    else
        biu_.mem_write(pend_.seg == kSegZero ? 0 : m_.sreg[pend_.seg], pend_.off,
                       m_.opr, !pend_.byte, pend_.seg, pend_.upc);
    pend_.active = false;
    opr_fresh_ = false;
}

template <class Bus>
void CpuT<Bus>::bus_read(uint8_t seg, uint16_t off, bool byte, bool io, uint16_t upc) {
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

template <class Bus>
void CpuT<Bus>::bus_write(uint8_t seg, uint16_t off, bool byte, bool io,
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
template <class Bus>
void CpuT<Bus>::bus_inta(uint16_t upc) {
    if (pend_.active) {
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    rdq_.push_back(biu_.inta_read(upc));
}

// --- the interpreter -------------------------------------------------------

template <class Bus>
void CpuT<Bus>::begin_sequence() {
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
template <class Bus>
bool CpuT<Bus>::reset() {
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

template <class Bus>
bool CpuT<Bus>::interrupt(EventKind kind) {
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

template <class Bus>
bool CpuT<Bus>::step() {
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

template <class Bus>
bool CpuT<Bus>::run_micro(const MicroPc& entry) {
    m_.upc = entry;
    bool ending = false;
    int guard = 0;

    for (;;) {
        if (++guard > exec_detail::kMaxRows) return false;
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
        // land in OPR (ledger, "F = bus interlock").  In TIMED mode the wait
        // is real -- and it covers the PRE-DECODE operand read too, which the
        // loader delivers straight into OPR without going through `rdq_`.
        if (op.f) { biu_.wait_read(); deliver_read(); }

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
        // Micro-row cadence (ucsim-t T1): one ROM row = one CPU clock; a TAKEN
        // micro-JMP costs one more (the sequencer's redirect bubble); an R-loop
        // costs one clock per iteration.  The E row and the row after it are
        // charged by the SUCCESSOR's decode, which overlaps them.
        int row_clocks = 1;
        int rloop_iters = 0;

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
                    ++rloop_iters;
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
                ++row_clocks;   // taken-JMP redirect bubble
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
                    case exec_detail::kIctlSusp: biu_.susp(); break;
                    // The mode flag.  MFS = native, MFC = 8080 emulation,
                    // ENDEM = leave emulation (RETEM restores the MD the
                    // BRKEM frame carried, which is always 1 because 0090
                    // pushes FLAGS BEFORE 0093 clears the flag).
                    case exec_detail::kIctlMfs: m_.mode8080 = false; break;
                    case exec_detail::kIctlMfc: m_.mode8080 = true; break;
                    case exec_detail::kIctlEndem: m_.mode8080 = false; break;
                    case exec_detail::kIctlFlush: biu_.flush(m_.pc); break;
                    case exec_detail::kIctlCitf:
                        m_.psw &= uint16_t(~(kFlagIE | kFlagBRK));
                        m_.set_flags(m_.psw);
                        break;
                    case exec_detail::kIctlClrCyV:
                        m_.psw &= uint16_t(~(kFlagCY | kFlagV));
                        m_.set_flags(m_.psw);
                        break;
                    case exec_detail::kIctlSetCyV:
                        m_.psw |= uint16_t(kFlagCY | kFlagV);
                        m_.set_flags(m_.psw);
                        break;
                    case exec_detail::kIctlSignTgl:
                        m_.sign_neg ^=
                            (m_.tmpb & (m_.op8 ? 0x0080u : 0x8000u)) != 0;
                        break;
                    // [-04-] / [-0D-] appear ONLY in the BCD-string block
                    // (0F 20/22/24/26).  [-04-] initialises the digit chain:
                    // CY = 0 and the aux latch set ("everything zero so far").
                    // [-0D-] clears the aux latch as soon as a corrected digit
                    // pair comes out non-zero, so the tail's `JMP [-09-]`
                    // resolves the final Z.  (Ledger, "the BCD string ops".)
                    case exec_detail::kIctlBcdInit:
                        m_.psw &= uint16_t(~kFlagCY);
                        m_.set_flags(m_.psw);
                        m_.sign_neg = true;
                        break;
                    case exec_detail::kIctlBcdNz:
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
                case exec_detail::kEctlMemR: bus_read(seg, m_.ind, byte, io, op.rom_addr); break;
                case exec_detail::kEctlMemW: bus_write(seg, m_.ind, byte, io, op.rom_addr); break;
                case exec_detail::kEctlWriteBack:
                    // [-06-]: the operand write-back strobe.  It commits OPR
                    // to the r/m operand ONLY when that operand is memory; a
                    // register r/m is written by the row's own `-> M`
                    // transfer (evidence: the 8F mod==3 ghost).
                    if (!suppress_commit && m_.WB.kind == OperandRef::kMem)
                        bus_write(m_.WB.seg, m_.WB.ea, m_.WB.byte, false,
                                  op.rom_addr);
                    break;
                case exec_detail::kEctlInta: bus_inta(op.rom_addr); break;
                case exec_detail::kEctlIntaTail:
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

        // --- cadence -------------------------------------------------------
        // The successor's opcode pop rides the E row's own clock: measured
        // (v0.1 saturated-queue goldens, all forms) the next F pop lands
        // exactly two clocks before the successor's first micro-row, and the
        // E row is two rows before it.  The post-E row therefore overlaps the
        // successor's decode and is charged there, not here.
        // A write still STAGED in the data-pairing latch has not even been
        // handed to the bus yet, so the instruction is not complete: the pop
        // is released after the tail below emits it (max-of-two-deadlines).
        if (ending) {
            row_clocks = 0;
        } else if (op.e && !pend_.active) {
            biu_.opcode_prefetch(m_.sreg[kCS]);
        }
        biu_.charge(row_clocks + rloop_iters);

        if (ending) break;
        if (op.e) ending = true;
        m_.upc.loc = next_loc;
        if (carry) m_.upc.opc = uint8_t(m_.upc.opc + 1);
    }

    if (pend_.active) {
        if (!opr_fresh_) deliver_read();
        emit_pending();
    }
    // Releases a pop the E row deferred because a write was still staged.
    // A no-op when the E row already latched the successor's opcode.
    biu_.opcode_prefetch(m_.sreg[kCS]);
    return true;
}

}  // namespace sim

#endif  // EXEC_IMPL_H
