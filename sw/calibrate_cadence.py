#!/usr/bin/env python3
"""calibrate_cadence - observe-only calibration for the cadence_floor rule
(task #29, Phase 3).

Two data sources feed the empirical step/rate/skip distributions the plan
requires before the cadence-floor thresholds may be frozen:

  observe-cache : BOARD-FREE. Replays the cached w1/w3 chip refs
                  (sw/testdata/chipcache, measure.py CACHE) against a
                  current-RTL Verilator TB run at the same waits, computes the
                  cadence metrics, and reports the floor accept-rate + the
                  step/|o|/skip distributions. This is the known-floor corpus
                  the >=90% gate is measured against.

  board-wrand   : ONE bounded board session (root@mister-nec). A check_seq-style
                  hw-ab batch under seeded random waits (wmax mix), capturing the
                  socketed chip leg (cached to disk) and comparing chip-vs-TB
                  (the campaign's replay scenario). ServeRunner.ensure() force-
                  cleans the wait rig at connect; the board is left use_core=0;
                  >=5 consecutive RunErrors aborts the session (never retry into
                  a wedge).

`report` renders sw/testdata/cadence_calibration.md from the collected json.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
import fuzz_accept as fa                                # noqa: E402
from check_seq import compose, run_tb, run_chip         # noqa: E402
from gen_seq import generate                            # noqa: E402
from measure import chip_ref, CACHE                     # noqa: E402

OUT = SW / "testdata"
CACHE_JSON = OUT / "cadence_cache_metrics.json"
BOARD_JSON = OUT / "cadence_board_metrics.json"
REPORT = OUT / "cadence_calibration.md"


def _classify_pair(real_slim, sim, waits, wrand, engine):
    """real_slim = cached chip rows (dicts); sim = TB rows. Returns (verdict,
    metrics-under-provisional-thresholds, diffresult)."""
    real = [dict(r, t_state=r["t"]) if "t" in r and "t_state" not in r else r
            for r in real_slim]
    ctx = fc.Ctx(tier="A", waits=waits, wrand=wrand, real_is_chip=True)
    v = fc.classify(real, sim, ctx, engine=engine)
    dr = fc.diff_rows(real, sim)
    thr = _cad_thr(engine)
    m = fa.cadence_metrics(real, sim, dr, thr) if dr.bad > 0 else None
    return v, m, dr


def _cad_thr(engine):
    for r in engine.rules:
        if isinstance(r, fa.CadenceFloorRule):
            return r.thr
    raise SystemExit("no cadence_floor rule loaded")


def observe_cache(seeds, waits_list, engine):
    """Replay cached chip refs vs current-RTL TB; collect per-seed metrics."""
    recs = []
    for w in waits_list:
        for s in seeds:
            key = CACHE / f"s{s}_w{w}_base.json"
            if not key.exists():
                continue
            real_slim = json.loads(key.read_text())
            g = generate(s, exts=())
            image, _meta = compose(g)
            sim = run_tb(image, 4200, waits=w)
            v, m, dr = _classify_pair(real_slim, sim, w, False, engine)
            rec = {"seed": s, "w": w, "verdict": v.verdict, "sub": v.sub,
                   "bad": dr.bad, "func_mm": v.func_mismatch,
                   "first": dr.first}
            if m:
                rec.update({k: m[k] for k in
                            ("ok", "reason", "mism", "skfrac_c", "skfrac_k",
                             "maxstep", "absmax_o", "final_o", "nfetch",
                             "waited_total", "worst_rate")})
            recs.append(rec)
            print(f"  w{w} s{s}: {v.verdict}/{v.sub} bad={dr.bad}"
                  + (f" step={m['maxstep']} |o|={m['absmax_o']} "
                     f"rate={m['worst_rate']:.2f} ok={m['ok']}({m['reason']})"
                     if m else ""), flush=True)
    CACHE_JSON.write_text(json.dumps(recs, indent=1))
    _summarize("cache", recs)
    return recs


def board_wrand(seeds, wmax_list, host, engine, stop_after_err=5):
    """Bounded board session: chip leg under wrand, compared chip-vs-TB."""
    recs = []
    consec_err = 0
    from v30run import RunError
    try:
        for idx, s in enumerate(seeds):
            wmax = wmax_list[idx % len(wmax_list)]
            wseed = (0x5EED ^ s) & 0xFFFF
            wrand = (wmax, wseed)
            # budget-coupled length (task #30 re-cal): nmax_eff = nmax*4/(4+wmax)
            # keeps the done marker inside the 4096-row window under waits, so
            # the offset series is truncation-FREE (the Phase-3 contamination fix)
            nmax_eff = max(24, int(80 * 4 / (4 + wmax)))
            g = generate(s, nmin=24, nmax=nmax_eff,
                         exts=("farjmp", "farcall", "callret", "loop",
                               "shifts", "earich"))
            image, _meta = compose(g)
            try:
                ckey = CACHE / f"wr_s{s}_wm{wmax}_ws{wseed:04x}.json"
                if ckey.exists():
                    real_slim = json.loads(ckey.read_text())
                else:
                    real = run_chip(image, host, use_core=False, wrand=wrand)
                    real_slim = [{"t": r.get("t_state", r.get("t")),
                                  "bs_early": r["bs_early"], "qs": r["qs"],
                                  "ube_n": r["ube_n"], "ad_addr": r["ad_addr"],
                                  "ad_data": r["ad_data"], "ps": r["ps"]}
                                 for r in real]
                    ckey.write_text(json.dumps(real_slim))
                consec_err = 0
            except RunError as e:
                consec_err += 1
                print(f"  w-rand s{s}: RunError ({consec_err}): {e}", flush=True)
                if consec_err >= stop_after_err:
                    print(f"STOP: {consec_err} consecutive RunErrors - not "
                          f"retrying into a wedge", flush=True)
                    break
                continue
            sim = run_tb(image, 4200, wrand=wrand)
            v, m, dr = _classify_pair(real_slim, sim, 0, True, engine)
            rec = {"seed": s, "wmax": wmax, "wseed": wseed,
                   "verdict": v.verdict, "sub": v.sub, "bad": dr.bad,
                   "func_mm": v.func_mismatch, "first": dr.first}
            if m:
                rec.update({k: m[k] for k in
                            ("ok", "reason", "mism", "skfrac_c", "skfrac_k",
                             "maxstep", "absmax_o", "final_o", "nfetch",
                             "waited_total", "worst_rate")})
            recs.append(rec)
            print(f"  w-rand s{s} wm{wmax}: {v.verdict}/{v.sub} bad={dr.bad}"
                  + (f" step={m['maxstep']} |o|={m['absmax_o']} "
                     f"rate={m['worst_rate']:.2f}" if m else ""), flush=True)
    finally:
        # board etiquette: leave the socketed chip selected (use_core=0)
        try:
            run_chip(compose(generate(0, exts=()))[0], host, use_core=False)
        except Exception as e:                          # noqa: BLE001
            print(f"  (post-run use_core=0 reset note: {e})", flush=True)
    BOARD_JSON.write_text(json.dumps(recs, indent=1))
    _summarize("board-wrand", recs)
    return recs


def _floor_corpus(recs):
    """Diverged + functional-clean (not FUNCTIONAL/QUARANTINE) = known floor."""
    return [r for r in recs if r["bad"] > 0 and not r["func_mm"]
            and r["verdict"] not in ("FUNCTIONAL", "QUARANTINE")]


def _summarize(tag, recs):
    div = [r for r in recs if r["bad"] > 0]
    floor = _floor_corpus(recs)
    fm = [r for r in recs if r["func_mm"]]
    print(f"\n=== {tag}: N={len(recs)} diverged={len(div)} "
          f"func_mismatch={len(fm)} floor-corpus={len(floor)}")
    if floor:
        steps = [r["maxstep"] for r in floor if "maxstep" in r]
        omax = [r["absmax_o"] for r in floor if "absmax_o" in r]
        rate = [r["worst_rate"] for r in floor if "worst_rate" in r]
        skc = [r["skfrac_c"] for r in floor if "skfrac_c" in r]
        skk = [r["skfrac_k"] for r in floor if "skfrac_k" in r]
        accepted = [r for r in floor if r.get("ok")]
        print(f"  maxstep: {sorted(set(steps))} "
              f"(max={max(steps)} p95={_pctl(steps, .95)})")
        print(f"  |o|max: max={max(omax)} median={statistics.median(omax):.0f} "
              f"p95={_pctl(omax, .95)}")
        print(f"  worst_rate: max={max(rate):.3f} "
              f"median={statistics.median(rate):.3f} p95={_pctl(rate, .95):.3f}")
        print(f"  skip_frac chip: max={max(skc):.3f} | core: max={max(skk):.3f}")
        print(f"  FLOOR ACCEPT (provisional thr): {len(accepted)}/{len(floor)} "
              f"= {100 * len(accepted) / len(floor):.1f}%")
        rej = [(r["seed"], r["w"] if "w" in r else r.get("wmax"), r["reason"])
               for r in floor if not r.get("ok")]
        if rej:
            print(f"  rejected floor seeds: {rej[:12]}")
    if fm:
        print(f"  func_mismatch seeds: "
              f"{[(r['seed'], r['sub']) for r in fm][:12]}")


def _pctl(xs, p):
    if not xs:
        return 0
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    oc = sub.add_parser("observe-cache")
    oc.add_argument("--start", type=int, default=90000)
    oc.add_argument("--n", type=int, default=70)
    oc.add_argument("--waits", default="1,3")

    bw = sub.add_parser("board-wrand")
    bw.add_argument("--host", default="root@mister-nec")
    bw.add_argument("--start", type=int, default=91000)
    bw.add_argument("--n", type=int, default=150)
    bw.add_argument("--wmax", default="1,3,7")

    sub.add_parser("report")

    a = ap.parse_args()
    engine = fa.AcceptEngine.load()

    if a.cmd == "observe-cache":
        seeds = range(a.start, a.start + a.n)
        observe_cache(seeds, [int(x) for x in a.waits.split(",")], engine)
    elif a.cmd == "board-wrand":
        seeds = range(a.start, a.start + a.n)
        board_wrand(seeds, [int(x) for x in a.wmax.split(",")], a.host, engine)
    elif a.cmd == "report":
        write_report()
    return 0


def _reason_hist(floor):
    from collections import Counter
    c = Counter(r.get("reason") or "accepted" for r in floor)
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def write_report():
    """Assemble cadence_calibration.md from the collected json."""
    cache = json.loads(CACHE_JSON.read_text()) if CACHE_JSON.exists() else []
    board = json.loads(BOARD_JSON.read_text()) if BOARD_JSON.exists() else []
    thr = next(r.thr for r in fa.AcceptEngine.load().rules
               if isinstance(r, fa.CadenceFloorRule))
    L = ["# cadence_floor calibration (task #29 Phase 3)\n",
         "\nObserve-only calibration of the waits>=1/wrand cadence-drift floor "
         "(biu_model.md:287-536). Ground truth = the socketed chip; the floor "
         "rule accepts a waited seed as KNOWN_ACCEPTED/cadence only when it is "
         "functional/arch clean AND its chip-vs-TB fetch-offset series stays "
         "inside the frozen bounds. Generated by `sw/calibrate_cadence.py "
         "report`.\n"]

    for tag, recs, note in (
        ("Cached w1/w3 chip refs (board-free) - the GATE corpus", cache,
         "measure.py CACHE seeds 90000-90069 at w1 and w3, replayed against a "
         "current-RTL Verilator TB at the same fixed waits."),
        ("Fresh board wrand batch (root@mister-nec)", board,
         "check_seq-style chip leg under seeded random waits (wmax mix 1/3/7, "
         "exts farjmp,farcall,callret,loop,shifts,earich), chip-vs-TB.")):
        floor = _floor_corpus(recs)
        L.append(f"\n## {tag}\n\n{note}\n\n")
        if not recs:
            L.append("_no data collected_\n")
            continue
        div = [r for r in recs if r["bad"] > 0]
        fm = [r for r in recs if r["func_mm"]]
        L.append(f"- seeds: **{len(recs)}**; diverged: {len(div)}; "
                 f"functional-mismatch: {len(fm)}; floor-corpus: **{len(floor)}**\n")
        if floor:
            steps = [r["maxstep"] for r in floor]
            omax = [r["absmax_o"] for r in floor]
            rate = [r["worst_rate"] for r in floor]
            skc = [r["skfrac_c"] for r in floor]
            acc = [r for r in floor if r.get("ok")]
            from collections import Counter
            L.append(f"- max |step| distribution: "
                     f"{dict(sorted(Counter(steps).items()))}\n")
            L.append(f"- |o| peak: max {max(omax)}, "
                     f"median {statistics.median(omax):.0f}, p95 {_pctl(omax, .95)}\n")
            L.append(f"- slip/waited-fetch rate: max {max(rate):.3f}, "
                     f"median {statistics.median(rate):.3f}, "
                     f"p95 {_pctl(rate, .95):.3f}\n")
            L.append(f"- fetch-alignment skip fraction (chip): max {max(skc):.3f}\n")
            L.append(f"- reject-reason histogram: {_reason_hist(floor)}\n")
            L.append(f"- **floor accept-rate (frozen thresholds): "
                     f"{len(acc)}/{len(floor)} = "
                     f"{100 * len(acc) / len(floor):.1f}%**\n")
        if fm:
            L.append(f"- functional-mismatch seeds (all `done_mismatch`): "
                     f"{[r['seed'] for r in fm]}\n")

    L.append("\n## Findings\n\n")
    L.append(
        "1. **The fixed-w1/w3 floor is tight and clean.** 0 functional "
        "mismatches; perfect fetch alignment (skip fraction 0.000); the "
        "per-step magnitude is bimodal - a dense cluster at {0,1,2} plus a "
        "three-member odd-parity stall family at exactly {8,9,10}, ALL at w1 "
        "(odd wait count). This is the documented odd-parity 8-cycle stall. "
        "`max_step` was raised 4->9 to admit the legitimate 8/9-clock members; "
        "the single step=10 tail (seed 90042) is left to surface as TIMING "
        "(conservative top-decile outlier). Accept-rate 58/59 = 98.3%.\n\n")
    L.append(
        "2. **The wrand batch is wider AND partly contaminated.** Two "
        "distinct effects inflate the wrand rejects:\n"
        "   - *Window-truncation* (the 9 `done_mismatch`): these calibration "
        "seeds use the un-budgeted `gen_seq.generate` (nmax=100), so under "
        "wmax=7 the ~200-fetch programs run the done marker past the 4096-row "
        "capture window on one leg. This is a capture-budget artifact, NOT a "
        "functional bug - the campaign's `nmax_eff = max(nmin, nmax*4/(4+wmax))` "
        "coupling (fuzz_campaign.derive_axes) keeps done in-window and removes "
        "it. The floor rule correctly treats these as functional evidence "
        "(only the 8080 rule may cover a done_mismatch), so they never mask.\n"
        "   - *Genuinely larger drift* (the 16 `step_break`, |step| 10-18, and "
        "the seeds with slip-rate 0.25-0.48): heavier random waits produce "
        "larger single-fetch offsets than fixed w1/w3. Under the conservative "
        "frozen thresholds these surface as TIMING for manual review rather "
        "than being masked.\n"
        "   - one **genuine outlier** (seed 91101, wmax7): `code_mism` "
        "(fetch streams fail to align, step 75) - correctly rejected/surfaced, "
        "exactly what the floor must not swallow.\n\n")
    L.append(
        "3. **Decision: freeze the conservative thresholds from the clean "
        "fixed-w corpus.** The plan's #1 risk is floor over-acceptance masking "
        "real waits bugs; the wrand tail is contaminated (truncation) and its "
        "clean subset is exactly the top-decile-outlier population the plan "
        "wants surfaced, not absorbed. `max_step=9` per the odd-parity "
        "guidance; slip/rate/skip bounds unchanged (fixed-w worst rate 0.214 < "
        "0.25). **Recommended before scaling (Phase 5+): one budget-coupled "
        "wrand re-calibration** (nmax_eff seeds) to measure the truncation-free "
        "wrand floor; the step/rate bounds may then widen with clean evidence.\n")

    L.append(f"\n## Frozen thresholds (fuzz_accept_rules.json v1.0)\n\n"
             f"```json\n{json.dumps(thr, indent=2)}\n```\n")
    REPORT.write_text("".join(L))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    sys.exit(main())
