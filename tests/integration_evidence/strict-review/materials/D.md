题目：输入整数 n 和恰好 n 个整数 a，输出它们的和。1<=n<=100000，-1000000000<=a_i<=1000000000。标准输入输出，Python3，时间2秒，内存256MiB。
待审程序：
```python
import sys
v=list(map(int,sys.stdin.buffer.read().split()))
print(sum(v[1:]))
```
