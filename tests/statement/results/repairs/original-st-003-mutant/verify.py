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
assert hashlib.sha256(candidate).hexdigest()=='547ce96e372a2c937345964f10e18b3b901c3688fd81b740fd1f8ebe0c14fc06','Candidate changed after proof preparation'
checks=[]

base=(ROOT/'cases/st-003-base.md').read_bytes()
assert candidate==base
assert solve('tree_xor',{'n':3,'edges':[[1,2,1],[2,3,1]]})==1
assert solve('tree_xor',{'n':3,'edges':[[1,2,3],[2,3,5]]})==6
assert solve('tree_xor',{'n':1,'edges':[]})==0
checks.append('exact clean-reference restoration and independent tree witnesses')

print(json.dumps({'case_id':'st-003-mutant','candidate_sha256':'547ce96e372a2c937345964f10e18b3b901c3688fd81b740fd1f8ebe0c14fc06','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
