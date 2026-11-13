#!/usr/bin/env python3
"""CPScore statement benchmark: deterministic checks + isolated host runs + adjudicated metrics.

Only `run` can invoke a model. No metric uses keyword matching as a semantic judge.
"""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True
from oracles import solve, sample_check, check_defect_witness
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
LEVELS = {'Fatal':10, 'Major':2, 'Minor':1}
TYPES = {'standard','interactive','communication','construction','floating','simulation'}


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save_text(path, text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='\n') as stream:stream.write(text)

def write(path, value):
    save_text(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(data): return hashlib.sha256(data).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def manifest(): return read(ROOT/'manifest.json')
def records(m=None):
    m=m or manifest(); return {c['case_id']:c for c in m['cases']+m['equivalences']}
def gold(cid):
    if cid not in records(): raise ValueError('Unknown case ID')
    return read(ROOT/'gold'/f'{cid}.json')
def score(defects): return 10-sum(LEVELS[d['severity']] for d in defects)
def safe_child(parent, relative):
    parent=Path(parent).resolve(); target=(parent/relative).resolve()
    if not target.is_relative_to(parent): raise ValueError('Path leaves package: '+relative)
    return target


def validate(smoke=False):
    m=manifest(); allcases=records(m); selected=m['smoke'] if smoke else list(allcases)
    assert len(m['cases'])==56 and len({c['family_id'] for c in m['cases']})==40
    base=[c for c in m['cases'] if c['version']=='base']
    assert len(base)==40 and sum(c['original_kind']=='clean' for c in base)==24
    assert sum(c['original_kind']=='defective' for c in base)==16
    assert sum(c['version']=='mutant' for c in m['cases'])==16
    assert len(m['consistency_cases'])==12 and m['repetitions']==5
    assert len(m['repair_targets'])==20
    assert len({(t['case_id'],t['root_id']) for t in m['repair_targets']})==20
    assert TYPES-{'standard'} <= {allcases[t['case_id']]['problem_type'] for t in m['repair_targets']}
    for target in m['repair_targets']:
        assert any(d['root_id']==target['root_id'] and d['status']=='confirmed' for d in gold(target['case_id'])['defects']),'Repair target is not confirmed'
    families=collections.defaultdict(list)
    for c in m['cases']: families[c['family_id']].append(c)
    for cs in families.values(): assert len({c['split'] for c in cs})==1, 'Family split leakage'
    for kind in TYPES-{'standard'}:
        cs=[c for c in base if c['problem_type']==kind]
        assert len(cs)>=4 and {c['original_kind'] for c in cs}=={'clean','defective'},kind
    assert all(allcases[cid]['split']=='development' for cid in m['smoke']),'Smoke families must stay in development'
    pending=[]
    checks=[]
    for cid in selected:
        c=allcases[cid];g=gold(cid);path=safe_child(ROOT,c['statement_path']);text=path.read_text(encoding='utf-8')
        assert sha(path.read_bytes())==c['statement_sha256']==g['statement_sha256'],cid
        assert all(g[k]==c[k] for k in c if k!='equivalent_to'),cid
        sample=re.search(r'## 样例输入\s+```text\n(.*?)\n```\s+## 样例输出\s+```text\n(.*?)\n```',text,re.S)
        actual_samples=[] if sample is None else [{'input':sample.group(1)+'\n','output':sample.group(2)+'\n'}]
        assert g['samples']==actual_samples,(cid,'Gold samples differ from statement')
        assert g['legal_input_domain'] and g['relation'] and g['completeness_review']
        assert isinstance(g['legal_input_domain'],dict)
        assert g['legal_input_domain']['input_contract']==text.split('## 输入格式\n\n')[1].split('\n## 输出格式')[0].strip()
        assert g['legal_input_domain']['bounds']==text.split('## 数据范围\n\n')[1].split('\n## ')[0].strip()
        assert g['has_known_defects']==bool(g['defects']) and g['human_verified'] is False
        assert g['gold_status'] in ('confirmed','needs_review')
        assert len({d['root_id'] for d in g['defects']})==len(g['defects'])
        for d in g['defects']:
            assert d['severity'] in LEVELS and d['quote'] in text,(cid,d['root_id'],'quote')
            assert d['evidence'] and d['category'] and d['verification']
            assert d['status'] in ('confirmed','needs_review')
            for repair in d['acceptable_repairs']:
                assert repair['find'] in text,(cid,'repair quote',repair['find'])
                assert repair['replace'] and isinstance(repair['conditional'],bool)
            if d['status']=='needs_review': pending.append((cid,d['root_id']))
        assert g['expected_score']==(score(g['defects']) if g['gold_status']=='confirmed' else None)
        witness=check_defect_witness(g)
        assert witness['passed'] is not False,(cid,'defect witness check',witness)
        o=g['oracle']; actual=solve(o['name'],o['args'])
        assert actual==o['expected'],(cid,'oracle',actual,o['expected'])
        if not g['defects']:
            assert sample_check(g),(cid,'clean sample')
        checks.append({'case_id':cid,'gold_status':g['gold_status'],'oracle':o['name'],'oracle_passed':True,'defect_witness':witness,'clean_sample_parsed':sample_check(g) if not g['defects'] else None})
        for field in ('case_id','family_id','root_id','expected_score','needs_review'):
            assert field not in text,(cid,'Gold leaked into statement')
    for c in m['equivalences']:
        assert c['family_id']==allcases[c['equivalent_to']]['family_id']
        assert c['split']==allcases[c['equivalent_to']]['split']
        a=safe_child(ROOT,c['statement_path']).read_text(encoding='utf-8')
        b=safe_child(ROOT,allcases[c['equivalent_to']]['statement_path']).read_text(encoding='utf-8')
        assert re.sub(r'\n{2,}','\n\n',a)==re.sub(r'\n{2,}','\n\n',b)
    print(json.dumps({'ok':True,'checked_versions':len(selected),'formal_families':40,'formal_versions':56,'equivalent_versions':4,'needs_review':pending},ensure_ascii=False))
    return {'checked_versions':len(selected),'formal_families':40,'formal_versions':56,'equivalences':4,'pending':pending,'checks':checks,'checked_at':now()}


def event_evidence(folder):
    path=Path(folder)/'events.jsonl';sessions=[];usage={}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='thread.started' and event.get('thread_id'):sessions.append(event['thread_id'])
            if event.get('type')=='turn.completed':usage=event.get('usage',{})
    return {'session_id':sessions[0] if sessions else None,'observed_session_ids':sessions,'token_usage':usage}


def skill_fingerprint(file_hashes):
    return sha(b''.join(p.encode()+b'\0'+h.encode()+b'\n' for p,h in sorted(file_hashes.items())))


def skill_snapshot(label):
    if label=='direct':
        return {'label':'direct','commit':None,'sha256':skill_fingerprint({}),'files':{}}
    spec=manifest()['skills'][label];ref=spec['git_ref'];prefix=spec['path']+'/'
    commit=subprocess.check_output(['git','rev-parse',ref+'^{commit}'],cwd=REPO,text=True).strip()
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'--',spec['path']],cwd=REPO,text=True).splitlines()
    if not paths: raise ValueError('Skill snapshot unavailable: '+commit)
    files={p[len(prefix):]:subprocess.check_output(['git','show',commit+':'+p],cwd=REPO) for p in paths}
    fingerprint=skill_fingerprint({p:sha(b) for p,b in files.items()})
    return {'label':label,'commit':commit,'sha256':fingerprint,'files':files}


def make_plan(suite, split='development', model='gpt-6.1-sol', effort='xhigh'):
    m=manifest();byid=records(m)
    if suite=='smoke': ids=m['smoke']
    elif suite=='b': ids=m['consistency_cases']
    elif suite=='equivalence': ids=[c['equivalent_to'] for c in m['equivalences']]+[c['case_id'] for c in m['equivalences']]
    elif suite=='c': ids=list(dict.fromkeys(t['case_id'] for t in m['repair_targets']))
    else: ids=[c['case_id'] for c in m['cases']]
    ids=[cid for cid in ids if split=='all' or byid[cid]['split']==split]
    repetitions=m['repetitions'] if suite=='b' else 1
    versions={label:skill_snapshot(label) for label in m['skills']}
    runs=[]
    for label,cid,repeat in itertools.product(versions,ids,range(1,repetitions+1)):
        c=byid[cid]
        runs.append({'run_id':f'{label}-{cid}-r{repeat}','case_id':cid,'skill':label,'repeat':repeat,'phase':'initial','statement_sha256':c['statement_sha256']})
    if suite=='campaign':
        seen={(r['skill'],r['case_id'],r['repeat']) for r in runs}
        for label,cid,repeat in itertools.product(versions,m['consistency_cases'],range(2,6)):
            if split=='all' or byid[cid]['split']==split:
                runs.append({'run_id':f'{label}-{cid}-r{repeat}','case_id':cid,'skill':label,'repeat':repeat,'phase':'initial','statement_sha256':byid[cid]['statement_sha256']})
        for label,c in itertools.product(versions,m['equivalences']):
            if split=='all' or c['split']==split:
                runs.append({'run_id':f'{label}-{c["case_id"]}-r1','case_id':c['case_id'],'skill':label,'repeat':1,'phase':'initial','statement_sha256':c['statement_sha256']})
    return {'schema_version':1,'benchmark_revision':m.get('benchmark_revision'),'manifest_sha256':sha((ROOT/'manifest.json').read_bytes()),'gold_sha256':{cid:sha((ROOT/'gold'/f'{cid}.json').read_bytes()) for cid in sorted({r['case_id'] for r in runs})},'suite':suite,'split':split,'created_at':now(),'model':model,'effort':effort,'host':'codex-exec','prompt_sha256':sha(PROMPT.encode()),'host_settings':{'sandbox':'read-only','approval':'never','ephemeral':True,'ignore_user_config':True,'network':'no web search; model backend only','tools':'host read-only shell; no MCP or additional skills intentionally supplied'},'skills':{k:{j:v[j] for j in ('label','commit','sha256')} for k,v in versions.items()},'runs':runs}


# No case IDs, Gold labels, rubric expectations, or repair oracle appear here.
PROMPT = '''使用当前目录 .agents/skills/cp-statement-review/SKILL.md 中的 Skill 审核 material.md，按入口读取必要 Reference。仅阅读当前目录提供的材料，不访问其他项目、历史会话或互联网。题面为中文原创竞赛材料，按 Skill 的适用规范审核；未提供的 std 实测和译文来源不推定违规。不要修改题面，不创建其他报告文件。
正常输出 Markdown 审核报告。报告末尾另附一个 ```json 代码块，内容格式为：
{"score":10,"complete":true,"findings":[{"id":"f1","severity":"Fatal","quote":"题面原句","evidence":"核验依据","repairs":[{"find":"精确原文","replace":"建议新文","conditional":false}]}],"optional_suggestions":[]}
JSON 应忠实归纳实际报告，示例数字不是预期。只把已确认扣分项放入 findings，id 在本报告内唯一。修改方向需作者选择时 conditional 为 true。没有扣分项时 findings 为空。无法给出精确替换时 repairs 可为空，不编造补丁。'''


# The control gets the task, grading contract and output schema, without a review workflow.
# No case-specific labels, expected answers, witnesses or CPScore method references are included.
DIRECT_PROMPT = '''请直接审核 material.md 中的算法竞赛题面，报告已确认的问题、依据和修改建议。不要使用或读取任何 Skill、其他审核指南或历史会话。仅阅读当前目录提供的材料，不访问其他项目或互联网。题面为中文原创竞赛材料，采用洛谷题面规范；未提供的 std 实测和译文来源不推定违规。不要修改题面，不创建其他报告文件。
为统一评价尺度，使用以下评分协议：满分 10 分，允许负分；Fatal 扣 10 分，Major 扣 2 分，Minor 扣 1 分。影响合法输入、正确答案或接受规则且上下文不能消除的缺失、歧义、矛盾，以及正式样例输入、输出或解释的实质错误属于 Fatal；语义最终可确定但存在显著理解障碍，或违反适用的明确格式要求属于 Major；可轻易恢复的局部错字、符号或表达问题且未达到更高等级属于 Minor。只扣已确认的独立根因，同一根因按最高等级扣一次；疑点和可选润色不扣分，没有确认问题可以给 10 分。关键核验未完成时如实标记未完成。'''+PROMPT[PROMPT.index('\n正常输出 Markdown'):]


def review_prompt(plan):
    mode=plan.get('review_mode','cpscore')
    assert mode in ('cpscore','direct'),'Unknown review mode'
    if mode=='direct':assert set(plan['skills'])=={'direct'},'Direct plan must not load a Skill'
    return DIRECT_PROMPT if mode=='direct' else PROMPT


def make_direct_plan(suite,split='development',model='gpt-6.1-sol',effort='xhigh'):
    plan=make_plan(suite,split,model,effort);snap=skill_snapshot('direct')
    plan.update(review_mode='direct',prompt_sha256=sha(DIRECT_PROMPT.encode()),
                skills={'direct':{k:snap[k] for k in ('label','commit','sha256')}},
                disabled_skill_names=sorted(p.parent.name for p in (REPO/'skills').glob('*/SKILL.md')))
    plan['runs']=[{**r,'run_id':r['run_id'].replace('improved-','direct-',1),'skill':'direct','review_mode':'direct'} for r in plan['runs'] if r['skill']=='improved']
    plan['host_settings']={**plan['host_settings'],'cpscore_skill_loading':'disabled by exact names; none staged; prompt prohibits other Skills'}
    return plan


def stage_payload(entry, snap, directory, statement=None, prompt=None):
    prompt=PROMPT if prompt is None else prompt
    directory=Path(directory)
    text=statement if statement is not None else safe_child(ROOT,records()[entry['case_id']]['statement_path']).read_text(encoding='utf-8')
    save_text(directory/'material.md',text)
    for path,body in snap['files'].items():
        dest=safe_child(directory/'.agents/skills/cp-statement-review',path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
    save_text(directory/'request.txt',prompt)
    return {'files':{str(p.relative_to(directory)):sha(p.read_bytes()) for p in sorted(directory.rglob('*')) if p.is_file()},'prompt_sha256':sha(prompt.encode())}


def parse_report(raw):
    candidates=[raw]+re.findall(r'(?im)^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*$',raw)
    for block in reversed(candidates):
        try: data=json.loads(block)
        except (ValueError,TypeError): continue
        if not isinstance(data,dict) or not isinstance(data.get('findings'),list): continue
        validate_prediction(data)
        return data
    # Markdown extraction generates candidates for inspection; never silently marks a review complete.
    findings=[]
    for j,match in enumerate(re.finditer(r'(?mi)^.*?\b(Fatal|Major|Minor)\b[^\n]*',raw),1):
        findings.append({'id':f'candidate-{j}','severity':match.group(1),'quote':'','evidence':match.group(0),'repairs':[]})
    return {'score':None,'complete':False,'findings':findings,'optional_suggestions':[],'parse_status':'needs_review'}


def validate_prediction(data):
    assert isinstance(data.get('complete'),bool),'complete must be bool'
    assert data.get('score') is None or (isinstance(data['score'],(int,float)) and not isinstance(data['score'],bool) and math.isfinite(data['score']))
    ids=[]
    for f in data['findings']:
        assert f['severity'] in LEVELS and isinstance(f['id'],str)
        assert isinstance(f['quote'],str) and isinstance(f['evidence'],str)
        ids.append(f['id'])
        for p in f.get('repairs',[]): assert all(isinstance(p[k],str) for k in ('find','replace')) and isinstance(p['conditional'],bool)
    assert len(ids)==len(set(ids)),'duplicate finding IDs'


def run_plan(plan_path, output, timeout=240, limit=None, executable='codex', workers=1):
    assert 1<=workers<=4, 'Use 1 to 4 isolated host processes'
    plan=read(plan_path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    prompt=review_prompt(plan)
    assert plan.get('prompt_sha256',sha(prompt.encode()))==sha(prompt.encode()),'Prompt drift'
    assert plan.get('manifest_sha256',sha((ROOT/'manifest.json').read_bytes()))==sha((ROOT/'manifest.json').read_bytes()),'Benchmark manifest drift'
    if (output/'plan.json').exists():
        previous=read(output/'plan.json');assert previous==plan,'Do not mix different plans in one result directory'
    write(output/'plan.json',plan)
    snapshots={label:skill_snapshot(label) for label in plan['skills']}
    for label,snap in snapshots.items():
        assert snap['sha256']==plan['skills'][label]['sha256'] and snap['commit']==plan['skills'][label]['commit'],'Skill drift'
    selected=[entry for entry in plan['runs'] if not (output/entry['run_id']/'run.json').exists()]
    if limit is not None:selected=selected[:limit]
    def run_one(entry):
        folder=safe_child(output,entry['run_id']);folder.mkdir(parents=True)
        c=records()[entry['case_id']]
        statement=None
        if entry['phase']=='repair':
            bundle=Path(entry['repair_bundle'])
            if not bundle.is_absolute():bundle=safe_child(ROOT,entry['repair_bundle'])
            statement=(bundle/'material.md').read_text(encoding='utf-8')
            assert sha(statement.encode())==entry['statement_sha256'],'Repair drift'
        else: assert c['statement_sha256']==entry['statement_sha256'],'Case drift'
        meta={**entry,'model':plan['model'],'model_identity_source':'requested CLI model alias','effort':plan['effort'],'skill_version':plan['skills'][entry['skill']],'started_at':now(),'execution_status':'running','source':'real_host','gold_sha256':plan.get('gold_sha256',{}).get(entry['case_id']),'batch_workers':workers,'timeout_seconds':timeout,'source_file_sha256_at_run_start':sha(Path(__file__).read_bytes()),'host_settings':plan['host_settings']}
        write(folder/'run.json',meta)
        try:
            host_version=subprocess.check_output([executable,'--version'],text=True,stderr=subprocess.DEVNULL).strip()
            with tempfile.TemporaryDirectory(prefix='cp-statement-') as temp:
                meta['payload']=stage_payload(entry,snapshots[entry['skill']],temp,statement,prompt)
                assert meta['payload']['files']['material.md']==entry['statement_sha256'],'Actual payload drift'
                # Output destinations stay outside the review workspace. The model sees only the neutral payload.
                cmd=[executable,'--no-daemon','-a','never','exec','--ignore-user-config','--skip-git-repo-check','--ephemeral','--sandbox','read-only','--color','never','--json','--model',plan['model'],'-c',f'model_reasoning_effort="{plan["effort"]}"']
                if plan.get('review_mode')=='direct':
                    names=plan['disabled_skill_names'];assert 'cp-statement-review' in names
                    config='skills.config=['+','.join('{name='+json.dumps(name)+',enabled=false}' for name in names)+']'
                    cmd+=['-c',config]
                cmd+=['-C',temp,'-o',str((folder/'report.md').resolve()),'-']
                meta.update(host_version=host_version,command=[temp if arg==temp else arg for arg in cmd])
                write(folder/'run.json',meta)
                with (folder/'events.jsonl').open('w',encoding='utf-8') as events, (folder/'stderr.txt').open('w',encoding='utf-8') as errors:
                    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=events,stderr=errors,text=True)
                    meta['pid']=proc.pid;write(folder/'run.json',meta)
                    try:
                        proc.communicate(prompt,timeout=timeout);meta['returncode']=proc.returncode
                        meta['execution_status']='completed' if proc.returncode==0 and (folder/'report.md').is_file() else 'failed'
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try: proc.wait(timeout=5)
                        except subprocess.TimeoutExpired: proc.kill();proc.wait()
                        meta['execution_status']='timeout'
            if meta['execution_status']=='completed':
                raw=(folder/'report.md').read_text(encoding='utf-8');meta['raw_sha256']=sha((folder/'report.md').read_bytes())
                try: prediction=parse_report(raw)
                except (AssertionError,ValueError,KeyError,TypeError) as exc:
                    prediction={'score':None,'complete':False,'findings':[],'optional_suggestions':[],'parse_status':'needs_review','parse_error':str(exc)}
                write(folder/'prediction.json',prediction)
        except (OSError,ValueError,AssertionError,subprocess.SubprocessError) as exc:
            meta['execution_status']='failed';meta['error']=str(exc)
        meta.update(event_evidence(folder))
        meta['finished_at']=now();write(folder/'run.json',meta)
        print(entry['run_id'],meta['execution_status'],flush=True)
        if meta['execution_status']!='completed':
            print('Host failure; remaining unscheduled runs stay unexecuted.',flush=True)
        return meta['execution_status']=='completed'

    with ThreadPoolExecutor(max_workers=workers) as pool:
        iterator=iter(selected);pending=set()
        for _ in range(workers):
            entry=next(iterator,None)
            if entry is not None:pending.add(pool.submit(run_one,entry))
        while pending:
            done,pending=wait(pending,return_when=FIRST_COMPLETED)
            if not all(f.result() for f in done):
                for future in pending:future.cancel()
                return False
            for _ in done:
                entry=next(iterator,None)
                if entry is not None:pending.add(pool.submit(run_one,entry))
    return True


def import_result(plan_path,run_id,report_path,output,host,model,run_date):
    plan=read(plan_path);entry=next(x for x in plan['runs'] if x['run_id']==run_id)
    assert model==plan['model'],'Model differs from frozen plan; create a separate plan'
    dt.datetime.fromisoformat(run_date.replace('Z','+00:00'))
    folder=safe_child(output,run_id);assert not folder.exists(),'Never overwrite an existing run'
    folder.mkdir(parents=True);raw=Path(report_path).read_text(encoding='utf-8')
    save_text(folder/'report.md',raw)
    write(folder/'run.json',{**entry,'model':model,'effort':plan['effort'],'skill_version':plan['skills'][entry['skill']],'started_at':run_date,'finished_at':now(),'execution_status':'completed','source':'imported_real_host_attestation','gold_sha256':plan.get('gold_sha256',{}).get(entry['case_id']),'host':host,'raw_sha256':sha(raw.encode()),'source_raw_sha256':sha(Path(report_path).read_bytes()),'host_controls':'operator-attested; actual external tool permissions not enforced by importer','provenance_note':'Imported real output, asserted by operator; not independently authenticated. Text line endings normalized to LF; body not rewritten.'})
    write(folder/'prediction.json',parse_report(raw))
    Path(output).mkdir(parents=True,exist_ok=True);write(Path(output)/'plan.json',plan)


def adjudication_template(folder):
    folder=Path(folder);meta=read(folder/'run.json');pred=read(folder/'prediction.json')
    return {'run_id':meta['run_id'],'raw_sha256':meta['raw_sha256'],'prediction_sha256':sha((folder/'prediction.json').read_bytes()),'judge_kind':None,'judge_identity':None,'reviewed_at':None,'complete':False,'findings':[{'finding_id':f['id'],'disposition':'pending','root_id':None,'extra_root_id':None,'evidence_valid':None,'reason':'','novel_issue_review':None} for f in pred['findings']]}


def judged_run(folder):
    folder=Path(folder);meta=read(folder/'run.json')
    if meta['execution_status']!='completed' or not (folder/'prediction.json').exists(): return None
    pred=read(folder/'prediction.json');validate_prediction(pred)
    if not pred['complete'] or pred.get('parse_status')=='needs_review': return None
    if not (folder/'adjudication.json').exists(): return None
    ann=read(folder/'adjudication.json');g=gold(meta['case_id'])
    if meta.get('gold_sha256'):assert meta['gold_sha256']==sha((ROOT/'gold'/f'{meta["case_id"]}.json').read_bytes()),'Gold changed after frozen run'
    assert meta.get('statement_sha256',g['statement_sha256'])==g['statement_sha256'],'Run belongs to a different statement version'
    assert ann['run_id']==meta['run_id'] and ann['raw_sha256']==meta['raw_sha256']
    assert ann['prediction_sha256']==sha((folder/'prediction.json').read_bytes()),'Prediction changed after adjudication'
    assert sha((folder/'report.md').read_bytes())==meta['raw_sha256'],'Report modified after run'
    if not ann['complete']: return None
    assert ann['judge_kind'] in ('human','independent_model','maintainer_model','automatic_empty') and ann['judge_identity'] and ann['reviewed_at']
    if ann['judge_kind']=='automatic_empty':assert not pred['findings'],'Only empty structured output can close without semantic adjudication'
    findings={f['id']:f for f in pred['findings']};assert len(ann['findings'])==len(findings)
    assert {f['finding_id'] for f in ann['findings']}==set(findings)
    known={d['root_id']:d for d in g['defects'] if d['status']=='confirmed'}
    tp={};fp={};evidence=[];novel={};duplicates=0
    for a in ann['findings']:
        f=findings[a['finding_id']];disposition=a['disposition']
        assert a['reason'], 'Adjudication requires a reason, including rejection of apparent new defects'
        if disposition=='pending': return None
        assert a['evidence_valid'] in (True,False,None)
        if a['evidence_valid'] is not None: evidence.append(a['evidence_valid'])
        if disposition in ('matched','duplicate'):
            assert a['root_id'] in known, 'Unconfirmed Gold cannot count as confirmed detection'
            rid=a['root_id'];prev=tp.get(rid)
            if prev is not None:duplicates+=1
            if disposition=='duplicate' and prev is None:duplicates+=1
            if prev is None or LEVELS[f['severity']]>LEVELS[prev['severity']]: tp[rid]=f
        elif disposition=='false_positive':
            assert a['novel_issue_review'] and a['novel_issue_review']['status']=='rejected' and a['novel_issue_review']['basis'],'Unlisted finding needs explicit verification before FP'
            assert a['extra_root_id'],'Stable semantic ID needed for consistency, not wording match'
            previous=fp.get(a['extra_root_id'])
            if previous is None or LEVELS[f['severity']]>LEVELS[previous['severity']]:fp[a['extra_root_id']]=f
        elif disposition=='new_confirmed':
            assert a['novel_issue_review'] and a['novel_issue_review']['status']=='confirmed' and a['novel_issue_review']['basis']
            assert a['extra_root_id']
            previous=novel.get(a['extra_root_id'])
            if previous is None or LEVELS[f['severity']]>LEVELS[previous['severity']]:novel[a['extra_root_id']]=f
        else: raise ValueError('Unknown disposition: '+disposition)
    return {'meta':meta,'prediction':pred,'gold':g,'tp':tp,'fp':fp,'novel':novel,'evidence':evidence,'duplicates':duplicates,'adjudication':ann}


def detection_metrics(judged):
    valid=[r for r in judged if r['gold']['gold_status']=='confirmed']
    counts=collections.Counter();scores=[]
    for r in valid:
        known={d['root_id']:d for d in r['gold']['defects'] if d['status']=='confirmed'}
        counts['tp']+=len(r['tp'])+len(r['novel']);counts['fp']+=len(r['fp']);counts['gold']+=len(known)
        for key,levels in [('fatal',{'Fatal'}),('important',{'Fatal','Major'})]:
            roots={rid for rid,d in known.items() if d['severity'] in levels}
            counts[key+'_total']+=len(roots);counts[key+'_hit']+=len(roots & set(r['tp']))
        counts['severity_total']+=len(r['tp'])
        counts['severity_correct']+=sum(f['severity']==known[rid]['severity'] for rid,f in r['tp'].items())
        counts['evidence_total']+=len(r['evidence']);counts['evidence_valid']+=sum(r['evidence'])
        counts['novel_confirmed']+=len(r['novel']);counts['duplicates']+=r['duplicates']
        novel_levels={a['extra_root_id']:a['novel_issue_review'].get('expected_severity') for a in r['adjudication'].get('findings',[]) if a['disposition']=='new_confirmed'}
        for rid,f in r['novel'].items():
            if novel_levels.get(rid) in LEVELS:
                counts['novel_severity_total']+=1
                counts['novel_severity_correct']+=f['severity']==novel_levels[rid]
        if not known and not r['novel']:
            counts['clean_total']+=1;counts['clean_fp']+=bool(r['fp'])
        if r['prediction']['score'] is not None:
            counts['score_total']+=1
            counts['score_arithmetic_error']+=r['prediction']['score']!=score(r['prediction']['findings'])
            counts['deduplicated_score_error']+=r['prediction']['score']!=10-sum(LEVELS[f['severity']] for bucket in ('tp','fp','novel') for f in r[bucket].values())
    return {'reviewed_runs':len(valid),'excluded_unconfirmed_gold_runs':len(judged)-len(valid),'counts':dict(counts)}


def consistency_metrics(judged, plan):
    groups=collections.defaultdict(list)
    for r in judged:
        if r['gold']['gold_status']=='confirmed':groups[(r['meta']['skill'],r['meta']['case_id'])].append(r)
    result=[]
    for (skill,cid),rs in sorted(groups.items()):
        if len(rs)!=5: continue
        rs=sorted(rs,key=lambda x:x['meta']['repeat']);assert len({r['meta']['repeat'] for r in rs})==5
        signatures=[frozenset(list(r['tp'])+['extra:'+k for k in r['fp']]+['new:'+k for k in r['novel']]) for r in rs]
        pairwise=[1 if not a|b else len(a&b)/len(a|b) for a,b in itertools.combinations(signatures,2)]
        modal=collections.Counter(signatures).most_common(1)[0][1]
        severity={}
        classified=[{rid:f['severity'] for rid,f in r['tp'].items()}|{'extra:'+rid:f['severity'] for rid,f in r['fp'].items()}|{'new:'+rid:f['severity'] for rid,f in r['novel'].items()} for r in rs]
        for rid in set().union(*(r.keys() for r in classified)):
            choices=[r.get(rid,'absent') for r in classified]
            severity[rid]={'labels':choices,'modal_count':collections.Counter(choices).most_common(1)[0][1],'denominator':5}
        scores=[r['prediction']['score'] for r in rs]
        result.append({'skill':skill,'case_id':cid,'core_modal':{'numerator':modal,'denominator':5},'pairwise_jaccard':sum(pairwise)/10,'severity':severity,'scores':scores,'score_range':None if None in scores else max(scores)-min(scores),'score_stddev':None if None in scores else statistics.pstdev(scores),'unsupported_deductions':sum(len(r['fp']) for r in rs),'score_mismatch_runs':sum(r['prediction']['score'] is not None and r['prediction']['score']!=score(r['prediction']['findings']) for r in rs),'judge_kinds':sorted({r['adjudication']['judge_kind'] for r in rs})})
    return result


def equivalent_metrics(judged):
    bykey={(r['meta']['skill'],r['meta']['case_id']):r for r in judged if r['meta']['repeat']==1};out=[]
    for c in manifest()['equivalences']:
        for skill in sorted({r['meta']['skill'] for r in judged}):
            a=bykey.get((skill,c['equivalent_to']));b=bykey.get((skill,c['case_id']))
            if not a or not b:continue
            def signature(r):return {rid:f['severity'] for rid,f in r['tp'].items()}|{'extra:'+rid:f['severity'] for rid,f in r['fp'].items()}|{'new:'+rid:f['severity'] for rid,f in r['novel'].items()}
            out.append({'skill':skill,'case_id':c['case_id'],'equivalent_to':c['equivalent_to'],'same_core_and_severity':signature(a)==signature(b),'score_pair':[a['prediction']['score'],b['prediction']['score']]})
    return out


def apply_repair(folder, finding_id, destination, author_choice=None, repair_indices=None):
    folder=Path(folder);meta=read(folder/'run.json');assert meta['execution_status']=='completed'
    pred=read(folder/'prediction.json');finding=next(f for f in pred['findings'] if f['id']==finding_id)
    proposals=finding.get('repairs',[])
    edits=proposals if repair_indices is None else [proposals[i] for i in repair_indices]
    assert edits,'No actual model repair was provided'
    if any(p['conditional'] for p in edits) and not author_choice: raise ValueError('Conditional repair requires an explicit author-choice rationale')
    original=safe_child(ROOT,records()[meta['case_id']]['statement_path']).read_text(encoding='utf-8');text=original
    for p in edits:
        if not p['find'] or text.count(p['find'])!=1:raise ValueError('Repair must match exactly once; apply manual patch as an import instead')
        text=text.replace(p['find'],p['replace'],1)
    dest=Path(destination);assert not dest.exists(),'Never overwrite a repair bundle'
    dest.mkdir(parents=True);save_text(dest/'material.md',text)
    write(dest/'repair.json',{'case_id':meta['case_id'],'parent_run_id':meta['run_id'],'parent_raw_sha256':meta['raw_sha256'],'finding_id':finding_id,'source':'actual_model_suggestion','edits':edits,'repair_indices':repair_indices,'author_choice':author_choice,'original_sha256':sha(original.encode()),'statement_sha256':sha(text.encode()),'created_at':now(),'independent_verification':'pending'})
    return dest


def repair_reference_check(bundle, save=True):
    bundle=Path(bundle);meta=read(bundle/'repair.json');g=gold(meta['case_id']);text=(bundle/'material.md').read_text(encoding='utf-8')
    assert sha(text.encode())==meta['statement_sha256']
    assert g['statement_sha256']==meta['original_sha256'],'Original case changed after repair'
    result={'case_id':g['case_id'],'checked_at':now(),'source':'deterministic_reference_check','status':'needs_review','full_repair_confirmed':False,'statement_sha256':meta['statement_sha256'],'checks':[]}
    # Exact restoration of an independently sample-checked clean family is a sufficient local certificate
    # for these synthetic mutants, but still requires a separate full review for new issues.
    if g['version']=='mutant':
        clean=gold(g['case_id'].replace('-mutant','-base'));baseline=safe_child(ROOT,clean['statement_path']).read_text(encoding='utf-8')
        match=text==baseline and clean['gold_status']=='confirmed' and not clean['defects'] and sample_check(clean)
        result['checks'].append({'kind':'exact_clean_reference','passed':match,'reference_sha256':clean['statement_sha256']})
        if match:result['status']='reference_verified'
    result['note']='Reference equivalence verifies the original local defect under the authored reference; it is not an independent human audit or a successful model re-review.'
    if save:write(bundle/'reference-check.json',result)
    return result


def recheck_plan(source_plan,bundle):
    plan=read(source_plan);bundle=Path(bundle).resolve();repair=read(bundle/'repair.json')
    parent=next(x for x in plan['runs'] if x['run_id']==repair['parent_run_id'])
    portable_bundle=str(bundle.relative_to(ROOT)) if bundle.is_relative_to(ROOT) else str(bundle)
    entry={**parent,'run_id':parent['run_id']+'-repair-'+repair['statement_sha256'][:10],'phase':'repair','parent_run_id':parent['run_id'],'statement_sha256':repair['statement_sha256'],'repair_bundle':portable_bundle}
    return {**plan,'suite':'repair-recheck','created_at':now(),'runs':[entry]}


def repair_metrics(output):
    out=[]
    for p in sorted(Path(output).rglob('repair-assessment.json')):
        a=read(p)
        required={'case_id','root_id','parent_run_id','review_run_id','review_run_directory','resolved','changed_clear_semantics','domain_changed','new_spec_errors','locality','necessary','verification','judge_kind','judge_identity','reason','complete'}
        assert required<=set(a),('Incomplete repair assessment',p)
        if not a['complete'] or a['resolved']=='needs_review':continue
        assert a['judge_kind'] in ('human','independent_model','maintainer_model')
        assert a['resolved'] in ('complete','partial','failed','needs_review')
        review=Path(a['review_run_directory'])
        if not review.is_absolute():review=p.parent/review
        meta=read(review/'run.json')
        assert meta['execution_status']=='completed' and meta['phase']=='repair' and meta['run_id']==a['review_run_id'] and meta['parent_run_id']==a['parent_run_id']
        assert a['review_run_id']!=a['parent_run_id']
        # Merely repeating the re-review model's claim is insufficient.
        verified=False
        for v in a['verification']:
            if v.get('kind') not in ('enumeration','mathematical_proof','exact_reference','human_semantic_review'):continue
            if not v.get('artifact') or not v.get('result'):continue
            artifact=safe_child(p.parent,v['artifact'])
            assert artifact.is_file() and v.get('artifact_sha256')==sha(artifact.read_bytes()),'Missing or changed independent verification artifact'
            if v['kind']=='exact_reference':
                recomputed=repair_reference_check(p.parent,save=False)
                assert recomputed['status']=='reference_verified','Repair is not equivalent to clean reference'
            if v['kind']=='human_semantic_review':assert a['judge_kind']=='human','Model-generated review must not claim human confirmation'
            verified=True
        if not a['complete'] or not verified or a['resolved']=='needs_review':continue
        assert a['reason'] and a['judge_identity'] and isinstance(a['new_spec_errors'],list)
        assert isinstance(a['changed_clear_semantics'],bool) and isinstance(a['domain_changed'],bool) and isinstance(a['locality'],bool) and isinstance(a['necessary'],bool)
        repair=read(p.parent/'repair.json')
        assert meta['statement_sha256']==repair['statement_sha256']==sha((p.parent/'material.md').read_bytes()),'Repair review used a different candidate'
        assert a['case_id']==repair['case_id'] and a['parent_run_id']==repair['parent_run_id']
        assert meta['raw_sha256']==sha((review/'report.md').read_bytes()),'Repair review changed after execution'
        out.append({**a,'skill':meta['skill'],'candidate_sha256':repair['statement_sha256']})
    return out


def ratio(n,d):return {'numerator':n,'denominator':d,'value':n/d if d else None}
def fmt(n,d):return f'{n}/{d} ('+f'{100*n/d:.1f}%)' if d else f'{n}/{d} (N/A)'


def report(output,destination,repair_output=None):
    output=Path(output);plan=read(output/'plan.json');judged=[];states=collections.Counter();run_rows=[];sessions={};triage=[]
    for entry in plan['runs']:
        folder=output/entry['run_id']
        if not (folder/'run.json').exists():states['not_run']+=1;continue
        meta=read(folder/'run.json');states[meta['execution_status']]+=1
        session=meta.get('session_id') or event_evidence(folder)['session_id']
        if session:
            assert session not in sessions or sessions[session]==entry['run_id'],'One host session reused as independent runs'
            sessions[session]=entry['run_id']
        if (folder/'adjudication.json').exists():
            a=read(folder/'adjudication.json')
            if not a['complete'] or any(f['disposition']=='new_confirmed' for f in a['findings']):triage.append({'run_id':entry['run_id'],'case_id':meta['case_id'],'complete':a['complete'],'findings':a['findings']})
        j=judged_run(folder)
        if j:judged.append(j)
        run_rows.append({'run_id':entry['run_id'],'status':meta['execution_status'],'adjudicated':bool(j)})
    summary={'created_at':now(),'plan_suite':plan['suite'],'execution':dict(states),'planned_runs':len(plan['runs']),'observed_unique_sessions':len(sessions),'runs':run_rows,'triage':triage,'detection':{},'detection_by_split':{},'consistency':consistency_metrics(judged,plan),'equivalence':equivalent_metrics(judged),'repairs':repair_metrics(repair_output or output),'repair_results_source':str(repair_output or output),'targets':{'important_recall':0.85,'precision':0.90,'clean_fpr':0.10,'core_consistency':0.80,'effective_repair':0.85,'new_substantive_errors':0},'target_status':'not_established; requires complete coverage and closed adjudications'}
    lines=['# CPScore 题面审核评测报告','',f'生成时间：{now()}。套件：`{plan["suite"]}`；切分：`{plan["split"]}`。',f'计划 {len(plan["runs"])} 次，执行状态：`{dict(states)}`；完成根因裁定 {len(judged)} 次。','', '比例均列分子/分母；N/A 表示没有可用分母，不表示零分或通过。A/B/D 的已确认指标排除未执行、解析未完成、未裁定及 needs_review Gold，并保留覆盖缺口；C 固定以每版 20 个预设目标为分母，未闭合不计成功。','']
    for skill in plan['skills']:
        formal_ids={c['case_id'] for c in manifest()['cases']}
        rs=[r for r in judged if r['meta']['skill']==skill and r['meta']['repeat']==1 and r['meta'].get('phase','initial')=='initial' and r['meta']['case_id'] in formal_ids];metrics=detection_metrics(rs);summary['detection'][skill]=metrics;c=collections.Counter(metrics['counts'])
        lines+= [f'## {skill}：Evaluation A / D','',f'Skill：`{plan["skills"][skill]["commit"]}`；模型：`{plan["model"]}`，effort=`{plan["effort"]}`。','', '| 指标 | 分子/分母 |','| --- | --- |']
        for label,n,d in [('Precision',c['tp'],c['tp']+c['fp']),('Recall',sum(len(r['tp']) for r in rs if r['gold']['gold_status']=='confirmed'),c['gold']),('Important Recall',c['important_hit'],c['important_total']),('Fatal Recall',c['fatal_hit'],c['fatal_total']),('Correct-case FPR',c['clean_fp'],c['clean_total']),('Severity Accuracy',c['severity_correct'],c['severity_total']),('Evidence Validity',c['evidence_valid'],c['evidence_total'])]:lines.append(f'| {label} | {fmt(n,d)} |')
        summary['detection_by_split'][skill]={split:detection_metrics([r for r in rs if r['gold']['split']==split]) for split in ('development','holdout')}
        for split,subset in summary['detection_by_split'][skill].items():
            v=collections.Counter(subset['counts'])
            lines.append(f'\n{split}：已确认 Gold 的审核 {subset["reviewed_runs"]} 次；重要缺陷 {fmt(v["important_hit"],v["important_total"])}，Precision {fmt(v["tp"],v["tp"]+v["fp"])}，正确题 FPR {fmt(v["clean_fp"],v["clean_total"])}。')
        lines+=['',f'确认的 Gold 未记录问题：{c["novel_confirmed"]}，其中另经裁定的等级准确率 {fmt(c["novel_severity_correct"],c["novel_severity_total"])}（与冻结 Gold 等级指标分开）；重复报根因：{c["duplicates"]}；已评分报告中的算术不一致：{c["score_arithmetic_error"]}/{c["score_total"]}，按独立根因复算不一致：{c["deduplicated_score_error"]}/{c["score_total"]}。','', '| 题型 | TP | FP | 已知缺陷 | Fatal 命中/总数 |','| --- | --- | --- | --- | --- |']
        for kind in sorted(TYPES):
            sub=detection_metrics([r for r in rs if r['gold']['problem_type']==kind]);v=collections.Counter(sub['counts'])
            lines.append(f'| {kind} | {v["tp"]} | {v["fp"]} | {v["gold"]} | {v["fatal_hit"]}/{v["fatal_total"]} |')
        lines+=['','### 漏检、误报及证据失败','']
        details=[]
        for r in rs:
            missing=[d['root_id'] for d in r['gold']['defects'] if d['status']=='confirmed' and d['root_id'] not in r['tp']]
            if missing or r['fp'] or any(v is False for v in r['evidence']):details.append(f'- `{r["meta"]["case_id"]}`：漏检 {missing}；误报 {list(r["fp"])}；裁定见 `{r["meta"]["run_id"]}/adjudication.json`。')
        lines+=details or ['暂无已裁定的失败案例；这不表示没有失败，须结合执行及裁定覆盖。']
        lines+=['']
    paired={}
    for r in judged:
        if r['meta']['repeat']==1 and r['meta'].get('phase','initial')=='initial':paired.setdefault(r['meta']['case_id'],{})[r['meta']['skill']]=r
    comparison=[]
    for cid,pair in sorted(paired.items()):
        if {'original','improved'}<=set(pair):
            a,b=pair['original'],pair['improved']
            comparison.append({'case_id':cid,'new_hits':sorted(set(b['tp'])-set(a['tp'])),'lost_hits':sorted(set(a['tp'])-set(b['tp'])),'original_fp':sorted(a['fp']),'improved_fp':sorted(b['fp']),'original_novel':{rid:f['severity'] for rid,f in a['novel'].items()},'improved_novel':{rid:f['severity'] for rid,f in b['novel'].items()},'severity_pairs':{rid:[a['tp'][rid]['severity'],b['tp'][rid]['severity']] for rid in set(a['tp'])&set(b['tp'])}})
    summary['comparison']=comparison
    lines+=['## 新问题与未决裁定','']
    for row in triage:
        lines.append(f'- `{row["run_id"]}`：'+ '；'.join(f'{f["finding_id"]} {f["disposition"]}：{f["reason"]}' for f in row['findings']))
    lines+=['','## 旧版与新版差异','',f'可配对且已裁定题面：{len(comparison)}。以下保留识别与级别差异，不用分数变化代替分析。','']
    for row in comparison:
        if row['new_hits'] or row['lost_hits'] or row['original_fp']!=row['improved_fp'] or row['original_novel']!=row['improved_novel'] or any(a!=b for a,b in row['severity_pairs'].values()):
            lines.append(f'- `{row["case_id"]}`：新增命中 {row["new_hits"]}，漏失原命中 {row["lost_hits"]}；误报旧/新 {row["original_fp"]}/{row["improved_fp"]}；另确认的新问题旧/新 {row["original_novel"]}/{row["improved_novel"]}。具体证据及原因见两次原始报告与 adjudication。')
    lines+=['','## Evaluation B：稳定性与等价版本','']
    if not summary['consistency']:lines+=['暂无具有 5 次完整独立审核及根因裁定的题面组。']
    for r in summary['consistency']:lines.append(f'- `{r["skill"]}/{r["case_id"]}`：核心集合众数 {fmt(r["core_modal"]["numerator"],5)}；两两 Jaccard {r["pairwise_jaccard"]:.3f}；分数 {r["scores"]}，极差 {r["score_range"]}；等级序列见 JSON。')
    consistency_aggregate={}
    for skill in plan['skills']:
        groups=[r for r in summary['consistency'] if r['skill']==skill]
        consistency_aggregate[skill]={'complete_groups':len(groups),'planned_groups':12,'core_modal_consistency':ratio(sum(r['core_modal']['numerator'] for r in groups),5*len(groups)),'mean_pairwise_jaccard':statistics.mean(r['pairwise_jaccard'] for r in groups) if groups else None}
        lines.append(f'- `{skill}` 汇总：完成 {len(groups)}/12 组，核心集合众数一致性 {fmt(sum(r["core_modal"]["numerator"] for r in groups),5*len(groups))}；不足 12 组不代表完整 B 评测。')
    summary['consistency_aggregate']=consistency_aggregate
    lines+=['',f'等价版本已裁定对数：{len(summary["equivalence"])}，核心与级别一致：{sum(r["same_core_and_severity"] for r in summary["equivalence"])}。','', '## Evaluation C：修复','']
    repairs=summary['repairs'];target=len(manifest()['repair_targets']);summary['repair_aggregate']={}
    lines.append(f'每个 Skill 使用同样 {target} 个独立缺陷，保留第一候选；complete 表示目标根因消除，不宣称全文无缺陷。原已存在的其他问题保留在 remaining_preexisting_defects；待复核和未执行均不计作成功。')
    for skill in plan['skills']:
        rs=[r for r in repairs if r['skill']==skill]
        assert len({(r['case_id'],r['root_id']) for r in rs})==len(rs),'Multiple repair attempts counted for one Skill/root'
        counts=collections.Counter(r['resolved'] for r in rs)
        effective=sum(r['resolved']=='complete' and not r['changed_clear_semantics'] and not r['new_spec_errors'] for r in rs)
        scope_changes=[r['case_id'] for r in rs if r.get('domain_changed')]
        summary['repair_aggregate'][skill]={'closed_records':len(rs),'target_defects':target,'complete':ratio(counts['complete'],target),'partial':ratio(counts['partial'],target),'failed':ratio(counts['failed'],target),'unclosed':target-len(rs),'effective_without_new_error_or_changed_task':ratio(effective,target),'changed_clear_semantics':sum(r['changed_clear_semantics'] for r in rs),'domain_model_or_protocol_changed':scope_changes,'new_spec_errors':sum(len(r['new_spec_errors']) for r in rs),'local_and_necessary':sum(r['locality'] and r['necessary'] for r in rs)}
        lines.extend(['',f'- `{skill}`：闭合 {len(rs)}/{target}；完整 {fmt(counts["complete"],target)}，部分 {fmt(counts["partial"],target)}，失败 {fmt(counts["failed"],target)}，未闭合 {target-len(rs)}/{target}。',f'  无新增错误且不改变缺陷之外已明确规则的有效修复 {fmt(effective,target)}；改变这些明确规则 {sum(r["changed_clear_semantics"] for r in rs)}/{target}，新增规格错误 {sum(len(r["new_spec_errors"]) for r in rs)}；局部且必要 {sum(r["locality"] and r["necessary"] for r in rs)}/{target}。',f'  输入域、模型或协议资源变化另列 {len(scope_changes)}/{target}：{scope_changes}。这些条件修改不能被称作原设计完整保持。'])
    repair_pairs={}
    for r in repairs:repair_pairs.setdefault((r['case_id'],r['root_id']),{})[r['skill']]=r
    summary['repair_comparison']=[]
    for (cid,rid),pair in sorted(repair_pairs.items()):
        if not {'original','improved'}<=set(pair):continue
        def effective(r):return r['resolved']=='complete' and not r['changed_clear_semantics'] and not r['new_spec_errors']
        a,b=pair['original'],pair['improved']
        row={'case_id':cid,'root_id':rid,'original_resolved':a['resolved'],'improved_resolved':b['resolved'],'original_effective':effective(a),'improved_effective':effective(b)}
        summary['repair_comparison'].append(row)
        if row['original_resolved']!=row['improved_resolved'] or row['original_effective']!=row['improved_effective']:
            lines.append(f'\n修复配对差异 `{cid}/{rid}`：根因消除旧/新 {a["resolved"]}/{b["resolved"]}；严格有效旧/新 {effective(a)}/{effective(b)}，依据见该候选 proof.md 和 repair-assessment.json。')
    lines +=['','无已复核修订时，错误数为 0 不能证明新增错误目标已达到。','', '## 工程目标与限制','', '阈值是待验证的工程目标，当前不自动宣称达标。报告须具有正式全量覆盖、闭合新问题裁定及足够修复样本后，才可作整体结论。生成者为模型，Gold 未经人类专家确认；同模型生成与被测、全局宿主上下文、阅读负担判断及有限验证范围均应披露。','']
    write(output/'metrics.json',summary);save_text(destination,'\n'.join(lines))
    return summary




def repair_assessment_template(bundle,review_folder,root_id):
    bundle=Path(bundle).resolve();review=Path(review_folder).resolve();repair=read(bundle/'repair.json');meta=read(review/'run.json')
    assert meta['phase']=='repair' and meta['parent_run_id']==repair['parent_run_id']
    return {'case_id':repair['case_id'],'root_id':root_id,'parent_run_id':repair['parent_run_id'],'review_run_id':meta['run_id'],'review_run_directory':os.path.relpath(review,bundle),'resolved':'needs_review','changed_clear_semantics':None,'domain_changed':None,'new_spec_errors':[],'locality':None,'necessary':None,'verification':[],'judge_kind':None,'judge_identity':None,'reason':'','complete':False}


def import_manual_repair(folder,finding_id,material,destination,note,identity):
    folder=Path(folder);meta=read(folder/'run.json');pred=read(folder/'prediction.json')
    assert meta['execution_status']=='completed' and any(f['id']==finding_id for f in pred['findings'])
    assert note and identity
    original=safe_child(ROOT,records()[meta['case_id']]['statement_path']).read_bytes();candidate=Path(material).read_bytes()
    assert sha(original)==meta['statement_sha256'],'Source statement drift'
    destination=Path(destination);assert not destination.exists();destination.mkdir(parents=True)
    (destination/'material.md').write_bytes(candidate)
    write(destination/'repair.json',{'case_id':meta['case_id'],'parent_run_id':meta['run_id'],'parent_raw_sha256':meta['raw_sha256'],'finding_id':finding_id,'source':'operator_application_of_actual_advice','application_note':note,'operator_identity':identity,'original_sha256':sha(original),'statement_sha256':sha(candidate),'created_at':now(),'independent_verification':'pending'})
    return destination


def export_payload(plan_path,run_id,destination):
    plan=read(plan_path);entry=next(x for x in plan['runs'] if x['run_id']==run_id)
    snap=skill_snapshot(entry['skill']);assert snap['sha256']==plan['skills'][entry['skill']]['sha256']
    dest=Path(destination);assert not dest.exists();dest.mkdir(parents=True)
    statement=None
    if entry.get('phase')=='repair':
        bundle=Path(entry['repair_bundle'])
        if not bundle.is_absolute():bundle=safe_child(ROOT,entry['repair_bundle'])
        statement=(bundle/'material.md').read_text(encoding='utf-8')
    payload=stage_payload(entry,snap,dest,statement,review_prompt(plan))
    assert payload['files']['material.md']==entry['statement_sha256'],'Export payload drift'
    return payload


def normalize_prediction(folder,path,identity):
    folder=Path(folder);meta=read(folder/'run.json');assert meta['execution_status']=='completed'
    data=read(path);validate_prediction(data)
    assert sha((folder/'report.md').read_bytes())==meta['raw_sha256']
    if (folder/'adjudication.json').exists():raise ValueError('Remove or archive prior adjudication before correcting extraction')
    write(folder/'prediction.json',data)
    write(folder/'extraction.json',{'method':'operator_normalization','identity':identity,'raw_sha256':meta['raw_sha256'],'prediction_sha256':sha((folder/'prediction.json').read_bytes()),'created_at':now(),'note':'Operator must faithfully extract actual report, not invent new findings.'})


def merge_results(inputs, destination):
    plans=[read(Path(p)/'plan.json') for p in inputs];assert plans
    for plan in plans[1:]:
        for key in ('model','effort','skills','host_settings'):
            assert plan[key]==plans[0][key],('Incompatible experiment settings',key)
        if plan.get('manifest_sha256') and plans[0].get('manifest_sha256'):
            assert plan['manifest_sha256']==plans[0]['manifest_sha256'],'Incompatible manifests'
        assert plan.get('prompt_sha256',sha(PROMPT.encode()))==plans[0].get('prompt_sha256',sha(PROMPT.encode()))
    dest=Path(destination);assert not dest.exists(),'Merge into a new directory'
    dest.mkdir(parents=True);combined={**plans[0],'suite':'combined','split':'all','created_at':now(),'runs':[],'source_plans':[],'legacy_gold_bound_at_merge':[]}
    pinned_manifests={p['manifest_sha256'] for p in plans if p.get('manifest_sha256')}
    assert len(pinned_manifests)<=1,'Incompatible manifests'
    if pinned_manifests:combined['manifest_sha256']=next(iter(pinned_manifests))
    seen={}
    for source,plan in zip(inputs,plans):
        source=Path(source);combined['source_plans'].append({'path':str(source),'sha256':sha((source/'plan.json').read_bytes()),'manifest_pinned_before_run':bool(plan.get('manifest_sha256')),'gold_pinned_before_run':bool(plan.get('gold_sha256'))})
        for cid,value in plan.get('gold_sha256',{}).items():
            assert combined.setdefault('gold_sha256',{}).setdefault(cid,value)==value,'Conflicting frozen Gold hashes'
        for entry in plan['runs']:
            rid=entry['run_id'];folder=source/rid
            if entry.get('phase','initial')=='initial':
                cid=entry['case_id'];assert entry['statement_sha256']==records()[cid]['statement_sha256'],'Legacy input differs from frozen dataset'
                current=sha((ROOT/'gold'/f'{cid}.json').read_bytes())
                assert combined.setdefault('gold_sha256',{}).setdefault(cid,current)==current,'Gold differs from a frozen plan'
                if cid not in plan.get('gold_sha256',{}) and cid not in combined['legacy_gold_bound_at_merge']:
                    combined['legacy_gold_bound_at_merge'].append(cid)
            if rid in seen:
                old=dest/rid
                if folder.exists() and old.exists():assert read(folder/'run.json').get('raw_sha256')==read(old/'run.json').get('raw_sha256'),'Conflicting independent runs with the same ID; never select by score'
                if folder.exists() and not old.exists():shutil.copytree(folder,old)
                continue
            seen[rid]=entry;combined['runs'].append(entry)
            if folder.exists():shutil.copytree(folder,dest/rid)
    write(dest/'plan.json',combined);return combined


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('validate');p.add_argument('--smoke',action='store_true');p.add_argument('--output')
    p=sub.add_parser('plan');p.add_argument('--suite',choices=['smoke','a','b','c','d','equivalence','campaign'],required=True);p.add_argument('--split',choices=['development','holdout','all'],default='development');p.add_argument('--model',default='gpt-6.1-sol');p.add_argument('--effort',default='xhigh');p.add_argument('--output',required=True);p.add_argument('--direct',action='store_true',help='No CPScore Skill; task, grading contract and output schema only')
    p=sub.add_parser('run');p.add_argument('--plan',required=True);p.add_argument('--output',required=True);p.add_argument('--timeout',type=int,default=240);p.add_argument('--limit',type=int);p.add_argument('--executable',default='codex');p.add_argument('--workers',type=int,default=1)
    p=sub.add_parser('import');p.add_argument('--plan',required=True);p.add_argument('--run-id',required=True);p.add_argument('--raw',required=True);p.add_argument('--output',required=True);p.add_argument('--host',required=True);p.add_argument('--model',required=True);p.add_argument('--run-date',required=True)
    p=sub.add_parser('adjudication-template');p.add_argument('--run',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('apply-repair');p.add_argument('--run',required=True);p.add_argument('--finding-id',required=True);p.add_argument('--output',required=True);p.add_argument('--author-choice');p.add_argument('--repair-indices',help='Comma-separated zero-based advice indices; required to choose mutually exclusive alternatives')
    p=sub.add_parser('check-repair');p.add_argument('--bundle',required=True)
    p=sub.add_parser('recheck-plan');p.add_argument('--source-plan',required=True);p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('report');p.add_argument('--results',required=True);p.add_argument('--output',required=True);p.add_argument('--repair-results')
    p=sub.add_parser('export');p.add_argument('--plan',required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('normalize');p.add_argument('--run',required=True);p.add_argument('--prediction',required=True);p.add_argument('--identity',required=True)
    p=sub.add_parser('merge');p.add_argument('--inputs',nargs='+',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('repair-assessment-template');p.add_argument('--bundle',required=True);p.add_argument('--review-run',required=True);p.add_argument('--root-id',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('import-repair');p.add_argument('--run',required=True);p.add_argument('--finding-id',required=True);p.add_argument('--material',required=True);p.add_argument('--output',required=True);p.add_argument('--note',required=True);p.add_argument('--identity',required=True)
    args=parser.parse_args()
    if args.command=='validate':
        result=validate(args.smoke)
        if args.output:write(args.output,result)
    elif args.command=='plan':write(args.output,(make_direct_plan if args.direct else make_plan)(args.suite,args.split,args.model,args.effort))
    elif args.command=='run':
        if not run_plan(args.plan,args.output,args.timeout,args.limit,args.executable,args.workers):raise SystemExit(1)
    elif args.command=='import':import_result(args.plan,args.run_id,args.raw,args.output,args.host,args.model,args.run_date)
    elif args.command=='adjudication-template':write(args.output,adjudication_template(args.run))
    elif args.command=='apply-repair':apply_repair(args.run,args.finding_id,args.output,args.author_choice,None if args.repair_indices is None else [int(i) for i in args.repair_indices.split(',')])
    elif args.command=='check-repair':print(json.dumps(repair_reference_check(args.bundle),ensure_ascii=False))
    elif args.command=='recheck-plan':write(args.output,recheck_plan(args.source_plan,args.bundle))
    elif args.command=='report':report(args.results,args.output,args.repair_results)
    elif args.command=='export':print(json.dumps(export_payload(args.plan,args.run_id,args.output),ensure_ascii=False))
    elif args.command=='normalize':normalize_prediction(args.run,args.prediction,args.identity)
    elif args.command=='merge':merge_results(args.inputs,args.output)
    elif args.command=='repair-assessment-template':write(args.output,repair_assessment_template(args.bundle,args.review_run,args.root_id))
    elif args.command=='import-repair':import_manual_repair(args.run,args.finding_id,args.material,args.output,args.note,args.identity)

if __name__=='__main__':main()
