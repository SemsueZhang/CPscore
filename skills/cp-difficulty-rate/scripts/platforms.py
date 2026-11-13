#!/usr/bin/env python3
"""Offline native-difficulty conversion. Does not infer K/T/I or solve a task."""

import argparse
from bisect import bisect_right
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LABELS = (
    '入门', '普及-', '普及', '普及+/提高-',
    '提高', '提高+/省选-', '省选/NOI-', 'NOI/NOI+/CTS',
)


def finite_number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('difficulty must be a finite number')
    return value


def at_display(raw):
    """AtCoder Problems clipDifficulty, including JavaScript Math.round semantics."""
    raw = finite_number(raw)
    value = raw if raw >= 400 else 400 * math.exp(raw / 400 - 1)
    return math.floor(value + 0.5)


def load_mapping():
    doc = json.loads((ROOT / 'references/platform-calibration.json').read_text(encoding='utf-8'))
    for name in ('codeforces', 'atcoder-problems'):
        cuts = doc['platforms'][name]['cuts']
        if len(cuts) != 7 or any(type(x) is not int for x in cuts):
            raise ValueError('mapping must contain seven integer cuts')
        if any(a >= b for a, b in zip(cuts, cuts[1:])):
            raise ValueError('mapping cuts must be strictly increasing')
    return doc


def level_from_value(value, cuts):
    return bisect_right(cuts, value)


def describe_level(level, mapping):
    if type(level) is not int or not 0 <= level <= 7:
        raise ValueError('CPScore total level must be an integer from 0 to 7')
    ranges = {}
    for name, model in mapping['platforms'].items():
        cuts = model['cuts']
        ranges[name] = {
            'scale': model['scale'],
            'lower_inclusive': model['domain_min'] if level == 0 else cuts[level - 1],
            'upper_exclusive': None if level == 7 else cuts[level],
            'paired_sample_count': model['support_by_level'][level],
        }
    return {
        'level': level,
        'luogu_name': LABELS[level],
        'mapping_version': mapping['version'],
        'mapping_status': mapping['status'],
        'ranges': ranges,
        'range_meaning': 'coarse conversion bins, not confidence or prediction intervals',
    }


def convert(platform, value, mapping, scale=None):
    value = finite_number(value)
    original = value
    if platform == 'codeforces':
        if value < 800 or value != int(value):
            raise ValueError('Codeforces problem rating must be an integer >= 800; unrated is unknown')
    elif platform == 'atcoder-problems':
        if scale == 'raw':
            value = at_display(value)
        elif scale == 'display':
            if value < 0 or value != int(value):
                raise ValueError('AtCoder Problems display difficulty must be a nonnegative integer')
        else:
            raise ValueError('AtCoder input requires raw or display scale')
    else:
        raise ValueError('unknown platform')
    model = mapping['platforms'][platform]
    level = level_from_value(value, model['cuts'])
    result = describe_level(level, mapping)
    lo, hi = model['observed_value_range']
    result['input'] = {'platform': platform, 'value': original, 'scale': scale or model['scale']}
    result['normalized_value'] = value
    result['outside_observed_range'] = value < lo or value > hi
    result['purpose'] = 'native-label conversion only; content-based assessment may differ'
    return result


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--level', type=int, choices=range(8))
    group.add_argument('--cf', type=float, help='Codeforces problem rating (not contestant rating)')
    group.add_argument('--at-raw', type=float, help='AtCoder Problems raw model difficulty')
    group.add_argument('--at-display', type=float, help='Already clipped and rounded difficulty')
    group.add_argument('--luogu-id', type=int, choices=range(9), help='2026-11-13 native ID, 0 means unrated')
    args = parser.parse_args()
    try:
        mapping = load_mapping()
        if args.level is not None:
            result = describe_level(args.level, mapping)
        elif args.luogu_id is not None:
            result = ({'level': None, 'luogu_name': '暂无评定', 'status': 'unrated'}
                      if args.luogu_id == 0 else describe_level(args.luogu_id - 1, mapping))
        elif args.cf is not None:
            result = convert('codeforces', args.cf, mapping)
        elif args.at_raw is not None:
            result = convert('atcoder-problems', args.at_raw, mapping, 'raw')
        else:
            result = convert('atcoder-problems', args.at_display, mapping, 'display')
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
