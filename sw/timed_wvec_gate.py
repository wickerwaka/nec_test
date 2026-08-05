#!/usr/bin/env python3
"""timed_wvec_gate -- the frozen wvec corpus, replayed through the TIMED SIM.

`docs/notes/biu_rebuild_wvec_baseline.json` is the biu-rebuild campaign's
board-free cadence freeze: 22 fuzz seeds (the class5 corpus 90000-90019 plus
the two DIRECTED law seeds 90270 / 90364) x 4 explicit per-access wait vectors,
4200 CPU clocks each, digested as the per-bus-cycle stream

    bs , tw , addr , npops , gap-from-previous-T1

That digest is deliberately CADENCE-SENSITIVE -- the mutation battery proved an
identity-only digest is blind to +/-1-slot shifts (biu_law_cards.md B).  The
baseline was produced from the silicon-validated RTL, so it is a TBR-class
reference: matching it is matching the model the chip validated.

This harness recomputes exactly that digest from `v30sim timed-boot --wvec`
and reports, per config:

    sha       the whole 4200-clock digest is IDENTICAL (the hard gate)
    counts    the run's bus-cycle count against the reference's, which is the
              coarse whole-program cadence number the T3 stage needs

CAVEAT, established by building this (see ucsim_t_provenance.md 11.9): the
frozen baseline is DEGENERATE for two of its four wvec configs -- all 22
DIFFERENT programs share one digest at `ws7:wmax3` and one at `ws11:wmax7`,
which cannot happen and is the signature of the `wv_of` bug the law cards
themselves record.  Use `--wvecs 0,1` until the corpus is re-frozen.

That caveat is `--tb`-ONLY.  The T2b silicon freeze (the default reference) is
non-degenerate at ALL FOUR configs -- re-measured: 22 distinct shas over 22
seeds at each of ws0:wmax0, ws5:wmax1, ws7:wmax3 and ws11:wmax7 -- so the
default run scores all 88 cells and none of them is vacuous.

ENGINES (`--core`, U3): the digest, the reference baselines and the scoring are
IDENTICAL across all three legs -- the only thing `--core` changes is where the
per-bus-cycle row stream comes from.

    sim    (default) the C++ timed sim, `v30sim timed-boot --wvec`
    fsm    the verilated FSM core TB, hdl/tb/obj_dir/Vtb_v30_core
    ucore  the verilated ROM-driven core TB, hdl/tb/obj_dir_ucore/Vtb_v30_core

Usage:  python3 sw/timed_wvec_gate.py [--core sim|fsm|ucore] [--seeds ...]
                                      [--wvecs 0,1,2,3] [-v]
"""

import argparse
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

from causal_wrand import accesses                  # noqa: E402
from check_seq import compose                      # noqa: E402
from gen_seq import generate                       # noqa: E402

import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
BASE = ROOT / "docs" / "notes" / "biu_rebuild_wvec_baseline.json"
# T2b P2: the corpus RE-FROZEN AGAINST SILICON (sw/t2b_board.py p2).  The old
# TBR-class baseline above is degenerate at 2 of its 4 configs (11.9) and its
# whole-program counts are ~4x the chip's; the chip freeze is the reference of
# record from T2b on.  22 seeds x 4 wait vectors, socket, use_core=False, every
# cell bit-repeatable, the two directed law seeds promoted at 4 and 8 MHz.
CHIP = ROOT / "sw" / "testdata" / "t2b" / "p2-wvec" / "wvec_chip_baseline.json"


def wv_of(ws, wmax):
    """sw/biu_rebuild_wvec_freeze.py::wv_of, verbatim."""
    rr = random.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def parts_of(acc):
    """sw/biu_rebuild_wvec_freeze.py's normalisation, verbatim."""
    out, prev = [], None
    for a in acc:
        gap = "" if prev is None else str(a["t1"] - prev)
        out.append(f"{a['bs']},{a['tw']},{a['addr']},{a['npops']},g{gap}")
        prev = a["t1"]
    return out


def image_of(seed):
    image, _ = compose(generate(f"fz{seed}", exts=()))
    return image


def run_sim(seed, wv, nrows, td):
    img = Path(td) / "img.bin"
    img.write_bytes(image_of(seed))
    wvf = Path(td) / "wv.txt"
    wvf.write_text("\n".join(str(x) for x in wv) + "\n")
    r = subprocess.run([str(SIM), "timed-boot", str(ROM), str(img),
                        f"--clocks={nrows}", "--ndjson", f"--wvec={wvf}"],
                       capture_output=True)
    rows = [x for x in (json.loads(l)
                        for l in r.stdout.decode().splitlines()
                        if l.startswith("{")) if "t" in x]
    return rows[:nrows]


_WVEC_REQUIRED = set()


def tb_bin(core):
    """sw/check_boot.py::_bin, verbatim: the two RTL engines are drop-in
    alternatives built into separate obj_dirs by sw/check_core.py."""
    d = "obj_dir" if core == "fsm" else f"obj_dir_{core}"
    b = ROOT / "hdl" / "tb" / d / "Vtb_v30_core"
    # THE SCORER POSTCONDITION (sw/artifact.py), once per core per process.
    if core not in _WVEC_REQUIRED and b.exists():
        import artifact as art                              # noqa: PLC0415
        art.require(b, why=f"timed_wvec_gate --core {core}")
        # P-1: a number with no artifact id is not quotable.
        print(f"  RTL leg {art.relpath(b)}  receipt "
              f"{str(art.receipt_id(b))[:16]}…", file=sys.stderr,
              flush=True)
        _WVEC_REQUIRED.add(core)
    return b


def run_tb(core, seed, wv, nrows, td):
    """The SAME corpus through the verilated TB in +bootimg mode, framed to
    match run_sim() clock for clock.

    Three driver-level (NOT part-level) settings make the two engines the same
    rig; each one mirrors a line of sim/timed_runner.cpp::run_timed_boot:

      +mirror=1   `biu.set_mirror(true);  // the capture board's 64 KB wiring`.
                  The TB memory is 1 MB FLAT since c78421fe07, so without this
                  the reset vector at FFFF0 reads unwritten memory (the same
                  trap sw/check_boot.py documents).
      IOR / INTA  the TB's own defaults already ARE the sim's measured rig
                  constants (iord_r = FFFF -> `biu.set_io_in(0xFFFF)`,
                  INT_VECTOR = FF -> `biu.set_inta(0x00FF)`), so nothing to set.
      +bootn      slack, then slice.  Both engines start recording at the same
                  event (RESET release; row 0 is release+0 in both), but they
                  do NOT record the same number of TRAILING clocks for a given
                  budget: `--clocks=N` yields N rows, `+bootn=N` yields N-1
                  (the TB's final clock's record is dropped as `recording`
                  clears).  So ask the TB for slack and cut BOTH legs to
                  exactly `nrows`.  This is a property of the two DRIVERS, not
                  of the part -- the same class of comparison window
                  ucore_provenance.md 42.2 documents for `ulockstep` -- and it
                  is not a mask: no column is dropped and no row inside the
                  window is exempt.  Verified: over fz90000:ws0:wmax0 all 4063
                  in-window rows agree on t / bs_early / qs 1:1 between the two
                  legs, and the ONLY differing column is `ad_addr` on non-T1
                  rows, which is float retention the two rigs prime differently
                  (42.6) and which the digest never reads.
    """
    img = Path(td) / "img.hex"
    img.write_text("\n".join(f"{b:02x}" for b in image_of(seed)) + "\n")
    wvf = Path(td) / "wv.hex"
    wvf.write_text("\n".join(f"{min(255, max(0, int(x))):02x}" for x in wv)
                   + "\n")
    out = Path(td) / "tb_out.txt"
    r = subprocess.run([str(tb_bin(core)), f"+bootimg={img}",
                        f"+bootn={nrows + 4}", "+mirror=1", f"+wvec={wvf}",
                        f"+out={out}"],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError(f"TB({core}) failed: "
                           f"{r.stdout[-300:]} {r.stderr[-200:]}")
    rows = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            rows.append({"t": int(p[1]), "bs_early": int(p[2]),
                         "qs": int(p[3]), "ube_n": int(p[4]),
                         "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                         "ps": int(p[7], 16)})
    if len(rows) < nrows:
        raise RuntimeError(f"TB({core}) returned {len(rows)} rows, "
                           f"window needs {nrows}")
    return rows[:nrows]


def run_engine(core, seed, wv, nrows, td):
    return (run_sim if core == "sim" else
            (lambda *a: run_tb(core, *a)))(seed, wv, nrows, td)


def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="")
    ap.add_argument("--wvecs", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--core", choices=("sim", "fsm", "ucore"), default="sim",
                    help="which engine produces the per-bus-cycle stream "
                         "(digest/baseline/scoring are identical for all)")
    ap.add_argument("--tb", action="store_true",
                    help="score against the OLD TBR baseline instead of the "
                         "T2b silicon freeze (11.9: half of it is vacuous)")
    args = ap.parse_args()

    base = json.loads((BASE if args.tb else CHIP).read_text())
    seeds = ([int(x) for x in args.seeds.split(",") if x]
             if args.seeds else base["seeds"])
    wvecs = base["wvecs"]
    if args.wvecs:
        wvecs = [wvecs[int(i)] for i in args.wvecs.split(",") if i != ""]
    nrows = base["nrows"]

    n_sha = n_acc = n = 0
    pre_sum = ref_sum = 0
    with tempfile.TemporaryDirectory() as td:
        for seed in seeds:
            for ws, wmax in wvecs:
                key = f"fz{seed}:ws{ws}:wmax{wmax}"
                ref = base["cases"].get(key)
                if not ref:
                    continue
                # score over the CHIP capture's own clock window
                acc = accesses(run_engine(args.core, seed, wv_of(ws, wmax),
                                          ref.get("rows", nrows), td))
                parts = parts_of(acc)
                sha = hashlib.sha256(";".join(parts).encode()).hexdigest()[:16]
                n += 1
                n_sha += (sha == ref["sha"])
                n_acc += (len(acc) == ref["accesses"])
                # the agreement prefix needs the reference's own parts, which
                # the freeze does not store -- so report it only against the
                # access COUNT and the first-divergence position we can see
                # (identical shas => full agreement).
                pre_sum += len(acc)
                ref_sum += ref["accesses"]
                if args.verbose and sha != ref["sha"]:
                    print(f"  {key}: accesses {args.core} {len(acc)} ref "
                          f"{ref['accesses']}  sha {sha} != {ref['sha']}")

    eng = {"sim": "the timed sim", "fsm": "the FSM core TB",
           "ucore": "the ucore TB"}[args.core]
    print(f"== the wvec corpus through {eng}, against "
          + ("the OLD TB baseline" if args.tb else "SILICON (T2b P2)") + " ==")
    print(f"  configs           {n}")
    print(f"  digest identical  {n_sha}/{n}")
    print(f"  access count      {n_acc}/{n}")
    print(f"  bus cycles: {args.core} {pre_sum} vs reference {ref_sum}"
          f"  ({100.0 * pre_sum / ref_sum - 100:+.1f} %)")
    return 0 if n_sha == n else 1


if __name__ == "__main__":
    sys.exit(main())
