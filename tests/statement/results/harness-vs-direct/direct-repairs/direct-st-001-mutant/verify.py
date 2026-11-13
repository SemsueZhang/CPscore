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
assert hashlib.sha256(candidate).hexdigest()=='4a5e5166a5239ffcc650e4340f8e41c882fa8d448beb8e5993ac60f42567ef55','Candidate changed after proof preparation'
checks=[]

def prefix_answer(capacity, orders):
    for k in range(1,len(orders)+1):
        if any(sum(d for l,r,d in orders[:k] if l<=i+1<=r)>c for i,c in enumerate(capacity)):return k
    return 0
for n in range(1,4):
    choices=[(l,r,d) for l in range(1,n+1) for r in range(l,n+1) for d in (1,2)]
    for cap in product(range(3),repeat=n):
        for orders in product(choices,repeat=2):assert solve('booking',{'capacity':list(cap),'orders':list(orders)})==prefix_answer(cap,orders)
checks.append('prefix-demand vs sequential booking on small complete domains')

print(json.dumps({'case_id':'st-001-mutant','candidate_sha256':'4a5e5166a5239ffcc650e4340f8e41c882fa8d448beb8e5993ac60f42567ef55','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
