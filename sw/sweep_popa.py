#!/usr/bin/env python3
"""sweep_popa - Campaign 5 fit: the POPA (0x61) read-start commit-phase
matrix.

POPA's 8-word stack read burst starts 2 cycles late on the core at some
prefetch phases. The dispatch's existing `bus_phase ? S_61G : S_61W`
2-way split (pop+2 vs pop+3) does not capture the full queue-fill-phase
law. This tool measures the chip's exact read-start (first MEMR T1 cycle
index, and its offset from the opcode-pop cycle) as a function of the
prefetch phase (NOP sled length) and queue-fill, running identical
micro-sequences on BOTH A/B positions of the harness.

Micro-sequence: N*NOP (N=phase) + 0x61 (POPA) + 4*NOP at the standard
anchor. SP preset into the stack window so the 8 reads land at a known
even address (first read = SS:SP).

Usage:
  sweep_popa.py [--phases 0-11] [--host H] [--out F]
  sweep_popa.py --tb     (core side from the Verilator TB, pre-flash)
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                                    # noqa: E402
from v30run import run_image                        # noqa: E402

ROOT = SW.parent
BIN = ROOT / "hdl" / "tb" / "obj_dir" / "Vtb_v30_core"

SP0 = 0x3E80             # even, inside the stack window; first read here


def build_image(phase):
    instr = b"\x90" * phase + b"\x61" + b"\x90" * 4
    regs = {"SS": 0, "SP": SP0, "DS0": 0, "DS1": 0, "PSW": 0xF202}
    ram = [(a, (a * 5 + 1) & 0xFF) for a in range(0x3E00, 0x3F80)]
    return testimage.compose(regs=regs, instr=instr, ram=ram)


def run_board(image, host, use_core, waits):
    recs = run_image(bytes(image), host, tag="popa", waits=waits,
                     use_core=use_core)
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    return recs[rel:]


def run_tb(image, waits, eudbg=False):
    td = tempfile.mkdtemp(prefix="popa_")
    img = Path(td) / "img.hex"
    out = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in image) + "\n")
    args = [str(BIN), f"+bootimg={img}", "+bootn=4200",
            f"+out={out}", f"+waits={waits}"]
    if eudbg:
        args.append("+eudbg")
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                       timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError(f"TB failed: {r.stdout[-200:]}")
    sim = []
    dbg = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            sim.append({"t": int(p[1]), "bs_early": int(p[2]),
                        "qs": int(p[3]), "ube_n": int(p[4]),
                        "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                        "ps": int(p[7], 16)})
        elif p and p[0] == "d":
            dbg.append(p[1:])
    return (sim, dbg) if eudbg else sim


def first_read_t1(recs):
    """Cycle index of the first POPA MEMR T1 at SS:SP (=SP0)."""
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] in (5, 6) and \
                (r["ad_addr"] & 0xFFFFF) == SP0:
            return i
    return None


def policy_diff(a, b):
    import check_seq
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        bad, first, n, flick = check_seq.diff(a, b, maxprint=0)
    return bad, first, n, flick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--phases", default="0-11")
    ap.add_argument("--waits", default="0")
    ap.add_argument("--tb", action="store_true")
    ap.add_argument("--out", default="/tmp/popaphase.tsv")
    a = ap.parse_args()

    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    waits_l = [int(x) for x in a.waits.split(",")]

    rows = []
    print(f"{'ph':2} {'w':1} {'chipT1':6} {'coreT1':6} {'d':>3} "
          f"{'diff':>4} {'first':>5}")
    for w in waits_l:
        for ph in phases:
            image, _ = build_image(ph)
            chip = run_board(image, a.host, False, w)
            core = run_tb(image, w) if a.tb else run_board(image, a.host, True, w)
            ct1 = first_read_t1(chip)
            kt1 = first_read_t1(core)
            bad, first, n, flick = policy_diff(chip, core)
            d = (kt1 - ct1) if (ct1 is not None and kt1 is not None) else None
            print(f"{ph:2} {w:1} {str(ct1):6} {str(kt1):6} {str(d):>3} "
                  f"{bad:>4} {str(first):>5}"
                  + (f" [+{flick}fl]" if flick else ""))
            rows.append((ph, w, ct1, kt1, d, bad, first))
    with open(a.out, "w") as f:
        f.write("phase\twaits\tchip_t1\tcore_t1\tdelta\tdiff\tfirst\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    ndiv = sum(1 for r in rows if r[5])
    print(f"\n{len(rows)} cells, {ndiv} divergent -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
