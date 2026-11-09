"""Trusted specification implementation for the human-authored sum fixture."""
import sys

values = [int(token) for token in sys.stdin.buffer.read().split()]
print(sum(values[1:]))
