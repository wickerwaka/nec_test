// exec.h -- the per-micro-row interpreter.  Micro-sequences are NEVER
// flattened into per-opcode C++: every instruction is executed by walking the
// ROM rows that docs/V20BITS.TXT actually contains.

#ifndef EXEC_H
#define EXEC_H

#include <cstdio>
#include <string>
#include <vector>

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

    void set_trace(std::FILE* f) { trace_ = f; }

    int rows_executed() const { return rows_; }

private:
    struct RowCtx {
        uint16_t sigma = 0;
        bool commits = true;
        uint16_t flags = 0;
        uint16_t flag_mask = 0;
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

    const ucrom::UcRom& rom_;
    Biu& biu_;
    Machine m_;
    Pending pend_;
    std::vector<uint16_t> rdq_;  // completed reads awaiting OPR delivery
    bool opr_fresh_ = false;
    std::FILE* trace_ = nullptr;
    int rows_ = 0;
};

std::string row_text(const ucrom::MicroOp& op);

}  // namespace sim

#endif  // EXEC_H
