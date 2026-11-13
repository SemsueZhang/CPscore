from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='45d1c2c26753491ad19bb06075a3951d1a97a2984c1f389d66ae0ed9f5bc6d01'
checks=[]
from math import factorial
for n in range(3,9):
 width=(factorial(n)-1).bit_length()
 assert 2**width>=factorial(n) and 2**(width-1)<factorial(n)
 seen=set()
 for rank,p in enumerate(permutations(range(1,n+1))):
  pos={v:i for i,v in enumerate(p)}
  signature=tuple(pos[u]<pos[v] for u in range(1,n+1) for v in range(u+1,n+1))
  assert signature not in seen;seen.add(signature)
  message=format(rank,f'0{width}b');assert len(message)==width and int(message,2)==rank
checks.append('n=3..8 capacity, permutation distinguishability and rank encoding')
print(json.dumps({'case_id': 'st-034-base', 'candidate_sha256': '45d1c2c26753491ad19bb06075a3951d1a97a2984c1f389d66ae0ed9f5bc6d01', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
