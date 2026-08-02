// timed_runner.h -- the `timed-run` subcommand: SingleStepTests cases in,
// per-clock row streams out.
//
// Case ingestion mirrors case_runner.cpp (JSON array or NDJSON on stdin, the
// same `initial.regs` / `initial.ram` / `initial.queue` / `iord` / `iords`
// fields), but NOTHING is compared here.  The output is the raw record stream
// plus the final architectural registers, and every comparison decision belongs
// to sw/timed_gate.py, which drives the UNMODIFIED sw/check_core.py machinery
// over it.  That is the same division of labour --emit-final already has with
// sw/ucsim_check.py.
//
// The run executes TWO instructions per case, because the golden cycle window
// closes on the FIRST QUEUE POP OF THE NEXT INSTRUCTION (tests/v30/v0.1
// README, "Trace window"); one instruction alone cannot produce the closing F.

#ifndef TIMED_RUNNER_H
#define TIMED_RUNNER_H

#include <cstdio>

#include "ucrom.h"

namespace sim {

struct TimedOptions {
    int waits = 0;          // uniform wait states per bus cycle
    bool ndjson = false;    // emitter (b): chip_rows NDJSON instead of text
    bool mirror = false;    // 64K-mirrored memory (the capture board's wiring)
    long only_idx = -1;     // run just this case index (-1 = all)
    int steps = 2;          // instructions executed per case
};

int run_timed(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
              const TimedOptions& opt);

}  // namespace sim

#endif  // TIMED_RUNNER_H
