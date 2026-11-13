"""Finite, independent mathematical checks; not an automatic natural-language proof."""
from pathlib import Path
from itertools import product
from fractions import Fraction
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='dd117366b24c99be94b07d74dca1f26da02df70590e17b9cdace99369025055c','Candidate changed after proof preparation'
checks=[]

for p in range(1,5):
    for arrival in range(11):
        earliest=min(k*p for k in range(20) if k*p>=arrival)
        assert earliest==((arrival+p-1)//p)*p
assert solve('ferry',{'n':3,'edges':[[1,2,1,1],[2,3,1,1]]})==2
assert solve('ferry',{'n':3,'edges':[[1,2,3,1],[2,3,2,4]]})==6
checks.append('tie and non-tie departure arithmetic; actual sample')

print(json.dumps({'case_id':'st-005-mutant','candidate_sha256':'dd117366b24c99be94b07d74dca1f26da02df70590e17b9cdace99369025055c','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
