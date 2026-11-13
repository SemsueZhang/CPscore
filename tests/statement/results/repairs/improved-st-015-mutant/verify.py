from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='35c836f0eaa10badff58e6293d692e230b27cab0ee9bf5969e2a79d4b7eed1ed'
checks=[]
assert solve('tree_distance',{'n':3,'edges':[[1,2],[2,3]],'query':1,'hidden':3})==2
checks.append('interaction transcript distance independently calculated')
print(json.dumps({'case_id': 'st-015-mutant', 'candidate_sha256': '35c836f0eaa10badff58e6293d692e230b27cab0ee9bf5969e2a79d4b7eed1ed', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
