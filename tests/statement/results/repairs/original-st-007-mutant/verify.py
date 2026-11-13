from pathlib import Path
from itertools import product,combinations,permutations
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'manifest.json').is_file() and (p/'scripts/oracles.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
from oracles import solve
candidate=(HERE/'material.md').read_bytes()
assert hashlib.sha256(candidate).hexdigest()=='25dbd1effc98df33b1fa3ffb0df5f9b17c10956dec5773653a36b03923eddf68'
checks=[]
assert solve('embedding',{'s':'aa','t':'a'})==2
assert solve('embedding',{'s':'abc','t':'ac'})==1
for n in range(1,6):
 for s in product('ab',repeat=n):
  for k in range(1,4):
   for t in product('ab',repeat=k):
    dp=[1]+[0]*k
    for ch in s:
     for j in range(k,0,-1):
      if ch==t[j-1]:dp[j]+=dp[j-1]
    assert solve('embedding',{'s':''.join(s),'t':''.join(t)})==dp[-1]
checks.append('index-subsequence count: enumeration vs independent DP')
print(json.dumps({'case_id': 'st-007-mutant', 'candidate_sha256': '25dbd1effc98df33b1fa3ffb0df5f9b17c10956dec5773653a36b03923eddf68', 'scope': 'finite witnesses; maintainer-model general argument in proof.md', 'status': 'passed'} | {'checks':checks},ensure_ascii=False))
