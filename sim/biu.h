// biu.h -- functional bus-interface unit: 1MB memory, 64K IO, prefetch queue,
// ordered transaction log.  Timing is NOT modelled; every access completes
// instantly.  The interlock call sites (F / Q waits) live in exec.cpp and are
// preserved for the future cycle-accurate mode.

#ifndef BIU_H
#define BIU_H

#include <cstdint>
#include <utility>
#include <vector>

namespace sim {

struct Txn {
    enum Kind : uint8_t {
        kCodeFetch, kMemRead, kMemWrite, kIoRead, kIoWrite, kIntAck, kHalt };
    uint32_t seq = 0;
    Kind kind = kCodeFetch;
    uint32_t addr20 = 0;
    // The address the SECOND byte cycle of a word access carries.  It is
    // `addr20 + 1` except at a segment-offset wrap, where the 16-bit adder
    // sends it back to the base of the segment (ledger A12) -- which is why it
    // is recorded here and not recomputed by the driver.
    uint32_t addr2 = 0;
    uint16_t data = 0;
    uint8_t width = 1;  // bytes
    uint8_t seg = 0;    // segment register index used to form addr20
    uint16_t upc = 0;   // ROM row that issued it (0xFFFF = pre-decode hardware)
};

class Biu {
public:
    Biu();

    // Per-case reset.  Memory is epoch-stamped, so this is O(1): every cell
    // whose stamp != the current epoch reads as kFill.
    void begin_case();

    void poke(uint32_t addr20, uint8_t v);
    uint8_t peek(uint32_t addr20) const;

    // --- data accesses ----------------------------------------------------
    uint16_t mem_read(uint16_t seg_val, uint16_t off, bool word, uint8_t seg_idx,
                      uint16_t upc);
    void mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word,
                   uint8_t seg_idx, uint16_t upc);
    uint16_t io_read(uint16_t port, bool word, uint16_t upc);
    // The suite records the value the port presented (case name `iord=XXXX`);
    // there is no I/O model, so it is replayed verbatim.  `set_io_seq` is the
    // ordered per-IOR form (the `iords` case field, INS / REP INS / LOCK
    // string-I/O): value k serves the k-th port read, the scalar serves the
    // rest.
    void set_io_in(uint16_t v) { io_in_ = v; }
    void set_io_seq(const std::vector<uint16_t>& s) { io_seq_ = s; io_n_ = 0; }
    void io_write(uint16_t port, uint16_t data, bool word, uint16_t upc);

    // --- interrupt acknowledge -------------------------------------------
    // Ext [-05-]: the INTA bus cycle.  There is no interrupt-controller model,
    // so the acknowledge data is the harness constant (CFG int_vector, 0xFF on
    // the low lane / 0x00 on the high lane -- exactly what the golden traces
    // show riding both INTA cycles).  Same replay policy as `iord`.
    void set_inta(uint16_t v) { inta_ = v; }
    uint16_t inta_read(uint16_t upc);

    // The HALT acknowledge status cycle.  It carries no data and no address;
    // it is logged so the ordered bus stream a multi-instruction replay
    // compares against a capture keeps its position marker (fuzz_classify's
    // `func_stream` emits a bare ("HALT",) for it).
    void note_halt(uint16_t upc);

    // Number of BUS CYCLES the ordered functional stream has emitted so far:
    // every non-CODE transaction counts 1, and an unaligned word access counts
    // 2 because the 16-bit bus splits it.  This is the coordinate the
    // interrupt-boundary replay is expressed in (see image_runner.cpp).
    long ev_count() const { return ev_; }

    // The functional bus has no clock; -1 so the shared interpreter's
    // env-gated ROW TRACE (exec_impl.h, V30SIM_ROWTRACE) compiles on both
    // bus policies.  A diagnostic only -- nothing reads it for behaviour.
    long clock() const { return -1; }

    // --- prefetch queue ---------------------------------------------------
    void queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr);
    // Pops one instruction byte, refilling from CS:fetch_ptr when empty.
    uint8_t next_byte(uint16_t cs, uint16_t upc);
    uint8_t decode_byte(uint16_t cs, uint16_t upc) { return next_byte(cs, upc); }
    // The displacement-completing byte (M8's `pen`); no timing in this mode.
    uint8_t disp_byte(uint16_t cs, uint16_t upc) { return next_byte(cs, upc); }
    void flush(uint16_t, uint16_t pc) { flush_pc(pc); }
    void flush_pc(uint16_t pc);  // clear queue, refetch from CS:pc
    void susp() { suspended_ = true; }
    void resume() { suspended_ = false; }
    size_t queue_len() const { return q_.size() - qhead_; }
    uint8_t queue_at(size_t i) const { return q_[qhead_ + i]; }
    uint16_t fetch_ptr() const { return fetch_ptr_; }

    // Instruction bytes handed to the decoder since the last clear.  The final
    // QUEUE comparison is deferred (no timing model), so the checker asserts
    // instead that the bytes the sim consumed are the case's `bytes`.
    const std::vector<uint8_t>& consumed() const { return consumed_; }
    void clear_consumed() { consumed_.clear(); }

    // --- the TIMED extensions to the Bus concept --------------------------
    // The functional model has no clock, so every one of these is a no-op.
    // They exist so `CpuT<Bus>` / `loader_decode<Bus>` can carry the cadence
    // call sites in ONE body shared by both instantiations.
    void charge(int) {}
    void wait_read() {}
    void wait_opr_free() {}
    void wait_opr() {}
    void write_request(uint16_t, uint16_t, bool, uint8_t, bool, uint16_t) {}
    void opcode_prefetch(uint16_t) {}
    bool opcode_pending() const { return false; }
    void prefix_retire() {}
    void wait_retire_lead() {}

    const std::vector<Txn>& txns() const { return txns_; }
    void clear_txns() { txns_.clear(); seq_ = 0; }

    // Ordered byte-granular data writes (memory only), for RAM-diff checking.
    const std::vector<std::pair<uint32_t, uint8_t>>& writes() const {
        return writes_;
    }

    // 64K-mirrored RAM, as the capture board is actually wired.  A golden whose
    // memory footprint holds two distinct 20-bit addresses aliasing to the same
    // 16-bit cell is only valid under this model; the checker retries a flat
    // failure here rather than editing the golden (check_core's `+mirror`).
    // Transaction addresses stay 20-bit -- only the storage aliases.
    void set_mirror(bool on) { mirror_ = on; }

    // --- A12 boundary instrumentation (ledger A12: word memory accesses wrap
    // the OFFSET at 16 bits inside the segment).  `near_wrap` counts DATA
    // accesses whose offset lands in the last four bytes of the segment
    // (0xFFFC..0xFFFF) -- the region where a word access either wraps or sits
    // one byte short of wrapping; `wrapped` counts the accesses that actually
    // took their second byte from offset 0x0000; `code_wrap` is the same for
    // instruction fetch (CS:PC rolling over).  Used to EXTRACT the boundary
    // subset out of a suite that has no dedicated boundary tranche.
    void clear_wrap() { near_wrap_ = wrapped_ = code_wrap_ = 0; }
    int near_wrap() const { return near_wrap_; }
    int wrapped() const { return wrapped_; }
    int code_wrap() const { return code_wrap_; }

    static constexpr uint8_t kFill = 0x00;
    // The TEST RIG fills unwritten memory with NOPs (tests/v30/v0.1/README
    // "0x90 fill"), and the timed model is compared against that rig's PINS
    // -- a prefetch or a read that lands outside the case's poked bytes
    // shows 0x90 there.  Settable so the FUNCTIONAL model keeps its 0x00
    // default and stays byte-identical.
    void set_fill(uint8_t v) { fill_ = v; }

private:
    void note_access(uint16_t off, bool word) {
        if (off >= 0xFFFC) ++near_wrap_;
        if (word && off == 0xFFFF) ++wrapped_;
    }

    uint32_t cell(uint32_t a) const { return mirror_ ? (a & 0xFFFF) : a; }
    uint8_t rd(uint32_t a0) const {
        uint32_t a = cell(a0);
        return stamp_[a] == epoch_ ? mem_[a] : fill_;
    }
    void wr(uint32_t a0, uint8_t v) {
        uint32_t a = cell(a0);
        mem_[a] = v;
        stamp_[a] = epoch_;
    }
    void log(Txn::Kind k, uint32_t a, uint32_t a2, uint16_t d, uint8_t w,
             uint8_t s, uint16_t upc);

    std::vector<uint8_t> mem_;
    std::vector<uint32_t> stamp_;
    uint32_t epoch_ = 0;
    uint8_t fill_ = kFill;
    bool mirror_ = false;

    std::vector<uint8_t> q_;
    size_t qhead_ = 0;
    uint16_t fetch_ptr_ = 0;
    uint16_t cs_ = 0;
    bool suspended_ = false;

    std::vector<Txn> txns_;
    uint16_t io_in_ = 0;
    std::vector<uint16_t> io_seq_;
    size_t io_n_ = 0;
    uint16_t inta_ = 0x00FF;
    uint32_t seq_ = 0;
    std::vector<std::pair<uint32_t, uint8_t>> writes_;
    std::vector<uint8_t> consumed_;
    int near_wrap_ = 0;
    int wrapped_ = 0;
    int code_wrap_ = 0;
    long ev_ = 0;
};

}  // namespace sim

#endif  // BIU_H
