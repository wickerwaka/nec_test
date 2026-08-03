// timed_runner.cpp -- see timed_runner.h.

#include "timed_runner.h"

#include <cstdlib>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "biu_timed.h"
#include "exec_timed.h"
#include "json.h"
#include "pin_replay.h"
#include "rows.h"

namespace sim {

namespace {

const char* const kRegKeys[14] = {"ax", "cx", "dx", "bx", "sp", "bp", "si",
                                  "di", "es", "cs", "ss", "ds", "ip", "flags"};

std::string read_all(std::FILE* f) {
    std::string s;
    char buf[65536];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) s.append(buf, n);
    return s;
}

// The suite's I/O replay conventions, verbatim from case_runner.cpp: the
// ordered `iords` array when present, otherwise the `iord=XXXX` field parsed
// out of the case name.  There is no I/O model to derive either from.
void bind_io(BiuTimed& biu, const json::Value& c) {
    biu.set_io_in(0);
    const json::Value* io = c.get("iords");
    if (io && io->type == json::Value::kArr) {
        std::vector<uint16_t> seq;
        for (const auto& e : io->arr) seq.push_back(uint16_t(e.u()));
        biu.set_io_seq(seq);
    }
    const json::Value* nm = c.get("name");
    if (!nm || nm->type != json::Value::kStr) return;
    size_t p = nm->str.find("iord=");
    if (p == std::string::npos) return;
    unsigned v = 0;
    for (size_t i = p + 5; i < nm->str.size(); ++i) {
        char ch = nm->str[i];
        int d;
        if (ch >= '0' && ch <= '9') d = ch - '0';
        else if (ch >= 'a' && ch <= 'f') d = ch - 'a' + 10;
        else if (ch >= 'A' && ch <= 'F') d = ch - 'A' + 10;
        else break;
        v = (v << 4) | unsigned(d);
    }
    biu.set_io_in(uint16_t(v));
}

// --- S9a: the pin-event forms -----------------------------------------------
//
// THE FIRING POLICY IS REPLAY, exactly as it is functionally (pin_replay.h):
// the golden's own pushed frame names the boundary, and the rig's `evt` record
// names the clock its pin schedule asserts on.  Nothing about WHEN the part
// recognises is predicted here.  What the timed model owes is the CLOCK
// GEOMETRY that hangs off the replayed boundary, and it is ONE number:
//
//   *** THE INTERRUPT ENTRY SEQUENCE STARTS AT B + 2, WHERE B IS THE
//       BOUNDARY'S WOULD-POP CLOCK. ***
//
// Everything `docs/facts/interrupt_model.md` records as a separate number
// falls out of that one plus the ROM's own rows and the ordinary bus grid:
//
//   INT, running   entry row 01E0 IS the acknowledge, so the INTA request is
//                  ready at B+2 -- the measured "READY during B+2".
//   NMI, running   entry 01DA, 01DB (FARJMP, 2 clocks), 01EC, 01ED, then 01EE
//                  issues the IVT read: B+2+5 = B+7 -- the measured "ready
//                  during B+7, IVT T1 = B+9 on a quiet bus".
//
// and in HALT the same rule holds with the pin pipeline supplying B:
//
//   the HALT wake costs ONE clock.  The recognition decision sits at the
//   earliest clock the pin pipeline allows -- assert+3 for the INT LEVEL
//   (the 3-deep sample) and assert+4 for the NMI LATCH (set at edge+3, read
//   the clock after) -- and the would-pop clock is one later:
//
//   HLT.RES  B = A+4 is the resumed opcode's pop; the prefetcher restarts at
//            the decision clock A+3     (measured "resumes at assert+3, the
//            next instruction pops one cycle later")
//   HLT.INT  B = A+4 -> entry at A+6    (measured "INTA request ready at
//            assert+6"), prefetcher restarts at A+3 and a cold queue lets one
//            fetch commit before the acknowledge
//   HLT.NMI  B = A+5 -> entry at A+7 -> IVT read at A+12, T1 at A+14
//            (measured "assert+12 / T1 = assert+14"), and the BUS IS HELD:
//            the prefetcher does NOT restart before the entry (measured).
//
// The only per-form numbers in this file are those three (3, 4, 5) and they
// are the pin-pipeline depths `interrupt_model.md` already states.
void run_evt(BiuTimed& biu, CpuTimed& cpu, Machine& m,
             const json::Value& c, const uint16_t* ir, uint16_t* fin);

void snapshot(const Machine& m, uint16_t* fin) {
    for (int i = 0; i < 8; ++i) fin[i] = m.gpr[i];
    fin[8] = m.sreg[kES];
    fin[9] = m.sreg[kCS];
    fin[10] = m.sreg[kSS];
    fin[11] = m.sreg[kDS];
    fin[12] = m.pc;
    fin[13] = m.flags();
}

void run_evt(BiuTimed& biu, CpuTimed& cpu, Machine& m,
             const json::Value& c, const uint16_t* ir, uint16_t* fin) {
    // The golden's own statement of what happened: the sparse-delta final
    // registers and the post-case memory image, which is where the pushed
    // frame that names the boundary lives.
    uint16_t exp[14];
    for (int i = 0; i < 14; ++i) exp[i] = ir[i];
    std::map<uint32_t, uint8_t> img;
    const json::Value* init = c.get("initial");
    if (const json::Value* v = init->get("ram"))
        if (v->type == json::Value::kArr)
            for (const auto& e : v->arr)
                if (e.type == json::Value::kArr && e.arr.size() >= 2)
                    img[e.arr[0].u() & 0xFFFFF] = uint8_t(e.arr[1].i());
    if (const json::Value* f = c.get("final")) {
        if (const json::Value* fr = f->get("regs"))
            for (int i = 0; i < 14; ++i)
                if (const json::Value* v = fr->get(kRegKeys[i]))
                    exp[i] = uint16_t(v->u());
        if (const json::Value* v = f->get("ram"))
            if (v->type == json::Value::kArr)
                for (const auto& e : v->arr)
                    if (e.type == json::Value::kArr && e.arr.size() >= 2)
                        img[e.arr[0].u() & 0xFFFFF] = uint8_t(e.arr[1].i());
    }
    Replay rp = derive_replay(c, ir, exp, img);
    const CpuTimed::EventKind kind = rp.nmi ? CpuTimed::kEvtNmi
                                            : CpuTimed::kEvtInt;

    // --- the running boundary ---------------------------------------------
    // A REP aborted mid-string resumes at its OWN first prefix byte, so its
    // start boundary is skipped and the withdrawal is armed inside the loop
    // instead (the same discrimination the functional replay makes).
    const bool rep_mid = rp.active && rp.elements > 0;
    // ...and the withdrawal ends at the SAME kind of boundary: the ROM's REPX
    // path (0225-0227) has already backed PC over the whole prefix chain, so
    // the rewound PC IS `resume_ip` and the recognised-boundary rule applies
    // unchanged -- including the SUPPRESSED pop, which is why the golden shows
    // no `F` between the withdrawal flush and the acknowledge.
    if (rp.active) cpu.set_fire_pc(rp.resume_ip);

    bool fired = false;
    for (int s = 0; s < 16 && !biu.halted(); ++s) {
        if (rep_mid && s == 0) cpu.set_rep_abort(rp.elements);
        if (!cpu.step()) break;
        if (s == 0 && !rp.active) snapshot(m, fin);
        if (cpu.fired_boundary()) { fired = true; break; }
        if (m.intr_pending) { fired = true; break; }   // the REP withdrawal
        if (m.halted) break;
        if (!rp.active) break;      // a no-fire event form: one instruction
    }
    cpu.set_fire_pc(-1);

    if (biu.halted() || m.halted) {
        // --- the HALT wake ------------------------------------------------
        // (the HALT status and the prefetch freeze were driven by the DECODE,
        // loader_impl.h; nothing to arm here)
        snapshot(m, fin);
        const long a = biu.assert_clk();
        if (a < 0) return;                     // no scheduled event: park
        if (!rp.active) {                      // masked INT: resume, no vector
            biu.charge_to(a + 3);
            biu.unhalt();       // the prefetcher restarts at the decision
            biu.charge_to(a + 4);   // ...and the opcode pops one clock later
            // The finals stay the HALT's own (the golden's `final.regs` for a
            // masked resume is the state after HLT, not after the resumed
            // instruction); this step only produces the closing `F` pop.
            cpu.step();
            return;
        }
        if (rp.nmi) {
            biu.charge_to(a + 7);              // B = a+5, entry at B+2
        } else {
            biu.charge_to(a + 3);
            biu.unhalt();                      // the prefetcher restarts here
            biu.charge_to(a + 6);              // B = a+4, entry at B+2
        }
        biu.unhalt();
        cpu.interrupt(kind);
        snapshot(m, fin);
        return;
    }

    if (!fired) { snapshot(m, fin); return; }

    // THE DECISION CLOCK, AND IT IS THE MEASURED PIN PIPELINE.
    //
    // The boundary is replayed; WHEN the decision on it was taken is not free.
    // `interrupt_model.md`: the INT LEVEL reaches the decision through three
    // flops ("the decision at B sees the pin level of cycle B-3"), and the NMI
    // EDGE sets a latch at edge+3 which the decision reads the clock after
    // ("latest catching edge = B-4").  So the decision cannot be taken before
    // the pin's own pipeline has produced it:
    //
    //     D = max(B, A + 3)   INT        D = max(B, A + 4)   NMI
    //     entry = D + 2
    //
    // MEASURED, and BOTH terms are load-bearing: the `B` term alone leaves 32
    // of the 800 running INT/NMI goldens wrong (the late-assert cases, entry
    // 1-2 clocks early), the pin term alone leaves the rest wrong, and the max
    // of the two is exact on all 800.  The census that says so is every
    // (A, B) cell of INT.90 / INT.B8 / NMI.90 / NMI.B8 scored against the
    // window the golden's own eval grid leaves for the acknowledge request:
    // 16 + 23 + 12 + 20 distinct cells, zero exceptions, and p = 5 / 6 is the
    // ONLY pair that fits (p=4 breaks A=1 B=3, p=6 breaks A=0 B=3 for INT).
    // Falsifier: any case whose acknowledge is inconsistent with this max.
    if (cpu.fired_boundary()) {
        const long pipe = rp.nmi ? 4 : 3;
        const long a2 = biu.assert_clk();
        long d = cpu.boundary_clk();
        if (a2 >= 0 && a2 + pipe > d) d = a2 + pipe;
        biu.charge_to(d + 2);
    }
    if (std::getenv("V30SIM_EVTTRACE"))
        std::fprintf(stderr, "EV anchor=%ld A=%ld B=%ld entry=%ld fpop=%ld\n",
                     biu.evt_anchor(), biu.assert_clk(), cpu.boundary_clk(),
                     biu.clock(), biu.first_fpop());
    cpu.interrupt(kind);
    snapshot(m, fin);
}

void run_one(const ucrom::UcRom& rom, BiuTimed& biu, RowEmitter& sink,
             long idx, const json::Value& c, const TimedOptions& opt) {
    const json::Value* init = c.get("initial");
    if (!init) return;
    const json::Value* iregs = init->get("regs");
    if (!iregs) return;

    uint16_t ir[14] = {};
    for (int i = 0; i < 14; ++i) {
        const json::Value* v = iregs->get(kRegKeys[i]);
        if (v) ir[i] = uint16_t(v->u());
    }

    biu.begin_case();
    // The rig's memory is NOP-filled; the timed model is compared against
    // that rig's pins, and a read or a prefetch outside the case's poked
    // bytes must show 0x90 on the bus exactly as it does there.
    biu.set_fill(0x90);
    const json::Value* iram = init->get("ram");
    if (iram && iram->type == json::Value::kArr)
        for (const auto& e : iram->arr)
            if (e.type == json::Value::kArr && e.arr.size() >= 2)
                biu.poke(e.arr[0].u() & 0xFFFFF, uint8_t(e.arr[1].i()));

    std::vector<uint8_t> q;
    const json::Value* iq = init->get("queue");
    if (iq && iq->type == json::Value::kArr)
        for (const auto& e : iq->arr) q.push_back(uint8_t(e.i()));

    CpuTimed cpu(rom, biu);
    Machine& m = cpu.state();
    m = Machine{};
    for (int i = 0; i < 8; ++i) m.gpr[i] = ir[i];
    m.sreg[kES] = ir[8];
    m.sreg[kCS] = ir[9];
    m.sreg[kSS] = ir[10];
    m.sreg[kDS] = ir[11];
    m.pc = ir[12];
    m.set_flags(ir[13]);
    biu.queue_preload(q, ir[9], ir[12]);
    biu.bind_psw(&m.psw);
    biu.bind_md(&m.mode8080);
    bind_io(biu, c);

    sink.begin_case(idx);

    // The architectural finals are sampled at the end of the FIRST instruction
    // -- the same point the golden's `final.regs` describes.  The second
    // instruction runs only to produce the window-closing queue pop.
    uint16_t fin[14] = {};

    // S9a: a case that carries an `evt` record is a PIN-EVENT form and has its
    // own driver (the rig's pin schedule plus the replayed firing boundary).
    // Every other form runs the loop below, untouched.
    if (c.get("evt")) {
        EvtSchedule ev = read_evt(c);
        biu.set_evt(ev.trigger, ev.pin, ev.addr, ev.delay, ev.hold, ev.pins);
        run_evt(biu, cpu, m, c, ir, fin);
        biu.end_case();
        sink.finals(fin);
        sink.end_case();
        return;
    }

    for (int s = 0; s < opt.steps; ++s) {
        if (!cpu.step()) break;
        if (s == 0) {
            for (int i = 0; i < 8; ++i) fin[i] = m.gpr[i];
            fin[8] = m.sreg[kES];
            fin[9] = m.sreg[kCS];
            fin[10] = m.sreg[kSS];
            fin[11] = m.sreg[kDS];
            fin[12] = m.pc;
            fin[13] = m.flags();
        }
    }
    biu.end_case();
    sink.finals(fin);
    sink.end_case();
}

}  // namespace

// --- the RESET entry point --------------------------------------------------
//
// RESET RELEASE -> the ROM's reset rows.  The capture pins the offset between
// the two: the reset flush's `E` blip lands on release+7 and the first CODE
// T1 on release+9 (largemode_boot_real, rows 7 and 9), and the ROM's reset
// block is 01D0 / 01D1 SUSP / 01D2 / 01D3 FLUSH / 01D4 `E` MFS -- so the
// FLUSH row runs on release+7 and 01D0 on release+4.  Everything after that
// is the ordinary machine: the flush's E takes the QS port on its own clock
// (the bus is quiet), the eval at the end of that clock commits the redirect,
// its status shows on release+8 and its T1 opens on release+9.
//
// The four clocks are the ONE constant here and they are the internal reset
// dispatch, not a fitted per-row cost.
constexpr int kResetEntryClocks = 4;

// The rig's replay / random wait sources, in nec_bus.sv's priority order.  A
// `--wvec` file is one wait count per line in BUS-ACCESS order, which is how
// wvec_buf.sv is indexed (`bus_idx`, counting every bus cycle from run start).
static bool apply_wait_source(BiuTimed& biu, const TimedOptions& opt) {
    if (opt.wvec_path) {
        std::FILE* f = std::fopen(opt.wvec_path, "r");
        if (!f) {
            std::fprintf(stderr, "wvec: cannot open %s\n", opt.wvec_path);
            return false;
        }
        std::vector<uint8_t> v;
        int n = 0;
        while (std::fscanf(f, "%d", &n) == 1) v.push_back(uint8_t(n & 31));
        std::fclose(f);
        biu.set_wvec(v);
    }
    if (opt.wrand) biu.set_wrand(true, opt.wmax, uint16_t(opt.wseed));
    return true;
}

int run_timed_boot(const ucrom::UcRom& rom, const char* image_path, long clocks,
                   std::FILE* out, const TimedOptions& opt) {
    std::FILE* f = std::fopen(image_path, "rb");
    if (!f) {
        std::fprintf(stderr, "timed-boot: cannot open %s\n", image_path);
        return 2;
    }
    std::vector<uint8_t> img(65536, 0x90);
    size_t n = std::fread(img.data(), 1, img.size(), f);
    std::fclose(f);
    if (n == 0) {
        std::fprintf(stderr, "timed-boot: %s is empty\n", image_path);
        return 2;
    }

    BiuTimed biu;
    biu.set_mirror(true);          // the capture board's 64 KB wiring
    // ...and the rest of the capture board's I/O map, which is EMPTY: an IN
    // reads the floating bus.  `image_runner.cpp` has carried this constant
    // since the fuzz campaign ("EVERY IOR cycle in every banked capture
    // carries 0xFFFF ... measured over the whole bank") and `timed-boot`
    // simply never got it, so every IN in a replayed program returned 0x0000
    // and the run diverged architecturally from that clock on.  Re-measured
    // independently for T3 over the four banks: **4,594 of 4,594** IOR
    // data-phase rows carry 0xFFFF, over 8+ distinct ports.
    biu.set_io_in(0xFFFF);
    biu.set_waits(opt.waits);
    if (!apply_wait_source(biu, opt)) return 2;

    std::unique_ptr<RowEmitter> sink;
    if (opt.ndjson)
        sink.reset(new ChipRowsEmitter(out));
    else
        sink.reset(new TextRowEmitter(out));
    biu.set_emitter(sink.get());

    biu.begin_case();
    for (uint32_t a = 0; a < img.size(); ++a) biu.poke(a, img[a]);

    CpuTimed cpu(rom, biu);
    Machine& m = cpu.state();
    biu.bind_psw(&m.psw);
    biu.bind_md(&m.mode8080);

    sink->begin_case(0);
    // THE PART COMES OUT OF RESET WITH THE PREFETCHER SUSPENDED.  There is no
    // fetch pointer until the reset block loads PS:PC and FLUSHes (01D3), so
    // the bus is quiet across the whole reset entry -- the capture shows the
    // first CODE T1 on release+9, right after that flush, and nothing before
    // it.  Without this the model committed a fetch from 0000:0000 during the
    // reset-entry clocks: INVISIBLE to sw/check_boot.py, whose column policy
    // starts at release+8 because the pins float before the first T1, but a
    // whole spurious BUS CYCLE, which shifts every wait-vector ordinal by one
    // and made the case250 L2 replay unresolvable.  `flush()` clears it.
    biu.susp();
    biu.charge(kResetEntryClocks);
    if (!cpu.reset()) {
        std::fprintf(stderr, "timed-boot: reset sequence did not terminate\n");
        return 1;
    }
    int guard = 0;
    while (biu.clock() < clocks && ++guard < 100000) {
        if (!cpu.step()) {
            // The EU gave up on this instruction (exec_detail::kMaxRows, or an
            // undecodable form).  SAY SO: a silently truncated run looks like
            // a cadence result and is not one.  See ucsim_t_provenance.md
            // R-STALL.
            std::fprintf(stderr,
                         "timed-boot: STEP-ABORT at clk=%ld cs=%04X ip=%04X\n",
                         biu.clock(), unsigned(m.sreg[kCS]), unsigned(m.pc));
            break;
        }
        // S8/S9: the part HALTS.  The HLT micro-row drives the HALT status
        // and the bus PARKS -- it does not keep prefetching, which is what
        // the model used to do and what made every whole-program bus-cycle
        // count meaningless (the ENTER/fuzz traces are ~200 real cycles and
        // the model was emitting ~840 by prefetching past the HLT forever).
        if (m.halted) {
            // The HALT status and the prefetch freeze are driven by the HLT
            // DECODE now (loader_impl.h, S9a); the bus just parks.
            while (biu.clock() < clocks && ++guard < 100000) biu.tick_idle();
            break;
        }
    }
    biu.end_case();
    uint16_t fin[14] = {};
    for (int i = 0; i < 8; ++i) fin[i] = m.gpr[i];
    fin[8] = m.sreg[kES];
    fin[9] = m.sreg[kCS];
    fin[10] = m.sreg[kSS];
    fin[11] = m.sreg[kDS];
    fin[12] = m.pc;
    fin[13] = m.flags();
    sink->finals(fin);
    sink->end_case();
    return 0;
}

int run_timed(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
              const TimedOptions& opt) {
    std::string buf = read_all(in);
    size_t p = 0;
    json::skip_ws(buf, p);

    BiuTimed biu;
    biu.set_mirror(opt.mirror);
    biu.set_waits(opt.waits);

    std::unique_ptr<RowEmitter> sink;
    if (opt.ndjson)
        sink.reset(new ChipRowsEmitter(out));
    else
        sink.reset(new TextRowEmitter(out));
    biu.set_emitter(sink.get());

    long idx = 0;
    auto handle = [&](const json::Value& c) {
        if (opt.only_idx < 0 || idx == opt.only_idx)
            run_one(rom, biu, *sink, idx, c, opt);
        ++idx;
    };

    if (p < buf.size() && buf[p] == '[') {
        ++p;
        json::skip_ws(buf, p);
        if (p < buf.size() && buf[p] == ']') {
            ++p;
        } else {
            for (;;) {
                json::Value c;
                std::string err;
                if (!json::parse(buf, p, c, err)) {
                    std::fprintf(stderr, "json: %s at %zu\n", err.c_str(), p);
                    return 2;
                }
                handle(c);
                json::skip_ws(buf, p);
                if (p < buf.size() && buf[p] == ',') { ++p; continue; }
                break;
            }
        }
    } else {
        while (p < buf.size()) {
            json::skip_ws(buf, p);
            if (p >= buf.size()) break;
            json::Value c;
            std::string err;
            if (!json::parse(buf, p, c, err)) {
                std::fprintf(stderr, "json: %s at %zu\n", err.c_str(), p);
                return 2;
            }
            handle(c);
        }
    }
    return 0;
}

}  // namespace sim
