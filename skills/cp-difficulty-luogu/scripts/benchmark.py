#!/usr/bin/env python3
"""Family-aware paired requests; reuse existing LuoguBench validators and metrics."""

import argparse
from datetime import date
import importlib
import json
from pathlib import Path
import sys

from common import (PROTOCOL, content_digest, digest, empty_directory, file_sha, read_json, read_jsonl,
                    text, validate_item, validate_prediction, write_json)
from difficulty import load_prepared, prepare


def luogubench(root):
    # Read-only integration: do not modify the owning repository, even via pycache.
    root = Path(root).resolve()
    if not (root / 'luogubench/core.py').is_file():
        raise ValueError('Missing LuoguBench package at --luogubench-root')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    core, scoring = importlib.import_module('luogubench.core'), importlib.import_module('luogubench.score')
    if Path(core.__file__).resolve().parent.parent != root:
        raise ValueError('A different LuoguBench checkout is already imported')
    return core, scoring


def benchmark_code(root):
    return {name: file_sha(Path(root) / 'luogubench' / name)
            for name in ('core.py', 'metrics.py', 'score.py')}


def make_manifest(items, dataset_id, purpose, registry):
    identities = {r['item_id']: r for r in registry['records'] if r.get('item_id')}
    rows = []
    for item in items:
        validate_item(item)
        known = identities.get(item['id'], {})
        problem = known.get('problem_id', '')
        rows.append({'id': item['id'], 'problem_id': problem, 'aliases': [], 'family_id': '',
                     'material_sha256': digest(item),
                     'solution_problem_ids': {s['method_id']: problem for s in item['solutions']},
                     'review': {'status': 'pending', 'reviewer': None, 'reviewed_on': None, 'notes': ''}})
    return {'format_version': 1, 'dataset_id': dataset_id, 'purpose': purpose, 'items': rows}


def load_registry(path):
    registry = read_json(path)
    if registry.get('expert_data'):
        from experts import load_data
        cases, _ = load_data(Path(path).parent / registry['expert_data'])
        for case in cases:
            row = {'identities': [case['problem_id']], 'family_ids': [case['family_id']],
                   'material_sha256': case.get('material_sha256'), 'source': 'expert_case:' + case['case_id']}
            if case['confirmation']['status'] == 'confirmed':
                material = read_json(Path(path).parent / registry['expert_data'] / case['material_path'])
                row['content_sha256'] = content_digest(material)
            registry['records'].append(row)
    return registry


def validate_split(items, split, registry):
    if split.get('format_version') != 1 or split.get('purpose') not in ('independent', 'development_diagnostic'):
        raise ValueError('Invalid split manifest')
    text(split.get('dataset_id'), 'dataset_id')
    independent = split['purpose'] == 'independent'
    refs = split['items']
    if len({r['id'] for r in refs}) != len(refs) or {r['id'] for r in refs} != {i['id'] for i in items}:
        raise ValueError('Split IDs do not match inputs')
    by_id = {r['id']: r for r in refs}
    known_ids, known_families, known_hashes, known_contents = set(), set(), set(), set()
    for r in registry['records']:
        known_ids.update(r['identities'])
        known_families.update(r.get('family_ids', []))
        if r.get('material_sha256'):
            known_hashes.add(r['material_sha256'])
        if r.get('content_sha256'):
            known_contents.add(r['content_sha256'])
    if independent and split['dataset_id'] in registry['development_dataset_ids']:
        raise ValueError('Historical development dataset cannot become independent by relabeling')
    identities, families = {}, {}
    for item in items:
        validate_item(item)
        ref = by_id[item['id']]
        text(ref['problem_id'], 'problem_id')
        text(ref['family_id'], 'family_id')
        if not isinstance(ref['aliases'], list):
            raise ValueError('aliases must be a list')
        for alias in ref['aliases']:
            text(alias, 'alias')
        if digest(item) != ref['material_sha256']:
            raise ValueError('Material hash mismatch, possibly mixed statement/solution/std: ' + item['id'])
        methods = {s['method_id']: ref['problem_id'] for s in item['solutions']}
        if ref['solution_problem_ids'] != methods:
            raise ValueError('Solutions are bound to a different problem')
        ids = {item['id'], ref['problem_id'], *ref['aliases']}
        if independent:
            if (ids & known_ids or ref['family_id'] in known_families or digest(item) in known_hashes
                    or content_digest(item) in known_contents):
                raise ValueError('Independent/development overlap: ' + item['id'])
            if ref['family_id'].startswith('unreviewed:'):
                raise ValueError('Unreviewed family placeholder cannot certify independent data')
            review = ref['review']
            if review.get('status') != 'confirmed':
                raise ValueError('Independent data requires human material and family review')
            text(review.get('reviewer'), 'reviewer')
            date.fromisoformat(review.get('reviewed_on', ''))
            text(review.get('notes'), 'family/material review notes')
        for identity in ids:
            if identity in identities:
                raise ValueError('Duplicate problem/alias identity across items')
            identities[identity] = item['id']
        families.setdefault(ref['family_id'], []).append(item['id'])
    return {'purpose': split['purpose'], 'family_count': len(families),
            'family_sizes': {k: len(v) for k, v in families.items()},
            'note': 'Hashes bind supplied text; human review covers semantics and near variants. Public pretraining exposure cannot be ruled out.'}


def prepare_pair(inputs, split_path, registry_path, out, model, reasoning, root):
    core, _ = luogubench(root)
    items = read_jsonl(inputs)
    for item in items:
        core.validate_input_item(item)
    split, registry = read_json(split_path), load_registry(registry_path)
    audit = validate_split(items, split, registry)
    out = empty_directory(out)
    metadata = {'dataset_id': split['dataset_id'], 'split_sha256': digest(split),
                'registry_sha256': digest(registry), 'split_audit': audit,
                'luogubench_code_sha256': benchmark_code(root),
                'comparison': 'same model, generation, materials and isolated context; only frozen Skill differs'}
    # Identity and split records remain outside the model request.
    write_json(out / 'split.json', split)
    write_json(out / 'registry.json', registry)
    for mode in ('baseline', 'skill'):
        prepare(items, out / mode, mode, model, reasoning, split['purpose'], metadata)
    write_json(out / 'comparison.json', {'protocol_id': PROTOCOL, 'metadata': metadata,
                                       'model': model, 'reasoning': reasoning, 'status': 'prepared'})
    return {'prepared': str(out), 'items': len(items), 'scope': split['purpose'], 'model_calls': 0}


def score_run(prepared, run, labels, out, root):
    core, scoring = luogubench(root)
    manifest, items, _ = load_prepared(prepared)
    if manifest['scope'] == 'single':
        raise ValueError('Use benchmark preparation for formal metrics')
    if benchmark_code(root) != manifest['metadata']['luogubench_code_sha256']:
        raise ValueError('LuoguBench scoring implementation changed after preparation')
    config = read_json(Path(run) / 'run.json')
    if (config['prepared_sha256'] != digest(manifest) or config['status'] != 'complete'
            or config.get('is_demo') or config['predictions_sha256'] != file_sha(Path(run) / 'predictions.jsonl')):
        raise ValueError('Run is incomplete, modified, a demo, or belongs to different prepared requests')
    rows, truth = read_jsonl(Path(run) / 'predictions.jsonl'), read_jsonl(labels)
    expected = {i['id'] for i in items}
    if len(rows) != len(expected) or {r['id'] for r in rows} != expected:
        raise ValueError('Incomplete or duplicate predictions')
    if len(truth) != len(expected) or {r['id'] for r in truth} != expected:
        raise ValueError('Labels do not match frozen material IDs')
    for row in rows:
        validate_prediction(row, row['id'])
    split = read_json(Path(prepared).parent / 'split.json')
    if digest(split) != manifest['metadata']['split_sha256']:
        raise ValueError('Frozen split changed')
    registry = read_json(Path(prepared).parent / 'registry.json')
    if digest(registry) != manifest['metadata']['registry_sha256']:
        raise ValueError('Frozen development registry changed')
    validate_split(items, split, registry)
    problem_ids = {r['id']: r['problem_id'] for r in split['items']}
    for label in truth:
        core.validate_label(label)  # Strict native 1..8. Unknown 0 is rejected.
        if label['problem_id'] != problem_ids[label['id']]:
            raise ValueError('Labels belong to a different problem')
    out = empty_directory(out)
    result = scoring.score(labels, Path(run) / 'predictions.jsonl', out, allow_partial=False, bootstrap=0)
    result.update(scope=manifest['scope'], protocol_id=PROTOCOL, skill_version=manifest['skill_version'],
                  model=manifest['model'], generation=manifest['generation'], mode=manifest['mode'],
                  independent=manifest['scope'] == 'independent',
                  comparison_identity=digest({'inputs': manifest['inputs_sha256'], 'metadata': manifest['metadata'],
                                              'model': manifest['model'], 'generation': manifest['generation'],
                                              'adapter_sha256': config['adapter_sha256']}))
    write_json(out / 'run.json', config)
    write_json(out / 'metrics.json', result)
    return result


def compare(baseline, skill):
    a, b = read_json(baseline), read_json(skill)
    if (a['mode'] != 'baseline' or b['mode'] != 'skill' or a['comparison_identity'] != b['comparison_identity']
            or a['label_file_sha256'] != b['label_file_sha256']):
        raise ValueError('Only paired runs with identical inputs, settings and split can be compared')
    keys = ('accuracy', 'mae', 'within_one_level', 'spearman_rho', 'mean_signed_error')
    return {'scope': b['scope'], 'independent': b['independent'], 'skill_version': b['skill_version'],
            'metrics': {k: {'baseline': a[k], 'skill': b[k],
                           'delta': b[k] - a[k] if a[k] is not None and b[k] is not None else None} for k in keys}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('manifest')
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--dataset-id', required=True)
    p.add_argument('--purpose', choices=['independent', 'development_diagnostic'], required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--split', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--reasoning', default='high')
    p.add_argument('--luogubench-root', type=Path, required=True)
    p = sub.add_parser('score')
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--luogubench-root', type=Path, required=True)
    p = sub.add_parser('compare')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--skill', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'manifest':
            if args.out.exists():
                raise ValueError('Manifest already exists')
            result = make_manifest(read_jsonl(args.inputs), args.dataset_id, args.purpose, load_registry(args.registry))
            write_json(args.out, result)
        elif args.command == 'prepare':
            result = prepare_pair(args.inputs, args.split, args.registry, args.out, args.model, args.reasoning, args.luogubench_root)
        elif args.command == 'score':
            result = score_run(args.prepared, args.run, args.labels, args.out, args.luogubench_root)
        else:
            result = compare(args.baseline, args.skill)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        parser.exit(2, 'error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
