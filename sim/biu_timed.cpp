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

static inline uint16_t swap8(uint16_t v) {   // the A0 rotator (see M5b below)
    return uint16_t((v >> 8) | (v << 8));
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
    no_eval_ = -1;
    e_pend_ = false;
    e_from_ = 0;
    e_x_ = -1;
    push_absorb_clk_ = -2;
    push_absorb_from_ = -2;
    req_.clear();
    eu_pending_ = 0;
    rd_pending_ = 0;
    wr_pending_ = 0;
    wres_ = 0;
    wr_done_clk_ = -1;
    rd_done_q_.clear();
    opr_held_ = 0;
    opr_free_clk_ = -1;
    last_wval_ = 0;
    bus_idx_ = 0;
    wlfsr_ = wseed_;
}

// M2r: the rig's wait draw for the bus cycle whose T1 opens now.  Mirrors
// nec_bus.sv's `next_t_state == ST_T1` block exactly, including the priority
// order and the fact that the LFSR advances once per bus cycle regardless of
// whether the random source is the one being used... except that nec_bus only
// advances it on the random path, so this does too.
int BiuTimed::next_waits() {
    long k = bus_idx_++;
    if (!wvec_.empty() && k < long(wvec_.size())) return wvec_[size_t(k)] & 31;
    if (wrand_) {
        int n = (int(wlfsr_ & 0xFF) * (wmax_ + 1)) >> 8;
        wlfsr_ = uint16_t((wlfsr_ >> 1) ^ ((wlfsr_ & 1) ? 0xB400u : 0u));
        return n;
    }
    return waits_;
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
        // M2r: the rig latches this access's wait count at T1 ENTRY, which
        // fixes the cycle's length and its ONE eval instant.
        cur_.waits = next_waits();
        cur_.last_i = 3 + cur_.waits;
        cur_.eval_i = (cur_.waits == 0) ? 2 : cur_.last_i;
        // ...driving whatever OPR still holds if nothing paired it.
        if (cur_.need_data && is_write(cur_.bs))
            cur_.data = (cur_.addr & 1) ? swap8(last_wval_) : last_wval_;
    }
    // The data phase opens on T2.
    if (run_ && ci_ == 1 && cur_.sys_word)
        cur_.data = sys_word_at(cur_.addr);

    const bool display = cmt_valid_ && cmt_t1_ == c + 1;
    const int last_i = cur_.last_i;                 // index of T4
    const int eval_i = cur_.eval_i;                 // M2r: the eval instant

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
    // F1(b), M2r: ...and a fetch that PUSHES keeps the queue port for the two
    // clocks its bytes take to land -- the PUSH EDGE (eval + 1) and the
    // ABSORB clock (eval + 2), the clock before they are poppable.  Together
    // with the T1..eval hold below that is ONE statement: A FETCH OWNS THE
    // QUEUE PORT FROM ITS T1 UNTIL ITS BYTES ARE IN.  A DOOMED fetch pushes
    // nothing and so lets go at the eval, which is why `EB` case 0 shows the E
    // on the doomed fetch's T4 at w0.  At w0 the two absorb clocks are T4 and
    // T4+1 and the w0 ratchet does not move (165,481 either way -- no w0
    // stimulus separates them); at w1 they are T4+1 and T4+2, and `E8` case 4
    // is the case that needs both (golden E on the push's status clock at
    // T4+3, not on T4+1).
    if (e_pend_ && c >= e_from_ && r.qs == kQsNone &&
        !(c >= push_absorb_from_ && c <= push_absorb_clk_) &&
        // ...but only while the EU's access has not STARTED: once its status
        // is on the pins (its display clock, or a cycle already running) the
        // QS port is free again, so the second half of a SPLIT push does not
        // hold the E any longer.  MEASURED: `E8` case 6 (CALL at an odd SP)
        // shows E on the FIRST half's status cycle.
        (req_.empty() || c == e_x_ ||
         (cmt_valid_ && !cmt_.is_fetch) || (run_ && !cur_.is_fetch)) &&
        // M2r: a fetch owns the QS port THROUGH ITS COMPLETION EVAL, and the
        // port is free from the eval's own clock onward.  At w0 the eval is at
        // the end of T3, so the E lands on T4 -- the zero-wait law unchanged.
        // Under waits the eval is at the end of T4, so it lands on T4+1, which
        // is mission-H's "a doomed fetch counts as busy through its (deferred)
        // completion eval -- E moves from the doomed fetch's T4 to the
        // following cycle".  One condition, both regimes.
        !(run_ && cur_.is_fetch && ci_ <= eval_i)) {
        r.qs = kQsEmpty;
        e_pend_ = false;
    }

    if (run_) {
        r.tstate = (ci_ == 0)          ? uint8_t(kT1)
                   : (ci_ == 1)        ? uint8_t(kT2)
                   : (ci_ == 2)        ? uint8_t(kT3)
                   : (ci_ < last_i)    ? uint8_t(kTw)
                                       : uint8_t(kT4);
        r.bs = (ci_ >= eval_i) ? uint8_t(kBsPasv) : cur_.bs;
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
        // OPR RELEASE -- and it does NOT STRETCH.  The store hands its word to
        // the AD OUTPUT LATCH at T2 and OPR is free from T3; how much longer
        // the BUS holds that word out is the memory's business, not OPR's.  So
        // the release sits at a FIXED cycle-relative index (2) at every wait
        // level, while eu_done (the read handover and the retire deadline)
        // rides the eval and stretches.  That asymmetry is mission-H's
        // "eu_done shifts identically" vs "the trap chain marches on from the
        // ZERO-WAIT completion point (eu_wdone)" -- two clocks in one cycle,
        // and only one of them is the READY sample.
        //
        // MEASURED, and it is the WAIT AXIS that separates the two candidates
        // (sw/wchain.py `MEMW>MEMW`, F7.6's divide-trap push chain, whose two
        // chains differ by exactly the two extra ROM rows between 01F5->01F9
        // and 01F9->01FB):
        //
        //   chain            w0    w1    w3
        //   PSW -> PS (+2 rows)   T4+4  T4+4  T4+2
        //   PS  -> PC             T4+3  T4+2  T4+2
        //
        // With the release FIXED at index 2 the issuing rows land at index 5
        // and 3 at every wait level, and the eval geometry alone produces all
        // six numbers.  With the release STRETCHED to the eval they walk out
        // to +5/+4 at w1 -- measured and rejected.
        if (ci_ == 1 && is_write(cur_.bs) && opr_held_ > 0) {
            --opr_held_;
            opr_free_clk_ = c + 1;
        }
        if (ci_ == eval_i) {
            eval_here = true;
            // M2r: THE COMPLETION EVAL'S DISPLAY CLOCK IS NOT AN EVAL POINT.
            // At w0 that clock is T4, which is inside the cycle and so was
            // never an idle-eval candidate -- "T4 is NOT an eval point" (M1)
            // is this same statement, and the model already had it for free.
            // Under waits the eval is at the end of T4, so its display clock
            // is T4+1, an IDLE clock, and the rule has to be said out loud:
            // mission-H's "the end of that deferred-eval cycle is NOT an eval
            // point -- a request that first asserts inside it waits for the
            // next idle-cycle end".  MEASURED: `89` case 48 at w1, where the
            // store's status appears two idle clocks after the fetch's T4 and
            // not one.  (The STRONG form of this -- every eval, idle ones
            // included, killing its successor, i.e. a true 2-clock grid -- was
            // tried and is FALSIFIED at w0: 165,481 -> 119,311.  Idle evals
            // run on every clock.  The grid is NOT the eval cadence.)
            no_eval_ = c + 1;
        }
        // F3: the flush-only point commits the REDIRECT PREFETCH only.  A
        // pending EU request still owns the first slot, and an EU access is
        // never granted at a T4 -- so with a request outstanding this point
        // simply does not fire and both wait for the next normal eval.
        if (ci_ == last_i && cur_.is_fetch && flush_eval_ && req_.empty())
            eval_here = true;
        if (ci_ == last_i) {
            // M2r: everything below is stated from the EVAL instant, which is
            // this clock at w>0 and the clock before T4 at w0.
            const long e = c - (last_i - eval_i);
            if (cur_.is_fetch && cur_.push_n) {
                // M3 / mission-H: the push lands one clock after the eval and
                // the byte is POPPABLE two clocks after the push edge.
                for (int i = 0; i < cur_.push_n; ++i)
                    q_.push_back(QByte{cur_.push_b[i], e + 3});
                // F1(b): the queue port is busy from the push edge until
                // the bytes are in -- see the QS-port block above.
                push_absorb_from_ = e + 1;
                push_absorb_clk_ = e + 2;
            }
            if (!cur_.is_fetch) {
                // eu_done: the data handover / store retire lands with the
                // push, one clock after the eval -- which is what mission-H
                // saw as "post-access EU schedules stretch by exactly one
                // cycle per waited access".
                if (eu_pending_) --eu_pending_;
                if (is_write(cur_.bs)) {
                    wr_done_clk_ = e + 2;
                    if (wr_pending_) --wr_pending_;
                } else if (rd_pending_ && cur_.rd_last) {
                    --rd_pending_;
                }
                if (cur_.rd_last && !is_write(cur_.bs)) {
                    rd_done_q_.push_back(e + 2);
                    last_wval_ = cur_.rd_val;    // the read lands in OPR
                }
            }
            run_ = false;
        } else {
            ++ci_;
        }
    } else if (!cmt_valid_ && c != no_eval_) {
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

void BiuTimed::flush(uint16_t cs, uint16_t pc) {
    q_.clear();
    // A committed-but-not-started fetch is withdrawn; a fetch already in
    // flight completes and its data is discarded (biu_model.md flush law).
    // This runs BEFORE the redirect is loaded: withdrawing a fetch rewinds
    // `fetch_ptr_` to what it was before that fetch was chosen, so doing it
    // afterwards silently threw the redirect away and sent the very next
    // eval back into the OLD stream (`FF.4` case 8: the chip fetches 0D8163,
    // the model re-fetched 0CE096).
    withdraw_fetch();
    // The redirect fetches from the NEW CS:PC.  A far transfer loads CS on
    // an earlier micro-row than the FLUSH, so taking CS from the last queue
    // pop instead left the redirect pointing into the OLD segment.
    cs_ = cs;
    fetch_ptr_ = pc;
    suspended_ = false;
    pop_is_first_ = true;
    opc_valid_ = false;
    // ...and DOOMED means doomed on either side of the announcement.  What
    // `withdraw_fetch` leaves behind is a fetch whose status is already on the
    // pins (`cmt_t1_ == clk_`): it runs its four clocks like any other cycle,
    // but nothing it reads may enter the queue.  Missing this second case is
    // what let the post-flush retire pre-pop a byte the chip does not have --
    // `FF.2` 01BD flushes two rows before its `E`, and the fetch whose T1 opens
    // on the flush clock was pushing into the flushed queue.
    if (run_ && cur_.is_fetch) cur_.push_n = 0;
    if (cmt_valid_ && cmt_.is_fetch) cmt_.push_n = 0;
    // F1: the queue port is not free on the flush clock itself if a bus cycle
    // still owns it; from the next clock on it is free once that cycle has
    // reached its T4.
    flush_eval_ = true;
    e_pend_ = true;
    e_x_ = clk_;
    // ...but only a FETCH owns the queue port.  An EU access never touches
    // the queue, so a flush that lands on the clock an EU read opens its T1
    // still takes the port at once.  MEASURED: `CF` (IRET) case 0 -- the E
    // shows on the third stack read's T1, the clock 01E8's `F` releases on.
    e_from_ = ((run_ && cur_.is_fetch) ||
               (cmt_valid_ && cmt_t1_ == clk_ && cmt_.is_fetch)) ? clk_ + 1
                                                                 : clk_;
}

void BiuTimed::clear_consumed() {
    consumed_.clear();
    // No pre-popped opcode in the latch => the loader is about to pop the
    // first byte of an instruction itself, and that pop is an F.  It also
    // STARTS the decode march (M3c), so there is no previous step for it to
    // re-run.  When the opcode IS latched the march is already running and
    // its stride is measured from the pre-pop, which is what puts the ModR/M
    // one clock after the opcode.
    if (!opc_valid_) { pop_is_first_ = true; last_dec_ = -1; }
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
    last_dec_ = clk_;   // the march's first step starts here (M3c)
}

uint8_t BiuTimed::pop(uint16_t cs, uint16_t upc, bool penalise) {
    cs_ = cs;
    if (opc_valid_) {
        opc_valid_ = false;
        uint8_t b = opc_byte_;
        consumed_.push_back(b);
        return b;
    }
    // M3c A DECODE STEP THAT MISSES RE-RUNS.  The decoder walks its byte
    // demands as a march of STEPS; a step that has to take a queue byte takes
    // it on the step's LAST clock, and if the byte is not poppable then the
    // WHOLE STEP runs again.  So the pop lands on the first clock at or after
    // `ready` that is a whole number of steps past the demand:
    //
    //     pop = min { demand + k*step : k >= 0, demand + k*step >= ready }
    //
    // `step` is not a parameter and not a table -- it is the march's own
    // stride, the clocks the decoder has advanced since its previous pop.
    // MEASURED over every v0.1 golden (sw/qcensus.py, with `ready`
    // reconstructed from the golden's OWN fetch stream as that fetch's
    // T4 + 2), previous decoder pop at clock 0.  Every observed cell:
    //
    //   step 1  modrm after the opcode or after the 0F byte, disp16-LO
    //           ready<=1 -> 1,  2 -> 2,  3 -> 3,  4 -> 4     (no penalty)
    //   step 2  the 0F page's opcode, the opcode after a prefix, disp8 after
    //           the modrm, disp16-HI after disp16-lo
    //           ready<=2 -> 2,  3 -> 4,  4 -> 4              (the step re-runs)
    //
    // This REPLACES M3b ("a queue miss costs two clocks", provenance 8.4): a
    // flat +2 is right for the two-clock steps and wrong for the one-clock
    // ones, which is exactly the 0F-escape / segment-prefixed residual of
    // 8.6 -- `26.8B` takes its ModR/M on the clock the byte arrives
    // (ready = opcode+2) and the flat penalty pushed it one late.  The EU's
    // own `Q` pops are not part of this march and never re-run.
    int guard = 0;
    const long demand = clk_;
    const long step = (penalise && last_dec_ >= 0 && demand > last_dec_)
                          ? demand - last_dec_ : 1;
    while ((q_.empty() || q_.front().ready > clk_) && ++guard < 4096) tick();
    if (step > 1) {
        long over = (clk_ - demand) % step;
        for (long i = over; i && i < step && ++guard < 4096; ++i) tick();
    }
    if (penalise) last_dec_ = clk_;
    if (q_.empty()) return 0x90;
    uint8_t b = q_.front().b;
    q_.pop_front();
    consumed_.push_back(b);
    qs_pending_ = pop_is_first_ ? kQsFirst : kQsSubseq;
    upc_pending_ = upc;
    pop_is_first_ = false;
    return b;
}

void BiuTimed::wait_retire_lead() {
    int guard = 0;
    while ((q_.empty() || q_.front().ready > clk_ + 1) && ++guard < 4096) tick();
}

void BiuTimed::wait_bus() {
    int guard = 0;
    while (wr_pending_ > 0 && ++guard < 4096) tick();
    while (clk_ < wr_done_clk_ && ++guard < 4096) tick();
}

// The F / OPR interlock: wait for the NEXT outstanding EU access -- read or
// write -- and consume it.  (See biu_timed.h: OPR is one register.)
void BiuTimed::wait_next_read(int extra) {
    int guard = 0;
    while (rd_done_q_.empty() && rd_pending_ > 0 && ++guard < 4096) tick();
    if (rd_done_q_.empty()) return;
    long t = rd_done_q_.front() + extra;
    rd_done_q_.pop_front();
    while (clk_ < t && ++guard < 4096) tick();
}

// The other half of the same interlock: the row cannot WRITE OPR while a
// store still owns it.
void BiuTimed::wait_opr_free() {
    int guard = 0;
    while (opr_held_ > 0 && ++guard < 4096) tick();
    while (clk_ < opr_free_clk_ && ++guard < 4096) tick();
}

void BiuTimed::wait_read() { wait_next_read(0); wait_opr_free(); }
void BiuTimed::wait_opr() { wait_next_read(1); }

// --- data accesses ----------------------------------------------------------

uint16_t BiuTimed::mem_read(uint16_t seg_val, uint16_t off, bool word,
                            uint8_t seg_idx, uint16_t upc) {
    uint16_t v = core_.mem_read(seg_val, off, word, seg_idx, upc);
    uint32_t a = phys(seg_val, off);
    Access acc;
    acc.rd_val = v;
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
        acc.rd_last = false;   // a split is ONE access to the EU (and to OPR)
        post(acc);
        uint32_t a1 = io ? uint32_t(uint16_t(off + 1))
                         : phys(seg_val, uint16_t(off + 1));
        acc.addr = a1;
        acc.ube_n = uint8_t((a1 & 1) ? 0 : 1);
        acc.rd_last = true;
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
    last_wval_ = data;
    for (int i = 0; i < n; ++i) {
        Access* r = find_reserved();
        if (!r) break;
        r->data = d;
        r->need_data = false;
        // ...and from this moment the store OWNS OPR (see wait_opr_free).
        ++opr_held_;
        if (wres_) --wres_;
    }
}

uint16_t BiuTimed::io_read(uint16_t port, bool word, uint16_t upc) {
    uint16_t v = core_.io_read(port, word, upc);
    Access acc;
    acc.rd_val = v;
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
    last_wval_ = data;
    for (int i = 0; i < n; ++i) {
        Access* r = find_reserved();
        if (!r) break;
        r->data = d;
        r->need_data = false;
        ++opr_held_;
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
