// disasm.h -- microcode ROM disassembly printer (golden: docs/V20UC.TXT).

#ifndef DISASM_H
#define DISASM_H

#include <cstdio>

namespace ucrom {

class UcRom;

// Writes the full disassembly listing, byte-for-byte compatible with the
// output of docs/V20UCDIS.PAS (CRLF line endings).
void disassemble(const UcRom& rom, FILE* out);

}  // namespace ucrom

#endif  // DISASM_H
