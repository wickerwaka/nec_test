#!/usr/bin/env python3
"""t31_root_signal - classify each FUNCTIONAL divergence by ROOT signal using the
diverging transaction's T1 (clean address-phase) rows in both legs, avoiding the
T2/T3 multiplexed-address trap. Board-free.

Root signals:
  escape        - the two legs' diverging-txn addresses differ and at least one
                  is out-of-image (linear >= 0x10000): the paths split, one leg
                  wandered out of the 64K image  -> task #32.
  value_bug     - both legs access the SAME in-image address but write/read
                  DIFFERENT data: a genuine functional value divergence -> #31.
  prefetch_split- the first divergence is in queue state (qs / rd_n) with both
                  legs in-image: a prefetch/queue phase split -> #33 cross-link.
  addr_split    - diverging-txn addresses differ but BOTH in-image: a control-flow
                  split inside the image -> #31 (real).
  other         - none of the above cleanly.

    python3 sw/t31_root_signal.py [--cid mc1]
"""
import argparse
import glob
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                                  # noqa: E402
CAMPAIGNS = SW / "testdata" / "campaigns"


def cap(cdir, r):
    fs = glob.glob(str(cdir / "captures" /
                       f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"))
    return json.load(gzip.open(fs[0], "rt")) if fs else None


def txn_at(rows, fb):
    """The transaction (start T1 row, addr, kind, data) covering row fb."""
    for tx in fc.extract_txns(rows):
        if tx["start"] <= fb <= tx["end"]:
            return tx
    # else nearest preceding txn
    prev = None
    for tx in fc.extract_txns(rows):
        if tx["start"] > fb:
            break
        prev = tx
    return prev


def root_signal(real, sim, fb):
    tr, ts = txn_at(real, fb), txn_at(sim, fb)
    # queue/ctrl-only first divergence with no txn address split
    rrow, srow = real[fb], sim[fb]
    qs_only = (rrow.get("qs") != srow.get("qs")
               or rrow.get("rd_n") != srow.get("rd_n"))
    if tr is None or ts is None:
        return "other"
    ra, sa = tr["addr"] & 0xFFFFF, ts["addr"] & 0xFFFFF
    r_out, s_out = ra >= 0x10000, sa >= 0x10000
    if ra != sa:
        if r_out or s_out:
            return "escape"
        return "addr_split"                    # both in-image, path split
    # same address
    if not r_out and tr.get("data") != ts.get("data"):
        return "value_bug"
    if qs_only and not r_out:
        return "prefetch_split"
    if r_out:
        return "escape"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", default="mc1")
    a = ap.parse_args()
    cdir = CAMPAIGNS / a.cid
    rows = [json.loads(l) for l in (cdir / "results.jsonl").read_text().splitlines()
            if l.strip()]
    func = [r for r in rows if r["verdict"] == "FUNCTIONAL"]

    def wc(r):
        w = r["waits"]
        if w.get("wrand"):
            return f"wr{w.get('wmax')}"
        return "w0" if (w.get("fixed") or 0) == 0 else f"w{w.get('fixed')}"

    by_sig = defaultdict(list)
    tally = Counter()
    for r in func:
        c = cap(cdir, r)
        fb = r.get("first_bad")
        if not c or fb is None:
            tally["nocap"] += 1; continue
        sig = root_signal(c["real"], c["sim"], fb)
        tally[sig] += 1
        subk = (r["sub"] or "").split("@")[0]
        by_sig[(sig, subk, wc(r) == "w0" and "w0" or "waited")].append(r)

    print(f"# task #31 root-signal over {a.cid}: {len(func)} FUNCTIONAL\n")
    print("root-signal tally:", dict(tally.most_common()))
    routing = {"escape": "#32", "value_bug": "#31", "addr_split": "#31",
               "prefetch_split": "#33", "other": "review", "nocap": "-"}
    print("\n| root-signal (task) | sub / waits | n | tiers | rep |")
    print("|---|---|---|---|---|")
    for key, rs in sorted(by_sig.items(), key=lambda kv: -len(kv[1])):
        sig, subk, waited = key
        if sig == "escape":
            continue                            # -> #32, not enumerated here
        tiers = ",".join(f"{k}:{v}" for k, v in
                         Counter(r["tier"] for r in rs).most_common())
        rep = min(rs, key=lambda r: r["k"])
        print(f"| {sig} ({routing[sig]}) | {subk} / {waited} | {len(rs)} | "
              f"{tiers} | {rep['cid']}/{rep['k']} |")
    for key, rs in by_sig.items():
        if any(r["k"] == 15 for r in rs):
            print(f"\nk=15 -> {key}")


if __name__ == "__main__":
    main()
