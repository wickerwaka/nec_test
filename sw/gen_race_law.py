#!/usr/bin/env python3
"""Generate the combinational POP-PSW race law from its frozen fitted model."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

VERSION = "gen_race_law.py 1.0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEX = ROOT / "hdl/rtl/core/int9d_race.hex"
DEFAULT_OUTPUT = ROOT / "hdl/rtl/core/race_law.svh"

# Literal dump of the frozen G/H/EXC model in race_rom_final_model.pkl.
# G is indexed by pre.DIR then {V,S,Z,AC,P,CY}; H is indexed by
# {pre.DIR,pop.DIR} then {V,S,Z,AC,P,CY}.
G_TABLES = (
    (25,15,58,32,17,19,37,16,20,55,41,61,43,51,13,26,7,4,39,56,47,18,53,45,10,9,5,1,22,29,63,30,
     34,60,57,48,49,14,46,52,44,24,54,40,42,36,12,59,6,3,23,28,27,35,50,33,8,11,2,0,21,38,62,31),
    (61,56,12,36,57,50,4,24,38,9,16,13,31,26,6,19,43,15,62,48,27,23,32,10,47,44,42,0,55,52,5,2,
     63,58,7,25,60,51,21,18,37,3,34,17,35,14,30,22,40,41,54,53,11,29,28,8,45,46,39,1,49,59,33,20),
)
H_TABLES = (
    (12,12,12,2,12,12,12,12,12,12,12,12,12,12,12,12,0,0,12,12,12,12,12,12,64,64,0,0,12,12,12,12,
     12,12,12,2,12,12,12,12,12,12,12,12,12,12,12,12,0,0,12,12,12,12,12,12,64,64,0,0,12,12,12,12),
    (12,14,12,2,12,12,12,12,12,12,12,12,12,12,12,12,0,0,12,14,12,12,12,12,64,64,0,0,12,12,12,12,
     8,8,12,2,8,8,12,12,8,8,8,8,12,12,12,12,0,0,8,12,8,8,8,8,62,62,0,0,8,8,8,8),
    (48,48,48,38,48,48,48,48,48,48,48,48,48,48,48,48,64,64,48,48,48,48,48,48,64,64,64,0,48,48,48,48,
     48,48,48,38,48,48,48,48,48,48,48,48,48,48,48,48,64,64,48,48,48,48,48,48,64,64,64,0,48,48,48,48),
    (48,48,48,38,48,48,48,48,48,48,48,48,48,48,48,48,64,64,48,48,48,48,48,48,64,64,64,0,48,48,48,48,
     44,44,48,38,44,44,48,48,44,44,44,44,48,48,48,48,64,64,44,48,44,44,44,44,2,2,64,0,44,44,44,44),
)
EXCEPTIONS = (
    3075,3107,3139,3171,3192,3193,3203,3235,3267,3299,3320,3321,4216,4217,4344,4345,4488,
    4520,4552,4584,4728,4729,4856,4857,6520,6521,6648,6649,7171,7203,7235,7267,7299,7331,
    7363,7395,7800,7801,7928,7929,11267,11299,11331,11363,11384,11385,11395,11427,11459,
    11491,11512,11513,12408,12409,12536,12537,12920,12921,13048,13049,14712,14713,14840,
    14841,15992,15993,16120,16121,
)


def read_rom(path: Path) -> tuple[bytes, list[int]]:
    raw = path.read_bytes()
    try:
        words = [int(line, 16) for line in raw.decode("ascii").splitlines() if line.strip()]
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{path}: invalid hexadecimal ROM: {exc}") from exc
    if len(words) != 1024 or any(word < 0 or word > 0xFFFF for word in words):
        raise ValueError(f"{path}: expected exactly 1024 16-bit hexadecimal words, got {len(words)}")
    return raw, words


def rom_bit(words: list[int], address: int) -> int:
    return (words[address >> 4] >> (address & 15)) & 1


def law_bit(address: int) -> int:
    pre = address >> 7
    pop = address & 0x7F
    if pre == pop:
        return 0
    rp = ((pre >> 6) << 5) | (pre & 0x1F)
    rq = ((pop >> 6) << 5) | (pop & 0x1F)
    pre_dir = (pre >> 5) & 1
    pop_dir = (pop >> 5) & 1
    base = int(G_TABLES[pre_dir][rp] >= H_TABLES[2 * pre_dir + pop_dir][rq])
    return base ^ int(address in EXCEPTION_SET)


EXCEPTION_SET = frozenset(EXCEPTIONS)


def emit_case_function(name: str, values: tuple[int, ...], width: int) -> str:
    lines = [f"function automatic [{width - 1}:0] {name}(input [5:0] i);", "    case (i)"]
    lines.extend(f"        6'd{i}: {name} = {width}'d{value};" for i, value in enumerate(values))
    lines += [f"        default: {name} = {width}'d0;", "    endcase", "endfunction"]
    return "\n".join(lines)


def render(digest: str) -> str:
    out = [
        "// -----------------------------------------------------------------------------",
        "// GENERATED - DO NOT HAND-EDIT",
        f"// Generator: {VERSION}",
        f"// int9d_race.hex SHA-256: {digest}",
        "// Pure-combinational staircase + diagonal + 68-cell exception race law.",
        "// -----------------------------------------------------------------------------",
        "",
        emit_case_function("rl_g0", G_TABLES[0], 6),
        "",
        emit_case_function("rl_g1", G_TABLES[1], 6),
    ]
    for index, values in enumerate(H_TABLES):
        out += ["", emit_case_function(f"rl_h{index >> 1}{index & 1}", values, 7)]
    out += ["", "function automatic rl_exc(input [13:0] a);", "    case (a)"]
    addresses = ",\n".join(f"        14'h{address:04x}" for address in EXCEPTIONS)
    out += [addresses + ": rl_exc = 1'b1;", "        default: rl_exc = 1'b0;",
            "    endcase", "endfunction", "",
            "function automatic race_law(input [6:0] pre, input [6:0] pop);",
            "    reg [5:0] rp;", "    reg [5:0] rq;", "    reg [6:0] rank;",
            "    reg [6:0] threshold;", "    reg base;", "    begin",
            "        rp = {pre[6], pre[4:0]};", "        rq = {pop[6], pop[4:0]};",
            "        case (pre[5])", "            1'b0: rank = {1'b0, rl_g0(rp)};",
            "            1'b1: rank = {1'b0, rl_g1(rp)};", "        endcase",
            "        case ({pre[5], pop[5]})", "            2'b00: threshold = rl_h00(rq);",
            "            2'b01: threshold = rl_h01(rq);", "            2'b10: threshold = rl_h10(rq);",
            "            2'b11: threshold = rl_h11(rq);", "        endcase",
            "        base = (rank >= threshold);",
            "        race_law = (pre == pop) ? 1'b0 : (base ^ rl_exc({pre, pop}));",
            "    end", "endfunction", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hex", type=Path, default=DEFAULT_HEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        raw, words = read_rom(args.hex)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    mismatches = [(a, rom_bit(words, a), law_bit(a)) for a in range(16384)
                  if rom_bit(words, a) != law_bit(a)]
    if mismatches:
        print(f"ERROR: frozen race-law model disagrees with {args.hex}; refusing to emit.",
              file=sys.stderr)
        for address, expected, actual in mismatches:
            print(f"  address=0x{address:04x} expected={expected} actual={actual}",
                  file=sys.stderr)
        print(f"ERROR: {len(mismatches)}/16384 mismatches", file=sys.stderr)
        return 1
    print("Generator self-check: 16384/16384 reconstructed bits match int9d_race.hex")
    text = render(hashlib.sha256(raw).hexdigest())
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="ascii", newline="\n")
    except OSError as exc:
        print(f"ERROR: cannot emit {args.output}: {exc}", file=sys.stderr)
        return 2
    print(f"Emitted {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
