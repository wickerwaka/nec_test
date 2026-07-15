import json, sys
DATA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/class5_data.json"
recs = json.load(open(DATA))
TRAIN = {90003,90007,90015,90021,90030}
HELD  = {90042,90051,90063,90077,90088}
FRESH = {90400,90411,90422,90433,90444}

def feats(r):
    w=r["window"]; L=len(w)
    pops=[1 if c["pop"] else 0 for c in w]; push=[c["push"] for c in w]
    qc=[c["qc"] for c in w]; ev=[1 if c["ev"] else 0 for c in w]
    def age(arr):
        for a in range(L):
            if arr[L-1-a]: return a
        return L
    def nth(arr,k):
        c=0
        for a in range(L):
            if arr[L-1-a]:
                c+=1
                if c==k: return a
        return L
    f={}
    f["last_pop_age"]=age(pops); f["2nd_pop_age"]=nth(pops,2)
    for k in (2,4,8,12): f[f"popcnt{k}"]=sum(pops[-k:])
    for k in (4,8):
        m=0
        for i,p in enumerate(pops[-k:]): m|=(p<<i)
        f[f"popmask{k}"]=m
    for k in (4,8,12):
        s=qc[-k:]; f[f"minqc{k}"]=min(s); f[f"maxqc{k}"]=max(s)
    for o in range(1,13): f[f"qc_m{o}"]=qc[L-o] if o<=L else -1
    for t in (1,2,3,4): f[f"tsince_qc_le{t}"]=next((a for a in range(L) if qc[L-1-a]<=t),L)
    f["qc_trans"]=sum(1 for i in range(1,L) if qc[i]!=qc[i-1])
    lp=age(pops); f["push_to_lastpop"]=lp-age([1 if x else 0 for x in push])
    f["eval_to_lastpop"]=lp-age(ev); f["signed_flow"]=sum(push)-sum(pops)
    f["qc_at_lastpop"]=qc[L-1-lp] if lp<L else -1
    f["eu_state"]=w[-1]["st"]; f["gph"]=w[-1]["gph"]
    return f
for r in recs: r["f"]=feats(r)
FN=list(recs[0]["f"].keys())
train=[r for r in recs if r["seed"] in TRAIN]; held=[r for r in recs if r["seed"] in HELD]
fresh=[r for r in recs if r["seed"] in FRESH]
def cc(rs): i=sum(x["idle"] for x in rs); return (i,len(rs)-i)
print(f"train {cc(train)}; held {cc(held)}; fresh {cc(fresh)}  (idle,code)")
idle_tr=[r for r in train if r["idle"]]; code_tr=[r for r in train if not r["idle"]]

# unpurifiable core: idle cases feature-identical (all FN) to some CODE in TRAIN
codekey=set(tuple(r["f"][fn] for fn in FN) for r in code_tr)
core=[r for r in idle_tr if tuple(r["f"][fn] for fn in FN) in codekey]
print(f"TRAIN idle {len(idle_tr)}: FULL-FEATURE-identical-to-a-CODE (unpurifiable) = {len(core)}")

def lits():
    for fn in FN:
        vs=sorted(set(r["f"][fn] for r in train))
        if fn in ("eu_state","gph"):
            for v in vs: yield (fn,"==",v)
        else:
            for v in vs: yield (fn,"<=",v); yield (fn,">=",v)
LITS=list(lits())
def sat(r,l):
    v=r["f"][l[0]]; return {"==":v==l[2],"<=":v<=l[2],">=":v>=l[2]}[l[1]]

# greedy cover ALL purifiable train idle with pure-idle conjunctions
uncov=[r for r in idle_tr if id(r) not in set(id(x) for x in core)]
rules=[]; used=set()
while uncov:
    iset=list(uncov); cset=list(code_tr); conj=[]
    while cset and len(conj)<10:
        best=None
        for l in LITS:
            ni=[r for r in iset if sat(r,l)]; 
            if not ni: continue
            nc=[r for r in cset if sat(r,l)]
            sc=(len(cset)-len(nc), len(ni))
            if sc[0]<=0: continue
            if best is None or sc>best[0]: best=(sc,l,ni,nc)
        if best is None: break
        _,l,ni,nc=best; conj.append(l); iset=ni; cset=nc
    if cset or not iset:  # couldn't purify this batch -> unpurifiable remainder
        break
    rules.append(conj)
    for l in conj: used.add(l[0])
    covset=set(id(r) for r in iset); uncov=[r for r in uncov if id(r) not in covset]
covered=len([r for r in idle_tr if id(r) not in set(id(x) for x in uncov)]) - len(core)
print(f"\nGREEDY cover-all: {len(rules)} rules, {len(used)} features, "
      f"{sum(len(c) for c in rules)} literals; covered {covered}/{len(idle_tr)-len(core)} purifiable "
      f"(uncovered {len(uncov)})")
print(f"  features: {sorted(used)}")
comp = len(used)<=4 and len(rules)<=4 and not uncov and len(core)==0
print(f"  COMPRESSION: {'PASS' if comp else 'FAIL'} "
      f"(need <=4 feat & <=4 rules & 0 unpurifiable; got {len(used)}feat/{len(rules)}rules/"
      f"{len(core)}core/{len(uncov)}uncov)")
def predict(r): return any(all(sat(r,l) for l in c) for c in rules)
def ev(name,rs):
    idl=[r for r in rs if r["idle"]]; cod=[r for r in rs if not r["idle"]]
    rec=sum(predict(r) for r in idl); fp=sum(predict(r) for r in cod)
    anc=len(set((r["seed"],r["succ"]) for r in idl if predict(r)))
    print(f"  [{name}] recall {rec}/{len(idl)} | CODE FP {fp}/{len(cod)} "
          f"({100*fp/max(1,len(cod)):.3f}%) | anchors {anc}")
print("\nFROZEN-rule validation:"); ev("TRAIN",train); ev("HELD",held); ev("FRESH",fresh)
