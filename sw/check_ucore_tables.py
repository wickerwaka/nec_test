#!/usr/bin/env python3
"""GATE G0 -- the generated ucore tables byte-match the reference model.

    python3 sw/check_ucore_tables.py

Three legs, all of which must pass:

  LEG A (independent re-parse).  This file contains its OWN parser of
  docs/V20BITS.TXT and docs/pla3_outputs.txt, written from docs/V20UCDIS.PAS
  (procedure ReadBits, lines 103-160) and from the bit-numbering note at the
  head of sim/pla3_table.h -- NOT importing sw/ucore_tables.py.  Leg A diffs
  that parse against `sim/v30sim dump-tables`, so a bug shared between the
  generator and its helper module cannot pass by being consistent with itself.

  LEG B (the artifacts).  hdl/rtl/ucore/ucrom.hex, ucdecode.hex and
  pla3_tables.svh are read back as data and diffed against the SAME sim dump:
      1028 microcode rows x 29b
      8192 micro-address decode entries (native resolution)
       768 PLA entries (3 x 256 x 14b)
  = 9988 compared entries, all of which must be identical.

  LEG C (staleness).  `sw/gen_ucore_tables.py --check` -- the artifacts on disk
  are what the generator produces today.

Exit 0 = G0 green.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "sim/v30sim"
V20BITS = ROOT / "docs/V20BITS.TXT"
PLA3 = ROOT / "docs/pla3_outputs.txt"
OUT = ROOT / "hdl/rtl/ucore"

N_ROWS = 1028
N_ADDRS = 8192


# --------------------------------------------------------------------------
# LEG A: an independent parse, from docs/V20UCDIS.PAS::ReadBits.
# Pascal indexes strings from 1: micro-word = Line[1..29], activation pattern =
# Line[31..45].  `Bits := Bits or 1 shl (29-i)` for i in 1..29, then
# `Bits := not Bits`.  Field slicing per sim/ucrom.h (documented as
# transliterated from the same Pascal program's PrintInstrs).
# --------------------------------------------------------------------------
def parse_v20bits():
    rows, pats = [], []
    text = V20BITS.read_bytes().decode("latin-1").splitlines()
    for row, line in enumerate(text[1:]):
        if len(rows) >= N_ROWS:
            break
        line = line.rstrip("\r")
        if len(line) < 29:
            continue
        n = len(rows)
        bits = 0
        for i in range(1, 30):                      # Pascal i := 1 to 29
            if line[i - 1] == "1":
                bits |= 1 << (29 - i)
        if n % 4 == 0:
            if len(line) < 45:
                raise SystemExit(f"bad activation pattern on row {n}")
            mask = cmp_ = 0
            for i in range(31, 46):                 # Pascal i := 31 to 45
                c = line[i - 1]
                if c == ".":
                    continue
                if c not in "01?":
                    raise SystemExit(f"bad activation pattern on row {n}")
                mask = (mask << 1) | (0 if c == "?" else 1)
                cmp_ = (cmp_ << 1) | (1 if c == "1" else 0)
            pats.append((mask, cmp_))
        rows.append((~bits) & 0x1FFFFFFF)           # Pascal: Bits := not Bits
    if len(rows) != N_ROWS or len(pats) != N_ROWS // 4:
        raise SystemExit(f"short parse: {len(rows)} rows / {len(pats)} patterns")
    return rows, pats


def resolve_banks(pats):
    """Fixed-priority match over the 13-bit micro-address; native mode takes
    the SECOND match where two patterns collide (sim/ucrom.h::bank_of)."""
    native, emu, ambiguous = [], [], []
    for addr in range(N_ADDRS):
        hit = [b for b, (m, c) in enumerate(pats) if (addr & m) == c]
        if not hit:
            native.append(-1)
            emu.append(-1)
        else:
            emu.append(hit[0])
            native.append(hit[1] if len(hit) > 1 else hit[0])
        if len(hit) > 1:
            ambiguous.append(addr)
    return native, emu, ambiguous


def parse_pla():
    """Vector printed MSB-first as b0..b13; b0 is stored in bit 13."""
    want = {"native opcodes": "native", "8080 opcodes": "mode8080",
            "ext opcodes": "ext"}
    tables, cur = {}, None
    for line in PLA3.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        if s in want:
            cur = want[s]
            tables[cur] = {}
            continue
        op, bits = s.split()
        v = 0
        for i, ch in enumerate(bits):
            if ch == "1":
                v |= 1 << (13 - i)
        tables[cur][int(op, 16)] = v
    return {k: [t[i] for i in range(256)] for k, t in tables.items()}


# --------------------------------------------------------------------------
# the sim's own dump
# --------------------------------------------------------------------------
def sim_dump():
    if not SIM.exists():
        raise SystemExit(f"{SIM} not built -- run `make -C sim`")
    out = subprocess.run([str(SIM), "dump-tables", str(V20BITS)],
                         capture_output=True, text=True, check=True).stdout
    rows, native, emu = [], [], []
    pla = {"native": [0] * 256, "mode8080": [0] * 256, "ext": [0] * 256}
    for line in out.splitlines():
        f = line.split()
        if f[0] == "row":
            rows.append(int(f[2], 16))
        elif f[0] == "addr":
            native.append(int(f[2]))
            emu.append(int(f[3]))
        elif f[0] == "pla" and len(f) == 4:
            pla[f[1]][int(f[2], 16)] = int(f[3], 16)
    if len(rows) != N_ROWS or len(native) != N_ADDRS:
        raise SystemExit(f"sim dump malformed: {len(rows)} rows, "
                         f"{len(native)} addrs")
    return rows, native, emu, pla


# --------------------------------------------------------------------------
# the emitted artifacts, read back as data
# --------------------------------------------------------------------------
def read_hexfile(path, count, width_nib):
    words = []
    for raw in path.read_text().splitlines():
        s = raw.split("//")[0].strip()
        if not s:
            continue
        if len(s) != width_nib or re.fullmatch(r"[0-9A-F]+", s) is None:
            raise SystemExit(f"{path.name}: bad word {raw!r}")
        words.append(int(s, 16))
    if len(words) != count:
        raise SystemExit(f"{path.name}: {len(words)} words (expected {count})")
    return words


def read_pla_svh(path):
    text = path.read_text()
    tables = {}
    for name in ("native", "mode8080", "ext"):
        m = re.search(r"function automatic logic \[13:0\] pla3_%s\("
                      r".*?endfunction" % name, text, re.S)
        if not m:
            raise SystemExit(f"pla3_tables.svh: pla3_{name} not found")
        body = m.group(0)
        ent = dict((int(o, 16), int(v, 16)) for o, v in re.findall(
            r"8'h([0-9A-F]{2}):\s*pla3_%s = 14'h([0-9A-F]{4});" % name, body))
        if len(ent) != 256:
            raise SystemExit(f"pla3_tables.svh: pla3_{name} has {len(ent)} "
                             "entries (expected 256)")
        tables[name] = [ent[i] for i in range(256)]
    return tables


def diff(label, got, want, fmt="%X", limit=5):
    bad = [i for i in range(len(want)) if got[i] != want[i]]
    if bad:
        print(f"  {label}: {len(bad)} MISMATCH of {len(want)}")
        for i in bad[:limit]:
            print(f"    [{i:#06x}] got {fmt % got[i]} want {fmt % want[i]}")
        if len(bad) > limit:
            print(f"    ... {len(bad) - limit} more")
    else:
        print(f"  {label}: {len(want)}/{len(want)} identical")
    return len(bad)


def main():
    errs = 0
    s_rows, s_native, s_emu, s_pla = sim_dump()
    print(f"sim dump: {len(s_rows)} rows, {len(s_native)} micro-addresses, "
          f"768 PLA entries")

    print("\nLEG A -- independent re-parse of the dumps vs the sim")
    a_rows, a_pats = parse_v20bits()
    a_native, a_emu, a_amb = resolve_banks(a_pats)
    a_pla = parse_pla()
    errs += diff("ucrom rows", a_rows, s_rows, "%08X")
    errs += diff("decode (native)", a_native, s_native, "%d")
    errs += diff("decode (emu)", a_emu, s_emu, "%d")
    for k in ("native", "mode8080", "ext"):
        errs += diff(f"pla3 {k}", a_pla[k], s_pla[k], "%04X")
    print(f"  ambiguous micro-addresses: {len(a_amb)} "
          f"({', '.join('%04X' % a for a in a_amb) or 'none'})")

    print("\nLEG B -- the emitted RTL artifacts vs the sim")
    b_rows = read_hexfile(OUT / "ucrom.hex", N_ROWS, 8)
    dec = read_hexfile(OUT / "ucdecode.hex", N_ADDRS, 3)
    b_native = [-1 if (w & 0x200) == 0 else (w & 0x1FF) for w in dec]
    b_pla = read_pla_svh(OUT / "pla3_tables.svh")
    errs += diff("ucrom.hex", b_rows, s_rows, "%08X")
    errs += diff("ucdecode.hex", b_native, s_native, "%d")
    for k in ("native", "mode8080", "ext"):
        errs += diff(f"pla3_tables.svh {k}", b_pla[k], s_pla[k], "%04X")

    print("\nLEG C -- artifacts are current with the generator")
    sys.stdout.flush()
    rc = subprocess.run([sys.executable,
                         str(ROOT / "sw/gen_ucore_tables.py"), "--check"])
    if rc.returncode != 0:
        errs += 1

    total = N_ROWS + N_ADDRS + 768
    print()
    if errs:
        print(f"check_ucore_tables: FAIL ({errs} mismatching table(s))")
        return 1
    print(f"check_ucore_tables: PASS -- G0 GREEN "
          f"({N_ROWS} rows + {N_ADDRS} micro-addresses + 768 PLA entries "
          f"= {total} entries byte-identical to sim/, on both legs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
