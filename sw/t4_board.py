#!/usr/bin/env python3
"""t4_board -- the T4 board probes (ucsim-t stage T4, ucsim_t_provenance 14).

SOCKET ONLY (`use_core=False`), no flashing, raw 64-bit capture words retained
with a sha256 beside every derived record, the FULL per-cycle stream retained
beside every digest (the P2 lesson, 13.4), `board_idle()` after every session.

Probes (specs + PRE-REGISTERED expected values: ucsim_t_provenance.md 14.0):

  freeze   write the victory tranche's (cid, k) list -- run and COMMIT before
           any capture, so the population cannot move afterwards.
  b1       the P2 wvec re-capture, with the per-access `parts` retained.
  b2       THE VICTORY TRANCHE -- 216 fresh seeds, 3 reps, 12 promoted cells.
  idle     board_idle().

Usage:
    python3 sw/t4_board.py freeze
    python3 sw/t4_board.py b1
    python3 sw/t4_board.py b2 [--limit N]
    python3 sw/t4_board.py idle
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

import check_seq                                        # noqa: E402
import fuzz_campaign as fzc                             # noqa: E402
from v30run import run_image                            # noqa: E402
from t2b_board import capture, stable_key, HOST, DIVS, REPS   # noqa: E402

OUT = ROOT / "sw" / "testdata" / "t4"

# --- the victory tranche's frozen population (14.0 B2) --------------------- #
CIDS = ["mc1", "mc2", "t30-raw"]
CLASSES = ["fix0", "fix1", "fix2", "fix3",
           "wrand1", "wrand2", "wrand3", "wrand7", "wrand15"]
PER_CELL = 8
K_BASE = 100000              # strictly outside every banked range
OV = {"no_evt": True}        # the scope exclusion, applied at GENERATION
TRANCHE_REPS = 3
PROMOTE_REPS = 5


def tranche_key(rows):
    """The repeatability projection for the TRANCHE, and it is deliberately the
    SAME projection the gate scores on, not the stricter T2b blackbox one.

    MEASURED before it was adopted (14.1): over four cells x three repetitions
    each, EVERY differing row is in indices 0-8 and NOT ONE row from 9 on
    differs.  Rows 0-8 are the capture's reset settling and are excluded by
    `fuzz_classify.diff_rows` -- the frozen T3 column policy this gate is
    scored with -- so a stability test that included them would exclude cells
    for disagreeing about something no gate ever compares.  The T2b
    `stable_key` is kept as the SECOND, stricter number and reported beside it.
    """
    out = []
    for r in rows[9:]:
        t = r["t"]
        a = r["ad_addr"] if t == 1 else -1
        d = r["ad_data"] if t in (2, 3) else -1
        out.append((t, r["bs_early"], r["qs"], r["ube_n"], r["lock_n"], a, d,
                    r["ps"] if t == 2 else -1))
    return hashlib.sha256(repr(out).encode()).hexdigest()


def wait_class(w):
    return f"wrand{w['wmax']}" if w["wrand"] else f"fix{w['fixed'] or 0}"


def tranche_population():
    """The frozen draw: for each (cid, class), scan k upward from K_BASE and
    take the first PER_CELL whose derived class matches.  Deterministic, and
    reproducible from these three lines alone."""
    out = []
    for cid in CIDS:
        got = {c: [] for c in CLASSES}
        k = K_BASE
        while any(len(v) < PER_CELL for v in got.values()):
            cfg = fzc.derive_case(cid, k, OV)
            c = wait_class(cfg["waits"])
            if c in got and len(got[c]) < PER_CELL:
                got[c].append(k)
            k += 1
            if k > K_BASE + 100000:
                raise RuntimeError("population scan did not converge")
        for c in CLASSES:
            for kk in got[c]:
                out.append({"cid": cid, "k": kk, "wc": c})
    return out


def promotion_cells(pop):
    """The 12 declared cells that additionally get 5 reps at BOTH frequencies."""
    sel = []
    for c in CLASSES:                       # mc1, one per wait class = 9
        sel.append(next(p for p in pop if p["cid"] == "mc1" and p["wc"] == c))
    for cid in ("mc2", "t30-raw"):          # + wrand15 on the other two = 11
        sel.append(next(p for p in pop if p["cid"] == cid and p["wc"] == "wrand15"))
    sel.append(next(p for p in pop if p["cid"] == "mc2" and p["wc"] == "fix0"))
    return [(p["cid"], p["k"]) for p in sel]


def cmd_freeze(args):
    d = OUT / "b2-tranche"
    d.mkdir(parents=True, exist_ok=True)
    pop = tranche_population()
    blob = {"spec": "docs/notes/ucsim_t_provenance.md 14.0 B2",
            "cids": CIDS, "classes": CLASSES, "per_cell": PER_CELL,
            "k_base": K_BASE, "ov": OV, "reps": TRANCHE_REPS,
            "promote_reps": PROMOTE_REPS, "n": len(pop),
            "promotion_cells": promotion_cells(pop), "seeds": pop}
    txt = json.dumps(blob, indent=1)
    (d / "population.json").write_text(txt)
    (d / "population.sha256").write_text(
        hashlib.sha256(txt.encode()).hexdigest() + "\n")
    print(f"{len(pop)} seeds frozen -> {d}/population.json")
    print("sha256", hashlib.sha256(txt.encode()).hexdigest())


# --------------------------------------------------------------------------- #
# B1 -- the P2 re-capture, WITH ITS PARTS
# --------------------------------------------------------------------------- #
def cmd_b1(args):
    from causal_wrand import accesses                    # noqa: E402
    from gen_seq import generate                         # noqa: E402
    import timed_wvec_gate as G                          # noqa: E402

    SEEDS = list(range(90000, 90020)) + [90270, 90364]
    WVECS = [(0, 0), (5, 1), (7, 3), (11, 7)]
    DIRECTED = {90270, 90364}
    LAWCARD = {("fz90364", 5, 1), ("fz90270", 5, 1)}
    NROWS = 4200
    d = OUT / "b1-wvec"
    d.mkdir(parents=True, exist_ok=True)

    old = json.loads((ROOT / "sw/testdata/t2b/p2-wvec/wvec_chip_baseline.json")
                     .read_text())
    out = {"probe": "B1 P2 re-capture WITH per-access parts",
           "spec": "docs/notes/ucsim_t_provenance.md 14.0 B1",
           "use_core": False, "host": HOST, "seeds": SEEDS, "wvecs": WVECS,
           "nrows": NROWS,
           "digest": "bs,tw,addr,npops,gap-from-previous-T1 (T2b normalisation, verbatim)",
           "cases": {}}
    t0 = time.time()
    same = diff = 0
    for seed in SEEDS:
        image, _ = check_seq.compose(generate(f"fz{seed}", exts=()))
        for ws, wmax in WVECS:
            wv = G.wv_of(ws, wmax)
            key = f"fz{seed}:ws{ws}:wmax{wmax}"
            promote = seed in DIRECTED and (ws, wmax) == (5, 1)
            reps = PROMOTE_REPS if promote else 2
            divs = DIVS if promote else [8]
            shas, keys, digs, parts0 = [], [], [], None
            rows0 = None
            n_acc = 0
            for div in divs:
                for _ in range(reps):
                    rows, raw, sha = capture(image, wvec=wv, div=div, tag="b1")
                    rows = rows[:NROWS]
                    shas.append(sha)
                    keys.append(stable_key(rows))
                    acc = accesses(rows)
                    parts = G.parts_of(acc)
                    digs.append(hashlib.sha256(
                        ";".join(parts).encode()).hexdigest()[:16])
                    if rows0 is None:
                        rows0, parts0, n_acc = rows, parts, len(acc)
            prev = (old["cases"].get(key) or {}).get("sha")
            ok = prev == digs[0]
            same += ok
            diff += (not ok)
            out["cases"][key] = {
                "rows": len(rows0), "accesses": n_acc, "sha": digs[0],
                # THE POINT OF THIS PROBE: the stream, not just its hash.
                "parts": parts0,
                "repeatable": len(set(digs)) == 1,
                "pin_identical": len(set(keys)) == 1,
                "reps": reps, "divs": divs, "raw_sha": shas,
                "promoted": promote, "t2b_sha": prev, "matches_t2b": ok,
            }
            if (f"fz{seed}", ws, wmax) in LAWCARD or promote:
                with gzip.open(d / f"{key.replace(':','_')}.rows.json.gz",
                               "wt") as f:
                    json.dump(rows0, f, separators=(",", ":"))
        print(f"  fz{seed} done ({time.time()-t0:.0f}s)", flush=True)
    out["t2b_reproduced"] = f"{same}/{same+diff}"
    (d / "wvec_chip_parts.json").write_text(json.dumps(out, indent=1))
    print(f"\n  T2b digest reproduced: {same}/{same+diff}")
    print(f"wrote {d}/wvec_chip_parts.json")


# --------------------------------------------------------------------------- #
# B2 -- THE VICTORY TRANCHE
# --------------------------------------------------------------------------- #
def cmd_b2(args):
    d = OUT / "b2-tranche"
    pop = json.loads((d / "population.json").read_text())
    promo = {tuple(x) for x in pop["promotion_cells"]}
    seeds = pop["seeds"][:args.limit] if args.limit else pop["seeds"]
    (d / "seeds").mkdir(parents=True, exist_ok=True)
    (d / "raw").mkdir(parents=True, exist_ok=True)
    man = {"probe": "B2 THE VICTORY TRANCHE",
           "spec": "docs/notes/ucsim_t_provenance.md 14.0 B2",
           "use_core": False, "host": HOST, "n": len(seeds), "cells": {}}
    t0 = time.time()
    for i, s in enumerate(seeds):
        cid, k = s["cid"], s["k"]
        cfg = fzc.derive_case(cid, k, OV)
        g = fzc.build(cfg)
        image, meta = check_seq.compose(g)
        isha = hashlib.sha256(bytes(image)).hexdigest()
        w = cfg["waits"]
        kw = dict(waits=int(w["fixed"] or 0)) if not w["wrand"] else \
            dict(wrand=(int(w["wmax"]), int(w["wseed"])))
        promote = (cid, k) in promo
        divs = DIVS if promote else [8]
        reps = PROMOTE_REPS if promote else TRANCHE_REPS
        keys, strict, shas, raws = [], [], [], []
        rows0 = None
        for div in divs:
            for _ in range(reps):
                rows, raw, sha = capture(image, div=div, tag="b2", **kw)
                keys.append(tranche_key(rows))
                strict.append(stable_key(rows))
                shas.append(sha)
                if rows0 is None:
                    rows0, raws = rows, raw
        stable = len(set(keys)) == 1
        key = f"{cid}_{k}"
        rec = {"cid": cid, "k": k, "ov": OV, "waits": w,
               "image_sha256": isha, "chip_rows": rows0,
               "wc": s["wc"], "stable": stable,
               "stable_t2b_projection": len(set(strict)) == 1,
               "reps": reps, "divs": divs,
               "raw_sha": shas, "promoted": promote,
               "freq_identical": (len({keys[0], keys[-1]}) == 1) if promote
                                 else None}
        with gzip.open(d / "seeds" / f"{key}.json.gz", "wt") as f:
            json.dump(rec, f, separators=(",", ":"))
        with gzip.open(d / "raw" / f"{key}.raw.hex.gz", "wt") as f:
            f.write("\n".join(raws) + "\n")
        man["cells"][key] = {k2: v for k2, v in rec.items()
                             if k2 != "chip_rows"} | {"rows": len(rows0)}
        if i % 20 == 0:
            print(f"  {i}/{len(seeds)} {key} {s['wc']} rows={len(rows0)} "
                  f"stable={stable} ({time.time()-t0:.0f}s)", flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    ns = sum(1 for v in man["cells"].values() if not v["stable"])
    print(f"\n  captured {len(seeds)} cells in {man['seconds']}s; "
          f"UNSTABLE {ns}")
    print(f"wrote {d}/manifest.json")


def cmd_idle(args):
    import b1_recapture
    b1_recapture.board_idle()
    print("board idle; use_core=0")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze").set_defaults(fn=cmd_freeze)
    sub.add_parser("b1").set_defaults(fn=cmd_b1)
    p = sub.add_parser("b2"); p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=cmd_b2)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
