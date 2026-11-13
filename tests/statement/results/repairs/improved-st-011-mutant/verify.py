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
assert hashlib.sha256(candidate).hexdigest()=='79028bf4a581575df412eea62079fc8c64408dc5b681cb4e525539bd059e4599','Candidate changed after proof preparation'
checks=[]

eps=Fraction(1,10**6)
def repaired(z,y):return y==0 if z==0 else abs(y-z)/abs(z)<=eps
for z in [Fraction(-2),Fraction(-1,10),Fraction(1,10),Fraction(2)]:
    for scale in [-2,-1,0,1,2]:
        y=z+scale*eps*abs(z)
        assert repaired(z,y)==(abs(y-z)/abs(z)<=eps)
assert repaired(Fraction(0),Fraction(0))
assert not repaired(Fraction(0),Fraction(1,2*10**6))
assert solve('centroid',{'points':[[0,0,1]]})==[0,0]
checks.append('zero branch defined; every tested nonzero acceptance preserved exactly')

print(json.dumps({'case_id':'st-011-mutant','candidate_sha256':'79028bf4a581575df412eea62079fc8c64408dc5b681cb4e525539bd059e4599','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
