"""Describe every preregistered local ablation rating; never select a release winner."""
from pathlib import Path
import json
import sys
REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO/'skills/cp-difficulty-luogu/scripts'))
from common import digest,read_json,read_jsonl,write_json,write_jsonl,validate_prediction
from difficulty import load_prepared
ROOT=REPO/'outputs/difficulty-why-20261114'
OUT=Path(__file__).resolve().parent
plan=read_json(ROOT/'ablation-plan.json')
jobplan=read_json(ROOT/'ablation-jobs.json')
observations=[];thread_ids=[];by_case={}
for e in jobplan['entries']:
 run=REPO/e['out'];prepared=REPO/e['prepared']
 if not (run/'run.json').exists() or read_json(run/'run.json')['status']!='complete':
  print(json.dumps({'ready':False,'waiting_for':e['run']}));sys.exit(1)
 manifest,items,requests=load_prepared(prepared)
 request_map={r['id']:r for r in requests}
 rows=read_jsonl(run/'predictions.jsonl')
 if len(rows)!=2 or {r['id'] for r in rows}!={plan['target_id'],plan['control_id']}:raise ValueError('Invalid item inventory')
 condition=manifest['metadata']['condition'];rep=manifest['metadata']['repetition']
 for row in rows:
  validate_prediction(row,row['id'])
  record_path=run/'responses'/(row['id']+'.json');record=read_json(record_path)
  if record['status']!='valid' or record['request_sha256']!=digest(request_map[row['id']]):raise ValueError('Frozen request failed audit')
  response=json.loads(record['stdout'])
  if response['prediction']!=row:raise ValueError('Prediction changed')
  thread_ids.append(response['thread_id'])
  observations.append({'condition':condition,'repetition':rep,**row,'source':str(record_path)})
  by_case.setdefault(row['id'],{}).setdefault(condition,{})[str(rep)]=row['level']
if len(thread_ids)!=16 or len(set(thread_ids))!=16:raise ValueError('Model conversations reused')
repeat_sources=read_json(OUT/'repeat-results.json')['original_and_recovery_sources']
old_threads={read_json(p['source'])['thread_id'] for p in repeat_sources}
if old_threads&set(thread_ids):raise ValueError('Ablation reused repeat conversation')
summary={'purpose':plan['purpose'],'ready':True,'new_valid_ratings':16,'unique_conversations':16,
         'target_id':plan['target_id'],'control_id':plan['control_id'],'levels_by_case_condition_repetition':by_case,
         'limits':plan['limits'],'official_skill_modified':False,'release_selection_performed':False}
write_json(OUT/'ablation-results.json',summary)
write_jsonl(OUT/'ablation-observations.jsonl',observations)
write_json(OUT/'ablation-plan.json',plan)
write_json(OUT/'ablation-variant-snapshots.json',read_json(ROOT/'ablation-variant-snapshots.json'))
print(json.dumps(summary,ensure_ascii=False,indent=2))
