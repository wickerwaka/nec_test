// rows.h -- the per-CPU-clock record the TIMED bus emits, and the two sinks
// that write it out.
//
// One `ClockRow` == one CPU clock.  The field set is deliberately the RAW pin
// sample set the existing comparators already speak, not a synthesized 11-column
// row: the golden 11-column `cycles` rows are DERIVED from these by
// sw/check_core.py::build_rows_sim (shadow-queue reconstruction + column
// synthesis), and the fuzz/black-box replay tooling consumes the same raw
// records (sw/check_seq.py::run_image).  Emitting the raw records and letting
// the UNMODIFIED python machinery synthesize is what makes the timing gate cost
// zero new comparison code.
//
// Emitter (a) `TextRowEmitter`  -> sw/check_core.py::parse_out's textual format
//                                  (`= <idx>` / `r ...` / `f ...` / `.`),
//                                  byte-compatible with hdl/tb/tb_v30_core.sv.
// Emitter (b) `ChipRowsEmitter` -> chip_rows NDJSON, one object per clock,
//                                  keys as sw/check_seq.py::run_image.

#ifndef ROWS_H
#define ROWS_H

#include <cstdint>
#include <cstdio>

namespace sim {

// Bus status (BS2-0), as sw/check_core.py::BUS_STR decodes it.
enum BusStatus : uint8_t {
    kBsInta = 0, kBsIoR = 1, kBsIoW = 2, kBsHalt = 3,
    kBsCode = 4, kBsMemR = 5, kBsMemW = 6, kBsPasv = 7,
};

// T-state annotation, as sw/check_core.py::T_STR decodes it.  NOTE the order:
// Tw is 4 and T4 is 5.
enum TState : uint8_t {
    kTi = 0, kT1 = 1, kT2 = 2, kT3 = 3, kTw = 4, kT4 = 5,
};

// Queue status (QS1:QS0), as sw/check_core.py::Q_STR decodes it.
enum QStatus : uint8_t {
    kQsNone = 0, kQsFirst = 1, kQsEmpty = 2, kQsSubseq = 3,
};

struct ClockRow {
    long     clk = 0;          // absolute CPU clock index within the case
    uint8_t  tstate = kTi;
    uint8_t  bs = kBsPasv;     // the REGISTERED status output (see biu_timed.h)
    uint8_t  qs = kQsNone;
    uint8_t  ube_n = 1;
    uint32_t ad_addr = 0;      // 20-bit address-phase (mid-cycle) sample
    uint16_t ad_data = 0;      // 16-bit end-of-cycle sample
    uint8_t  ps = 0;           // 4-bit A19:A16 in T1 / S6:S3 in the data phase
    uint8_t  lock_n = 1;       // BUSLOCK_N (inactive high); not modelled yet
    uint16_t upc = 0xFFFF;     // ROM row this clock is attributed to
};

class RowEmitter {
public:
    virtual ~RowEmitter() = default;
    virtual void begin_case(long idx) = 0;
    virtual void row(const ClockRow& r) = 0;
    // The 14 architectural registers in sw/check_core.py::REGS order:
    // ax cx dx bx sp bp si di es cs ss ds ip flags.
    virtual void finals(const uint16_t regs[14]) = 0;
    virtual void end_case() = 0;
};

// (a) The golden-comparator format.  Field order and radix are fixed by
// sw/check_core.py::parse_out (check_core.py:219) and match tb_v30_core.sv's
// `$fdisplay(fo, "r %0d %0d %0d %0d %05x %04x %01x %0d", ...)` exactly; the
// trailing BUSLOCK_N field is emitted for TB parity and ignored by parse_out.
class TextRowEmitter : public RowEmitter {
public:
    explicit TextRowEmitter(std::FILE* out) : out_(out) {}
    void begin_case(long idx) override;
    void row(const ClockRow& r) override;
    void finals(const uint16_t regs[14]) override;
    void end_case() override;

private:
    std::FILE* out_;
};

// (b) chip_rows NDJSON, one object per clock.  Keys match the record dicts
// sw/check_seq.py::run_image builds, plus `clk` and `upc` (the per-row micro-PC
// attribution the functional model already carries on every transaction).
class ChipRowsEmitter : public RowEmitter {
public:
    explicit ChipRowsEmitter(std::FILE* out) : out_(out) {}
    void begin_case(long idx) override;
    void row(const ClockRow& r) override;
    void finals(const uint16_t regs[14]) override;
    void end_case() override;

private:
    std::FILE* out_;
    long idx_ = 0;
};

}  // namespace sim

#endif  // ROWS_H
