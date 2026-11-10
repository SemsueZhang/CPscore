import sys
values = list(map(int, sys.stdin.read().split()))
print(max(values[1:]))
