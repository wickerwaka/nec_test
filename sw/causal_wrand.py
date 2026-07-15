#!/usr/bin/env python3
"""causal_wrand - Phase 2b prefetch-resume causal-radius discovery.

Controlled single-wait IMPULSE experiments on the physical chip using explicit
wait-vector replay. Unlike Phase 1's LFSR-seed correlation (confounded whole
streams), here we take a reference wait-vector, flip EXACTLY ONE access's Tw at
a chosen relative offset, and measure how the chip's prefetch-resume gap moves -
a true controlled intervention.

Resume event (narrow): a completing bus cycle whose next bus cycle (after some
idle) is a CODE fetch. gap = (CODE fetch T1 row) - (completing cycle T4 row).
Classes are kept SEPARATE (not pooled):
  Rc  CODE->CODE  (queue refill)
  Rr  EU-read(MEMR)->CODE
  Rw  EU-write(MEMW)->CODE
  Ri  IO(IOR/IOW)->CODE

Anchoring is by ARCHITECTURAL ordinal (the a-th MEMR/MEMW/IO access, or the
a-th CODE fetch) so a single upstream wait cannot renumber the target. Every
perturbed run is checked against the reference bus-stream up to the anchor
(GENERATOR-DESYNC guard): if they diverge before the event, the point is
discarded, not attributed to timing.

Subcommands:
  determ   - chip determinism under a fixed explicit vector (foundational)
  impulse  - single-anchor impulse sweep (offsets 0..-K, value deltas)
  scan     - list resume events + classes for a program
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from check_seq import compose, run_chip                  # noqa: E402
from gen_seq import generate                             # noqa: E402

MEMR, MEMW, CODE, IOR, IOW, INTA = 5, 6, 4, 1, 2, 0
CLASS = {CODE: "Rc", MEMR: "Rr", MEMW: "Rw", IOR: "Ri", IOW: "Ri"}


def accesses(rows):
    """Per bus cycle: dict(bs, t1, t4, tw). t1/t4 = row indices, tw = Tw count."""
    out, cur = [], None
    for i, r in enumerate(rows):
        if r["t"] == 1:
            if cur is not None:
                out.append(cur)
            cur = dict(bs=r["bs_early"], t1=i, t4=None, tw=0)
        elif cur is not None:
            if r["t"] == 4:
                cur["tw"] += 1
            if r["t"] == 5:
                cur["t4"] = i
    if cur is not None:
        out.append(cur)
    return out


def bs_stream(acc):
    return [a["bs"] for a in acc]


def resume_events(acc):
    """All resume events: (completing_idx, class, next_code_idx, gap).
    completing cycle bs in {CODE,MEMR,MEMW,IOR,IOW}; next bus cycle is CODE."""
    out = []
    for i in range(len(acc) - 1):
        b = acc[i]["bs"]
        if b not in CLASS:
            continue
        # find the next CODE fetch
        j = None
        for k in range(i + 1, len(acc)):
            if acc[k]["bs"] == CODE:
                j = k
                break
        if j is None or acc[i]["t4"] is None:
            continue
        # narrow: the immediately-following bus cycle is the CODE fetch (no
        # intervening EU access/IO between the completing cycle and the resume)
        if j != i + 1:
            continue
        out.append((i, CLASS[b], j, acc[j]["t1"] - acc[i]["t4"]))
    return out


def data_ordinal_index(acc, kinds, ordinal):
    """bus index of the `ordinal`-th access whose bs is in `kinds`."""
    d = 0
    for i, a in enumerate(acc):
        if a["bs"] in kinds:
            if d == ordinal:
                return i
            d += 1
    return None


def run(image, host, wvec, use_core=False):
    return accesses(run_chip(image, host, use_core=use_core, wvec=wvec))


def cmd_determ(a):
    """Foundational: does the chip give a bit-identical capture for repeated
    runs of the SAME explicit vector? (Falsification #8.)"""
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    wvec = [(k * 7 + 3) % (a.wmax + 1) for k in range(4096)]   # arbitrary fixed
    base = None
    ok = True
    for t in range(a.trials):
        acc = run(image, a.host, wvec)
        sig = [(x["bs"], x["tw"], x["t1"], x["t4"]) for x in acc]
        if base is None:
            base = sig
            print(f"  trial 0: {len(acc)} bus cycles (reference)")
        else:
            same = sig == base
            ok &= same
            print(f"  trial {t}: identical={same}"
                  + ("" if same else f" (first diff @ {_firstdiff(sig, base)})"))
    print(f"determinism: {'PASS - chip is repeatable under a fixed vector' if ok else 'FAIL - chip varies!'}")
    return 0 if ok else 1


def _firstdiff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return min(len(a), len(b))


def cmd_impulse(a):
    """Impulse sweep at one architectural anchor. Reference = all-zero vector
    (w0, cycle-exact). Flip one access's Tw at offsets 0,-1,..,-K; measure the
    resume-gap change on the chip. class chosen by the anchor kind."""
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)

    refvec = [a.ref_fill] * 4096
    ref = run(image, a.host, refvec)
    refbs = bs_stream(ref)
    # anchor either by (kind, ordinal) or by an explicit reference bus index
    # (converted to its architectural class-ordinal so it survives upstream waits)
    if a.anchor_bus >= 0:
        b = ref[a.anchor_bus]["bs"]
        a.kind = {CODE: "code", MEMR: "r", MEMW: "w",
                  IOR: "io", IOW: "io"}[b]
        a.ordinal = sum(1 for k in range(a.anchor_bus)
                        if ref[k]["bs"] in _kindset(a.kind))
    kinds = _kindset(a.kind)
    P = data_ordinal_index(ref, kinds, a.ordinal)
    if P is None:
        print(f"no {a.kind} access #{a.ordinal} in fz{a.seed}")
        return 1
    # resume event at the anchor: next CODE fetch
    Q = next((k for k in range(P + 1, len(ref)) if ref[k]["bs"] == CODE), None)
    if Q is None or ref[P]["t4"] is None:
        print("anchor has no following CODE fetch / no T4")
        return 1
    cls = CLASS[ref[P]["bs"]]
    gap0 = ref[Q]["t1"] - ref[P]["t4"]
    print(f"fz{a.seed} anchor: {a.kind}#{a.ordinal} @bus{P} (class {cls}), "
          f"resume CODE @bus{Q}, reference gap0={gap0} clk "
          f"(uniform-{a.ref_fill} vector)")
    print(f"impulse response (one access {a.ref_fill}->{a.ref_fill + a.dto}):")
    K = a.k
    causal = []
    for off in range(0, -K - 1, -1):
        idx = P + off
        if idx < 0:
            continue
        wv = list(refvec)
        wv[idx] = a.ref_fill + a.dto            # single perturbation
        acc = run(image, a.host, wv)
        abs_ = bs_stream(acc)
        # desync guard: bus stream must match the reference up to the event
        Pp = data_ordinal_index(acc, kinds, a.ordinal)
        if Pp is None:
            print(f"  off {off:+d}: DESYNC (anchor vanished)")
            continue
        Qp = next((k for k in range(Pp + 1, len(acc)) if acc[k]["bs"] == CODE), None)
        if Qp is None or acc[Pp]["t4"] is None:
            print(f"  off {off:+d}: no resume")
            continue
        if abs_[:Qp + 1] != refbs[:Q + 1]:
            fd = _firstdiff(abs_[:Qp + 1], refbs[:Q + 1])
            print(f"  off {off:+d}: DESYNC (bus stream diverges @bus{fd} before event) - skip")
            continue
        gap = acc[Qp]["t1"] - acc[Pp]["t4"]
        d = gap - gap0
        mark = "  <-- CAUSAL" if d != 0 else ""
        if d != 0:
            causal.append(off)
        print(f"  off {off:+d} (bus{idx}): gap={gap} delta={d:+d}{mark}")
    if causal:
        K_meas = -min(causal)
        print(f"=> causal offsets {sorted(causal)}; measured causal radius "
              f"K = {K_meas} (class {cls})")
    else:
        print(f"=> NO causal offset within K={K} (gap insensitive to single "
              f"upstream wait here)")
    return 0


def cmd_ownwait(a):
    """Sweep the completing access's OWN wait N=0..maxn; report the resume gap
    (T4->CODE-T1, confounded by T4 shifting) AND the resume position relative
    to the FIXED access T1 (CODE-T1 - access-T1). The latter is the true
    scheduling response (additive / saturating / phase). w0 reference."""
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    ref = run(image, a.host, [0] * 4096)
    refbs = bs_stream(ref)
    b = ref[a.anchor_bus]["bs"]
    kind = {CODE: "code", MEMR: "r", MEMW: "w", IOR: "io", IOW: "io"}[b]
    ordinal = sum(1 for k in range(a.anchor_bus) if ref[k]["bs"] in _kindset(kind))
    P = data_ordinal_index(ref, _kindset(kind), ordinal)
    cls = CLASS[b]
    print(f"fz{a.seed} own-wait sweep: {kind}#{ordinal} @bus{a.anchor_bus} "
          f"(class {cls})")

    def measure(N, use_core):
        wv = [0] * 4096
        wv[P] = N
        acc = run(image, a.host, wv, use_core=use_core)
        Pp = data_ordinal_index(acc, _kindset(kind), ordinal)
        if Pp is None:
            return None
        Qp = next((k for k in range(Pp + 1, len(acc)) if acc[k]["bs"] == CODE), None)
        if Qp is None or bs_stream(acc)[:Qp + 1] != refbs[:Qp + 1]:
            return None
        return acc[Qp]["t1"] - acc[Pp]["t1"]        # resume rel. access T1

    print("  N :  chip_resume  core_resume  (CODE_T1 - access_T1)  [DIFF]")
    for N in range(0, a.maxn + 1):
        rc = measure(N, False)
        rk = measure(N, True) if a.core else None
        diff = "" if (rc is None or rk is None) else \
            ("  <-- MODEL DIVERGES" if rc != rk else "  ok")
        print(f"  {N} :     {str(rc):>5}        {str(rk):>5}{diff}")
    return 0


def _setone(vec, idx, val):
    v = list(vec)
    v[idx] = val
    return v


def _kindset(kind):
    return {"r": {MEMR}, "w": {MEMW}, "io": {IOR, IOW}, "code": {CODE}}[kind]


def cmd_pfdiff(a):
    """Localize the prefetch-issue / queue-trajectory divergence: run the same
    wait vector on chip and fabric, find the FIRST bus cycle where their
    bus-type streams differ (a prefetch issued/skipped differently), and dump
    the local context of both. This is the actual drift driver."""
    import random as _r
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    rr = _r.Random(a.wseed)
    wv = [rr.randint(0, a.wmax) for _ in range(4096)]
    chip = accesses(run_chip(image, a.host, use_core=False, wvec=wv))
    core = accesses(run_chip(image, a.host, use_core=True, wvec=wv))
    cs, ks = bs_stream(chip), bs_stream(core)
    n = min(len(cs), len(ks))
    fd = next((i for i in range(n) if cs[i] != ks[i]), None)
    BN = {CODE: "CODE", MEMR: "MEMR", MEMW: "MEMW", IOR: "IOR", IOW: "IOW",
          INTA: "INTA", 3: "HALT", 7: "PASV"}
    if fd is None:
        print(f"fz{a.seed} wseed{a.wseed} wmax{a.wmax}: bus streams identical "
              f"over {n} cycles (no divergence)")
        return 0
    print(f"fz{a.seed} wseed{a.wseed} wmax{a.wmax}: FIRST bus-stream divergence "
          f"@bus cycle {fd}")
    print(f"  bus  {'chip(bs,Tw)':>14}   {'core(bs,Tw)':>14}")
    lo, hi = max(0, fd - 6), min(n, fd + 4)
    for i in range(lo, hi):
        c, k = chip[i], core[i]
        mark = "  <-- DIVERGE" if cs[i] != ks[i] else ""
        print(f"  {i:4} {BN.get(c['bs'],c['bs']):>7},{c['tw']}      "
              f"{BN.get(k['bs'],k['bs']):>7},{k['tw']}{mark}")
    # the completing cycle before the divergence + recent wait context
    print(f"  completed cycle before divergence: chip {BN.get(chip[fd-1]['bs'])}"
          f"(Tw={chip[fd-1]['tw']}); recent Tw (bus {fd-5}..{fd-1}): "
          f"{[chip[j]['tw'] for j in range(max(0,fd-5), fd)]}")
    return 0


def cmd_scan(a):
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    acc = run(image, a.host, [0] * 4096)
    ev = resume_events(acc)
    from collections import Counter
    c = Counter(e[1] for e in ev)
    print(f"fz{a.seed}: {len(acc)} bus cycles, {len(ev)} narrow resume events; "
          f"by class {dict(c)}")
    for i, (ci, cls, j, gap) in enumerate(ev[:a.show]):
        print(f"  ev {i}: class {cls} completing @bus{ci} -> CODE @bus{j} gap={gap}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("determ")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--trials", type=int, default=4)
    p.add_argument("--wmax", type=int, default=3)
    p.set_defaults(fn=cmd_determ)
    p = sub.add_parser("impulse")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--kind", choices=("r", "w", "io", "code"), default="r")
    p.add_argument("--ordinal", type=int, default=5)
    p.add_argument("--anchor-bus", type=int, default=-1,
                   help="anchor on this reference bus index (overrides "
                        "kind/ordinal; converted to class-ordinal)")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--ref-fill", type=int, default=0,
                   help="uniform reference wait level (0 = w0 cycle-exact)")
    p.add_argument("--dto", type=int, default=1,
                   help="perturbation magnitude added to one access")
    p.set_defaults(fn=cmd_impulse)
    p = sub.add_parser("ownwait")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90007)
    p.add_argument("--anchor-bus", type=int, required=True)
    p.add_argument("--maxn", type=int, default=6)
    p.add_argument("--core", action="store_true",
                   help="also run the fabric core and flag where it diverges")
    p.set_defaults(fn=cmd_ownwait)
    p = sub.add_parser("pfdiff")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--wseed", type=int, default=1)
    p.add_argument("--wmax", type=int, default=3)
    p.set_defaults(fn=cmd_pfdiff)
    p = sub.add_parser("scan")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--show", type=int, default=20)
    p.set_defaults(fn=cmd_scan)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
