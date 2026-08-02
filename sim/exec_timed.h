// exec_timed.h -- the TIMED interpreter instantiation.
//
// Same interpreter as exec.h (`sim::CpuT<Bus>` in exec_impl.h), bound to the
// timed bus instead of the functional one.  Nothing about the micro-sequencing
// changes: the ROM walk, the F interlock, the write-data pairing and the queue
// pops are the same code, and the bus policy decides whether an access takes
// zero time or a modelled number of clocks.

#ifndef EXEC_TIMED_H
#define EXEC_TIMED_H

#include "biu_timed.h"
#include "exec_impl.h"

namespace sim {

extern template class CpuT<BiuTimed>;

using CpuTimed = CpuT<BiuTimed>;

}  // namespace sim

#endif  // EXEC_TIMED_H
