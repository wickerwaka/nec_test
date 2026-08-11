#!/usr/bin/env python3
"""cfb_rederive - ERR-1: re-derive the banked `replay_verdict` column on the
MAPPED classifier, in place, printing every movement.

WHY THIS TOOL EXISTS.  `fuzz_bank._write_bank` computes the banked
`replay_verdict` / `replay_sig` / `replay_sub` by calling
`check_fuzz_bank.replay_classify` itself, and until `09ec85e4bb` that call site
handed `fc.Ctx` a tier literal outside its declared domain, so every tier branch
in the classifier was dead.  The banked column IS that defect's output.  With
the call site fixed, the banker's stored value and the checker's computed value
disagree on 90 of 621 seeds and `check_fuzz_bank` is honestly RED.

WHAT IT DOES.  Re-runs `replay_classify` -- the SAME function the gate runs, so
the two cannot drift -- and writes back exactly FOUR things
(`docs/notes/cfb_rederive_prereg_2026-08-11.md` §1):

    1  entry["replay_verdict"]        2  entry["replay_sig"]
    3  entry["replay_sub"]            4  the REPLAY contribution to
                                         tests/v30/fuzz_bank/sig_ledger.json

plus a `rederive` provenance block naming what each entry replaced (the INV-1
closure mechanics: the movement stays derivable from the artifact itself, not
only from a document).

WHAT IT REFUSES TO DO.  Every other key of every entry is UNTOUCHABLE and the
refusal is mechanical, not editorial: the tool hashes the canonical JSON of all
non-mutable keys before and after and ABORTS on a single mismatch.  `chip_rows`
are true silicon.  No image is regenerated into the bank, no capture is
re-taken, no manifest, sig index, result shard or `bank_status` predicate is
touched, and no seed enters or leaves the replayed population.

A GEN-DRIFT or a replay error is a STOP, not a repair: this tool re-derives a
column, it does not fix data.

DEFAULT IS DRY-RUN.  `--apply` writes.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import bank_status as bs                                 # noqa: E402
import fuzz_classify as fc                               # noqa: E402
from fuzz_accept import AcceptEngine                     # noqa: E402
from check_fuzz_bank import replay_classify, ASSERT_PARK  # noqa: E402,F401

BANK = SW.parent / "tests" / "v30" / "fuzz_bank"
LEDGER = BANK / "sig_ledger.json"
ARCHIVE = SW / "testdata" / "cfb-tier-archive"
PREREG = "docs/notes/cfb_rederive_prereg_2026-08-11.md"
FIX_COMMIT = "09ec85e4bb"

# The ONLY keys this tool may write.  Everything else in a banked entry is
# untouchable and §1.3's hash proves it entry by entry.
MUTABLE = ("replay_verdict", "replay_sig", "replay_sub", "rederive")


def untouchable_sha(entry):
    """sha256 over the canonical JSON of every key EXCEPT the mutable four.
    Sorted keys, so it is invariant to insertion order and comparable across
    the rewrite."""
    rest = {k: v for k, v in entry.items() if k not in MUTABLE}
    blob = json.dumps(rest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the re-derived column (default: dry run)")
    ap.add_argument("--limit", type=int, default=0,
                    help="dry-run only: stop after N seeds (never with --apply)")
    ap.add_argument("--record", type=Path,
                    help="write the full run record as JSON")
    a = ap.parse_args()
    if a.limit and a.apply:
        sys.exit("--limit is a dry-run instrument; a partial rewrite is a "
                 "truncated bank and is refused")
    if a.apply and not (ARCHIVE / "SHA256SUMS").exists():
        sys.exit(f"REFUSED: no archive at {ARCHIVE} -- archive before touch "
                 f"({PREREG} §3)")

    engine = AcceptEngine.load()
    seeds, dropped = bs.seed_paths()
    note = bs.dropped_note(dropped)
    if note:
        print(f"cfb_rederive: {note}", flush=True)
    if not seeds:
        sys.exit("cfb_rederive: no banked seeds -- nothing to re-derive")
    print(f"cfb_rederive: {'APPLY' if a.apply else 'DRY RUN'} over "
          f"{len(seeds)} banked seeds", flush=True)

    rows = []
    ledger_delta = Counter()
    n_ver = n_sub = n_sig = 0
    for p in sorted(seeds):
        entry = json.loads(gzip.decompress(p.read_bytes()))
        before = untouchable_sha(entry)
        old_v = entry.get("replay_verdict")
        old_s = entry.get("replay_sig")
        old_b = entry.get("replay_sub")
        sha, verdict, sig, sub = replay_classify(entry, engine)
        # A GEN-DRIFT here is a STOP.  This tool re-derives a DERIVED column;
        # it has no business writing one against an image that no longer
        # regenerates to the sha256 the capture was taken with.
        if sha != entry["image_sha256"]:
            sys.exit(f"STOP: GEN-DRIFT {entry['seed']}: {sha[:12]} != banked "
                     f"{entry['image_sha256'][:12]} -- nothing written")
        moved = []
        if verdict != old_v:
            moved.append("VERDICT")
            n_ver += 1
        if sub != old_b:
            moved.append("sub")
            n_sub += 1
        if sig != old_s:
            moved.append("sig")
            n_sig += 1
        # PRINTED, NEVER SILENT: one line per entry, moved or not.
        print(f"  {'MOVE ' if moved else 'same '}{entry['seed']:>14} "
              f"{entry['tier']:<4} {old_v}/{old_b} -> {verdict}/{sub} "
              f"| sig {str(old_s)[:12]} -> {str(sig)[:12]}"
              f"{' [' + ','.join(moved) + ']' if moved else ''}")
        # field #4: the entry's contribution to the ledger, as `_write_bank`
        # computed it -- `for _s in {discovery_sig, replay_sig}`, a SET, so an
        # entry whose replay sig equals its discovery sig contributed once.
        d = entry.get("sig")
        old_set = {x for x in (d, old_s) if x}
        new_set = {x for x in (d, sig) if x}
        for s in old_set - new_set:
            ledger_delta[s] -= 1
        for s in new_set - old_set:
            ledger_delta[s] += 1

        entry["replay_verdict"] = verdict
        entry["replay_sig"] = sig
        entry["replay_sub"] = sub
        entry["rederive"] = {
            "err": "ERR-1", "prereg": PREREG, "fix_commit": FIX_COMMIT,
            "prior_replay_verdict": old_v, "prior_replay_sig": old_s,
            "prior_replay_sub": old_b, "prior_banked_ts": entry.get("banked_ts"),
            "archive": "sw/testdata/cfb-tier-archive",
            "rederived_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        after = untouchable_sha(entry)
        if after != before:
            sys.exit(f"STOP: {entry['seed']} untouchable fields moved "
                     f"({before[:12]} -> {after[:12]}) -- nothing written")
        rows.append({"seed": entry["seed"], "tier": entry["tier"],
                     "before": [old_v, old_b, old_s],
                     "after": [verdict, sub, sig], "untouchable": before})
        if a.apply:
            p.write_bytes(gzip.compress(json.dumps(entry).encode()))
        if a.limit and len(rows) >= a.limit:
            break

    # ---- field #4: the ledger -------------------------------------------
    led = json.loads(LEDGER.read_text())
    sigs = led["sigs"]
    added, removed, negative = [], [], []
    for s, d in sorted(ledger_delta.items()):
        if d == 0:
            continue
        if s not in sigs:
            if d < 0:
                negative.append((s, "absent", d))
                continue
            sigs[s] = {"first_campaign": "ERR-1-rederive",
                       "first_verdict": None, "klass": None, "tier": None,
                       "waits_class": None, "count": 0}
            added.append(s)
        sigs[s]["count"] += d
        if sigs[s]["count"] < 0:
            negative.append((s, "negative", sigs[s]["count"]))
        elif sigs[s]["count"] == 0:
            removed.append(s)
            del sigs[s]
    for s in added:
        print(f"  LEDGER + {s} (+{ledger_delta[s]})")
    for s in removed:
        print(f"  LEDGER - {s} (count reached 0)")
    if negative:
        for s, why, n in negative:
            print(f"  LEDGER !! {s}: {why} ({n})")
        sys.exit(f"STOP: {len(negative)} ledger count(s) went negative -- the "
                 f"ledger was not written by the arithmetic {PREREG} §P-6 "
                 f"registered.  Seed files "
                 f"{'WERE' if a.apply else 'were NOT'} written.")

    print(f"\ncfb_rederive: {len(rows)} entries | verdict moved {n_ver} | "
          f"sub moved {n_sub} | sig moved {n_sig} | untouchable identical "
          f"{len(rows)}/{len(rows)} | ledger +{len(added)} -{len(removed)} "
          f"(sigs {len(sigs) + len(removed) - len(added)} -> {len(sigs)}) | "
          f"{'WRITTEN' if a.apply else 'DRY RUN, nothing written'}")
    if a.apply:
        LEDGER.write_text(json.dumps(led, indent=1))
    if a.record:
        a.record.write_text(json.dumps(
            {"applied": a.apply, "n": len(rows), "verdict_moved": n_ver,
             "sub_moved": n_sub, "sig_moved": n_sig,
             "ledger_added": added, "ledger_removed": removed,
             "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
