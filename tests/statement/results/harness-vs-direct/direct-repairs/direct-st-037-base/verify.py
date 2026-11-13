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
assert hashlib.sha256(candidate).hexdigest()=='c6e1ea7e2f746f5ae558354065e3d0d1ed198a684aca34fb3bace3bb3f50fd7d','Candidate changed after proof preparation'
checks=[]

for n in range(2,6):
    for a in product(range(-1,2),repeat=n):
        s=sorted(a);expected=min(s[-2]-s[0],s[-1]-s[1])
        assert solve('delete_range',{'a':list(a)})==expected
checks.append('all small arrays: deletion enumeration vs extreme-deletion characterization')

print(json.dumps({'case_id':'st-037-base','candidate_sha256':'c6e1ea7e2f746f5ae558354065e3d0d1ed198a684aca34fb3bace3bb3f50fd7d','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
