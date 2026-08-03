// pin_replay.h -- the pin-event REPLAY directive, shared by the functional
// single-instruction runner (case_runner.cpp) and the timed one
// (timed_runner.cpp).
//
// FUNCTIONAL policy (ledger sec. 38, "pin-event forms"): the simulator does NOT
// predict the cycle-exact catch window.  It REPLAYS the boundary the golden
// recorded -- the same class of decision as the `iord=` replay (R3) -- and
// computes every architectural consequence.  Two numbers identify the boundary:
//
//   resume_ip  the PC the chip pushed, i.e. the instruction the interrupt
//              preempted.  Read out of the golden's own pushed frame at
//              SS:SP (final SS/SP, final memory image), which is the only
//              recorded statement of "which boundary fired".
//   elements   for a REP aborted mid-string (resume_ip == the prefix address,
//              which is where the V30 resumes -- no lost-prefix bug): the
//              number of string elements the golden's BUS TRACE shows
//              completing before the acknowledge.  Counted as MEMW cycles
//              ahead of the first INTA row.
//
// A case whose golden shows no push at all (SP unchanged, no PSW frame) did not
// fire (masked INT, HALT masked-resume, POLL) and runs as an ordinary case.
//
// The TIMED path needs one more coordinate the functional path does not: the
// clock the rig's PIN SCHEDULE asserts on.  That is `EvtSchedule` below, and it
// is a RIG INPUT (the same class as `iord`), read verbatim out of the golden's
// `evt` / `pins` fields -- see sw/emit_suite.py's EVT block and
// hdl/tb/tb_v30_core.sv's pin-event scheduler, which this mirrors exactly.

#ifndef PIN_REPLAY_H
#define PIN_REPLAY_H

#include <cstdint>
#include <map>
#include <string>

#include "json.h"

namespace sim {

struct Replay {
    bool active = false;
    bool nmi = false;
    uint16_t resume_ip = 0;
    int elements = -1;
};

// The rig's pin schedule, verbatim from the golden's `evt` / `pins` fields.
//   trigger 0 = no event, 1 = fetch anchor, 2 = window-opening F pop
//   assert clock = anchor + 2 + delay  (fetch)   /  anchor + delay  (fpop)
//   the pin is driven for `hold` clocks (0 = to the end of the case)
//   pins = the STATIC pin levels: b0 INT, b1 NMI, b2 POLL_N
struct EvtSchedule {
    int trigger = 0;
    int pin = 0;            // 0 INT, 1 NMI, 2 POLL_N
    uint32_t addr = 0;      // 20-bit fetch anchor
    long delay = 0;
    long hold = 0;
    int pins = 0;
};

inline bool is_rep_prefix(unsigned b) {
    return b == 0xF3 || b == 0xF2 || b == 0x65 || b == 0x64;
}

inline EvtSchedule read_evt(const json::Value& c) {
    EvtSchedule e;
    if (const json::Value* p = c.get("pins")) e.pins = int(p->i());
    const json::Value* evt = c.get("evt");
    if (!evt || evt->type != json::Value::kObj) return e;
    if (const json::Value* v = evt->get("pin")) e.pin = int(v->i());
    if (const json::Value* v = evt->get("delay")) e.delay = long(v->i());
    if (const json::Value* v = evt->get("hold")) e.hold = long(v->i());
    if (const json::Value* v = evt->get("addr")) e.addr = uint32_t(v->u()) & 0xFFFFFu;
    if (const json::Value* v = evt->get("trigger")) {
        if (v->type == json::Value::kStr)
            e.trigger = (v->str == "fetch") ? 1 : 2;
    }
    return e;
}

inline Replay derive_replay(const json::Value& c, const uint16_t* iregs,
                            const uint16_t* eregs,
                            const std::map<uint32_t, uint8_t>& img) {
    Replay r;
    const json::Value* evt = c.get("evt");
    if (!evt || evt->type != json::Value::kObj) return r;
    const json::Value* pin = evt->get("pin");
    r.nmi = pin && pin->i() == 1;

    uint32_t ss = eregs[10], sp = eregs[4];
    auto word = [&](uint32_t off) -> uint32_t {
        uint32_t a = ((ss << 4) + (off & 0xFFFF)) & 0xFFFFF;
        uint32_t a1 = ((ss << 4) + ((off + 1) & 0xFFFF)) & 0xFFFFF;
        auto lo = img.find(a), hi = img.find(a1);
        return uint32_t((lo == img.end() ? 0 : lo->second) |
                        ((hi == img.end() ? 0 : hi->second) << 8));
    };
    // A real V30 interrupt frame: PSW at SP+4 with the forced reserved bits
    // 15:12 all set, and SP six lower than it started.
    if (sp == iregs[4]) return r;
    if ((word(sp + 4) & 0xF000) != 0xF000) return r;
    r.active = true;
    r.resume_ip = uint16_t(word(sp));

    const json::Value* by = c.get("bytes");
    bool rep = by && by->type == json::Value::kArr && !by->arr.empty() &&
               is_rep_prefix(unsigned(by->arr[0].u()));
    if (rep && r.resume_ip == iregs[12]) {
        int n = 0;
        const json::Value* cy = c.get("cycles");
        if (cy && cy->type == json::Value::kArr) {
            for (const auto& row : cy->arr) {
                if (row.type != json::Value::kArr || row.arr.size() < 9) continue;
                const std::string& bs = row.arr[7].str;
                if (bs == "INTA") break;
                if (bs == "MEMW" && row.arr[8].str == "T1") ++n;
            }
        }
        r.elements = n;
    }
    return r;
}

}  // namespace sim

#endif  // PIN_REPLAY_H
