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
    // S9b (sec.19.8.2 falsifier): the wait count of the last WRITE cycle that
    // completed.  Diagnostic instrument only -- it exists so the chained
    // REP-abort's rival anchor ("write-accept / eval-keyed", which moves with
    // the wait count) can be RUN against the census instead of argued about.
    int last_write_waits() const { return last_wr_waits_; }
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
    // The HLT DECODE drives the status register and freezes the prefetcher --
    // see loader_impl.h's ONE_BYTE_LOGIC block (S9a).
    void halt_decode(uint16_t upc) { note_halt(upc); }
    // S8/S9: run one clock with no EU behind it (the parked, halted bus).
    void tick_idle() { tick(); }

    // --- S9a: the pin-event machinery -------------------------------------
    //
    // THE RIG'S PIN SCHEDULE, replayed.  `hdl/tb/tb_v30_core.sv`'s pin-event
    // scheduler arms on one of two anchors and then counts clocks:
    //   trigger 1 (fetch): the CODE T1 whose 20-bit address is `addr`;
    //                      the pin is driven from anchor + 2 + delay
    //   trigger 2 (fpop):  the window-opening `F` pop;
    //                      the pin is driven from anchor + delay
    // and it is held for `hold` clocks (0 = to the end of the case).  This is
    // a RIG INPUT, in the same class as `iord` / the INTA constant: nothing
    // about the part is predicted from it.  The BIU tracks the two anchors
    // because they are pin events on ITS OWN row stream.
    void set_evt(int trigger, int pin, uint32_t addr, long delay, long hold,
                 int pins_cfg) {
        ev_trigger_ = trigger; ev_pin_ = pin; ev_addr_ = addr & 0xFFFFFu;
        ev_delay_ = delay; ev_hold_ = hold; ev_pins_ = pins_cfg;
        ev_anchor_ = -1;
    }
    // The clock the scheduled pin goes active on, or -1 while the anchor has
    // not been seen yet.
    long assert_clk() const {
        if (ev_trigger_ == 0 || ev_anchor_ < 0) return -1;
        return ev_anchor_ + (ev_trigger_ == 1 ? 2 : 0) + ev_delay_;
    }
    // POLL_N as the 9B `JMP BUSY` row samples it.  Static level from `pins`
    // bit 2, pulled low while the scheduled POLL event drives.
    //
    // S9a -- AND IT IS THE SAME 3-DEEP PIN PIPELINE THE INT LEVEL GOES
    // THROUGH.  `interrupt_model.md`'s INT law is "the decision at B sees the
    // pin level of cycle B-3"; POLL_N is read through the same three flops, so
    // the row running on clock `c` decides on the level of clock `c-3`.
    //
    // MEASURED, and it is a CLEAN FIT with no exceptions: over the 200
    // POLL.REL goldens the missed-sample count k (the golden's own
    // `gap = 3 + 5k` to the next `F` pop) is reproduced by
    // `k = min{ j : 2 + 5j - d >= A }` at d = 3 in 200 / 200 cases, and at no
    // other depth -- d = 2 gets 164, d = 4 gets 171, d = 0 gets 65.  The
    // falsifier is any POLL release whose k needs a different depth.
    static constexpr long kPinPipe = 3;
    bool poll_busy() const {
        if (!(ev_pins_ & 4)) return false;          // POLL_N statically low
        if (ev_trigger_ == 0 || ev_pin_ != 2) return true;
        const long a = assert_clk();
        const long t = clk_ - kPinPipe;
        if (a < 0 || t < a) return true;            // release not seen yet
        return ev_hold_ != 0 && t >= a + ev_hold_;
    }
    // The recognition BOUNDARY: the clock the successor's opcode WOULD have
    // been popped on.  Same deadline as `opcode_prefetch`, but the byte stays
    // in the queue and no `F` reaches the QS port -- a recognised boundary
    // suppresses its own pop (MEASURED: every vectored golden shows the
    // would-pop cycle with QS idle).
    long boundary_no_pop(bool post_redirect = true);
    long evt_anchor() const { return ev_anchor_; }
    long first_fpop() const { return first_fpop_; }
    // The part leaves HALT: the prefetcher runs again.  (`flush()` already
    // clears `suspended_`; `halted_` is the S8/S9 park and outlives it.)
    //
    // M20 -- THE WAKE AND THE HLT ROW WRITE THE SAME STATUS REGISTER, AND THE
    // WAKE CAN GET THERE FIRST.  `halt_pending_` is the HLT row's write
    // WAITING for the register to be free (S8/S9: the display takes it on the
    // first clock the bus is idle and the eval's display slot is not).  A wake
    // that is decided BEFORE that clock takes the part out of HALT while the
    // write is still queued -- and the write never happens.  Nothing new is
    // computed here: the caller has already advanced the BIU to the decision
    // clock, so "the display has not been taken yet when unhalt() runs" IS
    // "the wake beat it to the register".  MEASURED on the S2 delay sweep:
    // the HALT status is driven iff A - H >= -2 at BOTH wait levels and BOTH
    // forms, 196/196 cells, and A + 3 (the pin pipeline, 19.7) >= H + 1 is
    // that same inequality.  20.8's 32 seeds "where the chip never drives the
    // HALT status at all because the wake reached the register first" are this
    // sentence, and this is the line that says it.
    void unhalt() { halted_ = false; halt_pending_ = false; }
    // F54 -- THE CANCELLATION IS ONE CONSTANT PER PIN, AND ONLY ONE OF THE TWO
    // WAS IN THE MODEL.  M20 (above) is the INT half and it is EXACT: the INT
    // arms release at `A + 3` and silicon's INT constant is `K = 3`.  The NMI
    // wake released at `A + 7` and silicon's NMI constant is `K = 6`, so the
    // model's announcement survived one clock too long -- the TOP delay of the
    // NMI band at every wait level, `w0 d0 / w1 d4 / w2 d6 / w3 d8`, and no
    // banked population but the S16 display walk reaches those delays.
    //
    //   F54.  The HALT announcement at clock `H` is cancelled iff the pin
    //   event's assert clock `A` satisfies `A <= H - K`, with `K = 3` on the
    //   INT pin and `K = 6` on the NMI pin.
    //
    // Invariant over the wait level, the program and IE; 1,512 S16 captures,
    // no exception (`ucore_provenance.md` §78.B, and §79 for this leg).
    //
    // THIS CANCELS THE ANNOUNCEMENT AND NOTHING ELSE.  It is the ucore's
    // `eu_unhalt_disp` in the model's idiom: the ucore leaves the EU's own
    // unhalt sequencing (`unhalt_pend`, at `A + 7`) exactly where it was and
    // puts F54 on the display path alone, so the model leaves `halted_` -- the
    // prefetch park -- to `unhalt()` at `A + 7` unchanged.  The wake's prefetch
    // release is a DIFFERENT mechanism (family B) and is not folded in here.
    //
    // On every delay >= 8 -- which is every one of the 11,200 standing
    // `HLT.NMI` goldens -- the display has already been taken long before
    // `A + 6`, `halt_pending_` is already false, and this is a no-op.
    void cancel_halt_disp() { halt_pending_ = false; }
    bool halted() const { return halted_; }
    bool suspended() const { return suspended_; }   // diagnostic only
    void charge_to(long c) { while (clk_ < c) tick(); }
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
    // I1 / F39 -- THE FLAG REGISTER IS FED BY THE DATA LATCH, NOT BY THE ROW.
    // A micro-row's destination write-enable is a LEVEL for as long as the row
    // STANDS.  While an `OPR -> FLAGS ... F` row is blocked on its interlock
    // its destination is already selected, so the PSW takes the word on the
    // clock the AD input latch CLOSES -- the T3/Tw -> T4 advance of the read it
    // is waiting for -- and not when the row finally releases.  The EU arms
    // this before it blocks and disarms it after; the BIU is the only thing
    // that knows when that edge is.  (The RTL publishes the same edge as
    // `eu_rd_edge`.)  Non-null = armed.
    void arm_flags_latch(uint16_t* psw) { flags_latch_ = psw; }
    // §84: the clock PSW.BRK last rose, for the single-step arm's sample.
    long brk_rise() const { return brk_rise_; }
    void wait_opr_free();
    void wait_bus();
    void wait_ie_floor();    // SM3 s11: the rising-IE recognition floor
    void sample_ie();        // ...and the one edge sample it needs
    // A recognition the IE gate applies to.  The rig's pin schedule already
    // names the kind (`set_evt`): 0 = INT, 1 = NMI, 2 = POLL_N.  Only the
    // maskable one is gated -- an NMI is not IE-gated and has nothing to wait
    // for, which is the WHOLE of the exemption and it is not a case in the
    // law, it is the law's own domain.
    bool maskable() const { return ev_pin_ == 0; }
    // The clock before the queue's next byte can be popped.  A pre-decode-
    // executed form's execute strobe sits there -- see loader_impl.h,
    // ONE_BYTE_LOGIC.
    void wait_retire_lead();
    // W3.4: set by `CpuT::step()` before `loader_decode`.  The BRK/TF arm
    // is known BEFORE the decode (the previous retire set it) and a
    // ONE_BYTE_LOGIC form is not in the shadow class, so this is the take.
    void set_brk_pending(bool v) { brk_pending_ = v; }
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
        // ...and a split is ONE access to the REQUEST SLOT too (M10): this is
        // true on the cycle that carries the EU's request and false on the
        // second half the BIU manufactures from it.
        bool first_of_access = true;
        // M5b, said once.  The A0 byte swapper is passed ONCE per ACCESS, on
        // the ACCESS's own address, and both cycles of a split drive the same
        // rotated word.  `mem_write` already did that for a PAIRED store; the
        // OPR-shadow path used to re-derive it from each CYCLE's address and
        // so drove the second half of a split unrotated.  MEASURED: `F3AB`
        // case 0 (`rep stosw` at an odd DI, AW = B852) shows 52B8 on all six
        // cycles -- the even-address halves included -- and `F3A5` case 6
        // shows 29A0 on both halves of its last store.
        bool odd_base = false;
        uint16_t rd_val = 0;   // a READ's datapath value -> OPR at its T4+1
        // M22: the clock this access's status reached the pins on.
        long disp = -1;
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
        // S9a -- THE INTA CYCLE DRIVES NO ADDRESS.  MEASURED
        // (docs/facts/interrupt_model.md, "INTA cycle drive", and every
        // vectored golden): AD15-0 FLOAT through the commit display and T1 --
        // they keep whatever the last data phase left standing -- and AD19-16
        // are driven to 0 over both.  From T2 on it is an ordinary read
        // display: the acknowledge byte on the lanes, PS = IE:seg as usual.
        bool no_addr = false;
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
    void expire_cmt();   // M22 -- see biu_timed.cpp
    long bus_free_clk() const;
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
    long cmt_t1_ = -1;
    // S9b: the clock the winner's status reaches the pins on (eval + 1).
    // For every non-HALT access this is cmt_t1_ - 1; see eval().
    long cmt_disp_ = -1;
    long cur_t1_ = -1;      // the RUNNING cycle's own T1 clock
    int last_wr_waits_ = 0;      // absolute clock of the committed cycle's T1
    uint16_t cmt_prev_fp_ = 0;   // fetch_ptr before the committed fetch took it
    // M22 -- the clock the ANNOUNCEMENT expires.  See `expire()` in the .cpp.
    long cmt_expire_ = -1;
    bool cmt_was_owed_ = false;  // M19's latch as it stood before this grant

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
    bool brk_pending_ = false;   // W3.4: this sequence retires into a BRK/TF take
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
    //
    // M12 -- AND A FLUSH INVALIDATES THAT RESERVATION, exactly as it already
    // invalidates M7's `pf_arm_` and M7b's `pf_infl_` (and, until F56 deleted
    // it, M6's `pf_land_`): a
    // decision the completing cycle latched about a queue the flush has just
    // emptied cannot outlive it.  So the end of the FLUSH CLOCK is an eval
    // point again and the redirect commits there.  With its sibling in
    // `flush()` (the QS-port absorb hold is released by the flush, but not
    // before the flush's own clock) this is the whole of the open Q2 question
    // -- the redirect family of 14.2 / 16.6 -- and it is W0-NEUTRAL BY
    // CONSTRUCTION: at w0 the eval sits at T3 so its display slot is T4, a
    // clock inside the cycle that the idle-eval path never reaches.
    //
    // MEASURED (17.1, `sw/q2law.py` over the fuzz bank and the w0/w1/w3
    // goldens): 300 / 300 Q2 seeds flush at T4+1 and show the E AND the
    // redirect's status on T4+2; 57 / 57 `EB` w1 cases flush at T4+2 and show
    // both on T4+3.  One rule, both populations; a window keyed to T4 instead
    // gets the first right and the second wrong, which is the masking
    // regression two prior landings were reverted for.
    long no_eval_ = -1;
    // ~~M6~~ -- **DELETED 2026-08-05, SM3 sitting 21, as F56.  DO NOT
    // RE-PROPOSE IT WITHOUT READING `ucore_provenance.md` §82 AND
    // `sm3_s21a_prereg_2026-08-05.md`.**
    //
    // M6 said: A FETCH'S BYTES ARE WRITTEN INTO THE QUEUE ON T4+1, AND THAT
    // CLOCK IS NOT A PREFETCH-GRANT POINT -- one clock, keyed to T4, so the
    // earliest eval that may resume a prefetch after a pushing fetch is T4+2
    // and that fetch's T1 opens at T4+4, at every wait level.  It was measured
    // in T2b 12.1 on three stimuli (P1's ENTER store stub, P5's Arm-C sled at
    // N = 8/12, the boot loop and the `0F39` tail) and it was a `long` pair of
    // fields here.
    //
    // WHAT REFUTES IT IS ITS OWN FIRING CENSUS, taken on this tree with a
    // counter on the branch: the block is REACHED AND TAKEN **22 times in the
    // entire tree**.  ZERO on `v0.1`'s 169,000 cases, ZERO on `v0.1-w1`,
    // `-w3` and the `evt` cells, ZERO on `timed_scenario`, `timed_enter_replay`,
    // `timed_ins_replay` and `timed_wvec_gate`, and **ZERO on all 228
    // `timed_lawcards` processes -- including C1/C2/C3, the Arm-C sled that
    // MEASURED it**.  THREE firings in one seed of the 3,242-seed fuzz bank,
    // whose verdict does not move either way.  The remaining NINETEEN are the
    // HALT sweeps and the S16 display walk, and every one of them is a cell
    // where SILICON GRANTS AND M6 REFUSES -- family B's B-1, 18 cells, closed
    // by this deletion and by nothing else.
    //
    // WHY IT WENT REDUNDANT WITHOUT ANYONE NOTICING: `no_eval_` (M2r, above)
    // already kills the clock after any completion eval, and under waits the
    // completion eval IS at T4 -- so `no_eval_ == T4 + 1` and M6's window is
    // covered by construction at every wait level above zero.  M6 was only
    // ever reachable at w0, where the completion eval is at T3.  That is also
    // why family B was a w0-only residue: not a wait-dependent law, but the
    // one wait level at which this branch existed at all.
    //
    // This does NOT say the T2b measurement was wrong.  It says the rule it
    // authorised is redundant where it agrees with silicon and wrong where it
    // does not, and 12.1's own consequence (`T4+2` / `T4+4`) is produced by
    // M2r's eval geometry alone.  FALSIFIER, standing: any population on which
    // the deleted branch would fire AND silicon agrees with it.

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
    // M19 -- THE REDIRECT IS A STANDING REQUEST, AND SUSP DOES NOT TAKE IT
    // BACK.  A FLUSH empties the queue and loads a new fetch pointer, which
    // raises the prefetcher's bus request there and then.  SUSP is an input to
    // the condition that RAISES that request; it is not a reset of the request
    // itself, so a request already standing when a later micro-row asserts
    // SUSP is still standing, and the first slot the bus can give it takes it.
    //
    // The whole of the effect lives in one window: a FLUSH whose redirect
    // cannot be granted at once (the bus is mid-cycle) followed by a SUSP
    // before the next eval.  The ROM's REP-withdrawal path is exactly that --
    // `0227 SIGMA -> PC CTL FLUSH` ... `022C tmpb -> tmpc CTL SUSP` -- and the
    // slot that then comes free is the FIRST ACKNOWLEDGE's completion eval.
    // That is the whole of 21.3's prefetch-in-the-acknowledge-gap.
    //
    // The request is CONSUMED BY THE GRANT -- the eval that chooses a fetch
    // clears it.  (Clearing it at the fetch's T1 instead is FALSIFIED: the
    // flush can land on the very clock a PRE-flush fetch opens its T1 on --
    // one already displayed, so F2 cannot take it back -- and that fetch would
    // then swallow the request the flush had just raised.  Measured: w1 181
    // vs 200 rows-exact on `INT.F3AA`.)
    bool pf_owed_ = false;
    // H1 (SM3 sitting 2) -- THE RETIRE AFTER A REDIRECT.
    //
    // A queue-flushing redirect does not retire on the clock the restarted
    // prefetcher takes the bus: the boundary sits TWO CLOCKS LATER, at that
    // fetch's T1 + 2.  One fixed index, and it is a property of the RETIRE,
    // not of the interrupt: `boundary_no_pop()` and the ordinary
    // `opcode_prefetch()` deadline both read it.
    //
    // It is INVISIBLE in ordinary code, which is why nothing measured it
    // until the whole-program event axis existed: after a flush the
    // successor's opcode pop is BYTE-limited at the refilling fetch's
    // eval + 3 (M2r), i.e. at T1 + 5 with no waits and later with them, so
    // the retire deadline never wins the max.  It is visible only where the
    // boundary is read WITHOUT a pop -- S9a's recognition boundary.
    //
    // MEASURED on the socket, `sw/sm3_ackgeom.py` over the 1,008-seed EVT
    // bank: 2,318 re-entry acknowledges, ZERO exceptions,
    //     INTA1 T1 = max(F1 + 6, F1 + L + 1)
    // with F1 the refilling CODE fetch's T1 and L its length -- i.e.
    // max(boundary + 4, the next free bus slot) with boundary = F1 + 2.
    // The floor bites only at L = 4 (w0), where it costs exactly 2 clocks.
    //
    // AND THE ARM IS THE **IE RESTORE**.  SM3 SITTING 11, LANDED 2026-08-04
    // (`ucore_provenance.md` §72, `sm3_s11_prereg_2026-08-04.md`).
    //
    //     A MASKABLE recognition may not act until TWO CLOCKS after PSW.IE's
    //     RISING EDGE.  A NON-MASKABLE one is not IE-gated and waits for
    //     nothing.
    //
    // That is the whole mechanism.  There is no arm, no stamp, no spend and no
    // exemption clause: one edge on a flag the recognition pipeline already
    // reads.  The entry clears IE (`CITF`, `01F5`), the handler's IRET pops a
    // PSW that raises it, and the floor is the two clocks the raised flag
    // needs before a gated recognition can stand on it.
    //
    // HOW IT GOT HERE, because two rivals were built first and both were
    // refuted, and a future agent will otherwise rebuild one of them:
    //
    //   C1  "the floor belongs to any REDIRECT" -- REFUTED by the sitting-2
    //       board cell (§61.3): near JMP, far JMP, CALL/RET and a bare IRET
    //       chain all sit before an unfloored ord-1 acknowledge.
    //   A2  "the arm is the INTA CYCLE" -- REFUTED by the sitting-7 cell
    //       (§68.4): a software `INT n` entry with NO INTA anywhere floors the
    //       next acknowledge 30/30 at w0.
    //   A1  "the arm is the interrupt ENTRY, generically" -- BUILT, PERFECT on
    //       its own cell (791/791) and REFUTED by the disjoint bank (§71.4):
    //       it broke FIVE seeds, all five `evt.pin = 1` (NMI), improved two,
    //       both INT, and no INT seed regressed.  Same geometry, opposite
    //       answer, partitioned perfectly by MASKABILITY.
    //
    // WHAT AUTHORISED THIS ONE.  §64.1 forbids the bank from validating a
    // reading the bank selected, so a NEW directed board cell was
    // pre-registered and run (`sm3_h1_cell.py --out sm3-s11cell`, socket,
    // FLASH #5, 672 captures).  Its sleds put an IE RISE at a boundary with NO
    // ENTRY AND NO ACKNOWLEDGE BEHIND IT and read the chosen boundary off the
    // pins (the pushed frame's IP).  At w0, 24 delays per cell:
    //
    //   `CLI;POPF;NOP;NOP`  the POPF's OWN boundary is taken   0 / 24  times
    //   `CLI;STI;NOP;NOP`   the STI's OWN boundary is taken    0 / 24
    //   `POPF;NOP;NOP;NOP`  (IE 1 -> 1, NO RISE) own boundary  9 / 24  -- the
    //                       CONTROL: the instrument can see it
    //   `CLI;POPF`          NO ENTRY AT ALL                   24 / 24  -- the
    //                       chain has no boundary a floored recognition can
    //                       ever reach, which is why §61.3's `clipopf` was
    //                       silent.  It was never a broken stimulus.
    //   the same sleds on the **NMI** pin: the raising instruction's own
    //   boundary is taken freely (9/24, 6/24) and `CLI;POPF` acknowledges
    //   24/24.  NOT GATED, exactly as the five bank seeds said.
    //
    // AND THE FLOOR'S SIZE IS MEASURED IN THE SAME COORDINATE, chip side, no
    // engine, w0, from the POP that commits IE to the entry's announcement:
    // `iehot` (no rise) min 8 and `iretnext` (planted frame, no rise) min 8;
    // `swintnext` (the IRET raises IE) min 10.  **+2, and it is H1's own two
    // clocks re-anchored from "an INTA behind us" to "IE just rose".**
    //
    // *Falsifier*: an NMI recognition FLOORED after an entry + IRET restart;
    // an IE-gated recognition UNFLOORED after one; or a maskable acknowledge
    // taken at a boundary where PSW.IE is CLEAR.
    // `V30SIM_BNDTRACE=1` prints one line per recognition boundary (the clock,
    // the pin, the last rise, whether the floor is live) and
    // `V30SIM_IETRACE=1` prints every IE transition; they are the instruments
    // that read all of the above.
    static constexpr long kIeFloor = 2;   // MEASURED; see above
    long ie_rise_ = -1;         // the clock PSW.IE last went 0 -> 1
    // §84: the SAME sample, one bit over.  `sample_ie()` already reads the
    // live architectural PSW at the EU's own commit edge (I1/F39's early load
    // at the read latch's close included), so the BRK rise costs one more
    // comparison on a word that is already in hand -- no second opinion about
    // when a flag moves.
    long brk_rise_ = -1;        // the clock PSW.BRK last went 0 -> 1
    bool brk_prev_ = false;
    bool ie_prev_ = false;      // ...the one sample the edge needs
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
    // S9a: the rig's pin schedule and its two anchors (see set_evt).
    int ev_trigger_ = 0;
    int ev_pin_ = 0;
    uint32_t ev_addr_ = 0;
    long ev_delay_ = 0;
    long ev_hold_ = 0;
    int ev_pins_ = 0;
    long ev_anchor_ = -1;
    long first_fpop_ = -1;
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
    //
    // M12 (see `no_eval_` above and `flush()`): a FLUSH discards those bytes,
    // so the hold is released -- but not before the flush's own clock, which
    // the dying absorb still occupies.  At w0 that is a no-op by construction:
    // the hold is [T4, T4+1] and a flush at or before T4 finds the fetch still
    // running and zeroes its `push_n`, so the earliest clock a flush can see a
    // hold on IS its last one.
    long push_absorb_from_ = -2;
    long push_absorb_clk_ = -2;
    uint8_t qs_pending_ = kQsNone;   // point sample for the clock about to run
    uint16_t upc_pending_ = 0xFFFF;
    bool opc_valid_ = false;
    uint8_t opc_byte_ = 0;

    // --- EU requests ---
    std::deque<Access> req_;
    // M10 -- ONE REQUEST SLOT.  The EU has a single bus-request register: a
    // micro-row that asks for a bus cycle cannot hand its request over while
    // the PREVIOUS one is still sitting in that register waiting for the bus.
    // The register is freed when the bus TAKES the request -- the accepted
    // cycle's own T1 -- and the blocked row issues on that clock.  A SPLIT
    // word access is ONE request the BIU serves with two cycles, so the slot
    // is taken once and freed at the LAST of the two T1s (`rd_last`).
    // MEASURED, and the two halves of the rule separately: releasing at the
    // FIRST cycle's T1 leaves `F3A5` (REP MOVSW) at 406/500 with the residual
    // exactly the geometry "split load, aligned store" in every cx band;
    // releasing at the LAST takes it to 500/500 and changes nothing else in
    // the 169,000-case suite.
    //
    // It is the row engine, not the bus, that this changes: the bus grid, the
    // eval, the queue and the OPR interlock are all untouched.  What it
    // removes is the model's ability to let the ROM row cadence free-run
    // arbitrarily far ahead of the bus, which is the whole of the `cx >= 2`
    // REP residual: the string loops are the only sequences in the corpus
    // whose row body is SHORTER than their bus period, so they are the only
    // place the free-run is visible at w0.  Under waits the bus period exceeds
    // the row path everywhere and the slot is never the binding deadline --
    // which is exactly why w1/w3 were already exact (12.4).
    //
    // A SPLIT word access is ONE request: the BIU manufactures the second
    // cycle itself, so only `first_of_access` posts take the slot.
    bool eu_slot_busy_ = false;
    long eu_accept_clk_ = -1;   // T1 of the access holding the slot, once known
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
    //
    // M13 -- ...AND IN 8080 EMULATION MODE THE STORE DOES NOT LET GO UNTIL IT
    // HAS RETIRED.  The write half above is 11.4's FIXED index 2 (the store
    // hands its word to the AD output latch at T2, OPR free from T3, and it
    // does NOT stretch).  With MD set the release is the store's own eu_done
    // -- the completion eval + 2, i.e. exactly `wait_bus()`'s deadline -- so
    // it stretches with the eval like every other eval-keyed quantity.
    //
    // WHAT IS MEASURED IS THE BUS GAP, NOT THE RELEASE.  The pins cannot see
    // OPR; this is the minimal model that reproduces the measured gaps from
    // quantities the model already has, and 18.2 says so.  The MEASUREMENT
    // (`sw/tacensus.py --chains`, 18.1), pins only and no model in the loop:
    // every TRAP PUSH CHAIN in the fuzz bank -- three MEMW cycles
    // stepping down by 2, then a CODE fetch -- scored by its store-2-to-
    // store-3 T1 gap against PS3, M9's emulation-mode status bit.  1,566
    // chains: 1,488 with MD clear throughout sit at the NATIVE law (gap 6 at
    // waits 0 and 1, waits+5 above, up to 20 at 15 waits); 78 with MD rising
    // between push 1 and push 2 sit at eval+2 -- gap 7 at 0 waits (73), 9 at
    // 1 (3), 11 at 3 (2).  Zero exceptions on either side, and the wait axis
    // is what separates this from a fixed extra row count (which would need
    // +1/+3/+3) and from `2*(1+waits)` (which predicts 13 at 3 waits).  Those
    // named rivals are REFUTED; uniqueness is NOT established -- there are
    // only five minority chains above w0.
    //
    // It also closes 80 of the 93 residual flush-`E` events 17.4 named and
    // misread as a post-write bus turnaround: 475 events carry that stated
    // signature and 398 of them were ALREADY exact (18.1).
    std::deque<long> rd_done_q_;   // completed reads' completion clock
                                   // (`e + 2`), in order
    // F57: this cycle's completion clock is already stamped.  See the eval
    // block in biu_timed.cpp -- the stamp is made THERE and the T4 arm is the
    // fallback for a cycle whose eval never fired.
    bool rd_stamped_ = false;
    uint16_t* flags_latch_ = nullptr;   // I1 / F39, see arm_flags_latch()
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
