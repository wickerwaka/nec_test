#!/usr/bin/env python3
"""tb_bootrun -- the RTL engine leg for the WHOLE-PROGRAM replay harnesses.

`sw/timed_enter_replay.py` and `sw/timed_ins_replay.py` drive a whole program
from RESET and score the bus stream it produces.  Until U3 they had one engine,
the C++ timed sim (`v30sim timed-boot`).  This module is the second engine and
NOTHING ELSE: it drives the verilated TB in its existing `+bootimg` mode and
returns rows in the SAME shape the sim's `--ndjson` emits, so a harness swaps
engines by swapping one call and changes no comparison, no window and no
column policy.

`sw/check_boot.py` is the reference for all of this (it has run both engines
against the boot capture since mission G); the plumbing here is its `run_sim`
generalised over the image, the clock budget and the wait source.

    rows = run_boot(image_bytes, clocks, td, waits=3)
    rows = run_boot(image_bytes, clocks, td, wrand=(wmax, wseed))
    rows = run_boot(image_bytes, clocks, td, wvec=[0, 2, 0, ...])

Row keys are the sim's: t, bs_early, qs, ube_n, ad_addr, ad_data, ps.

THE THREE DRIVER FACTS a caller has to know, because each is a property of the
DRIVERS and not of the part:

1. THE FRAME.  Both engines' row 0 is the clock at which RESET releases, and
   row i is the same clock in both.  MEASURED, not assumed: over the ENTER w0
   image the two 299-row streams agree on t/bs/qs/ube (and on addr at T1, data
   at T2/T3) in 299 of 299 rows, and their extracted transaction lists are
   identical.  `check_boot.py` scores the same alignment against silicon on
   both legs (220/220).

2. THE WINDOW.  The TB writes the record for the cycle that is ENDING, so a
   run of `+bootn=N` cycles emits N-1 rows; the sim emits exactly `--clocks`
   rows and then keeps its own trailing pad.  We therefore ask the TB for
   `clocks + PAD_CYCLES` and TRUNCATE to `clocks`, which makes both engines
   hand the harness a list of the same length covering the same clocks.  This
   is a window, NOT a mask: no row inside it is excluded from any comparison,
   and it exists only because the two drivers stop recording at different
   points past a run's close (ucore_provenance.md sec.42.2 makes the same
   distinction for `ulockstep`).

3. THE ADDRESS COLUMN off T1.  The TB's column 5 is the mid-cycle composed bus
   (`ad_mid`), so on T2/T3/T4 rows it carries the DATA phase, while the sim's
   `ad_addr` holds the cycle's T1 address for the whole cycle.  Both replay
   harnesses read `ad_addr` on T1 rows only (`fuzz_classify.extract_txns`,
   `causal_wrand.accesses`), which is `check_boot`'s column policy, so the
   difference is out of every scored column.  Do not start reading `ad_addr`
   off T1 without re-deriving this.

The 64 KB MIRROR is on by default because `run_timed_boot` has it wired on
unconditionally (`sim/timed_runner.cpp`: `biu.set_mirror(true); // the capture
board's 64 KB wiring`) -- these images are all captured-on-the-board programs.
The TB is flat 1 MB unless told otherwise, so the flag has to be passed.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent

# See note 2 above.  One is enough (the TB's record lag is exactly one cycle);
# four is what check_boot.py has always used, and the surplus is truncated.
PAD_CYCLES = 4


def tb_bin(core="ucore"):
    """The verilated TB for an engine, laid out as sw/check_core.py builds it
    (and named as sw/check_boot.py::_bin selects it)."""
    d = "obj_dir" if core == "fsm" else f"obj_dir_{core}"
    return ROOT / "hdl" / "tb" / d / "Vtb_v30_core"


def _hexfile(image, td, _seen={}):
    """$readmemh image, one byte per line.  Cached by content: the ENTER leg
    rebuilds a fresh image per case but the INS leg replays one image per seed
    over 200+ wait cells."""
    key = hashlib.sha1(image).hexdigest()
    p = _seen.get(key)
    if p is None or not Path(p).exists():
        p = str(Path(td) / f"img_{key[:12]}.hex")
        Path(p).write_text("\n".join(f"{b:02x}" for b in image) + "\n")
        _seen[key] = p
    return p


def run_boot(image, clocks, td, *, waits=0, wrand=None, wvec=None,
             core="ucore", mirror=True, evt=None):
    """Drive `image` from RESET through the verilated TB and return `clocks`
    rows.  Exactly one wait source, in the TB's own priority order: an explicit
    per-bus-cycle `wvec`, else a seeded random `wrand=(wmax, wseed)`, else
    uniform `waits`."""
    exe = tb_bin(core)
    if not exe.exists():
        sys.exit(f"tb_bootrun: {exe} not built")
    out = Path(td) / "tb_out.txt"
    argv = [str(exe), f"+bootimg={_hexfile(image, td)}",
            f"+bootn={clocks + PAD_CYCLES}", f"+out={out}"]
    if mirror:
        argv.append("+mirror=1")
    if wvec is not None:
        # The two drivers read the SAME vector through different readers: the
        # sim's is fscanf("%d") (sim/timed_runner.cpp) and the TB's is
        # $readmemh, so the TB's copy has to be written in HEX or every entry
        # >= 10 would be read as 0x10.. and the wait axis would silently shift.
        wv = Path(td) / "wvec_tb.hex"
        wv.write_text("\n".join(f"{int(x) & 31:02x}" for x in wvec) + "\n")
        argv.append(f"+wvec={wv}")
    elif wrand is not None:
        wmax, wseed = wrand
        # +wseed is read with %h; the sim's --wseed is strtoul(...,0), so the
        # same integer is spelled differently on the two command lines.
        argv += ["+wrand=1", f"+wmax={int(wmax)}", f"+wseed={int(wseed):04x}"]
    else:
        argv.append(f"+waits={int(waits)}")
    if evt:
        argv += list(evt)
    # cwd=ROOT: the ucore TB $readmemh's its microcode/decode tables by
    # REPO-RELATIVE path (hdl/rtl/ucore/ucrom.hex), and a run started anywhere
    # else comes up with an all-zero ROM and an idle bus rather than an error.
    r = subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT))
    if "BOOT DONE" not in r.stdout:
        sys.exit(f"tb_bootrun: boot run failed\n{r.stdout}\n{r.stderr}")
    rows = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            rows.append({"t": int(p[1]), "bs_early": int(p[2]),
                         "qs": int(p[3]), "ube_n": int(p[4]),
                         "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                         "ps": int(p[7], 16)})
    return rows[:clocks]          # the window (note 2)
