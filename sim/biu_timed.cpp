// biu_timed.cpp -- see biu_timed.h.

#include "biu_timed.h"

#include "state.h"

#include <cstdio>
#include <cstdlib>

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
    // M9 (T4).  S5 = IE, S4:S3 = segment -- and S6 is NOT "always 0 for a
    // CPU-driven cycle": it is the 8080 EMULATION-MODE bit, high for every
    // cycle the part runs with MD clear.
    //
    // MEASURED (sw/timed_fuzz.py family `ps d!=5`, 73 seeds): every one of
    // them begins at an opcode `0F xx`, the chip then reads an interrupt
    // VECTOR and pushes PSW / CS / IP to the stack, and PS3 comes up BETWEEN
    // the PSW push and the CS push -- i.e. on the clock the BRKEM microcode
    // clears MD -- and stays up on every following cycle, CODE fetches
    // included (`ps e` on a CS fetch, `ps d`/`ps 9` on an SS store).  It goes
    // down again at RETEM / CALLN.
    //
    // The T3 handoff recorded this family as "present in brkem and non-brkem
    // seeds alike, so it is not emulation mode" (13.5).  That negative was
    // read off the BANK's `has_brkem` flag, which only counts the documented
    // `0F FF` encoding -- and the chip's PLA decodes a whole spread of
    // undefined `0F xx` second bytes as BRKEM too (`0F F7`, `0F FD`, `0F D3`,
    // `0F 40`, `0F 73`, `0F 90`, ... each taking the NEXT byte as its vector).
    // Every seed in the family is a BRKEM; the flag was measuring the
    // encoding, not the instruction.
    bool ie = psw_ && (*psw_ & kFlagIE);
    bool md = md8080_ && *md8080_;
    return uint8_t((md ? 8 : 0) | (ie ? 4 : 0) | (segc & 3));
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

// DIAGNOSTIC ONLY (Q2): the flush / commit trace.  One line per case, per
// flush(), per commit and per QS=E display, so the E clock, the flush clock
// and the commit clock can be read against the bus state each of them saw.
// Touches no model state.  (The analogue of V30SIM_ROWTRACE / EVALTRACE.)
static const bool kFlushTrace = ::getenv("V30SIM_FLUSHTRACE") != nullptr;

void BiuTimed::begin_case() {
    if (kFlushTrace) fprintf(stderr, "FB\n");
    core_.begin_case();
    core_.clear_wrap();
    clk_ = 0;
    run_ = false;
    ci_ = 0;
    cmt_valid_ = false;
    cmt_t1_ = -1;
    cmt_disp_ = -1;
    cur_t1_ = -1;
    last_addr_ = 0;
    last_data_ = 0;
    last_ps_ = 0;
    last_ube_ = 0;
    last_dp_ = 0;
    q_.clear();
    fetch_ptr_ = 0;
    cs_ = 0;
    suspended_ = false;
    halted_ = false;
    halt_pending_ = false;
    last_fetch_addr_ = 0;
    pf_land_from_ = pf_land_to_ = -2;
    pf_infl_to_ = -2;
    pf_infl_n_ = 0;
    pf_owed_ = false;           // M19
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
    eu_slot_busy_ = false;
    eu_accept_clk_ = -1;
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
    last_wr_waits_ = 0;
    wlfsr_ = wseed_;
    // S9a: the pin schedule is a per-case rig input; clear it here so a form
    // without an `evt` record can never inherit the previous case's.
    ev_trigger_ = 0;
    ev_pin_ = 0;
    ev_addr_ = 0;
    ev_delay_ = 0;
    ev_hold_ = 0;
    ev_pins_ = 0;
    ev_anchor_ = -1;
    first_fpop_ = -1;
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
    // M7b: the OUTSTANDING-FETCH term clears when the bytes are POPPABLE
    // (e+3), not when they are WRITTEN (e+1) -- see biu_timed.h.  The queue
    // counter has already taken them, so across the two landing clocks the
    // scheduler counts them twice.
    if (clk_ - 1 <= pf_infl_to_) n += pf_infl_n_;
    return n;
}

// --- the clock --------------------------------------------------------------

// DIAGNOSTIC ONLY (T3): env-gated stderr trace, no model state touched.
static const bool kEvalTrace = ::getenv("V30SIM_EVALTRACE") != nullptr;


// DIAGNOSTIC ONLY (S9b): `V30SIM_TICKTRACE=<clk>` dumps the bus register state
// for 14 clocks from <clk>.  Touches no model state.
static const long kTickTrace =
    ::getenv("V30SIM_TICKTRACE") ? ::atol(::getenv("V30SIM_TICKTRACE")) : -1;

void BiuTimed::tick() {
    long c = clk_;
    if (kTickTrace >= 0 && c >= kTickTrace && c < kTickTrace + 14)
        std::fprintf(stderr, "TK %ld run=%d ci=%d bs=%d cmtv=%d cmt_t1=%ld "
                             "cmtfetch=%d halted=%d susp=%d slot=%d acc=%ld\n",
                     c, int(run_), ci_, int(cur_.bs), int(cmt_valid_), cmt_t1_,
                     int(cmt_.is_fetch), int(halted_), int(suspended_),
                     int(eu_slot_busy_), eu_accept_clk_);

    // A committed cycle opens its T1 on this clock.
    if (!run_ && cmt_valid_ && cmt_t1_ == c) {
        run_ = true;
        cur_ = cmt_;
        ci_ = 0;
        cur_t1_ = c;              // S9b: this cycle's own T1 clock
        cmt_valid_ = false;
        // M10: the bus has TAKEN the whole request -- the slot is free from
        // this clock, which is the clock the blocked row issues on.  `rd_last`
        // is what makes a SPLIT one request: the slot is held until the SECOND
        // cycle opens.  The `eu_accept_clk_ == c` test is what makes "issues
        // ON that clock" work: the released row runs at clk_ == T1 and may
        // post its OWN request before this tick runs, and that newer occupant
        // (whose accept clock is not yet known) must not be released by the
        // older access's T1.
        if (!cur_.is_fetch && cur_.rd_last && eu_accept_clk_ == c)
            eu_slot_busy_ = false;
        // S9a: the rig's fetch-trigger anchor (tb_v30_core.sv: the CODE T1
        // whose 20-bit address is `ev_addr`).
        if (ev_trigger_ == 1 && ev_anchor_ < 0 && cur_.is_fetch &&
            cur_.addr == ev_addr_)
            ev_anchor_ = c;
        // M2r: the rig latches this access's wait count at T1 ENTRY, which
        // fixes the cycle's length and its ONE eval instant.
        cur_.waits = next_waits();
        cur_.last_i = 3 + cur_.waits;
        // S8/S9: the HALT's status release is at index 1 at every wait level;
        // every other cycle releases at the READY sample (M2r).
        cur_.eval_i = cur_.is_halt ? 1
                      : (cur_.waits == 0) ? 2 : cur_.last_i;
        // ...driving whatever OPR still holds if nothing paired it, through
        // the SAME single pass of the A0 swapper `mem_write` uses (M5b: the
        // rotation is a property of the ACCESS, not of the cycle).
        if (cur_.need_data && is_write(cur_.bs))
            cur_.data = cur_.odd_base ? swap8(last_wval_) : last_wval_;
    }
    // S8/S9: the HALT status takes the register on the FIRST clock the
    // register is FREE -- the bus idle and not the completion eval's display
    // slot.  MEASURED at w0/w1/w3 alike: the display lands on the previous
    // cycle's e+2 (w0 T4+1, w>0 T4+2), one clock later than a granted cycle's
    // display, because a grant loads the register AT the eval and the HLT row
    // can only load it once the finishing cycle has let go.
    if (halt_pending_ && !run_ && !cmt_valid_ && c != no_eval_) {
        cmt_ = halt_acc_;
        // S9b -- THE HALT DISPLAY DRIVES THE ADDRESS LATCH AS IT STANDS WHEN
        // THE CYCLE TAKES THE REGISTER, not as it stood at the HLT decode.
        // M16 already says the decode does not take a committed fetch back, so
        // a fetch granted at the decode's own eval RUNS -- and then it is that
        // fetch's address the HALT cycle drives.  MEASURED on the waited EVT
        // captures, where the two differ by exactly the extra fetch (chip
        // 0504, model 0502 with the decode-time snapshot).
        cmt_.addr = (uint32_t(data_ps(2)) << 16) | (last_fetch_addr_ & 0xFFFFu);
        cmt_.data = uint16_t(last_fetch_addr_ & 0xFFFF);
        cmt_valid_ = true;
        cmt_disp_ = c;
        cmt_t1_ = c + 1;
        halt_pending_ = false;
    }
    // The data phase opens on T2.
    if (run_ && ci_ == 1 && cur_.sys_word)
        cur_.data = sys_word_at(cur_.addr);

    const bool display = cmt_valid_ && c >= cmt_disp_ && c < cmt_t1_;
    // S9a (Access::no_addr): an INTA drives no address.  Freeze the FLOATING
    // AD -- the last data phase, upper nibble 0 -- into the access on its
    // display clock, so the display row and T1 both carry it through the
    // ordinary address path.
    if (display && cmt_.no_addr) cmt_.addr = uint32_t(last_data_);
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
        if (kFlushTrace)
            fprintf(stderr, "FE %ld x=%ld run=%d ci=%d fetch=%d cmt=%d\n",
                    c, e_x_, int(run_), run_ ? ci_ : -1,
                    int(run_ && cur_.is_fetch), int(cmt_valid_));
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

    // S9a: the rig's fpop-trigger anchor -- the WINDOW-OPENING `F` pop
    // (tb_v30_core.sv: `recording && QS == 2'b01 && fcount == 0`).
    if (ev_trigger_ == 2 && ev_anchor_ < 0 && r.qs == kQsFirst) ev_anchor_ = c;
    if (first_fpop_ < 0 && r.qs == kQsFirst) first_fpop_ = c;

    if (rows_) rows_->row(r);
    if (kEvalTrace) {
        int popp = 0;
        for (const auto& b : q_) if (b.ready <= c) ++popp;
        fprintf(stderr, "QT %ld q=%d pop=%d occ=%d run=%d ci=%d fetch=%d "
                        "cmt=%d qs=%d susp=%d req=%d rd=%d wr=%d eu=%d opr=%d\n",
                c, int(q_.size()), popp, occupancy(), int(run_), run_ ? ci_ : -1,
                int(run_ && cur_.is_fetch), int(cmt_valid_), int(r.qs),
                int(suspended_), int(req_.size()), rd_pending_, wr_pending_,
                eu_pending_, opr_held_);
    }
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
        // M7 -- THE PREFETCH-ELIGIBILITY TEST IS SAMPLED AT A FIXED CYCLE
        // INDEX (2 = T3), NOT AT THE COMPLETION EVAL.  See biu_timed.h.
        // S9b -- ...and the HALT BLOCK IS SAMPLED AT THE SAME INDEX.  M16
        // ("prefetch is blocked from the HLT DECODE cycle") was measured on
        // the w0 goldens, where index 2 and the eval are the same clock; under
        // waits they are not, and the chip grants a refill the model refused.
        // The block is not a separate rule: it is one more term of the
        // eligibility answer M7 already says is decided at index 2 and merely
        // APPLIED at the completion eval.
        if (ci_ == 2) pf_arm_ = occupancy() <= 4 && !halted_;
        if (ci_ == eval_i) {
            eval_here = true;
            pf_arm_valid_ = true;   // this eval applies the index-2 sample
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
                // M6: keyed to T4, NOT to the eval.  See biu_timed.h.
                pf_land_from_ = pf_land_to_ = c + 1;
                // M7b: ...and the accounting term for those bytes lives until
                // they are POPPABLE.
                pf_infl_to_ = e + 2;
                pf_infl_n_ = cur_.push_n;
            }
            // S9a: ...and the HALT PSEUDO-CYCLE is not an EU access at all.
            // It never went through `post()` (the HLT row drives the status
            // register directly), so it must not complete one either: before
            // this guard it decremented `eu_pending_` and pushed a phantom
            // read-completion clock into `rd_done_q_`, which the FIRST `F` row
            // after the wake then consumed instead of waiting for its own
            // acknowledge -- HLT.INT's second INTA landed 3 clocks early.
            if (!cur_.is_fetch && !cur_.is_halt) {
                // eu_done: the data handover / store retire lands with the
                // push, one clock after the eval -- which is what mission-H
                // saw as "post-access EU schedules stretch by exactly one
                // cycle per waited access".
                if (eu_pending_) --eu_pending_;
                if (is_write(cur_.bs)) {
                    last_wr_waits_ = cur_.waits;
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
    pf_arm_valid_ = false;   // M7: the sample is spent by its own eval
}

// The completion eval: pick the next bus cycle.  The winner is DISPLAYED on
// the next clock and opens its T1 the clock after that (M1).
// DIAGNOSTIC ONLY (T3).  Off unless V30SIM_EVALTRACE is set; writes to stderr
// and touches no model state.  One line per eval point, so a divergence in the
// prefetch decision can be read against the state the decision saw.

void BiuTimed::et(char decision, char why) const {
    if (!kEvalTrace) return;
    long oldest = q_.empty() ? -1 : q_.front().ready;
    long newest = q_.empty() ? -1 : q_.back().ready;
    fprintf(stderr,
            "ET %ld %c%c q=%d occ=%d req=%d susp=%d halt=%d run=%d "
            "cur=%d ci=%d nw=%d old=%ld new=%ld land=%ld,%ld fp=%u\n",
            clk_ - 1, decision, why, int(q_.size()), occupancy(), int(req_.size()),
            int(suspended_), int(halted_), int(run_),
            run_ ? int(cur_.bs) : -1, run_ ? ci_ : -1, run_ ? cur_.waits : -1,
            oldest, newest, pf_land_from_, pf_land_to_, unsigned(fetch_ptr_));
}

// S9b -- THE DISPLAY CLOCK AND THE T1 ARE TWO DIFFERENT THINGS, AND THE ONLY
// THING BETWEEN THEM IS WHETHER THE BUS IS FREE.
//
// M1/M2 say the winner's status is loaded into the register at the eval (so it
// is on the pins from eval + 1) and its T1 opens at eval + 2.  For EVERY
// ordinary cycle those are the same statement, because the eval sits at
// `last_i - 1` (w0) or at `last_i` (waited) and eval + 2 IS the first clock the
// bus is free.  The HALT pseudo-cycle is the one access where they come apart:
// its eval is at index 1 (S8/S9, the measured status release) while its T4 is
// still at index 3, so a cycle granted at that eval is DISPLAYED at index 2 and
// has to wait for index 4 to open its T1.
//
// MEASURED, and it is the chip's own rows: over the EVT captures with a HALT
// wake the golden drives the woken fetch's CODE status on the HALT cycle's T3
// AND T4 and opens its T1 the clock after -- two display clocks, one T1.  A
// model that ties the T1 to the display puts the T1 inside the still-running
// HALT cycle, where it can never open at all.
//
//     display = eval + 1        T1 = max(eval + 2, the bus's first free clock)
//
// w-neutral by construction for every non-HALT access.
long BiuTimed::bus_free_clk() const {
    if (!run_) return clk_;                 // nothing running: no constraint
    return cur_t1_ + cur_.last_i + 1;       // the clock after this cycle's T4
}

void BiuTimed::eval() {
    flush_eval_ = false;   // F3: the flush-only T4 point is spent by any commit
    const long free_clk = bus_free_clk();
    if (!req_.empty()) {
        et('R', '-');
        cmt_ = req_.front();
        req_.pop_front();
        cmt_valid_ = true;
        cmt_disp_ = clk_;
        cmt_t1_ = free_clk > clk_ + 1 ? free_clk : clk_ + 1;
        // M10: the slot's occupant now has the T1 that frees it -- the LAST
        // cycle of the access -- so a row blocked on it knows the clock it may
        // issue on.  While a split's first half is committed the accept clock
        // stays unknown (-1) and the blocked row keeps waiting.
        if (cmt_.rd_last) eu_accept_clk_ = cmt_t1_;
        if (kFlushTrace)
            fprintf(stderr, "FC %ld disp=%ld t1=%ld kind=R addr=%05x\n",
                    clk_ - 1, clk_, cmt_t1_, unsigned(cmt_.addr));
        return;
    }
    // F2 keeps SUSP at the eval: it is measured to reach the BIU one row
    // early and to take back a fetch the eval has just chosen.
    // M19: ...but SUSP gates the RAISING of a prefetch request, not a request
    // the flush already raised.  See biu_timed.h.
    if (suspended_ && !pf_owed_) { et('.', 'S'); return; }
    // M7: at a COMPLETION eval the answer was decided at index 2 of the cycle
    // that is finishing; at an IDLE eval the queue -- and the HALT -- are read
    // live, because there is no cycle to have sampled them.
    if (pf_arm_valid_ ? !pf_arm_ : (occupancy() > 4 || halted_)) {
        et('.', 'O');
        return;
    }
    // M6 (biu_timed.h): no fetch is chosen while the previous fetch's bytes
    // are LANDING in the queue.
    if (clk_ - 1 >= pf_land_from_ && clk_ - 1 <= pf_land_to_) { et('.', 'M'); return; }
    et('F', '-');
    pf_owed_ = false;      // M19: the arbiter has taken the request
    cmt_ = make_fetch();
    // The fetch pointer advances when the cycle is COMMITTED, not when its
    // data lands: the address is latched into the bus cycle here.
    cmt_prev_fp_ = fetch_ptr_;
    last_fetch_addr_ = cmt_.addr;
    fetch_ptr_ = uint16_t(fetch_ptr_ + cmt_.push_n);
    cmt_valid_ = true;
    cmt_disp_ = clk_;
    cmt_t1_ = free_clk > clk_ + 1 ? free_clk : clk_ + 1;
    if (kFlushTrace)
        fprintf(stderr, "FC %ld disp=%ld t1=%ld kind=F addr=%05x\n",
                clk_ - 1, clk_, cmt_t1_, unsigned(cmt_.addr));
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
    if (cmt_valid_ && cmt_.is_fetch && cmt_disp_ >= clk_) {
        cmt_valid_ = false;
        fetch_ptr_ = cmt_prev_fp_;
    }
}

void BiuTimed::susp() {
    suspended_ = true;
    withdraw_fetch();   // F2 -- see biu_timed.h
}

void BiuTimed::post(const Access& a) {
    // M10 -- ONE REQUEST SLOT (biu_timed.h).  The row that carries a new EU
    // access waits until the bus has taken the previous one, and issues on
    // the T1 that takes it (the LAST cycle's, for a split).  Only the cycle
    // that carries the EU's own request tests the slot; the second half of a
    // split is the BIU's own continuation and never blocks.
    if (a.first_of_access) {
        int g = 0;
        while (eu_slot_busy_ &&
               (eu_accept_clk_ < 0 || clk_ < eu_accept_clk_) && ++g < 4096)
            tick();
    }
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
    if (a.first_of_access) {
        eu_slot_busy_ = true;
        eu_accept_clk_ = -1;
    }
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
    // S9a: ...and the LAST of those pre-window fetch addresses is the address
    // a HALT display would drive if the part halts before making a fetch of
    // its own (the HALT law's "fetch pointer - 2", stated as the address it is
    // derived from).  Without this the prefetched HALT variants displayed
    // address 0.
    last_fetch_addr_ = last_addr_;
}

void BiuTimed::flush(uint16_t cs, uint16_t pc) {
    const long tr_noeval = no_eval_;          // diagnostic: pre-M12 values
    const long tr_absorb = push_absorb_clk_;
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
    pf_land_from_ = pf_land_to_ = -2;   // M6: the flush discards what was landing
    pf_infl_to_ = -2;                   // M7b: ...and their accounting with them
    // M19: the flush raises the prefetcher's request (empty queue, new fetch
    // pointer).  It stands until the bus takes it -- a later SUSP does not
    // reset it.  See biu_timed.h.
    pf_owed_ = true;
    // M7: the sampled quantity is the QUEUE COUNTER, and the flush zeroes it.
    // A latch taken at index 2 of a cycle the flush then invalidates cannot
    // hold the eval off -- the redirect must be free to go at once.  MEASURED:
    // without this `EB` is 149/200 at w1 and 145/200 at w3 (it is the only
    // form the whole waited suite loses), with it 200/200 at both.
    pf_arm_ = true;
    // M12 -- AND SO DOES EVERY OTHER LATCH THE COMPLETING CYCLE LEFT BEHIND.
    // The three lines above are one sentence: a decision the previous cycle
    // latched about a queue the flush has just emptied cannot outlive it.  The
    // same sentence covers the two latches that were NOT being cleared, and
    // they are exactly the two halves of the open Q2 question (14.2, 16.6):
    //
    //   * the COMPLETION EVAL's reserved display slot (11.2).  It is the
    //     completing cycle's decision that the next clock is its display
    //     clock; a flush invalidates that decision, so the end of the flush
    //     clock is an eval point again and the REDIRECT commits there.
    //   * the QUEUE-PORT absorb hold (11.3, F1(b)).  The hold exists because
    //     the fetch's bytes are LANDING; the flush discards them, so the port
    //     is released -- but not before the flush's own clock, which the dying
    //     absorb still occupies.
    //
    // Both are W0-NEUTRAL BY CONSTRUCTION, and for the same reason the rest of
    // M2r is: at w0 the completion eval sits at T3, so its display slot is T4,
    // a clock INSIDE the cycle that the idle-eval path never reaches; and the
    // absorb hold is [T4, T4+1], whose last clock is the EARLIEST clock a
    // flush can see it on at all (a flush at or before T4 finds the fetch
    // still running and zeroes its `push_n`, so no hold is created).  Under
    // waits the eval is at T4, the display slot is T4+1 and the hold is
    // [T4+1, T4+2] -- and a flush at T4+1 then frees the port at T4+2, which
    // is Q2's own measured "the port frees at T4+2 under waits" (14.2, 293
    // seeds), while a flush at T4+2 leaves the hold alone and the E stays at
    // T4+3, which is what the 57 `EB` w1 cases say.  ONE rule, both
    // populations, and the two clocks are the SAME clock because the E rides
    // the redirect's own display clock whenever the port is what deferred it.
    no_eval_ = -1;
    if (push_absorb_clk_ > clk_) push_absorb_clk_ = clk_;
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
    if (kFlushTrace)
        fprintf(stderr,
                "FX %ld run=%d ci=%d fetch=%d cmt=%d cmt_t1=%ld cmtfetch=%d "
                "req=%d noeval=%ld absorb=%ld,%ld efrom=%ld occ=%d\n",
                clk_, int(run_), run_ ? ci_ : -1,
                int(run_ && cur_.is_fetch), int(cmt_valid_), cmt_t1_,
                int(cmt_valid_ && cmt_.is_fetch), int(req_.size()), tr_noeval,
                push_absorb_from_, tr_absorb, e_from_, occupancy());
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

// S9a -- THE RECOGNITION BOUNDARY IS THE RETIRE, NOT THE POP.
//
// `opcode_prefetch` takes the successor's opcode at
// `max(retire deadline, byte poppable)` (M8's max-of-two-deadlines).  The
// RECOGNITION decision sits at the FIRST of those two only: the instruction's
// own retire.  It does not need the byte -- it is the decision NOT to take
// one -- and a recognised boundary therefore does not slide when the queue is
// dry.
//
// MEASURED, and the queue geometry is what separates the two readings: the
// anchor instruction's fetch delivers TWO bytes at an even address and ONE at
// an odd one, so half the `INT.*` / `NMI.*` goldens have the successor byte
// standing at the retire clock and half do not -- and the acknowledge lands at
// the SAME offset from the retire in both (`INT.90` 200/200, `NMI.90` 200/200
// with this rule; 177 and 186 with the pop deadline, and every one of the 37
// failures was an odd-address, dry-queue case).
//
// The pop itself is SUPPRESSED: the byte stays in the queue and the QS port
// stays idle (`INT.90` case 0 row 3 against `IE0.90` case 0 row 3 -- the same
// geometry with and without the recognition).
long BiuTimed::boundary_no_pop() {
    if (opc_valid_) return clk_;   // already latched: this IS the pop clock
    wait_bus();
    return clk_;
}

uint8_t BiuTimed::pop(uint16_t cs, uint16_t upc, bool disp_last) {
    cs_ = cs;
    if (opc_valid_) {
        opc_valid_ = false;
        uint8_t b = opc_byte_;
        consumed_.push_back(b);
        return b;
    }
    // M8 -- THE POP IS A MAX OF TWO CLOCKS, AND THERE IS NO RE-RUN.
    //
    //     pop = max(demand, ready + pen)
    //
    // `demand` is the requester's own clock (the byte-demand schedule the
    // loader and the micro-rows charge out); `ready` is the byte's poppable
    // clock, which the push sets to the delivering fetch's EVAL + 3 -- i.e.
    // T4 + 2 at w0 and T4 + 3 for a fetch that took ANY wait states, because
    // M2r moves the eval from T4-1 out to T4.  (That step -- one clock, flat
    // in the wait count -- is MEASURED directly: over the 3,242 banked chip
    // captures, a byte-limited pop lands at its deliverer's T4+2 when that
    // fetch was unwaited and at T4+3 for every Tw from 1 to 15.)
    //
    // **M3c ("a decode step that misses RE-RUNS", provenance 9.1) is
    // RETRACTED.**  It was fitted on the v0.1 goldens with four "stride 2"
    // classes POOLED, and the pooled cells `ready 3 -> pop 4` and
    // `ready 4 -> pop 4` cannot both be a max -- so a re-run was invented to
    // hold them together.  Split by role they are two different classes and
    // each is a plain max (sw/q1census.py, over the v0.1 goldens AND the 3,242
    // banked chip captures, w0 and every wait level; every cell is
    // SINGLE-VALUED):
    //
    //   demand 1, pen 0   modrm after the opcode / after the 0F byte,
    //                     disp16-LO after the modrm, a micro-row's imm-hi
    //                     ready<=1 -> 1,  2 -> 2,  3 -> 3,  4 -> 4, ...
    //   demand 2, pen 0   the 0F page's opcode, the opcode after a prefix, a
    //                     prefix after a prefix, a micro-row's first immediate
    //                     ready<=2 -> 2,  3 -> 3,  4 -> 4,  5 -> 5, ...
    //   demand 2, pen 1   the byte that COMPLETES a displacement: a disp8, or
    //                     the HIGH byte of a disp16
    //                     ready<=1 -> 2,  2 -> 3,  3 -> 4,  4 -> 5, ...
    //
    // The goldens never sample `ready 3` for the demand-2/pen-0 classes nor
    // `ready >= 4` for the pen-1 ones, which is exactly why the pooled fit
    // survived a 165,490-case w0 gate and still owned 87 % of the fuzz bank's
    // first divergences (provenance 13.5, family Q1).
    //
    // The economical reading of `pen`: the displacement's LAST byte is what
    // the EA adder needs, and the adder stands one stage behind the decode
    // port -- it reads the byte the clock after the queue can give it up.
    // Nothing here depends on that reading; the constant is measured.
    int guard = 0;
    const long demand = clk_;
    while ((q_.empty() || q_.front().ready > clk_) && ++guard < 4096) tick();
    if (disp_last && !q_.empty() && q_.front().ready >= demand &&
        ++guard < 4096)
        tick();
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
//
// M13 -- ...AND IN 8080 EMULATION MODE THE STORE DOES NOT LET GO UNTIL IT HAS
// RETIRED.  In native mode the store hands its word to the AD output latch at
// T2 and OPR is free from T3 (11.4, the FIXED index 2 that does NOT stretch).
// With MD set the release is the store's own eu_done -- the completion eval
// + 2, the deadline `wait_bus()` already carries -- so it STRETCHES with the
// eval like every other eval-keyed quantity.  See biu_timed.h.
void BiuTimed::wait_opr_free() {
    int guard = 0;
    if (md8080_ && *md8080_) { wait_bus(); return; }
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
        acc.first_of_access = false;   // M10: one request, two cycles
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
    acc.odd_base = (a & 1) != 0;   // M5b: one rotation, the ACCESS's own A0
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
        acc.first_of_access = false;   // M10: one request, two cycles
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
        // ...but only until the AD output latch takes the word at T2 (11.4).
        // If the pairing happens AFTER that clock has gone by (the write
        // cycle was reserved and STARTED before its data existed, which is
        // exactly what S5's retirement allows) the release instant is already
        // past, so OPR is never held.  Without this the hold LEAKS and the
        // next `-> OPR` row burns wait_opr_free's whole 4096-tick guard --
        // R-STALL, ucsim_t_provenance.md 13.
        if (!(r == &cur_ && run_ && ci_ > 1)) ++opr_held_;
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
        acc.first_of_access = false;   // M10: one request, two cycles
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
        // ...but only until the AD output latch takes the word at T2 (11.4).
        // If the pairing happens AFTER that clock has gone by (the write
        // cycle was reserved and STARTED before its data existed, which is
        // exactly what S5's retirement allows) the release instant is already
        // past, so OPR is never held.  Without this the hold LEAKS and the
        // next `-> OPR` row burns wait_opr_free's whole 4096-tick guard --
        // R-STALL, ucsim_t_provenance.md 13.
        if (!(r == &cur_ && run_ && ci_ > 1)) ++opr_held_;
        if (wres_) --wres_;
    }
}

uint16_t BiuTimed::inta_read(uint16_t upc) {
    uint16_t v = core_.inta_read(upc);
    Access acc;
    acc.bs = kBsInta;
    acc.addr = 0;         // filled from the FLOATING AD at the display clock
    acc.no_addr = true;   // see Access::no_addr
    acc.ube_n = 0;
    acc.segc = 2;
    acc.data = v;
    acc.upc = upc;
    post(acc);
    return v;
}

void BiuTimed::note_halt(uint16_t upc) {
    core_.note_halt(upc);
    // S8/S9 (see Access::is_halt).  HALT is NOT a bus request that goes
    // through the arbiter -- it is a status the HLT micro-row drives straight
    // into the registered status output, so it appears on the pins on the
    // NEXT clock whatever the eval grid is doing.  MEASURED: the ENTER stub's
    // HALT display lands at the previous cycle's e+2 at w0, w1 and w3 alike,
    // which is one clock past the slot a granted cycle would have taken --
    // exactly "the HLT row drives it, nothing arbitrates it".
    //
    // S9a: and it does NOT take a committed fetch back.  "Prefetch is blocked
    // FROM the decode cycle" is a statement about the DECISION, not a
    // retroactive withdrawal: a fetch the eval at the end of the OPCODE POP
    // clock already granted runs to completion and the HALT display waits for
    // it.  MEASURED on the prefetched HALT variants, where the pop sits on an
    // idle bus and the golden shows CODE display / T1 / T2 / T3 / T4 and only
    // then the HALT (`HLT.RES` case 1 rows 1-6; 300 of the 600 HALT cases).
    Access acc;
    acc.bs = kBsHalt;
    // M10 (T4): the HALT display's upper nibble is a LIVE PS, not a constant.
    // It was hard-coded to the bare segment code (CS = 2).  MEASURED on the
    // re-captured wvec corpus with its per-access parts retained (14.1 B1):
    // of 139 and 187 accesses in the two directed law cells, EXACTLY ONE
    // differs -- the closing HALT -- and only in this nibble: chip 0x6, model
    // 0x2, i.e. the chip carries IE on the HALT display like any other cycle.
    acc.addr = (uint32_t(data_ps(2)) << 16) | (last_fetch_addr_ & 0xFFFFu);
    acc.ube_n = 1;
    acc.segc = 2;
    acc.data = uint16_t(last_fetch_addr_ & 0xFFFF);
    acc.upc = upc;
    acc.is_halt = true;
    halt_acc_ = acc;
    halt_pending_ = true;
    halted_ = true;
}

}  // namespace sim
