from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='ffa02a27de3877e96605f2649d738ff188a8db0b083abcaa17f0b211ea2b92ac'
checks=[]
assert not list(combinations(range(1),2))
for n in range(2,5):
 for a in product(range(-1,2),repeat=n):
  values=[abs(a[i]-a[j]) for i,j in combinations(range(n),2)]
  assert values and min(values)==min(abs(x-y) for x,y in zip(sorted(a),sorted(a)[1:]))
checks.append('excluded singleton; nonempty minimum and adjacent-sorted invariant')
print(json.dumps({'case_id': 'st-026-base', 'candidate_sha256': 'ffa02a27de3877e96605f2649d738ff188a8db0b083abcaa17f0b211ea2b92ac', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
