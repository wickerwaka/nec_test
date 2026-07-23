#!/usr/bin/env python3
"""Standing exhaustive and reproducibility gate for race_law.svh."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEX = ROOT / "hdl/rtl/core/int9d_race.hex"
LAW = ROOT / "hdl/rtl/core/race_law.svh"
GENERATOR = ROOT / "sw/gen_race_law.py"
TB = ROOT / "sw/race_law_equiv_tb.sv"
DIGEST_RE = re.compile(r"^// int9d_race\.hex SHA-256: ([0-9a-f]{64})$", re.MULTILINE)


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, text=True, check=True, **kwargs)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="check_race_law_") as directory:
            temp = Path(directory)
            run(["verilator", "--binary", "--timing", "-Wall", "-Wno-fatal",
                 "--top-module", "race_law_equiv_tb", "-Ihdl/rtl/core",
                 "--Mdir", str(temp / "obj"), str(TB)])
            simulation = run([str(temp / "obj/Vrace_law_equiv_tb")],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(simulation.stdout, end="")
            print("CHECK (a) PASS: checked-in race_law.svh exhaustively matches ROM")

            regenerated = temp / "race_law.svh"
            generation = run([sys.executable, str(GENERATOR), "--output", str(regenerated)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(generation.stdout, end="")
            if regenerated.read_bytes() != LAW.read_bytes():
                print("CHECK (b) FAIL: regenerated race_law.svh differs byte-for-byte",
                      file=sys.stderr)
                return 1
            checked_in = LAW.read_text(encoding="ascii")
            match = DIGEST_RE.search(checked_in)
            actual_digest = hashlib.sha256(HEX.read_bytes()).hexdigest()
            if not match:
                print("CHECK (b) FAIL: checked-in header has no valid ROM SHA-256",
                      file=sys.stderr)
                return 1
            if match.group(1) != actual_digest:
                print(f"CHECK (b) FAIL: header digest {match.group(1)} != {actual_digest}",
                      file=sys.stderr)
                return 1
            print("CHECK (b) PASS: regeneration is byte-identical and header SHA-256 matches")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: race-law gate failed: {exc}", file=sys.stderr)
        return 1
    print("check_race_law.py: PASS (2/2 sub-checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
