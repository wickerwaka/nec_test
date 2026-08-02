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

uint16_t BiuTimed::lane_data(uint16_t retained, uint32_t addr, bool word,
                             uint16_t value) {
    if (word && !(addr & 1)) return value;             // both lanes driven
    if (addr & 1)                                      // high lane only
        return uint16_t(((value & 0xFF) << 8) | (retained & 0x00FF));
    return uint16_t((retained & 0xFF00) | (value & 0xFF));  // low lane only
}

// The 16-bit system always presents the ALIGNED WORD on a read.
uint16_t BiuTimed::sys_word_at(uint32_t addr) const {
    uint32_t a = addr & ~1u;
    return uint16_t(core_.peek(a) | (uint16_t(core_.peek(a | 1u)) << 8));
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
    last_dp_ = 0;
    q_.clear();
    fetch_ptr_ = 0;
    cs_ = 0;
    suspended_ = false;
    pop_is_first_ = true;
    consumed_.clear();
    qs_pending_ = kQsNone;
    upc_pending_ = 0xFFFF;
    opc_valid_ = false;
    flush_eval_ = false;
    e_pend_ = false;
    e_from_ = 0;
    e_x_ = -1;
    push_absorb_clk_ = -2;
    req_.clear();
    eu_pending_ = 0;
    rd_pending_ = 0;
    wr_pending_ = 0;
    wres_ = 0;
    wr_done_clk_ = -1;
    rd_done_q_.clear();
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
    // The data phase opens on T2.
    if (run_ && ci_ == 1 && cur_.sys_word)
        cur_.data = sys_word_at(cur_.addr);

    const bool display = cmt_valid_ && cmt_t1_ == c + 1;
    const int last_i = 3 + waits_;                  // index of T4
    const int passive_i = (waits_ == 0) ? 2 : (3 + waits_);

    ClockRow r;
    r.clk = c;
    r.qs = qs_pending_;
    r.upc = upc_pending_;
    qs_pending_ = kQsNone;
    upc_pending_ = 0xFFFF;

    // F1: the parked flush takes the QS port on the first free clock.
    // (c): a ready-but-not-yet-started EU request owns the next slot, and the
    // flush display waits for that request's STATUS clock -- except on the
    // flush clock itself (biu_model.md: the divide trap raises flush and the
    // PC push together and still shows E at once).
    if (e_pend_ && c >= e_from_ && r.qs == kQsNone && c != push_absorb_clk_ &&
        (req_.empty() || c == e_x_) &&
        !(run_ && cur_.is_fetch && ci_ < last_i)) {
        r.qs = kQsEmpty;
        e_pend_ = false;
    }

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
        // ...but UBE is NOT part of that register.  It changes at T1, one
        // clock after the status and address do.  MEASURED: `E8` case 0 golden
        // rows 14-15 (the split push's second half is displayed with the first
        // half's UBE and only asserts its own at T1) and rows 18-19 (the
        // redirect fetch is displayed with the write's UBE).  Every CODE cycle
        // drives UBE low, which is why this is invisible until an EU access
        // sits next to a fetch.
        if (r.upc == 0xFFFF) r.upc = cmt_.upc;
    }

    last_addr_ = r.ad_addr;
    last_data_ = r.ad_data;
    // The retained lane tracks the DATA PHASE only -- never the address a
    // cycle drives during T1, and never the early status/address a display
    // clock carries.
    if (run_ && ci_ >= 1) last_dp_ = cur_.data;
    last_ps_ = r.ps;
    last_ube_ = r.ube_n;

    if (rows_) rows_->row(r);
    ++clk_;

    // --- end-of-clock: advance the cycle, then run the eval --------------
    bool eval_here = false;
    if (run_) {
        if (waits_ == 0 ? (ci_ == 2) : (ci_ == last_i)) eval_here = true;
        // F3: the flush-only point commits the REDIRECT PREFETCH only.  A
        // pending EU request still owns the first slot, and an EU access is
        // never granted at a T4 -- so with a request outstanding this point
        // simply does not fire and both wait for the next normal eval.
        if (ci_ == last_i && cur_.is_fetch && flush_eval_ && req_.empty())
            eval_here = true;
        if (ci_ == last_i) {
            if (cur_.is_fetch && cur_.push_n) {
                // M3: the push lands at the end of T4 and the byte is
                // poppable two clocks later.
                for (int i = 0; i < cur_.push_n; ++i)
                    q_.push_back(QByte{cur_.push_b[i], c + 2});
                push_absorb_clk_ = c + 1;   // F1(b): the queue port is busy
            }
            if (!cur_.is_fetch) {
                // eu_done: the data handover / store retire lands one clock
                // after the completion eval (mission-H); at w0 that is T4 + 1.
                if (eu_pending_) --eu_pending_;
                if (is_write(cur_.bs)) {
                    wr_done_clk_ = c + 1;
                    if (wr_pending_) --wr_pending_;
                }
                if (!is_write(cur_.bs) && cur_.rd_last) {
                    rd_done_q_.push_back(c + 1);
                    if (rd_pending_) --rd_pending_;
                }
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
    flush_eval_ = false;   // F3: the flush-only T4 point is spent by any commit
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
    cmt_prev_fp_ = fetch_ptr_;
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
    acc.sys_word = true;
    if (a & 1) {
        uint8_t b = core_.peek(a);
        acc.push_n = 1;
        acc.push_b[0] = b;
    } else {
        uint8_t lo = core_.peek(a);
        uint8_t hi = core_.peek(phys(cs_, uint16_t(fetch_ptr_ + 1)));
        acc.push_n = 2;
        acc.push_b[0] = lo;
        acc.push_b[1] = hi;
    }
    return acc;
}

// F2: withdraw a prefetch that is committed but has not been displayed yet.
void BiuTimed::withdraw_fetch() {
    // Only a commit that has not reached the status PINS yet can be taken
    // back: once its display clock has been emitted (cmt_t1_ == clk_, i.e. the
    // T1 opens on the clock about to run) the cycle is irrevocably announced.
    if (cmt_valid_ && cmt_.is_fetch && cmt_t1_ > clk_) {
        cmt_valid_ = false;
        fetch_ptr_ = cmt_prev_fp_;
    }
}

void BiuTimed::susp() {
    suspended_ = true;
    withdraw_fetch();   // F2 -- see biu_timed.h
}

void BiuTimed::post(const Access& a) {
    // F2 (generalised).  The EU's bus request reaches the BIU one clock ahead
    // of the micro-row that carries it -- the same one-row-early control decode
    // as SUSP -- so a prefetch the eval just chose is taken back before it
    // reaches the status pins.  This IS the measured "the reservation must LEAD
    // the request by one cycle" rule (biu_model.md, "Store-vs-prefetch
    // reservation law"), expressed as the decode pipeline rather than as a
    // per-form S_RSV table.
    withdraw_fetch();
    // Backpressure: the EU cannot queue an unbounded number of accesses ahead
    // of the bus.  Two in flight (the two halves of a split word) is the most
    // the datapath can hold.
    int guard = 0;
    while (req_.size() >= 2 && ++guard < 4096) tick();
    req_.push_back(a);
    ++eu_pending_;
    if (is_write(a.bs)) ++wr_pending_;
    else if (a.rd_last) ++rd_pending_;
}

// --- prefetch queue ---------------------------------------------------------

// PRE-WINDOW PRIMING (T0 open item 3, second half).  `begin_case` starts the
// bus idle, but the bus PINS are not blank: the fetches that filled the
// injected queue left their data phase standing on AD, and an odd-address
// single-byte fetch inside the window shows that stale byte on its undriven
// low lane (T0 2.6).  So replay the pre-window fetch ADDRESS sequence -- the
// same word/odd-byte rule the scheduler uses -- and leave the last one's data
// phase on the retained pins.  MEASURED: `EB` case 5, a jump to an odd target
// whose fetch shows `9090` (the pre-window NOP pair) and not `9000`.
void BiuTimed::queue_preload(const std::vector<uint8_t>& q, uint16_t cs,
                             uint16_t ip) {
    q_.clear();
    for (uint8_t b : q) q_.push_back(QByte{b, 0});
    cs_ = cs;
    fetch_ptr_ = uint16_t(ip + q.size());
    uint16_t p = ip;
    int need = int(q.size());
    while (need > 0) {
        uint32_t a = phys(cs, p);
        if (a & 1) {
            last_data_ = uint16_t((uint16_t(core_.peek(a)) << 8) |
                                  (last_data_ & 0x00FF));
            last_dp_ = last_data_;
            last_addr_ = a;
            p = uint16_t(p + 1);
            need -= 1;
        } else {
            last_data_ = uint16_t(core_.peek(a) |
                                  (uint16_t(core_.peek(phys(cs, uint16_t(p + 1))))
                                   << 8));
            last_dp_ = last_data_;
            last_addr_ = a;
            p = uint16_t(p + 2);
            need -= 2;
        }
    }
}

void BiuTimed::flush(uint16_t pc) {
    q_.clear();
    fetch_ptr_ = pc;
    suspended_ = false;
    pop_is_first_ = true;
    opc_valid_ = false;
    // A committed-but-not-started fetch is withdrawn; a fetch already in
    // flight completes and its data is discarded (biu_model.md flush law).
    withdraw_fetch();
    if (run_ && cur_.is_fetch) { cur_.push_n = 0; }
    // F1: the queue port is not free on the flush clock itself if a bus cycle
    // still owns it; from the next clock on it is free once that cycle has
    // reached its T4.
    flush_eval_ = true;
    e_pend_ = true;
    e_x_ = clk_;
    e_from_ = (run_ || (cmt_valid_ && cmt_t1_ == clk_)) ? clk_ + 1 : clk_;
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
    // The instruction-boundary pre-pop is the BOUNDARY requester, not the
    // decoder's byte pipeline: it is already synchronised to the E row and
    // takes its byte the moment the queue can give it up.
    opc_byte_ = pop(cs, 0xFFFE, false);
    opc_valid_ = true;
}

uint8_t BiuTimed::pop(uint16_t cs, uint16_t upc, bool penalise) {
    cs_ = cs;
    if (opc_valid_) {
        opc_valid_ = false;
        uint8_t b = opc_byte_;
        consumed_.push_back(b);
        return b;
    }
    // M3b THE QUEUE MISS COSTS TWO CLOCKS.  A demand that finds its byte
    // already poppable takes it on the demand clock itself.  A demand that
    // MISSES restarts the two-clock demand pipeline -- the same two clocks
    // that put micro-row 0 at opcode+2 and never at opcode+1 -- so the pop
    // lands at max(ready, demand + 2).  MEASURED on the queue-empty goldens,
    // where every byte's ready clock is its fetch's T4 + 2:
    //   8B  modrm  demand 1, ready 4 -> 4    (ready dominates)
    //   B8  imm-lo demand 2, ready 4 -> 4
    //   C6  disp16-lo demand 2, ready 4 -> 4,  disp16-hi demand 4 -> 6
    //   8A  disp8  demand 3, ready 4 -> 5    (the miss penalty dominates)
    //   04  imm8   demand 2, already there   -> 2
    int guard = 0;
    const long demand = clk_;
    const bool miss = q_.empty() || q_.front().ready > demand;
    while ((q_.empty() || q_.front().ready > clk_) && ++guard < 4096) tick();
    if (miss && penalise)
        while (clk_ < demand + 2 && ++guard < 4096) tick();
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
    while (wr_pending_ > 0 && ++guard < 4096) tick();
    while (clk_ < wr_done_clk_ && ++guard < 4096) tick();
}

// The F / OPR interlock: wait for the NEXT outstanding read, and consume it.
void BiuTimed::wait_next_read(int extra) {
    int guard = 0;
    while (rd_done_q_.empty() && rd_pending_ > 0 && ++guard < 4096) tick();
    if (rd_done_q_.empty()) return;
    long t = rd_done_q_.front() + extra;
    rd_done_q_.pop_front();
    while (clk_ < t && ++guard < 4096) tick();
}

void BiuTimed::wait_read() { wait_next_read(0); }
void BiuTimed::wait_opr() { wait_next_read(1); }

// --- data accesses ----------------------------------------------------------

uint16_t BiuTimed::mem_read(uint16_t seg_val, uint16_t off, bool word,
                            uint8_t seg_idx, uint16_t upc) {
    uint16_t v = core_.mem_read(seg_val, off, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    Access acc;
    acc.bs = kBsMemR;
    acc.segc = seg_code(seg_idx);
    acc.upc = upc;
    acc.sys_word = true;
    if (word && (a & 1)) {
        // The 16-bit bus splits an unaligned word into two byte cycles.
        acc.addr = a;
        acc.ube_n = 0;
        acc.rd_last = false;      // the interlock releases on the SECOND half
        post(acc);
        uint32_t a1 = phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        acc.rd_last = true;
        post(acc);
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        post(acc);
    }
    return v;
}

// M5b THE BUS BYTE SWAPPER.  The write-data register is loaded through an
// 8-bit rotator controlled by A0 of the ACCESS: at an odd address the datapath
// value is rotated so its low byte lands on AD15-8, and BOTH bus cycles of a
// split word write then drive that same rotated value.  MEASURED, four
// quadrants, one case each: `88` (`mov [odd], dl`, DX=403F -> 3F40 and
// `mov [even], dl`, DX=6720 -> 6720), `C6.0` (imm8 A3 sign-extended to FFA3,
// odd -> A3FF), `50` (PUSH AX, AX=CD0B at an odd SP -> 0BCD on both halves;
// AX=1B17 at an even SP -> 1B17).  Validated 366/366 over the `88` byte-store
// rows.  Nothing here is per-opcode: it is one rotator on A0.
static inline uint16_t swap8(uint16_t v) {
    return uint16_t((v >> 8) | (v << 8));
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
// S5: reserve the write cycle(s) at the ROM row that issues the store.  The
// data is not known yet; `mem_write` / `io_write` fill it in when the EU pairs
// it, which always happens before the cycle's T1 is emitted.
void BiuTimed::write_request(uint16_t seg_val, uint16_t off, bool word,
                             uint8_t seg_idx, bool io, uint16_t upc) {
    Access acc;
    acc.bs = io ? uint8_t(kBsIoW) : uint8_t(kBsMemW);
    acc.segc = io ? uint8_t(2) : seg_code(seg_idx);
    acc.upc = upc;
    acc.need_data = true;
    uint32_t a = io ? uint32_t(off) : phys(seg_val, off);
    if (word && (a & 1)) {
        acc.addr = a;
        acc.ube_n = 0;
        post(acc);
        uint32_t a1 = io ? uint32_t(uint16_t(off + 1))
                         : phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        post(acc);
        wres_ += 2;
    } else {
        acc.addr = a;
        acc.ube_n = uint8_t((word || (a & 1)) ? 0 : 1);
        post(acc);
        wres_ += 1;
    }
}

// The reserved cycles, in the order the BIU will run them: the one already
// in flight, then the committed one, then the queued requests.
BiuTimed::Access* BiuTimed::find_reserved() {
    if (run_ && cur_.need_data) return &cur_;
    if (cmt_valid_ && cmt_.need_data) return &cmt_;
    for (auto& a : req_)
        if (a.need_data) return &a;
    return nullptr;
}

void BiuTimed::mem_write(uint16_t seg_val, uint16_t off, uint16_t data,
                         bool word, uint8_t seg_idx, uint16_t upc) {
    core_.mem_write(seg_val, off, data, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    int n = (word && (a & 1)) ? 2 : 1;
    // M5b: ONE pass through the A0 byte swapper, on the ACCESS's own address --
    // both cycles of a split then drive that same rotated value.
    uint16_t d = (a & 1) ? swap8(data) : data;
    for (int i = 0; i < n; ++i) {
        Access* r = find_reserved();
        if (!r) break;
        r->data = d;
        r->need_data = false;
        if (wres_) --wres_;
    }
}

uint16_t BiuTimed::io_read(uint16_t port, bool word, uint16_t upc) {
    uint16_t v = core_.io_read(port, word, upc);
    Access acc;
    acc.bs = kBsIoR;
    acc.addr = port;
    acc.segc = 2;  // I/O drives the "no segment" code (MEASURED, E4 case 0)
    acc.upc = upc;
    // The bus carries the datapath value back through the A0 swapper, i.e. the
    // word the port presented.  MEASURED: `E4` case 0, `in al, 9dh` with
    // iord=23D8 shows 23D8 on the data phase, not the byte plus a stale lane.
    acc.data = (port & 1) ? swap8(v) : v;
    if (word && (port & 1)) {
        // The 16-bit bus splits an unaligned WORD I/O access into two byte
        // cycles, exactly as it does for memory, and both drive the port's
        // own word.  MEASURED: `E5` case 4, `in ax, 79h` -> ports 79 and 7A.
        acc.ube_n = 0;
        acc.rd_last = false;
        post(acc);
        acc.addr = uint32_t(uint16_t(port + 1));
        acc.ube_n = uint8_t((acc.addr & 1) ? 0 : 1);
        acc.rd_last = true;
        post(acc);
    } else {
        acc.ube_n = uint8_t((word || (port & 1)) ? 0 : 1);
        post(acc);
    }
    return v;
}

void BiuTimed::io_write(uint16_t port, uint16_t data, bool word, uint16_t upc) {
    core_.io_write(port, data, word, upc);
    int n = (word && (port & 1)) ? 2 : 1;
    uint16_t d = (port & 1) ? swap8(data) : data;
    for (int i = 0; i < n; ++i) {
        Access* r = find_reserved();
        if (!r) break;
        r->data = d;
        r->need_data = false;
        if (wres_) --wres_;
    }
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
