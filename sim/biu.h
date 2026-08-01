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
    enum Kind : uint8_t { kCodeFetch, kMemRead, kMemWrite, kIoRead, kIoWrite };
    uint32_t seq = 0;
    Kind kind = kCodeFetch;
    uint32_t addr20 = 0;
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
    void io_write(uint16_t port, uint16_t data, bool word, uint16_t upc);

    // --- prefetch queue ---------------------------------------------------
    void queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr);
    // Pops one instruction byte, refilling from CS:fetch_ptr when empty.
    uint8_t next_byte(uint16_t cs, uint16_t upc);
    void flush(uint16_t pc);  // clear queue, refetch from CS:pc
    void susp() { suspended_ = true; }
    void resume() { suspended_ = false; }
    size_t queue_len() const { return q_.size() - qhead_; }
    uint8_t queue_at(size_t i) const { return q_[qhead_ + i]; }
    uint16_t fetch_ptr() const { return fetch_ptr_; }

    const std::vector<Txn>& txns() const { return txns_; }
    void clear_txns() { txns_.clear(); seq_ = 0; }

    // Ordered byte-granular data writes (memory only), for RAM-diff checking.
    const std::vector<std::pair<uint32_t, uint8_t>>& writes() const {
        return writes_;
    }

    static constexpr uint8_t kFill = 0x00;

private:
    uint8_t rd(uint32_t a) const {
        return stamp_[a] == epoch_ ? mem_[a] : kFill;
    }
    void wr(uint32_t a, uint8_t v) {
        mem_[a] = v;
        stamp_[a] = epoch_;
    }
    void log(Txn::Kind k, uint32_t a, uint16_t d, uint8_t w, uint8_t s,
             uint16_t upc);

    std::vector<uint8_t> mem_;
    std::vector<uint32_t> stamp_;
    uint32_t epoch_ = 0;

    std::vector<uint8_t> q_;
    size_t qhead_ = 0;
    uint16_t fetch_ptr_ = 0;
    uint16_t cs_ = 0;
    bool suspended_ = false;

    std::vector<Txn> txns_;
    uint32_t seq_ = 0;
    std::vector<std::pair<uint32_t, uint8_t>> writes_;
};

}  // namespace sim

#endif  // BIU_H
