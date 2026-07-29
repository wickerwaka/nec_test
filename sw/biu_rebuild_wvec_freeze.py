#!/usr/bin/env python3
"""Board-free model-side wvec replay freeze for the BIU-rebuild A/B baseline.

Stage-A4: freeze a deterministic per-cycle MODEL (Verilator TB) trace digest over
a fixed corpus + wvec set, so that Stage C/D (grid_phase promotion, shadow
scheduler) can A/B the modified RTL against this baseline and attribute every
changed row. Board-free (run_tb_internal only, NO run_chip) -- Stage A does not
touch the board. Deterministic: fixed seeds + fixed wvec seeds.

Corpus = the canonical class5 gap-error census seeds (fz90000..fz90019), plus the
random-wait settings that exercise the cadence laws. Per case we record the
sha256 of the normalized bus-access stream (bus-type, t-state, addr, qs) and the
row count -- a compact, tamper-evident baseline. Re-run after an RTL change and
diff the JSON: any digest delta is a model-behavior change to adjudicate.

Usage:
  python3 sw/biu_rebuild_wvec_freeze.py --out docs/notes/biu_rebuild_wvec_baseline.json
  python3 sw/biu_rebuild_wvec_freeze.py --check docs/notes/biu_rebuild_wvec_baseline.json
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from causal_wrand import run_tb_internal, accesses          # noqa: E402
from gen_seq import generate                                # noqa: E402
from check_seq import compose                               # noqa: E402
import random as _r                                         # noqa: E402

SEEDS = list(range(90000, 90020))          # canonical class5 corpus (A4 baseline)
# B0 directed-gate seeds (biu_law_gatesearch.py discriminators): seeds where
# breaking a narrow veto law changes the OBSERVABLE model bus stream, so the
# timing-sensitive wvec gate catches its mutation. 90270 = G-LC4a (pf_rsv_lead),
# 90364 = G-LC2 (low-band pause). Both discriminate at ws5/wmax1.
DIRECTED_SEEDS = [90270, 90364]
SEEDS = SEEDS + DIRECTED_SEEDS
# (ws, wmax): w0 control + the random-wait settings the cadence laws live on.
WVECS = [(0, 0), (5, 1), (7, 3), (11, 7)]
NROWS = 4200


def wv_of(ws, wmax):
    rr = _r.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def digest_case(seed, ws, wmax):
    g = generate(f"fz{seed}", exts=())
    image, _meta = compose(g)
    wv = wv_of(ws, wmax)
    rows = run_tb_internal(image, NROWS, wv)
    # run_tb_internal rows key t/bs/qs/addr; accesses() wants bs_early/ad_addr/
    # ad_data/qs/t (same remap class5_gaperr.analyze_vec applies).
    acc = accesses([dict(t=r["t"], bs_early=r["bs"], qs=r["qs"],
                         ad_addr=r["addr"], ad_data=0) for r in rows])
    # normalize to the observable per-bus-cycle stream. CRITICAL: include the
    # inter-T1 CYCLE GAP (t1[i]-t1[i-1]) -- the cadence metric the class5/waited
    # laws actually move. Without it the digest captures only access IDENTITY
    # (bs/addr/tw) and is BLIND to pure +-1-slot timing shifts (proven: the
    # mutation battery missed M-LC2/LC3/LC4a/LC6 with an identity-only digest).
    parts = []
    prev_t1 = None
    for a in acc:
        gap = "" if prev_t1 is None else str(a['t1'] - prev_t1)
        parts.append(f"{a['bs']},{a['tw']},{a['addr']},{a['npops']},g{gap}")
        prev_t1 = a['t1']
    norm = ";".join(parts)
    h = hashlib.sha256(norm.encode()).hexdigest()[:16]
    return {"rows": len(rows), "accesses": len(acc), "sha": h}


def build():
    out = {"seeds": SEEDS, "wvecs": WVECS, "nrows": NROWS, "cases": {}}
    for seed in SEEDS:
        for ws, wmax in WVECS:
            key = f"fz{seed}:ws{ws}:wmax{wmax}"
            out["cases"][key] = digest_case(seed, ws, wmax)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--check")
    a = ap.parse_args()
    cur = build()
    if a.check:
        ref = json.loads(Path(a.check).read_text())
        diffs = [k for k in cur["cases"]
                 if ref["cases"].get(k) != cur["cases"][k]]
        if diffs:
            print(f"wvec-freeze A/B: {len(diffs)} case(s) DIVERGED from baseline:")
            for k in diffs[:20]:
                print(f"  {k}: ref={ref['cases'].get(k)} cur={cur['cases'][k]}")
            return 1
        print(f"wvec-freeze A/B: PASS ({len(cur['cases'])} cases identical)")
        return 0
    dst = Path(a.out or "docs/notes/biu_rebuild_wvec_baseline.json")
    dst.write_text(json.dumps(cur, indent=1) + "\n")
    print(f"wvec-freeze: wrote {len(cur['cases'])} case digests -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
