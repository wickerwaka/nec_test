// image_runner.h -- `v30sim image`: multi-instruction fuzz-bank image replay.
// See image_runner.cpp for the wire protocol.

#ifndef IMAGE_RUNNER_H
#define IMAGE_RUNNER_H

#include <cstdio>

#include "ucrom.h"

namespace sim {

struct ImageOptions {
    bool coverage = false;
    bool trace = false;
    long trace_idx = -1;
};

int run_images(const ucrom::UcRom& rom, std::FILE* in, std::FILE* out,
               const ImageOptions& opt);

}  // namespace sim

#endif  // IMAGE_RUNNER_H
