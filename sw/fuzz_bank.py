#!/usr/bin/env python3
"""fuzz_bank - promote divergent/representative fuzz seeds into the standing
replay bank (task #29 Phase 6).

The bank is the campaign's regression corpus: the CHIP leg the driver already
captured (chip runs once ever per banked seed) plus full provenance, so
check_fuzz_bank.py can regenerate the image (hash-checked - GEN-DRIFT hard
fail), replay it in the Verilator TB, and re-classify against the banked chip
rows forever without re-touching the board.

Layout (per the plan):
  tests/v30/fuzz_bank/<cid>/
      manifest.json                         campaign provenance + promotion tally
      seeds/<tier>_<k>_<cfghash>.json.gz     one banked entry (chip rows + prov)
      sigs/<sig>.jsonl                       seed index per signature
      results/shard_000.jsonl.gz             compact per-seed result lines
  tests/v30/fuzz_bank/sig_ledger.json        top-level novelty ledger

Promotion (strict precedence, plan's criteria):
  * every FUNCTIONAL
  * every provenance-alarm QUARANTINE           (cap 20)
  * unexplained TIMING (no rule hit)            (cap 10 / signature)
  * first 50 seeds per KNOWN_ACCEPTED rule klass + novel slip-context sigs
  * a 1-in-50 seeded sample of CADENCE          (representative floor corpus)
  * 100 stratified SUCCESS ballast              (fab-vs-TB float-floor alarm;
                                                 needs captured SUCCESS rows -
                                                 see --ballast-from note)
25 MB / campaign cap (json.gz); the driver's gzipped captures/ supply chip rows.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
from fuzz_accept import AcceptEngine                    # noqa: E402

_ENGINE = AcceptEngine.load()
BANK = SW.parent / "tests" / "v30" / "fuzz_bank"
LEDGER = BANK / "sig_ledger.json"
CAMPAIGNS = SW / "testdata" / "campaigns"
CAP_MB = 25
FUNC = fc.FUNCTIONAL
TIM = fc.TIMING
QUAR = fc.QUARANTINE
KACC = fc.KNOWN_ACCEPTED
SUCC = fc.SUCCESS


def _load_capture(cap_dir, tier, k, cfg_hash):
    p = cap_dir / f"{tier}_{k}_{cfg_hash}.json.gz"
    if not p.exists():
        return None
    return json.loads(gzip.decompress(p.read_bytes()))


def _arch(rows, window):
    return fc.arch_dump(rows, window)


def promote(cid, ov, results_path=None, cap_dir=None):
    """Select + write banked entries for one campaign. Returns a tally dict."""
    results_path = results_path or (CAMPAIGNS / cid / "results.jsonl")
    cap_dir = cap_dir or (CAMPAIGNS / cid / "captures")
    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]

    # per-sig counters for the caps
    timing_by_sig = Counter()
    rule_seen = defaultdict(int)
    cadence_n = 0
    quar_n = 0
    slip_sigs = set()

    promoted = []            # (reason, result_row, capture)
    for r in rows:
        v = r["verdict"]
        sig = r.get("sig")
        cap = _load_capture(cap_dir, r["tier"], r["k"], r["cfg_hash"])
        reason = None
        if v == FUNC:
            reason = "functional"
        elif v == QUAR and r.get("alarms"):
            if quar_n < 20:
                reason = "provenance_alarm"
                quar_n += 1
        elif v == TIM and not r.get("rule_hits"):
            if timing_by_sig[sig] < 10:
                reason = "timing_unexplained"
                timing_by_sig[sig] += 1
        elif v == KACC:
            klass = r["rule_hits"][0]["klass"] if r.get("rule_hits") else "?"
            drift = r.get("drift") or {}
            slipctx = tuple(sorted((s.get("occ"),) for s in drift.get("slips", [])[:1]))
            novel_slip = slipctx and slipctx not in slip_sigs
            if klass == "cadence":
                if cadence_n % 50 == 0 or novel_slip:      # 1-in-50 + novel slip
                    reason = "cadence_sample"
                cadence_n += 1
            elif rule_seen[klass] < 50:
                reason = f"rule_first50:{klass}"
            rule_seen[klass] += 1
            if novel_slip:
                slip_sigs.add(slipctx)
        # SUCCESS ballast handled below (needs captured rows)
        if reason and cap is not None:
            promoted.append((reason, r, cap))

    # 100 stratified SUCCESS ballast - only those whose rows were captured
    succ = [r for r in rows if r["verdict"] == SUCC]
    ball = 0
    for r in succ:
        if ball >= 100:
            break
        cap = _load_capture(cap_dir, r["tier"], r["k"], r["cfg_hash"])
        if cap is not None:
            promoted.append(("success_ballast", r, cap))
            ball += 1

    return _write_bank(cid, ov, rows, promoted)


def _write_bank(cid, ov, all_rows, promoted):
    cdir = BANK / cid
    (cdir / "seeds").mkdir(parents=True, exist_ok=True)
    (cdir / "sigs").mkdir(exist_ok=True)
    (cdir / "results").mkdir(exist_ok=True)

    sig_index = defaultdict(list)
    shard = []
    tally = Counter()
    total_bytes = 0
    ledger_sigs = []
    for reason, r, cap in promoted:
        window = r.get("win") or (cap["line"].get("win"))
        chip = cap["real"]
        arch = _arch(chip, window or min(len(chip), 4000))
        entry = {
            "cid": cid, "k": r["k"], "seed": r["seed"], "tier": r["tier"],
            "cfg_hash": r["cfg_hash"], "ov": ov,
            "gen_git": r.get("gen_git"), "image_sha256": r["image_sha256"],
            "verdict": r["verdict"], "sub": r["sub"], "sig": r.get("sig"),
            "sigv": r.get("sigv"), "first_bad": r.get("first_bad"),
            "bad_rows": r.get("bad_rows"), "func_mismatch": r.get("func_mismatch"),
            "done_real": r.get("done_real"), "done_sim": r.get("done_sim"),
            "rule_hits": r.get("rule_hits", []), "alarms": r.get("alarms", []),
            "brkem_pos": r.get("brkem_pos", []),
            "lea_mod3_pos": r.get("lea_mod3_pos", []),
            "evt": r.get("evt"), "waits": r.get("waits"),
            "nmin": r.get("nmin"), "nmax_eff": r.get("nmax_eff"),
            "has_brkem": r.get("has_brkem"), "has_tf": r.get("has_tf"),
            "raw_mode": r.get("raw_mode"),
            "promoted_reason": reason,
            "chip_arch": arch,
            "chip_rows": chip,          # the socket leg (regenerable image; rows kept)
            "banked_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        # compute the chip-vs-TB REPLAY verdict now (the round-trip target;
        # deterministic given the TB build) - the banked `verdict` above is the
        # chip-vs-fabric DISCOVERY verdict, kept as provenance.
        from check_fuzz_bank import replay_classify
        _sha, rv, rsig, rsub = replay_classify(entry, _ENGINE)
        entry["replay_verdict"] = rv
        entry["replay_sig"] = rsig
        entry["replay_sub"] = rsub
        # ledger tracks BOTH the discovery sig (chip-vs-fabric; Phase-7 campaign
        # novelty) and the replay sig (chip-vs-TB; check_fuzz_bank new-sig warn)
        klass = r["rule_hits"][0]["klass"] if r.get("rule_hits") else None
        for _s in {r.get("sig"), rsig}:
            if _s:
                ledger_sigs.append((_s, r["verdict"], r["tier"],
                                    r.get("waits"), klass))
        blob = gzip.compress(json.dumps(entry).encode())
        total_bytes += len(blob)
        if total_bytes > CAP_MB * (1 << 20):
            tally["_capped"] += 1
            continue
        (cdir / "seeds" / f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz").write_bytes(blob)
        if r.get("sig"):
            sig_index[r["sig"]].append({"k": r["k"], "reason": reason,
                                        "verdict": r["verdict"]})
        shard.append({k: entry[k] for k in
                      ("k", "seed", "tier", "cfg_hash", "verdict", "sub", "sig",
                       "promoted_reason", "image_sha256")})
        tally[reason] += 1

    for sig, seeds in sig_index.items():
        (cdir / "sigs" / f"{sig}.jsonl").write_text(
            "\n".join(json.dumps(s) for s in seeds) + "\n")
    with gzip.open(cdir / "results" / "shard_000.jsonl.gz", "wt") as fh:
        for s in shard:
            fh.write(json.dumps(s) + "\n")

    manifest = {
        "cid": cid, "ov": ov,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_results": len(all_rows), "n_banked": sum(tally[k] for k in tally
                                                    if not k.startswith("_")),
        "promotion": dict(tally),
        "bytes": total_bytes, "cap_mb": CAP_MB,
        "verdict_census": dict(Counter(r["verdict"] for r in all_rows)),
    }
    # comprehensive Phase-7 baseline: record EVERY discovery sig the campaign
    # produced (not only the banked subset), so a genuinely-new mechanism next
    # campaign is flagged and the pilots' own sigs are not re-flagged.
    for r in all_rows:
        if r.get("sig"):
            ledger_sigs.append((r["sig"], r["verdict"], r["tier"],
                                r.get("waits"),
                                (r["rule_hits"][0]["klass"] if r.get("rule_hits")
                                 else None)))
    (cdir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    _update_ledger(cid, ledger_sigs)
    return manifest


def _update_ledger(cid, ledger_sigs):
    """Record the chip-vs-TB REPLAY signatures banked from this campaign so
    Phase-7 novelty detection recognises them (a new sig = not in the ledger)."""
    led = json.loads(LEDGER.read_text()) if LEDGER.exists() else \
        {"sigv": fc.SIGV, "sigs": {}, "legacy_baseline": {}}
    for sig, verdict, tier, waits, klass in ledger_sigs:
        e = led["sigs"].setdefault(sig, {
            "first_campaign": cid, "first_verdict": verdict, "klass": klass,
            "tier": tier,
            "waits_class": "wrand" if (waits or {}).get("wrand")
            else f"w{(waits or {}).get('fixed', 0)}", "count": 0})
        e["count"] += 1
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1))


def backfill_legacy(path=None):
    """Seed the ledger's legacy baseline from the pre-classifier
    fuzz_divergences.jsonl (no sigs; the historical known-divergence corpus for
    Phase-7 cross-reference)."""
    path = path or (SW / "testdata" / "fuzz_divergences.jsonl")
    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    led = json.loads(LEDGER.read_text()) if LEDGER.exists() else \
        {"sigv": fc.SIGV, "sigs": {}, "legacy_baseline": {}}
    # coarse dedup key from the available metadata (no capture -> no exact sig)
    keyed = {}
    for e in entries:
        key = f"{e['seed']}|w{e.get('waits', 0)}|{'wr' if e.get('wrand') else ''}"
        keyed[key] = {"seed": e["seed"], "waits": e.get("waits", 0),
                      "wrand": bool(e.get("wrand")),
                      "first_row": e.get("first_row"),
                      "bad_rows": e.get("bad_rows"),
                      "inject_int": e.get("inject_int"), "hw_ab": e.get("hw_ab")}
    led["legacy_baseline"] = {
        "source": "sw/testdata/fuzz_divergences.jsonl", "n": len(entries),
        "note": "pre-classifier hw-ab divergences; no per-seed signature "
                "(captures were not retained). Coarse (seed|waits|wrand) keys "
                "for Phase-7 cross-reference; not sig-keyed novelty.",
        "entries": list(keyed.values()),
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1))
    print(f"backfilled {len(entries)} legacy divergences ({len(keyed)} unique "
          f"keys) -> {LEDGER}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote")
    p.add_argument("cid")
    p.add_argument("--ov", default="{}", help="JSON overrides dict used for the run")
    b = sub.add_parser("backfill-legacy")
    b.add_argument("--path", default=None)
    a = ap.parse_args()
    if a.cmd == "promote":
        m = promote(a.cid, json.loads(a.ov))
        print(f"banked {m['n_banked']} from {m['n_results']} results "
              f"({m['bytes']/1024:.0f} KB); promotion={m['promotion']}")
    elif a.cmd == "backfill-legacy":
        backfill_legacy(Path(a.path) if a.path else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
