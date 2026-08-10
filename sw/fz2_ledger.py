#!/usr/bin/env python3
"""fz2_ledger -- RE-DERIVE THE A-15 TRUE FAILURE LEDGER FROM A BANKED CORPUS.

Pre-registered in `docs/notes/fz2_f14_prereg_2026-08-10.md` §6.6 and amended by
`docs/notes/fz2_f14_erratum_e1_2026-08-10.md`.  It exists because **no tool in
this tree writes `fz2_failure_ledger_2026-08-09.json`** -- the only references
to that file are consumers (`sw/b1_rescore.py`, `sw/fz2_c1_rescore.py`) -- so a
sitting that re-captures the corpus has nothing to re-derive the ledger with.

WHAT IS DERIVED AND WHAT IS CARRIED FORWARD, AND WHY THE SPLIT
--------------------------------------------------------------
DERIVED, from `results.jsonl` alone, with the rules pinned against the
committed ledger BEFORE this tool was written (erratum E-1 §1):

    membership       a seed is a FAILURE iff `bad_rows != 0`
                     -- set-equal to the committed ledger's 198, symmetric
                        difference EMPTY, and `verdict == "SUCCESS"` is the
                        same predicate (3,639 both ways)
    discards         `ps3_8080` is True  (amendment A-12: out of the
                     denominator too).  A-2: this is a SOCKET-leg predicate.
    first_bad_row    == `first_bad`                          198 / 198
    diverging_rows   == `bad_rows` + `flick`                 198 / 198
    compare_window   == `win`
    arch             NODUMP iff not (done_real and done_sim), or
                     `mech == "FORGED_DONE"`, or either dump is absent /
                     `arch_restart`; else the differing register names,
                     excluding MAGIC, comma-joined and sorted; else OK.
                     Reproduces 196 / 198 -- the two residuals
                     (`fz2c/410067`, `fz2e/516001`, both OK in the committed
                     ledger) are an OK/NODUMP edge case, REPORTED by the
                     control and not smoothed.

CARRIED FORWARD, by seed, from the committed ledger:

    family           the A-15 partition.  §38.9 is explicit that "the partition
                     is a record of how the bus structure classified each seed
                     and it is not rewritten because a later reading grouped two
                     of its cells."  There is no committed classifier for it --
                     §38.5 describes an ordered decision list in prose -- so
                     re-implementing it by inspection would be inventing a
                     partition, not reproducing one.  A seed that is a failure
                     in BOTH corpora keeps its label.
    the §38.9 overlay  the 40 named missed-trap seeds, intersected with the new
                     failure set.

NEW failures -- seeds that fail now and did not before -- are NOT given a family
by guesswork.  They are labelled `NEW/UNCLASSIFIED` and ITEMIZED, because
`P-7` predicts there are none and a silent absorption of one into a family
would hide exactly the finding this sitting exists to catch.

THE ACCEPTANCE CONTROL -- `--control`
-------------------------------------
Runs the identical derivation against the FLASH #13 archive and requires it to
reproduce the committed ledger: 198 failures as a SET, the 14 family counts,
`first_bad_row` 198/198, `diverging_rows` 198/198, the 3 discards, and the
denominator 3,837.  **Registered before the new capture existed so the
derivation cannot be tuned to it.**  If the control does not reproduce, the new
ledger is not quotable and the finding is the tool, not the corpus.
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGNS = os.path.join(ROOT, "sw/testdata/campaigns")
COMMITTED = os.path.join(ROOT, "sw/testdata/fz2/fz2_failure_ledger_2026-08-09.json")
CIDS = ("fz2c", "fz2e")

# §38.9's 40-seed missed-trap overlay, verbatim from
# fz2_corpus_prereg_2026-08-08.md md:6043-6049.
OVERLAY_38_9 = """
fz2c/400007 fz2c/400019 fz2c/400022 fz2c/402075 fz2c/406073 fz2c/407019
fz2c/407024 fz2c/407057 fz2c/407064 fz2c/408079 fz2c/409062 fz2c/410000
fz2c/410053 fz2c/410062 fz2e/507064 fz2e/512021 fz2e/512027 fz2e/518039
fz2e/518044 fz2e/518046 fz2e/518072 fz2e/519032 fz2e/521012 fz2e/521036
fz2e/521054 fz2e/521062 fz2e/522047 fz2e/522051 fz2e/522071 fz2e/522075
fz2e/528035 fz2e/529017 fz2e/529036 fz2e/529040 fz2e/529055 fz2e/530024
fz2e/530030 fz2e/531000 fz2e/531036 fz2e/535042
""".split()

DISCARD_REASON = ("ps3_8080 runtime 8080 entry "
                  "(amendment A-12: out of the denominator too)")


# --------------------------------------------------------------------------- #
# the derivation
# --------------------------------------------------------------------------- #
def arch_field(r):
    """The ledger's `arch` string.  See the module docstring for provenance."""
    if not (r.get("done_real") and r.get("done_sim")):
        return "NODUMP"
    if r.get("mech") == "FORGED_DONE":
        return "NODUMP"
    if r.get("arch_restart"):
        return "NODUMP"
    a, b = r.get("arch_words"), r.get("arch_sim_words")
    if not a or not b:
        return "NODUMP"
    if not r.get("arch_ok") or r.get("arch_sim_ok") is False:
        return "NODUMP"
    diff = sorted(k for k in a if k != "MAGIC" and a[k] != b.get(k))
    return ",".join(diff) if diff else "OK"


def read_rows(suffix):
    out = {}
    for cid in CIDS:
        p = os.path.join(CAMPAIGNS, cid + suffix, "results.jsonl")
        if not os.path.exists(p):
            sys.exit(f"fz2_ledger: no such corpus leg: {p}")
        with open(p) as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                out[r["seed"]] = r
    return out


def sha256_of(path):
    if not path:
        return None
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def capture_path(cid, r, suffix):
    """The retained capture for a seed, if one exists.  Named
    `<tier>_<k>_<12hex>.json.gz`; the hex is the cfg hash."""
    d = os.path.join(CAMPAIGNS, cid + suffix, "captures")
    if not os.path.isdir(d):
        return None
    stem = f"{r['tier']}_{r['k']}_"
    for n in os.listdir(d):
        if n.startswith(stem) and n.endswith(".json.gz"):
            return os.path.relpath(os.path.join(d, n), ROOT)
    return None


def derive(suffix, prior, with_sha=True):
    rows = read_rows(suffix)
    prior_fam = {f["seed"]: f["family"] for f in prior["failures"]}

    discards, failures = [], []
    denom = 0
    rows_compared = rows_diverging = 0
    for seed in sorted(rows):
        r = rows[seed]
        cid = r["cid"]
        if r.get("ps3_8080"):
            cap = capture_path(cid, r, suffix)
            discards.append({
                "seed": seed, "tier": r["tier"],
                "banked_verdict": r["verdict"], "banked_sub": r["sub"],
                "bad_rows": r["bad_rows"], "reason": DISCARD_REASON,
                "capture": cap,
                "capture_sha256": sha256_of(cap) if with_sha else None})
            continue
        denom += 1
        rows_compared += r["win"] or 0
        rows_diverging += r["bad_rows"] or 0
        if r["bad_rows"] == 0:
            continue
        cap = capture_path(cid, r, suffix)
        failures.append({
            "seed": seed, "cid": cid, "k": r["k"], "tier": r["tier"],
            "family": prior_fam.get(seed, "NEW/UNCLASSIFIED"),
            "new_failure": seed not in prior_fam,
            "banked_verdict": r["verdict"], "banked_sub": r["sub"],
            "first_bad_row": r["first_bad"],
            "diverging_rows": (r["bad_rows"] or 0) + (r.get("flick") or 0),
            "compare_window": r["win"],
            "arch": arch_field(r),
            "arch_match": r.get("arch_match"),
            "done_chip": r.get("done_real"), "done_core": r.get("done_sim"),
            "mech": r.get("mech"),
            "capture": cap,
            "capture_sha256": sha256_of(cap) if with_sha else None,
            "image_sha256": r.get("image_sha256")})

    matched = denom - len(failures)
    fam = collections.Counter(f["family"] for f in failures)
    era = None
    for r in rows.values():
        era = r.get("era")
        break
    return {
        "stage": "fz2 TRUE FAILURE LEDGER (amendment A-15), re-derived",
        "tool": "sw/fz2_ledger.py",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "corpus_suffix": suffix or "(live)",
        "era": era,
        "corpus": {
            "campaigns": list(CIDS),
            "seeds": len(rows),
            "discards": len(discards),
            "denominator": denom,
            "matched": matched,
            "failures": len(failures),
            "seed_match_pct": round(100.0 * matched / denom, 4) if denom else None,
            "seed_match_pct_incl_discards":
                round(100.0 * matched / len(rows), 4) if rows else None,
            "rows_compared": rows_compared,
            "rows_diverging": rows_diverging,
            "row_match_pct": round(100.0 * (rows_compared - rows_diverging)
                                   / rows_compared, 4) if rows_compared else None},
        "family_counts": dict(sorted(fam.items())),
        "overlay_38_9": sorted(set(OVERLAY_38_9)
                               & {f["seed"] for f in failures}),
        "failures": failures,
        "discards": discards}


# --------------------------------------------------------------------------- #
# C-LEDGER, the acceptance control
# --------------------------------------------------------------------------- #
def control(suffix):
    prior = json.load(open(COMMITTED))
    got = derive(suffix, prior, with_sha=False)
    ref_f = {f["seed"]: f for f in prior["failures"]}
    got_f = {f["seed"]: f for f in got["failures"]}
    checks = []

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    chk("failure SET identical", set(ref_f) == set(got_f),
        f"ref {len(ref_f)}  got {len(got_f)}  "
        f"symdiff {sorted(set(ref_f) ^ set(got_f))[:8]}")
    chk("denominator 3,837",
        got["corpus"]["denominator"] == prior["corpus"]["denominator"],
        f"{got['corpus']['denominator']} vs {prior['corpus']['denominator']}")
    chk("matched 3,639", got["corpus"]["matched"] == prior["corpus"]["matched"],
        f"{got['corpus']['matched']} vs {prior['corpus']['matched']}")
    chk("discards 3", len(got["discards"]) == len(prior["discards"]),
        f"{len(got['discards'])} vs {len(prior['discards'])}; "
        f"{sorted(d['seed'] for d in got['discards'])}")
    fam_ref = {k: v for k, v in prior["family_counts"].items()}
    chk("14 family counts", got["family_counts"] == fam_ref,
        "identical" if got["family_counts"] == fam_ref
        else f"{got['family_counts']} vs {fam_ref}")
    common = set(ref_f) & set(got_f)
    fb = sum(1 for s in common
             if ref_f[s]["first_bad_row"] == got_f[s]["first_bad_row"])
    chk(f"first_bad_row {fb}/{len(common)}", fb == len(common), "")
    dv = sum(1 for s in common
             if ref_f[s]["diverging_rows"] == got_f[s]["diverging_rows"])
    chk(f"diverging_rows {dv}/{len(common)}", dv == len(common), "")
    ar = [s for s in common if ref_f[s]["arch"] != got_f[s]["arch"]]
    # The two OK/NODUMP residuals are KNOWN and REPORTED, not asserted away.
    chk(f"arch {len(common) - len(ar)}/{len(common)} (<=2 known residuals)",
        len(ar) <= 2,
        "" if not ar else "; ".join(f"{s} ref={ref_f[s]['arch']} "
                                    f"got={got_f[s]['arch']}" for s in ar))
    chk("overlay 38.9 = 40", len(got["overlay_38_9"]) == 40,
        f"{len(got['overlay_38_9'])}")

    print("  --- C-LEDGER: the re-derivation against the FLASH #13 archive ---")
    bad = 0
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f"   {detail}" if detail else ""))
        bad += not ok
    print(f"  C-LEDGER: {'PASS' if not bad else 'FAIL'} "
          f"({len(checks) - bad}/{len(checks)})")
    return 0 if not bad else 1


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suffix", default="",
                    help="campaign dir suffix, e.g. '-F13-archive'")
    ap.add_argument("--control", action="store_true",
                    help="run C-LEDGER against --suffix and exit")
    ap.add_argument("--out", help="write the derived ledger here")
    ap.add_argument("--diff", metavar="LEDGER",
                    help="seed-by-seed diff against a ledger JSON "
                         "(default: the committed one)")
    a = ap.parse_args()

    if a.control:
        return control(a.suffix)

    prior = json.load(open(COMMITTED))
    led = derive(a.suffix, prior)
    c = led["corpus"]
    print(f"  corpus{'' if not a.suffix else ' ' + a.suffix}: "
          f"{c['seeds']} seeds, {c['discards']} discards, "
          f"denominator {c['denominator']}")
    print(f"  SEED MATCH  {c['matched']:,} / {c['denominator']:,} "
          f"= {c['seed_match_pct']} %      failures {c['failures']}")
    print(f"  ROW  MATCH  {c['rows_compared'] - c['rows_diverging']:,} / "
          f"{c['rows_compared']:,} = {c['row_match_pct']} %  "
          f"(DISCARDS EXCLUDED -- this is §38.4's registered row figure, "
          f"md:5793, which has no field in the committed JSON)")
    print("  families:")
    for k, v in led["family_counts"].items():
        print(f"    {k:46s} {v:3d}")
    print(f"  §38.9 overlay still failing: {len(led['overlay_38_9'])}")
    new = [f["seed"] for f in led["failures"] if f["new_failure"]]
    if new:
        print(f"  *** {len(new)} NEW FAILURE(S) -- itemized, not absorbed ***")
        for s in new:
            f = next(x for x in led["failures"] if x["seed"] == s)
            print(f"      {s}  first_bad {f['first_bad_row']}  "
                  f"rows {f['diverging_rows']}  arch {f['arch']}")
    else:
        print("  0 new failures")

    ref = json.load(open(a.diff)) if a.diff else prior
    ref_s = {f["seed"] for f in ref["failures"]}
    got_s = {f["seed"] for f in led["failures"]}
    left, came = sorted(ref_s - got_s), sorted(got_s - ref_s)
    print(f"\n  LEFT the ledger : {len(left)}")
    ref_f = {f["seed"]: f for f in ref["failures"]}
    byfam = collections.Counter(ref_f[s]["family"] for s in left)
    for k, v in sorted(byfam.items()):
        print(f"    {k:46s} {v:3d}")
    print(f"  ENTERED the ledger: {len(came)}   {came if came else ''}")

    if a.out:
        with open(a.out, "w") as f:
            json.dump(led, f, indent=1)
        print(f"\n  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
