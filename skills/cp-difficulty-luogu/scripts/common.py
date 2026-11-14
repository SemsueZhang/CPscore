"""Small stdlib contracts, compatible with LuoguBench's label-free item format."""

import hashlib
import json
from pathlib import Path
import re

VERSION = 'cpscore-difficulty-luogu-v2.0.0'
PROTOCOL = 'cpscore-luogu-paired-isolated-v2'
LEVELS = {1: '入门', 2: '普及-', 3: '普及', 4: '普及+/提高-',
          5: '提高', 6: '提高+/省选-', 7: '省选/NOI-', 8: 'NOI/NOI+/CTS'}
SKILL = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows), encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_digest(item):
    """Detect exact historical materials even if their blinded item ID is renamed."""
    return digest({'statement_md': item['statement_md'], 'solutions': item['solutions']})


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + ' must be nonempty text')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid safe identifier')


def level(value, allow_unknown=False):
    if type(value) is not int or value not in ({0, *LEVELS} if allow_unknown else LEVELS):
        raise ValueError('level must be integer 1..8 (0 is unknown, never a valid benchmark label)')


def validate_item(item):
    # Contract mirrors luogubench.core.validate_input_item. No label/provenance fields.
    if not isinstance(item, dict) or set(item) != {'id', 'statement_md', 'solutions'}:
        raise ValueError('Input must contain exactly id, statement_md, solutions; no labels')
    identifier(item['id'])
    text(item['statement_md'], 'statement_md')
    if not isinstance(item['solutions'], list) or not 1 <= len(item['solutions']) <= 3:
        raise ValueError('Input requires 1..3 complete solutions')
    seen = set()
    for solution in item['solutions']:
        if not isinstance(solution, dict) or set(solution) != {'method_id', 'editorial_md', 'std'}:
            raise ValueError('Solution requires exactly method_id, editorial_md, std')
        method = solution['method_id']
        if not isinstance(method, str) or not re.fullmatch(r'method_[1-3]', method) or method in seen:
            raise ValueError('Invalid/duplicate solution identity')
        seen.add(method)
        text(solution['editorial_md'], 'editorial_md')
        std = solution['std']
        if not isinstance(std, dict) or set(std) != {'language', 'interface', 'code'}:
            raise ValueError('std requires exactly language, interface, code')
        if std['language'] != 'cpp17' or std['interface'] not in ('stdin_stdout', 'library'):
            raise ValueError('LuoguBench material requires cpp17 and stdin_stdout/library')
        text(std['code'], 'std.code')


def validate_prediction(row, item_id, allow_unknown=False):
    if not isinstance(row, dict) or set(row) != {'id', 'level', 'label', 'reason'}:
        raise ValueError('Prediction requires exactly id, level, label, reason')
    if row['id'] != item_id:
        raise ValueError('Prediction belongs to another problem')
    level(row['level'], allow_unknown)
    if row['label'] != ({0: '未知', **LEVELS})[row['level']]:
        raise ValueError('label does not match native level')
    text(row['reason'], 'reason')
    if len(row['reason']) > 8192:
        raise ValueError('reason exceeds 8192 characters')


def schema(allow_unknown=False):
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'id': {'type': 'string'},
                           'level': {'type': 'integer', 'minimum': 0 if allow_unknown else 1, 'maximum': 8},
                           'label': {'type': 'string', 'enum': (['未知'] if allow_unknown else []) + list(LEVELS.values())},
                           'reason': {'type': 'string', 'minLength': 1}},
            'required': ['id', 'level', 'label', 'reason']}


def empty_directory(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError('Destination must be empty: ' + str(path))
    path.mkdir(parents=True, exist_ok=True)
    return path
