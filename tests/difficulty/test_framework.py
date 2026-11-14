"""Offline contract and integration tests. No real model calls or accuracy claims."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / 'skills/cp-difficulty-luogu'
sys.path.insert(0, str(SKILL / 'scripts'))
import common
import difficulty
import experts
import benchmark
import codex_adapter

BENCH = os.environ.get('LUOGUBENCH_ROOT')
FIXTURE = common.read_json(Path(__file__).parent / 'fixtures/item.json')


def prediction(item_id='synthetic_sum', level=1):
    return {'id': item_id, 'level': level, 'label': {0: '未知', **common.LEVELS}[level], 'reason': '合成接口测试数据，不是模型评测。'}


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cpscore luogu test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = {'format_version': 1, 'development_dataset_ids': ['old87'], 'records': []}
        self.split = benchmark.make_manifest([FIXTURE], 'synthetic_test', 'independent', self.registry)
        row = self.split['items'][0]
        row.update(problem_id='synthetic_identity', family_id='synthetic_family',
                   solution_problem_ids={'method_1': 'synthetic_identity'},
                   review={'status': 'confirmed', 'reviewer': 'test fixture curator',
                           'reviewed_on': '2026-11-14', 'notes': 'Synthetic material and family test only.'})

    def prepared(self, mode='skill', scope='single'):
        path = self.root / (mode + '_' + scope)
        difficulty.prepare([FIXTURE], path, mode, 'test-model', scope=scope)
        return path

    def test_native_levels_and_unknown(self):
        for level in range(1, 9):
            common.validate_prediction(prediction(level=level), FIXTURE['id'])
        common.validate_prediction(prediction(level=0), FIXTURE['id'], allow_unknown=True)
        with self.assertRaises(ValueError):
            common.validate_prediction(prediction(level=0), FIXTURE['id'])

    def test_invalid_level_types_ranges(self):
        for level in [-1, 9, True, False, 1.0, None, float('nan'), '3']:
            with self.subTest(level=level), self.assertRaises(ValueError):
                common.validate_prediction({**prediction(), 'level': level}, FIXTURE['id'], allow_unknown=True)

    def test_result_format_and_identity(self):
        for change in [{'id': 'another'}, {'label': '普及'}, {'reason': ' '}, {'K': 2}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                common.validate_prediction({**prediction(), **change}, FIXTURE['id'])
        row = prediction()
        row.pop('reason')
        with self.assertRaises(ValueError):
            common.validate_prediction(row, FIXTURE['id'])

    def test_label_fields_do_not_enter_input(self):
        with self.assertRaises(ValueError):
            common.validate_item({**FIXTURE, 'level': 1})
        item = deepcopy(FIXTURE)
        item['solutions'][0]['actual_label'] = '入门'
        with self.assertRaises(ValueError):
            common.validate_item(item)

    def test_incomplete_and_duplicate_routes_rejected(self):
        for item in [{**FIXTURE, 'solutions': []}, {**FIXTURE, 'solutions': FIXTURE['solutions'] * 2}]:
            with self.assertRaises(ValueError):
                common.validate_item(item)

    def test_single_prepare_freezes_material_and_prompt(self):
        path = self.prepared()
        manifest, items, requests = difficulty.load_prepared(path)
        self.assertEqual(items, [FIXTURE])
        self.assertEqual(requests[0]['id'], FIXTURE['id'])
        item = deepcopy(FIXTURE)
        item['solutions'][0]['std']['code'] = 'other problem code'
        common.write_jsonl(path / 'inputs.jsonl', [item])
        with self.assertRaises(ValueError):
            difficulty.load_prepared(path)

    def test_prompt_mutation_rejected(self):
        path = self.prepared()
        target = path / 'requests' / (FIXTURE['id'] + '.json')
        req = common.read_json(target)
        req['messages'][0]['content'] = 'stale request from another problem'
        common.write_json(target, req)
        with self.assertRaises(ValueError):
            difficulty.load_prepared(path)

    def test_baseline_is_skill_free(self):
        base = self.prepared('baseline')
        skill = self.prepared('skill')
        _, _, a = difficulty.load_prepared(base)
        _, _, b = difficulty.load_prepared(skill)
        self.assertNotIn('<frozen_skill>', a[0]['messages'][0]['content'])
        self.assertIn('<frozen_skill>', b[0]['messages'][0]['content'])
        self.assertEqual(a[0]['generation'], b[0]['generation'])

    def test_split_blocks_family_identity_and_hash_overlap(self):
        for record in [{'identities': ['synthetic_identity']},
                       {'identities': [], 'family_ids': ['synthetic_family']},
                       {'identities': [], 'material_sha256': common.digest(FIXTURE)}]:
            registry = {**self.registry, 'records': [record]}
            with self.subTest(record=record), self.assertRaises(ValueError):
                benchmark.validate_split([FIXTURE], self.split, registry)

    def test_old_dataset_cannot_become_independent(self):
        self.split['dataset_id'] = 'old87'
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, self.registry)

    def test_renaming_id_does_not_hide_exposed_materials(self):
        registry = {**self.registry, 'records': [{'identities': [], 'content_sha256': common.content_digest(FIXTURE)}]}
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, registry)

    def test_unreviewed_family_placeholder_is_not_independent(self):
        self.split['items'][0]['family_id'] = 'unreviewed:synthetic'
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, self.registry)

    def test_material_binding_rejects_swapped_solutions(self):
        self.split['items'][0]['solution_problem_ids']['method_1'] = 'another'
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, self.registry)

    def test_independent_requires_human_family_material_review(self):
        self.split['items'][0]['review']['status'] = 'pending'
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, self.registry)
        self.split['purpose'] = 'development_diagnostic'
        benchmark.validate_split([FIXTURE], self.split, self.registry)

    def test_unknown_single_output_is_not_benchmark_result(self):
        adapter = self.root / 'unknown.py'
        adapter.write_text('import json,sys\nr=json.load(sys.stdin)\njson.dump({"id":r["id"],"level":0,"label":"未知","reason":"缺少确认"},sys.stdout)\n')
        for scope, expected in [('single', 'complete'), ('development_diagnostic', 'incomplete')]:
            prepared = self.prepared(scope=scope)
            result = difficulty.run(prepared, adapter, self.root / ('run_' + scope))
            self.assertEqual(result['status'], expected)

    def expert_data(self):
        data = self.root / 'expert'
        data.mkdir()
        common.write_jsonl(data / 'cases.jsonl', [])
        common.write_jsonl(data / 'experiences.jsonl', [])
        return data

    def test_unreviewed_case_cannot_be_distilled(self):
        data = self.expert_data()
        case = experts.template('case', 'case1')
        case.update(problem_id='synthetic', family_id='sum')
        common.write_jsonl(data / 'cases.jsonl', [case])
        with self.assertRaises(ValueError):
            experts.distill(data, ['case1'], self.root / 'request.json')

    def test_confirmed_case_needs_label_material_and_explanation(self):
        case = experts.template('case', 'case1')
        case.update(problem_id='synthetic', family_id='sum',
                    confirmation={'status': 'confirmed', 'reviewer': 'test', 'reviewed_on': '2026-11-14'})
        with self.assertRaises(ValueError):
            experts.validate_case(case, self.root)

    def test_candidate_cannot_enter_scoring(self):
        temp_skill = self.root / 'skill'
        shutil.copytree(SKILL, temp_skill)
        rule = {'id': 'rule1', 'experience': 'synthetic test', 'source_cases': ['case1'],
                'applicability': ['test only'], 'limitations': ['test only'], 'counterexamples': [],
                'counterexample_check': 'synthetic check', 'confirmation': {'status': 'candidate'}, 'introduced_in': None}
        common.write_json(temp_skill / 'references/expert-rules.json', {'skill_version': common.VERSION, 'rules': [rule]})
        with patch.object(difficulty, 'SKILL', temp_skill), self.assertRaises(ValueError):
            difficulty.skill_snapshot()

    def test_release_matches_reviewed_sources(self):
        result = experts.check_release(REPO / 'data/difficulty/expert')
        self.assertTrue(result['valid'])

    def test_confirmed_expert_source_and_manual_release(self):
        data = self.expert_data()
        common.write_json(data / 'material.json', FIXTURE)
        case = experts.template('case', 'case1')
        case.update(problem_id='synthetic', family_id='sum', level=1, label_source='synthetic test label',
                    material_path='material.json', material_sha256=common.digest(FIXTURE), material_problem_id='synthetic',
                    expert_explanation='Synthetic expert workflow fixture, not a real expert assertion.',
                    confirmation={'status': 'confirmed', 'reviewer': 'test reviewer', 'reviewed_on': '2026-11-14'})
        common.write_jsonl(data / 'cases.jsonl', [case])
        experts.distill(data, ['case1'], self.root / 'distill.json')
        self.assertEqual(common.read_json(self.root / 'distill.json')['purpose'], 'development_distillation_only')
        rule = {'id': 'rule1', 'experience': 'synthetic fixture', 'source_cases': ['case1'],
                'applicability': ['synthetic fixture'], 'limitations': ['synthetic fixture'], 'counterexamples': [],
                'counterexample_check': 'synthetic fixture check',
                'confirmation': {'status': 'confirmed', 'reviewer': 'test reviewer', 'reviewed_on': '2026-11-14'},
                'introduced_in': common.VERSION}
        common.write_jsonl(data / 'experiences.jsonl', [rule])
        release_skill = self.root / 'release'
        common.write_json(release_skill / 'references/expert-rules.json', {'skill_version': common.VERSION, 'rules': [rule]})
        with patch.object(experts, 'SKILL', release_skill):
            self.assertEqual(experts.check_release(data)['released'], 1)
            rule['experience'] = 'changed unsupported rule'
            common.write_json(release_skill / 'references/expert-rules.json', {'skill_version': common.VERSION, 'rules': [rule]})
            with self.assertRaises(ValueError):
                experts.check_release(data)

    def test_new_expert_cases_are_reserved_from_evaluation(self):
        data = self.expert_data()
        case = experts.template('case', 'case1')
        case.update(problem_id='synthetic_identity', family_id='synthetic_family')
        common.write_jsonl(data / 'cases.jsonl', [case])
        path = self.root / 'registry.json'
        common.write_json(path, {**self.registry, 'expert_data': 'expert'})
        registry = benchmark.load_registry(path)
        with self.assertRaises(ValueError):
            benchmark.validate_split([FIXTURE], self.split, registry)

    def test_legacy_skill_and_archived_results_unchanged(self):
        index = common.read_json(REPO / 'data/difficulty/history/index.json')
        for name, sha in index['legacy_skill_files'].items():
            self.assertEqual(common.file_sha(REPO / name), sha)
        for record in index['runs']:
            for name, sha in record['files'].items():
                self.assertEqual(common.file_sha(REPO / 'data/difficulty/history' / record['name'] / name), sha)

    def test_standalone_cli_with_spaces(self):
        installed = self.root / 'installed skill'
        shutil.copytree(SKILL, installed)
        item_path = self.root / 'item.json'
        common.write_json(item_path, FIXTURE)
        result = subprocess.run([sys.executable, str(installed / 'scripts/difficulty.py'), 'prepare',
                                 '--item', str(item_path), '--out', str(self.root / 'request'), '--model', 'test'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_codex_adapter_rejects_tool_use(self):
        request = {'model': 'test', 'generation': {'reasoning_effort': 'high'},
                   'response_schema': common.schema(), 'messages': [{'content': 'test'}]}
        event = json.dumps({'item': {'type': 'command_execution'}})
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, event, '')):
            with self.assertRaises(ValueError):
                codex_adapter.predict(request)

    def test_adapter_cannot_reuse_conversation(self):
        second = {**FIXTURE, 'id': 'synthetic_second'}
        prepared = self.root / 'two_items'
        difficulty.prepare([FIXTURE, second], prepared, 'baseline', 'test-model', scope='development_diagnostic')
        adapter = self.root / 'reused_context.py'
        adapter.write_text('import json,sys\nr=json.load(sys.stdin)\n'
                           'json.dump({"prediction":{"id":r["id"],"level":1,"label":"入门","reason":"test"},'
                           '"thread_id":"same-thread","demo":True},sys.stdout)\n', encoding='utf-8')
        result = difficulty.run(prepared, adapter, self.root / 'two_results')
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['failed_ids'], ['synthetic_second'])

    def test_parallel_transports_keep_problem_binding_and_order(self):
        second = {**FIXTURE, 'id': 'synthetic_second'}
        prepared = self.root / 'parallel_requests'
        difficulty.prepare([FIXTURE, second], prepared, 'baseline', 'test-model', scope='development_diagnostic')
        adapter = self.root / 'parallel_adapter.py'
        adapter.write_text('import json,sys\nr=json.load(sys.stdin)\n'
                           'json.dump({"prediction":{"id":r["id"],"level":1,"label":"入门","reason":"test"},'
                           '"thread_id":r["id"],"demo":True},sys.stdout)\n', encoding='utf-8')
        out = self.root / 'parallel_results'
        result = difficulty.run(prepared, adapter, out, workers=2)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual([r['id'] for r in common.read_jsonl(out / 'predictions.jsonl')], [FIXTURE['id'], second['id']])

    def test_frozen_runtime_cannot_change(self):
        installed = self.root / 'runtime'
        shutil.copytree(SKILL, installed)
        prepared = self.root / 'frozen_runtime'
        with patch.object(difficulty, 'SKILL', installed):
            difficulty.prepare([FIXTURE], prepared, 'baseline', 'test-model')
            with (installed / 'scripts/common.py').open('a', encoding='utf-8') as stream:
                stream.write('\n# new runtime revision\n')
            with self.assertRaises(ValueError):
                difficulty.load_prepared(prepared)


@unittest.skipUnless(BENCH, 'Set LUOGUBENCH_ROOT for existing LuoguBench integration')
class LuoguBenchIntegrationTests(unittest.TestCase):
    setUp = FrameworkTests.setUp
    def pair(self):
        inputs, split, registry = [self.root / p for p in ('inputs.jsonl', 'split.json', 'registry.json')]
        common.write_jsonl(inputs, [FIXTURE])
        common.write_json(split, self.split)
        common.write_json(registry, self.registry)
        out = self.root / 'pair'
        benchmark.prepare_pair(inputs, split, registry, out, 'synthetic-test-model', 'high', BENCH)
        return out

    def synthetic_run(self, pair, mode):
        # Construct synthetic scoring inputs in a temporary directory, never publish them as model results.
        prepared = pair / mode
        manifest, _, _ = difficulty.load_prepared(prepared)
        run = self.root / ('run_' + mode)
        run.mkdir()
        common.write_jsonl(run / 'predictions.jsonl', [prediction(level=2 if mode == 'baseline' else 1)])
        common.write_json(run / 'run.json', {'prepared_sha256': common.digest(manifest), 'status': 'complete',
                                          'predictions_sha256': common.file_sha(run / 'predictions.jsonl'),
                                          'adapter_sha256': 'synthetic-scoring-fixture', 'is_demo': False})
        return prepared, run

    def test_existing_contract_matches_new_output(self):
        core, _ = benchmark.luogubench(BENCH)
        core.validate_input_item(FIXTURE)
        from luogubench.bundle import validate_predictions
        validate_predictions([prediction()], [FIXTURE['id']])

    def test_pair_is_label_free_and_equal_context(self):
        pair = self.pair()
        a, _, ra = difficulty.load_prepared(pair / 'baseline')
        b, _, rb = difficulty.load_prepared(pair / 'skill')
        self.assertEqual(a['inputs_sha256'], b['inputs_sha256'])
        self.assertEqual(a['metadata'], b['metadata'])
        self.assertNotIn('synthetic_identity', ra[0]['messages'][0]['content'])
        self.assertNotIn('synthetic_family', rb[0]['messages'][0]['content'])

    def test_all_five_metrics_and_unknown_gold(self):
        pair = self.pair()
        labels = self.root / 'labels.jsonl'
        common.write_jsonl(labels, [{'id': FIXTURE['id'], 'problem_id': 'synthetic_identity', 'bucket': 'synthetic',
                                    'level': 1, 'label': '入门'}])
        paths = {}
        for mode in ('baseline', 'skill'):
            prepared, run = self.synthetic_run(pair, mode)
            out = self.root / ('score_' + mode)
            metrics = benchmark.score_run(prepared, run, labels, out, BENCH)
            paths[mode] = out / 'metrics.json'
            self.assertIn('accuracy', metrics)
            self.assertIn('within_one_level', metrics)
            self.assertIn('mae', metrics)
            self.assertIn('mean_signed_error', metrics)
            self.assertIsNone(metrics['spearman_rho'])  # constant ranks are undefined
        result = benchmark.compare(paths['baseline'], paths['skill'])
        self.assertEqual(result['metrics']['mae']['baseline'], 1)
        self.assertEqual(result['metrics']['mean_signed_error']['baseline'], 1)
        self.assertEqual(result['metrics']['accuracy']['skill'], 1)
        common.write_jsonl(labels, [{'id': FIXTURE['id'], 'problem_id': 'synthetic_identity', 'bucket': 'synthetic',
                                    'level': 0, 'label': '未知'}])
        with self.assertRaises(ValueError):
            benchmark.score_run(pair / 'skill', self.root / 'run_skill', labels, self.root / 'bad', BENCH)

    def test_score_rejects_demo_and_wrong_problem_labels(self):
        pair = self.pair()
        prepared, run = self.synthetic_run(pair, 'skill')
        labels = self.root / 'labels.jsonl'
        common.write_jsonl(labels, [{'id': FIXTURE['id'], 'problem_id': 'wrong', 'bucket': 'synthetic', 'level': 1, 'label': '入门'}])
        with self.assertRaises(ValueError):
            benchmark.score_run(prepared, run, labels, self.root / 'wrong', BENCH)
        config = common.read_json(run / 'run.json')
        config['is_demo'] = True
        common.write_json(run / 'run.json', config)
        with self.assertRaises(ValueError):
            benchmark.score_run(prepared, run, labels, self.root / 'demo', BENCH)


if __name__ == '__main__':
    unittest.main()
