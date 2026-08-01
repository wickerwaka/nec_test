// biu.cpp -- see biu.h.

#include "biu.h"

namespace sim {

namespace {
inline uint32_t phys(uint16_t seg_val, uint16_t off) {
    return uint32_t((uint32_t(seg_val) << 4) + off) & 0xFFFFFu;
}
}  // namespace

Biu::Biu() : mem_(1u << 20, 0), stamp_(1u << 20, 0) {}

void Biu::begin_case() {
    ++epoch_;
    q_.clear();
    qhead_ = 0;
    fetch_ptr_ = 0;
    suspended_ = false;
    txns_.clear();
    seq_ = 0;
    writes_.clear();
}

void Biu::poke(uint32_t a, uint8_t v) { wr(a & 0xFFFFF, v); }
uint8_t Biu::peek(uint32_t a) const { return rd(a & 0xFFFFF); }

void Biu::log(Txn::Kind k, uint32_t a, uint16_t d, uint8_t w, uint8_t s,
              uint16_t upc) {
    Txn t;
    t.seq = seq_++;
    t.kind = k;
    t.addr20 = a;
    t.data = d;
    t.width = w;
    t.seg = s;
    t.upc = upc;
    txns_.push_back(t);
}

uint16_t Biu::mem_read(uint16_t seg_val, uint16_t off, bool word,
                       uint8_t seg_idx, uint16_t upc) {
    uint32_t a = phys(seg_val, off);
    uint16_t v = rd(a);
    if (word) {
        // The offset wraps inside the segment (16-bit adder), so a word at
        // offset FFFF takes its high byte from offset 0000.
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        v = uint16_t(v | (uint16_t(rd(a1)) << 8));
    }
    log(Txn::kMemRead, a, v, word ? 2 : 1, seg_idx, upc);
    return v;
}

void Biu::mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word,
                    uint8_t seg_idx, uint16_t upc) {
    uint32_t a = phys(seg_val, off);
    wr(a, uint8_t(data & 0xFF));
    writes_.emplace_back(a, uint8_t(data & 0xFF));
    if (word) {
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        wr(a1, uint8_t(data >> 8));
        writes_.emplace_back(a1, uint8_t(data >> 8));
    }
    log(Txn::kMemWrite, a, data, word ? 2 : 1, seg_idx, upc);
}

uint16_t Biu::io_read(uint16_t port, bool word, uint16_t upc) {
    // Unbacked IO space: reads return the fill pattern.  Real port data is
    // supplied by the case runner for IN forms (out of S1a scope).
    uint16_t v = word ? 0xFFFF : 0x00FF;
    v = 0;
    log(Txn::kIoRead, port, v, word ? 2 : 1, 0, upc);
    return v;
}

void Biu::io_write(uint16_t port, uint16_t data, bool word, uint16_t upc) {
    log(Txn::kIoWrite, port, data, word ? 2 : 1, 0, upc);
}

void Biu::queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr) {
    q_ = q;
    qhead_ = 0;
    fetch_ptr_ = fetch_ptr;
}

uint8_t Biu::next_byte(uint16_t cs, uint16_t upc) {
    cs_ = cs;
    if (qhead_ >= q_.size()) {
        uint32_t a = phys(cs_, fetch_ptr_);
        uint8_t b = rd(a);
        log(Txn::kCodeFetch, a, b, 1, /*CS=*/1, upc);
        fetch_ptr_ = uint16_t(fetch_ptr_ + 1);
        q_.push_back(b);
    }
    return q_[qhead_++];
}

void Biu::flush(uint16_t pc) {
    q_.clear();
    qhead_ = 0;
    fetch_ptr_ = pc;
    suspended_ = false;
}

}  // namespace sim
