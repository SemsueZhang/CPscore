import random
import sys

seed, case_index = map(int, sys.argv[1:])
rng = random.Random(f"cpscore-sum-v1:{seed}:{case_index}")
n = rng.randint(1, 100)
values = [rng.randint(-10**9, 10**9) for _ in range(n)]
print(n)
print(*values)
