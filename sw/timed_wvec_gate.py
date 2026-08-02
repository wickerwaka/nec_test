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

Usage:  python3 sw/timed_wvec_gate.py [--seeds ...] [--wvecs 0,1,2,3] [-v]
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

SIM = ROOT / "sim" / "v30sim"
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


def run_sim(seed, wv, nrows, td):
    image, _ = compose(generate(f"fz{seed}", exts=()))
    img = Path(td) / "img.bin"
    img.write_bytes(image)
    wvf = Path(td) / "wv.txt"
    wvf.write_text("\n".join(str(x) for x in wv) + "\n")
    r = subprocess.run([str(SIM), "timed-boot", str(ROM), str(img),
                        f"--clocks={nrows}", "--ndjson", f"--wvec={wvf}"],
                       capture_output=True)
    rows = [x for x in (json.loads(l)
                        for l in r.stdout.decode().splitlines()
                        if l.startswith("{")) if "t" in x]
    return rows[:nrows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="")
    ap.add_argument("--wvecs", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
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
                acc = accesses(run_sim(seed, wv_of(ws, wmax),
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
                    print(f"  {key}: accesses sim {len(acc)} ref "
                          f"{ref['accesses']}  sha {sha} != {ref['sha']}")

    print("== the wvec corpus through the timed sim, against "
          + ("the OLD TB baseline" if args.tb else "SILICON (T2b P2)") + " ==")
    print(f"  configs           {n}")
    print(f"  digest identical  {n_sha}/{n}")
    print(f"  access count      {n_acc}/{n}")
    print(f"  bus cycles: sim {pre_sum} vs reference {ref_sum}"
          f"  ({100.0 * pre_sum / ref_sum - 100:+.1f} %)")
    return 0 if n_sha == n else 1


if __name__ == "__main__":
    sys.exit(main())
