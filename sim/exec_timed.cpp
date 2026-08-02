// exec_timed.cpp -- see exec_timed.h.  The single out-of-line copy of the
// interpreter and the pre-decode hardware for the TIMED bus.

#include "exec_timed.h"

namespace sim {

template LoadResult loader_decode<BiuTimed>(Machine&, BiuTimed&);
template class CpuT<BiuTimed>;

}  // namespace sim
