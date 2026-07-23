#!/usr/bin/env python3
"""V30 BCD string-4S oracle predicate — standing empty-set assertion (L1/F2a).

The V30 accumulates the Z flag (and P=Z) over the ADJUSTED written bytes of the
packed-BCD string ops ADD4S/SUB4S/CMP4S; the V20 (uPD70108) accumulates over the
PRE-adjust bytes. The two stage laws give the same final Z for every vector in
the CURRENT v20 oracle suite (predicate empty), so the RTL's V30-stage fix
preserves the v20 4S oracle at hard 100% with NO amendment.

This module is the maintained Python lane mirror (bcd_add8/bcd_sub8 replicate
v30_eu.sv exactly, byte-level, no digit masking) plus the standing gate:

  * `predicate(form, case)` -> (z20, z30): the final Z under each stage law.
  * `scan_v20_4s()` -> list of in-predicate v20 vectors (Z20 != Z30).
  * run as a script: asserts the predicate is EMPTY over the v20 4S suite and
    exits non-zero if not. If a future v20 re-emission makes it non-empty, the
    PRE-REGISTERED rule applies automatically: those vectors must assert against
    the V30 prediction (z30), not the V20 result — reported here, no new
    decision needed.

Falsifier record (retired + replaced, per the architect's L1 ratification):
  (a) all 15 in-predicate v0.3 divergent CMP4S/SUB4S cases flip to chip-matching
      under the fix, and the V20 stage mispredicts all 15;
  (b) the 130 byte-level v0.3 CMP4S CL=1 cases (low nibble zero-wraps, full byte
      non-zero) stay Z=0 post-fix — the V30 chip is byte-level;
  (c) no single-vector replacement: none exists in the current suites, and
      inventing one would be fitting the falsifier to the law.
The original idx-652 falsifier premise was a digit-level mis-reading during F2
characterization sub-work; the byte-level chip data (130 CL=1 cases) corrected
it — recorded per the provenance discipline.
"""
import gzip
import json
import sys
from pathlib import Path

V20 = Path(__file__).resolve().parent.parent / "tests" / "v30" / "v20suite"
FORMS_4S = ("0F20", "0F22", "0F26")   # ADD4S / SUB4S / CMP4S


def lin(seg, off):
    return ((seg << 4) + off) & 0xFFFFF


def bcd_add8(a, b, cin):
    """-> (carry, prez, res). Mirrors v30_eu.sv bcd_add8 (s[8]=prez, s[7:0]=res)."""
    lo = (a & 0xF) + (b & 0xF) + cin
    c1 = (lo >> 4) & 1
    dlo0 = lo & 0xF
    c2 = 1 if dlo0 > 9 else 0
    dlo = (dlo0 + 6) & 0xF if (c1 or c2) else dlo0
    hi = ((a >> 4) & 0xF) + ((b >> 4) & 0xF) + c1 + c2
    dhi0 = hi & 0xF
    fire = 1 if (((a >> 4) & 0xF) + ((b >> 4) & 0xF) + (c1 | c2)) > 9 else 0
    dhi = (dhi0 + 6) & 0xF if fire else dhi0
    prez = 1 if (dhi0 == 0 and dlo0 == 0) else 0
    return ((a + b + cin) >> 8) & 1, prez, ((dhi << 4) | dlo) & 0xFF


def bcd_sub8(a, b, bin_):
    """-> (borrow, prez, res). Mirrors v30_eu.sv bcd_sub8 (s[8]=prez, s[7:0]=res)."""
    lo = ((a & 0xF) - (b & 0xF) - bin_) & 0x1F
    c1 = (lo >> 4) & 1
    dlo0 = lo & 0xF
    c2 = 1 if dlo0 > 9 else 0
    fl = c1 or c2
    dlo = (dlo0 - 6) & 0xF if fl else dlo0
    wrapb = 1 if (fl and dlo0 < 6) else 0
    hi = (((a >> 4) & 0xF) - ((b >> 4) & 0xF) - c1 - wrapb) & 0x1F
    dhi0 = hi & 0xF
    dec = (((a >> 4) & 0xF) - ((b >> 4) & 0xF) - c1) & 0x1F
    fire = 1 if (((dec >> 4) & 1) or dec > 9
                 or ((dec & 0xF) == 9 and c2 and not c1)) else 0
    dhi = (dhi0 - 6) & 0xF if fire else dhi0
    prez = 1 if (dhi0 == 0 and dlo0 == 0) else 0
    return ((a - b - bin_) >> 8) & 1, prez, ((dhi << 4) | dlo) & 0xFF


def predicate(form, c):
    """Final Z under the (V20 pre-adjust, V30 adjusted) stage laws -> (z20, z30)."""
    r = c["initial"]["regs"]
    cl = r["cx"] & 0xFF
    n = (cl + 1) // 2                       # COUNT = (CL+1)>>1 full bytes
    ram = {a: v for a, v in c["initial"]["ram"]}
    src = [ram.get(lin(r["ds"], (r["si"] + k) & 0xFFFF), 0) for k in range(n)]
    dst = [ram.get(lin(r["es"], (r["di"] + k) & 0xFFFF), 0) for k in range(n)]
    carry = 0
    z20 = z30 = 1
    for k in range(n):
        a, b = dst[k], src[k]
        if form == "0F20":                          # ADD4S
            cin = carry
            u = 1 if (a + b + cin) == 0 else 0       # U add: 9-bit raw sum == 0
            carry, prez, _ = bcd_add8(a, b, cin)
        else:                                        # SUB4S / CMP4S
            lo = ((a & 0xF) - (b & 0xF) - carry) & 0x1F
            c1 = (lo >> 4) & 1
            dlo0 = lo & 0xF
            fl = c1 or (1 if dlo0 > 9 else 0)
            dlo = (dlo0 - 6) & 0xF if fl else dlo0
            dec = (((a >> 4) & 0xF) - ((b >> 4) & 0xF) - c1) & 0x1F
            u = 1 if ((dec & 0xF) == 0 and dlo == 0) else 0   # {dec[3:0], dlo}==0
            carry, prez, _ = bcd_sub8(a, b, carry)
        z20 &= prez
        z30 &= u
    return z20, z30


def scan_v20_4s():
    """-> {form: [(idx, z20, z30), ...]} of in-predicate (Z20 != Z30) vectors."""
    out = {}
    for form in FORMS_4S:
        fn = V20 / f"{form}.json.gz"
        if not fn.exists():
            continue
        hits = []
        for c in json.load(gzip.open(fn)):
            z20, z30 = predicate(form, c)
            if z20 != z30:
                hits.append((c["idx"], z20, z30))
        out[form] = hits
    return out


def main():
    hits = scan_v20_4s()
    total = sum(len(v) for v in hits.values())
    for form, v in hits.items():
        print(f"  {form}: predicate fires {len(v)}"
              + (f"  {v[:8]}" if v else ""))
    if total == 0:
        print("oracle_4s_predicate: PASS (predicate EMPTY over v20 4S; "
              "gate stays hard 100% V20, unamended)")
        return 0
    print(f"oracle_4s_predicate: NON-EMPTY ({total}). Pre-registered rule: "
          "these vectors must assert against the V30 prediction (z30), NOT the "
          "V20 result. Amend the 4S oracle gate accordingly (no new decision).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
