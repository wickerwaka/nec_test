#!/usr/bin/env python3
"""fuzz_report - campaign rollup for the massive fuzz expansion (task #29
Phase 6). Renders a markdown report over one or more campaigns' results.jsonl:

  * verdict x tier x waits-class table
  * rule-hit counts, with zero-hit rules flagged stale
  * signature novelty vs the top-level sig_ledger (new vs known)
  * drift summary + accepted-outlier tripwire (top-decile accepted-TIMING |o|)
  * QUARANTINE full enumeration
  * coverage summary (from the campaign coverage.json)
  * escalation-relevant seeds (w0 functionals, provenance alarms, new-sig w0 TIMING)
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_cov                                          # noqa: E402

CAMPAIGNS = SW / "testdata" / "campaigns"
LEDGER = SW.parent / "tests" / "v30" / "fuzz_bank" / "sig_ledger.json"
OUTDIR = SW.parent / "docs" / "notes"


def _waits_class(r):
    w = r.get("waits") or {}
    return "wrand" if w.get("wrand") else f"w{w.get('fixed', 0)}"


def _load(cid):
    p = CAMPAIGNS / cid / "results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] \
        if p.exists() else []


def report(cids):
    known = set(json.loads(LEDGER.read_text()).get("sigs", {})) \
        if LEDGER.exists() else set()
    L = ["# Fuzz campaign rollup (task #29)\n",
         f"\nCampaigns: {', '.join(cids)}\n"]
    all_rows = []
    for cid in cids:
        all_rows += [(cid, r) for r in _load(cid)]
    n = len(all_rows)
    L.append(f"\nTotal seeds: **{n}**\n")

    # 1. verdict x tier x waits-class
    L.append("\n## Verdict x tier x waits-class\n\n")
    cube = defaultdict(Counter)
    for cid, r in all_rows:
        cube[(r["tier"], _waits_class(r))][r["verdict"]] += 1
    verds = ["SUCCESS", "KNOWN_ACCEPTED", "TIMING", "FUNCTIONAL", "QUARANTINE"]
    L.append("| tier | waits | " + " | ".join(verds) + " | n |\n")
    L.append("|" + "---|" * (len(verds) + 3) + "\n")
    for (tier, wc), c in sorted(cube.items()):
        tot = sum(c.values())
        L.append(f"| {tier} | {wc} | " + " | ".join(str(c[v]) for v in verds)
                 + f" | {tot} |\n")

    # 2. rule hits
    L.append("\n## Rule hits (zero-hit = stale)\n\n")
    rh = Counter()
    for cid, r in all_rows:
        for h in r.get("rule_hits", []):
            rh[h["klass"]] += 1
    canon = ("8080-gap", "cadence", "lea-mod3", "open_bus")
    for klass in canon:
        c = rh.get(klass, 0)
        L.append(f"- {klass}: {c}{'  <-- STALE (zero hits)' if c == 0 else ''}\n")
    for klass, c in rh.items():
        if klass not in canon:
            L.append(f"- {klass}: {c}\n")

    # 2b. raw open-bus escape budget: how much of the raw-whole population
    # far-jumps out of the 64K image into open-bus feedthrough space.
    raw = [r for cid, r in all_rows if r["tier"] == "raw" and r.get("ob_escape")]
    if raw:
        escaped = [r for r in raw if r["ob_escape"]["feed"] >= 8]
        fracs = sorted(r["ob_escape"]["frac"] for r in raw)
        med = fracs[len(fracs) // 2]
        L.append("\n## Raw open-bus escape budget\n\n"
                 f"- raw seeds with capture: {len(raw)}; escaped (>=8 feedthrough "
                 f"fetches): {len(escaped)} ({100 * len(escaped) / len(raw):.0f}%); "
                 f"median out-of-image feed-fraction: {med:.2f}\n")

    # 3. signatures
    sigs = Counter(r["sig"] for cid, r in all_rows if r.get("sig"))
    new = [s for s in sigs if s not in known]
    L.append(f"\n## Signatures\n\n- distinct: {len(sigs)}; "
             f"in-ledger: {len(sigs) - len(new)}; **NEW (not in ledger): "
             f"{len(new)}**\n")

    # 4. drift / accepted-outlier tripwire
    acc_tim = [r for cid, r in all_rows if r["verdict"] == "KNOWN_ACCEPTED"
               and r.get("drift")]
    if acc_tim:
        omax = sorted(abs((r["drift"] or {}).get("final", 0)) for r in acc_tim)
        p90 = omax[int(0.9 * len(omax)) - 1] if omax else 0
        outliers = [r for r in acc_tim
                    if abs((r["drift"] or {}).get("final", 0)) >= p90]
        L.append(f"\n## Drift (accepted-TIMING outlier tripwire)\n\n"
                 f"- accepted waited seeds with drift: {len(acc_tim)}; "
                 f"|final_off| p90 = {p90}; top-decile outliers: "
                 f"{len(outliers)} (review for floor over-acceptance)\n")

    # 5. quarantine enumeration
    quar = [(cid, r) for cid, r in all_rows if r["verdict"] == "QUARANTINE"]
    L.append(f"\n## QUARANTINE ({len(quar)})\n\n")
    for cid, r in quar[:50]:
        L.append(f"- {cid}/{r['k']}: {r['sub'][:60]}\n")

    # 6. coverage
    L.append("\n## Coverage\n\n")
    for cid in cids:
        cp = CAMPAIGNS / cid / "coverage.json"
        if cp.exists():
            c = fuzz_cov.Coverage.load(cp)
            L.append(f"- {cid}: {c.seeds} seeds, {c.instrs} instrs, "
                     f"{len(c.form)} forms, {len(c.opsig)} opsigs, "
                     f"{len(c.prefix)} prefix-combos, {len(c.qfill)} qfill-buckets\n")

    # 7. escalation-relevant
    esc = [(cid, r) for cid, r in all_rows
           if (r["verdict"] == "FUNCTIONAL" and _waits_class(r) == "w0"
               and not r.get("rule_hits")) or r.get("alarms")]
    L.append(f"\n## Escalation-relevant seeds ({len(esc)})\n\n")
    for cid, r in esc[:30]:
        why = "provenance" if r.get("alarms") else "w0-functional"
        L.append(f"- {cid}/{r['k']} [{why}]: {r['verdict']}/{r['sub'][:40]}\n")

    return "".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cids", nargs="*", help="campaign ids (default: all)")
    ap.add_argument("--out", default=None, help="markdown path (default stdout)")
    a = ap.parse_args()
    cids = a.cids or sorted(p.name for p in CAMPAIGNS.iterdir()
                            if (p / "results.jsonl").exists())
    md = report(cids)
    if a.out:
        Path(a.out).write_text(md)
        print(f"wrote {a.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
