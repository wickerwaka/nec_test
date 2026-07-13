#!/usr/bin/env python3
"""sweep_dispphase - Campaign 4 Mission D: the disp-reader commit-phase
matrix.

The Mission S blocker: a disp8/disp16-form reader whose EU read becomes
ready exactly on a prefetch T3 commits there on the core, but the chip
defers (~2 cycles observed), in a phase- and segment-prefix-dependent way
(no-prefix disp16 matched at all phases; 3e:disp16 and 3e:mod1-disp8
diverged). This tool measures the chip's exact deferral law directly by
running identical micro-sequences on BOTH A/B positions of the harness
(CFG.use_core 0/1) and reporting, per cell:

  (EA-mode x prefix x queue-fill phase x waits) ->
      reader MEMR T1 cycle index on chip and on core, their delta,
      and the policy-diff row count between the full traces.

Micro-sequence: N*NOP (N = phase 0..7) + [prefix] + reader + 4*NOP, at
the standard test-image anchor (testimage.compose, PS:PC = 0000:0100),
store stub falls through after. The reader's data read targets a fixed
even address in the data window so its MEMR T1 row is unambiguous.

EA modes (reader = MOV AX,form / load-op ALU as noted):
  disp16      8B 06 <ea16>      MOV AX,[disp16]     (mod0 rm6)
  disp8bx     8B 47 <d8>        MOV AX,[BX+d8]      (mod1 rm7, BX preset)
  disp8bp     8B 46 <d8>        MOV AX,[BP+d8]      (mod1 rm6, SS-based)
  alu16       03 06 <ea16>      ADD AX,[disp16]     (load-op)
Prefixes: none, 3E (DS:), 26 (ES:).

Usage:
  sweep_dispphase.py [--phases 0-7] [--waits 0,1] [--host H] [--out F]
  sweep_dispphase.py --tb        (core side from the Verilator TB instead
                                  of use_core=1 - pre-flash dry run)
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

TGT_EA = 0x2482          # even, inside gen_seq's prefilled data window
BX0 = 0x2440
BP0 = 0x2440
D8 = TGT_EA - BX0        # 0x42

EA_MODES = {
    "disp16":  bytes([0x8B, 0x06, TGT_EA & 0xFF, TGT_EA >> 8]),
    "disp8bx": bytes([0x8B, 0x47, D8]),
    "disp8bp": bytes([0x8B, 0x46, D8]),
    "alu16":   bytes([0x03, 0x06, TGT_EA & 0xFF, TGT_EA >> 8]),
}
PREFIXES = {"none": b"", "3e": b"\x3e", "26": b"\x26"}


def build_image(ea, prefix, phase):
    instr = b"\x90" * phase + PREFIXES[prefix] + EA_MODES[ea] + b"\x90" * 4
    regs = {"BW": BX0, "BP": BP0, "SS": 0, "SP": 0x3F00,
            "DS0": 0, "DS1": 0, "PSW": 0xF202}
    ram = [(a, (a * 7 + 3) & 0xFF) for a in range(0x2400, 0x2500)]
    ram += [(a, (a * 5 + 1) & 0xFF) for a in range(0x3E00, 0x3F80)]
    return testimage.compose(regs=regs, instr=instr, ram=ram)


def run_board(image, host, use_core, waits):
    recs = run_image(bytes(image), host, tag="disp", waits=waits,
                     use_core=use_core)
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    return recs[rel:]


def run_tb(image, waits):
    td = tempfile.mkdtemp(prefix="disp_")
    img = Path(td) / "img.hex"
    out = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in image) + "\n")
    r = subprocess.run([str(BIN), f"+bootimg={img}", "+bootn=4200",
                        f"+out={out}", f"+waits={waits}"],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError(f"TB failed: {r.stdout[-200:]}")
    sim = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            sim.append({"t": int(p[1]), "bs_early": int(p[2]),
                        "qs": int(p[3]), "ube_n": int(p[4]),
                        "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                        "ps": int(p[7], 16)})
    return sim


def reader_t1(recs):
    """Cycle index of the reader's MEMR T1 at the target address."""
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and r["bs_early"] == 5 and \
                (r["ad_addr"] & 0xFFFFF) == TGT_EA:
            return i
    return None


def policy_diff(a, b):
    """check_boot-policy diff row count over the compared window."""
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
    ap.add_argument("--phases", default="0-7")
    ap.add_argument("--waits", default="0,1")
    ap.add_argument("--ea", default=",".join(EA_MODES))
    ap.add_argument("--prefix", default=",".join(PREFIXES))
    ap.add_argument("--tb", action="store_true",
                    help="core side = Verilator TB (pre-flash dry run)")
    ap.add_argument("--out", default="/tmp/dispphase.tsv")
    a = ap.parse_args()

    lo, hi = (a.phases.split("-") + [a.phases.split("-")[0]])[:2]
    phases = range(int(lo), int(hi) + 1)
    waits_l = [int(x) for x in a.waits.split(",")]
    eas = a.ea.split(",")
    prefixes = a.prefix.split(",")

    rows = []
    print(f"{'ea':8} {'pfx':4} {'ph':2} {'w':1} {'chipT1':6} {'coreT1':6} "
          f"{'d':>3} {'diff':>4} {'first':>5}")
    for w in waits_l:
        for ea in eas:
            for pfx in prefixes:
                for ph in phases:
                    image, _ = build_image(ea, pfx, ph)
                    chip = run_board(image, a.host, False, w)
                    if a.tb:
                        core = run_tb(image, w)
                    else:
                        core = run_board(image, a.host, True, w)
                    ct1 = reader_t1(chip)
                    kt1 = reader_t1(core)
                    bad, first, n, flick = policy_diff(chip, core)
                    d = (kt1 - ct1) if (ct1 is not None and kt1 is not None) \
                        else None
                    print(f"{ea:8} {pfx:4} {ph:2} {w:1} "
                          f"{str(ct1):6} {str(kt1):6} {str(d):>3} "
                          f"{bad:>4} {str(first):>5}"
                          + (f" [+{flick}fl]" if flick else ""))
                    rows.append((ea, pfx, ph, w, ct1, kt1, d, bad, first))
    with open(a.out, "w") as f:
        f.write("ea\tpfx\tphase\twaits\tchip_t1\tcore_t1\tdelta\tdiff\tfirst\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    ndiv = sum(1 for r in rows if r[7])
    print(f"\n{len(rows)} cells, {ndiv} divergent -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
