#!/usr/bin/env python3
"""EXTENDED CORPUS: emit ALL aligned transitions, not just CODE->CODE.

WHY (the instrument is broken): the proxy/census ratio went 1.03 -> 1.04 ->
1.72. The proxy only ever saw CODE->CODE ALIGNED opportunities. Of the 188
census units left after the pf_drain deletion, 42 (22%) are transitions it is
STRUCTURALLY BLIND TO (CODE->MEMW -2:13, MEMW->CODE -1:12, CODE->MEMR -2:2).
The 1.03 ratio held ONLY while CODE->CODE dominated the mass; removing that mass
promoted the blind spot from negligible to a fifth of everything. Until this is
fixed no board-free accept/reject is sound.

THE CORPUS FILTER EXCLUDED THESE TRANSITIONS, NOT THE CHIP. class5_bandage.py:138
  if cb[i] != CODE or cb[i-1] != CODE: continue
cidle (idle clocks between predecessor T4 and successor T1) is well-defined for
ANY transition, so the exclusion was never physical.

ONE CHANGE, FOUR QUESTIONS: (a) repairs the proxy; (b) unblocks Arm D, whose
signal lives in DATA->CODE pairs (CODE->CODE adjacent pairs are blind to the
DATA lever by construction); (c) opens the law's unfitted non-CODE domain;
(d) enables the lowband subsumption retest on its 21 flush/non-CODE rows.

NEW AXES, folded into this same regeneration (no second pass):
  - QS POP CLASS per pop (F/RNI vs S/NXT). We record QS every cycle and have
    NEVER keyed on it.
  - ADDRESS PARITY (the HL flip-flop) for predecessor AND successor.
  - SUCCESSOR-SIDE frame fields. Every frame we have used anchors on the
    PREDECESSOR; nobody has keyed on the fetch being SCHEDULED.

Chip = ground truth (use_core=False, read-only, no flash).
"""
import sys, json, gzip, time, argparse, traceback
import random as _r
from pathlib import Path
from collections import defaultdict

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from causal_wrand import (generate, compose, run_chip, run_tb_internal,
                          accesses, bs_stream, CODE)

OUT = SW / "class5_alltrans.jsonl.gz"
LOG = SW / "class5_alltrans.log"

BSNAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
          6: "MEMW", 7: "PASV"}


def wait_vectors():
    wd = {"w1": [1] * 4096, "w2": [2] * 4096, "w3": [3] * 4096}
    for (ws, wm) in [(4, 3), (7, 7)]:
        rr = _r.Random((ws << 8) | wm)
        wd[f"r{ws}.{wm}"] = [rr.randint(0, wm) for _ in range(4096)]
    return wd


def opportunities(seed, host, image, wv, wname, tag, out):
    """EVERY aligned transition, with chip cidle as ground truth."""
    cr = run_chip(image, host, use_core=False, wvec=wv)
    crel = cr[next(k for k, r in enumerate(cr) if not r["rst"]):]
    kr = run_tb_internal(image, 4200, wv)
    ca = accesses(crel)
    ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                        ad_addr=x["addr"], ad_data=0) for x in kr])
    kt1, kt4, bi = {}, {}, -1
    for ri, x in enumerate(kr):
        if x["t"] == 1:
            bi += 1; kt1[bi] = ri
        if x["t"] == 5:
            kt4[bi] = ri
    cb, kb = bs_stream(ca), bs_stream(ka)
    n = min(len(cb), len(kb))
    D = next((j for j in range(n)
              if cb[j] != kb[j] or ca[j]["addr"] != ka[j]["addr"]), n)
    nopp = 0
    for i in range(1, D):
        # NO CODE->CODE FILTER. Every aligned transition qualifies.
        if ca[i - 1]["t4"] is None or (i - 1) not in kt4 or i not in kt1:
            continue
        de = kt4[i - 1] + 1 if (kt4[i - 1] + 1) < len(kr) else kt4[i - 1]
        e = kr[de]
        cidle = sum(1 for r in range(ca[i - 1]["t4"] + 1, ca[i]["t1"])
                    if crel[r]["t"] == 0)
        midle = sum(1 for r in range(kt4[i - 1] + 1, kt1[i])
                    if kr[r]["t"] == 0)
        label = "go" if cidle <= 1 else ("pause" if cidle >= 3 else "amb")
        # ---- NEW AXES ----
        # QS pop class over the window: QS codes seen (1=F/RNI, 2=E, 3=S/NXT)
        qsw = defaultdict(int)
        for r in range(kt4[i - 1], min(kt1[i] + 1, len(kr))):
            q = kr[r]["qs"]
            if q:
                qsw[q] += 1
        rec = dict(seed=seed, w=wname, tag=tag, i=i,
                   bs_pred=BSNAME.get(cb[i - 1], str(cb[i - 1])),
                   bs_succ=BSNAME.get(cb[i], str(cb[i])),
                   cidle=cidle, model_cidle=midle, ge=midle - cidle,
                   label=label, pred_tw=ka[i - 1]["tw"], succ_tw=ka[i]["tw"],
                   # predecessor + successor ADDRESS PARITY (HL flip-flop)
                   pred_par=ca[i - 1]["addr"] & 1, succ_par=ca[i]["addr"] & 1,
                   # QS pop class over the window
                   qs_F=qsw.get(1, 0), qs_E=qsw.get(2, 0), qs_S=qsw.get(3, 0),
                   # predecessor-frame (the only frame ever used)
                   occ=e["occupied"], q_cnt=e["q_cnt"], cnt_next=e["cnt_next"],
                   eu_req=e["eu_req"], eu_consuming=e["eu_consuming"],
                   q_aged=e["q_aged"], pf_lim=e["pf_lim"],
                   # SUCCESSOR-SIDE frame: state at the successor's own T1
                   succ_occ=kr[kt1[i]]["occupied"],
                   succ_qcnt=kr[kt1[i]]["q_cnt"],
                   succ_eu_req=kr[kt1[i]]["eu_req"])
        out.append(rec)
        nopp += 1
    return nopp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--discovery", type=int, nargs="+",
                    default=list(range(90000, 90008)))
    ap.add_argument("--heldout", type=int, nargs="+",
                    default=list(range(91000, 91006)))
    a = ap.parse_args()
    logf = LOG.open("w")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    log(f"start {time.ctime()}  ALL-TRANSITION corpus (no CODE->CODE filter)")
    out = []
    wvs = wait_vectors()
    for tag, seeds in (("disc", a.discovery), ("held", a.heldout)):
        for seed in seeds:
            g = generate(f"fz{seed}", exts=())
            image, meta = compose(g)
            for wname, wv in wvs.items():
                t0 = time.time()
                try:
                    k = opportunities(seed, a.host, image, wv, wname, tag, out)
                    log(f"  {tag} fz{seed} {wname}: {k} opps "
                        f"({time.time()-t0:.0f}s) total={len(out)}")
                except Exception as ex:
                    log(f"  {tag} fz{seed} {wname}: ERR {ex}")
                    traceback.print_exc()
                with gzip.open(OUT, "wt") as f:      # incremental
                    for r in out:
                        f.write(json.dumps(r) + "\n")
    tr = defaultdict(int)
    for r in out:
        tr[(r["bs_pred"], r["bs_succ"])] += 1
    log(f"\ntransitions captured: {len(out)} rows")
    for k, v in sorted(tr.items(), key=lambda x: -x[1])[:12]:
        log(f"  {k[0]:>5} -> {k[1]:<5}: {v}")
    cc = sum(v for k, v in tr.items() if k == ("CODE", "CODE"))
    log(f"\n  CODE->CODE (what the old corpus saw): {cc}")
    log(f"  NON-CODE->CODE (the blind spot): {len(out)-cc}")
    log(f"wrote {OUT}")
    logf.close()


if __name__ == "__main__":
    main()
