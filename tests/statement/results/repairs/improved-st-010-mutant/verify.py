from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='2f2ce7779a4de87b48ae77870d264f50291c5d06ccbccdf7a17db86ba939863e'
checks=[]
text=candidate.decode();block=text.split('## 样例输出')[1].split('```text')[1].split('```')[0].strip().splitlines()
assert block[0]=='YES'
assert solve('matrix',{'rows':[1,1],'cols':[1,1],'matrix':block[1:]})
checks.append('actual candidate sample satisfies row and column margins')
print(json.dumps({'case_id': 'st-010-mutant', 'candidate_sha256': '2f2ce7779a4de87b48ae77870d264f50291c5d06ccbccdf7a17db86ba939863e', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
