// biu_timed.h -- the TIMED bus-interface unit: same Bus concept as sim::Biu,
// but it owns the CPU CLOCK and emits one ClockRow per clock.
//
// STATUS AT T1 (ucsim-t): the BIU is the master clock and the EU is a CLIENT.
// The interpreter pumps clocks through `charge()` (micro-row cadence),
// `next_byte()` (a queue pop is a POINT SAMPLE riding an existing clock, not a
// clock of its own) and `wait_read()` (the F/OPR interlock).  Everything the
// bus does -- the T-state FSM, the completion eval, the prefetch scheduler, the
// queue push/pop latency pipeline -- happens inside `tick()`.
//
// Composition, not inheritance: a functional `Biu core_` holds the 1 MB
// epoch-stamped memory, the transaction log, the write stream and the ordered
// bus-cycle counter, so the timed model never re-implements storage.
//
// --- THE MECHANISMS (all measured; provenance in ucsim_t_provenance.md) ------
//
// M1 GRID / COMPLETION EVAL.  A bus cycle is T1 T2 T3 (Tw x N) T4.  The next
//    cycle is chosen at a completion eval; the winner's status and address are
//    driven on the clock AFTER the eval (the DISPLAY clock) and its T1 opens
//    the clock after that.  Eval points: the T3->T4 edge of a zero-wait cycle,
//    the T4 edge of a waited one, and the end of every idle clock.  T4 of a
//    zero-wait cycle is NOT an eval point.  (biu_model.md "Consolidated
//    bus-grid law" 3; mission-H deferral.)
//
// M2 STATUS IS A REGISTERED OUTPUT.  It is loaded at the eval and RELEASED one
//    clock before the next display clock, so exactly one PASV clock separates
//    two cycles' status.  At w0 that release lands on T3, at w>0 on T4 -- the
//    "w==0?2:3+w" conditional the T0 ledger flagged is not a property of the
//    part, it is the eval geometry (M1) seen through one register.
//
// M3 QUEUE.  6 bytes; word fetch at an even address (+2), single upper-lane
//    byte at an odd one (+1).  A fetch is issued at any eval where the
//    occupancy INCLUDING in-flight bytes is <= 4 (refill threshold = 2 bytes
//    free).  A completed fetch pushes at the end of its T4 and the pushed byte
//    is POPPABLE two clocks later.  (biu_model.md exp1 + grid law 2.)
//
// M4 ARBITRATION.  An EU access never preempts an in-flight cycle; it wins the
//    next eval.  The second half of a split (unaligned) word access has top
//    priority.  (grid law 4; law card #12 want_half2.)
//
// M2r THE READY SAMPLE IS THE ONLY WAIT-STATE MECHANISM, and it is ONE INSTANT.
//    The rig (hdl/rtl/nec_bus.sv) loads its wait counter at T1 entry and drives
//    READY so that the line is HIGH for exactly the clocks from which the
//    T-state machine may advance to T4:
//
//        N = 0   READY high from T2  (`ready_q <= cfg_wait_states == 0`)
//        N > 0   READY high from the LAST Tw (`ready_q <= wait_cnt == 1`,
//                decremented once per clock while t_state is T3/Tw)
//
//    The CPU registers that line at the end of every clock, and ONE CLOCK LATER
//    it does two things at once: it RELEASES the status register (that clock
//    displays PASV) and it runs the COMPLETION EVAL at the clock's end.  So the
//    eval instant `e` sits at cycle-relative index
//
//        e_i = (N == 0) ? 2 : 3 + N          (T3 at zero waits, T4 otherwise)
//
//    and EVERY other quantity in the model is a fixed offset from `e`:
//
//        e     status goes passive; OPR is released to a `-> OPR` row
//        e+1   the DISPLAY clock: the winner's status / address / PS
//        e+2   the winner's T1; eu_done (read handover, store retire)
//        e+3   a fetched byte becomes POPPABLE
//
//    At w0 that reads T3 / T4 / T4+1 / T4+2 -- the zero-wait numbers of T1
//    (M1, M2, M3) unchanged.  At w>0 it reads T4 / T4+1 / T4+2 / T4+3, which is
//    mission-H's "completion-eval deferral" plus "the push lands one cycle
//    after the eval, poppable two after" plus "post-access EU schedules stretch
//    by exactly one cycle per waited access" -- three fitted laws that are the
//    SAME OFFSET seen from three places.  The `w == 0 ? 2 : 3+w` shape lives in
//    the RIG's counter, not in the part: the CPU only ever waits one clock
//    after a level.  (Derived from nec_bus.sv; biu_model.md mission H.)

#ifndef BIU_TIMED_H
#define BIU_TIMED_H

#include <cstdint>
#include <deque>
#include <utility>
#include <vector>

#include "biu.h"
#include "rows.h"

namespace sim {

class BiuTimed {
public:
    BiuTimed() = default;

    // --- timed-mode configuration ----------------------------------------
    void set_emitter(RowEmitter* e) { rows_ = e; }
    // --- the three wait sources, in the rig's own priority order ----------
    // (nec_bus.sv, the `next_t_state == ST_T1` block: replay > random >
    // uniform, all keyed on `bus_idx`, which counts EVERY bus cycle from the
    // run's start.)  The count is latched at T1 ENTRY, so it belongs to the
    // order the cycles RUN in, not to the order the EU requested them.
    void set_waits(int w) { waits_ = w < 0 ? 0 : w; }
    // Explicit per-access vector: access k takes wvec[k] waits (0..31), and
    // the uniform setting takes over past its end.
    void set_wvec(const std::vector<uint8_t>& v) { wvec_ = v; }
    // The seeded random-wait rig: 16-bit Galois LFSR, poly 0xB400, seeded at
    // reset (0 -> 0xACE1), advanced EXACTLY ONCE per bus cycle at T1 entry,
    // count = (lfsr[7:0] * (wmax+1)) >> 8.  (docs/notes/random_wait_rig.md.)
    void set_wrand(bool on, int wmax, uint16_t seed) {
        wrand_ = on;
        wmax_ = wmax < 0 ? 0 : wmax;
        wseed_ = seed ? seed : uint16_t(0xACE1);
    }
    long bus_idx() const { return bus_idx_; }
    // S5 on the status lines is the IE flag, so the row emitter needs a live
    // view of the PSW.  Bound to the interpreter's own machine state.
    void bind_psw(const uint16_t* psw) { psw_ = psw; }
    // M9: PS3 is the EMULATION-MODE bit.  See data_ps() in biu_timed.cpp.
    void bind_md(const bool* md8080) { md8080_ = md8080; }
    long clock() const { return clk_; }

    // --- case lifecycle ---------------------------------------------------
    void begin_case();
    void end_case();

    // --- the Bus concept (consumed by CpuT<Bus> and loader_decode<Bus>) ----
    // M8 (T4).  EVERY byte requester -- decoder or micro-row -- takes its byte
    // on the first clock at or after BOTH its own demand clock and the byte's
    // ready clock:
    //
    //     pop = max(demand, ready + pen)
    //
    // There is no re-run and no stride (M3c is RETRACTED, see biu_timed.cpp).
    // `pen` is 1 for exactly one requester: the byte that COMPLETES a
    // displacement (a disp8, or the HIGH byte of a disp16), which is taken one
    // clock after it is poppable.
    uint8_t next_byte(uint16_t cs, uint16_t upc) { return pop(cs, upc, false); }
    uint8_t decode_byte(uint16_t cs, uint16_t upc) { return pop(cs, upc, false); }
    uint8_t disp_byte(uint16_t cs, uint16_t upc) { return pop(cs, upc, true); }
    uint16_t mem_read(uint16_t seg_val, uint16_t off, bool word,
                      uint8_t seg_idx, uint16_t upc);
    void mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word,
                   uint8_t seg_idx, uint16_t upc);
    // S5 RETIRED.  The write CYCLE is scheduled by the BIU at the eval that
    // follows the ROM row which ISSUES it -- not at the moment the EU pairs
    // the data.  `write_request` posts the (possibly split) cycle with its
    // address and status; the data-pairing latch fills it in later, before the
    // T1 that drives it.  MEASURED: `A4` (MOVSB) puts the store's status on
    // the load's T4 and its T1 on the very next clock, which is the eval at
    // the end of the load's T3 granting a request whose DATA does not exist
    // yet.  A no-op on the functional bus.
    void write_request(uint16_t seg_val, uint16_t off, bool word,
                       uint8_t seg_idx, bool io, uint16_t upc);
    uint16_t io_read(uint16_t port, bool word, uint16_t upc);
    void io_write(uint16_t port, uint16_t data, bool word, uint16_t upc);
    uint16_t inta_read(uint16_t upc);
    void note_halt(uint16_t upc);
    // S8/S9: run one clock with no EU behind it (the parked, halted bus).
    void tick_idle() { tick(); }
    // F2 SUSP IS ONE CLOCK EARLY.  The ROM's bus-control field is decoded a
    // row ahead of the datapath, so SUSP reaches the BIU on the same clock
    // edge that loads the prefetch COMMIT register -- and a fetch the eval
    // just chose therefore does not survive.  This is the mechanism behind
    // the measured "reservation starts at the final-pop cycle" (biu_model.md:
    // EB reserves at its last-disp pop, E9 at pop+1) even though EB's SUSP row
    // 0159 runs one clock after that pop, and behind the loop family's
    // "dly<=3 blocked / dly>=4 free" cutoff (SUSP three rows before FLUSH).
    void susp();
    void resume() { suspended_ = false; }
    void withdraw_fetch();
    void flush(uint16_t cs, uint16_t pc);
    void clear_consumed();
    long ev_count() const { return core_.ev_count(); }

    // --- the TIMED extensions to the Bus concept --------------------------
    // (all no-ops on the functional sim::Biu, which has no clock)

    // The EU burns `n` clocks of micro-row cadence.
    void charge(int n) { for (int i = 0; i < n; ++i) tick(); }
    // The F / OPR bus interlock: block until the outstanding EU access has
    // completed and its data handed over (eu_done = T4 + 1 at zero waits).
    void wait_read();
    void wait_next_read(int extra);
    void wait_opr_free();
    void wait_bus();
    // The clock before the queue's next byte can be popped.  A pre-decode-
    // executed form's execute strobe sits there -- see loader_impl.h,
    // ONE_BYTE_LOGIC.
    void wait_retire_lead();
    // The PRE-DECODE operand read.  Its data is not consumed by an F-flagged
    // micro-row -- it is consumed by micro-row 0 itself -- and the decoder
    // spends one clock handing the sequencer over, exactly as it does on the
    // saturated-queue schedule (7.6: micro-row 0 lands at opcode+2, never
    // opcode+1).  So micro-row 0 opens at the read's T4 + 2, one clock after
    // the F/OPR interlock would release.  MEASURED over the whole v0.1 suite:
    // a WRITE-terminated instruction retires at its last T4 + 1 (52,752 cases,
    // no exceptions) while a PRE-READ-terminated one retires at T4 + 1 + (the
    // number of micro-rows that still have to run) -- 8A/8B/02/03/... 2 rows
    // -> +3 (9,043 cases), 84/85/8E/66/67/D8-DF 1 row -> +2, 0F10/0F11 3 rows
    // -> +4.  The row count is the cadence engine's; the +1 is this handover.
    void wait_opr();
    // The decoder pre-pops the next instruction's opcode.  Called on the E
    // (end-of-sequence) micro-row, which is the clock the chip pops it on --
    // two clocks before the successor's first micro-row.
    void opcode_prefetch(uint16_t cs);
    bool opcode_pending() const { return opc_valid_; }
    // A prefix retired: the NEXT pop is an F again (each prefix byte is its
    // own 2-clock instruction with its own F pop).
    void prefix_retire() { pop_is_first_ = true; }

    // --- queue ------------------------------------------------------------
    void queue_preload(const std::vector<uint8_t>& q, uint16_t cs,
                       uint16_t ip);
    size_t queue_len() const { return q_.size(); }
    uint8_t queue_at(size_t i) const { return q_[i].b; }
    uint16_t fetch_ptr() const { return fetch_ptr_; }
    const std::vector<uint8_t>& consumed() const { return consumed_; }

    // --- storage and replay inputs (delegated to the functional core) -----
    void poke(uint32_t a, uint8_t v) { core_.poke(a, v); }
    void set_fill(uint8_t v) { core_.set_fill(v); }
    uint8_t peek(uint32_t a) const { return core_.peek(a); }
    void set_mirror(bool on) { core_.set_mirror(on); }
    void set_io_in(uint16_t v) { core_.set_io_in(v); }
    void set_io_seq(const std::vector<uint16_t>& s) { core_.set_io_seq(s); }
    void set_inta(uint16_t v) { core_.set_inta(v); }
    const std::vector<Txn>& txns() const { return core_.txns(); }
    const std::vector<std::pair<uint32_t, uint8_t>>& writes() const {
        return core_.writes();
    }

private:
    struct Access {
        uint8_t bs = kBsPasv;
        uint32_t addr = 0;    // 20-bit
        uint16_t data = 0;    // the composed AD15-0 data phase
        uint8_t ube_n = 1;
        uint8_t segc = 2;     // S4:S3 code -- 0 ES, 1 SS, 2 CS/none, 3 DS
        uint16_t upc = 0xFFFF;
        bool is_fetch = false;
        // On a READ the CPU floats AD: the 16-bit MEMORY drives the whole
        // ALIGNED WORD and UBE/A0 only decide which half the CPU latches.  So
        // the data phase of any read -- byte, word, or either half of a split
        // -- is the aligned word at its address, and the "undriven lane
        // retains" reading of T0 2.6 was an alias of the 0x90 NOP fill.
        // MEASURED: `58` case 0 (split POP at an odd SP: the second half at an
        // EVEN address shows 9007, the aligned word, not the A2 the first half
        // just put on the high lane), `8A` case 0 row 10, `FE.0` case 0.
        bool sys_word = false;
        bool need_data = false;   // reserved by write_request, data not paired yet
        // A SPLIT access is ONE read to the EU: the F interlock releases on
        // the LAST of its two byte cycles.  (MEASURED: `8B` case 11, a word
        // load from an odd address, retires off the second half's T4.)
        bool rd_last = true;
        uint16_t rd_val = 0;   // a READ's datapath value -> OPR at its T4+1
        // S8/S9 -- THE HALT BUS PSEUDO-CYCLE.  MEASURED on the socket, T2b P3
        // (sw/testdata/t2b/p1-susp, the ENTER store stub's own HLT, w0/w1/w3 x
        // two preparation histories x 5 repetitions x 4 and 8 MHz):
        //   * the status register carries HALT for exactly TWO clocks -- the
        //     display clock and T1 -- and is PASSIVE from T2 on, at EVERY wait
        //     level.  So a HALT's status release index is 1, not the eval.
        //   * T1 drives UBE HIGH (no data phase) and puts the LAST FETCH's
        //     address on A15-0 with the segment code (2 = CS) on A19-16 -- it
        //     never does an address phase on the upper nibble.
        //   * the RIG still runs a full T-state cycle over it and DOES insert
        //     Tw (T1..T4 = 4/5/7 clocks at w0/w1/w3), so it consumes a wait
        //     draw and a bus-cycle ordinal like any other cycle.  (This
        //     FALSIFIES the pre-registered 12.0-P3 prediction 2, which said
        //     the pseudo-cycle would not stretch.)
        //   * the bus then PARKS: zero non-passive status rows afterwards.
        bool is_halt = false;
        uint8_t push_n = 0;    // queue bytes this fetch delivers
        uint8_t push_b[2] = {0, 0};
        // M2r: the wait count the rig latches at this cycle's T1 entry, and
        // the cycle-relative index of the completion eval it implies.
        int waits = 0;
        int eval_i = 2;
        int last_i = 3;
    };
    struct QByte {
        uint8_t b = 0;
        long ready = 0;   // first clock on which this byte may be popped
    };

    static uint32_t phys(uint16_t seg_val, uint16_t off) {
        return uint32_t((uint32_t(seg_val) << 4) + off) & 0xFFFFFu;
    }
    // sim::Sreg is ES,CS,SS,DS = 0,1,2,3; the S4:S3 pin code is
    // ES,SS,CS,DS = 0,1,2,3.  kSegZero (the internal INT routine's
    // segment-less vector fetch) and I/O both drive the "no segment" code,
    // which is the same encoding as CS.
    static uint8_t seg_code(uint8_t seg_idx);
    uint8_t data_ps(uint8_t segc) const;
    static bool is_write(uint8_t bs) { return bs == kBsMemW || bs == kBsIoW; }

    static uint16_t lane_data(uint16_t retained, uint32_t addr, bool word,
                              uint16_t value);
    uint16_t sys_word_at(uint32_t addr) const;

    // one CPU clock: emit this clock's row, advance the bus FSM, run the
    // completion eval if this clock ends on an eval point.
    void tick();
    void eval();
    void et(char decision, char why) const;   // T3 diagnostic (env-gated)
    void post(const Access& a);
    // occupancy including bytes already fetched but not yet pushed
    int occupancy() const;
    Access make_fetch() const;
    uint8_t pop(uint16_t cs, uint16_t upc, bool disp_last);

    // M2r: the rig's per-bus-cycle wait draw, latched at T1 entry.
    int next_waits();

    Biu core_;
    RowEmitter* rows_ = nullptr;
    const uint16_t* psw_ = nullptr;
    const bool* md8080_ = nullptr;
    int waits_ = 0;
    std::vector<uint8_t> wvec_;
    bool wrand_ = false;
    int wmax_ = 0;
    uint16_t wseed_ = 0xACE1;
    uint16_t wlfsr_ = 0xACE1;
    long bus_idx_ = 0;
    long clk_ = 0;

    // --- bus FSM ---
    bool run_ = false;      // a cycle is in progress
    Access cur_;
    int ci_ = 0;            // clock index within the running cycle (0 = T1)
    bool cmt_valid_ = false;
    Access cmt_;
    long cmt_t1_ = -1;      // absolute clock of the committed cycle's T1
    uint16_t cmt_prev_fp_ = 0;   // fetch_ptr before the committed fetch took it

    // retained pin state (idle rows and undriven byte lanes)
    uint32_t last_addr_ = 0;
    uint16_t last_data_ = 0;
    uint8_t last_ps_ = 0;
    uint8_t last_ube_ = 0;
    uint16_t last_dp_ = 0;   // last DATA-PHASE AD value (T1 excluded)

    // --- queue / prefetch ---
    std::deque<QByte> q_;
    uint16_t fetch_ptr_ = 0;
    uint16_t cs_ = 0;
    bool suspended_ = false;
    bool pop_is_first_ = true;
    std::vector<uint8_t> consumed_;
    // F1 (flush display).  The queue-clear event QS=E is a POINT SAMPLE on the
    // QS port, and the port can only carry one event per clock.  A flush
    // therefore parks here and is displayed on the first clock the port is
    // free: not while a doomed fetch is still running (it shows at that
    // fetch's T4), not on the clock a completed fetch's bytes are being
    // absorbed into the queue, and not on a clock that already carries a pop.
    // (biu_model.md, "QS=E pin display".)
    // F3 (flush-only eval point).  From the end of the flush onward the
    // redirected prefetch may also commit at the end of a PREFETCH cycle's T4
    // -- a point the grid does not otherwise evaluate at w0.  An EU access's
    // T4 is never an eval point, flush or not.  (biu_model.md, "Redirect
    // commit".)  Armed by flush(), spent by the first commit.
    bool flush_eval_ = false;
    // M2r: the clock an eval has reserved as its DISPLAY slot -- not an eval
    // point itself.
    long no_eval_ = -1;
    // M6 -- A FETCH'S BYTES ARE WRITTEN INTO THE QUEUE ON **T4+1**, AND THAT
    // CLOCK IS NOT A PREFETCH-GRANT POINT.  ONE clock, keyed to T4 and NOT to
    // the completion eval -- so, like the OPR release (11.4) and the F3AA
    // closing pop (T2b P4), it sits at a FIXED CYCLE-RELATIVE INDEX and does
    // not stretch.  The consequence is a single wait-independent number: the
    // earliest eval that may resume a prefetch after a pushing fetch is
    // **T4+2**, and that fetch's T1 opens at **T4+4**, at every wait level.
    //
    // MEASURED, T2b, three independent stimuli:
    //   * P1, the ENTER w0 store stub (sw/testdata/t2b/p1-susp, both
    //     preparation histories): chip and model are clock-identical for 197
    //     clocks and part on exactly the eval at T4+1.  Blocking it makes all
    //     four captured cells clock-identical over the whole 4,063-clock run.
    //   * P5, the Arm-C fetch-limited sled at N = 8 / N = 12
    //     (sw/testdata/t2b/p5-armc): the chip's minimum resume gap pins at
    //     cidle = 3, which is T1 = T4+4 -- unreachable if the block were keyed
    //     to the eval, because under waits that would push the grant to T4+3.
    //   * the boot loop and the `0F39` tail, the other two legs of the
    //     "SUSP lead" conflict, both close on it (12.1).
    //
    // It is a SEPARATE pair of fields from the QS-port hold below for exactly
    // one reason: a FLUSH discards the bytes, so nothing is written and the
    // redirect prefetch is not held off, while the QS port stays busy anyway
    // (MEASURED both ways: clearing the QS window at the flush costs 6,848
    // qop rows; NOT clearing the scheduler window costs 1,555 branch-form
    // cases -- E9/EA/EB/E2/E3/70-7F, every one of them a flush).
    long pf_land_from_ = -2;
    long pf_land_to_ = -2;
    // M7 -- THE PREFETCH-ELIGIBILITY TEST IS SAMPLED AT A FIXED CYCLE INDEX
    // (2 = T3) AND LATCHED; the COMPLETION EVAL only applies what that clock
    // decided.  The predicate itself is UNCHANGED (M4: occupancy including
    // bytes in flight <= 4) -- what moves is WHEN it is read.
    //
    // At w0 index 2 IS the completion eval (M2r: e = 2 when N = 0), so this is
    // w0-neutral BY CONSTRUCTION, not by luck.  Under waits the eval moves out
    // to T4 with the READY sample while the sample instant does NOT -- so
    // every queue POP that happens during T3..T4 (i.e. during the Tw stretch)
    // is invisible to the decision, and the part declines a refill the model
    // used to grant.  That is the whole of the "the model resumes too eagerly"
    // shape the six RED law cards share.
    //
    // It joins the campaign's other fixed cycle-relative indices -- the OPR
    // release at index 2 (11.4, the SAME clock), M6's queue-write block at
    // T4+1 (12.1) and the `F3AA` closing pop at T4+2 (12.4).
    //
    // MEASURED on the T2b Arm-C silicon sled (sw/testdata/t2b/p5-armc), which
    // is the only stimulus in the repo that scores the resume decision
    // EVENT BY EVENT.  Over the divergence-free prefix (2,252 CODE->CODE
    // completion evals, 26 of them a chip PAUSE), the occupancy read at each
    // candidate index against the chip's own GO/PAUSE:
    //
    //     sampled at   N = 8 errors   N = 12 errors
    //     T1                44             ---
    //     T2                22              20
    //     T3 (index 2)       4               0
    //     T4 (the eval)     15              12
    //
    // T3 is the minimum on BOTH wait levels and is exact at N = 12; T4 -- the
    // model's own instant -- is the worst on both.  The falsifier is any
    // waited capture where a pop between T3 and T4 changes the decision.
    bool pf_arm_ = true;
    bool pf_arm_valid_ = false;
    // M7b -- THE OUTSTANDING-FETCH TERM CLEARS WHEN THE BYTES ARE POPPABLE,
    // NOT WHEN THEY ARE WRITTEN.  The queue counter takes the bytes at the
    // push edge (e+1, M3); the "a fetch is out" term the scheduler adds to it
    // holds until e+2 inclusive -- the clock before they may be popped.  Two
    // flops, two clear conditions; across the landing clocks the scheduler
    // therefore counts those bytes TWICE and the refill threshold bites two
    // bytes early.
    //
    // w0-NEUTRAL BY CONSTRUCTION: at w0 the window is [T4, T4+1], of which T4
    // is not an eval point (M1) and T4+1 is M6's blocked clock -- so no w0
    // eval can see it.  Under waits the window is [T4+1, T4+2] and T4+2 IS a
    // live idle eval, which is the only clock the rule changes.
    //
    // MEASURED on the same Arm-C silicon sled, on the events where the chip's
    // COMPLETION eval declined (53 of them, aligned): the chip grants at T4+2
    // in 40 and at T4+3 in 13, and the queue count at T4+2 separates the two
    // sets with ZERO exceptions -- q <= 2 grants, q = 3 or 4 waits a clock.
    // With the fetch's own two bytes still counted that is exactly the
    // unchanged `occupancy <= 4`; without it no threshold on any single clock
    // separates the two sets at all.
    long pf_infl_to_ = -2;
    int pf_infl_n_ = 0;
    // S8/S9: once the part is halted the prefetcher never runs again.
    bool halted_ = false;
    bool halt_pending_ = false;
    Access halt_acc_;
    uint32_t last_fetch_addr_ = 0;
    bool e_pend_ = false;
    long e_from_ = 0;
    long e_x_ = -1;                  // the flush micro-row's own clock                // earliest clock the display may take
    // F1(b): the two clocks a completed fetch's bytes take to land in the
    // queue -- the push edge (eval+1) and the absorb clock (eval+2).  The
    // fetch owns the QS port across both.
    long push_absorb_from_ = -2;
    long push_absorb_clk_ = -2;
    uint8_t qs_pending_ = kQsNone;   // point sample for the clock about to run
    uint16_t upc_pending_ = 0xFFFF;
    bool opc_valid_ = false;
    uint8_t opc_byte_ = 0;

    // --- EU requests ---
    std::deque<Access> req_;
    int wres_ = 0;           // write cycles reserved but not yet given data
    Access* find_reserved();
    // Two deadlines, because a STORE and a LOAD are waited on for different
    // reasons: the F/OPR interlock waits for the READ that feeds it, while the
    // instruction's retire waits for ALL of its bus work (S5: a store the BIU
    // has already scheduled but not yet run must not stall the interlock that
    // is about to hand it its data).
    // THE RETIRE DEADLINE IS THE WRITE, NOT THE BUS.  An instruction's
    // successor pops its opcode on the E row's own clock; the only thing that
    // can push that later is a STORE still owed its data by the write-pairing
    // latch (7.7's max-of-two-deadlines).  An outstanding READ does NOT hold
    // the retire -- the ROM's own `F` rows do that where it matters.
    // MEASURED: `8F.0` mod3 (POP r16 via 0058..005B) pops the successor's
    // opcode at pop+5, on the E row, while its stack read has not even
    // reached T1; `88` mod0 pops it on the MEMW's T4+1.
    int eu_pending_ = 0;     // every EU access posted but not yet completed
    int rd_pending_ = 0;     // ...just the reads
    int wr_pending_ = 0;     // ...just the writes
    long wr_done_clk_ = -1;  // retire deadline: last WRITE T4 + 1
    // THE F INTERLOCK IS THE **OPR** INTERLOCK: PER ACCESS, IN ORDER, READS
    // AND WRITES ALIKE.  `F` marks the row that loads OPR, and OPR is both the
    // read-data register and the write-data register -- one register, so the
    // row cannot load it until the outstanding access has finished with it
    // (T4 + 1).
    //  * on a READ that is "wait for my data": `A6` (CMPSB) issues both loads
    //    back to back and runs 00A0 F / 00A1 / 00A2 F E -- the first F
    //    releases on load 1's T4+1 and the retire lands on load 2's, three
    //    clocks apart, which only happens if 00A0 waited for load 1 alone.
    //  * on a WRITE it is "wait until the store has taken its data", and it is
    //    what spaces a PUSH CHAIN.  `60` (PUSHA) alternates 023A `MEMW` /
    //    023B `CX -> OPR F`, and `9A` (CALLF) runs 022E `MEMW` / 022F
    //    `PC -> OPR F` / 0230 `MEMW`: the F releases at the first store's
    //    T4+1, the next store's bus-control field decodes one row early (F2),
    //    so the second store's T1 lands on the first's T4+3.  MEASURED over
    //    every golden (sw/wchain.py): write->write is T4+3 in `60 9A CC CD CE
    //    FF.3 62 F6.6/7 F7.6/7`, and T4+1 exactly where the ROM has NO
    //    `-> OPR` row between the two stores -- ENTER's nesting loop (026D
    //    MEMW / 026E JMP / 026F / 0270 MEMW, the pushed value still standing
    //    in OPR from the loop's own MEMR) and REP STOS (the stored AW never
    //    leaves OPR).  No table, no store lead-in: one register, one flag.
    std::deque<long> rd_done_q_;   // completed reads' T4 + 1, in order
    // ...and the WRITE side of the same register: how many stores have been
    // GIVEN their data and not yet handed it to the bus, plus the clock the
    // last of them frees OPR on.  A store that is only RESERVED (S5) does not
    // own OPR -- the very `F` row that would wait for it is the row about to
    // load it (ENTER's 0262 MEMW / 0263 `BP -> OPR F`).
    int opr_held_ = 0;
    long opr_free_clk_ = -1;
    // OPR, SHADOWED.  Every completed READ loads it (at that read's T4 + 1)
    // and every paired store's value passes through it; a store that reaches
    // T1 without having been given data drives whatever is STILL STANDING
    // there, rotated by its own A0 (M5b).  That is not a fallback -- it is
    // the whole of the string loops:
    //   * `A4` REP MOVS has NO `F` row between its 008D MEMR and its 008F
    //     MEMW, so the store simply drives what the load put in OPR one clock
    //     earlier.  MEASURED: `F3A4` cx=1, load at an ODD address showing
    //     5190 on the pins, store at an ODD address driving 5190 -- the
    //     rotator applied twice.
    //   * `F3AA` REP STOS refreshes OPR only on its first element, so every
    //     later store re-drives the same word aligned to its own address.
    uint16_t last_wval_ = 0;
};

}  // namespace sim

#endif  // BIU_TIMED_H
