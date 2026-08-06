#!/usr/bin/env python3
"""wrfuzz_w1 -- the W1 SOCKET-CAPTURE driver for the random-wait fuzz campaign
(task #38).

It executes `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md` AS REGISTERED and
scores that document's capture-integrity bars B-1 .. B-9.  It does not design
anything: the 28 strata, their sizes, their k-blocks and the bars all come from
the pre-registration, which was committed before any generation at scale and
before any board contact.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

BOARD DISCIPLINE (CLAUDE.md), in code and not in a comment:
  * SOCKET FIRST, and the A/B pair differs in `use_core` and in NOTHING else --
    `fuzz_campaign.capture_board` is the inherited primitive and is not
    re-implemented here.
  * The DIVIDER IS PINNED and the runner's own `div_readback` is RECORDED at
    every stratum boundary (`div_guard`, s13_board's contract verbatim).  An
    UNPINNED readback is a rig-integrity FINDING, printed and banked, never
    smoothed.
  * NO FLASHING.  The resident bitstream is the pin in the campaign manifest
    and `fuzz_campaign run` REFUSES if `flash_log`'s tail has moved off it.
  * Full per-clock rows retained with a sha256 (the B-9 pass banks all three
    repetitions' rows, both legs, and writes SHA256SUMS beside them).
  * `board_idle()` at the close, with `use_core=0` left selected.
  * A wedge STOPS the session; it is not nursed along.  `cmd_run`'s own
    circuit breaker (>= 5 consecutive quarantines) is left armed, and a
    stratum that writes fewer lines than it was asked for HALTS this driver.

Subcommands:
  preflight  single-writer probe, board reachability, div_guard, the boot A/B
             health leg, the era block, and the offline regeneration sample --
             everything that must be true BEFORE board time is spent
  capture    the 28 strata, in the registered k-blocks, in order
  b9         the B-9 stability sub-sample: 158 seeds x 3 repetitions
  bars       score B-1 .. B-9 from the banked results, OFFLINE
  idle       board_idle() + a closing div_guard readback
"""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                          # noqa: E402
import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import testimage                                          # noqa: E402
import v30run                                             # noqa: E402
import wvec_shapes as wv                                  # noqa: E402

HOST = "root@mister-nec"
CID = "wr1"
CDIR = fzc.CAMPAIGNS / CID
OUT = SW / "testdata" / "wrfuzz"

# --------------------------------------------------------------------------- #
# THE REGISTERED STRATIFICATION -- prereg §2.1 / §2.2, transcribed and then
# ASSERTED (28 strata, 2,100 + 1,050 = 3,150 seeds, k-blocks 1,000 apart from
# k_base = 200000 in the document's own order).
# --------------------------------------------------------------------------- #
K_BASE = 200000
K_STRIDE = 1000
SOURCES = ("fix0", "fix1", "fix2", "fix3",
           "wrand1", "wrand2", "wrand3", "wrand7", "wrand15",
           "wvec-uni", "wvec-walk", "wvec-skew", "wvec-burst", "wvec-edge")


def strata():
    out, i = [], 0
    for tier, n in (("soup", 150), ("raw", 75)):
        for src in SOURCES:
            out.append({"i": i, "tier": tier, "src": src, "n": n,
                        "k_lo": K_BASE + K_STRIDE * i})
            i += 1
    return out


STRATA = strata()
assert len(STRATA) == 28, "the grid is 2 tiers x 14 wait sources"
assert sum(s["n"] for s in STRATA) == 3150, "the registered corpus is 3,150 seeds"
assert STRATA[0]["k_lo"] == 200000 and STRATA[27]["k_lo"] == 227000


def ov_of(st):
    """The overrides for one stratum -- prereg §2.3's invocation, in code."""
    ov = {"force_tier": st["tier"], "no_evt": True, "no8080": True}
    src = st["src"]
    if src.startswith("fix"):
        ov["force_fixed"] = int(src[3:])
    elif src.startswith("wrand"):
        ov["force_wrand"] = [int(src[5:])]
    elif src.startswith("wvec-"):
        ov["wvec_shapes"] = [src[5:]]
    else:
        raise ValueError(src)
    return ov


def label(st):
    return f"{st['tier']}/{st['src']}"


# --------------------------------------------------------------------------- #
# THE B-9 SUB-SAMPLE -- declared HERE, derived, and fixed before any capture.
# 5 % of 3,150 is 157.5; the registered number is 158, so the per-stratum
# allocation is the LARGEST-REMAINDER apportionment of 158 over the 28 strata
# (floor(0.05 n) everywhere, then the 18 remaining seats to the largest
# fractional parts: raw's .75 before soup's .5, ties by stratum index).  Within
# a stratum the seeds are EVENLY SPACED across the k-block, `k_lo + (j*n)//m`.
# Any deterministic subset is unbiased -- the seeds are independent draws keyed
# by k -- so the choice is made for spread and reproducibility, not for balance.
# --------------------------------------------------------------------------- #
B9_TOTAL = 158


def b9_alloc():
    base = {s["i"]: int(0.05 * s["n"]) for s in STRATA}
    frac = {s["i"]: 0.05 * s["n"] - base[s["i"]] for s in STRATA}
    left = B9_TOTAL - sum(base.values())
    for i in sorted(frac, key=lambda x: (-frac[x], x))[:left]:
        base[i] += 1
    assert sum(base.values()) == B9_TOTAL
    return base


def b9_seeds():
    alloc = b9_alloc()
    out = []
    for st in STRATA:
        m, n = alloc[st["i"]], st["n"]
        for j in range(m):
            out.append({"i": st["i"], "k": st["k_lo"] + (j * n) // m})
    assert len(out) == B9_TOTAL
    assert len({(o["i"], o["k"]) for o in out}) == B9_TOTAL
    return out


# --------------------------------------------------------------------------- #
# board primitives
# --------------------------------------------------------------------------- #
def div_guard(tag, rec=None):
    """s13_board.div_guard's contract: PIN the divider, then ask the TRANSPORT
    what it commanded and record the answer.  UNPINNED is a rig-integrity
    FINDING -- recorded, not smoothed (21.1 / 22.6)."""
    img, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    v30run.run_image(bytes(img), HOST, tag="wr1div", waits=0, use_core=False,
                     div=v30run.DIV_OF_RECORD)
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if ("UNPINNED" not in str(rb)
                         and "UNKNOWN" not in str(rb)) else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "(21.1) ***", flush=True)
    d = {"tag": tag, "readback": str(rb), "state": state,
         "rig": getattr(r, "rig_readback", None),
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if rec is not None:
        rec.append(d)
    return d


def board_idle():
    """Leave the socketed chip selected and the rig quiet."""
    img, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img, HOST, use_core=False)


def _ssh(cmd, timeout=30):
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=10", HOST, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #
def cmd_preflight(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "W1 preflight", "cid": CID, "host": HOST,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": []}
    ok = True

    # ---- 1. SINGLE WRITER.  Asked of the board, not assumed. --------------
    print("== single-writer / reachability")
    rc, up, err = _ssh("uptime")
    rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
    print(f"  uptime: {rec['uptime']}")
    if rc != 0:
        print("  BOARD UNREACHABLE -- stop")
        rec["single_writer"] = "UNKNOWN (unreachable)"
        (OUT / "w1_preflight.json").write_text(json.dumps(rec, indent=1))
        return 2
    rc, ps, _ = _ssh("ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    others = [l for l in ps.splitlines() if l.strip()]
    rec["board_procs"] = others
    if others:
        ok = False
        print(f"  *** SINGLE-WRITER VIOLATION: {len(others)} v30/serve "
              f"process(es) on the board ***")
        for l in others:
            print(f"    {l}")
        rec["single_writer"] = "VIOLATED"
    else:
        print("  no v30/serve process on the board -> SINGLE WRITER")
        rec["single_writer"] = "OK"
    # `[v]` so the probe cannot match its own command line -- the
    # self-matching-pgrep lesson (task #29 P7), applied to a liveness check
    # rather than to a watcher.
    lp = subprocess.run(["bash", "-lc",
                         "pgrep -af '[v]30ctl.py serve' || true"],
                        capture_output=True, text=True).stdout.strip()
    rec["local_serve_procs"] = [l for l in lp.splitlines() if l.strip()]
    if rec["local_serve_procs"]:
        ok = False
        print(f"  *** local serve client(s) already running: "
              f"{rec['local_serve_procs']} ***")

    # ---- 2. THE ERA, and the flash pin the campaign will refuse without ----
    print("== era / flash pin")
    flash = fzc._last_flash_entry()
    rec["flash_log_tail"] = flash
    man_path = CDIR / "manifest.json"
    if not man_path.exists():
        print(f"  no manifest for {CID} -- run `fuzz_campaign.py new {CID}`")
        rec["manifest"] = None
        ok = False
    else:
        man = json.loads(man_path.read_text())
        era = fzc.era_of(man)
        rec["manifest_flash_pin"] = man.get("flash_pin")
        rec["era"] = era
        print(json.dumps(era, indent=1))
        if (flash or {}).get("sha256") != (man.get("flash_pin") or {}).get("sha256"):
            ok = False
            print("  *** flash pin MISMATCH against flash_log tail ***")
        for k in ("sof_sha256", "gen_git", "rig_evt_hold_bits"):
            if era.get(k) in (None, ""):
                ok = False
                print(f"  *** era field ABSENT: {k} ***")
        if not era["rtl"]["inputs_sha256"]:
            ok = False
            print("  *** no quartus receipt carries the pinned .sof -- the RTL "
                  "input-manifest hash is ABSENT (B-2) ***")

    # ---- 3. GENERATION, REGENERATED, before board time is spent ------------
    print(f"== generation / regeneration sample ({a.sample} per stratum)")
    hits = 0
    per = []
    for st in STRATA:
        ov = ov_of(st)
        step = max(1, st["n"] // a.sample)
        ks = [st["k_lo"] + j for j in range(0, st["n"], step)][:a.sample]
        npair = 0
        vecs = set()
        for k in ks:
            cfg = fzc.derive_case(CID, k, ov)
            img, _ = fzc.compose_case(fzc.build(cfg), cfg)
            sha = hashlib.sha256(bytes(img)).hexdigest()
            cfg2 = fzc.derive_case(CID, k, ov)
            img2, _ = fzc.compose_case(fzc.build(cfg2), cfg2)
            if sha != hashlib.sha256(bytes(img2)).hexdigest():
                hits += 1
                print(f"  GEN_DRIFT {label(st)}/{k}")
            npair += fzc.no_brkem_pairs(img)
            if cfg["evt"] is not None:
                hits += 1
                print(f"  EVT PRESENT {label(st)}/{k}")
            if cfg["tier"] != st["tier"]:
                hits += 1
                print(f"  TIER WRONG {label(st)}/{k}")
            v = fzc.wvec_of(cfg)
            if st["src"].startswith("wvec-"):
                if v is None or len(v) != wv.NWVEC or \
                        not all(0 <= x <= 31 for x in v) or \
                        cfg["wvec"]["shape"] != st["src"][5:]:
                    hits += 1
                    print(f"  WVEC BAD {label(st)}/{k}")
                else:
                    vecs.add(wv.sha256_of(v))
            elif v is not None:
                hits += 1
                print(f"  WVEC UNEXPECTED {label(st)}/{k}")
            w = cfg["waits"]
            if st["src"].startswith("fix") and \
                    (w["wrand"] or w["fixed"] != int(st["src"][3:])):
                hits += 1
                print(f"  WAITS WRONG {label(st)}/{k}: {w}")
            if st["src"].startswith("wrand") and \
                    (not w["wrand"] or w["wmax"] != int(st["src"][5:])):
                hits += 1
                print(f"  WAITS WRONG {label(st)}/{k}: {w}")
        per.append({"i": st["i"], "stratum": label(st), "sampled": len(ks),
                    "brkem_pairs": npair, "distinct_vectors": len(vecs)})
        if npair:
            hits += 1
            print(f"  BRKEM PAIRS {label(st)}: {npair}")
    rec["regen_sample"] = {"per_stratum": per, "hits": hits,
                           "seeds": sum(p["sampled"] for p in per)}
    print(f"  {rec['regen_sample']['seeds']} seeds, hits={hits}")
    ok = ok and hits == 0

    # ---- 4. THE BOARD ITSELF: div_guard + the boot A/B health leg ----------
    if a.board:
        print("== board health")
        div_guard("preflight", rec["div_guards"])
        r = subprocess.run([sys.executable, str(SW / "check_ab_hw.py"), "all",
                            "187", "--host", HOST],
                           capture_output=True, text=True, timeout=300)
        tail = (r.stdout + r.stderr).strip().splitlines()
        rec["check_ab_hw"] = {"rc": r.returncode, "tail": tail[-12:]}
        for l in tail[-12:]:
            print(f"  {l}")
        if r.returncode != 0:
            ok = False
            print("  *** check_ab_hw FAILED ***")
        div_guard("preflight-end", rec["div_guards"])
        board_idle()
        print("  board left use_core=0 (board_idle)")

    rec["verdict"] = "OK" if ok else "BLOCKED"
    (OUT / "w1_preflight.json").write_text(json.dumps(rec, indent=1))
    print(f"\nW1 PREFLIGHT: {rec['verdict']}  -> {OUT/'w1_preflight.json'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def _done_ks():
    p = CDIR / "results.jsonl"
    if not p.exists():
        return set()
    out = set()
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.add(json.loads(line)["k"])
                except Exception:                       # noqa: BLE001
                    pass
    return out


def _run_args(st, start, n, host):
    a = argparse.Namespace(
        cid=CID, host=host, session_seeds=n, start=start, tb_only=False,
        jobs=1, stop_after=0, measure=0, allow_stale=False,
        force_tier=st["tier"], contained=False, w0=False,
        force_fixed=None, no_evt=True, strict=False, fence=False,
        no_brkem=False, brkem_high=False, mainline=False, survey=True,
        force_evt=False, force_wrand=None, wvec_shapes=None, no8080=True,
        done_dist=None)
    src = st["src"]
    if src.startswith("fix"):
        a.force_fixed = int(src[3:])
    elif src.startswith("wrand"):
        a.force_wrand = src[5:]
    elif src.startswith("wvec-"):
        a.wvec_shapes = src[5:]
    return a


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec_path = OUT / "w1_capture.json"
    rec = {"stage": "W1 capture", "cid": CID, "host": a.host,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "strata": [], "div_guards": []}
    done = _done_ks()
    t_all = time.time()
    halted = None
    for st in STRATA:
        ks = [st["k_lo"] + j for j in range(st["n"])]
        missing = [k for k in ks if k not in done]
        if not missing:
            print(f"== {st['i']:>2} {label(st):<16} already complete, skipped")
            rec["strata"].append({"i": st["i"], "stratum": label(st),
                                  "n": st["n"], "written": st["n"],
                                  "seconds": 0.0, "skipped": True})
            continue
        start, n = missing[0], missing[-1] - missing[0] + 1
        print(f"\n== {st['i']:>2} {label(st):<16} k [{start},{start+n}) n={n}",
              flush=True)
        div_guard(f"stratum{st['i']:02d}-{label(st)}", rec["div_guards"])
        t0 = time.time()
        rc = fzc.cmd_run(_run_args(st, start, n, a.host))
        dt = time.time() - t0
        done = _done_ks()
        written = sum(1 for k in ks if k in done)
        rec["strata"].append({"i": st["i"], "stratum": label(st),
                              "k_lo": st["k_lo"], "n": st["n"],
                              "written": written, "rc": rc,
                              "seconds": round(dt, 1),
                              "rate": round(n / max(1e-6, dt), 2)})
        rec["board_seconds"] = round(time.time() - t_all, 1)
        rec_path.write_text(json.dumps(rec, indent=1))
        print(f"  {label(st)}: {written}/{st['n']} in {dt:.1f}s "
              f"({n/max(1e-6,dt):.1f}/s) rc={rc}")
        if written < st["n"] or rc != 0:
            halted = (f"stratum {st['i']} {label(st)} wrote {written}/{st['n']} "
                      f"rc={rc} -- STOPPED, not nursed")
            print(f"\n*** {halted} ***")
            break
    rec["board_seconds"] = round(time.time() - t_all, 1)
    rec["halted"] = halted
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec_path.write_text(json.dumps(rec, indent=1))
    print(f"\nW1 CAPTURE: {sum(s['written'] for s in rec['strata'])}/3150 seeds "
          f"in {rec['board_seconds']/60:.1f} min"
          f"{'  HALTED: ' + halted if halted else ''}")
    return 1 if halted else 0


# --------------------------------------------------------------------------- #
# B-9 -- the stability sub-sample
# --------------------------------------------------------------------------- #
B9_REPS = 3


def cmd_b9(a):
    OUT.mkdir(parents=True, exist_ok=True)
    bdir = CDIR / "captures" / "b9"
    bdir.mkdir(parents=True, exist_ok=True)
    seeds = b9_seeds()
    by_i = {s["i"]: s for s in STRATA}
    rec = {"stage": "W1 B-9 stability", "cid": CID, "reps": B9_REPS,
           "n_seeds": len(seeds), "alloc": {str(k): v
                                            for k, v in b9_alloc().items()},
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": [], "seeds": []}
    div_guard("b9-start", rec["div_guards"])
    t0 = time.time()
    stable = unstable = errs = 0
    for idx, s in enumerate(seeds):
        st = by_i[s["i"]]
        cfg = fzc.derive_case(CID, s["k"], ov_of(st))
        g = fzc.build(cfg)
        image, meta = fzc.compose_case(g, cfg)
        reps = []
        err = None
        for _ in range(B9_REPS):
            real, sim, e = fzc.capture_board(image, meta, cfg, a.host)
            if e:
                err = e
                break
            reps.append((real, sim))
        if err or len(reps) < B9_REPS:
            errs += 1
            rec["seeds"].append({"i": s["i"], "stratum": label(st),
                                 "k": s["k"], "error": err or "short"})
            print(f"  [{idx+1}/{len(seeds)}] {label(st)}/{s['k']} ERROR {err}")
            continue
        # THE COMPARISON: `fuzz_classify.diff_rows`' own window and column
        # policy (rows 9+), rep 1 against rep 2 and rep 3, on BOTH legs.
        cells = []
        for leg in (0, 1):
            for j in (1, 2):
                d = fc.diff_rows(reps[0][leg], reps[j][leg])
                cells.append({"leg": "chip" if leg == 0 else "fabric",
                              "rep": j + 1, "n": d.n, "bad": d.bad,
                              "flick": d.flick, "first": d.first,
                              "len": [len(reps[0][leg]), len(reps[j][leg])]})
        bad = sum(c["bad"] for c in cells)
        flick = sum(c["flick"] for c in cells)
        blob = json.dumps({"k": s["k"], "stratum": label(st),
                           "cfg_hash": cfg["cfg_hash"],
                           "image_sha256": hashlib.sha256(bytes(image)).hexdigest(),
                           "wvec_sha256": (wv.sha256_of(fzc.wvec_of(cfg))
                                           if cfg.get("wvec") else None),
                           "reps": [{"chip": r[0], "fabric": r[1]} for r in reps]})
        p = bdir / f"{st['tier']}_{s['k']}_{cfg['cfg_hash']}.json.gz"
        with gzip.open(p, "wt") as f:
            f.write(blob)
        if bad == 0:
            stable += 1
        else:
            unstable += 1
        rec["seeds"].append({"i": s["i"], "stratum": label(st), "k": s["k"],
                             "bad": bad, "flick": flick, "cells": cells,
                             "rows": p.name,
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        if (idx + 1) % 20 == 0 or bad:
            print(f"  [{idx+1}/{len(seeds)}] {label(st)}/{s['k']} bad={bad} "
                  f"flick={flick}  ({(idx+1)/(time.time()-t0):.1f} seeds/s)",
                  flush=True)
    div_guard("b9-end", rec["div_guards"])
    rec["seconds"] = round(time.time() - t0, 1)
    rec["stable"] = stable
    rec["unstable"] = unstable
    rec["errors"] = errs
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lines = []
    for p in sorted(bdir.glob("*.json.gz")):
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (bdir / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    (OUT / "w1_b9.json").write_text(json.dumps(rec, indent=1))
    print(f"\nB-9: {stable}/{len(seeds)} stable, {unstable} unstable, "
          f"{errs} errors, {rec['seconds']/60:.1f} min "
          f"({len(seeds)*B9_REPS} seed-loops)")
    return 0 if (unstable == 0 and errs == 0) else 1


# --------------------------------------------------------------------------- #
# bars
# --------------------------------------------------------------------------- #
def _lines():
    p = CDIR / "results.jsonl"
    out = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


_BY_I = {s["i"]: s for s in STRATA}


def _regen_one(args):
    k, ovkey = args
    cfg = fzc.derive_case(CID, k, ov_of(_BY_I[ovkey]))
    img, _ = fzc.compose_case(fzc.build(cfg), cfg)
    v = fzc.wvec_of(cfg)
    return (k, hashlib.sha256(bytes(img)).hexdigest(),
            fzc.no_brkem_pairs(img), wv.to_hex(v) if v else None)


def cmd_bars(a):
    from multiprocessing import Pool
    OUT.mkdir(parents=True, exist_ok=True)
    lines = _lines()
    by_k = {r["k"]: r for r in lines}
    i_of = {}
    for st in STRATA:
        for j in range(st["n"]):
            i_of[st["k_lo"] + j] = st["i"]
    rec = {"stage": "W1 bars", "cid": CID, "n_lines": len(lines),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "bars": {}}

    # ---- the per-stratum roll-up (counts only; W2 owns the rates) ----------
    per = []
    for st in STRATA:
        ks = [st["k_lo"] + j for j in range(st["n"])]
        got = [by_k[k] for k in ks if k in by_k]
        vd = Counter(r["verdict"] for r in got)
        per.append({"i": st["i"], "stratum": label(st), "k_lo": st["k_lo"],
                    "n": st["n"], "captured": len(got), "verdicts": dict(vd)})
    rec["per_stratum"] = per
    rec["captured"] = sum(p["captured"] for p in per)
    rec["verdicts"] = dict(Counter(r["verdict"] for r in lines))

    # ---- B-4 / B-6: regeneration + BRKEM, over the WHOLE corpus ------------
    print("== B-4 / B-6: regenerating every image")
    t0 = time.time()
    drift = regen_err = pairs = vec_mismatch = 0
    with Pool(a.jobs) as pool:
        for k, sha, npair, vhex in pool.imap_unordered(
                _regen_one, [(k, i_of[k]) for k in sorted(by_k)], chunksize=16):
            r = by_k[k]
            if sha != r["image_sha256"]:
                drift += 1
                print(f"  GEN_DRIFT k={k}")
            pairs += npair
            if (r.get("wvec_hex") or None) != vhex:
                vec_mismatch += 1
                print(f"  WVEC RE-DERIVE MISMATCH k={k}")
    print(f"  {len(by_k)} seeds in {time.time()-t0:.1f}s")
    rec["bars"]["B-4"] = {"statement": "no gen-drift",
                          "registered": "0 GEN_DRIFT, 0 REGEN_ERROR",
                          "measured": {"gen_drift": drift,
                                       "regen_error": regen_err,
                                       "seeds": len(by_k)},
                          "verdict": "MET" if drift == 0 and regen_err == 0
                          else "MISSED"}
    rec["bars"]["B-6"] = {"statement": "BRKEM-free by construction",
                          "registered": "0 `0F FF` pairs over the whole corpus",
                          "measured": {"pairs": pairs, "seeds": len(by_k)},
                          "verdict": "MET" if pairs == 0 else "MISSED"}

    # ---- B-3: the vector is banked IN FULL --------------------------------
    nvec = badlen = badsha = missing = 0
    for r in lines:
        if not r.get("wvec"):
            if r.get("wvec_hex"):
                missing += 1
            continue
        nvec += 1
        h = r.get("wvec_hex")
        if not h:
            missing += 1
            continue
        v = wv.from_hex(h)
        if len(v) != wv.NWVEC or r.get("wvec_n") != wv.NWVEC:
            badlen += 1
        if wv.sha256_of(v) != r.get("wvec_sha256"):
            badsha += 1
    rec["bars"]["B-3"] = {
        "statement": "the vector is banked in full",
        "registered": "0 mismatches; 0 records with a vector spec and no wvec_hex",
        "measured": {"vector_seeds": nvec, "no_hex": missing,
                     "bad_length": badlen, "bad_sha256": badsha,
                     "re_derive_mismatch": vec_mismatch},
        "verdict": "MET" if (missing + badlen + badsha + vec_mismatch) == 0
        else "MISSED"}

    # ---- B-5: the bus-cycle bound, PER CAPTURE ----------------------------
    bc = [r["bus_cycles"] for r in lines if r.get("bus_cycles") is not None]
    over = [r["k"] for r in lines
            if (r.get("bus_cycles") or 0) >= wv.NWVEC]
    rec["bars"]["B-5"] = {
        "statement": "no capture reaches 4,096 bus cycles",
        "registered": "0 seeds at or beyond 4,096",
        "measured": {"scored": len(bc), "no_bus_cycle_field": len(lines) - len(bc),
                     "max": max(bc) if bc else None,
                     "p95": sorted(bc)[int(0.95 * len(bc))] if bc else None,
                     "at_or_over": len(over), "ks": over[:20]},
        "verdict": "MET" if not over else "MISSED"}

    # ---- B-2: the era stamp -----------------------------------------------
    eras = Counter(json.dumps(r.get("era"), sort_keys=True) for r in lines)
    absent = sum(n for e, n in eras.items() if e == "null")
    incomplete = 0
    for e, n in eras.items():
        if e == "null":
            continue
        d = json.loads(e)
        if not (d.get("sof_sha256") and d.get("gen_git")
                and d.get("rig_evt_hold_bits")
                and (d.get("rtl") or {}).get("inputs_sha256")):
            incomplete += n
    stale = sum(1 for r in lines if r.get("build_stale"))
    gits = Counter(r.get("gen_git") for r in lines)
    rec["bars"]["B-2"] = {
        "statement": "era",
        "registered": "0 captures with an absent or mixed era stamp",
        "measured": {"distinct_eras": len(eras), "absent": absent,
                     "incomplete": incomplete, "build_stale": stale,
                     "gen_git": dict(gits),
                     "era": json.loads(next(iter(eras))) if len(eras) == 1
                     else "MIXED"},
        "verdict": "MET" if (len(eras) == 1 and absent == 0
                             and incomplete == 0 and stale == 0) else "MISSED"}

    # ---- B-1: THE VECTOR WAS APPLIED, on the socket leg, off banked rows ---
    print("== B-1: applied_score over every retained capture")
    m_tot = n_tot = 0
    ncap = nbad = 0
    worst = []
    for p in sorted((CDIR / "captures").glob("*.json.gz")):
        e = json.loads(gzip.decompress(p.read_bytes()))
        ln = e.get("line") or {}
        if not ln.get("wvec_hex"):
            continue
        v = wv.from_hex(ln["wvec_hex"])
        if wv.sha256_of(v) != ln.get("wvec_sha256"):
            nbad += 1
            continue
        m, n, fb = wv.applied_score(e["real"], v)
        m_tot += m
        n_tot += n
        ncap += 1
        if fb is not None:
            worst.append({"k": ln["k"], "first_bad": fb, "m": m, "n": n})
    pct = (100.0 * m_tot / n_tot) if n_tot else None
    rec["bars"]["B-1"] = {
        "statement": "the vector was applied (socket leg)",
        "registered": ">= 99.9 % (expectation 100.0 %; anything below 100.0 % "
                      "is a FINDING)",
        "measured": {"matched": m_tot, "cycles": n_tot,
                     "pct": None if pct is None else round(pct, 4),
                     "captures": ncap, "sha_mismatch": nbad,
                     "captures_with_a_miss": len(worst), "examples": worst[:10]},
        "verdict": ("MET" if (pct is not None and pct >= 99.9) else "MISSED"),
        "finding": (None if pct == 100.0 else
                    f"applied rate {pct} % is below the 100.0 % expectation")}

    # ---- B-7 / B-8: board discipline + transport ---------------------------
    guards = []
    for f in ("w1_preflight.json", "w1_capture.json", "w1_b9.json",
              "w1_idle.json"):
        p = OUT / f
        if p.exists():
            guards += json.loads(p.read_text()).get("div_guards", [])
    unpinned = [g for g in guards if g["state"] != "PINNED"]
    quar = sum(1 for r in lines if r["verdict"] == fc.QUARANTINE)
    # `_quarantine("run_error", ...)` puts the reason in `sub`, NOT in
    # `alarms` -- only `provenance_alarm` reaches `alarms`.  Counting alarms
    # would report 0 transport errors however many there were.
    runerr = sum(1 for r in lines
                 if str(r.get("sub") or "").startswith("run_error"))
    prov = sum(1 for r in lines
               if "provenance_alarm" in (r.get("alarms") or []))
    b9 = json.loads((OUT / "w1_b9.json").read_text()) \
        if (OUT / "w1_b9.json").exists() else {}
    cap = json.loads((OUT / "w1_capture.json").read_text()) \
        if (OUT / "w1_capture.json").exists() else {}
    rec["bars"]["B-7"] = {
        "statement": "board discipline",
        "registered": "div_guard PINNED on 100 % of probes; 0 unpinned readbacks",
        "measured": {"div_guards": len(guards), "unpinned": len(unpinned),
                     "unpinned_detail": unpinned,
                     "use_core_left": "0 (fuzz_campaign post-session leg + "
                                      "board_idle)"},
        "verdict": "MET" if (guards and not unpinned) else "MISSED"}
    rec["bars"]["B-8"] = {
        "statement": "transport",
        "registered": "circuit breaker not tripped; error count REPORTED, "
                      "not barred",
        "measured": {"quarantines": quar, "run_error_lines": runerr,
                     "provenance_alarms": prov, "b9_errors": b9.get("errors"),
                     "consecutive_quarantine_break_at": quar_break(lines),
                     "halted": cap.get("halted")},
        "verdict": "MET" if (not cap.get("halted") and quar_break(lines) is None)
        else "MISSED"}
    rec["bars"]["B-9"] = {
        "statement": "the capture is stable",
        "registered": f"{B9_TOTAL} / {B9_TOTAL} stable",
        "measured": {"seeds": b9.get("n_seeds"), "reps": b9.get("reps"),
                     "stable": b9.get("stable"), "unstable": b9.get("unstable"),
                     "errors": b9.get("errors"),
                     "flicker_rows": sum(s.get("flick", 0)
                                         for s in b9.get("seeds", []))},
        "verdict": ("MET" if b9.get("stable") == B9_TOTAL
                    and not b9.get("unstable") and not b9.get("errors")
                    else ("MISSED" if b9 else "NOT RUN"))}

    rec["board_minutes"] = round(
        (cap.get("board_seconds", 0) + b9.get("seconds", 0)) / 60.0, 2)
    (OUT / "w1_bars.json").write_text(json.dumps(rec, indent=1))
    print(f"\n{'bar':<5} {'verdict':<8} measured")
    for b in sorted(rec["bars"]):
        d = rec["bars"][b]
        print(f"{b:<5} {d['verdict']:<8} {json.dumps(d['measured'])[:150]}")
    missed = [b for b, d in rec["bars"].items() if d["verdict"] != "MET"]
    print(f"\nW1 BARS: {len(rec['bars'])-len(missed)}/{len(rec['bars'])} MET"
          f"{'  MISSED: ' + ','.join(sorted(missed)) if missed else ''}")
    print(f"board time: {rec['board_minutes']:.2f} min "
          f"(registered bound <= 30 min)")
    return 0 if not missed else 1


def quar_break(lines):
    """The circuit breaker's own rule, re-read off the banked results: the
    first k at which 5 QUARANTINEs occurred consecutively, or None."""
    run = 0
    for r in lines:
        run = run + 1 if r["verdict"] == fc.QUARANTINE else 0
        if run >= 5:
            return r["k"]
    return None


def cmd_idle(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "W1 close", "div_guards": [],
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    div_guard("idle", rec["div_guards"])
    board_idle()
    rc, ps, _ = _ssh("ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    rec["board_procs_after"] = [l for l in ps.splitlines() if l.strip()]
    rec["use_core"] = 0
    rec["board_idle"] = "OK"
    (OUT / "w1_idle.json").write_text(json.dumps(rec, indent=1))
    print("board_idle: OK, use_core=0 left selected")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--sample", type=int, default=6)
    p.add_argument("--board", action="store_true",
                   help="also contact the board (div_guard + check_ab_hw)")
    p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("capture")
    p.add_argument("--host", default=HOST)
    p.set_defaults(func=cmd_capture)
    p = sub.add_parser("b9")
    p.add_argument("--host", default=HOST)
    p.set_defaults(func=cmd_b9)
    p = sub.add_parser("bars")
    p.add_argument("--jobs", type=int, default=8)
    p.set_defaults(func=cmd_bars)
    p = sub.add_parser("idle")
    p.set_defaults(func=cmd_idle)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
