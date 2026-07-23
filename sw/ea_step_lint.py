#!/usr/bin/env python3
"""F4a standing source-level lint (runs with ss_lint in the standing gate set).

Every "next word of the same segmented operand" step of eu_addr MUST wrap its
16-bit offset via ea_step2() -- a linear `eu_addr <= eu_addr + N` carries across
offset 0xFFFF->0x0000 into the segment base (the F4a bug). This lint fails if any
eu_addr arithmetic-step pattern appears in v30_eu.sv OUTSIDE the blessed set:

  - the IVT high-word read (S_TRAP): deliberately LINEAR (page-0 physical, not a
    segmented operand) -- blessed by its `// vector high word` comment.

Everything else that steps eu_addr must be `eu_addr <= ea_step2(eu_addr, <seg>)`.
The architect chose this over a runtime assertion: a coherent runtime check needs
a per-eu_addr-assignment latched segbase whose hand-maintenance lapse is exactly
the hazard, and a false-firing $error is worse than none. A source lint has no
runtime state and catches a missed consumer that no golden happens to exercise
(this lint's first run caught the double-space INS split w0->w1 site).

Exit 0 = clean, non-zero = a stray step. No build required.
"""
import re
import sys
from pathlib import Path

EU = Path(__file__).resolve().parent.parent / "hdl/rtl/core/v30_eu.sv"

# a linear self-increment of eu_addr: `eu_addr <= eu_addr + <expr>` (any spacing)
STEP = re.compile(r"eu_addr\s*<=\s*eu_addr\s*\+")
# blessed: the deliberately-linear IVT high-word read
BLESSED = re.compile(r"//.*vector high word")


def main():
    strays = []
    for n, line in enumerate(EU.read_text().splitlines(), 1):
        if STEP.search(line) and not BLESSED.search(line):
            strays.append((n, line.strip()))
    if strays:
        print("ea_step_lint: FAIL -- eu_addr stepped linearly outside ea_step2 "
              "(F4a segment-offset-wrap hazard):")
        for n, l in strays:
            print(f"  v30_eu.sv:{n}: {l}")
        print("  Fix: use `eu_addr <= ea_step2(eu_addr, <seg>);` (or, if the "
              "access is genuinely a linear page-0 read like the IVT, add a "
              "`// vector high word` no-wrap comment on the line).")
        return 1
    print("ea_step_lint: PASS (all eu_addr operand steps wrap via ea_step2; "
          "only the IVT high-word read is linear, by design)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
