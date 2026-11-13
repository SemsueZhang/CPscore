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
assert hashlib.sha256(candidate).hexdigest()=='cf2d6304fd247e3bd37d2499385ef4abfb2434f3a0010f25c8ac160912bdfeba','Candidate changed after proof preparation'
checks=[]

from itertools import permutations
for n in range(1,7):
    attainable={sum(p[i]>p[j] for i in range(n) for j in range(i+1,n)) for p in permutations(range(1,n+1))}
    assert attainable==set(range(n*(n-1)//2+1))
assert solve('permutation',{'n':3,'k':1,'permutation':[1,3,2]})
checks.append('all permutations up to n=6; no-solution and sample acceptance')

print(json.dumps({'case_id':'st-008-mutant','candidate_sha256':'cf2d6304fd247e3bd37d2499385ef4abfb2434f3a0010f25c8ac160912bdfeba','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
