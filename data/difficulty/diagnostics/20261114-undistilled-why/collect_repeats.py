"""Collect the preregistered repeats, retaining the first valid rating per planned cell.

This is a selected development diagnostic, never an independent benchmark.
"""
from pathlib import Path
from collections import Counter
import json
import sys

REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO/'skills/cp-difficulty-luogu/scripts'))
from common import digest,read_json,read_jsonl,validate_prediction,write_json,write_jsonl
from difficulty import load_prepared
ROOT=REPO/'outputs/difficulty-why-20261114'
ORIGINAL=REPO/'outputs/difficulty-luogu-v2-20261114-gpt61sol-high'
OUT=Path(__file__).resolve().parent
plan=read_json(ROOT/'plan.json')
recovery=read_json(ROOT/'recovery-plan.json')
ids=plan['selection']['disagreements']+plan['selection']['stable_controls']
collected={}
threads=[]
provenance=[]
for entry in recovery['entries']:
    name=entry['run']
    path=REPO/entry['out']
    if not (path/'run.json').exists() or read_json(path/'run.json')['status']!='complete':
        print(json.dumps({'ready':False,'waiting_for':name}));sys.exit(1)
    old=ROOT/'runs'/name
    first={r['id']:r for r in read_jsonl(old/'predictions.jsonl')}
    new={r['id']:r for r in read_jsonl(path/'predictions.jsonl')}
    if len(first)!=entry['valid_originals'] or len(new)!=entry['pending'] or set(first)&set(new):
        raise ValueError('A successful original cell was replaced or recovery is incomplete')
    union={**first,**new}
    if set(union)!=set(ids):raise ValueError('Missing planned diagnostic cells')
    manifest,_,requests=load_prepared(ROOT/'prepared'/name)
    request_map={r['id']:r for r in requests}
    _,_,retry_requests=load_prepared(REPO/entry['prepared'])
    for r in retry_requests:
        if r!=request_map[r['id']]:raise ValueError('Recovery changed request text/model/settings')
    for item_id,row in union.items():
        validate_prediction(row,item_id)
        directory=old if item_id in first else path
        record_path=directory/'responses'/(item_id+'.json')
        record=read_json(record_path)
        if record['status']!='valid' or record['request_sha256']!=digest(request_map[item_id]):
            raise ValueError('Request/response audit failed')
        response=json.loads(record['stdout'])
        if response['prediction']!=row:raise ValueError('Prediction was modified')
        threads.append(response['thread_id'])
        provenance.append({'run':name,'id':item_id,'source':str(record_path),'recovered':item_id in new})
    collected[name]=union
if len(threads)!=76 or len(threads)!=len(set(threads)):
    raise ValueError('Expected 76 distinct valid repeat conversations')
# Labels are used for descriptive diagnosis only after all planned cells pass audit.
truth={r['id']:r for r in read_jsonl('/Users/zhangchenrui/Workspace/work/ai/LuoguBench/data/labels.jsonl')}
for mode in ('baseline','skill'):
    original={r['id']:r for r in read_jsonl(ORIGINAL/'runs'/mode/'predictions.jsonl')}
    collected[mode+'-r0']={i:original[i] for i in ids}
original_threads=[read_json(ORIGINAL/'runs'/mode/'responses'/(i+'.json'))['thread_id']
                  for mode in ('baseline','skill') for i in ids]
if set(original_threads)&set(threads) or len(original_threads)!=len(set(original_threads)):
    raise ValueError('A repeat reused an original conversation')
subsets={'all_selected':ids,'original_disagreements':plan['selection']['disagreements'],'stable_controls':plan['selection']['stable_controls']}
rounds={}
for rep in (0,1,2):
    desc={}
    for subset,subset_ids in subsets.items():
        arm={}
        for mode in ('baseline','skill'):
            rows=collected[mode+'-r'+str(rep)]
            errors=[rows[i]['level']-truth[i]['level'] for i in subset_ids]
            arm[mode]={'n':len(errors),'exact':sum(e==0 for e in errors),'mae':sum(abs(e) for e in errors)/len(errors),
                       'signed_error':sum(errors)/len(errors)}
        arm['skill_minus_baseline_exact']=arm['skill']['exact']-arm['baseline']['exact']
        desc[subset]=arm
    rounds[str(rep)]=desc
cases=[]
for i in ids:
    a=[collected['baseline-r'+str(rep)][i]['level'] for rep in (0,1,2)]
    b=[collected['skill-r'+str(rep)][i]['level'] for rep in (0,1,2)]
    cases.append({'id':i,'problem_id':truth[i]['problem_id'],'truth':truth[i]['level'],
                  'subset':'original_disagreement' if i in plan['selection']['disagreements'] else 'stable_control',
                  'baseline_levels':a,'skill_levels':b,'baseline_invariant':len(set(a))==1,'skill_invariant':len(set(b))==1,
                  'baseline_new_differs_from_original':sum(x!=a[0] for x in a[1:]),
                  'skill_new_differs_from_original':sum(x!=b[0] for x in b[1:]),
                  'strict_arm_separation':max(a)<min(b) or max(b)<min(a),
                  'overlapping_levels':sorted(set(a)&set(b))})
stability={}
for mode in ('baseline','skill'):
    stability[mode]={'items_identical_all_three':sum(c[mode+'_invariant'] for c in cases),
                     'items_changed_in_at_least_one_repeat':sum(not c[mode+'_invariant'] for c in cases),
                     'new_ratings_different_from_original':sum(c[mode+'_new_differs_from_original'] for c in cases),
                     'new_ratings_total':38}
new_pair_differences=[collected['skill-r'+str(rep)][i]['level']-collected['baseline-r'+str(rep)][i]['level'] for rep in (1,2) for i in ids]
summary={'purpose':'selected post_hoc development repeat diagnostic','ready':True,'new_valid_ratings':76,
         'unique_new_conversations':len(set(threads)),'original_ratings_in_context':False,'labels_in_model_prompts':False,
         'unique_original_plus_repeat_conversations':len(set(original_threads+threads)),
         'original_and_recovery_sources':provenance,'rounds':rounds,'same_prompt_stability':stability,
         'new_pair_level_shift':{'skill_lower':sum(x<0 for x in new_pair_differences),'same':sum(x==0 for x in new_pair_differences),
                                 'skill_higher':sum(x>0 for x in new_pair_differences),'mean_skill_minus_baseline_level':sum(new_pair_differences)/len(new_pair_differences)},
         'original_disagreement_items_strictly_separated_all_three':sum(c['strict_arm_separation'] for c in cases if c['subset']=='original_disagreement'),
         'selection_and_inference_limits':plan['limitations'],
         'transport_note':'First valid outputs are retained. Missing cells were recovered once after connection failures. Failed/cancelled attempts are preserved outside these valid-rating counts; their total model billing is unknown.'}
write_json(OUT/'repeat-results.json',summary)
write_json(OUT/'repeat-cases.json',cases)
write_json(OUT/'repeat-plan.json',plan)
write_json(OUT/'recovery-plan.json',recovery)
write_jsonl(OUT/'repeat-observations.jsonl',[{'run':name,**r} for name,rows in collected.items() for r in rows.values()])
print(json.dumps({'ready':True,'rounds':rounds,'stability':stability,'new_pair_level_shift':summary['new_pair_level_shift'],'strict_separation':summary['original_disagreement_items_strictly_separated_all_three']},ensure_ascii=False,indent=2))
