// timed_runner.cpp -- see timed_runner.h.

#include "timed_runner.h"

#include <memory>
#include <string>
#include <vector>

#include "biu_timed.h"
#include "exec_timed.h"
#include "json.h"
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
            biu.note_halt(0xFFFF);
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
