#!/usr/bin/env python3
"""Reproduce native-label mappings from the bundled snapshot; no network or API key."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from platforms import at_display, finite_number, level_from_value

ROOT = Path(__file__).resolve().parents[1]


def fit(rows, domain_min):
    # Ordinal absolute error is the sum of seven binary boundary errors.
    # A 100-point grid avoids implying precision unsupported by this small pilot.
    end = (max(x for x, _ in rows) // 100 + 2) * 100
    grid = list(range(domain_min + 100, max(domain_min + 800, end) + 1, 100))
    costs, centers = [], []
    for boundary in range(7):
        loss = [sum((x >= cut) != (y > boundary) for x, y in rows) for cut in grid]
        best = min(loss)
        optimal = [cut for cut, cost in zip(grid, loss) if cost == best]
        costs.append(loss)
        centers.append((optimal[0] + optimal[-1]) / 2)
    states = []
    for boundary in range(7):
        new = []
        for j, cut in enumerate(grid):
            extra = (costs[boundary][j], abs(cut - centers[boundary]))
            if boundary == 0:
                new.append((extra[0], extra[1], (cut,)))
            else:
                previous = [s for s in states[:j] if s is not None]
                if not previous:
                    new.append(None)
                else:
                    best = min(previous)
                    new.append((best[0] + extra[0], best[1] + extra[1], best[2] + (cut,)))
        states = new
    return list(min(s for s in states if s is not None)[2])


def metrics(truth, predictions):
    errors = [abs(a - b) for a, b in zip(truth, predictions)]
    return {
        'n': len(errors),
        'mean_absolute_level_error': sum(errors) / len(errors),
        'exact_count': sum(e == 0 for e in errors),
        'within_one_count': sum(e <= 1 for e in errors),
        'max_absolute_level_error': max(errors),
    }


def build(snapshot_path):
    raw = snapshot_path.read_bytes()
    snapshot = json.loads(raw)
    seen = set()
    rows_by_platform = {name: {'development': [], 'holdout': []}
                        for name in ('codeforces', 'atcoder-problems')}
    for record in snapshot['records']:
        key = (record['provider'], record['problem_id'])
        if key in seen:
            raise ValueError('duplicate task identity: ' + str(key))
        seen.add(key)
        if not record['eligible']:
            continue
        native = finite_number(record['native_value'])
        luogu_id = record['luogu_id']
        if type(luogu_id) is not int or not 1 <= luogu_id <= 8:
            raise ValueError('eligible record must have a rated Luogu label')
        value = native if record['provider'] == 'codeforces' else at_display(native)
        split = record['split']
        if split not in ('development', 'holdout'):
            raise ValueError('eligible record must have a frozen split')
        rows_by_platform[record['provider']][split].append((value, luogu_id - 1, record['problem_id']))
    result = {
        'version': 'cpscore-platforms-20261113-v1',
        'status': 'provisional_paired_native_labels',
        'snapshot_sha256': hashlib.sha256(raw).hexdigest(),
        'method': 'Seven strictly increasing cuts on a 100-point grid minimize absolute ordinal error. Ties prefer boundary-wise optimal centers, then lexicographic cuts. Each platform is fitted separately.',
        'evaluation': 'Frozen task-identity holdout, five tasks per Luogu level and platform. Stratified metadata sample, not a population accuracy estimate or a new-trick test. Does not evaluate K/T/I or content-to-level accuracy.',
        'platforms': {},
    }
    for name, splits in rows_by_platform.items():
        rows = [row[:2] for row in splits['development']]
        held = [row[:2] for row in splits['holdout']]
        domain_min = 800 if name == 'codeforces' else 0
        if len(rows) < 8 or set(y for _, y in rows) != set(range(8)):
            raise ValueError('calibration snapshot must support all eight levels: ' + name)
        cuts = fit(rows, domain_min)
        truth = [y for _, y in rows]
        predictions = [level_from_value(x, cuts) for x, _ in rows]
        held_truth = [y for _, y in held]
        held_predictions = [level_from_value(x, cuts) for x, _ in held]
        if len(held) != 40 or Counter(held_truth) != Counter({k: 5 for k in range(8)}):
            raise ValueError('holdout must contain five tasks per level: ' + name)
        counts = Counter(truth)
        result['platforms'][name] = {
            'scale': 'problem.rating' if name == 'codeforces' else 'problem-model.difficulty.display',
            'domain_min': domain_min,
            'cuts': cuts,
            'observed_value_range': [min(x for x, _ in rows), max(x for x, _ in rows)],
            'support_by_level': [counts[k] for k in range(8)],
            'development_fit': metrics(truth, predictions),
            'frozen_holdout': metrics(held_truth, held_predictions),
            'evaluation_rows': [
                {'problem_id': pid, 'value': x, 'level': y, 'prediction': p, 'split': 'development'}
                for (x, y, pid), p in zip(splits['development'], predictions)
            ] + [
                {'problem_id': pid, 'value': x, 'level': y, 'prediction': p, 'split': 'holdout'}
                for (x, y, pid), p in zip(splits['holdout'], held_predictions)
            ],
        }
    return result


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional destination; otherwise print JSON')
    args = parser.parse_args()
    result = build(ROOT / 'references/platform-anchors.json')
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
