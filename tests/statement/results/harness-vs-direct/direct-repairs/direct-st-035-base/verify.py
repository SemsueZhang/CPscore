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
assert hashlib.sha256(candidate).hexdigest()=='3ee97f24806abbfc34d1cd9da12dff44e0750757a6e0ebf1c96d9276548baacf','Candidate changed after proof preparation'
checks=[]

def settle(s,days):
    failed=0
    for inc,expense in days:
        available=s+inc
        if available<expense:failed+=1;s=available
        else:s=available-expense
        assert s>=0
    return failed,s
for s in range(3):
    for days in product(list(product(range(3),repeat=2)),repeat=3):
        f,b=settle(s,days);assert 0<=f<=3 and b>=0
assert settle(3,[(2,1)])==(0,4)
assert settle(0,[(1,1)])==(0,0)
checks.append('finite settlement domain, nonnegative invariant, sample and old witness')

print(json.dumps({'case_id':'st-035-base','candidate_sha256':'3ee97f24806abbfc34d1cd9da12dff44e0750757a6e0ebf1c96d9276548baacf','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
