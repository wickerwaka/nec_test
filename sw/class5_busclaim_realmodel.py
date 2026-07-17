#!/usr/bin/env python3
"""ARC 2 STEP 2 PRE-SHADOW: bus-claim re-key benefit under the REAL RTL model.

The Step-1 audit (class5_busclaim_audit.py) measured the re-key benefit against a
PROXY model:  model_go = !eu_req  (ignoring the rest of prefetch_ok). But the real
RTL grant is

    prefetch_ok = !(eu_req || eu_hold) && occupied <= pf_lim && q_aged == 0

i.e. the model ALREADY pauses when occ>pf_lim(=4) or q_aged!=0. Those two gates are
NOT in the proxy, so the proxy over-counts "model grants" (and therefore the table's
flip-correct advantage) on every occ>4 / q_aged!=0 row.

This script re-runs the *->CODE prefetch-grant counterfactual with the REAL RTL grant
semantics for the model, and measures the two implementable readiness-claim rules the
Step-2 spec derives, so the census target is sized against the GENUINE attributable
benefit, not the proxy headline. Freshness rule: thresholds re-derived from CURRENT
composition, never carried forward.

  MODEL  (real RTL): !(eu_req) && occ<=4 && q_aged==0   (eu_hold assumed 0: absent
                     from the dump, and 0 on these *->CODE resume rows)
  Rule A (REPLACE) : claim = !eu_ready && eu_req_p1 && cnt_next>=2  (drops eu_req;
                     the spec's stated readiness key; relies on want_eu priority in
                     the eu_req && eu_ready cell)
  Rule B (SURGICAL): claim = eu_req && (eu_ready || (eu_req_p1 && cnt_next>=2))
                     (keeps eu_req; only re-decides the contested eu_req==1 &&
                     eu_ready==0 reservation cell - the 446-slot w0 region)
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
DUMP = SW / "class5_alltrans.jsonl.gz"
DISC = set(range(90000, 90008))
HELD = set(range(91000, 91006))


def qb(v):
    return 0 if v <= 1 else (2 if v <= 4 else 5)


def key(r):
    return (r["eu_ready"], r["eu_req_p1"], qb(r["q_cnt"]), qb(r["occ"]),
            qb(r["cnt_next"]))


def model_grant(r):
    # the REAL prefetch_ok (eu_hold assumed 0)
    return 1 if (r["eu_req"] == 0 and r["occ"] <= 4 and r["q_aged"] == 0) else 0


def a_grant(r):
    claim = (r["eu_ready"] == 0 and r["eu_req_p1"] == 1 and r["cnt_next"] >= 2)
    return 1 if (not claim and r["occ"] <= 4 and r["q_aged"] == 0) else 0


def b_grant(r):
    claim = (r["eu_req"] == 1 and
             (r["eu_ready"] == 1 or (r["eu_req_p1"] == 1 and r["cnt_next"] >= 2)))
    return 1 if (not claim and r["occ"] <= 4 and r["q_aged"] == 0) else 0


def main():
    rows = [json.loads(l) for l in gzip.open(DUMP, "rt")]
    for r in rows:
        r["chip_go"] = 1 if r["label"] == "go" else 0
        r["proxy_go"] = 0 if r["eu_req"] == 1 else 1

    # rebuild the proxy H-ARB table (as in the Step-1 audit) to trace its flip-correct
    disc = [r for r in rows if r["seed"] in DISC]
    tab = defaultdict(lambda: [0, 0])
    for r in disc:
        tab[key(r)][r["chip_go"]] += 1
    table = {k: (1 if v[1] >= v[0] else 0) for k, v in tab.items()}

    def tpred(r):
        return table.get(key(r), r["proxy_go"])

    held = [r for r in rows if r["seed"] in HELD and r["bs_succ"] == "CODE"]
    n = len(held)
    print(f"=== *->CODE prefetch-grant, HELD (seeds 91000-05), n={n} ===\n")

    def report(nm, gf):
        acc = sum(1 for r in held if gf(r) == r["chip_go"])
        fc = sum(1 for r in held if gf(r) != model_grant(r)
                 and gf(r) == r["chip_go"] and model_grant(r) != r["chip_go"])
        fi = sum(1 for r in held if gf(r) != model_grant(r)
                 and model_grant(r) == r["chip_go"] and gf(r) != r["chip_go"])
        print(f"  {nm:16s} acc {acc}/{n} = {100*acc/n:5.2f}%   "
              f"flip-correct {fc:3d}  flip-incorrect {fi:2d} "
              f"({100*fi/n:.3f}%)")

    report("MODEL (real RTL)", model_grant)
    report("Rule A REPLACE", a_grant)
    report("Rule B SURGICAL", b_grant)

    # THE PROXY GAP: how much of the audit's 287 flip-correct is already handled
    # by the RTL's existing occ<=pf_lim / q_aged gates?
    fc287 = [r for r in held if tpred(r) == r["chip_go"]
             and r["proxy_go"] != r["chip_go"]]
    already = sum(1 for r in fc287 if model_grant(r) == r["chip_go"])
    via_occ = sum(1 for r in fc287 if model_grant(r) == r["chip_go"] and r["occ"] > 4)
    via_qaged = sum(1 for r in fc287 if model_grant(r) == r["chip_go"]
                    and r["q_aged"] != 0)
    print(f"\n=== PROXY-GAP DECOMPOSITION of the audit's 287 flip-correct ===")
    print(f"  proxy-model (!eu_req) flip-correct              : {len(fc287)}")
    print(f"  ALREADY correct under the real RTL occ/q_aged gates: {already} "
          f"(via occ>4 {via_occ}, via q_aged!=0 {via_qaged})")
    print(f"  GENUINELY new (real RTL model also wrong)         : "
          f"{len(fc287) - already}")
    print(f"  -> the +5.76pt / 287-row headline is {100*already/len(fc287):.0f}% "
          f"a proxy artifact of the omitted occ<=pf_lim / q_aged gates.")


if __name__ == "__main__":
    main()
