#!/usr/bin/env python3
"""Explicit expert feedback entry and release validation. Never edits scoring rules."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

from common import (SKILL, VERSION, digest, identifier, level, read_json, read_jsonl,
                    text, validate_item, write_json, write_jsonl)


def review(value, states):
    if not isinstance(value, dict) or value.get('status') not in states:
        raise ValueError('Invalid human review status')
    if value['status'] == 'confirmed':
        text(value.get('reviewer'), 'reviewer')
        date.fromisoformat(value.get('reviewed_on', ''))


def strings(values, field, nonempty=True):
    if not isinstance(values, list) or (nonempty and not values):
        raise ValueError(field + ' must be a list' + (' with at least one entry' if nonempty else ''))
    for value in values:
        text(value, field)


def validate_case(case, base):
    identifier(case['case_id'])
    text(case['problem_id'], 'problem_id')
    text(case['family_id'], 'family_id')
    level(case['level'], allow_unknown=True)
    review(case['confirmation'], {'pending', 'confirmed', 'legacy_axis_only'})
    if case['confirmation']['status'] == 'confirmed':
        level(case['level'])
        text(case.get('label_source'), 'label_source')
        text(case.get('expert_explanation'), 'expert_explanation')
        item = read_json(Path(base) / case['material_path'])
        validate_item(item)
        if digest(item) != case.get('material_sha256'):
            raise ValueError('Expert case material hash mismatch')
        # Curator binds the blinded materials to the actual problem at review time.
        if case.get('material_problem_id') != case['problem_id']:
            raise ValueError('Expert case material belongs to another problem')


def validate_rule(rule):
    identifier(rule['id'])
    text(rule['experience'], 'experience')
    for field in ('source_cases', 'applicability', 'limitations'):
        strings(rule[field], field)
    strings(rule['counterexamples'], 'counterexamples', nonempty=False)
    text(rule['counterexample_check'], 'counterexample_check')
    review(rule['confirmation'], {'candidate', 'confirmed', 'rejected'})
    if rule['confirmation']['status'] == 'confirmed':
        text(rule['introduced_in'], 'introduced_in')


def load_data(path):
    path = Path(path)
    cases = read_jsonl(path / 'cases.jsonl')
    rules = read_jsonl(path / 'experiences.jsonl')
    if len({c['case_id'] for c in cases}) != len(cases) or len({r['id'] for r in rules}) != len(rules):
        raise ValueError('Duplicate expert case/rule ID')
    for case in cases:
        validate_case(case, path)
    by_id = {c['case_id']: c for c in cases}
    for rule in rules:
        validate_rule(rule)
        if any(i not in by_id for i in rule['source_cases']):
            raise ValueError('Missing source case')
        if rule['confirmation']['status'] == 'confirmed':
            if any(by_id[i]['confirmation']['status'] != 'confirmed' for i in rule['source_cases']):
                raise ValueError('Confirmed rule requires complete human-reviewed sources')
    return cases, rules


def check_release(data):
    cases, rules = load_data(data)
    release = read_json(SKILL / 'references/expert-rules.json')
    if release['skill_version'] != VERSION:
        raise ValueError('Release version mismatch')
    by_id = {r['id']: r for r in rules}
    seen = set()
    for rule in release['rules']:
        validate_rule(rule)
        if rule['confirmation']['status'] != 'confirmed' or rule != by_id.get(rule['id']) or rule['id'] in seen:
            raise ValueError('Release rule must exactly match a unique human-confirmed source record')
        seen.add(rule['id'])
    return {'valid': True, 'cases': len(cases), 'experiences': len(rules), 'released': len(seen)}


def template(kind, record_id):
    identifier(record_id)
    confirmation = {'status': 'pending' if kind == 'case' else 'candidate', 'reviewer': None, 'reviewed_on': None}
    if kind == 'case':
        return {'case_id': record_id, 'problem_id': '', 'family_id': '', 'level': 0,
                'label_source': '', 'material_path': '', 'material_sha256': '', 'material_problem_id': '',
                'expert_explanation': '', 'comparisons': [], 'prediction': None, 'confirmation': confirmation}
    return {'id': record_id, 'experience': '', 'source_cases': [], 'applicability': [],
            'limitations': [], 'counterexamples': [], 'counterexample_check': '',
            'confirmation': confirmation, 'introduced_in': None}


def add(data, kind, source):
    data = Path(data)
    cases, rules = load_data(data)
    row = read_json(source)
    if kind == 'case':
        validate_case(row, data)
        rows, key, filename = cases, 'case_id', 'cases.jsonl'
    else:
        validate_rule(row)
        if row['confirmation']['status'] != 'candidate':
            raise ValueError('New rules must enter as candidates; human review is a separate edit')
        if any(i not in {c['case_id'] for c in cases} for i in row['source_cases']):
            raise ValueError('Missing source case')
        rows, key, filename = rules, 'id', 'experiences.jsonl'
    if row[key] in {r[key] for r in rows}:
        raise ValueError('Duplicate ID')
    write_jsonl(data / filename, rows + [row])
    return {'added': row[key]}


def distill(data, ids, out):
    cases, _ = load_data(data)
    by_id = {c['case_id']: c for c in cases}
    selected = []
    for case_id in ids:
        case = by_id[case_id]
        if case['confirmation']['status'] != 'confirmed':
            raise ValueError('Distillation requires human-reviewed complete cases')
        selected.append({'case': case, 'material': read_json(Path(data) / case['material_path'])})
    instruction = ('这是开发蒸馏任务，含真实标签，禁止作为独立评测输入。根据专家解释归纳少量候选经验，'
                   '用给定模板输出，保持 candidate。说明适用条件、局限、反例和反例检查。'
                   '若来源不足以支持通用经验则不输出规则。不能记忆某题等级为通用算法定档规则。')
    write_json(out, {'purpose': 'development_distillation_only', 'instruction': instruction,
                     'rule_template': template('rule', 'candidate_id'), 'sources': selected})
    return {'request': str(out), 'cases': len(selected), 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for kind in ('case', 'rule'):
        p = sub.add_parser('new-' + kind)
        p.add_argument('--id', required=True)
        p.add_argument('--out', type=Path, required=True)
        p = sub.add_parser('add-' + kind)
        p.add_argument('--data', type=Path, required=True)
        p.add_argument('--file', type=Path, required=True)
    for cmd in ('check', 'check-release'):
        p = sub.add_parser(cmd)
        p.add_argument('--data', type=Path, required=True)
    p = sub.add_parser('distill')
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--case-ids', nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command.startswith('new-'):
            if args.out.exists():
                raise ValueError('Template destination already exists')
            write_json(args.out, template(args.command[4:], args.id))
            result = {'template': str(args.out)}
        elif args.command.startswith('add-'):
            result = add(args.data, args.command[4:], args.file)
        elif args.command == 'distill':
            result = distill(args.data, args.case_ids, args.out)
        elif args.command == 'check-release':
            result = check_release(args.data)
        else:
            cases, rules = load_data(args.data)
            result = {'valid': True, 'cases': len(cases), 'experiences': len(rules)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, 'error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
