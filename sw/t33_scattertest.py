import sys,json,gzip,glob,random; sys.path.insert(0,'.')
from pathlib import Path
from collections import defaultdict
from causal_wrand import accesses, CODE
from class5_align import align
CAP=Path('testdata/campaigns/mc1/captures')
rows=[json.loads(l) for l in open('testdata/campaigns/mc1/results.jsonl') if l.strip()]
def waited(r):
    w=r.get('waits') or {}; return bool(w.get('wrand')) or (w.get('fixed') or 0)>0
fam=[r for r in rows if waited(r) and (r.get('verdict')=='TIMING' or r.get('sub')=='done_mismatch')]
capmap={}
for f in glob.glob(str(CAP/'*.json.gz')):
    b=Path(f).name.split('_')
    try: capmap[int(b[1])]=f
    except: pass
BSN={4:'C',5:'r',6:'w',2:'o',1:'i',0:'a',3:'h'}
# extract all signed impulses with context, tagged by seed (for held-out split)
impulses=[]  # (seed, ge, ctx_tuple)
for r in fam:
    k=r['k']; f=capmap.get(k)
    if not f: continue
    try: d=json.load(gzip.open(f))
    except: continue
    real=d['real']; rel=next((i for i,x in enumerate(real) if not x.get('rst')),0)
    ca=accesses(real[rel:]); ka=accesses(d['sim'])
    if len(ca)<4 or len(ka)<4: continue
    try: pairs,_e,_s=align(ca,ka)
    except: continue
    kmap={ci:ki for ci,ki in pairs}
    keys=sorted(kmap)
    for i in keys:
        if i<2 or (i-1) not in kmap: continue
        ki,kip=kmap[i],kmap[i-1]
        ge=(ca[i]['t1']-ca[i-1]['t1'])-(ka[ki]['t1']-ka[kip]['t1'])
        if ge==0: continue
        pp = BSN.get(ca[i-2]['bs'],'?') if (i-2) in kmap else '?'
        ctx=(BSN.get(ca[i-1]['bs'],'?'),BSN.get(ca[i]['bs'],'?'),ca[i-1]['tw'],ca[i]['tw'],ca[i]['addr']&1,pp)
        impulses.append((k,ge,ctx))
print('total nonzero impulses:',len(impulses),' total|ge|=',sum(abs(g) for _,g,_ in impulses))
# held-out: split seeds
seeds=sorted(set(k for k,_,_ in impulses)); random.Random(7).shuffle(seeds)
half=set(seeds[:len(seeds)//2])
train=[x for x in impulses if x[0] in half]; test=[x for x in impulses if x[0] not in half]
# conditional signed mean per ctx on TRAIN
ctxsum=defaultdict(lambda:[0,0]) # ctx -> [sum_ge, n]
for k,ge,ctx in train:
    ctxsum[ctx][0]+=ge; ctxsum[ctx][1]+=1
# predict sign on TEST by train conditional mean; measure accuracy + mass explained
correct=0; total=0; mass_pred=0; mass_unpred=0; base_correct=0
POS=sum(1 for _,g,_ in train if g>0); NEG=len(train)-POS
majority=1 if POS>=NEG else -1
for k,ge,ctx in test:
    s,n=ctxsum.get(ctx,[0,0])
    pred = (1 if s>0 else -1 if s<0 else majority) if n>=8 else majority
    total+=1
    if (pred>0)==(ge>0): correct+=1
    if (majority>0)==(ge>0): base_correct+=1
    # mass explained: if ctx conditional mean has consistent sign matching this impulse AND |mean| strong
    if n>=8 and abs(s/n)>=0.5 and (s>0)==(ge>0):
        mass_pred+=abs(ge)
    else:
        mass_unpred+=abs(ge)
print('HELD-OUT sign prediction: ctx-model %.1f%% vs majority-baseline %.1f%% (n=%d)'%(100*correct/total,100*base_correct/total,total))
print('TEST mass: context-PREDICTABLE(|cond mean|>=0.5, held-out) = %d ; UNPREDICTED = %d ; frac predictable=%.1f%%'%(mass_pred,mass_unpred,100*mass_pred/(mass_pred+mass_unpred)))
# strongest predictive context cells (train, |mean|>=0.5, n>=30)
strong=sorted([(ctx,s/n,n,abs(s)) for ctx,(s,n) in ctxsum.items() if n>=30 and abs(s/n)>=0.5],key=lambda x:-x[3])
print('strongest signed-law context cells (prev,cur,ptw,ctw,par,pp): mean, n:')
for ctx,mean,n,_ in strong[:14]: print('  ',ctx,'mean=%+.2f n=%d'%(mean,n))
