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
    // Uniform wait states inserted in EVERY bus cycle.  Per-access wait
    // vectors and the wrand generator arrive with the wait axis (T2).
    void set_waits(int w) { waits_ = w < 0 ? 0 : w; }
    // S5 on the status lines is the IE flag, so the row emitter needs a live
    // view of the PSW.  Bound to the interpreter's own machine state.
    void bind_psw(const uint16_t* psw) { psw_ = psw; }
    long clock() const { return clk_; }

    // --- case lifecycle ---------------------------------------------------
    void begin_case();
    void end_case();

    // --- the Bus concept (consumed by CpuT<Bus> and loader_decode<Bus>) ----
    // M3b: the DECODER's byte demand is a two-clock PLA pipeline and restarts
    // it on a queue miss; the EU's `Q` source read is a combinational read of
    // the queue head and takes its byte the moment it is poppable.  Same queue,
    // two requesters.  MEASURED on the queue-empty goldens (every byte's ready
    // clock = its fetch's T4 + 2): with demand 3 / ready 4, `8A`'s DECODER
    // disp8 pops at 5 while `B8`'s MICRO-ROW imm-hi pops at 4.
    uint8_t next_byte(uint16_t cs, uint16_t upc) { return pop(cs, upc, false); }
    uint8_t decode_byte(uint16_t cs, uint16_t upc) { return pop(cs, upc, true); }
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
        uint8_t push_n = 0;    // queue bytes this fetch delivers
        uint8_t push_b[2] = {0, 0};
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
    void post(const Access& a);
    // occupancy including bytes already fetched but not yet pushed
    int occupancy() const;
    Access make_fetch() const;
    uint8_t pop(uint16_t cs, uint16_t upc, bool penalise);

    Biu core_;
    RowEmitter* rows_ = nullptr;
    const uint16_t* psw_ = nullptr;
    int waits_ = 0;
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
    bool e_pend_ = false;
    long e_from_ = 0;
    long e_x_ = -1;                  // the flush micro-row's own clock                // earliest clock the display may take
    long push_absorb_clk_ = -2;      // clock on which a fetch's bytes land
    uint8_t qs_pending_ = kQsNone;   // point sample for the clock about to run
    uint16_t upc_pending_ = 0xFFFF;
    bool opc_valid_ = false;
    uint8_t opc_byte_ = 0;
    // M3c: the clock of the previous DECODER pop.  The march's stride (this
    // step's length) is `demand - last_dec_`, and a step that misses re-runs.
    long last_dec_ = -1;

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
