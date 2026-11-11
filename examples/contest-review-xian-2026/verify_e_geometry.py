import random,json

class Summary:
 def __init__(self,S,A,width=64):
  self.S=set(S);self.A=A;self.width=width;self.mask=(1<<width)-1
  self.ones=0;self.edges=[];self.adj=[0]*width;self.deg=[0]*width;self.far=[]
  for value in S:
   E=value^A;k=E.bit_count()
   if k==1:self.ones|=E
   elif k==2:
    u=(E&-E).bit_length()-1;v=(E^(1<<u)).bit_length()-1
    self.edges.append((u,v));self.adj[u]|=1<<v;self.adj[v]|=1<<u;self.deg[u]+=1;self.deg[v]+=1
   elif k>2:self.far.append(value)
  self.B=self.far[0] if self.far else None
  if self.B is None:return
  self.D=A^self.B;self.delta=self.D.bit_count()
  if self.delta>6:return
  self.reserve=self.D&-self.D;self.groups={};D=self.D;I=D
  while True:
   k=I.bit_count();t=min(3-k,3-self.delta+k)
   if t>=0:
    z=(self.mask^D)|self.reserve if t else self.reserve
    for value in self.far:
     E=value^A;h=(E^I).bit_count()
     one=(self.mask^D) if h<=2 else (E&(self.mask^D)) if h<=4 else 0
     empty=self.reserve if h<=3 else 0
     z&=(one|empty) if t else empty
    self.groups[I]=(t,z)
   if I==0:break
   I=(I-1)&D
 def all_near(self,x):
  C=x^self.A;k=C.bit_count()
  if k>3:return False
  if k==3 and self.ones&~C:return False
  if k>=2:
   vs=[i for i in range(self.width) if C>>i&1]
   covered=sum(self.deg[u] for u in vs)-sum((self.adj[u]>>v)&1 for i,u in enumerate(vs) for v in vs[i+1:])
   if covered!=len(self.edges):return False
  if self.B is None:return True
  if (x^self.B).bit_count()>3:return False
  assert self.delta<=6
  I=C&self.D;J=C&~self.D
  t,z=self.groups[I]
  assert J.bit_count()<=t
  return bool(z&(J if J else self.reserve))

def main():
 rng=random.Random(20261115);sets=queries=0
 for width in range(4,11):
  for _ in range(150):
   S=set(rng.randrange(1<<width) for _ in range(rng.randrange(1,100)))
   A=rng.choice(list(S));z=Summary(S,A,width)
   for x in range(1<<width):
    got=z.all_near(x);want=all((x^v).bit_count()<=3 for v in S)
    assert got==want,(width,S,A,x,z.__dict__)
    queries+=1
   sets+=1
 # Force every anchor-distance case, including nonempty intersections.
 for width in [8,16,32,64]:
  for delta in range(3,7):
   for _ in range(100):
    A=rng.getrandbits(width);D=sum(1<<i for i in rng.sample(range(width),delta));B=A^D
    x=A^sum(1<<i for i in rng.sample([i for i in range(width) if D>>i&1],delta//2))
    assert (x^A).bit_count()<=3 and (x^B).bit_count()<=3
    S={A,B}
    for __ in range(50):S.add(x^sum(1<<i for i in rng.sample(range(width),rng.randrange(4))))
    z=Summary(S,A,width)
    for y in [x]+[rng.getrandbits(width) for _ in range(100)]:
     assert z.all_near(y)==all((y^v).bit_count()<=3 for v in S)
     queries+=1
    sets+=1
 print(json.dumps({'distinct_value_sets':sets,'exact_membership_queries':queries}),flush=True)
if __name__=='__main__':main()
