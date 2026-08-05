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
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "alu.h"
#include "loader_impl.h"
#include "state.h"
#include "ucrom.h"

namespace sim {

// S9b -- THE FALSIFIER FOR sec.19.8.2's OPEN MECHANISM, runnable.
// `V30SIM_REPCHAIN=eval` scales the chained REP-abort's extra clock with the
// completing store's wait count, which is what a WRITE-ACCEPT / completion-
// EVAL anchor predicts (the eval moves from T3 to T4+N under waits) and what a
// cadence/index anchor does not.  The two are IDENTICAL at w0 -- which is why
// the w0 corpus never separated them -- so the discriminating stimulus is a
// WAITED chained withdrawal.  Default 0 = the cadence anchor, unchanged.
inline int rep_chain_eval() {
    static const int v = ::getenv("V30SIM_REPCHAIN") &&
                         std::string(::getenv("V30SIM_REPCHAIN")) == "eval";
    return v;
}
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

    // --- S9a: the recognition boundary, in the TIMED domain -----------------
    // The pin-event firing BOUNDARY is replayed (pin_replay.h): the golden's
    // own pushed frame names the instruction the interrupt preempted, so the
    // boundary is the one whose live PC is that address.  `fire_pc` arms it;
    // when the sequence reaches the `E` row with that PC the successor's
    // opcode pop is RUN BUT SUPPRESSED (BiuTimed::boundary_no_pop) and the
    // sequence returns, leaving the driver the clock the pop would have taken.
    // A no-op on the functional bus (which is never armed).  -1 disables.
    void set_fire_pc(long pc) { fire_pc_ = pc; }
    bool fired_boundary() const { return fired_boundary_; }
    long boundary_clk() const { return boundary_clk_; }

    // --- §84: THE BRK/TF SINGLE-STEP ARM ------------------------------------
    // ONE bit.  It is SAMPLED from TF at every boundary the fetcher retires --
    // and a PREFIX retires as its own instruction (loader_impl.h,
    // `prefix_retire`), so a prefix byte is such a boundary.  The trap is
    // TAKEN at an instruction RETIRE boundary when the bit stands, and the
    // entry clears both TF and the bit.  The sample reads TF as it stands when
    // the sequence's `E` ROW OPENS, which is what makes `IRET` arm its own
    // boundary and `POPF` not: 007A (POP PSW) IS `9D`'s `E` row, so at its
    // open the popped word has not landed, while 01EA (RETI) is followed by
    // the far-jump chain, so by `CF`'s `E` row it has.  No opcode is named.
    //
    // MEASURED, sw/sm3_tf_law.py: 38/38 exact on the ruler-valid stratum of
    // the 197 chip-side vector-1 seeds, storm cadence 0 on 1,742/1,742 pairs,
    // and 44 storm traps landing on PREFIXED instructions all at retire (which
    // is what says the TAKE is at retire and not at the prefix boundary --
    // otherwise those 44 would have re-trapped the same byte forever).
    //
    // *Falsifier*: any trap taken at a prefix boundary; any `POPF` whose
    // trap does not fall two retire boundaries later; any `IRET` whose trap
    // does not fall one; any third ROM row that loads FLAGS from OPR.
    bool brk_fired() const { return brk_fired_; }
    void set_brk_enable(bool on) { brk_enable_ = on; }
    void clear_brk() { brk_arm_ = false; brk_take_ = false; brk_fired_ = false; }

    // --- S9b: the SAME boundary, in the MULTI-INSTRUCTION domain -------------
    // A single-instruction case has exactly one boundary, so `fire_pc` alone
    // names it.  A whole-program replay does not: the recorded resume CS:IP can
    // recur (a loop) and a bus position alone cannot separate two boundaries
    // with no bus cycle between them.  So the timed path uses the SAME TWO
    // COORDINATES the functional replay already uses (image_runner.cpp's
    // `want_fire`): the ordered bus position the acknowledge stands at, and the
    // CS:IP the chip's own pushed frame recorded.  Both are guards on the
    // existing predicate -- -1 disables either, which is the S9a single-
    // instruction configuration byte for byte.
    void set_fire_ev(long ev) { fire_ev_ = ev; }
    void set_fire_cs(long cs) { fire_cs_ = cs; }

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

    void deliver_read(bool reads_opr = true);
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
    long fire_pc_ = -1;
    long fire_ev_ = -1;
    long fire_cs_ = -1;
    // The replayed firing boundary, evaluated at the `E` row.  Same predicate
    // as the functional driver's, in the same two coordinates.
    bool ext_fire() const {
        if (fire_pc_ < 0 || m_.pc != uint16_t(fire_pc_)) return false;
        if (fire_cs_ >= 0 && m_.sreg[kCS] != uint16_t(fire_cs_)) return false;
        if (fire_ev_ >= 0 && biu_.ev_count() < fire_ev_) return false;
        return true;
    }
    // §84: the BRK/TF trap is recognised at the SAME boundary, by the same
    // machinery -- it is the existing entry with one more term on the arm,
    // not a second recognition path.  A REPLAYED external boundary wins the
    // tie, because that one is a directive from the capture and this one is a
    // prediction.
    bool at_fire_boundary() const { return ext_fire() || brk_take_; }
    void note_boundary_reason() { brk_fired_ = brk_take_ && !ext_fire(); }
    void brk_retire(uint8_t op_dbg = 0) {
        if (!brk_enable_) return;
        const bool tf = (m_.psw & kFlagBRK) != 0;
        const long rise = biu_.brk_rise();
        const long clk = biu_.clock();
        const bool seen = tf && (rise < 0 || clk >= rise + brk_floor());
        if (std::getenv("V30SIM_BRKTRACE"))
            std::fprintf(stderr, "BRKR clk=%ld tf=%d rise=%ld seen=%d "
                                 "take=%d arm=%d op=%02X\n",
                         clk, int(tf), rise, int(seen), int(brk_take_),
                         int(brk_arm_), unsigned(op_dbg));
        if (brk_take_) { brk_arm_ = false; brk_take_ = false; }
        else { brk_arm_ = seen; }
    }
    // §84 / §72's SHAPE, AND §84's ONE NUMBER.  The arm does not see a TF that
    // rose too recently -- the same shape as the IE-restore floor (§72, 2
    // clocks), one bit over, and for the same reason: a flag written into the
    // PSW reaches the recognition decision through a pipeline.
    //
    // MEASURED, over the 29 scored vector-1 seeds (`gapdist`, ledger §84.3):
    // the ONLY two opcodes that ever raise TF are `9D` and `CF`, and the
    // clocks between the rise and the retire that samples it are
    //     `9D`  1 (x16) or 2 (x12)      -- 007A IS `9D`'s `E` row, so it
    //                                      retires AT its own flag write
    //     `CF`  6 .. 26 (x813)          -- 01E8 FLUSHED the queue, so `CF`
    //                                      cannot retire until a refill lands
    // with NOTHING in between.  So the floor is bounded by the data to
    // [3, 6] and no value in that interval is distinguishable on this
    // population.  **3 is taken because it is not a new constant**: it is the
    // depth the INT LEVEL already pays to reach this same decision
    // (`timed_runner.cpp`'s `evpipe`, `docs/facts/interrupt_model.md`).
    //
    // *Falsifier*: any instruction whose TF rise is 3, 4 or 5 clocks before
    // the retire that must sample it -- that case separates [3,6] and this
    // tree has none.  Any third opcode raising TF also falsifies the premise.
    //
    // §85 (SM3 sitting 24) makes the constant SETTABLE, for the directed cell
    // that MEASURES it.  `V30SIM_BRKFLOOR` is an INSTRUMENT KNOB and nothing
    // else: it is read once, it defaults to the landed 3, and no gate, suite
    // or replay path sets it.  The cell's whole method is "run the identical
    // stimulus at floor = 1 … 7 and ask which one the silicon is", and that
    // needs the engine to be able to be wrong on purpose.
    static long brk_floor() {
        static const long v = [] {
            const char* s = std::getenv("V30SIM_BRKFLOOR");
            return s ? std::strtol(s, nullptr, 10) : 3L;
        }();
        return v;
    }
    static constexpr long kBrkFloorDefault = 3;
    bool brk_enable_ = false;   // program replay only; a single-instruction
                                // case has no successor boundary to trap at
    bool brk_arm_ = false;      // the arm bit itself
    bool brk_take_ = false;     // this sequence retires into the trap
    bool brk_fired_ = false;    // ...and it did
    bool fired_boundary_ = false;
    long boundary_clk_ = -1;
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

// --- U2 pass-3 diagnostic: THE COMPLETED-READ STORE DEPTH (C3) --------------
// `rdq_` is the EU's store of read words that have LANDED but that no `F` row
// has delivered into OPR yet; the RTL renders it as `rdq0`/`rdq1` + `rdq_n`,
// i.e. a bound of 2, and pass 2 asserted that bound WITHOUT proving it.  These
// two counters are the proof instrument: process-global maxima, printed by
// `V30SIM_QDEPTH=1` (one stderr line per NEW maximum, carrying the ROM row that
// pushed it), so a run over a form's whole tranche states the form's true
// bound.  Diagnostic only -- nothing reads them back.
extern int g_rdq_max;       // max |rdq_|          (EU-side completed reads)
extern int g_rddone_max;    // max |rd_done_q_|    (BIU-side completion times)
bool qdepth_trace();


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
// Source1 / Dest1 index of OPR (ucrom.cpp kStrSource1 / kStrDest1).
constexpr uint8_t kSrcOpr = 6;
}  // namespace exec_detail

template <class Bus>
uint16_t CpuT<Bus>::rd_operand(const OperandRef& r) const {
    switch (r.kind) {
        case OperandRef::kReg:
            // A byte operand read is the whole register PAIR rotated so the
            // selected half sits in the low lane (state.h::rb16).  Byte-width
            // consumers mask it off; the write-data latch does not, which is
            // where the sibling byte on the unused bus lane comes from.
            return r.byte ? m_.rb16(r.idx) : m_.gpr[r.idx];
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
            if (m_.intr_pending) {
                // S9a -- A CHAINED REP ABORT'S DECISION EDGE IS ONE CLOCK
                // LATER THAN THE LOOP ROW'S.  `interrupt_model.md` records the
                // two anchors separately and MEASURED them apart: the FIRST
                // boundary is POP-anchored (the decision edge at a fixed
                // opcode-pop+7, its flush invariant at pop+16) while a chained
                // boundary (>= 2 elements completed) is WRITE-ACCEPT-anchored.
                // The row cadence lands on the pop-anchored edge by itself; on
                // a chained boundary it is exactly ONE CLOCK short.
                //
                // MEASURED, uniform, no exceptions: over the 56 `INT.F3AA`
                // mid-string withdrawals the model's flush matches the golden
                // in all 35 one-element aborts and is EXACTLY +1 early in all
                // 21 chained ones (14 at two elements, 7 at three) -- a single
                // clock, not a per-iteration drift.
                //
                // PROVENANCE: MEASURED offset, MECHANISM OPEN.  Two anchors
                // were tried and REFUTED against the goldens: the completing
                // store's display clock (gives +2 on the chained cases) and
                // the previous store's display (gives 0, i.e. no change).  The
                // falsifier is any chained abort whose flush is not at the
                // loop row + 10, or any one-element abort that needs the +1.
                if (rep_elems_ >= 2)
                    biu_.charge(1 + rep_chain_eval() *
                                        biu_.last_write_waits());
                return false;
            }
            if (m_.rep_test == kTestZ)
                return ((psw & kFlagZ) != 0) == m_.rep_pol;
            if (m_.rep_test == kTestCy)
                return ((psw & kFlagCY) != 0) == m_.rep_pol;
            return true;
        }
        // BUSY is the 9B POLL_N pin, sampled on the row's own clock.  On the
        // functional bus there is no clock and no pin, so `poll_busy()` is a
        // constant false and 9B still retires in one pass (ledger R2,
        // unchanged).  On the TIMED bus it is the rig's replayed pin level,
        // and the ROM's own 3-row loop (006C `JMP BUSY 3` taken = 2 clocks,
        // 006F `JMP INTR 5` not taken = 1, 0070 `JMP 0` taken = 2) is the
        // measured FIVE-CLOCK sampling period -- no timer, no counter.
        case exec_detail::kCondBusy: return biu_.poll_busy();
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
void CpuT<Bus>::deliver_read(bool reads_opr) {
    // The F / OPR interlock: the EU stalls here until the NEXT outstanding bus
    // read has landed (the ONLY EU<->BIU data sync -- biu_model.md, ROM
    // confirmations).  No-op in the functional model.  Called exactly once per
    // `F` row, so the per-read in-order interlock queue lines up with the
    // ROM's own F rows.
    // ...and which HALF of the interlock applies is the direction of the
    // row's own touch.  A row that READS OPR must wait for the read that
    // fills it.  A row that only LOADS OPR (or, like `8F`'s 005A
    // `SIGMA -> SP F`, neither) waits only for a store to give OPR back:
    // the read it is nominally synchronising with is consumed by the NEXT
    // row's bus cycle, which takes OPR's contents at its own T1 (the OPR
    // shadow in biu_timed.h) and does not need the datapath to have caught
    // up.  MEASURED: `8F.0` mod0 -- the write-back's cycle is reserved at
    // the load's T3 eval, three clocks before the load's data reaches OPR,
    // and drives that data anyway.
    if (reads_opr) biu_.wait_read(); else biu_.wait_opr_free();
    if (rdq_.empty()) return;
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
    if (int(rdq_.size()) > g_rdq_max) {
        g_rdq_max = int(rdq_.size());
        if (qdepth_trace())
            std::fprintf(stderr, "QD rdq=%d upc=%04X clk=%ld\n", g_rdq_max,
                         upc, biu_.clock());
    }
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
    // S5: the BIU reserves the cycle NOW, on the row that issues the store.
    // The data-pairing latch below fills it in when OPR carries a fresh value.
    biu_.write_request(seg == kSegZero ? 0 : m_.sreg[seg], off, !byte, seg, io,
                       upc);
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
    if (int(rdq_.size()) > g_rdq_max) {
        g_rdq_max = int(rdq_.size());
        if (qdepth_trace())
            std::fprintf(stderr, "QD rdq=%d upc=%04X clk=%ld (inta)\n",
                         g_rdq_max, upc, biu_.clock());
    }
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
    fired_boundary_ = false;
    biu_.clear_consumed();
    brk_fired_ = false;
    brk_take_ = false;
    LoadResult ld = loader_decode(m_, biu_);
    if (brk_enable_) {
        // §84.  Every PREFIX this sequence just retired was a boundary, and
        // it SAMPLED the arm; TF cannot move across a prefix chain, so one
        // assignment covers the whole chain.  The TAKE is then decided here,
        // before the opcode runs, which is what lets the ordinary recognised-
        // boundary machinery carry the trap without a second path.
        if (m_.pfxcnt > 0) {
            const long rise = biu_.brk_rise();
            brk_arm_ = (m_.psw & kFlagBRK) != 0 &&
                       (rise < 0 || biu_.clock() >= rise + brk_floor());
        }
        brk_take_ = brk_arm_;
    }
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
        // S9b -- A PRE-DECODE-EXECUTED FORM RETIRES AT A BOUNDARY TOO.
        // `HLT`, `EI`, `DI`, `STC`, ... never enter the ROM, so they have no
        // `E` row and the recognition check below never ran for them.  In a
        // single-instruction case that is invisible (the case IS the ROM
        // form); in a whole-program replay it means every boundary that
        // follows one of these was silently skipped, and the replay then
        // withdrew from whatever string loop it met next -- 9 of the 1,008
        // EVT seeds, all of them reported as REP-WITHDRAW-UNMATCHED.  A HALT
        // is excluded: a halted part's wake is its own sequence (sec.19.6).
        if (!ld.halt && at_fire_boundary()) {
            boundary_clk_ = biu_.boundary_no_pop(!m_.intr_pending);
            fired_boundary_ = true;
            note_boundary_reason();
        }
        brk_retire(ld.opcode);
        return true;
    }

    bool ok = run_micro(ld.entry);
    rep_abort_at_ = -1;
    brk_retire(ld.opcode);
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
        // §84: the arm's SAMPLE INSTANT.  TF as it stands when the `E` row
        // OPENS -- before that row's `F` interlock delivers anything.  007A
        // (POP PSW) IS `9D`'s `E` row, so `POPF` samples the OLD TF; 01EA
        // (RETI) is followed by the far-jump chain, so `IRET` samples the NEW
        // one.  The asymmetry is ROM geometry read at one instant, not a rule
        // about two opcodes.

        ++rows_;
        if (bank >= 0) ++g_row_cover[bank * 4 + m_.upc.row()];

        // ROW TRACE (env-gated diagnostic, V30SIM_ROWTRACE=1).  One line per
        // micro-row: the CLOCK the row opens on, the ROM row index, and the
        // disassembled row.  Written to stderr, reads no model state beyond
        // what the trace above already prints, and is the instrument the REP
        // re-entry census reads the row schedule out of.  Printed BEFORE the
        // `F` interlock so the line shows the clock the row was REACHED; the
        // interlock's own stall is then visible as the gap to the next line.
        static const bool kRowTrace = std::getenv("V30SIM_ROWTRACE") != nullptr;
        if (kRowTrace) {
            std::fprintf(stderr, "RT %ld %04X %s\n", biu_.clock(),
                         bank >= 0 ? unsigned(bank * 4 + m_.upc.row()) : 0xFFFFu,
                         row_text(op).c_str());
        }

        // `F` is the bus interlock: the row waits for the outstanding read to
        // land in OPR (ledger, "F = bus interlock").  In TIMED mode the wait
        // is real -- and it covers the PRE-DECODE operand read too, which the
        // loader delivers straight into OPR without going through `rdq_`.
        if (op.f) {
            // I1 / F39 -- THE FLAG REGISTER IS FED BY THE DATA LATCH, NOT BY
            // THE ROW.  A micro-row's destination write-enable is a LEVEL for
            // as long as the row STANDS: a row blocked on its `F` interlock
            // has its control decoded and its destination selected, so a
            // destination fed from the read latch takes the word when the
            // LATCH CLOSES, not when the row releases.  Invisible for every
            // other destination -- nothing runs between the row's arrival and
            // its release -- but FLAGS is wired to the outside world twice
            // over (S5 on the status pins and the IE gate of the recognition
            // pipeline), so there the early load SHOWS, and silicon shows it:
            // `interrupt_model.md`, "POP PSW consumes the popped image at its
            // read's data edge (the new IE shows in the PS bits during the
            // read's own T4)".
            //
            // The rule names no opcode.  It hits EXACTLY TWO ROM ROWS -- 007A
            // (POP PSW) and 01EA (RETI), the only rows in the ROM carrying
            // source OPR, destination FLAGS and the `F` interlock.  Five other
            // rows write FLAGS and none takes OPR through an `F`; E1 measured
            // that same pair on silicon (108/108 H-IDENTICAL).
            //
            // The word is already known: `rdq_` is filled at ISSUE time (the
            // functional read runs eagerly), so this is a re-ordering of the
            // COMMIT and not a new value.  `wr_dst1`'s FLAGS arm below writes
            // the identical word again when the row retires.
            //
            // *Falsifier*: any `OPR -> FLAGS` row whose flag write is NOT
            // visible at its read's T4, or any third ROM row acquiring that
            // source/destination pair.
            bool latch_flags = (op.s1 == exec_detail::kSrcOpr && op.d1 == 15);
            if (latch_flags) biu_.arm_flags_latch(&m_.psw);
            deliver_read(op.s1 == exec_detail::kSrcOpr);
            if (latch_flags) biu_.arm_flags_latch(nullptr);
        }

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
                // M11 -- THE REDIRECT BUBBLE IS NOT PAID ON A JUMP TO THE ROW
                // THE SEQUENCER RAN ON THE PREVIOUS CLOCK.  A taken micro-JMP
                // normally costs one clock (7.7): the target address is only
                // known at the end of the row, so the next ROM read is late.
                // A jump BACK BY ONE ROW is the one case where no new read is
                // needed -- the target is the row the sequencer read one clock
                // ago -- so the ROM's tightest loop runs at one row per clock.
                //
                // MEASURED, and the measurement is a subtraction, not a fit:
                // `cx = 0` and `cx = 1` pin the REP STOS entry (micro-row 0 at
                // the opcode pop + 2, M8b) and its exit path (nine clocks from
                // the store row to the successor's pop) exactly, and the
                // silicon then requires the SECOND store row of a `cx = 2`
                // REP STOS to run on the FIRST store's own T1 -- reachable
                // only if `00BF -> 00C0(JMP REP) -> 00BF` is TWO clocks.  The
                // 166 cases that need it are exactly those whose EU entered
                // late enough that M10's slot is already free (store T1 minus
                // the row's own clock = 2).
                //
                // SCOPE, stated because it is thin: the whole v0.1 corpus
                // contains exactly ONE taken-JMP site whose target is its own
                // `loc - 1` -- `00C0`, the STOS/SCAS REP loop (a census over
                // every form's first six cases finds 59 taken-JMP sites, 8 of
                // them backward, and only this one by a single row).  So the
                // assets do NOT separate this general form from "the STOS REP
                // loop-back is free".  The general form is kept because it is
                // the falsifiable one: any other loc-1 backward jump a future
                // stimulus reaches must also be free.  Over the 169,000-case
                // suite it moves three forms and only upward
                // (F3AA/F3AB/F2AA -> 500/500) and nothing else at all.
                if (op.loc + 1 != m_.upc.loc)
                    ++row_clocks;   // taken-JMP redirect bubble
            }
        } else {
            // CTL
            if (op.is_farjmp()) {
                m_.upc.page = 7;
                m_.upc.opc = uint8_t(op.far_loc() << 3);
                next_loc = 0;
                carry = false;
                // H1a NOTE (SM3 sitting 10).  This row is the interrupt
                // entry's ONE door: the entry routine is the page-7 block
                // `111.0001?000` at `01EC` (the `?` is the ROM's own statement
                // that `INT` and `INTEM` are the same rows) and every entry in
                // the part reaches it through a `FARJMP` -- `CC`/`CD`/`CE`,
                // the divide trap (`0195`, `01A9`), `CHKIND` (`0283`), the
                // hardware BRK/TF and NMI rows (`01D9`, `01DB`), both INTA
                // vector-fetch tails (`01DF`, `01E3`), and `BRKEM`.  A hook
                // here that armed a recognition-floor flop -- H1a's landing --
                // WAS BUILT AND IS REFUTED (SM3 sitting 10), and SM3 sitting
                // 11 replaced the floor's arm altogether with PSW.IE's rising
                // edge; see `ie_rise_` in biu_timed.h.  The funnel is recorded
                // because the fact is true and re-usable; nothing arms from it
                // today, and nothing should.
                // A FARJMP is a taken micro-jump and pays the same sequencer
                // redirect bubble (7.7).  MEASURED on the shift family: with
                // it, D2/D3/C0/C1 retire at pop+10+n for n>=1 and pop+9 for
                // n==0 -- exactly the measured shift law -- and D0/D1, which
                // reach the same R row WITHOUT a FARJMP, stay at 6.
                ++row_clocks;
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
                    case exec_detail::kIctlFlush:
                        biu_.flush(m_.sreg[kCS], m_.pc);
                        break;
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
            // S9a: a RECOGNISED boundary runs the retire deadline and keeps
            // the byte -- no pop, no clock charged past it.  The sequence
            // still finishes its post-`E` row (which costs no clocks but does
            // carry datapath work -- `9D`'s `SIGMA -> SP` lives there); only
            // the successor's decode is what does not happen.
            if (at_fire_boundary()) {
                // H1: a mid-string REP withdrawal is not an instruction
                // retire, so it does not carry the post-redirect floor.
                boundary_clk_ = biu_.boundary_no_pop(!m_.intr_pending);
                fired_boundary_ = true;
                note_boundary_reason();
                row_clocks = 0;
            } else {
                biu_.opcode_prefetch(m_.sreg[kCS]);
            }
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
    //
    // M8b: the clock AFTER the pop belongs to the successor's decode either
    // way.  On the E-row path it is part of `charge(row_clocks)` above; on
    // this deferred path that charge has already gone by, so it is spent
    // here.  Without it the deferred boundary hands over one clock early and
    // the successor's first byte demand lands at pop+1 instead of pop+2 --
    // the whole `O -> I0` residual of the Q1 family (sw/q1diff.py).
    if (fired_boundary_) return true;          // S9a: no successor decode
    const bool deferred = !biu_.opcode_pending();
    if (at_fire_boundary()) {
        boundary_clk_ = biu_.boundary_no_pop(!m_.intr_pending);  // S9a deferred
        fired_boundary_ = true;
        note_boundary_reason();
        return true;
    }
    biu_.opcode_prefetch(m_.sreg[kCS]);
    if (deferred) biu_.charge(1);
    return true;
}

}  // namespace sim

#endif  // EXEC_IMPL_H
