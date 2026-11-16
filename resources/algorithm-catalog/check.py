#!/usr/bin/env python3
"""Offline regression checks for the single catalog and its Luogu annotations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


m = module('catalog', HERE / 'catalog.py')
C = m.read_catalog(HERE / 'catalog.json')
ENTRIES = {e['id']: e for e in C['entries']}
P = module('performance', ROOT / 'skills/cp-performance-predict/scripts/predict.py')


def links(aid):
    return {t['id']: t['relation'] for t in ENTRIES['oiwiki.' + aid]['luogu_tags']}


class CatalogChecks(unittest.TestCase):
    def test_all_original_identity_and_provenance_fields(self):
        core = {'source': C['source'], 'entries': [{k: v for k, v in e.items() if
                k in ('id', 'name', 'aliases', 'category', 'source_url', 'section')} for e in C['entries']]}
        digest = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '6e25479fa366e4e7b27206c39f226b3b9ff833d31e388fb8176c61513cc43eca')
        self.assertEqual(len(core['entries']), 635)

    def test_public_snapshot_and_complete_entry_shapes(self):
        report = m.validate(C)
        self.assertEqual(report['luogu_algorithm_tags'], 262)
        self.assertEqual(report['mapped_entries'] + report['unmapped_entries'], 635)
        self.assertEqual(report['problem_samples'], 34)
        self.assertEqual(report['knowledge_references'], 42)
        self.assertEqual(report['provisional_knowledge_references'], 43)
        self.assertFalse(report['representative_sample'])
        for e in C['entries']:
            self.assertTrue({'luogu_tags', 'knowledge_level', 'problem_difficulty'} <= set(e))

    def test_eight_bands_and_unrated_are_not_off_by_one(self):
        expected = ['入门', '普及-', '普及', '普及+/提高-', '提高', '提高+/省选-', '省选/NOI-', 'NOI/NOI+/CTS']
        self.assertEqual([s['label'] for s in C['luogu']['difficulty_scale']], expected)
        self.assertEqual([m.difficulty_index(i) for i in range(9)], [None] + list(range(8)))
        for invalid in (True, -1, 9, 2.5, '4'):
            with self.assertRaises(ValueError):
                m.difficulty_index(invalid)

    def test_exact_and_broader_correspondences(self):
        self.assertEqual(links('ds.seg')[42], 'equivalent')
        self.assertEqual(links('ds.seg.lazy')[42], 'broader')
        self.assertEqual(links('string.z-func')[474], 'equivalent')
        self.assertEqual(links('ds.lct')[229], 'equivalent')
        self.assertTrue({179, 180} <= set(links('graph.scc.tarjan')))
        self.assertTrue({291, 525} <= set(links('geometry.convex-hull.minkowski')))

    def test_ambiguous_names_and_page_neighbors_do_not_become_equivalent(self):
        self.assertNotIn(180, links('graph.lca.tarjan'))
        self.assertNotIn(180, links('graph.dominator-tree.lengauer-tarjan'))
        self.assertNotIn(391, links('string.bm'))
        self.assertNotIn(391, links('misc.main-element.majority-vote'))
        self.assertNotIn(241, links('math.number-theory.gcd.lcm'))
        self.assertNotIn(64, links('graph.matrix-tree.best'))
        self.assertEqual(links('math.poly.fft.dft')[313], 'context')
        self.assertEqual(links('math.number-theory.primitive-root.order')[66], 'context')
        self.assertNotIn(45, links('basic.binary.ternary'))
        self.assertEqual(links('math.probability.exp-var.variance')[270], 'context')
        self.assertEqual(links('basic.quick-sort.bfprt')[113], 'context')

    def test_missing_correspondence_is_retained(self):
        e = ENTRIES['oiwiki.misc.kahan-summation']
        self.assertEqual(e['luogu_tags'], [])
        self.assertIsNone(e['knowledge_level']['range'])
        self.assertEqual(e['problem_difficulty']['sample_size'], 0)
        self.assertIsNone(e['problem_difficulty']['distribution'])

    def test_reverse_lookup_uses_official_id_or_exact_name(self):
        self.assertEqual(m.find_tags(C['luogu'], '42'), m.find_tags(C['luogu'], '线段树'))
        self.assertEqual(m.find_tags(C['luogu'], '基础算法')[0]['id'], 110)
        with self.assertRaises(ValueError):
            m.find_tags(C['luogu'], '好像线段树')
        self.assertEqual(m.find_tags(C['luogu'], '523')[0]['type'], 3)
        self.assertFalse(any(523 in {x['id'] for x in e['luogu_tags']} for e in C['entries']))

    def test_reference_is_not_tag_sample_distribution(self):
        sieve = ENTRIES['oiwiki.math.number-theory.sieve.linear']
        self.assertEqual(sieve['knowledge_level']['range'], [1, 2])
        prime = ENTRIES['oiwiki.math.number-theory.prime.trial-division']
        self.assertIn('P5438', prime['problem_difficulty']['sample_ids'])
        self.assertEqual(prime['problem_difficulty']['distribution'][7], 1)
        self.assertEqual(prime['knowledge_level']['range'], [1, 2])
        self.assertFalse(prime['problem_difficulty']['representative'])

    def test_multi_tag_sample_union_is_deduplicated(self):
        entry = copy.deepcopy(ENTRIES['oiwiki.ds.seg'])
        entry['luogu_tags'].append({'id': 53, 'relation': 'broader', 'note': 'test union only'})
        stats = m.problem_distribution(entry, C['luogu'])
        self.assertEqual(stats['sample_ids'].count('P3384'), 1)
        self.assertEqual(sum(stats['distribution']), stats['sample_size'])

    def test_unrated_sample_does_not_enter_beginner_bin(self):
        metadata = copy.deepcopy(C['luogu'])
        sample = metadata['problem_samples'][0]
        sample.update(luogu_difficulty_id=0, difficulty_index=None, tags=[42])
        metadata['problem_samples'] = [sample]
        stats = m.problem_distribution(ENTRIES['oiwiki.ds.seg'], metadata)
        self.assertEqual(stats['sample_size'], 1)
        self.assertEqual(stats['unrated_count'], 1)
        self.assertIsNone(stats['distribution'])

    def test_no_target_label_leakage(self):
        e = ENTRIES['oiwiki.ds.seg']
        view = m.entry_view(e, C, ['P3372'])
        self.assertNotIn('P3372', view['problem_difficulty']['sample_ids'])
        self.assertEqual(view['knowledge_level']['confidence'], 'unknown')
        self.assertIsNone(view['knowledge_level']['range'])
        identity = m.entry_view(e, C, identity_only=True)
        self.assertFalse({'luogu_tags', 'knowledge_level', 'problem_difficulty'} & set(identity))
        self.assertNotIn('problem_difficulty', m.entry_view(e, C, knowledge_only=True))

    def test_oiwiki_rebuild_preserves_annotations_and_new_ids_stay_unknown(self):
        new = {'schema_version': 1, 'source': copy.deepcopy(C['source']),
               'entries': [m.entry_view(e, C, identity_only=True) for e in C['entries']]}
        extra = copy.deepcopy(new['entries'][0])
        extra.update(id='oiwiki.example.new', name='新增知识演示')
        new['entries'].append(extra)
        result = m.preserve_luogu(C, new)
        for old, rebuilt in zip(C['entries'], result['entries']):
            for key in ('luogu_tags', 'knowledge_level', 'problem_difficulty'):
                self.assertEqual(old[key], rebuilt[key])
        self.assertEqual(result['entries'][-1]['luogu_tags'], [])
        self.assertEqual(result['entries'][-1]['knowledge_level']['confidence'], 'unknown')
        m.validate(result)

    def test_invalid_mappings_statistics_and_intervals_are_rejected(self):
        for kind in ('non-algorithm', 'nonexistent', 'duplicate', 'fixed-grade', 'stale-statistics', 'category-equivalence'):
            data = copy.deepcopy(C)
            entry = data['entries'][0]
            if kind == 'non-algorithm':
                entry['luogu_tags'] = [{'id': 523, 'relation': 'equivalent', 'note': 'bad'}]
            elif kind == 'nonexistent':
                entry['luogu_tags'] = [{'id': 999999, 'relation': 'equivalent', 'note': 'bad'}]
            elif kind == 'duplicate':
                entry['luogu_tags'] *= 2
            elif kind == 'fixed-grade':
                entry['knowledge_level'] = {'range': [4, 4], 'confidence': 'reference',
                    'evidence': ['https://www.luogu.com.cn/problem/P3372'], 'note': 'bad'}
            elif kind == 'stale-statistics':
                entry['problem_difficulty']['sample_size'] += 1
            else:
                entry['luogu_tags'] = [{'id': 6, 'relation': 'equivalent', 'note': 'bad'}]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                m.validate(data)

    def test_profiles_read_references_without_changing_abilities(self):
        path = P.SKILL / 'references/reference-profiles.json'
        before = path.read_bytes()
        catalog = P.load_catalog(HERE)
        profiles = P.load_profiles(P.load_json(path), catalog)
        snapshot = copy.deepcopy(profiles)
        output = P.knowledge_references(profiles, catalog)
        self.assertEqual(len(output['algorithms']), 41)
        self.assertEqual(set(p['id'] for p in profiles),
                         {pid for e in output['algorithms'] for pid in e['profile_ids']})
        self.assertEqual(profiles, snapshot)
        self.assertEqual(path.read_bytes(), before)

    def test_no_per_skill_catalog_copies(self):
        self.assertEqual(list((ROOT / 'skills').rglob('catalog.json')), [])

    def test_cli_both_directions_and_profile_consumer(self):
        def run(script, *args):
            process = subprocess.run([sys.executable, str(script), *args], cwd=str(ROOT),
                                     text=True, capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)
        tag = run(HERE / 'catalog.py', 'tag', '42')
        self.assertIn('oiwiki.ds.seg', {e['id'] for e in tag['entries']})
        self.assertEqual(run(HERE / 'catalog.py', 'get', 'oiwiki.ds.seg')['luogu_tags'][0]['id'], 42)
        query = run(HERE / 'catalog.py', 'search', '--luogu-tag', '42', '--identity-only')
        self.assertGreater(query['total'], 1)
        self.assertNotIn('knowledge_level', query['entries'][0])
        profile = run(P.SKILL / 'scripts/predict.py', '--catalog', str(HERE), 'knowledge')
        self.assertEqual(len(profile['algorithms']), 41)

    def test_refresh_stops_on_taxonomy_changes_and_downgrades_changed_evidence(self):
        tags = {'tags': [{k: v for k, v in t.items() if k != 'kind'} for t in C['luogu']['tags']],
                'types': C['luogu']['tag_types'], '_version': 'offline-test'}
        config = {'ProblemDifficulty': [{'id': 0, 'name': '暂无评定'}] +
                  [{'id': r['luogu_id'], 'name': r['luogu_name']} for r in C['luogu']['difficulty_scale']],
                  '_version': 'offline-test'}
        sample = next(s for s in C['luogu']['problem_samples'] if s['pid'] == 'P3372')
        problem = {'pid': 'P3372', 'name': sample['name'], 'tags': sample['tags'], 'difficulty': 5}

        class Response:
            status = 200
            def __init__(self, raw): self.raw = raw
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return self.raw[:limit]

        def fetch(request, timeout):
            if request.full_url.endswith('/tags'): data = json.dumps(tags)
            elif request.full_url.endswith('/config'): data = json.dumps(config)
            else: data = '<script id="lentille-context">' + json.dumps({'data': {'problem': problem}}) + '</script>'
            return Response(data.encode())

        original = copy.deepcopy(C)
        with patch.object(m, 'urlopen', fetch), patch.object(m.time, 'sleep') as delay:
            updated = m.refresh_luogu(C, ['P3372'])
            self.assertEqual(delay.call_args_list, [unittest.mock.call(2)] * 3)
            entry = next(e for e in updated['entries'] if e['id'] == 'oiwiki.ds.seg')
            self.assertEqual(entry['knowledge_level']['confidence'], 'provisional')
            self.assertEqual(entry['knowledge_level']['range'], ENTRIES['oiwiki.ds.seg']['knowledge_level']['range'])
            tags['tags'].append({'id': 999999, 'name': 'new', 'type': 2, 'parent': None})
            with self.assertRaisesRegex(ValueError, 'taxonomy changed'):
                m.refresh_luogu(C, [])
        self.assertEqual(C, original)
        with self.assertRaises(ValueError):
            m.refresh_luogu(C, ['P1'] * 41)


if __name__ == '__main__':
    unittest.main(verbosity=2)
