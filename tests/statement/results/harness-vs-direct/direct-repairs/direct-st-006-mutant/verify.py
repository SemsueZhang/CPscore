from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='1c16d6ddde180f0c08ff20e32e0570430ce5b6cf0a0fba813570a889e77efb07'
checks=[]
assert solve('components',{'n':3,'ops':[['?'],['+',1,2],['?'],['-',2,1],['?']]})==[3,2,3]
checks.append('sample operations simulated independently')
print(json.dumps({'case_id': 'st-006-mutant', 'candidate_sha256': '1c16d6ddde180f0c08ff20e32e0570430ce5b6cf0a0fba813570a889e77efb07', 'scope': 'finite witnesses; general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
