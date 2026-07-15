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
    """Per bus cycle: dict(bs, t1, t4, tw, addr, data, npops). t1/t4 = row
    indices, tw = Tw count, addr = T1 address, data = data-phase word, npops =
    queue F-pops (QS==1) seen during the cycle (a coarse consumption signal)."""
    out, cur = [], None
    for i, r in enumerate(rows):
        if r["t"] == 1:
            if cur is not None:
                out.append(cur)
            cur = dict(bs=r["bs_early"], t1=i, t4=None, tw=0,
                       addr=r["ad_addr"], data=None, npops=0)
        elif cur is not None:
            if r["t"] == 4:
                cur["tw"] += 1
            if r["t"] in (2, 3):
                cur["data"] = r["ad_data"]
            if r["t"] == 5:
                cur["t4"] = i
        if cur is not None and r.get("qs") == 1:
            cur["npops"] += 1
    if cur is not None:
        out.append(cur)
    return out


def bs_stream(acc):
    return [a["bs"] for a in acc]


def build_cycles(rows):
    """Bus cycles annotated with an EXACT-as-possible reconstructed prefetch
    queue occupancy ENTERING each cycle (occ_in). Queue model: a completed CODE
    fetch adds its width (address-parity aware: even=2 bytes, odd=1 byte); each
    QS F/S pop removes 1 byte; QS E flushes to 0. Occupancy is sampled at each
    cycle's T1 (before that cycle's own fetch completes)."""
    cyc = accesses(rows)
    # walk rows to get running depth; record depth at each T1 row index
    depth = 0
    depth_at_row = {}
    # map row index -> is a CODE-fetch T4 completion + its width
    # precompute per-cycle completion info
    comp = {}     # t4_row -> width
    for a in cyc:
        if a["bs"] == CODE and a["t4"] is not None:
            comp[a["t4"]] = 1 if (a["addr"] & 1) else 2
    for i, r in enumerate(rows):
        depth_at_row[i] = depth            # depth ENTERING this row
        # apply this row's events (order: pops then completion)
        q = r.get("qs")
        if q == 1 or q == 3:               # F or S: one byte consumed
            depth = max(0, depth - 1)
        elif q == 2:                       # E: flush
            depth = 0
        if i in comp:                      # a CODE fetch completed at this row
            depth = min(depth + comp[i], 6)   # V30 6-byte queue cap
    for a in cyc:
        a["occ_in"] = depth_at_row.get(a["t1"], 0)
        a["width"] = 1 if (a["addr"] & 1) else 2
    return cyc


def arch_id(cyc, i):
    """Architectural fingerprint of the CODE->EU anchor at bus index i:
    (anchor CODE fetch addr, EU access bs, EU access addr). Invariant to waits
    (addresses don't move), so it identifies the SAME semantic event across
    backgrounds - unlike a bus index."""
    if i + 1 >= len(cyc):
        return None
    return (cyc[i]["addr"], cyc[i + 1]["bs"], cyc[i + 1]["addr"])


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

    if a.bg == "zero":
        refvec = [a.ref_fill] * 4096
    else:
        import random as _r
        rr = _r.Random(a.bgseed)
        refvec = [rr.randint(0, a.ref_fill or 3) for _ in range(4096)]
    ref = run(image, a.host, refvec)
    refbs = bs_stream(ref)
    if a.anchor_bus >= 0:
        b = ref[a.anchor_bus]["bs"]
        a.kind = {CODE: "code", MEMR: "r", MEMW: "w", IOR: "io", IOW: "io"}[b]
        a.ordinal = sum(1 for k in range(a.anchor_bus)
                        if ref[k]["bs"] in _kindset(a.kind))
    kinds = _kindset(a.kind)
    P = data_ordinal_index(ref, kinds, a.ordinal)
    if P is None:
        print(f"no {a.kind} access #{a.ordinal} in fz{a.seed}")
        return 1
    # IMMEDIATE-successor resume event (bug fix): the next bus cycle must be CODE
    if P + 1 >= len(ref) or ref[P + 1]["bs"] != CODE or ref[P]["t4"] is None:
        print(f"anchor bus{P} is not an immediate ->CODE resume event "
              f"(successor bs={ref[P + 1]['bs'] if P + 1 < len(ref) else 'EOF'})")
        return 1
    Q = P + 1
    cls = CLASS[ref[P]["bs"]]
    gap0 = ref[Q]["t1"] - ref[P]["t4"]
    print(f"fz{a.seed} anchor {a.kind}#{a.ordinal} @bus{P} (class {cls}), "
          f"resume CODE @bus{Q}, gap0={gap0} clk, bg={a.bg}(fill{a.ref_fill})")
    print(f"impulse: one access {a.ref_fill}->{a.ref_fill + a.dto}. "
          f"per-offset intervention matrix:")
    print(f"  off  outcome              gap  Ddecision")
    # matrix counters
    tot = dict(preserved_inert=0, preserved_gapchg=0, streamchg=0, lost=0)
    timing_causal, decision_causal = [], []
    K = a.k
    for off in range(0, -K - 1, -1):
        idx = P + off
        if idx < 0:
            continue
        wv = list(refvec)
        wv[idx] = a.ref_fill + a.dto
        acc = run(image, a.host, wv)
        Pp = data_ordinal_index(acc, kinds, a.ordinal)
        if Pp is None:
            tot["lost"] += 1
            print(f"  {off:+d}   anchor-lost")
            continue
        # DECISION outcome: is the anchor still an immediate ->CODE resume?
        imm_code = (Pp + 1 < len(acc) and acc[Pp + 1]["bs"] == CODE)
        # stream preserved up to & including the event?
        preserved = bs_stream(acc)[:Pp + 2] == refbs[:Q + 1]
        if not imm_code or not preserved:
            tot["streamchg"] += 1
            decision_causal.append(off)
            nb = acc[Pp + 1]["bs"] if Pp + 1 < len(acc) else -1
            print(f"  {off:+d}   STREAM-CHANGED       -    next={BSN.get(nb,nb)} "
                  f"(arbitration/issue altered)")
            continue
        gap = acc[Q]["t1"] - acc[Pp]["t4"] if False else acc[Pp + 1]["t1"] - acc[Pp]["t4"]
        d = gap - gap0
        if d != 0:
            tot["preserved_gapchg"] += 1
            timing_causal.append(off)
            print(f"  {off:+d}   preserved,gap-chg    {gap}   (Dgap={d:+d})")
        else:
            tot["preserved_inert"] += 1
            print(f"  {off:+d}   preserved,inert      {gap}")
    tk = -min(timing_causal) if timing_causal else None
    dk = -min(decision_causal) if decision_causal else None
    print(f"=> matrix {tot}")
    print(f"=> TIMING-K (stream-preserved gap change) = {tk}  |  "
          f"DECISION-K (arbitration/issue altered) = {dk}")
    return 0


BSN = {CODE: "CODE", MEMR: "MEMR", MEMW: "MEMW", IOR: "IOR", IOW: "IOW",
       INTA: "INTA", 3: "HALT", 7: "PASV"}


def _load_state_names():
    """Parse the EU state enum from hdl/rtl/core/v30_eu.sv so onset_state
    numbers dumped by the TB decode to names (S_EA1/S_EA2/S_RMWX/...). The enum
    is a flat `typedef enum logic [6:0] { ... } state_e;` with values assigned
    in declaration order from 0."""
    import re
    src = (SW.parent / "hdl" / "rtl" / "core" / "v30_eu.sv").read_text()
    m = re.search(r"typedef enum logic \[6:0\] \{(.*?)\} state_e;", src, re.S)
    if not m:
        return {}
    body = re.sub(r"//.*", "", m.group(1))
    names = [t.strip() for t in body.replace("\n", " ").split(",") if t.strip()]
    return {i: n for i, n in enumerate(names)}


STATE_NAMES = _load_state_names()


def _sname(n):
    return STATE_NAMES.get(n, f"S#{n}")


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


def _occ_proxy(acc, upto_bus):
    """Coarse queue occupancy (bytes) just before bus cycle upto_bus:
    2*(#CODE fetches completed) - (#F-pops), clamped >= 0."""
    t1 = acc[upto_bus]["t1"]
    fetched = sum(2 for j in range(upto_bus)
                  if acc[j]["bs"] == CODE and acc[j]["t4"] is not None)
    pops = sum(acc[j]["npops"] for j in range(upto_bus))
    return max(0, fetched - pops)


def cmd_arbsweep(a):
    """DECISIVE arbitration-state experiment. Fixed background vector; sweep the
    wait N=0..maxn on ONE anchor CODE fetch (bus index B, immediate ->EU in the
    reference). For each N record the chip's and core's decision (# CODE
    prefetches inserted between the anchor and the next EU access), the anchor
    CODE-T4 / next-EU-T1 clocks, and a queue-occupancy proxy. Truth vector +
    candidate state-encoding fit."""
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    if a.bgseed < 0:
        refvec = [0] * 4096
        bgtag = "zero"
    else:
        import random as _r
        rr = _r.Random(a.bgseed)
        refvec = [rr.randint(0, a.wmax) for _ in range(4096)]
        bgtag = f"rand({a.bgseed},wmax{a.wmax})"
    B = a.anchor_bus
    ref = run(image, a.host, refvec)
    if ref[B]["bs"] != CODE:
        print(f"bus{B} is not a CODE fetch (bs={ref[B]['bs']})"); return 1
    occ = _occ_proxy(ref, B)
    # find the next EU access after B in the reference
    euref = next((j for j in range(B + 1, len(ref))
                  if ref[j]["bs"] in (MEMR, MEMW, IOR, IOW)), None)
    print(f"fz{a.seed} arb anchor: CODE @bus{B}, bg={bgtag}, occ_proxy~{occ}B, "
          f"next EU @bus{euref} ({BSN.get(ref[euref]['bs']) if euref else '-'})")
    print(f"  N : chip[extra_pf,decision]  core[extra_pf]  chipT4  euT1  {'DIVERGE' }")

    def decision(acc):
        # # CODE fetches strictly between B and the next EU access
        eu = next((j for j in range(B + 1, len(acc))
                   if acc[j]["bs"] in (MEMR, MEMW, IOR, IOW)), None)
        if eu is None:
            return None
        extra = sum(1 for j in range(B + 1, eu) if acc[j]["bs"] == CODE)
        return extra, acc[B]["t4"], acc[eu]["t1"], acc[eu]["bs"]

    truth = []
    for N in range(0, a.maxn + 1):
        wv = list(refvec)
        wv[B] = N
        dc = decision(run(image, a.host, wv, use_core=False))
        dk = decision(run(image, a.host, wv, use_core=True))
        if dc is None or dk is None:
            print(f"  {N:2}: (no EU access)"); continue
        cext, ct4, cet1, ek = dc
        kext = dk[0]
        div = "  <-- DIVERGE" if cext != kext else ""
        truth.append((N, cext, kext))
        print(f"  {N:2}: chip extra={cext} ({'EU-next' if cext == 0 else f'{cext}xCODE-first'})"
              f"      core extra={kext}      {ct4}   {cet1}{div}")
    # candidate state-encoding fit for the CHIP decision (cext)
    print("  candidate encodings for chip decision (extra prefetch count vs N):")
    _fit_encodings(truth)
    return 0


def _fit_encodings(truth):
    """Report which simple functions of N predict the chip decision."""
    if not truth:
        print("    (no data)"); return
    Ns = [t[0] for t in truth]
    dec = [t[1] for t in truth]        # chip extra-prefetch count
    cands = {
        "N==0": [0 if n == 0 else 1 for n in Ns],
        "N>=1": [1 if n >= 1 else 0 for n in Ns],
        "parity N%2": [n % 2 for n in Ns],
        "phase N%4": [n % 4 for n in Ns],
        "phase N%3": [n % 3 for n in Ns],
        "sat min(N,2)": [min(n, 2) for n in Ns],
        "sat min(N,1)": [min(n, 1) for n in Ns],
    }
    # a candidate "explains" if decision is a consistent function of it
    for name, vals in cands.items():
        mp = {}
        ok = True
        for v, d in zip(vals, dec):
            if v in mp and mp[v] != d:
                ok = False; break
            mp[v] = d
        print(f"    {name:14}: {'CONSISTENT' if ok else 'inconsistent'}"
              f"{'  map=' + str(mp) if ok else ''}")


def _bg_vectors(kinds, wmax):
    """Diverse backgrounds designed to produce DISTINCT local queue states."""
    import random as _r
    out = {}
    for k in kinds:
        if k == "z":
            out["z"] = [0] * 4096
        elif k == "o":
            out["o"] = [1] * 4096
        elif k == "t":
            out["t"] = [wmax] * 4096
        elif k == "a":
            out["a"] = [0 if i % 2 else wmax for i in range(4096)]
        elif k.startswith("r"):
            rr = _r.Random(int(k[1:]))
            out[k] = [rr.randint(0, wmax) for _ in range(4096)]
    return out


def _eu_anchors(cyc):
    """Every EU access whose immediate predecessor is a CODE fetch, keyed by
    architectural EU identity (addr, bs, ordinal-among-same-addr). Returns list
    of (key, B) where B = the preceding CODE's bus index and B+1 = the EU."""
    seen = {}
    out = []
    for i in range(1, len(cyc)):
        if cyc[i]["bs"] in (MEMR, MEMW, IOR, IOW):
            k0 = (cyc[i]["addr"], cyc[i]["bs"])
            seen[k0] = seen.get(k0, 0) + 1
            if cyc[i - 1]["bs"] == CODE:
                out.append(((cyc[i]["addr"], cyc[i]["bs"], seen[k0]), i - 1))
    return out


def cmd_arbpop(a):
    """UNIQUE-architectural-anchor N* population (Phase 2d #1,#2,#5). Anchor =
    an EU access (keyed by addr+bs+ordinal, stable across backgrounds) whose
    predecessor is a CODE fetch B. Sweep B's wait N; decision = # CODE
    prefetches between B and the EU (fixed-B count, valid since only wv[B]
    changes). Dedup by EU identity; report N* over UNIQUE anchors, occupancy
    spread, invariant vs variant, and N* vs (occ_in, EU-type)."""
    from collections import defaultdict, Counter
    bgs = _bg_vectors(a.bgs, a.wmax)
    pop = defaultdict(list)     # eu-key -> [(bg, N*, occ_in, eu_bs, dec)]
    obs = 0
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for bgname, refvec in bgs.items():
            ref = build_cycles(run_chip(image, a.host, use_core=False, wvec=refvec))
            for key0, B in _eu_anchors(ref)[:a.per]:
                key = (seed,) + key0     # Step 2: dedup within-program only
                occ0 = ref[B + 1]["occ_in"]
                eu_bs = ref[B + 1]["bs"]
                dec, kdec = [], []
                for N in range(0, a.maxn + 1):
                    wv = list(refvec); wv[B] = N
                    dec.append(_extra_pf(
                        build_cycles(run_chip(image, a.host, use_core=False, wvec=wv)), B))
                    if a.core:
                        kdec.append(_extra_pf(
                            build_cycles(run_chip(image, a.host, use_core=True, wvec=wv)), B))
                    obs += 1
                pop[key].append((bgname, _boundary(dec), occ0, eu_bs, dec,
                                 _boundary(kdec) if a.core else None))
    print(f"arbpop: {obs} chip runs, {len(pop)} UNIQUE EU-anchors")
    euname = {MEMR: "R", MEMW: "W", IOR: "IOr", IOW: "IOw"}
    variant, invariant = [], 0
    for key, recs in pop.items():
        is_var = any(len(set(x for x in r[4] if x is not None)) > 1 for r in recs)
        if is_var:
            variant.append((key, recs))
        else:
            invariant += 1
    print(f"  VARIANT unique anchors: {len(variant)} | INVARIANT: {invariant}")
    # N* population over UNIQUE variant anchors (min boundary across bg)
    nstar_pop = []
    for key, recs in variant:
        ns = [r[1] for r in recs if r[1] is not None]
        if ns:
            nstar_pop.append(min(ns))
    print(f"  N* over UNIQUE variant anchors: {dict(sorted(Counter(nstar_pop).items()))}")
    print("  per-variant-anchor (EU@addr | N*/bg | occ_in/bg):")
    for key, recs in variant[:26]:
        ns = [r[1] for r in recs]
        occs = [r[2] for r in recs]
        nstab = "STABLE" if len(set(ns)) == 1 else "VARIES/bg"
        ospread = "occ-DISTINCT" if len(set(occs)) > 1 else "occ-same"
        print(f"    fz{key[0]} {euname[key[2]]}@{key[1]:05x}#{key[3]}: N*={ns} "
              f"occ_in={occs} [{nstab},{ospread}]")
    # dissociation seed: does N* track occ_in and/or EU-type?
    print("  N* vs (EU-type, occ_in entering) over variant anchors:")
    bykey = defaultdict(list)
    for key, recs in variant:
        for rec in recs:
            bgname, nstar, occ0, eu_bs, dec = rec[:5]
            if nstar is not None:
                bykey[(eu_bs, occ0)].append(nstar)
    for (eu_bs, occ), ns in sorted(bykey.items()):
        print(f"    EU={euname[eu_bs]} occ_in={occ}: N* {sorted(set(ns))} (n={len(ns)})")
    if a.core:
        print("  CHIP vs MODEL boundary by occ_in (localizes the model bug):")
        cby, kby = defaultdict(list), defaultdict(list)
        for key, recs in pop.items():
            for bgname, nstar, occ0, eu_bs, dec, knstar in recs:
                if nstar is not None:
                    cby[occ0].append(nstar)
                if knstar is not None:
                    kby[occ0].append(knstar)
        for occ in sorted(set(cby) | set(kby)):
            import statistics as _st
            cm = _st.mean(cby[occ]) if cby[occ] else None
            km = _st.mean(kby[occ]) if kby[occ] else None
            tag = "  <-- MODEL N* HIGH" if (cm is not None and km is not None
                                            and km > cm + 0.2) else ""
            print(f"    occ_in={occ}: chip N* mean={cm:.2f} core N* mean="
                  f"{km:.2f}{tag}" if cm is not None and km is not None else
                  f"    occ_in={occ}: chip={cm} core={km}")
    return 0


def cmd_arbscan(a):
    """Broad test: is the CHIP's local arbitration (EU-next vs insert-prefetch)
    ever a function of a single CODE fetch's wait? For many CODE->EU anchors
    across programs/backgrounds, sweep the anchor CODE's wait and record whether
    the CHIP decision varies (a real arbitration boundary) vs is invariant
    (model-only artifact). Also record which N the CORE deviates at."""
    import random as _r
    chip_variant = 0
    chip_invariant = 0
    model_dev = {}          # N -> count of anchors where core deviates at that N
    boundaries = []         # chip N* per variant anchor
    anchors_tested = 0
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for bg in a.bgs:
            if bg < 0:
                refvec = [0] * 4096
            else:
                rr = _r.Random(bg)
                refvec = [rr.randint(0, a.wmax) for _ in range(4096)]
            ref = run(image, a.host, refvec)
            # CODE->EU anchors
            anchs = [B for B in range(1, len(ref) - 1)
                     if ref[B]["bs"] == CODE
                     and ref[B + 1]["bs"] in (MEMR, MEMW, IOR, IOW)]
            for B in anchs[:a.per]:
                anchors_tested += 1
                cdec = []
                for N in range(0, a.maxn + 1):
                    wv = list(refvec); wv[B] = N
                    cdec.append(_extra_pf(run(image, a.host, wv, use_core=False), B))
                cset = set(x for x in cdec if x is not None)
                cbnd = _boundary(cdec)     # first N with EU-next (extra 0)
                if len(cset) > 1:
                    chip_variant += 1
                    # only sweep the core where the chip is variant (bug hunt)
                    kdec = []
                    for N in range(0, a.maxn + 1):
                        wv = list(refvec); wv[B] = N
                        kdec.append(_extra_pf(run(image, a.host, wv, use_core=True), B))
                    kbnd = _boundary(kdec)
                    boundaries.append(cbnd)
                    tag = "" if kdec == cdec else f"  MODEL-BUG core_bnd={kbnd}"
                    print(f"  fz{seed} bg{bg} CODE@bus{B}: chip={cdec} "
                          f"chip_bnd(N*)={cbnd}{tag}")
                    for N, (c, k) in enumerate(zip(cdec, kdec)):
                        if c is not None and k is not None and c != k:
                            model_dev[N] = model_dev.get(N, 0) + 1
                else:
                    chip_invariant += 1
    import statistics as _st
    print(f"\narbscan: {anchors_tested} CODE->EU anchors "
          f"({a.maxn + 1} N-values each)")
    print(f"  CHIP-VARIANT (arbitration depends on local CODE wait): {chip_variant}")
    print(f"  CHIP-INVARIANT: {chip_invariant}")
    if boundaries:
        from collections import Counter
        print(f"  chip boundary N* distribution: {dict(sorted(Counter(boundaries).items()))} "
              f"(a FIXED phase latch would give a single value; variation => "
              f"slack/request-age coupling)")
    print(f"  model deviates from chip at N = {dict(sorted(model_dev.items()))} "
          f"(anchor-N cells; the model boundary runs high)")
    return 0


def _boundary(dec):
    """first N at which the chip commits to EU-next (extra==0) and stays."""
    for N in range(len(dec)):
        if dec[N] == 0 and all(d == 0 for d in dec[N:] if d is not None):
            return N
    return None


def _extra_pf(acc, B):
    """# CODE prefetches inserted between anchor CODE @B and the next EU access."""
    eu = next((j for j in range(B + 1, len(acc))
               if acc[j]["bs"] in (MEMR, MEMW, IOR, IOW)), None)
    if eu is None:
        return None
    return sum(1 for j in range(B + 1, eu) if acc[j]["bs"] == CODE)


def cmd_episodes(a):
    """One-vs-two-mechanisms (Phase 2d #4). Align chip vs core; cluster
    divergences into EPISODES (contiguous edit regions); classify the FIRST
    unmatched issue decision sign (core-INSERTS-CODE = over-prefetch vs
    core-OMITS-CODE = under-prefetch) and record the reconstructed queue
    occupancy + EU-type at that decision. If ONE occupancy-boundary mechanism
    explains BOTH signs, the two signs should occupy complementary occupancy
    regimes consistent with a boundary the model places wrong."""
    import difflib, random as _r
    from collections import defaultdict
    over, under, other = [], [], []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                rr = _r.Random((ws << 8) | wmax)
                wv = [rr.randint(0, wmax) for _ in range(4096)]
                c = _trunc(build_cycles(run_chip(image, a.host, use_core=False, wvec=wv)))
                k = _trunc(build_cycles(run_chip(image, a.host, use_core=True, wvec=wv)))
                cseq = [(x["bs"], x["addr"]) for x in c]
                kseq = [(x["bs"], x["addr"]) for x in k]
                sm = difflib.SequenceMatcher(a=cseq, b=kseq, autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        continue
                    # occupancy entering the divergence (chip side, before i1)
                    occ = c[i1]["occ_in"] if i1 < len(c) else None
                    # nearest EU type around the episode
                    euk = next((c[x]["bs"] for x in range(i1, min(i2 + 3, len(c)))
                                if c[x]["bs"] in (MEMR, MEMW)), None)
                    coside = [c and k[x]["bs"] for x in range(j1, j2)]
                    chside = [c[x]["bs"] for x in range(i1, i2)]
                    if tag == "insert" and CODE in [k[x]["bs"] for x in range(j1, j2)]:
                        over.append((occ, euk))
                    elif tag == "delete" and CODE in chside:
                        under.append((occ, euk))
                    elif tag == "replace":
                        kc = [k[x]["bs"] for x in range(j1, j2)]
                        if CODE in kc and CODE not in chside:
                            over.append((occ, euk))
                        elif CODE in chside and CODE not in kc:
                            under.append((occ, euk))
                        else:
                            other.append((occ, euk))
    def occhist(lst):
        h = defaultdict(int)
        for occ, _ in lst:
            if occ is not None:
                h[occ] += 1
        return dict(sorted(h.items()))
    print(f"episodes: OVER-prefetch(core inserts CODE)={len(over)}  "
          f"UNDER-prefetch(core omits CODE)={len(under)}  other={len(other)}")
    print(f"  OVER  occupancy-entering histogram: {occhist(over)}")
    print(f"  UNDER occupancy-entering histogram: {occhist(under)}")
    print("  interpretation: if the SAME queue-boundary is placed wrong by the "
          "model, OVER concentrates at LOW occ (model prefetches into room the\n"
          "  chip reserves for EU) and UNDER at HIGH occ (model withholds a "
          "prefetch the chip issues); overlapping ranges => one signed boundary.")
    return 0


def run_tb_internal(image, n, wvec):
    """Run the Verilator TB with +eudbg and return per-CPU-cycle rows with the
    bus record AND the core's internal queue-pipeline state. The TB is
    bit-identical to the fabric, so up to the first chip divergence these
    internals equal the CHIP's (Codex Step 1/5: use RTL state, not an external
    reconstruction). eudbg 'd' field order (tb_v30_core.sv):
    state q_pop q_avl q_cnt eu_wrap cur_wrap eu_addr eu_seg opc q_byte bus_phase
    bus_ts q_fresh eu_started eu_req eu_ready q_flush eval_ext evald flush_fast
    occupied q_aged infl eu_req_p1 pf_late_rsv pf_starved prefetch_ext prefetch_ok
    eu_wr eu_mem_acc onset_state onset_age onset_opc onset_kind onset_wr.
    onset_* (Phase 2k) = the reservation's OWN source: the EU state (onset_state)
    that generated the current eu_req, the CPU-cycle age since that rising edge
    (onset_age; 0 = rises on this row), and the opcode/kind/dir latched at onset."""
    import subprocess, tempfile
    from pathlib import Path
    from check_seq import BIN, ROOT
    td = tempfile.mkdtemp(prefix="eud_")
    img = Path(td) / "img.hex"; out = Path(td) / "out.txt"; wvf = Path(td) / "wv.hex"
    img.write_text("\n".join(f"{b:02x}" for b in image) + "\n")
    wvf.write_text("\n".join(f"{min(255, max(0, int(x))):02x}" for x in wvec) + "\n")
    args = [str(BIN), f"+bootimg={img}", f"+bootn={n}", f"+wvec={wvf}",
            f"+out={out}", "+eudbg"]
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError("TB eudbg failed")
    rows = []
    pend = None
    for ln in out.read_text().splitlines():
        p = ln.split()
        if not p:
            continue
        if p[0] == "d":
            pend = p
        elif p[0] == "r" and pend is not None:
            d = pend
            rows.append(dict(
                t=int(p[1]), bs=int(p[2]), qs=int(p[3]), addr=int(p[5], 16),
                state=int(d[1]), q_pop=int(d[2]), q_avl=int(d[3]), q_cnt=int(d[4]),
                eu_req=int(d[15]), eu_ready=int(d[16]), q_flush=int(d[17]),
                eval_ext=int(d[18]), occupied=int(d[21]), q_aged=int(d[22]),
                infl=int(d[23]),
                eu_req_p1=int(d[24]) if len(d) > 24 else 0,
                pf_late_rsv=int(d[25]) if len(d) > 25 else 0,
                pf_starved=int(d[26]) if len(d) > 26 else 0,
                prefetch_ext=int(d[27]) if len(d) > 27 else 0,
                prefetch_ok=int(d[28]) if len(d) > 28 else 0,
                eu_wr=int(d[29]) if len(d) > 29 else 0,
                eu_mem_acc=int(d[30]) if len(d) > 30 else 0,
                onset_state=int(d[31]) if len(d) > 31 else -1,
                onset_age=int(d[32]) if len(d) > 32 else -1,
                onset_opc=int(d[33], 16) if len(d) > 33 else -1,
                onset_kind=int(d[34]) if len(d) > 34 else -1,
                onset_wr=int(d[35]) if len(d) > 35 else -1))
            pend = None
    return rows


def cmd_predicate(a):
    """DECISIVE collision test (Codex Steps 1/3/5). On divergent vectors, align
    chip vs model, find the FIRST divergent bus cycle (streams aligned up to
    there, so the model's internal state == the chip's). Read the RTL
    queue-pipeline state at the decision and record: chip decision (prefetch
    CODE vs go-EU), model decision, occupied, q_aged, eu_req, q_avl, consuming.
    Build the (state -> chip decision) table and test COLLISION-FREEness; split
    over- vs under-prefetch to test one-vs-two mechanisms."""
    import random as _r
    from collections import defaultdict
    recs = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                rr = _r.Random((ws << 8) | wmax)
                wv = [rr.randint(0, wmax) for _ in range(4096)]
                chip = _trunc(accesses(run_chip(image, a.host, use_core=False, wvec=wv)))
                tb = run_tb_internal(image, 4200, wv)
                # model bus cycles from the tb rows (T1 starts a cycle)
                mcyc = []
                for i, rw in enumerate(tb):
                    if rw["t"] == 1:
                        mcyc.append((i, rw))
                mbs = [rw["bs"] for _, rw in mcyc]
                cbs = [x["bs"] for x in chip]
                n = min(len(cbs), len(mbs))
                fd = next((i for i in range(n) if cbs[i] != mbs[i]), None)
                # collect chip CODE/EU decisions over the ALIGNED prefix [0,fd]
                # (model==chip there, so the internal state is the CHIP's), plus
                # the first divergence itself. This gives agree-CODE, agree-EU,
                # AND the over-prefetch divergence for a real collision test.
                upto = (fd if fd is not None else n - 1)
                for bi in range(1, upto + 1):
                    cb = cbs[bi]
                    if cb not in (CODE, MEMR, MEMW, IOR, IOW):
                        continue
                    rowi = mcyc[bi][0]
                    st = tb[max(0, rowi - 1)]
                    pops = sum(tb[j]["q_pop"] for j in range(max(0, rowi - 8), rowi))
                    consuming = 1 if pops >= 2 else 0
                    cd = "CODE" if cb == CODE else "EU"
                    is_div = (fd is not None and bi == fd)
                    md = ("CODE" if mbs[bi] == CODE else "EU") if is_div else cd
                    sign = ("OVER" if is_div and md == "CODE" and cd == "EU" else
                            "UNDER" if is_div and md == "EU" and cd == "CODE" else "agree")
                    recs.append(dict(seed=seed, occ=st["occupied"], qa=st["q_aged"],
                                     eq=st["eu_req"], erdy=st["eu_ready"],
                                     qavl=st["q_avl"], infl=st["infl"],
                                     evx=st["eval_ext"], cons=consuming,
                                     chip=cd, model=md, sign=sign, div=is_div))
                    if is_div:
                        break
    from collections import Counter
    print(f"predicate: {len(recs)} chip CODE/EU decisions "
          f"({sum(r['div'] for r in recs)} first-divergences)")
    print(f"  divergence signs: "
          f"{dict(Counter(r['sign'] for r in recs if r['div']))}")

    def collide(fields, label):
        tbl = defaultdict(Counter)
        for r in recs:
            tbl[tuple(r[f] for f in fields)][r["chip"]] += 1
        coll = [(k, dict(v)) for k, v in tbl.items() if len(v) > 1]
        print(f"  keyed by {label}: {len(tbl)} cells, {len(coll)} COLLISIONS")
        for k, v in sorted(coll)[:12]:
            print(f"    {dict(zip(fields, k))}: chip={v}")
        return len(coll)

    # does the MODEL's fielded state (what prefetch_ok sees) predict chip decision?
    collide(["occ", "qa", "eq", "cons"], "model(occupied,q_aged,eu_req,consuming)")
    # add eu_ready, then eval_ext (the waited-window override predicate)
    collide(["occ", "qa", "eq", "erdy", "cons"], "+eu_ready")
    collide(["occ", "qa", "eq", "erdy", "cons", "evx"], "+eval_ext")
    # divergence internal states, now with eval_ext
    print("  first-divergence (OVER) states (chip=EU, model prefetched CODE):")
    dtbl = Counter()
    for r in recs:
        if r["div"] and r["sign"] == "OVER":
            dtbl[(r["occ"], r["eq"], r["erdy"], r["evx"], r["cons"])] += 1
    for k, ct in sorted(dtbl.items()):
        print(f"    occ={k[0]} eu_req={k[1]} eu_ready={k[2]} eval_ext={k[3]} "
              f"consuming={k[4]}: {ct}")
    print(f"  eval_ext=1 at divergence: "
          f"{sum(ct for k, ct in dtbl.items() if k[3] == 1)} / "
          f"{sum(dtbl.values())} (implicates the waited-window override)")
    return 0


def _eu_event(rows, bs, addr, ordinal):
    """Return the T1 row index of the `ordinal`-th (bs,addr) EU bus cycle."""
    d = 0
    for i, r in enumerate(rows):
        if r["t"] == 1 and r["bs_early"] == bs and (r["ad_addr"] & 0xFFFFF) == addr:
            if d == ordinal:
                return i
            d += 1
    return None


def _final_pop_before(rows, t1):
    """Row index of the last queue pop (QS F=1 / S=3) strictly before row t1."""
    for i in range(t1 - 1, -1, -1):
        if rows[i].get("qs") in (1, 3):
            return i
    return None


def _code_between(rows, lo, hi):
    """Was a CODE fetch T1 issued in (lo, hi)? (competition present)"""
    return any(rows[i]["t"] == 1 and rows[i]["bs_early"] == CODE
              for i in range(lo + 1, hi))


def cmd_nocomp(a):
    """DECISIVE no-competition control (Phase 2f Step 1). At a reproducible
    over-prefetch anchor, measure the chip's and model's EU-T1 relative to an
    OBSERVABLE anchor (the final instruction-byte pop, QS F/S), across diverse
    backgrounds. In NO-COMPETITION cells (no competing CODE prefetch between the
    final pop and the EU on that side) the EU issue latency is uncontaminated by
    arbitration:
      chip latency EARLIER than model  => Hyp A (chip EU readiness genuinely early)
      chip == model latency            => readiness correct => Hyp B/C (arbitration)
    Everything here is CHIP-OBSERVABLE (bus type + QS + clock); RTL internals are
    used ONLY to label the model side."""
    import random as _r
    g = generate(f"fz{a.seed}", exts=())
    image, meta = compose(g)
    # auto-select the target EU: first over-prefetch divergence on a ref bg
    rr = _r.Random(a.refws)
    refwv = [rr.randint(0, a.wmax) for _ in range(4096)]
    cref = _trunc(accesses(run_chip(image, a.host, use_core=False, wvec=refwv)))
    kref = _trunc(accesses(run_chip(image, a.host, use_core=True, wvec=refwv)))
    cbs, kbs = bs_stream(cref), bs_stream(kref)
    n = min(len(cbs), len(kbs))
    fd = next((i for i in range(n) if cbs[i] != kbs[i]
               and cbs[i] in (MEMR, MEMW) and kbs[i] == CODE), None)
    if fd is None:
        print(f"no over-prefetch divergence on fz{a.seed} ws{a.refws}"); return 1
    tbs, taddr = cref[fd]["bs"], cref[fd]["addr"]
    tord = sum(1 for j in range(fd) if cref[j]["bs"] == tbs and cref[j]["addr"] == taddr)
    print(f"target EU: {BSN[tbs]}@{taddr:05x} #{tord} (fz{a.seed}, divergence @bus{fd})")
    print(f"  bg: chip[lat comp?] | model[lat comp?]  (lat = EU_T1 - final_pop)")
    bgs = _bg_vectors(a.bgs, a.wmax)
    mutual, diverg = [], []       # (bgname, clat, klat) pairs
    for bgname, wv in bgs.items():
        cr = run_chip(image, a.host, use_core=False, wvec=wv)
        crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
        kr = run_tb_internal(image, 4200, wv)
        ct1 = _eu_event(crel, tbs, taddr, tord)
        kt1 = _eu_event([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                              ad_addr=x["addr"]) for x in kr], tbs, taddr, tord)
        if ct1 is None or kt1 is None:
            print(f"  {bgname}: target not found"); continue
        cpop = _final_pop_before(crel, ct1)
        kpop = _final_pop_before([dict(qs=x["qs"]) for x in kr], kt1)
        if cpop is None or kpop is None:
            print(f"  {bgname}: no pop"); continue
        clat, klat = ct1 - cpop, kt1 - kpop
        ccomp = _code_between(crel, cpop, ct1)
        kcomp = _code_between([dict(t=x["t"], bs_early=x["bs"]) for x in kr], kpop, kt1)
        print(f"  {bgname}: chip[lat={clat} comp={int(ccomp)}] | "
              f"model[lat={klat} comp={int(kcomp)}]")
        if not ccomp and not kcomp:
            mutual.append((bgname, clat, klat))
        elif not ccomp and kcomp:
            diverg.append((bgname, clat, klat))     # over-prefetch: chip EU, model CODE
    print("  --- MUTUAL no-competition (neither side prefetched) ---")
    if mutual:
        eq = all(c == k for _, c, k in mutual)
        for bg, c, k in mutual:
            print(f"    {bg}: chip lat={c}  model lat={k}  {'match' if c == k else 'DIFF'}")
        if eq:
            print("  => chip == model in every mutual cell => EU readiness/issue "
                  "timing CORRECT => HYP A RULED OUT (arbitration, not readiness)")
        else:
            print("  => chip differs from model with no competition => HYP A "
                  "(readiness genuinely early)")
    else:
        print("    (none - widen backgrounds)")
    # B vs C hint: in over-prefetch divergence cells, does the chip issue EU at
    # the SAME latency as its mutual-no-comp baseline (=> chip reserved, never
    # intended to prefetch: pending-reservation, HYP B) - the model's inserted
    # prefetch is pure extra.
    if diverg and mutual:
        base = mutual[0][1]
        print("  --- over-prefetch divergence cells (chip EU, model CODE) ---")
        for bg, c, k in diverg:
            print(f"    {bg}: chip EU lat={c} (baseline {base}); model inserted "
                  f"prefetch (+{k - c} clk)")
        print("  => chip issues EU on its normal schedule and leaves the "
              "queue-eligible slot UNUSED (reserved for the pending EU) => "
              "consistent with HYP B (pending-reservation priority); reader/store "
              "factorial needed to fully separate B from C.")
    return 0


def _reqclass(req, reqp1, rdy):
    if not req:
        return "absent"
    if rdy:
        return "ready"
    return "young" if not reqp1 else "aged"   # young = coincident (eu_req_p1==0)


def cmd_urgency(a):
    """Phase 2i (corrected): MEASURE the urgency predicate with ALL gate inputs
    sampled LIVE on the SAME eval_ext commit row (fixes the T4-vs-T4+1 sampler
    bug - q_cnt advances every CPU edge). At each waited-CODE->EU contested edge,
    find the model's eval_ext decision row, sample q_cnt/q_avl/q_aged/infl/occ/
    eu_req/eu_req_p1/eu_ready/pf_late_rsv there, classify the CHIP action
    IDLE/CODE, and STRATIFY by (q_cnt_eval, request-age class, access family).
    Confirms: q_cnt_eval>=2 => IDLE for YOUNG (coincident, eu_req_p1==0)
    reservations - the actionable claim for the one-line gate."""
    import random as _r
    from collections import defaultdict, Counter
    recs = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                wv = [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]
                cr = run_chip(image, a.host, use_core=False, wvec=wv)
                crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
                kr = run_tb_internal(image, 4200, wv)
                ca = _trunc(accesses(crel))
                ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                           ad_addr=x["addr"], ad_data=0) for x in kr]))
                cb, kb = bs_stream(ca), bs_stream(ka)
                nn = min(len(cb), len(kb))
                fd = next((i for i in range(nn) if cb[i] != kb[i]), nn)
                mt4 = {}
                bi = -1
                for ri, x in enumerate(kr):
                    if x["t"] == 1:
                        bi += 1
                    if x["t"] == 5:
                        mt4[bi] = ri
                for B in range(1, min(fd + 1, nn - 1)):
                    if ca[B]["bs"] != CODE or ca[B]["tw"] == 0:
                        continue
                    eu = next((j for j in range(B + 1, min(B + 6, len(ca)))
                               if ca[j]["bs"] in (MEMR, MEMW)), None)
                    if eu is None:
                        continue
                    if any(ca[j]["bs"] not in (CODE,) for j in range(B + 1, eu)):
                        continue
                    action = "CODE" if any(ca[j]["bs"] == CODE
                                           for j in range(B + 1, eu)) else "IDLE"
                    if B not in mt4:
                        continue
                    # find the eval_ext DECISION row: first eval_ext==1 within a
                    # few cycles after the completing CODE's T4 (the deferred eval)
                    er = None
                    for ri in range(mt4[B] + 1, min(mt4[B] + 6, len(kr))):
                        if kr[ri]["eval_ext"] == 1:
                            er = ri; break
                        if kr[ri]["t"] == 1:      # next bus cycle started, stop
                            er = ri; break
                    if er is None:
                        er = min(mt4[B] + 1, len(kr) - 1)
                    d = kr[er]
                    recs.append(dict(action=action, qc=d["q_cnt"], qa2=d["q_avl"],
                                     qag=d["q_aged"], infl=d["infl"], occ=d["occupied"],
                                     req=d["eu_req"], reqp1=d["eu_req_p1"],
                                     rdy=d["eu_ready"], plr=d["pf_late_rsv"],
                                     evx=d["eval_ext"], euwr=d.get("eu_wr", 0),
                                     rc=_reqclass(d["eu_req"], d["eu_req_p1"], d["eu_ready"]),
                                     fam=BSN[ca[eu]["bs"]],
                                     rwfam=("W" if d.get("eu_wr", 0) else "R")))
    print(f"urgency (corrected, live eval_ext-row sampling): {len(recs)} edges "
          f"({sum(1 for r in recs if r['action']=='IDLE')} IDLE / "
          f"{sum(1 for r in recs if r['action']=='CODE')} CODE)")
    if not recs:
        print("  (none)"); return 0

    def tab(pred, keys, label):
        sub = [r for r in recs if pred(r)]
        t = defaultdict(Counter)
        for r in sub:
            t[tuple(r[k] for k in keys)][r["action"]] += 1
        coll = sum(1 for v in t.values() if len(v) > 1)
        print(f"  [{label}] n={len(sub)} keyed by {keys}: {coll} MIXED")
        for k, v in sorted(t.items()):
            print(f"     {dict(zip(keys, k))}: {dict(v)}"
                  f"{'  <-- MIXED' if len(v) > 1 else ''}")
        return sub

    # request-age classes overall
    print("  action by request-age class:")
    rcc = defaultdict(Counter)
    for r in recs:
        rcc[r["rc"]][r["action"]] += 1
    for rc in sorted(rcc):
        print(f"    {rc}: {dict(rcc[rc])}")
    # THE actionable claim: YOUNG (coincident) reservations vs q_cnt_eval
    tab(lambda r: r["rc"] == "young", ["qc"], "YOUNG reservations, by q_cnt_eval")
    tab(lambda r: r["rc"] == "young", ["qc", "fam"],
        "YOUNG, by q_cnt_eval x CHIP-arch access family")
    tab(lambda r: r["rc"] == "young", ["qc", "rwfam"],
        "YOUNG, by q_cnt_eval x RTL eu_wr (R/W at the eval_ext row)")
    # pf_late_rsv firings vs q_cnt (which of these does the edit remove?)
    plr = [r for r in recs if r["plr"] == 1]
    print(f"  pf_late_rsv=1 firings: {len(plr)}; by q_cnt_eval: "
          f"{dict(sorted(Counter(r['qc'] for r in plr).items()))}; "
          f"at q_cnt>=2: {sum(1 for r in plr if r['qc']>=2)} "
          f"(=> q_cnt<=1 edit is a NO-OP if 0)")
    # pf_late_rsv firings by (q_cnt, family, chip action): where is the model
    # WRONG (pf_late_rsv=1 -> model CODE, but chip IDLE = over-prefetch)?
    print("  pf_late_rsv firings by (q_cnt, family) -> chip action:")
    pt = defaultdict(Counter)
    for r in plr:
        pt[(r["qc"], r["fam"])][r["action"]] += 1
    for k, v in sorted(pt.items()):
        wrong = v.get("IDLE", 0)   # chip IDLE while pf_late_rsv fired = model wrong
        print(f"    q_cnt={k[0]} {k[1]}: {dict(v)}"
              f"{'  <-- OVER-PREFETCH (chip IDLE, model CODE)' if wrong else ''}")
    return 0


def cmd_idleslot(a):
    """Phase 2h: the IDLE-SLOT proof of B's FAILING form. At over-prefetch
    divergences, measure whether the CHIP inserts idle (Ti) cycles between the
    completing CODE's T4 and the EU access's T1 (reserving the bus for a
    pending-but-unready EU request) while the MODEL issues a doomed prefetch in
    that slot. Record the model's internal state at its commit (occ/req/rdy/
    eval_ext) to characterize the reservation-age + queue-urgency rule."""
    import random as _r
    recs = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                wv = [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]
                cr = run_chip(image, a.host, use_core=False, wvec=wv)
                crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
                kr = run_tb_internal(image, 4200, wv)
                ca = _trunc(accesses(crel))
                ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                           ad_addr=x["addr"], ad_data=0) for x in kr]))
                cb, kb = bs_stream(ca), bs_stream(ka)
                nn = min(len(cb), len(kb))
                fd = next((i for i in range(nn) if cb[i] != kb[i]
                           and cb[i] in (MEMR, MEMW) and kb[i] == CODE), None)
                if fd is None or fd == 0:
                    continue
                # CHIP idle slots between completing CODE T4 and EU T1
                t4 = ca[fd - 1]["t4"]
                eut1 = ca[fd]["t1"]
                idle = sum(1 for i in range(t4 + 1, eut1) if crel[i]["t"] == 0)
                # MODEL commit state: the row where it starts the doomed CODE
                kt4 = ka[fd - 1]["t4"]
                kcode_t1 = ka[fd]["t1"]      # model's CODE T1 (fd is CODE for model)
                # its decision row = the Ti commit just before (eval_ext edge)
                dec = kr[max(0, kcode_t1 - 1)]
                recs.append(dict(seed=seed, ws=ws, wmax=wmax, idle=idle,
                                 occ=dec["occupied"], req=dec["eu_req"],
                                 rdy=dec["eu_ready"], qa=dec["q_aged"],
                                 evx=dec["eval_ext"], eu=BSN[ca[fd]["bs"]]))
    from collections import Counter
    print(f"idleslot: {len(recs)} over-prefetch divergences")
    if not recs:
        print("  (none found - widen corpus)"); return 0
    idled = sum(1 for r in recs if r["idle"] > 0)
    print(f"  chip inserted >=1 IDLE (Ti) slot where model prefetched: "
          f"{idled}/{len(recs)}  => idle-slot signature "
          f"{'UNIVERSAL' if idled == len(recs) else 'PARTIAL'}")
    print(f"  chip idle-slot count distribution: "
          f"{dict(sorted(Counter(r['idle'] for r in recs).items()))}")
    print(f"  model commit state (occ,req,rdy,evx) at the doomed prefetch:")
    st = Counter((r["occ"], r["req"], r["rdy"], r["evx"]) for r in recs)
    for k, ct in sorted(st.items()):
        print(f"    occ={k[0]} eu_req={k[1]} eu_ready={k[2]} eval_ext={k[3]}: {ct}")
    print(f"  eval_ext=1 at commit: {sum(1 for r in recs if r['evx'])}/{len(recs)}")
    print(f"  eu_req=1 (pending) & eu_ready=0 (unready) at commit: "
          f"{sum(1 for r in recs if r['req'] and not r['rdy'])}/{len(recs)} "
          f"(the pending-but-unready reservation the model wrongly overrides)")
    print(f"  queue occupancy at commit: "
          f"{dict(sorted(Counter(r['occ'] for r in recs).items()))} "
          f"(urgency: low occ = starved/urgent-refill regime)")
    return 0


def cmd_onset(a):
    """Phase 2k: RESOLVE the 12/24 collision by the reservation's OWN source +
    onset age. Same corpus as `urgency` (waited-CODE->EU contested edges, chip
    action IDLE/CODE = ground truth), but at the eval_ext decision row read the
    NEW onset instrumentation (onset_state = the EU state that generated eu_req,
    onset_age = CPU cycles since that rising edge) and key the YOUNG-reservation
    collision by (onset_state[, onset_age][, q_avl/q_aged]). The coarse
    eu_req_p1==0 'young' bit conflates ~10 reservation-source states; this tests
    whether the source + exact onset age is a COLLISION-FREE discriminator.

    Chip is ground truth (IDLE/CODE measured on the board); the model onset
    fields are valid CONDITION LABELS only on the aligned prefix (model==chip up
    to the first divergence, which is where these contested edges live)."""
    import random as _r
    from collections import defaultdict, Counter
    recs = []
    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                wv = [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]
                cr = run_chip(image, a.host, use_core=False, wvec=wv)
                crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
                kr = run_tb_internal(image, 4200, wv)
                ca = _trunc(accesses(crel))
                ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                                           ad_addr=x["addr"], ad_data=0) for x in kr]))
                cb, kb = bs_stream(ca), bs_stream(ka)
                nn = min(len(cb), len(kb))
                fd = next((i for i in range(nn) if cb[i] != kb[i]), nn)
                mt4 = {}
                bi = -1
                for ri, x in enumerate(kr):
                    if x["t"] == 1:
                        bi += 1
                    if x["t"] == 5:
                        mt4[bi] = ri
                for B in range(1, min(fd + 1, nn - 1)):
                    if ca[B]["bs"] != CODE or ca[B]["tw"] == 0:
                        continue
                    eu = next((j for j in range(B + 1, min(B + 6, len(ca)))
                               if ca[j]["bs"] in (MEMR, MEMW)), None)
                    if eu is None:
                        continue
                    if any(ca[j]["bs"] not in (CODE,) for j in range(B + 1, eu)):
                        continue
                    action = "CODE" if any(ca[j]["bs"] == CODE
                                           for j in range(B + 1, eu)) else "IDLE"
                    if B not in mt4:
                        continue
                    er = None
                    for ri in range(mt4[B] + 1, min(mt4[B] + 6, len(kr))):
                        if kr[ri]["eval_ext"] == 1:
                            er = ri; break
                        if kr[ri]["t"] == 1:
                            er = ri; break
                    if er is None:
                        er = min(mt4[B] + 1, len(kr) - 1)
                    d = kr[er]
                    recs.append(dict(action=action, qc=d["q_cnt"], qavl=d["q_avl"],
                                     qag=d["q_aged"], infl=d["infl"], occ=d["occupied"],
                                     req=d["eu_req"], reqp1=d["eu_req_p1"],
                                     rdy=d["eu_ready"], evx=d["eval_ext"],
                                     euwr=d.get("eu_wr", 0),
                                     rc=_reqclass(d["eu_req"], d["eu_req_p1"], d["eu_ready"]),
                                     osrc=_sname(d.get("onset_state", -1)),
                                     oage=d.get("onset_age", -1),
                                     okind=d.get("onset_kind", -1),
                                     owr=d.get("onset_wr", -1),
                                     oopc=d.get("onset_opc", -1),
                                     fam=BSN[ca[eu]["bs"]],
                                     seed=seed, ws=ws, wmax=wmax, B=B))
    print(f"onset (Phase 2k): {len(recs)} contested edges "
          f"({sum(1 for r in recs if r['action']=='IDLE')} IDLE / "
          f"{sum(1 for r in recs if r['action']=='CODE')} CODE)")
    if not recs:
        print("  (none)"); return 0

    def tab(pred, keys, label, show_ex=False):
        sub = [r for r in recs if pred(r)]
        t = defaultdict(Counter)
        ex = defaultdict(list)
        for r in sub:
            t[tuple(r[k] for k in keys)][r["action"]] += 1
            ex[tuple(r[k] for k in keys)].append(r)
        coll = sum(1 for v in t.values() if len(v) > 1)
        print(f"  [{label}] n={len(sub)} keyed by {keys}: "
              f"{coll} MIXED{'  <== COLLISION-FREE' if coll==0 and t else ''}")
        for k, v in sorted(t.items(), key=lambda kv: str(kv[0])):
            line = f"     {dict(zip(keys, k))}: {dict(v)}"
            if len(v) > 1:
                line += "  <-- MIXED"
            print(line)
            if show_ex and len(v) > 1:
                for act in ("IDLE", "CODE"):
                    e = next((r for r in ex[k] if r["action"] == act), None)
                    if e:
                        print(f"        e.g. {act}: seed={e['seed']} ws={e['ws']} "
                              f"wmax={e['wmax']} bus_B={e['B']} osrc={e['osrc']} "
                              f"oage={e['oage']} okind={e['okind']} owr={e['owr']} "
                              f"opc={e['oopc']:#04x}")
        return sub

    print("  action by request-age class (sanity vs urgency):")
    rcc = defaultdict(Counter)
    for r in recs:
        rcc[r["rc"]][r["action"]] += 1
    for rc in sorted(rcc):
        print(f"    {rc}: {dict(rcc[rc])}")

    # baseline: the collision AS PREVIOUSLY MEASURED (young x q_cnt x eu_wr) --
    # should reproduce the 12 IDLE / 24 CODE mix that has no separator.
    tab(lambda r: r["rc"] == "young", ["qc", "euwr"],
        "BASELINE collision (young x q_cnt x eu_wr) -- expect MIXED", show_ex=True)
    # THE test: does the reservation's OWN source separate it?
    tab(lambda r: r["rc"] == "young", ["osrc"],
        "young keyed by reservation SOURCE (onset_state)", show_ex=True)
    tab(lambda r: r["rc"] == "young", ["osrc", "oage"],
        "young keyed by SOURCE + onset AGE")
    tab(lambda r: r["rc"] == "young" and r["qc"] == 1, ["osrc", "oage"],
        "young q_cnt=1 keyed by SOURCE + onset AGE")
    # queue-pipeline orthogonalization (step 5): split q_cnt=1 by q_avl/q_aged
    tab(lambda r: r["rc"] == "young" and r["qc"] == 1, ["osrc", "qavl", "qag"],
        "young q_cnt=1 keyed by SOURCE + q_avl + q_aged")
    tab(lambda r: r["rc"] == "young", ["osrc", "oage", "qc"],
        "young keyed by SOURCE + AGE + q_cnt (full)")
    # keep the eu_req=0 (reservation registered too late) cases separate
    absent = [r for r in recs if r["rc"] == "absent"]
    print(f"  eu_req=0 (absent/late-registration) edges: {len(absent)} "
          f"actions={dict(Counter(r['action'] for r in absent))}")
    return 0


def cmd_leactl(a):
    """B-vs-C discriminator (Phase 2g Step 1): the no-request LEA control. Build
    a matched 3-variant block - reader (8B07, reserves S_EA1), store (8907,
    S_EA2), LEA (8D07, NO EU bus request) - at the same anchor, and compare what
    happens at the disputed edge E (the bus cycle right after the ModRM is
    delivered). LEA issues a CODE prefetch at E => E is a REAL arbitration edge;
    reader/store issuing their EU access there instead => a pending EU request
    SELECTIVELY suppresses the eligible prefetch => Hypothesis B (edge exists +
    pending-reservation priority), refuting C (no edge at E)."""
    import testimage
    regs = dict(BW=0x0200, AW=0x1234, DS0=0x0000, PS=0x0000, PC=0x0100)
    ram = [(0x0200, 0x34), (0x0201, 0x12)]
    variants = [("reader 8B07", b"\x8b\x07", MEMR),
                ("store  8907", b"\x89\x07", MEMW),
                ("lea    8D07", b"\x8d\x07", None)]
    print("no-request LEA control (edge E = bus cycle after the ModRM byte):")
    for name, op, eubs in variants:
        image, meta = testimage.compose(regs=regs, instr=op, ram=ram)
        al = meta["anchor_linear"]
        outcomes = []
        for N in range(0, a.maxn + 1):
            ref = accesses(run_chip(image, a.host, use_core=False, wvec=[0] * 4096))
            af = next((i for i, x in enumerate(ref)
                       if x["bs"] == CODE and x["addr"] == al), None)
            wv = [0] * 4096
            if af is not None and af + 2 < 4096:
                wv[af + 2] = N
            c = accesses(run_chip(image, a.host, use_core=False, wvec=wv))
            afc = next((i for i, x in enumerate(c)
                        if x["bs"] == CODE and x["addr"] == al), None)
            if afc is None:
                outcomes.append("?"); continue
            after = c[afc + 3] if afc + 3 < len(c) else None
            if after is None:
                outcomes.append("-")
            elif after["bs"] == CODE:
                outcomes.append("CODE")        # prefetch issued at E
            elif after["bs"] in (MEMR, MEMW) and (after["addr"] & 0xFFFFF) == 0x0200:
                outcomes.append("EU")          # EU access (prefetch suppressed)
            else:
                outcomes.append(BSN.get(after["bs"], "?"))
        uniq = sorted(set(outcomes))
        print(f"  {name}: at E over N=0..{a.maxn} -> {uniq}")
    print("  => LEA=CODE (edge is a real prefetch opportunity), reader/store=EU "
          "(pending request suppresses it): arbitration edge EXISTS at E and a "
          "pending EU request SELECTIVELY suppresses the prefetch => HYP B "
          "(C refuted). [At this clean anchor the reservation is always old "
          "enough; the model AGREES - the young-reservation threshold + the "
          "model's error live in the pf_late_rsv boundary, not reproduced by "
          "this minimal block - see notes.]")
    return 0


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


def _trunc(acc):
    """Drop the post-program idle tail: cut at the first HALT (bs==3), which
    marks the store-routine's end - the tail after it is meaningless idle."""
    for i, x in enumerate(acc):
        if x["bs"] == 3:
            return acc[:i]
    return acc


def cmd_align(a):
    """Enumerate ALL divergence classes via SEQUENCE ALIGNMENT (not equal-index).
    Align chip vs core bus streams by (bs, addr); classify every edit op and,
    on matched cycles, flag same-type-wrong-clock and same-type-wrong-address.
    Aggregates class counts over a corpus - answers 'one class or several?'"""
    import difflib
    import random as _r
    classes = {}

    def bump(k):
        classes[k] = classes.get(k, 0) + 1

    for seed in a.seeds:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, a.nws + 1):
            for wmax in a.wmaxes:
                rr = _r.Random((ws << 8) | wmax)
                wv = [rr.randint(0, wmax) for _ in range(4096)]
                c = _trunc(accesses(run_chip(image, a.host, use_core=False, wvec=wv)))
                k = _trunc(accesses(run_chip(image, a.host, use_core=True, wvec=wv)))
                cseq = [(x["bs"], x["addr"]) for x in c]
                kseq = [(x["bs"], x["addr"]) for x in k]
                sm = difflib.SequenceMatcher(a=cseq, b=kseq, autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        # matched accesses: check clock alignment drift onset
                        continue
                    # classify the edit
                    chside = [BSN.get(c[x]["bs"], c[x]["bs"]) for x in range(i1, i2)]
                    coside = [BSN.get(k[x]["bs"], k[x]["bs"]) for x in range(j1, j2)]
                    if tag == "insert":     # present in core, not chip
                        bump("core-INSERTS " + "/".join(sorted(set(coside))))
                    elif tag == "delete":   # present in chip, not core
                        bump("core-OMITS " + "/".join(sorted(set(chside))))
                    else:  # replace / reorder
                        if set(chside) == set(coside):
                            bump("REORDER " + "/".join(sorted(set(chside))))
                        elif "CODE" in coside and set(chside) <= {"MEMR", "MEMW",
                                                                  "IOR", "IOW"}:
                            bump("core-CODE-vs-chip-EU")
                        else:
                            bump("replace " + "/".join(sorted(set(chside))) +
                                 "->" + "/".join(sorted(set(coside))))
    total = sum(classes.values())
    print(f"align: corpus {len(a.seeds)} progs x {a.nws} wseeds x {a.wmaxes}; "
          f"{total} divergence edit-ops")
    for cls, ct in sorted(classes.items(), key=lambda x: -x[1]):
        print(f"  {ct:4}  {cls}")
    if not classes:
        print("  (no divergences in corpus)")
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
    p.add_argument("--bg", choices=("zero", "rand"), default="zero",
                   help="background: uniform ref-fill, or random (nonzero)")
    p.add_argument("--bgseed", type=int, default=1)
    p.set_defaults(fn=cmd_impulse)
    p = sub.add_parser("ownwait")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90007)
    p.add_argument("--anchor-bus", type=int, required=True)
    p.add_argument("--maxn", type=int, default=6)
    p.add_argument("--core", action="store_true",
                   help="also run the fabric core and flag where it diverges")
    p.set_defaults(fn=cmd_ownwait)
    p = sub.add_parser("arbsweep")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--anchor-bus", type=int, required=True)
    p.add_argument("--bgseed", type=int, default=2,
                   help="background wait-vector seed (-1 = all-zero)")
    p.add_argument("--wmax", type=int, default=3)
    p.add_argument("--maxn", type=int, default=15)
    p.set_defaults(fn=cmd_arbsweep)
    p = sub.add_parser("arbpop")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--bgs", nargs="+",
                   default=["z", "o", "t", "a", "r2", "r5"],
                   help="background kinds: z=0 o=1 t=wmax a=alt rN=random(N)")
    p.add_argument("--wmax", type=int, default=3)
    p.add_argument("--maxn", type=int, default=5)
    p.add_argument("--per", type=int, default=10)
    p.add_argument("--core", action="store_true",
                   help="also sweep the fabric core and compare boundaries")
    p.set_defaults(fn=cmd_arbpop)
    p = sub.add_parser("arbscan")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015])
    p.add_argument("--bgs", type=int, nargs="+", default=[-1, 2, 5])
    p.add_argument("--wmax", type=int, default=3)
    p.add_argument("--maxn", type=int, default=4)
    p.add_argument("--per", type=int, default=6,
                   help="max anchors per (program,bg)")
    p.set_defaults(fn=cmd_arbscan)
    p = sub.add_parser("episodes")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=6)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    p.set_defaults(fn=cmd_episodes)
    p = sub.add_parser("predicate")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=8)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    p.set_defaults(fn=cmd_predicate)
    p = sub.add_parser("nocomp")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--refws", type=int, default=2)
    p.add_argument("--wmax", type=int, default=3)
    p.add_argument("--bgs", nargs="+",
                   default=["z", "o", "t", "a", "r2", "r5", "r7", "r11"])
    p.set_defaults(fn=cmd_nocomp)
    p = sub.add_parser("leactl")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--maxn", type=int, default=8)
    p.set_defaults(fn=cmd_leactl)
    p = sub.add_parser("idleslot")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=8)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    p.set_defaults(fn=cmd_idleslot)
    p = sub.add_parser("urgency")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=8)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7])
    p.set_defaults(fn=cmd_urgency)
    p = sub.add_parser("onset")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=10)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 2, 3, 7])
    p.set_defaults(fn=cmd_onset)
    p = sub.add_parser("pfdiff")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--wseed", type=int, default=1)
    p.add_argument("--wmax", type=int, default=3)
    p.set_defaults(fn=cmd_pfdiff)
    p = sub.add_parser("align")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seeds", type=int, nargs="+",
                   default=[90003, 90007, 90015, 90021, 90030])
    p.add_argument("--nws", type=int, default=6)
    p.add_argument("--wmaxes", type=int, nargs="+", default=[1, 3, 7, 15])
    p.set_defaults(fn=cmd_align)
    p = sub.add_parser("scan")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--seed", type=int, default=90003)
    p.add_argument("--show", type=int, default=20)
    p.set_defaults(fn=cmd_scan)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
