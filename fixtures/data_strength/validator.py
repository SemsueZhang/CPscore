import sys
try:
    values = list(map(int, sys.stdin.read().split()))
    assert values and 1 <= values[0] <= 8
    assert len(values) == values[0] + 1
    assert all(-5 <= x <= 5 for x in values[1:])
except (ValueError, AssertionError):
    sys.exit(1)
