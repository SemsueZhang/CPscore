from itertools import permutations,product
from collections import Counter,defaultdict
from math import factorial
import random,json,argparse,subprocess

def step(f):
 g=defaultdict(int)
 for (j,x),v in f.items():
  for J,X,c in [(j+1,x,j+x),(j,x,2*j+x-1),(j-1,x,j-1),(j,x-1,x+1),(j+1,x-1,x+1)]:
   if c>0 and J>=1 and X>=-1 and J+X>=0:g[J,X]+=v*c
 return g

def kernel(t):
 f=factorial(t)
 return [[(t+1)*f,2*t*f,t*(t-1)*f],[0,f,t*f],[0,0,(t+1)*f]]
def start(t):
 f=factorial(t)
 return [f,2*f,(t-1)*f]
def ending(t):return [((t-1)*factorial(t) if t>=2 else 0),factorial(t) if t else 0,factorial(t) if t else 0]
def allowed(a,b):
 out=[]
 for x,y in [(1,0),(1,1),(0,1),(0,0)]:out.append((a=='?' or int(a)==x) and (b=='?' or int(b)==y))
 return out

def solve(a,b):
 n=len(a)
 if '0' in [a[0],a[-1],b[0],b[-1]]:return 0
 prev=0;init=None
 forced=[i for i in range(1,n) if a[i-1]=='1' or b[i]=='1']+[n]
 for end in forced:
  corr=[];last=None
  for i in range(prev+1,end+1):
   t=i-prev
   if i==n:
    base=factorial(n) if init is None else sum(init[s]*ending(t)[s] for s in range(3))
    for j,u in corr:
     z=ending(i-j);base+=sum(u[s]*z[s] for s in range(3))
    return base
   K=kernel(t)
   cur=start(i) if init is None else [sum(init[s]*K[s][v] for s in range(3)) for v in range(3)]
   for j,u in corr:
    K=kernel(i-j)
    for v in range(3):cur[v]+=sum(u[s]*K[s][v] for s in range(3))
   mask=allowed(a[i-1],b[i])
   if i==end:
    last=[cur[s] if mask[s] else 0 for s in range(3)]
   else:
    assert mask[3]
    corr.append((i,[-cur[s] if not mask[s] else 0 for s in range(3)]))
  init=last;prev=end

def flags(p):
 n=len(p);aa=[];bb=[]
 for i in range(1,n):
  z=p[:i];aa.append(max(z)-min(z)+1==i)
  z=p[i:];bb.append(max(z)-min(z)+1==n-i)
 return list(zip(aa,bb))
def brute(a,b,patterns):
 return sum(count for f,count in patterns.items() if all((a[i]=='?' or int(a[i])==x) and (b[i+1]=='?' or int(b[i+1])==y) for i,(x,y) in enumerate(f)))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--solver');args=parser.parse_args()
 rng=random.Random(20261111);checks=0;ex=0
 cpp_cases=[];cpp_wants=[]
 for n in range(2,9):
  pats=Counter(tuple(flags(p)) for p in permutations(range(n)))
  cases=product('01?',repeat=2*(n-1)) if n<=5 else (tuple(rng.choice('01?') for _ in range(2*(n-1))) for _ in range(1500))
  num=0
  for c in cases:
   a=''.join(c[:n-1])+'1';b='1'+''.join(c[n-1:])
   got=solve(a,b);want=brute(a,b,pats)
   assert got==want,(n,a,b,got,want)
   if args.solver:cpp_cases.append((a,b));cpp_wants.append(want%998244353)
   checks+=1;num+=1
   if n<=5:ex+=1
  print(n,num,flush=True)
 # Check transition kernels against the weighted insertion recurrence.
 states=[(1,1),(1,0),(2,-1)]
 for s in range(3):
  f={states[s]:1}
  for t in range(31):
   assert [f.get(z,0) for z in states]==kernel(t)[s]
   assert f.get((1,-1),0)==ending(t)[s]
   f=step(f)
 f={(0,1):1}
 for t in range(1,31):
  f=step(f)
  assert [f.get(z,0) for z in states]==start(t)
  if t>=2:assert f.get((1,-1),0)==factorial(t)
 if args.solver:
  text=str(len(cpp_cases))+'\n'+''.join(f'{len(a)}\n{a}\n{b}\n' for a,b in cpp_cases)
  got=list(map(int,subprocess.check_output([args.solver],input=text.encode()).split()))
  assert got==cpp_wants
  print('cpp_matched_permutation_counts',len(cpp_cases),flush=True)
 print(json.dumps({'constraint_patterns_exhaustive_n2_to5':ex,'random_patterns_n6_to8':checks-ex,'kernel_lengths':30}),flush=True)
if __name__=='__main__':main()
