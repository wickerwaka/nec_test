// case_runner.cpp -- see case_runner.h.

#include "case_runner.h"

#include <cstring>
#include <map>
#include <set>
#include <vector>

#include "biu.h"
#include "exec.h"
#include "json.h"
#include "pin_replay.h"
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
    uint16_t hw_owned[kHwCount] = {};
    long hw_writes[kHwCount] = {};
    // --emit-final payload
    uint16_t regs[14] = {};
    std::vector<std::pair<uint32_t, uint8_t>> writes;
    std::vector<uint8_t> first_bytes;
    int steps = 0;
    bool fired = false;
    int near_wrap = 0, wrapped = 0, code_wrap = 0;
};

// The pin-event replay directive now lives in pin_replay.h, shared verbatim
// with the TIMED runner (S9a).  The policy statement is there.

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
    biu.clear_wrap();
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

    // The suite encodes the value each IN form's port presented in the case
    // name ("in al, a1h (iord=2ffc)").  There is no I/O model to derive it.
    // The block-I/O forms (INS / REP INS / LOCK string-I/O) carry the ORDERED
    // per-IOR sequence in an `iords` field instead.
    biu.set_io_in(0);
    {
        const json::Value* io = c.get("iords");
        if (io && io->type == json::Value::kArr) {
            std::vector<uint16_t> seq;
            for (const auto& e : io->arr) seq.push_back(uint16_t(e.u()));
            biu.set_io_seq(seq);
        }
    }
    {
        const json::Value* nm = c.get("name");
        if (nm && nm->type == json::Value::kStr) {
            size_t p = nm->str.find("iord=");
            if (p != std::string::npos) {
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
        }
    }

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

    // --- expected registers (sparse delta) -------------------------------
    uint16_t exp[14];
    for (int i = 0; i < 14; ++i) exp[i] = fr.has[i] ? fr.v[i] : ir.v[i];

    // --- pin-event replay -------------------------------------------------
    std::map<uint32_t, uint8_t> golden_img = init_ram;
    {
        const json::Value* fram0 = fin->get("ram");
        if (fram0 && fram0->type == json::Value::kArr)
            for (const auto& e : fram0->arr)
                if (e.type == json::Value::kArr && e.arr.size() >= 2)
                    golden_img[e.arr[0].u() & 0xFFFFF] = uint8_t(e.arr[1].i());
    }
    Replay rp = derive_replay(c, ir.v, exp, golden_img);
    res.fired = rp.active;

    if (rp.active) {
        bool first = true;
        for (;;) {
            if (++res.steps > 16) {
                res.ok = false;
                res.detail = " pin-event replay never reached the recorded "
                             "resume point";
                return res;
            }
            // The interrupt is taken at an INSTRUCTION boundary, so the only
            // boundary at which the recorded resume PC can be the live PC is
            // the one that fired.  A REP whose golden shows completed elements
            // resumes at its OWN first prefix byte, so its start boundary is
            // skipped and the abort is armed inside the string loop instead.
            if (!(first && rp.elements > 0) && m.pc == rp.resume_ip) break;
            cpu.set_rep_abort(first ? rp.elements : -1);
            if (!cpu.step()) {
                res.ok = false;
                // The ILLEGAL-FORM STALL is a modelled outcome, not a runaway
                // sequence -- say which one it was.  No golden reaches it (a
                // golden is a captured chip record and the chip stalls), so
                // this is a truthfulness fix, not a scoring one.
                res.detail = m.stalled ? "illegal-form stall"
                                       : "micro-sequence did not terminate";
                return res;
            }
            if (first) res.first_bytes = biu.consumed();
            first = false;
            if (m.intr_pending) break;
        }
        if (!cpu.interrupt(rp.nmi ? Cpu::kEvtNmi : Cpu::kEvtInt)) {
            res.ok = false;
            res.detail = "interrupt sequence did not terminate";
            return res;
        }
    } else if (!cpu.step()) {
        res.ok = false;
        res.detail = m.stalled ? "illegal-form stall"
                               : "micro-sequence did not terminate";
        return res;
    } else {
        res.steps = 1;
        res.first_bytes = biu.consumed();
    }
    if (opt.alu_hw_report) {
        for (int i = 0; i < kHwCount; ++i) {
            res.hw_owned[i] = cpu.hw_owned(i);
            res.hw_writes[i] = cpu.hw_writes(i);
        }
    }

    // --- expected vs. got registers --------------------------------------
    uint16_t got[14];
    for (int i = 0; i < 8; ++i) got[i] = m.gpr[i];
    got[8] = m.sreg[kES];
    got[9] = m.sreg[kCS];
    got[10] = m.sreg[kSS];
    got[11] = m.sreg[kDS];
    got[12] = m.pc;
    got[13] = m.flags();
    for (int i = 0; i < 14; ++i) res.regs[i] = got[i];
    res.near_wrap = biu.near_wrap();
    res.wrapped = biu.wrapped();
    res.code_wrap = biu.code_wrap();
    if (opt.emit_final) {
        res.writes = biu.writes();
        return res;
    }

    // Pin-event forms: the golden's recorded final.flags is the POST-HANDLER
    // store-stub PUSH PSW, an unreliable capture on both sides.  The
    // ARCHITECTURAL final flags are the interrupt-pushed PSW with IE/BRK
    // cleared; derive them from each side's own memory image and compare those
    // (sw/check_core.py::_pushed_psw_flags -- the production checker
    // sw/ucsim_check.py applies the same rule, this is only so the bring-up
    // driver reports honestly).
    if (rp.active) {
        auto pushed = [](const std::map<uint32_t, uint8_t>* im, const Biu* b,
                         uint16_t ss, uint16_t sp) {
            uint32_t a = ((uint32_t(ss) << 4) + uint16_t(sp + 4)) & 0xFFFFF;
            uint32_t a1 = ((uint32_t(ss) << 4) + uint16_t(sp + 5)) & 0xFFFFF;
            unsigned lo, hi;
            if (im) {
                auto l = im->find(a), h = im->find(a1);
                lo = l == im->end() ? 0x90 : l->second;
                hi = h == im->end() ? 0x90 : h->second;
            } else {
                lo = b->peek(a);
                hi = b->peek(a1);
            }
            return uint16_t((lo | (hi << 8)) & ~0x300);
        };
        exp[13] = pushed(&golden_img, nullptr, exp[10], exp[4]);
        got[13] = pushed(nullptr, &biu, got[10], got[4]);
    }

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

// --emit-final: one compact record per case.  `r` = the 14 final registers in
// golden order, `w` = the ORDERED byte write stream (the checker replays it the
// way sw/check_core.py reconstructs RAM), `b` = the instruction bytes the
// decoder consumed for the FIRST instruction (the deferred-queue substitute),
// `s` = instructions retired before the event, `f` = the event fired.
void emit_final(std::FILE* out, long idx, const CaseResult& r,
                bool wrap_scan) {
    std::fprintf(out, "{\"i\":%ld,\"r\":[", idx);
    for (int i = 0; i < 14; ++i)
        std::fprintf(out, "%s%u", i ? "," : "", r.regs[i]);
    std::fprintf(out, "],\"w\":[");
    bool first = true;
    for (const auto& w : r.writes) {
        std::fprintf(out, "%s[%u,%u]", first ? "" : ",", w.first, w.second);
        first = false;
    }
    std::fprintf(out, "],\"b\":[");
    for (size_t i = 0; i < r.first_bytes.size(); ++i)
        std::fprintf(out, "%s%u", i ? "," : "", r.first_bytes[i]);
    std::fprintf(out, "],\"s\":%d,\"f\":%d", r.steps, r.fired ? 1 : 0);
    if (wrap_scan && (r.near_wrap || r.wrapped || r.code_wrap))
        std::fprintf(out, ",\"x\":%d,\"xw\":%d,\"xc\":%d", r.near_wrap,
                     r.wrapped, r.code_wrap);
    if (!r.ok) std::fprintf(out, ",\"e\":\"%s\"", r.detail.c_str());
    std::fprintf(out, "}\n");
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
    biu.set_mirror(opt.mirror);
    long idx = 0, pass = 0, fail = 0, reported = 0;
    // --alu-hw-report accumulators, per hardware behaviour.
    long hw_cases[kHwCount] = {};   // cases whose FINAL PSW keeps such a bit
    long hw_bits[kHwCount] = {};    // total such bits over all cases
    long hw_commits[kHwCount] = {}; // flag commits driven by the behaviour
    long hw_any_case = 0;

    auto handle = [&](const json::Value& c) {
        if (opt.trace_idx >= 0 && idx != opt.trace_idx) {
            ++idx;
            return;
        }
        CaseResult r = run_one(rom, biu, c, opt, opt.trace ? stderr : nullptr);
        // The attribution accumulates for BOTH drivers: sw/ucsim_check.py runs
        // the sim in --emit-final mode (it owns the comparison policy), so the
        // audit has to be collected before that early return or the production
        // gates could never contribute to the sufficiency headline.
        if (opt.alu_hw_report) {
            bool any = false;
            for (int i = 0; i < kHwCount; ++i) {
                hw_commits[i] += r.hw_writes[i];
                if (r.hw_owned[i]) {
                    ++hw_cases[i];
                    any = true;
                    for (uint16_t b = r.hw_owned[i]; b; b &= uint16_t(b - 1))
                        ++hw_bits[i];
                }
            }
            if (any) ++hw_any_case;
        }
        if (opt.emit_final) {
            emit_final(out, idx, r, opt.wrap_scan);
            ++idx;
            return;
        }
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

    if (opt.alu_hw_report) {
        static const char* const kHwName[kHwCount] = {"shift_v", "logic_ac",
                                                      "bcd"};
        std::fprintf(out, "{\"alu_hw_report\":true,\"cases\":%ld,"
                          "\"cases_any\":%ld", idx, hw_any_case);
        for (int i = 0; i < kHwCount; ++i)
            std::fprintf(out,
                         ",\"%s_commits\":%ld,\"%s_cases\":%ld,\"%s_bits\":%ld",
                         kHwName[i], hw_commits[i], kHwName[i], hw_cases[i],
                         kHwName[i], hw_bits[i]);
        std::fprintf(out, "}\n");
    }
    if (opt.coverage) {
        std::fprintf(out, "{\"coverage\":[");
        for (int i = 0; i < ucrom::kRowCount; ++i)
            std::fprintf(out, "%s%ld", i ? "," : "", g_row_cover[i]);
        std::fprintf(out, "]}\n");
    }
    if (opt.emit_final) return 0;
    std::fprintf(out, "{\"summary\":true,\"pass\":%ld,\"fail\":%ld}\n", pass,
                 fail);
    return fail == 0 ? 0 : 1;
}

}  // namespace sim
