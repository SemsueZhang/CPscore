#!/usr/bin/env python3
"""Run the published Subway review against an external, unchanged data folder."""
import argparse
from pathlib import Path
import resource
import subprocess
import tempfile
import time

MODES = [
    'correct', 'parallel_overwrite', 'adjacent_only', 'two_endpoints',
    'nearest_platform', 'early_visited', 'floyd_ikj', 'unsorted_lookup',
    'infinity_1e12', 'int32_distances',
]

COUNTEREXAMPLES = {
    'parallel_overwrite': ('''21 2 4 20 1
1 1 1 1
3 1 1 2 1 3 100
3 2 1 3 100 4 1
1 4
''', 6),
    'adjacent_only': ('''1 3 3 20 1
1 1 1
2 1 1 2 1
1 2 100
2 2 1 3 1
1 3
''', 6),
    'two_endpoints': ('''1 3 4 20 1
1 1 1 1
2 1 100 2 1
2 1 100 3 1
2 1 1 4 1
1 4
''', 4),
    'nearest_platform': ('''21 2 2 20 1
1 1
1 1 1
2 1 2 2 1
1 2
''', 5),
    'early_visited': ('''1 3 5 20 1
1 1 1 1 1
3 1 1 2 50 3 1
3 2 50 4 1 5 1
2 3 1 4 1
1 5
''', 8),
    'unsorted_lookup': ('''20 1 3 20 1
1 1 1
3 3 1 1 1 2 1
3 2
''', 4),
    'int32_distances': ('''21 2 3 20 1
1 1 1
2 1 1 2 600000000
2 2 600000000 3 1
1 3
''', 1200000004),
}
rows = ['24 500 501 20 1', ' '.join(['1000000000'] * 501)]
rows += [f'2 {i} 1000000000 {i+1} 1000000000' for i in range(1, 501)]
rows += ['1 501']
COUNTEREXAMPLES['infinity_1e12'] = ('\n'.join(rows) + '\n', 1002000000000)


def limit_process():
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run(command, *, source=None, payload=None):
    return subprocess.run(command, stdin=source, input=payload,
                          capture_output=True, timeout=15,
                          preexec_fn=limit_process, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='folder containing subway1.in/.ans through subway25.in/.ans')
    parser.add_argument('--compiler', default='clang++')
    parser.add_argument('--std', type=Path, help='optional original subway.cpp')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='cpscore-subway-') as temporary:
        work = Path(temporary)
        for name in ('candidates', 'verify'):
            subprocess.run([args.compiler, '-std=c++14', '-O2', '-Wall', '-Wextra',
                            str(here / f'{name}.cpp'), '-o', str(work / name)], check=True)
        if args.std:
            subprocess.run([args.compiler, '-std=c++14', '-O2', str(args.std),
                            '-o', str(work / 'std')], check=True)

        total_queries = 0
        for point in range(1, 26):
            inp, ans = args.data / f'subway{point}.in', args.data / f'subway{point}.ans'
            with inp.open() as source:
                header = source.readline().split()
            assert int(header[0]) == point
            total_queries += int(header[-1])
            result = run([str(work / 'verify'), str(inp), str(ans)])
            print(result.stdout.decode().strip(), flush=True)
        print(f'ORIGINAL: 25 valid points, {total_queries} checked answers', flush=True)

        for mode in MODES + (['original_std'] if args.std else []):
            passed, failed, slowest = [], [], 0.0
            for point in range(1, 26):
                command = ([str(work / 'std')] if mode == 'original_std'
                           else [str(work / 'candidates'), mode])
                start = time.perf_counter()
                with (args.data / f'subway{point}.in').open('rb') as source:
                    result = run(command, source=source)
                slowest = max(slowest, time.perf_counter() - start)
                answer = (args.data / f'subway{point}.ans').read_bytes()
                # Official rule: discard trailing spaces and final newlines.
                normalize = lambda data: b'\n'.join(line.rstrip(b' \t\r') for line in data.rstrip(b'\r\n').split(b'\n'))
                (passed if normalize(result.stdout) == normalize(answer) else failed).append(point)
            print(f'{mode}: pass={passed} fail={failed} score={4 * len(passed)} '
                  f'max_wall_seconds={slowest:.3f}', flush=True)

        for mode, (text, expected) in COUNTEREXAMPLES.items():
            inp, ans = work / f'{mode}.in', work / f'{mode}.ans'
            inp.write_text(text)
            ans.write_text(f'{expected}\n')
            run([str(work / 'verify'), str(inp), str(ans)])
            payload = text.encode()
            correct = run([str(work / 'candidates'), 'correct'], payload=payload)
            wrong = run([str(work / 'candidates'), mode], payload=payload)
            assert int(correct.stdout) == expected
            assert int(wrong.stdout) != expected
            if args.std:
                assert int(run([str(work / 'std')], payload=payload).stdout) == expected
            print(f'COUNTEREXAMPLE {mode}: correct={expected} actual={wrong.stdout.decode().strip()}', flush=True)


if __name__ == '__main__':
    main()
