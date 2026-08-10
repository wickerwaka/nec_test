#!/usr/bin/env python3
"""b1_rescore -- the OFFLINE corpus rescore instrument for survey fix #2 (B1).

WHY IT EXISTS, AND WHAT IT IS NOT.  The fz2 corpus was captured on the BOARD:
leg `real` is the socketed chip (`use_core=0`), leg `sim` is the FABRIC core
(`use_core=1`).  An offline sitting cannot re-take the fabric leg.  So this
file re-runs the CORE leg in Verilator (`tb_v30_core`, `--core ucore`) on the
regenerated image / wait vector / event and scores it against the BANKED CHIP
ROWS with the campaign's OWN comparator (`fuzz_classify.diff_rows`) at each
seed's OWN comparison window.  The chip leg is silicon and never moves; only
the core leg is re-measured.  Every figure here is therefore RTL-vs-SILICON.

⚠ IT IS A DIFFERENT INSTRUMENT FROM THE BANKED ONE, AND ITS CONTROL SAYS SO.
Measured at this sitting on the 24 `B1` seeds: the offline leg reproduces the
banked `first_bad` and the banked first-divergence SIGNATURE on 21 of 24, but
its `bad_rows` are far larger (278-846 against 4), because `tb_v30_core` and
the Verilated `system_large`/fabric disagree downstream on classes that have
nothing to do with this fix.  **So `bad_rows == 0` is NOT a usable closure
criterion here and this file does not use one.**  It scores two things:

  (A) THE MECHANISM, DIRECTLY.  Every HALT pseudo-cycle in the window: the
      value the core PUBLISHES on the display row (`ad_data`) and on its T1
      (`ad_addr`, all 20 bits) against the chip's.  This is the quantity the
      fix is about and it is scored site by site, not seed by seed.
  (B) NO COLLATERAL DAMAGE.  The full `diff_rows` differing-row SET, per seed,
      before and after.  Rows may LEAVE it; a row that ENTERS it is a
      regression and is printed with its coordinate.  This is what "zero lost"
      is measured by on this instrument.

Regeneration is asserted byte-exact against each seed's banked `image_sha256`,
with the stratum overrides from `fz2_w1`'s 48-stratum table -- `derive_case`
with an empty `ov` builds a DIFFERENT program (verified), so the assert is
load-bearing and a drift is a hard failure, never a quietly different image.

`tb_v30_core`'s composer has keyed on the core's own `AD_OE` port since SM3
sitting 20 (commit 0254d9f23e, F55 part 2), so a published-value change on a
HALT pseudo-cycle IS visible here.  The older note that this class is invisible
on this TB describes the pre-sitting-20 composer and no longer holds.
"""
import argparse, glob, gzip, hashlib, json, os, re, sys, time
from multiprocessing import Pool

SW = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SW)
ROOT = os.path.dirname(SW)

import fuzz_campaign as fzc                                   # noqa: E402
import fuzz_classify as fc                                    # noqa: E402
import fz2_w1 as w1                                           # noqa: E402

LEDGER = os.path.join(SW, "testdata/fz2/fz2_failure_ledger_2026-08-09.json")
CAPRE = re.compile(r"^(raw|soup)_(\d+)_([0-9a-f]+)\.json\.gz$")
BS_HALT = 3


def retained():
    """(cid, k, capture-path) for every seed with banked rows, both cids."""
    out = []
    for cid in ("fz2c", "fz2e"):
        d = os.path.join(SW, "testdata/campaigns", cid, "captures")
        for f in sorted(glob.glob(os.path.join(d, "*.json.gz"))):
            m = CAPRE.match(os.path.basename(f))
            if m:
                out.append((cid, int(m.group(2)),
                            os.path.relpath(f, ROOT)))
    return out


def halt_sites(chip, core, n, first_bad):
    """See below; `first_bad` bounds the population to sites still in lockstep."""
    return _halt_sites(chip, core, n, first_bad)


def _halt_sites(chip, core, n, first_bad):
    """(A): per HALT pseudo-cycle, does the core publish what the chip does?

    A site is a chip row with HALT status at `t == 0` whose next row is its
    `t == 1`.  Two cells per site: the display row's low-16 (`ad_data`, the
    column the comparator calls `nxta`) and the T1's full 20 bits.

    ⚠ ONLY SITES STILL IN LOCKSTEP ARE SCORED (`i <= first_bad`).  Past the
    first divergence the two legs are executing different programs and their
    HALT cycles are not the same event, so comparing them measures nothing.
    Without this bound the baseline reads 163 MISS of 337 sites, almost all of
    them downstream of an unrelated fork."""
    ok = bad = 0
    misses = []
    for i in range(min(n, len(chip), len(core)) - 1):
        r = chip[i]
        if r["bs_early"] != BS_HALT or r["t"] != 0 or chip[i + 1]["t"] != 1:
            continue
        if first_bad is not None and i > first_bad:
            break
        d_ok = r["ad_data"] == core[i]["ad_data"]
        a_ok = chip[i + 1]["ad_addr"] == core[i + 1]["ad_addr"]
        if d_ok and a_ok:
            ok += 1
        else:
            bad += 1
            misses.append((i, r["ad_data"], core[i]["ad_data"],
                           chip[i + 1]["ad_addr"], core[i + 1]["ad_addr"]))
    return ok, bad, misses


def _one(arg):
    cid, k, cap, win_hint = arg
    try:
        ov = w1.ov_of(w1.STRATA[w1._stratum_of(cid, k)])
        cfg = fzc.derive_case(cid, k, ov)
        img, meta = fzc.compose_case(fzc.build(cfg), cfg)
        with gzip.open(os.path.join(ROOT, cap)) as fh:
            chip = json.load(fh)["real"]
        core = fzc.capture_tb(img, meta, cfg, core="ucore")
        dr = fc.diff_rows(chip, core, window=win_hint) if win_hint \
            else fc.diff_rows(chip, core)
        fb = dr.rows[0].i if dr.rows else None
        ok, bad, misses = halt_sites(chip, core, dr.n, fb)
        return dict(cid=cid, k=k, seed=f"{cid}/{k}", n=dr.n,
                    bad_set=sorted({r.i for r in dr.rows if not r.flicker}),
                    fb=fb, evt=bool(cfg.get("evt") or meta.get("evt")),
                    halt_ok=ok, halt_bad=bad, misses=misses,
                    img=hashlib.sha256(bytes(img)).hexdigest(), err=None)
    except Exception as e:                                    # noqa: BLE001
        return dict(cid=cid, k=k, seed=f"{cid}/{k}", err=f"{type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", help="ledger family prefix, e.g. B1")
    ap.add_argument("--seeds", help="comma-separated seed names")
    ap.add_argument("--noevt", action="store_true",
                    help="only the no-event strata -- the domain in which "
                         "tb_v30_core can express the rig's stimulus at all")
    ap.add_argument("--all-retained", action="store_true",
                    help="every seed with banked rows (the offline denominator)")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--vs", help="an earlier --out to diff against")
    a = ap.parse_args()

    led = json.load(open(LEDGER))
    byseed = {f["seed"]: f for f in led["failures"]}
    winof = {s: f["compare_window"] for s, f in byseed.items()}
    imgof = {s: f.get("image_sha256") for s, f in byseed.items()}

    if a.all_retained:
        pop = [(c, k, p, winof.get(f"{c}/{k}")) for c, k, p in retained()]
        if a.noevt:
            pop = [x for x in pop
                   if w1.STRATA[w1._stratum_of(x[0], x[1])]["evt"] == "noevt"]
    else:
        names = ([s.strip() for s in a.seeds.split(",")] if a.seeds else
                 [s for s, f in byseed.items() if f["family"].startswith(a.family)])
        cap = {f"{c}/{k}": p for c, k, p in retained()}
        pop = [(byseed[s]["cid"], byseed[s]["k"], cap[s], winof[s])
               for s in sorted(names)]

    jobs = a.jobs or min(12, max(1, (os.cpu_count() or 2) - 2))
    print(f"b1_rescore: {len(pop)} seeds, jobs={jobs}, core=ucore")
    print(f"  engine: {fzc.tb_engine('ucore')}")
    t0 = time.time()
    res = []
    with Pool(jobs, initializer=fzc._engine) as pool:
        for r in pool.imap_unordered(_one, pop, chunksize=1):
            res.append(r)
            if len(res) % 50 == 0:
                print(f"  {len(res)}/{len(pop)}", flush=True)
    print(f"  {time.time()-t0:.0f}s")

    res.sort(key=lambda r: (r["cid"], r["k"]))
    errs = [r for r in res if r.get("err")]
    good = [r for r in res if not r.get("err")]
    drift = [r for r in good if r["seed"] in imgof and imgof[r["seed"]]
             and r["img"] != imgof[r["seed"]]]
    HO = sum(r["halt_ok"] for r in good)
    HB = sum(r["halt_bad"] for r in good)
    NB = sum(len(r["bad_set"]) for r in good)
    clean = sum(1 for r in good if not r["bad_set"])
    print(f"\n  seeds scored     {len(good)}   errors {len(errs)}  "
          f"image-drift {len(drift)}")
    print(f"  HALT sites       {HO+HB}   MATCH {HO}   MISS {HB}")
    print(f"  differing rows   {NB}   seeds with none {clean}/{len(good)}")
    for r in errs[:10]:
        print(f"  ERROR {r['seed']}: {r['err']}")

    if a.vs:
        old = {r["seed"]: r for r in json.load(open(a.vs))["rows"]}
        gained = lost = 0
        gseeds = []
        for r in good:
            o = old.get(r["seed"])
            if not o or "bad_set" not in o:
                continue
            ns, os_ = set(r["bad_set"]), set(o["bad_set"])
            g, l = ns - os_, os_ - ns
            gained += len(g); lost += len(l)
            if g:
                gseeds.append((r["seed"], sorted(g)[:6]))
        print(f"\n  vs {a.vs}:")
        print(f"    rows LEFT the differing set : {lost}")
        print(f"    rows ENTERED it (REGRESSION): {gained}")
        for s, g in gseeds[:20]:
            print(f"      + {s} at {g}")
        oh = sum(o["halt_bad"] for o in old.values() if "halt_bad" in o)
        print(f"    HALT-site MISS {oh} -> {HB}")

    json.dump(dict(engine=str(fzc.tb_engine('ucore')), rows=good,
                   halt_ok=HO, halt_bad=HB, nbad=NB),
              open(a.out, "w"))
    print(f"wrote {a.out}")
    return 1 if errs or drift else 0


if __name__ == "__main__":
    sys.exit(main())
