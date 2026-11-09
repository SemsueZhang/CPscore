import sys

values = list(map(int, sys.stdin.buffer.read().split()))
print(sum(values[1:]))
