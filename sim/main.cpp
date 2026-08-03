// main.cpp -- v30sim CLI dispatcher.
//
// Subcommands:
//   disasm <romfile>   disassemble the EU microcode ROM (docs/V20BITS.TXT)
//   info   <romfile>   summarise ROM contents and micro-address coverage
//   dump-tables <romfile>  flat dump of the ROM rows, the resolved
//                      micro-address decode and the PLA3 tables (gate G0)
//   run    <romfile>   execute SingleStepTests cases from stdin (NDJSON out)
//   image  <romfile>   replay whole 64 KB test images (fuzz-bank sequences)
//   trace  <romfile> <idx>  per-micro-row dump of ONE case (to stderr)
//   timed-run <romfile>  execute cases in TIMED mode, emitting one record per
//                        CPU clock (ucsim-t)

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "case_runner.h"
#include "disasm.h"
#include "image_runner.h"
#include "pla3_table.h"
#include "timed_runner.h"

namespace sim { int run_biu_script(const char* path, std::FILE* out); }
#include "ucrom.h"

namespace {

int usage(const char* argv0) {
    std::fprintf(stderr,
                 "usage: %s <command> [args]\n"
                 "\n"
                 "commands:\n"
                 "  disasm <romfile>   print microcode disassembly (V20UC.TXT format)\n"
                 "  info   <romfile>   print ROM statistics\n"
                 "  dump-tables <romfile>\n"
                 "                     dump ROM rows + resolved micro-address\n"
                 "                     decode + the PLA3 tables (gate G0)\n"
                 "  run    <romfile> [--queue] [--emit-final] [--mirror]\n"
                 "                     [--alu-hw-report] [--coverage]\n"
                 "                     [--wrap-scan]\n"
                 "                     run cases from stdin\n"
                 "  image  <romfile> [--coverage] [--trace[=idx]]\n"
                 "                     replay 64 KB test IMAGES from stdin\n"
                 "                     (reset -> load stub -> program -> store\n"
                 "                      stub); see sim/image_runner.cpp\n"
                 "  trace  <romfile> <idx>      trace one case from stdin\n"
                 "  timed-run <romfile> [--waits N] [--ndjson] [--mirror]\n"
                 "  biu-script <script>  BIU-only scripted run (ucore U1)\n"
                 "                     [--case=IDX] [--steps=N]\n"
                 "                     run cases from stdin in TIMED mode,\n"
                 "                     emitting one row per CPU clock\n",
                 argv0);
    return 2;
}

bool load_rom(const char* path, ucrom::UcRom& rom) {
    std::string err;
    if (!rom.load(path, err)) {
        std::fprintf(stderr, "v30sim: %s\n", err.c_str());
        return false;
    }
    return true;
}

int cmd_disasm(int argc, char** argv) {
    if (argc != 1) {
        std::fprintf(stderr, "usage: v30sim disasm <romfile>\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    ucrom::disassemble(rom, stdout);
    return 0;
}

int cmd_info(int argc, char** argv) {
    if (argc != 1) {
        std::fprintf(stderr, "usage: v30sim info <romfile>\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    std::printf("rows            : %d of %d\n", rom.rows_read(), ucrom::kRowCount);
    std::printf("patterns        : %d of %d\n", rom.pats_read(), ucrom::kOpcCount);
    std::printf("unmapped addrs  : %d of 8192\n", rom.unmapped_addrs());
    std::printf("ambiguous addrs : %d of 8192\n", rom.ambiguous_addrs());
    return 0;
}

// dump-tables -- emit the two GENERATED-TABLE sources (microcode ROM rows +
// resolved micro-address decode, and the group-decode PLA) in a flat text form
// so `sw/check_ucore_tables.py` can byte-diff the ucore RTL artifacts against
// THIS model's own copy.  Read-only; no execution state is touched.
int cmd_dump_tables(int argc, char** argv) {
    if (argc != 1) {
        std::fprintf(stderr, "usage: v30sim dump-tables <romfile>\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;

    std::printf("# v30sim dump-tables v1\n");
    std::printf("rows %d\n", ucrom::kRowCount);
    for (int i = 0; i < ucrom::kRowCount; ++i) {
        const ucrom::MicroOp& m = rom.op(i);
        // Re-encode the decoded row into the 29-bit post-inversion word, from
        // the FIELDS -- so a field-position drift in either implementation
        // shows up as a diff rather than cancelling out.
        uint32_t w = (uint32_t(m.s1) << 24) | (uint32_t(m.d1) << 19) |
                     (uint32_t(m.s2) << 15) | (uint32_t(m.d2) << 13);
        if (!m.f) w |= 1u << 12;
        if (!m.w) w |= 1u << 11;
        if (!m.e) w |= 1u << 10;
        if (m.type == ucrom::MicroType::CTL)
            w |= (1u << 9) | (uint32_t(m.ictl) << 5) |
                 (uint32_t(m.ectl) << 2) | uint32_t(m.sr);
        else if (m.type == ucrom::MicroType::JMP)
            w |= (1u << 8) | (uint32_t(m.cond) << 4) | uint32_t(m.loc);
        else
            w |= (uint32_t(m.alu_op) << 3) | (uint32_t(m.alu_tmp) << 1) |
                 uint32_t(m.r ? 1 : 0);
        std::printf("row %04X %08X\n", unsigned(i), w);
    }
    std::printf("addrs 8192\n");
    for (int addr = 0; addr < 8192; ++addr) {
        int page = (addr >> 10) & 7;
        int opc = (addr >> 2) & 0xFF;
        int row = addr & 3;
        std::printf("addr %04X %d %d\n", unsigned(addr),
                    rom.bank_of(page, opc, row, false),
                    rom.bank_of(page, opc, row, true));
    }
    std::printf("pla 3\n");
    for (int i = 0; i < 256; ++i)
        std::printf("pla native %02X %04X\n", unsigned(i),
                    unsigned(pla3::kNative[size_t(i)]));
    for (int i = 0; i < 256; ++i)
        std::printf("pla mode8080 %02X %04X\n", unsigned(i),
                    unsigned(pla3::kMode8080[size_t(i)]));
    for (int i = 0; i < 256; ++i)
        std::printf("pla ext %02X %04X\n", unsigned(i),
                    unsigned(pla3::kExt[size_t(i)]));
    return 0;
}

int cmd_run(int argc, char** argv) {
    if (argc < 1) {
        std::fprintf(stderr,
                     "usage: v30sim run <romfile> [--queue] "
                     "[--alu-hw-report]\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    sim::RunOptions opt;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--queue") == 0) opt.check_queue = true;
        else if (std::strcmp(argv[i], "--emit-final") == 0)
            opt.emit_final = true;
        else if (std::strcmp(argv[i], "--mirror") == 0)
            opt.mirror = true;
        else if (std::strcmp(argv[i], "--alu-hw-report") == 0)
            opt.alu_hw_report = true;
        else if (std::strcmp(argv[i], "--coverage") == 0)
            opt.coverage = true;
        else if (std::strcmp(argv[i], "--wrap-scan") == 0)
            opt.wrap_scan = true;
        else if (std::strncmp(argv[i], "--report=", 9) == 0)
            opt.max_report = std::atoi(argv[i] + 9);
    }
    return sim::run_cases(rom, stdin, stdout, opt);
}

int cmd_image(int argc, char** argv) {
    if (argc < 1) {
        std::fprintf(stderr,
                     "usage: v30sim image <romfile> [--coverage] "
                     "[--trace[=idx]]\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    sim::ImageOptions opt;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--coverage") == 0) opt.coverage = true;
        else if (std::strcmp(argv[i], "--trace") == 0) opt.trace = true;
        else if (std::strncmp(argv[i], "--trace=", 8) == 0) {
            opt.trace = true;
            opt.trace_idx = std::atol(argv[i] + 8);
        }
    }
    return sim::run_images(rom, stdin, stdout, opt);
}

int cmd_trace(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: v30sim trace <romfile> <case-index>\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    sim::RunOptions opt;
    opt.trace = true;
    opt.trace_idx = std::atol(argv[1]);
    opt.max_report = 1 << 30;
    return sim::run_cases(rom, stdin, stdout, opt);
}

int cmd_timed_run(int argc, char** argv) {
    if (argc < 1) {
        std::fprintf(stderr,
                     "usage: v30sim timed-run <romfile> [--waits N] "
                     "[--ndjson] [--mirror] [--case=IDX] [--steps=N]\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    sim::TimedOptions opt;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--ndjson") == 0) opt.ndjson = true;
        else if (std::strcmp(argv[i], "--mirror") == 0) opt.mirror = true;
        else if (std::strcmp(argv[i], "--waits") == 0 && i + 1 < argc)
            opt.waits = std::atoi(argv[++i]);
        else if (std::strncmp(argv[i], "--waits=", 8) == 0)
            opt.waits = std::atoi(argv[i] + 8);
        else if (std::strncmp(argv[i], "--case=", 7) == 0)
            opt.only_idx = std::atol(argv[i] + 7);
        else if (std::strncmp(argv[i], "--steps=", 8) == 0)
            opt.steps = std::atoi(argv[i] + 8);
    }
    return sim::run_timed(rom, stdin, stdout, opt);
}

// ucore stage U1: the BIU alone, driven by a script (sim/biu_script.cpp).
int cmd_biu_script(int argc, char** argv) {
    if (argc < 1) {
        std::fprintf(stderr, "usage: v30sim biu-script <script>\n");
        return 2;
    }
    return sim::run_biu_script(argv[0], stdout);
}

int cmd_timed_boot(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr,
                     "usage: v30sim timed-boot <romfile> <image.bin> "
                     "[--clocks N] [--ndjson] [--waits N] "
                     "[--wvec F] [--wmax K --wseed S] [--evt F]\n");
        return 2;
    }
    ucrom::UcRom rom;
    if (!load_rom(argv[0], rom)) return 1;
    sim::TimedOptions opt;
    long clocks = 260;
    for (int i = 2; i < argc; ++i) {
        if (std::strcmp(argv[i], "--ndjson") == 0) opt.ndjson = true;
        else if (std::strncmp(argv[i], "--clocks=", 9) == 0)
            clocks = std::atol(argv[i] + 9);
        else if (std::strcmp(argv[i], "--clocks") == 0 && i + 1 < argc)
            clocks = std::atol(argv[++i]);
        else if (std::strncmp(argv[i], "--waits=", 8) == 0)
            opt.waits = std::atoi(argv[i] + 8);
        else if (std::strncmp(argv[i], "--wvec=", 7) == 0)
            opt.wvec_path = argv[i] + 7;
        else if (std::strncmp(argv[i], "--evt=", 6) == 0)
            opt.evt_path = argv[i] + 6;
        else if (std::strncmp(argv[i], "--wmax=", 7) == 0)
            { opt.wrand = true; opt.wmax = std::atoi(argv[i] + 7); }
        else if (std::strncmp(argv[i], "--wseed=", 8) == 0)
            { opt.wrand = true;
              opt.wseed = unsigned(std::strtoul(argv[i] + 8, nullptr, 0)); }
    }
    return sim::run_timed_boot(rom, argv[1], clocks, stdout, opt);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return usage(argv[0]);
    const char* cmd = argv[1];
    if (std::strcmp(cmd, "disasm") == 0) return cmd_disasm(argc - 2, argv + 2);
    if (std::strcmp(cmd, "info") == 0) return cmd_info(argc - 2, argv + 2);
    if (std::strcmp(cmd, "dump-tables") == 0)
        return cmd_dump_tables(argc - 2, argv + 2);
    if (std::strcmp(cmd, "run") == 0) return cmd_run(argc - 2, argv + 2);
    if (std::strcmp(cmd, "image") == 0) return cmd_image(argc - 2, argv + 2);
    if (std::strcmp(cmd, "trace") == 0) return cmd_trace(argc - 2, argv + 2);
    if (std::strcmp(cmd, "timed-run") == 0)
        return cmd_timed_run(argc - 2, argv + 2);
    if (std::strcmp(cmd, "timed-boot") == 0)
        return cmd_timed_boot(argc - 2, argv + 2);
    if (std::strcmp(cmd, "biu-script") == 0)
        return cmd_biu_script(argc - 2, argv + 2);
    std::fprintf(stderr, "v30sim: unknown command '%s'\n", cmd);
    return usage(argv[0]);
}
