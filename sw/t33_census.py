#!/usr/bin/env python3
"""t33_census - board-free per-transition gap-error census over the mc1
waited-cadence family, in the class-5 taxonomy.

Each mc1 capture holds the CHIP (real) and the BOARD-FABRIC (sim) legs run under
the SAME campaign wrand vector, so they are already wait-aligned. We compute the
class-5 signed inter-T1 gap-error per aligned bus ordinal:

    ge[i] = (chip_gap[i]) - (fabric_gap[i])

and census by the BUS-OBSERVABLE context (transition kind, prev_tw, parity). The
model-INTERNAL keys (occ/q_cnt/eval_ext) need a TB re-run and are the Stage-2
law-fitting frame; this census gives the MASS MAP the coordinator asked for
(mass per taxonomy cell, incl. the never-attacked CODE->EU block), board-free.
"""
import sys, json, gzip, glob
from pathlib import Path
from collections import defaultdict, Counter
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import accesses, MEMR, MEMW, CODE, IOR, IOW, INTA  # noqa: E402
from class5_align import align                                       # noqa: E402

CAP = SW / "testdata" / "campaigns" / "mc1" / "captures"
BSN = {CODE: "CODE", MEMR: "MEMR", MEMW: "MEMW", IOR: "IOR", IOW: "IOW",
       INTA: "INTA", 3: "HALT", 7: "PASV"}


def kind(bs):
    return "CODE" if bs == CODE else "EU"   # EU = MEMR/MEMW/IOR/IOW/INTA


def census(seeds, capmap):
    cells = defaultdict(lambda: [0, 0, 0, 0])   # key -> [n, zero, pos, neg]
    mass = defaultdict(int)                      # key -> sum|ge|
    kindmass = defaultdict(int)
    kindn = defaultdict(lambda: [0, 0])          # kind-cell -> [nonzero, total]
    paired_mass = unpaired_mass = 0
    tot_intervals = tot_nz = 0
    per_seed_ge = []
    used = 0
    for k in seeds:
        f = capmap.get(k)
        if not f:
            continue
        try:
            d = json.load(gzip.open(f))
        except Exception:
            continue
        real = d["real"]
        rel = next((i for i, r in enumerate(real) if not r.get("rst")), 0)
        ca = accesses(real[rel:])
        ka = accesses(d["sim"])
        if len(ca) < 3 or len(ka) < 3:
            continue
        used += 1
        try:
            pairs, _e, _s = align(ca, ka)
        except Exception:
            continue
        kmap = {ci: ki for ci, ki in pairs}
        ges = []
        for i in sorted(kmap):
            if i == 0 or (i - 1) not in kmap:
                continue
            ki, kip = kmap[i], kmap[i - 1]
            if ca[i]["t1"] is None or ka[ki]["t1"] is None:
                continue
            cg = ca[i]["t1"] - ca[i - 1]["t1"]
            mg = ka[ki]["t1"] - ka[kip]["t1"]
            ge = cg - mg
            kc = f"{kind(ca[i-1]['bs'])}->{kind(ca[i]['bs'])}"
            tk = f"{BSN.get(ca[i-1]['bs'],ca[i-1]['bs'])}->{BSN.get(ca[i]['bs'],ca[i]['bs'])}"
            tot_intervals += 1
            kindn[kc][1] += 1
            c = cells[tk]
            c[0] += 1
            if ge == 0:
                c[1] += 1
            elif ge > 0:
                c[2] += 1
            else:
                c[3] += 1
            if ge != 0:
                tot_nz += 1
                kindn[kc][0] += 1
                mass[tk] += abs(ge)
                kindmass[kc] += abs(ge)
                ges.append((i, ge, kc))
        # paired vs unpaired: one-to-one greedy match of adjacent opposite-sign ge
        paired, unpaired = pair_match(ges)
        paired_mass += paired
        unpaired_mass += unpaired
    return dict(used=used, tot_intervals=tot_intervals, tot_nz=tot_nz,
                cells=cells, mass=mass, kindmass=kindmass, kindn=kindn,
                paired_mass=paired_mass, unpaired_mass=unpaired_mass)


def pair_match(ges):
    """Authoritative one-to-one greedy pairing of adjacent opposite-sign impulses
    (class5 method: any 1-slot shift makes a +N/-N adjacent pair; pair them to
    separate ordering-scatter from net directional drift)."""
    paired = unpaired = 0
    used = [False] * len(ges)
    for a in range(len(ges)):
        if used[a]:
            continue
        ia, ga, _ = ges[a]
        matched = False
        for b in range(a + 1, min(a + 3, len(ges))):
            if used[b]:
                continue
            ib, gb, _ = ges[b]
            if gb == -ga and ib - ia <= 3:
                paired += abs(ga) * 2
                used[a] = used[b] = True
                matched = True
                break
        if not matched:
            unpaired += abs(ga)
            used[a] = True
    return paired, unpaired


def main():
    rows = [json.loads(l) for l in (SW / "testdata" / "campaigns" / "mc1"
            / "results.jsonl").read_text().splitlines() if l.strip()]

    def waited(r):
        w = r.get("waits") or {}
        return bool(w.get("wrand")) or (w.get("fixed") or 0) > 0
    fam = [r for r in rows if waited(r) and
           (r.get("verdict") == "TIMING" or r.get("sub") == "done_mismatch")]
    # map k -> capture file
    capmap = {}
    for f in glob.glob(str(CAP / "*.json.gz")):
        b = Path(f).name.split("_")
        if len(b) >= 3:
            try:
                capmap[int(b[1])] = f
            except ValueError:
                pass
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(fam)
    seeds = [r["k"] for r in fam][:limit]
    R = census(seeds, capmap)
    print(f"=== t33 gap-error census: {R['used']} seeds, {R['tot_intervals']} "
          f"aligned intervals, {R['tot_nz']} nonzero "
          f"({100*R['tot_nz']/max(1,R['tot_intervals']):.1f}%) ===")
    tot_mass = sum(R["mass"].values())
    print(f"TOTAL |ge| mass = {tot_mass}")
    print(f"PAIRED mass = {R['paired_mass']} ; UNPAIRED (net directional) = "
          f"{R['unpaired_mass']}  (paired ~ ordering-scatter/1-slot; unpaired ~ "
          f"real net drift)")
    print("\nBy KIND cell (class-5 top taxonomy) [nonzero/total, mass, mass%]:")
    for kc in ("CODE->CODE", "CODE->EU", "EU->CODE", "EU->EU"):
        nz, tot = R["kindn"][kc]
        m = R["kindmass"][kc]
        print(f"  {kc:<10} nz={nz:6d}/{tot:<7d} ({100*nz/max(1,tot):4.1f}%)  "
              f"mass={m:7d} ({100*m/max(1,tot_mass):4.1f}%)")
    print("\nTop bus-transition cells by mass:")
    for tk, m in sorted(R["mass"].items(), key=lambda x: -x[1])[:16]:
        n, z, p, mg = R["cells"][tk]
        print(f"  {tk:<14} mass={m:6d}  n={n:6d} +{p:<5d} -{mg:<5d} "
              f"err={100*(p+mg)/max(1,n):4.1f}%")


if __name__ == "__main__":
    main()
