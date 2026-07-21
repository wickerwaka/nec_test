#!/usr/bin/env python3
"""extract_iords - recover the per-case INS port-read sequence from the V20 oracle.

INS (6C/6D) reads port DW (one IOR per element) and writes each value to ES:IY,
then steps IY by (DF ? -width : +width). So the ordered port sequence is
recoverable two ways, cross-checked here:

  1. final.ram: the byte(s) each iteration wrote to ES:IY, read back in order
     from the effective final memory (initial ram overlaid with the case's
     final-ram diff - a byte that equalled its pre-existing value is absent
     from the diff but still recovered from the initial image).
  2. the cycles IOR data column (col 6 on the IOR T3 row), in bus order - the
     value the port physically returned on each read.

For non-overlapping writes these agree exactly. A case is AMBIGUOUS only when a
later iteration overwrites a byte an earlier iteration wrote (DF/wrap over the
16-bit IY offset), so final.ram alone cannot reconstruct the earlier value.
Ambiguous cases are counted and listed, never guessed; the INS gate excludes
them (with that count + list).

Output: one sidecar per opcode, <out-dir>/<op>.iords.json.gz, holding
    {"iords": {idx: [v0, v1, ...]}, "ambiguous": [idx, ...]}
where each v is the 16-bit value to serve on that IOR (byte forms carry the
byte in BOTH lanes so the served word is port-parity-agnostic; word forms carry
the full 16-bit word). check_core --arch-only loads it for 6C/6D.

Usage:
  extract_iords.py [--suite-dir tests/v30/v20suite] [--opcodes 6C,6D]
                   [--out-dir tests/v30/v20suite] [--report-only]
"""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REP_PREFIXES = {0xF3, 0xF2, 0x64, 0x65}


def eff_mem(case):
    """Effective final memory: initial ram overlaid with the final-ram diff."""
    m = {a & 0xFFFFF: v for a, v in case["initial"]["ram"]}
    for a, v in case["final"]["ram"]:
        m[a & 0xFFFFF] = v
    return m


def byte_at(m, addr20):
    # unlisted bytes are the TB's 0x90 NOP fill (matches the harness image)
    return m.get(addr20 & 0xFFFFF, 0x90)


def ior_data_from_cycles(case):
    """Ordered per-IOR read data from the cycle rows (col 6 on the IOR T3 row).
    May be short if the golden window closed before a late IOR's T3."""
    out = []
    for r in case["cycles"]:
        # row = [ale, bus, seg, memcmd, iocmd, ube, data, busstat, tstate, ...]
        if r[7] == "IOR" and r[8] == "T3":
            out.append(r[6] & 0xFFFF)
    return out


def extract_case(case, width):
    """-> (iords list, ambiguous bool, xcheck (n_checked, n_mismatch))."""
    b = case["bytes"]
    is_rep = any(x in REP_PREFIXES for x in b[:-1])
    reg = case["initial"]["regs"]
    cw = reg["cx"]
    df = (reg["flags"] >> 10) & 1
    step = (-width if df else width) & 0xFFFF
    es = reg["es"]
    iy0 = reg["di"]

    if is_rep:
        niter = cw            # REP INS repeats CW times (cw==0 -> 0 elements)
    else:
        niter = 1

    m = eff_mem(case)
    base = es << 4

    # per-iteration byte addresses (16-bit IY offset arithmetic within ES)
    iter_addrs = []
    for k in range(niter):
        iy = (iy0 + k * step) & 0xFFFF
        addrs = [(base + ((iy + j) & 0xFFFF)) & 0xFFFFF for j in range(width)]
        iter_addrs.append(addrs)

    # overlap map: an addr written by >1 iteration makes the earlier ones
    # unrecoverable from final memory (only the last write survives)
    last_writer = {}
    for k, addrs in enumerate(iter_addrs):
        for a in addrs:
            last_writer[a] = k

    ambiguous = False
    vals = []
    for k, addrs in enumerate(iter_addrs):
        if any(last_writer[a] != k for a in addrs):
            ambiguous = True
        bs = [byte_at(m, a) for a in addrs]
        if width == 1:
            vals.append((bs[0] & 0xFF) * 0x0101)   # both lanes (parity-agnostic)
        else:
            vals.append((bs[0] | (bs[1] << 8)) & 0xFFFF)

    # cross-check against the bus IOR data column where available
    cyc = ior_data_from_cycles(case)
    n_chk = min(len(cyc), len(vals))
    n_mis = 0
    for k in range(n_chk):
        got = cyc[k]
        if width == 1:
            # the bus row carries the byte in one lane; compare the active byte
            ref = vals[k] & 0xFF
            if (got & 0xFF) != ref and ((got >> 8) & 0xFF) != ref:
                n_mis += 1
        else:
            if got != vals[k]:
                n_mis += 1
    return vals, ambiguous, (n_chk, n_mis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-dir", default="tests/v30/v20suite")
    ap.add_argument("--opcodes", default="6C,6D")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--report-only", action="store_true",
                    help="print the summary; do not write sidecars")
    a = ap.parse_args()

    suite = Path(a.suite_dir)
    # sidecars live in an iords/ subdir so the suite's own *.json.gz glob
    # (check_core --opcodes all) never mistakes them for opcode files.
    out_dir = Path(a.out_dir) if a.out_dir else suite / "iords"
    if not a.report_only:
        out_dir.mkdir(parents=True, exist_ok=True)
    grand_amb = 0
    for op in a.opcodes.split(","):
        fn = suite / f"{op}.json.gz"
        if not fn.exists():
            print(f"{op}: no suite file")
            continue
        cases = json.load(gzip.open(fn))
        width = 2 if int(op, 16) & 1 else 1
        iords = {}
        ambiguous = []
        tot_chk = tot_mis = tot_ior = 0
        for c in cases:
            vals, amb, (nchk, nmis) = extract_case(c, width)
            iords[c["idx"]] = vals
            tot_ior += len(vals)
            tot_chk += nchk
            tot_mis += nmis
            if amb:
                ambiguous.append(c["idx"])
        grand_amb += len(ambiguous)
        # NB: the V20 trace convention records only T1/T2 for IOR cycles (no
        # T3/T4), so the port read data is NOT in the cycle rows - the design
        # note's "col 6 at IOR read points" cross-check has no data here. The
        # overlap detector (final.ram last-writer) is the ambiguity guard.
        xc = (f"cross-checked {tot_chk} vs cycles ({tot_mis} mismatch)"
              if tot_chk else "no bus IOR data in cycles (V20 trace stops at "
                              "T2) - final.ram + overlap-detector only")
        print(f"{op}: {len(cases)} cases, {tot_ior} IORs total; {xc}; "
              f"ambiguous(overlap) {len(ambiguous)}"
              + (f" idx {ambiguous[:12]}" if ambiguous else ""))
        if not a.report_only:
            out = out_dir / f"{op}.iords.json.gz"
            with gzip.open(out, "wt") as f:
                json.dump({"iords": {str(k): v for k, v in iords.items()},
                           "ambiguous": ambiguous}, f)
            print(f"     -> {out}")
    print(f"\nTOTAL ambiguous across opcodes: {grand_amb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
