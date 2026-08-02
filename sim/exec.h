// exec.h -- the FUNCTIONAL interpreter instantiation.
//
// The interpreter itself is `sim::CpuT<Bus>` in exec_impl.h (a template over
// the bus policy, ucsim-t T0).  This header binds it to the functional bus
// `sim::Biu` and names the result `sim::Cpu`, which is what every existing
// driver (case_runner, image_runner) uses -- unchanged.
//
// The explicit-instantiation DECLARATION below is load-bearing: it stops every
// translation unit that merely *uses* `Cpu` from instantiating the interpreter
// for itself, so the whole functional build keeps calling the single
// out-of-line copy that exec.cpp emits.  That is the codegen shape the
// interpreter had before the policy split, which is why the split is a
// zero-behaviour, zero-perf-change refactor.

#ifndef EXEC_H
#define EXEC_H

#include "biu.h"
#include "exec_impl.h"

namespace sim {

extern template class CpuT<Biu>;

using Cpu = CpuT<Biu>;

}  // namespace sim

#endif  // EXEC_H
