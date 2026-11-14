"""Offline analysis of the frozen original A/B run; not a new benchmark or tuner."""
from pathlib import Path
import json
import math
import random
import statistics
import sys

REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO/'skills/cp-difficulty-luogu/scripts'))
from common import read_json,read_jsonl,write_json
ROOT=REPO/'outputs/difficulty-luogu-v2-20261114-gpt61sol-high'
OUT=Path(__file__).resolve().parent
A={r['id']:r for r in read_jsonl(ROOT/'runs/baseline/predictions.jsonl')}
B={r['id']:r for r in read_jsonl(ROOT/'runs/skill/predictions.jsonl')}
T={r['id']:r for r in read_jsonl('/Users/zhangchenrui/Workspace/work/ai/LuoguBench/data/labels.jsonl')}
ids=list(A)
delta=[int(B[i]['level']==T[i]['level'])-int(A[i]['level']==T[i]['level']) for i in ids]
gains=sum(d>0 for d in delta);losses=sum(d<0 for d in delta);discordant=gains+losses
p=min(1,2*sum(math.comb(discordant,k) for k in range(min(gains,losses)+1))/2**discordant)
rng=random.Random(20261114)
samples=sorted(sum(rng.choice(delta) for _ in delta)/len(delta) for _ in range(30000))
stats={'n':len(ids),'same_level':sum(A[i]['level']==B[i]['level'] for i in ids),
       'different_level':sum(A[i]['level']!=B[i]['level'] for i in ids),
       'skill_lower':sum(B[i]['level']<A[i]['level'] for i in ids),
       'skill_higher':sum(B[i]['level']>A[i]['level'] for i in ids),
       'max_between_arm_level_difference':max(abs(A[i]['level']-B[i]['level']) for i in ids),
       'skill_only_correct':gains,'baseline_only_correct':losses,
       'accuracy_delta':sum(delta)/len(delta),'paired_exact_mcnemar_two_sided_p':p,
       'item_bootstrap_accuracy_delta_percentile95':[samples[750],samples[29249]],
       'bootstrap_seed':20261114,'bootstrap_repetitions':30000,
       'statistics_limit':'Descriptive analysis of curated public development items. Item independence/family independence and population sampling are not established. p does not prove equality; bootstrap is not a generation-repeat interval.'}
for mode in ('baseline','skill'):
    records=[read_json(p) for p in (ROOT/'runs'/mode/'responses').glob('*.json')]
    stats[mode+'_usage']={'input_mean':statistics.mean(r['usage']['input_tokens'] for r in records),
                        'input_max':max(r['usage']['input_tokens'] for r in records),
                        'reasoning_tokens':sum(r['usage'].get('reasoning_output_tokens',0) for r in records),
                        'output_tokens':sum(r['usage']['output_tokens'] for r in records),
                        'invalid_predictions':sum(r['status']!='valid' for r in records)}
write_json(OUT/'original-statistics.json',stats)
print(json.dumps(stats,ensure_ascii=False,indent=2))
