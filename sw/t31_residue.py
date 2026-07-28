#!/usr/bin/env python3
"""t31_residue - enumerate the GENUINE value-bug residue in the FUNCTIONAL
population (task #31). Board-free. A genuine isolated value divergence has an
IDENTICAL code-fetch stream in both legs (same execution path) but a differing
store DATA value at a shared in-image address - so it is neither an escape
(paths would diverge) nor a prefetch split (fetch stream identical). This is the
discriminator that isolates k=6475 from the escape/desync bulk.

    python3 sw/t31_residue.py [--cid mc1]
"""
import argparse
import glob
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                                  # noqa: E402
CAMPAIGNS = SW / "testdata" / "campaigns"


def cap(cdir, r):
    fs = glob.glob(str(cdir / "captures" /
                       f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"))
    return json.load(gzip.open(fs[0], "rt")) if fs else None


def code_fetches(rows):
    return [r["ad_addr"] & 0xFFFFF for r in rows
            if fc._tstate(r) == 1 and r["bs_early"] == 4]


def wmap(rows):
    m = {}
    for tx in fc.extract_txns(rows):
        if fc.KIND[tx["kind"]] in ("MEMW", "IOW") and (tx["addr"] & 0xFFFFF) < 0x10000:
            m.setdefault(tx["addr"] & 0xFFFF, tx.get("data"))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", default="mc1")
    a = ap.parse_args()
    cdir = CAMPAIGNS / a.cid
    rows = [json.loads(l) for l in (cdir / "results.jsonl").read_text().splitlines()
            if l.strip()]
    func = [r for r in rows if r["verdict"] == "FUNCTIONAL"]

    genuine = []
    for r in func:
        c = cap(cdir, r)
        if not c:
            continue
        cf_r, cf_s = code_fetches(c["real"]), code_fetches(c["sim"])
        n = min(len(cf_r), len(cf_s))
        if not (cf_r[:n] == cf_s[:n] and abs(len(cf_r) - len(cf_s)) <= 2):
            continue                        # code paths diverge -> escape/prefetch
        wr, ws = wmap(c["real"]), wmap(c["sim"])
        diffs = [(x, wr[x], ws[x]) for x in set(wr) & set(ws) if wr[x] != ws[x]]
        if diffs:
            addr, rd, sd = min(diffs, key=lambda d: d[0])
            w = r["waits"]
            wl = f"wr{w['wmax']}" if w.get("wrand") else f"w{w.get('fixed') or 0}"
            genuine.append((r["k"], r["tier"], r["sub"], wl,
                            addr, rd, sd, len(diffs)))

    print(f"# task #31 residue over {a.cid}: {len(genuine)} genuine isolated "
          f"value divergences (identical code path, differing store data)\n")
    chipvals = Counter(g[5] for g in genuine)
    print("chip-value clusters (>=2):",
          {hex(v): c for v, c in chipvals.most_common() if c >= 2})
    print("\n  k      tier sub            waits addr    chip    fabric  ndiff")
    for g in sorted(genuine):
        print("  %-6d %-4s %-14s %-5s %-7s %-7s %-7s %d"
              % (g[0], g[1], g[2], g[3], hex(g[4]), hex(g[5] or 0),
                 hex(g[6] or 0), g[7]))


if __name__ == "__main__":
    main()
