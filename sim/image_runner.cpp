// image_runner.cpp -- `v30sim image`: MULTI-INSTRUCTION replay of a fuzz-bank
// test image, from RESET RELEASE through the load stub, the program and the
// store stub.
//
// The single-instruction runner (case_runner.cpp) injects an architectural
// state and executes ONE instruction.  This one injects nothing at all: it
// loads a 64 KB image into the 64K-mirrored memory the capture board is wired
// as, runs the ROM's own RESET sequence, and then lets the machine execute
// until it halts or the caller's bus-cycle budget runs out.  Everything the
// harness needs -- the twelve dumped registers, the PSW, the ordered write
// stream -- comes out of the ORDERED BUS TRANSACTION LOG, exactly as it comes
// out of the chip's cycle capture on the other side of the comparison
// (sw/fuzz_classify.py::extract_txns / func_stream / arch_dump).
//
// Wire protocol: NDJSON in, NDJSON out (one record per image).
//
//   in  {"i":N,
//        "fill":144,                 image fill byte (0x90 NOP / 0xF4 HLT)
//        "ram":[[addr,byte],...],    the non-fill bytes of the 64 KB image
//        "max_ev":N, "max_ins":N,    budgets (bus cycles / instructions)
//        "evt":{"pin":0,"at":[e,..]},external-event REPLAY directive: fire an
//                                    INT (pin 0) / NMI (pin 1) entry when the
//                                    ordered bus stream reaches cycle `e`
//        "tf":1}                     model the BRK/TF single-step trap
//
//   out {"i":N,"ins":N,"ev":N,"done":0|1,"halt":0|1,"stall":0|1,"fired":N,
//        "tx":[[kind,addr,addr2,data,width],...],   kind: see kKindName
//        "err":"..."}                               (only when something broke)
//
// The firing BOUNDARY is replayed and every consequence is computed -- the same
// policy the single-instruction pin-event forms use (ledger sec. 38), lifted to
// a coordinate that can also name a point INSIDE a string loop: the position in
// the ordered bus stream.

#include "image_runner.h"

#include <cstring>
#include <string>
#include <vector>

#include "biu.h"
#include "exec.h"
#include "json.h"
#include "pla3_table.h"
#include "state.h"

namespace sim {

namespace {

std::string read_all(std::FILE* f) {
    std::string s;
    char buf[1 << 16];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) s.append(buf, n);
    return s;
}

// The harness's done marker: OUT 0xFC, 0xF00D (sw/testimage.py).
constexpr uint16_t kDonePort = 0x00FC;
constexpr uint16_t kDoneData = 0xF00D;

struct ImgResult {
    long ins = 0;
    long ev = 0;
    int fired = 0;
    bool done = false;
    bool halt = false;
    // The illegal-form stall (state.h::stalled).  Reported as its own key so a
    // parked run cannot be read as a completed one or as an error.
    bool stalled = false;
    std::string err;
    // Decode census over the bytes the loader actually CONSUMED, so it is a
    // statement about executed code, not about bytes that happen to sit in the
    // image.  `pfx` = seen in a prefix position, `opm` = seen in the opcode
    // position.  This is what makes `F1` (pla_3: a BUSLOCK-alias prefix) and
    // A19 (conflicting REP-family prefix chains) empirically testable.
    uint32_t pfx[8] = {};
    uint32_t opm[8] = {};
    std::vector<std::vector<uint8_t>> rep2;   // conflicting REP chains
    // A string loop withdrew (the ROM's REPX path ran) but the rewound CS:PC
    // was not the CS:IP the capture recorded -- i.e. the replayed boundary did
    // not land where the chip's did.  Reported, never silently swallowed.
    int rep_withdraw_unmatched = 0;
    // Mid-string withdrawals whose rewound CS:PC DID land on the CS:IP the
    // chip pushed, bucketed by how many prefix bytes PFXCNT had to unwind.
    // Bucket >= 2 is the STACKED-prefix case (e.g. `F3 26 A4`): the general
    // form of the "saved IP covers all prefixes" law, which rows 0225-0227
    // have to produce on their own.
    int rep_withdraw_ok = 0;
    int rep_pfx[8] = {};
    // A30: how many replayed external acknowledges were taken with MD == 0.
    // Bank A of the ambiguous micro-address 111.00000010.00 is, on the A30
    // reading, the EMULATION-MODE acknowledge; an acknowledge taken in 8080
    // mode is therefore the discriminator the residual asks for.
    int inta_in_8080 = 0;
    // 8080-emulation entries the run made.  `intem` counts executions of the
    // shared INTEM bank's push row (0091, reached by BRKEM `0F FF` and by the
    // 8080 `CALLN`); `mfc` counts the MFC row (0093), which the ROM reaches
    // ONLY when COUNT came in as 1 -- i.e. only from BRKEM -- and which is the
    // instant the part leaves native mode.  Any seed with mfc > 0 is running
    // 8080 code from that point on (residual R10).
    long intem = 0, mfc = 0;
    // Diagnostic (`"ilog":1`): one entry per retired instruction --
    // [bus-cycle count at its start, CS, PC, consumed bytes...].  Lets the
    // driver name the instruction that produced a divergent bus event instead
    // of guessing from addresses.
    std::vector<std::vector<long>> ilog;
};

void census(ImgResult& r, const std::vector<uint8_t>& b) {
    size_t i = 0;
    int rep_kinds = 0;
    bool ext = false;
    for (; i < b.size(); ++i) {
        uint16_t v = pla3::kNative[b[i]];
        if (!pla3::is_prefix(v)) break;
        r.pfx[b[i] >> 5] |= 1u << (b[i] & 31);
        pla3::Bl1Op o = pla3::bl1_op(v);
        if (o == pla3::Bl1Op::kRepPfx || o == pla3::Bl1Op::kRepnePfx ||
            o == pla3::Bl1Op::kRepcPfx || o == pla3::Bl1Op::kRepncPfx)
            rep_kinds |= 1 << int(o);
        if (o == pla3::Bl1Op::kExtPrefix) { ext = true; ++i; break; }
    }
    if (i < b.size()) r.opm[b[i] >> 5] |= 1u << (b[i] & 31);
    (void)ext;
    // Two DIFFERENT REP-family prefixes in one chain: the A19 discriminator.
    if (rep_kinds && (rep_kinds & (rep_kinds - 1)) && r.rep2.size() < 16)
        r.rep2.push_back(b);
}

ImgResult run_one(const ucrom::UcRom& rom, Biu& biu, const json::Value& c,
                  std::FILE* trace_out) {
    ImgResult res;

    long max_ev = 20000, max_ins = 200000;
    if (const json::Value* v = c.get("max_ev")) max_ev = long(v->i());
    if (const json::Value* v = c.get("max_ins")) max_ins = long(v->i());
    bool tf_model = true;
    if (const json::Value* v = c.get("tf")) tf_model = v->i() != 0;
    // Codex item 8, the status-latch persistence probe: overwrite the ALU
    // status latch on every interrupt entry.  If no banked seed changes its
    // outcome under this, no banked seed DISCRIMINATES whether the latch
    // survives an interrupt -- which is the answer the probe is after.
    long stat_clobber = -1;
    if (const json::Value* v = c.get("stat_clobber")) stat_clobber = long(v->i());
    bool ilog = false;
    if (const json::Value* v = c.get("ilog")) ilog = v->i() != 0;

    // --- external-event replay directive ---------------------------------
    Cpu::EventKind evt_kind = Cpu::kEvtInt;
    std::vector<long> evt_at, evt_cs, evt_ip;
    if (const json::Value* e = c.get("evt")) {
        if (e->type == json::Value::kObj) {
            const json::Value* pin = e->get("pin");
            evt_kind = (pin && pin->i() == 1) ? Cpu::kEvtNmi : Cpu::kEvtInt;
            const json::Value* at = e->get("at");
            if (at && at->type == json::Value::kArr)
                for (const auto& x : at->arr) evt_at.push_back(long(x.i()));
            // The CS:IP the chip's own interrupt frame recorded, per firing.
            const json::Value* cs = e->get("cs");
            if (cs && cs->type == json::Value::kArr)
                for (const auto& x : cs->arr) evt_cs.push_back(long(x.i()));
            const json::Value* ip = e->get("ip");
            if (ip && ip->type == json::Value::kArr)
                for (const auto& x : ip->arr) evt_ip.push_back(long(x.i()));
        }
    }
    size_t evt_n = 0;

    // --- image ------------------------------------------------------------
    biu.begin_case();
    biu.clear_wrap();
    uint8_t fill = 0x90;
    if (const json::Value* v = c.get("fill")) fill = uint8_t(v->i());
    for (uint32_t a = 0; a < 0x10000u; ++a) biu.poke(a, fill);
    if (const json::Value* r = c.get("ram")) {
        if (r->type == json::Value::kArr) {
            for (const auto& e : r->arr) {
                if (e.type != json::Value::kArr || e.arr.size() < 2) continue;
                biu.poke(uint32_t(e.arr[0].u()) & 0xFFFF, uint8_t(e.arr[1].i()));
            }
        }
    }
    // Whole-image form (raw-tier images are ~100 % non-fill, so the sparse
    // form is five times larger than the hex dump).
    if (const json::Value* h = c.get("hex")) {
        if (h->type == json::Value::kStr) {
            auto nib = [](char ch) -> int {
                if (ch >= '0' && ch <= '9') return ch - '0';
                if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
                if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
                return -1;
            };
            size_t n = h->str.size() / 2;
            for (size_t k = 0; k < n && k < 0x10000u; ++k) {
                int hi = nib(h->str[2 * k]), lo = nib(h->str[2 * k + 1]);
                if (hi < 0 || lo < 0) break;
                biu.poke(uint32_t(k), uint8_t((hi << 4) | lo));
            }
        }
    }
    // R3 replay policy, extended to the rig: EVERY IOR cycle in every banked
    // capture carries 0xFFFF and every INTA cycle carries 0x00FF (measured over
    // the whole bank), so both are constants here rather than predictions.
    biu.set_io_in(0xFFFF);
    biu.set_inta(0x00FF);

    long cov0_intem = g_row_cover[0x91], cov0_mfc = g_row_cover[0x93];
    Cpu cpu(rom, biu);
    if (trace_out) cpu.set_trace(trace_out);
    Machine& m = cpu.state();
    if (!cpu.reset()) {
        res.err = "reset sequence did not terminate";
        return res;
    }

    size_t txn_seen = 0;
    auto scan_new = [&]() {
        const std::vector<Txn>& t = biu.txns();
        for (; txn_seen < t.size(); ++txn_seen) {
            if (t[txn_seen].kind == Txn::kIoWrite &&
                (t[txn_seen].addr20 & 0xFFFF) == kDonePort &&
                t[txn_seen].data == kDoneData)
                res.done = true;
        }
    };

    // The recorded firing boundary has TWO coordinates and needs both.  The
    // bus-stream position alone cannot separate two instruction boundaries
    // that make no bus access between them (the load stub's register MOVs are
    // a whole run of them); the recorded resume CS:IP alone cannot separate a
    // string instruction's start boundary from the mid-string withdrawal that
    // rewinds PC back to exactly that address.  Together they are unambiguous:
    // fire at the first boundary at or after the recorded bus position whose
    // live CS:PC is the CS:IP the chip pushed.
    auto want_fire = [&]() {
        if (evt_n >= evt_at.size()) return false;
        if (biu.ev_count() < evt_at[evt_n]) return false;
        if (evt_n < evt_ip.size() && evt_ip[evt_n] >= 0)
            return m.sreg[kCS] == uint16_t(evt_cs[evt_n]) &&
                   m.pc == uint16_t(evt_ip[evt_n]);
        return true;
    };
    auto take_event = [&]() {
        if (m.mode8080) ++res.inta_in_8080;
        cpu.set_evt_at(-1);
        if (!cpu.interrupt(evt_kind)) {
            res.err = "interrupt entry did not terminate";
            return false;
        }
        if (stat_clobber >= 0) m.stat = uint16_t(stat_clobber);
        ++evt_n;
        ++res.fired;
        scan_new();
        return true;
    };

    bool halt_noted = false;
    for (;;) {
        if (m.halted && !halt_noted) {
            biu.note_halt(0xFFFF);       // the HALT acknowledge status cycle
            halt_noted = true;
            res.halt = true;
        }
        // A halted machine makes no further bus cycles and never moves PC, so
        // a pending event fires unconditionally: there is nothing else that
        // could advance either coordinate.
        bool fire = want_fire() || (m.halted && evt_n < evt_at.size());
        if (fire) {
            if (!take_event()) break;
            halt_noted = false;
            continue;
        }
        if (m.halted) break;             // halted with nothing left to wake it
        if (res.ins >= max_ins) {
            res.err = "instruction budget";
            break;
        }
        if (biu.ev_count() >= max_ev) break;

        bool tf = tf_model && (m.psw & kFlagBRK) != 0;
        long ev0 = biu.ev_count();
        long cs0 = m.sreg[kCS], pc0 = m.pc;
        cpu.set_evt_at(evt_n < evt_at.size() ? evt_at[evt_n] : -1);
        if (!cpu.step()) {
            // THE ILLEGAL-FORM STALL (state.h::stalled) is a MODELLED OUTCOME.
            // The EU parks on a micro-row whose `F` interlock has nothing to
            // wait for, so no further instruction retires and no further bus
            // cycle is made by the EU.  It is NOT a HALT -- no `HALT`
            // acknowledge status is logged -- and it is NOT an error, so `err`
            // stays empty and the ordered transaction log ends where the
            // chip's does.  `res.halt` stays false for the same reason.
            if (m.stalled) {
                res.stalled = true;
                break;
            }
            res.err = "micro-sequence did not terminate";
            break;
        }
        ++res.ins;
        if (ilog) {
            std::vector<long> e{ev0, cs0, pc0};
            for (uint8_t b : biu.consumed()) e.push_back(b);
            res.ilog.push_back(e);
        }
        census(res, biu.consumed());
        scan_new();
        if (m.intr_pending) {
            // A string loop withdrew mid-element: the ROM has already backed PC
            // up over the whole prefix chain (REPX 0225-0227).
            m.intr_pending = false;
            if (want_fire()) {
                ++res.rep_withdraw_ok;
                ++res.rep_pfx[m.pfxcnt < 8 ? m.pfxcnt : 7];
                if (!take_event()) break;
                continue;
            }
            ++res.rep_withdraw_unmatched;
        }
        if (tf && !m.halted) {
            // The BRK/TF single-step trap: vector 1, entered at the ROM's own
            // hardware address (111.00000000.00 row 0).  TF is sampled at the
            // START of the instruction, so the instruction that SETS it does
            // not trap (the 8086/V30 latching rule).
            if (!cpu.interrupt(Cpu::kEvtBrk)) {
                res.err = "BRK trap entry did not terminate";
                break;
            }
            if (stat_clobber >= 0) m.stat = uint16_t(stat_clobber);
            scan_new();
        }
    }
    scan_new();
    res.ev = biu.ev_count();
    res.intem = g_row_cover[0x91] - cov0_intem;
    res.mfc = g_row_cover[0x93] - cov0_mfc;
    return res;
}

void emit(std::FILE* out, long idx, const ImgResult& r, const Biu& biu,
          bool with_code) {
    std::fprintf(out, "{\"i\":%ld,\"ins\":%ld,\"ev\":%ld,\"done\":%d,"
                      "\"halt\":%d,\"stall\":%d,\"fired\":%d,\"repbad\":%d,"
                      "\"intem\":%ld,\"mfc\":%ld,\"repok\":%d,\"inta8080\":%d,\"reppfx\":[",
                 idx, r.ins, r.ev, r.done ? 1 : 0, r.halt ? 1 : 0,
                 r.stalled ? 1 : 0, r.fired,
                 r.rep_withdraw_unmatched, r.intem, r.mfc,
                 r.rep_withdraw_ok, r.inta_in_8080);
    for (int i = 0; i < 8; ++i)
        std::fprintf(out, "%s%d", i ? "," : "", r.rep_pfx[i]);
    std::fprintf(out, "],\"tx\":[");
    std::fprintf(out, "%s", "");
    bool first = true;
    for (const Txn& t : biu.txns()) {
        if (t.kind == Txn::kCodeFetch && !with_code) continue;  // not functional
        std::fprintf(out, "%s[%u,%u,%u,%u,%u]", first ? "" : ",",
                     unsigned(t.kind), t.addr20, t.addr2, t.data, t.width);
        first = false;
    }
    std::fprintf(out, "],\"pfx\":[");
    for (int i = 0; i < 8; ++i)
        std::fprintf(out, "%s%u", i ? "," : "", r.pfx[i]);
    std::fprintf(out, "],\"opm\":[");
    for (int i = 0; i < 8; ++i)
        std::fprintf(out, "%s%u", i ? "," : "", r.opm[i]);
    std::fprintf(out, "],\"rep2\":[");
    for (size_t i = 0; i < r.rep2.size(); ++i) {
        std::fprintf(out, "%s[", i ? "," : "");
        for (size_t j = 0; j < r.rep2[i].size(); ++j)
            std::fprintf(out, "%s%u", j ? "," : "", r.rep2[i][j]);
        std::fprintf(out, "]");
    }
    std::fprintf(out, "]");
    if (!r.ilog.empty()) {
        std::fprintf(out, ",\"ilog\":[");
        for (size_t i = 0; i < r.ilog.size(); ++i) {
            std::fprintf(out, "%s[", i ? "," : "");
            for (size_t j = 0; j < r.ilog[i].size(); ++j)
                std::fprintf(out, "%s%ld", j ? "," : "", r.ilog[i][j]);
            std::fprintf(out, "]");
        }
        std::fprintf(out, "]");
    }
    if (!r.err.empty()) std::fprintf(out, ",\"err\":\"%s\"", r.err.c_str());
    std::fprintf(out, "}\n");
}

}  // namespace

int run_images(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
               const ImageOptions& opt) {
    std::string buf = read_all(in);
    size_t p = 0;
    Biu biu;
    biu.set_mirror(true);   // the capture board is 64K RAM mirrored over 1 MB
    long idx = 0;
    while (p < buf.size()) {
        json::skip_ws(buf, p);
        if (p >= buf.size()) break;
        json::Value c;
        std::string err;
        if (!json::parse(buf, p, c, err)) {
            std::fprintf(stderr, "json: %s at %zu\n", err.c_str(), p);
            return 2;
        }
        long i = idx;
        if (const json::Value* v = c.get("i")) i = long(v->i());
        bool tracing = opt.trace && (opt.trace_idx < 0 || opt.trace_idx == i);
        ImgResult r = run_one(rom, biu, c, tracing ? stderr : nullptr);
        const json::Value* wc = c.get("code");
        emit(out, i, r, biu, wc && wc->i() != 0);
        ++idx;
    }
    if (opt.coverage) {
        std::fprintf(out, "{\"coverage\":[");
        for (int k = 0; k < ucrom::kRowCount; ++k)
            std::fprintf(out, "%s%ld", k ? "," : "", g_row_cover[k]);
        std::fprintf(out, "]}\n");
    }
    return 0;
}

}  // namespace sim
