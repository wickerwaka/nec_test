#!/usr/bin/env python3
"""simbin -- THE SINGLE DECLARATION OF WHAT `v30sim` IS A FUNCTION OF.

`sw/artifact.py` is the layer; `docs/notes/artifact_receipt_layer.md` is its
spec.  This module is to the C++ model what `check_core.recipe()` is to the
Verilator TB: one place that says what the binary is built from, so that every
`--core sim` number in the ledger can name the bytes that produced it.

WHY IT EXISTS.  `ucore_provenance.md` §75.7 item **U1** named `sim/v30sim` as
THE LARGEST REMAINING HOLE in the artifact layer: seventeen tools ran it, every
`--core sim` figure in the ledger was scored against it, and its relationship to
`sim/*.cpp` was a `make` timestamp.  A stale `v30sim` was indistinguishable from
a fresh one.  That is the same bug as all seven incarnations -- *a file path is
not an identity*.


  §A  WHAT THE ARTIFACT IS A FUNCTION OF -- and the one that is not obvious

      sim/*.cpp, sim/*.h        the sources, including the GENERATED but
                                CHECKED-IN `pla3_table.h`
      sim/Makefile              it carries CXX and CXXFLAGS; a flag change is a
                                different binary
      docs/V20BITS.TXT          **THE MICROCODE ROM, AND IT IS READ AT RUN
                                TIME.**  `v30sim` takes the ROM as argv[1] --
                                every one of the seventeen consumers passes
                                `docs/V20BITS.TXT` and nothing else -- so under
                                a "files the command reads" rule the ROM the
                                entire model executes would sit OUTSIDE the
                                identity of every number ever scored against it.
                                This is erratum **E-1** exactly as it landed for
                                the ucore's `ucrom.hex` / `ucdecode.hex`
                                (§75.6a), reproduced here for the model:
                                `inputs` is what the ARTIFACT is a function of,
                                NOT what the COMMAND reads.

      NOT inputs: the per-invocation data files (`--wvec`, `--evt`, the image,
      a `biu-script`).  Those are the QUESTION, not the instrument.


  §B  WHY THE BINARY MOVED TO `sim/build/v30sim`

      `artifact.build()` PROMOTES by renaming its workdir, and the workdir is
      the artifact's parent directory.  With the artifact at `sim/v30sim` the
      workdir would be `sim/` -- i.e. a build would rename the source tree.  So
      the receipted binary lives in a directory of its own.  `sim/v30sim` is
      still what a bare `make -C sim` produces and is NOT consumed by any scorer
      any more.

      MEASURED at the migration, the §75.4 control: a full `make -B` into a
      scratch directory outside the repo reproduces the `sim/v30sim` that was on
      disk **byte for byte** (`cd2735e645a1cc35...`).  g++ 14 is byte-
      reproducible on this tree and output-path-independent, so the migration
      cannot move a number through a rebuild.


  §C  THE BUILD IS `make -B`, ON PURPOSE

      The layer's key is CONTENT; `make`'s is MTIME.  If the layer decides to
      build, it must not then hand the decision back to a weaker test: a source
      whose CONTENT changed under an unchanged mtime would move the build key,
      run `make`, and `make` would skip the object.  `-B` removes that seam at a
      cost of 2.9 seconds.

      `CXX=g++` is passed on the command line (a make command-line assignment
      beats both the environment and the Makefile's `?=`) so that the recorded
      `tool` probe is the compiler that actually ran.  `CXXFLAGS` / `LDFLAGS`
      cannot be pinned that way without duplicating the Makefile, so an
      environment override is REFUSED rather than silently omitted from the
      receipt -- see `_guard_env()`.
"""
import argparse
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import artifact as art                                        # noqa: E402

SIMDIR = ROOT / "sim"
BUILD = SIMDIR / "build"
SIM = BUILD / "v30sim"

# the two runtime tables of record.  ROM is an INPUT (§A); GOLDEN is the disasm
# gate's expected output and is not part of the binary's identity.
ROM = ROOT / "docs" / "V20BITS.TXT"
GOLDEN = ROOT / "docs" / "V20UC.TXT"

# `?=` in sim/Makefile means these silently win over it and would never appear
# in a receipt.  Refusing is three lines; omitting them is an incarnation.
_ENV_GUARD = ("CXXFLAGS", "LDFLAGS", "CXX")


def _guard_env():
    import os
    bad = [v for v in _ENV_GUARD if os.environ.get(v)]
    if bad:
        raise art.ArtifactError(art._shout(
            "BUILD ENVIRONMENT OVERRIDES sim/Makefile",
            [f"{v}={os.environ[v]!r}" for v in bad] +
            ["",
             "sim/Makefile declares these with `?=`, so the environment wins",
             "and the receipt would not record it.  Unset them and re-run."]))


def recipe():
    """WHAT `v30sim` IS A FUNCTION OF.  One declaration, all consumers."""
    inputs = (sorted(SIMDIR.glob("*.cpp")) + sorted(SIMDIR.glob("*.h")) +
              [SIMDIR / "Makefile", ROM])
    cmd = ["make", "-B", "-j8", "-C", art.TOK_ROOT + "/sim",
           "CXX=g++", "BIN=" + art.TOK_OUT + "/v30sim"]
    return art.Recipe(kind="cxx_binary", artifact=SIM, inputs=inputs,
                      command=cmd, tool="g++",
                      tool_probe=["g++", "--version"],
                      workdir=BUILD, label="v30sim")


def ensure(why="", force=False, quiet=True):
    """build-if-needed, then assert the scorer postcondition.  -> Path.

    What a `--core sim` gate calls, once, before it scores anything."""
    _guard_env()
    return art.ensure(recipe(), force=force, quiet=quiet,
                      why=why or "a --core sim scorer")


def require_bin(why=""):
    """P-2 only, for a consumer that must not build (a board sitting, a
    library import).  Raises naming what is stale.  -> Path."""
    art.require(SIM, why=why or "a --core sim scorer")
    return SIM


def receipt_id():
    """P-1: what a scorer prints beside its result."""
    return art.receipt_id(SIM)


# --------------------------------------------------------------------------- #
# the ROM/PLA disasm gate, ON THE RECEIPTED BINARY
#
# `make -C sim test` builds `sim/v30sim` by mtime and diffs its disassembly
# against docs/V20UC.TXT.  That is the same gate, on a binary with no receipt.
# This runs it on the binary the scorers actually execute.
# --------------------------------------------------------------------------- #
def disasm_gate():
    ensure(why="disasm gate")
    out = subprocess.run([str(SIM), "disasm", str(ROM)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        return 1
    want = GOLDEN.read_bytes().decode("latin-1")
    got = out.stdout
    if got.splitlines() != want.splitlines():
        n = sum(1 for a, b in zip(got.splitlines(), want.splitlines()) if a != b)
        print(f"disasm gate: FAIL -- {n} differing lines "
              f"({len(got.splitlines())} vs {len(want.splitlines())})")
        return 1
    print(f"disasm gate: PASS  ({len(want.splitlines())} rows)  "
          f"receipt {receipt_id()[:16]}...")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true",
                    help="build if the content key moved, then require()")
    ap.add_argument("--force", action="store_true", help="rebuild regardless")
    ap.add_argument("--require", action="store_true",
                    help="assert the postcondition only; never build")
    ap.add_argument("--disasm", action="store_true",
                    help="the ROM/PLA disasm gate on the RECEIPTED binary")
    ap.add_argument("--id", action="store_true", help="print the receipt id")
    args = ap.parse_args()
    if args.disasm:
        return disasm_gate()
    if args.require:
        require_bin(why="simbin --require")
        print(f"OK  {art.relpath(SIM)}  receipt {receipt_id()[:16]}...")
        return 0
    if args.id:
        rid = receipt_id()
        print(rid or "NO RECEIPT")
        return 0 if rid else 1
    ensure(why="simbin --build", force=args.force, quiet=False)
    print(f"OK  {art.relpath(SIM)}  receipt {receipt_id()[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
