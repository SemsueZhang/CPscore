# 货币系统受限摘编

来源模型：[洛谷 P5020 / NOIP 2018 货币系统](https://www.luogu.com.cn/problem/P5020)。本文件是人工编写的自足受限版本，不是官方题面全文。

给定 n 个两两不同的正整数面额 a_i，每种货币可以使用任意多张。金额 x 可表示，是指存在 t_i 属于非负整数，使 x=sum(a_i*t_i)。两种系统等价，是指它们对每一个非负整数金额的可表示性完全一致。新系统的面额可以是任意正整数，不要求预先来自原系统。求等价系统的最少面额种数。

输入第一行 T。每组先读 n，再读 n 个面额。满足 1<=T<=5，1<=n<=20，1<=a_i<=100，且同组面额两两不同。每组输出一行最少种数。

样例输入：
```text
1
3
4 6 9
```
样例输出：
```text
3
```

---

## 待审核程序

```python
import sys


def minimum_denominations(coins):
    # Check whether an earlier denomination divides this coin.
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
```
