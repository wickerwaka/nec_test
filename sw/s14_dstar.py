#!/usr/bin/env python3
"""s14_dstar -- is `H - anchor` = 8, 12, 14, 16 just the FETCH PITCH?
(ucsim_t_provenance 25.5)

OFFLINE, chip only, no model anywhere.  Reads the banked S2 (w0/w1) and S13
(w2/w3) captures and prints every bus cycle between the trigger anchor and the
HALT status display, with the T1-to-T1 PITCH between them.

24.8 recorded the anchor-to-HALT-display distance as MEASURED with its
mechanism OPEN, and read the `+4, +2, +2` step as "one slot on the 2-clock
eval grid".  This says what it actually is.
"""
import gzip
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import s12_census as sc                                    # noqa: E402

# --- fuzz-v2 T12: RETIRED, not broken.  See sw/retired_v1.py. -----------
import retired_v1  # noqa: E402
retired_v1.retire(
    's14_dstar.py',
    'S14 d* measurement tool (NOT a gate)',
    'reaches compose(stub_linear=) transitively through s12_census.case_of; a measurement tool of a closed sitting',
    None)
# ------------------------------------------------------------------------


S2 = ROOT / "sw/testdata/s10/s2-hltsweep"
S13 = ROOT / "sw/testdata/s13/p1b-ahsweep"


def main():
    for form in ("HLT.INT", "HLT.RES"):
        _spec, _case, _img, meta = sc.case_of(form, "v30-s10-hlt")
        anchor_lin = meta["anchor_linear"]
        for w, d in ((0, S2), (1, S2), (2, S13), (3, S13)):
            # any delay well ABOVE d* -- the program is the same at every
            # delay and the wake plays no part in the pre-HALT stretch
            for delay in (30, 24, 20):
                p = d / f"{form}_w{w}_d{delay}.rows.json.gz"
                if p.exists():
                    break
            rows = json.load(gzip.open(p))
            cyc = sc.cycles(rows)
            hd = next(i for i, r in enumerate(rows) if r["bs_early"] == 3)
            anchor = next(c["t1"] for c in cyc
                          if c["kind"] == "CODE" and c["addr"] == anchor_lin)
            # `t1` is None for an announcement the part displayed and never
            # took a T1 for (s12_census.cycles, 24.1); the pre-HALT stretch has
            # none, and skipping them keeps this listing the T1-to-T1 pitch it
            # has always been.
            seq = [c for c in cyc
                   if c["t1"] is not None and anchor <= c["t1"] <= hd + 2]
            print(f"{form} w{w} (d={delay})  anchor T1={anchor}  "
                  f"HALT display H={hd}   H-anchor={hd - anchor}")
            prev = None
            for c in seq:
                pitch = "" if prev is None else f"   pitch {c['t1'] - prev}"
                print("    %-5s T1=%-4d T4=%-4s len=%-3s addr=%05X%s"
                      % (c["kind"], c["t1"], c["t4"],
                         (c["t4"] - c["t1"] + 1) if c["t4"] else "?",
                         c["addr"], pitch))
                prev = c["t1"]
        print()


main()
