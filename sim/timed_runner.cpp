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
