#!/usr/bin/env python3
"""sm3_sigctl -- the INDEPENDENT control for the sig_ledger admission (SM3 item 0).

`check_fuzz_bank --strict` FAILS on `new-sig TIMING 166`.  SM2 reported that all
166 arise from the 760 INV-1 re-captured seeds.  This tool RE-DERIVES that
attribution from the artifact rather than trusting the report: it replays every
banked seed exactly as `check_fuzz_bank` does (same `replay_classify`, same TB,
same accept engine) and records, PER SEED, the verdict, the signature, whether
the signature is already in the novelty ledger, and whether the seed carries a
`recapture` block with `evt.hold_bits == 12` and `evt.hold == 300`.

It is a MEASUREMENT, not a gate.  The gate stays `check_fuzz_bank`.

  sm3_sigctl.py --jobs 8 --out ~/.cache/ucsimt-tmp/sm3/sigctl.json

REPRODUCIBILITY (SM3 sitting 5, Codex concern #6).  "New" is relative to a
novelty ledger, and this tool used to read whatever `tests/v30/fuzz_bank/
sig_ledger.json` said TODAY.  Once the 140 signatures were ADMITTED to that
file the recorded 166/140 could no longer be reproduced by the tool that
produced it -- a control that cannot be re-run is not a control.  `--ledger`
names the ledger explicitly, so the admission run is reproducible from git:

  git show 369e4953ce:tests/v30/fuzz_bank/sig_ledger.json > /tmp/pre.json
  sm3_sigctl.py --ledger /tmp/pre.json --out ...      # -> 166 seeds / 140 sigs
"""
import argparse
import gzip
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import check_fuzz_bank as cfb                            # noqa: E402
import bank_status as bs                                 # noqa: E402
import fuzz_classify as fc                               # noqa: E402
from fuzz_accept import AcceptEngine                     # noqa: E402

_ENGINE = None


def _init():
    global _ENGINE
    _ENGINE = AcceptEngine.load()


def _one(p):
    p = Path(p)
    entry = json.loads(gzip.decompress(p.read_bytes()))
    e = entry.get("evt") or {}
    rec = {
        "path": str(p.relative_to(cfb.BANK)),
        "seed": entry["seed"],
        "campaign": p.parts[-3],
        "banked": entry.get("replay_verdict", entry["verdict"]),
        "recaptured": bool(entry.get("recapture")),
        "evt_hold": e.get("hold"),
        "evt_hold_bits": e.get("hold_bits"),
        "evt_hold_applied": e.get("hold_applied"),
    }
    try:
        sha, verdict, sig, sub = cfb.replay_classify(entry, _ENGINE)
    except Exception as ex:                              # noqa: BLE001
        rec.update(error=repr(ex))
        return rec
    rec.update(sha_ok=(sha == entry["image_sha256"]), verdict=verdict,
               sig=sig, sub=sub)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--out", required=True)
    ap.add_argument("--ledger", default="",
                    help="novelty ledger to score 'new' against (default: the "
                         "live tests/v30/fuzz_bank/sig_ledger.json).  Name a "
                         "pre-admission copy retrieved from git to REPRODUCE "
                         "an admission run after its signatures were admitted.")
    # This tool MIRRORS `check_fuzz_bank`'s population deliberately -- it exists
    # to explain that gate's `new-sig TIMING` line seed for seed -- so it must
    # honour the same SUPERSEDED status, or the two would disagree by 3,242
    # seeds and the explanation would be of a different population than the
    # gate's.  `--include-superseded` reproduces a pre-SUP-1 admission run.
    ap.add_argument("--include-superseded", action="store_true",
                    help="also score banks marked SUPERSEDED in their manifest "
                         "(docs/notes/invalidation_ledger.md § SUP-1)")
    a = ap.parse_args()

    ledger = Path(a.ledger) if a.ledger else cfb.LEDGER
    known = set(json.loads(ledger.read_text()).get("sigs", {})) \
        if ledger.exists() else set()
    seeds, _dropped = bs.seed_paths(include_superseded=a.include_superseded)
    note = bs.dropped_note(_dropped)
    if note:
        print(f"sm3_sigctl: {note}", flush=True)
    print(f"sm3_sigctl: {len(seeds)} banked seeds, {len(known)} known signatures"
          f" from {ledger}, jobs={a.jobs}", flush=True)

    with Pool(a.jobs, initializer=_init) as pool:
        recs = pool.map(_one, [str(p) for p in seeds], chunksize=4)

    newsig = [r for r in recs
              if r.get("verdict") == fc.TIMING and r.get("sig")
              and r["sig"] not in known]
    for r in newsig:
        r["new_sig"] = True

    by_recap = Counter(r["recaptured"] for r in newsig)
    print(f"\nnew-sig TIMING seeds: {len(newsig)}"
          f"   distinct signatures: {len({r['sig'] for r in newsig})}")
    print(f"  on RE-CAPTURED seeds : {by_recap[True]}")
    print(f"  on any OTHER seed    : {by_recap[False]}")
    bad = [r for r in newsig
           if not (r["recaptured"] and r.get("evt_hold") == 300
                   and r.get("evt_hold_bits") == 12)]
    print(f"  failing the control (not a true-300/12-bit re-capture): {len(bad)}")
    for r in bad[:20]:
        print("   ", r["path"], r.get("evt_hold"), r.get("evt_hold_bits"),
              r["recaptured"])
    print("\nerrors:", sum(1 for r in recs if "error" in r),
          " gen-drift:", sum(1 for r in recs if r.get("sha_ok") is False))

    Path(a.out).write_text(json.dumps(
        {"n_seeds": len(recs), "ledger": str(ledger), "n_known_sigs": len(known),
         "new_sig_seeds": len(newsig),
         "new_sig_distinct": sorted({r["sig"] for r in newsig}),
         "recs": recs}, indent=1))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
