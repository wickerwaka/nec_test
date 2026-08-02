// main.cpp -- v30sim CLI dispatcher.
//
// Subcommands:
//   disasm <romfile>   disassemble the EU microcode ROM (docs/V20BITS.TXT)
//   info   <romfile>   summarise ROM contents and micro-address coverage
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
#include "timed_runner.h"
#include "ucrom.h"

namespace {

int usage(const char* argv0) {
    std::fprintf(stderr,
                 "usage: %s <command> [args]\n"
                 "\n"
                 "commands:\n"
                 "  disasm <romfile>   print microcode disassembly (V20UC.TXT format)\n"
                 "  info   <romfile>   print ROM statistics\n"
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

int cmd_timed_boot(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr,
                     "usage: v30sim timed-boot <romfile> <image.bin> "
                     "[--clocks N] [--ndjson] [--waits N]\n");
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
    }
    return sim::run_timed_boot(rom, argv[1], clocks, stdout, opt);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return usage(argv[0]);
    const char* cmd = argv[1];
    if (std::strcmp(cmd, "disasm") == 0) return cmd_disasm(argc - 2, argv + 2);
    if (std::strcmp(cmd, "info") == 0) return cmd_info(argc - 2, argv + 2);
    if (std::strcmp(cmd, "run") == 0) return cmd_run(argc - 2, argv + 2);
    if (std::strcmp(cmd, "image") == 0) return cmd_image(argc - 2, argv + 2);
    if (std::strcmp(cmd, "trace") == 0) return cmd_trace(argc - 2, argv + 2);
    if (std::strcmp(cmd, "timed-run") == 0)
        return cmd_timed_run(argc - 2, argv + 2);
    if (std::strcmp(cmd, "timed-boot") == 0)
        return cmd_timed_boot(argc - 2, argv + 2);
    std::fprintf(stderr, "v30sim: unknown command '%s'\n", cmd);
    return usage(argv[0]);
}
