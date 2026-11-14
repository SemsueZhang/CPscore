"""Score only after both complete prediction files are frozen; no model calls."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import sys

REPO=Path(__file__).resolve().parents[2]
ROOT=Path(__file__).resolve().parent
BENCH=Path('/Users/zhangchenrui/Workspace/work/ai/LuoguBench')
sys.path.insert(0,str(REPO/'skills/cp-difficulty-luogu/scripts'))
from common import digest,file_sha,read_json,read_jsonl,write_json
from difficulty import load_prepared
from benchmark import score_run,compare

runs={mode:read_json(ROOT/'runs'/mode/'run.json') for mode in ('baseline','skill')}
if any(r['status']!='complete' or r['valid_predictions']!=87 for r in runs.values()):
    raise ValueError('Wait for all 174 predictions before loading ground truth')
thread_ids=[]
usage={}
call_audit={}
for mode in runs:
    manifest,items,requests=load_prepared(ROOT/'paired'/mode)
    predictions=read_jsonl(ROOT/'runs'/mode/'predictions.jsonl')
    if len(predictions)!=87 or file_sha(ROOT/'runs'/mode/'predictions.jsonl')!=runs[mode]['predictions_sha256']:
        raise ValueError('Unfrozen predictions')
    records=sorted((ROOT/'runs'/mode/'responses').glob('*.json'))
    if len(records)!=87:
        raise ValueError('Unexpected response inventory')
    refs={r['id']:r for r in manifest['items']}
    subtotal={}
    for path in records:
        record=read_json(path)
        if record['status']!='valid' or record['request_sha256']!=refs[record['id']]['request_sha256']:
            raise ValueError('Failed call or prompt mismatch')
        response=json.loads(record['stdout'])
        if response['prediction'] not in predictions or response['thread_id']!=record['thread_id']:
            raise ValueError('Response identity mismatch')
        thread_ids.append(record['thread_id'])
        for k,v in (record.get('usage') or {}).items():
            if type(v) in (int,float): subtotal[k]=subtotal.get(k,0)+v
    call_audit[mode]={'rating_requests':len(records),'valid_predictions':len(predictions),'usage':subtotal}
    for k,v in subtotal.items(): usage[k]=usage.get(k,0)+v
if len(thread_ids)!=len(set(thread_ids)):
    raise ValueError('Model conversations were reused across questions/arms')
# Ground truth is first opened here, after both complete frozen runs pass audit.
metrics={mode:score_run(ROOT/'paired'/mode,ROOT/'runs'/mode,BENCH/'data/labels.jsonl',ROOT/'scores'/mode,BENCH) for mode in runs}
comparison=compare(ROOT/'scores/baseline/metrics.json',ROOT/'scores/skill/metrics.json')
write_json(ROOT/'comparison.json',comparison)
truth={r['id']:r for r in read_jsonl(BENCH/'data/labels.jsonl')}
preds={mode:{r['id']:r for r in read_jsonl(ROOT/'runs'/mode/'predictions.jsonl')} for mode in runs}
paired={'both_correct':0,'baseline_only_correct':0,'skill_only_correct':0,'neither_correct':0,
        'skill_smaller_error':0,'baseline_smaller_error':0,'equal_absolute_error':0,'different_predictions':0}
for item_id,t in truth.items():
    a,b=preds['baseline'][item_id]['level'],preds['skill'][item_id]['level']
    ac,bc=a==t['level'],b==t['level']
    key='both_correct' if ac and bc else 'baseline_only_correct' if ac else 'skill_only_correct' if bc else 'neither_correct'
    paired[key]+=1
    ea,eb=abs(a-t['level']),abs(b-t['level'])
    paired['skill_smaller_error' if eb<ea else 'baseline_smaller_error' if ea<eb else 'equal_absolute_error']+=1
    paired['different_predictions']+=a!=b
experiment=read_json(ROOT/'experiment.json')
experiment.update(status='complete',labels_loaded_for_this_run=True,scored_at_utc=datetime.now(timezone.utc).isoformat(),
                  label_file_sha256=file_sha(BENCH/'data/labels.jsonl'),call_audit=call_audit,
                  unique_rating_conversations=len(set(thread_ids)),usage_reported_by_cli=usage,paired_results=paired)
write_json(ROOT/'experiment.json',experiment)
OUT=REPO/'data/difficulty/evaluations/20261114-v2-undistilled-sol-high'
if OUT.exists(): raise ValueError('Report destination already exists')
OUT.mkdir(parents=True)
for mode in runs:
    target=OUT/mode
    target.mkdir()
    for filename in ('metrics.json','per_problem.csv','confusion.csv','run.json'):
        shutil.copyfile(ROOT/'scores'/mode/filename,target/filename)
    shutil.copyfile(ROOT/'runs'/mode/'predictions.jsonl',target/'predictions.jsonl')
for name in ('comparison.json','experiment.json','score-and-report.py'):
    shutil.copyfile(ROOT/name,OUT/name)
a,b=metrics['baseline'],metrics['skill']
lines=['# 未蒸馏 Difficulty Skill：LuoguBench 87 题对照','',
       '日期：2026-11-14。模型：GPT-6.1 Sol，reasoning effort = high。',
       'Skill：cpscore-difficulty-luogu-v2.0.0，正式专家经验 0 条，评分文本未修改。',
       '协议：cpscore-luogu-paired-isolated-v2。数据身份：development_diagnostic。','',
       '两组各 87/87 有效作答，共 174 次正式模型请求和 174 个不同会话。每题完整材料直接传入，禁止工具与其他题历史，没有模型复核、投票、语义重试或等级修正。',
       '两组同模型、同推理参数、同材料、同 adapter。87 对提示逐字核对后，唯一差异为冻结 Skill 块。每组并发 2 个独立请求，共最多 4 个。两组预测完整冻结后才读取标签计分。','',
       '| 指标 | 纯 LLM | 未蒸馏 Skill | Skill − 基线 |',
       '| --- | ---: | ---: | ---: |']
for key,label in [('accuracy','Accuracy'),('mae','MAE'),('within_one_level','Within-one-level'),('spearman_rho','Spearman'),('mean_signed_error','平均有符号误差')]:
    def fmt(x): return '未定义' if x is None else f'{x*100:.2f}%' if key in ('accuracy','within_one_level') else f'{x:.4f}'
    delta=None if a[key] is None or b[key] is None else b[key]-a[key]
    display_delta = f'{delta*100:+.2f} 个百分点' if delta is not None and key in ('accuracy','within_one_level') else fmt(delta)
    lines.append(f'| {label} | {fmt(a[key])} | {fmt(b[key])} | {display_delta} |')
lines+=['',f"完全命中：纯 LLM {round(a['accuracy']*87)}/87，Skill {round(b['accuracy']*87)}/87。有符号误差为预测减真实档位，负数表示低估。",'',
        '## 配对结果','',
        f"两组都命中 {paired['both_correct']} 题，仅基线命中 {paired['baseline_only_correct']} 题，仅 Skill 命中 {paired['skill_only_correct']} 题，两组都未命中 {paired['neither_correct']} 题。",
        f"Skill 绝对误差更小 {paired['skill_smaller_error']} 题，基线更小 {paired['baseline_smaller_error']} 题，误差相同 {paired['equal_absolute_error']} 题。两组预测等级不同 {paired['different_predictions']} 题。",'',
        '## 分档结果','',
        '| 真实档位 | 题数 | 基线命中 | Skill 命中 | 基线有符号误差 | Skill 有符号误差 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
for level in map(str,range(1,9)):
    aa,bb=a['by_level'].get(level),b['by_level'].get(level)
    if aa:
        lines.append(f"| {level} | {aa['n']} | {round(aa['n']*aa['accuracy'])}/{aa['n']} | {round(bb['n']*bb['accuracy'])}/{bb['n']} | {aa['mean_signed_error']:.3f} | {bb['mean_signed_error']:.3f} |")
lines+=['','## 范围与开销','',
        '这是已用于开发和历史诊断的公开 87 题的一次配对实验，不是未见题独立测试，不证明泛化或稳定收益。没有根据本轮标签修改 Skill，也没有将错题自动蒸馏为经验。',
        '历史 GPT 6 luna 的结果使用不同模型或共享上下文，不能据本次差异单独归因于框架重构。当前专用协议也不是禁止额外 Skill 的 LuoguBench 官方协议。',
        '评分理由保留供人工检查，没有自动评分理由正确性。题面、题解和代码的冻结身份校验不能证明全部语义理解正确。',
        '启动前有一次沙箱阻止 app-server 初始化，未产生模型预测。提升执行权限后完成一次合成题传输检查，该次模型请求排除在 174 次正式评级和成绩之外。',
        'CLI 报告的正式用量：`'+json.dumps(usage,ensure_ascii=False)+'`。用量不是实际账单，不推算订阅费用。','',
        '## 证据','',
        '- [纯 LLM 指标](baseline/metrics.json)与[预测](baseline/predictions.jsonl)',
        '- [Skill 指标](skill/metrics.json)与[预测](skill/predictions.jsonl)',
        '- [配对比较](comparison.json)与[实验审计](experiment.json)',
        f'- 完整冻结材料、请求、Skill/脚本快照与逐题传输记录：`{ROOT}`。',
        '- 本报告与指标只在两组全部完成后生成。计分脚本预先设置了全题完成检查，没有向评分模型反馈真实标签。','']
(OUT/'Report.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'report':str(OUT/'Report.md'),'comparison':comparison,'calls':call_audit,'paired':paired},ensure_ascii=False,indent=2))
