#!/usr/bin/env python3
"""fz2_a10_replay - the PROOF that amendment A-10 changed the alarm, taken on
the real board capture that halted the A-9 validation.  Offline, no board.

`docs/notes/fz2_corpus_prereg_2026-08-08.md` §27 (A-10) extends D-2's sentinel
predicate -- *a done marker is an `OUT 0xFC` carrying `0xF00D`* -- to
`provenance_alarms`' Tier-A done-data clause, which §17.6 says A-6 deliberately
left alone.  A stop-condition change that cannot be SHOWN to still stop is not a
safe change, so this replays the banked rows of the seed that stopped the run
(`fz2v/604011`) through `fuzz_classify.classify` + `EscalationPolicy` TWICE:
once against the pre-amendment module (`git show b5f2b14f05:sw/fuzz_classify.py`)
as the CONTROL, once against the tree.

THE CONTROL IS THE WHOLE POINT.  It must reproduce the BANKED verdict and sub
exactly -- verdict, sub-reason, alarm list and the ('STOP', 'provenance_alarm')
escalation.  If it does not, the replay is not a replay and nothing it says
about the tree is evidence; this script exits non-zero on that and says so.

AND THE ALARM MUST STILL BE ABLE TO CATCH SOMETHING.  An alarm that can no
longer fire is a deletion wearing an extension's clothes, so leg 2 takes THE
SAME board rows and removes the harness's own sentinel marker from both legs --
the second pass's `OUT 0xFC, 0xF00D` at row 3406 -- leaving the shared
non-sentinel write in place.  That is a corrupt shared store built out of real
silicon rows, and the TREE must still QUARANTINE it and still STOP.  Leg 3 does
the one-sided form of the same construction, where the shared-vs-one-sided
discriminator (task #29 P7) and not the sentinel predicate is what must refuse.

Campaign captures are `.gitignore`d, so a reviewer without them will see the
glob come up empty -- that is a missing input, not a failure, and it is
reported as SKIP.  `sw/test_fuzz_classify.py` carries the same five assertions
on a board-free Verilator fixture and needs no capture at all.

    python3 sw/fz2_a10_replay.py [scratch-dir]
"""
import copy
import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
SW = ROOT / "sw"
sys.path.insert(0, str(SW))
import fuzz_campaign as fzc          # noqa: E402
import fz2_w1 as W                   # noqa: E402
import fz2_val as V                  # noqa: E402
import fuzz_classify as fc_new       # noqa: E402

CONTROL_REV = "b5f2b14f05"           # the commit the halt was scored under
CID = V.VAL_CID
K = 604011


def load_old(tmp, rev=CONTROL_REV):
    """The pre-amendment fuzz_classify, imported under its own name."""
    src = subprocess.run(["git", "-C", str(ROOT), "show",
                          f"{rev}:sw/fuzz_classify.py"],
                         capture_output=True, text=True, check=True).stdout
    p = Path(tmp) / "fuzz_classify.py"          # same basename: its own imports
    p.write_text(src)
    spec = importlib.util.spec_from_file_location("fc_old", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["fc_old"] = m
    spec.loader.exec_module(m)
    return m


def _ctx(mod, cfg, g):
    return mod.Ctx(
        tier="A" if cfg["tier"] == "soup" else "B",
        waits=0 if (cfg["waits"]["wrand"] or cfg.get("wvec"))
        else cfg["waits"]["fixed"],
        wrand=bool(cfg["waits"]["wrand"] or cfg.get("wvec")),
        real_is_chip=True, brkem_pos=g.get("brkem_pos", []),
        lea_mod3_pos=g.get("lea_mod3_pos", []),
        has_halt=g.get("has_halt", False),
        with_drift=(cfg["waits"]["wrand"] or cfg["waits"]["fixed"] > 0),
        cid=CID, seed=f"{CID}/{K}", cfg_hash=cfg["cfg_hash"])


def _done_txns(mod, recs):
    return [t for t in mod.extract_txns(recs)
            if mod.KIND[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == mod.OUT_PORT_DONE]


def _strip_sentinel(mod, recs):
    """Move every SENTINEL-carrying `OUT 0xFC` off the done port, leaving the
    non-sentinel writes exactly where they are.  Returns how many moved."""
    n = 0
    for t in _done_txns(mod, recs):
        if t["data"] != mod.DONE_SENTINEL:
            continue
        for j in range(t["start"], t["end"] + 1):
            r = recs[j]
            if mod._tstate(r) == 1:
                r["ad_addr"] = (r["ad_addr"] & 0xF0000) | 0x00AA
        n += 1
    return n


def _run(mod, tag, real, sim, ctx, banked=None):
    v = mod.classify(real, sim, ctx, engine=fzc._engine())
    acts = mod.EscalationPolicy().consult(v, ctx)
    stop = any(a == ("STOP", "provenance_alarm") for a in acts)
    print(f"    {tag:22s} -> {v.verdict}/{v.sub}")
    print(f"    {'':22s}    alarms={v.alarms}  win={v.n}  "
          f"bad_rows={v.bad_rows}  STOP={stop}")
    ok = True
    if banked is not None:
        ok = (v.verdict == banked["verdict"] and v.sub == banked["sub"]
              and list(v.alarms) == list(banked["alarms"]))
        print(f"    {'':22s}    CONTROL reproduces the banked line: "
              f"{'YES' if ok else 'NO'}")
    return v, stop, ok


def main():
    tmp = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
    cdir = fzc.CAMPAIGNS / CID
    caps = sorted((cdir / "captures").glob(f"*_{K}_*.json.gz"))
    if not caps:
        print(f"SKIP: no banked capture for {CID}/{K} "
              f"(campaign captures are gitignored) -- this is a missing "
              f"input, not a failure.  `sw/test_fuzz_classify.py` carries the "
              f"same assertions board-free.")
        return 0
    cap = caps[0]
    sha = subprocess.run(["sha256sum", str(cap)], capture_output=True,
                         text=True, check=True).stdout.split()[0]
    banked = next(json.loads(line) for line in open(cdir / "results.jsonl")
                  if json.loads(line)["k"] == K)
    d = json.load(gzip.open(cap))
    real, sim = d["real"], d["sim"]

    j = V._stratum_of(K)
    cfg = fzc.derive_case(CID, K, W.ov_of(V.STRATA[j]))
    g = fzc.build(cfg)

    fc_old = load_old(tmp)
    rc = 0

    print(f"=== {CID}/{K}  ({cap.name})")
    print(f"    sha256         : {sha}")
    print(f"    stratum        : {V.label(V.STRATA[j])}  cfg_hash="
          f"{cfg['cfg_hash']}  evt={cfg['evt']}")
    print(f"    rows           : real {len(real)}  sim {len(sim)}")
    print(f"    banked verdict : {banked['verdict']}/{banked['sub']}")
    print(f"    banked columns : arch_ok={banked['arch_ok']} "
          f"arch_match={banked['arch_match']} bad_rows={banked['bad_rows']} "
          f"win={banked['win']} mech={banked['mech']}")
    for tag, recs in (("real", real), ("sim", sim)):
        outs = [(t["start"], f"0x{t['data']:04x}")
                for t in _done_txns(fc_new, recs)]
        print(f"    OUT 0xFC ({tag:4s}): {outs}")

    # ---- LEG 1: the seed itself.  BEFORE must reproduce the halt; AFTER must
    # ---- score it, with the arch dumps compared.
    print("\n--- LEG 1: the halting seed, as captured")
    _, stop_o, ok = _run(fc_old, f"BEFORE ({CONTROL_REV})", real, sim,
                         _ctx(fc_old, cfg, g), banked)
    if not ok:
        rc = 1
    if not stop_o:
        print("    *** CONTROL did not STOP -- the replay is not a replay")
        rc = 1
    v_new, stop_n, _ = _run(fc_new, "AFTER  (tree)", real, sim,
                            _ctx(fc_new, cfg, g))
    if v_new.verdict == fc_new.QUARANTINE or stop_n:
        print("    *** AFTER still quarantines/stops -- A-10 did not land")
        rc = 1
    ar = fc_new.arch_dump(real, len(real), sentinel_only=True)
    as_ = fc_new.arch_dump(sim, len(sim), sentinel_only=True)
    print(f"    arch dumps compared: real={'ok' if ar else 'None'} "
          f"sim={'ok' if as_ else 'None'} equal={ar == as_}")
    if not (ar and as_ and ar == as_):
        print("    *** the seed does not score with both legs' arch compared")
        rc = 1
    print(f"    arch_ok(banked)={banked['arch_ok']} "
          f"arch_match(banked)={banked['arch_match']}  "
          f"replayed arch == banked arch_words: "
          f"{ar == {k: v for k, v in banked['arch_words'].items()}}")

    # ---- LEG 2: THE FALSIFIER.  Same silicon rows, the harness's sentinel
    # ---- marker removed from BOTH legs -> a shared corrupt store.  The tree
    # ---- must still QUARANTINE and still STOP.
    print("\n--- LEG 2: THE FALSIFIER -- the same rows with NO sentinel "
          "marker anywhere")
    r2, s2 = copy.deepcopy(real), copy.deepcopy(sim)
    n2 = _strip_sentinel(fc_new, r2) + _strip_sentinel(fc_new, s2)
    print(f"    sentinel markers moved off the done port: {n2}")
    for tag, recs in (("real", r2), ("sim", s2)):
        outs = [(t["start"], f"0x{t['data']:04x}")
                for t in _done_txns(fc_new, recs)]
        sen = fc_new.has_done(recs, len(recs), sentinel_only=True)[0]
        print(f"    OUT 0xFC ({tag:4s}): {outs}  sentinel_present={sen}")
    v2, stop2, _ = _run(fc_new, "AFTER  (tree)", r2, s2, _ctx(fc_new, cfg, g))
    catches = (v2.verdict == fc_new.QUARANTINE
               and any("done_data_both" in a for a in v2.alarms) and stop2)
    print(f"    the alarm STILL CATCHES a corrupt shared store: "
          f"{'YES' if catches else 'NO'}")
    if not catches:
        print("    *** A-10 is a DELETION, not an extension")
        rc = 1

    # ---- LEG 3: the one-sided form of leg 2 -- no sentinel on either leg, but
    # ---- only ONE leg writes the junk.  The shared-vs-one-sided discriminator
    # ---- (task #29 P7), not the sentinel predicate, must refuse this.
    print("\n--- LEG 3: one-sided, and no sentinel on either leg")
    r3, s3 = copy.deepcopy(r2), copy.deepcopy(s2)
    for t in _done_txns(fc_new, s3):
        for jj in range(t["start"], t["end"] + 1):
            if fc_new._tstate(s3[jj]) == 1:
                s3[jj]["ad_addr"] = (s3[jj]["ad_addr"] & 0xF0000) | 0x00AA
    print(f"    sentinel_present real={fc_new.has_done(r3, len(r3), True)[0]} "
          f"sim={fc_new.has_done(s3, len(s3), True)[0]}   "
          f"done-port writes real={len(_done_txns(fc_new, r3))} "
          f"sim={len(_done_txns(fc_new, s3))}")
    v3, _, _ = _run(fc_new, "AFTER  (tree)", r3, s3, _ctx(fc_new, cfg, g))
    if any("done_data" in a for a in v3.alarms):
        print("    *** a ONE-SIDED junk done raised a capture-integrity alarm")
        rc = 1
    else:
        print("    the discriminator still refuses a one-sided junk done: YES")

    print(f"\nFZ2_A10_REPLAY: {'PASS' if rc == 0 else 'FAIL'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
