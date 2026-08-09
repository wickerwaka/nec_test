#!/usr/bin/env python3
"""inv1_recapture -- close INV-1 by RE-CAPTURING the 760 poisoned EVT seeds.

WHAT IS BROKEN AND WHAT THIS FIXES
----------------------------------
`docs/notes/invalidation_ledger.md` INV-1 / F46: 760 banked fuzz seeds carry
`evt.hold = 300` and the rig's `evt_hold` register was EIGHT bits, so the socket
was held `300 & 0xFF = 44` clocks.  The captures are TRUE SILICON; the LABEL is
false, and therefore so is the directive an engine is handed when it replays
them.  The register is 12 bits since 2026-08-04 and this tool takes the capture
that the widen makes possible.

THE MECHANISM, AND WHY IT IS AN IN-PLACE UPDATE
-----------------------------------------------
INV-1's exclusion is DERIVED, not listed (`timed_fuzz.f46_invalidated`): a seed
is out iff its banked `hold` disagrees with what the rig that took it could
hold.  Its own stated closure is *"a re-capture on the widened rig banks
`hold_bits = 12`, and the seed leaves this set by arithmetic"* -- i.e. the
entries are UPDATED IN PLACE and no list is edited and no file is renamed.

NOTHING IS DELETED.  `archive` first copies all 760 entries byte-identical to
`sw/testdata/inv1-archive/`, with a sha256 manifest.  That path is OUTSIDE
`tests/v30/fuzz_bank/` on purpose: `check_fuzz_bank` globs `*/seeds/*.json.gz`
under that root, so an archive placed inside it would silently grow the
3,242-seed corpus -- the second falsehood INV-1 refused to introduce to record
the first.

SUBCOMMANDS
-----------
  archive   copy the 760 originals + SHA256SUMS.  Board-free.  Idempotent.
  probe     THE WIRE PROOF, and it gates everything else: write a hold > 255
            through `v30ctl.set_event`, read `EVT_CFG` back, confirm the split
            packing [23:16]+[30:27] round-trips, and take one directed capture
            demonstrating a hold of 300 clocks actually held.
  capture   the socket leg (use_core=False) for the 760.  Per seed: regenerate
            the image from (cid, k, ov), HASH-CHECK it against the banked
            `image_sha256` (GEN-DRIFT is a hard skip, never a silent capture),
            run the chip at the banked directive, retain the FULL per-clock rows
            plus a sha256.
  rebank    rewrite the 760 entries in place from the raw captures, banking
            `evt.hold_bits = 12` / `evt.hold_applied = 300` and a `recapture`
            provenance block that names the bitstream, the flash and the sha256
            of the rows it replaces.  Recomputes `replay_verdict` and REPORTS
            the before/after matrix -- recomputing it silently would make
            `check_fuzz_bank` vacuous on these seeds.
  verify    the §59.2 integrity bars, as arithmetic over the artifact.

Board discipline (CLAUDE.md): single-writer checked by the caller, socket only,
the divider PINNED by `check_seq.run_chip`'s `div=DIV_OF_RECORD` on every
capture, `div_guard` readback recorded, and a run of consecutive transport
errors STOPs rather than grinding on.
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
ROOT = SW.parent
sys.path.insert(0, str(SW))

import bank_status as bs                                  # noqa: E402
import check_seq                                          # noqa: E402
import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import timed_fuzz as tf                                   # noqa: E402
import v30ctl                                             # noqa: E402
import v30run                                             # noqa: E402
import testimage                                          # noqa: E402

HOST = "root@mister-nec"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"
ARCHIVE = ROOT / "sw" / "testdata" / "inv1-archive"
RAW = ROOT / "sw" / "testdata" / "inv1-recapture"
STORM = 15                       # consecutive transport errors -> STOP


def sha(b):
    return hashlib.sha256(b).hexdigest()


def poisoned():
    """The population, DERIVED -- never a list.  Same predicate the gate uses.

    SPANS SUPERSEDED BANKS ON PURPOSE.  INV-1's 760 seeds live entirely in
    `mc1`/`mc2`, which SUP-1 retired from the replayed population on 2026-08-09
    (`docs/notes/invalidation_ledger.md`).  Retirement is not deletion and the
    two predicates are independent: `f46_invalidated` is a statement about a rig
    defect, `status` a statement about which corpus the project develops
    against.  Filtering by status here would silently empty INV-1's own closure
    tooling, so the inclusion is explicit."""
    out = []
    for p in sorted(bs.seed_paths(include_superseded=True)[0]):
        e = json.loads(gzip.decompress(p.read_bytes()))
        if tf.f46_invalidated(e):
            out.append((p, e))
    return out


# --------------------------------------------------------------------------- #
def cmd_archive(a):
    seeds = poisoned()
    print(f"archive: {len(seeds)} INVALIDATED entries")
    lines = []
    for p, _e in seeds:
        rel = p.relative_to(BANK)
        dst = ARCHIVE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        blob = p.read_bytes()
        if not dst.exists() or dst.read_bytes() != blob:
            dst.write_bytes(blob)
        lines.append(f"{sha(blob)}  {rel}")
    (ARCHIVE / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    man = {
        "what": "INV-1 -- the 760 EVT seeds captured under an 8-bit evt_hold",
        "why": "docs/notes/invalidation_ledger.md INV-1 / F46",
        "note": "byte-identical copies of the banked entries as they stood "
                "BEFORE the SM2 re-capture.  chip_rows here are TRUE silicon "
                "for a 44-clock hold.  NOTHING GATES ON THEM.",
        "archived_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(lines),
        "sha256sums_sha256": sha((ARCHIVE / "SHA256SUMS").read_bytes()),
    }
    (ARCHIVE / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"  -> {ARCHIVE}  ({len(lines)} files)")
    print(f"  SHA256SUMS sha256 {man['sha256sums_sha256']}")
    return 0


# --------------------------------------------------------------------------- #
def _image_of(entry):
    """Regenerate + HASH-CHECK.  Raises on GEN-DRIFT: a generator change that
    silently moved the seed must never be captured over."""
    cfg = fzc.derive_case(entry["cid"], entry["k"], entry.get("ov") or {})
    g = fzc.build(cfg)
    image, meta = check_seq.compose(g)
    got = sha(bytes(image))
    if got != entry["image_sha256"]:
        raise RuntimeError(f"GEN-DRIFT {got[:16]} != {entry['image_sha256'][:16]}")
    return image, meta, cfg


def _legs(entry, meta):
    w = entry.get("waits") or {}
    wrand = (w.get("wmax"), w.get("wseed")) if w.get("wrand") else None
    fixed = 0 if w.get("wrand") else (w.get("fixed") or 0)
    e = entry["evt"]
    evt = (meta["anchor_linear"] & 0xFFFFF, int(e["delay"]), int(e["hold"]),
           int(e["pin"]))
    return fixed, wrand, evt


def div_guard(tag):
    """s13_board.div_guard's contract, inlined so this tool has no dependency
    on a probe module: PIN the divider and ask the TRANSPORT what it commanded.
    An UNPINNED readback is a rig-integrity FINDING and is recorded, not
    smoothed."""
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if ("UNPINNED" not in str(rb)
                         and "UNKNOWN" not in str(rb)) else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    return {"readback": str(rb), "state": state}


# --------------------------------------------------------------------------- #
def cmd_probe(a):
    """THE WIRE PROOF (§59.2 item 3).  If this does not round-trip, NOTHING is
    re-captured."""
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": a.host, "rig_evt_hold_bits": v30ctl.RIG_EVT_HOLD_BITS}
    ok = True

    # -- 1. the PACKING, host-side and arithmetic-only ---------------------- #
    # set_event's own packing, reproduced here so the readback has something
    # INDEPENDENT to be compared against.
    def pack(delay, hold, pin, arm=True):
        v = ((delay & 0xFFFF) | ((hold & 0xFF) << 16) | ((pin & 7) << 24)
             | (((hold >> 8) & 0xF) << 27))
        return v | (1 << 31) if arm else v

    def unpack(v):
        return {"delay": v & 0xFFFF,
                "hold": ((v >> 16) & 0xFF) | (((v >> 27) & 0xF) << 8),
                "pin": (v >> 24) & 7, "arm": bool(v >> 31 & 1)}

    round_trip = [(d, h, p) for d in (0, 7, 0xFFFF) for h in (0, 2, 44, 255,
                                                              256, 300, 4095)
                  for p in (0, 1, 2)]
    bad = [(d, h, p) for d, h, p in round_trip
           if unpack(pack(d, h, p)) != {"delay": d, "hold": h, "pin": p,
                                        "arm": True}]
    out["packing_selftest"] = {"cases": len(round_trip), "bad": len(bad)}
    print(f"  packing self-test: {len(round_trip)} cases, {len(bad)} bad")
    if bad:
        ok = False

    # -- 2. the REGISTER, on the wire -------------------------------------- #
    # `v30ctl.Harness` opens /dev/mem, so it exists only ON the board; the
    # readback therefore runs THERE, through the board's own copy -- which is
    # the point (§59.0): it proves the host the captures will actually use.
    return _probe_wire(a, out, ok, pack, unpack)


def _probe_wire(a, out, ok, pack, unpack):
    """The EVT_CFG readback + the directed 300-clock capture.

    The register lives on the BOARD, so this runs `v30ctl.py` THERE over ssh --
    the same copy `serve` uses, which is exactly the point: it proves the host
    the captures will actually go through, not a local reimplementation."""
    import subprocess
    script = r"""
import sys
sys.path.insert(0, "/media/fat/v30")
import v30ctl, json
h = v30ctl.Harness()
res = {"RIG_EVT_HOLD_BITS": v30ctl.RIG_EVT_HOLD_BITS, "rt": []}
for (d, hold, pin) in [(0,2,0),(0,44,0),(0,255,0),(0,256,0),(0,300,0),
                       (0,4095,0),(7,300,1),(65535,300,2)]:
    h.set_event(addr=0x00400, delay=d, hold=hold, pin=pin, arm=True)
    v = h.read32(v30ctl.R_EVT_CFG)
    res["rt"].append({"delay": d, "hold": hold, "pin": pin, "raw": v})
h.set_event(arm=False)
try:
    h.write32(v30ctl.R_PINS, 0)
except Exception:
    pass
print("JSON:" + json.dumps(res))
"""
    p = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                        a.host, "cd /media/fat/v30 && python3 -"],
                       input=script.encode(), capture_output=True, timeout=120)
    txt = p.stdout.decode()
    line = next((l for l in txt.splitlines() if l.startswith("JSON:")), None)
    if line is None:
        print("  ERR: no JSON from the board")
        print(txt[-2000:])
        print(p.stderr.decode()[-2000:])
        return 2
    res = json.loads(line[5:])
    out["board"] = res
    print(f"  board RIG_EVT_HOLD_BITS = {res['RIG_EVT_HOLD_BITS']}")
    if res["RIG_EVT_HOLD_BITS"] != 12:
        print("  *** the BOARD's v30ctl.py is not the 12-bit one ***")
        ok = False
    for r in res["rt"]:
        got = unpack(r["raw"])
        exp = {"delay": r["delay"], "hold": r["hold"], "pin": r["pin"],
               "arm": True}
        good = got == exp
        ok = ok and good
        print(f"    delay={r['delay']:<6} hold={r['hold']:<5} pin={r['pin']}  "
              f"raw=0x{r['raw']:08X} -> {got}  {'OK' if good else 'MISMATCH'}")
    out["readback_ok"] = ok
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "probe.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"PROBE: {'PASS' if ok else 'FAIL'}  -> {RAW/'probe.json'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
def cmd_holdproof(a):
    """THE DIRECTED DEMONSTRATION that a hold > 255 clocks is actually HELD.

    The readback (§59.2 item 3, `probe`) proves the REGISTER carries 300.  It
    does not prove the SCHEDULER counts to 300, and INV-1's falsifier is
    written on the PIN, not on the register.  So: one seed, one image, three
    directives that differ ONLY in `hold` -- 44 (what the 8-bit rig actually
    applied), 300 (what the bank asked for), and 2 (the un-poisoned control) --
    and the acknowledge pattern is counted in each.

    F46's own mechanism (`ucore_gaps_2026-08-04.md` §T.5) says what to expect
    and is therefore what this can falsify: with INT level-asserted for 300
    clocks instead of 44 the part re-enters the handler where it entered once.
    MORE INTA cycles at 300 than at 44 is the demonstration; the SAME count is
    a refutation of the fix and stops the session."""
    seeds = poisoned()
    p, entry = seeds[0]
    image, meta, cfg = _image_of(entry)
    fixed, wrand, evt = _legs(entry, meta)
    out = {"seed": entry["seed"], "cid": entry["cid"], "k": entry["k"],
           "banked_evt": entry["evt"], "waits": entry.get("waits"),
           "image_sha256": entry["image_sha256"],
           "old_capture_inta_t1": sum(1 for r in entry["chip_rows"]
                                      if r.get("t") == 1
                                      and r.get("bs_early") == 0),
           "legs": []}
    for hold in (2, 44, 255, 300, 600):
        e = (evt[0], evt[1], hold, evt[3])
        recs, fired = v30run.run_image(bytes(image), a.host, tag="inv1hp",
                                       use_core=False, waits=fixed, evt=e,
                                       wrand=wrand, want_fired=True,
                                       div=v30run.DIV_OF_RECORD)
        rel = next(j for j, r in enumerate(recs) if not r["rst"])
        recs = recs[rel:]
        inta = [j for j, r in enumerate(recs)
                if r.get("t") == 1 and r.get("bs_early") == 0]
        out["legs"].append({"hold": hold, "fired": bool(fired),
                            "n_rows": len(recs), "inta_t1": len(inta),
                            "inta_at": inta[:24],
                            "rows_sha256": sha(json.dumps(recs).encode())})
        print(f"  hold={hold:<5} fired={bool(fired)!s:<5} rows={len(recs):<5} "
              f"INTA T1 = {len(inta):<3} at {inta[:12]}", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "holdproof.json").write_text(json.dumps(out, indent=1) + "\n")
    by = {L["hold"]: L["inta_t1"] for L in out["legs"]}
    ok = by.get(300, 0) > by.get(44, 0)
    print(f"HOLDPROOF: hold=44 -> {by.get(44)} INTA T1, hold=300 -> "
          f"{by.get(300)}  ==> {'a hold > 255 DEMONSTRABLY HELD' if ok else 'NO DIFFERENCE -- the widen is NOT on the wire'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
def cmd_capture(a):
    seeds = poisoned()
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "raw").mkdir(exist_ok=True)
    print(f"capture: {len(seeds)} seeds, socket leg (use_core=False)",
          flush=True)
    done = skip = err = drift = 0
    consec = 0
    t0 = time.time()
    guard = None
    for i, (p, entry) in enumerate(seeds):
        name = f"{entry['cid']}_{entry['tier']}_{entry['k']}_{entry['cfg_hash']}"
        fn = RAW / "raw" / f"{name}.json.gz"
        if fn.exists() and not a.force:
            skip += 1
            continue
        try:
            image, meta, cfg = _image_of(entry)
        except Exception as ex:                            # noqa: BLE001
            drift += 1
            print(f"  GEN-DRIFT {name}: {ex}", flush=True)
            continue
        fixed, wrand, evt = _legs(entry, meta)
        try:
            recs, fired = v30run.run_image(
                bytes(image), a.host, tag="inv1", use_core=False, waits=fixed,
                evt=evt, wrand=wrand, want_fired=True,
                div=v30run.DIV_OF_RECORD)
            rel = next(j for j, r in enumerate(recs) if not r["rst"])
            recs = recs[rel:]
            consec = 0
        except Exception as ex:                            # noqa: BLE001
            err += 1
            consec += 1
            print(f"  ERR {name}: {str(ex)[:140]}", flush=True)
            if consec >= STORM:
                print(f"=== INV1_WEDGE_STOP consec={consec} at {name} ===",
                      flush=True)
                return 2
            continue
        if guard is None:
            guard = div_guard("first capture")
            (RAW / "div_guard.json").write_text(json.dumps(guard, indent=1))
        body = json.dumps({
            "name": name, "cid": entry["cid"], "k": entry["k"],
            "tier": entry["tier"], "cfg_hash": entry["cfg_hash"],
            "seed": entry["seed"], "bank_path": str(p.relative_to(BANK)),
            "image_sha256": entry["image_sha256"],
            "evt": {"delay": evt[1], "hold": evt[2], "pin": evt[3],
                    "hold_bits": v30ctl.RIG_EVT_HOLD_BITS,
                    "hold_applied": evt[2] & ((1 << v30ctl.RIG_EVT_HOLD_BITS) - 1)},
            "waits": entry.get("waits"), "evt_fired": bool(fired),
            "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rows": recs,
        }).encode()
        fn.write_bytes(gzip.compress(body))
        (RAW / "raw" / f"{name}.sha256").write_text(sha(body) + "\n")
        done += 1
        if done % 25 == 0:
            print(f"  ... {done}/{len(seeds)} ({time.time()-t0:.0f}s, "
                  f"{err} err, {drift} drift)", flush=True)
    print(f"CAPTURE: {done} new, {skip} already present, {err} errors, "
          f"{drift} gen-drift, {time.time()-t0:.0f}s")
    return 0 if (err == 0 and drift == 0) else 1


# --------------------------------------------------------------------------- #
def cmd_rebank(a):
    from fuzz_accept import AcceptEngine
    from check_fuzz_bank import replay_classify
    engine = AcceptEngine.load()
    seeds = poisoned()
    prov = json.loads((RAW / "provenance.json").read_bytes()) \
        if (RAW / "provenance.json").exists() else {}
    n = miss = 0
    matrix = Counter()
    log = []
    for p, entry in seeds:
        name = f"{entry['cid']}_{entry['tier']}_{entry['k']}_{entry['cfg_hash']}"
        fn = RAW / "raw" / f"{name}.json.gz"
        if not fn.exists():
            miss += 1
            continue
        cap = json.loads(gzip.decompress(fn.read_bytes()))
        old_rows = entry["chip_rows"]
        old_sha = sha(json.dumps(old_rows).encode())
        old_replay = entry.get("replay_verdict")
        win = entry.get("first_bad")
        entry["chip_rows"] = cap["rows"]
        entry["chip_arch"] = fc.arch_dump(cap["rows"],
                                          min(len(cap["rows"]), 4000))
        entry["evt"]["hold_bits"] = v30ctl.RIG_EVT_HOLD_BITS
        entry["evt"]["hold_applied"] = cap["evt"]["hold_applied"]
        entry["recapture"] = {
            "why": "INV-1 / F46 -- the 8-bit evt_hold truncated this seed's "
                   "300-clock directive to 44.  docs/notes/"
                   "invalidation_ledger.md",
            "session": "SM2", "captured_utc": cap["captured_utc"],
            "evt_fired": cap["evt_fired"],
            "prior_chip_rows_sha256": old_sha,
            "prior_n_rows": len(old_rows),
            "prior_banked_ts": entry.get("banked_ts"),
            "prior_replay_verdict": old_replay,
            "archive": "sw/testdata/inv1-archive/" + str(p.relative_to(BANK)),
            **prov,
        }
        entry["banked_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _sha, rv, rsig, rsub = replay_classify(entry, engine)
        entry["replay_verdict"], entry["replay_sig"], entry["replay_sub"] = \
            rv, rsig, rsub
        matrix[(old_replay, rv)] += 1
        log.append({"name": name, "old_replay": old_replay, "new_replay": rv,
                    "old_rows": len(old_rows), "new_rows": len(cap["rows"]),
                    "prior_chip_rows_sha256": old_sha,
                    "evt_fired": cap["evt_fired"], "win": win})
        if not a.dry_run:
            p.write_bytes(gzip.compress(json.dumps(entry).encode()))
        n += 1
    print(f"REBANK: {n} entries {'(DRY RUN)' if a.dry_run else 'rewritten'}, "
          f"{miss} without a capture")
    print("  replay-verdict matrix (banked -> re-captured):")
    for (o, v), c in sorted(matrix.items(), key=lambda x: -x[1]):
        print(f"    {o!s:>16} -> {v!s:<16} {c}")
    (RAW / "rebank_log.json").write_text(json.dumps(
        {"matrix": {f"{o}->{v}": c for (o, v), c in matrix.items()},
         "n": n, "missing": miss, "entries": log}, indent=1) + "\n")
    return 0 if miss == 0 else 1


# --------------------------------------------------------------------------- #
def cmd_verify(a):
    """The §59.2 integrity bars, as arithmetic over the artifact.

    `include_superseded=True` for the same reason `poisoned()` does it: these
    bars are about INV-1's EVT population, all of which sits in banks SUP-1
    retired.  Status and invalidation are independent predicates."""
    n_inv = n_evt = n300 = ok300 = 0
    for p in sorted(bs.seed_paths(include_superseded=True)[0]):
        e = json.loads(gzip.decompress(p.read_bytes()))
        ev = e.get("evt")
        if not ev:
            continue
        n_evt += 1
        if tf.f46_invalidated(e):
            n_inv += 1
        if int(ev.get("hold", 0)) == 300:
            n300 += 1
            if (int(ev.get("hold_bits", 8)) == 12
                    and int(ev.get("hold_applied", -1)) == 300):
                ok300 += 1
    arch = ARCHIVE / "SHA256SUMS"
    n_arch = len(arch.read_text().splitlines()) if arch.exists() else 0
    print("=== INV-1 CLOSURE BARS (§59.2) ===")
    print(f"  bar 1  hold=300 entries with hold_bits=12 and hold_applied=300:"
          f" {ok300}/{n300}   {'MET' if ok300 == n300 and n300 else 'NOT MET'}")
    print(f"  bar 2  f46_invalidated True over the whole bank: {n_inv}"
          f"   {'MET' if n_inv == 0 else 'NOT MET'}")
    print(f"  bar 4  archived originals: {n_arch}"
          f"   {'MET' if n_arch == 760 else 'NOT MET'}")
    print(f"  (evt-armed banked seeds: {n_evt})")
    return 0 if (n_inv == 0 and ok300 == n300 and n_arch == 760) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("archive", cmd_archive), ("probe", cmd_probe),
                     ("holdproof", cmd_holdproof),
                     ("capture", cmd_capture), ("rebank", cmd_rebank),
                     ("verify", cmd_verify)):
        c = s.add_parser(name)
        c.add_argument("--host", default=HOST)
        if name == "capture":
            c.add_argument("--force", action="store_true")
        if name == "rebank":
            c.add_argument("--dry-run", action="store_true")
        c.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
