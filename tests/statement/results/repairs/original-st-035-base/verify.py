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
assert hashlib.sha256(candidate).hexdigest()=='d40123f14026c57f6b80d75cecb92071077641657d77f8ab86934ea40f140866','Candidate changed after proof preparation'
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

print(json.dumps({'case_id':'st-035-base','candidate_sha256':'d40123f14026c57f6b80d75cecb92071077641657d77f8ab86934ea40f140866','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
