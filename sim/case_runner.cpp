// case_runner.cpp -- see case_runner.h.

#include "case_runner.h"

#include <cstring>
#include <map>
#include <set>
#include <vector>

#include "biu.h"
#include "exec.h"
#include "json.h"
#include "state.h"

namespace sim {

namespace {

// Golden register-name order; index into the machine is explicit below.
const char* const kRegNames[14] = {"ax", "cx", "dx", "bx", "sp", "bp",
                                   "si", "di", "es", "cs", "ss", "ds",
                                   "ip", "flags"};

struct Regs {
    uint16_t v[14] = {};
    bool has[14] = {};
};

bool read_regs(const json::Value& o, Regs& r) {
    if (o.type != json::Value::kObj) return false;
    for (const auto& kv : o.obj) {
        for (int i = 0; i < 14; ++i) {
            if (kv.first == kRegNames[i]) {
                r.v[i] = uint16_t(kv.second.i());
                r.has[i] = true;
                break;
            }
        }
    }
    return true;
}

std::string read_all(std::FILE* f) {
    std::string s;
    char buf[1 << 16];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) s.append(buf, n);
    return s;
}

struct CaseResult {
    bool ok = true;
    std::string detail;
};

CaseResult run_one(const ucrom::UcRom& rom, Biu& biu, const json::Value& c,
                   const RunOptions& opt, std::FILE* trace_out) {
    CaseResult res;
    const json::Value* init = c.get("initial");
    const json::Value* fin = c.get("final");
    if (!init || !fin) {
        res.ok = false;
        res.detail = "malformed case";
        return res;
    }

    Regs ir, fr;
    const json::Value* iregs = init->get("regs");
    if (!iregs || !read_regs(*iregs, ir)) {
        res.ok = false;
        res.detail = "no initial.regs";
        return res;
    }
    const json::Value* fregs = fin->get("regs");
    if (fregs) read_regs(*fregs, fr);

    biu.begin_case();
    std::map<uint32_t, uint8_t> init_ram;
    const json::Value* iram = init->get("ram");
    if (iram && iram->type == json::Value::kArr) {
        for (const auto& e : iram->arr) {
            if (e.type != json::Value::kArr || e.arr.size() < 2) continue;
            uint32_t a = e.arr[0].u() & 0xFFFFF;
            uint8_t v = uint8_t(e.arr[1].i());
            biu.poke(a, v);
            init_ram[a] = v;
        }
    }

    std::vector<uint8_t> q;
    const json::Value* iq = init->get("queue");
    if (iq && iq->type == json::Value::kArr)
        for (const auto& e : iq->arr) q.push_back(uint8_t(e.i()));

    Cpu cpu(rom, biu);
    Machine& m = cpu.state();
    m = Machine{};
    for (int i = 0; i < 8; ++i) m.gpr[i] = ir.v[i];
    m.sreg[kES] = ir.v[8];
    m.sreg[kCS] = ir.v[9];
    m.sreg[kSS] = ir.v[10];
    m.sreg[kDS] = ir.v[11];
    m.pc = ir.v[12];
    m.set_flags(ir.v[13]);
    biu.queue_preload(q, uint16_t(ir.v[12] + q.size()));

    if (opt.trace && trace_out) {
        const json::Value* nm = c.get("name");
        std::fprintf(trace_out, "case: %s\n",
                     nm && nm->type == json::Value::kStr ? nm->str.c_str() : "?");
        std::fprintf(trace_out,
                     "  init AX=%04X CX=%04X DX=%04X BX=%04X SP=%04X BP=%04X "
                     "IX=%04X IY=%04X\n       ES=%04X CS=%04X SS=%04X DS=%04X "
                     "IP=%04X PSW=%04X q=%zu\n",
                     ir.v[0], ir.v[1], ir.v[2], ir.v[3], ir.v[4], ir.v[5],
                     ir.v[6], ir.v[7], ir.v[8], ir.v[9], ir.v[10], ir.v[11],
                     ir.v[12], ir.v[13], q.size());
        cpu.set_trace(trace_out);
    }

    if (!cpu.step()) {
        res.ok = false;
        res.detail = "micro-sequence did not terminate";
        return res;
    }

    // --- expected vs. got registers --------------------------------------
    uint16_t exp[14], got[14];
    for (int i = 0; i < 14; ++i) exp[i] = fr.has[i] ? fr.v[i] : ir.v[i];
    for (int i = 0; i < 8; ++i) got[i] = m.gpr[i];
    got[8] = m.sreg[kES];
    got[9] = m.sreg[kCS];
    got[10] = m.sreg[kSS];
    got[11] = m.sreg[kDS];
    got[12] = m.pc;
    got[13] = m.flags();

    std::string diff;
    for (int i = 0; i < 14; ++i) {
        if (exp[i] != got[i]) {
            char b[64];
            std::snprintf(b, sizeof b, " %s exp=%04X got=%04X", kRegNames[i],
                          exp[i], got[i]);
            diff += b;
        }
    }

    // --- RAM (same reconstruction as sw/check_core.py) --------------------
    std::map<uint32_t, uint8_t> memv = init_ram;
    std::map<uint32_t, uint8_t> got_ram;
    for (const auto& w : biu.writes()) {
        auto it = memv.find(w.first);
        if (it == memv.end() || it->second != w.second) {
            memv[w.first] = w.second;
            got_ram[w.first] = w.second;
        }
    }
    std::map<uint32_t, uint8_t> exp_ram;
    const json::Value* fram = fin->get("ram");
    if (fram && fram->type == json::Value::kArr) {
        for (const auto& e : fram->arr) {
            if (e.type != json::Value::kArr || e.arr.size() < 2) continue;
            exp_ram[e.arr[0].u() & 0xFFFFF] = uint8_t(e.arr[1].i());
        }
    }
    std::set<uint32_t> addrs;
    for (const auto& kv : exp_ram) addrs.insert(kv.first);
    for (const auto& kv : got_ram) addrs.insert(kv.first);
    for (uint32_t a : addrs) {
        auto ev = exp_ram.find(a);
        auto gv = got_ram.find(a);
        auto iv = init_ram.find(a);
        int e = ev != exp_ram.end() ? ev->second
                                    : (iv != init_ram.end() ? iv->second : -1);
        int g = gv != got_ram.end() ? gv->second
                                    : (iv != init_ram.end() ? iv->second : -1);
        if (e != g) {
            char b[64];
            std::snprintf(b, sizeof b, " ram[%05X] exp=%02X got=%02X", a, e, g);
            diff += b;
        }
    }

    if (!diff.empty()) {
        res.ok = false;
        res.detail = diff;
    }
    return res;
}

void emit(std::FILE* out, long idx, const CaseResult& r, const json::Value& c) {
    const json::Value* nm = c.get("name");
    std::fprintf(out, "{\"idx\":%ld,\"ok\":%s,\"name\":\"%s\",\"diff\":\"%s\"}\n",
                 idx, r.ok ? "true" : "false",
                 nm && nm->type == json::Value::kStr ? nm->str.c_str() : "",
                 r.detail.c_str());
}

}  // namespace

int run_cases(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
              const RunOptions& opt) {
    std::string buf = read_all(in);
    size_t p = 0;
    json::skip_ws(buf, p);
    Biu biu;
    long idx = 0, pass = 0, fail = 0, reported = 0;

    auto handle = [&](const json::Value& c) {
        if (opt.trace_idx >= 0 && idx != opt.trace_idx) {
            ++idx;
            return;
        }
        CaseResult r = run_one(rom, biu, c, opt, opt.trace ? stderr : nullptr);
        if (r.ok)
            ++pass;
        else
            ++fail;
        if (!r.ok && reported < opt.max_report) {
            ++reported;
            emit(out, idx, r, c);
        } else if (opt.trace) {
            emit(out, idx, r, c);
        }
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

    std::fprintf(out, "{\"summary\":true,\"pass\":%ld,\"fail\":%ld}\n", pass,
                 fail);
    return fail == 0 ? 0 : 1;
}

}  // namespace sim
