from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='6d81810d6a06ce4acc7ac7b20b0427eb99f95b2d4cbc97a482e4388bc862de59'
checks=[]
for n in range(1,6):
 for bits in product('01',repeat=n):
  for mask in range(1,1<<n):
   indices=[j+1 for j in range(n) if mask>>j&1]
   assert solve('parity',{'bits':bits,'indices':indices})==sum(int(bits[j-1]) for j in indices)%2
  assert [solve('parity',{'bits':bits,'indices':[j]}) for j in range(1,n+1)]==list(map(int,bits))
checks.append('all nonempty subsets and singleton reconstruction through n=5')
print(json.dumps({'case_id': 'st-016-mutant', 'candidate_sha256': '6d81810d6a06ce4acc7ac7b20b0427eb99f95b2d4cbc97a482e4388bc862de59', 'scope': 'finite witnesses; general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
