#!/usr/bin/env python3
"""u4_tranche - THE STANDING PRIORITY GATE (ucore_provenance.md §48.4).

The project's #1 ranking is arbitrary-wait accuracy, and this is the campaign's
victory condition: a FRESH stratified random-wait tranche, frozen before any
capture, run through

    the socketed chip          (use_core=0)   -- the reference
    the ucore in fabric        (use_core=1)   -- the thing under test
    the ucore under Verilator  (--leg vsim)   -- V3's fabric-vs-sim control

and scored with the SAME window + column policy the fuzz bank is scored with
(`ucsim_fuzz.window_of`, `fuzz_classify.diff_rows`, `timed_fuzz.excuse`), so
the number is comparable to the banked tranche's 89.4 % by construction.

    freeze   generate the seeds, build the images, write the manifest.
             BOARD-FREE.  Commit the manifest BEFORE capturing anything --
             that is the pre-registration, and it is what makes V1 falsifiable.
    capture  one board leg (--leg chip | core).  Retains FULL per-clock rows
             and a sha256 per capture, never digests alone.
    vsim     the Verilator ucore leg.  Board-free.
    score    V0-V5 against the registered bars.

Board discipline (CLAUDE.md): single-writer checked by the caller, the divider
is PINNED by `check_seq.run_chip`'s `div=DIV_OF_RECORD` on every capture, and a
run of consecutive transport errors STOPs rather than grinding on.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))

import fuzz_campaign as fzc          # noqa: E402
import check_seq                     # noqa: E402
import fuzz_classify as fc           # noqa: E402
import ucsim_fuzz as uf              # noqa: E402
import timed_fuzz as tf              # noqa: E402

HOST = "root@mister-nec"
OUT = ROOT / "sw/testdata/t4/b3-u4tranche"
STORM = 15                            # consecutive transport errors -> STOP

# The stratification.  §48.4 asks for ~200 stratified `wrand` seeds; the axis is
# the random-wait one, so the strata are the wmax levels the bank itself uses
# and the tranche carries NO evt directive (a corrected hold moves nothing here).
STRATA = [1, 2, 3, 7, 15]
PER_STRATUM = 40


def sha(b):
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------- #
def cmd_freeze(a):
    OUT.mkdir(parents=True, exist_ok=True)
    man = {"probe": "B3 -- U4 pass 2 fresh random-wait tranche",
           "spec": "docs/notes/ucore_provenance.md §48.4",
           "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cid": a.cid, "k_base": a.k_base, "strata": STRATA,
           "per_stratum": PER_STRATUM, "cells": {}}
    k = a.k_base
    for wmax in STRATA:
        got = 0
        while got < PER_STRATUM:
            if k > a.k_base + 20000:
                raise SystemExit(f"ran out of seeds for wmax={wmax}")
            name = f"{a.cid}_{k}"
            try:
                cfg = fzc.derive_case(a.cid, k, {"force_contained": True,
                                                 "strict": True,
                                                 "no_evt": True,
                                                 "force_wrand": [wmax]})
                g = fzc.build(cfg)
                image, meta = check_seq.compose(g)
            except Exception:                                  # noqa: BLE001
                k += 1
                continue
            w = cfg["waits"]
            if not w.get("wrand") or w.get("wmax") != wmax:
                k += 1
                continue
            man["cells"][name] = {
                "cid": a.cid, "k": k, "wmax": wmax, "wseed": w["wseed"],
                "image_sha256": sha(bytes(image)),
                "n_rows_budget": a.rows,
            }
            got += 1
            k += 1
    body = json.dumps(man, indent=1, sort_keys=True).encode()
    (OUT / "manifest.json").write_bytes(body)
    (OUT / "manifest.sha256").write_text(sha(body) + "\n")
    print(f"FROZEN {len(man['cells'])} seeds -> {OUT/'manifest.json'}")
    print(f"manifest sha256 {sha(body)}")
    return 0


# --------------------------------------------------------------------------- #
def _image_of(cell):
    cfg = fzc.derive_case(cell["cid"], cell["k"],
                          {"force_contained": True, "strict": True,
                           "no_evt": True, "force_wrand": [cell["wmax"]]})
    g = fzc.build(cfg)
    image, meta = check_seq.compose(g)
    got = sha(bytes(image))
    if got != cell["image_sha256"]:
        raise RuntimeError(f"image drift {got[:16]} != "
                           f"{cell['image_sha256'][:16]}")
    return image, cfg


def cmd_capture(a):
    man = json.loads((OUT / "manifest.json").read_bytes())
    leg = OUT / f"raw_{a.leg}"
    leg.mkdir(parents=True, exist_ok=True)
    # SM2 / X3: the `_f4` legs are the SAME two positions re-captured on
    # FLASH #4, written beside the pass-3 ones rather than over them (§55.2
    # item 6 declared the carried-forward substitution; removing it must not
    # also destroy the thing it is being compared against).  The A/B POSITION
    # is read from the leg's prefix, so a new leg name cannot silently change
    # which side of the harness is captured.
    use_core = not a.leg.startswith("chip")
    consec = done = err = 0
    t0 = time.time()
    for name, cell in sorted(man["cells"].items()):
        fn = leg / f"{name}.json.gz"
        if fn.exists() and not a.force:
            done += 1
            continue
        image, cfg = _image_of(cell)
        w = cfg["waits"]
        try:
            recs = check_seq.run_chip(image, a.host, use_core=use_core,
                                      wrand=(w["wmax"], w["wseed"]))
            consec = 0
        except Exception as e:                                 # noqa: BLE001
            err += 1
            consec += 1
            print(f"  ERR {name}: {str(e)[:120]}", flush=True)
            if consec >= STORM:
                print(f"=== TRANCHE_WEDGE_STOP consec={consec} at {name} ===",
                      flush=True)
                return 2
            continue
        body = json.dumps({"name": name, "leg": a.leg, "cell": cell,
                           "rows": recs}).encode()
        fn.write_bytes(gzip.compress(body))
        done += 1
        if done % 25 == 0:
            print(f"  ... {done}/{len(man['cells'])} "
                  f"({time.time()-t0:.0f}s, {err} err)", flush=True)
    print(f"CAPTURE {a.leg}: {done} cells, {err} errors, "
          f"{time.time()-t0:.0f}s")
    return 0


# --------------------------------------------------------------------------- #
def cmd_vsim(a):
    import tempfile
    man = json.loads((OUT / "manifest.json").read_bytes())
    chip = OUT / "raw_chip"
    leg = OUT / f"raw_vsim_{a.core}"
    leg.mkdir(parents=True, exist_ok=True)
    done = 0
    for name, cell in sorted(man["cells"].items()):
        cf = chip / f"{name}.json.gz"
        if not cf.exists():
            continue
        recs = json.loads(gzip.decompress(cf.read_bytes()))["rows"]
        image, cfg = _image_of(cell)
        # timed_fuzz.run_tb, NOT check_seq.run_tb: the latter is pinned to the
        # FSM `obj_dir` binary, and V3 is a control on the UCORE.
        entry = {"waits": cfg["waits"]}
        with tempfile.TemporaryDirectory() as td:
            rows, err = tf.run_tb(image, entry, len(recs), td, a.core)
        if not rows:
            print(f"  ERR {name}: {err.strip()[:120]}", flush=True)
            continue
        body = json.dumps({"name": name, "leg": "vsim", "cell": cell,
                           "rows": rows}).encode()
        (leg / f"{name}.json.gz").write_bytes(gzip.compress(body))
        done += 1
        if done % 25 == 0:
            print(f"  ... {done}", flush=True)
    print(f"VSIM: {done} cells")
    return 0


# --------------------------------------------------------------------------- #
def _load(leg, name):
    fn = OUT / f"raw_{leg}" / f"{name}.json.gz"
    if not fn.exists():
        return None
    return json.loads(gzip.decompress(fn.read_bytes()))["rows"]


def cmd_score(a):
    man = json.loads((OUT / "manifest.json").read_bytes())
    legs = a.legs.split(",")
    res = {L: {"exact": 0, "scored": 0, "excused": 0, "fam": {}, "miss": []}
           for L in legs}
    for name, cell in sorted(man["cells"].items()):
        chip = _load(a.ref, name)
        if chip is None:
            continue
        win = uf.window_of(chip)
        # the SAME excuse policy the bank is scored with, applied to the
        # CAPTURE, so every leg gets the identical denominator
        ex = tf.excuse({"evt": None, "waits": {"wrand": True}}, chip, win,
                       False)
        for L in legs:
            rows = _load(L, name)
            r = res[L]
            if rows is None:
                continue
            if ex:
                r["excused"] += 1
                continue
            r["scored"] += 1
            dr = fc.diff_rows(chip, rows)
            if not dr.rows:
                r["exact"] += 1
            else:
                k = tf.first_kind(dr.rows[0])
                r["fam"][k] = r["fam"].get(k, 0) + 1
                r["miss"].append((name, k, dr.rows[0].i, len(dr.rows), dr.n))
    print(f"=== B3 tranche, {len(man['cells'])} frozen seeds "
          f"(manifest {man['frozen_utc']})")
    for L in legs:
        r = res[L]
        pct = 100.0 * r["exact"] / r["scored"] if r["scored"] else 0.0
        print(f"  {L:<6} cycle-exact {r['exact']}/{r['scored']} ({pct:.1f} %)"
              f"   excused {r['excused']}")
        if r["fam"]:
            print("         residue: " +
                  "  ".join(f"{k}={v}" for k, v in sorted(r["fam"].items())))
    if a.verbose:
        for L in legs:
            for m in res[L]["miss"]:
                print(f"  {L} {m[0]} first={m[1]} row={m[2]} "
                      f"ndiff={m[3]}/{m[4]}")
    (OUT / a.out).write_text(json.dumps(
        {L: {k: v for k, v in res[L].items() if k != "miss"} for L in legs},
        indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--cid", default="mc1")
    f.add_argument("--k-base", type=int, default=300000)
    f.add_argument("--rows", type=int, default=4000)
    f.set_defaults(fn=cmd_freeze)
    c = sub.add_parser("capture")
    c.add_argument("--leg", required=True,
                   choices=["chip", "core", "fsmcore",
                            "chip_f4", "core_f4",
                            # SM3 sitting 7 / FLASH #5: the same two positions
                            # again, beside the `_f4` pair rather than over it.
                            # A leg is scored against the SOCKET capture taken
                            # on its OWN bitstream and never another flash's.
                            "chip_f5", "core_f5"])
    c.add_argument("--host", default=HOST)
    c.add_argument("--force", action="store_true")
    c.set_defaults(fn=cmd_capture)
    v = sub.add_parser("vsim")
    v.add_argument("--core", default="ucore", choices=["ucore", "fsm"])
    v.set_defaults(fn=cmd_vsim)
    s = sub.add_parser("score")
    s.add_argument("--legs", default="core")
    s.add_argument("--ref", default="chip",
                   help="the leg every other leg is scored AGAINST -- the "
                        "socket capture.  SM2/X3 scores the FLASH #4 legs "
                        "against `chip_f4`, the socket capture taken on the "
                        "same bitstream, never against another flash's.")
    s.add_argument("--out", default="score.json")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
