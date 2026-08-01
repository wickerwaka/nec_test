// main.cpp -- v30sim CLI dispatcher.
//
// Subcommands:
//   disasm <romfile>   disassemble the EU microcode ROM (docs/V20BITS.TXT)
//   info   <romfile>   summarise ROM contents and micro-address coverage
//   run    <romfile>   execute SingleStepTests cases from stdin (NDJSON out)
//   trace  <romfile> <idx>  per-micro-row dump of ONE case (to stderr)

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "case_runner.h"
#include "disasm.h"
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
                 "  trace  <romfile> <idx>      trace one case from stdin\n",
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

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return usage(argv[0]);
    const char* cmd = argv[1];
    if (std::strcmp(cmd, "disasm") == 0) return cmd_disasm(argc - 2, argv + 2);
    if (std::strcmp(cmd, "info") == 0) return cmd_info(argc - 2, argv + 2);
    if (std::strcmp(cmd, "run") == 0) return cmd_run(argc - 2, argv + 2);
    if (std::strcmp(cmd, "trace") == 0) return cmd_trace(argc - 2, argv + 2);
    std::fprintf(stderr, "v30sim: unknown command '%s'\n", cmd);
    return usage(argv[0]);
}
