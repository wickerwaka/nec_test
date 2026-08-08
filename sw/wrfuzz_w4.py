#!/usr/bin/env python3
"""wrfuzz_w4 -- THE VICTORY SITTING (task #38, W4).

It executes the FROZEN victory protocol and NOTHING else:

  * the population is `sw/testdata/wrfuzz/victory_population.json`, sha256
    `dcaa48fa991f…`, frozen at W2 and verified before it is read;
  * the bar is **B = 86.6681 %**, frozen at W2 (`wrfuzz_provenance.md` §3.1)
    and NEVER re-derived here -- this file carries it as a constant beside the
    sha of the document it came from, so a drift is a diff and not a rounding;
  * the statistic is the one that produced `S`: the **unweighted mean of the
    per-stratum hardware-versus-silicon cycle-exact rates** under the
    registered OPEN_BUS exclusion.  `wrfuzz_w2.open_bus` is IMPORTED, not
    re-implemented, so the two cannot drift.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

BOARD DISCIPLINE (CLAUDE.md), in code and not in a comment -- W1's driver's
contract, unchanged: socket first and the A/B pair differs in `use_core` and
nothing else (`fuzz_campaign.capture_board` is the inherited primitive);
`div_guard` PINNED and its readback RECORDED at every cell boundary; the flash
pin is checked against `flash_log`'s tail before any capture; full per-clock
rows retained for EVERY capture with sha256 (F-9's booked lesson -- the tranche
is 296 seeds, so the retention policy that failed the survey is affordable
here); `board_idle()` at the close with `use_core=0` left selected; a wedge
STOPS the session.

Subcommands:
  preflight  single-writer, era/flash pin, the whole-population regeneration
             integrity leg (B-3/B-4/B-6), div_guard and check_ab_hw first light
  capture    the 196-seed body + the four directed cells, at the frozen
             repetitions
  score      the tranche statistic against B, the per-stratum table, the
             family census, the D-cells' class-B statistic, and B-1..B-9
  idle       board_idle() + a closing div_guard readback
"""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                                 # noqa: E402
import fuzz_classify as fc                                  # noqa: E402
import wrfuzz_w1 as w1                                      # noqa: E402
import wrfuzz_w2 as w2                                      # noqa: E402
import wvec_shapes as wv                                    # noqa: E402

HOST = "root@mister-nec"
CID = "wr2"
CDIR = fzc.CAMPAIGNS / CID
OUT = SW / "testdata" / "wrfuzz"
POP_PATH = OUT / "victory_population.json"

# --------------------------------------------------------------------------- #
# THE FROZEN CONSTANTS.  Carried as literals, verified against the artifacts.
# --------------------------------------------------------------------------- #
POP_SHA256 = "dcaa48fa991fa3cc78588bc95e4881a17a563b875624ac58138882056f39066d"
S_FROZEN = 91.6681          # wrfuzz_provenance.md §3.1, computed at W2
B_FROZEN = 86.6681          # = S - 5.0, campaign plan §5.  NOT re-derived.
K_BODY_BASE = 300000
K_DIRECTED_BASE = 328000


def population():
    blob = POP_PATH.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    if sha != POP_SHA256:
        raise SystemExit(f"*** VICTORY POPULATION SHA MISMATCH ***\n"
                         f"  on disk {sha}\n  frozen  {POP_SHA256}\n"
                         f"  the tranche is not the frozen one -- STOP")
    return json.loads(blob.decode())


def cells(pop):
    """Every cell of the tranche, body then directed, in one flat list.  A cell
    is (label, tier, ov, [k...], reps_default)."""
    out = []
    for b in pop["body"]:
        out.append({"kind": "body", "i": b["i"],
                    "label": f"{b['tier']}/{b['src']}", "tier": b["tier"],
                    "ov": b["ov"], "k": list(b["k"])})
    for d in pop["directed"]:
        out.append({"kind": "directed", "i": None, "label": d["cell"],
                    "tier": d["tier"], "ov": d["ov"], "k": list(d["k"]),
                    "wlo": d["wlo"], "whi": d["whi"], "blk": d["blk"]})
    return out


def reps_for(pop, k):
    return pop["promotion_reps"] if k in set(pop["promotion_cells"]) \
        else pop["reps"]


def body_stratum_of(k):
    """The stratum of a BODY seed, DERIVED from k (never from a stored label),
    so a mislabelled record cannot move a denominator -- `wrfuzz_w2`'s rule at
    the tranche's own base."""
    i = (int(k) - K_BODY_BASE) // w1.K_STRIDE
    if not (0 <= i < len(w1.STRATA)):
        raise ValueError(f"k={k} is outside the tranche's body blocks")
    st = w1.STRATA[i]
    if not (K_BODY_BASE + w1.K_STRIDE * i <= int(k)
            < K_BODY_BASE + w1.K_STRIDE * i + 7):
        raise ValueError(f"k={k} is outside body stratum {i}")
    return st


# --------------------------------------------------------------------------- #
# board primitives -- W1's, imported rather than re-written
# --------------------------------------------------------------------------- #
def div_guard(tag, rec=None):
    return w1.div_guard(tag, rec)


def board_idle():
    return w1.board_idle()


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #
def cmd_preflight(a):
    OUT.mkdir(parents=True, exist_ok=True)
    pop = population()
    rec = {"stage": "W4 preflight", "cid": CID, "host": HOST,
           "pop_sha256": POP_SHA256,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": []}
    ok = True
    print(f"== victory population VERIFIED sha256 {POP_SHA256[:16]}…")

    print("== single-writer / reachability")
    rc, up, err = w1._ssh("uptime")
    rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
    print(f"  uptime: {rec['uptime']}")
    if rc != 0:
        rec["single_writer"] = "UNKNOWN (unreachable)"
        (OUT / "w4_preflight.json").write_text(json.dumps(rec, indent=1))
        return 2
    rc, ps, _ = w1._ssh("ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    others = [l for l in ps.splitlines() if l.strip()]
    rec["board_procs"] = others
    rec["single_writer"] = "VIOLATED" if others else "OK"
    if others:
        ok = False
        print(f"  *** SINGLE-WRITER VIOLATION: {others} ***")
    else:
        print("  no v30/serve process on the board -> SINGLE WRITER")

    print("== era / flash pin")
    flash = fzc._last_flash_entry()
    rec["flash_log_tail"] = flash
    man_path = CDIR / "manifest.json"
    if not man_path.exists():
        print(f"  no manifest for {CID} -- run `fuzz_campaign.py new {CID}`")
        ok = False
    else:
        man = json.loads(man_path.read_text())
        era = fzc.era_of(man)
        rec["era"] = era
        print(json.dumps(era, indent=1))
        if (flash or {}).get("sha256") != (man.get("flash_pin") or {}).get("sha256"):
            ok = False
            print("  *** flash pin MISMATCH against flash_log tail ***")
        for key in ("sof_sha256", "gen_git", "rig_evt_hold_bits"):
            if era.get(key) in (None, ""):
                ok = False
                print(f"  *** era field ABSENT: {key} ***")
        if not era["rtl"]["inputs_sha256"]:
            ok = False
            print("  *** RTL input-manifest hash ABSENT (B-2) ***")

    # ---- the WHOLE population regenerated, before board time is spent ------ #
    # The tranche is 296 seeds, so B-3 / B-4 / B-6 are evaluated over ALL of it
    # rather than on a sample: at this size the complete leg costs less than the
    # argument about whether the sample was representative.
    print("== generation / regeneration -- the WHOLE population")
    hits = 0
    per = []
    for c in cells(pop):
        npair = 0
        vecs = set()
        for k in c["k"]:
            cfg = fzc.derive_case(CID, k, c["ov"])
            img, _ = fzc.compose_case(fzc.build(cfg), cfg)
            sha = hashlib.sha256(bytes(img)).hexdigest()
            cfg2 = fzc.derive_case(CID, k, c["ov"])
            img2, _ = fzc.compose_case(fzc.build(cfg2), cfg2)
            if sha != hashlib.sha256(bytes(img2)).hexdigest():
                hits += 1
                print(f"  GEN_DRIFT {c['label']}/{k}")
            npair += fzc.bad_0f_pairs(img)
            if cfg["evt"] is not None:
                hits += 1
                print(f"  EVT PRESENT {c['label']}/{k}")
            if cfg["tier"] != c["tier"]:
                hits += 1
                print(f"  TIER WRONG {c['label']}/{k}")
            v = fzc.wvec_of(cfg)
            src = c["ov"].get("wvec_shapes")
            if src:
                if v is None or len(v) != wv.NWVEC or \
                        not all(0 <= x <= 31 for x in v) or \
                        cfg["wvec"]["shape"] != src[0]:
                    hits += 1
                    print(f"  WVEC BAD {c['label']}/{k}")
                else:
                    vecs.add(wv.sha256_of(v))
                # the DIRECTED cells' own selection criterion, re-checked on
                # the artifact rather than trusted from the frozen file
                if c["kind"] == "directed":
                    sp = cfg["wvec"]
                    if (sp.get("blk"), sp.get("wlo"), sp.get("whi")) != \
                            (c["blk"], c["wlo"], c["whi"]):
                        hits += 1
                        print(f"  DIRECTED SPEC WRONG {c['label']}/{k}: {sp}")
            elif v is not None:
                hits += 1
                print(f"  WVEC UNEXPECTED {c['label']}/{k}")
        per.append({"cell": c["label"], "n": len(c["k"]),
                    "brkem_pairs": npair, "distinct_vectors": len(vecs)})
        if npair:
            hits += 1
            print(f"  BRKEM PAIRS {c['label']}: {npair}")
    rec["regen"] = {"cells": per, "hits": hits,
                    "seeds": sum(p["n"] for p in per)}
    print(f"  {rec['regen']['seeds']} seeds, hits={hits}")
    ok = ok and hits == 0

    if a.board:
        print("== board health")
        div_guard("w4-preflight", rec["div_guards"])
        r = subprocess.run([sys.executable, str(SW / "check_ab_hw.py"), "all",
                            "800", "--host", HOST],
                           capture_output=True, text=True, timeout=900)
        tail = (r.stdout + r.stderr).strip().splitlines()
        rec["check_ab_hw"] = {"rc": r.returncode, "tail": tail[-12:]}
        for l in tail[-12:]:
            print(f"  {l}")
        if r.returncode != 0:
            ok = False
            print("  *** check_ab_hw FAILED ***")
        div_guard("w4-preflight-end", rec["div_guards"])
        board_idle()
        print("  board left use_core=0 (board_idle)")

    rec["verdict"] = "OK" if ok else "BLOCKED"
    (OUT / "w4_preflight.json").write_text(json.dumps(rec, indent=1))
    print(f"\nW4 PREFLIGHT: {rec['verdict']}  -> {OUT/'w4_preflight.json'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def _done(res_path):
    if not res_path.exists():
        return set()
    out = set()
    for line in res_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.add(json.loads(line)["k"])
            except Exception:                               # noqa: BLE001
                pass
    return out


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    pop = population()
    man_path = CDIR / "manifest.json"
    if not man_path.exists():
        print(f"capture: no manifest for {CID}")
        return 2
    man = json.loads(man_path.read_text())
    cur = fzc._last_flash_entry()
    if (cur or {}).get("sha256") != (man.get("flash_pin") or {}).get("sha256"):
        print("capture: flash_log tail has moved off the manifest pin -- STOP")
        return 2
    era = fzc.era_of(man)
    fzc.set_era(era)

    bdir = CDIR / "captures"
    bdir.mkdir(parents=True, exist_ok=True)
    res_path = CDIR / "results.jsonl"
    done = _done(res_path)
    rec = {"stage": "W4 capture", "cid": CID, "host": a.host,
           "pop_sha256": POP_SHA256, "era": era,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cells": [], "div_guards": [], "seeds": []}
    rec_path = OUT / "w4_capture.json"
    t_all = time.time()
    halted = None
    n_seed_loops = 0
    quar_run = 0

    for c in cells(pop):
        todo = [k for k in c["k"] if k not in done]
        if not todo:
            print(f"== {c['label']:<16} already complete, skipped")
            continue
        print(f"\n== {c['label']:<16} n={len(todo)}", flush=True)
        div_guard(f"cell-{c['label']}", rec["div_guards"])
        t0 = time.time()
        wrote = 0
        for k in todo:
            R = reps_for(pop, k)
            reps, line1, err = [], None, None
            for rep in range(1, R + 1):
                r = fzc.eval_case(CID, k, c["ov"], False, a.host, False,
                                  keep_rows=True)
                if r["rows"] is None:
                    err = f"no rows (run_error) rep {rep}"
                    break
                reps.append(r["rows"])
                if rep == 1:
                    line1 = r["line"]
            if err or line1 is None:
                quar_run += 1
                rec["seeds"].append({"cell": c["label"], "k": k,
                                     "error": err or "short"})
                print(f"  {c['label']}/{k} QUARANTINE {err}")
                if quar_run >= 5:
                    halted = ("circuit breaker: 5 consecutive quarantines"
                              " -- STOPPED, not nursed")
                    break
                continue
            quar_run = 0
            n_seed_loops += len(reps)
            # ---- the stability leg: rep 1 against every later rep, BOTH A/B
            # legs, inside `fuzz_classify.diff_rows`' own window (rows 9+) --
            # W1's B-9 contract, applied to every tranche seed rather than to a
            # 5 % sub-sample, because at 296 seeds the whole population fits.
            stab = []
            for j in range(1, len(reps)):
                for leg in (0, 1):
                    d = fc.diff_rows(reps[0][leg], reps[j][leg])
                    stab.append({"rep": j + 1,
                                 "leg": "chip" if leg == 0 else "fabric",
                                 "n": d.n, "bad": d.bad, "flick": d.flick,
                                 "first": d.first})
            bad = sum(s["bad"] for s in stab)
            flick = sum(s["flick"] for s in stab)
            blob = json.dumps({"k": k, "cell": c["label"], "kind": c["kind"],
                               "cfg_hash": line1["cfg_hash"],
                               "image_sha256": line1["image_sha256"],
                               "wvec_sha256": line1.get("wvec_sha256"),
                               "era": era, "reps": len(reps),
                               "rows": [{"chip": r[0], "fabric": r[1]}
                                        for r in reps]})
            p = bdir / f"{c['tier']}_{k}_{line1['cfg_hash']}.json.gz"
            with gzip.open(p, "wt") as f:
                f.write(blob)
            line1["rep_count"] = len(reps)
            line1["stable"] = (bad == 0)
            line1["stab_bad"] = bad
            line1["stab_flick"] = flick
            line1["cell"] = c["label"]
            line1["cell_kind"] = c["kind"]
            line1["rows_file"] = p.name
            line1["rows_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            with open(res_path, "a") as fh:
                fzc._append_fsync(fh, line1)
            rec["seeds"].append({"cell": c["label"], "k": k,
                                 "verdict": line1["verdict"],
                                 "sub": line1["sub"], "reps": len(reps),
                                 "stable": bad == 0, "flick": flick,
                                 "rows": p.name,
                                 "sha256": line1["rows_sha256"]})
            wrote += 1
            if bad:
                print(f"  {c['label']}/{k} *** UNSTABLE bad={bad} ***")
        dt = time.time() - t0
        rec["cells"].append({"cell": c["label"], "n": len(c["k"]),
                             "written": wrote, "seconds": round(dt, 1)})
        rec["board_seconds"] = round(time.time() - t_all, 1)
        rec["seed_loops"] = n_seed_loops
        rec_path.write_text(json.dumps(rec, indent=1))
        print(f"  {c['label']}: {wrote}/{len(todo)} in {dt:.1f}s")
        if halted:
            break
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(bdir.glob('*.json.gz'))]
    (bdir / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    div_guard("w4-capture-end", rec["div_guards"])
    rec["halted"] = halted
    rec["board_seconds"] = round(time.time() - t_all, 1)
    rec["seed_loops"] = n_seed_loops
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec_path.write_text(json.dumps(rec, indent=1))
    print(f"\nW4 CAPTURE: {sum(c['written'] for c in rec['cells'])} seeds, "
          f"{n_seed_loops} seed-loops in {rec['board_seconds']/60:.1f} min"
          f"{'  HALTED: ' + halted if halted else ''}")
    return 1 if halted else 0


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #
def _lines():
    p = CDIR / "results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _rows_of(r):
    p = CDIR / "captures" / r["rows_file"]
    blob = json.loads(gzip.decompress(p.read_bytes()))
    return blob["rows"][0]["chip"], blob["rows"][0]["fabric"]


def _classify(r):
    import s15_census as s15                                # noqa: PLC0415
    chip, fab = _rows_of(r)
    entry = dict(r)
    entry["chip_rows"] = chip
    entry["fabric_rows"] = fab
    return s15.classify(entry, chip, fab)


def cmd_score(a):
    pop = population()
    rows = _lines()
    by_k = {r["k"]: r for r in rows}
    print(f"== wrfuzz W4 SCORE -- {len(rows)} tranche captures, "
          f"population sha256 {POP_SHA256[:16]}…")

    # --------------------------------------------------------------------- #
    # B-1 .. B-9, the capture-integrity bars.  A bar that fires is VOID.
    # --------------------------------------------------------------------- #
    bars = {}
    body_ks = [k for b in pop["body"] for k in b["k"]]
    dir_ks = [k for d in pop["directed"] for k in d["k"]]
    bars["B-2_era"] = {"absent": sum(1 for r in rows if not r.get("era")),
                       "distinct_sof": sorted({(r.get("era") or {})
                                               .get("sof_sha256")
                                               for r in rows})}
    bars["B-3_vector"] = {
        "spec_without_hex": sum(1 for r in rows
                                if r.get("wvec") and not r.get("wvec_hex")),
        "wrong_len": sum(1 for r in rows if r.get("wvec_hex")
                         and r.get("wvec_n") != wv.NWVEC)}
    bars["B-5_bus_bound"] = {
        "at_or_beyond": sorted(r["k"] for r in rows
                               if (r.get("bus_cycles") or 0) >= wv.NWVEC)}
    # B-1 -- THE VECTOR WAS APPLIED.  W1 could only read this off the ~12 % of
    # captures whose rows survived; here every capture's socket rows are on
    # disk, so the bar is evaluated on the WHOLE tranche.  Registered ≥ 99.9 %,
    # expected 100.0 %, and anything below 100.0 % is a FINDING (prereg §6).
    b1_m = b1_n = 0
    b1_bad = []
    for r in rows:
        if not r.get("wvec_hex"):
            continue
        chip, _ = _rows_of(r)
        m, n, fb = wv.applied_score(chip, wv.from_hex(r["wvec_hex"]))
        b1_m += m
        b1_n += n
        if fb is not None:
            b1_bad.append((r["k"], fb))
    bars["B-1_vector_applied"] = {
        "matched": b1_m, "total": b1_n,
        "rate": (100.0 * b1_m / b1_n) if b1_n else None,
        "seeds_with_a_mismatch": len(b1_bad), "first": b1_bad[:10]}
    # B-4 / B-6 are GENERATION bars and were evaluated over the whole
    # population at preflight, before board time was spent; carried in rather
    # than re-derived, so the two cannot report different things.
    pf = OUT / "w4_preflight.json"
    if pf.exists():
        p = json.loads(pf.read_text())
        bars["B-4_B-6_generation"] = {
            "seeds": (p.get("regen") or {}).get("seeds"),
            "hits": (p.get("regen") or {}).get("hits"),
            "brkem_pairs": sum(c.get("brkem_pairs", 0)
                               for c in (p.get("regen") or {}).get("cells", []))}
    bars["B-9_stability"] = {
        "unstable": sorted(r["k"] for r in rows if not r.get("stable", True)),
        "stable": sum(1 for r in rows if r.get("stable", True)),
        "flicker_rows": sum(r.get("stab_flick", 0) for r in rows)}
    quarantined = [k for k in body_ks + dir_ks if k not in by_k]
    bars["captured"] = {"expected": len(body_ks) + len(dir_ks),
                        "present": len(rows), "missing": quarantined}

    # --------------------------------------------------------------------- #
    # THE PER-STRATUM TABLE -- the SAME construction as `S`.
    #
    # Exclusions, all three DECLARED IN ADVANCE (prereg §2.4 + the b2
    # precedent for instability): the registered OPEN_BUS detector, B-5's
    # bus-cycle bound, and a cell that is not stable across its repetitions.
    # class-A 8080 landings are COUNTED and LEFT IN, per §3.3.
    # --------------------------------------------------------------------- #
    def excluded(r):
        if w2.open_bus(r):
            return "open_bus"
        if (r.get("bus_cycles") or 0) >= wv.NWVEC:
            return "b5_bound"
        if not r.get("stable", True):
            return "unstable"
        return None

    per = defaultdict(Counter)
    for r in rows:
        if r["k"] not in set(body_ks):
            continue
        i = body_stratum_of(r["k"])["i"]
        t = per[i]
        t["n"] += 1
        e = excluded(r)
        if e:
            t[e] += 1
            continue
        t["scored"] += 1
        if r["verdict"] == "SUCCESS":
            t["exact"] += 1
        else:
            t[f"miss_{r['verdict']}"] += 1

    print(f"\n{'i':>3} {'stratum':<16} {'n':>3} {'OPEN':>5} {'B5':>3} "
          f"{'UNST':>5} {'scored':>7} {'exact':>6} {'rate%':>8}")
    rates, empty = [], []
    tot = Counter()
    table = []
    for st in w1.STRATA:
        t = per[st["i"]]
        sc, ex = t["scored"], t["exact"]
        rate = (100.0 * ex / sc) if sc else None
        if rate is None:
            empty.append(st["i"])
        else:
            rates.append(rate)
        for kk in t:
            tot[kk] += t[kk]
        table.append({"i": st["i"], "stratum": w1.label(st), "n": t["n"],
                      "open_bus": t["open_bus"], "b5": t["b5_bound"],
                      "unstable": t["unstable"], "scored": sc, "exact": ex,
                      "rate": rate})
        print(f"{st['i']:>3} {w1.label(st):<16} {t['n']:>3} "
              f"{t['open_bus']:>5} {t['b5_bound']:>3} {t['unstable']:>5} "
              f"{sc:>7} {ex:>6} "
              + (f"{rate:>8.2f}" if rate is not None else f"{'--':>8}"))

    T = sum(rates) / len(rates) if rates else float("nan")
    pooled_ex, pooled_sc = tot["exact"], tot["scored"]
    pooled = 100.0 * pooled_ex / pooled_sc if pooled_sc else float("nan")
    bar_seeds = int(B_FROZEN / 100.0 * pooled_sc)     # rounded DOWN, as written

    print(f"\n  scored {pooled_sc}, exact {pooled_ex}, pooled "
          f"{pooled:.2f} %")
    if empty:
        print(f"  ⚠ STRATA WITH AN EMPTY SCORED DENOMINATOR (no rate exists "
              f"to average): {empty} -- the mean is over {len(rates)}, "
              f"declared in advance")
    print(f"\n  THE TRANCHE STATISTIC  T = unweighted mean of the per-stratum "
          f"rates = {T:.4f} %")
    print(f"  THE FROZEN BAR         B = {B_FROZEN} %   "
          f"(S = {S_FROZEN} % at W2, minus 5.0; NOT re-derived)")
    print(f"  the plan's seed-count conversion: floor({B_FROZEN} % x "
          f"{pooled_sc}) = {bar_seeds} seeds; measured {pooled_ex}")

    # --------------------------------------------------------------------- #
    # THE SECOND CONDITION OF `MET`: every non-exact seed's first divergence
    # in a family NAMED in the W2 census's taxonomy.
    # --------------------------------------------------------------------- #
    # The six families the W2 census actually populated (§3.3): `PF_LOST` 43 ·
    # `SCHEDULE` 42 · `DATA_SEQ` 23 · `PF_GAINED` 18 · `PIN` 7 · `PF_ADDR` 2,
    # with `TAIL_EXTRA` / `TAIL_MISS` 0 and the catch-all EMPTY.  ⚠ The `MET`
    # clause says "a family NAMED in the W2 census's taxonomy" -- the TAXONOMY,
    # which is `s15_census`'s whole family set, not only the six cells that
    # happened to be non-zero.  So `TAIL_EXTRA` / `TAIL_MISS` COUNT AS NAMED
    # and a member of either is a result, not a failure of the clause; what is
    # NOT named is the catch-all, a classify error, or anything else.  Stated
    # here, in advance, so the reading cannot be chosen after the count.
    #
    # ⚠ `NOW_EXACT` IS NOT A FAMILY AND IS NOT A CONDITION-2 FAILURE, and the
    # reason is a MEASUREMENT on the banked W2 census, not an accommodation.
    # `s15_census.classify` returns `cat = NOW_EXACT` when the two row streams
    # have NO difference at all -- the seed's non-SUCCESS verdict came off the
    # FUNCTIONAL/architectural axis and not off the rows.  Such a seed HAS NO
    # FIRST DIVERGENCE, so the clause "every non-exact seed's FIRST DIVERGENCE
    # falls in a family named at W2" is VACUOUS for it rather than violated.
    # It is also not new: `sw/testdata/wrfuzz/w2_fabric_census.json.gz` is
    # `PF_LOST` 43 · `SCHEDULE` 42 · `DATA_SEQ` 23 · `PF_GAINED` 18 · `PIN` 7 ·
    # `PF_ADDR` 2 · **`NOW_EXACT` 1** = 136, which is exactly §3.3's
    # "136 scored misses / 135 classified".  So the category is IN the W2
    # census, with one member, and is carried here COUNTED and REPORTED.
    W2_FAMILIES = {"PF_LOST", "SCHEDULE", "DATA_SEQ", "PF_GAINED", "PIN",
                   "PF_ADDR", "TAIL_EXTRA", "TAIL_MISS", "NOW_EXACT"}
    W2_NONZERO = {"PF_LOST", "SCHEDULE", "DATA_SEQ", "PF_GAINED", "PIN",
                  "PF_ADDR", "NOW_EXACT"}
    resid = [r for r in rows if r["k"] in set(body_ks)
             and not excluded(r) and r["verdict"] != "SUCCESS"]
    fam = Counter()
    unnamed = []
    for r in resid:
        try:
            c = _classify(r)
        except Exception as e:                              # noqa: BLE001
            fam["CLASSIFY_ERROR"] += 1
            unnamed.append((r["k"], f"error:{e}"))
            continue
        f = c.get("fam") or ("NOW_EXACT" if c.get("cat") == "NOW_EXACT"
                             else "CATCH_ALL")
        fam[f] += 1
        if f not in W2_FAMILIES:
            unnamed.append((r["k"], f))
    print(f"\n  the residue, by family ({len(resid)} scored non-exact body "
          f"seeds):")
    for f, n in fam.most_common():
        tag = ("" if f in W2_NONZERO else
               "   (NAMED in the taxonomy, EMPTY at W2)" if f in W2_FAMILIES
               else "   *** NOT IN THE W2 TAXONOMY ***")
        print(f"    {f:<16} {n}{tag}")
    named_ok = not unnamed

    met = (T >= B_FROZEN) and named_ok
    void = bool(bars["B-5_bus_bound"]["at_or_beyond"]) \
        or bars["B-2_era"]["absent"] > 0 \
        or bars["B-3_vector"]["spec_without_hex"] > 0 \
        or bars["B-3_vector"]["wrong_len"] > 0
    verdict = "VOID" if void else ("MET" if met else "MISSED")
    print(f"\n  ================================================")
    print(f"  VICTORY: **{verdict}**   T = {T:.4f} %  vs  B = {B_FROZEN} %"
          f"   ({T - B_FROZEN:+.4f} points)")
    print(f"    condition 1 (T >= B)                : "
          f"{'MET' if T >= B_FROZEN else 'NOT MET'}")
    print(f"    condition 2 (every residue family named at W2): "
          f"{'MET' if named_ok else 'NOT MET -- ' + str(unnamed)}")
    print(f"  ================================================")

    # --------------------------------------------------------------------- #
    # THE FOUR DIRECTED CELLS -- scored as their own cells, NOT folded into T.
    # §68.6's class-B observable: same-clock / different-owner pairs, paired by
    # ordinal.  Here the pairing is chip against the FABRIC core, which is this
    # campaign's own comparator (plan §4), and `sm3_h3_cell.measure` is
    # IMPORTED so the statistic is the one §68.6 measured.
    # --------------------------------------------------------------------- #
    import sm3_h3_cell as h3                                # noqa: PLC0415
    print(f"\n  the four DIRECTED H3-B cells (skew, blk = 32) -- "
          f"class-B: same clock, different owner")
    dcells = []
    for d in pop["directed"]:
        # TWO POPULATIONS, both reported -- prereg §3.4a, declared before any
        # capture.  Ordinal pairing is only unambiguous where the two streams
        # are the same stream; on a divergent seed a coincidental `t1` match
        # with a different owner is a pairing artefact, not a class-B event.
        # §68.6's own population agreed 7,254/7,254, i.e. it was the EXACT
        # population.  So (a) is the strict, comparable statistic and (b) is
        # the whole cell; NEITHER is dropped and neither is chosen afterwards.
        agg = {"exact": [0, 0, 0], "all": [0, 0, 0]}     # acc, same, swap
        n_ex = n_seen = 0
        swaps = []
        for k in d["k"]:
            r = by_k.get(k)
            if r is None:
                continue
            n_seen += 1
            is_ex = r["verdict"] == "SUCCESS"
            n_ex += is_ex
            chip, fab = _rows_of(r)
            ca, fa = h3.measure(chip), h3.measure(fab)
            for j in range(min(len(ca), len(fa))):
                pops = ["all"] + (["exact"] if is_ex else [])
                for p in pops:
                    agg[p][0] += 1
                if ca[j]["t1"] == fa[j]["t1"]:
                    hit = 1 if ca[j]["prev_kind"] == fa[j]["prev_kind"] else 2
                    for p in pops:
                        agg[p][hit] += 1
                    if hit == 2:
                        swaps.append((k, j, ca[j]["prev_kind"],
                                      fa[j]["prev_kind"], ca[j]["occ"], is_ex))
        dcells.append({"cell": d["cell"], "tier": d["tier"],
                       "wlo": d["wlo"], "whi": d["whi"], "n": n_seen,
                       "exact_seeds": n_ex,
                       "exact_pop": {"paired": agg["exact"][0],
                                     "same_owner": agg["exact"][1],
                                     "class_b": agg["exact"][2]},
                       "all_pop": {"paired": agg["all"][0],
                                   "same_owner": agg["all"][1],
                                   "class_b": agg["all"][2]},
                       "swaps": swaps[:20]})
        print(f"    {d['cell']}  {d['tier']:<5} wlo={d['wlo']} whi={d['whi']}"
              f"   seeds {n_seen} (exact {n_ex})")
        print(f"        (a) EXACT seeds only : {agg['exact'][0]:>6} paired "
              f"accesses   **class-B {agg['exact'][2]}**")
        print(f"        (b) all seeds        : {agg['all'][0]:>6} paired "
              f"accesses   class-B {agg['all'][2]}  [pairing is ambiguous "
              f"past a divergence]")
    ta = sum(c["exact_pop"]["paired"] for c in dcells)
    tb = sum(c["exact_pop"]["class_b"] for c in dcells)
    aa = sum(c["all_pop"]["paired"] for c in dcells)
    ab = sum(c["all_pop"]["class_b"] for c in dcells)
    print(f"    TOTAL (a) EXACT: **{tb} class-B pairs over {ta} paired "
          f"accesses**   (§68.6 measured 0 over 7,254)")
    print(f"    TOTAL (b) all  : {ab} class-B pairs over {aa} paired accesses")

    print(f"\n  the bars:")
    for k, v in bars.items():
        print(f"    {k}: {json.dumps(v)[:200]}")

    if a.report:
        Path(a.report).write_text(json.dumps(
            {"pop_sha256": POP_SHA256, "S_frozen": S_FROZEN,
             "B_frozen": B_FROZEN, "T": T, "verdict": verdict,
             "condition_T": T >= B_FROZEN, "condition_families": named_ok,
             "empty_strata": empty, "n_rates_averaged": len(rates),
             "pooled_exact": pooled_ex, "pooled_scored": pooled_sc,
             "pooled_rate": pooled, "bar_seed_count": bar_seeds,
             "strata": table, "families": dict(fam), "unnamed": unnamed,
             "directed": dcells, "bars": bars}, indent=1))
        print(f"\n  report -> {a.report}")
    return 0


def cmd_idle(a):
    rec = []
    board_idle()
    div_guard("w4-close", rec)
    (OUT / "w4_idle.json").write_text(json.dumps(rec, indent=1))
    print("board_idle() done, use_core=0 selected")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--board", action="store_true")
    p.set_defaults(fn=cmd_preflight)
    p = sub.add_parser("capture")
    p.add_argument("--host", default=HOST)
    p.set_defaults(fn=cmd_capture)
    p = sub.add_parser("score")
    p.add_argument("--report", default="")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("idle")
    p.set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
