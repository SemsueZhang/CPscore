from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='2f8885bb75b40df042066d30ec975faf6c3c0997cad3fec91e39e18e865fc065'
checks=[]
assert solve('circular',{'a':[5,-8,4,3]})==12
for n in range(1,5):
 for a in product(range(-1,2),repeat=n):
  vals=[sum((a+a)[s:s+k]) for s in range(n) for k in range(1,n+1)]
  assert vals and solve('circular',{'a':a})==max(vals)
checks.append('finite nonempty circular domains, including n=1 and negative values')
print(json.dumps({'case_id': 'st-004-mutant', 'candidate_sha256': '2f8885bb75b40df042066d30ec975faf6c3c0997cad3fec91e39e18e865fc065', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
