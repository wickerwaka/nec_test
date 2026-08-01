// case_runner.h -- SingleStepTests case ingestion and verdicts.
//
// Reads a JSON array (or NDJSON, one case per line) on stdin, executes ONE
// instruction per case and compares the architectural final state:
//   * registers, including the RAW PSW (sparse-delta reconstruction: the
//     expected value is `initial.regs` updated by `final.regs`);
//   * RAM, reconstructed from the ordered write stream exactly the way
//     sw/check_core.py::check_case does it;
//   * queue comparison is DEFERRED (see docs/notes/ucsim_provenance.md); the
//     bytes the decoder consumed are reported instead.
//
// Cases carrying an `evt` (pin-event pseudo-forms INT.* / NMI.* / HLT.*) run
// the FUNCTIONAL external-event model: instructions retire until the golden's
// recorded firing boundary is reached, then the hardware interrupt entry runs.
// WHICH boundary fired is REPLAYED from the golden (see derive_replay below and
// docs/notes/ucsim_provenance.md); every architectural consequence -- the
// acknowledge, the vector fetch, the pushed frame, the resume PC, the final
// state -- is computed by the simulator.

#ifndef CASE_RUNNER_H
#define CASE_RUNNER_H

#include <cstdio>
#include <string>

#include "ucrom.h"

namespace sim {

struct RunOptions {
    bool check_queue = false;
    // Emit the architectural result of every case as one compact NDJSON record
    // instead of an in-C++ verdict; sw/ucsim_check.py owns the comparison
    // policy (flags masks, don't-cares, pushed-PSW derivation, RAM fallback).
    bool emit_final = false;
    // 64K-mirrored memory model (the capture board's real wiring).
    bool mirror = false;
    int max_report = 8;   // per-run failure details printed to stderr
    long trace_idx = -1;  // `trace` mode: only this case index
    bool trace = false;
    // Audit switch: attribute the FINAL PSW bits of every case to the three
    // non-emergent ALU-hardware behaviours (per-step shift V law, logic-op
    // AC = 0, BCD correction).  Everything not attributed emerged from the
    // microcode ROM alone.  Printed as one extra summary record.
    bool alu_hw_report = false;
};

// Returns the process exit code (0 = all cases passed).
int run_cases(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
              const RunOptions& opt);

}  // namespace sim

#endif  // CASE_RUNNER_H
