#!/usr/bin/env python3
"""Offline conversion, optimizer and frozen-data checks; no model calls."""

from itertools import combinations
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / 'skills/cp-difficulty-rate'
sys.path.insert(0, str(SKILL / 'scripts'))
import platforms
import calibrate_platforms


class DifficultyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = platforms.load_mapping()

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SKILL/'scripts/platforms.py'), *args],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result

    def test_atcoder_raw_display_semantics(self):
        self.assertEqual(platforms.at_display(0), 147)
        self.assertEqual(platforms.at_display(-197), 90)
        self.assertEqual(platforms.at_display(400), 400)
        self.assertEqual(platforms.at_display(400.5), 401)
        self.assertEqual(platforms.at_display(-10000), 0)
        self.assertEqual(self.cli('--at-raw', '0')['normalized_value'], 147)
        self.assertEqual(self.cli('--at-display', '0')['normalized_value'], 0)

    def test_unknown_luogu_and_eight_levels(self):
        unknown = self.cli('--luogu-id', '0')
        self.assertIsNone(unknown['level'])
        self.assertEqual(unknown['status'], 'unrated')
        for native_id in range(1, 9):
            self.assertEqual(self.cli('--luogu-id', str(native_id))['level'], native_id - 1)
        self.assertEqual(self.cli('--level', '0')['luogu_name'], '入门')
        self.assertEqual(self.cli('--level', '7')['luogu_name'], 'NOI/NOI+/CTS')

    def test_boundaries_and_ranges(self):
        for name, model in self.mapping['platforms'].items():
            values = list(range(model['domain_min'], 4600))
            levels = [platforms.level_from_value(v, model['cuts']) for v in values]
            self.assertEqual(levels, sorted(levels))
            for k, cut in enumerate(model['cuts']):
                self.assertEqual(platforms.level_from_value(cut-1, model['cuts']), k)
                self.assertEqual(platforms.level_from_value(cut, model['cuts']), k+1)
            for level in range(8):
                r = platforms.describe_level(level, self.mapping)['ranges'][name]
                self.assertEqual(platforms.level_from_value(r['lower_inclusive'], model['cuts']), level)
        self.assertEqual(self.cli('--cf', '2200')['level'], 4)
        self.assertEqual(self.cli('--at-display', '1528')['level'], 3)
        self.assertTrue(self.cli('--cf', '4000')['outside_observed_range'])

    def test_invalid_inputs_do_not_become_scores(self):
        for value in (None, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                platforms.finite_number(value)
        for args in [('--cf', '0'), ('--cf', '800.5'), ('--at-display', '-1'),
                     ('--cf', 'nan'), ('--at-raw', 'inf'), ('--level', '8')]:
            self.cli(*args, success=False)

    def test_standalone_install_in_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='cpscore difficulty ') as temp:
            installed = Path(temp) / 'cp-difficulty-rate'
            shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns('__pycache__'))
            result = subprocess.run([sys.executable, str(installed/'scripts/platforms.py'), '--level', '7'],
                                    cwd=temp, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['luogu_name'], 'NOI/NOI+/CTS')

    def test_optimizer_against_exhaustive_search(self):
        rows = [(20, 0), (160, 1), (260, 2), (420, 4), (590, 5), (630, 6), (780, 7)]
        cuts = calibrate_platforms.fit(rows, 0)
        loss = sum(abs(platforms.level_from_value(x, cuts)-y) for x, y in rows)
        best = min(sum(abs(platforms.level_from_value(x, c)-y) for x, y in rows)
                   for c in combinations(range(100, 901, 100), 7))
        self.assertEqual(loss, best)

    def test_frozen_snapshot_reproduces_model(self):
        actual = calibrate_platforms.build(SKILL/'references/platform-anchors.json')
        self.assertEqual(actual, self.mapping)
        for name, model in actual['platforms'].items():
            rows = model['evaluation_rows']
            development = {r['problem_id'] for r in rows if r['split']=='development'}
            holdout = {r['problem_id'] for r in rows if r['split']=='holdout'}
            self.assertFalse(development & holdout)
            self.assertEqual(len(holdout), 40)
            self.assertEqual(model['frozen_holdout']['n'], 40)
            self.assertEqual(len(model['support_by_level']), 8)
            self.assertTrue(all(n >= 10 for n in model['support_by_level']))


if __name__ == '__main__':
    unittest.main()
