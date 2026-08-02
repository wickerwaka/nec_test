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
    run_ = false;
    ci_ = 0;
    cmt_valid_ = false;
    cmt_t1_ = -1;
    last_addr_ = 0;
    last_data_ = 0;
    last_ps_ = 0;
    last_ube_ = 0;
    q_.clear();
    fetch_ptr_ = 0;
    cs_ = 0;
    suspended_ = false;
    pop_is_first_ = true;
    consumed_.clear();
    qs_pending_ = kQsNone;
    upc_pending_ = 0xFFFF;
    opc_valid_ = false;
    req_.clear();
    eu_pending_ = 0;
    eu_done_clk_ = -1;
}

void BiuTimed::end_case() {
    // Drain whatever the EU left posted so the last cycle's rows exist.
    int guard = 0;
    while ((run_ || cmt_valid_ || !req_.empty()) && ++guard < 64) tick();
}

int BiuTimed::occupancy() const {
    int n = int(q_.size());
    if (run_ && cur_.is_fetch) n += cur_.push_n;
    if (cmt_valid_ && cmt_.is_fetch) n += cmt_.push_n;
    return n;
}

// --- the clock --------------------------------------------------------------

void BiuTimed::tick() {
    long c = clk_;

    // A committed cycle opens its T1 on this clock.
    if (!run_ && cmt_valid_ && cmt_t1_ == c) {
        run_ = true;
        cur_ = cmt_;
        ci_ = 0;
        cmt_valid_ = false;
    }

    const bool display = cmt_valid_ && cmt_t1_ == c + 1;
    const int last_i = 3 + waits_;                  // index of T4
    const int passive_i = (waits_ == 0) ? 2 : (3 + waits_);

    ClockRow r;
    r.clk = c;
    r.qs = qs_pending_;
    r.upc = upc_pending_;
    qs_pending_ = kQsNone;
    upc_pending_ = 0xFFFF;

    if (run_) {
        r.tstate = (ci_ == 0)          ? uint8_t(kT1)
                   : (ci_ == 1)        ? uint8_t(kT2)
                   : (ci_ == 2)        ? uint8_t(kT3)
                   : (ci_ < last_i)    ? uint8_t(kTw)
                                       : uint8_t(kT4);
        r.bs = (ci_ >= passive_i) ? uint8_t(kBsPasv) : cur_.bs;
        r.ube_n = cur_.ube_n;
        if (ci_ == 0) {
            // The address-phase (mid-cycle) sample is the address; the
            // end-of-cycle sample is the address too, EXCEPT on a write, where
            // the CPU has already switched AD to the write data by the end of
            // T1 (MEASURED: 88 case 0 row 15).
            r.ad_addr = cur_.addr;
            r.ad_data = is_write(cur_.bs) ? cur_.data
                                          : uint16_t(cur_.addr & 0xFFFF);
            r.ps = uint8_t((cur_.addr >> 16) & 0xF);
        } else {
            r.ad_addr = cur_.addr;
            r.ad_data = cur_.data;
            r.ps = data_ps(cur_.segc);
        }
        if (r.upc == 0xFFFF) r.upc = cur_.upc;
    } else {
        r.tstate = kTi;
        r.bs = kBsPasv;
        r.ube_n = last_ube_;
        r.ad_addr = last_addr_;
        r.ad_data = last_data_;
        r.ps = last_ps_;
    }

    // M2: the registered status output.  The display clock carries the NEXT
    // cycle's status, address and UBE -- whatever T-state that clock happens
    // to be (a T4, or a plain idle clock after a gap).
    if (display) {
        r.bs = cmt_.bs;
        r.ad_addr = cmt_.addr;
        r.ad_data = uint16_t(cmt_.addr & 0xFFFF);
        r.ps = uint8_t((cmt_.addr >> 16) & 0xF);
        r.ube_n = cmt_.ube_n;
        if (r.upc == 0xFFFF) r.upc = cmt_.upc;
    }

    last_addr_ = r.ad_addr;
    last_data_ = r.ad_data;
    last_ps_ = r.ps;
    last_ube_ = r.ube_n;

    if (rows_) rows_->row(r);
    ++clk_;

    // --- end-of-clock: advance the cycle, then run the eval --------------
    bool eval_here = false;
    if (run_) {
        if (waits_ == 0 ? (ci_ == 2) : (ci_ == last_i)) eval_here = true;
        if (ci_ == last_i) {
            if (cur_.is_fetch) {
                // M3: the push lands at the end of T4 and the byte is
                // poppable two clocks later.
                for (int i = 0; i < cur_.push_n; ++i)
                    q_.push_back(QByte{cur_.push_b[i], c + 2});
            }
            if (!cur_.is_fetch) {
                // eu_done: the data handover / store retire lands one clock
                // after the completion eval (mission-H); at w0 that is T4 + 1.
                eu_done_clk_ = c + 1;
                if (eu_pending_) --eu_pending_;
            }
            run_ = false;
        } else {
            ++ci_;
        }
    } else if (!cmt_valid_) {
        eval_here = true;                 // end of an idle clock
    }
    if (eval_here && !cmt_valid_) eval();
}

// The completion eval: pick the next bus cycle.  The winner is DISPLAYED on
// the next clock and opens its T1 the clock after that (M1).
void BiuTimed::eval() {
    if (!req_.empty()) {
        cmt_ = req_.front();
        req_.pop_front();
        cmt_valid_ = true;
        cmt_t1_ = clk_ + 1;
        return;
    }
    if (suspended_) return;
    if (occupancy() > 4) return;
    cmt_ = make_fetch();
    // The fetch pointer advances when the cycle is COMMITTED, not when its
    // data lands: the address is latched into the bus cycle here.
    fetch_ptr_ = uint16_t(fetch_ptr_ + cmt_.push_n);
    cmt_valid_ = true;
    cmt_t1_ = clk_ + 1;
}

BiuTimed::Access BiuTimed::make_fetch() const {
    uint32_t a = phys(cs_, fetch_ptr_);
    Access acc;
    acc.bs = kBsCode;
    acc.addr = a;
    acc.ube_n = 0;
    acc.segc = seg_code(kCS);
    acc.upc = 0xFFFF;
    acc.is_fetch = true;
    if (a & 1) {
        uint8_t b = core_.peek(a);
        acc.data = uint16_t((uint16_t(b) << 8) | (last_data_ & 0x00FF));
        acc.push_n = 1;
        acc.push_b[0] = b;
    } else {
        uint8_t lo = core_.peek(a);
        uint8_t hi = core_.peek(phys(cs_, uint16_t(fetch_ptr_ + 1)));
        acc.data = uint16_t(lo | (uint16_t(hi) << 8));
        acc.push_n = 2;
        acc.push_b[0] = lo;
        acc.push_b[1] = hi;
    }
    return acc;
}

void BiuTimed::post(const Access& a) {
    // Backpressure: the EU cannot queue an unbounded number of accesses ahead
    // of the bus.  Two in flight (the two halves of a split word) is the most
    // the datapath can hold.
    int guard = 0;
    while (req_.size() >= 2 && ++guard < 4096) tick();
    req_.push_back(a);
    ++eu_pending_;
}

// --- prefetch queue ---------------------------------------------------------

void BiuTimed::queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr) {
    q_.clear();
    for (uint8_t b : q) q_.push_back(QByte{b, 0});
    fetch_ptr_ = fetch_ptr;
}

void BiuTimed::flush(uint16_t pc) {
    q_.clear();
    fetch_ptr_ = pc;
    suspended_ = false;
    pop_is_first_ = true;
    opc_valid_ = false;
    // A committed-but-not-started fetch is withdrawn; a fetch already in
    // flight completes and its data is discarded (biu_model.md flush law).
    if (cmt_valid_ && cmt_.is_fetch) { cmt_valid_ = false; }
    if (run_ && cur_.is_fetch) { cur_.push_n = 0; }
    qs_pending_ = kQsEmpty;
}

void BiuTimed::clear_consumed() {
    consumed_.clear();
    // No pre-popped opcode in the latch => the loader is about to pop the
    // first byte of an instruction itself, and that pop is an F.
    if (!opc_valid_) pop_is_first_ = true;
}

void BiuTimed::opcode_prefetch(uint16_t cs) {
    if (opc_valid_) return;
    // MAX-OF-TWO-DEADLINES.  The successor's opcode pop rides the E row's own
    // clock, but an instruction does not retire until its bus work is done:
    // the pop is the LATER of the E-row clock and eu_done of the last EU
    // access.  (Measured: 88 mod0 store -- the closing F lands on the MEMW's
    // T4+1, not on the E row.)
    wait_bus();
    cs_ = cs;
    pop_is_first_ = true;
    opc_byte_ = next_byte(cs, 0xFFFE);
    opc_valid_ = true;
}

uint8_t BiuTimed::next_byte(uint16_t cs, uint16_t upc) {
    cs_ = cs;
    if (opc_valid_) {
        opc_valid_ = false;
        uint8_t b = opc_byte_;
        consumed_.push_back(b);
        return b;
    }
    int guard = 0;
    while ((q_.empty() || q_.front().ready > clk_) && ++guard < 4096) tick();
    if (q_.empty()) return 0x90;
    uint8_t b = q_.front().b;
    q_.pop_front();
    consumed_.push_back(b);
    qs_pending_ = pop_is_first_ ? kQsFirst : kQsSubseq;
    upc_pending_ = upc;
    pop_is_first_ = false;
    return b;
}

void BiuTimed::wait_bus() {
    int guard = 0;
    while (eu_pending_ > 0 && ++guard < 4096) tick();
    while (clk_ < eu_done_clk_ && ++guard < 4096) tick();
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
        post(acc);
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        acc.data = lane_data(a1, false, uint16_t(v >> 8));
        post(acc);
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        acc.data = lane_data(a, word, v);
        post(acc);
    }
    eu_done_clk_ = -1;
    return v;
}

// M5 WRITE DATA IS THE WHOLE 16-BIT DATAPATH VALUE.  On a WRITE the CPU drives
// AD15-0 with its internal 16-bit value and lets UBE/A0 pick the lane(s) the
// memory latches -- it does NOT compose a per-lane value.  So both halves of a
// SPLIT (unaligned) word write show the same full word, and a byte write shows
// the whole internal register/immediate.  MEASURED: `50` (PUSH AX at an odd SP)
// drives 0BCD on both byte cycles; measurements.md's "byte-store data lane law"
// (sign-extended imm8 for C6, the sibling register byte for 88) is the same
// fact seen from the source side.  Only READS retain on the undriven lane
// (see lane_data / §2.6) -- there the CPU floats AD and the system drives.
void BiuTimed::mem_write(uint16_t seg_val, uint16_t off, uint16_t data,
                         bool word, uint8_t seg_idx, uint16_t upc) {
    core_.mem_write(seg_val, off, data, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    Access acc;
    acc.bs = kBsMemW;
    acc.segc = seg_code(seg_idx);
    acc.upc = upc;
    acc.data = data;
    if (word && (a & 1)) {
        acc.addr = a;
        acc.ube_n = 0;
        post(acc);
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        post(acc);
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        post(acc);
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
    post(acc);
    eu_done_clk_ = -1;
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
    acc.data = data;   // M5: a write drives the whole datapath value
    post(acc);
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
    post(acc);
    eu_done_clk_ = -1;
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
    post(acc);
}

}  // namespace sim
