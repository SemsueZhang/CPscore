"""Exact finite checks and a simulation of the constructive upper bound for B."""
from collections import deque
from itertools import product
from functools import lru_cache
import argparse,json,random,subprocess

def reconstruct(n,edges,a,simulate=True):
 g=[[] for _ in range(n)]
 for u,v in edges:g[u].append(v);g[v].append(u)
 @lru_cache(None)
 def dp(u,p):
  ch=[dp(v,u) for v in g[u] if v!=p]
  s0=sum(x[0] for x in ch);s1=sum(x[1] for x in ch);best=sum(min(x) for x in ch)
  if a[u]==1:return best+1,best+1
  if a[u]>=2:return best+2,min(s1+1,best+2)
  f0=min(s0,best+2);f1=s0
  if ch:f1=min(f1,best+2+max(0,min(x[0]-x[1] for x in ch)))
  return f0,f1
 root=min(range(n),key=lambda u:dp(u,-1)[1]);predicted=n+dp(root,-1)[1]
 if not simulate:return predicted
 kind=['']*n;children=[[] for _ in range(n)];parent=[-1]*n
 def choose(u,p,mode):
  parent[u]=p;children[u]=[v for v in g[u] if v!=p];ch=children[u]
  vals=[dp(v,u) for v in ch];best=sum(min(x) for x in vals);s0=sum(x[0] for x in vals);s1=sum(x[1] for x in vals)
  modes=[0 if x[0]<=x[1] else 1 for x in vals]
  if a[u]==1:kind[u]='one'
  elif a[u]>=2:
   if mode==1 and s1+1<=best+2:kind[u]='high';modes=[1]*len(ch)
   else:kind[u]='paid'
  else:
   extra=max(0,min((x[0]-x[1] for x in vals),default=0)) if mode else 0
   activation=best+2+extra if ch or mode==0 else 10**9
   if s0<=activation:kind[u]='zero';modes=[0]*len(ch)
   else:
    kind[u]='active'
    if mode:
     witness=min(range(len(ch)),key=lambda i:vals[i][0]-min(vals[i]));modes[witness]=0
  for v,m in zip(ch,modes):choose(v,u,m)
 choose(root,-1,1)
 values=list(a);alive=[True]*n;count=0
 def mex(u):
  nonlocal count
  S={values[v] for v in g[u] if alive[v]};x=0
  while x in S:x+=1
  values[u]=x;count+=1;return x
 def dec(u):
  nonlocal count
  assert values[u]>0;values[u]-=1;count+=1
 def delete(u):
  nonlocal count
  assert alive[u] and values[u]==0 and sum(alive[v] for v in g[u])<=1
  alive[u]=False;count+=1
 def visit(u,hold=False):
  ch=children[u];t=kind[u]
  if t=='high':
   for v in ch:visit(v)
   assert mex(u)==0
  elif t=='zero':
   for v in ch:visit(v)
  elif t in ('one','paid'):
   before=[v for v in ch if kind[v] in ('high','one')]
   after=[v for v in ch if kind[v] not in ('high','one')]
   for v in before:visit(v)
   if t=='one':dec(u)
   else:
    x=mex(u);assert x in (0,1)
    if x:dec(u)
   for v in after:visit(v)
  else:
   before=[v for v in ch if kind[v]!='high'];after=[v for v in ch if kind[v]=='high']
   p=parent[u];external=p>=0 and alive[p] and values[p]==0;held=None
   if not external:
    assert before;held=before.pop()
   for v in before:visit(v)
   if held is not None:visit(held,True)
   assert mex(u)==1
   if held is not None:delete(held)
   for v in after:visit(v)
   dec(u)
  assert values[u]==0
  if not hold:delete(u)
 visit(root)
 assert not any(alive) and count==predicted,(n,edges,a,kind,count,predicted)
 return predicted

def exact_table(n,edges,M):
 """Reverse BFS over all connected live subtrees and weights 0..M, M>=n."""
 R=M+2;pw=[R**i for i in range(n)];g=[[] for _ in range(n)]
 for u,v in edges:g[u].append(v);g[v].append(u)
 dist=[-1]*(R**n);dist[0]=0;q=deque([0])
 while q:
  state=q.popleft();v=[];z=state
  for i in range(n):v.append(z%R);z//=R
  for u,d in enumerate(v):
   dest=[]
   if not d:
    if state==0 or sum(v[x]!=0 for x in g[u])==1:dest.append(state+pw[u])
   else:
    if d<R-1:dest.append(state+pw[u])
    S={v[x]-1 for x in g[u] if v[x]};mex=0
    while mex in S:mex+=1
    if d==mex+1:dest.extend(state+(prev-d)*pw[u] for prev in range(1,R))
   for to in dest:
    if dist[to]<0:dist[to]=dist[state]+1;q.append(to)
 def get(a):return dist[sum((x+1)*pw[i] for i,x in enumerate(a))]
 return get

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--solver');args=parser.parse_args()
 shapes=[(1,[]),(2,[(0,1)]),(3,[(0,1),(1,2)]),(4,[(i,i+1) for i in range(3)]),(4,[(0,i) for i in range(1,4)]),
  (5,[(i,i+1) for i in range(4)]),(5,[(0,i) for i in range(1,5)]),(5,[(0,1),(0,2),(0,3),(3,4)]),
  (6,[(i,i+1) for i in range(5)]),(6,[(0,i) for i in range(1,6)]),(6,[(0,1),(0,2),(0,3),(3,4),(3,5)]),(6,[(0,1),(1,2),(1,3),(3,4),(4,5)])]
 cases=[];wants=[];count=0;weight_states=0
 for n,E in shapes:
  M=max(n,3);get=exact_table(n,E,M)
  for a in product(range(M+1),repeat=n):
   want=get(a);got=reconstruct(n,E,a,simulate=False)
   assert got==want,(n,E,a,got,want);weight_states+=1
  for a in product(range(3),repeat=n):
   want=get(a);assert reconstruct(n,E,a)==want;cases.append((n,E,a));wants.append(want);count+=1
  print('exact_shape',n,E,flush=True)
 rng=random.Random(20261114)
 for _ in range(1000):
  n=rng.randrange(1,101);E=[(i,rng.randrange(i)) for i in range(1,n)]
  a=[rng.choice([0,0,1,2,3,10**9]) for _ in range(n)];want=reconstruct(n,E,a)
  cases.append((n,E,a));wants.append(want)
 if args.solver:
  text=str(len(cases))+'\n'+''.join(str(n)+'\n'+''.join(f'{u+1} {v+1}\n' for u,v in E)+' '.join(map(str,a))+'\n' for n,E,a in cases)
  got=list(map(int,subprocess.check_output([args.solver],input=text.encode()).split()))
  assert got==wants
 print(json.dumps({'exact_initial_weight_states':weight_states,'exact_category_states_with_operation_simulation':count,'random_operation_simulations':1000,'cpp_cases':len(cases) if args.solver else 0}),flush=True)
if __name__=='__main__':main()
