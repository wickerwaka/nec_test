// loader.cpp -- the FUNCTIONAL instantiation of the pre-decode hardware.
//
// The body moved to loader_impl.h (a template over the bus policy) for the
// ucsim-t timing campaign; this file exists to emit exactly one out-of-line
// copy for the functional bus, which is the shape every caller had before the
// split.

#include "loader_impl.h"

namespace sim {

template LoadResult loader_decode<Biu>(Machine&, Biu&);

}  // namespace sim
