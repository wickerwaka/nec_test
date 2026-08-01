// main.cpp -- v30sim CLI dispatcher.
//
// Subcommands:
//   disasm <romfile>   disassemble the EU microcode ROM (docs/V20BITS.TXT)
//   info   <romfile>   summarise ROM contents and micro-address coverage
//
// `run` and `trace` will be added as the simulator core lands.

#include <cstdio>
#include <cstring>
#include <string>

#include "disasm.h"
#include "ucrom.h"

namespace {

int usage(const char* argv0) {
    std::fprintf(stderr,
                 "usage: %s <command> [args]\n"
                 "\n"
                 "commands:\n"
                 "  disasm <romfile>   print microcode disassembly (V20UC.TXT format)\n"
                 "  info   <romfile>   print ROM statistics\n",
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

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return usage(argv[0]);
    const char* cmd = argv[1];
    if (std::strcmp(cmd, "disasm") == 0) return cmd_disasm(argc - 2, argv + 2);
    if (std::strcmp(cmd, "info") == 0) return cmd_info(argc - 2, argv + 2);
    std::fprintf(stderr, "v30sim: unknown command '%s'\n", cmd);
    return usage(argv[0]);
}
