import sys,json,gzip,glob; sys.path.insert(0,'.')

# --- fuzz-v2 T12: RETIRED, not broken.  See sw/retired_v1.py. -----------
import retired_v1  # noqa: E402
retired_v1.retire(
    't33_refix.py',
    'task #33 mc1 re-fix (CLOSED)',
    'reads testdata/campaigns/mc1, part of the DISCARDED corpus, and drives the board to do it',
    None)
# ------------------------------------------------------------------------

from pathlib import Path
from collections import defaultdict
import fuzz_campaign as fzc, check_seq
from causal_wrand import accesses, CODE
from class5_align import align
HOST='root@mister-nec'
rows=[json.loads(l) for l in open('testdata/campaigns/mc1/results.jsonl') if l.strip()]
def waited(r):
    w=r.get('waits') or {}; return bool(w.get('wrand')) or (w.get('fixed') or 0)>0
fam=[r for r in rows if waited(r) and (r.get('verdict')=='TIMING' or r.get('sub')=='done_mismatch')]
capmap={}
for f in glob.glob('testdata/campaigns/mc1/captures/*.json.gz'):
    b=Path(f).name.split('_')
    try: capmap[int(b[1])]=f
    except: pass
# stratified 60: 25 ENTER-soup, 20 non-ENTER soup, 15 done_mismatch
ent=[]; noent=[]; dm=[]
for r in fam:
    if r['tier']!='soup': continue
    ov={'force_contained':True,'strict':True}
    try: g=fzc.build(fzc.derive_case('mc1',r['k'],ov))
    except: continue
    hasent=0xc8 in bytes(g['instr'])
    if r.get('sub')=='done_mismatch' and len(dm)<15: dm.append((r,g))
    elif hasent and len(ent)<25: ent.append((r,g))
    elif not hasent and len(noent)<20: noent.append((r,g))
    if len(ent)>=25 and len(noent)>=20 and len(dm)>=15: break
sample=ent+noent+dm
def kindof(bs): return 'CODE' if bs==CODE else 'EU'
def censusleg(real,sim):
    rel=next((i for i,x in enumerate(real) if not x.get('rst')),0)
    ca=accesses(real[rel:]); ka=accesses(sim)
    if len(ca)<4 or len(ka)<4: return None
    try: pairs,_e,_s=align(ca,ka)
    except: return None
    kmap={ci:ki for ci,ki in pairs}; m=defaultdict(int)
    for i in sorted(kmap):
        if i==0 or (i-1) not in kmap: continue
        ki,kip=kmap[i],kmap[i-1]
        ge=(ca[i]['t1']-ca[i-1]['t1'])-(ka[ki]['t1']-ka[kip]['t1'])
        if ge: m['%s->%s'%(kindof(ca[i-1]['bs']),kindof(ca[i]['bs']))]+=abs(ge)
    return m
pre=defaultdict(int); post=defaultdict(int); npre=npost=0
img0,_=check_seq.compose({'regs':{},'instr':bytes([0x90]),'ram':None}) if False else (check_seq.testimage.compose(regs={},instr=bytes([0x90])) if hasattr(check_seq,'testimage') else (None,None))
import testimage


img0,_=testimage.compose(regs={},instr=bytes([0x90])); check_seq.run_chip(img0,HOST,use_core=False)
for r,g in sample:
    k=r['k']; w=r['waits']; wr=(w['wmax'],w['wseed']) if w.get('wrand') else None
    # PRE-fix census (from capture)
    d=json.load(gzip.open(capmap[k])); mp=censusleg(d['real'],d['sim'])
    if mp:
        for c,v in mp.items(): pre[c]+=v
        npre+=1
    # POST-fix: fresh hw-ab with fixed core
    image,_=check_seq.compose(g)
    try:
        if wr: chip=check_seq.run_chip(image,HOST,use_core=False,wrand=wr); core=check_seq.run_chip(image,HOST,use_core=True,wrand=wr)
        else: chip=check_seq.run_chip(image,HOST,use_core=False,waits=w['fixed']); core=check_seq.run_chip(image,HOST,use_core=True,waits=w['fixed'])
    except Exception as e: continue
    mq=censusleg(chip,core)
    if mq:
        for c,v in mq.items(): post[c]+=v
        npost+=1
check_seq.run_chip(img0,HOST,use_core=False)
print('POST-FIX RE-CAPTURE: %d seeds (pre %d, post %d)'%(len(sample),npre,npost))
tp=sum(pre.values()); tq=sum(post.values())
print('cell         PRE-fix-mass  POST-fix-mass  (same 60 seeds, chip vs pre/post fabric)')
for c in ('CODE->CODE','EU->CODE','CODE->EU','EU->EU'):
    print('  %-11s %6d (%4.1f%%)   %6d (%4.1f%%)'%(c,pre[c],100*pre[c]/max(1,tp),post[c],100*post[c]/max(1,tq)))
print('TOTAL pre=%d post=%d (delta %+d = ENTER-fix + any other fabric change)'%(tp,tq,tq-tp))
print('board idle')
