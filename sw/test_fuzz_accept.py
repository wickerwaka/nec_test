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


def _ob_fetch(addr, feed=True):
    """A CODE fetch whose T1 row carries open-bus feedthrough (ad_data ==
    addr & 0xFFFF) when feed=True, else a normal (non-feedthrough) fetch. The
    rule reads the T1 row's ad_data, mirroring the real captures."""
    data = (addr & 0xFFFF) if feed else ((addr + 0x100) & 0xFFFF)
    return [{"t": 1, "bs_early": 4, "qs": 1, "ube_n": 0, "ad_addr": addr,
             "ad_data": data, "ps": 0},
            {"t": 2, "bs_early": 4, "qs": 0, "ube_n": 0, "ad_addr": addr,
             "ad_data": data, "ps": 0},
            {"t": 3, "bs_early": 4, "qs": 0, "ube_n": 0, "ad_addr": addr,
             "ad_data": data, "ps": 0},
            {"t": 5, "bs_early": 4, "qs": 0, "ube_n": 0, "ad_addr": addr,
             "ad_data": data, "ps": 0}]


def test_open_bus():
    eng = fa.AcceptEngine.load()
    R = fa.OpenBusEscapeRule({"min_escape_fetches": 8, "escape_frac_min": 0.5})
    # 2 in-image fetches, then 12 out-of-image feedthrough fetches (the escape)
    real = _ob_fetch(0x0500) + _ob_fetch(0x0502)
    escape_first = len(real)                       # first out-of-image row
    for k in range(12):
        real += _ob_fetch(0x10000 + 0x2000 * k + k)
    n = len(real) + 20

    esc, n_out, fo = fa.open_bus_escape_metrics(real, n)
    check("escape metrics: 12 feedthrough / 12 out-of-image",
          len(esc) == 12 and n_out == 12, f"(feed={len(esc)} out={n_out})")
    check("first out-of-image row located", fo == escape_first, f"({fo})")

    # accept: divergence AFTER the escape point
    v = dict(covers="functional", ctx=fc.Ctx(tier="B"), real=real,
             dr=_dr(escape_first + 8, n), sim=None)
    hit = R.apply(v)
    check("open_bus accept when div after escape",
          hit is not None and hit.klass == "open_bus", f"({hit})")

    # refuse: divergence BEFORE the escape point (a real in-image bug)
    v = dict(covers="functional", ctx=fc.Ctx(tier="B"), real=real,
             dr=_dr(1, n), sim=None)
    check("open_bus REFUSES div before escape", R.apply(v) is None)

    # refuse: fewer than min_escape_fetches feedthrough fetches
    short = _ob_fetch(0x0500) + _ob_fetch(0x10000) + _ob_fetch(0x12000)
    v = dict(covers="functional", ctx=fc.Ctx(tier="B"), real=short,
             dr=_dr(len(short) + 1, len(short) + 10), sim=None)
    check("open_bus REFUSES below min_escape_fetches", R.apply(v) is None)

    # refuse: out-of-image but NOT feedthrough (a real out-of-image bug, not
    # open-bus) -> must not be masked
    nonfeed = _ob_fetch(0x0500)
    for k in range(12):
        nonfeed += _ob_fetch(0x10000 + 0x2000 * k, feed=False)
    v = dict(covers="functional", ctx=fc.Ctx(tier="B"), real=nonfeed,
             dr=_dr(len(nonfeed) + 1, len(nonfeed) + 10), sim=None)
    check("open_bus REFUSES non-feedthrough out-of-image", R.apply(v) is None)

    # refuse: soup tier (A) never triggers - soup stays in-image by construction
    v = dict(covers="functional", ctx=fc.Ctx(tier="A"), real=real,
             dr=_dr(escape_first + 8, n), sim=None)
    check("open_bus REFUSES tier A (soup)", R.apply(v) is None)

    # the engine counts the hit on the rule path
    eng.consider(dict(covers="functional", ctx=fc.Ctx(tier="B"), real=real,
                      dr=_dr(escape_first + 8, n), sim=None))
    check("engine counted the open_bus hit", eng.hits["open_bus_escape"] >= 1,
          f"(hits={eng.hits})")

    # FULL CLASSIFY PATH: fuzz-v2 T4.  These fetches are outside the v2 code
    # region, so `escaped_code_region` fires FIRST and the seed QUARANTINEs on
    # a containment alarm -- it can no longer reach the accept engine.  That is
    # the intended v2 behaviour: containment is a falsifier, not an excuse, and
    # a seed that leaves its code region is a statement about the GENERATOR.
    # (The rule itself is untouched and still applies to the v1 bank, which
    # `timed_fuzz` scores through `open_bus_escape_metrics` directly.)
    sim = real[:escape_first] + [_pasv()] * (n - escape_first)
    v = fc.classify(real, sim, fc.Ctx(tier="B", real_is_chip=True), engine=eng)
    check("escaped seed -> QUARANTINE (v2 containment falsifier)",
          v.verdict == fc.QUARANTINE
          and any(a.startswith("escaped_code_region") for a in v.alarms),
          f"({v.verdict}/{v.sub})")


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


def test_lea_mod3_raw():
    eng = fa.AcceptEngine.load()

    def prog(store_vals):
        rows = [_pasv()] * 8
        rows += _cycle(4, 0x500) + _cycle(4, 0x502) + _cycle(4, 0x504)
        for a, d in store_vals:
            rows += _cycle(6, a, d)
        return rows + [_pasv()] * 6
    # LEA mod=11 at 0x502 (dest DI=7); DI used as a pushed value AND a store addr
    # -> one store value differs; identical code stream + equal store count.
    real = prog([(0x3EFE, 0x1111), (0x60CC, 0xAAAA)])
    sim = prog([(0x3EFE, 0x2222), (0x41FC, 0xAAAA)])     # value + addr move (DI)
    n = len(real)
    # locate the LEA's T1 fetch row (2nd code fetch)
    fetches = [i for i, r in enumerate(real)
               if fc._tstate(r) == 1 and r["bs_early"] == 4]
    lea_row = fetches[1]
    ctxB = fc.Ctx(tier="B", lea_mod3_pos=[(0x502, 7)])

    # accept: identical code stream, equal store count, divergence after the LEA
    hit = eng.consider(dict(covers="functional", ctx=ctxB, real=real, sim=sim,
                            dr=_dr(lea_row + 8, n)))
    check("raw lea_mod3 accept", hit is not None and hit.klass == "lea-mod3",
          f"({hit})")

    # REJECT: unequal store COUNT (the ENTER nesting-mask class - push count moved)
    sim_cnt = prog([(0x3EFE, 0x2222)])                   # one fewer store
    check("raw lea_mod3 REJECT (store-count diff = ENTER-like)",
          eng.consider(dict(covers="functional", ctx=ctxB, real=real,
                            sim=sim_cnt, dr=_dr(lea_row + 8, len(sim_cnt)))) is None)

    # REJECT: divergent code path (escape / control-flow split)
    sim_path = prog([(0x3EFE, 0x2222), (0x60CC, 0xAAAA)])
    # mutate a code-fetch address in sim -> paths diverge
    for i, r in enumerate(sim_path):
        if fc._tstate(r) == 1 and r["bs_early"] == 4 and r["ad_addr"] == 0x504:
            sim_path[i] = dict(r, ad_addr=0x9000)
    check("raw lea_mod3 REJECT (code path diverges)",
          eng.consider(dict(covers="functional", ctx=ctxB, real=real,
                            sim=sim_path, dr=_dr(lea_row + 8, n))) is None)

    # REJECT: divergence BEFORE the LEA executes (positional)
    check("raw lea_mod3 REJECT (div before LEA)",
          eng.consider(dict(covers="functional", ctx=ctxB, real=real, sim=sim,
                            dr=_dr(lea_row - 2, n))) is None)

    # inert without lea_mod3_pos (no LEA detected in the raw payload)
    check("raw lea_mod3 inert without provenance",
          eng.consider(dict(covers="functional", ctx=fc.Ctx(tier="B"),
                            real=real, sim=sim, dr=_dr(lea_row + 8, n))) is None)


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


def _arch_cap(regvals):
    """Synthetic capture whose arch_dump yields regvals (STORE_ORDER names ->
    value): one IOW-0xFE write per STORE_ORDER name, MAGIC at its own index,
    then the done marker.  PSW is a word IN the run (fuzz-v2 D6) - the
    `MEMW @ 0xFFEC` channel is gone."""
    from fuzz_classify import STORE_ORDER, MAGIC
    rows = [_pasv()] * 4
    for name in STORE_ORDER:
        d = MAGIC if name == "MAGIC" else regvals.get(name, 0)
        rows += _cycle(2, 0x00FE, data=d)                        # IOW 0xFE
    rows += _cycle(2, 0x00FC, data=fc.DONE_SENTINEL)             # done marker
    rows += [_pasv()] * 4
    return rows


def test_lea_mod3():
    eng = fa.AcceptEngine.load()
    base = {"AW": 1, "CW": 2, "DW": 3, "BW": 4, "SP": 5, "BP": 6,
            "IX": 7, "IY": 8, "PS": 0, "PC": 9, "PSW": 0xF202,
            "SS": 0, "DS0": 0, "DS1": 0}
    real = _arch_cap(base)
    n = len(real)
    ctx = fc.Ctx(tier="A", lea_mod3_pos=[(0x0510, "IX")])

    # accept: diff confined to the LEA dest reg (IX)
    sim = _arch_cap({**base, "IX": 0x1234})
    v = dict(covers="functional", ctx=ctx, real=real, sim=sim,
             dr=_dr(50, n))
    hit = eng.consider(v)
    check("lea_mod3 accept (diff = dest reg)",
          hit is not None and hit.klass == "lea-mod3", f"({hit})")

    # REJECT (strictness): a second reg (CW) also differs -> refuse -> surface
    sim2 = _arch_cap({**base, "IX": 0x1234, "CW": 0x99})
    check("lea_mod3 REJECT (extra reg differs)",
          eng.consider(dict(covers="functional", ctx=ctx, real=real, sim=sim2,
                            dr=_dr(50, n))) is None)

    # inert without lea_mod3_pos
    check("lea_mod3 inert without provenance",
          eng.consider(dict(covers="functional", ctx=fc.Ctx(tier="A"),
                            real=real, sim=sim, dr=_dr(50, n))) is None)

    # no accept when nothing differs (clean -> not this rule's job)
    check("lea_mod3 no-op on identical dumps",
          eng.consider(dict(covers="functional", ctx=ctx, real=real,
                            sim=_arch_cap(base), dr=_dr(50, n))) is None)


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
    lin = 0x8520          # inside the v2 code region: no containment alarm
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
    test_open_bus()
    test_lea_mod3_raw()
    test_brkem()
    test_cadence()
    test_lea_mod3()
    test_static()
    test_invariant_and_counting()
    print(f"\n{'PASS' if not FAILS else 'FAIL'}: {len(FAILS)} failure(s)"
          + (f": {', '.join(FAILS)}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
