#!/usr/bin/env python3
"""check_fuzz_bank - standing replay-regression gate over the fuzz bank
(task #29 Phase 6), the check_ff_t4 idiom for the fuzz corpus.

The bank stores the CHIP leg (captured once on silicon) + full provenance +
the chip-vs-TB REPLAY verdict computed at bank time. For every banked seed:
  1. REGENERATE the image from (cid, k, ov) - the image is NOT stored - and
     hash-check it against the banked image_sha256. A mismatch is GEN-DRIFT: a
     generator change silently moved the seed -> HARD FAIL.
  2. Replay in the Verilator TB with the banked cfg (fixed waits / wrand / evt);
     a TB assertion abort (e.g. the sim-only terminal-else whitelist catching a
     booked FE-group mod=11 in raw bytes) is a first-class outcome, not a crash.
  3. Re-classify the banked CHIP rows vs the TB replay and compare to the banked
     REPLAY verdict (chip-vs-TB is deterministic given the TB build, so a stable
     RTL round-trips exactly).

A WORSE verdict fails; an IMPROVED verdict is reported and queued for retire
(never auto-deleted); a banked SUCCESS that no longer classifies SUCCESS is the
fab-vs-TB float-floor alarm; a new-signature TIMING warns (fails under --strict).
The discovery verdict (chip-vs-fabric) is retained as provenance and the
discovery-vs-replay delta is reported (the plan's fab-vs-TB float census).
"""
import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
from fuzz_accept import AcceptEngine                    # noqa: E402
import fuzz_campaign as fzc                             # noqa: E402
import timed_fuzz as tf                                 # noqa: E402  (banked_wvec)
import bank_status as bs                                # noqa: E402

BANK = SW.parent / "tests" / "v30" / "fuzz_bank"
LEDGER = BANK / "sig_ledger.json"
ASSERT_PARK = "ASSERT_PARK"           # TB aborted (whitelist/other sim assert)
SEV = {fc.SUCCESS: 0, fc.KNOWN_ACCEPTED: 1, fc.TIMING: 2,
       fc.FUNCTIONAL: 3, ASSERT_PARK: 4, fc.QUARANTINE: 5}


def replay_classify(entry, engine):
    """Regenerate + replay a banked seed in the TB and classify chip-vs-TB.
    Returns (image_sha256, verdict, sig, sub). A TB abort -> ASSERT_PARK.

    THE IMAGE COMES FROM `fuzz_campaign.compose_case`, THE SINGLE BUILD PATH.
    It used to call `check_seq.compose` directly, which is only PART of the
    build: every image-level rule `compose_case` adds (the fuzz-v2 0F scrub
    among them) was missing here, so this gate regenerated a DIFFERENT image
    from the one the capture was taken with -- precisely the GEN-DRIFT the
    sha256 check exists to catch, reported as drift in the seed rather than as
    a defect in the gate.

    AND THE BANKED WAIT VECTOR IS REPLAYED.  `wvec` was silently dropped, so a
    per-access-wait seed was re-run at a FLAT wait profile and scored against a
    capture taken under a vector.  It reads green today only because no banked
    seed uses that axis; the v2 corpus is stratified on it."""
    cfg = fzc.derive_case(entry["cid"], entry["k"], entry.get("ov") or {})
    g = fzc.build(cfg)
    image, meta = fzc.compose_case(g, cfg)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    w = entry.get("waits") or {}
    wrand = (w.get("wmax"), w.get("wseed")) if w.get("wrand") else None
    fixed = 0 if w.get("wrand") else (w.get("fixed") or 0)
    wvec = tf.banked_wvec(entry)      # RAISES on a sha/length mismatch
    evt = None
    e = entry.get("evt")
    if e:
        evt = (meta["anchor_linear"] & 0xFFFFF, e["delay"], e["hold"], e["pin"])
    try:
        sim = check_seq.run_tb(image, 4200, waits=fixed, evt=evt, wrand=wrand,
                               wvec=wvec)
    except Exception:                                    # noqa: BLE001
        return sha, ASSERT_PARK, None, "tb_abort"
    chip = entry["chip_rows"]
    ctx = fc.Ctx(tier=entry["tier"], waits=fixed, wrand=bool(w.get("wrand")),
                 real_is_chip=True, brkem_pos=entry.get("brkem_pos", []),
                 lea_mod3_pos=entry.get("lea_mod3_pos", []),
                 has_halt=entry.get("has_halt", False), cid=entry["cid"],
                 seed=entry["seed"], cfg_hash=entry["cfg_hash"])
    v = fc.classify(chip, sim, ctx, engine=engine)
    return sha, v.verdict, v.sig, v.sub


def check(strict=False, include_superseded=False, include_excluded=False):
    # RESOLVE THE TB BINARY FIRST, AND EAGERLY.  `check_seq.tb_bin()` builds if
    # the content key moved and then asserts the artifact-layer postcondition
    # (sw/artifact.py) -- this gate is INCARNATION #3's home, the one that
    # scored 3,242 seeds against a binary `check_seq` never built.
    #
    # It is called HERE, before the loop, and not left to fire inside it: both
    # `replay_classify` and the loop below catch `Exception`, so a stale binary
    # would otherwise be swallowed 3,242 times as a per-seed `regen_err` /
    # `ASSERT_PARK`.  The gate would still FAIL -- but it would fail as 3,242
    # confusing seed errors instead of one sentence naming the stale file.
    print(f"check_fuzz_bank: TB leg {check_seq.tb_bin()}", flush=True)
    engine = AcceptEngine.load()
    known_sigs = set(json.loads(LEDGER.read_text()).get("sigs", {})) \
        if LEDGER.exists() else set()
    # THE REPLAYED POPULATION IS A PREDICATE OVER THE MANIFESTS, not this
    # module's glob.  A campaign retired with `status: SUPERSEDED` leaves the
    # gate -- it does not leave the tree, nothing is moved or deleted, and
    # `--include-superseded` replays it in full (`sw/bank_status.py`,
    # `docs/notes/invalidation_ledger.md` § SUP-1).  The exclusion is announced
    # on its own line, never silently.
    #
    # AND THE SAME, ONE LEVEL DOWN: an individual seed named in its bank's
    # `excluded_seeds` leaves the REPLAYED POPULATION while the campaign stays
    # ACTIVE (EXC-1, prereg §31 / A-12).  A banked capture of a DEFERRED
    # feature must not fail a landing on that feature's divergence, and it must
    # not do so SILENTLY either -- `dropped_note` names the class, the count and
    # the flag that brings it back, and the two classes are never merged into
    # one word.
    seeds, dropped = bs.seed_paths(include_superseded=include_superseded,
                                   include_excluded=include_excluded)
    note = bs.dropped_note(dropped)
    if note:
        print(f"check_fuzz_bank: {note}", flush=True)
    if not seeds:
        if dropped:
            # A GATE THAT REPLAYS NOTHING IS NOT A PASS.  If every bank in the
            # tree has been retired, this gate has gone vacuous and must say so
            # loudly rather than exit 0 on an empty population -- the exact
            # failure mode `standing_gates.md` was written against.
            print("check_fuzz_bank: FAIL | 0 seeds -- every bank is "
                  "SUPERSEDED or every seed EXCLUDED, and nothing is left to "
                  "replay.  A gate with an empty population is vacuous, not "
                  "green.")
            return 1
        print("check_fuzz_bank: no banked seeds")
        return 0
    gen_drift = worse = improved = float_alarm = new_sig_tim = stable = err = 0
    matrix = Counter()
    for p in seeds:
        entry = json.loads(gzip.decompress(p.read_bytes()))
        try:
            sha, verdict, sig, sub = replay_classify(entry, engine)
        except Exception as ex:                          # noqa: BLE001
            err += 1
            print(f"  REGEN/REPLAY ERROR {p.name}: {ex}")
            continue
        if sha != entry["image_sha256"]:
            gen_drift += 1
            print(f"  GEN-DRIFT {entry['seed']}: sha {sha[:12]} != banked "
                  f"{entry['image_sha256'][:12]}")
            continue
        banked = entry.get("replay_verdict", entry["verdict"])
        matrix[(banked, verdict)] += 1
        if verdict == banked:
            stable += 1
        elif SEV[verdict] > SEV[banked]:
            worse += 1
            print(f"  WORSE {entry['seed']}: banked-replay {banked} -> {verdict}/{sub}")
        else:
            improved += 1
            print(f"  IMPROVED {entry['seed']}: {banked} -> {verdict} "
                  f"(queue retire; not auto-deleted)")
        if entry.get("replay_verdict") == fc.SUCCESS and verdict != fc.SUCCESS:
            float_alarm += 1
        if verdict == fc.TIMING and sig and sig not in known_sigs:
            new_sig_tim += 1

    n = len(seeds)
    ok = gen_drift == 0 and worse == 0 and err == 0 and \
        (new_sig_tim == 0 or not strict)
    print(f"\ncheck_fuzz_bank: {'PASS' if ok else 'FAIL'} | {n} banked seeds | "
          f"stable {stable} improved {improved} worse {worse} | "
          f"gen_drift {gen_drift} regen_err {err} | float-floor {float_alarm} | "
          f"new-sig TIMING {new_sig_tim}{' (strict-fail)' if new_sig_tim and strict else ''}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--include-superseded", action="store_true",
                    help="also replay banks marked SUPERSEDED in their "
                         "manifest (retirement is not deletion -- this is how "
                         "a pre-v2 figure is re-derived)")
    ap.add_argument("--include-excluded", action="store_true",
                    help="also replay individual seeds named in a bank's "
                         "`excluded_seeds` (EXC-1: exclusion is not deletion "
                         "-- the captures are true silicon and are retained)")
    a = ap.parse_args()
    return check(a.strict, a.include_superseded, a.include_excluded)


if __name__ == "__main__":
    sys.exit(main())
