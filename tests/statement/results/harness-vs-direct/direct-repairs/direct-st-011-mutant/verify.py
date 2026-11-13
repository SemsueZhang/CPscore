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
assert hashlib.sha256(candidate).hexdigest()=='8afea51d9880dee95961c9ec7a7d9f71eee6bd2f377b6e577e99eb6b3c6f8fd4','Candidate changed after proof preparation'
checks=[]

eps=Fraction(1,10**6)
def old_nonzero(z,y):return abs(y-z)/abs(z)<=eps
def repaired(z,y):return abs(y-z)<=eps*max(Fraction(1),abs(z))
z=Fraction(1,10);y=z+Fraction(1,2*10**6)
assert not old_nonzero(z,y) and repaired(z,y)
assert repaired(Fraction(0),Fraction(0))
assert repaired(Fraction(0),Fraction(1,2*10**6))
assert solve('centroid',{'points':[[0,0,9],[1,1,1]]})==[0.1,0.1]
checks.append('zero denominator removed; legal nonzero witness proves acceptance relation broadened')

print(json.dumps({'case_id':'st-011-mutant','candidate_sha256':'8afea51d9880dee95961c9ec7a7d9f71eee6bd2f377b6e577e99eb6b3c6f8fd4','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
