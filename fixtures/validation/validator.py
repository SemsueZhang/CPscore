import re
import sys

tokens = sys.stdin.buffer.read().split()
if not tokens or any(re.fullmatch(rb"-?(0|[1-9][0-9]*)", token) is None for token in tokens):
    print("expected decimal integer tokens", file=sys.stderr)
    raise SystemExit(1)
try:
    values = [int(token) for token in tokens]
except ValueError:
    raise SystemExit(1)
n = values[0]
if not 1 <= n <= 100 or len(values) != n + 1 or any(abs(value) > 10**9 for value in values[1:]):
    print("n, token count, or value range violated", file=sys.stderr)
    raise SystemExit(1)
