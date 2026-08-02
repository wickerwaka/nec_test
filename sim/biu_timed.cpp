// biu_timed.cpp -- see biu_timed.h.

#include "biu_timed.h"

#include "state.h"

namespace sim {

uint8_t BiuTimed::seg_code(uint8_t seg_idx) {
    switch (seg_idx) {
        case kES: return 0;
        case kSS: return 1;
        case kCS: return 2;
        case kDS: return 3;
        default: return 2;  // kSegZero: "no segment", same code as CS
    }
}

uint8_t BiuTimed::data_ps(uint8_t segc) const {
    // S6 = 0 (always, for a CPU-driven cycle), S5 = IE, S4:S3 = segment.
    bool ie = psw_ && (*psw_ & kFlagIE);
    return uint8_t((ie ? 4 : 0) | (segc & 3));
}

uint16_t BiuTimed::lane_data(uint32_t addr, bool word, uint16_t value) const {
    if (word && !(addr & 1)) return value;             // both lanes driven
    if (addr & 1)                                      // high lane only
        return uint16_t(((value & 0xFF) << 8) | (last_data_ & 0x00FF));
    return uint16_t((last_data_ & 0xFF00) | (value & 0xFF));  // low lane only
}

void BiuTimed::begin_case() {
    core_.begin_case();
    core_.clear_wrap();
    clk_ = 0;
    held_valid_ = false;
    held_ = ClockRow{};
    last_addr_ = 0;
    last_data_ = 0;
    last_ps_ = 0;
    q_.clear();
    fetch_ptr_ = 0;
    cs_ = 0;
    suspended_ = false;
    pop_is_first_ = true;
    consumed_.clear();
}

void BiuTimed::end_case() {
    if (held_valid_ && rows_) rows_->row(held_);
    held_valid_ = false;
}

// Law L1: the row for clock N is released only once clock N+1 exists, so a
// cycle that commits on clock N+1 can still write its status and address into
// clock N -- which is exactly what a registered status output does.
void BiuTimed::emit(ClockRow r) {
    if (held_valid_ && rows_) rows_->row(held_);
    held_ = r;
    held_valid_ = true;
}

void BiuTimed::tick(uint8_t qs, uint16_t upc) {
    ClockRow r;
    r.clk = clk_++;
    r.tstate = kTi;
    r.bs = kBsPasv;
    r.qs = qs;
    r.ube_n = 1;
    r.ad_addr = last_addr_;
    r.ad_data = last_data_;
    r.ps = last_ps_;
    r.upc = upc;
    emit(r);
}

void BiuTimed::run_cycle(const Access& a) {
    // L1: hand the upcoming cycle's status and address to the clock that is
    // still in the delay buffer.
    if (held_valid_) {
        held_.bs = a.bs;
        held_.ad_addr = a.addr;
        held_.ad_data = uint16_t(a.addr & 0xFFFF);
        held_.ps = uint8_t((a.addr >> 16) & 0xF);
    }

    // L2: the cycle-relative clock index at which BS drops to passive.
    const int passive_at = (waits_ == 0) ? 2 : (3 + waits_);
    const uint8_t ps_data = data_ps(a.segc);

    ClockRow r;
    r.ube_n = a.ube_n;
    r.upc = a.upc;
    int idx = 0;
    for (int phase = 0; phase < 4 + waits_; ++phase) {
        // T1, T2, T3, Tw x waits_, T4
        uint8_t ts;
        if (phase == 0) ts = kT1;
        else if (phase == 1) ts = kT2;
        else if (phase == 2) ts = kT3;
        else if (phase < 3 + waits_) ts = kTw;
        else ts = kT4;

        r.clk = clk_++;
        r.tstate = ts;
        r.bs = (idx >= passive_at) ? uint8_t(kBsPasv) : a.bs;
        r.qs = kQsNone;
        if (ts == kT1) {
            // The address-phase (mid-cycle) sample is the address; the
            // end-of-cycle sample is the address too, EXCEPT on a write, where
            // the CPU has already switched AD to the write data by the end of
            // T1 (MEASURED: 88 case 0 row 15).
            r.ad_addr = a.addr;
            r.ad_data = is_write(a.bs) ? a.data : uint16_t(a.addr & 0xFFFF);
            r.ps = uint8_t((a.addr >> 16) & 0xF);
        } else {
            r.ad_addr = a.addr;
            r.ad_data = a.data;
            r.ps = ps_data;
        }
        last_addr_ = r.ad_addr;
        last_data_ = r.ad_data;
        last_ps_ = r.ps;
        emit(r);
        ++idx;
    }
}

// --- prefetch queue ---------------------------------------------------------

void BiuTimed::queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr) {
    q_.assign(q.begin(), q.end());
    fetch_ptr_ = fetch_ptr;
}

void BiuTimed::flush(uint16_t pc) {
    q_.clear();
    fetch_ptr_ = pc;
    suspended_ = false;
    pop_is_first_ = true;
    tick(kQsEmpty, 0xFFFF);
}

void BiuTimed::clear_consumed() {
    consumed_.clear();
    pop_is_first_ = true;
}

// SCAFFOLDING: demand fill.  A real V30 fetches ahead on a scheduler; here the
// queue is filled only when the decoder asks for a byte it does not have, which
// is what the functional Biu does.  The fetch WIDTH and alignment are already
// modelled properly (word from an even address; a single byte when the fetch
// pointer is odd, which is the state a flush to an odd PC leaves behind), since
// those decide the pin-level shape of the cycle.
void BiuTimed::do_fetch(uint16_t upc) {
    uint32_t a = phys(cs_, fetch_ptr_);
    Access acc;
    acc.bs = kBsCode;
    acc.addr = a;
    acc.ube_n = 0;
    acc.segc = seg_code(kCS);
    acc.upc = upc;
    if (a & 1) {
        uint8_t b = core_.peek(a);
        acc.data = lane_data(a, false, b);
        run_cycle(acc);
        q_.push_back(b);
        fetch_ptr_ = uint16_t(fetch_ptr_ + 1);
    } else {
        uint8_t lo = core_.peek(a);
        uint8_t hi = core_.peek(phys(cs_, uint16_t(fetch_ptr_ + 1)));
        acc.data = uint16_t(lo | (uint16_t(hi) << 8));
        run_cycle(acc);
        q_.push_back(lo);
        q_.push_back(hi);
        fetch_ptr_ = uint16_t(fetch_ptr_ + 2);
    }
}

uint8_t BiuTimed::next_byte(uint16_t cs, uint16_t upc) {
    cs_ = cs;
    if (q_.empty()) do_fetch(upc);
    uint8_t b = q_.front();
    q_.pop_front();
    consumed_.push_back(b);
    tick(pop_is_first_ ? kQsFirst : kQsSubseq, upc);
    pop_is_first_ = false;
    return b;
}

// --- data accesses ----------------------------------------------------------

uint16_t BiuTimed::mem_read(uint16_t seg_val, uint16_t off, bool word,
                            uint8_t seg_idx, uint16_t upc) {
    uint16_t v = core_.mem_read(seg_val, off, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    Access acc;
    acc.bs = kBsMemR;
    acc.segc = seg_code(seg_idx);
    acc.upc = upc;
    if (word && (a & 1)) {
        // The 16-bit bus splits an unaligned word into two byte cycles.
        acc.addr = a;
        acc.ube_n = 0;
        acc.data = lane_data(a, false, uint16_t(v & 0xFF));
        run_cycle(acc);
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        acc.data = lane_data(a1, false, uint16_t(v >> 8));
        run_cycle(acc);
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        acc.data = lane_data(a, word, v);
        run_cycle(acc);
    }
    return v;
}

void BiuTimed::mem_write(uint16_t seg_val, uint16_t off, uint16_t data,
                         bool word, uint8_t seg_idx, uint16_t upc) {
    core_.mem_write(seg_val, off, data, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    Access acc;
    acc.bs = kBsMemW;
    acc.segc = seg_code(seg_idx);
    acc.upc = upc;
    if (word && (a & 1)) {
        acc.addr = a;
        acc.ube_n = 0;
        acc.data = lane_data(a, false, uint16_t(data & 0xFF));
        run_cycle(acc);
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        acc.data = lane_data(a1, false, uint16_t(data >> 8));
        run_cycle(acc);
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        acc.data = lane_data(a, word, data);
        run_cycle(acc);
    }
}

uint16_t BiuTimed::io_read(uint16_t port, bool word, uint16_t upc) {
    uint16_t v = core_.io_read(port, word, upc);
    Access acc;
    acc.bs = kBsIoR;
    acc.addr = port;
    acc.segc = 2;  // I/O drives the "no segment" code (MEASURED, E4 case 0)
    acc.upc = upc;
    acc.ube_n = uint8_t((word || (port & 1)) ? 0 : 1);
    acc.data = lane_data(port, word, v);
    run_cycle(acc);
    return v;
}

void BiuTimed::io_write(uint16_t port, uint16_t data, bool word, uint16_t upc) {
    core_.io_write(port, data, word, upc);
    Access acc;
    acc.bs = kBsIoW;
    acc.addr = port;
    acc.segc = 2;
    acc.upc = upc;
    acc.ube_n = uint8_t((word || (port & 1)) ? 0 : 1);
    acc.data = lane_data(port, word, data);
    run_cycle(acc);
}

uint16_t BiuTimed::inta_read(uint16_t upc) {
    uint16_t v = core_.inta_read(upc);
    Access acc;
    acc.bs = kBsInta;
    acc.addr = 0;
    acc.ube_n = 0;
    acc.segc = 2;
    acc.data = v;
    acc.upc = upc;
    run_cycle(acc);
    return v;
}

void BiuTimed::note_halt(uint16_t upc) {
    core_.note_halt(upc);
    Access acc;
    acc.bs = kBsHalt;
    acc.addr = last_addr_;
    acc.ube_n = 1;
    acc.segc = 2;
    acc.data = last_data_;
    acc.upc = upc;
    run_cycle(acc);
}

}  // namespace sim
