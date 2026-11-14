#!/usr/bin/env python3
"""LuoguBench-style adapter using an existing Codex CLI login, one fresh call only.

Adapted from LuoguBench/tools/run_isolated_skill_retest.py's Backend transport.
No API client, key handling, reviewer model, retry or shared conversation.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def predict(request):
    with tempfile.TemporaryDirectory(prefix='cpscore-luogu-') as directory:
        root = Path(directory)
        schema_path = root / 'schema.json'
        response_path = root / 'response.json'
        schema_path.write_text(json.dumps(request['response_schema']), encoding='utf-8')
        developer = ('Use only the supplied single-item prompt. Do not use tools, files, browsing, '
                     'other models, skills from the host, or other questions. Return only the requested JSON.')
        cli = os.environ.get('CPSCORE_CODEX_CLI', 'codex')
        command = [cli, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                   '--sandbox', 'read-only', '--model', request['model'],
                   '-c', 'model_reasoning_effort=' + json.dumps(request['generation']['reasoning_effort']),
                   '-c', 'developer_instructions=' + json.dumps(developer),
                   '--output-schema', str(schema_path), '--json', '--color', 'never',
                   '--output-last-message', str(response_path), '-']
        prompt = request['messages'][0]['content']
        result = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                encoding='utf-8', cwd=root, timeout=570, shell=False)
        if result.returncode:
            raise ValueError('Codex transport exit ' + str(result.returncode) + ': ' + result.stderr[-2000:])
        usage, thread_ids = {}, []
        for line in result.stdout.splitlines():
            event = json.loads(line)
            if event.get('type') in ('error', 'turn.failed'):
                raise ValueError('Codex reported a failed call')
            if event.get('type') == 'thread.started':
                thread_ids.append(event['thread_id'])
            if event.get('type') == 'turn.completed':
                usage = event.get('usage', {})
            item = event.get('item', {})
            if item and item.get('type') not in ('reasoning', 'agent_message'):
                raise ValueError('Tool-free protocol violated: ' + str(item.get('type')))
        if len(thread_ids) != 1:
            raise ValueError('Expected one fresh model conversation')
        return {'prediction': json.loads(response_path.read_text(encoding='utf-8')),
                'usage': usage, 'thread_id': thread_ids[0]}


if __name__ == '__main__':
    try:
        json.dump(predict(json.load(sys.stdin)), sys.stdout, ensure_ascii=False)
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
