#!/usr/bin/env python3
"""check_ff_t4 - standing reachability gate for the far-flush direct-commit
slots (task #28).

The R6c ordering regression (614ce0a) broke the SLOT_FF_T4 direct commit
while every standing suite stayed green: the slot never fires in the
single-instruction corpora, so its breakage was invisible. This gate pins
reachability: a fixed set of check_seq fuzz seeds whose TB replay is KNOWN
to fire SLOT_FF_T4 (far flush landing on a prefetch T4, w0), plus the
sim-only invariant that a direct commit's ST_T1 survives (v30_biu
dbg_direct_q assert, compiled under the always-on --assert build).

PASS requires, for every seed:
  - the TB run completes (no assert abort), and
  - cov_ff_t4 >= 1 (the slot actually fired - non-vacuous by construction).

If an RTL change legitimately moves the flush geometry so a seed stops
firing, re-hunt replacements (the hunt recipe is in the task #28 ledger:
scan check_seq seeds with exts farjmp,farcall,callret and read the TB cov
line) - do NOT delete seeds to make the gate pass.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import check_seq                                       # noqa: E402
from gen_seq import generate                           # noqa: E402

BIN = ROOT / "hdl" / "tb" / "obj_dir" / "Vtb_v30_core"

# Hunted 2026-07-26 on 614ce0a (scan fz0-fz299): each fires SLOT_FF_T4
# exactly once at w0. Frozen census; see module docstring before editing.
SEEDS = ("fz6", "fz104", "fz116", "fz147", "fz156", "fz159",
         "fz169", "fz245", "fz281")
EXTS = ("farjmp", "farcall", "callret")


def run_seed(seed):
    g = generate(seed, exts=EXTS)
    image, _meta = check_seq.compose(g)
    with tempfile.TemporaryDirectory(prefix="fft4_") as td:
        img = Path(td) / "img.hex"
        out = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image) * 16)
                       + "\n")
        r = subprocess.run([str(BIN), f"+bootimg={img}", "+bootn=4200",
                            "+waits=0", f"+out={out}"],
                           capture_output=True, text=True, cwd=ROOT,
                           timeout=300)
    done = "BOOT DONE" in r.stdout
    m = re.search(r"COV ff_t4=(\d+) ff_ti=(\d+)", r.stdout)
    ff_t4 = int(m.group(1)) if m else -1
    ff_ti = int(m.group(2)) if m else -1
    return done, ff_t4, ff_ti, r.stderr[-200:] if not done else ""


def main():
    if not BIN.exists():
        print("check_ff_t4: TB binary missing - run check_core.py --build")
        return 2
    bad = 0
    total_t4 = 0
    for seed in SEEDS:
        done, ff_t4, ff_ti, tail = run_seed(seed)
        ok = done and ff_t4 >= 1
        total_t4 += max(0, ff_t4)
        if not ok:
            bad += 1
            print(f"  {seed}: FAIL done={done} cov_ff_t4={ff_t4} "
                  f"cov_ff_ti={ff_ti} {tail}")
    if bad:
        print(f"check_ff_t4: FAIL ({bad}/{len(SEEDS)} seeds; a completed "
              f"run with cov_ff_t4=0 means the slot went unreachable - "
              f"re-hunt, do not drop seeds)")
        return 1
    print(f"check_ff_t4: PASS ({len(SEEDS)}/{len(SEEDS)} seeds complete, "
          f"{total_t4} SLOT_FF_T4 fires, invariant assert armed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
