#!/usr/bin/env python3
"""dumpeu - TB run with +eudbg, merged r+d rows around an index range."""
import sys, subprocess, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, BS_NAME, T_NAME, QS_NAME, ROOT, BIN
from gen_seq import generate
import argparse

# EU state names (best-effort; numeric fallback)
ap = argparse.ArgumentParser()
ap.add_argument("seed", type=int)
ap.add_argument("--waits", type=int, default=1)
ap.add_argument("--lo", type=int, default=0)
ap.add_argument("--hi", type=int, default=40)
a = ap.parse_args()

g = generate(a.seed, exts=())
image, meta = compose(g)
td = tempfile.mkdtemp(prefix="eu_")
img = Path(td)/"img.hex"; out = Path(td)/"out.txt"
img.write_text("\n".join(f"{b:02x}" for b in image)+"\n")
subprocess.run([str(BIN), f"+bootimg={img}", f"+bootn=4200",
                f"+waits={a.waits}", f"+out={out}", "+eudbg"],
               capture_output=True, text=True, cwd=ROOT, timeout=300)
# r and d rows interleave; pair them by order (both emitted per recorded cycle)
rrows=[]; drows=[]
for line in out.read_text().splitlines():
    p=line.split()
    if not p: continue
    if p[0]=="r": rrows.append(p)
    elif p[0]=="d": drows.append(p)
# d row: d state q_pop q_avl q_cnt eu_wrap cur_wrap eu_addr eu_seg opc q_byte
#        bus_phase bus_ts q_fresh eu_started eu_req eu_ready
print(f"seed{a.seed} w{a.waits}  rows r={len(rrows)} d={len(drows)}")
print(f"{'idx':>4} {'t':<2} {'bs':<4} {'addr':<5} {'qs':<1} | "
      f"{'eust':>4} pop avl cnt | req rdy strt | opc addr")
n=min(len(rrows),len(drows))
for i in range(max(0,a.lo), min(n,a.hi)):
    r=rrows[i]; d=drows[i]
    t=T_NAME.get(int(r[1])); bs=BS_NAME[int(r[2])]; addr=int(r[5],16); qs=QS_NAME[int(r[3])]
    est=d[1]; pop=d[2]; avl=d[3]; cnt=d[4]; opc=d[9]; eaddr=d[7]
    req=d[15]; rdy=d[16]; strt=d[14]
    flush=d[17] if len(d)>17 else "?"; ext=d[18] if len(d)>18 else "?"
    evald=d[19] if len(d)>19 else "?"; ffast=d[20] if len(d)>20 else "?"
    print(f"{i:>4} {t:<2} {bs:<4} {addr:05x} {qs:<1} | "
          f"{est:>4} {pop:>3} {avl:>3} {cnt:>3} | {req:>3} {rdy:>3} {strt:>4} | "
          f"fl={flush} ext={ext} evd={evald} ff={ffast} | {opc:>3} {eaddr}")
