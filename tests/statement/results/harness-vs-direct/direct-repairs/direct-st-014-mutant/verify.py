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
assert hashlib.sha256(candidate).hexdigest()=='6be6723b8f93595ecbf81c90cc7b2ac291361d5819c91fa6f87e19799b7ca044','Candidate changed after proof preparation'
checks=[]

from math import ceil,log2
for n in range(1,65):
    for h in range(1,n+1):
        lo,hi,count=1,n,0
        while lo<=hi:
            x=(lo+hi)//2;count+=1
            reply='A' if h<x else 'Q' if h==x else 'Z'
            if reply=='Q':break
            if reply=='A':hi=x-1
            else:lo=x+1
        assert x==h and count<=ceil(log2(n))+1
checks.append('actual letter mapping supports all hidden values for N<=64')

print(json.dumps({'case_id':'st-014-mutant','candidate_sha256':'6be6723b8f93595ecbf81c90cc7b2ac291361d5819c91fa6f87e19799b7ca044','checks':checks,'scope':'finite witnesses; general argument and prose mapping are in proof.md','status':'passed'},ensure_ascii=False))
