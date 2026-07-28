#!/usr/bin/env python3
"""t31_family_map - cluster the in-image FUNCTIONAL divergences (task #31) into
mechanism families. Board-free: reads mc1 results + captures. Per seed computes
the divergence position (first_bad / window), the primary differing column
group, whether a func:W/R differs in DATA (a value bug) vs addr/bus (structural/
prefetch), and w0-vs-waited. Clusters and emits the family map + reps.

    python3 sw/t31_family_map.py [--cid mc1]
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

COLS = {"data": ("ad_data",), "addr": ("ad_addr",),
        "bus": ("bs_early", "bs_late"), "queue": ("qs",),
        "ctrl": ("rd_n", "lock_n"), "tstate": ("t",)}


def cap(cdir, r):
    fs = glob.glob(str(cdir / "captures" /
                       f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"))
    return json.load(gzip.open(fs[0], "rt")) if fs else None


def wc(r):
    w = r["waits"]
    if w.get("wrand"):
        return f"wr{w.get('wmax')}"
    return "w0" if (w.get("fixed") or 0) == 0 else f"w{w.get('fixed')}"


def exec_addr(rows, fb):
    for i in range(min(fb, len(rows) - 1), -1, -1):
        if rows[i].get("t") == 1 and rows[i]["bs_early"] == 4:
            return rows[i]["ad_addr"] & 0xFFFFF
    return None


def div_char(real, sim, fb):
    """primary differing column group at/near first_bad + a data-value flag."""
    groups = Counter()
    data_val = False
    for i in range(fb, min(fb + 6, len(real), len(sim))):
        for g, cols in COLS.items():
            if any(real[i].get(c) != sim[i].get(c) for c in cols):
                groups[g] += 1
        # a MEMW/IOW data-value mismatch = a functional value bug
        if real[i].get("t") in (2, 3, 4) and real[i]["bs_early"] in (2, 6) \
                and real[i].get("ad_data") != sim[i].get("ad_data"):
            data_val = True
    prim = groups.most_common(1)[0][0] if groups else "-"
    return prim, data_val


def escape_at_div(real, sim, fb):
    """True if EITHER leg is executing out-of-image (linear >= 0x10000) in the
    divergence window [fb, fb+8] - the divergence is an escape consequence
    (one leg wandered out of the 64K image), not a genuine in-image functional
    bug. Excludes the normal reset-vector startup (that is at/above 0xFFFF0 but
    happens long before any FUNCTIONAL first_bad)."""
    # only T1 (t==1) address-phase rows with an ACTIVE bus cycle (code fetch /
    # mem read / mem write = bs 4/5/6) carry a clean physical address; T2/T3
    # multiplex segment/status onto the upper ad_addr bits, so they must be
    # ignored. A passive (bs=7) high address is a park - checked separately.
    for rows in (real, sim):
        for i in range(max(0, fb - 2), min(fb + 8, len(rows))):
            r = rows[i]
            a = r.get("ad_addr", 0) & 0xFFFFF
            active_t1 = r.get("t") == 1 and r["bs_early"] in (4, 5, 6)
            passive_park = r["bs_early"] == 7 and r.get("t") == 0
            if (active_t1 or passive_park) and a >= 0x10000:
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", default="mc1")
    a = ap.parse_args()
    cdir = CAMPAIGNS / a.cid
    rows = [json.loads(l) for l in (cdir / "results.jsonl").read_text().splitlines()
            if l.strip()]
    func = [r for r in rows if r["verdict"] == "FUNCTIONAL"]

    fam = defaultdict(list)
    n_escape = 0
    for r in func:
        c = cap(cdir, r)
        fb = r.get("first_bad")
        if not c or fb is None:
            fam[("nocap", "-", "-")].append(r); continue
        real, sim = c["real"], c["sim"]
        win = r["win"]
        # tight filter: exclude escape-consequence divergences (either leg
        # out-of-image at the divergence) - those are task #32, not #31.
        if escape_at_div(real, sim, fb):
            n_escape += 1
            continue
        pos = fb / max(1, win)                      # early vs late in the run
        prim, data_val = div_char(real, sim, fb)
        sub = (r["sub"] or "").split("@")[0].split(":")[0]  # func / done_mismatch
        subk = (r["sub"] or "").split("@")[0]              # func:W / func:R / ...
        waited = "waited" if (r["waits"].get("wrand")
                              or (r["waits"].get("fixed") or 0) > 0) else "w0"
        # family key: sub-kind x primary-column x data-value x waited
        if sub == "done_mismatch":
            # split prefetch-split (early, structural) from fall-through (late)
            kind = "dm_prefetch_split" if pos < 0.6 and prim in (
                "queue", "bus", "ctrl", "addr") else "dm_fallthrough"
            key = (kind, prim, waited)
        else:
            kind = subk + ("+dataval" if data_val else "")
            key = (kind, prim, waited)
        fam[key].append(dict(r, _pos=pos, _prim=prim))

    genuine = sum(len(v) for k, v in fam.items() if k[0] != "nocap")
    print(f"# task #31 family map over {a.cid}: {len(func)} FUNCTIONAL total; "
          f"{n_escape} escape-consequence (-> task #32); "
          f"{genuine} GENUINE in-image divergences\n")
    print("| family (kind / prim-col / waits) | n | tiers | waits-classes | rep |")
    print("|---|---|---|---|---|")
    for key, rs in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        kind, prim, waited = key
        tiers = ",".join(f"{k}:{v}" for k, v in
                         Counter(r["tier"] for r in rs).most_common())
        wcs = ",".join(f"{k}:{v}" for k, v in
                       Counter(wc(r) for r in rs).most_common(4))
        rep = min(rs, key=lambda r: r["k"])
        print(f"| {kind} / {prim} / {waited} | {len(rs)} | {tiers} | {wcs} "
              f"| {rep['cid']}/{rep['k']} |")
    # locate k=15
    for key, rs in fam.items():
        if any(r["k"] == 15 for r in rs):
            print(f"\nk=15 -> family {key}")


if __name__ == "__main__":
    main()
