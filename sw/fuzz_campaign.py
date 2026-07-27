#!/usr/bin/env python3
"""fuzz_campaign - orchestrator for the massive fuzz expansion (task #29).

Subcommands:
  new     - snapshot axes/knobs + generator git + the pinned flash_log build
            into sw/testdata/campaigns/<CID>/manifest.json
  run     - session of --session-seeds cases: derive -> generate -> compose ->
            capture (board hw-ab chip-then-fabric, or --tb-only) -> classify
            inline -> append-only fsync'd results.jsonl; resume from the jsonl
            tail; RunError -> reconnect+retry-once -> quarantine; >=5 consecutive
            quarantines trips the circuit breaker (wedge house rule); divergent
            captures gzipped immediately; coverage every 500; EscalationPolicy
            consulted after every seed
  status  - roll up a campaign's results.jsonl
  show    - re-derive one case (bit-reproducible from cid,k)
  replay  - parallel Verilator forensics over a set of cases
  lint    - generation-only safety scan (Phase 1 gate)

Everything is reproducible from (campaign_id, k) alone: `cfg/<cid>/<k>` draws
the axes (tier, event, waits) and the program seeds off `soup|raw/<cid>/<k>`.
All derived values are recorded verbatim in each result line; the manifest pins
the generator git SHA and the flashed bitstream.

nmax_eff capture-budget coupling: nmax_eff = max(nmin, nmax*C/(C+wmax)). C is
frozen from the TB pilot done_idx distribution (see NMAX_SCALE_C below).
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import fuzz_cov                                         # noqa: E402
import optable                                          # noqa: E402
from fuzz_accept import AcceptEngine                    # noqa: E402
from fuzz_classify import Ctx, classify, EscalationPolicy  # noqa: E402
from gen_soup import gen_soup, SoupKnobs                 # noqa: E402
from gen_raw import gen_raw                              # noqa: E402
from v30run import run_image, RunError                  # noqa: E402

RESERVED_LO = 0xFF00
NMIN, NMAX = 24, 80
# Capture-budget coupling constant. C=4 == a bus cycle is ~4 clocks (T1-T4), so
# a wmax equal to C halves the instruction budget. Confirmed by the TB pilot:
# at w0 the contained-soup done_idx stayed well inside the 4096-row window with
# nmax=80 (see sw/testdata/tb_pilot_done_dist.json), so the base budget holds
# and C=4 follows from the measured rows/instruction. FROZEN 2026-07-27.
NMAX_SCALE_C = 4
SESSION_SEEDS = 5000
TB_ROWS = 4200
CAMPAIGNS = SW / "testdata" / "campaigns"
FLASH_LOG = SW / "testdata" / "flash_log.jsonl"


# ===========================================================================
# Seed -> config derivation.
# ===========================================================================
def derive_axes(cid, k):
    """Draw the per-seed axes from the `cfg/<cid>/<k>` namespace."""
    r = random.Random(f"cfg/{cid}/{k}")
    tier = "raw" if r.random() < 0.20 else "soup"

    evt = None
    if r.random() < 0.25:
        x = r.random()
        pin = 0 if x < 0.70 else (1 if x < 0.95 else 2)   # INT / NMI / POLL
        if tier == "raw" and pin == 2:
            pin = 0
        delay = int(round(8 * (2048 / 8) ** r.random()))
        evt = {"pin": pin, "delay": delay, "hold": 2}

    if r.random() < 0.50:
        wmax = r.choices([1, 2, 3, 7, 15], weights=[30, 25, 20, 15, 10])[0]
        waits = {"wrand": True, "wmax": wmax, "wseed": r.getrandbits(16),
                 "fixed": None}
        weff = wmax
    else:
        w = r.choices([0, 1, 2, 3], weights=[70, 10, 10, 10])[0]
        waits = {"wrand": False, "wmax": None, "wseed": None, "fixed": w}
        weff = w

    nmax_eff = max(NMIN, int(NMAX * NMAX_SCALE_C / (NMAX_SCALE_C + weff)))
    return {"cid": cid, "k": k, "tier": tier, "evt": evt, "waits": waits,
            "wild": None, "nmin": NMIN, "nmax_eff": nmax_eff}


def derive_case(cid, k, ov=None):
    """derive_axes + optional pilot overrides + nmax_eff recompute + cfg_hash.
    ov keys: force_tier, force_contained, w0, no_evt, force_evt, force_wrand."""
    ov = ov or {}
    ax = derive_axes(cid, k)
    if ov.get("force_tier"):
        ax["tier"] = ov["force_tier"]
    if ov.get("force_contained"):
        ax["wild"] = False
    if ov.get("w0"):
        ax["waits"] = {"wrand": False, "wmax": None, "wseed": None, "fixed": 0}
    if ov.get("no_evt"):
        ax["evt"] = None
    if ov.get("force_evt"):
        r = random.Random(f"pilotevt/{cid}/{k}")
        pin = 0 if r.random() < 0.7 else 1                 # INT / NMI mix
        ax["evt"] = {"pin": pin,
                     "delay": int(round(8 * (2048 / 8) ** r.random())),
                     "hold": 2}
    if ov.get("force_wrand"):
        r = random.Random(f"pilotwr/{cid}/{k}")
        wmax = r.choice(ov["force_wrand"])
        ax["waits"] = {"wrand": True, "wmax": wmax, "wseed": r.getrandbits(16),
                       "fixed": None}
    ax["strict"] = bool(ov.get("strict"))
    w = ax["waits"]
    weff = w["wmax"] if w["wrand"] else w["fixed"]
    ax["nmax_eff"] = max(NMIN, int(NMAX * NMAX_SCALE_C / (NMAX_SCALE_C + weff)))
    core = {kk: ax[kk] for kk in ("tier", "evt", "waits", "wild", "nmax_eff",
                                  "strict")}
    ax["cfg_hash"] = hashlib.sha1(
        json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
    return ax


def build(cfg):
    """Materialise the g-dict for a derived config."""
    seed = f"{cfg['cid']}/{cfg['k']}"
    if cfg["tier"] == "raw":
        g = gen_raw(seed)
    else:
        pin = cfg["evt"]["pin"] if cfg["evt"] else None
        # strict = contained fall-through generation: suppress the deliberate
        # no-done breadth classes (BRKEM 8080-entry, TF single-step storm, undoc
        # opcodes, random-DS window escape) so the pilot measures fall-through.
        knobs = SoupKnobs(p_brkem=0.0, p_tf=0.0, p_undoc=0.0, p_sreg_rand=0.0) \
            if cfg.get("strict") else SoupKnobs()
        g = gen_soup(seed, nmin=cfg["nmin"], nmax=cfg["nmax_eff"],
                     evt_pin=pin, wild=cfg["wild"], knobs=knobs)
    if cfg["evt"] and g.get("has_halt"):
        cfg["evt"]["hold"] = 300
    return g


def _weff(cfg):
    w = cfg["waits"]
    return w["wmax"] if w["wrand"] else w["fixed"]


# ===========================================================================
# Capture legs.
# ===========================================================================
def _evt_tuple(cfg, meta):
    if not cfg["evt"]:
        return None
    e = cfg["evt"]
    return (meta["anchor_linear"] & 0xFFFFF, e["delay"], e["hold"], e["pin"])


def capture_tb(image, meta, cfg):
    """Single Verilator TB leg (temp hygiene handled inside run_tb)."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    return check_seq.run_tb(image, TB_ROWS, waits=fixed,
                            evt=_evt_tuple(cfg, meta), wrand=wrand)


def capture_board(image, meta, cfg, host):
    """hw-ab: socketed chip (use_core=0) then fabric core (use_core=1), same
    image/evt/wrand. ensure() force-cleans the rig at connect. One reconnect +
    retry on RunError, else the caller quarantines."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evt = _evt_tuple(cfg, meta)
    for attempt in (1, 2):
        try:
            real = check_seq.run_chip(image, host, use_core=False, waits=fixed,
                                      evt=evt, wrand=wrand)
            sim = check_seq.run_chip(image, host, use_core=True, waits=fixed,
                                     evt=evt, wrand=wrand)
            return real, sim, None
        except RunError as e:
            if attempt == 2:
                return None, None, f"run_error:{e}"
    return None, None, "run_error:unreachable"


def _ctx_for(cfg, g, tb_only):
    w = cfg["waits"]
    return Ctx(tier="A" if cfg["tier"] == "soup" else "B",
               waits=0 if w["wrand"] else w["fixed"], wrand=w["wrand"],
               real_is_chip=not tb_only,
               brkem_pos=g.get("brkem_pos", []),
               has_halt=g.get("has_halt", False),
               with_drift=(w["wrand"] or (not w["wrand"] and w["fixed"] > 0)),
               cid=cfg["cid"], seed=f"{cfg['cid']}/{cfg['k']}",
               cfg_hash=cfg["cfg_hash"])


# ===========================================================================
# Result line (harmonised schema).
# ===========================================================================
def result_line(cfg, g, sha, v, di, gen_git, build_stale, ts):
    return {
        "k": cfg["k"], "seed": f"{cfg['cid']}/{cfg['k']}", "cid": cfg["cid"],
        "tier": cfg["tier"], "cfg_hash": cfg["cfg_hash"],
        "wild": g.get("wild"), "has_brkem": g.get("has_brkem", False),
        "brkem_pos": g.get("brkem_pos", []), "has_halt": g.get("has_halt", False),
        "has_tf": g.get("has_tf", False), "raw_mode": g.get("raw_mode"),
        "ivt_mode": g.get("ivt_mode"), "n_ins": g["n_ins"],
        "evt": cfg["evt"], "waits": cfg["waits"], "nmin": cfg["nmin"],
        "nmax_eff": cfg["nmax_eff"], "image_sha256": sha,
        "build_stale": build_stale, "gen_git": gen_git, "ts": ts,
        "verdict": v.verdict, "sub": v.sub, "first_bad": v.first_bad,
        "bad_rows": v.bad_rows, "flick": v.flick, "win": v.n,
        "func_mismatch": v.func_mismatch, "truncated": v.truncated,
        "done_real": v.done_real, "done_sim": v.done_sim, "done_idx": di,
        "alarms": v.alarms,
        "rule_hits": [{"rule": h.rule, "klass": h.klass, "covers": h.covers}
                      for h in v.rule_hits],
        "sig": v.sig, "sigv": v.sigv, "drift": v.drift,
    }


# ===========================================================================
# One-case evaluation (shared by sequential + parallel run and replay).
# ===========================================================================
_ENGINE = None            # per-process engine (Pool initializer / lazy)
_GEN_GIT = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AcceptEngine.load()
    return _ENGINE


def _gen_git():
    global _GEN_GIT
    if _GEN_GIT is None:
        try:
            _GEN_GIT = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                text=True).strip()
        except Exception:                               # noqa: BLE001
            _GEN_GIT = "unknown"
    return _GEN_GIT


def eval_case(cid, k, ov, tb_only, host, build_stale, keep_rows=False):
    """Derive -> build -> compose -> capture -> classify. Returns a dict with
    the result line, verdict/ctx (for escalation), done_idx, timings, coverage
    bits, and (on divergence, or keep_rows) the raw rows for the banker."""
    t = {}
    t0 = time.time()
    cfg = derive_case(cid, k, ov)
    t["derive"] = time.time() - t0
    t0 = time.time()
    g = build(cfg)
    t["build"] = time.time() - t0
    t0 = time.time()
    image, meta = check_seq.compose(g)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    t["compose"] = time.time() - t0

    t0 = time.time()
    run_error = None
    if tb_only:
        try:
            real = capture_tb(image, meta, cfg)
            sim = copy.deepcopy(real)     # TB-vs-TB: plumbing + done-in-window
        except Exception as e:            # noqa: BLE001  (run_tb RuntimeError)
            real = sim = None
            run_error = f"run_error:tb:{str(e)[:120]}"
    else:
        real, sim, run_error = capture_board(image, meta, cfg, host)
    t["capture"] = time.time() - t0

    ctx = _ctx_for(cfg, g, tb_only)
    if run_error:
        ctx.run_error = run_error
    t0 = time.time()
    v = classify(real, sim, ctx, engine=_engine())
    t["classify"] = time.time() - t0

    di = fc._done_idx(real) if real else None
    line = result_line(cfg, g, sha, v, di, _gen_git(), build_stale,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    qfill = fuzz_cov.qfill_at_dispatch(real) if real else []
    divergent = v.verdict != fc.SUCCESS
    rows = (real, sim) if (divergent or keep_rows) and real else None
    return {"k": k, "cfg_hash": cfg["cfg_hash"], "tier": cfg["tier"],
            "line": line, "verdict": v, "ctx": ctx, "di": di,
            "timeout": run_error is not None and tb_only,
            "timings": t, "qfill": qfill, "forms": g["forms"], "ins": g["ins"],
            "weff": _weff(cfg), "rows": rows}


# ===========================================================================
# run.
# ===========================================================================
def _pool_init(cid, ov, tb_only, host, build_stale):
    global _EVAL_ARGS
    _EVAL_ARGS = (cid, ov, tb_only, host, build_stale)
    _engine()


def _pool_eval(k):
    cid, ov, tb_only, host, build_stale = _EVAL_ARGS
    return eval_case(cid, k, ov, tb_only, host, build_stale)


def _append_fsync(fh, obj):
    fh.write(json.dumps(obj) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def _resume_k(results_path):
    if not results_path.exists():
        return 0
    last = -1
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    last = max(last, json.loads(line)["k"])
                except Exception:                       # noqa: BLE001
                    pass
    return last + 1


def cmd_run(a):
    cdir = CAMPAIGNS / a.cid
    manifest_path = cdir / "manifest.json"
    build_stale = False
    if not a.tb_only:
        if not manifest_path.exists():
            print(f"run: no manifest for {a.cid} - run `new {a.cid}` first")
            return 2
        manifest = json.loads(manifest_path.read_text())
        cur = _last_flash_entry()
        pin = manifest.get("flash_pin", {})
        if not cur or cur.get("sha256") != pin.get("sha256"):
            if not a.allow_stale:
                print("run: flash_log sof-sha does not match the manifest pin; "
                      "new RTL => new campaign, or pass --allow-stale")
                return 2
            build_stale = True
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "captures").mkdir(exist_ok=True)
    results_path = cdir / "results.jsonl"

    ov = {}
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    if a.contained:
        ov["force_contained"] = True
    if a.w0:
        ov["w0"] = True
    if a.no_evt:
        ov["no_evt"] = True
    if a.strict:
        ov["strict"] = True
    if a.force_evt:
        ov["force_evt"] = True
    if a.force_wrand:
        ov["force_wrand"] = [int(x) for x in a.force_wrand.split(",")]

    start = a.start if a.start is not None else _resume_k(results_path)
    end = start + a.session_seeds
    print(f"run {a.cid}: seeds [{start},{end}) tb_only={a.tb_only} "
          f"jobs={a.jobs} ov={ov}", flush=True)

    engine = _engine()
    esc = EscalationPolicy(engine.escalation)
    cov = fuzz_cov.Coverage()
    consec_q = real_div = done_ok = done_win = timeouts = 0
    stage_t = {s: [] for s in ("derive", "build", "compose", "capture", "classify")}
    done_idxs = []
    t_start = time.time()
    stopped = None

    def handle(res):
        nonlocal consec_q, real_div, done_ok, done_win, timeouts, stopped
        v = res["verdict"]
        ctx = res["ctx"]
        _append_fsync(rf, res["line"])
        cov.add_program(res["forms"], res["ins"], waits=res["weff"])
        for d in res["qfill"]:
            cov.qfill[f"q{min(d, 6)}"] += 1
        if res["di"] is not None:
            done_ok += 1
            done_idxs.append(res["di"])
            if res["di"] < TB_ROWS - 8:
                done_win += 1
        if res["timeout"]:
            timeouts += 1
        if res["rows"] is not None and v.verdict != fc.SUCCESS:
            gz = cdir / "captures" / f"{res['tier']}_{res['k']}_{res['cfg_hash']}.json.gz"
            with gzip.open(gz, "wt") as g:
                json.dump({"real": res["rows"][0], "sim": res["rows"][1],
                           "line": res["line"]}, g)
        for s, dt in res["timings"].items():
            stage_t[s].append(dt)
        if v.verdict == fc.QUARANTINE:
            consec_q += 1
        else:
            consec_q = 0
        if v.verdict in (fc.FUNCTIONAL, fc.TIMING):
            real_div += 1
        acts = esc.consult(v, ctx)
        for act, why in acts:
            if act == "STOP":
                stopped = f"escalation:{why} @k={res['k']}"
        if consec_q >= 5:
            stopped = (f"circuit_breaker:{consec_q} consecutive quarantines "
                       f"@k={res['k']} (wedge house rule)")
        if a.stop_after and real_div >= a.stop_after:
            stopped = f"stop_after:{real_div} real divergences @k={res['k']}"

    with open(results_path, "a") as rf:
        ks = range(start, end)
        if a.tb_only and a.jobs > 1:
            with Pool(a.jobs, initializer=_pool_init,
                      initargs=(a.cid, ov, True, a.host, build_stale)) as pool:
                for i, res in enumerate(pool.imap(_pool_eval, ks, chunksize=4)):
                    handle(res)
                    _progress(res, i, start, t_start, cov, cdir)
                    if stopped:
                        pool.terminate()
                        break
        else:
            for i, k in enumerate(ks):
                res = eval_case(a.cid, k, ov, a.tb_only, a.host, build_stale)
                handle(res)
                _progress(res, i, start, t_start, cov, cdir)
                if stopped:
                    break

    cov.save(cdir / "coverage.json")
    n = done_ok + (0 if a.tb_only else 0)
    processed = (res["k"] - start + 1) if 'res' in dir() else 0
    print(f"\n=== run {a.cid}: {processed} seeds in {time.time()-t_start:.1f}s"
          f"{(' STOPPED ' + stopped) if stopped else ''}")
    if a.measure:
        for s in stage_t:
            xs = sorted(stage_t[s][:a.measure])
            if xs:
                print(f"  {s:<9} p50={_pct(xs,.5)*1000:.1f}ms "
                      f"p95={_pct(xs,.95)*1000:.1f}ms")
    if a.tb_only:
        tot = processed
        print(f"  done-in-window: {done_win}/{tot} = "
              f"{100*done_win/max(1,tot):.1f}%  timeouts: {timeouts}/{tot} = "
              f"{100*timeouts/max(1,tot):.2f}%")
        if done_idxs:
            di = sorted(done_idxs)
            print(f"  done_idx: min={di[0]} median={statistics.median(di):.0f} "
                  f"p95={_pct(di,.95)} max={di[-1]}")
        if a.done_dist:
            dist = {"cid": a.cid, "n": tot, "overrides": ov,
                    "nmax_scale_c": NMAX_SCALE_C, "tb_rows": TB_ROWS,
                    "done_ok": done_ok, "done_in_window": done_win,
                    "timeouts": timeouts, "done_idx": done_idxs}
            Path(a.done_dist).write_text(json.dumps(dist))
            print(f"  wrote done_idx distribution -> {a.done_dist}")
    _verdict_rollup(results_path)
    return 1 if stopped and "circuit_breaker" in stopped else 0


def _progress(res, i, start, t_start, cov, cdir):
    if (i + 1) % 500 == 0:
        cov.save(cdir / "coverage.json")
        rate = (i + 1) / (time.time() - t_start)
        print(f"  k={res['k']} ({rate:.1f}/s) last={res['verdict'].verdict}"
              f"/{res['verdict'].sub}", flush=True)


def _pct(xs, p):
    if not xs:
        return 0
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


# ===========================================================================
# new / status / show / replay.
# ===========================================================================
def _last_flash_entry():
    if not FLASH_LOG.exists():
        return None
    last = None
    for line in FLASH_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                last = json.loads(line)
            except Exception:                           # noqa: BLE001
                pass
    return last


def cmd_new(a):
    flash = _last_flash_entry()
    if not flash or flash.get("verify") != "OK":
        print("new: no valid VERIFY=OK flash_log entry to pin - flash via "
              "sw/safe_flash.sh (or backfill an entry) first")
        return 2
    cdir = CAMPAIGNS / a.cid
    cdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "cid": a.cid,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gen_git": _gen_git(),
        "flash_pin": flash,
        "axes": {"raw_frac": 0.20, "nmin": NMIN, "nmax": NMAX,
                 "nmax_scale_c": NMAX_SCALE_C, "tb_rows": TB_ROWS,
                 "event_frac": 0.25, "wrand_frac": 0.50},
        "knobs": vars(SoupKnobs()),
        "rules_version": _engine().meta.get("version"),
        "sigv": _engine().meta.get("sigv"),
    }
    (cdir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"new: wrote {cdir/'manifest.json'} (pin sha256 "
          f"{flash['sha256'][:12]}..., gen_git {manifest['gen_git']})")
    return 0


def _verdict_rollup(results_path):
    from collections import Counter
    if not results_path.exists():
        print("  (no results yet)")
        return
    verd = Counter()
    rules = Counter()
    sigs = set()
    n = 0
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            verd[r["verdict"]] += 1
            for h in r.get("rule_hits", []):
                rules[h["klass"]] += 1
            if r.get("sig"):
                sigs.add(r["sig"])
    print(f"  verdicts ({n}): {dict(verd)}")
    if rules:
        print(f"  rule hits: {dict(rules)}")
    print(f"  distinct signatures: {len(sigs)}")


def cmd_status(a):
    results_path = CAMPAIGNS / a.cid / "results.jsonl"
    print(f"status {a.cid}: next k = {_resume_k(results_path)}")
    _verdict_rollup(results_path)
    eng = _engine()
    zero = eng.zero_hit_rules()
    if zero:
        print(f"  (zero-hit rules this load: {zero})")
    return 0


def cmd_show(a):
    ov = {}
    if a.contained:
        ov["force_contained"] = True
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    cfg = derive_case(a.cid, a.k, ov)
    g = build(cfg)
    image, meta = check_seq.compose(g)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    print(json.dumps({"cfg": {kk: cfg[kk] for kk in
                              ("tier", "evt", "waits", "wild", "nmin",
                               "nmax_eff", "cfg_hash")},
                      "n_ins": g["n_ins"], "wild": g.get("wild"),
                      "has_brkem": g.get("has_brkem"), "brkem_pos": g.get("brkem_pos"),
                      "has_halt": g.get("has_halt"), "raw_mode": g.get("raw_mode"),
                      "image_sha256": sha, "anchor": meta["anchor_linear"]},
                     indent=1))
    return 0


def _replay_one(args):
    cid, k, ov = args
    res = eval_case(cid, k, ov, tb_only=True, host=None, build_stale=False)
    v = res["verdict"]
    return (k, v.verdict, v.sub, res["di"])


def cmd_replay(a):
    ov = {"force_contained": True} if a.contained else {}
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    ks = list(range(a.start, a.start + a.n))
    jobs = min(8, max(1, (os.cpu_count() or 2) // 2), a.jobs or 8)
    print(f"replay {a.cid}: {len(ks)} cases via TB, jobs={jobs}")
    with Pool(jobs, initializer=_engine) as pool:
        for k, verdict, sub, di in pool.imap(
                _replay_one, [(a.cid, k, ov) for k in ks], chunksize=4):
            print(f"  k={k}: {verdict}/{sub} done_idx={di}")
    return 0


# ===========================================================================
# lint (Phase 1 gate, retained).
# ===========================================================================
def _lint_soup(cid, n, report_every):
    hits = comp_err = wild = brkem = halt = tf = 0
    t0 = time.time()
    for k in range(n):
        cfg = derive_case(cid, k, {"force_tier": "soup"})
        g = build(cfg)
        wild += bool(g["wild"])
        brkem += bool(g["brkem_pos"])
        halt += g["has_halt"]
        tf += g["has_tf"]
        vio = optable.scan_code(g["instr"])
        if vio:
            hits += len(vio)
            print(f"  SOUP HIT soup/{cid}/{k}: {vio[:4]}")
        off = 0
        for ins in g["ins"]:
            if optable.ilen(g["instr"], off) != len(ins):
                hits += 1
                print(f"  SOUP MALFORMED soup/{cid}/{k} @off {off}")
                break
            off += len(ins)
        try:
            check_seq.compose(g)
        except Exception as e:                          # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  SOUP COMPOSE ERR soup/{cid}/{k}: {e!r}")
        if report_every and (k + 1) % report_every == 0:
            print(f"  soup {k+1}/{n} ({(k+1)/(time.time()-t0):.0f}/s) "
                  f"hits={hits} comp_err={comp_err}", flush=True)
    print(f"soup: {n} seeds in {time.time()-t0:.1f}s | wild={wild} "
          f"brkem={brkem} halt={halt} tf={tf} | hits={hits} compose_err={comp_err}")
    return hits, comp_err


def _lint_raw(cid, n, report_every):
    hits = comp_err = whole = payload = 0
    scrub_tot = {"pair0f": 0, "halt": 0, "poll": 0}
    t0 = time.time()
    for k in range(n):
        cfg = derive_case(cid, k, {"force_tier": "raw"})
        g = build(cfg)
        whole += g["raw_mode"] == "whole"
        payload += g["raw_mode"] == "payload"
        for key in scrub_tot:
            scrub_tot[key] += g["scrubbed"][key]
        try:
            img, _m = check_seq.compose(g)
        except Exception as e:                          # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  RAW COMPOSE ERR raw/{cid}/{k}: {e!r}")
            continue
        vio = optable.scan_raw_bytes(img[:RESERVED_LO])
        if vio:
            hits += len(vio)
            print(f"  RAW HIT raw/{cid}/{k} mode={g['raw_mode']}: {vio[:4]}")
        if report_every and (k + 1) % report_every == 0:
            print(f"  raw {k+1}/{n} ({(k+1)/(time.time()-t0):.0f}/s) "
                  f"hits={hits} comp_err={comp_err}", flush=True)
    print(f"raw: {n} seeds in {time.time()-t0:.1f}s | whole={whole} "
          f"payload={payload} | scrub_totals={scrub_tot} | "
          f"hits={hits} compose_err={comp_err}")
    return hits, comp_err


def cmd_lint(a):
    print(f"fuzz lint: cid={a.cid} soup_n={a.n} raw_n={a.raw_n}")
    sh, sc = _lint_soup(a.cid, a.n, a.report_every)
    rh, rc = _lint_raw(a.cid, a.raw_n, a.report_every)
    total = sh + sc + rh + rc
    print(f"\nLINT {'PASS' if total == 0 else 'FAIL'}: "
          f"soup hits={sh} compose_err={sc}; raw hits={rh} compose_err={rc}")
    return 0 if total == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new")
    p.add_argument("cid")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("run")
    p.add_argument("cid")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--session-seeds", type=int, default=SESSION_SEEDS)
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--tb-only", action="store_true")
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--stop-after", type=int, default=0)
    p.add_argument("--measure", type=int, default=0)
    p.add_argument("--allow-stale", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.add_argument("--contained", action="store_true")
    p.add_argument("--w0", action="store_true")
    p.add_argument("--no-evt", action="store_true")
    p.add_argument("--strict", action="store_true",
                   help="strict contained fall-through generation (pilot)")
    p.add_argument("--force-evt", action="store_true")
    p.add_argument("--force-wrand", default=None, help="comma wmax list, e.g. 1,3,7")
    p.add_argument("--done-dist", default=None)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status")
    p.add_argument("cid")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("show")
    p.add_argument("cid")
    p.add_argument("k", type=int)
    p.add_argument("--contained", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("replay")
    p.add_argument("cid")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--contained", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("lint")
    p.add_argument("--cid", default="lint")
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--raw-n", type=int, default=100000)
    p.add_argument("--report-every", type=int, default=0)
    p.set_defaults(func=cmd_lint)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
