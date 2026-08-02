// biu_timed.h -- the TIMED bus-interface unit: same Bus concept as sim::Biu,
// but it owns a CPU CLOCK and emits one ClockRow per clock.
//
// STATUS AT T0 (ucsim-t): this is deliberate SCAFFOLDING.  It is strictly
// serial -- one bus cycle at a time, T1 T2 T3 [Tw x N] T4, no overlap with the
// EU, no prefetch scheduler (the queue is still demand-filled, exactly as the
// functional Biu fills it), no queue push/pop latency, no cadence model for
// micro-rows, uniform wait input only.  Every one of those is a named entry in
// docs/notes/ucsim_t_provenance.md with the stage that replaces it.  What IS
// modelled here is the pin-level SHAPE of a bus cycle, because that is what the
// row emitter has to get right before any timing law can be tested at all.
//
// Composition, not inheritance: a functional `Biu core_` holds the 1 MB
// epoch-stamped memory, the transaction log, the write stream and the ordered
// bus-cycle counter, so the timed model never re-implements storage.  What the
// timed model DOES own is the prefetch queue and the fetch pointer, because a
// timed fetch is a real word-wide bus cycle and the functional core fetches one
// byte at a time on demand.
//
// --- the two pin laws that ARE modelled (MEASURED, v0.1 / v0.1-w1 / v0.1-w3) -
//
// L1 STATUS IS A REGISTERED OUTPUT, DRIVEN ONE CLOCK EARLY.  The clock
//    immediately before a cycle's T1 already carries that cycle's BS and its
//    address on AD/PS.  That is why the v0.1 README's column 7 says a T4 row
//    shows the UPCOMING cycle's type, and why an idle Ti row one clock before
//    T1 shows it too (measured: 8A case 0 rows 7-9 = PASV Ti, MEMR Ti, MEMR
//    T1).  Implemented as a one-clock delay buffer: the row for clock N is
//    handed to the sink only once clock N+1 is known, so committing a cycle
//    patches the status/address into the row that is still in flight.  No
//    look-ahead into the EU is needed or used.
//
// L2 STATUS GOES PASSIVE AFTER THE LAST DATA CLOCK.  Measured on B8 case 0 at
//    three wait levels: w0 -> active T1,T2 then PASV from T3; w1 -> active
//    T1,T2,T3,Tw then PASV at T4; w3 -> active T1..Tw(x3) then PASV at T4.
//    So the passive clock is cycle-relative index 2 at w=0 and 3+w at w>0.
//    The w=0 / w>0 discontinuity is NOT understood -- by the campaign's
//    simplicity rule a conditional like that is a signal that two simple
//    machines are interacting and we have only seen the envelope.  It is
//    recorded as an OPEN QUESTION for T1, not as a law.

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
    // Uniform wait states inserted in EVERY bus cycle.  T0 takes a scalar
    // only; per-access wait vectors and the wrand generator arrive with the
    // wait axis (T2).
    void set_waits(int w) { waits_ = w < 0 ? 0 : w; }
    // S5 on the status lines is the IE flag, so the row emitter needs a live
    // view of the PSW.  Bound to the interpreter's own machine state.
    void bind_psw(const uint16_t* psw) { psw_ = psw; }
    long clock() const { return clk_; }

    // --- case lifecycle ---------------------------------------------------
    void begin_case();
    // Flushes the one-clock delay buffer.  Must be called before the finals.
    void end_case();

    // --- the Bus concept (consumed by CpuT<Bus> and loader_decode<Bus>) ----
    uint8_t next_byte(uint16_t cs, uint16_t upc);
    uint16_t mem_read(uint16_t seg_val, uint16_t off, bool word,
                      uint8_t seg_idx, uint16_t upc);
    void mem_write(uint16_t seg_val, uint16_t off, uint16_t data, bool word,
                   uint8_t seg_idx, uint16_t upc);
    uint16_t io_read(uint16_t port, bool word, uint16_t upc);
    void io_write(uint16_t port, uint16_t data, bool word, uint16_t upc);
    uint16_t inta_read(uint16_t upc);
    void note_halt(uint16_t upc);
    void susp() { suspended_ = true; }
    void resume() { suspended_ = false; }
    void flush(uint16_t pc);
    void clear_consumed();
    long ev_count() const { return core_.ev_count(); }

    // --- queue ------------------------------------------------------------
    void queue_preload(const std::vector<uint8_t>& q, uint16_t fetch_ptr);
    size_t queue_len() const { return q_.size(); }
    uint8_t queue_at(size_t i) const { return q_[i]; }
    uint16_t fetch_ptr() const { return fetch_ptr_; }
    const std::vector<uint8_t>& consumed() const { return consumed_; }

    // --- storage and replay inputs (delegated to the functional core) -----
    void poke(uint32_t a, uint8_t v) { core_.poke(a, v); }
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
    };

    static uint32_t phys(uint16_t seg_val, uint16_t off) {
        return uint32_t((uint32_t(seg_val) << 4) + off) & 0xFFFFFu;
    }
    // sim::Sreg is ES,CS,SS,DS = 0,1,2,3; the S4:S3 pin code is
    // ES,SS,CS,DS = 0,1,2,3.  kSegZero (the internal INT routine's
    // segment-less vector fetch) and I/O both drive the "no segment" code,
    // which is the same encoding as CS -- MEASURED for I/O on E4 case 0
    // (ps=6 = IE|CS on the IOR data phase), ASSUMED for the zero segment.
    static uint8_t seg_code(uint8_t seg_idx);
    uint8_t data_ps(uint8_t segc) const;
    static bool is_write(uint8_t bs) {
        return bs == kBsMemW || bs == kBsIoW;
    }

    // Composes the AD15-0 data phase for a transfer, retaining the previous
    // value on the lane the transfer does not drive (MEASURED: 8A case 0 row
    // 10, an odd-address byte read, shows the stale low byte alongside the
    // fetched high byte).
    uint16_t lane_data(uint32_t addr, bool word, uint16_t value) const;

    void run_cycle(const Access& a);
    void do_fetch(uint16_t upc);
    // One clock that is not part of a bus cycle (a queue point sample, a
    // flush, or plain idle).
    void tick(uint8_t qs, uint16_t upc);
    void emit(ClockRow r);

    Biu core_;
    RowEmitter* rows_ = nullptr;
    const uint16_t* psw_ = nullptr;
    int waits_ = 0;
    long clk_ = 0;

    // one-clock delay buffer (law L1)
    ClockRow held_{};
    bool held_valid_ = false;

    // retained pin state, for idle rows and undriven byte lanes
    uint32_t last_addr_ = 0;
    uint16_t last_data_ = 0;
    uint8_t last_ps_ = 0;

    std::deque<uint8_t> q_;
    uint16_t fetch_ptr_ = 0;
    uint16_t cs_ = 0;
    bool suspended_ = false;
    // The next queue pop is the FIRST byte of an instruction (QS = F rather
    // than S).  Set at every instruction boundary (Cpu::step clears the
    // consumed list) and at every queue flush.
    bool pop_is_first_ = true;
    std::vector<uint8_t> consumed_;
};

}  // namespace sim

#endif  // BIU_TIMED_H
