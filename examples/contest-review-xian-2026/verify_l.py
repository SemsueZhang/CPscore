from itertools import combinations
from collections import defaultdict,deque
import random,json
from pathlib import Path

class Oracle:
    def __init__(self,n,edges):
        self.n=n;self.g=[set() for _ in range(n)]
        for a,b in edges:self.g[a].add(b);self.g[b].add(a)
        self.calls=0;self.cost=0
    def ask(self,a,b,S):
        assert a!=b and a not in S and b not in S and len(S)==len(set(S))
        self.calls+=1;self.cost+=max(len(S)-1,0)
        return connected(self.g,a,b,set(S))

def connected(g,a,b,S):
    seen={a};todo=[a]
    for u in todo:
        for v in g[u]:
            if v not in S and v not in seen:seen.add(v);todo.append(v)
    return b in seen

def solve_l(n,ask):
    root=0;anc=[set() for _ in range(n)]
    for v in range(1,n):
        for z in range(1,n):
            if z!=v and not ask(root,v,[z]):anc[v].add(z)
    groups=defaultdict(list)
    for v in range(1,n):groups[tuple(sorted(anc[v]))].append(v)
    blocks=[]
    for A,U in groups.items():
        p=max(A,key=lambda x:len(anc[x])) if A else root
        left=U[:]
        while left:
            u=left.pop();W=[u];other=[]
            for v in left:
                if ask(u,v,[p]):W.append(v)
                else:other.append(v)
            left=other;blocks.append((p,W))
    out=[]
    for p,W in blocks:
        s=len(W)
        if s==1:out.append((p,W[0]));continue
        anchor=W[0];e=W[1]
        for z in W[2:]:
            if not ask(anchor,z,[p,e]):e=z
        def sort(X):
            if len(X)<2:return X
            h=len(X)//2;A=sort(X[:h]);B=sort(X[h:]);i=j=0;C=[]
            while i<len(A) and j<len(B):
                if ask(e,A[i],[p,B[j]]):C.append(A[i]);i+=1
                else:C.append(B[j]);j+=1
            return C+A[i:]+B[j:]
        order=[e]+sort([x for x in W if x!=e])
        out.append((p,order[0]));out.extend(zip(order,order[1:]));out.append((order[-1],p))
    return {tuple(sorted(e)) for e in out}

def cactus(n,edges):
    g=[[] for _ in range(n)]
    for i,(a,b) in enumerate(edges):g[a].append((b,i));g[b].append((a,i))
    tin=[-1]*n;low=[0]*n;clock=0;stack=[];okay=True
    def dfs(u,pe):
        nonlocal clock,okay
        tin[u]=low[u]=clock;clock+=1
        for v,e in g[u]:
            if e==pe:continue
            if tin[v]<0:
                stack.append(e);dfs(v,e);low[u]=min(low[u],low[v])
                if low[v]>=tin[u]:
                    B=[]
                    while True:
                        x=stack.pop();B.append(x)
                        if x==e:break
                    if len(B)>1:
                        deg=defaultdict(int)
                        for x in B:
                            a,b=edges[x];deg[a]+=1;deg[b]+=1
                        if len(B)!=len(deg) or any(v!=2 for v in deg.values()):okay=False
            elif tin[v]<tin[u]:stack.append(e);low[u]=min(low[u],tin[v])
    dfs(0,-1)
    return okay and all(x>=0 for x in tin)

def all_cacti(n):
    pairs=list(combinations(range(n),2));out=[]
    for mask in range(1<<len(pairs)):
        k=mask.bit_count()
        if k<n-1 or k>3*(n-1)//2:continue
        E=[pairs[i] for i in range(len(pairs)) if mask>>i&1]
        if cactus(n,E):out.append(E)
    return out

def check(n,E):
    o=Oracle(n,E);out=solve_l(n,o.ask)
    assert out=={tuple(sorted(e)) for e in E},(n,E,out)
    assert o.calls<=3*n*n and o.cost<=n*(n-1).bit_length()+2*n,(n,o.calls,o.cost)
    return o.calls,o.cost

def random_cactus(n,rng):
    E=[];size=1
    while size<n:
        p=rng.randrange(size)
        if size+2<=n and rng.random()<.55:
            k=rng.randint(2,min(n-size,12));vs=[p]+list(range(size,size+k))
            E+=list(zip(vs,vs[1:]))+[(vs[-1],p)];size+=k
        else:E.append((p,size));size+=1
    P=list(range(n));rng.shuffle(P)
    return [(P[a],P[b]) for a,b in E]

def main():
    rng=random.Random(20261111);cnt=0;pool={};largest=(0,0)
    for n in range(2,7):
        arr=all_cacti(n);pool[n]=arr
        for E in arr:
            c=check(n,E);cnt+=1;largest=max(largest,c)
        print('exhaustive',n,len(arr),flush=True)
    rc=0
    for n in [8,16,32,64,128]:
        for _ in range(25):check(n,random_cactus(n,rng));rc+=1
        check(n,[(i,i+1) for i in range(n-1)])
        check(n,[(0,i) for i in range(1,n)])
        check(n,[(i,(i+1)%n) for i in range(n)])
        rc+=3
    adaptive=0
    for n in range(3,6):
        for trial in range(12):
            possible=[Oracle(n,E).g for E in pool[n]];calls=cost=0
            def ask(a,b,S):
                nonlocal possible,calls,cost
                calls+=1;cost+=max(len(S)-1,0)
                A=[];B=[]
                for g in possible:(A if connected(g,a,b,set(S)) else B).append(g)
                use=len(A)>len(B) or (len(A)==len(B) and rng.randrange(2)==0)
                possible=A if use else B
                return use
            out=solve_l(n,ask)
            assert possible
            for g in possible:
                assert out=={(u,v) for u in range(n) for v in g[u] if u<v}
            assert calls<=3*n*n and cost<=n*(n-1).bit_length()+2*n
            adaptive+=1
    data={'exhaustive_fixed_cacti_n2_to6':cnt,'random_and_structured_cacti_n8_to128':rc,'adaptive_transcript_cases_n3_to5':adaptive}
    Path(__file__).with_name('l-checks.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data),flush=True)
if __name__=='__main__':main()
