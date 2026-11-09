"""Solution for context/p5020.md. No execution result is claimed."""
import sys


def minimum_denominations(coins):
    limit = max(coins)
    reachable = [False] * (limit + 1)
    reachable[0] = True
    answer = 0
    for coin in sorted(coins):
        if reachable[coin]:
            continue
        answer += 1
        for value in range(coin, limit + 1):
            reachable[value] = reachable[value] or reachable[value - coin]
    return answer


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
