#!/usr/bin/env python3
"""Offline tests only. Synthetic parser/metric fixtures below are NOT model results."""
import contextlib
import subprocess
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
import evaluate as e
import compare_harness as comparison
from oracles import solve, sample_check


class DatasetChecks(unittest.TestCase):
    def test_smoke_before_formal_validation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(e.validate(True)['checked_versions'],8)
            self.assertEqual(e.validate()['checked_versions'],60)

    def test_all_clean_base_samples_are_independently_parsed(self):
        for c in e.manifest()['cases']:
            if c['version']=='base' and c['original_kind']=='clean':
                self.assertTrue(sample_check(e.gold(c['case_id'])),c['case_id'])

    def test_family_split_and_equivalences(self):
        families={}
        for c in e.records().values():
            self.assertEqual(families.setdefault(c['family_id'],c['split']),c['split'])
        self.assertEqual(len(families),40)
        for c in e.manifest()['equivalences']:
            self.assertEqual(c['split'],e.records()[c['equivalent_to']]['split'])

    def test_gold_and_prompt_never_enter_payload(self):
        # Reuse the actual current Skill files; CI needs no Git history or model CLI.
        root=e.REPO/'skills/cp-statement-review'
        snap={'files':{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}}
        with tempfile.TemporaryDirectory() as temp:
            entry={'case_id':'st-025-base'}
            payload=e.stage_payload(entry,snap,temp)
            files={p.relative_to(temp).as_posix() for p in Path(temp).rglob('*') if p.is_file()}
            self.assertEqual(files,set(payload['files']))
            self.assertEqual(payload['files']['material.md'],e.records()['st-025-base']['statement_sha256'])
            self.assertNotIn(b'\r',(Path(temp)/'request.txt').read_bytes())
            self.assertEqual({p for p in files if not p.startswith('.agents/')},{'material.md','request.txt'})
            self.assertNotIn('Gold',Path(temp,'material.md').read_text(encoding='utf-8'))
            self.assertNotIn('st-025',Path(temp,'request.txt').read_text(encoding='utf-8'))
            self.assertNotIn('gold/',e.PROMPT)

    def test_plan_counts_and_repeated_sessions_are_distinct(self):
        def snapshot(label):return {'label':label,'commit':'unit-'+label,'sha256':'unit-'+label,'files':{}}
        with patch.object(e,'skill_snapshot',side_effect=snapshot):
            self.assertEqual(len(e.make_plan('a','all')['runs']),112)
            self.assertEqual(len(e.make_plan('b','all')['runs']),120)
            plan=e.make_plan('campaign','all')
            self.assertEqual(len(plan['runs']),216)
            self.assertEqual(len({r['run_id'] for r in plan['runs']}),216)
            for cid in e.manifest()['consistency_cases']:
                for skill in ('original','improved'):
                    self.assertEqual({r['repeat'] for r in plan['runs'] if r['case_id']==cid and r['skill']==skill},{1,2,3,4,5})

    def test_direct_control_plan_and_payload_do_not_load_cpscore(self):
        def snapshot(label):return {'label':label,'commit':None,'sha256':e.skill_fingerprint({}),'files':{}}
        with patch.object(e,'skill_snapshot',side_effect=snapshot):
            plan=e.make_direct_plan('campaign','all')
        self.assertEqual(len(plan['runs']),108)
        self.assertEqual(set(plan['skills']),{'direct'})
        self.assertIn('cp-statement-review',plan['disabled_skill_names'])
        self.assertEqual(plan['prompt_sha256'],e.sha(e.DIRECT_PROMPT.encode()))
        with tempfile.TemporaryDirectory() as temp:
            payload=e.stage_payload(plan['runs'][0],snapshot('direct'),temp,prompt=e.review_prompt(plan))
            self.assertEqual(set(payload['files']),{'material.md','request.txt'})
            self.assertFalse((Path(temp)/'.agents').exists())
            self.assertNotIn('references/',(Path(temp)/'request.txt').read_text(encoding='utf-8'))
        self.assertEqual(e.skill_snapshot('direct')['files'],{})

    def test_direct_and_cpscore_prompts_have_same_output_contract(self):
        marker='\n正常输出 Markdown'
        self.assertEqual(e.PROMPT[e.PROMPT.index(marker):],e.DIRECT_PROMPT[e.DIRECT_PROMPT.index(marker):])
        with self.assertRaises(AssertionError):e.review_prompt({'review_mode':'direct','skills':{'improved':{}}})

    def test_skill_exclusion_glob_is_not_a_skill_content_read(self):
        listing={'command':"/bin/zsh -lc \"pwd && rg --files -g '!SKILL.md'\"",'aggregated_output':'/private/tmp/cp-statement-unit\nmaterial.md\nrequest.txt\n'}
        self.assertTrue(comparison.neutral_file_inventory(listing))
        listing['command']="/bin/zsh -lc \"pwd; rg --files -g '!SKILL.md'\""
        self.assertTrue(comparison.neutral_file_inventory(listing))
        self.assertFalse(comparison.neutral_file_inventory({'command':"/bin/zsh -lc 'cat SKILL.md'",'aggregated_output':'skill contents'}))
        listing['command']="/bin/zsh -lc \"rg --files -g '!SKILL.md'; cat SKILL.md\""
        self.assertFalse(comparison.neutral_file_inventory(listing))

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):e.safe_child(e.ROOT,'../README.md')
        with self.assertRaises(ValueError):e.safe_child(e.ROOT,'/etc/passwd')

    def test_host_initialization_failure_is_saved_and_stops_scheduling(self):
        snapshot=lambda label:{'label':label,'commit':'unit','sha256':'unit','files':{}}
        with tempfile.TemporaryDirectory() as temp, patch.object(e,'skill_snapshot',side_effect=snapshot):
            root=Path(temp);plan=e.make_plan('smoke');plan['runs']=plan['runs'][:2]
            e.write(root/'plan.json',plan)
            failure=subprocess.CalledProcessError(1,['unit-only-host','--version'])
            with patch.object(e.subprocess,'check_output',side_effect=failure), contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(e.run_plan(root/'plan.json',root/'results',workers=1))
            first=root/'results'/plan['runs'][0]['run_id']
            self.assertEqual(e.read(first/'run.json')['execution_status'],'failed')
            self.assertFalse((first/'prediction.json').exists())
            self.assertFalse((root/'results'/plan['runs'][1]['run_id']).exists())

    def test_export_repair_uses_candidate_instead_of_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle=root/'candidate';bundle.mkdir()
            candidate='unit-only revised statement\n';e.save_text(bundle/'material.md',candidate)
            plan={'skills':{'improved':{'sha256':'unit'}},'runs':[{'run_id':'unit-repair',
                  'case_id':'st-012-mutant','skill':'improved','phase':'repair',
                  'repair_bundle':str(bundle),'statement_sha256':e.sha(candidate.encode())}]}
            e.write(root/'plan.json',plan)
            with patch.object(e,'skill_snapshot',return_value={'sha256':'unit','files':{}}):
                e.export_payload(root/'plan.json','unit-repair',root/'payload')
            self.assertEqual((root/'payload/material.md').read_text(encoding='utf-8'),candidate)

    def test_merge_keeps_all_gold_hashes_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            base={'model':'unit','effort':'unit','skills':{},'host_settings':{},
                  'manifest_sha256':'same','runs':[],'gold_sha256':{}}
            for name,hashes in [('development',{'unit-a':'a'}),('holdout',{'unit-b':'b'})]:
                e.write(root/name/'plan.json',{**base,'gold_sha256':hashes})
            result=e.merge_results([root/'development',root/'holdout'],root/'combined')
            self.assertEqual(result['gold_sha256'],{'unit-a':'a','unit-b':'b'})
            e.write(root/'holdout/plan.json',{**base,'gold_sha256':{'unit-a':'conflict'}})
            with self.assertRaises(AssertionError):
                e.merge_results([root/'development',root/'holdout'],root/'conflict')

    def test_legacy_plan_merge_discloses_post_run_gold_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cid='st-001-base'
            plan={'model':'unit','effort':'unit','skills':{},'host_settings':{},'runs':[
                {'run_id':'unit-only','phase':'initial','case_id':cid,
                 'statement_sha256':e.records()[cid]['statement_sha256']}]}
            e.write(root/'legacy/plan.json',plan)
            result=e.merge_results([root/'legacy'],root/'combined')
            self.assertEqual(result['legacy_gold_bound_at_merge'],[cid])
            self.assertFalse(result['source_plans'][0]['gold_pinned_before_run'])
            self.assertEqual(result['gold_sha256'][cid],e.sha((e.ROOT/'gold'/f'{cid}.json').read_bytes()))

    def test_recorded_repair_witness_programs_are_offline_and_reproducible(self):
        for script in (e.ROOT/'results/repairs').glob('*/verify.py'):
            result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,encoding='utf-8',check=True)
            value=json.loads(result.stdout)
            self.assertEqual(value['status'],'passed')
            self.assertEqual(value['candidate_sha256'],e.sha((script.parent/'material.md').read_bytes()))

    def test_sample_witnesses_are_not_assumed_correct(self):
        g=e.gold('st-010-base');g['samples'][0]['output']='YES\n11\n00\n'
        self.assertFalse(sample_check(g))
        g=e.gold('st-001-base');g['samples'][0]['output']='0\n'
        self.assertFalse(sample_check(g))

    def test_information_lower_bounds(self):
        self.assertFalse(solve('information_bound',{'states':8,'replies':2,'queries':2}))
        self.assertTrue(solve('information_bound',{'states':8,'replies':2,'queries':3}))
        self.assertFalse(solve('communication_bound',{'n':4,'message_bits':3}))
        self.assertTrue(solve('communication_bound',{'n':4,'message_bits':4}))

    def test_small_boundary_models(self):
        self.assertEqual(solve('booking',{'capacity':[0],'orders':[[1,1,1]]}),1)
        self.assertEqual(solve('dag',{'n':1,'edges':[]}),[0,1])
        self.assertEqual(solve('circular',{'a':[-3,-1,-2]}),-1)
        self.assertEqual(solve('centroid',{'points':[[0,0,1]]}),[0,0])
        self.assertEqual(solve('warehouse',{'stock':1,'cap':3,'days':[[5,4]]}),[0,2])
        self.assertEqual(solve('robots',{'robots':[[0,'R'],[1,'L']],'turns':1}),[[1,1],[2,0]])
        self.assertEqual(solve('round_robin',{'tasks':[[0,2],[1,1]]}),[3,2])
        self.assertEqual(solve('direction_witness',{}),[1,2])
        self.assertEqual(solve('matching_conflict',{}),[2,1])


class ExtractionAndMetrics(unittest.TestCase):
    def pred(self,findings=None,score=10):
        return {'score':score,'complete':True,'findings':findings or [],'optional_suggestions':[]}
    def finding(self,level='Fatal',fid='f1'):
        return {'id':fid,'severity':level,'quote':'original text','evidence':'counterexample','repairs':[]}

    def test_harness_comparison_separates_format_from_semantic_recall(self):
        rows=[self.judged('st-009-mutant',tp={'literal_markup':self.finding('Major')}),
              self.judged('st-001-mutant')]
        self.assertEqual(comparison.known_recall(rows),e.ratio(0,1))
        self.assertEqual(comparison.known_recall(rows,True),e.ratio(1,1))

    def test_unavailable_advice_is_not_removed_from_repair_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            e.write(Path(temp)/'one/repair-unavailable.json',{'case_id':'unit-case','reason':'unit-only fixture'})
            metrics=comparison.repair_summary(temp,'direct')
            self.assertEqual(metrics['effective'],e.ratio(0,20))
            self.assertEqual(len(metrics['unavailable_advice']),1)
            self.assertEqual(metrics['pending'],19)
    def judged(self,cid,tp=None,fp=None,novel=None,findings=None,score=10,repeat=1):
        return {'meta':{'skill':'improved','case_id':cid,'repeat':repeat},'gold':e.gold(cid),'prediction':self.pred(findings,score),'tp':tp or {},'fp':fp or {},'novel':novel or {},'evidence':[True],'duplicates':0,'adjudication':{'judge_kind':'maintainer_model'}}

    def test_extract_json_and_no_findings_is_valid(self):
        raw='report\n```json\n'+json.dumps(self.pred())+'\n```'
        self.assertEqual(e.parse_report(raw),self.pred())
        self.assertEqual(e.parse_report(json.dumps(self.pred())),self.pred())

    def test_text_witness_before_json_does_not_swallow_json_fence(self):
        raw='report\n```text\n1 2 3\n```\nexplanation\n```json\n'+json.dumps(self.pred())+'\n```'
        self.assertEqual(e.parse_report(raw),self.pred())

    def test_markdown_candidate_is_not_a_completed_review(self):
        result=e.parse_report('[Fatal -10] suspected issue\n')
        self.assertFalse(result['complete']);self.assertEqual(result['parse_status'],'needs_review')

    def test_invalid_structured_output_is_rejected(self):
        with self.assertRaises(AssertionError):e.parse_report(json.dumps(self.pred([self.finding(),self.finding()])))
        with self.assertRaises(AssertionError):e.validate_prediction(self.pred(score=float('nan')))

    def test_root_dedup_and_raw_denominators(self):
        f=self.finding();r=self.judged('st-025-base',{'direction':f},findings=[f],score=0)
        clean=self.judged('st-001-base',fp={'invented-root':self.finding('Minor')})
        metrics=e.detection_metrics([r,clean])['counts']
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['gold']),(1,1,1))
        self.assertEqual((metrics['clean_fp'],metrics['clean_total']),(1,1))
        self.assertEqual((metrics['fatal_hit'],metrics['fatal_total']),(1,1))
        self.assertEqual(metrics['severity_correct'],1)

    def test_unconfirmed_gold_is_excluded(self):
        r=self.judged('st-030-base')
        metrics=e.detection_metrics([r])
        self.assertEqual(metrics['reviewed_runs'],0)
        self.assertEqual(metrics['excluded_unconfirmed_gold_runs'],1)
        self.assertIsNone(e.ratio(0,0)['value'])

    def test_consistency_tracks_roots_and_severity_not_only_score(self):
        rs=[]
        for i in range(5):
            tp={'direction':self.finding('Fatal' if i<4 else 'Major')} if i<4 else {}
            fp={} if i<4 else {'invented-root':self.finding('Fatal')}
            rs.append(self.judged('st-025-base',tp,fp,score=0,repeat=i+1))
        out=e.consistency_metrics(rs,{})[0]
        self.assertEqual(out['core_modal']['numerator'],4)
        self.assertEqual(out['score_range'],0)
        self.assertEqual(out['unsupported_deductions'],1)
        self.assertLess(out['pairwise_jaccard'],1)
        self.assertEqual(out['severity']['direction']['labels'][-1],'absent')

    def test_pending_adjudication_template_does_not_claim_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw='unit test fixture, NOT model output'
            e.write(p/'run.json',{'run_id':'unit-only','case_id':'st-001-base','execution_status':'completed','raw_sha256':e.sha(raw.encode())})
            e.write(p/'prediction.json',self.pred());(p/'report.md').write_text(raw,encoding='utf-8')
            e.write(p/'adjudication.json',e.adjudication_template(p))
            self.assertIsNone(e.judged_run(p))

    def test_duplicate_findings_take_highest_severity_once(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw='unit test fixture, NOT model output'
            e.write(p/'run.json',{'run_id':'unit-only','case_id':'st-025-base','execution_status':'completed','raw_sha256':e.sha(raw.encode())})
            e.write(p/'prediction.json',self.pred([self.finding('Major','f1'),self.finding('Fatal','f2')],-2));(p/'report.md').write_text(raw,encoding='utf-8')
            ann=e.adjudication_template(p);ann.update(complete=True,judge_kind='human',judge_identity='unit fixture',reviewed_at=e.now())
            for item in ann['findings']:item.update(disposition='matched',root_id='direction',reason='unit fixture root match',evidence_valid=True)
            e.write(p/'adjudication.json',ann);r=e.judged_run(p)
            self.assertEqual(len(r['tp']),1);self.assertEqual(r['tp']['direction']['severity'],'Fatal')
            metrics=e.detection_metrics([r])['counts']
            self.assertEqual(metrics['tp'],1);self.assertEqual(metrics['deduplicated_score_error'],1)

    def test_same_session_cannot_be_counted_as_independent_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);e.write(p/'plan.json',{'runs':[{'run_id':'one'},{'run_id':'two'}]})
            for rid in ('one','two'):
                folder=p/rid;folder.mkdir();e.write(folder/'run.json',{'execution_status':'completed','session_id':'unit-same-session'})
            with self.assertRaises(AssertionError):e.report(p,p/'report.md')

    def test_unknown_findings_need_review_before_false_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw='unit test fixture, NOT model output';f=self.finding('Minor')
            meta={'run_id':'unit-only','case_id':'st-001-base','execution_status':'completed','raw_sha256':e.sha(raw.encode())}
            e.write(p/'run.json',meta);e.write(p/'prediction.json',self.pred([f],9));(p/'report.md').write_text(raw,encoding='utf-8')
            ann=e.adjudication_template(p);ann.update(complete=True,judge_kind='human',judge_identity='unit test',reviewed_at=e.now())
            ann['findings'][0].update(disposition='false_positive',extra_root_id='unit-only-root',reason='unit-test rejection')
            e.write(p/'adjudication.json',ann)
            with self.assertRaises(AssertionError):e.judged_run(p)
            ann['findings'][0]['novel_issue_review']={'status':'rejected','basis':'explicit context rules out interpretation'}
            e.write(p/'adjudication.json',ann);self.assertEqual(len(e.judged_run(p)['fp']),1)

    def test_repair_is_from_actual_saved_advice_and_not_silently_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'run';p.mkdir();g=e.gold('st-012-mutant');repair=g['defects'][0]['acceptable_repairs'][0]
            meta={'execution_status':'completed','case_id':g['case_id'],'run_id':'unit-only','raw_sha256':'unit-only'}
            e.write(p/'run.json',meta);f=self.finding('Minor');f['repairs']=[repair];e.write(p/'prediction.json',self.pred([f],9))
            dest=Path(temp)/'repair';e.apply_repair(p,'f1',dest)
            self.assertEqual(e.repair_reference_check(dest)['status'],'reference_verified')
            self.assertFalse(e.repair_reference_check(dest)['full_repair_confirmed'])
            f['repairs'][0]['conditional']=True;e.write(p/'prediction.json',self.pred([f],9))
            with self.assertRaises(ValueError):e.apply_repair(p,'f1',Path(temp)/'conditional')

    def test_no_results_do_not_produce_passing_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);plan={'suite':'unit-only','split':'development','runs':[{'run_id':'missing'}],'skills':{'original':{'commit':'unit-only'}},'model':'unit-only','effort':'unit-only'}
            e.write(p/'plan.json',plan);summary=e.report(p,p/'report.md')
            self.assertEqual(summary['execution']['not_run'],1)
            self.assertIn('not_established',summary['target_status'])
            self.assertIn('N/A',(p/'report.md').read_text(encoding='utf-8'))

    def test_repair_denominators_remain_paired_and_include_unclosed_targets(self):
        # Metric fixtures only; never written into actual evaluation directories.
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            plan={'suite':'unit-only','split':'all','runs':[],
                  'skills':{k:{'commit':'unit-only'} for k in ('original','improved')},
                  'model':'unit-only','effort':'unit-only'}
            e.write(p/'plan.json',plan)
            rs=[{'skill':skill,'case_id':'unit-case','root_id':'unit-root','resolved':'complete',
                 'changed_clear_semantics':skill=='original','new_spec_errors':[],
                 'locality':True,'necessary':True} for skill in plan['skills']]
            with patch.object(e,'repair_metrics',return_value=rs):
                summary=e.report(p,p/'report.md')
            for skill in plan['skills']:
                agg=summary['repair_aggregate'][skill]
                self.assertEqual(agg['complete']['denominator'],20)
                self.assertEqual(agg['closed_records'],1)
                self.assertEqual(agg['unclosed'],19)
            self.assertEqual(summary['repair_aggregate']['original']['effective_without_new_error_or_changed_task']['numerator'],0)
            self.assertEqual(summary['repair_aggregate']['improved']['effective_without_new_error_or_changed_task']['numerator'],1)

    def test_newly_confirmed_severity_is_visible_without_changing_frozen_gold(self):
        finding=self.finding('Minor')
        run=self.judged('st-029-base',novel={'unit-extra':finding})
        run['adjudication']['findings']=[{'disposition':'new_confirmed','extra_root_id':'unit-extra',
                                         'novel_issue_review':{'expected_severity':'Major'}}]
        result=e.detection_metrics([run])['counts']
        self.assertEqual(result['novel_severity_total'],1)
        self.assertEqual(result['novel_severity_correct'],0)
        self.assertEqual(result['gold'],1)
        self.assertEqual(result['severity_total'],0)

if __name__=='__main__':unittest.main(verbosity=2)
