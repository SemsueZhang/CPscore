"""Artificially mutated solution for context/p5020.md, not official code."""
import sys


def minimum_denominations(coins):
    # Mutated claim: only individual divisibility can make a coin redundant.
    kept = []
    for coin in sorted(coins):
        if not any(coin % earlier == 0 for earlier in kept):
            kept.append(coin)
    return len(kept)


def main():
    data = iter(map(int, sys.stdin.buffer.read().split()))
    groups = next(data)
    answers = []
    for _ in range(groups):
        count = next(data)
        answers.append(str(minimum_denominations([next(data) for _ in range(count)])))
    print("\n".join(answers))


if __name__ == "__main__":
    main()
