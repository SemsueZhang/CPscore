#!/usr/bin/env python3
"""Validate profiles and compare intact solution routes. Python 3.8+, no API calls.

The analyst supplies problem-specific gates; this is an uncalibrated consistency
aid, not a solver or an empirical model of contestant success.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys

SKILL = Path(__file__).resolve().parents[1]
AXES = ('D', 'P', 'I', 'B')
OUTCOMES = {
    'supported': '预计能够独立完成（在所列条件下）',
    'conditional': '存在完成可能，关键环节有明显困难',
    'unknown': '信息不足，无法可靠判断',
    'progress': '可能取得有效进展，尚不能支持完整完成',
    'blocked': '预计难以取得实质性突破（限已分析路线）',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def obj(value, allowed, where):
    require(isinstance(value, dict), where + ': expected object')
    require(not set(value) - set(allowed), where + ': unexpected fields ' +
            ', '.join(sorted(set(value) - set(allowed))))
    return value


def string(value, where):
    require(isinstance(value, str) and bool(value.strip()), where + ': expected nonempty string')
    return value


def array(value, where):
    require(isinstance(value, list), where + ': expected list')
    return value


def strings(value, where):
    return [string(v, where) for v in array(value, where)]


def score(value, where, allow_unknown=True):
    if allow_unknown and (value is None or value == 'unknown'):
        return None
    require(type(value) is int and 0 <= value <= 5, where + ': expected 0..5 or unknown')
    return value


def unique(values, where):
    require(len(values) == len(set(values)), where + ': duplicate IDs/records')


def load_json(path):
    path = Path(path)
    require(path.stat().st_size <= 4_000_000, str(path) + ': exceeds 4 MB')
    raw = path.read_text(encoding='utf-8')
    if path.suffix.lower() == '.md':
        blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', raw, re.M | re.S)
        require(len(blocks) == 1, str(path) + ': expected exactly one fenced json block')
        raw = blocks[0]

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError('invalid JSON: ' + s)))


def load_catalog(path=None):
    target = path or os.environ.get('CPSCORE_CATALOG')
    target = Path(target) if target else SKILL.parents[1] / 'resources/algorithm-catalog'
    if target.is_dir():
        target = target / 'catalog.json'
    require(target.is_file(), 'Algorithm Catalog dependency missing: ' + str(target) +
            '; set CPSCORE_CATALOG or --catalog to the shared catalog (no local copy)')
    catalog = load_json(target)
    require(isinstance(catalog, dict) and type(catalog.get('schema_version')) is int and
            catalog['schema_version'] == 1, 'unsupported Algorithm Catalog schema')
    entries = array(catalog.get('entries'), 'catalog.entries')
    ids, categories = set(), set()
    for e in entries:
        require(isinstance(e, dict), 'invalid catalog entry')
        aid = string(e.get('id'), 'catalog.id')
        require(aid not in ids, 'duplicate catalog ID: ' + aid)
        ids.add(aid)
        category = strings(e.get('category'), 'catalog.category')
        require(bool(category), 'empty catalog category')
        categories.update(tuple(category[:i]) for i in range(1, len(category) + 1))
    require(bool(ids), 'empty Algorithm Catalog')
    return {'ids': ids, 'categories': categories, 'path': str(target.resolve()),
            'entries': {e['id']: e for e in entries}, 'luogu': catalog.get('luogu')}


def knowledge_references(profiles, catalog):
    """Read shared references without assigning mastery or modifying D/P/I/B."""
    users = {}
    for i, profile in enumerate(profiles):
        _, knowledge = profile_values(profile)
        for aid in knowledge:
            users.setdefault(aid, []).append(profile.get('id', 'anonymous-' + str(i)))
    tags = {t['id']: t for t in (catalog.get('luogu') or {}).get('tags', [])}
    result = []
    for aid in sorted(users):
        entry = catalog['entries'][aid]
        links = [{**link, 'name': tags[link['id']]['name'], 'kind': tags[link['id']]['kind']}
                 for link in entry.get('luogu_tags', [])]
        result.append({'algorithm_id': aid, 'name': entry['name'], 'profile_ids': users[aid],
                       'luogu_tags': links, 'knowledge_level': entry.get('knowledge_level'),
                       'problem_difficulty': entry.get('problem_difficulty')})
    return {'kind': 'shared_knowledge_references', 'catalog': catalog['path'], 'algorithms': result,
            'reference_status': 'available' if catalog.get('luogu') else 'unavailable',
            'difficulty_scale': (catalog.get('luogu') or {}).get('difficulty_scale'),
            'note': '参考索引0..7与画像掌握度0..5是不同量表；标签样本非全站分布，不推断掌握度或D/P/I/B'}


def algorithm(value, catalog):
    string(value, 'algorithm_id')
    require(value in catalog['ids'], 'unknown Algorithm Catalog ID: ' + value)
    return value


def validate_profile(profile, catalog):
    obj(profile, ('schema_version', 'profile_type', 'id', 'label', 'scope',
                  'self_assessment', 'evidence', 'assumptions'), 'profile')
    require(type(profile.get('schema_version', 2)) is int and profile.get('schema_version', 2) == 2,
            'profile schema_version must be 2; migrate v1 text manually, do not infer I/B or scores')
    require(profile.get('profile_type', 'individual') in ('individual', 'reference'), 'invalid profile_type')
    for key in ('id', 'label', 'scope'):
        if key in profile:
            string(profile[key], 'profile.' + key)
    strings(profile.get('assumptions', []), 'assumptions')
    evidence_ids = []
    for e in array(profile.get('evidence', []), 'evidence'):
        obj(e, ('id', 'source', 'conditions', 'observation', 'date', 'verification'), 'evidence')
        for key in ('id', 'source', 'conditions', 'observation'):
            string(e.get(key), 'evidence.' + key)
        if 'date' in e:
            from datetime import date
            date.fromisoformat(string(e['date'], 'evidence.date'))
        require(e.get('verification', 'reported') in ('reported', 'linked', 'reproduced'),
                'invalid evidence.verification')
        evidence_ids.append(e['id'])
    unique(evidence_ids, 'evidence')
    assessment = obj(profile.get('self_assessment', {}),
                     ('abilities', 'notes', 'knowledge', 'strengths', 'limitations'), 'self_assessment')
    abilities = obj(assessment.get('abilities', {}), AXES, 'abilities')
    for axis, value in abilities.items():
        score(value, 'abilities.' + axis)
    notes = obj(assessment.get('notes', {}), AXES, 'notes')
    for axis, value in notes.items():
        string(value, 'notes.' + axis)
    for key in ('strengths', 'limitations'):
        strings(assessment.get(key, []), key)
    knowledge = obj(assessment.get('knowledge', {}), ('categories', 'algorithms'), 'knowledge')
    seen = []
    for record in array(knowledge.get('categories', []), 'knowledge.categories'):
        obj(record, ('category', 'mastery', 'note'), 'knowledge.category')
        category = tuple(strings(record.get('category'), 'category'))
        require(category in catalog['categories'], 'unknown catalog category: ' + '/'.join(category))
        score(record.get('mastery'), 'category.mastery')
        if 'note' in record:
            string(record['note'], 'category.note')
        seen.append(category)
    unique(seen, 'knowledge.categories')
    seen = []
    for record in array(knowledge.get('algorithms', []), 'knowledge.algorithms'):
        obj(record, ('algorithm_id', 'mastery', 'note', 'evidence_ids'), 'knowledge.algorithm')
        seen.append(algorithm(record.get('algorithm_id'), catalog))
        score(record.get('mastery'), 'algorithm.mastery')
        if 'note' in record:
            string(record['note'], 'algorithm.note')
        refs = strings(record.get('evidence_ids', []), 'evidence_ids')
        unique(refs, 'evidence_ids')
        require(set(refs) <= set(evidence_ids), 'dangling evidence_ids')
    unique(seen, 'knowledge.algorithms')
    return profile


def load_profiles(value, catalog):
    profiles = value if isinstance(value, list) else [value]
    require(0 < len(profiles) <= 256, 'expected 1..256 profiles')
    for profile in profiles:
        validate_profile(profile, catalog)
    unique([p.get('id', 'anonymous-' + str(i)) for i, p in enumerate(profiles)], 'profiles')
    return profiles


def validate_analysis(analysis, catalog):
    obj(analysis, ('schema_version', 'problem_id', 'sources', 'summary', 'environment',
                   'scoring', 'routes', 'uncertainties'), 'analysis')
    require(type(analysis.get('schema_version')) is int and analysis['schema_version'] == 1,
            'analysis.schema_version must be 1')
    for key in ('problem_id', 'summary', 'environment'):
        string(analysis.get(key), 'analysis.' + key)
    require(bool(strings(analysis.get('sources'), 'sources')), 'analysis needs source references')
    require(bool(strings(analysis.get('uncertainties'), 'uncertainties')), 'state analysis uncertainties')
    scoring = obj(analysis.get('scoring'), ('mode', 'subtasks'), 'scoring')
    require(scoring.get('mode') in ('binary', 'subtasks', 'unknown'), 'invalid scoring.mode')
    subtasks = array(scoring.get('subtasks', []), 'subtasks')
    subtask_ids = []
    for sub in subtasks:
        obj(sub, ('id', 'conditions', 'credit', 'source'), 'subtask')
        for key in ('id', 'conditions', 'credit', 'source'):
            string(sub.get(key), 'subtask.' + key)
        subtask_ids.append(sub['id'])
    unique(subtask_ids, 'subtasks')
    require((scoring['mode'] == 'subtasks') == bool(subtasks),
            'only scoring.mode=subtasks may declare nonempty, sourced subtasks')
    routes = array(analysis.get('routes'), 'routes')
    require(0 < len(routes) <= 32, 'analysis needs 1..32 intact routes')
    route_ids = []
    for route in routes:
        obj(route, ('id', 'name', 'target', 'subtask_ids', 'method', 'correctness', 'complexity',
                    'initial_attempts', 'gates', 'progress'), 'route')
        for key in ('id', 'name', 'method', 'correctness', 'complexity'):
            string(route.get(key), 'route.' + key)
        route_ids.append(route['id'])
        require(route.get('target') in ('full', 'partial'), 'route.target must be full or partial')
        subs = strings(route.get('subtask_ids', []), 'route.subtask_ids')
        unique(subs, 'route.subtask_ids')
        require(set(subs) <= set(subtask_ids), 'unknown route subtask ID')
        require((route['target'] == 'partial') == bool(subs),
                'partial routes need actual subtask IDs; full routes have none')
        strings(route.get('initial_attempts', []), 'initial_attempts')
        gates = array(route.get('gates'), 'gates')
        require(0 < len(gates) <= 64, 'route needs 1..64 ordered gates')
        gate_ids, required_axes = [], set()
        for gate in gates:
            obj(gate, ('id', 'dimension', 'minimum', 'task', 'role', 'algorithm_id', 'derive'), 'gate')
            string(gate.get('id'), 'gate.id')
            string(gate.get('task'), 'gate.task')
            require(gate.get('dimension') in AXES + ('K',), 'invalid gate dimension')
            score(gate.get('minimum'), 'gate.minimum', False)
            require(gate.get('role', 'required') in ('required', 'helpful'), 'invalid gate role')
            if gate.get('role', 'required') == 'required':
                required_axes.add(gate['dimension'])
            gate_ids.append(gate['id'])
            if gate['dimension'] == 'K':
                algorithm(gate.get('algorithm_id'), catalog)
            else:
                require(not {'algorithm_id', 'derive'} & set(gate), 'only K gates have algorithm_id/derive')
            if 'derive' in gate:
                derive = obj(gate['derive'], ('D', 'P', 'task'), 'derive')
                for axis in ('D', 'P'):
                    score(derive.get(axis), 'derive.' + axis, False)
                string(derive.get('task'), 'derive.task')
        unique(gate_ids, 'route.gates')
        require(set(AXES) <= required_axes, 'each intact route must assess D/P/I/B (minimum 0 is allowed)')
        for progress in array(route.get('progress', []), 'route.progress'):
            obj(progress, ('after_gate', 'description'), 'progress')
            require(progress.get('after_gate') in gate_ids, 'unknown progress gate')
            string(progress.get('description'), 'progress.description')
    unique(route_ids, 'routes')
    require(any(r['target'] == 'full' for r in routes), 'at least one full route required')
    return analysis


def compare(value, minimum):
    if minimum == 0:
        return 'supported'
    if value is None:
        return 'unknown'
    if value >= minimum:
        return 'supported'
    if value == 0:
        return 'gap'
    return 'strain' if value == minimum - 1 else 'gap'


def profile_values(profile):
    assessment = profile.get('self_assessment', {})
    abilities = {a: score(assessment.get('abilities', {}).get(a), a) for a in AXES}
    knowledge = {r['algorithm_id']: score(r.get('mastery'), 'mastery')
                 for r in assessment.get('knowledge', {}).get('algorithms', [])}
    return abilities, knowledge


def evaluate_route(route, abilities, knowledge):
    trace = []
    for gate in route['gates']:
        axis = gate['dimension']
        value = knowledge.get(gate['algorithm_id']) if axis == 'K' else abilities[axis]
        state = compare(value, gate['minimum'])
        mode = 'known' if axis == 'K' else 'ability'
        if axis == 'K' and state != 'supported' and 'derive' in gate:
            derive = gate['derive']
            ds = [compare(abilities[a], derive[a]) for a in ('D', 'P')]
            if all(s == 'supported' for s in ds):
                # A proposed reconstruction is always conditional, never a proven discovery.
                state, mode = 'strain', 'reconstruct'
            elif state == 'gap' and 'unknown' in ds:
                state, mode = 'unknown', 'reconstruction-uncertain'
        trace.append({'id': gate['id'], 'dimension': axis, 'state': state,
                      'mode': mode, 'task': gate['task'], 'value': value,
                      'minimum': gate['minimum'], 'required': gate.get('role', 'required') == 'required',
                      **({'algorithm_id': gate['algorithm_id']} if axis == 'K' else {}),
                      **({'reconstruction': gate['derive']['task']} if mode.startswith('reconstruct') else {})})
    required = [g for g in trace if g['required']]
    states = {g['state'] for g in required}
    progress = []
    for milestone in route.get('progress', []):
        end = next(i for i, g in enumerate(trace) if g['id'] == milestone['after_gate'])
        if all(g['state'] == 'supported' for g in trace[:end + 1] if g['required']):
            progress.append(milestone['description'])
    if 'gap' in states:
        outcome = 'progress' if progress else 'blocked'
    elif 'unknown' in states:
        outcome = 'unknown'
    elif 'strain' in states:
        outcome = 'conditional'
    else:
        outcome = 'supported'
    return {'route_id': route['id'], 'target': route['target'], 'outcome': outcome,
            'trace': trace, 'progress': progress, 'subtask_ids': route.get('subtask_ids', []),
            'initial_attempts': route.get('initial_attempts', [])}


def evaluate_profile(analysis, profile, index=0):
    abilities, knowledge = profile_values(profile)
    routes = [evaluate_route(r, abilities, knowledge) for r in analysis['routes']]
    full = [r for r in routes if r['target'] == 'full']
    rank = {key: i for i, key in enumerate(('supported', 'conditional', 'unknown', 'progress', 'blocked'))}
    best = min(rank[r['outcome']] for r in full)
    selected = [r for r in full if rank[r['outcome']] == best]
    outcome = selected[0]['outcome']
    partial = [r for r in routes if r['target'] == 'partial' and r['outcome'] in ('supported', 'conditional')]
    if partial and outcome in ('blocked', 'progress'):
        outcome = 'progress'
    return {'profile_id': profile.get('id', 'anonymous-' + str(index)), 'outcome': outcome,
            'selected_routes': [r['route_id'] for r in selected],
            'partial_options': [{'route_id': r['route_id'], 'subtask_ids': r['subtask_ids'],
                                 'conditional': r['outcome'] == 'conditional'} for r in partial],
            'routes': routes}


def signature(result):
    """Ignore raw scores and helpful gates; preserve causal barriers and intact routes."""
    relevant = [r for r in result['routes'] if r['route_id'] in result['selected_routes']]
    # Failed alternatives explain why a partial route was selected or a full route unavailable.
    if result['outcome'] != 'supported':
        relevant = [r for r in result['routes'] if r['target'] == 'full']
    route_keys = []
    for r in relevant:
        barriers = [(g['id'], g['state'], g['mode']) for g in r['trace']
                    if g['required'] and g['state'] != 'supported']
        route_keys.append((r['route_id'], r['outcome'], barriers, r['progress']))
    return json.dumps([result['outcome'], result['selected_routes'], result['partial_options'], route_keys],
                      ensure_ascii=False, sort_keys=True)


def group_results(results):
    groups = {}
    for result in results:
        key = signature(result)
        if key not in groups:
            barriers = []
            for r in result['routes']:
                if r['target'] == 'full' and (result['outcome'] != 'supported' or
                                             r['route_id'] in result['selected_routes']):
                    barriers.extend({'route_id': r['route_id'], **{k: g[k] for k in
                                     ('id', 'dimension', 'state', 'mode', 'task')}}
                                    for g in r['trace'] if g['required'] and g['state'] != 'supported')
            groups[key] = {'profile_ids': [], 'outcome': result['outcome'],
                           'interpretation': OUTCOMES[result['outcome']],
                           'selected_routes': result['selected_routes'], 'barriers': barriers,
                           'partial_options': result['partial_options'],
                           'progress': list(dict.fromkeys(p for r in result['routes'] for p in r['progress']))}
        groups[key]['profile_ids'].append(result['profile_id'])
    return list(groups.values())


def sensitivity(analysis, profile):
    baseline = evaluate_profile(analysis, profile)
    baseline_key = signature(baseline)
    abilities, knowledge = profile_values(profile)
    used = {g['algorithm_id'] for r in analysis['routes'] for g in r['gates'] if g['dimension'] == 'K'}
    changes, unknown = [], []
    fields = [(a, v, None) for a, v in abilities.items()]
    fields += [('K', knowledge.get(aid), aid) for aid in sorted(used)]
    for axis, value, aid in fields:
        if value is None:
            unknown.append(aid or axis)
            continue
        for new in (value - 1, value + 1):
            if not 0 <= new <= 5:
                continue
            modified = copy.deepcopy(profile)
            if aid:
                for record in modified['self_assessment']['knowledge']['algorithms']:
                    if record['algorithm_id'] == aid:
                        record['mastery'] = new
            else:
                modified['self_assessment']['abilities'][axis] = new
            result = evaluate_profile(analysis, modified)
            if signature(result) == baseline_key:
                continue
            gates = []
            for old_route, new_route in zip(baseline['routes'], result['routes']):
                for old, updated in zip(old_route['trace'], new_route['trace']):
                    if old['required'] and (old['state'], old['mode']) != (updated['state'], updated['mode']):
                        gates.append({'route_id': old_route['route_id'], 'gate_id': old['id'],
                                      'task': old['task'], 'from': old['state'], 'to': updated['state']})
            changes.append({'dimension': aid or axis, 'from': value, 'to': new,
                            'outcome_from': baseline['outcome'], 'outcome_to': result['outcome'],
                            'changed_gates': gates})
    return {'changes': changes, 'unassessed_unknown': unknown,
            'note': '规则敏感性，非因果实验；须审查门槛是否对应真实任务，未知不自动补值'}


def audit_references(profiles):
    require(len(profiles) == 16, 'expected exactly 16 reference anchors')
    seen, knowledge_sets, vectors = set(), {}, {}
    coverage = set()
    ranges = {a: set() for a in AXES}
    for p in profiles:
        require(p.get('profile_type') == 'reference', 'reference bundle must only contain reference profiles')
        require(p.get('id') and p.get('scope') and p.get('assumptions'), 'reference needs id/scope/assumptions')
        require(not p.get('evidence'), 'hypothetical references must not contain real-player evidence')
        abilities, knowledge = profile_values(p)
        require(all(v is not None for v in abilities.values()), 'anchors need explicit D/P/I/B')
        vector = tuple(abilities[a] for a in AXES)
        k = json.dumps(knowledge, sort_keys=True)
        assessment = p.get('self_assessment', {})
        key = (vector, k, json.dumps(assessment.get('knowledge', {}).get('categories', []), sort_keys=True))
        require(key not in seen, 'duplicate reference ability/knowledge data')
        seen.add(key)
        for a, v in abilities.items():
            ranges[a].add(v)
        coverage.update(knowledge)
        vectors.setdefault(vector, []).append(p['id'])
        knowledge_sets.setdefault(k, []).append(p['id'])
    return {'count': len(profiles), 'axis_values': {a: sorted(v) for a, v in ranges.items()},
            'explicit_algorithm_count': len(coverage),
            'same_abilities_different_knowledge': [v for v in vectors.values() if len(v) > 1],
            'same_knowledge_different_abilities': [v for v in knowledge_sets.values() if len(v) > 1],
            'limitation': '人工假设锚点；结构覆盖检查不能证明代表性或预测准确率'}


def predict(analysis, profiles, details=False):
    results = [evaluate_profile(analysis, p, i) for i, p in enumerate(profiles)]
    groups = group_results(results)
    output = {'kind': 'qualitative_inference', 'problem_id': analysis['problem_id'],
              'environment': analysis['environment'], 'sources': analysis['sources'],
              'scoring': analysis['scoring'],
              'profile_basis': ('hypothetical_reference_anchors' if all(
                  p.get('profile_type') == 'reference' for p in profiles) else
                  'submitted_assessments_or_mixed; evidence is not automatically verified'),
              'route_summaries': [{k: r[k] for k in ('id', 'name', 'target', 'method', 'complexity')}
                                  for r in analysis['routes']],
              'profile_count': len(profiles),
              'group_count': len(groups), 'groups': groups,
              'uncertainties': analysis['uncertainties'],
              'limitations': ['未校准的规则初稿，需按 prediction.md 作语义审查',
                              '画像与阈值均非成功概率；没有执行选手求解或测量耗时',
                              '不支持的已分析路线不等于不存在其他解法；类别知识不外推具体算法']}
    if details:
        output['internal_assessments'] = results
        output['sensitivity'] = {r['profile_id']: sensitivity(analysis, p) for r, p in zip(results, profiles)}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', help='single shared catalog directory or catalog.json')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('validate', help='validate an individual profile or a reference bundle')
    check.add_argument('profile')
    audit = sub.add_parser('audit', help='check all 16 shipped reference anchors')
    audit.add_argument('--profiles', default=str(SKILL / 'references/reference-profiles.json'))
    knowledge = sub.add_parser('knowledge', help='read shared algorithm references for submitted profiles')
    knowledge.add_argument('--profiles', default=str(SKILL / 'references/reference-profiles.json'))
    run = sub.add_parser('predict', help='compare routes once analyzed by a human/LLM')
    run.add_argument('analysis')
    run.add_argument('--profiles', default=str(SKILL / 'references/reference-profiles.json'))
    run.add_argument('--details', action='store_true', help='include private per-profile traces and sensitivity')
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.catalog)
        path = args.profile if args.command == 'validate' else args.profiles
        profiles = load_profiles(load_json(path), catalog)
        if args.command == 'validate':
            result = {'valid': True, 'profile_count': len(profiles), 'catalog': catalog['path'],
                      'provenance': '结构和 ID 校验，不认证自评或经历真实性'}
        elif args.command == 'audit':
            result = audit_references(profiles)
        elif args.command == 'knowledge':
            result = knowledge_references(profiles, catalog)
        else:
            analysis = validate_analysis(load_json(args.analysis), catalog)
            result = predict(analysis, profiles, args.details)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
