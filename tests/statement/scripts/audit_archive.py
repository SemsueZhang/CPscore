#!/usr/bin/env python3
"""Audit saved real runs and repair proofs offline; never invoke a model."""
import argparse
import collections
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import evaluate as e


def audit(main, reviews, repairs, freeze):
    frozen=e.read(freeze)
    assert e.sha((e.ROOT/'manifest.json').read_bytes())==frozen['manifest_sha256']
    assert e.sha(e.PROMPT.encode())==frozen['prompt_sha256']
    for cid,c in e.records().items():
        assert e.sha((e.ROOT/c['statement_path']).read_bytes())==frozen['case_sha256'][cid]
        assert e.sha((e.ROOT/'gold'/f'{cid}.json').read_bytes())==frozen['gold_sha256'][cid]
    sessions=set();counts={};judges=collections.Counter();source_counts=collections.Counter()
    for directory,expected in [(Path(main),216),(Path(reviews),40)]:
        plan=e.read(directory/'plan.json');assert len(plan['runs'])==expected
        states=collections.Counter()
        for entry in plan['runs']:
            folder=directory/entry['run_id'];meta=e.read(folder/'run.json')
            states[meta['execution_status']]+=1;assert meta['execution_status']=='completed'
            assert meta['model']==frozen['model'] and meta['effort']==frozen['effort']
            assert meta['skill_version']==frozen['skills'][entry['skill']]
            raw=(folder/'report.md').read_bytes();assert e.sha(raw)==meta['raw_sha256']
            pred=e.read(folder/'prediction.json');assert pred['complete']
            assert e.parse_report(raw.decode('utf-8'))==pred,'Saved extraction differs from actual output'
            native=e.event_evidence(folder);assert len(native['observed_session_ids'])==1
            sid=native['session_id'];assert sid and sid not in sessions
            sessions.add(sid);source_counts[meta['source']]+=1
            # The frozen fingerprint covers both paths and file hashes. This also works in
            # shallow CI checkouts, without fetching old Git objects or invoking a host.
            prefix='.agents/skills/cp-statement-review/'
            package={p[len(prefix):]:h for p,h in meta['payload']['files'].items() if p.startswith(prefix)}
            assert e.skill_fingerprint(package)==frozen['skills'][entry['skill']]['sha256']
            expected_files={'material.md':meta['statement_sha256'],'request.txt':frozen['prompt_sha256']}
            expected_files.update({prefix+p:h for p,h in package.items()})
            assert meta['payload']['files']==expected_files,'Unexpected file or hash in model payload'
            if meta['phase']=='initial':
                assert meta['statement_sha256']==e.records()[meta['case_id']]['statement_sha256']
                if (folder/'adjudication.json').exists():judges[e.read(folder/'adjudication.json')['judge_kind']]+=1
            else:
                bundle=Path(repairs)/(meta['skill']+'-'+meta['case_id']);repair=e.read(bundle/'repair.json')
                assert repair['statement_sha256']==meta['statement_sha256']==e.sha((bundle/'material.md').read_bytes())
                parent=e.read(Path(main)/repair['parent_run_id']/'run.json')
                assert repair['parent_raw_sha256']==parent['raw_sha256']
                pre=e.read(bundle/'pre-review-analysis.json')
                assert dt.datetime.fromisoformat(pre['registered_at'])<dt.datetime.fromisoformat(meta['started_at'])
        counts[directory.name]=dict(states)
    closed=e.repair_metrics(repairs);assert len(closed)==40
    programs=[]
    for bundle in sorted(Path(repairs).glob('*')):
        if not (bundle/'repair.json').is_file():continue
        result=subprocess.run([sys.executable,str(bundle/'verify.py')],capture_output=True,text=True,encoding='utf-8',check=True)
        actual=json.loads(result.stdout);saved=e.read(bundle/'verification.json')
        assert saved=={**actual,'verification_script_sha256':e.sha((bundle/'verify.py').read_bytes())}
        assert actual['status']=='passed'
        assessment=e.read(bundle/'repair-assessment.json');pre=e.read(bundle/'pre-review-analysis.json')
        for key in ('changed_clear_semantics','domain_changed','locality','necessary'):
            assert assessment[key]==pre[key],'Scope classification changed after re-review'
        programs.append(bundle.name)
    assert len(programs)==40 and len(sessions)==256
    return {'checked_at':e.now(),'status':'passed','benchmark_revision':frozen['benchmark_revision'],
            'frozen_case_and_gold_pairs':60,'execution':counts,'unique_evaluated_sessions':len(sessions),
            'exact_neutral_payloads':256,'closed_repair_assessments':len(closed),'reexecuted_repair_programs':programs,
            'main_adjudication_kinds':dict(judges),'record_sources':dict(source_counts),
            'limits':['Hash and file isolation checks are not an OS-level access barrier.',
                      'Finite programs and maintainer-model proofs do not establish human-expert validation.',
                      'Two subjective Golds and related pending adjudications remain excluded from confirmed metrics.',
                      'Legacy development Gold hashes were bound at merge, not retroactively before calls.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);root=e.ROOT/'results'
    p.add_argument('--main',default=root/'final');p.add_argument('--reviews',default=root/'repair-reviews')
    p.add_argument('--repairs',default=root/'repairs');p.add_argument('--freeze',default=root/'protocol-freeze.json')
    p.add_argument('--output',default=root/'archive-audit.json');args=p.parse_args()
    value=audit(args.main,args.reviews,args.repairs,args.freeze);e.write(args.output,value)
    print(json.dumps({k:v for k,v in value.items() if k!='reexecuted_repair_programs'},ensure_ascii=False))
