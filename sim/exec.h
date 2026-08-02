// exec.h -- the per-micro-row interpreter.  Micro-sequences are NEVER
// flattened into per-opcode C++: every instruction is executed by walking the
// ROM rows that docs/V20BITS.TXT actually contains.

#ifndef EXEC_H
#define EXEC_H

#include <cstdio>
#include <string>
#include <vector>

#include "alu.h"
#include "biu.h"
#include "loader.h"
#include "state.h"
#include "ucrom.h"

namespace sim {

class Cpu {
public:
    Cpu(const ucrom::UcRom& rom, Biu& biu) : rom_(rom), biu_(biu) {}

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
    Biu& biu_;
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

}  // namespace sim

#endif  // EXEC_H
