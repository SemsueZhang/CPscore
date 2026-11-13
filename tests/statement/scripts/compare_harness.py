#!/usr/bin/env python3
"""CPScore versus direct review of the same material; saved real outputs only."""
import argparse
import collections
import datetime as dt
import json
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import sys

sys.dont_write_bytecode=True
import evaluate as e


def collect(directory,label):
    directory=Path(directory);plan=e.read(directory/'plan.json');rows=[];judged=[];states=collections.Counter()
    for entry in plan['runs']:
        if entry['skill']!=label:continue
        folder=directory/entry['run_id']
        if not (folder/'run.json').exists():states['not_run']+=1;continue
        meta=e.read(folder/'run.json');states[meta['execution_status']]+=1
        if meta['execution_status']!='completed':continue
        assert e.sha((folder/'report.md').read_bytes())==meta['raw_sha256']
        if label=='direct':
            assert meta['review_mode']=='direct' and meta['skill_version']['commit'] is None
            assert meta['payload']['files']=={'material.md':meta['statement_sha256'],'request.txt':e.sha(e.DIRECT_PROMPT.encode())}
            assert any(arg.startswith('skills.config=') for arg in meta['command'])
        native=e.event_evidence(folder);assert len(native['observed_session_ids'])==1
        result=e.judged_run(folder)
        rows.append({'meta':meta,'native':native,'directory':str(folder),'adjudicated':bool(result)})
        if result:judged.append(result)
    return plan,rows,judged,dict(states)


def timing(rows):
    input_tokens=[];cached=[];output_tokens=[];seconds=[]
    for row in rows:
        usage=row['native']['token_usage'];meta=row['meta']
        if 'input_tokens' in usage:input_tokens.append(usage['input_tokens'])
        if 'cached_input_tokens' in usage:cached.append(usage['cached_input_tokens'])
        if 'output_tokens' in usage:output_tokens.append(usage['output_tokens'])
        seconds.append((dt.datetime.fromisoformat(meta['finished_at'])-dt.datetime.fromisoformat(meta['started_at'])).total_seconds())
    def values(xs):return {'count':len(xs),'total':sum(xs),'median':statistics.median(xs) if xs else None}
    return {'input_tokens':values(input_tokens),'cached_input_tokens':values(cached),'output_tokens':values(output_tokens),'elapsed_seconds':values(seconds)}


def known_recall(rows,format_only=False):
    hit=total=0
    for r in rows:
        if r['gold']['gold_status']!='confirmed':continue
        roots={d['root_id'] for d in r['gold']['defects'] if d['status']=='confirmed' and (d['category']=='format')==format_only}
        total+=len(roots);hit+=len(roots&set(r['tp']))
    return e.ratio(hit,total)


def neutral_file_inventory(item):
    """An `rg --files -g !SKILL.md` exclusion lists names; it does not read a Skill."""
    try:
        outer=shlex.split(item['command']);body=outer[-1] if '-lc' in outer else item['command']
        if any(s in body for s in ('$(','`','<(','>(')):return False
        lexer=shlex.shlex(body,posix=True,punctuation_chars=';&|');lexer.whitespace_split=True
        tokens=list(lexer)
    except (ValueError,KeyError):return False
    if 'rg' not in tokens or '--files' not in tokens:return False
    allowed={'pwd','rg','--files','--hidden','-g','.','&&',';'}
    if any(t not in allowed and not t.strip('\"\'').startswith('!') for t in tokens):return False
    lines=item.get('aggregated_output','').splitlines()
    return bool(lines) and all(line in ('material.md','request.txt','./material.md','./request.txt') or re.fullmatch(r'/(?:private/)?tmp/cp-statement-[^/]+',line) for line in lines)


def repair_summary(directory,label):
    directory=Path(directory);rs=[r for r in e.repair_metrics(directory) if r['skill']==label]
    unavailable=[e.read(p) for p in directory.rglob('repair-unavailable.json') if e.read(p).get('skill',label)==label]
    assert len({(r['case_id'],r['root_id']) for r in rs})==len(rs)
    assert not ({r['case_id'] for r in rs}&{r['case_id'] for r in unavailable})
    effective=sum(r['resolved']=='complete' and not r['changed_clear_semantics'] and not r['new_spec_errors'] for r in rs)
    semantic={t['case_id'] for t in e.manifest()['repair_targets'] if next(d for d in e.gold(t['case_id'])['defects'] if d['root_id']==t['root_id'])['category']!='format'}
    semantic_effective=sum(r['case_id'] in semantic and r['resolved']=='complete' and not r['changed_clear_semantics'] and not r['new_spec_errors'] for r in rs)
    return {'target_roots':20,'reviewed_candidates':len(rs),'unavailable_advice':unavailable,
            'pending':20-len(rs)-len(unavailable),'resolved':dict(collections.Counter(r['resolved'] for r in rs)),
            'complete':e.ratio(sum(r['resolved']=='complete' for r in rs),20),
            'effective':e.ratio(effective,20),'semantic_sample_language_effective':e.ratio(semantic_effective,len(semantic)),'changed_clear_semantics':sum(r['changed_clear_semantics'] for r in rs),
            'scope_changes':[r['case_id'] for r in rs if r['domain_changed']],
            'new_spec_errors':sum(len(r['new_spec_errors']) for r in rs)}


def report(harness,direct,harness_repairs,direct_repairs,destination):
    hp,hr,hj,hs=collect(harness,'improved');dp,dr,dj,ds=collect(direct,'direct')
    assert hp['model']==dp['model'] and hp['effort']==dp['effort']
    assert hp['skills']['improved']['commit']==e.manifest()['skills']['improved']['git_ref']
    assert dp['prompt_sha256']==e.sha(e.DIRECT_PROMPT.encode())
    sessions=[r['native']['session_id'] for r in hr+dr];assert len(sessions)==len(set(sessions))
    official={c['case_id'] for c in e.manifest()['cases']}
    def first(rs):return {r['meta']['case_id']:r for r in rs if r['meta']['repeat']==1 and r['meta']['case_id'] in official}
    ha,da=first(hj),first(dj);paired=sorted(set(ha)&set(da))
    result={'created_at':e.now(),'question':'CPScore Skill versus direct review, same Codex-hosted model',
            'harness_skill':hp['skills']['improved'],'model':dp['model'],'effort':dp['effort'],
            'execution':{'harness':hs,'direct':ds},'paired_adjudicated_official_cases':paired,
            'unpaired_harness_cases':sorted(set(ha)-set(da)),'unpaired_direct_cases':sorted(set(da)-set(ha)),
            'detection':{},'consistency':{},'equivalence':{},'repairs':{},'resources':{},'differences':[],
            'unadjudicated':{name:[r['meta']['run_id'] for r in rows if not r['adjudicated']] for name,rows in [('harness',hr),('direct',dr)]},'triage':[]}
    result['host_versions']={name:sorted({r['meta'].get('host_version','unrecorded') for r in rows}) for name,rows in [('harness',hr),('direct',dr)]}
    lines=['# CPScore harness 与直接审题对照','',f'模型 `{dp["model"]}`，effort=`{dp["effort"]}`；CPScore 固定 `{hp["skills"]["improved"]["commit"]}`。',
           '直接组仅获得题面、通用评分协议和相同输出格式，无 CPScore Skill 或方法 Reference。双方保留相同 Codex 宿主及工具；这不是去掉所有底层宿主的裸 API 对照。',
           f'执行状态：harness={hs}，direct={ds}；可配对且已裁定正式题面 {len(paired)}/56。两个未确认阅读 Gold 不进入已确认指标。','',
           '| 指标 | CPScore harness | 直接审题 |','| --- | --- | --- |']
    display={}
    for name,rs,allrows,alljudged,rdir,label in [('harness',[ha[c] for c in paired],hr,hj,harness_repairs,'improved'),('direct',[da[c] for c in paired],dr,dj,direct_repairs,'direct')]:
        metrics=e.detection_metrics(rs);c=collections.Counter(metrics['counts'])
        result['detection'][name]={'all_known':metrics,'semantic_sample_language_recall':known_recall(rs),'format_recall':known_recall(rs,True),
                                  'by_split':{split:e.detection_metrics([r for r in rs if r['gold']['split']==split]) for split in ['development','holdout']},
                                  'by_type':{kind:e.detection_metrics([r for r in rs if r['gold']['problem_type']==kind]) for kind in sorted(e.TYPES)}}
        result['consistency'][name]=e.consistency_metrics(alljudged,{})
        result['equivalence'][name]=e.equivalent_metrics(alljudged)
        result['repairs'][name]=repair_summary(rdir,label)
        result['resources'][name]=timing(allrows)
        groups=result['consistency'][name]
        repeated=[r for r in alljudged if r['meta']['case_id'] in e.manifest()['consistency_cases']]
        display[name]={'语义、样例与文字根因 Recall':known_recall(rs),'格式根因 Recall':known_recall(rs,True),
                       '全部确认发现 Precision':e.ratio(c['tp'],c['tp']+c['fp']),'Fatal Recall':e.ratio(c['fatal_hit'],c['fatal_total']),
                       '正确题误报率':e.ratio(c['clean_fp'],c['clean_total']),'冻结 Gold 等级准确率':e.ratio(c['severity_correct'],c['severity_total']),
                       'Gold 外确认问题等级准确率':e.ratio(c['novel_severity_correct'],c['novel_severity_total']),
                       '证据有效率':e.ratio(c['evidence_valid'],c['evidence_total']),
                       '核心集合众数一致性':e.ratio(sum(g['core_modal']['numerator'] for g in groups),5*len(groups)),
                       '重复审核中出现无依据扣分':e.ratio(sum(bool(r['fp']) for r in repeated),len(repeated)),
                       '修复有效率（20目标为分母）':result['repairs'][name]['effective'],
                       '语义、样例与文字目标修复有效率':result['repairs'][name]['semantic_sample_language_effective']}
    for metric in display['harness']:
        a,b=display['harness'][metric],display['direct'][metric]
        def cell(name,value):
            text=e.fmt(value['numerator'],value['denominator'])
            if '修复有效率' in metric and result['repairs'][name]['pending']:
                return '待完成；已确认 '+text
            return text
        lines.append(f'| {metric} | {cell("harness",a)} | {cell("direct",b)} |')
    lines+=['','## 逐题差异','']
    for cid in paired:
        a,b=ha[cid],da[cid]
        row={'case_id':cid,'harness_only_known':sorted(set(a['tp'])-set(b['tp'])),'direct_only_known':sorted(set(b['tp'])-set(a['tp'])),
             'harness_fp':sorted(a['fp']),'direct_fp':sorted(b['fp']),
             'harness_new':{k:v['severity'] for k,v in a['novel'].items()},'direct_new':{k:v['severity'] for k,v in b['novel'].items()},
             'severity_differences':{k:[a['tp'][k]['severity'],b['tp'][k]['severity']] for k in set(a['tp'])&set(b['tp']) if a['tp'][k]['severity']!=b['tp'][k]['severity']}}
        result['differences'].append(row)
        if row['harness_only_known'] or row['direct_only_known'] or row['harness_fp']!=row['direct_fp'] or row['harness_new']!=row['direct_new'] or row['severity_differences']:
            lines.append(f'- `{cid}`：'+json.dumps({k:v for k,v in row.items() if k!='case_id'},ensure_ascii=False))
    lines+=['','## 未决与 Gold 外发现','']
    for name,rows in [('harness',hr),('direct',dr)]:
        for row in rows:
            path=Path(row['directory'])/'adjudication.json'
            if not path.exists():continue
            a=e.read(path)
            if not a['complete'] or any(f['disposition']=='new_confirmed' for f in a['findings']):
                result['triage'].append({'condition':name,'run_id':row['meta']['run_id'],'adjudication':a})
                lines.append(f'- {name}/{row["meta"]["case_id"]}：'+ '；'.join(f'{f["finding_id"]} {f["disposition"]}：{f["reason"]}' for f in a['findings']))
    lines+=['','## 修订、稳定性与资源','']
    for name in ['harness','direct']:
        r=result['repairs'][name];t=result['resources'][name]
        lines.append(f'- {name}：修订复审 {r["reviewed_candidates"]}/20；无可用建议 {len(r["unavailable_advice"])}/20；待复核 {r["pending"]}/20；根因消除 {e.fmt(r["complete"]["numerator"],20)}，有效 {e.fmt(r["effective"]["numerator"],20)}；新增规格错误 {r["new_spec_errors"]}，额外明确语义变化 {r["changed_clear_semantics"]}，范围/协议变化 {r["scope_changes"]}。')
        lines.append(f'- {name}：重复审核完整组 {len(result["consistency"][name])}/12，等价版本对 {len(result["equivalence"][name])}/4。108 次主审核报告的输入 tokens 合计 {t["input_tokens"]["total"]}，其中缓存 {t["cached_input_tokens"]["total"]}；输出 tokens 合计 {t["output_tokens"]["total"]}；调用耗时中位数 {t["elapsed_seconds"]["median"]} 秒。各项原始计数及中位数见 JSON，不是账单价格。')
    lines+=['','## 解释边界','',
            '格式规范收益与语义检出收益分开解释。无建议、失败和待复核修订不计成功；只消除选定根因不等于全文无缺陷。',
            '直接组共享基本等级定义、扣分及输出格式，没有获得完整 CPScore 的细化影响判据与判例。等级一致性反映对 CPScore 专用标准的遵循，不能作为新增数学检错能力的证据。',
            'harness 为较早的真实运行复用，直接组在之后执行；模型别名、后端状态及时间负载没有独立固定。因此耗时只作描述，tokens 不换算为账单价格。',
            'Gold、语义裁定及证明由维护者模型完成，未经人类专家确认；生成者与被测模型未建立独立性。确认子集可能有天花板效应，不能把相同分数解释为所有场景均无收益。','']
    destination=Path(destination);e.save_text(destination,'\n'.join(lines));e.write(destination.with_suffix('.json'),result)
    return result


def audit(direct,direct_repairs,harness,harness_repairs):
    direct=Path(direct);repairs=Path(direct_repairs);root=direct.parent
    freeze=e.read(root/'direct-freeze.json');protocol=e.read(root/'protocol.json')
    assert e.sha((root/'protocol.json').read_bytes())==freeze['protocol_sha256']
    assert e.sha(e.DIRECT_PROMPT.encode())==freeze['prompt_sha256']
    assert (root/'direct-request.txt').read_text(encoding='utf-8')==e.DIRECT_PROMPT
    assert e.sha((e.ROOT/'results/protocol-freeze.json').read_bytes())==freeze['dataset_freeze_sha256']
    dataset=e.read(e.ROOT/'results/protocol-freeze.json')
    for cid,c in e.records().items():
        assert e.sha((e.ROOT/c['statement_path']).read_bytes())==dataset['case_sha256'][cid]
        assert e.sha((e.ROOT/'gold'/f'{cid}.json').read_bytes())==dataset['gold_sha256'][cid]
    _,hrows,_,_=collect(harness,'improved');sessions={r['native']['session_id'] for r in hrows}
    hr=[r for r in e.repair_metrics(harness_repairs) if r['skill']=='improved']
    assert len(hr)==20
    for r in hr:
        bundle=Path(harness_repairs)/('improved-'+r['case_id'])
        review=(bundle/r['review_run_directory']).resolve();sid=e.event_evidence(review)['session_id']
        assert sid and sid not in sessions;sessions.add(sid)
    count=0;flagged=[];inventory=[];execution={}
    for directory,expected in [(direct,108),(root/'direct-repair-reviews',19)]:
        plan=e.read(directory/'plan.json');assert len(plan['runs'])==expected and plan['review_mode']=='direct'
        names=plan['disabled_skill_names'];assert names==protocol['control']['disabled_skill_names']
        config='skills.config=['+','.join('{name='+json.dumps(n)+',enabled=false}' for n in names)+']'
        for entry in plan['runs']:
            folder=directory/entry['run_id'];meta=e.read(folder/'run.json')
            assert meta['execution_status']=='completed' and meta['source']=='real_host'
            assert meta['model']==protocol['model'] and meta['effort']==protocol['effort']
            assert meta['source_file_sha256_at_run_start']==freeze['runner_sha256']
            assert meta['review_mode']=='direct' and meta['skill_version']['commit'] is None
            assert config in meta['command'] and '--ignore-user-config' in meta['command']
            assert meta['payload']['files']=={'material.md':meta['statement_sha256'],'request.txt':freeze['prompt_sha256']}
            raw=(folder/'report.md').read_bytes();assert e.sha(raw)==meta['raw_sha256']
            assert e.parse_report(raw.decode('utf-8'))==e.read(folder/'prediction.json')
            native=e.event_evidence(folder);assert len(native['observed_session_ids'])==1
            sid=native['session_id'];assert sid and sid not in sessions;sessions.add(sid);count+=1
            for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines():
                event=json.loads(line);item=event.get('item',{});cmd=item.get('command','')
                if event.get('type')=='item.completed' and item.get('type')=='command_execution' and re.search(r'SKILL\.md|\.agents/skills|\.codex/skills|/gold|manifest\.json',cmd):
                    record={'run_id':entry['run_id'],'command':cmd,'observed_output':item.get('aggregated_output','')}
                    if neutral_file_inventory(item):inventory.append(record)
                    else:flagged.append(record)
        execution[directory.name]=expected
    assert not flagged,'Unexpected Skill/Gold command needs investigation'
    closed=e.repair_metrics(repairs);unavailable=[e.read(p) for p in repairs.rglob('repair-unavailable.json')]
    targets={(t['case_id'],t['root_id']) for t in e.manifest()['repair_targets']}
    assert len(closed)==19 and len(unavailable)==1
    assert {(r['case_id'],r['root_id']) for r in closed+unavailable}==targets
    for bundle in sorted(repairs.glob('direct-*')):
        if not (bundle/'repair.json').exists():continue
        repair=e.read(bundle/'repair.json');parent=direct/repair['parent_run_id']
        assert e.read(parent/'run.json')['raw_sha256']==repair['parent_raw_sha256']
        pred=e.read(parent/'prediction.json');finding=next(f for f in pred['findings'] if f['id']==repair['finding_id'])
        edits=[finding['repairs'][i] for i in repair['repair_indices']];assert edits==repair['edits']
        text=(e.ROOT/e.records()[repair['case_id']]['statement_path']).read_text(encoding='utf-8')
        for edit in edits:
            assert text.count(edit['find'])==1;text=text.replace(edit['find'],edit['replace'],1)
        assert text==(bundle/'material.md').read_text(encoding='utf-8')
        value=subprocess.run([sys.executable,str(bundle/'verify.py')],capture_output=True,text=True,encoding='utf-8',check=True)
        expected={**json.loads(value.stdout),'verification_script_sha256':e.sha((bundle/'verify.py').read_bytes())}
        assert expected==e.read(bundle/'verification.json') and expected['status']=='passed'
        pre=e.read(bundle/'pre-review-analysis.json');a=e.read(bundle/'repair-assessment.json')
        review=(bundle/a['review_run_directory']).resolve();meta=e.read(review/'run.json')
        assert dt.datetime.fromisoformat(pre['registered_at'])<dt.datetime.fromisoformat(meta['started_at'])
        for key in ('domain_changed','changed_clear_semantics','locality','necessary'):assert pre[key]==a[key]
    for row in unavailable:
        parent=direct/row['parent_run_id'];assert e.read(parent/'run.json')['raw_sha256']==row['parent_raw_sha256']
        assert e.sha((parent/'prediction.json').read_bytes())==row['parent_prediction_sha256']
    assert count==127 and len(sessions)==255
    return {'checked_at':e.now(),'status':'passed','direct_real_sessions':count,'reused_harness_real_sessions':128,
            'unique_comparison_sessions':len(sessions),'direct_execution':execution,'neutral_two_file_payloads':count,
            'reexecuted_direct_repair_programs':19,'unavailable_target_roots':len(unavailable),'skill_gold_access_command_flags':flagged,
            'neutral_inventory_commands_excluding_skill_files':inventory,
            'limits':['Command scan and payload checks are not an OS-level access barrier.',
                      'direct-st-019-base-r1 interface-binding question remains pending, not counted as FP.',
                      'Native identities and hashes establish archive integrity, not human-expert Gold correctness or immutable backend weights.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);root=e.ROOT/'results';experiment=root/'harness-vs-direct'
    p.add_argument('--harness',default=root/'final');p.add_argument('--direct',default=experiment/'direct-final')
    p.add_argument('--harness-repairs',default=root/'repairs');p.add_argument('--direct-repairs',default=experiment/'direct-repairs')
    p.add_argument('--output',default=experiment/'report.md');p.add_argument('--audit',action='store_true');args=p.parse_args()
    value=report(args.harness,args.direct,args.harness_repairs,args.direct_repairs,args.output)
    if args.audit:
        result=audit(args.direct,args.direct_repairs,args.harness,args.harness_repairs);e.write(Path(args.output).parent/'archive-audit.json',result)
    print(json.dumps({'paired_official_cases':len(value['paired_adjudicated_official_cases']),'execution':value['execution']},ensure_ascii=False))
