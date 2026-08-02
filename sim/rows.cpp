// rows.cpp -- see rows.h.

#include "rows.h"

namespace sim {

namespace {
const char* kRegNames[14] = {"ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
                             "es", "cs", "ss", "ds", "ip", "flags"};
}  // namespace

// --- (a) check_core parse_out format ---------------------------------------

void TextRowEmitter::begin_case(long idx) {
    std::fprintf(out_, "= %ld\n", idx);
}

void TextRowEmitter::row(const ClockRow& r) {
    std::fprintf(out_, "r %u %u %u %u %05x %04x %01x %u\n", unsigned(r.tstate),
                 unsigned(r.bs), unsigned(r.qs), unsigned(r.ube_n),
                 unsigned(r.ad_addr & 0xFFFFF), unsigned(r.ad_data),
                 unsigned(r.ps & 0xF), unsigned(r.lock_n));
}

void TextRowEmitter::finals(const uint16_t regs[14]) {
    std::fprintf(out_, "f");
    for (int i = 0; i < 14; ++i) std::fprintf(out_, " %04x", regs[i]);
    std::fprintf(out_, "\n");
}

void TextRowEmitter::end_case() { std::fprintf(out_, ".\n"); }

// --- (b) chip_rows NDJSON ---------------------------------------------------

void ChipRowsEmitter::begin_case(long idx) { idx_ = idx; }

void ChipRowsEmitter::row(const ClockRow& r) {
    std::fprintf(out_,
                 "{\"idx\":%ld,\"clk\":%ld,\"t\":%u,\"bs_early\":%u,"
                 "\"qs\":%u,\"ube_n\":%u,\"ad_addr\":%u,\"ad_data\":%u,"
                 "\"ps\":%u,\"lock_n\":%u,\"upc\":%u}\n",
                 idx_, r.clk, unsigned(r.tstate), unsigned(r.bs),
                 unsigned(r.qs), unsigned(r.ube_n),
                 unsigned(r.ad_addr & 0xFFFFF), unsigned(r.ad_data),
                 unsigned(r.ps & 0xF), unsigned(r.lock_n), unsigned(r.upc));
}

void ChipRowsEmitter::finals(const uint16_t regs[14]) {
    std::fprintf(out_, "{\"idx\":%ld,\"final\":{", idx_);
    for (int i = 0; i < 14; ++i)
        std::fprintf(out_, "%s\"%s\":%u", i ? "," : "", kRegNames[i],
                     unsigned(regs[i]));
    std::fprintf(out_, "}}\n");
}

void ChipRowsEmitter::end_case() {}

}  // namespace sim
