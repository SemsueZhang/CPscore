import argparse,subprocess,random,time,json
parser=argparse.ArgumentParser();parser.add_argument('--solver',required=True);args=parser.parse_args()
rng=random.Random(20261117);n=m=200000;solver=args.solver
for case in range(4):
 if case in [0,2]:a=[sum(1<<i for i in rng.sample(range(64),2)) for _ in range(n)]
 else:a=[rng.getrandbits(64) for _ in range(n)]
 ops=[]
 for i in range(m-1):
  if case==0:ops.append(f'1 1 {n} {1<<(i%64)}')
  elif case==1:ops.append(f'1 1 {n} {rng.getrandbits(64)}')
  elif case==2:
   if i%2:ops.append(f'1 1 {n} {1<<(i%64)}')
   else:
    p=rng.randrange(1,n+1);x=sum(1<<j for j in rng.sample(range(64),2));ops.append(f'3 {p} {p} {x}')
  else:
   l=rng.randrange(1,n+1);r=rng.randrange(l,n+1);typ=rng.choices([1,2,3],[7,2,1])[0]
   ops.append(f'{typ} {l} {r}'+(f' {rng.getrandbits(64)}' if typ!=2 else ''))
 ops.append(f'2 1 {n}')
 data=f'{n} {m} 3\n'+' '.join(map(str,a))+'\n'+'\n'.join(ops)+'\n'
 start=time.perf_counter();p=subprocess.run([solver],input=data.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE);elapsed=time.perf_counter()-start
 assert p.returncode==0,p.stderr.decode();print(json.dumps({'case':case,'seconds':round(elapsed,3),'answers':len(p.stdout.split())}),flush=True)
