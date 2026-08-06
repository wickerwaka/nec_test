// biu_timed.cpp -- see biu_timed.h.

#include "biu_timed.h"

#include "state.h"

#include <cstdio>
#include <cstdlib>

namespace sim {
// U2 pass-3 C3 diagnostic; defined in exec.cpp, also declared in exec_impl.h.
extern int g_rddone_max;
bool qdepth_trace();
}  // namespace sim

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
    pf_infl_to_ = -2;
    pf_infl_n_ = 0;
    pf_owed_ = false;           // M19
    ie_rise_ = -1;              // SM3 s11: no IE rise has happened yet
    brk_rise_ = -1;             // §84: nor a BRK rise
    brk_prev_ = false;
    ie_prev_ = false;
    cmt_expire_ = -1;           // M22
    cmt_was_owed_ = false;
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

// M22 -- AN ANNOUNCEMENT EXPIRES.  The status register is written by the
// arbiter at the GRANT and it lets go again at the announced cycle's own
// release index, counted from the T1 the grant reserved.  A cycle that never
// OPENS a T1 never latches a wait count (M2r: "the rig latches this access's
// wait count at T1 ENTRY"), so its release falls at the ZERO-WAIT index --
// three clocks after the display -- and it may not be given up before the
// clock the bus it is waiting for finishes on.  If the bus has not taken the
// cycle by then the announcement is simply GONE: the pins go passive for that
// clock and the arbiter chooses again at its end.
//
//     cmt_expire_ = max(cmt_disp_ + 3, cmt_t1_ - 1)
//     the cycle RUNS iff its T1 opens STRICTLY BEFORE that clock
//
// For every ordinary grant `cmt_t1_ == cmt_disp_ + 1` and the expiry is three
// clocks in the future, so nothing changes; the rule can only bite where the
// display and the T1 are separated, which is the woken HALT (M21's idle evals
// run while the HALT pseudo-cycle still owns the bus) and nowhere else in the
// corpus.
//
// MEASURED on the four-wait-level HLT sweep, 16 band cells, zero exceptions:
// the chip DISPLAYS the woken prefetch at `D = max(A + 4, H + 3)` and then
// drops it for the acknowledge in every cell where `F - D >= 3` (`F` = the
// clock the HALT pseudo-cycle frees the bus), runs it in every cell where
// `F - D <= 2`, and the passive clock it drops on is `max(D + 3, F - 1)`.
// w0 has NO withdrawal at any delay, and that is the same rule: at w0
// `D >= H + 3` and `F = H + 5`, so `F - D <= 2` always.
//
// AND IT UNDOES THE GRANT.  M19's request is "consumed by the GRANT"; an
// announcement that expires was never taken, so the fetch pointer rewinds and
// `pf_owed_` goes back to what it was -- the same sentence `withdraw_fetch`
// makes, now made at the other end of the display.
void BiuTimed::expire_cmt() {
    if (!cmt_valid_ || cmt_t1_ < cmt_expire_ || clk_ < cmt_expire_) return;
    cmt_valid_ = false;
    if (cmt_.is_fetch) {
        fetch_ptr_ = cmt_prev_fp_;
        pf_owed_ = cmt_was_owed_;   // the arbiter never took the request
    } else {
        req_.push_front(cmt_);      // an EU access is not the BIU's to lose
    }
}

// SM3 sitting 11 -- THE IE RISING EDGE.  `psw_` is the live architectural PSW
// the EU commits into (it is already read for the PS lanes, `data_ps` above),
// so the instant this records IS the EU's own kFlagIE commit edge -- I1/F39's
// early commit at the read latch's close of a POP included, with no second
// opinion about when that happens.  One sample, one comparison.
//
// It is sampled from `tick()` AND from the top of `boundary_no_pop()`, because
// a recognition boundary is asked for ON a clock whose tick has not run yet:
// without the second call the rise that happens on the boundary's own clock is
// stamped one clock late and the floor it owes is never paid.
void BiuTimed::sample_ie() {
    const bool ie = psw_ && (*psw_ & kFlagIE);
    if (ie && !ie_prev_) ie_rise_ = clk_;
    const bool brk = psw_ && (*psw_ & kFlagBRK);
    if (brk && !brk_prev_) brk_rise_ = clk_;
    brk_prev_ = brk;
    static const bool kIeTrace = std::getenv("V30SIM_IETRACE") != nullptr;
    if (kIeTrace && ie != ie_prev_)
        std::fprintf(stderr, "IE clk=%ld -> %d\n", clk_, int(ie));
    ie_prev_ = ie;
}

void BiuTimed::tick() {
    long c = clk_;
    sample_ie();
    // M22: the announcement expires before anything else this clock -- in
    // particular before the T1 it can no longer open (the two coincide when
    // `cmt_t1_ == cmt_disp_ + 3`, and the expiry wins).
    expire_cmt();
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
        rd_stamped_ = false;      // F57: one stamp per cycle
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
        // M22 (second consequence) -- AT ZERO WAITS THE EVAL INSTANT IS COUNTED FROM THE
        // DISPLAY, NOT FROM THE T1.  M2r says the eval rides the READY
        // sample; at N = 0 the rig's READY is high unconditionally (nec_bus.sv
        // `ready_q <= cfg_wait_states == 0`), so nothing the T1 latches can
        // move it and the instant is the part's own, counted from the clock
        // the status register was LOADED.  At N > 0 READY goes low and the
        // wait counter -- loaded at T1 ENTRY -- is what stretches the cycle,
        // so the instant rides the T1 (`last_i`), unchanged.
        //
        // For every cycle whose T1 opens the clock after its display the two
        // readings are the SAME CLOCK (`disp + 3 == T1 + 2`), which is why the
        // whole w0 corpus cannot tell them apart; they separate only where the
        // bus made the T1 wait, and M22 says that is the woken HALT and
        // nothing else.  MEASURED: `HLT.INT` w0 `A - H = -2` and `-1`, where
        // the chip's woken fetch opens T1 at `disp + 2` and releases its
        // status at `disp + 3` = T1 + 1 (the model released at T1 + 2 and put
        // the whole acknowledge chain one clock late -- 141 row diffs a cell).
        cur_.eval_i = cur_.is_halt ? 1
                      : (cur_.waits == 0)
                            ? int(cur_.disp + 3 - c > 1 ? cur_.disp + 3 - c : 1)
                            : cur_.last_i;
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
        cmt_.disp = c;                                        // M22
        cmt_t1_ = c + 1;
        cmt_expire_ = c + 3;        // M22 (never reached: T1 is at c + 1)
        cmt_was_owed_ = pf_owed_;
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
        // I1 / F39 -- THE FLAG REGISTER IS FED BY THE DATA LATCH, NOT BY THE
        // ROW.  This clock IS the T3/Tw -> T4 advance of a completing EU read,
        // which is the READY sample and the instant the AD input latch closes.
        // If an `OPR -> FLAGS ... F` row is STANDING (arm_flags_latch), its
        // destination is already selected and takes the word here -- before
        // this same clock's `r.ps` is composed, which is the whole observable
        // consequence and the reason silicon shows it: `interrupt_model.md`,
        // "the new IE shows in the PS bits during the read's own T4".
        // Everything else the EU does with the word still waits for the
        // handover at e+2 (`rd_done_q_`); this moves the COMMIT, not the data.
        if (flags_latch_ && ci_ == last_i && cur_.rd_last && !cur_.is_fetch &&
            !cur_.is_halt && !is_write(cur_.bs))
            *flags_latch_ = uint16_t((cur_.rd_val & kPswWritable) | kPswForced);
        r.tstate = (ci_ == 0)          ? uint8_t(kT1)
                   : (ci_ == 1)        ? uint8_t(kT2)
                   : (ci_ == 2)        ? uint8_t(kT3)
                   : (ci_ < last_i)    ? uint8_t(kTw)
                                       : uint8_t(kT4);
        r.bs = (ci_ >= eval_i) ? uint8_t(kBsPasv) : cur_.bs;
        // F53b -- UBE IS LOADED BY THE ADDRESS PHASE AND THEN HELD.  It is not
        // re-driven by a cycle that is merely RUNNING.  This used to read
        // `r.ube_n = cur_.ube_n` unconditionally, which is invisible for an
        // ordinary cycle (the value it re-drives is the one its own T1 latched)
        // and WRONG the moment an announcement that has already put its own UBE
        // on the pin is WITHDRAWN: the pads keep the withdrawn cycle's UBE and
        // the running cycle painted its own back over it.  `v30u_biu.sv`'s
        // `ube_n` middle term, in the model's idiom -- the ucore's is
        // `(r_run && r_ts == TS_T1) ? r_cur_ube_n : last_ube`.
        // Falsifier: a capture in which UBE changes on a clock that is neither
        // a display at `cdage != 0` nor a T1.
        r.ube_n = (ci_ == 0) ? cur_.ube_n : last_ube_;
        if (ci_ == 0) {
            // The address-phase (mid-cycle) sample is the address; the
            // end-of-cycle sample is the address too, EXCEPT on a write, where
            // the CPU has already switched AD to the write data by the end of
            // T1 (MEASURED: 88 case 0 row 15).
            r.ad_addr = cur_.addr;
            r.ad_data = is_write(cur_.bs) ? cur_.data
                                          : uint16_t(cur_.addr & 0xFFFF);
            r.ps = uint8_t((cur_.addr >> 16) & 0xF);
            // M23 -- ...but A19-A16 is a SHARED pad group, and the address
            // one-shot that owns it is fired by the DISPLAY, not by the T1
            // (see the display block below).  For every cycle whose T1 opens
            // the clock after its display -- which is every cycle in the
            // ordinary corpus -- `c == cur_.disp + 1` and this is dead code.
            // Where the bus made the T1 wait, the one-shot has already
            // expired and the upper nibble is back on the segment status
            // while A15-A0 still holds the address by pad retention.
            if (cur_.disp >= 0 && c != cur_.disp + 1)
                r.ad_addr = (uint32_t(data_ps(cur_.segc)) << 16) |
                            (cur_.addr & 0xFFFFu);
        } else if (!cur_.is_halt) {
            r.ad_addr = cur_.addr;
            r.ad_data = cur_.data;
            r.ps = data_ps(cur_.segc);
        } else {
            // F51 -- THE HALT PSEUDO-CYCLE HAS NO DATA PHASE, so after its own
            // address phase it drives NOTHING and the pads hold.  Every other
            // cycle hands AD over at the end of T1 -- to the write data, or to
            // the memory -- and a HALT hands it to nobody.  This branch used to
            // republish `cur_.addr` / `cur_.data` / `data_ps(segc)` on every
            // clock of the pseudo-cycle's body, which is the SAME VALUE its own
            // T1 put there unless something else took the pads in between, and
            // the only thing that can is a multi-clock ANNOUNCEMENT that is
            // then WITHDRAWN (`v30u_biu.sv` F53, `tb_v30_core.sv`'s `cycle_live`
            // -- a HALT-typed cycle is excluded from `core_ps_drive`, and in
            // fabric the pads themselves do this).  MEASURED on
            // `s13-hltsweep-w2 HLT.INT idx 10/11` row 12 and `-w3 idx 12/13/14`
            // row 14: the chip holds the withdrawn wake fetch's `067CB4` /
            // `7CB4` / `ube 0` and the model reverted to the HALT's `067CB2` /
            // `7CB2` / `ube 1`, which an INTA then froze into its own access
            // (line 357) and carried two rows further.
            r.ad_addr = last_addr_;
            r.ad_data = last_data_;
            r.ps = last_ps_;
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
        // ...but UBE is NOT part of that register.  It changes ONE CLOCK AFTER
        // the status does.  MEASURED: `E8` case 0 golden rows 14-15 (the split
        // push's second half is displayed with the first half's UBE and only
        // asserts its own a clock later) and rows 18-19 (the redirect fetch is
        // displayed with the write's UBE).  Every CODE cycle drives UBE low,
        // which is why this is invisible until an EU access sits next to a
        // fetch.
        //
        // M23 -- THE ADDRESS ONE-SHOT IS FIRED BY THE DISPLAY, NOT BY THE T1.
        // The clock that loads the status register also starts the address
        // phase, and the address phase is ONE CLOCK LONG: on `disp + 1` the
        // part drives the announced cycle's A19-A0 and its UBE, and from
        // `disp + 2` A19-A16 is back on the segment status while A15-A0 holds
        // the address by pad retention.  For an ordinary cycle `disp + 1` IS
        // the T1 and the whole rule collapses to "address at T1", which is
        // what the 168,997 w0 goldens say and why they cannot see it.
        //
        // MEASURED (sw/s16_dispwin.py, banked captures only, no board):
        // exactly 42 display windows longer than one clock exist in the whole
        // banked corpus -- 30 in the four HLT delay sweeps and 12 in the
        // 3,242-seed fuzz bank -- against 1,231,445 one-clock windows there
        // and 1,396,331 one-clock windows and NOT ONE longer in every
        // committed golden suite.  In all 42 the nibble on `disp + 1` differs
        // from the cycle's own segment status; in the 22 that reach a T1 the
        // T1 nibble IS that status, 22/22, and never the `disp + 1` one,
        // 0/22; the low 16 bits are the same address on both clocks, 22/22;
        // and UBE at `disp + 1` is the value the T1 carries, 22/22.
        // The `HLT.RES` sweep breaks 25.6's confound by itself: its injected
        // CS:IP puts the woken fetch at 0x9AD8x, so the nibble on `disp + 1`
        // is 9 -- PS3 set, the 8080 emulation-mode bit -- in a capture whose
        // every genuine status sample reads 1, 2 or 3.  No status code can be
        // 9 there, so the nibble names itself as the address.
        //
        // `r.ps` is the END-of-clock sample, i.e. the pin during clock c + 1:
        // on the display clock that is `disp + 1` (the address), and on any
        // later announcement clock it is `disp + 2` or beyond (the status).
        if (c != cmt_disp_) {
            r.ps = data_ps(cmt_.segc);
            r.ube_n = cmt_.ube_n;
        }
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
            // M21 (second half).  The index-2 sample belongs to the cycle that
            // is FINISHING, and the HALT pseudo-cycle's eval sits at index 1 --
            // BEFORE its own index 2 exists.  It therefore has no latch to
            // apply, and applying the LAST cycle's (taken while the part was
            // still running, i.e. before the HLT decode ever set `halted_`) is
            // reading a decision about a machine state that is gone.  The
            // HALT's eval is an ORDINARY IDLE EVAL -- it reads the queue and
            // `halted_` LIVE -- which is exactly what M21 already says of
            // every clock AFTER it.  MEASURED: with the latch applied the
            // woken prefetch's display is one clock late at `A - H = -1` and
            // absent at `-2`, at all four wait levels; without it
            // `D = max(A + 4, H + 3)` is exact at every delay.
            pf_arm_valid_ = !cur_.is_halt;
            // F57 -- A READ'S COMPLETION CLOCK IS STAMPED AT THE CYCLE'S OWN
            // EVAL.  The VALUE is unchanged (`e + 2`, and at this clock `c`
            // IS `e` by definition); what moves is the clock the EU can first
            // SEE it on.  `wait_next_read()` blocks in two stages -- until a
            // stamp EXISTS, then until the clock it names -- and pushing at
            // T4 made the first stage bind whenever the eval and T4 are more
            // than one clock apart, i.e. whenever the cycle's DISPLAY WAITED
            // for the bus.  Then the model could not leave before T4 + 1 even
            // though it had itself computed `e + 2` as the answer.
            //
            // MEASURED, `s10-hltsweep-w0 HLT.INT`: silicon's second
            // acknowledge is `display + 7` at every delay; the model's was
            // `T1 + 6`, which is the same number for every cycle whose T1
            // opens the clock after its display and one clock late for the
            // acknowledge that follows a woken HALT -- the only place in the
            // corpus where a T1 waits.  It is M22's `cmt_expire_` sentence one
            // mechanism over.
            //
            // W0-NEUTRAL BY CONSTRUCTION for every ordinary cycle: the second
            // stage (`clk_ < e + 2`) is untouched, so the EU still leaves at
            // `e + 2`.  Under waits `eval_i == last_i` and the two sites are
            // the SAME CLOCK.  FALSIFIER: any cell whose EU leaves the wait at
            // a clock other than `e + 2`.
            if (!cur_.is_fetch && !cur_.is_halt && cur_.rd_last &&
                !is_write(cur_.bs) && rd_pending_) {
                rd_done_q_.push_back(c + 2);
                last_wval_ = cur_.rd_val;    // the read lands in OPR
                rd_stamped_ = true;
                if (int(rd_done_q_.size()) > g_rddone_max) {
                    g_rddone_max = int(rd_done_q_.size());
                    if (qdepth_trace())
                        std::fprintf(stderr,
                                     "QD rd_done=%d upc=%04X clk=%ld\n",
                                     g_rddone_max, cur_.upc, clk_);
                }
            }
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
        // M21 -- THE HALT PSEUDO-CYCLE HOLDS THE BUS ONLY UNTIL ITS STATUS
        // RELEASE.  20.5 already measured that the HALT is the one access
        // whose eval (index 1, the status release) and whose T4 (index 3) are
        // different clocks.  This is the other half of that sentence: from the
        // release on there is no bus cycle left to arbitrate, so EVERY clock is
        // an ordinary idle eval, exactly as it is when the bus is parked.  For
        // a HALT that is never woken this changes nothing -- the live read at
        // an idle eval sees `halted_` and refuses (the 600 w0 HALT goldens are
        // byte-identical) -- and for a woken one it is what lets the restart be
        // granted at max(A + 3, the HALT's own eval), which is the MEASURED law
        // of the S2 sweep: the woken fetch's DISPLAY = max(A + 4, H + 3) at
        // both wait levels and both forms.
        if (cur_.is_halt && ci_ > cur_.eval_i) eval_here = true;
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
                // F57: the stamp is made at the EVAL (above).  This arm is
                // the one that runs when the eval never fired for this cycle;
                // `rd_stamped_` is what keeps them from both firing when
                // `eval_i == last_i`, which is every waited cycle.
                if (cur_.rd_last && !is_write(cur_.bs) && !rd_stamped_) {
                    rd_done_q_.push_back(e + 2);
                    last_wval_ = cur_.rd_val;    // the read lands in OPR
                    // U2 pass-3, C3: the completion deque's PROVEN depth.
                    if (int(rd_done_q_.size()) > g_rddone_max) {
                        g_rddone_max = int(rd_done_q_.size());
                        if (qdepth_trace())
                            std::fprintf(stderr,
                                         "QD rd_done=%d upc=%04X clk=%ld\n",
                                         g_rddone_max, cur_.upc, clk_);
                    }
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
            "cur=%d ci=%d nw=%d old=%ld new=%ld fp=%u\n",
            clk_ - 1, decision, why, int(q_.size()), occupancy(), int(req_.size()),
            int(suspended_), int(halted_), int(run_),
            run_ ? int(cur_.bs) : -1, run_ ? ci_ : -1, run_ ? cur_.waits : -1,
            oldest, newest, unsigned(fetch_ptr_));
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
        cmt_.disp = clk_;                                     // M22
        cmt_t1_ = free_clk > clk_ + 1 ? free_clk : clk_ + 1;
        // M10: the slot's occupant now has the T1 that frees it -- the LAST
        // cycle of the access -- so a row blocked on it knows the clock it may
        // issue on.  While a split's first half is committed the accept clock
        // stays unknown (-1) and the blocked row keeps waiting.
        if (cmt_.rd_last) eu_accept_clk_ = cmt_t1_;
        cmt_was_owed_ = pf_owed_;                             // M22
        cmt_expire_ = (cmt_disp_ + 3 > cmt_t1_ - 1) ? cmt_disp_ + 3
                                                    : cmt_t1_ - 1;
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
    et('F', '-');
    cmt_was_owed_ = pf_owed_;   // M22: ...and gives it back if it expires
    pf_owed_ = false;      // M19: the arbiter has taken the request
    cmt_ = make_fetch();
    // The fetch pointer advances when the cycle is COMMITTED, not when its
    // data lands: the address is latched into the bus cycle here.
    cmt_prev_fp_ = fetch_ptr_;
    last_fetch_addr_ = cmt_.addr;
    fetch_ptr_ = uint16_t(fetch_ptr_ + cmt_.push_n);
    cmt_valid_ = true;
    cmt_disp_ = clk_;
    cmt_.disp = clk_;                                         // M22
    cmt_t1_ = free_clk > clk_ + 1 ? free_clk : clk_ + 1;
    cmt_expire_ = (cmt_disp_ + 3 > cmt_t1_ - 1) ? cmt_disp_ + 3
                                                : cmt_t1_ - 1;
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
        // M22/22.10: a grant that is TAKEN BACK did not consume the request.
        // M19 says the request is "consumed by the GRANT"; un-granting must
        // un-consume it, and that is 22.10 item 1's edge answered in the only
        // way that keeps M19 one sentence.
        pf_owed_ = cmt_was_owed_;
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
    // H1: the floor is NOT read here.  It is a RECOGNITION-edge instant
    // (S9a already separates the recognition boundary from the pop deadline),
    // and the byte pipeline has its own: after a redirect the successor's pop
    // is byte-limited at the refilling fetch's eval + 3, which is index 5 at
    // w0 and later under waits -- strictly after the floor at index 2, so the
    // floor could never be the binding term.  Charging the EU to it anyway
    // (tried, and MEASURED) costs `INT.F3AA` 75 of 200 w0 cases and 18 of 200
    // at w1, because the REP-withdrawal path flushes and then SUSPENDS, so its
    // restart is the one that does NOT come at once (M19 / sec.21.3).
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
long BiuTimed::boundary_no_pop(bool post_redirect) {
    if (opc_valid_) return clk_;   // already latched: this IS the pop clock
    wait_bus();
    // SM3 SITTING 11 -- THE FLOOR IS THE IE RESTORE, AND IT IS THE EDGE ALONE.
    // A MASKABLE recognition may not act until two clocks after PSW.IE's
    // rising edge.  A NON-MASKABLE one bypasses BY CONSTRUCTION -- it does not
    // read the stamp -- and there is no exemption clause anywhere.
    //
    // `post_redirect` is FALSE for the REP mid-string withdrawal, which is not
    // an instruction retire at all: its recognition was taken inside the loop
    // (sec.19.8.1) and the ROM's own REPX path does the flush AFTER the
    // decision, so there is no boundary for the reload to hold off.  MEASURED:
    // flooring it too costs `INT.F3AA` 26 of 200 at w0 and 0 elsewhere.
    //
    // The rise is sampled HERE as well as in `tick()`: the boundary is asked
    // for on a clock whose tick has not run yet, and the rise this floor is
    // about happens on exactly that clock (the IRET's PSW restore commits at
    // its own retire).
    sample_ie();
    // DIAGNOSTIC (env-gated, `V30SIM_BNDTRACE=1`).  One line per recognition
    // boundary: the clock, the pin, the last IE rise and whether the floor is
    // LIVE.  It reads no state the block below does not.
    static const bool kBndTrace = std::getenv("V30SIM_BNDTRACE") != nullptr;
    const bool live = maskable() && ie_rise_ >= 0 && clk_ < ie_rise_ + kIeFloor;
    if (kBndTrace)
        fprintf(stderr, "BND clk=%ld post=%d pin=%d ierise=%ld floor=%ld "
                        "live=%d\n",
                clk_, int(post_redirect), ev_pin_, ie_rise_,
                ie_rise_ >= 0 ? ie_rise_ + kIeFloor : -1, int(live));
    if (post_redirect && live) {
        wait_ie_floor();
        // ...and the recognition that PAYS the floor also holds the
        // prefetcher off: the chip grants the slot between the floor and the
        // acknowledge's own request to NOTHING (the census's two idle clocks).
        susp();
    }
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

// wrfuzz W3.4 -- THE RETIRE LEAD LEADS THE SUCCESSOR'S *POP*, AND A BOUNDARY
// THAT FIRES CANCELS THAT POP.
//
// The wait itself is a MEASURED law and it is NOT removed: `loader_impl.h`'s
// own comment above the call carries the golden, 250/250 on each half --
//     even `ip`  the successor's byte is already in the queue, its pop is at
//                pop+2, and the golden shows the new IE at pop+1
//     odd  `ip`  a single upper-lane byte, so the successor's pop waits for
//                the next fetch's T4+2, and the golden still shows the OLD IE
// -- and W3.4 CONFIRMED that by falsifying its own first candidate: deleting
// the `q_.empty()` disjunct moved `FA` (74), `FB` (68) and `INT.FB` (39),
// 181 row-diffs on `v0.1` where the registered ladder is 0.  The flag write's
// commit clock really does wait for the byte to ARRIVE.
//
// What does NOT wait is the RECOGNITION BOUNDARY.  That is the law
// `boundary_no_pop()` already states and `v30u_eu.sv`'s boundary block already
// quotes -- *"the recognition decision does not need the byte (it is the
// decision NOT to take one), so a recognised boundary does not slide when the
// queue is dry"*, measured there as `INT.90` 200/200 with the retire deadline
// against 177 with the pop deadline.  The ROM path got that treatment; the
// ONE_BYTE_LOGIC path never did, because on it the two rode one call.
//
// So the two are separated by the one condition that distinguishes them: when
// the BRK/TF arm is set, this instruction retires INTO the trap and its
// successor is never popped.  There is no pop to lead.
//
// MEASURED, `wrfuzz_provenance.md` §7 -- 23 `wr1` seeds, chip-side, no engine
// in the loop: the trapping instruction is `FC` x18 / `FD` x4 / `F8` x1, ONE
// BYTE LOGIC 23/23; its fetch address is ODD 23/23, so the redirect's refill
// delivered a single byte and the queue is DRY at the retire; the chip's take
// is its own opcode pop + 2 on 23/23, WAIT-INDEPENDENT (cycle lengths 5, 6, 7);
// and the engine's take was late by exactly `delta` on 23/23, which is the
// whole of the class.  The extra `CODE` fetch W3.2 chased is a CONSEQUENCE of
// the late take, not a grant defect.
//
// *Falsifier*: any capture in which a ONE_BYTE_LOGIC form retiring into a
// BRK/TF take has its boundary later than its own opcode pop + 2 with a dry
// queue; or any `FA`/`FB` golden that moves when this gate is armed.
void BiuTimed::wait_retire_lead() {
    if (brk_pending_) return;
    int guard = 0;
    while ((q_.empty() || q_.front().ready > clk_ + 1) && ++guard < 4096) tick();
}

// SM3 sitting 11 -- THE RECOGNITION FLOOR IS THE IE RESTORE.  A maskable
// recognition may not act until TWO CLOCKS after PSW.IE's rising edge.  There
// is no arm, no stamp and no spend: the edge is the whole mechanism.
void BiuTimed::wait_ie_floor() {
    int guard = 0;
    while (clk_ < ie_rise_ + kIeFloor && ++guard < 32) tick();
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
