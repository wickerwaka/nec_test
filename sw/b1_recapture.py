#!/usr/bin/env python3
"""B1 — 2313-seed fixed-fabric RE-CAPTURE + re-based per-KIND-cell census.

Scales t33_refix.py (proven 60-seed method) to the FULL waited-cadence family on
the CURRENT board fabric (master build fae64d5). Per seed: derive->build->compose
the mc1 image, capture CHIP (use_core=False) then FABRIC (use_core=True) under the
seed's exact wait vector, compute the class-5 signed inter-T1 gap-error per aligned
bus ordinal, and mass it per KIND cell. done_mismatch seeds are censused as their
OWN regime. Board-only for the capture; the census is board-free.

Discipline: per-case capture wrapped (RunError -> skip + count); CIRCUIT-BREAKER
STOP on a RunError storm (>=STORM consecutive); incremental repo-relative log with
a LITERAL completion marker; board left use_core=False idle at start and end.

Usage: nohup setsid python3 -u sw/b1_recapture.py > sw/b1_recapture.log 2>&1 &
       (watch sw/b1_recapture.log for "B1_RECAPTURE_DONE" or "B1_WEDGE_STOP")
"""
import sys
import json
import gzip
import time
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import fuzz_campaign as fzc                          # noqa: E402
import check_seq                                     # noqa: E402
import testimage                                     # noqa: E402
from causal_wrand import accesses, CODE              # noqa: E402
from class5_align import align                       # noqa: E402

HOST = "root@mister-nec"
RESULTS = ROOT / "sw/testdata/campaigns/mc1/results.jsonl"
OUT = ROOT / "sw/testdata/campaigns/mc1_refix"
STORM = 25                          # consecutive RunErrors -> wedge circuit-break


def waited(r):
    w = r.get("waits") or {}
    return bool(w.get("wrand")) or (w.get("fixed") or 0) > 0


def kindof(bs):
    return "CODE" if bs == CODE else "EU"


def censusleg(real, sim):
    rel = next((i for i, x in enumerate(real) if not x.get("rst")), 0)
    ca = accesses(real[rel:])
    ka = accesses(sim)
    if len(ca) < 4 or len(ka) < 4:
        return None, None
    try:
        pairs, _e, _s = align(ca, ka)
    except Exception:
        return None, None
    kmap = {ci: ki for ci, ki in pairs}
    m = defaultdict(int)
    net = 0
    for i in sorted(kmap):
        if i == 0 or (i - 1) not in kmap:
            continue
        ki, kip = kmap[i], kmap[i - 1]
        ge = (ca[i]["t1"] - ca[i - 1]["t1"]) - (ka[ki]["t1"] - ka[kip]["t1"])
        if ge:
            m["%s->%s" % (kindof(ca[i - 1]["bs"]), kindof(ca[i]["bs"]))] += abs(ge)
            net += ge
    return m, net


def board_idle():
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)


def main():
    t0 = time.time()
    print(f"=== B1 RE-CAPTURE  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
          f"fabric=fae64d5 (master pin) ===", flush=True)
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    fam = [r for r in rows if waited(r) and
           (r.get("verdict") == "TIMING" or r.get("sub") == "done_mismatch")]
    print(f"family: {len(fam)} waited seeds (TIMING + done_mismatch)", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)

    board_idle()
    print("board idle confirmed; starting capture", flush=True)

    # census accumulators (TIMING regime vs done_mismatch regime, separately)
    mass = {"TIMING": defaultdict(int), "done_mismatch": defaultdict(int)}
    netmass = {"TIMING": 0, "done_mismatch": 0}
    n_ok = {"TIMING": 0, "done_mismatch": 0}
    perseed = []
    runerr = 0
    consec_err = 0
    done = 0
    for r in fam:
        k = r["k"]
        regime = "done_mismatch" if r.get("sub") == "done_mismatch" else "TIMING"
        w = r["waits"]
        wr = (w["wmax"], w["wseed"]) if w.get("wrand") else None
        # reconstruct image
        try:
            ov = {"force_contained": True, "strict": True}
            g = fzc.build(fzc.derive_case(r.get("cid", "mc1"), k, ov))
            image, _ = check_seq.compose(g)
        except Exception as e:
            continue
        # capture chip + fabric
        try:
            if wr:
                chip = check_seq.run_chip(image, HOST, use_core=False, wrand=wr)
                core = check_seq.run_chip(image, HOST, use_core=True, wrand=wr)
            else:
                chip = check_seq.run_chip(image, HOST, use_core=False, waits=w["fixed"])
                core = check_seq.run_chip(image, HOST, use_core=True, waits=w["fixed"])
            consec_err = 0
        except Exception as e:
            runerr += 1
            consec_err += 1
            if consec_err >= STORM:
                print(f"\n=== B1_WEDGE_STOP: {consec_err} consecutive RunErrors "
                      f"at seed {k} ({repr(e)[:120]}) -- circuit-breaker ===",
                      flush=True)
                board_idle()
                return 2
            continue
        m, net = censusleg(chip, core)
        done += 1
        if m is not None:
            for c, v in m.items():
                mass[regime][c] += v
            netmass[regime] += net
            n_ok[regime] += 1
            perseed.append(dict(k=k, regime=regime,
                                mass=sum(m.values()), net=net))
        if done % 200 == 0:
            print(f"  ... {done}/{len(fam)} captured "
                  f"({time.time()-t0:.0f}s, {runerr} runerr)", flush=True)

    board_idle()
    print("board idle (session end)", flush=True)

    # save per-seed + census
    (OUT / "perseed.json").write_text(json.dumps(perseed) + "\n")
    census_out = {reg: {"n_ok": n_ok[reg], "net": netmass[reg],
                        "mass": dict(mass[reg]),
                        "total": sum(mass[reg].values())}
                  for reg in ("TIMING", "done_mismatch")}
    (OUT / "census.json").write_text(json.dumps(census_out, indent=1) + "\n")

    print("\n=== RE-BASED CENSUS (current fabric) ===", flush=True)
    for reg in ("TIMING", "done_mismatch"):
        tot = sum(mass[reg].values())
        print(f"\n[{reg}] {n_ok[reg]} seeds, total |ge| mass={tot}, "
              f"net={netmass[reg]}")
        for c in ("CODE->CODE", "EU->CODE", "CODE->EU", "EU->EU"):
            v = mass[reg][c]
            print(f"  {c:<11} {v:7d} ({100*v/max(1,tot):4.1f}%)")
    grand = sum(sum(mass[reg].values()) for reg in mass)
    print(f"\nGRAND TOTAL |ge| mass = {grand}  (runerr={runerr}, "
          f"{time.time()-t0:.0f}s)")
    print(f"\n=== B1_RECAPTURE_DONE  seeds={done}/{len(fam)} "
          f"grand_mass={grand} ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
