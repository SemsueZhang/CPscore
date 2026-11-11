import argparse,subprocess,random,time,json
from verify_a import step
parser=argparse.ArgumentParser();parser.add_argument('--solver',required=True);parser.add_argument('--large',action='store_true');args=parser.parse_args()
P=998244353;rng=random.Random(20261112)
cases=[('?1','1?'),('???','0??'),('??1?','?0??'),('1??01','10??1')]
for _ in range(600):
 n=rng.randrange(2,15);cases.append((''.join(rng.choice('01?') for _ in range(n)),''.join(rng.choice('01?') for _ in range(n))))
for n in [50,64,65,100,127,128,129,200,300]:
 for _ in range(15):
  a=''.join(rng.choice('00????') for _ in range(n));b=''.join(rng.choice('00????') for _ in range(n))
  if rng.random()<.5:
   a=list(a);b=list(b)
   for __ in range(rng.randrange(1,6)):a[rng.randrange(n)]='1'
   a=''.join(a);b=''.join(b)
  cases.append(('1'+a[1:-1]+'1','1'+b[1:-1]+'1'))

def dp(a,b):
 n=len(a)
 if '0' in [a[0],a[-1],b[0],b[-1]]:return 0
 f={(0,1):1}
 for i in range(1,n+1):
  f=step(f)
  if i<n:
   g={}
   for (j,x),v in f.items():
    if j+x<1:continue
    aa=j==1;bb=j+x==1
    if (a[i-1]=='?' or int(a[i-1])==aa) and (b[i]=='?' or int(b[i])==bb):g[j,x]=v%P
   f=g
 return f.get((1,-1),0)%P
text=str(len(cases))+'\n'+''.join(str(len(a))+'\n'+a+'\n'+b+'\n' for a,b in cases)
out=subprocess.check_output([args.solver],input=text.encode()).split()
for (a,b),v in zip(cases,out):
 want=dp(a,b);assert int(v)==want,(len(a),a,b,int(v),want)
print('cpp_matched_quadratic',len(cases),flush=True)
# Maximum-size single segments exercise the complete convolution route.
if not args.large:raise SystemExit(0)
n=200000
large=[('?'*n,'?'*n),('1'+'0'*(n-2)+'1','1'+'0'*(n-2)+'1'),('1'+''.join(rng.choice('0?') for _ in range(n-2))+'1','1'+''.join(rng.choice('0?') for _ in range(n-2))+'1')]
for i,(a,b) in enumerate(large):
 text=f'1\n{n}\n{a}\n{b}\n';start=time.perf_counter();ans=subprocess.check_output([args.solver],input=text.encode()).decode().strip()
 print('large',i,'seconds',round(time.perf_counter()-start,3),'answer',ans,flush=True)
