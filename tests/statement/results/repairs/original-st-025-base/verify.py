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
assert hashlib.sha256(candidate).hexdigest()=='23c77bd6f037a8647316af8dc331c6da2e5ee82fd94446399ea12918b8e0e219','Candidate changed after proof preparation'
checks=[]

edges=[[1,2,1],[2,3,1],[3,1,1]]
assert solve('shortest',{'n':3,'edges':edges,'directed':True,'source':1,'target':3})==2
assert solve('shortest',{'n':3,'edges':edges,'directed':True,'source':1,'target':2})==1
checks.append('chosen directed interpretation and unchanged official sample')

print(json.dumps({'case_id':'st-025-base','candidate_sha256':'23c77bd6f037a8647316af8dc331c6da2e5ee82fd94446399ea12918b8e0e219','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
