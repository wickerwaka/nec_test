#!/usr/bin/env python3
"""test_fuzz_accept - offline unit tests for the Phase-3 acceptance rules
(task #29). Board-free: captures are synthesised to drive each rule path.
Run directly: `python3 sw/test_fuzz_accept.py`.

Covers:
  * brkem_gap accept (divergence at/after the BRKEM fetch) and REJECT
    (divergence BEFORE the BRKEM fetch = a real bug the rule must refuse),
    plus the optional IVT-2xMEMR + 3xMEMW signature upgrade
  * cadence_floor accept + each reject reason (step_break / rate_break /
    skip_frac / pre_tw) on constructed offset series, and the waits<1
    precondition
  * static_seed exact + wildcard hit
  * the KNOWN_ACCEPTED-carries-a-rule-hit invariant through fuzz_classify
  * rule-hit counting / zero-hit reporting
"""
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
import fuzz_accept as fa                                # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    if not cond:
        FAILS.append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{('  ' + extra) if extra else ''}")


# --- synthetic capture builders -------------------------------------------
def _pasv():
    return {"t": 0, "bs_early": 7, "qs": 0, "ube_n": 0,
            "ad_addr": 0, "ad_data": 0, "ps": 0}


def _cycle(bs, addr, data=0, waited=False):
    """One bus cycle: T1, T2, [Tw], T3, T4 - the fetch/txn primitive."""
    rows = [{"t": 1, "bs_early": bs, "qs": 1, "ube_n": 0, "ad_addr": addr,
             "ad_data": 0, "ps": 0},
            {"t": 2, "bs_early": bs, "qs": 0, "ube_n": 0, "ad_addr": addr,
             "ad_data": data, "ps": 0}]
    if waited:
        rows.append({"t": 4, "bs_early": bs, "qs": 0, "ube_n": 0,
                     "ad_addr": addr, "ad_data": data, "ps": 0})
    rows += [{"t": 3, "bs_early": bs, "qs": 0, "ube_n": 0, "ad_addr": addr,
              "ad_data": data, "ps": 0},
             {"t": 5, "bs_early": bs, "qs": 0, "ube_n": 0, "ad_addr": addr,
              "ad_data": data, "ps": 0}]
    return rows


def _dr(first, n):
    """A DiffResult stub carrying just .first and .n (all cadence_metrics /
    brkem_gap read)."""
    rows = [fc.RowDiff(first, False, None, ["x"], False)] if first is not None else []
    return fc.DiffResult(n, rows, None)


def _fetch_cap(addrs, waited=None, gaps=None):
    """Capture of CODE fetches at `addrs`, `gaps[k]` PASV fillers before each
    (controls row spacing -> the offset series), `waited[k]` inserts a Tw."""
    waited = waited or [False] * len(addrs)
    gaps = gaps or [0] * len(addrs)
    rows = []
    for k, a in enumerate(addrs):
        rows += [_pasv()] * gaps[k]
        rows += _cycle(4, a, waited=waited[k])
    return rows


# ===========================================================================
def test_brkem():
    eng = fa.AcceptEngine.load()
    lin = 0x0510
    # a CODE fetch of the BRKEM opcode at row ~ (fetch T1 at index 10, T4 at 14)
    real = [_pasv()] * 10 + _cycle(4, lin) + [_pasv()] * 30
    ctx = fc.Ctx(tier="A", brkem_pos=[(3, lin)])
    frow = fa._brkem_fetch_row(real, len(real), lin)
    check("brkem fetch row located", frow is not None, f"(row {frow})")

    # accept: first divergence at/after the BRKEM fetch
    v = dict(covers="functional", ctx=ctx, real=real, dr=_dr(frow + 5, len(real)),
             sim=None)
    hit = eng.consider(v)
    check("brkem accept when div after fetch",
          hit is not None and hit.klass == "8080-gap", f"({hit})")

    # reject: divergence BEFORE the BRKEM fetch (a real bug)
    v2 = dict(covers="functional", ctx=ctx, real=real, dr=_dr(frow - 5, len(real)),
              sim=None)
    check("brkem REJECT when div before fetch", eng.consider(v2) is None)

    # reject: no brkem_pos at all
    v3 = dict(covers="timing", ctx=fc.Ctx(tier="A"), real=real,
              dr=_dr(20, len(real)), sim=None)
    check("brkem inert without brkem_pos", eng.consider(v3) is None)

    # signature upgrade: IVT 2xMEMR + 3xMEMW after the fetch
    real_sig = ([_pasv()] * 10 + _cycle(4, lin)
                + _cycle(5, 0x0100) + _cycle(5, 0x0102)          # IVT 2x MEMR
                + _cycle(6, 0x3EFE) + _cycle(6, 0x3EFC) + _cycle(6, 0x3EFA)
                + [_pasv()] * 10)                                 # 3x MEMW push
    frow2 = fa._brkem_fetch_row(real_sig, len(real_sig), lin)
    hit2 = eng.consider(dict(covers="functional", ctx=ctx, real=real_sig,
                             dr=_dr(frow2 + 2, len(real_sig)), sim=None))
    check("brkem signature confirmed", hit2 is not None
          and "confirmed" in hit2.reason, f"({hit2.reason if hit2 else None})")


def test_cadence():
    eng = fa.AcceptEngine.load()
    thr = next(r.thr for r in eng.rules if isinstance(r, fa.CadenceFloorRule))

    def metrics(addrs_r, addrs_s, waited_r, gaps_r, gaps_s, first, window,
                waited_s=None):
        # the SAME wait pattern drives chip and TB, so both legs carry the Tw
        # rows (identical cycle length) -> the baseline offset is 0 and the gaps
        # alone shape the offset series.
        real = _fetch_cap(addrs_r, waited_r, gaps_r)
        sim = _fetch_cap(addrs_s, waited_s if waited_s is not None else waited_r,
                         gaps_s)
        return fa.cadence_metrics(real, sim, _dr(first, window), thr), real, sim

    n = 40
    addrs = [0x500 + 2 * k for k in range(n)]
    waited = [True] * n

    # ACCEPT: a small monotone offset (one +2 stall midway); first_bad after Tw
    gaps_r = [0] * n
    gaps_r[20] = 2                       # a 2-row stall on the chip side -> step 2
    m, real, sim = metrics(addrs, addrs, waited, gaps_r, [0] * n, 300, 4000)
    ctx = fc.Ctx(tier="A", waits=1)
    hit = eng.consider(dict(covers="timing", ctx=ctx, real=real, sim=sim,
                            dr=_dr(300, 4000)))
    check("cadence accept (small step)", hit is not None and hit.klass == "cadence"
          and m["ok"], f"(step={m['maxstep']} reason={m['reason']})")

    # REJECT step_break: one 15-row stall -> a single |step| of 15 (> max_step 9)
    gaps_big = [0] * n
    gaps_big[15] = 15
    mb, real, sim = metrics(addrs, addrs, waited, gaps_big, [0] * n, 300, 4000)
    check("cadence reject step_break",
          not mb["ok"] and mb["reason"].startswith("step_break"),
          f"(step={mb['maxstep']} reason={mb['reason']})")

    # REJECT rate_break: offset climbs via legal steps but few waited fetches
    addrs2 = [0x500 + 2 * k for k in range(8)]
    waited2 = [True, True] + [False] * 6         # only 2 waited fetches
    gaps2 = [0, 4, 4, 0, 0, 0, 0, 0]             # offsets 0,4,8,... via steps 4
    mr, real, sim = metrics(addrs2, addrs2, waited2, gaps2, [0] * 8, 300, 4000,
                            waited_s=waited2)
    check("cadence reject rate_break",
          not mr["ok"] and mr["reason"].startswith("rate_break"),
          f"(reason={mr['reason']} |o|={mr['absmax_o']})")

    # REJECT skip_frac: chip carries many speculative fetches absent on core
    ra = [0x500 + 2 * k for k in range(n)]
    spec = ra[:5] + [0x9000, 0x9002, 0x9004, 0x9006] + ra[5:]   # 4 extra / ~44
    ms, real, sim = metrics(spec, ra, [True] * len(spec), [0] * len(spec),
                            [0] * n, 300, 4000)
    check("cadence reject skip_frac",
          not ms["ok"] and ms["reason"] in ("skip_frac", "code_mism"),
          f"(reason={ms['reason']} skc={ms['skfrac_c']:.3f})")

    # REJECT pre_tw: divergence before the first chip Tw
    gaps_r2 = [0] * n
    gaps_r2[30] = 2
    real = _fetch_cap(addrs, [False] * 20 + [True] * 20, gaps_r2)  # first Tw late
    sim = _fetch_cap(addrs, None, [0] * n)
    first_tw = next(i for i, r in enumerate(real) if r["t"] == 4)
    mp = fa.cadence_metrics(real, sim, _dr(first_tw - 5, 4000), thr)
    check("cadence reject pre_tw", not mp["ok"] and mp["reason"] == "pre_tw",
          f"(reason={mp['reason']})")

    # precondition: waits<1 and not wrand -> rule inert
    ctx0 = fc.Ctx(tier="A", waits=0, wrand=False)
    inert = fa.CadenceFloorRule({"thresholds": thr}).apply(
        dict(covers="timing", ctx=ctx0, real=real, sim=sim, dr=_dr(300, 4000)))
    check("cadence inert at w0/no-wrand", inert is None)


def test_static():
    rule = fa.StaticRule(
        {"A/fz9": "KNOWN_ACCEPTED: exact ledger#12",
         "deadbeef": "KNOWN_ACCEPTED: by cfg_hash"},
        [["B/", "KNOWN_ACCEPTED: raw-family wildcard"]])
    # exact by tier/seed
    h = rule.apply(dict(covers="functional",
                        ctx=fc.Ctx(tier="A", seed="fz9")))
    check("static exact tier/seed hit", h is not None and "ledger#12" in h.reason,
          f"({h})")
    # exact by cfg_hash
    h2 = rule.apply(dict(covers="timing",
                         ctx=fc.Ctx(tier="A", seed="x", cfg_hash="deadbeef")))
    check("static cfg_hash hit", h2 is not None and h2.klass == "KNOWN_ACCEPTED")
    # wildcard by tier prefix
    h3 = rule.apply(dict(covers="functional",
                         ctx=fc.Ctx(tier="B", seed="raw123")))
    check("static wildcard hit", h3 is not None and "wildcard" in h3.reason)
    # miss
    check("static miss -> None",
          rule.apply(dict(covers="functional",
                          ctx=fc.Ctx(tier="A", seed="nope"))) is None)


def test_invariant_and_counting():
    # KNOWN_ACCEPTED through the real classifier must carry a rule hit, and the
    # engine must count it (the classify assert guards the without-hit case).
    eng = fa.AcceptEngine.load()
    lin = 0x0520
    # a chip capture that reaches done, plus a TB "sim" diverging only AFTER the
    # BRKEM fetch, with brkem_pos set -> functional done_mismatch covered by 8080
    real = ([_pasv()] * 12 + _cycle(4, lin)
            + _cycle(2, 0x00FC, data=fc.DONE_SENTINEL)     # real reaches done
            + [_pasv()] * 20)
    sim = [_pasv()] * 12 + _cycle(4, lin) + [_pasv()] * 20   # sim: no done
    ctx = fc.Ctx(tier="A", waits=0, brkem_pos=[(2, lin)], real_is_chip=False)
    v = fc.classify(real, sim, ctx, engine=eng)
    check("brkem seed -> KNOWN_ACCEPTED", v.verdict == fc.KNOWN_ACCEPTED,
          f"({v.verdict}/{v.sub})")
    check("KNOWN_ACCEPTED carries a rule hit", len(v.rule_hits) >= 1)
    check("engine counted the brkem hit", eng.hits["brkem_gap"] >= 1,
          f"(hits={eng.hits})")
    check("zero-hit rules reported", "cadence_floor" in eng.zero_hit_rules())


def main():
    print("test_fuzz_accept:")
    test_brkem()
    test_cadence()
    test_static()
    test_invariant_and_counting()
    print(f"\n{'PASS' if not FAILS else 'FAIL'}: {len(FAILS)} failure(s)"
          + (f": {', '.join(FAILS)}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
