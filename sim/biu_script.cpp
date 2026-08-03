// biu_script.cpp -- `v30sim biu-script`: the BIU ALONE, driven by a script.
//
// The ucore campaign's stage U1 brings up hdl/rtl/ucore/v30u_biu.sv against
// THIS model with no EU on either side.  `timed-run` and `timed-boot` both run
// the interpreter, so neither can be the oracle for a BIU-only RTL; this
// subcommand supplies the missing leg.
//
// It adds NOTHING to the model.  It instantiates `sim::BiuTimed`, injects the
// same state the V30_BACKDOOR group injects into the RTL, and calls the Bus
// concept's own methods in the order a script names -- exactly the calls the
// interpreter would make.  The output is the standard `r`-record stream
// (rows.h TextRowEmitter), so sw/ulockstep.py diffs it against the TB's stream
// with no new comparison code.
//
// SCRIPT GRAMMAR (whitespace-separated; `#` ends a line; ALL NUMBERS HEX):
//
//     waits <N>              uniform READY wait states (default 0)
//     fill  <hex8>           memory fill byte (default 90)
//     cs    <hex16>          the code segment
//     ip    <hex16>          the queue-preload IP (the injected bytes' base)
//     q     <n> <b0..bn-1>   the injected queue (RIPE, as the backdoor leaves it)
//     mem   <hex20> <hex8>   poke one byte (repeatable)
//     ops
//       w <n>                burn n clocks of micro-row cadence
//       f                    pop the next byte as an F (instruction first byte)
//       s                    pop the next byte as an S
//       e <hex16> <hex16>    FLUSH + redirect to cs:ip
//     end
//
// THE ONE-CLOCK CONVENTION, stated once.  The model's EU acts BETWEEN ticks:
// `pop()` leaves `clk_` on the clock the pop rides and `flush()` does not tick
// at all.  The RTL's consumer instead OCCUPIES the clock it acts on.  So `f`,
// `s` and `e` each `tick()` once after the act, which makes the two legs agree
// on what "the next op starts on the next clock" means.  `w n` is n ticks.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "biu_timed.h"
#include "rows.h"

namespace sim {

namespace {

bool next_tok(std::FILE* f, std::string& out) {
    int c;
    for (;;) {
        do { c = std::fgetc(f); } while (c == ' ' || c == '\t' || c == '\n' ||
                                          c == '\r');
        if (c == EOF) return false;
        if (c != '#') break;
        while (c != EOF && c != '\n') c = std::fgetc(f);
    }
    out.clear();
    while (c != EOF && c != ' ' && c != '\t' && c != '\n' && c != '\r') {
        out.push_back(char(c));
        c = std::fgetc(f);
    }
    return true;
}

long hexv(const std::string& s) {
    return std::strtol(s.c_str(), nullptr, 16);
}

}  // namespace

int run_biu_script(const char* path, std::FILE* out) {
    std::FILE* f = std::fopen(path, "r");
    if (!f) {
        std::fprintf(stderr, "biu-script: cannot open %s\n", path);
        return 1;
    }

    BiuTimed biu;
    TextRowEmitter em(out);
    biu.set_emitter(&em);
    // S5 on the status lines is IE and M9's PS3 is the emulation-mode bit; the
    // stage-U1 RTL has no EU, so both are the injected constants the ucore EU
    // stub drives (`psw_ie` from the injected PSW, `md8080` tied low).
    static uint16_t psw = 0;
    static bool md = false;
    biu.bind_psw(&psw);
    biu.bind_md(&md);

    int waits = 0;
    uint8_t fill = 0x90;
    uint16_t cs = 0, ip = 0;
    std::vector<uint8_t> q;
    std::vector<std::pair<uint32_t, uint8_t>> pokes;

    std::string t;
    bool in_ops = false;
    // --- header ---
    while (!in_ops && next_tok(f, t)) {
        if (t == "waits")      { next_tok(f, t); waits = int(hexv(t)); }
        else if (t == "fill")  { next_tok(f, t); fill = uint8_t(hexv(t)); }
        else if (t == "psw")   { next_tok(f, t); psw = uint16_t(hexv(t)); }
        else if (t == "cs")    { next_tok(f, t); cs = uint16_t(hexv(t)); }
        else if (t == "ip")    { next_tok(f, t); ip = uint16_t(hexv(t)); }
        else if (t == "q") {
            next_tok(f, t);
            int n = int(hexv(t));
            for (int i = 0; i < n; ++i) { next_tok(f, t); q.push_back(uint8_t(hexv(t))); }
        } else if (t == "mem") {
            next_tok(f, t); uint32_t a = uint32_t(hexv(t)) & 0xFFFFFu;
            next_tok(f, t); pokes.push_back({a, uint8_t(hexv(t))});
        } else if (t == "ops") in_ops = true;
        else {
            std::fprintf(stderr, "biu-script: bad header token '%s'\n", t.c_str());
            std::fclose(f);
            return 2;
        }
    }

    biu.set_fill(fill);
    biu.set_waits(waits);
    biu.begin_case();
    for (auto& p : pokes) biu.poke(p.first, p.second);
    biu.queue_preload(q, cs, ip);
    em.begin_case(0);

    // --- ops ---
    while (next_tok(f, t)) {
        if (t == "end") break;
        if (t == "w") {
            next_tok(f, t);
            biu.charge(int(hexv(t)));
        } else if (t == "f" || t == "s") {
            if (t == "f") biu.prefix_retire();   // the next pop is an F again
            biu.next_byte(cs, 0xFFFF);
            biu.charge(1);                       // the pop rides THIS clock
        } else if (t == "e") {
            next_tok(f, t); uint16_t ncs = uint16_t(hexv(t));
            next_tok(f, t); uint16_t nip = uint16_t(hexv(t));
            biu.flush(ncs, nip);
            cs = ncs;
            biu.charge(1);                       // the flush occupies THIS clock
        } else {
            std::fprintf(stderr, "biu-script: bad op '%s'\n", t.c_str());
            std::fclose(f);
            return 2;
        }
    }
    std::fclose(f);
    em.end_case();
    return 0;
}

}  // namespace sim
