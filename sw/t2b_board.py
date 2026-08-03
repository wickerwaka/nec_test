#!/usr/bin/env python3
"""t2b_board -- the T2b board probes (ucsim-t stage T2b, ucsim_t_provenance 12).

The campaign's first board contact.  Five directed probes, all SOCKET ONLY
(use_core=False), no flashing, raw 64-bit capture words retained with a sha256
beside every derived record, board_idle() at the end of every session.

Probes (specs + PRE-REGISTERED expected values: ucsim_t_provenance.md 12.0):

  p1   the SUSP-lead discriminator -- ENTER nest=2, both contexts, per-clock
       rows, 5 repetitions, 4 MHz and 8 MHz.  (Also carries P3's HALT tail.)
  p3   the HALT bus pseudo-cycle -- the same ENTER stimulus at w0/w1/w3.
  p2   the wvec corpus, frozen against SILICON (22 seeds x 4 wait vectors).
  p4   F3AA cases 16 and 10 at w1/w3 -- does the closing pop ride the eval?
  p5   the Arm-C sled at N=8/12 -- C3's cidle pin, frozen with a sha.

Usage:
    python3 sw/t2b_board.py p1 [--out DIR]
    python3 sw/t2b_board.py p2 [--reps 2]
    python3 sw/t2b_board.py p4
    python3 sw/t2b_board.py idle
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage                                        # noqa: E402
import char_enter as ce                                 # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
from v30run import run_image, DIV_OF_RECORD             # noqa: E402

HOST = "root@mister-nec"
OUT = ROOT / "sw" / "testdata" / "t2b"
DIVS = [8, 4]              # 8 -> 4 MHz, 4 -> 8 MHz (the blackbox controls)
REPS = 5


# --------------------------------------------------------------------------- #
# capture primitive: raw words retained, run_chip's own row semantics applied
# --------------------------------------------------------------------------- #
def capture(image, waits=0, div=DIV_OF_RECORD, wvec=None, wrand=None,
            tag="t2b"):
    """One socket capture.  Returns (rows, raw_hex_lines, sha256).

    rows use check_seq.run_chip's semantics exactly (reset-trimmed, TI/T4
    bs_early replaced by the end-of-cycle sample) so every existing derived
    record in the repo is comparable; the RAW 64-bit words are returned
    untouched and hashed, per the blackbox retention rule.

    21.1: `div` DEFAULTS to the divider of record and is always sent.  The
    dual-frequency promotion path passes it explicitly; nothing inherits the
    board's sticky value by omission any more."""
    recs, words = run_image(bytes(image), HOST, tag=tag, waits=waits,
                            use_core=False, div=div, wvec=wvec, wrand=wrand,
                            want_raw=True)
    raw = [f"{w:016x}" for w in words]
    sha = hashlib.sha256(("\n".join(raw) + "\n").encode()).hexdigest()
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    rows = recs[rel:]
    for r in rows:
        if r["t"] in (0, 5):
            r["bs_early"] = r["bs_late"]
    return rows, raw, sha


def stable_key(rows):
    """The electrically meaningful projection the blackbox protocol hashes for
    repeatability: control/status on every row, the T1 address, and T3/Tw data.
    Floating AD samples in TI/T2/T4 are retained raw but excluded.

    TWO further fields are excluded, MEASURED not assumed (T2b, 12.1): `rd_n`
    and the raw `bs_late`.  Both are WITHIN-CYCLE pulses sampled at a fixed
    edge, so the clock divider moves the sampling phase relative to them and
    they differ between the 4 MHz and 8 MHz controls on the very same program
    (249 of 4,063 rows, ONLY in those two fields).  `rd_n` was checked to carry
    no independent information at all: at div=8 it is an exact function of
    (t_state, bs) over the whole trace (0 ambiguous cells) and at div=4 exactly
    one cell (T3/PASV, the read data phase) is ambiguous -- i.e. it is the
    sampling edge racing the strobe, not a chip behaviour.  `bs_late` is already
    folded into `bs_early` on TI/T4 rows by run_chip's own like-sampling rule."""
    out = []
    for r in rows:
        t = r["t"]
        a = r["ad_addr"] if t == 1 else -1
        d = r["ad_data"] if t in (3, 4) else -1
        out.append((t, r["bs_early"], r["qs"], r["ube_n"], r["lock_n"], a, d))
    return hashlib.sha256(repr(out).encode()).hexdigest()


def reps_capture(image, waits=0, wvec=None, wrand=None, tag="t2b",
                 reps=REPS, divs=DIVS):
    """The protocol capture: `reps` repetitions at each clock divider.  Returns
    a record with the per-(div,rep) stability hash, the raw shas, and ONE
    decoded row stream (the first 4 MHz repetition) for analysis."""
    rec = {"waits": waits, "reps": reps, "divs": divs, "captures": {}}
    rows0 = raw0 = None
    for div in divs:
        keys, shas = [], []
        for i in range(reps):
            rows, raw, sha = capture(image, waits=waits, div=div, wvec=wvec,
                                     wrand=wrand, tag=tag)
            keys.append(stable_key(rows))
            shas.append(sha)
            if rows0 is None:
                rows0, raw0 = rows, raw
        rec["captures"][str(div)] = {
            "stable_key": keys[0],
            "stable_identical": len(set(keys)) == 1,
            "raw_sha": shas,
        }
    rec["freq_identical"] = len({v["stable_key"]
                                 for v in rec["captures"].values()}) == 1
    return rec, rows0, raw0


# --------------------------------------------------------------------------- #
# P1 / P3 -- the ENTER stimulus
# --------------------------------------------------------------------------- #
def enter_image(ctx_i, nest):
    ctx = ce.CONTEXTS[ctx_i]
    instr = ce.enter_case_instr(ctx["BP"], ctx["fsize"], nest)
    image, meta = testimage.compose(regs={"BP": ctx["BP"], "SP": ctx["SP"]},
                                    instr=instr)
    return image, meta["anchor_linear"] & 0xFFFF


def cmd_p1(args):
    d = OUT / "p1-susp"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {"probe": "P1 SUSP-lead discriminator + P3 HALT",
                "spec": "docs/notes/ucsim_t_provenance.md 12.0 P1/P3",
                "use_core": False, "host": HOST, "cells": {}}
    for ctx_i in (1, 0):                       # two preparation histories
        for waits in args.waits:
            key = f"ctx{ctx_i}_nest2_w{waits}"
            image, a16 = enter_image(ctx_i, 2)
            t0 = time.time()
            rec, rows, raw = reps_capture(image, waits=waits, tag="p1",
                                          reps=args.reps, divs=DIVS)
            rec["anchor16"] = a16
            rec["seconds"] = round(time.time() - t0, 1)
            manifest["cells"][key] = rec
            with gzip.open(d / f"{key}.rows.json.gz", "wt") as f:
                json.dump(rows, f, separators=(",", ":"))
            # blackbox retention rule: the COMPLETE raw 64-bit capture records
            # live beside the derived ones, not just their hash.
            with gzip.open(d / f"{key}.raw.hex.gz", "wt") as f:
                f.write("\n".join(raw) + "\n")
            print(f"  {key}: stable={all(v['stable_identical'] for v in rec['captures'].values())} "
                  f"freq_identical={rec['freq_identical']} rows={len(rows)} "
                  f"({rec['seconds']}s)", flush=True)
    (d / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {d}/manifest.json")


# --------------------------------------------------------------------------- #
# P2 -- the wvec corpus, against silicon
# --------------------------------------------------------------------------- #
def cmd_p2(args):
    from causal_wrand import accesses                    # noqa: E402
    from gen_seq import generate                         # noqa: E402
    import timed_wvec_gate as G                          # noqa: E402

    SEEDS = list(range(90000, 90020)) + [90270, 90364]
    WVECS = [(0, 0), (5, 1), (7, 3), (11, 7)]
    DIRECTED = {90270, 90364}
    NROWS = 4200
    d = OUT / "p2-wvec"
    d.mkdir(parents=True, exist_ok=True)

    out = {"probe": "P2 wvec corpus frozen against SILICON",
           "spec": "docs/notes/ucsim_t_provenance.md 12.0 P2",
           "use_core": False, "host": HOST, "seeds": SEEDS, "wvecs": WVECS,
           "nrows": NROWS,
           "digest": "bs,tw,addr,npops,gap-from-previous-T1 (freeze normalisation, verbatim)",
           "cases": {}}
    t0 = time.time()
    for seed in SEEDS:
        image, _ = check_seq.compose(generate(f"fz{seed}", exts=()))
        for ws, wmax in WVECS:
            wv = G.wv_of(ws, wmax)
            key = f"fz{seed}:ws{ws}:wmax{wmax}"
            # promotion cells (the directed seeds at ws5:wmax1) get the full
            # protocol: 5 reps x both frequencies.  Everything else gets the
            # corpus minimum plus a repeatability control.
            promote = seed in DIRECTED and (ws, wmax) == (5, 1)
            reps = REPS if promote else args.reps
            divs = DIVS if promote else [8]
            shas, keys, digs = [], [], []
            rows0 = None
            for div in divs:
                for _ in range(reps):
                    rows, raw, sha = capture(image, wvec=wv, div=div, tag="p2")
                    rows = rows[:NROWS]
                    shas.append(sha)
                    keys.append(stable_key(rows))
                    acc = accesses(rows)
                    digs.append(hashlib.sha256(
                        ";".join(G.parts_of(acc)).encode()).hexdigest()[:16])
                    if rows0 is None:
                        rows0 = rows
                        n_acc = len(acc)
            out["cases"][key] = {
                "rows": len(rows0), "accesses": n_acc, "sha": digs[0],
                "repeatable": len(set(digs)) == 1,
                "pin_identical": len(set(keys)) == 1,
                "reps": reps, "divs": divs, "raw_sha": shas,
                "promoted": promote,
            }
        print(f"  fz{seed} done ({time.time()-t0:.0f}s)", flush=True)
    (d / "wvec_chip_baseline.json").write_text(json.dumps(out, indent=1))
    # the collapse test, per config
    from collections import defaultdict
    g = defaultdict(set)
    for k, v in out["cases"].items():
        g[k.split(":", 1)[1]].add(v["sha"])
    print("\n  distinct digests per config (22 programs each):")
    for cfg, s in g.items():
        print(f"    {cfg}: {len(s)}")
    print(f"wrote {d}/wvec_chip_baseline.json")


# --------------------------------------------------------------------------- #
# P4 -- F3AA cases 16 / 10 at w1 and w3
# --------------------------------------------------------------------------- #
def cmd_p4(args):
    import emit_suite as es                              # noqa: E402
    d = OUT / "p4-f3aa"
    d.mkdir(parents=True, exist_ok=True)
    assert es.EMIT_USE_CORE is False
    out = {"probe": "P4 F3AA cx>=2 closing pop under waits",
           "spec": "docs/notes/ucsim_t_provenance.md 12.0 P4",
           "use_core": False, "seed_base": "v30-v0.1", "cases": {}}
    for waits in (0, 1, 3):
        for idx in (16, 10):
            t = es._emit_one_index(es.OPCODES["F3AA"], False, "F3AA", idx,
                                   HOST, "v30-v0.1", -1, waits)
            out["cases"][f"F3AA:{idx}:w{waits}"] = t
            print(f"  F3AA idx {idx} w{waits}: {len(t.get('cycles', []))} rows",
                  flush=True)
    blob = json.dumps(out, separators=(",", ":"))
    (d / "f3aa_pair.json").write_text(blob)
    (d / "f3aa_pair.sha256").write_text(
        hashlib.sha256(blob.encode()).hexdigest() + "\n")
    print(f"wrote {d}/f3aa_pair.json")


def cmd_idle(args):
    import b1_recapture
    b1_recapture.board_idle()
    print("board idle; use_core=0")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("p1"); p.add_argument("--reps", type=int, default=REPS)
    p.add_argument("--waits", type=int, nargs="+", default=[0, 1, 3])
    p.set_defaults(fn=cmd_p1)
    p = sub.add_parser("p2"); p.add_argument("--reps", type=int, default=2)
    p.set_defaults(fn=cmd_p2)
    p = sub.add_parser("p4"); p.set_defaults(fn=cmd_p4)
    p = sub.add_parser("idle"); p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
