#!/usr/bin/env python3
"""exact_predict - EXACT-internal-state resume predictor go/no-go (Phase B).

The reverted beat-lookup used features RECONSTRUCTED from bus rows (occupancy,
beat) and plateaued at ~70% big-gap because reconstruction is lossy. This tests
the design-doc 4a claim directly: does the RTL's EXACT INTERNAL STATE (occupied
incl in-flight, q_aged, infl, bus_ts sub-phase, bus grid phase - read from the
TB via +eudbg) predict the CHIP's resume gap toward ~100%?

Method: run the TB (+eudbg) to get the exact internal state per cycle; extract
each prefetch-resume event with the TB's exact features at the crossing; align
to the CHIP's resume events by prefetch-T1 ORDER (both issue the same fetch
address sequence). Predictor key = exact features -> chip gap. Report closure
overall + big-gap, per feature set (ablation: coarse -> exact climb).

w0 is the CONTROL: TB==chip bit-exact, so the exact state IS the chip's; closure
there must be ~100% (validates the exact state is sufficient/deterministic). If
w1/w3 climb toward 100% as features approach exact, the scheduler is buildable.
"""
import argparse, json, subprocess, tempfile, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, ROOT, BIN
from gen_seq import generate
from measure import chip_ref

# d-row field indices (see tb_v30_core eudbg $fdisplay)
D = dict(state=1, q_pop=2, q_avl=3, q_cnt=4, bus_phase=11, bus_ts=12,
         eu_started=14, eu_req=15, eu_ready=16, occupied=21, q_aged=22, infl=23)


def tb_trace(seed, waits):
    g = generate(seed, exts=())
    image, meta = compose(g)
    td = tempfile.mkdtemp(prefix="ex_")
    img = Path(td)/"img.hex"; out = Path(td)/"out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in image)+"\n")
    subprocess.run([str(BIN), f"+bootimg={img}", "+bootn=4200",
                    f"+waits={waits}", f"+out={out}", "+eudbg"],
                   capture_output=True, text=True, cwd=ROOT, timeout=300)
    rrows=[]; drows=[]
    for line in out.read_text().splitlines():
        p=line.split()
        if not p: continue
        if p[0]=="r": rrows.append(p)
        elif p[0]=="d": drows.append(p)
    return rrows, drows


def tb_resumes(rrows, drows, P):
    """TB prefetch-resume events with EXACT internal features at the crossing."""
    n=min(len(rrows),len(drows)); out=[]
    prev_end=None; prevk=None; last_t1=None
    for i in range(n):
        r=rrows[i]; t=int(r[1]); bs=int(r[2]); addr=int(r[5],16)
        if t==1:
            if bs==4 and prev_end is not None and i-prev_end<40 and last_t1 is not None:
                # crossing = first idle after prev_end where occupied<=4
                cross=None
                for j in range(prev_end+1, i+1):
                    if int(drows[j][D["occupied"]])<=4:
                        cross=j; break
                if cross is not None:
                    d=drows[cross]
                    out.append(dict(
                        row=i,
                        addr=addr,
                        kind="EU" if prevk!=4 else "PF",
                        occ=int(d[D["occupied"]]),
                        qaged=int(d[D["q_aged"]]),
                        infl=int(d[D["infl"]]),
                        bts=int(d[D["bus_ts"]]),
                        bph=int(d[D["bus_phase"]]),
                        beat=(cross-last_t1)%P,       # mod-P grid beat at crossing
                        gap=i-cross,
                        raw_gap=i-prev_end-1))
            last_t1=i
        if t==5:
            prev_end=i; prevk=int(rrows[i][2])
    return out


def chip_resumes(rows):
    """CHIP prefetch-resume events (addr + gap) - order-aligned to TB."""
    from predict_resume import occ_trace
    oc=occ_trace([dict(t=r["t"], bs_early=r["bs_early"], qs=r["qs"],
                       ad_addr=r["ad_addr"], ube_n=r["ube_n"]) for r in rows])
    out=[]; prev_end=None; last_t1=None
    for i,r in enumerate(rows):
        t=r["t"]
        if t==1:
            if r["bs_early"]==4 and prev_end is not None and i-prev_end<40 and last_t1 is not None:
                cross=next((j for j in range(prev_end+1,i+1) if oc[j]<=4), None)
                if cross is not None:
                    out.append(dict(addr=r["ad_addr"]&0xFFFFF, gap=i-cross,
                                    raw_gap=i-prev_end-1))
            last_t1=i
        if t==5: prev_end=i
    return out


FEATURES = [
    ("kind,occ",              lambda e:(e["kind"], e["occ"])),
    ("+bts (sub-phase)",      lambda e:(e["kind"], e["occ"], e["bts"])),
    ("+qaged",                lambda e:(e["kind"], e["occ"], e["bts"], e["qaged"])),
    ("+infl",                 lambda e:(e["kind"], e["occ"], e["bts"], e["qaged"], e["infl"])),
    ("+bph (grid phase)",     lambda e:(e["kind"], e["occ"], e["bts"], e["qaged"], e["infl"], e["bph"])),
    ("occ+BEAT (mod-P)",      lambda e:(e["kind"], e["occ"], e["beat"])),
    ("BEAT only",             lambda e:(e["kind"], e["beat"])),
]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--waits", default="0,1,3")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start", type=int, default=90000)
    ap.add_argument("--clean-prefix", action="store_true",
                    help="only resume events BEFORE the first chip-vs-TB "
                         "divergence (TB internal state == chip state there)")
    ap.add_argument("--dump", action="store_true",
                    help="dump the (kind,occ)->gap law + mispredicted big-gaps")
    a=ap.parse_args()
    from check_seq import diff
    for w in [int(x) for x in a.waits.split(",")]:
        evs=[]
        for s in range(a.start, a.start+a.seeds):
            rr,dd=tb_trace(s,w)
            tb=tb_resumes(rr,dd,4+w)
            chip_raw=chip_ref(s,w,a.host)
            chip=chip_resumes(chip_raw)
            # first chip-vs-TB divergence row (TB state == chip state before it)
            div=10**9
            if a.clean_prefix:
                sim=[{"t":int(r[1]),"bs_early":int(r[2]),"qs":int(r[3]),
                      "ube_n":int(r[4]),"ad_addr":int(r[5],16),
                      "ad_data":int(r[6],16),"ps":int(r[7],16)} for r in rr]
                real=[dict(r,t_state=r["t"]) for r in chip_raw]
                _,first,_,_=diff(real,sim,maxprint=0)
                div=first if first is not None else 10**9
            # order-align by index; keep addr-agreeing events (arch-identical)
            m=min(len(tb),len(chip))
            for k in range(m):
                if tb[k]["addr"]==chip[k]["addr"] and tb[k]["row"]<div:
                    e=dict(tb[k]); e["cgap"]=chip[k]["gap"]
                    e["big"]=chip[k]["raw_gap"]>2
                    evs.append(e)
        if not evs:
            print(f"w{w}: no aligned events"); continue
        big=[e for e in evs if e["big"]]
        print(f"=== w{w}: N={len(evs)} big={len(big)} (exact-state -> CHIP gap) ===")
        for name,keyf in FEATURES:
            tab=defaultdict(Counter)
            for e in evs: tab[keyf(e)][e["cgap"]]+=1
            pr=lambda e:tab[keyf(e)].most_common(1)[0][0]
            ov=100*sum(pr(e)==e["cgap"] for e in evs)/len(evs)
            bg=100*sum(pr(e)==e["cgap"] for e in big)/len(big) if big else 0
            print(f"    {name:22} overall={ov:5.1f}%  big-gap={bg:5.1f}%")
        if a.dump:
            # the (kind, exact-occ) -> chip-gap law table
            tab=defaultdict(Counter)
            for e in evs: tab[(e["kind"],e["occ"])][e["cgap"]]+=1
            print(f"  --- (kind, exact-occ) -> chip gap [w{w}] ---")
            for k in sorted(tab):
                c=tab[k]; tot=sum(c.values())
                print(f"    {k[0]} occ={k[1]}: n={tot:4} gaps={dict(c.most_common(5))}")
            # big-gap cases mispredicted by (kind,occ): show full exact state
            tab2=defaultdict(Counter)
            for e in evs: tab2[(e["kind"],e["occ"])][e["cgap"]]+=1
            prf=lambda e:tab2[(e["kind"],e["occ"])].most_common(1)[0][0]
            miss=[e for e in big if prf(e)!=e["cgap"]]
            print(f"  --- big-gap MISSES by (kind,occ): {len(miss)}/{len(big)} ---")
            mc=Counter((e["kind"],e["occ"],e["qaged"],e["infl"],e["bts"],e["bph"],e["cgap"]) for e in miss)
            for key,n in mc.most_common(12):
                print(f"    kind={key[0]} occ={key[1]} qaged={key[2]} infl={key[3]} "
                      f"bts={key[4]} bph={key[5]} -> cgap={key[6]}  (x{n})")


if __name__ == "__main__":
    main()
