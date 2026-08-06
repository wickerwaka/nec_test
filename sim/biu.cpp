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
    consumed_.clear();
    io_seq_.clear();
    io_n_ = 0;
    ev_ = 0;
}

void Biu::poke(uint32_t a, uint8_t v) { wr(a & 0xFFFFF, v); }
uint8_t Biu::peek(uint32_t a) const { return rd(a & 0xFFFFF); }

void Biu::log(Txn::Kind k, uint32_t a, uint32_t a2, uint16_t d, uint8_t w,
              uint8_t s, uint16_t upc) {
    Txn t;
    t.seq = seq_++;
    t.kind = k;
    t.addr20 = a;
    t.addr2 = a2;
    t.data = d;
    t.width = w;
    t.seg = s;
    t.upc = upc;
    txns_.push_back(t);
    if (k != Txn::kCodeFetch) ev_ += (w == 2 && (a & 1)) ? 2 : 1;
}

void Biu::note_halt(uint16_t upc) { log(Txn::kHalt, 0, 0, 0, 1, 0, upc); }

uint16_t Biu::mem_read(uint16_t seg_val, uint16_t off, bool word,
                       uint8_t seg_idx, uint16_t upc) {
    uint32_t a = phys(seg_val, off);
    uint32_t a1 = phys(seg_val, uint16_t(off + 1));
    note_access(off, word);
    uint16_t v = rd(a);
    if (word) {
        // The offset wraps inside the segment (16-bit adder), so a word at
        // offset FFFF takes its high byte from offset 0000.
        v = uint16_t(v | (uint16_t(rd(a1)) << 8));
    }
    log(Txn::kMemRead, a, a1, v, word ? 2 : 1, seg_idx, upc);
    // THE DATA-PATH BYTE SWAPPER (read half).  The 16-bit system presents the
    // whole ALIGNED WORD and the CPU routes the addressed byte to the low half
    // of its datapath, carrying the COMPANION byte along in the high half --
    // the read-side mirror of the write swapper, and the same "the datapath is
    // 16 bits wide always" law the ALU already obeys.  Byte-width consumers
    // mask it off, so nothing architectural changes; what it explains is the
    // companion byte a byte RMW puts back on the bus (measured: `10` case 0,
    // `adc byte [odd], dh` drives EC90 where 90 is the aligned partner).
    if (!word) v = uint16_t(v | (uint16_t(rd(a ^ 1u)) << 8));
    return v;
}

void Biu::mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word,
                    uint8_t seg_idx, uint16_t upc, bool) {
    uint32_t a = phys(seg_val, off);
    uint32_t a1 = phys(seg_val, uint16_t(off + 1));
    note_access(off, word);
    wr(a, uint8_t(data & 0xFF));
    writes_.emplace_back(a, uint8_t(data & 0xFF));
    if (word) {
        wr(a1, uint8_t(data >> 8));
        writes_.emplace_back(a1, uint8_t(data >> 8));
    }
    log(Txn::kMemWrite, a, a1, data, word ? 2 : 1, seg_idx, upc);
}

uint16_t Biu::io_read(uint16_t port, bool word, uint16_t upc) {
    // No I/O model: the byte lane follows the port's parity, exactly as the
    // 8086-style bus multiplexes AD15-8 for odd addresses.
    // The suite serves the same 16-bit word on every cycle of the access; the
    // byte lane follows the address parity (AD15-8 for odd), so a word access
    // to an ODD port -- which the bus splits into two byte cycles -- comes
    // back byte-swapped.
    uint16_t src = io_in_;
    if (io_n_ < io_seq_.size()) src = io_seq_[io_n_];
    ++io_n_;
    // ONE expression for both widths, and it is the same A0 BYTE SWAPPER the
    // memory path uses: the port presents its 16-bit word on both lanes and
    // the CPU rotates the addressed byte into the low half of its datapath,
    // carrying the companion along.  A byte consumer masks it off.
    uint16_t v = (port & 1) ? uint16_t((src >> 8) | (src << 8)) : src;
    log(Txn::kIoRead, port, uint16_t(port + 1), word ? v : uint16_t(v & 0xFF),
        word ? 2 : 1, 0, upc);
    return v;
}

uint16_t Biu::inta_read(uint16_t upc) {
    log(Txn::kIntAck, 0, 0, inta_, 2, 0, upc);
    return inta_;
}

void Biu::io_write(uint16_t port, uint16_t data, bool word, uint16_t upc) {
    log(Txn::kIoWrite, port, uint16_t(port + 1), data, word ? 2 : 1, 0, upc);
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
        log(Txn::kCodeFetch, a, a, b, 1, /*CS=*/1, upc);
        if (fetch_ptr_ == 0xFFFF) ++code_wrap_;
        fetch_ptr_ = uint16_t(fetch_ptr_ + 1);
        q_.push_back(b);
    }
    uint8_t b = q_[qhead_++];
    consumed_.push_back(b);
    return b;
}

void Biu::flush_pc(uint16_t pc) {
    q_.clear();
    qhead_ = 0;
    fetch_ptr_ = pc;
    suspended_ = false;
}

}  // namespace sim
