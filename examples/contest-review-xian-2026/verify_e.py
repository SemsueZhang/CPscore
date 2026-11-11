import argparse,random,subprocess,json,time
MASK=(1<<64)-1

def check(solver,a,ops):
 data=f'{len(a)} {len(ops)} 3\n'+' '.join(map(str,a))+'\n'+'\n'.join(' '.join(map(str,z)) for z in ops)+'\n'
 values=a[:];want=[]
 for z in ops:
  typ,l,r,*rest=z
  if typ==2:want.append(sum(values[l-1:r])&MASK)
  else:
   x=rest[0]
   for i in range(l-1,r):
    if typ==3 or (values[i]^x).bit_count()>3:values[i]=x
 p=subprocess.run([solver],input=data.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 assert p.returncode==0,(p.returncode,p.stderr.decode(),data[:10000])
 got=list(map(int,p.stdout.split()));assert got==want,(len(a),ops[:20],got,want)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--solver',required=True);parser.add_argument('--cases',type=int,default=200);parser.add_argument('--large',action='store_true');args=parser.parse_args()
 rng=random.Random(20261116);cnt=0;operations=0
 for case in range(args.cases):
  n=rng.randrange(1,180);width=rng.choice([4,5,6,8,16,32,64]);a=[rng.getrandbits(width) for _ in range(n)];ops=[]
  for _ in range(500):
   typ=rng.choices([1,2,3],[7,2,1])[0]
   if rng.random()<.35:l,r=1,n
   else:l=rng.randrange(1,n+1);r=rng.randrange(l,n+1)
   z=(typ,l,r) if typ==2 else (typ,l,r,rng.getrandbits(width));ops.append(z)
  ops.extend((2,i,i) for i in range(1,n+1));check(args.solver,a,ops);cnt+=1;operations+=len(ops)
 if args.large:
  for case in range(12):
   n=6000;width=rng.choice([4,8,64]);a=[rng.getrandbits(width) for _ in range(n)];ops=[]
   for _ in range(500):
    typ=rng.choices([1,2,3],[7,2,1])[0];l=rng.randrange(1,n+1);r=rng.randrange(l,n+1)
    if rng.random()<.5:l,r=1,n
    ops.append((typ,l,r) if typ==2 else (typ,l,r,rng.getrandbits(width)))
   check(args.solver,a,ops);cnt+=1;operations+=len(ops)
  for width in [8,32,64]:
   n=6000;a=[sum(1<<i for i in rng.sample(range(width),rng.randrange(3))) for _ in range(n)];ops=[]
   for i in range(1000):ops.extend([(1,1,n,1<<(i%width)),(2,1,n)])
   check(args.solver,a,ops);cnt+=1;operations+=len(ops)
 print(json.dumps({'operation_sequences':cnt,'operations':operations,'oracle':'direct element updates and sums modulo 2^64'}),flush=True)
