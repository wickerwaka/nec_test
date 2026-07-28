import sys,json,gzip,glob; sys.path.insert(0,'.')
from pathlib import Path
from causal_wrand import accesses
from class5_align import align
import statistics as st
CAP=Path('testdata/campaigns/mc1/captures')
rows=[json.loads(l) for l in open('testdata/campaigns/mc1/results.jsonl') if l.strip()]
def waited(r):
    w=r.get('waits') or {}; return bool(w.get('wrand')) or (w.get('fixed') or 0)>0
capmap={}
for f in glob.glob(str(CAP/'*.json.gz')):
    b=Path(f).name.split('_')
    try: capmap[int(b[1])]=f
    except: pass
def slopes(seeds, cutoff=80):
    # cumulative signed drift vs ordinal, slope over first `cutoff` aligned intervals
    sl=[]; cov=[]
    for k in seeds:
        f=capmap.get(k)
        if not f: continue
        try: d=json.load(gzip.open(f))
        except: continue
        real=d['real']; rel=next((i for i,x in enumerate(real) if not x.get('rst')),0)
        ca=accesses(real[rel:]); ka=accesses(d['sim'])
        if len(ca)<10 or len(ka)<10: continue
        try: pairs,_e,_s=align(ca,ka)
        except: continue
        kmap={ci:ki for ci,ki in pairs}; keys=sorted(kmap)
        cov.append(len(keys)/max(1,len(ca)))
        cum=0; series=[]
        cnt=0
        for i in keys:
            if i==0 or (i-1) not in kmap: continue
            ki,kip=kmap[i],kmap[i-1]
            cum+=(ca[i]['t1']-ca[i-1]['t1'])-(ka[ki]['t1']-ka[kip]['t1'])
            series.append(cum); cnt+=1
            if cnt>=cutoff: break
        if len(series)>=20:
            sl.append((series[-1])/len(series))  # avg drift per interval over prefix
    return sl,cov
tim=[r['k'] for r in rows if waited(r) and r.get('verdict')=='TIMING']
dm=[r['k'] for r in rows if waited(r) and r.get('sub')=='done_mismatch']
for name,seeds in (('TIMING',tim),('done_mismatch',dm)):
    sl,cov=slopes(seeds)
    print('%s: %d seeds | early-prefix drift SLOPE per interval: median=%.3f mean=%.3f | neg-slope=%d pos-slope=%d | aligned-coverage median=%.2f'%(
        name,len(sl),st.median(sl),st.mean(sl),sum(1 for s in sl if s<-0.02),sum(1 for s in sl if s>0.02),st.median(cov)))
