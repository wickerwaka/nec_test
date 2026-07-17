#!/usr/bin/env python3
"""eu_req=0 EU-onset characterization (Phase 3b follow-up).

For each class-1 first-divergence (chip issues an EU access at bus B while the
fabric/model prefetches an extra CODE first, because the model's eu_req=0 at the
eval edge), MEASURE:
  - the instruction (opcode/ModRM, EU-access CS:IP + linear addr),
  - the EU access kind (MEMR/MEMW/IOR/IOW),
  - the reservation SOURCE state the model EVENTUALLY uses (onset_state at the
    model's eu_req RISING edge downstream of the eval),
  - the LATENESS: how many CPU cycles the model's eu_req rises AFTER the eval
    decision edge (where the chip's reservation is already effective), and where
    the doomed CODE prefetch sits relative to that rising edge.

Chip = ground truth. Model (TB==fabric) internals are valid labels only on the
aligned prefix (model==chip up to the first (bs,addr) divergence), which is
exactly where these edges live.
"""
import sys, random as _r
from pathlib import Path
from collections import defaultdict, Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import causal_wrand as C
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, _trunc, _sname, BSN,
                          MEMR, MEMW, CODE, IOR, IOW)

SEEDS = [90003, 90007, 90015, 90021, 90030, 90042, 90051, 90063, 90077, 90088]
NWS = 10
WMAXES = [1, 3, 7]


def find_class1(seed, ws, wmax, host, image):
    """Reproduce census class-1 detection for one vector. Returns a dict with the
    chip trace, model trace, bus index B of the first over-prefetch-with-eu_req=0,
    and the eval decision row, or None."""
    wv = [_r.Random((ws << 8) | wmax).randint(0, wmax) for _ in range(4096)]
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = _trunc(accesses(crel))
    ka = _trunc(accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                               ad_addr=x["addr"], ad_data=0) for x in kr]))
    cb, kb = bs_stream(ca), bs_stream(ka)
    nn = min(len(cb), len(kb))
    B = next((i for i in range(nn)
              if cb[i] != kb[i] or ca[i]["addr"] != ka[i]["addr"]), None)
    if B is None:
        return None
    cbb, kbb = cb[B], kb[B]
    over = (cbb in (MEMR, MEMW, IOR, IOW) and kbb == CODE)
    if not over:
        return None
    # map model bus index -> T1/T4 rows
    mt4 = {}; mt1 = {}; bi = -1
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1; mt1[bi] = ri
        if x["t"] == 5:
            mt4[bi] = ri
    # decision row: eval_ext preceding bus B (same logic as census)
    d = None; drow = None
    if B in mt4 and (B - 1) in mt4:
        for ri in range(mt4[B - 1] + 1, min(mt1.get(B, mt4[B - 1] + 6) + 1, len(kr))):
            if kr[ri]["eval_ext"] == 1:
                d = kr[ri]; drow = ri; break
    if d is None and B in mt1:
        drow = max(0, mt1[B] - 1); d = kr[drow]
    if d is None:
        drow = 0; d = kr[0]
    if d["eu_req"] != 0:
        return None    # not class-1
    return dict(wv=wv, ca=ca, ka=ka, cr=crel, kr=kr, B=B, drow=drow, d=d,
                mt1=mt1, mt4=mt4, cbb=cbb, seed=seed, ws=ws, wmax=wmax)


def analyze(rec, image):
    kr = rec["kr"]; drow = rec["drow"]; B = rec["B"]; ca = rec["ca"]
    # --- the EU access the chip performs at B ---
    eu_bs = ca[B]["bs"]; eu_addr = ca[B]["addr"]
    # opcode of the instruction generating this EU access: find the last CODE
    # access (chip) before B, use the model onset_opc as authoritative once eu_req
    # rises. Also grab raw bytes at the *preceding* CODE fetch addr for context.
    # --- model: find eu_req RISING edge downstream of the eval decision ---
    rise = None
    prev_req = kr[drow]["eu_req"]
    for ri in range(drow + 1, min(drow + 40, len(kr))):
        if kr[ri]["eu_req"] == 1 and prev_req == 0:
            rise = ri; break
        prev_req = kr[ri]["eu_req"]
    onset = kr[rise] if rise is not None else None
    # doomed CODE prefetch T1 (model bus B) row:
    pf_t1 = rec["mt1"].get(B)
    # CPU-cycle lateness: rows between the eval decision and the eu_req rising edge
    late_cycles = (rise - drow) if rise is not None else None
    # also lateness relative to the doomed prefetch's T1
    late_vs_pf = (rise - pf_t1) if (rise is not None and pf_t1 is not None) else None
    return dict(
        eu_bs=BSN.get(eu_bs, eu_bs), eu_addr=eu_addr,
        d_state=_sname(rec["d"].get("state", -1)),
        d_qcnt=rec["d"]["q_cnt"], d_occ=rec["d"]["occupied"], d_infl=rec["d"]["infl"],
        d_evx=rec["d"]["eval_ext"], d_reqp1=rec["d"]["eu_req_p1"],
        rise=rise, late_cycles=late_cycles, late_vs_pf=late_vs_pf,
        onset_state=_sname(onset.get("onset_state", -1)) if onset else None,
        onset_opc=onset.get("onset_opc", -1) if onset else -1,
        onset_kind=onset.get("onset_kind", -1) if onset else -1,
        onset_wr=onset.get("onset_wr", -1) if onset else -1,
        onset_age=onset.get("onset_age", -1) if onset else -1,
        rise_state=_sname(onset.get("state", -1)) if onset else None,
    )


def main():
    host = "root@mister-nec"
    hits = []
    for seed in SEEDS:
        g = generate(f"fz{seed}", exts=())
        image, meta = compose(g)
        for ws in range(1, NWS + 1):
            for wmax in WMAXES:
                rec = find_class1(seed, ws, wmax, host, image)
                if rec is None:
                    continue
                info = analyze(rec, image)
                hits.append((rec, info))
                print(f"fz{seed} ws{ws} wmax{wmax}: B={rec['B']} "
                      f"chip={info['eu_bs']}@{info['eu_addr']:05x} "
                      f"| eval: state={info['d_state']} q_cnt={info['d_qcnt']} "
                      f"occ={info['d_occ']} infl={info['d_infl']} evx={info['d_evx']} "
                      f"| model eu_req rises +{info['late_cycles']}cyc "
                      f"(vs doomed-pf-T1 {info['late_vs_pf']:+}) "
                      f"onset={info['onset_state']} opc={info['onset_opc']:#04x} "
                      f"kind={info['onset_kind']} wr={info['onset_wr']} "
                      f"rise_state={info['rise_state']}")
    print(f"\n=== {len(hits)} class-1 eu_req=0 cases ===")
    print("\nBy EU-access kind:")
    for k, n in Counter(i["eu_bs"] for _, i in hits).most_common():
        print(f"   {k}: {n}")
    print("\nBy model reservation ONSET source (at eu_req rising edge):")
    for k, n in Counter(i["onset_state"] for _, i in hits).most_common():
        print(f"   {k}: {n}")
    print("\nBy onset opcode:")
    for k, n in Counter(i["onset_opc"] for _, i in hits).most_common():
        print(f"   {k:#04x}: {n}")
    print("\nLateness (model eu_req rise - eval decision row), CPU cycles:")
    for k, n in sorted(Counter(i["late_cycles"] for _, i in hits).items()):
        print(f"   +{k}: {n}")
    print("\nLateness vs doomed-prefetch T1 (rise - pf_T1):")
    for k, n in sorted(Counter(i["late_vs_pf"] for _, i in hits).items()):
        print(f"   {k:+}: {n}")
    print("\nBy (eu_bs, onset_state, late_cycles):")
    for k, n in sorted(Counter((i["eu_bs"], i["onset_state"], i["late_cycles"])
                               for _, i in hits).items()):
        print(f"   {k}: {n}")


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] in ("dump", "w0")):
    main()


def dump_case(seed, ws, wmax, host="root@mister-nec", win=8):
    """Cycle-level dump of one class-1 case: model (TB) internal rows around the
    eval decision, and the chip's raw T-state stream around the same bus index."""
    g = generate(f"fz{seed}", exts=())
    image, meta = compose(g)
    rec = find_class1(seed, ws, wmax, host, image)
    if rec is None:
        print(f"fz{seed} ws{ws} wmax{wmax}: not class-1"); return
    kr = rec["kr"]; drow = rec["drow"]; B = rec["B"]; ca = rec["ca"]
    TN = {1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4", 0: "Ti"}
    print(f"\n### fz{seed} ws{ws} wmax{wmax}  B={B} chip={BSN.get(ca[B]['bs'])}"
          f"@{ca[B]['addr']:05x}  eval drow={drow}")
    print("MODEL (TB) rows [row t bs addr state eu_req eu_ready eval_ext q_cnt "
          "q_pop occ]:")
    for ri in range(max(0, drow - win), min(drow + win + 1, len(kr))):
        x = kr[ri]
        mark = " <== EVAL" if ri == drow else ""
        mark += " <== eu_req^" if (ri > 0 and x["eu_req"] == 1
                                   and kr[ri-1]["eu_req"] == 0) else ""
        print(f"  {ri:4d} {TN.get(x['t'],x['t']):>2} bs={BSN.get(x['bs'],x['bs']):<4} "
              f"{x['addr']:05x} {_sname(x['state']):<11} req={x['eu_req']} "
              f"rdy={x['eu_ready']} evx={x['eval_ext']} qc={x['q_cnt']} "
              f"qpop={x['q_pop']} occ={x['occupied']}{mark}")
    # chip raw rows around bus B
    crel = rec["cr"]
    # find chip absolute row for bus B T1
    cb1 = ca[B]["t1"]
    print("CHIP raw rows [row t bs addr qs]:")
    for ri in range(max(0, cb1 - win - 4), min(cb1 + 6, len(crel))):
        r = crel[ri]
        mark = " <== chip EU T1" if ri == cb1 else ""
        print(f"  {ri:4d} {TN.get(r['t'],r['t']):>2} "
              f"bs={BSN.get(r['bs_early'],r['bs_early']):<4} {r['ad_addr']:05x} "
              f"qs={r['qs']}{mark}")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "dump":
    # usage: eureq0_char.py dump SEED WS WMAX
    dump_case(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    sys.exit(0)


def dump_w0(seed, eu_addr, eu_bs_name, host="root@mister-nec", win=10):
    """Dump the w0 (all-zero wait) model + chip trace around the SAME architectural
    EU access (wait-invariant address), to see whether the +1 onset lateness is
    present-but-masked at w0 and whether asserting one state earlier would collide
    with a real w0 prefetch."""
    g = generate(f"fz{seed}", exts=())
    image, meta = compose(g)
    wv = [0] * 4096
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(i for i, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    TN = {1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4", 0: "Ti"}
    # find model bus access to eu_addr with matching bs
    target = {"MEMR": MEMR, "MEMW": MEMW}.get(eu_bs_name)
    krow = next((ri for ri, x in enumerate(kr)
                 if x["t"] == 1 and x["bs"] == target
                 and (x["addr"] & 0xFFFFF) == eu_addr), None)
    print(f"\n### w0  fz{seed}  {eu_bs_name}@{eu_addr:05x}")
    if krow is None:
        print("  (model access not found at w0)"); return
    print("MODEL w0 [row t bs addr state eu_req eval_ext q_cnt q_pop]:")
    for ri in range(max(0, krow - win), min(krow + 3, len(kr))):
        x = kr[ri]
        mk = " <== EU T1" if ri == krow else ""
        mk += " <== eu_req^" if (ri > 0 and x["eu_req"] == 1
                                 and kr[ri-1]["eu_req"] == 0) else ""
        print(f"  {ri:4d} {TN.get(x['t'],x['t']):>2} bs={BSN.get(x['bs'],x['bs']):<4} "
              f"{x['addr']:05x} {_sname(x['state']):<11} req={x['eu_req']} "
              f"evx={x['eval_ext']} qc={x['q_cnt']} qpop={x['q_pop']}{mk}")
    crow = next((ri for ri, r in enumerate(crel)
                 if r["t"] == 1 and r["bs_early"] == target
                 and (r["ad_addr"] & 0xFFFFF) == eu_addr), None)
    print("CHIP w0 [row t bs addr qs]:")
    if crow is None:
        print("  (chip access not found)"); return
    for ri in range(max(0, crow - win), min(crow + 3, len(crel))):
        r = crel[ri]
        mk = " <== EU T1" if ri == crow else ""
        print(f"  {ri:4d} {TN.get(r['t'],r['t']):>2} "
              f"bs={BSN.get(r['bs_early'],r['bs_early']):<4} {r['ad_addr']:05x} "
              f"qs={r['qs']}{mk}")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "w0":
    dump_w0(int(sys.argv[2]), int(sys.argv[3], 16), sys.argv[4])
    sys.exit(0)
