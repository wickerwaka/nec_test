#!/usr/bin/env python3
"""Pre-10k #17 validation gates over an emitted suite (host-side, zero board).

Checks per case:
  1. schema/type: required keys present, correct types, sane ranges.
  2. hash: recompute SHA1(name,bytes,initial,final,cycles) == stored hash.
  3. final-RAM: reconstruct changed bytes independently from the MEMW write
     transactions in `cycles` (address col1 @T2, data col6, UBE col5 for
     byte/word) and compare to `final.ram`.
  4. cold/prefetched convention: even idx -> empty initial.queue; odd -> non-empty.
  5. trace boundaries: first row is an F pop; queue-op column only F/S/E/-.
  6. unaligned: flag odd-address word accesses (informational count).

  python3 sw/validate_suite.py [--dir tests/v30/v0.2] [--sample N]
"""
import sys, gzip, json, glob, os, argparse, hashlib
from collections import Counter

REGS16 = ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
          "cs", "ss", "ds", "es", "ip", "flags")


def recompute_hash(c):
    return hashlib.sha1(json.dumps(
        [c["name"], c["bytes"], c["initial"], c["final"], c["cycles"]],
        separators=(",", ":")).encode()).hexdigest()


def reconstruct_writes(cycles):
    """Changed bytes from MEMW cycles. The ADDRESS is the T1 (address-phase) row's
    col1; the DATA is the following T2 (data-phase) row's col6; col5 (UBE) + address
    parity give byte/word width (even+UBE=0 -> word; even+UBE=1 -> low byte; odd ->
    high byte). Returns {addr20: byte}."""
    w = {}
    n = len(cycles)
    for i, row in enumerate(cycles):
        if not (row[7] == "MEMW" and row[8] == "T1"):
            continue
        addr = row[1] & 0xFFFFF
        ube = row[5]
        data = None
        for j in range(i + 1, min(i + 4, n)):
            if cycles[j][8] == "T2":
                data = cycles[j][6]
                break
        if data is None:
            continue
        even = (addr & 1) == 0
        if even and not ube:
            w[addr] = data & 0xFF
            w[(addr + 1) & 0xFFFFF] = (data >> 8) & 0xFF
        elif even and ube:
            w[addr] = data & 0xFF
        else:
            w[addr] = (data >> 8) & 0xFF
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="tests/v30/v0.2")
    ap.add_argument("--sample", type=int, default=0, help="0=all per form")
    a = ap.parse_args()
    fails = Counter()
    ex = {}
    tot = 0
    unaligned = 0
    for f in sorted(glob.glob(os.path.join(a.dir, "*.json.gz"))):
        op = os.path.basename(f)[:-len(".json.gz")]
        cases = json.load(gzip.open(f))
        if a.sample:
            cases = cases[:a.sample]
        for c in cases:
            tot += 1
            # 1. schema/type
            ok = True
            for k in ("name", "bytes", "initial", "final", "cycles", "hash", "idx"):
                if k not in c:
                    ok = False
            if ok:
                for sec in ("initial", "final"):
                    if not isinstance(c[sec].get("regs"), dict) or \
                       not isinstance(c[sec].get("ram"), list):
                        ok = False
                if not all(isinstance(b, int) and 0 <= b <= 255 for b in c["bytes"]):
                    ok = False
            if not ok:
                fails["schema"] += 1
                ex.setdefault("schema", (op, c.get("idx")))
                continue
            # 2. hash
            if recompute_hash(c) != c["hash"]:
                fails["hash"] += 1
                ex.setdefault("hash", (op, c["idx"]))
            # 3. final-RAM reconstruction
            init = {x & 0xFFFFF: v for x, v in c["initial"]["ram"]}
            recon = reconstruct_writes(c["cycles"])
            recon_changed = {x: v for x, v in recon.items() if init.get(x) != v}
            stored = {x & 0xFFFFF: v for x, v in c["final"]["ram"]}
            if recon_changed != stored:
                # allow: stored is a subset/superset only if values agree where present
                mism = {x for x in set(recon_changed) | set(stored)
                        if recon_changed.get(x, init.get(x)) !=
                           stored.get(x, init.get(x))}
                if mism:
                    fails["final_ram"] += 1
                    ex.setdefault("final_ram", (op, c["idx"], sorted(mism)[:4]))
            # 4. cold/prefetched
            q = c["initial"].get("queue", [])
            if (c["idx"] % 2 == 1) != bool(q):
                fails["cold_pf"] += 1
                ex.setdefault("cold_pf", (op, c["idx"]))
            # 5. boundaries + qop column
            if c["cycles"] and c["cycles"][0][9] != "F":
                fails["open_boundary"] += 1
                ex.setdefault("open_boundary", (op, c["idx"]))
            if any(row[9] not in ("F", "S", "E", "-") for row in c["cycles"]):
                fails["qop_col"] += 1
                ex.setdefault("qop_col", (op, c["idx"]))
            # 6. unaligned word accesses (informational)
            for row in c["cycles"]:
                if row[7] in ("MEMR", "MEMW") and (row[1] & 1) and not row[5]:
                    unaligned += 1
                    break
    print(f"validated {tot} cases across {len(glob.glob(os.path.join(a.dir,'*.json.gz')))} forms")
    print(f"FAILURES: {dict(fails) or 'NONE'}")
    for k, v in ex.items():
        print(f"  first {k}: {v}")
    print(f"unaligned-word cases (informational): {unaligned}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
