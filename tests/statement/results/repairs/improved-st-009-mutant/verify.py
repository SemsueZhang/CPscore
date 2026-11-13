from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='72565cbc4176611d6248a5007bff8ee1404e4fec136145a7079fe29f8c1dade7'
checks=[]
original=(ROOT/'cases/st-009-mutant.md').read_text(encoding='utf-8')
assert candidate.decode().replace('无解输出一行 `NO`。','无解输出一行 NO。')==original
checks.append('exact one local markup change; semantic token NO retained')
print(json.dumps({'case_id': 'st-009-mutant', 'candidate_sha256': '72565cbc4176611d6248a5007bff8ee1404e4fec136145a7079fe29f8c1dade7', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
